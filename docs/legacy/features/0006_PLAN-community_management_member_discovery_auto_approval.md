# Feature 0006: Community Management & Member Discovery System

## Overview

Complete the community management foundation that enables users to discover, join, and explore communities with their members. This creates the social layer necessary for delegation-based voting by allowing users to browse community members and identify potential people to follow on specific topics.

## Context & User Journey

Before users can meaningfully participate in voting and delegation, they need to:
1. **Join Communities**: Apply and get accepted (auto-approval for demo)
2. **Explore Members**: Browse community member lists to find experts
3. **Understand Roles**: See who are voters vs. lobbyists vs. managers
4. **Community Information**: Rich community pages with descriptions and activity
5. **Member Profiles**: Basic member information to aid in delegation decisions

This foundation enables the social discovery necessary for trust-based delegation networks.

## Technical Requirements

### 1. Auto-Approval System for Demo

**Current State**: Applications require manual approval via Django admin
**Demo Need**: Instant approval so friends can immediately explore communities

**Implementation:**
- Add `auto_approve_applications` boolean field to Community model
- For demo communities (Minion Collective, Springfield), set to True
- Modify application view to automatically approve and create membership
- Maintain manual approval option for production communities

### 2. Community Detail Pages

**URL Structure:**
- `/communities/` - List all communities (existing community_discovery view)
- `/communities/<uuid:id>/` - Individual community detail page

**Community Detail Features:**
- Community description and statistics (member count, active decisions)
- Complete member list with roles (voters, lobbyists, managers)
- Recent decisions and their outcomes
- Application status for current user
- Join/Leave community actions

### 3. Member List & Role Display

**Member List Features:**
- Filterable by role: All Members | Voters | Lobbyists | Managers
- Search functionality to find specific members
- Member information: username, join date, role badges
- Link to member profiles (future: for delegation decisions)

**Role Badge System:**
```python
# In Membership model
@property
def role_badges(self):
    badges = []
    if self.is_community_manager:
        badges.append({"label": "Manager", "class": "bg-purple-100 text-purple-800"})
    if self.is_voting_community_member:
        badges.append({"label": "Voter", "class": "bg-green-100 text-green-800"})
    else:
        badges.append({"label": "Lobbyist", "class": "bg-blue-100 text-blue-800"})
    return badges
```

### 4. Community Management Interface

**Manager Permissions** (for community managers only):
- Edit community description
- Approve/reject membership applications
- Remove members from community
- Publish decisions to community docket
- View member statistics and activity

**Restrictions:**
- Managers CANNOT create or delete communities (superuser only)
- Managers CANNOT change other members' roles
- Managers CANNOT see anonymous vote mappings

### 5. Enhanced Community Model

**Additional Fields:**
```python
class Community(BaseModel):
    # Existing fields: name, description, members
    
    auto_approve_applications = models.BooleanField(
        default=False,
        help_text="Automatically approve membership applications (demo mode)"
    )
    
    member_count_display = models.BooleanField(
        default=True,
        help_text="Show member count publicly"
    )
    
    application_message_required = models.BooleanField(
        default=False,
        help_text="Require application message from users"
    )
```

### 6. Membership Statistics & Analytics

**Community Analytics:**
- Total members, voting members, lobbyists, managers
- Recent application activity
- Decision participation rates
- Growth trends (for managers only)

### 7. User Dashboard Integration

**My Communities Section:**
- List of communities user belongs to
- Application status for pending applications
- Quick links to community details and active decisions
- Notification badges for new decisions or applications (future)

## User Stories

### Primary User Stories
1. **As a new user**, I want to see all available communities and join ones that interest me
2. **As a community member**, I want to browse other members to understand who I might follow
3. **As a community manager**, I want to review and approve applications efficiently
4. **As a user**, I want to understand the different roles (voter/lobbyist/manager) in communities
5. **As a demo user**, I want to join communities instantly without waiting for approval

### Secondary User Stories
6. **As a community member**, I want to see community activity and recent decisions
7. **As a community manager**, I want to edit community descriptions and settings
8. **As a user**, I want to leave communities I no longer want to participate in
9. **As a community manager**, I want to see member statistics and engagement
10. **As a user**, I want to find communities by topic or interest area (future)

