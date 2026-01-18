
import requests
import json
import sys

# Container internal URL if running from inside another container, 
# or localhost if running from host with port mapping.
# Since we run via docker exec in fastapi container, we can use localhost:8000
BASE_URL = "http://localhost:8000"

def test_roadmap():
    print("\n--- Testing Roadmap ---")
    payload = {
        "subject_uid": "MATH-FULL-V1",
        "current_progress": {},
        "user_context": {"attributes": {"level": 5}}
    }
    try:
        r = requests.post(f"{BASE_URL}/v1/engine/roadmap", json=payload)
        if r.status_code == 200:
            data = r.json()
            nodes = data.get("nodes", [])
            print(f"Roadmap returned {len(nodes)} nodes")
            print(f"Total Roadmap Max Score: {data.get('max_score', 'N/A')}")
            for i, node in enumerate(nodes):
                print(f"\nNode {i+1}: {node.get('title')} ({node.get('status')})")
                print(f"  Max Score: {node.get('max_score', 'N/A')}")
                units = node.get("units", [])
                print(f"  Units: {len(units)}")
                for u in units:
                    print(f"  - [{u.get('type')}] {u.get('title')}")
        else:
            print(f"Error: {r.status_code} - {r.text}")
            sys.exit(1)
    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_roadmap()
