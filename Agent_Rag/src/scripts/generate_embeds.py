#!/usr/bin/env python3
"""
Gera embeddings OpenAI para as user stories e salva em CSV.

Entrada: data/raw/user_stories.csv
Saída: data/processed/user_stories_embeddings.csv

Executar a partir da raiz do Agent_Rag/:
    python -m src.scripts.generate_embeds
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
from openai import OpenAI
from src import config


def main():
    input_path = os.path.join(config.DATA_RAW_PATH, "user_stories.csv")
    output_path = os.path.join(config.DATA_PROCESSED_PATH, "user_stories_embeddings.csv")
    os.makedirs(config.DATA_PROCESSED_PATH, exist_ok=True)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    df = pd.read_csv(input_path, delimiter=";")
    df["embedding"] = None
    df["embedding"] = df["embedding"].astype(object)

    batch_size = 50
    for start in range(0, len(df), batch_size):
        end = min(start + batch_size, len(df))
        print(f"Processando batch {start + 1} a {end}...")

        embeddings = []
        for text in df.iloc[start:end]["user_story"]:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=str(text),
            )
            embeddings.append(response.data[0].embedding)

        for i, emb in enumerate(embeddings):
            df.at[start + i, "embedding"] = str(emb)

        df.to_csv(output_path, sep=";", index=False)
        print(f"Batch {start + 1} a {end} concluído e salvo.")

    print(f"Arquivo final salvo em: {output_path}")


if __name__ == "__main__":
    main()
