import json
import pytest
from unittest.mock import patch, MagicMock
from src.skill.skill_manager import skill_manager
from src.skill.skill_tester import skill_tester_instance
from src.config import config_instance
from src.memory.memory_engine import memory_engine

def test_skill_vertical_extraction():
    task_id = "SLS_REVENUE_001"
    task_desc = "Aggregate sales revenue"
    code = "def aggregate_sales_revenue(orders):\n    return {'total_revenue': 100.0, 'total_discount': 10.0, 'net_revenue': 90.0}"
    
    mock_llm_res = {
        "skills": [
            {
                "name": "aggregate_sales_revenue",
                "code": "def aggregate_sales_revenue(orders):\n    return {'total_revenue': 100.0, 'total_discount': 10.0, 'net_revenue': 90.0}",
                "docstring": "Aggregate sales revenue and discount.",
                "domain": "math",
                "vertical": "sales",
                "dependencies": []
            }
        ]
    }
    
    config_mock = {
        "verticals.enabled": True,
        "verticals.allowed": ["sales", "marketing", "finance", "generic"],
        "project.version": "1.0.0"
    }
    
    with patch.object(skill_manager.llm, "generate", return_value=json.dumps(mock_llm_res)) as mock_gen, \
         patch.object(skill_tester_instance, "verify_skill", return_value=(True, "def test_agg(): pass")) as mock_verify, \
         patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)), \
         patch.object(memory_engine, "add_skill", return_value="skl_test_123") as mock_add:
         
        res = skill_manager.extract_and_register_skills(
            task_id=task_id,
            task_description=task_desc,
            code=code,
            vertical_hint="sales"
        )
        
        assert len(res) == 1
        assert res[0] == "skl_test_123"
        
        mock_add.assert_called_once()
        args, kwargs = mock_add.call_args
        metadata = kwargs.get("metadata")
        assert metadata["vertical"] == "sales"
        assert metadata["domain"] == "math"

def test_skill_vertical_clamping():
    task_id = "FIN_LEDGER_001"
    task_desc = "Calculate ledger balance"
    code = "def calculate_ledger_balance(txs):\n    return {'final_balance': 100.0}"
    
    mock_llm_res = {
        "skills": [
            {
                "name": "calculate_ledger_balance",
                "code": "def calculate_ledger_balance(txs):\n    return {'final_balance': 100.0}",
                "docstring": "Calculate final ledger balance.",
                "domain": "math",
                "vertical": "crypto",
                "dependencies": []
            }
        ]
    }
    
    config_mock = {
        "verticals.enabled": True,
        "verticals.allowed": ["sales", "marketing", "finance", "generic"],
        "project.version": "1.0.0"
    }
    
    with patch.object(skill_manager.llm, "generate", return_value=json.dumps(mock_llm_res)), \
         patch.object(skill_tester_instance, "verify_skill", return_value=(True, "def test_bal(): pass")), \
         patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)), \
         patch.object(memory_engine, "add_skill", return_value="skl_test_456") as mock_add:
         
        res = skill_manager.extract_and_register_skills(
            task_id=task_id,
            task_description=task_desc,
            code=code,
            vertical_hint="finance"
        )
        
        assert len(res) == 1
        assert res[0] == "skl_test_456"
        
        mock_add.assert_called_once()
        args, kwargs = mock_add.call_args
        metadata = kwargs.get("metadata")
        assert metadata["vertical"] == "generic"
