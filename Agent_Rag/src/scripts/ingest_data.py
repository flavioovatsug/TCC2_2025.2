#!/usr/bin/env python3
"""
Script de ingestão: lê o CSV processado e povoa o Neo4j.

Executar a partir da raiz do Agent_Rag/:
    python -m src.scripts.ingest_data [--clear]
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.infra.neo4j.client import Neo4jClient
from src.service.graph_service import GraphService
from src import config


def main():
    parser = argparse.ArgumentParser(description="Popula o grafo Neo4j a partir do CSV.")
    parser.add_argument("--clear", action="store_true", help="Limpa o banco antes de popular")
    parser.add_argument("--csv", default=config.CSV_PATH, help="Caminho para o CSV com embeddings")
    args = parser.parse_args()

    client = Neo4jClient()
    client.test_connection()
    print(f"[ok] Conectado ao Neo4j: {config.NEO4J_URL}")

    if args.clear:
        print("[!] Limpando banco de dados...")
        client.clear_database()

    service = GraphService(client)
    service.populate_complete(csv_path=args.csv)
    print(f"[ok] Ingestão concluída. Total de nós: {client.node_count()}")
    client.close()


if __name__ == "__main__":
    main()
