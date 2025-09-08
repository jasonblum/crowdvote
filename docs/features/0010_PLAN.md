# Feature #10: Enhanced Delegation Tree Visualization & Member Profiles

## Overview

Unify and enhance the delegation tree visualization across CrowdVote by applying the hierarchical ASCII tree format from the Community Detail page to the Decision Results page. Additionally, implement comprehensive member profile pages with biographies, avatars, social links, and tag history. Create consistent visual delegation trees throughout the application with clickable usernames linking to rich member profiles.

## Context

Currently, CrowdVote has two different delegation visualizations:
1. **Community Detail Page**: Beautiful hierarchical ASCII tree with proper nesting, Unicode characters (└─, │), and tag display
2. **Decision Results Page**: Flat list of voters without hierarchical structure

The Community Detail tree shows **all members and their delegation relationships**, while the Decision Results tree should show **only voting participants and their delegation chains for that specific decision**. Both need consistent formatting and clickable usernames linking to member profiles.

## Technical Requirements

### Phase 1: Decision Results Tree Visualization Enhancement

**Enhanced Decision Results Template (`democracy/templates/democracy/decision_results.html`)**:
- Replace flat voter list with hierarchical ASCII tree visualization
- Apply same formatting as Community Detail page using Unicode characters (└─, │, ├─)
- Show only members who voted or whose votes were calculated for this decision
- Display tag inheritance chains with proper nesting levels
- Include vote values (stars) alongside delegation relationships

**Tree Structure for Decision Results (Clean Delegation Flow)**:
```
🗳️ DECISION PARTICIPATION TREE
═══════════════════════════════════════

👤 B_minion (Calculated: ⭐⭐⭐⭐⭐) [Tags: governance]
└─ 📋 governance (priority: 1)
    └─ A_minion (Manual Vote: ⭐⭐⭐⭐⭐) [Tags: governance]

👤 E_minion (Calculated: ⭐⭐⭐⭐⭐) [Tags: governance] 
└─ 📋 governance (priority: 1)
    └─ C_minion (Calculated: ⭐⭐⭐⭐⭐) [Tags: governance]
        └─ 📋 governance (priority: 1)
            └─ A_minion (Manual Vote: ⭐⭐⭐⭐⭐) [Tags: governance]

👤 F_minion (Calculated: ⭐⭐⭐⭐⭐) [Tags: governance]
└─ 📋 all topics (priority: 1)
    └─ C_minion (Calculated: ⭐⭐⭐⭐⭐) [Tags: governance]
        └─ 📋 governance (priority: 1)
            └─ A_minion (Manual Vote: ⭐⭐⭐⭐⭐) [Tags: governance]

👤 stuart_minion (Calculated: ⭐⭐⭐☆☆) [Tags: operations]
└─ 📋 operations (priority: 1)
    └─ kevin_minion (Manual Vote: ⭐⭐⭐☆☆) [Tags: operations]

👤 Anonymous Voter #A1B2C3 (Calculated: ⭐⭐☆☆☆) [Tags: budget]
└─ 📋 budget (priority: 1)
    └─ marge_simpson (Manual Vote: ⭐⭐☆☆☆) [Tags: budget]
```

**Key Differences from Community Tree**:
- Shows only decision participants (voters + calculated voters)
- Includes vote values (star ratings) for each participant  
- Displays "Manual Vote" vs "Calculated" indicators
- **Tag Inheritance Display**: Shows both original tags and inherited tags
- **Clickable Usernames**: All non-anonymous usernames link to member profiles
- **Anonymous Handling**: Anonymous voters show as "Anonymous Voter #UUID" without links
- **Clean Tree Structure**: No stray connecting lines, proper indentation
- **Delegation Flow Structure**: Shows Follower → Tag → Followee (who they delegate to)
- Tree structure reflects actual vote inheritance for this specific decision
- Filtered to only include members with ballots for this decision

**Correct Delegation Flow Logic**:
- **Root nodes**: People who delegate (followers/voters)
- **Tag nodes**: The topics they delegate on (governance, budget, etc.)
- **Leaf nodes**: People they delegate to (followees/experts)
- **Multi-level chains**: E_minion → governance → C_minion → governance → A_minion
- **Clean Indentation**: Proper prefix-based tree structure without visual artifacts

### Phase 2: Member Profile System

**New Member Profile Model Enhancement (`accounts/models.py`)**:
- Add `bio` TextField for member biographies
- Add `website_url`, `twitter_url`, `linkedin_url` fields for social links
- Add `location` CharField for member location
- Add `joined_date` for membership timeline

