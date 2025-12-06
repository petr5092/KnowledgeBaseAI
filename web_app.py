import os
import json
from typing import List, Dict

from flask import Flask, jsonify, request, render_template, redirect, url_for
from neo4j_utils import build_graph_from_neo4j, analyze_knowledge, sync_from_jsonl
from neo4j_utils import list_items, get_node_details, search_titles, health


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


def rewrite_jsonl(filepath: str, records: List[Dict]) -> None:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


VALID_UID_PREFIXES = {
    'subjects': ['SUB-'],
    'sections': ['SEC-'],
    'topics': ['TOP-'],
    'skills': ['SKL-'],
    'methods': ['MET-'],
    'topic_goals': ['GOAL-'],
    'topic_objectives': ['OBJ-'],
    'skill_methods': None,
}


def uid_has_valid_prefix(kind: str, uid: str | None) -> bool:
    prefixes = VALID_UID_PREFIXES.get(kind)
    if not prefixes or not uid:
        return True
    return any(uid.startswith(p) for p in prefixes)


def uid_suffix_is_valid(uid: str) -> bool:
    # everything after first '-' must be letters/digits (Unicode) or '-'/'_'
    if '-' not in uid:
        return False
    suffix = uid.split('-', 1)[1]
    for ch in suffix:
        if not (ch.isalnum() or ch in ['-', '_']):
            return False
    return True


