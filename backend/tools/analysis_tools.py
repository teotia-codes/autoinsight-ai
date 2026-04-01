import re
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder


# ============================================================
# Smart General-Purpose CSV Preprocessing
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

    # Handle weird accounting negative formats like (1234)
    if re.fullmatch(r"\(\s*.*\s*\)", s):
        inner = s[1:-1].strip()
        s = f"-{inner}"

    return s


def try_parse_numeric_like_series(series: pd.Series) -> pd.Series:
    """
    Try to convert object series to numeric if enough values look numeric.
    Handles:
    - commas
    - currency symbols ($, ₹, €, £)
    - percentages (45%)
    - accounting negatives (already normalized as -123)
    """
    cleaned = series.copy()

    # Convert all values to cleaned strings / NaN
    cleaned = cleaned.apply(clean_string_value)

    def parse_one(x):
        if pd.isna(x):
            return np.nan

        s = str(x).strip()

        # Remove currency symbols and commas
        s = s.replace(",", "")
        s = re.sub(r"[$₹€£¥]", "", s)

        # Handle percentages as numeric percentage values (e.g., 45% -> 45)
        s = s.replace("%", "")

        # Remove stray spaces again
        s = s.strip()

        # If empty after cleaning => NaN
        if s == "":
            return np.nan

        # Must contain at least one digit to be numeric-like
        if not re.search(r"\d", s):
            return np.nan

        try:
            return float(s)
        except Exception:
            return np.nan

    parsed = cleaned.apply(parse_one)

    # Convert only if enough non-null values successfully parsed
    original_non_null = cleaned.notna().sum()
    parsed_non_null = parsed.notna().sum()

    if original_non_null == 0:
        return series

    success_ratio = parsed_non_null / original_non_null

    # Only convert if at least 70% of non-null values are numeric-like
    if success_ratio >= 0.70:
        return parsed

    return series


def try_parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        if df[col].dtype == "object" and is_date_like_column_name(col):
            try:
                converted = pd.to_datetime(df[col], errors="coerce")
                # Convert only if enough values parsed
                success_ratio = converted.notna().sum() / max(df[col].notna().sum(), 1)
                if success_ratio >= 0.60:
                    df[col] = converted
            except Exception:
                pass

    return df


def smart_preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Normalize column names
    df.columns = [normalize_column_name(c) for c in df.columns]

    # 2. Clean object values + try numeric conversion
    for col in df.columns:
        if df[col].dtype == "object":
            # First clean strings / missing placeholders
            df[col] = df[col].apply(clean_string_value)

            # Then try numeric conversion if appropriate
            converted = try_parse_numeric_like_series(df[col])

            # Replace only if conversion happened
            if pd.api.types.is_numeric_dtype(converted):
                df[col] = converted

    # 3. Parse date-like columns
    df = try_parse_dates(df)

    return df


# ============================================================
# File Reading
# ============================================================
def safe_read_csv(file_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(file_path)
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="latin1")

    df = smart_preprocess_dataframe(df)
    return df


# ============================================================
# Column Type Helpers
# ============================================================
def classify_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    # Exclude datetime from numeric
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()

    object_cols = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

    constant_cols = []
    binary_cols = []
    continuous_numeric = []
    discrete_numeric = []
    categorical_cols = []
    id_like_cols = []

    for col in df.columns:
        nunique = df[col].nunique(dropna=True)
        col_lower = col.lower()

        # Constant columns
        if nunique <= 1:
            constant_cols.append(col)
            continue

        # ID-like columns
        if (
            "id" in col_lower
            or "record" in col_lower
            or "doctor" in col_lower
            or "physician" in col_lower
            or "name" in col_lower
            or "charge" in col_lower
            or "timestamp" in col_lower
        ):
            id_like_cols.append(col)
            continue

        # Datetime columns
        if col in datetime_cols:
            continue

        # Numeric columns
        if col in numeric_cols:
            if nunique == 2:
                binary_cols.append(col)
            elif nunique <= 10:
                discrete_numeric.append(col)
            else:
                continuous_numeric.append(col)

        # Object / category / bool columns
        elif col in object_cols:
            if nunique == 2:
                binary_cols.append(col)
            else:
                categorical_cols.append(col)

    return {
        "numeric_cols": numeric_cols,
        "object_cols": object_cols,
        "datetime_cols": datetime_cols,
        "constant_cols": constant_cols,
        "binary_cols": binary_cols,
        "continuous_numeric": continuous_numeric,
        "discrete_numeric": discrete_numeric,
        "categorical_cols": categorical_cols,
        "id_like_cols": id_like_cols,
    }


