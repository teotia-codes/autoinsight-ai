import os
import random
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================
NUM_EXAMPLES = 300
OUTPUT_DRAFTS = "training_data/drafts"
OUTPUT_POLISHED = "training_data/polished"

random.seed(42)

# ============================================================
# DOMAIN CONFIGS
# ============================================================
DOMAINS = [
    {
        "name": "Retail Sales",
        "filename_prefix": "retail_sales",
        "targets": ["Sales", "Profit", "Order Value"],
        "task_type_map": {
            "Sales": "Regression",
            "Profit": "Regression",
            "Order Value": "Regression",
        },
        "kpis": ["Total Sales", "Average Order Value", "Gross Profit", "Profit Margin"],
        "signals": ["Discount", "Quantity", "Shipping Cost", "Region", "Category"],
        "visualizations": ["Monthly Sales Trend", "Profit by Category", "Regional Sales Distribution"],
        "models": ["XGBoost Regressor", "Random Forest Regressor", "LightGBM Regressor"],
    },
    {
        "name": "Healthcare Risk",
        "filename_prefix": "healthcare_risk",
        "targets": ["DiabetesRisk", "ReadmissionRisk", "HeartDiseaseRisk"],
        "task_type_map": {
            "DiabetesRisk": "Classification",
            "ReadmissionRisk": "Classification",
            "HeartDiseaseRisk": "Classification",
        },
        "kpis": ["Risk Prevalence", "Positive Class Rate", "Average Biomarker Score"],
        "signals": ["Glucose", "BMI", "Age", "BloodPressure", "Insulin"],
        "visualizations": ["Risk Distribution", "Biomarker Correlation Heatmap", "Age vs Risk"],
        "models": ["Logistic Regression", "XGBoost Classifier", "Random Forest Classifier"],
    },
    {
        "name": "Customer Churn",
        "filename_prefix": "customer_churn",
        "targets": ["Churn", "RetentionRisk"],
        "task_type_map": {
            "Churn": "Classification",
            "RetentionRisk": "Classification",
        },
        "kpis": ["Churn Rate", "Average Revenue per User", "Retention Rate"],
        "signals": ["Tenure", "MonthlyCharges", "ContractType", "SupportCalls", "Usage"],
        "visualizations": ["Churn by Contract Type", "Tenure Distribution", "Revenue by Segment"],
        "models": ["Logistic Regression", "CatBoost Classifier", "Random Forest Classifier"],
    },
    {
        "name": "Financial Credit",
        "filename_prefix": "credit_risk",
        "targets": ["Default", "CreditScoreBand"],
        "task_type_map": {
            "Default": "Classification",
            "CreditScoreBand": "Classification",
        },
        "kpis": ["Default Rate", "Average Credit Utilization", "Delinquency Rate"],
        "signals": ["CreditUtilization", "Income", "DebtToIncome", "LatePayments", "LoanAmount"],
        "visualizations": ["Default Rate by Segment", "Income vs Default", "Utilization Distribution"],
        "models": ["Logistic Regression", "XGBoost Classifier", "LightGBM Classifier"],
    },
    {
        "name": "Supply Chain",
        "filename_prefix": "supply_chain",
        "targets": ["DeliveryDelay", "FulfillmentTime", "StockoutRisk"],
        "task_type_map": {
            "DeliveryDelay": "Regression",
            "FulfillmentTime": "Regression",
            "StockoutRisk": "Classification",
        },
        "kpis": ["On-Time Delivery Rate", "Average Fulfillment Time", "Stockout Frequency"],
        "signals": ["LeadTime", "InventoryLevel", "SupplierRegion", "OrderVolume", "TransportMode"],
        "visualizations": ["Lead Time Trend", "Stockout by Warehouse", "Delay by Supplier"],
        "models": ["XGBoost Regressor", "Random Forest Regressor", "Gradient Boosting Regressor"],
    },
    {
        "name": "HR Attrition",
        "filename_prefix": "hr_attrition",
        "targets": ["Attrition", "PerformanceScore"],
        "task_type_map": {
            "Attrition": "Classification",
            "PerformanceScore": "Regression",
        },
        "kpis": ["Attrition Rate", "Average Tenure", "Performance Distribution"],
        "signals": ["Overtime", "YearsAtCompany", "JobRole", "MonthlyIncome", "JobSatisfaction"],
        "visualizations": ["Attrition by Department", "Income vs Attrition", "Tenure Distribution"],
        "models": ["Logistic Regression", "Random Forest Classifier", "XGBoost Classifier"],
    },
]

