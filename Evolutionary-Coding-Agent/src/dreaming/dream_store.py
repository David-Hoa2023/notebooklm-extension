import os
import json
import glob
import shutil
from src.config import config_instance
from src.memory.memory_engine import memory_engine

class DreamStore:
    def __init__(self):
        self.dreams_dir = "data/memory/dreams"
        os.makedirs(self.dreams_dir, exist_ok=True)

    def save_dream_session(self, session_id: str, dream_result: dict) -> str:
        """
        Saves the DreamResult dict locally to a JSON file and registers
        its summary and individual insights in the SQLite DB under the 'dream' namespace.
        """
        # 1. Save filesystem mirror
        filepath = os.path.join(self.dreams_dir, f"{session_id}.json")
        dream_result["session_id"] = session_id
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(dream_result, f, ensure_ascii=False, indent=2)
            
        # Write to latest.json
        latest_path = os.path.join(self.dreams_dir, "latest.json")
        try:
            # We copy instead of symlink to ensure maximum Windows compatibility
            shutil.copy2(filepath, latest_path)
        except Exception as e:
            print(f"DreamStore: Failed to copy to latest.json: {e}")
            
        # 2. Write to SQLite database
        # Save session summary
        summary_content = f"[SUMMARY] {dream_result.get('session_summary', '')}"
        memory_engine.add_dream(
            content=summary_content,
            importance=7.0,
            metadata={
                "type": "session_summary",
                "session_id": session_id
            }
        )
        
        # Save individual distilled insights
        for ins in dream_result.get("insights", []):
            memory_engine.add_dream(
                content=ins.get("content", ""),
                importance=ins.get("importance", 5.0),
                metadata={
                    "type": "insight",
                    "session_id": session_id,
                    "evidence_task_ids": ins.get("evidence_task_ids", []),
                    "scope": ins.get("scope", "global"),
                    "domain": ins.get("domain", "generic")
                }
            )
            
        # 3. Prune older sessions
        retain = config_instance.get("dreaming.retain_sessions", 5)
        self.prune_sessions(retain)
        
        print(f"DreamStore: Saved dream session '{session_id}' to SQLite and mirrored to {filepath}")
        return filepath

    def retrieve_dreams(self, query_text: str, limit: int = 3) -> list[dict]:
        """
        Retrieves relevant dreams from SQLite namespace 'dream'.
        Repopulates SQLite from filesystem first if SQLite namespace is empty.
        """
        try:
            db_dreams = memory_engine.get_all_memories(namespace="dream")
            if not db_dreams:
                self.repopulate_from_filesystem()
        except Exception as e:
            print(f"DreamStore: Error checking DB dreams: {e}")
            
        return memory_engine.retrieve_memories(
            namespace="dream",
            query_text=query_text,
            limit=limit
        )

    def repopulate_from_filesystem(self):
        """
        Loads all stored dream session JSON files from the filesystem and inserts
        them back into the SQLite DB 'dream' namespace.
        """
        print("DreamStore: Repopulating SQLite namespace 'dream' from filesystem mirror...")
        files = glob.glob(os.path.join(self.dreams_dir, "*.json"))
        # Exclude latest.json to avoid duplicates, only load actual session files
        files = [f for f in files if os.path.basename(f) != "latest.json"]
        
        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    dream_result = json.load(f)
                session_id = dream_result.get("session_id")
                if not session_id:
                    session_id = os.path.splitext(os.path.basename(filepath))[0]
                
                # Save session summary
                summary_content = f"[SUMMARY] {dream_result.get('session_summary', '')}"
                memory_engine.add_dream(
                    content=summary_content,
                    importance=7.0,
                    metadata={
                        "type": "session_summary",
                        "session_id": session_id
                    }
                )
                
                # Save individual distilled insights
                for ins in dream_result.get("insights", []):
                    memory_engine.add_dream(
                        content=ins.get("content", ""),
                        importance=ins.get("importance", ins.get("importance", 5.0)),
                        metadata={
                            "type": "insight",
                            "session_id": session_id,
                            "evidence_task_ids": ins.get("evidence_task_ids", []),
                            "scope": ins.get("scope", "global"),
                            "domain": ins.get("domain", "generic")
                        }
                    )
                print(f"DreamStore: Repopulated session '{session_id}' from {filepath}")
            except Exception as e:
                print(f"DreamStore: Error repopulating from {filepath}: {e}")

    def prune_sessions(self, max_keep: int):
        """
        Deletes oldest JSON files and corresponding database entries if they exceed max_keep limit.
        """
        # Find all session JSON files (excluding latest.json)
        files = glob.glob(os.path.join(self.dreams_dir, "*.json"))
        files = [f for f in files if os.path.basename(f) != "latest.json"]
        
        if len(files) <= max_keep:
            return
            
        # Sort files by modification time (ascending: oldest first)
        files.sort(key=os.path.getmtime)
        to_prune = files[:-max_keep]
        
        for filepath in to_prune:
            try:
                # Read file to extract session_id
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session_id = data.get("session_id")
                
                # Delete filesystem mirror
                os.remove(filepath)
                print(f"DreamStore: Pruned dream session file: {filepath}")
                
                # Delete SQLite memories associated with this session_id
                if session_id:
                    all_dreams = memory_engine.get_all_memories(namespace="dream")
                    deleted_count = 0
                    for dr in all_dreams:
                        meta = dr.get("metadata", {}) or {}
                        if meta.get("session_id") == session_id:
                            memory_engine.db.delete_memory(dr["id"])
                            deleted_count += 1
                    if deleted_count > 0:
                        print(f"DreamStore: Pruned {deleted_count} DB memory rows for session '{session_id}'")
            except Exception as e:
                print(f"DreamStore: Error pruning file {filepath}: {e}")

dream_store = DreamStore()
