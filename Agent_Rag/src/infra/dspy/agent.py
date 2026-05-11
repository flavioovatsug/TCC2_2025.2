"""
GraphRAGAgent — DSPy Module que implementa BaseAgent.
"""

import os
import re
import time
from contextvars import ContextVar
from typing import Callable, List, Optional

import dspy

from src.core.interfaces import BaseAgent, BaseGraphClient
from src.infra.dspy.signatures import RequirementsQA
from src import config

# Rastreia nós acessados durante cada request (thread-safe via ContextVar)
accessed_nodes: ContextVar[Optional[list]] = ContextVar("accessed_nodes", default=None)
# Grafo ativo para o request atual
current_graph_id: ContextVar[str] = ContextVar("current_graph_id", default="default")
# Callback para enviar eventos de progresso via WebSocket
push_event: ContextVar[Optional[Callable]] = ContextVar("push_event", default=None)


def _track(ids: list):
    lst = accessed_nodes.get(None)
    if lst is not None:
        lst.extend(ids)


def _connect_graph_nodes(client: BaseGraphClient, graph_id: str):
    """Conecta os nós de um grafo recém-criado às Techniques/Concepts/Instructions padrão."""
    kw_map = {
        "TECH_001": ["login", "autenticacao", "usuario", "stakeholder", "entrevistar"],
        "TECH_003": ["caso de uso", "cenario", "fluxo"],
        "TECH_004": ["prototipo", "interface", "tela", "formulario"],
        "TECH_005": ["seguranca", "criptografia", "autorizar", "senha", "permissao"],
    }
    # Keywords que indicam requisito NÃO-FUNCIONAL (checadas ANTES de "deve")
    _NF_KEYWORDS = [
        "tempo de resposta", "latencia", "latência", "desempenho", "performance",
        "disponibilidade", "uptime", "sla", "throughput", "capacidade",
        "escalabilidade", "confiabilidade", "seguranca", "segurança",
        "usabilidade", "portabilidade", "manutenibilidade", "velocidade",
        "tempo de carregamento", "inferior a", "superior a", "por segundo",
        "milissegundos", "ms", "segundos por", "requisicoes por", "requisições por",
        "95%", "99%", "99.9%", "criptografia", "auditoria", "backup",
    ]
    reqs = client.run(
        "MATCH (r:Requirement {graph_id: $gid}) RETURN r.req_id AS req_id, toLower(r.text) AS txt, r.type AS rtype",
        {"gid": graph_id},
    )
    for r in reqs:
        rid, txt = r["req_id"], r["txt"]
        rtype_stored = (r.get("rtype") or "").lower()
        for tech_id, keywords in kw_map.items():
            if any(kw in txt for kw in keywords):
                client.run(
                    "MATCH (r:Requirement {req_id:$rid}),(t:Technique {tech_id:$tid}) MERGE (r)-[:USES_TECHNIQUE]->(t)",
                    {"rid": rid, "tid": tech_id},
                )
        # Classifica: usa o campo 'type' salvo no nó se existir; caso contrário detecta por keywords NF
        if "nao" in rtype_stored or "não" in rtype_stored or "non" in rtype_stored:
            is_nf = True
        elif rtype_stored == "funcional":
            is_nf = False
        else:
            is_nf = any(kw in txt for kw in _NF_KEYWORDS)
        cid = "CONC_002" if is_nf else "CONC_001"
        client.run(
            "MATCH (r:Requirement {req_id:$rid}),(c:Concept {concept_id:$cid}) MERGE (r)-[:IS_A]->(c)",
            {"rid": rid, "cid": cid},
        )
        for iid in ["INST_001", "INST_004"]:
            client.run(
                "MATCH (r:Requirement {req_id:$rid}),(i:Instruction {instr_id:$iid}) MERGE (r)-[:SUPPORTED_BY]->(i)",
                {"rid": rid, "iid": iid},
            )


# Detecta pedidos de criação de grafo antes de entrar no ReAct
_CREATION_RE = re.compile(
    r"\b(cri[ae]|gen[ae]r|mont[ae]|constru[ia]|build|creat[e])\b.{0,120}\b(grafo|graph|projeto|project|base\s+de\s+requisitos?)\b",
    re.IGNORECASE | re.DOTALL,
)


def _parse_creation_intent(question: str):
    """Extrai name, node_count, description de um pedido de criação de grafo."""
    # nome: string entre aspas ou após 'chamado'
    m_quote = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', question)
    if m_quote:
        name = m_quote.group(1).strip()
    else:
        m_name = re.search(
            r'\bchamado\s+([\w\s\-]+?)(?=\s+com\s|\s+de\s|\s+sobre\s|\s*$)',
            question,
            re.IGNORECASE,
        )
        name = m_name.group(1).strip() if m_name else "Novo Projeto"

    # quantidade: dígito antes de requisitos/nós/nodes
    m_cnt = re.search(r'(\d+)\s*(?:requisitos?|n[oó]s?|nodes?)', question, re.IGNORECASE)
    count = min(max(int(m_cnt.group(1)), 5), 100) if m_cnt else 20

    # descrição: após 'sobre'
    m_desc = re.search(r'\bsobre\s+(.+?)(?:\s*$)', question, re.IGNORECASE)
    description = m_desc.group(1).strip() if m_desc else name

    return name, count, description


