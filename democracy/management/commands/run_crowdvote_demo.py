"""
CrowdVote Democratic Process Demo Command

This command demonstrates the complete CrowdVote system:
1. Tag-based delegative democracy
2. Vote inheritance through trust networks  
3. STAR voting (Score Then Automatic Runoff)
4. Complete transparency and auditability

Run with: python manage.py run_crowdvote_demo
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from democracy.services import StageBallots, Tally
from democracy.models import Decision, Community


class Command(BaseCommand):
    help = 'Demonstrate the complete CrowdVote democratic process'

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
            self.style.SUCCESS('✅ CROWDVOTE DEMO COMPLETE!')
        )
        self.stdout.write('')
        self.stdout.write('Your vision of democracy happening between the people is working!')
        self.stdout.write('🌟 Votes flow through trust networks based on expertise')
        self.stdout.write('🔍 Complete transparency - every decision is auditable') 
        self.stdout.write('🗽 Free-market representation instead of K Street lobbying')

    def show_system_overview(self):
        """Show high-level system statistics."""
        from accounts.models import CustomUser, Following
        from democracy.models import Ballot
        
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

        # Calculate STAR results
        stage_service = StageBallots()
        scores = stage_service.score(voting_ballots)
        runoff_results = stage_service.automatic_runoff(voting_ballots)
        
        self.stdout.write('⭐ SCORE PHASE (S in STAR):')
        for i, (choice, data) in enumerate(scores.items(), 1):
            self.stdout.write(f'   {i}. {choice.title}: {data["score"]:.3f} avg stars')
        
        self.stdout.write('')
        self.stdout.write('🏃 AUTOMATIC RUNOFF (AR in STAR):')
        
        if runoff_results['runoff_needed']:
            self.stdout.write('   Top 2 choices in head-to-head runoff:')
            for choice_title, details in runoff_results['runoff_details'].items():
                self.stdout.write(
                    f'     {choice_title}: {details["runoff_preferences"]} preferences'
                )
            
            if runoff_results['ties'] > 0:
                self.stdout.write(f'     Tied preferences: {runoff_results["ties"]}')
        
        self.stdout.write('')
        self.stdout.write('🏆 FINAL RESULT:')
        
        if runoff_results['winner']:
            margin_pct = (runoff_results['margin'] / runoff_results['total_ballots']) * 100
            self.stdout.write(
                self.style.SUCCESS(f'   WINNER: {runoff_results["winner"].title}')
            )
            self.stdout.write(f'   Margin: {runoff_results["margin"]} votes ({margin_pct:.1f}%)')
            
            if runoff_results['runner_up']:
                self.stdout.write(f'   Runner-up: {runoff_results["runner_up"].title}')
        else:
            self.stdout.write('   No winner determined')