# ============================================================
# Domain Guess
# ============================================================
def guess_domain(columns: List[str]) -> str:
    cols = " ".join([c.lower() for c in columns])

    healthcare_keywords = [
        "glucose", "insulin", "bmi", "blood pressure", "bp", "hba1c",
        "creatinine", "gfr", "egfr", "bun", "acr", "protein", "urine",
        "diagnosis", "disease", "patient", "cholesterol", "symptom"
    ]
    finance_keywords = ["revenue", "sales", "profit", "loss", "customer", "invoice", "order", "discount", "cogs"]
    hr_keywords = ["employee", "salary", "department", "attrition", "performance", "overtime", "job"]
    retail_keywords = ["product", "price", "category", "quantity", "store", "segment", "units sold"]

    if any(k in cols for k in healthcare_keywords):
        return "healthcare"
    if any(k in cols for k in finance_keywords):
        return "finance/sales"
    if any(k in cols for k in hr_keywords):
        return "hr"
    if any(k in cols for k in retail_keywords):
        return "retail/ecommerce"

    return "generic tabular"


# ============================================================
# Better Target Detection
# ============================================================
def detect_target_column(df: pd.DataFrame, column_info: Dict[str, List[str]], domain: str) -> Dict[str, Any]:
    columns = df.columns.tolist()

    preferred_keywords = [
        "diagnosis", "outcome", "target", "label", "class",
        "risk", "stage", "disease", "condition", "status",
        "attrition", "churn", "default", "fraud", "sales", "profit", "revenue"
    ]

    admin_keywords = [
        "id", "record", "doctor", "physician", "name",
        "timestamp", "charge", "hospital", "clinic"
    ]

    constant_cols = set(column_info["constant_cols"])
    id_like_cols = set(column_info["id_like_cols"])
    datetime_cols = set(column_info.get("datetime_cols", []))

    candidates = []

    for col in columns:
        col_lower = col.lower()
        nunique = df[col].nunique(dropna=True)

        # Reject constant
        if col in constant_cols:
            continue

        # Reject admin/id-like
        if col in id_like_cols:
            continue

        # Reject datetime columns as targets by default
        if col in datetime_cols:
            continue

        if any(k in col_lower for k in admin_keywords):
            continue

        score = 0
        reasons = []

        # Strong semantic preference
        for k in preferred_keywords:
            if k in col_lower:
                score += 10
                reasons.append(f"keyword:{k}")

        # Good ML target shape
        if nunique == 2:
            score += 5
            reasons.append("binary")
        elif 2 < nunique <= 10:
            score += 3
            reasons.append("low_cardinality")
        elif nunique > 10 and pd.api.types.is_numeric_dtype(df[col]):
            score += 2
            reasons.append("numeric_regression_candidate")

        # Domain-specific preference
        if domain == "healthcare":
            if "diagnosis" in col_lower or "disease" in col_lower or "outcome" in col_lower:
                score += 8
                reasons.append("healthcare_semantic_boost")

        if domain in ["finance/sales", "retail/ecommerce"]:
            if "profit" in col_lower or "sales" in col_lower or "revenue" in col_lower:
                score += 6
                reasons.append("business_target_boost")

        if domain == "hr":
            if "attrition" in col_lower or "performance" in col_lower:
                score += 6
                reasons.append("hr_target_boost")

        if score > 0:
            candidates.append({
                "column": col,
                "score": score,
                "reasons": reasons,
                "nunique": int(nunique),
                "dtype": str(df[col].dtype),
            })

    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

    if not candidates:
        return {
            "target_column": None,
            "task_type": "unknown",
            "confidence": "low",
            "candidates": [],
            "note": "No reliable target detected."
        }

    best = candidates[0]
    best_col = best["column"]
    nunique = best["nunique"]

    if nunique == 2 or nunique <= 10:
        task_type = "classification"
    elif pd.api.types.is_numeric_dtype(df[best_col]):
        task_type = "regression"
    else:
        task_type = "classification"

    confidence = "high" if best["score"] >= 15 else "medium" if best["score"] >= 8 else "low"

    return {
        "target_column": best_col,
        "task_type": task_type,
        "confidence": confidence,
        "candidates": candidates[:5],
        "note": "Selected based on semantic relevance + cardinality + domain-aware rules."
    }


