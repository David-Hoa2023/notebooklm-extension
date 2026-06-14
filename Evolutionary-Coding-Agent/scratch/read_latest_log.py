import json

lines = []
with open("logs/trace.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            lines.append(line)

print("Latest 10 trace entries:")
for line in lines[-10:]:
    try:
        r = json.loads(line)
        print(f"Timestamp: {r.get('timestamp')} | Pass: {r.get('pass_type')} | Task: {r.get('task_id')} | Status: {r.get('status')} | Step: {r.get('step')}")
    except Exception as e:
        print(f"JSON Error: {e} on line: {line[:100]}")
