#!/bin/bash
# Stop hook: before a turn ends in the kunkun repo, refuse to stop while lanes are idle and READY-QUEUE.md has unchecked items.
# Fires at most once per stop cycle (stop_hook_active) and at most once per 10 minutes, so it cannot loop.
IN=$(cat)
CWD=$(printf '%s' "$IN" | python3 -c "import sys,json;print(json.load(sys.stdin).get('cwd',''))" 2>/dev/null)
ACTIVE=$(printf '%s' "$IN" | python3 -c "import sys,json;print(json.load(sys.stdin).get('stop_hook_active',False))" 2>/dev/null)
case "$CWD" in */kunkun-v2.1*) ;; *) exit 0;; esac
[ "$ACTIVE" = "True" ] && exit 0
Q=/Volumes/Portable2TB/ExtDev/kunkun-v2.1/.repo-local/dev-loop/READY-QUEUE.md
[ -f "$Q" ] || exit 0
M=/tmp/kunkun-refill-stop.stamp
if [ -f "$M" ] && [ $(( $(date +%s) - $(stat -f %m "$M") )) -lt 600 ]; then exit 0; fi
export PATH=$HOME/.local/bin:$HOME/.cargo/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
LIVE=$(hc ls --label project=kunkun 2>/dev/null | python3 -c "import sys,json;print(len([t for t in json.load(sys.stdin)['terminals'] if t.get('state')=='live']))" 2>/dev/null || echo 0)
ITEMS=$(grep -E '^- \[ \]' "$Q" | head -6)
[ -z "$ITEMS" ] && exit 0
[ "$LIVE" -ge 6 ] && exit 0
touch "$M"
REASON="Idle lanes: only $LIVE live kunkun lanes (target >= 6) while READY-QUEUE.md has unchecked items. Launch the next ones now (Swift is one serial chain; fill with non-Swift work), mark them in the queue, then stop. Top items:
$ITEMS"
python3 -c "import json,sys;print(json.dumps({'decision':'block','reason':sys.argv[1]}))" "$REASON"
