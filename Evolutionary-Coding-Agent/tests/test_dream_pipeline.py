import pytest
from unittest.mock import patch, MagicMock
from src.pipeline import AgentPipeline
from src.config import config_instance

def test_pipeline_dream_injection():
    config_mock = {
        "dreaming.enabled": True,
        "dreaming.max_dream_insights_in_prompt": 3,
        "dreaming.load_dreams_on_frozen": True
    }
    
    # Mock return values for memory retrieval
    mock_dreams = [
        {"id": "drm_mock_1", "content": "Bài học 1", "metadata": {"type": "insight"}},
        {"id": "drm_mock_2", "content": "[SUMMARY] Tóm tắt", "metadata": {"type": "session_summary"}}
    ]
    
    # Mock LLM Client generate
    mock_llm_gen = MagicMock(return_value="```python\ndef run(): pass\n```")
    
    # Mock validation gate
    mock_val_gate = MagicMock(return_value={"status": "passed", "score": 9.0})
    
    # Create pipeline (frozen_memory=True to check signature/reference code inputs too)
    pipeline = AgentPipeline(memory_enabled=True, frozen_memory=True)
    
    task = {
        "id": "SUB_001",
        "description": "Mock SMTP send task",
        "test_code": "def test(): pass"
    }
    
    with patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
        with patch("src.dreaming.dream_loader.dream_loader.format_for_prompt", return_value="=== SESSION WISDOM (DREAM) ===\n- Bài học 1") as mock_format:
            with patch("src.dreaming.dream_store.dream_store.retrieve_dreams", return_value=mock_dreams):
                with patch.object(pipeline.llm, "generate", mock_llm_gen):
                    with patch("src.pipeline.validation_gate.validate_solution", mock_val_gate):
                        
                        res = pipeline.execute_task(task, seed=42)
                        
                        # 1. Verify dream_loader was called
                        mock_format.assert_called_once_with(description=task["description"], task_id=task["id"], limit=3)
                        
                        # 2. Verify dreams_retrieved IDs logged in metadata (excluding [SUMMARY] memory)
                        assert res["dreams_retrieved"] == ["drm_mock_1"]
                        
                        # 3. Verify mock_llm_gen was called with prompt containing the dream block prepended
                        called_prompt = mock_llm_gen.call_args[1]["prompt"]
                        assert called_prompt.startswith("=== SESSION WISDOM (DREAM) ===\n- Bài học 1")
