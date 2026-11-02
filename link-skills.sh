#!/usr/bin/env bash
set -euo pipefail

# link-skills.sh — Symlink skills from this repo into agent harness directories.
#
# Directory layout:
#   skills/claude/          ← Claude Code
#   skills/codex/           ← Codex
#   skills/pi/              ← Pi
#   skills/openclaw/        ← OpenClaw
#
# All skills are platform-bound for now. Universal skills will appear at
# skills/ when they exist. Each platform target symlinks:
#   skills/* (universal, if any) + skills/<platform>/* → target dir.
#
# Codex and Pi both read ~/.agents/skills/ (shared universal destination).
#
# Usage:
#   ./link-skills.sh claude      → ~/.claude/skills/
#   ./link-skills.sh codex       universal → ~/.agents/skills/
#                                codex/* → ~/.codex/skills/
#   ./link-skills.sh pi          universal → ~/.agents/skills/
#                                pi/* → ~/.pi/agent/skills/
#   ./link-skills.sh openclaw    → ~/clawd/skills/
#   ./link-skills.sh all         All four platforms

REPO="$(cd "$(dirname "$0")" && pwd)"
TARGET="all"
for arg in "$@"; do
  case "$arg" in
    --force) LINK_FORCE=1 ;;
    -*) echo "Unknown option: $arg" >&2; exit 1 ;;
    *) TARGET="$arg" ;;
  esac
done

link_into() {
  local src_dir="$1"
  local dest_dir="$2"
  local label="$3"

  if [ ! -d "$src_dir" ]; then
    echo "[$label] Source directory $src_dir not found, skipping."
    return 0
  fi

  mkdir -p "$dest_dir"

  for skill_dir in "$src_dir"/*/; do
    [ -d "$skill_dir" ] || continue

    # A skill directory has a SKILL.md at its root. Excludes things that live
    # next to skills but are not skills — notably skill-creator eval workspaces
    # (<skill-name>-workspace/, a sibling of the skill dir per skill-creator).
    [ -f "$skill_dir/SKILL.md" ] || continue

    local dirname
    dirname="$(basename "$skill_dir")"

    # Skip platform subdirectories when iterating skills/ top-level
    case "$dirname" in
      claude|codex|pi|openclaw) continue ;;
    esac

    local name="$dirname"
    local target="$dest_dir/$name"

    if [ -L "$target" ] && [ "$(readlink "$target")" = "$skill_dir" ]; then
      echo "[$label] Already linked: $name"
      continue
    fi

    if [ -e "$target" ] && [ ! -L "$target" ]; then
      if [ "${LINK_FORCE:-0}" = "1" ]; then
        echo "[$label] Removing real dir (--force): $target"
        rm -rf "$target"
      else
        echo "[$label] SKIP: $target exists as a real directory. Use --force to replace."
        continue
      fi
    fi

    if [ -L "$target" ]; then
      rm -f "$target"
    fi

    ln -sfn "$skill_dir" "$target"
    echo "[$label] Linked $name → $target"
  done
}

# ============================================================
# Platform definitions
# ============================================================

link_standalone() {
  # Agent that only reads its own path: universal + platform-specific → same dest
  local label="$1"
  local dest="$2"
  local platform_dir="$3"

  link_into "$REPO/skills"              "$dest" "$label"
  link_into "$REPO/skills/$platform_dir" "$dest" "$label"
}

link_agents_shared() {
  # Agent that reads ~/.agents/skills/: universal → shared, platform-specific → own path
  local label="$1"
  local platform_dest="$2"
  local platform_dir="$3"

  link_into "$REPO/skills"               "$HOME/.agents/skills" "$label"
  link_into "$REPO/skills/$platform_dir" "$platform_dest"       "$label"
}

configure_openclaw_symlink_allow() {
  # OpenClaw 2026.7.1+ blocks symlinks that resolve outside the workspace root.
  # Allow the skills/openclaw source directory as a valid symlink target.
  local config="$HOME/.openclaw/openclaw.json"
  if [ ! -f "$config" ]; then
    echo "[openclaw] No config at $config, skip allowSymlinkTargets."
    return 0
  fi
  REPO_DIR="$REPO" python3 -c "
import json, os, sys
repo = os.environ['REPO_DIR']
home = os.path.expanduser('~')
target = repo + '/skills/openclaw'
if target.startswith(home + '/'):
    target = '~' + target[len(home):]
with open('$config') as f:
    d = json.load(f)
d.setdefault('skills', {}).setdefault('load', {})['allowSymlinkTargets'] = [target]
with open('$config', 'w') as f:
    json.dump(d, f, indent=2)
    f.write('\n')
print('[openclaw] Set allowSymlinkTargets in config.')
" 2>&1 || echo "[openclaw] WARNING: Failed to set allowSymlinkTargets."
}

case "$TARGET" in
  claude)         link_standalone   "claude"   "$HOME/.claude/skills"       "claude" ;;
  openclaw)       link_standalone   "openclaw" "$HOME/clawd/skills"         "openclaw"
                  configure_openclaw_symlink_allow ;;
  codex)          link_agents_shared "codex"   "$HOME/.codex/skills"        "codex" ;;
  pi)             link_agents_shared "pi"      "$HOME/.pi/agent/skills"     "pi" ;;
  all)
    link_standalone   "claude"   "$HOME/.claude/skills"       "claude"
    link_standalone   "openclaw" "$HOME/clawd/skills"         "openclaw"
    configure_openclaw_symlink_allow
    link_agents_shared "codex"   "$HOME/.codex/skills"        "codex"
    link_agents_shared "pi"      "$HOME/.pi/agent/skills"     "pi"
    ;;
  *)
    echo "Usage: $0 {claude|codex|pi|openclaw|all} [--force]"
    exit 1
    ;;
esac

echo "Done."