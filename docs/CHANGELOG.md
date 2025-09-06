# CrowdVote Development Changelog

This file documents the development history of the CrowdVote project, capturing key milestones, decisions, and progress made during development sessions.

## 2025-01-06 - CrowdVote Core Models & Django Apps (Plan #3)

### Session Overview
Built the foundational CrowdVote architecture with three Django apps (`accounts`, `democracy`, and `shared`), implemented all core models for STAR voting and delegative democracy, registered comprehensive Django admin interfaces, and generated realistic dummy data with multi-level delegation chains.

### Accomplished
- **Three-App Architecture**: Clean separation of concerns with shared utilities
  - `shared/` app with `BaseModel` providing UUID primary keys and timestamps
  - `accounts/` app for user management and following relationships
  - `democracy/` app for community decision-making and voting
- **Complete Model Implementation**: All 8 core models for CrowdVote functionality
  - `CustomUser` extending `AbstractUser` for future-proofing
  - `Following` for user-to-user delegation relationships
  - `Community` with multi-community support and rich descriptions
  - `Membership` through-model with voting rights and management permissions
  - `Decision` (renamed from "Referendum") for community questions
  - `Choice` for decision options with STAR voting score tracking
  - `Ballot` for complete user votes (manual or calculated)
  - `Vote` for individual star ratings (0-5) on each choice
  - `Result` for flexible results storage with JSONField
- **Comprehensive Django Admin**: Full admin interfaces for all models
  - List displays, filters, search functionality for all models
  - Inline editing for related models (Choices in Decisions, Votes in Ballots)
  - Raw ID fields for performance with large datasets
  - Proper admin organization and user experience
- **Database Architecture**: UUID-based security and scalability
  - All migrations created and applied successfully
  - Fresh database setup with CustomUser from the start
  - UUID primary keys throughout for security
  - Proper foreign key relationships with `PROTECT` constraints
- **Realistic Test Data**: Rich dummy data for development and testing
  - 2 themed communities: "Minion Collective" and "Springfield Town Council"
  - 370 total users with realistic names and profiles
  - 204 following relationships creating multi-level delegation chains
  - Proper membership distribution (80% voters, 20% lobbyists, 10% managers)
  - Cross-community following relationships for complex scenarios

### Key Decisions Made
1. **Three-App Structure**: `accounts`, `democracy`, and `shared` for clean separation
2. **CustomUser from Start**: Avoided future migration headaches by implementing immediately
3. **BaseModel Pattern**: Shared abstract model for consistent UUIDs and timestamps
4. **Terminology**: "Decision" instead of "Referendum" for better user experience
5. **Admin-First Approach**: Built comprehensive admin to validate models before frontend
6. **UUID Primary Keys**: Enhanced security and future scalability
7. **Tag System Deferral**: Temporarily removed django-taggit due to UUID compatibility issues

### Technical Challenges Resolved
1. **CustomUser Migration**: Resolved database conflicts by dropping and recreating database
2. **Django-Taggit UUID Incompatibility**: Discovered and worked around tagging system limitations
3. **Docker Container Dependencies**: Rebuilt containers with updated requirements.txt
4. **Migration Dependencies**: Properly sequenced migrations across three new apps
5. **Data Generation Complexity**: Created sophisticated dummy data with realistic delegation patterns

### Files Created/Modified
- **Created**: `docs/features/0003_PLAN.md` - Technical plan for this session
- **Created**: Complete `shared/` app with `BaseModel`
- **Created**: Complete `accounts/` app with `CustomUser` and `Following` models
- **Created**: Complete `democracy/` app with 6 core voting models
- **Created**: `democracy/management/commands/generate_dummy_data.py` - Data generation
- **Created**: Comprehensive admin interfaces for all models
- **Created**: Initial migrations for all three apps
- **Modified**: `crowdvote/settings.py` - Added new apps and `AUTH_USER_MODEL`
- **Modified**: `requirements.txt` - Added `django-taggit==6.1.0`

