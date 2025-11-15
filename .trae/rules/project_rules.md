# AVThrift Backend Project Rules

These rules codify conventions for this Django + DRF backend so development stays consistent and scalable.

## Overview
- Runtime: Python 3.13
- Frameworks: Django, Django REST Framework, drf-spectacular
- Package manager: UV (no pip)
- Environment: `python-decouple` (no dotenv)
- Deployment: Docker image to DigitalOcean (App Platform or Droplet)

## Tooling
- Formatting: Black with `line-length: 120`
- Imports: isort with `profile: black`
- Linting: Flake8, ignore `E203`, `W503`, exclude `.venv`, `migrations`, `staticfiles`, `build`, `dist`
- Pre-commit: enable hooks `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `black`, `isort`, `flake8`

## Environment & Config
- All settings via `python-decouple`; see `.env.example`
- Required vars: `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_ENGINE`, `FRONTEND_URL`
- Dev defaults: SQLite, console email backend
- Prod: Postgres, SMTP provider, strict CORS/CSRF

## Architecture
- Apps: start with `users`, then add bounded-context apps (e.g., `catalog`, `inventory`, `orders`, `payments`)
- Service layer: business logic in `services.py`; keep views thin
- Selectors vs services: selectors for read-only queries, services for mutations/side-effects
- Observability: JSON logs in prod, add Sentry later

## Authentication & Authorization
- JWT: SimpleJWT for API clients; session auth for admin
- Token endpoints: obtain/refresh/verify
- Logout: blacklist refresh tokens
- Unique emails: enforce DB-level uniqueness; normalize lowercase

## Emails
- Verification: send token to current email; confirm sets `email_verified=true`
- Password reset: request (generic response), confirm with token + new password
- Email reset: authenticated request sets `pending_email`; confirm applies change
- Links built with `FRONTEND_URL` (`/verify-email`, `/reset-password`, `/change-email`)

## API Docs
- Schema: `GET /api/schema/`
- Swagger UI: `GET /api/docs/`
- Annotate serializers/views for clear OpenAPI docs; plan versioning (`/api/v1/...`)

## Coding Rules
- Docstrings: required for public functions/classes; concise (1–3 sentences)
- Serializers: ModelSerializer for CRUD; plain Serializer for actions/workflows
- Views: avoid heavy logic; delegate to services
- Security: generic responses for sensitive flows; validate inputs rigorously
- Tests: use pytest + pytest-django; add unit/integration tests per app; prefer `factory_boy` for fixtures; keep tests close to apps

## Deployment
- Dockerfile: installs UV; default `gunicorn` command; `DJANGO_SETTINGS_MODULE=config.settings.prod`
- DigitalOcean: provide env vars; run `uv run python manage.py migrate` on deploy
- Static: Whitenoise; media storage: plan DigitalOcean Spaces later

## Common Commands
- Install deps: `uv sync`
- Migrate: `uv run python manage.py migrate`
- Run dev: `uv run python manage.py runserver`
- Formatting: `uv run isort .` and `uv run black .`
- Linting: `uv run flake8 config users`
- Pre-commit: `uv run pre-commit install` and `uv run pre-commit run --all-files`
 - Pytest: `uv run pytest -q` and `uv run pytest --cov=config --cov=users --cov-report=term-missing`

## Change Management
- Keep changes small and focused; respect existing style
- Prefer adding tests with new features; do not fix unrelated issues in feature PRs
- Document new environment variables in `.env.example` and README
