# Change 0003: Add Interactive Delegation Network Visualization

## Description

Add D3.js-powered interactive network visualization to the community detail page showing delegation relationships between members. Nodes represent community memberships, edges represent Following relationships with tags displayed on the edges. The visualization uses force-directed layout with drag-and-drop interaction, zoom/pan capabilities, and color-coded nodes based on follower count.

## Files to Create

### Static Files
1. **static/css/network-visualization.css**
   - Styles specific to the D3.js network visualization component
   - Includes node styles, link styles, legend styles, etc.
   - Extracted from the standalone network visualization.html

2. **static/css/crowdvote.css**
   - New site-wide CSS file for common styles across all pages
   - Initially contains TODO comments for future CSS consolidation work
   - Should be included in base.html for all pages

### JavaScript/Template Integration
3. **democracy/templates/democracy/components/network_visualization.html**
   - Reusable template component for the D3.js network visualization
   - Contains SVG container, D3.js script, and legend markup
   - Receives network data as context variables

## Files to Modify

### Template Files
1. **democracy/templates/democracy/community_detail.html**
   - Replace placeholder div in "Delegation Network" panel with actual visualization
   - Include network-visualization.css
   - Include D3.js library from CDN: https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js
   - Render network data as JavaScript variables in template
   - Include the network_visualization.html component

2. **crowdvote/templates/base.html**
   - Add link to new site-wide crowdvote.css file
   - Should be loaded after Tailwind but before page-specific CSS

### View Files
3. **democracy/views.py - community_detail() function**
   - Query all Memberships for this community
   - Query all Following relationships where both follower and followee belong to this community
   - Build network data structure for D3.js:
     - `nodes`: List of dicts with membership data (id, username, display_name)
     - `links`: List of dicts with following data (source_id, target_id, tags)
   - Calculate follower counts for color coding
   - Add network data to context

## Data Structure for D3.js

### Nodes Array
```
nodes = [
    {
        'id': '<membership_uuid>',
        'username': 'kevin_minion',
        'display_name': 'Kevin',
    },
    ...
]
```

### Links Array
```
links = [
    {
        'source': '<follower_membership_uuid>',
        'target': '<followee_membership_uuid>',
        'tags': ['apple', 'banana']  # Empty list means "ALL"
    },
    ...
]
```

### Follower Counts
```
follower_counts = {
    '<membership_uuid>': 5,
    ...
}
```

## Algorithm: Building Network Data

### Step 1: Get All Memberships for Community
```
memberships = Membership.objects.filter(community=community).select_related('member')
```

### Step 2: Get All Following Relationships in This Community
```
followings = Following.objects.filter(
    follower__community=community,
    followee__community=community
).select_related('follower__member', 'followee__member')
```

### Step 3: Build Nodes Array
- Iterate through memberships
- For each membership, create node dict with:
  - id: str(membership.id)
  - username: membership.member.username
  - display_name: membership.member.get_full_name() or username

### Step 4: Build Links Array
- Iterate through followings
- For each following, create link dict with:
  - source: str(following.follower.id)
  - target: str(following.followee.id)
  - tags: list of tag names (empty list if following.tags is None/empty, meaning "ALL")

### Step 5: Calculate Follower Counts
- Create dict mapping membership_id → count of incoming links
- Used for color coding nodes (more followers = hotter color)

### Step 6: Pass to Template Context
```
context['network_data'] = {
    'nodes': nodes,
    'links': links,
    'follower_counts': follower_counts,
}
```

## D3.js Implementation Details

### Force Simulation Setup
- Use d3.forceSimulation() with:
  - forceLink: distance=150 for readable spacing
  - forceManyBody: strength=-400 for node repulsion
  - forceCenter: centered in SVG viewport
  - forceCollide: radius=40 to prevent overlap

### Node Styling
- Circle radius: 22px
- Fill color based on follower count (heat map):
  - 0 followers: Gray (#9ca3af)
  - Low: Blue (#3b82f6)
  - Medium-low: Green (#10b981)
  - Medium: Yellow (#eab308)
  - Medium-high: Orange (#f97316)
  - High: Red (#ef4444)
- Text: White, centered, member username

### Edge Styling
- Curved paths using SVG arc
- Arrow markers at target end
- Labels show tags or "ALL" if no tags

### Interactions
- Drag nodes: Update position while maintaining edges
- Zoom/Pan: Standard D3 zoom behavior on SVG
- Auto-stop simulation after 3 seconds for stability

## Template Integration

### In community_detail.html
```django
{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/network-visualization.css' %}">
{% endblock %}

{% block extra_js %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
{% endblock %}

<!-- In Delegation Network panel -->
<div id="network-visualization">
    {% include 'democracy/components/network_visualization.html' with network_data=network_data %}
</div>

<script>
    const networkData = {
        nodes: {{ network_data.nodes|safe }},
        links: {{ network_data.links|safe }},
        followerCounts: {{ network_data.follower_counts|safe }}
    };
    // Initialize D3 visualization with networkData
</script>
```

## CSS Organization

### network-visualization.css
- Contains all styles from the standalone network visualization.html
- Scoped to #network-visualization container
- Includes: .link, .link-label, .node, .legend, controls

### crowdvote.css (Site-wide)
- Add header comment:
```css
/*
 * CrowdVote Site-wide Styles
 * 
 * TODO: In a future change, consolidate repetitive CSS from templates into this file.
 * Look for common patterns in:
 * - Panel/card styles
 * - Button styles
 * - Typography
 * - Dark mode utilities
 * - Layout helpers
 */
```

## Testing Requirements

### Manual Testing
1. Visit community detail page for "Minion Collective"
2. Verify network visualization renders in Delegation Network panel
3. Verify all minion members appear as nodes
4. Verify following relationships appear as edges with correct tags
5. Test drag interaction - nodes should move smoothly
6. Test zoom/pan - should work on background drag and scroll
7. Verify node colors reflect follower counts (leaders should be hotter colors)
8. Verify "ALL" appears on edges with no tags
9. Verify specific tags appear on edges with tags
10. Test in both light and dark mode

### Unit Tests (Future)
- Test network data building in community_detail view
- Test follower count calculation
- Test edge case: community with no following relationships
- Test edge case: members with no followers
- Test edge case: circular following relationships

## Notes

- D3.js loaded from CDN (not bundled) - acceptable for MVP
- No API endpoint yet - will create in future change for better separation
- No performance optimization - will address when supporting larger communities
- Simulation auto-stops after 3 seconds to reduce CPU usage
- Following model must have `tags` field (string or array) - verify this exists

## Reference Files

- Source: `crowdvote/templates/network visualization.html` (standalone demo)
- Target: `democracy/templates/democracy/community_detail.html` (integration point)
- Models: `democracy/models.py` (Membership, Following)
