"""
STAR Voting implementation with Decimal support for CrowdVote.

This module implements the STAR (Score Then Automatic Runoff) voting algorithm
with native support for fractional star ratings using Python's Decimal type.

STAR Voting works in two phases:
1. Score Phase: Calculate average stars for each choice
2. Automatic Runoff: Head-to-head comparison of top 2 choices

References:
- https://www.starvoting.org/
- https://www.starvoting.org/ties (Official Tiebreaker Protocol)
"""

from decimal import Decimal, getcontext
from typing import Any, Dict, List, Tuple

from .exceptions import UnresolvedTieError


# Set Decimal precision for calculations
# 12 significant figures provides sufficient precision for complex delegation chains
# while avoiding excessive decimal expansion
getcontext().prec = 12


def quantize_stars(value: Decimal) -> Decimal:
    """
    Quantize a Decimal star rating to 8 decimal places.
    
    This ensures consistent precision for storage and comparison while
    maintaining sufficient accuracy for fairness even with deep delegation chains.
    
    Args:
        value: Decimal star rating to quantize
        
    Returns:
        Decimal quantized to 8 decimal places
        
    Example:
        >>> quantize_stars(Decimal('3.58372894573756383'))
        Decimal('3.58372895')
    """
    return value.quantize(Decimal('0.00000001'))


