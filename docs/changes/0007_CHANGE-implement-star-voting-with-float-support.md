# Change 0007: Implement STAR Voting with Float Support

## Description

Implement CrowdVote's own standalone STAR (Score Then Automatic Runoff) voting tally algorithm with native support for fractional star ratings. The external `starvote` library strictly requires integer scores (0-5), but CrowdVote's delegation system produces calculated ballots with fractional stars (e.g., 3.7, 4.23) when averaging across multiple inherited votes.

**SCOPE**: This change creates a new standalone `STARVotingTally` service only. It does NOT integrate with existing code, modify database schemas, or update UI. Integration will happen in a future change.

## Problem

The `starvote` library validation rejects non-integer ballot scores:
```python
ballots = [{'apple': 3.7, 'banana': 2.9}]
starvote.election(starvote.STAR_Voting, ballots)
# ValueError: ballot['apple'] score is invalid, all scores must be integer
```

This is incompatible with CrowdVote's delegation calculation, where User A following Users B, C, and D (who themselves follow others) will inherit averaged fractional star ratings.

## Why Write Our Own Instead of Fork starvote?

After analyzing the [starvote library](https://github.com/larryhastings/starvote), we've decided to write our own implementation rather than fork or submit a PR:

**Reasons:**
1. **Simplicity**: Core STAR algorithm is straightforward (~100 lines including tie-breaking)
2. **Design conflict**: starvote is intentionally designed for integer ballots only
3. **Different requirements**: We need CrowdVote-specific tie-breaking and Decimal precision
4. **No baggage**: Don't need 5 electoral systems, file parsing, CLI, complex tiebreaker framework
5. **Timeline control**: No waiting for PR review/merge
6. **Maintenance**: No dependency on external library updates

## Solution

Implement custom STAR voting algorithm in `democracy/services.py` with Decimal support:

### STAR Voting Algorithm (Core Logic)

**Phase 1: Score Phase (S)**
```python
for each choice:
    total_stars = sum(ballot[choice] for all ballots)
    average_stars = total_stars / number_of_ballots
    
# Identify top 2 choices with highest average
# Handle ties using Official Tiebreaker Protocol Step 1
```

**Phase 2: Automatic Runoff (AR)**
```python
# Compare top 2 choices head-to-head
for each ballot:
    if ballot[choice_A] > ballot[choice_B]:
        choice_A_preferences += 1
    elif ballot[choice_B] > ballot[choice_A]:
        choice_B_preferences += 1
    else:
        ties += 1

# Winner is choice with more preferences
# Handle ties using Official Tiebreaker Protocol Step 2
```

### Official Tiebreaker Protocol

Following [STAR Voting Official Tiebreaker Protocol](https://www.starvoting.org/ties):

**Step 1: Ties in Scoring Round**
- Break tie in favor of candidate scored higher by more voters
- Compare tied candidates head-to-head
- Eliminate candidate(s) who lost the most matchups
- Repeat until two candidates can advance to runoff

**Step 2: Ties in Runoff Round**
- Break tie in favor of candidate who scored higher in Score Phase

**Step 3: Unresolved Ties**
- Break tie in favor of candidate with most 5-star ratings
- If still tied, eliminate candidate(s) with least 5-star ratings

**Step 4: Community Manager Decision (CrowdVote-Specific)**
- If tie persists after Steps 1-3, raise `UnresolvedTieError`
- Return tied candidates to Community Manager for resolution
- Manager decides tie-breaking method (coin toss, revote, etc.)
- **No random/automatic tie-breaking at this level**

### Implementation Requirements

**File: `democracy/services.py`**

Create new service class `STARVotingTally`:

**Input:**
```python
{
    'ballots': [
        {choice_uuid: Decimal('3.7'), choice_uuid2: Decimal('4.0'), ...},
        {choice_uuid: Decimal('5'), choice_uuid2: Decimal('2.5'), ...},
        ...
    ]
}
```

**Core methods:**
- `_calculate_scores(ballots)` → Average stars per choice
- `_get_top_two_with_tiebreak(scores, ballots)` → Top 2 choices (applying Step 1 if needed)
- `_run_automatic_runoff(top_two, ballots, scores)` → Winner (applying Step 2 if needed)
- `_break_tie_by_five_star_ratings(tied_choices, ballots)` → Step 3 tiebreaker
- `_count_head_to_head_preferences(choice_a, choice_b, ballots)` → Head-to-head comparison

**Output:**
```python
{
    'winner': Choice object (or None if UnresolvedTieError),
    'tied_candidates': [Choice objects] if unresolved,
    'scores': {choice: Decimal_average_stars},
    'runoff_details': {
        'finalists': [choice_a, choice_b],
        'choice_a_preferences': int,
        'choice_b_preferences': int,
        'ties': int
    },
    'tally_log': [
        'Score Phase: Apple 4.23 avg (26 votes), Banana 3.67 avg (26 votes)',
        'Runoff: Apple vs Banana',
        'Apple: 15 preferences, Banana: 11 preferences',
        'Winner: Apple (margin: 4 votes)',
    ]
}
```

**Critical requirements:**
- Use `decimal.Decimal` throughout (never float)
- Convert integer ballots to Decimal: `Decimal('5')`
- All arithmetic operations preserve precision
- Log every step for complete audit trail
- Raise `UnresolvedTieError` if tie persists after Step 3

### Decimal Precision Strategy

**The Problem:**
Complex delegation chains (A follows B,C; B follows D,E,F; D follows G,H...) can produce very long decimal numbers like `3.58372894573756383` after multiple averaging operations.

**Storage Precision: 8 Decimal Places**

Configure Python's Decimal context and quantize for storage:

```python
from decimal import Decimal, getcontext

# Set global precision for calculations (high enough to avoid rounding during calculation)
getcontext().prec = 12  # 12 significant figures during calculation

# Quantize to 8 decimal places before storage
calculated_stars = Decimal('3.58372894573756383').quantize(Decimal('0.00000001'))
# Result: Decimal('3.58372895')  (8 decimal places)
```

**Format for Future Database Storage:**

```python
# Future: In Ballot model (or snapshot JSON storage)
# max_digits=9: Total digits: 1 digit before decimal + 8 after (e.g., 3.58372895)
# decimal_places=8: 8 decimal places
# Range: 0.00000000 to 5.00000000
```

**Benefits of 8 Decimal Places:**
- Sufficient precision for fairness (even 10+ delegation levels)
- Prevents database overflow
- Reasonable for display and logging
- Maintains comparison accuracy for STAR voting
- Auditability preserved

**Implementation Notes:**
- Set `getcontext().prec = 12` at module level in `star_voting.py`
- Provide helper function to quantize to 8 decimal places: `.quantize(Decimal('0.00000001'))`
- All Decimal comparisons work perfectly (e.g., `Decimal('3.58372895') > Decimal('3.5')`)
- UI display logic will be handled in future integration work

### Testing Requirements

**File: `tests/test_services/test_star_voting_float.py`**

**Core Algorithm Tests:**
- Test score phase with integer ballots (backward compatibility)
- Test score phase with Decimal ballots (3.7, 4.23, etc.)
- Test automatic runoff phase
- Test winner determination
- Test tally log generation

**Tiebreaker Protocol Tests:**

**Step 1: Score Phase Ties**
- Test 2-way tie broken by head-to-head comparison
- Test 3-way tie with elimination of lowest head-to-head performer
- Test multiple rounds of Step 1 elimination

**Step 2: Runoff Phase Ties**
- Test tie in runoff broken by higher score phase average
- Test equal preferences but different scores

**Step 3: Five-Star Rating Tiebreaker**
- Test tie broken by most 5-star ratings
- Test tie broken by eliminating least 5-star ratings

**Step 4: Unresolved Tie**
- Test `UnresolvedTieError` raised when all tiebreakers fail
- Verify error includes list of tied candidates
- Verify error message instructs community manager

**Decimal Precision Tests:**
- Test 8-decimal place storage: `Decimal('3.58372895')`
- Test quantization: verify long decimals truncate to 8 places
- Test calculation precision: `getcontext().prec = 12` works correctly
- Test Decimal comparisons: `3.58372895 > 3.5` (no float conversion issues)
- Test averaging with high precision: multiple nested delegation chains
- Test database field constraints: `max_digits=9, decimal_places=8`

**Edge Cases:**
- Single voter
- All identical ballots
- Single choice (no runoff needed)
- All choices have same score
- Empty ballots (all zeros)
- Maximum precision decimals (verify quantization to 8 places)

**Backward Compatibility:**
- Test exact same results as old starvote implementation for integer ballots
- Compare with known STAR voting election results

### Exception Definition

**File: `democracy/exceptions.py`** (create if doesn't exist)

```python
class UnresolvedTieError(Exception):
    """
    Raised when STAR voting tie cannot be resolved by Official Tiebreaker Protocol.
    
    After Steps 1-3 of the tiebreaker protocol, if candidates remain tied,
    this exception is raised to notify the Community Manager that manual
    tie-breaking is required.
    
    Attributes:
        tied_candidates: List of Choice objects still tied
        message: Instructions for Community Manager
        tiebreaker_log: Log of all tiebreaker attempts
    """
    def __init__(self, tied_candidates, tiebreaker_log):
        self.tied_candidates = tied_candidates
        self.tiebreaker_log = tiebreaker_log
        candidate_titles = ', '.join([c.title for c in tied_candidates])
        self.message = (
            f"Unresolved tie between: {candidate_titles}. "
            f"Community Manager must decide tie-breaking method "
            f"(coin toss, revote, or other community-specific process)."
        )
        super().__init__(self.message)
```

## Files to Create (This Change Only)

1. **democracy/exceptions.py** - Add `UnresolvedTieError` exception (~30 lines)
2. **democracy/star_voting.py** - New module with `STARVotingTally` service class (~200 lines)
3. **tests/test_services/test_star_voting_decimal.py** - Comprehensive test suite (~300 lines)

## Files NOT Modified in This Change

The following will be handled in future integration work:
- ~~`democracy/services.py`~~ - Not touching existing starvote integration yet
- ~~`democracy/models.py`~~ - Not modifying database schemas yet
- ~~`requirements.txt`~~ - Not removing starvote yet
- ~~UI templates~~ - No display logic yet
- ~~Migrations~~ - No database changes yet

## Benefits

1. **Native Float Support**: Calculated ballots with fractional stars work seamlessly
2. **Precision**: Use `Decimal` for exact arithmetic (no float rounding errors)
3. **Control**: Full control over algorithm and tie-breaking behavior
4. **Simplicity**: STAR voting is straightforward to implement correctly
5. **Maintainability**: No external library dependency to maintain
6. **Auditability**: Complete control over logging and result transparency

## Implementation Phases

### Phase 1: Exception Definition (15 min)
1. Create `democracy/exceptions.py`
2. Implement `UnresolvedTieError` exception
3. Test import works

### Phase 2: Core Algorithm (2-3 hours)
1. Create `democracy/star_voting.py` with `STARVotingTally` service
2. Implement score phase with Decimal support
3. Implement automatic runoff phase
4. Add basic tally logging
5. Write core algorithm tests (no tiebreakers yet)
6. **TEST CHECKPOINT**: Verify basic STAR voting works with integer and Decimal ballots

### Phase 3: Tiebreaker Protocol (2-3 hours)
1. Implement Step 1: Score phase ties (head-to-head elimination)
2. Implement Step 2: Runoff phase ties (higher score wins)
3. Implement Step 3: Five-star rating tiebreaker
4. Raise `UnresolvedTieError` if tie persists (Step 4)
5. Write comprehensive tiebreaker tests
6. **TEST CHECKPOINT**: Verify all tiebreaker scenarios work correctly

### Phase 4: Decimal Precision (1 hour)
1. Configure `getcontext().prec = 12` in module
2. Add quantize helper for 8-decimal storage format
3. Test precision handling and comparisons
4. Verify long decimal chains work correctly
5. **FINAL TEST**: Run complete test suite

**Total estimated time: 5-7 hours**

## Success Criteria (This Change Only)

1. ✅ `STARVotingTally` service accepts Decimal ballots (no integer requirement)
2. ✅ Decimal precision: `getcontext().prec = 12` configured, quantize to 8 places
3. ✅ Score phase correctly averages stars across all ballots
4. ✅ Automatic runoff correctly counts head-to-head preferences
5. ✅ Step 1 tiebreaker: Score ties broken by head-to-head comparison
6. ✅ Step 2 tiebreaker: Runoff ties broken by higher score
7. ✅ Step 3 tiebreaker: Remaining ties broken by 5-star counts
8. ✅ `UnresolvedTieError` raised when tie persists (manager decides)
9. ✅ Complete audit log generated for every tally
10. ✅ All new tests pass (100% success rate)
11. ✅ Integer ballot results match starvote behavior exactly
12. ✅ Fractional ballot tallies work correctly
13. ✅ Standalone module with no dependencies on existing code

## Future Work (Not This Change)

- Integrate `STARVotingTally` into existing `democracy/services.py`
- Update database schema for 8-decimal precision
- Remove starvote dependency from requirements.txt
- Add UI display logic for fractional stars
- Update existing tests to use new service

## Notes

- STAR voting algorithm is simple and well-documented
- Core implementation: ~200 lines including comprehensive docstrings and tiebreakers
- Exception handling: ~30 lines
- Decimal precision handling: ~20 lines (context setup, quantization helpers)
- Tests: ~300 lines covering all scenarios (including precision tests)
- Must maintain exact compatibility with existing STAR voting behavior for integer ballots
- This is a **standalone module** - integration happens in future work
- No external library dependencies (pure Python + Django)
- Complete control over audit logging for CrowdVote transparency requirements
- Once integrated, this unblocks Plan #8 (snapshot-based ballot calculation system)

## References

- [STAR Voting Official](https://www.starvoting.org/)
- [STAR Voting Wikipedia](https://en.wikipedia.org/wiki/STAR_voting)
- Current starvote usage in `democracy/services.py` (to be replaced)

