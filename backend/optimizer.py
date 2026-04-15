"""
Otimização automática de prompts com DSPy — tema central do TCC.

O que este módulo faz:
  Dado um conjunto de exemplos (trainset) e uma métrica de qualidade,
  usa o algoritmo BootstrapFewShot do DSPy para descobrir automaticamente
  os melhores few-shot examples para o agente GraphRAGAgent.

  Antes da otimização: o agente usa apenas as instruções manuais em _AGENT_INSTRUCTIONS.
  Depois:  o agente carrega exemplos otimizados que guiam o LLM a usar
           as ferramentas do grafo de forma mais precisa.

Uso:
  # Roda no mesmo ambiente do servidor (precisa do Neo4j rodando)
  python -m backend.optimizer

  # Pula avaliação e apenas exibe o trainset
  python -m backend.optimizer --dry-run

Saída:
  backend/compiled_agent.json   ← carregado automaticamente pelo server.py
"""

import os
import sys
import re
import argparse

# Garante imports relativos ao projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import dspy
from dspy.teleprompt import BootstrapFewShot

from backend import config
from backend.neo4j_client import Neo4jClient
from backend import agent as agent_module

# ---------------------------------------------------------------------------
# Caminho onde o estado compilado sera salvo / carregado
# ---------------------------------------------------------------------------

COMPILED_PATH = os.path.join(os.path.dirname(__file__), "compiled_agent.json")

# ---------------------------------------------------------------------------
# Trainset — exemplos de pergunta + resposta esperada
#
# Não precisam ser respostas perfeitas: o BootstrapFewShot usará o LLM
# para gerar traces completos a partir dessas perguntas e a métrica
# decidirá quais traces são bons o suficiente para virar few-shot demos.
# ---------------------------------------------------------------------------

TRAINSET = [
    dspy.Example(
        question="Quais requisitos no grafo tratam de autenticação ou login de usuário?",
        answer_hint="autenticação login usuário",
    ).with_inputs("question"),
    dspy.Example(
        question="Explique a técnica de entrevista para elicitação de requisitos.",
        answer_hint="entrevista elicitação stakeholder",
    ).with_inputs("question"),
    dspy.Example(
        question="Quais requisitos funcionais estão relacionados a pagamento?",
        answer_hint="pagamento funcional REQ_",
    ).with_inputs("question"),
    dspy.Example(
        question="O que é um requisito não-funcional? Dê exemplos do grafo.",
        answer_hint="não-funcional desempenho segurança REQ_",
    ).with_inputs("question"),
    dspy.Example(
        question="Liste as boas práticas de escrita de requisitos presentes no grafo.",
        answer_hint="boas práticas instrução requisito claro",
    ).with_inputs("question"),
    dspy.Example(
        question="Busque requisitos sobre notificações ao usuário.",
        answer_hint="notificação usuário REQ_",
    ).with_inputs("question"),
    dspy.Example(
        question="Quais conceitos fundamentais de engenharia de requisitos estão no grafo?",
        answer_hint="conceito stakeholder requisito grafo",
    ).with_inputs("question"),
    dspy.Example(
        question="Mostre requisitos de uma mesma comunidade semantica no grafo.",
        answer_hint="comunidade similar REQ_",
    ).with_inputs("question"),
    dspy.Example(
        question="Quais técnicas de prototipagem são mencionadas no grafo?",
        answer_hint="prototipagem técnica elicitação",
    ).with_inputs("question"),
    dspy.Example(
        question="Encontre requisitos sobre acessibilidade ou usabilidade.",
        answer_hint="acessibilidade usabilidade REQ_",
    ).with_inputs("question"),
]


# ---------------------------------------------------------------------------
# Métrica de qualidade
#
# Recebe (example, prediction) e retorna float em [0, 1].
# O BootstrapFewShot só usa como demo traces com score >= threshold.
# ---------------------------------------------------------------------------

