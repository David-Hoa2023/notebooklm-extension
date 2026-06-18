import re
from src.config import config_instance

TECHNICAL_DOMAINS = [
    "regex", "smtp", "json", "math", "datetime", 
    "string_parsing", "file_io", "algorithms", 
    "data_structures", "error_handling", "testing", "generic"
]

DEFAULT_VERTICALS = ["sales", "marketing", "finance", "generic"]

VERTICAL_KEYWORDS = {
    "sales": ["revenue", "order", "discount", "sales", "sold", "deal", "pricing"],
    "marketing": ["campaign", "segment", "utm", "ad", "marketing", "subscriber", "click-through"],
    "finance": ["ledger", "balance", "invoice", "tax", "finance", "payment", "transaction", "bank", "account"]
}

def get_allowed_verticals() -> list[str]:
    """Returns the list of allowed verticals, loading from config if enabled/available."""
    # Note: If verticals.enabled config key is not present, default to True
    if config_instance.get("verticals.enabled", True):
        allowed = config_instance.get("verticals.allowed")
        if allowed:
            return [v.lower().strip() for v in allowed]
    return DEFAULT_VERTICALS

def infer_vertical(text: str) -> set[str]:
    """
    Infers business verticals based on keywords in the text.
    Returns a set of matched verticals.
    """
    if not text:
        return set()
    
    text_lower = text.lower()
    matched = set()
    allowed_verticals = get_allowed_verticals()
    
    for vertical, keywords in VERTICAL_KEYWORDS.items():
        if vertical in allowed_verticals:
            for keyword in keywords:
                # Use word boundaries for keyword match to prevent partial matches like 'taxi' matching 'tax'
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    matched.add(vertical)
                    break
                    
    return matched

def infer_vertical_primary(text: str) -> str | None:
    """
    Infers the primary vertical. Returns the first matched vertical or 'generic' if none match.
    """
    matched = infer_vertical(text)
    if not matched:
        return "generic"
    # Pick the first matched vertical based on DEFAULT_VERTICALS order or alphabetical
    for v in DEFAULT_VERTICALS:
        if v in matched:
            return v
    return list(matched)[0]
