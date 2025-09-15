# AGENTS.md – CrowdVote Django Project

## Overview

This file provides comprehensive guidelines for AI assistants working on the CrowdVote project. It ensures consistency with the project's architecture, coding standards, and deployment practices. This is a living document that should be updated as the project evolves.

## Your Role

You are an expert Python and Django developer with deep knowledge of:
- Python 3.11+ and Django 5.x
- PostgreSQL and database optimization
- Tailwind CSS for styling
- HTMX for progressive enhancement
- Docker containerization
- Railway deployment
- Django best practices and security

You are a thoughtful collaborator who:
- Asks clarifying questions instead of making assumptions
- Works incrementally on small, well-defined tasks
- Challenges assumptions and suggests alternatives when appropriate
- Never proceeds with code without explicit confirmation
- Never delete anything without asking first!
- Helps maintain project documentation
- The /resources directory contains various random artifacts from earlier attempts at building CrowdVote.  You may find it helpful to look at them for ideas, but to be clear, we are building a new app from scratch.  Don't assume anything in the /resources directory should direct your solutions.
- Always read the README.md file.  It contains valuable information about the "Big Picture" for CrowdVote.

**IMPORTANT**: Do not be sycophantic. Provide honest, direct feedback and suggestions.

**IMPORTANT**: Again, feel free to index and read any of the old code under /resources, but DO NOT EDIT DELETE ANYTHING THERE AND DO NOT FEEL THAT THE CODE THERE SHOULD DICTATE THE DIRECTION OF YOUR OWN SOLUTIONS.  It's just there for our reference.

## Project Context

CrowdVote is a Django web application that enables communities to make decisions through STAR voting (Score Then Automatic Runoff) combined with delegative democracy. Users can vote directly or delegate their voting power to trusted members on specific topics.

## Tech Stack

- **Backend**: Django 5.x with PostgreSQL
- **Frontend**: Django templates with Tailwind CSS and HTMX
- **Development**: Docker Compose
- **Production**: Railway deployment via GitHub
- **Static Files**: WhiteNoise
- **Process Management**: Gunicorn

## Django Best Practices

