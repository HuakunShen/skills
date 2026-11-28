#!/usr/bin/env bash
# Strip AI/agent co-author and attribution trailers from git commit messages.
#
#   RANGE=origin/main..HEAD bash strip-ai-coauthors.sh            # dry run
#   RANGE=origin/main..HEAD APPLY=1 bash strip-ai-coauthors.sh    # rewrite
#
# See ../SKILL.md for the safe flow, verification and force-push rules.
# bash 3.2 compatible (macOS system bash): no mapfile, no ${var,,}.

set -eu

RANGE="${RANGE:-origin/main..HEAD}"
APPLY="${APPLY:-0}"

# Perl regex body, matched case-insensitively per message line.
DEFAULT_RE='co-authored-by:[^\n]*(?:claude|sisyphus|clio|noreply@anthropic\.com)|ultraworked with|generated with \[?claude|🤖[^\n]*generated with'
STRIP_RE="${STRIP_RE:-$DEFAULT_RE}"
export STRIP_RE

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
note() { printf '%s\n' "$*"; }

command -v perl >/dev/null 2>&1 || die "perl is required"

[ -z "$(git status --porcelain)" ] || die "working tree is dirty; commit or stash first"

git rev-list -n 1 "$RANGE" >/dev/null 2>&1 || die "cannot resolve range: $RANGE"
TOTAL=$(git rev-list --count "$RANGE")
[ "$TOTAL" -gt 0 ] || die "range $RANGE is empty"

# Temp perl program kept outside the repo: filter-branch checks out commits.
MSGPROG=$(mktemp "${TMPDIR:-/tmp}/strip-ai-coauthors.XXXXXX.pl")
trap 'rm -f "$MSGPROG"' EXIT

# Reads a message on stdin, deletes matching lines, trims trailing blanks.
cat >"$MSGPROG" <<'PERL'
BEGIN {
    my $p = $ENV{STRIP_RE};
    die "STRIP_RE not set\n" unless defined $p && length $p;
    $main::re = qr/$p/i;
}
s/^.*$main::re.*\n//mg;
s/[ \t]+$//mg;
s/\s+\z//;
$_ .= "\n" if length;
PERL

# --- dry run: classify every commit in range -------------------------------
strip_count=0
printf '%-6s %-9s %s\n' VERDICT COMMIT SUBJECT
while IFS= read -r sha; do
  [ -n "$sha" ] || continue
  msg=$(git log -1 --format=%B "$sha")
  if printf '%s\n' "$msg" | perl -0777 -ne '
      BEGIN { my $p = $ENV{STRIP_RE} // ""; $re = length $p ? qr/$p/i : undef }
      exit(defined $re && /$re/m ? 0 : 1)'; then
    verdict=strip
    strip_count=$((strip_count + 1))
  else
    verdict=keep
  fi
  printf '%-6s %-9s %s\n' "$verdict" "$(git log -1 --format=%h "$sha")" \
    "$(git log -1 --format=%s "$sha")"
done <<EOF
$(git rev-list "$RANGE")
EOF

if [ "$strip_count" -eq 0 ]; then
  note ""
  note "nothing to strip in $RANGE"
  exit 0
fi

if [ "$APPLY" != "1" ]; then
  note ""
  note "dry run: $strip_count of $TOTAL commit(s) in $RANGE would be rewritten"
  note "re-run with APPLY=1 to rewrite"
  exit 0
fi

# --- apply ----------------------------------------------------------------
old_head=$(git rev-parse HEAD)
short_head=$(git rev-parse --short "$old_head")
backup_branch="backup/pre-coauthor-strip-$(date +%Y%m%d-%H%M%S)"
backup_ref="refs/backup/coauthor-strip-$short_head"

git branch "$backup_branch" "$old_head"
git update-ref "$backup_ref" "$old_head"
note ""
note "backup branch: $backup_branch"
note "backup ref:    $backup_ref"

export MSGPROG FILTER_BRANCH_SQUELCH_WARNING=1
git filter-branch -f --msg-filter 'perl -0777 -p "$MSGPROG"' "$RANGE"

if [ -n "$(git diff --stat "$backup_branch" HEAD)" ]; then
  die "tree changed during rewrite — restore with: git reset --hard $backup_branch"
fi

remaining=$(git log "$RANGE" --format=%B | grep -ciE 'co-authored-by|ultraworked|generated with|noreply@anthropic' || true)
note ""
note "rewrote $(git rev-list --count "$RANGE") commit(s) in $RANGE"
if [ "$remaining" = "0" ]; then
  note "verified: tree identical to backup, no AI trailers remain"
else
  note "warning: $remaining trailer line(s) still match — check STRIP_RE"
fi
