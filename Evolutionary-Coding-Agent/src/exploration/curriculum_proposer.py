import json
import uuid
from google.genai import types
from src.llm import llm_client
from src.config import config_instance
from src.exploration.models import ProposedTask


TASK_PROPOSAL_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "description": {"type": "STRING"},
        "difficulty": {"type": "STRING"},
        "target_skills": {"type": "ARRAY", "items": {"type": "STRING"}},
        "vertical_target": {"type": "STRING"},
        "rationale": {"type": "STRING"},
    },
    "required": ["title", "description", "difficulty", "target_skills", "rationale", "vertical_target"],
}


def compute_recent_success_rate(runs: list[dict], window: int = 10) -> float:
    """Fraction of passed runs in the most recent task executions."""
    task_runs = [
        r for r in runs
        if isinstance(r, dict)
        and "task_id" in r
        and r.get("pass_type") not in ("lifecycle_event",)
    ]
    if not task_runs:
        return 0.5
    recent = task_runs[-window:]
    passed = sum(1 for r in recent if r.get("status") == "passed")
    return passed / len(recent)


def calibrate_difficulty(success_rate: float) -> str:
    """
    Zone of Proximal Development calibration.
    High success -> harder tasks; low success -> easier tasks.
    """
    if success_rate >= 0.75:
        return "advanced"
    if success_rate >= 0.45:
        return "intermediate"
    return "basic"


class CurriculumProposer:
    def __init__(self):
        self.llm = llm_client

    def propose(
        self,
        success_rate: float,
        skill_summaries: list[str],
        gap_targets: list[str] | None = None,
        avoid_topics: list[str] | None = None,
        vertical_targets: list[str] | None = None,
    ) -> ProposedTask:
        difficulty = calibrate_difficulty(success_rate)
        gap_targets = gap_targets or []
        avoid_topics = avoid_topics or []
        vertical_targets = vertical_targets or []

        system_instruction = (
            "You are an autonomous curriculum designer for a Python coding agent. "
            "Propose ONE self-contained practice task at the requested difficulty level. "
            "The task must be solvable with standard library only, include clear function signatures, "
            "and target the listed skill gaps. Return JSON only."
        )

        testing_instruction = ""
        if "testing" in gap_targets:
            testing_instruction = (
                "- CRITICAL: Since 'testing' is a target skill gap, the task MUST require the agent to write "
                "custom assertions, test validation helpers, or self-check test suites checking implementations for correctness, "
                "using Python standard 'unittest' or 'assert' style. The function signature should receive test cases/results "
                "or run testing/assertion validation logic. The resulting skill/helper must be a reusable testing utility "
                "that performs self-check assertion validations."
            )

        verticals_instruction = ""
        if vertical_targets:
            verticals_instruction = (
                f"- CRITICAL: Close the following business vertical gap: {', '.join(vertical_targets)}. "
                "Design this practice task around the theme of one of these business verticals (sales, marketing, or finance). "
                "The proposed task MUST be set in this business context (e.g., aggregating order prices for 'sales', "
                "filtering UTM campaigns for 'marketing', or ledger auditing/tax math for 'finance') but still using Python stdlib only. "
                "Populate the 'vertical_target' field with the targeted vertical (one of: sales, marketing, finance, generic)."
            )

        prompt = f"""
Recent agent success rate: {success_rate:.0%}
Target difficulty (ZPD): {difficulty}
Skill gaps to close: {", ".join(gap_targets) if gap_targets else "general Python utilities"}
Known skills in bank: {", ".join(skill_summaries[:12]) if skill_summaries else "none yet"}
Avoid repeating these topics: {", ".join(avoid_topics[:8]) if avoid_topics else "none"}

Design a novel Python coding task with:
- A clear function signature requirement in the description
- Testable behavior (no external APIs, no files unless trivial)
- Difficulty aligned to {difficulty}
{testing_instruction}
{verticals_instruction}
"""

        res_str = self.llm.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.4,
            json_mode=True,
            response_schema=TASK_PROPOSAL_SCHEMA,
        )
        data = json.loads(res_str)
        task_id = f"EXP_{uuid.uuid4().hex[:8].upper()}"

        return ProposedTask(
            id=task_id,
            title=data["title"],
            description=data["description"],
            difficulty=data.get("difficulty", difficulty),
            target_skills=data.get("target_skills", gap_targets),
            rationale=data.get("rationale", ""),
            source="curriculum_proposer",
            skill_gap_targets=gap_targets,
            vertical_target=data.get("vertical_target", "generic"),
        )


curriculum_proposer = CurriculumProposer()
