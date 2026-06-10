## TCC 2

# ARQUITETURA

Seguindo paradigmas de POO e clean Arctecture a arquitetura definida foi focada em separar a lógica de domínio (o grafo) da infraestrutura (Neo4j, FastAPI) e das ferramentas de ingestão de dados.

```
/
├── data/                       # Dataset original e persistência local
│   ├── raw/                    # CSVs originais
│   └── processed/              # CSVs com embeddings e processados
│
├── src/                        # Código fonte unificado (modularizado)
│   ├── core/                   # Domínio e Interfaces (POO pura)
│   │   ├── entities.py         # Classes Requirement, Concept, Technique
│   │   └── interfaces.py       # Classes abstratas (BaseGraphClient, BaseAgent)
│   │
│   ├── infra/                  # Implementações de tecnologias (Infra)
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
│   ├── api/                    # Camada de Entrega - FastAPI
│   │   ├── routes/             # Endpoints (chat.py, graph.py)
│   │   └── main.py             # App entry point
│   │
│   └── scripts/                # Scripts de utilidade
│       ├── ingest_data.py      # Script para ler CSV e povoar o banco
│       ├── build_metrics.py    # Cálculo de Louvain e comunidades
│       └── generate_embeds.py  # Geração de embeddings
│
├── frontend/                   # Aplicação React (mantém separada pela stack)
│
├── docker-compose.yml          # Neo4j via Docker
├── .env.example                # Exemplo de variáveis de ambiente
├── requirements.txt            # Dependências consolidadas
└── README.md

```

# COMO RODAR

## 1. Banco de dados (Neo4j)

```bash
docker compose up -d
```

O Neo4j sobe em `bolt://localhost:7687` e a interface web em `http://localhost:7474` (usuário: `neo4j`, senha: `testpassword`).

## 2. Backend (FastAPI)

```bash
source ../venv/bin/activate       # ativar o virtualenv (da raiz do projeto)
pip install -r requirements.txt   # instalar dependências (primeira vez apenas)
python -m src.api.main            # sobe em http://localhost:8000
```

## 3. Frontend (React/Vite)

```bash
cd ../frontend
npm install                       # instalar dependências (primeira vez apenas)
npm run dev                       # sobe em http://localhost:5173
```