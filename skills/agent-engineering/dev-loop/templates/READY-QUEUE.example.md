# Ready queue (owner rule 2026-11-03: never leave lanes idle; run runs/refill.sh after every completion)
Format: `- [ ] id | kind | model | what` ; `- [x]` done ; `- [B]` blocked (say by what). Swift items are ONE serial chain.

- [ ] bridge-p0.3-5 | TS+Swift | codex luna / deepseek | after sol-bridge-review3 verdict: P0.3 contract module, P0.4 exporters, P0.5 Swift generator
- [ ] bridge-k2-k5 | Swift (kkrpc) | opus-level or deepseek+sol | policy, async handler, shutdown; serial, after K1 (done)
- [ ] plans-A | planning | sonnet | A3 A4 A5 A7 G2e G4 closed (agent a18c37a79ef31b17b running)
- [ ] plans-B | planning | sonnet | HC4 P9 P9a P10c T2 T3 T4 closed (agent a5cae8bdcfbcac851 running)
- [ ] speech N6-N11 | Swift chain | deepseek | after r12-speech (N2,N3,N5)
- [ ] glaze G2d | Swift | deepseek | write after plans-A
- [ ] cu-readiness | read-only review | free model | tsk_cu_kk_readiness; blocked by M1 owner gates
- [B] bridge-p0.1 | TS | free | blocked: pnpm-lock.yaml has another session's uncommitted hunk
- [B] sd-install | owner | - | install dist/service-dashboard-kunkun-0.1.0.tgz in Kunkun.app
- [B] sd4-sd5 | design | - | held: needs safety redesign + re-review
