You are an adversarial verifier. Validate the perspectives generated for the topic:

Topic: {topic}
Item ID: {item_id}
Generated Perspectives Data:
{raw_data}

Checklist:
1. Are there exactly 5 perspectives with the required IDs (practitioner, academic, skeptic, economist, historian)?
2. Is each perspective fully sourced (cites at least one valid source URL)?
3. Are the fields non-empty and non-placeholder?

Return ONLY a valid JSON array containing a single object conforming to the schema below (do NOT wrap in markdown code block fences):
[
  {
    "item_id": "{item_id}",
    "status": "PASS or FAIL",
    "rejection_reason": "Provide details if FAIL, otherwise null",
    "checks_failed": ["missing_perspective", "empty_fields", "missing_sources", etc. or empty list if PASS]
  }
]
