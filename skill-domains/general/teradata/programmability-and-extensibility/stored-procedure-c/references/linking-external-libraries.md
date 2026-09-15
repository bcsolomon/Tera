# Linking an External Library into a C/C++ XSP (EXTERNAL NAME)

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Linking an External Library into a C/C++ XSP (EXTERNAL NAME) (EXTERNAL NAME syntax from the manual; node/link behavior verified against Teradata database server source)

C/C++ External Stored Procedures are compiled and linked **inside the database** by the same
worker process (`cufdoudf`) and go through the same `EXTERNAL NAME` parser as C UDFs, so the
mechanism for attaching a third-party library is identical. XSPs take a two-phase
compile-then-link path, but the library and search-path controls are the same. Use this when an
XSP must link against a library that is not part of the base toolchain (for example
`librdkafka`, `libcurl`, or an in-house `.a`/`.so`).

> This is distinct from the `SP!CLI!` prefix already used for CLIv2 procedures. `SP!CLI!`
> selects the predefined **CLI application category** (its includes/libs are injected
> automatically). The steps below cover linking an **arbitrary** third-party library.

## How the in-database link command is built

`cufdoudf` writes a `Makefile` and runs `make`. The base libraries, base include path
(`-I/usr/tdbms/etc`), and base library path (`-L/usr/tdbms/lib`) are fixed. The only slots you
control are:

- `UDFLIBn`, populated by the `SL` file item, which emits `-l<name>`.
- `UDFPKGn`, populated by the `SP` file item, which places a verbatim token/path on the link line.
- Extra `-L` / `-rpath` search paths, populated from the `cufconfig` `USRLibraryPath` setting.

## The two EXTERNAL NAME file items for libraries

Both are **server-side only** (there is no `CL`/`CP` client-side form) and are **not valid for
`LANGUAGE JAVA`**.

- `SL!<library_base_name>` emits `-l<library_base_name>`. `SL!rdkafka` links `-lrdkafka`,
  resolved to `librdkafka.so`/`.a` on the search path. The library item must appear **last** in
  the `EXTERNAL NAME` string.
- `SP!<package_name_or_path>`: a recognized SDK keyword (`CLI`, `ODBC`, `JAVA`, `.NET`) selects
  an application category and injects that SDK's predefined includes/libs; any other value
  (category `AppStandard`) is placed **verbatim** on the link line, so you can pass a full path
  such as `SP!/opt/kafka/lib/librdkafka.a`. A package cannot be combined with source/object/
  include/library items in the same clause.

## Telling the linker where the library lives: `USRLibraryPath`

A third-party library is not under `/usr/tdbms/lib`, so `-lrdkafka` alone will not resolve. Add
the directory that holds the library to the **`cufconfig` `USRLibraryPath`** setting
(colon-separated, default `/usr/tdbms/lib`):

```bash
cufconfig -o | grep -i USRLibraryPath          # inspect
# put ONLY the field you are changing in the input file:
#   echo 'USRLibraryPath: /usr/tdbms/lib:/opt/kafka/lib' > usrlibpath.txt
cufconfig -f usrlibpath.txt                     # apply
```

> **Do not feed a full `cufconfig -o` dump back into `cufconfig -f`.** The dump includes the
> immutable system paths `UDFLibraryPath`, `JavaLibraryPath`, and `UIFLibraryPath`. If any of
> those lines is present, `cufconfig -f` reports `... is Teradata system path that cannot be
> changed` and `No changes to the gdo are made.`, applying **nothing** (so `USRLibraryPath`
> silently stays at its default). The `-f` file must contain only the field(s) you are changing.

When any `SL`/`SP` library is present, `cufdoudf` adds `-L<path>` **and**
`-Xlinker -rpath -Xlinker <path>` for every entry, so the path is used both at link time and,
via the baked-in `rpath`, at runtime.

## Multi-node staging: a C XSP is compiled on EVERY node

This is the single most common cause of a `CREATE/REPLACE PROCEDURE ... SL!...` failure on a
multi-node system, and it differs from how C UDFs behave:

- A **C UDF** is compiled once on a single compile-capable node and the resulting `.so` is then
  distributed to all nodes by the database (`cufdistdll`). Only the compile node needs the
  library present at link time.
- A **C XSP requires a compiler on each node**: the database compiles and links the procedure
  **independently on every node** (the object is stored in the dictionary, not distributed like a
  UDF `.so`). Therefore the link-time prerequisites must be satisfied on **all** nodes, not just
  the node you are logged into or the one that parses the DDL.

Because the link runs on every node, the DDL fails if **any** node is missing the library, and
the failing node is usually not the one you ran the statement from. A real failure looks like:

