
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api.engine import TopicsAvailableResponse

client = TestClient(app)

def test_topics_available_with_curriculum():
    # Mock Neo4jRepo
    with patch("app.api.engine.Neo4jRepo") as MockRepo:
        mock_repo_instance = MockRepo.return_value
        
        # Mock get_graph_view
        with patch("app.api.engine.get_graph_view") as mock_get_gv:
            # Setup mocks
            mock_get_gv.return_value = {
                "ok": True, 
                "nodes": [{"canonical_uid": "TOP-1"}]
            }
            
            # Define side_effect for repo.read to handle different queries
            def repo_read_side_effect(query, params=None):
                # 1. Curriculum expansion query
                if "UNWIND $roots" in query:
                    return [{"uids": ["TOP-1", "TOP-PRE-1"]}]
                
                # 2. Topics query (Block 1)
                if "MATCH (sub:Subject {uid:$su})" in query:
                    return [
                        {"topic_uid": "TOP-1", "title": "Topic 1", "user_class_min": 1, "user_class_max": 11},
                        {"topic_uid": "TOP-2", "title": "Topic 2", "user_class_min": 1, "user_class_max": 11},
                        {"topic_uid": "TOP-PRE-1", "title": "Pre Topic 1", "user_class_min": 1, "user_class_max": 11}
                    ]
                return []

            mock_repo_instance.read.side_effect = repo_read_side_effect
            
            # Payload
            payload = {
                "subject_uid": "SUB-1",
                "user_context": {"user_class": 5},
                "curriculum_code": "TEST-CURR"
            }
            
            response = client.post("/v1/engine/topics/available", json=payload)
            
            assert response.status_code == 200
            data = response.json()
            items = data["items"]
            
            # Should contain TOP-1 and TOP-PRE-1, but NOT TOP-2
            uids = {item["topic_uid"] for item in items}
            assert "TOP-1" in uids
            assert "TOP-PRE-1" in uids
            assert "TOP-2" not in uids
            
            # Verify mocks were called
            mock_get_gv.assert_called_with("TEST-CURR")
            assert mock_repo_instance.read.call_count >= 2

def test_topics_available_without_curriculum():
    # Mock Neo4jRepo
    with patch("app.api.engine.Neo4jRepo") as MockRepo:
        mock_repo_instance = MockRepo.return_value
        
        mock_repo_instance.read.return_value = [
            {"topic_uid": "TOP-1", "title": "Topic 1", "user_class_min": 1, "user_class_max": 11},
            {"topic_uid": "TOP-2", "title": "Topic 2", "user_class_min": 1, "user_class_max": 11}
        ]
        
        payload = {
            "subject_uid": "SUB-1",
            "user_context": {"user_class": 5}
        }
        
        response = client.post("/v1/engine/topics/available", json=payload)
        assert response.status_code == 200
        data = response.json()
        uids = {item["topic_uid"] for item in data["items"]}
        assert "TOP-1" in uids
        assert "TOP-2" in uids
