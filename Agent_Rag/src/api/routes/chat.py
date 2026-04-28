"""
POST /api/chat — SSE streaming do agente DSPy.
"""

import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.service.chat_service import ChatService

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)

_chat_service: ChatService = None  # type: ignore


def init(chat_service: ChatService):
    global _chat_service
    _chat_service = chat_service


class ChatRequest(BaseModel):
    question: str


@router.post("/api/chat")
async def chat_stream(request: ChatRequest):
    async def generate():
        loop = asyncio.get_event_loop()

        yield f"data: {json.dumps({'type': 'thinking', 'content': 'Consultando o grafo...'})}\n\n"
        await asyncio.sleep(0)

        try:
            answer, node_ids = await loop.run_in_executor(
                _executor, _chat_service.answer, request.question
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield 'data: {"type": "done"}\n\n'
            return

        if node_ids:
            yield f"data: {json.dumps({'type': 'accessed_nodes', 'node_ids': node_ids})}\n\n"
            await asyncio.sleep(0)

        for char in answer:
            yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"
            await asyncio.sleep(0.012)

        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
