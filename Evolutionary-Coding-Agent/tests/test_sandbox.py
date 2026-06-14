import pytest
from src.infra.sandbox import DockerSandbox

def test_sandbox_basic():
    sandbox = DockerSandbox()
    sandbox.refuse_fallback = False
    code = "print('Hello from Sandbox')"
    res = sandbox.run_code(code)
    assert res["status"] == "success"
    assert "Hello from Sandbox" in res["stdout"]
    assert res["exit_code"] == 0

def test_sandbox_syntax_error():
    sandbox = DockerSandbox()
    sandbox.refuse_fallback = False
    code = "print('Unterminated string"
    res = sandbox.run_code(code)
    assert res["status"] == "syntax_error"
    assert res["exit_code"] != 0

def test_sandbox_timeout():
    sandbox = DockerSandbox()
    sandbox.refuse_fallback = False
    code = "import time\ntime.sleep(15)"
    res = sandbox.run_code(code)
    assert res["status"] == "timeout"
    assert "timed out" in res["stderr"]

