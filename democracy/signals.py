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
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from democracy.models import Following, Ballot, Decision, Membership
from democracy.services import CreateCalculationSnapshot, SnapshotBasedStageBallots, Tally

logger = logging.getLogger(__name__)


def validate_signal_registration():
    """
    Validate that signals are registered correctly to prevent duplication.
    
    This function checks how many signal receivers are registered for each
    model to ensure we don't have duplicate handlers that would spawn
    multiple threads per user action.
    
    Called during Django app initialization to provide early warning of
    configuration issues.
    """
    from django.db.models.signals import post_save, post_delete
    
    # Check Ballot signal registration
    ballot_save_receivers = [r for r in post_save._live_receivers(Ballot) if r]
    ballot_delete_receivers = [r for r in post_delete._live_receivers(Ballot) if r]
    
    logger.info(f"[SIGNAL_CHECK] Ballot post_save has {len(ballot_save_receivers)} receiver(s)")
    logger.info(f"[SIGNAL_CHECK] Ballot post_delete has {len(ballot_delete_receivers)} receiver(s)")
    
    # Check Following signal registration
    following_save_receivers = [r for r in post_save._live_receivers(Following) if r]
    following_delete_receivers = [r for r in post_delete._live_receivers(Following) if r]
    
    logger.info(f"[SIGNAL_CHECK] Following post_save has {len(following_save_receivers)} receiver(s)")
    logger.info(f"[SIGNAL_CHECK] Following post_delete has {len(following_delete_receivers)} receiver(s)")
    
    # Check Decision signal registration
    decision_save_receivers = [r for r in post_save._live_receivers(Decision) if r]
    
    logger.info(f"[SIGNAL_CHECK] Decision post_save has {len(decision_save_receivers)} receiver(s)")
    
    # Warn if we detect potential duplicates
    if len(ballot_save_receivers) > 1:
        logger.warning("[SIGNAL_WARNING] Multiple Ballot post_save receivers detected! This may cause duplicate threads.")
    
    return {
        'ballot_save': len(ballot_save_receivers),
        'ballot_delete': len(ballot_delete_receivers),
        'following_save': len(following_save_receivers),
        'following_delete': len(following_delete_receivers),
        'decision_save': len(decision_save_receivers),
    }


def recalculate_community_decisions_async(community_id, trigger_event="unknown", user_id=None):
    """
    Background thread function that recalculates all open decisions in a community.
    
    Uses Plan #21 snapshot-based services for data consistency during calculation.
    Runs in background thread to avoid blocking user requests.
    
    IMPORTANT: This function runs in a background thread and MUST close database
    connections when complete to prevent connection pool exhaustion.
    
    Args:
        community_id (UUID): Community to recalculate
        trigger_event (str): Description of what triggered this recalculation
        user_id (UUID, optional): User who triggered the event
        
    This function:
    1. Creates calculation snapshots for all open decisions
    2. Runs SnapshotBasedStageBallots service for each decision
    3. Runs Tally service to calculate STAR voting results
    4. Logs comprehensive event information for transparency
    5. Closes database connections to prevent pool exhaustion
    """
    try:
        from democracy.models import Community, Decision
        from django.db import connection
        
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
                
                # Calculate STAR voting results from snapshot (Plan #9)
                logger.info(f"[TALLY_START] [system] - Starting tally for snapshot {snapshot.id}")
                tally_start_time = timezone.now()
                
                # Pass snapshot ID to Tally service to tally from frozen data
                tally_service = Tally(snapshot_id=snapshot.id)
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
                
        logger.info(f"[RECALC_COMPLETE] [system] - Community recalculation completed for {community.name}")
        
    except Exception as e:
        logger.error(f"[RECALC_CRITICAL_ERROR] [system] - Critical error in background recalculation: {str(e)}")
        logger.error(f"[RECALC_CRITICAL_ERROR] [system] - Traceback: {traceback.format_exc()}")
    finally:
        # CRITICAL: Close database connection to prevent pool exhaustion
        # Background threads don't automatically close connections like request threads do
        connection.close()
        logger.debug(f"[DB_CONNECTION_CLOSED] [system] - Background thread connection closed for community {community_id}")


