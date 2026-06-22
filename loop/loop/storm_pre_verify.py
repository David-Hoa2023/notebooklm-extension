import os
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from pydantic import ValidationError

from loop.storm_schema import (
    PerspectivesSchema,
    ContradictionMapSchema,
    OutlineSchema,
    SynthesisSchema,
    ArticleSchema,
    PeerReviewSchema
)
from loop.storm_paths import get_stage_normalized_filename

logger = logging.getLogger("loop.storm_pre_verify")

def get_stage_schema_class(stage: str) -> Any:
    mapping = {
        "perspectives": PerspectivesSchema,
        "contradictions": ContradictionMapSchema,
        "outline": OutlineSchema,
        "synthesis": SynthesisSchema,
        "article": ArticleSchema,
        "peer_review": PeerReviewSchema
    }
    return mapping.get(stage)

def pre_verify_storm_stage(stage: str, raw_data: Dict[str, Any], run_id: str, topic_slug: str, config: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str], Optional[str]]:
    """
    Validates stage outputs against Pydantic schemas.
    If valid: saves the normalized json and returns (True, [], None).
    If invalid: returns (False, checks_failed, rejection_reason).
    """
    schema_cls = get_stage_schema_class(stage)
    if not schema_cls:
        return False, ["invalid_stage"], f"Unknown stage: {stage}"

    try:
        schema_cls.model_validate(raw_data, context={"config": config} if config else None)
        
        # Save to normalized destination path
        norm_dir = os.path.join("artifacts", "raw", run_id, topic_slug).replace("\\", "/")
        os.makedirs(norm_dir, exist_ok=True)
        filename = get_stage_normalized_filename(stage)
        norm_path = os.path.join(norm_dir, filename).replace("\\", "/")
        
        with open(norm_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2)
            
        return True, [], None
        
    except ValidationError as e:
        checks_failed = []
        rejection_reasons = []
        for error in e.errors():
            loc = error.get("loc", ())
            field = str(loc[0]) if loc else "general"
            msg = error.get("msg", "Validation error")
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, "):]
            checks_failed.append(f"invalid_{field}")
            rejection_reasons.append(f"{field}: {msg}")
            
        return False, checks_failed, "; ".join(rejection_reasons)
