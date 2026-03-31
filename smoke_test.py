"""Smoke test: validates API connection, RAG ingestion, retrieval, and chat."""

from dotenv import load_dotenv
load_dotenv()

import os

print("1. Checking API key...", end=" ")
key = os.getenv("OPENAI_API_KEY")
assert key and key.startswith("sk-"), "OPENAI_API_KEY not set"
print("OK")

print("2. Initializing RAG pipeline...", end=" ")
from rag_pipeline import RAGPipeline
rag = RAGPipeline()
print("OK")

print("3. Ingesting sample text...", end=" ")
count = rag.ingest_text(
    "The company Q1 revenue was $4.2 million, up 15% from last year. "
    "The main growth driver was the enterprise segment.",
    source="q1_report.txt",
)
print(f"OK ({count} chunks)")

print("4. Retrieving context...", end=" ")
results = rag.retrieve("What was the Q1 revenue?")
assert len(results) > 0, "No results returned"
print(f"OK ({len(results)} results)")
print(f"   Top result: {results[0]['text'][:80]}...")

print("5. Testing chat completion...", end=" ")
from chat import ChatSession
session = ChatSession(rag)
reply = session.send("What was the Q1 revenue?")
print("OK")
print(f"   Reply: {reply[:200]}")

print("6. Cleanup...", end=" ")
rag.clear_index()
print("OK")

print("\nAll smoke tests passed!")
