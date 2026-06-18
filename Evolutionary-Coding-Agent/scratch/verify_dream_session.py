"""Verification script for Offline Dreaming and Session Distillation."""
import os
import json
import sys
import glob

sys.stdout.reconfigure(encoding="utf-8")

from src.memory.memory_engine import memory_engine
from src.observability import observability_manager

print("=" * 60)
print("Phase 7: Offline Dreaming verification checklist")
print("=" * 60)

# 1. Check filesystem mirror files
dreams_dir = "data/memory/dreams"
json_files = glob.glob(os.path.join(dreams_dir, "*.json"))
has_latest = os.path.exists(os.path.join(dreams_dir, "latest.json"))
session_files = [f for f in json_files if os.path.basename(f) != "latest.json"]

print(f"\n1. Filesystem check:")
print(f"   Dreams directory:    {dreams_dir} ({'EXISTS' if os.path.exists(dreams_dir) else 'MISSING'})")
print(f"   Total dream files:   {len(session_files)}")
print(f"   latest.json link:    {'EXISTS' if has_latest else 'MISSING'}")

# 2. Retrieve database records
db_dreams = memory_engine.get_all_memories(namespace="dream")
summaries = [d for d in db_dreams if d.get("content", "").startswith("[SUMMARY]")]
insights = [d for d in db_dreams if not d.get("content", "").startswith("[SUMMARY]")]

print(f"\n2. SQLite DB Namespace 'dream' check:")
print(f"   Total dream rows:    {len(db_dreams)}")
print(f"   Session summaries:   {len(summaries)}")
print(f"   Distilled insights:  {len(insights)}")
for ins in insights[:5]:
    meta = ins.get("metadata", {}) or {}
    print(f"   - [{meta.get('scope', 'global')}] {ins.get('content')[:60]}... (Domain: {meta.get('domain', 'N/A')})")

# 3. Check Trace files for metadata log
dreams_injected = []
has_dream_logs = False
try:
    with open("logs/trace.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                meta = r.get("metadata", {}) or {}
                if "dreams_retrieved" in meta:
                    has_dream_logs = True
                    retrieved = meta.get("dreams_retrieved", [])
                    if retrieved:
                        dreams_injected.append((r.get("task_id"), r.get("pass_type"), retrieved))
except FileNotFoundError:
    pass

print(f"\n3. Pipeline Trace Ingestion:")
print(f"   Has dreaming trace:  {'YES' if has_dream_logs else 'NO'}")
print(f"   Dreams injected:     {len(dreams_injected)} runs")
for task_id, pass_type, items in dreams_injected[:5]:
    print(f"   - Run {task_id} ({pass_type}) loaded dreams: {items}")

# 4. Generate checklist status
print(f"\n4. Verification Checklist:")
checks = [
    ("Dreams directory exists", os.path.exists(dreams_dir)),
    ("latest.json mirror exists", has_latest),
    ("SQLite dream database rows exist", len(db_dreams) > 0),
    ("Insights separate from summaries", len(insights) > 0),
    ("Session summaries present in DB", len(summaries) > 0)
]

for label, ok in checks:
    print(f"   [{'PASS' if ok else 'FAIL'}] {label}")

print("\n" + "=" * 60)
