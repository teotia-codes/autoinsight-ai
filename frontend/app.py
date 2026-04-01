import os
import requests
import streamlit as st
import pandas as pd

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="AutoInsight AI", layout="wide")
st.title("🤖 AutoInsight AI")
st.caption("Domain-Agnostic LLM + RAG + Agentic Data Analysis Platform")


# ============================================================
# Helpers
# ============================================================
def save_uploaded_report(content: str, filename: str):
    """Optional local save helper if you want to persist in frontend runtime."""
    report_dir = "generated_reports"
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def get_dataset_profile(csv_response: dict) -> dict:
    """
    Supports both:
    1. New backend format -> dataset_profile nested
    2. Old backend format -> top-level fields
    """
    if not csv_response:
        return {}

    # New backend format
    if "dataset_profile" in csv_response and isinstance(csv_response["dataset_profile"], dict):
        return csv_response["dataset_profile"]

    # Backward compatibility (old format)
    return {
        "filename": csv_response.get("filename", "unknown.csv"),
        "shape": csv_response.get("shape", {"rows": 0, "columns": 0}),
        "columns": csv_response.get("columns", []),
        "missing_values": csv_response.get("missing_values", {}),
        "preview": csv_response.get("preview", []),
        "numeric_summary": csv_response.get("numeric_summary", {}),
    }


# ============================================================
# Session State
# ============================================================
if "csv_response" not in st.session_state:
    st.session_state.csv_response = None

if "doc_uploaded" not in st.session_state:
    st.session_state.doc_uploaded = False

if "dataset_insight" not in st.session_state:
    st.session_state.dataset_insight = None

if "agentic_result" not in st.session_state:
    st.session_state.agentic_result = None


# ============================================================
# Sidebar
# ============================================================
st.sidebar.header("⚙️ Workflow")
st.sidebar.markdown("""
1. Upload business/domain context document (optional but recommended for RAG)  
2. Upload CSV dataset  
3. Generate basic AI insight  
4. Run deep agentic analysis  
5. Review charts + final report  
6. Download final report  
""")


# ============================================================
# 1. Upload Context Document
# ============================================================
st.header("1️⃣ Upload Business / Domain Context (Optional)")
doc_file = st.file_uploader(
    "Upload .txt / .md context document",
    type=["txt", "md"],
    key="doc_uploader"
)

if doc_file is not None:
    if st.button("Upload Context Document"):
        with st.spinner("Uploading and indexing context..."):
            try:
                files = {"file": (doc_file.name, doc_file.getvalue(), doc_file.type)}
                res = requests.post(f"{BACKEND_URL}/upload-doc", files=files)

                if res.status_code == 200:
                    data = res.json()
                    st.success(data.get("message", "Context uploaded successfully."))

                    # Support both old and new backend keys
                    chunks = data.get("chunks_ingested", data.get("chunks_added", 0))
                    st.info(f"Chunks indexed: {chunks}")

                    active_context_dir = data.get("active_context_dir")
                    if active_context_dir:
                        st.caption(f"Active context: {active_context_dir}")

                    st.session_state.doc_uploaded = True
                else:
                    st.error(f"Context upload failed: {res.text}")

            except Exception as e:
                st.error(f"Context upload failed: {str(e)}")


# ============================================================
# 2. Upload CSV
# ============================================================
st.header("2️⃣ Upload CSV Dataset")
csv_file = st.file_uploader("Upload CSV file", type=["csv"], key="csv_uploader")

if csv_file is not None:
    if st.button("Upload CSV"):
        with st.spinner("Uploading CSV and profiling dataset..."):
            try:
                files = {"file": (csv_file.name, csv_file.getvalue(), csv_file.type)}
                res = requests.post(f"{BACKEND_URL}/upload-csv", files=files)

                if res.status_code == 200:
                    st.session_state.csv_response = res.json()
                    st.session_state.dataset_insight = None
                    st.session_state.agentic_result = None
                    st.success("CSV uploaded successfully!")
                else:
                    st.error(f"CSV upload failed: {res.text}")

            except Exception as e:
                st.error(f"CSV upload failed: {str(e)}")


# ============================================================
# 3. Show CSV Profile
# ============================================================
if st.session_state.csv_response:
    csv_data = st.session_state.csv_response
    profile = get_dataset_profile(csv_data)

    st.header("3️⃣ Dataset Profile")

    shape = profile.get("shape", {})
    rows = shape.get("rows", 0)
    cols = shape.get("columns", 0)

    filename = csv_data.get("filename") or profile.get("filename", "unknown.csv")

    col1, col2, col3 = st.columns(3)
    col1.metric("Rows", rows)
    col2.metric("Columns", cols)
    col3.metric("Filename", filename)

    st.subheader("📋 Columns")
    columns = profile.get("columns", [])
    if columns:
        st.write(columns)
    else:
        st.info("No columns available.")

    st.subheader("❗ Missing Values")
    missing_values = profile.get("missing_values", {})
    if missing_values:
        st.json(missing_values)
    else:
        st.info("No missing values info available.")

    st.subheader("👀 Preview (First 5 Rows)")
    preview = profile.get("preview", [])
    if preview:
        preview_df = pd.DataFrame(preview)
        st.dataframe(preview_df, use_container_width=True)
    else:
        st.info("No preview available.")

    st.subheader("📈 Numeric Summary")
    numeric_summary = profile.get("numeric_summary", {})
    if numeric_summary:
        st.json(numeric_summary)
    else:
        st.info("No numeric columns found.")


