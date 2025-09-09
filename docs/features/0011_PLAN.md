# Plan #11: Consistent Application Layout & Navigation System

## Overview

Standardize the entire CrowdVote application with a consistent layout, navigation system, and theme behavior. The **Decision Results page** serves as our design standard - every page should follow this modern application shell pattern with sidebar navigation and top header.

## Design Standards (Based on Decision Results Page)

### 🎯 **Target Layout Pattern**
- **Top Header**: Logo (left) → CrowdVote brand → User menu (right) with avatar, username, logout
- **Sidebar Panel**: Page-specific navigation and content details (280px width)
- **Main Content**: Full-width responsive content area
- **Theme Toggle**: Light/Dark/Auto in sidebar (except landing page)
- **Consistent Theming**: Dark mode affects entire page, not just header

### 🧭 **Navigation Requirements**
- **Logo ("CrowdVote")**: Links to user's profile page
- **Username Dropdown**: Click username to reveal dropdown menu with:
  - Profile link (to user's profile page)
  - Documentation link (to /docs/)
  - Logout link (logs out and returns to landing page)
- **Theme toggle**: Available in sidebar on authenticated pages only (not on landing page)
- **No "Home" link**: Removed since logo already provides navigation

## Current Template Status Audit

### ✅ **COMPLIANT (Modern Application Shell)**
1. **Decision Results** (`democracy/decision_results.html`)
   - ✅ Sidebar navigation with page sections
   - ✅ Top header with proper navigation
   - ✅ Complete dark mode theming
   - ✅ Theme toggle functional

### 🟡 **PARTIALLY COMPLIANT (Needs Updates)**
2. **Landing Page** (`crowdvote/home.html`)
   - ✅ No theme toggle needed (as requested)
   - 🔄 Should redirect logged-in users to profile
   - ✅ Modern styling already

3. **Documentation/FAQ** (`crowdvote/docs.html`)
   - 🔄 Has sidebar but not matching decision results style
   - 🔄 Theme toggle only affects header
   - 🔄 Navigation not consistent with target

4. **Decision Detail/Voting** (`democracy/decision_detail.html`)
   - 🔄 Theme toggle only affects navigation banner
   - 🔄 No sidebar navigation panel
   - 🔄 Remove "Save Draft" button (as requested)
   - 🔄 Layout needs complete redesign

### ❌ **NON-COMPLIANT (Major Updates Needed)**
5. **Community Detail** (`democracy/community_detail.html`)
   - ❌ Old centered layout
   - ❌ No consistent navigation
   - ❌ Theme issues

6. **Community List** (`democracy/decision_list.html`)
   - ❌ Basic layout
   - ❌ No sidebar navigation
   - ❌ Theme inconsistencies

7. **Decision Create** (`democracy/decision_create.html`)
   - ❌ Form-focused layout
   - ❌ No application shell
   - ❌ Theme issues

8. **Profile Setup** (`accounts/profile_setup.html`)
   - ✅ Modern layout but different style
   - 🔄 Should match decision results pattern
   - 🔄 Navigation needs updates

9. **Dashboard** (`accounts/dashboard.html`)
   - 🔄 Has some modern elements
   - 🔄 Navigation needs standardization
   - 🔄 Theme behavior needs review

10. **Community Discovery** (`accounts/community_discovery.html`)
    - ❌ Basic card layout
    - ❌ No consistent navigation
    - ❌ Theme issues

11. **Member Profile** (`accounts/member_profile_community.html`)
    - ✅ Modern styling
    - 🔄 Needs navigation standardization
    - 🔄 Theme behavior review

12. **Edit Profile** (`accounts/edit_profile.html`)
    - ✅ Modern card layout
    - 🔄 Navigation needs updates
    - 🔄 Theme consistency check

13. **Community Management** (`democracy/community_manage.html`)
    - 🔄 Management interface needs review
    - 🔄 Layout standardization needed

## Implementation Plan

### **Phase 1: Base Template Enhancement** 🏗️
- **Update `crowdvote/templates/base.html`**:
  - Standardize header navigation (logo → user menu with logout)
  - Implement proper navigation links (all point to user profile)
  - Ensure theme toggle affects entire page layout
  - Add sidebar slot for page-specific navigation

### **Phase 2: High-Priority Pages** 🎯
1. **Decision Detail/Voting** (`democracy/decision_detail.html`)
   - Add sidebar with decision info and navigation
   - Remove "Save Draft" button
   - Fix theme toggle to affect entire page
   - Match decision results layout

2. **Documentation/FAQ** (`crowdvote/docs.html`)
   - Redesign sidebar to match decision results style
   - Fix theme behavior for entire page
   - Standardize navigation

3. **Community Detail** (`democracy/community_detail.html`) - **FULLY COMPLETED** ✅:
   - ✅ **COMPLETED**: Add sidebar with community info and actions  
   - ✅ **COMPLETED**: Implement full application shell layout with proper spacing
   - ✅ **COMPLETED**: Fix theme toggle not affecting page content (working!)
   - ✅ **COMPLETED**: Fix TemplateSyntaxError (nested block tag issue resolved)
   - ✅ **COMPLETED**: Update header section with proper dark mode and consistent card styling
   - ✅ **COMPLETED**: Update Community Actions section with dark mode and consistent layout
   - ✅ **COMPLETED**: Update Members section header and filters with dark mode
   - ✅ **COMPLETED**: Update Delegation Network panel with consistent styling and dark mode
   - ✅ **COMPLETED**: Update Recent Decisions panel with consistent styling and dark mode
   - ✅ **COMPLETED**: All panels now use consistent `rounded-lg shadow-sm ring-1` styling with proper spacing

### **Phase 3: Form and Management Pages** 📝
4. **Profile Setup** (`accounts/profile_setup.html`)
   - Adapt to new navigation standards
   - Maintain current modern styling
   - Add appropriate sidebar content

5. **Dashboard** (`accounts/dashboard.html`)
   - Standardize with application shell
   - Add sidebar with user stats and quick actions
   - Fix navigation and theme behavior

6. **Decision Create** (`democracy/decision_create.html`)
   - Implement application shell layout
   - Add sidebar with form guidance
   - Fix theme and navigation

### **Phase 4: Secondary Pages** 🔧
7. **Community Discovery** (`accounts/community_discovery.html`)
8. **Decision List** (`democracy/decision_list.html`) - ✅ **FIXED**: Updated to application shell with sidebar and full dark mode support
9. **Community Management** (`democracy/community_manage.html`)
10. **Member Profile** (`accounts/member_profile_community.html`)
11. **Edit Profile** (`accounts/edit_profile.html`)
12. **User Profile** (`accounts/member_profile.html`) - ✅ **COMPLETED**:
   - ✅ Updated to use Jdenticon avatars instead of initials  
   - ✅ Updated to use application shell layout with proper sidebar
   - ✅ Added comprehensive dark mode support (Following/Followers panels, delegation actions)
   - ✅ Fixed sidebar header to show user's Jdenticon avatar and name instead of generic icon

### **Phase 5: Navigation Enhancement** 🧭
- **Update all internal links**:
  - Logo clicks → user profile
  - Username dropdown → Profile, Documentation, Logout options
  - Remove "Home" link (redundant with logo)
- **Landing page logic**: Redirect logged-in users to profile

## 🚨 **Critical Issues Found & Fixed**

### **Template Syntax Error** ✅ **FIXED**
- **Issue**: `decision_detail.html` had invalid `{% endblock %}` on line 474
- **Cause**: JavaScript was placed outside template blocks, causing double endblock
- **Fix**: Wrapped JavaScript in `{% block scripts %}` block

### **Nested Sidebar Issue** ✅ **FIXED**
- **Issue**: `decision_results.html` had two sidebars - one nested inside the other
- **Cause**: Page implemented custom sidebar structure inside `{% block content %}` instead of using `{% block sidebar_content %}`
- **Fix**: Moved sidebar content to proper `{% block sidebar_content %}` and updated template structure

### **Theme Toggle Not Affecting Content** 🔧 **IN PROGRESS**
- **Issue**: Theme toggle only affects navigation/sidebar, not page content
- **Cause**: Pages not using application shell layout + missing dark mode classes
- **Affected Pages**: 
  - `accounts/member_profile.html` 
  - `democracy/community_detail.html`
  - Other pages not yet updated to new layout
- **Fix Required**: Update to application shell + add dark mode classes to all content

### **Layout Inconsistency** 🔧 **IN PROGRESS**  
- **Issue**: Some pages still use old layout without sidebar
- **Cause**: Pages not updated to Plan #11 application shell structure
- **Fix Required**: Update all pages to use `{% block sidebar_content %}` pattern

## Technical Requirements

### **Theme System Standards**
```html
<!-- Every page (except landing) should have this structure -->
<body class="min-h-screen bg-gray-50 dark:bg-gray-900">
  <div class="lg:flex">
    <!-- Sidebar Navigation -->
    <nav class="lg:w-80 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700">
      <!-- Theme toggle in sidebar -->
    </nav>
    
    <!-- Main Content -->
    <main class="flex-1">
      <!-- Page header -->
      <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <!-- Top navigation -->
      </div>
      
      <!-- Page content -->
      <div class="max-w-4xl mx-auto py-8 px-6">
        <!-- Content cards -->
      </div>
    </main>
  </div>
</body>
```

### **Navigation Component Standards**
- **Header height**: `64px` consistent
- **Sidebar width**: `320px` (`lg:w-80`)
- **Logo placement**: Top-left with profile link
- **User menu**: Avatar + Username + Dropdown arrow (Alpine.js powered)
- **Dropdown menu**: Profile, Documentation, Logout (with icons)
- **Theme toggle**: In sidebar with Light/Dark/Auto options

## Success Criteria

### ✅ **Layout Consistency**
- All pages use the same application shell pattern
- Sidebar navigation on every page (except landing)
- Consistent header with proper navigation links

### ✅ **Theme Behavior**
- Dark mode affects entire page layout, not just header
- Theme toggle available in sidebar on authenticated pages only
- No theme toggle on landing page (background image doesn't need theming)
- Smooth transitions between themes

### ✅ **Navigation Functionality**
- Logo links to user profile
- Username dropdown provides: Profile, Documentation, Logout
- Documentation accessible from all authenticated pages
- Logged-in users redirected from landing page

### ✅ **User Experience**
- "Save Draft" button removed from voting page
- Consistent visual hierarchy and spacing
- Mobile-responsive on all pages

## Files to Modify

### **Base Templates**
- `crowdvote/templates/base.html` - Core application shell
- `crowdvote/views.py` - Landing page redirect logic

### **High Priority**
- `democracy/templates/democracy/decision_detail.html`
- `crowdvote/templates/docs.html`
- `democracy/templates/democracy/community_detail.html`

### **Secondary Updates**
- All remaining template files listed in audit
- Navigation links throughout application
- Theme toggle JavaScript consistency

---

**Goal**: Transform CrowdVote from a collection of pages with different layouts into a cohesive, professional application with consistent navigation and theming throughout. The Decision Results page becomes our design system foundation! 🎨🧭✨
