from typing import Optional, Dict
from pydantic import BaseModel, Field
from app.schemas.context import UserContext

class RoadmapRequest(BaseModel):
    subject_uid: Optional[str] = None
    user_context: UserContext
    limit: int = Field(default=30, ge=1, le=100)
    current_progress: Dict[str, float] = Field(default_factory=dict)
    focus_topic_uid: Optional[str] = None
