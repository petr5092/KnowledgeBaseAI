import os
import json
from typing import List, Dict

from flask import Flask, jsonify, request, render_template, redirect, url_for
from neo4j_utils import build_graph_from_neo4j, analyze_knowledge, sync_from_jsonl


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE_DIR, 'kb')


def load_jsonl(filepath: str) -> List[Dict]:
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
                # skip bad lines silently in UI context
                continue
    return data


def append_jsonl(filepath: str, record: Dict) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_graph(subject_filter: str | None = None) -> Dict:
    subjects = load_jsonl(os.path.join(KB_DIR, 'subjects.jsonl'))
    sections = load_jsonl(os.path.join(KB_DIR, 'sections.jsonl'))
    topics = load_jsonl(os.path.join(KB_DIR, 'topics.jsonl'))
    skills = load_jsonl(os.path.join(KB_DIR, 'skills.jsonl'))
    methods = load_jsonl(os.path.join(KB_DIR, 'methods.jsonl'))
    skill_methods = load_jsonl(os.path.join(KB_DIR, 'skill_methods.jsonl'))
    topic_goals = load_jsonl(os.path.join(KB_DIR, 'topic_goals.jsonl'))
    topic_objectives = load_jsonl(os.path.join(KB_DIR, 'topic_objectives.jsonl'))

    nodes = []
    edges = []

    subj_uids = set()
    if subject_filter:
        subj_uids = {subject_filter}
    else:
        subj_uids = {s.get('uid') for s in subjects}

    # subjects
    for s in subjects:
        if s.get('uid') not in subj_uids:
            continue
        nodes.append({
            'data': {
                'id': s.get('uid'),
                'label': s.get('title'),
                'type': 'subject'
            }
        })

    # sections with edges to subject
    for sec in sections:
        if sec.get('subject_uid') not in subj_uids:
            continue
        nodes.append({
            'data': {
                'id': sec.get('uid'),
                'label': sec.get('title'),
                'type': 'section'
            }
        })
        edges.append({
            'data': {
                'id': f"{sec.get('subject_uid')}->{sec.get('uid')}",
                'source': sec.get('subject_uid'),
                'target': sec.get('uid'),
                'rel': 'contains'
            }
        })

    # topics with edges to section
    allowed_sections = {sec.get('uid') for sec in sections if sec.get('subject_uid') in subj_uids}
    for t in topics:
        if t.get('section_uid') not in allowed_sections:
            continue
        nodes.append({
            'data': {
                'id': t.get('uid'),
                'label': t.get('title'),
                'type': 'topic'
            }
        })
        edges.append({
            'data': {
                'id': f"{t.get('section_uid')}->{t.get('uid')}",
                'source': t.get('section_uid'),
                'target': t.get('uid'),
                'rel': 'contains'
            }
        })

    # topic goals and objectives
    goal_by_topic = {}
    for g in topic_goals:
        tuid = g.get('topic_uid')
        gid = g.get('uid') or f"GOAL-{tuid}-{abs(hash(g.get('title','')))%100000}"
        goal_by_topic.setdefault(tuid, []).append({'uid': gid, 'title': g.get('title')})
    for obj in topic_objectives:
        tuid = obj.get('topic_uid')
        oid = obj.get('uid') or f"OBJ-{tuid}-{abs(hash(obj.get('title','')))%100000}"
        goal_by_topic.setdefault(tuid, []).append({'uid': oid, 'title': obj.get('title'), 'is_objective': True})

    for tuid, items in goal_by_topic.items():
        # only add nodes if topic is present in allowed graph
        if not any(n.get('data', {}).get('id') == tuid for n in nodes):
            continue
        for it in items:
            nodes.append({
                'data': {
                    'id': it['uid'],
                    'label': it['title'],
                    'type': 'objective' if it.get('is_objective') else 'goal'
                }
            })
            edges.append({
                'data': {
                    'id': f"{tuid}->{it['uid']}",
                    'source': tuid,
                    'target': it['uid'],
                    'rel': 'targets'
                }
            })

    # skills, grouped by subject (edge to subject for now)
    for sk in skills:
        if sk.get('subject_uid') not in subj_uids:
            continue
        nodes.append({
            'data': {
                'id': sk.get('uid'),
                'label': sk.get('title'),
                'type': 'skill'
            }
        })
        edges.append({
            'data': {
                'id': f"{sk.get('subject_uid')}->{sk.get('uid')}",
                'source': sk.get('subject_uid'),
                'target': sk.get('uid'),
                'rel': 'has_skill'
            }
        })

    # methods
    for m in methods:
        nodes.append({
            'data': {
                'id': m.get('uid'),
                'label': m.get('title'),
                'type': 'method'
            }
        })

    # skill-method edges
    for sm in skill_methods:
        if sm.get('skill_uid') is None or sm.get('method_uid') is None:
            continue
        edges.append({
            'data': {
                'id': f"{sm.get('skill_uid')}->{sm.get('method_uid')}",
                'source': sm.get('skill_uid'),
                'target': sm.get('method_uid'),
                'rel': sm.get('weight', 'linked')
            }
        })

    return {'nodes': nodes, 'edges': edges}