# ============================================================
# Missing Value Analysis
# ============================================================
def get_high_missing_columns(df: pd.DataFrame, threshold: float = 20.0) -> Dict[str, float]:
    missing_pct = (df.isnull().mean() * 100).round(2)
    high_missing = missing_pct[missing_pct > threshold]
    return {k: float(v) for k, v in high_missing.to_dict().items()}


# ============================================================
# Outlier Detection (ONLY continuous numeric)
# ============================================================
def detect_outliers_iqr(df: pd.DataFrame, continuous_numeric_cols: List[str]) -> Dict[str, int]:
    outlier_counts = {}

    for col in continuous_numeric_cols:
        series = df[col].dropna()
        if series.empty:
            outlier_counts[col] = 0
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            outlier_counts[col] = 0
            continue

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        count = ((series < lower) | (series > upper)).sum()
        outlier_counts[col] = int(count)

    return outlier_counts


# ============================================================
# Correlation Strength Helpers
# ============================================================
def interpret_correlation_strength(r: float) -> str:
    a = abs(r)
    if a < 0.10:
        return "negligible"
    elif a < 0.30:
        return "weak"
    elif a < 0.50:
        return "moderate"
    elif a < 0.70:
        return "strong"
    else:
        return "very strong"


def get_top_correlations(df: pd.DataFrame, top_n: int = 5) -> List[Dict[str, Any]]:
    numeric_df = df.select_dtypes(include=["number"])
    if numeric_df.shape[1] < 2:
        return []

    corr_matrix = numeric_df.corr()
    pairs = []

    cols = corr_matrix.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            c1 = cols[i]
            c2 = cols[j]
            corr_val = corr_matrix.loc[c1, c2]

            if pd.isna(corr_val):
                continue

            pairs.append({
                "col1": c1,
                "col2": c2,
                "correlation": round(float(corr_val), 4),
                "strength": interpret_correlation_strength(float(corr_val)),
            })

    pairs = sorted(pairs, key=lambda x: abs(x["correlation"]), reverse=True)
    return pairs[:top_n]


