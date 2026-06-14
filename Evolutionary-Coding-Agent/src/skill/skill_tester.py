import json
from src.infra.sandbox import DockerSandbox
from src.llm import llm_client

class SkillTester:
    def __init__(self):
        # Instantiate sandbox locally to avoid circular dependencies
        self.sandbox = DockerSandbox()
        self.llm = llm_client

    def verify_skill(self, name: str, code: str, docstring: str) -> tuple[bool, str]:
        """
        Generate unit tests for a skill, execute them in Docker,
        and return if it passes along with the test code.
        """
        system_instruction = (
            "Bạn là kỹ sư kiểm thử phần mềm (QA Automation). Nhiệm vụ của bạn là viết "
            "các unit test case ngắn gọn nhưng đầy đủ (bao gồm cả các edge cases) cho một hàm Python cụ thể. "
            "Các test case được thiết kế để chạy trực tiếp (sử dụng assert thuần, không cần pytest)."
        )
        
        prompt = f"""
Đoạn code của hàm helper:
```python
{code}
```

Mô tả docstring:
{docstring}

Hãy viết một hàm test có tên `test_{name}()` chứa ít nhất 3 assert test cases để kiểm tra tính đúng đắn của hàm trên.
Hàm test này không nhận tham số đầu vào. Kết thúc file bằng việc gọi trực tiếp hàm test đó: `test_{name}()`.
Chú ý:
- Chỉ trả về đoạn code test thuần, không kèm chú thích markdown hay markdown block.
- Sử dụng câu lệnh `assert` thuần của Python.
- Đảm bảo nhập (import) các thư viện cần thiết nếu hàm helper của bạn sử dụng chúng.

Ví dụ định dạng đầu ra:
def test_add_numbers():
    assert add_numbers(1, 2) == 3
    assert add_numbers(-1, 1) == 0
test_add_numbers()
"""
        try:
            # Generate test code
            # We want plain text from the LLM, so json_mode=False
            test_code = self.llm.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1
            )
            
            # Clean up the output in case LLM returns markdown blocks
            clean_test_code = test_code.strip()
            if clean_test_code.startswith("```python"):
                clean_test_code = clean_test_code.split("```python")[1]
            if clean_test_code.endswith("```"):
                clean_test_code = clean_test_code.rsplit("```", 1)[0]
            clean_test_code = clean_test_code.strip()
            
            # Combine skill code with generated test code
            full_test_runner_code = f"{code}\n\n# --- Auto-generated Tests ---\n{clean_test_code}"
            
            # Run in sandbox
            res = self.sandbox.run_code(full_test_runner_code)
            
            is_passed = (res["status"] == "success" and res["exit_code"] == 0)
            
            if not is_passed:
                print(f"Skill '{name}' verification failed. Sandbox status: {res['status']}. Stderr: {res['stderr']}")
                
            return is_passed, clean_test_code
            
        except Exception as e:
            print(f"Error verifying skill '{name}': {e}")
            return False, ""

# Global instance
skill_tester_instance = SkillTester()
