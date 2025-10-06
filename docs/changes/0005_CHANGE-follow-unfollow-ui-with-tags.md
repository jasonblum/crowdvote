# Change 0005: Add Follow/Unfollow UI with Tag Selection

## Description

Implement community-specific follow/unfollow functionality with tag selection. Users can follow other members within a community context and specify which tags they want to follow them on. Following relationships are Membership→Membership (community-specific), not User→User (global).

## Context

Following was broken during the accounts→security refactoring when Following model was moved to democracy app and changed from User→User to Membership→Membership architecture. This change restores and enhances the follow/unfollow UI in the appropriate community context.

## Files to Modify

### 1. **democracy/templates/democracy/community_detail.html**

**Members Table Structure Changes:**
- Remove "Member" column (full name column)
- Rename "Username" column header to "Member"
- Add "Following" column (shows current following status with tag pills)
- Add "Actions" column as the last column
- Actions column contains Follow button/link for each member

**Table Structure:**
```
| Member (avatar + @username) | Roles | Following | Joined | Actions |
```

**Following Column Display:**
- **Not following**: Show "—" (em dash)
- **Following on specific tags**: Show small tag pills (e.g., `budget` `finance` `environment`)
- **Following on ALL tags**: Show badge "All Tags"
- **Cell ID**: Each cell has unique ID `following-{{ membership.id }}` for HTMX targeting

**Actions Column Content:**
- If not following: Show "Follow" button
- If already following: Show "Following ✓" button (with checkmark)
- Clicking opens follow modal

### 2. **democracy/templates/democracy/components/follow_modal.html** (Create New)

**Modal Structure:**
- Modal backdrop overlay (semi-transparent dark background)
- Clicking backdrop closes modal
- Modal dialog centered on screen
- Modal contains:
  - Header: "Follow @{username} in {community_name}"
  - Tag selection section
  - Action buttons (Save/Cancel or Update/Unfollow/Cancel)

**Tag Input Section:**
- **Tag pills display area**: Shows selected tags as visual "pills/chips"
  - Each pill has tag name + × remove button
  - Pills use Tailwind badge styling with dark mode support
- **Text input box**: Type tag name, blur/enter converts to pill
- **Suggested tags section below input**:
  - Header: "Tags this member has used in this community:"
  - Display tags as clickable pills
  - Clicking adds tag to selected list (if not already selected)
  - If member hasn't used any tags yet, show message: "No tags yet"
- **"All Tags" checkbox option**: Follow on all tags (replaces specific tag selection)

**Modal States:**

**State 1: Not Currently Following**
- Modal title: "Follow @username"
- Empty tag pills area
- Show all their used tags as suggestions
- Primary button: "Follow" (green)
- Secondary button: "Cancel" (gray)

**State 2: Already Following**
- Modal title: "Update Following: @username"
- Pre-populate tag pills area with currently followed tags
- Show all their used tags as suggestions (with already-selected tags indicated)
- Primary button: "Update" (blue)
- Destructive button: "Unfollow" (red)
- Secondary button: "Cancel" (gray)

### 3. **democracy/views.py**

**New View: `follow_modal`**
```python
@login_required
def follow_modal(request, community_id, member_id):
    """
    Return HTMX modal for follow/unfollow with tag selection.
    
    Args:
        community_id: UUID of the community
        member_id: UUID of the membership to follow
    
    Context:
        - member_membership: The Membership being followed
        - user_membership: Current user's Membership in this community
        - existing_following: Following object if exists, else None
        - member_tags: List of tags the member has used in this community
        - current_tags: List of tags user is currently following them on (if following)
    """
```

**New View: `follow_member`**
```python
@login_required
@require_POST
def follow_member(request, community_id, member_id):
    """
    Create or update Following relationship with tag selection.
    
    POST data:
        - tags: JSON array of tag names, or ["ALL"] for all tags
    
    Returns:
        - On success: Renders partial template with:
          1. Updated Following column HTML (tag pills)
          2. Updated Actions column HTML (button state)
          Uses HTMX out-of-band swaps to update both
        - On error: Error message
    """
```

**Return Template Structure:**
```html
<!-- following_update.html -->
<div id="following-{{ membership.id }}" hx-swap-oob="true">
    {% if following.tags %}
        {% for tag in following.tags_list %}
            <span class="tag-pill-small">{{ tag }}</span>
        {% endfor %}
    {% elif following %}
        <span class="following-all-tags">All Tags</span>
    {% else %}
        —
    {% endif %}
</div>

<div id="actions-{{ membership.id }}" hx-swap-oob="true">
    <button hx-get="{% url 'democracy:follow_modal' community.id membership.id %}"
            hx-target="#follow-modal-container"
            class="text-blue-600 hover:text-blue-800 text-sm font-medium">
        Following ✓
    </button>
</div>
```

