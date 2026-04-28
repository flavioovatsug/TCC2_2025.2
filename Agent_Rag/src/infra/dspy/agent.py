"""
GraphRAGAgent — DSPy Module que implementa BaseAgent.
"""

import os
import time
from contextvars import ContextVar
from typing import List, Optional

import dspy

from src.core.interfaces import BaseAgent, BaseGraphClient
from src.infra.dspy.signatures import RequirementsQA
from src import config

# Rastreia nós acessados durante cada request (thread-safe via ContextVar)
accessed_nodes: ContextVar[Optional[list]] = ContextVar("accessed_nodes", default=None)


def _track(ids: list):
    lst = accessed_nodes.get(None)
    if lst is not None:
        lst.extend(ids)


def _make_tools(client: BaseGraphClient):
    """Cria closures de tool functions para o agente DSPy."""

    def search_requirements(query: str) -> str:
        """Search the knowledge graph for software requirements matching keywords."""
        results = client.search_requirements(query, limit=8)
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
        """Get full context for a specific requirement by its ID (e.g. 'REQ_0001')."""
        _track([req_id])
        ctx = client.get_requirement_context(req_id)
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
        """Get all requirements in the same Louvain community as the given requirement ID."""
        members = client.get_community_requirements(req_id, limit=15)
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
        techs = client.get_all_techniques()
        if not techs:
            return "Nenhuma tecnica encontrada."
        return "\n".join(
            f"[{t['id']}] {t['name']}: {t['description']} (Cat: {t['category']})"
            for t in techs
        )

    def list_concepts() -> str:
        """List all requirements engineering concepts in the knowledge graph."""
        concepts = client.get_all_concepts()
        if not concepts:
            return "Nenhum conceito encontrado."
        return "\n".join(f"[{c['id']}] {c['name']}: {c['definition']}" for c in concepts)

    def list_instructions() -> str:
        """List all requirements engineering best practices and guidelines."""
        insts = client.get_all_instructions()
        if not insts:
            return "Nenhuma instrucao encontrada."
        return "\n".join(f"[{i['id']}] {i['text']} (Ctx: {i['context']})" for i in insts)

    def get_graph_overview() -> str:
        """Get statistics about the knowledge graph contents."""
        stats = client.get_graph_statistics()
        if not stats:
            return "Nao foi possivel obter estatisticas."
        lines = ["Grafo de Conhecimento:"]
        for s in stats:
            lines.append(f"  {s['label']}: {s['count']} nos")
        return "\n".join(lines)

    return [
        search_requirements,
        get_requirement_context,
        get_community_context,
        list_techniques,
        list_concepts,
        list_instructions,
        get_graph_overview,
    ]


class GraphRAGAgent(dspy.Module):
    def __init__(self, client: BaseGraphClient):
        super().__init__()
        self.react = dspy.ReAct(
            RequirementsQA,
            tools=_make_tools(client),
            max_iters=8,
        )

    def forward(self, question: str) -> dspy.Prediction:
        return self.react(question=question)

    def ask(self, question: str) -> tuple[str, List[str]]:
        node_list: list[str] = []
        waits = [5, 15, 30, 60]

        for attempt in range(len(waits) + 1):
            token = accessed_nodes.set(node_list)
            try:
                result = self.forward(question=question)
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


def build_agent(client: BaseGraphClient) -> GraphRAGAgent:
    """Configura DSPy, cria e retorna o agente. Carrega prompt otimizado se disponível."""
    lm = dspy.LM(
        model=config.DSPY_MODEL,
        api_key=config.OPENROUTER_API_KEY,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
    )
    dspy.configure(lm=lm)

    agent = GraphRAGAgent(client)
    print(f"[agent] LLM: {config.DSPY_MODEL}")

    if os.path.exists(config.COMPILED_AGENT_PATH):
        try:
            agent.load(config.COMPILED_AGENT_PATH)
            print("[agent] Prompt otimizado carregado.")
        except Exception as e:
            print(f"[agent] Aviso: compiled_agent.json inválido ({e}). Usando prompt padrão.")

    return agent
