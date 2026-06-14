import ast
from src.memory.memory_engine import memory_engine

class SkillCompositionManager:
    def __init__(self):
        pass

    def get_active_skills(self) -> list[dict]:
        """
        Retrieve all skills that are verified and active (retrievable = True).
        """
        all_skills = memory_engine.get_all_memories(namespace="skill")
        active_skills = []
        for sk in all_skills:
            metadata = sk.get("metadata", {})
            if metadata.get("retrievable", False):
                active_skills.append(sk)
        return active_skills

    def format_skills_for_prompt(self, skills: list[dict]) -> str:
        """
        Formats a list of skills into a structured text context block for LLM prompts.
        """
        if not skills:
            return "Không có Skill nào phù hợp trong kho lưu trữ."
            
        formatted_list = []
        for i, sk in enumerate(skills, 1):
            metadata = sk.get("metadata", {})
            name = metadata.get("name", "Unnamed Skill")
            docstring = metadata.get("docstring", "")
            code = sk["content"]
            
            block = f"""[Skill #{i}]
Tên hàm: `{name}`
Mục đích: {docstring}
Đoạn code:
```python
{code}
```"""
            formatted_list.append(block)
            
        return "\n\n".join(formatted_list)

    def trace_used_skills(self, code: str, active_skills: list[dict]) -> list[str]:
        """
        Analyze code using AST to find which active skills were called.
        """
        try:
            tree = ast.parse(code)
        except Exception:
            return []
            
        called_functions = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_functions.add(node.func.id)
                    
        used_skill_names = []
        for sk in active_skills:
            name = sk.get("metadata", {}).get("name")
            if name in called_functions:
                used_skill_names.append(name)
                
        return used_skill_names

    def resolve_dependencies(self, retrieved_skills: list[dict]) -> list[dict]:
        """
        Recursively fetches dependencies of retrieved skills to construct composed skill bundles.
        Ensures correct definition order (topological order).
        """
        all_skills = memory_engine.get_all_memories(namespace="skill")
        name_to_skill = {}
        for sk in all_skills:
            name = sk.get("metadata", {}).get("name")
            if name:
                name_to_skill[name] = sk
                
        resolved = []
        visited = set()
        
        def dfs(sk):
            name = sk.get("metadata", {}).get("name")
            if not name or name in visited:
                return
            visited.add(name)
            
            # Fetch dependencies first (post-order traversal for correct ordering)
            deps = sk.get("metadata", {}).get("dependencies", [])
            for dep_name in deps:
                if dep_name in name_to_skill:
                    dfs(name_to_skill[dep_name])
                    
            resolved.append(sk)
            
        for sk in retrieved_skills:
            dfs(sk)
            
        return resolved

# Global instance
skill_composition_instance = SkillCompositionManager()

