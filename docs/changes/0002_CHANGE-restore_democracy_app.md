# Change 0002: Restore Democracy App with Membership-Based Following

**Date**: 2025-01-06  
**Status**: Completed

**Implementation Notes**: Database reset required (docker-compose down -v) due to migration conflicts. Added error handling in create_community_delegation_chains for missing memberships.

## Context

In Change 0001, we:
1. Renamed `accounts` app to `security`
2. Moved community-specific models/methods from security to democracy (but left them commented out)
3. Temporarily disabled democracy app to focus on getting security app working

Now we need to restore the democracy app with the correct architecture where `Following` relationships are **Membership→Membership** (community-specific) instead of **User→User** (global). This is critical because:
- Users can belong to multiple communities with different delegation preferences in each
- Following relationships are inherently community-specific
- Delegation chains must respect community boundaries

## Objective

**Primary Goal**: Get the democracy app fully functional so we can run `generate_demo_communities.py` to populate the database with Minion Collective and Springfield Town Council test data.

**Out of Scope** (for this change): 
- Fixing views/templates that use Following
- Fixing following-related URLs
- Making the full web UI work
- **Rewriting `stage_and_tally_ballots.py`** - this needs complete architectural refactor:
  - Old: Loops through all members inefficiently on every change
  - New: Target only impacted members when changes occur
  - Old: Tried to use STAR voting to calculate ballots (wrong!)
  - New: Just AVERAGE star ratings from followed members for inherited ballots
  - STAR voting only for final tally to pick winner
- We ONLY care about making `generate_demo_communities` work

## Files to Modify

### 1. Democracy Models (`democracy/models.py`)

**Add Following Model**:
- Create `Following` model with Membership→Membership relationships
- Fields: `follower` (FK to Membership), `followee` (FK to Membership), `tags`, `order`
- Unique constraint on `follower + followee`
- Ordering by `order` for tie-breaking

**No changes needed to Membership model** - the TODO comments were placeholders only. The methods `get_tag_usage_frequency()` and `get_delegation_network()` are not actually used by the demo data generation command, so we can defer implementing them.

### 2. Update Import Statements Across Codebase

**Files Importing Following from security** (found via grep):
- `democracy/management/commands/generate_demo_communities.py`
- `democracy/management/commands/stage_and_tally_ballots.py`
- `democracy/views.py`
- `democracy/signals.py`
- ~~`democracy/tree_service.py`~~ - **DELETED** (replaced by JavaScript visualization)

**All need**:
- Update import: `from security.models import Following` → `from democracy.models import Following`

### 3. Update Management Command (`democracy/management/commands/generate_demo_communities.py`)

**Current Issues**:
- Imports `Following` from `security.models` (old location)
- Creates Following relationships using User→User pattern
- Needs to be updated to use Membership→Membership pattern

**Required Changes**:
- Update import: `from security.models import Following` → `from democracy.models import Following`
- Update all `Following.objects.get_or_create()` calls to use Memberships instead of Users
- Get the appropriate Membership objects for each community before creating Following relationships
- Update docstrings to reflect Membership-based architecture

### 4. Update Other Democracy Files

**Files to Update** (just change imports, logic stays same for now):

1. **`democracy/views.py`**:
   - Update import: `from security.models import Following` → `from democracy.models import Following`
   - Note: Views may be broken (out of scope), we're just fixing the import

2. **`democracy/signals.py`**:
   - Update import: `from security.models import Following` → `from democracy.models import Following`
   - Note: Signals may need updates if they use Following, but just fix import for now

3. **`democracy/management/commands/stage_and_tally_ballots.py`**:
   - Update import: `from security.models import CustomUser, Following` → keep CustomUser from security, get Following from democracy
   - Change to: `from security.models import CustomUser` and `from democracy.models import Following`
   - Note: **This command needs major refactor (out of scope)** - old approach loops through all members inefficiently
   - New approach will target only impacted members when changes occur
   - STAR voting should only be used for final tally, NOT for calculating inherited ballots
   - Inherited ballots should just AVERAGE star ratings from followed members
   - Just fix the import for now - complete rewrite is a separate change

