import os
import sqlite3
import json
import time
import math
import numpy as np
from src.config import config_instance

class HybridVectorDB:
    def __init__(self):
        self.db_path = config_instance.get("memory.sqlite_db_path", "data/memory/memory.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.setup_tables()

    def setup_tables(self):
        with self.conn:
            # Main memories table
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    task_id TEXT,
                    status TEXT,
                    created_at REAL NOT NULL,
                    importance REAL DEFAULT 5.0,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    metadata TEXT
                )
            """)
            # Create indexes
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_task_id ON memories(task_id)")
            
            # FTS5 Virtual table for sparse search (BM25)
            # FTS5 comes built-in with Python's sqlite3 on most platforms (Windows/Linux/macOS)
            try:
                self.conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                        id UNINDEXED,
                        content
                    )
                """)
            except sqlite3.OperationalError:
                # FTS5 might not be compiled in some extreme cases, fallback to FTS4
                print("Warning: FTS5 not available. Falling back to FTS4.")
                self.conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts4(
                        id,
                        content
                    )
                """)

    def add_memory(self, memory_id: str, namespace: str, content: str, embedding: list[float], task_id: str = None, status: str = None, importance: float = 5.0, metadata: dict = None) -> bool:
        # Convert embedding to bytes (float32 array)
        emb_array = np.array(embedding, dtype=np.float32)
        emb_blob = emb_array.tobytes()
        
        metadata_str = json.dumps(metadata) if metadata else None
        created_at = time.time()
        
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO memories (id, namespace, task_id, status, created_at, importance, content, embedding, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (memory_id, namespace, task_id, status, created_at, importance, content, emb_blob, metadata_str)
                )
                self.conn.execute(
                    "INSERT INTO memories_fts (id, content) VALUES (?, ?)",
                    (memory_id, content)
                )
            return True
        except Exception as e:
            print(f"Error adding memory: {e}")
            return False

    def delete_memory(self, memory_id: str) -> bool:
        try:
            with self.conn:
                self.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                self.conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            return True
        except Exception as e:
            print(f"Error deleting memory: {e}")
            return False

    def clear_namespace(self, namespace: str) -> bool:
        try:
            with self.conn:
                # Fetch ids first to delete from FTS
                cursor = self.conn.execute("SELECT id FROM memories WHERE namespace = ?", (namespace,))
                ids = [row["id"] for row in cursor.fetchall()]
                for memory_id in ids:
                    self.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                    self.conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            return True
        except Exception as e:
            print(f"Error clearing namespace {namespace}: {e}")
            return False

    def get_all_memories(self, namespace: str = None) -> list[dict]:
        cursor = self.conn.cursor()
        if namespace:
            cursor.execute("SELECT id, namespace, task_id, status, created_at, importance, content, embedding, metadata FROM memories WHERE namespace = ?", (namespace,))
        else:
            cursor.execute("SELECT id, namespace, task_id, status, created_at, importance, content, embedding, metadata FROM memories")
            
        rows = cursor.fetchall()
        memories = []
        for r in rows:
            emb_array = np.frombuffer(r["embedding"], dtype=np.float32)
            memories.append({
                "id": r["id"],
                "namespace": r["namespace"],
                "task_id": r["task_id"],
                "status": r["status"],
                "created_at": r["created_at"],
                "importance": r["importance"],
                "content": r["content"],
                "embedding": emb_array.tolist(),
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {}
            })
        return memories

    def search_memories(self, namespace: str, query_text: str, query_embedding: list[float], limit: int = 5, filters: dict = None) -> list[dict]:
        """
        Perform a hybrid dense (vector similarity) + sparse (BM25) search with metadata filtering
        and a customized retrieval score = relevance * w_rel + importance * w_imp + recency * w_rec.
        """
        # 1. Fetch candidates from database using metadata filters first
        # We load candidates matching namespace and any filters into memory, then compute cosine similarity.
        query_parts = ["namespace = ?"]
        query_params = [namespace]
        
        if filters:
            for col, val in filters.items():
                if col in ["status", "task_id"]:
                    query_parts.append(f"{col} = ?")
                    query_params.append(val)
                elif col == "importance_min":
                    query_parts.append("importance >= ?")
                    query_params.append(val)
                    
        where_clause = " AND ".join(query_parts)
        
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT id, created_at, importance, content, embedding, metadata, status, task_id FROM memories WHERE {where_clause}",
            query_params
        )
        candidates = cursor.fetchall()
        
        if not candidates:
            return []
            
        # Convert search query embedding to numpy array
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        
        candidate_list = []
        
        # 2. Dense search: Compute Cosine Similarity for each candidate
        for c in candidates:
            emb_bytes = c["embedding"]
            c_vec = np.frombuffer(emb_bytes, dtype=np.float32)
            c_norm = np.linalg.norm(c_vec)
            
            if q_norm > 0 and c_norm > 0:
                cosine_sim = float(np.dot(q_vec, c_vec) / (q_norm * c_norm))
            else:
                cosine_sim = 0.0
                
            # Cosine similarity is in [-1, 1], normalize to [0, 1]
            cosine_sim = (cosine_sim + 1.0) / 2.0
            
            candidate_list.append({
                "id": c["id"],
                "created_at": c["created_at"],
                "importance": c["importance"],
                "content": c["content"],
                "status": c["status"],
                "task_id": c["task_id"],
                "metadata": json.loads(c["metadata"]) if c["metadata"] else {},
                "dense_score": cosine_sim,
                "sparse_score": 0.0  # Default sparse score if no FTS match
            })
            
        # 3. Sparse search: BM25 score via FTS5
        # Search for query_text in FTS table
        # Pre-process query to prevent syntax errors (escape double quotes, strip special chars)
        import re
        # Strip all special characters that might trigger FTS5 operator syntax errors
        clean_query = re.sub(r'[^\w\s\d\u00C0-\u1EF9]', ' ', query_text) # support Vietnamese characters too
        clean_query = re.sub(r'\s+', ' ', clean_query).strip()
        if clean_query:
            try:
                # FTS5 match search
                # bm25() score is negative (more negative is better match), so we negate it.
                fts_query = f"""
                    SELECT id, -bm25(memories_fts) as score 
                    FROM memories_fts 
                    WHERE memories_fts MATCH ?
                """
                fts_cursor = self.conn.execute(fts_query, (clean_query,))
                fts_scores = {row["id"]: row["score"] for row in fts_cursor.fetchall()}
                
                # Assign sparse scores to candidates
                for cand in candidate_list:
                    if cand["id"] in fts_scores:
                        cand["sparse_score"] = fts_scores[cand["id"]]
            except Exception as e:
                print(f"BM25 Search failed: {e}")
                
        # 4. Normalize scores and calculate hybrid relevance
        # Scale dense scores to [0, 1]
        dense_scores = [c["dense_score"] for c in candidate_list]
        max_dense = max(dense_scores) if dense_scores else 1.0
        min_dense = min(dense_scores) if dense_scores else 0.0
        
        # Scale sparse scores to [0, 1]
        sparse_scores = [c["sparse_score"] for c in candidate_list]
        max_sparse = max(sparse_scores) if sparse_scores else 1.0
        min_sparse = min(sparse_scores) if sparse_scores else 0.0
        
        for cand in candidate_list:
            d_norm = (cand["dense_score"] - min_dense) / (max_dense - min_dense + 1e-9) if max_dense > min_dense else cand["dense_score"]
            s_norm = (cand["sparse_score"] - min_sparse) / (max_sparse - min_sparse + 1e-9) if max_sparse > min_sparse else cand["sparse_score"]
            
            # Hybrid relevance (dense has 0.7 weight, sparse/keyword has 0.3)
            cand["relevance_score"] = 0.7 * d_norm + 0.3 * s_norm
            
        # 5. Calculate final score = relevance * w_rel + importance * w_imp + recency * w_rec
        current_time = time.time()
        decay_rate = config_instance.get("memory.decay_rate", 0.01)
        w_rel = config_instance.get("memory.weights.relevance", 0.5)
        w_imp = config_instance.get("memory.weights.importance", 0.3)
        w_rec = config_instance.get("memory.weights.recency", 0.2)
        
        for cand in candidate_list:
            # Importance normalization: [0, 1] (importance ranges 1-10)
            imp_score = cand["importance"] / 10.0
            
            # Recency: exponential decay in hours
            age_hours = (current_time - cand["created_at"]) / 3600.0
            rec_score = math.exp(-decay_rate * age_hours)
            
            cand["recency_score"] = rec_score
            cand["importance_score"] = imp_score
            
            # Final scoring
            cand["final_score"] = (w_rel * cand["relevance_score"] + 
                                   w_imp * imp_score + 
                                   w_rec * rec_score)
            
        # Sort candidates by final score in descending order
        candidate_list.sort(key=lambda x: x["final_score"], reverse=True)
        
        # Return top-limit results (using Reranker if enabled)
        return self.rerank_memories(query_text, candidate_list, limit)

    def rerank_memories(self, query_text: str, candidates: list[dict], limit: int) -> list[dict]:
        use_reranker = config_instance.get("memory.use_reranker", True)
        if not use_reranker or not candidates:
            return candidates[:limit]

        from src.llm import llm_client
        # Take up to 10 candidates to rerank
        pool = candidates[:10]
        
        # Format candidates for LLM prompt
        items_str = ""
        for i, c in enumerate(pool):
            items_str += f"ID: {c['id']}\nNội dung: {c['content']}\n\n"
            
        system_instruction = (
            "Bạn là một hệ thống xếp hạng thông tin (Reranker). "
            "Nhiệm vụ của bạn là chọn ra tối đa các phần tử liên quan nhất tới câu hỏi và xếp hạng chúng theo thứ tự giảm dần của độ liên quan. "
            "Trả về JSON."
        )
        
        prompt = f"""
