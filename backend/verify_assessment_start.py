
import requests
import json

url = "http://knowledgebase-fastapi-1:8000/v1/assessment/start"

# Test Case: User Class 0 (Should pass now)
payload = {
    "subject_uid": "MATH-FULL-V1",
    "topic_uid": "TOP-SVOISTVA-RASPREDELENII-V-9d066a",
    "user_context": {
        "user_class": 0,
        "age": 0
    }
}

# First, let's verify if the topic actually exists (using a direct neo4j check if possible, or just try the endpoint)
# We can't check neo4j directly easily from python script without driver, but we can assume user's log is correct.
# Or we can query /available first to find a valid topic UID if that one is missing.

# Let's try to get a valid topic from /available first to be sure
avail_url = "http://knowledgebase-fastapi-1:8000/v1/engine/topics/available"
avail_payload = {
    "subject_uid": "MATH-FULL-V1",
    "user_context": {
        "user_class": 10
    }
}
try:
    print("Fetching available topics...")
    r = requests.post(avail_url, json=avail_payload)
    if r.status_code == 200:
        topics = r.json().get("items", [])
        if topics:
            target_topic = topics[0]["topic_uid"]
            print(f"Using topic: {target_topic}")
            payload["topic_uid"] = target_topic
            
            # Now try start with class 0
            print("Testing /assessment/start with user_class=0...")
            resp = requests.post(url, json=payload)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("SUCCESS: Session started.")
                print(resp.json())
            else:
                print("FAILURE: " + resp.text)
        else:
            print("No topics found for class 10.")
    else:
        print(f"Failed to fetch topics: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
