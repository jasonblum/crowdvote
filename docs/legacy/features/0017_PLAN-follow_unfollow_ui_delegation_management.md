# Plan #17: Follow/Unfollow UI & Delegation Management Interface

## Overview

**Current State**: Complete delegation backend with Following model, tag-based delegation, and vote inheritance working. Zero user interface for creating or managing following relationships.

**Target Goal**: Build comprehensive follow/unfollow UI and delegation management interface so users can actually create and manage their delegation relationships through the web interface.

**Primary Impact**: Transform CrowdVote from a backend-only delegation system into a fully user-facing democratic platform where members can build trust networks and delegate voting power.

## Context & Motivation

The delegation system backend is complete and functional:
- ✅ `Following` model with tags, order, and validation
- ✅ Vote inheritance through delegation chains  
- ✅ Tag-based delegation (follow Alice on "budget", Bob on "environment")
- ✅ Delegation tree visualization and transparency
- ✅ Multi-level delegation chains working correctly

**Critical Gap**: Users cannot create, modify, or manage following relationships through the UI. The system has all the democratic infrastructure but no way for users to actually participate in delegation.

## Technical Requirements

### Phase 1: Follow/Unfollow Interface

**Files to Create/Modify**:
- `accounts/views.py` - Add follow/unfollow views with HTMX support
- `accounts/urls.py` - Add follow management URL patterns
- `accounts/forms.py` - Create FollowForm with tag input and validation
- `accounts/templates/accounts/components/follow_button.html` - Reusable follow button component
- `accounts/templates/accounts/components/follow_modal.html` - Tag specification modal
- `democracy/templates/democracy/community_detail.html` - Add follow buttons to member lists
- `accounts/templates/accounts/member_profile.html` - Add follow button to profiles

**Key Features**:
1. **Follow Button Component**: Appears on member profiles and community member lists
2. **Tag Specification Modal**: HTMX-powered modal for specifying tags when following someone
3. **Smart Tag Suggestions**: Shows tags the followee has actually used in past votes
4. **Click-to-Add Tags**: Users can click suggested tags to automatically add them
5. **Manual Tag Entry**: Users can type any custom tags they want
6. **Follow Status Display**: Shows current following status (Following on: budget, environment)
7. **Unfollow Functionality**: One-click unfollow with confirmation
8. **HTMX Integration**: Real-time updates without page refreshes

**Follow Button States**:
- **Not Following**: "Follow [Name]" button (blue)
- **Following All Topics**: "Following [Name]" button with dropdown (green)  
- **Following Specific Tags**: "Following on: budget, environment" with dropdown (green)
- **Dropdown Options**: "Edit Tags", "Unfollow", "View Profile"

### Phase 2: Personal Delegation Dashboard

**Files to Create/Modify**:
- `accounts/views.py` - Add delegation_dashboard view
- `accounts/urls.py` - Add dashboard URL pattern
- `accounts/templates/accounts/delegation_dashboard.html` - Complete delegation management interface
- `accounts/templates/accounts/components/following_card.html` - Individual following relationship card
- `accounts/templates/accounts/components/followers_card.html` - Followers display card

**Dashboard Sections**:
1. **Following Management**: 
   - List of people you follow with tags and priority order
   - Edit tags, change priority, unfollow actions
   - Search and filter following relationships
2. **Followers Overview**:
   - People who follow you with their tag preferences  
   - Your influence metrics and tag expertise areas
3. **Delegation Analytics**:
   - How often your votes are inherited vs. manual
   - Tag usage frequency and expertise building
   - Delegation chain visualization for your relationships

### Phase 3: Bulk Delegation Management

**Files to Create/Modify**:
- `accounts/forms.py` - Add BulkFollowForm and DelegationImportForm
- `accounts/views.py` - Add bulk management views
- `accounts/templates/accounts/components/bulk_follow_modal.html` - Multi-user follow interface
- `accounts/management/commands/import_delegation_csv.py` - CSV import for large communities

