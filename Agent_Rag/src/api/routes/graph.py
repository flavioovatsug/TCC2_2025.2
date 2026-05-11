"""
GET  /api/graph   — nós e arestas para visualização.
GET  /api/graphs  — lista de grafos disponíveis.
POST /api/graphs  — cria um novo grafo.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.service.graph_service import GraphService

router = APIRouter()
_graph_service: GraphService = None  # type: ignore


def init(graph_service: GraphService):
    global _graph_service
    _graph_service = graph_service


@router.get("/api/graph")
def get_graph_data(
    limit: int = Query(200, ge=1, le=1000),
    graph_id: str = Query("default"),
):
    return _graph_service.get_graph_for_visualization(limit, graph_id)


@router.get("/api/graphs")
def list_graphs():
    return _graph_service.list_graphs()


class CreateGraphRequest(BaseModel):
    name: str


@router.post("/api/graphs")
def create_graph(req: CreateGraphRequest):
    return _graph_service.create_graph(req.name)
