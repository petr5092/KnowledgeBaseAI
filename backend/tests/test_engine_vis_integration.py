
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.api.engine import _generate_question_llm, VisualizationType
from app.services.visualization.geometry import GeometryEngine

# Mock Neo4jRepo to avoid DB connection
@pytest.fixture
def mock_neo4j():
    with patch("app.api.engine.Neo4jRepo") as MockRepo:
        repo_instance = MockRepo.return_value
        repo_instance._retry.return_value = "Test Topic" # Mock title
        yield MockRepo

@pytest.mark.asyncio
async def test_generate_question_llm_visual_integration(mock_neo4j):
    # Mock OpenAI response
    mock_response_content = """
    ```json
    {
        "prompt": "Test Question",
        "is_visual": true,
        "visualization": {
            "type": "geometric_shape",
            "coordinates": [
                {"type": "polygon", "points": [{"x": 0, "y": 0}, {"x": 2, "y": 2}, {"x": 2, "y": 0}], "label": "A"}
            ]
        },
        "options": [{"text": "A", "is_correct": true}]
    }
    ```
    """
    
    mock_openai = AsyncMock(return_value={"ok": True, "content": mock_response_content})
    
    with patch("app.api.engine.openai_chat_async", mock_openai):
        # Call the function
        result = await _generate_question_llm(
            topic_uid="topic_123",
            exclude_uids=set(),
            is_visual=True,
            difficulty=5
        )
        
        # Verify visualization is present
        assert result["is_visual"] is True
        assert result["visualization"] is not None
        assert result["visualization"]["type"] == VisualizationType.GEOMETRIC_SHAPE
        
        # Verify coordinates are normalized
        coords = result["visualization"]["coordinates"]
        points = coords[0]["points"]
        
        # Check first point (originally 0,0)
        p1 = points[0]
        # Expecting around 1.0 (since 0->1 in normalization of [0,2] to [1,9] with margin)
        assert abs(p1["x"] - 1.0) < 0.1
        assert abs(p1["y"] - 1.0) < 0.1

@pytest.mark.asyncio
async def test_generate_question_llm_visual_normalization_points_list(mock_neo4j):
    # Test handling of "Mode 1" (list of points) - legacy support
    mock_response_content = """
    ```json
    {
        "prompt": "Test Question",
        "is_visual": true,
        "visualization": {
            "type": "geometric_shape",
            "coordinates": [
                {"x": 0, "y": 0}, {"x": 2, "y": 2}, {"x": 2, "y": 0}
            ]
        },
        "options": [{"text": "A", "is_correct": true}]
    }
    ```
    """
    
    mock_openai = AsyncMock(return_value={"ok": True, "content": mock_response_content})
    
    with patch("app.api.engine.openai_chat_async", mock_openai):
        result = await _generate_question_llm(
            topic_uid="topic_123",
            exclude_uids=set(),
            is_visual=True,
            difficulty=5
        )
        
        assert result["is_visual"] is True
        assert result["visualization"] is not None
        
        # Should have been converted to list of shapes
        coords = result["visualization"]["coordinates"]
        assert isinstance(coords, list)
        assert "points" in coords[0]
        assert len(coords[0]["points"]) == 3
