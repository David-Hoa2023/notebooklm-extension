import os
import sys
import json
import uuid
import yaml
import argparse
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Fix output encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from loop.state import ItemState, LoopState, load_state, save_state
from loop.pre_verify import pre_verify_item
from loop.feeds import fetch_yahoo_finance_price, fetch_binance_price
from loop.utils import extract_json
from loop.storm_paths import to_topic_slug, expand_topics_to_stage_items, STAGES, get_stage_normalized_filename, get_stage_output_filename
from loop.storm_stages import (
    run_stage_perspectives,
    run_stage_contradictions,
    run_stage_outline,
    run_stage_synthesis,
    run_stage_article,
    run_stage_peer_review
)
from loop.storm_pre_verify import pre_verify_storm_stage
from loop.storm_verify import run_storm_verifier

# ==============================================================================
# CLI Configuration Defaults
# ==============================================================================
DEFAULT_CONFIG = {
    "max_iterations": 5,
    "state_file": "STATE.yaml",
    "batch_size": 100,
    "roles": {
        "planner_verifier": "z-ai/glm-5.2",
        "executor_swarm": "moonshot/kimi-k2.6"
    },
    "items": ["TSLA", "BYD", "RIVN"]
}

# ==============================================================================
# Mock Data and Stubs (TSK-006)
# ==============================================================================
MOCK_FIXTURE_ITEMS = ["TSLA", "BYD", "RIVN"]

MOCK_LIVE_FEEDS = {
    "TSLA": {"revenue": 96.77, "margin": 0.15, "stock_price": 400.49, "source_url": "https://ir.tesla.com", "metrics": {"market_cap": 600.0}},
    "BYD": {"revenue": 85.0, "margin": 0.05, "stock_price": 55.20, "source_url": "https://byd.com/investor", "metrics": {"market_cap": 100.0}},
    "RIVN": {"revenue": 4.98, "margin": -0.30, "stock_price": 11.85, "source_url": "https://rivian.com/ir", "metrics": {"market_cap": 15.0}}
}

def run_mock_executor(item_id: str, attempt: int) -> Dict[str, Any]:
    """
    Simulates Kimi execution for the 3-item fixture.
    Generates data that fails early on and gets corrected over attempts.
    """
    print(f"🤖 [Mock Executor] Simulating attempt {attempt} for {item_id}")
    
    if item_id == "TSLA":
        if attempt == 0:
            # Fails pre-verify (invalid/placeholder source URL format)
            return {
                "company_name": "Tesla",
                "revenue": 96.77,
                "margin": 0.15,
                "stock_price": 400.49,
                "source_url": "placeholder-url",
                "metrics": {"market_cap": 600.0}
            }
        elif attempt == 1:
            # Fails LLM verify (incorrect stock price figure)
            return {
                "company_name": "Tesla",
                "revenue": 96.77,
                "margin": 0.15,
                "stock_price": 200.0,
                "source_url": "https://ir.tesla.com",
                "metrics": {"market_cap": 600.0}
            }
        else:
            # Passes all checks
            return {
                "company_name": "Tesla",
                "revenue": 96.77,
                "margin": 0.15,
                "stock_price": 400.49,
                "source_url": "https://ir.tesla.com",
                "metrics": {"market_cap": 600.0}
            }
            
    elif item_id == "BYD":
        if attempt == 0:
            # Fails pre-verify (margin is a sentinel zero value)
            return {
                "company_name": "BYD",
                "revenue": 85.0,
                "margin": 0.0,
                "stock_price": 55.20,
                "source_url": "https://byd.com/investor",
                "metrics": {"market_cap": 100.0}
            }
        else:
            # Passes all checks
            return {
                "company_name": "BYD",
                "revenue": 85.0,
                "margin": 0.05,
                "stock_price": 55.20,
                "source_url": "https://byd.com/investor",
                "metrics": {"market_cap": 100.0}
            }
            
    elif item_id == "RIVN":
        if attempt == 0:
            # Fails LLM verify (incorrect stock price figure)
            return {
                "company_name": "Rivian",
                "revenue": 4.98,
                "margin": -0.30,
                "stock_price": 5.0,
                "source_url": "https://rivian.com/ir",
                "metrics": {"market_cap": 15.0}
            }
        else:
            # Passes all checks
            return {
                "company_name": "Rivian",
                "revenue": 4.98,
                "margin": -0.30,
                "stock_price": 11.85,
                "source_url": "https://rivian.com/ir",
                "metrics": {"market_cap": 15.0}
            }
            
    else:
        raise ValueError(f"Unknown item ID for mock executor: {item_id}")


