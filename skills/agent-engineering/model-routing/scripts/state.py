#!/usr/bin/env python3
"""Resolve portable routing state without creating stores or loading credentials."""
import argparse
import json
import os
from pathlib import Path
import sys


class StateError(ValueError):
    pass


def load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateError(f"Cannot read configuration {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise StateError(f"{path}: expected configuration version 1")
    storage = value.get("storage")
    if not isinstance(storage, dict) or not isinstance(storage.get("backend"), str) or not storage["backend"].strip():
        raise StateError(f"{path}: storage.backend is required")
    for table in ("ledger", "rules"):
        locator = storage.get(table)
        if not isinstance(locator, dict) or not isinstance(locator.get("uri"), str) or not locator["uri"].strip():
            raise StateError(f"{path}: storage.{table}.uri is required")
    if not isinstance(value.get("policy", {}), dict):
        raise StateError(f"{path}: policy must be an object")
    if not isinstance(value.get("policy_files", []), list) or not all(isinstance(p, str) for p in value.get("policy_files", [])):
        raise StateError(f"{path}: policy_files must be a list of paths")
    return value


def expanded(value):
    return Path(os.path.expandvars(str(value))).expanduser().resolve()


def candidates(project, explicit=None, env=None, home=None, skill_dir=None):
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)
    skill_dir = Path(__file__).resolve().parents[1] if skill_dir is None else Path(skill_dir)
    paths = []
    configured = explicit or env.get("MODEL_ROUTING_CONFIG")
    if configured:
        selected = expanded(configured)
        if not selected.is_file():
            raise StateError(f"Explicit configuration does not exist: {selected}")
        paths.append(selected)
    root = expanded(project)
    for parent in (root, *root.parents):
        match = parent / ".model-routing" / "config.json"
        if match.is_file():
            paths.append(match)
            break
    xdg = Path(env.get("XDG_CONFIG_HOME") or home / ".config").expanduser()
    paths.extend([xdg / "model-routing" / "config.json", skill_dir / ".local" / "config.json"])
    unique = []
    for path in paths:
        path = path.resolve()
        if path.is_file() and path not in unique:
            unique.append(path)
    return unique


def resolve(project, explicit=None, env=None, home=None, skill_dir=None):
    paths = candidates(project, explicit, env, home, skill_dir)
    if not paths:
        return {"configured": False, "message": "No state found. Locate an existing store before bootstrapping one."}
    loaded = [(path, load(path)) for path in paths]
    layers = []
    for path, state in reversed(loaded):
        texts = []
        for filename in state.get("policy_files", []):
            policy_path = Path(os.path.expandvars(filename)).expanduser()
            if not policy_path.is_absolute():
                policy_path = path.parent / policy_path
            try:
                texts.append({"path": str(policy_path.resolve()), "text": policy_path.read_text(encoding="utf-8")})
            except OSError as exc:
                raise StateError(f"Cannot load policy file {policy_path}: {exc}") from exc
        layers.append({"config": str(path), "policy": state.get("policy", {}), "policy_files": texts})
    path, state = loaded[0]
    return {"configured": True, "config": str(path), "scope": state.get("scope", "user"),
            "storage": state["storage"], "policy_layers": layers,
            "policy_precedence": "Newest explicit user instructions govern. Retain hard bans/data restrictions across layers unless the user changes them."}


def initialize(path, backend, ledger_uri, rules_uri, ledger_table=None, rules_table=None):
    for name, value in (("backend", backend), ("ledger_uri", ledger_uri), ("rules_uri", rules_uri)):
        if not isinstance(value, str) or not value.strip():
            raise StateError(f"{name} must be non-empty")
    state = {"version": 1, "scope": "user", "storage": {"backend": backend,
        "ledger": {"uri": ledger_uri}, "rules": {"uri": rules_uri}}, "policy": {}, "policy_files": []}
    if ledger_table:
        state["storage"]["ledger"]["table"] = ledger_table
    if rules_table:
        state["storage"]["rules"]["table"] = rules_table
    path = expanded(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise StateError(f"Refusing to overwrite existing configuration: {path}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(state, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return {"created": str(path), "storage": state["storage"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    resume = commands.add_parser("resolve", help="Read state and all policy layers; never writes")
    resume.add_argument("--project", default=os.getcwd())
    resume.add_argument("--config")
    validate = commands.add_parser("validate", help="Validate one configuration")
    validate.add_argument("path")
    init = commands.add_parser("init", help="Create a new configuration at an explicit path")
    init.add_argument("--output", required=True)
    init.add_argument("--backend", required=True)
    init.add_argument("--ledger-uri", required=True)
    init.add_argument("--rules-uri", required=True)
    init.add_argument("--ledger-table")
    init.add_argument("--rules-table")
    args = parser.parse_args()
    try:
        if args.command == "resolve":
            result = resolve(args.project, args.config)
        elif args.command == "validate":
            load(expanded(args.path))
            result = {"valid": True, "config": str(expanded(args.path))}
        else:
            result = initialize(args.output, args.backend, args.ledger_uri, args.rules_uri, args.ledger_table, args.rules_table)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except StateError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
