You are an adversarial verifier. Validate the synthesis briefing generated for the topic:

Topic: {topic}
Item ID: {item_id}
Generated Synthesis Data:
{raw_data}
Upstream Outline & Contradiction Map:
{upstream_data}

Checklist:
1. Are there at least 5 key findings ranked with reliability scores between 1 and 10?
2. Are source references present for key findings?
3. Is there an actionable insight and a summary present and non-placeholder?
4. Do the findings align with the outline sections and the contradiction map?

Return ONLY a valid JSON array containing a single object conforming to the schema below (do NOT wrap in markdown code block fences):
[
  {
    "item_id": "{item_id}",
    "status": "PASS or FAIL",
    "rejection_reason": "Provide details if FAIL, otherwise null",
    "checks_failed": ["insufficient_findings", "invalid_reliability_score", "missing_actionable_insight", etc. or empty list if PASS]
  }
]
