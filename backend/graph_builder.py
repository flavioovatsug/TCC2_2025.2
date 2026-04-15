"""
Popula o grafo Neo4j a partir do CSV e dados estáticos.
Adaptado de Knowledge_Graphs/graph_creator.py para uso como módulo.
"""

import csv
import ast
from backend import config
from backend.neo4j_client import Neo4jClient


def populate_from_csv(client: Neo4jClient):
    """Cria nós Requirement a partir do CSV de user stories com embeddings."""
    path = config.CSV_PATH
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for i, row in enumerate(reader, start=1):
            emb_str = row.get("embedding", "[]")
            emb = ast.literal_eval(emb_str) if emb_str else []
            client.create_requirement(
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


def create_static_nodes(client: Neo4jClient):
    """Cria Technique, Instruction e Concept estáticos."""
    techniques = [
        {"tech_id": "TECH_001", "name": "Entrevista", "description": "Elicitacao por conversas estruturadas com stakeholders", "category": "Elicitacao", "source": "literatura"},
        {"tech_id": "TECH_002", "name": "Questionario", "description": "Coleta via formularios estruturados", "category": "Elicitacao", "source": "literatura"},
        {"tech_id": "TECH_003", "name": "Casos de Uso", "description": "Cenarios de interacao usuario-sistema", "category": "Documentacao", "source": "literatura"},
        {"tech_id": "TECH_004", "name": "Prototipos", "description": "Modelos visuais para validacao", "category": "Validacao", "source": "literatura"},
        {"tech_id": "TECH_005", "name": "Analise de Dominio", "description": "Estudo do contexto e dominio do problema", "category": "Analise", "source": "literatura"},
    ]
    instructions = [
        {"instr_id": "INST_001", "text": "Priorize requisitos por valor de negocio e impacto no usuario", "context": "Elicitacao e analise", "source": "boas_praticas"},
        {"instr_id": "INST_002", "text": "Valide sempre os requisitos com os stakeholders envolvidos", "context": "Pos-elicitacao", "source": "boas_praticas"},
        {"instr_id": "INST_003", "text": "Mantenha rastreabilidade completa dos requisitos", "context": "Ciclo de vida", "source": "boas_praticas"},
        {"instr_id": "INST_004", "text": "Use linguagem clara e nao ambigua na especificacao", "context": "Documentacao", "source": "boas_praticas"},
        {"instr_id": "INST_005", "text": "Considere restricoes tecnicas e de negocio", "context": "Analise de viabilidade", "source": "boas_praticas"},
    ]
    concepts = [
        {"concept_id": "CONC_001", "name": "Requisito Funcional", "definition": "Descreve o que o sistema deve fazer", "source": "literatura"},
        {"concept_id": "CONC_002", "name": "Requisito Nao-Funcional", "definition": "Descreve como o sistema deve se comportar em termos de qualidade", "source": "literatura"},
        {"concept_id": "CONC_003", "name": "Stakeholder", "definition": "Pessoa, grupo ou organizacao com interesse no sistema", "source": "literatura"},
        {"concept_id": "CONC_004", "name": "Elicitacao de Requisitos", "definition": "Processo de descoberta e coleta de requisitos", "source": "literatura"},
        {"concept_id": "CONC_005", "name": "Validacao de Requisitos", "definition": "Verificacao se os requisitos estao corretos e completos", "source": "literatura"},
    ]
    for t in techniques:
        client.create_technique(**t)
    for i in instructions:
        client.create_instruction(**i)
    for c in concepts:
        client.create_concept(**c)
    print(f"  {len(techniques)} tecnicas, {len(instructions)} instrucoes, {len(concepts)} conceitos criados.")


def create_smart_relationships(client: Neo4jClient):
    """Cria relacionamentos baseados em regras / keywords."""
    queries = [
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
    for q in queries:
        client.run(q)
    print("  Relacionamentos criados.")


def populate_complete(client: Neo4jClient):
    """Popula o grafo completo: CSV + nós estáticos + relacionamentos."""
    print("[graph_builder] Populando grafo completo...")
    populate_from_csv(client)
    create_static_nodes(client)
    create_smart_relationships(client)
    client.ensure_vector_index()
    print("[graph_builder] Grafo pronto.")
