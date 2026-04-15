"""
Agente Graph RAG especialista em Engenharia de Requisitos.
Utiliza DSPy + ReAct para consultar um grafo de conhecimento Neo4j
contendo requisitos, técnicas, instruções e conceitos de ER.

Uso: python graph_rag.py
"""

import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
import dspy


# ---------------------------------------------------------------------------
# Neo4j Retriever — camada de acesso ao grafo (somente leitura)
# ---------------------------------------------------------------------------

class Neo4jRetriever:
    """Encapsula todas as consultas Cypher ao grafo de Engenharia de Requisitos."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URL")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver = GraphDatabase.driver(
            self.uri, auth=(self.username, self.password)
        )
        # Testa a conexão
        with self.driver.session(database=self.database) as session:
            session.run("RETURN 1")
        print("Conexao com Neo4j estabelecida.")

    def close(self):
        self.driver.close()

    def _run(self, query: str, params: dict = None) -> List[Dict]:
        with self.driver.session(database=self.database) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    # --- Buscas ---

    def search_requirements(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca requisitos por palavras-chave (case-insensitive, multi-keyword OR)."""
        keywords = [kw.strip() for kw in query.lower().split() if len(kw.strip()) > 2]
        if not keywords:
            keywords = [query.lower()]

        cypher = """
        MATCH (r:Requirement)
        WHERE any(kw IN $keywords WHERE toLower(r.text) CONTAINS kw)
           OR any(kw IN $keywords WHERE toLower(r.summary) CONTAINS kw)
        WITH r,
             size([kw IN $keywords WHERE toLower(r.text) CONTAINS kw]) +
             size([kw IN $keywords WHERE toLower(r.summary) CONTAINS kw]) AS score
        ORDER BY score DESC
        LIMIT $limit
        RETURN r.req_id AS req_id, r.text AS text, r.summary AS summary,
               r.type AS type, r.domain AS domain, score
        """
        return self._run(cypher, {"keywords": keywords, "limit": limit})

    def get_context_for_requirement(self, req_id: str) -> Optional[Dict]:
        """Retorna contexto completo de um requisito, com traversal de relacionamentos."""
        cypher = """
        MATCH (r:Requirement {req_id: $req_id})
        OPTIONAL MATCH (r)-[:USES_TECHNIQUE]->(t:Technique)
        OPTIONAL MATCH (r)-[:IS_A]->(c1:Concept)
        OPTIONAL MATCH (r)-[:IS_RELATED_TO]->(c2:Concept)
        OPTIONAL MATCH (r)-[:SUPPORTED_BY]->(i:Instruction)
        OPTIONAL MATCH (r)-[:ELICITED_BY]->(t2:Technique)
        RETURN r.req_id AS req_id,
               r.text AS text,
               r.summary AS summary,
               r.type AS type,
               r.domain AS domain,
               collect(DISTINCT t.name) + collect(DISTINCT t2.name) AS techniques,
               collect(DISTINCT c1.name) + collect(DISTINCT c2.name) AS concepts,
               collect(DISTINCT i.text) AS instructions
        """
        rows = self._run(cypher, {"req_id": req_id})
        if not rows or rows[0].get("text") is None:
            return None
        row = rows[0]
        # Limpa listas (remove None e duplicatas)
        row["techniques"] = list({t for t in row.get("techniques", []) if t})
        row["concepts"] = list({c for c in row.get("concepts", []) if c})
        row["instructions"] = list({i for i in row.get("instructions", []) if i})
        return row

    def get_all_techniques(self) -> List[Dict]:
        return self._run("""
            MATCH (t:Technique)
            RETURN t.tech_id AS id, t.name AS name,
                   t.description AS description, t.category AS category
            ORDER BY t.tech_id
        """)

    def get_all_instructions(self) -> List[Dict]:
        return self._run("""
            MATCH (i:Instruction)
            RETURN i.instr_id AS id, i.text AS text, i.context AS context
            ORDER BY i.instr_id
        """)

    def get_all_concepts(self) -> List[Dict]:
        return self._run("""
            MATCH (c:Concept)
            RETURN c.concept_id AS id, c.name AS name, c.definition AS definition
            ORDER BY c.concept_id
        """)

    def get_graph_statistics(self) -> List[Dict]:
        return self._run("""
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY label
        """)

    def ensure_vector_index(self):
        """Cria indice vetorial para busca por similaridade (Neo4j 5.x)."""
        try:
            self._run("""
                CREATE VECTOR INDEX requirement_embeddings IF NOT EXISTS
                FOR (r:Requirement) ON (r.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
            """)
            print("Indice vetorial criado/verificado.")
        except Exception as e:
            print(f"Nota: indice vetorial nao criado ({e})")

    def search_requirements_by_vector(
        self, query_embedding: List[float], limit: int = 10
    ) -> List[Dict]:
        """Busca vetorial usando o indice nativo do Neo4j 5.x."""
        cypher = """
        CALL db.index.vector.queryNodes('requirement_embeddings', $limit, $query_embedding)
        YIELD node, score
        RETURN node.req_id AS req_id, node.text AS text,
               node.summary AS summary, score
        ORDER BY score DESC
        """
        return self._run(cypher, {"query_embedding": query_embedding, "limit": limit})

    def get_community_requirements(self, req_id: str, limit: int = 15) -> List[Dict]:
        """Retorna todos os requisitos da mesma comunidade Louvain do req_id dado."""
        cypher = """
        MATCH (r:Requirement {req_id: $req_id})
        WHERE r.communityId IS NOT NULL
        WITH r.communityId AS cid
        MATCH (m:Requirement {communityId: cid})
        RETURN m.req_id AS req_id, m.text AS text, m.summary AS summary,
               m.communityId AS community_id
        ORDER BY m.req_id
        LIMIT $limit
        """
        rows = self._run(cypher, {"req_id": req_id, "limit": limit})
        # Se req_id não tem communityId, tenta fallback por SIMILAR_TO
        if not rows:
            fallback = """
            MATCH (r:Requirement {req_id: $req_id})-[:SIMILAR_TO]-(m:Requirement)
            RETURN m.req_id AS req_id, m.text AS text, m.summary AS summary,
                   m.communityId AS community_id
            ORDER BY m.req_id
            LIMIT $limit
            """
            rows = self._run(fallback, {"req_id": req_id, "limit": limit})
        return rows

    def get_community_stats(self) -> List[Dict]:
        """Retorna distribuição de tamanho das comunidades."""
        return self._run("""
            MATCH (r:Requirement)
            WHERE r.communityId IS NOT NULL
            RETURN r.communityId AS community_id, count(r) AS size
            ORDER BY size DESC
            LIMIT 20
        """)


