# Change 0006: Membership-Level Anonymity System

## Context

Currently, anonymity is handled at the ballot level with `is_anonymous_by_default` on Membership. This change moves anonymity to be a membership-level setting where users can be anonymous in some communities but not others. Lobbyists are never allowed to be anonymous since they're building reputation and seeking followers.

## Key Requirements

### Core Anonymity Features
1. **Rename field**: `Membership.is_anonymous_by_default` → `Membership.is_anonymous`
2. **Add constraint**: Lobbyists (`is_voting_community_member=False`) cannot be anonymous (`is_anonymous` must be `False`)
3. **Default to anonymous**: `is_anonymous` defaults to `True` for all new memberships
4. **Community Detail UI updates**:
   - Add "Member" column showing first/last name
   - Rename current "Member" column to "Username"
   - Show "Anonymous" instead of username if `is_anonymous=True`
5. **Network visualization**: Show "Anonymous" on nodes for anonymous members
6. **Anonymity toggle**: HTMX modal in sidebar Quick Actions to toggle anonymity per community
7. **No profile links for anonymous**: Anonymous members should not have clickable profile links

### Demo Data & Database Management
8. **Database reset tool**: Add `--reset-database` flag to generate_demo_communities command
9. **Auto-create superuser**: Create admin/admin superuser in local environments only
10. **Additional demo communities**: Add 3 realistic communities with application-required flow
11. **Multiple decisions**: Each community gets 4 themed decisions with varied close times
12. **Decision timing**: Mix of closed, closing soon, and future decisions

### Ballot UI Updates
13. **Remove anonymity checkbox from ballot page**: Anonymity is now membership-level, not ballot-level
14. **Closed decision UI**: Disable voting on closed decisions, show "Decision Closed" instead of "Update Vote"

### Deployment
15. **Railway cron job documentation**: Document how to set up weekly database reset on Railway

## Files to Modify

### 1. Migration
**File**: `democracy/migrations/XXXX_membership_anonymity.py`
- Rename `is_anonymous_by_default` to `is_anonymous`
- Add `CheckConstraint` to enforce lobbyists cannot be anonymous
- Update any existing data if needed

### 2. Model Updates
**File**: `democracy/models.py`

**Membership model (lines 132-225)**:
- Rename field `is_anonymous_by_default` → `is_anonymous`
- Update field help_text: "Whether this member's identity is anonymous in this community"
- Add constraint in Meta:
  ```python
  constraints = [
      models.CheckConstraint(
          check=Q(is_voting_community_member=True) | Q(is_anonymous=False),
          name='lobbyists_cannot_be_anonymous'
      )
  ]
  ```
- Update docstring to explain membership-level anonymity and lobbyist restriction
- Update `__str__` method if needed
- Remove any references to `is_anonymous_by_default` in comments/methods

**Ballot model (lines 673-841)**:
- Remove `is_anonymous` field (no longer needed at ballot level)
- Remove `set_anonymity_preference()` method (no longer needed)
- Remove `get_display_name()` and `get_display_username()` methods (move logic to Membership)
- Update docstring to reflect that anonymity is now at membership level
- Update any methods that reference `is_anonymous`

### 3. Community Detail Page
**File**: `democracy/templates/democracy/community_detail.html`

**Members Table section (lines 156-222)**:
- Add new column before current "Member" column:
  - Header: "Member"
  - Content: `{{ membership.member.first_name }} {{ membership.member.last_name }}`
- Change current "Member" column header to "Username"
- Update username column content:
  ```django
  {% if membership.is_anonymous %}
      <span class="text-gray-500 dark:text-gray-400">Anonymous</span>
  {% else %}
      <a href="{% url 'accounts:member_profile' membership.member.username %}" ...>
          @{{ membership.member.username }}
      </a>
  {% endif %}
  ```
- Update DataTables columnDefs for new column structure

**Delegation Network section (lines 237-256)**:
- Pass `memberships` data to network visualization with anonymity flags
- Update network_visualization.html to handle anonymous nodes

### 4. Network Visualization Component
**File**: `democracy/templates/democracy/components/network_visualization.html`

- Update node rendering to check `is_anonymous` flag
- Show "Anonymous" label instead of username for anonymous members
- Keep delegation edges visible but anonymize node labels

### 5. Sidebar Quick Actions - Anonymity Toggle
**File**: `democracy/templates/democracy/community_detail.html` (lines 39-59)

Add button in Quick Actions section (only for members):
```django
{% if user_membership %}
    <button hx-get="{% url 'democracy:membership_settings_modal' community.id %}"
            hx-target="#settings-modal-container"
            hx-swap="innerHTML"
            class="inline-flex items-center justify-center w-full px-4 py-2 bg-gray-600 text-white text-sm font-medium rounded-md hover:bg-gray-700 transition-colors">
        ⚙️ My Settings
    </button>
{% endif %}
```

