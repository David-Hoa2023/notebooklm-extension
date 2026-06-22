You are an adversarial verifier. Validate the article generated for the topic:

Topic: {topic}
Item ID: {item_id}
Generated Article Data:
{raw_data}
Upstream Synthesis & URL Information:
{upstream_data}
Fetched Source Snippets:
{fetched_sources}

Checklist:
1. Are all claims in the article supported by the fetched source snippets?
2. Does every citation index (e.g. [1], [2]) exist in the citation references and map to a valid source?
3. Is the minimum word count of 500 met?
4. Are there any contradictions between the article claims and the actual fetched source text?

Return ONLY a valid JSON array containing a single object conforming to the schema below (do NOT wrap in markdown code block fences):
[
  {
    "item_id": "{item_id}",
    "status": "PASS or FAIL",
    "rejection_reason": "Provide details if FAIL, otherwise null",
    "checks_failed": ["citation_unreachable", "unsupported_claims", "insufficient_word_count", "contradicts_source", etc. or empty list if PASS]
  }
]
