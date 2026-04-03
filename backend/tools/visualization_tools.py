import matplotlib
matplotlib.use("Agg")

import os
import uuid
import pandas as pd
import matplotlib.pyplot as plt

from backend.tools.analysis_tools import safe_read_csv


# ============================================================
# Config
# ============================================================
CHART_DIR = os.path.join("data", "processed", "charts")
os.makedirs(CHART_DIR, exist_ok=True)


# ============================================================
# Helpers
# ============================================================
def _safe_chart_path(prefix: str) -> str:
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    return os.path.join(CHART_DIR, filename)


def _save_current_plot(path: str):
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()


def _get_numeric_columns(df: pd.DataFrame):
    return df.select_dtypes(include=["number"]).columns.tolist()


def _get_categorical_columns(df: pd.DataFrame):
    return df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()


def _get_continuous_numeric_columns(df: pd.DataFrame):
    continuous = []
    for col in _get_numeric_columns(df):
        if df[col].nunique(dropna=True) > 10:
            continuous.append(col)
    return continuous


# ============================================================
# Chart Generators
# ============================================================
def create_histogram(df: pd.DataFrame, column: str):
    if column not in df.columns:
        return None

    series = df[column].dropna()
    if series.empty:
        return None

    path = _safe_chart_path(f"hist_{column}")

    plt.figure(figsize=(8, 5))
    plt.hist(series, bins=20)
    plt.title(f"Distribution of {column}")
    plt.xlabel(column)
    plt.ylabel("Frequency")

    _save_current_plot(path)

    interpretation = (
        f"This histogram shows the distribution of '{column}'. "
        f"It helps assess central tendency, spread, skewness, and possible extreme values."
    )

    return {
        "title": f"Histogram: {column}",
        "chart_type": "histogram",
        "columns": [column],
        "path": path,
        "interpretation": interpretation,
    }


def create_boxplot(df: pd.DataFrame, column: str):
    if column not in df.columns:
        return None

    series = df[column].dropna()
    if series.empty:
        return None

    path = _safe_chart_path(f"box_{column}")

    plt.figure(figsize=(8, 5))
    plt.boxplot(series, vert=True)
    plt.title(f"Boxplot of {column}")
    plt.ylabel(column)

    _save_current_plot(path)

    interpretation = (
        f"This boxplot highlights the spread of '{column}' and potential outliers. "
        f"Points beyond the whiskers may represent unusual or extreme observations worth validating."
    )

    return {
        "title": f"Boxplot: {column}",
        "chart_type": "boxplot",
        "columns": [column],
        "path": path,
        "interpretation": interpretation,
    }


def create_bar_chart(df: pd.DataFrame, column: str, top_n: int = 10):
    if column not in df.columns:
        return None

    counts = df[column].astype(str).value_counts().head(top_n)
    if counts.empty:
        return None

    path = _safe_chart_path(f"bar_{column}")

    plt.figure(figsize=(10, 5))
    counts.plot(kind="bar")
    plt.title(f"Top {top_n} Categories in {column}")
    plt.xlabel(column)
    plt.ylabel("Count")
    plt.xticks(rotation=45, ha="right")

    _save_current_plot(path)

    interpretation = (
        f"This bar chart shows the most frequent categories in '{column}'. "
        f"It helps identify dominant categories, class imbalance, and concentration patterns."
    )

    return {
        "title": f"Bar Chart: {column}",
        "chart_type": "bar",
        "columns": [column],
        "path": path,
        "interpretation": interpretation,
    }


def create_scatter_plot(df: pd.DataFrame, x_col: str, y_col: str):
    if x_col not in df.columns or y_col not in df.columns:
        return None

    plot_df = df[[x_col, y_col]].dropna()
    if plot_df.empty:
        return None

    path = _safe_chart_path(f"scatter_{x_col}_{y_col}")

    plt.figure(figsize=(8, 5))
    plt.scatter(plot_df[x_col], plot_df[y_col], alpha=0.6)
    plt.title(f"{x_col} vs {y_col}")
    plt.xlabel(x_col)
    plt.ylabel(y_col)

    _save_current_plot(path)

    interpretation = (
        f"This scatter plot compares '{x_col}' and '{y_col}'. "
        f"It helps visually assess direction, clustering, possible association, and outliers."
    )

    return {
        "title": f"Scatter Plot: {x_col} vs {y_col}",
        "chart_type": "scatter",
        "columns": [x_col, y_col],
        "path": path,
        "interpretation": interpretation,
    }


