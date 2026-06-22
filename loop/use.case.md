# Use Cases & User Stories - STORM Multi-Perspective Verify Loop

This document presents concrete user stories and scenarios for the Stanford STORM + Nav Toor self-verifying research loop. Two real E2E runs have validated the pipeline on live search and OpenRouter LLMs.

---

## At-a-Glance: Pain Points vs. STORM Solutions

| Traditional AI Research Pain Point | How STORM Option B Solves It |
| :--- | :--- |
| **The hype bubble & bias**: AI summaries reiterate marketing fluff, missing engineering constraints or skeptical perspectives. | **Multi-perspective scan (P1)**: Enforces distinct roles (Practitioner, Academic, Skeptic, Economist, Historian) with config-driven `required_perspectives`. |
| **Contradictory and unresolved claims**: Labs claim readiness while factories claim failure; AI averages them into vague prose. | **Contradiction mapping (P2)**: Surfaces explicit clashes; minimum clash count enforced by schema and deterministic verify. |
| **Ghost or broken citations**: Hallucinated URLs or dead pages undermine credibility. | **Citation verify gate**: Live HTTP fetch per citation; unreachable URLs trigger self-correction. Blocked reference sites use curated mock excerpts (documented trade-off). |
| **Linear cascading errors**: Early-stage mistakes propagate unchecked into the final report. | **Cascading resets**: Failed upstream stage resets all downstream stages to `pending` for the topic. |
| **Expensive verifier loops**: Structural bugs (missing keys, short word count) burn LLM verifier tokens. | **Layered pre-checks**: Pydantic pre-verify + `run_deterministic_verify_checks()` fail fast before URL fetch or OpenRouter calls. |
| **Upstream-to-final drift**: Final articles diverge from research findings and contradictions, or drift to generic topics/homonyms. | **Briefing-First mode (P5)**: Re-generates article using synthesis briefing and Allowed Citation URLs pool, verified by deterministic perspective coverage, term overlap, and domain blocklists. |
| **Silent file/path mismatches**: Generator writes artifacts the orchestrator never reads. | **Directory sync + early failure**: `sync_storm_files()` copies STORM output into canonical slug folders; missing `storm_gen_article.txt` raises `FileNotFoundError` instead of parsing empty content. |
| **Fragile CI without full STORM install**: Import errors break tests and tooling. | **Adapter placeholders**: `storm_adapter.py` provides fallback classes when `knowledge-storm` is absent; mock mode runs fully offline. |

---

## Validated Real Runs

| Topic | Run ID | Outcome | Peer review | Note |
|-------|--------|---------|-------------|------|
| loop engineering in AI in 2026 (pre-UCF) | `608a1d91-7205-4941-a30e-c4cd07dfa125` | 6/6 stages passed | C+ | Pre-fidelity drift run |
| loop engineering in AI in 2026 (post-UCF) | `24d5cafd-8af8-450e-a3f5-5365695813cd` | Escalated (10 attempts) | N/A | Caught drift, word count, and format failures |
| Solid-state battery commercialization (pre-UCF) | `1bc3e040-6d2d-4d52-ace8-f1f3d91f9702` | 6/6 stages passed | A- | Baseline run |
| Solid-state battery commercialization (post-UCF) | `06613612-d320-4e15-91ba-16b7e390f038` | Escalated (10 attempts) | N/A | Escalated on missing perspective keyword checks |

Artifacts: `artifacts/final/{run_id}.json` (now augmented with `metadata.fidelity` detailing upstream ratios, covered perspectives, and mock excerpt counts).

---

## User Stories

### Story 1: The battery venture capital analyst (the hype bubble)

- **Persona**: Marcus, principal battery tech analyst at a cleantech VC.
- **Pain point**: One-shot AI summaries return optimistic marketing copy claiming "production is 1 year away." Marcus misses dendrite issues, manufacturing yield limits, and historical adoption curves.
- **STORM workflow**:
  1. Marcus sets topic `"Solid-state battery commercialization"` in `loop.config.real_second.yaml`.
  2. Runs `python -m loop.run --config loop.config.real_second.yaml` with `OPENROUTER_API_KEY` in `.env`.
  3. **Perspectives** stage runs a 5-role scan (Practitioner, Academic, Skeptic, Economist, Historian).
  4. **Contradictions** surfaces clashes between lab readiness claims and manufacturing realities.
  5. **Synthesis → article → peer review** produce a cited, verified report.
- **Validated outcome** (Run `1bc3e040-...`): Final report covers Toyota, QuantumScape, Solid Power, sulfide/oxide/polymer electrolytes, manufacturing scalability, and market projections. Peer review grade **A-**, confidence 8/10.

---

### Story 2: The EV product manager (contradictory briefs)

- **Persona**: Sarah, lead product manager for battery pack assemblies.
- **Pain point**: Research asserts silicon-anode readiness; manufacturing asserts yield-killing expansion. Generic AI averages these into useless summaries.
- **STORM workflow**:
  1. Sarah configures an internal topic in a STORM config YAML.
  2. **Contradictions (P2)** produces an explicit clash map, e.g. academic density breakthroughs vs. practitioner cell-line cracking.
  3. **Synthesis (P3)** aggregates contradictions into key findings with reliability scores and an actionable insight.
  4. If perspectives fail verification, **cascade reset** clears outline, synthesis, article, and peer review so downstream work cannot proceed on stale inputs.
  5. During article verify, deterministic checkers enforce that at least 2 clashes from the contradiction map are explicitly reflected in the content.
