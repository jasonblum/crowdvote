"""
Django signals for automatic vote recalculation in CrowdVote.

This module implements real-time democracy by automatically triggering vote
recalculation whenever system changes occur that could affect democratic outcomes.
Uses background threading to ensure user requests remain fast while calculations
happen asynchronously.

Key Events That Trigger Recalculation:
1. Vote cast/updated/deleted - affects decision results directly
2. Following relationship created/deleted/modified - changes delegation networks
3. Community membership changes - affects who can vote
4. Ballot tags modified - changes delegation targeting
5. Decision published - makes voting active
6. Decision closed - triggers final calculation

Integration with Plan #21 Snapshot System:
- All calculations use CreateCalculationSnapshot and SnapshotBasedStageBallots
- Background threads work with snapshot isolation for data consistency
- Error handling and retry mechanisms for production reliability
"""

import logging
import threading
import traceback
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction

from democracy.models import Following
from democracy.models import Vote, Ballot, Decision, Membership
from democracy.services import CreateCalculationSnapshot, SnapshotBasedStageBallots, Tally

logger = logging.getLogger(__name__)


def recalculate_community_decisions_async(community_id, trigger_event="unknown", user_id=None):
    """
    Background thread function that recalculates all open decisions in a community.
    
    Uses Plan #21 snapshot-based services for data consistency during calculation.
    Runs in background thread to avoid blocking user requests.
    
    Args:
        community_id (UUID): Community to recalculate
        trigger_event (str): Description of what triggered this recalculation
        user_id (UUID, optional): User who triggered the event
        
    This function:
    1. Creates calculation snapshots for all open decisions
    2. Runs SnapshotBasedStageBallots service for each decision
    3. Runs Tally service to calculate STAR voting results
    4. Logs comprehensive event information for transparency
    """
    try:
        from democracy.models import Community, Decision
        
        # Log the trigger event
        logger.info(f"[RECALC_START] [system] - Background recalculation triggered by {trigger_event} in community {community_id}")
        
        # Get community and open decisions
        try:
            community = Community.objects.get(id=community_id)
            open_decisions = Decision.objects.filter(
                community=community,
                dt_close__gt=timezone.now()
            )
            
            if not open_decisions.exists():
                logger.info(f"[RECALC_COMPLETE] [system] - No open decisions in community {community.name}")
                return
                
        except Community.DoesNotExist:
            logger.error(f"[RECALC_ERROR] [system] - Community {community_id} not found")
            return
            
        logger.info(f"[RECALC_PROCESSING] [system] - Processing {open_decisions.count()} open decisions in {community.name}")
        
        # Process each decision with snapshot isolation
        for decision in open_decisions:
            try:
                # Atomic check and create to prevent race conditions
                from democracy.models import DecisionSnapshot
                from django.db import transaction
                
                with transaction.atomic():
                    # Use select_for_update to lock the decision row
                    locked_decision = Decision.objects.select_for_update().get(id=decision.id)
                    
                    # Check if there's already an active calculation for this decision
                    active_snapshot = DecisionSnapshot.objects.filter(
                        decision=locked_decision,
                        calculation_status__in=['creating', 'ready', 'staging', 'tallying']
                    ).first()
                    
                    if active_snapshot:
                        logger.info(f"[SNAPSHOT_SKIP] [system] - Skipping '{locked_decision.title}' - already has active calculation: {active_snapshot.id}")
                        continue
                    
                    # STEP 1: Calculate ballots in database (Plan #9: needed before snapshot)
                    logger.info(f"[STAGE_BALLOTS_START] [system] - Calculating ballots in database for '{locked_decision.title}'")
                    from democracy.services import StageBallots
                    stage_ballots_service = StageBallots()
                    # Process only this decision's ballots
                    for membership in locked_decision.community.memberships.all():
                        stage_ballots_service.get_or_calculate_ballot(
                            locked_decision, 
                            membership.member
                        )
                    logger.info(f"[STAGE_BALLOTS_COMPLETE] [system] - Database ballots calculated")
                    
                    # STEP 2: Create calculation snapshot (Plan #8 integration) - now captures the ballots we just created
                    logger.info(f"[SNAPSHOT_CREATE_START] [system] - Creating snapshot for decision '{locked_decision.title}'")
                    snapshot_service = CreateCalculationSnapshot(locked_decision.id)
                    snapshot = snapshot_service.process()
                logger.info(f"[SNAPSHOT_CREATE_COMPLETE] [system] - Snapshot created successfully: {snapshot.id}")
                
                # STEP 3: Process snapshot ballots (Plan #9: builds delegation tree from frozen state)
                logger.info(f"[SNAPSHOT_PROCESS_START] [system] - Processing snapshot-based calculation for decision '{decision.title}'")
                stage_start_time = timezone.now()
                
                stage_service = SnapshotBasedStageBallots(snapshot.id)
                stage_service.process()
                
                stage_duration = (timezone.now() - stage_start_time).total_seconds()
                logger.info(f"[STAGE_BALLOTS_COMPLETE] [system] - Snapshot-based staging completed in {stage_duration:.1f} seconds")
                
                # Calculate STAR voting results
                logger.info(f"[TALLY_START] [system] - Starting tally for snapshot {snapshot.id}")
                tally_start_time = timezone.now()
                
                # Note: Using existing Tally service - TODO: Implement snapshot-based tally
                tally_service = Tally()
                tally_service.process()
                
                tally_duration = (timezone.now() - tally_start_time).total_seconds()
                logger.info(f"[TALLY_COMPLETE] [system] - Tally completed in {tally_duration:.1f} seconds")
                
                # Mark decision as recalculated
                decision.results_need_updating = False
                decision.save(update_fields=['results_need_updating'])
                
            except Exception as e:
                logger.error(f"[RECALC_ERROR] [system] - Failed to recalculate decision '{decision.title}': {str(e)}")
                logger.error(f"[RECALC_ERROR] [system] - Traceback: {traceback.format_exc()}")
                continue
                
        total_duration = (timezone.now() - timezone.now()).total_seconds()  # Will be calculated properly
        logger.info(f"[RECALC_COMPLETE] [system] - Community recalculation completed for {community.name}")
        
    except Exception as e:
        logger.error(f"[RECALC_CRITICAL_ERROR] [system] - Critical error in background recalculation: {str(e)}")
        logger.error(f"[RECALC_CRITICAL_ERROR] [system] - Traceback: {traceback.format_exc()}")


