# Django CrowdVote Project Setup and Railway Deployment Plan

## Brief Description

This plan outlines the complete process for creating a Django project called "crowdvote" from scratch, setting up local development environment, pushing to GitHub, and deploying to Railway. The plan addresses the virtual environment vs Docker question and provides a clear roadmap following Railway's official Django guide and best practices.

## Why Virtual Environment First, Then Docker?

**Answer to your excellent question:** Both guides start with virtual environments rather than Docker because:

1. **Development Workflow**: Most Django developers work locally with virtual environments for faster iteration, debugging, and IDE integration
2. **Dependency Management**: Virtual environments help you generate clean `requirements.txt` files with only the packages you actually need
3. **Railway's Approach**: Railway's build process uses the `requirements.txt` file to install dependencies in their containers, so you need a clean dependency list first
4. **Docker for Production**: Docker comes later as the deployment/production container format, not the development environment
5. **Hybrid Approach**: You develop locally with venv, then Docker wraps it for consistent deployment

Think of it as: **Virtual Env for Development → Docker for Deployment**

## Phase 1: Local Development Setup

### 1.1 Project Initialization
- Create project directory structure
- Initialize Git repository
- Set up Python virtual environment using `python3 -m venv venv`
- Activate virtual environment with `source venv/bin/activate`

### 1.2 Django Project Creation
- Install Django 5.x in virtual environment
- Create Django project using `django-admin startproject crowdvote`
- Verify initial setup with `python manage.py runserver`

### 1.3 Production Dependencies Installation
Install `uv` for fast package management, then install required packages for Railway deployment:
- Install `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or via Homebrew: `brew install uv`)
- `gunicorn` - Production WSGI server
- `whitenoise` - Static file serving
- `psycopg[binary,pool]` - PostgreSQL adapter
- `django-environ` - Environment variable management

### 1.4 Database Configuration
- Configure PostgreSQL settings using environment variables
- Set up local PostgreSQL database named `crowdvote_dev`
- Update `settings.py` with database configuration using `os.environ`
- Run initial migrations with `python manage.py migrate`

### 1.5 Static Files and Middleware Setup
- Configure WhiteNoise middleware for static file serving
- Set up static files configuration (`STATIC_URL`, `STATIC_ROOT`, `STATICFILES_DIRS`)
- Create `static/` directory in project root
- Update `ALLOWED_HOSTS` for Railway deployment

### 1.6 Requirements and Configuration Files
- Generate `requirements.txt` with `uv pip freeze > requirements.txt`
- Create `.env.example` file with required environment variables
- Create `.gitignore` file for Python/Django projects
- Document environment variables needed for deployment

## Phase 2: GitHub Repository Setup

### 2.1 Repository Creation
- Create new GitHub repository named "crowdvote"
- Push local code to GitHub repository
- Ensure all necessary files are tracked (requirements.txt, manage.py, etc.)
- Verify repository structure matches Railway expectations

### 2.2 Documentation Updates
- Update README.md with setup instructions
- Include Railway deployment badge
- Document environment variables and setup steps

## Phase 3: Railway Deployment Configuration

### 3.1 Railway Project Setup
- Create new Railway project
- Connect GitHub repository to Railway
- Configure automatic deployments from main branch

### 3.2 Environment Variables Configuration
Required Railway environment variables:
- `PGDATABASE` → `${{Postgres.PGDATABASE}}`
- `PGUSER` → `${{Postgres.PGUSER}}`
- `PGPASSWORD` → `${{Postgres.PGPASSWORD}}`
- `PGHOST` → `${{Postgres.PGHOST}}`
- `PGPORT` → `${{Postgres.PGPORT}}`
- `SECRET_KEY` → Generate secure Django secret key
- `DEBUG` → `False`
- `ALLOWED_HOSTS` → `.railway.app` or custom domain

### 3.3 Database Service
- Add PostgreSQL database service to Railway project
- Connect database service to Django app service
- Verify database connectivity and run migrations

### 3.4 Dockerfile for Railway
Create production Dockerfile:
- Use `python:3.11-slim` base image
- Install `uv` for fast dependency installation
- Install dependencies from requirements.txt using `uv pip install`
- Copy application code
- Run `collectstatic` for static files
- Expose port 8000
- Use gunicorn as WSGI server

### 3.5 Deployment and Verification
- Deploy application to Railway
- Verify logs show successful startup
- Generate public domain for application
- Test application accessibility
- Run database migrations in production

## Phase 4: Post-Deployment Setup

### 4.1 Production Verification
- Run Django's deployment checklist: `python manage.py check --deploy`
- Verify static files are served correctly
- Test database connectivity
- Create superuser account in production

### 4.2 Monitoring and Maintenance
- Set up Railway logging monitoring
- Configure domain and SSL if needed
- Document deployment process and troubleshooting

## Key Files to Create/Modify

### New Files
- `requirements.txt` - Python dependencies
- `Dockerfile` - Production container configuration
- `.env.example` - Environment variable template
- `.gitignore` - Git ignore patterns
- `docs/deployment.md` - Deployment documentation

### Modified Files
- `crowdvote/settings.py` - Database, static files, security configuration
- `crowdvote/wsgi.py` - Production WSGI configuration (if needed)
- `README.md` - Updated with deployment instructions

## Dependencies Required

### Core Dependencies
```
Django>=5.0,<6.0
gunicorn>=21.0
whitenoise>=6.0
psycopg[binary,pool]>=3.1
django-environ>=0.10
```

**Note**: Install these using `uv` commands:
- `uv pip install django>=5.0,<6.0`
- `uv pip install gunicorn>=21.0`
- `uv pip install whitenoise>=6.0`
- `uv pip install psycopg[binary,pool]>=3.1`
- `uv pip install django-environ>=0.10`

### Future CrowdVote-Specific Dependencies
(For later implementation phases)
```
django-allauth>=0.54
django-service-objects>=0.7
django-taggit>=4.0
django-extensions>=3.2
django-debug-toolbar>=4.0
```

## Expected Project Structure After Setup

```
crowdvote/
├── crowdvote/              # Django project directory
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py         # Main configuration
│   ├── urls.py
│   └── wsgi.py
├── static/                 # Static files directory
├── requirements.txt        # Python dependencies
├── Dockerfile             # Production container
├── .env.example           # Environment template
├── .gitignore            # Git ignore patterns
├── manage.py             # Django management script
├── README.md             # Project documentation
└── docs/                 # Additional documentation
    └── deployment.md
```

## Critical Success Criteria

1. **Local Development**: Django app runs locally with PostgreSQL
2. **GitHub Integration**: Code successfully pushed and tracked
3. **Railway Deployment**: App deploys and runs on Railway
4. **Database Connectivity**: PostgreSQL service connected and migrations run
5. **Static Files**: Static files served correctly via WhiteNoise
6. **Security**: Production security settings enabled
7. **Documentation**: Clear setup and deployment instructions

## Next Steps After Deployment

Once basic deployment is working:
1. Implement Django apps for CrowdVote features (communities, voting, delegation)
2. Add Tailwind CSS for styling
3. Implement HTMX for progressive enhancement
4. Set up comprehensive testing suite
5. Add monitoring and logging
6. Implement the STAR voting and delegation features

This plan provides a solid foundation for the CrowdVote Django application with a clear path from development to production deployment on Railway.


