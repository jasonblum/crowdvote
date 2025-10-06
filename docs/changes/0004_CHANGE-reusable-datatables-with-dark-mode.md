# Change 0004: Add Reusable DataTables Component with Dark Mode Support

## Description

Implement DataTables library across the application to provide sortable, searchable, paginated tables with dark mode support. Create a reusable component pattern that can be applied consistently to any table in the app. Replace existing card-based lists with proper HTML tables on three pages: community members, decisions (docket), and community discovery.

## Files to Create

### CSS Files
1. **static/css/datatables-custom.css**
   - Custom styling for DataTables to integrate with Tailwind
   - Comprehensive dark mode support
   - Styled pagination controls, search box, info text
   - Table header/cell styling consistent with app design

### Template Components
2. **democracy/templates/democracy/components/datatable_wrapper.html**
   - Reusable wrapper for DataTables initialization
   - Accepts configuration parameters (table ID, columns, sort order, etc.)
   - Standard search box and pagination HTML structure

## Files to Modify

### Base Template
1. **crowdvote/templates/base.html**
   - Add DataTables CDN links (JS and minimal CSS)
   - Include datatables-custom.css after Tailwind

### Community Detail Page
2. **democracy/templates/democracy/community_detail.html**
   - Convert Members section from div cards to HTML `<table>`
   - Convert Docket (Decisions) section from div cards to HTML `<table>`
   - Add DataTables initialization for both tables

### Community Discovery Page
3. **security/templates/accounts/community_discovery.html**
   - Convert community cards to HTML `<table>`
   - Add DataTables initialization

### Views
4. **democracy/views.py - community_detail()**
   - Keep existing data structure (already provides memberships and decisions)
   - No changes needed - data is already in context

5. **security/views.py - community_discovery()**
   - Verify communities queryset includes all needed fields
   - Add membership status check for "Already Member" indicator

## DataTables Configuration

### Common Settings (All Tables)
```javascript
{
    pageLength: 10,
    lengthMenu: [10, 25, 50, 100],
    searching: true,
    ordering: true,
    info: true,
    autoWidth: false,
    language: {
        search: "Search:",
        lengthMenu: "Show _MENU_ entries",
        info: "Showing _START_ to _END_ of _TOTAL_ entries",
        paginate: {
            first: "First",
            last: "Last",
            next: "Next",
            previous: "Previous"
        }
    }
}
```

### Table-Specific Configurations

#### Members Table
- **Columns**: Avatar/Icon, Name, Username, Roles (badges), Joined Date
- **Sort order**: Column 2 (Username) ascending
- **Sortable columns**: Name, Username, Joined Date
- **Non-sortable**: Avatar, Roles (contains badges/buttons)
- **Search columns**: Name, Username

#### Decisions Table (Docket)
- **Columns**: Status (badge), Title, Close Date, Votes, Choices, Action
- **Sort order**: Column 2 (Close Date) descending (most recent first)
- **Sortable columns**: Title, Close Date, Votes, Choices
- **Non-sortable**: Status, Action
- **Search columns**: Title

#### Communities Table (Discovery)
- **Columns**: Name, Members Count, Description, Status/Action
- **Sort order**: Column 0 (Name) ascending
- **Sortable columns**: Name, Members Count
- **Non-sortable**: Description (truncated), Status/Action
- **Search columns**: Name, Description

## HTML Table Structures

### Members Table
```html
<table id="members-table" class="display w-full">
    <thead>
        <tr>
            <th>Member</th>
            <th>Username</th>
            <th>Roles</th>
            <th>Joined</th>
        </tr>
    </thead>
    <tbody>
        {% for membership in memberships %}
        <tr>
            <td>
                <div class="flex items-center">
                    <span class="identicon">{{ membership.member.username|first }}</span>
                    <span>{{ membership.member.get_full_name|default:membership.member.username }}</span>
                </div>
            </td>
            <td>@{{ membership.member.username }}</td>
            <td>
                {% if membership.is_community_manager %}
                    <span class="badge badge-purple">👑 Manager</span>
                {% endif %}
                {% if membership.is_voting_community_member %}
                    <span class="badge badge-green">🗳️ Voter</span>
                {% else %}
                    <span class="badge badge-blue">📢 Lobbyist</span>
                {% endif %}
            </td>
            <td>{{ membership.dt_joined|date:"M Y" }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

### Decisions Table (Docket)
```html
<table id="decisions-table" class="display w-full">
    <thead>
        <tr>
            <th>Status</th>
            <th>Title</th>
            <th>Close Date</th>
            <th>Votes</th>
            <th>Choices</th>
            <th>Action</th>
        </tr>
    </thead>
    <tbody>
        {% for decision in decisions %}
        <tr>
            <td>
                {% if decision.status == 'active' %}
                    <span class="badge badge-green">🟢 Active</span>
                {% elif decision.status == 'closed' %}
                    <span class="badge badge-gray">🔴 Closed</span>
                {% elif decision.status == 'draft' %}
                    <span class="badge badge-yellow">⚪ Draft</span>
                {% endif %}
            </td>
            <td>
                <a href="{% url 'democracy:decision_detail' community.id decision.id %}">
                    {{ decision.title }}
                </a>
            </td>
            <td data-order="{{ decision.dt_close|date:'U' }}">
                {{ decision.dt_close|date:"M j, Y g:i A" }}
            </td>
            <td>{{ decision.total_votes }}</td>
            <td>{{ decision.total_choices }}</td>
            <td>
                <a href="{% url 'democracy:decision_detail' community.id decision.id %}" class="btn-primary-sm">
                    {% if decision.status == 'active' %}Vote{% else %}View{% endif %}
                </a>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

