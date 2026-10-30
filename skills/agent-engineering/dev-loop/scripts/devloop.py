#!/usr/bin/env python3
"""Resolve dev-loop configuration and scaffold the project layout.

Never contacts a service and never reads credentials. Remote instruction sources
(Notion, Google Docs, S3, URLs) are reported as `fetch_required`; the agent fetches
them with whatever tool it has.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import sys

STAGES = ["intent", "record", "design", "design_review", "slice", "implement",
          "verify", "code_review", "merge", "deploy", "close_out", "reflect"]
# Detection hints only. The skill never requires any of these tools.
CATEGORIES = {
    "spec": ("openspec", "spec-kit", "speckit", "specify", "kiro", "requirements"),
    "plan": ("writing-plans", "brainstorm", "plan", "design"),
    "review": ("review", "audit"),
    "tdd": ("tdd", "test-driven", "testing"),
    "worktree": ("worktree",),
    "debug": ("debug", "root-cause"),
    "orchestration": ("subagent", "orchestrat", "parallel", "dispatch"),
}
KNOWN_CLIS = ("openspec", "codex", "opencode", "claude", "gh", "herdr", "git")
LOCAL_KINDS = {"file", "dir", "text"}
DEFAULT_LAYOUT = {
    "decisions": "docs/decisions",
    "plans": "docs/plans",
    "register": "docs/plans/WORK-REGISTER.md",
    "intake": "docs/plans/INTAKE.md",
    "adr": "docs/adr",
    "backlog": "docs/backlog",
    "patches": "docs/backlog/PATCHES.md",
    "research": "docs/research",
    "handbook": "docs/handbook",
    "followups": "docs/review-followups.md",
    "journal": ".journal",
    "references": "references",
    "artifacts": "artifacts",
    "private": ".repo-local",
}
IGNORED = ("references", "artifacts", "private")
TEMPLATE_FILES = {"patches": "PATCHES.md", "register": "WORK-REGISTER.md", "intake": "INTAKE.md", "followups": "review-followups.md"}


class ConfigError(ValueError):
    pass


def expanded(value):
    return Path(os.path.expandvars(str(value))).expanduser().resolve()


def load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Cannot read configuration {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ConfigError(f"{path}: expected configuration version 1")
    layout = value.get("layout", {})
    if not isinstance(layout, dict) or not all(isinstance(v, str) and v.strip() for v in layout.values()):
        raise ConfigError(f"{path}: layout must map names to non-empty paths")
    unknown = set(layout) - set(DEFAULT_LAYOUT)
    if unknown:
        raise ConfigError(f"{path}: unknown layout keys {sorted(unknown)}")
    for key in ("inbox", "research_store"):
        if key in value and not (isinstance(value[key], dict) and isinstance(value[key].get("kind"), str)):
            raise ConfigError(f"{path}: {key}.kind is required")
    stage_tools = value.get("stage_tools", {})
    if not isinstance(stage_tools, dict) or set(stage_tools) - set(STAGES):
        raise ConfigError(f"{path}: stage_tools keys must be stage ids {STAGES}")
    for stage, tool in stage_tools.items():
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ConfigError(f"{path}: stage_tools.{stage} needs a name")
    sources = value.get("instruction_sources", [])
    if not isinstance(sources, list):
        raise ConfigError(f"{path}: instruction_sources must be a list")
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str) or not isinstance(source.get("kind"), str):
            raise ConfigError(f"{path}: every instruction source needs id and kind")
        if source["id"] in seen:
            raise ConfigError(f"{path}: duplicate instruction source id {source['id']}")
        seen.add(source["id"])
        if source["kind"] == "text":
            if not isinstance(source.get("text"), str):
                raise ConfigError(f"{path}: source {source['id']} kind=text needs text")
        elif not isinstance(source.get("uri"), str) or not source["uri"].strip():
            raise ConfigError(f"{path}: source {source['id']} needs uri")
        bad = [s for s in source.get("applies_to", []) if s not in STAGES and s != "all"]
        if bad:
            raise ConfigError(f"{path}: source {source['id']} names unknown stages {bad}")
        if source.get("mode", "append") not in ("append", "replace", "skip"):
            raise ConfigError(f"{path}: source {source['id']} mode must be append, replace or skip")
    return value


def candidates(project, explicit=None, env=None, home=None):
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)
    paths = []
    configured = explicit or env.get("DEV_LOOP_CONFIG")
    if configured:
        selected = expanded(configured)
        if not selected.is_file():
            raise ConfigError(f"Explicit configuration does not exist: {selected}")
        paths.append(selected)
    root = expanded(project)
    for parent in (root, *root.parents):
        match = parent / ".dev-loop" / "config.json"
        if match.is_file():
            paths.append(match)
            break
    xdg = Path(env.get("XDG_CONFIG_HOME") or home / ".config").expanduser()
    paths.append(xdg / "dev-loop" / "config.json")
    unique = []
    for path in paths:
        path = path.resolve()
        if path.is_file() and path not in unique:
            unique.append(path)
    return unique


def read_local(source, base):
    kind = source["kind"]
    if kind == "text":
        return {"text": source["text"]}
    if kind not in LOCAL_KINDS:
        return {"fetch_required": True}
    path = Path(os.path.expandvars(source["uri"])).expanduser()
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    try:
        if kind == "dir":
            files = sorted(p for p in path.iterdir() if p.suffix in (".md", ".txt"))
            return {"path": str(path), "text": "\n\n".join(f"# {p.name}\n{p.read_text(encoding='utf-8')}" for p in files)}
        return {"path": str(path), "text": path.read_text(encoding="utf-8")}
    except OSError as exc:
        raise ConfigError(f"Cannot load instruction source {source['id']} at {path}: {exc}") from exc


def resolve(project, explicit=None, env=None, home=None):
    paths = candidates(project, explicit, env, home)
    if not paths:
        return {"configured": False, "layout": dict(DEFAULT_LAYOUT),
                "message": "No configuration. Defaults apply; run interactive setup (guides/customization.md)."}
    loaded = [(p, load(p)) for p in paths]
    layers, layout, sources = [], dict(DEFAULT_LAYOUT), {}
    singles = {}
    stage_tools = {}
    for path, cfg in reversed(loaded):  # lowest priority first, so higher layers override
        layout.update(cfg.get("layout", {}))
        for key in ("inbox", "research_store", "roles", "review", "reflect", "constraints", "language", "spec_tool"):
            if key in cfg:
                singles[key] = cfg[key]
        for source in cfg.get("instruction_sources", []):
            entry = {**source, "from_config": str(path), **read_local(source, path.parent)}
            sources[source["id"]] = entry  # same id in a higher layer replaces the lower one
        stage_tools.update(cfg.get("stage_tools", {}))
        layers.append({"config": str(path), "scope": cfg.get("scope", "user")})
    by_stage = {stage: [] for stage in STAGES}
    for entry in sources.values():
        for stage in (STAGES if "all" in entry.get("applies_to", ["all"]) or not entry.get("applies_to") else entry["applies_to"]):
            by_stage[stage].append(entry["id"])
    return {"configured": True, "config": str(loaded[0][0]), "layers": layers, "layout": layout,
            **singles, "stage_tools": stage_tools, "instruction_sources": list(sources.values()),
            "sources_by_stage": {k: v for k, v in by_stage.items() if v},
            "precedence": "Newest explicit user instruction > project config > user config > skill defaults. "
                          "A source with mode=replace overrides that stage's default guide; append adds to it; skip turns the stage off."}


def skill_name(skill_md):
    try:
        text = skill_md.read_text(encoding="utf-8")[:2000]
    except OSError:
        return None
    match = re.search(r"^name:\s*(.+)$", text, re.M)
    return match.group(1).strip().strip("\"'") if match else skill_md.parent.name


def discover(project, roots=None, home=None, env=None):
    """List installed skills and CLIs that could fill workflow stages. Read-only."""
    home = Path.home() if home is None else Path(home)
    env = os.environ if env is None else env
    project = expanded(project)
    if roots is None:
        roots = [home / ".claude/skills", home / ".claude/plugins", home / ".agents/skills", home / ".codex/skills",
                 home / ".config/opencode/skills", home / ".config/opencode/skill",
                 project / ".claude/skills", project / ".agents/skills", project / "skills"]
    found, seen = [], set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for skill_md in sorted(root.rglob("SKILL.md")):
            if len(skill_md.relative_to(root).parts) > 6:
                continue
            real = skill_md.resolve()
            name = skill_name(skill_md)
            if not name or real in seen:
                continue
            seen.add(real)
            lowered = name.lower()
            cats = [c for c, words in CATEGORIES.items() if any(w in lowered for w in words)]
            if cats:
                found.append({"name": name, "categories": cats, "path": str(real)})
    path_env = env.get("PATH")
    clis = {c: shutil.which(c, path=path_env) for c in KNOWN_CLIS}
    return {"skills": found, "clis": {k: v for k, v in clis.items() if v},
            "note": "Detection by name only. Ask the user which of these they actually use; never adopt one silently."}


def initialize(path, scope="project"):
    state = {"version": 1, "scope": scope,
             "inbox": {"kind": "local_file", "uri": "docs/backlog/INDEX.md", "notes": "Where the owner's wishes land."},
             "research_store": {"kind": "local_dir", "uri": "references"},
             "layout": {}, "language": "en",
             "review": {"design": {"when": "new or risky design"}, "code": {"when": "security, lifecycle or default-on changes"}, "round_limit": 3},
             "reflect": {"interval_minutes": 30},
             "instruction_sources": []}
    path = expanded(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ConfigError(f"Refusing to overwrite existing configuration: {path}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(state, out, ensure_ascii=False, indent=2)
        out.write("\n")
    return {"created": str(path)}


def scaffold(root, layout, templates, dry_run=False):
    root = expanded(root)
    actions = []
    files = {k: v for k, v in layout.items() if k in TEMPLATE_FILES}
    for key, rel in layout.items():
        target = root / rel
        if key in files:
            if target.exists():
                actions.append({"skip": str(target)})
                continue
            source = templates / TEMPLATE_FILES[key]
            actions.append({"write": str(target)})
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        elif target.exists():
            actions.append({"skip": str(target)})
        elif key in ("references",):
            actions.append({"mkdir": str(target)})  # user may replace it with a symlink
            if not dry_run:
                target.mkdir(parents=True)
        else:
            actions.append({"mkdir": str(target)})
            if not dry_run:
                target.mkdir(parents=True)
    ignore = [layout[k].rstrip("/") + "/" for k in IGNORED]
    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    missing = [line for line in ignore if line not in existing]
    if missing:
        actions.append({"gitignore_add": missing})
        if not dry_run:
            with gitignore.open("a", encoding="utf-8") as out:
                out.write(("\n" if existing and existing[-1] else "") + "\n".join(missing) + "\n")
    return {"root": str(root), "dry_run": dry_run, "actions": actions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cmds = parser.add_subparsers(dest="command", required=True)
    res = cmds.add_parser("resolve", help="Read layered config and local instruction sources; never writes")
    res.add_argument("--project", default=os.getcwd())
    res.add_argument("--config")
    val = cmds.add_parser("validate")
    val.add_argument("path")
    init = cmds.add_parser("init", help="Create a config at an explicit path; never overwrites")
    init.add_argument("--output", required=True)
    init.add_argument("--scope", default="project")
    dis = cmds.add_parser("discover", help="List installed skills/CLIs relevant to workflow stages; read-only")
    dis.add_argument("--project", default=os.getcwd())
    dis.add_argument("--root", action="append", help="Skill root to scan (repeatable); default: standard locations")
    sc = cmds.add_parser("scaffold", help="Create the docs layout; never overwrites files")
    sc.add_argument("--project", default=os.getcwd())
    sc.add_argument("--config")
    sc.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "resolve":
            result = resolve(args.project, args.config)
        elif args.command == "discover":
            result = discover(args.project, roots=args.root)
        elif args.command == "validate":
            load(expanded(args.path))
            result = {"valid": True, "config": str(expanded(args.path))}
        elif args.command == "init":
            result = initialize(args.output, args.scope)
        else:
            layout = resolve(args.project, args.config)["layout"]
            result = scaffold(args.project, layout, Path(__file__).resolve().parents[1] / "templates", args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ConfigError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
