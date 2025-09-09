# Plan #3: CrowdVote Core Models & Django Apps

## Brief Description

Build the foundational CrowdVote architecture with three Django apps (`accounts`, `democracy`, and `shared`), implement all core models based on the previous design, register everything in Django admin, and generate realistic dummy data to test the tag-based following system and multi-level delegation chains.

## Phase 1: Project Setup & Dependencies

### Files to Create/Modify

**New Dependencies:**
- Add `django-taggit` to `requirements.txt`
- Install via `uv pip install django-taggit`

**Settings Updates:**
- Add `'taggit'` to `INSTALLED_APPS`
- Add new apps `'accounts'`, `'democracy'`, and `'shared'` to `INSTALLED_APPS`

## Phase 2: Shared App Infrastructure

### Files to Create

**Shared App Structure:**
- `shared/__init__.py`
- `shared/apps.py`
- `shared/models.py` - BaseModel with common fields
- `shared/migrations/`

**BaseModel Implementation:**
```python
# shared/models.py
import uuid
from django.db import models

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
```

## Phase 3: Accounts App

### Files to Create

**App Structure:**
- `accounts/__init__.py`
- `accounts/apps.py`
- `accounts/models.py`
- `accounts/admin.py`
- `accounts/migrations/`

**Models to Implement:**

1. **CustomUser** (extends AbstractUser)
   - Basic user model with ordering by username
   - Verbose names for admin
   - Future-proofing for when we need custom user fields

2. **Following** (extends BaseModel from shared)
   - `follower` → CustomUser (related_name="followings")
   - `followee` → CustomUser (related_name="followers") 
   - `tags` → TaggableManager for topic-specific following
   - Proper ordering and help text

**Admin Registration:**
- CustomUser with search, filters, list display
- Following with inline editing, tag filters

## Phase 4: Democracy App

### Files to Create

**App Structure:**
- `democracy/__init__.py`
- `democracy/apps.py` 
- `democracy/models.py`
- `democracy/admin.py`
- `democracy/migrations/`

**Models to Implement:**

1. **Community** (extends BaseModel from shared)
   - `name`, `description`
   - `members` → ManyToMany through Membership

2. **Membership** (extends BaseModel from shared) 
   - `member` → CustomUser
   - `community` → Community
   - `is_anonymous_by_default`, `is_community_manager`, `is_voting_community_member`
   - `dt_joined` auto timestamp

3. **Decision** (extends BaseModel from shared) - *renamed from Referendum*
   - `title`, `description`
   - `dt_close` voting deadline
   - `community` → Community
   - `results_need_updating` flag

4. **Choice** (extends BaseModel from shared)
   - `title`, `description` 
   - `decision` → Decision
   - Score tracking fields (to be calculated later)

5. **UUIDTaggedItem** (for taggit integration)
   - Custom tagged item model for UUID support
   - Extends GenericUUIDTaggedItemBase, TaggedItemBase

6. **Ballot** (extends BaseModel from shared)
   - UUID primary key override
   - `decision` → Decision
   - `voter` → CustomUser
   - `is_calculated` vs manual flag
   - `is_anonymous` flag
   - `tags` → TaggableManager (through UUIDTaggedItem)
   - `comments` text field

7. **Vote** (extends BaseModel from shared)
   - UUID primary key override
   - `choice` → Choice
   - `ballot` → Ballot
   - `stars` (0-5 integer with MinValueValidator, MaxValueValidator)

8. **Result** (extends BaseModel from shared)
   - `decision` → Decision
   - `report` text field
   - `stats` JSONField for flexible data storage

**Admin Registration:**
- All models with appropriate list displays, filters, search
- Inline editing where appropriate (Choices in Decisions, Votes in Ballots)
- Tag filtering and display

## Phase 5: Database Setup

### Migration Strategy
1. Create initial migrations for all three apps
2. Run migrations to create database schema
3. Verify all relationships work in Django admin

### Files Created:
- `shared/migrations/` (may be empty since BaseModel is abstract)
- `accounts/migrations/0001_initial.py`
- `democracy/migrations/0001_initial.py`

## Phase 6: Dummy Data Generation

### Realistic Test Data Structure

**Communities (2):**
- "Minion Collective" (~100 members)
- "Springfield Town Council" (~100 members)

**User Distribution:**
- Mix of active voters, occasional participants, lurkers
- Realistic usernames and profiles
- Various join dates across communities

**Following Patterns:**
- **Single-level**: 60% of users follow 1-3 others directly
- **Multi-level**: 30% create 2-3 level delegation chains  
- **Complex**: 10% create interesting cross-community patterns

**Tag Diversity:**
- Community-specific tags: "lunch", "budget", "maintenance", "events"
- Cross-cutting tags: "environment", "finance", "social"
- Realistic tag usage patterns (some popular, some niche)

**Following Relationships:**
- Prevent circular references
- Create realistic influence trees
- Mix of topic-specific and general following

### Implementation Approach
- Generate via Django management command
- Use realistic names, dates, and patterns
- Create JSON fixtures for repeatability
- Validate data integrity after generation

## App Structure Summary

```
crowdvote/
├── shared/           # Common utilities, BaseModel, shared templates
│   ├── models.py     # BaseModel
│   └── ...
├── accounts/         # User management and following
│   ├── models.py     # CustomUser, Following
│   ├── admin.py
│   └── ...
└── democracy/        # Community decision-making
    ├── models.py     # Community, Membership, Decision, Choice, Ballot, Vote, Result
    ├── admin.py
    └── ...
```

## Success Criteria

1. **Three Apps Created**: `accounts`, `democracy`, and `shared` apps properly structured
2. **Models Working**: All models created, migrated, and visible in admin
3. **Relationships Functional**: Foreign keys, many-to-many, and tagging working
4. **Admin Interface**: All models registered with good UX (search, filters, inlines)
5. **Dummy Data**: Realistic test data demonstrating complex following patterns
6. **Tag System**: django-taggit integration working for Following and Ballot models
7. **BaseModel**: Shared abstract model working across all apps

## Key Design Decisions

1. **Three-App Architecture**: Clean separation of concerns with shared utilities
2. **CustomUser**: Future-proofing even though not customized initially
3. **BaseModel in Shared**: Common fields and behavior available to all apps
4. **Terminology**: "Decision" instead of "Referendum" for approachability
5. **Tag Integration**: django-taggit for flexible topic-based following
6. **Admin-First**: Build admin interface to validate models before building frontend

## Next Steps After Completion

This foundation will enable:
- Testing complex delegation scenarios in Django admin
- Validating tag-based following logic with real data
- Building the STAR voting calculation services
- Creating the frontend voting interface
- Implementing the ballot inheritance algorithm

The dummy data will reveal edge cases and help refine the delegation logic before building the core voting services.