### Communities Table (Discovery)
```html
<table id="communities-table" class="display w-full">
    <thead>
        <tr>
            <th>Community</th>
            <th>Members</th>
            <th>Description</th>
            <th>Status</th>
        </tr>
    </thead>
    <tbody>
        {% for community in communities %}
        <tr>
            <td>
                <a href="{% url 'democracy:community_detail' community.id %}" class="font-semibold">
                    {{ community.name }}
                </a>
            </td>
            <td>{{ community.member_count }}</td>
            <td>{{ community.description|truncatewords:15 }}</td>
            <td>
                {% if community.user_is_member %}
                    <span class="badge badge-green">✓ Member</span>
                {% else %}
                    <a href="{% url 'security:apply_to_community' community.id %}" class="btn-primary-sm">
                        Apply
                    </a>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

## CSS Styling Strategy

### DataTables Custom CSS (datatables-custom.css)
```css
/* Base table styling with Tailwind */
.dataTables_wrapper table.dataTable {
    @apply w-full border-collapse;
}

.dataTables_wrapper table.dataTable thead th {
    @apply bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300;
    @apply font-semibold text-sm px-4 py-3 text-left;
    @apply border-b border-gray-200 dark:border-gray-600;
}

.dataTables_wrapper table.dataTable tbody td {
    @apply px-4 py-3 text-sm text-gray-900 dark:text-gray-100;
    @apply border-b border-gray-200 dark:border-gray-700;
}

.dataTables_wrapper table.dataTable tbody tr:hover {
    @apply bg-gray-50 dark:bg-gray-700;
}

/* Search box styling */
.dataTables_wrapper .dataTables_filter input {
    @apply border border-gray-300 dark:border-gray-600;
    @apply rounded px-3 py-2 text-sm;
    @apply bg-white dark:bg-gray-800;
    @apply text-gray-900 dark:text-gray-100;
}

/* Pagination styling */
.dataTables_wrapper .dataTables_paginate .paginate_button {
    @apply px-3 py-1 mx-1 rounded;
    @apply bg-white dark:bg-gray-800;
    @apply border border-gray-300 dark:border-gray-600;
    @apply text-gray-700 dark:text-gray-300;
}

.dataTables_wrapper .dataTables_paginate .paginate_button.current {
    @apply bg-blue-600 text-white border-blue-600;
}

/* Badge classes for table cells */
.badge {
    @apply inline-flex items-center px-2 py-1 rounded text-xs font-medium;
}
.badge-green { @apply bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200; }
.badge-blue { @apply bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200; }
.badge-purple { @apply bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-200; }
.badge-yellow { @apply bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200; }
.badge-gray { @apply bg-gray-100 dark:bg-gray-600 text-gray-800 dark:text-gray-200; }

/* Button classes */
.btn-primary-sm {
    @apply px-3 py-1.5 bg-blue-600 text-white text-xs rounded-md hover:bg-blue-700 font-medium;
}
```

## DataTables Initialization Pattern

Each page will initialize its table like this:

```javascript
<script>
$(document).ready(function() {
    $('#members-table').DataTable({
        pageLength: 10,
        lengthMenu: [10, 25, 50, 100],
        order: [[1, 'asc']], // Sort by username column
        columnDefs: [
            { orderable: false, targets: [0, 2] } // Avatar and Roles not sortable
        ]
    });
});
</script>
```

## Implementation Steps

### Phase 1: Setup DataTables Infrastructure
1. Add DataTables CDN to base.html
2. Create datatables-custom.css with Tailwind styling
3. Test with simple table to verify dark mode works

### Phase 2: Members Table (Community Detail)
1. Convert members section from div cards to HTML table
2. Add DataTables initialization
3. Test sorting, searching, pagination
4. Verify badges render correctly

### Phase 3: Decisions Table (Community Detail)
1. Convert docket section from div cards to HTML table
2. Add DataTables initialization
3. Handle date sorting with data-order attribute
4. Test all functionality

### Phase 4: Communities Table (Discovery Page)
1. Update view to add member count and membership status
2. Convert community cards to HTML table
3. Add DataTables initialization
4. Test application flow (join links work)

## Benefits

1. **Consistency**: Same table behavior across entire app
2. **Performance**: DataTables handles large datasets efficiently
3. **User Experience**: Instant search, flexible pagination, sortable columns
4. **Maintainability**: Write dark mode CSS once, reuse everywhere
5. **Scalability**: Easy to add new tables following the same pattern
6. **Accessibility**: DataTables has built-in ARIA support

## Testing Requirements

### Manual Testing
1. Test all three tables (members, decisions, communities)
2. Verify sorting works on each sortable column
3. Verify search filters results correctly
4. Test pagination (change page size, navigate pages)
5. Test dark mode toggle - all table elements adapt
6. Verify badges and buttons render correctly in cells
7. Verify links in table cells work
8. Test with empty tables (show appropriate message)
9. Test with large datasets (100+ rows)
10. Verify table adapts to panel width

### Edge Cases
- Empty search results
- Single-page table (fewer than 10 rows)
- Very long text in cells (truncation)
- Special characters in search

## Notes

- DataTables CDN used (not bundled) - acceptable for MVP
- No mobile responsive extension (per user preference)
- Using jQuery-based DataTables (most stable version)
- Dark mode handled via CSS overrides, not DataTables theme
- Action buttons and badges work fine inside table cells
- Date sorting uses data-order attribute for proper chronological sort

## CDN Links

```html
<!-- DataTables CSS -->
<link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">

<!-- jQuery (required for DataTables) -->
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>

<!-- DataTables JS -->
<script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
```

## Reference Files

- Current members section: `democracy/templates/democracy/community_detail.html` lines 172-239
- Current decisions section: `democracy/templates/democracy/community_detail.html` lines 262-363
- Community discovery page: `security/templates/accounts/community_discovery.html`
