import sys
import os

# Configure stdout and stderr to use UTF-8 to prevent encoding errors on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from src.infra.curriculum import curriculum_manager
from src.evaluation import eval_framework
from src.robustness import robustness_suite
from src.observability import observability_manager
from src.memory.memory_engine import memory_engine
from src.exploration import exploration_loop


def print_help():
    print("""
Evolutionary Coding Agent CLI Runner

Sử dụng: python run.py [LỆNH]

Các lệnh khả dụng:
  init-curriculum   Khởi tạo bộ bài tập mẫu (Subtasks, Complex, Held-out) trong data/
  baseline          Chạy đánh giá Memoryless Baseline (thiết lập B_i)
  first-pass        Chạy First Pass (vừa học vừa làm, lưu bộ nhớ và snapshot)
  second-pass       Đóng băng bộ nhớ từ snapshot và chạy lại (thiết lập Stability Gain)
  held-out          Chạy đánh giá Held-out Tasks (thiết lập Generalization Gain)
  robustness        Chạy các bài kiểm thử phá hoại (Naive Stream, Memory Poisoning)
  report            Xuất kết quả đo lường và sinh Dashboard HTML báo cáo trực quan
  explore           Chạy Phase 5 Active Exploration (tự đề xuất, probe, oracle)
  run-all           Chạy tuần tự toàn bộ quy trình trên và sinh báo cáo
  dream             Chạy offline Dreaming để đúc rút bài học từ trace log
  dream-promote     Thăng chức (promote) một bài học từ dream sang insight namespace
  backfill-verticals Gán nhãn business vertical cho các skill cũ (--dry-run để chạy thử)
""")


def archive_trace_file():
    trace_path = observability_manager.trace_file
    if os.path.exists(trace_path):
        import time
        archived_path = f"logs/trace_archived_{int(time.time())}.jsonl"
        try:
            os.rename(trace_path, archived_path)
            print(f"Archived existing trace file to {archived_path}")
        except Exception as e:
            print(f"Failed to archive trace file: {e}")

