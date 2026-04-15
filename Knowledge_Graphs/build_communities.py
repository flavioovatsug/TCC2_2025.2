"""
Constrói comunidades no grafo de requisitos usando o algoritmo de Louvain.

Fluxo:
  1. Lê embeddings dos requisitos do Neo4j
  2. Calcula similaridade de cosseno entre todos os pares (sklearn)
  3. Testa múltiplos limiares τ e reporta a modularidade Q para cada um
  4. Cria arestas SIMILAR_TO e escreve communityId nos nós com o τ escolhido

Uso:
  python build_communities.py                  # interativo
  python build_communities.py --tau 0.90       # τ fixo
  python build_communities.py --scan-only      # só mostra tabela τ → Q
"""

import os
import sys
import argparse
import numpy as np
import networkx as nx
from networkx.algorithms.community import louvain_communities, modularity
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
from neo4j import GraphDatabase


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

TAU_VALUES = [0.80, 0.83, 0.85, 0.87, 0.88, 0.89, 0.90, 0.92, 0.95]
NX_SEED = 42  # para reprodutibilidade do Louvain


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------

def get_driver():
    load_dotenv()
    uri = os.getenv("NEO4J_URL")
    auth = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    return GraphDatabase.driver(uri, auth=auth), database


def load_requirement_embeddings(driver, database):
    """Carrega (req_id, embedding) de todos os requisitos com embedding."""
    query = """
    MATCH (r:Requirement)
    WHERE r.embedding IS NOT NULL AND size(r.embedding) > 10
    RETURN r.req_id AS req_id, r.embedding AS embedding
    ORDER BY r.req_id
    """
    with driver.session(database=database) as s:
        rows = s.run(query).data()
    return rows


def write_community_ids(driver, database, req_id_to_community: dict):
    """Escreve communityId em cada nó Requirement."""
    query = """
    UNWIND $rows AS row
    MATCH (r:Requirement {req_id: row.req_id})
    SET r.communityId = row.community_id
    """
    rows = [{"req_id": k, "community_id": v} for k, v in req_id_to_community.items()]
    # Divide em lotes de 500
    batch_size = 500
    with driver.session(database=database) as s:
        for i in range(0, len(rows), batch_size):
            s.run(query, {"rows": rows[i:i + batch_size]})
    print(f"  communityId escrito em {len(rows)} requisitos.")


def write_similar_to_edges(driver, database, edges: list, tau: float):
    """
    Cria arestas SIMILAR_TO entre requisitos.
    edges: lista de (req_id_a, req_id_b, score)
    """
    # Remove arestas antigas
    with driver.session(database=database) as s:
        s.run("MATCH ()-[r:SIMILAR_TO]->() DELETE r")
        print(f"  Arestas SIMILAR_TO antigas removidas.")

    query = """
    UNWIND $rows AS row
    MATCH (a:Requirement {req_id: row.a})
    MATCH (b:Requirement {req_id: row.b})
    MERGE (a)-[:SIMILAR_TO {score: row.score, tau: row.tau}]->(b)
    """
    rows = [
        {"a": a, "b": b, "score": round(float(score), 4), "tau": tau}
        for a, b, score in edges
    ]
    batch_size = 1000
    total = 0
    with driver.session(database=database) as s:
        for i in range(0, len(rows), batch_size):
            s.run(query, {"rows": rows[i:i + batch_size]})
            total += len(rows[i:i + batch_size])
            print(f"  {total}/{len(rows)} arestas criadas...", end="\r")
    print(f"\n  {len(rows)} arestas SIMILAR_TO criadas (tau={tau}).")


# ---------------------------------------------------------------------------
# Louvain + Modularidade
# ---------------------------------------------------------------------------

def build_graph_for_tau(req_ids: list, sim_matrix: np.ndarray, tau: float):
    """Constrói grafo NetworkX com arestas onde similaridade >= tau."""
    G = nx.Graph()
    G.add_nodes_from(req_ids)
    n = len(req_ids)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            score = sim_matrix[i, j]
            if score >= tau:
                G.add_edge(req_ids[i], req_ids[j], weight=float(score))
                edges.append((req_ids[i], req_ids[j], score))
    return G, edges


def run_louvain_and_score(G, req_ids):
    """Roda Louvain e retorna (communities, Q, req_id_to_community_dict)."""
    # Nós sem arestas ficam em comunidades singleton — isso reduz Q.
    # Removemos componentes isolados para calcular Q de forma justa.
    if G.number_of_edges() == 0:
        return None, 0.0, {}

    communities = louvain_communities(G, seed=NX_SEED)
    q = modularity(G, communities)
    req_id_to_community = {}
    for i, comm in enumerate(communities):
        for node in comm:
            req_id_to_community[node] = i
    return communities, q, req_id_to_community


