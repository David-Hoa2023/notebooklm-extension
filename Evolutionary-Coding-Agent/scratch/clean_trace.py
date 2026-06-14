import json

print("Cleaning trace.jsonl...")
cleaned_lines = []
with open("logs/trace.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            # Keep only baseline, first_pass, second_pass, held_out, and early lifecycle events
            # Remove any pass_type='exploration' or 'exploration_step'
            pt = r.get("pass_type")
            if pt in ("baseline", "first_pass", "second_pass", "held_out"):
                cleaned_lines.append(line)
            elif pt == "lifecycle_event" and r.get("timestamp", 0) < 1781400000:
                # keep old lifecycle events before exploration began
                cleaned_lines.append(line)
        except Exception as e:
            print(f"Error parsing line: {e}")

with open("logs/trace.jsonl", "w", encoding="utf-8") as f:
    f.writelines(cleaned_lines)
print("trace.jsonl cleaned successfully. Total lines remaining:", len(cleaned_lines))