**Bulk Features**:
1. **Multi-Select Follow**: Follow multiple people on same tags simultaneously
2. **Tag Management**: Bulk edit tags across multiple following relationships
3. **Priority Reordering**: Drag-and-drop priority management for tie-breaking
4. **CSV Import/Export**: For large communities migrating from other systems
5. **Following Templates**: Save common tag combinations for quick application

## Implementation Details

### Tag Suggestion Algorithm

**Data Source**: Uses existing `CustomUser.get_tag_usage_frequency()` method to get tags the followee has used in past votes.

**Algorithm Steps**:
1. **Query Past Ballots**: Get all ballots where `voter=followee` and `tags` is not empty
2. **Parse Tags**: Split comma-separated tag strings and normalize (strip whitespace, lowercase)
3. **Count Frequency**: Count how many times each tag has been used
4. **Sort by Usage**: Order tags by frequency (most used first)
5. **Limit Results**: Return top 10 most frequently used tags
6. **Display Format**: Show as clickable buttons with usage count: "budget (5)"

**User Interaction Flow**:
1. **Modal Opens**: User clicks "Follow [Name]" button
2. **Load Suggestions**: Modal displays followee's most-used tags as clickable buttons
3. **Manual Entry**: User can type custom tags in text input field
4. **Click to Add**: User clicks suggested tag buttons to automatically add to input
5. **Duplicate Prevention**: JavaScript prevents adding same tag twice
6. **Visual Feedback**: Clicked tags briefly turn green to show they were added
7. **Submit**: Final tag list (manual + clicked) submitted with follow request

**Example User Experience**:
- User A has voted with tags: "budget" (5 times), "environment" (3 times), "safety" (2 times)
- User B wants to follow User A
- Modal shows: [budget (5)] [environment (3)] [safety (2)] as clickable buttons
- User B types "infrastructure" and clicks [budget (5)] and [environment (3)]
- Final tags: "infrastructure, budget, environment"

### Follow Form Design

```python
class FollowForm(forms.Form):
    """Form for creating/editing following relationships with tag specification."""
    
    followee = forms.ModelChoiceField(
        queryset=CustomUser.objects.all(),
        widget=forms.HiddenInput()
    )
    
    tags = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Type tags like "budget, environment" or click suggestions below',
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'id': 'follow-tags-input'
        }),
        help_text="Specify topics to follow this person on, or leave empty to follow on all topics"
    )
    
    order = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'w-20 px-3 py-2 border border-gray-300 rounded-md'
        }),
        help_text="Priority for tie-breaking (lower numbers = higher priority)"
    )
    
    def __init__(self, *args, **kwargs):
        self.followee = kwargs.pop('followee', None)
        super().__init__(*args, **kwargs)
        
    def get_suggested_tags(self):
        """Get tags this followee has used in past votes for suggestions."""
        if not self.followee:
            return []
        
        # Get tags from user's past ballots, ordered by frequency
        return self.followee.get_tag_usage_frequency()[:10]  # Top 10 most used tags
```

### Tag Suggestion Modal Component

