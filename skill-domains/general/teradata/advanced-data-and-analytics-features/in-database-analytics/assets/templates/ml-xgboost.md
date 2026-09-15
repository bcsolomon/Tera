# ml xguoost

```sql
-- ML Train/Predict Template: XGBoost Classification
-- Replace: <database>, <train_table>, <score_table>, <target>, <features>

-- Train
SELECT * FROM XGBoost (
    ON <database>.<train_table> AS InputTable
    OUT TABLE OutputTable(<database>.xgb_model)
    USING
        ResponseColumn('<target>')
        NumericInputs(<features>)
        LossFunction('BINOMIAL')
        NumBoostedTrees(100)
        MaxDepth(6)
        LearningRate(0.1)
        RegularizationLambda(1)
        Seed(42)
) AS xgb;

-- Predict
SELECT * FROM XGBoostPredict (
    ON <database>.<score_table> AS InputTable
    ON <database>.xgb_model AS ModelTable DIMENSION
    USING
        NumericInputs(<features>)
        IdColumn('id')
) AS predictions;
```
