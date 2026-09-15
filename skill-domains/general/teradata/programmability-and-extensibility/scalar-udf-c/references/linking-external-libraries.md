# Linking an External Library into a C UDF (EXTERNAL NAME)

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Linking an External Library into a C UDF (EXTERNAL NAME) (EXTERNAL NAME syntax from the manual; node/link behavior verified against Teradata database server source)

C/C++ UDFs are compiled and linked **inside the database** by a worker process (`cufdoudf`).
By default the link line pulls in only Teradata's own libraries. To link a UDF against a
third-party library that is not part of the base toolchain (for example `librdkafka`,
`libcurl`, or an in-house `.a`/`.so`), you must (1) tell the linker which library to link
with an `EXTERNAL NAME` file item, and (2) tell the linker where to find it with a
`cufconfig` setting. This applies identically to C/C++ External Stored Procedures.

## How the in-database link command is built

`cufdoudf` generates a `Makefile` in a temporary working directory and runs `make`. On Linux
the compile and link steps are:

```make
CFLAGS    = -D_REENTRANT -D_LIBC_REENTRANT $(DEBUG) $(INCPATH) $(LIBPATH)
INCPATH   = $(APPINCPATH) -I/usr/tdbms/etc
LIBPATH   = $(APPLIBPATH) -L/usr/tdbms/lib  [ -L<USRLibraryPath entry> ... ]
LIBRARIES = $(APPLIBS) $(DBLIBS) $(UDFLIB0) ... $(UDFPKG0) ... -ludf -lm -ljil -lstdc++

# compile each source
$(CC) $(CFLAGS) -fpic -c <source>.c

# link the shared object that becomes the UDF library
$(CC) -shared -fpic -Xlinker -rpath -Xlinker /usr/tdbms/lib \
      [ -Xlinker -rpath -Xlinker <USRLibraryPath entry> ... ] \
      -Wl,--version-script=<temp>/UserUdf_versions.scr \
      $(CFLAGS) -o @FileList $(LIBRARIES)
```

The base libraries (`-ludf -lm -ljil -lstdc++`), the base include path (`-I/usr/tdbms/etc`),
and the base library path (`-L/usr/tdbms/lib`) are fixed. The only slots you control are:

- `UDFLIBn`, populated by the `SL` file item (a `-l<name>` entry).
- `UDFPKGn`, populated by the `SP` file item (a verbatim token or path on the link line).
- The extra `-L` / `-rpath` search paths, populated from the `cufconfig` `USRLibraryPath`.

## The two EXTERNAL NAME file items for libraries

Both items are **server-side only** (they live in the `S...` branch of the parser: there is
no `CL`/`CP` client-side equivalent) and are **not valid for `LANGUAGE JAVA`**.

### `SL` : link a named library

```
SL!<library_base_name>
```

Emits `-l<library_base_name>` into the link line. `SL!rdkafka` links `-lrdkafka`, which the
linker resolves to `librdkafka.so` (or `librdkafka.a`) on the library search path. This is the
cleanest way to attach a normal shared or static library. The library item must appear **last**
in the `EXTERNAL NAME` string.

### `SP` : link a package

```
SP!<package_name_or_path>
```

Two behaviours depending on the value:

- **Recognized SDK keyword** (`CLI`, `ODBC`, `JAVA`, `.NET`): selects a predefined
  *application category*. The database then injects that SDK's whole predefined set of
  include paths (`APPINCPATH`), library paths (`APPLIBPATH`), and libraries (`APPLIBS`),
  read from the UDF GDO configuration. This is exactly the mechanism behind the `SP!CLI!`
  prefix used by CLIv2 external stored procedures.
- **Any other value** (application category `AppStandard`): the value is placed **verbatim**
  onto the link line as a `UDFPKG` token. You can therefore pass a full path to a specific
  archive, for example `SP!/opt/kafka/lib/librdkafka.a`. A package cannot be combined with
  `S`/`L`/`I`/`O` source/library/include/object items in the same clause.

## Telling the linker where the library lives: `USRLibraryPath`

`librdkafka` is not under `/usr/tdbms/lib`, so `-lrdkafka` alone will fail to resolve. Add the
directory that contains the library to the **`cufconfig` `USRLibraryPath`** setting (a
colon-separated list, default `/usr/tdbms/lib`):

```bash
# on a database node, as the Teradata admin user
cufconfig -o | grep -i USRLibraryPath          # inspect current value
# put ONLY the field you are changing in the input file, then apply it:
#   echo 'USRLibraryPath: /usr/tdbms/lib:/opt/kafka/lib' > usrlibpath.txt
cufconfig -f usrlibpath.txt
```

> **Do not feed a full `cufconfig -o` dump back into `cufconfig -f`.** The dump includes the
> immutable system paths `UDFLibraryPath`, `JavaLibraryPath`, and `UIFLibraryPath`. When
> `cufconfig -f` sees any of those lines it prints `ERROR: ... is Teradata system path that
> cannot be changed` and `No changes to the gdo are made.`, then returns **without applying any
> change** (so `USRLibraryPath` silently stays at its previous/default value). The `-f` file must
> contain only the field(s) you are actually changing. The multi-path colon syntax
> (`/usr/tdbms/lib:/opt/kafka/lib`) is itself valid and is split correctly at compile time.

When any `SL`/`SP` library is present (or `USRLibraryPath` is non-default), `cufdoudf` adds
`-L<path>` **and** `-Xlinker -rpath -Xlinker <path>` for every entry. The `rpath` is baked
into the compiled UDF library, so the same path is used to locate the library **at runtime**,
not just at link time.

## Multi-node staging: link-time vs runtime