- **Outcome**: A contradiction map artifact (`contradiction_map.json`) and research briefing (`research_briefing.json`) suitable for engineering decisions, with verified contradiction coverage in the final report.

---

### Story 3: The energy policy advisor (citation integrity)

- **Persona**: David, government policy advisor drafting EV tariff guidelines.
- **Pain point**: Hallucinated or dead citation links destroy policy credibility.
- **STORM workflow**:
  1. David runs the loop on `"Chinese EV export tariffs impact"` (see `loop.config.storm.example.yaml` for mock CI, or a custom real config).
  2. **Article stage** generates structured JSON with `citation_references`.
  3. **Verify gate** fetches every citation URL; unreachable links fail with `citation_unreachable` and trigger retry with rejection feedback.
  4. Deterministic pre-checks reject articles below `min_word_count` or with unmapped citation indices **before** the LLM verifier runs.
  5. Upstream citation ratio checking enforces that at least 50% of the cited URLs originate from the upstreamcollected sources, failing-fast on low-value dictionary URLs.
- **Outcome**: Reports where every citation index maps to a declared URL, passes fetch validation, and conforms to the collected upstream research corpus (with documented mock-excerpt fallback for anti-bot dictionary sites).

---

### Story 4: The platform engineer (reliable orchestration)

- **Persona**: Alex, engineer operating the verify-gate loop in production.
- **Pain point**: STORM writes to `Solid-state_battery_commercialization/` while the orchestrator reads `solidstate_battery_commercialization/`. Missing files cause the parser to hallucinate off-topic articles; the LLM verifier rejects them 70+ times.
- **STORM workflow**:
  1. Alex enables `sync_storm_files()` (built into article/peer-review stages after STORM runs).
  2. If `storm_gen_article.txt` is still missing, the stage raises `FileNotFoundError` → orchestrator marks `pre_failed` immediately instead of entering a semantic rejection loop.
  3. Empty DuckDuckGo results no longer crash scikit-learn cosine similarity (adapter monkey-patch).
  4. Empty `url_to_info.json` triggers citation harvest from `perspectives.json`.
- **Validated outcome**: Solid-state battery run completed after fixes; article passed on the first attempt post-sync (iteration 73).

---

### Story 5: The meta-researcher (loop engineering in AI)

- **Persona**: Jordan, researcher studying autonomous feedback loops in AI systems.
- **Pain point**: Need a structured, multi-stage research artifact on an emerging topic with full verify-gate traceability.
- **STORM workflow**:
  1. Topic: `"loop engineering in AI in 2026"` via `loop.config.custom.yaml`.
  2. Full 6-stage pipeline with live search; 84 iterations to convergence on baseline.
  3. Peer review flagged conceptual drift (sources described Microsoft Loop and dictionary definitions rather than a formal field).
  4. Post-UCF fix runs enforce a minimum synthesis briefing Jaccard overlap of 0.3 and perspective representation count of 5, triggering early rejections or regenerations to ensure the final report maintains focus.
- **Outcome**: Demonstrates the loop's self-correction and honest peer-review grading. While the pre-fidelity run achieved C+, the post-fidelity pipeline is configured to automatically reject drift and escalate early (capped at 10 article attempts) for human intervention.

---

## Operating Modes

| Mode | Command | When to use |
|------|---------|-------------|
| **EV verify gate** | `python -m loop.run --config loop.config.yaml` | Stock price validation (TSLA, BYD, RIVN) |
| **Mock STORM** | `python -m loop.run --config loop.config.storm.example.yaml --mock-storm` | Offline CI, 18-item multi-topic cycle |
| **Real STORM** | `python -m loop.run --config loop.config.real_second.yaml` | Live search + OpenRouter LLMs |
| **Resume** | `python -m loop.run --config <yaml> --resume <run_id>` | Continue escalated or interrupted runs |

**Requirements for real mode**: `pip install -r requirements-storm.txt`, `OPENROUTER_API_KEY` in `.env`, reload extension after code changes.

---

## Configuration Knobs (`nav_toor.*`)

All thresholds are YAML-driven and enforced in both Pydantic pre-verify and deterministic verify:

- `required_perspectives`, `contradiction_map_min_clashes`, `synthesis_min_findings`
- `peer_review_min_confidence`, `min_word_count`, `min_outline_depth`
- `fidelity.article_mode`: `"briefing_first"` (grounded in synthesis briefing) or `"storm_only"` (raw STORM output).
- `fidelity.article_min_perspective_mentions`: Minimum mentions of each required perspective in article content (default 5).
- `fidelity.citation_upstream_min_ratio`: Minimum ratio of citations matching collected upstream sources (default 0.5).
- `fidelity.synthesis_term_overlap_min`: Minimum Jaccard word overlap with research briefing (default 0.3).
- `fidelity.contradiction_min_reflected`: Minimum clashes from the contradiction map reflected in the article (default 2).
- `fidelity.peer_review_min_grade`: Minimum overall grade threshold (default `"B-"`).
- `fidelity.peer_review_fail_on_missing_perspectives`: Fail review if missing perspectives exist and are indeed absent (default `true`).
- `fidelity.article_max_attempts_before_escalate`: Cap retries on article stage before escalation (default 10).
- `fidelity.force_storm_regen_on_drift`: Delete cached text on drift rejection to force LLM regeneration (default `true`).
- `fidelity.blocked_citation_domains`: List of blocked/low-value reference domains (e.g. dictionaries).

See `loop.config.storm.example.yaml` for a full example.
