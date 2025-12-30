from typing import Dict, List
from src.services.graph import neo4j_repo
from src.services.questions import all_topic_uids_from_examples


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
    if len(items) >= limit:
        return items[:limit]
    if subject_uid:
        s2 = neo4j_repo.get_driver().session()
        try:
            more = s2.run(
                "MATCH (:Section)-[:CONTAINS]->(t:Topic) "
                "OPTIONAL MATCH (t)-[:PREREQ]->(pre:Topic) "
                "RETURN t.uid AS uid, t.title AS title, collect(pre.uid) AS prereqs"
            ).data()
        finally:
            try:
                s2.close()
            except Exception:
                ...
        for r in more:
            tuid = r["uid"]
            if any(it["uid"] == tuid for it in items):
                continue
            mastered = float(progress.get(tuid, 0.0) or 0.0)
            missing = 0
            for pre in (r.get("prereqs") or []):
                mastered_pre = float(progress.get(pre, 0.0) or 0.0)
                if mastered_pre < 0.3:
                    missing += 1
            priority = max(0.0, (1.0 - mastered) + penalty_factor * missing)
            items.append({"uid": tuid, "title": r["title"], "mastered": mastered, "missing_prereqs": missing, "priority": priority})
        items.sort(key=lambda x: x["priority"], reverse=True)
        if items and len(items) >= limit:
            return items[:limit]
        if items and len(items) < limit and progress:
            present = {it["uid"] for it in items}
            for tuid, mastered in progress.items():
                if tuid in present:
                    continue
                try:
                    mastered_f = float(mastered or 0.0)
                except Exception:
                    mastered_f = 0.0
                items.append({"uid": tuid, "title": tuid, "mastered": mastered_f, "missing_prereqs": 0, "priority": max(0.0, 1.0 - mastered_f)})
                if len(items) >= limit:
                    break
            items.sort(key=lambda x: x["priority"], reverse=True)
            if items:
                return items[:limit]
    # Fallback 1: use progress keys as topics (prefer known user context)
    fallback: List[Dict] = []
    if progress:
        for tuid, mastered in progress.items():
            try:
                mastered_f = float(mastered or 0.0)
            except Exception:
                mastered_f = 0.0
            priority = max(0.0, (1.0 - mastered_f))
            fallback.append({"uid": tuid, "title": tuid, "mastered": mastered_f, "missing_prereqs": 0, "priority": priority})
            if len(fallback) >= limit:
                break
        fallback.sort(key=lambda x: x["priority"], reverse=True)
        return fallback[:limit]
    # Fallback 2: synthesize starter topics
    for i in range(limit):
        tuid = f"TOP-STUB-{i+1}"
        fallback.append({"uid": tuid, "title": f"Стартовая тема {i+1}", "mastered": 0.0, "missing_prereqs": 0, "priority": 1.0})
    return fallback[:limit]
