#!/usr/bin/env python3
import os
import time
import json
import requests

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ELASTIC_DIR = os.path.join(BASE_DIR, 'elastic')
KB_DIR = os.path.join(BASE_DIR, 'kb')

ES_URL = os.getenv('ES_URL', 'http://localhost:9200')
ES_USER = os.getenv('ES_USER')
ES_PASSWORD = os.getenv('ES_PASSWORD')
ES_VERIFY_SSL = os.getenv('ES_VERIFY_SSL', 'true').lower() == 'true'
AUTH = (ES_USER, ES_PASSWORD) if ES_USER and ES_PASSWORD else None

INDEX_FILES = {
    'subjects': ('subjects.json', 'subjects.jsonl'),
    'sections': ('sections.json', 'sections.jsonl'),
    'topics': ('topics.json', 'topics.jsonl'),
    'skills': ('skills.json', 'skills.jsonl'),
    'methods': ('methods.json', 'methods.jsonl'),
    'examples': ('examples.json', 'examples.jsonl'),
    'errors': ('errors.json', 'errors.jsonl'),
    'skill_topics': ('skill_topics.json', 'skill_topics.jsonl'),
    'theories': ('theories.json', 'theories.jsonl'),
    'example_skills': ('example_skills.json', 'example_skills.jsonl'),
    'lesson_steps': ('lesson_steps.json', 'lesson_steps.jsonl'),
}

def wait_for_es(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(ES_URL, auth=AUTH, verify=ES_VERIFY_SSL)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError('Elasticsearch is not reachable')

def create_index(index_name, mapping_path):
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)
    url = f"{ES_URL}/{index_name}"
    # Delete if exists for idempotent runs
    requests.delete(url, auth=AUTH, verify=ES_VERIFY_SSL)
    r = requests.put(url, json=mapping, auth=AUTH, verify=ES_VERIFY_SSL)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create index {index_name}: {r.status_code} {r.text}")

def bulk_index(index_name, data_path):
    if not os.path.exists(data_path):
        print(f"Skip {index_name}: {data_path} not found")
        return
    ndjson_lines = []
    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc_id = doc.get('uid') or doc.get('id')
            action = {"index": {"_index": index_name}}
            if doc_id:
                action["index"]["_id"] = doc_id
            ndjson_lines.append(json.dumps(action))
            ndjson_lines.append(json.dumps(doc, ensure_ascii=False))
    if not ndjson_lines:
        print(f"No data to index for {index_name}")
        return
    payload = "\n".join(ndjson_lines) + "\n"
    url = f"{ES_URL}/_bulk"
    headers = {"Content-Type": "application/x-ndjson"}
    r = requests.post(url, data=payload.encode('utf-8'), headers=headers, auth=AUTH, verify=ES_VERIFY_SSL)
    if r.status_code != 200:
        raise RuntimeError(f"Bulk index failed for {index_name}: {r.status_code} {r.text}")
    res = r.json()
    if res.get('errors'):
        # Surface the first error for debugging
        first_error = next((item for item in res.get('items', []) if item.get('index', {}).get('error')), None)
        raise RuntimeError(f"Bulk index errors for {index_name}: {first_error}")
    print(f"Indexed {len(ndjson_lines)//2} docs into {index_name}")

def main():
    wait_for_es()
    for index_name, (mapping_file, data_file) in INDEX_FILES.items():
        mapping_path = os.path.join(ELASTIC_DIR, mapping_file)
        data_path = os.path.join(KB_DIR, data_file)
        print(f"Create index {index_name}")
        create_index(index_name, mapping_path)
        print(f"Bulk index {index_name}")
        bulk_index(index_name, data_path)
    print('Indexing complete')

if __name__ == '__main__':
    main()