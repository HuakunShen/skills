---
name: strip-ai-coauthors
description: >
  Remove AI / agent co-author and attribution trailers (Co-Authored-By: Claude,
  Sisyphus, noreply@anthropic.com, "Ultraworked with", "Generated with Claude",
  🤖 lines) from git commit messages by rewriting history. Use when a user wants
  to clean up, strip, or scrub co-author / bot / AI-attribution trailers from
  commit history, un-attribute an AI from commits, or fix a contributors graph
  showing an AI account. Covers the safe dry-run → backup → filter-branch → verify
  → cleanup flow and the pushed-vs-unpushed force-push distinction.
---

# Strip AI co-author trailers from git history

Use this skill when someone wants AI/agent co-author or attribution lines gone
from their commit messages — e.g. `Co-Authored-By: Claude ...`, a `Sisyphus`
co-author, `Ultraworked with ...`, `🤖 Generated with [Claude Code]`, or an AI
account (`sisyphus-dev-ai`, a bot) showing up in the GitHub contributors graph.

## Principle (why this rewrites history)

A commit's hash is `SHA(tree + parents + author + committer + message)`. The
message is part of the hash, so **you cannot edit a message in place** — you
create a new commit with the new message, and because each child references its
parent by hash, **every commit from the first changed one up to HEAD is rebuilt
with a new hash**. That is "rewriting history."

Consequences:
- **Unpushed commits** (e.g. `origin/main..HEAD` on a feature branch) → rewrite
  is purely local, zero coordination, no force-push. This is the easy, safe case.
- **Already-pushed commits** → local and remote diverge; you must
  `git push --force-with-lease`, and anyone who cloned must reset. Only do this
  with the user's explicit go-ahead.
- Rewriting only changes messages — verify the **tree is byte-identical** to a
  backup afterward (`git diff --stat backup HEAD` must be empty).

## Preconditions — check before touching anything

1. **Clean working tree.** `git diff --quiet && git diff --cached --quiet`.
   If dirty, stop — commit or stash first. NEVER `git stash` when another
   session/agent may be actively editing the same tree; you can swallow their
   in-progress work. Ask the user to confirm they're done and everything's
   committed.
2. **Know the range.** Default `origin/main..HEAD` (the unpushed commits on the
   current branch). Confirm with `git log <range> --oneline` and whether any of
   it is already pushed (`git branch -r --contains <sha>`).
3. **Make a backup branch** pinned to current HEAD:
   `git branch backup/pre-coauthor-strip-$(date +%Y%m%d-%H%M%S)`.

## Run mode

The bundled script `references/strip-ai-coauthors.sh` does the safe flow:
dry-run by default, creates its own backup ref, then rewrites via
`git filter-branch --msg-filter` (a perl one-liner that deletes matching lines
and trims trailing blanks). It is bash-3.2 compatible (macOS system bash).

```bash
# 1. dry run — lists each commit as strip/keep, changes nothing
RANGE=origin/main..HEAD bash references/strip-ai-coauthors.sh

# 2. apply — creates refs/backup/... then rewrites
RANGE=origin/main..HEAD APPLY=1 bash references/strip-ai-coauthors.sh
```

What to remove is `STRIP_RE` (a perl regex, the alternation body, matched
case-insensitively per message line). Default covers Claude/Sisyphus/Clio
co-authors, `noreply@anthropic.com`, `clio-agent@sisyphuslabs.ai`,
`Ultraworked with`, `Generated with [Claude`, and `🤖 ... Generated with`.
Override for other bots, e.g.:

```bash
STRIP_RE='co-authored-by:.*(?:dependabot|renovate)\[bot\].*' \
  RANGE=origin/main..HEAD APPLY=1 bash references/strip-ai-coauthors.sh
```

Prefer NOT to strip legitimate human co-authors — keep the pattern specific to
AI/agent/bot identities.

### Modern alternative — git filter-repo

If `git filter-repo` is installed (`brew install git-filter-repo`), prefer it —
faster, cleaner (no `refs/original` cruft), purpose-built. A `--message-callback`
variant is in the script's trailing comment. `filter-branch` is the no-install
fallback and what the script uses by default.

## Verify (always, before declaring done)

```bash
# no AI trailers remain
git log <range> --format='%B' | grep -iE \
  'co-authored-by|ultraworked|generated with|noreply@anthropic|sisyphus' \
  || echo "clean"

# only messages changed — tree must be identical to the backup
git diff --stat backup/pre-coauthor-strip-<ts> HEAD   # expect no output
```

Spot-check one message: `git show <new-sha> -s`.

## Cleanup (after the user confirms the result)

```bash
git branch -D backup/pre-coauthor-strip-<ts>
git update-ref -d refs/backup/coauthor-strip-<oldshort>   # script's own ref
rm -rf .git/refs/original && git reflog expire --expire=now --all
```

Keep the backups until the user is happy — they are the only undo.
Restore: `git reset --hard backup/pre-coauthor-strip-<ts>`.

## Push

- Unpushed branch → just `git push` normally.
- Already-pushed → `git push --force-with-lease` (only with explicit consent).

## Notes / gotchas

- macOS ships bash 3.2 — invoke the script with `bash script.sh` (its shebang is
  `#!/usr/bin/env bash`); the script avoids `mapfile` and other bash-4-isms.
- GitHub's **contributors graph is cached** and lags after a rewrite/force-push;
  the live `repos/OWNER/REPO/contributors` API is the source of truth. Don't
  chase a stale graph.
- Rewriting only reachable history: a trailer on a commit that's no longer on any
  branch (e.g. left on an old backup branch) is separate work — target its range
  specifically.
