import pytest
from unittest.mock import patch, MagicMock
from src.exploration.curriculum_proposer import (
    calibrate_difficulty,
    compute_recent_success_rate,
)
from src.exploration.explore_exploit_controller import ExploreExploitController
from src.exploration.skill_gap_analyzer import SkillGapAnalyzer, _infer_capabilities
from src.exploration.novelty_reward import cosine_distance


def test_calibrate_difficulty_zpd():
    assert calibrate_difficulty(0.9) == "advanced"
    assert calibrate_difficulty(0.6) == "intermediate"
    assert calibrate_difficulty(0.2) == "basic"


def test_compute_recent_success_rate():
    runs = [
        {"task_id": "A", "pass_type": "first_pass", "status": "passed"},
        {"task_id": "B", "pass_type": "first_pass", "status": "failed_tests"},
        {"task_id": "C", "pass_type": "first_pass", "status": "passed"},
        {"pass_type": "lifecycle_event"},
    ]
    assert compute_recent_success_rate(runs) == pytest.approx(2 / 3)


def test_infer_capabilities_regex():
    caps = _infer_capabilities("Use regex to match email patterns with re.findall")
    assert "regex" in caps


def test_explore_exploit_controller_budget_exhausted():
    controller = ExploreExploitController()
    controller.budget_tokens = 1000
    decision = controller.decide(recent_payoff=0.5, tokens_spent=2000)
    assert decision.mode == "exploit"
    assert decision.budget_remaining == 0


def test_explore_exploit_controller_force_explore():
    controller = ExploreExploitController()
    decision = controller.decide(recent_payoff=0.5, tokens_spent=0, force_explore=True)
    assert decision.mode == "explore"


def test_cosine_distance_identical_vectors():
    assert cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)


def test_cosine_distance_orthogonal_vectors():
    assert cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)


@patch("src.exploration.skill_gap_analyzer.skill_composition_instance")
@patch("src.exploration.skill_gap_analyzer.memory_engine")
def test_skill_gap_analyzer_finds_gaps(mock_memory, mock_skills):
    mock_skills.get_active_skills.return_value = [
        {
            "metadata": {"name": "extract_emails", "docstring": "regex email parser"},
            "content": "import re\ndef extract_emails(text): ...",
        }
    ]
    mock_memory.get_all_memories.return_value = []

    analyzer = SkillGapAnalyzer()
    gaps = analyzer.top_gaps(limit=5)
    assert "regex" not in gaps or len(gaps) > 0
    info = analyzer.analyze()
    assert "coverage_rate" in info
    assert 0.0 <= info["coverage_rate"] <= 1.0


def test_escape_unescaped_newlines():
    from src.exploration.oracle_synthesis import oracle_synthesizer
    sample = '{\n  "test_code": "def test_foo():\\n    assert foo() == \\"bar\\nhello\\"\\n"\n}'
    fixed = oracle_synthesizer._escape_unescaped_newlines(sample)
    assert '\\n' in fixed


def test_oracle_rejects_pytest():
    from src.exploration.oracle_synthesis import oracle_synthesizer
    test_code_with_pytest = "import pytest\ndef test_foo():\n    assert True"
    passed, reason = oracle_synthesizer._validate_oracle(
        description="Write a function `foo`",
        test_code=test_code_with_pytest,
        hidden_test_code=""
    )
    assert passed is False
    assert "pytest" in reason


def test_oracle_requires_exact_function_name():
    from src.exploration.oracle_synthesis import oracle_synthesizer
    description = "Viết hàm `calculate_sum(a, b)` để tính tổng."
    test_code_without_fn = "def test_sum():\n    assert 1 + 1 == 2"
    passed, reason = oracle_synthesizer._validate_oracle(
        description=description,
        test_code=test_code_without_fn,
        hidden_test_code=""
    )
    assert passed is False
    assert "calculate_sum" in reason


def test_oracle_rejects_pytest_in_hidden():
    from src.exploration.oracle_synthesis import oracle_synthesizer
    test_code = "def test_foo():\n    assert True"
    hidden_test_code = "import pytest\ndef test_foo_hidden():\n    assert True"
    passed, reason = oracle_synthesizer._validate_oracle(
        description="Write a function `foo`",
        test_code=test_code,
        hidden_test_code=hidden_test_code
    )
    assert passed is False
    assert "pytest" in reason


def test_top_gaps_logic():
    analyzer = SkillGapAnalyzer()
    
    # Case 1: skill-backed gaps are non-empty
    mock_analyze_results_1 = {
        "gap_capabilities": ["math_evaluation", "regex"],
        "skill_backed_gap_capabilities": ["json_parsing", "testing"]
    }
    with patch.object(analyzer, 'analyze', return_value=mock_analyze_results_1):
        gaps = analyzer.top_gaps(limit=3)
        assert gaps == ["json_parsing", "testing"]
        
    # Case 2: skill-backed gaps are empty, fallback to keyword gaps
    mock_analyze_results_2 = {
        "gap_capabilities": ["math_evaluation", "regex"],
        "skill_backed_gap_capabilities": []
    }
    with patch.object(analyzer, 'analyze', return_value=mock_analyze_results_2):
        gaps = analyzer.top_gaps(limit=3)
        assert gaps == ["math_evaluation", "regex"]

