# Plan #15: Standardize All Templates for Layout Consistency

## Objective

Ensure all templates in the CrowdVote application follow the same layout pattern as the dashboard, extending `base.html` properly to provide consistent navigation, logo placement, and theme controls across the entire application.

## Current State Analysis

**✅ PERFECT TEMPLATES (Reference Standards)**:
- `accounts/templates/accounts/dashboard.html` - Perfect layout extending base.html with `{% block sidebar_content %}` and `{% block header_left %}`
- `crowdvote/templates/base.html` - Perfect base template with logo, navigation, and theme controls
- `crowdvote/templates/home.html` - Landing page (intentionally different, no changes needed)

**🔄 TEMPLATES TO STANDARDIZE**:

### Accounts App Templates
1. **`accounts/templates/accounts/profile_setup.html`**
   - Current: Custom layout with own sidebar and theme toggle
   - Target: Extend base.html, keep existing setup steps in sidebar, remove duplicate theme controls

2. **`accounts/templates/accounts/edit_profile.html`**
   - Current: Likely has old layout patterns
   - Target: Extend base.html, keep profile editing content, add consistent header

3. **`accounts/templates/accounts/community_discovery.html`**
   - Current: Likely has old layout patterns
   - Target: Extend base.html, keep community browsing content, add consistent header

4. **`accounts/templates/accounts/member_profile.html`**
   - Current: May have inconsistent layout
   - Target: Extend base.html, keep member profile content, add consistent header

5. **`accounts/templates/accounts/member_profile_community.html`**
   - Current: May have inconsistent layout
   - Target: Extend base.html, keep community-specific profile content, add consistent header

### Democracy App Templates
6. **`democracy/templates/democracy/community_detail.html`**
   - Current: May have old logo/navigation
   - Target: Extend base.html, keep community information in sidebar, add consistent header

7. **`democracy/templates/democracy/community_manage.html`**
   - Current: May have inconsistent layout
   - Target: Extend base.html, keep management tools in sidebar, add consistent header

8. **`democracy/templates/democracy/decision_create.html`**
   - Current: May have old layout patterns
   - Target: Extend base.html, keep decision creation form, add consistent header

9. **`democracy/templates/democracy/decision_detail.html`**
   - Current: May have old layout patterns
   - Target: Extend base.html, keep decision details and voting interface, add consistent header

10. **`democracy/templates/democracy/decision_list.html`**
    - Current: May have old layout patterns
    - Target: Extend base.html, keep decision listing, add consistent header

11. **`democracy/templates/democracy/decision_results.html`**
    - Current: May have old layout patterns
    - Target: Extend base.html, keep results display, add consistent header

### Main App Templates
12. **`crowdvote/templates/docs.html`**
    - Current: May have old logo/navigation
    - Target: Extend base.html, keep documentation content, add consistent header

## Target Layout Pattern

All templates should follow this structure (like dashboard.html):

```html
{% extends "base.html" %}

{% block title %}Page Title - CrowdVote{% endblock %}

{% block sidebar_content %}
    <!-- Inherit logo from base.html -->
    {{ block.super }}
    
    <!-- Page-specific sidebar content (keep existing content) -->
    <div class="px-6 py-4">
        <!-- Existing sidebar content goes here -->
    </div>
{% endblock sidebar_content %}

{% block header_left %}
    <div class="flex items-center">
        <h1 class="text-xl font-bold text-gray-900 dark:text-white">Page Title</h1>
    </div>
{% endblock header_left %}

{% block content %}
    <!-- Existing page content goes here -->
{% endblock %}
```

## Key Requirements

### What Every Template MUST Have After Standardization:
1. **Logo**: CrowdVote logo image in upper left (inherited from base.html)
2. **Navigation**: Username dropdown with Dashboard/Profile/Docs/Logout links (inherited from base.html)
3. **Theme Toggle**: Light/Dark/Auto theme switcher in upper right (inherited from base.html)
4. **Consistent Header**: Page title in `{% block header_left %}` with proper styling
5. **Sidebar Structure**: Use `{{ block.super }}` to inherit logo, then add page-specific content

### What to PRESERVE:
- **Existing sidebar content** (don't replace with dashboard's Quick Stats)
- **Existing main content** (forms, lists, details, etc.)
- **Page-specific functionality** (HTMX interactions, JavaScript, etc.)
- **Current styling** of page content (just ensure it uses proper dark mode classes)

### What to REMOVE/REPLACE:
- **Old logo text** ("CrowdVote" text in headers)
- **Duplicate theme toggles** (remove any custom theme controls)
- **Inconsistent navigation** (replace with base.html navigation)
- **Custom header structures** that don't use `{% block header_left %}`

## Implementation Strategy

### Phase 1: Accounts App Templates (5 templates)
1. `profile_setup.html` - Remove custom theme toggle, use base.html structure
2. `edit_profile.html` - Standardize layout, keep editing functionality
3. `community_discovery.html` - Standardize layout, keep community browsing
4. `member_profile.html` - Standardize layout, keep profile display
5. `member_profile_community.html` - Standardize layout, keep community context

### Phase 2: Democracy App Templates (6 templates)
6. `community_detail.html` - Standardize layout, keep community information
7. `community_manage.html` - Standardize layout, keep management tools
8. `decision_create.html` - Standardize layout, keep creation form
9. `decision_detail.html` - Standardize layout, keep voting interface
10. `decision_list.html` - Standardize layout, keep decision listing
11. `decision_results.html` - Standardize layout, keep results display

### Phase 3: Main App Templates (1 template)
12. `docs.html` - Standardize layout, keep documentation content

## Success Criteria

After completion, every template should:
- ✅ Display the CrowdVote logo image in the upper left corner
- ✅ Show the username dropdown menu in the upper right corner
- ✅ Include the Light/Dark/Auto theme toggle next to the username
- ✅ Have a consistent page header with proper title styling
- ✅ Maintain all existing page-specific functionality and content
- ✅ Support dark mode throughout all components
- ✅ Work responsively on mobile and desktop

## Files to Modify

### Templates to Update (12 files):
- `accounts/templates/accounts/profile_setup.html`
- `accounts/templates/accounts/edit_profile.html`
- `accounts/templates/accounts/community_discovery.html`
- `accounts/templates/accounts/member_profile.html`
- `accounts/templates/accounts/member_profile_community.html`
- `democracy/templates/democracy/community_detail.html`
- `democracy/templates/democracy/community_manage.html`
- `democracy/templates/democracy/decision_create.html`
- `democracy/templates/democracy/decision_detail.html`
- `democracy/templates/democracy/decision_list.html`
- `democracy/templates/democracy/decision_results.html`
- `crowdvote/templates/docs.html`

### Templates to Leave Unchanged:
- `crowdvote/templates/base.html` (already perfect)
- `accounts/templates/accounts/dashboard.html` (reference standard)
- `crowdvote/templates/home.html` (intentionally different landing page)
- `crowdvote/templates/under_construction.html` (special purpose)
- All component templates in `/components/` directories (partial templates)

## Quality Assurance

After each template update:
1. Verify logo appears in upper left and links to dashboard
2. Verify username dropdown appears in upper right with all links
3. Verify theme toggle works and affects entire page
4. Verify page-specific content is preserved and functional
5. Verify dark mode works throughout all page elements
6. Test responsive behavior on mobile devices

## Expected Outcome

A completely consistent user experience across all pages of the CrowdVote application, with professional navigation, branding, and theme controls while preserving all existing functionality and content.
