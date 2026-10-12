#!/usr/bin/env bash
# Plain-browser mode: same page, no host. Use the Lab tab to drive macos / dark / glass / zoom by hand.
set -euo pipefail
cd "$(dirname "$0")/web"
echo "http://localhost:${PORT:-8787}/index.html?view=lab"
exec python3 -m http.server "${PORT:-8787}"
