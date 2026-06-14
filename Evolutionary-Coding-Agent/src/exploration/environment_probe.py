import json
from google.genai import types
from src.infra.sandbox import DockerSandbox
from src.llm import llm_client
from src.memory.memory_engine import memory_engine
from src.exploration.models import ProbeAction, ProbeResult


PROBE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "probes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "purpose": {"type": "STRING"},
                    "code": {"type": "STRING"},
                },
                "required": ["purpose", "code"],
            },
        }
    },
    "required": ["probes"],
}


class EnvironmentProber:
    def __init__(self):
        self.llm = llm_client
        self.sandbox = DockerSandbox()

    def should_probe(self, retrieved_insights: list[dict], is_self_proposed: bool) -> bool:
        if is_self_proposed:
            return True
        if len(retrieved_insights) < 1:
            return True
        low_confidence = all(ins.get("score", 1.0) < 0.5 for ins in retrieved_insights if "score" in ins)
        return low_confidence

    def generate_probes(self, task_description: str, max_probes: int = 2) -> list[ProbeAction]:
        system_instruction = (
            "You generate short diagnostic Python snippets to gather facts before solving a task. "
            "Each probe must be standalone, use only stdlib, print observations, and avoid solving the task. "
            "Return JSON only."
        )
        prompt = f"""
Task (not yet solved):
{task_description}

Generate up to {max_probes} small diagnostic scripts that help understand constraints, edge cases, or library behavior.
Do NOT implement the full solution.
"""
        res_str = self.llm.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.2,
            json_mode=True,
            response_schema=PROBE_SCHEMA,
        )
        data = json.loads(res_str)
        probes = []
        for item in data.get("probes", [])[:max_probes]:
            probes.append(ProbeAction(purpose=item["purpose"], code=item["code"]))
        return probes

    def run_probes(self, task_id: str, probes: list[ProbeAction]) -> list[ProbeResult]:
        results = []
        for probe in probes:
            sandbox_res = self.sandbox.run_code(probe.code)
            result = ProbeResult(
                purpose=probe.purpose,
                code=probe.code,
                stdout=sandbox_res.get("stdout", ""),
                stderr=sandbox_res.get("stderr", ""),
                status=sandbox_res.get("status", "unknown"),
                execution_mode=sandbox_res.get("execution_mode", "unknown"),
            )
            results.append(result)

            observation = (
                f"[PROBE] {probe.purpose}\n"
                f"Code:\n{probe.code}\n"
                f"Status: {result.status}\n"
                f"Stdout:\n{result.stdout}\n"
                f"Stderr:\n{result.stderr}"
            )
            memory_engine.add_interaction(
                task_id=task_id,
                content=observation,
                status="probe",
                importance=4.0,
                metadata={"event": "environment_probe", "purpose": probe.purpose},
            )
        return results

    def format_probe_context(self, results: list[ProbeResult]) -> str:
        if not results:
            return ""
        lines = ["=== QUAN SÁT MÔI TRƯỜNG (PROBE) ==="]
        for i, r in enumerate(results, 1):
            lines.append(f"--- Probe #{i}: {r.purpose} [{r.status}] ---")
            if r.stdout.strip():
                lines.append(f"Output:\n{r.stdout.strip()}")
            if r.stderr.strip():
                lines.append(f"Errors:\n{r.stderr.strip()}")
        lines.append("")
        return "\n".join(lines)


environment_prober = EnvironmentProber()
