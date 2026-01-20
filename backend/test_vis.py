import sys
import os
import asyncio
import json
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

# Need to mock settings before importing app.api.assessment because it imports app.config.settings
with patch('app.config.settings.settings') as mock_settings:
    mock_settings.neo4j_uri = "bolt://localhost:7687"
    from app.api.assessment import _generate_question_llm, VisualizationType

async def test_generation():
    print("Testing Visualization Generation...")

    # Mock Neo4jRepo
    with patch('app.api.assessment.Neo4jRepo') as MockRepo:
        repo_instance = MockRepo.return_value
        # Mock _retry to return the title directly
        repo_instance._retry.return_value = "Geometry Basics"
        
        # Mock openai_chat_async
        with patch('app.api.assessment.openai_chat_async') as mock_openai:
            mock_response_content = {
                "prompt": "Calculate area of the triangle",
                "options": [{"text": "6", "is_correct": True}],
                "is_visual": True,
                "visualization": {
                    "type": "geometric_shape",
                    "coordinates": [{"x": 0, "y": 0}, {"x": 3, "y": 0}, {"x": 0, "y": 4}],
                    "params": {"color": "red"}
                }
            }
            mock_openai.return_value = {
                "ok": True,
                "content": "```json\n" + json.dumps(mock_response_content) + "\n```"
            }
            
            # Call function
            # Note: topic_uid "topic_123" will correspond to "Geometry Basics" via mock
            result = await _generate_question_llm("topic_123", set(), previous_prompts=["Avoid this prompt"])
            
            # Verify prompt content
            call_args = mock_openai.call_args
            prompt_sent = call_args[0][0][0]["content"]
            if "Avoid this prompt" not in prompt_sent:
                print("FAILED: Previous prompts not found in LLM prompt")
                return
            else:
                print("PASSED: Previous prompts included in LLM prompt")

            # Verify result
            print(f"Result is_visual: {result.get('is_visual')}")
            print(f"Result visualization: {result.get('visualization')}")
            
            if result.get('is_visual') is not True:
                print("FAILED: is_visual is not True")
                return

            vis = result.get('visualization')
            if not vis:
                print("FAILED: visualization is None")
                return
                
            # Handle both dict and object (in case implementation changes)
            vis_type = vis.get("type") if isinstance(vis, dict) else vis.type
            vis_coords = vis.get("coordinates") if isinstance(vis, dict) else vis.coordinates

            if vis_type != "geometric_shape" and vis_type != VisualizationType.GEOMETRIC_SHAPE:
                print(f"FAILED: Unexpected type {vis_type}")
                return
                
            if len(vis_coords) != 3:
                print(f"FAILED: Coordinates length {len(vis_coords)}")
                return
                
            print("Test Passed!")

if __name__ == "__main__":
    asyncio.run(test_generation())
