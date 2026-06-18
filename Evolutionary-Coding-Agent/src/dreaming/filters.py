import json
from src.config import config_instance

def clean_and_compress_trace_runs(runs: list[dict]) -> list[dict]:
    """
    Applies deterministic filtering to event trace runs to compress size.
    - Keeps only the final run for each (task_id, seed, pass_type) to drop retries.
    - Strips code and prompt for passed runs.
    - Truncates code and preserves errors for failed runs.
    - Limits to max_trace_events.
    """
    max_events = config_instance.get("dreaming.max_trace_events", 100)
    
    # 1. Filter only relevant execution runs
    exec_runs = []
    for r in runs:
        if r.get("pass_type") in ["baseline", "first_pass", "second_pass", "held_out", "naive_stream", "exploration", "regression"]:
            exec_runs.append(r)
            
    # 2. De-duplicate: Keep only the LAST execution for each task_id x seed x pass_type combination
    seen = {}
    for r in exec_runs:
        key = (r.get("task_id"), r.get("seed"), r.get("pass_type"))
        seen[key] = r
        
    filtered_runs = list(seen.values())
    
    # Sort by timestamp to maintain chronological order
    filtered_runs.sort(key=lambda x: x.get("timestamp", 0))
    
    # Limit number of events to prevent prompt overflow
    filtered_runs = filtered_runs[-max_events:]
    
    # 3. Compress each run metadata
    compressed = []
    for r in filtered_runs:
        compressed_r = {
            "timestamp": r.get("timestamp"),
            "task_id": r.get("task_id"),
            "seed": r.get("seed"),
            "pass_type": r.get("pass_type"),
            "status": r.get("status"),
            "score": r.get("score"),
            "duration_seconds": r.get("duration_seconds"),
            "estimated_tokens": r.get("estimated_tokens"),
            "estimated_cost_usd": r.get("estimated_cost_usd")
        }
        
        meta = r.get("metadata", {}) or {}
        comp_meta = {}
        
        # Preserve error message or exception details
        if "message" in meta:
            comp_meta["error"] = str(meta["message"])
        elif "error" in meta:
            comp_meta["error"] = str(meta["error"])
            
        # Extract validation feedback keys
        if "val_res" in meta and isinstance(meta["val_res"], dict):
            val = meta["val_res"]
            comp_meta["val_status"] = val.get("status")
            if val.get("message"):
                comp_meta["val_message"] = val.get("message")
                
        # Strip or truncate code
        if r.get("status") == "passed":
            # Passed tasks do not need code details to derive lessons
            pass
        else:
            # Failed tasks: preserve first 40 lines of code snippet
            code = meta.get("code", "") or ""
            lines = code.splitlines()
            if len(lines) > 40:
                comp_meta["failed_code_snippet"] = "\n".join(lines[:40]) + "\n... [TRUNCATED] ..."
            elif code:
                comp_meta["failed_code_snippet"] = code
                
        # Preserve active skills used if present
        if "skills_retrieved" in meta:
            comp_meta["skills_used"] = meta["skills_retrieved"]
        elif "skills_used" in meta:
            comp_meta["skills_used"] = meta["skills_used"]
            
        compressed_r["metadata"] = comp_meta
        compressed.append(compressed_r)
        
    return compressed
