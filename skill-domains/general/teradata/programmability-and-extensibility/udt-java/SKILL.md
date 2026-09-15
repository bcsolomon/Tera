---
name: udt-java
description: 'Work with Teradata User-Defined Types (UDTs) from Java external routines. Teradata has no Java User-Defined Methods: methods bound to a type (CREATE METHOD) are C/C++ only, and DISTINCT type cast/ordering/transform is auto-generated. Java participates by writing UDFs or external stored procedures that accept and return UDT parameters. Covers UDT-to-Java mapping (a DISTINCT UDT maps to the Java type of its predefined source type; a STRUCTURED UDT maps to java.sql.Struct via com.teradata.fnc.Struct), reading attributes with Struct.getAttributes(), constructing a Struct result, CREATE TYPE for distinct types, LANGUAGE JAVA PARAMETER STYLE JAVA UDF DDL with UDT params, EXTERNAL NAME object mapping, SYSUDTLIB residence, unsupported types (VARIANT_TYPE, GRAPHIC, ST_Geometry/XML structured attributes), and JAR lifecycle. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user wants a Java UDF or external stored procedure that takes or returns a UDT, asks how a distinct or structured UDT maps to Java, mentions java.sql.Struct, com.teradata.fnc.Struct, Struct.getAttributes, passing a UDT to Java, or asks whether CREATE METHOD LANGUAGE JAVA exists for UDTs.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata UDTs from Java

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

Teradata has **no Java User-Defined Methods**. Methods bound to a type with `CREATE METHOD`
(`INSTANCE`, `CONSTRUCTOR`, and the cast/ordering/transform routines for STRUCTURED types) are
**C/C++ only** (see **udt-c**); for DISTINCT types that functionality is auto-generated. Java
participates with UDTs by writing **UDFs or external stored procedures that accept and return
UDT parameters**.

> **Not this skill:** To create a UDT and its methods in C/C++, see **udt-c**. For a plain Java
> scalar UDF, see **scalar-udf-java**. For a Java XSP, see **stored-procedure-java**.

## When to Use

- Writing a Java UDF or external stored procedure whose parameters or return type is a UDT
- Mapping a **DISTINCT** UDT to the Java type of its predefined source type (for example
  `MYINT AS INTEGER` -> `int`/`Integer`)
- Reading a **STRUCTURED** UDT in Java as a `java.sql.Struct` (`getAttributes()`), or constructing
  one with `com.teradata.fnc.Struct` to return it
- Deciding whether a UDT method can be written in Java (it cannot: `CREATE METHOD` is C/C++ only)
- Determining which UDT shapes are unsupported as Java parameters (XML/ST_Geometry structured
  attributes, `VARIANT_TYPE`, GRAPHIC)

## How UDTs Map to Java

| UDT kind | Java mapping | Notes |
|----------|--------------|-------|
| **DISTINCT** | The Java type of its predefined **source** type | The value is converted to its source type before being passed. Default is simple mapping to a primitive (for example `MYINT AS INTEGER` -> `int`); object mapping (`java.lang.Integer`) is used when the EXTERNAL NAME lists the parameter type. |
| **STRUCTURED** | `java.sql.Struct` | `com.teradata.fnc.Struct` implements `java.sql.Struct`. Read attributes with `getAttributes()` (returns `Object[]`); build a result by constructing a `com.teradata.fnc.Struct`. Object mapping only (no simple map). |

**Restrictions on UDT parameters to Java routines:**
- Structured UDTs with **XML** or **ST_Geometry** attributes cannot be passed.
- LOB attributes are allowed only at the **first** level of nesting.
- `VARIANT_TYPE` and GRAPHIC character-set types are not supported as parameters or returns.

### Simple vs Object Mapping

A DISTINCT UDT supports two mappings, selected by whether the `EXTERNAL NAME` lists the Java
parameter/return classes:

| Mapping | Selected when | Java type | NULL support |
|---------|---------------|-----------|--------------|
| **Simple** (default) | EXTERNAL NAME omits the parameter list | Primitive (`int`, `double`) | Cannot represent SQL NULL |
| **Object** | EXTERNAL NAME lists the class, e.g. `(java.lang.Integer)` | Boxed (`Integer`, `Double`) | `null` = SQL NULL |

STRUCTURED UDTs are always object mapping (`java.sql.Struct`); there is no simple form.

UDTs reside in **SYSUDTLIB**. Grant `UDTUSAGE ON SYSUDTLIB` (or on the specific UDT) to callers.

## Procedure: Create the DISTINCT UDT (language-agnostic)

The type itself is created with plain DDL; no Java is involved, and cast/ordering/transform are
auto-generated:

```sql
CREATE TYPE SYSUDTLIB.myint AS INTEGER FINAL;
```

A STRUCTURED type and its methods are created in C/C++ (see **udt-c**); from Java you only
consume/produce it as a `java.sql.Struct`.

## Procedure: Java UDF That Takes and Returns a DISTINCT UDT

A distinct UDT maps to its source type, so the Java method just uses that primitive (or boxed)
type. With simple mapping (the default) the EXTERNAL NAME omits the parameter list.

```java
import java.sql.SQLException;

public class UserDefinedFunctions {
    /* MYINT maps to int (its INTEGER source type). */
    public static int myScore(int a) throws SQLException {
        return a * 10;
    }
}
```

