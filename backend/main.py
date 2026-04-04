import os
import uuid
import shutil
import traceback
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.models import AskRequest
from backend.utils import save_upload_file, get_csv_summary, generate_dataset_profile
from backend.config import OLLAMA_MODEL
from backend.services.ollama_service import query_ollama
from backend.rag.ingest import ingest_document_to_chroma
from backend.rag.retrieve import retrieve_relevant_context
from backend.agents.graph import build_agent_graph
from backend.services.finetuned_service import load_finetuned_model

# ============================================================
# App Setup
# ============================================================
app = FastAPI(title="AutoInsight AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Paths
# ============================================================
UPLOAD_DIR = os.path.join("data", "uploads")
DOCS_DIR = os.path.join("data", "docs")
VECTORSTORE_ROOT = os.path.join("data", "vectorstore")
PROCESSED_DIR = os.path.join("data", "processed")
CURRENT_CONTEXT_FILE = os.path.join(VECTORSTORE_ROOT, "current_context.txt")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(VECTORSTORE_ROOT, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


# ============================================================
# Windows-Safe Context Management
# ============================================================
def create_new_context_dir() -> str:
    """
    Create a fresh unique vectorstore directory for each uploaded context.
    This avoids Windows file-lock issues with Chroma.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    context_dir = os.path.join(VECTORSTORE_ROOT, f"context_{timestamp}_{unique_id}")
    os.makedirs(context_dir, exist_ok=True)
    return context_dir


def set_current_context_dir(path: str):
    os.makedirs(VECTORSTORE_ROOT, exist_ok=True)
    with open(CURRENT_CONTEXT_FILE, "w", encoding="utf-8") as f:
        f.write(path)


def get_current_context_dir() -> str | None:
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


def cleanup_old_context_dirs(keep_latest: int = 2):
    """
    Best-effort cleanup of old context dirs.
    Safe on Windows: failures are ignored.
    """
    try:
        if not os.path.exists(VECTORSTORE_ROOT):
            return

        entries = []
        for name in os.listdir(VECTORSTORE_ROOT):
            full_path = os.path.join(VECTORSTORE_ROOT, name)
            if os.path.isdir(full_path) and name.startswith("context_"):
                entries.append(full_path)

        # Sort by modified time (newest first)
        entries.sort(key=lambda p: os.path.getmtime(p), reverse=True)

        to_delete = entries[keep_latest:]

        for old_dir in to_delete:
            try:
                shutil.rmtree(old_dir, ignore_errors=True)
            except Exception:
                # Ignore locked folders on Windows
                pass

    except Exception:
        pass


# ============================================================
# Health Check
# ============================================================
@app.get("/")
def root():
    return {
        "message": "AutoInsight AI backend is running",
        "model": OLLAMA_MODEL
    }


# ============================================================
# Upload CSV
# ============================================================
@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported.")

        file_path = save_upload_file(file, UPLOAD_DIR)

        summary_text = get_csv_summary(file_path)
        dataset_profile = generate_dataset_profile(file_path)

        return {
            "message": "CSV uploaded successfully",
            "filename": os.path.basename(file_path),
            "file_path": file_path,
            "summary_text": summary_text,
            "dataset_profile": dataset_profile,
        }

    except Exception as e:
        print("UPLOAD CSV ERROR:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"CSV upload failed: {str(e)}")


# ============================================================
# Upload Context Document (Windows-safe)
# ============================================================
@app.post("/upload-doc")
async def upload_doc(file: UploadFile = File(...)):
    try:
        if not (file.filename.lower().endswith(".txt") or file.filename.lower().endswith(".md")):
            raise HTTPException(status_code=400, detail="Only .txt or .md files are supported for context.")

        # Save doc file
        file_path = save_upload_file(file, DOCS_DIR)

        # Create a brand new isolated vectorstore directory
        new_context_dir = create_new_context_dir()

        # Ingest into this dedicated directory
        ingest_result = ingest_document_to_chroma(
            file_path=file_path,
            persist_directory=new_context_dir
        )

        # Mark this as the active context
        set_current_context_dir(new_context_dir)

        # Best-effort cleanup of older inactive contexts
        cleanup_old_context_dirs(keep_latest=2)

        return {
            "message": "Context document uploaded and indexed successfully",
            "filename": os.path.basename(file_path),
            "file_path": file_path,
            "active_context_dir": new_context_dir,
            "chunks_ingested": ingest_result.get("chunks_ingested", 0),
        }

    except Exception as e:
        print("UPLOAD DOC ERROR:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")


# ============================================================
# Basic Dataset Insight (LLM + RAG)
# ============================================================
@app.post("/dataset-insight")
async def dataset_insight(request: AskRequest):
    try:
        summary_text = request.summary_text or ""
        filename = request.filename or "uploaded_dataset.csv"

        retrieved_context = retrieve_relevant_context(
            query=f"Provide domain context and analytical guidance for dataset: {filename}"
        )

        prompt = f"""
You are an expert data analyst AI.

A user uploaded a dataset: {filename}

Dataset summary:
{summary_text}

Retrieved domain context:
{retrieved_context}

Task:
- Briefly explain what kind of dataset this appears to be
- Mention likely analytical goals
- Mention likely target column candidates (if any)
- Mention possible business or ML use cases
- Keep it practical and concise
"""

        answer = query_ollama(prompt)

        return {
            "answer": answer,
            "retrieved_context": retrieved_context
        }

    except Exception as e:
        print("DATASET INSIGHT ERROR:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Dataset insight failed: {str(e)}")


# ============================================================
# Agentic Analysis (Phase 5)
# ============================================================
@app.post("/agentic-analysis")
async def agentic_analysis(request: AskRequest):
    try:
        if not request.file_path:
            raise HTTPException(status_code=400, detail="file_path is required for agentic analysis.")

        graph = build_agent_graph()

        retrieved_context = retrieve_relevant_context(
            query=f"Provide domain-specific analytical guidance for dataset: {request.filename or 'dataset'}"
        )

        initial_state = {
            "filename": request.filename or os.path.basename(request.file_path),
            "file_path": request.file_path,
            "summary_text": request.summary_text or "",
            "retrieved_context": retrieved_context,

            "planner_output": "",

            "tool_analysis_result": {},
            "tool_analysis_text": "",

            "target_validation_output": "",
            "target_validation_structured": {},

            "data_quality_output": "",
            "data_quality_structured": {},

            "kpi_output": "",
            "kpi_structured": {},

            "feature_importance_output": "",
            "feature_importance_structured": {},

            "visualizations": [],
            "chart_paths": [],
            "visualization_summary": "",

            "ml_readiness_output": "",
            "ml_readiness_structured": {},

            "verifier_output": "",
            "final_report": "",
        }

        result = graph.invoke(initial_state)

        return {
            "message": "Agentic analysis completed successfully",

            "planner_output": result.get("planner_output", ""),
            "tool_analysis_text": result.get("tool_analysis_text", ""),

            "target_validation_output": result.get("target_validation_output", ""),
            "target_validation_structured": result.get("target_validation_structured", {}),

            "data_quality_output": result.get("data_quality_output", ""),
            "data_quality_structured": result.get("data_quality_structured", {}),

            "kpi_output": result.get("kpi_output", ""),
            "kpi_structured": result.get("kpi_structured", {}),

            "feature_importance_output": result.get("feature_importance_output", ""),
            "feature_importance_structured": result.get("feature_importance_structured", {}),

            "visualizations": result.get("visualizations", []),
            "chart_paths": result.get("chart_paths", []),
            "visualization_summary": result.get("visualization_summary", ""),

            "ml_readiness_output": result.get("ml_readiness_output", ""),
            "ml_readiness_structured": result.get("ml_readiness_structured", {}),

            "verifier_output": result.get("verifier_output", ""),
            "final_report": result.get("final_report", ""),
        }

    except Exception as e:
        print("AGENTIC ANALYSIS ERROR:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Agentic analysis failed: {str(e)}")
@app.on_event("startup")
async def preload_models():
    try:
        print("[Startup] Preloading fine-tuned model...")
        load_finetuned_model()
        print("[Startup] Fine-tuned model preloaded successfully.")
    except Exception as e:
        print(f"[Startup] Fine-tuned model preload failed: {e}")    