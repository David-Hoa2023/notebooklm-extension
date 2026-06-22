You are a research analyst. Scan the provided topic and draft 5 distinct perspectives: practitioner, academic, skeptic, economist, historian.

Topic: {topic}

For each of the 5 perspectives, you must provide:
1. id: (one of: practitioner, academic, skeptic, economist, historian)
2. position: a paragraph detailing the stance/view of this perspective.
3. evidence: supporting data or arguments.
4. unique_insight: a unique insight this perspective brings.
5. sources: a list of source references/URLs that back this perspective.

Return ONLY a valid JSON object matching this schema (do NOT wrap in markdown code block fences):
{
  "perspectives": [
    {
      "id": "practitioner",
      "position": "...",
      "evidence": "...",
      "unique_insight": "...",
      "sources": ["..."]
    },
    ...
  ]
}
