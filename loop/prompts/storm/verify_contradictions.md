You are an adversarial verifier. Validate the contradictions map generated for the topic:

Topic: {topic}
Item ID: {item_id}
Generated Contradictions Map Data:
{raw_data}
Upstream Perspectives:
{upstream_data}

Checklist:
1. Are there at least 3 genuine, distinct clashes between different perspectives?
2. Do all clashes reference valid perspective IDs present in the upstream perspectives?
3. Are the blind spots, strongest evidence, and weakest evidence fields present, non-empty, and non-placeholder?

Return ONLY a valid JSON array containing a single object conforming to the schema below (do NOT wrap in markdown code block fences):
[
  {
    "item_id": "{item_id}",
    "status": "PASS or FAIL",
    "rejection_reason": "Provide details if FAIL, otherwise null",
    "checks_failed": ["insufficient_clashes", "invalid_perspective_id", "empty_fields", etc. or empty list if PASS]
  }
]
