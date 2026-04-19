"""
query.py — SSE streaming answer endpoint.

POST /api/query
Body: {"question": "...", "max_articles": 5}

Response: text/event-stream
Each event: data: <JSON>\n\n
Terminated with: data: [DONE]\n\n
"""
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    max_articles: int = Field(default=5, ge=1, le=20)


async def _event_stream(
    request: Request, question: str, max_articles: int
) -> AsyncGenerator[str, None]:
    query_service = request.app.state.query_service
    async for event in query_service.stream(question, max_articles=max_articles):
        yield f"data: {json.dumps(event)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/query")
async def query_endpoint(body: QueryRequest, request: Request):
    return StreamingResponse(
        _event_stream(request, body.question, body.max_articles),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
