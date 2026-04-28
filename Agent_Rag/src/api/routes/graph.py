"""
GET /api/graph — retorna nós e arestas para visualização.
"""

from fastapi import APIRouter, Query

from src.service.graph_service import GraphService

router = APIRouter()
_graph_service: GraphService = None  # type: ignore


def init(graph_service: GraphService):
    global _graph_service
    _graph_service = graph_service


@router.get("/api/graph")
def get_graph_data(limit: int = Query(200, ge=1, le=1000)):
    return _graph_service.get_graph_for_visualization(limit)