**Member Profile View (`accounts/views.py`)**:
- `member_profile(request, community_id, member_id)` - Display member profile
- `edit_profile(request)` - Allow users to edit their own profiles
- Show member's communities, roles, and participation statistics
- Calculate and display tag usage frequency (tags they've used, not inherited)
- Show delegation relationships (who they follow, who follows them)

**Tag Usage Frequency Logic**:
```python
def get_member_tag_usage(member):
    """
    Calculate frequency of tags used by member in their manual votes.
    Returns list of tuples: [('governance', 5), ('budget', 3), ('environment', 1)]
    """
    from django.db.models import Count
    from collections import Counter
    
    # Get all manual ballots by this member (not calculated/inherited)
    manual_ballots = Ballot.objects.filter(
        voter=member, 
        is_calculated=False
    ).exclude(tags='')
    
    # Count tag usage frequency
    tag_counter = Counter()
    for ballot in manual_ballots:
        if ballot.tags:
            tags = [tag.strip() for tag in ballot.tags.split(',')]
            for tag in tags:
                if tag:  # Skip empty tags
                    tag_counter[tag] += 1
    
    # Return sorted by frequency (most used first)
    return tag_counter.most_common()
```

**Member Profile Template (`accounts/templates/accounts/member_profile.html`)**:
```html
<!-- Member Profile Layout -->
<div class="member-profile">
    <!-- Profile Header -->
    <div class="profile-header">
        <h1>{{ member.get_full_name|default:member.username }}</h1>
        <p class="location">📍 {{ member.location }}</p>
        <div class="social-links">
            <!-- Twitter, LinkedIn, Website links -->
        </div>
    </div>
    
    <!-- Biography -->
    <div class="biography">
        <h2>About {{ member.username }}</h2>
        <p>{{ member.bio|default:"No biography provided." }}</p>
    </div>
    
    <!-- Community Participation -->
    <div class="communities">
        <h2>Communities</h2>
        <!-- List of communities with roles -->
    </div>
    
    <!-- Tags Used -->
    <div class="tags-used">
        <h2>Expertise Tags</h2>
        <p>Tags {{ member.username }} has used when voting (not inherited):</p>
        <div class="tag-frequency-list">
            {% for tag, count in member_tag_usage %}
                <span class="tag-badge">
                    {{ tag }} ({{ count }})
                </span>
            {% empty %}
                <p class="text-gray-500">No tags used yet.</p>
            {% endfor %}
        </div>
    </div>
    
    <!-- Delegation Network -->
    <div class="delegation-network">
        <h2>Delegation Network</h2>
        <div class="following">
            <h3>Following</h3>
            <!-- Who this member follows -->
        </div>
        <div class="followers">
            <h3>Followers</h3>
            <!-- Who follows this member -->
        </div>
    </div>
</div>
```

### Phase 3: Universal Username Linking

**Template Enhancement Across All Pages**:
- Create reusable template tag for username display: `{% username_link user community %}`
- Apply to all delegation trees (Community Detail and Decision Results)
- Apply to all voter lists and member directories
- Apply to all decision result displays

**Template Tag Implementation (`accounts/templatetags/member_tags.py`)**:
```python
@register.inclusion_tag('accounts/components/username_link.html')
def username_link(user, community=None):
    """
    Render a clickable username link to member profile.
    
    Args:
        user: User object to link to
        community: Community context for profile link
    """
    return {
        'user': user,
        'community': community,
        'profile_url': reverse('accounts:member_profile', args=[community.id, user.id])
    }
```

**Username Link Component (`accounts/templates/accounts/components/username_link.html`)**:
```html
<a href="{% url 'accounts:member_profile' community.id user.id %}" 
   class="username-link hover:text-blue-600 transition-colors">
    {{ user.get_full_name|default:user.username }}
</a>
```

### Phase 4: Tree Visualization Service Layer

**Enhanced Tree Building Service (`democracy/views.py`)**:
- `build_influence_tree(community, include_links=True)` - Updated with username linking
- Uses prefix-based tree structure to prevent visual artifacts
- `format_username(user)` helper for HTML link generation
- Clean indentation logic: `followee_prefix = prefix + ("    " if is_last_delegation else "│   ")`
- Template renders tree as `{{ tree_text|safe }}` to enable HTML links
- Create `build_decision_delegation_tree(decision)` method for decision-specific trees
- Filter to only include decision participants (voters + calculated voters)
- Include vote data (stars, manual vs calculated) and tag inheritance in tree nodes

**Tree Data Structure**:
```python
decision_tree = {
    'tree_text': '🗳️ DECISION PARTICIPATION TREE\n═══════...',
    'has_relationships': True,
    'stats': {
        'total_participants': 34,
        'manual_voters': 16,
        'calculated_voters': 18,
        'delegation_chains': 12
    },
    'nodes': [
        {
            'username': 'A_minion',
            'vote_type': 'manual',
            'stars': 5,
            'children': [
                {
                    'username': 'B_minion',
                    'vote_type': 'calculated',
                    'stars': 5,
                    'tags': ['governance'],
                    'priority': 1
                }
            ]
        }
    ]
}
```

## User Experience Requirements

### Visual Design Consistency
- **Unified Tree Format**: Both community and decision trees use identical Unicode characters (└─, │, ├─)
- **Clear Hierarchy**: Proper indentation showing delegation depth levels
- **Vote Integration**: Star ratings displayed alongside delegation relationships on decision trees
- **Tag Display**: Consistent tag formatting with priority indicators
- **Clickable Usernames**: All usernames link to member profiles throughout the application

### Member Profile Experience
- **Rich Profiles**: Comprehensive member information with biography and social links
- **Expertise Display**: Clear indication of member's area of expertise through original tags
- **Delegation Insights**: Visual representation of who they follow and who follows them
- **Community Context**: Profile shows member's role and participation in specific community
- **Privacy Controls**: Members can control visibility of personal information

### Navigation Flow
1. **Community Detail → Member Profile**: Click username in delegation tree
2. **Decision Results → Member Profile**: Click username in participation tree
3. **Member Profile → Community Detail**: Navigate back to community context
4. **Member Profile → Edit Profile**: Allow users to edit their own profiles

## Implementation Details

### Database Schema Updates
```sql
-- Add profile fields to User model
ALTER TABLE accounts_customuser ADD COLUMN bio TEXT;
ALTER TABLE accounts_customuser ADD COLUMN website_url VARCHAR(200);
ALTER TABLE accounts_customuser ADD COLUMN twitter_url VARCHAR(200);
ALTER TABLE accounts_customuser ADD COLUMN linkedin_url VARCHAR(200);
ALTER TABLE accounts_customuser ADD COLUMN location VARCHAR(100);
```

### URL Structure
```python
# accounts/urls.py
urlpatterns = [
    path('communities/<uuid:community_id>/members/<uuid:member_id>/', 
         views.member_profile, name='member_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]
```

### Template Integration Points
- `democracy/templates/democracy/community_detail.html` - Update delegation tree usernames
- `democracy/templates/democracy/decision_results.html` - Replace flat list with hierarchical tree
- `democracy/templates/democracy/components/delegation_tree.html` - Add username links
- All voter lists and member directories throughout application

## Success Criteria

### Functional Requirements
- ✅ Decision results show hierarchical delegation tree with vote values
- ✅ Tree format matches community detail page (Unicode characters, nesting)
- ✅ All usernames throughout application link to member profiles
- ✅ Member profiles show biography, avatar, social links, and expertise tags
- ✅ Delegation networks visible on member profiles (following/followers)
- ✅ Only original tags displayed (not inherited tags)
- ✅ Consistent tree visualization across community and decision pages

### User Experience Goals
- **Visual Consistency**: Unified delegation tree format across all pages
- **Member Discovery**: Rich profiles help users identify delegation targets
- **Social Context**: Member profiles provide context for delegation decisions
- **Navigation Flow**: Seamless movement between trees, profiles, and communities
- **Expertise Identification**: Clear indication of member areas of expertise

### Technical Goals
- **Reusable Components**: Template tags and services work across all pages
- **Performance**: Efficient profile loading with proper query optimization
- **Responsive Design**: Member profiles work on all device sizes
- **Privacy Controls**: Appropriate visibility controls for personal information

## Files to Create/Modify

### New Files
- `accounts/templates/accounts/member_profile.html` - Member profile page
- `accounts/templates/accounts/edit_profile.html` - Profile editing form
- `accounts/templates/accounts/components/username_link.html` - Reusable username link
- `accounts/templatetags/member_tags.py` - Username linking template tags
- `accounts/migrations/00XX_add_profile_fields.py` - Database migration

### Modified Files
- `accounts/models.py` - Add profile fields to CustomUser model
- `accounts/views.py` - Add member_profile and edit_profile views
- `accounts/urls.py` - Add profile URL patterns
- `democracy/views.py` - Add build_decision_delegation_tree method
- `democracy/templates/democracy/decision_results.html` - Replace flat list with tree
- `democracy/templates/democracy/community_detail.html` - Add username links
- `accounts/forms.py` - Add profile editing form

## Development Notes

### Tree Visualization Logic
- Community tree shows all delegation relationships regardless of voting
- Decision tree shows only relationships that resulted in vote inheritance for that decision
- Both trees use identical visual formatting for consistency
- Vote values (stars) only displayed on decision trees where relevant

### Member Profile Privacy
- Members control visibility of biography, location, and social links
- Username and basic community participation always visible
- Original tags with usage frequency always visible (helps with delegation decisions)

### Performance Considerations
- Profile pages should use select_related for efficient loading
- Tree building should cache results when possible
- Large delegation networks may need pagination or collapse/expand functionality
- Tag frequency calculation should be optimized for users with many ballots

This feature will create a cohesive, professional delegation visualization system with rich member profiles that help users make informed delegation decisions while maintaining visual consistency throughout CrowdVote.
