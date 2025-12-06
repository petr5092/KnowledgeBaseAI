import os
import json
from typing import Dict, List
from neo4j import GraphDatabase
from neo4j_repo import Neo4jRepo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, 'kb')


def _load_jsonl(filepath: str) -> List[Dict]:
    data: List[Dict] = []
    if not os.path.exists(filepath):
        return data
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return data


def get_driver():
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER')
    password = os.getenv('NEO4J_PASSWORD')
    if not uri or not user or not password:
        raise RuntimeError('Missing Neo4j connection environment variables')
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_constraints(session):
    session.run("CREATE CONSTRAINT subject_uid_unique IF NOT EXISTS FOR (n:Subject) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT section_uid_unique IF NOT EXISTS FOR (n:Section) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT topic_uid_unique IF NOT EXISTS FOR (n:Topic) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT skill_uid_unique IF NOT EXISTS FOR (n:Skill) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT method_uid_unique IF NOT EXISTS FOR (n:Method) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT goal_uid_unique IF NOT EXISTS FOR (n:Goal) REQUIRE n.uid IS UNIQUE")
    session.run("CREATE CONSTRAINT objective_uid_unique IF NOT EXISTS FOR (n:Objective) REQUIRE n.uid IS UNIQUE")


def ensure_weight_defaults(session):
    session.run("MATCH (t:Topic) WHERE t.static_weight IS NULL SET t.static_weight = 0.5")
    session.run("MATCH (t:Topic) WHERE t.dynamic_weight IS NULL SET t.dynamic_weight = t.static_weight")
    session.run("MATCH (s:Skill) WHERE s.static_weight IS NULL SET s.static_weight = 0.5")
    session.run("MATCH (s:Skill) WHERE s.dynamic_weight IS NULL SET s.dynamic_weight = s.static_weight")


def ensure_weight_defaults_repo(repo: Neo4jRepo):
    repo.write("MATCH (t:Topic) WHERE t.static_weight IS NULL SET t.static_weight = 0.5")
    repo.write("MATCH (t:Topic) WHERE t.dynamic_weight IS NULL SET t.dynamic_weight = t.static_weight")
    repo.write("MATCH (s:Skill) WHERE s.static_weight IS NULL SET s.static_weight = 0.5")
    repo.write("MATCH (s:Skill) WHERE s.dynamic_weight IS NULL SET s.dynamic_weight = s.static_weight")


def ensure_user_profile(session, user_id: str):
    session.run("MERGE (:User {id:$id})", id=user_id)


