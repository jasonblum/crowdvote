# Change 0010: Fix Signal Duplication and Database Connection Exhaustion

## Problem Statement

CrowdVote's signal system is spawning multiple threads per user action, causing:
1. **Database connection exhaustion**: "FATAL: sorry, too many clients already" errors
2. **Perpetual spinner**: Global processing indicator spins constantly even when no calculations are active
3. **Performance degradation**: 2-3x more background threads than necessary

### Root Causes Identified

1. **Duplicate Signal Handlers on Ballot Model**
   - `ballot_changed` (line 167) fires on ALL ballot saves
   - `ballot_tags_changed` (line 391) ALSO fires on ALL ballot saves
   - Result: Every ballot action spawns 2 threads instead of 1

2. **Broken Tag Change Detection Logic**
   - `ballot_tags_changed` attempts to detect tag changes by re-fetching the ballot from database
   - Logic fails because it fetches AFTER the save completes, so old and new values are identical
   - Signal fires on every ballot update regardless of whether tags actually changed
   - Code at democracy/signals.py:409-411

3. **Potential Stuck Snapshots**
   - Snapshots stuck in `['creating', 'ready', 'staging', 'tallying']` states never reach 'completed'
   - Global indicator polls these statuses and shows spinner as long as any exist
   - No timeout mechanism to mark stale snapshots as failed

4. **Aggressive Polling**
   - base.html:620-624 polls `/status/global-calculations/` every 5 seconds continuously
   - Each poll makes database queries via crowdvote/views.py:114-229
   - Contributes to connection pool pressure

## Expected Behavior: TTEs (Tally-Triggering Events)

CrowdVote defines exactly **5 Tally-Triggering Events** that should spawn calculations:

| TTE | User Action | Expected Threads | Current Threads | File/Signal |
|-----|-------------|------------------|-----------------|-------------|
| 1. Voting | Cast or update ballot | 1 | **2-3** ❌ | signals.py:167,391 |
| 2. Following | Follow another member | 1 | 1 ✓ | signals.py:248 |
| 3. Unfollowing | Unfollow a member | 1 | 1 ✓ | signals.py:291 |
| 4. Tag Change | Modify following tags | 1 | 1 ✓ | signals.py:248 |
| 5. ALL Tags Switch | Toggle specific↔all tags | 1 | 1 ✓ | signals.py:248 |

**Critical Requirement**: Each TTE should spawn exactly ONE background thread that:
1. Runs `recalculate_community_decisions_async` (signals.py:38)
2. Creates one snapshot per open decision
3. Stages ballots and tallies results
4. Closes database connection in `finally` block
5. Completes within 2-5 seconds for typical demo data

**Global Spinner Behavior**: Should spin ONLY while background threads are actively processing:
- Blue spinning: Active calculations (snapshots in 'creating', 'staging', 'tallying')
- Gray static: No active calculations
- Stops spinning when snapshot reaches 'completed' status

## Files Requiring Changes

### Primary Changes
- `democracy/signals.py` - Remove duplicate signal, add validation logging
- `democracy/management/commands/check_stuck_snapshots.py` - New diagnostic command
- `democracy/models.py` - Add snapshot timeout method
- `crowdvote/templates/base.html` - Optimize polling frequency

### Supporting Changes
- `democracy/tests/test_signals.py` - Add tests for single-thread-per-TTE
- `docker-compose.yml` - Already has max_connections=200 (keep as-is)

## Resolution Strategy

### Phase 1: Remove Duplicate Signal (Immediate Fix)

**File**: `democracy/signals.py`

1. **Delete `ballot_tags_changed` signal entirely** (lines 391-433)
   - This signal is redundant with `ballot_changed`
   - Its tag-change detection logic is broken
   - Ballot updates are already handled by `ballot_changed`

2. **Add thread spawn logging to remaining signals**:
   ```python
   # In each signal that spawns threads, add:
   thread_id = threading.get_ident()
   logger.info(f"[THREAD_SPAWN] TTE='{trigger_event}' THREAD_ID={thread_id} COMMUNITY={community.name}")
   ```

3. **Add signal registration check**:
   ```python
   # At module level, add validation:
   def validate_signal_registration():
       """Ensure no duplicate signals registered."""
       ballot_receivers = post_save._live_receivers(Ballot)
       logger.info(f"[SIGNAL_CHECK] Ballot post_save has {len(ballot_receivers)} receivers")
   ```

### Phase 2: Add Snapshot Timeout Mechanism

**File**: `democracy/models.py` - Add to `DecisionSnapshot` model:

