import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from openai import OpenAI
from loop.utils import extract_json, clean_electrical_analogy
from loop.storm_adapter import build_storm_runner, HAS_STORM
from loop.storm_fidelity import get_fidelity_config, build_allowed_citation_urls
from loop.storm_paths import to_topic_slug, get_stage_output_filename, get_stage_normalized_filename

logger = logging.getLogger("loop.storm_stages")

def load_prompt_template(name: str) -> str:
    """
    Loads prompt template from prompts/storm/
    """
    path = os.path.join("prompts", "storm", name).replace("\\", "/")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt template not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def sync_storm_files(topic: str, config: Dict[str, Any]):
    """
    Finds the directory where STORM wrote files, and copies them to the
    orchestrator's canonical to_topic_slug(topic) output directory to keep them synced.
    """
    import shutil
    run_id = config.get("run_id", "")
    canonical_dir = os.path.join("artifacts", "raw", run_id, to_topic_slug(topic)).replace("\\", "/")
    os.makedirs(canonical_dir, exist_ok=True)
    
    # Try to find the directory where STORM actually wrote files
    base_dir = os.path.join("artifacts", "raw", run_id).replace("\\", "/")
    if not os.path.exists(base_dir):
        return
        
    expected_slug = to_topic_slug(topic).replace("_", "").lower()
    storm_dir = None
    for entry in os.listdir(base_dir):
        entry_path = os.path.join(base_dir, entry).replace("\\", "/")
        if os.path.isdir(entry_path):
            normalized_entry = entry.lower().replace("-", "").replace("_", "")
            if normalized_entry == expected_slug and entry_path != canonical_dir:
                storm_dir = entry_path
                break
                
    if storm_dir and os.path.exists(storm_dir):
        logger.info(f"Syncing files from STORM output dir '{storm_dir}' to canonical dir '{canonical_dir}'")
        for file_name in os.listdir(storm_dir):
            src_file = os.path.join(storm_dir, file_name)
            if os.path.isfile(src_file):
                dst_file = os.path.join(canonical_dir, file_name)
                try:
                    shutil.copy2(src_file, dst_file)
                except Exception as e:
                    logger.warning(f"Failed to copy '{src_file}' to '{dst_file}': {e}")


def call_llm(prompt: str, config: Dict[str, Any], use_planner: bool = False) -> str:
    """
    Calls the configured LLM (planner_verifier or executor_swarm) via OpenRouter.
    """
    roles = config.get("roles", {})
    model = roles.get("planner_verifier" if use_planner else "executor_swarm", "z-ai/glm-5.2")
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set.")
        
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a research assistant. Output ONLY valid JSON array/object matching the requested schema, without markdown formatting or code block fences."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=8000
    )
    return response.choices[0].message.content or ""


def call_llm_and_parse_json(prompt: str, config: Dict[str, Any], schema_name: str, use_planner: bool = False) -> Dict[str, Any]:
    """
    Calls the LLM and parses JSON output with automatic repair retry on failure.
    """
    max_parse_retries = 3
    last_error = None
    llm_output = ""
    for r_idx in range(max_parse_retries):
        try:
            if r_idx == 0:
                llm_output = call_llm(prompt, config, use_planner=use_planner)
            else:
                logger.info(f"🔧 Attempting syntax repair for {schema_name} JSON (attempt {r_idx+1})...")
                repair_prompt = f"""
You are a JSON syntax repair assistant. The previous attempt to generate a valid JSON representing the {schema_name} failed with this JSONDecodeError:
{last_error}

Here is the raw text that failed parsing:
{llm_output}

Fix the syntax errors in the JSON (such as unescaped double quotes inside strings, missing commas, unescaped backslashes, or mismatched brackets) and return ONLY the corrected, valid JSON conforming to the requested schema.
Do NOT wrap your response in markdown code blocks or write conversational text. Return ONLY the raw valid JSON.
"""
                llm_output = call_llm(repair_prompt, config, use_planner=use_planner)
            
            parsed_json = json.loads(extract_json(llm_output))
            return parsed_json
        except Exception as e:
            logger.warning(f"[{schema_name}] JSON parse attempt {r_idx+1} failed: {e}")
            last_error = str(e)
            
    raise ValueError(f"Failed to generate valid JSON for {schema_name} after {max_parse_retries} attempts. Last error: {last_error}")