def sync_from_jsonl() -> Dict:
    subjects = _load_jsonl(os.path.join(KB_DIR, 'subjects.jsonl'))
    sections = _load_jsonl(os.path.join(KB_DIR, 'sections.jsonl'))
    topics = _load_jsonl(os.path.join(KB_DIR, 'topics.jsonl'))
    skills = _load_jsonl(os.path.join(KB_DIR, 'skills.jsonl'))
    methods = _load_jsonl(os.path.join(KB_DIR, 'methods.jsonl'))
    skill_methods = _load_jsonl(os.path.join(KB_DIR, 'skill_methods.jsonl'))
    topic_goals = _load_jsonl(os.path.join(KB_DIR, 'topic_goals.jsonl'))
    topic_objectives = _load_jsonl(os.path.join(KB_DIR, 'topic_objectives.jsonl'))

    driver = get_driver()
    with driver.session() as session:
        ensure_constraints(session)
        ensure_weight_defaults(session)

        for s in subjects:
            session.run(
                "MERGE (n:Subject {uid:$uid}) SET n.title=$title, n.description=COALESCE($description,'')",
                uid=s.get('uid'), title=s.get('title'), description=s.get('description')
            )

        for sec in sections:
            session.run(
                "MERGE (n:Section {uid:$uid}) SET n.title=$title, n.description=COALESCE($description,'')",
                uid=sec.get('uid'), title=sec.get('title'), description=sec.get('description')
            )
            if sec.get('subject_uid'):
                session.run(
                    "MATCH (a:Subject {uid:$su}), (b:Section {uid:$uid}) MERGE (a)-[:CONTAINS]->(b)",
                    su=sec.get('subject_uid'), uid=sec.get('uid')
                )

        for t in topics:
            session.run(
                "MERGE (n:Topic {uid:$uid}) SET n.title=$title, n.description=COALESCE($description,'')",
                uid=t.get('uid'), title=t.get('title'), description=t.get('description')
            )
            if t.get('section_uid'):
                session.run(
                    "MATCH (a:Section {uid:$su}), (b:Topic {uid:$uid}) MERGE (a)-[:CONTAINS]->(b)",
                    su=t.get('section_uid'), uid=t.get('uid')
                )

        for sk in skills:
            session.run(
                "MERGE (n:Skill {uid:$uid}) SET n.title=$title, n.definition=COALESCE($definition,'')",
                uid=sk.get('uid'), title=sk.get('title'), definition=sk.get('definition')
            )
            if sk.get('subject_uid'):
                session.run(
                    "MATCH (a:Subject {uid:$su}), (b:Skill {uid:$uid}) MERGE (a)-[:HAS_SKILL]->(b)",
                    su=sk.get('subject_uid'), uid=sk.get('uid')
                )

        for m in methods:
            session.run(
                "MERGE (n:Method {uid:$uid}) SET n.title=$title, n.method_text=COALESCE($text,''), n.applicability_types=$types",
                uid=m.get('uid'), title=m.get('title'), text=m.get('method_text'), types=m.get('applicability_types', [])
            )

        for sm in skill_methods:
            if not sm.get('skill_uid') or not sm.get('method_uid'):
                continue
            session.run(
                "MATCH (a:Skill {uid:$su}), (b:Method {uid:$mu}) MERGE (a)-[r:LINKED]->(b) SET r.weight=$weight, r.confidence=$confidence",
                su=sm.get('skill_uid'), mu=sm.get('method_uid'), weight=sm.get('weight', 'linked'), confidence=float(sm.get('confidence', 0.9))
            )

        for g in topic_goals:
            gid = g.get('uid') or f"GOAL-{g.get('topic_uid')}-{abs(hash(g.get('title','')))%100000}"
            session.run(
                "MERGE (n:Goal {uid:$uid}) SET n.title=$title",
                uid=gid, title=g.get('title')
            )
            if g.get('topic_uid'):
                session.run(
                    "MATCH (a:Topic {uid:$tu}), (b:Goal {uid:$uid}) MERGE (a)-[:TARGETS]->(b)",
                    tu=g.get('topic_uid'), uid=gid
                )

        for obj in topic_objectives:
            oid = obj.get('uid') or f"OBJ-{obj.get('topic_uid')}-{abs(hash(obj.get('title','')))%100000}"
            session.run(
                "MERGE (n:Objective {uid:$uid}) SET n.title=$title",
                uid=oid, title=obj.get('title')
            )
            if obj.get('topic_uid'):
                session.run(
                    "MATCH (a:Topic {uid:$tu}), (b:Objective {uid:$uid}) MERGE (a)-[:TARGETS]->(b)",
                    tu=obj.get('topic_uid'), uid=oid
                )

    driver.close()
    return {
        'subjects': len(subjects),
        'sections': len(sections),
        'topics': len(topics),
        'skills': len(skills),
        'methods': len(methods),
        'skill_methods': len(skill_methods),
        'goals': len(topic_goals),
        'objectives': len(topic_objectives)
    }


