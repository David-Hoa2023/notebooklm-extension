# Use Cases & User Stories - STORM Multi-Perspective Verify Loop

This document presents concrete user stories and scenarios showcasing how the Stanford STORM + Nav Toor self-verifying research loop resolves core pain points encountered when relying on standard generative AI for structured research.

---

## At-a-Glance: Pain Points vs. STORM Solutions

| Traditional AI Research Pain Point | How STORM Option B Solves It |
| :--- | :--- |
| **The Hype Bubble & Bias**: AI summaries reiterate marketing fluff, missing engineering constraints or skeptical perspectives. | **Multi-Perspective scan (P1)**: Enforces exactly 5 distinct roles (Practitioner, Academic, Skeptic, Economist, Historian) to guarantee balanced inputs. |
| **Contradictory and Unresolved Claims**: Labs claim readiness while factories claim failure. Traditional AI glosses over details. | **Contradiction Mapping (P2)**: Explicitly surfaces clashes between expert fields and forces a dedicated contradiction artifact. |
| **"Ghost" or Broken Citations**: AI hallucinating URLs or citing dead pages that compromise the report's credibility. | **Web Verification Gate**: Active connection checks test every citation. If any URL is unreachable, it triggers a self-correction feedback loop. |
| **Linear Cascading Errors**: A mistake in the early research phase flows unchecked into the final printed report. | **Cascading Resets**: If the perspectives scan is failed and updated on a retry, all downstream stages of the topic reset back to pending. |

---

## User Stories

### Story 1: The Battery Venture Capital Analyst (The Hype Bubble)
* **Persona**: Marcus, Principal Battery Tech Analyst at a Cleantech VC.
* **The Pain Point**: Marcus needs to evaluate solid-state battery startups. Standard search engines and one-shot AI summaries return optimistic marketing copy, press releases, and high-level summaries claiming "production is 1 year away." Marcus misses critical engineering realities, raw material pricing, and historical adoption curves.
* **The STORM Solution**:
  1. Marcus configures the topic `"Solid-state battery commercialization"` in `loop.config.storm.example.yaml` and executes the orchestrator.
  2. The system executes the **Perspectives stage**. It forces a 5-role scan.
  3. The *Skeptic* and *Practitioner* roles highlight dendrite growth issues and cell packing defects. The *Historian* compares the adoption rate to the 15-year transition of lithium-ion.
  4. **Outcome**: The final report contains a balanced, realistic, multi-perspective breakdown, preventing Marcus's firm from investing in overhyped technology.

---

### Story 2: The Electric Vehicle Product Manager (The Contradictory Briefs)
* **Persona**: Sarah, Lead Product Manager for Battery Pack Assemblies.
* **The Pain Point**: Sarah receives conflicting claims. Her research department asserts a new silicon-anode chemistry is ready for deployment (high energy density). Her manufacturing yield engineers assert that the silicon expansion causes structural defects on cell lines. AI search tools average these out into vague sentences.
* **The STORM Solution**:
  1. Sarah runs the STORM loop on her internal anode research briefs.
  2. The **Contradictions stage** triggers Nav Toor's P2 prompt.
  3. It explicitly identifies the clash: `Academic (high anode density breakthroughs) vs. Practitioner (manufacturing yield cell cracking defects)`.
  4. The **Synthesis stage** aggregates these contradictions, highlighting the "hidden connection" (lab yield scale limits) and provides an actionable insight: invest in pre-lithiation machinery to mitigate expansion.
  5. **Outcome**: Sarah gets a clear map of resolved contradictions rather than an averaged summary, enabling direct engineering decisions.

---

### Story 3: The Energy Policy Advisor (The Ghost Citations)
* **Persona**: David, Government Policy Advisor drafting EV tariff guidelines.
* **The Pain Point**: David drafts policy recommendations. If his reports contain hallucinated facts or dead, broken citation links, the opposition will tear down the policy draft. Standard AI generators frequently hallucinate URL links.
* **The STORM Solution**:
  1. David initiates the research loop on `"Chinese EV export tariffs impact"`.
  2. During the **Article stage**, the raw article is generated with citations.
  3. The **Verify Gate** intercepts the article. It does a live HTTP fetch on every single citation reference.
  4. If a link is dead, the verifier fails the item (`citation_unreachable`), increments attempts, and logs the feedback: `URL https://example.com/tariffs/dead_link failed to fetch`.
  5. The executor automatically retries, references the feedback, and updates the article with an active, corrected citation.
  6. **Outcome**: David receives a report with 100% verified, active, and reachable URLs, maintaining complete credibility.
