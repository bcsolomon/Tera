# Scalar C UDF Examples

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Scalar C UDF Examples

Complete, tested examples for common data types and patterns. Each example includes the C source, SQL registration, and test queries.

## Example 1: Integer Arithmetic — double_value

Doubles an integer input, returning NULL for NULL input.

### C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

void double_value(
    INTEGER       *input_val,
    INTEGER       *result,
    int           *input_val_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*input_val_null == -1) {
        *result_null = -1;
        return;
    }
    *result = *input_val * 2;
    *result_null = 0;
}
```

### SQL Registration

```sql
CREATE FUNCTION mydb.double_value (input_val INTEGER)
RETURNS INTEGER
LANGUAGE C NO SQL DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!double_value!double_value.c'
PARAMETER STYLE SQL;
```

### Test Queries

```sql
SELECT mydb.double_value(5);      -- 10
SELECT mydb.double_value(0);      -- 0
SELECT mydb.double_value(-3);     -- -6
SELECT mydb.double_value(NULL);   -- NULL
```

---

## Example 2: Float Division with Error Reporting — safe_divide

Divides two floats. Returns NULL for NULL inputs. Signals an error on division by zero using `sqlstate` and `error_msg`.

### C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"
#include <string.h>

void safe_divide(
    FLOAT         *numerator,
    FLOAT         *denominator,
    FLOAT         *result,
    int           *numerator_null,
    int           *denominator_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*numerator_null == -1 || *denominator_null == -1) {
        *result_null = -1;
        return;
    }
    if (*denominator == 0.0) {
        strcpy(sqlstate, "U0001");
        strcpy(error_msg, "Division by zero");
        return;
    }
    *result = *numerator / *denominator;
    *result_null = 0;
}
```

### SQL Registration

```sql
CREATE FUNCTION mydb.safe_divide (num FLOAT, den FLOAT)
RETURNS FLOAT
LANGUAGE C NO SQL DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!safe_divide!safe_divide.c'
PARAMETER STYLE SQL;
```

### Test Queries

```sql
SELECT mydb.safe_divide(10.0, 3.0);    -- 3.333...
SELECT mydb.safe_divide(10.0, 0.0);    -- Error: Division by zero
SELECT mydb.safe_divide(NULL, 5.0);    -- NULL
```

---

## Example 3: String Transformation — upper_name

Converts a VARCHAR to uppercase.

### C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"
#include <ctype.h>

void upper_name(
    VARCHAR_LATIN *input,
    VARCHAR_LATIN *result,
    int           *input_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*input_null == -1) {
        *result_null = -1;
        return;
    }

    int i;
    for (i = 0; input[i] != '\0'; i++) {
        result[i] = toupper((unsigned char)input[i]);
    }
    result[i] = '\0';
    *result_null = 0;
}
```

### SQL Registration

```sql
CREATE FUNCTION mydb.upper_name (input VARCHAR(200))
RETURNS VARCHAR(200)
LANGUAGE C NO SQL DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!upper_name!upper_name.c'
PARAMETER STYLE SQL;
```

### Test Queries

```sql
SELECT mydb.upper_name('hello world');   -- 'HELLO WORLD'
SELECT mydb.upper_name('Test 123');      -- 'TEST 123'
SELECT mydb.upper_name(NULL);            -- NULL
```

---

## Example 4: Date Manipulation — days_until_year_end

Calculates the number of days remaining until the end of the year for a given DATE.

### C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

/* Days in each month (non-leap) */
static int days_in_month[] = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};

static int is_leap_year(int year) {
    return (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
}

static int day_of_year(int year, int month, int day) {
    int doy = 0;
    int i;
    for (i = 1; i < month; i++) {
        doy += days_in_month[i];
        if (i == 2 && is_leap_year(year)) doy++;
    }
    return doy + day;
}

void days_until_year_end(
    DATE          *input_date,
    INTEGER       *result,
    int           *input_date_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*input_date_null == -1) {
        *result_null = -1;
        return;
    }

    int year  = (*input_date / 10000) + 1900;
    int month = (*input_date % 10000) / 100;
    int day   = *input_date % 100;

    int total_days = is_leap_year(year) ? 366 : 365;
    int current_doy = day_of_year(year, month, day);

    *result = total_days - current_doy;
    *result_null = 0;
}
```

