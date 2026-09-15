# Protection Strategy Reference — New Data Access Skill

This reference provides detailed guidance on column-level protection strategies
for the sensitivity assessment and access design steps.

## Protection Approaches

### 1. Column Exclusion (Recommended Default for Critical/High PII)

Remove the column entirely from the view's SELECT list.

**When to use:**
- Column contains data that no consumer in this role needs (e.g., SSN for analysts)
- Simplest and most secure option
- No risk of data leakage through masking weaknesses

**Teradata implementation:**
```sql
CREATE VIEW db.v_customer_safe AS
  SELECT CustomerId, FirstName, LastName, City, State, ZipCode
  -- SSN, Email, Phone, StreetAddress excluded
  FROM db.Customer;
```

### 2. Column Masking (When Partial Data Is Needed)

Replace sensitive values with a transformed version that preserves utility.

**When to use:**
- Consumer needs a reference but not the full value (e.g., last 4 of card number)
- Masking preserves the column's presence for application compatibility

**Common masking patterns in Teradata:**

| Pattern | Expression | Example Output |
|---------|-----------|---------------|
| Last 4 digits | `'****-****-****-' \|\| SUBSTR(CardNumber, -4)` | `****-****-****-1111` |
| First initial + asterisks | `SUBSTR(FirstName, 1, 1) \|\| '****'` | `J****` |
| Hash (irreversible) | `HASHBUCKET(HASHROW(SSN))` | `12847` |
| Date to year only | `EXTRACT(YEAR FROM DateOfBirth)` | `1985` |
| Email domain only | `'****@' \|\| SUBSTR(Email, INDEX(Email, '@') + 1)` | `****@email.com` |

**Teradata implementation:**
```sql
CREATE VIEW db.v_card_masked AS
  SELECT CardId, CustomerId, CardType,
         '****-****-****-' || SUBSTR(CardNumber, -4) AS CardNumberMasked,
         CreditLimit, CurrentBalance, IsActive, IssueDate
         -- CVV excluded entirely, ExpiryMonth/ExpiryYear excluded (PCI combo risk)
  FROM db.Credit_Card;
```

### 3. Row-Level Filtering (Restrict Which Rows Are Visible)

Apply a WHERE clause to limit the rows a role can access.

**When to use:**
- Role should only see data for their branch, region, department, or customer segment
- Row-level security without the complexity of Teradata's built-in RLS policies

**Teradata implementation:**
```sql
CREATE VIEW db.v_branch_customers AS
  SELECT CustomerId, FirstName, LastName, City, State, ZipCode,
         AccountOpenDate, BranchId, CustomerTier
  FROM db.Customer
  WHERE BranchId = 1;  -- Dallas branch only
```

### 4. Full Access (Direct Table Grant)

Grant SELECT directly on the base table without any view intermediary.

**When to use:**
- Role has a legitimate, documented need for all columns and all rows
- Typically: compliance auditors, DBA roles, data stewards
- Must be explicitly justified and documented in the audit log

**Teradata implementation:**
```sql
GRANT SELECT ON db.Customer TO compliance_auditor;
GRANT SELECT ON db.Credit_Card TO compliance_auditor;
```

## PCI Combination Risk — Detailed Guidance

### What Is Combination Risk?

Individual columns that are classified as Low sensitivity can become High or
Critical when exposed together in the same view or query result. This is
particularly relevant for PCI DSS compliance.

### Known Dangerous Combinations

| Columns | Risk Level | Why |
|---------|-----------|-----|
| CardType + ExpiryMonth + ExpiryYear | High | Combined with transaction amounts, significantly narrows card identification |
| ZipCode + DateOfBirth | High | Can uniquely identify ~87% of US individuals (Sweeney, 2000) |
| ZipCode + DateOfBirth + Gender | Critical | Can uniquely identify ~99% of US individuals |
| FirstName + LastName + City | High | Enough for identity resolution in most populations |
| AccountId + Amount + Timestamp | Medium | Transaction fingerprinting enables re-identification |
| CardNumber (last 4) + ExpiryMonth + ExpiryYear | High | Partial card + expiry can identify many cards |

### Mitigation Strategies

1. **Exclude one quasi-identifier from each dangerous group** — e.g., keep ZipCode
   but exclude DateOfBirth, or vice versa.
2. **Generalize values** — e.g., use birth year instead of full date, or 3-digit
   zip prefix instead of full zip code.
3. **Add row-level restrictions** — reduce the row count to make re-identification
   harder (k-anonymity principle: ensure each combination matches at least k rows).
4. **Separate into different views** — put quasi-identifiers in different views
   so they can't be trivially joined.

### PCI DSS Requirements (Summary)

- **PCI DSS Requirement 3.4:** Render PAN (Primary Account Number) unreadable
  anywhere it is stored. Masking to first 6 / last 4 is acceptable for display.
- **PCI DSS Requirement 3.2:** Do not store CVV/CVC2 after authorization — ever.
  This means CVV should never appear in views, exports, or test data.
- **PCI DSS Requirement 7.1:** Limit access to cardholder data to only those
  individuals whose job requires such access (least privilege).

## Encryption Considerations (Future Reference)

The UJM design document describes column-level encryption using partner UDFs
(e.g., Protegrity) with centralized key management. This is not implemented in
the current skill version but may be added in the future.

Key principles for when encryption is added:
- **Encrypt at rest immediately** — staging tables should never contain unencrypted
  sensitive data, even temporarily.
- **Decryption happens in-flight** — encrypted columns are decrypted inside view
  definitions using UDF calls, so the base table always stores ciphertext.
- **Key management is separate** — encryption keys are managed by the partner
  platform (Protegrity), not by Teradata roles/grants.
- **Hash functions as testing alternative** — when Protegrity is not available,
  use `HASHBUCKET(HASHROW(column))` as a simple irreversible hash for testing
  the workflow without real encryption infrastructure.
