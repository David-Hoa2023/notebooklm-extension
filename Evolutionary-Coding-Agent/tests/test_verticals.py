import pytest
from src.taxonomy.verticals import (
    infer_vertical,
    infer_vertical_primary,
    get_allowed_verticals
)

def test_infer_vertical():
    # Test sales vertical detection
    assert infer_vertical("summarize sales revenue by product") == {"sales"}
    assert infer_vertical("an order with some discount details") == {"sales"}
    
    # Test marketing vertical detection
    assert infer_vertical("start a campaign and check the UTM segment") == {"marketing"}
    
    # Test finance vertical detection
    assert infer_vertical("update the general ledger and print an invoice") == {"finance"}
    assert infer_vertical("compute the tax on this invoice balance") == {"finance"}
    
    # Test SMTP / non-matching
    assert infer_vertical("SMTP send email") == set()
    
    # Test multiple verticals
    multiple = infer_vertical("integrate sales revenue with finance invoice ledger")
    assert "sales" in multiple
    assert "finance" in multiple

def test_infer_vertical_primary():
    assert infer_vertical_primary("summarize sales revenue by product") == "sales"
    assert infer_vertical_primary("SMTP send email") == "generic"
    assert infer_vertical_primary("") == "generic"
    
    # Precedence check (sales vs finance)
    primary = infer_vertical_primary("sales revenue vs finance invoice ledger")
    assert primary in ["sales", "finance"]

def test_get_allowed_verticals():
    allowed = get_allowed_verticals()
    assert "sales" in allowed
    assert "marketing" in allowed
    assert "finance" in allowed
    assert "generic" in allowed
