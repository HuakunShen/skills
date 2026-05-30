---
name: deepwiki-badge
description: >
  Generate a DeepWiki badge (Markdown or HTML) from a repo URL, or from the
  current git remote if run inside a repository, and optionally insert it into
  README.md.
---

# DeepWiki Badge Skill

Use this skill when a user asks to create or insert a DeepWiki badge.

## What I do

- Accept a repository URL (for example, `https://github.com/owner/repo` or `git@github.com:owner/repo.git`), or infer it from git remote.
- Resolve `owner/repo` and generate either Markdown or HTML badge syntax.
- Optionally insert the badge line into `README.md` (at top) when requested.
- Avoid creating/maintaining any extra shell script; the coding agent executes
  git parsing itself.

## Badge forms

Markdown example:

```markdown
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/owner/repo)
```

HTML example:

```html
<a href="https://deepwiki.com/owner/repo"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
```

## Run mode

1. Determine repo slug:
   - If input URL exists, normalize it.
   - Else, run `git remote get-url origin` (preferred).
   - If unavailable, read the first URL from `git remote -v`.
   - Parse `owner/repo` from common formats:
     - `https://github.com/owner/repo`
     - `https://github.com/owner/repo.git`
     - `git@github.com:owner/repo.git`
     - `ssh://git@github.com/owner/repo.git`
2. Build badge:
   - Markdown: `[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/owner/repo)`
   - HTML: `<a href="https://deepwiki.com/owner/repo"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>`
3. If insertion is requested:
   - Use `README.md` by default (or provided path).
   - Insert badge at the beginning, before existing content.
   - If content already contains `deepwiki.com/badge.svg`, skip adding.

## Example behaviors

Input:
- URL: `https://github.com/kunkunsh/kunkun`
- format: markdown

Output:
`[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/kunkunsh/kunkun)`

Input:
- URL: `https://github.com/kunkunsh/kunkun`
- format: html

Output:
`<a href="https://deepwiki.com/kunkunsh/kunkun"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>`

## Expected implementation behavior

- No script files to create under this skill.
- Badge generation should be deterministic and idempotent when writing README.
