from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    channel: Optional[str] = None
    agent: Optional[str] = None


class QueryResponse(BaseModel):
    query: str
    response: str
    sources: List[Dict[str, Any]]
    conversation_id: Optional[str] = None
