"""
GET /api/graph — retorna nós e arestas para visualização.
"""

from fastapi import APIRouter, Query
from backend.neo4j_client import Neo4jClient

router = APIRouter()
_client: Neo4jClient = None  # type: ignore


def init(client: Neo4jClient):
    global _client
    _client = client


@router.get("/api/graph")
def get_graph_data(limit: int = Query(200, ge=1, le=1000)):
    nodes = []
    links = []

    # Requirements
    reqs = _client.run(
        """
        MATCH (r:Requirement)
        RETURN r.req_id AS id, r.text AS text, r.summary AS summary,
               r.type AS type, r.domain AS domain, r.communityId AS communityId
        ORDER BY r.req_id LIMIT $limit
        """,
        {"limit": limit},
    )
    for r in reqs:
        text = r.get("text") or ""
        nodes.append({
            "id": r["id"], "label": "Requirement",
            "name": text[:60] + ("..." if len(text) > 60 else ""),
            "text": text, "summary": r.get("summary") or "",
            "communityId": r.get("communityId"),
        })

    for t in _client.get_all_techniques():
        nodes.append({"id": t["id"], "label": "Technique", "name": t["name"],
                       "text": t.get("description") or "", "category": t.get("category") or ""})
    for i in _client.get_all_instructions():
        text = i.get("text") or ""
        nodes.append({"id": i["id"], "label": "Instruction",
                       "name": text[:50] + ("..." if len(text) > 50 else ""), "text": text})
    for c in _client.get_all_concepts():
        nodes.append({"id": c["id"], "label": "Concept", "name": c["name"],
                       "text": c.get("definition") or ""})

    all_ids = {n["id"] for n in nodes}

    # Relacionamentos
    rels = _client.run(
        """
        MATCH (a)-[r]->(b) WHERE type(r) <> 'SIMILAR_TO'
        RETURN coalesce(a.req_id, a.tech_id, a.instr_id, a.concept_id) AS source,
               coalesce(b.req_id, b.tech_id, b.instr_id, b.concept_id) AS target,
               type(r) AS type
        LIMIT 2000
        """
    )
    for r in rels:
        if r["source"] in all_ids and r["target"] in all_ids:
            links.append({"source": r["source"], "target": r["target"], "type": r["type"]})

    # SIMILAR_TO (amostra)
    for r in _client.run(
        "MATCH (a:Requirement)-[:SIMILAR_TO]->(b:Requirement) "
        "RETURN a.req_id AS source, b.req_id AS target LIMIT 300"
    ):
        if r["source"] in all_ids and r["target"] in all_ids:
            links.append({"source": r["source"], "target": r["target"], "type": "SIMILAR_TO"})

    return {"nodes": nodes, "links": links}
