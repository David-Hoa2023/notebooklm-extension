import os
import json
import pytest
from src.dreaming.filters import clean_and_compress_trace_runs
from src.dreaming.dream_reader import dream_reader

def test_clean_and_compress_trace_runs():
    # Construct mock trace events
    mock_runs = [
        # Retried run (should be excluded by deduplication because a later one exists)
        {
            "timestamp": 100.0,
            "task_id": "SUB_001",
            "seed": 42,
            "pass_type": "first_pass",
            "status": "failed_tests",
            "score": 4.5,
            "duration_seconds": 12.0,
            "metadata": {"message": "Test mismatch", "code": "def func(): return 1"}
        },
        # Final pass_type = first_pass (passed, should keep this one and compress)
        {
            "timestamp": 110.0,
            "task_id": "SUB_001",
            "seed": 42,
            "pass_type": "first_pass",
            "status": "passed",
            "score": 9.0,
            "duration_seconds": 15.0,
            "metadata": {"message": "Success", "code": "def func(): return 2", "skills_retrieved": ["some_skill"]}
        },
        # Non-execution step (should be excluded)
        {
            "timestamp": 120.0,
            "pass_type": "exploration_step",
            "seed": 42,
            "step": "policy_decision",
            "detail": {}
        },
        # Non-execution step (should be excluded)
        {
            "timestamp": 130.0,
            "pass_type": "lifecycle_event",
            "event_type": "deduplication",
            "namespace": "insight",
            "detail": {}
        },
        # Failed run (passed=failed, should truncate long code)
        {
            "timestamp": 140.0,
            "task_id": "SUB_002",
            "seed": 42,
            "pass_type": "baseline",
            "status": "failed_syntax",
            "score": 0.0,
            "duration_seconds": 2.0,
            "metadata": {
                "message": "SyntaxError",
                "code": "\n".join([f"line_{i} = {i}" for i in range(100)]) # 100 lines
            }
        }
    ]
    
    compressed = clean_and_compress_trace_runs(mock_runs)
    
    # Assertions
    # 1. Total runs remaining: SUB_001 first_pass final, SUB_002 baseline final
    assert len(compressed) == 2
    
    # 2. Check SUB_001 (passed): code should be stripped
    sub1 = [c for c in compressed if c["task_id"] == "SUB_001"][0]
    assert sub1["status"] == "passed"
    assert "code" not in sub1["metadata"]
    assert "failed_code_snippet" not in sub1["metadata"]
    assert sub1["metadata"]["skills_used"] == ["some_skill"]
    
    # 3. Check SUB_002 (failed): code should be truncated with marker
    sub2 = [c for c in compressed if c["task_id"] == "SUB_002"][0]
    assert sub2["status"] == "failed_syntax"
    assert "failed_code_snippet" in sub2["metadata"]
    assert "[TRUNCATED]" in sub2["metadata"]["failed_code_snippet"]
    assert len(sub2["metadata"]["failed_code_snippet"].splitlines()) == 41 # 40 lines + marker

def test_dream_reader_load_trace(tmp_path):
    # Setup temporary trace file
    trace_file = tmp_path / "trace_temp.jsonl"
    mock_runs = [
        {
            "timestamp": 200.0,
            "task_id": "SUB_003",
            "seed": 43,
            "pass_type": "held_out",
            "status": "passed",
            "score": 9.0,
            "duration_seconds": 8.0,
            "metadata": {"code": "def parse(): pass"}
        }
    ]
    
    with open(trace_file, "w", encoding="utf-8") as f:
        for r in mock_runs:
            f.write(json.dumps(r) + "\n")
            
    bundle = dream_reader.load_trace(str(trace_file))
    
    assert bundle["source_trace"] == str(trace_file)
    assert bundle["raw_events_count"] == 1
    assert bundle["compressed_events_count"] == 1
    assert len(bundle["runs"]) == 1
    assert bundle["runs"][0]["task_id"] == "SUB_003"
    assert "compression_ratio" in bundle
