from typing import Dict, List, Tuple
from app.services.graph.neo4j_repo import get_driver

def compute_gaps(subject_uid: str, progress: Dict[str, float], goals: List[str] | None = None, prereq_threshold: float = 0.7) -> Dict[str, List[Dict]]:
    drv = get_driver()
    blocking: List[Dict] = []
    latent: List[Dict] = []
    with drv.session() as s:
        rows = s.run(
            "MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) "
            "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
            "RETURN t.uid AS uid, t.title AS title, collect(pre.uid) AS prereqs",
            {"su": subject_uid}
        )
        for r in rows:
            tuid = r["uid"]
            prereqs = [p for p in r["prereqs"] or [] if p]
            missing = [p for p in prereqs if (progress.get(p, 0.0) < prereq_threshold)]
            if missing:
                blocking.append({
                    "topic_uid": tuid,
                    "why": "missing_prereqs",
                    "prereqs": missing,
                    "affected_topics": [tuid],
                })
        # latent gaps: topics with low mastery but unlocked
        for r in rows:
            tuid = r["uid"]
            prereqs = [p for p in r["prereqs"] or [] if p]
            unlocked = all(progress.get(p, 0.0) >= prereq_threshold for p in prereqs)
            if unlocked and progress.get(tuid, 0.0) < 0.5:
                latent.append({
                    "topic_uid": tuid,
                    "distance": 1.0 - progress.get(tuid, 0.0),
                    "why": "low_mastery_unlocked",
                })
    drv.close()
    return {"blocking_gaps": blocking, "latent_gaps": latent}