Add modal container at bottom:
```django
<div id="settings-modal-container"></div>
```

### 6. Membership Settings Modal Template
**File**: `democracy/templates/democracy/components/membership_settings_modal.html` (NEW)

Create HTMX modal with:
- Header: "My Membership in [Community Name]"
- Checkbox for anonymity toggle
- If lobbyist: Show disabled checkbox with explanation "Lobbyists cannot be anonymous"
- Save button with HTMX post
- Cancel button to close modal

### 7. Views
**File**: `democracy/views.py`

**Add `membership_settings_modal` view**:
- Get user's membership in community
- Render modal template with current settings
- Handle HTMX request detection

**Add `membership_settings_save` view**:
- Get user's membership
- Validate they're not trying to make lobbyist anonymous
- Update `is_anonymous` field
- Return success response with HTMX redirect or OOB update
- Log the change to crowdvote.log

**Update vote submission view** (e.g., `vote_on_decision`, `update_ballot`, etc.):
- Add check: `if not decision.is_open:` 
- Reject submissions with error message: "This decision is closed. Voting is no longer allowed."
- Return 403 or redirect with error message
- Example:
  ```python
  if not decision.is_open:
      messages.error(request, "This decision is closed. Voting is no longer allowed.")
      return redirect('democracy:decision_detail', community_id=community.id, decision_id=decision.id)
  ```

### 8. URLs
**File**: `democracy/urls.py`

Add two new URL patterns:
- `membership-settings/<uuid:community_id>/` → `membership_settings_modal` (GET)
- `membership-settings/<uuid:community_id>/save/` → `membership_settings_save` (POST)

### 9. Community Detail View
**File**: `democracy/views.py` - `community_detail` function

- Update memberships query to include all fields needed
- Pass anonymity data to network visualization context
- Ensure template receives updated membership data

### 10. Generate Demo Communities Command
**File**: `democracy/management/commands/generate_demo_communities.py`

**Major Enhancements**:

**A. Database Reset with Superuser Creation**:
- Add `--reset-database` flag that performs complete wipe
- Wipe order (respecting foreign keys):
  1. Vote.objects.all().delete()
  2. Ballot.objects.all().delete()
  3. Choice.objects.all().delete()
  4. Decision.objects.all().delete()
  5. Following.objects.all().delete()
  6. Membership.objects.all().delete()
  7. Community.objects.all().delete()
  8. User.objects.all().delete()
- After wipe, check if environment is local (check `settings.DEBUG == True`)
- If local, create superuser:
  ```python
  if settings.DEBUG:
      User.objects.create_superuser(
          username='admin',
          email='admin@crowdvote.local',
          password='admin',
          first_name='Admin',
          last_name='User'
      )
      self.stdout.write(self.style.SUCCESS('Created superuser: admin/admin'))
  ```

**B. Additional Realistic Communities**:
Create 3 new communities with `auto_approve_applications=False`:

1. **Ocean View Condo Association** 🏖️
   - Description: "A beachfront residential community managing shared amenities and maintenance decisions."
   - auto_approve_applications: False
   - No initial members

2. **Tech Workers Cooperative** 💻
   - Description: "A worker-owned technology cooperative making operational and strategic decisions democratically."
   - auto_approve_applications: False
   - No initial members

3. **Riverside Community Garden** 🌱
   - Description: "A neighborhood garden collective deciding on plot assignments, rules, and community events."
   - auto_approve_applications: False
   - No initial members

Implementation in `create_communities()`:
```python
def create_communities(self):
    """Create demo communities: 2 auto-approve + 3 application-required."""
    # Auto-approve communities (existing)
    minion_community, _ = Community.objects.get_or_create(...)
    springfield_community, _ = Community.objects.get_or_create(...)
    
    # Application-required communities (NEW)
    oceanview, _ = Community.objects.get_or_create(
        name='Ocean View Condo Association',
        defaults={
            'description': 'A beachfront residential community...',
            'auto_approve_applications': False,
            'application_message_required': True
        }
    )
    
    tech_coop, _ = Community.objects.get_or_create(
        name='Tech Workers Cooperative',
        defaults={
            'description': 'A worker-owned technology cooperative...',
            'auto_approve_applications': False,
            'application_message_required': True
        }
    )
    
    garden, _ = Community.objects.get_or_create(
        name='Riverside Community Garden',
        defaults={
            'description': 'A neighborhood garden collective...',
            'auto_approve_applications': False,
            'application_message_required': True
        }
    )
    
    return [minion_community, springfield_community, oceanview, tech_coop, garden]
```

