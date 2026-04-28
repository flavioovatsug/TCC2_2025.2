"""
Interfaces (classes abstratas) do domínio.
Seguindo Clean Architecture: a infra implementa, o domínio define.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Protocol, runtime_checkable


class BaseGraphClient(ABC):
    """Contrato para qualquer cliente de grafo de conhecimento."""

    @abstractmethod
    def search_requirements(self, query: str, limit: int = 10) -> List[Dict]: ...

    @abstractmethod
    def get_requirement_context(self, req_id: str) -> Optional[Dict]: ...

    @abstractmethod
    def get_community_requirements(self, req_id: str, limit: int = 15) -> List[Dict]: ...

    @abstractmethod
    def get_all_techniques(self) -> List[Dict]: ...

    @abstractmethod
    def get_all_instructions(self) -> List[Dict]: ...

    @abstractmethod
    def get_all_concepts(self) -> List[Dict]: ...

    @abstractmethod
    def get_graph_statistics(self) -> List[Dict]: ...

    @abstractmethod
    def node_count(self) -> int: ...

    @abstractmethod
    def run(self, query: str, params: dict = None) -> List[Dict]: ...


@runtime_checkable
class BaseAgent(Protocol):
    """Contrato estrutural para qualquer agente de Q&A sobre o grafo.
    Usa Protocol para evitar conflito de metaclasse com dspy.Module."""

    def ask(self, question: str) -> tuple[str, List[str]]:
        """Retorna (resposta, lista de IDs de nós acessados)."""
        ...
