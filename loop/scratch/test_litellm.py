import os
import ujson
from knowledge_storm.lm import LitellmModel

# Set API key from .env if needed
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                name, val = line.strip().split("=", 1)
                os.environ[name] = val

lm = LitellmModel(
    model="openrouter/moonshotai/kimi-k2.6",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    max_tokens=100,
    temperature=0.2
)

try:
    res = lm("Hello, tell me a 3-word greeting.")
    print("History entry:")
    import pprint
    pprint.pprint(lm.history[-1])
except Exception as e:
    import traceback
    traceback.print_exc()