# ---------------------------------------------------------------------------
# DSPy Signatures
# ---------------------------------------------------------------------------

class RequirementsQA(dspy.Signature):
    """Voce eh um especialista em Engenharia de Requisitos. Responda a pergunta
    do usuario usando o contexto fornecido do grafo de conhecimento. Cite IDs
    de requisitos e nomes de tecnicas quando relevante. Responda no mesmo idioma
    da pergunta."""

    context: str = dspy.InputField(
        desc="Contexto recuperado do grafo de conhecimento"
    )
    question: str = dspy.InputField(
        desc="Pergunta do usuario sobre engenharia de requisitos"
    )
    answer: str = dspy.OutputField(
        desc="Resposta detalhada fundamentada no contexto e na expertise em ER"
    )


class RequirementAnalysis(dspy.Signature):
    """Analise um requisito de software e forneca recomendacoes de melhoria,
    tecnicas aplicaveis e boas praticas da engenharia de requisitos."""

    requirement_text: str = dspy.InputField(desc="Texto do requisito a analisar")
    graph_context: str = dspy.InputField(
        desc="Tecnicas, conceitos e instrucoes relacionadas do grafo"
    )
    analysis: str = dspy.OutputField(
        desc="Analise da qualidade, completude e clareza do requisito"
    )
    recommendations: str = dspy.OutputField(
        desc="Recomendacoes especificas para melhorar o requisito"
    )
    suggested_techniques: str = dspy.OutputField(
        desc="Tecnicas de ER aplicaveis a este requisito"
    )


# ---------------------------------------------------------------------------
# Instância global do retriever (inicializada em main())
# ---------------------------------------------------------------------------

retriever: Optional[Neo4jRetriever] = None


# ---------------------------------------------------------------------------
# Tool Functions para o agente ReAct
# ---------------------------------------------------------------------------

def search_requirements(query: str) -> str:
    """Search the knowledge graph for software requirements matching keywords.
    Use this to find requirements about a specific topic, feature, or domain.
    Input must be search keywords (e.g. 'authentication login security')."""
    results = retriever.search_requirements(query, limit=8)
    if not results:
        return "Nenhum requisito encontrado para essa busca."
    lines = []
    for r in results:
        lines.append(f"[{r['req_id']}] {r['text']}")
        if r.get("summary"):
            lines.append(f"  Criterios de aceitacao: {r['summary'][:200]}")
    return "\n".join(lines)


def get_requirement_context(req_id: str) -> str:
    """Get full context for a specific requirement by its ID (e.g. 'REQ_0001').
    Returns the requirement text plus related techniques, concepts, and best practices.
    Use after finding a requirement to understand its graph relationships."""
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


def list_techniques() -> str:
    """List all requirements engineering techniques in the knowledge graph.
    Use when the user asks about RE techniques, methods, or elicitation approaches."""
    techs = retriever.get_all_techniques()
    if not techs:
        return "Nenhuma tecnica encontrada no grafo."
    return "\n".join(
        f"[{t['id']}] {t['name']}: {t['description']} (Categoria: {t['category']})"
        for t in techs
    )


def list_concepts() -> str:
    """List all requirements engineering concepts in the knowledge graph.
    Use when the user asks about RE concepts, definitions, or terminology."""
    concepts = retriever.get_all_concepts()
    if not concepts:
        return "Nenhum conceito encontrado no grafo."
    return "\n".join(
        f"[{c['id']}] {c['name']}: {c['definition']}" for c in concepts
    )


