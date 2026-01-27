from fastapi.testclient import TestClient
from app.main import app
import pytest
from unittest.mock import patch, MagicMock

client = TestClient(app)

@pytest.fixture
def mock_neo4j():
    with patch("app.api.engine.Neo4jRepo") as MockRepo:
        mock_instance = MockRepo.return_value
        # Setup mock data
        # We need to return a list of topics with different class constraints
        
        # Topic 1: Grade 5-9 (Suitable for OGE, Study Grade 9)
        t1 = {
            "topic_uid": "t1",
            "title": "Topic 1 (5-9)",
            "user_class_min": 5,
            "user_class_max": 9,
            "difficulty_band": "standard",
            "prereq_topic_uids": []
        }
        # Topic 2: Grade 10-11 (Suitable for EGE, Study Grade 11, NOT OGE)
        t2 = {
            "topic_uid": "t2",
            "title": "Topic 2 (10-11)",
            "user_class_min": 10,
            "user_class_max": 11,
            "difficulty_band": "standard",
            "prereq_topic_uids": []
        }
        # Topic 3: Grade 1-4 (Suitable for everyone)
        t3 = {
            "topic_uid": "t3",
            "title": "Topic 3 (1-4)",
            "user_class_min": 1,
            "user_class_max": 4,
            "difficulty_band": "basic",
            "prereq_topic_uids": []
        }
        
        mock_instance.read.return_value = [t1, t2, t3]
        yield mock_instance

def test_topics_available_filtering(mock_neo4j):
    # Mock user context
    user_context = {
        "user_id": "test_user",
        "tenant_id": "default",
        "user_class": 11,  # Grade 11
        "age": 17,
        "attributes": {}
    }
    
    # 1. Study Topics (Grade 11)
    # Expect topics valid for grade 11.
    # t1 (max 9) -> Exclude? Wait, logic says: if resolved < min or resolved > max then exclude.
    # Grade 11 > 9 (max of t1). So t1 excluded.
    # Grade 11 <= 11 (max of t2). So t2 included.
    # Grade 11 > 4 (max of t3). So t3 excluded.
    # Result: [t2]
    resp = client.post("/v1/engine/topics/available", json={
        "subject_title": "Математика",
        "user_context": user_context,
        "goal_type": "study_topics"
    })
    if resp.status_code != 200:
        print(f"Error: {resp.text}")
    assert resp.status_code == 200
    data = resp.json()
    uids = [t["topic_uid"] for t in data["items"]]
    print(f"Study Topics (Grade 11): {uids}")
    assert "t2" in uids
    assert "t1" not in uids
    
    # 2. Exam (OGE)
    # Logic: if exam_type == OGE, exclude if min > 9.
    # t1 (min 5) <= 9. Included.
    # t2 (min 10) > 9. Excluded.
    # t3 (min 1) <= 9. Included.
    # Result: [t1, t3]
    resp_oge = client.post("/v1/engine/topics/available", json={
        "subject_title": "Математика",
        "user_context": user_context,
        "goal_type": "exam",
        "exam_type": "ОГЭ"
    })
    assert resp_oge.status_code == 200
    data_oge = resp_oge.json()
    uids_oge = [t["topic_uid"] for t in data_oge["items"]]
    print(f"OGE Topics: {uids_oge}")
    assert "t1" in uids_oge
    assert "t3" in uids_oge
    assert "t2" not in uids_oge
    
    # 3. Exam (EGE)
    # Logic: if exam_type == EGE, exclude if min > 11.
    # t1 (min 5) <= 11. Included.
    # t2 (min 10) <= 11. Included.
    # t3 (min 1) <= 11. Included.
    # Result: [t1, t2, t3]
    resp_ege = client.post("/v1/engine/topics/available", json={
        "subject_title": "Математика",
        "user_context": user_context,
        "goal_type": "exam",
        "exam_type": "ЕГЭ Профиль"
    })
    assert resp_ege.status_code == 200
    data_ege = resp_ege.json()
    uids_ege = [t["topic_uid"] for t in data_ege["items"]]
    print(f"EGE Topics: {uids_ege}")
    assert "t1" in uids_ege
    assert "t2" in uids_ege
    assert "t3" in uids_ege

if __name__ == "__main__":
    # Manually run if needed, but pytest handles fixtures
    pass
