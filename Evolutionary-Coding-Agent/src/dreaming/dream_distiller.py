import json
from src.llm import llm_client
from src.config import config_instance
from src.memory.memory_engine import memory_engine
from src.dreaming.models import DreamResult

class DreamDistiller:
    def __init__(self):
        self.llm = llm_client

    def distill(self, bundle: dict) -> dict:
        """
        Takes a DreamSessionBundle, queries existing insights to avoid duplicates,
        runs LLM reflection over the trace event runs, and returns a DreamResult dict.
        """
        token_budget = config_instance.get("dreaming.token_budget", 150000)
        
        # 1. Fetch active insights to prevent duplicates
        existing_insights = memory_engine.get_all_memories(namespace="insight")
        existing_list = [ins.get("content", "") for ins in existing_insights]
        
        # 2. Construct prompt
        bundle_json = json.dumps(bundle.get("runs", []), ensure_ascii=False, indent=2)
        
        # Estimate prompt tokens (4 chars = 1 token rule)
        prompt_len = len(bundle_json)
        estimated_prompt_tokens = prompt_len // 4
        if estimated_prompt_tokens > token_budget:
            raise ValueError(f"DreamDistiller: Prompt token count ({estimated_prompt_tokens}) exceeds budget limit ({token_budget}). Aborting.")
            
        system_instruction = (
            "You are a meta-cognitive agent memory compiler. Your task is to analyze raw execution traces of a session "
            "and distill high-level, cross-session Python coding wisdom (lessons learned, API workarounds, error patterns) "
            "into structured JSON matching the DreamResult schema.\n"
            "CRITICAL REQUIREMENTS:\n"
            "1. Output valid JSON adhering to the schema.\n"
            "2. Distilled insights must be written in Vietnamese prose (Vietnamese bullet language).\n"
            "3. Do not duplicate existing insights provided in the context.\n"
            "4. Keep insights actionable, concise, and generalized."
        )
        
        prompt = f"""
=== RAW SESSION TRACE EVENTS ===
{bundle_json}

=== EXISTING INSIGHTS (DO NOT DUPLICATE) ===
{json.dumps(existing_list, ensure_ascii=False, indent=2)}

Please distill this session trace. Focus on:
- Patterns of repeat failures (e.g., signature drift, environment sandbox error, mock library mismatch).
- Specific actions/workarounds (e.g., how NEG_001 was solved without a context manager).
- Domain rules that should guide future runs.

For each insight, list the evidence_task_ids (e.g., ["NEG_001"] or ["SUB_001", "SUB_003"]) that support it.
Assign a domain (e.g. "smtp", "regex", "math"), scope ("global", "session", or "task"), and vertical (one of the business verticals: "sales", "marketing", "finance", "generic"). If the lesson is purely technical or generic, assign "generic".
"""
        
        print("DreamDistiller: Distilling session runs via LLM...")
        try:
            res_str = self.llm.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1,
                json_mode=True,
                response_schema=DreamResult
            )
            res_data = json.loads(res_str)
            res_data["token_budget_used"] = estimated_prompt_tokens
            
            # DRM_SAFE_002: Evidence-required and confidence-based filtering
            min_confidence = config_instance.get("dreaming.min_confidence", 0.6)
            valid_task_ids = {run.get("task_id") for run in bundle.get("runs", []) if run.get("task_id")}
            
            filtered_insights = []
            discarded_reasons = []
            
            for ins in res_data.get("insights", []):
                content = ins.get("content", "")
                confidence = ins.get("confidence", 0.0)
                evidence = ins.get("evidence_task_ids", [])
                
                # Confidence check
                if confidence < min_confidence:
                    discarded_reasons.append(f"Dropped '{content[:30]}...' due to low confidence ({confidence} < {min_confidence})")
                    continue
                    
                # Evidence check
                if not evidence:
                    discarded_reasons.append(f"Dropped '{content[:30]}...' due to empty evidence_task_ids")
                    continue
                    
                invalid_evidence = [t for t in evidence if t not in valid_task_ids]
                if invalid_evidence:
                    discarded_reasons.append(f"Dropped '{content[:30]}...' because evidence task_ids {invalid_evidence} are not in the session bundle")
                    continue
                    
                filtered_insights.append(ins)
                
            res_data["insights"] = filtered_insights
            if discarded_reasons:
                current_noise = res_data.get("noise_discarded_summary", "")
                discarded_block = "\n".join(discarded_reasons)
                res_data["noise_discarded_summary"] = f"{current_noise}\n[Safety Filters]:\n{discarded_block}".strip()
                print(f"DreamDistiller: Filtered out {len(discarded_reasons)} insights. Reasons:\n{discarded_block}")
                
            return res_data
        except Exception as e:
            print(f"DreamDistiller: Distillation failed: {e}")
            raise e

dream_distiller = DreamDistiller()
