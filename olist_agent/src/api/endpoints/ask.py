from fastapi import APIRouter, Request

from src.models import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/ask", response_model=QueryResponse)
async def ask(body: QueryRequest, request: Request) -> QueryResponse:
    return await request.app.state.agent_service.process_query(body)
