#!/usr/bin/env python3
"""
Entry point unico do projeto.

    python -m backend.server          # a partir da raiz do projeto
    python backend/server.py          # idem

O que acontece ao rodar:
  1. Carrega .env
  2. Conecta ao Neo4j
  3. Se o grafo estiver vazio → popula automaticamente (~700 requisitos)
  4. Configura o agente DSPy
  5. Sobe o servidor FastAPI (uvicorn) na porta 8000
"""

import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Garante que "from backend import ..." funcione de qualquer diretório
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend import config  # noqa: E402 — carrega .env automaticamente
from backend.neo4j_client import Neo4jClient  # noqa: E402
from backend import graph_builder  # noqa: E402
from backend import agent as agent_module  # noqa: E402
from backend.routes import graph as graph_routes, chat as chat_routes  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI(title="RE Expert Agent")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(graph_routes.router)
    app.include_router(chat_routes.router)

    @app.on_event("startup")
    async def startup():
        # 1. Neo4j
        print("=" * 60)
        print("  RE Expert Agent — Startup")
        print("=" * 60)

        try:
            client = Neo4jClient()
            client.test_connection()
        except Exception as e:
            print(f"\n[ERRO] Nao foi possivel conectar ao Neo4j ({config.NEO4J_URL}).")
            print(f"       {e}")
            print("\n  Suba o Neo4j com:")
            print(f"    docker run -d --name neo4j-er -p 7474:7474 -p 7687:7687 \\")
            print(f"      -e NEO4J_AUTH={config.NEO4J_USERNAME}/{config.NEO4J_PASSWORD} neo4j:5.26\n")
            sys.exit(1)

        print(f"[ok] Neo4j conectado ({config.NEO4J_URL})")

        # 2. Popular grafo se vazio
        n = client.node_count()
        if n == 0:
            if not os.path.exists(config.CSV_PATH):
                print(f"[ERRO] CSV nao encontrado: {config.CSV_PATH}")
                sys.exit(1)
            print(f"[!] Grafo vazio — populando automaticamente...")
            graph_builder.populate_complete(client)
            n = client.node_count()

        print(f"[ok] Grafo: {n} nos")

        # 3. Agente DSPy
        agent_module.setup(client)
        graph_routes.init(client)

        print(f"[ok] Servidor pronto em http://localhost:8000")
        print(f"[ok] Frontend esperado em http://localhost:5173")
        print("=" * 60)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "backend.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.join(config.PROJECT_ROOT, "backend")],
    )
