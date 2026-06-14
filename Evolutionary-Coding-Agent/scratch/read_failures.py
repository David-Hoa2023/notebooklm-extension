import json

with open("logs/trace.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if r.get("task_id") in ("EXP_7602454C", "EXP_17201BA0") or "7602454C" in str(r) or "17201BA0" in str(r):
                print("="*80)
                print(f"Pass Type: {r.get('pass_type')}")
                print(f"Step: {r.get('step')}")
                print(json.dumps(r, indent=2))
        except Exception as e:
            pass
