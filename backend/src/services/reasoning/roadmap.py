from typing import Dict, List
from src.services.reasoning.gaps import compute_gaps
from src.services.reasoning.next_best_topic import next_best_topics

def build_roadmap(subject_uid: str, progress: Dict[str, float], goals: List[str] | None = None, prereq_threshold: float = 0.7, top_k: int = 10) -> Dict[str, List[Dict]]:
    gaps = compute_gaps(subject_uid, progress, goals, prereq_threshold)
    nbt = next_best_topics(subject_uid, progress, prereq_threshold, top_k)
    items: List[Dict] = []
    missing_map = {bg["topic_uid"]: bg.get("prereqs", []) for bg in gaps.get("blocking_gaps", [])}
    for it in nbt["items"]:
        tuid = it["topic_uid"]
        items.append({
            "topic_uid": tuid,
            "title": it["title"],
            "mastery": it["mastery"],
            "missing_prereqs": missing_map.get(tuid, []),
            "priority": "high" if it["score"] >= 1.0 else ("medium" if it["score"] >= 0.5 else "low"),
            "reasoning": it["reasoning"],
        })
    return {"items": items, "meta": {"blocking_gaps": gaps.get("blocking_gaps", []), "latent_gaps": gaps.get("latent_gaps", [])}}

