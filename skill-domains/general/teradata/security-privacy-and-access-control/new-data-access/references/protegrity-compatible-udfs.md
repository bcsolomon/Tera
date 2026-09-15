# protegrity compatiule udfs

```sql
-- ============================================================
-- PROTEGRITY-COMPATIBLE SQL UDFs (Teradata)
--
-- Drop-in replacements matching Protegrity function signatures.
-- Uses Teradata built-in functions (HASHROW, LCG, string ops).
--
-- PURPOSE: Dev/demo/test environments without Protegrity installed.
-- NOT for production — these are NOT cryptographically equivalent
-- to Protegrity's AES-FF1/FF3 format-preserving encryption.
--
-- USAGE: Deploy to a utility database, then reference in views:
--   SELECT <db>.prot_fp_encrypt_int(id) AS id_token, ...
--
-- SIGNATURES MATCHED:
--   prot_fp_encrypt_int(INTEGER)       → INTEGER
--   prot_fp_decrypt_int(INTEGER)       → INTEGER
--   prot_fp_encrypt_varchar(VARCHAR)   → VARCHAR(64)
--   prot_tokenize_varchar(VARCHAR)     → VARCHAR(64)
--   prot_tokenize_int(INTEGER)         → INTEGER
--   prot_mask_varchar(VARCHAR)         → VARCHAR(4000)
--   prot_mask_int(INTEGER)             → INTEGER
-- ============================================================

-- ------------------------------------------------------------
-- 1. prot_fp_encrypt_int(INTEGER) RETURNS INTEGER
--    Format-preserving "encryption" for integers.
--    LCG-based — deterministic, reversible via decrypt counterpart.
-- ------------------------------------------------------------
REPLACE FUNCTION ${TARGET_DB}.prot_fp_encrypt_int(input_val INTEGER)
RETURNS INTEGER
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
RETURN (input_val * 6364136223846793005 + 1442695040888963407) MOD 2147483647;

-- ------------------------------------------------------------
-- 2. prot_fp_decrypt_int(INTEGER) RETURNS INTEGER
--    Reverse of the LCG transform above.
--    Uses modular multiplicative inverse.
-- ------------------------------------------------------------
REPLACE FUNCTION ${TARGET_DB}.prot_fp_decrypt_int(input_val INTEGER)
RETURNS INTEGER
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
RETURN ((input_val - 1442695040888963407) * 3039061438261498677) MOD 2147483647;

-- ------------------------------------------------------------
-- 3. prot_fp_encrypt_varchar(VARCHAR(4000)) RETURNS VARCHAR(64)
--    Format-preserving "encryption" for strings.
--    Returns a deterministic hex token via HASHROW.
--    Not reversible — use tokenize semantics.
-- ------------------------------------------------------------
REPLACE FUNCTION ${TARGET_DB}.prot_fp_encrypt_varchar(input_val VARCHAR(4000))
RETURNS VARCHAR(64)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
RETURN SUBSTR(TO_CHAR(HASHROW(input_val), 'XXXXXXXXXXXXXXXX'), 1, 16);

-- ------------------------------------------------------------
-- 4. prot_tokenize_varchar(VARCHAR(4000)) RETURNS VARCHAR(64)
--    Tokenization — replaces value with a deterministic opaque token.
--    Prefixed with 'TKN-' for easy identification.
-- ------------------------------------------------------------
REPLACE FUNCTION ${TARGET_DB}.prot_tokenize_varchar(input_val VARCHAR(4000))
RETURNS VARCHAR(64)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
RETURN 'TKN-' || SUBSTR(TO_CHAR(HASHROW(input_val), 'XXXXXXXXXXXXXXXX'), 1, 12);

-- ------------------------------------------------------------
-- 5. prot_tokenize_int(INTEGER) RETURNS INTEGER
--    Tokenization for integers — deterministic, non-reversible.
--    Knuth multiplicative hash.
-- ------------------------------------------------------------
REPLACE FUNCTION ${TARGET_DB}.prot_tokenize_int(input_val INTEGER)
RETURNS INTEGER
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
RETURN ABS(MOD(input_val * 2654435761, 2147483647));

-- ------------------------------------------------------------
-- 6. prot_mask_varchar(VARCHAR(4000)) RETURNS VARCHAR(4000)
--    Masking — preserves first and last character, masks middle.
--    Example: 'Johnson' → 'J*****n'
-- ------------------------------------------------------------
REPLACE FUNCTION ${TARGET_DB}.prot_mask_varchar(input_val VARCHAR(4000))
RETURNS VARCHAR(4000)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
RETURN CASE
  WHEN CHARACTER_LENGTH(TRIM(input_val)) <= 2
    THEN REPEAT('*', CHARACTER_LENGTH(TRIM(input_val)))
  ELSE SUBSTR(input_val, 1, 1)
    || REPEAT('*', CHARACTER_LENGTH(TRIM(input_val)) - 2)
    || SUBSTR(TRIM(input_val), CHARACTER_LENGTH(TRIM(input_val)), 1)
  END;

-- ------------------------------------------------------------
-- 7. prot_mask_int(INTEGER) RETURNS INTEGER
--    Masking for integers — replaces all digits with 9.
--    Example: 12345 → 99999
-- ------------------------------------------------------------
REPLACE FUNCTION ${TARGET_DB}.prot_mask_int(input_val INTEGER)
RETURNS INTEGER
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
RETURN CAST(REPEAT('9', CHARACTER_LENGTH(TRIM(CAST(ABS(input_val) AS VARCHAR(20))))) AS INTEGER);

-- ============================================================
-- DEPLOYMENT EXAMPLE
-- Replace ${TARGET_DB} with actual database name before running:
--
--   sed 's/${TARGET_DB}/my_utility_db/g' protegrity-compatible-udfs.sql
--
-- COMPATIBILITY MATRIX
-- ┌───────────────────────────┬──────────────────┬────────────────┐
-- │ Protegrity Function       │ This UDF         │ Reversible?    │
-- ├───────────────────────────┼──────────────────┼────────────────┤
-- │ prot_fp_encrypt_int       │ LCG transform    │ Yes (decrypt)  │
-- │ prot_fp_decrypt_int       │ LCG inverse      │ N/A            │
-- │ prot_fp_encrypt_varchar   │ HASHROW hex      │ No             │
-- │ prot_tokenize_varchar     │ HASHROW + prefix │ No             │
-- │ prot_tokenize_int         │ Knuth hash       │ No             │
-- │ prot_mask_varchar         │ First/last + '*' │ No             │
-- │ prot_mask_int             │ All → 9s         │ No             │
-- └───────────────────────────┴──────────────────┴────────────────┘
-- ============================================================
```
