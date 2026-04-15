"""
Backend FastAPI para o Agente Graph RAG de Engenharia de Requisitos.
Expõe:
  GET  /api/graph        — nós e arestas do Neo4j para visualização
  POST /api/chat         — chat SSE com streaming do agente DSPy
"""

import sys
import os
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import dspy

# Importa Neo4jRetriever do módulo existente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Knowledge_Graphs"))
from graph_rag import Neo4jRetriever  # noqa: E402

# ---------------------------------------------------------------------------
# Rastreador de nós acessados por requisição (thread-safe via contextvars)
# ---------------------------------------------------------------------------

_accessed_nodes: ContextVar[Optional[list]] = ContextVar("accessed_nodes", default=None)


def _track(node_ids: list):
    lst = _accessed_nodes.get(None)
    if lst is not None:
        lst.extend(node_ids)


# ---------------------------------------------------------------------------
# Ferramentas do agente (com rastreamento de nós)
# ---------------------------------------------------------------------------

retriever: Optional[Neo4jRetriever] = None


def search_requirements(query: str) -> str:
    """Search the knowledge graph for software requirements matching keywords.
    Use this to find requirements about a specific topic, feature, or domain."""
    results = retriever.search_requirements(query, limit=8)
    _track([r["req_id"] for r in results])
    if not results:
        return "Nenhum requisito encontrado para essa busca."
    lines = []
    for r in results:
        lines.append(f"[{r['req_id']}] {r['text']}")
        if r.get("summary"):
            lines.append(f"  Criterios: {r['summary'][:200]}")
    return "\n".join(lines)


def get_requirement_context(req_id: str) -> str:
    """Get full context for a specific requirement by its ID (e.g. 'REQ_0001').
    Returns related techniques, concepts, and best practices."""
    _track([req_id])
    ctx = retriever.get_context_for_requirement(req_id)
    if not ctx:
        return f"Requisito '{req_id}' nao encontrado."
    parts = [f"Requisito [{ctx['req_id']}]: {ctx['text']}"]
    if ctx.get("summary"):
        parts.append(f"Criterios: {ctx['summary']}")
    if ctx.get("type"):
        parts.append(f"Tipo: {ctx['type']}")
    if ctx.get("techniques"):
        parts.append(f"Tecnicas: {', '.join(ctx['techniques'])}")
    if ctx.get("concepts"):
        parts.append(f"Conceitos: {', '.join(ctx['concepts'])}")
    if ctx.get("instructions"):
        parts.append(f"Boas praticas: {'; '.join(ctx['instructions'])}")
    return "\n".join(parts)


def get_community_context(req_id: str) -> str:
    """Get all requirements in the same Louvain community as the given requirement ID.
    Returns a semantically coherent cluster of related requirements."""
    members = retriever.get_community_requirements(req_id, limit=15)
    if members:
        _track([m["req_id"] for m in members])
    if not members:
        return (
            f"Requisito '{req_id}' nao pertence a nenhuma comunidade. "
            "Execute build_communities.py primeiro."
        )
    community_id = members[0].get("community_id", "?")
    lines = [f"Comunidade {community_id} — {len(members)} requisitos relacionados:"]
    for m in members:
        lines.append(f"  [{m['req_id']}] {m['text']}")
        if m.get("summary"):
            lines.append(f"    Criterios: {m['summary'][:150]}")
    return "\n".join(lines)


def list_techniques() -> str:
    """List all requirements engineering techniques in the knowledge graph."""
    techs = retriever.get_all_techniques()
    if not techs:
        return "Nenhuma tecnica encontrada."
    return "\n".join(
        f"[{t['id']}] {t['name']}: {t['description']} (Categoria: {t['category']})"
        for t in techs
    )


def list_concepts() -> str:
    """List all requirements engineering concepts in the knowledge graph."""
    concepts = retriever.get_all_concepts()
    if not concepts:
        return "Nenhum conceito encontrado."
    return "\n".join(
        f"[{c['id']}] {c['name']}: {c['definition']}" for c in concepts
    )


def list_instructions() -> str:
    """List all requirements engineering best practices and guidelines."""
    instructions = retriever.get_all_instructions()
    if not instructions:
        return "Nenhuma instrucao encontrada."
    return "\n".join(
        f"[{i['id']}] {i['text']} (Contexto: {i['context']})" for i in instructions
    )


def get_graph_overview() -> str:
    """Get statistics about the knowledge graph contents."""
    stats = retriever.get_graph_statistics()
    if not stats:
        return "Nao foi possivel obter estatisticas."
    lines = ["Visao geral do Grafo de Conhecimento:"]
    for s in stats:
        lines.append(f"  {s['label']}: {s['count']} nos")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agente DSPy
# ---------------------------------------------------------------------------

class GraphRAGAgent(dspy.Module):
    def __init__(self):
        super().__init__()
        self.agent = dspy.ReAct(
            dspy.Signature("question -> answer").with_instructions(
                "Voce eh um especialista em Engenharia de Requisitos (RE). "
                "Voce tem acesso a um grafo de conhecimento com ~700 requisitos "
                "reais de software (user stories), tecnicas de RE, instrucoes "
                "de boas praticas e conceitos fundamentais. "
                "Use suas ferramentas para buscar e explorar o grafo antes de "
                "responder. Cite IDs de requisitos e nomes de tecnicas quando "
                "relevante. Responda no mesmo idioma da pergunta."
            ),
            tools=[
                search_requirements,
                get_requirement_context,
                get_community_context,
                list_techniques,
                list_concepts,
                list_instructions,
                get_graph_overview,
            ],
            max_iters=8,
        )

    def forward(self, question: str) -> dspy.Prediction:
        return self.agent(question=question)


