"""
Management command to diagnose and fix stuck decision snapshots.

Stuck snapshots occur when calculations fail silently or threads crash
without updating the snapshot status. This leaves snapshots in processing
states ('creating', 'staging', 'tallying') indefinitely, causing the
global spinner to spin forever.

This command:
1. Identifies snapshots stuck in processing states beyond timeout threshold
2. Reports details about each stuck snapshot (decision, age, status)
3. Optionally marks stuck snapshots as 'failed_timeout' to stop spinner

Usage:
    # Diagnose only (no changes):
    python manage.py check_stuck_snapshots
    
    # Mark stuck snapshots as failed:
    python manage.py check_stuck_snapshots --fix
    
    # Use custom timeout (default is 10 minutes):
    python manage.py check_stuck_snapshots --timeout 5
    
    # Combine options:
    python manage.py check_stuck_snapshots --fix --timeout 15

This command should be run:
- When the global spinner won't stop spinning
- After system crashes or unexpected shutdowns
- As part of routine maintenance (e.g., daily cron job)
- Before deploying to verify clean state

Example output:
    🔍 Checking for stuck snapshots (timeout: 10 minutes)...
    
    Found 2 stuck snapshots:
      ⚠️  Decision: "Banana Budget Allocation"
          Status: staging
          Age: 45.3 minutes
          Community: Minion Collective
      
      ⚠️  Decision: "World Domination Schedule"
          Status: tallying  
          Age: 2.1 hours
          Community: Minion Collective
    
    Run with --fix to mark these as failed.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from democracy.models import DecisionSnapshot


class Command(BaseCommand):
    help = 'Check for and optionally fix stuck decision snapshots'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Mark stuck snapshots as failed (default is diagnose-only)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='Minutes before considering snapshot stuck (default: 10)',
        )

    def handle(self, *args, **options):
        fix_mode = options['fix']
        timeout_minutes = options['timeout']
        
        # Header
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('  🔍 STUCK SNAPSHOT CHECKER'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')
        
        # Show configuration
        mode_display = "FIX MODE" if fix_mode else "DIAGNOSE ONLY"
        self.stdout.write(f'Mode: {self.style.WARNING(mode_display)}')
        self.stdout.write(f'Timeout threshold: {timeout_minutes} minutes')
        self.stdout.write('')
        
        # Calculate cutoff time
        cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)
        
        # Find stuck snapshots
        stuck_snapshots = DecisionSnapshot.objects.filter(
            calculation_status__in=['creating', 'staging', 'tallying'],
            created_at__lt=cutoff_time
        ).select_related('decision__community').order_by('created_at')
        
        count = stuck_snapshots.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No stuck snapshots found!'))
            self.stdout.write('')
            self.stdout.write('All snapshots are either:')
            self.stdout.write('  • Completed successfully')
            self.stdout.write('  • Still processing (within timeout window)')
            self.stdout.write('  • Already marked as failed')
            self.stdout.write('')
            return
        
        # Report findings
        self.stdout.write(self.style.WARNING(f'Found {count} stuck snapshot(s):'))
        self.stdout.write('')
        
        for snapshot in stuck_snapshots:
            age_minutes = (timezone.now() - snapshot.created_at).total_seconds() / 60
            age_display = self._format_age(age_minutes)
            
            self.stdout.write(self.style.WARNING('  ⚠️  Stuck Snapshot:'))
            self.stdout.write(f'      Decision: "{snapshot.decision.title}"')
            self.stdout.write(f'      Community: {snapshot.decision.community.name}')
            self.stdout.write(f'      Status: {snapshot.calculation_status}')
            self.stdout.write(f'      Age: {age_display}')
            self.stdout.write(f'      Created: {snapshot.created_at.strftime("%Y-%m-%d %H:%M:%S")}')
            self.stdout.write(f'      Snapshot ID: {snapshot.id}')
            self.stdout.write('')
        
        # Take action based on mode
        if fix_mode:
            self.stdout.write(self.style.WARNING('🔧 Marking stuck snapshots as failed...'))
            self.stdout.write('')
            
            # Use the model's classmethod to mark them as failed
            fixed_count, decision_titles = DecisionSnapshot.mark_stuck_snapshots_as_failed(
                timeout_minutes=timeout_minutes
            )
            
            self.stdout.write(self.style.SUCCESS(f'✅ Successfully marked {fixed_count} snapshot(s) as failed_timeout'))
            self.stdout.write('')
            self.stdout.write('These snapshots will now show as "Calculation Timed Out" in the UI.')
            self.stdout.write('The global spinner should stop spinning for these decisions.')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Next steps:'))
            self.stdout.write('  1. Check the global spinner - it should now be gray/static')
            self.stdout.write('  2. Review logs to understand why calculations got stuck')
            self.stdout.write('  3. Consider re-running calculations manually if needed')
            self.stdout.write('')
            
        else:
            # Diagnose-only mode
            self.stdout.write(self.style.WARNING('ℹ️  DIAGNOSE-ONLY MODE'))
            self.stdout.write('')
            self.stdout.write('No changes made to the database.')
            self.stdout.write('')
            self.stdout.write('To fix these stuck snapshots, run:')
            self.stdout.write(self.style.SUCCESS(f'  python manage.py check_stuck_snapshots --fix'))
            self.stdout.write('')
            self.stdout.write('Or with custom timeout:')
            self.stdout.write(self.style.SUCCESS(f'  python manage.py check_stuck_snapshots --fix --timeout {timeout_minutes}'))
            self.stdout.write('')
        
        # Show system impact
        self.stdout.write('='*70)
        self.stdout.write(self.style.SUCCESS('System Impact Summary:'))
        self.stdout.write('='*70)
        self.stdout.write(f'Stuck snapshots: {count}')
        self.stdout.write(f'Affected decisions: {len(set(s.decision.id for s in stuck_snapshots))}')
        self.stdout.write(f'Affected communities: {len(set(s.decision.community.id for s in stuck_snapshots))}')
        self.stdout.write('')
        
        if fix_mode:
            self.stdout.write(self.style.SUCCESS('✅ All stuck snapshots have been resolved!'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Run with --fix to resolve these issues.'))
        self.stdout.write('')
    
    def _format_age(self, minutes):
        """Format age in human-readable format."""
        if minutes < 60:
            return f'{minutes:.1f} minutes'
        elif minutes < 1440:  # Less than 24 hours
            hours = minutes / 60
            return f'{hours:.1f} hours'
        else:
            days = minutes / 1440
            return f'{days:.1f} days'