def _make_tools(client: BaseGraphClient):
    """Cria closures de tool functions para o agente DSPy."""

    def search_requirements(query: str) -> str:
        """Search the knowledge graph for software requirements matching keywords."""
        gid = current_graph_id.get("default")
        results = client.search_requirements(query, limit=8, graph_id=gid)
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

    def create_requirement(text: str, req_type: str = "funcional", domain: str = "") -> str:
        """Create a new software requirement node in the current knowledge graph.
        Use this when the user explicitly asks to add, create, or register a new requirement.
        Args:
            text: Clear, complete requirement text describing what the system should do.
            req_type: 'funcional' for functional, 'nao-funcional' for non-functional.
            domain: Application domain (e.g. 'autenticacao', 'pagamento', 'relatorios').
        """
        gid = current_graph_id.get("default")
        req_id = f"REQ_U{int(time.time() * 100) % 10 ** 8:08d}"

        client.create_requirement(
            req_id=req_id,
            text=text,
            req_type=req_type,
            domain=domain or "geral",
            source="agent_created",
            embedding=[],
            graph_id=gid,
        )
        _track([req_id])

        # Conecta a técnicas relevantes por keywords
        text_lower = text.lower()
        tech_kw = {
            "TECH_001": ["login", "autenticacao", "usuario", "stakeholder", "entrevistar"],
            "TECH_003": ["caso de uso", "cenario", "fluxo"],
            "TECH_004": ["prototipo", "interface", "tela", "formulario"],
            "TECH_005": ["seguranca", "criptografia", "autorizar", "senha", "permissao"],
        }
        for tech_id, keywords in tech_kw.items():
            if any(kw in text_lower for kw in keywords):
                client.run(
                    "MATCH (r:Requirement {req_id: $rid}), (t:Technique {tech_id: $tid}) "
                    "MERGE (r)-[:USES_TECHNIQUE]->(t)",
                    {"rid": req_id, "tid": tech_id},
                )

        # Conecta ao conceito (funcional vs nao-funcional)
        cid = "CONC_001" if req_type == "funcional" else "CONC_002"
        client.run(
            "MATCH (r:Requirement {req_id: $rid}), (c:Concept {concept_id: $cid}) "
            "MERGE (r)-[:IS_A]->(c)",
            {"rid": req_id, "cid": cid},
        )

        # Conecta a instruções de boas práticas
        for instr_id in ["INST_001", "INST_004"]:
            client.run(
                "MATCH (r:Requirement {req_id: $rid}), (i:Instruction {instr_id: $iid}) "
                "MERGE (r)-[:SUPPORTED_BY]->(i)",
                {"rid": req_id, "iid": instr_id},
            )

        label = f"'{text[:80]}{'...' if len(text) > 80 else ''}"
        return f"✓ Requisito {req_id} criado: {label} (tipo: {req_type}, domínio: {domain or 'geral'})"

    def create_graph_from_dataset(
        name: str, node_count: int = 20, description: str = ""
    ) -> str:
        """Create a brand-new knowledge graph seeded from the dataset requirements.
        Use this when the user explicitly asks to create a new graph, project, or knowledge base.
        Args:
            name: Short descriptive name for the new graph (e.g. 'E-commerce', 'Sistema Bancário').
            node_count: How many requirements to include (5-100, default 20).
            description: Topic keywords to pick relevant requirements (e.g. 'login pagamento seguranca').
        """
        import json as _json
        from src.infra.dspy.signatures import GenerateGraphChunk

        push = push_event.get(None)

        def _push(msg: str, pct: int, extra: Optional[dict] = None):
            if push:
                evt = {"type": "progress", "message": msg, "percent": pct}
                if extra:
                    evt.update(extra)
                push(evt)

        # 1. Gera graph_id único
        safe = re.sub(r"[^a-z0-9]", "_", name.lower())[:20].strip("_")
        gid = f"{safe}_{int(time.time())}"

        print(f"[tool:create_graph] name={name!r} node_count={node_count} gid={gid!r}")
        _push(f"Criando grafo '{name}'...", 5)
        client.create_graph_meta(gid, name)

        # 2. Busca exemplos do dataset como few-shot reference
        node_count = min(max(int(node_count), 5), 100)
        keywords = [kw.lower() for kw in description.split() if len(kw) > 2]
        _push("Buscando exemplos de referência no dataset...", 12)
        examples = client.sample_requirements_for_graph(keywords or [], min(15, node_count))
        if not examples:
            examples = client.sample_requirements_for_graph([], 15)

        reference_str = "\n".join(
            f"- {r['text']}" + (f" [Critérios: {r['summary'][:80]}]" if r.get("summary") else "")
            for r in examples[:10]
        )

        # 3. Gera requisitos em chunks via LLM (5 por chamada)
        CHUNK_SIZE = 5
        generator = dspy.Predict(GenerateGraphChunk)
        created_ids: list[str] = []
        remaining = node_count
        chunk_num = 0
        total_chunks = (node_count + CHUNK_SIZE - 1) // CHUNK_SIZE

        while remaining > 0:
            batch = min(CHUNK_SIZE, remaining)
            chunk_num += 1
            pct = 15 + int((chunk_num / total_chunks) * 75)
            _push(
                f"Gerando requisitos com IA: chunk {chunk_num}/{total_chunks}...",
                pct,
            )

            try:
                result = generator(
                    project_name=name,
                    description=description or name,
                    reference_examples=reference_str,
                    count=str(batch),
                )
                raw = result.requirements_json.strip()
                # Strip markdown code fences if present
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                generated = _json.loads(raw)
                if not isinstance(generated, list):
                    raise ValueError("LLM output is not a JSON array")
            except Exception as e:
                print(f"[tool:create_graph] ✗ LLM chunk {chunk_num} failed: {e} — falling back to dataset copy")
                fb = client.sample_requirements_for_graph(keywords or [], batch)
                generated = [
                    {"text": r["text"], "summary": r.get("summary", ""),
                     "type": r.get("type", "funcional"), "domain": r.get("domain", "geral")}
                    for r in fb
                ]

            for i, req in enumerate(generated[:batch]):
                ts = int(time.time() * 100) % 10 ** 7
                new_id = f"REQ_{safe[:6].upper()}{chunk_num:02d}{i:02d}_{ts:07d}"
                client.create_requirement(
                    req_id=new_id,
                    text=req.get("text", ""),
                    summary=req.get("summary", ""),
                    req_type=req.get("type", "funcional"),
                    domain=req.get("domain", "geral"),
                    source="llm_generated",
                    embedding=[],
                    graph_id=gid,
                )
                created_ids.append(new_id)
                _track([new_id])

            remaining -= batch

        # 4. Conecta nós a técnicas/conceitos/instruções padrão
        _push("Construindo relacionamentos...", 93)
        print(f"[tool:create_graph] connecting nodes for gid={gid!r}")
        _connect_graph_nodes(client, gid)

        # 5. Notifica conclusão
        print(f"[tool:create_graph] ✓ done | created={len(created_ids)} | gid={gid!r}")
        _push(
            f"Grafo '{name}' criado com {len(created_ids)} requisitos!",
            100,
            {"type": "graph_created", "graph_id": gid, "name": name, "node_count": len(created_ids)},
        )
        return (
            f"✓ Grafo '{name}' criado com sucesso! "
            f"{len(created_ids)} requisitos gerados por IA. graph_id: {gid}"
        )

    return [
        search_requirements,
        get_requirement_context,
        get_community_context,
        list_techniques,
        list_concepts,
        list_instructions,
        get_graph_overview,
        create_requirement,
        create_graph_from_dataset,
    ]


