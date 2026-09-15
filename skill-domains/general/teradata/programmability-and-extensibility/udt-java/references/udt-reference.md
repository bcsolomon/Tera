# UDT-from-Java Reference - Teradata SQL External Routine Programming (v20.00)

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** UDT-from-Java Reference - Teradata SQL External Routine Programming (v20.00)

Sources:
- https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming/SQL-Data-Type-Mapping/Java-Data-Types
- https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Data-Definition-Language-Syntax-and-Examples/User-Defined-Type-Statements
- https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Data-Definition-Language-Syntax-and-Examples/User-Defined-Method-Statements

---

## 1. Key Rule: UDTs and UDMs Are C/C++ Only

Teradata User-Defined Types and the User-Defined Methods bound to them (`CREATE METHOD`,
including instance, constructor, and the cast/ordering/transform routines for structured types)
are implemented in **C or C++ only**. There is **no `LANGUAGE JAVA` UDM** and no Java-backed
UDT method. See **udt-c** for creating types and methods.

Java works with UDTs only by writing **UDFs or external stored procedures that accept and return
UDT parameters**. The type must already exist (created via DDL, with C/C++ methods or, for
distinct types, auto-generated cast/ordering/transform functionality).

UDTs reside in the **SYSUDTLIB** database. Callers need `UDTUSAGE` on SYSUDTLIB (or on the
specific UDT); definers need `UDTTYPE`/`UDTMETHOD` on SYSUDTLIB.

---

## 2. UDT-to-Java Parameter Mapping

| UDT kind | Java mapping | Details |
|----------|--------------|---------|
| DISTINCT | The Java type of its predefined **source** type | The value is converted to its source type before being passed to the Java routine. Default is simple mapping to a primitive; object mapping (boxed type) is used when the EXTERNAL NAME lists the parameter type, which also allows nulls. |
| STRUCTURED | `java.sql.Struct` | Object mapping only (no simple map). `com.teradata.fnc.Struct` implements `java.sql.Struct`. |

When a distinct UDT is itself a structured-UDT attribute or an Array element, it is object-mapped
to the corresponding Java type.

### Restrictions

- Structured UDTs with **XML** or **ST_Geometry** attributes cannot be passed to Java UDFs or XSPs.
- LOB attributes are allowed only at the **first** level of nesting.
- `VARIANT_TYPE`, and GRAPHIC character-set character types, are not supported as parameters or
  returns of Java routines.

---

## 3. DISTINCT UDT From Java

```sql
CREATE TYPE SYSUDTLIB.myint AS INTEGER FINAL;

REPLACE FUNCTION mydb.my_score (a1 SYSUDTLIB.myint)
RETURNS SYSUDTLIB.myint
LANGUAGE JAVA
NO SQL
PARAMETER STYLE JAVA
EXTERNAL NAME 'UDF_JAR:UserDefinedFunctions.myScore';
```

```java
/* MYINT maps to int (its INTEGER source type) under simple mapping. */
public static int myScore(int a) throws SQLException { return a * 10; }
```

For nullable values use object mapping and list the type in EXTERNAL NAME:
`'UDF_JAR:UserDefinedFunctions.myScore(java.lang.Integer) returns java.lang.Integer'`.

---

## 4. STRUCTURED UDT From Java (java.sql.Struct)

Read attributes (in declared order) with `getAttributes()`. Build a result by constructing a
`com.teradata.fnc.Struct`. Structured mapping is object mapping, so list the parameter type in
the EXTERNAL NAME.

```java
import com.teradata.fnc.Struct;

public static Double area(java.sql.Struct circle) throws SQLException {
    if (circle == null) return null;
    Object[] attrs = circle.getAttributes();      // {radius}
    double radius = ((Number) attrs[0]).doubleValue();
    return Math.PI * radius * radius;
}
```

```sql
REPLACE FUNCTION mydb.circle_area (c SYSUDTLIB.circle_t)
RETURNS FLOAT
LANGUAGE JAVA
NO SQL
PARAMETER STYLE JAVA
EXTERNAL NAME 'CIRCLE_JAR:CircleFunctions.area(java.sql.Struct) returns java.lang.Double';
```

Period, TIME/TIMESTAMP WITH TIME ZONE, and structured UDTs all surface to Java as
`java.sql.Struct`; their nested elements follow the documented Struct layout.

---

## 5. JAR Lifecycle

```sql
DATABASE mydb;
CALL SQLJ.INSTALL_JAR('CJ!udf_src/circle_jar.jar', 'CIRCLE_JAR', 0);
-- Replace in place:
CALL SQLJ.REPLACE_JAR('CJ!udf_src/circle_jar_v2.jar', 'CIRCLE_JAR');
-- Remove when no routine references it:
CALL SQLJ.REMOVE_JAR('CIRCLE_JAR', 0);
```

The type itself, plus any C/C++ methods/cast/ordering/transform, is created and dropped
separately; see **udt-c** for `ALTER TYPE ... DROP SPECIFIC METHOD` and the `DROP TYPE` order.

---

## 6. Related DDL Views

| View | Purpose |
|------|---------|
| `DBC.TypesV` | Registered UDTs (in SYSUDTLIB) |
| `DBC.FunctionsV` | Java UDFs/XSPs, plus methods and cast/ordering/transform routines |
| `DBC.ColumnsV` | Find tables with UDT columns |

---

*Reference: Teradata SQL External Routine Programming and SQL Data Definition Language, v20.00*
