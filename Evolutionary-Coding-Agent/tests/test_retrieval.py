import os
import pytest
import numpy as np
from src.infra.retrieval import HybridVectorDB
from src.config import config_instance

@pytest.fixture
def temp_db(tmp_path):
    # Set a temporary database path for tests
    db_file = tmp_path / "test_memory.db"
    config_instance.data["memory"]["sqlite_db_path"] = str(db_file)
    db = HybridVectorDB()
    yield db
    # Close connection
    db.conn.close()

def test_db_add_and_retrieve(temp_db):
    memory_id = "test_1"
    content = "Viết hàm extract_emails để tìm địa chỉ email trong chuỗi."
    embedding = np.random.randn(768).tolist()
    
    # Add memory
    success = temp_db.add_memory(
        memory_id=memory_id,
        namespace="skill",
        content=content,
        embedding=embedding,
        task_id="TASK_01",
        status="success",
        importance=8.0,
        metadata={"name": "extract_emails"}
    )
    assert success is True
    
    # Query it back
    res = temp_db.get_all_memories(namespace="skill")
    assert len(res) == 1
    assert res[0]["id"] == memory_id
    assert res[0]["content"] == content
    assert res[0]["importance"] == 8.0
    assert res[0]["metadata"]["name"] == "extract_emails"

def test_db_hybrid_search(temp_db):
    # Insert multiple records
    emb1 = [1.0] + [0.0] * 767
    emb2 = [0.0, 1.0] + [0.0] * 766
    
    temp_db.add_memory("m1", "insight", "Lưu ý lỗi SyntaxError khi dùng regex", emb1, "T1", "fail", 7.0)
    temp_db.add_memory("m2", "insight", "Cách cấu hình Docker memory limit hợp lý", emb2, "T2", "success", 9.0)
    
    # Search for "regex" (should trigger BM25 match on m1)
    results = temp_db.search_memories(
        namespace="insight",
        query_text="regex",
        query_embedding=emb1,
        limit=2
    )
    
    assert len(results) >= 1
    # m1 should be the top match because of keyword match and embedding similarity
    assert results[0]["id"] == "m1"
    
    # Search with filters
    results_filtered = temp_db.search_memories(
        namespace="insight",
        query_text="regex",
        query_embedding=emb1,
        limit=2,
        filters={"status": "success"}
    )
    # m1 is status='fail', m2 is status='success'. Filtered query should return only m2 (or empty if it doesn't match at all, but here we search inside 'insight')
    assert len(results_filtered) == 1
    assert results_filtered[0]["id"] == "m2"
