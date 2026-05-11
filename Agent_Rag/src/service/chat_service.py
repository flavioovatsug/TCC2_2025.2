"""
ChatService — lógica do fluxo de conversa com o agente.
"""

from src.core.interfaces import BaseAgent


class ChatService:
    def __init__(self, agent: BaseAgent):
        self._agent = agent

    def answer(self, question: str, graph_id: str = "default") -> tuple[str, list[str]]:
        """
        Executa o agente e retorna (resposta, ids_de_nos_acessados).
        O graph_id determina qual grafo de conhecimento usar.
        """
        return self._agent.ask(question, graph_id=graph_id)
