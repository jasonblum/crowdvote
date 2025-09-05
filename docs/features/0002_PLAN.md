# Docker Development Environment, Railway Deployment, and Custom Landing Page

## Brief Description

Implement a complete development-to-production workflow for CrowdVote using Docker containers for local development, deploy to Railway for production hosting, and replace the default Django landing page with a custom welcome page. The goal is to enable local development via `http://localhost:8000` in a Docker container and have a live public website accessible through Railway deployment.

## Phase 1: Docker Development Environment Setup

### Files to Create/Modify

**New Files:**
- `docker-compose.yml` - Multi-service container orchestration
- `Dockerfile.dev` - Development-specific container configuration  
- `.dockerignore` - Exclude unnecessary files from Docker context

**Modified Files:**
- `crowdvote/settings.py` - Add Docker-specific database configuration
- `.env.local` - Update with Docker database connection settings

### Docker Configuration Details

**Docker Compose Services:**
1. **Web Service** - Django application container
   - Build from `Dockerfile.dev` 
   - Port mapping: `8000:8000`
   - Volume mount: `.:/app` for hot-reloading
   - Depends on database service

2. **Database Service** - PostgreSQL container
   - Use `postgres:14` official image
   - Environment variables for database credentials
   - Volume mount for data persistence
   - Port mapping: `5432:5432`

**Development Dockerfile Specifications:**
- Base image: `python:3.11-slim`
- Install UV package manager
- Install dependencies from `requirements.txt`
- Set working directory to `/app`
- Expose port 8000
- Command: `python manage.py runserver 0.0.0.0:8000`

## Phase 2: Railway Production Deployment

### Files to Modify

**Railway Configuration:**
- Verify existing `Dockerfile` (production) works with Railway
- Update environment variable configuration in Railway dashboard

**Database Connection Updates:**
- Ensure `crowdvote/settings.py` handles both Docker and Railway database configurations
- Verify Railway PostgreSQL service integration

**Deployment Process:**
1. Push Docker changes to GitHub `main` branch
2. Connect Railway to GitHub repository (if not already connected)
3. Add Railway PostgreSQL database service
4. Configure production environment variables in Railway
5. Deploy and generate public domain
6. Verify deployment at Railway-provided URL

## Phase 3: Custom Landing Page Implementation

### Files to Create/Modify

**New Files:**
- `crowdvote/templates/` - Template directory
- `crowdvote/templates/base.html` - Base template structure
- `crowdvote/templates/home.html` - Welcome page template
- `crowdvote/views.py` - View functions for home page

**Modified Files:**
- `crowdvote/urls.py` - Add URL pattern for home page
- `crowdvote/settings.py` - Update `TEMPLATES` configuration for template directory

### URL and View Implementation

**URL Configuration:**
- Add root URL pattern `path('', views.home, name='home')` to `crowdvote/urls.py`
- Remove or comment out default Django admin URL from root

**View Function:**
- Create `home` function in `crowdvote/views.py`
- Return `render(request, 'home.html')` with basic context

**Template Structure:**
- `base.html` - Basic HTML5 structure with title and content blocks
- `home.html` - Extends base template with "Welcome to CrowdVote" content
- Simple, clean HTML without external dependencies

## Development Workflow Algorithm

### Step-by-Step Process:

1. **Docker Setup:**
   - Create `docker-compose.yml` with web and database services
   - Create `Dockerfile.dev` optimized for development
   - Update database settings to use Docker PostgreSQL container
   - Test local development: `docker-compose up` → `http://localhost:8000`

2. **Railway Deployment:**
   - Commit Docker changes to GitHub
   - Configure Railway project with PostgreSQL service
   - Set production environment variables
   - Deploy and verify public URL accessibility

3. **Landing Page Development:**
   - Create Django templates directory structure
   - Implement home view and URL routing
   - Create basic HTML templates for welcome page
   - Test both locally (Docker) and on Railway

## Database Configuration Strategy

**Environment-Based Settings:**
- Local Docker: Use Docker Compose PostgreSQL service
- Railway Production: Use Railway-managed PostgreSQL service
- Detect environment via `RAILWAY_ENVIRONMENT` or similar environment variable
- Fallback to local Docker settings for development

## Port and URL Conventions

**Local Development:**
- Django app: `http://localhost:8000`
- PostgreSQL: `localhost:5432` (container-to-container communication)

**Production:**
- Railway-generated domain (e.g., `crowdvote-production.up.railway.app`)
- HTTPS enforced by Railway

## Static Files Handling

**Docker Development:**
- Serve static files via Django's development server
- Volume mount for real-time updates

**Railway Production:**
- Use existing WhiteNoise configuration
- Static files collected during Docker build process