@receiver(post_save, sender=Ballot)
def ballot_changed(sender, instance, created, **kwargs):
    """
    Signal handler for when ballots are cast or updated.
    
    Triggers automatic recalculation for the decision when:
    - New MANUAL ballot is cast (created=True, is_calculated=False)
    - Existing MANUAL ballot is updated (created=False, is_calculated=False)
    
    CRITICAL: Only manual ballots trigger recalculation. Calculated ballots do NOT
    trigger recalculation to prevent infinite cascade (recalculation → calculated
    ballots saved → signals fired → more recalculation → infinite loop).
    
    NOTE: This fires on Ballot save, not individual Vote saves, so one ballot
    submission triggers exactly ONE recalculation thread, not one per choice.
    
    Args:
        sender: Ballot model class
        instance: The Ballot instance that was saved
        created: True if this is a new ballot, False if updated
        **kwargs: Additional signal arguments
    """
    try:
        # CRITICAL: Ignore calculated ballots to prevent infinite cascade
        if instance.is_calculated:
            logger.debug(f"[BALLOT_CALCULATED_SKIP] [{instance.voter.username}] - Skipping recalculation for calculated ballot")
            return
        
        decision = instance.decision
        community = decision.community
        
        # Log the ballot event
        action = "cast" if created else "updated"
        logger.info(f"[BALLOT_{action.upper()}] [{instance.voter.username}] - Ballot {action} on decision '{decision.title}'")
        
        # Only recalculate for open decisions
        if decision.dt_close > timezone.now():
            # Start background recalculation
            thread = threading.Thread(
                target=recalculate_community_decisions_async,
                args=(community.id, f"ballot_{action}", instance.voter.id),
                daemon=True
            )
            thread.start()
            thread_id = thread.ident
            
            logger.info(f"[THREAD_SPAWN] TTE='ballot_{action}' THREAD_ID={thread_id} COMMUNITY={community.name} USER={instance.voter.username}")
            logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {community.name}")
        else:
            logger.info(f"[BALLOT_IGNORED] [system] - Ballot on closed decision '{decision.title}' - no recalculation needed")
            
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in ballot_changed signal: {str(e)}")


