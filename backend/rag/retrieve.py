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


def retrieve_relevant_context(query: str, k: int = 4) -> str:
    """
    Retrieve relevant context only from the currently active context vectorstore.
    """
    persist_directory = get_current_context_dir()

    if not persist_directory:
        return "No context document available."

    try:
        embeddings = get_embedding_model()

        vectordb = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )

        docs = vectordb.similarity_search(query, k=k)

        if not docs:
            return "No relevant context found."

        return "\n\n".join([doc.page_content for doc in docs])

    except Exception as e:
        return f"Context retrieval failed: {str(e)}"