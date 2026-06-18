import json
import pytest
from unittest.mock import patch, MagicMock
from src.exploration.vertical_gap_analyzer import vertical_gap_analyzer
from src.exploration.curriculum_proposer import curriculum_proposer
from src.config import config_instance
from src.infra.retrieval import HybridVectorDB
from src.memory.memory_engine import memory_engine

@pytest.fixture
def test_db_env(tmp_path):
    db_file = tmp_path / "test_vertical_explore.db"
    config_instance.data["memory"]["sqlite_db_path"] = str(db_file)
    db = HybridVectorDB()
    old_db = memory_engine.db
    memory_engine.db = db
    
    yield db
    
    db.conn.close()
    memory_engine.db = old_db

def test_vertical_explore_targets_propagation(test_db_env):
    emb = [1.0] + [0.0] * 767
    
    # Cover finance vertical, leaving sales and marketing as gaps
    test_db_env.add_memory(
        memory_id="skl_finance_1",
        namespace="skill",
        content="def audit_ledger(): pass",
        embedding=emb,
        task_id="FIN_001",
        status="success",
        importance=8.0,
        metadata={"name": "audit_ledger", "vertical": "finance", "retrievable": True}
    )
    
    # Check vertical gap detection
    gaps = vertical_gap_analyzer.top_vertical_gaps(limit=3)
    assert "sales" in gaps
    assert "marketing" in gaps
    assert "finance" not in gaps
    
    mock_proposal = {
        "title": "Sales discount calculator",
        "description": "Calculate order discount based on customer history",
        "difficulty": "basic",
        "target_skills": ["math"],
        "vertical_target": "sales",
        "rationale": "Close sales vertical gap"
    }
    
    config_mock = {
        "verticals.enabled": True,
        "verticals.explore_target_verticals": True,
        "verticals.allowed": ["sales", "marketing", "finance", "generic"],
        "exploration.max_tasks_per_run": 1,
        "exploration.probe_before_solve": False,
        "memory.sqlite_db_path": config_instance.get("memory.sqlite_db_path"),
        "dreaming.enabled": False
    }
    
    with patch.object(curriculum_proposer.llm, "generate", return_value=json.dumps(mock_proposal)) as mock_gen, \
         patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
         
        proposed = curriculum_proposer.propose(
            success_rate=0.8,
            skill_summaries=["audit_ledger"],
            gap_targets=["math"],
            vertical_targets=gaps
        )
        
        assert proposed.vertical_target == "sales"
        
        mock_gen.assert_called_once()
        args, kwargs = mock_gen.call_args
        prompt = kwargs.get("prompt") if kwargs.get("prompt") else args[0]
        assert "sales" in prompt
        assert "marketing" in prompt
