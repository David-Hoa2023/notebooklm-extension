import json
import ast
from google.genai import types
from src.llm import llm_client
from src.memory.memory_engine import memory_engine
from src.skill.skill_tester import skill_tester_instance
from src.config import config_instance


# Native Gemini Schema definition for Skill list to avoid Pydantic $defs/$ref nested schema errors and SDK dict attribute errors
SKILL_LIST_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "skills": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "code": {"type": "STRING"},
                    "docstring": {"type": "STRING"},
                    "dependencies": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["name", "code", "docstring", "dependencies"]
            }
        }
    },
    "required": ["skills"]
}

class SkillManager:
    def __init__(self):
        self.llm = llm_client

    def extract_and_register_skills(self, task_id: str, task_description: str, code: str) -> list[str]:
        """
        Takes successfully verified code, extracts modular helper functions/skills,
        and runs tests on them before inserting them into the 'skill' memory.
        """
        system_instruction = (
            "Bạn là một kiến trúc sư phần mềm chuyên môn hóa việc tái cấu trúc code. "
            "Nhiệm vụ của bạn là phân tách các đoạn code lớn thành các hàm (function) nhỏ hơn, "
            "độc lập, có tính tái sử dụng cao (utility helper). Trả về kết quả dạng JSON."
        )
        
        prompt = f"""
Nhiệm vụ lập trình gốc:
{task_description}

Giải pháp code hoàn chỉnh đã pass test:
```python
{code}
```

Hãy trích xuất tất cả các hàm helper cốt lõi, độc lập và có tính tái sử dụng cao trong tương lai từ giải pháp trên.
Mỗi hàm helper trích xuất cần phải:
1. Độc lập hoàn toàn hoặc chỉ phụ thuộc vào thư viện chuẩn/thư viện đã có.
2. Có kiểu dữ liệu đầu vào, đầu ra rõ ràng (Type Hints).
3. Có docstring mô tả chi tiết chức năng, tham số và giá trị trả về bằng tiếng Anh/Việt.
4. KHÔNG bao gồm code test hoặc code chạy thử ở mức toàn cục.
"""
        extracted_ids = []
        try:
            res_str = self.llm.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.1,
                json_mode=True,
                response_schema=SKILL_LIST_SCHEMA
            )
            data = json.loads(res_str)
            skills = data.get("skills", [])
            
            for sk in skills:
                name = sk.get("name")
                code_content = sk.get("code")
                docstring = sk.get("docstring", "")
                deps = sk.get("dependencies", [])
                
                if not name or not code_content:
                    continue
                    
                print(f"Extracted Skill candidate: '{name}' from task '{task_id}'. Running verification...")
                
                # Step 2: Test & Verify Skill (SKILL_002)
                # We call skill_tester to auto-generate tests and verify inside sandbox
                is_verified, generated_tests = skill_tester_instance.verify_skill(name, code_content, docstring)
                
                # Trace AST dependencies on existing active skills
                from src.skill.skill_composition import skill_composition_instance
                active_skills = skill_composition_instance.get_active_skills()
                active_names = {s.get("metadata", {}).get("name") for s in active_skills}
                
                ast_deps = []
                try:
                    tree = ast.parse(code_content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                            if node.func.id in active_names and node.func.id != name:
                                ast_deps.append(node.func.id)
                except Exception:
                    pass
                    
                combined_deps = list(set(deps + ast_deps))
                
                # Register in database with version and source task provenance
                metadata = {
                    "name": name,
                    "docstring": docstring,
                    "dependencies": combined_deps,
                    "retrievable": is_verified, # Only retrieve if verified
                    "generated_tests": generated_tests,
                    "version": config_instance.get("project.version", "1.0.0"),
                    "source_tasks": [task_id]
                }
                
                # Save to skill namespace
                sk_id = memory_engine.add_skill(
                    task_id=task_id,
                    content=code_content,
                    importance=8.0 if is_verified else 4.0,
                    metadata=metadata
                )
                
                if is_verified:
                    print(f"Skill '{name}' verified successfully and added as ACTIVE skill '{sk_id}'.")
                else:
                    print(f"Skill '{name}' FAILED verification. Added as INACTIVE.")
                    
                extracted_ids.append(sk_id)
                
            return extracted_ids
            
        except Exception as e:
            print(f"Error extracting skills: {e}")
            return []

# Global skill manager instance
skill_manager = SkillManager()