def run_mock_verifier(item_id: str, raw_data: Dict[str, Any]) -> Tuple[bool, List[str], Optional[str]]:
    """
    Simulates Opus LLM verify gate using mock live feeds checking stock price.
    """
    print(f"🔍 [Mock Verifier] Checking {item_id}...")
    feed = MOCK_LIVE_FEEDS.get(item_id)
    if not feed:
        return False, ["unknown_item"], f"Item {item_id} not found in live feeds."
        
    stock_price = raw_data.get("stock_price")
    expected_price = feed.get("stock_price")
    
    # 1% tolerance checks
    if abs(stock_price - expected_price) > 0.01 * expected_price:
        return (
            False,
            ["stock_price_mismatch"],
            f"Stock price {stock_price} does not match Yahoo Finance live feed which shows {expected_price}."
        )
        
    return True, [], None

# extract_json is now imported from loop.utils


def log_rejection_history(run_id: str, item_id: str, attempt: int, phase: str, reason: str, stage: str = None, topic_slug: str = None):
    """
    Appends a rejection reason to a persistent run-level rejection history log file.
    """
    os.makedirs(f"artifacts/raw/{run_id}", exist_ok=True)
    history_path = f"artifacts/raw/{run_id}/rejections.json"
    
    history = []
    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass
            
    entry = {
        "timestamp": datetime.now().isoformat(),
        "item_id": item_id,
        "attempt": attempt,
        "phase": phase,
        "reason": reason
    }
    if stage:
        entry["stage"] = stage
    if topic_slug:
        entry["topic_slug"] = topic_slug
        
    history.append(entry)
    
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def run_real_executor(item_id: str, attempt: int, last_rejection: Optional[str], model: str) -> Dict[str, Any]:
    """
    Invokes Kimi via OpenRouter or direct Moonshot API with fallback.
    Uses large max_tokens limit (4096) to accommodate reasoning/thinking models.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("The 'openai' package is required for real mode. Install with 'pip install openai'.")
        
    prompt = f"Generate an EV company data entry for ticker '{item_id}'."
    
    # We do NOT supply the stock price hint by default to allow Kimi to generate
    # the price autonomously, letting the Opus Verifier Gate catch and provide feedback
    # on any stale/mismatched stock prices to demonstrate the self-correcting loop.
    ref_price_str = ""
    if os.environ.get("INJECT_WRONG_PRICE") == "1" and attempt == 0 and item_id == "TSLA":
        ref_price_str = "stock price is 9999.99 USD"
    
    if ref_price_str:
        prompt += f"\nReference: {ref_price_str}."
    if last_rejection:
        prompt += f"\nNote: The previous attempt failed validation for the following reason:\n{last_rejection}\nPlease correct this error."
        
    prompt += "\nReturn ONLY a valid JSON object matching this schema:\n"
    prompt += '{\n  "company_name": "string",\n  "revenue": float,\n  "margin": float,\n  "stock_price": float,\n  "source_url": "string",\n  "metrics": { "market_cap": float }\n}'
    
    moonshot_key = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    
    response = None
    if moonshot_key:
        try:
            print("🔗 [Executor] Connecting directly to Moonshot API (api.moonshot.ai)...")
            client = OpenAI(base_url="https://api.moonshot.ai/v1", api_key=moonshot_key)
            model_name = model.split("/")[-1]
            print(f"🤖 [Executor] Calling Kimi Model '{model_name}' for {item_id} (attempt {attempt})...")
            # Note: direct Kimi reasoning models enforce temperature=1.0
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a data extraction executor. Output ONLY valid JSON, no markdown formatting, code block fences, or extra dialogue."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0 if "kimi" in model_name.lower() else 0.2,
                max_tokens=1000
            )
        except Exception as e:
            print(f"⚠️ [Executor] Direct Moonshot API call failed: {e}. Falling back to OpenRouter...")
            response = None

    if not response:
        print("🔗 [Executor] Connecting via OpenRouter API...")
        if not api_key:
            raise ValueError("Neither valid MOONSHOT_API_KEY nor OPENROUTER_API_KEY is set in environment.")
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        print(f"🤖 [Executor] Calling Kimi Model '{model}' via OpenRouter for {item_id} (attempt {attempt})...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a data extraction executor. Output ONLY valid JSON, no markdown formatting, code block fences, or extra dialogue."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
    
    content = response.choices[0].message.content
    if not content:
        # Fallback if content field is null but thinking/reasoning field has content
        print("⚠️ [Executor] Response content is empty, attempting to parse reasoning field...")
        content = getattr(response.choices[0].message, "reasoning", "")
        if not content:
            # Check for direct Moonshot API reasoning field name
            content = getattr(response.choices[0].message, "reasoning_content", "")
        if not content:
            raise ValueError("LLM returned an empty response with no content or reasoning.")
            
    return json.loads(extract_json(content))


def run_real_verifier(item_id: str, raw_data: Dict[str, Any], model: str) -> Tuple[bool, List[str], Optional[str]]:
    """
    Invokes Opus via OpenRouter to cross-reference stock price against live API.
    Uses 350 max_tokens limit to satisfy credit constraints.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("The 'openai' package is required for real mode. Install with 'pip install openai'.")
        
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set in environment.")
        
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    
    # Load system prompt
    prompt_path = os.path.join("prompts", "verify_gate_system.md").replace("\\", "/")
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"Verifier prompt not found at {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()
        
    # Get live stock price feed
    live_stock = fetch_yahoo_finance_price(item_id)
    live_btc = fetch_binance_price("BTCUSDT")
    
    feed_snapshot = {}
    if live_stock.get("status") == "success":
        feed_snapshot["stock_price"] = live_stock["price"]
        feed_snapshot["currency"] = live_stock["currency"]
        feed_snapshot["source"] = live_stock["source"]
    else:
        # Fallback to mock feed stock prices
        mock_feed = MOCK_LIVE_FEEDS.get(item_id, {})
        feed_snapshot["stock_price"] = mock_feed.get("stock_price")
        feed_snapshot["currency"] = "USD"
        feed_snapshot["source"] = "Stale mock backup data"

    user_msg = f"""
Please verify this item:
Item ID: {item_id}
Generated Item Data:
{json.dumps(raw_data, indent=2)}

Live Feed Snapshot for verification:
{json.dumps(feed_snapshot, indent=2)}

General Reference (Live Crypto Feed):
BTCUSDT symbol price: {live_btc.get('price')} USD (Source: {live_btc.get('source')})
"""

    print(f"🔍 [Verifier] Calling Verifier Model '{model}' to check {item_id}...")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        temperature=0.0,
        max_tokens=1000
    )
    
    content = response.choices[0].message.content
    results = json.loads(extract_json(content))
    result = next((r for r in results if r.get("item_id") == item_id), None)
    if not result:
        return False, ["verifier_parse_error"], f"Verifier returned no details for item {item_id}."
        
    if result.get("status") == "FAIL":
        return False, result.get("checks_failed", []), result.get("rejection_reason")
        
    return True, [], None

