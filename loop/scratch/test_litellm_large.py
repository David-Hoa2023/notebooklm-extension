import os
import pprint
from knowledge_storm.lm import LitellmModel

if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                name, val = line.strip().split("=", 1)
                os.environ[name] = val

print("Testing deepseek/deepseek-chat...")
try:
    lm = LitellmModel(
        model="openrouter/deepseek/deepseek-chat",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        max_tokens=500,
        temperature=0.2
    )
    res = lm("Hello, tell me a 3-word greeting.")
    print("DeepSeek result:", res)
except Exception as e:
    print("DeepSeek failed:", e)

print("\nTesting google/gemini-2.5-flash...")
try:
    lm2 = LitellmModel(
        model="openrouter/google/gemini-2.5-flash",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        max_tokens=500,
        temperature=0.2
    )
    res2 = lm2("Hello, tell me a 3-word greeting.")
    print("Gemini result:", res2)
except Exception as e:
    print("Gemini failed:", e)