# ============================================================
# Feature Importance Engine
# ============================================================
def compute_feature_importance(df: pd.DataFrame, target_info: Dict[str, Any]) -> Dict[str, Any]:
    target_col = target_info.get("target_column")
    task_type = target_info.get("task_type", "unknown")

    if not target_col or target_col not in df.columns:
        return {
            "available": False,
            "reason": "No valid target column detected.",
            "target_column": None,
            "task_type": "unknown",
            "top_features": []
        }

    work_df = df.copy()

    # Drop constant columns
    drop_cols = []
    for col in work_df.columns:
        if work_df[col].nunique(dropna=True) <= 1:
            drop_cols.append(col)

    if drop_cols:
        work_df = work_df.drop(columns=drop_cols, errors="ignore")

    if target_col not in work_df.columns:
        return {
            "available": False,
            "reason": "Target removed because it became invalid after preprocessing.",
            "target_column": None,
            "task_type": "unknown",
            "top_features": []
        }

    # Convert datetime columns to ordinal numbers for modeling
    for col in work_df.columns:
        if pd.api.types.is_datetime64_any_dtype(work_df[col]):
            work_df[col] = work_df[col].map(lambda x: x.toordinal() if pd.notna(x) else np.nan)

    # Build X, y
    y = work_df[target_col]
    X = work_df.drop(columns=[target_col])

    if X.shape[1] == 0:
        return {
            "available": False,
            "reason": "No features left after excluding target.",
            "target_column": target_col,
            "task_type": task_type,
            "top_features": []
        }

    # Encode categoricals
    for col in X.columns:
        if pd.api.types.is_numeric_dtype(X[col]):
            if X[col].isna().all():
                X[col] = 0
            else:
                X[col] = X[col].fillna(X[col].median())
        else:
            X[col] = X[col].astype(str).fillna("MISSING")
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col])

    # Encode y if needed
    if task_type == "classification":
        y = y.astype(str).fillna("MISSING")
        y_le = LabelEncoder()
        y = y_le.fit_transform(y)

        model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )
    elif task_type == "regression":
        if not pd.api.types.is_numeric_dtype(y):
            return {
                "available": False,
                "reason": "Regression target is non-numeric.",
                "target_column": target_col,
                "task_type": task_type,
                "top_features": []
            }

        if y.isna().all():
            return {
                "available": False,
                "reason": "Regression target contains only missing values.",
                "target_column": target_col,
                "task_type": task_type,
                "top_features": []
            }

        y = y.fillna(y.median())

        model = RandomForestRegressor(
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )
    else:
        return {
            "available": False,
            "reason": "Unknown task type.",
            "target_column": target_col,
            "task_type": task_type,
            "top_features": []
        }

    try:
        model.fit(X, y)
        importances = model.feature_importances_

        feat_df = pd.DataFrame({
            "feature": X.columns,
            "importance": importances
        }).sort_values("importance", ascending=False)

        top_features = []
        for _, row in feat_df.head(10).iterrows():
            top_features.append({
                "feature": str(row["feature"]),
                "importance": round(float(row["importance"]), 4)
            })

        return {
            "available": True,
            "reason": "Feature importance computed successfully.",
            "target_column": target_col,
            "task_type": task_type,
            "top_features": top_features
        }

    except Exception as e:
        return {
            "available": False,
            "reason": f"Feature importance failed: {str(e)}",
            "target_column": target_col,
            "task_type": task_type,
            "top_features": []
        }


# ============================================================
# Clinical Rules Engine (Optional healthcare support)
# ============================================================
def evaluate_healthcare_rules(df: pd.DataFrame) -> Dict[str, Any]:
    findings = []
    risk_signals = []

    col_map = {c.lower(): c for c in df.columns}

    def get_col_contains(keyword_list):
        for k in keyword_list:
            for col_lower, original in col_map.items():
                if k in col_lower:
                    return original
        return None

    # Creatinine
    creat_col = get_col_contains(["creatinine"])
    if creat_col and pd.api.types.is_numeric_dtype(df[creat_col]):
        mean_val = df[creat_col].dropna().mean()
        findings.append(f"Average {creat_col}: {round(float(mean_val), 3)}")
        if mean_val > 1.2:
            risk_signals.append(f"Elevated average {creat_col} may indicate renal stress or kidney dysfunction risk.")

    # GFR / eGFR
    gfr_col = get_col_contains(["gfr", "egfr"])
    if gfr_col and pd.api.types.is_numeric_dtype(df[gfr_col]):
        mean_val = df[gfr_col].dropna().mean()
        findings.append(f"Average {gfr_col}: {round(float(mean_val), 3)}")
        if mean_val < 90:
            risk_signals.append(f"Reduced average {gfr_col} may indicate impaired kidney filtration.")

    # HbA1c
    hba1c_col = get_col_contains(["hba1c"])
    if hba1c_col and pd.api.types.is_numeric_dtype(df[hba1c_col]):
        mean_val = df[hba1c_col].dropna().mean()
        findings.append(f"Average {hba1c_col}: {round(float(mean_val), 3)}")
        if mean_val >= 5.7:
            risk_signals.append(f"Elevated average {hba1c_col} suggests glycemic dysregulation and possible diabetes-related risk.")

    return {
        "findings": findings,
        "risk_signals": risk_signals,
        "caution": "Clinical rules are supportive analytical heuristics only and must not be interpreted as diagnosis."
    }