### Model Architecture Summary
```
BaseModel (Abstract)
├── UUID primary key
├── created/modified timestamps
└── Used by all CrowdVote models

CustomUser (extends AbstractUser)
└── Future-proofed user model

Following (extends BaseModel)
├── follower → CustomUser
├── followee → CustomUser
└── [Tags deferred for UUID compatibility]

Community (extends BaseModel)
├── name, description
└── members → ManyToMany through Membership

Membership (extends BaseModel)
├── member → CustomUser
├── community → Community
├── voting/management permissions
└── anonymity preferences

Decision (extends BaseModel)
├── title, description, dt_close
├── community → Community
└── results_need_updating flag

Choice (extends BaseModel)
├── title, description
├── decision → Decision
└── score/runoff_score fields

Ballot (extends BaseModel)
├── decision → Decision
├── voter → CustomUser
├── is_calculated/is_anonymous flags
└── [Tags deferred for UUID compatibility]

Vote (extends BaseModel)
├── choice → Choice
├── ballot → Ballot
└── stars (0-5 with validation)

Result (extends BaseModel)
├── decision → Decision
├── report (text)
└── stats (JSONField)
```

### Development Workflow Insights
- **UUID Benefits**: Enhanced security but requires careful third-party package compatibility
- **Admin Interface Value**: Comprehensive admin enables rapid model validation and testing
- **Data Generation Strategy**: AI-generated realistic data more efficient than factory_boy
- **Docker Development**: Container rebuilds necessary when adding new dependencies
- **Migration Strategy**: Clean database recreation better than complex migration fixes

### Technical Stack Status
- **Local Development**: Docker Compose with PostgreSQL - `http://localhost:8000` ✅
- **Django Admin**: Full admin interface - `http://localhost:8000/admin/` (admin/admin123) ✅
- **Database**: PostgreSQL with 370 users, 2 communities, 204 following relationships ✅
- **Models**: All 8 core models implemented and tested ✅
- **Migrations**: All migrations applied successfully ✅

### Next Steps
- Implement STAR voting calculation services (from old code in `/resources`)
- Build ballot inheritance algorithm for delegative democracy
- Create UUID-compatible tagging solution for topic-based following
- Develop frontend voting interfaces
- Add comprehensive test suite
- Implement API endpoints for transparency and auditability

### Development Notes
- Tag system temporarily deferred with clear TODOs for future implementation
- All models use `on_delete=models.PROTECT` to prevent accidental data loss
- Dummy data includes realistic delegation chains for testing complex scenarios
- Admin interface provides full CRUD operations for all models
- UUID primary keys throughout enhance security and prepare for distributed systems

---

## 2025-01-05 - Docker Development Environment, Railway Deployment, and Custom Landing Page (Plan #2)

### Session Overview
Implemented complete development-to-production workflow with Docker containerization, successful Railway deployment, and custom landing page replacing Django's default welcome page.

### Accomplished
- **Docker Development Environment**: Full containerization with hot-reloading
  - `docker-compose.yml` with web and PostgreSQL services
  - `Dockerfile.dev` for development with UV package manager
  - `.dockerignore` for optimized build context
  - Local development accessible at `http://localhost:8000`
- **Railway Production Deployment**: Live production environment
  - Resolved Railpack auto-detection conflicts with legacy files
  - Fixed SECRET_KEY security issue (avoid `#` characters in Railway environment variables)
  - Fixed Dockerfile curl dependency for UV installation in slim Python images
  - Successful deployment to `https://crowdvote-production.up.railway.app`
- **Custom Landing Page**: Professional CrowdVote branding
  - Django templates directory structure (`base.html`, `home.html`)
  - Home view and URL routing for root path
  - Responsive design showcasing key features and project vision
  - Proper template configuration in Django settings

### Key Decisions Made
1. **Development Approach**: Docker containers for both local development and production consistency
2. **Railway Branch Strategy**: Use `main` branch instead of legacy `master` for clean deployment
3. **Environment Variables**: Railway-safe secret keys without special characters (`#`, `@`, etc.)
4. **Template Organization**: Project-level templates directory (future consideration for `shared` app)
5. **Dockerfile Optimization**: Install system dependencies (curl) for UV package manager in slim images

### Technical Challenges Resolved
1. **Railway Auto-Detection**: Cleaned up legacy Django files that confused Railway's buildpack detection
2. **Secret Key Security**: Generated Railway-compatible secret keys avoiding comment characters
3. **Container Dependencies**: Added curl installation to production Dockerfile for UV setup
4. **Template Configuration**: Properly configured Django TEMPLATES setting for custom template directory

