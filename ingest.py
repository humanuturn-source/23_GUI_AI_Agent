"""
ingest.py
Chunks ./documents/serengeti.md and stores embeddings in local ChromaDB
collection `serengeti_knowledge` using Ollama embeddings.
"""

import os
import ollama
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

DOCS_FILE = "./documents/serengeti.md"
CHROMA_PATH = "./data/chroma_db"
COLLECTION_NAME = "serengeti_knowledge"
EMBED_MODEL = "nomic-embed-text"


def get_embedding(text: str) -> list[float]:
    res = ollama.embeddings(model=EMBED_MODEL, prompt=text)
    return res["embedding"]


def get_serengeti_collection() -> chromadb.Collection:
    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name=COLLECTION_NAME)


def ingest_serengeti_document() -> None:
    if not os.path.exists(DOCS_FILE):
        os.makedirs(os.path.dirname(DOCS_FILE), exist_ok=True)
        print(f"[!] Place serengeti.md at {DOCS_FILE} and re-run.")
        return

    with open(DOCS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " "],
    )
    chunks = splitter.split_text(content)
    col = get_serengeti_collection()

    print(f"[*] Embedding {len(chunks)} chunks from serengeti.md...")
    for idx, chunk in enumerate(chunks):
        col.upsert(
            ids=[f"serengeti_chunk_{idx}"],
            embeddings=[get_embedding(chunk)],
            documents=[chunk],
            metadatas=[{"source": "serengeti.md", "chunk_index": idx}],
        )
    print(f"[OK] Stored {len(chunks)} chunks in '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    ingest_serengeti_document()