def build_graph_from_neo4j(subject_filter: str | None = None) -> Dict:
    driver = get_driver()
    nodes = []
    edges = []
    with driver.session() as session:
        subj_uids: List[str] = []
        if subject_filter:
            res = session.run("MATCH (s:Subject {uid:$uid}) RETURN s.uid AS uid, s.title AS title", uid=subject_filter)
            for rec in res:
                nodes.append({'data': {'id': rec['uid'], 'label': rec['title'], 'type': 'subject'}})
                subj_uids.append(rec['uid'])
        else:
            res = session.run("MATCH (s:Subject) RETURN s.uid AS uid, s.title AS title")
            for rec in res:
                nodes.append({'data': {'id': rec['uid'], 'label': rec['title'], 'type': 'subject'}})
                subj_uids.append(rec['uid'])

        res = session.run(
            "MATCH (s:Subject)-[:CONTAINS]->(sec:Section) WHERE s.uid IN $uids RETURN s.uid AS su, sec.uid AS uid, sec.title AS title",
            uids=subj_uids
        )
        allowed_sections = set()
        for rec in res:
            allowed_sections.add(rec['uid'])
            nodes.append({'data': {'id': rec['uid'], 'label': rec['title'], 'type': 'section'}})
            edges.append({'data': {'id': f"{rec['su']}->{rec['uid']}", 'source': rec['su'], 'target': rec['uid'], 'rel': 'contains'}})

        res = session.run(
            "MATCH (sec:Section)-[:CONTAINS]->(t:Topic) WHERE sec.uid IN $uids RETURN sec.uid AS su, t.uid AS uid, t.title AS title",
            uids=list(allowed_sections)
        )
        topic_uids = set()
        for rec in res:
            topic_uids.add(rec['uid'])
            nodes.append({'data': {'id': rec['uid'], 'label': rec['title'], 'type': 'topic'}})
            edges.append({'data': {'id': f"{rec['su']}->{rec['uid']}", 'source': rec['su'], 'target': rec['uid'], 'rel': 'contains'}})

        res = session.run(
            "MATCH (t:Topic)-[:TARGETS]->(g) WHERE t.uid IN $uids RETURN t.uid AS tuid, labels(g)[0] AS label, g.uid AS uid, g.title AS title",
            uids=list(topic_uids)
        )
        for rec in res:
            typ = 'objective' if rec['label'] == 'Objective' else 'goal'
            nodes.append({'data': {'id': rec['uid'], 'label': rec['title'], 'type': typ}})
            edges.append({'data': {'id': f"{rec['tuid']}->{rec['uid']}", 'source': rec['tuid'], 'target': rec['uid'], 'rel': 'targets'}})

        res = session.run(
            "MATCH (s:Subject)-[:HAS_SKILL]->(sk:Skill) WHERE s.uid IN $uids RETURN s.uid AS su, sk.uid AS uid, sk.title AS title",
            uids=subj_uids
        )
        for rec in res:
            nodes.append({'data': {'id': rec['uid'], 'label': rec['title'], 'type': 'skill'}})
            edges.append({'data': {'id': f"{rec['su']}->{rec['uid']}", 'source': rec['su'], 'target': rec['uid'], 'rel': 'has_skill'}})

        res = session.run("MATCH (sk:Skill)-[r:LINKED]->(m:Method) RETURN sk.uid AS su, m.uid AS uid, m.title AS title, r.weight AS weight")
        for rec in res:
            nodes.append({'data': {'id': rec['uid'], 'label': rec['title'], 'type': 'method'}})
            edges.append({'data': {'id': f"{rec['su']}->{rec['uid']}", 'source': rec['su'], 'target': rec['uid'], 'rel': rec['weight'] or 'linked'}})

    driver.close()
    return {'nodes': nodes, 'edges': edges}


def analyze_knowledge(subject_uid: str | None = None) -> Dict:
    driver = get_driver()
    metrics: Dict = {}
    with driver.session() as session:
        metrics['subjects'] = session.run("MATCH (n:Subject) RETURN count(n) AS c").single()['c']
        metrics['sections'] = session.run("MATCH (n:Section) RETURN count(n) AS c").single()['c']
        metrics['topics'] = session.run("MATCH (n:Topic) RETURN count(n) AS c").single()['c']
        metrics['skills'] = session.run("MATCH (n:Skill) RETURN count(n) AS c").single()['c']
        metrics['methods'] = session.run("MATCH (n:Method) RETURN count(n) AS c").single()['c']
        metrics['goals'] = session.run("MATCH (n:Goal) RETURN count(n) AS c").single()['c']
        metrics['objectives'] = session.run("MATCH (n:Objective) RETURN count(n) AS c").single()['c']

        orphan_sections = [r['uid'] for r in session.run("MATCH (sec:Section) WHERE NOT EXISTS{ (:Subject)-[:CONTAINS]->(sec) } RETURN sec.uid AS uid")]
        orphan_topics = [r['uid'] for r in session.run("MATCH (t:Topic) WHERE NOT EXISTS{ (:Section)-[:CONTAINS]->(t) } RETURN t.uid AS uid")]
        topics_without_targets = [r['uid'] for r in session.run("MATCH (t:Topic) WHERE NOT EXISTS{ (t)-[:TARGETS]->() } RETURN t.uid AS uid")]
        skills_without_subject = [r['uid'] for r in session.run("MATCH (sk:Skill) WHERE NOT EXISTS{ (:Subject)-[:HAS_SKILL]->(sk) } RETURN sk.uid AS uid")]
        skills_without_methods = [r['uid'] for r in session.run("MATCH (sk:Skill) WHERE NOT EXISTS{ (sk)-[:LINKED]->(:Method) } RETURN sk.uid AS uid")]
        methods_without_links = [r['uid'] for r in session.run("MATCH (m:Method) WHERE NOT EXISTS{ (:Skill)-[:LINKED]->(m) } RETURN m.uid AS uid")]

        metrics['orphan_sections'] = orphan_sections
        metrics['orphan_topics'] = orphan_topics
        metrics['topics_without_targets'] = topics_without_targets
        metrics['skills_without_subject'] = skills_without_subject
        metrics['skills_without_methods'] = skills_without_methods
        metrics['methods_without_links'] = methods_without_links

        total_topics = metrics['topics']
        with_targets = total_topics - len(topics_without_targets)
        metrics['topic_targets_coverage'] = (with_targets / total_topics) if total_topics else 0.0
        total_skills = metrics['skills']
        linked_skills = total_skills - len(skills_without_methods)
        metrics['skill_linkage_coverage'] = (linked_skills / total_skills) if total_skills else 0.0

    driver.close()
    return metrics