### 5. Create Fresh Migrations

- Delete existing `democracy/migrations/0001_initial.py` and `0002_initial.py`
- Create fresh migration with `makemigrations democracy`
- This migration will include Following model

### 6. Update Django Admin (`democracy/admin.py`)

**Add Following to Admin**:
- Register Following model
- Create admin interface showing follower/followee memberships
- Display community context in list view
- Add filters for community and tags

### 7. Update Tests

**Test Files to Update**:
- Any test importing Following from security → update to democracy
- Tests that create Following with User→User → update to Membership→Membership
- May need to comment out/skip broken following tests for now (out of scope for this change)

### 8. Update Docstrings

**Files Needing Docstring Updates**:
- `democracy/models.py` - Following model docstring
- `generate_demo_communities.py` - Update comments about delegation
- Any other files mentioning Following architecture

## Step-by-Step Implementation

### Phase 1: Update All Import Statements

1. **Update imports in democracy app files**:
   - `democracy/management/commands/generate_demo_communities.py`
   - `democracy/management/commands/stage_and_tally_ballots.py`
   - `democracy/views.py`
   - `democracy/signals.py`
   
   Change: `from security.models import Following` → `from democracy.models import Following`
   
   Note: `democracy/tree_service.py` has been deleted (replaced by JavaScript visualization)

### Phase 2: Create Following Model

2. **Add Following model to `democracy/models.py`**
   ```python
   class Following(BaseModel):
       """
       Represents a Membership following another Membership for vote delegation.
       
       Following relationships are community-specific: each Following links two
       Membership objects within the SAME community. This ensures delegation
       respects community boundaries and allows users to have different delegation
       preferences in different communities.
       
       Attributes:
           follower (ForeignKey): Membership doing the following (who inherits votes)
           followee (ForeignKey): Membership being followed (whose votes are inherited)
           tags (CharField): Comma-separated tags to filter which decisions this applies to
           order (PositiveIntegerField): Priority order for resolving ties (lower = higher priority)
       
       Example:
           If Alice (Member in Community A) follows Bob (Member in Community A) on "budget" tags,
           then when Bob votes on a decision tagged with "budget", Alice's ballot can inherit
           from Bob's vote if Alice hasn't voted directly.
       """
       follower = models.ForeignKey(
           Membership,
           related_name='following',
           on_delete=models.CASCADE,
           help_text="The membership who is following someone (inherits votes)"
       )
       followee = models.ForeignKey(
           Membership,
           related_name='followers',
           on_delete=models.CASCADE,
           help_text="The membership being followed (whose votes are inherited)"
       )
       tags = models.CharField(
           max_length=500,
           blank=True,
           help_text="Comma-separated tags. Empty means 'all tags'. Example: 'budget,environment'"
       )
       order = models.PositiveIntegerField(
           default=1,
           help_text="Priority order for tie-breaking (lower number = higher priority)"
       )
       
       class Meta:
           ordering = ['follower', 'order', 'followee']
           verbose_name = "Following Relationship"
           verbose_name_plural = "Following Relationships"
           unique_together = ['follower', 'followee']
       
       def __str__(self):
           tags_str = f" on tags: {self.tags}" if self.tags else " on all tags"
           return f"{self.follower.member.username} follows {self.followee.member.username}{tags_str}"
       
       def clean(self):
           """Validate the following relationship."""
           from django.core.exceptions import ValidationError
           
           # Ensure both memberships are in the same community
           if self.follower.community != self.followee.community:
               raise ValidationError(
                   "Following relationships must be within the same community"
               )
           
           # Prevent self-following
           if self.follower == self.followee:
               raise ValidationError("A member cannot follow themselves")
   ```

3. **Validation Rules**:
   - `follower.community` must equal `followee.community` (same community)
   - `follower` cannot equal `followee` (no self-following)
   - Unique constraint on `follower + followee` (no duplicate relationships)