**New View: `unfollow_member`**
```python
@login_required
@require_POST
def unfollow_member(request, community_id, member_id):
    """
    Delete Following relationship.
    
    Returns:
        - On success: Updated Actions column HTML (HTMX swap)
    """
```

**Helper Function: `get_member_tags_in_community`**
```python
def get_member_tags_in_community(membership):
    """
    Get all unique tags a member has used in their community.
    
    Queries Decision tags where this membership has voted.
    Returns list of unique tag names.
    """
```

### 4. **democracy/urls.py**

Add new URL patterns:
```python
path('communities/<uuid:community_id>/follow/<uuid:member_id>/', 
     views.follow_modal, name='follow_modal'),
path('communities/<uuid:community_id>/follow/<uuid:member_id>/save/', 
     views.follow_member, name='follow_member'),
path('communities/<uuid:community_id>/unfollow/<uuid:member_id>/', 
     views.unfollow_member, name='unfollow_member'),
```

### 5. **static/css/crowdvote.css**

Add modal and tag pill styles:

**Modal Backdrop:**
```css
.modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
}

.dark .modal-backdrop {
    background: rgba(0, 0, 0, 0.7);
}
```

**Tag Pills (in modal):**
```css
.tag-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.75rem;
    background: #3b82f6;
    color: white;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 500;
}

.tag-pill-remove {
    cursor: pointer;
    font-weight: bold;
    opacity: 0.7;
}

.tag-pill-remove:hover {
    opacity: 1;
}

.dark .tag-pill {
    background: #2563eb;
}

.tag-suggestion {
    cursor: pointer;
    opacity: 0.7;
}

.tag-suggestion:hover {
    opacity: 1;
    background: #2563eb;
}
```

**Tag Pills (small, in table):**
```css
.tag-pill-small {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    margin-right: 0.25rem;
    background: #3b82f6;
    color: white;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
}

.dark .tag-pill-small {
    background: #2563eb;
}

.following-all-tags {
    display: inline-flex;
    padding: 0.125rem 0.5rem;
    background: #10b981;
    color: white;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 600;
}

.dark .following-all-tags {
    background: #059669;
}
```

## Algorithm: Tag Selection Flow

### Step 1: User Clicks Follow Button
1. HTMX GET request to `/communities/{uuid}/follow/{member_uuid}/`
2. View retrieves:
   - User's membership in this community
   - Target member's membership
   - Existing Following relationship (if any)
   - List of tags target member has used in this community
3. Render modal with appropriate state (new follow vs. edit existing)
4. HTMX swaps modal into `#follow-modal-container`

### Step 2: User Interacts with Tag Input
1. **Typing a tag**: Input field accepts text
2. **Blur/Enter**: Convert typed text to tag pill
3. **Click suggested tag**: Add tag to pills area (if not duplicate)
4. **Click × on pill**: Remove pill from selection
5. **Check "All Tags"**: Clear all specific tags, set to "follow all"

### Step 3: User Saves
1. Form submits via HTMX POST to `/communities/{uuid}/follow/{member_uuid}/save/`
2. POST data includes: `{"tags": ["apple", "banana"]}` or `{"tags": ["ALL"]}`
3. View logic:
   - Get or create Following object
   - Update `tags` field (comma-separated string: "apple,banana" or empty for ALL)
   - Save Following relationship
4. Return updated Actions column HTML
5. HTMX swaps "Follow" button → "Following ✓" button

### Step 4: User Unfollows
1. User clicks "Unfollow" in modal
2. HTMX POST to `/communities/{uuid}/unfollow/{member_uuid}/`
3. View deletes Following object
4. Return updated Actions column HTML
5. HTMX swaps "Following ✓" button → "Follow" button

## Data Structure

### Following Model (existing)
```python
class Following(BaseModel):
    follower = ForeignKey(Membership)  # Who is following
    followee = ForeignKey(Membership)  # Who is being followed
    tags = CharField(blank=True)  # Comma-separated: "apple,banana" or "" for ALL
    order = PositiveIntegerField(default=0)
```

### Tags Storage
- Stored as comma-separated string in `Following.tags` field
- Empty string (`""`) means "ALL tags"
- Example: `"budget,finance,environment"`

### POST Data Format
```json
{
  "tags": ["budget", "finance", "environment"]
}
```
Or for "all tags":
```json
{
  "tags": ["ALL"]
}
```

## UI/UX Details

