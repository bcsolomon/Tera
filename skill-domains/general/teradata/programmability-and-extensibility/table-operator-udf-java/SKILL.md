---
name: table-operator-udf-java
description: 'Create, register, and remove Java Table Operator User-Defined Functions on Teradata. Use when implementing a parallel streaming operator in Java that takes a table as input and produces a table as output. Java table operators differ from Java table functions: they declare no scalar parameters (input arrives as streamed ResultSet arrays), define their output schema dynamically through a contract method named in the RETURNS TABLE VARYING USING FUNCTION clause, use PARAMETER STYLE SQLTABLE, implement the TableOperator interface with contract and execute methods, run on each AMP in parallel, and accept partitioning clauses (HASH BY, PARTITION BY, LOCAL ORDER BY). Covers the operator DDL, the TableOperator interface, JAR lifecycle, and the EXTERNAL NAME format. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions Java table operator, TableOperator interface, RuntimeContract, PARAMETER STYLE SQLTABLE with LANGUAGE JAVA, RETURNS TABLE VARYING USING FUNCTION in Java, a contract and execute method pair, or wants to run a Java function on each AMP across a partitioned input stream.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Java Table Operator UDF

> **Installation differs by platform.** All Teradata systems support external UDFs, XSPs, and UDTs,
> but not all allow the same installation process. The `CREATE`/`REPLACE ... EXTERNAL NAME` DDL in
> this skill applies to on-prem systems where you have full access to the database nodes. On
> Teradata-managed systems, direct DDL installation may be blocked for security reasons:
>
> - **VantageCloud Lake:** use the `tdextroutine` CLI to install, list, and uninstall these objects.
>   See [Create, Use, and Migrate UDFs and External Stored Procedures in VantageCloud Lake](https://docs.teradata.com/r/Lake-Using-Queries-UDFs-and-External-Stored-Procedures/Create-Use-and-Migrate-UDFs-and-External-Stored-Procedures-in-VantageCloud-Lake).
> - **VantageCloud Enterprise:** `EXTERNAL NAME` installation is supported on Compute Engine nodes
>   but not on the primary Enterprise Data Warehouse (EDW) node; that is typically handled through a
>   customer service request.
>
> Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`.

A **Java table operator** takes a **table** as input and produces a table as output. Unlike a
table function (which takes scalar inputs and returns rows), a table operator:

- Declares no formal scalar parameters. Its input arrives as one or more streamed `ResultSet`
  inputs at invocation
- Defines its output schema through a separate **contract method** named in the
  `RETURNS TABLE VARYING USING FUNCTION <contract>` clause
- Uses `PARAMETER STYLE SQLTABLE`, not `PARAMETER STYLE JAVA`
- Implements the `com.teradata.fnc.TableOperator` interface with two methods: `contract` and `execute`
- Runs on each AMP in parallel, processing the locally partitioned rows

> **Not this skill:** For C/C++ table operators, see **table-operator-udf-c**. For Java functions
> returning rows from scalar inputs, see **table-function-udf-java**.

## When to Use

- Implementing a parallel per-AMP streaming transform in Java
- Running a stateful algorithm across a partitioned input (e.g., rolling window, scoring)
- Processing each AMP's local data share without cross-AMP communication
- Any workload where a Java method consumes rows from a table and emits rows

## DDL Syntax

A Java table operator is registered with an **empty parameter list**. A single DDL registers both
the contract and execute methods. The output schema is determined at plan time by the **contract
method**, referenced through the `USING FUNCTION` clause.

```sql
REPLACE FUNCTION mydb.jtblop_udtvals ()
    RETURNS TABLE VARYING USING FUNCTION mydb.jtblop_udtvals_contract
    LANGUAGE JAVA
    NO SQL
    PARAMETER STYLE SQLTABLE
    EXTERNAL NAME 'TBLOPUDT_JAR:jtblop_udtvals.execute';
```

- `()` empty parameter list: the operator reads input rows from the streamed input table, not from declared parameters
- `RETURNS TABLE VARYING USING FUNCTION <contract>`: names the contract method that defines the output column schema dynamically
- `PARAMETER STYLE SQLTABLE`: the table operator calling convention. Input and output flow through `ResultSet` arrays, not scalar parameters
- `EXTERNAL NAME '<JAR_ALIAS>:<class>.execute'`: the installed JAR alias, the class implementing `TableOperator`, and the `execute` method. The contract method is located automatically from the same class. Only one DDL is needed for both

### Key DDL Differences vs Java Table Function

| Aspect | Java Table Function | Java Table Operator |
|--------|---------------------|---------------------|
| Output clause | `RETURNS TABLE (col defs)` | `RETURNS TABLE VARYING USING FUNCTION <contract>` |
| Parameter style | `PARAMETER STYLE JAVA` | `PARAMETER STYLE SQLTABLE` |
| Input | Scalar parameters | Streamed input table (empty parameter list) |
| Output schema | Fixed in the DDL | Defined dynamically by the contract method |
| Java structure | `public static` method | Class implementing `TableOperator` (`contract` + `execute`) |
| AMP execution | All AMPs process the same inputs | Each AMP processes its local partition |
| Partitioning | Not applicable | `HASH BY`, `PARTITION BY`, `LOCAL ORDER BY` |

## The TableOperator Interface

A Java table operator is a public class that implements `com.teradata.fnc.TableOperator`. It has a
public no-argument constructor and two methods.

| Method | Phase | Purpose |
|--------|-------|---------|
| `int contract(RuntimeContract, ResultSet[] rsin, ResultSet[] rsout)` | Plan time | Inspect input columns, define the output schema, return 1 on success |
| `void execute(RuntimeContract, ResultSet[] rsin, ResultSet[] rsout)` | Run time | Read input rows from `rsin`, write output rows to `rsout` |

```java
import java.sql.ResultSet;
import java.sql.SQLException;
import com.teradata.fnc.TableOperator;
import com.teradata.fnc.RuntimeContract;
import com.teradata.fnc.MetaData;
import com.teradata.fnc.ColumnDefinition;
import com.teradata.fnc.TeradataType;
import com.teradata.fnc.UDTBaseInfo;
import com.teradata.fnc.TeradataResultSet;

public class jtblop_udtvals implements TableOperator {

    public jtblop_udtvals() {}

    /* Plan-time: define the output schema from the input columns. */
    public int contract(RuntimeContract contract, ResultSet rsin[], ResultSet rsout[])
        throws SQLException
    {
        int incount = contract.getInputInfo().getIncount();

        /* Count input columns across all input streams. */
        int total_colcount = 0;
        for (int i = 0; i < incount; i++) {
            if (rsin[i] != null) {
                MetaData iCols = ((TeradataResultSet) rsin[i]).getTeradataMetaData();
                total_colcount += iCols.getColumnCount();
            }
        }

        /* Build one output column per input column, preserving type details. */
        ColumnDefinition outCols[] = new ColumnDefinition[total_colcount];
        int ocount = 0;
        for (int j = 0; j < incount; j++) {
            MetaData inCols = ((TeradataResultSet) rsin[j]).getTeradataMetaData();
            for (int i = 0; i < inCols.getColumnCount(); i++) {
                outCols[ocount] = new ColumnDefinition(
                    "O" + ocount, inCols.getTeradataColumnType(i + 1));
                outCols[ocount].setDisplayLength(inCols.getColumnDisplaySize(i + 1));

                TeradataType t = TeradataType.get(inCols.getTeradataColumnType(i + 1));
                switch (t) {
                    case VARCHAR_DT:
                    case CHAR_DT:
                        outCols[ocount].setCharset(inCols.getPrecision(i + 1));
                        break;
                    case DECIMAL1_DT:
                    case DECIMAL2_DT:
                    case DECIMAL4_DT:
                    case DECIMAL8_DT:
                    case DECIMAL16_DT:
                    case NUMBER_DT:
                        outCols[ocount].setPrecision(inCols.getPrecision(i + 1));
                        outCols[ocount].setScale(inCols.getScale(i + 1));
                        break;
                    case ARRAY_DT:
                    case UDT_DT:
                        outCols[ocount].setUdtName(inCols.getUdtTypeName(i + 1));
                        break;
                    default:
                        break;  /* handle TIME, TIMESTAMP, INTERVAL, LOB types as needed */
                }
                outCols[ocount].setPeriodType(inCols.getPeriodType(i + 1));
                ocount++;
            }
        }

        contract.setOutputInfo(0, outCols);  /* stream 0 output schema */
        contract.complete();
        return 1;
    }

    /* Run-time: read input rows from rsin, emit output rows to rsout. */
    public void execute(RuntimeContract contract, ResultSet rsin[], ResultSet rsout[])
        throws SQLException
    {
        /* Read each input row from rsin[], write transformed rows to rsout[]. */
    }
}
```

**Rules:**
- The class must implement `com.teradata.fnc.TableOperator` and have a public no-argument constructor.
- `contract` runs at plan time. It must call `contract.setOutputInfo(streamNo, columns)` then `contract.complete()`, and return 1 on success.
- Cast a `ResultSet` input to `TeradataResultSet` to call `getTeradataMetaData()` for Teradata column types.
- `execute` runs at run time on each AMP. Read from `rsin[]`, write to `rsout[]`.
- Preserve type details (charset, precision, scale, UDT name, period type) when copying input columns to output.

## Procedure: Build the JAR

```bash
javac -cp .:/path/to/terajdbc4.jar:/path/to/tdgssconfig.jar \
      jtblop_udtvals.java

jar cf tblopudt.jar jtblop_udtvals.class
```

## Procedure: Install the JAR

```sql
GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO udf_developer_role;
GRANT EXECUTE PROCEDURE ON SQLJ.REMOVE_JAR  TO udf_developer_role;

DATABASE mydb;
CALL SQLJ.INSTALL_JAR('CJ!/path/to/tblopudt.jar', 'TBLOPUDT_JAR', 0);
```

## Procedure: Register the DDL

```sql
REPLACE FUNCTION mydb.jtblop_udtvals ()
    RETURNS TABLE VARYING USING FUNCTION mydb.jtblop_udtvals_contract
    LANGUAGE JAVA
    NO SQL
    PARAMETER STYLE SQLTABLE
    EXTERNAL NAME 'TBLOPUDT_JAR:jtblop_udtvals.execute';

GRANT EXECUTE FUNCTION ON mydb.jtblop_udtvals TO app_role;
```

### EXTERNAL NAME Format

```
'<JAR_ALIAS>:<class>.execute'
```

The `<JAR_ALIAS>` is the alias from `SQLJ.INSTALL_JAR`. The class implements `TableOperator`. The
method named is `execute`. The contract method is located automatically from the same class, so a
single DDL covers both.

## Procedure: Call the Table Operator

A table operator is named directly in the `FROM` clause. Input arrives through one or more `ON`
clauses (a table, a view, or a query expression). There is no `TABLE OPERATOR` wrapper keyword and
no `TABLE (...)` input wrapper.

```sql
-- Single input, hash-partitioned and locally ordered
SELECT t.*
FROM mydb.jtblop_udtvals (
    ON (SELECT id, value FROM source_table)
    HASH BY id
    LOCAL ORDER BY id
) AS t;

-- Partition by a key column, alias the output columns
SELECT t.region, t.amount
FROM mydb.jtblop_udtvals (
    ON (SELECT region, amount FROM mydb.raw_data)
    PARTITION BY region
    LOCAL ORDER BY amount
) AS t (region, amount);
```

A table operator can take up to 16 `ON` clauses (multiple input streams), and custom name-value
clauses through a `USING` clause:

```sql
SELECT adname, attr_revenue
FROM mydb.attribute_sales (
    ON (SELECT cookie, cart_amt FROM weblog WHERE page = 'thankyou') AS W PARTITION BY cookie
    ON adlog AS S PARTITION BY cookie
    USING clicks(.8) impressions(.2)
) AS D1 (adname, attr_revenue);
```

Caller needs `EXECUTE FUNCTION` on the operator or its containing database.

## Procedure: Verify and Uninstall

```sql
SELECT FunctionName, ExternalName, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'jtblop_udtvals';

SELECT * FROM DBC.FunctionXRefsV
WHERE UDFDatabase = 'mydb' AND UDFName = 'jtblop_udtvals';

DROP FUNCTION mydb.jtblop_udtvals;

CALL SQLJ.REMOVE_JAR('TBLOPUDT_JAR', 0);
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Output schema depends on input | Build `ColumnDefinition[]` in `contract` from the input `MetaData` |
| Multiple input streams | Loop over `getInputInfo().getIncount()`; check each `rsin[i]` for null |
| UDT input column | Use `setUdtName(...)` from `getUdtTypeName(...)`; read UDT metadata with `getUDTMetadata(streamNo)` |
| DECIMAL or NUMBER output | Copy both precision and scale with `setPrecision` and `setScale` |
| Output ResultSet handling | Write rows to `rsout[]` in `execute`; do not close the output stream early |
| JAR already installed | Use `SQLJ.REPLACE_JAR` to update in place, or `REMOVE_JAR` then `INSTALL_JAR` |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="table-operator-udf-java", path="references/FILENAME")` — do NOT call `list`.

- [External UDFs](./references/external-udfs.md): full Java UDF development guide, JAR lifecycle, in-engine JDBC, privilege matrix, EXTERNAL NAME details
- Teradata SQL External Routine Programming, Java Table Operators: https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming/Java-User-Defined-Functions/Table-Operators
