# CrowdVote Change Log

Format: Each entry includes change reference (docs/changes/), git commit, and concise summary.

---

## 2025-01-06 - Add Reusable DataTables Component with Dark Mode

**Change**: docs/changes/0004_CHANGE-reusable-datatables-with-dark-mode.md  
**Commit**: ce0ad20  
**Summary**: Implemented DataTables library with comprehensive dark mode support across the app. Converted three card-based lists to sortable, searchable, paginated tables: Members table (community detail), Decisions table (docket), and Communities table (discovery page). Created reusable pattern with datatables-custom.css containing Tailwind-style dark mode styling. Tables default to 10 rows per page with options for 10/25/50/100. All tables support column sorting, instant search, and badges/buttons in cells.

---

## 2025-01-06 - Add Interactive Delegation Network Visualization

**Change**: docs/changes/0003_CHANGE-delegation-network-visualization.md  
**Commit**: 397bda7  
**Summary**: Added D3.js interactive network visualization to community detail page showing delegation relationships. Nodes represent memberships, edges show Following relationships with tags. Includes force-directed layout, drag-and-drop, zoom/pan, classic heat map colors (gray→light blue→blue→purple→red). Created site-wide CSS file (crowdvote.css) and component-specific network-visualization.css. Added timestamp display for network data currency.

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