```sql
REPLACE FUNCTION mydb.my_score (a1 SYSUDTLIB.myint)
RETURNS SYSUDTLIB.myint
LANGUAGE JAVA
NO SQL
PARAMETER STYLE JAVA
EXTERNAL NAME 'UDF_JAR:UserDefinedFunctions.myScore';
```

To allow nulls, use object mapping (boxed types) and list the parameter type in EXTERNAL NAME:
`EXTERNAL NAME 'UDF_JAR:UserDefinedFunctions.myScore(java.lang.Integer) returns java.lang.Integer'`.

## Procedure: Java UDF That Reads a STRUCTURED UDT

A structured UDT maps to `java.sql.Struct`. Read its attributes (in declared order) with
`getAttributes()`. Because the structured mapping is object mapping, list the parameter type in
the EXTERNAL NAME.

```java
import com.teradata.fnc.Struct;
import java.sql.SQLException;

public class CircleFunctions {
    /* circle_t (attribute: radius FLOAT) arrives as a java.sql.Struct. */
    public static Double area(java.sql.Struct circle) throws SQLException {
        if (circle == null) return null;
        Object[] attrs = circle.getAttributes();
        double radius = ((Number) attrs[0]).doubleValue();
        return Math.PI * radius * radius;
    }
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

To **return** a structured UDT, construct a `com.teradata.fnc.Struct` with the attribute values in
declared order and declare the return as `java.sql.Struct` in the EXTERNAL NAME.

## Procedure: Build and Install the JAR

```bash
javac -cp .:/path/to/tdgss/fnc.jar CircleFunctions.java
jar cf circle_jar.jar CircleFunctions.class
```

```sql
DATABASE mydb;
CALL SQLJ.INSTALL_JAR('CJ!udf_src/circle_jar.jar', 'CIRCLE_JAR', 0);

GRANT UDTUSAGE ON SYSUDTLIB TO app_role;
GRANT EXECUTE FUNCTION ON mydb.circle_area TO app_role;
```

## Procedure: Call the Function

```sql
SELECT mydb.circle_area(c) AS area
FROM shapes;   -- c is a column of type SYSUDTLIB.circle_t
```

## Procedure: Verify and Uninstall

```sql
SELECT FunctionName, ExternalName, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'circle_area';

DROP FUNCTION mydb.circle_area;
-- Remove the JAR only when nothing else references it:
DATABASE mydb;
CALL SQLJ.REMOVE_JAR('CIRCLE_JAR', 0);
```

The UDT itself (and any C/C++ methods/cast/ordering/transform) is torn down separately; see
**udt-c** for the `ALTER TYPE ... DROP SPECIFIC METHOD` and `DROP TYPE` order.

## Edge Cases

| Situation | Action |
|-----------|--------|
| "How do I write a Java method on a UDT?" | You cannot. `CREATE METHOD` is C/C++ only; write a Java UDF/XSP that takes the UDT as a parameter, or implement the method in C/C++ (**udt-c**) |
| Need to pass nulls for a distinct UDT | Use object mapping (boxed type) and list the parameter type in EXTERNAL NAME |
| Reading a structured UDT | Map it to `java.sql.Struct`; use `getAttributes()` to read fields in declared order |
| Returning a structured UDT | Construct a `com.teradata.fnc.Struct`; declare the return as `java.sql.Struct` in EXTERNAL NAME |
| Structured UDT with XML/ST_Geometry attribute | Not supported as a Java parameter; pass the needed fields individually |
| VARIANT_TYPE or GRAPHIC parameter | Not supported for Java routines |
| Overloaded Java method | List the full parameter type signature in EXTERNAL NAME |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## Common Errors and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `CREATE METHOD ... LANGUAGE JAVA` is rejected | Java UDMs do not exist; methods bound to a type are C/C++ only | Write a Java UDF/XSP that takes the UDT as a parameter, or implement the method in C/C++ (**udt-c**) |
| `No UDTUSAGE privilege` | Caller lacks usage on the UDT | `GRANT UDTUSAGE ON SYSUDTLIB TO <role>` (or on the specific UDT) |
| `ClassCastException` reading `getAttributes()` | Attribute element cast to the wrong Java type | Cast to the mapped type of each attribute in declared order (for example `((Number) attrs[0]).doubleValue()`) |
| `NullPointerException` for a distinct UDT arg | Simple (primitive) mapping cannot represent a SQL NULL | Use object mapping: list the boxed parameter type in EXTERNAL NAME and null-check it |
| UDT parameter rejected at CREATE FUNCTION | Structured UDT has an XML or ST_Geometry attribute, or type is `VARIANT_TYPE`/GRAPHIC | Not passable to Java; pass the needed scalar fields individually |
| `NoSuchMethodException` / signature mismatch | EXTERNAL NAME parameter classes do not match the Java method | List the exact Java signature, e.g. `(java.sql.Struct) returns java.lang.Double` |
| Attributes read in the wrong order | `getAttributes()` returns attributes in declared order, not name order | Read/build attributes in the type's `CREATE TYPE` declaration order |

## References


> **Access:** `skill_resource_read(action="read", skill="udt-java", path="references/FILENAME")` — do NOT call `list`.

- [UDT Reference](./references/udt-reference.md): DISTINCT vs STRUCTURED comparison, UDT-to-Java mapping, java.sql.Struct usage, why methods are C/C++ only, SYSUDTLIB residence and privileges
