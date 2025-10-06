# Feature 0021: Snapshot Isolation for Vote Calculation System

## Overview

**CRITICAL BUG FIX**: The current vote calculation system in `democracy/services.py` has a fundamental flaw where it processes live database data during multi-minute calculations. This creates race conditions where users can vote, follow, or join communities while calculations are running, leading to **inconsistent and incorrect democratic results**. This plan implements proper snapshot isolation to ensure calculation integrity.

## The Critical Problem

### Current Broken Behavior:
1. **Stage Ballots process starts** (could run 2-10 minutes for large communities)
2. **User votes during calculation** → Live `Ballot.objects.get_or_create()` picks up new vote
3. **User follows someone during calculation** → Live `followings.select_related()` picks up new relationship
4. **User joins community during calculation** → Live `memberships.all()` includes new member
5. **Results are calculated using MIXED data** - some from start time, some from current time
6. **Democratic outcomes are wrong and unpredictable**

### Specific Code Issues in `services.py`:

**Line 208**: `Ballot.objects.get_or_create(decision=decision, voter=voter)`
- **Problem**: Creates ballots using live database state during calculation
- **Impact**: New votes cast during processing affect results inconsistently

**Line 258**: `ballot.voter.followings.select_related("followee").order_by("order")`
- **Problem**: Queries live following relationships during calculation
- **Impact**: Delegation changes during processing create inconsistent inheritance

**Line 558**: `for membership in community.memberships.all()`
- **Problem**: Iterates over live membership data
- **Impact**: New members joining during calculation may or may not be included

**Line 291**: `followee_ballot = self.get_or_calculate_ballot(decision, following.followee, follow_path.copy(), delegation_depth + 1)`
- **Problem**: Recursive calls use live data at different time points
- **Impact**: Deep delegation chains use inconsistent snapshots

## Solution: Atomic Snapshot Isolation

### Core Principle:
**All calculation must work from a single point-in-time snapshot taken at the start of processing. No live database queries during calculation.**

### Implementation Strategy:

#### 1. **Snapshot Data Structure**
```python
class CalculationSnapshot:
    """
    Point-in-time snapshot of all data needed for vote calculation.
    Ensures consistent results even during long-running calculations.
    """
    def __init__(self, communities=None, decisions=None):
        self.timestamp = timezone.now()
        self.communities_data = {}  # {community_id: community_snapshot}
        self.decisions_data = {}    # {decision_id: decision_snapshot}
        self.memberships_data = {}  # {community_id: [member_ids]}
        self.followings_data = {}   # {follower_id: [following_relationships]}
        self.existing_ballots = {}  # {(decision_id, voter_id): ballot_data}
        self.existing_votes = {}    # {ballot_id: [vote_data]}
```

#### 2. **Snapshot Creation Process**
```python
def create_calculation_snapshot(communities=None, decisions=None):
    """
    Create atomic snapshot of all calculation-relevant data.
    
    This function must complete quickly (< 5 seconds) and capture:
    - All community memberships
    - All following relationships with tags and priorities
    - All existing ballots and votes
    - All decision and choice data
    
    Returns CalculationSnapshot object with immutable data.
    """
```

#### 3. **Snapshot-Based Calculation**
```python
def get_or_calculate_ballot_from_snapshot(snapshot, decision_id, voter_id, follow_path=None):
    """
    Calculate ballot using ONLY snapshot data - no live database queries.
    
    Args:
        snapshot: CalculationSnapshot with all needed data
        decision_id: Decision UUID
        voter_id: Voter UUID  
        follow_path: List of voter IDs to prevent circular delegation
        
    Returns:
        Calculated ballot data (not saved to database until end)
    """
```

#### 4. **Result Persistence**
```python
def persist_calculation_results(snapshot, calculated_results):
    """
    Save all calculated results to database.
    
    Uses database transaction to ensure either all results save or none do.
    """
```

## Detailed Implementation Plan

### Phase 1: Snapshot Infrastructure

**New File: `democracy/snapshot.py`**
- `CalculationSnapshot` class with all snapshot data structures
- `create_calculation_snapshot()` function with optimized queries
- `validate_snapshot_consistency()` for debugging
- Comprehensive docstrings and error handling

**Enhanced File: `democracy/services.py`**
- Add `use_snapshot=False` parameter to existing methods for backward compatibility
- Create new snapshot-based calculation methods
- Add snapshot validation and consistency checks

### Phase 2: Snapshot-Based Calculation Engine

