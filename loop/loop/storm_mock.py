import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("loop.storm_mock")

def mock_stage_perspectives(topic: str, attempt: int, last_rejection: Optional[str], output_dir: str) -> Dict[str, Any]:
    logger.info(f"🎭 [Mock Perspectives] Running for {topic} (attempt {attempt})")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Write dummy raw search outputs
    url_to_info = {
        "https://example.com/battery_tech": {"title": "Solid State Batteries", "url": "https://example.com/battery_tech"},
        "https://example.com/supply_chain": {"title": "Supply Chain Issues", "url": "https://example.com/supply_chain"},
        "https://example.com/tariffs": {"title": "Tariffs report", "url": "https://example.com/tariffs"},
        "https://example.com/dead_link": {"title": "Dead Link", "url": "https://example.com/dead_link"}
    }
    
    with open(os.path.join(output_dir, "url_to_info.json"), "w") as f:
        json.dump(url_to_info, f, indent=2)
    with open(os.path.join(output_dir, "conversation_log.json"), "w") as f:
        json.dump({"conversations": []}, f, indent=2)
    with open(os.path.join(output_dir, "raw_search_results.json"), "w") as f:
        json.dump({"results": []}, f, indent=2)

    # 2. Setup perspectives list
    perspectives = [
        {
            "id": "practitioner",
            "position": "Practitioners look at practical manufacturing and engineering challenges.",
            "evidence": "Giga-factory throughput and cell assembly yields are key metrics.",
            "unique_insight": "Automating cell packing reduces defect rates by 15%.",
            "sources": ["https://example.com/battery_tech"]
        },
        {
            "id": "academic",
            "position": "Academics focus on chemical research and breakthrough cell chemistries.",
            "evidence": "NMC and LFP chemistry limitations have been documented extensively.",
            "unique_insight": "Lithium-sulfur has high energy density but low cycle life.",
            "sources": ["https://example.com/battery_tech"]
        },
        {
            "id": "economist",
            "position": "Economists focus on supply/demand dynamics and price points per kWh.",
            "evidence": "Battery packs cost $130/kWh currently, aiming for sub-$100/kWh.",
            "unique_insight": "Tariffs on raw materials drive up localized costs by 20%.",
            "sources": ["https://example.com/supply_chain"]
        },
        {
            "id": "historian",
            "position": "Historians trace adoption timelines from lead-acid to lithium-ion.",
            "evidence": "Similar transitions show it takes 15-20 years to scale new chemistries.",
            "unique_insight": "Early standardizations define long-term industry winners.",
            "sources": ["https://example.com/supply_chain"]
        }
    ]

    # Check adversarial env var: if historian should be missing
    inject_missing = os.environ.get("INJECT_MISSING_PERSPECTIVE")
    
    # We fail on attempt 0 by missing skeptic (unless INJECT_MISSING_PERSPECTIVE is set, in which case we miss historian)
    if attempt == 0:
        if inject_missing == "historian":
            logger.info("🎭 [Mock Perspectives] Dropping historian for attempt 0 due to INJECT_MISSING_PERSPECTIVE")
            # Filter out historian, keep skeptic
            perspectives = [p for p in perspectives if p["id"] != "historian"]
            perspectives.append({
                "id": "skeptic",
                "position": "Skeptics warn against hype cycles and real-world safety/safety concerns.",
                "evidence": "Thermal runaway issues and recycling bottlenecks persist.",
                "unique_insight": "Solid-state commercialization is still 5+ years away.",
                "sources": ["https://example.com/supply_chain"]
            })
        else:
            logger.info("🎭 [Mock Perspectives] Intentionally dropping skeptic for attempt 0 to simulate verify fail")
            # skeptic is missing
    else:
        # Success: add the missing perspective
        perspectives.append({
            "id": "skeptic",
            "position": "Skeptics warn against hype cycles and real-world safety/safety concerns.",
            "evidence": "Thermal runaway issues and recycling bottlenecks persist.",
            "unique_insight": "Solid-state commercialization is still 5+ years away.",
            "sources": ["https://example.com/supply_chain"]
        })

    norm_path = os.path.join(output_dir, "perspectives.json").replace("\\", "/")
    with open(norm_path, "w", encoding="utf-8") as f:
        json.dump({"perspectives": perspectives}, f, indent=2)

    return {
        "artifact_paths": [
            os.path.join(output_dir, "conversation_log.json").replace("\\", "/"),
            norm_path
        ],
        "storm_metadata": {"query_count": 5}
    }

