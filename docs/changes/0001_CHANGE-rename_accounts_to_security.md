# Change 0001: Rename Accounts App to Security

**Date**: 2025-01-06  
**Status**: Draft - Awaiting Review

## Context

The `accounts` app name conflicts with django-allauth conventions and doesn't align with the documented architecture in AGENTS.md, which specifies a `security` app for user management, authentication, and authorization.

Additionally, several models and methods are in the wrong app:
- **Following model**: Should be in democracy app (links Membership→Membership, not User→User)
- **vote_anonymously_by_default**: Should be on Membership (per-community preference)
- **get_tag_usage_frequency()**: Should be on Membership (tags are community-specific)
- **get_delegation_network()**: Should be on Membership (delegation is community-specific)

These belong in democracy app because CustomUser can have multiple communities with different behaviors in each.

Since we have no production data (only regenerable dummy data), we can do a clean refactor by dropping the database and creating fresh migrations.

**Strategy**: 
1. Focus this change on getting security app (auth only) working
2. Move community-specific code to democracy app but leave it temporarily disabled
3. Next change will fix democracy app with correct architecture

## Objectives

1. Rename `/accounts/` directory to `/security/`
2. **Move community-specific models/methods to democracy app**:
   - Move `Following` model → `democracy/models.py` (will be broken temporarily)
   - Move `vote_anonymously_by_default` field → `Membership` model
   - Move `get_tag_usage_frequency()` method → `Membership` model
   - Move `get_delegation_network()` method → `Membership` model
3. Temporarily disable democracy app to focus on security app
4. Update all imports across the codebase
5. Update Django settings and configuration
6. Delete all existing migrations
7. Reset database completely
8. Create fresh migrations for security app only
9. Get security app (auth) working independently

## Files to Modify

### Directory Rename
- `accounts/` → `security/`
  - All subdirectories maintain structure
  - `accounts/migrations/` → `security/migrations/`
  - `accounts/templates/accounts/` → `security/templates/security/`

### Settings and Configuration
- `crowdvote/settings.py`
  - Change `AUTH_USER_MODEL = 'accounts.CustomUser'` → `'security.CustomUser'`
  - Update `INSTALLED_APPS`: `'accounts.apps.AccountsConfig'` → `'security.apps.SecurityConfig'`
  
### App Configuration
- `security/apps.py`
  - Update `name = 'accounts'` → `name = 'security'`
  - Update class name if needed: `AccountsConfig` → `SecurityConfig`

### URL Configuration
- `crowdvote/urls.py`
  - Update: `path('accounts/', include('accounts.urls'))` → `path('accounts/', include('security.urls'))`
  - **Note**: Keep URL path as 'accounts/' for user-facing URLs (login, profile, etc.)
  - Only the Django app name changes, not the URL structure

### Import Updates

Need to find and replace across entire codebase:

**Python imports:**
```python
# Old:
from accounts.models import CustomUser, Following, MagicLink, CommunityApplication
from accounts.forms import ...
from accounts.views import ...
from accounts.utils import ...

# New:
from security.models import CustomUser, Following, MagicLink, CommunityApplication
from security.forms import ...
from security.views import ...
from security.utils import ...
```

**Files likely to need updates:**
- `democracy/models.py` (imports CustomUser, CommunityApplication)
- `democracy/views.py` (may import from accounts)
- `democracy/Let's do this phase one prep.py` (if registering accounts models)
- `democracy/forms.py` (if using accounts forms)
- `crowdvote/views.py` (landing page, docs)
- `tests/` (all test files referencing accounts)
- `tests/factories/` (Factory Boy factories)
- Any management commands

### Template Updates

**Template directories:**
- `security/templates/accounts/` → `security/templates/security/`
  - Or keep as `security/templates/accounts/` if you want URL path consistency
  - Decision: Keep templates in `accounts/` subdirectory for URL consistency

**Template tags and includes:**
- Search for `{% load ... from accounts %}` or similar
- Update to `{% load ... from security %}`
- Check for any hardcoded app name references in templates

### Admin Configuration
- `security/admin.py`
  - Verify all model registrations work with new app name

### Migration Files
- Delete `accounts/migrations/*.py` (except `__init__.py`)
- Delete `democracy/migrations/*.py` (except `__init__.py`)
- Keep empty `__init__.py` files in migration directories

## Step-by-Step Implementation

### Phase 1: Preparation
1. **Commit current state**
   - Ensure clean git status before starting
   - `git status` should show no uncommitted changes
   
