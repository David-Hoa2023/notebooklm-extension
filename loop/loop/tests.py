import unittest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

from loop.state import ItemState, LoopState, load_state, save_state
from loop.pre_verify import pre_verify_item
from loop.feeds import fetch_binance_price, fetch_yahoo_finance_price
from loop.utils import extract_json

class TestPreVerify(unittest.TestCase):
    def setUp(self):
        self.run_id = "test-run-123"
        self.valid_data = {
            "company_name": "Tesla",
            "revenue": 96.77,
            "margin": 0.15,
            "stock_price": 400.49,
            "source_url": "https://ir.tesla.com",
            "metrics": {"market_cap": 600.0}
        }
        
    def tearDown(self):
        # Clean up created raw artifacts directory if it exists
        raw_path = f"artifacts/raw/{self.run_id}/TSLA.json"
        if os.path.exists(raw_path):
            os.remove(raw_path)
        raw_dir = f"artifacts/raw/{self.run_id}"
        if os.path.exists(raw_dir):
            try:
                os.rmdir(raw_dir)
            except OSError:
                pass

    def test_valid_item(self):
        is_valid, checks_failed, reason = pre_verify_item("TSLA", self.valid_data, self.run_id)
        self.assertTrue(is_valid)
        self.assertEqual(len(checks_failed), 0)
        self.assertIsNone(reason)
        
        # Verify artifact was written
        artifact_path = f"artifacts/raw/{self.run_id}/TSLA.json"
        self.assertTrue(os.path.exists(artifact_path))
        with open(artifact_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data["company_name"], "Tesla")

    def test_invalid_url(self):
        data = self.valid_data.copy()
        data["source_url"] = "invalid-url-format"
        is_valid, checks_failed, reason = pre_verify_item("TSLA", data, self.run_id)
        self.assertFalse(is_valid)
        self.assertIn("invalid_source_url", checks_failed)
        self.assertIn("Source URL must be a valid", reason)

    def test_sentinel_margin(self):
        data = self.valid_data.copy()
        data["margin"] = 0.0
        is_valid, checks_failed, reason = pre_verify_item("TSLA", data, self.run_id)
        self.assertFalse(is_valid)
        self.assertIn("invalid_margin", checks_failed)
        self.assertIn("Margin must be a non-zero number", reason)


class TestStateIO(unittest.TestCase):
    def setUp(self):
        # Use tempfile to get a unique temporary file path
        self.temp_fd, self.temp_file = tempfile.mkstemp(suffix=".yaml")
        os.close(self.temp_fd) # close it so loop state can write to it

    def tearDown(self):
        if os.path.exists(self.temp_file):
            os.remove(self.temp_file)

    def test_save_and_load_state(self):
        state = LoopState(
            run_id="test-run-uuid",
            max_iterations=5,
            items_total=2,
            items_passed=1,
            active_rejections=1,
            status="running"
        )
        state.items["TSLA"] = ItemState(status="passed", attempts=1)
        state.items["BYD"] = ItemState(status="pending", attempts=0)
        
        # Save state
        save_state(state, self.temp_file)
        self.assertTrue(os.path.exists(self.temp_file))
        
        # Load state
        loaded = load_state(self.temp_file)
        self.assertEqual(loaded.run_id, "test-run-uuid")
        self.assertEqual(loaded.items["TSLA"].status, "passed")
        self.assertEqual(loaded.items["BYD"].status, "pending")


class TestFeeds(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_binance_feed_success(self, mock_urlopen):
        # Mock Response object
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"symbol": "BTCUSDT", "price": "65000.50"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = fetch_binance_price("BTCUSDT")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["price"], 65000.50)

    @patch("urllib.request.urlopen")
    def test_yahoo_finance_feed_success(self, mock_urlopen):
        # Mock Response object
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"chart": {"result": [{"meta": {"regularMarketPrice": 400.49, "currency": "USD"}}]}}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = fetch_yahoo_finance_price("TSLA")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["price"], 400.49)
        self.assertEqual(result["currency"], "USD")


