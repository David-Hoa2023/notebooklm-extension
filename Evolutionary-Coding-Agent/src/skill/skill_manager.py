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
                    "domain": {"type": "STRING"},
                    "dependencies": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["name", "code", "docstring", "dependencies", "domain"]
            }
        }
    },
    "required": ["skills"]
}

KNOWN_IMPORTS = {
    "List": "from typing import List",
    "Dict": "from typing import Dict",
    "Tuple": "from typing import Tuple",
    "Set": "from typing import Set",
    "Optional": "from typing import Optional",
    "Union": "from typing import Union",
    "Any": "from typing import Any",
    "Callable": "from typing import Callable",
    "Iterable": "from typing import Iterable",
    "Sequence": "from typing import Sequence",
    "Mapping": "from typing import Mapping",
    "re": "import re",
    "json": "import json",
    "math": "import math",
    "datetime": "import datetime",
    "time": "import time",
    "sys": "import sys",
    "os": "import os",
    "collections": "import collections",
    "defaultdict": "from collections import defaultdict",
    "deque": "from collections import deque",
    "Counter": "from collections import Counter",
}

def auto_prepend_imports(code: str) -> str:
    try:
        tree = ast.parse(code)
    except Exception:
        return code

    existing_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                existing_imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    existing_imports.add(alias.name)
                    existing_imports.add(f"{node.module}.{alias.name}")

    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)
                used_names.add(f"{node.value.id}.{node.attr}")
        elif isinstance(node, ast.arg) and node.annotation:
            for subnode in ast.walk(node.annotation):
                if isinstance(subnode, ast.Name):
                    used_names.add(subnode.id)
        elif isinstance(node, ast.FunctionDef) and node.returns:
            for subnode in ast.walk(node.returns):
                if isinstance(subnode, ast.Name):
                    used_names.add(subnode.id)

    imports_to_add = []
    typing_names = []
    other_imports = []
    for name in sorted(used_names):
        if name in KNOWN_IMPORTS:
            if name in existing_imports or f"typing.{name}" in existing_imports or f"collections.{name}" in existing_imports:
                continue
            imp_stmt = KNOWN_IMPORTS[name]
            if "typing" in imp_stmt:
                typing_names.append(name)
            else:
                other_imports.append(imp_stmt)

    if typing_names:
        imports_to_add.append(f"from typing import {', '.join(sorted(list(set(typing_names))))}")
    for imp in sorted(list(set(other_imports))):
        imports_to_add.append(imp)

    if imports_to_add:
        code = "\n".join(imports_to_add) + "\n\n" + code
    return code


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
5. Xác định domain (lĩnh vực) phù hợp cho hàm này (chọn một trong: regex, smtp, json, math, datetime, string_parsing, file_io, algorithms, data_structures, error_handling, testing, hoặc generic).
   Chú ý: Khi định nghĩa kiểu dữ liệu (Type Hints), hãy sử dụng kiểu chữ thường (ví dụ: list, dict) hoặc import đầy đủ từ thư viện `typing` (ví dụ: List, Dict, Optional) nếu cần thiết.
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
                domain = sk.get("domain", "generic").lower().strip()
                deps = sk.get("dependencies", [])
                
                if not name or not code_content:
                    continue
                
                # 1. Clean code content formatting: unescape \n
                code_content = code_content.replace('\\n', '\n')
                
                # 2. Verify initial AST syntax validity
                try:
                    ast.parse(code_content)
                except Exception as parse_err:
                    print(f"Skipping skill candidate '{name}' due to AST parsing error: {parse_err}")
                    continue
                
                # 3. Auto-prepend required standard library & typing imports
                code_content = auto_prepend_imports(code_content)
                
                # 4. Verify AST validity again after prepending
                try:
                    ast.parse(code_content)
                except Exception as parse_err:
                    print(f"Skipping skill candidate '{name}' after auto-prepend imports: {parse_err}")
                    continue
                    
                print(f"Extracted Skill candidate: '{name}' (domain: '{domain}') from task '{task_id}'. Running verification...")
                
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
                
                # Register in database with version, domain tag, and source task provenance
                metadata = {
                    "name": name,
                    "docstring": docstring,
                    "domain": domain,
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
