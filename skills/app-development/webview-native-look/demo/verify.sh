#!/usr/bin/env bash
# Build the host and assert the contract on a live WKWebView. Prints PASS/FAIL per check, and
# leaves screenshots in $OUT (default: ./.build/shots) so a human can look at them too.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${OUT:-$here/.build/shots}"; build="${NATIVE_LOOK_BUILD_DIR:-$here/.build}"
mkdir -p "$out" "$build"
swiftc -O -swift-version 5 "$here/host-macos/main.swift" -o "$build/NativeLookHost"
url="file://$here/web/index.html?view=lab"
fail=0
check() { # name backdrop appearance expected-substring js
  local got; got="$("$build/NativeLookHost" --url "$url" --backdrop "$2" --appearance "$3" --eval "$5" --delay 1.5 | sed -n 's/^eval //p')"
  if [[ "$got" == *"$4"* ]]; then echo "PASS $1: $got"; else echo "FAIL $1: wanted '$4' in '$got'"; fail=1; fi
}
J='JSON.stringify({macos:document.documentElement.getAttribute("macos")!==null,dark:document.documentElement.hasAttribute("dark"),backdrop:document.documentElement.getAttribute("backdrop"),glass:document.documentElement.getAttribute("glass"),accent:getComputedStyle(document.documentElement).getPropertyValue("--color-system-accent").trim().length>0,ipc:!!(window.webkit&&window.webkit.messageHandlers.ipcRequest)})'
check "vibrancy+dark"  vibrancy dark  '"backdrop":"vibrancy","glass":"native"' "$J"
check "dark attribute" vibrancy dark  '"dark":true' "$J"
check "light attribute" vibrancy light '"dark":false' "$J"
check "host attributes" vibrancy dark '"macos":true' "$J"
check "accent injected" vibrancy dark '"accent":true' "$J"
check "ipc bridge"     vibrancy dark  '"ipc":true' "$J"
check "no backdrop -> blur" none dark '"glass":"blur"' "$J"
check "ipc round trip" vibrancy dark '"os":"Version' 'JSON.stringify(window.__hostInfo||null)'
for b in vibrancy glass none; do for a in light dark; do
  "$build/NativeLookHost" --url "file://$here/web/index.html?view=launcher" --backdrop "$b" --appearance "$a" --screenshot "$out/launcher-$b-$a.png" --delay 1.5 >/dev/null
done; done
echo "screenshots: $out"
exit $fail
