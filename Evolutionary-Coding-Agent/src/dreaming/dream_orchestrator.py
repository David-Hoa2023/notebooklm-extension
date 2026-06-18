import os
import time
from src.config import config_instance
from src.observability import observability_manager
from src.dreaming.dream_reader import dream_reader
from src.dreaming.dream_distiller import dream_distiller
from src.dreaming.dream_store import dream_store

class DreamOrchestrator:
    def run_after_session(self, session_type: str, trace_path: str, seeds: list[int] = None):
        """
        Executed automatically at the end of run-all or explore sessions
        if configured in dreaming.auto_run_after list.
        """
        if not config_instance.get("dreaming.enabled", False):
            return
            
        auto_run_list = config_instance.get("dreaming.auto_run_after", [])
        if session_type not in auto_run_list:
            return
            
        print(f"\n[DREAMING] Running automatic Dreaming hook after session type: {session_type}...")
        
        session_id = f"auto_{session_type}_{int(time.time())}"
        try:
            # Load and filter trace
            bundle = dream_reader.load_trace(trace_path)
            
            # Filter runs by seed if specified
            if seeds and bundle.get("runs"):
                bundle["runs"] = [r for r in bundle["runs"] if r.get("seed") in seeds]
                bundle["compressed_events_count"] = len(bundle["runs"])
                
            if not bundle.get("runs"):
                print("[DREAMING] Auto-dreaming skipped: No valid trace runs matching constraints.")
                return
                
            # Distill via LLM
            result = dream_distiller.distill(bundle)
            
            # Persist to DB and filesystem
            filepath = dream_store.save_dream_session(session_id, result)
            print(f"[DREAMING] Auto-dreaming completed successfully! Session: {session_id}. Path: {filepath}")
            
            # Log exploration step event for tracking
            observability_manager.log_exploration_step(
                seed=seeds[0] if seeds else 42,
                step="dream_completed",
                detail={
                    "session_id": session_id,
                    "session_type": session_type,
                    "compression_ratio": bundle.get("compression_ratio", 1.0),
                    "insights_count": len(result.get("insights", [])),
                    "token_budget_used": result.get("token_budget_used", 0)
                }
            )
        except Exception as e:
            # Crucial requirement: Failure in dreaming does not crash the entire process.
            # We warn and log a failure trace event.
            warn_msg = f"[DREAMING WARNING] Auto-dreaming failed: {e}"
            print(warn_msg)
            try:
                observability_manager.log_exploration_step(
                    seed=seeds[0] if seeds else 42,
                    step="dream_failed",
                    detail={"error": str(e), "session_type": session_type}
                )
            except Exception:
                pass

dream_orchestrator = DreamOrchestrator()