### Files Created/Modified
- **Created**: `docker-compose.yml`, `Dockerfile.dev`, `.dockerignore`
- **Created**: `docs/features/0002_PLAN.md` - Technical plan for this session
- **Created**: `crowdvote/templates/base.html`, `crowdvote/templates/home.html`
- **Created**: `crowdvote/views.py` with home view
- **Modified**: `crowdvote/urls.py` - Added root URL routing
- **Modified**: `crowdvote/settings.py` - Template directory configuration
- **Modified**: `Dockerfile` - Added curl installation for production builds
- **Cleanup**: Removed legacy Django files from `/resources` directory

### Development Workflow Insights
- **Docker vs Virtual Environment**: Use virtual env for dependency management, Docker for deployment consistency
- **Railway Environment Variables**: Special characters in secrets can cause truncation issues
- **Dockerfile Layer Optimization**: Install system dependencies before application dependencies
- **Git Branch Strategy**: Clean `main` branch deployment avoids legacy configuration conflicts

### Technical Stack Status
- **Local Development**: Docker Compose with PostgreSQL - `http://localhost:8000` ✅
- **Production**: Railway with managed PostgreSQL - `https://crowdvote-production.up.railway.app` ✅
- **Landing Page**: Custom CrowdVote welcome page with feature overview ✅
- **Database**: PostgreSQL 14 (local) + Railway managed (production) ✅
- **Static Files**: WhiteNoise configuration working in both environments ✅

### Next Steps
- Implement CrowdVote core features (voting, delegation, communities)
- Add Tailwind CSS for enhanced styling
- Implement HTMX for progressive enhancement
- Create Django apps for specific features (voting, communities, users)
- Consider `shared` app for common templates and utilities

### Development Notes
- Railway auto-deploys on GitHub push to `main` branch
- Docker hot-reloading works for local template development
- UV package manager significantly faster than pip for dependency installation
- Both local and production environments now serve identical custom landing page

---

## 2025-01-05 - Initial Django Project Setup (Plan #1)

### Session Overview
Complete Django project initialization with PostgreSQL, production dependencies, and Railway deployment preparation.

### Accomplished
- **Project Foundation**: Created Django 5.2.6 project with Python 3.11.13
- **Database Setup**: Installed and configured PostgreSQL 14 with `crowdvote_dev` database
- **Production Dependencies**: Installed using `uv` package manager:
  - `gunicorn 23.0.0` - Production WSGI server
  - `whitenoise 6.9.0` - Static file serving
  - `psycopg 3.2.9` - PostgreSQL adapter
  - `django-environ 0.12.0` - Environment variable management
- **Configuration**: Updated Django settings for Railway deployment compatibility
- **Static Files**: Configured WhiteNoise middleware and static file collection
- **Environment Management**: Created `.env.local` template following workplace conventions

### Key Decisions Made
1. **Python Version**: Upgraded to Python 3.11.13 for Django 5.x compatibility
2. **Package Manager**: Adopted `uv` instead of `pip` for faster dependency management
3. **Database**: PostgreSQL for both local development and production consistency
4. **Deployment Target**: Railway platform with automated GitHub integration
5. **Environment Files**: Used `.env.local` convention instead of `.env.example`

### Files Created/Modified
- **Created**: Django project structure (`crowdvote/`, `manage.py`)
- **Created**: `requirements.txt` with production dependencies
- **Created**: `.gitignore` for Python/Django projects
- **Created**: `.env.local` environment template
- **Created**: `static/` and `staticfiles/` directories
- **Modified**: `crowdvote/settings.py` for PostgreSQL and Railway configuration
- **Modified**: `AGENTS.md`, `README.md`, `resources/plan_feature.md` with CHANGELOG directive

### Technical Details
- **Django Version**: 5.2.6
- **Python Version**: 3.11.13
- **Database**: PostgreSQL 14.19 (`crowdvote_dev`)
- **Package Manager**: uv (faster than pip)
- **Static Files**: 127 files collected successfully
- **Migrations**: All Django core migrations applied

### Next Steps
- **Phase 2**: GitHub repository setup and initial commit
- **Phase 3**: Railway deployment configuration
- **Phase 4**: Production deployment and verification

### Development Notes
- PostgreSQL service running locally via Homebrew
- Virtual environment activated and configured
- All Django system checks passing
- Ready for version control and deployment pipeline

---

*This changelog should be updated after each significant development session to maintain project history and context for future development work.*
