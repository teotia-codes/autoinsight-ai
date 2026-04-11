import re
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

from backend.data.preprocessing import (
    MISSING_TOKENS,
    normalize_column_name,
    is_date_like_column_name,
    clean_string_value,
    try_parse_numeric_like_series,
    try_parse_dates,
    smart_preprocess_dataframe,
    safe_read_csv,
)


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
    finance_keywords = [
        "revenue", "sales", "profit", "loss", "customer", "invoice",
        "order", "discount", "cogs"
    ]
    hr_keywords = [
        "employee", "salary", "department", "attrition",
        "performance", "overtime", "job"
    ]
    retail_keywords = [
        "product", "price", "category", "quantity",
        "store", "segment", "units sold"
    ]

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
# Column Type Helpers (FIXED)
# ============================================================
def classify_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()
    object_cols = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

    constant_cols = []
    binary_cols = []
    continuous_numeric = []
    discrete_numeric = []
    categorical_cols = []
    id_like_cols = []

    rows = max(len(df), 1)

    def is_id_like(col_name: str, series: pd.Series) -> bool:
        col_lower = col_name.lower().strip()
        nunique = series.nunique(dropna=True)
        unique_ratio = nunique / rows

        # Strong semantic ID / code-like indicators (GENERAL, not dataset-specific)
        id_keywords = [
            "id", "empid", "employeeid", "employeenumber",
            "customerid", "orderid", "transactionid", "invoiceid",
            "recordid", "uuid", "serial",
            "postal", "postalcode", "zip", "zipcode", "pin", "pincode",
            "code"
        ]

        if any(k == col_lower or k in col_lower for k in id_keywords):
            if not any(k in col_lower for k in [
                "sales", "profit", "revenue", "income", "price", "amount",
                "score", "target", "label", "class", "outcome", "diagnosis", "attrition"
            ]):
                return True

        # Very high-cardinality columns are often IDs
        if unique_ratio > 0.95 and nunique > 20:
            if not any(k in col_lower for k in [
                "sales", "profit", "revenue", "income", "price", "amount",
                "score", "target", "label", "class", "outcome", "diagnosis", "attrition"
            ]):
                return True

        return False

    for col in df.columns:
        nunique = df[col].nunique(dropna=True)

        if nunique <= 1:
            constant_cols.append(col)
            continue

        if col in datetime_cols:
            continue

        if is_id_like(col, df[col]):
            id_like_cols.append(col)
            continue

        if col in numeric_cols:
            if nunique == 2:
                binary_cols.append(col)
            elif nunique <= 10:
                discrete_numeric.append(col)
            else:
                continuous_numeric.append(col)

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
# Better Target Detection (AMBIGUITY FIXED)
# ============================================================
def detect_target_column(df: pd.DataFrame, column_info: Dict[str, List[str]], domain: str) -> Dict[str, Any]:
    columns = df.columns.tolist()

    preferred_keywords = [
        "diagnosis", "outcome", "target", "label", "class",
        "risk", "stage", "disease", "condition", "status",
        "attrition", "churn", "default", "fraud",
        "sales", "profit", "revenue", "demand", "forecast", "quantity"
    ]

    admin_keywords = [
        "record", "doctor", "physician", "timestamp",
        "charge", "hospital", "clinic"
    ]

    constant_cols = set(column_info["constant_cols"])
    id_like_cols = set(column_info["id_like_cols"])
    datetime_cols = set(column_info.get("datetime_cols", []))

    candidates = []
    rows = max(len(df), 1)

    for col in columns:
        col_lower = col.lower()
        nunique = df[col].nunique(dropna=True)
        unique_ratio = nunique / rows

        if col in constant_cols:
            continue

        if col in id_like_cols:
            continue

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
            score += 4
            reasons.append("numeric_regression_candidate")

        # Penalize almost unique columns
        if unique_ratio > 0.95:
            score -= 8
            reasons.append("high_uniqueness_penalty")

        # Domain-specific boost
        if domain == "healthcare":
            if any(k in col_lower for k in ["diagnosis", "disease", "outcome", "risk"]):
                score += 8
                reasons.append("healthcare_semantic_boost")

        if domain in ["finance/sales", "retail/ecommerce"]:
            if any(k in col_lower for k in ["profit", "sales", "revenue", "demand", "quantity"]):
                score += 6
                reasons.append("business_target_boost")

        if domain == "hr":
            if any(k in col_lower for k in ["attrition", "performance", "salary", "income"]):
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
            "ambiguous": False,
            "alternate_targets": [],
            "note": "No reliable target detected."
        }

    best = candidates[0]
    best_col = best["column"]
    best_score = best["score"]
    nunique = best["nunique"]

    # Ambiguity detection
    ambiguous = False
    alternate_targets = []
    if len(candidates) > 1:
        second = candidates[1]
        if abs(best_score - second["score"]) <= 2:
            ambiguous = True
            alternate_targets.append(second["column"])

    if nunique == 2 or nunique <= 10:
        task_type = "classification"
    elif pd.api.types.is_numeric_dtype(df[best_col]):
        task_type = "regression"
    else:
        task_type = "classification"

    if best_score >= 15 and not ambiguous:
        confidence = "high"
    elif best_score >= 8:
        confidence = "medium"
    else:
        confidence = "low"

    note = "Selected based on semantic relevance + cardinality + domain-aware rules."
    if ambiguous:
        note += " Multiple plausible targets detected; manual confirmation recommended."

    return {
        "target_column": best_col,
        "task_type": task_type,
        "confidence": confidence,
        "candidates": candidates[:5],
        "ambiguous": ambiguous,
        "alternate_targets": alternate_targets,
        "note": note
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
        if len(series) < 5:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        count = ((series < lower) | (series > upper)).sum()
        if count > 0:
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


def get_top_correlations(df: pd.DataFrame, column_info: Dict[str, List[str]], top_n: int = 8) -> List[Dict[str, Any]]:
    id_like_cols = set(column_info.get("id_like_cols", []))
    constant_cols = set(column_info.get("constant_cols", []))

    numeric_cols = [
        c for c in df.select_dtypes(include=["number"]).columns.tolist()
        if c not in id_like_cols and c not in constant_cols
    ]

    if len(numeric_cols) < 2:
        return []

    numeric_df = df[numeric_cols]
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
# Signal Ranking Engine (RENAMED from Feature Importance)
# ============================================================
def compute_signal_ranking(df: pd.DataFrame, target_info: Dict[str, Any], column_info: Dict[str, List[str]]) -> Dict[str, Any]:
    target_col = target_info.get("target_column")
    task_type = target_info.get("task_type", "unknown")

    if not target_col or target_col not in df.columns:
        return {
            "available": False,
            "reason": "No valid target column detected.",
            "target_column": None,
            "task_type": "unknown",
            "top_signals": []
        }

    work_df = df.copy()

    # Drop constants + ID-like
    drop_cols = set(column_info.get("constant_cols", []) + column_info.get("id_like_cols", []))
    drop_cols.discard(target_col)

    if drop_cols:
        work_df = work_df.drop(columns=list(drop_cols), errors="ignore")

    if target_col not in work_df.columns:
        return {
            "available": False,
            "reason": "Target removed because it became invalid after preprocessing.",
            "target_column": None,
            "task_type": "unknown",
            "top_signals": []
        }

    # Convert datetime columns to ordinal numbers
    for col in work_df.columns:
        if pd.api.types.is_datetime64_any_dtype(work_df[col]):
            work_df[col] = work_df[col].map(lambda x: x.toordinal() if pd.notna(x) else np.nan)

    y = work_df[target_col]
    X = work_df.drop(columns=[target_col])

    if X.shape[1] == 0:
        return {
            "available": False,
            "reason": "No features left after excluding target.",
            "target_column": target_col,
            "task_type": task_type,
            "top_signals": []
        }

    # Encode X
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

    # Encode y
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
                "top_signals": []
            }

        if y.isna().all():
            return {
                "available": False,
                "reason": "Regression target contains only missing values.",
                "target_column": target_col,
                "task_type": task_type,
                "top_signals": []
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
            "top_signals": []
        }

    try:
        model.fit(X, y)
        importances = model.feature_importances_

        feat_df = pd.DataFrame({
            "feature": X.columns,
            "importance": importances
        }).sort_values("importance", ascending=False)

        top_signals = []
        for _, row in feat_df.head(10).iterrows():
            top_signals.append({
                "feature": str(row["feature"]),
                "importance": round(float(row["importance"]), 4)
            })

        return {
            "available": True,
            "reason": "Model-based signal ranking computed successfully.",
            "target_column": target_col,
            "task_type": task_type,
            "method": "random_forest_feature_importance",
            "top_signals": top_signals
        }

    except Exception as e:
        return {
            "available": False,
            "reason": f"Signal ranking failed: {str(e)}",
            "target_column": target_col,
            "task_type": task_type,
            "top_signals": []
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
    top_correlations = get_top_correlations(df, column_info, top_n=8)
    signal_ranking = compute_signal_ranking(df, target_analysis, column_info)

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
        "signal_ranking": signal_ranking,
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
    lines.append(f"- Ambiguous: {target.get('ambiguous', False)}")
    alt_targets = target.get("alternate_targets", [])
    if alt_targets:
        lines.append(f"- Alternate Targets: {alt_targets}")
    lines.append(f"- Note: {target.get('note', '')}")

    candidates = target.get("candidates", [])
    if candidates:
        lines.append("- Top Candidates:")
        for c in candidates[:5]:
            lines.append(f"  • {c['column']} (score={c['score']}, reasons={', '.join(c['reasons'])})")
    lines.append("")

    # Signal ranking
    sr = analysis.get("signal_ranking", {})
    lines.append("SIGNAL RANKING")
    if sr.get("available"):
        lines.append(f"- Target Used: {sr.get('target_column')}")
        lines.append(f"- Task Type: {sr.get('task_type')}")
        lines.append(f"- Method: {sr.get('method', 'unknown')}")
        lines.append("- Top Signals:")
        for feat in sr.get("top_signals", []):
            lines.append(f"  • {feat['feature']}: {feat['importance']}")
    else:
        lines.append(f"- Not available: {sr.get('reason', 'Unknown reason')}")
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

    def add_generic_numeric_kpis():
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        column_info = analysis.get("column_types", {})
        id_like_cols = set(column_info.get("id_like_cols", []))
        constant_cols = set(column_info.get("constant_cols", []))

        usable_numeric = [
            c for c in numeric_cols
            if c not in id_like_cols and c not in constant_cols
        ]

        for col in usable_numeric[:3]:
            metrics[f"avg_{col.lower().replace(' ', '_')}"] = round(float(df[col].dropna().mean()), 2)

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

        if not metrics:
            add_generic_numeric_kpis()

    elif domain in ["finance/sales", "retail/ecommerce"]:
        total_sales = None
        total_profit = None

        for col in df.columns:
            col_lower = col.lower()

            if "sales" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                total_sales = float(df[col].sum())
                metrics[f"total_{col.lower().replace(' ', '_')}"] = round(total_sales, 2)
                metrics[f"avg_{col.lower().replace(' ', '_')}"] = round(float(df[col].mean()), 2)

            elif "profit" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                total_profit = float(df[col].sum())
                metrics[f"total_{col.lower().replace(' ', '_')}"] = round(total_profit, 2)
                metrics[f"avg_{col.lower().replace(' ', '_')}"] = round(float(df[col].mean()), 2)

            elif "revenue" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics[f"total_{col.lower().replace(' ', '_')}"] = round(float(df[col].sum()), 2)

            elif "units sold" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics["total_units_sold"] = round(float(df[col].sum()), 2)

        if total_sales and total_profit:
            metrics["avg_profit_margin_pct"] = round((total_profit / total_sales) * 100, 2)

        if not metrics:
            add_generic_numeric_kpis()

    elif domain == "hr":
        for col in df.columns:
            col_lower = col.lower()

            if "attrition" in col_lower:
                metrics["attrition_distribution"] = df[col].astype(str).value_counts().to_dict()

            elif ("monthlyincome" in col_lower or "income" in col_lower or "salary" in col_lower) and pd.api.types.is_numeric_dtype(df[col]):
                metrics[f"avg_{col.lower().replace(' ', '_')}"] = round(float(df[col].mean()), 2)

            elif "hourlyrate" in col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics["avg_hourly_rate"] = round(float(df[col].mean()), 2)

            elif "age" == col_lower and pd.api.types.is_numeric_dtype(df[col]):
                metrics["avg_age"] = round(float(df[col].mean()), 2)

        if not metrics:
            add_generic_numeric_kpis()

    else:
        metrics["row_count"] = int(df.shape[0])
        metrics["column_count"] = int(df.shape[1])
        add_generic_numeric_kpis()

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
# ML Readiness Report (UPDATED for ambiguity + signal ranking)
# ============================================================
def build_ml_readiness_report(analysis: Dict[str, Any]) -> Dict[str, Any]:
    target = analysis.get("target_analysis", {})
    target_col = target.get("target_column")
    task_type = target.get("task_type", "unknown")
    confidence = target.get("confidence", "low")
    ambiguous = target.get("ambiguous", False)

    high_missing = analysis.get("high_missing_columns", {})
    constant_cols = analysis.get("column_types", {}).get("constant_cols", [])
    id_like_cols = analysis.get("column_types", {}).get("id_like_cols", [])
    duplicate_rows = analysis.get("duplicate_rows", 0)
    sr = analysis.get("signal_ranking", {})

    preprocessing_recommendations = []
    leakage_risk = []

    if not target_col:
        preprocessing_recommendations.append("No reliable target detected. Define a valid label/target column.")

    if confidence == "low":
        preprocessing_recommendations.append("Target detection confidence is low; manually validate the target column.")

    if ambiguous:
        preprocessing_recommendations.append("Multiple plausible targets detected; confirm the intended modeling target manually.")

    if len(high_missing) > 3:
        preprocessing_recommendations.append("Multiple high-missing columns detected; apply imputation or feature pruning.")

    if constant_cols:
        preprocessing_recommendations.append("Drop constant columns before model training.")

    if id_like_cols:
        preprocessing_recommendations.append("Exclude identifier-like columns from modeling unless explicitly justified.")
        leakage_risk.append("Identifier-like columns detected; ensure they are excluded from feature set.")

    if duplicate_rows > 0:
        preprocessing_recommendations.append("Review duplicate rows before training.")

    if not sr.get("available", False):
        preprocessing_recommendations.append("Signal ranking unavailable; validate target and preprocessing pipeline.")

    severe_missing_count = len([v for v in high_missing.values() if v >= 40])
    moderate_missing_count = len([v for v in high_missing.values() if 20 <= v < 40])

    is_ml_ready = True

    if not target_col:
        is_ml_ready = False
    elif confidence == "low":
        is_ml_ready = False
    elif ambiguous:
        is_ml_ready = False
    elif severe_missing_count > 0:
        is_ml_ready = False
    elif not sr.get("available", False):
        is_ml_ready = False
    elif duplicate_rows > 20:
        is_ml_ready = False

    class_imbalance_flag = False

    baseline_models = []
    if task_type == "classification":
        baseline_models = ["Logistic Regression", "Random Forest Classifier", "XGBoost (optional later)"]
    elif task_type == "regression":
        baseline_models = ["Linear Regression", "Random Forest Regressor", "XGBoost Regressor (optional later)"]

    readiness_label = (
        "Ready"
        if is_ml_ready and moderate_missing_count == 0 and len(constant_cols) == 0 and duplicate_rows == 0
        else "Conditionally Ready"
        if target_col
        else "Not Ready"
    )

    return {
        "target_detected": bool(target_col),
        "target_column": target_col,
        "task_type": task_type,
        "confidence": confidence,
        "ambiguous_target": ambiguous,
        "alternate_targets": target.get("alternate_targets", []),
        "is_ml_ready": is_ml_ready,
        "readiness_label": readiness_label,
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
    lines.append(f"Ambiguous Target: {mlr.get('ambiguous_target', False)}")

    alt_targets = mlr.get("alternate_targets", [])
    if alt_targets:
        lines.append(f"Alternate Targets: {alt_targets}")

    lines.append(f"ML Ready: {mlr.get('is_ml_ready', False)}")
    lines.append(f"Readiness Label: {mlr.get('readiness_label', 'Unknown')}")
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