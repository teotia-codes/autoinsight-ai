# Final Report

## Executive Summary
This dataset appears related to customer churn and seems usable for exploratory and predictive analysis. Some preprocessing is probably needed before production modeling.

## Target Validation
The likely target is Churn. Task type is Classification. Confidence is Moderate. Ambiguous = False. The selected target is plausible but should be validated against stakeholder intent.

## Key Data Quality Findings
Quality score is around 72/100 with about 35523 rows and 17 columns.
Critical issues: None major.
Moderate issues: Missing values in selected columns, Potential outliers in numeric features.
Recommendations: Impute missing values, Review outliers before modeling.

## Key Statistical / Analytical Findings
Skewness in important measures suggests that robust preprocessing could improve downstream modeling reliability.

## KPI Highlights
- Retention Rate: should be reviewed for trend and segment behavior
- Churn Rate: should be reviewed for trend and segment behavior
- Average Revenue per User: should be reviewed for trend and segment behavior

## Signal Ranking Highlights
Top signals look like:
- Usage: 0.44
- ContractType: 0.44
- MonthlyCharges: 0.32

## Visualization Insights
- Churn by Contract Type: useful for finding patterns but needs more inspection
- Revenue by Segment: useful for finding patterns but needs more inspection

## ML Readiness Assessment
Readiness is Conditionally Ready. ML ready = True. Class imbalance flag = True.
Potential leakage = Potential target leakage in engineered columns.
Preprocessing recommendations = Drop leakage-prone columns, Handle class imbalance, Review missing value strategy.
Suggested baseline models = Random Forest Classifier, CatBoost Classifier.

## Risks / Cautions
Potential leakage from post-outcome or engineered columns could inflate model performance if not removed.

## Actionable Recommendations
1. Confirm that engineered features do not leak post-outcome information.
2. Remove identifier-like columns and review high-cardinality fields before model training.
3. Review subgroup performance to ensure the model generalizes across segments.

## Conclusion
This report gives an initial analysis of customer_churn_150.csv and suggests the dataset may be useful after preprocessing, validation, and baseline benchmarking.