def list_instructions() -> str:
    """List all requirements engineering best practices and guidelines.
    Use when the user asks about RE best practices, guidelines, or recommendations."""
    instructions = retriever.get_all_instructions()
    if not instructions:
        return "Nenhuma instrucao encontrada no grafo."
    return "\n".join(
        f"[{i['id']}] {i['text']} (Contexto: {i['context']})" for i in instructions
    )


def get_graph_overview() -> str:
    """Get statistics about the knowledge graph: how many requirements, techniques,
    instructions, and concepts are stored. Use when the user asks about the scope
    or contents of the knowledge base."""
    stats = retriever.get_graph_statistics()
    if not stats:
        return "Nao foi possivel obter estatisticas do grafo."
    lines = ["Visao geral do Grafo de Conhecimento:"]
    for s in stats:
        lines.append(f"  {s['label']}: {s['count']} nos")
    return "\n".join(lines)


def get_community_context(req_id: str) -> str:
    """Get all requirements that belong to the same Louvain community as the given
    requirement ID. Returns a semantically coherent 'module' of related requirements.
    Use this after finding a relevant requirement to expand context to the full
    functional cluster it belongs to. Requires build_communities.py to have been run.
    Example: get_community_context('REQ_0045')"""
    members = retriever.get_community_requirements(req_id, limit=15)
    if not members:
        return (
            f"Requisito '{req_id}' nao pertence a nenhuma comunidade. "
            "Execute build_communities.py para construir as comunidades Louvain."
        )
    community_id = members[0].get("community_id", "?")
    lines = [f"Comunidade {community_id} — {len(members)} requisitos relacionados:"]
    for m in members:
        lines.append(f"  [{m['req_id']}] {m['text']}")
        if m.get("summary"):
            lines.append(f"    Criterios: {m['summary'][:150]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agente DSPy Graph RAG
# ---------------------------------------------------------------------------

class GraphRAGAgent(dspy.Module):
    """Agente especialista em Engenharia de Requisitos com acesso ao grafo Neo4j."""

    def __init__(self):
        super().__init__()
        self.agent = dspy.ReAct(
            dspy.Signature("question -> answer").with_instructions(
                "Voce eh um especialista em Engenharia de Requisitos (RE). "
                "Voce tem acesso a um grafo de conhecimento com ~700 requisitos "
                "reais de software (user stories), 5 tecnicas de RE, 5 instrucoes "
                "de boas praticas e 5 conceitos fundamentais. "
                "Use suas ferramentas para buscar e explorar o grafo antes de "
                "responder. Sempre cite IDs de requisitos ou nomes de tecnicas "
                "quando relevante. Responda no mesmo idioma da pergunta "
                "(portugues ou ingles). Seja detalhado e fundamentado."
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


# ---------------------------------------------------------------------------
# Interface de chat interativa
# ---------------------------------------------------------------------------

def chat_loop():
    """Loop interativo de conversacao com o agente."""
    print("=" * 70)
    print("  Agente Graph RAG — Especialista em Engenharia de Requisitos")
    print("  Comandos:")
    print("    'sair' ou 'quit' — encerra o chat")
    print("    'debug'          — ativa/desativa modo debug (mostra tool calls)")
    print("=" * 70)

    agent = GraphRAGAgent()
    debug_mode = False

    while True:
        try:
            question = input("\nVoce: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAte mais!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "sair", "q"):
            print("Ate mais!")
            break
        if question.lower() == "debug":
            debug_mode = not debug_mode
            print(f"Modo debug: {'ATIVADO' if debug_mode else 'DESATIVADO'}")
            continue

        try:
            result = agent(question=question)
            print(f"\nAgente: {result.answer}")

            if debug_mode:
                print("\n--- Debug: historico da LM ---")
                dspy.inspect_history(n=1)
                print("--- Fim debug ---")
        except Exception as e:
            print(f"\nErro: {e}")
            print("Tente reformular sua pergunta.")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main():
    global retriever

    load_dotenv()

    # Valida variaveis de ambiente obrigatorias
    required = ["OPENROUTER_API_KEY", "NEO4J_URL", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Erro: Variaveis de ambiente faltando: {', '.join(missing)}")
        print("Verifique seu arquivo .env")
        return

    # Configura DSPy com OpenRouter
    model_name = os.getenv("DSPY_MODEL", "openrouter/google/gemma-4-26b-a4b-it:free")
    lm = dspy.LM(
        model=model_name,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        temperature=0.7,
        max_tokens=2048,
    )
    dspy.configure(lm=lm)
    print(f"LLM configurada: {model_name}")

    # Inicializa o retriever Neo4j
    retriever = Neo4jRetriever()

    # Tenta criar indice vetorial (opcional)
    retriever.ensure_vector_index()

    try:
        chat_loop()
    finally:
        retriever.close()
        print("Conexao Neo4j encerrada.")


if __name__ == "__main__":
    main()
