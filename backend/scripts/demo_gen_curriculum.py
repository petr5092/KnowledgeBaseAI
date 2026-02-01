import requests
import json
import os
import time
import uuid

API_URL = "http://localhost:8000/v1"

def login():
    # Use bootstrap admin credentials from env or fallback
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "devops@xteam.pro")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "gfhjkmvfhjkm")
    
    print(f"Logging in as {email}...")
    
    # Payload for login (JSON)
    login_data = {
        "email": email,
        "password": password
    }
    
    try:
        # Try login
        r = requests.post(f"{API_URL}/auth/login", json=login_data)
        if r.status_code == 200:
            return r.json()["access_token"]
        
        print(f"Login failed: {r.status_code} {r.text}")
        return None
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

def generate_curriculum(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": "root"
    }
    payload = {
        "goal": "Подготовка к экзамену по математике (ОГЭ)",
        "audience": "Школьники 9 класса",
        "language": "ru"
    }
    print(f"Sending generation request for: {payload['goal']}")
    start = time.time()
    r = requests.post(f"{API_URL}/admin/curriculum/generate", json=payload, headers=headers, timeout=120)
    elapsed = time.time() - start
    print(f"Time taken: {elapsed:.2f}s")
    print(f"Status: {r.status_code}")
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except:
        print(r.text)

if __name__ == "__main__":
    # Wait for service to be ready
    time.sleep(2)
    token = login()
    if token:
        print("Logged in successfully.")
        generate_curriculum(token)
    else:
        print("Could not log in.")
