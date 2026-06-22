You are a peer reviewer. Review the polished article generated for the research topic:

Article & Synthesis Data:
{upstream_data}

Provide:
1. confidence_scores: dictionary mapping parts/stages to confidence scores (1-10)
2. overall_confidence: an overall confidence score (1-10)
3. bias_check: analysis of potential bias in the article.
4. missing_perspectives: any perspectives that were omitted or underrepresented.
5. overall_grade: a letter grade from A to F (A, B, C, D, E, F).

Return ONLY a valid JSON object matching this schema (do NOT wrap in markdown code block fences):
{
  "confidence_scores": {
    "perspectives": 8,
    "contradictions": 9,
    "synthesis": 8,
    "article": 9
  },
  "overall_confidence": 8,
  "bias_check": "...",
  "missing_perspectives": [],
  "overall_grade": "A-"
}