# ==============================================================================
# Orchestration Loop
# ==============================================================================
def record_guideline(success_items: List[str]):
    """
    Appends a summary of successful results to memory/distilled_guidelines.md
    """
    os.makedirs("memory", exist_ok=True)
    guidelines_path = os.path.join("memory", "distilled_guidelines.md").replace("\\", "/")
    
    entry = f"""
## Run Guidelines - {datetime.now().isoformat()}
- **Success Criteria**: Zero active rejections achieved.
- **Verified Items**: {', '.join(success_items)}
- **Observations**: 
  - Iterative self-correction corrected structural issues (pre-verify) and stock price discrepancies (LLM verifier).
  - Pre-verification correctly filtered invalid URLs and placeholder variables, reducing LLM token costs.
"""
    with open(guidelines_path, "a", encoding="utf-8") as f:
        f.write(entry)
    print(f"📝 Guidelines written to {guidelines_path}")


def write_escalation_report(state: LoopState, state_file_path: str, is_storm: bool = False):
    """
    Writes an escalation report detailing failures when max iterations are exceeded.
    """
    escalation_dir = os.path.join("artifacts", "escalation").replace("\\", "/")
    os.makedirs(escalation_dir, exist_ok=True)
    escalation_path = os.path.join(escalation_dir, f"{state.run_id}.md").replace("\\", "/")
    
    failures = []
    if is_storm:
        # Group by topic_slug
        by_topic = {}
        for item_id, item_state in state.items.items():
            if item_state.status != "passed":
                topic = item_state.topic_slug or "unknown"
                by_topic.setdefault(topic, []).append((item_id, item_state))
        for topic, items in by_topic.items():
            failures.append(f"### Topic: {topic}\n")
            for item_id, item_state in items:
                failures.append(
                    f"- **Stage**: {item_state.stage}\n"
                    f"  - **Status**: {item_state.status}\n"
                    f"  - **Attempts**: {item_state.attempts}\n"
                    f"  - **Last Rejection Reason**: {item_state.last_rejection or 'No rejection recorded.'}\n"
                )
    else:
        for item_id, item_state in state.items.items():
            if item_state.status != "passed":
                failures.append(
                    f"### {item_id}\n"
                    f"- **Status**: {item_state.status}\n"
                    f"- **Attempts**: {item_state.attempts}\n"
                    f"- **Last Rejection Reason**: {item_state.last_rejection or 'No rejection recorded.'}\n"
                )
            
    content = f"""# Escalation Report - Run {state.run_id}

> [!WARNING]
> The verification loop exceeded the maximum of {state.max_iterations} iterations with active rejections.

## Summary Metrics
- **Total Items**: {state.items_total}
- **Passed Items**: {state.items_passed}
- **Active Rejections**: {state.active_rejections}
- **Timestamp**: {datetime.now().isoformat()}

## Remaining Failures
{"".join(failures) if is_storm else chr(10).join(failures)}

## Recommended Actions
1. Fix the underlying raw data sources or schemas.
2. Manually override the state in the state file '{state_file_path}' by setting status to `passed` and providing an override reason if applicable.
3. Resume the execution run with `python -m loop.run --resume {state.run_id}`.
"""
    with open(escalation_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"🚨 Escalation report written to {escalation_path}")


