from typing import Dict, List, Tuple
from src.services.graph.neo4j_repo import get_driver

def next_best_topics(subject_uid: str, progress: Dict[str, float], prereq_threshold: float = 0.7, top_k: int = 5, alpha: float = 0.5, beta: float = 0.3) -> Dict[str, List[Dict]]:
    drv = get_driver()
    items: List[Dict] = []
    with drv.session() as s:
        rows = s.run(
            "MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) "
            "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
            "WITH t, collect(pre.uid) AS prereqs "
            "OPTIONAL MATCH (x:Topic)-[:PREREQ]->(t) WITH t, prereqs, COUNT(x) AS in_deg "
            "OPTIONAL MATCH path=(t)-[:PREREQ*1..10]->(d:Topic) WITH t, prereqs, in_deg, COUNT(DISTINCT d) AS descendants "
            "RETURN t.uid AS uid, t.title AS title, prereqs, in_deg, descendants",
            {"su": subject_uid}
        )
        for r in rows:
            tuid = r["uid"]
            prereqs = r["prereqs"] or []
            unlocked = all(progress.get(p, 0.0) >= prereq_threshold for p in prereqs)
            if not unlocked:
                continue
            mastery = float(progress.get(tuid, 0.0))
            need = 1.0 - mastery
            importance = float(r["in_deg"] or 0.0)
            unlock_impact = float(r["descendants"] or 0.0)
            score = need * (1.0 + alpha * importance + beta * unlock_impact)
            items.append({
                "topic_uid": tuid,
                "title": r["title"],
                "mastery": mastery,
                "score": score,
                "reasoning": {
                    "need": need,
                    "importance": importance,
                    "unlock_impact": unlock_impact,
                    "prereqs": prereqs,
                }
            })
    drv.close()
    items.sort(key=lambda x: x["score"], reverse=True)
    return {"items": items[:top_k]}