Câu hỏi/Mục tiêu:
"{query_text}"

Danh sách các tài liệu tìm thấy:
{items_str}

Hãy chọn ra tối đa {limit} tài liệu liên quan nhất và xếp hạng ID của chúng từ cao xuống thấp.
"""
        try:
            res_str = llm_client.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1,
                json_mode=True,
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "ranked_ids": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"}
                        }
                    },
                    "required": ["ranked_ids"]
                }
            )
            data = json.loads(res_str)
            ranked_ids = data.get("ranked_ids", [])
            
            # Reorder pool according to ranked_ids
            id_to_cand = {c["id"]: c for c in pool}
            reranked = []
            for rid in ranked_ids:
                if rid in id_to_cand:
                    reranked.append(id_to_cand[rid])
                    
            # Add any candidates that were in pool but not included in ranked_ids
            for c in pool:
                if c not in reranked:
                    reranked.append(c)
                    
            return reranked[:limit]
        except Exception as e:
            print(f"Reranking failed: {e}. Falling back to default order.")
            return candidates[:limit]

    def evaluate_retrieval_recall(self) -> float:
        """
        Runs a small diagnostic evaluation of search Recall@3.
        Creates temporary memories, queries them, and checks recall.
        """
        test_namespace = "test_recall_ns"
        self.clear_namespace(test_namespace)
        
        # Inject mock memories
        m1_content = "Hàm xử lý tách chuỗi regex email trong Python"
        m2_content = "Cách tạo và cấu hình docker container memory limit"
        m3_content = "Cách truy vấn sqlite FTS5 và tìm kiếm từ khóa BM25"
        
        from src.llm import llm_client
        try:
            emb1 = llm_client.embed(m1_content)
            emb2 = llm_client.embed(m2_content)
            emb3 = llm_client.embed(m3_content)
        except Exception:
            emb1 = [0.1] * 3072
            emb2 = [0.2] * 3072
            emb3 = [0.3] * 3072
            
        self.add_memory("rec_1", test_namespace, m1_content, emb1, "t1", "success", 8.0)
        self.add_memory("rec_2", test_namespace, m2_content, emb2, "t2", "success", 7.0)
        self.add_memory("rec_3", test_namespace, m3_content, emb3, "t3", "success", 9.0)
        
        # Perform 3 test queries
        queries = [
            ("tách email", "rec_1"),
            ("docker memory limit", "rec_2"),
            ("sqlite fts5", "rec_3")
        ]
        
        hits = 0
        for query_text, expected_id in queries:
            try:
                q_emb = llm_client.embed(query_text)
            except Exception:
                q_emb = [0.1] * 3072
            # Disable reranker for raw retrieval test
            orig_use_reranker = config_instance.data["memory"].get("use_reranker", True)
            config_instance.data["memory"]["use_reranker"] = False
            results = self.search_memories(test_namespace, query_text, q_emb, limit=3)
            config_instance.data["memory"]["use_reranker"] = orig_use_reranker
            
            retrieved_ids = [r["id"] for r in results]
            if expected_id in retrieved_ids:
                hits += 1
                
        # Clean up
        self.clear_namespace(test_namespace)
        
        recall = hits / len(queries)
        print(f"Retrieval Recall@3 Diagnostic: {recall * 100:.1f}% ({hits}/{len(queries)})")
        return recall

# Global vector DB instance
db_instance = HybridVectorDB()
