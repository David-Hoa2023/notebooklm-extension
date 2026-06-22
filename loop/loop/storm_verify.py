import os
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from openai import OpenAI

from loop.utils import extract_json
from loop.feeds import batch_fetch_sources
from loop.storm_paths import to_topic_slug

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
            
    elif stage == "peer_review":
        confidence = raw_data.get("overall_confidence", 8)
        min_conf = nav_toor.get("peer_review_min_confidence", 7)
        if confidence < min_conf:
            return False, ["low_confidence"], f"Peer review confidence {confidence} is below required {min_conf}."

        missing_flagged = raw_data.get("missing_perspectives", [])
        # Load upstream perspectives to see if they actually exist
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
    Performs deterministic mock validation logic.
    """
    logger.info(f"🎭 [Mock Verifier] Checking {item_id}...")
    
    nav_toor = config.get("nav_toor", {})
    
    if stage == "perspectives":
        perspectives = raw_data.get("perspectives", [])
        ids = {p.get("id") for p in perspectives}
        req_list = nav_toor.get("required_perspectives", [])
        required = {p.get("id") for p in req_list} if req_list else {"practitioner", "academic", "skeptic", "economist", "historian"}
        
        # Check adversarial hook
        inject_missing = os.environ.get("INJECT_MISSING_PERSPECTIVE")
        if inject_missing == "historian" and "historian" not in ids and attempt == 0:
            return False, ["missing_perspective"], "Historian perspective is missing from scans (attempt 0)."
            
        missing = required - ids
        if missing:
            return False, ["missing_perspective"], f"Missing perspectives: {list(missing)}"
            
        # Check sources are non-empty
        for p in perspectives:
            if not p.get("sources"):
                return False, ["missing_sources"], f"Perspective '{p.get('id')}' has no sources."

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
            
        has_depth = check_depth(sections, 1)
        if not has_depth:
            return False, ["insufficient_depth"], f"Outline lacks required depth of {min_depth}."

    elif stage == "synthesis":
        findings = raw_data.get("key_findings", [])
        min_findings = nav_toor.get("synthesis_min_findings", 5)
        if len(findings) < min_findings:
            return False, ["insufficient_findings"], f"Synthesis requires >={min_findings} findings, got {len(findings)}"

    elif stage == "article":
        # Check citations URLs
        citations = raw_data.get("citation_references", {})
        
        # Check bad citation adversarial env var
        if os.environ.get("INJECT_BAD_CITATION") == "1" and attempt == 0:
            return False, ["citation_unreachable"], "Injected bad citation detected at verify stage (attempt 0)."
            
        for key, url in citations.items():
            if "dead_link" in url:
                return False, ["citation_unreachable"], f"Dead citation URL detected: {url}"
                
        # Check word count
        total_words = 0
        for s in raw_data.get("sections", []):
            total_words += len(s.get("content", "").split())
        word_count_min = nav_toor.get("min_word_count", 500)
        if total_words < word_count_min:
            return False, ["insufficient_word_count"], f"Word count {total_words} is below {word_count_min}."

    elif stage == "peer_review":
        confidence = raw_data.get("overall_confidence", 8)
        min_conf = nav_toor.get("peer_review_min_confidence", 7)
        if confidence < min_conf:
            return False, ["low_confidence"], f"Peer review confidence {confidence} is below required {min_conf}."

    return True, [], None
