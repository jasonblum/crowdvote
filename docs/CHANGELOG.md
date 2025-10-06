# CrowdVote Change Log

Format: Each entry includes change reference (docs/changes/), git commit, and concise summary.

---

## 2025-01-06 - Add Interactive Delegation Network Visualization

**Change**: docs/changes/0003_CHANGE-delegation-network-visualization.md  
**Commit**: [pending]  
**Summary**: Added D3.js interactive network visualization to community detail page showing delegation relationships. Nodes represent memberships, edges show Following relationships with tags. Includes force-directed layout, drag-and-drop, zoom/pan. Created site-wide CSS file (crowdvote.css) and component-specific network-visualization.css. Updated community_detail view to build network data structure for D3.js consumption.

---

## 2025-01-06 - Restore Democracy App with Membership-Based Following

**Change**: docs/changes/0002_CHANGE-restore_democracy_app.md  
**Commit**: 3a31e40  
**Summary**: Restored democracy app with Following model using Membership→Membership architecture (community-specific delegation). Updated generate_demo_communities command to create Following relationships between Memberships instead of Users. Added Following to Django admin. Database reset required for fresh migrations.

---

## 2025-01-06 - Rename Accounts App to Security (Part 1)

**Change**: docs/changes/0001_CHANGE-rename_accounts_to_security.md  
**Commit**: 4fcd1bc  
**Summary**: Renamed accounts→security app. Removed community-specific code (Following model, delegation methods) from security. Re-enabled democracy app (needed for CommunityApplication). Disabled signals temporarily. Fresh migrations created for both apps.

---

## 2025-01-06 - Documentation Reorganization

**Change**: N/A (organizational change only)  
**Commit**: 2d23490  
**Summary**: Moved legacy documentation (4,121-line CHANGELOG.md and 26 feature plans) to `docs/legacy/`. Created new `docs/changes/` directory for future change documentation. New CHANGELOG format: concise entries with change references, commit hashes, and brief summaries only.

---
