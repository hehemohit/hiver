import os
from pathlib import Path
from typing import Any
import chromadb
from chromadb.utils import embedding_functions
import pandas as pd


class SupportKnowledgeBase:

  def __init__(
      self,
      persist_directory: str = "data/chroma_db",
      collection_name: str = "apple_support_corpus",
  ):
    self.persist_directory = persist_directory
    self.client = chromadb.PersistentClient(path=persist_directory)

    # Uses Chroma's native, lightweight ONNX all-MiniLM-L6-v2 (no torch installation needed)
    self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()

    self.collection = self.client.get_or_create_collection(
        name=collection_name,
        embedding_function=self.embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

  def index_corpus(
      self,
      parquet_path: str = "data/processed/retrieval_corpus.parquet",
      max_samples: int = 3000,
      batch_size: int = 250,
  ):
    """Embeds historical customer queries and maps them to the brand's verified answer."""
    df = pd.read_parquet(parquet_path)
    if len(df) > max_samples:
      df = df.sample(n=max_samples, random_state=42).reset_index(drop=True)

    print(
        f"[*] Indexing {len(df):,} conversation pairs into ChromaDB"
        f" ('{self.persist_directory}')..."
    )

    total = len(df)
    for i in range(0, total, batch_size):
      batch = df.iloc[i : i + batch_size]
      ids = [str(x) for x in batch["tweet_id"].tolist()]
      documents = batch["text_customer"].tolist()
      metadatas = [
          {
              "agent_reply": row["text_agent"],
              "historically_escalated": bool(row["historically_escalated"]),
          }
          for _, row in batch.iterrows()
      ]

      self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
      print(
          f"    -> Indexed batch {i + len(batch)}/{total} ("
          f"{((i + len(batch)) / total) * 100:.1f}%)"
      )

    print(f"[+] Successfully populated collection '{self.collection.name}'.")

  def query_similar(self, customer_query: str, top_k: int = 3) -> list[dict]:
    """Retrieves top_k historically resolved issues matching the incoming text."""
    results = self.collection.query(
        query_texts=[customer_query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    matches = []
    if results and results["documents"]:
      for doc, meta, dist in zip(
          results["documents"][0],
          results["metadatas"][0],
          results["distances"][0],
      ):
        matches.append({
            "similar_query": doc,
            "resolved_reply": meta["agent_reply"],
            "historically_escalated": meta["historically_escalated"],
            "similarity_score": round(1.0 - dist, 4),
        })
    return matches


if __name__ == "__main__":
  kb = SupportKnowledgeBase()
  kb.index_corpus(max_samples=3000)

  sample_q = "My iPhone 13 battery dies in 3 hours after updating iOS"
  results = kb.query_similar(sample_q, top_k=2)
  print(f"\n[Test Query]: {sample_q}")
  for idx, res in enumerate(results, 1):
    print(f"\n--- Match {idx} (Score: {res['similarity_score']}) ---")
    print(f"Customer: {res['similar_query']}")
    print(f"Brand:    {res['resolved_reply']}")