```html
<!-- accounts/templates/accounts/components/follow_modal.html -->
<div id="follow-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full mx-4">
        <div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-lg font-medium text-gray-900 dark:text-white">
                Follow {{ followee.get_display_name }}
            </h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Choose topics to follow them on, or leave empty for all topics
            </p>
        </div>
        
        <form hx-post="{% url 'accounts:follow' followee.id %}" 
              hx-target="#follow-button-{{ followee.id }}"
              hx-swap="outerHTML">
            {% csrf_token %}
            <div class="px-6 py-4">
                <!-- Manual Tag Input -->
                <div class="mb-4">
                    <label for="follow-tags-input" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Topics to follow on:
                    </label>
                    {{ form.tags }}
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {{ form.tags.help_text }}
                    </p>
                </div>
                
                <!-- Suggested Tags Section -->
                {% with suggested_tags=form.get_suggested_tags %}
                {% if suggested_tags %}
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        {{ followee.get_display_name }} has voted on these topics:
                    </label>
                    <div class="flex flex-wrap gap-2">
                        {% for tag, count in suggested_tags %}
                        <button type="button" 
                                onclick="addTagToInput('{{ tag }}')"
                                class="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors cursor-pointer">
                            {{ tag }}
                            <span class="ml-1 text-xs text-blue-600">({{ count }})</span>
                        </button>
                        {% endfor %}
                    </div>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
                        Click tags to add them, or type your own in the box above
                    </p>
                </div>
                {% endif %}
                {% endwith %}
                
                <!-- Priority Order -->
                <div class="mb-4">
                    <label for="{{ form.order.id_for_label }}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Priority Order:
                    </label>
                    {{ form.order }}
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {{ form.order.help_text }}
                    </p>
                </div>
            </div>
            
            <div class="px-6 py-4 bg-gray-50 dark:bg-gray-700 flex justify-end space-x-3">
                <button type="button" 
                        onclick="document.getElementById('follow-modal').remove()"
                        class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-600 border border-gray-300 dark:border-gray-500 rounded-md hover:bg-gray-50 dark:hover:bg-gray-500">
                    Cancel
                </button>
                <button type="submit"
                        class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700">
                    Follow
                </button>
            </div>
        </form>
    </div>
</div>

<script>
function addTagToInput(tag) {
    const input = document.getElementById('follow-tags-input');
    const currentTags = input.value.trim();
    
    // Check if tag already exists
    const tagList = currentTags ? currentTags.split(',').map(t => t.trim()) : [];
    if (tagList.includes(tag)) {
        return; // Tag already added
    }
    
    // Add new tag
    const newValue = currentTags ? `${currentTags}, ${tag}` : tag;
    input.value = newValue;
    
    // Visual feedback - briefly highlight the added tag button
    event.target.classList.add('bg-green-200', 'text-green-800');
    setTimeout(() => {
        event.target.classList.remove('bg-green-200', 'text-green-800');
        event.target.classList.add('bg-blue-100', 'text-blue-800');
    }, 500);
}
</script>
```

### HTMX Follow Button Component

```html
<!-- accounts/templates/accounts/components/follow_button.html -->
<div id="follow-button-{{ user.id }}" class="inline-block">
    {% if is_following %}
        <div class="relative" x-data="{ open: false }">
            <button @click="open = !open" 
                    class="inline-flex items-center px-3 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors">
                <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/>
                </svg>
                {% if following.tags %}
                    Following on: {{ following.tags }}
                {% else %}
                    Following {{ user.get_display_name }}
                {% endif %}
                <svg class="w-4 h-4 ml-2" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/>
                </svg>
            </button>
            
            <!-- Dropdown Menu -->
            <div x-show="open" @click.away="open = false" 
                 class="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg ring-1 ring-gray-200 z-50">
                <div class="py-1">
                    <button hx-get="{% url 'accounts:edit_follow' user.id %}" 
                            hx-target="#follow-modal" 
                            hx-trigger="click"
                            class="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                        Edit Tags
                    </button>
                    <button hx-post="{% url 'accounts:unfollow' user.id %}" 
                            hx-target="#follow-button-{{ user.id }}" 
                            hx-confirm="Stop following {{ user.get_display_name }}?"
                            class="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50">
                        Unfollow
                    </button>
                </div>
            </div>
        </div>
    {% else %}
        <button hx-get="{% url 'accounts:follow' user.id %}" 
                hx-target="#follow-modal" 
                hx-trigger="click"
                class="inline-flex items-center px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">
            <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
            </svg>
            Follow {{ user.get_display_name }}
        </button>
    {% endif %}
</div>
```

### URL Patterns

```python
# accounts/urls.py additions
urlpatterns = [
    # ... existing patterns ...
    
    # Follow/Unfollow Management
    path('follow/<int:user_id>/', views.follow_user, name='follow'),
    path('unfollow/<int:user_id>/', views.unfollow_user, name='unfollow'),
    path('edit-follow/<int:user_id>/', views.edit_follow, name='edit_follow'),
    
    # Delegation Dashboard
    path('delegation/', views.delegation_dashboard, name='delegation_dashboard'),
    path('delegation/bulk-follow/', views.bulk_follow, name='bulk_follow'),
    path('delegation/reorder/', views.reorder_following, name='reorder_following'),
    
    # HTMX Partials
    path('htmx/follow-status/<int:user_id>/', views.follow_status_partial, name='follow_status_partial'),
]
```

