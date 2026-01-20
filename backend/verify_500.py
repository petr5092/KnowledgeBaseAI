import requests
import json
import time

API_URL = "http://localhost:8000/v1/assessment/start"
PAYLOAD = {
    "subject_uid": "MATH-FULL-V1",
    "topic_uid": "TOP-PARAMETRICHESKAYA-I-NEPA-301947",
    "user_context": {"user_class": 7}
}

def test_api():
    print(f"Testing {API_URL}...")
    for i in range(1, 6):
        print(f"Request {i}...")
        try:
            start_time = time.time()
            resp = requests.post(API_URL, json=PAYLOAD)
            duration = time.time() - start_time
            print(f"Status: {resp.status_code}, Time: {duration:.2f}s")
            if resp.status_code != 200:
                print(f"Error: {resp.text}")
            else:
                data = resp.json()
                print("Success")
        except Exception as e:
            print(f"Exception: {e}")
        time.sleep(1)

if __name__ == "__main__":
    test_api()
