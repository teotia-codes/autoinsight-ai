import os

# Preferred package
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

from backend.rag.embeddings import get_embedding_model


VECTORSTORE_ROOT = os.path.join("data", "vectorstore")
CURRENT_CONTEXT_FILE = os.path.join(VECTORSTORE_ROOT, "current_context.txt")


def get_current_context_dir() -> str | None:
    """
    Returns the currently active context vectorstore directory.
    """
    if not os.path.exists(CURRENT_CONTEXT_FILE):
        return None

    try:
        with open(CURRENT_CONTEXT_FILE, "r", encoding="utf-8") as f:
            path = f.read().strip()
            if path and os.path.exists(path):
                return path
    except Exception:
        return None

    return None

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

def retrieve_relevant_context(query: str, k: int = 3, persist_directory: str = None) -> str:
    try:
        if not persist_directory:
            persist_directory = "./data/vectorstore"

        embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

        vectordb = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )

        docs = vectordb.similarity_search(query, k=k)

        if not docs:
            return ""

        return "\n\n".join([d.page_content for d in docs])

    except Exception as e:
        print(f"[retrieve_relevant_context] Error: {e}")
        return ""