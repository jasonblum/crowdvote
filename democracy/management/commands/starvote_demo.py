"""
STAR Voting Demo - Educational demonstration of the starvote library.

This management command demonstrates STAR Voting (Score Then Automatic Runoff)
using the starvote library by Larry Hastings. Each run generates random votes
from the same voters for the same sandwich choices, allowing you to see how
different vote patterns lead to different outcomes.

STAR Voting Process:
1. SCORE PHASE: Sum all stars for each candidate. Top 2 advance.
2. AUTOMATIC RUNOFF: Count which of the top 2 each voter preferred.
3. TIEBREAKER: If tied in runoff, higher score from phase 1 wins.
4. If still tied: Unbreakable tie.

Run with: python manage.py starvote_demo
"""

import random
from django.core.management.base import BaseCommand

try:
    import starvote
except ImportError:
    starvote = None


class Command(BaseCommand):
    help = 'Demo STAR Voting with random sandwich votes using the starvote library'

    # Fixed voters - same every time
    VOTERS = [
        "Alice", "Bob", "Carol", "David", "Emma"
    ]
    
    # Fixed sandwich choices - same every time
    SANDWICHES = [
        "Ham & Cheese",
        "Turkey Club", 
        "Grilled Cheese",
        "BLT",
        "Reuben"
    ]

    def handle(self, *args, **options):
        if starvote is None:
            self.stdout.write(
                self.style.ERROR(
                    '❌ The starvote library is not installed.\n'
                    'Install it with: pip install starvote'
                )
            )
            return

        self.print_header()
        
        # Generate random ballots
        ballots = self.generate_random_ballots()
        
        # Show all ballots
        self.print_ballots(ballots)
        
        # Calculate and display results manually
        self.calculate_and_display_results(ballots)
        
        # Verify with starvote library (it includes STAR Official Tiebreaker Protocol automatically)
        self.stdout.write('')
        self.stdout.write('🔍 Verification: Running starvote library...')
        
        try:
            # Create a simple tiebreaker that raises UnbreakableTieError
            def raise_on_tie(tie):
                raise starvote.UnbreakableTieError(tie)
            
            winners = starvote.election(
                method=starvote.STAR_Voting,
                ballots=ballots,
                tiebreaker=raise_on_tie
            )
            self.stdout.write(f'   ✅ starvote library confirms: {winners[0]} wins!')
            
        except starvote.UnbreakableTieError as e:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('   ⚠️  starvote library also detected an unbreakable tie'))

    def print_header(self):
        """Print a nice header for the demo."""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('🥪 ' + '='*70))
        self.stdout.write(self.style.SUCCESS('   STAR VOTING DEMO: The Great Sandwich Election'))
        self.stdout.write(self.style.SUCCESS('   Using the starvote library by Larry Hastings'))
        self.stdout.write(self.style.SUCCESS('='*72))
        self.stdout.write('')
        self.stdout.write('Five hungry voters will score five delicious sandwiches (0-5 stars).')
        self.stdout.write('Watch how STAR Voting determines the winner in two phases!')
        self.stdout.write('')

    def generate_random_ballots(self):
        """Generate random ballots with 0-5 stars for each sandwich."""
        ballots = []
        
        for voter in self.VOTERS:
            ballot = {}
            for sandwich in self.SANDWICHES:
                ballot[sandwich] = random.randint(0, 5)
            ballots.append(ballot)
        
        return ballots

    def print_ballots(self, ballots):
        """Print all ballots in an easy-to-read format."""
        self.stdout.write('📊 ALL BALLOTS CAST:')
        self.stdout.write('')
        
        # Print header row
        header = "Voter".ljust(12)
        for sandwich in self.SANDWICHES:
            # Use first letter of each word for compact display
            abbrev = ''.join(word[0] for word in sandwich.split())
            header += f" {abbrev:>3}"
        self.stdout.write(self.style.HTTP_INFO(header))
        self.stdout.write('-' * 60)
        
        # Print each ballot
        for i, ballot in enumerate(ballots):
            voter = self.VOTERS[i].ljust(12)
            row = voter
            for sandwich in self.SANDWICHES:
                stars = ballot[sandwich]
                # Use emoji stars for visual appeal
                star_display = '★' * stars + '☆' * (5 - stars)
                row += f" {stars:>3}"
            self.stdout.write(row)
        
        self.stdout.write('')

    def calculate_and_display_results(self, ballots):
        """Calculate and display STAR voting results step by step."""
        
        # PHASE 1: Calculate total scores
        self.stdout.write('')
        self.stdout.write('='*72)
        self.stdout.write(self.style.HTTP_INFO('⭐ PHASE 1: SCORE PHASE (the "S" in STAR)'))
        self.stdout.write('='*72)
        self.stdout.write('')
        self.stdout.write('Tallying stars for each sandwich...')
        self.stdout.write('')
        
        # Calculate total scores
        scores = {sandwich: 0 for sandwich in self.SANDWICHES}
        for ballot in ballots:
            for sandwich, stars in ballot.items():
                scores[sandwich] += stars
        
        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        max_score = max(scores.values()) if scores else 0
        
        # Display scores
        for i, (sandwich, score) in enumerate(sorted_scores, 1):
            bar_length = int((score / max_score) * 30) if max_score > 0 else 0
            bar = '█' * bar_length
            
            if i <= 2:
                self.stdout.write(
                    self.style.SUCCESS(f'  {i}. {sandwich:20s} {score:5d} stars {bar} ← TOP 2')
                )
            else:
                self.stdout.write(f'  {i}. {sandwich:20s} {score:5d} stars {bar}')
        
        # Get top 2 finalists
        finalist_1, score_1 = sorted_scores[0]
        finalist_2, score_2 = sorted_scores[1]
        
        self.stdout.write('')
        self.stdout.write(f'Top 2 sandwiches advance to runoff: {finalist_1} vs {finalist_2}')
        
        # PHASE 2: Automatic Runoff
        self.stdout.write('')
        self.stdout.write('='*72)
        self.stdout.write(self.style.HTTP_INFO('🏃 PHASE 2: AUTOMATIC RUNOFF (the "AR" in STAR)'))
        self.stdout.write('='*72)
        self.stdout.write('')
        self.stdout.write(f'Head-to-head matchup: {finalist_1} vs {finalist_2}')
        self.stdout.write('Counting which sandwich each voter preferred...')
        self.stdout.write('')
        
        # Count preferences in runoff
        pref_1 = 0
        pref_2 = 0
        ties = 0
        
        for ballot in ballots:
            stars_1 = ballot[finalist_1]
            stars_2 = ballot[finalist_2]
            
            if stars_1 > stars_2:
                pref_1 += 1
            elif stars_2 > stars_1:
                pref_2 += 1
            else:
                ties += 1
        
        self.stdout.write(f'  {finalist_1:20s} {pref_1:3d} preferences')
        self.stdout.write(f'  {finalist_2:20s} {pref_2:3d} preferences')
        
        if ties > 0:
            self.stdout.write(f'  {"(Equal scores)":20s} {ties:3d} ballots')
        
        # Determine winner
        self.stdout.write('')
        self.stdout.write('='*72)
        self.stdout.write(self.style.SUCCESS('🏆 FINAL RESULT'))
        self.stdout.write('='*72)
        self.stdout.write('')
        
        # Apply STAR Voting Official Tiebreaker Protocol
        if pref_1 > pref_2:
            winner = finalist_1
            margin = pref_1 - pref_2
            tiebreaker_used = False
        elif pref_2 > pref_1:
            winner = finalist_2
            margin = pref_2 - pref_1
            tiebreaker_used = False
        else:
            # Tie in runoff - use Phase 1 scores as tiebreaker
            if score_1 > score_2:
                winner = finalist_1
            elif score_2 > score_1:
                winner = finalist_2
            else:
                # Unbreakable tie!
                self.stdout.write(self.style.WARNING('   🤝 UNBREAKABLE TIE!'))
                self.stdout.write(f'   Both {finalist_1} and {finalist_2} are perfectly tied.')
                return
            
            margin = 0
            tiebreaker_used = True
        
        self.stdout.write(
            self.style.SUCCESS(f'   🥇 WINNER: {winner}')
        )
        
        if not tiebreaker_used and margin > 0:
            self.stdout.write(f'   Margin of victory: {margin} preference(s)')
        elif tiebreaker_used:
            self.stdout.write('   Tie in runoff! Winner determined by higher score in Phase 1.')
            self.stdout.write('   (STAR Voting Official Tiebreaker Protocol applied)')
            self.stdout.write(f'   {finalist_1} had {score_1} stars, {finalist_2} had {score_2} stars in Phase 1.')
        
        self.stdout.write('')
        self.stdout.write('='*72)
        self.stdout.write('')
        self.stdout.write('💡 TIP: Run this command again to see different voting patterns!')
        self.stdout.write('   Same voters, same sandwiches, but different preferences each time.')
        self.stdout.write('')