**Note**: Only create users and memberships for Minions and Springfield. The 3 new communities remain empty for users to apply to.

**C. Realistic Delegation Relationships**:

The delegation network should look like a real community with varied engagement levels:

**Engagement Patterns**:
1. **Highly Engaged** (~30% of members):
   - Follow 2-3 people on specific tags
   - Are followed by multiple people
   - Active voters with opinions on many issues
   - Form the core of delegation chains

2. **Moderately Engaged** (~40% of members):
   - Follow 1-2 people, maybe on all tags
   - Some are followed, some aren't
   - Might vote manually, might rely on delegation
   - Middle layers of delegation trees

3. **Low Engagement** (~20% of members):
   - Follow 0-1 person (mostly inactive)
   - Rarely followed by others
   - Don't vote manually, rely entirely on delegation
   - Leaf nodes in delegation trees

4. **Completely Disengaged** (~10% of members):
   - Don't follow anyone
   - Not followed by anyone
   - Don't vote (ballots never created)
   - Present but inactive in community

**Specific Requirements**:
- **Multi-level chains**: At least 4-5 chains that go 3+ levels deep (A→B→C→D)
- **Circular relationships**: Include 2-3 circular delegation scenarios (A→B→C→A on different tags)
- **Isolated members**: 3-5 members per community who follow no one and are followed by no one
- **Popular nodes**: 2-3 members followed by 5+ people (opinion leaders)
- **Orphan nodes**: 4-5 members who follow others but are never followed
- **Dual inheritance**: Some members follow 2+ people, creating merged inheritance

**Implementation**:
```python
def create_community_delegation_chains(self, users, tag_options):
    """Create realistic delegation with varied engagement levels."""
    
    # Categorize users by engagement level
    highly_engaged = users[:int(len(users)*0.3)]  # 30%
    moderately_engaged = users[int(len(users)*0.3):int(len(users)*0.7)]  # 40%
    low_engaged = users[int(len(users)*0.7):int(len(users)*0.9)]  # 20%
    disengaged = users[int(len(users)*0.9):]  # 10%
    
    # Highly engaged: Follow 2-3 people on specific tags
    for member in highly_engaged:
        num_follows = random.randint(2, 3)
        # Select from other highly engaged or moderately engaged
        # Create Following relationships with specific tags
    
    # Moderately engaged: Follow 1-2 people, sometimes on all tags
    for member in moderately_engaged:
        num_follows = random.randint(1, 2)
        # 50% chance of following on all tags vs specific tags
    
    # Low engaged: Follow 0-1 person, usually on all tags
    for member in low_engaged:
        if random.random() < 0.6:  # 60% follow someone
            # Follow on all tags (empty string)
        # 40% don't follow anyone
    
    # Disengaged: Create no Following relationships
    # These members exist but don't participate in delegation
```

**D. Update Membership Creation for Anonymity**:
- By default, `is_anonymous=True` (Django default)
- Randomly set some members to `is_anonymous=False` (30% of voting members)
- Ensure all lobbyists have `is_anonymous=False`
- Example:
  ```python
  # For voting members
  is_anonymous = random.random() > 0.3  # 30% public, 70% anonymous
  
  # For lobbyists - MUST be public
  if not is_voter:
      is_anonymous = False
  
  membership = Membership.objects.create(
      member=user,
      community=community,
      is_voting_community_member=is_voter,
      is_anonymous=is_anonymous
  )
  ```

**E. Update Command Help**:
```python
help = 'Generate realistic demo communities with delegation chains. Use --reset-database to wipe everything first.'

def add_arguments(self, parser):
    parser.add_argument(
        '--clear-data',
        action='store_true',
        help='Clear existing community data (keeps users)'
    )
    parser.add_argument(
        '--reset-database',
        action='store_true',
        help='DESTRUCTIVE: Wipe entire database and recreate superuser (local only)'
    )
```