```
/usr/bin/gcc -shared -fpic ... -L/usr/tdbms/lib -L/usr/lib64/ -o @FileList -lrdkafka ...
/usr/lib64/.../ld: cannot find -lrdkafka: No such file or directory
collect2: error: ld returned 1 exit status
```

### The linker needs the UNVERSIONED `.so`, not the runtime `.so.N`

`-lrdkafka` makes `ld` search for a file named exactly `librdkafka.so`. Runtime packages ship
only the **versioned** shared object (`librdkafka.so.1`); the **unversioned** `librdkafka.so`
symlink is a *development* artifact that comes from the `-devel`/`-dev` package (or must be
created by hand). Having `librdkafka.so.1` present is enough for **runtime** but not for the
**link** step. Confirm both, on every node:

```bash
# run on each node (or fan out with psh / pcl)
ldconfig -p | grep librdkafka
#   librdkafka.so.1  => /usr/lib64/librdkafka.so.1   <- runtime only, link will FAIL
#   librdkafka.so    => /usr/lib64/librdkafka.so     <- REQUIRED for -lrdkafka to link
```

If the unversioned symlink is missing on a node, create it (or install the `-devel` package)
there and refresh the cache:

```bash
ln -s /usr/lib64/librdkafka.so.1 /usr/lib64/librdkafka.so
ldconfig
```

Do this on **all** nodes before running the DDL; then re-verify with `ldconfig -p` per node.

## Recipe: link a C XSP against `librdkafka`

1. **Stage the library and headers on every TPA node** (and, for protected-mode routines,
   inside the `udfsectsk` container): e.g. `librdkafka.so` in `/opt/kafka/lib`, `rdkafka.h` in
   `/opt/kafka/include`. Verify with `pcl -s`. **Include the unversioned `.so` dev symlink on
   every node** (see above), since the XSP is linked on each node.
2. **Register the directory** with `cufconfig`: add `/opt/kafka/lib` to `USRLibraryPath`.
3. **Reference the library in the DDL** (server-compiled source, header supplied as an include
   item):

```sql
REPLACE PROCEDURE mydb.kafka_send (
    IN topic VARCHAR(128),
    IN msg   VARCHAR(1000)
)
LANGUAGE C
NO SQL
PARAMETER STYLE TD_GENERAL
EXTERNAL NAME 'CS!kafka_send!kafka_send.c!F!kafka_send_entry!SL!rdkafka';
```

Or precompile the object off-node so no server-side header path is needed, then link it:

```bash
gcc -fPIC -I/usr/tdbms/etc -I/opt/kafka/include -c kafka_send.c -o kafka_send.o
```

```sql
EXTERNAL NAME 'CO!kafka_send!kafka_send.o!F!kafka_send_entry!SL!rdkafka';
```

### Combining a third-party library with CLIv2

An XSP that both executes SQL (CLIv2) and needs a third-party library uses the `SP!CLI!`
package for CLIv2 plus the `SL` item for the extra library. Keep the `SL` item last:

```sql
REPLACE PROCEDURE mydb.kafka_relay (
    IN topic VARCHAR(128)
)
LANGUAGE C
READS SQL DATA
PARAMETER STYLE TD_GENERAL
EXTERNAL NAME 'SP!CLI!CS!kafka_relay!kafka_relay.c!SL!rdkafka';
```

## Gotchas

- **Link-time vs runtime, per node.** The unversioned `librdkafka.so` symlink is needed at
  **link** time on every node that compiles (all nodes for a C XSP); the versioned
  `librdkafka.so.N` is needed at **runtime** on every node. Staging only `.so.N` links nothing
  (`ld: cannot find -lrdkafka`); staging only the dev `.so` with no runtime object loads nothing
  (`Failure 7506`). Stage both, on all nodes.
- **Runtime load path.** The `rpath` is fixed from `USRLibraryPath` at compile time, so the
  library must sit at that exact path on **all** nodes. A missing/misnamed file yields
  `*** Failure 7506 The library for UDF/XSP/UDM ... could not be found`, logged by
  `udfcachelib` in `/var/log/messages`.
- **Protected mode.** Protected routines run in the `udfsectsk` container; the library must be
  reachable there as well.
- **No client-side library codes.** `SL`/`SP` are server-side only; the library and its search
  path are always node-resident.
- **Java.** `SL`/generic `SP` are rejected for `LANGUAGE JAVA`; Java routines link through
  installed JARs (`SQLJ.INSTALL_JAR`).
- **Ordering / exclusivity.** The library item must be last, and a `SP` package cannot be mixed
  with source/object/include/library items in the same clause.
