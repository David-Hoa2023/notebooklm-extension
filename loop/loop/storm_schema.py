from __future__ import annotations
import re
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from typing import List, Dict, Any, Optional

# ==============================================================================
# Perspectives Schema (Stage 1)
# ==============================================================================
class Perspective(BaseModel):
    id: str  # practitioner | academic | skeptic | economist | historian
    position: str
    evidence: str
    unique_insight: str
    sources: List[str]

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info: ValidationInfo) -> str:
        context = info.context or {}
        config = context.get("config", {})
        nav_toor = config.get("nav_toor", {})
        required = nav_toor.get("required_perspectives", [])
        
        allowed = {p.get("id") for p in required} if required else {"practitioner", "academic", "skeptic", "economist", "historian"}
        if v not in allowed:
            raise ValueError(f"Perspective ID '{v}' is not allowed. Must be one of: {allowed}")
        return v

    @field_validator("position", "evidence", "unique_insight")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v or v.strip() in ("", "placeholder", "Placeholder", "N/A"):
            raise ValueError("Fields cannot be empty or placeholder.")
        return v

class PerspectivesSchema(BaseModel):
    perspectives: List[Perspective]

    @field_validator("perspectives")
    @classmethod
    def validate_perspectives_count(cls, v: List[Perspective], info: ValidationInfo) -> List[Perspective]:
        context = info.context or {}
        config = context.get("config", {})
        nav_toor = config.get("nav_toor", {})
        required = nav_toor.get("required_perspectives", [])
        
        expected_count = len(required) if required else 5
        
        if len(v) != expected_count:
            raise ValueError(f"Must have exactly {expected_count} perspectives, got {len(v)}.")
        ids = {p.id for p in v}
        if len(ids) != expected_count:
            raise ValueError(f"All {expected_count} perspectives must have unique IDs.")
        return v


# ==============================================================================
# Contradiction Map Schema (Stage 2)
# ==============================================================================
class Clash(BaseModel):
    perspective_id_1: str
    perspective_id_2: str
    description: str

    @model_validator(mode="after")
    def validate_clash(self, info: ValidationInfo) -> Clash:
        if self.perspective_id_1 == self.perspective_id_2:
            raise ValueError("A clash must reference two distinct perspective IDs.")
        context = info.context or {}
        config = context.get("config", {})
        nav_toor = config.get("nav_toor", {})
        required = nav_toor.get("required_perspectives", [])
        
        allowed = {p.get("id") for p in required} if required else {"practitioner", "academic", "skeptic", "economist", "historian"}
        if self.perspective_id_1 not in allowed or self.perspective_id_2 not in allowed:
            raise ValueError("Clash perspective IDs must be valid required perspectives.")
        return self

class ContradictionMapSchema(BaseModel):
    clashes: List[Clash]
    strongest_evidence: str
    weakest_evidence: str
    blind_spots: List[str]

    @field_validator("clashes")
    @classmethod
    def validate_clashes_count(cls, v: List[Clash], info: ValidationInfo) -> List[Clash]:
        context = info.context or {}
        config = context.get("config", {})
        nav_toor = config.get("nav_toor", {})
        min_clashes = nav_toor.get("contradiction_map_min_clashes", 3)
        
        if len(v) < min_clashes:
            raise ValueError(f"Must have at least {min_clashes} clashes, got {len(v)}.")
        return v

    @field_validator("strongest_evidence", "weakest_evidence")
    @classmethod
    def validate_evidence(cls, v: str) -> str:
        if not v or v.strip() in ("", "placeholder", "Placeholder", "N/A"):
            raise ValueError("Evidence fields cannot be empty or placeholder.")
        return v

    @field_validator("blind_spots")
    @classmethod
    def validate_blind_spots(cls, v: List[str]) -> List[str]:
        if not v or any(not s.strip() or s.strip() == "placeholder" for s in v):
            raise ValueError("Blind spots cannot be empty or placeholders.")
        return v


# ==============================================================================
# Outline Schema (Stage 3)
# ==============================================================================
class OutlineSection(BaseModel):
    title: str
    description: str
    perspective_coverage: List[str] = Field(default_factory=list)
    contradiction_refs: List[int] = Field(default_factory=list)
    subsections: List[OutlineSection] = Field(default_factory=list)

