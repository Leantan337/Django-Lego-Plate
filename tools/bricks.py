import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
import subprocess
import datetime
import shutil
import tempfile
import re
import sys

import yaml


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROJECT_SETTINGS_PATH = WORKSPACE_ROOT / "config" / "settings.py"
PROJECT_URLS_PATH = WORKSPACE_ROOT / "config" / "urls.py"
REQUIREMENTS_PATH = WORKSPACE_ROOT / "requirements.txt"
ENV_EXAMPLE_PATH = WORKSPACE_ROOT / ".env.example"
LEDGER_PATH = WORKSPACE_ROOT / "tools" / "lego_manifest.json"


def load_ledger() -> Dict[str, Any]:
    if not LEDGER_PATH.exists():
        return {"entries": []}
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def save_ledger(ledger: Dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def read_manifest(brick_path: Path) -> Dict[str, Any]:
    for name in ("brick.yaml", "brick.yml", "brick.json"):
        cand = brick_path / name
        if cand.exists():
            if cand.suffix in {".yaml", ".yml"}:
                return yaml.safe_load(cand.read_text(encoding="utf-8"))
            return json.loads(cand.read_text(encoding="utf-8"))
    raise FileNotFoundError("No brick manifest found (brick.yaml/brick.json)")


def plan_integration(manifest: Dict[str, Any]) -> Dict[str, Any]:
    plan: Dict[str, Any] = {
        "requirements": [],
        "settings": {"installed_apps": [], "middleware": [], "blocks": []},
        "urls": [],
        "env": [],
        "files": [],
    }
    for dep in manifest.get("dependencies", []) or []:
        plan["requirements"].append({"name": dep})
    django_cfg = manifest.get("django", {}) or {}
    for app in django_cfg.get("installed_apps", []) or []:
        plan["settings"]["installed_apps"].append(app)
    for mw in django_cfg.get("middleware", []) or []:
        plan["settings"]["middleware"].append(mw)
    if django_cfg.get("settings"):
        plan["settings"]["blocks"].append({
            "key_path": [],
            "merge_strategy": "deep_merge",
            "value": django_cfg["settings"],
        })
    for u in django_cfg.get("urls", []) or []:
        plan["urls"].append({"mount": u.get("mount"), "include": u.get("include")})
    for e in (manifest.get("env") or []):
        # support list of dicts or objects with key/default
        if isinstance(e, dict) and "key" in e:
            plan["env"].append(e)
    return plan


def print_plan(plan: Dict[str, Any]) -> None:
    print("Plan:")
    print(json.dumps(plan, indent=2))


def cmd_plan(path: str) -> None:
    manifest = read_manifest(Path(path))
    plan = plan_integration(manifest)
    print_plan(plan)


def _write_json_stdout(data: Any, compact: bool = False) -> None:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 2)
    sys.stdout.write(text + "\n")


def cmd_list(compact: bool = False, output: str | None = None) -> None:
    ledger = load_ledger()
    if output:
        Path(output).write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Print only the path so piping stays clean
        _write_json_stdout({"wrote": output}, compact=True)
        return
    _write_json_stdout(ledger, compact)


def _ensure_requirements(packages: List[str]) -> List[str]:
    if not packages:
        return []
    REQUIREMENTS_PATH.touch(exist_ok=True)
    current = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
    normalized = [line.strip() for line in current]
    actions: List[str] = []
    for pkg in packages:
        name = str(pkg)
        if not any(line.startswith(name) for line in normalized):
            current.append(name)
            actions.append(f"add:{name}")
    REQUIREMENTS_PATH.write_text("\n".join(current) + "\n", encoding="utf-8")
    return actions


def _insert_into_list_block(file_path: Path, block_name: str, entries: List[str]) -> List[str]:
    if not entries:
        return []
    content = file_path.read_text(encoding="utf-8")
    start_token = f"{block_name} = ["
    start_idx = content.find(start_token)
    if start_idx == -1:
        # block missing; nothing to do
        return []
    end_idx = content.find("]", start_idx)
    if end_idx == -1:
        return []
    list_block = content[start_idx:end_idx]
    actions: List[str] = []
    new_lines = []
    for entry in entries:
        quoted = f'    "{entry}",'  # match indentation style
        if quoted not in list_block and quoted not in content:
            new_lines.append(quoted)
            actions.append(f"add:{block_name}:{entry}")
    if not new_lines:
        return []
    insertion_point = end_idx
    updated = content[:insertion_point] + "\n" + "\n".join(new_lines) + content[insertion_point:]
    file_path.write_text(updated, encoding="utf-8")
    return actions


