# Plan #24: Alphabet Test Community for Delegation Validation

## Context

Create a clean, systematic test community with alphabetically-named members (A, B, C, etc.) to validate complex delegation inheritance calculations and visualize multi-level delegation trees. This addresses the need to verify that fractional star averaging, priority-based tie-breaking, and tag-specific following work correctly in realistic scenarios with 3-5 levels of delegation depth.

## Technical Requirements

### Test Community Structure

**Community Name**: "Alphabet Delegation Test"
**Members**: 12 users with usernames/first names like "AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC" through "LLLLLLLLLLL" and last name "Test"
**Tags**: Six numbered tags: "one", "two", "three", "four", "five", "six"
**Decision**: Single decision with 3 choices to test fractional inheritance

### Delegation Network Design

**Manual Voters (4 users who vote manually but may also follow others)**:
- **AAAAAAAAAAA**: Votes manually, uses tags "one,two,three" (5 stars, 3 stars, 1 star for choices 1,2,3)
  - Also follows JJJJJJJJJJJ on "four,five" and LLLLLLLLLLL on "six"
- **BBBBBBBBBBB**: Votes manually, uses tags "two,four,five" (2 stars, 4 stars, 5 stars for choices 1,2,3)  
  - Also follows GGGGGGGGGGG on "one,three" and KKKKKKKKKKK on "six"
- **CCCCCCCCCCC**: Votes manually, uses tags "three,five,six" (4 stars, 1 star, 3 stars for choices 1,2,3)
  - Also follows EEEEEEEEEEE on "one,two" and IIIIIIIIIII on "four"
- **DDDDDDDDDDD**: Votes manually, uses tags "one,four,six" (1 star, 5 stars, 2 stars for choices 1,2,3)
  - Also follows FFFFFFFFFFF on "two,three" and HHHHHHHHHHH on "five"

**Mixed Delegation Users (8 users who follow others across all levels)**:
- **EEEEEEEEEEE**: Follows AAAAAAAAAAA on "one,two", follows BBBBBBBBBBB on "four", follows KKKKKKKKKKK on "three,five"
- **FFFFFFFFFFF**: Follows BBBBBBBBBBB on "two,five", follows CCCCCCCCCCC on "three", follows IIIIIIIIIII on "one,six"
- **GGGGGGGGGGG**: Follows CCCCCCCCCCC on "five,six", follows DDDDDDDDDDD on "one", follows LLLLLLLLLLL on "two,four"
- **HHHHHHHHHHH**: Follows AAAAAAAAAAA on "one,two,three", follows DDDDDDDDDDD on "six", follows JJJJJJJJJJJ on "four,five"
- **IIIIIIIIIII**: Follows EEEEEEEEEEE on "one,two", follows FFFFFFFFFFF on "three,four", follows AAAAAAAAAAA on "five,six"
- **JJJJJJJJJJJ**: Follows GGGGGGGGGGG on "five,six", follows HHHHHHHHHHH on "one,two", follows BBBBBBBBBBB on "three,four"
- **KKKKKKKKKKK**: Follows EEEEEEEEEEE on "one,three", follows GGGGGGGGGGG on "six", follows CCCCCCCCCCC on "two,four,five"
- **LLLLLLLLLLL**: Follows IIIIIIIIIII on "one,two,three", follows JJJJJJJJJJJ on "four,five", follows DDDDDDDDDDD on "six"

### Expected Fractional Calculations

**Key Test Cases for Validation**:

1. **AAAAAAAAAAA** (manual voter who also follows others):
   - Manual votes: 5★, 3★, 1★ on tags "one,two,three"
   - Also follows JJJJJJJJJJJ on "four,five" and LLLLLLLLLLL on "six"
   - Should show manual votes for "one,two,three" and calculated inheritance for "four,five,six"
   - Demonstrates that manual voters can also delegate on other tags