## Implementation Phases

### Phase 1: Auto-Approval & Community Details
- Add auto_approve_applications field to Community model
- Implement community detail view with member lists
- Auto-approval logic for demo communities
- Enhanced community_discovery page

### Phase 2: Member Management Interface
- Role badge system and member filtering
- Community management dashboard for managers
- Member search and profile views
- Leave community functionality

### Phase 3: Analytics & Enhancement
- Community statistics and analytics
- Enhanced user dashboard with community overview
- Application management interface
- Member activity tracking

## Files to Create/Modify

### New Files
- `democracy/templates/democracy/community_detail.html` - Community detail page
- `democracy/templates/democracy/community_manage.html` - Manager interface
- `democracy/templates/democracy/member_list.html` - Member list component

### Modified Files
- `democracy/models.py` - Add auto_approve_applications field
- `democracy/views.py` - Community detail and management views
- `democracy/urls.py` - Community detail URL patterns
- `accounts/views.py` - Auto-approval logic in apply_to_community
- `accounts/templates/accounts/community_discovery.html` - Enhanced UI

### Migrations
- `democracy/migrations/0006_add_community_auto_approval.py`

## Permissions & Security

### Community Manager Permissions
- Edit community description and settings
- Approve/reject membership applications
- Remove members (except other managers)
- Publish decisions to community
- View member statistics

### User Permissions
- View public community information
- Apply to join communities
- Leave communities they belong to
- View member lists of communities they belong to

### Superuser Permissions
- Create and delete communities
- Promote/demote community managers
- Override any community settings
- Access anonymous vote mappings (future feature)

## Anonymity Considerations

### Future Anonymous Voting System
While not implemented in this phase, the architecture prepares for:

**Anonymous Vote Mapping:**
```python
class AnonymousVote(BaseModel):
    """Secure mapping for anonymous votes (heavily encrypted)"""
    decision = models.ForeignKey(Decision)
    user = models.ForeignKey(CustomUser)
    anonymous_guid = models.UUIDField(unique=True)
    
    class Meta:
        # This table would be encrypted at database level
        # Only accessible to system, not even superusers
        db_table = 'anonymous_votes_secure'
```

**Member Display Logic:**
- Community detail page: Always shows real usernames (all 100 members)
- Decision page: Shows mix of real names + GUIDs based on user preference
- Count verification: Both pages show same total count for trust
- Follow paths: Work with both real names and anonymous GUIDs

### is_anonymous_by_default Field
**Current Implementation**: Field exists in Membership model
**Future Use**: 
- `True`: Member votes anonymously unless they explicitly choose otherwise
- `False`: Member votes publicly unless they explicitly choose to be anonymous
- Per-decision override: Users can always change anonymity for specific decisions

**Example Scenarios:**
- **Mauricio (Activist)**: `is_anonymous_by_default=False` - wants to build influence publicly
- **Private Citizen**: `is_anonymous_by_default=True` - prefers anonymity by default
- **Both can override per decision** for sensitive votes

## Success Criteria

### Demo Readiness
- Friends can create accounts and join communities instantly
- Rich community pages show member lists and activity
- Clear role distinctions (voter/lobbyist/manager)
- Community managers can edit descriptions and approve applications

### Foundation for Voting
- Users can discover other community members
- Role system clearly indicates who can be followed vs. who votes count
- Member lists provide context for delegation decisions
- Community structure supports the social trust networks needed for delegation

### Production Scalability
- Permission system supports real community management
- Auto-approval can be disabled for production communities
- Community growth and engagement tracking
- Secure foundation for future anonymous voting features

## Next Phase Integration

This community management foundation directly enables:
- **Voting Interface**: Users know their communities and can vote on decisions
- **Delegation Management**: Users can browse members to find experts to follow
- **Member Discovery**: Rich member profiles help users make delegation decisions
- **Anonymous Voting**: Architecture prepared for secure anonymous vote mapping

The social layer is essential before the democratic participation layer can be meaningful.
