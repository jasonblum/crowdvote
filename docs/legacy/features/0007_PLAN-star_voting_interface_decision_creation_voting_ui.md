# Feature 0007: STAR Voting Interface System

## Overview

Build the complete voting interface system that transforms CrowdVote from a social platform into a functional democracy tool. This connects the social foundation from Plan #6 to the existing STAR voting backend from Plan #4, enabling communities to create decisions, vote on them, and see transparent results.

## Context & User Journey

With Plan #6's social foundation complete, users can now discover communities and members. Plan #7 enables the core democratic process:

1. **Community Managers**: Create decisions with multiple choices for their communities
2. **Community Members**: Vote on active decisions using STAR voting (0-5 stars per choice)
3. **Real-Time Results**: See live vote tallies and final STAR voting results
4. **Transparency**: Complete audit trails showing who voted (respecting anonymity preferences)
5. **Democracy in Action**: Transform social connections into actual democratic participation

## Technical Requirements

### 1. Decision Creation Interface

**For Community Managers Only:**
- Create new decisions with title, description, and deadline
- Add multiple choices (minimum 2, maximum 10)
- Set voting deadline (future date/time)
- Preview decision before publishing
- Edit unpublished decisions, lock after first vote

**Decision Creation Form:**
```
Title: [Short descriptive title]
Description: [Detailed explanation of what's being decided]
Voting Deadline: [Date/Time picker]
Choices:
  1. [Choice title] [Choice description] [Remove]
  2. [Choice title] [Choice description] [Remove]
  [+ Add Choice] (up to 10 total)

[Preview] [Save Draft] [Publish Decision]
```

### 2. STAR Voting Interface

**For All Community Members:**
- View active decisions in their communities
- Rate each choice from 0-5 stars with clear UI
- See current vote totals (if not anonymous)
- Submit complete ballot or save draft
- Edit votes until decision closes
- Anonymous voting toggle per decision

**STAR Voting UI:**
```
Decision: What color should we paint the community room?

Your Vote (you can change this anytime before [deadline]):
☆☆☆☆☆ Cathedral Gray - Classic and timeless
★★★☆☆ Aqua Chiffon - Bright and cheerful  
★★★★★ Oceanside - Calming blue-green
☆☆☆☆☆ Custom Color - [Write-in option]

Tags for this decision: [maintenance] [beautification] [community room]
Vote anonymously: [Toggle] (your preference: Anonymous by default)

[Save Draft] [Submit Vote] [View Current Results]
```

### 3. Decision Discovery & Management

**Decision Lists:**
- **Active Decisions**: Currently open for voting
- **Upcoming Decisions**: Published but voting hasn't started
- **Closed Decisions**: Completed with final results
- **Draft Decisions**: Manager-only unpublished decisions

**Decision Status Indicators:**
- 🟢 Active (voting open)
- 🟡 Upcoming (published, voting starts later)  
- 🔴 Closed (voting ended, results final)
- ⚪ Draft (unpublished, manager only)

### 4. Real-Time Results & Transparency

**Live Results Page:**
- Current vote totals by choice (respecting anonymity)
- Participation statistics (X of Y members voted)
- Anonymous voter display (mix of real names + GUIDs)
- Vote submission timeline
- STAR voting progress (score phase)