# ============================================================
# 4. Basic AI Insight
# ============================================================
if st.session_state.csv_response:
    st.header("4️⃣ Basic AI Dataset Insight")

    if st.button("Generate Basic AI Insight"):
        with st.spinner("Generating AI insight..."):
            try:
                payload = {
                    "filename": st.session_state.csv_response.get("filename"),
                    "summary_text": st.session_state.csv_response.get("summary_text", "")
                }
                res = requests.post(f"{BACKEND_URL}/dataset-insight", json=payload)

                if res.status_code == 200:
                    data = res.json()

                    # New backend returns "answer"
                    # Old backend may return "insight"
                    st.session_state.dataset_insight = data.get("answer") or data.get("insight") or "No insight returned."
                else:
                    st.error(f"Dataset insight failed: {res.text}")

            except Exception as e:
                st.error(f"Insight generation failed: {str(e)}")

    if st.session_state.dataset_insight:
        st.markdown(st.session_state.dataset_insight)


# ============================================================
# 5. Deep Agentic Analysis
# ============================================================
if st.session_state.csv_response:
    st.header("5️⃣ Deep Agentic Analysis")

    if st.button("Run Deep Agentic Analysis"):
        with st.spinner("Running planner → tools → target validation → DQ → KPI → feature importance → visualization → ML readiness → verifier → final report..."):
            try:
                payload = {
                    "filename": st.session_state.csv_response.get("filename"),
                    "file_path": st.session_state.csv_response.get("file_path"),
                    "summary_text": st.session_state.csv_response.get("summary_text", ""),
                }

                res = requests.post(f"{BACKEND_URL}/agentic-analysis", json=payload)

                if res.status_code == 200:
                    st.session_state.agentic_result = res.json()
                    st.success("Deep agentic analysis completed!")
                else:
                    st.error(f"Agentic analysis failed: {res.text}")

            except Exception as e:
                st.error(f"Agentic analysis failed: {str(e)}")


# ============================================================
# 6. Show Agentic Results
# ============================================================
if st.session_state.agentic_result:
    result = st.session_state.agentic_result

    st.header("6️⃣ Agentic Analysis Results")

    with st.expander("🧠 Planner Output", expanded=False):
        st.markdown(result.get("planner_output", "No planner output."))

    with st.expander("🛠️ Tool Analysis", expanded=False):
        st.text(result.get("tool_analysis_text", "No tool analysis output."))

    with st.expander("🎯 Target Validation", expanded=False):
        st.text(result.get("target_validation_output", "No target validation output."))

    with st.expander("🧹 Data Quality Agent", expanded=False):
        st.text(result.get("data_quality_output", "No data quality output."))

    with st.expander("📊 KPI Agent", expanded=False):
        st.text(result.get("kpi_output", "No KPI output."))

    with st.expander("⭐ Feature Importance Agent", expanded=False):
        st.text(result.get("feature_importance_output", "No feature importance output."))

    with st.expander("📈 Visualization Agent Summary", expanded=False):
        st.text(result.get("visualization_summary", "No visualization summary."))

    with st.expander("🤖 ML Readiness Agent", expanded=False):
        st.text(result.get("ml_readiness_output", "No ML readiness output."))

    with st.expander("✅ Verifier Agent", expanded=False):
        st.markdown(result.get("verifier_output", "No verifier output."))

    st.subheader("📌 Final Executive Report")
    final_report = result.get("final_report", "No final report generated.")
    st.markdown(final_report)

    # --------------------------------------------------------
    # Visualizations
    # --------------------------------------------------------
    visualizations = result.get("visualizations", [])
    chart_paths = result.get("chart_paths", [])

    if visualizations or chart_paths:
        st.subheader("📉 Generated Visualizations")

        # Preferred: detailed visualization objects
        if visualizations:
            for idx, viz in enumerate(visualizations, start=1):
                st.markdown(f"### {idx}. {viz.get('title', 'Untitled Visualization')}")
                st.write(f"**Chart Type:** {viz.get('chart_type', 'N/A')}")
                st.write(f"**Columns Used:** {viz.get('columns', [])}")

                img_path = viz.get("path")
                if img_path and os.path.exists(img_path):
                    st.image(img_path, use_container_width=True)
                elif idx - 1 < len(chart_paths) and os.path.exists(chart_paths[idx - 1]):
                    st.image(chart_paths[idx - 1], use_container_width=True)

                interpretation = viz.get("interpretation")
                if interpretation:
                    st.info(f"Interpretation: {interpretation}")

        # Fallback: only chart paths available
        elif chart_paths:
            for idx, path in enumerate(chart_paths, start=1):
                if path and os.path.exists(path):
                    st.markdown(f"### Chart {idx}")
                    st.image(path, use_container_width=True)

    # --------------------------------------------------------
    # Downloads
    # --------------------------------------------------------
    st.subheader("⬇️ Download Final Report")

    # Optional local save on frontend runtime
    save_uploaded_report(final_report, "latest_final_report.md")

    st.download_button(
        label="Download Final Report (.md)",
        data=final_report,
        file_name="autoinsight_final_report.md",
        mime="text/markdown",
    )

    st.download_button(
        label="Download Final Report (.txt)",
        data=final_report,
        file_name="autoinsight_final_report.txt",
        mime="text/plain",
    )