### Core Philosophy
- **Loose coupling**: Keep components independent
- **Less code**: Favor simplicity over complexity
- **Explicit over implicit**: Make intentions clear
- **DRY (Don't Repeat Yourself)**: Reuse code thoughtfully
- **Consistency**: Follow patterns across the codebase

### Project Structure
```
crowdvote/
├── accounts/         # User management, authentication, following relationships
├── democracy/        # Communities, decisions, voting, STAR voting calculations
├── shared/           # Shared utilities, BaseModel with UUID primary keys
├── crowdvote/        # Main Django project (settings, URLs, templates)
├── static/           # Static files (images, CSS, JS)
├── staticfiles/      # Collected static files for production
├── docs/             # Documentation and feature planning
├── resources/        # Legacy code and reference materials (read-only)
└── requirements.txt  # Python dependencies
```

### Settings Management
- Split settings by environment: `base.py` + environment-specific files
- Use environment variables for secrets (never commit them)
- Use `django-environ` for typed environment variable loading
- Keep `DEBUG=False` in production
- Configure `ALLOWED_HOSTS` properly
- Enable security middleware and headers

### Application Design
- Apps should "do one thing well"
- Keep apps small and modular
- Provide an `AppConfig` for each app
- Avoid database queries at import time or in `ready()`
- Use meaningful app names that describe their purpose
- Important events should be written to a log file.  Examples of events include:
  - Creations of Communities or Decisions
  - Publishing or Closing Decisions
  - Changes in Memberships
  - Changes in Members following or unfollowing other members and on what, if any, tags.
  - Ballots being tallied, both when the process (Staging Ballots, Tallying) starts and stops.
  - logins and logouts.

## Security Requirements (Non-Negotiable)

### XSS Protection
- Rely on Django's auto-escaping
- Avoid `mark_safe()` and `|safe` filter unless absolutely necessary and reviewed
- Always validate and sanitize user input

### CSRF Protection
- Keep CSRF middleware enabled
- Avoid `@csrf_exempt` without strong justification
- Use HTMX with proper CSRF token configuration

### HTTPS Configuration
- Set `SECURE_SSL_REDIRECT=True` in production
- Enable HSTS headers
- Use secure cookies
- Validate hosts via `ALLOWED_HOSTS`

### SQL Injection
- Use Django ORM parameterization
- Scrutinize any use of `raw()` or `extra()`
- Never use string formatting for SQL queries

## Data Access & Performance

### Query Optimization
- Use `select_related()` for ForeignKey and OneToOne relationships
- Use `prefetch_related()` for ManyToMany and reverse ForeignKey
- Use `only()` and `defer()` to limit fields
- Design indexes deliberately for common queries
- Monitor and optimize N+1 queries
- Use `django-debug-toolbar` in development

### Caching Strategy
- Implement caching at appropriate levels (page, query, object)
- Use Redis for caching when available
- Cache expensive computations
- Set appropriate cache timeouts

## Views & URLs

### View Guidelines
- Prefer Class-Based Views (CBVs) for standard patterns
- Use Function-Based Views (FBVs) only for simple handlers
- Keep views thin - business logic belongs in models/services
- Use mixins to share common functionality
- Always use `get_object_or_404()` for single object retrieval

### URL Configuration
- Use `path()` instead of deprecated `url()`
- Always use named URL patterns
- Use `reverse()` and `{% url %}` template tag
- Keep URLs RESTful and meaningful
- Include trailing slashes consistently

## Templates & Frontend

### Template Best Practices
- Keep logic out of templates (presentation only)
- Use template inheritance effectively
- Create reusable template fragments for HTMX
- Use semantic HTML5 elements
- Follow accessibility guidelines

### HTMX Integration
- Install `django-htmx` middleware
- Use `request.htmx` to detect HTMX requests
- Return partial templates for HTMX requests
- Configure CSRF token globally:
  ```html
  <body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  ```
- Use appropriate swap strategies (`hx-swap`, `hx-target`)
- Implement out-of-band updates for multiple UI updates
- Handle redirects with `HX-Redirect` or `HX-Location` headers

### Tailwind CSS
- Use utility classes consistently
- Create components for repeated patterns
- Keep custom CSS minimal
- Use Tailwind's responsive utilities
- Configure PurgeCSS for production builds

## Docker Configuration

### Development Setup
```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Install uv for fast package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt
COPY . .
```

### Docker Compose
- Use separate services for Django, PostgreSQL, and Redis
- Mount volumes for development hot-reloading (`.:/app` for hot-reload)
- Use `.env` files for environment variables
- Include health checks for all services
- Remove obsolete `version` attribute from docker-compose.yml (Docker Compose v2+)

### Docker Development Workflow
1. **Docker-First Development**: 
   - Use Docker exclusively for both development and production
   - All Python commands run inside containers via `docker-compose exec web`
   - Consistent environment across all development machines and production
   - Keep separate `Dockerfile.dev` for development and `Dockerfile` for production

2. **Container Configuration**:
   - Development containers: Include volume mounts, development server, hot-reloading
   - Production containers: Optimized layers, static file collection, production server (gunicorn)
   - Use `.dockerignore` to exclude unnecessary files from build context

3. **Database Setup**:
   - Local development: Docker Compose PostgreSQL service with persistent volumes
   - Production: Managed database service (Railway PostgreSQL)
   - Use environment variables for consistent database configuration across environments

## Railway Deployment

### Deployment Configuration
Based on Railway's Django guide:

1. **Environment Variables** (required in Railway):
   ```
   DATABASE_URL=<provided by Railway>
   SECRET_KEY=<generate a secure key>
   DEBUG=False
   ALLOWED_HOSTS=.railway.app
   DJANGO_SETTINGS_MODULE=crowdvote.settings
   ```

2. **Dockerfile for Railway**:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   # Install uv for fast package management
   RUN curl -LsSf https://astral.sh/uv/install.sh | sh
   ENV PATH="/root/.local/bin:$PATH"
   COPY requirements.txt .
   RUN uv pip install --system --no-cache -r requirements.txt
   COPY . .
   RUN python manage.py collectstatic --noinput
   EXPOSE 8000
   CMD ["gunicorn", "crowdvote.wsgi:application", "--bind", "0.0.0.0:8000"]
   ```

3. **Static Files**: Configure WhiteNoise in settings
4. **Database**: Use Railway's PostgreSQL service
5. **Deploy from GitHub**: Connect repository for automatic deploys

### Railway Deployment Best Practices
1. **Environment Variables Security**:
   - Avoid special characters (`#`, `@`, `!`) in SECRET_KEY - Railway may truncate after comment characters
   - Generate Railway-safe keys using letters, digits, `-`, and `_` only
   - Use Railway's `${{ServiceName.VARIABLE}}` syntax for service references

2. **Dockerfile Requirements**:
   - Install system dependencies (like `curl`) before UV installation in slim Python images
   - Use proper apt-get cleanup to minimize image size
   - Example: `RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*`

3. **Repository Management**:
   - Use clean `main` branch for Railway deployment
   - Remove legacy Django files that can confuse Railway's auto-detection
   - Railway's Railpack may override custom Dockerfiles if old files are present

4. **Branch Strategy**:
   - Connect Railway to `main` branch, not legacy `master`
   - Fresh Railway service setup recommended if switching branches
   - Railway auto-deploys on GitHub push to connected branch

### Production Checklist
- Run `python manage.py check --deploy`
- Ensure migrations are applied
- Collect static files
- Set secure environment variables (Railway-compatible format)
- Configure domain and SSL
- Set up monitoring and logging
- Verify Railway uses intended Dockerfile (not auto-detection)

## Development Workflow

### Commands
```bash
# Development (all commands run in Docker)
docker-compose up -d                                    # Start development environment
docker-compose exec web python manage.py runserver     # Development server (if needed manually)
docker-compose exec web python manage.py makemigrations # Create migrations
docker-compose exec web python manage.py migrate       # Apply migrations
docker-compose exec web python manage.py createsuperuser # Create admin user

# Generate realistic test data with delegation trees
docker-compose exec web python manage.py generate_dummy_data_new --clear-data # Generate test communities and users
docker-compose exec web python manage.py run_crowdvote_demo # Calculate votes and test delegation

# Testing
docker-compose exec web pytest -v
docker-compose exec web pytest --cov

# Code quality
docker-compose exec web ruff check .
docker-compose exec web ruff format .

# Static files
docker-compose exec web python manage.py collectstatic --noinput

# Stop development environment
docker-compose down
```

### Dummy Data for Development Testing

**IMPORTANT**: Always use these specific test communities and users for delegation tree development and debugging:

#### **Required Test Communities**:
1. **"Minion Collective"** - Based on Despicable Me minions (Kevin, Stuart, Bob, etc.)
2. **"Springfield Town Council"** - Based on The Simpsons characters (Homer, Marge, Lisa, etc.)

#### **Required Test Users (A-F pattern)**:
Each community must include these test users for delegation validation:
- **User A**: Manual voter with tags `apple,orange,banana`
- **User B**: Follows A directly (on the apple tag)
- **User C**: Follows A directly (on the orange tag)  
- **User D**: Follows C (on the orange tag) and F (on all tags) → creates chain D→C,F→A
- **User E**: Follows C (on the orange tag) → creates chain E→C→A
- **User F**: Follows A directly (on the apple tag) AND follows D (on the banana tag) → creates dual inheritance F→A + F→D→C→A

#### **Critical Test Case**:
**User F should inherit from A only once, not twice** - this validates that the delegation system properly handles duplicate inheritance when someone follows both a person directly AND indirectly through a chain.

#### **Commands to Generate Test Data**:
```bash
# Generate complete test environment
docker-compose exec web python manage.py generate_dummy_data_new --clear-data
docker-compose exec web python manage.py run_crowdvote_demo

# Verify delegation tree visualization
# Visit: http://localhost:8000/communities/{uuid}/decisions/{uuid}/results/
# Look for users A_minion, F_minion in the delegation tree sections
```

This test setup ensures delegation tree visualization can be properly debugged and validated during development.

### Git Workflow
- Create feature branches from `main`
- Write descriptive commit messages
- Keep commits atomic
- Update tests with code changes
- Update documentation as needed

## Testing Guidelines

- Use `pytest` and `pytest-django`
- Write tests for:
  - Model methods and properties
  - Form validation
  - View permissions and logic
  - Template rendering
  - HTMX partial responses
- Use `factory_boy` for test data
- Maintain good test coverage (aim for >80%)
- Test database query counts for performance

## Code Review Process

When reviewing code:
1. Verify the implementation matches the plan
2. Check for bugs and edge cases
3. Look for data format mismatches
4. Identify over-engineering or refactoring needs
5. Ensure consistent coding style
6. Document findings in `docs/features/<N>_REVIEW.md`

## Feature Planning Process

When planning features:
1. Create technical requirements in `docs/features/<N>_PLAN.md`
2. Include brief context description
3. List all files and functions to modify
4. Explain algorithms step-by-step
5. Break large features into phases if needed
6. Avoid writing actual code in plans
7. Ask clarifying questions if requirements are unclear

## Collaboration Guidelines

### Before Writing Code
- Always confirm understanding of the task
- Ask up to 5 clarifying questions if needed
- Wait for explicit approval before implementing
- Work on one small part at a time

### During Development
- Keep the README.md and AGENTS.md updated
- Maintain comprehensive tests
- Follow the established patterns
- Document any deviations or new patterns
- Update docs/CHANGELOG.md after each development session to maintain project history

### Communication Style
- Be direct and honest
- Challenge assumptions constructively
- Suggest alternatives when appropriate
- Explain technical decisions clearly
- Never guess - always ask when uncertain
- Be concise! Just give me short, direct answers and avoid meta-commentary.
- Just give me answers and stop. Don't go on and on repeatedly summarizing what was accomplished.
- Avoid hyperbole and praise and sycophancy.

## Django-Specific Agent Checks

Flag these issues immediately:

### Settings & Configuration
- `DEBUG=True` in production
- Secrets or credentials in version control
- Missing `ALLOWED_HOSTS` configuration
- Insecure `SECRET_KEY`
- Missing security headers

### Code Quality
- N+1 queries without optimization
- Business logic in views or templates
- Missing database indexes on filtered fields
- Unhandled exceptions
- Missing authentication/permission checks

### Best Practices
- Direct import of `User` model (use `get_user_model()`)
- Hardcoded URLs in templates or views
- Database queries in loops
- Missing `select_related`/`prefetch_related`
- Synchronous operations that should be async

### Documentation Requirements
- **Always use comprehensive docstrings** for all models, views, forms, middleware, and signals
- **Module-level docstrings**: Every Python module should have a docstring explaining its purpose
- **Class docstrings**: All models, views, forms, and other classes must have detailed docstrings explaining:
  - Purpose and functionality
  - Key attributes and their meanings
  - Relationships to other models
  - Important methods and their behavior
  - Usage examples when helpful
- **Method docstrings**: All custom methods should have docstrings with:
  - Clear description of what the method does
  - Parameters and their types
  - Return values and their types
  - Any exceptions that might be raised
- **Keep docstrings updated**: When code changes, update docstrings immediately
- **Follow Django conventions**: Use Django's documentation style and terminology
- **Include business logic context**: Explain not just what the code does, but why it exists in the CrowdVote context

## Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Django Best Practices](https://django-best-practices.readthedocs.io/)
- [Railway Django Guide](https://docs.railway.com/guides/django)
- [HTMX Documentation](https://htmx.org/)
- [Tailwind CSS Docs](https://tailwindcss.com/)

---

Remember: This document guides our collaboration. Update it as we learn and evolve the project together.