**Final Results Page:**
- Complete STAR voting results (score + runoff phases)
- Winner announcement with margin
- Full transparency report from existing services
- Delegation inheritance trees (when Plan #8 implemented)
- Downloadable audit data

### 5. Integration with Existing Backend

**Connect to Plan #4 Services:**
- Use existing `StageBallots` service for vote calculation
- Use existing `TallyDecisionSTAR` service for results
- Leverage existing `Result` model for storage
- Connect to `AnonymousVoteMapping` for privacy

**Models Already Available:**
- ✅ Decision, Choice, Ballot, Vote models exist
- ✅ STAR voting calculation services work
- ✅ Anonymous voting architecture ready
- ✅ Community management foundation complete

## Implementation Phases

### Phase 1: Decision Creation (Managers)
- Decision creation form with validation
- Choice management (add/remove/edit)
- Draft/publish workflow
- Decision list views for managers
- Basic edit capabilities (before votes cast)

### Phase 2: STAR Voting Interface (Members)  
- Decision discovery page for members
- STAR voting form (0-5 stars per choice)
- Vote submission and validation
- Draft vote saving functionality
- Vote editing (before decision closes)

### Phase 3: Results & Transparency (Everyone)
- Live results page with current totals
- Final results with complete STAR analysis
- Anonymous voter display system
- Participation tracking and statistics
- Integration with existing calculation services

### Phase 4: Enhanced Features (Polish)
- Decision search and filtering
- Email notifications for new decisions
- Voting deadline reminders
- Mobile-optimized voting interface
- Performance optimization for large communities

## User Stories

### Community Manager Stories
1. **As a community manager**, I want to create decisions with multiple choices so members can vote on community issues
2. **As a community manager**, I want to set voting deadlines so decisions don't remain open indefinitely
3. **As a community manager**, I want to preview decisions before publishing so I can ensure they're clear and complete
4. **As a community manager**, I want to see who has voted so I can follow up with non-participants
5. **As a community manager**, I want to edit decisions before votes are cast so I can fix errors

### Community Member Stories
6. **As a community member**, I want to see all active decisions in my communities so I can participate in democracy
7. **As a community member**, I want to rate choices from 0-5 stars so I can express my preferences clearly
8. **As a community member**, I want to vote anonymously when desired so I can express unpopular opinions safely
9. **As a community member**, I want to change my vote before the deadline so I can reconsider my choices
10. **As a community member**, I want to see current results so I understand how the community is leaning

### Transparency Stories
11. **As anyone**, I want to see final STAR voting results so I can understand how decisions were made
12. **As anyone**, I want to verify vote counts so I can trust the democratic process
13. **As anyone**, I want to see participation rates so I can understand community engagement
14. **As anyone**, I want audit trails so I can verify the integrity of elections

## Files to Create/Modify

### New Templates
- `democracy/templates/democracy/decision_list.html` - List all decisions by status
- `democracy/templates/democracy/decision_create.html` - Create new decision form
- `democracy/templates/democracy/decision_detail.html` - View decision details and vote
- `democracy/templates/democracy/decision_vote.html` - STAR voting interface
- `democracy/templates/democracy/decision_results.html` - Results and transparency page
- `democracy/templates/democracy/decision_manage.html` - Manager decision overview

### New Views
- `democracy/views.py` - Add decision CRUD operations and voting views
- `democracy/forms.py` - Create decision creation and voting forms
- `democracy/utils.py` - Helper functions for vote validation and display

### Enhanced Files
- `democracy/urls.py` - Add decision and voting URL patterns
- `democracy/models.py` - Add any needed fields or methods
- `democracy/admin.py` - Enhance admin for decision management
- `accounts/templates/accounts/dashboard.html` - Add active decisions section

### New Migrations
- `democracy/migrations/0008_decision_voting_enhancements.py` - Any model updates needed

## Integration Points

### HTMX Enhanced Interactions
- Real-time vote submission without page reload
- Dynamic choice adding/removing in creation form
- Live results updates during voting period
- Star rating interactive UI with immediate feedback

### Existing Services Integration
```python
# Use existing STAR voting services
from democracy.services import StageBallots, TallyDecisionSTAR

# Calculate votes (integrates with delegation when Plan #8 ready)  
stage_service = StageBallots()
stage_service.execute({'decision': decision})

# Calculate STAR results
tally_service = TallyDecisionSTAR()
results = tally_service.execute({'decision': decision})
```

### Anonymous Voting System
```python
# Use existing anonymous mapping
from democracy.models import AnonymousVoteMapping

# Display voter names (real or anonymous GUIDs)
display_name = AnonymousVoteMapping.get_display_name(decision, voter)
```

## Security & Validation

### Voting Security
- Only community members can vote on community decisions
- One vote per user per decision (ballot uniqueness)
- Votes locked after decision deadline
- CSRF protection on all voting forms
- Star rating validation (0-5 integers only)

### Manager Permissions
- Only community managers can create decisions
- Managers cannot edit decisions after first vote cast
- Managers cannot see individual anonymous votes
- Managers can view participation statistics only

### Data Integrity
- Vote submission validation with error handling
- Decision deadline enforcement
- Choice validation (2-10 choices required)
- Ballot completeness checking (all choices rated)

## Success Criteria

### Functional Requirements
- Community managers can create multi-choice decisions with deadlines
- Community members can vote using STAR system (0-5 stars per choice)
- STAR voting results calculated correctly using existing services
- Anonymous voting works with proper GUID mapping
- Real-time results display with live updates

### User Experience Requirements
- Intuitive decision creation workflow for managers
- Clear, mobile-friendly voting interface for members
- Transparent results pages showing complete STAR analysis
- Seamless integration with existing community management system
- Proper error handling and user feedback throughout

### Technical Requirements
- Zero linting errors and Django best practices
- HTMX integration for smooth real-time interactions
- Responsive design working on all device sizes
- Performance optimized for communities with 100+ members
- Integration with existing Plan #4 voting services

## Next Phase Integration

Plan #7 creates the foundation for Plan #8 (Delegation Management):
- **Decision Tagging**: Decisions can be tagged with topics for delegation
- **Vote Inheritance**: Framework ready for delegation-based vote calculation
- **Trust Networks**: Social connections from Plan #6 connect to voting from Plan #7
- **Transparency**: Results pages ready to show delegation trees and influence flows

This transforms CrowdVote from a social platform into a working democracy where:
1. **Managers create decisions** → Communities have real issues to vote on
2. **Members vote with STAR system** → Democratic participation happens
3. **Results show transparency** → Trust in the process is maintained
4. **Ready for delegation** → Plan #8 can add vote inheritance seamlessly

**Plan #7 is the bridge between social infrastructure and democratic action.**
