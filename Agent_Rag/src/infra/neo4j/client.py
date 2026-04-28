"""
Neo4jClient — implementa BaseGraphClient.
"""

from typing import Dict, List, Optional
from neo4j import GraphDatabase

from src.core.interfaces import BaseGraphClient
from src.infra.neo4j import queries
from src import config


class Neo4jClient(BaseGraphClient):
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

    # ---- Leitura ----

    def search_requirements(self, query: str, limit: int = 10) -> List[Dict]:
        keywords = [kw.strip() for kw in query.lower().split() if len(kw.strip()) > 2]
        if not keywords:
            keywords = [query.lower()]
        return self.run(queries.SEARCH_REQUIREMENTS, {"keywords": keywords, "limit": limit})

    def get_requirement_context(self, req_id: str) -> Optional[Dict]:
        rows = self.run(queries.GET_REQUIREMENT_CONTEXT, {"req_id": req_id})
        if not rows or rows[0].get("text") is None:
            return None
        row = rows[0]
        row["techniques"] = list({t for t in row.get("techniques", []) if t})
        row["concepts"] = list({c for c in row.get("concepts", []) if c})
        row["instructions"] = list({i for i in row.get("instructions", []) if i})
        return row

    def get_community_requirements(self, req_id: str, limit: int = 15) -> List[Dict]:
        rows = self.run(queries.GET_COMMUNITY_REQUIREMENTS, {"req_id": req_id, "limit": limit})
        if not rows:
            rows = self.run(queries.GET_COMMUNITY_REQUIREMENTS_FALLBACK, {"req_id": req_id, "limit": limit})
        return rows

    def get_all_techniques(self) -> List[Dict]:
        return self.run(queries.GET_ALL_TECHNIQUES)

    def get_all_instructions(self) -> List[Dict]:
        return self.run(queries.GET_ALL_INSTRUCTIONS)

    def get_all_concepts(self) -> List[Dict]:
        return self.run(queries.GET_ALL_CONCEPTS)

    def get_graph_statistics(self) -> List[Dict]:
        return self.run(queries.GET_GRAPH_STATISTICS)

    def node_count(self) -> int:
        rows = self.run(queries.COUNT_NODES)
        return rows[0]["c"] if rows else 0

    # ---- Escrita ----

    def clear_database(self):
        self.run(queries.CLEAR_DATABASE)

    def create_requirement(self, **kw):
        self.run(queries.CREATE_REQUIREMENT, {
            "req_id": kw["req_id"],
            "text": kw.get("text", ""),
            "summary": kw.get("summary", ""),
            "type": kw.get("req_type", "funcional"),
            "source": kw.get("source", ""),
            "domain": kw.get("domain", ""),
            "embedding": kw.get("embedding", []),
            "embedding_model": kw.get("embedding_model", "text-embedding-3-small"),
        })

    def create_technique(self, **kw):
        self.run(queries.CREATE_TECHNIQUE,
                 {k: kw.get(k, "") for k in ["tech_id", "name", "description", "category", "source"]})

    def create_instruction(self, **kw):
        self.run(queries.CREATE_INSTRUCTION,
                 {k: kw.get(k, "") for k in ["instr_id", "text", "context", "source"]})

    def create_concept(self, **kw):
        self.run(queries.CREATE_CONCEPT,
                 {k: kw.get(k, "") for k in ["concept_id", "name", "definition", "source"]})

    def ensure_vector_index(self):
        try:
            self.run(queries.CREATE_VECTOR_INDEX)
        except Exception:
            pass
