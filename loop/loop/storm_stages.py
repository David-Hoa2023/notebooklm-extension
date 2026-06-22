import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from openai import OpenAI
from loop.utils import extract_json, clean_electrical_analogy
from loop.storm_adapter import build_storm_runner, HAS_STORM
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
    llm_output = call_llm(prompt, config)
    parsed_json = json.loads(extract_json(llm_output))
    
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
    llm_output = call_llm(prompt, config)
    parsed_json = json.loads(extract_json(llm_output))
    
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
        
    llm_output = call_llm(parser_prompt, config)
    try:
        parsed_json = json.loads(extract_json(llm_output))
        if isinstance(parsed_json, list):
            parsed_json = {"sections": parsed_json}
    except Exception as e:
        logger.error(f"Failed to parse outline JSON. Raw output:\n{llm_output}")
        raise e
    
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
    llm_output = call_llm(prompt, config)
    parsed_json = json.loads(extract_json(llm_output))
    
    out_path = os.path.join(output_dir, "research_briefing.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed_json, f, indent=2)
        
    return {"artifact_paths": [out_path]}

# ==============================================================================
# STB-014: Article Stage (STORM article generation)
# ==============================================================================
def run_stage_article(topic: str, attempt: int, last_rejection: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
    output_dir = os.path.join("artifacts", "raw", config["run_id"], to_topic_slug(topic)).replace("\\", "/")
    
    if config.get("mock_storm"):
        from loop.storm_mock import mock_stage_article
        return mock_stage_article(topic, attempt, last_rejection, output_dir)

    logger.info(f"Running real article stage for topic: {topic} (attempt {attempt})")
    
    article_txt_path = os.path.join(output_dir, "storm_gen_article.txt").replace("\\", "/")
    if not os.path.exists(article_txt_path):
        # Run STORM article generation
        runner = build_storm_runner(config)
        runner.run(topic=topic, do_research=False, do_generate_outline=False, do_generate_article=True, do_polish_article=False)
        runner.post_run()
    if os.path.exists(article_txt_path):
        with open(article_txt_path, "r", encoding="utf-8") as f:
            article_content = f.read()
    else:
        article_content = "No article content."
        
    # Load actual STORM citation mapping to avoid hallucinations
    url_to_info_path = os.path.join(output_dir, "url_to_info.json").replace("\\", "/")
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

Return ONLY valid JSON matching ArticleSchema:
{{
  "title": "...",
  "sections": [
    {{
      "title": "...",
      "content": "...",
      "citation_indices": [1]
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
        
    llm_output = call_llm(parser_prompt, config)
    parsed_json = json.loads(extract_json(llm_output))
    
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
    if os.path.exists(polished_txt_path):
        with open(polished_txt_path, "r", encoding="utf-8") as f:
            polished_content = f.read()
            
        cleaned_content = clean_electrical_analogy(polished_content)
        if cleaned_content != polished_content:
            polished_content = cleaned_content
            with open(polished_txt_path, "w", encoding="utf-8") as f:
                f.write(polished_content)
    else:
        polished_content = "No polished article content."
        
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
    llm_output = call_llm(prompt, config, use_planner=True)
    parsed_json = json.loads(extract_json(llm_output))
    
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