def run_orchestrator(config_path: str, run_mock: bool, resume_run_id: str = None, run_mock_storm: bool = False):
    import time
    from concurrent.futures import ThreadPoolExecutor

    # Load configuration
    config = DEFAULT_CONFIG.copy()
    if config_path and os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                config.update(yaml_config)
                
    state_file = config.get("state_file", "STATE.yaml").replace("\\", "/")
    max_iterations = config.get("max_iterations", 5)
    
    is_storm_mode = run_mock_storm or config.get("mode") == "storm_option_b"
    if run_mock_storm:
        config["mock_storm"] = True
        if "topics" not in config or not config["topics"]:
            config["topics"] = ["test_ev_battery_supply_chain", "test_solid_state_battery"]
        
    # Retrieve configured models
    verifier_model = config.get("roles", {}).get("planner_verifier", "z-ai/glm-5.2")
    executor_model = config.get("roles", {}).get("executor_swarm", "moonshot/kimi-k2.6")
    
    # Determine the target items/topics
    if is_storm_mode:
        if run_mock_storm:
            target_topics = config["topics"]
        else:
            target_topics = config.get("topics", [])
        expanded_items = expand_topics_to_stage_items(target_topics)
        target_items = list(expanded_items.keys())
    else:
        if run_mock:
            target_items = MOCK_FIXTURE_ITEMS
        else:
            target_items = config.get("items", DEFAULT_CONFIG["items"])
            
    # Load or initialize state
    if resume_run_id and os.path.exists(state_file):
        print(f"🔄 Resuming existing run from {state_file}...")
        state = load_state(state_file)
        if state.run_id != resume_run_id:
            print(f"⚠️ Warning: State file has run_id '{state.run_id}', but '{resume_run_id}' was requested. Resetting state ID to match file.")
        
        if state.status in ("escalated", "failed"):
            print("📈 Resuming from non-running status. Resetting state status to running and increasing max_iterations.")
            state.status = "running"
            state.max_iterations = max_iterations + state.iteration
    else:
        run_id = str(uuid.uuid4()) if not resume_run_id else resume_run_id
        print(f"🆕 Initializing new run state with run_id: {run_id}")
        state = LoopState(
            run_id=run_id,
            max_iterations=max_iterations,
            items_total=len(target_items),
            items_passed=0,
            active_rejections=len(target_items),
            status="running"
        )
        if is_storm_mode:
            for item_id, item_meta in expanded_items.items():
                state.items[item_id] = ItemState(
                    stage=item_meta["stage"],
                    topic_slug=item_meta["topic_slug"],
                    depends_on=item_meta["depends_on"]
                )
        else:
            for item_id in target_items:
                state.items[item_id] = ItemState()
        save_state(state, state_file)
        
    config["run_id"] = state.run_id
    print(f"📊 State loaded: {state.items_passed}/{state.items_total} passed. Iteration: {state.iteration}/{state.max_iterations}")
    
    # Check for manual human overrides and passed count
    passed_count = sum(1 for item in state.items.values() if item.status == "passed")
    state.items_passed = passed_count
    state.active_rejections = state.items_total - passed_count
    
    if state.active_rejections == 0:
        state.status = "passed"
        print("🏁 Loop already completed. All items are in passed status.")

    stage_metrics = []
    topic_concurrency = config.get("topic_concurrency", 2)
    
    # Orchestrator Loop
    while state.iteration <= state.max_iterations and state.status == "running":
        print(f"\n--- 🔄 Iteration {state.iteration}/{state.max_iterations} ---")
        
        # 1. Plan & Execute phase
        print("🎬 [Execute Phase] Running executors...")
        
        # Filter ready items
        ready_items = []
        for item_id, item_state in state.items.items():
            if item_state.status in ("pending", "pre_failed", "verify_failed"):
                if is_storm_mode:
                    # Enforce stage dependency
                    deps_ok = True
                    for dep_id in item_state.depends_on:
                        dep_item = state.items.get(dep_id)
                        if not dep_item or dep_item.status != "passed":
                            deps_ok = False
                            break
                    if deps_ok:
                        ready_items.append((item_id, item_state))
                else:
                    ready_items.append((item_id, item_state))
                    
        def execute_one_item(item_id, item_state):
            attempt = item_state.attempts
            start_time = time.time()
            try:
                if is_storm_mode:
                    stage = item_state.stage
                    topic_name = next((t for t in config.get("topics", []) if to_topic_slug(t) == item_state.topic_slug), item_state.topic_slug)
                        
                    print(f"🤖 [Executor] Executing stage '{stage}' for topic '{topic_name}' (attempt {attempt})...")
                    
                    if stage == "perspectives":
                        res = run_stage_perspectives(topic_name, attempt, item_state.last_rejection, config)
                    elif stage == "contradictions":
                        res = run_stage_contradictions(topic_name, attempt, item_state.last_rejection, config)
                    elif stage == "outline":
                        res = run_stage_outline(topic_name, attempt, item_state.last_rejection, config)
                    elif stage == "synthesis":
                        res = run_stage_synthesis(topic_name, attempt, item_state.last_rejection, config)
                    elif stage == "article":
                        res = run_stage_article(topic_name, attempt, item_state.last_rejection, config)
                    elif stage == "peer_review":
                        res = run_stage_peer_review(topic_name, attempt, item_state.last_rejection, config)
                    
                    # Load primary output file
                    out_dir = os.path.join("artifacts", "raw", state.run_id, item_state.topic_slug).replace("\\", "/")
                    filename = get_stage_normalized_filename(stage)
                    filepath = os.path.join(out_dir, filename).replace("\\", "/")
                    with open(filepath, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                        
                    latency = int((time.time() - start_time) * 1000)
                    return {"status": "success", "raw_data": raw_data, "latency": latency, "res": res}
                else:
                    if run_mock:
                        raw_data = run_mock_executor(item_id, attempt)
                    else:
                        raw_data = run_real_executor(item_id, attempt, item_state.last_rejection, executor_model)
                    latency = int((time.time() - start_time) * 1000)
                    return {"status": "success", "raw_data": raw_data, "latency": latency}
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"status": "error", "error": str(e)}

        # Run executions in parallel
        exec_results = {}
        with ThreadPoolExecutor(max_workers=topic_concurrency) as pool:
            futures = {pool.submit(execute_one_item, item_id, item_state): item_id for item_id, item_state in ready_items}
            for fut in futures:
                item_id = futures[fut]
                exec_results[item_id] = fut.result()
                
        # Handle execution results and run Pre-Verify
        for item_id, res in exec_results.items():
            item_state = state.items[item_id]
            attempt = item_state.attempts
            if res["status"] == "error":
                print(f"❌ Execution failed for {item_id}: {res['error']}")
                item_state.status = "pre_failed"
                item_state.last_rejection = f"Execution Error: {res['error']}"
                item_state.attempts += 1
                log_rejection_history(
                    state.run_id, item_id, attempt, "execution_phase", res["error"],
                    stage=item_state.stage, topic_slug=item_state.topic_slug
                )
            else:
                raw_data = res["raw_data"]
                print(f"🧪 [Pre-Verify Phase] Checking schema for {item_id}...")
                
                if is_storm_mode:
                    is_valid, checks_failed, reason = pre_verify_storm_stage(
                        item_state.stage, raw_data, state.run_id, item_state.topic_slug, config=config
                    )
                else:
                    is_valid, checks_failed, reason = pre_verify_item(item_id, raw_data, state.run_id)
                    
                if not is_valid:
                    print(f"⚠️ Pre-verification FAILED for {item_id}: {reason}")
                    item_state.status = "pre_failed"
                    item_state.last_rejection = reason
                    item_state.attempts += 1
                    log_rejection_history(
                        state.run_id, item_id, attempt, "pre_verify", reason,
                        stage=item_state.stage, topic_slug=item_state.topic_slug
                    )
                else:
                    print(f"✅ Pre-verification PASSED for {item_id}")
                    item_state.status = "executing"
                    if is_storm_mode:
                        out_dir = os.path.join("artifacts", "raw", state.run_id, item_state.topic_slug).replace("\\", "/")
                        filename = get_stage_normalized_filename(item_state.stage)
                        item_state.artifact_path = os.path.join(out_dir, filename).replace("\\", "/")
                    else:
                        item_state.artifact_path = os.path.join("artifacts", "raw", state.run_id, f"{item_id}.json").replace("\\", "/")
                        
        save_state(state, state_file)
        
        # 3. Verify Gate phase
        print("🛡️ [Verify Gate Phase] Running live validation...")
        
        executing_items = [(item_id, item_state) for item_id, item_state in state.items.items() if item_state.status == "executing"]
        
        def verify_one_item(item_id, item_state):
            attempt = item_state.attempts
            start_time = time.time()
            with open(item_state.artifact_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            try:
                if is_storm_mode:
                    topic_name = next((t for t in config.get("topics", []) if to_topic_slug(t) == item_state.topic_slug), item_state.topic_slug)
                    is_verified, checks_failed, reason = run_storm_verifier(
                        item_state.stage, raw_data, config, topic_name, item_id, verifier_model, attempt=attempt
                    )
                else:
                    if run_mock:
                        is_verified, checks_failed, reason = run_mock_verifier(item_id, raw_data)
                    else:
                        is_verified, checks_failed, reason = run_real_verifier(item_id, raw_data, verifier_model)
                latency = int((time.time() - start_time) * 1000)
                return {"status": "success", "is_verified": is_verified, "checks_failed": checks_failed, "reason": reason, "latency": latency}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        verify_results = {}
        with ThreadPoolExecutor(max_workers=topic_concurrency) as pool:
            futures = {pool.submit(verify_one_item, item_id, item_state): item_id for item_id, item_state in executing_items}
            for fut in futures:
                item_id = futures[fut]
                verify_results[item_id] = fut.result()

        for item_id, res in verify_results.items():
            item_state = state.items[item_id]
            attempt = item_state.attempts
            if res["status"] == "error":
                print(f"❌ Verification crashed for {item_id}: {res['error']}")
                reason = f"Verifier crash: {res['error']}"
                item_state.status = "verify_failed"
                item_state.last_rejection = reason
                item_state.attempts += 1
                log_rejection_history(
                    state.run_id, item_id, attempt, "verify_gate_crash", reason,
                    stage=item_state.stage, topic_slug=item_state.topic_slug
                )
            else:
                is_verified = res["is_verified"]
                checks_failed = res["checks_failed"]
                reason = res["reason"]
                
                # Add to metrics
                stage_metrics.append({
                    "topic_slug": item_state.topic_slug,
                    "stage": item_state.stage,
                    "latency_ms": res["latency"],
                    "status": "pass" if is_verified else "fail",
                    "checks_failed": checks_failed
                })
                
                if is_verified:
                    print(f"🎉 Verification PASSED for {item_id}!")
                    item_state.status = "passed"
                    item_state.last_rejection = None
                    item_state.verified_at = datetime.now().isoformat()
                else:
                    print(f"❌ Verification FAILED for {item_id}: {reason}")
                    item_state.status = "verify_failed"
                    item_state.last_rejection = reason
                    item_state.attempts += 1
                    log_rejection_history(
                        state.run_id, item_id, attempt, "verify_gate", reason,
                        stage=item_state.stage, topic_slug=item_state.topic_slug
                    )
                    # Cascade reset if perspectives fail
                    if is_storm_mode and item_state.stage == "perspectives":
                        print(f"🔄 Cascade resetting downstream stages for topic {item_state.topic_slug}")
                        for ds_stage in ["contradictions", "outline", "synthesis", "article", "peer_review"]:
                            ds_id = f"{item_state.topic_slug}::{ds_stage}"
                            if ds_id in state.items:
                                state.items[ds_id].status = "pending"
                                state.items[ds_id].attempts = 0
                                state.items[ds_id].last_rejection = None
                                
        # Update metrics
        passed_count = sum(1 for item in state.items.values() if item.status == "passed")
        state.items_passed = passed_count
        state.active_rejections = state.items_total - passed_count
        
        print(f"📉 Active Rejections: {state.active_rejections}/{state.items_total}")
        
        # 4. Termination Check
        if state.active_rejections == 0:
            state.status = "passed"
            print("🏁 Loop completed successfully! All items passed verification.")
            
            # Export final combined JSON/bundle artifact
            final_dir = os.path.join("artifacts", "final").replace("\\", "/")
            os.makedirs(final_dir, exist_ok=True)
            final_path = os.path.join(final_dir, f"{state.run_id}.json").replace("\\", "/")
            
            final_data = {}
            if is_storm_mode:
                for item_id, item_state in state.items.items():
                    if item_state.stage == "peer_review":
                        # Load final_report.json for the topic
                        out_dir = os.path.join("artifacts", "raw", state.run_id, item_state.topic_slug).replace("\\", "/")
                        rep_path = os.path.join(out_dir, "final_report.json").replace("\\", "/")
                        if os.path.exists(rep_path):
                            with open(rep_path, "r", encoding="utf-8") as f:
                                final_data[item_state.topic_slug] = json.load(f)
            else:
                for item_id, item_state in state.items.items():
                    with open(item_state.artifact_path, "r", encoding="utf-8") as f:
                        final_data[item_id] = json.load(f)
                        
            with open(final_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=2)
                
            print(f"🏆 Final report exported to {final_path}")
            
            # Record distilled guidelines
            record_guideline(list(state.items.keys()))
            
        elif state.iteration >= state.max_iterations:
            state.status = "escalated"
            print("🛑 Max iterations reached without achieving zero rejections. Escalating.")
            # Write escalation report
            write_escalation_report(state, state_file, is_storm=is_storm_mode)
        else:
            state.iteration += 1
            
        save_state(state, state_file)

    # Write run_metrics.json at termination
    metrics_dir = os.path.join("artifacts", "raw", state.run_id).replace("\\", "/")
    os.makedirs(metrics_dir, exist_ok=True)
    metrics_path = os.path.join(metrics_dir, "run_metrics.json").replace("\\", "/")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(stage_metrics, f, indent=2)
    print(f"📊 Metrics written to {metrics_path}")
    
    print(f"🏁 Execution finished. Final status: {state.status}")


# ==============================================================================
# Main entry point
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Self-Verifying Loop & Verify Gate")
    parser.add_argument("--config", type=str, default="loop.config.yaml", help="Path to config yaml")
    parser.add_argument("--mock", action="store_true", help="Run in local test mock/fixture mode")
    parser.add_argument("--mock-storm", action="store_true", help="Run STORM option B in mock mode")
    parser.add_argument("--resume", type=str, default=None, help="Resume an existing run ID")
    args = parser.parse_args()
    
    run_orchestrator(config_path=args.config, run_mock=args.mock, resume_run_id=args.resume, run_mock_storm=args.mock_storm)
