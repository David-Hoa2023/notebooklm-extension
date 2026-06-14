import os
import time
import uuid
import docker
import docker.errors
import subprocess
import sys
import ast
from src.config import config_instance

class GradedAssertTransformer(ast.NodeTransformer):
    def visit_Assert(self, node):
        pass_print = ast.Expr(
            value=ast.Call(
                func=ast.Name(id='print', ctx=ast.Load()),
                args=[ast.Constant(value='__ASSERT_PASSED__')],
                keywords=[]
            )
        )
        fail_print = ast.Expr(
            value=ast.Call(
                func=ast.Name(id='print', ctx=ast.Load()),
                args=[ast.Constant(value='__ASSERT_FAILED__')],
                keywords=[]
            )
        )
        try_node = ast.Try(
            body=[node, pass_print],
            handlers=[
                ast.ExceptHandler(
                    type=ast.Name(id='AssertionError', ctx=ast.Load()),
                    name=None,
                    body=[fail_print]
                )
            ],
            orelse=[],
            finalbody=[]
        )
        return ast.copy_location(try_node, node)

def rewrite_asserts_for_grading(test_code_str: str) -> str:
    try:
        tree = ast.parse(test_code_str)
        transformer = GradedAssertTransformer()
        transformed_tree = transformer.visit(tree)
        ast.fix_missing_locations(transformed_tree)
        return ast.unparse(transformed_tree)
    except Exception as e:
        print(f"Error rewriting assert statements: {e}")
        return test_code_str

class DockerSandbox:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            print(f"Warning: Failed to connect to Docker daemon: {e}. Sandbox will use local fallback.")
            self.client = None
            
        self.image_name = config_instance.get("sandbox.image_name", "python:3.10-slim")
        self.cpu_limit = config_instance.get("sandbox.cpu_limit", 1.0)
        self.mem_limit = config_instance.get("sandbox.mem_limit", "256m")
        self.timeout = config_instance.get("sandbox.timeout_seconds", 10)
        self.refuse_fallback = config_instance.get("sandbox.refuse_fallback", False)
        
        # Ensure image is pulled
        if self.client:
            self.ensure_image_pulled()

    def ensure_image_pulled(self):
        try:
            self.client.images.get(self.image_name)
        except docker.errors.ImageNotFound:
            print(f"Pulling Docker image {self.image_name}...")
            self.client.images.pull(self.image_name)
            print(f"Image {self.image_name} pulled successfully.")
        except Exception as e:
            print(f"Error checking/pulling image {self.image_name}: {e}")

    def run_code(self, code: str, filename: str = None) -> dict:
        """
        Execute python code in a sandbox container.
        """
        # Generate a unique temp file name if not provided
        if not filename:
            filename = f"run_{uuid.uuid4().hex}.py"
            
        temp_dir = os.path.abspath("temp_sandbox")
        os.makedirs(temp_dir, exist_ok=True)
        temp_filepath = os.path.join(temp_dir, filename)

        # Write code to temp file
        with open(temp_filepath, "w", encoding="utf-8") as f:
            f.write(code)

        if not self.client:
            if self.refuse_fallback:
                raise RuntimeError("Docker daemon is not running and refuse_fallback is enabled. Sandbox execution aborted.")
            # Fallback: Run code locally in a subprocess (non-isolated!)
            start_time = time.time()

            try:
                res = subprocess.run(
                    [sys.executable, temp_filepath],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )
                duration = time.time() - start_time
                stdout = res.stdout
                stderr = res.stderr
                exit_code = res.returncode
                
                if exit_code == 0:
                    status = "success"
                else:
                    if "SyntaxError:" in stderr or "IndentationError:" in stderr or "TabError:" in stderr:
                        status = "syntax_error"
                    else:
                        status = "runtime_error"
                        
                return {
                    "status": status,
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration_seconds": duration,
                    "execution_mode": "local_subprocess_fallback"
                }
            except subprocess.TimeoutExpired:
                duration = time.time() - start_time
                return {
                    "status": "timeout",
                    "exit_code": 137,
                    "stdout": "",
                    "stderr": f"Execution timed out after {self.timeout} seconds.",
                    "duration_seconds": duration,
                    "execution_mode": "local_subprocess_fallback"
                }
            except Exception as e:
                duration = time.time() - start_time
                return {
                    "status": "unknown_error",
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Local execution failed: {e}",
                    "duration_seconds": duration,
                    "execution_mode": "local_subprocess_fallback"
                }
            finally:
                if os.path.exists(temp_filepath):
                    try:
                        os.remove(temp_filepath)
                    except Exception:
                        pass

        # Map file paths for docker volume mount

        # On Windows, we mount absolute paths
        container_app_dir = "/app"
        volumes = {
            temp_dir: {"bind": container_app_dir, "mode": "rw"}
        }

        # Limit CPU
        nano_cpus = int(self.cpu_limit * 1_000_000_000)

        container = None
        start_time = time.time()
        
        try:
            # Create container
            container = self.client.containers.create(
                image=self.image_name,
                command=f"python {container_app_dir}/{filename}",
                volumes=volumes,
                network_mode="none",
                mem_limit=self.mem_limit,
                nano_cpus=nano_cpus,
                working_dir=container_app_dir,
            )
            
            # Start container
            container.start()
            
            # Wait for container to exit with a timeout
            exit_code = None
            oom_killed = False
            
            # Polling loop to check timeout
            while time.time() - start_time < self.timeout:
                container.reload()
                state = container.attrs.get("State", {})
                if not state.get("Running", False):
                    exit_code = state.get("ExitCode", 0)
                    oom_killed = state.get("OOMKilled", False)
                    break
                time.sleep(0.1)
            else:
                # Timeout occurred! Kill container.
                try:
                    container.kill()
                except Exception:
                    pass
                duration = time.time() - start_time
                return {
                    "status": "timeout",
                    "exit_code": 137, # Standard SIGKILL exit code
                    "stdout": "",
                    "stderr": f"Execution timed out after {self.timeout} seconds.",
                    "duration_seconds": duration,
                    "execution_mode": "docker"
                }

            duration = time.time() - start_time
            
            # Capture outputs
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            
            # Analyze exit status
            if oom_killed or exit_code == 137:
                status = "oom"
            elif exit_code == 0:
                status = "success"
            else:
                # Check for syntax error in stderr
                if "SyntaxError:" in stderr or "IndentationError:" in stderr or "TabError:" in stderr:
                    status = "syntax_error"
                else:
                    status = "runtime_error"
                    
            return {
                "status": status,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "duration_seconds": duration,
                "execution_mode": "docker"
            }

        except Exception as e:
            duration = time.time() - start_time
            return {
                "status": "unknown_error",
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Error running container: {e}",
                "duration_seconds": duration,
                "execution_mode": "docker"
            }
        finally:
            # Clean up
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            # Remove temporary python file
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except Exception:
                    pass