TARGET_NOTES = [
    "The target selection appears aligned with the likely business objective.",
    "The selected target is plausible but should be validated against stakeholder intent.",
    "Multiple plausible targets may exist, so manual confirmation is recommended before production modeling.",
]

STAT_FINDINGS = [
    "Correlation patterns suggest that a small subset of operational variables explains a meaningful share of target variation.",
    "Segment-level differences indicate that performance is not uniform across categories, regions, or customer groups.",
    "Outlier concentration in numeric fields may affect KPI interpretation and model stability if not addressed.",
    "Skewness in important measures suggests that robust preprocessing could improve downstream modeling reliability.",
]

RISKS = [
    "Potential leakage from post-outcome or engineered columns could inflate model performance if not removed.",
    "Identifier-like columns may distort signal ranking if retained in the modeling set.",
    "Outliers may bias statistical summaries and tree-based importance signals if not reviewed.",
    "Class imbalance may reduce minority-class recall unless reweighting or resampling is applied.",
]

RECOMMENDATIONS = [
    "Validate the target variable against the intended analytical objective before production use.",
    "Remove identifier-like columns and review high-cardinality fields before model training.",
    "Impute missing values using domain-aware methods instead of blanket defaults.",
    "Inspect outliers before deciding between clipping, winsorization, or exclusion.",
    "Benchmark at least two baseline models before selecting a production candidate.",
    "Review subgroup performance to ensure the model generalizes across segments.",
    "Confirm that engineered features do not leak post-outcome information.",
]

QUALITY_OPTIONS = [
    {
        "label": "High",
        "score_range": (84, 95),
        "critical_issues": [],
        "moderate_issues": ["Minor missing values in non-critical columns"],
        "recommendations": ["Proceed with light preprocessing", "Validate feature types before training"],
    },
    {
        "label": "Moderate",
        "score_range": (68, 82),
        "critical_issues": [],
        "moderate_issues": ["Missing values in selected columns", "Potential outliers in numeric features"],
        "recommendations": ["Impute missing values", "Review outliers before modeling"],
    },
    {
        "label": "Low",
        "score_range": (48, 64),
        "critical_issues": ["Identifier-like columns detected", "Potential leakage risk in derived fields"],
        "moderate_issues": ["High missingness in important fields", "Potential outliers in key variables"],
        "recommendations": ["Perform substantial cleaning", "Drop leakage-prone columns", "Validate target carefully"],
    },
]

READINESS_OPTIONS = [
    {
        "label": "Ready",
        "is_ml_ready": True,
        "class_imbalance_flag": False,
        "leakage_risk": [],
        "preprocessing_recommendations": ["Standardize numeric variables", "Validate categorical encoding"],
        "baseline_model_count": 2,
    },
    {
        "label": "Conditionally Ready",
        "is_ml_ready": True,
        "class_imbalance_flag": True,
        "leakage_risk": ["Potential target leakage in engineered columns"],
        "preprocessing_recommendations": ["Drop leakage-prone columns", "Handle class imbalance", "Review missing value strategy"],
        "baseline_model_count": 2,
    },
    {
        "label": "Requires Preprocessing",
        "is_ml_ready": False,
        "class_imbalance_flag": True,
        "leakage_risk": ["High missingness and imbalance risk", "Potential identifier leakage"],
        "preprocessing_recommendations": ["Impute missing values", "Remove identifiers", "Resample target classes", "Review target validity"],
        "baseline_model_count": 1,
    },
]

# ============================================================
# HELPERS
# ============================================================
def choose(lst, k=None):
    if k is None:
        return random.choice(lst)
    return random.sample(lst, min(k, len(lst)))

def score_from_range(rng):
    return random.randint(rng[0], rng[1])

def build_signal_pairs(signals):
    chosen = choose(signals, 3)
    weights = sorted([round(random.uniform(0.18, 0.48), 2) for _ in chosen], reverse=True)
    return list(zip(chosen, weights))

