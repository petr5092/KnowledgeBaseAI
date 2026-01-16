from typing import Optional, List, Any
from pydantic import BaseModel, Field

class UserContext(BaseModel):
    user_class: Optional[int] = None
    age: Optional[int] = None
    level: Optional[int] = None  # Unified level field
    language: str = "ru"         # Default language
    country: Optional[str] = None
    timezone: Optional[str] = None
    preferences: dict[str, Any] = Field(default_factory=dict)