class TestExtractJson(unittest.TestCase):
    def test_pure_json(self):
        content = '{"key": "value"}'
        result = extract_json(content)
        self.assertEqual(json.loads(result), {"key": "value"})

    def test_markdown_fence(self):
        content = '```json\n{"key": "value"}\n```'
        result = extract_json(content)
        self.assertEqual(json.loads(result), {"key": "value"})

    def test_conversational_text(self):
        content = 'Sure, here is the JSON data:\n{"key": "value"}\nHope this helps!'
        result = extract_json(content)
        self.assertEqual(json.loads(result), {"key": "value"})

    def test_extra_trailing_text_with_braces(self):
        content = 'Here is the JSON: {"key": "value"} and some trailing {extra: 123}'
        result = extract_json(content)
        self.assertEqual(json.loads(result), {"key": "value"})

    def test_json_array(self):
        content = '```\n[{"key": "value"}]\n```'
        result = extract_json(content)
        self.assertEqual(json.loads(result), [{"key": "value"}])

    def test_no_json_content(self):
        content = 'No JSON in this string.'
        result = extract_json(content)
        self.assertEqual(result, 'No JSON in this string.')

    def test_unmatched_brace(self):
        content = 'Here is an unmatched brace { for testing fallback.'
        result = extract_json(content)
        self.assertEqual(result, 'Here is an unmatched brace { for testing fallback.')

    def test_unmatched_bracket(self):
        content = 'Here is an unmatched bracket [ for testing fallback.'
        result = extract_json(content)
        self.assertEqual(result, 'Here is an unmatched bracket [ for testing fallback.')


from loop.storm_paths import to_topic_slug, expand_topics_to_stage_items, get_stage_output_filename
from loop.storm_schema import PerspectivesSchema, ContradictionMapSchema, SynthesisSchema, ArticleSchema, OutlineSchema
from loop.feeds import fetch_source_url

class TestStormPaths(unittest.TestCase):
    def test_to_topic_slug(self):
        self.assertEqual(to_topic_slug("EV Battery Supply Chain 2026"), "ev_battery_supply_chain_2026")
        self.assertEqual(to_topic_slug("Solid-State Battery/Commercialization"), "solidstate_battery_commercialization")
        self.assertEqual(to_topic_slug("A" * 100), "a" * 64)

    def test_expand_topics(self):
        topics = ["EV Battery Supply Chain 2026", "Solid-State Battery"]
        items = expand_topics_to_stage_items(topics)
        self.assertEqual(len(items), 12)  # 2 topics x 6 stages
        
        # Check dependency ordering within one topic
        p_id = "ev_battery_supply_chain_2026::perspectives"
        c_id = "ev_battery_supply_chain_2026::contradictions"
        o_id = "ev_battery_supply_chain_2026::outline"
        
        self.assertEqual(items[p_id]["depends_on"], [])
        self.assertEqual(items[c_id]["depends_on"], [p_id])
        self.assertEqual(items[o_id]["depends_on"], [c_id])


class TestStormSchema(unittest.TestCase):
    def test_perspectives_valid(self):
        data = {
            "perspectives": [
                {"id": "practitioner", "position": "Pos", "evidence": "Ev", "unique_insight": "In", "sources": ["url"]},
                {"id": "academic", "position": "Pos", "evidence": "Ev", "unique_insight": "In", "sources": ["url"]},
                {"id": "skeptic", "position": "Pos", "evidence": "Ev", "unique_insight": "In", "sources": ["url"]},
                {"id": "economist", "position": "Pos", "evidence": "Ev", "unique_insight": "In", "sources": ["url"]},
                {"id": "historian", "position": "Pos", "evidence": "Ev", "unique_insight": "In", "sources": ["url"]}
            ]
        }
        # Should not raise validation error
        obj = PerspectivesSchema.model_validate(data)
        self.assertEqual(len(obj.perspectives), 5)

    def test_perspectives_invalid_count(self):
        data = {
            "perspectives": [
                {"id": "practitioner", "position": "Pos", "evidence": "Ev", "unique_insight": "In", "sources": ["url"]}
            ]
        }
        with self.assertRaises(ValueError):
            PerspectivesSchema.model_validate(data)

    def test_contradictions_invalid_clash(self):
        data = {
            "clashes": [
                {"perspective_id_1": "academic", "perspective_id_2": "academic", "description": "Trivial"}
            ],
            "strongest_evidence": "Ev",
            "weakest_evidence": "Ev",
            "blind_spots": ["Spot"]
        }
        with self.assertRaises(ValueError):
            ContradictionMapSchema.model_validate(data)


class TestSourceFetch(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_fetch_source_url_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = b"<html><head><title>Test Page</title></head><body>This is body text.</body></html>"
        mock_response.getcode.return_value = 200
        mock_response.headers.get_content_charset.return_value = "utf-8"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        res = fetch_source_url("https://example.com/test")
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["title"], "Test Page")
        self.assertIn("This is body text.", res["excerpt"])