def build_scenario(idx: int):
    domain = random.choice(DOMAINS)
    target = random.choice(domain["targets"])
    task_type = domain["task_type_map"][target]

    confidence = random.choice(["High", "Medium", "Moderate"])
    ambiguous = random.choice([False, False, True])
    note = random.choice(TARGET_NOTES)

    quality_cfg = random.choice(QUALITY_OPTIONS)
    readiness_cfg = random.choice(READINESS_OPTIONS)

    quality_score = score_from_range(quality_cfg["score_range"])

    signal_pairs = build_signal_pairs(domain["signals"])
    selected_kpis = choose(domain["kpis"], 3)
    selected_visualizations = choose(domain["visualizations"], 2)
    selected_models = choose(domain["models"], readiness_cfg["baseline_model_count"])

    rows = random.randint(800, 50000)
    cols = random.randint(8, 35)

    scenario = {
        "filename": f"{domain['filename_prefix']}_{idx:03d}.csv",
        "domain_name": domain["name"],
        "target": target,
        "task_type": task_type,
        "confidence": confidence,
        "ambiguous": ambiguous,
        "note": note,

        "rows": rows,
        "columns": cols,

        "quality_label": quality_cfg["label"],
        "quality_score": quality_score,
        "critical_issues": quality_cfg["critical_issues"],
        "moderate_issues": quality_cfg["moderate_issues"],
        "quality_recommendations": quality_cfg["recommendations"],

        "stat_finding": random.choice(STAT_FINDINGS),

        "kpis": selected_kpis,
        "signal_pairs": signal_pairs,
        "visualizations": selected_visualizations,

        "readiness_label": readiness_cfg["label"],
        "is_ml_ready": readiness_cfg["is_ml_ready"],
        "class_imbalance_flag": readiness_cfg["class_imbalance_flag"],
        "leakage_risk": readiness_cfg["leakage_risk"],
        "preprocessing_recommendations": readiness_cfg["preprocessing_recommendations"],
        "baseline_models": selected_models,

        "risk": random.choice(RISKS),
        "recommendations": choose(RECOMMENDATIONS, 3),
    }

    return scenario

# ============================================================
# RENDERERS
# ============================================================
def render_draft(s):
    kpi_lines = "\n".join(
        [f"- {metric}: should be reviewed for trend and segment behavior" for metric in s["kpis"]]
    )

    signal_lines = "\n".join(
        [f"- {feat}: {weight}" for feat, weight in s["signal_pairs"]]
    )

    viz_lines = "\n".join(
        [f"- {viz}: useful for finding patterns but needs more inspection" for viz in s["visualizations"]]
    )

    critical = ", ".join(s["critical_issues"]) if s["critical_issues"] else "None major"
    moderate = ", ".join(s["moderate_issues"]) if s["moderate_issues"] else "None obvious"
    quality_recos = ", ".join(s["quality_recommendations"])
    leakage = ", ".join(s["leakage_risk"]) if s["leakage_risk"] else "None obvious"
    preprocessing = ", ".join(s["preprocessing_recommendations"])
    baseline = ", ".join(s["baseline_models"])

    return f"""# Final Report

## Executive Summary
This dataset appears related to {s["domain_name"].lower()} and seems usable for exploratory and predictive analysis. Some preprocessing is probably needed before production modeling.

## Target Validation
The likely target is {s["target"]}. Task type is {s["task_type"]}. Confidence is {s["confidence"]}. Ambiguous = {s["ambiguous"]}. {s["note"]}

## Key Data Quality Findings
Quality score is around {s["quality_score"]}/100 with about {s["rows"]} rows and {s["columns"]} columns.
Critical issues: {critical}.
Moderate issues: {moderate}.
Recommendations: {quality_recos}.

## Key Statistical / Analytical Findings
{s["stat_finding"]}

## KPI Highlights
{kpi_lines}

## Signal Ranking Highlights
Top signals look like:
{signal_lines}

## Visualization Insights
{viz_lines}

## ML Readiness Assessment
Readiness is {s["readiness_label"]}. ML ready = {s["is_ml_ready"]}. Class imbalance flag = {s["class_imbalance_flag"]}.
Potential leakage = {leakage}.
Preprocessing recommendations = {preprocessing}.
Suggested baseline models = {baseline}.

## Risks / Cautions
{s["risk"]}

## Actionable Recommendations
1. {s["recommendations"][0]}
2. {s["recommendations"][1]}
3. {s["recommendations"][2]}

## Conclusion
This report gives an initial analysis of {s["filename"]} and suggests the dataset may be useful after preprocessing, validation, and baseline benchmarking.
"""