def scan_tau_values(req_ids, sim_matrix, tau_values):
    """Retorna tabela com métricas para cada τ."""
    results = []
    for tau in tau_values:
        G, _ = build_graph_for_tau(req_ids, sim_matrix, tau)
        n_edges = G.number_of_edges()
        isolated = sum(1 for n in G.nodes() if G.degree(n) == 0)
        communities, q, _ = run_louvain_and_score(G, req_ids)
        n_comm = len(communities) if communities else 0
        results.append({
            "tau": tau,
            "edges": n_edges,
            "nodes_isolated": isolated,
            "communities": n_comm,
            "Q": round(q, 4),
        })
    return results


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def print_table(results):
    print()
    print(f"{'τ':>6}  {'Arestas':>8}  {'Isolados':>9}  {'Comunidades':>12}  {'Q':>7}")
    print("-" * 55)
    best_q = max(r["Q"] for r in results)
    for r in results:
        marker = " <-- melhor Q" if r["Q"] == best_q and r["Q"] > 0 else ""
        print(
            f"{r['tau']:>6.2f}  {r['edges']:>8,}  {r['nodes_isolated']:>9,}  "
            f"{r['communities']:>12,}  {r['Q']:>7.4f}{marker}"
        )
    print()


def main():
    parser = argparse.ArgumentParser(description="Constrói comunidades Louvain no grafo de requisitos.")
    parser.add_argument("--tau", type=float, default=None, help="Limiar de similaridade de cosseno (ex: 0.90)")
    parser.add_argument("--scan-only", action="store_true", help="Apenas mostra tabela τ → Q sem modificar o banco")
    args = parser.parse_args()

    print("=" * 60)
    print("  Build Communities — Louvain Graph RAG")
    print("=" * 60)

    driver, database = get_driver()

    # 1. Carrega embeddings
    print("\n1. Carregando embeddings do Neo4j...")
    rows = load_requirement_embeddings(driver, database)
    if not rows:
        print("ERRO: Nenhum requisito com embedding encontrado.")
        print("Execute primeiro: python graph_creator.py")
        driver.close()
        return

    req_ids = [r["req_id"] for r in rows]
    embeddings = np.array([r["embedding"] for r in rows], dtype=np.float32)
    print(f"  {len(req_ids)} requisitos carregados (dim={embeddings.shape[1]})")

    # 2. Calcula similaridade de cosseno
    print("\n2. Calculando matriz de similaridade de cosseno...")
    sim_matrix = cosine_similarity(embeddings)
    np.fill_diagonal(sim_matrix, 0.0)  # ignora auto-similaridade
    print(f"  Matriz {sim_matrix.shape[0]}x{sim_matrix.shape[1]} calculada.")
    print(f"  Similaridade media (par): {sim_matrix.sum() / (len(req_ids) * (len(req_ids) - 1)):.4f}")

    # 3. Varre τ e calcula Q
    print("\n3. Varrendo limiares τ...")
    results = scan_tau_values(req_ids, sim_matrix, TAU_VALUES)
    print_table(results)

    if args.scan_only:
        driver.close()
        return

    # 4. Escolhe τ
    best = max(results, key=lambda r: r["Q"])

    if args.tau is not None:
        chosen_tau = args.tau
        print(f"Usando τ = {chosen_tau} (fornecido via --tau)")
    else:
        print(f"Melhor τ encontrado: {best['tau']} (Q = {best['Q']})")
        answer = input(f"Usar τ = {best['tau']}? [Enter para confirmar, ou digite outro valor]: ").strip()
        if answer == "":
            chosen_tau = best["tau"]
        else:
            try:
                chosen_tau = float(answer)
            except ValueError:
                print("Valor invalido. Usando o melhor automaticamente.")
                chosen_tau = best["tau"]

    # 5. Constrói grafo final com τ escolhido
    print(f"\n4. Construindo grafo final com τ = {chosen_tau}...")
    G, edges = build_graph_for_tau(req_ids, sim_matrix, chosen_tau)
    communities, q, req_id_to_community = run_louvain_and_score(G, req_ids)

    if not communities:
        print("ERRO: Nenhuma aresta criada com esse τ. Tente um valor menor.")
        driver.close()
        return

    print(f"  Arestas: {G.number_of_edges():,}")
    print(f"  Comunidades: {len(communities)}")
    print(f"  Modularidade Q = {q:.4f}")

    # Distribuição de tamanho das comunidades
    sizes = sorted([len(c) for c in communities], reverse=True)
    print(f"  Maiores comunidades: {sizes[:10]}")

    # 6. Escreve no Neo4j
    print("\n5. Escrevendo communityId nos nós...")
    write_community_ids(driver, database, req_id_to_community)

    print("\n6. Criando arestas SIMILAR_TO...")
    write_similar_to_edges(driver, database, edges, chosen_tau)

    print(f"\nConcluido!")
    print(f"  τ = {chosen_tau}, Q = {q:.4f}, {len(communities)} comunidades")
    print(f"  Acesse o Neo4j Browser: http://localhost:7474")
    print(f"  Query sugerida:")
    print(f"    MATCH (a:Requirement {{communityId: 0}})-[r:SIMILAR_TO]-(b)")
    print(f"    RETURN a, r, b LIMIT 50")

    driver.close()


if __name__ == "__main__":
    main()
