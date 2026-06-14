import pytest
from unittest.mock import patch, MagicMock
from src.memory.validation_gate import validation_gate

@patch("src.memory.validation_gate.memory_engine")
def test_validate_solution_returns_execution_mode(mock_memory_engine):
    # We test that validate_solution returns execution_mode in its dictionary
    with patch.object(validation_gate.sandbox, 'refuse_fallback', False):
        task_id = "TEST_INTEGRATION_001"
        task_description = "Write a function `add(a, b)` that returns their sum."
        code = "def add(a, b):\n    return a + b"
        test_code = "def test_add():\n    assert add(1, 2) == 3\ntest_add()"
        
        with patch("src.llm.llm_client.generate") as mock_generate:
            mock_generate.return_value = '{"is_passed": true, "score": 9.5, "critique": "Correct solution.", "success_factors": "Proper addition", "lesson_learned": "none"}'
            
            res = validation_gate.validate_solution(
                task_id=task_id,
                task_description=task_description,
                code=code,
                test_code=test_code
            )
            
            assert "execution_mode" in res
            assert res["execution_mode"] in ("docker", "local_subprocess_fallback")