def raq_metric(example: dspy.Example, prediction: dspy.Prediction, trace=None) -> float:
    """
    Avalia a qualidade da resposta do agente para fins de otimização.

    Critérios (pesos):
      0.4 — Resposta substantiva (> 150 chars)
      0.3 — Cita ao menos um ID de requisito (REQ_XXXX) — evidência de busca no grafo
      0.2 — Contém termos de RE relevantes
      0.1 — Contém termos do answer_hint do exemplo de treino
    """
    answer = getattr(prediction, "answer", "") or ""
    score = 0.0

    # Critério 1: resposta substantiva
    if len(answer) > 150:
        score += 0.4
    elif len(answer) > 60:
        score += 0.2

    # Critério 2: cita IDs de requisitos (evidência de que o agente buscou no grafo)
    if re.search(r"REQ_\d{3,}", answer, re.IGNORECASE):
        score += 0.3

    # Critério 3: terminologia de Engenharia de Requisitos
    re_terms = [
        "requisito", "requirement", "funcional", "técnica", "technique",
        "elicitação", "elicitation", "stakeholder", "conceito", "concept",
        "instrução", "instruction", "comunidade", "community",
    ]
    if any(t in answer.lower() for t in re_terms):
        score += 0.2

    # Critério 4: alinhamento com o hint do exemplo
    hint = getattr(example, "answer_hint", "") or ""
    hint_words = [w.lower() for w in hint.split() if len(w) > 3]
    if hint_words and any(w in answer.lower() for w in hint_words):
        score += 0.1

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Compilação
# ---------------------------------------------------------------------------

def compile_agent(agent: agent_module.GraphRAGAgent) -> agent_module.GraphRAGAgent:
    """
    Executa BootstrapFewShot e salva o agente compilado em COMPILED_PATH.
    Retorna o agente compilado.
    """
    print("\n[optimizer] Iniciando BootstrapFewShot...")
    print(f"[optimizer] Trainset: {len(TRAINSET)} exemplos")
    print(f"[optimizer] Metrica: raq_metric")
    print(f"[optimizer] Output: {COMPILED_PATH}")
    print()

    teleprompter = BootstrapFewShot(
        metric=raq_metric,
        max_bootstrapped_demos=3,   # max few-shot demos gerados por bootstrap
        max_labeled_demos=2,        # max demos manuais do trainset
        max_rounds=1,
    )

    compiled = teleprompter.compile(agent, trainset=TRAINSET)
    compiled.save(COMPILED_PATH)
    print(f"\n[optimizer] Agente compilado salvo em: {COMPILED_PATH}")
    return compiled


def load_compiled_agent(agent: agent_module.GraphRAGAgent) -> bool:
    """
    Carrega estado compilado se existir. Retorna True se carregou.
    """
    if os.path.exists(COMPILED_PATH):
        try:
            agent.load(COMPILED_PATH)
            print(f"[agent] Prompt otimizado carregado: {COMPILED_PATH}")
            return True
        except Exception as e:
            print(f"[agent] Aviso: nao foi possivel carregar prompt compilado ({e})")
    return False


# ---------------------------------------------------------------------------
# Entry point (uso standalone: python -m backend.optimizer)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Otimiza prompts do agente com DSPy BootstrapFewShot.")
    parser.add_argument("--dry-run", action="store_true", help="Exibe trainset sem rodar a otimizacao")
    args = parser.parse_args()

    print("=" * 60)
    print("  DSPy Prompt Optimizer — BootstrapFewShot")
    print("=" * 60)

    if args.dry_run:
        print(f"\nTrainset ({len(TRAINSET)} exemplos):")
        for i, ex in enumerate(TRAINSET, 1):
            print(f"  {i:02d}. {ex.question}")
        print()
        return

    # Conecta Neo4j e configura agente
    try:
        client = Neo4jClient()
        client.test_connection()
        print("[ok] Neo4j conectado")
    except Exception as e:
        print(f"\n[ERRO] Neo4j nao disponivel: {e}")
        print("       Certifique-se de que o Neo4j esta rodando antes de otimizar.")
        sys.exit(1)

    agent_module.setup(client)
    agent = agent_module._agent

    # Compila
    compiled = compile_agent(agent)

    # Mostra resumo dos demos encontrados
    print("\n[optimizer] Resumo dos demos gerados:")
    try:
        for i, demo in enumerate(compiled.react.demos or [], 1):
            q = getattr(demo, "question", "?")[:80]
            print(f"  Demo {i}: {q}...")
    except Exception:
        pass

    print("\n[optimizer] Concluido.")
    print("  Execute o servidor normalmente — o prompt otimizado sera carregado automaticamente.")


if __name__ == "__main__":
    main()