class GraphRAGAgent(dspy.Module):
    def __init__(self, client: BaseGraphClient):
        super().__init__()
        self._tools_list = _make_tools(client)
        self.react = dspy.ReAct(
            RequirementsQA,
            tools=self._tools_list,
            max_iters=8,
        )

    def forward(self, question: str) -> dspy.Prediction:
        return self.react(question=question)

    def ask(self, question: str, graph_id: str = "default") -> tuple[str, List[str]]:
        node_list: list[str] = []
        waits = [5, 15, 30, 60]
        print(f"[agent] ask() | graph_id={graph_id!r} | question={question!r}")

        # ── Bypass: criação de grafo detectada por intenção ───────────────────
        if _CREATION_RE.search(question):
            name, count, description = _parse_creation_intent(question)
            print(f"[agent] ⚡ creation intent | name={name!r} count={count} desc={description!r}")
            create_fn = next(
                (t for t in self._tools_list if getattr(t, "__name__", "") == "create_graph_from_dataset"),
                None,
            )
            if create_fn:
                token_nodes = accessed_nodes.set(node_list)
                token_graph = current_graph_id.set(graph_id)
                try:
                    result = create_fn(name=name, node_count=count, description=description)
                    return result, list(dict.fromkeys(node_list))
                finally:
                    accessed_nodes.reset(token_nodes)
                    current_graph_id.reset(token_graph)
        # ─────────────────────────────────────────────────────────────────────

        for attempt in range(len(waits) + 1):
            token_nodes = accessed_nodes.set(node_list)
            token_graph = current_graph_id.set(graph_id)
            try:
                print(f"[agent] → ReAct.forward() attempt={attempt + 1}")
                result = self.forward(question=question)
                print(f"[agent] ✓ answer_len={len(result.answer)} | nodes_accessed={len(node_list)}")
                return result.answer, list(dict.fromkeys(node_list))
            except Exception as e:
                err = str(e)
                is_rate = "429" in err or "RateLimitError" in err or "rate-limited" in err.lower()
                print(f"[agent] ✗ error attempt={attempt + 1} rate_limit={is_rate}: {err[:200]}")
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
                accessed_nodes.reset(token_nodes)
                current_graph_id.reset(token_graph)
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
