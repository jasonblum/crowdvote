# Change 0008: Event-Driven Ballot Calculation with System Snapshots

## Description

Fundamentally redesign CrowdVote's ballot calculation and tallying system to be event-driven, efficient, and fully auditable. Replace the current community-wide recalculation approach with targeted affected-user calculation, timestamped system snapshots, and persistent historical records.

## What's Changing vs What's Staying the Same

### ✅ Staying the Same (Already Working)

1. **Signals in `democracy/signals.py`** - Already implemented and working correctly:
   - Vote changed/deleted signals ✅
   - Following changed/deleted signals ✅
   - Membership changed/deleted signals ✅
   - Background threading with `recalculate_community_decisions_async()` ✅
   - HTMX spinner integration ✅
   - Comprehensive logging ✅

2. **DecisionSnapshot Model** - Already exists in `democracy/models.py`:
   - Complete model with all required fields ✅
   - Proper indexes and ordering ✅
   - Status tracking ✅

3. **Snapshot Services (Partially)** - Already exist:
   - `CreateCalculationSnapshot` service exists ✅
   - `SnapshotBasedStageBallots` service exists (needs completion) ⚠️

### 🔄 What's Changing (The Big Refactor)

1. **`StageBallots` Service** - Major refactoring needed:
   - ❌ Currently uses `round(average, 2)` - loses precision
   - ❌ Mixes float and Decimal types
   - ✅ Need to use Decimal throughout
   - ✅ Need to preserve full fractional star precision

2. **`Tally` Service** - Complete rewrite needed:
   - ❌ Has custom STAR voting implementation (lines 26-182)
   - ❌ Does not use Plan #7 `STARVotingTally` class
   - ✅ Need to integrate `democracy/star_voting.py`
   - ✅ Need to support fractional stars properly

3. **SnapshotBasedStageBallots** - Needs full implementation:
   - ⚠️ Currently returns placeholder data
   - ✅ Need to integrate with refactored StageBallots logic
   - ✅ Need to work from frozen snapshot data only

4. **UI (Future Phase)** - New components:
   - Historical results table using Plan #4 DataTables
   - Snapshot detail page with delegation tree visualization

### 💡 Key Insight

**The infrastructure is already there!** The signals work, the snapshot model exists, and the three-step process is already called. What we're doing is:
1. Making the calculation services support fractional stars properly (Decimal precision)
2. Integrating Plan #7's STAR voting implementation
3. Completing the snapshot-based calculation implementation
4. Adding UI to view the historical snapshots

## Critical Context

This is **the heart of CrowdVote's democratic process**. The current system has two fundamental problems:

### Problem 1: Inefficient Full-Community Recalculation

**Current behavior:** When anyone votes, the system loops through the entire community, recursively calculating ballots for everyone who hasn't voted manually.

**New behavior:** When someone votes (or follows/unfollows), only calculate ballots for users **affected by that specific change**. Walk down the delegation tree from the trigger event.

**Example:**
- C votes manually (tags: "budget")
- A follows C on "budget"
- D follows A on "all tags"
- E follows D on "budget"

When C votes → Signal fires → Calculate: A's ballot (inherits from C), D's ballot (inherits from A), E's ballot (inherits from D)

Remember that in this very simple example above, each user is only inherting from one person.  But in reality, people will be following multiple people, who are them selves following multiplel peoplem, etc.  This process much average the stars across ballots to calculate each follower's ballot.

**Do NOT calculate ballots for unrelated community members.**.

### Problem 2: Misuse of STAR Voting for Ballot Calculation

**Current behavior:** Using STAR voting (which returns a **winner**) to calculate individual member ballots.

**Reality:** STAR voting determines election winners, not individual ballots.

