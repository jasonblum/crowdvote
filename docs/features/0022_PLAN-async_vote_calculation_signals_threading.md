# Feature 0022: Asynchronous Vote Calculation with Django Signals & Threading

## Overview

Implement real-time vote calculation using Django signals and background threading to automatically recalculate results whenever system changes occur (votes, follows, community membership). This eliminates the need for manual `run_crowdvote_demo` commands and provides immediate user feedback with background processing for optimal user experience.

## Context & Current State

**IMPLEMENTATION STATUS: COMPLETED ✅** (September 15, 2025)

**UPDATED POST-PLAN #21**: Plan #21 successfully implemented snapshot isolation for vote calculations, creating the `CreateCalculationSnapshot` and `SnapshotBasedStageBallots` services. Plan #22 has been fully implemented and tested with the following status: by the end of the day or a couple days equally you know we made

✅ **Snapshot-Based Calculation**: All calculations use point-in-time snapshots for consistency
✅ **Error Handling**: Comprehensive error tracking with `calculation_status`, `error_log`, `retry_count` 
✅ **DecisionSnapshot Model**: Enhanced with status tracking and validation
✅ **Production-Ready Services**: `CreateCalculationSnapshot` and `SnapshotBasedStageBallots` services
✅ **Comprehensive Testing**: 29 tests covering snapshot functionality (Plan #21)
✅ **525 Total Tests**: 100% success rate with existing test infrastructure

Currently, vote calculation still requires manually running `python manage.py run_crowdvote_demo` which calls the snapshot-based services. Users vote but don't see updated results until someone manually triggers recalculation. This creates a poor user experience and prevents real-time democracy.

The heavy lifting is complete in `democracy/services.py` with snapshot isolation - we now need to trigger these snapshot-based services automatically when system state changes.

### How Current Vote Calculation Works (Post-Plan #21)

**1. Ballot Staging Process (`StageBallots` + `SnapshotBasedStageBallots`)**:
- **`get_or_calculate_ballot()`**: Core recursive function that handles delegation inheritance
- **Delegation Algorithm**: Users inherit votes from people they follow based on tag matching
- **Tag Inheritance**: Both votes AND tags flow through delegation networks
- **Circular Prevention**: `follow_path` parameter prevents infinite delegation loops
- **Priority Ordering**: Lower `order` values = higher priority for tie-breaking
- **Comprehensive Logging**: Detailed `ballot_tree_log` tracks every delegation decision

**2. STAR Voting Process (`Tally` service)**:
- **Score Phase (S)**: Calculate average star ratings for each choice
- **Automatic Runoff (AR)**: Top 2 choices compete based on voter preferences
- **Participation Filtering**: Only voting members count (excludes lobbyists)
- **Detailed Logging**: Complete `tally_log` with participation stats and calculations

**3. Service Idempotency (Critical for Plan #22)**:
- **Safe to Run Multiple Times**: All services can be called repeatedly without corruption
- **Existing Ballot Handling**: `get_or_create()` prevents duplicate ballot creation
- **Vote Replacement**: Calculated votes are deleted and recalculated each time
- **Status Tracking**: `DecisionSnapshot.calculation_status` prevents concurrent calculations

## Technical Requirements

### 1. Django Signals System

**File: `democracy/signals.py` (new)**

Create signals to detect the 6 trigger events that require recalculation:

1. **Vote cast/updated** (`Vote` model post_save)
2. **Follow someone** (`Following` model post_save) 
3. **Unfollow someone** (`Following` model post_delete)
4. **Follow tags changed** (`Following` model post_save with field changes)
5. **Community membership changes** (`Membership` model post_save/post_delete)
6. **Ballot tags updated** (`Ballot` model post_save with tag changes)

**Signal Functions (Updated for Plan #21 Snapshot Integration):**
- `recalculate_community_decisions_async(community_id)` - Background thread function that calls `CreateCalculationSnapshot` and `SnapshotBasedStageBallots` services for all open decisions in specified community
- `vote_changed(sender, instance, created, **kwargs)` - Triggered when Vote is saved/updated/deleted
- `following_changed(sender, instance, **kwargs)` - Triggered when Following is created/deleted/modified
- `membership_changed(sender, instance, **kwargs)` - Triggered when Membership is created/deleted
- `ballot_tags_changed(sender, instance, **kwargs)` - Triggered when Ballot tags are modified

**When Functions Are Called:**
- `recalculate_community_decisions_async()`: Called by all signal handlers in background thread with specific community_id
- `vote_changed()`: Every time a user votes, updates, or deletes their vote → Recalculates all open decisions in the community where the vote was cast
- `following_changed()`: When user follows/unfollows someone or changes delegation tags → Recalculates all open decisions in communities where the follower is a member
- `membership_changed()`: When someone joins/leaves a community → Recalculates all open decisions in that specific community
- `ballot_tags_changed()`: When vote tags are modified on existing ballot → Recalculates all open decisions in the community where the ballot exists

**Community-Scoped Recalculation:**
All trigger events result in community-scoped recalculation only. Membership, delegation, and votes are community-local, so changes in one community do not affect decisions in other communities.

### 2. Background Threading Implementation

**Threading Strategy:**
- Use `threading.Thread` with `daemon=True` for background processing
- Pass only `decision_id` to avoid serialization issues
- Include comprehensive logging for monitoring and debugging
- Graceful error handling that doesn't crash web requests

**Thread Safety:**
- Django database connections are thread-safe
- Services are already idempotent (safe to run multiple times)
- Use try/catch blocks to prevent thread crashes
- **Critical**: Services use `get_or_create()` and status tracking to prevent corruption

**How Django Signals Work:**
- **Signal Dispatch**: Django automatically calls registered signal handlers when model events occur
- **Synchronous by Default**: Signals run in the same request thread unless explicitly made async
- **Multiple Handlers**: Multiple functions can listen to the same signal
- **Signal Registration**: Must be registered in Django app's `ready()` method

**How Background Threading Works:**
- **Thread Creation**: `threading.Thread(target=function, args=(params,), daemon=True).start()`
- **Daemon Threads**: Automatically terminate when main process exits
- **Database Connections**: Each thread gets its own database connection
- **Error Isolation**: Thread exceptions don't crash the main web request
- **Resource Management**: Threads are lightweight and automatically cleaned up

### 3. Manual Manager Override

**File: `democracy/views.py`**

Add new view `recalculate_results(request, community_id, decision_id)`:
- Only accessible to community managers
- Uses same threading approach as signals
- Provides immediate feedback: "Recalculation started - results will update shortly"
- Accessible via button on decision detail and results pages

### 4. Real-Time UI Indicators

**HTMX Processing Indicators:**

**Decision Detail Page (`democracy/templates/democracy/decision_detail.html`):**
- Add spinning icon + "Calculating results..." to live results panel (left sidebar)
- Show/hide based on calculation status
- Update timestamp when calculation completes

**Decision Results Page (`democracy/templates/democracy/decision_results.html`):**
- Prominent processing indicator at top of results
- "Last calculated: [timestamp]" with "FINAL" indicator if decision is closed
- Auto-refresh results section when calculation completes

**Implementation:**
- Add `is_calculating` field to Decision model (or use cache-based status)
- HTMX polling to check calculation status every 5 seconds
- Replace spinner with completion timestamp + "FINAL" badge if `decision.dt_close < now()`

### 5. Enhanced User Messaging

**Updated Confirmation Messages:**
- **Vote submitted**: "Vote recorded! Results are being recalculated - watch the live stats panel for updates."
- **Follow/Unfollow**: "Following updated! Keep an eye on decision results as they recalculate based on your new delegation."
- **Community joined**: "Welcome to [Community]! Your participation will be reflected in all active decision results."

**Message Integration:**
- Update all relevant views (`vote_submit`, `follow_user`, `unfollow_user`, `apply_to_community`)
- Include instructions to watch for spinning indicator
- Mention approximate timing (30-60 seconds for large communities)

### 6. Calculation Status Tracking (Updated for Plan #21 Integration)

**Decision Model Enhancement:**
- Add `last_calculated` timestamp field
- Add `is_calculating` property method for UI status (based on DecisionSnapshot.calculation_status)
- Add `is_final_calculation` property (True if `dt_close < now()` and final snapshot exists)
- Track calculation status using existing DecisionSnapshot.calculation_status field

**Snapshot Integration (Already Implemented in Plan #21):**
✅ **DecisionSnapshot** already has `is_final` flag and comprehensive status tracking
✅ **Status Management**: 9 calculation states from 'creating' to 'completed' with failure modes  
✅ **Error Handling**: `calculation_status`, `error_log`, `retry_count`, `last_error` fields
✅ **Validation**: Only one final snapshot per decision with model-level validation

**New Requirements:**
- Display "FINAL RESULT" badge on results when decision is closed and final snapshot exists
- Show calculation history with timestamps using existing DecisionSnapshot records
- Add real-time status polling using DecisionSnapshot.calculation_status

### 7. System Event Logging (Enhanced from Current Basic Logging)

**Current State**: Basic console logging is configured in `crowdvote/settings.py` with verbose formatter.

**Enhanced Event Logging System:**
- **Log File Location**: `logs/crowdvote.log` (created automatically)
- **Log Format**: `[TIMESTAMP] [LEVEL] [EVENT_TYPE] [USER] - MESSAGE`
- **Log Rotation**: Daily rotation with 30-day retention
- **Integration**: Enhance existing logging configuration rather than replace

**Events to Log:**
1. **Community & Decision Events**:
   - Community creation: `[INFO] [COMMUNITY_CREATE] [admin_user] - Community 'Springfield' created`
   - Decision creation: `[INFO] [DECISION_CREATE] [manager_user] - Decision 'Budget Vote' created in Springfield`
   - Decision publishing: `[INFO] [DECISION_PUBLISH] [manager_user] - Decision 'Budget Vote' published, voting opens`

2. **Membership & Following Events**:
   - Membership changes: `[INFO] [MEMBERSHIP_CHANGE] [user] - Joined community 'Springfield' as Voter`
   - Following changes: `[INFO] [FOLLOWING_CHANGE] [user] - Now following alice_user on tags: budget,governance`
   - Unfollowing: `[INFO] [FOLLOWING_CHANGE] [user] - Stopped following alice_user`

3. **Voting & Calculation Events (Updated for Plan #21 Snapshot Integration)**:
   - Vote cast: `[INFO] [VOTE_CAST] [user] - Vote cast on decision 'Budget Vote'`
   - Signal triggered: `[INFO] [SIGNAL_TRIGGERED] [system] - vote_changed signal fired for decision 'Budget Vote'`
   - Background thread start: `[INFO] [THREAD_START] [system] - Starting background calculation thread for community 'Springfield'`
   - Snapshot creation start: `[INFO] [SNAPSHOT_CREATE_START] [system] - Creating snapshot for decision 'Budget Vote'`
   - Snapshot creation complete: `[INFO] [SNAPSHOT_CREATE_COMPLETE] [system] - Snapshot created successfully: {snapshot_id}`
   - Stage ballots start: `[INFO] [STAGE_BALLOTS_START] [system] - Starting snapshot-based ballot staging for decision 'Budget Vote'`
   - Delegation processing: `[DEBUG] [DELEGATION] [system] - Processing delegation: user_b follows user_a on tags: budget,governance`
   - Vote inheritance: `[DEBUG] [VOTE_INHERIT] [system] - user_b inherited 4.5 stars for choice_a from user_a`
   - Stage ballots complete: `[INFO] [STAGE_BALLOTS_COMPLETE] [system] - Snapshot-based staging completed in 4.2 seconds (247 ballots processed)`
   - Tally start: `[INFO] [TALLY_START] [system] - Starting STAR voting tally for snapshot {snapshot_id}`
   - Score phase: `[DEBUG] [STAR_SCORE] [system] - Choice A: 4.23 avg stars (89 votes), Choice B: 3.67 avg stars (89 votes)`
   - Runoff phase: `[DEBUG] [STAR_RUNOFF] [system] - Runoff: Choice A vs Choice B - Choice A wins 52 to 37`
   - Tally complete: `[INFO] [TALLY_COMPLETE] [system] - Tally completed in 1.8 seconds - Winner: Choice A`
   - Background thread complete: `[INFO] [THREAD_COMPLETE] [system] - Background calculation completed for community 'Springfield'`
   - Manual recalculation: `[INFO] [MANUAL_RECALC] [manager_user] - Manual recalculation triggered for decision 'Budget Vote'`
   - Calculation errors: `[ERROR] [CALCULATION_ERROR] [system] - Snapshot creation failed: {error_details}`

4. **Authentication Events**:
   - Login: `[INFO] [LOGIN] [user] - User logged in via magic link`
   - Logout: `[INFO] [LOGOUT] [user] - User logged out`
   - Failed login: `[WARNING] [LOGIN_FAILED] [anonymous] - Invalid magic link attempted`

5. **System Events**:
   - Signal processing errors: `[ERROR] [SIGNAL_ERROR] [system] - Failed to process vote_changed signal: [error details]`
   - Threading errors: `[ERROR] [THREAD_ERROR] [system] - Background calculation failed: [error details]`

**Implementation:**
- Enhance existing Django logging in `settings.py` with file handler (currently has console logging)
- Add logging calls to all signal handlers and background functions
- Create `logs/` directory with proper permissions
- Add log monitoring section to admin interface
- Integrate with existing logger configuration for 'accounts' and 'django' apps

### 8. Documentation Updates

**File: `crowdvote/templates/docs.html`**

Update the "How are votes calculated?" FAQ section to reflect the new signal-based approach:

**Current text to replace:**
> "CrowdVote uses a sophisticated two-stage vote calculation system powered by background cron jobs that automatically recalculate results whenever anything changes in the system."

**New text:**
> "CrowdVote uses a sophisticated two-stage vote calculation system powered by Django signals and background threading that automatically recalculate results in real-time whenever anything changes in the system."

**Additional updates:**
- Replace "cron jobs" references with "signal-based triggers"
- Add section about real-time processing indicators
- Mention typical calculation times (30-60 seconds)
- Explain final vs. interim calculation status

**File: `README.md`**

Add new section about system logging:

**New section to add after "Testing" section:**
```markdown
### System Logs

CrowdVote maintains comprehensive logs of all important system events for transparency and debugging.

#### Log Location
- **Development**: `logs/crowdvote.log`
- **Production**: Logs are written to the same location and should be monitored

#### What Gets Logged
- **Democratic Events**: Decision creation, publishing, vote casting, result calculations
- **Community Events**: Membership changes, community creation and management
- **Delegation Events**: Following/unfollowing relationships and tag changes
- **Authentication**: User logins, logouts, and authentication failures
- **System Events**: Background processing, errors, and performance metrics

#### Log Format
```
[2025-09-15 14:30:25] [INFO] [VOTE_CAST] [alice_user] - Vote cast on decision 'Springfield Budget 2025'
[2025-09-15 14:30:26] [INFO] [STAGE_BALLOTS_START] [system] - Staging ballots for 3 decisions across 2 communities
[2025-09-15 14:30:30] [INFO] [STAGE_BALLOTS_COMPLETE] [system] - Staged 247 ballots in 4.2 seconds
```

#### Monitoring
- Logs rotate daily with 30-day retention
- ERROR and WARNING level events should be monitored in production
- Log files can be analyzed for community engagement patterns and system performance
```

### 9. Comprehensive Testing & Logging Requirements (100% Coverage Target)

**CRITICAL REQUIREMENT**: All new code must include comprehensive testing AND logging of important events as specified by the user. Important events include:
- People joining or leaving communities
- Voting and delegation (following/unfollowing)
- Decisions being published or closed
- Stage ballots and tally beginning and ending
- Authentication events (login/logout)
- System errors and failures

**Testing Coverage Requirements:**

**New Test Files:**

**`tests/test_signals/test_vote_calculation_signals.py` (Target: 100% coverage):**
- Test all 6 trigger events properly fire signals with correct community scope
- Test `vote_changed` signal: Vote create/update/delete → community-scoped recalculation
- Test `following_changed` signal: Following create/delete/modify → follower's communities recalculated
- Test `membership_changed` signal: Membership create/delete → specific community recalculated
- Test `ballot_tags_changed` signal: Ballot tag updates → community-scoped recalculation
- Verify background threads are created with correct community_id (mock threading.Thread)
- Test signal handler error handling and logging
- Test signal registration in Django app configuration
- Test community scoping: changes in Community A don't trigger recalculation in Community B
- Test edge cases: deleted objects, invalid community IDs, concurrent signals

**`tests/test_views/test_manual_recalculation.py` (Target: 100% coverage):**
- Test manager-only access to manual recalculation endpoint
- Test non-manager access returns 403 Forbidden
- Test non-member access returns 403 Forbidden
- Test invalid community/decision IDs return 404
- Test successful recalculation starts background thread
- Test user feedback messages and redirects
- Test HTMX vs regular request handling
- Test permission checks with various user roles (manager, voter, lobbyist, non-member)

**`tests/test_integration/test_real_time_calculation.py` (Target: 100% coverage):**
- End-to-end test: vote → signal → background calculation → updated results
- Test complex delegation scenarios: multi-level chains, tag inheritance
- Test multiple simultaneous changes and proper community scoping
- Test calculation status tracking and timestamp updates
- Test UI indicator updates (mock HTMX responses)
- Test final vs interim calculation status
- Test calculation failure scenarios and error handling

**`tests/test_services/test_async_calculation.py` (Target: 100% coverage):**
- Test `recalculate_community_decisions_async` function directly
- Test `CreateCalculationSnapshot` and `SnapshotBasedStageBallots` service integration (Plan #21 services)
- Test error handling and logging in background threads
- Test community-scoped processing (only specified community processed)
- Test calculation timing and performance monitoring
- Test thread safety and concurrent execution
- Test snapshot creation and status tracking integration

**Updated Test Files (Building on Existing 525 Tests):**
- `tests/test_views/test_democracy_views.py`: Update vote submission tests to account for automatic recalculation signals
- `tests/test_views/test_follow_views.py`: Update follow/unfollow tests to verify signal firing  
- `tests/test_models/test_accounts.py`: Update membership tests to verify signal integration
- `tests/test_services/test_star_voting.py`: Update existing STAR voting tests to work with signal integration
- `tests/test_services/test_tally.py`: Update existing tally tests to verify signal-triggered calculations
- `tests/test_services/test_snapshot_isolation.py`: Update Plan #21 tests to work with signal integration
- Mock `threading.Thread` in all tests to avoid actual background processing during test runs
- Add signal mocking utilities for consistent test behavior
- **Critical**: Maintain 100% test success rate (currently 525/525 passing)

**Testing Pattern Consistency (Following Established Conventions):**
- Use `@pytest.mark.services` for service layer tests
- Use `@pytest.mark.integration` for end-to-end workflow tests  
- Use `TestCase` classes for Django model tests
- Use factory classes from `tests/factories/` for test data generation
- Follow existing docstring patterns with module-level descriptions
- Use descriptive test method names following `test_specific_behavior` pattern

### 9. Performance Considerations

**Optimization Strategies:**
- Debounce rapid changes (if user votes multiple times quickly, only trigger one recalculation)
- Batch processing for multiple simultaneous changes
- Monitor thread creation to prevent resource exhaustion
- Add configuration for maximum concurrent calculations

**Monitoring:**
- Log calculation start/end times for performance tracking
- Track thread creation and completion
- Monitor for calculation failures or timeouts

## Plan #21 Integration Requirements

**CRITICAL**: Plan #22 must integrate seamlessly with Plan #21's snapshot isolation system. The signal-based triggers must use the new snapshot-based services, not the old direct calculation methods.

### Integration Points:

1. **Service Integration**: 
   - Signals must call `CreateCalculationSnapshot` service first
   - Then call `SnapshotBasedStageBallots` service with the created snapshot
   - Use existing error handling and status tracking from DecisionSnapshot model

2. **Status Tracking Integration**:
   - Use `DecisionSnapshot.calculation_status` for UI indicators
   - Monitor snapshot creation and processing status
   - Display error information from `DecisionSnapshot.error_log`

3. **Error Handling Integration**:
   - Leverage existing retry mechanisms from Plan #21
   - Use `DecisionSnapshot.retry_count` and `last_error` fields
   - Integrate with existing error recovery strategies

4. **Admin Interface Integration**:
   - Enhance existing DecisionSnapshot admin interface
   - Add signal-triggered calculation monitoring
   - Display automatic vs manual calculation triggers

## Implementation Phases

### Phase 1: Core Signal System (Integrated with Plan #21)
- Create signals.py with all trigger events
- Implement background threading for snapshot-based service calls
- Add comprehensive logging and error handling
- **Integration**: Use `CreateCalculationSnapshot` and `SnapshotBasedStageBallots` services

### Phase 2: UI Indicators & Manager Controls (Plan #21 Status Integration)
- Add HTMX processing indicators using DecisionSnapshot.calculation_status
- Implement manual recalculation for managers
- Update user messaging throughout application
- **Integration**: Display snapshot creation and processing status

### Phase 3: Status Tracking & Documentation (Enhanced Plan #21 Features)
- Add Decision model fields for UI convenience methods
- Update FAQ documentation to reflect snapshot-based processing
- Implement final vs. interim result indicators using DecisionSnapshot.is_final
- **Integration**: Leverage existing snapshot status tracking

### Phase 4: Testing & Optimization (Plan #21 Service Testing)
- Create comprehensive test suite including snapshot service integration
- Add performance monitoring for snapshot-based calculations
- Implement debouncing and optimization features
- **Integration**: Test snapshot creation, processing, and error handling

## Detailed Implementation Plan

### Files to Create (with Complete Docstrings)

**`democracy/signals.py` (New File):**
```python
"""
Django signals for automatic vote calculation triggering.

This module implements real-time vote recalculation using Django signals and 
background threading. When any system change occurs that affects democratic
outcomes (votes, delegation, membership), signals automatically trigger
community-scoped recalculation of all open decisions.

Key Functions:
- recalculate_community_decisions_async(): Background thread executor
- vote_changed(): Signal handler for Vote model changes
- following_changed(): Signal handler for Following model changes  
- membership_changed(): Signal handler for Membership model changes
- ballot_tags_changed(): Signal handler for Ballot tag updates

All functions include comprehensive docstrings with:
- Purpose and functionality description
- Parameter types and meanings
- Return values and side effects
- Exception handling details
- Usage examples and integration notes
"""
```

**`tests/test_signals/test_vote_calculation_signals.py` (New File):**
- Complete test coverage for all signal handlers
- Mock threading to avoid background processing during tests
- Test community scoping and edge cases
- Comprehensive docstrings for all test methods

**`tests/test_views/test_manual_recalculation.py` (New File):**
- Test manager recalculation endpoint with all permission scenarios
- Test HTMX integration and user feedback
- Complete docstrings documenting test scenarios

**`tests/test_integration/test_real_time_calculation.py` (New File):**
- End-to-end testing of signal → calculation → UI update flow
- Complex delegation scenario testing
- Complete docstrings for integration test methods

**`tests/test_services/test_async_calculation.py` (New File):**
- Direct testing of background calculation functions
- Thread safety and error handling validation
- Performance and timing verification tests

### Files to Modify (with Enhanced Docstrings)

**`democracy/apps.py`:**
- Import and register all signal handlers in ready() method
- Add comprehensive module docstring explaining signal integration
- Document signal registration process and dependencies

**`democracy/models.py` (Updated for Plan #21 Integration):**
- Add `last_calculated` DateTimeField to Decision model
- Add `is_calculating` property method for UI status (using DecisionSnapshot.calculation_status)
- Add `is_final_calculation` property for closed decisions (using DecisionSnapshot.is_final)
- Enhance all model docstrings to document new fields and methods
- **Note**: DecisionSnapshot model already enhanced in Plan #21 with status tracking

**`democracy/views.py`:**
- Add `recalculate_results(request, community_id, decision_id)` view function
- Update `vote_submit` view messaging to mention background processing
- Enhance all view docstrings to document signal integration
- Add comprehensive error handling and logging

**`democracy/urls.py`:**
- Add URL pattern for manual recalculation endpoint
- Update URL docstrings to document new patterns

**`crowdvote/settings.py` (Enhanced from Existing Configuration):**
- Enhance existing logging configuration with file handler for `logs/crowdvote.log`
- Set up log rotation (daily with 30-day retention)
- Configure log levels and formatters for structured event logging
- Add logging configuration for both development and production
- **Current State**: Already has console logging with verbose formatter for 'accounts' and 'django' apps

**`accounts/views.py`:**
- Update `follow_user`, `unfollow_user`, `apply_to_community` view messaging
- Enhance docstrings to document automatic recalculation triggers
- Add user guidance about processing indicators

**`democracy/templates/democracy/decision_detail.html`:**
- Add HTMX processing indicator to live results panel
- Implement auto-refresh functionality for calculation status
- Add timestamp display with "FINAL" badge logic

**`democracy/templates/democracy/decision_results.html`:**
- Add prominent processing indicator at top of results
- Implement calculation status polling with HTMX
- Add manual recalculation button for managers

**`crowdvote/templates/docs.html`:**
- Update FAQ section "How are votes calculated?" 
- Replace "cron jobs" with "Django signals and background threading"
- Add section about real-time processing indicators
- Document typical calculation times and status indicators

### Comprehensive Docstring Requirements

**All New Functions Must Include:**
```python
def function_name(param1: Type, param2: Type) -> ReturnType:
    """
    Brief one-line description of function purpose.
    
    Detailed explanation of what the function does, why it exists in the
    CrowdVote context, and how it fits into the democratic process.
    
    Args:
        param1 (Type): Description of parameter, its purpose, and constraints
        param2 (Type): Description of parameter, including valid values
        
    Returns:
        ReturnType: Description of return value, including possible states
        
    Raises:
        ExceptionType: When and why this exception is raised
        AnotherException: Description of other possible exceptions
        
    Example:
        >>> result = function_name(value1, value2)
        >>> print(result)
        Expected output description
        
    Note:
        Any important implementation details, performance considerations,
        or integration requirements for CrowdVote's democratic processes.
    """
```

**All New Classes Must Include:**
```python
class ClassName:
    """
    Brief description of class purpose in CrowdVote system.
    
    Detailed explanation of the class role in democratic processes,
    key attributes, relationships to other models, and usage patterns.
    
    Attributes:
        attribute_name (Type): Description of attribute and its purpose
        another_attr (Type): Description with valid values and constraints
        
    Methods:
        method_name(): Brief description of key methods
        
    Example:
        >>> instance = ClassName(param1, param2)
        >>> result = instance.method_name()
        
    Note:
        Integration details, performance considerations, or special
        requirements for CrowdVote's delegation and voting systems.
    """
```

### Testing Coverage Requirements (100% Target)

**Signal Testing:**
- Every signal handler function: 100% line coverage
- All trigger conditions: vote create/update/delete, follow/unfollow, membership changes
- Error scenarios: invalid data, missing objects, concurrent signals
- Community scoping: verify isolation between communities

**View Testing:**
- Manual recalculation endpoint: all permission scenarios
- Updated messaging: verify new user feedback text
- HTMX integration: test partial responses and status updates
- Error handling: invalid IDs, permission failures, calculation errors

**Integration Testing:**
- Complete user workflows: vote → signal → calculation → UI update
- Complex delegation scenarios: multi-level chains, tag inheritance
- Performance testing: timing and resource usage validation
- Concurrent usage: multiple users triggering calculations simultaneously

**Service Testing:**
- Background calculation function: direct unit testing
- Thread safety: concurrent execution scenarios
- Error recovery: calculation failures and retry logic
- Community scoping: verify only specified community is processed

## Success Criteria

1. **Automatic Calculation**: All 6 trigger events automatically start background recalculation using Plan #21 snapshot services
2. **Real-Time Feedback**: Users see immediate confirmation with processing indicators
3. **Manager Override**: Community managers can manually trigger recalculation
4. **Status Visibility**: Clear indicators show when calculations are running/complete/final using DecisionSnapshot.calculation_status
5. **Documentation Accuracy**: FAQ reflects actual signal-based implementation
6. **Test Coverage**: Comprehensive testing of all signal triggers and edge cases while maintaining 525/525 test success rate
7. **Performance**: Background processing doesn't impact user request response times
8. **Reliability**: Calculation failures don't crash user requests or break functionality
9. **Service Idempotency**: Multiple signal triggers don't corrupt data due to existing get_or_create() patterns
10. **Logging Completeness**: All important events logged as specified (voting, delegation, community changes, calculation phases)
11. **Plan #21 Integration**: Seamless integration with existing snapshot isolation system without breaking existing functionality

## Critical Implementation Notes

**MUST NOT BREAK EXISTING FUNCTIONALITY**:
- Plan #21's 29 snapshot isolation tests must continue passing
- All 525 existing tests must maintain 100% success rate
- Existing `CreateCalculationSnapshot` and `SnapshotBasedStageBallots` services must be used as-is
- Current logging configuration in `settings.py` must be enhanced, not replaced
- Existing service idempotency patterns must be preserved

**MUST BUILD ON EXISTING WORK**:
- Use established test patterns (`@pytest.mark.services`, factory classes, TestCase classes)
- Follow existing docstring conventions and module organization
- Integrate with existing `DecisionSnapshot.calculation_status` tracking
- Enhance existing logging rather than creating parallel systems
- Use existing error handling patterns from Plan #21

This implementation transforms CrowdVote from manual batch processing to real-time democratic participation while preserving all existing functionality and building systematically on the comprehensive work completed in previous plans.

---

## IMPLEMENTATION COMPLETED ✅

**Final Status (September 15, 2025)**: Plan #22 has been successfully implemented and tested. All phases completed:

### ✅ Phase 1: Django Signals System - COMPLETED
- **6 Signal Handlers**: Vote, Following, Membership, Ballot, Decision events all trigger background calculations
- **Background Threading**: Non-blocking calculations using `threading.Thread` with proper daemon configuration
- **Service Integration**: Seamless integration with Plan #21 `CreateCalculationSnapshot` and `SnapshotBasedStageBallots`
- **Error Handling**: Comprehensive logging and graceful failure handling

### ✅ Phase 2: UI Status Indicators - COMPLETED  
- **Real-Time Status Display**: Decision pages show live calculation status with color-coded indicators
- **JavaScript Polling**: Automatic status updates every 5 seconds with smart termination
- **Vote Submission Feedback**: Immediate visual feedback when users submit votes
- **Status Endpoint**: JSON API at `/communities/<id>/decisions/<id>/status/` for real-time updates

### ✅ Phase 3: Manager Controls - COMPLETED
- **Manual Recalculation**: Community managers can trigger on-demand calculations via AJAX
- **Permission Controls**: Proper validation ensuring only managers can access manual controls
- **Progress Indicators**: Visual feedback during manual recalculation with status polling
- **Error Display**: User-friendly error messages for failed calculations

### ✅ Phase 4: Comprehensive Testing - COMPLETED
- **67 New Tests**: Complete coverage of signals, threading, UI controls, and error scenarios
- **Signal Validation**: All trigger events tested with proper service integration
- **UI Testing**: JavaScript functionality, template rendering, and AJAX responses
- **Manager Controls**: Full permission and error scenario coverage

### ✅ Additional Improvements Completed
- **Data Validation**: Fixed critical gap preventing decisions without choices
- **Database Transactions**: Atomic operations in decision creation to prevent orphaned records  
- **Enhanced Logging**: Structured event logging with rotation and comprehensive error tracking
- **Clean Test Data**: Fresh database with proper Minion Collective and Springfield communities

### System Status
- **Real-Time Democracy**: ✅ Users see immediate feedback when voting or following others
- **Background Processing**: ✅ All calculations happen asynchronously without blocking user requests
- **Data Consistency**: ✅ Plan #21 snapshot isolation ensures accurate results during concurrent activity
- **Production Ready**: ✅ Comprehensive error handling, logging, and monitoring capabilities

**CrowdVote now provides true real-time democratic participation with automatic vote recalculation, immediate user feedback, and robust background processing.**
