#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target="${1:-$PWD}"
target="$(cd "$target" && pwd)"
install_skill=1
copilot=1

usage() {
  cat <<'EOF'
Usage: setup.sh [project-root] [--no-skill] [--no-copilot]

Installs a local skill copy and agent instruction pointers. It never reads,
prints, copies, or changes Pro credentials and does not configure MCP servers.
EOF
}

for arg in "${@:2}"; do
  case "$arg" in
    --no-skill) install_skill=0 ;;
    --no-copilot) copilot=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

marker_start='<!-- shadcn-studio-skill:start -->'
marker_end='<!-- shadcn-studio-skill:end -->'
snippet="$marker_start
Use the project-local `shadcn-studio` skill at `.agents/skills/shadcn-studio/SKILL.md` for Studio registry, CLI, agent setup, or React-to-Svelte porting. Follow its credential-handling rules and inspect the target package's `components.json` before installing.
$marker_end"

add_pointer() {
  local file="$1"
  mkdir -p "$(dirname "$target/$file")"
  touch "$target/$file"
  if ! grep -Fq "$marker_start" "$target/$file"; then
    printf '\n%s\n' "$snippet" >> "$target/$file"
    echo "Added pointer: $file"
  else
    echo "Pointer already present: $file"
  fi
}

if (( install_skill )); then
  mkdir -p "$target/.agents/skills"
  if [[ -e "$target/.agents/skills/shadcn-studio" ]]; then
    echo "Skill destination exists; leaving it untouched: .agents/skills/shadcn-studio" >&2
  else
    cp -R "$skill_dir" "$target/.agents/skills/shadcn-studio"
    echo "Installed skill: .agents/skills/shadcn-studio"
  fi
fi

add_pointer AGENTS.md
add_pointer CLAUDE.md
mkdir -p "$target/.cursor/rules"
cursor_file="$target/.cursor/rules/shadcn-studio.mdc"
if [[ ! -e "$cursor_file" ]]; then
  cat > "$cursor_file" <<'EOF'
---
description: Shadcn Studio registry setup and component porting guidance
alwaysApply: false
---
For Shadcn Studio work, read `.agents/skills/shadcn-studio/SKILL.md` first. Inspect the target package's `components.json`; never expose Pro credentials. Studio registry components are React-oriented and need a native port for Svelte or another framework.
EOF
  echo "Created pointer: .cursor/rules/shadcn-studio.mdc"
else
  echo "Cursor rule exists; leaving it untouched: .cursor/rules/shadcn-studio.mdc"
fi

if (( copilot )); then
  copilot_file="$target/.github/instructions/shadcn-studio.instructions.md"
  mkdir -p "$(dirname "$copilot_file")"
  if [[ -e "$copilot_file" ]]; then
    echo "Copilot instruction file exists; leaving it untouched: .github/instructions/shadcn-studio.instructions.md"
  else
    curl --create-dirs -fL --silent --show-error \
      -o "$copilot_file" \
      https://cdn.shadcnstudio.com/ss-assets/mcp/instructions/copilot-instructions.md
    echo "Downloaded Copilot instructions: .github/instructions/shadcn-studio.instructions.md"
  fi
fi

echo "Setup complete in $target"
echo "MCP is agent-specific and is not configured by this script. See the skill's MCP section."
