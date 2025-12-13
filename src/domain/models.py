from typing import List, Literal
from pydantic import BaseModel, Field, ConfigDict

class Concept(BaseModel):
    model_config = ConfigDict(strict=True)
    uid: str
    title: str
    definition: str
    embedding: List[float] = Field(default_factory=list)

class Skill(BaseModel):
    model_config = ConfigDict(strict=True)
    uid: str
    title: str
    description: str = ""

class Misconception(BaseModel):
    model_config = ConfigDict(strict=True)
    uid: str
    title: str
    explanation: str
    concept_uid: str

class Relation(BaseModel):
    model_config = ConfigDict(strict=True)
    from_uid: str
    to_uid: str
    type: Literal["IS_PREREQUISITE", "IS_PART_OF"]
    weight: float = Field(ge=0.0, le=1.0)
