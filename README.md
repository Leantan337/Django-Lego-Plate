# Django Lego Plate

Modular Django project assembler that snaps prebuilt, reusable Django apps (“bricks”) onto a clean base project (“plate”). Designed for hackathon speed and production-aware defaults. Instead of hand-writing boilerplate, it integrates and wires settings, URLs, dependencies, environment variables, and services automatically.

## In plain English
- This tool helps you make a working Django backend fast, without the boring setup.
- Imagine your project is a base plate and features are Lego bricks.
- You pick the bricks you want (Login/Auth, API, Background Tasks, etc.). The tool snaps them in for you.
- It updates settings, URLs, and installs packages automatically so you don’t have to.
- You can bring bricks from your computer (a folder) or from any repo/package.
- It’s safe to run more than once, and you can remove bricks later if you change your mind.

## Who is this for?
- Hackathons and quick prototypes.
- Teams who repeat the same Django setup again and again.
- Beginners who want a working project in minutes.

## Why
- **Integration over generation**: Safely modifies `settings.py`, `urls.py`, `requirements.txt`, `.env(.example)`, Docker/Celery configs, and more.
- **Reusable bricks**: Import from a local folder, git repository, or pip package.
- **Idempotent edits**: Dry-run plans, minimal diffs, and recorded changes for uninstall.
- **Hackathon-fast**: Go from idea to running backend in minutes, not days.

## Features
- **Brick import from anywhere**: Local path, git URL, or pip package.
- **Auto-discovery with manifest-first**: Reads `brick.yaml/json` if present; falls back to heuristics (detect Django apps, URLs, deps, settings).
- **Safe integration**: Adds `INSTALLED_APPS`, URLs, middleware, settings, env keys, migrations, Celery tasks, admin, templates/static.
- **Dry-run and verification**: Shows a plan/diff before applying; verifies with install/migrate/run commands.
- **Uninstall-ready**: Records edits in `lego_manifest.json` so you can revert a brick later.
- **Sane defaults**: SQLite, DRF, CORS, WhiteNoise, DRF Spectacular, and pytest recommended as a baseline.

## Quick Start (with Cursor + GPT-5)
1) Open this repo in Cursor.
2) Use the kickoff prompt in the editor/chat:

```text
Assemble a Django project with importable bricks.

Project:
- Name: config
- Database: SQLite
- Docker: no

Import these bricks (sources can be local path, git URL, or pip package):
- drf (builtin)
- cors (builtin)
- spectacular (builtin)
- whitenoise (builtin)
- pytest (builtin)
- <your-local-brick-path-or-git-url-1>
- (optional) django-allauth
- (optional) celery+redis
- (optional) postgres
- (optional) sentry

Deliver:
- Edits to requirements/settings/urls/env and any new files.
- Dry-run plan first; then final edits.
- Commands to install, migrate, run.
- Verification steps.
```

3) After assembly, run the suggested commands (example):

```bash
python -m venv .venv && .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
# If Celery added:
celery -A config worker -l info
```

## Brick Catalog (starter set)
- **REST API (DRF)**: Adds `djangorestframework`, `'rest_framework'` to `INSTALLED_APPS`, base `REST_FRAMEWORK` settings, and browsable API routes under `api/`.
- **Auth (django-allauth)**: Adds packages, `SITE_ID`, auth backends, and `allauth` URLs.
- **Background tasks (Celery + Redis)**: Adds `celery.py`, broker config from env, and sample task wiring.
- **PostgreSQL**: Adds `psycopg[binary]` and env-driven `DATABASES` settings.
- **CORS**: Adds `django-cors-headers` with middleware and default origins.
- **Static files (WhiteNoise)**: Adds middleware and storage configuration.
- **OpenAPI/Docs (DRF Spectacular)**: Adds schema generation and docs routes.
- **Error monitoring (Sentry)**: Initializes Sentry with DSN from env.
- **Testing (pytest-django)**: Adds `pytest`, `pytest-django`, and a minimal config.
- **Containerization (Docker)**: Adds `Dockerfile` and optional `docker-compose.yml`.

## Importing Bricks
- **Local folder**: Select or drag the brick folder. The assistant will read a manifest if available or infer integration.
- **Git repo**: Provide a URL. The assistant stages it under `bricks/<name>/` (or installs via pip VCS URL) and integrates.
- **Pip package**: Provide the package name or VCS URL. Dependencies are added to `requirements.txt` and integration proceeds.

## Uninstalling Bricks
- The assistant records per-brick edits in `lego_manifest.json`.
- Request an uninstall to reverse edits (requirements, settings, urls, env). Database migration rollback is opt-in.

## Project Structure (after assembly)
```
config/                 # Django project (example name)
  settings.py
  urls.py
  __init__.py
  celery.py             # if Celery added
apps/                   # optional app namespace
bricks/<name>/          # staged bricks (git/local)
requirements.txt
.env.example
pytest.ini              # if pytest added
lego_manifest.json      # recorded edits for uninstall
```

## Documentation
- Architecture: see `docs/ARCHITECTURE.md`

## Roadmap
- Manifest schema v1 and validation
- Rich uninstall/rollback including migrations
- GUI for brick selection and conflict resolution
- Remote catalog with verified bricks

## License
TBD. Add a `LICENSE` file (MIT recommended for templates).


