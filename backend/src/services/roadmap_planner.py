from typing import Dict, List
from src.services.graph import neo4j_repo


def plan_route(subject_uid: str | None, progress: Dict[str, float], limit: int = 30, penalty_factor: float = 0.15) -> List[Dict]:
    drv = neo4j_repo.get_driver()
    items: List[Dict] = []
    s = drv.session()
    if subject_uid:
        rows = s.run(
            "MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) "
            "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
            "RETURN t.uid AS uid, t.title AS title, collect(pre.uid) AS prereqs",
            {"su": subject_uid}
        ).data()
    else:
        rows = s.run(
            "MATCH (t:Topic) OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
            "RETURN t.uid AS uid, t.title AS title, collect(pre.uid) AS prereqs"
        ).data()
    for r in rows:
        tuid = r["uid"]
        mastered = float(progress.get(tuid, 0.0) or 0.0)
        missing = 0
        for pre in (r.get("prereqs") or []):
            mastered_pre = float(progress.get(pre, 0.0) or 0.0)
            if mastered_pre < 0.3:
                missing += 1
        priority = max(0.0, (1.0 - mastered) + penalty_factor * missing)
        items.append({"uid": tuid, "title": r["title"], "mastered": mastered, "missing_prereqs": missing, "priority": priority})
    try:
        s.close()
    except Exception:
        pass
    drv.close()
    items.sort(key=lambda x: x["priority"], reverse=True)
    return items[:limit]