2. **EEEEEEEEEEE** (complex multi-source following):
   - Follows AAAAAAAAAAA on "one,two", BBBBBBBBBBB on "four", KKKKKKKKKKK on "three,five"
   - Should inherit A's manual votes for "one,two"
   - Should inherit B's manual votes for "four"  
   - Should inherit K's calculated votes for "three,five"
   - Demonstrates cross-level inheritance (manual + calculated sources)

3. **IIIIIIIIIII** (mixed manual and delegation inheritance):
   - Follows EEEEEEEEEEE on "one,two", FFFFFFFFFFF on "three,four", AAAAAAAAAAA on "five,six"
   - Should inherit through E (which inherits from A) for "one,two"
   - Should inherit through F (which has complex inheritance) for "three,four"
   - Should inherit directly from A's manual votes for "five,six"
   - Demonstrates both direct and multi-level inheritance in same user

4. **LLLLLLLLLLL** (deep cross-network inheritance):
   - Follows IIIIIIIIIII on "one,two,three", JJJJJJJJJJJ on "four,five", DDDDDDDDDDD on "six"
   - Should show complex fractional averaging from multiple inheritance paths
   - Should demonstrate how votes flow through complex networks
   - Some inheritance paths may be 4+ levels deep (D→F→I→L or A→E→I→L)

### Files to Create/Modify

**New Management Command**:
- `democracy/management/commands/create_alphabet_test_community.py`
  - Create "Alphabet Delegation Test" community
  - Generate 12 users with usernames "AAAAAAAAAAA" through "LLLLLLLLLLL", first names same as username, last name "Test"
  - Create complex following relationships as specified above
  - Create single decision "Test Delegation Inheritance" with 3 choices
  - Have manual voters (AAAAAAAAAAA,BBBBBBBBBBB,CCCCCCCCCCC,DDDDDDDDDDD) cast votes with different star ratings
  - Generate realistic membership roles (all as voters for simplicity)

**Enhanced Delegation Tree Display**:
- `democracy/tree_service.py` - Ensure delegation trees show full inheritance chains clearly
- `democracy/templates/democracy/decision_results.html` - Verify fractional star display works correctly

**Testing Integration**:
- Update existing `democracy/management/commands/run_crowdvote_demo.py` to include alphabet community
- Ensure `StageBallots` and `Tally` services process the complex delegation correctly

### Validation Points

**Fractional Star Verification**:
- Users following multiple people with different votes should show fractional averages
- Priority ordering (order field) should break ties correctly
- Tag-specific inheritance should only inherit votes on matching tags

**Delegation Tree Visualization**:
- Results page should show clear 3-4 level delegation chains
- Each level should display inherited tags and fractional star ratings
- "Manual Vote" vs "Calculated Vote" should be clearly distinguished

**Mathematical Accuracy**:
- Verify averaging calculations: following 2 people with 5 and 3 stars = 4.0 average
- Verify tag filtering: only inherit votes on tags you follow someone for
- Verify priority ordering: lower order number wins ties

### Algorithm Implementation

**Delegation Processing Steps**:
1. **Manual Voters**: A,B,C,D cast votes with specific star ratings and tags
2. **Level 2 Calculation**: E,F,G,H inherit from manual voters based on tag matching
3. **Level 3 Calculation**: I,J,K inherit from Level 2 users, creating 3-level chains
4. **Level 4 Calculation**: L inherits from Level 3 users, creating 4-level chains
5. **Fractional Averaging**: When following multiple people, average their star ratings
6. **Tag Inheritance**: Inherit both votes AND tags from delegation sources
7. **Priority Resolution**: Use Following.order field to break ties

**Expected Results Display**:
- Manual voters show "Manual Vote: ★★★★★ (5.00)" format
- Calculated voters show "Calculated Vote: 3.67 × ★" format for fractional inheritance
- Delegation trees show clear inheritance paths with tag information
- Vote tally shows mix of manual and calculated votes with proper fractional display

### Comprehensive Test Suite