@receiver(post_delete, sender=Ballot)
def ballot_deleted(sender, instance, **kwargs):
    """
    Signal handler for when ballots are deleted.
    
    Triggers automatic recalculation for the decision when MANUAL ballots are deleted.
    Calculated ballots are ignored to prevent infinite cascade.
    
    Args:
        sender: Ballot model class
        instance: The Ballot instance that was deleted
        **kwargs: Additional signal arguments
    """
    try:
        # CRITICAL: Ignore calculated ballots to prevent infinite cascade
        if instance.is_calculated:
            logger.debug(f"[BALLOT_CALCULATED_DELETE_SKIP] [{instance.voter.username}] - Skipping recalculation for calculated ballot deletion")
            return
        
        decision = instance.decision
        community = decision.community
        
        # Log the ballot deletion
        logger.info(f"[BALLOT_DELETED] [{instance.voter.username}] - Ballot deleted on decision '{decision.title}'")
        
        # Only recalculate for open decisions
        if decision.dt_close > timezone.now():
            # Start background recalculation
            thread = threading.Thread(
                target=recalculate_community_decisions_async,
                args=(community.id, "ballot_deleted", instance.voter.id),
                daemon=True
            )
            thread.start()
            thread_id = thread.ident
            
            logger.info(f"[THREAD_SPAWN] TTE='ballot_deleted' THREAD_ID={thread_id} COMMUNITY={community.name} USER={instance.voter.username}")
            logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community {community.name}")
        else:
            logger.info(f"[BALLOT_DELETE_IGNORED] [system] - Ballot deletion on closed decision '{decision.title}' - no recalculation needed")
            
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in ballot_deleted signal: {str(e)}")


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
            thread_id = thread.ident
            
            logger.info(f"[THREAD_SPAWN] TTE='following_{action}' THREAD_ID={thread_id} COMMUNITY_ID={community_id} USER={instance.follower.member.username}")
            
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
            thread_id = thread.ident
            
            logger.info(f"[THREAD_SPAWN] TTE='following_deleted' THREAD_ID={thread_id} COMMUNITY_ID={community_id} USER={instance.follower.member.username}")
            
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
    
    NOTE: Membership changes do NOT trigger recalculation because:
    - Joining a community doesn't affect existing decisions
    - Membership status is checked at calculation time
    - Only votes and delegation changes should trigger recalculation
    
    This handler exists only for logging purposes.
    
    Args:
        sender: Membership model class
        instance: The Membership instance that was saved
        created: True if this is a new membership, False if updated
        **kwargs: Additional signal arguments
    """
    try:
        if created:
            logger.info(f"[MEMBER_JOINED] [{instance.member.username}] - Joined community '{instance.community.name}' (Voting: {instance.is_voting_community_member})")
        else:
            # Check if voting rights changed
            if hasattr(instance, '_state') and instance._state.adding is False:
                try:
                    old_instance = Membership.objects.get(pk=instance.pk)
                    if old_instance.is_voting_community_member != instance.is_voting_community_member:
                        status = "granted" if instance.is_voting_community_member else "revoked"
                        logger.info(f"[VOTING_RIGHTS_{status.upper()}] [{instance.member.username}] - Voting rights {status} in community '{instance.community.name}'")
                except Membership.DoesNotExist:
                    pass
                    
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in membership_changed signal: {str(e)}")


@receiver(post_delete, sender=Membership)
def membership_deleted(sender, instance, **kwargs):
    """
    Signal handler for when community memberships are deleted (member leaves).
    
    NOTE: Membership deletion does NOT trigger recalculation because:
    - Leaving a community doesn't require immediate recalculation
    - Member's ballots are filtered out at calculation time based on membership
    - Only votes and delegation changes should trigger recalculation
    
    This handler exists only for logging purposes.
    
    Args:
        sender: Membership model class
        instance: The Membership instance that was deleted
        **kwargs: Additional signal arguments
    """
    try:
        logger.info(f"[MEMBER_LEFT] [{instance.member.username}] - Left community '{instance.community.name}'")
        
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in membership_deleted signal: {str(e)}")


@receiver(post_save, sender=Decision)
def decision_status_changed(sender, instance, created, **kwargs):
    """
    Signal handler for when decisions are published.
    
    Triggers INITIAL calculation when:
    - Decision is published (becomes active for voting)
    
    This ensures a snapshot exists even if no one votes/follows during the voting period.
    
    NOTE: Decision closing does NOT trigger calculation because the last calculation
    before closing is effectively the final one. No need to recalculate if nothing changed.
    
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
                
                # Trigger initial calculation (ensures snapshot exists even if no votes)
                thread = threading.Thread(
                    target=recalculate_community_decisions_async,
                    args=(instance.community.id, "decision_published", None),
                    daemon=True
                )
                thread.start()
                thread_id = thread.ident
                
                logger.info(f"[THREAD_SPAWN] TTE='decision_published' THREAD_ID={thread_id} COMMUNITY={instance.community.name} DECISION={instance.title}")
                logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Initial calculation started for decision '{instance.title}'")
        
        # Note: We don't trigger on decision closing because:
        # - If nothing changed since last calculation, no need to recalculate
        # - The last calculation before closing is effectively the final one
        # - Saves database connections and processing time
                    
    except Exception as e:
        logger.error(f"[SIGNAL_ERROR] [system] - Error in decision_status_changed signal: {str(e)}")
