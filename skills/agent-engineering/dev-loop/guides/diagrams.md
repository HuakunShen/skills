# Diagrams

## The loop

```mermaid
flowchart TD
    W["Owner wish<br/>(Notion / GitHub Projects / local file / chat)"] --> I[0 intent: write it down in the owner's words]
    I --> R[1 record: decision log + register + backlog]
    R --> D{New or risky?}
    D -- no --> S
    D -- yes --> DS[2 design: look first, plan, ADR]
    DS --> DR[3 design review<br/>independent reviewer, per config]
    DR -- P1 open --> DS
    DR -- pass --> S[4 slice into lanes<br/>branch + worktree + owner + write set]
    S --> L1[lane A]
    S --> L2[lane B]
    S --> L3[lane C]
    L1 & L2 & L3 --> IM[5 implement: RED, GREEN, negative control]
    IM --> V[6 verify for real<br/>say what was not verified]
    V --> CR{Risky change?}
    CR -- yes --> RV[7 code review<br/>fix P0/P1, round limit]
    RV --> M
    CR -- no --> M[8 merge: local, no push]
    M --> DP[9 deploy / install<br/>only if owner allows]
    DP --> C[10 close out: register, logs, follow-ups, cleanup]
    C --> RF((11 reflect<br/>every 30 min))
    RF -. new work found .-> I
```

## Intake: every chat request is captured first

```mermaid
flowchart TD
    MSG["Owner message<br/>(bug / feature / tweak)"] --> CAP["1 Append row to INTAKE.md<br/>W-### + owner's words, status: captured"]
    CAP --> BC["2 Board check: what is running?<br/>register + non-done intake rows"]
    BC --> T{3 Triage size}
    T -- "small, obvious" --> P["patch: PATCHES.md list<br/>no issue, no branch"]
    T -- "needs design / risky / big" --> L["lane: branch + worktree + register row<br/>(PR / issue only if project uses them)"]
    T -- "information" --> Q[answer, log if it changes plans]
    P --> B[batch into next worker brief<br/>or fold into a lane touching same files]
    L --> D[delegate to subagent / CLI worker<br/>in parallel with existing lanes]
    B --> DONE
    D --> DONE[merge, then intake row = done + commit]
    Q --> DONE
    BC -. "reply: logged W-014, still running A, B" .-> MSG
    RF((reflect every 30 min)) -. "any row still captured or without a live lane = lost work" .-> CAP
```

## Who does what

```mermaid
flowchart LR
    O[Owner] -- wishes, decisions, acceptance --> M[Main agent session<br/>one per project]
    M -- brief --> A[Subagent]
    M -- brief --> B[Agent CLI<br/>codex / opencode / ...]
    M -- brief --> C[Other worker]
    A & B & C -- report once --> M
    M -- plan / code --> RV[Independent reviewer]
    RV -- verdict P0-P3 --> M
    M -- reads/writes --> F[(Files: register,<br/>decisions, plans)]
    F -. read after compaction .-> M
    CFG[(Config + instruction sources<br/>Notion / Doc / S3 / file)] -. patches stages .-> M
```

## Where things live

```text
 Owner's chat / AI ──► INBOX (Notion DB | GitHub Projects | docs/backlog/INDEX.md)
                              │ accepted
                              ▼
  RESEARCH STORE ◄─ symlink ─ references/   (not in git)    docs/research/  (public-safe evidence)
  (Google Drive: discussions,                                      │
   concept pictures)                                                ▼
                         docs/decisions/  ──►  docs/plans/ + docs/adr/  ──►  code lanes
                                 │                    │                          │
                                 └────────────────────┴───► WORK-REGISTER.md ◄──┘
                                                      review-followups.md, .journal/
```
