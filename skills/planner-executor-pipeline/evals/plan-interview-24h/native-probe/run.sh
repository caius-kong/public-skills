#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../../.." && pwd -P)"
EXTENSION_ROOT="$(cd "$REPO_ROOT/pi/planner-executor-pipeline" && pwd -P)"
PI_SUBAGENTS_ROOT="${PI_SUBAGENTS_ROOT:-$HOME/.pi/agent/npm/node_modules/pi-subagents}"
TYPEBOX_ROOT="${TYPEBOX_ROOT:-$(find "$HOME/Library/pnpm/global/v11" -path '*/node_modules/typebox/package.json' -print -quit 2>/dev/null | sed 's#/package.json##')}"

[ -d "$PI_SUBAGENTS_ROOT/src/intercom" ] || { echo "pi-subagents source not found at $PI_SUBAGENTS_ROOT" >&2; exit 2; }
[ -f "$TYPEBOX_ROOT/package.json" ] || { echo "Pi's installed typebox package not found; set TYPEBOX_ROOT" >&2; exit 2; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/pi-plan-interview-native.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/node_modules"
cp -a "$PI_SUBAGENTS_ROOT/src" "$TMP/src"
ln -s "$TYPEBOX_ROOT" "$TMP/node_modules/typebox"
printf '{"type":"module"}\n' > "$TMP/package.json"
cat > "$TMP/resolve-typebox.mjs" <<EOF
const target = new URL("file://$TYPEBOX_ROOT/build/index.mjs").href;
export async function resolve(specifier, context, nextResolve) {
  if (specifier === "typebox") return { url: target, shortCircuit: true };
  return nextResolve(specifier, context);
}
EOF

PI_SUBAGENTS_NATIVE_CHANNEL="$TMP/src/intercom/native-supervisor-channel.js" \
  node --experimental-strip-types --experimental-loader "$TMP/resolve-typebox.mjs" --test \
  "$EXTENSION_ROOT/evals/plan-interview-24h/native-probe/timeout-extension.test.mjs"
