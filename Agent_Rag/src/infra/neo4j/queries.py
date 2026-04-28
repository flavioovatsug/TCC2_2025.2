"""
Queries Cypher isoladas — todas as strings ficam aqui.
"""

SEARCH_REQUIREMENTS = """
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

GET_REQUIREMENT_CONTEXT = """
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
"""

GET_COMMUNITY_REQUIREMENTS = """
MATCH (r:Requirement {req_id: $req_id})
WHERE r.communityId IS NOT NULL
WITH r.communityId AS cid
MATCH (m:Requirement {communityId: cid})
RETURN m.req_id AS req_id, m.text AS text, m.summary AS summary,
       m.communityId AS community_id
ORDER BY m.req_id LIMIT $limit
"""

GET_COMMUNITY_REQUIREMENTS_FALLBACK = """
MATCH (r:Requirement {req_id: $req_id})-[:SIMILAR_TO]-(m:Requirement)
RETURN m.req_id AS req_id, m.text AS text, m.summary AS summary,
       m.communityId AS community_id
ORDER BY m.req_id LIMIT $limit
"""

GET_ALL_TECHNIQUES = """
MATCH (t:Technique)
RETURN t.tech_id AS id, t.name AS name, t.description AS description,
       t.category AS category ORDER BY t.tech_id
"""

GET_ALL_INSTRUCTIONS = """
MATCH (i:Instruction)
RETURN i.instr_id AS id, i.text AS text, i.context AS context ORDER BY i.instr_id
"""

GET_ALL_CONCEPTS = """
MATCH (c:Concept)
RETURN c.concept_id AS id, c.name AS name, c.definition AS definition ORDER BY c.concept_id
"""

GET_GRAPH_STATISTICS = """
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label
"""

COUNT_NODES = "MATCH (n) RETURN count(n) AS c"

CLEAR_DATABASE = "MATCH (n) DETACH DELETE n"

CREATE_REQUIREMENT = """
CREATE (r:Requirement {
    req_id: $req_id, text: $text, summary: $summary,
    type: $type, source: $source, domain: $domain,
    embedding: $embedding, embedding_model: $embedding_model,
    embedding_ts: datetime(), created_at: datetime()
})
"""

CREATE_TECHNIQUE = """
CREATE (:Technique {
    tech_id: $tech_id, name: $name, description: $description,
    category: $category, source: $source,
    embedding: [], embedding_model: '', embedding_ts: datetime(), created_at: datetime()
})
"""

CREATE_INSTRUCTION = """
CREATE (:Instruction {
    instr_id: $instr_id, text: $text, context: $context, source: $source,
    embedding: [], embedding_model: '', embedding_ts: datetime(), created_at: datetime()
})
"""

CREATE_CONCEPT = """
CREATE (:Concept {
    concept_id: $concept_id, name: $name, definition: $definition, source: $source,
    embedding: [], embedding_model: '', embedding_ts: datetime(), created_at: datetime()
})
"""

CREATE_VECTOR_INDEX = """
CREATE VECTOR INDEX requirement_embeddings IF NOT EXISTS
FOR (r:Requirement) ON (r.embedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
}}
"""

GET_GRAPH_NODES_REQUIREMENTS = """
MATCH (r:Requirement)
RETURN r.req_id AS id, r.text AS text, r.summary AS summary,
       r.type AS type, r.domain AS domain, r.communityId AS communityId
ORDER BY r.req_id LIMIT $limit
"""

GET_GRAPH_RELATIONSHIPS = """
MATCH (a)-[r]->(b) WHERE type(r) <> 'SIMILAR_TO'
RETURN coalesce(a.req_id, a.tech_id, a.instr_id, a.concept_id) AS source,
       coalesce(b.req_id, b.tech_id, b.instr_id, b.concept_id) AS target,
       type(r) AS type
LIMIT 2000
"""

GET_SIMILAR_TO_SAMPLE = """
MATCH (a:Requirement)-[:SIMILAR_TO]->(b:Requirement)
RETURN a.req_id AS source, b.req_id AS target LIMIT 300
"""
