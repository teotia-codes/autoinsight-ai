You are a senior data analyst writing a polished executive analytics report.

Create a FINAL REPORT using the evidence below.

IMPORTANT RULES:
1. Be accurate and conservative. Do NOT exaggerate.
2. If target selection is ambiguous, explicitly mention that the selected target is the default choice and manual confirmation is recommended.
3. Use the term "Signal Ranking" instead of "Feature Importance".
4. If ML readiness is not fully clean, say "Conditionally Ready" or "Requires preprocessing" instead of claiming the dataset is fully ready.
5. Do NOT repeat the verification section verbatim.
6. Keep the report executive, analytical, and grounded.
7. Do NOT claim causality from correlations or model-based signal ranking.

INPUTS:

Planner Output:
### Analysis Priorities

1. **Understanding Employee Attrition:**
   - Investigate why employees leave the company (target variable).
2. **Employee Satisfaction Factors:**
   - Analyze factors influencing employee satisfaction such as job involvement, work-life balance, and departmental distribution.
3. **Work-Life Balance and Overtime:**
   - Examine the impact of overtime and work-life balance on attrition.
4. **Salary and Years at Company:**
   - Evaluate how salary levels and tenure affect employee retention.
5. **Job Role and Department Distribution:**
   - Analyze job role distribution across departments to identify potential issues or opportunities.

### Business / Domain Questions

1. **Why do employees leave?** What are the key reasons for attrition?
2. **What factors influence employee satisfaction?** How can we improve these areas?
3. **How does overtime impact employee retention?**
4. **Are salary levels and years at company significant predictors of attrition?**
5. **Is there a specific job role or department that contributes more to attrition?**

### What Should Be Checked

#### Target Validity
- Ensure the target variable (Attrition) is binary (0/1).

#### Data Quality
- Check for missing values and outliers in numeric columns.
- Verify data types, especially for categorical variables.

#### Correlations
- Identify correlations between Attrition and other key features like AgeGroup, EducationField, JobRole, etc.

#### Outliers
- Detect and handle any outliers in numerical columns.

#### Key Performance Indicators (KPIs)
- Monitor the performance of different feature importance models.
- Track model accuracy, precision, recall, F1-score for Attrition prediction.

#### Signal Ranking
- Rank features based on their predictive power using correlation coefficients or other ranking methods.

#### ML Readiness
- Ensure data is clean and ready for modeling. Check for any transformations needed (e.g., encoding categorical variables).

#### Visualizations
- Create visualizations to understand the distribution of Attrition, AgeGroup, EducationField, JobRole, etc.
- Use heatmaps to identify correlations between features.

### Plan Structure

1. **Data Cleaning:**
   - Handle missing values in YearsWithCurrManager.
   - Check for and handle outliers in numeric columns.
   - Verify data types and encode categorical variables if necessary.

2. **Exploratory Data Analysis (EDA):**
   - Visualize distributions of key features like Age, EducationField, JobRole, etc.
   - Create correlation matrices to identify potential predictors of Attrition.
   - Plot histograms for numerical features to understand their distribution.

3. **Feature Engineering:**
   - Create new features if necessary (e.g., tenure in years).
   - Encode categorical variables using one-hot encoding or label encoding.

4. **Model Evaluation:**
   - Split the dataset into training and testing sets.
   - Train various models (e.g., Logistic Regression, Random Forest, Gradient Boosting) to predict Attrition.
   - Evaluate model performance using metrics like accuracy, precision, recall, F1-score.

5. **Feature Importance Analysis:**
   - Use feature importance scores from the trained models to identify key predictors of Attrition.

6. **Visualization and Reporting:**
   - Create a final report using the evidence above.
   - Use a clear and concise language to communicate the findings and conclusions.
   - Include recommendations for improvement based on the findings.

7. **Recommendations:**
   - Identify key areas for improvement based on the findings.
   - Provide recommendations for addressing these areas.
   - Provide a detailed plan for addressing the identified areas.

8. **Conclusion:**
   - Summarize the key findings and recommendations.
   - Provide a conclusion that summarizes the findings and recommendations.
   - Include a call to action for the client to take action based on the findings.