```python
@classmethod
def mark_stuck_snapshots_as_failed(cls, timeout_minutes=10):
    """
    Find snapshots stuck in processing states and mark them as failed.
    
    Args:
        timeout_minutes: How long before considering snapshot stuck
        
    Returns:
        int: Number of snapshots marked as failed
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)
    stuck_snapshots = cls.objects.filter(
        calculation_status__in=['creating', 'staging', 'tallying'],
        created_at__lt=cutoff_time
    )
    
    count = stuck_snapshots.count()
    stuck_snapshots.update(
        calculation_status='failed_timeout',
        error_log='Calculation timed out after {} minutes'.format(timeout_minutes),
        last_error=timezone.now()
    )
    
    return count
```

**File**: `democracy/management/commands/check_stuck_snapshots.py` - New command:

```python
"""
Management command to diagnose and optionally fix stuck snapshots.

Usage:
  python manage.py check_stuck_snapshots              # Diagnose only
  python manage.py check_stuck_snapshots --fix        # Mark as failed
  python manage.py check_stuck_snapshots --timeout 5  # Custom timeout
"""
```

### Phase 3: Optimize Global Spinner Polling

**File**: `crowdvote/templates/base.html` - Line 620-624:

Current (problematic):
```javascript
const constantPollInterval = setInterval(() => {
    if (!isPolling && !pollingTimeout) {
        pollGlobalStatus();
    }
}, 5000); // Poll every 5 seconds
```

Proposed:
```javascript
// Only poll when necessary - adaptive polling
let pollInterval = 10000; // Start at 10 seconds

const constantPollInterval = setInterval(() => {
    if (!isPolling && !pollingTimeout) {
        pollGlobalStatus();
    }
}, pollInterval); // Use dynamic interval
```

**File**: `democracy/models.py` - Update DecisionSnapshot choices:

Add new status:
```python
('failed_timeout', 'Calculation Timed Out'),
```

## Debugging and Validation

### Debugging Steps

**1. Check Current Signal Registration**:
```bash
docker-compose exec web python manage.py shell
>>> from django.db.models.signals import post_save
>>> from democracy.models import Ballot
>>> receivers = post_save._live_receivers(Ballot)
>>> for r in receivers:
...     print(f"Receiver: {r}")
```

**Expected**: Should see 2 receivers before fix, 1 after fix

**2. Monitor Thread Spawning**:
```bash
# Watch logs in real-time
docker-compose logs -f web | grep "THREAD_SPAWN\|ASYNC_RECALC_TRIGGERED"
```

**Expected output per TTE**:
```
[THREAD_SPAWN] TTE='ballot_cast' THREAD_ID=140562856827776 COMMUNITY=Minion Collective
[ASYNC_RECALC_TRIGGERED] [system] - Background recalculation started for community Minion Collective
```

Should see EXACTLY 1 pair per user action.

**3. Find Stuck Snapshots**:
```bash
docker-compose exec web python manage.py check_stuck_snapshots
```

**Expected output**:
```
🔍 Checking for stuck snapshots...
Found 3 stuck snapshots:
  - Decision "Banana Budget" (staging, 45 minutes old)
  - Decision "World Domination" (tallying, 2 hours old)
  - Decision "Lair Location" (creating, 1 day old)

Run with --fix to mark these as failed.
```

**4. Monitor Database Connections**:
```bash
docker-compose exec db psql -U postgres -d crowdvote_dev -c "SELECT count(*) FROM pg_stat_activity WHERE datname='crowdvote_dev';"
```

**Expected**: Should stay under 20 connections during normal operation (max is 200)

**5. Test Global Spinner State**:
```javascript
// In browser console on any page
fetch('/status/global-calculations/')
  .then(r => r.json())
  .then(data => console.log(data))
```

**Expected output (when idle)**:
```json
{
  "has_active_calculations": false,
  "has_recent_activity": false,
  "decisions": []
}
```

### Validation Tests

**Test 1: Single Ballot Cast**
```bash
# Start with clean logs
docker-compose logs -f web > /tmp/crowdvote.log &

# In browser: Login, navigate to decision, cast ballot

# Check logs
grep -c "ASYNC_RECALC_TRIGGERED" /tmp/crowdvote.log
```
✅ **PASS**: Count should be exactly 1
❌ **FAIL**: Count is 2 or more

**Test 2: Follow Member**
```bash
# Clear logs
docker-compose restart web

# In browser: Follow a member on specific tags

# Check logs  
docker-compose logs web | grep "FOLLOWING_STARTED\|ASYNC_RECALC_TRIGGERED"
```
✅ **PASS**: See 1 FOLLOWING_STARTED + 1 ASYNC_RECALC_TRIGGERED
❌ **FAIL**: See multiple ASYNC_RECALC_TRIGGERED