def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
        
    cmd = sys.argv[1].lower()
    
    # Default is [42, 43, 44, 45, 46, 47] for full statistical rigor.
    seeds = [42, 43, 44, 45, 46, 47]
    if "--seeds" in sys.argv:
        try:
            idx = sys.argv.index("--seeds")
            seeds_str = sys.argv[idx + 1]
            seeds = [int(x.strip()) for x in seeds_str.split(",")]
            # Remove --seeds and its argument from sys.argv so positional checks still work
            sys.argv.pop(idx + 1)
            sys.argv.pop(idx)
        except Exception as e:
            print(f"Error parsing --seeds option: {e}. Using default seeds: {seeds}")
            
    print(f"Chạy thực nghiệm với các seeds: {seeds}")
    
    if cmd == "init-curriculum":
        curriculum_manager.load_or_create_tasks()
        print("Curriculum tasks initialized successfully in data/curriculum/tasks.json.")
        
    elif cmd == "baseline":
        archive_trace_file()
        eval_framework.run_baseline(seeds=seeds)
        print("Baseline evaluation completed.")
        
    elif cmd == "first-pass":
        eval_framework.run_first_pass(seeds=seeds)
        print("First pass completed.")
        
    elif cmd == "second-pass":
        eval_framework.run_second_pass(seeds=seeds)
        print("Second pass completed.")
        
    elif cmd == "held-out":
        eval_framework.run_held_out(seeds=seeds)
        print("Held-out evaluation completed.")
        
    elif cmd == "robustness":
        robustness_suite.run_naive_stream_interference(seeds=seeds)
        robustness_suite.run_memory_poisoning_test(seeds=seeds)
        robustness_suite.run_negative_transfer_test(seeds=seeds)
        print("Robustness suite completed.")
        
    elif cmd == "report":
        observability_manager.generate_html_dashboard()

    elif cmd == "explore":
        print("=========================================================")
        print("PHASE 5: ACTIVE EXPLORATION")
        print("=========================================================")
        archive_trace_file()
        curriculum_manager.load_or_create_tasks()
        for seed in seeds:
            print(f"\n--- Exploration Seed {seed} ---")
            exploration_loop.run_exploration_pass(seed=seed)
        observability_manager.generate_html_dashboard()
        
        # Auto-dream hook
        from src.dreaming.dream_orchestrator import dream_orchestrator
        dream_orchestrator.run_after_session(session_type="explore", trace_path=observability_manager.trace_file, seeds=seeds)
        
        print("Active exploration pass completed.")
        
    elif cmd == "run-all":
        print("=========================================================")
        print("BẮT ĐẦU CHẠY TOÀN BỘ PIPELINE TIẾN HÓA AGENT (RUN-ALL)")
        print("=========================================================")
        
        # 0. Init
        archive_trace_file()
        curriculum_manager.load_or_create_tasks()
        
        # 1. Baseline
        eval_framework.run_baseline(seeds=seeds)
        
        # 2. First Pass
        eval_framework.run_first_pass(seeds=seeds)
        
        # 3. Second Pass
        eval_framework.run_second_pass(seeds=seeds)
        
        # 4. Held-out
        eval_framework.run_held_out(seeds=seeds)
        
        # 5. Robustness
        robustness_suite.run_naive_stream_interference(seeds=seeds)
        robustness_suite.run_memory_poisoning_test(seeds=seeds)
        robustness_suite.run_negative_transfer_test(seeds=seeds)
        
        # 6. Report
        observability_manager.generate_html_dashboard()
        
        # Auto-dream hook
        from src.dreaming.dream_orchestrator import dream_orchestrator
        dream_orchestrator.run_after_session(session_type="run-all", trace_path=observability_manager.trace_file, seeds=seeds)
        
        print("\n=========================================================")
        print("HOÀN THÀNH TOÀN BỘ PIPELINE THỬ NGHIỆM!")
        print(f"Bạn có thể mở file báo cáo tại: {os.path.abspath(observability_manager.dashboard_file)}")
        print("=========================================================")
        
    elif cmd == "dream":
        import time
        trace_path = observability_manager.trace_file
        if "--trace" in sys.argv:
            idx = sys.argv.index("--trace")
            trace_path = sys.argv[idx + 1]
            
        session_id = f"dream_{int(time.time())}"
        if "--session-id" in sys.argv:
            idx = sys.argv.index("--session-id")
            session_id = sys.argv[idx + 1]
            
        from src.dreaming.dream_reader import dream_reader
        from src.dreaming.dream_distiller import dream_distiller
        from src.dreaming.dream_store import dream_store
        
        print(f"Loading trace file: {trace_path}")
        try:
            bundle = dream_reader.load_trace(trace_path)
            if not bundle.get("runs"):
                print("Dream command: Bundle contains no valid trace events. Exiting.")
                sys.exit(1)
                
            result = dream_distiller.distill(bundle)
            filepath = dream_store.save_dream_session(session_id, result)
            print(f"Dreaming completed successfully. Artifact saved to: {filepath}")
        except Exception as e:
            print(f"Dream command failed: {e}")
            sys.exit(1)
            
    elif cmd == "dream-promote":
        insight_id = None
        if "--id" in sys.argv:
            idx = sys.argv.index("--id")
            insight_id = sys.argv[idx + 1]
            
        if not insight_id:
            print("Usage: python run.py dream-promote --id <insight_id>")
            sys.exit(1)
            
        from src.memory.memory_engine import memory_engine
        
        all_dreams = memory_engine.get_all_memories(namespace="dream")
        target_dream = None
        for dr in all_dreams:
            if dr["id"] == insight_id:
                target_dream = dr
                break
                
        if not target_dream:
            print(f"Dream insight with ID '{insight_id}' not found.")
            sys.exit(1)
            
        content = target_dream.get("content", "")
        if content.startswith("[SUMMARY]"):
            print("Cannot promote a session summary memory. Must be an individual insight.")
            sys.exit(1)
            
        meta = target_dream.get("metadata", {}) or {}
        meta["source_dream_id"] = insight_id
        
        new_id = memory_engine.add_insight(
            task_id="DREAM_PROMOTED",
            content=content,
            status="success",
            importance=target_dream.get("importance", 5.0),
            metadata=meta
        )
        if new_id:
            print(f"Successfully promoted dream insight '{insight_id}' to insight namespace as '{new_id}'")
        else:
            print(f"Failed to promote dream insight '{insight_id}'")
            
    elif cmd == "backfill-verticals":
        dry_run = "--dry-run" in sys.argv
        from src.skill.skill_manager import skill_manager
        print(f"Bắt đầu backfill business verticals cho các skill cũ (dry_run={dry_run})...")
        num_changed, num_total = skill_manager.backfill_verticals(dry_run=dry_run)
        print(f"Backfill hoàn tất: đã cập nhật/đề xuất {num_changed}/{num_total} skills.")
        
    else:
        print(f"Lệnh không hợp lệ: {cmd}")
        print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
