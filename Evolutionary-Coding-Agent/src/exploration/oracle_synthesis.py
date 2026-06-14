import json
from google.genai import types
from src.infra.sandbox import DockerSandbox, rewrite_asserts_for_grading
from src.llm import llm_client
from src.exploration.models import OracleBundle, ProposedTask


from pydantic import BaseModel

class OracleSchema(BaseModel):
    test_code: str
    hidden_test_code: str = ""


KNOWN_BAD_STUB = '''
def _intentionally_wrong_solution():
    """Stub that should fail synthesized tests."""
    return None
'''


class OracleSynthesizer:
    def __init__(self):
        self.llm = llm_client
        self.sandbox = DockerSandbox()

    def _clean_json_response(self, text: str) -> str:
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean.split("```json")[1]
            if "```" in clean:
                clean = clean.split("```")[0]
        elif clean.startswith("```"):
            clean = clean.split("```")[1]
            if "```" in clean:
                clean = clean.split("```")[0]
        return clean.strip()

    def _escape_unescaped_newlines(self, json_str: str) -> str:
        result = []
        in_string = False
        escaped = False
        for char in json_str:
            if char == '"' and not escaped:
                in_string = not in_string
                result.append(char)
            elif char == '\\' and in_string:
                escaped = not escaped
                result.append(char)
            elif char == '\n':
                if in_string:
                    result.append('\\n')
                else:
                    result.append(char)
                escaped = False
            else:
                result.append(char)
                escaped = False
        return "".join(result)

    def synthesize(self, task: ProposedTask) -> OracleBundle:
        system_instruction = (
            "You write executable Python unit tests for a coding task. "
            "Use assert-based test functions or standard unittest TestCase classes that call the functions described in the task. "
            "Do NOT import or use 'pytest' or any third-party libraries. Only use standard library assert statements or the built-in unittest module. "
            "Return JSON with test_code (visible) and optional hidden_test_code. "
            "IMPORTANT: All code within test_code and hidden_test_code must be correctly escaped, "
            "and literal newlines inside string values must be escaped as \\n."
        )
        prompt = f"""
        Task title: {task.title}
        Task description:
        {task.description}

        Write visible tests (test_code) and harder hidden tests (hidden_test_code).
        Tests must reference function names from the task description.
        Do not include the solution implementation.
        """
        res_str = self.llm.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.1,
            json_mode=True,
            response_schema=OracleSchema,
        )
        cleaned_str = self._clean_json_response(res_str)
        fixed_str = self._escape_unescaped_newlines(cleaned_str)
        try:
            data = json.loads(fixed_str)
        except json.JSONDecodeError as e:
            print(f"Error parsing oracle JSON: {e}. Raw response: {res_str}")
            data = {"test_code": "", "hidden_test_code": ""}
                
        bundle = OracleBundle(
            test_code=data.get("test_code", ""),
            hidden_test_code=data.get("hidden_test_code", ""),
        )
        bundle.validation_passed, bundle.rejection_reason = self._validate_oracle(
            task.description,
            bundle.test_code,
            bundle.hidden_test_code,
        )
        return bundle

    def _extract_function_names(self, description: str) -> list[str]:
        import re
        # Match backticked words that look like identifiers (with optional parameters inside backticks)
        backticked = re.findall(r'`([a-zA-Z_][a-zA-Z0-9_]*)(?:\(.*?\))?`', description)
        # Match def function_name
        defs = re.findall(r'\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)', description)
        # Match function_name() style calls
        refs = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\(\)', description)
        
        candidates = set(backticked + defs + refs)
        banned = {'def', 'class', 'import', 'from', 'dict', 'list', 'str', 'int', 'float', 'bool', 'set', 'tuple', 'any', 'None', 'ValueError', 'TypeError', 'KeyError', 'Exception', 'return', 'if', 'else', 'for', 'while', 'in', 'and', 'or', 'not', 'is', 'lambda'}
        return sorted([c for c in candidates if c not in banned])

    def _validate_oracle(self, description: str, test_code: str, hidden_test_code: str) -> tuple[bool, str]:
        if not test_code.strip():
            return False, "empty test_code"

        # Static pytest rejection
        if "pytest" in test_code or "pytest" in hidden_test_code:
            return False, "oracle imports or uses pytest"

        # Exact function name presence enforcement
        expected_names = self._extract_function_names(description)
        if expected_names:
            for name in expected_names:
                if name not in test_code:
                    return False, f"oracle test_code does not reference expected function: {name}"

        rewritten = rewrite_asserts_for_grading(test_code)
        bad_code = f"{KNOWN_BAD_STUB}\n\n# --- Synthesized Tests ---\n{rewritten}"
        bad_res = self.sandbox.run_code(bad_code)

        if bad_res["status"] == "syntax_error":
            return False, f"syntax error in test_code: {bad_res.get('stderr', '').strip()}"

        if bad_res["status"] == "runtime_error":
            stderr = bad_res.get("stderr", "")
            if "ModuleNotFoundError" in stderr or "ImportError" in stderr or "pytest" in stderr:
                return False, f"oracle runtime error: {stderr.strip()}"

        if bad_res["status"] == "success":
            stdout = bad_res.get("stdout", "")
            failed = stdout.count("__ASSERT_FAILED__")
            passed = stdout.count("__ASSERT_PASSED__")
            if failed == 0 and passed > 0:
                return False, "oracle accepts known-bad solution"

        if hidden_test_code.strip():
            rewritten_hidden = rewrite_asserts_for_grading(hidden_test_code)
            hidden_bad = f"{KNOWN_BAD_STUB}\n\n# --- Hidden Tests ---\n{rewritten_hidden}"
            hidden_res = self.sandbox.run_code(hidden_bad)
            if hidden_res["status"] == "syntax_error":
                return False, f"syntax error in hidden_test_code: {hidden_res.get('stderr', '').strip()}"
            if hidden_res["status"] == "runtime_error":
                h_stderr = hidden_res.get("stderr", "")
                if "ModuleNotFoundError" in h_stderr or "ImportError" in h_stderr or "pytest" in h_stderr:
                    return False, f"hidden oracle runtime error: {h_stderr.strip()}"
            if hidden_res["status"] == "success":
                h_stdout = hidden_res.get("stdout", "")
                if h_stdout.count("__ASSERT_FAILED__") == 0 and h_stdout.count("__ASSERT_PASSED__") > 0:
                    return False, "hidden oracle accepts known-bad solution"

        return True, ""

    def to_task_dict(self, proposed: ProposedTask, oracle: OracleBundle) -> dict:
        return {
            "id": proposed.id,
            "title": proposed.title,
            "description": proposed.description,
            "difficulty": proposed.difficulty,
            "dependencies": [],
            "is_held_out": False,
            "test_code": oracle.test_code,
            "hidden_test_code": oracle.hidden_test_code,
            "is_self_proposed": True,
            "target_skills": proposed.target_skills,
            "rationale": proposed.rationale,
        }


oracle_synthesizer = OracleSynthesizer()
