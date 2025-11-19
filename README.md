# AVThrift Backend

A production-grade e-commerce backend built with Django, Django REST Framework, and drf-spectacular for API docs. The project uses UV for Python dependency management, `python-decouple` for environment configuration, and ships with Docker for consistent builds and deployments. Frontend will be a separate Next.js app integrated later.

## Highlights
- Django 5 + DRF with modular settings (`base`, `dev`, `prod`)
- OpenAPI schema and Swagger UI via `drf-spectacular`
- Environment-first config using `python-decouple`
- UV for fast, reproducible dependency management
- Dockerfile and docker-compose for parity across dev/CI/prod
- Pre-commit hooks and code quality tools (Black, isort, Flake8)

Project rules: see `.trae/rules/project_rules.md` for conventions and guidelines.

---

## Quick Start (Local Dev)

Prerequisites
- Python 3.13 (optional if you only use Docker)
- UV installed (`iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex` on Windows)
- Docker (optional, only if you want local Postgres)

1) Install dependencies
```
uv sync
```

2) Configure environment
```
copy .env.example .env
```
Defaults use SQLite. To switch to Postgres locally set in `.env`:
```
DATABASE_ENGINE=postgres
DATABASE_NAME=postgres
DATABASE_USER=postgres
DATABASE_PASSWORD=postgres
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

3) (Optional) Start Postgres via Docker Compose
```
docker compose up -d db
```

4) (Optional) Start Redis for local cache/sessions
```
docker compose up -d redis
```
Then set `REDIS_URL=redis://localhost:6379/1` in `.env`. Dev settings will automatically use Redis for cache and `cached_db` sessions when `REDIS_URL` is present.

5) Run migrations and start the server
```
uv run python manage.py migrate
uv run python manage.py runserver
```

6) Explore endpoints
- Health: `GET http://localhost:8000/health/`
- Swagger UI: `GET http://localhost:8000/api/docs/`
- OpenAPI schema: `GET http://localhost:8000/api/schema/`

---

## Project Structure
```
config/
  asgi.py
  wsgi.py
  urls.py
  health.py
  settings/
    base.py
    dev.py
    prod.py
.env.example
Dockerfile
docker-compose.yml
pyproject.toml
```

Key points
- `manage.py` defaults to `config.settings.dev` for local runs.
- `asgi.py` and `wsgi.py` default to `config.settings.prod` for deploy contexts.
- `settings/base.py` configures DRF, Spectacular, CORS, static files, and DB selection (`DATABASE_ENGINE`).

---

## Configuration & Environment

This project uses `python-decouple` (not dotenv). All settings are read via `config()` calls.

Environment variables (see `.env.example`):
- Core: `SECRET_KEY`, `ALLOWED_HOSTS`, `DEBUG`
- CORS/CSRF: `CORS_ALLOW_ALL_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`
- Database: `DATABASE_ENGINE` (`sqlite` or `postgres`), `DATABASE_*`
- Production security (in prod.py): `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`

Cache & Sessions
- Dev/Test use in-memory cache (`LocMemCache`) and cache-backed sessions for speed.
- Prod uses Redis cache via `REDIS_URL` and `SESSION_ENGINE=cached_db` for durability.
- Set `REDIS_URL` like `redis://:password@redis-host:6379/1`.

Throttling
- Global rates: `user`, `anon`.
- Scoped rates include `catalog`, `catalog_admin_write`, `cart` (read), `cart_write` (write), and auth-related scopes.
- Tests override `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES` and the app reads them dynamically.

Cart throttling defaults
- Development: `cart=20/min`, `cart_write=20/min` (configured in `config/settings/dev.py`)
- Production: `cart=120/hour`, `cart_write=60/hour` (configured in `config/settings/prod.py`)
If you enable Redis (`REDIS_URL`), throttling consistency improves across processes.

---

## API Docs
- `drf-spectacular` generates the OpenAPI schema.
- `GET /api/schema/` returns JSON schema.
- `GET /api/docs/` serves Swagger UI.

Annotate serializers and views for best docs quality. Versioning can be added later via URL (`/api/v1/...`) or content negotiation.

---

## Cart and Guest Sessions

Overview
- All endpoints are versioned under `/api/v1/cart/`.
- Authenticated users operate on a single active cart; guests operate via a client-side session id.
- Throttle scopes: reads use `cart`, writes use `cart_write` (see Throttling above for rates).

Guest session identifier
- Header: `X-Session-Id` is required for guest cart reads and most writes.
- Body field: `session_id` is accepted on guest write serializers; header takes precedence.
- Format: generate a UUIDv4 or random 32–64 char token client-side and persist until signup/login.

Authenticated endpoints
- `GET /api/v1/cart/` returns the active cart with items and totals.
- `POST /api/v1/cart/items/` adds a variant to the cart.
- `PATCH /api/v1/cart/items/{item_id}/` updates quantity for a cart item.
- `DELETE /api/v1/cart/items/{item_id}/delete/` removes a cart item.
- `POST /api/v1/cart/checkout/` checks out the cart.
  - Optional header `Idempotency-Key: <token>` makes checkout idempotent per user+path+method.
- `POST /api/v1/cart/abandon/` releases reservations and marks the cart abandoned.
- `POST /api/v1/cart/clear/` deletes items and releases reservations; status stays active.

