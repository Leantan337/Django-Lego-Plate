import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
import subprocess
import datetime
import shutil

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


def cmd_list() -> None:
    ledger = load_ledger()
    print(json.dumps(ledger, indent=2))


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
    print("Plan:")
    print(json.dumps(plan, indent=2))
    if not assume_yes:
        print("Use --yes to apply changes")
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
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "actions": actions,
    }
    ledger.setdefault("entries", []).append(entry)
    save_ledger(ledger)
    print("Applied.")

def main() -> None:
    parser = argparse.ArgumentParser("lego bricks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("path")

    sub.add_parser("list")
    p_apply = sub.add_parser("apply")
    p_apply.add_argument("path")
    p_apply.add_argument("--yes", action="store_true", dest="assume_yes")

    args = parser.parse_args()
    if args.cmd == "plan":
        cmd_plan(args.path)
    elif args.cmd == "list":
        cmd_list()
    elif args.cmd == "apply":
        cmd_apply(args.path, args.assume_yes)


if __name__ == "__main__":
    main()


