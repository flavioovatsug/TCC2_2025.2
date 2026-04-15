"""
Camada de acesso ao Neo4j — todas as queries Cypher em um lugar.
"""

from typing import List, Dict, Optional
from neo4j import GraphDatabase
from backend import config


class Neo4jClient:
    """Cliente Neo4j read/write para o grafo de Engenharia de Requisitos."""

    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URL,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
        )
        self.database = config.NEO4J_DATABASE

    def close(self):
        self.driver.close()

    def test_connection(self):
        with self.driver.session(database=self.database) as s:
            s.run("RETURN 1")

    def run(self, query: str, params: dict = None) -> List[Dict]:
        with self.driver.session(database=self.database) as s:
            result = s.run(query, params or {})
            return [record.data() for record in result]

    # ---- Queries de leitura ----

    def search_requirements(self, query: str, limit: int = 10) -> List[Dict]:
        """Busca requisitos por palavras-chave (multi-keyword OR, ranked)."""
        keywords = [kw.strip() for kw in query.lower().split() if len(kw.strip()) > 2]
        if not keywords:
            keywords = [query.lower()]
        return self.run(
            """
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
            """,
            {"keywords": keywords, "limit": limit},
        )

    def get_requirement_context(self, req_id: str) -> Optional[Dict]:
        """Contexto completo de um requisito via traversal de relacionamentos."""
        rows = self.run(
            """
            MATCH (r:Requirement {req_id: $req_id})
            OPTIONAL MATCH (r)-[:USES_TECHNIQUE]->(t:Technique)
            OPTIONAL MATCH (r)-[:IS_A]->(c1:Concept)
            OPTIONAL MATCH (r)-[:IS_RELATED_TO]->(c2:Concept)
            OPTIONAL MATCH (r)-[:SUPPORTED_BY]->(i:Instruction)
            OPTIONAL MATCH (r)-[:ELICITED_BY]->(t2:Technique)
            RETURN r.req_id AS req_id, r.text AS text, r.summary AS summary,
                   r.type AS type, r.domain AS domain,
                   collect(DISTINCT t.name) + collect(DISTINCT t2.name) AS techniques,
                   collect(DISTINCT c1.name) + collect(DISTINCT c2.name) AS concepts,
                   collect(DISTINCT i.text) AS instructions
            """,
            {"req_id": req_id},
        )
        if not rows or rows[0].get("text") is None:
            return None
        row = rows[0]
        row["techniques"] = list({t for t in row.get("techniques", []) if t})
        row["concepts"] = list({c for c in row.get("concepts", []) if c})
        row["instructions"] = list({i for i in row.get("instructions", []) if i})
        return row

    def get_community_requirements(self, req_id: str, limit: int = 15) -> List[Dict]:
        """Requisitos da mesma comunidade Louvain."""
        rows = self.run(
            """
            MATCH (r:Requirement {req_id: $req_id})
            WHERE r.communityId IS NOT NULL
            WITH r.communityId AS cid
            MATCH (m:Requirement {communityId: cid})
            RETURN m.req_id AS req_id, m.text AS text, m.summary AS summary,
                   m.communityId AS community_id
            ORDER BY m.req_id LIMIT $limit
            """,
            {"req_id": req_id, "limit": limit},
        )
        if not rows:
            rows = self.run(
                """
                MATCH (r:Requirement {req_id: $req_id})-[:SIMILAR_TO]-(m:Requirement)
                RETURN m.req_id AS req_id, m.text AS text, m.summary AS summary,
                       m.communityId AS community_id
                ORDER BY m.req_id LIMIT $limit
                """,
                {"req_id": req_id, "limit": limit},
            )
        return rows

    def get_all_techniques(self) -> List[Dict]:
        return self.run(
            "MATCH (t:Technique) RETURN t.tech_id AS id, t.name AS name, "
            "t.description AS description, t.category AS category ORDER BY t.tech_id"
        )

    def get_all_instructions(self) -> List[Dict]:
        return self.run(
            "MATCH (i:Instruction) RETURN i.instr_id AS id, i.text AS text, "
            "i.context AS context ORDER BY i.instr_id"
        )

    def get_all_concepts(self) -> List[Dict]:
        return self.run(
            "MATCH (c:Concept) RETURN c.concept_id AS id, c.name AS name, "
            "c.definition AS definition ORDER BY c.concept_id"
        )

    def get_graph_statistics(self) -> List[Dict]:
        return self.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label"
        )

    def node_count(self) -> int:
        rows = self.run("MATCH (n) RETURN count(n) AS c")
        return rows[0]["c"] if rows else 0

    # ---- Escrita ----

    def clear_database(self):
        self.run("MATCH (n) DETACH DELETE n")

    def create_requirement(self, **kw):
        self.run(
            """
            CREATE (r:Requirement {
                req_id: $req_id, text: $text, summary: $summary,
                type: $type, source: $source, domain: $domain,
                embedding: $embedding, embedding_model: $embedding_model,
                embedding_ts: datetime(), created_at: datetime()
            })
            """,
            {
                "req_id": kw["req_id"],
                "text": kw.get("text", ""),
                "summary": kw.get("summary", ""),
                "type": kw.get("req_type", "funcional"),
                "source": kw.get("source", ""),
                "domain": kw.get("domain", ""),
                "embedding": kw.get("embedding", []),
                "embedding_model": kw.get("embedding_model", "text-embedding-3-small"),
            },
        )

    def create_technique(self, **kw):
        self.run(
            """
            CREATE (:Technique {
                tech_id: $tech_id, name: $name, description: $description,
                category: $category, source: $source,
                embedding: [], embedding_model: '', embedding_ts: datetime(), created_at: datetime()
            })
            """,
            {k: kw.get(k, "") for k in ["tech_id", "name", "description", "category", "source"]},
        )

    def create_instruction(self, **kw):
        self.run(
            """
            CREATE (:Instruction {
                instr_id: $instr_id, text: $text, context: $context, source: $source,
                embedding: [], embedding_model: '', embedding_ts: datetime(), created_at: datetime()
            })
            """,
            {k: kw.get(k, "") for k in ["instr_id", "text", "context", "source"]},
        )

    def create_concept(self, **kw):
        self.run(
            """
            CREATE (:Concept {
                concept_id: $concept_id, name: $name, definition: $definition, source: $source,
                embedding: [], embedding_model: '', embedding_ts: datetime(), created_at: datetime()
            })
            """,
            {k: kw.get(k, "") for k in ["concept_id", "name", "definition", "source"]},
        )

    def ensure_vector_index(self):
        try:
            self.run(
                """
                CREATE VECTOR INDEX requirement_embeddings IF NOT EXISTS
                FOR (r:Requirement) ON (r.embedding)
                OPTIONS {indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }}
                """
            )
        except Exception:
            pass
