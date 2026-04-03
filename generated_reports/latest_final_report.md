# Final Report

## Executive Summary
The primary analysis priorities are focused on understanding revenue generation, discount impact, customer segmentation effectiveness, and regional performance. Key questions revolve around identifying top-performing segments, regions, and products. The checks include ensuring data quality, detecting outliers, analyzing correlations, validating target validity, and preparing the dataset for potential machine learning applications. Visualizations will help in gaining insights into complex relationships within the dataset.

## Target Validation
- **Selected Target**: `Sales`
- **Task Type**: regression
- **Confidence**: medium
- **Ambiguous**: True
- **Alternate Targets**: `Quantity`, `Profit`
- **Note**: Selected based on semantic relevance + cardinality + domain-aware rules. Multiple plausible targets detected; manual confirmation recommended.

## Key Data Quality Findings
- **Missingness**: 
  - `Order Date`: 39.12% missing
  - `Ship Date`: 38.67% missing
  - `Postal Code`: 80.51% missing
- **Duplicates**: None detected.
- **Outliers**: Potential outliers in `Sales`, `Profit`, and `Quantity` columns need to be investigated further.
- **Identifier-Like Columns / Leakage Risks**: No identifier-like columns detected; no leakage risks identified.

## Key Statistical / Analytical Findings
- **Correlations**:
  - `Sales ↔ Profit`: 0.4849 (moderate)
  - `Discount ↔ Profit`: -0.3165 (moderate)
  - `Sales ↔ Quantity`: 0.3136 (moderate)
  - `Quantity ↔ Profit`: 0.1044 (weak)
  - `Sales ↔ Discount`: -0.0867 (negligible)
  - `Quantity ↔ Discount`: -0.0199 (negligible)

## KPI Highlights
- **Total Sales**: $1,264,250.19
- **Average Sales**: $246.49
- **Total Profit**: $146,745.73
- **Average Profit Margin Percentage**: 11.61%

## Signal Ranking Highlights
The top signals based on model-based feature importance are:
- `Profit`: 0.6976
- `Discount`: 0.0441
- `Quantity`: 0.0405
- `Sub-Category`: 0.0326
- `Product Name`: 0.0263
- `Ship Date`: 0.0241
- `Order Date`: 0.0228
- `Customer Name`: 0.0188
- `Category`: 0.0177
- `City`: 0.0176

## Visualization Insights
- **Histogram of Sales**: This histogram shows the distribution of sales, helping assess central tendency, spread, skewness, and possible extreme values.
- **Boxplot of Profit**: This boxplot highlights the spread of profit and potential outliers. Points beyond the whiskers may represent unusual or extreme observations worth validating.
- **Bar Chart of Ship Mode**: This bar chart shows the most frequent categories in `Ship Mode`, helping identify dominant categories, class imbalance, and concentration patterns.
- **Scatter Plot of Sales vs Profit**: This scatter plot compares sales and profit. It helps visually assess direction, clustering, possible association, and outliers.

## ML Readiness Assessment
- **Target Detection**: True
- **Task Type**: regression
- **Target Confidence**: medium
- **Ambiguous Target**: True
- **Alternate Targets**: `Quantity`, `Profit`
- **ML Ready Label**: Conditionally Ready
- **Preprocessing Needs**:
  - Multiple plausible targets detected; confirm the intended modeling target manually.
  - Exclude identifier-like columns from modeling unless explicitly justified.

## Risks / Cautions
1. **Ambiguous Target**: Manual confirmation is recommended for the target column `Sales`.
2. **Potential Outliers**: Investigate potential outliers to ensure they represent true extreme cases rather than data quality issues.
3. **Missing Data**: Handle missing values appropriately (e.g., imputation or exclusion) to avoid bias in analysis results.

## Actionable Recommendations
1. Manually confirm the target column `Sales` as it is flagged as ambiguous.
2. Apply domain-aware imputation for columns with moderate missingness and validate outliers in severely incomplete columns.
3. Investigate potential outliers to ensure they are not data quality issues but rather true anomalies.

## Conclusion
The analysis has identified key performance indicators such as total sales, average sales, total profit, and average profit margin percentage. The top signals based on model-based feature importance include `Profit`, `Discount`, `Quantity`, and other relevant features. Visualizations have provided insights into the distribution of sales and profits, while potential outliers need further investigation. Recommendations for handling missing data and confirming target validity are crucial steps to ensure robust analysis results.