app = Flask(__name__)


@app.route('/')
def index():
    return redirect(url_for('knowledge'))


@app.route('/knowledge')
def knowledge():
    # preload subjects for selector
    subjects = load_jsonl(os.path.join(KB_DIR, 'subjects.jsonl'))
    return render_template('knowledge.html', subjects=subjects)


@app.get('/api/graph')
def api_graph():
    subject_uid = request.args.get('subject_uid')
    if os.getenv('NEO4J_URI') and os.getenv('NEO4J_USER') and os.getenv('NEO4J_PASSWORD'):
        graph = build_graph_from_neo4j(subject_uid)
    else:
        graph = build_graph(subject_uid)
    return jsonify(graph)


def make_uid(prefix: str, title: str) -> str:
    base = ''.join(ch for ch in title.upper() if ch.isalnum())
    base = base[:18] if base else 'ITEM'
    return f"{prefix}-{base}"


@app.post('/api/subjects')
def api_add_subject():
    payload = request.get_json(force=True)
    title = payload.get('title')
    description = payload.get('description', '')
    uid = payload.get('uid') or make_uid('SUB', title)
    record = {'uid': uid, 'title': title, 'description': description}
    append_jsonl(os.path.join(KB_DIR, 'subjects.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/sections')
def api_add_section():
    payload = request.get_json(force=True)
    title = payload.get('title')
    description = payload.get('description', '')
    subject_uid = payload.get('subject_uid')
    uid = payload.get('uid') or make_uid('SEC', title)
    record = {'uid': uid, 'subject_uid': subject_uid, 'title': title, 'description': description}
    append_jsonl(os.path.join(KB_DIR, 'sections.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/topics')
def api_add_topic():
    payload = request.get_json(force=True)
    title = payload.get('title')
    description = payload.get('description', '')
    section_uid = payload.get('section_uid')
    uid = payload.get('uid') or make_uid('TOP', title)
    record = {
        'uid': uid,
        'section_uid': section_uid,
        'title': title,
        'description': description,
        # sensible defaults for thresholds
        'accuracy_threshold': 0.85,
        'critical_errors_max': 0,
        'median_time_threshold_seconds': 600,
    }
    append_jsonl(os.path.join(KB_DIR, 'topics.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/skills')
def api_add_skill():
    payload = request.get_json(force=True)
    title = payload.get('title')
    definition = payload.get('definition', '')
    subject_uid = payload.get('subject_uid')
    uid = payload.get('uid') or make_uid('SKL', title)
    record = {'uid': uid, 'subject_uid': subject_uid, 'title': title, 'definition': definition}
    append_jsonl(os.path.join(KB_DIR, 'skills.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/methods')
def api_add_method():
    payload = request.get_json(force=True)
    title = payload.get('title')
    method_text = payload.get('method_text', '')
    applicability_types = payload.get('applicability_types', [])
    uid = payload.get('uid') or make_uid('MET', title)
    record = {'uid': uid, 'title': title, 'method_text': method_text, 'applicability_types': applicability_types}
    append_jsonl(os.path.join(KB_DIR, 'methods.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/topic_goals')
def api_add_topic_goal():
    payload = request.get_json(force=True)
    title = payload.get('title')
    topic_uid = payload.get('topic_uid')
    uid = payload.get('uid') or make_uid('GOAL', title)
    record = {'uid': uid, 'topic_uid': topic_uid, 'title': title}
    append_jsonl(os.path.join(KB_DIR, 'topic_goals.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/topic_objectives')
def api_add_topic_objective():
    payload = request.get_json(force=True)
    title = payload.get('title')
    topic_uid = payload.get('topic_uid')
    uid = payload.get('uid') or make_uid('OBJ', title)
    record = {'uid': uid, 'topic_uid': topic_uid, 'title': title}
    append_jsonl(os.path.join(KB_DIR, 'topic_objectives.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/skill_methods')
def api_link_skill_method():
    payload = request.get_json(force=True)
    skill_uid = payload.get('skill_uid')
    method_uid = payload.get('method_uid')
    weight = payload.get('weight', 'primary')
    confidence = float(payload.get('confidence', 0.9))
    is_auto_generated = bool(payload.get('is_auto_generated', False))
    record = {
        'skill_uid': skill_uid,
        'method_uid': method_uid,
        'weight': weight,
        'confidence': confidence,
        'is_auto_generated': is_auto_generated
    }
    append_jsonl(os.path.join(KB_DIR, 'skill_methods.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/neo4j_sync')
def api_neo4j_sync():
    stats = sync_from_jsonl()
    return jsonify({'ok': True, 'stats': stats})


@app.get('/api/analysis')
def api_analysis():
    subject_uid = request.args.get('subject_uid')
    metrics = analyze_knowledge(subject_uid)
    return jsonify({'ok': True, 'metrics': metrics})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