2. **Stop Docker containers**
   ```bash
   docker-compose down -v  # -v flag removes volumes (database)
   ```

3. **Backup if needed**
   - Not necessary since we have no production data
   - Dummy data can be regenerated

### Phase 2: Directory and File Renaming
4. **Rename app directory**
   ```bash
   mv accounts security
   ```

5. **Clean up security/models.py - Remove community-specific code**
   - File: `security/models.py`
   - **Delete** `Following` model entirely (move to democracy later)
   - **Delete** `vote_anonymously_by_default` field from CustomUser
   - **Delete** `get_tag_usage_frequency()` method from CustomUser
   - **Delete** `get_delegation_network()` method from CustomUser
   - **Keep**: `CustomUser` (basic auth fields only), `MagicLink`, `CommunityApplication`
   
   CustomUser should only have:
   - Auth fields (username, email, password, etc. from AbstractUser)
   - Profile fields (bio, location, website_url, twitter_url, linkedin_url)
   - Privacy controls (bio_public, location_public, social_links_public)
   - Profile methods (get_display_name, get_avatar_html, etc.)

5b. **Clean up security/urls.py - Remove following URLs**
   - File: `security/urls.py`
   - **Remove** following-related URL patterns:
     - `path('follow/<int:user_id>/', views.follow_user, name='follow_user')`
     - `path('unfollow/<int:user_id>/', views.unfollow_user, name='unfollow_user')`
     - `path('edit-follow/<int:user_id>/', views.edit_follow, name='edit_follow')`
   - These belong in democracy app (following is between Memberships, not Users)
   - Will move to `democracy/urls.py` in Change 0002

5c. **Clean up security/views.py - Remove following views**
   - File: `security/views.py`
   - **Remove** following-related view functions:
     - `follow_user()`
     - `unfollow_user()`
     - `edit_follow()`
   - Will move to `democracy/views.py` in Change 0002

5d. **Update CustomUser docstrings**
   - File: `security/models.py`
   - Update class docstring to remove references to delegation
   - Current docstring mentions "delegation-related preferences" - remove this
   - Focus docstring on: authentication, user profiles, privacy controls
   - Remove any delegation/following references from method docstrings

6. **Copy community-specific code to democracy/models.py**
   - Copy `Following` model to democracy app (but comment it out with TODO)
   - Add `vote_anonymously_by_default` field to `Membership` model (comment out)
   - Copy `get_tag_usage_frequency()` to `Membership` model (comment out)
   - Copy `get_delegation_network()` to `Membership` model (comment out)
   - Add comment: `# TODO: Fix in next change - requires Membership→Membership Following`

7. **Update app configuration**
   - File: `security/apps.py`
   - Change `name = 'accounts'` to `name = 'security'`
   - Change `class AccountsConfig` to `class SecurityConfig`
   - Update verbose_name if present

8. **Update URL namespace** (if used)
   - File: `security/urls.py`
   - Check for `app_name = 'accounts'` - keep as is for URL consistency
   - URLs like `/accounts/login/` and `{% url 'accounts:login' %}` will still work

### Phase 3: Settings and Configuration
9. **Temporarily disable democracy app**
   - File: `crowdvote/settings.py`
   - Comment out `'democracy.apps.DemocracyConfig'` in `INSTALLED_APPS`
   - Add comment: `# TODO: Re-enable after fixing Following model (Change 0002)`
   - This allows us to focus on getting security app working

10. **Update Django settings**
    - File: `crowdvote/settings.py`
    - Change `INSTALLED_APPS`: `'accounts.apps.AccountsConfig'` → `'security.apps.SecurityConfig'`
    - Change `AUTH_USER_MODEL = 'accounts.CustomUser'` → `'security.CustomUser'`

11. **Update main URLs**
    - File: `crowdvote/urls.py`
    - Change `path('accounts/', include('accounts.urls'))` → `path('accounts/', include('security.urls'))`
    - Comment out democracy URLs temporarily: `# path('communities/', include('democracy.urls')),`

### Phase 4: Import Updates Across Codebase
12. **Search and replace imports**
    - Search pattern: `from accounts`
    - Replace with: `from security`
    - **Skip democracy app files for now** (app is disabled)
    - Files to check:
      - `crowdvote/views.py`
      - `tests/**/*.py` (comment out tests that need democracy app)
      - `tests/factories/*.py` (fix user factory only)

