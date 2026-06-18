import json
import time
import numpy as np
from pydantic import BaseModel
from src.infra.retrieval import db_instance
from src.llm import llm_client
from src.config import config_instance
from src.observability import observability_manager


class MemoryMerge(BaseModel):
    merged_content: str
    new_importance: float

class ConflictResolution(BaseModel):
    has_conflict: bool
    resolution_action: str  # "update_old" | "delete_old" | "keep_both"
    resolved_content: str

class MemoryLifecycleManager:
    def __init__(self):
        self.db = db_instance
        self.llm = llm_client
        self.dedup_threshold = config_instance.get("memory.dedup_threshold", 0.85)
        self.max_capacity = config_instance.get("memory.max_capacity", 500)

    def deduplicate_and_merge(self, namespace: str, new_content: str, new_importance: float, status: str = None, metadata: dict = None) -> tuple[bool, str]:
        """
        Check if a highly similar memory already exists. If yes, merge them using LLM.
        Returns (is_merged, memory_id).
        """
        # Embed new content to do similarity search
        try:
            emb = self.llm.embed(new_content)
        except Exception as e:
            print(f"Embedding error during deduplication: {e}")
            return False, ""
            
        # Search the database for top candidates in this namespace
        # We look for similarity > dedup_threshold.
        # Note: search_memories returns sorted list by final_score. 
        # We will extract dense_score (cosine similarity) directly.
        candidates = self.db.search_memories(namespace, new_content, emb, limit=3)
        
        duplicate = None
        for c in candidates:
            # check cosine similarity (dense_score is the normalized similarity [0, 1])
            # dense_score in retrieval.py is (cosine_similarity + 1)/2. 
            # Let's convert it back to normal cosine similarity, or compare normalized score
            # A normalized score of 0.92+ roughly corresponds to 0.85+ similarity.
            # Let's check if dense_score >= self.dedup_threshold
            if c["dense_score"] >= self.dedup_threshold:
                duplicate = c
                break
                
        if not duplicate:
            return False, ""
            
        # Merge duplicate with new_content using LLM
        old_id = duplicate["id"]
        old_content = duplicate["content"]
        
        if namespace == "skill":
            system_instruction = (
                "You are a software architect memory manager. Your task is to merge two similar Python utility functions "
                "(old and new versions) into a single, clean, valid Python code block. Return the result in JSON."
            )
            prompt = f"""
Old Python utility function code:
```python
{old_content}
```

New Python utility function code:
```python
{new_content}
```

Please merge these two Python functions into a single code block. Ensure:
1. The output is valid, clean, and executable Python code containing the necessary functions.
2. Do not include explanations, markdown formatting, or comments outside the code.
3. Do not write in Vietnamese description. The output must be Python code.
4. Re-evaluate the importance (1-10 scale) based on both (old importance: {duplicate['importance']}, new importance: {new_importance}).
"""
        else:
            system_instruction = (
                "Bạn là trợ lý quản lý bộ nhớ. Nhiệm vụ của bạn là gộp hai thông tin tương đồng "
                "(một cũ, một mới) thành một thông tin duy nhất đầy đủ, súc tích và cập nhật nhất. Trả về dạng JSON."
            )
            prompt = f"""
Thông tin cũ trong bộ nhớ:
"{old_content}"

Thông tin mới cần nạp:
"{new_content}"

Hãy gộp chúng lại sao cho không mất thông tin quan trọng của cả hai, viết bằng tiếng Việt ngắn gọn.
Đồng thời, đánh giá lại độ quan trọng (thang điểm 10) dựa trên tầm quan trọng của cả hai (độ quan trọng cũ: {duplicate['importance']}, độ quan trọng mới: {new_importance}).
"""
        try:
            res_str = self.llm.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1,
                json_mode=True,
                response_schema=MemoryMerge
            )
            res_data = json.loads(res_str)
            merged_content = res_data.get("merged_content", new_content)
            merged_importance = res_data.get("new_importance", max(duplicate["importance"], new_importance))
            
            # Merge duplicate metadata and new metadata
            old_meta = duplicate.get("metadata", {}) or {}
            new_meta = metadata or {}
            
            old_tasks = old_meta.get("source_tasks", [])
            new_tasks = new_meta.get("source_tasks", [])
            merged_tasks = list(set(old_tasks + new_tasks))
            
            final_metadata = new_meta.copy()
            final_metadata["source_tasks"] = merged_tasks
            final_metadata["version"] = config_instance.get("project.version", "1.0.0")
            
            # Update database
            # Remove old
            self.db.delete_memory(old_id)
            
            # Insert merged as new memory (to refresh timestamp)
            new_emb = self.llm.embed(merged_content)
            self.db.add_memory(
                memory_id=old_id, # keep same ID to preserve references
                namespace=namespace,
                content=merged_content,
                embedding=new_emb,
                task_id=duplicate["task_id"],
                status=status or duplicate["status"],
                importance=merged_importance,
                metadata=final_metadata
            )
            
            # Print log
            print(f"Memory Deduplication: Merged new entry into existing memory '{old_id}'.")
            observability_manager.log_lifecycle_event(
                event_type="deduplication",
                namespace=namespace,
                detail={"old_id": old_id, "merged_content": merged_content, "importance": merged_importance}
            )
            return True, old_id
            
        except Exception as e:
            print(f"Error merging duplicate memories: {e}")
            # Fallback: just return false, let it write a new record
            return False, ""

    def resolve_conflicts(self, namespace: str, new_content: str) -> None:
        """
        Check for direct contradictions between new insight/dream and existing insights.
        """
        if namespace not in ["insight", "dream"]:
            return
            
        try:
            emb = self.llm.embed(new_content)
        except Exception:
            return
            
        # Always resolve conflicts against 'insight' namespace to maintain consistency
        search_ns = "insight"
        candidates = self.db.search_memories(search_ns, new_content, emb, limit=5)
        if not candidates:
            return
            
        for cand in candidates:
            # Ask LLM if there is a contradiction
            system_instruction = "Bạn là hệ thống gác cổng tri thức. Hãy phát hiện mâu thuẫn logic giữa các bài học kinh nghiệm. Trả về JSON."
            prompt = f"""
Thông tin cũ:
"{cand['content']}"

Thông tin mới:
"{new_content}"

Hai thông tin trên có mâu thuẫn trực tiếp với nhau không (ví dụ: một cái bảo 'dùng A', một cái bảo 'cấm dùng A')?
Nếu có mâu thuẫn, hãy đưa ra cách giải quyết (giữ cái nào, sửa đổi ra sao).
"""
            try:
                res_str = self.llm.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=0.1,
                    json_mode=True,
                    response_schema=ConflictResolution
                )
                res_data = json.loads(res_str)
                
                if res_data.get("has_conflict", False):
                    action = res_data.get("resolution_action")
                    print(f"Conflict detected between new memory and existing memory '{cand['id']}'. Action: {action}")
                    
                    observability_manager.log_lifecycle_event(
                        event_type="conflict_resolution",
                        namespace=namespace,
                        detail={"old_id": cand["id"], "action": action, "resolved_content": res_data.get("resolved_content", "")}
                    )
                    
                    if action == "delete_old":
                        self.db.delete_memory(cand["id"])
                    elif action == "update_old":
                        resolved_content = res_data.get("resolved_content", cand["content"])
                        resolved_emb = self.llm.embed(resolved_content)
                        # Update old record content
                        self.db.delete_memory(cand["id"])
                        self.db.add_memory(
                            memory_id=cand["id"],
                            namespace=namespace,
                            content=resolved_content,
                            embedding=resolved_emb,
                            task_id=cand["task_id"],
                            status=cand["status"],
                            importance=cand["importance"],
                            metadata=cand["metadata"]
                        )
            except Exception as e:
                print(f"Error during conflict resolution: {e}")

    def enforce_capacity(self, namespace: str) -> None:
        """
        Keep database size under max_capacity. If exceeded, delete low score records.
        """
        all_m = self.db.get_all_memories(namespace)
        if len(all_m) <= self.max_capacity:
            return
            
        # Evict records
        # Compute generic score = importance * recency
        # Since we don't have query context, we use decay factor directly
        current_time = time.time()
        decay_rate = config_instance.get("memory.decay_rate", 0.01)
        
        scored_m = []
        for m in all_m:
            age_hours = (current_time - m["created_at"]) / 3600.0
            recency_score = np.exp(-decay_rate * age_hours)
            importance_score = m["importance"] / 10.0
            
            # combined generic score (equal weights)
            score = 0.5 * importance_score + 0.5 * recency_score
            scored_m.append((score, m["id"]))
            
        # Sort by score ascending (lowest first)
        scored_m.sort()
        
        num_to_delete = len(all_m) - self.max_capacity
        print(f"Memory Capacity Limit Exceeded ({len(all_m)}/{self.max_capacity}) in namespace '{namespace}'. Evicting {num_to_delete} entries.")
        
        evicted_ids = []
        for i in range(num_to_delete):
            _, mid = scored_m[i]
            self.db.delete_memory(mid)
            evicted_ids.append(mid)
            
        observability_manager.log_lifecycle_event(
            event_type="eviction",
            namespace=namespace,
            detail={"num_evicted": num_to_delete, "evicted_ids": evicted_ids}
        )

# Global lifecycle manager instance
lifecycle_manager = MemoryLifecycleManager()