**Core Changes to `StageBallots.process()`:**
1. **Start**: Create snapshot of all relevant data (< 5 seconds)
2. **Calculate**: Use only snapshot data for all ballot calculations
3. **Persist**: Save results to database
4. **Log**: Record snapshot timestamp and calculation duration

**New Method: `StageBallots.process_with_snapshot()`:**
- Creates calculation snapshot at start
- Processes all decisions using snapshot data only
- Returns detailed calculation report with timing

### Phase 3: Error Handling & Recovery

**Critical Failure Scenarios & Recovery:**

#### **Scenario 1: Snapshot Creation Fails**
```python
def create_calculation_snapshot(decision):
    snapshot = CalculationSnapshot.objects.create(
        decision=decision,
        calculation_status='creating'
    )
    
    try:
        # Capture all data in single transaction
        with transaction.atomic():
            snapshot_data = {
                'community_memberships': list(decision.community.memberships.values_list('member_id', flat=True)),
                'followings': dict(Following.objects.filter(...).values()),
                'existing_ballots': dict(Ballot.objects.filter(decision=decision).values()),
                'existing_votes': dict(Vote.objects.filter(ballot__decision=decision).values()),
                # ... other data
            }
            
            # Validate snapshot integrity
            validate_snapshot_data(snapshot_data)
            
            snapshot.snapshot_data = snapshot_data
            snapshot.calculation_status = 'ready'
            snapshot.save()
            
    except Exception as e:
        snapshot.calculation_status = 'failed_snapshot'
        snapshot.error_log = f"Snapshot creation failed: {str(e)}\n{traceback.format_exc()}"
        snapshot.last_error = timezone.now()
        snapshot.save()
        
        # Log critical error
        logger.error(f"CRITICAL: Snapshot creation failed for decision {decision.id}: {e}")
        raise SnapshotCreationError(f"Failed to create snapshot: {e}")
```

#### **Scenario 2: Stage Ballots Fails Mid-Process**
```python
def process_with_snapshot(self, snapshot):
    try:
        snapshot.calculation_status = 'staging'
        snapshot.save()
        
        # Process each member with checkpoint logging
        for i, member_id in enumerate(snapshot.snapshot_data['community_memberships']):
            try:
                ballot = self.get_or_calculate_ballot_from_snapshot(snapshot, member_id)
                
                # Checkpoint every 100 members
                if i % 100 == 0:
                    logger.info(f"Stage Ballots progress: {i}/{len(members)} members processed")
                    
            except Exception as e:
                # Log individual member failure but continue
                logger.warning(f"Failed to process member {member_id}: {e}")
                continue
                
        snapshot.calculation_status = 'tallying'
        snapshot.save()
        
    except Exception as e:
        snapshot.calculation_status = 'failed_staging'
        snapshot.error_log = f"Stage Ballots failed: {str(e)}\n{traceback.format_exc()}"
        snapshot.last_error = timezone.now()
        snapshot.retry_count += 1
        snapshot.save()
        
        logger.error(f"CRITICAL: Stage Ballots failed for snapshot {snapshot.id}: {e}")
        raise StagingError(f"Stage Ballots failed: {e}")
```

#### **Scenario 3: Tally Fails After Staging Succeeds**
```python
def tally_from_snapshot(self, snapshot):
    try:
        if snapshot.calculation_status != 'tallying':
            raise ValueError(f"Snapshot not ready for tally: {snapshot.calculation_status}")
            
        # Use snapshot results_data from staging
        ballots_data = snapshot.results_data.get('calculated_ballots', {})
        
        # Perform STAR voting calculations
        star_results = self.calculate_star_voting(ballots_data)
        
        # Save results atomically
        with transaction.atomic():
            snapshot.results_data.update({
                'star_results': star_results,
                'tally_completed': timezone.now().isoformat()
            })
            snapshot.calculation_status = 'completed'
            snapshot.calculation_duration = timezone.now() - snapshot.timestamp
            snapshot.save()
            
    except Exception as e:
        snapshot.calculation_status = 'failed_tallying'
        snapshot.error_log += f"\nTally failed: {str(e)}\n{traceback.format_exc()}"
        snapshot.last_error = timezone.now()
        snapshot.retry_count += 1
        snapshot.save()
        
        logger.error(f"CRITICAL: Tally failed for snapshot {snapshot.id}: {e}")
        raise TallyError(f"Tally failed: {e}")
```

