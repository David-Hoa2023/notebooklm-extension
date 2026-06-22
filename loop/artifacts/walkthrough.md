# Walkthrough - Autonomous Verify Gate

This document serves as the developer walkthrough for the autonomous self-verifying loop implementation.

## File Organization & Package Layout

The implementation is located under the standard `loop/` package directory:
- **[__init__.py](file:///d:/AI_project/loop/loop/__init__.py)**: Standard package identifier.
- **[state.py](file:///d:/AI_project/loop/loop/state.py)**: Defines `LoopState` and `ItemState` Pydantic models mapping to the epic design schema in `verify-gate-backlog.yaml`. State persistence is handled atomically using temporary write + replace.
- **[pre_verify.py](file:///d:/AI_project/loop/loop/pre_verify.py)**: Implements deterministic, cheap validations (e.g. invalid URL formats, sentinel values, empty metrics) using Pydantic validation before querying LLMs. It validates the aligned schema containing the `stock_price` field.
- **[feeds.py](file:///d:/AI_project/loop/loop/feeds.py)**: Real live market connectors. Connects to the public Binance API (cryptocurrency rates) and Yahoo Finance chart API (live stock prices) without requiring keys.
- **[run.py](file:///d:/AI_project/loop/loop/run.py)**: Orchestrates the Plan -> Execute -> Verify -> Repeat control loop, managing state transitions, escalation reporting, and resume capabilities.
- **[tests.py](file:///d:/AI_project/loop/loop/tests.py)**: Exposes a suite of automated unit tests covering pre-verifier validation logic, state IO, and feed connectors.
- **[verify_gate_system.md](file:///d:/AI_project/loop/prompts/verify_gate_system.md)**: Extracted GLM-5.2 verifier system prompt detailing requirements, stock price verification checklist, and JSON output structure.
- **[loop.config.yaml](file:///d:/AI_project/loop/loop.config.yaml)**: Configuration file detailing default models, retry thresholds, and items list.

---

## Technical Feeds & Verification Flow

### API Connectors
Real live feed APIs are implemented under `loop/feeds.py`:
1. **Yahoo Finance**: Fetches stock prices dynamically from `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}`.
2. **Binance**: Fetches stablecoin conversion rates from `https://api.binance.com/api/v3/ticker/price?symbol={symbol}`.

### Verification Circuit
- **Deterministic Pre-Gate**: Items fail with code `invalid_<field>` if they lack fields, exceed range checks, or use placeholder strings.
- **LLM Verifier Gate**: Items that pass the pre-gate are checked by GLM-5.2 against real-time API snapshots. It verifies that the generated `stock_price` matches the Yahoo Finance stock price.
- **Rejection Routing**: Failed items increment attempts, save their last rejection feedback, and get re-routed to the executor swarm with the feedback appended for self-correction.

---

## Escalation and Resume Support

1. **Escalation**: If the loop exceeds `max_iterations`, the status becomes `escalated` and the orchestrator outputs a markdown report at `artifacts/escalation/{run_id}.md` detailing every failure, attempt history, and last rejection reason.
2. **Resume & Override**:
   - Resuming is supported via `python -m loop.run --resume <run_id>`.
   - Resume mode detects escalated runs, resets status to `running`, and extends `max_iterations` to allow further corrections.
   - Humans can manually mark items as `passed` in `STATE.yaml` and resume the run.

---

## Test Verification

All modules have been validated via unit tests and automated runs:

### 1. Automated Unit Tests
To run unit tests:
```powershell
python -m unittest loop.tests
```
Output:
```text
Ran 14 tests in 0.026s
OK
```

### 2. Integration Mock Verification Loop
To run the mock loop test showing the full correction cycle:
```powershell
python -m loop.run --mock
```
The cycle validates:
- **Iteration 1**: TSLA fails URL pre-verify, BYD fails margin pre-verify, RIVN passes pre-verify but fails verifier check.
- **Iteration 2**: TSLA and BYD pass pre-verify; TSLA fails verifier check (stock price mismatch), BYD/RIVN pass verifier check.
- **Iteration 3**: TSLA passes verifier check; active rejections drops to 0; loop exits successfully.
- **Outputs**: Generates `STATE.yaml`, combined final report at `artifacts/final/{run_id}.json`, and distilled observations at `memory/distilled_guidelines.md`.

### 3. End-to-End Real-Mode Verification Loop (Adversarial & Self-Correcting Run)

We executed a real-mode adversarial verification run (Run ID: `8bcf9780-a1c3-47fa-8e0f-0f1b65d2527a`) utilizing `moonshotai/kimi-k2.6` as the executor swarm and `z-ai/glm-5.2` as the verifier on OpenRouter.

#### Adversarial Injection Configuration
To prove the adversarial check:
- We set `INJECT_WRONG_PRICE=1` as an environment variable.
- For `attempt == 0`, `item_id == "TSLA"` was injected with a deliberately wrong reference hint: `"stock price is 9999.99 USD"`.
- This forced the executor to generate a data entry with `stock_price: 9999.99` for TSLA.

#### Execution Timeline and Self-Correction
- **Iteration 1**:
  - **TSLA**: Generated `stock_price: 9999.99`. The `z-ai/glm-5.2` verifier successfully caught this mismatch against the live stock price of `400.49` USD, rejecting it with a clear, descriptive reason. TSLA transitioned to `verify_failed`.
  - **BYD**: FAILED schema pre-verification (attempt 0 used a placeholder source URL).
  - **RIVN**: FAILED executor generation (truncated API output).
- **Iteration 2**:
  - **TSLA**: Resumed with the verifier rejection feedback in the prompt. The executor corrected the stock price to `400.15` USD (within 1% tolerance of `400.49`). The verifier passed TSLA.
  - **RIVN**: Corrected its generation schema and stock price to `16.52` USD, passing verifier gate on attempt 2.
  - **BYD**: FAILED verifier check (attempt 2 generated stock price `57.8` vs live snapshot `84.68`, over 30% mismatch).
- **Iteration 3**:
  - **BYD**: FAILED executor generation (attempt 3 returned invalid JSON containing unquoted keys, raising an "Extra data" error).
- **Iteration 4**:
  - **BYD**: Resumed and generated stock price `25.5` which still mismatched the live `84.68` and was failed by the verifier (attempt 4).
- **Iteration 5**:
  - **BYD**: Resumed, corrected the stock price to `84.68` based on the verifier feedback, and successfully passed verification!
- **Completion**: The run terminated successfully at iteration 5 with 0 active rejections. The final combined report was written to `artifacts/final/8bcf9780-a1c3-47fa-8e0f-0f1b65d2527a.json`.

#### Robust Parsing and observatons
- **Robust JSON Parsing**: To resolve "Extra data" and truncation parsing errors on open-source reasoning models, we added a bulletproof JSON extraction helper (`extract_json`) that dynamically checks brace/bracket matching slices until a valid JSON parses. This has been covered by 5 new unit tests.
- **Rejection History Logging**: Rejections across all phases (execution, pre-verify, and verification) are now logged persistently to a run-specific log file: `artifacts/raw/{run_id}/rejections.json` for full audit trails.
- **Failed Runs Prior to Success**: Earlier runs hit max iterations and escalated (producing escalation reports in `artifacts/escalation/*.md`) due to credit limit constraints and Kimi output parsing issues, which guided our implementation of robust parsing and token limit adjustments.
- **Revenue/Margin Validation Gap**: Currently, the verifier snapshot only receives live stock prices, meaning other fields like revenue/margin pass on trust. BYD's final margin was `17.5` (representing 17.5% as a literal percentage) while TSLA's was `0.178` (representing 17.8% as a ratio). This highlighting inconsistency remains an open item for future feed additions.
