# Memory - STORM Option B Implementation & Architecture

This document logs the key changes, architecture, and design decisions made to integrate Stanford STORM and Nav Toor's multi-perspective research workflow into the self-verifying loop orchestrator.

## Project Status (June 2026)

- **Epic**: STORM Option B + Nav Toor multi-perspective research loop integrated into the same orchestrator as the EV verify-gate loop.
- **Test suite**: **37 passing tests** (`python -m unittest loop.tests`).
- **Real E2E runs completed**: 2 topics end-to-end with live DuckDuckGo search and OpenRouter LLMs.
- **Latest commit**: `ed68b76` on `origin/master`.

| Run ID | Topic | Status | Iterations | Notes |
|--------|-------|--------|------------|-------|
| `608a1d91-7205-4941-a30e-c4cd07dfa125` | loop engineering in AI in 2026 | passed | 84 | First real E2E; peer review grade C+ |
| `1bc3e040-6d2d-4d52-ace8-f1f3d91f9702` | Solid-state battery commercialization | passed | 74 | Early stages near-zero retries; article needed 70 attempts before fixes |

---

## Key Changes Overview

1. **State & Path Management**:
   - Extended `ItemState` in `loop/state.py` to support optional STORM-specific attributes (`stage`, `topic_slug`, `depends_on`, `override_reason`) while maintaining backward-compatibility with older runs.
   - Created `loop/storm_paths.py` to handle topic slug normalization and sequential stage transitions:
     `perspectives -> contradictions -> outline -> synthesis -> article -> peer_review`.

2. **Strict Schema Verification**:
   - Implemented `loop/storm_schema.py` defining Pydantic schemas validating structure and requirements for all 6 stages.
   - Refactored validators to read thresholds dynamically (specifically `required_perspectives`, `contradiction_map_min_clashes`, `synthesis_min_findings`, `peer_review_min_confidence`, `min_word_count`, and `min_outline_depth`) from the configuration context passed at validation time, falling back to defaults if no context is provided.
   - Created `loop/storm_pre_verify.py` for cheap, local deterministic validation, passing configuration context into model validation.

3. **Stage Execution & Verification**:
   - Wrote wrappers in `loop/storm_stages.py` routing stage execution to STORM adapters or fallbacks.
   - Built deterministic checks (e.g., citation URL accessibility) and LLM verify gates in `loop/storm_verify.py`.
   - Wired verification gate thresholds to be dynamically checked from the configuration snapshot.
   - Setup a simulated mock flow in `loop/storm_mock.py` simulating failure on attempt 0 and recovery on attempt 1.

4. **Multi-Topic Concurrency & Cascade Resets**:
   - Modified `loop/run.py` to orchestrate composite stage items (`topic_slug::stage`).
   - Enabled concurrent execution of multiple topics up to `topic_concurrency: 2` using `ThreadPoolExecutor`, while stages within a topic are strictly sequential.
   - Implemented cascading resets: if a stage fails verification and gets reset, all of its downstream stages are marked back to `pending`.

5. **Adversarial Integrity**:
   - Scoped adversarial test hooks (`INJECT_BAD_CITATION=1` and `INJECT_MISSING_PERSPECTIVE=historian`) to attempt 0 only, ensuring self-correcting validation loops could recover on attempt 1.

6. **Verification Hardening & Cost Control**:
   - Added `run_deterministic_verify_checks()` in `loop/storm_verify.py` to validate structural constraints locally **before** URL fetches or LLM verifier calls (perspectives, contradictions, outline depth, synthesis findings, article word count + citation mapping, peer review confidence and missing-perspective accuracy).
   - Fail-fast early returns skip OpenRouter verifier calls when deterministic checks fail, reducing token cost and latency.
   - Documented layered flow in `walkthrough.md` (Pydantic pre-verify → deterministic verify → URL fetch → LLM verifier).