def render_polished(s):
    kpi_lines = "\n".join(
        [f"- **{metric}** should be monitored across time, segments, and operational slices to surface actionable performance patterns." for metric in s["kpis"]]
    )

    signal_lines = "\n".join(
        [f"- **{feat}**: estimated importance **{weight}**" for feat, weight in s["signal_pairs"]]
    )

    viz_lines = "\n".join(
        [f"- **{viz}** can support trend detection, anomaly review, and stakeholder interpretation." for viz in s["visualizations"]]
    )

    critical = ", ".join(s["critical_issues"]) if s["critical_issues"] else "No critical issues were explicitly detected"
    moderate = ", ".join(s["moderate_issues"]) if s["moderate_issues"] else "No major moderate issues were identified"
    quality_recos = ", ".join(s["quality_recommendations"])
    leakage = ", ".join(s["leakage_risk"]) if s["leakage_risk"] else "No immediate leakage indicators detected"
    preprocessing = ", ".join(s["preprocessing_recommendations"])
    baseline = ", ".join(s["baseline_models"])

    return f"""# Final Report

## Executive Summary
This dataset is suitable for exploratory and predictive analysis in the **{s["domain_name"]}** domain. The estimated data quality score is **{s["quality_score"]}/100**, which indicates a **{s["quality_label"].lower()}** readiness level for downstream analytics. With targeted preprocessing, target validation, and baseline benchmarking, the dataset can support KPI monitoring, signal ranking, and early-stage machine learning workflows.

## Target Validation
The most likely target variable is **{s["target"]}**, and the inferred task type is **{s["task_type"]}**. Confidence in this target selection is **{s["confidence"]}**, with ambiguity status set to **{s["ambiguous"]}**. {s["note"]}

## Key Data Quality Findings
The dataset contains approximately **{s["rows"]} rows** and **{s["columns"]} columns**.  
- **Critical Issues:** {critical}  
- **Moderate Issues:** {moderate}  
- **Recommended Remediation:** {quality_recos}  

This indicates that the dataset is analytically useful, but some preprocessing steps should be completed before production-grade modeling.

## Key Statistical / Analytical Findings
{s["stat_finding"]} These findings should be interpreted as directional analytical evidence rather than proof of causality.

## KPI Highlights
{kpi_lines}

## Signal Ranking Highlights
The preliminary signal ranking suggests the following variables are the strongest contributors:
{signal_lines}

## Visualization Insights
{viz_lines}

## ML Readiness Assessment
The dataset is currently assessed as **{s["readiness_label"]}** for machine learning.  
- **ML Ready:** {s["is_ml_ready"]}  
- **Class Imbalance Flag:** {s["class_imbalance_flag"]}  
- **Potential Leakage Risk:** {leakage}  
- **Recommended Preprocessing:** {preprocessing}  
- **Suggested Baseline Models:** {baseline}  

## Risks / Cautions
{s["risk"]} These issues should be addressed before treating model performance as production-ready.

## Actionable Recommendations
1. {s["recommendations"][0]}
2. {s["recommendations"][1]}
3. {s["recommendations"][2]}

## Conclusion
This report provides a structured assessment of **{s["filename"]}** and indicates that the dataset has meaningful analytical value. With proper target validation, data cleaning, leakage review, and baseline model benchmarking, it can support both business intelligence workflows and early-stage predictive modeling.
"""

# ============================================================
# MAIN
# ============================================================
def main():
    Path(OUTPUT_DRAFTS).mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_POLISHED).mkdir(parents=True, exist_ok=True)

    for i in range(1, NUM_EXAMPLES + 1):
        scenario = build_scenario(i)

        draft = render_draft(scenario)
        polished = render_polished(scenario)

        filename = f"report_{i:03d}.md"

        with open(os.path.join(OUTPUT_DRAFTS, filename), "w", encoding="utf-8") as f:
            f.write(draft)

        with open(os.path.join(OUTPUT_POLISHED, filename), "w", encoding="utf-8") as f:
            f.write(polished)

    print(f"Generated {NUM_EXAMPLES} aligned draft reports in: {OUTPUT_DRAFTS}")
    print(f"Generated {NUM_EXAMPLES} aligned polished reports in: {OUTPUT_POLISHED}")
    print("Done. Draft and polished files are fact-aligned and ready for JSONL conversion.")

if __name__ == "__main__":
    main()