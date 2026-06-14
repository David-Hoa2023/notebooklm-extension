# Project Memory — Evolutionary Coding Agent

Last updated: 2026-06-14 (evening). Living record of audits, Phase 5 hardening, Phase 6 evidence, and verification status.

---

## Session log (June 14, 2026 — evening)

### What was accomplished

1. **Phase 5 Hardening & Phase 6 Evidence milestone closed** — Oracle synthesis hardened, governors/regression wired, dashboard split into keyword vs skill-backed coverage, project committed to git (`70e0cc9` init + `3059112` docs/screenshot).

2. **Forced active exploration E2E verified** — Temporarily set `epsilon: 1.0` and `min_epsilon: 1.0` in `config.yaml` (restored to `0.35` / `0.1` after run) so every policy decision selected explore mode (not exploit-only).

3. **Oracle validation gates exercised live**:
   - 12 tasks proposed (`task_proposed`)
   - 9 `oracle_validated`, 3 `oracle_rejected` → **75% oracle validation rate**
   - Rejection reasons in trace: 2× missing expected function name (`params_to_add_update`), 1× syntax error in `test_code` (no live `pytest` rejection in this run; pytest ban covered by unit tests)

4. **Self-proposed execution** — 9 `explore_proposed` runs executed in Docker (`execution_mode: docker`), **100% passed (9/9)**:
   - Seed 42: 2/2
   - Seed 43: 4/4
   - Seed 44: 3/3
   - Sample IDs: `EXP_091D450D`, `EXP_CD13BC42`, `EXP_BBD1A10D`, `EXP_66108722`, `EXP_8E4FB50C`, `EXP_6D2407DE`, `EXP_DB0533E6`, `EXP_D1CE4A0A`, `EXP_E51E4B28`

5. **Git hygiene** — `.gitignore` added; 49 project files committed; `Evolutionary-Coding-Agent/` working tree clean for tracked files.

6. **Tests** — **24/24 passed** (`pytest` ~25–43s).

### Verified E2E metrics (`calculate_metrics()`)

| Metric | Value | Detail |
|--------|-------|--------|
| Oracle validation rate | **75%** | 9 validated, 3 rejected |
| Self-proposed success | **100%** | 9 passed / 9 executed (`explore_proposed` only) |
| Keyword coverage | **100%** | 10/10 `CAPABILITY_TAXONOMY` caps (heuristic) |
| Skill-backed coverage | **80%** | 8/10 caps (verified active skills only) |
| Skill-backed gaps | **`json_parsing`, `testing`** | Not `string_parsing` — confirm from live `skill_gap_analyzer` |
| PG (mean) | **+0.038** | Unchanged from `run-all` benchmark |
| SG (mean) | **-0.813** | Memory interference; unchanged |
| p-value | **0.110** | Not significant at α=0.05; exploration tasks do not alter baseline/second-pass paired t-test |

### Interpretation caveats

- **12 proposed ≠ 12 executed** — 3 oracles rejected before pipeline run; report as 12 proposed → 9 executed.
- **Keyword 100% ≠ verified mastery** — use skill-backed column (80%) for honest capability assessment.
- **p-value unchanged** — improving significance requires `run-all` over ≥6 seeds (e.g. 42–47), not more explore tasks alone.
- **Prior smoke run archived** — earlier n=6 run (67% success, 2 pytest runtime failures) superseded by forced-explore verification.

### Next steps (priority)

1. **Phase 6 statistical significance**: Run `run-all` with seeds `[42..47]` to target p < 0.05 on PG/SG.
2. **Close skill-backed gaps**: Target `json_parsing` and `testing` with verified active skills.
3. **Sync `walkthrough.md` gap list**: Update skill-backed gaps from `string_parsing` → `json_parsing` to match live metrics.

---

## Historical Audit (June 14, 2026 — morning) — Archived

Early June 14 session before forced explore:

| Item | Value |
|------|-------|
| Self-proposed tasks | 6 (2/seed) |
| Oracle validation | 6 validated, 0 rejected |
| Self-proposed success | 67% (4/6) |
| Failures | `EXP_7602454C`, `EXP_17201BA0` (`pytest` sandbox import) |

Superseded by forced-explore run (9/9 passed). Exploit-only intermediate run (12× curriculum, 0 EXP_*) also archived under June 13 audit.

---

## Historical Audit (June 13, 2026) — Archived

Initial claim-state audit before Phase 5 E2E was fixed:

