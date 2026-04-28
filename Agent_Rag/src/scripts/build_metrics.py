#!/usr/bin/env python3
"""
Cálculo de métricas Louvain e comunidades a partir de embeddings no Neo4j.

Executar a partir da raiz do Agent_Rag/:
    python -m src.scripts.build_metrics [--tau 0.85] [--scan-only]
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx
from networkx.algorithms.community import louvain_communities

from src.infra.neo4j.client import Neo4jClient
from src import config


def load_requirement_embeddings(client: Neo4jClient):
    rows = client.run(
        "MATCH (r:Requirement) WHERE r.embedding IS NOT NULL AND size(r.embedding) > 0 "
        "RETURN r.req_id AS req_id, r.embedding AS embedding"
    )
    req_ids = [r["req_id"] for r in rows]
    embeddings = np.array([r["embedding"] for r in rows], dtype=float)
    return req_ids, embeddings


def build_graph_for_tau(req_ids, embeddings, tau: float) -> nx.Graph:
    sim_matrix = cosine_similarity(embeddings)
    G = nx.Graph()
    G.add_nodes_from(req_ids)
    n = len(req_ids)
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= tau:
                G.add_edge(req_ids[i], req_ids[j], weight=float(sim_matrix[i, j]))
    return G


def run_louvain_and_score(G: nx.Graph):
    if G.number_of_edges() == 0:
        return [], 0.0
    communities = louvain_communities(G, seed=42)
    q = nx.community.modularity(G, communities)
    return communities, q


def scan_tau_values(req_ids, embeddings):
    print(f"{'tau':>6}  {'edges':>8}  {'communities':>12}  {'modularity':>12}")
    print("-" * 45)
    for tau in [0.80, 0.82, 0.84, 0.85, 0.86, 0.88, 0.90, 0.92, 0.95]:
        G = build_graph_for_tau(req_ids, embeddings, tau)
        comms, q = run_louvain_and_score(G)
        print(f"{tau:>6.2f}  {G.number_of_edges():>8}  {len(comms):>12}  {q:>12.4f}")


def write_community_ids(client: Neo4jClient, req_ids, communities):
    for comm_id, community in enumerate(communities):
        for req_id in community:
            client.run(
                "MATCH (r:Requirement {req_id: $req_id}) SET r.communityId = $cid",
                {"req_id": req_id, "cid": comm_id},
            )
    print(f"[ok] communityId escrito para {len(req_ids)} requisitos em {len(communities)} comunidades.")


def write_similar_to_edges(client: Neo4jClient, req_ids, embeddings, tau: float):
    sim_matrix = cosine_similarity(embeddings)
    n = len(req_ids)
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            if sim_matrix[i, j] >= tau:
                client.run(
                    "MATCH (a:Requirement {req_id: $a}), (b:Requirement {req_id: $b}) "
                    "MERGE (a)-[:SIMILAR_TO {score: $score}]->(b)",
                    {"a": req_ids[i], "b": req_ids[j], "score": float(sim_matrix[i, j])},
                )
                count += 1
    print(f"[ok] {count} arestas SIMILAR_TO criadas (tau={tau}).")


def main():
    parser = argparse.ArgumentParser(description="Detecta comunidades Louvain no grafo de requisitos.")
    parser.add_argument("--tau", type=float, default=0.85, help="Limiar de similaridade (0-1)")
    parser.add_argument("--scan-only", action="store_true", help="Apenas exibe tabela de tau x modularidade")
    args = parser.parse_args()

    client = Neo4jClient()
    client.test_connection()
    print(f"[ok] Conectado ao Neo4j.")

    req_ids, embeddings = load_requirement_embeddings(client)
    print(f"[ok] {len(req_ids)} requisitos com embeddings carregados.")

    if args.scan_only:
        scan_tau_values(req_ids, embeddings)
        return

    G = build_graph_for_tau(req_ids, embeddings, args.tau)
    communities, q = run_louvain_and_score(G)
    print(f"[ok] tau={args.tau}: {G.number_of_edges()} arestas, {len(communities)} comunidades, Q={q:.4f}")

    write_community_ids(client, req_ids, communities)
    write_similar_to_edges(client, req_ids, embeddings, args.tau)
    client.close()


if __name__ == "__main__":
    main()
