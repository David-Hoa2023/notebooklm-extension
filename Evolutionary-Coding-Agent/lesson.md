# Lesson Log — Evolutionary Coding Agent

This document captures the findings from evaluating the project walkthrough against
`doc/backlog/Evolutionary-Coding-Agent.yaml`. Each entry is structured as
**Issue → Fix → Failure → Success → Lesson** so the team can learn from what was
built, what was claimed, and what still needs work.

Evaluation date: 2026-06-13. Source of truth: the actual source under `src/`,
`config.yaml`, and the real run output in `logs/trace.jsonl` (single seed 42).

---

## 1. Overall progress vs. claims

- **Issue:** The walkthrough claims the pipeline was "fully implemented and successfully
  tested end-to-end," which reads as 100% complete against the backlog. In reality only
  ~60% of the acceptance criteria are truly met; ~30% is built-but-not-integrated or
  not statistically rigorous; ~10% is missing.
- **Fix:** Re-baseline status honestly: keep `done` only where acceptance criteria are
  fully satisfied, mark integration/rigor gaps as `in_progress`, and mark missing work
  as `todo`/`deferred` in the backlog.
- **Failure:** Treating "code exists and the script runs" as equivalent to "acceptance
  criteria met." Several modules are present but never invoked.
- **Success:** All 15 planned source files exist and the full sequence
  (baseline → first pass → second pass → held-out → robustness → dashboard) executes
  without crashing. The architecture maps cleanly onto the backlog epics.
- **Lesson:** "Runs end-to-end" is a smoke test, not a Definition of Done. Verify each
  acceptance criterion against real artifacts (code paths actually taken + logged output),
  not against the narrative.

---

## 2. Single-seed results presented as evolutionary gains

- **Issue:** Headline metrics (e.g. Stability Gain +9.50 on `SUB_001`) come from a single
  run with seed 42. The backlog repeatedly requires `>=3 seeds` with `mean ± std` and a
  significance check (OBS_003, EVAL_000–002).
- **Fix:** Run `seeds=[42, 43, 44]` (the framework already supports it — change the default
  in `run.py`), report `mean ± std` per task, and add a significance check before claiming
  any gain is real.
- **Failure:** `SUB_001` "gain" is an artifact of LLM nondeterminism, not memory:
  baseline failed on a truncated/syntax bug (0.0), first pass failed on a runtime bug (0.0),
  second pass happened to pass (9.5). `SUB_002` failed in all three passes for similar
  stochastic reasons. With one seed at `temperature=0.1`, these swings are within noise.
- **Success:** The metric plumbing is correct — `observability.calculate_metrics()` already
  groups by `(task_id, pass_type)` and averages across seeds, so it is ready for multi-seed
  data with no structural change.
- **Lesson:** With stochastic LLMs, a single run is anecdote, not evidence. Multi-seed
  reporting with variance is the cheapest, highest-leverage fix for credibility.

---

## 3. Lifecycle modules built but not wired in

- **Issue:** `MEM_003` (deduplication) and `MEM_005` (conflict resolution, eviction) exist
  in `src/memory/lifecycle.py` but are **never called**. `memory_engine.add_*` writes
  directly to the DB, bypassing the lifecycle layer entirely.
- **Fix:** Route all writes through `lifecycle_manager`: call `deduplicate_and_merge` and
  `resolve_conflicts` before insert, and `enforce_capacity` after. Add per-namespace dedup
  stats to the trace log.
- **Failure:** The Memory Poisoning test (`ROB_003`) "passed," but resilience came purely
  from the system-prompt framing of memory as reference material — not from the lifecycle
  conflict/decay defense the criteria intended to validate. The test therefore does not
  prove what it claims to.
- **Success:** The lifecycle logic itself is reasonable (LLM-based merge, conflict actions,
  importance×recency eviction) and decay *is* live inside the retrieval scoring path.
- **Lesson:** Dead code that looks complete is worse than missing code — it creates a false
  sense of coverage. A feature isn't done until it's on the execution path and observable
  in logs.

---

## 4. Sandbox isolation not actually exercised

- **Issue:** The walkthrough states code runs "isolated via Docker." The real run used the
  **local subprocess fallback** (trace stderr shows `D:\...\temp_sandbox\run_*.py`), which
  has no resource limits, no network block, and no filesystem isolation.
- **Fix:** Either ensure the Docker daemon is running for evaluation runs, or explicitly
  document that results were produced in the non-isolated fallback. Consider failing loudly
  (or tagging the trace) when the fallback is used during a graded run.
- **Failure:** `INFRA_001`'s core acceptance criteria (isolation, no network, resource
  limits) were not demonstrated by the experiment that produced the reported numbers.
- **Success:** The Docker code path is correctly written (`network_mode="none"`, `mem_limit`,
  `nano_cpus`, polling timeout + kill), and the fallback kept the demo unblocked on a machine
  without Docker.
