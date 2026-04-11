"""
backend/data/preprocessing.py

Single source of truth for CSV loading and smart preprocessing.
Import from here — do NOT duplicate this logic elsewhere.
"""

import re
import pandas as pd
import numpy as np


# ============================================================
# Missing-value sentinel tokens
# ============================================================
MISSING_TOKENS = {
    "", " ", "na", "n/a", "null", "none", "nan", "missing",
    "-", "--", "---", "_", "?", "not available"
}


# ============================================================
# Column-name helpers
# ============================================================
def normalize_column_name(col: str) -> str:
    col = str(col)
    col = re.sub(r"\s+", " ", col).strip()
    return col


def is_date_like_column_name(col: str) -> bool:
    col = col.lower()
    date_keywords = ["date", "time", "timestamp", "month", "year", "day"]
    return any(k in col for k in date_keywords)


# ============================================================
# Cell-level cleaning
# ============================================================
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


# ============================================================
# Series-level numeric coercion
# ============================================================
def try_parse_numeric_like_series(series: pd.Series) -> pd.Series:
    """
    Try to convert an object Series to numeric if >= 70% of values parse.
    Handles: commas, currency symbols ($, ₹, €, £, ¥), percentages, accounting negatives.
    """
    cleaned = series.copy()
    cleaned = cleaned.apply(clean_string_value)

    def parse_one(x):
        if pd.isna(x):
            return np.nan

        s = str(x).strip()
        s = s.replace(",", "")
        s = re.sub(r"[$₹€£¥]", "", s)
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


# ============================================================
# DataFrame-level date parsing
# ============================================================
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


# ============================================================
# Full DataFrame preprocessing pipeline
# ============================================================
def smart_preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Normalize column names
    df.columns = [normalize_column_name(c) for c in df.columns]

    # 2. Clean object values + try numeric conversion
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].apply(clean_string_value)

            converted = try_parse_numeric_like_series(df[col])
            if pd.api.types.is_numeric_dtype(converted):
                df[col] = converted

    # 3. Parse date-like columns
    df = try_parse_dates(df)

    return df


# ============================================================
# CSV reader (encoding-safe + preprocessed)
# ============================================================
def safe_read_csv(file_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="latin1")

    df = smart_preprocess_dataframe(df)
    return df