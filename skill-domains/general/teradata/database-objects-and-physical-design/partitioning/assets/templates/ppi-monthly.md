# ppi monthly

```sql
-- Partitioned Table Template: Monthly Date Range
-- Replace: <database>, <table_name>, <columns>, <pi_columns>, <date_column>

CREATE TABLE <database>.<table_name> (
    <columns>
) PRIMARY INDEX (<pi_columns>)
  PARTITION BY RANGE_N(<date_column> BETWEEN DATE '2020-01-01'
      AND DATE '2025-12-31' EACH INTERVAL '1' MONTH,
      NO RANGE, UNKNOWN);
```