### View Functions

```python
# accounts/views.py additions

@login_required
@require_http_methods(["GET", "POST"])
def follow_user(request, user_id):
    """Handle following a user with tag specification."""
    followee = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == "GET":
        # Return follow modal for tag specification
        form = FollowForm(initial={'followee': followee}, followee=followee)
        return render(request, 'accounts/components/follow_modal.html', {
            'form': form,
            'followee': followee
        })
    
    if request.method == "POST":
        form = FollowForm(request.POST)
        if form.is_valid():
            # Create or update following relationship
            following, created = Following.objects.update_or_create(
                follower=request.user,
                followee=followee,
                defaults={
                    'tags': form.cleaned_data['tags'],
                    'order': form.cleaned_data['order']
                }
            )
            
            if request.htmx:
                # Return updated follow button
                return render(request, 'accounts/components/follow_button.html', {
                    'user': followee,
                    'is_following': True,
                    'following': following
                })
            
            messages.success(request, f"Now following {followee.get_display_name()}")
            return redirect('accounts:member_profile', username=followee.username)

@login_required
@require_POST
def unfollow_user(request, user_id):
    """Handle unfollowing a user."""
    followee = get_object_or_404(CustomUser, id=user_id)
    
    try:
        following = Following.objects.get(
            follower=request.user,
            followee=followee
        )
        following.delete()
        
        if request.htmx:
            # Return updated follow button
            return render(request, 'accounts/components/follow_button.html', {
                'user': followee,
                'is_following': False,
                'following': None
            })
        
        messages.success(request, f"Stopped following {followee.get_display_name()}")
        
    except Following.DoesNotExist:
        messages.error(request, "You are not following this user")
    
    return redirect('accounts:member_profile', username=followee.username)

@login_required
def delegation_dashboard(request):
    """Personal delegation management dashboard."""
    # Get user's following relationships with related data
    following = request.user.followings.select_related('followee').order_by('order', 'followee__username')
    
    # Get user's followers
    followers = request.user.followers.select_related('follower').order_by('follower__username')
    
    # Get delegation analytics
    delegation_stats = {
        'total_following': following.count(),
        'total_followers': followers.count(),
        'tag_usage': request.user.get_tag_usage_frequency(),
        'recent_inherited_votes': request.user.ballots.filter(is_calculated=True).count()
    }
    
    return render(request, 'accounts/delegation_dashboard.html', {
        'following': following,
        'followers': followers,
        'delegation_stats': delegation_stats
    })
```

## User Experience Flow

### Following Someone New
1. **Discover Member**: Browse community members or view member profile
2. **Click Follow**: Blue "Follow [Name]" button opens tag specification modal
3. **Specify Tags**: Enter tags like "budget, environment" or leave empty for all topics
4. **Set Priority**: Choose priority number for tie-breaking (default: 1)
5. **Confirm**: Click "Follow" to create relationship
6. **Visual Feedback**: Button changes to green "Following on: budget, environment"

### Managing Existing Relationships
1. **View Dashboard**: Visit personal delegation dashboard
2. **See Following List**: All people you follow with tags and priority
3. **Edit Relationship**: Click "Edit" to modify tags or priority
4. **Reorder Priority**: Drag and drop to change tie-breaking order
5. **Bulk Actions**: Select multiple relationships for bulk tag editing

### Understanding Your Influence
1. **Followers Section**: See who follows you and on which tags
2. **Tag Expertise**: View your most-used tags and expertise areas
3. **Delegation Analytics**: See how often your votes are inherited
4. **Influence Growth**: Track follower growth over time

## Security & Validation

### Following Constraints
- Users cannot follow themselves (model validation)
- Duplicate following relationships prevented (unique constraint)
- Tag validation and cleaning (remove duplicates, normalize case)
- Priority validation (positive integers only)

### Permission Checks
- Only community members can follow other community members
- Following relationships respect community boundaries
- CSRF protection on all follow/unfollow actions
- Rate limiting on follow actions to prevent spam

