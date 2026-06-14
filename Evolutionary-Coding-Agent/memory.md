# Project Memory — Evolutionary Coding Agent

Last updated: 2026-06-14. Living record of audits, Phase 5 work, and verification status.

---

## Session log (June 14, 2026)

### What was accomplished

1. **Phase 5 E2E verified** — `python run.py explore` produces full `explore_proposed` loop (not exploit-only):
   - 6 self-proposed tasks (2 per seed: 42, 43, 44)
   - 6 `oracle_validated`, 0 `oracle_rejected`
   - Trace keys: `pass_type: "exploration"` and `pass_type: "exploration_step"`

2. **`validation_gate.py` restored** — Overwritten by unrelated NotebookLM extension code; reconstructed `ValidationGate` (~270 lines) with AST check, Docker sandbox, LLM judge. `sqlite-utils` installed in `.venv`.

3. **Oracle synthesis fixes** (`oracle_synthesis.py`):
   - Ban `pytest` imports (sandbox uses `python:3.10-slim`)
   - `_escape_unescaped_newlines` for malformed JSON from LLM

4. **Documentation synced to live metrics**:
   - `walkthrough.md` (English)
   - `doc/walkthrough-evolutionary-loop.md` (Vietnamese)
   - `memory.md` — stale June 13 audit table archived under "Historical Audit"

5. **Tests** — **23 collected** (adds `test_validation_integration`; re-run full suite to confirm pass count)

### Verified E2E metrics (`calculate_metrics()`)

| Metric | Value | Detail |
|--------|-------|--------|
| Oracle validation | **100%** | 6 validated, 0 rejected |
| Self-proposed success | **67%** | 4 passed / 6 (`explore_proposed` only) |
| Skill coverage | **100%** | 10/10 `CAPABILITY_TAXONOMY` caps (keyword heuristic) |
| Novelty range | **0.14–0.24** | 6 proposed tasks |

### Per-seed exploration results

| Seed | Task ID | Status | Score |
|------|---------|--------|-------|
| 42 | EXP_A4BAA071 | passed | 10.0 |
| 42 | EXP_7602454C | failed_runtime_error | 0.0 |
| 43 | EXP_C5FBDC9E | passed | 10.0 |
| 43 | EXP_21B1F1A6 | passed | 9.85 |
| 44 | EXP_FC5242A0 | passed | 10.0 |
| 44 | EXP_17201BA0 | failed_runtime_error | 0.0 |

### Doc fix this session

- `walkthrough.md` §Verification corrected: was still claiming 100% self-proposed success; now matches 67%.

### Interpretation caveats

- **100% skill coverage is keyword-based**, not verified mastery — `skill_gap_analyzer` matches patterns in skill names, docstrings, and insights.
- **n=6 is a smoke test**, not a statistical benchmark — do not treat 67% as stable until n≥12+ across seeds.
- **2 runtime failures** (`EXP_7602454C`, `EXP_17201BA0`) — mine stderr from `trace.jsonl` for root cause.

### Next steps (priority)

1. Diagnose 2 `failed_runtime_error` tasks; add lessons to `lesson.md`.
2. Re-run explore with `max_tasks_per_run: 4` for larger sample.
3. Implement **`EL_OBS_004`** — cost & budget governor (hard stop on `budget_tokens`).
4. Implement **`EL_MEM_009`** — regression re-test of solved tasks after each batch.
5. Split dashboard coverage into **keyword coverage** vs **skill-backed coverage**.
6. Add unit tests for `_escape_unescaped_newlines` and oracle `pytest` rejection.

---

## Historical Audit (June 13, 2026) — Archived

Initial claim-state audit before Phase 5 E2E was fixed:

| Claim | Verdict | Evidence |
|-------|---------|----------|
| `refuse_fallback: true` | **Confirmed** | `config.yaml` |
| 11/11 tests | **Superseded** | Now 19/19 |
| 60 runs, 20/seed | **Confirmed** | `run-all` trace (pre-explore) |
| PG +0.038, SG -0.813, p=0.110 | **Confirmed** | `calculate_metrics()` |
| Phase 5 todo | **Superseded** | EL_EXPLORE_001–006 now `done` |

Early Phase 5 run was **exploit-only** (12× `exploit_curriculum`, 6 oracle rejections). Fixed in later session.

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

### Wiring

- `pipeline.py` — `probe_context` param; `execution_mode` in trace metadata
- `observability.py` — `log_exploration_step()`; Phase 5 dashboard section
- `run.py` — `python run.py explore`
- `config.yaml` — `exploration.epsilon: 0.35`, `max_tasks_per_run: 2`, `budget_tokens: 200000`

### Run command

```powershell
cd D:\AI_project\Evolutionary-Coding-Agent
python run.py explore
```

Requires `GEMINI_API_KEY` and Docker (`refuse_fallback: true`).

---

## Test status

- **23 collected** — `test_exploration` (8), `test_lifecycle` (4), `test_retrieval` (2), `test_retrieval_rerank` (3), `test_sandbox` (3), `test_validation_integration` (1+)
- Run: `.venv\Scripts\python -m pytest` (~30–40s)

---

## Backlog snapshot

**evolutionary-loop.yaml:** 21 done, 2 todo (`EL_MEM_009`, `EL_OBS_004`)

**Evolutionary-Coding-Agent.yaml:** 24 done, 0 in_progress, 0 todo

---

## Evolutionary loop metrics (run-all, 3 seeds)

- **Plasticity Gain (PG):** +0.038 (mean)
- **Stability Gain (SG):** -0.813 (mean)
- **Generalization Gain (GG):** 0.0 (mean)
- **p-value:** 0.110 (not significant at α=0.05)

---

## Related docs

- `walkthrough.md` — English Phase 5 walkthrough
- `doc/walkthrough-evolutionary-loop.md` — Vietnamese walkthrough
- `lesson.md` — Issue → Fix → Lesson log
- `doc/backlog/evolutionary-loop.yaml` — Active explorer backlog
- `doc/backlog/Evolutionary-Coding-Agent.yaml` — Canonical roadmap
- `logs/trace.jsonl` — Run traces
- `logs/dashboard.html` — Metrics dashboard
