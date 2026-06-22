You are an adversarial verifier. Validate the peer review generated for the topic:

Topic: {topic}
Item ID: {item_id}
Generated Peer Review Data:
{raw_data}
Upstream Polished Article & Review Context:
{upstream_data}

Checklist:
1. Is the overall confidence score at least 7?
2. Are all required fields (confidence_scores, overall_confidence, bias_check, overall_grade) present and valid?
3. Does the review correctly identify if any required perspectives (practitioner, academic, skeptic, economist, historian) are missing from the article? If the historian perspective is missing from upstream but the peer review claims 0 missing perspectives, it should FAIL.

Return ONLY a valid JSON array containing a single object conforming to the schema below (do NOT wrap in markdown code block fences):
[
  {
    "item_id": "{item_id}",
    "status": "PASS or FAIL",
    "rejection_reason": "Provide details if FAIL, otherwise null",
    "checks_failed": ["low_confidence", "invalid_fields", "failed_bias_check", "missed_missing_perspectives", etc. or empty list if PASS]
  }
]
