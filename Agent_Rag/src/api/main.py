#!/usr/bin/env python3
"""
Entry point da API — FastAPI + Uvicorn.

Executar a partir da raiz do projeto Agent_Rag/:
    python -m src.api.main
"""

import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Garante imports absolutos a partir da raiz do Agent_Rag
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src import config  # noqa: E402
from src.infra.neo4j.client import Neo4jClient  # noqa: E402
from src.infra.dspy.agent import build_agent  # noqa: E402
from src.service.graph_service import GraphService  # noqa: E402
from src.service.chat_service import ChatService  # noqa: E402
from src.api.routes import chat as chat_routes, graph as graph_routes  # noqa: E402


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
        print("=" * 60)
        print("  RE Expert Agent — Startup")
        print("=" * 60)

        # 1. Neo4j
        try:
            client = Neo4jClient()
            client.test_connection()
        except Exception as e:
            print(f"\n[ERRO] Nao foi possivel conectar ao Neo4j ({config.NEO4J_URL}).")
            print(f"       {e}")
            sys.exit(1)

        print(f"[ok] Neo4j conectado ({config.NEO4J_URL})")

        # 2. Serviços
        graph_service = GraphService(client)
        graph_routes.init(graph_service)

        # 3. Popular grafo se vazio
        n = client.node_count()
        if n == 0:
            if not os.path.exists(config.CSV_PATH):
                print(f"[ERRO] CSV nao encontrado: {config.CSV_PATH}")
                sys.exit(1)
            print("[!] Grafo vazio — populando automaticamente...")
            graph_service.populate_complete()
            n = client.node_count()

        print(f"[ok] Grafo: {n} nos")

        # 4. Agente DSPy
        agent = build_agent(client)
        chat_service = ChatService(agent)
        chat_routes.init(chat_service)

        print("[ok] Servidor pronto em http://localhost:8000")
        print("[ok] Frontend esperado em http://localhost:5173")
        print("=" * 60)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.join(config.PROJECT_ROOT, "src")],
    )
