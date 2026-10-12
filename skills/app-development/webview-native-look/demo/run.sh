#!/usr/bin/env bash
# Build the Swift host (once) and open the web demo in it.
#   ./run.sh                       dark/light follows the system, vibrancy backdrop
#   ./run.sh --backdrop glass      Liquid Glass (macOS 26+), falls back to vibrancy
#   ./run.sh --appearance light --url "file://$PWD/web/index.html?view=lab"
# Browser-only (no host): ./serve.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${NATIVE_LOOK_BUILD_DIR:-$here/.build}"
mkdir -p "$out"
if [ ! -x "$out/NativeLookHost" ] || [ "$here/host-macos/main.swift" -nt "$out/NativeLookHost" ]; then
  swiftc -O -swift-version 5 "$here/host-macos/main.swift" -o "$out/NativeLookHost"
fi
args=("$@")
case " ${args[*]:-} " in *" --url "*) ;; *) args+=(--url "file://$here/web/index.html") ;; esac
exec "$out/NativeLookHost" "${args[@]}"
