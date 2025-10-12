# CrowdVote Change Log

Format: Each entry includes change reference (docs/changes/), git commit, and concise summary.

---

## 2025-10-12 - Complete Snapshot Calculation Engine (Plan #9)

**Change**: docs/changes/0009_CHANGE-complete-snapshot-calculation-engine.md  
**Commit**: (pending)  
**Summary**: Completed the incomplete aspects of Plan #8 by fully implementing `SnapshotBasedStageBallots._calculate_ballot_from_snapshot()` - a recursive engine that calculates ballots entirely from frozen snapshot data (no live DB queries). Method builds complete delegation tree structure (nodes, edges, inheritance_chains, circular_prevented) with proper tag matching, ballot averaging, and depth tracking. Fixed signal flow in `democracy/signals.py` to call `StageBallots` BEFORE `CreateCalculationSnapshot` so ballots exist in DB to be captured. Removed obsolete `decision_results` view (lines 1307-1496 in `views.py`) and URL pattern - correct flow is now Decision Detail → Historical Results Table → Snapshot Detail. Engine successfully processes real data: 38 ballots, 38 nodes, 13 edges, 20 inheritance chains, max depth 2 levels. All 19 snapshot tests passing. Core calculation engine complete - delegation tree visualization in templates is functional and ready.

---

## 2025-10-11 - Event-Driven Ballot Calculation with System Snapshots

**Change**: docs/changes/0008_CHANGE-event-driven-ballot-calculation-with-snapshots.md  
**Commit**: 4412ac4  
**Summary**: Implemented three-stage democratic process: (1) Ballot calculation using simple averaging (not STAR voting) with full Decimal precision, (2) Immutable system snapshots capturing complete delegation trees and ballot state, (3) STAR voting tally on frozen snapshot data. Refactored `StageBallots` service to maintain Decimal throughout, removed `round()` calls. Rewrote `Tally` service to integrate Plan #7 `STARVotingTally` class. Completed `SnapshotBasedStageBallots` to process from frozen snapshot data. Updated `CreateCalculationSnapshot` to store Decimals as strings in JSON. Fixed `democracy/signals.py` to pass User IDs instead of Membership IDs. Renamed `stage_and_tally_ballots.py` → `stage_snapshot_and_tally_ballots.py`. Added historical snapshots table (DataTables) to `decision_detail.html`. Created `snapshot_detail.html` template with delegation tree visualization (modeled after `vote-inheritance-tree.html`). Added `snapshot_detail` view with influence analytics. Updated `docs.html` to reflect three-stage process and simple averaging for ballots. Fixed 19 test files with obsolete `accounts` imports → `security`. Tests: 461 passing, 165 legacy tests need updates.

---

## 2025-10-11 - STAR Voting with Decimal Support

**Change**: docs/changes/0007_CHANGE-implement-star-voting-with-float-support.md  
**Commit**: 22f6b5a  
**Summary**: Implemented standalone STAR voting algorithm with native Decimal support for fractional star ratings (up to 8 decimal places). Created `democracy/star_voting.py` with `STARVotingTally` service implementing complete Score Then Automatic Runoff algorithm following Official Tiebreaker Protocol from starvoting.org. Raises `UnresolvedTieError` for Community Manager resolution (no random tie-breaking). Created `democracy/exceptions.py` for custom exceptions. Comprehensive test suite (22 tests) covering integer/Decimal ballots, tiebreaker protocol (all 4 steps), edge cases, and complex delegation scenarios producing 8-decimal precision. Standalone module - not integrated with existing code yet. Unblocks Plan #8 (snapshot-based calculations).

---

## 2025-01-08 - Membership-Level Anonymity System

**Change**: docs/changes/0006_CHANGE-membership-level-anonymity.md  
**Commit**: d2155f9  
**Summary**: Refactored anonymity from ballot-level to membership-level. Renamed `Membership.is_anonymous_by_default` → `is_anonymous` (default True). Added database constraint preventing anonymous lobbyists. Removed ballot `is_anonymous` field. Added HTMX modal (⚙️ My Settings) for per-community anonymity toggle. Community detail table now shows Member (first/last name) and Username columns; anonymous members display "Anonymous" with no profile link. Network visualization shows "Anonymous" nodes. Ballot page updated with tag chips UI, removed anonymity checkbox. Enhanced `generate_demo_communities` command: `--reset-database` flag, admin/admin superuser (DEBUG only), 3 new application-required communities (Ocean View, Tech Workers, Riverside), 8 themed decisions (4 per community) with varied close times, 43 Following relationships with realistic delegation chains. Fixed signal handlers and Following model bugs. Added 16 new tests. Includes Railway cron job documentation.

---

## 2025-01-06 - Add Follow/Unfollow UI with Tag Selection

**Change**: docs/changes/0005_CHANGE-follow-unfollow-ui-with-tags.md  
**Commit**: 5b0dfa1  
**Summary**: Implemented community-specific follow/unfollow functionality with tag selection. Users can follow members within a community and specify which tags to follow them on. Modal dialog displays existing tags as pills with add/remove functionality, shows suggested tags from member's ballot history, and includes "All Tags" checkbox. Merged Following and Actions columns in Members table for cleaner UX. Following relationships are Membership→Membership (community-specific). HTMX handles dynamic table updates via out-of-band swaps without page reloads. JavaScript wrapped in IIFE to prevent variable redeclaration on modal reopening. Fixed tag trimming and modal closure bugs.

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
