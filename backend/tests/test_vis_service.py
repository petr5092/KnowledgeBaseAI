import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.visualization.service import VisualizationService

@pytest.mark.asyncio
async def test_generate_visual_question_success():
    mock_llm_response = {
        "ok": True,
        "content": """
        ```json
        {
            "question_text": "What is the area?",
            "visualization_matches_text": true,
            "visualization": {
                "coordinates": [
                    {"points": [{"x": 0, "y": 0}, {"x": 2, "y": 2}]}
                ]
            }
        }
        ```
        """
    }
    
    with patch("app.services.visualization.service.openai_chat_async", new_callable=AsyncMock) as mock_chat, \
         patch("app.services.visualization.service.get_driver") as mock_driver:
        
        mock_chat.return_value = mock_llm_response
        
        # Mock Neo4j
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = [] # No prereqs
        
        context = {"current_difficulty": 5}
        result = await VisualizationService.generate_visual_question("TOPIC-1", context)
        
        assert result["visualization_matches_text"] is True
        assert "visualization" in result

@pytest.mark.asyncio
async def test_generate_visual_question_retry_on_inconsistency():
    bad_response = {
        "ok": True,
        "content": json.dumps({"visualization_matches_text": False})
    }
    good_response = {
        "ok": True,
        "content": json.dumps({
            "visualization_matches_text": True,
            "visualization": {"coordinates": []}
        })
    }
    
    with patch("app.services.visualization.service.openai_chat_async", new_callable=AsyncMock) as mock_chat, \
         patch("app.services.visualization.service.get_driver") as mock_driver:
         
        mock_chat.side_effect = [bad_response, good_response]
        
        # Mock Neo4j
        mock_session = MagicMock()
        mock_driver.return_value.session.return_value.__enter__.return_value = mock_session
        
        result = await VisualizationService.generate_visual_question("TOPIC-1", {})
        assert result["visualization_matches_text"] is True
        assert mock_chat.call_count == 2

def test_calculate_difficulty():
    # Base 5. Correct (+1), Fast (+0.5) -> 6.5 -> 6
    ctx = {"current_difficulty": 5, "last_correct": True, "last_response_time": 5}
    diff = VisualizationService._calculate_difficulty(ctx)
    assert diff == 6
    
    # Base 5. Wrong (-1), Slow (-0.5) -> 3.5 -> 4 (round half to even)
    ctx = {"current_difficulty": 5, "last_correct": False, "last_response_time": 61}
    diff = VisualizationService._calculate_difficulty(ctx)
    assert diff == 4
    
    # Recent errors penalty (-2)
    ctx = {"current_difficulty": 5, "recent_errors": 2}
    diff = VisualizationService._calculate_difficulty(ctx)
    assert diff == 3  # 5 - 2 = 3

def test_calculate_mastery():
    # Perfect score
    m = VisualizationService.calculate_mastery(1.0, 1.0, 10.0, 1.0)
    # 0.5*1 + 0.3*1 + 0.1*1 + 0.1*1 = 1.0
    assert m == 1.0
    
    # Zero
    m = VisualizationService.calculate_mastery(0.0, 0.0, 100.0, 0.0)
    # Speed factor for 100s: 1 - (70/60) < 0 -> clamped to 0.5
    # 0 + 0 + 0.1*0.5 + 0 = 0.05
    assert abs(m - 0.05) < 0.001
