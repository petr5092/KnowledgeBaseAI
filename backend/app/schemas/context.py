from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class UserContext(BaseModel):
    language: str = "ru"
    attributes: Dict[str, Any] = Field(default_factory=dict)
