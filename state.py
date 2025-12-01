from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AgentState(BaseModel):
    prompt: str
    classification: List[str] = Field(default_factory=list)
    route_plan: List[str] = Field(default_factory=list)
    route_taken: List[str] = Field(default_factory=list)
    lookup_result: Optional[Dict[str, Any]] = None
    news_result: Optional[NewsState] = None


class NewsState(BaseModel):
    prompt: Optional[str] = None
    company: Optional[str] = None
    items: Optional[int] = None
    rows: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
