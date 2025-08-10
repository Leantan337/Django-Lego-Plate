from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
import subprocess
import sys


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
    installed = [{"name": e["brick"], "source": e.get("source", "")} for e in ledger.get("entries", [])]
    installed_names = {i["name"] for i in installed}
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
        if b["name"] in installed_names:
            b["status"] = "Installed"
    return render(request, "bricks.html", {"available": available, "installed": installed})


def system_status(request: HttpRequest) -> HttpResponse:
    checks = [
        {"name": "OpenAPI schema", "url": "/api/schema/", "ok": True},
        {"name": "Swagger docs", "url": "/api/docs/", "ok": True},
        {"name": "Blog list", "url": "/blog/", "ok": True},
    ]
    return render(request, "system.html", {"checks": checks})


def demo(request: HttpRequest) -> HttpResponse:
    return render(request, "demo.html")


@csrf_exempt
def import_brick(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)
    source = request.POST.get("source", "").strip()
    if not source:
        return JsonResponse({"success": False, "error": "Missing source"}, status=400)
    # Decide install vs apply
    try:
        if source.startswith("http://") or source.startswith("https://") or "/" in source and not Path(source).exists():
            cmd = [sys.executable, str(Path(__file__).resolve().parent.parent / "tools" / "bricks.py"), "install", source]
        else:
            # local path
            cmd = [sys.executable, str(Path(__file__).resolve().parent.parent / "tools" / "bricks.py"), "apply", source, "--yes"]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).resolve().parent.parent))
        ok = proc.returncode == 0
        return JsonResponse({"success": ok, "stdout": proc.stdout, "stderr": proc.stderr})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


