import numpy as np
from src.memory.memory_engine import memory_engine
from src.llm import llm_client


def cosine_distance(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 1.0
    return 1.0 - float(np.dot(va, vb) / denom)


class NoveltyScorer:
    def __init__(self):
        self.llm = llm_client

    def score(self, text: str) -> float:
        """
        Intrinsic motivation: distance from nearest existing memory (insight + interaction).
        Higher = more novel.
        """
        if not text.strip():
            return 0.0

        try:
            query_emb = self.llm.embed(text[:2000])
        except Exception:
            return 0.5

        memories = (
            memory_engine.get_all_memories(namespace="insight")
            + memory_engine.get_all_memories(namespace="interaction")
        )
        if not memories:
            return 1.0

        min_distance = 1.0
        for mem in memories[:200]:
            content = mem.get("content", "")
            if not content.strip():
                continue
            try:
                mem_emb = self.llm.embed(content[:500])
                dist = cosine_distance(query_emb, mem_emb)
                min_distance = min(min_distance, dist)
            except Exception:
                continue

        return min_distance


novelty_scorer = NoveltyScorer()