**New Test File**: `tests/test_services/test_alphabet_delegation_validation.py`

**Test Class**: `AlphabetDelegationValidationTest`
- Inherits from Django TestCase for database access
- Uses alphabet test community data for validation
- Includes comprehensive docstrings explaining delegation math

**Test Methods**:

1. **`test_manual_voters_vote_correctly()`**:
   - Verify AAAAAAAAAAA, BBBBBBBBBBB, CCCCCCCCCCC, DDDDDDDDDDD have manual votes
   - Verify exact star ratings: A(5,3,1), B(2,4,5), C(4,1,3), D(1,5,2)
   - Verify correct tags are applied to each manual vote

2. **`test_level_2_delegation_inheritance()`**:
   - Test EEEEEEEEEEE inherits from AAAAAAAAAAA on "one,two" tags only
   - Test FFFFFFFFFFF inherits mixed votes from BBBBBBBBBBB and CCCCCCCCCCC
   - Test GGGGGGGGGGG inherits from multiple sources with correct tag filtering
   - Test HHHHHHHHHHH inherits mostly from A with D override on "six"

3. **`test_level_3_delegation_inheritance()`**:
   - Test IIIIIIIIIII inherits through 3-level chains (A→E→I, B/C→F→I)
   - Test JJJJJJJJJJJ inherits complex mixed inheritance through G and H
   - Test KKKKKKKKKKK inherits mostly through E with G override on "six"

4. **`test_level_4_delegation_inheritance()`**:
   - Test LLLLLLLLLLL inherits through 4-level chains
   - Verify mathematical accuracy of deep inheritance calculations
   - Verify tag accumulation through multiple delegation levels

5. **`test_fractional_star_calculations()`**:
   - Test users following 2+ people get correct fractional averages
   - Example: If following someone with 5★ and someone with 3★ → expect 4.0★
   - Test priority ordering breaks ties correctly (lower order wins)
   - Test tag-specific inheritance only affects matching tags

6. **`test_tag_inheritance_accuracy()`**:
   - Verify users only inherit votes on tags they follow others for
   - Test tag accumulation through delegation chains
   - Verify inherited tags are properly displayed and stored

7. **`test_delegation_tree_structure()`**:
   - Verify delegation trees show correct inheritance paths
   - Test 4-level deep chains are properly displayed
   - Verify manual vs calculated vote distinctions

8. **`test_mathematical_accuracy()`**:
   - Comprehensive mathematical validation of all calculated votes
   - Test specific scenarios like EEEEEEEEEEE should inherit A's exact votes
   - Test complex averaging scenarios with multiple inheritance sources
   - Verify no rounding errors in fractional calculations

**Test Data Setup**:
- Use `setUpTestData()` classmethod to create alphabet community once per test class
- Call management command to generate test data
- Run vote calculation services to populate calculated votes
- Verify test data integrity before running validation tests

**Expected Test Results**:
- All 8 test methods should pass with mathematical precision
- Tests should validate the core delegation algorithms work correctly
- Tests should catch any regressions in fractional star calculations
- Tests should verify tag-specific inheritance works as designed

### Manual Verification Process

**Development Workflow**:
1. Run `python manage.py create_alphabet_test_community --clear-existing`
2. Run `python manage.py run_crowdvote_demo` to calculate inheritance
3. Visit decision results page for "Test Delegation Inheritance" 
4. Verify delegation trees show 3-4 level inheritance chains
5. Run `python -m pytest tests/test_services/test_alphabet_delegation_validation.py -v`

**Key Validation Checks**:
- LLLLLLLLLLL should show 4-level inheritance chain in delegation tree
- Users following multiple people should show fractional star averages
- Tag-specific following should only inherit matching tags
- All calculated votes should trace back to manual voters
- Mathematical accuracy of all fractional calculations verified by tests

This plan creates a systematic test environment to validate CrowdVote's core delegation algorithms with clear, verifiable results that demonstrate the complexity and accuracy of the democratic inheritance system.