**F. Update Success Message**:
Update the final success message to reflect:
- 5 total communities (2 auto-approve, 3 application-required)
- 4 decisions per community (8 total)
- Decision timing variety
- Anonymity distribution
- Superuser creation (if DEBUG mode)
- Example:
```python
self.stdout.write(
    self.style.SUCCESS(
        f'Successfully generated realistic demo data!\n'
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f'Communities:\n'
        f'  • 5 communities: 2 auto-approve (Minions, Springfield), 3 application-required\n'
        f'  • Minions: 30 users, 4 themed decisions\n'
        f'  • Springfield: 30 users, 4 themed decisions\n'
        f'  • Ocean View, Tech Workers, Riverside: 0 users (apply to join)\n'
        f'\nDecisions (8 total):\n'
        f'  • 2 closed (1 hour ago)\n'
        f'  • 2 closing tomorrow (~23 hours)\n'
        f'  • 2 closing in 1 week\n'
        f'  • 2 closing in 2 weeks\n'
        f'\nMembers:\n'
        f'  • ~70% anonymous voting members, 30% public\n'
        f'  • All lobbyists are public (cannot be anonymous)\n'
        f'  • 10 manual voters per community\n'
        f'  • 15+ calculated voters with multi-level delegation chains\n'
        f'  • 5 lobbyists per community\n'
        f'  • 8 test users (A-H) with specific delegation patterns\n'
        f'\nDelegation (Realistic Engagement):\n'
        f'  • 30% highly engaged (follow 2-3 people, form core chains)\n'
        f'  • 40% moderately engaged (follow 1-2 people)\n'
        f'  • 20% low engagement (follow 0-1 person)\n'
        f'  • 10% completely disengaged (no Following relationships)\n'
        f'  • Multi-level chains up to 4+ levels deep\n'
        f'  • Circular delegation relationships included\n'
        f'  • Some members not followed by anyone (orphan nodes)\n'
        f'  • Some members followed by 5+ people (opinion leaders)\n'
        f'  • Diverse tags: governance, budget, environment, safety, etc.\n'
        + (f'\n🔐 Superuser: admin/admin (DEBUG mode)\n' if settings.DEBUG else '')
        + f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
    )
)
```

### 11. Services
**File**: `democracy/services.py`

Check for any references to `ballot.is_anonymous` and update to use `membership.is_anonymous` instead:
- Ballot staging/calculation services
- Tally report generation
- Any anonymity checks

### 12. Template Tags
**File**: `security/templatetags/member_tags.py`

Check if any template tags reference anonymity and update accordingly.

### 13. Decision Creation - Enhanced Themes
**File**: `democracy/management/commands/generate_demo_communities.py`

Replace single decision per community with **4 themed decisions** each with varied timing.

**Decision Timing Strategy**:
- Decision 1: `dt_close = timezone.now() - timedelta(hours=1)` (already closed - 1 hour ago)
- Decision 2: `dt_close = timezone.now() + timedelta(hours=23)` (closes tomorrow at ~noon)
- Decision 3: `dt_close = timezone.now() + timedelta(days=7)` (closes in 1 week)
- Decision 4: `dt_close = timezone.now() + timedelta(days=14)` (closes in 2 weeks)

**Minion Collective Decisions** (4):

1. **"Which Master Should We Follow Next?"** (CLOSED)
   - Description: "Our current master situation is uncertain. Who should lead us into our next adventure?"
   - Choices:
     - "Stay with Gru" - "He's familiar and has great gadgets"
     - "Return to Scarlet Overkill" - "She was stylish and ambitious"
     - "Find El Macho" - "Strong and fearless leader"
     - "Follow Dr. Nefario" - "Smart inventor with freeze ray"
   - Status: Closed 1 hour ago

2. **"Official Minion Language Word of the Month"** (Closes tomorrow)
   - Description: "Vote for the most useful Minionese word that everyone should use more often this month!"
   - Choices:
     - "Bello!" - "Classic greeting, always appropriate"
     - "Poopaye!" - "Versatile exclamation for any situation"
     - "Tulaliloo ti amo" - "Romantic and sophisticated"
     - "Banana" - "Universal word, works for everything"
   - Status: Closes in ~23 hours

3. **"Mandatory Uniform Upgrade Decision"** (Closes in 1 week)
   - Description: "Time to update our iconic look! Which uniform modification should we adopt?"
   - Choices:
     - "Keep Classic Overalls" - "If it ain't broke, don't fix it"
     - "Add Superhero Capes" - "More dramatic and impressive"
     - "Switch to Tuxedos" - "Sophisticated and professional"
     - "Banana Costumes" - "Commit fully to the banana theme"
   - Status: Closes in 7 days

4. **"Weekly Banana Budget Allocation"** (Closes in 2 weeks)
   - Description: "How many bananas should each minion receive per week? This affects our community budget significantly."
   - Choices:
     - "50 bananas per week" - "Conservative, sustainable approach"
     - "75 bananas per week" - "Balanced option for most minions"
     - "100 bananas per week" - "Generous allocation for happy minions"
     - "Unlimited banana access" - "BANANA! (budget concerns irrelevant)"
   - Status: Closes in 14 days

**Springfield Town Council Decisions** (4):

