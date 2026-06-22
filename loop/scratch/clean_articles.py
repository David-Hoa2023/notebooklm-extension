import os
import json
from loop.utils import clean_electrical_analogy

run_id = "608a1d91-7205-4941-a30e-c4cd07dfa125"
topic_slug = "loop_engineering_in_ai_in_2026"

raw_dir = f"artifacts/raw/{run_id}/{topic_slug}"
final_report_path = f"{raw_dir}/final_report.json"
polished_txt_path = f"{raw_dir}/storm_gen_article_polished.txt"
final_bundle_path = f"artifacts/final/{run_id}.json"

# 1. Clean storm_gen_article_polished.txt
if os.path.exists(polished_txt_path):
    print(f"Cleaning {polished_txt_path}...")
    with open(polished_txt_path, "r", encoding="utf-8") as f:
        content = f.read()
    cleaned = clean_electrical_analogy(content)
    if cleaned != content:
        with open(polished_txt_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

# 2. Clean final_report.json
if os.path.exists(final_report_path):
    print(f"Cleaning {final_report_path}...")
    with open(final_report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "polished_article" in data:
        data["polished_article"] = clean_electrical_analogy(data["polished_article"])
    with open(final_report_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# 3. Clean final_bundle.json
if os.path.exists(final_bundle_path):
    print(f"Cleaning {final_bundle_path}...")
    with open(final_bundle_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if topic_slug in data:
        topic_data = data[topic_slug]
        if "polished_article" in topic_data:
            topic_data["polished_article"] = clean_electrical_analogy(topic_data["polished_article"])
    with open(final_bundle_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

print("Done cleaning!")