### SQL Registration

```sql
CREATE FUNCTION mydb.days_until_year_end (input_date DATE)
RETURNS INTEGER
LANGUAGE C NO SQL DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!days_until_year_end!days_until_year_end.c'
PARAMETER STYLE SQL;
```

### Test Queries

```sql
SELECT mydb.days_until_year_end(DATE '2026-01-01');   -- 364
SELECT mydb.days_until_year_end(DATE '2026-12-31');   -- 0
SELECT mydb.days_until_year_end(DATE '2024-02-29');   -- 306 (leap year)
SELECT mydb.days_until_year_end(NULL);                -- NULL
```

---

## Example 5: Multi-Parameter String Builder — format_full_name

Concatenates first, middle, and last names with selective NULL handling.

### C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"
#include <string.h>
#include <stdio.h>

void format_full_name(
    VARCHAR_LATIN *first_name,
    VARCHAR_LATIN *middle_name,
    VARCHAR_LATIN *last_name,
    VARCHAR_LATIN *result,
    int           *first_null,
    int           *middle_null,
    int           *last_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    /* First and last name are required */
    if (*first_null == -1 || *last_null == -1) {
        *result_null = -1;
        return;
    }

    if (*middle_null == -1) {
        sprintf(result, "%s %s", first_name, last_name);
    } else {
        sprintf(result, "%s %s %s", first_name, middle_name, last_name);
    }
    *result_null = 0;
}
```

### SQL Registration

```sql
CREATE FUNCTION mydb.format_full_name (
    first_name  VARCHAR(50),
    middle_name VARCHAR(50),
    last_name   VARCHAR(50)
)
RETURNS VARCHAR(160)
LANGUAGE C NO SQL DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!format_full_name!format_full_name.c'
PARAMETER STYLE SQL;
```

### Test Queries

```sql
SELECT mydb.format_full_name('John', 'Michael', 'Smith');  -- 'John Michael Smith'
SELECT mydb.format_full_name('Jane', NULL, 'Doe');         -- 'Jane Doe'
SELECT mydb.format_full_name(NULL, NULL, 'Doe');           -- NULL
```

---

## Example 6: Decimal Handling — percent_of_total

Computes a percentage from DECIMAL values.

### C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"
#include <string.h>

/*
 * percent_of_total: (part / total) * 100
 * SQL types: DECIMAL(10,2) inputs, FLOAT result
 * DECIMAL(10,2) maps to DECIMAL8 in C (precision 10–18)
 */
void percent_of_total(
    DECIMAL8      *part,
    DECIMAL8      *total,
    FLOAT         *result,
    int           *part_null,
    int           *total_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*part_null == -1 || *total_null == -1) {
        *result_null = -1;
        return;
    }

    /* DECIMAL(10,2) has scale=2, so stored value = actual * 100 */
    double part_val  = (double)(*(long long *)part);
    double total_val = (double)(*(long long *)total);

    if (total_val == 0.0) {
        strcpy(sqlstate, "U0002");
        strcpy(error_msg, "Total cannot be zero");
        return;
    }

    *result = (part_val / total_val) * 100.0;
    *result_null = 0;
}
```

### SQL Registration

```sql
CREATE FUNCTION mydb.percent_of_total (
    part  DECIMAL(10,2),
    total DECIMAL(10,2)
)
RETURNS FLOAT
LANGUAGE C NO SQL DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!percent_of_total!percent_of_total.c'
PARAMETER STYLE SQL;
```

### Test Queries

```sql
SELECT mydb.percent_of_total(25.00, 100.00);   -- 25.0
SELECT mydb.percent_of_total(1.00, 3.00);      -- 33.333...
SELECT mydb.percent_of_total(50.00, 0.00);     -- Error: Total cannot be zero
```
