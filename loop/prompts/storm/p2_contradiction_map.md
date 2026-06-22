You are an expert analytical agent. Analyze the following 5 perspectives for the research topic:

Perspectives Data:
{upstream_data}

Identify at least 3 distinct clashes/contradictions between the perspectives. Each clash must involve two distinct perspectives.
Also determine:
1. The strongest evidence among all perspectives.
2. The weakest/most questionable evidence among all perspectives.
3. Blind spots identified across the perspectives.

Return ONLY a valid JSON object matching this schema (do NOT wrap in markdown code block fences):
{
  "clashes": [
    {
      "perspective_id_1": "practitioner",
      "perspective_id_2": "academic",
      "description": "..."
    },
    ...
  ],
  "strongest_evidence": "...",
  "weakest_evidence": "...",
  "blind_spots": [
    "..."
  ]
}
