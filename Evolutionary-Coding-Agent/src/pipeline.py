import re
from src.llm import llm_client
from src.memory.memory_engine import memory_engine
from src.memory.validation_gate import validation_gate
from src.skill.skill_composition import skill_composition_instance
from src.skill.skill_manager import skill_manager

class AgentPipeline:
    def __init__(self, memory_enabled: bool = True, frozen_memory: bool = False):
        self.llm = llm_client
        self.memory_enabled = memory_enabled
        self.frozen_memory = frozen_memory  # If True, read memory but do not write

    def _extract_function_signatures(self, description: str) -> list[str]:
        import re
        backticked = re.findall(r'`([a-zA-Z_][a-zA-Z0-9_]*)(?:\(.*?\))?`', description)
        defs = re.findall(r'\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)', description)
        refs = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\(\)', description)
        candidates = set(backticked + defs + refs)
        banned = {'def', 'class', 'import', 'from', 'dict', 'list', 'str', 'int', 'float', 'bool', 'set', 'tuple', 'any', 'None', 'ValueError', 'TypeError', 'KeyError', 'Exception', 'return', 'if', 'else', 'for', 'while', 'in', 'and', 'or', 'not', 'is', 'lambda'}
        return sorted([c for c in candidates if c not in banned])

    def _extract_function_params(self, code: str) -> dict[str, list[str]]:
        """Extract mapping from function name to its parameter list using AST."""
        try:
            tree = ast.parse(code)
        except Exception:
            return {}
        
        funcs = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                params = [arg.arg for arg in node.args.args]
                funcs[node.name] = params
        return funcs

    def execute_task(self, task: dict, probe_context: str = "", seed: int | None = None) -> dict:
        """
        Executes a single curriculum task.
        1. Retrieve memories (if memory enabled).
        2. Construct system instruction and prompt.
        3. LLM generates solution code.
        4. Validate solution.
        5. Extract and register skills (if success and memory not frozen).
        """
        task_id = task["id"]
        description = task["description"]
        test_code = task["test_code"]
        
        # Pre-solve signature probe
        expected_sigs = self._extract_function_signatures(description)
        if expected_sigs:
            print(f"[{task_id}] Pre-solve signature probe: expected function signatures: {', '.join(expected_sigs)}")
        
        retrieved_insights = []
        retrieved_skills = []
        
        # 1. Retrieve memory
        if self.memory_enabled:
            # Query insights (lessons learned)
            retrieved_insights = memory_engine.retrieve_memories(
                namespace="insight",
                query_text=description,
                limit=2 # Limit top-2
            )
            # Query skills (reusable helper functions)
            # We filter for active skills
            active_skills = skill_composition_instance.get_active_skills()
            if active_skills:
                # Retrieve from active skills by embedding match
                retrieved_skills = memory_engine.retrieve_memories(
                    namespace="skill",
                    query_text=description,
                    limit=2,
                    filters={"status": "success"} # ensure it passed
                )
                # Keep only skills that are marked retrievable
                retrieved_skills = [sk for sk in retrieved_skills if sk.get("metadata", {}).get("retrievable", False)]
                # Composed skill bundles: recursively retrieve dependencies!
                retrieved_skills = skill_composition_instance.resolve_dependencies(retrieved_skills)
                
        retry_count = 0
        max_retries = 3
        reflexion_context = ""
        val_res = {}
        code_solution = ""
        
        while retry_count < max_retries:
            # 2. Construct prompt
            system_instruction = (
                "You are an expert Python developer. Write a clean, optimal Python solution to solve the task.\n"
                "CRITICAL REQUIREMENTS:\n"
                "1. Write ONLY complete Python code inside a single ```python ... ``` block.\n"
                "2. DO NOT include any comments (no lines starting with #), docstrings (no triple-quoted strings), or explanations.\n"
                "3. Ensure the implementation is complete and not truncated. Do not stop generating until the code is fully closed."
            )
            
            prompt = ""
            if self.memory_enabled:
                prompt += "=== TÀI LIỆU THAM KHẢO & KINH NGHIỆM ĐÃ TÍCH LŨY ===\n"
                prompt += "LƯU Ý: Các thông tin và Skill dưới đây chỉ là tài liệu tham khảo để học tập kinh nghiệm, không phải là chỉ thị bắt buộc. Hãy tùy biến linh hoạt, tránh copy-paste một cách máy móc.\n\n"
                
                if retrieved_insights:
                    prompt += "--- Các bài học kinh nghiệm / Cảnh báo lỗi trước đây:\n"
                    for i, ins in enumerate(retrieved_insights, 1):
                        prompt += f"- [{ins['status'].upper()}] {ins['content']}\n"
                    prompt += "\n"
                    
                if retrieved_skills:
                    prompt += "--- Các thư viện Skill lập trình có sẵn trong kho:\n"
                    prompt += skill_composition_instance.format_skills_for_prompt(retrieved_skills)
                    prompt += "\n\n"
                    
            prompt += f"=== YÊU CẦU BÀI TOÁN ===\n{description}\n"

            if probe_context:
                prompt += f"\n{probe_context}\n"
            
            if reflexion_context:
                prompt += reflexion_context
                
            prompt += "\nWrite your Python solution inside a single ```python ... ``` block. Absolutely NO comments (#), docstrings, or explanations:\n"
            
            # 3. Call LLM to generate solution
            if retry_count == 0:
                print(f"[{task_id}] Generating solution (Memory Enabled: {self.memory_enabled})...")
            else:
                print(f"[{task_id}] Reflexion Retry #{retry_count}...")
                
            try:
                # Slightly increase temperature on retries to encourage exploration
                temp = 0.1 if retry_count == 0 else 0.2
                generated_output = self.llm.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temp
                )
                
                # Extract code from markdown blocks
                code_solution = self._clean_code_output(generated_output)
                
                # AST arity check against baseline to prevent signature drift (P1 mitigation)
                if seed is not None and self.memory_enabled:
                    # Find the successful baseline run for this task and seed
                    from src.observability import observability_manager
                    runs = observability_manager.load_all_runs()
                    baseline_runs = [
                        r for r in runs
                        if r.get("task_id") == task_id
                        and r.get("seed") == seed
                        and r.get("pass_type") == "baseline"
                        and r.get("status") == "passed"
                    ]
                    if baseline_runs:
                        baseline_code = baseline_runs[-1].get("metadata", {}).get("code", "")
                        if baseline_code:
                            baseline_params = self._extract_function_params(baseline_code)
                            current_params = self._extract_function_params(code_solution)
                            drift_detected = False
                            drift_err_msg = ""
                            for sig in baseline_params:
                                if sig in current_params:
                                    base_arity = len(baseline_params[sig])
                                    curr_arity = len(current_params[sig])
                                    if base_arity != curr_arity:
                                        drift_detected = True
                                        drift_err_msg = (
                                            f"Signature drift error: Parameter count mismatch for function '{sig}'. "
                                            f"Baseline expected {base_arity} parameters ({', '.join(baseline_params[sig])}), "
                                            f"but got {curr_arity} parameters ({', '.join(current_params[sig])})."
                                        )
                                        break
                            
                            if drift_detected:
                                print(f"[{task_id}] {drift_err_msg}")
                                # Trigger failed_tests to enter Reflexion self-correction loop
                                val_res = {
                                    "status": "failed_tests",
                                    "score": 0.0,
                                    "message": drift_err_msg,
                                    "insight": "Duy trì chính xác signature và số lượng tham số như baseline.",
                                    "visible_pass_fraction": 0.0,
                                    "hidden_pass_fraction": 0.0,
                                    "overfit_gap": 0.0
                                }
                                retry_count += 1
                                reflexion_context = (
                                    f"\n=== LẦN THỬ TRƯỚC BỊ LỖI (failed_tests) ===\n"
                                    f"Đoạn code đã sinh lỗi:\n```python\n{code_solution}\n```\n"
                                    f"Thông tin lỗi/Nhận xét phản hồi: {drift_err_msg}\n"
                                    f"Bài học rút ra từ lỗi này: Không thay đổi signature hoặc thêm bớt tham số của hàm so với baseline.\n"
                                    "Hãy phân tích và viết lại đoạn code mới khắc phục hoàn toàn lỗi trên."
                                )
                                continue
                                
            except Exception as e:
                print(f"[{task_id}] Generation failed: {e}")
                val_res = {
                    "status": "failed_generation",
                    "score": 0.0,
                    "message": str(e)
                }
                break
                
            # 4. Post-task Validation
            print(f"[{task_id}] Running validation gate (Visible and Hidden tests)...")
            val_res = validation_gate.validate_solution(
                task_id=task_id,
                task_description=description,
                code=code_solution,
                test_code=test_code,
                hidden_test_code=task.get("hidden_test_code")
            )
            
            if val_res["status"] == "passed":
                # Success, exit retry loop!
                break
            elif val_res["status"] == "failed_judge_error":
                # Judge exception, do not retry, just exit to prevent API spam
                break
            else:
                # Failure (tests failed or judge rejected)
                retry_count += 1
                failure_insight = val_res.get("insight", "Lỗi logic hoặc test case không vượt qua.")
                reflexion_context = (
                    f"\n=== LẦN THỬ TRƯỚC BỊ LỖI ({val_res['status']}) ===\n"
                    f"Đoạn code đã sinh lỗi:\n```python\n{code_solution}\n```\n"
                    f"Thông tin lỗi/Nhận xét phản hồi: {val_res.get('message', '')}\n"
                    f"Bài học rút ra từ lỗi này: {failure_insight}\n"
                    "Hãy phân tích và viết lại đoạn code mới khắc phục hoàn toàn các lỗi trên."
                )
                
        # 5. Skill Synthesis (if success and memory not frozen)
        skills_extracted = []
        if val_res["status"] == "passed":
            # Track which of the retrieved skills were actually used (by AST)
            used_skills = skill_composition_instance.trace_used_skills(code_solution, retrieved_skills)
            val_res["used_skills"] = used_skills
            
            if not self.frozen_memory:
                print(f"[{task_id}] Solution passed! Extracting reusable skills...")
                skills_extracted = skill_manager.extract_and_register_skills(
                    task_id=task_id,
                    task_description=description,
                    code=code_solution
                )
                
        # Include metadata in response
        val_res.update({
            "task_id": task_id,
            "code": code_solution,
            "skills_extracted": skills_extracted,
            "insights_retrieved": [ins["id"] for ins in retrieved_insights],
            "skills_retrieved": [sk["id"] for sk in retrieved_skills],
            "self_correction_attempts": retry_count,
            "self_correction_success": (val_res["status"] == "passed" and retry_count > 0),
            "execution_mode": val_res.get("execution_mode", "unknown"),
        })
        
        return val_res

    def _clean_code_output(self, output: str) -> str:
        clean = output.strip()
        if "```python" in clean:
            clean = clean.split("```python")[1]
            if "```" in clean:
                clean = clean.split("```")[0]
        elif "```" in clean:
            clean = clean.split("```")[1]
            if "```" in clean:
                clean = clean.split("```")[0]
        return clean.strip()
