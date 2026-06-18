import json
import pytest
from unittest.mock import patch, MagicMock
from src.dreaming.dream_distiller import dream_distiller
from src.config import config_instance

def test_dream_distiller_safety_filters():
    # Mock trace bundle
    bundle = {
        "runs": [
            {"task_id": "SUB_001", "status": "passed"},
            {"task_id": "SUB_002", "status": "failed"}
        ]
    }
    
    # Mock LLM Client generate to return a set of insights:
    # 1. Valid insight
    # 2. Insight with low confidence
    # 3. Insight with empty evidence_task_ids
    # 4. Insight with evidence task id not in the bundle
    mock_result = {
        "session_summary": "Tóm tắt session",
        "noise_discarded_summary": "Ban đầu sạch",
        "insights": [
            {
                "content": "Bài học tốt 1",
                "importance": 7.0,
                "evidence_task_ids": ["SUB_001"],
                "scope": "global",
                "domain": "smtp",
                "confidence": 0.9
            },
            {
                "content": "Bài học tự tin thấp",
                "importance": 5.0,
                "evidence_task_ids": ["SUB_001"],
                "scope": "global",
                "domain": "regex",
                "confidence": 0.4 # Below min_confidence 0.6
            },
            {
                "content": "Bài học thiếu bằng chứng",
                "importance": 8.0,
                "evidence_task_ids": [], # Empty
                "scope": "task",
                "domain": "smtp",
                "confidence": 0.8
            },
            {
                "content": "Bài học sai bằng chứng",
                "importance": 6.0,
                "evidence_task_ids": ["SUB_999"], # SUB_999 not in runs
                "scope": "global",
                "domain": "math",
                "confidence": 0.7
            }
        ]
    }
    
    config_mock = {
        "dreaming.token_budget": 150000,
        "dreaming.min_confidence": 0.6
    }
    
    # Mock LLM Client generate
    with patch.object(dream_distiller.llm, "generate", return_value=json.dumps(mock_result)) as mock_gen:
        with patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
            res = dream_distiller.distill(bundle)
            
            # Assertions
            # 1. Only the first (valid) insight should be kept
            assert len(res["insights"]) == 1
            assert res["insights"][0]["content"] == "Bài học tốt 1"
            
            # 2. Check noise_discarded_summary updates
            noise = res["noise_discarded_summary"]
            assert "low confidence (0.4 < 0.6)" in noise
            assert "empty evidence_task_ids" in noise
            assert "evidence task_ids ['SUB_999'] are not in the session bundle" in noise
            
            # 3. Verify generate call arguments
            mock_gen.assert_called_once()
