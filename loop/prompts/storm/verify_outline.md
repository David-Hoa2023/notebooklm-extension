You are an adversarial verifier. Validate the outline generated for the topic:

Topic: {topic}
Item ID: {item_id}
Generated Outline Data:
{raw_data}
Upstream Perspectives and Contradictions:
{upstream_data}

Checklist:
1. Is the outline depth >= 2 (must contain subsections)?
2. Do all 5 required perspective IDs (practitioner, academic, skeptic, economist, historian) appear in the perspective_coverage metadata fields across sections?
3. Does the outline cover the contradictions/clashes identified in the contradiction map?

Return ONLY a valid JSON array containing a single object conforming to the schema below (do NOT wrap in markdown code block fences):
[
  {
    "item_id": "{item_id}",
    "status": "PASS or FAIL",
    "rejection_reason": "Provide details if FAIL, otherwise null",
    "checks_failed": ["insufficient_depth", "missing_perspective_coverage", "missing_clash_coverage", etc. or empty list if PASS]
  }
]
