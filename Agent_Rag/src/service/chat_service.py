"""
ChatService — lógica do fluxo de conversa com o agente.
"""

from src.core.interfaces import BaseAgent


class ChatService:
    def __init__(self, agent: BaseAgent):
        self._agent = agent

    def answer(self, question: str) -> tuple[str, list[str]]:
        """
        Executa o agente e retorna (resposta, ids_de_nos_acessados).
        Delega retry/rate-limit ao agente.
        """
        return self._agent.ask(question)
