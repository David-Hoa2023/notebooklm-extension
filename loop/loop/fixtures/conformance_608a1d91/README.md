# Conformance Fixtures: Run 608a1d91

This directory contains regression fixtures captured from run `608a1d91-7205-4941-a30e-c4cd07dfa125` for the topic "loop engineering in AI in 2026".

## Gaps Identified (Story 2, 3, and 5)
1. **Story 2 (Upstream Alignment & Semantic Drift)**: The generated article drifted to describe "Microsoft Loop" or general dictionary definitions of "loop", failing to cover the main technical connections, tensions, and key findings from the `research_briefing.json` and `contradiction_map.json`.
2. **Story 3 (Citation Integrity)**: The final article cited irrelevant dictionary domains (like `merriam-webster.com`) rather than the original upstream research sources gathered during the perspectives/synthesis phases.
3. **Story 5 (Meta-Researcher Honest Grading)**: The peer review stage returned a grade of `C+` with 4 missing perspectives but incorrectly passed overall. These fixtures are used to test deterministic verify checks that enforce strict upstream alignment.