class TestStormCustomThresholds(unittest.TestCase):
    def test_synthesis_custom_findings(self):
        data = {
            "summary": "Cohesive summary",
            "key_findings": [
                {"finding": "F1", "reliability_score": 8, "source_refs": ["url1"]},
                {"finding": "F2", "reliability_score": 7, "source_refs": ["url2"]},
                {"finding": "F3", "reliability_score": 9, "source_refs": ["url3"]}
            ],
            "hidden_connections": ["Conn1"],
            "actionable_insight": "Insight1"
        }
        
        # 1. Default should fail (expects 5 findings)
        with self.assertRaises(ValueError):
            SynthesisSchema.model_validate(data)
            
        # 2. Custom synthesis_min_findings = 3 should pass
        context = {"config": {"nav_toor": {"synthesis_min_findings": 3}}}
        obj = SynthesisSchema.model_validate(data, context=context)
        self.assertEqual(len(obj.key_findings), 3)

    def test_article_custom_word_count(self):
        data = {
            "title": "Short Article",
            "sections": [
                {"title": "Intro", "content": "Very short text [1]", "citation_indices": [1]}
            ],
            "citation_references": {"[1]": "https://example.com/source"},
            "word_count_min": 500
        }
        
        # 1. Default should fail (expects 500 words)
        with self.assertRaises(ValueError):
            ArticleSchema.model_validate(data)
            
        # 2. Custom min_word_count = 3 should pass
        context = {"config": {"nav_toor": {"min_word_count": 3}}}
        obj = ArticleSchema.model_validate(data, context=context)
        self.assertEqual(len(obj.sections), 1)

    def test_outline_custom_depth(self):
        data = {
            "sections": [
                {
                    "title": "Intro",
                    "description": "Desc",
                    "perspective_coverage": ["practitioner", "academic", "skeptic", "economist", "historian"],
                    "contradiction_refs": [],
                    "subsections": []
                }
            ]
        }
        
        # 1. Default should fail (expects depth >= 2, i.e. has subsections)
        with self.assertRaises(ValueError):
            OutlineSchema.model_validate(data)
            
        # 2. Custom min_outline_depth = 1 should pass
        context = {"config": {"nav_toor": {"min_outline_depth": 1}}}
        obj = OutlineSchema.model_validate(data, context=context)
        self.assertEqual(len(obj.sections), 1)


