"""
GraphService — lógica de negócio para manipular o grafo.
"""

import csv
import ast
from typing import List, Dict

from src.core.interfaces import BaseGraphClient
from src.infra.neo4j import queries
from src import config


_TECHNIQUES = [
    {"tech_id": "TECH_001", "name": "Entrevista", "description": "Elicitacao por conversas estruturadas com stakeholders", "category": "Elicitacao", "source": "literatura"},
    {"tech_id": "TECH_002", "name": "Questionario", "description": "Coleta via formularios estruturados", "category": "Elicitacao", "source": "literatura"},
    {"tech_id": "TECH_003", "name": "Casos de Uso", "description": "Cenarios de interacao usuario-sistema", "category": "Documentacao", "source": "literatura"},
    {"tech_id": "TECH_004", "name": "Prototipos", "description": "Modelos visuais para validacao", "category": "Validacao", "source": "literatura"},
    {"tech_id": "TECH_005", "name": "Analise de Dominio", "description": "Estudo do contexto e dominio do problema", "category": "Analise", "source": "literatura"},
]

_INSTRUCTIONS = [
    {"instr_id": "INST_001", "text": "Priorize requisitos por valor de negocio e impacto no usuario", "context": "Elicitacao e analise", "source": "boas_praticas"},
    {"instr_id": "INST_002", "text": "Valide sempre os requisitos com os stakeholders envolvidos", "context": "Pos-elicitacao", "source": "boas_praticas"},
    {"instr_id": "INST_003", "text": "Mantenha rastreabilidade completa dos requisitos", "context": "Ciclo de vida", "source": "boas_praticas"},
    {"instr_id": "INST_004", "text": "Use linguagem clara e nao ambigua na especificacao", "context": "Documentacao", "source": "boas_praticas"},
    {"instr_id": "INST_005", "text": "Considere restricoes tecnicas e de negocio", "context": "Analise de viabilidade", "source": "boas_praticas"},
]

_CONCEPTS = [
    {"concept_id": "CONC_001", "name": "Requisito Funcional", "definition": "Descreve o que o sistema deve fazer", "source": "literatura"},
    {"concept_id": "CONC_002", "name": "Requisito Nao-Funcional", "definition": "Descreve como o sistema deve se comportar em termos de qualidade", "source": "literatura"},
    {"concept_id": "CONC_003", "name": "Stakeholder", "definition": "Pessoa, grupo ou organizacao com interesse no sistema", "source": "literatura"},
    {"concept_id": "CONC_004", "name": "Elicitacao de Requisitos", "definition": "Processo de descoberta e coleta de requisitos", "source": "literatura"},
    {"concept_id": "CONC_005", "name": "Validacao de Requisitos", "definition": "Verificacao se os requisitos estao corretos e completos", "source": "literatura"},
]

_RELATIONSHIP_QUERIES = [
    "MATCH (r:Requirement) WHERE r.text =~ '(?i).*sistema deve.*|deve permitir.*|deve ter.*|deve fazer.*' MATCH (c:Concept {concept_id: 'CONC_001'}) CREATE (r)-[:IS_A]->(c)",
    "MATCH (r:Requirement) WHERE r.text =~ '(?i).*desempenho.*|seguranca.*|usabilidade.*|disponibilidade.*|manutenibilidade.*' MATCH (c:Concept {concept_id: 'CONC_002'}) CREATE (r)-[:IS_A]->(c)",
    "MATCH (r:Requirement) WHERE r.text =~ '(?i).*seguranca.*|criptografar.*|autenticar.*|autorizar.*' MATCH (t:Technique {tech_id: 'TECH_005'}) CREATE (r)-[:USES_TECHNIQUE]->(t)",
    "MATCH (r:Requirement)-[:IS_A]->(:Concept {concept_id: 'CONC_001'}) MATCH (t:Technique {tech_id: 'TECH_001'}) CREATE (r)-[:USES_TECHNIQUE]->(t)",
    "MATCH (i:Instruction {instr_id: 'INST_002'}) MATCH (c:Concept {concept_id: 'CONC_005'}) CREATE (i)-[:APPLIES_TO]->(c)",
    "MATCH (i:Instruction {instr_id: 'INST_003'}) MATCH (c:Concept {concept_id: 'CONC_004'}) CREATE (i)-[:APPLIES_TO]->(c)",
    "MATCH (t:Technique) MATCH (i:Instruction {instr_id: 'INST_002'}) CREATE (t)-[:FOLLOWS]->(i)",
    "MATCH (r:Requirement) MATCH (i:Instruction {instr_id: 'INST_001'}) CREATE (r)-[:SUPPORTED_BY]->(i)",
    "MATCH (r:Requirement) MATCH (i:Instruction {instr_id: 'INST_004'}) CREATE (r)-[:SUPPORTED_BY]->(i)",
]