# ============================================================
# Main Real Analysis
# ============================================================
def run_real_data_analysis(file_path: str) -> Dict[str, Any]:
    df = safe_read_csv(file_path)

    column_info = classify_columns(df)
    domain = guess_domain(df.columns.tolist())
    target_analysis = detect_target_column(df, column_info, domain)
    high_missing_columns = get_high_missing_columns(df, threshold=20.0)
    outlier_counts = detect_outliers_iqr(df, column_info["continuous_numeric"])
    top_correlations = get_top_correlations(df, top_n=8)
    feature_importance = compute_feature_importance(df, target_analysis)

    clinical_rules = {}
    if domain == "healthcare":
        clinical_rules = evaluate_healthcare_rules(df)

    return {
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": df.columns.astype(str).tolist(),
        "domain_guess": domain,
        "duplicate_rows": int(df.duplicated().sum()),

        "column_types": column_info,

        "high_missing_columns": high_missing_columns,
        "outlier_counts": outlier_counts,
        "top_correlations": top_correlations,

        "target_analysis": target_analysis,
        "feature_importance": feature_importance,
        "clinical_rules": clinical_rules,
    }


# ============================================================
# Tool Analysis Text
# ============================================================
def build_tool_analysis_text(analysis: Dict[str, Any]) -> str:
    lines = []
    lines.append("AUTONOMOUS TOOL-BASED ANALYSIS REPORT")
    lines.append("=" * 60)

    shape = analysis.get("shape", {})
    lines.append(f"Rows: {shape.get('rows', 0)}")
    lines.append(f"Columns: {shape.get('columns', 0)}")
    lines.append(f"Domain Guess: {analysis.get('domain_guess', 'unknown')}")
    lines.append(f"Duplicate Rows: {analysis.get('duplicate_rows', 0)}")
    lines.append("")

    # Column typing
    col_types = analysis.get("column_types", {})
    lines.append("COLUMN TYPE SUMMARY")
    lines.append(f"- Continuous Numeric: {len(col_types.get('continuous_numeric', []))}")
    lines.append(f"- Discrete Numeric: {len(col_types.get('discrete_numeric', []))}")
    lines.append(f"- Binary: {len(col_types.get('binary_cols', []))}")
    lines.append(f"- Categorical: {len(col_types.get('categorical_cols', []))}")
    lines.append(f"- Datetime: {len(col_types.get('datetime_cols', []))}")
    lines.append(f"- Constant: {len(col_types.get('constant_cols', []))}")
    lines.append(f"- ID-like / Admin: {len(col_types.get('id_like_cols', []))}")
    lines.append("")

    # Missing
    lines.append("HIGH MISSING COLUMNS (>20%)")
    high_missing = analysis.get("high_missing_columns", {})
    if high_missing:
        for col, pct in high_missing.items():
            lines.append(f"- {col}: {pct}% missing")
    else:
        lines.append("- No columns above threshold")
    lines.append("")

    # Outliers
    lines.append("OUTLIER COUNTS (continuous numeric only)")
    outliers = analysis.get("outlier_counts", {})
    if outliers:
        sorted_outliers = sorted(outliers.items(), key=lambda x: x[1], reverse=True)
        for col, count in sorted_outliers[:10]:
            lines.append(f"- {col}: {count}")
    else:
        lines.append("- No valid continuous numeric columns for outlier detection")
    lines.append("")

    # Correlations
    lines.append("TOP CORRELATIONS")
    corrs = analysis.get("top_correlations", [])
    if corrs:
        for item in corrs:
            lines.append(
                f"- {item['col1']} ↔ {item['col2']}: {item['correlation']} "
                f"({item['strength']})"
            )
    else:
        lines.append("- No sufficient numeric columns for correlation analysis")
    lines.append("")

    # Target
    lines.append("TARGET DETECTION")
    target = analysis.get("target_analysis", {})
    lines.append(f"- Target Column: {target.get('target_column', None)}")
    lines.append(f"- Task Type: {target.get('task_type', 'unknown')}")
    lines.append(f"- Confidence: {target.get('confidence', 'low')}")
    lines.append(f"- Note: {target.get('note', '')}")

    candidates = target.get("candidates", [])
    if candidates:
        lines.append("- Top Candidates:")
        for c in candidates[:5]:
            lines.append(f"  • {c['column']} (score={c['score']}, reasons={', '.join(c['reasons'])})")
    lines.append("")

    # Feature importance
    fi = analysis.get("feature_importance", {})
    lines.append("FEATURE IMPORTANCE")
    if fi.get("available"):
        lines.append(f"- Target Used: {fi.get('target_column')}")
        lines.append(f"- Task Type: {fi.get('task_type')}")
        lines.append("- Top Predictors:")
        for feat in fi.get("top_features", []):
            lines.append(f"  • {feat['feature']}: {feat['importance']}")
    else:
        lines.append(f"- Not available: {fi.get('reason', 'Unknown reason')}")
    lines.append("")

    # Optional healthcare rules
    clinical = analysis.get("clinical_rules", {})
    if clinical:
        lines.append("OPTIONAL HEALTHCARE RULES")
        findings = clinical.get("findings", [])
        risks = clinical.get("risk_signals", [])

        if findings:
            lines.append("- Findings:")
            for f in findings:
                lines.append(f"  • {f}")

        if risks:
            lines.append("- Risk Signals:")
            for r in risks:
                lines.append(f"  • {r}")

        lines.append(f"- Caution: {clinical.get('caution', '')}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# Data Quality Report
# ============================================================
def build_data_quality_report(analysis: Dict[str, Any]) -> Dict[str, Any]:
    shape = analysis.get("shape", {})
    rows = shape.get("rows", 0)
    cols = shape.get("columns", 0)

    high_missing = analysis.get("high_missing_columns", {})
    duplicate_rows = analysis.get("duplicate_rows", 0)
    outlier_counts = analysis.get("outlier_counts", {})
    constant_cols = analysis.get("column_types", {}).get("constant_cols", [])

    critical_issues = []
    moderate_issues = []
    recommendations = []

    severe_missing = {k: v for k, v in high_missing.items() if v >= 40}
    moderate_missing = {k: v for k, v in high_missing.items() if 20 <= v < 40}

    if severe_missing:
        critical_issues.append(f"{len(severe_missing)} columns have severe missingness (>=40%).")
        recommendations.append("Consider dropping or heavily imputing severely incomplete columns.")

    if moderate_missing:
        moderate_issues.append(f"{len(moderate_missing)} columns have moderate missingness (20-40%).")
        recommendations.append("Apply domain-aware imputation for moderately missing columns.")

    if duplicate_rows > 0:
        moderate_issues.append(f"{duplicate_rows} duplicate rows detected.")
        recommendations.append("Review and remove duplicate rows if they are accidental duplicates.")

    if constant_cols:
        moderate_issues.append(f"{len(constant_cols)} constant columns detected.")
        recommendations.append("Drop constant columns because they do not add analytical or ML value.")

    high_outlier_cols = [k for k, v in outlier_counts.items() if v > 0]
    if high_outlier_cols:
        moderate_issues.append(f"{len(high_outlier_cols)} continuous numeric columns contain potential outliers.")
        recommendations.append("Validate whether outliers are true extreme cases or data quality issues.")

    quality_score = 100
    quality_score -= min(len(severe_missing) * 8, 25)
    quality_score -= min(len(moderate_missing) * 4, 15)
    quality_score -= min(duplicate_rows // 5, 10)
    quality_score -= min(len(constant_cols) * 3, 10)
    quality_score -= min(len(high_outlier_cols) * 2, 10)

    quality_score = max(0, min(100, quality_score))

    return {
        "quality_score": int(quality_score),
        "rows": int(rows),
        "columns": int(cols),
        "critical_issues": critical_issues,
        "moderate_issues": moderate_issues,
        "recommendations": recommendations,
    }


def build_data_quality_text(dq: Dict[str, Any]) -> str:
    lines = []
    lines.append("DATA QUALITY AGENT REPORT")
    lines.append("=" * 50)
    lines.append(f"Quality Score: {dq.get('quality_score', 0)}/100")
    lines.append(f"Rows: {dq.get('rows', 0)}")
    lines.append(f"Columns: {dq.get('columns', 0)}")
    lines.append("")

    if dq.get("critical_issues"):
        lines.append("Critical Issues:")
        for issue in dq["critical_issues"]:
            lines.append(f"- {issue}")

    if dq.get("moderate_issues"):
        lines.append("Moderate Issues:")
        for issue in dq["moderate_issues"]:
            lines.append(f"- {issue}")

    if dq.get("recommendations"):
        lines.append("Recommendations:")
        for rec in dq["recommendations"]:
            lines.append(f"- {rec}")

    return "\n".join(lines)


# ============================================================
# KPI Report
# ============================================================
def build_kpi_report(file_path: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    df = safe_read_csv(file_path)
    domain = analysis.get("domain_guess", "generic tabular")

    metrics = {}

    if domain == "healthcare":
        for col in df.columns:
            col_lower = col.lower()

            if "creatinine" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics["avg_creatinine"] = round(float(df[col].dropna().mean()), 3)

            elif ("gfr" in col_lower or "egfr" in col_lower) and pd.api.types.is_numeric_dtype(df[col]):
                metrics["avg_gfr"] = round(float(df[col].dropna().mean()), 3)

            elif "hba1c" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics["avg_hba1c"] = round(float(df[col].dropna().mean()), 3)

            elif ("blood pressure" in col_lower or col_lower == "bp" or "systolic" in col_lower) and pd.api.types.is_numeric_dtype(df[col]):
                metrics["avg_blood_pressure"] = round(float(df[col].dropna().mean()), 3)

            elif ("diagnosis" in col_lower or "outcome" in col_lower or "disease" in col_lower):
                metrics["class_distribution"] = df[col].astype(str).value_counts().to_dict()

    elif domain in ["finance/sales", "retail/ecommerce"]:
        for col in df.columns:
            col_lower = col.lower()

            if "sales" == col_lower or "sales" in col_lower:
                if pd.api.types.is_numeric_dtype(df[col]):
                    metrics[f"total_{col.lower().replace(' ', '_')}"] = round(float(df[col].sum()), 2)

            elif "profit" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics[f"total_{col.lower().replace(' ', '_')}"] = round(float(df[col].sum()), 2)
                metrics[f"avg_{col.lower().replace(' ', '_')}"] = round(float(df[col].mean()), 2)

            elif "units sold" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics["total_units_sold"] = round(float(df[col].sum()), 2)

    elif domain == "hr":
        for col in df.columns:
            col_lower = col.lower()

            if "attrition" in col_lower:
                metrics["attrition_distribution"] = df[col].astype(str).value_counts().to_dict()

            elif "salary" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics["avg_salary"] = round(float(df[col].mean()), 2)

    else:
        metrics["row_count"] = int(df.shape[0])
        metrics["column_count"] = int(df.shape[1])

    return {
        "domain": domain,
        "metrics": metrics
    }


def build_kpi_text(kpi: Dict[str, Any]) -> str:
    lines = []
    lines.append("KPI AGENT REPORT")
    lines.append("=" * 50)
    lines.append(f"Detected Domain: {kpi.get('domain', 'unknown')}")
    lines.append("")

    metrics = kpi.get("metrics", {})
    if metrics:
        lines.append("Key Metrics:")
        for k, v in metrics.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("No KPI metrics available.")

    return "\n".join(lines)


# ============================================================
# ML Readiness Report
# ============================================================
def build_ml_readiness_report(analysis: Dict[str, Any]) -> Dict[str, Any]:
    target = analysis.get("target_analysis", {})
    target_col = target.get("target_column")
    task_type = target.get("task_type", "unknown")
    confidence = target.get("confidence", "low")

    high_missing = analysis.get("high_missing_columns", {})
    constant_cols = analysis.get("column_types", {}).get("constant_cols", [])
    fi = analysis.get("feature_importance", {})

    is_ml_ready = True
    preprocessing_recommendations = []
    leakage_risk = []

    if not target_col:
        is_ml_ready = False
        preprocessing_recommendations.append("No reliable target detected. Define a valid label/target column.")

    if confidence == "low":
        preprocessing_recommendations.append("Target detection confidence is low; manually validate the target column.")

    if len(high_missing) > 3:
        preprocessing_recommendations.append("Multiple high-missing columns detected; apply imputation or feature pruning.")

    if constant_cols:
        preprocessing_recommendations.append("Drop constant columns before model training.")

    if not fi.get("available", False):
        preprocessing_recommendations.append("Feature importance unavailable; validate target and preprocessing pipeline.")

    class_imbalance_flag = False

    baseline_models = []
    if task_type == "classification":
        baseline_models = ["Logistic Regression", "Random Forest Classifier", "XGBoost (optional later)"]
    elif task_type == "regression":
        baseline_models = ["Linear Regression", "Random Forest Regressor", "XGBoost Regressor (optional later)"]

    return {
        "target_detected": bool(target_col),
        "target_column": target_col,
        "task_type": task_type,
        "confidence": confidence,
        "is_ml_ready": is_ml_ready,
        "class_imbalance_flag": class_imbalance_flag,
        "leakage_risk": leakage_risk,
        "preprocessing_recommendations": preprocessing_recommendations,
        "baseline_model_suggestions": baseline_models,
    }


def build_ml_readiness_text(mlr: Dict[str, Any]) -> str:
    lines = []
    lines.append("ML READINESS AGENT REPORT")
    lines.append("=" * 50)
    lines.append(f"Target Detected: {mlr.get('target_detected', False)}")
    lines.append(f"Target Column: {mlr.get('target_column', None)}")
    lines.append(f"Task Type: {mlr.get('task_type', 'unknown')}")
    lines.append(f"Target Confidence: {mlr.get('confidence', 'low')}")
    lines.append(f"ML Ready: {mlr.get('is_ml_ready', False)}")
    lines.append(f"Class Imbalance Flag: {mlr.get('class_imbalance_flag', False)}")
    lines.append("")

    if mlr.get("leakage_risk"):
        lines.append("Leakage Risks:")
        for risk in mlr["leakage_risk"]:
            lines.append(f"- {risk}")

    if mlr.get("preprocessing_recommendations"):
        lines.append("Preprocessing Recommendations:")
        for rec in mlr["preprocessing_recommendations"]:
            lines.append(f"- {rec}")

    if mlr.get("baseline_model_suggestions"):
        lines.append("Suggested Baseline Models:")
        for model in mlr["baseline_model_suggestions"]:
            lines.append(f"- {model}")

    return "\n".join(lines)