agent: Optional[GraphRAGAgent] = None
executor = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="RE Expert Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/graph")
def get_graph_data(limit: int = 200):
    """Retorna nós e arestas do grafo para visualização no frontend."""
    nodes = []
    links = []

    # Requirements (paginado)
    reqs = retriever._run(
        """
        MATCH (r:Requirement)
        RETURN r.req_id AS id, r.text AS text, r.summary AS summary,
               r.type AS type, r.domain AS domain, r.communityId AS communityId
        ORDER BY r.req_id LIMIT $limit
        """,
        {"limit": limit},
    )
    req_node_ids = set()
    for r in reqs:
        req_node_ids.add(r["id"])
        text = r.get("text") or ""
        nodes.append({
            "id": r["id"],
            "label": "Requirement",
            "name": text[:60] + ("..." if len(text) > 60 else ""),
            "text": text,
            "summary": r.get("summary") or "",
            "communityId": r.get("communityId"),
        })

    # Technique, Instruction, Concept
    for t in retriever.get_all_techniques():
        nodes.append({
            "id": t["id"], "label": "Technique", "name": t["name"],
            "text": t.get("description") or "", "category": t.get("category") or "",
        })
    for i in retriever.get_all_instructions():
        text = i.get("text") or ""
        nodes.append({
            "id": i["id"], "label": "Instruction",
            "name": text[:50] + ("..." if len(text) > 50 else ""),
            "text": text, "context": i.get("context") or "",
        })
    for c in retriever.get_all_concepts():
        nodes.append({
            "id": c["id"], "label": "Concept", "name": c["name"],
            "text": c.get("definition") or "",
        })

    all_ids = {n["id"] for n in nodes}

    # Relacionamentos não-SIMILAR_TO
    rels = retriever._run(
        """
        MATCH (a)-[r]->(b)
        WHERE type(r) <> 'SIMILAR_TO'
        RETURN
          coalesce(a.req_id, a.tech_id, a.instr_id, a.concept_id) AS source,
          coalesce(b.req_id, b.tech_id, b.instr_id, b.concept_id) AS target,
          type(r) AS type
        LIMIT 2000
        """
    )
    for r in rels:
        if r["source"] in all_ids and r["target"] in all_ids:
            links.append({"source": r["source"], "target": r["target"], "type": r["type"]})

    # Amostra de SIMILAR_TO
    similar = retriever._run(
        """
        MATCH (a:Requirement)-[r:SIMILAR_TO]->(b:Requirement)
        RETURN a.req_id AS source, b.req_id AS target
        LIMIT 300
        """
    )
    for r in similar:
        if r["source"] in all_ids and r["target"] in all_ids:
            links.append({"source": r["source"], "target": r["target"], "type": "SIMILAR_TO"})

    return {"nodes": nodes, "links": links}


# ---------------------------------------------------------------------------
# Chat endpoint (SSE streaming)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str


def _run_agent_sync(question: str, node_list: list) -> str:
    """Executa o agente DSPy de forma síncrona, com retry em caso de rate limit."""
    import time

    max_retries = 4
    wait_seconds = [5, 15, 30, 60]

    for attempt in range(max_retries):
        token = _accessed_nodes.set(node_list)
        try:
            result = agent(question=question)
            return result.answer
        except Exception as e:
            err = str(e)
            is_rate_limit = (
                "429" in err or "RateLimitError" in err or "rate-limited" in err.lower()
            )
            if is_rate_limit and attempt < max_retries - 1:
                wait = wait_seconds[attempt]
                print(f"Rate limit (tentativa {attempt + 1}/{max_retries}). Aguardando {wait}s...")
                time.sleep(wait)
                node_list.clear()  # reset para a próxima tentativa
                continue
            # Erro não-recuperável ou última tentativa
            if is_rate_limit:
                raise Exception(
                    "O modelo de IA está sobrecarregado (rate limit). "
                    "Aguarde alguns minutos e tente novamente, ou troque o "
                    "DSPY_MODEL no arquivo .env por outro modelo gratuito do OpenRouter "
                    "(ex: meta-llama/llama-3.1-8b-instruct:free)."
                )
            raise
        finally:
            _accessed_nodes.reset(token)


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    async def generate():
        node_list: list = []
        loop = asyncio.get_event_loop()

        # Sinaliza que está pensando
        yield f"data: {json.dumps({'type': 'thinking', 'content': 'Consultando o grafo de conhecimento...'})}\n\n"
        await asyncio.sleep(0)

        # Roda o agente em thread pool (DSPy é síncrono)
        try:
            answer = await loop.run_in_executor(
                executor, _run_agent_sync, request.question, node_list
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield 'data: {"type": "done"}\n\n'
            return

        # Emite nós acessados para o frontend destacar no grafo
        unique_nodes = list(dict.fromkeys(node_list))
        if unique_nodes:
            yield f"data: {json.dumps({'type': 'accessed_nodes', 'node_ids': unique_nodes})}\n\n"
            await asyncio.sleep(0)

        # Streaming da resposta caractere por caractere
        for char in answer:
            yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"
            await asyncio.sleep(0.012)

        yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    global retriever, agent
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path)

    model = os.getenv("DSPY_MODEL", "openrouter/google/gemma-4-26b-a4b-it:free")
    lm = dspy.LM(
        model=model,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0.7,
        max_tokens=2048,
    )
    dspy.configure(lm=lm)
    print(f"LLM: {model}")

    retriever = Neo4jRetriever()
    try:
        retriever.ensure_vector_index()
    except Exception:
        pass

    agent = GraphRAGAgent()
    print("Backend pronto em http://localhost:8000")


@app.on_event("shutdown")
async def shutdown():
    if retriever:
        retriever.close()
    executor.shutdown(wait=False)