Guest endpoints
- `GET /api/v1/cart/guest/` returns the guest cart (`X-Session-Id` required).
- `POST /api/v1/cart/guest/items/` adds an item (`X-Session-Id` optional if `session_id` in body).
- `PATCH /api/v1/cart/guest/items/{item_id}/` updates quantity (`X-Session-Id` required unless in body).
- `DELETE /api/v1/cart/guest/items/{item_id}/delete/` removes an item (`X-Session-Id` required).
- `POST /api/v1/cart/guest/clear/` clears the guest cart (`X-Session-Id` required).
- `POST /api/v1/cart/merge-guest/` merges a guest cart into the authenticated user cart (`X-Session-Id` required).

Merge behavior
- Quantities aggregate per variant; reservations are recreated atomically on the destination user cart.
- Guest reservations are released after successful merge; the source guest cart is deleted.
- Conflicts (e.g., insufficient stock) return `400` with a generic, safe error.

Error responses
- Generic mutation failures use `400` with `{"detail": "Unable to update cart."}`.
- Missing guest session header returns `400` with `{"detail": "Missing X-Session-Id."}`.
- Access violations to non-owned items return `404` with `{"detail": "Not found."}`.

Reservation & abandonment TTLs
- `CART_RESERVATION_TTL_MINUTES` controls how long stock reservations live (default `30`).
- `CART_ABANDON_TTL_MINUTES` controls when stale active carts are auto-abandoned (default `120`).
- Configure in `.env` and they are read via `python-decouple` (`settings/base.py`).

Support/Admin actions
- Admin list page for `Cart` includes actions for:
  - Clear cart: releases reservations, keeps status active.
  - Abandon cart: releases reservations, marks abandoned.
  - Merge guest cart into user: select a target user in the action form, then merge.
- Management command to abandon stale carts by TTL:
  - `uv run python manage.py abandon_stale_carts`
  - Uses `CART_ABANDON_TTL_MINUTES` to compute cutoff and abandons all matching active carts.

Idempotent checkout
- Header: `Idempotency-Key` is supported on `POST /api/v1/cart/checkout/`.
- Replays with the same key return the original response to prevent duplicate orders.
- Keys are unique per user and endpoint; use a new key for each distinct intent.

## Scheduled Jobs (Production)

Orders idempotency cleanup
- Command: `uv run python manage.py cleanup_idempotency`
- Purpose: deletes expired idempotency keys (`orders.IdempotencyKey.expires_at` < now).

DigitalOcean App Platform
- Add a Job component with schedule `@daily` (or `0 3 * * *`).
- Set command to `uv run python manage.py cleanup_idempotency`.
- Ensure environment variables mirror your Web service (e.g., `DJANGO_SETTINGS_MODULE=config.settings.prod`).

DigitalOcean Droplet (cron)
- Create a cron entry: `0 3 * * * cd /app && uv run python manage.py cleanup_idempotency >> /var/log/cleanup_idempotency.log 2>&1`
- Replace `/app` with your deploy directory; confirm the environment exports `DJANGO_SETTINGS_MODULE=config.settings.prod`.

Local manual run
- `uv run python manage.py cleanup_idempotency`

---

## Code Quality & Tooling

Installed dev tools: Black, isort, Flake8, pre-commit.

Run manually
```
uv run isort .
uv run black .
uv run flake8 config
```

Pre-commit (optional but recommended)
```
git init
uv run pre-commit install
uv run pre-commit run --all-files
```

Configuration
- Black/isort/Flake8 configured in `pyproject.toml`
- `.flake8` ensures consistent behavior across environments (line-length 120, excludes `.venv`, migrations, staticfiles)

---

## Running with Docker

Production-style image
```
docker build -t avthrift-backend:latest .
docker run -p 8000:8000 --env-file .env avthrift-backend:latest
```

Local dev compose (Django + Postgres)
```
docker compose up --build
```

Notes
- The Dockerfile installs UV in the image and runs `gunicorn` by default.
- In App Platform, set `DJANGO_SETTINGS_MODULE=config.settings.prod` and provide environment variables.

---

## Deployment (DigitalOcean)

Option A: App Platform
- Connect repo and use the `Dockerfile`.
- Set environment variables:
  - `DJANGO_SETTINGS_MODULE=config.settings.prod`
  - `SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`
  - `DATABASE_ENGINE=postgres` and `DATABASE_*` for Managed PostgreSQL
- Add a deploy command: `uv run python manage.py migrate`
- Optionally run `collectstatic` if you serve static assets externally.

Option B: Droplet
- Install Docker and run the image.
- Use nginx as reverse proxy with HTTPS.
- Connect to DO Managed PostgreSQL and DO Spaces for media (when added).

---

## Roadmap (Backend)
- Auth: JWT via `djangorestframework-simplejwt`, email verification, password resets
- Core apps: `customers`, `catalog`, `inventory`, `cart`, `orders`, `payments`, `shipping`
- Media storage: `django-storages` + DO Spaces
- Tasks & cache: `Celery` + `Redis` for async jobs, caching
- Observability: Sentry, structured logs (JSON already enabled in `prod.py`)

---

## Common Commands
```
# Migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Create admin
uv run python manage.py createsuperuser

# Run dev server
uv run python manage.py runserver 0.0.0.0:8000

# System check
uv run python manage.py check
```

---

## Troubleshooting
- Flake8 reading config: keep `.flake8` for consistent behavior if `pyproject.toml` isn’t picked up.
- Postgres connection: ensure `DATABASE_ENGINE=postgres` and the container/managed DB is reachable.
- CORS/CSRF in production: restrict `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to your Next.js domain(s).

---

## License
Proprietary. Do not distribute without permission.
