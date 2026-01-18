
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

print("Testing Class 5...")
try:
    response = requests.post(url, json=payload_class_5)
    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])
        print(f"Found {len(items)} topics for Class 5.")
        
        # Check for forbidden topics
        forbidden = ["Регрессионный анализ", "Центральная предельная теорема", "Применение статистических методов"]
        found_forbidden = []
        for item in items:
            if item['title'] in forbidden:
                found_forbidden.append(item)
            if "Тригонометрия" in item['title']:
                 found_forbidden.append(item)

        if found_forbidden:
            print("ERROR: Found topics that should be filtered out:")
            for f in found_forbidden:
                print(f"  - {f['title']} (Min: {f.get('user_class_min')}, Max: {f.get('user_class_max')})")
        else:
            print("SUCCESS: No forbidden topics found.")
            # Print a few valid ones
            print("Examples of valid topics:")
            for i in items[:3]:
                print(f"  - {i['title']} (Min: {i.get('user_class_min')})")

    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Request failed: {e}")

# Test Case 2: Class 10
payload_class_10 = {
    "subject_uid": "MATH-FULL-V1",
    "user_context": {
        "user_class": 10
    }
}

print("\nTesting Class 10...")
try:
    response = requests.post(url, json=payload_class_10)
    if response.status_code == 200:
        data = response.json()
        items = data.get("items", [])
        print(f"Found {len(items)} topics for Class 10.")
        
        # Check if advanced topics are present
        target = "Регрессионный анализ"
        found = any(item['title'] == target for item in items)
        if found:
            print(f"SUCCESS: Found '{target}' for Class 10.")
        else:
            print(f"WARNING: '{target}' not found for Class 10 (might be 11 only or missing?).")
            
    else:
        print(f"Error: {response.status_code}")
except Exception as e:
    print(f"Request failed: {e}")
