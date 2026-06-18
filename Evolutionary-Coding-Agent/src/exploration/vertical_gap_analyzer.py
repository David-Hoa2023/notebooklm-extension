from src.skill.skill_composition import skill_composition_instance
from src.taxonomy.verticals import get_allowed_verticals

class VerticalGapAnalyzer:
    def __init__(self):
        self.skill_composition_instance = skill_composition_instance

    def analyze(self) -> dict:
        allowed = get_allowed_verticals()
        
        # Get active, retrievable (verified) skills
        active_skills = self.skill_composition_instance.get_active_skills()
        
        verticals_covered = set()
        for sk in active_skills:
            meta = sk.get("metadata", {})
            if meta.get("retrievable", False):
                vert = meta.get("vertical", "generic").lower().strip()
                if vert in allowed:
                    verticals_covered.add(vert)
                    
        # Exclude 'generic' from gaps and coverage calculations for targeting purpose
        non_generic_allowed = [v for v in allowed if v != "generic"]
        vertical_gaps = [v for v in non_generic_allowed if v not in verticals_covered]
        
        if non_generic_allowed:
            coverage_rate = 1.0 - (len(vertical_gaps) / len(non_generic_allowed))
        else:
            coverage_rate = 1.0
            
        return {
            "verticals_allowed": allowed,
            "verticals_covered": sorted(list(verticals_covered)),
            "vertical_gaps": vertical_gaps,
            "vertical_skill_backed_coverage_rate": coverage_rate
        }

    def top_vertical_gaps(self, limit: int = 3) -> list[str]:
        res = self.analyze()
        return res.get("vertical_gaps", [])[:limit]

vertical_gap_analyzer = VerticalGapAnalyzer()
