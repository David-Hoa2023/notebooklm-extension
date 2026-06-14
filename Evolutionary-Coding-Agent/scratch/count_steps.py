import json
from collections import Counter

counts = Counter()
try:
    with open("logs/trace.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                pt = r.get("pass_type")
                if pt == "exploration_step":
                    counts[f"step_{r.get('step')}"] += 1
                elif pt == "exploration":
                    counts[f"explore_status_{r.get('status')}"] += 1
                else:
                    counts[pt] += 1
            except Exception:
                pass
except Exception as e:
    print(f"Error reading trace: {e}")

print("Progress statistics in trace.jsonl:")
for k, v in sorted(counts.items()):
    print(f"  {k}: {v}")