### Privacy Controls
- Users can make their following/follower lists private
- Anonymous following option for sensitive topics
- Delegation dashboard respects privacy settings
- Following notifications can be disabled

## Testing Requirements

### New Test Files to Create

**Unit Tests**:
- `tests/test_views/test_follow_views.py` - Follow/unfollow view logic and permissions
- `tests/test_forms/test_follow_forms.py` - FollowForm validation, tag suggestions, and cleaning
- `tests/test_models/test_following_model.py` - Following model constraints and validation
- `tests/test_services/test_tag_suggestions.py` - Tag suggestion algorithm testing

**Integration Tests**:
- `tests/test_integration/test_follow_workflow.py` - Complete follow/unfollow user journey
- `tests/test_htmx/test_follow_interactions.py` - HTMX partial responses and modal behavior
- `tests/test_delegation/test_dashboard_functionality.py` - Delegation dashboard features

**Frontend Tests**:
- `tests/test_templates/test_follow_components.py` - Template rendering and context
- `tests/test_javascript/test_tag_input.py` - JavaScript tag addition functionality

### Existing Tests to Update

**Model Tests**:
- `tests/test_models/test_accounts.py` - Update Following model tests for new tag suggestion methods
- `tests/test_models/test_democracy.py` - Ensure delegation still works with new follow UI

**View Tests**:
- `tests/test_views/test_accounts_views.py` - Update member profile tests to include follow buttons
- `tests/test_views/test_democracy_views.py` - Update community detail tests for follow functionality

**Service Tests**:
- `tests/test_services/test_delegation.py` - Ensure delegation algorithms work with UI-created relationships
- `tests/test_services/test_star_voting.py` - Verify voting inheritance with new follow relationships

### Test Coverage Requirements

**Follow/Unfollow Views (`tests/test_views/test_follow_views.py`)**:
```python
class FollowViewsTest(TestCase):
    def test_follow_user_get_returns_modal()
    def test_follow_user_post_creates_relationship()
    def test_follow_user_post_with_tags()
    def test_follow_user_post_without_tags_follows_all()
    def test_follow_user_prevents_self_following()
    def test_follow_user_requires_authentication()
    def test_follow_user_requires_community_membership()
    def test_unfollow_user_removes_relationship()
    def test_unfollow_user_htmx_response()
    def test_edit_follow_updates_tags()
    def test_follow_user_duplicate_prevention()
```

**Follow Form Tests (`tests/test_forms/test_follow_forms.py`)**:
```python
class FollowFormTest(TestCase):
    def test_form_initialization_with_followee()
    def test_get_suggested_tags_returns_user_tags()
    def test_get_suggested_tags_limits_to_ten()
    def test_get_suggested_tags_orders_by_frequency()
    def test_get_suggested_tags_handles_no_ballots()
    def test_tags_field_validation()
    def test_tags_field_cleaning_and_normalization()
    def test_order_field_validation()
    def test_form_without_followee_parameter()
```

**Tag Suggestion Algorithm Tests (`tests/test_services/test_tag_suggestions.py`)**:
```python
class TagSuggestionTest(TestCase):
    def test_tag_frequency_calculation()
    def test_tag_normalization_and_deduplication()
    def test_tag_sorting_by_usage_count()
    def test_tag_limit_enforcement()
    def test_empty_tags_handling()
    def test_case_insensitive_tag_counting()
    def test_comma_separated_tag_parsing()
```

**Following Model Tests (`tests/test_models/test_following_model.py`)**:
```python
class FollowingModelTest(TestCase):
    def test_following_creation_with_tags()
    def test_following_creation_without_tags()
    def test_self_following_prevention()
    def test_duplicate_following_prevention()
    def test_tag_cleaning_on_save()
    def test_order_validation()
    def test_string_representation()
    def test_following_relationship_cascade()
```

**HTMX Integration Tests (`tests/test_htmx/test_follow_interactions.py`)**:
```python
class FollowHTMXTest(TestCase):
    def test_follow_button_htmx_response()
    def test_follow_modal_htmx_loading()
    def test_unfollow_htmx_confirmation()
    def test_follow_status_partial_rendering()
    def test_htmx_headers_and_csrf()
    def test_htmx_error_handling()
```

