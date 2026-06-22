import os
import json
import logging
import re
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional

logger = logging.getLogger("loop.storm_fidelity")

DEFAULT_FIDELITY_CONFIG = {
    "article_mode": "briefing_first",
    "article_min_perspective_mentions": 5,
    "citation_upstream_min_ratio": 0.5,
    "synthesis_term_overlap_min": 0.3,
    "contradiction_min_reflected": 2,
    "blocked_citation_domains": [
        "dictionary.cambridge.org",
        "merriam-webster.com",
        "login.adaptiveinsights.com"
    ],
    "peer_review_min_grade": "B-",
    "peer_review_fail_on_missing_perspectives": True,
    "article_max_attempts_before_escalate": 10,
    "force_storm_regen_on_drift": True,
    "allow_extra_citations": False,
    "allow_blocked_domains": False
}

def get_fidelity_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieves the nav_toor.fidelity configuration block and merges it with defaults.
    """
    nav_toor = config.get("nav_toor", {})
    fidelity = nav_toor.get("fidelity", {})
    merged = {}
    for key, default in DEFAULT_FIDELITY_CONFIG.items():
        merged[key] = fidelity.get(key, default)
    return merged

def extract_article_text(article_json: Dict[str, Any]) -> str:
    """
    Extracts all header, section, and subsection text from the article schema JSON.
    """
    text_parts = []
    
    # Extract title
    title = article_json.get("title", "")
    if title:
        text_parts.append(title)
        
    # Extract sections recursively
    def extract_sections(sections):
        for sec in sections:
            text_parts.append(sec.get("title", ""))
            text_parts.append(sec.get("content", ""))
            if "subsections" in sec:
                extract_sections(sec["subsections"])
                
    extract_sections(article_json.get("sections", []))
    return "\n".join(text_parts)

def count_perspective_mentions(text: str, required_perspectives: List[Any]) -> Dict[str, int]:
    """
    Counts mentions of required perspectives in the article text.
    required_perspectives can be a list of strings or a list of dicts with {"id": ..., "label": ...}.
    """
    text_lower = text.lower()
    counts = {}
    for item in required_perspectives:
        if isinstance(item, dict):
            p_id = item.get("id", "")
            label = item.get("label", "")
            
            # Count matches of ID
            id_count = len(re.findall(rf"\b{re.escape(p_id.lower())}\b", text_lower))
            # Count matches of label
            label_count = 0
            if label:
                label_count = len(re.findall(rf"\b{re.escape(label.lower())}\b", text_lower))
                
            counts[p_id] = max(id_count, label_count)
        else:
            p_str = str(item).lower()
            counts[p_str] = len(re.findall(rf"\b{re.escape(p_str)}\b", text_lower))
    return counts

def normalize_url(url: str) -> str:
    """
    Normalizes a URL to verify presence in upstream lists ignoring schemes, www. and trailing slashes.
    """
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = parsed.path.rstrip("/")
        # Keep query parameters if they specify article identifier, otherwise drop
        query = parsed.query
        if query:
            return f"{netloc}{path}?{query}"
        return f"{netloc}{path}"
    except Exception:
        return url.strip().lower()

def citation_upstream_ratio(citation_refs: Dict[str, str], upstream_urls: List[str]) -> float:
    """
    Computes ratio of citation_references URLs that match the upstream collected URLs.
    """
    if not citation_refs:
        return 0.0
    normalized_upstream = {normalize_url(u) for u in upstream_urls if u}
    matched = 0
    total = 0
    for key, url in citation_refs.items():
        if url:
            total += 1
            if normalize_url(url) in normalized_upstream:
                matched += 1
    return matched / total if total > 0 else 0.0

STOPWORDS = {
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'this', 'these', 'those', 
    'are', 'was', 'were', 'been', 'have', 'has', 'had', 'will', 'would', 'should',
    'can', 'could', 'about', 'their', 'there', 'what', 'which', 'who', 'how', 'why',
    'not', 'but', 'into', 'than', 'then', 'them', 'they', 'our', 'your', 'its', 'out',
    'their', 'about'
}

def get_words(text: str) -> set:
    """
    Splits text into lowercase alphanumeric words, filtering out stopwords.
    """
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}

def synthesis_term_overlap(synthesis_json: Dict[str, Any], article_text: str) -> float:
    """
    Computes Jaccard-like term overlap ratio between synthesis briefing text and article text.
    """
    briefing_parts = []
    # Add summary
    summary = synthesis_json.get("summary", "")
    if summary:
        briefing_parts.append(summary)
        
    # Add key findings
    for finding in synthesis_json.get("key_findings", []):
        briefing_parts.append(finding.get("finding", ""))
        briefing_parts.append(finding.get("supporting_evidence", ""))
        
    # Add hidden connections
    for conn in synthesis_json.get("hidden_connections", []):
        if conn:
            briefing_parts.append(conn)
            
    # Add actionable insight (could be string, dict, or list)
    act_insight = synthesis_json.get("actionable_insight", "")
    if isinstance(act_insight, list):
        for item in act_insight:
            if isinstance(item, dict):
                briefing_parts.append(item.get("insight", ""))
                briefing_parts.append(item.get("implementation_strategy", ""))
            else:
                briefing_parts.append(str(item))
    elif isinstance(act_insight, dict):
        briefing_parts.append(act_insight.get("insight", ""))
        briefing_parts.append(act_insight.get("implementation_strategy", ""))
    else:
        if act_insight:
            briefing_parts.append(str(act_insight))

    # Also support old key "actionable_insights" list
    for insight in synthesis_json.get("actionable_insights", []):
        briefing_parts.append(insight.get("insight", ""))
        briefing_parts.append(insight.get("implementation_strategy", ""))
        
    briefing_text = " ".join(briefing_parts)
    briefing_words = get_words(briefing_text)
    if not briefing_words:
        return 1.0
        
    article_words = get_words(article_text)
    matched_words = briefing_words.intersection(article_words)
    return len(matched_words) / len(briefing_words)

def contradictions_reflected(contradiction_map: Dict[str, Any], article_text: str) -> int:
    """
    Checks how many contradiction map clashes are reflected in the article text.
    A clash is considered reflected if a minimal subset of its keywords appear.
    """
    matched = 0
    clashes = contradiction_map.get("clashes", [])
    article_words = get_words(article_text)
    
    for clash in clashes:
        clash_text = (
            clash.get("description", "") + " " + 
            clash.get("difference_summary", "") + " " +
            clash.get("perspective_a_view", "") + " " +
            clash.get("perspective_b_view", "")
        )
        clash_words = get_words(clash_text)
        if clash_words:
            matched_words = clash_words.intersection(article_words)
            ratio = len(matched_words) / len(clash_words)
            if ratio >= 0.15:
                matched += 1
    return matched

def is_blocked_domain(url: str, blocked_list: List[str]) -> bool:
    """
    Checks if a URL belongs to a blocked domain from the blocked list.
    """
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        for blocked in blocked_list:
            if blocked.lower() in netloc:
                return True
        return False
    except Exception:
        return False

GRADE_MAP = {
    "A+": 12, "A": 11, "A-": 10,
    "B+": 9, "B": 8, "B-": 7,
    "C+": 6, "C": 5, "C-": 4,
    "D+": 3, "D": 2, "D-": 1,
    "F": 0
}

def grade_at_least(grade: str, min_grade: str) -> bool:
    """
    Returns True if overall_grade is at least min_grade.
    """
    g_val = GRADE_MAP.get(grade.upper(), 0)
    m_val = GRADE_MAP.get(min_grade.upper(), 7)  # default B- is 7
    return g_val >= m_val

def build_allowed_citation_urls(output_dir: str) -> List[str]:
    """
    Gathers the union of source URLs from perspectives.json and research_briefing.json.
    """
    urls = []
    
    # Load perspectives
    pers_path = os.path.join(output_dir, "perspectives.json").replace("\\", "/")
    if os.path.exists(pers_path):
        try:
            with open(pers_path, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                for p in p_data.get("perspectives", []):
                    for src in p.get("sources", []):
                        if src and src not in urls:
                            urls.append(src)
        except Exception:
            pass
            
    # Load synthesis briefing
    synth_path = os.path.join(output_dir, "research_briefing.json").replace("\\", "/")
    if os.path.exists(synth_path):
        try:
            with open(synth_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                for finding in s_data.get("key_findings", []):
                    refs = finding.get("sources", [])
                    if not refs:
                        refs = finding.get("source_refs", [])
                    for ref in refs:
                        if ref and ref not in urls:
                            urls.append(ref)
        except Exception:
            pass
            
    return urls