| Claim | Verdict | Evidence |
|-------|---------|----------|
| `refuse_fallback: true` | **Confirmed** | `config.yaml` |
| 11/11 tests | **Superseded** | Now 24/24 |
| 60 runs, 20/seed | **Confirmed** | `run-all` trace (pre-explore) |
| PG +0.038, SG -0.813, p=0.110 | **Confirmed** | `calculate_metrics()` |
| Phase 5 todo | **Superseded** | EL_EXPLORE_001–006 now `done` |

Early Phase 5 run was **exploit-only** (12× `exploit_curriculum`). Fixed via forced `epsilon: 1.0` explore pass.

---

## Phase 5: Active Exploration

Loop: **explore → propose → probe → solve → verify → consolidate**

```
Explore/Exploit policy
    ├─ explore → Curriculum proposer (ZPD) → Oracle synthesis → Environment probe → Pipeline solve → Memory consolidate
    └─ exploit  → Fixed curriculum task ──────────────────────→ Environment probe → Pipeline solve → Memory consolidate
```

### Module: `src/exploration/`

| Task | Module | Status |
|------|--------|--------|
| EL_EXPLORE_001 | `curriculum_proposer.py` | done |
| EL_EXPLORE_002 | `environment_probe.py` | done |
| EL_EXPLORE_003 | `oracle_synthesis.py` | done |
| EL_EXPLORE_004 | `skill_gap_analyzer.py` | done |
| EL_EXPLORE_005 | `explore_exploit_controller.py` | done |
| EL_EXPLORE_006 | `novelty_reward.py` | done |
| Orchestrator | `exploration_loop.py` | done |

### Hardening (Phase 5)

- `oracle_synthesis.py` — static `pytest` ban, function-name enforcement, `_escape_unescaped_newlines`, runtime import-error rejection on known-bad stub
- `EL_OBS_004` — budget governor (`budget_tokens: 200000`, hard stop)
- `EL_MEM_009` — regression re-test (`SUB_001`, `SUB_003`) after each explore batch

### Wiring

- `pipeline.py` — `probe_context` param; `execution_mode` in trace metadata
- `observability.py` — dual coverage panels, stderr logging, per-seed breakdown, paired t-test
- `run.py` — `python run.py explore`
- `config.yaml` — `exploration.epsilon: 0.35`, `max_tasks_per_run: 4`, `budget_tokens: 200000`

### Run command

```powershell
cd D:\AI_project\Evolutionary-Coding-Agent
python run.py explore
```

Requires `GEMINI_API_KEY` and Docker (`refuse_fallback: true`).

To force 100% explore for verification: temporarily set `epsilon: 1.0` and `min_epsilon: 1.0`, then restore defaults.

---

## Test status

- **24/24 passed** — `test_exploration` (12), `test_lifecycle` (3), `test_retrieval` (2), `test_retrieval_rerank` (3), `test_sandbox` (3), `test_validation_integration` (1)
- Run: `.venv\Scripts\python -m pytest` (~25–43s)

---

## Backlog snapshot

**evolutionary-loop.yaml:** 23 done, 0 todo (Phase 5 Hardening + Phase 6 Observability complete)

**Evolutionary-Coding-Agent.yaml:** 24 done, 0 in_progress, 0 todo

---

## Evolutionary loop metrics (run-all, 3 seeds)

- **Plasticity Gain (PG):** +0.038 (mean)
- **Stability Gain (SG):** -0.813 (mean)
- **Generalization Gain (GG):** 0.0 (mean)
- **p-value:** 0.110 (not significant at α=0.05)

---

## Git snapshot

| Commit | Summary |
|--------|---------|
| `70e0cc9` | Initialize project structure (49 files) |
| `3059112` | Walkthrough, memory, dashboard screenshot |
| `3d2b74d` | Dashboard JS syntax fix |

Tracked `Evolutionary-Coding-Agent/` path: clean working tree.

---

## Related docs

- `walkthrough.md` — Phase 5 Hardening & Phase 6 Evidence walkthrough (Vietnamese)
- `doc/walkthrough-evolutionary-loop.md` — Vietnamese Phase 5 walkthrough (earlier)
- `lesson.md` — Issue → Fix → Lesson log (incl. pytest sandbox §8)
- `doc/backlog/evolutionary-loop.yaml` — Active explorer backlog
- `doc/backlog/Evolutionary-Coding-Agent.yaml` — Canonical roadmap
- `logs/trace.jsonl` — Run traces
- `logs/dashboard.html` — Metrics dashboard
- `active_explore_results.png` — Forced-explore dashboard screenshot
