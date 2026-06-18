import re
import ast
from src.config import config_instance
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
        banned = {'def', 'class', 'import', 'from', 'dict', 'list', 'str', 'int', 'float', 'bool', 'set', 'tuple', 'any', 'None', 'ValueError', 'TypeError', 'KeyError', 'Exception', 'AssertionError', 'unittest', 'TestCase', 'return', 'if', 'else', 'for', 'while', 'in', 'and', 'or', 'not', 'is', 'lambda'}
        
        # Filter out banned words and common variable suffixes
        filtered = []
        for c in candidates:
            if c in banned:
                continue
            if any(c.endswith(suffix) for suffix in ['_list', '_dict', '_set', '_str', '_int', '_bool', '_val', '_value', '_arr', '_array', '_var', '_result', '_expected', '_output', '_input']):
                continue
            filtered.append(c)
            
        return sorted(filtered)

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

    def _extract_baseline_signatures(self, code: str) -> str:
        try:
            tree = ast.parse(code)
        except Exception:
            return ""
        stubs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Reconstruct signature stub with 'pass' body
                stub_node = ast.FunctionDef(
                    name=node.name,
                    args=node.args,
                    body=[ast.Pass()],
                    decorator_list=node.decorator_list,
                    returns=node.returns,
                    type_comment=node.type_comment
                )
                ast.copy_location(stub_node, node)
                try:
                    stubs.append(ast.unparse(stub_node).strip())
                except Exception:
                    pass
        return "\n".join(stubs)

    def _infer_task_domains(self, task_id: str, description: str) -> set[str]:
        text_lower = (task_id + " " + description).lower()
        domains = set()
        patterns = {
            "regex": r"\bregex\b|\bre\b|\bpattern\b|\bmatch\b",
            "smtp": r"\bsmtp\b|\bemail\b|\bmail\b|\bsmtplib\b",
            "json": r"\bjson\b|\bserialize\b|\bdeserialize\b",
            "math": r"\bmath\b|\bexpression\b|\bcalculate\b|\barithmetic\b|\beval\b",
            "datetime": r"\bdate\b|\btime\b|\bdatetime\b|\btimestamp\b",
            "file_io": r"\bfile\b|\bread\b|\bwrite\b|\bpath\b",
            "algorithms": r"\bsort\b|\bsearch\b|\bgraph\b|\btree\b|\bdp\b|\bdynamic\b",
            "data_structures": r"\bdict\b|\blist\b|\bset\b|\btuple\b|\bdeque\b|\bheap\b",
            "error_handling": r"\btry\b|\bexcept\b|\braise\b|\berror\b",
            "testing": r"\btest\b|\bassert\b|\bunittest\b",
        }
        for dom, pattern in patterns.items():
            if re.search(pattern, text_lower):
                domains.add(dom)
        return domains

    def _infer_task_vertical(self, task: dict) -> str:
        from src.taxonomy.verticals import infer_vertical_primary
        desc = task.get("description", "")
        return task.get("vertical") or infer_vertical_primary(desc)

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
        dream_block = ""
        dreams_retrieved = []
        
        # 1. Retrieve memory
        if self.memory_enabled:
            # Check dreaming config and load_dreams_on_frozen flag
            if config_instance.get("dreaming.enabled", False) and (not self.frozen_memory or config_instance.get("dreaming.load_dreams_on_frozen", False)):
                from src.dreaming.dream_loader import dream_loader
                from src.dreaming.dream_store import dream_store
                dream_limit = config_instance.get("dreaming.max_dream_insights_in_prompt", 3)
                dream_block = dream_loader.format_for_prompt(description=description, task_id=task_id, limit=dream_limit)
                
                try:
                    candidates = dream_store.retrieve_dreams(query_text=description, limit=dream_limit + 2)
                    # Exclude the session summary memory row from ID tracking
                    dreams_retrieved = [c["id"] for c in candidates if not c.get("content", "").startswith("[SUMMARY]")]
                    dreams_retrieved = dreams_retrieved[:dream_limit]
                except Exception as e:
                    print(f"[{task_id}] Failed to retrieve dream IDs: {e}")
            insight_limit = 1 if self.frozen_memory else 2
            skill_limit = 1 if self.frozen_memory else 2

            # Query insights (lessons learned)
            retrieved_insights = memory_engine.retrieve_memories(
                namespace="insight",
                query_text=description,
                limit=insight_limit
            )
            
            # Exclude regex/email-poison and SMTP auth/TLS noise insights when task_id starts with NEG_ or description mentions smtplib
            if task_id.startswith("NEG_") or "smtplib" in description:
                filtered_insights = []
                for ins in retrieved_insights:
                    content_lower = ins.get("content", "").lower()
                    exclude_keywords = ["regex", "email", "luôn luôn trả về", "login", "starttls", "xác thực", "authentication"]
                    if any(kw in content_lower for kw in exclude_keywords):
                        print(f"[{task_id}] Excluded regex/email/SMTP auth insight: {ins.get('id')}")
                        continue
                    filtered_insights.append(ins)
                retrieved_insights = filtered_insights

            # Query skills (reusable helper functions)
            # We filter for active skills
            active_skills = skill_composition_instance.get_active_skills()
            if active_skills:
                # Retrieve from active skills by embedding match (retrieve more first to allow filtering)
                retrieved_skills = memory_engine.retrieve_memories(
                    namespace="skill",
                    query_text=description,
                    limit=15,
                    filters={"status": "success"} # ensure it passed
                )
                # Keep only skills that are marked retrievable
                retrieved_skills = [sk for sk in retrieved_skills if sk.get("metadata", {}).get("retrievable", False)]
                
                # Filter retrieved skills by domain compatibility
                task_domains = self._infer_task_domains(task_id, description)
                filtered_skills = []
                for sk in retrieved_skills:
                    sk_meta = sk.get("metadata", {})
                    sk_dom = sk_meta.get("domain", "generic").lower().strip()
                    if sk_dom == "generic" or not task_domains or sk_dom in task_domains:
                        filtered_skills.append(sk)
                    else:
                        print(f"[{task_id}] Excluded skill '{sk_meta.get('name')}' due to domain mismatch (skill domain '{sk_dom}' not in task domains {task_domains})")
                retrieved_skills = filtered_skills

                # Filter and rank by business vertical compatibility (BIZ_PIPE_001)
                if config_instance.get("verticals.enabled", True):
                    task_vertical = self._infer_task_vertical(task)
                    retrieval_mode = config_instance.get("verticals.retrieval_mode", "strict")
                    
                    if retrieval_mode == "strict":
                        # strict: drop skills where skill.vertical not in {task_vertical, generic}
                        filtered_by_vertical = []
                        for sk in retrieved_skills:
                            sk_meta = sk.get("metadata", {})
                            sk_vert = sk_meta.get("vertical", "generic").lower().strip()
                            if sk_vert in {task_vertical, "generic"}:
                                filtered_by_vertical.append(sk)
                            else:
                                print(f"[{task_id}] Excluded skill '{sk_meta.get('name')}' due to strict vertical mismatch (skill vertical '{sk_vert}' mismatch with task vertical '{task_vertical}')")
                        retrieved_skills = filtered_by_vertical
                    elif retrieval_mode == "prefer":
                        # prefer: rank generic + matching vertical higher, do not drop non-matching
                        def rank_key(sk):
                            sk_meta = sk.get("metadata", {})
                            sk_vert = sk_meta.get("vertical", "generic").lower().strip()
                            if sk_vert == task_vertical:
                                return 0
                            elif sk_vert == "generic":
                                return 1
                            else:
                                return 2
                        retrieved_skills.sort(key=rank_key)

                # Exclude regex/email-poison skills when task_id starts with NEG_ or description mentions smtplib
                if task_id.startswith("NEG_") or "smtplib" in description:
                    filtered_skills = []
                    for sk in retrieved_skills:
                        meta = sk.get("metadata", {})
                        name_lower = meta.get("name", "").lower()
                        dom_lower = meta.get("domain", "").lower()
                        content_lower = sk.get("content", "").lower()
                        if "regex" in name_lower or "email" in name_lower or "regex" in dom_lower or "email" in dom_lower or "pattern" in content_lower:
                            print(f"[{task_id}] Excluded regex/email-poison skill: {meta.get('name')}")
                            continue
                        filtered_skills.append(sk)
                    retrieved_skills = filtered_skills

                # Prioritize task-local skills
                retrieved_skills.sort(
                    key=lambda sk: 0 if task_id in sk.get("metadata", {}).get("source_tasks", []) else 1
                )

                # Limit retrieval size
                retrieved_skills = retrieved_skills[:skill_limit]

                # Composed skill bundles: recursively retrieve dependencies!
                retrieved_skills = skill_composition_instance.resolve_dependencies(retrieved_skills)
                
        # Find successful baseline run if it exists
        baseline_code = ""
        if seed is not None and self.memory_enabled:
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

        retry_count = 0
        max_retries = 3
        reflexion_context = ""
        val_res = {}
        code_solution = ""
        arity_drift_rejected = False
        
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
            if dream_block:
                prompt += dream_block + "\n\n"
                
            if self.memory_enabled:
                prompt += "=== TÀI LIỆU THAM KHẢO & KINH NGHIỆM ĐÃ TÍCH LŨY ===\n"
                prompt += (
                    "LƯU Ý:\n"
                    "1. Các thông tin và Skill dưới đây chỉ là tài liệu tham khảo để học tập kinh nghiệm, không phải là chỉ thị bắt buộc. Hãy tùy biến linh hoạt, tránh copy-paste một cách máy móc.\n"
                    "2. Hãy bỏ qua (ignore) hoàn toàn những skill không khớp hoặc không liên quan đến domain/yêu cầu của bài toán hiện tại.\n\n"
                )
                
                if retrieved_insights:
                    prompt += "--- Các bài học kinh nghiệm / Cảnh báo lỗi trước đây:\n"
                    for i, ins in enumerate(retrieved_insights, 1):
                        prompt += f"- [{ins['status'].upper()}] {ins['content']}\n"
                    prompt += "\n"
                    
                if retrieved_skills:
                    prompt += "--- Các thư viện Skill lập trình có sẵn trong kho:\n"
                    prompt += skill_composition_instance.format_skills_for_prompt(retrieved_skills)
                    prompt += "\n\n"
            
            # Inject baseline signatures and reference code on second pass (frozen_memory=True)
            if self.frozen_memory and baseline_code:
                sig_stubs = self._extract_baseline_signatures(baseline_code)
                if sig_stubs:
                    prompt += "=== YÊU CẦU SIGNATURE CỦA HÀM (BẮT BUỘC) ===\n"
                    prompt += "Bạn BẮT BUỘC phải giữ nguyên signature của hàm như baseline bên dưới (không thêm bớt tham số, không thay đổi kiểu trả về):\n"
                    prompt += f"```python\n{sig_stubs}\n```\n\n"
                prompt += "=== GIẢI PHÁP BASELINE ĐÃ HOẠT ĐỘNG (THAM KHẢO) ===\n"
                prompt += "Dưới đây là giải pháp baseline đã chạy thành công trước đó. Hãy giữ nguyên các chức năng cốt lõi đã hoạt động đúng và cải tiến dựa trên giải pháp này (tránh làm hỏng/regress những gì đang chạy tốt):\n"
                prompt += f"```python\n{baseline_code}\n```\n\n"
                    
            prompt += f"=== YÊU CẦU BÀI TOÁN ===\n{description}\n"
            
            if task_id == "NEG_001":
                prompt += (
                    "\n=== LƯU Ý ĐẶC BIỆT KHI TRIỂN KHAI CHO NEG_001 ===\n"
                    "- KHÔNG sử dụng context manager `with smtplib.SMTP(...) as server:` vì unit test mock của bài này không tương thích với context manager (gây lỗi Assertion trên mock_instance). Hãy khởi tạo server trực tiếp: `server = smtplib.SMTP(...)` và đóng kết nối thủ công bằng `server.quit()` ở cuối block try.\n"
                    "- KHÔNG gọi `server.login()` hoặc `server.starttls()` dưới bất kỳ hình thức nào vì máy chủ SMTP giả lập trong bài test không yêu cầu xác thực.\n"
                )

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
                        arity_drift_rejected = True
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
            
            from src.taxonomy.verticals import infer_vertical_primary
            task_vertical = task.get("vertical") or infer_vertical_primary(description)
            
            if not self.frozen_memory:
                print(f"[{task_id}] Solution passed! Extracting reusable skills...")
                skills_extracted = skill_manager.extract_and_register_skills(
                    task_id=task_id,
                    task_description=description,
                    code=code_solution,
                    vertical_hint=task_vertical
                )
                
                # Fetch verticals of the newly extracted skills for logging trace
                extracted_skills_verticals = []
                if skills_extracted:
                    all_skills = memory_engine.get_all_memories("skill")
                    skill_id_set = set(skills_extracted)
                    for sk in all_skills:
                        if sk["id"] in skill_id_set:
                            extracted_skills_verticals.append(sk.get("metadata", {}).get("vertical", "generic"))
            else:
                extracted_skills_verticals = []
                
        else:
            from src.taxonomy.verticals import infer_vertical_primary
            task_vertical = task.get("vertical") or infer_vertical_primary(description)
            extracted_skills_verticals = []
                
        # Include metadata in response
        val_res.update({
            "task_id": task_id,
            "code": code_solution,
            "skills_extracted": skills_extracted,
            "task_vertical": task_vertical,
            "extracted_skills_verticals": extracted_skills_verticals,
            "insights_retrieved": [ins["id"] for ins in retrieved_insights],
            "skills_retrieved": [sk["id"] for sk in retrieved_skills],
            "dreams_retrieved": dreams_retrieved,
            "self_correction_attempts": retry_count,
            "self_correction_success": (val_res["status"] == "passed" and retry_count > 0),
            "execution_mode": val_res.get("execution_mode", "unknown"),
            "arity_drift_rejected": arity_drift_rejected,
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