class GraphService:
    def __init__(self, client: BaseGraphClient):
        self._client = client

    def populate_from_csv(self, csv_path: str = None) -> int:
        """Cria nós Requirement a partir do CSV de user stories com embeddings."""
        path = csv_path or config.CSV_PATH
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for i, row in enumerate(reader, start=1):
                emb_str = row.get("embedding", "[]")
                emb = ast.literal_eval(emb_str) if emb_str else []
                self._client.create_requirement(
                    req_id=f"REQ_{i:04d}",
                    text=row.get("user_story", ""),
                    summary=row.get("acceptance_criteria", ""),
                    req_type="funcional",
                    domain="user_story",
                    source="csv_dataset",
                    embedding=emb,
                    embedding_model="text-embedding-3-small",
                )
                count += 1
                if count % 100 == 0:
                    print(f"  {count} requisitos criados...")
        print(f"  {count} requisitos criados do CSV.")
        return count

    def create_static_nodes(self):
        """Cria Technique, Instruction e Concept estáticos."""
        for t in _TECHNIQUES:
            self._client.create_technique(**t)
        for i in _INSTRUCTIONS:
            self._client.create_instruction(**i)
        for c in _CONCEPTS:
            self._client.create_concept(**c)
        print(f"  {len(_TECHNIQUES)} tecnicas, {len(_INSTRUCTIONS)} instrucoes, {len(_CONCEPTS)} conceitos criados.")

    def create_smart_relationships(self):
        """Cria relacionamentos baseados em regras/keywords."""
        for q in _RELATIONSHIP_QUERIES:
            self._client.run(q)
        print("  Relacionamentos criados.")

    def populate_complete(self, csv_path: str = None):
        """Popula o grafo completo: CSV + nós estáticos + relacionamentos."""
        print("[graph_service] Populando grafo completo...")
        self.populate_from_csv(csv_path)
        self.create_static_nodes()
        self.create_smart_relationships()
        self._client.ensure_vector_index()
        print("[graph_service] Grafo pronto.")

    def get_graph_for_visualization(self, limit: int = 200, graph_id: str = "") -> Dict:
        """Retorna nós e arestas para visualização no front."""
        nodes = []
        links = []

        # 1. Requirement nodes filtrados pelo grafo
        reqs = self._client.run(queries.GET_GRAPH_NODES_REQUIREMENTS, {"limit": limit, "graph_id": graph_id})
        req_ids: set[str] = set()
        for r in reqs:
            text = r.get("text") or ""
            nodes.append({
                "id": r["id"], "label": "Requirement",
                "name": text[:60] + ("..." if len(text) > 60 else ""),
                "text": text, "summary": r.get("summary") or "",
                "communityId": r.get("communityId"),
            })
            req_ids.add(r["id"])

        # 2. Arestas que partem de Requirements deste grafo
        raw_rels = self._client.run(queries.GET_GRAPH_RELATIONSHIPS, {"graph_id": graph_id})
        # IDs de nós auxiliares (Technique/Concept/Instruction) referenciados
        aux_ids_needed: set[str] = set()
        for r in raw_rels:
            src, tgt = r["source"], r["target"]
            if src and tgt:
                links.append({"source": src, "target": tgt, "type": r["type"]})
                if src not in req_ids:
                    aux_ids_needed.add(src)
                if tgt not in req_ids:
                    aux_ids_needed.add(tgt)

        # 3. SIMILAR_TO filtrado
        for r in self._client.run(queries.GET_SIMILAR_TO_SAMPLE, {"graph_id": graph_id}):
            src, tgt = r["source"], r["target"]
            if src in req_ids and tgt in req_ids:
                links.append({"source": src, "target": tgt, "type": "SIMILAR_TO"})

        # 4. Inclui apenas nós auxiliares que são alcançados pelas arestas deste grafo
        if aux_ids_needed:
            for t in self._client.get_all_techniques():
                if t["id"] in aux_ids_needed:
                    nodes.append({"id": t["id"], "label": "Technique", "name": t["name"],
                                   "text": t.get("description") or "", "category": t.get("category") or ""})
            for i in self._client.get_all_instructions():
                if i["id"] in aux_ids_needed:
                    text = i.get("text") or ""
                    nodes.append({"id": i["id"], "label": "Instruction",
                                   "name": text[:50] + ("..." if len(text) > 50 else ""), "text": text})
            for c in self._client.get_all_concepts():
                if c["id"] in aux_ids_needed:
                    nodes.append({"id": c["id"], "label": "Concept", "name": c["name"],
                                   "text": c.get("definition") or ""})

        return {"nodes": nodes, "links": links}

    def list_graphs(self) -> list:
        return self._client.list_graphs()

    def create_graph(self, name: str) -> dict:
        import time as _time
        safe = name.lower().replace(" ", "_")[:20]
        graph_id = f"{safe}_{int(_time.time())}"
        self._client.create_graph_meta(graph_id, name)
        return {"graph_id": graph_id, "name": name, "node_count": 0}

    def populate_graph_from_dataset(
        self, graph_id: str, name: str, count: int = 100, keywords: List[str] = None
    ) -> int:
        """Cria um grafo completo copiando `count` requisitos do dataset default.
        Útil para testes e demos. Conecta também técnicas/conceitos/instruções.
        """
        self._client.create_graph_meta(graph_id, name)
        samples = self._client.sample_requirements_for_graph(keywords or [], count)
        if not samples:
            samples = self._client.sample_requirements_for_graph([], count)

        prefix = graph_id[:6].upper()
        for i, r in enumerate(samples):
            new_id = f"REQ_{prefix}_{i:04d}"
            self._client.create_requirement(
                req_id=new_id,
                text=r["text"],
                summary=r.get("summary", ""),
                req_type=r.get("type", "funcional"),
                domain=r.get("domain", "geral"),
                source="dataset_seeded",
                embedding=[],
                graph_id=graph_id,
            )
            if (i + 1) % 20 == 0:
                print(f"  [{name}] {i + 1}/{len(samples)} requisitos...")

        # Relacionamentos
        kw_map = {
            "TECH_001": ["login", "autenticacao", "usuario", "stakeholder"],
            "TECH_003": ["caso de uso", "cenario", "fluxo"],
            "TECH_004": ["prototipo", "interface", "tela"],
            "TECH_005": ["seguranca", "criptografia", "autorizar", "senha"],
        }
        reqs = self._client.run(
            "MATCH (r:Requirement {graph_id: $gid}) RETURN r.req_id AS req_id, toLower(r.text) AS txt",
            {"gid": graph_id},
        )
        for r in reqs:
            rid, txt = r["req_id"], r["txt"]
            for tech_id, keywords_t in kw_map.items():
                if any(kw in txt for kw in keywords_t):
                    self._client.run(
                        "MATCH (r:Requirement {req_id:$rid}),(t:Technique {tech_id:$tid}) MERGE (r)-[:USES_TECHNIQUE]->(t)",
                        {"rid": rid, "tid": tech_id},
                    )
            cid = "CONC_001" if ("deve" in txt or "permitir" in txt) else "CONC_002"
            self._client.run(
                "MATCH (r:Requirement {req_id:$rid}),(c:Concept {concept_id:$cid}) MERGE (r)-[:IS_A]->(c)",
                {"rid": rid, "cid": cid},
            )
            for iid in ["INST_001", "INST_004"]:
                self._client.run(
                    "MATCH (r:Requirement {req_id:$rid}),(i:Instruction {instr_id:$iid}) MERGE (r)-[:SUPPORTED_BY]->(i)",
                    {"rid": rid, "iid": iid},
                )

        print(f"  [{name}] Grafo de teste criado: {len(samples)} requisitos.")
        return len(samples)
