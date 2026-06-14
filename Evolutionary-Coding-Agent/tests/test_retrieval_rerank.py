import pytest
from unittest.mock import MagicMock, patch
from src.config import config_instance
from src.infra.retrieval import HybridVectorDB

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_retrieval_rerank.db"
    orig_path = config_instance.data["memory"].get("sqlite_db_path")
    config_instance.data["memory"]["sqlite_db_path"] = str(db_file)
    db = HybridVectorDB()
    yield db
    db.conn.close()
    if orig_path:
        config_instance.data["memory"]["sqlite_db_path"] = orig_path

def test_rerank_disabled(temp_db):
    config_instance.data["memory"]["use_reranker"] = False
    
    candidates = [
        {"id": "m1", "content": "Regex email logic", "final_score": 0.9},
        {"id": "m2", "content": "Docker memory settings", "final_score": 0.8}
    ]
    
    # Reranking is disabled, should just return candidates directly up to limit
    res = temp_db.rerank_memories("email", candidates, limit=1)
    assert len(res) == 1
    assert res[0]["id"] == "m1"

def test_rerank_enabled_success(temp_db):
    config_instance.data["memory"]["use_reranker"] = True
    
    candidates = [
        {"id": "m1", "content": "Regex email logic", "final_score": 0.9},
        {"id": "m2", "content": "Docker memory settings", "final_score": 0.8}
    ]
    
    with patch("src.llm.llm_client.generate") as mock_generate:
        # LLM decides that m2 is more relevant than m1
        mock_generate.return_value = '{"ranked_ids": ["m2", "m1"]}'
        
        res = temp_db.rerank_memories("docker", candidates, limit=2)
        assert len(res) == 2
        assert res[0]["id"] == "m2"
        assert res[1]["id"] == "m1"

def test_evaluate_retrieval_recall(temp_db):
    with patch("src.llm.llm_client.embed") as mock_embed:
        # Mock embeddings to be random vectors
        mock_embed.return_value = [0.1] * 3072
        
        recall = temp_db.evaluate_retrieval_recall()
        # Should return a float between 0.0 and 1.0
        assert isinstance(recall, float)
        assert 0.0 <= recall <= 1.0