1. **"Donut Shop Zoning Variance for Lard Lad"** (CLOSED)
   - Description: "Lard Lad Donuts wants to expand. Should we approve the zoning variance?"
   - Choices:
     - "Approve Full Expansion" - "More donuts = happier Springfield"
     - "Deny Expansion" - "Keep our small-town character"
     - "Approve with Conditions" - "Require healthy options menu"
     - "Relocate to Edge of Town" - "Compromise solution"
   - Status: Closed 1 hour ago

2. **"School Bus Route Optimization"** (Closes tomorrow)
   - Description: "Springfield Elementary needs updated bus routes. Otto is willing to drive whatever we decide."
   - Choices:
     - "Keep Otto's Current Route" - "Chaotic but familiar"
     - "Hire Professional Driver" - "Safety-first approach"
     - "Add More Stops" - "Convenience for all students"
     - "Reduce Stops for Efficiency" - "Faster routes, less waiting"
   - Status: Closes in ~23 hours

3. **"Nuclear Plant Safety Inspection Frequency"** (Closes in 1 week)
   - Description: "How often should we inspect the power plant? Homer promises to stay awake this time. Probably."
   - Choices:
     - "Daily Inspections" - "Maximum safety, minimum donuts for Homer"
     - "Weekly Inspections" - "Balanced approach, some donuts allowed"
     - "Monthly Inspections" - "Trust Homer more, maximum donuts"
     - "When Homer Remembers" - "The Springfield way"
   - Status: Closes in 7 days

4. **"Annual Ribwich Festival Location"** (Closes in 2 weeks)
   - Description: "Where should we hold this year's legendary Ribwich Festival? The whole town is watching!"
   - Choices:
     - "Town Square" - "Central location, traditional"
     - "Krusty Burger Parking Lot" - "Corporate sponsorship, free fries"
     - "Springfield Stadium" - "Largest capacity, proper facilities"
     - "Cancel Festival" - "Health department concerns"
   - Status: Closes in 14 days

**Implementation**:
```python
def create_test_decisions(self, communities):
    """Create 4 themed decisions per community with varied timing."""
    decisions = []
    
    for community in [minion_community, springfield_community]:
        if community.name == 'Minion Collective':
            community_decisions = self.create_minion_decisions(community)
        else:
            community_decisions = self.create_springfield_decisions(community)
        decisions.extend(community_decisions)
    
    return decisions

def create_minion_decisions(self, community):
    """Create 4 Minion-themed decisions."""
    # Create decisions with varied timing as specified above
    pass

def create_springfield_decisions(self, community):
    """Create 4 Springfield-themed decisions."""
    # Create decisions with varied timing as specified above
    pass
```

### 14. Ballot Page Updates
**File**: `democracy/templates/democracy/decision_detail.html` or ballot template

**Remove Anonymity Checkbox**:
- Delete the anonymity checkbox/toggle from ballot form
- Remove associated form field from `BallotForm` or vote submission form
- Anonymity is now controlled at membership level, not per-ballot

**Disable Closed Decision Voting**:
- Check `if not decision.is_open` in template
- If closed:
  - Disable all star rating inputs (add `disabled` attribute)
  - Replace "Update Vote" button with static text: "Decision Closed"
  - Add visual indication (gray out form, show "🔒 Voting Closed" badge)
- Example:
  ```django
  {% if decision.is_open %}
      <button type="submit" class="btn-primary">Update Vote</button>
  {% else %}
      <div class="text-gray-500 dark:text-gray-400 font-medium">
          🔒 Decision Closed
      </div>
  {% endif %}
  ```

### 15. Forms Updates
**File**: `democracy/forms.py`

**BallotForm or VoteForm**:
- Remove `is_anonymous` field if it exists
- Remove any anonymity-related validation
- Update form docstring to reflect membership-level anonymity
- Ensure form still works with closed decisions (validation should prevent submission)

### 16. Railway Cron Job Documentation
**File**: `docs/DEPLOYMENT.md` or `docs/RAILWAY_CRON_SETUP.md` (NEW)

Create documentation for setting up weekly database reset cron job on Railway.