class OutlineSchema(BaseModel):
    sections: List[OutlineSection]

    @field_validator("sections")
    @classmethod
    def validate_depth_and_coverage(cls, v: List[OutlineSection], info: ValidationInfo) -> List[OutlineSection]:
        if not v:
            raise ValueError("Outline must have sections.")
        
        context = info.context or {}
        config = context.get("config", {})
        nav_toor = config.get("nav_toor", {})
        min_depth = nav_toor.get("min_outline_depth", 2)
        
        # Check depth >= min_depth
        has_depth = False
        all_covered_perspectives = set()

        def collect_coverage_and_check_depth(sec: OutlineSection, depth: int):
            nonlocal has_depth
            if depth >= min_depth:
                has_depth = True
            for tag in sec.perspective_coverage:
                all_covered_perspectives.add(tag)
            for sub in sec.subsections:
                collect_coverage_and_check_depth(sub, depth + 1)

        for section in v:
            collect_coverage_and_check_depth(section, 1)

        if not has_depth:
            raise ValueError(f"Outline depth must be >= {min_depth}.")

        required_list = nav_toor.get("required_perspectives", [])
        required = {p.get("id") for p in required_list} if required_list else {"practitioner", "academic", "skeptic", "economist", "historian"}
        missing = required - all_covered_perspectives
        if missing:
            raise ValueError(f"Outline coverage metadata is missing required perspectives: {missing}")

        return v


# ==============================================================================
# Synthesis Schema (Stage 4)
# ==============================================================================
class KeyFinding(BaseModel):
    finding: str
    reliability_score: int  # 1-10
    source_refs: List[str] = Field(default_factory=list)

    @field_validator("reliability_score")
    @classmethod
    def validate_reliability(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("Reliability score must be between 1 and 10.")
        return v

class SynthesisSchema(BaseModel):
    summary: str
    key_findings: List[KeyFinding]
    hidden_connections: List[str]
    actionable_insight: str

    @field_validator("key_findings")
    @classmethod
    def validate_findings_count(cls, v: List[KeyFinding], info: ValidationInfo) -> List[KeyFinding]:
        context = info.context or {}
        config = context.get("config", {})
        nav_toor = config.get("nav_toor", {})
        min_findings = nav_toor.get("synthesis_min_findings", 5)
        
        if len(v) < min_findings:
            raise ValueError(f"Must have at least {min_findings} key findings, got {len(v)}.")
        return v

    @field_validator("actionable_insight", "summary")
    @classmethod
    def validate_fields(cls, v: str) -> str:
        if not v or v.strip() in ("", "placeholder", "Placeholder"):
            raise ValueError("Summary and Actionable Insight cannot be empty or placeholder.")
        return v


# ==============================================================================
# Article Schema (Stage 5)
# ==============================================================================
class ArticleSection(BaseModel):
    title: str
    content: str
    citation_indices: List[int] = Field(default_factory=list)

class ArticleSchema(BaseModel):
    title: str
    sections: List[ArticleSection]
    citation_references: Dict[str, str] = Field(default_factory=dict)  # maps "[N]" -> URL/source
    word_count_min: int = 500

    @model_validator(mode="after")
    def validate_citations_and_word_count(self, info: ValidationInfo) -> ArticleSchema:
        total_words = 0
        all_cited_indices = set()
        
        for section in self.sections:
            total_words += len(section.content.split())
            # Search for citations like [1], [2] in content
            for match in re.findall(r"\[(\d+)\]", section.content):
                all_cited_indices.add(int(match))

        context = info.context or {}
        config = context.get("config", {})
        nav_toor = config.get("nav_toor", {})
        word_count_min = nav_toor.get("min_word_count", self.word_count_min)

        if total_words < word_count_min:
            raise ValueError(f"Article word count {total_words} is below minimum {word_count_min}.")

        # Enforce that each section content has citations, or at least every factual section
        # Let's verify that the citation indices used in content are declared in citation_references
        for idx in all_cited_indices:
            key = f"[{idx}]"
            if key not in self.citation_references and str(idx) not in self.citation_references:
                raise ValueError(f"Citation index {key} used in text but not found in citation_references.")
                
        return self


# ==============================================================================
# Peer Review Schema (Stage 6)
# ==============================================================================
class PeerReviewSchema(BaseModel):
    confidence_scores: Dict[str, int]
    overall_confidence: int
    bias_check: str
    missing_perspectives: List[str] = Field(default_factory=list)
    overall_grade: str

    @field_validator("overall_confidence")
    @classmethod
    def validate_overall_confidence(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("Overall confidence must be between 1 and 10.")
        return v

    @field_validator("overall_grade")
    @classmethod
    def validate_grade(cls, v: str) -> str:
        allowed = {"A", "B", "C", "D", "E", "F", "A+", "A-", "B+", "B-", "C+", "C-"}
        if v.upper() not in allowed:
            raise ValueError(f"Overall grade '{v}' is invalid. Allowed: {allowed}")
        return v.upper()
