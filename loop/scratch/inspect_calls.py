import json

failed_calls = []
with open("litellm_calls.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        try:
            call = json.loads(line)
            if "Convert the following outline text into a structured JSON outline matching the OutlineSchema." in call.get("prompt", ""):
                failed_calls.append(call)
        except Exception:
            pass

print(f"Total outline parsing calls: {len(failed_calls)}")
if failed_calls:
    last_call = failed_calls[-1]
    print("\n--- PROMPT (last 500 chars) ---")
    print(last_call["prompt"][-500:])
    print("\n--- RESULT ---")
    print(last_call["result"])