### Phase 3: Update Management Command

4. **Update Following creation in `generate_demo_communities.py`**:
   ```python
   # OLD:
   from security.models import Following
   
   # NEW:
   from democracy.models import Following
   ```

5. **Update `create_test_delegation_relationships()` method**:
   - Get Membership objects instead of User objects
   - Create Following with Membership→Membership
   
   Example transformation:
   ```python
   # OLD (User→User):
   Following.objects.get_or_create(
       follower=B,  # B is a User
       followee=A,  # A is a User
       defaults={'tags': 'governance', 'order': 1}
   )
   
   # NEW (Membership→Membership):
   community = Community.objects.get(name='Minion Collective')
   B_membership = Membership.objects.get(member=B, community=community)
   A_membership = Membership.objects.get(member=A, community=community)
   
   Following.objects.get_or_create(
       follower=B_membership,
       followee=A_membership,
       defaults={'tags': 'governance', 'order': 1}
   )
   ```

6. **Update `create_multilevel_delegation_chains()` method**:
   - Same pattern: get Membership objects before creating Following
   - Update all Following creations to use Memberships

7. **Update `create_community_delegation_chains()` method**:
   - Convert user lists to membership lists
   - Use Membership objects in Following creation

### Phase 4: Migrations

8. **Delete old democracy migrations**:
   ```bash
   rm democracy/migrations/0001_initial.py
   rm democracy/migrations/0002_initial.py
   ```

9. **Keep `__init__.py`**:
   - Ensure `democracy/migrations/__init__.py` exists

10. **Create fresh migrations**:
   ```bash
   docker-compose exec web python manage.py makemigrations democracy
   ```
   - Should create new `0001_initial.py` with all models including Following

11. **Apply migrations**:
    ```bash
    docker-compose exec web python manage.py migrate
    ```

### Phase 5: Admin Configuration

12. **Update `democracy/admin.py`** - Add Following admin:
    ```python
    @admin.register(Following)
    class FollowingAdmin(admin.ModelAdmin):
        list_display = ['follower_display', 'followee_display', 'community_display', 'tags', 'order']
        list_filter = ['follower__community', 'tags']
        search_fields = [
            'follower__member__username',
            'followee__member__username',
            'tags'
        ]
        ordering = ['follower__community', 'follower__member__username', 'order']
        
        def follower_display(self, obj):
            return f"{obj.follower.member.username}"
        follower_display.short_description = 'Follower'
        
        def followee_display(self, obj):
            return f"{obj.followee.member.username}"
        followee_display.short_description = 'Followee'
        
        def community_display(self, obj):
            return obj.follower.community.name
        community_display.short_description = 'Community'
    ```

### Phase 6: Test Updates

13. **Update test imports**:
    - Find all tests importing `Following` from security
    - Update to import from democracy
    - Pattern: `grep -r "from security.models import.*Following" tests/`

14. **Update test fixtures**:
    - Tests creating Following need Membership objects
    - Update factory patterns in `tests/factories/`

15. **Skip broken tests** (for now):
    - Add `@pytest.mark.skip(reason="Change 0002: Following UI not updated yet")` to view tests
    - Focus only on making model-level tests pass

### Phase 7: Testing and Verification

16. **Run management command**:
    ```bash
    docker-compose exec web python manage.py generate_demo_communities --clear-data
    ```
    - Should create communities, users, memberships, decisions, and Following relationships
    - No errors about Following model

17. **Verify in Django admin**:
    - Visit `/admin/democracy/following/`
    - Should see Following relationships with Membership references
    - Community context should be clear

18. **Check database**:
    ```bash
    docker-compose exec db psql -U crowdvote -d crowdvote -c "SELECT * FROM democracy_following LIMIT 5;"
    ```
    - Should see `follower_id` and `followee_id` referencing Membership UUIDs

19. **Verify demo data quality**:
    - Check that Following relationships were created with Membership→Membership
    - Verify test users A-H exist with correct delegation patterns
    - Confirm both communities have decisions with choices
    