# ============================================================
# Main Autonomous Visualization Engine (UPDATED)
# ============================================================
def generate_recommended_visualizations(file_path: str, analysis_result: dict):
    df = safe_read_csv(file_path)  # IMPORTANT: use same smart preprocessing
    visualizations = []

    column_info = analysis_result.get("column_types", {})
    id_like_cols = set(column_info.get("id_like_cols", []))
    constant_cols = set(column_info.get("constant_cols", []))

    numeric_cols = [
        c for c in _get_numeric_columns(df)
        if c not in id_like_cols and c not in constant_cols
    ]

    continuous_numeric_cols = [
        c for c in _get_continuous_numeric_columns(df)
        if c not in id_like_cols and c not in constant_cols
    ]

    categorical_cols = [
        c for c in _get_categorical_columns(df)
        if c not in id_like_cols and c not in constant_cols
        and df[c].nunique(dropna=True) <= 20
    ]

    # 1. Histogram
    hist_col = continuous_numeric_cols[0] if continuous_numeric_cols else (numeric_cols[0] if numeric_cols else None)
    if hist_col:
        hist_viz = create_histogram(df, hist_col)
        if hist_viz:
            visualizations.append(hist_viz)

    # 2. Boxplot
    outlier_counts = analysis_result.get("outlier_counts", {})
    filtered_outliers = {k: v for k, v in outlier_counts.items() if k in numeric_cols}

    if filtered_outliers:
        sorted_outliers = sorted(filtered_outliers.items(), key=lambda x: x[1], reverse=True)
        box_col = sorted_outliers[0][0] if sorted_outliers and sorted_outliers[0][1] > 0 else hist_col
    else:
        box_col = hist_col

    if box_col:
        box_viz = create_boxplot(df, box_col)
        if box_viz:
            visualizations.append(box_viz)

    # 3. Bar chart
    if categorical_cols:
        bar_viz = create_bar_chart(df, categorical_cols[0], top_n=10)
        if bar_viz:
            visualizations.append(bar_viz)

    # 4. Scatter plot from strongest valid correlation
    top_corrs = analysis_result.get("top_correlations", [])
    for pair in top_corrs:
        x_col = pair.get("col1")
        y_col = pair.get("col2")

        if x_col in numeric_cols and y_col in numeric_cols and x_col != y_col:
            scatter_viz = create_scatter_plot(df, x_col, y_col)
            if scatter_viz:
                visualizations.append(scatter_viz)
                break

    # 5. Filtered correlation heatmap
    if len(numeric_cols) >= 3:
        corr = df[numeric_cols].corr()

        if corr.shape[0] >= 2:
            path = _safe_chart_path("heatmap_corr")

            plt.figure(figsize=(10, 8))
            plt.imshow(corr, aspect="auto")
            plt.colorbar()
            plt.xticks(range(len(corr.columns)), corr.columns, rotation=90)
            plt.yticks(range(len(corr.columns)), corr.columns)
            plt.title("Correlation Heatmap (Filtered Numeric Features)")

            _save_current_plot(path)

            visualizations.append({
                "title": "Correlation Heatmap",
                "chart_type": "heatmap",
                "columns": corr.columns.tolist(),
                "path": path,
                "interpretation": (
                    "This filtered correlation heatmap summarizes pairwise relationships across meaningful numeric features, "
                    "excluding identifier-like and constant columns."
                ),
            })

    # 6. Target-aware visualization
    target_info = analysis_result.get("target_analysis", {})
    target_col = target_info.get("target_column")

    if target_col and target_col in df.columns and target_col not in id_like_cols:
        already_used_as_single_col = any(viz.get("columns") == [target_col] for viz in visualizations)

        if not already_used_as_single_col:
            if target_col in numeric_cols:
                target_hist = create_histogram(df, target_col)
                if target_hist:
                    target_hist["title"] = f"Target Distribution: {target_col}"
                    target_hist["interpretation"] = (
                        f"This chart shows the distribution of the detected target '{target_col}'. "
                        f"It helps assess spread, skewness, and possible extreme values."
                    )
                    visualizations.append(target_hist)
            else:
                if df[target_col].nunique(dropna=True) <= 20:
                    target_bar = create_bar_chart(df, target_col, top_n=10)
                    if target_bar:
                        target_bar["title"] = f"Target Class Distribution: {target_col}"
                        target_bar["interpretation"] = (
                            f"This chart shows the class distribution for the detected target '{target_col}'. "
                            f"It helps identify class imbalance, which is important for classification modeling."
                        )
                        visualizations.append(target_bar)

    return visualizations[:6]