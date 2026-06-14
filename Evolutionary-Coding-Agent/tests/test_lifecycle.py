import os
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.config import config_instance
from src.infra.retrieval import HybridVectorDB
from src.memory.lifecycle import MemoryLifecycleManager
from src.memory.memory_engine import MemoryEngine

@pytest.fixture
def test_env(tmp_path):
    # Set up temp SQLite database path
    db_file = tmp_path / "test_lifecycle.db"
    orig_path = config_instance.data["memory"].get("sqlite_db_path")
    config_instance.data["memory"]["sqlite_db_path"] = str(db_file)
    
    # Re-instantiate HybridVectorDB and set as global instances
    from src.infra import retrieval
    from src.memory import lifecycle
    from src.memory import memory_engine
    
    db = retrieval.HybridVectorDB()
    retrieval.db_instance = db
    lifecycle.lifecycle_manager.db = db
    memory_engine.memory_engine.db = db
    
    yield db, lifecycle.lifecycle_manager
    
    db.conn.close()
    if orig_path:
        config_instance.data["memory"]["sqlite_db_path"] = orig_path

def test_deduplicate_and_merge(test_env):
    db, mgr = test_env
    
    # 1. Insert an existing memory
    content_old = "Lỗi SyntaxError xảy ra khi thiếu dấu ngoặc đơn ở cuối."
    emb_old = [0.1] * 3072
    db.add_memory("m_old", "insight", content_old, emb_old, "t1", "fail", 7.0)
    
    # 2. Run deduplicate_and_merge with a similar memory
    content_new = "Có lỗi SyntaxError do thiếu dấu ngoặc đơn kết thúc."
    
    # Mock LLM calls (embed and generate)
    with patch("src.llm.llm_client.embed") as mock_embed, \
         patch("src.llm.llm_client.generate") as mock_generate:
         
        mock_embed.return_value = [0.1] * 3072 # Same embedding to trigger dedup_threshold
        mock_generate.return_value = '{"merged_content": "SyntaxError khi thiếu ngoặc đơn kết thúc.", "new_importance": 8.5}'
        
        is_merged, old_id = mgr.deduplicate_and_merge("insight", content_new, 8.0, "fail", {})
        
        assert is_merged is True
        assert old_id == "m_old"
        
        # Verify db contains merged memory and only 1 record
        memories = db.get_all_memories("insight")
        assert len(memories) == 1
        assert memories[0]["content"] == "SyntaxError khi thiếu ngoặc đơn kết thúc."
        assert memories[0]["importance"] == 8.5

def test_resolve_conflicts_delete_old(test_env):
    db, mgr = test_env
    
    # 1. Insert old memory
    db.add_memory("m1", "insight", "Hãy sử dụng Python 3.10", [0.1]*3072, "t1", "success", 8.0)
    
    # 2. Try to add contradicting memory: "Không dùng Python 3.10"
    with patch("src.llm.llm_client.embed") as mock_embed, \
         patch("src.llm.llm_client.generate") as mock_generate:
         
        mock_embed.return_value = [0.1]*3072
        mock_generate.return_value = '{"has_conflict": true, "resolution_action": "delete_old", "resolved_content": "Không dùng Python 3.10"}'
        
        mgr.resolve_conflicts("insight", "Không dùng Python 3.10")
        
        # Verify old memory was deleted
        memories = db.get_all_memories("insight")
        assert len(memories) == 0

def test_enforce_capacity(test_env):
    db, mgr = test_env
    
    # Force max capacity to 2
    mgr.max_capacity = 2
    
    # Add 3 memories (different ages and importances)
    import time
    t_now = time.time()
    
    # Lowest generic score: low importance + older age
    db.add_memory("m1", "insight", "Low importance old", [0.1]*3072, "t1", "success", 1.0)
    # Update created_at to make it older (e.g. 10 hours ago)
    with db.conn:
        db.conn.execute("UPDATE memories SET created_at = ? WHERE id = ?", (t_now - 36000, "m1"))
        
    db.add_memory("m2", "insight", "High importance", [0.1]*3072, "t2", "success", 9.0)
    db.add_memory("m3", "insight", "Medium importance", [0.1]*3072, "t3", "success", 5.0)
    
    # Enforce capacity
    mgr.enforce_capacity("insight")
    
    # Verify we only have 2 memories left, and the lowest score one ("m1") was deleted
    memories = db.get_all_memories("insight")
    assert len(memories) == 2
    remaining_ids = [m["id"] for m in memories]
    assert "m1" not in remaining_ids
    assert "m2" in remaining_ids
    assert "m3" in remaining_ids
