import os
import json
import pytest
from unittest.mock import patch, MagicMock
from src.config import config_instance
from src.dreaming.dream_loader import dream_loader

def test_dream_loader_disabled():
    with patch.object(config_instance, "get", return_value=False) as mock_get:
        formatted = dream_loader.format_for_prompt("Some task description")
        assert formatted == ""

def test_dream_loader_enabled_no_latest_no_db(tmp_path):
    # Enable dreaming but mock file and DB to be empty
    config_mock = {
        "dreaming.enabled": True,
        "dreaming.max_summary_chars": 1000,
        "dreaming.max_dream_insights_in_prompt": 3
    }
    
    with patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
        with patch("os.path.exists", return_value=False):
            with patch("src.dreaming.dream_store.dream_store.retrieve_dreams", return_value=[]):
                formatted = dream_loader.format_for_prompt("Some description")
                assert formatted == ""

def test_dream_loader_formatting(tmp_path):
    config_mock = {
        "dreaming.enabled": True,
        "dreaming.max_summary_chars": 1000,
        "dreaming.max_dream_insights_in_prompt": 3
    }
    
    # Mock data from SQLite retrieved dreams
    mock_sqlite_dreams = [
        {
            "id": "drm_1",
            "content": "[SUMMARY] Tóm tắt của session",
            "metadata": {"type": "session_summary"}
        },
        {
            "id": "drm_2",
            "content": "Không gọi login() khi không có credentials",
            "metadata": {"type": "insight", "domain": "smtp"}
        },
        {
            "id": "drm_3",
            "content": "Sử dụng regex tách email thay vì cắt chuỗi thủ công",
            "metadata": {"type": "insight", "domain": "regex"}
        }
    ]
    
    # Mock latest.json filesystem reading
    mock_latest_json = {
        "session_summary": "Session này sửa thành công lỗi SMTP",
        "insights": []
    }
    
    with patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()) as mock_open:
                mock_file = MagicMock()
                mock_file.read.return_value = json.dumps(mock_latest_json)
                mock_open.return_value.__enter__.return_value = mock_file
                
                with patch("src.dreaming.dream_store.dream_store.retrieve_dreams", return_value=mock_sqlite_dreams):
                    formatted = dream_loader.format_for_prompt("SMTP regex task description")
                    
                    # Verification
                    assert "=== SESSION WISDOM (DREAM) ===" in formatted
                    assert "Tóm tắt phiên trước: Session này sửa thành công lỗi SMTP" in formatted
                    assert "Các bài học kinh nghiệm chắt lọc:" in formatted
                    # Check first insight content & domain
                    assert "Không gọi login() khi không có credentials [Domain: smtp]" in formatted
                    # Check second insight content & domain
                    assert "Sử dụng regex tách email thay vì cắt chuỗi thủ công [Domain: regex]" in formatted
                    # The session summary database row should be skipped in the insights list
                    assert "Tóm tắt của session" not in formatted.split("Các bài học kinh nghiệm chắt lọc:")[1]

def test_dream_loader_truncation():
    config_mock = {
        "dreaming.enabled": True,
        "dreaming.max_summary_chars": 70, # tiny limit to force truncation
        "dreaming.max_dream_insights_in_prompt": 3
    }
    
    mock_sqlite_dreams = [
        {
            "id": "drm_2",
            "content": "Một insight siêu dài vượt quá giới hạn thiết lập",
            "metadata": {"type": "insight", "domain": "generic"}
        }
    ]
    
    with patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
        with patch("os.path.exists", return_value=False):
            with patch("src.dreaming.dream_store.dream_store.retrieve_dreams", return_value=mock_sqlite_dreams):
                formatted = dream_loader.format_for_prompt("some desc")
                assert len(formatted) <= 70
                assert "[TRUNCATED DUE TO BUDGET]" in formatted

def test_dream_loader_scope_and_domain_filtering():
    config_mock = {
        "dreaming.enabled": True,
        "dreaming.max_summary_chars": 1000,
        "dreaming.max_dream_insights_in_prompt": 3
    }
    
    mock_sqlite_dreams = [
        {
            "id": "drm_a",
            "content": "SMTP global lesson",
            "metadata": {"type": "insight", "scope": "global", "domain": "smtp"}
        },
        {
            "id": "drm_b",
            "content": "SMTP NEG_001 task lesson",
            "metadata": {"type": "insight", "scope": "task", "domain": "smtp", "evidence_task_ids": ["NEG_001"]}
        },
        {
            "id": "drm_c",
            "content": "Regex global lesson",
            "metadata": {"type": "insight", "scope": "global", "domain": "regex"}
        }
    ]
    
    with patch.object(config_instance, "get", side_effect=lambda key, default=None: config_mock.get(key, default)):
        with patch("os.path.exists", return_value=False):
            with patch("src.dreaming.dream_store.dream_store.retrieve_dreams", return_value=mock_sqlite_dreams):
                # Scenario 1: SMTP description but unrelated task SUB_001
                # Should include A (SMTP, global), exclude B (SMTP task mismatch), exclude C (Regex domain mismatch)
                formatted_1 = dream_loader.format_for_prompt(
                    description="Write email code with smtp client", 
                    task_id="SUB_001"
                )
                assert "SMTP global lesson" in formatted_1
                assert "SMTP NEG_001 task lesson" not in formatted_1
                assert "Regex global lesson" not in formatted_1
                
                # Scenario 2: SMTP description and matching task NEG_001
                # Should include A (SMTP, global) and B (SMTP task match), exclude C (Regex domain mismatch)
                formatted_2 = dream_loader.format_for_prompt(
                    description="Write email code with smtp client for NEG_001", 
                    task_id="NEG_001"
                )
                assert "SMTP global lesson" in formatted_2
                assert "SMTP NEG_001 task lesson" in formatted_2
                assert "Regex global lesson" not in formatted_2

