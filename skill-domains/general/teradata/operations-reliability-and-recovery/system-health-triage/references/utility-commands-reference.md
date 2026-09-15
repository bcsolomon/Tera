# Teradata System Administration — Utility Commands Reference

> Source: 541-0007106-C03 (Data Recovery Using Teradata Table Rebuild)

> See also: [crash-dump-reference.md](crash-dump-reference.md) — ctl debug screen, csp crash dump save, crashdumps DB setup, pcl multi-node commands, dump verification, offload/upload

---

## Table of Contents

1. [checktable Utility](#1-checktable-utility)
2. [vprocmanager Utility](#2-vprocmanager-utility)
3. [rcvmanager Utility](#3-rcvmanager-utility)
4. [rebuild (Table Rebuild) Utility](#4-rebuild-table-rebuild-utility)
5. [cnsrun / cnstool — Scripting Utilities](#5-cnsrun--cnstool--scripting-utilities)
6. [Recovery Concepts](#6-recovery-concepts)
7. [Data Recovery Decision Tree](#7-data-recovery-decision-tree)

---

## 1. checktable Utility

**Purpose:** Finds inconsistencies and data corruption in internal data structures of a specified table (missing/bad table headers, missing rows, missing data blocks, etc.). Runs under CNS.

### Syntax

```
CHECK <dbname>.<tablename> AT LEVEL <level> [ERROR ONLY] [WITH NO ERROR LIMIT];
CHECK <dbname> AT LEVEL <level> [ERROR ONLY];
CHECK ALL TABLES AT LEVEL <level> [ERROR ONLY];
```

### Check Levels

| Level | Description |
|-------|-------------|
| `LEVEL ONE` | Basic check — table header existence |
| `LEVEL TWO` | Moderate — primary/fallback data row consistency, index consistency |
| `LEVEL THREE` | Full — includes data block integrity checks, detects bad data blocks (error 5148) |

### Key Options

- `ERROR ONLY` — Only report tables with errors (skip "No errors" output)
- `WITH NO ERROR LIMIT` — Override the default 20-errors-per-table limit; report all errors. The error file path is displayed at completion.

### Error Output Format

Checktable reports include:
- Error code number
- Description of the error
- AMP number where the error was found
- Subtable ID (hex) and row IDs (hex) for the affected rows
- Error file path: `/var/opt/teradata/tdtemp/CheckTableErrors<timestamp>`

### Common Error Codes and Remediation

| Error Code | Description | Remediation |
|------------|-------------|-------------|
| **2741** | Table header not found (missing table header) | `REBUILD AMP <n> <db>.<tbl> TABLE HEADER;` |
| **2756** | Fallback data row is missing | `REBUILD AMP <n> <db>.<tbl> SUBTABLE <id> ROWRANGE <start> <end>;` or `REBUILD AMP <n> <db>.<tbl> FALLBACK DATA;` |
| **2764** | Data row not indexed by USI | `REBUILD AMP <n> <db>.<tbl> PRIMARY DATA;` |
| **2767** | Primary USI row is missing | `REBUILD AMP <n> <db>.<tbl> SUBTABLE <id> ROWRANGE <start> <end>;` |
| **2772** | NUSI row indexes non-existent data row | `REBUILD AMP <n> <db>.<tbl> PRIMARY DATA;` or `REBUILD AMP <n> <db>.<tbl> ALL DATA;` |
| **5148** | Bad data block detected — Run SCANDISK | `REBUILD AMP <n> <db>.<tbl> SUBTABLE <id> ROWRANGE <start> <end> AUTOADJUSTBLOCKS;` |
| **7495** | Table check skipped due to error 5148 — Run SCANDISK | Run `scandisk`, then surgical rebuild |
| **7530** | LOB row references a non-existent data row | Rebuild the affected row range |

### Examples

```
-- Check a single table at level two
check mloaddb.t1 at level two;

-- Check all tables in a database
check TRSINGLEDB at level two;

-- Check all tables, errors only
check all tables at level two error only;

-- Check with no error limit (get all errors, not just first 20)
check tr_surgicaldb.testtable at level three with no error limit;
```

### Key Rules

- Always run checktable **after** any rebuild operation to verify data integrity.
- Checktable defaults to **concurrent mode** on a non-quiescent system.
- Default limit is **20 errors per table**; use `WITH NO ERROR LIMIT` for full error listing.
- When error 5148 is reported, you must also run **scandisk** to get subtable ID and data block details.
- The error file can be viewed to get complete row ID listings for surgical rebuild row ranges.

---

## 2. vprocmanager Utility

**Purpose:** Manages AMP VPROC states, issues restarts, boots AMPs for rebuild, and displays configuration/cluster information. Runs from the command line or under CNS.

### Starting vprocmanager

```bash
# From command line
vprocmanager

# From CNS
6:start vprocmanager
```

### Commands

| Command | Description |
|---------|-------------|
| `status not` | Show status of all VPROCs that are NOT fully online |
| `status <amp#>` | Show status of a specific AMP VPROC |
| `status` | Show full status of all VPROCs |
| `set <amp#> = offline` | Set an AMP to OFFLINE state |
| `set <amp#> = fatal` | Set an AMP to FATAL state |
| `set <amp#> = online` | Set an AMP to ONLINE state (triggers recovery) |
| `set <amp1>,<amp2>,<ampN> fatal` | Set multiple AMPs to FATAL |
| `set <amp1>,<amp2>,<ampN> online` | Set multiple AMPs to ONLINE |
| `boot <amp#>` or `bo <amp#>` | Boot a FATAL AMP to prepare it for Full-AMP Rebuild. Changes state from FATAL/Down to UTILITY/Down |
| `restart nodump coldwait` | Restart the database, wait for all recovery to complete before coming fully up. No dump is taken. |
| `quit` | Exit vprocmanager |

### AMP State Transitions

```
                  set offline              set online
ONLINE ──────────► OFFLINE ──────────────► ONLINE (recovery starts)
   │                  │                        ▲
   │ set fatal        │ restart                │ set online
   ▼                  ▼                        │
 FATAL ──── boot ──► UTILITY ──(rebuild)──► OFFLINE ──► ONLINE
 (Down)              (Down)                 (Down)      (recovery)
```

| State | Config Status | Meaning |
|-------|--------------|---------|
| Online | Online | Normal operation |
| Offline | Down | AMP is down, OJs/CJs accumulating, fallback access active |
| Fatal | Down | AMP had a fatal error, must be booted before Full-AMP Rebuild |
| Utility | Down | AMP has been booted and is ready for Full-AMP Rebuild |

### Determining Cluster Membership

The DBS Logical Configuration display from vprocmanager shows which AMPs belong to which cluster. This is critical for:
- Knowing which AMPs can be rebuilt simultaneously (only one per cluster at a time)
- Planning Many Full-AMP Rebuilds (pick one AMP from each affected cluster)

**Rule:** Only one AMP per cluster can be down at any time for data to remain accessible.

### Coldwait Restart

```
restart nodump coldwait
```

- Keeps the system down until **all recovery (OJ/CJ processing) is complete** before accepting logons.
- Should be issued after rebuild completes and AMPs are set online.
- Without `coldwait`, the system comes up while AMPs are still in recovery (catchup).

---

## 3. rcvmanager Utility

**Purpose:** Monitors AMP VPROC recovery status — shows OJ/CJ counts, recovery progress, and pass status. Runs under CNS.

### Commands

| Command | Description |
|---------|-------------|
| `list status;` | Summary of recovery statistics for all down AMP VPROCs |
| `list status <amp#>;` | Detailed status for a specific AMP: number of tables to recover, byte counts, OJ/CJ counts |
| `rebuild priority` | Check current rebuild priority |
| `recovery priority` | Check current recovery priority |

### Key Output Elements

- **Current Pass** — OJs/CJs being actively processed
- **Next Pass** — OJs/CJs that accumulated while Current Pass is being processed
- A `*` next to the AMP listing indicates recovery is complete and a coldwait restart can proceed
- Byte counts help estimate remaining recovery time

### OJ vs CJ

| Journal Type | Tracks | Description |
|-------------|--------|-------------|
| **OJ** (Ordered System Change Journal) | DDL changes | CREATE TABLE, ALTER TABLE, etc. during AMP outage |
| **CJ** (Changed Row Journal) | DML changes | INSERT, UPDATE, DELETE, etc. during AMP outage |

When a Full-AMP Rebuild starts, it **deletes all OJs and CJs** for that AMP. If users continue work during rebuild, new OJs/CJs accumulate in the "Next Pass."

---

## 4. rebuild (Table Rebuild) Utility

**Purpose:** Recovers data on a failed or corrupted AMP by copying from fallback copies on other AMPs in the same cluster. Runs under CNS.

### Full Syntax (from rebuild banner)

```
                     {ALL TABLES   } {ALL     }
REBUILD AMP nnnn     {dbname       } {PRIMARY } DATA [, Options] ;
                     {dbname.tname } {FALLBACK}

REBUILD AMP nnnn FALLBACK TABLES [, Options] ;

RESTART REBUILD ON AMP nnnn ;

Options : LOG INTO logdbase.logtbl
          NO LOCK [ON NO FALLBACK TABLES]
               {DATABASE LOCK}
          WITH {TABLE    LOCK}
               {ROWRANGE LOCK}
         [n TABLES] IN PARALLEL

-- Surgical Rebuild (Teradata 14.10+):
REBUILD AMP nnnn dbname.tname SUBTABLE subtableid ROWRANGE startrowid endrowid
         [AUTOADJUSTBLOCKS] [,lockwaittimeinminutes] ;

REBUILD AMP nnnn dbname.tname DOWN REGION [,lockwaittimeinminutes] ;

REBUILD AMP nnnn dbname.tname TABLE HEADER [,lockwaittimeinminutes] ;
```

### Parameter Details

| Parameter | Description |
|-----------|-------------|
| `nnnn` | VPROC number of the AMP to be rebuilt |
| `dbname` | Database name (for single database rebuild) |
| `dbname.tname` | Database and table name (for single table rebuild) |
| `ALL TABLES` | Rebuild all tables in all databases on the AMP (Full-AMP Rebuild) |
| `FALLBACK TABLES` | Rebuild only fallback tables on the AMP |
| `ALL DATA` | Rebuild both primary and fallback data |
| `PRIMARY DATA` | Rebuild only primary data |
| `FALLBACK DATA` | Rebuild only fallback data |
| `subtableid` | 16-bit hex number identifying the subtable (should not be zero) |
| `startrowid` / `endrowid` | Row ID defined as: `partition hash0 hash1 uniq0 uniq1` where partition is 64-bit hex, others are 16-bit hex |
| `AUTOADJUSTBLOCKS` | If start/end of row range falls in the middle of a bad data block, automatically adjusts to rebuild the entire block. Without this, rebuild returns an error. |
| `lockwaittimeinminutes` | >= 0. Default 0 = wait indefinitely. |
| `LOG INTO logdbase.logtbl` | Required for quiet mode (background) rebuilds. Specifies a log table. |
| `IN PARALLEL` | Rebuild up to 6 tables in parallel per database. Available on TD 13.00+. Up to 33% performance improvement. |
| `NO LOCK` | Skip locking (use with caution) |
| `WITH DATABASE LOCK` | Lock at database level during rebuild |
| `WITH TABLE LOCK` | Lock at table level during rebuild |
| `WITH ROWRANGE LOCK` | Lock at row range level during rebuild (least restrictive) |

### Rebuild Modes — Decision Matrix

| Condition | Recommended Rebuild Mode | AMP State Required |
|-----------|--------------------------|-------------------|
| Single table with errors on online AMP | Surgical Table Rebuild (preferred) or Single Table Rebuild | Online |
| Single table with errors on offline AMP | Surgical Table Rebuild (preferred) or Single Table Rebuild | Offline |
| Multiple tables in one database | Surgical (preferred) or Single Database Rebuild | Online or Offline |
| Multiple tables in multiple databases, AMP can come online | Surgical or Single Table/Database Rebuild after bringing online | Online |
| Multiple tables in multiple databases, AMP cannot come online | Full-AMP Rebuild | Fatal → boot → Utility |
| Fatal AMP | Full-AMP Rebuild | Fatal → boot → Utility |
| Multiple fatal AMPs in different clusters | Many Full-AMP Rebuilds (quiet mode, in parallel) | Fatal → boot → Utility |
| Bad/missing table header | `TABLE HEADER` rebuild | Online or Offline |
| Bad data block (error 5148) | `SUBTABLE ... ROWRANGE ... AUTOADJUSTBLOCKS` | Online or Offline |
| Missing rows | `SUBTABLE ... ROWRANGE ...` | Online or Offline |
| Down regions in table header | `DOWN REGION` rebuild | Online or Offline |
| Single subtable with bad data blocks or missing rows | `SUBTABLE ... ROWRANGE ...` | Online or Offline |

### Rebuild Log Table DDL

**Teradata Database 15.00 and later:**

```sql
CREATE TABLE logdb.logtbl, FALLBACK
     ( msgdate CHAR(8),     /* format:  'yy/mm/dd' */
       msgtime CHAR(8),     /* format:  'hh:mm:ss' */
       msgamp  CHAR(6),     /* format:  'nnnn' */
       msgcode CHAR(1),
       msgtext VARCHAR(600) CHARACTER SET UNICODE)
     PRIMARY INDEX (MsgDate, MsgTime);
```

**Prior to Teradata Database 15.00:**

```sql
CREATE TABLE logdb.logtbl, FALLBACK
     ( msgdate CHAR(8),     /* format:  'yy/mm/dd' */
       msgtime CHAR(8),     /* format:  'hh:mm:ss' */
       msgamp  CHAR(6),     /* format:  'nnnn' */
       msgcode CHAR(1),
       msgtext VARCHAR(80) CHARACTER SET LATIN)
     PRIMARY INDEX (MsgDate, MsgTime);
```

**Log table msgcode values:**

| Code | Meaning |
|------|---------|
| `S` | Starting rebuild |
| `D` | Deleting AMP recovery journal |
| `C` | Completed rebuild |

### Surgical Table Rebuild Prerequisites (Teradata 14.10+)

For **rowrange** and **down region** options, ALL of these must be true:
- No other down AMP in the same cluster (except the one being rebuilt)
- The table has fallback
- The table is hashed
- The table is NOT: a non-hashed dictionary table, journal table, restartable spool table, global temporary table, volatile table, join index, or hash index
- The row range / down region is NOT in a NUSI subtable

### Row ID Format

```
partition hash0 hash1 uniq0 uniq1
```
- `partition` — 64-bit hex number
- `hash0`, `hash1`, `uniq0`, `uniq1` — 16-bit hex numbers each
- Examples of valid row IDs: `0 B334 4BFA 0 1`, `0H B334H 4BFAH 0H 1H`

### Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Interactive (foreground)** | Up to 4 simultaneous rebuilds in CNS windows 1–4. Completion message displayed on screen. | Single table, single database, or one Full-AMP rebuild |
| **Quiet (background)** | Indefinite number from one window. Output goes to log table. | Many Full-AMP rebuilds on multiple AMPs |

**Key rule:** Only one Full-AMP rebuild per cluster can run at a time.

**Restartable:** Only Full-AMP (All Tables) Rebuild is restartable. If a database restart occurs during Full-AMP rebuild:
```
RESTART REBUILD ON AMP <n>;
```

### Estimating Rebuild Time

Formula for serial rebuild:
```
% Complete = (Byte Count of completed table) / (Total Byte Count of all tables)
Estimated Total Time = (Time for completed table) / (% Complete)
```

For parallel rebuild, estimate = **77% of serial time** (up to 33% improvement).

### Monitoring Rebuild Progress (BTEQ)

```sql
-- Check for completion messages
SELECT * FROM systemfe.rebuild2 WHERE msgtext LIKE '%ALL TABLES%';

-- Check for table-level completion
SELECT * FROM systemfe.rebuild2 WHERE msgcode = 'c';
```

Also check `/var/log/messages` for:
```
<timestamp> <hostname> Teradata[<pid>]: INFO: Teradata: 2900 # <date> <time> AMP <n> Completed rebuild of ALL TABLES
```

### Query: List All Fallback Tables and Sizes

```sql
SELECT
  SUM(dbs.CurrentPermSpace) (NAMED CurrentPerm, DECIMAL(15,0),
    FORMAT '---,---,---,---,--9'),
  dbtvm.databasenamei (FORMAT 'X(15)') AS DBASE,
  dbtvm.tvmnamei (FORMAT 'X(30)') AS Tablename
FROM DBC.DataBaseSpace dbs,
  (SELECT db.databaseid, tab.tvmid, db.databasenamei, tab.tvmnamei
   FROM dbc.tvm tab, dbc.dbase db
   WHERE tab.tablekind = 't'
     AND tab.protectiontype = 'f'
     AND db.databaseid = tab.databaseid) dbtvm
WHERE dbs.databaseid = dbtvm.databaseid
  AND dbs.tableid = dbtvm.tvmid
  AND dbs.TableID <> '000000000000'XB
GROUP BY 2, 3
ORDER BY 1 DESC;
```

---

## 5. cnsrun / cnstool — Scripting Utilities

**Purpose:** Automate execution of commands against CNS-based utilities (vprocmanager, rebuild, checktable, rcvmanager) from the command line using script files.

### cnstool

Connects to the Console Subsystem and provides the supervisor window (#6) and interactive windows (#1–4).

```bash
cnstool
```

Output:
```
0:Attempting to connect to CNS...
0:Connecting user root...
0:Attempting to connect to CNS...completed.
0:1/1 sdlc4809 Logons are enabled - The system is quiescent
6:
6:Input Supervisor Command:
```

From the supervisor window (#6), start utilities:
```
6:start vprocmanager    -- starts vprocmanager in an available window
6:start rebuild         -- starts rebuild utility in an available window
6:start checktable      -- starts checktable in an available window
6:start rcvmanager      -- starts rcvmanager in an available window
```

### cnsrun

Sends a script file to a utility running under CNS. Critical for automating Many Full-AMP Rebuilds.

```bash
cnsrun -machine <hostname> -u <utility> -f <scriptfile>
```

| Parameter | Description |
|-----------|-------------|
| `-machine <hostname>` | Teradata system hostname |
| `-u <utility>` | Target utility: `vprocmanager`, `rebuild`, `checktable`, `rcvmanager` |
| `-f <scriptfile>` | Path to the script file containing commands |

### Example Script Files for Many Full-AMP Rebuilds

**tr1_bootamp246** — Boot multiple fatal AMPs:
```
boot 2
y
boot 4
y
boot 6
y
status not
quit
```

Execute: `cnsrun -machine gyoza -u vprocmanager -f tr1_bootamp246`

**tr3_rebuildamp246** — Rebuild multiple AMPs in quiet mode:
```
rebuild amp 2 all tables all data, log into systemfe.rebuild2, in parallel;
y
c
rebuild amp 4 all tables all data, log into systemfe.rebuild4, in parallel;
y
c
rebuild amp 6 all tables all data, log into systemfe.rebuild6, in parallel;
y
quit
```

Execute: `cnsrun -machine gyoza -u rebuild -f tr3_rebuildamp246`

**Key note:** Use separate log tables per AMP to avoid write lock contention.

---

## 6. Recovery Concepts

### AMP Clusters

- AMPs are assigned to **clusters** during system configuration.
- A copy of each **primary data row** (called a **fallback data row**) is distributed to a different AMP in the same cluster.
- Recommended: **2-AMP clusters** for customer systems.
- If an AMP fails, the system accesses fallback data from other AMPs in the same cluster.
- **Rule:** As long as no more than one AMP in a cluster is down at any time, all data remains accessible.

### Fallback Data Distribution

In a 4-AMP cluster (e.g., AMPs 0, 32, 64, 96):
- AMP #0 has primary rows; AMPs #32, #64, #96 each store one-third of AMP #0's primary rows as fallback.
- Rebuild copies primary data from fallback (and vice versa) across the cluster.

### Cliques vs Clusters

- **Clique:** A group of nodes sharing hardware (e.g., shared storage). Hardware failures may take down all AMPs on a node.
- **Cluster:** A logical grouping of AMPs for fallback data distribution. Spans multiple cliques/nodes.

### OJ / CJ Journals

| Journal | Full Name | Tracks |
|---------|-----------|--------|
| **OJ** | Ordered System Change Journal | DDL operations (CREATE, ALTER, DROP) while AMP is down |
| **CJ** | Changed Row Journal | DML operations (INSERT, UPDATE, DELETE) while AMP is down |

### Current Pass vs Next Pass

1. When an AMP comes online, all pending OJs/CJs move to **Current Pass** and start processing.
2. New work during Current Pass processing goes to **Next Pass**.
3. This cycle repeats until Next Pass is empty.
4. Minimizing user activity during recovery reduces recovery time.

### Non-Fallback Table Recovery

Table Rebuild only rebuilds the **table header** for non-fallback tables — the data is lost and must be reloaded from backups (Archive/Recovery utility).

Exception: `TABLE HEADER` surgical rebuild only fixes the header without deleting data, so non-fallback tables don't need reload for header-only issues.

---

## 7. Data Recovery Decision Tree

### Step-by-Step Procedure

```
1. DETECT ERROR
   └─► Hardware alert, user error, scandisk report, or checktable finding

2. RESOLVE HARDWARE ISSUES FIRST
   └─► Work with hardware support to ensure platform is stable
   └─► Do NOT attempt data rebuild if hardware will corrupt data again

3. ASSESS SCOPE
   ├─► How many AMPs affected?
   ├─► How many tables/databases affected?
   ├─► Can the AMP(s) be brought online?
   └─► What is the AMP state? (Online / Offline / Fatal)

4. RUN CHECKTABLE
   └─► check <table> at level three with no error limit;
   └─► Review error file for complete row ID listings

5. SELECT REBUILD MODE (see decision matrix below)

6. EXECUTE REBUILD
   └─► For online/offline AMP: Interactive rebuild
   └─► For fatal AMP: Boot → Create log table → Quiet mode rebuild
   └─► For multiple fatal AMPs: Boot all → Create log tables → cnsrun quiet mode

7. POST-REBUILD
   ├─► set <amp> = online          (vprocmanager)
   ├─► Monitor recovery             (rcvmanager: list status <amp>;)
   ├─► Wait for * indicator
   ├─► restart nodump coldwait      (vprocmanager)
   └─► Verify: check <tables> at level two error only;
```

### Decision Matrix: Which Rebuild to Use

```
Is the AMP Fatal?
├─► YES: Can it be brought online after hardware repair?
│   ├─► YES: Bring online → use Surgical/Single Table/Database rebuild
│   └─► NO: Full-AMP Rebuild required
│       ├─► Single fatal AMP → Full-AMP Rebuild
│       └─► Multiple fatal AMPs → Many Full-AMP Rebuilds (one per cluster)
└─► NO (Online or Offline):
    ├─► Single table error?
    │   ├─► Bad/missing table header → TABLE HEADER rebuild
    │   ├─► Bad data block (5148) → SUBTABLE ROWRANGE AUTOADJUSTBLOCKS
    │   ├─► Missing rows → SUBTABLE ROWRANGE
    │   ├─► Down regions → DOWN REGION rebuild
    │   └─► General corruption → Single Table Rebuild (ALL DATA)
    ├─► Multiple tables in one database → Single Database Rebuild
    └─► Multiple databases → Fallback Tables Rebuild or Full-AMP Rebuild
```

### Procedures by Rebuild Type

#### Single Table Rebuild — Online AMP
1. `rebuild amp <n> <db>.<tbl> all data;`
2. `check <db>.<tbl> at level two;`

#### Single Table Rebuild — Offline AMP
1. Confirm offline: `status not` (vprocmanager)
2. `rebuild amp <n> <db>.<tbl> all data;`
3. `set <n> = online` (vprocmanager)
4. Monitor: `list status <n>;` (rcvmanager)
5. `restart nodump coldwait` (vprocmanager)
6. `check <db>.<tbl> at level two;`

#### Single Database Rebuild
```
-- Serial
rebuild amp <n> <dbname> all data;
-- Parallel (TD 13.00+)
rebuild amp <n> <dbname> all data, in parallel;
```

#### Fallback Tables Rebuild — Offline AMP
```
-- Serial
rebuild amp <n> fallback tables;
-- Parallel
rebuild amp <n> fallback tables, in parallel;
```

#### Full-AMP Rebuild — Fatal AMP
1. Confirm fatal: `status not` (vprocmanager)
2. `boot <n>` (vprocmanager) — wait for UTILITY/Down state
3. Create log table via BTEQ
4. `rebuild amp <n> all tables all data, log into <logdb>.<logtbl>, in parallel;`
5. Monitor via log table queries
6. `set <n> = online` (vprocmanager)
7. `list status <n>;` (rcvmanager) — wait for `*`
8. `restart nodump coldwait` (vprocmanager)
9. `check all tables at level two error only;`

#### Many Full-AMP Rebuilds — Multiple Fatal AMPs
1. `set <amp1>,<amp2>,<ampN> fatal` then `restart nodump coldwait`
2. Build script files for boot, log table creation, and rebuild
3. `cnsrun -machine <host> -u vprocmanager -f <boot_script>`
4. `bteq < <create_log_script>`
5. Confirm all AMPs show UTILITY/Down
6. `cnsrun -machine <host> -u rebuild -f <rebuild_script>`
7. Monitor via log table queries
8. `set <amp1>,<amp2>,<ampN> online`
9. Wait for recovery, then `restart nodump coldwait`

**Critical constraint:** Only AMPs from **different clusters** can be rebuilt simultaneously.
