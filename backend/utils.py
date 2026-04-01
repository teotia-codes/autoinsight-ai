import os
import re
import uuid
import pandas as pd
import numpy as np
from typing import Dict, Any


# ============================================================
# Shared smart preprocessing (aligned with analysis_tools.py)
# ============================================================
MISSING_TOKENS = {
    "", " ", "na", "n/a", "null", "none", "nan", "missing",
    "-", "--", "---", "_", "?", "not available"
}


def normalize_column_name(col: str) -> str:
    col = str(col)
    col = re.sub(r"\s+", " ", col).strip()
    return col


def is_date_like_column_name(col: str) -> bool:
    col = col.lower()
    date_keywords = ["date", "time", "timestamp", "month", "year", "day"]
    return any(k in col for k in date_keywords)


def clean_string_value(val):
    if pd.isna(val):
        return np.nan

    s = str(val).strip()

    if s.lower() in MISSING_TOKENS:
        return np.nan

    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()

    # Accounting negative format: (1234) -> -1234
    if re.fullmatch(r"\(\s*.*\s*\)", s):
        inner = s[1:-1].strip()
        s = f"-{inner}"

    return s


def try_parse_numeric_like_series(series: pd.Series) -> pd.Series:
    cleaned = series.copy()
    cleaned = cleaned.apply(clean_string_value)

    def parse_one(x):
        if pd.isna(x):
            return np.nan

        s = str(x).strip()

        # Remove commas + currency symbols
        s = s.replace(",", "")
        s = re.sub(r"[$₹€£¥]", "", s)

        # Convert percentages like 45% -> 45
        s = s.replace("%", "")

        s = s.strip()

        if s == "":
            return np.nan

        if not re.search(r"\d", s):
            return np.nan

        try:
            return float(s)
        except Exception:
            return np.nan

    parsed = cleaned.apply(parse_one)

    original_non_null = cleaned.notna().sum()
    parsed_non_null = parsed.notna().sum()

    if original_non_null == 0:
        return series

    success_ratio = parsed_non_null / original_non_null

    if success_ratio >= 0.70:
        return parsed

    return series


def try_parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == "object" and is_date_like_column_name(col):
            try:
                converted = pd.to_datetime(df[col], errors="coerce")
                success_ratio = converted.notna().sum() / max(df[col].notna().sum(), 1)
                if success_ratio >= 0.60:
                    df[col] = converted
            except Exception:
                pass

    return df


def smart_preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Normalize column names
    df.columns = [normalize_column_name(c) for c in df.columns]

    # Clean object cols + try numeric conversion
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(clean_string_value)

            converted = try_parse_numeric_like_series(df[col])
            if pd.api.types.is_numeric_dtype(converted):
                df[col] = converted

    # Try parse date-like columns
    df = try_parse_dates(df)

    return df


def safe_read_csv(file_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="latin1")

    df = smart_preprocess_dataframe(df)
    return df


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