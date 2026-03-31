"""
RAG Pipeline: Document processing, embedding, and retrieval for the business chatbot.

Supports: .txt, .pdf, .csv, .xlsx files
Uses: FAISS for vector storage, OpenAI embeddings for semantic search
"""

import os
import hashlib
import pickle
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Optional imports for file types
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    import pandas as pd
except ImportError:
    pd = None


UPLOAD_DIR = Path("uploads")
INDEX_DIR = Path("index_store")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


class RAGPipeline:
    """Handles document ingestion, chunking, embedding, and retrieval."""

    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self.index: Optional[faiss.IndexFlatL2] = None
        self.chunks: list[dict] = []  # {text, source, chunk_id}
        self._ensure_dirs()
        self._load_index()

    # ── Directory Setup ──────────────────────────────────────────────

    @staticmethod
    def _ensure_dirs():
        UPLOAD_DIR.mkdir(exist_ok=True)
        INDEX_DIR.mkdir(exist_ok=True)

    # ── File Reading ─────────────────────────────────────────────────

    def read_file(self, file_path: str) -> str:
        """Read content from a supported file type."""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            return path.read_text(encoding="utf-8")

        if suffix == ".pdf":
            return self._read_pdf(path)

        if suffix in (".csv", ".xlsx"):
            return self._read_tabular(path, suffix)

        raise ValueError(f"Unsupported file type: {suffix}")

    @staticmethod
    def _read_pdf(path: Path) -> str:
        if PyPDF2 is None:
            raise ImportError("Install PyPDF2 to process PDF files: pip install PyPDF2")
        text_parts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    @staticmethod
    def _read_tabular(path: Path, suffix: str) -> str:
        if pd is None:
            raise ImportError("Install pandas to process tabular files: pip install pandas")
        if suffix == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)
        return df.to_string(index=False)

    # ── Chunking ─────────────────────────────────────────────────────

    def chunk_text(self, text: str, source: str) -> list[dict]:
        """Split text into chunks with source metadata."""
        splits = self.text_splitter.split_text(text)
        return [
            {
                "text": chunk,
                "source": source,
                "chunk_id": hashlib.sha256(f"{source}:{i}:{chunk[:50]}".encode()).hexdigest()[:12],
            }
            for i, chunk in enumerate(splits)
        ]

    # ── Embeddings ───────────────────────────────────────────────────

    def _embed(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for a list of texts."""
        response = self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        vectors = [item.embedding for item in response.data]
        return np.array(vectors, dtype="float32")

    # ── Indexing ──────────────────────────────────────────────────────

    def ingest_file(self, file_path: str) -> int:
        """Process a file: read → chunk → embed → index. Returns chunk count."""
        text = self.read_file(file_path)
        if not text.strip():
            return 0

        source = Path(file_path).name
        new_chunks = self.chunk_text(text, source)
        if not new_chunks:
            return 0

        texts = [c["text"] for c in new_chunks]
        vectors = self._embed(texts)

        if self.index is None:
            self.index = faiss.IndexFlatL2(EMBEDDING_DIM)

        self.index.add(vectors)
        self.chunks.extend(new_chunks)
        self._save_index()
        return len(new_chunks)

    def ingest_text(self, text: str, source: str = "direct_input") -> int:
        """Ingest raw text directly. Returns chunk count."""
        if not text.strip():
            return 0

        new_chunks = self.chunk_text(text, source)
        if not new_chunks:
            return 0

        texts = [c["text"] for c in new_chunks]
        vectors = self._embed(texts)

        if self.index is None:
            self.index = faiss.IndexFlatL2(EMBEDDING_DIM)

        self.index.add(vectors)
        self.chunks.extend(new_chunks)
        self._save_index()
        return len(new_chunks)

    # ── Retrieval ────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        """Retrieve the most relevant chunks for a query."""
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vec = self._embed([query])
        distances, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx].copy()
            chunk["score"] = float(dist)
            results.append(chunk)
        return results

    def get_context_string(self, query: str, top_k: int = 3) -> str:
        """Retrieve chunks and format them as a context string for the LLM."""
        results = self.retrieve(query, top_k)
        if not results:
            return ""

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(f"[Source: {r['source']}]\n{r['text']}")
        return "\n\n---\n\n".join(parts)

    # ── Persistence ──────────────────────────────────────────────────

    def _save_index(self):
        if self.index is not None:
            faiss.write_index(self.index, str(INDEX_DIR / "faiss.index"))
        with open(INDEX_DIR / "chunks.pkl", "wb") as f:
            pickle.dump(self.chunks, f)

    def _load_index(self):
        index_path = INDEX_DIR / "faiss.index"
        chunks_path = INDEX_DIR / "chunks.pkl"
        if index_path.exists() and chunks_path.exists():
            self.index = faiss.read_index(str(index_path))
            with open(chunks_path, "rb") as f:
                self.chunks = pickle.load(f)

    # ── Management ───────────────────────────────────────────────────

    def clear_index(self):
        """Remove all indexed data."""
        self.index = None
        self.chunks = []
        for p in INDEX_DIR.iterdir():
            p.unlink()

    def get_stats(self) -> dict:
        """Return index statistics."""
        sources = set(c["source"] for c in self.chunks) if self.chunks else set()
        return {
            "total_chunks": len(self.chunks),
            "total_vectors": self.index.ntotal if self.index else 0,
            "sources": sorted(sources),
        }