**Content**:
```markdown
# Railway Cron Job Setup for CrowdVote Demo Reset

## Overview
To keep the demo fresh, we run a weekly database reset that wipes all data and regenerates the demo communities with new users, decisions, and delegation chains.

## Configuration

### 1. Create Cron Service in Railway

1. In your Railway project, create a new service
2. Connect it to the same GitHub repository
3. Set service name: `crowdvote-demo-reset`

### 2. Configure Cron Schedule

In the service settings, add cron schedule:

**For weekly reset every Monday at 12:01 PM UTC**:
```
1 12 * * 1
```

**For daily reset at 12:01 PM UTC**:
```
1 12 * * *
```

Note: Railway cron jobs use UTC time. Adjust for your timezone:
- PST (UTC-8): 12:01 PM PST = 20:01 UTC → `1 20 * * *`
- EST (UTC-5): 12:01 PM EST = 17:01 UTC → `1 17 * * *`
- CST (UTC-6): 12:01 PM CST = 18:01 UTC → `1 18 * * *`

### 3. Set Start Command

Set the service start command to:
```bash
python manage.py generate_demo_communities --reset-database && python manage.py stage_and_tally_ballots
```

**Important**: The command should complete and exit. Railway will run it on schedule.

### 4. Environment Variables

The cron service needs the same environment variables as your main web service:
- `DATABASE_URL` - Use Railway's service reference: `${{Postgres.DATABASE_URL}}`
- `SECRET_KEY` - Same as web service
- `DEBUG` - Set to `False` (prevents superuser creation in production)
- All other Django settings

### 5. Railway Cron Job Requirements

From [Railway's cron job documentation](https://docs.railway.com/reference/cron-jobs):

✅ **Do**:
- Service must exit when task completes
- Minimum frequency: 5 minutes
- Use UTC timezone for scheduling
- Close all database connections before exiting

❌ **Don't**:
- Leave long-running processes open
- Rely on sub-5-minute precision
- Use for web servers or always-on services

### 6. Monitoring

After setup:
1. Check Railway logs for cron execution
2. Verify data resets on schedule
3. Confirm new superuser NOT created (DEBUG=False in production)
4. Test demo communities are accessible

## Troubleshooting

**Cron job not running?**
- Verify cron expression in service settings
- Check if previous execution is still running (Railway skips overlapping jobs)
- Review Railway logs for errors

**Database not resetting?**
- Ensure `DATABASE_URL` environment variable is correct
- Check database connection permissions
- Verify --reset-database flag is working locally first

**Superuser created in production?**
- Check `DEBUG` environment variable is set to `False`
- Command only creates admin/admin when DEBUG=True
```

## Tests to Write/Update

### Test File: `tests/test_models/test_democracy.py`

**New tests**:
1. `test_membership_is_anonymous_defaults_to_true` - Verify default value
2. `test_lobbyist_cannot_be_anonymous_constraint` - Try to create anonymous lobbyist, expect ValidationError
3. `test_voting_member_can_be_anonymous` - Verify voting members can toggle anonymity
4. `test_voting_member_can_be_public` - Verify voting members can be public

### Test File: `tests/test_views/test_community_views.py`

**New tests**:
1. `test_community_detail_shows_member_name_column` - Verify new column appears
2. `test_community_detail_shows_anonymous_for_anonymous_members` - Verify "Anonymous" text
3. `test_community_detail_shows_username_for_public_members` - Verify username link
4. `test_anonymous_members_no_profile_link` - Verify no clickable profile for anonymous

### Test File: `tests/test_views/test_membership_settings.py` (NEW)

**New tests**:
1. `test_membership_settings_modal_opens` - HTMX modal renders correctly
2. `test_toggle_anonymity_on` - Toggle from public to anonymous
3. `test_toggle_anonymity_off` - Toggle from anonymous to public
4. `test_lobbyist_cannot_toggle_anonymity` - Checkbox disabled for lobbyists
5. `test_non_member_cannot_access_settings` - Permission check
6. `test_settings_save_logs_change` - Verify log entry created

### Test File: `tests/test_services/test_tally.py`

**Update existing tests**:
- Any tests checking `ballot.is_anonymous` should check `membership.is_anonymous` instead
- Verify tally reports correctly handle anonymous memberships

### Test File: `tests/test_integration/test_basic_workflows.py`

**Update/add tests**:
1. Test full workflow: Join community → toggle anonymity → vote → verify tally shows "Anonymous"
2. Test lobbyist cannot become anonymous in workflow

### Test File: `tests/test_management_commands/test_generate_demo_communities.py` (NEW)

**New tests**:
1. `test_clear_data_flag` - Verify --clear-data wipes relationships but keeps users
2. `test_reset_database_flag` - Verify --reset-database wipes everything
3. `test_superuser_created_in_debug_mode` - Verify admin/admin created when DEBUG=True
4. `test_no_superuser_in_production` - Verify no superuser created when DEBUG=False
5. `test_additional_communities_created` - Verify 3 new communities exist (Ocean View, Tech Workers, Riverside)
6. `test_additional_communities_not_auto_approve` - Verify new communities require applications
7. `test_membership_anonymity_distribution` - Verify ~70% anonymous, 30% public for voting members
8. `test_lobbyists_never_anonymous` - Verify all lobbyists have is_anonymous=False
9. `test_four_decisions_per_community` - Verify Minions and Springfield each have 4 decisions
10. `test_decision_timing_variety` - Verify mix of closed, closing soon, and future decisions
11. `test_closed_decision_in_past` - Verify first decision has dt_close in the past
12. `test_realistic_delegation_variety` - Verify delegation includes:
    - Some members following multiple people (highly engaged)
    - Some members following no one (disengaged)
    - Some members not followed by anyone (orphan nodes)
    - Multi-level chains (3+ levels deep)
    - At least one circular relationship detected
