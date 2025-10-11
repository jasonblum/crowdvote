"""
Stage Snapshot and Tally Ballots - CrowdVote's Democratic Process

MANUAL TESTING ONLY: In production, signals automatically trigger ballot
calculation, snapshot creation, and tallying when users vote, follow, or 
change memberships. This command is for:
- Manual testing and debugging
- One-time recalculation after data fixes
- Verifying the complete calculation pipeline

This management command executes the two-phase democratic process:

STAGE PHASE:
1. Collect manually-cast ballots from direct voters
2. Calculate inherited ballots through delegation (tag-based following)
3. Prepare the complete ballot set for tallying

TALLY PHASE:
1. Score all ballots (the 'S' in STAR voting)
2. Run automatic runoff between top 2 choices (the 'AR' in STAR voting)
3. Determine the winner with complete transparency

Run with: python manage.py stage_snapshot_and_tally_ballots
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from democracy.services import StageBallots, Tally
from democracy.models import Decision, Community


class Command(BaseCommand):
    help = '[MANUAL TESTING] Stage ballots and tally using STAR voting. In production, signals handle this automatically.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--show-delegation', 
            action='store_true',
            help='Show detailed delegation tree (can be very long)'
        )
        parser.add_argument(
            '--decision',
            type=str,
            help='Focus on specific decision title (partial match)'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🗳️ ' + '='*70)
        )
        self.stdout.write(
            self.style.SUCCESS('   CROWDVOTE: DEMOCRACY BETWEEN THE PEOPLE')
        )
        self.stdout.write(
            self.style.SUCCESS('   Free-Market Representation in Action')
        )
        self.stdout.write(
            self.style.SUCCESS('='*72)
        )
        self.stdout.write('')

        # Show system overview
        self.show_system_overview()

        # Check if Alphabet Delegation Test community exists and highlight it
        alphabet_community = Community.objects.filter(name="Alphabet Delegation Test").first()
        if alphabet_community:
            self.stdout.write(
                self.style.SUCCESS('📊 ALPHABET DELEGATION TEST COMMUNITY DETECTED')
            )
            self.stdout.write(
                '   This systematic test community validates complex delegation inheritance'
            )
            self.stdout.write(
                '   with 12 users (AAAAAAAAAAA-LLLLLLLLLLL) and realistic cross-level following.'
            )
            self.stdout.write('')

        # Get open decisions
        decisions = Decision.objects.filter(dt_close__gt=timezone.now())
        
        if options['decision']:
            decisions = decisions.filter(title__icontains=options['decision'])
            
        if not decisions:
            self.stdout.write(
                self.style.WARNING('No open decisions found for voting.')
            )
            return

        # Process each decision
        for decision in decisions:
            self.stdout.write('')
            self.stdout.write('='*80)
            self.stdout.write(
                self.style.HTTP_INFO(f'📋 DECISION: {decision.title}')
            )
            self.stdout.write(f'Community: {decision.community.name}')
            self.stdout.write(f'Closes: {decision.dt_close.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write('')
            
            # Show choices
            choices = list(decision.choices.all())
            self.stdout.write('Choices:')
            for i, choice in enumerate(choices, 1):
                self.stdout.write(f'  {i}. {choice.title}')
            self.stdout.write('')

            # Run ballot calculation (delegation)
            self.stdout.write('🔄 RUNNING BALLOT CALCULATION (Tag-Based Delegation)...')
            stage_service = StageBallots()
            stage_service.execute({})
            
            if options['show_delegation']:
                self.show_delegation_sample(decision)
            else:
                self.show_delegation_summary(decision)

            # Run STAR voting tally
            self.stdout.write('')
            self.stdout.write('🎯 RUNNING STAR VOTING TALLY...')
            tally_service = Tally()
            tally_service.execute({})
            
            self.show_star_results(decision)

        self.stdout.write('')
        self.stdout.write('='*80)
        self.stdout.write(
            self.style.SUCCESS('✅ STAGING AND TALLYING COMPLETE!')
        )
        self.stdout.write('')
        self.stdout.write('Your vision of democracy happening between the people is working!')
        self.stdout.write('🌟 Votes flow through trust networks based on expertise')
        self.stdout.write('🔍 Complete transparency - every decision is auditable') 
        self.stdout.write('🗽 Free-market representation instead of K Street lobbying')

    def show_system_overview(self):
        """Show high-level system statistics."""
        from security.models import CustomUser
        from democracy.models import Following, Ballot
        
        total_users = CustomUser.objects.count()
        total_communities = Community.objects.count()
        total_followings = Following.objects.count()
        tag_followings = Following.objects.exclude(tags='').count()
        total_ballots = Ballot.objects.count()
        calculated_ballots = Ballot.objects.filter(is_calculated=True).count()
        
        self.stdout.write('📊 SYSTEM OVERVIEW:')
        self.stdout.write(f'   Communities: {total_communities}')
        self.stdout.write(f'   Users: {total_users}')
        self.stdout.write(f'   Following relationships: {total_followings}')
        self.stdout.write(f'     - Tag-specific: {tag_followings}')
        self.stdout.write(f'     - General: {total_followings - tag_followings}')
        self.stdout.write(f'   Ballots cast: {total_ballots}')
        self.stdout.write(f'     - Manual votes: {total_ballots - calculated_ballots}')
        self.stdout.write(f'     - Calculated (delegated): {calculated_ballots}')

    def show_delegation_summary(self, decision):
        """Show summary of delegation activity."""
        total_ballots = decision.ballots.count()
        manual_ballots = decision.ballots.filter(is_calculated=False).count()
        calculated_ballots = decision.ballots.filter(is_calculated=True).count()
        
        # Tag analysis
        tag_counts = {}
        for ballot in decision.ballots.all():
            if ballot.tags:
                for tag in ballot.tags.split(','):
                    tag = tag.strip()
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        self.stdout.write('🌳 DELEGATION SUMMARY:')
        self.stdout.write(f'   Total ballots: {total_ballots}')
        self.stdout.write(f'   Manual votes: {manual_ballots}')
        self.stdout.write(f'   Calculated (inherited): {calculated_ballots}')
        
        if tag_counts:
            self.stdout.write('   Tag influence:')
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_ballots) * 100
                self.stdout.write(f'     - "{tag}": {count} ballots ({percentage:.1f}%)')
        
        self.stdout.write(f'   Use --show-delegation to see detailed delegation tree')

    def show_delegation_sample(self, decision):
        """Show sample delegation tree (first few users)."""
        self.stdout.write('🌳 DELEGATION TREE SAMPLE (first 3 calculations):')
        self.stdout.write('')
        
        # This would show delegation tree if it was saved to database
        # For now, just show that delegation happened
        calculated_ballots = decision.ballots.filter(is_calculated=True)[:3]
        
        for ballot in calculated_ballots:
            followings = ballot.voter.followings.all()
            if followings:
                self.stdout.write(f'  {ballot.voter.username}:')
                for following in followings[:2]:  # Show first 2 followings
                    tags_display = following.tags if following.tags else '(all issues)'
                    self.stdout.write(f'    ↳ follows {following.followee.username} on: {tags_display}')
                if ballot.tags:
                    self.stdout.write(f'    → inherited tags: {ballot.tags}')
                self.stdout.write('')

    def show_star_results(self, decision):
        """Show STAR voting results for a decision."""
        # Get voting member ballots
        voting_ballots = decision.ballots.filter(
            voter__memberships__community=decision.community,
            voter__memberships__is_voting_community_member=True
        )
        
        if not voting_ballots:
            self.stdout.write('No voting member ballots found.')
            return

        # Calculate STAR results using Plan #7 implementation
        from democracy.star_voting import STARVotingTally
        from democracy.exceptions import UnresolvedTieError
        from decimal import Decimal
        
        # Convert ballots to format expected by STARVotingTally
        ballot_list = []
        choice_id_to_obj = {}
        
        for ballot in voting_ballots:
            ballot_dict = {}
            for vote in ballot.votes.select_related('choice'):
                ballot_dict[str(vote.choice.id)] = vote.stars
                choice_id_to_obj[str(vote.choice.id)] = vote.choice
            
            if ballot_dict:
                ballot_list.append(ballot_dict)
        
        try:
            star_tally = STARVotingTally()
            result = star_tally.run(ballot_list)
            
            # Display score phase
            self.stdout.write('⭐ SCORE PHASE (S in STAR):')
            for i, (choice_id, score) in enumerate(sorted(result['scores'].items(), key=lambda x: x[1], reverse=True), 1):
                choice = choice_id_to_obj.get(choice_id)
                if choice:
                    self.stdout.write(f'   {i}. {choice.title}: {score} avg stars')
            
            # Display runoff
            self.stdout.write('')
            self.stdout.write('🏃 AUTOMATIC RUNOFF (AR in STAR):')
            
            if result.get('runoff_details'):
                self.stdout.write('   Top 2 choices in head-to-head runoff:')
                runoff = result['runoff_details']
                for finalist_id in runoff['finalists']:
                    choice = choice_id_to_obj.get(finalist_id)
                    if choice:
                        prefs = runoff['choice_a_preferences'] if runoff['finalists'][0] == finalist_id else runoff['choice_b_preferences']
                        self.stdout.write(f'     {choice.title}: {prefs} preferences')
                
                if runoff['ties'] > 0:
                    self.stdout.write(f'     Tied preferences: {runoff["ties"]}')
            
            # Display winner
            self.stdout.write('')
            self.stdout.write('🏆 FINAL RESULT:')
            
            if result['winner']:
                winner_choice = choice_id_to_obj.get(result['winner'])
                if winner_choice:
                    self.stdout.write(
                        self.style.SUCCESS(f'   WINNER: {winner_choice.title}')
                    )
                    
                    if result.get('runoff_details'):
                        runoff = result['runoff_details']
                        winner_prefs = runoff['choice_a_preferences'] if runoff['finalists'][0] == result['winner'] else runoff['choice_b_preferences']
                        runner_prefs = runoff['choice_b_preferences'] if runoff['finalists'][0] == result['winner'] else runoff['choice_a_preferences']
                        margin = abs(winner_prefs - runner_prefs)
                        margin_pct = (margin / len(ballot_list)) * 100 if ballot_list else 0
                        self.stdout.write(f'   Margin: {margin} votes ({margin_pct:.1f}%)')
                        
                        runner_up_id = runoff['finalists'][1] if runoff['finalists'][0] == result['winner'] else runoff['finalists'][0]
                        runner_up_choice = choice_id_to_obj.get(runner_up_id)
                        if runner_up_choice:
                            self.stdout.write(f'   Runner-up: {runner_up_choice.title}')
            else:
                self.stdout.write('   No winner determined')
            
        except UnresolvedTieError as e:
            self.stdout.write('')
            self.stdout.write('⚠️ UNRESOLVED TIE:')
            self.stdout.write('   Tie could not be resolved by automatic tiebreakers.')
            tied_names = [choice_id_to_obj.get(c).title if choice_id_to_obj.get(c) else c for c in e.tied_candidates]
            self.stdout.write(f'   Tied candidates: {", ".join(tied_names)}')
        
        except ValueError as e:
            self.stdout.write('')
            self.stdout.write(f'❌ TALLY ERROR: {str(e)}')
