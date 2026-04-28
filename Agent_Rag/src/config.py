"""
Configuração centralizada — carrega .env e expõe constantes.
"""

import os
from dotenv import load_dotenv

# Carrega .env de Agent_Rag/
_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_ENV_PATH)

# --- Neo4j ---
NEO4J_URL = os.getenv("NEO4J_URL", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "testpassword")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# --- LLM (OpenRouter via DSPy/LiteLLM) ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
_raw_model = os.getenv("DSPY_MODEL", "openrouter/deepseek/deepseek-chat-v3-0324:free")
DSPY_MODEL = _raw_model if _raw_model.startswith("openrouter/") else f"openrouter/{_raw_model}"
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

# --- Caminhos ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_RAW_PATH = os.path.join(PROJECT_ROOT, "data", "raw")
DATA_PROCESSED_PATH = os.path.join(PROJECT_ROOT, "data", "processed")
CSV_PATH = os.path.join(DATA_PROCESSED_PATH, "user_stories_embeddings.csv")
COMPILED_AGENT_PATH = os.path.join(PROJECT_ROOT, "compiled_agent.json")
