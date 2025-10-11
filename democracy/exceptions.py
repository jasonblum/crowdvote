"""
Democracy app exceptions.

This module defines custom exceptions for the democracy app, particularly
for handling STAR voting edge cases.
"""


class UnresolvedTieError(Exception):
    """
    Raised when STAR voting tie cannot be resolved by Official Tiebreaker Protocol.
    
    After Steps 1-3 of the tiebreaker protocol, if candidates remain tied,
    this exception is raised to notify the Community Manager that manual
    tie-breaking is required.
    
    The Community Manager must decide on an appropriate tie-breaking method
    based on their community's established protocols (coin toss, revote, or
    other community-specific process).
    
    Attributes:
        tied_candidates: List of choice identifiers still tied after all automatic
                        tiebreaker attempts. These can be any hashable type (UUIDs,
                        strings, etc.) that identify the choices in the election.
        tiebreaker_log: List of strings documenting all tiebreaker attempts and
                       their outcomes, providing a complete audit trail.
        message: Human-readable instructions for the Community Manager explaining
                the situation and what action is required.
    
    Example:
        >>> try:
        ...     result = STARVotingTally().run(ballots)
        ... except UnresolvedTieError as e:
        ...     print(e.message)
        ...     print("Tied candidates:", e.tied_candidates)
        ...     print("Tiebreaker log:", e.tiebreaker_log)
    """
    
    def __init__(self, tied_candidates, tiebreaker_log):
        """
        Initialize the UnresolvedTieError.
        
        Args:
            tied_candidates: List of choice identifiers that remain tied
            tiebreaker_log: List of strings documenting tiebreaker attempts
        """
        self.tied_candidates = tied_candidates
        self.tiebreaker_log = tiebreaker_log
        
        # Format candidate list for message
        # Check if candidates are Django model instances with title attribute (not method)
        if tied_candidates and hasattr(tied_candidates[0], 'title') and not callable(tied_candidates[0].title):
            # If candidates are Django model instances with title attribute
            candidate_titles = ', '.join([c.title for c in tied_candidates])
        else:
            # If candidates are simple identifiers (strings, UUIDs, etc.)
            candidate_titles = ', '.join([str(c) for c in tied_candidates])
        
        self.message = (
            f"Unresolved tie between: {candidate_titles}. "
            f"Community Manager must decide tie-breaking method "
            f"(coin toss, revote, or other community-specific process)."
        )
        super().__init__(self.message)

