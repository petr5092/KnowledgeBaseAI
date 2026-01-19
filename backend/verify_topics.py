
import requests
import json

url = "http://knowledgebase-fastapi-1:8000/v1/engine/topics/available"

# Test Case 1: Class 5
payload_class_5 = {
    "subject_uid": "MATH-FULL-V1",
    "user_context": {
        "user_class": 5,
        "age": 15
    }
}

print("\n--- Testing Class 5 ---")
try:
    r = requests.post(url, json=payload_class_5)
    if r.status_code == 200:
        data = r.json()
        items = data.get("items", [])
        print(f"Items count: {len(items)}")
        
        # Check for topics that should NOT be here (e.g. min > 5 or max < 5)
        errors = []
        for i in items:
            mn = i.get("user_class_min")
            mx = i.get("user_class_max")
            if mn is not None and 5 < mn:
                 errors.append(f"{i['title']} (min {mn} > 5)")
            if mx is not None and 5 > mx:
                 errors.append(f"{i['title']} (max {mx} < 5)")
        
        if errors:
            print("FAIL: Found invalid topics for Class 5:")
            for e in errors[:5]:
                print("  - " + e)
        else:
            print("PASS: All topics valid for Class 5")
            
        # Check for expected topics (e.g. Arithmetic)
        # Assuming we have some (1,4) topics, they should NOT be here for 5 if max is strictly 4
        # But wait, if max is 4, 5 > 4, so it should be excluded.
        
    else:
        print(f"Error: {r.status_code} {r.text}")
except Exception as e:
    print(f"Exception: {e}")

# Test Case 2: Class 10
payload_class_10 = {
    "subject_uid": "MATH-FULL-V1",
    "user_context": {
        "user_class": 10
    }
}

print("\n--- Testing Class 10 ---")
try:
    r = requests.post(url, json=payload_class_10)
    if r.status_code == 200:
        data = r.json()
        items = data.get("items", [])
        print(f"Items count: {len(items)}")
         # Check for topics that should NOT be here
        errors = []
        for i in items:
            mn = i.get("user_class_min")
            mx = i.get("user_class_max")
            if mn is not None and 10 < mn:
                 errors.append(f"{i['title']} (min {mn} > 10)")
            if mx is not None and 10 > mx:
                 errors.append(f"{i['title']} (max {mx} < 10)")
        
        if errors:
            print("FAIL: Found invalid topics for Class 10:")
            for e in errors[:5]:
                print("  - " + e)
        else:
            print("PASS: All topics valid for Class 10")
    else:
        print(f"Error: {r.status_code} {r.text}")
except Exception as e:
    print(f"Exception: {e}")
