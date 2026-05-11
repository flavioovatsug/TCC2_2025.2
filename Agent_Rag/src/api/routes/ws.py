"""
WS /ws/chat — streaming do agente DSPy via WebSocket.

Protocolo (JSON):
  Cliente → {"type": "chat",  "question": "...", "graph_id": "default"}
  Cliente → {"type": "ping"}
  Servidor → {"type": "thinking", "content": "..."}
  Servidor → {"type": "token",   "content": "..."}
  Servidor → {"type": "accessed_nodes", "node_ids": [...]}
  Servidor → {"type": "progress", "message": "...", "percent": 0-100}
  Servidor → {"type": "graph_created", "graph_id": "...", "name": "...", "node_count": N}
  Servidor → {"type": "done"}
  Servidor → {"type": "error",   "content": "..."}
  Servidor → {"type": "pong"}
"""

import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.service.chat_service import ChatService
from src.infra.dspy.agent import push_event

router = APIRouter()
_executor = ThreadPoolExecutor(max_workers=4)
_chat_service: ChatService = None  # type: ignore


def init(chat_service: ChatService):
    global _chat_service
    _chat_service = chat_service


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "chat":
                question = (data.get("question") or "").strip()
                graph_id = data.get("graph_id") or "default"
                if question:
                    await _stream_response(websocket, question, graph_id)
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass


async def _stream_response(websocket: WebSocket, question: str, graph_id: str):
    import logging
    log = logging.getLogger("ws.chat")
    log.info(f"[WS] question={question!r} graph_id={graph_id!r}")
    print(f"[WS] ▶ question={question!r} | graph_id={graph_id!r}")

    await websocket.send_json(
        {"type": "thinking", "content": "Consultando o grafo..."}
    )
    print("[WS] → event:thinking")

    loop = asyncio.get_event_loop()

    # Callback thread-safe que envia eventos de progresso do tool para o WebSocket
    def make_pusher():
        def _push(event: dict):
            etype = event.get('type')
            pct = event.get('percent', '')
            msg = str(event.get('message', ''))[:60]
            print(f"[WS] -> push event: type={etype} pct={pct} msg={msg}")
            future = asyncio.run_coroutine_threadsafe(
                websocket.send_json(event), loop
            )
            try:
                future.result(timeout=5)
            except Exception as e:
                print(f"[WS] push failed: {e}")
        return _push

    token_push = push_event.set(make_pusher())
    try:
        print("[WS] ⏳ running agent...")
        # copy_context() captura o ContextVar (push_event, etc.) para dentro da thread
        # run_in_executor NÃO propaga ContextVars automaticamente
        ctx = contextvars.copy_context()
        answer, node_ids = await loop.run_in_executor(
            _executor,
            lambda: ctx.run(_chat_service.answer, question, graph_id=graph_id),
        )
        print(f"[WS] ✓ agent done | answer_len={len(answer)} | nodes={node_ids}")
    except Exception as e:
        print(f"[WS] ✗ agent error: {e}")
        await websocket.send_json({"type": "error", "content": str(e)})
        await websocket.send_json({"type": "done"})
        return
    finally:
        push_event.reset(token_push)

    if node_ids:
        print(f"[WS] → event:accessed_nodes count={len(node_ids)}")
        await websocket.send_json({"type": "accessed_nodes", "node_ids": node_ids})

    # Envia resposta em chunks de 4 chars para dar sensação de streaming
    chunk_size = 4
    for i in range(0, len(answer), chunk_size):
        await websocket.send_json({"type": "token", "content": answer[i : i + chunk_size]})
        await asyncio.sleep(0.010)

    print("[WS] → event:done")
    await websocket.send_json({"type": "done"})
