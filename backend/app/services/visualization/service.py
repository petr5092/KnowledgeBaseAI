import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from app.services.visualization.geometry import GeometryEngine
from app.services.graph.neo4j_repo import get_driver
from app.services.kb.builder import openai_chat_async
from app.config.settings import settings

logger = logging.getLogger(__name__)

class VisualizationService:
    @staticmethod
    async def generate_visual_question(topic_uid: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a visual question for the given topic, adapting to user context.
        """
        # 1. Fetch Context from Neo4j
        prereqs = VisualizationService._get_prerequisites(topic_uid)
        
        # 2. Calculate Adaptive Difficulty
        difficulty = VisualizationService._calculate_difficulty(user_context)
        
        # 3. Generate Question via LLM
        prompt = VisualizationService._build_prompt(topic_uid, prereqs, difficulty, user_context)
        
        # Retry loop for consistency
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            response = await openai_chat_async([
                {"role": "system", "content": "You are a math question generator specializing in visual geometry problems."},
                {"role": "user", "content": prompt}
            ], temperature=0.7)
            
            if not response.get('ok'):
                error_msg = response.get('error', 'Unknown error')
                logger.error(f"LLM error: {error_msg}")
                last_error = error_msg
                continue
                
            content = response.get('content')
            try:
                # Expecting JSON in markdown block or raw
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                data = json.loads(content)
                
                # 4. Normalize & Validate Visualization
                shapes = data.get("visualization", {}).get("coordinates", [])
                
                # Check consistency flag from LLM
                if not data.get("visualization_matches_text", False):
                    logger.warning(f"LLM reported inconsistency on attempt {attempt}")
                    last_error = "Inconsistency detected"
                    continue
                    
                GeometryEngine.validate(shapes)
                normalized_shapes = GeometryEngine.normalize(shapes)
                
                # Update data with normalized shapes
                if "visualization" not in data:
                     data["visualization"] = {}
                data["visualization"]["coordinates"] = normalized_shapes
                data["difficulty"] = difficulty # Ensure difficulty matches requested
                
                return data
                
            except Exception as e:
                logger.error(f"Failed to parse/validate LLM response: {e}")
                last_error = str(e)
                continue
        
        raise RuntimeError(f"Failed to generate valid visual question after {max_retries} retries. Last error: {last_error}")

    @staticmethod
    def _get_prerequisites(topic_uid: str) -> List[Dict]:
        try:
            driver = get_driver()
            with driver.session() as session:
                result = session.run("""
                    MATCH (t:Topic {uid: $uid})-[:REQUIRES]->(p:Topic)
                    RETURN p.uid as uid, p.title as title
                """, {"uid": topic_uid})
                return [{"uid": r["uid"], "title": r["title"]} for r in result]
        except Exception as e:
            logger.error(f"Failed to fetch prerequisites for {topic_uid}: {e}")
            return []

    @staticmethod
    def _calculate_difficulty(user_context: Dict[str, Any]) -> int:
        # Default logic based on spec
        base = user_context.get("current_difficulty", 5)
        last_correct = user_context.get("last_correct", None)
        response_time = user_context.get("last_response_time", 30)
        
        if last_correct is True:
            base += 1
        elif last_correct is False:
            base -= 1
            
        if response_time < 10:
            base += 0.5
        elif response_time > 60:
            base -= 0.5
            
        # History check (simplified)
        recent_errors = user_context.get("recent_errors", 0)
        if recent_errors >= 2:
            base -= 2
            
        return max(1, min(10, int(round(base))))

    @staticmethod
    def _build_prompt(topic_uid: str, prereqs: List[Dict], difficulty: int, user_context: Dict) -> str:
        # Construct prompt
        return f"""
        Generate a visual math question for Topic: {topic_uid}.
        Prerequisites: {json.dumps(prereqs)}
        Target Difficulty: {difficulty}/10.
        
        Requirements:
        1. Output JSON format strictly.
        2. Visualization must be on 10x10 canvas.
        3. Center main objects at (5,5).
        4. Max 3 objects.
        5. "visualization_matches_text" must be true.
        6. Question text must match coordinates mathematically.
        
        Format:
        {{
            "question_text": "...",
            "options": [...],
            "correct_answer": "...",
            "visualization": {{
                "type": "geometric_shape",
                "coordinates": [
                    {{ "type": "polygon", "points": [{{ "x": ..., "y": ... }}], ... }}
                ],
                "indicators": [...]
            }},
            "visualization_matches_text": true
        }}
        """

    @staticmethod
    def calculate_mastery(accuracy: float, complexity: float, avg_speed: float, consistency_bonus: float) -> float:
        # Mastery = (w1 * Accuracy) + (w2 * Complexity) + (w3 * SpeedFactor) + (w4 * Consistency)
        w1, w2, w3, w4 = 0.5, 0.3, 0.1, 0.1
        
        speed_factor = 1.0 if avg_speed < 30 else max(0.5, 1.0 - (avg_speed - 30)/60)
        
        mastery = (w1 * accuracy) + (w2 * complexity) + (w3 * speed_factor) + (w4 * consistency_bonus)
        return min(1.0, max(0.0, mastery))
