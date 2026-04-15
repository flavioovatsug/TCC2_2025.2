"""
Agente DSPy + tool functions para o Graph RAG.
"""

import os
import time
from contextvars import ContextVar
from typing import Optional

import dspy
from backend import config
from backend.neo4j_client import Neo4jClient

# Rastreia nós acessados durante cada request (thread-safe)
accessed_nodes: ContextVar[Optional[list]] = ContextVar("accessed_nodes", default=None)

# Referência global ao client (setada em setup())
_client: Optional[Neo4jClient] = None


def _track(ids: list):
    lst = accessed_nodes.get(None)
    if lst is not None:
        lst.extend(ids)


# -----------------------------------------------------------------------
# Tool functions (passadas ao dspy.ReAct)
# -----------------------------------------------------------------------

def search_requirements(query: str) -> str:
    """Search the knowledge graph for software requirements matching keywords.
    Use this to find requirements about a specific topic, feature, or domain."""
    results = _client.search_requirements(query, limit=8)
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
    ctx = _client.get_requirement_context(req_id)
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
    members = _client.get_community_requirements(req_id, limit=15)
    if members:
        _track([m["req_id"] for m in members])
    if not members:
        return f"Requisito '{req_id}' nao pertence a nenhuma comunidade."
    cid = members[0].get("community_id", "?")
    lines = [f"Comunidade {cid} — {len(members)} requisitos:"]
    for m in members:
        lines.append(f"  [{m['req_id']}] {m['text']}")
        if m.get("summary"):
            lines.append(f"    Criterios: {m['summary'][:150]}")
    return "\n".join(lines)


def list_techniques() -> str:
    """List all requirements engineering techniques in the knowledge graph."""
    techs = _client.get_all_techniques()
    if not techs:
        return "Nenhuma tecnica encontrada."
    return "\n".join(
        f"[{t['id']}] {t['name']}: {t['description']} (Cat: {t['category']})"
        for t in techs
    )


def list_concepts() -> str:
    """List all requirements engineering concepts in the knowledge graph."""
    concepts = _client.get_all_concepts()
    if not concepts:
        return "Nenhum conceito encontrado."
    return "\n".join(f"[{c['id']}] {c['name']}: {c['definition']}" for c in concepts)


def list_instructions() -> str:
    """List all requirements engineering best practices and guidelines."""
    insts = _client.get_all_instructions()
    if not insts:
        return "Nenhuma instrucao encontrada."
    return "\n".join(f"[{i['id']}] {i['text']} (Ctx: {i['context']})" for i in insts)


def get_graph_overview() -> str:
    """Get statistics about the knowledge graph contents."""
    stats = _client.get_graph_statistics()
    if not stats:
        return "Nao foi possivel obter estatisticas."
    lines = ["Grafo de Conhecimento:"]
    for s in stats:
        lines.append(f"  {s['label']}: {s['count']} nos")
    return "\n".join(lines)


# -----------------------------------------------------------------------
# Agente DSPy (ReAct)
# -----------------------------------------------------------------------

_TOOLS = [
    search_requirements,
    get_requirement_context,
    get_community_context,
    list_techniques,
    list_concepts,
    list_instructions,
    get_graph_overview,
]

_AGENT_INSTRUCTIONS = (
    "Voce eh um especialista em Engenharia de Requisitos (RE). "
    "Voce tem acesso a um grafo de conhecimento com ~700 requisitos "
    "reais de software, tecnicas de RE, instrucoes de boas praticas "
    "e conceitos fundamentais. Use suas ferramentas para buscar e "
    "explorar o grafo antes de responder. Cite IDs de requisitos e "
    "nomes de tecnicas quando relevante. Responda no mesmo idioma da "
    "pergunta (portugues ou ingles). Seja detalhado e fundamentado."
)


class GraphRAGAgent(dspy.Module):
    def __init__(self):
        super().__init__()
        self.react = dspy.ReAct(
            dspy.Signature("question -> answer").with_instructions(_AGENT_INSTRUCTIONS),
            tools=_TOOLS,
            max_iters=8,
        )

    def forward(self, question: str) -> dspy.Prediction:
        return self.react(question=question)


# Instância global (criada em setup())
_agent: Optional[GraphRAGAgent] = None


# -----------------------------------------------------------------------
# Setup e chamada
# -----------------------------------------------------------------------

def setup(client: Neo4jClient):
    """Configura DSPy e cria o agente. Carrega prompt otimizado se disponível."""
    global _client, _agent
    _client = client

    lm = dspy.LM(
        model=config.DSPY_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
    )
    dspy.configure(lm=lm)
    _agent = GraphRAGAgent()
    print(f"[agent] LLM: {config.DSPY_MODEL}")

    # Carrega prompt otimizado se existir (gerado por backend/optimizer.py)
    _compiled_path = os.path.join(os.path.dirname(__file__), "compiled_agent.json")
    if os.path.exists(_compiled_path):
        try:
            _agent.load(_compiled_path)
            print(f"[agent] Prompt otimizado carregado.")
        except Exception as e:
            print(f"[agent] Aviso: compiled_agent.json invalido ({e}). Usando prompt padrao.")


def ask(question: str) -> tuple[str, list[str]]:
    """
    Executa o agente e retorna (answer, accessed_node_ids).
    Inclui retry com backoff para rate limit.
    """
    node_list: list[str] = []
    waits = [5, 15, 30, 60]

    for attempt in range(len(waits) + 1):
        token = accessed_nodes.set(node_list)
        try:
            result = _agent(question=question)
            return result.answer, list(dict.fromkeys(node_list))
        except Exception as e:
            err = str(e)
            is_rate = "429" in err or "RateLimitError" in err or "rate-limited" in err.lower()
            if is_rate and attempt < len(waits):
                wait = waits[attempt]
                print(f"[agent] Rate limit. Retry em {wait}s (tentativa {attempt + 1})...")
                time.sleep(wait)
                node_list.clear()
                continue
            if is_rate:
                raise RuntimeError(
                    "O modelo de IA esta sobrecarregado (rate limit). "
                    "Aguarde alguns minutos ou troque o DSPY_MODEL no .env."
                )
            raise
        finally:
            accessed_nodes.reset(token)
    raise RuntimeError("Maximo de tentativas atingido")
