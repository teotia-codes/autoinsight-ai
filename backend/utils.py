import os
import uuid
import pandas as pd
import numpy as np
from typing import Dict, Any

from backend.data.preprocessing import safe_read_csv


# ============================================================
# File Save Helper
# ============================================================
def save_upload_file(file, upload_dir: str) -> str:
    """
    Save uploaded file safely with a unique filename.
    Works with FastAPI UploadFile.
    """
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1]
    base = os.path.splitext(file.filename)[0]
    unique_name = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(upload_dir, unique_name)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    return file_path


# ============================================================
# CSV Summary Text (used by /upload-csv and /dataset-insight)
# ============================================================
def get_csv_summary(file_path: str) -> str:
    df = safe_read_csv(file_path)

    rows, cols = df.shape
    columns = df.columns.tolist()

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()

    missing_values = df.isnull().sum()
    missing_summary = {col: int(val) for col, val in missing_values.items() if val > 0}

    lines = []
    lines.append(f"Dataset contains {rows} rows and {cols} columns.")
    lines.append(f"Columns: {', '.join(map(str, columns))}")
    lines.append(f"Numeric columns: {len(numeric_cols)}")
    lines.append(f"Categorical columns: {len(categorical_cols)}")
    lines.append(f"Datetime columns: {len(datetime_cols)}")

    if missing_summary:
        lines.append("Missing values detected in:")
        for col, cnt in missing_summary.items():
            lines.append(f"- {col}: {cnt}")
    else:
        lines.append("No missing values detected.")

    return "\n".join(lines)


# ============================================================
# Dataset Profile (used by frontend preview)
# ============================================================
def generate_dataset_profile(file_path: str) -> Dict[str, Any]:
    df = safe_read_csv(file_path)

    shape = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1])
    }

    columns = df.columns.astype(str).tolist()

    missing_values = {
        col: int(val)
        for col, val in df.isnull().sum().to_dict().items()
    }

    preview = df.head(5).copy()

    # Convert datetime to string for JSON serialization
    for col in preview.columns:
        if pd.api.types.is_datetime64_any_dtype(preview[col]):
            preview[col] = preview[col].astype(str)

    # Replace NaN with None for JSON-safe preview
    preview = preview.replace({np.nan: None})
    preview_records = preview.to_dict(orient="records")

    numeric_summary = {}
    numeric_df = df.select_dtypes(include=["number"])

    if not numeric_df.empty:
        desc = numeric_df.describe().round(3)

        for col in desc.columns:
            numeric_summary[col] = {
                stat: (
                    None if pd.isna(val) else float(val)
                )
                for stat, val in desc[col].to_dict().items()
            }

    return {
        "filename": os.path.basename(file_path),
        "shape": shape,
        "columns": columns,
        "missing_values": missing_values,
        "preview": preview_records,
        "numeric_summary": numeric_summary,
    }