def _ensure_url_include(module: str, mount: str) -> List[str]:
    content = PROJECT_URLS_PATH.read_text(encoding="utf-8")
    actions: List[str] = []
    # ensure include import exists
    if " include(" not in content and "include" not in content.splitlines()[1]:
        if "from django.urls import path" in content and "include" not in content:
            content = content.replace(
                "from django.urls import path",
                "from django.urls import path, include",
            )
            actions.append("import:include")
    line = f'    path("{mount}", include("{module}")),\n'
    if line not in content:
        # insert before schema if present else append before last bracket
        insert_anchor = "# OpenAPI schema and docs"
        idx = content.find(insert_anchor)
        if idx == -1:
            idx = content.rfind("]\n")
        if idx == -1:
            idx = len(content)
        content = content[:idx] + line + content[idx:]
        actions.append(f"url:{mount}->{module}")
    PROJECT_URLS_PATH.write_text(content, encoding="utf-8")
    return actions


def _ensure_env(keys: List[Dict[str, Any]]) -> List[str]:
    if not keys:
        return []
    ENV_EXAMPLE_PATH.touch(exist_ok=True)
    lines = ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines()
    existing = {l.split("=", 1)[0] for l in lines if l and not l.startswith("#") and "=" in l}
    actions: List[str] = []
    for item in keys:
        key = item.get("key")
        default = item.get("default", "")
        if key and key not in existing:
            lines.append(f"{key}={default}")
            actions.append(f"env:{key}")
    ENV_EXAMPLE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return actions


def cmd_apply(path: str, assume_yes: bool) -> None:
    brick_path = Path(path)
    manifest = read_manifest(brick_path)
    plan = plan_integration(manifest)
    _write_json_stdout({"plan": plan}, compact=False)
    if not assume_yes:
        sys.stdout.write("Use --yes to apply changes\n")
        return

    actions: List[Dict[str, str]] = []
    # requirements
    req_pkgs = [pkg["name"] for pkg in plan["requirements"]]
    for act in _ensure_requirements(req_pkgs):
        actions.append({"file": "requirements.txt", "type": act})

    # copy app packages from brick into workspace if present
    for app_name in plan["settings"]["installed_apps"]:
        src = brick_path / app_name
        dst = WORKSPACE_ROOT / app_name
        if src.exists() and src.is_dir():
            if not dst.exists():
                shutil.copytree(src, dst)
                actions.append({"file": str(dst.relative_to(WORKSPACE_ROOT)), "type": "create_dir"})

    # settings.py mutations
    settings_actions: List[str] = []
    settings_actions += _insert_into_list_block(PROJECT_SETTINGS_PATH, "INSTALLED_APPS", plan["settings"]["installed_apps"])
    settings_actions += _insert_into_list_block(PROJECT_SETTINGS_PATH, "MIDDLEWARE", plan["settings"]["middleware"])
    for sa in settings_actions:
        actions.append({"file": "config/settings.py", "type": sa})

    # urls.py mutations
    for u in plan["urls"]:
        for ua in _ensure_url_include(u["include"], u["mount"].lstrip("/")):
            actions.append({"file": "config/urls.py", "type": ua})

    # env example
    for ea in _ensure_env(plan["env"]):
        actions.append({"file": ".env.example", "type": ea})

    # install and migrate
    subprocess.run(["pip", "install", "-r", str(REQUIREMENTS_PATH), "--disable-pip-version-check", "--no-input"], check=True)
    subprocess.run(["python", str(WORKSPACE_ROOT / "manage.py"), "migrate", "--noinput"], check=True)

    # record ledger
    ledger = load_ledger()
    entry = {
        "brick": manifest.get("name") or brick_path.name,
        "source": str(brick_path),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "actions": actions,
    }
    ledger.setdefault("entries", []).append(entry)
    save_ledger(ledger)
    sys.stdout.write("Applied.\n")


# ==================
# Git install + diff
# ==================

def _normalize_repo_to_url(repo: str) -> str:
    if repo.startswith("http://") or repo.startswith("https://") or repo.endswith(".git"):
        return repo
    if re.match(r"^[\w.-]+/[\w.-]+$", repo):
        return f"https://github.com/{repo}.git"
    raise ValueError("Unrecognized repo format. Use full git URL or owner/repo shorthand.")


