import re
from typing import List, Dict, Any

STAGES = ["perspectives", "contradictions", "outline", "synthesis", "article", "peer_review"]

def to_topic_slug(topic: str) -> str:
    """
    Normalizes a topic string into a topic_slug:
    lowercase, spaces and slashes to underscore, max 64 chars, alphanumeric/underscore only.
    """
    slug = topic.strip().lower()
    slug = re.sub(r'[\s/]+', '_', slug)
    slug = re.sub(r'[^a-z0-9_]', '', slug)
    return slug[:64]

def expand_topics_to_items(topics: List[str], stages: List[str] = STAGES) -> Dict[str, Dict[str, Any]]:
    """
    Expands a list of topics and sequential stages into a dictionary of composite item IDs and metadata.
    """
    items = {}
    for topic in topics:
        slug = to_topic_slug(topic)
        for i, stage in enumerate(stages):
            item_id = f"{slug}::{stage}"
            depends_on = []
            if i > 0:
                depends_on = [f"{slug}::{stages[i-1]}"]
            items[item_id] = {
                "topic_slug": slug,
                "stage": stage,
                "depends_on": depends_on
            }
    return items

def expand_topics_to_stage_items(topics: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Alias/wrapper for expand_topics_to_items using default STAGES.
    """
    return expand_topics_to_items(topics, STAGES)

def get_stage_output_filename(stage: str) -> str:
    """
    Maps a stage name to its raw output filename.
    """
    mapping = {
        "perspectives": "conversation_log.json",
        "contradictions": "contradiction_map.json",
        "outline": "storm_gen_outline.txt",
        "synthesis": "research_briefing.json",
        "article": "storm_gen_article.txt",
        "peer_review": "storm_gen_article_polished.txt"
    }
    return mapping.get(stage, f"{stage}_output.json")

def get_stage_normalized_filename(stage: str) -> str:
    """
    Maps a stage name to its normalized output filename.
    """
    mapping = {
        "perspectives": "perspectives.json",
        "contradictions": "contradiction_map.json",
        "outline": "outline.json",
        "synthesis": "research_briefing.json",
        "article": "article.json",
        "peer_review": "peer_review.json"
    }
    return mapping.get(stage, f"{stage}_normalized.json")