def update_dynamic_weight(topic_uid: str, score: float) -> Dict:
    driver = get_driver()
    delta = (50.0 - float(score)) / 100.0
    with driver.session() as session:
        ensure_weight_defaults(session)
        cur = session.run(
            "MATCH (t:Topic {uid:$uid}) RETURN t.uid AS uid, t.title AS title, t.static_weight AS static_weight, t.dynamic_weight AS dynamic_weight",
            uid=topic_uid
        ).single()
        if not cur:
            driver.close()
            return {'uid': topic_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
        new_dw = cur['dynamic_weight'] + delta
        if new_dw < 0.0:
            new_dw = 0.0
        if new_dw > 1.0:
            new_dw = 1.0
        session.run(
            "MATCH (t:Topic {uid:$uid}) SET t.dynamic_weight = $dw",
            uid=topic_uid, dw=new_dw
        )
    driver.close()
    return {'uid': cur['uid'], 'title': cur['title'], 'static_weight': cur['static_weight'], 'dynamic_weight': new_dw}


def update_skill_dynamic_weight(skill_uid: str, score: float) -> Dict:
    driver = get_driver()
    delta = (50.0 - float(score)) / 100.0
    with driver.session() as session:
        ensure_weight_defaults(session)
        cur = session.run(
            "MATCH (s:Skill {uid:$uid}) RETURN s.uid AS uid, s.title AS title, s.static_weight AS static_weight, s.dynamic_weight AS dynamic_weight",
            uid=skill_uid
        ).single()
        if not cur:
            driver.close()
            return {'uid': skill_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
        new_dw = cur['dynamic_weight'] + delta
        if new_dw < 0.0:
            new_dw = 0.0
        if new_dw > 1.0:
            new_dw = 1.0
        session.run(
            "MATCH (s:Skill {uid:$uid}) SET s.dynamic_weight = $dw",
            uid=skill_uid, dw=new_dw
        )
    driver.close()
    return {'uid': cur['uid'], 'title': cur['title'], 'static_weight': cur['static_weight'], 'dynamic_weight': new_dw}


def get_current_knowledge_level(topic_uid: str) -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    rows = repo.read("MATCH (t:Topic {uid:$uid}) RETURN t.uid AS uid, t.title AS title, t.static_weight AS static_weight, t.dynamic_weight AS dynamic_weight", {"uid": topic_uid})
    repo.close()
    rec = rows[0] if rows else {'uid': topic_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
    return {'uid': rec['uid'], 'title': rec['title'], 'static_weight': rec['static_weight'], 'dynamic_weight': rec['dynamic_weight']}


def get_current_skill_level(skill_uid: str) -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    rows = repo.read("MATCH (s:Skill {uid:$uid}) RETURN s.uid AS uid, s.title AS title, s.static_weight AS static_weight, s.dynamic_weight AS dynamic_weight", {"uid": skill_uid})
    repo.close()
    rec = rows[0] if rows else {'uid': skill_uid, 'title': None, 'static_weight': None, 'dynamic_weight': None}
    return {'uid': rec['uid'], 'title': rec['title'], 'static_weight': rec['static_weight'], 'dynamic_weight': rec['dynamic_weight']}


def build_adaptive_roadmap(subject_uid: str | None = None, limit: int = 50) -> List[Dict]:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    if subject_uid:
        rows = repo.read("MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) RETURN t.uid AS uid, t.title AS title, t.static_weight AS sw, t.dynamic_weight AS dw", {"su": subject_uid})
    else:
        rows = repo.read("MATCH (t:Topic) RETURN t.uid AS uid, t.title AS title, t.static_weight AS sw, t.dynamic_weight AS dw")
    items = [{'uid': r['uid'], 'title': r['title'], 'static_weight': r['sw'], 'dynamic_weight': r['dw']}] if rows else []
    items = [{'uid': r['uid'], 'title': r['title'], 'static_weight': r['sw'], 'dynamic_weight': r['dw']} for r in rows]
    items.sort(key=lambda x: (x['dynamic_weight'] or 0.0), reverse=True)
    items = items[:limit]

    roadmap: List[Dict] = []
    for it in items:
        pr = 'high' if (it['dynamic_weight'] or 0.0) >= 0.7 else ('medium' if (it['dynamic_weight'] or 0.0) >= 0.4 else 'low')
        skills_rows = repo.read(
            "MATCH (sub:Subject)-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic {uid:$uid}) MATCH (sub)-[:HAS_SKILL]->(sk:Skill) RETURN DISTINCT sk.uid AS uid, sk.title AS title, sk.static_weight AS sw, sk.dynamic_weight AS dw",
            {"uid": it['uid']}
        )
        skills = [{'uid': r['uid'], 'title': r['title'], 'static_weight': r['sw'], 'dynamic_weight': r['dw']} for r in skills_rows]
        method_rows = repo.read(
            "MATCH (sub:Subject)-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic {uid:$uid}) MATCH (sub)-[:HAS_SKILL]->(sk:Skill)-[:LINKED]->(m:Method) RETURN DISTINCT m.uid AS uid, m.title AS title",
            {"uid": it['uid']}
        )
        methods = [{'uid': r['uid'], 'title': r['title']}] for r in method_rows
        methods = [{'uid': r['uid'], 'title': r['title']} for r in method_rows]
        roadmap.append({'topic': it, 'priority': pr, 'skills': skills, 'methods': methods})
    repo.close()
    return roadmap


def recompute_relationship_weights() -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    rows = repo.read("MATCH (sk:Skill)-[r:LINKED]->(m:Method) SET r.adaptive_weight = COALESCE(sk.dynamic_weight, sk.static_weight, 0.5) RETURN count(r) AS c")
    repo.close()
    return {"updated_links": (rows[0]['c'] if rows else 0)}


def update_user_topic_weight(user_id: str, topic_uid: str, score: float) -> Dict:
    repo = Neo4jRepo()
    delta = (50.0 - float(score)) / 100.0
    with repo.driver.session() as session:
        ensure_weight_defaults(session)
        ensure_user_profile(session, user_id)
        cur = session.run(
            "MATCH (:User {id:$uid})-[r:PROGRESS_TOPIC]->(t:Topic {uid:$tuid}) RETURN r.dynamic_weight AS dw, t.static_weight AS sw, t.title AS title",
            uid=user_id, tuid=topic_uid
        ).single()
        if cur is None:
            base = session.run(
                "MATCH (t:Topic {uid:$tuid}) RETURN t.static_weight AS sw, t.title AS title",
                tuid=topic_uid
            ).single()
            if base is None:
                driver.close()
                return {'uid': topic_uid, 'user_id': user_id, 'title': None, 'static_weight': None, 'dynamic_weight': None}
            dw = float(base['sw'] or 0.5)
            session.run(
                "MATCH (u:User {id:$uid}), (t:Topic {uid:$tuid}) MERGE (u)-[r:PROGRESS_TOPIC]->(t) SET r.dynamic_weight = $dw",
                uid=user_id, tuid=topic_uid, dw=dw
            )
            title = base['title']
        else:
            dw = float((cur['dw'] if cur['dw'] is not None else cur['sw'] or 0.5))
            title = cur['title']
        new_dw = dw + delta
        if new_dw < 0.0:
            new_dw = 0.0
        if new_dw > 1.0:
            new_dw = 1.0
        session.run(
            "MATCH (:User {id:$uid})-[r:PROGRESS_TOPIC]->(t:Topic {uid:$tuid}) SET r.dynamic_weight = $dw",
            uid=user_id, tuid=topic_uid, dw=new_dw
        )
    repo.close()
    return {'uid': topic_uid, 'user_id': user_id, 'title': title, 'dynamic_weight': new_dw}


def update_user_skill_weight(user_id: str, skill_uid: str, score: float) -> Dict:
    repo = Neo4jRepo()
    delta = (50.0 - float(score)) / 100.0
    with repo.driver.session() as session:
        ensure_weight_defaults(session)
        ensure_user_profile(session, user_id)
        cur = session.run(
            "MATCH (:User {id:$uid})-[r:PROGRESS_SKILL]->(s:Skill {uid:$suid}) RETURN r.dynamic_weight AS dw, s.static_weight AS sw, s.title AS title",
            uid=user_id, suid=skill_uid
        ).single()
        if cur is None:
            base = session.run(
                "MATCH (s:Skill {uid:$suid}) RETURN s.static_weight AS sw, s.title AS title",
                suid=skill_uid
            ).single()
            if base is None:
                driver.close()
                return {'uid': skill_uid, 'user_id': user_id, 'title': None, 'static_weight': None, 'dynamic_weight': None}
            dw = float(base['sw'] or 0.5)
            session.run(
                "MATCH (u:User {id:$uid}), (s:Skill {uid:$suid}) MERGE (u)-[r:PROGRESS_SKILL]->(s) SET r.dynamic_weight = $dw",
                uid=user_id, suid=skill_uid, dw=dw
            )
            title = base['title']
        else:
            dw = float((cur['dw'] if cur['dw'] is not None else cur['sw'] or 0.5))
            title = cur['title']
        new_dw = dw + delta
        if new_dw < 0.0:
            new_dw = 0.0
        if new_dw > 1.0:
            new_dw = 1.0
        session.run(
            "MATCH (:User {id:$uid})-[r:PROGRESS_SKILL]->(s:Skill {uid:$suid}) SET r.dynamic_weight = $dw",
            uid=user_id, suid=skill_uid, dw=new_dw
        )
    repo.close()
    return {'uid': skill_uid, 'user_id': user_id, 'title': title, 'dynamic_weight': new_dw}


def get_user_topic_level(user_id: str, topic_uid: str) -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    repo.ensure_user(user_id)
    rows = repo.read("MATCH (t:Topic {uid:$tuid}) OPTIONAL MATCH (:User {id:$uid})-[r:PROGRESS_TOPIC]->(t) RETURN t.title AS title, t.static_weight AS sw, COALESCE(r.dynamic_weight, t.dynamic_weight, t.static_weight) AS dw", {"uid": user_id, "tuid": topic_uid})
    repo.close()
    rec = rows[0] if rows else {'title': None, 'sw': None, 'dw': None}
    return {'uid': topic_uid, 'user_id': user_id, 'title': rec['title'], 'static_weight': rec['sw'], 'dynamic_weight': rec['dw']}


def get_user_skill_level(user_id: str, skill_uid: str) -> Dict:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    repo.ensure_user(user_id)
    rows = repo.read("MATCH (s:Skill {uid:$suid}) OPTIONAL MATCH (:User {id:$uid})-[r:PROGRESS_SKILL]->(s) RETURN s.title AS title, s.static_weight AS sw, COALESCE(r.dynamic_weight, s.dynamic_weight, s.static_weight) AS dw", {"uid": user_id, "suid": skill_uid})
    repo.close()
    rec = rows[0] if rows else {'title': None, 'sw': None, 'dw': None}
    return {'uid': skill_uid, 'user_id': user_id, 'title': rec['title'], 'static_weight': rec['sw'], 'dynamic_weight': rec['dw']}


def build_user_roadmap(user_id: str, subject_uid: str | None = None, limit: int = 50) -> List[Dict]:
    repo = Neo4jRepo()
    ensure_weight_defaults_repo(repo)
    repo.ensure_user(user_id)
    if subject_uid:
        rows = repo.read("MATCH (sub:Subject {uid:$su})-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic) OPTIONAL MATCH (:User {id:$uid})-[r:PROGRESS_TOPIC]->(t) RETURN t.uid AS uid, t.title AS title, t.static_weight AS sw, COALESCE(r.dynamic_weight, t.dynamic_weight, t.static_weight) AS dw", {"su": subject_uid, "uid": user_id})
    else:
        rows = repo.read("MATCH (t:Topic) OPTIONAL MATCH (:User {id:$uid})-[r:PROGRESS_TOPIC]->(t) RETURN t.uid AS uid, t.title AS title, t.static_weight AS sw, COALESCE(r.dynamic_weight, t.dynamic_weight, t.static_weight) AS dw", {"uid": user_id})
    items = [{'uid': r['uid'], 'title': r['title'], 'static_weight': r['sw'], 'dynamic_weight': r['dw']} for r in rows]
    items.sort(key=lambda x: (x['dynamic_weight'] or 0.0), reverse=True)
    items = items[:limit]
    roadmap: List[Dict] = []
    for it in items:
        pr = 'high' if (it['dynamic_weight'] or 0.0) >= 0.7 else ('medium' if (it['dynamic_weight'] or 0.0) >= 0.4 else 'low')
        skills_rows = repo.read(
            "MATCH (sub:Subject)-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic {uid:$uid}) MATCH (sub)-[:HAS_SKILL]->(sk:Skill) OPTIONAL MATCH (:User {id:$u})-[r:PROGRESS_SKILL]->(sk) RETURN DISTINCT sk.uid AS uid, sk.title AS title, sk.static_weight AS sw, COALESCE(r.dynamic_weight, sk.dynamic_weight, sk.static_weight) AS dw",
            {"uid": it['uid'], "u": user_id}
        )
        skills = [{'uid': r['uid'], 'title': r['title'], 'static_weight': r['sw'], 'dynamic_weight': r['dw']} for r in skills_rows]
        method_rows = repo.read(
            "MATCH (sub:Subject)-[:CONTAINS]->(:Section)-[:CONTAINS]->(t:Topic {uid:$uid}) MATCH (sub)-[:HAS_SKILL]->(sk:Skill)-[lk:LINKED]->(m:Method) OPTIONAL MATCH (:User {id:$u})-[r:PROGRESS_SKILL]->(sk) RETURN DISTINCT m.uid AS uid, m.title AS title, COALESCE(r.dynamic_weight, sk.dynamic_weight, sk.static_weight) AS weight",
            {"uid": it['uid'], "u": user_id}
        )
        methods = [{'uid': r['uid'], 'title': r['title'], 'weight': r['weight']} for r in method_rows]
        roadmap.append({'topic': it, 'priority': pr, 'skills': skills, 'methods': methods})
    repo.close()
    return roadmap


def fix_orphan_section(section_uid: str, subject_uid: str) -> Dict:
    driver = get_driver()
    with driver.session() as session:
        session.run(
            "MATCH (sub:Subject {uid:$su}), (sec:Section {uid:$uid}) MERGE (sub)-[:CONTAINS]->(sec)",
            su=subject_uid, uid=section_uid
        )
    driver.close()
    return {"fixed": section_uid, "subject": subject_uid}


def compute_static_weights() -> Dict:
    driver = get_driver()
    updated_topics = 0
    updated_skills = 0
    adv_terms = [
        'логарифм','экспонен','диофант','тригонометр','интеграл','предел',
        'комбинатор','вектор','матриц','дифференц','производн','градиент'
    ]

    def score(text: str) -> float:
        t = (text or '').lower()
        tokens = [c for c in t if c.isalnum() or c.isspace()]
        token_count = len(''.join(tokens).split())
        adv = sum(1 for term in adv_terms if term in t)
        base = 0.3
        s = base + min(0.7, 0.02 * token_count + 0.1 * adv)
        return max(0.0, min(1.0, s))

    with driver.session() as session:
        res = session.run("MATCH (t:Topic) RETURN t.uid AS uid, t.title AS title, t.description AS desc")
        for r in res:
            sw = score((r['title'] or '') + ' ' + (r['desc'] or ''))
            session.run(
                "MATCH (t:Topic {uid:$uid}) SET t.static_weight = $sw, t.dynamic_weight = COALESCE(t.dynamic_weight, $sw)",
                uid=r['uid'], sw=sw
            )
            updated_topics += 1

        res = session.run("MATCH (s:Skill) RETURN s.uid AS uid, s.title AS title, s.definition AS def")
        for r in res:
            sw = score((r['title'] or '') + ' ' + (r['def'] or ''))
            session.run(
                "MATCH (s:Skill {uid:$uid}) SET s.static_weight = $sw, s.dynamic_weight = COALESCE(s.dynamic_weight, $sw)",
                uid=r['uid'], sw=sw
            )
            updated_skills += 1

    driver.close()
    return {"topics": updated_topics, "skills": updated_skills}


def add_prereqs_heuristic() -> Dict:
    driver = get_driver()
    created = 0
    with driver.session() as session:
        rules = [
            {"match":"квадратн", "target":"TOP-ALG-QUAD-EQ", "prereqs":["TOP-ALG-LIN-EQ","TOP-ALG-FACTOR"]},
            {"match":"логарифм", "target":"TOP-FUNC-LOG", "prereqs":["TOP-FUNC-EXP"]},
            {"match":"экспонен", "target":"TOP-FUNC-EXP", "prereqs":["TOP-AR-POWERS"]},
            {"match":"тожд", "target":"TOP-TRIG-IDENTITIES", "prereqs":["TOP-TRIG-DEFS","TOP-TRIG-UNIT-CIRCLE"]},
        ]

        for rule in rules:
            # ensure target exists
            tgt = session.run("MATCH (t:Topic {uid:$uid}) RETURN t.uid AS uid", uid=rule['target']).single()
            if not tgt:
                continue
            for pre in rule['prereqs']:
                pr = session.run("MATCH (p:Topic {uid:$uid}) RETURN p.uid AS uid", uid=pre).single()
                if not pr:
                    continue
                session.run(
                    "MATCH (p:Topic {uid:$pre}), (t:Topic {uid:$tgt}) MERGE (t)-[:PREREQ]->(p)",
                    pre=pre, tgt=rule['target']
                )
                created += 1

    driver.close()
    return {"created_prereq_edges": created}


def link_remaining_skills_methods() -> Dict:
    driver = get_driver()
    created = 0
    pairs = [
        ("SKL-CIRCLE-PROPS","MET-GEO-CIRCLE-SECANT"),
        ("SKL-CIRCLE-PROPS","MET-GEO-CIRCLE-CIRCUMSCRIBED"),
        ("SKL-COMBI-COUNT","MET-COMB-PIGEONHOLE"),
        ("SKL-DIFF-RULES","MET-FUNC-PIECEWISE-DERIVATIVE"),
        ("SKL-PROB-CALC","MET-PROB-POISSON"),
        ("SKL-MOD-OPS","MET-NUM-EULER-TOTIENT"),
        ("SKL-AREA-CALC","MET-GEO-SOLID-ANGLES"),
        ("SKL-EXP-RULES","MET-ANA-TAYLOR-SERIES"),
        ("SKL-COORD-OPS","MET-GEO-CIRCLE-POWER"),
        ("SKL-TRANSFORM-APPLY","MET-FUNC-PIECEWISE-CONTINUITY"),
        ("SKL-FUNC-TRANSFORM","MET-FUNC-PIECEWISE-CONTINUITY"),
        ("SKL-DIOPH-SOLVE","MET-NUM-FERMAT-LITTLE"),
        ("SKL-LINE-EQ","MET-VEC-TRIPLE-PRODUCT"),
    ]
    with driver.session() as session:
        for su, mu in pairs:
            ok = session.run(
                "MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) RETURN s.uid AS su, m.uid AS mu",
                su=su, mu=mu
            ).single()
            if not ok:
                continue
            session.run(
                "MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) MERGE (s)-[r:LINKED]->(m) SET r.weight=COALESCE(r.weight,'secondary'), r.confidence=COALESCE(r.confidence,0.8)",
                su=su, mu=mu
            )
            created += 1
    driver.close()
    return {"created_links": created}


def link_skill_to_best(skill_uid: str, method_candidates: List[str]) -> Dict:
    driver = get_driver()
    created = False
    with driver.session() as session:
        for mu in method_candidates:
            ok = session.run(
                "MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) RETURN s.uid AS su, m.uid AS mu",
                su=skill_uid, mu=mu
            ).single()
            if not ok:
                continue
            session.run(
                "MATCH (s:Skill {uid:$su}), (m:Method {uid:$mu}) MERGE (s)-[r:LINKED]->(m) SET r.weight=COALESCE(r.weight,'primary'), r.confidence=COALESCE(r.confidence,0.9)",
                su=skill_uid, mu=mu
            )
            created = True
            break
    driver.close()
    return {"skill": skill_uid, "linked": created}