- **Lesson:** Graceful fallbacks are great for developer velocity but dangerous for claims.
  Record *which* execution mode actually ran, and never let a fallback silently undermine a
  security/isolation acceptance criterion.

---

## 5. Seed/config reproducibility is nominal only

- **Issue:** `config.yaml` declares `seed: 42`, but the seed is only used as a logging label.
  No `random.seed`, no seed forwarded to the LLM; the config has no `version` field.
- **Fix:** Apply the seed (`random.seed`, NumPy seed, and pass through to generation where
  possible), and add a `version` to the config so experiments are traceable.
- **Failure:** "Same seed + config → consistent results" (INFRA_004) cannot currently hold.
- **Success:** Centralized config access exists (`config_instance.get(...)`) and most tunables
  (weights, thresholds, sandbox limits) live in one versionable file.
- **Lesson:** Declaring a seed is not the same as honoring it. Reproducibility must be wired
  through every source of randomness, then verified by re-running.

---

## 6. Retrieval stack missing reranker and measurement

- **Issue:** `INFRA_002` requires a reranker, a config on/off toggle, and a measured `recall@k`.
  The implementation has hybrid dense + BM25 + metadata filters but none of those three.
- **Fix:** Add a rerank step (even a lightweight cross-encoder or LLM rerank), gate it behind
  config, and measure `recall@k` on a small labeled query set — or formally descope the
  reranker in the backlog.
- **Failure:** Retrieval quality is asserted but never quantified.
- **Success:** The hybrid core is solid: cosine similarity normalized to [0,1], FTS5 BM25 with
  query sanitization (including Vietnamese characters), and weighted relevance×importance×recency.
- **Lesson:** "We have retrieval" needs a number attached. Without `recall@k` you can't tell
  improvement from regression.

---

## 7. Missing and partial robustness coverage

- **Issue:** `ROB_004` (negative transfer) has no implementation. `ROB_001`/`ROB_002` ran on a
  single seed, and `ROB_001` measures complex-task score under interference rather than a clean
  SG delta comparison.
- **Fix:** Implement `ROB_004` or set its status to `deferred`. Re-run robustness with
  `>=3 seeds` and report the SG comparison between compositional and naive streams explicitly.
- **Failure:** The robustness epic looks complete in the narrative but is partial in code and
  under-powered statistically.
- **Success:** Naive-stream interference and memory-poisoning harnesses exist, run, and produce
  logged, inspectable results.
- **Lesson:** Stress tests are only meaningful with a quantified comparison and enough seeds to
  separate signal from noise.

---

## Summary scoreboard

| Theme | State |
| :--- | :--- |
| Fully meets acceptance criteria | MEM_001, MEM_002, MEM_006, SKILL_001, SKILL_002, TASK_001, TASK_002, TASK_003, OBS_002 |
| Built but not integrated / not rigorous | INFRA_001, INFRA_002, INFRA_004, MEM_003, MEM_004, MEM_005, SKILL_003, EVAL_000, EVAL_001, EVAL_002, OBS_001, ROB_001, ROB_002, ROB_003 |
| Missing | OBS_003 (multi-seed significance), ROB_004 (negative transfer) |

## Top fixes by leverage

1. Run `>=3 seeds` and report `mean ± std` (unblocks OBS_003 and validates all gains).
2. Wire `lifecycle_manager` (MEM_003 + MEM_005) into the memory write path.
3. Honor the seed and version the config (INFRA_004).
4. Make sandbox execution mode explicit in the trace (INFRA_001).
5. Add reranker + `recall@k`, or descope (INFRA_002).
6. Implement or defer negative-transfer (ROB_004).

**Meta-lesson:** The gap here is not engineering capability — the scaffolding is broad and
well-structured. The gap is *rigor and integration*: closing the distance between
"code that exists" and "criteria that are verifiably met under realistic, repeatable conditions."

---

## 8. Sandbox Runtime Failures (Active Exploration)

- **Issue:** Self-proposed active exploration tasks (such as `EXP_7602454C` and `EXP_17201BA0`) encountered sandbox runtime crashes during solving (`ModuleNotFoundError: No module named 'pytest'`) in the Docker container because the synthesized test suites imported `pytest`, which is not pre-installed in the lightweight `python:3.10-slim` runtime container.
- **Fix:** Enhance `oracle_synthesis.py` to statically scan for and reject `pytest` references in generated tests (both `test_code` and `hidden_test_code`), and reject synthesized oracles that trigger `ModuleNotFoundError` or `ImportError` runtime errors during the known-bad solution verification step.
- **Failure:** The LLM-proposed oracle tests passed syntactic screening but crashed when run inside the sandboxed environment due to unfulfilled library dependencies, bypassing the initial validation gate.
- **Success:** Enforcing standard `unittest` and `assert` statements statically, and catching dynamic import failures on stub runs, successfully isolates dependency issues during oracle validation rather than during pipeline execution.
- **Lesson:** Sandboxed environments have constrained library ecosystems. Verification systems must prove test harness runnability under exact sandbox conditions before assigning them as grading baselines.