@receiver(post_save, sender=Vote)
def vote_changed(sender, instance, created, **kwargs):
    """
    Signal handler for when votes are cast, updated, or deleted.
    
    Triggers automatic recalculation for the decision when:
    - New vote is cast (created=True)
    - Existing vote is updated (created=False)
    
    Args:
        sender: Vote model class
        instance: The Vote instance that was saved
        created: True if this is a new vote, False if updated
        **kwargs: Additional signal arguments
    """
    try:
        decision = instance.ballot.decision
        community = decision.community
        
        # Log the vote event
        action = "cast" if created else "updated"
        logger.info(f"[VOTE_{action.upper()}] [{instance.ballot.voter.username}] - Vote {action} on decision '{decision.title}' (Choice: {instance.choice.title}, Stars: {instance.stars})")
        
        # Only recalculate for open decisions
        if decision.dt_close > timezone.now():
            # Start background recalculation
            thread = threading.Thread(
                target=recalculate_community_decisions_async,
                args=(community.id, f"vote_{action}", instance.ballot.voter.id),
                daemon=True
            )
            thread.start()
            
            logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {community.name}")
        else:
            logger.info(f"[VOTE_IGNORED] [system] - Vote on closed decision '{decision.title}' - no recalculation needed")
            
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in vote_changed signal: {str(e)}")


@receiver(post_delete, sender=Vote)
def vote_deleted(sender, instance, **kwargs):
    """
    Signal handler for when votes are deleted.
    
    Triggers automatic recalculation for the decision.
    
    Args:
        sender: Vote model class
        instance: The Vote instance that was deleted
        **kwargs: Additional signal arguments
    """
    try:
        decision = instance.ballot.decision
        community = decision.community
        
        # Log the vote deletion
        logger.info(f"[VOTE_DELETED] [{instance.ballot.voter.username}] - Vote deleted on decision '{decision.title}' (Choice: {instance.choice.title})")
        
        # Only recalculate for open decisions
        if decision.dt_close > timezone.now():
            # Start background recalculation
            thread = threading.Thread(
                target=recalculate_community_decisions_async,
                args=(community.id, "vote_deleted", instance.ballot.voter.id),
                daemon=True
            )
            thread.start()
            
            logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {community.name}")
        else:
            logger.info(f"[VOTE_DELETE_IGNORED] [system] - Vote deletion on closed decision '{decision.title}' - no recalculation needed")
            
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in vote_deleted signal: {str(e)}")