def normalize_jsonl_file(filepath: str, kind: str) -> Dict:
    if not os.path.exists(filepath):
        return {'file': os.path.basename(filepath), 'exists': False, 'before': 0, 'after': 0}
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    if text.find('}{') != -1:
        text = text.replace('}{', '}\n{')
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    before = len(lines)
    parsed: List[Dict] = []
    invalid: List[Dict] = []
    warnings: List[Dict] = []
    for l in lines:
        try:
            rec = json.loads(l)
            # basic schema checks
            if kind in {'subjects','sections','topics','skills','methods'}:
                if not isinstance(rec.get('uid'), str) or not rec.get('uid'):
                    invalid.append({'line': l, 'reason': 'missing uid'})
                    continue
                if not uid_has_valid_prefix(kind, rec.get('uid')):
                    invalid.append({'uid': rec.get('uid'), 'reason': 'bad uid prefix'})
                    continue
                if not uid_suffix_is_valid(rec.get('uid')):
                    invalid.append({'uid': rec.get('uid'), 'reason': 'uid suffix must be alnum'})
                    continue
                if kind != 'methods':
                    if not isinstance(rec.get('title'), str) or not rec.get('title').strip():
                        invalid.append({'uid': rec.get('uid'), 'reason': 'missing title'})
                        continue
                    title = rec.get('title').strip()
                    if len(title) < 3:
                        warnings.append({'uid': rec.get('uid'), 'warning': 'title too short (<3)'})
                    if len(title) > 200:
                        warnings.append({'uid': rec.get('uid'), 'warning': 'title too long (>200)'})
                else:
                    if not isinstance(rec.get('title'), str) or not rec.get('title').strip():
                        invalid.append({'uid': rec.get('uid'), 'reason': 'missing title'})
                        continue
                    if not isinstance(rec.get('method_text'), str) or len(rec.get('method_text').strip()) < 10:
                        warnings.append({'uid': rec.get('uid'), 'warning': 'method_text too short (<10)'})
                    if 'applicability_types' in rec and not isinstance(rec.get('applicability_types'), list):
                        warnings.append({'uid': rec.get('uid'), 'warning': 'applicability_types not a list'})
            if kind == 'sections' and not isinstance(rec.get('subject_uid'), str):
                invalid.append({'uid': rec.get('uid'), 'reason': 'missing subject_uid'})
                continue
            if kind == 'topics' and not isinstance(rec.get('section_uid'), str):
                invalid.append({'uid': rec.get('uid'), 'reason': 'missing section_uid'})
                continue
            if kind == 'skills' and not isinstance(rec.get('subject_uid'), str):
                invalid.append({'uid': rec.get('uid'), 'reason': 'missing subject_uid'})
                continue
            if kind == 'skill_methods':
                su, mu = rec.get('skill_uid'), rec.get('method_uid')
                if not isinstance(su, str) or not isinstance(mu, str):
                    invalid.append({'pair': (su, mu), 'reason': 'missing skill_uid/method_uid'})
                    continue
                if not uid_has_valid_prefix('skills', su) or not uid_has_valid_prefix('methods', mu):
                    invalid.append({'pair': (su, mu), 'reason': 'bad uid prefix'})
                    continue
                if not uid_suffix_is_valid(su) or not uid_suffix_is_valid(mu):
                    invalid.append({'pair': (su, mu), 'reason': 'uid suffix must be alnum'})
                    continue
            # description warnings
            if kind in {'subjects','sections','topics'}:
                if not isinstance(rec.get('description'), str) or not rec.get('description').strip():
                    warnings.append({'uid': rec.get('uid'), 'warning': 'empty description'})
            if kind in {'topic_goals','topic_objectives'}:
                if not isinstance(rec.get('topic_uid'), str) or not rec.get('topic_uid').strip():
                    invalid.append({'uid': rec.get('uid'), 'reason': 'missing topic_uid'})
                    continue
                if not isinstance(rec.get('title'), str) or len(rec.get('title').strip()) < 5:
                    invalid.append({'uid': rec.get('uid'), 'reason': 'title too short (<5)'})
                    continue
            parsed.append(rec)
        except json.JSONDecodeError:
            continue
    if kind == 'skill_methods':
        seen = set()
        dedup = []
        for r in parsed:
            key = (r.get('skill_uid'), r.get('method_uid'))
            if key in seen or key[0] is None or key[1] is None:
                continue
            seen.add(key)
            dedup.append(r)
        parsed = dedup
    else:
        seen = set()
        dedup = []
        for r in parsed:
            uid = r.get('uid')
            if not uid or uid in seen:
                continue
            if kind in {'subjects','sections','topics','skills','methods'} and not (r.get('title') or '').strip():
                continue
            seen.add(uid)
            dedup.append(r)
        parsed = dedup
    rewrite_jsonl(filepath, parsed)
    return {'file': os.path.basename(filepath), 'exists': True, 'before': before, 'after': len(parsed), 'invalid': invalid, 'warnings': warnings}


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
    if not title or not subject_uid:
        return jsonify({'ok': False, 'error': 'title and subject_uid are required'}), 400
    uid = payload.get('uid') or make_uid('SEC', title)
    if payload.get('uid') and (not uid_has_valid_prefix('sections', payload.get('uid')) or not uid_suffix_is_valid(payload.get('uid'))):
        return jsonify({'ok': False, 'error': 'bad uid prefix'}), 400
    record = {'uid': uid, 'subject_uid': subject_uid, 'title': title, 'description': description}
    append_jsonl(os.path.join(KB_DIR, 'sections.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/topics')
def api_add_topic():
    payload = request.get_json(force=True)
    title = payload.get('title')
    description = payload.get('description', '')
    section_uid = payload.get('section_uid')
    if not title or not section_uid:
        return jsonify({'ok': False, 'error': 'title and section_uid are required'}), 400
    uid = payload.get('uid') or make_uid('TOP', title)
    if payload.get('uid') and (not uid_has_valid_prefix('topics', payload.get('uid')) or not uid_suffix_is_valid(payload.get('uid'))):
        return jsonify({'ok': False, 'error': 'bad uid prefix'}), 400
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
    if not title or not subject_uid:
        return jsonify({'ok': False, 'error': 'title and subject_uid are required'}), 400
    uid = payload.get('uid') or make_uid('SKL', title)
    if payload.get('uid') and (not uid_has_valid_prefix('skills', payload.get('uid')) or not uid_suffix_is_valid(payload.get('uid'))):
        return jsonify({'ok': False, 'error': 'bad uid prefix'}), 400
    record = {'uid': uid, 'subject_uid': subject_uid, 'title': title, 'definition': definition}
    append_jsonl(os.path.join(KB_DIR, 'skills.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/methods')
def api_add_method():
    payload = request.get_json(force=True)
    title = payload.get('title')
    method_text = payload.get('method_text', '')
    applicability_types = payload.get('applicability_types', [])
    if not title:
        return jsonify({'ok': False, 'error': 'title is required'}), 400
    uid = payload.get('uid') or make_uid('MET', title)
    if payload.get('uid') and (not uid_has_valid_prefix('methods', payload.get('uid')) or not uid_suffix_is_valid(payload.get('uid'))):
        return jsonify({'ok': False, 'error': 'bad uid prefix'}), 400
    record = {'uid': uid, 'title': title, 'method_text': method_text, 'applicability_types': applicability_types}
    append_jsonl(os.path.join(KB_DIR, 'methods.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/topic_goals')
def api_add_topic_goal():
    payload = request.get_json(force=True)
    title = payload.get('title')
    topic_uid = payload.get('topic_uid')
    if not title or not topic_uid:
        return jsonify({'ok': False, 'error': 'title and topic_uid are required'}), 400
    uid = payload.get('uid') or make_uid('GOAL', title)
    if payload.get('uid') and (not uid_has_valid_prefix('topic_goals', payload.get('uid')) or not uid_suffix_is_valid(payload.get('uid'))):
        return jsonify({'ok': False, 'error': 'bad uid prefix'}), 400
    record = {'uid': uid, 'topic_uid': topic_uid, 'title': title}
    append_jsonl(os.path.join(KB_DIR, 'topic_goals.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/topic_objectives')
def api_add_topic_objective():
    payload = request.get_json(force=True)
    title = payload.get('title')
    topic_uid = payload.get('topic_uid')
    if not title or not topic_uid:
        return jsonify({'ok': False, 'error': 'title and topic_uid are required'}), 400
    uid = payload.get('uid') or make_uid('OBJ', title)
    if payload.get('uid') and (not uid_has_valid_prefix('topic_objectives', payload.get('uid')) or not uid_suffix_is_valid(payload.get('uid'))):
        return jsonify({'ok': False, 'error': 'bad uid prefix'}), 400
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
    if not skill_uid or not method_uid:
        return jsonify({'ok': False, 'error': 'skill_uid and method_uid are required'}), 400
    record = {
        'skill_uid': skill_uid,
        'method_uid': method_uid,
        'weight': weight,
        'confidence': confidence,
        'is_auto_generated': is_auto_generated
    }
    if (not uid_has_valid_prefix('skills', skill_uid) or not uid_has_valid_prefix('methods', method_uid) or not uid_suffix_is_valid(skill_uid) or not uid_suffix_is_valid(method_uid)):
        return jsonify({'ok': False, 'error': 'bad uid prefix'}), 400
    append_jsonl(os.path.join(KB_DIR, 'skill_methods.jsonl'), record)
    return jsonify({'ok': True, 'record': record})


@app.post('/api/normalize_kb')
def api_normalize_kb():
    expected = os.getenv('ADMIN_API_KEY')
    provided = request.headers.get('X-API-Key')
    if expected and provided != expected:
        return jsonify({'ok': False, 'error': 'invalid api key'}), 401
    files = [
        ('subjects', os.path.join(KB_DIR, 'subjects.jsonl')),
        ('sections', os.path.join(KB_DIR, 'sections.jsonl')),
        ('topics', os.path.join(KB_DIR, 'topics.jsonl')),
        ('skills', os.path.join(KB_DIR, 'skills.jsonl')),
        ('methods', os.path.join(KB_DIR, 'methods.jsonl')),
        ('skill_methods', os.path.join(KB_DIR, 'skill_methods.jsonl')),
        ('topic_goals', os.path.join(KB_DIR, 'topic_goals.jsonl')),
        ('topic_objectives', os.path.join(KB_DIR, 'topic_objectives.jsonl')),
    ]
    stats = [normalize_jsonl_file(path, kind) for kind, path in files]
    return jsonify({'ok': True, 'stats': stats})


@app.get('/api/list')
def api_list():
    kind = request.args.get('kind')
    subject_uid = request.args.get('subject_uid')
    section_uid = request.args.get('section_uid')
    rows = list_items(kind, subject_uid, section_uid)
    return jsonify({'ok': True, 'items': rows})


@app.get('/api/node_details')
def api_node_details():
    uid = request.args.get('uid')
    details = get_node_details(uid)
    return jsonify({'ok': True, 'details': details})


@app.get('/api/search')
def api_search():
    q = request.args.get('q', '')
    limit = int(request.args.get('limit', '20'))
    items = search_titles(q, limit)
    return jsonify({'ok': True, 'items': items})


@app.get('/health')
def api_health():
    return jsonify(health())


@app.post('/api/delete_record')
def api_delete_record():
    expected = os.getenv('ADMIN_API_KEY')
    provided = request.headers.get('X-API-Key')
    if expected and provided != expected:
        return jsonify({'ok': False, 'error': 'invalid api key'}), 401
    payload = request.get_json(force=True)
    kind = payload.get('type')
    uid = payload.get('uid')
    skill_uid = payload.get('skill_uid')
    method_uid = payload.get('method_uid')
    mapping = {
        'subjects': 'subjects.jsonl',
        'sections': 'sections.jsonl',
        'topics': 'topics.jsonl',
        'skills': 'skills.jsonl',
        'methods': 'methods.jsonl',
        'skill_methods': 'skill_methods.jsonl',
        'topic_goals': 'topic_goals.jsonl',
        'topic_objectives': 'topic_objectives.jsonl',
    }
    if kind not in mapping:
        return jsonify({'ok': False, 'error': 'invalid type'}), 400
    filepath = os.path.join(KB_DIR, mapping[kind])
    data = load_jsonl(filepath)
    before = len(data)
    if kind == 'skill_methods':
        if not skill_uid or not method_uid:
            return jsonify({'ok': False, 'error': 'skill_uid and method_uid are required'}), 400
        data = [r for r in data if not (r.get('skill_uid') == skill_uid and r.get('method_uid') == method_uid)]
    else:
        if not uid:
            return jsonify({'ok': False, 'error': 'uid is required'}), 400
        data = [r for r in data if r.get('uid') != uid]
    rewrite_jsonl(filepath, data)
    return jsonify({'ok': True, 'removed': before - len(data), 'remaining': len(data)})


@app.post('/api/neo4j_sync')
def api_neo4j_sync():
    # simple header-based key protection
    expected = os.getenv('ADMIN_API_KEY')
    provided = request.headers.get('X-API-Key')
    if expected and provided != expected:
        return jsonify({'ok': False, 'error': 'invalid api key'}), 401
    stats = sync_from_jsonl()
    return jsonify({'ok': True, 'stats': stats})


@app.get('/api/analysis')
def api_analysis():
    subject_uid = request.args.get('subject_uid')
    metrics = analyze_knowledge(subject_uid)
    return jsonify({'ok': True, 'metrics': metrics})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
