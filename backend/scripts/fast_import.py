import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.graph.utils import sync_from_jsonl
from app.services.kb.jsonl_io import load_jsonl, get_path

def main() -> int:
    print("Starting fast import from JSONL to Graph/DB...")
    
    # Debug: check skills.jsonl content
    skills = load_jsonl(get_path('skills.jsonl'))
    check_uid = 'SKL-PRIMENENIE-OSNOVNYE-PONY-28132b'
    found = any(s.get('uid') == check_uid for s in skills)
    print(f"Debug: {check_uid} in skills.jsonl loaded by utils: {found}")
    
    try:
        res = sync_from_jsonl()
        # We need to print the result fully to see errors
        import json
        print("Import result:", json.dumps(res, default=str))
        return 0 if res.get("ok") else 1
    except Exception as e:
        print(f"Error during import: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