**Delegation Dashboard Tests (`tests/test_delegation/test_dashboard_functionality.py`)**:
```python
class DelegationDashboardTest(TestCase):
    def test_dashboard_displays_following_list()
    def test_dashboard_displays_followers_list()
    def test_dashboard_delegation_analytics()
    def test_dashboard_requires_authentication()
    def test_dashboard_following_edit_functionality()
    def test_dashboard_bulk_operations()
    def test_dashboard_responsive_design()
```

**Integration Workflow Tests (`tests/test_integration/test_follow_workflow.py`)**:
```python
class FollowWorkflowTest(TestCase):
    def test_complete_follow_workflow()
    def test_follow_with_tag_suggestions()
    def test_follow_edit_and_unfollow()
    def test_follow_delegation_inheritance()
    def test_bulk_follow_operations()
    def test_cross_community_following()
```

### Security and Edge Case Tests

**Security Tests**:
- CSRF protection on all follow/unfollow actions
- Permission checks for community membership requirements
- Rate limiting prevention of follow spam
- XSS prevention in tag input fields
- SQL injection prevention in tag queries

**Edge Case Tests**:
- Following users with no voting history (empty tag suggestions)
- Following users with very long tag lists
- Following users across multiple communities
- Following relationships with special characters in tags
- Following priority conflicts and tie-breaking
- Following circular relationship prevention

**Performance Tests**:
- Tag suggestion query performance with large ballot datasets
- Dashboard loading performance with many following relationships
- HTMX response times for follow operations
- Bulk follow operation performance

### Test Data Requirements

**Factory Updates**:
- Update `UserFactory` to create users with voting history for tag suggestions
- Update `BallotFactory` to create ballots with realistic tag patterns
- Create `FollowingFactory` for generating test following relationships

**Test Fixtures**:
- Users with various tag usage patterns (frequent, infrequent, diverse, specialized)
- Communities with different following relationship densities
- Ballots with realistic tag distributions for suggestion testing

### Regression Testing

**Existing Functionality**:
- Ensure existing delegation algorithms still work with UI-created relationships
- Verify STAR voting calculations remain accurate with new following data
- Confirm delegation tree visualization includes UI-created relationships
- Test that existing member profiles and community pages still render correctly

**Database Integrity**:
- Verify Following model constraints prevent invalid relationships
- Test cascade behavior when users or communities are deleted
- Ensure tag data integrity with new cleaning and validation rules

## Success Metrics

### Functionality
- ✅ Users can follow/unfollow other members through UI
- ✅ Tag specification works correctly with validation
- ✅ Following relationships integrate with existing delegation system
- ✅ Dashboard provides comprehensive delegation management
- ✅ HTMX interactions work smoothly without page refreshes

### User Experience
- ✅ Intuitive follow button states and visual feedback
- ✅ Clear tag specification with helpful examples
- ✅ Easy bulk management for power users
- ✅ Mobile-responsive design on all devices
- ✅ Accessible interface with proper ARIA labels

### Technical Quality
- ✅ All new code has comprehensive test coverage
- ✅ HTMX integration follows established patterns
- ✅ Database queries optimized with select_related/prefetch_related
- ✅ Proper error handling and user feedback
- ✅ Security measures prevent abuse and spam

## Implementation Timeline

**Phase 1 (Week 1)**: Follow/Unfollow Interface
- Follow button component with HTMX integration
- Tag specification modal and form validation
- Basic follow/unfollow functionality working

**Phase 2 (Week 2)**: Delegation Dashboard  
- Personal delegation management interface
- Following/followers display with analytics
- Edit and reorder functionality

**Phase 3 (Week 3)**: Bulk Management & Polish
- Bulk follow operations and CSV import/export
- Advanced dashboard features and analytics
- Comprehensive testing and bug fixes

**Total Effort**: 3 weeks
**Risk Level**: Medium (HTMX integration complexity, UX design challenges)

---

This plan transforms CrowdVote from a backend delegation system into a complete user-facing democratic platform where members can easily build trust networks and participate in delegative democracy through an intuitive web interface.