class STARVotingTally:
    """
    STAR Voting tally calculator with Decimal support.
    
    Implements the complete STAR (Score Then Automatic Runoff) voting algorithm
    including the Official Tiebreaker Protocol from starvoting.org.
    
    This implementation accepts both integer and Decimal star ratings (0-5 range),
    making it compatible with CrowdVote's delegation system which produces
    fractional ratings when averaging inherited votes.
    
    Input Format:
        ballots: List of dictionaries mapping choice identifiers to star ratings
        Example: [
            {'choice_a': Decimal('3.7'), 'choice_b': Decimal('4.0')},
            {'choice_a': Decimal('5'), 'choice_b': Decimal('2.5')},
        ]
    
    Output Format:
        Dictionary containing:
        - winner: Winning choice identifier (or None if unresolved tie)
        - tied_candidates: List of tied choices if UnresolvedTieError would be raised
        - scores: Dict mapping choices to average star ratings
        - runoff_details: Dict with finalist comparison details
        - tally_log: List of strings documenting the tally process
    
    Algorithm:
        Phase 1 (Score): Calculate average stars for each choice
        Phase 2 (Automatic Runoff): Compare top 2 choices head-to-head
        Tiebreakers: Apply Official Tiebreaker Protocol if needed
    
    Example:
        >>> ballots = [
        ...     {'apple': Decimal('5'), 'banana': Decimal('3')},
        ...     {'apple': Decimal('4'), 'banana': Decimal('5')},
        ... ]
        >>> tally = STARVotingTally()
        >>> result = tally.run(ballots)
        >>> print(result['winner'])
        'apple'
    """
    
    def __init__(self):
        """Initialize the STAR voting tally calculator."""
        self.tally_log: List[str] = []
        
    def run(self, ballots: List[Dict[Any, Decimal]]) -> Dict[str, Any]:
        """
        Execute complete STAR voting tally.
        
        Args:
            ballots: List of ballot dictionaries mapping choices to Decimal star ratings
        
        Returns:
            Dictionary with winner, scores, runoff details, and tally log
            
        Raises:
            UnresolvedTieError: If tie cannot be resolved by automatic protocol
            ValueError: If ballots are invalid or empty
        """
        self.tally_log = []
        
        # Validate input
        if not ballots:
            raise ValueError("Cannot tally election with no ballots")
        
        # Get all unique choices across all ballots
        all_choices = set()
        for ballot in ballots:
            all_choices.update(ballot.keys())
        
        if len(all_choices) == 0:
            raise ValueError("Cannot tally election with no choices")
        
        self.tally_log.append(f"STAR Voting Tally")
        self.tally_log.append(f"Total ballots: {len(ballots)}")
        self.tally_log.append(f"Total choices: {len(all_choices)}")
        self.tally_log.append("")
        
        # Phase 1: Score Phase
        scores = self._calculate_scores(ballots, all_choices)
        self.tally_log.append("=== PHASE 1: SCORE PHASE ===")
        for choice, avg_stars in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            self.tally_log.append(f"{choice}: {avg_stars} stars")
        self.tally_log.append("")
        
        # Handle single choice case (no runoff needed)
        if len(all_choices) == 1:
            winner = list(all_choices)[0]
            self.tally_log.append(f"Only one choice - Winner: {winner}")
            return {
                'winner': winner,
                'tied_candidates': [],
                'scores': scores,
                'runoff_details': None,
                'tally_log': self.tally_log,
            }
        
        # Get top 2 choices (with tiebreaking if needed)
        top_two = self._get_top_two_with_tiebreak(scores, ballots)
        
        self.tally_log.append("=== PHASE 2: AUTOMATIC RUNOFF ===")
        self.tally_log.append(f"Finalists: {top_two[0]} vs {top_two[1]}")
        self.tally_log.append("")
        
        # Phase 2: Automatic Runoff
        winner, runoff_details = self._run_automatic_runoff(top_two, ballots, scores)
        
        return {
            'winner': winner,
            'tied_candidates': [],
            'scores': scores,
            'runoff_details': runoff_details,
            'tally_log': self.tally_log,
        }
    
    def _calculate_scores(
        self,
        ballots: List[Dict[Any, Decimal]],
        all_choices: set
    ) -> Dict[Any, Decimal]:
        """
        Calculate average star ratings for all choices (Score Phase).
        
        Args:
            ballots: List of ballot dictionaries
            all_choices: Set of all choice identifiers
            
        Returns:
            Dictionary mapping choices to average Decimal star ratings
        """
        scores = {}
        
        for choice in all_choices:
            total_stars = Decimal('0')
            
            for ballot in ballots:
                # Treat missing choices as 0 stars
                stars = ballot.get(choice, Decimal('0'))
                total_stars += stars
            
            # Calculate average and quantize to 8 decimal places
            avg_stars = total_stars / Decimal(len(ballots))
            scores[choice] = quantize_stars(avg_stars)
        
        return scores
    
    def _get_top_two_with_tiebreak(
        self,
        scores: Dict[Any, Decimal],
        ballots: List[Dict[Any, Decimal]]
    ) -> Tuple[Any, Any]:
        """
        Get the top 2 highest scoring choices, applying Step 1 tiebreakers if needed.
        
        Official Tiebreaker Protocol Step 1:
        - If multiple choices tie for 1st or 2nd place in scoring round,
          break tie by head-to-head comparison
        - Eliminate the choice(s) that lose the most head-to-head matchups
        - Repeat if needed until we have exactly 2 finalists
        
        Args:
            scores: Dictionary mapping choices to average scores
            ballots: List of ballot dictionaries (for tiebreaking)
            
        Returns:
            Tuple of (first_place, second_place) choice identifiers
            
        Raises:
            UnresolvedTieError: If tie cannot be resolved (extremely rare in score phase)
        """
        # Sort choices by score (highest first)
        sorted_choices = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Check if there's a tie for 1st or 2nd place
        if len(sorted_choices) < 2:
            # Only one choice - already handled in run()
            return sorted_choices[0][0], sorted_choices[0][0]
        
        first_score = sorted_choices[0][1]
        second_score = sorted_choices[1][1]
        
        # Find all choices tied for 1st place
        tied_for_first = [c for c, s in sorted_choices if s == first_score]
        
        if len(tied_for_first) == 1:
            # No tie for 1st, check for tie for 2nd
            tied_for_second = [c for c, s in sorted_choices if s == second_score and c != tied_for_first[0]]
            
            if len(tied_for_second) <= 1:
                # No ties - simple case
                return sorted_choices[0][0], sorted_choices[1][0]
            else:
                # Tie for 2nd place - break it
                self.tally_log.append(f"Tie for 2nd place: {tied_for_second}")
                second_place = self._break_score_tie(tied_for_second, ballots)
                return tied_for_first[0], second_place
        
        else:
            # Multiple choices tied for 1st place
            self.tally_log.append(f"Tie for 1st place: {tied_for_first}")
            
            if len(tied_for_first) == 2:
                # Exactly 2 tied for first - they're our finalists
                return tied_for_first[0], tied_for_first[1]
            else:
                # More than 2 tied for first - need to eliminate some
                finalists = self._break_score_tie_multi(tied_for_first, ballots, needed=2)
                return finalists[0], finalists[1]
    
    def _break_score_tie(
        self,
        tied_choices: List[Any],
        ballots: List[Dict[Any, Decimal]]
    ) -> Any:
        """
        Break a tie between multiple choices using head-to-head comparison.
        
        Step 1 of Official Tiebreaker Protocol: Compare tied choices head-to-head
        and return the one that wins the most matchups.
        
        Args:
            tied_choices: List of choice identifiers that are tied
            ballots: List of ballot dictionaries
            
        Returns:
            The choice that wins the tie
            
        Raises:
            UnresolvedTieError: If tie cannot be resolved
        """
        finalists = self._break_score_tie_multi(tied_choices, ballots, needed=1)
        return finalists[0]
    
    def _break_score_tie_multi(
        self,
        tied_choices: List[Any],
        ballots: List[Dict[Any, Decimal]],
        needed: int = 2
    ) -> List[Any]:
        """
        Break a tie between multiple choices, returning top N choices.
        
        Uses head-to-head comparison matrix to eliminate choices that lose
        the most matchups. Repeats until we have the required number of choices.
        
        Args:
            tied_choices: List of choice identifiers that are tied
            ballots: List of ballot dictionaries
            needed: Number of choices to return (1 or 2)
            
        Returns:
            List of top choices after tiebreaking
            
        Raises:
            UnresolvedTieError: If tie cannot be resolved
        """
        remaining = tied_choices.copy()
        tiebreaker_log = []
        
        while len(remaining) > needed:
            # Build head-to-head preference matrix for remaining choices
            head_to_head = {}
            for choice in remaining:
                head_to_head[choice] = {'wins': 0, 'losses': 0}
            
            # Count head-to-head preferences
            for i, choice_a in enumerate(remaining):
                for choice_b in remaining[i+1:]:
                    a_pref, b_pref, ties = self._count_head_to_head_preferences(
                        choice_a, choice_b, ballots
                    )
                    
                    if a_pref > b_pref:
                        head_to_head[choice_a]['wins'] += 1
                        head_to_head[choice_b]['losses'] += 1
                    elif b_pref > a_pref:
                        head_to_head[choice_b]['wins'] += 1
                        head_to_head[choice_a]['losses'] += 1
                    # Ties don't count
            
            # Find choice(s) with most losses to eliminate
            max_losses = max(h['losses'] for h in head_to_head.values())
            to_eliminate = [c for c in remaining if head_to_head[c]['losses'] == max_losses]
            
            if len(to_eliminate) == len(remaining):
                # Everyone has the same record - perfect tie
                tiebreaker_log.append(
                    f"Head-to-head comparison inconclusive: all choices have equal records"
                )
                # Can't break this tie with head-to-head
                # Return arbitrary subset for now (will be caught by later tiebreakers)
                return remaining[:needed]
            
            # Eliminate the losers
            for choice in to_eliminate:
                remaining.remove(choice)
                tiebreaker_log.append(
                    f"Eliminated {choice} (losses: {head_to_head[choice]['losses']})"
                )
        
        if tiebreaker_log:
            self.tally_log.extend(tiebreaker_log)
        
        return remaining
    
    def _count_head_to_head_preferences(
        self,
        choice_a: Any,
        choice_b: Any,
        ballots: List[Dict[Any, Decimal]]
    ) -> Tuple[int, int, int]:
        """
        Count head-to-head preferences between two choices.
        
        Args:
            choice_a: First choice identifier
            choice_b: Second choice identifier
            ballots: List of ballot dictionaries
            
        Returns:
            Tuple of (a_preferences, b_preferences, ties)
        """
        a_pref = 0
        b_pref = 0
        ties = 0
        
        for ballot in ballots:
            a_stars = ballot.get(choice_a, Decimal('0'))
            b_stars = ballot.get(choice_b, Decimal('0'))
            
            if a_stars > b_stars:
                a_pref += 1
            elif b_stars > a_stars:
                b_pref += 1
            else:
                ties += 1
        
        return a_pref, b_pref, ties
    
    def _run_automatic_runoff(
        self,
        top_two: Tuple[Any, Any],
        ballots: List[Dict[Any, Decimal]],
        scores: Dict[Any, Decimal]
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Run automatic runoff between top 2 choices (Runoff Phase).
        
        Compare the two finalists head-to-head by counting how many voters
        scored each one higher. Applies Steps 2-4 of Official Tiebreaker Protocol
        if needed.
        
        Args:
            top_two: Tuple of (choice_a, choice_b) identifiers
            ballots: List of ballot dictionaries
            scores: Dictionary of average scores (for Step 2 tiebreaking)
            
        Returns:
            Tuple of (winner, runoff_details_dict)
            
        Raises:
            UnresolvedTieError: If tie cannot be resolved after all steps
        """
        choice_a, choice_b = top_two
        
        # Count head-to-head preferences
        a_preferences, b_preferences, ties = self._count_head_to_head_preferences(
            choice_a, choice_b, ballots
        )
        
        # Log runoff results
        self.tally_log.append(f"{choice_a}: {a_preferences} preferences")
        self.tally_log.append(f"{choice_b}: {b_preferences} preferences")
        self.tally_log.append(f"Equal preferences: {ties}")
        self.tally_log.append("")
        
        # Determine winner
        if a_preferences > b_preferences:
            winner = choice_a
            margin = a_preferences - b_preferences
            self.tally_log.append(f"Winner: {winner} (margin: {margin} votes)")
        elif b_preferences > a_preferences:
            winner = choice_b
            margin = b_preferences - a_preferences
            self.tally_log.append(f"Winner: {winner} (margin: {margin} votes)")
        else:
            # Tie in runoff - apply tiebreaker protocol
            self.tally_log.append("=== TIEBREAKER PROTOCOL ===")
            winner = self._break_runoff_tie(choice_a, choice_b, scores, ballots)
        
        runoff_details = {
            'finalists': [choice_a, choice_b],
            'choice_a_preferences': a_preferences,
            'choice_b_preferences': b_preferences,
            'ties': ties,
        }
        
        return winner, runoff_details
    
    def _break_runoff_tie(
        self,
        choice_a: Any,
        choice_b: Any,
        scores: Dict[Any, Decimal],
        ballots: List[Dict[Any, Decimal]]
    ) -> Any:
        """
        Break a tie in the runoff phase using Steps 2-4 of Official Tiebreaker Protocol.
        
        Step 2: Break tie in favor of candidate with higher score
        Step 3: Break tie by five-star rating counts
        Step 4: Raise UnresolvedTieError if tie persists
        
        Args:
            choice_a: First choice identifier
            choice_b: Second choice identifier
            scores: Dictionary of average scores
            ballots: List of ballot dictionaries
            
        Returns:
            The winning choice
            
        Raises:
            UnresolvedTieError: If tie cannot be resolved
        """
        tiebreaker_log = []
        
        # Step 2: Higher score wins
        if scores[choice_a] > scores[choice_b]:
            tiebreaker_log.append(
                f"Step 2: Tie broken by score - {choice_a} wins "
                f"({scores[choice_a]} vs {scores[choice_b]})"
            )
            self.tally_log.extend(tiebreaker_log)
            self.tally_log.append(f"Winner: {choice_a}")
            return choice_a
        elif scores[choice_b] > scores[choice_a]:
            tiebreaker_log.append(
                f"Step 2: Tie broken by score - {choice_b} wins "
                f"({scores[choice_b]} vs {scores[choice_a]})"
            )
            self.tally_log.extend(tiebreaker_log)
            self.tally_log.append(f"Winner: {choice_b}")
            return choice_b
        
        # Step 3: Five-star rating counts
        tiebreaker_log.append("Step 2 inconclusive (equal scores)")
        tiebreaker_log.append("Attempting Step 3: Five-star rating tiebreaker")
        
        winner = self._break_tie_by_five_stars(choice_a, choice_b, ballots, tiebreaker_log)
        
        if winner is not None:
            self.tally_log.extend(tiebreaker_log)
            self.tally_log.append(f"Winner: {winner}")
            return winner
        
        # Step 4: Unresolved tie - raise exception for manual resolution
        tiebreaker_log.append("Step 3 inconclusive")
        tiebreaker_log.append("All automatic tiebreakers exhausted")
        self.tally_log.extend(tiebreaker_log)
        
        raise UnresolvedTieError(
            tied_candidates=[choice_a, choice_b],
            tiebreaker_log=tiebreaker_log
        )
    
    def _break_tie_by_five_stars(
        self,
        choice_a: Any,
        choice_b: Any,
        ballots: List[Dict[Any, Decimal]],
        tiebreaker_log: List[str]
    ) -> Any:
        """
        Break tie using five-star rating counts (Step 3 of Official Protocol).
        
        - First, try: candidate with most 5-star ratings wins
        - If still tied: eliminate candidate with fewest 5-star ratings
        
        Args:
            choice_a: First choice identifier
            choice_b: Second choice identifier
            ballots: List of ballot dictionaries
            tiebreaker_log: Log to append tiebreaker attempts to
            
        Returns:
            Winning choice, or None if still tied
        """
        # Count five-star ratings for each choice
        a_five_stars = sum(
            1 for b in ballots 
            if b.get(choice_a, Decimal('0')) == Decimal('5')
        )
        b_five_stars = sum(
            1 for b in ballots 
            if b.get(choice_b, Decimal('0')) == Decimal('5')
        )
        
        tiebreaker_log.append(
            f"Five-star counts: {choice_a}={a_five_stars}, {choice_b}={b_five_stars}"
        )
        
        # Candidate with most 5-star ratings wins
        if a_five_stars > b_five_stars:
            tiebreaker_log.append(f"Step 3: {choice_a} wins (more five-star ratings)")
            return choice_a
        elif b_five_stars > a_five_stars:
            tiebreaker_log.append(f"Step 3: {choice_b} wins (more five-star ratings)")
            return choice_b
        
        # Still tied - both have same number of 5-star ratings
        # This is as far as the official protocol goes for automatic resolution
        tiebreaker_log.append("Equal five-star ratings")
        return None

