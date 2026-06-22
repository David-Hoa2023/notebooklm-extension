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
            
            # 2. If it flags only 'historian' (which is not in perspectives.json), and the article has it, it should pass
            polished_path = os.path.join(tmpdir, "storm_gen_article_polished.txt").replace("\\", "/")
            with open(polished_path, "w", encoding="utf-8") as f:
                f.write("This article covers the views of the historian and academic perspectives.")
                
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
            
            # 4. If peer review overall grade is below threshold, it should fail
            raw_data_low_grade = {
                "overall_grade": "C+",
                "missing_perspectives": []
            }
            config_low_grade = {
                "nav_toor": {
                    "fidelity": {
                        "peer_review_min_grade": "B-"
                    }
                }
            }
            is_valid, checks_failed, reason = run_deterministic_verify_checks(
                "peer_review", raw_data_low_grade, config_low_grade, "test_topic", "test_item_id", tmpdir
            )
            self.assertFalse(is_valid)
            self.assertIn("grade_below_threshold", checks_failed)
            self.assertIn("below the required 'B-'", reason)

    def test_run_stage_article_missing_file_throws_error(self):
        from loop.storm_stages import run_stage_article
        config = {
            "run_id": "test_run_123",
            "mock_storm": False,
            "nav_toor": {
                "fidelity": {
                    "article_mode": "storm_only"
                }
            }
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


class TestStormFidelity(unittest.TestCase):
    def setUp(self):
        self.fixture_dir = "loop/fixtures/conformance_608a1d91"
        self.config = {
            "nav_toor": {
                "fidelity": {
                    "article_mode": "briefing_first",
                    "article_min_perspective_mentions": 5,
                    "citation_upstream_min_ratio": 0.5,
                    "synthesis_term_overlap_min": 0.3,
                    "contradiction_min_reflected": 2,
                    "peer_review_min_grade": "B-",
                    "peer_review_fail_on_missing_perspectives": True,
                    "article_max_attempts_before_escalate": 10,
                    "force_storm_regen_on_drift": True,
                    "blocked_citation_domains": [
                        "dictionary.cambridge.org",
                        "merriam-webster.com",
                        "login.adaptiveinsights.com"
                    ]
                }
            }
        }

    def test_extract_article_text(self):
        from loop.storm_fidelity import extract_article_text
        article_json = {
            "title": "My Article",
            "sections": [
                {"title": "Sec 1", "content": "Content of Sec 1.", "subsections": []},
                {"title": "Sec 2", "content": "Content of Sec 2.", "subsections": [
                    {"title": "Sub 2.1", "content": "Content of Sub 2.1.", "subsections": []}
                ]}
            ]
        }
        text = extract_article_text(article_json)
        self.assertIn("My Article", text)
        self.assertIn("Content of Sec 1.", text)
        self.assertIn("Content of Sub 2.1.", text)

    def test_count_perspective_mentions(self):
        from loop.storm_fidelity import count_perspective_mentions
        text = "This report discusses the practitioner perspective, while also introducing some academic and skeptic thoughts."
        required = [
            {"id": "practitioner", "label": "Practitioner"},
            {"id": "academic", "label": "Academic"},
            {"id": "skeptic", "label": "Skeptic"},
            {"id": "economist", "label": "Economist"}
        ]
        counts = count_perspective_mentions(text, required)
        self.assertEqual(counts["practitioner"], 1)
        self.assertEqual(counts["academic"], 1)
        self.assertEqual(counts["skeptic"], 1)
        self.assertEqual(counts["economist"], 0)

    def test_citation_upstream_ratio(self):
        from loop.storm_fidelity import citation_upstream_ratio
        citations = {
            "[1]": "https://example.com/source1",
            "[2]": "https://example.com/source2",
            "[3]": "https://dictionary.com/word"
        }
        upstream_urls = [
            "https://example.com/source1",
            "https://example.com/source2",
            "https://example.com/another"
        ]
        ratio = citation_upstream_ratio(citations, upstream_urls)
        self.assertAlmostEqual(ratio, 2/3)

    def test_synthesis_term_overlap(self):
        from loop.storm_fidelity import synthesis_term_overlap
        synthesis = {
            "key_findings": [
                {"finding": "Solid-state cell yield is currently sub-50% in testing.", "supporting_evidence": "Yield data"}
            ],
            "actionable_insights": [
                {"insight": "Establish domestic processing to bypass tariffs."}
            ]
        }
        article_text = "Yield testing shows solid-state cell yield is sub-50%. Establishing domestic processing helps bypass tariffs."
        overlap = synthesis_term_overlap(synthesis, article_text)
        self.assertGreater(overlap, 0.5)

    def test_contradictions_reflected(self):
        from loop.storm_fidelity import contradictions_reflected
        contradiction_map = {
            "clashes": [
                {"description": "Academics claim rapid scaling of chemistry, while skeptics warn of recycling bottlenecks."}
            ]
        }
        article_text = "Academics claim rapid scaling, but skeptics warns about recycling bottlenecks."
        reflected = contradictions_reflected(contradiction_map, article_text)
        self.assertEqual(reflected, 1)

    def test_is_blocked_domain(self):
        from loop.storm_fidelity import is_blocked_domain
        blocked_list = ["merriam-webster.com", "dictionary.cambridge.org"]
        self.assertTrue(is_blocked_domain("https://www.merriam-webster.com/dictionary/current", blocked_list))
        self.assertFalse(is_blocked_domain("https://arxiv.org/abs/1234.5678", blocked_list))

    def test_grade_at_least(self):
        from loop.storm_fidelity import grade_at_least
        self.assertTrue(grade_at_least("A-", "B-"))
        self.assertTrue(grade_at_least("B-", "B-"))
        self.assertFalse(grade_at_least("C+", "B-"))

    def test_fixture_perspective_mentions_fails(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "article.json"), "r", encoding="utf-8") as f:
            article_data = json.load(f)
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", article_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("missing_perspective_in_article", checks_failed)

    def test_fixture_citation_upstream_ratio_fails(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "article.json"), "r", encoding="utf-8") as f:
            article_data = json.load(f)
        # Set required perspectives to a word guaranteed to be present ("loop") to avoid early return on UCF-020
        self.config["nav_toor"]["required_perspectives"] = [{"id": "loop", "label": "loop"}]
        # Set min ratio high so it is guaranteed to fail
        self.config["nav_toor"]["fidelity"]["citation_upstream_min_ratio"] = 0.5
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", article_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("low_upstream_citation_ratio", checks_failed)

    def test_fixture_blocked_citation_domain_fails(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "article.json"), "r", encoding="utf-8") as f:
            article_data = json.load(f)
        # Set required perspectives to a word guaranteed to be present ("loop") to avoid early return on UCF-020
        self.config["nav_toor"]["required_perspectives"] = [{"id": "loop", "label": "loop"}]
        # Set citation_upstream_min_ratio to 0.0 to avoid early return on UCF-021
        self.config["nav_toor"]["fidelity"]["citation_upstream_min_ratio"] = 0.0
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", article_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("blocked_citation_domain", checks_failed)

    def test_fixture_semantic_drift_fails(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "article.json"), "r", encoding="utf-8") as f:
            article_data = json.load(f)
        # Bypass perspective check by required_perspectives targeting "loop"
        self.config["nav_toor"]["required_perspectives"] = [{"id": "loop", "label": "loop"}]
        # Bypass ratio check and blocked domain check
        self.config["nav_toor"]["fidelity"]["citation_upstream_min_ratio"] = 0.0
        self.config["nav_toor"]["fidelity"]["allow_blocked_domains"] = True
        # Set synthesis overlap min high (0.5) so it fails on the fixture's 0.342 overlap
        self.config["nav_toor"]["fidelity"]["synthesis_term_overlap_min"] = 0.5
        
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", article_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("semantic_drift", checks_failed)

    def test_fixture_contradictions_not_reflected_fails(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "article.json"), "r", encoding="utf-8") as f:
            article_data = json.load(f)
        # Bypass perspective, ratio, blocked domain, and synthesis overlap checks
        self.config["nav_toor"]["required_perspectives"] = [{"id": "loop", "label": "loop"}]
        self.config["nav_toor"]["fidelity"]["citation_upstream_min_ratio"] = 0.0
        self.config["nav_toor"]["fidelity"]["allow_blocked_domains"] = True
        self.config["nav_toor"]["fidelity"]["synthesis_term_overlap_min"] = 0.0
        # Set contradiction clashes min high (5) so it fails on the fixture
        self.config["nav_toor"]["fidelity"]["contradiction_min_reflected"] = 5
        
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", article_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("contradictions_not_reflected", checks_failed)

    def test_fixture_semantic_drift_fails_without_bypass_ucf020(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "article.json"), "r", encoding="utf-8") as f:
            article_data = json.load(f)
        
        # Modify the loaded article data in memory to mention all 5 standard perspectives
        if article_data.get("sections"):
            article_data["sections"][0]["content"] += " practitioner academic skeptic economist historian"
            
        self.config["nav_toor"]["fidelity"]["citation_upstream_min_ratio"] = 0.0
        self.config["nav_toor"]["fidelity"]["allow_blocked_domains"] = True
        self.config["nav_toor"]["fidelity"]["synthesis_term_overlap_min"] = 0.5
        
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", article_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("semantic_drift", checks_failed)

    def test_fixture_contradictions_not_reflected_fails_without_bypass_ucf020(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "article.json"), "r", encoding="utf-8") as f:
            article_data = json.load(f)
            
        # Modify the loaded article data in memory to mention all 5 standard perspectives
        if article_data.get("sections"):
            article_data["sections"][0]["content"] += " practitioner academic skeptic economist historian"
            
        self.config["nav_toor"]["fidelity"]["citation_upstream_min_ratio"] = 0.0
        self.config["nav_toor"]["fidelity"]["allow_blocked_domains"] = True
        self.config["nav_toor"]["fidelity"]["synthesis_term_overlap_min"] = 0.0
        self.config["nav_toor"]["fidelity"]["contradiction_min_reflected"] = 5
        
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "article", article_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("contradictions_not_reflected", checks_failed)

    def test_fixture_peer_review_fails_on_grade_and_missing_perspectives(self):
        from loop.storm_verify import run_deterministic_verify_checks
        with open(os.path.join(self.fixture_dir, "peer_review.json"), "r", encoding="utf-8") as f:
            peer_review_data = json.load(f)
        
        # 1. Grade check fails
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "peer_review", peer_review_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("grade_below_threshold", checks_failed)

        # 2. Gaps check fails if we override grade to pass
        peer_review_data["overall_grade"] = "A"
        is_valid, checks_failed, reason = run_deterministic_verify_checks(
            "peer_review", peer_review_data, self.config, "topic", "item_id", self.fixture_dir
        )
        self.assertFalse(is_valid)
        self.assertIn("peer_review_unresolved_gaps", checks_failed)

    @patch.dict(os.environ, {"INJECT_TOPIC_DRIFT": "1"})
    def test_inject_topic_drift_hook(self):
        from loop.storm_stages import run_stage_article
        from loop.storm_verify import run_deterministic_verify_checks
        import shutil
        
        run_id = "test_drift"
        topic_slug = "test_topic"
        target_dir = f"artifacts/raw/{run_id}/{topic_slug}"
        os.makedirs(target_dir, exist_ok=True)
        self.addCleanup(shutil.rmtree, f"artifacts/raw/{run_id}", ignore_errors=True)
        
        # Setup dummy files in target_dir representing output_dir
        with open(os.path.join(target_dir, "research_briefing.json"), "w") as f:
            json.dump({
                "key_findings": [
                    {"finding": "EV battery cell chemistry must decline to $100/kWh for mass parity in loop engineering transition.", "supporting_evidence": "Evidence"}
                ],
                "actionable_insights": []
            }, f)
        with open(os.path.join(target_dir, "contradiction_map.json"), "w") as f:
            json.dump({"clashes": []}, f)
        with open(os.path.join(target_dir, "outline.json"), "w") as f:
            json.dump({"sections": []}, f)
        
        # Write storm_gen_article.txt so mock_storm doesn't run live LLM
        with open(os.path.join(target_dir, "storm_gen_article.txt"), "w") as f:
            f.write("A good article content.")
            
        config = {
            "run_id": run_id,
            "mock_storm": False,
            "nav_toor": {
                "min_word_count": 5,
                "required_perspectives": [{"id": "pizza", "label": "pizza"}],
                "fidelity": {
                    "article_mode": "storm_only",
                    "force_storm_regen_on_drift": False,
                    "synthesis_term_overlap_min": 0.3,
                    "contradiction_min_reflected": 0
                }
            }
        }
        
        def mock_call_llm(prompt, config, use_planner=False):
            if "pizza" in prompt:
                return json.dumps({
                    "title": "Drifted Article",
                    "sections": [
                        {"title": "Pizza History", "content": "This is a completely unrelated essay about cooking pizza."}
                    ],
                    "citation_references": {},
                    "word_count_min": 500
                })
            return json.dumps({
                "title": "Clean Article",
                "sections": [
                    {"title": "Intro", "content": "This covers practitioners and academics."}
                ],
                "citation_references": {},
                "word_count_min": 500
            })
            
        with patch("loop.storm_stages.sync_storm_files"), \
             patch("loop.storm_stages.call_llm", side_effect=mock_call_llm):
            # Run on attempt 0 (should activate hook and replace with off-topic content)
            res = run_stage_article("test topic", 0, None, config)
            with open(res["artifact_paths"][1], "r") as f:
                content_json = json.load(f)
            
            # Check that it got replaced with pizza content
            is_valid, checks_failed, reason = run_deterministic_verify_checks(
                "article", content_json, config, "test topic", "item_id", target_dir
            )
            self.assertFalse(is_valid)
            self.assertIn("semantic_drift", checks_failed)






