
import pytest
from unittest.mock import MagicMock, patch
from app.api.engine import topics_available, TopicsAvailableRequest, GoalType, ExamType, UserContext, _filter_rows

@pytest.mark.asyncio
async def test_filter_logic_ege_with_none():
    # Test _filter_rows directly
    
    rows = [
        {"topic_uid": "T1", "user_class_min": 5, "user_class_max": 10},  # Standard
        {"topic_uid": "T2", "user_class_min": 11, "user_class_max": 11}, # Grade 11
        {"topic_uid": "T3", "user_class_min": None, "user_class_max": None}, # Unknown
        {"topic_uid": "T4", "user_class_min": 12, "user_class_max": 12}, # University?
    ]
    
    # Payload for EGE Profile
    payload = TopicsAvailableRequest(
        user_context=UserContext(language="ru"),
        goal_type=GoalType.exam,
        exam_type=ExamType.ege_profile
    )
    
    # Current logic (strict)
    # T1: min=5 <= 11 -> Keep
    # T2: min=11 <= 11 -> Keep
    # T3: min=None -> Exclude (because of "if mn is None ...")
    # T4: min=12 > 11 -> Exclude
    
    filtered = _filter_rows(rows, None, payload, 0)
    uids = [r["topic_uid"] for r in filtered]
    
    print(f"Filtered UIDs: {uids}")
    
    # Check what is currently happening
    assert "T1" in uids
    assert "T2" in uids
    # T3 is currently excluded by my recent change. 
    # If the user says "missing topics", and T3 represents those, we need to include it.
    assert "T3" not in uids 

