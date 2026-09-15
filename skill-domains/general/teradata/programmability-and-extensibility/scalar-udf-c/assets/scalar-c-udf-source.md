# Scalar C UDF Source Template

```c
/*
 * Teradata Scalar C UDF — C Source Template
 * Replace placeholders marked with <angle_brackets>
 *
 * SQL Registration:
 *   CREATE FUNCTION <database_name>.<function_name> (
 *       <param1_name> <param1_sql_type>,
 *       <param2_name> <param2_sql_type>
 *   )
 *   RETURNS <return_sql_type>
 *   LANGUAGE C NO SQL DETERMINISTIC
 *   CALLED ON NULL INPUT
 *   EXTERNAL NAME 'CS!<function_name>!<function_name>.c'
 *   PARAMETER STYLE SQL;
 */

#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

void <function_name>(
    /* Input parameters — one per SQL parameter */
    <PARAM1_C_TYPE>  *<param1_name>,
    <PARAM2_C_TYPE>  *<param2_name>,

    /* Result — matches RETURNS type */
    <RESULT_C_TYPE>  *result,

    /* Null indicators — one per input + result */
    int              *<param1_name>_null,
    int              *<param2_name>_null,
    int              *result_null,

    /* Trailing metadata — always present */
    char              sqlstate[6],
    SQL_TEXT          extname[129],
    SQL_TEXT          specific_name[129],
    SQL_TEXT          error_msg[257])
{
    /* Step 1: Check for NULL inputs */
    if (*<param1_name>_null == -1 || *<param2_name>_null == -1) {
        *result_null = -1;
        return;
    }

    /* Step 2: Validate inputs (optional) */
    /* if (<invalid condition>) {
           strcpy(sqlstate, "U0001");
           strcpy(error_msg, "Description of the problem");
           return;
       } */

    /* Step 3: Compute result */
    *result = /* your computation here */;
    *result_null = 0;
}
```
