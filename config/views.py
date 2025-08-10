from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse


def _read_ledger() -> Dict[str, Any]:
    ledger_path = Path(__file__).resolve().parent.parent / "tools" / "lego_manifest.json"
    if not ledger_path.exists():
        return {"entries": []}
    return json.loads(ledger_path.read_text(encoding="utf-8"))


def home(request: HttpRequest) -> HttpResponse:
    ledger = _read_ledger()
    bricks = [e["brick"] for e in ledger.get("entries", [])]
    stats = {
        "num_bricks": len(bricks),
        "num_features": 4 + (1 if "auth-allauth" in bricks else 0),
    }
    return render(request, "home.html", {"bricks": bricks, "stats": stats})


def bricks_catalog(request: HttpRequest) -> HttpResponse:
    ledger = _read_ledger()
    installed = {e["brick"] for e in ledger.get("entries", [])}
    available_path = Path(__file__).resolve().parent.parent / "tools" / "available_bricks.json"
    if available_path.exists():
        available = json.loads(available_path.read_text(encoding="utf-8"))
    else:
        available = [
            {"name": "blog", "category": "API", "status": "Installed", "description": "Simple blog app"},
            {"name": "allauth", "category": "Auth", "status": "Installed", "description": "Accounts and auth"},
            {"name": "celery", "category": "Tasks", "status": "Available", "description": "Background workers"},
            {"name": "postgres", "category": "DB", "status": "Available", "description": "PostgreSQL database"},
            {"name": "sentry", "category": "Observability", "status": "Available", "description": "Error monitoring"},
        ]
    for b in available:
        if b["name"] in installed:
            b["status"] = "Installed"
    return render(request, "bricks.html", {"available": available})


def system_status(request: HttpRequest) -> HttpResponse:
    checks = [
        {"name": "OpenAPI schema", "url": "/api/schema/", "ok": True},
        {"name": "Swagger docs", "url": "/api/docs/", "ok": True},
        {"name": "Blog list", "url": "/blog/", "ok": True},
    ]
    return render(request, "system.html", {"checks": checks})


def demo(request: HttpRequest) -> HttpResponse:
    return render(request, "demo.html")


