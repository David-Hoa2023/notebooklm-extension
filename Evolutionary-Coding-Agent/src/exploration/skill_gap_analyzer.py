import re
from collections import Counter
from src.skill.skill_composition import skill_composition_instance
from src.memory.memory_engine import memory_engine


CAPABILITY_TAXONOMY = [
    "string_parsing",
    "regex",
    "math_evaluation",
    "data_structures",
    "file_io",
    "json_parsing",
    "date_time",
    "algorithms",
    "error_handling",
    "testing",
]


def _infer_capabilities(text: str) -> set[str]:
    text_lower = text.lower()
    caps = set()
    patterns = {
        "string_parsing": r"split|strip|join|substring|text",
        "regex": r"regex|re\.|pattern|match",
        "math_evaluation": r"math|expression|calculate|arithmetic",
        "data_structures": r"dict|list|set|tuple|deque|heap",
        "file_io": r"file|read|write|path",
        "json_parsing": r"json|serialize|deserialize",
        "date_time": r"date|time|datetime|timestamp",
        "algorithms": r"sort|search|graph|tree|dp|dynamic",
        "error_handling": r"try|except|raise|error",
        "testing": r"test|assert|unittest",
    }
    for cap, pattern in patterns.items():
        if re.search(pattern, text_lower):
            caps.add(cap)
    return caps


class SkillGapAnalyzer:
    def __init__(self):
        self.skill_composition_instance = skill_composition_instance
        self.memory_engine = memory_engine

    def analyze(self) -> dict:
        active_skills = skill_composition_instance.get_active_skills()
        covered = set()
        skill_backed_covered = set()
        skill_names = []

        for sk in active_skills:
            meta = sk.get("metadata", {})
            name = meta.get("name", "")
            if name:
                skill_names.append(name)
            doc = meta.get("docstring", "")
            code = sk.get("content", "")
            
            inferred = _infer_capabilities(f"{name} {doc} {code}")
            covered |= inferred
            
            # Skill-backed coverage: only from active, verified skills (excluding insights)
            # Typically verified skills have metadata retrievable=True or status=success
            if meta.get("retrievable", False) or meta.get("status") == "success":
                skill_backed_covered |= inferred

        insights = memory_engine.get_all_memories(namespace="insight")
        for ins in insights:
            covered |= _infer_capabilities(ins.get("content", ""))

        gaps = [cap for cap in CAPABILITY_TAXONOMY if cap not in covered]
        coverage_rate = 1.0 - (len(gaps) / len(CAPABILITY_TAXONOMY))

        skill_backed_gaps = [cap for cap in CAPABILITY_TAXONOMY if cap not in skill_backed_covered]
        skill_backed_coverage_rate = 1.0 - (len(skill_backed_gaps) / len(CAPABILITY_TAXONOMY))

        return {
            "covered_capabilities": sorted(covered),
            "gap_capabilities": gaps,
            "skill_names": skill_names,
            "coverage_rate": coverage_rate,
            "skill_backed_covered": sorted(skill_backed_covered),
            "skill_backed_gap_capabilities": skill_backed_gaps,
            "skill_backed_coverage_rate": skill_backed_coverage_rate,
        }

    def top_gaps(self, limit: int = 3) -> list[str]:
        res = self.analyze()
        gaps = res.get("skill_backed_gap_capabilities", [])
        if not gaps:
            gaps = res.get("gap_capabilities", [])
        return gaps[:limit]


skill_gap_analyzer = SkillGapAnalyzer()