#### **Scenario 4: Network/Database Connectivity Loss**
```python
def robust_calculation_with_retries(decision, max_retries=3):
    """
    Perform calculation with automatic retry on transient failures.
    """
    for attempt in range(max_retries):
        try:
            snapshot = create_calculation_snapshot(decision)
            stage_service = StageBallots()
            stage_service.process_with_snapshot(snapshot)
            
            tally_service = Tally()
            tally_service.tally_from_snapshot(snapshot)
            
            return snapshot  # Success!
            
        except (DatabaseError, ConnectionError, TimeoutError) as e:
            logger.warning(f"Transient error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                logger.error(f"CRITICAL: All {max_retries} attempts failed for decision {decision.id}")
                raise
                
        except (SnapshotCreationError, StagingError, TallyError) as e:
            logger.error(f"CRITICAL: Non-retryable error: {e}")
            raise
```

#### **Scenario 5: Snapshot Corruption Detection**
```python
def validate_snapshot_data(snapshot_data):
    """
    Validate snapshot data integrity before processing.
    """
    required_keys = ['community_memberships', 'followings', 'existing_ballots', 'existing_votes']
    
    for key in required_keys:
        if key not in snapshot_data:
            raise SnapshotCorruptionError(f"Missing required key: {key}")
    
    # Validate data consistency
    member_count = len(snapshot_data['community_memberships'])
    if member_count == 0:
        raise SnapshotCorruptionError("No community members found")
        
    # Validate following relationships reference valid members
    for follower_id, followings in snapshot_data['followings'].items():
        if follower_id not in snapshot_data['community_memberships']:
            logger.warning(f"Following relationship for non-member: {follower_id}")
            
    logger.info(f"Snapshot validation passed: {member_count} members, {len(snapshot_data['followings'])} following relationships")
```

### Phase 4: Recovery & Monitoring

**Automatic Recovery Strategies:**

#### **Failed Snapshot Recovery:**
```python
def recover_failed_snapshots():
    """
    Automatic recovery for failed snapshots (run via management command).
    """
    failed_snapshots = CalculationSnapshot.objects.filter(
        calculation_status__in=['failed_snapshot', 'failed_staging', 'failed_tallying'],
        retry_count__lt=3,
        last_error__lt=timezone.now() - timedelta(minutes=30)  # Wait 30 min before retry
    )
    
    for snapshot in failed_snapshots:
        try:
            logger.info(f"Attempting recovery for snapshot {snapshot.id}")
            
            if snapshot.calculation_status == 'failed_snapshot':
                # Recreate snapshot
                new_snapshot = create_calculation_snapshot(snapshot.decision)
                snapshot.delete()  # Remove failed snapshot
                
            elif snapshot.calculation_status == 'failed_staging':
                # Retry staging with existing snapshot
                stage_service = StageBallots()
                stage_service.process_with_snapshot(snapshot)
                
            elif snapshot.calculation_status == 'failed_tallying':
                # Retry tally with existing results
                tally_service = Tally()
                tally_service.tally_from_snapshot(snapshot)
                
        except Exception as e:
            logger.error(f"Recovery failed for snapshot {snapshot.id}: {e}")
            snapshot.retry_count += 1
            snapshot.last_error = timezone.now()
            snapshot.error_log += f"\nRecovery attempt {snapshot.retry_count} failed: {e}"
            snapshot.save()
```

#### **Corruption Detection & Cleanup:**
```python
def detect_corrupted_snapshots():
    """
    Detect and mark corrupted snapshots for manual review.
    """
    suspicious_snapshots = CalculationSnapshot.objects.filter(
        calculation_status='staging',
        timestamp__lt=timezone.now() - timedelta(hours=2)  # Stuck for 2+ hours
    )
    
    for snapshot in suspicious_snapshots:
        logger.warning(f"Marking snapshot {snapshot.id} as potentially corrupted")
        snapshot.calculation_status = 'corrupted'
        snapshot.error_log += f"\nMarked as corrupted: stuck in staging for >2 hours"
        snapshot.save()
```

**Monitoring & Alerting:**

#### **Health Check Endpoint:**
```python
def snapshot_health_check():
    """
    Health check for snapshot system (for monitoring tools).
    """
    failed_count = CalculationSnapshot.objects.filter(
        calculation_status__in=['failed_snapshot', 'failed_staging', 'failed_tallying']
    ).count()
    
    corrupted_count = CalculationSnapshot.objects.filter(
        calculation_status='corrupted'
    ).count()
    
    stuck_count = CalculationSnapshot.objects.filter(
        calculation_status__in=['creating', 'staging', 'tallying'],
        timestamp__lt=timezone.now() - timedelta(hours=1)
    ).count()
    
    return {
        'status': 'healthy' if failed_count + corrupted_count + stuck_count == 0 else 'degraded',
        'failed_snapshots': failed_count,
        'corrupted_snapshots': corrupted_count,
        'stuck_snapshots': stuck_count,
        'total_snapshots': CalculationSnapshot.objects.count()
    }
```