13. `test_engagement_level_distribution` - Verify ~30% highly engaged, ~40% moderate, ~20% low, ~10% disengaged
14. `test_isolated_members_exist` - Verify 3-5 members per community have no Following relationships in/out

### Test File: `tests/test_forms/test_democracy_forms.py`

**Update tests**:
1. Remove any tests for ballot anonymity field
2. `test_ballot_form_no_anonymity_field` - Verify is_anonymous field removed from form
3. `test_closed_decision_prevents_submission` - Verify form validation rejects votes on closed decisions

### Test File: `tests/test_views/test_ballot_views.py` or `test_decision_views.py`

**New/updated tests**:
1. `test_ballot_page_no_anonymity_checkbox` - Verify checkbox removed from ballot template
2. `test_closed_decision_shows_disabled_ui` - Verify stars disabled and "Decision Closed" shown
3. `test_closed_decision_vote_submission_blocked` - Verify POST to closed decision is rejected
4. `test_open_decision_shows_update_button` - Verify "Update Vote" button appears for open decisions

## Docstring Updates

### 1. Membership Model
Update class docstring (lines 132-157) to include:
- Explanation of membership-level anonymity
- Constraint that lobbyists cannot be anonymous
- Why this approach (auditability while preserving privacy)

### 2. Ballot Model
Update class docstring (lines 673-701) to:
- Remove references to ballot-level anonymity
- Explain that anonymity is determined by membership
- Update any method docstrings that mentioned `is_anonymous`

### 3. New Views and Methods
Add comprehensive docstrings to:
- `membership_settings_modal` - Explain HTMX modal pattern
- `membership_settings_save` - Explain validation and logging
- `create_minion_decisions` - Explain 4 decision creation with timing
- `create_springfield_decisions` - Explain 4 decision creation with timing
- `reset_database_completely` - Explain full database wipe and superuser creation

### 4. Forms
Update docstrings in `democracy/forms.py`:
- `BallotForm` or `VoteForm` - Remove references to ballot-level anonymity
- Explain that anonymity is now at membership level
- Document closed decision validation

## Implementation Notes

1. **Migration Safety**: The field rename should be straightforward, but test on dev data first
2. **Constraint Validation**: Django will validate the constraint on save, but also validate in the form
3. **Tally Reports**: Ensure tally snapshot generation uses membership anonymity, not ballot anonymity
4. **Network Visualization**: Anonymous nodes should still show delegation edges (structure matters for audit)
5. **Logging**: Log anonymity changes to crowdvote.log: "User {username} changed anonymity to {True/False} in community {community_name}"
6. **Database Reset Order**: 
   - Must delete in reverse foreign key order: Vote → Ballot → Choice → Decision → Following → Membership → Community → User
   - Only create superuser if `settings.DEBUG == True`
   - Import settings at top: `from django.conf import settings`
7. **Community Loop Logic**: 
   - Only create users/memberships for Minions and Springfield
   - Skip user creation for the 3 new communities
   - Update loop: `for community in [minion_community, springfield_community]:`
8. **Flag Handling**:
   - `--reset-database` should call new method `reset_database_completely()`
   - `--clear-data` should keep existing behavior (just relationships)
   - If both flags provided, `--reset-database` takes precedence
9. **Decision Creation Timing**:
   - Use `timezone.now()` as base time
   - Closed decision: `timezone.now() - timedelta(hours=1)`
   - Tomorrow: `timezone.now() + timedelta(hours=23)` 
   - 1 week: `timezone.now() + timedelta(days=7)`
   - 2 weeks: `timezone.now() + timedelta(days=14)`
   - When reset runs, timing is relative to that moment
10. **Ballot Page Updates**:
    - Find and remove anonymity checkbox/field from template
    - Add `{% if decision.is_open %}` check around form submit button
    - Add `disabled` attribute to star inputs when closed
    - Test both open and closed decision rendering
11. **Forms.py Updates**:
    - Check if `BallotForm` or similar has `is_anonymous` field
    - Remove field and any related validation
    - Update form `__init__` or `clean` methods if they reference anonymity
12. **Backwards Compatibility**:
    - Existing ballots with `is_anonymous` will need migration
    - Consider data migration to set membership anonymity based on ballot history
    - Or just accept new system going forward (simpler)