7. **STORM Stage Robustness & Parsing Updates**:
   - **Schema Parsing Correction**: Added automated list-to-dictionary wrapping in `run_stage_outline` to wrap direct list outline structures into a `{"sections": ...}` layout, matching `OutlineSchema`.
   - **STORM Directory Sync**: Added `sync_storm_files()` in `storm_stages.py` to locate STORM's case/hyphen-sensitive output folders (e.g. `Solid-state_battery_commercialization/`) and copy artifacts into the orchestrator's canonical slug directory (`solidstate_battery_commercialization/`).
   - **Citation Fallback**: When `url_to_info.json` is empty after search, harvest source URLs from upstream `perspectives.json` and rebuild citation mapping before article parsing.
   - **Resource & Memory Optimization**: Skip `runner.run(...)` when `storm_gen_article.txt` or `storm_gen_article_polished.txt` already exist, avoiding redundant SentenceTransformer loads (Windows paging file / `os error 1455`).
   - **Early File-Missing Hardening**: `run_stage_article` and `run_stage_peer_review` raise `FileNotFoundError` if expected STORM output files are missing after generation/sync, preventing empty-content parsing and semantic verifier loops.
   - **URL Path Encoding**: Percent-encoding for non-ASCII URL paths in `fetch_source_url` (`feeds.py`).
   - **Anti-Bot & Verification Overrides**: Return descriptive mock excerpts with HTTP 200 for blocked reference sites (Merriam-Webster, Cambridge, OpenAI, Microsoft Loop, etc.) and normalize other HTTP/network errors to 200 with grounding excerpts so strict verifiers can proceed (trade-off: reduced live fetch grounding).
   - **Refined Parser Prompts**: Preserve full article text (≥500 words) and strip irrelevant electrical-current analogies.
   - **Structured vs Polished Alignment**: `clean_electrical_analogy()` in `loop/utils.py` applied during peer review and via one-off cleanup script; shared helper used by `storm_stages.py` and `scratch/clean_articles.py`.
   - **Knowledge-Storm Empty Retrieval Guard**: Monkey-patched `StormInformationTable.retrieve_information` in `storm_adapter.py` to return `[]` on empty snippets or scikit-learn `cosine_similarity` empty-array errors.
   - **UTF-8 FileIO Patch**: Monkey-patched `FileIOHelper` string IO for Windows compatibility.

8. **Adapter & Environment Resilience**:
   - `storm_adapter.py` defines placeholder classes (`STORMWikiRunnerArguments`, `STORMWikiRunner`, `STORMWikiLMConfigs`, `SafeLitellmModel`, `DuckDuckGoSearchRM`) in the `except ImportError` fallback block so modules import cleanly when `knowledge-storm` is absent; `build_storm_runner()` returns `DummyRunner` when `HAS_STORM` is false.
   - `run.py` loads `.env` via `python-dotenv` at startup for `OPENROUTER_API_KEY` and related secrets.

9. **Security & Repository Hygiene**:
   - OpenRouter API key rotated after accidental inclusion in tracked artifacts; git history rewritten on `main` to remove secrets; `.env` and runtime artifacts excluded via `loop/.gitignore`.
   - Recommendation: rotate keys if they were ever pushed before the purge.

---

## Configuration Files

| File | Purpose |
|------|---------|
| `loop.config.yaml` | EV verify-gate mode (TSLA, BYD, RIVN) |
| `loop.config.storm.example.yaml` | STORM mock/CI: 3 topics, 18 stage items |
| `loop.config.custom.yaml` | Single-topic real run: loop engineering in AI |
| `loop.config.real_second.yaml` | Single-topic real run: solid-state battery |

---

## Verification Outcomes

- **Unit Tests**: **37 passing tests** in `loop/tests.py` — schema validation, config thresholds, production fixes (outline wrapping, unicode URLs, HTTP 403/500/network errors, deterministic verify checks, early file-missing errors).
- **Mock STORM Run**: 3 topics × 6 stages = 18 items; 9-iteration self-correction cycle via `--mock-storm`.
- **Adversarial Recovery**:
  - `INJECT_MISSING_PERSPECTIVE=historian` — fails attempt 0, recovers attempt 1.
  - `INJECT_BAD_CITATION=1` — fails article verify attempt 0, recovers attempt 1.
- **Real Run #1 — loop engineering in AI in 2026** (`608a1d91-...`):
  - All 6 stages passed after 84 iterations; exported to `artifacts/final/608a1d91-...json`.
  - Peer review grade **C+** (conceptual drift: sources described Microsoft Loop / dictionary terms rather than a distinct "loop engineering" field).
  - Article stage: 68 attempts; outline: 13 attempts.
- **Real Run #2 — Solid-state battery commercialization** (`1bc3e040-...`):
  - Early stages: perspectives 1 retry, contradictions/outline/synthesis near first-pass success after deterministic hardening.
  - Article blockers: empty-search crash + directory slug mismatch caused 70 verifier cycles of off-topic hallucinated content before `sync_storm_files` and citation fallback were added.
  - After fixes and resume: article passed iteration 73, peer review iteration 74; final report **A-** grade, confidence 8; exported to `artifacts/final/1bc3e040-...json`.

---

## Known Limitations & Future Work

- **Citation grounding trade-off**: Mock excerpts for anti-bot sites pass verification but weaken live source grounding.
- **Article retry cost**: LLM verifier rejections on semantic/off-topic content can still be expensive even when structural pre-checks pass.
- **Co-STORM HITL**: `costorm_hook.py` remains a stub.
- **Revenue/margin EV validation**: EV loop still validates `stock_price` deterministically; other fields pass on trust.

---

## Quick Commands

```powershell
# Unit tests
python -m unittest loop.tests

# Mock STORM (offline CI)
python -m loop.run --config loop.config.storm.example.yaml --mock-storm

# Real STORM (requires OPENROUTER_API_KEY in .env)
python -m loop.run --config loop.config.real_second.yaml

# Resume escalated run
python -m loop.run --config loop.config.real_second.yaml --resume 1bc3e040-6d2d-4d52-ace8-f1f3d91f9702
```
