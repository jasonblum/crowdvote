# Feature #9: Delegation Tree Visualization System

## Overview

Implement an interactive delegation tree visualization that shows how votes flow through trust networks in CrowdVote's delegative democracy system. The visualization will display nested bullet-style trees showing who follows whom, how votes are inherited and calculated, and which tags enable delegation relationships. The system must be both interactive (with hover details and profile links) and print-friendly for transparency and auditability.

## Context

Currently, the Decision Results page shows a "Coming in Phase 2" placeholder for the delegation tree section. Users can see that votes are "Manual" vs "Calculated" but cannot understand how calculated votes were derived or explore the trust networks that enable delegative democracy. This visualization will make the delegation system transparent and help users understand how to build influence through expertise and trust.

## Technical Requirements

### Phase 1: Data Structure Enhancement

**Enhanced DecisionSnapshot Model (`democracy/models.py`)**:
- Expand `snapshot_data.delegation_tree` JSON structure to include:
  ```json
  {
    "delegation_tree": {
      "nodes": [
        {
          "voter_id": "uuid",
          "username": "joe_smith",
          "is_anonymous": false,
          "vote_type": "manual|calculated",
          "votes": {
            "choice_uuid": {
              "stars": 4.0,
              "sources": [
                {
                  "from_voter": "alice_chen",
                  "stars": 5.0,
                  "tags": ["budget"],
                  "order": 1,
                  "is_anonymous": false
                }
              ]
            }
          },
          "tags": ["budget", "maintenance"],
          "inherited_tags": ["budget"],
          "delegation_depth": 0
        }
      ],
      "edges": [
        {
          "follower": "voter_uuid",
          "followee": "voter_uuid", 
          "tags": ["budget"],
          "order": 1,
          "active_for_decision": true
        }
      ],
      "inheritance_chains": [
        {
          "final_voter": "mary_johnson",
          "choice": "choice_uuid",
          "final_stars": 3.25,
          "calculation_path": [
            {"voter": "alice_chen", "stars": 5.0, "weight": 0.33, "tags": ["budget"]},
            {"voter": "bob_wilson", "stars": 2.0, "weight": 0.33, "tags": ["maintenance"]},
            {"voter": "carol_davis", "stars": 3.0, "weight": 0.34, "tags": ["budget"]}
          ]
        }
      ]
    }
  }
  ```

**Enhanced StageBallots Service (`democracy/services.py`)**:
- Modify `get_or_calculate_ballot()` to capture detailed delegation tree data
- Track inheritance chains with source attribution and tag matching
- Calculate delegation depth levels for proper nesting
- Store fractional star calculations with source breakdowns

### Phase 2: Delegation Tree Component

**New Template Component (`democracy/templates/democracy/components/delegation_tree.html`)**:
- Nested bullet structure using CSS indentation
- Expandable/collapsible sections for deep delegation chains
- Fractional star display using CSS partial fills
- Tag inheritance visualization with color coding
- Anonymous voter handling with GUID display

**CSS Styling (`static/css/delegation_tree.css`)**:
```css
.delegation-tree {
  font-family: 'Courier New', monospace; /* Print-friendly */
  line-height: 1.6;
}

.tree-node {
  margin-left: 20px;
  border-left: 2px solid #e5e7eb;
  padding-left: 15px;
}

.tree-node.manual {
  border-left-color: #10b981; /* Green for manual votes */
}

.tree-node.calculated {
  border-left-color: #8b5cf6; /* Purple for calculated votes */
}

.fractional-stars {
  display: inline-flex;
  align-items: center;
}

.star-partial {
  background: linear-gradient(90deg, #fbbf24 var(--fill-percent), #d1d5db var(--fill-percent));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

@media print {
  .delegation-tree {
    color: black !important;
    background: white !important;
  }
  .interactive-elements {
    display: none;
  }
}
```

### Phase 3: Interactive Features

**JavaScript Functionality (`static/js/delegation_tree.js`)**:
- Expand/collapse delegation chains
- Hover popovers showing calculation details
- Click-to-copy voter information for sharing
- Print mode toggle (hide interactive elements)
- Tag filtering and highlighting

