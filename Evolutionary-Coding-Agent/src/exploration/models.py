from pydantic import BaseModel, Field


class ProposedTask(BaseModel):
    id: str
    title: str
    description: str
    difficulty: str = Field(description="basic | intermediate | advanced")
    target_skills: list[str] = Field(default_factory=list)
    rationale: str = ""
    source: str = "curriculum_proposer"
    novelty_score: float = 0.0
    skill_gap_targets: list[str] = Field(default_factory=list)


class ProbeAction(BaseModel):
    purpose: str
    code: str


class ProbeResult(BaseModel):
    purpose: str
    code: str
    stdout: str
    stderr: str
    status: str
    execution_mode: str = "unknown"


class OracleBundle(BaseModel):
    test_code: str
    hidden_test_code: str = ""
    validation_passed: bool = False
    rejection_reason: str = ""


class ExplorationDecision(BaseModel):
    mode: str = Field(description="explore | exploit")
    epsilon: float
    budget_remaining: int
    rationale: str = ""