#### **Management Commands:**
- `python manage.py recover_failed_snapshots` - Automatic recovery
- `python manage.py validate_snapshots` - Check snapshot integrity
- `python manage.py snapshot_health` - System health report

### Phase 5: Performance Optimization

**Snapshot Creation Optimization:**
- Use `select_related()` and `prefetch_related()` for efficient queries
- Batch process large communities (>1000 members)
- Implement snapshot compression for storage
- Add progress indicators for large snapshot creation

**Memory Management:**
- Stream large snapshots to avoid memory issues
- Monitor memory usage during calculation
- Implement snapshot data pagination for very large communities

## Database Schema Changes

### Enhanced Model: `DecisionSnapshot` (Existing Model)

**Use Existing Model**: The codebase already has a comprehensive `DecisionSnapshot` model that's perfect for Plan #21. We'll enhance it with error handling and status tracking fields.

**New Fields to Add:**
```python
class DecisionSnapshot(BaseModel):
    # ... existing fields ...
    
    # NEW: Calculation status tracking
    calculation_status = models.CharField(
        max_length=20, 
        default='ready',
        choices=[
            ('creating', 'Creating Snapshot'),
            ('ready', 'Ready for Calculation'),
            ('staging', 'Stage Ballots in Progress'),
            ('tallying', 'Tally in Progress'),
            ('completed', 'Calculation Completed'),
            ('failed_snapshot', 'Snapshot Creation Failed'),
            ('failed_staging', 'Stage Ballots Failed'),
            ('failed_tallying', 'Tally Failed'),
            ('corrupted', 'Snapshot Corrupted')
        ],
        help_text="Current status of the calculation process"
    )
    
    # NEW: Error handling fields
    error_log = models.TextField(
        blank=True,
        help_text="Detailed error information and stack traces"
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of retry attempts for failed calculations"
    )
    last_error = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When the last error occurred"
    )
    
    # CRITICAL: Only one final snapshot per decision
    def clean(self):
        """
        Validate that only one DecisionSnapshot can have is_final=True per decision.
        """
        super().clean()
        
        if self.is_final:
            # Check if another final snapshot exists for this decision
            existing_final = DecisionSnapshot.objects.filter(
                decision=self.decision,
                is_final=True
            ).exclude(pk=self.pk)
            
            if existing_final.exists():
                raise ValidationError({
                    'is_final': 'Only one final snapshot is allowed per decision. '
                               f'Final snapshot already exists: {existing_final.first()}'
                })
    
    def save(self, *args, **kwargs):
        """Override save to enforce validation."""
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def create_final_snapshot(cls, decision):
        """
        Create the final snapshot for a decision, ensuring only one exists.
        
        This method handles the transition from interim to final snapshots
        when a decision closes.
        """
        # Mark any existing final snapshot as non-final (shouldn't happen, but safety)
        cls.objects.filter(decision=decision, is_final=True).update(is_final=False)
        
        # Create new final snapshot
        return cls.objects.create(
            decision=decision,
            is_final=True,
            calculation_status='ready'
        )
```

### Enhanced Model: `Decision`
```python
class Decision(BaseModel):
    # ... existing fields ...
    
    # New fields for snapshot tracking
    last_snapshot = models.ForeignKey(CalculationSnapshot, null=True, blank=True, related_name='latest_for_decision')
    calculation_in_progress = models.BooleanField(default=False)
    
    # New methods for snapshot management
    def get_latest_snapshot(self):
        """Get the most recent snapshot for this decision."""
        return self.snapshots.first()  # Uses related_name='snapshots'
    
    def get_final_snapshot(self):
        """Get the final snapshot for this decision (if it exists)."""
        return self.snapshots.filter(is_final=True).first()
```

## Testing Strategy

### Critical Test Scenarios:

**Test 1: Basic Snapshot Isolation**
- Create snapshot
- User votes during calculation
- Verify results don't include new vote
- Verify new vote triggers next calculation

**Test 2: Deep Delegation Consistency**
- Create complex delegation chain (A→B→C→D→E)
- Start calculation
- User changes delegation in middle of chain during calculation
- Verify calculation uses original delegation structure
- Verify changed delegation triggers new calculation

