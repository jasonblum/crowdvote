# Feature 0005: Authentication & Community Onboarding System

## Overview

Implement a complete user authentication and onboarding system using django-allauth with magic link login, safe username generation, and community membership application workflow. This creates the foundation for users to actually interact with CrowdVote's democratic processes.

## Context & User Journey

Users will experience this flow:
1. **Landing Page**: Clean welcome with email input
2. **Magic Link Login**: Email-based authentication (no passwords)
3. **Profile Setup**: Safe username generation with HTMX validation
4. **Community Discovery**: Browse and apply to join communities  
5. **Membership Approval**: Community managers approve applications
6. **Democratic Participation**: Vote and delegate within approved communities

## Technical Requirements

### 1. Authentication System (django-allauth)

**Dependencies:**
- `django-allauth` - Email-based authentication with magic links
- `wonderwords` - Safe, family-friendly word generation for usernames

**Key Features:**
- Magic link email authentication (no password required)
- Custom signup flow with profile completion
- Email verification and user activation
- Integration with existing CustomUser model

**Settings Configuration:**
```python
# Email-only authentication
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False  # We'll generate usernames
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_BY_CODE_ENABLED = True  # Magic links
ACCOUNT_PASSWORD_MIN_LENGTH = None  # No passwords needed
```

### 2. Safe Username Generation

**Algorithm:**
- Use `wonderwords` library for safe adjective + noun combinations
- Examples: "WiseElephant", "QuietGardener", "BrightMountain"
- Fallback to number suffix if collision: "WiseElephant2"
- HTMX real-time availability checking
- Blacklist filtering for edge cases

**Implementation:**
```python
from wonderwords import RandomWord

def generate_safe_username():
    """Generate family-friendly username with collision handling"""
    r = RandomWord()
    while True:
        adjective = r.word(word_min_length=4, word_max_length=8, 
                          include_parts_of_speech=["adjectives"])
        noun = r.word(word_min_length=4, word_max_length=8,
                     include_parts_of_speech=["nouns"])
        username = f"{adjective.title()}{noun.title()}"
        
        # Check availability with collision handling
        if not CustomUser.objects.filter(username__iexact=username).exists():
            return username
        
        # Try with number suffix
        for i in range(2, 100):
            numbered = f"{username}{i}"
            if not CustomUser.objects.filter(username__iexact=numbered).exists():
                return numbered
```

### 3. Community Membership System

**Models Enhancement:**
```python
class CommunityApplication(BaseModel):
    """User application to join a community"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'), 
        ('rejected', 'Rejected')
    ], default='pending')
    application_message = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(CustomUser, null=True, blank=True, 
                                   on_delete=models.SET_NULL, related_name='reviewed_applications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'community']
```

**Community Management:**
- Auto-approve for public communities
- Application workflow for private communities
- Email notifications to community managers
- Dashboard for reviewing applications

### 4. HTMX Integration Points

**Real-time Features:**
- Username availability checking during profile setup
- Community application status updates
- Live membership approval notifications
- Dynamic form validation feedback

**HTMX Patterns:**
```html
<!-- Username availability check -->
<input name="username" 
       hx-post="{% url 'check_username' %}"
       hx-trigger="keyup changed delay:500ms"
       hx-target="#username-feedback">

<!-- Community application -->
<button hx-post="{% url 'apply_community' community.id %}"
        hx-target="#application-status">
    Apply to Join
</button>
```

## Implementation Phases

### Phase 1: Core Authentication (Priority: High)
1. **Install and Configure django-allauth**
   - Add to requirements.txt and settings.py
   - Configure email backend for magic links
   - Set up URL routing

2. **Create Landing Page**
   - Clean, welcoming design with Tailwind CSS
   - Email input with magic link request
   - CrowdVote branding and tagline

3. **Profile Setup Flow**
   - Post-login redirect to profile completion
   - Safe username generation with wonderwords
   - Basic profile fields (bio, avatar placeholder)

### Phase 2: Community System (Priority: High)
1. **Community Application Model**
   - Create CommunityApplication model and migrations
   - Admin interface for community managers

2. **Community Discovery Page**
   - List all communities with public/private indicators
   - Member counts and community descriptions
   - Apply/Join buttons with appropriate logic

3. **Application Management**
   - Email notifications for new applications
   - Manager dashboard for approving/rejecting
   - User notification of application status

### Phase 3: HTMX Enhancement (Priority: Medium)
1. **Real-time Username Validation**
   - HTMX endpoint for availability checking
   - Visual feedback during typing
   - Smooth user experience

2. **Dynamic Community Interaction**
   - Real-time application status updates
   - Live membership notifications
   - Progressive enhancement patterns

### Phase 4: Integration & Polish (Priority: Medium)
1. **Connect to Existing Democracy**
   - Link authenticated users to voting system
   - Profile-based delegation setup
   - Community-specific decision viewing

2. **Email System**
   - Magic link email templates
   - Application notification emails
   - Welcome and onboarding emails

## Files to Create/Modify

### New Files:
- `accounts/forms.py` - Custom allauth forms
- `accounts/adapters.py` - Allauth customization
- `accounts/utils.py` - Username generation utilities
- `accounts/migrations/0005_community_application.py`
- `templates/account/` - Allauth template overrides
- `templates/communities/` - Community browsing and application
- `templates/onboarding/` - Profile setup flow

### Modified Files:
- `requirements.txt` - Add django-allauth, wonderwords
- `crowdvote/settings.py` - Allauth configuration
- `crowdvote/urls.py` - Include allauth URLs
- `accounts/models.py` - CommunityApplication model
- `accounts/admin.py` - Application management
- `democracy/models.py` - Link to authentication

## User Experience Goals

### Seamless Onboarding:
- Single email input to get started
- No password friction
- Guided profile setup
- Clear community joining process

### Trust and Safety:
- Family-friendly usernames
- Community manager approval
- Clear application process
- Transparent membership status

### Progressive Enhancement:
- Works without JavaScript
- Enhanced with HTMX interactions
- Responsive design with Tailwind
- Accessible for all users

## Success Metrics

- **Authentication Flow**: Email → Magic Link → Profile → Community (< 3 minutes)
- **Username Quality**: 0% offensive usernames, 100% availability checking
- **Community Joining**: Clear application process with manager notifications
- **HTMX Enhancement**: Real-time feedback without page reloads

## Future Integration Points

- **Voting Interface**: Authenticated users can vote and delegate
- **Democracy Dashboard**: Personal influence and trust networks
- **Real-time Reports**: Watch democracy happen live
- **Community Management**: Advanced moderation tools

## Notes

This feature creates the essential user foundation for CrowdVote. Once complete, we'll have:
- Real users with safe, memorable usernames
- Community membership with approval workflows  
- Integration hooks for democratic participation
- HTMX-enhanced user experience

The magic link authentication removes password friction while maintaining security. The wonderwords username generation ensures family-friendly, memorable identities. The community application system builds trust and prevents spam while maintaining openness.

Next: Connect this authentication system to the voting interface for complete democratic participation.
