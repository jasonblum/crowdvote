"""
Management command to regenerate delegation tree data for debugging.

This command will delete existing DecisionSnapshots and regenerate them
with the fixed delegation tree data structure.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from democracy.models import Decision, DecisionSnapshot
from democracy.services import StageBallots
from collections import Counter


class Command(BaseCommand):
    help = 'Regenerate delegation tree data for all decisions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--decision-id',
            type=str,
            help='Regenerate only for specific decision ID',
        )

    def handle(self, *args, **options):
        decision_id = options.get('decision_id')
        
        if decision_id:
            decisions = Decision.objects.filter(id=decision_id)
            if not decisions.exists():
                self.stdout.write(
                    self.style.ERROR(f'Decision with ID {decision_id} not found')
                )
                return
        else:
            decisions = Decision.objects.all()

        for decision in decisions:
            self.stdout.write(f'Processing decision: {decision.title}')
            
            # Delete existing snapshots
            existing_snapshots = DecisionSnapshot.objects.filter(decision=decision)
            if existing_snapshots.exists():
                count = existing_snapshots.count()
                existing_snapshots.delete()
                self.stdout.write(f'  Deleted {count} existing snapshots')
            
            # Generate new delegation tree data
            stage_ballots_service = StageBallots()
            
            # Reset delegation tree data for this decision
            stage_ballots_service.delegation_tree_data = {
                'nodes': [],
                'edges': [],
                'inheritance_chains': []
            }
            
            # Process all community members to build delegation tree
            community = decision.community
            self.stdout.write(f'  Processing {community.memberships.count()} members...')
            
            for membership in community.memberships.all():
                stage_ballots_service.get_or_calculate_ballot(
                    decision=decision, voter=membership.member
                )
            
            # Get the delegation tree data
            delegation_tree_data = stage_ballots_service.delegation_tree_data.copy()
            
            # Calculate basic stats
            total_ballots = decision.ballots.count()
            manual_ballots = decision.ballots.filter(is_calculated=False).count()
            calculated_ballots = decision.ballots.filter(is_calculated=True).count()
            voting_members = community.get_voting_members().count()
            
            # Get tags used
            tags_used = []
            for ballot in decision.ballots.exclude(tags=''):
                if ballot.tags:
                    ballot_tags = [tag.strip().lower() for tag in ballot.tags.split(',')]
                    tags_used.extend(ballot_tags)
            
            # Count tag frequency
            tag_frequency = Counter(tags_used)
            
            # Create comprehensive snapshot data
            snapshot_data = {
                "metadata": {
                    "calculation_timestamp": timezone.now().isoformat(),
                    "system_version": "1.0.1-debug",
                    "decision_status": "active" if decision.dt_close and decision.dt_close > timezone.now() else "closed"
                },
                "delegation_tree": delegation_tree_data,
                "tag_analysis": {
                    "tag_frequency": dict(tag_frequency.most_common(10)),
                    "total_unique_tags": len(tag_frequency)
                },
                "vote_tally": {
                    "direct_votes": manual_ballots,
                    "calculated_votes": calculated_ballots
                }
            }
            
            # Create new snapshot
            snapshot = DecisionSnapshot.objects.create(
                decision=decision,
                snapshot_data=snapshot_data,
                total_eligible_voters=voting_members,
                total_votes_cast=manual_ballots,
                total_calculated_votes=calculated_ballots,
                tags_used=list(tag_frequency.keys()),
                is_final=(decision.dt_close and decision.dt_close <= timezone.now())
            )
            
            # Report results
            nodes_count = len(delegation_tree_data.get('nodes', []))
            edges_count = len(delegation_tree_data.get('edges', []))
            chains_count = len(delegation_tree_data.get('inheritance_chains', []))
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✓ Generated new snapshot: {nodes_count} nodes, {edges_count} edges, {chains_count} inheritance chains'
                )
            )
            
            # Show sample of vote data for debugging
            sample_node = None
            for node in delegation_tree_data.get('nodes', []):
                if node.get('votes'):
                    sample_node = node
                    break
            
            if sample_node:
                votes_info = []
                for choice_id, vote_data in sample_node['votes'].items():
                    votes_info.append(f"{vote_data.get('choice_name', choice_id)}: {vote_data.get('stars')} stars")
                
                self.stdout.write(
                    f'  Sample vote data from {sample_node.get("username", "Anonymous")}: {", ".join(votes_info)}'
                )
            else:
                self.stdout.write('  No vote data found in any nodes')

        self.stdout.write(
            self.style.SUCCESS(f'Successfully processed {decisions.count()} decisions')
        )