## Algorithm: Anonymity Display Logic

For any display of member identity:
```
1. Get membership for user in community
2. If membership.is_anonymous:
   - Display "Anonymous" (no link)
   - Show user's first/last name in "Member" column (for managers to identify)
3. Else:
   - Display @username with link to profile
   - Show user's first/last name in "Member" column
```

## Validation Logic

When saving membership settings:
```
1. Get membership
2. If not membership.is_voting_community_member (is lobbyist):
   - Reject if trying to set is_anonymous=True
   - Return error: "Lobbyists cannot vote anonymously"
3. Else:
   - Allow any is_anonymous value (True or False)
   - Save and log change
```

## Usage Examples

### Full Database Reset (Local Development)
```bash
# Complete wipe + fresh start with admin user
docker-compose exec web python manage.py generate_demo_communities --reset-database

# Result:
# - All data wiped
# - Superuser created: admin/admin (local only)
# - 5 communities created (2 with users, 3 empty)
# - 60 users with delegation chains
# - Decisions and votes created
```

### Clear Data Only (Preserve Users)
```bash
# Clear relationships but keep user accounts
docker-compose exec web python manage.py generate_demo_communities --clear-data

# Result:
# - Communities, decisions, memberships, votes cleared
# - User accounts preserved
# - Fresh communities and relationships created
```

### Normal Run (Add/Update)
```bash
# Add data without clearing existing
docker-compose exec web python manage.py generate_demo_communities

# Result:
# - Creates communities if they don't exist
# - Creates users if they don't exist
# - Updates existing data where appropriate
```

## Summary

This plan covers a comprehensive refactoring of CrowdVote's anonymity system along with major enhancements to the demo data generation and deployment infrastructure.

### Core Changes (Phase 1 - Anonymity System)
1. **Database**: Rename `Membership.is_anonymous_by_default` → `is_anonymous` with constraint preventing anonymous lobbyists
2. **Models**: Update Membership and Ballot models, remove ballot-level anonymity
3. **UI**: Add "Member" column to community detail, show "Anonymous" for anonymous users
4. **Forms**: Remove anonymity field from ballot forms
5. **Views**: Add membership settings modal for toggling anonymity
6. **Network Viz**: Show "Anonymous" nodes in delegation network
7. **Ballot Page**: Remove anonymity checkbox, disable voting on closed decisions
8. **Tests**: 20+ new/updated tests across models, views, forms, integration

### Demo Data Enhancements (Phase 2)
9. **Database Reset**: `--reset-database` flag for complete wipe + superuser creation (local only)
10. **5 Communities**: 2 auto-approve (Minions, Springfield) + 3 application-required (Ocean View, Tech Workers, Riverside)
11. **8 Themed Decisions**: 4 per community with fun, show-specific scenarios
12. **Varied Timing**: Closed, closing tomorrow, closing in 1 week, closing in 2 weeks
13. **Anonymity Distribution**: 70% anonymous voting members, 30% public, all lobbyists public
14. **Enhanced Output**: Beautiful formatted success message with statistics

### Deployment Infrastructure (Phase 3)
15. **Railway Cron Jobs**: Complete documentation for automated weekly resets
16. **Production Safety**: Prevents superuser creation when DEBUG=False
17. **Timezone Handling**: UTC-based scheduling with conversion examples
18. **Monitoring**: Log verification and troubleshooting guide

### Files Modified
- **Models**: `democracy/models.py` (Membership, Ballot)
- **Migrations**: New migration for field rename + constraint
- **Templates**: `community_detail.html`, ballot templates, new membership settings modal
- **Views**: `democracy/views.py` (3 new views, 1 updated)
- **Forms**: `democracy/forms.py` (remove anonymity field)
- **Management Command**: `generate_demo_communities.py` (major enhancements)
- **Services**: `democracy/services.py` (anonymity reference updates)
- **URLs**: `democracy/urls.py` (2 new patterns)
- **Documentation**: New `RAILWAY_CRON_SETUP.md`
- **Tests**: 8 test files with 30+ new/updated tests

### Expected Impact
- **Users**: Clear anonymity controls, better demo experience
- **Developers**: Easier local development with `--reset-database`
- **Production**: Automated weekly demo refresh, fresh data for visitors
- **Auditability**: Maintained while preserving privacy (lobbyists always visible)

### Implementation Order
1. Migration + model changes (Membership, Ballot)
2. Remove ballot anonymity checkbox from templates/forms
3. Add membership settings modal + views
4. Update community detail table UI
5. Enhance generate_demo_communities command
6. Update all tests and docstrings
7. Create Railway cron job documentation
8. Test locally with `--reset-database`
9. Deploy and configure Railway cron job