On a multi-node system a UDF and an XSP stage the library differently, and the link step needs a
different file than the runtime step. Both distinctions cause real `EXTERNAL NAME` failures.

### Which nodes compile

- A **C UDF** is compiled and linked once on a single compile-capable node; the database then
  distributes the resulting `.so` to every node (`cufdistdll`). Strictly, only the compile node
  needs the library at link time. However, you cannot reliably predict which node that is, so
  stage the library on **all** compile-capable nodes to be safe.
- A **C/C++ XSP requires a compiler on each node**: it is compiled and linked **independently on
  every node** (the object is stored in the dictionary, not distributed like a UDF `.so`). Every
  node must satisfy the link-time prerequisites, and the failing node is usually not the one you
  ran the DDL from.

Net guidance: stage the library (and its dev symlink, below) on **all** nodes for either routine
type.

### The linker needs the UNVERSIONED `.so`, not the runtime `.so.N`

`-lrdkafka` makes `ld` search for a file named exactly `librdkafka.so`. Runtime packages ship
only the **versioned** object (`librdkafka.so.1`); the **unversioned** `librdkafka.so` symlink is
a *development* artifact from the `-devel`/`-dev` package (or created by hand). `librdkafka.so.1`
alone satisfies **runtime** but not the **link** step, producing:

```
ld: cannot find -lrdkafka: No such file or directory
collect2: error: ld returned 1 exit status
```

Verify both objects on every node and create the symlink where it is missing:

```bash
ldconfig -p | grep librdkafka          # per node (fan out with psh / pcl)
#   librdkafka.so.1 => /usr/lib64/librdkafka.so.1   <- runtime only, link FAILS
#   librdkafka.so   => /usr/lib64/librdkafka.so     <- REQUIRED for -lrdkafka

ln -s /usr/lib64/librdkafka.so.1 /usr/lib64/librdkafka.so && ldconfig   # if missing
```

## Recipe: link a C UDF against `librdkafka`

1. **Stage the library and headers on every TPA node** (and, for protected-mode routines,
   inside the `udfsectsk` container). For example: `librdkafka.so` in `/opt/kafka/lib`,
   `rdkafka.h` in `/opt/kafka/include`. Use `pcl -s` to confirm the file is present on all
   nodes.
2. **Register the directory** with `cufconfig`: add `/opt/kafka/lib` to `USRLibraryPath`.
3. **Reference the library in the DDL.** Two equivalent forms:

Compile the source on the node and link `-lrdkafka` (header supplied as an include item, or
pre-staged where `INCPATH` reaches it):

```sql
CREATE FUNCTION mydb.kafka_produce (msg VARCHAR(1000))
RETURNS INTEGER
LANGUAGE C
NO SQL
PARAMETER STYLE SQL
EXTERNAL NAME 'CS!kafka_produce!kafka_produce.c!SL!rdkafka';
```

Or precompile the object off-node (so no server-side header path is needed) and link it:

```bash
# off-node, matching the server toolchain
gcc -fPIC -I/usr/tdbms/etc -I/opt/kafka/include -c kafka_produce.c -o kafka_produce.o
```

```sql
CREATE FUNCTION mydb.kafka_produce (msg VARCHAR(1000))
RETURNS INTEGER
LANGUAGE C
NO SQL
PARAMETER STYLE SQL
EXTERNAL NAME 'CO!kafka_produce!kafka_produce.o!F!kafka_produce_entry!SL!rdkafka';
```

Full-path package variant (link a specific archive without relying on `-l` resolution):

```sql
EXTERNAL NAME 'CO!kafka_produce!kafka_produce.o!F!kafka_produce_entry!SP!/opt/kafka/lib/librdkafka.so';
```

## Supplying headers (`-I`) for server-side compilation

`INCPATH` is only `$(APPINCPATH) -I/usr/tdbms/etc` by default, so a server-compiled source
that needs `rdkafka.h` must get the header path one of these ways:

- Ship the header as an **include file item**: `...!CI!rdkafka!rdkafka.h!...` (client include)
  or `SI` (server include), placed alongside the source.
- Use an **SDK application category** via `SP!<keyword>` when the library is one of the
  recognized SDKs (this also sets `APPINCPATH`).
- **Precompile the `.o` off-node** with your own `-I` (the `CO`/`SO` approach above); the
  header is then irrelevant at link time.

## Gotchas

- **Link-time vs runtime object.** `-lrdkafka` links against the unversioned `librdkafka.so`
  (a `-devel` symlink); the loader uses the versioned `librdkafka.so.N`. Stage both on every
  node: only `.so.N` fails the link (`ld: cannot find -lrdkafka`), only the dev `.so` fails the
  load (`Failure 7506`).
- **Runtime load path.** The `rpath` is fixed from `USRLibraryPath` at compile time, so the
  library must sit at that exact path on **all** nodes. A missing or misnamed file yields
  `*** Failure 7506 The library for UDF/XSP/UDM ... could not be found`, logged by
  `udfcachelib` in `/var/log/messages` as `cannot open shared object file`.
- **Protected mode.** Protected/secure routines run in the `udfsectsk` container. The shared
  library must be reachable there too, not just on the bare node.
- **No client-side library codes.** `SL`/`SP` are server-side only. The library and its search
  path are always node-resident; you cannot upload a library from the client the way you upload
  a `.c` (`CS`) or `.o` (`CO`).
- **Java.** `SL`/generic `SP` are rejected for `LANGUAGE JAVA`. Java routines link their
  dependencies through installed JARs (`SQLJ.INSTALL_JAR`) instead.
- **Ordering / exclusivity.** The library item must be the last item in the `EXTERNAL NAME`
  string, and a `SP` package cannot be mixed with source/object/include/library items in the
  same clause.
