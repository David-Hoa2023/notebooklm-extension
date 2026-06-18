import os
import json
from src.config import config_instance
from src.dreaming.dream_store import dream_store

class DreamLoader:
    def format_for_prompt(self, description: str, task_id: str = None, limit: int = 3) -> str:
        """
        Retrieves relevant dreams and constructs the SESSION WISDOM prompt block.
        Prepend to system prompt if dreaming is enabled.
        """
        if not config_instance.get("dreaming.enabled", False):
            return ""
            
        max_chars = config_instance.get("dreaming.max_summary_chars", 1000)
        
        # 1. Load session summary from latest.json filesystem mirror
        session_summary = ""
        latest_path = os.path.join(dream_store.dreams_dir, "latest.json")
        if os.path.exists(latest_path):
            try:
                with open(latest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session_summary = data.get("session_summary", "")
            except Exception as e:
                print(f"DreamLoader: Error loading latest.json: {e}")
                
        # 2. Retrieve top-k relevant dream insights from database
        try:
            # We fetch more first to account for filtering out summary/non-matching rows
            candidates = dream_store.retrieve_dreams(query_text=description, limit=limit + 10)
            
            # Exclude session summary entries and filter by domain/relevance
            insights = []
            for c in candidates:
                content = c.get("content", "")
                if content.startswith("[SUMMARY]"):
                    continue
                    
                meta = c.get("metadata", {}) or {}
                
                # Enforce scope check: DRM_SAFE_001
                if meta.get("scope") == "task":
                    evidence = meta.get("evidence_task_ids", [])
                    if not evidence and meta.get("task_id"):
                        evidence = [meta.get("task_id")]
                        
                    matched = False
                    if task_id and task_id in evidence:
                        matched = True
                    elif any(eid in description for eid in evidence):
                        matched = True
                    elif task_id and any(eid in task_id for eid in evidence):
                        matched = True
                        
                    if not matched:
                        continue
                        
                # Enforce domain match: DRM_SAFE_001
                domain = meta.get("domain", "").lower().strip()
                if domain and domain not in ["generic", "global"]:
                    desc_lower = (description + " " + (task_id or "")).lower()
                    domain_keywords = {
                        "smtp": ["smtp", "email", "mail", "smtplib"],
                        "regex": ["regex", "re", "pattern", "match"],
                        "json": ["json", "serialize", "deserialize"],
                        "math": ["math", "expression", "calculate", "arithmetic", "eval"],
                        "datetime": ["date", "time", "datetime", "timestamp"],
                        "file_io": ["file", "read", "write", "path"]
                    }
                    keywords = domain_keywords.get(domain, [domain])
                    if not any(kw in desc_lower for kw in keywords):
                        continue
                        
                insights.append(c)
                if len(insights) >= limit:
                    break
        except Exception as e:
            print(f"DreamLoader: Error retrieving dreams from DB: {e}")
            insights = []
            
        if not session_summary and not insights:
            return ""
            
        # 3. Format markdown block
        lines = ["=== SESSION WISDOM (DREAM) ==="]
        if session_summary:
            lines.append(f"Tóm tắt phiên trước: {session_summary}")
        if insights:
            lines.append("Các bài học kinh nghiệm chắt lọc:")
            for i, ins in enumerate(insights, 1):
                meta = ins.get("metadata", {}) or {}
                domain_str = f" [Domain: {meta.get('domain')}]" if meta.get("domain") else ""
                lines.append(f"- {ins['content']}{domain_str}")
                
        block = "\n".join(lines)
        
        # 4. Enforce max_chars limit gracefully
        if len(block) > max_chars:
            suffix = "\n... [TRUNCATED DUE TO BUDGET] ..."
            block = block[:max_chars - len(suffix)] + suffix
            
        return block

dream_loader = DreamLoader()
