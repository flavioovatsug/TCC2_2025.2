## TCC 2

# ARQUITETURA


Seguindo paradigmas de POO e clean Arctecture a arquitetura definida foi focada em separar a lógica de domínio (o grafo) da infraestrutura (Neo4j, FastAPI) e das ferramentas de ingestão de dados.


```
/
├── data/                       # Dataset original e persistência local (antiga 'Dados/')
│   ├── raw/                    # CSVs originais
│   └── processed/              # CSVs com embeddings e processados
│
├── src/                        # Código fonte unificado (modularizado)
│   ├── core/                   # Domínio e Interfaces (POO pura)
│   │   ├── entities.py         # Classes Requirement, Concept, Technique (Data Classes)
│   │   └── interfaces.py       # Classes abstratas (BaseGraphClient, BaseAgent)
│   │
│   ├── infrastructure/         # Implementações de tecnologias (Infra)
│   │   ├── neo4j/              # Tudo sobre Neo4j
│   │   │   ├── client.py       # Neo4jClient implementando BaseGraphClient
│   │   │   └── queries.py      # Queries Cypher isoladas
│   │   └── dspy/               # Scripts do Agente e Otimização
│   │       ├── agent.py        # GraphRAGAgent (DSPy Module)
│   │       └── signatures.py   # DSPy Signatures e instruções de prompt
│   │
│   ├── service/                # Orquestração (Casos de Uso)
│   │   ├── graph_service.py    # Lógica de negócio para manipular o grafo
│   │   └── chat_service.py     # Lógica do fluxo de conversa
│   │
│   ├── api/                    # Camada de Entrega - FastAPI (antiga 'backend/')
│   │   ├── routes/             # Endpoints (chat.py, graph.py)
│   │   └── main.py             # App entry point
│   │
│   └── scripts/                # Scripts de utilidade (antiga 'Knowledge_Graphs/')
│       ├── ingest_data.py      # Script para ler CSV e povoar o banco
│       ├── build_metrics.py    # Cálculo de Louvain e comunidades
│       └── generate_embeds.py  # Geração de embeddings (antiga 'embedding.py')
│
├── frontend/                   # Aplicação React (mantém separada pela stack)
│
├── .env.example                # Exemplo de variáveis de ambiente
├── requirements.txt            # Dependências consolidadas
└── README.md

```