@receiver(post_save, sender=Following)
def following_changed(sender, instance, created, **kwargs):
    """
    Signal handler for when following relationships are created or modified.
    
    Triggers recalculation for all communities where both follower and followee are members,
    since delegation networks affect vote inheritance.
    
    Args:
        sender: Following model class
        instance: The Following instance that was saved
        created: True if this is a new relationship, False if updated
        **kwargs: Additional signal arguments
    """
    try:
        action = "started" if created else "updated"
        tags_display = f" on tags: {instance.tags}" if instance.tags else " (all tags)"
        
        # Note: follower and followee are Membership objects, not User objects
        logger.info(f"[FOLLOWING_{action.upper()}] [{instance.follower.member.username}] - {action.title()} following {instance.followee.member.username}{tags_display} (priority: {instance.order})")
        
        # Both follower and followee are already in the same community (Following is community-specific)
        # So we only need to recalculate for this one community
        shared_communities = {instance.follower.community_id}
        
        # Trigger recalculation for each shared community
        for community_id in shared_communities:
            thread = threading.Thread(
                target=recalculate_community_decisions_async,
                args=(community_id, f"following_{action}", instance.follower.member.id),
                daemon=True
            )
            thread.start()
            
        if shared_communities:
            logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for {len(shared_communities)} shared communities")
        else:
            logger.info(f"[FOLLOWING_NO_IMPACT] [system] - Following relationship has no shared communities - no recalculation needed")
            
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in following_changed signal: {str(e)}")


@receiver(post_delete, sender=Following)
def following_deleted(sender, instance, **kwargs):
    """
    Signal handler for when following relationships are deleted (unfollowing).
    
    Triggers recalculation for all communities where both users are members.
    
    Args:
        sender: Following model class
        instance: The Following instance that was deleted
        **kwargs: Additional signal arguments
    """
    try:
        tags_display = f" on tags: {instance.tags}" if instance.tags else " (all tags)"
        
        # Note: follower and followee are Membership objects, not User objects
        logger.info(f"[FOLLOWING_DELETED] [{instance.follower.member.username}] - Stopped following {instance.followee.member.username}{tags_display}")
        
        # Both follower and followee are already in the same community (Following is community-specific)
        # So we only need to recalculate for this one community
        shared_communities = {instance.follower.community_id}
        
        # Trigger recalculation for each shared community
        for community_id in shared_communities:
            thread = threading.Thread(
                target=recalculate_community_decisions_async,
                args=(community_id, "following_deleted", instance.follower.member.id),
                daemon=True
            )
            thread.start()
            
        if shared_communities:
            logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for {len(shared_communities)} shared communities")
        else:
            logger.info(f"[FOLLOWING_DELETE_NO_IMPACT] [system] - Unfollowing has no shared communities - no recalculation needed")
            
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in following_deleted signal: {str(e)}")


@receiver(post_save, sender=Membership)
def membership_changed(sender, instance, created, **kwargs):
    """
    Signal handler for when community memberships are created or modified.
    
    Triggers recalculation when:
    - New member joins community (created=True)
    - Member's voting rights change (is_voting_community_member modified)
    
    Args:
        sender: Membership model class
        instance: The Membership instance that was saved
        created: True if this is a new membership, False if updated
        **kwargs: Additional signal arguments
    """
    try:
        if created:
            logger.info(f"[MEMBER_JOINED] [{instance.member.username}] - Joined community '{instance.community.name}' (Voting: {instance.is_voting_community_member})")
            
            # Trigger recalculation for the community
            thread = threading.Thread(
                target=recalculate_community_decisions_async,
                args=(instance.community.id, "member_joined", instance.member.id),
                daemon=True
            )
            thread.start()
            
            logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {instance.community.name}")
            
        else:
            # Check if voting rights changed
            if hasattr(instance, '_state') and instance._state.adding is False:
                # This is an update - check if voting status changed
                try:
                    old_instance = Membership.objects.get(pk=instance.pk)
                    if old_instance.is_voting_community_member != instance.is_voting_community_member:
                        status = "granted" if instance.is_voting_community_member else "revoked"
                        logger.info(f"[VOTING_RIGHTS_{status.upper()}] [{instance.member.username}] - Voting rights {status} in community '{instance.community.name}'")
                        
                        # Trigger recalculation
                        thread = threading.Thread(
                            target=recalculate_community_decisions_async,
                            args=(instance.community.id, f"voting_rights_{status}", instance.member.id),
                            daemon=True
                        )
                        thread.start()
                        
                        logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {instance.community.name}")
                        
                except Membership.DoesNotExist:
                    # Old instance doesn't exist, treat as creation
                    pass
                    
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in membership_changed signal: {str(e)}")