**Hover Popover Content**:
```html
<div class="popover">
  <h4>Vote Calculation for Mary Johnson</h4>
  <p><strong>Choice A: 3.25 stars</strong></p>
  <ul>
    <li>Alice Chen: 5.0 stars (weight: 33.3%) [budget]</li>
    <li>Bob Wilson: 2.0 stars (weight: 33.3%) [maintenance]</li>
    <li>Carol Davis: 3.0 stars (weight: 33.4%) [budget]</li>
  </ul>
  <p><strong>Calculation:</strong> (5.0×0.333 + 2.0×0.333 + 3.0×0.334) = 3.25</p>
  <p><strong>Tags Inherited:</strong> budget, maintenance</p>
  <p><strong>Delegation Depth:</strong> Level 2</p>
</div>
```

### Phase 4: Integration with Decision Results

**Enhanced decision_results View (`democracy/views.py`)**:
- Generate delegation tree data during snapshot creation
- Pass tree structure to template context
- Handle anonymous voter privacy in tree display
- Optimize queries for large delegation networks

**Updated decision_results.html Template**:
- Replace "Coming in Phase 2" placeholder with delegation tree component
- Add tree controls (expand all, collapse all, print mode)
- Integrate with existing search/filter functionality
- Maintain responsive design for mobile viewing

## User Experience Requirements

### Visual Design
- **Nested Bullet Structure**: Clear indentation showing delegation hierarchy
- **Fractional Stars**: Visual representation of calculated averages (★★★◐☆ for 3.25)
- **Color Coding**: Green for manual votes, purple for calculated votes
- **Tag Badges**: Small colored badges showing inherited tags
- **Print Optimization**: Clean black/white layout for paper printing

### Interactive Elements
- **Expandable Sections**: Click to show/hide deep delegation chains
- **Hover Details**: Rich popovers with calculation breakdowns
- **Profile Links**: Clickable usernames (when not anonymous) linking to member profiles
- **Tag Highlighting**: Click tags to highlight inheritance paths
- **Copy/Share**: Easy sharing of specific delegation paths

### Privacy & Anonymity
- **Anonymous Voters**: Show as "Anonymous Voter #ABC123" with no profile links
- **GUID Consistency**: Same anonymous voter shows same GUID across views
- **Privacy Controls**: Respect user anonymity preferences in all displays
- **Audit Trail**: Complete transparency while protecting individual privacy

## Technical Implementation Details

### Data Flow
1. **Snapshot Creation**: Enhanced StageBallots service captures delegation tree data
2. **Tree Building**: Recursive algorithm builds nested tree structure from delegation chains
3. **Rendering**: Template component renders interactive tree with proper nesting
4. **Interactivity**: JavaScript adds expand/collapse, hover, and filtering features

### Performance Considerations
- **Lazy Loading**: Load delegation details on demand for large trees
- **Caching**: Cache tree structures in DecisionSnapshot for fast repeated access
- **Pagination**: Limit tree depth display with "show more" options
- **Mobile Optimization**: Collapsible sections for small screens

### Accessibility
- **Screen Readers**: Proper ARIA labels for tree navigation
- **Keyboard Navigation**: Tab through tree nodes and interactive elements
- **High Contrast**: Ensure sufficient contrast for all visual elements
- **Print Accessibility**: Clean, readable layout when printed

## Files to Create/Modify

### New Files
- `democracy/templates/democracy/components/delegation_tree.html` - Tree component template
- `static/css/delegation_tree.css` - Tree-specific styling
- `static/js/delegation_tree.js` - Interactive functionality

### Modified Files
- `democracy/models.py` - Enhanced DecisionSnapshot JSON structure
- `democracy/services.py` - Enhanced StageBallots with tree data capture
- `democracy/views.py` - Enhanced decision_results view with tree generation
- `democracy/templates/democracy/decision_results.html` - Integration of tree component
- `democracy/admin.py` - Admin interface for debugging tree data

## Success Criteria

### Functional Requirements
- ✅ Display complete delegation chains for all calculated votes
- ✅ Show fractional star ratings with visual representation
- ✅ Enable expand/collapse of delegation tree sections
- ✅ Provide hover details for vote calculations
- ✅ Link to member profiles (when not anonymous)
- ✅ Maintain print-friendly layout
- ✅ Handle anonymous voters with consistent GUIDs

### User Experience Goals
- **Transparency**: Users understand exactly how their democracy works
- **Education**: New users learn how to build influence through delegation
- **Trust Building**: Clear attribution helps users identify experts to follow
- **Auditability**: Complete vote trails enable community oversight
- **Accessibility**: Works for all users including screen readers and print

This delegation tree visualization will transform CrowdVote from a "black box" voting system into a completely transparent democratic platform where every vote can be traced, understood, and audited by the community.
