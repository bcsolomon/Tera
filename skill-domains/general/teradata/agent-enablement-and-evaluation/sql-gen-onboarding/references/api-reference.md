# SQL Gen API Endpoint Reference

All endpoints use base path `/sql-gen/api/v1/`.

## Authentication

**Two auth patterns:**

1. **VectorStore endpoints (Section A):** Uses `Authorization: Basic <base64(user:pass)>` header + `session_id` cookie from session creation
2. **SQL Gen endpoints (Section B):** Uses `HTTPBasicAuth(username, password)` from requests library

---

## Section A: VectorStore Management

### A1. Health Check
```
GET /health
```
No parameters. Returns service health status.

### A2. Create Session
```
POST /session
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| database_name | string (body) | Yes | Target database name |

Returns `session_id` cookie. **Must be called before any VectorStore operations.**

### A3. Get Existing Patterns
```
GET /patterns
```
Returns all naming patterns. Requires session cookie.

### A4. Create Naming Pattern
```
POST /patterns/{name}?pattern_string={pattern}
```
Creates a naming pattern for table matching (e.g., `customer360_%_VW`).

### A5. Get Objects for Pattern
```
GET /patterns/{name}
```
Returns tables/views matching the pattern.

### A6. Create VectorStore
```
POST /vectorstores/{vs_name}
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| vs_parameters | JSON string (form) | Yes | `{"embeddings_model": "...", "search_algorithm": "VECTORDISTANCE", "top_k": 10}` |
| vs_index | JSON string (form) | Yes | `{"target_database": "...", "include_patterns": [...]}` |

Runs async. Poll status with A7.

### A7. Get VectorStore Status
```
GET /vectorstores/{vs_name}
```
Poll until status is `READY`.

### A8. Get VectorStore Details
```
GET /vectorstores/{vs_name}?get_details=true
```

### A9. Update VectorStore
```
PATCH /vectorstores/{vs_name}
```
Modify parameters or add/delete tables from an existing VectorStore.

### A10. Delete VectorStore
```
DELETE /vectorstores/{vs_name}
```

### A11. Modify VectorStore Permissions
```
PUT /permissions/{vs_name}
```

### A12. Get VectorStore Permissions
```
GET /permissions/{vs_name}
```

### A13. Get VectorStore Object List
```
GET /vectorstores/{vs_name}?get_object_list=true
```

### A14. List All VectorStores
```
GET /vectorstores
```

### A15. Disconnect Session
```
DELETE /session
```
**Must be called after VectorStore operations are complete.**

---

## Section B: SQL Gen Endpoints

### B1. Upload Files (Synonyms, Taxonomy, AutoTaxonomy)
```
POST /files
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| vectorstore | string | Yes | VectorStore name |
| synonyms_file | file | No | Excel/CSV synonyms file |
| taxonomy_disambiguation_file | file | No | JSON taxonomy disambiguation file |
| autotaxonomy_file | file | No | JSON autotaxonomy file |
| replace_existing | boolean | No | Replace if files exist |

### B2. Run Index Scripts
```
POST /indexing-scripts
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| vectorstore | string | Yes | VectorStore name |

Triggers 3 **MANDATORY** scripts simultaneously: FeatureIndex, FeatureIndexDescription, IndexColumnUniqueness. Runs async — poll with B4.

### B3.1. Run AutoTaxonomy
```
POST /autotaxonomy-script
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| vectorstore | string | Yes | VectorStore name |
| table_pattern | string | Yes | Pattern to match tables (e.g., `customer360_%_VW`) |

OPTIONAL. Runs async — poll with B4.

### B3.2. Download AutoTaxonomy File
```
GET /autotaxonomy-file
```
Downloads the generated JSON for human curation.

### B4. Get SQL Gen Status
```
GET /status
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| vectorstore | string | Yes | VectorStore name |

Tracks 5 scripts: FeatureIndex, FeatureIndexDescription, IndexColumnUniqueness, AutoTaxonomy, InitializeSqlGen.

**Status values:** `RUNNING`, `FAILED`, `SUCCEEDED`, `NEVER TRIGGERED`

### B5. User Profiles

#### B5.1. Upload User Profiles
```
POST /user-profiles
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| user_profiles_file | file | Yes | Excel/CSV user profiles file |
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| vectorstore | string | Yes | VectorStore name |
| replace_existing | boolean | No | Replace existing profiles |

#### B5.2. Delete User Profile
```
DELETE /user-profile
```

#### B5.3. List User Profiles
```
GET /user-profiles
```

#### B5.4. Insert User Profile
```
POST /user-profile
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| username | string | Yes | New username |
| acct_team_member_qlid | string | No | QLID |
| acct_team_member_role_name | string | No | Role name |
| acct_team_member_name | string | No | Member name |

#### B5.5. Update User Profile
```
PUT /user-profile
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hostname, database, username, password | string | Yes | Connection params |
| current_username | string | Yes | Existing username to update |
| new_username | string | No | New username |
| new_acct_team_member_qlid | string | No | New QLID |
| new_acct_team_member_role_name | string | No | New role |
| new_acct_team_member_name | string | No | New name |

### B6. Table Descriptions

#### B6.1. Upload Table Descriptions
```
POST /table-descriptions
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| table_description_file | file | Yes | Excel/CSV with columns: database_name, table_name, table_comment |
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| replace_existing | boolean | No | Replace if comments exist |

**REQUIRED step.** Comments added for one DB at a time.

#### B6.2. Delete Table Descriptions
```
DELETE /table-descriptions
```

#### B6.3. List Table Descriptions
```
GET /table-descriptions
```

### B7. Column Descriptions

#### B7.1. Upload Column Descriptions
```
POST /column-descriptions
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| column_description_file | file | Yes | Excel/CSV with columns: database_name, table_name, column_name, column_comment |
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| replace_existing | boolean | No | Replace if comments exist |

**REQUIRED step.** Comments added for one DB at a time.

#### B7.2. Delete Column Descriptions
```
DELETE /column-descriptions
```

#### B7.3. List Column Descriptions
```
GET /column-descriptions
```

### B8. Acronyms

#### B8.1. Upload Acronyms
```
POST /acronyms
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| acronyms_file | file | Yes | Excel/CSV with columns: acronym, description, vs_name (optional) |
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| replace_existing | boolean | No | Replace existing acronyms |

OPTIONAL.

#### B8.2. Delete Acronyms
```
DELETE /acronyms
```

#### B8.3. List Acronyms
```
GET /acronyms
```

### B9. Initialize SQL Gen
```
POST /sql-gen-initialization
```
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hostname | string | Yes | Database host IP |
| database | string | Yes | Database name |
| username | string | Yes | Admin username |
| password | string | Yes | Admin password |

**REQUIRED — final step.** Runs async. Loads all models and data files. Poll with B4 for `InitializeSqlGen` status.
