# Delegation ledger

Append one row per verified delegated task, newest at the bottom. Keep rows factual. Durations are wall-clock; tokens are subagent tokens when the tool reports them ("free" for opencode).

Outcome is one of `pass`, `pass-after-retry`, `partial` or `fail`. Rework records what a later round or review had to fix.

Projects:
- **kk** = Kunkun v2.1
- **sd** = service-dashboard

| date | project | tool | model/effort | task kind | size | outcome | rework | quality notes | duration | tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-08 | kk | claude | sonnet/medium | UI wiring to a fixed contract (M6) | 2 workers | pass | one slip: branched on error message text, caught by root | clean checks | — | — |
| 2026-10-08 | kk | claude | opus/medium+high | cross-package lane and MCP manager | M6 | pass | none | — | — | — |
| 2026-10-10 | kk | claude | opus | frozen-contract catalog (RS3a), SDK side of a landed contract (R2b) | medium | pass | none | over-tiered: sonnet would have done | — | — |
| 2026-10-10 | kk | opencode | muse-spark-1.3-free | read-only package table | 23 rows | pass | none | output repeats the table twice; use the last | 12 s | free |
| 2026-10-10 | kk | opencode | muse-spark-1.3-free | scoped single-file write | 1 file | pass | none | accurate | 32 s | free |
| 2026-10-10 | kk | opencode | muse-spark-1.3-free | rule-driven doc path rewrite (LANES.md) | 12 paths | pass | none | left out-of-rule cases alone, with reasons | 111 s | free |
| 2026-10-10 | kk | claude | haiku/medium | execute 15-task hand-off plan with full code (C1 ClipboardCore) | 40 files | pass-after-retry | self-stopped at task 7 citing the tier table; skipped a negative control when a tool was refused; dropped logging after resuming | 40/40 files byte-identical, 130/130 tests | — | ~330k |
| 2026-10-10 | kk | claude | sonnet/medium | shared-core extraction from a hand-off plan | large | pass | none | no stops | — | — |
| 2026-10-10 | kk | opencode | muse-spark-1.3-free | lab run with long downloads | — | fail | moved downloads to background shells; the jobs died when `run` exited | prompt now says foreground only | — | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | 4 background runs without stdin redirect | — | fail | hung 3–4 h at 0% CPU, no session created | always `< /dev/null` | — | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | write security/lifecycle spec+plan (Service Dashboard) | large | fail | sol: 17 P1 | not executable | — | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | write native hand-off plans (Shelf, C2) | large | fail | sol: Shelf 9 P1, C2 13 P1 | compiled, and its own tests passed in scratch | — | free |
| 2026-10-11 | kk | claude | opus | write plans (MCP OAuth, PM, Dictation) | large | partial | first sol review: 7 / 13 / 12 P1 | opus did not save review rounds | — | 200–560k each |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | execute reviewed plan batches (x26) | 8 tasks | pass | none | verbatim | — | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | execute Shelf, C2, MCP OAuth plans plus review fixes | large | pass | normal review-fix rounds | transport/SSL errors mid-run, resumed with `-s` | — | free |
| 2026-10-11 | sd | claude | sonnet/high | implement 11 milestone review findings, test first | 13 commits | partial | recheck: 1 P1 + 1 P2 partial; next round introduced 1 new P2 regression; third round PASS | found and fixed an extra leak; honest about one unreproduced claim | 35 min | 306k |
| 2026-10-11 | sd | claude | sonnet/high | recheck fixes (2 then 2) via SendMessage resume | 2+2 commits | pass | see above | resume kept context, so cheap | 5 + 4 min | ~16k + ~10k incremental |
| 2026-10-11 | kk | claude | sonnet/high | implement 10 Dictation review findings | 10 commits | pass | recheck PASS WITH FIXES (2 P2 in the UI fence) | strong RED evidence per item | 25 min | 254k |
| 2026-10-11 | kk | claude | sonnet/high | 2 P2 UI-fence fixes (resume) | 1 commit | pass | none | — | 2.4 min | ~18k incremental |
| 2026-10-11 | kk | claude | sonnet/high | x26 convergence RED R1–R4 (deadlock, custody, shutdown) | 4 commits | pass | none; merged | deadlock test bounded by a deadline, as asked | 7 min | 153k |
| 2026-10-11 | kk | claude | sonnet/high | merge finished React branch, 40 conflicts | 1 merge | pass | none | found the add/add conflicts were identical pilot copies, so the resolution was trivial and correct | 11 min | 166k |
| 2026-10-11 | kk | claude | haiku/medium | Notion status sync, 9 pages | 9 updates | pass-after-retry | first call used URLs instead of dashed UUIDs; self-corrected | verified with SQL afterwards | 1.4 min | 130k |
| 2026-10-11 | kk | claude | haiku/medium | full regression + failure triage (rerun alone) | 519 files | pass | none | correct triage of flakes vs environment failures | 27 min | 85k |
| 2026-10-11 | kk | claude | haiku/medium | React vs Svelte parity + perf rerun | 3 runs | pass | none | pulled medians from JSON when stdout was terse | 4 min | 81k |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 Task 12.1 (verbatim contract task) | 8 files | pass | none | noted test-count drift from the plan honestly | 5 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 Task 12.2 (verbatim) | 3 files | pass | none | recorded RED by moving the file aside (disclosed) | 2 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 RED-2/3/4: judgment, tests not given | 3 commits | pass | none | designed tests, reproduced the reviewer's exact leak, stopped on an out-of-scope gap instead of improvising | 15 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | RED-2 follow-up after a root decision (`-s` resume) | 1 commit | pass | none | stated the missing UI report channel honestly | 5 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | root-cause unhandled ERR_INVALID_STATE (speech) | 1 commit | pass | none | isolated it with scratch tests, explained the cause at file:line, test made to fail on unhandled rejections | 4 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 Task 12.3 (strong tier: pipes, log rotation) + RED-1, RED-5 | 3 commits | pass | none so far | changed 3 test expectations per the new spec; root checked none was loosened; 393/393 suite | 15 min | free |
| 2026-10-11 | kk | codex | gpt-6.1-sol/high | implementation rechecks (x26, SD, Dictation) | 7 reviews | pass | — | found real bugs with in-memory reproductions; no false P1s observed | 10–25 min each | OpenAI |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 Task 12.4 (strong: run controller, load handle) + RED-6 | 2 commits | pass-after-retry | transport drop mid-run, resumed with `-s`; its own edit broke an outage test, which it diagnosed and fixed itself; but the fix was fail-open (dropped app credential patterns during a store outage), caught by root review and sent back | good diagnosis and deviation report; security direction needs root review | 7 + 11 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | fail-safe redactor fix after root review (`-s` resume) | 1 commit | pass | none | caught its own vacuous first test (it would have passed on the buggy code) and rewrote it | 6 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 Task 12.5 (verbatim, app-shell-core) | 1 commit | pass | none | correctly reported an environment-only tsc error (an unbuilt uniview dist) without overreaching | ~6 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 Task 12.7 (strong: Swift native window) | 1 commit | pass | none | all anchors exact; swift build + 23 tests | ~12 min | free |
| 2026-10-11 | kk | opencode | muse-spark-1.3-free | PM12 Task 12.8 (live third-party check + regression) | 1 commit | pass | none | live check passed; marked GUI steps NOT RUN honestly; skipped the STATUS edit because of the prompt's docs ban (prompt conflict, root's fault) | ~14 min | free |
| 2026-10-12 | kk | claude | sonnet/high | write native launcher spec + 14-task full-code plan, self-validated by replay and a live Host | 2 docs, 7.8k lines | pending sol review | — | replayed every task RED→GREEN on a scratch tree; found and fixed 9 defects in its own plan; honest about what needs the GUI | 83 min | 458k |