def mock_stage_contradictions(topic: str, attempt: int, last_rejection: Optional[str], output_dir: str) -> Dict[str, Any]:
    logger.info(f"🎭 [Mock Contradictions] Running for {topic} (attempt {attempt})")
    os.makedirs(output_dir, exist_ok=True)

    contradictions = {
        "clashes": [
            {
                "perspective_id_1": "academic",
                "perspective_id_2": "skeptic",
                "description": "Academics claim rapid scaling of new chemistry is near, while skeptics emphasize recycling bottlenecks."
            },
            {
                "perspective_id_1": "practitioner",
                "perspective_id_2": "economist",
                "description": "Practitioners demand high-spec custom cells, whereas economists require standardization to lower costs."
            },
            {
                "perspective_id_1": "historian",
                "perspective_id_2": "practitioner",
                "description": "Historians point out the slow pace of past infrastructure changes, while practitioners expect sudden disruption."
            }
        ],
        "strongest_evidence": "The cost curve reduction data in economist reports.",
        "weakest_evidence": "Lab-only cycle tests in early academic papers.",
        "blind_spots": ["Environmental impact of nickel/cobalt mining in South America."]
    }

    out_path = os.path.join(output_dir, "contradiction_map.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(contradictions, f, indent=2)
    return {"artifact_paths": [out_path]}

def mock_stage_outline(topic: str, attempt: int, last_rejection: Optional[str], output_dir: str) -> Dict[str, Any]:
    logger.info(f"🎭 [Mock Outline] Running for {topic} (attempt {attempt})")
    os.makedirs(output_dir, exist_ok=True)

    outline_txt = """
# Outline for EV Battery Research
## 1. Introduction to Battery Chemistry
### 1.1 Academic breakthroughs in LFP and solid state
### 1.2 Practitioner manufacturing realities
## 2. Supply Chain Dynamics
### 2.1 Economists' cost projections and market caps
### 2.2 Historians' historical transitions
## 3. Risk Mitigation & Future Outlook
### 3.1 Skeptics' safety and recycling warnings
"""
    with open(os.path.join(output_dir, "storm_gen_outline.txt"), "w") as f:
        f.write(outline_txt)

    outline_json = {
        "sections": [
            {
                "title": "Introduction to Battery Chemistry",
                "description": "Overview of breakthroughs and factory yields.",
                "perspective_coverage": ["academic", "practitioner"],
                "contradiction_refs": [0],
                "subsections": [
                    {
                        "title": "Academic breakthroughs in LFP and solid state",
                        "description": "Lab research details.",
                        "perspective_coverage": ["academic"],
                        "contradiction_refs": []
                    },
                    {
                        "title": "Practitioner manufacturing realities",
                        "description": "Factory yield rates.",
                        "perspective_coverage": ["practitioner"],
                        "contradiction_refs": []
                    }
                ]
            },
            {
                "title": "Supply Chain Dynamics",
                "description": "Raw materials and economics.",
                "perspective_coverage": ["economist", "historian"],
                "contradiction_refs": [1],
                "subsections": [
                    {
                        "title": "Economists' cost projections",
                        "description": "$130/kWh targets.",
                        "perspective_coverage": ["economist"],
                        "contradiction_refs": []
                    },
                    {
                        "title": "Historians' historical transitions",
                        "description": "Transitions from lead-acid.",
                        "perspective_coverage": ["historian"],
                        "contradiction_refs": []
                    }
                ]
            },
            {
                "title": "Risk Mitigation & Future Outlook",
                "description": "Recycling and safety risk checklist.",
                "perspective_coverage": ["skeptic"],
                "contradiction_refs": [2],
                "subsections": []
            }
        ]
    }

    out_path = os.path.join(output_dir, "outline.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(outline_json, f, indent=2)
    return {"artifact_paths": [os.path.join(output_dir, "storm_gen_outline.txt").replace("\\", "/"), out_path]}

def mock_stage_synthesis(topic: str, attempt: int, last_rejection: Optional[str], output_dir: str) -> Dict[str, Any]:
    logger.info(f"🎭 [Mock Synthesis] Running for {topic} (attempt {attempt})")
    os.makedirs(output_dir, exist_ok=True)

    synthesis = {
        "summary": "Cohesive synthesis of EV battery supply chain trends.",
        "key_findings": [
            {"finding": "Solid-state cell yield is currently sub-50% in testing.", "reliability_score": 9, "source_refs": ["https://example.com/battery_tech"]},
            {"finding": "Battery cell pricing must decline to $100/kWh for mass parity.", "reliability_score": 8, "source_refs": ["https://example.com/supply_chain"]},
            {"finding": "Recycling of spent LFP batteries is economically unviable today.", "reliability_score": 7, "source_refs": ["https://example.com/supply_chain"]},
            {"finding": "Historical transitions suggest standardizations take 15 years.", "reliability_score": 9, "source_refs": ["https://example.com/supply_chain"]},
            {"finding": "Tariffs increase localized battery pack costs by 20% in the US.", "reliability_score": 8, "source_refs": ["https://example.com/tariffs"]}
        ],
        "hidden_connections": ["The clash between academic research pace and manufacturing scale-up."],
        "actionable_insight": "Establish domestic processing to bypass import tariffs."
    }

    out_path = os.path.join(output_dir, "research_briefing.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(synthesis, f, indent=2)
    return {"artifact_paths": [out_path]}

def mock_stage_article(topic: str, attempt: int, last_rejection: Optional[str], output_dir: str) -> Dict[str, Any]:
    logger.info(f"🎭 [Mock Article] Running for {topic} (attempt {attempt})")
    os.makedirs(output_dir, exist_ok=True)

    # Check adversarial bad citation hook
    inject_bad = os.environ.get("INJECT_BAD_CITATION") == "1"

    # Make attempt 0 fail word count or inject a dead citation link
    word_count_min = 500
    if attempt == 0:
        if inject_bad:
            logger.info("🎭 [Mock Article] Injecting bad citation for attempt 0 due to INJECT_BAD_CITATION")
            citation_url = "https://example.com/dead_link"
        else:
            logger.info("🎭 [Mock Article] Creating short article for attempt 0 to fail word count check")
            word_count_min = 200  # Will trigger verify error or Pydantic error because we produce less content
            citation_url = "https://example.com/battery_tech"
    else:
        citation_url = "https://example.com/battery_tech"

    # Generate content that meets the length requirement if not attempt 0 short
    content_block_1 = "This is a detailed analysis of battery chemistry breakthroughs. " * 30
    content_block_2 = "Supply chain and tariff issues are driving costs. " * 30
    
    if attempt == 0 and not inject_bad:
        # short content
        content_block_1 = "Short content. " * 5
        content_block_2 = "Short content. " * 5

    article_txt = f"""
# Detailed EV Battery Research
## 1. Introduction to Battery Chemistry
{content_block_1} [1]
## 2. Supply Chain Dynamics
{content_block_2} [2]
"""
    with open(os.path.join(output_dir, "storm_gen_article.txt"), "w") as f:
        f.write(article_txt)

    article_json = {
        "title": "Detailed EV Battery Research",
        "sections": [
            {
                "title": "Introduction to Battery Chemistry",
                "content": content_block_1 + " [1]",
                "citation_indices": [1]
            },
            {
                "title": "Supply Chain Dynamics",
                "content": content_block_2 + " [2]",
                "citation_indices": [2]
            }
        ],
        "citation_references": {
            "[1]": citation_url,
            "[2]": "https://example.com/supply_chain"
        },
        "word_count_min": 500
    }

    out_path = os.path.join(output_dir, "article.json").replace("\\", "/")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(article_json, f, indent=2)
    return {"artifact_paths": [os.path.join(output_dir, "storm_gen_article.txt").replace("\\", "/"), out_path]}

def mock_stage_peer_review(topic: str, attempt: int, last_rejection: Optional[str], output_dir: str) -> Dict[str, Any]:
    logger.info(f"🎭 [Mock Peer Review] Running for {topic} (attempt {attempt})")
    os.makedirs(output_dir, exist_ok=True)

    # Fail on attempt 0 due to low confidence score
    confidence = 8
    grade = "A"
    if attempt == 0:
        logger.info("🎭 [Mock Peer Review] Returning low confidence score (6) for attempt 0 to trigger fail")
        confidence = 6
        grade = "C"

    review = {
        "confidence_scores": {
            "perspectives": confidence,
            "contradictions": confidence,
            "synthesis": confidence,
            "article": confidence
        },
        "overall_confidence": confidence,
        "bias_check": "No significant bias detected.",
        "missing_perspectives": [],
        "overall_grade": grade
    }

    # Write storm_gen_article_polished.txt
    polished_txt = "Polished: This is a highly refined EV battery supply chain report."
    with open(os.path.join(output_dir, "storm_gen_article_polished.txt"), "w") as f:
        f.write(polished_txt)

    peer_review_path = os.path.join(output_dir, "peer_review.json").replace("\\", "/")
    with open(peer_review_path, "w", encoding="utf-8") as f:
        json.dump(review, f, indent=2)

    final_report = {
        "topic": topic,
        "polished_article": polished_txt,
        "peer_review": review,
        "metadata": {
            "attempt": attempt,
            "timestamp": datetime.now().isoformat()
        }
    }
    
    final_report_path = os.path.join(output_dir, "final_report.json").replace("\\", "/")
    with open(final_report_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2)

    return {"artifact_paths": [
        os.path.join(output_dir, "storm_gen_article_polished.txt").replace("\\", "/"),
        peer_review_path,
        final_report_path
    ]}