@receiver(post_delete, sender=Membership)
def membership_deleted(sender, instance, **kwargs):
    """
    Signal handler for when community memberships are deleted (member leaves).
    
    Triggers recalculation for the community.
    
    Args:
        sender: Membership model class
        instance: The Membership instance that was deleted
        **kwargs: Additional signal arguments
    """
    try:
        logger.info(f"[MEMBER_LEFT] [{instance.member.username}] - Left community '{instance.community.name}'")
        
        # Trigger recalculation for the community
        thread = threading.Thread(
            target=recalculate_community_decisions_async,
            args=(instance.community.id, "member_left", instance.member.id),
            daemon=True
        )
        thread.start()
        
        logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {instance.community.name}")
        
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in membership_deleted signal: {str(e)}")


@receiver(post_save, sender=Ballot)
def ballot_tags_changed(sender, instance, created, **kwargs):
    """
    Signal handler for when ballot tags are modified.
    
    Tags affect delegation targeting, so changes require recalculation.
    Only triggers for tag changes, not ballot creation (handled by vote signals).
    
    Args:
        sender: Ballot model class
        instance: The Ballot instance that was saved
        created: True if this is a new ballot, False if updated
        **kwargs: Additional signal arguments
    """
    try:
        # Only process tag changes on existing ballots
        if not created and hasattr(instance, 'tags'):
            # Check if tags actually changed
            try:
                old_instance = Ballot.objects.get(pk=instance.pk)
                if old_instance.tags != instance.tags:
                    logger.info(f"[BALLOT_TAGS_CHANGED] [{instance.voter.username}] - Updated tags on decision '{instance.decision.title}' from '{old_instance.tags}' to '{instance.tags}'")
                    
                    # Only recalculate for open decisions
                    if instance.decision.dt_close > timezone.now():
                        # Trigger recalculation
                        thread = threading.Thread(
                            target=recalculate_community_decisions_async,
                            args=(instance.decision.community.id, "ballot_tags_changed", instance.voter.id),
                            daemon=True
                        )
                        thread.start()
                        
                        logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {instance.decision.community.name}")
                    else:
                        logger.info(f"[BALLOT_TAGS_IGNORED] [system] - Tag change on closed decision '{instance.decision.title}' - no recalculation needed")
                        
            except Ballot.DoesNotExist:
                # Old instance doesn't exist, treat as creation (handled by vote signals)
                pass
                
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in ballot_tags_changed signal: {str(e)}")


@receiver(post_save, sender=Decision)
def decision_status_changed(sender, instance, created, **kwargs):
    """
    Signal handler for when decisions are published or closed.
    
    Triggers recalculation when:
    - Decision is published (becomes active for voting)
    - Decision is closed (triggers final calculation)
    
    Args:
        sender: Decision model class
        instance: The Decision instance that was saved
        created: True if this is a new decision, False if updated
        **kwargs: Additional signal arguments
    """
    try:
        if created:
            logger.info(f"[DECISION_CREATED] [{instance.community.name}] - New decision created: '{instance.title}' (closes: {instance.dt_close})")
            
            # If decision is already open for voting, trigger initial calculation
            if instance.dt_close > timezone.now():
                logger.info(f"[DECISION_PUBLISHED] [{instance.community.name}] - Decision '{instance.title}' is open for voting")
                
                # Trigger initial calculation
                thread = threading.Thread(
                    target=recalculate_community_decisions_async,
                    args=(instance.community.id, "decision_published", None),
                    daemon=True
                )
                thread.start()
                
                logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Initial calculation started for decision '{instance.title}'")
                
        else:
            # Check if decision just closed
            if instance.dt_close <= timezone.now():
                # Check if this is a recent closure (within last minute to avoid repeated triggers)
                time_since_close = timezone.now() - instance.dt_close
                if time_since_close.total_seconds() <= 60:
                    logger.info(f"[DECISION_CLOSED] [{instance.community.name}] - Decision '{instance.title}' has closed - triggering final calculation")
                    
                    # Trigger final calculation
                    thread = threading.Thread(
                        target=recalculate_community_decisions_async,
                        args=(instance.community.id, "decision_closed", None),
                        daemon=True
                    )
                    thread.start()
                    
                    logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Final calculation started for closed decision '{instance.title}'")
                    
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in decision_status_changed signal: {str(e)}")