**Note**: Do NOT try to run `stage_and_tally_ballots` - it needs complete rewrite (separate change)

## Testing Checklist

After implementation:

- [ ] Django starts without errors: `docker-compose up`
- [ ] Democracy app loads in settings (no import errors)
- [ ] Fresh migration created: `democracy/migrations/0001_initial.py`
- [ ] Migration applies successfully: `python manage.py migrate`
- [ ] Following model appears in admin: `/admin/democracy/following/`
- [ ] Management command runs: `generate_demo_communities --clear-data`
- [ ] Following relationships created (check admin)
- [ ] Following relationships use Membership→Membership (not User→User)
- [ ] Following relationships respect community boundaries
- [ ] Test users A-H created with correct delegation patterns
- [ ] Minion Collective and Springfield communities populated
- [ ] No errors in logs during data generation

## Potential Issues and Solutions

### Issue 1: Circular Import Errors
**Symptom**: ImportError when importing Following in security models  
**Solution**: Following should only be in democracy, not imported by security

### Issue 2: Migration Dependencies
**Symptom**: Migration fails due to missing Membership model  
**Solution**: Ensure Membership model is created before Following in migration

### Issue 3: Existing Test Data
**Symptom**: Unique constraint violations when running command  
**Solution**: Use `--clear-data` flag to wipe existing data first

### Issue 4: Community Boundary Violations
**Symptom**: ValidationError about mismatched communities  
**Solution**: Ensure code always gets Membership from correct community before creating Following

## Files Changed Summary

**New Files**:
- `democracy/migrations/0001_initial.py` (fresh migration)

**Modified Files**:
- `democracy/models.py` - Add Following model
- `democracy/admin.py` - Register Following admin
- `democracy/management/commands/generate_demo_communities.py` - Use Membership-based Following
- `democracy/management/commands/stage_and_tally_ballots.py` - Update import
- `democracy/views.py` - Update import
- `democracy/signals.py` - Update import
- Tests that import Following (TBD based on grep results)
- `docs/CHANGELOG.md` - Add entry for Change 0002

**Deleted Files**:
- `democracy/migrations/0001_initial.py` (old)
- `democracy/migrations/0002_initial.py` (old)
- `democracy/tree_service.py` - **DELETED** (replaced by JavaScript network visualization)

## Success Criteria

**Minimum Success** (required):
1. ✅ `generate_demo_communities --clear-data` runs without errors
2. ✅ Minion Collective and Springfield communities created
3. ✅ Test users A-H created with memberships
4. ✅ Following relationships created using Membership→Membership
5. ✅ Data visible in Django admin

**Stretch Goals** (nice to have):
1. 🎯 Model-level tests pass
2. 🎯 No regression in existing passing tests

**Explicitly NOT Included**:
- ❌ `stage_and_tally_ballots` (needs complete rewrite - separate change)
- ❌ tree_service.py functionality (likely to be replaced with JavaScript visualization)

## Next Steps (Future Changes)

After this change, the following will still be broken (to be fixed later):

**Change 0003: Rewrite Stage & Tally Architecture**
- Complete rewrite of ballot calculation logic
- New approach: Target only impacted members when changes occur
- Calculate inherited ballots by AVERAGING star ratings (not STAR voting!)
- STAR voting only for final tally phase (picking winner)
- Efficient queries instead of looping through all members

**Change 0004: Following UI & Views**
- Following-related views (`follow_user`, `unfollow_user`, `edit_follow`)
- Following-related URLs (use Membership UUIDs instead of User IDs)
- Templates showing following relationships
- User profiles showing delegation networks

**Change 0005: JavaScript Network Visualization**
- Implement new JavaScript network visualization
- Interactive delegation tree exploration
- Note: Old `tree_service.py` already deleted in Change 0002

These are intentionally out of scope for Change 0002 - we're just getting the data layer working first.

---

**Ready for Review**: Please review this plan and approve before implementation begins.
