import time
from src.config import config_instance
from src.pipeline import AgentPipeline
from src.infra.curriculum import curriculum_manager
from src.observability import observability_manager
from src.exploration.curriculum_proposer import (
    curriculum_proposer,
    compute_recent_success_rate,
)
from src.exploration.environment_probe import environment_prober
from src.exploration.oracle_synthesis import oracle_synthesizer
from src.exploration.skill_gap_analyzer import skill_gap_analyzer
from src.exploration.explore_exploit_controller import explore_exploit_controller
from src.exploration.novelty_reward import novelty_scorer


class ExplorationLoop:
    def run_regression_suite(self, pipeline: AgentPipeline, seed: int):
        """
        EL_MEM_009: Run a small regression set on historically solved tasks
        and log score deltas to trace.
        """
        print("Running regression suite (EL_MEM_009)...")
        regression_tasks = ["SUB_001", "SUB_003"]
        runs = observability_manager.load_all_runs()
        
        for task_id in regression_tasks:
            task = curriculum_manager.get_task(task_id)
            if not task:
                continue
                
            prev_runs = [r for r in runs if r.get("task_id") == task_id and r.get("status") == "passed"]
            prev_score = prev_runs[-1]["score"] if prev_runs else 0.0
            
            start = time.time()
            res = pipeline.execute_task(task)
            duration = time.time() - start
            
            score_delta = res["score"] - prev_score
            
            observability_manager.log_run(
                task_id=task_id,
                seed=seed,
                pass_type="regression",
                status=res["status"],
                score=res["score"],
                duration=duration,
                metadata={
                    **res,
                    "regression": {
                        "previous_score": prev_score,
                        "score_delta": score_delta
                    }
                }
            )
            print(f"Regression task {task_id}: score = {res['score']}, delta = {score_delta:.2f}")

    def run_exploration_pass(self, seed: int = 42, num_tasks: int | None = None) -> list[dict]:
        """
        Active exploration pass: propose -> probe -> solve -> verify -> consolidate.
        Implements EL_EXPLORE_001 through EL_EXPLORE_006 orchestration.
        """
        num_tasks = num_tasks or config_instance.get("exploration.max_tasks_per_run", 2)
        probe_enabled = config_instance.get("exploration.probe_before_solve", True)

        runs = observability_manager.load_all_runs()
        success_rate = compute_recent_success_rate(runs)
        gap_info = skill_gap_analyzer.analyze()
        gap_targets = skill_gap_analyzer.top_gaps(limit=3)

        pipeline = AgentPipeline(memory_enabled=True, frozen_memory=False)
        results = []
        tokens_spent = sum(r.get("estimated_tokens", 0) for r in runs)
        recent_scores = [
            r["score"] for r in runs
            if r.get("status") == "passed" and "score" in r
        ][-5:]
        recent_payoff = sum(recent_scores) / len(recent_scores) / 10.0 if recent_scores else 0.5

        avoid_topics = [
            t.get("title", "") for t in curriculum_manager.get_training_curriculum()
        ]

        for i in range(num_tasks):
            decision = explore_exploit_controller.decide(
                recent_payoff=recent_payoff,
                tokens_spent=tokens_spent,
            )
            
            # EL_OBS_004: Cost & budget governor hard stop
            if decision.budget_remaining <= 0:
                print(f"Cost & budget governor: hard stop triggered. Spent {tokens_spent} tokens.")
                observability_manager.log_exploration_step(
                    seed=seed,
                    step="hard_stop_triggered",
                    detail={
                        "reason": f"budget tokens spent ({tokens_spent}) reached budget limit ({explore_exploit_controller.budget_tokens})"
                    }
                )
                break

            observability_manager.log_exploration_step(
                seed=seed,
                step="policy_decision",
                detail={
                    "mode": decision.mode,
                    "epsilon": decision.epsilon,
                    "rationale": decision.rationale,
                    "iteration": i + 1,
                },
            )

            if decision.mode == "exploit":
                training = curriculum_manager.get_sorted_training_tasks()
                if not training:
                    continue
                task = training[i % len(training)]
                task = {**task, "is_self_proposed": False}
                proposed_meta = {"source": "exploit_curriculum", "task_id": task["id"]}
            else:
                proposed = curriculum_proposer.propose(
                    success_rate=success_rate,
                    skill_summaries=gap_info["skill_names"],
                    gap_targets=gap_targets,
                    avoid_topics=avoid_topics,
                )
                proposed.novelty_score = novelty_scorer.score(
                    f"{proposed.title} {proposed.description}"
                )
                observability_manager.log_exploration_step(
                    seed=seed,
                    step="task_proposed",
                    detail={
                        "task_id": proposed.id,
                        "difficulty": proposed.difficulty,
                        "novelty_score": proposed.novelty_score,
                        "gap_targets": gap_targets,
                        "success_rate": success_rate,
                    },
                )

                oracle = oracle_synthesizer.synthesize(proposed)
                if not oracle.validation_passed:
                    observability_manager.log_exploration_step(
                        seed=seed,
                        step="oracle_rejected",
                        detail={
                            "task_id": proposed.id,
                            "reason": oracle.rejection_reason,
                        },
                    )
                    continue

                task = oracle_synthesizer.to_task_dict(proposed, oracle)
                proposed_meta = {
                    "source": "explore_proposed",
                    "task_id": proposed.id,
                    "novelty_score": proposed.novelty_score,
                    "oracle_validated": True,
                }
                observability_manager.log_exploration_step(
                    seed=seed,
                    step="oracle_validated",
                    detail={"task_id": proposed.id},
                )

            probe_context = ""
            if probe_enabled and environment_prober.should_probe(
                retrieved_insights=[],
                is_self_proposed=task.get("is_self_proposed", False),
            ):
                probes = environment_prober.generate_probes(task["description"], max_probes=2)
                probe_results = environment_prober.run_probes(task["id"], probes)
                probe_context = environment_prober.format_probe_context(probe_results)
                observability_manager.log_exploration_step(
                    seed=seed,
                    step="environment_probe",
                    detail={
                        "task_id": task["id"],
                        "probe_count": len(probe_results),
                        "statuses": [p.status for p in probe_results],
                    },
                )

            start = time.time()
            res = pipeline.execute_task(task, probe_context=probe_context)
            duration = time.time() - start

            res["exploration"] = proposed_meta
            res["execution_mode"] = res.get("execution_mode", "unknown")

            observability_manager.log_run(
                task_id=task["id"],
                seed=seed,
                pass_type="exploration",
                status=res["status"],
                score=res["score"],
                duration=duration,
                metadata=res,
            )
            observability_manager.log_exploration_step(
                seed=seed,
                step="task_completed",
                detail={
                    "task_id": task["id"],
                    "status": res["status"],
                    "score": res["score"],
                    "mode": decision.mode,
                },
            )

            results.append(res)
            tokens_spent += (len(str(task)) + len(str(res.get("code", "")))) // 4

            if res["status"] == "passed":
                success_rate = min(1.0, success_rate + 0.05)
                recent_payoff = min(1.0, recent_payoff + 0.1)
            else:
                success_rate = max(0.0, success_rate - 0.05)

        # EL_MEM_009: Run regression suite after each exploration batch
        try:
            self.run_regression_suite(pipeline, seed)
        except Exception as e:
            print(f"Error running regression suite: {e}")

        return results


exploration_loop = ExplorationLoop()
