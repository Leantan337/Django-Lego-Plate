# Django Lego Plate

Build Django backends like Lego — fast, reusable, and production-ready.

## What is this?

Django Lego Plate helps you create a working Django backend in minutes — without the boring setup.
Think of it like building with Lego:

- The base plate = your Django project.
- The bricks = prebuilt features (Login/Auth, API, Background Tasks, etc.).

You choose the bricks you want, and the tool snaps them into your project automatically. It updates settings, URLs, installs dependencies, and sets up configs so you don’t have to.

You can add bricks from:

- Your computer (a folder)
- Any GitHub/Git repo
- Any Python package

You can safely run it multiple times or remove bricks later.

## Who is it for?

- Hackathons & quick prototypes – Get a backend running in minutes.
- Teams – Stop repeating the same Django setup over and over.
- Beginners – Skip the setup pain, start coding features right away.

## Why use it?

- Integration over generation – Modifies your existing project instead of overwriting it.
- Reusable bricks – Share and reuse features across projects.
- Safe changes – See a preview before applying edits.
- Uninstall ready – Remove a brick anytime, with tracked changes.

## What it can do

- Add bricks from:
  - Local folder
  - Git repository
  - Pip package
- Automatically update:
  - INSTALLED_APPS
  - urls.py
  - Middleware
  - settings.py
  - .env / .env.example
  - requirements.txt
  - Celery/Docker configs
- Built-in defaults:
  - SQLite, Django REST Framework, CORS, WhiteNoise, DRF Spectacular, pytest

## Starter Brick Catalog

| Feature                | What it adds                  |
| ---------------------- | ----------------------------- |
| REST API (DRF)         | APIs with browsable interface |
| Auth (allauth)         | Login, signup, social auth    |
| CORS                   | Cross-origin requests         |
| WhiteNoise             | Static file serving           |
| API Docs (Spectacular) | OpenAPI & Swagger docs        |
| Background Tasks       | Celery + Redis                |
| PostgreSQL             | Production DB setup           |
| Sentry                 | Error tracking                |
| Testing                | pytest, pytest-django         |
| Docker                 | Container setup               |

## Example Setup

```bash
# 1. Create a project
django-admin startproject config

# 2. Pick your bricks (via CLI or Web UI)
# CLI (examples):
python tools/bricks.py plan bricks/blog
python tools/bricks.py apply bricks/blog --yes
python tools/bricks.py install owner/repo          # GitHub shorthand
python tools/bricks.py install https://github.com/owner/repo.git

# 3. Install and run
python -m venv .venv && .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

If Celery was added:

```bash
celery -A config worker -l info
```

## Uninstalling a Brick

Recorded edits live in `tools/lego_manifest.json`.

```bash
# (coming soon) CLI uninstall using the ledger
lego remove drf
```

## Project Structure (after setup)

```
config/              # Main Django project
bricks/              # Downloaded/staged bricks
requirements.txt
.env.example
pytest.ini           # if pytest added
tools/lego_manifest.json   # Tracks all brick edits
```

## Roadmap

- Rich uninstall with migration rollback
- GUI for brick selection
- Remote catalog of verified bricks



