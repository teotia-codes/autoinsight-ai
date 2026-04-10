import os
import uuid
import shutil
import json
import traceback
import asyncio
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

from backend.models import AskRequest
from backend.utils import save_upload_file, get_csv_summary, generate_dataset_profile
from backend.config import OLLAMA_MODEL
from backend.rag.ingest import ingest_document_to_chroma
from backend.rag.retrieve import retrieve_relevant_context
from backend.agents.graph import build_agent_graph
from backend.agents.nodes import (
    planner_node,
    tool_analysis_node,
    target_validation_node,
    data_quality_node,
    kpi_node,
    signal_ranking_node,
    visualization_tool_node,
    ml_readiness_node,
    verifier_node,
    final_report_node,
)

# Optional fine-tuned refinement (disabled by default for low-memory laptops)
ENABLE_FINETUNED_REFINEMENT = os.getenv("ENABLE_FINETUNED_REFINEMENT", "false").lower() == "true"

if ENABLE_FINETUNED_REFINEMENT:
    from backend.services.finetuned_service import load_finetuned_model, refine_full_report_chunked


# ============================================================
# App Setup
# ============================================================
app = FastAPI(title="AutoInsight AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # okay for local dev + Vercel demo
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
CHARTS_ROOT = os.path.join(PROCESSED_DIR, "charts")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(VECTORSTORE_ROOT, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(CHARTS_ROOT, exist_ok=True)

# Serve static files
app.mount("/static", StaticFiles(directory="data"), name="static")


# ============================================================
# Helpers
# ============================================================
def create_new_context_dir() -> str:
    """
    Create a fresh unique vectorstore directory for each uploaded context.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    context_dir = os.path.join(VECTORSTORE_ROOT, f"context_{timestamp}_{unique_id}")
    os.makedirs(context_dir, exist_ok=True)
    return context_dir


def cleanup_old_context_dirs(keep_latest: int = 5):
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

        entries.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        to_delete = entries[keep_latest:]

        for old_dir in to_delete:
            try:
                shutil.rmtree(old_dir, ignore_errors=True)
            except Exception:
                pass

    except Exception:
        pass


def create_chart_output_dir(session_id: str) -> str:
    chart_dir = os.path.join(CHARTS_ROOT, session_id)
    os.makedirs(chart_dir, exist_ok=True)
    return chart_dir


def normalize_chart_paths(chart_paths: list[str]) -> list[str]:
    """
    Convert local paths into /static URLs if possible.
    """
    normalized = []

    for path in chart_paths:
        if not path:
            continue

        path_fixed = path.replace("\\", "/")
        if path_fixed.startswith("data/"):
            normalized.append("/static/" + path_fixed[len("data/"):])
        else:
            normalized.append(path_fixed)

    return normalized


def build_initial_state(request: AskRequest, retrieved_context: str, session_id: str, chart_output_dir: str):
    return {
        "session_id": session_id,
        "chart_output_dir": chart_output_dir,
        "context_dir": request.context_dir,

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

        "signal_ranking_output": "",
        "signal_ranking_structured": {},

        "visualizations": [],
        "chart_paths": [],
        "visualization_summary": "",

        "ml_readiness_output": "",
        "ml_readiness_structured": {},

        "verifier_output": "",
        "final_report": "",
    }


def maybe_refine_report(draft_report: str) -> str:
    final_report = draft_report

    if ENABLE_FINETUNED_REFINEMENT and draft_report and draft_report.strip():
        try:
            print("[Agentic Analysis] Fine-tuned refinement enabled. Running chunked refinement...")
            final_report = refine_full_report_chunked(draft_report)
        except Exception:
            print("[Agentic Analysis] Fine-tuned refinement failed. Falling back to draft report.")
            print(traceback.format_exc())
            final_report = draft_report
    else:
        print("[Agentic Analysis] Stable mode enabled: skipping fine-tuned refinement.")

    return final_report


def sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


# ============================================================
# Health Check
# ============================================================
@app.get("/")
def root():
    return {
        "message": "AutoInsight AI backend is running",
        "model": OLLAMA_MODEL,
        "fine_tuned_refinement_enabled": ENABLE_FINETUNED_REFINEMENT
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
# Upload Context Document (request-safe)
# ============================================================
@app.post("/upload-doc")
async def upload_doc(file: UploadFile = File(...)):
    try:
        if not (file.filename.lower().endswith(".txt") or file.filename.lower().endswith(".md")):
            raise HTTPException(status_code=400, detail="Only .txt or .md files are supported for context.")

        file_path = save_upload_file(file, DOCS_DIR)

        new_context_dir = create_new_context_dir()

        ingest_result = ingest_document_to_chroma(
            file_path=file_path,
            persist_directory=new_context_dir
        )

        cleanup_old_context_dirs(keep_latest=5)

        return {
            "message": "Context document uploaded and indexed successfully",
            "filename": os.path.basename(file_path),
            "file_path": file_path,
            "context_dir": new_context_dir,  # IMPORTANT: frontend should store this
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

        try:
            if request.context_dir:
                retrieved_context = retrieve_relevant_context(
                    query=f"Provide domain context and analytical guidance for dataset: {filename}",
                    persist_directory=request.context_dir
                )
            else:
                retrieved_context = retrieve_relevant_context(
                    query=f"Provide domain context and analytical guidance for dataset: {filename}"
                )
        except TypeError:
            # Backward compatibility if retrieve_relevant_context doesn't yet accept persist_directory
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

        from backend.services.ollama_service import query_ollama
        answer = query_ollama(prompt)

        return {
            "answer": answer,
            "retrieved_context": retrieved_context
        }

    except Exception as e:
        print("DATASET INSIGHT ERROR:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Dataset insight failed: {str(e)}")


# ============================================================
# Legacy Agentic Analysis (still supported)
# ============================================================
@app.post("/agentic-analysis")
async def agentic_analysis(request: AskRequest):
    try:
        if not request.file_path:
            raise HTTPException(status_code=400, detail="file_path is required for agentic analysis.")

        session_id = str(uuid.uuid4())
        chart_output_dir = create_chart_output_dir(session_id)

        try:
            if request.context_dir:
                retrieved_context = retrieve_relevant_context(
                    query=f"Provide domain-specific analytical guidance for dataset: {request.filename or 'dataset'}",
                    persist_directory=request.context_dir
                )
            else:
                retrieved_context = retrieve_relevant_context(
                    query=f"Provide domain-specific analytical guidance for dataset: {request.filename or 'dataset'}"
                )
        except TypeError:
            retrieved_context = retrieve_relevant_context(
                query=f"Provide domain-specific analytical guidance for dataset: {request.filename or 'dataset'}"
            )

        initial_state = build_initial_state(
            request=request,
            retrieved_context=retrieved_context,
            session_id=session_id,
            chart_output_dir=chart_output_dir
        )

        # Keep existing graph flow for non-streaming path
        graph = build_agent_graph()
        result = graph.invoke(initial_state)

        draft_report = result.get("final_report", "")
        final_report = maybe_refine_report(draft_report)

        normalized_chart_paths = normalize_chart_paths(result.get("chart_paths", []))

        return {
            "message": "Agentic analysis completed successfully",
            "session_id": session_id,

            "planner_output": result.get("planner_output", ""),
            "tool_analysis_text": result.get("tool_analysis_text", ""),
            "tool_analysis_result": result.get("tool_analysis_result", {}),

            "target_validation_output": result.get("target_validation_output", ""),
            "target_validation_structured": result.get("target_validation_structured", {}),

            "data_quality_output": result.get("data_quality_output", ""),
            "data_quality_structured": result.get("data_quality_structured", {}),

            "kpi_output": result.get("kpi_output", ""),
            "kpi_structured": result.get("kpi_structured", {}),

            "signal_ranking_output": result.get("signal_ranking_output", ""),
            "signal_ranking_structured": result.get("signal_ranking_structured", {}),

            "visualizations": result.get("visualizations", []),
            "chart_paths": normalized_chart_paths,
            "visualization_summary": result.get("visualization_summary", ""),

            "ml_readiness_output": result.get("ml_readiness_output", ""),
            "ml_readiness_structured": result.get("ml_readiness_structured", {}),

            "verifier_output": result.get("verifier_output", ""),

            "draft_report": draft_report,
            "final_report": final_report,
        }

    except Exception as e:
        print("AGENTIC ANALYSIS ERROR:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Agentic analysis failed: {str(e)}")


# ============================================================
# NEW: Streaming Agentic Analysis (Phase 1 UX upgrade)
# ============================================================
@app.post("/agentic-analysis-stream")
async def agentic_analysis_stream(request: AskRequest):
    if not request.file_path:
        raise HTTPException(status_code=400, detail="file_path is required for agentic analysis.")

    async def event_generator():
        session_id = str(uuid.uuid4())
        chart_output_dir = create_chart_output_dir(session_id)

        try:
            yield sse_event("progress", {
                "step": "initializing",
                "status": "started",
                "message": "Initializing analysis session...",
                "session_id": session_id
            })
            await asyncio.sleep(0.05)

            try:
                if request.context_dir:
                    retrieved_context = retrieve_relevant_context(
                        query=f"Provide domain-specific analytical guidance for dataset: {request.filename or 'dataset'}",
                        persist_directory=request.context_dir
                    )
                else:
                    retrieved_context = retrieve_relevant_context(
                        query=f"Provide domain-specific analytical guidance for dataset: {request.filename or 'dataset'}"
                    )
            except TypeError:
                retrieved_context = retrieve_relevant_context(
                    query=f"Provide domain-specific analytical guidance for dataset: {request.filename or 'dataset'}"
                )

            state = build_initial_state(
                request=request,
                retrieved_context=retrieved_context,
                session_id=session_id,
                chart_output_dir=chart_output_dir
            )

            steps = [
                ("planner", planner_node),
                ("tool_analysis", tool_analysis_node),
                ("target_validation", target_validation_node),
                ("data_quality", data_quality_node),
                ("kpi", kpi_node),
                ("signal_ranking", signal_ranking_node),
                ("visualization_tool", visualization_tool_node),
                ("ml_readiness", ml_readiness_node),
                ("verifier", verifier_node),
                ("final_report", final_report_node),
            ]

            for step_name, step_fn in steps:
                yield sse_event("progress", {
                    "step": step_name,
                    "status": "started",
                    "message": f"{step_name.replace('_', ' ').title()} started"
                })
                await asyncio.sleep(0.05)

                # Run sync node safely in worker thread
                state = await asyncio.to_thread(step_fn, state)

                yield sse_event("progress", {
                    "step": step_name,
                    "status": "completed",
                    "message": f"{step_name.replace('_', ' ').title()} completed"
                })
                await asyncio.sleep(0.05)

            draft_report = state.get("final_report", "")

            yield sse_event("progress", {
                "step": "refinement",
                "status": "started",
                "message": "Refining final report..."
            })
            await asyncio.sleep(0.05)

            final_report = await asyncio.to_thread(maybe_refine_report, draft_report)

            yield sse_event("progress", {
                "step": "refinement",
                "status": "completed",
                "message": "Final report ready"
            })
            await asyncio.sleep(0.05)

            normalized_chart_paths = normalize_chart_paths(state.get("chart_paths", []))

            final_payload = {
                "message": "Agentic analysis completed successfully",
                "session_id": session_id,

                "planner_output": state.get("planner_output", ""),
                "tool_analysis_text": state.get("tool_analysis_text", ""),
                "tool_analysis_result": state.get("tool_analysis_result", {}),

                "target_validation_output": state.get("target_validation_output", ""),
                "target_validation_structured": state.get("target_validation_structured", {}),

                "data_quality_output": state.get("data_quality_output", ""),
                "data_quality_structured": state.get("data_quality_structured", {}),

                "kpi_output": state.get("kpi_output", ""),
                "kpi_structured": state.get("kpi_structured", {}),

                "signal_ranking_output": state.get("signal_ranking_output", ""),
                "signal_ranking_structured": state.get("signal_ranking_structured", {}),

                "visualizations": state.get("visualizations", []),
                "chart_paths": normalized_chart_paths,
                "visualization_summary": state.get("visualization_summary", ""),

                "ml_readiness_output": state.get("ml_readiness_output", ""),
                "ml_readiness_structured": state.get("ml_readiness_structured", {}),

                "verifier_output": state.get("verifier_output", ""),

                "draft_report": draft_report,
                "final_report": final_report,
            }

            yield sse_event("done", final_payload)

        except Exception as e:
            print("STREAMING AGENTIC ANALYSIS ERROR:\n", traceback.format_exc())
            yield sse_event("error", {
                "message": f"Agentic analysis failed: {str(e)}"
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================
# Startup
# ============================================================
@app.on_event("startup")
async def preload_models():
    try:
        print("[Startup] AutoInsight backend starting...")
        print(f"[Startup] Ollama model configured: {OLLAMA_MODEL}")

        if ENABLE_FINETUNED_REFINEMENT:
            print("[Startup] Fine-tuned refinement is ENABLED. Preloading model...")
            load_finetuned_model()
            print("[Startup] Fine-tuned model preloaded successfully.")
        else:
            print("[Startup] Fine-tuned refinement is DISABLED (stable mode).")

    except Exception as e:
        print(f"[Startup] Optional model preload failed: {e}")