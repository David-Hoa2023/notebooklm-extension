import os
import yaml
import tempfile
from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime

class ItemState(BaseModel):
    status: str = "pending"  # pending | executing | pre_failed | verify_failed | passed
    attempts: int = 0
    last_rejection: Optional[str] = None
    artifact_path: Optional[str] = None
    verified_at: Optional[str] = None
    stage: Optional[str] = None
    topic_slug: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    override_reason: Optional[str] = None

class LoopState(BaseModel):
    run_id: str
    iteration: int = 1
    max_iterations: int = 5
    items_total: int = 0
    items_passed: int = 0
    active_rejections: int = 0
    status: str = "running"  # running | passed | failed | escalated
    items: Dict[str, ItemState] = Field(default_factory=dict)

def load_state(path: str) -> LoopState:
    """
    Loads and validates the LoopState from a YAML file.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"State file not found at {path}")
        
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        
    if not data:
        raise ValueError(f"State file at {path} is empty or invalid.")
        
    return LoopState.model_validate(data)

def save_state(state: LoopState, path: str):
    """
    Atomically writes the LoopState to a YAML file using a temp file and replace.
    """
    data = state.model_dump()
    
    # Resolve the directory of the state file to place the temp file in the same directory
    # (required for atomic rename to prevent cross-device/drive link issues)
    dir_name = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_name, exist_ok=True)
    
    # Create a temp file in the same directory
    fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix="state_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
            
        # Atomic replace
        os.replace(temp_path, path)
    except Exception as e:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e
