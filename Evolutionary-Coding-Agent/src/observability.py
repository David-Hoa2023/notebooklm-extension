import os
import json
import time
import numpy as np
from src.config import config_instance

class ObservabilityManager:
    def __init__(self):
        self.log_dir = config_instance.get("observability.log_dir", "logs")
        self.trace_file = config_instance.get("observability.trace_file", "logs/trace.jsonl")
        self.dashboard_file = config_instance.get("observability.dashboard_file", "logs/dashboard.html")
        os.makedirs(self.log_dir, exist_ok=True)

    def log_run(self, task_id: str, seed: int, pass_type: str, status: str, score: float, duration: float, metadata: dict = None):
        """
        Appends a structured execution record to trace.jsonl.
        """
        record = {
            "timestamp": time.time(),
            "task_id": task_id,
            "seed": seed,
            "pass_type": pass_type,  # 'baseline', 'first_pass', 'second_pass', 'held_out', 'naive_stream'
            "status": status,        # 'passed', 'failed_syntax', 'failed_runtime', etc.
            "score": score,          # Float, e.g. 0.0 - 10.0
            "duration_seconds": duration,
            "metadata": metadata or {}
        }
        
        # Estimate token usage (rough approximation: 1 token = 4 characters of inputs/outputs)
        input_len = len(str(metadata.get("prompt", ""))) if metadata else 0
        output_len = len(str(metadata.get("code", ""))) if metadata else 0
        record["estimated_tokens"] = (input_len + output_len) // 4
        record["estimated_cost_usd"] = (record["estimated_tokens"] / 1000) * 0.000075 # Gemini 2.5 Flash input/output average cost
        
        try:
            with open(self.trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error writing to trace file: {e}")

    def log_exploration_step(self, seed: int, step: str, detail: dict):
        """
        Structured trace for explore -> propose -> probe -> solve -> verify -> consolidate.
        """
        record = {
            "timestamp": time.time(),
            "pass_type": "exploration_step",
            "seed": seed,
            "step": step,
            "detail": detail,
        }
        try:
            with open(self.trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error writing exploration step to trace file: {e}")

    def log_lifecycle_event(self, event_type: str, namespace: str, detail: dict):
        """
        Logs memory engine lifecycle events (deduplication, conflict resolution, capacity enforcement) to trace.jsonl.
        """
        record = {
            "timestamp": time.time(),
            "pass_type": "lifecycle_event",
            "event_type": event_type,
            "namespace": namespace,
            "detail": detail
        }
        try:
            with open(self.trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error writing lifecycle event to trace file: {e}")

    def load_all_runs(self) -> list[dict]:
        if not os.path.exists(self.trace_file):
            return []
        runs = []
        try:
            with open(self.trace_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        runs.append(json.loads(line))
        except Exception as e:
            print(f"Error reading trace file: {e}")
        return runs

    def paired_t_test(self, x, y):
        import math
        n = len(x)
        if n <= 1:
            return 0.0, 1.0
        differences = np.array(y) - np.array(x)
        mean_diff = np.mean(differences)
        std_diff = np.std(differences, ddof=1)
        if std_diff == 0:
            return 0.0, 1.0 if mean_diff == 0 else 0.0
        t_stat = mean_diff / (std_diff / math.sqrt(n))
        p_val = 1.0 - math.erf(abs(t_stat) / math.sqrt(2.0))
        return float(t_stat), float(p_val)

    def calculate_metrics(self) -> dict:
        """
        Aggregates logs to compute baseline scores, First Pass, Second Pass,
        and computes Plasticity Gain (PG), Stability Gain (SG), and Generalization Gain (GG).
        Now calculates variance (std) and paired t-test p-value significance.
        Also calculates Active Exploration metrics (skill coverage, novelty, oracle validation, self-verified success).
        """
        all_raw_runs = self.load_all_runs()
        runs = [r for r in all_raw_runs if isinstance(r, dict) and "task_id" in r and r.get("pass_type") not in ("lifecycle_event", "exploration_step")]
        if not runs and not any(r.get("pass_type") in ("exploration", "exploration_step") for r in all_raw_runs):
            return {}
            
        # Check if sandbox fallback was used in any run
        sandbox_fallback_detected = False
        for r in runs:
            meta = r.get("metadata", {})
            if isinstance(meta, dict) and meta.get("execution_mode") == "local_subprocess_fallback":
                sandbox_fallback_detected = True
                break

        # Group runs by task_id, pass_type
        # We average scores over seeds for statistical rigor
        grouped = {}
        for r in runs:
            key = (r["task_id"], r["pass_type"])
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r["score"])
            
        # Compute mean and std scores
        mean_scores = {}
        std_scores = {}
        for (task_id, pass_type), scores in grouped.items():
            mean_scores[(task_id, pass_type)] = np.mean(scores)
            std_scores[(task_id, pass_type)] = np.std(scores) if len(scores) > 1 else 0.0
            
        # Calculate paired t-test between baseline and second_pass
        baseline_paired = []
        second_pass_paired = []
        baseline_map = {}
        second_pass_map = {}
        
        for r in runs:
            if r["pass_type"] == "baseline":
                baseline_map[(r["task_id"], r["seed"])] = r["score"]
            elif r["pass_type"] == "second_pass":
                second_pass_map[(r["task_id"], r["seed"])] = r["score"]
                
        common_keys = sorted(list(set(baseline_map.keys()).intersection(second_pass_map.keys())))
        for k in common_keys:
            baseline_paired.append(baseline_map[k])
            second_pass_paired.append(second_pass_map[k])
            
        t_stat, p_value = None, None
        if len(common_keys) > 1:
            t_stat, p_value = self.paired_t_test(baseline_paired, second_pass_paired)

        # Group tasks into lists
        all_task_ids = sorted(list(set(r["task_id"] for r in runs)))
        
        task_metrics = []
        run_records = [r for r in all_raw_runs if isinstance(r, dict) and "task_id" in r and r.get("pass_type") != "lifecycle_event"]
        total_tokens = sum(r.get("estimated_tokens", 0) for r in run_records)
        total_cost = sum(r.get("estimated_cost_usd", 0.0) for r in run_records)
        total_duration = sum(r.get("duration_seconds", 0.0) for r in run_records)
        
        for tid in all_task_ids:
            # Baseline (B_i)
            b_score = mean_scores.get((tid, "baseline"), 0.0)
            b_std = std_scores.get((tid, "baseline"), 0.0)
            # First Pass (F_i)
            f_score = mean_scores.get((tid, "first_pass"), 0.0)
            f_std = std_scores.get((tid, "first_pass"), 0.0)
            # Second Pass (S_i)
            s_score = mean_scores.get((tid, "second_pass"), 0.0)
            s_std = std_scores.get((tid, "second_pass"), 0.0)
            # Held out (H_j)
            h_score = mean_scores.get((tid, "held_out"), 0.0)
            h_std = std_scores.get((tid, "held_out"), 0.0)
            
            # Gains
            pg = f_score - b_score if (tid, "first_pass") in mean_scores and (tid, "baseline") in mean_scores else None
            sg = s_score - f_score if (tid, "second_pass") in mean_scores and (tid, "first_pass") in mean_scores else None
            gg = h_score - b_score if (tid, "held_out") in mean_scores and (tid, "baseline") in mean_scores else None
            
            task_metrics.append({
                "task_id": tid,
                "baseline": b_score,
                "baseline_std": b_std,
                "first_pass": f_score if (tid, "first_pass") in mean_scores else None,
                "first_pass_std": f_std if (tid, "first_pass") in mean_scores else 0.0,
                "second_pass": s_score if (tid, "second_pass") in mean_scores else None,
                "second_pass_std": s_std if (tid, "second_pass") in mean_scores else 0.0,
                "held_out": h_score if (tid, "held_out") in mean_scores else None,
                "held_out_std": h_std if (tid, "held_out") in mean_scores else 0.0,
                "plasticity_gain": pg,
                "stability_gain": sg,
                "generalization_gain": gg
            })
            
        # Calculate overall averages
        valid_pgs = [m["plasticity_gain"] for m in task_metrics if m["plasticity_gain"] is not None]
        valid_sgs = [m["stability_gain"] for m in task_metrics if m["stability_gain"] is not None]
        valid_ggs = [m["generalization_gain"] for m in task_metrics if m["generalization_gain"] is not None]

        # Calculate Active Exploration metrics
        exploration_steps = [r for r in all_raw_runs if isinstance(r, dict) and r.get("pass_type") == "exploration_step"]
        
        # 1. Skill coverage (from skill_gap_analyzer)
        try:
            from src.exploration.skill_gap_analyzer import skill_gap_analyzer, CAPABILITY_TAXONOMY, _infer_capabilities
            gap_info = skill_gap_analyzer.analyze()
            coverage_rate = gap_info.get("coverage_rate", 0.0)
            covered_caps = gap_info.get("covered_capabilities", [])
            gap_caps = gap_info.get("gap_capabilities", [])
            skill_backed_coverage_rate = gap_info.get("skill_backed_coverage_rate", 0.0)
            skill_backed_covered = gap_info.get("skill_backed_covered", [])
            skill_backed_gaps = gap_info.get("skill_backed_gap_capabilities", [])
            
            # Compute coverage delta specifically from exploration
            active_skills = skill_gap_analyzer.skill_composition_instance.get_active_skills()
            insights = skill_gap_analyzer.memory_engine.get_all_memories(namespace="insight")
            initial_covered = set()
            for sk in active_skills:
                meta = sk.get("metadata", {})
                task_id = meta.get("task_id", "")
                if not (task_id and task_id.startswith("EXP_")):
                    name = meta.get("name", "")
                    doc = meta.get("docstring", "")
                    code = sk.get("content", "")
                    initial_covered |= _infer_capabilities(f"{name} {doc} {code}")
                    
            for ins in insights:
                task_id = ins.get("metadata", {}).get("task_id", "")
                if not (task_id and task_id.startswith("EXP_")):
                    initial_covered |= _infer_capabilities(ins.get("content", ""))
                    
            initial_coverage_rate = 1.0 - (len([c for c in CAPABILITY_TAXONOMY if c not in initial_covered]) / len(CAPABILITY_TAXONOMY))
            coverage_delta = coverage_rate - initial_coverage_rate
        except Exception as e:
            print(f"Error analyzing skill gaps for dashboard: {e}")
            coverage_rate = 0.0
            covered_caps = []
            gap_caps = []
            skill_backed_coverage_rate = 0.0
            skill_backed_covered = []
            skill_backed_gaps = []
            coverage_delta = 0.0
            
        # 2. Novelty scores trend
        novelty_scores = []
        for r in exploration_steps:
            if r.get("step") == "task_proposed":
                detail = r.get("detail", {})
                score = detail.get("novelty_score")
                if score is not None:
                    novelty_scores.append({
                        "task_id": detail.get("task_id", "Unknown"),
                        "novelty": score,
                        "timestamp": r.get("timestamp")
                    })
                    
        # 3. Oracle validation rate
        validated_count = sum(1 for r in exploration_steps if r.get("step") == "oracle_validated")
        rejected_count = sum(1 for r in exploration_steps if r.get("step") == "oracle_rejected")
        total_proposed = sum(1 for r in exploration_steps if r.get("step") == "task_proposed")
        
        oracle_validation_rate = 0.0
        if (validated_count + rejected_count) > 0:
            oracle_validation_rate = validated_count / (validated_count + rejected_count)
        elif total_proposed > 0:
            oracle_validation_rate = 1.0
            
        # 4. Success rate of self-proposed tasks
        explore_tasks_run = [r for r in all_raw_runs if isinstance(r, dict) and r.get("pass_type") == "exploration" and r.get("metadata", {}).get("exploration", {}).get("source") == "explore_proposed"]
        passed_explore_tasks = [r for r in explore_tasks_run if r.get("status") == "passed"]
        self_verified_success_rate = len(passed_explore_tasks) / len(explore_tasks_run) if len(explore_tasks_run) > 0 else 0.0
        
        # Log failed exploration stderrs
        failed_exploration_logs = []
        for r in all_raw_runs:
            if isinstance(r, dict) and r.get("pass_type") == "exploration":
                if r.get("status") != "passed":
                    task_id = r.get("task_id", "Unknown")
                    err_msg = r.get("metadata", {}).get("message", "")
                    stderr = r.get("metadata", {}).get("stderr", "")
                    failed_exploration_logs.append({
                        "task_id": task_id,
                        "status": r.get("status"),
                        "error_message": err_msg,
                        "stderr": stderr
                    })
                    
        # Seed breakdown
        seed_breakdown = {}
        for r in explore_tasks_run:
            sd = r.get("seed")
            if sd is not None:
                if sd not in seed_breakdown:
                    seed_breakdown[sd] = {"passed": 0, "total": 0}
                seed_breakdown[sd]["total"] += 1
                if r.get("status") == "passed":
                    seed_breakdown[sd]["passed"] += 1
                    
        # Convert seed breakdown to string format
        seed_breakdown_str = ", ".join(f"Seed {s}: {stats['passed']}/{stats['total']}" for s, stats in sorted(seed_breakdown.items()))

        return {
            "tasks": task_metrics,
            "summary": {
                "mean_plasticity_gain": np.mean(valid_pgs) if valid_pgs else 0.0,
                "mean_stability_gain": np.mean(valid_sgs) if valid_sgs else 0.0,
                "mean_generalization_gain": np.mean(valid_ggs) if valid_ggs else 0.0,
                "total_tokens_consumed": total_tokens,
                "total_estimated_cost_usd": total_cost,
                "total_execution_time_seconds": total_duration,
                "total_runs": len(runs) + len(explore_tasks_run),
                "sandbox_fallback_detected": sandbox_fallback_detected,
                "p_value": p_value,
                "t_stat": t_stat
            },
            "exploration": {
                "coverage_rate": coverage_rate,
                "covered_capabilities": covered_caps,
                "gap_capabilities": gap_caps,
                "skill_backed_coverage_rate": skill_backed_coverage_rate,
                "skill_backed_covered": skill_backed_covered,
                "skill_backed_gaps": skill_backed_gaps,
                "coverage_delta": coverage_delta,
                "novelty_scores": novelty_scores,
                "validated_count": validated_count,
                "rejected_count": rejected_count,
                "oracle_validation_rate": oracle_validation_rate,
                "self_verified_success_rate": self_verified_success_rate,
                "explore_tasks_count": len(explore_tasks_run),
                "passed_explore_tasks_count": len(passed_explore_tasks),
                "failed_exploration_logs": failed_exploration_logs,
                "seed_breakdown_str": seed_breakdown_str
            }
        }

    def generate_html_dashboard(self):
        """
        Generates a premium HTML report displaying the evolutionary coding agent metrics.
        """
        metrics = self.calculate_metrics()
        if not metrics:
            print("No trace data available to generate dashboard.")
            return
            
        # JSON dump metrics to embed directly in Javascript
        embedded_json = json.dumps(metrics, ensure_ascii=False, indent=2)
        
        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evolutionary Coding Agent - Dashboard Chỉ Số</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(30, 41, 59, 0.7);
            --primary: #8b5cf6;
            --primary-glow: rgba(139, 92, 246, 0.4);
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text-color: #f1f5f9;
            --text-muted: #94a3b8;
            --border: rgba(255, 255, 255, 0.08);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-color);
            min-height: 100vh;
            padding: 2rem;
            background-image: 
                radial-gradient(at 10% 20%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 90% 80%, rgba(16, 185, 129, 0.1) 0px, transparent 50%);
            background-attachment: fixed;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.5rem;
        }}

        .logo h1 {{
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #a78bfa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .logo p {{
            color: var(--text-muted);
            margin-top: 0.2rem;
        }}

        .timestamp {{
            font-size: 0.9rem;
            color: var(--text-muted);
            background: var(--card-bg);
            padding: 0.5rem 1rem;
            border-radius: 50px;
            border: 1px solid var(--border);
        }}

        /* Sandbox Warning Banner */
        .warning-banner {{
            display: none;
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid var(--danger);
            color: var(--text-color);
            padding: 1.2rem;
            border-radius: 16px;
            margin-bottom: 2.5rem;
            align-items: center;
            gap: 12px;
            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.2);
            backdrop-filter: blur(10px);
        }}

        /* Summary Cards */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}

        .card {{
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease, border-color 0.3s ease;
        }}

        .card:hover {{
            transform: translateY(-5px);
            border-color: rgba(139, 92, 246, 0.3);
        }}

        .card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--primary);
        }}

        .card.success::before {{ background: var(--success); }}
        .card.warning::before {{ background: var(--warning); }}

        .card-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .card-value {{
            font-size: 1.8rem;
            font-weight: 800;
        }}

        .card-desc {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.4rem;
        }}

        /* Main Section */
        .main-grid {{
            display: grid;
            grid-template-columns: 1.8fr 1.2fr;
            gap: 2rem;
            margin-bottom: 2.5rem;
        }}

        @media (max-width: 900px) {{
            .main-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .chart-panel, .list-panel {{
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }}

        .panel-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.8rem;
        }}

        /* Table */
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}

        th, td {{
            padding: 0.8rem 1rem;
            border-bottom: 1px solid var(--border);
        }}

        th {{
            color: var(--text-muted);
            font-size: 0.85rem;
            text-transform: uppercase;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        .badge {{
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
        }}

        .badge-positive {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
        }}

        .badge-negative {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
        }}

        .badge-neutral {{
            background: rgba(148, 163, 184, 0.15);
            color: var(--text-muted);
        }}

        /* Active Exploration Styles */
        .section-header {{
            font-size: 1.6rem;
            font-weight: 700;
            margin-top: 3rem;
            margin-bottom: 1.5rem;
            background: linear-gradient(135deg, #a78bfa, #60a5fa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.5rem;
        }}

        .exploration-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 3rem;
        }}

        @media (max-width: 900px) {{
            .exploration-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .capability-badge {{
            display: inline-block;
            padding: 0.4rem 0.8rem;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }}

        .capability-covered {{
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--success);
        }}

        .capability-gap {{
            background: rgba(245, 158, 11, 0.12);
            border: 1px solid rgba(245, 158, 11, 0.3);
            color: var(--warning);
        }}

        .progress-bar-container {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            height: 10px;
            width: 100%;
            overflow: hidden;
            margin-top: 8px;
        }}

        .progress-bar {{
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--success));
            border-radius: 8px;
            transition: width 0.5s ease-in-out;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                <h1>Evolutionary Coding Agent</h1>
                <p>Khung đánh giá AgentCL & Cơ chế bộ nhớ MemProbe</p>
            </div>
            <div class="timestamp" id="current-time">Đang tải...</div>
        </header>

        <!-- Sandbox Warning Banner -->
        <div class="warning-banner" id="sandbox-warning">
            <span style="font-size: 1.8rem;">⚠️</span>
            <div>
                <strong style="color: var(--danger); text-transform: uppercase; display: block; margin-bottom: 2px;">Cảnh Báo Cách Ly Sandbox Thất Bại</strong>
                <span style="font-size: 0.9rem; opacity: 0.9;">
                    Hệ thống đã tự động kích hoạt chế độ fallback <strong>Local Subprocess</strong> (không cô lập) do không kết nối được Docker daemon.
                    Hãy bật Docker daemon trước khi chạy đánh giá để kích hoạt các giới hạn CPU, bộ nhớ và an toàn mạng.
                </span>
            </div>
        </div>

        <!-- Cards -->
        <div class="summary-grid">
            <div class="card">
                <div class="card-label">Plasticity Gain (PG)</div>
                <div class="card-value" id="pg-val">0.00</div>
                <div class="card-desc">Khả năng vừa học vừa làm kỹ năng mới (F_i - B_i)</div>
            </div>
            <div class="card success">
                <div class="card-label">Stability Gain (SG)</div>
                <div class="card-value" id="sg-val">0.00</div>
                <div class="card-desc">Độ ổn định khi đóng băng bộ nhớ (S_i - F_i)</div>
            </div>
            <div class="card warning">
                <div class="card-label">Generalization Gain (GG)</div>
                <div class="card-value" id="gg-val">0.00</div>
                <div class="card-desc">Khả năng tổng quát trên Held-out tasks</div>
            </div>
            <div class="card" id="p-val-card">
                <div class="card-label">Kiểm định p-value</div>
                <div class="card-value" id="p-val">N/A</div>
                <div class="card-desc" id="p-desc">So sánh t-test (p &lt; 0.05 là tối ưu)</div>
            </div>
            <div class="card">
                <div class="card-label">Chi phí / Token</div>
                <div class="card-value" id="cost-val">$0.00</div>
                <div class="card-desc" id="token-val">0 tokens consumed</div>
            </div>
        </div>

        <!-- Charts & Tasks -->
        <div class="main-grid">
            <div class="chart-panel">
                <div class="panel-title">Biểu Đồ So Sánh Điểm Số Các Task</div>
                <canvas id="scoresChart" style="max-height: 400px;"></canvas>
            </div>
            
            <div class="list-panel">
                <div class="panel-title">Chỉ Số Chi Tiết Theo Task (± std)</div>
                <table id="tasks-table">
                    <thead>
                        <tr>
                            <th>Task ID</th>
                            <th>Baseline (B_i)</th>
                            <th>First Pass (F_i)</th>
                            <th>Second Pass (S_i)</th>
                            <th>PG</th>
                            <th>SG</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Inserted via JS -->
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Phase 5 Active Exploration Section -->
        <div class="section-header">Phase 5: Kết Quả Active Exploration</div>
        
        <div class="summary-grid">
            <div class="card">
                <div class="card-label">Keyword (Taxonomy) Coverage</div>
                <div class="card-value" id="coverage-val">0%</div>
                <div class="progress-bar-container">
                    <div class="progress-bar" id="coverage-bar" style="width: 0%"></div>
                </div>
                <div class="card-desc" id="coverage-desc">Bao phủ 0/10 Capabilities trong Taxonomy</div>
                <div style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--text-muted);">
                    Delta: <span id="coverage-delta-val" style="color: var(--success); font-weight: bold;">+0%</span>
                </div>
            </div>
            <div class="card">
                <div class="card-label">Skill-Backed Coverage</div>
                <div class="card-value" id="skill-backed-coverage-val">0%</div>
                <div class="progress-bar-container">
                    <div class="progress-bar" id="skill-backed-coverage-bar" style="width: 0%; background-color: var(--primary);"></div>
                </div>
                <div class="card-desc" id="skill-backed-coverage-desc">Bao phủ 0/10 Capabilities (Verified skills only)</div>
            </div>
            <div class="card success">
                <div class="card-label">Oracle Validation Rate</div>
                <div class="card-value" id="oracle-val">0%</div>
                <div class="card-desc" id="oracle-desc">0 validated / 0 rejected oracles</div>
            </div>
            <div class="card warning">
                <div class="card-label">Self-Proposed Task Success</div>
                <div class="card-value" id="self-success-val">0%</div>
                <div class="card-desc" id="self-success-desc">Đã chạy 0 task (Passed 0)</div>
                <div style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--text-muted);" id="seed-breakdown-val">
                    Seed breakdown: N/A
                </div>
            </div>
        </div>

        <div class="exploration-grid">
            <div class="chart-panel">
                <div class="panel-title">Lịch Sử Novelty Score Tự Đề Xuất</div>
                <canvas id="noveltyChart" style="max-height: 300px;"></canvas>
            </div>
            
            <div class="list-panel">
                <div class="panel-title">Phân Tích Năng Lực (Capabilities Taxonomy)</div>
                <div style="margin-bottom: 1.5rem; font-size: 0.9rem; color: var(--text-muted);">
                    So sánh độ bao phủ năng lực theo từ khóa (Keyword Matching) và năng lực thực tế được chứng thực bởi Skill đã được test (Verified Skill-Backed).
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                    <div>
                        <h4 style="font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--primary);">Từ Khóa (Keyword Matching)</h4>
                        <div style="margin-bottom: 0.8rem;">
                            <strong style="font-size: 0.85rem; color: var(--text-muted);">Đã bao phủ:</strong>
                            <div id="covered-caps-list" style="margin-top: 0.3rem;"></div>
                        </div>
                        <div>
                            <strong style="font-size: 0.85rem; color: var(--text-muted);">Lỗ hổng (Gaps):</strong>
                            <div id="gap-caps-list" style="margin-top: 0.3rem;"></div>
                        </div>
                    </div>
                    <div>
                        <h4 style="font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--success);">Thực Tế (Verified Skill-Backed)</h4>
                        <div style="margin-bottom: 0.8rem;">
                            <strong style="font-size: 0.85rem; color: var(--text-muted);">Đã bao phủ:</strong>
                            <div id="skill-backed-covered-list" style="margin-top: 0.3rem;"></div>
                        </div>
                        <div>
                            <strong style="font-size: 0.85rem; color: var(--text-muted);">Lỗ hổng (Gaps):</strong>
                            <div id="skill-backed-gap-list" style="margin-top: 0.3rem;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Failed Exploration Trace Stderrs -->
        <div class="chart-panel" style="margin-top: 1.5rem; display: none;" id="failed-logs-panel">
            <div class="panel-title" style="color: var(--danger);">Nhật Ký Lỗi Runtime / Thất Bại Active Exploration</div>
            <div id="failed-logs-list" style="margin-top: 1rem; font-family: monospace; font-size: 0.85rem; max-height: 300px; overflow-y: auto;">
            </div>
        </div>
    </div>

    <script>
        // Set timestamp
        document.getElementById('current-time').innerText = "Cập nhật lúc: " + new Date().toLocaleString('vi-VN');

        // Embedded data
        const data = {embedded_json};
        
        // Populate cards
        const summary = data.summary;
        document.getElementById('pg-val').innerText = (summary.mean_plasticity_gain >= 0 ? "+" : "") + summary.mean_plasticity_gain.toFixed(2);
        document.getElementById('sg-val').innerText = (summary.mean_stability_gain >= 0 ? "+" : "") + summary.mean_stability_gain.toFixed(2);
        document.getElementById('gg-val').innerText = (summary.mean_generalization_gain >= 0 ? "+" : "") + summary.mean_generalization_gain.toFixed(2);
        document.getElementById('cost-val').innerText = "$" + summary.total_estimated_cost_usd.toFixed(4);
        document.getElementById('token-val').innerText = summary.total_tokens_consumed.toLocaleString() + " tokens";
        
        // Show Sandbox Warning banner
        if (summary.sandbox_fallback_detected) {{
            document.getElementById('sandbox-warning').style.display = 'flex';
        }}

        // Populate p-value card
        const pCard = document.getElementById('p-val-card');
        const pValText = document.getElementById('p-val');
        const pDescText = document.getElementById('p-desc');
        
        if (summary.p_value !== null && summary.p_value !== undefined) {{
            const pv = summary.p_value;
            pValText.innerText = pv.toFixed(4);
            if (pv < 0.05) {{
                pCard.classList.add('success');
                pValText.style.color = 'var(--success)';
                pDescText.innerHTML = `Có ý nghĩa thống kê (p = ${{pv.toFixed(4)}} < 0.05)`;
            }} else {{
                pValText.style.color = 'var(--warning)';
                pDescText.innerHTML = `Ít ý nghĩa thống kê (p = ${{pv.toFixed(4)}} >= 0.05)`;
            }}
        }} else {{
            pValText.innerText = "N/A";
            pDescText.innerText = "Chưa có đủ dữ liệu seed để tính";
        }}
        
        // Color cards based on value
        if (summary.mean_plasticity_gain < 0) {{
            document.getElementById('pg-val').parentElement.classList.add('danger');
        }}
        if (summary.mean_stability_gain < 0) {{
            document.getElementById('sg-val').parentElement.classList.add('danger');
        }}

        // Populate table
        const tbody = document.querySelector('#tasks-table tbody');
        data.tasks.forEach(t => {{
            const tr = document.createElement('tr');
            
            let pgBadge = '<span class="badge badge-neutral">N/A</span>';
            if (t.plasticity_gain !== null) {{
                const cls = t.plasticity_gain > 0 ? 'badge-positive' : (t.plasticity_gain < 0 ? 'badge-danger' : 'badge-neutral');
                pgBadge = `<span class="badge ${{cls}}">${{t.plasticity_gain > 0 ? '+' : ''}}${{t.plasticity_gain.toFixed(2)}}</span>`;
            }}
            
            let sgBadge = '<span class="badge badge-neutral">N/A</span>';
            if (t.stability_gain !== null) {{
                const cls = t.stability_gain > 0 ? 'badge-positive' : (t.stability_gain < 0 ? 'badge-danger' : 'badge-neutral');
                sgBadge = `<span class="badge ${{cls}}">${{t.stability_gain > 0 ? '+' : ''}}${{t.stability_gain.toFixed(2)}}</span>`;
            }}
            
            const bVal = `${{t.baseline.toFixed(1)}} ± ${{t.baseline_std.toFixed(2)}}`;
            const fVal = t.first_pass !== null ? `${{t.first_pass.toFixed(1)}} ± ${{t.first_pass_std.toFixed(2)}}` : 'N/A';
            const sVal = t.second_pass !== null ? `${{t.second_pass.toFixed(1)}} ± ${{t.second_pass_std.toFixed(2)}}` : 'N/A';

            tr.innerHTML = `
                <td><strong>${{t.task_id}}</strong></td>
                <td>${{bVal}}</td>
                <td>${{fVal}}</td>
                <td>${{sVal}}</td>
                <td>${{pgBadge}}</td>
                <td>${{sgBadge}}</td>
            `;
            tbody.appendChild(tr);
        }});

        // Draw Chart
        const labels = data.tasks.map(t => t.task_id);
        const baselineData = data.tasks.map(t => t.baseline);
        const firstPassData = data.tasks.map(t => t.first_pass || 0);
        const secondPassData = data.tasks.map(t => t.second_pass || 0);

        const ctx = document.getElementById('scoresChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'Baseline (B_i)',
                        data: baselineData,
                        backgroundColor: 'rgba(148, 163, 184, 0.4)',
                        borderColor: '#94a3b8',
                        borderWidth: 1
                    }},
                    {{
                        label: 'First Pass (F_i)',
                        data: firstPassData,
                        backgroundColor: 'rgba(139, 92, 246, 0.6)',
                        borderColor: '#8b5cf6',
                        borderWidth: 1
                    }},
                    {{
                        label: 'Second Pass (S_i)',
                        data: secondPassData,
                        backgroundColor: 'rgba(16, 185, 129, 0.6)',
                        borderColor: '#10b981',
                        borderWidth: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        labels: {{ color: '#f1f5f9' }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    y: {{
                        min: 0,
                        max: 10,
                        grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                        ticks: {{ color: '#94a3b8' }}
                    }}
                }}
            }}
        }});

        // Active Exploration Population
        if (data.exploration) {{
            const exp = data.exploration;
            
            // Populate Cards
            const covPercent = (exp.coverage_rate * 100).toFixed(0);
            document.getElementById('coverage-val').innerText = covPercent + "%";
            document.getElementById('coverage-bar').style.width = covPercent + "%";
            
            const totalCapsCount = (exp.covered_capabilities ? exp.covered_capabilities.length : 0) + (exp.gap_capabilities ? exp.gap_capabilities.length : 0);
            const coveredCount = exp.covered_capabilities ? exp.covered_capabilities.length : 0;
            document.getElementById('coverage-desc').innerText = `Bao phủ ${{coveredCount}}/${{totalCapsCount || 10}} Capabilities (Keyword matching)`;
            
            // Delta
            const covDelta = (exp.coverage_delta * 100).toFixed(0);
            document.getElementById('coverage-delta-val').innerText = (exp.coverage_delta >= 0 ? "+" : "") + covDelta + "%";
            
            // Skill Backed Coverage
            const skillCovPercent = (exp.skill_backed_coverage_rate * 100).toFixed(0);
            document.getElementById('skill-backed-coverage-val').innerText = skillCovPercent + "%";
            document.getElementById('skill-backed-coverage-bar').style.width = skillCovPercent + "%";
            
            const skillCoveredCount = exp.skill_backed_covered ? exp.skill_backed_covered.length : 0;
            document.getElementById('skill-backed-coverage-desc').innerText = `Bao phủ ${{skillCoveredCount}}/${{totalCapsCount || 10}} Capabilities (Verified skills only)`;

            const oracleRate = (exp.oracle_validation_rate * 100).toFixed(0);
            document.getElementById('oracle-val').innerText = oracleRate + "%";
            document.getElementById('oracle-desc').innerText = `${{exp.validated_count || 0}} validated / ${{exp.rejected_count || 0}} rejected oracles`;
            
            const selfRate = (exp.self_verified_success_rate * 100).toFixed(0);
            document.getElementById('self-success-val').innerText = selfRate + "%";
            document.getElementById('self-success-desc').innerText = `Đã chạy ${{exp.explore_tasks_count || 0}} task (Passed ${{exp.passed_explore_tasks_count || 0}})`;
            
            // Seed breakdown
            if (exp.seed_breakdown_str) {{
                document.getElementById('seed-breakdown-val').innerText = "Chi tiết: " + exp.seed_breakdown_str;
            }}
            
            // Failed stderrs logs
            if (exp.failed_exploration_logs && exp.failed_exploration_logs.length > 0) {{
                const failedPanel = document.getElementById('failed-logs-panel');
                const failedList = document.getElementById('failed-logs-list');
                failedPanel.style.display = 'block';
                failedList.innerHTML = '';
                
                exp.failed_exploration_logs.forEach(log => {{
                    const div = document.createElement('div');
                    div.style.marginBottom = '1.5rem';
                    div.style.padding = '1rem';
                    div.style.backgroundColor = 'rgba(239, 68, 68, 0.05)';
                    div.style.borderLeft = '3px solid var(--danger)';
                    div.style.borderRadius = '4px';
                    
                    const title = document.createElement('div');
                    title.style.fontWeight = 'bold';
                    title.style.color = 'var(--danger)';
                    title.style.marginBottom = '0.5rem';
                    title.innerText = `Task: ${{log.task_id}} (${{log.status}})`;
                    
                    const errMsg = document.createElement('div');
                    errMsg.style.color = 'var(--text-color)';
                    errMsg.style.marginBottom = '0.5rem';
                    errMsg.innerText = log.error_message;
                    
                    const pre = document.createElement('pre');
                    pre.style.color = 'var(--text-muted)';
                    pre.style.overflowX = 'auto';
                    pre.style.whiteSpace = 'pre-wrap';
                    pre.innerText = log.stderr || 'No stderr logged.';
                    
                    div.appendChild(title);
                    div.appendChild(errMsg);
                    div.appendChild(pre);
                    failedList.appendChild(div);
                }});
            }}
            
            // Covered and Gap Capabilities
            const coveredList = document.getElementById('covered-caps-list');
            if (exp.covered_capabilities && exp.covered_capabilities.length > 0) {{
                exp.covered_capabilities.forEach(cap => {{
                    const span = document.createElement('span');
                    span.className = 'capability-badge capability-covered';
                    span.innerText = cap;
                    coveredList.appendChild(span);
                }});
            }} else {{
                coveredList.innerHTML = '<span style="color: var(--text-muted); font-size: 0.9rem;">Chưa có kỹ năng nào được ghi nhận</span>';
            }}
            
            const gapList = document.getElementById('gap-caps-list');
            if (exp.gap_capabilities && exp.gap_capabilities.length > 0) {{
                exp.gap_capabilities.forEach(cap => {{
                    const span = document.createElement('span');
                    span.className = 'capability-badge capability-gap';
                    span.innerText = cap;
                    gapList.appendChild(span);
                }});
            }} else {{
                gapList.innerHTML = '<span style="color: var(--success); font-size: 0.9rem;">Không còn khoảng trống năng lực nào!</span>';
            }}

            // Skill Backed Covered and Gap Capabilities
            const skillCoveredList = document.getElementById('skill-backed-covered-list');
            if (exp.skill_backed_covered && exp.skill_backed_covered.length > 0) {{
                exp.skill_backed_covered.forEach(cap => {{
                    const span = document.createElement('span');
                    span.className = 'capability-badge capability-covered';
                    span.innerText = cap;
                    skillCoveredList.appendChild(span);
                }});
            }} else {{
                skillCoveredList.innerHTML = '<span style="color: var(--text-muted); font-size: 0.9rem;">Chưa có skill được xác minh</span>';
            }}
            
            const skillGapList = document.getElementById('skill-backed-gap-list');
            if (exp.skill_backed_gaps && exp.skill_backed_gaps.length > 0) {{
                exp.skill_backed_gaps.forEach(cap => {{
                    const span = document.createElement('span');
                    span.className = 'capability-badge capability-gap';
                    span.innerText = cap;
                    skillGapList.appendChild(span);
                }});
            }} else {{
                skillGapList.innerHTML = '<span style="color: var(--success); font-size: 0.9rem;">Không còn khoảng trống (100% Verified)!</span>';
            }}
            
            // Draw Novelty Chart
            const noveltyCtx = document.getElementById('noveltyChart').getContext('2d');
            const noveltyData = exp.novelty_scores || [];
            
            const noveltyLabels = noveltyData.map((n, idx) => `Task ${{idx + 1}} (${{n.task_id}})`);
            const noveltyVals = noveltyData.map(n => n.novelty);
            
            new Chart(noveltyCtx, {{
                type: 'line',
                data: {{
                    labels: noveltyLabels.length > 0 ? noveltyLabels : ['Chưa có dữ liệu'],
                    datasets: [{{
                        label: 'Novelty Score',
                        data: noveltyVals.length > 0 ? noveltyVals : [0],
                        borderColor: '#a78bfa',
                        backgroundColor: 'rgba(167, 139, 250, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#94a3b8' }}
                        }},
                        y: {{
                            min: 0,
                            max: 1.0,
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            ticks: {{ color: '#94a3b8' }}
                        }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
"""
        try:
            with open(self.dashboard_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Generated Beautiful HTML Dashboard at: {self.dashboard_file}")
        except Exception as e:
            print(f"Error generating dashboard HTML: {e}")


# Global observability manager
observability_manager = ObservabilityManager()