13. **Update get_user_model() references**
    - Most code should use `get_user_model()` instead of direct imports
    - Verify no hardcoded `accounts.CustomUser` strings in code
    - Search for: `'accounts.CustomUser'` (as string)
    - Replace with: `'security.CustomUser'`

### Phase 5: Template Updates
14. **Review template structure**
    - Option A: Keep `security/templates/accounts/` for URL path consistency
    - Option B: Rename to `security/templates/security/` for app name consistency
    - **Decision**: Keep as `accounts/` for consistency with URL namespace

15. **Update template tag loads** (if any)
    - Search templates for: `{% load ... from accounts %}`
    - Update to: `{% load ... from security %}`
    - Only update security app templates for now
    - Democracy templates will be fixed in next change

### Phase 6: Migration Reset
16. **Delete all migration files**
    ```bash
    # Delete security migrations (except __init__.py)
    rm security/migrations/0*.py
    
    # Delete democracy migrations (except __init__.py)
    rm democracy/migrations/0*.py
    ```

17. **Verify __init__.py files remain**
    - `security/migrations/__init__.py` should exist and be empty
    - `democracy/migrations/__init__.py` should exist and be empty

### Phase 7: Database Reset
18. **Ensure Docker volumes are removed** (already done in step 2)
    - This deletes the PostgreSQL database completely
    - Fresh database will be created on next `docker-compose up`

19. **Start Docker containers**
    ```bash
    docker-compose up -d
    ```

20. **Create fresh migrations for security app only**
    ```bash
    docker-compose exec web python manage.py makemigrations security
    ```
    - Should create: `security/migrations/0001_initial.py`
    - Should include: CustomUser, MagicLink, CommunityApplication
    - Should NOT include: Following (moved to democracy)
    - Review migration file to ensure models are correct

21. **Apply migrations**
    ```bash
    docker-compose exec web python manage.py migrate
    ```
    - Only security app migrations will run
    - Democracy app is disabled

22. **Create superuser**
    ```bash
    docker-compose exec web python manage.py createsuperuser
    ```

### Phase 8: Testing
23. **Clean up security app tests**
    - File: `tests/test_models/test_accounts_models.py` → rename to `test_security_models.py`
    - **Remove** tests for deleted functionality:
      - Tests for `Following` model (moved to democracy)
      - Tests for `get_delegation_network()` method (moved to democracy)
      - Tests for `get_tag_usage_frequency()` method (moved to democracy)
      - Tests for `vote_anonymously_by_default` field (moved to democracy)
    - **Keep** tests for:
      - CustomUser authentication
      - MagicLink creation and validation
      - CommunityApplication workflow
      - User profile fields and privacy controls
    - Update imports: `from accounts` → `from security`

24. **Skip/comment out democracy-related tests**
    - Don't try to fix democracy tests now
    - Comment out or skip test files that import democracy models
    - Add comment: `# TODO (Change 0002): Fix after democracy app restored`

25. **Test admin interface**
    - Visit: http://localhost:8000/admin/
    - Verify security models appear correctly:
      - CustomUser
      - MagicLink  
      - CommunityApplication
    - Democracy models won't appear (app disabled)

26. **Manual testing (limited scope)**
    - Test magic link login flow
    - Test user profile pages (basic fields only)
    - Create a few test users
    - **Skip**: Following, communities, decisions (democracy app disabled)

27. **Run security app tests**
    ```bash
    docker-compose exec web pytest tests/test_models/test_security_models.py -v
    docker-compose exec web pytest tests/test_views/test_security_views.py -v
    ```
    - Only security-specific tests should run
    - Auth-related tests should pass
    - Democracy tests skipped/commented out

### Phase 9: Documentation
28. **Update CHANGELOG.md**
    - Add entry referencing this change document
    - Include git commit hash
    - Brief summary: "Renamed accounts→security app, moved community-specific code to democracy (disabled)"
    
29. **Add TODO in democracy/models.py**
    ```python
    # TODO (Change 0002): Fix architecture
    # - Following model: Membership→Membership (not User→User)
    # - Add methods to Membership:
    #   - vote_anonymously_by_default field
    #   - get_tag_usage_frequency()
    #   - get_delegation_network()
    ```

## Files Requiring Import Updates

Based on grep search across codebase, these files likely import from accounts:

### Core Django Apps
- `democracy/models.py` - Imports CustomUser for ForeignKeys
- `democracy/views.py` - May import auth views or user models
- `democracy/forms.py` - May use user-related forms
- `democracy/admin.py` - May register accounts models
- `democracy/services.py` - May reference user models
- `democracy/tree_service.py` - Uses Following model

### Management Commands
- `democracy/management/commands/generate_dummy_data_new.py` - Creates users
- `democracy/management/commands/stage_and_tally_ballots.py` - May reference users

### Tests
- `tests/conftest.py` - May import user factories
- `tests/factories/user_factory.py` - Creates CustomUser instances
- `tests/test_models/test_accounts_models.py` - Tests accounts models
- `tests/test_views/test_accounts_views.py` - Tests accounts views
- `tests/test_forms/test_accounts_forms.py` - Tests accounts forms
- All integration tests

### Project Configuration
- `crowdvote/views.py` - Landing page, may check authentication
- `crowdvote/settings.py` - AUTH_USER_MODEL setting

## Testing Steps

After implementation (limited scope - democracy app disabled):

- [ ] Django starts without errors: `docker-compose up`
- [ ] No import errors in logs related to security app
- [ ] Admin interface loads and shows security models (CustomUser, MagicLink, CommunityApplication)
- [ ] Security migration created successfully (`0001_initial.py`)
- [ ] Database tables created: `security_customuser`, `security_magiclink`, `security_communityapplication`
- [ ] Can create superuser
- [ ] Can log in with magic link
- [ ] User profile pages accessible (basic fields)
- [ ] No references to 'accounts' in security app code
- [ ] URL routing works for auth: `/accounts/login/`, `/accounts/profile/`, etc.
- [ ] Democracy app properly disabled (no errors, just unavailable)
- [ ] Security app tests pass (Following/delegation tests removed)
- [ ] CustomUser docstrings updated (no delegation references)
- [ ] Democracy tests commented out/skipped

**Expected Failures** (will fix in Change 0002):
- ❌ Following/unfollowing (moved to democracy)
- ❌ Community creation/membership (democracy disabled)
- ❌ Decision creation/voting (democracy disabled)
- ❌ Dummy data generation (requires democracy)
- ❌ Most integration tests (require democracy)

## Potential Issues and Solutions

### Issue 1: Import Errors After Rename
**Symptom**: `ModuleNotFoundError: No module named 'accounts'`
**Solution**: Search codebase for any missed `from accounts` imports

### Issue 2: AUTH_USER_MODEL Not Updated
**Symptom**: Django can't find user model
**Solution**: Verify `settings.py` has `AUTH_USER_MODEL = 'security.CustomUser'`

### Issue 3: Test Failures
**Symptom**: Tests fail with import errors
**Solution**: Update test imports and factory references

### Issue 4: Template Not Found
**Symptom**: `TemplateDoesNotExist: accounts/...`
**Solution**: Check template directory structure in `security/templates/`

### Issue 5: URL Reverse Errors
**Symptom**: `NoReverseMatch` for accounts URLs
**Solution**: Verify `app_name = 'accounts'` is kept in `security/urls.py`

## Additional Tasks to Consider

- [ ] Update test file names? (`test_accounts_*.py` → `test_security_*.py`)
- [ ] Update template directory structure decision
- [ ] Update any API documentation
- [ ] Update any developer documentation
- [ ] Check for hardcoded strings in JavaScript files
- [ ] Verify static files don't reference old app name

---

**Notes for Implementation:**
- This change focuses ONLY on getting security app (authentication) working
- Democracy app will be temporarily broken - this is intentional
- Community-specific code moved to democracy but commented out with TODOs
- Next change (0002) will fix democracy app with correct Membership→Membership architecture
- The key is being thorough with search/replace for imports in security app
- Keep URL paths as `/accounts/` for user-facing consistency
- Only the Django app name changes from `accounts` to `security`

**What moves to democracy app (to be fixed in Change 0002):**
- `Following` model (entire model)
- Following-related URLs: `follow_user`, `unfollow_user`, `edit_follow`
- Following-related views: `follow_user()`, `unfollow_user()`, `edit_follow()`
- `vote_anonymously_by_default` field → Membership
- `get_tag_usage_frequency()` method → Membership
- `get_delegation_network()` method → Membership

**What stays in security app:**
- `CustomUser` (minimal auth + profile fields)
- `MagicLink` (passwordless auth)
- `CommunityApplication` (for now - may move later)
- Auth URLs: login, logout, profile, magic links
- Auth views: authentication, profile management
