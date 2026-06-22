import os
import re
import json
from typing import Dict, Any, List, Tuple, Optional
from pydantic import BaseModel, ValidationError, field_validator

class EVCompanyData(BaseModel):
    company_name: str
    revenue: float
    margin: float
    stock_price: float
    source_url: str
    metrics: Dict[str, Any]

    @field_validator("company_name")
    @classmethod
    def check_company_name(cls, v: str) -> str:
        if not v or v.strip() in ("", "N/A", "TBD", "placeholder", "Placeholder"):
            raise ValueError("Company name cannot be empty or placeholder.")
        return v

    @field_validator("revenue")
    @classmethod
    def check_revenue(cls, v: float) -> float:
        if v == 0.0:
            raise ValueError("Revenue must be a non-zero number.")
        if v < 0.0:
            raise ValueError("Revenue cannot be negative.")
        return v

    @field_validator("margin")
    @classmethod
    def check_margin(cls, v: float) -> float:
        if v == 0.0:
            raise ValueError("Margin must be a non-zero number.")
        return v

    @field_validator("stock_price")
    @classmethod
    def check_stock_price(cls, v: float) -> float:
        if v == 0.0:
            raise ValueError("Stock price must be a non-zero number.")
        if v < 0.0:
            raise ValueError("Stock price cannot be negative.")
        return v

    @field_validator("source_url")
    @classmethod
    def check_source_url(cls, v: str) -> str:
        # Simple URL check
        pattern = re.compile(r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        if not pattern.match(v) or "example.com" in v or "placeholder" in v:
            raise ValueError("Source URL must be a valid, non-placeholder URL.")
        return v

    @field_validator("metrics")
    @classmethod
    def check_metrics(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("Metrics dictionary cannot be empty.")
        for key, val in v.items():
            if val in (None, "", "N/A", "TBD", 0.0, "0"):
                raise ValueError(f"Metric '{key}' cannot have a placeholder, null, or zero value.")
        return v

def pre_verify_item(item_id: str, raw_data: Dict[str, Any], run_id: str) -> Tuple[bool, List[str], Optional[str]]:
    """
    Deterministically validates a raw item dict.
    If valid: saves to artifacts/raw/{run_id}/{item_id}.json and returns (True, [], None).
    If invalid: returns (False, checks_failed, rejection_reason).
    """
    try:
        EVCompanyData.model_validate(raw_data)
        
        # Save to raw artifacts storage on success
        raw_dir = os.path.join("artifacts", "raw", run_id).replace("\\", "/")
        os.makedirs(raw_dir, exist_ok=True)
        artifact_path = os.path.join(raw_dir, f"{item_id}.json").replace("\\", "/")
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2)
            
        return True, [], None
        
    except ValidationError as e:
        checks_failed = []
        rejection_reasons = []
        for error in e.errors():
            loc = error.get("loc", ("general",))
            field = str(loc[0])
            msg = error.get("msg", "Validation error")
            # Remove "Value error, " prefix from pydantic custom validation messages if present
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, "):]
            checks_failed.append(f"invalid_{field}")
            rejection_reasons.append(f"{field}: {msg}")
            
        return False, checks_failed, "; ".join(rejection_reasons)