**Test 3: Large Community Performance**
- Generate community with 10,000+ members
- Measure snapshot creation time (must be < 30 seconds)
- Measure calculation time with snapshot
- Verify memory usage stays reasonable

**Test 4: Result Persistence**
- Start calculation with snapshot
- User manually votes during calculation
- Verify calculation completes with snapshot data
- Verify new vote triggers new calculation cycle

**Test 5: Final Snapshot Uniqueness**
- Create interim snapshot with `is_final=False`
- Create final snapshot with `is_final=True`
- Attempt to create second final snapshot
- Verify ValidationError is raised
- Verify only one final snapshot exists per decision

**Test 6: Concurrent Calculation Prevention**
- Start calculation
- Attempt to start second calculation
- Verify second calculation waits or fails gracefully
- Verify no race conditions

## Files to Create

**`democracy/snapshot.py` (New File):**
- `CalculationSnapshot` data class
- `create_calculation_snapshot()` function
- `validate_snapshot_consistency()` function
- Snapshot compression and serialization utilities
- Comprehensive error handling and logging

**`democracy/migrations/0013_add_calculation_snapshot.py` (New File):**
- Database migration for CalculationSnapshot model
- Add snapshot tracking fields to Decision model
- Create indexes for performance

**`tests/test_services/test_snapshot_isolation.py` (New File):**
- Comprehensive test suite for snapshot functionality
- Race condition testing
- Performance benchmarking
- Conflict resolution validation

## Files to Modify

**`democracy/services.py`:**
- Add snapshot-based calculation methods
- Maintain backward compatibility with existing methods
- Add conflict detection and resolution
- Enhanced error handling and logging

**`democracy/models.py`:**
- Enhance existing `DecisionSnapshot` model with error handling fields
- Add calculation status tracking and error logging
- Add validation for final snapshot uniqueness
- **FIX**: Move `get_latest_for_decision` and `get_final_for_decision` methods from `DecisionSnapshot` to `Decision` model
- Add proper `get_latest_snapshot()` and `get_final_snapshot()` methods to `Decision` model
- Update model methods for snapshot management

**`democracy/admin.py`:**
- Enhance existing DecisionSnapshot admin interface with comprehensive filtering
- Add filtering by decision (in addition to existing community filtering)
- Add snapshot monitoring dashboard showing failed/corrupted snapshots
- Add "Retry Failed Calculation" admin action
- Add "Mark as Corrupted" admin action for manual intervention
- Display calculation status, error logs, and retry counts
- Add snapshot data validation tools for debugging
- Add list display for decision title, community, calculation status, and timestamps

## Success Criteria

### Functional Requirements:
1. **Calculation Consistency**: Results identical regardless of user activity during calculation
2. **Snapshot Isolation**: All calculations use single point-in-time data
3. **Performance**: Snapshot creation < 30 seconds for 10,000 member communities
4. **Reliability**: Zero data corruption under concurrent user activity

### Technical Requirements:
1. **Atomic Operations**: All database updates in transactions
2. **Memory Efficiency**: Reasonable memory usage for large snapshots
3. **Error Handling**: Graceful handling of all failure scenarios
4. **Audit Trail**: Complete logging of all snapshot operations

### Testing Requirements:
1. **100% Test Coverage**: All snapshot functionality thoroughly tested
2. **Race Condition Testing**: Concurrent user activity scenarios
3. **Performance Testing**: Large community benchmarking
4. **Stress Testing**: Extended calculation periods with high user activity

## Implementation Priority

**This is a CRITICAL BUG FIX that must be completed before any other vote calculation work.**

The current system produces incorrect democratic results under normal user activity. This undermines the entire purpose of CrowdVote and must be fixed immediately.

**Estimated Implementation Time**: 2-3 development sessions
**Risk Level**: High (fundamental architecture change)
**Impact**: Critical (fixes incorrect democratic outcomes)

## Migration Strategy

### Phase 1: Implement Snapshot System
- Create snapshot infrastructure
- Add snapshot-based calculation methods
- Maintain existing methods for backward compatibility

### Phase 2: Testing & Validation
- Comprehensive test suite
- Performance benchmarking
- Race condition validation

### Phase 3: Production Deployment
- Switch to snapshot-based calculations
- Monitor for conflicts and performance
- Remove old calculation methods after validation

This plan addresses the fundamental flaw in the current vote calculation system and ensures CrowdVote produces accurate, consistent democratic results regardless of user activity during processing.