**Test 3: Unfollow Member**
```bash
# In browser: Unfollow the member

# Check logs
docker-compose logs web | grep "FOLLOWING_DELETED\|ASYNC_RECALC_TRIGGERED"
```
✅ **PASS**: See 1 FOLLOWING_DELETED + 1 ASYNC_RECALC_TRIGGERED
❌ **FAIL**: Multiple recalculation triggers

**Test 4: Global Spinner Behavior**
```bash
# Start calculation
# Cast ballot in browser

# Watch spinner in top-right corner:
# 1. Should turn blue and spin immediately
# 2. Hover over it - should show "Currently Processing"
# 3. Wait 2-5 seconds
# 4. Should turn gray and stop spinning
# 5. Hover - should show "Recent Activity (24h)"
```
✅ **PASS**: Spinner follows above sequence
❌ **FAIL**: Spinner keeps spinning indefinitely

**Test 5: Database Connection Stability**
```bash
# Run stress test: cast 20 ballots rapidly
for i in {1..20}; do
  # Cast ballot in browser
  sleep 1
done

# Check for errors
docker-compose logs web | grep "too many clients"
```
✅ **PASS**: No "too many clients" errors
❌ **FAIL**: See connection errors

**Test 6: Stuck Snapshot Cleanup**
```bash
# Check for stuck snapshots
docker-compose exec web python manage.py check_stuck_snapshots

# If found, mark them as failed
docker-compose exec web python manage.py check_stuck_snapshots --fix

# Verify spinner stops
# Visit any page, check that spinner is gray/static
```
✅ **PASS**: Stuck snapshots marked as failed, spinner stops
❌ **FAIL**: Spinner still spinning after cleanup

## Success Criteria

### Functional Requirements
1. ✅ Each TTE spawns exactly 1 background thread
2. ✅ No duplicate signal handlers on Ballot model
3. ✅ Global spinner accurately reflects calculation state
4. ✅ Spinner stops within 10 seconds of calculation completing
5. ✅ Stuck snapshots auto-timeout after 10 minutes

### Performance Requirements
1. ✅ Database connections stay under 50 during normal operation
2. ✅ No "too many clients" errors under any user load
3. ✅ Ballot submission completes in <1 second (user-facing)
4. ✅ Background calculation completes in 2-5 seconds (demo data)

### Monitoring Requirements
1. ✅ Thread spawn events logged with TTE identifier
2. ✅ Connection close events logged in background threads
3. ✅ Management command available to diagnose stuck snapshots
4. ✅ Clear log patterns for each TTE type

## Rollback Plan

If issues arise after deploying these changes:

1. **Immediate**: Revert `democracy/signals.py` to restore `ballot_tags_changed`
2. **Temporary fix**: Disable automatic recalculation by commenting out signal receivers
3. **Manual fallback**: Use `python manage.py stage_snapshot_and_tally_ballots` to calculate on demand

## Additional Issue Discovered During Testing

### Infinite Cascade from Calculated Ballots

**Problem**: Following a user triggered an infinite cascade creating 471+ snapshots instead of 2.

**Root Cause**: 
- `ballot_changed` signal fires on ALL ballot saves (both manual and calculated)
- When user follows someone → triggers recalculation
- Recalculation calculates inherited ballots and SAVES them to database
- Those ballot saves trigger `ballot_changed` signal again
- New signal spawns another thread → calculates more ballots → saves them → triggers signal
- **Infinite loop!**

**Solution**: Modified `ballot_changed` and `ballot_deleted` signals to ignore calculated ballots:

```python
@receiver(post_save, sender=Ballot)
def ballot_changed(sender, instance, created, **kwargs):
    # CRITICAL: Ignore calculated ballots to prevent infinite cascade
    if instance.is_calculated:
        logger.debug(f"[BALLOT_CALCULATED_SKIP] - Skipping recalculation for calculated ballot")
        return
    # ... rest of signal handler
```

**Result**: Only manual ballots (user-cast votes) trigger recalculation. Calculated ballots created during delegation processing do not spawn new threads.

---

## Future Enhancements (Out of Scope)

- Celery/Redis task queue for better background job management
- Rate limiting on signal triggers to prevent rapid-fire recalculations
- Snapshot deduplication (skip if identical snapshot created <30 seconds ago)
- Real-time WebSocket updates instead of polling for spinner state