# ==============================================================================
# STB-010: Perspectives Stage (STORM research + P1 enrichment)
# ==============================================================================
def run_stage_perspectives(topic: str, attempt: int, last_rejection: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")
    os.makedirs(output_dir, exist_ok=True)
    
    if config.get("mock_storm"):
        from loop.storm_mock import mock_stage_perspectives
        return mock_stage_perspectives(topic, attempt, last_rejection, output_dir)

    logger.info(f"Running real perspectives stage for topic: {topic} (attempt {attempt})")
    
    # 1. Run STORM Research simulation (stores conversation_log.json, raw_search_results.json, url_to_info.json)
    runner = build_storm_runner(config)
    runner.run(topic=topic, do_research=True, do_generate_outline=False, do_generate_article=False, do_polish_article=False)
    runner.post_run()
    sync_storm_files(topic, config)

    
    # 2. Enrich/Post-process into perspectives.json using P1 prompt template
    p1_template = load_prompt_template("p1_multi_perspective_scan.md")
    
    # Check adversarial hook
    missing_perspective = os.environ.get("INJECT_MISSING_PERSPECTIVE")
    if missing_perspective and attempt == 0:
        logger.info(f"Adversarial Hook: Injecting missing perspective: {missing_perspective}")
        p1_template += f"\nNote: Do NOT include the '{missing_perspective}' perspective under any circumstance for attempt 0."
        
    if last_rejection:
        p1_template += f"\nNote: Your previous attempt failed validation for the following reason:\n{last_rejection}\nPlease correct this error."
        
    prompt = p1_template.replace("{topic}", topic)
    parsed_json = call_llm_and_parse_json(prompt, config, "perspectives")
    
    # Save perspectives.json
    norm_path = os.path.join(output_dir, "perspectives.json").replace("\\", "/")
    with open(norm_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
        
    return {
        "artifact_paths": [
            os.path.join(output_dir, "conversation_log.json").replace("\\", "/"),
            norm_path
        ],
        "storm_metadata": runner.summary() if HAS_STORM else {"query_count": 0}
    }

# ==============================================================================
# STB-011: Contradictions Stage (Nav Toor P2)
# ==============================================================================
def run_stage_contradictions(topic: str, attempt: int, last_rejection: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")
    
    if config.get("mock_storm"):
        from loop.storm_mock import mock_stage_contradictions
        return mock_stage_contradictions(topic, attempt, last_rejection, output_dir)

    logger.info(f"Running real contradictions stage for topic: {topic} (attempt {attempt})")
    
    # Load perspectives.json
    perspectives_path = os.path.join(output_dir, "perspectives.json").replace("\\", "/")
    with open(perspectives_path, "r", encoding="utf-8") as f:
        perspectives_data = f.read()
        
    p2_template = load_prompt_template("p2_contradiction_map.md")
    if last_rejection:
        p2_template += f"\nNote: Your previous attempt failed validation:\n{last_rejection}\nPlease correct."
        
    prompt = p2_template.replace("{upstream_data}", perspectives_data)
    parsed_json = call_llm_and_parse_json(prompt, config, "contradictions")
    
    out_path = os.path.join(output_dir, "contradiction_map.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
        
    return {"artifact_paths": [out_path]}

# ==============================================================================
# STB-012: Outline Stage (STORM outline generation)
# ==============================================================================
def run_stage_outline(topic: str, attempt: int, last_rejection: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")
    
    if config.get("mock_storm"):
        from loop.storm_mock import mock_stage_outline
        return mock_stage_outline(topic, attempt, last_rejection, output_dir)

    logger.info(f"Running real outline stage for topic: {topic} (attempt {attempt})")
    
    # Run STORM outline generation
    runner = build_storm_runner(config)
    runner.run(topic=topic, do_research=False, do_generate_outline=True, do_generate_article=False, do_polish_article=False)
    runner.post_run()
    sync_storm_files(topic, config)

    
    # Convert/Normalize outline.txt into outline.json with coverage tags
    outline_txt_path = os.path.join(output_dir, "storm_gen_outline.txt").replace("\\", "/")
    if os.path.exists(outline_txt_path):
        with open(outline_txt_path, "r", encoding="utf-8") as f:
            outline_content = f.read()
    else:
        outline_content = "No outline content."
        
    # We use LLM to parse outline content and add metadata tags
    parser_prompt = f"""
Convert the following outline text into a structured JSON outline matching the OutlineSchema.
Outline Text:
{outline_content}

For each section/subsection, you must add tags in 'perspective_coverage' choosing from: practitioner, academic, skeptic, economist, historian.
Every one of the 5 required perspective IDs must appear in 'perspective_coverage' fields across sections. Ensure depth is at least 2 (use subsections).
Return ONLY a valid JSON object matching OutlineSchema:
{{
  "sections": [
    {{
      "title": "...",
      "description": "...",
      "perspective_coverage": ["practitioner"],
      "contradiction_refs": [0],
      "subsections": [
        ...
      ]
    }}
  ]
}}
"""
    if last_rejection:
        parser_prompt += f"\nNote: The previous outline attempt was rejected: {last_rejection}. Please correct this."
        
    parsed_json = call_llm_and_parse_json(parser_prompt, config, "outline")
    if isinstance(parsed_json, list):
        parsed_json = {"sections": parsed_json}
    
    out_path = os.path.join(output_dir, "outline.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
        
    return {"artifact_paths": [outline_txt_path, out_path]}

# ==============================================================================
# STB-013: Synthesis Stage (Nav Toor P3)
# ==============================================================================
def run_stage_synthesis(topic: str, attempt: int, last_rejection: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")
    
    if config.get("mock_storm"):
        from loop.storm_mock import mock_stage_synthesis
        return mock_stage_synthesis(topic, attempt, last_rejection, output_dir)

    logger.info(f"Running real synthesis stage for topic: {topic} (attempt {attempt})")
    
    # Load upstream: perspectives.json, contradiction_map.json, outline.json
    p_path = os.path.join(output_dir, "perspectives.json").replace("\\", "/")
    c_path = os.path.join(output_dir, "contradiction_map.json").replace("\\", "/")
    o_path = os.path.join(output_dir, "outline.json").replace("\\", "/")
    
    context = {}
    for p, name in [(p_path, "perspectives"), (c_path, "contradictions"), (o_path, "outline")]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                context[name] = json.load(f)
                
    p3_template = load_prompt_template("p3_synthesis.md")
    if last_rejection:
        p3_template += f"\nNote: Previous synthesis attempt failed: {last_rejection}. Please correct."
        
    prompt = p3_template.replace("{upstream_data}", json.dumps(context, indent=2))
    parsed_json = call_llm_and_parse_json(prompt, config, "synthesis")
    
    out_path = os.path.join(output_dir, "research_briefing.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
        
    return {"artifact_paths": [out_path]}

def parse_markdown_article_to_json(article_content: str, topic: str, allowed_urls: List[str]) -> Dict[str, Any]:
    import re
    lines = article_content.split("\n")
    title = topic
    sections = []
    current_section = None
    current_content = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            # Header line
            if current_section is not None:
                current_section["content"] = "\n".join(current_content).strip()
                sections.append(current_section)
            
            # Clean header title
            h_title = re.sub(r"^#+\s*", "", stripped)
            # If it's a top level title (e.g. # Topic Name), update title
            if stripped.startswith("# ") and not sections:
                title = h_title
                current_section = None
                current_content = []
            else:
                current_section = {
                    "title": h_title,
                    "content": "",
                    "citation_indices": [],
                    "perspective_coverage": []
                }
                current_content = []
        else:
            if current_section is not None:
                current_content.append(line)
            elif stripped and not sections:
                # Lead content before any section headers
                current_section = {
                    "title": "Introduction",
                    "content": "",
                    "citation_indices": [],
                    "perspective_coverage": []
                }
                current_content = [line]
                
    if current_section is not None:
        current_section["content"] = "\n".join(current_content).strip()
        sections.append(current_section)
        
    if not sections:
        sections.append({
            "title": "Introduction",
            "content": article_content.strip(),
            "citation_indices": [],
            "perspective_coverage": []
        })
        
    citation_references = {}
    perspectives = ["practitioner", "academic", "skeptic", "economist", "historian"]
    
    for sec in sections:
        matches = re.findall(r"\[(\d+)\]", sec["content"])
        indices = []
        for m in matches:
            idx = int(m)
            indices.append(idx)
            if 0 < idx <= len(allowed_urls):
                url = allowed_urls[idx - 1]
                citation_references[f"[{idx}]"] = url
        sec["citation_indices"] = sorted(list(set(indices)))
        
        cov = []
        text_to_search = (sec["title"] + " " + sec["content"]).lower()
        for p in perspectives:
            if p in text_to_search:
                cov.append(p)
        sec["perspective_coverage"] = cov
        
    return {
        "title": title,
        "sections": sections,
        "citation_references": citation_references,
        "word_count_min": 500
    }

# ==============================================================================
# STB-014: Article Stage (STORM article generation)
# ==============================================================================
def run_stage_article(topic: str, attempt: int, last_rejection: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")
    
    if config.get("mock_storm"):
        from loop.storm_mock import mock_stage_article
        return mock_stage_article(topic, attempt, last_rejection, output_dir)

    logger.info(f"Running real article stage for topic: {topic} (attempt {attempt})")
    
    fidelity_cfg = get_fidelity_config(config)
    article_mode = fidelity_cfg.get("article_mode", "briefing_first")
    if config.get("regen_hint") == "briefing_first":
        article_mode = "briefing_first"
    
    article_txt_path = os.path.join(output_dir, "storm_gen_article.txt").replace("\\", "/")
    
    # UCF-012: Force STORM regen on semantic drift or previous failures
    if last_rejection and fidelity_cfg.get("force_storm_regen_on_drift", True):
        fidelity_keywords = [
            "missing_perspective", "low_upstream_citation", 
            "blocked_citation", "semantic_drift", "contradictions_not_reflected"
        ]
        if any(kw in last_rejection for kw in fidelity_keywords) or attempt > 0:
            logger.info("Fidelity rejection or retry detected; forcing regeneration of storm_gen_article.txt")
            if os.path.exists(article_txt_path):
                try:
                    os.remove(article_txt_path)
                except Exception as e:
                    logger.warning(f"Could not remove old article file: {e}")

    if not os.path.exists(article_txt_path):
        if article_mode == "briefing_first":
            logger.info("Generating article via Briefing-First Mode (p5 prompt template)")
            
            # 1. Load upstream files
            briefing_data = ""
            briefing_path = os.path.join(output_dir, "research_briefing.json").replace("\\", "/")
            if os.path.exists(briefing_path):
                with open(briefing_path, "r", encoding="utf-8") as f:
                    briefing_data = f.read()
                    
            contradictions_data = ""
            contradictions_path = os.path.join(output_dir, "contradiction_map.json").replace("\\", "/")
            if os.path.exists(contradictions_path):
                with open(contradictions_path, "r", encoding="utf-8") as f:
                    contradictions_data = f.read()
                    
            outline_data = ""
            outline_path = os.path.join(output_dir, "outline.json").replace("\\", "/")
            if os.path.exists(outline_path):
                with open(outline_path, "r", encoding="utf-8") as f:
                    outline_data = f.read()
            else:
                outline_txt_path = os.path.join(output_dir, "storm_gen_outline.txt").replace("\\", "/")
                if os.path.exists(outline_txt_path):
                    with open(outline_txt_path, "r", encoding="utf-8") as f:
                        outline_data = f.read()
                        
            # 2. Build allowed citations list
            allowed_urls = build_allowed_citation_urls(output_dir)
            allowed_citations_str = ""
            for idx, url in enumerate(allowed_urls):
                allowed_citations_str += f"[{idx+1}]: {url}\n"
                
            # 3. Load prompt and replace templates
            p5_template = load_prompt_template("p5_article_from_briefing.md")
            prompt = (
                p5_template.replace("{topic}", topic)
                .replace("{upstream_briefing}", briefing_data)
                .replace("{contradictions}", contradictions_data)
                .replace("{outline}", outline_data)
                .replace("{allowed_citations}", allowed_citations_str)
            )
            
            if last_rejection:
                prompt += f"\n\nNote: The previous article was rejected: {last_rejection}. Adjust content to fix these issues."
                
            article_content = call_llm(prompt, config, use_planner=True)
            with open(article_txt_path, "w", encoding="utf-8") as f:
                f.write(article_content)
        else:
            # Run STORM article generation
            runner = build_storm_runner(config)
            runner.run(topic=topic, do_research=False, do_generate_outline=False, do_generate_article=True, do_polish_article=False)
            runner.post_run()
            sync_storm_files(topic, config)

    if not os.path.exists(article_txt_path):
        raise FileNotFoundError(f"STORM article generation did not produce storm_gen_article.txt at {article_txt_path}")

    with open(article_txt_path, "r", encoding="utf-8") as f:
        article_content = f.read()
        
    if os.environ.get("INJECT_TOPIC_DRIFT") == "1" and attempt == 0:
        logger.info("Adversarial Hook: Injecting topic drift for attempt 0")
        article_content = (
            "This is a completely unrelated essay about cooking pizza and the history of tomato sauce. "
            "The practitioner likes baking pizza. The academic researches pizza fermentation. "
            "The skeptic warns about high sodium in pizza dough. The economist analyzes pizza delivery costs. "
            "The historian writes about early Neapolitan pizza makers. "
            "Tomato sauce recipes have evolved. We do not mention EV battery chemistry here. "
            "The practitioner builds pizza ovens. The academic teaches pizza chemistry. "
            "The skeptic hates pineapple toppings. The economist projects cheese market rates. "
            "The historian documents pasta transitions. "
        )
        
    # UCF-011: Restrict/build allowed citations pool and write/merge url_to_info.json
    url_to_info_path = os.path.join(output_dir, "url_to_info.json").replace("\\", "/")
    allowed_urls = build_allowed_citation_urls(output_dir)
    
    if article_mode == "briefing_first" or not os.path.exists(url_to_info_path) or not allowed_urls:
        ref_data = {
            "url_to_unified_index": {url: i + 1 for i, url in enumerate(allowed_urls)},
            "url_to_info": {}
        }
        try:
            with open(url_to_info_path, "w", encoding="utf-8") as f_out:
                json.dump(ref_data, f_out, indent=2)
        except Exception as e:
            logger.error(f"Failed to write allowed url_to_info.json: {e}")

    ref_mapping_str = ""
    if os.path.exists(url_to_info_path):
        try:
            with open(url_to_info_path, "r", encoding="utf-8") as f:
                ref_data = json.load(f)
                index_to_url = {v: k for k, v in ref_data.get("url_to_unified_index", {}).items()}
                if index_to_url:
                    ref_mapping_str = "You MUST map the numeric citations in the text to these exact URLs in 'citation_references':\n"
                    for idx, url in sorted(index_to_url.items()):
                        ref_mapping_str += f"[{idx}]: {url}\n"
        except Exception as e:
            logger.error(f"Failed to load url_to_info.json: {e}")

    # We parse to article.json
    parser_prompt = f"""
Convert the following article text into a structured JSON matching ArticleSchema.
Article Content:
{article_content}

{ref_mapping_str}

CRITICAL INSTRUCTIONS:
1. You MUST preserve the full, detailed text of each section and subsection from the original Article Content. Do NOT summarize, shorten, truncate, or omit any paragraphs or detailed explanations.
2. Clean up any illogical or irrelevant claims in the article content. Specifically, remove the parallel drawing to electrical current intensity or the symbol 'I' (from Wikipedia [2]), and instead describe 'current' purely as the active, present-time stream or flow of information and feedback processed in loop engineering.
3. The final word count of all sections combined must be at least 500 words, preserving the full richness of the original text.
4. Ensure all citation references are correctly mapped in 'citation_references' using the provided mapping.
5. You MUST escape all double quotes inside string fields (like 'content' and 'title') using a backslash. E.g., write \"current\" instead of "current". Nested double quotes MUST be escaped to avoid breaking the JSON format.

Return ONLY valid JSON matching ArticleSchema:
{{
  "title": "...",
  "sections": [
    {{
      "title": "...",
      "content": "...",
      "citation_indices": [1],
      "perspective_coverage": ["practitioner", "academic"]
    }}
  ],
  "citation_references": {{
    "[1]": "http://..."
  }},
  "word_count_min": 500
}}
"""
    if last_rejection:
        parser_prompt += f"\nNote: Previous article attempt failed verify check: {last_rejection}. Please correct this."
        
    try:
        parsed_json = call_llm_and_parse_json(parser_prompt, config, "article")
        from loop.storm_schema import ArticleSchema
        ArticleSchema.model_validate(parsed_json)
    except Exception as e:
        logger.warning(f"Failed to generate valid Article JSON via LLM: {e}. Falling back to Python Markdown parser.")
        parsed_json = parse_markdown_article_to_json(article_content, topic, allowed_urls)
        
    out_path = os.path.join(output_dir, "article.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
        
    return {"artifact_paths": [article_txt_path, out_path]}

# ==============================================================================
# STB-015: Peer Review Stage (STORM polish + Nav Toor P4)
# ==============================================================================
def run_stage_peer_review(topic: str, attempt: int, last_rejection: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")
    
    if config.get("mock_storm"):
        from loop.storm_mock import mock_stage_peer_review
        return mock_stage_peer_review(topic, attempt, last_rejection, output_dir)

    logger.info(f"Running real peer review stage for topic: {topic} (attempt {attempt})")
    
    polished_txt_path = os.path.join(output_dir, "storm_gen_article_polished.txt").replace("\\", "/")
    if not os.path.exists(polished_txt_path):
        # Run STORM polish article
        runner = build_storm_runner(config)
        runner.run(topic=topic, do_research=False, do_generate_outline=False, do_generate_article=False, do_polish_article=True)
        runner.post_run()
        sync_storm_files(topic, config)

    if not os.path.exists(polished_txt_path):
        raise FileNotFoundError(f"STORM polishing did not produce storm_gen_article_polished.txt at {polished_txt_path}")

    with open(polished_txt_path, "r", encoding="utf-8") as f:
        polished_content = f.read()
        
    cleaned_content = clean_electrical_analogy(polished_content)
    if cleaned_content != polished_content:
        polished_content = cleaned_content
        with open(polished_txt_path, "w", encoding="utf-8") as f:
            f.write(polished_content)
        
    # Run P4 Peer Review LLM pass
    p4_template = load_prompt_template("p4_peer_review.md")
    if last_rejection:
        p4_template += f"\nNote: The previous peer review was rejected: {last_rejection}. Adjust scores and comments accordingly."
        
    # Fetch synthesis briefing
    briefing_path = os.path.join(output_dir, "research_briefing.json").replace("\\", "/")
    briefing_data = ""
    if os.path.exists(briefing_path):
        with open(briefing_path, "r", encoding="utf-8") as f:
            briefing_data = f.read()
            
    context = f"Briefing:\n{briefing_data}\n\nPolished Article:\n{polished_content}"
    prompt = p4_template.replace("{upstream_data}", context)
    parsed_json = call_llm_and_parse_json(prompt, config, "peer_review", use_planner=True)
    
    peer_review_path = os.path.join(output_dir, "peer_review.json").replace("\\", "/")
    with open(peer_review_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
        
    # Bundle final_report.json
    final_report = {
        "topic": topic,
        "polished_article": polished_content,
        "peer_review": parsed_json,
        "metadata": {
            "attempt": attempt,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    final_report_path = os.path.join(output_dir, "final_report.json").replace("\\", "/")
    with open(final_report_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)
        
    return {
        "artifact_paths": [
            polished_txt_path,
            peer_review_path,
            final_report_path
        ]
    }
