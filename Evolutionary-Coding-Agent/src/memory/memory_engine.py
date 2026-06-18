import uuid
import os
import shutil
import sqlite3
from src.infra.retrieval import db_instance
from src.llm import llm_client
from src.config import config_instance

class MemoryEngine:
    def __init__(self):
        self.db = db_instance
        self.llm = llm_client

    def retrieve_memories(self, namespace: str, query_text: str, limit: int = 3, filters: dict = None) -> list[dict]:
        """
        Retrieves relevant memories from a specific namespace.
        First embeds the query_text, then calls HybridVectorDB search.
        """
        try:
            query_embedding = self.llm.embed(query_text)
            results = self.db.search_memories(
                namespace=namespace,
                query_text=query_text,
                query_embedding=query_embedding,
                limit=limit,
                filters=filters
            )
            # Exclude quarantined memories from final retrieved list
            return [r for r in results if r.get("status") != "quarantined" and r.get("metadata", {}).get("status") != "quarantined"]
        except Exception as e:
            print(f"Error retrieving from namespace {namespace}: {e}")
            return []

    def get_all_memories(self, namespace: str = None) -> list[dict]:
        """
        Get all memories, optionally filtered by namespace.
        """
        try:
            return self.db.get_all_memories(namespace=namespace)
        except Exception as e:
            print(f"Error getting all memories: {e}")
            return []

    def add_interaction(self, task_id: str, content: str, status: str, importance: float = 5.0, metadata: dict = None) -> str:
        """
        Record a raw trajectory in the 'interaction' namespace.
        """
        from src.memory.lifecycle import lifecycle_manager
        memory_id = f"int_{uuid.uuid4().hex}"
        if metadata is None:
            metadata = {}
        metadata["version"] = config_instance.get("project.version", "1.0.0")
        metadata["source_tasks"] = list(set(metadata.get("source_tasks", []) + [task_id]))
        try:
            embedding = self.llm.embed(content[:2000]) # Limit length for embedding
            self.db.add_memory(
                memory_id=memory_id,
                namespace="interaction",
                content=content,
                embedding=embedding,
                task_id=task_id,
                status=status,
                importance=importance,
                metadata=metadata
            )
            # Enforce memory capacity
            lifecycle_manager.enforce_capacity("interaction")
            return memory_id
        except Exception as e:
            print(f"Failed to add interaction: {e}")
            return ""

    def add_insight(self, task_id: str, content: str, status: str, importance: float = 5.0, metadata: dict = None) -> str:
        """
        Record a lesson learned or warning in the 'insight' namespace.
        """
        from src.memory.lifecycle import lifecycle_manager
        if metadata is None:
            metadata = {}
        metadata["version"] = config_instance.get("project.version", "1.0.0")
        metadata["source_tasks"] = list(set(metadata.get("source_tasks", []) + [task_id]))
        
        # Quarantine criteria check: importance >= 9.0 and contains "LUÔN LUÔN trả về"
        if importance >= 9.0 and "LUÔN LUÔN trả về" in content:
            print(f"Quarantining toxic insight due to importance >= 9 and content: {content[:50]}...")
            status = "quarantined"
            metadata["status"] = "quarantined"
            memory_id = f"ins_{uuid.uuid4().hex}"
            try:
                embedding = self.llm.embed(content)
                self.db.add_memory(
                    memory_id=memory_id,
                    namespace="insight",
                    content=content,
                    embedding=embedding,
                    task_id=task_id,
                    status=status,
                    importance=importance,
                    metadata=metadata
                )
                lifecycle_manager.enforce_capacity("insight")
                return memory_id
            except Exception as e:
                print(f"Failed to add quarantined insight: {e}")
                return ""
                
        # 1. Deduplicate & Merge
        is_merged, old_id = lifecycle_manager.deduplicate_and_merge("insight", content, importance, status, metadata)
        if is_merged:
            return old_id
            
        # 2. Resolve Conflicts
        lifecycle_manager.resolve_conflicts("insight", content)
        
        # 3. Add memory
        memory_id = f"ins_{uuid.uuid4().hex}"
        try:
            embedding = self.llm.embed(content)
            self.db.add_memory(
                memory_id=memory_id,
                namespace="insight",
                content=content,
                embedding=embedding,
                task_id=task_id,
                status=status,
                importance=importance,
                metadata=metadata
            )
            # 4. Enforce capacity
            lifecycle_manager.enforce_capacity("insight")
            return memory_id
        except Exception as e:
            print(f"Failed to add insight: {e}")
            return ""

    def add_skill(self, task_id: str, content: str, importance: float = 8.0, metadata: dict = None) -> str:
        """
        Record a modular python function in the 'skill' namespace.
        """
        from src.memory.lifecycle import lifecycle_manager
        
        # 1. Deduplicate & Merge
        is_merged, old_id = lifecycle_manager.deduplicate_and_merge("skill", content, importance, "success", metadata)
        if is_merged:
            return old_id
            
        # 2. Add memory
        memory_id = f"skl_{uuid.uuid4().hex}"
        try:
            embedding = self.llm.embed(content)
            self.db.add_memory(
                memory_id=memory_id,
                namespace="skill",
                content=content,
                embedding=embedding,
                task_id=task_id,
                status="success",
                importance=importance,
                metadata=metadata
            )
            # 3. Enforce capacity
            lifecycle_manager.enforce_capacity("skill")
            return memory_id
        except Exception as e:
            print(f"Failed to add skill: {e}")
            return ""

    def add_dream(self, content: str, importance: float = 5.0, metadata: dict = None) -> str:
        """
        Record a distilled dream lesson or summary in the 'dream' namespace.
        """
        from src.memory.lifecycle import lifecycle_manager
        if metadata is None:
            metadata = {}
        metadata["version"] = config_instance.get("project.version", "1.0.0")
        
        # Quarantine criteria check: importance >= 9.0 and contains "LUÔN LUÔN trả về"
        if importance >= 9.0 and "LUÔN LUÔN trả về" in content:
            print(f"Quarantining toxic dream due to importance >= 9 and content: {content[:50]}...")
            status = "quarantined"
            metadata["status"] = "quarantined"
            memory_id = f"drm_{uuid.uuid4().hex}"
            try:
                embedding = self.llm.embed(content)
                self.db.add_memory(
                    memory_id=memory_id,
                    namespace="dream",
                    content=content,
                    embedding=embedding,
                    task_id=None,
                    status=status,
                    importance=importance,
                    metadata=metadata
                )
                lifecycle_manager.enforce_capacity("dream")
                return memory_id
            except Exception as e:
                print(f"Failed to add quarantined dream: {e}")
                return ""

        # 1. Deduplicate & Merge (similar logic to insight)
        is_merged, old_id = lifecycle_manager.deduplicate_and_merge("dream", content, importance, "success", metadata)
        if is_merged:
            return old_id
            
        # 2. Resolve Conflicts against insight namespace
        lifecycle_manager.resolve_conflicts("dream", content)
            
        # 3. Add memory
        memory_id = f"drm_{uuid.uuid4().hex}"
        try:
            embedding = self.llm.embed(content)
            self.db.add_memory(
                memory_id=memory_id,
                namespace="dream",
                content=content,
                embedding=embedding,
                task_id=None,
                status="success",
                importance=importance,
                metadata=metadata
            )
            # 4. Enforce capacity
            lifecycle_manager.enforce_capacity("dream")
            return memory_id
        except Exception as e:
            print(f"Failed to add dream: {e}")
            return ""

    def clear_all(self):
        self.db.clear_namespace("interaction")
        self.db.clear_namespace("insight")
        self.db.clear_namespace("skill")
        self.db.clear_namespace("dream")

    def create_snapshot(self, version_name: str) -> str:
        """
        Snapshot the current memory database state.
        Returns the path to the backup file.
        """
        snapshot_dir = "data/memory_snapshots"
        os.makedirs(snapshot_dir, exist_ok=True)
        dest_db_path = os.path.join(snapshot_dir, f"memory_{version_name}.db")
        
        # Close connection to flush writes, copy, then reopen
        self.db.conn.close()
        try:
            shutil.copy2(self.db.db_path, dest_db_path)
            print(f"Created memory snapshot at {dest_db_path}")
            return dest_db_path
        finally:
            # Reopen connection
            self.db.conn = sqlite3.connect(self.db.db_path, check_same_thread=False)
            self.db.conn.row_factory = sqlite3.Row

    def restore_snapshot(self, version_name: str) -> bool:
        """
        Restore memory database from a snapshot.
        """
        snapshot_path = os.path.join("data/memory_snapshots", f"memory_{version_name}.db")
        if not os.path.exists(snapshot_path):
            print(f"Snapshot file not found: {snapshot_path}")
            return False
            
        self.db.conn.close()
        try:
            shutil.copy2(snapshot_path, self.db.db_path)
            print(f"Restored memory database from snapshot {version_name}")
            return True
        except Exception as e:
            print(f"Failed to restore snapshot: {e}")
            return False
        finally:
            self.db.conn = sqlite3.connect(self.db.db_path, check_same_thread=False)
            self.db.conn.row_factory = sqlite3.Row

# Global memory engine instance
memory_engine = MemoryEngine()