**Correct approach:** 
- **Ballot calculation** = Simple averaging of inherited star ratings
- **Final tally** = STAR voting on all ballots (from Plan #7)

**Example of ballot calculation:**
```
B's ballot: {apple: 3, banana: 2, orange: 5} tagged ["budget"]
C's ballot: {apple: 5, banana: 2, orange: 0} tagged ["budget"]

A follows B on ["budget"]
A follows C on ["budget"]

A's calculated ballot:
- apple: (3 + 5) / 2 = 4.0
- banana: (2 + 2) / 2 = 2.0
- orange: (5 + 0) / 2 = 2.5
- tags: ["budget"] (intersection of A's following tags with B and C's ballot tags)
```

## Three-Step Process

### Step 1: Calculate Affected Ballots

**Trigger events (signals already implemented):**
1. Vote cast/updated
2. Following created/deleted
3. Following tags changed
4. Membership changed
5. Decision published/closed

**When signal fires:**
- Identify the "source" user (who voted/was followed/etc.)
- Walk DOWN the delegation tree to find affected users
- Calculate ballots only for affected users
- Use simple averaging with tag matching

### Step 2: Create System Snapshot

**Critical requirement:** Grab a timestamped snapshot of the **entire system state** before tallying.

**Why:** The tally process may take time. During tallying, users might vote/follow/unfollow, which would corrupt the results. The snapshot freezes the system state at a point in time.

**Snapshot contents:**
- Timestamp
- All ballots (manual + calculated) with star ratings
- All delegation relationships (who follows whom on which tags)
- Complete calculation trees (how each ballot was calculated)
- Anonymous/non-anonymous status
- Final vs. interim status

**Snapshot = Single source of truth for that point in time**

### Step 3: Tally Using STAR Voting

Run STAR voting tally (Plan #7 implementation) on the ballots captured in the snapshot. The tally operates on snapshot data, not live system data.

## Tag Inheritance Logic

**CRITICAL CLARIFICATION:** 
- **Choices are NEVER tagged** (apple, banana, hotdog are not tagged)
- **Decisions are tagged** (the question "What should we eat for lunch?" is tagged)
- When you vote, you tag the DECISION with terms like ["budget", "environment"]
- Others following you on matching tags inherit your ENTIRE BALLOT + matching tags

**Critical rule:** You inherit ballots AND tags where tags match.

### Tag Matching Examples

**Example 1: Specific tag following**
```
Decision: "What should we eat for lunch?" (Choices: apple, banana, hotdog)
B votes: {apple: 5, banana: 3, hotdog: 2} and tags the DECISION ["budget", "environment", "infrastructure"]
A follows B on ["budget"]
A inherits: {apple: 5, banana: 3, hotdog: 2} tagged ["budget"]  ← full ballot, tag intersection only
```

**Example 2: ALL tags following**
```
Decision: "Community room color" (Choices: gray, blue, green)
B votes: {gray: 5, blue: 2, green: 0} and tags the DECISION ["budget", "environment", "infrastructure"]
A follows B on [ALL tags]
A inherits: {gray: 5, blue: 2, green: 0} tagged ["budget", "environment", "infrastructure"]  ← full ballot, all tags
```

**Example 3: Tag propagation blocking**
```
Decision: "Park renovation" (Choices: playground, garden, trails)
B votes: {playground: 5, garden: 3, trails: 2} and tags DECISION ["budget", "environment"]
A follows B on ["budget"]
A's inherited ballot: {playground: 5, garden: 3, trails: 2} tagged ["budget"]  ← tag intersection

D follows A on ["environment"]
D CANNOT inherit from A (A's ballot not tagged "environment")
```

**Example 4: Multi-source averaging with tag intersection**
```
Decision: "Weekend menu" (Choices: pizza, tacos, sushi)
B votes: {pizza: 5, tacos: 2, sushi: 1} and tags DECISION ["budget"]
C votes: {pizza: 3, tacos: 4, sushi: 2} and tags DECISION ["budget", "infrastructure"]

A follows B on ["budget"]
A follows C on ["budget"]

A inherits from both (both have "budget" tag):
- Full ballot averaged: pizza: (5 + 3) / 2 = 4.0, tacos: (2 + 4) / 2 = 3.0, sushi: (1 + 2) / 2 = 1.5
- tags: ["budget"]  ← intersection of ["budget"] with B's ["budget"] and C's ["budget", "infrastructure"]
```

### Recursive Calculation with Circular Prevention

**Algorithm:**
```python
def calculate_ballot(user, decision, follow_path=[], affected_users_only=False):
    """
    Calculate ballot for user on decision through delegation.
    
    Args:
        user: User whose ballot to calculate
        decision: Decision being voted on
        follow_path: List of users already in calculation chain (prevents circular)
        affected_users_only: If True, only calculate if user in affected set
        
    Returns:
        dict: Ballot {choice: Decimal_stars, ...} and list of inherited tags
    """
    # Circular detection
    if user in follow_path:
        log(f"Circular reference: {' → '.join(follow_path)} → {user}")
        return None, []
    
    # Check for manual ballot
    manual_ballot = get_manual_ballot(user, decision)
    if manual_ballot:
        return manual_ballot.ratings, manual_ballot.tags
    
    # Get followings for this user in this community
    followings = user.followings.filter(community=decision.community)
    
    if not followings:
        return None, []  # Can't calculate
    
    # Collect inherited ballots with tag matching
    inherited = []
    for following in followings:
        followee = following.followee
        
        # RECURSE to get followee's ballot
        followee_ballot, followee_tags = calculate_ballot(
            followee, 
            decision, 
            follow_path + [user]
        )
        
        if not followee_ballot:
            continue
        
        # Tag matching
        if following.tags:  # Specific tags
            if any(tag in followee_tags for tag in following.tags):
                # Inherit with tag intersection
                matched_tags = [t for t in following.tags if t in followee_tags]
                inherited.append((followee_ballot, matched_tags))
        else:  # ALL tags
            inherited.append((followee_ballot, followee_tags))
    
    if not inherited:
        return None, []  # No matching tags
    
    # Average all inherited ballots
    averaged_ballot = {}
    all_tags = set()
    
    for ballot, tags in inherited:
        for choice, stars in ballot.items():
            averaged_ballot[choice] = averaged_ballot.get(choice, Decimal(0)) + stars
        all_tags.update(tags)
    
    num_sources = len(inherited)
    averaged_ballot = {
        choice: stars / num_sources 
        for choice, stars in averaged_ballot.items()
    }
    
    return averaged_ballot, list(all_tags)
```

## Database Schema

### New Model: DecisionSystemSnapshot

**File: `democracy/models.py`**

```python
class DecisionSystemSnapshot(BaseModel):
    """
    Timestamped snapshot of complete system state for a decision.
    
    Contains all ballots, delegation relationships, and calculation trees
    at a specific point in time. Provides complete auditability and allows
    rerunning tallies without affecting live system state.
    
    Attributes:
        decision: Decision this snapshot belongs to
        timestamp: When snapshot was created
        snapshot_data: JSON blob with complete system state
        is_final: True if decision was closed when snapshot taken
        winner: Choice that won (set after tally completes)
        tally_log: Complete log of STAR voting tally process
        calculation_status: Status of snapshot processing
        error_log: Any errors during calculation/tally
    """
    decision = models.ForeignKey(Decision, on_delete=models.CASCADE, related_name='snapshots')
    timestamp = models.DateTimeField(auto_now_add=True)
    snapshot_data = models.JSONField()
    is_final = models.BooleanField(default=False)
    winner = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    tally_log = models.JSONField(default=dict, blank=True)
    calculation_status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('calculating', 'Calculating Ballots'),
            ('snapshotting', 'Creating Snapshot'),
            ('tallying', 'Running Tally'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ]
    )
    error_log = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['decision', '-timestamp']),
            models.Index(fields=['decision', 'is_final']),
        ]
    
    def __str__(self):
        status = "FINAL" if self.is_final else "interim"
        return f"{self.decision.title} - {status} - {self.timestamp}"
```

### Snapshot Data Structure (JSON)

```json
{
    "timestamp": "2025-10-11T10:30:00Z",
    "decision_id": "uuid",
    "community_id": "uuid",
    "is_final": false,
    "stats": {
        "total_members": 34,
        "manual_ballots": 8,
        "calculated_ballots": 18,
        "no_ballot": 8,
        "lobbyists": 0,
        "circular_prevented": 3,
        "max_delegation_depth": 7
    },
    "manual_ballots": [
        {
            "username": "Kelly",
            "display_name": "Kelly Martinez",
            "is_anonymous": false,
            "ballot": {
                "choice_uuid_1": "5",
                "choice_uuid_2": "3",
                "choice_uuid_3": "0"
            },
            "tags": ["environment", "budget"],
            "influence_count": 12
        }
    ],
    "calculated_ballots": [
        {
            "username": "Carol",
            "display_name": "Carol Smith",
            "is_anonymous": false,
            "ballot": {
                "choice_uuid_1": "4.5",
                "choice_uuid_2": "2.33333",
                "choice_uuid_3": "1.66667"
            },
            "tags": ["environment", "budget"],
            "inherited_from": ["Kelly", "Olivia"],
            "calculation_tree": {
                "follows": [
                    {
                        "followee": "Kelly",
                        "on_tags": ["environment", "budget"],
                        "result": "MATCH",
                        "inherited_tags": ["environment", "budget"]
                    },
                    {
                        "followee": "Olivia",
                        "on_tags": ["ALL"],
                        "result": "MATCH",
                        "inherited_tags": ["maintenance"],
                        "olivia_calculation": {
                            "follows": [
                                {
                                    "followee": "Jack",
                                    "on_tags": ["maintenance"],
                                    "result": "NO MATCH - Jack ballot tagged [budget]"
                                },
                                {
                                    "followee": "Bob",
                                    "on_tags": ["environment", "beautification"],
                                    "result": "NO MATCH - Bob ballot tagged [maintenance]"
                                }
                            ],
                            "result": "no ballot calculated (no matching tags)"
                        }
                    },
                    {
                        "followee": "Victor",
                        "on_tags": ["environment"],
                        "result": "CIRCULAR PREVENTED - Victor → Carol → Victor"
                    }
                ]
            },
            "influence_count": 3
        }
    ],
    "no_ballot": [
        {
            "username": "Rachel",
            "display_name": "Rachel Green",
            "is_anonymous": true,
            "reason": "Not following anyone"
        },
        {
            "username": "Maya",
            "display_name": "Maya Lopez",
            "is_anonymous": false,
            "reason": "Following others but no tag matches",
            "follows": ["Carol on [budget]", "Jack on [infrastructure]"]
        }
    ],
    "relationships": [
        {
            "follower": "Carol",
            "followee": "Kelly",
            "tags": ["environment", "budget"]
        },
        {
            "follower": "Carol",
            "followee": "Olivia",
            "tags": []  // ALL tags
        }
    ],
    "tally_result": {
        "method": "STAR Voting",
        "winner": "choice_uuid_1",
        "score_phase": {
            "choice_uuid_1": {"avg_stars": "4.23", "vote_count": 26},
            "choice_uuid_2": {"avg_stars": "3.67", "vote_count": 26},
            "choice_uuid_3": {"avg_stars": "2.10", "vote_count": 26}
        },
        "runoff_phase": {
            "choice_uuid_1": 15,
            "choice_uuid_2": 11,
            "ties": 0
        },
        "margin": 4,
        "margin_percentage": "15.4%"
    }
}
```

## Service Layer Redesign

### File: `democracy/services.py`

**IMPORTANT:** We will be **refactoring the existing services**, not creating entirely new ones. The existing `StageBallots` and `Tally` services need major refactoring because the old implementation did not support fractional stars (Plan #7 changed this).

**Refactored `StageBallots` service:**

```python
class StageBallots(Service):
    """
    Calculate ballots for ALL users in a decision (for manual testing/commands).
    
    This service now:
    - Supports fractional star ratings (Decimal)
    - Uses simple averaging (not STAR voting) for ballot calculation
    - Properly handles tag inheritance and matching
    - Tracks delegation trees for visualization
    
    For event-driven updates, signals will call this service targeting only
    affected users (implementation detail handled by the service).
    
    Input (via process() method):
        No explicit input - processes all open decisions
        
    Output:
        {
            'delegation_trees': {decision_id: tree_data},
            'ballots_calculated': int,
            'calculation_trees': [detailed logs],
            'circular_prevented': int
        }
    """
```

**Existing `CreateCalculationSnapshot` and `SnapshotBasedStageBallots` services:**

These services already exist (see lines 791-1019 in `democracy/services.py`) but need refactoring to:
- Integrate with refactored `StageBallots` logic
- Support fractional star ratings throughout
- Use Plan #7 STAR voting for final tally

**Refactored `Tally` service:**

```python
class Tally(Service):
    """
    Run STAR voting tally on ballots from a decision.
    
    Now uses Plan #7 STAR voting implementation (democracy/star_voting.py)
    with full Decimal support for fractional star ratings.
    
    Input (via process() method):
        No explicit input - processes all open decisions
        
    Output:
        HTML-formatted tally report with:
        - Score phase results
        - Automatic runoff results
        - Winner determination
        - Tag analysis
    """
```

## Management Command Redesign

### File: `democracy/management/commands/stage_and_tally_ballots.py`

**Complete rewrite to use new three-step process:**

```python
class Command(BaseCommand):
    """
    DEPRECATED: This command now only for manual testing.
    
    In production, signals automatically trigger:
    1. CalculateAffectedBallots (Step 1)
    2. CreateSystemSnapshot (Step 2)
    3. TallyFromSnapshot (Step 3)
    
    This command is useful for:
    - Manual recalculation after data fixes
    - Testing the full pipeline
    - Debugging calculation issues
    """
    
    def handle(self, *args, **options):
        # For each open decision:
        #   1. Calculate all ballots (not just affected - manual mode)
        #   2. Create snapshot
        #   3. Run tally
        #   4. Display results matching vote-inheritance-tree.html format
```

## UI Changes

### Decision Detail Page: Results Table

**File: `democracy/templates/democracy/decision_detail.html`**

**Replace left sidebar "Live Results" section with bottom-of-page historical results table.**

**Current (to remove):**
```
📊 Live Results
🟢 Live
Voting closes in: 11d 9h 57m 23s
Participation 16/34 (47.1%)
Calculation Calculating Votes...
📋 Complete Results & Analysis
```

**New: Historical Results Table (bottom of page)**

Use DataTables component from Plan #4 (reusable pattern).

**Columns:**
1. **Timestamp** - When snapshot was taken (sortable, default desc)
2. **Status** - Badge: "🔴 FINAL" (closed decision) or "🟢 Interim" (open decision)
3. **Winner** - Choice title that won
4. **Participation** - "16/34 (47.1%)" - manual + calculated / total members
5. **Manual Ballots** - Count of directly cast ballots
6. **Calculated** - Count of inherited ballots
7. **Action** - "View Details" button → links to snapshot detail page

**Table features:**
- Show all snapshots (keep forever)
- Default sort: newest first
- Pagination: 10/25/50/100 per page
- Search by timestamp, winner
- Mobile responsive (DataTables handles this)

### New Page: Snapshot Detail/Results

**File: `democracy/templates/democracy/snapshot_detail.html`**

**URL:** `/communities/<uuid>/decisions/<uuid>/snapshots/<uuid>/`

**Content structure (modeled after vote-inheritance-tree.html):**

1. **Header stats:**
   - Manual: 8
   - Calculated: 41
   - Circular Prevented: 10
   - No Ballot: 16 (can't calculate)
   - Max Depth: 14 levels

2. **Stage 1: Manual Ballots**
   - List all manual voters
   - Show their ballots and tags
   - Show influence count (N) = # of people who inherited from this voter
   - 🏆 for most influential voter(s)

3. **Stage 2: Calculated Ballots (Delegation)**
   - Show delegation trees with indentation
   - For each calculated ballot:
     - Show user (anonymous if applicable)
     - Show who they follow (with tags)
     - Show tag matching results (✓ MATCH or ✗ NO MATCH)
     - Show circular references (⚠️ Circular reference prevented)
     - Show final calculated ballot and inherited tags
   - Use color coding:
     - 🟢 Manual voters
     - 🔵 Calculated voters
     - 🟠 Circular prevented

4. **Stage 3: No Ballot Calculated**
   - List users with no ballot
   - Show reason: "not following anyone" or "following others but no tag matches"

5. **Stage 4: STAR Voting Tally**
   - Show score phase results (average stars per choice)
   - Show automatic runoff results (preferences between top 2)
   - Show winner with margin

**Visual style:** Match vote-inheritance-tree.html dark theme, monospace font, indented trees

## Signal Integration (Already Exists)

**File: `democracy/signals.py`** (from legacy Plan #22)

**Update signal handlers to call new three-step process:**

```python
def vote_changed(sender, instance, created, **kwargs):
    """
    Triggered when Vote is saved.
    
    New behavior:
    1. Call CalculateAffectedBallots (only users affected by this vote)
    2. Call CreateSystemSnapshot
    3. Call TallyFromSnapshot
    """

def following_changed(sender, instance, **kwargs):
    """
    Triggered when Following is created/deleted/modified.
    
    New behavior:
    1. Find all decisions in affected communities
    2. For each decision, run three-step process
    """
```

## Testing Requirements

### New Test Files

**tests/test_services/test_calculate_affected_ballots.py:**
- Test single-level delegation (A follows B, B votes)
- Test multi-level delegation (E follows D follows C follows B follows A)
- Test tag intersection inheritance
- Test ALL tags inheritance
- Test circular reference detection
- Test complex scenarios (multiple sources, mixed tags)
- Test fractional star averaging

**tests/test_services/test_system_snapshot.py:**
- Test snapshot creation with complete data structure
- Test snapshot captures all required fields
- Test final vs interim status
- Test multiple snapshots for same decision
- Test snapshot immutability (once created, never modified)

**tests/test_services/test_tally_from_snapshot.py:**
- Test STAR tally on snapshot data (uses Plan #7 implementation)
- Test float ballot support
- Test result recording in snapshot
- Test tally operates on frozen snapshot, not live data

**tests/test_views/test_snapshot_detail.py:**
- Test snapshot detail page renders correctly
- Test calculation tree visualization
- Test anonymous voter handling
- Test permission checks (who can view snapshots?)

**tests/test_models/test_decision_snapshot.py:**
- Test DecisionSystemSnapshot model fields
- Test snapshot ordering
- Test is_final validation
- Test relationships to Decision and Choice

**tests/test_integration/test_event_driven_calculation.py:**
- End-to-end test: vote → affected users → snapshot → tally
- Test delegation chains propagate correctly
- Test tag inheritance through multiple levels
- Test circular detection in complex networks

### Updated Test Files

- **tests/test_services/test_star_voting.py** - Update to use Plan #7 float implementation
- **tests/test_services/test_tally.py** - Update to use snapshot-based tallying
- **tests/test_integration/test_basic_workflows.py** - Update to expect snapshot creation

## Implementation Phases

**CRITICAL:** Each phase requires explicit approval before proceeding to the next.

---

### Phase 1: Database Model (Already Exists!)

**Status:** ✅ DecisionSnapshot model already exists in `democracy/models.py` (lines 1000-1202)

**What we have:**
- Complete model with all required fields
- Proper indexes and ordering
- Status tracking fields (calculation_status, error_log, etc.)
- JSON field for snapshot_data
- Validation logic

**What needs checking:**
1. Review existing model against plan requirements
2. Ensure all fields match plan specification
3. Check if migration needed for any field changes

**Deliverables:**
- [ ] Review DecisionSnapshot model
- [ ] Create migration if needed
- [ ] Run migration
- [ ] Write/update model tests

**✋ APPROVAL GATE 1:** Model verified and tested before proceeding to services

---

### Phase 2A: Refactor StageBallots Service - Ballot Calculation Logic

**File:** `democracy/services.py` lines 16-598

**Current issues:**
- Does NOT support fractional stars properly
- Uses `round(average, 2)` instead of keeping full Decimal precision
- Mixes float and Decimal types
- Vote.stars field expects Decimal but service uses float

**Changes needed:**

1. **Import Decimal at top of file:**
```python
from decimal import Decimal
```

2. **Update `get_or_calculate_ballot()` method:**
   - Remove `round()` calls on star scores
   - Keep Decimal precision throughout
   - Ensure ballot.votes.create() receives Decimal, not float
   - Fix JSON serialization issues (convert Decimal to str for JSON)

3. **Update `calculate_star_score_with_tiebreaking()` method:**
   - Remove `round(average, 2)` on line 513
   - Return full Decimal precision
   - Store as Decimal in database

4. **Update `should_inherit_ballot()` method:**
   - Already correct - tag matching logic is good
   - Verify it handles ALL tags (empty string) correctly

5. **Test with dummy data:**
   - Generate test communities
   - Verify fractional stars propagate correctly
   - Check that averaging produces proper Decimals

**Deliverables:**
- [ ] Refactor StageBallots to use Decimal throughout
- [ ] Remove all round() calls on star scores  
- [ ] Fix JSON serialization (Decimal → str for JSON)
- [ ] Write tests for fractional star propagation
- [ ] Test with complex delegation chains (A→B→C→D)
- [ ] Verify tag inheritance works correctly

**✋ APPROVAL GATE 2A:** StageBallots refactored and tested with fractional stars

---

### Phase 2B: Integrate STAR Voting from Plan #7

**File:** `democracy/services.py` lines 600-788 (Tally service)

**Current issues:**
- Tally service has custom STAR voting implementation
- Does NOT use `democracy/star_voting.py` from Plan #7
- Needs complete rewrite to use STARVotingTally class

**Changes needed:**

1. **Import Plan #7 STAR voting:**
```python
from .star_voting import STARVotingTally
from decimal import Decimal
```

2. **Rewrite Tally.process() to use STARVotingTally:**
   - Remove custom `score()` and `automatic_runoff()` methods
   - Build ballot list in correct format for STARVotingTally
   - Convert Vote.stars to Decimal
   - Handle UnresolvedTieError
   - Format tally log for display

3. **Remove obsolete methods:**
   - Delete old `score()` method (lines 26-76)
   - Delete old `automatic_runoff()` method (lines 78-182)
   - Keep delegation tree logic in StageBallots

**Deliverables:**
- [ ] Rewrite Tally service to use STARVotingTally
- [ ] Remove custom STAR voting code
- [ ] Convert all ballots to Decimal format
- [ ] Handle tie resolution properly
- [ ] Write tests for Tally with fractional stars
- [ ] Test with existing STAR voting test scenarios

**✋ APPROVAL GATE 2B:** Tally service integrated with Plan #7 STAR voting

---

### Phase 2C: Refactor Snapshot Services

**Files:** 
- `democracy/services.py` lines 791-857 (CreateCalculationSnapshot)
- `democracy/services.py` lines 938-1019 (SnapshotBasedStageBallots)

**Current issues:**
- CreateCalculationSnapshot exists but may need Decimal updates
- SnapshotBasedStageBallots is stubbed out (returns placeholder data)
- Need to integrate with refactored StageBallots logic

**Changes needed:**

1. **Update CreateCalculationSnapshot:**
   - Verify Decimal handling in snapshot_data
   - Ensure all star ratings stored as strings in JSON
   - Check membership/following capture logic

2. **Implement SnapshotBasedStageBallots:**
   - Use refactored StageBallots logic
   - Work exclusively from snapshot_data (frozen state)
   - Don't query live database during calculation
   - Return complete delegation tree

3. **Add snapshot-based Tally:**
   - Create method to tally from snapshot data
   - Use STARVotingTally on frozen ballots
   - Store results back in snapshot

**Deliverables:**
- [ ] Update CreateCalculationSnapshot for Decimal
- [ ] Implement SnapshotBasedStageBallots fully
- [ ] Add snapshot-based tally method
- [ ] Write tests for snapshot isolation
- [ ] Test concurrent changes don't affect snapshots
- [ ] Verify frozen state remains immutable

**✋ APPROVAL GATE 2C:** Snapshot services complete and tested

---

### Phase 3: Signal Integration (Minimal Changes)

**File:** `democracy/signals.py`

**Current status:** Signals already exist and work!

**Changes needed:** Very minimal

1. **Update recalculate_community_decisions_async():**
   - Signals already call CreateCalculationSnapshot
   - Signals already call SnapshotBasedStageBallots  
   - Signals already call Tally
   - Just verify they're using refactored services correctly

2. **No structural changes needed** - existing signal handlers are fine:
   - vote_changed ✅
   - following_changed ✅
   - membership_changed ✅
   - etc.

**Deliverables:**
- [ ] Verify signals call refactored services
- [ ] Test signal → snapshot → tally flow
- [ ] Test multiple rapid signals don't corrupt data
- [ ] Check race condition handling

**✋ APPROVAL GATE 3:** Signals verified and tested with refactored services

---

### Phase 4: Update Management Commands

**File:** `democracy/management/commands/stage_and_tally_ballots.py`

**Changes needed:**

1. Update to use refactored services
2. Add option to display results in vote-inheritance-tree format
3. Update help text and documentation
4. Mark as "for manual testing only"

**Deliverables:**
- [ ] Refactor command to use new services
- [ ] Add visualization output option
- [ ] Update help text
- [ ] Test command works end-to-end

**✋ APPROVAL GATE 4:** Management commands updated and tested

---

### Phase 5: Update Dummy Data Generator (If Needed)

**File:** `democracy/management/commands/generate_demo_communities.py` or `generate_dummy_data_new.py`

**Check if needed:**
- Do A-F test user patterns exist?
- Do they have proper tag following relationships?
- Are decisions tagged appropriately?
- Will fractional stars result from current setup?

**Deliverables:**
- [ ] Review existing dummy data
- [ ] Update generator if needed for A-F patterns
- [ ] Generate test data
- [ ] Verify complex delegation produces fractions
- [ ] Verify tag inheritance works in practice

**✋ APPROVAL GATE 5:** Test data generates correctly with all required patterns

---

### Phase 6: UI - Historical Results Table (Backend First!)

**File:** `democracy/views.py` and `democracy/templates/democracy/decision_detail.html`

**Important:** Use DataTables pattern from Plan #4:
- Reference: `docs/changes/0004_CHANGE-reusable-datatables-with-dark-mode.md`
- Reusable component with dark mode support
- Server-side pagination and sorting

**Changes needed:**

1. **Add view method to return snapshot list for decision**
2. **Add table to decision_detail.html**
3. **Remove old "Live Results" sidebar section**
4. **Use Plan #4 DataTables component**

**Deliverables:**
- [ ] Create view for snapshot list
- [ ] Add DataTable to decision detail page
- [ ] Remove old results sidebar
- [ ] Test table rendering and sorting
- [ ] Test dark mode support
- [ ] Test mobile responsive layout

**✋ APPROVAL GATE 6:** Results table complete and tested

---

### Phase 7: UI - Snapshot Detail Page

**Files:**
- `democracy/views.py` (new view)
- `democracy/templates/democracy/snapshot_detail.html` (new template)
- `democracy/urls.py` (new URL pattern)

**Modeled after:** `crowdvote/templates/vote-inheritance-tree.html`

**Changes needed:**

1. Create snapshot detail view
2. Create template with calculation tree visualization
3. Add URL pattern
4. Add navigation from results table

**Deliverables:**
- [ ] Create snapshot_detail view
- [ ] Create template with tree visualization
- [ ] Add URL pattern
- [ ] Test with complex delegation scenarios
- [ ] Test anonymous voter handling
- [ ] Test permission checks
- [ ] Verify dark mode styling

**✋ APPROVAL GATE 7:** Snapshot detail page complete and tested

---

### Phase 8: Integration Testing & Documentation

**Final phase before completion**

**Testing:**
- [ ] Run full test suite (maintain 100% success rate)
- [ ] Test with large communities (100+ members)
- [ ] Test complex delegation scenarios
- [ ] Test fractional star propagation end-to-end
- [ ] Test snapshot immutability
- [ ] Test concurrent user actions
- [ ] Performance test with realistic data

**Documentation:**
- [ ] Update docs/CHANGELOG.md
- [ ] Update AGENTS.md if needed
- [ ] Update crowdvote/templates/docs.html FAQ
- [ ] Document any gotchas or edge cases discovered

**✋ FINAL APPROVAL:** Plan #8 complete and production-ready

## Critical Implementation Notes

### Use Decimal, Not Float

```python
from decimal import Decimal

# When calculating ballots
stars = Decimal('3.7')  # Precise
stars = 3.7  # Avoid - float precision issues

# When averaging
avg = sum(star_values) / Decimal(len(star_values))
```

### Affected Users Algorithm

**Walking DOWN the delegation tree:**

```python
def find_affected_users(trigger_user, decision):
    """
    Find all users whose ballots need recalculation.
    
    Walk down from trigger_user to find everyone who follows them
    (directly or indirectly through delegation chains).
    """
    affected = set()
    
    def walk_down(user, visited=set()):
        if user in visited:
            return  # Circular
        visited.add(user)
        
        # Find everyone who follows this user in this community
        followers = Following.objects.filter(
            followee=user,
            community=decision.community
        )
        
        for following in followers:
            follower = following.follower
            affected.add(follower)
            walk_down(follower, visited.copy())
    
    walk_down(trigger_user)
    return affected
```

### Snapshot Immutability

**Once created, snapshots are NEVER modified.** They are historical records.

- No updates to snapshot_data after creation
- Tally results are written once
- If re-tally needed, create new snapshot

### Keeping Snapshots Forever

**No automatic deletion.** Snapshots are the audit trail.

- Database storage is cheap
- Transparency requires complete history
- Admin interface can manually delete if absolutely necessary
- Consider database backups/archiving for very old snapshots (years)

## Success Criteria

1. ✅ Vote triggers calculation of only affected users (not entire community)
2. ✅ Ballot calculation uses simple averaging (not STAR voting)
3. ✅ Tag inheritance works correctly (intersection + ALL tags)
4. ✅ Circular references detected and logged
5. ✅ Fractional stars handled throughout (using Decimal)
6. ✅ System snapshots created with complete data structure
7. ✅ Snapshots frozen and immutable after creation
8. ✅ STAR tally operates on snapshot data (Plan #7 implementation)
9. ✅ Historical results table displays all snapshots
10. ✅ Snapshot detail page visualizes calculation trees
11. ✅ All snapshots kept forever (no automatic deletion)
12. ✅ Signals trigger three-step process automatically
13. ✅ Tests maintain 100% success rate
14. ✅ Complex delegation scenarios work correctly

## Dependencies

**Requires Plan #7 completion:** This plan depends on having a working STAR voting implementation with float support.

## Notes

- This is the most complex change in CrowdVote history
- Take time to implement carefully and test thoroughly
- Tag inheritance is subtle - test extensively
- Snapshot structure mirrors vote-inheritance-tree.html visualization
- The three-step process ensures data integrity during concurrent changes
- Event-driven calculation is vastly more efficient than full community loops
- Complete audit trail satisfies transparency requirements

## References

- `crowdvote/templates/vote-inheritance-tree.html` - Visualization example
- `docs/legacy/features/0022_PLAN-async_vote_calculation_signals_threading.md` - Signal implementation
- `docs/changes/0004_CHANGE-reusable-datatables-with-dark-mode.md` - DataTables pattern
- `docs/changes/0007_CHANGE-implement-star-voting-with-float-support.md` - STAR voting with floats

