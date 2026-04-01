import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# New packages (preferred)
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

from backend.rag.embeddings import get_embedding_model


def ingest_document_to_chroma(file_path: str, persist_directory: str) -> dict:
    """
    Ingest a text document into a dedicated Chroma persist directory.
    Each context upload should get its own persist_directory.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    os.makedirs(persist_directory, exist_ok=True)

    loader = TextLoader(file_path, encoding="utf-8")
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    split_docs = splitter.split_documents(docs)

    embeddings = get_embedding_model()

    vectordb = Chroma.from_documents(
        documents=split_docs,
        embedding=embeddings,
        persist_directory=persist_directory
    )

    # For compatibility across versions
    try:
        vectordb.persist()
    except Exception:
        pass

    return {
        "chunks_ingested": len(split_docs),
        "persist_directory": persist_directory
    }