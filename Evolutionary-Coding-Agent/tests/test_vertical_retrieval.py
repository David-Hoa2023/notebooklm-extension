import pytest
import numpy as np
from unittest.mock import patch
from src.infra.retrieval import HybridVectorDB
from src.memory.memory_engine import memory_engine
from src.pipeline import AgentPipeline
from src.config import config_instance

@pytest.fixture
def test_db_env(tmp_path):
    db_file = tmp_path / "test_vertical_retrieval.db"
    config_instance.data["memory"]["sqlite_db_path"] = str(db_file)
    db = HybridVectorDB()
    old_db = memory_engine.db
    memory_engine.db = db
    
    yield db
    
    db.conn.close()
    memory_engine.db = old_db

def test_strict_and_prefer_vertical_retrieval(test_db_env):
    emb = [1.0] + [0.0] * 767
    
    # Seed active retrievable skills
    test_db_env.add_memory(
        memory_id="skl_sales_1",
        namespace="skill",
        content="def get_sales_total(): pass",
        embedding=emb,
        task_id="SLS_001",
        status="success",
        importance=8.0,
        metadata={"name": "get_sales_total", "vertical": "sales", "retrievable": True, "domain": "math"}
    )
    
    test_db_env.add_memory(
        memory_id="skl_finance_1",
        namespace="skill",
        content="def audit_ledger(): pass",
        embedding=emb,
        task_id="FIN_001",
        status="success",
        importance=8.0,
        metadata={"name": "audit_ledger", "vertical": "finance", "retrievable": True, "domain": "math"}
    )
    
    config_mock = {
        "verticals.enabled": True,
        "verticals.retrieval_mode": "strict",
        "verticals.explore_target_verticals": True,
        "memory.sqlite_db_path": config_instance.get("memory.sqlite_db_path"),
        "dreaming.enabled": False
    }
    
    task = {
        "id": "FIN_LEDGER_001",
        "title": "Audit financial ledger balance",
        "description": "audit ledger calculations and invoice matching",
        "test_code": "def test(): pass",
        "vertical": "finance"
    }
    
    pipeline = AgentPipeline(memory_enabled=True, frozen_memory=False)
    
    with patch.object(pipeline.llm, "generate", return_value="```python\ndef audit_ledger(): pass\n```"), \
         patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
         
        res = pipeline.execute_task(task)
        retrieved_ids = res.get("skills_retrieved", [])
        
        # Strict mode: exclude sales-scoped skills from finance task
        assert "skl_finance_1" in retrieved_ids
        assert "skl_sales_1" not in retrieved_ids

    # Test prefer mode
    config_mock["verticals.retrieval_mode"] = "prefer"
    
    with patch.object(pipeline.llm, "generate", return_value="```python\ndef audit_ledger(): pass\n```"), \
         patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
         
        res = pipeline.execute_task(task)
        retrieved_ids = res.get("skills_retrieved", [])
        
        # Prefer mode: retrieve all, but rank matching vertical first
        assert "skl_finance_1" in retrieved_ids
        assert "skl_sales_1" in retrieved_ids
        
        fin_idx = retrieved_ids.index("skl_finance_1")
        sales_idx = retrieved_ids.index("skl_sales_1")
        assert fin_idx < sales_idx
