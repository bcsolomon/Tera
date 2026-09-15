# Teradata Crash Dump Management Reference

> Source: 541-0009271-A02 (Database Crash Dump Handling)

> See also: [utility-commands-reference.md](utility-commands-reference.md) — checktable, vprocmanager, rcvmanager, rebuild, cnsrun/cnstool, recovery concepts, data recovery decision tree

---

## Table of Contents

1. [ctl Utility — Debug Screen](#1-ctl-utility--debug-screen)
2. [csp Utility — Crash Dump Save Program](#2-csp-utility--crash-dump-save-program)
3. [Crashdumps Database Setup](#3-crashdumps-database-setup)
4. [pcl — Multi-Node Commands](#4-pcl--multi-node-commands)
5. [Crash Dump Verification Utilities](#5-crash-dump-verification-utilities)
6. [Crash Dump Offload and Upload](#6-crash-dump-offload-and-upload)

---

## 1. ctl Utility — Debug Screen

**Purpose:** Set PDE control options including crash dump behavior.

### Accessing Debug Screen

```bash
ctl
> screen debug
```

### Debug Screen Parameters

```
(0) Start DBS:              On
(1) Break Stop:             Off
(2) Enable Logons:          All
(3) Start with Debug:       Off
(4) Save Dumps:             Off          
(5) Snapshot Crash:         Off
(6) Maximum Dumps:          5            
(7) Maximum Dump Size:      0(MB)
(8) Maximum FSG Area Dumped: 10 (MB)
(9) Start PrgTraces:        Off
```

### Parameter Details

| # | Parameter | Values | Default | Description |
|---|-----------|--------|---------|-------------|
| 0 | Start DBS | On/Off | On | Whether database starts automatically |
| 1 | Break Stop | On/Off | Off | Break on stop |
| 2 | Enable Logons | All/Off | All | Logon control |
| 3 | Start with Debug | On/Off | Off | Debug mode at startup |
| 4 | **Save Dumps** | On/Off | **Off (recommended)** | If On, raw dumps are automatically saved (via CSP) to Crashdumps database immediately after restart. If Off, raw dumps must be saved manually using `csp -mode save -force`. Recommended Off for control over the process; with multi-restart conditions the auto-save can be a runaway process. |
| 5 | Snapshot Crash | On/Off | Off | Snapshot dump behavior |
| 6 | **Maximum Dumps** | -1, 0, 1–N | 5 | Max raw dumps in `/var/opt/teradata/tddump`. If 0: dumps disabled (NOT recommended). If -1: limited only by available disk space. If N: skips dump if N directories already exist. |
| 7 | **Maximum Dump Size** | 0 or N (MB) | 0 | Max size of a single raw dump. 0 = no size limit. |
| 8 | Maximum FSG Area Dumped | N (MB) | 10 | Max FSG cache area dumped |
| 9 | Start PrgTraces | On/Off | Off | Program trace startup |

### Selective Dumps (Teradata 14.0+)

An additional control GDO option (not on the screen above):

| Setting | Description |
|---------|-------------|
| `System` (default) | Full system dumps for database failures — every process from every node |
| `Selective` | Only dump processes most relevant to the failure — smaller, faster restarts, but may hinder diagnosing some errors |

---

## 2. csp Utility — Crash Dump Save Program

**Purpose:** Save (harvest/coalesce) raw PDE crash dumps from each node into a single table in the Crashdumps database. Also lists, clears, and manages crash dumps.

### Syntax

```bash
csp -mode <mode> [options]
```

### Modes and Commands

| Command | Description |
|---------|-------------|
| `csp -mode list` | List available raw dumps ready to be saved |
| `csp -mode list -source table` | List dumps already saved in the Crashdumps database |
| `csp -mode save` | Interactively iterate through raw dumps, asking whether to save each |
| `csp -mode save <dumpID>` | Save a specific dump by ID (e.g., `2012/02/15-14:06:36-02`) |
| `csp -mode save -force` | Override the "Save Dumps = Off" flag in ctl and save the dump |
| `csp -mode save -force <dumpID>` | Save a specific dump, overriding the Save Dumps flag |
| `csp -mode clear` | Iterate through raw dumps and ask whether to remove each |
| `csp -mode clear -source dump` | Clear raw dumps (from `/var/opt/teradata/tddump`) |
| `csp -mode clear -source table` | Clear database dumps (from Crashdumps database tables) |

### CSP List Output Format

```
csp: Sel   ID (date-time-token)   Nodes  Event  Instigator   Status
csp: ---  ----------------------  -----  -----  -------------------------
csp:  *   2011/11/03-11:42:28-02      1   3601  16383/13/(9917)
```

```
csp: Sel   DumpName               Nodes  Event  Instigator         Status
csp: ---  ----------------------  -----  -----  ---------------    ------
csp:  *   CRASH_20120110_145647_03      1      0  0/0/(24455)
csp:  *   CRASH_20120106_112245_02      4   2967  0/15/(5808)
```

### Key Behaviors

- After a successful save, CSP **automatically removes (clears)** the raw dump from each node.
- No output is displayed while saving is in progress.
- If save must be stopped: `Ctrl-C`, then manually drop incomplete dump tables from Crashdumps database.
- CSP **cannot detect incomplete crash dumps** — use SQL to find and drop `_Err1`/`_Err2` tables.
- CSP can be run from **any node** in the TPA configuration.
- CSP log entries go to `/var/log/messages` — use `logview -contains csp` to view.

### CSP Performance Impact

- Saving raw dumps: up to **15% of node CPU capacity**
- Unloading crash dumps: around **8% of CPU**
- Can be managed via TASM: "CSP Save Dump" under FastLoad utility limits (TD 13.10+)

### Crashdumps Database Table Naming

For each crash dump, CSP creates:
1. `CRASH_<timestamp>_<token>` — The dump table
2. `CRASH_<timestamp>_<token>_Err1` — Error log table 1 (removed after successful save)
3. `CRASH_<timestamp>_<token>_Err2` — Error log table 2 (removed after successful save)

If `_Err1`/`_Err2` tables remain, the dump was incomplete. Drop all three tables before re-saving:

```sql
DROP TABLE crashdumps.CRASH_20120215_160609_01;
DROP TABLE crashdumps.CRASH_20120215_160609_01_Err1;
DROP TABLE crashdumps.CRASH_20120215_160609_01_Err2;
```

---

## 3. Crashdumps Database Setup

### Sizing Formula

```
Perm Space = ½ × (Memory per Node in GB) × (Number of Nodes) × (Number of Dumps to Save)
```

**Example:** 96 GB per node, 10 nodes, save 3 full dumps:
```
½ × 96 GB × 10 nodes × 3 dumps = 1,440 GB ≈ 1.44 TB perm space
```

- The Crashdumps database normally has **fallback turned on** — the formula accounts for this.
- With **block-level compression** (TD 13.10+), perm space typically shrinks by factor of **3.7 to 3.8**.
- In practice, selective dumps mean maximum storage is rarely used.

### Raw Dump Storage

- Location: `/var/opt/teradata/tddump` (usually part of `/var/opt/teradata` filesystem)
- For crash dump servers, ensure `/var/opt/teradata` is as large or larger than the production system.
- Each raw dump creates a subdirectory: `dump_<YYYYMMDD>_<HHMMSS>`

### Crash Dump Size Estimates

- **Full system dump:** ~150 MB per VPROC (±30 MB). Example: 34 nodes, 978 VPROCs = ~150 GB.
- **Selective/precision dumps:** Only 2–3 relevant VPROCs = ~2–4 GB regardless of system size.
- **Snapshot dumps:** Relatively small — only processes related to the failed transaction.

### Dump Server Requirements

1. Same version of Linux (SLES version), Teradata Database, and PDE as the production system (exact patch level)
2. `teradata-gsctools`, `dul`, and `duptape` packages installed
3. Storage for 2–3 full crash dumps
4. No VMware or other virtualization
5. VM&F can support up to 2 different OS/DB version combinations

---

## 4. pcl — Multi-Node Commands

**Purpose:** Execute shell commands across multiple nodes simultaneously.

### Syntax

```bash
# Execute command on all nodes
pcl -sh "<command>"

# Execute command on specific nodes
pcl -nodes <node1>,<node2>,<nodeN> -sh "<command>"
```

### Examples

```bash
# List raw dump directories across all nodes
pcl -sh "ls -l /var/opt/teradata/tddump"

# Remove a raw dump from specific nodes
pcl -nodes byn001-9,byn001-10,byn001-12,byn001-13 \
  -sh "rm -r /var/opt/teradata/tddump/dump_20120215_165556"
```

**Note:** Useful when a raw dump is not available to CSP (e.g., the node containing it is not in the TPA configuration). Manually check/remove dump directories using `pcl`.

---

## 5. Crash Dump Verification Utilities

### logview — Filter System Logs

```bash
# Filter log entries from CSP
logview -contains csp

# Filter log entries from dmp (raw dump creation)
logview -contains dmp
```

### Successful Raw Dump Indicators

In `/var/log/messages`:
```
dmp[2533]: INFO: TdatTools: 29001 #PDE DMP Utility -- Dump started: mode=mapped, buffer=64 MB, workers=4
dmp[2533]: INFO: TdatTools: 29001 #PDE DMP Utility -- Dump completed (size = 102560 KB)
```

### Warning: Max Dumps Exceeded

```
dmp[2533]: DEGRADED: TdatTools: 29003 #PDE DMP Utility -- Control GDO maxdumps exceeded -- no dump captured
```

### dmptrace.txt Verification

Inside each raw dump directory (`/var/opt/teradata/tddump/dump_<timestamp>/`):
```bash
tail -3 dmptrace.txt
# Expected output:
# 28266: [LOG] PDE DMP Utility -- Dump completed (size = 467588 KB)
```

If `dmptrace.txt` is not found, the raw dump was not created successfully.

### csppeek — Verify Crash Dump Contents

```bash
csppeek -d <DumpName>
```

**Example:**
```bash
csppeek -d CRASH_20120215_154812_06
```

**Output includes:**
- Number of nodes, vprocs, pids, tids, memos in the dump
- Software versions (PDE, TDBMS, PDEGPL, TGTW, TDGSS)
- Operating system version per node
- Dump token and instigator information

Use to verify:
- All expected nodes are present in the dump
- Needed VPROCs are included (important for partial dumps)
- Software versions match the production system

### Checksum Verification for Offloaded Dumps

```bash
# View checksum file
tail -3 crashdump.REC8UUN8B.cs.01of02
# Output: 2351704587 167996553 crashdump.REC8UUN8B.gz.02of02.gpg

# Verify checksum
cksum crashdump.REC8UUN8B.gz.02of02.gpg
# Should match: 2351704587 167996553 crashdump.REC8UUN8B.gz.02of02.gpg
```

---

## 6. Crash Dump Offload and Upload

### get_cdump.sh — Offload Script

Part of the `teradata-gsctools` package. Automates DUL unload, compression, splitting, and encryption.

```bash
get_cdump.sh
```

**Prompts:**
1. Use default crashdumps user/password? (y/n)
2. Enter incident number (e.g., `rec8uun8b`)
3. Optional unique ID for multiple uploads per incident
4. Select crash dump from list
5. Select output directory (default: `/var/opt/teradata/gsctools/getcdump`)
6. Select dump type:
   - `1)` Partial crash dump (default — use in most cases)
   - `2)` Full crash dump (for hangs, forced dumps)
   - `3)` Specific vproc(s) — unloads the node(s) where those vprocs are located
   - `4)` Specific node — only on GSC request
7. Encrypt output files? (y/n — required for external FTP upload)

**Output:** Split files (max 1 GB each) + checksum `.cs` file.

### upload2gsc.pl — Upload Script

```bash
upload2gsc.pl <file1> [file2] ...
```

**Options:**
| Option | Description |
|--------|-------------|
| `-s` | Use Secure FTP (SFTP) protocol |
| `-b` | Background mode — returns to shell during upload, logs to `nohup.out` |

**File type prompt:** `(t)` Teradata DBS crashdump, `(d)` OS panic dump, `(l)` Log files, `(o)` Other.

### DUL Utility

```bash
# Direct usage (usually automated by get_cdump.sh)
dul
```

The Data Unload/Load utility exports crash dump tables to flat files and loads them on dump servers. Can select specific VPROCs from a dump.

### Force Dump Command

When the database hangs (no automatic dump):
```bash
tpareset -d
```

Forces a system-level dump and restart. Results in a full dump of all nodes.
