from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, List

router = APIRouter(prefix="/v1/graph")

class ViewportQuery(BaseModel):
    x: float
    y: float
    zoom: float

@router.get("/viewport")
async def viewport(x: float, y: float, zoom: float) -> Dict:
    return {"nodes": [], "edges": [], "viewport": {"x": x, "y": y, "zoom": zoom}}

class ChatInput(BaseModel):
    question: str

@router.post("/chat")
async def chat(payload: ChatInput) -> Dict:
    return {"answer": "", "question": payload.question}
