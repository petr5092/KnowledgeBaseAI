import os
import json
from typing import List, Dict, Set

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'kb')

def load_jsonl(filename: str) -> List[Dict]:
    path = os.path.join(KB_DIR, filename)
    data = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except:
                        pass
    return data

def save_jsonl(filename: str, data: List[Dict]):
    path = os.path.join(KB_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

def main():
    print("Cleaning orphan skills...")
    skills = load_jsonl('skills.jsonl')
    skill_methods = load_jsonl('skill_methods.jsonl')
    
    # Skills that have at least one method
    skills_with_methods = set()
    for sm in skill_methods:
        if sm.get('skill_uid') and sm.get('method_uid'):
            skills_with_methods.add(sm.get('skill_uid'))
            
    print(f"Total skills: {len(skills)}")
    print(f"Skills with methods: {len(skills_with_methods)}")
    
    check_uid = 'SKL-PRIMENENIE-OSNOVNYE-PONY-28132b'
    print(f"Check {check_uid} in skills: {any(s.get('uid') == check_uid for s in skills)}")
    print(f"Check {check_uid} in skill_methods: {check_uid in skills_with_methods}")

    valid_skills = [s for s in skills if s.get('uid') in skills_with_methods]
    removed_count = len(skills) - len(valid_skills)
    
    print(f"Removing {removed_count} skills without methods...")
    save_jsonl('skills.jsonl', valid_skills)
    
    # Also clean up topic_skills and example_skills
    valid_skill_uids = {s.get('uid') for s in valid_skills}
    
    topic_skills = load_jsonl('topic_skills.jsonl')
    valid_topic_skills = [ts for ts in topic_skills if ts.get('skill_uid') in valid_skill_uids]
    if len(topic_skills) != len(valid_topic_skills):
        print(f"Removing {len(topic_skills) - len(valid_topic_skills)} invalid topic_skills...")
        save_jsonl('topic_skills.jsonl', valid_topic_skills)

    example_skills = load_jsonl('example_skills.jsonl')
    valid_example_skills = [es for es in example_skills if es.get('skill_uid') in valid_skill_uids]
    if len(example_skills) != len(valid_example_skills):
        print(f"Removing {len(example_skills) - len(valid_example_skills)} invalid example_skills...")
        save_jsonl('example_skills.jsonl', valid_example_skills)
        
    print("Done cleaning.")

if __name__ == "__main__":
    main()
