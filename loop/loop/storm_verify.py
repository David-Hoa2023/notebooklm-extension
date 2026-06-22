import os
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from openai import OpenAI

from loop.utils import extract_json
from loop.feeds import batch_fetch_sources
from loop.storm_paths import to_topic_slug
from loop.storm_fidelity import (
    get_fidelity_config,
    extract_article_text,
    count_perspective_mentions,
    citation_upstream_ratio,
    synthesis_term_overlap,
    contradictions_reflected,
    is_blocked_domain,
    grade_at_least,
    build_allowed_citation_urls
)

logger = logging.getLogger("loop.storm_verify")

def load_verify_prompt_template(stage: str) -> str:
    path = os.path.join("prompts", "storm", f"verify_{stage}.md").replace("\\", "/")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Verify template not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def call_verifier_llm(prompt: str, config: Dict[str, Any]) -> str:
    roles = config.get("roles", {})
    model = roles.get("planner_verifier", "z-ai/glm-5.2")
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set.")
        
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a verification gate. Output ONLY a valid JSON array matching the requested schema, no conversational text or code block fences."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=1000
    )
    return response.choices[0].message.content or ""

def run_deterministic_verify_checks(stage: str, raw_data: Dict[str, Any], config: Dict[str, Any], topic: str, item_id: str, output_dir: str) -> Tuple[Optional[bool], List[str], Optional[str]]:
    """
    Runs fast, local deterministic verification checks for each stage before invoking LLMs.
    Returns (False, checks_failed, reason) if checks fail, or (None, [], None) if checks pass
    (meaning we should proceed to the LLM verifier).
    """
    nav_toor = config.get("nav_toor", {})
    
    if stage == "perspectives":
        perspectives = raw_data.get("perspectives", [])
        ids = {p.get("id") for p in perspectives}
        req_list = nav_toor.get("required_perspectives", [])
        required = {p.get("id") for p in req_list} if req_list else {"practitioner", "academic", "skeptic", "economist", "historian"}
        
        missing = required - ids
        if missing:
            return False, ["missing_perspective"], f"Missing required perspectives: {list(missing)}"
            
        for p in perspectives:
            if not p.get("sources"):
                return False, ["missing_sources"], f"Perspective '{p.get('id')}' has empty sources."
                
    elif stage == "contradictions":
        clashes = raw_data.get("clashes", [])
        min_clashes = nav_toor.get("contradiction_map_min_clashes", 3)
        if len(clashes) < min_clashes:
            return False, ["insufficient_clashes"], f"Required at least {min_clashes} clashes, got {len(clashes)}"
            
    elif stage == "outline":
        sections = raw_data.get("sections", [])
        min_depth = nav_toor.get("min_outline_depth", 2)
        
        def check_depth(sec_list, current_depth):
            if current_depth >= min_depth:
                return True
            for s in sec_list:
                if check_depth(s.get("subsections", []), current_depth + 1):
                    return True
            return False
            
        if not check_depth(sections, 1):
            return False, ["insufficient_depth"], f"Outline lacks required depth of {min_depth}."
            
    elif stage == "synthesis":
        findings = raw_data.get("key_findings", [])
        min_findings = nav_toor.get("synthesis_min_findings", 5)
        if len(findings) < min_findings:
            return False, ["insufficient_findings"], f"Synthesis requires at least {min_findings} findings, got {len(findings)}"
            
    elif stage == "article":
        fidelity_cfg = get_fidelity_config(config)
        
        # 1. Deterministic Word Count check
        total_words = 0
        for s in raw_data.get("sections", []):
            total_words += len(s.get("content", "").split())
        word_count_min = nav_toor.get("min_word_count", 500)
        if total_words < word_count_min:
            return False, ["insufficient_word_count"], f"Word count {total_words} is below minimum requirement of {word_count_min}."
            
        # 2. Deterministic Citation references mapping check
        citations = raw_data.get("citation_references", {})
        all_cited = set()
        import re
        for s in raw_data.get("sections", []):
            for match in re.findall(r"\[(\d+)\]", s.get("content", "")):
                all_cited.add(int(match))
        for idx in all_cited:
            key = f"[{idx}]"
            if key not in citations and str(idx) not in citations:
                return False, ["missing_citation_ref"], f"Citation index {key} used in text but not found in citation_references."
                
        # UCF-020: Deterministic check for all required perspectives present
        article_text = extract_article_text(raw_data)
        required_list = nav_toor.get("required_perspectives", [])
        required = [p for p in required_list] if required_list else [
            {"id": "practitioner", "label": "Practitioner"},
            {"id": "academic", "label": "Academic"},
            {"id": "skeptic", "label": "Skeptic"},
            {"id": "economist", "label": "Economist"},
            {"id": "historian", "label": "Historian"}
        ]
        mentions = count_perspective_mentions(article_text, required)
        missing_perspectives = [p.get("id") if isinstance(p, dict) else p for p, count in mentions.items() if count == 0]
        if missing_perspectives:
            return False, ["missing_perspective_in_article"], f"The article content failed to represent these required perspectives: {missing_perspectives}"
            
        # UCF-021: Deterministic check for citation upstream URL ratio
        upstream_urls = build_allowed_citation_urls(output_dir)
        if upstream_urls:
            ratio = citation_upstream_ratio(citations, upstream_urls)
            min_ratio = fidelity_cfg.get("citation_upstream_min_ratio", 0.5)
            if ratio < min_ratio:
                return False, ["low_upstream_citation_ratio"], f"Only {ratio:.2f} of citations match upstream sources (minimum required: {min_ratio})."
                
        # UCF-022: Deterministic check for blocklisted low-value domains
        if not fidelity_cfg.get("allow_blocked_domains", False):
            blocked_list = fidelity_cfg.get("blocked_citation_domains", [])
            for key, url in citations.items():
                if is_blocked_domain(url, blocked_list):
                    return False, ["blocked_citation_domain"], f"Citation {key} ({url}) belongs to a blocked dictionary or reference domain."
                    
        # UCF-023: Deterministic check for synthesis term overlap (semantic drift)
        briefing_path = os.path.join(output_dir, "research_briefing.json").replace("\\", "/")
        if os.path.exists(briefing_path):
            try:
                with open(briefing_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    overlap = synthesis_term_overlap(s_data, article_text)
                    min_overlap = fidelity_cfg.get("synthesis_term_overlap_min", 0.3)
                    if overlap < min_overlap:
                        return False, ["semantic_drift"], f"Article semantic overlap with synthesis briefing is {overlap:.2f} (below minimum required: {min_overlap})."
            except Exception as e:
                logger.error(f"Error loading research_briefing.json for term overlap check: {e}")
                
        # UCF-024: Deterministic check for contradictions map reflected in article
        contradictions_path = os.path.join(output_dir, "contradiction_map.json").replace("\\", "/")
        if os.path.exists(contradictions_path):
            try:
                with open(contradictions_path, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                    clashes_reflected = contradictions_reflected(c_data, article_text)
                    min_reflected = fidelity_cfg.get("contradiction_min_reflected", 2)
                    if clashes_reflected < min_reflected:
                        return False, ["contradictions_not_reflected"], f"Article reflected only {clashes_reflected} clashes from the contradictions map (minimum required: {min_reflected})."
            except Exception as e:
                logger.error(f"Error loading contradiction_map.json for checks: {e}")
            
    elif stage == "peer_review":
        fidelity_cfg = get_fidelity_config(config)
        
        confidence = raw_data.get("overall_confidence", 8)
        min_conf = nav_toor.get("peer_review_min_confidence", 7)
        if confidence < min_conf:
            return False, ["low_confidence"], f"Peer review confidence {confidence} is below required {min_conf}."

        # UCF-026: Deterministic check for minimum grade threshold
        overall_grade = raw_data.get("overall_grade", "A")
        min_grade = fidelity_cfg.get("peer_review_min_grade", "B-")
        if not grade_at_least(overall_grade, min_grade):
            return False, ["grade_below_threshold"], f"Peer review overall grade '{overall_grade}' is below the required '{min_grade}'."

        missing_flagged = raw_data.get("missing_perspectives", [])
        
        # 1. Existing check: Incorrect missing perspectives flagged
        p_path = os.path.join(output_dir, "perspectives.json").replace("\\", "/")
        if os.path.exists(p_path) and missing_flagged:
            try:
                with open(p_path, "r", encoding="utf-8") as f:
                    p_data = json.load(f)
                    existing_ids = {p.get("id") for p in p_data.get("perspectives", [])}
                    incorrectly_flagged = [p_id for p_id in missing_flagged if p_id in existing_ids]
                    if incorrectly_flagged:
                        return False, ["incorrect_missing_perspectives"], f"The peer review incorrectly identified these perspectives as missing, but they are present in the upstream scan: {incorrectly_flagged}"
            except Exception as e:
                logger.error(f"Error loading perspectives.json for peer review check: {e}")
                
        # UCF-025: Peer review gate fails when missing_perspectives is non-empty and indeed absent
        if missing_flagged and fidelity_cfg.get("peer_review_fail_on_missing_perspectives", True):
            polished_txt_path = os.path.join(output_dir, "storm_gen_article_polished.txt").replace("\\", "/")
            article_text = ""
            if os.path.exists(polished_txt_path):
                try:
                    with open(polished_txt_path, "r", encoding="utf-8") as f:
                        article_text = f.read()
                except Exception:
                    pass
            if not article_text:
                article_json_path = os.path.join(output_dir, "article.json").replace("\\", "/")
                if os.path.exists(article_json_path):
                    try:
                        with open(article_json_path, "r", encoding="utf-8") as f:
                            article_text = extract_article_text(json.load(f))
                    except Exception:
                        pass
            
            required_list = nav_toor.get("required_perspectives", [])
            required = [p for p in required_list] if required_list else [
                {"id": "practitioner", "label": "Practitioner"},
                {"id": "academic", "label": "Academic"},
                {"id": "skeptic", "label": "Skeptic"},
                {"id": "economist", "label": "Economist"},
                {"id": "historian", "label": "Historian"}
            ]
            
            genuine_gaps = []
            for p_id in missing_flagged:
                p_match = next((p for p in required if p.get("id") == p_id), None)
                if p_match:
                    p_mentions = count_perspective_mentions(article_text, [p_match])
                    if p_mentions.get(p_id, 0) == 0:
                        genuine_gaps.append(p_id)
                else:
                    p_mentions = count_perspective_mentions(article_text, [p_id])
                    if p_mentions.get(p_id, 0) == 0:
                        genuine_gaps.append(p_id)
                        
            if genuine_gaps:
                return False, ["peer_review_unresolved_gaps"], f"The peer review flagged these perspectives as missing, and they are indeed absent from the article content: {genuine_gaps}"
                
    return None, [], None

def run_storm_verifier(stage: str, raw_data: Dict[str, Any], config: Dict[str, Any], topic: str, item_id: str, verifier_model: str, attempt: int = 0) -> Tuple[bool, List[str], Optional[str]]:
    """
    Executes verify gate checks (both deterministic and LLM-adversarial) for a stage.
    """
    if config.get("mock_storm"):
        return run_mock_storm_verifier(stage, raw_data, config, topic, item_id, attempt)

    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")

    # 0. Deterministic Verification Pre-checks to cut retries
    is_valid, checks_failed, reason = run_deterministic_verify_checks(
        stage, raw_data, config, topic, item_id, output_dir
    )
    if is_valid is False:
        logger.info(f"⚠️ Deterministic verification check FAILED: {reason}")
        return False, checks_failed, reason

    logger.info(f"Running real verifier gate for {item_id} (stage: {stage})")
    
    # 1. Deterministic URL check for article stage
    if stage == "article":
        citations = raw_data.get("citation_references", {})
        urls = list(citations.values())
        cache_dir = os.path.join("artifacts", "cache", config["run_id"]).replace("\\", "/")
        fetched = batch_fetch_sources(urls, cache_dir)
        
        # Check adversarial bad citation hook or actual failures
        for url, fetch_res in fetched.items():
            if fetch_res.get("status_code") != 200 or (os.environ.get("INJECT_BAD_CITATION") == "1" and attempt == 0):
                return False, ["citation_unreachable"], f"Citation URL {url} is unreachable (status: {fetch_res.get('status_code')})."

    # 2. Gather upstream context
    upstream_data = ""
    
    stages_order = ["perspectives", "contradictions", "outline", "synthesis", "article", "peer_review"]
    current_idx = stages_order.index(stage)
    
    # Collect data from preceding stages as context
    preceding_data = {}
    for prev_stage in stages_order[:current_idx]:
        prev_filename = f"{prev_stage}.json" if prev_stage != "contradictions" else "contradiction_map.json"
        if prev_stage == "outline":
            prev_filename = "outline.json"
        elif prev_stage == "synthesis":
            prev_filename = "research_briefing.json"
            
        prev_path = os.path.join(output_dir, prev_filename).replace("\\", "/")
        if os.path.exists(prev_path):
            with open(prev_path, "r", encoding="utf-8") as f:
                preceding_data[prev_stage] = json.load(f)
                
    upstream_data = json.dumps(preceding_data, indent=2)

    # 3. Call LLM Verifier
    template = load_verify_prompt_template(stage)
    
    # Sub fields for verify templates
    # verify_article requires fetched_sources separately
    fetched_sources_str = ""
    if stage == "article":
        citations = raw_data.get("citation_references", {})
        urls = list(citations.values())
        cache_dir = os.path.join("artifacts", "cache", config["run_id"]).replace("\\", "/")
        fetched = batch_fetch_sources(urls, cache_dir)
        fetched_sources_str = json.dumps(fetched, indent=2)
        
    prompt = (
        template.replace("{topic}", topic)
        .replace("{item_id}", item_id)
        .replace("{raw_data}", json.dumps(raw_data, indent=2))
        .replace("{upstream_data}", upstream_data)
        .replace("{fetched_sources}", fetched_sources_str)
    )
    
    try:
        llm_output = call_verifier_llm(prompt, config)
        parsed = json.loads(extract_json(llm_output))
        result = next((r for r in parsed if r.get("item_id") == item_id), None)
        if not result:
            return False, ["verifier_parse_error"], f"Verifier returned no details for item {item_id}."
            
        if result.get("status") == "FAIL":
            return False, result.get("checks_failed", []), result.get("rejection_reason")
            
        return True, [], None
        
    except Exception as e:
        logger.error(f"Verifier crashed for {item_id}: {e}")
        return False, ["verifier_crash"], str(e)


def run_mock_storm_verifier(stage: str, raw_data: Dict[str, Any], config: Dict[str, Any], topic: str, item_id: str, attempt: int = 0) -> Tuple[bool, List[str], Optional[str]]:
    """
    Performs deterministic mock validation logic, enforcing the full content fidelity checks.
    """
    logger.info(f"🎭 [Mock Verifier] Checking {item_id}...")
    
    output_dir = os.path.join("artifacts", "raw", config.get("run_id", "mock"), to_topic_slug(topic)).replace("\\", "/")
    
    # Run deterministic verify checks first
    is_valid, checks_failed, reason = run_deterministic_verify_checks(
        stage, raw_data, config, topic, item_id, output_dir
    )
    if is_valid is False:
        logger.info(f"🎭 [Mock Verifier] Deterministic check FAILED: {reason}")
        return False, checks_failed, reason

    # Fall back to remaining mock-specific checks/adversarial flags if any
    nav_toor = config.get("nav_toor", {})
    if stage == "perspectives":
        perspectives = raw_data.get("perspectives", [])
        ids = {p.get("id") for p in perspectives}
        # Check adversarial hook
        inject_missing = os.environ.get("INJECT_MISSING_PERSPECTIVE")
        if inject_missing == "historian" and "historian" not in ids and attempt == 0:
            return False, ["missing_perspective"], "Historian perspective is missing from scans (attempt 0)."
            
    elif stage == "article":
        # Check bad citation adversarial env var
        if os.environ.get("INJECT_BAD_CITATION") == "1" and attempt == 0:
            return False, ["citation_unreachable"], "Injected bad citation detected at verify stage (attempt 0)."
            
        citations = raw_data.get("citation_references", {})
        for key, url in citations.items():
            if "dead_link" in url:
                return False, ["citation_unreachable"], f"Dead citation URL detected: {url}"

    return True, [], None