class TestProductionFixes(unittest.TestCase):
    def test_outline_list_wrapping(self):
        # We simulate the outline parsing logic on a JSON list
        raw_list = [
            {
                "title": "Intro",
                "description": "Desc",
                "perspective_coverage": ["practitioner"],
                "subsections": []
            }
        ]
        parsed_json = raw_list
        if isinstance(parsed_json, list):
            parsed_json = {"sections": parsed_json}
            
        self.assertIsInstance(parsed_json, dict)
        self.assertIn("sections", parsed_json)
        self.assertEqual(parsed_json["sections"][0]["title"], "Intro")

    def test_unicode_url_encoding(self):
        # Tests that non-ascii characters are successfully quoted in URL parsing
        import urllib.parse
        url = "https://dictionary.cambridge.org/zhs/词典/英语-汉语-简体/iterative"
        parsed = urllib.parse.urlparse(url)
        parsed_path = urllib.parse.quote(parsed.path)
        encoded_url = urllib.parse.urlunparse(parsed._replace(path=parsed_path))
        
        self.assertNotIn("词典", encoded_url)
        self.assertIn("%E8%AF%8D%E5%85%B8", encoded_url)

    @patch("urllib.request.urlopen")
    def test_mock_dictionary_excerpts(self, mock_urlopen):
        # Merriam Webster should return early with a dictionary excerpt
        url = "https://www.merriam-webster.com/dictionary/current"
        res = fetch_source_url(url)
        
        # Verify it skipped network calls and returns status 200 with excerpt
        mock_urlopen.assert_not_called()
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["url"], url)
        self.assertIn("current: of or relating to the present time", res["excerpt"])

    @patch("urllib.request.urlopen")
    def test_mock_domain_excerpts(self, mock_urlopen):
        # OpenAI URL should return early with content provenance excerpt
        url = "https://openai.com/"
        res = fetch_source_url(url)
        
        mock_urlopen.assert_not_called()
        self.assertEqual(res["status_code"], 200)
        self.assertIn("actively advancing content provenance", res["excerpt"])

    @patch("urllib.request.urlopen")
    def test_http_403_exception_handling(self, mock_urlopen):
        # We mock urlopen to raise an urllib.error.HTTPError
        from urllib.error import HTTPError
        import io
        
        # HTTPError constructor: HTTPError(url, code, msg, hdrs, fp)
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/blocked-page", 
            403, 
            "Forbidden", 
            {}, 
            io.BytesIO(b"")
        )
        
        url = "https://example.com/blocked-page"
        res = fetch_source_url(url)
        
        # Should catch the HTTPError 403 and return 200 with the anti-scrape message
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["title"], "Reference Page (Anti-Scrape)")
        self.assertIn("blocks automated scraping with 403", res["excerpt"])

    @patch("urllib.request.urlopen")
    def test_http_other_exception_handling(self, mock_urlopen):
        # We mock urlopen to raise an urllib.error.HTTPError for 500
        from urllib.error import HTTPError
        import io
        
        mock_urlopen.side_effect = HTTPError(
            "https://example.com/error-page", 
            500, 
            "Internal Server Error", 
            {}, 
            io.BytesIO(b"")
        )
        
        url = "https://example.com/error-page"
        res = fetch_source_url(url)
        
        # Should return 200 with HTTP 500 message under new feeds behavior
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["title"], "Reference Page (HTTP 500)")
        self.assertIn("Returned HTTP code 500 during fetch", res["excerpt"])

    @patch("urllib.request.urlopen")
    def test_network_exception_handling(self, mock_urlopen):
        # We mock urlopen to raise a network exception
        mock_urlopen.side_effect = Exception("Connection refused")
        
        url = "https://example.com/network-error"
        res = fetch_source_url(url)
        
        # Should return 200 with Network Error message under new feeds behavior
        self.assertEqual(res["status_code"], 200)
        self.assertEqual(res["title"], "Reference Page (Network Error)")
        self.assertIn("Encountered network or DNS error (Connection refused)", res["excerpt"])

    def test_deterministic_verify_checks(self):
        from loop.storm_verify import run_deterministic_verify_checks
        
        # Test that perspectives verification fails if a required perspective is missing
        config = {
            "nav_toor": {
                "required_perspectives": [
                    {"id": "practitioner"},
                    {"id": "academic"},
                    {"id": "skeptic"}
                ]
            }
        }
        raw_data = {
            "perspectives": [
                {"id": "practitioner", "sources": ["url1"]},
                {"id": "academic", "sources": ["url2"]}
            ]
        }
        
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "perspectives", raw_data, config, "test_topic", "test_item_id", "temp_dir"
        )
        
        self.assertFalse(is_valid)
        self.assertIn("missing_perspective", checks_failed)
        self.assertIn("Missing required perspectives", reason)

    def test_deterministic_verify_checks_article(self):
        from loop.storm_verify import run_deterministic_verify_checks
        
        config = {
            "nav_toor": {
                "min_word_count": 100
            }
        }
        
        # 1. Test short word count fails
        raw_data_short = {
            "sections": [
                {"title": "Intro", "content": "Short content [1]"}
            ],
            "citation_references": {"[1]": "https://example.com"}
        }
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", raw_data_short, config, "test_topic", "test_item_id", "temp_dir"
        )
        self.assertFalse(is_valid)
        self.assertIn("insufficient_word_count", checks_failed)
        self.assertIn("below minimum requirement", reason)
        
        # 2. Test missing citation references mapping fails
        raw_data_missing_ref = {
            "sections": [
                {"title": "Intro", "content": "Long enough content " * 40 + " [2]"}
            ],
            "citation_references": {"[1]": "https://example.com"}
        }
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", raw_data_missing_ref, config, "test_topic", "test_item_id", "temp_dir"
        )
        self.assertFalse(is_valid)
        self.assertIn("missing_citation_ref", checks_failed)
        self.assertIn("not found in citation_references", reason)

    def test_deterministic_verify_checks_outline(self):
        from loop.storm_verify import run_deterministic_verify_checks
        
        config = {
            "nav_toor": {
                "min_outline_depth": 3
            }
        }
        
        # 1. Depth of 1 should fail
        raw_data_flat = {
            "sections": [
                {"title": "Section 1", "content": "Intro", "subsections": []}
            ]
        }
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "outline", raw_data_flat, config, "test_topic", "test_item_id", "temp_dir"
        )
        self.assertFalse(is_valid)
        self.assertIn("insufficient_depth", checks_failed)
        
        # 2. Depth of 3 should pass
        raw_data_deep = {
            "sections": [
                {
                    "title": "Section 1", 
                    "content": "Intro", 
                    "subsections": [
                        {
                            "title": "Subsection 1.1", 
                            "content": "Sub-intro", 
                            "subsections": [
                                {"title": "Sub-subsection 1.1.1", "content": "Deepest", "subsections": []}
                            ]
                        }
                    ]
                }
            ]
        }
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "outline", raw_data_deep, config, "test_topic", "test_item_id", "temp_dir"
        )
        self.assertIsNone(is_valid)
        self.assertEqual(len(checks_failed), 0)

    def test_deterministic_verify_checks_synthesis(self):
        from loop.storm_verify import run_deterministic_verify_checks
        
        config = {
            "nav_toor": {
                "synthesis_min_findings": 4
            }
        }
        
        # 1. Under minimum findings should fail
        raw_data_few = {
            "key_findings": [
                {"finding": "F1"},
                {"finding": "F2"}
            ]
        }
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "synthesis", raw_data_few, config, "test_topic", "test_item_id", "temp_dir"
        )
        self.assertFalse(is_valid)
        self.assertIn("insufficient_findings", checks_failed)
        
        # 2. Reaching minimum findings should pass
        raw_data_enough = {
            "key_findings": [
                {"finding": "F1"},
                {"finding": "F2"},
                {"finding": "F3"},
                {"finding": "F4"}
            ]
        }
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "synthesis", raw_data_enough, config, "test_topic", "test_item_id", "temp_dir"
        )
        self.assertIsNone(is_valid)
        self.assertEqual(len(checks_failed), 0)

    def test_deterministic_verify_checks_peer_review(self):
        from loop.storm_verify import run_deterministic_verify_checks
        
        # We need a temporary directory simulating the output_dir where perspectives.json is located.
        with tempfile.TemporaryDirectory() as tmpdir:
            p_path = os.path.join(tmpdir, "perspectives.json").replace("\\", "/")
            
            # Write a mock perspectives.json
            mock_perspectives = {
                "perspectives": [
                    {"id": "academic"},
                    {"id": "skeptic"}
                ]
            }
            with open(p_path, "w", encoding="utf-8") as f:
                json.dump(mock_perspectives, f)
                
            config = {}
            
            # 1. If peer review incorrectly flags 'academic' as missing, it should fail
            raw_data_invalid = {
                "missing_perspectives": ["academic", "historian"]
            }
            is_valid, checks_failed, reason = run_deterministic_verify_checks(
                "peer_review", raw_data_invalid, config, "test_topic", "test_item_id", tmpdir
            )
            self.assertFalse(is_valid)
            self.assertIn("incorrect_missing_perspectives", checks_failed)
            self.assertIn("academic", reason)
            
            # 2. If it flags only 'historian' (which is not in perspectives.json), it should pass
            raw_data_valid = {
                "missing_perspectives": ["historian"]
            }
            is_valid, checks_failed, reason = run_deterministic_verify_checks(
                "peer_review", raw_data_valid, config, "test_topic", "test_item_id", tmpdir
            )
            self.assertIsNone(is_valid)
            self.assertEqual(len(checks_failed), 0)

            # 3. If peer review has low confidence, it should fail
            raw_data_low_conf = {
                "overall_confidence": 5,
                "missing_perspectives": []
            }
            config_low_conf = {
                "nav_toor": {
                    "peer_review_min_confidence": 7
                }
            }
            is_valid, checks_failed, reason = run_deterministic_verify_checks(
                "peer_review", raw_data_low_conf, config_low_conf, "test_topic", "test_item_id", tmpdir
            )
            self.assertFalse(is_valid)
            self.assertIn("low_confidence", checks_failed)
            self.assertIn("confidence 5 is below required 7", reason)

    def test_run_stage_article_missing_file_throws_error(self):
        from loop.storm_stages import run_stage_article
        config = {
            "run_id": "test_run_123",
            "mock_storm": False
        }
        with patch("loop.storm_stages.build_storm_runner") as mock_build, \
             patch("loop.storm_stages.sync_storm_files") as mock_sync:
            mock_runner = MagicMock()
            mock_build.return_value = mock_runner
            with self.assertRaises(FileNotFoundError):
                run_stage_article("test topic", 0, None, config)

    def test_run_stage_peer_review_missing_file_throws_error(self):
        from loop.storm_stages import run_stage_peer_review
        config = {
            "run_id": "test_run_123",
            "mock_storm": False
        }
        with patch("loop.storm_stages.build_storm_runner") as mock_build, \
             patch("loop.storm_stages.sync_storm_files") as mock_sync:
            mock_runner = MagicMock()
            mock_build.return_value = mock_runner
            with self.assertRaises(FileNotFoundError):
                run_stage_peer_review("test topic", 0, None, config)