### Modal Behavior
- **Open**: Fade in backdrop, slide in modal
- **Close**: Click backdrop, click Cancel, press Escape key
- **Backdrop**: Semi-transparent dark overlay, prevents interaction with background
- **Scroll**: If modal content is tall, modal body should scroll (not page behind it)

### Tag Pills Visual Design
- **Color**: Blue pills (`bg-blue-600` / `dark:bg-blue-700`)
- **Shape**: Fully rounded (`rounded-full`)
- **Size**: Small padding, 14px font
- **Remove button**: × symbol, hover to darken
- **Spacing**: Gap between pills

### Suggested Tags
- Display below input in a flex-wrapped container
- Use same pill styling but lighter/grayed out
- Hover effect to indicate clickable
- If tag already selected, show as disabled/checked

### Responsive Design
- Modal width: `max-w-md` (28rem) on mobile, `max-w-lg` (32rem) on desktop
- Tag pills wrap to multiple lines if needed
- Modal is vertically scrollable on small screens

## HTMX Integration

### Follow Button (in Members table)
```html
<button hx-get="{% url 'democracy:follow_modal' community.id membership.id %}"
        hx-target="#follow-modal-container"
        hx-swap="innerHTML"
        class="text-blue-600 hover:text-blue-800 text-sm font-medium">
    Follow
</button>
```

### Modal Form (in follow_modal.html)
```html
<form hx-post="{% url 'democracy:follow_member' community.id member_membership.id %}"
      hx-target="#following-{{ member_membership.id }}, #actions-{{ member_membership.id }}"
      hx-swap="innerHTML"
      @submit.prevent>
    <!-- Tag input UI -->
    <input type="hidden" name="tags" id="tags-input" value="">
    <button type="submit">Follow</button>
</form>
```

**Note**: The `hx-target` includes both the Following column cell AND the Actions cell, separated by comma. This allows updating both cells in one response using HTMX out-of-band swaps.

### Unfollow Button (in modal)
```html
<button hx-post="{% url 'democracy:unfollow_member' community.id member_membership.id %}"
        hx-target="#member-{{ member_membership.id }}-actions"
        hx-swap="innerHTML"
        hx-confirm="Stop following this member?"
        class="btn-danger">
    Unfollow
</button>
```

## JavaScript Requirements

**Tag Input Handler** (in follow_modal.html):
```javascript
// Convert text input to tag pill on blur/enter
// Handle pill removal clicks
// Update hidden input with JSON array of tags
// Handle "All Tags" checkbox toggle
// Handle suggested tag clicks
```

## Testing Requirements

### Manual Testing
1. **Not Following → Follow**:
   - Click "Follow" button for a member
   - Modal opens with empty tag selection
   - Type a tag, verify it becomes a pill
   - Click suggested tag, verify it's added
   - Click × on pill, verify it's removed
   - Click "Follow", modal closes, button changes to "Following ✓"

2. **Already Following → Update**:
   - Click "Following ✓" button
   - Modal opens with current tags pre-populated
   - Add/remove tags
   - Click "Update", modal closes, tags updated in database

3. **Unfollow**:
   - Open modal for someone you're following
   - Click "Unfollow"
   - Confirm dialog appears
   - Confirm, modal closes, button changes to "Follow"

4. **All Tags Option**:
   - Check "All Tags" checkbox
   - Verify specific tags are cleared
   - Save, verify `Following.tags` is empty string

5. **Backdrop Click**:
   - Open modal
   - Click backdrop (outside modal)
   - Modal closes without saving

6. **Tag Suggestions**:
   - Verify suggestions show member's actual used tags
   - Verify clicking suggestion adds it to selection
   - Verify already-selected tags are indicated

### Edge Cases
- Member with no tags yet (show appropriate message)
- Following self (should not show Follow button)
- Non-member viewing page (should not show Follow buttons)
- Very long tag names (should wrap or truncate)
- Many tags (modal scrolls)

### Database Testing
- Verify Following created with correct follower/followee Memberships
- Verify tags stored correctly (comma-separated or empty)
- Verify Following updated (not duplicated) when editing
- Verify Following deleted when unfollowing

## Notes

- Following is **Membership→Membership**, not User→User
- Tags are **community-specific** (same user may use different tags in different communities)
- Empty `tags` field means "follow on ALL tags"
- User cannot follow themselves
- User can only follow members of communities they're both in
- Modal should be keyboard accessible (Tab navigation, Escape to close)

## Future Enhancements (Not in This Change)

- Show following status on profile page (read-only view across all shared communities)
- Bulk follow/unfollow actions
- Tag autocomplete from Decision tags
- Following suggestions ("Members you might want to follow")
- Notification when someone follows you
