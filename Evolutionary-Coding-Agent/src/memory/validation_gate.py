import ast
import json
import logging
from pydantic import BaseModel
from src.infra.sandbox import DockerSandbox, rewrite_asserts_for_grading
from src.llm import llm_client
from src.memory.memory_engine import memory_engine

logger = logging.getLogger(__name__)

class FailureAnalysis(BaseModel):
    failure_reason: str
    lesson_learned_insight: str
    importance: float

class JudgeResult(BaseModel):
    score: float
    is_passed: bool
    critique: str
    success_factors: str
    lesson_learned: str

class ValidationGate:
    def __init__(self):
        self.sandbox = DockerSandbox()
        self.llm = llm_client

    def _extract_failure_mode(self, task_id: str, task_description: str, code: str, error_msg: str, failure_type: str) -> dict:
        system_instruction = (
            "You are a Senior Software Quality Analyst. Analyze the failure of a coding agent trying "
            "to solve a task. Determine why it failed and extract a generic, actionable lesson learned (insight) "
            "to prevent this type of failure in the future. Be concise."
        )
        prompt = f"""
Task: {task_description}
Code written by agent:
```python
{code}
```
Failure Type: {failure_type}
Error/Stderr: {error_msg}

Analyze the failure and output a JSON object conforming to FailureAnalysis.
"""
        try:
            res_str = self.llm.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1,
                json_mode=True,
                response_schema=FailureAnalysis
            )
            return json.loads(res_str)
        except Exception as e:
            logger.error(f"Error during failure extraction: {e}")
            return {
                "failure_reason": f"Execution failed: {error_msg}",
                "lesson_learned_insight": "Ensure complete implementation, correct imports, and proper type safety.",
                "importance": 5.0
            }

    def validate_solution(self, task_id: str, task_description: str, code: str, test_code: str, hidden_test_code: str = None) -> dict:
        """
        Post-task processing pipeline:
        1. Syntactic checking via AST.
        2. Run code and test cases in Docker sandbox.
        3. LLM Judge logic check (if code runs successfully).
        4. Save to memories (Interaction, Insight, Skill accordingly).
        """
        # Step 1: Syntactic Check
        try:
            ast.parse(code)
        except SyntaxError as e:
            error_msg = f"Syntax Error: {e.msg} at line {e.lineno}, col {e.offset}\nLine content: {e.text}"
            insight_content = self._extract_failure_mode(task_id, task_description, code, error_msg, "SyntaxError")
            
            memory_engine.add_insight(
                task_id=task_id,
                content=insight_content["lesson_learned_insight"],
                status="failed_tests",
                importance=insight_content["importance"],
                metadata={"failure_reason": insight_content["failure_reason"], "failure_type": "SyntaxError"}
            )
            memory_engine.add_interaction(
                task_id=task_id,
                content=f"Syntax error: {error_msg}",
                status="failed_tests"
            )
            return {
                "status": "failed_tests",
                "score": 0.0,
                "message": f"Syntax error: {error_msg}",
                "insight": insight_content["lesson_learned_insight"],
                "visible_pass_fraction": 0.0,
                "hidden_pass_fraction": 0.0,
                "overfit_gap": 0.0
            }

        # Step 2: Run code in sandbox
        rewritten_test_code = rewrite_asserts_for_grading(test_code)
        full_code = code + "\n\n" + rewritten_test_code
        run_res = self.sandbox.run_code(full_code)
        
        status = run_res["status"]
        stdout = run_res.get("stdout", "")
        stderr = run_res.get("stderr", "")
        execution_mode = run_res.get("execution_mode", "local_subprocess_fallback")
        
        # Check assertions
        passed_count = stdout.count("__ASSERT_PASSED__")
        failed_count = stdout.count("__ASSERT_FAILED__")
        total_count = passed_count + failed_count
        
        visible_pass_fraction = passed_count / total_count if total_count > 0 else (1.0 if status == "success" else 0.0)
        
        if status != "success" or failed_count > 0 or visible_pass_fraction < 1.0:
            error_msg = stderr if stderr else f"Assertions failed: {failed_count} out of {total_count} failed."
            insight_content = self._extract_failure_mode(
                task_id, task_description, code, error_msg, 
                "RuntimeError" if status == "success" else status
            )
            
            memory_engine.add_insight(
                task_id=task_id,
                content=insight_content["lesson_learned_insight"],
                status="failed_tests",
                importance=insight_content["importance"],
                metadata={"failure_reason": insight_content["failure_reason"], "failure_type": status}
            )
            memory_engine.add_interaction(
                task_id=task_id,
                content=f"Unit tests failed.\nError: {error_msg}\nInsight: {insight_content['lesson_learned_insight']}",
                status="failed_tests"
            )
            
            return {
                "status": "failed_tests",
                "score": 0.0,
                "message": f"Unit tests failed. Visible pass fraction: {visible_pass_fraction*100:.1f}% ({passed_count}/{total_count})",
                "insight": insight_content["lesson_learned_insight"],
                "visible_pass_fraction": visible_pass_fraction,
                "hidden_pass_fraction": 0.0,
                "overfit_gap": 0.0,
                "execution_mode": execution_mode
            }

        # Run hidden tests if they exist
        hidden_pass_fraction = 1.0
        if hidden_test_code:
            rewritten_hidden = rewrite_asserts_for_grading(hidden_test_code)
            full_hidden_code = code + "\n\n" + rewritten_hidden
            hidden_run_res = self.sandbox.run_code(full_hidden_code)
            
            hidden_status = hidden_run_res["status"]
            hidden_stdout = hidden_run_res.get("stdout", "")
            hidden_stderr = hidden_run_res.get("stderr", "")
            
            hidden_passed = hidden_stdout.count("__ASSERT_PASSED__")
            hidden_failed = hidden_stdout.count("__ASSERT_FAILED__")
            hidden_total = hidden_passed + hidden_failed
            
            hidden_pass_fraction = hidden_passed / hidden_total if hidden_total > 0 else (1.0 if hidden_status == "success" else 0.0)
            if hidden_status != "success" or hidden_failed > 0:
                hidden_pass_fraction = min(hidden_pass_fraction, 0.0)

        # Step 3: LLM Judge Check
        system_instruction = (
            "Bạn là một giám khảo lập trình (LLM Judge) độc lập. Nhiệm vụ của bạn là đánh giá xem giải pháp code "
            "có thực sự giải quyết được yêu cầu bài toán một cách tổng quát hay không, hay chỉ đơn thuần là cheat "
            "hoặc hardcode kết quả để pass unit test. Trả về kết quả dạng JSON."
        )
        
        prompt = f"""
Yêu cầu bài toán:
{task_description}

Giải pháp của Agent:
```python
{code}
```

Kết quả chạy test case (stdout):
{stdout}

Hãy chấm điểm code này trên thang điểm 10. Nếu code logic tốt, tổng quát và không bị hardcode kết quả, hãy đánh giá là PASSED (is_passed: true, score >= 7.0). Nếu có dấu hiệu cheat/hardcode hoặc lỗi logic nghiêm trọng, hãy đánh giá FAILED (is_passed: false, score < 7.0).
"""
        try:
            res_str = self.llm.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1,
                json_mode=True,
                response_schema=JudgeResult
            )
            judge_data = json.loads(res_str)
            
            is_passed = judge_data.get("is_passed", True)
            score = judge_data.get("score", 8.0)
            critique = judge_data.get("critique", "Tự động duyệt.")
            
        except Exception as e:
            logger.error(f"Error during LLM Judge evaluation: {e}")
            return {
                "status": "failed_judge_error",
                "score": 0.0,
                "message": f"LLM Judge failed: {e}",
                "execution_mode": execution_mode
            }

        if not is_passed:
            insight_content = self._extract_failure_mode(
                task_id, task_description, code, 
                f"LLM Judge critique: {critique}", "FailedLLMJudge"
            )
            
            memory_engine.add_insight(
                task_id=task_id,
                content=insight_content["lesson_learned_insight"],
                status="failed_judge",
                importance=insight_content["importance"],
                metadata={"failure_reason": insight_content["failure_reason"], "failure_type": "FailedLLMJudge"}
            )
            memory_engine.add_interaction(
                task_id=task_id,
                content=f"LLM Judge failed: {critique}\nInsight: {insight_content['lesson_learned_insight']}",
                status="failed_judge"
            )
            
            return {
                "status": "failed_judge",
                "score": score,
                "message": f"LLM Judge rejected: {critique}",
                "insight": insight_content["lesson_learned_insight"],
                "visible_pass_fraction": visible_pass_fraction,
                "hidden_pass_fraction": hidden_pass_fraction,
                "overfit_gap": visible_pass_fraction - hidden_pass_fraction,
                "execution_mode": execution_mode
            }

        # Success path!
        success_factors = judge_data.get("success_factors", "")
        lesson_learned = judge_data.get("lesson_learned", "")
        insight_content = f"Đối với nhiệm vụ: '{task_description}'. Giải pháp thành công cần đáp ứng: {success_factors}. Bài học rút ra: {lesson_learned}"
        
        memory_engine.add_insight(
            task_id=task_id,
            content=insight_content,
            status="passed",
            importance=7.0,
            metadata={}
        )
        memory_engine.add_interaction(
            task_id=task_id,
            content=f"Passed task validation.\nScore: {score}\nCritique: {critique}",
            status="passed"
        )
        
        return {
            "status": "passed",
            "score": score,
            "message": critique,
            "insight": insight_content,
            "visible_pass_fraction": visible_pass_fraction,
            "hidden_pass_fraction": hidden_pass_fraction,
            "overfit_gap": visible_pass_fraction - hidden_pass_fraction,
            "execution_mode": execution_mode
        }

# Global Validation Gate instance
validation_gate = ValidationGate()
