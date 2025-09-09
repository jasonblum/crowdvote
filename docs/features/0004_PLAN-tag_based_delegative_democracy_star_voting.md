# Feature 0004: Core Ballot Delegation System with Tag-Based Following

## Overview

Implement the core CrowdVote delegation system that allows users to follow others on specific tags and inherit both their votes and tags. Decisions are published without tags, then voters apply tags as they vote, hoping others who follow them on those tags will inherit their influence. This builds on the existing services.py foundation to create working ballot calculation with tag-based inheritance, ordered tie-breaking, and complete audit trails.

## Context

The user has 370 users, 204 following relationships, and 3 communities but no decisions yet. The existing services.py has the delegation framework but needs:
- Tag-based following implementation  
- Tag inheritance with votes (inherit tags when inheriting votes)
- Ordered tie-breaking for conflicts
- Complete STAR voting calculation
- Working dummy data pipeline

## Phase 1: Data Layer Foundation

### Simple Tag Implementation
**File: `democracy/models.py` and `accounts/models.py`**
- Add `tags` CharField to `Ballot` model for comma-separated tags (e.g., "environmental,fiscal")
- Update `Following` model to include `tags` CharField and `order` field for tie-breaking
- No separate Tag model needed - keep it simple with real-time audit trails
- Create migrations for new fields

### Dummy Data Enhancement  
**File: `democracy/management/commands/generate_dummy_data.py`**
- Generate 2-3 test decisions with choices and close dates (decisions published WITHOUT tags)
- Create tag-specific following relationships with ordered preferences (e.g., "environmental,fiscal")
- Generate some manual ballots from key community members who apply tags as they vote
- Use common tags like "fiscal", "environmental", "safety", "beautification", "infrastructure"

### Admin Interface Updates
**File: `democracy/admin.py`**
- Update Following admin to show tags and order fields
- Update Ballot admin to show tags field
- Enhance Decision admin to show choices and voting status

## Phase 2: Core Service Implementation

### Ballot Calculation Service
**File: `democracy/services.py`**

**Update `StageBallots.get_or_calculate_ballot()` method:**
1. **Topic-based inheritance filtering**: Only inherit votes from followees on matching topics
2. **Tag inheritance logic**: Inherit tags from followees for topics you follow them on  
3. **Ordered conflict resolution**: Use Following.order field for tie-breaking
4. **Audit trail enhancement**: Track who votes/tags were inherited from
5. **Circular reference protection**: Maintain existing follow_path logic

**Key algorithm steps:**
1. Get voter's followings ordered by preference (Following.order)
2. For each following relationship, check if decision has matching topics
3. If match found, inherit both vote and tags for those topics only
4. Calculate average stars for each choice across all inherited votes
5. Use follower order for tie-breaking when averages are equal
6. Create Vote records and BallotTopic records with inheritance tracking
7. Update ballot_tree_log with detailed topic inheritance information

### STAR Voting Implementation
**File: `democracy/services.py`**

**Implement `StageBallots.score()` method:**
- Calculate average star rating for each choice across all voting member ballots
- Update Choice.score fields with calculated averages
- Return ordered results for runoff phase

**Implement `StageBallots.automatic_runoff()` method:**
- Identify top 2 choices from score phase
- For each ballot, determine voter's preferred choice between top 2
- Count preferences to determine winner
- Update Choice.runoff_score fields
- Return final winner and margin

### Result Generation
**Update `Tally.process()` method:**
- Generate comprehensive result report with topic inheritance chains
- Create Result record with detailed stats JSON including:
  - Vote counts and averages per choice
  - Topic inheritance tree showing delegation flows  
  - Tie-breaking decisions and rationale
  - Participation statistics (manual vs calculated ballots)

## Phase 3: Testing and Validation

### Management Command
**File: `democracy/management/commands/test_delegation.py`**
- Command to run complete delegation cycle on dummy data
- Generate test decisions with realistic topic distributions
- Execute StageBallots and Tally services
- Output detailed reports showing delegation chains and topic inheritance

### Simple Views for Testing
**File: `democracy/views.py`**
- `ballot_tree_view`: Display delegation calculation results 
- `tally_view`: Display final STAR voting results
- Simple templates to render service outputs (similar to old ballot_tree.html/tally.html)

## Technical Requirements

### Model Changes
```python
# New models to add
class Topic(BaseModel):
    name = models.CharField(max_length=50, unique=True)

class BallotTopic(BaseModel):
    ballot = models.ForeignKey(Ballot, ...)
    topic = models.ForeignKey(Topic, ...)
    inherited_from = models.ForeignKey(CustomUser, null=True, blank=True)

# Updates to existing models  
class Following(BaseModel):
    # ... existing fields ...
    topics = models.ManyToManyField(Topic, blank=True)
    order = models.PositiveIntegerField(help_text="Priority order for tie-breaking")
    
    class Meta:
        ordering = ['follower', 'order']
        unique_together = [('follower', 'followee')]
```

### Key Service Algorithms

**Topic Inheritance Logic:**
1. For voter V following user F on topics [T1, T2]
2. If F voted on decision D and tagged it with [T2, T3]  
3. Then V inherits F's vote and tag T2 (intersection of followed topics and decision tags)

**Tie-Breaking Logic:**
1. Calculate average stars for each choice from all inherited votes
2. If averages tie exactly, use Following.order (lower number = higher priority)
3. Record tie-breaking decision in audit log

**Audit Trail Requirements:**
- Track every vote inheritance with source user and topic
- Record all tag inheritances with delegation path
- Log all tie-breaking decisions with rationale
- Maintain complete transparency for verification

## Success Criteria

1. **Working delegation calculation** that processes all community members
2. **Topic-based vote inheritance** showing realistic delegation chains  
3. **Complete audit trail** in ballot_tree output showing who followed whom on which topics
4. **STAR voting results** with proper scoring and runoff phases
5. **Realistic test data** with varied topic following patterns and manual votes

## Notes

- Build on existing StageBallots/Tally service structure
- Maintain backward compatibility with current Following relationships (add topics gradually)
- Focus on transparency and auditability in all calculations
- Use existing ballot_tree_log pattern for detailed delegation reporting