def _find_brick_dir(root: Path) -> Path | None:
    for name in ("brick.yaml", "brick.yml", "brick.json"):
        if (root / name).exists():
            return root
    for p in root.rglob("brick.yaml"):
        return p.parent
    for p in root.rglob("brick.yml"):
        return p.parent
    for p in root.rglob("brick.json"):
        return p.parent
    return None


def _auto_detect_manifest(repo_root: Path) -> tuple[Path, Dict[str, Any]]:
    for apps_py in repo_root.rglob("apps.py"):
        app_dir = apps_py.parent
        app_name = app_dir.name
        urls_include = (app_dir / "urls.py").exists()
        manifest: Dict[str, Any] = {
            "name": app_name,
            "dependencies": [],
            "django": {
                "installed_apps": [app_name],
                "middleware": [],
                "settings": {},
                "urls": ([{"include": f"{app_name}.urls", "mount": f"/{app_name}/"}] if urls_include else []),
            },
        }
        # include root requirements if present
        req = repo_root / "requirements.txt"
        if req.exists():
            deps = [l.strip() for l in req.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith('#')]
            manifest["dependencies"] = deps[:20]
        brick_dir = repo_root
        (brick_dir / "brick.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        return brick_dir, manifest
    raise FileNotFoundError("Could not auto-detect a Django app (no apps.py found)")


def _cmd_install_git(repo: str) -> None:
    try:
        url = _normalize_repo_to_url(repo)
    except Exception as e:
        sys.stderr.write(f"[git-install] Invalid repo '{repo}': {e}\n")
        sys.stderr.write("[git-install] Falling back to local demo brick...\n")
        demo_dir = _ensure_demo_brick()
        cmd_plan(str(demo_dir))
        cmd_apply(str(demo_dir), assume_yes=True)
        return

    try:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            subprocess.run(["git", "clone", url, str(td_path)], check=True)
            brick_dir = _find_brick_dir(td_path)
            if brick_dir is None:
                brick_dir, _ = _auto_detect_manifest(td_path)
            sys.stdout.write("Plan (from git clone):\n")
            cmd_plan(str(brick_dir))
            cmd_apply(str(brick_dir), assume_yes=True)
    except Exception as e:
        sys.stderr.write(f"[git-install] Clone/apply failed: {e}\n")
        sys.stderr.write("[git-install] Falling back to local demo brick...\n")
        demo_dir = _ensure_demo_brick()
        cmd_plan(str(demo_dir))
        cmd_apply(str(demo_dir), assume_yes=True)


def _ensure_demo_brick() -> Path:
    demo_root = WORKSPACE_ROOT / "bricks" / "demo_polls"
    app_root = demo_root / "polls"
    templates_root = app_root / "templates" / "polls"
    demo_root.mkdir(parents=True, exist_ok=True)
    app_root.mkdir(parents=True, exist_ok=True)
    templates_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "polls-demo",
        "description": "Demo polls brick (fallback)",
        "dependencies": [],
        "django": {
            "installed_apps": ["polls"],
            "urls": [{"include": "polls.urls", "mount": "/polls/"}],
            "settings": {},
        },
    }
    (demo_root / "brick.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (app_root / "__init__.py").write_text("\n", encoding="utf-8")
    (app_root / "apps.py").write_text(
        "from django.apps import AppConfig\n\n"
        "class PollsConfig(AppConfig):\n"
        "    default_auto_field = 'django.db.models.BigAutoField'\n"
        "    name = 'polls'\n",
        encoding="utf-8",
    )
    (app_root / "views.py").write_text(
        "from django.shortcuts import render\n\n"
        "def index(request):\n"
        "    return render(request, 'polls/index.html', {'message': 'Hello from demo polls brick!'})\n",
        encoding="utf-8",
    )
    (app_root / "urls.py").write_text(
        "from django.urls import path\n"
        "from . import views\n\n"
        "app_name = 'polls'\n"
        "urlpatterns = [path('', views.index, name='index')]\n",
        encoding="utf-8",
    )
    (templates_root / "index.html").write_text(
        "{% extends 'base.html' %}\n"
        "{% block title %}Polls Demo{% endblock %}\n"
        "{% block content %}\n"
        "<div class=\"card\"><strong>Polls Demo</strong><div class=\"muted\">{{ message }}</div></div>\n"
        "{% endblock %}\n",
        encoding="utf-8",
    )
    return demo_root


def _cmd_diff(path: str) -> None:
    manifest = read_manifest(Path(path))
    plan = plan_integration(manifest)
    _write_json_stdout({"plan": plan}, compact=False)
    previews: List[str] = []
    if plan["requirements"]:
        existing = []
        if REQUIREMENTS_PATH.exists():
            existing = [l.strip() for l in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()]
        adds = [pkg["name"] for pkg in plan["requirements"] if not any(line.startswith(pkg["name"]) for line in existing)]
        if adds:
            previews.append("requirements.txt additions:\n" + "\n".join(["+ " + a for a in adds]))
    if plan["settings"]["installed_apps"]:
        previews.append("settings.py INSTALLED_APPS additions:\n" + "\n".join(["+ " + a for a in plan["settings"]["installed_apps"]]))
    if plan["settings"]["middleware"]:
        previews.append("settings.py MIDDLEWARE additions:\n" + "\n".join(["+ " + m for m in plan["settings"]["middleware"]]))
    if plan["urls"]:
        url_lines = [f'+ path("{u["mount"]}", include("{u["include"]}"))' for u in plan["urls"]]
        previews.append("config/urls.py additions:\n" + "\n".join(url_lines))
    if previews:
        sys.stdout.write("\nDiff preview (planned additions):\n" + "\n\n".join(previews) + "\n")
    else:
        sys.stdout.write("No changes planned.\n")

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lego bricks",
        description="Snap-in manager: plan/apply bricks, install from git, and preview diffs.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser(
        "plan",
        help="Show integration plan for a brick folder (reads brick.yaml or auto-detects)",
        description=(
            "Show integration plan for a brick folder.\n\n"
            "Examples:\n"
            "  python tools/bricks.py plan bricks/blog\n"
            "  python tools/bricks.py plan /path/to/brick\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_plan.add_argument("path", help="Path to a brick folder containing brick.yaml (or auto-detect)")

    p_list = sub.add_parser(
        "list",
        help="List installed bricks (JSON)",
        description=(
            "List installed bricks recorded in tools/lego_manifest.json (JSON).\n\n"
            "Examples:\n"
            "  python tools/bricks.py list\n"
            "  python tools/bricks.py list --compact | Out-File ledger.json\n"
            "  python tools/bricks.py list --output tools/ledger_dump.json\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_list.add_argument("--compact", action="store_true", help="Emit minified JSON (better for pipes)")
    p_list.add_argument("--output", help="Write JSON to file instead of stdout")
    p_apply = sub.add_parser(
        "apply",
        help="Apply a local brick folder non-interactively",
        description=(
            "Apply a brick: installs deps, updates settings/urls/env, migrates, records ledger.\n\n"
            "Examples:\n"
            "  python tools/bricks.py apply bricks/blog --yes\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_apply.add_argument("path", help="Path to local brick folder")
    p_apply.add_argument("--yes", action="store_true", dest="assume_yes", help="Apply without prompt")

    p_install = sub.add_parser(
        "install",
        help="Install a brick from git (URL or GitHub owner/repo)",
        description=(
            "Clone a git repo, detect a brick, show plan, and apply changes.\n\n"
            "Examples:\n"
            "  python tools/bricks.py install https://github.com/OWNER/REPO.git\n"
            "  python tools/bricks.py install OWNER/REPO\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_install.add_argument("repo", help="Git URL or GitHub owner/repo shorthand")

    p_diff = sub.add_parser(
        "diff",
        help="Preview planned additions (requirements/settings/urls) for a brick",
        description=(
            "Show a concise diff preview of planned changes.\n\n"
            "Examples:\n"
            "  python tools/bricks.py diff bricks/blog\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_diff.add_argument("path", help="Path to local brick folder")

    args = parser.parse_args()
    if args.cmd == "plan":
        cmd_plan(args.path)
    elif args.cmd == "list":
        cmd_list(compact=getattr(args, "compact", False), output=getattr(args, "output", None))
    elif args.cmd == "apply":
        cmd_apply(args.path, args.assume_yes)
    elif args.cmd == "install":
        _cmd_install_git(args.repo)
    elif args.cmd == "diff":
        _cmd_diff(args.path)


if __name__ == "__main__":
    main()


