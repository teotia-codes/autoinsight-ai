# Final Report

## Executive Summary
This dataset is suitable for exploratory and predictive analysis in the **Customer Churn** domain. The estimated data quality score is **72/100**, which indicates a **moderate** readiness level for downstream analytics. With targeted preprocessing, target validation, and baseline benchmarking, the dataset can support KPI monitoring, signal ranking, and early-stage machine learning workflows.

## Target Validation
The most likely target variable is **Churn**, and the inferred task type is **Classification**. Confidence in this target selection is **Moderate**, with ambiguity status set to **False**. The selected target is plausible but should be validated against stakeholder intent.

## Key Data Quality Findings
The dataset contains approximately **35523 rows** and **17 columns**.  
- **Critical Issues:** No critical issues were explicitly detected  
- **Moderate Issues:** Missing values in selected columns, Potential outliers in numeric features  
- **Recommended Remediation:** Impute missing values, Review outliers before modeling  

This indicates that the dataset is analytically useful, but some preprocessing steps should be completed before production-grade modeling.

## Key Statistical / Analytical Findings
Skewness in important measures suggests that robust preprocessing could improve downstream modeling reliability. These findings should be interpreted as directional analytical evidence rather than proof of causality.

## KPI Highlights
- **Retention Rate** should be monitored across time, segments, and operational slices to surface actionable performance patterns.
- **Churn Rate** should be monitored across time, segments, and operational slices to surface actionable performance patterns.
- **Average Revenue per User** should be monitored across time, segments, and operational slices to surface actionable performance patterns.

## Signal Ranking Highlights
The preliminary signal ranking suggests the following variables are the strongest contributors:
- **Usage**: estimated importance **0.44**
- **ContractType**: estimated importance **0.44**
- **MonthlyCharges**: estimated importance **0.32**

## Visualization Insights
- **Churn by Contract Type** can support trend detection, anomaly review, and stakeholder interpretation.
- **Revenue by Segment** can support trend detection, anomaly review, and stakeholder interpretation.

## ML Readiness Assessment
The dataset is currently assessed as **Conditionally Ready** for machine learning.  
- **ML Ready:** True  
- **Class Imbalance Flag:** True  
- **Potential Leakage Risk:** Potential target leakage in engineered columns  
- **Recommended Preprocessing:** Drop leakage-prone columns, Handle class imbalance, Review missing value strategy  
- **Suggested Baseline Models:** Random Forest Classifier, CatBoost Classifier  

## Risks / Cautions
Potential leakage from post-outcome or engineered columns could inflate model performance if not removed. These issues should be addressed before treating model performance as production-ready.

## Actionable Recommendations
1. Confirm that engineered features do not leak post-outcome information.
2. Remove identifier-like columns and review high-cardinality fields before model training.
3. Review subgroup performance to ensure the model generalizes across segments.

## Conclusion
This report provides a structured assessment of **customer_churn_150.csv** and indicates that the dataset has meaningful analytical value. With proper target validation, data cleaning, leakage review, and baseline model benchmarking, it can support both business intelligence workflows and early-stage predictive modeling.
