import time
import concurrent.futures
from src.infra.curriculum import curriculum_manager
from src.memory.memory_engine import memory_engine
from src.memory.validation_gate import validation_gate
from src.skill.skill_manager import skill_manager
from src.pipeline import AgentPipeline
from src.observability import observability_manager

class EvaluationFramework:
    def __init__(self):
        pass

    def run_baseline(self, seeds: list[int] = [42, 43, 44]):
        """
        Run the training curriculum tasks WITHOUT memory.
        """
        print("=== CHẠY MEMORYLESS BASELINE ===")
        tasks = curriculum_manager.get_sorted_training_tasks()
        held_out_tasks = curriculum_manager.get_held_out_curriculum()
        
        all_eval_tasks = tasks + held_out_tasks
        
        for seed in seeds:
            print(f"\n--- Running Seed {seed} ---")
            # Clear database to prevent leakage
            memory_engine.clear_all()
            
            # Setup pipeline without memory
            pipeline = AgentPipeline(memory_enabled=False)
            
            for t in all_eval_tasks:
                start_time = time.time()
                # Run task
                res = pipeline.execute_task(t)
                duration = time.time() - start_time
                
                # Check pass type
                pass_type = "held_out" if t.get("is_held_out", False) else "baseline"
                if pass_type == "held_out":
                    # For held-out baseline, we log as baseline under held-out tag or baseline
                    # Let's keep a separate pass_type: held_out baseline will be measured later,
                    # but logging it under 'baseline' with metadata `is_held_out: True` is clean.
                    pass_type = "baseline"
                
                # Log run
                observability_manager.log_run(
                    task_id=t["id"],
                    seed=seed,
                    pass_type=pass_type,
                    status=res["status"],
                    score=res["score"],
                    duration=duration,
                    metadata=res
                )
                print(f"Task {t['id']} ({t['title']}): score={res['score']}, status={res['status']}")

    def run_first_pass(self, seeds: list[int] = [42, 43, 44]):
        """
        Run the training curriculum tasks WITH active read/write memory.
        Includes parallel subtask execution and sequential complex task execution.
        """
        print("\n=== CHẠY FIRST PASS (PLASTICITY GAIN) ===")
        
        # Get sorted training curriculum
        tasks = curriculum_manager.get_sorted_training_tasks()
        
        # Separate subtasks (no dependencies) and complex tasks (has dependencies)
        subtasks = [t for t in tasks if not t.get("dependencies", [])]
        complex_tasks = [t for t in tasks if t.get("dependencies", [])]
        
        for seed in seeds:
            print(f"\n--- Running Seed {seed} ---")
            # Clear database at start of seed
            memory_engine.clear_all()
            
            # Setup pipeline with active memory
            pipeline = AgentPipeline(memory_enabled=True, frozen_memory=False)
            
            # 1. Run Level 1 Subtasks in PARALLEL (TASK_001)
            print(f"Executing {len(subtasks)} subtasks in parallel...")
            subtask_runs = []
            
            # Define a helper function to run single task in thread (read-only memory during thread runs)
            def run_subtask_thread(task):
                # Thread runs pipeline with memory, but frozen writing to avoid SQLite locked errors.
                # All writing is deferred to the Consolidation step.
                thread_pipeline = AgentPipeline(memory_enabled=True, frozen_memory=True)
                start_time = time.time()
                res = thread_pipeline.execute_task(task)
                duration = time.time() - start_time
                return task, res, duration

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(subtasks)) as executor:
                futures = [executor.submit(run_subtask_thread, t) for t in subtasks]
                for fut in concurrent.futures.as_completed(futures):
                    task, res, duration = fut.result()
                    subtask_runs.append((task, res, duration))
                    print(f"Subtask {task['id']} thread execution finished. Status: {res['status']}")
                    
            # 2. Consolidation step (TASK_003) - Synchronously commit results to memory
            print("Running Synchronous Consolidation Step...")
            for task, res, duration in subtask_runs:
                # Re-run Validation Gate sequentially on active DB to log insights and skills properly
                print(f"Consolidating subtask {task['id']}...")
                val_res = validation_gate.validate_solution(
                    task_id=task["id"],
                    task_description=task["description"],
                    code=res["code"],
                    test_code=task["test_code"],
                    hidden_test_code=task.get("hidden_test_code")
                )
                
                # Extract and register skills if passed
                skills_extracted = []
                if val_res["status"] == "passed":
                    skills_extracted = skill_manager.extract_and_register_skills(
                        task_id=task["id"],
                        task_description=task["description"],
                        code=res["code"]
                    )
                    
                val_res.update({
                    "task_id": task["id"],
                    "code": res["code"],
                    "skills_extracted": skills_extracted,
                    "insights_retrieved": res.get("insights_retrieved", []),
                    "skills_retrieved": res.get("skills_retrieved", [])
                })
                
                # Log run
                observability_manager.log_run(
                    task_id=task["id"],
                    seed=seed,
                    pass_type="first_pass",
                    status=val_res["status"],
                    score=val_res["score"],
                    duration=duration,
                    metadata=val_res
                )
                print(f"Subtask {task['id']} consolidated: score={val_res['score']}, status={val_res['status']}")

            # 3. Run Level 2 Complex Tasks in SEQUENTIAL order (TASK_002)
            print(f"Executing {len(complex_tasks)} complex tasks sequentially...")
            for t in complex_tasks:
                start_time = time.time()
                res = pipeline.execute_task(t)
                duration = time.time() - start_time
                
                # Log run
                observability_manager.log_run(
                    task_id=t["id"],
                    seed=seed,
                    pass_type="first_pass",
                    status=res["status"],
                    score=res["score"],
                    duration=duration,
                    metadata=res
                )
                print(f"Complex Task {t['id']} completed: score={res['score']}, status={res['status']}")

            # Snapshot final memory state for this seed
            memory_engine.create_snapshot(f"seed_{seed}")

    def run_second_pass(self, seeds: list[int] = [42, 43, 44]):
        """
        Re-run the curriculum tasks with FROZEN memory (Read-only).
        This measures the stability gain (SG = S_i - F_i).
        """
        print("\n=== CHẠY SECOND PASS (STABILITY GAIN) ===")
        tasks = curriculum_manager.get_sorted_training_tasks()
        
        for seed in seeds:
            print(f"\n--- Running Seed {seed} (Frozen Memory) ---")
            # Restore memory snapshot for this seed
            success = memory_engine.restore_snapshot(f"seed_{seed}")
            if not success:
                print(f"Skipping seed {seed} second pass: snapshot not found.")
                continue
                
            # Setup pipeline with frozen memory (Read-only)
            pipeline = AgentPipeline(memory_enabled=True, frozen_memory=True)
            
            for t in tasks:
                start_time = time.time()
                res = pipeline.execute_task(t)
                duration = time.time() - start_time
                
                # Log run
                observability_manager.log_run(
                    task_id=t["id"],
                    seed=seed,
                    pass_type="second_pass",
                    status=res["status"],
                    score=res["score"],
                    duration=duration,
                    metadata=res
                )
                print(f"Task {t['id']}: score={res['score']}, status={res['status']}")

    def run_held_out(self, seeds: list[int] = [42, 43, 44]):
        """
        Run the held-out tasks using the frozen memory learned from first pass.
        This measures the Generalization Gain (GG = H_j - B_j).
        """
        print("\n=== CHẠY HELD-OUT EVALUATION (GENERALIZATION GAIN) ===")
        held_out_tasks = curriculum_manager.get_held_out_curriculum()
        
        for seed in seeds:
            print(f"\n--- Running Seed {seed} on Held-Out tasks ---")
            # Restore memory snapshot for this seed
            success = memory_engine.restore_snapshot(f"seed_{seed}")
            if not success:
                print(f"Skipping seed {seed} held-out pass: snapshot not found.")
                continue
                
            # Setup pipeline with frozen memory (Read-only)
            pipeline = AgentPipeline(memory_enabled=True, frozen_memory=True)
            
            for t in held_out_tasks:
                start_time = time.time()
                res = pipeline.execute_task(t)
                duration = time.time() - start_time
                
                # Log run
                observability_manager.log_run(
                    task_id=t["id"],
                    seed=seed,
                    pass_type="held_out",
                    status=res["status"],
                    score=res["score"],
                    duration=duration,
                    metadata=res
                )
                print(f"Held-out Task {t['id']}: score={res['score']}, status={res['status']}")

# Global evaluation framework instance
eval_framework = EvaluationFramework()
