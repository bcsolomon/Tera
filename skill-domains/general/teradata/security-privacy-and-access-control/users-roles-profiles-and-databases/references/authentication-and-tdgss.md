# Authentication and TDGSS Reference

> Sources: 541-0004998-D02 "Security: User Authentication and Directory Integration", 541-0011029-A02 "TDNEGO: Single Mechanism to Log On"

---

## 1. TDGSS Overview

Teradata Database Generic Security Services (TDGSS) is based on GSS-API (IETF RFC 2743/2744). It provides security services between Client applications and the Gateway (or Unity) on the Teradata Server.

### TDGSS Packages
| Package | Platform | Description |
|---------|----------|-------------|
| **Tdgss** | Teradata Server | C code implementation running on the Teradata Database (Gateway) |
| **Teragss** | C code Clients | Supports CLI, ODBC, and other C code based Clients |
| **TERAGSSJAVA** | Java Clients | Embedded in the Teradata JDBC Driver |
| **TERAGSSNET** | Windows .NET | Embedded in the Teradata .NET Data Provider |

### Security Mechanisms
| Mechanism | Type | Description |
|-----------|------|-------------|
| **TD2** | Non-authenticating | Teradata Method 2; default mechanism; credentials verified by the database after context establishment |
| **ldap** | Authenticating | Uses external LDAP directory for authentication and optional authorization |
| **KRB5** | Authenticating | Kerberos Version 5; authenticates at a Key Distribution Center (KDC) |
| **SPNEGO** | Authenticating | Simple and Protected GSSAPI Negotiation; supports Kerberos from Windows .NET clients |
| **TDNEGO** | Pseudo-mechanism | Negotiates best mechanism automatically; does not provide security services itself |
| **PROXY** | Special purpose | Connections between Unity Servers and Teradata Databases only; not available for TDNEGO negotiation |

### Four Security Services
1. **Authentication** — Confirming that user credentials are valid
2. **Authorization** — Specifying what resources the user is allowed to use
3. **Confidentiality** — Encrypting message contents (unreadable to third parties)
4. **Integrity** — Guaranteeing message contents have not changed

### Security Context Establishment
Context establishment is a multi-step token exchange between Client and Gateway:
1. Client calls `tdgss_init_sec_context` → generates mechanism-specific context token
2. Client sends token to Gateway
3. Gateway calls `tdgss_accept_sec_context` → generates new context token
4. Gateway sends token to Client
5. Repeat until both sides have established a security context

Authentication and authorization happen during context establishment. Confidentiality and integrity services operate after context establishment.

---

## 2. Mechanism Ranking

Each mechanism has a numeric **MechanismRank** property. Lower rank = higher priority.

### Factory Default Ranks and Sort Order
| Priority | Mechanism | Authenticating | Rank |
|----------|-----------|----------------|------|
| 1 | KRB5 | Yes | 40 |
| 2 | SPNEGO | Yes | 65 |
| 3 | ldap | Yes | 70 |
| 4 | TD2 | No | 20 |

Authenticating mechanisms always sort above non-authenticating mechanisms regardless of numeric rank. Within each group, lower rank value = higher priority. TD2 has rank 20 but sorts last because it is non-authenticating.

### DefaultMechanism vs DefaultNegotiatingMechanism
- **DefaultMechanism** — Any mechanism can be set; factory default is TD2 at the Teradata Database, none at Client
- **DefaultNegotiatingMechanism** — Only negotiating mechanisms eligible (currently only TDNEGO); factory default is none
- If both are defined, DefaultNegotiatingMechanism is used when a common negotiating mechanism exists at both Client and Server; otherwise DefaultMechanism is used
- Setting TDNEGO as DefaultMechanism is **not recommended** (breaks logon to systems that don't support TDNEGO)
- Setting TDNEGO as DefaultNegotiatingMechanism **is recommended** for making TDNEGO a default

### Mechanism Selection Priority
1. If a security mechanism is explicitly specified, use it
2. If not, and a default mechanism is specified at the Client, use it
3. If not, and a default mechanism is specified at the Teradata Database, use it

---

## 3. TDNEGO

### Purpose
TDNEGO is a pseudo-mechanism that negotiates between Client and Teradata Database to automatically select the best security mechanism for each session. It is based on IETF RFC 4178 (SPNEGO protocol), modified and extended for Teradata.

### TDNEGO OID
```
1.3.6.1.4.1.28698.4.302.1.3
```
Breakdown: `1{iso}.3{org}.6{dod}.1{internet}.4{private}.1{enterprise}.28698{Teradata}.4{td-products}.302{TDGSS}.1{Mechanisms}.3{TDNEGO}`

### NegotiatedMechanism OIDs
| Mechanism | OID |
|-----------|-----|
| KRB5 | `1.2.840.113554.1.2.2` |
| SPNEGO | `1.3.6.1.5.5.2` |
| ldap | `1.3.6.1.4.1.191.1.1012.1.20` |
| TD2 | `1.3.6.1.4.1.191.1.1012.1.1.9` |

### Negotiated Mechanisms Per Package
- **Tdgss** (Server): KRB5, SPNEGO, ldap, TD2
- **Teragss** (C Client): KRB5, ldap, TD2
- **TERAGSSJAVA** (Java): KRB5, ldap, TD2
- **TERAGSSNET** (.NET): SPNEGO, ldap, TD2

### Negotiation Steps
1. Both Client and Server get the list of negotiable mechanisms from TDGSS Configuration Files
2. Sort list: authenticating mechanisms first, then by MechanismRank (ascending)
3. Client obtains credentials and first context token for each mechanism in parallel
4. Failed mechanisms are rejected; rejection is communicated to peer in next token
5. Mechanism tokens are bundled in TDNEGO context token and sent to Server
6. Server applies user policy from External Directory; disallowed mechanisms rejected
7. Server performs next context establishment step for remaining mechanisms
8. Steps repeat until the top available mechanism completes context establishment
9. Either Client or Server can select the mechanism; whichever completes first wins
10. Selected mechanism is communicated to peer in final token
11. TDNEGO passes selected mechanism to Gateway via `mech_type` output of `tdgss_accept_sec_context`

### Key Use Cases
- **SSO**: User selects TDNEGO without credentials; gets an SSO-capable mechanism if available
- **Policy-driven**: External Directory policy restricts user to specific mechanisms; TDNEGO enforces this
- **Legacy interop**: Old Client with new Server — TDNEGO not offered; old mechanisms work as before. New Client with old Server — Client sees TDNEGO is unsupported, falls back
- **BTEQ with name/password**: `.logon MySystem/joe,joe_password` — TDNEGO determines mechanism that can authenticate "joe"
- **BTEQ with user mapping**: `.logdata user=joe` then `.logon MySystem/dir_user,dir_password`

### Performance
- TDNEGO adds overhead only at logon time; no impact after session established
- Remove unused mechanisms from negotiation list to improve performance
- Preference order matters: if ldap is preferred above KRB5, every KRB5 logon waits for ldap to fail first

---

## 4. LDAP Mechanism Configuration

### Key TdgssUserConfigFile.xml Properties

```xml
<Mechanism Name="ldap">
    <MechanismProperties
        MechanismEnabled="yes"
        AuthorizationSupported="no|yes"
        MechanismRank="70"
        DefaultMechanism="no"

        LdapServerName="ldap://server/"
        LdapServerRealm=""
        LdapSystemFQDN=""
        LdapUserBaseFQDN=""
        LdapGroupBaseFQDN=""
        LdapBaseFQDN=""              <!-- deprecated -->
        LdapServerPort="389"         <!-- deprecated -->

        LdapClientMechanism="simple"
        LdapClientUseTls="yes"
        LdapClientTlsReqCert="never|allow|try|demand|hard"
        LdapClientTlsCACert="/path/to/ca-cert.pem"
        LdapClientTlsCACertDir="/path/to/certs/"
        LdapClientTlsCert="/path/to/client-cert.pem"
        LdapClientTlsKey="/path/to/client-key.pem"
        LdapClientTlsCRLCheck="none|peer|all"
        LdapClientSaslSecProps="minssf=1"

        LdapServiceFQDN="cn=teradata,ou=services,dc=site"
        LdapServicePassword="secret"
        LdapServicePasswordProtected="no"
        LdapAllowUnsafeServerConnect="yes"
        />
</Mechanism>
```

### Property Descriptions
| Property | Description |
|----------|-------------|
| `LdapServerName` | LDAP URI(s) or DNS SRV RR name. Space-separated list for fault tolerance |
| `LdapClientMechanism` | `SASL/DIGEST-MD5` (default) or `simple` |
| `LdapClientUseTls` | Enable TLS (`yes`/`no`) |
| `LdapClientTlsReqCert` | Certificate verification level: `never`, `allow`, `try`, `demand`, `hard` |
| `LdapClientTlsCACert` | Path to CA certificate file (PEM format) |
| `LdapSystemFQDN` | DN of the Teradata system entry in the directory (for authorization mode) |
| `LdapUserBaseFQDN` | DN superior to user objects (required for Active Directory with DIGEST-MD5) |
| `LdapGroupBaseFQDN` | DN superior to directory groups (required for authorization mode) |
| `LdapServiceFQDN` | Service bind DN for identity searches |
| `LdapServicePassword` | Password for service bind |
| `AuthorizationSupported` | `yes` enables authorization mode; `no` for authentication-only |
| `LdapClientSaslSecProps` | SASL security properties; `minssf=1` prevents MITM on DIGEST-MD5 |

### LDAP URI Schemes
| Scheme | Port | Meaning |
|--------|------|---------|
| `ldap` | 389 | LDAP with or without TLS |
| `ldaps` | 636 | LDAP through SSL |
| `gc` | 3268 | Windows Global Catalog via LDAP |
| `gcs` | 3269 | Windows Global Catalog via SSL |

### Directory Server Configuration
**DNS SRV RR (best practice)**:
```xml
LdapServerName="_ldap._tcp.example.com"
```

**Fault-tolerant primary-backup**:
```xml
LdapServerName="ldap://server1/ ldap://server2/"
```

**Site-aware DNS SRV RR** (Windows domains):
```
_ldap._tcp.sitename._sites.domain-name
```

### Binding Methods

**SASL/DIGEST-MD5** (default):
- Challenge-response protocol; password never sent in plaintext
- Requires WHO-AM-I extended operation support (except Active Directory, eDirectory)
- Vulnerable to MITM on QoP list unless `minssf≥1`
- Password storage concern: directory stores plaintext or reversible hash

**Simple binding**:
- User DN and plaintext password sent to directory
- Requires TLS or SSL for security
- All directories support simple binding
- Set `LdapClientMechanism="simple"`

### Certified Directory Servers
**DIGEST-MD5 and simple binding**: Active Directory (Win 2003), Sun Java System DS 5.2, OpenLDAP 2.1+, Novell eDirectory 8.8 SP2

**Simple binding only**: ADAM, AD LDS, Active Directory (Win 2000)

---

## 5. Identity Maps and Canonicalization

Canonicalization converts a simple username into the FQDN or search required by the directory.

### Identity Map
Regex-based pattern matching to construct a DN directly from the username:
```xml
<IdentityMap
    Match="([^\.=@]+)@([^\.=]+)"
    Pattern="uid=${1},ou=people,ou=${2},dc=site"/>
```
Example: `diperm01@testing` → `uid=diperm01,ou=people,ou=testing,dc=site`

### Identity Search
When users are scattered in the directory, search for the DN:
```xml
<IdentitySearch
    Match="([^\.=@]+)@([^\.=]+)"
    Base="ou=${2},dc=site"
    Scope="subtree"
    Filter="(uid=${1})"/>
```
Requires a **service bind** (`LdapServiceFQDN`/`LdapServicePassword`) unless the directory allows anonymous searches.

### Substitution Variables
- `${0}` — entire authcid
- `${1}` through `${50}` — captured substrings from parenthesized groups in Match pattern
- `${result}` — result of the canonicalization (available only in `BindName` attribute)

### Processing Rules (14.0+)
1. All canonicalizations whose Match pattern completely consumes the authcid are "in play"
2. Identity maps are tried until one binds successfully or an identity search is reached
3. If an identity search is processed, authentication succeeds or fails based on that search
4. If all canonicalizations fail, authentication fails

### DatabaseName Attribute
Rewrites the Teradata Database username (authentication-only mode):
```xml
<IdentitySearch
    Match="(.+)\\(.+)"
    Base="dc=${1},dc=teradata,dc=com"
    Scope="subtree"
    Filter="(samaccountname=${2})"
    DatabaseName="${1}_${2}"/>
```
`td\dl160010` → database user becomes `td_dl160010`

### BindName Attribute
Rewrites the bind name for DIGEST-MD5 with directories that require prefixed names:
```xml
<IdentitySearch
    Match="(.+)\\(.+)"
    Base="dc=${1},dc=teradata,dc=com"
    Scope="subtree"
    Filter="(uid=${2})"
    BindName="dn:${result}"/>
```

---

## 6. Authorization Mode

When `AuthorizationSupported="yes"`, the directory maps directory users to Teradata users, profiles, and roles.

### Directory Structure (DIT)
```
ou=tdat,dc=example,dc=com                    ← Root node (organizationalUnit)
  └── ou=xyz,ou=tdat,dc=example,dc=com       ← System entry (ou = system name)
        ├── ou=users,...                       ← Users container
        │     └── cn=perm01,...               ← Teradata user (groupOfNames)
        ├── ou=profiles,...                    ← Profiles container
        │     └── cn=profperm01,...           ← Teradata profile (groupOfNames)
        └── ou=roles,...                      ← Roles container
              └── cn=extrole01,...            ← Teradata role (groupOfNames)
```

### User Mapping
Directory user → Teradata user via `member` attribute in groupOfNames entry under `ou=users`:
```
cn=perm01,ou=users,ou=xyz,ou=tdat,dc=example,dc=com
  member: uid=diperm01,ou=principals,dc=example,dc=com
```
- Teradata user must exist in DB and have `GRANT LOGON...WITH NULL PASSWORD`
- Multiple directory users can map to one Teradata user (many-to-one)

### Profile Mapping
Directory user → Teradata profile via `member` attribute in groupOfNames entry under `ou=profiles`:
```
cn=profperm01,ou=profiles,ou=xyz,ou=tdat,dc=example,dc=com
  member: uid=diperm01,ou=principals,dc=example,dc=com
```
- Directory profile takes precedence over DB-defined profile

### Role Mapping
Directory group → Teradata role via `member` attribute in groupOfNames entry under `ou=roles`:
```
cn=extrole01,ou=roles,ou=xyz,ou=tdat,dc=example,dc=com
  member: cn=xu1,ou=groups,dc=example,dc=com    ← points to directory group
```
- The directory group contains `member` entries pointing to directory user FQDNs
- Maximum 50 roles per user (DBS table limitation)
- Created with `CREATE EXTERNAL ROLE` in Teradata

### Authentication-Only vs Authorization Mode
| Feature | Auth-Only | Authorization |
|---------|-----------|---------------|
| `AuthorizationSupported` | `no` | `yes` |
| Schema extensions | Not required | Not required (uses core LDAP) |
| DIT modifications | Not required | Teradata structure required |
| User naming | Tied to directory identity | Flexible mapping |
| Centralized roles/profiles | No | Yes |

### Lightweight Authorizations (AuthSearch/AuthSearchMap)
Introduced for use with mechanisms other than LDAP (e.g., KRB5, SPNEGO):

```xml
<AuthSearch Name="roles"
    MemberAttribute="member"
    ObjectClass="groupOfNames"
    NamingAttribute="cn"
    Base="ou=groups,dc=example,dc=com"
    Scope="subtree"/>

<AuthSearchMap Name="rolefilter"
    AuthSearch="roles"
    Scope="subtree"
    Base="ou=tdroles,dc=example,dc=com"
    Filter="(member=${result})"/>
```

**AuthSearch properties**: `Name`, `MemberAttribute`, `ObjectClass`, `NamingAttribute`, `Base`, `Scope`
**AuthSearchMap properties**: `Name`, `AuthSearch`, `Scope`, `Base`, `Filter`

---

## 7. SSL/TLS for LDAP

### Enabling TLS
```xml
LdapClientUseTls="yes"
LdapServerName="ldap://myserver/"
```

### Enabling SSL (deprecated)
```xml
LdapServerName="ldaps://myserver/"
```
Or with DNS SRV: `_ldaps._tcp.mydomain`

### Certificate Verification Levels (`LdapClientTlsReqCert`)
| Value | Behavior |
|-------|----------|
| `never` | No verification; obfuscation only |
| `allow` | Certificate requested; connection proceeds if absent or invalid |
| `try` | Certificate requested; connection aborted only if certificate is present and invalid |
| `demand` / `hard` | Certificate required and must be valid; connection aborted otherwise |

### Key SSL/TLS Configuration Properties
| Property | Description |
|----------|-------------|
| `LdapClientUseTls` | Enable TLS (`yes`/`no`) |
| `LdapClientTlsReqCert` | Certificate verification level |
| `LdapClientTlsCACert` | Path to CA certificate (PEM format) |
| `LdapClientTlsCACertDir` | Directory containing CA certificates |
| `LdapClientTlsCert` | Path to client certificate |
| `LdapClientTlsKey` | Path to client private key |
| `LdapClientTlsCRLCheck` | CRL checking: `none`, `peer`, `all` |
| `LdapAllowUnsafeServerConnect` | Allow unverified connections |

### Best Practices
- TLS preferred over SSL (SSL is deprecated by LDAP standards)
- Use fully qualified DNS names in URIs (not IP addresses) when using DIGEST-MD5, SSL, or TLS
- Certificates must be PEM format; convert DER/CER with: `openssl x509 -in cert.der -inform DER -out cert.pem -outform PEM`
- Client keys must not be password-protected

---

## 8. Multi-Domain LDAP

Allows a single TDGSS configuration to authenticate users against multiple directory domains.

### Rules
- The `<Tls>` element applies to all services
- Each `<Service>` section defines an independent directory configuration with its own server, binding method, and identity maps
- Canonicalizations in the mechanism's main section apply globally; canonicalizations in a Service section are local

### Configuration Structure
```xml
<Mechanism Name="ldap">
    <MechanismProperties ... />

    <Tls LdapClientUseTls="yes" LdapClientTlsReqCert="demand"
         LdapClientTlsCACert="/path/to/ca.pem"/>

    <Service Name="domain1"
        LdapServerName="ldap://dc1.domain1.com/"
        LdapClientMechanism="simple"
        LdapServiceFQDN="cn=svc,dc=domain1,dc=com"
        LdapServicePassword="secret">
        <IdentityMap Match="(.+)@domain1\.com"
            Pattern="cn=${1},ou=users,dc=domain1,dc=com"/>
    </Service>

    <Service Name="domain2"
        LdapServerName="ldap://dc2.domain2.com/"
        LdapClientMechanism="SASL/DIGEST-MD5">
        <IdentityMap Match="(.+)@domain2\.com"
            Pattern="uid=${1},ou=people,dc=domain2,dc=com"
            BindName="dn:${result}"/>
    </Service>
</Mechanism>
```

### Use Cases
- Primary: Authenticate users from multiple directory domains
- Migration: Transition from one directory to another
- Unifying LDAP authorization configuration across domains

---

## 9. Client Authentication

### BTEQ
```
.logon MySystem/username,password                     -- uses default mechanism
.SET LOGMECH LDAP                                     -- select mechanism
.logon MySystem/username,password                     -- logon with LDAP
.logdata user=tduser                                  -- optional: map to TD user
.logon MySystem/dir_user,dir_password
```

### CLI (Call Level Interface)
```c
/* Legacy LDAP login */
logdata = "authcid=diperm01@@realm";
logmech = "LDAP";

/* UPN style */
logdata = "";  /* empty or omitted */
username = "diperm01@testing";
logmech = "LDAP";
```

### JDBC
```
jdbc:teradata://MySystem/LOGMECH=LDAP,USER=diperm01,PASSWORD=secret
jdbc:teradata://MySystem/LOGMECH=TDNEGO
```
Connection properties: `LOGMECH=`, `USER=`, `PASSWORD=`, `LOGDATA=`

### ODBC
Configure via DSN setup dialog:
- Data Source Name → Authentication Mechanism → select LDAP or TDNEGO
- Or set `AuthenticationMechanism=LDAP` in connection string

### .NET Data Provider
```csharp
TdConnection conn = new TdConnection();
conn.ConnectionString = "Data Source=MySystem;User ID=diperm01;" +
    "Password=secret;Authentication Mechanism=LDAP;";
conn.Open();
```

---

## 10. tdsbind Testing Tool

### Syntax
```bash
tdsbind -u username [-m mechanism]
```

### Common Options
| Option | Description |
|--------|-------------|
| `-u username` | Specify the user (authcid) to test |
| `-m mechanism` | Specify the mechanism (default: configured mechanism) |

### Output Fields
| Field | Description |
|-------|-------------|
| `FQDN` | Fully qualified DN of the authenticated principal |
| `AuthUser` | LDAP URI with DN and server that authenticated the user |
| `DatabaseName` | The Teradata username that will be associated with the session |
| `Service` | Service that authenticated (`tdsbind` = mechanism's own config) |
| `Users` | Mapped Teradata user(s) |
| `Profiles` | Mapped Teradata profile(s) |
| `Roles` | Mapped Teradata external role(s) |

### Configuration Properties Displayed
tdsbind displays: `LdapGroupBaseFQDN`, `LdapUserBaseFQDN`, `LdapSystemFQDN`, `LdapServerName`, `LdapServerPort`, `LdapClientUseTls`, `LdapClientTlsReqCert`, `LdapClientMechanism`, `LdapServiceFQDN`, `LdapServicePasswordProtected`, `LdapServicePassword` (shows "configured"), `LdapServiceBindRequired`, `LdapClientTlsCRLCheck`, `LdapAllowUnsafeServerConnect`, `AuthorizationSupported`

---

## 11. TDGSS Configuration Files

### TdgssLibraryConfigFile.xml
- Provided with each TDGSS release; **must never be edited**
- Contains factory defaults for all mechanisms
- Contains mechanism attributes (Name, ObjectId, LibraryName, Prefix, InterfaceType)

### TdgssUserConfigFile.xml
- Meant to be edited by the user; preserved across version switches
- Override properties from the Library config
- TDNEGO section is shipped commented out (uncomment to modify)
- After editing: run `run_tdgssconfig` script, then `tpareset` for Tdgss changes to take effect
- For Teragss (client): changes are active for all new client processes automatically

### TDNEGO Configuration in TdgssUserConfigFile.xml
```xml
<Mechanism Name="TDNEGO">
    <MechanismProperties
        MechanismEnabled="yes"
        DefaultMechanism="no"
        DefaultNegotiatingMechanism="no"
        MechanismRank="10"
        />
    <NegotiatedMechanism ObjectId="1.2.840.113554.1.2.2" Enable="yes"/>  <!-- KRB5 -->
    <NegotiatedMechanism ObjectId="1.3.6.1.5.5.2" Enable="yes"/>        <!-- SPNEGO -->
    <NegotiatedMechanism ObjectId="1.3.6.1.4.1.191.1.1012.1.20" Enable="yes"/>  <!-- ldap -->
    <NegotiatedMechanism ObjectId="1.3.6.1.4.1.191.1.1012.1.1.9" Enable="yes"/> <!-- TD2 -->
</Mechanism>
```

**TERAGSSNET exception**: Uses `NegotiatedMechanismName` instead of `ObjectId`:
```xml
<NegotiatedMechanism NegotiatedMechanismName="1.3.6.1.4.1.191.1.1012.1.1.9" Enable="yes"/>
```

### Java Configuration
- `TdgssLibraryConfigFile.xml` in `tdgssjava.jar`; `TdgssUserConfigFile.xml` in `tdgssconfig.jar`
- TDNEGO section shipped commented out; uncomment to modify

### Enabling External Authentication
```bash
gtwcontrol -a ON          # Enable external auth in Gateway
dbscontrol: m g 26 0      # Enable external auth in DBS
```

---

## 12. Troubleshooting

### Common LDAP Errors
| Error | Cause |
|-------|-------|
| Error 8068 "External Authentication is not allowed" | `gtwcontrol -a ON` or `dbscontrol m g 26 0` not run |
| CLI error 244 "SSO logon failed by gateway" | Various auth failures; use `tdsbind` to diagnose |
| `0xe3000215` in Gateway log | LDAP failure; check canonicalization, directory connectivity |
| `tdsldap_bind: Directory error - Invalid DN syntax` | Canonicalization failed; identity search returned 0 or >1 objects |
| CLI error 507 `BADLOGMECH` | Requested mechanism not supported at Teradata Database |

### TDNEGO Negotiation Failures
- Mechanisms not available or disabled at Client or Server
- Policy in External Directory cannot be satisfied
- Incorrect logon credentials
- SSO attempted but no SSO-capable mechanism available

### TDNEGO Negotiation Log
Enable at Gateway: `gtwcontrol -N`
Log location: `/var/opt/teradata/tdtemp/gtw`
System log: `/var/log/messages`

**TERAGSSJAVA**: `com.teradata.tdgss.logging.level=INFO` (in tdgsslogging.properties or `-D` JVM arg)

**TERAGSSNET**: Add to application config file:
```xml
<system.diagnostics>
    <switches>
        <add name="TDNEGO" value="3"/>
    </switches>
</system.diagnostics>
```

### Log Record Fields
| Field | Description |
|-------|-------------|
| `Mechanism` | Mechanism this record concerns |
| `MechState` | `Available`, `Selected`, or `Rejected` |
| `MechReason` | `Available`, `GSSAPI Error`, `Not Available at Client/Server`, `Due to Policy`, `Due to Rank`, `SSO Required`, `Authorization Required` |
| `GSS MajorStatus` | RFC 2744 major status (hex); `000D0000` = unspecified failure |
| `GSS MinorStatus` | Mechanism-specific minor status (hex) |
| `IsCtxEstablished` | Whether context establishment is complete for this mechanism |
| `IsPolicyApplied` | Whether External Directory policy has been applied |
| `NegState` | `Completed`, `Incomplete`, or `Reject` |
| `Elapsed Time` | Milliseconds since negotiation start |

### SSL/TLS Troubleshooting
| Error | Resolution |
|-------|------------|
| `hostname does not match CN in peer certificate` | Use FQDN in LdapServerName, not IP address |
| `certificate verify failed` | Install correct CA certificate; check `LdapClientTlsCACert` path |
| `self signed certificate` | Install self-signed cert as CA cert |
| `unable to get local issuer certificate` | Missing intermediate or root CA certificate in chain |

### Gateway gtwglobal
Starting in Release 16.0, `gtwglobal di sess nnnn` shows negotiating mechanism:
```
Partition        Authentication NegotiatingMechanism
---------------- -------------- --------------------
DBC/SQL          ldap           TDNEGO
```

---

## 13. Data Dictionary

### DBC.SessionTbl
Contains LDAP-related columns for active sessions:
- Authentication mechanism used
- AuthUser URI (directory server and user DN)

### DBC.EventLog
Records authentication events including:
- LDAP authentication successes and failures
- Mechanism-specific error information
- Gateway error codes (e.g., `0xe3000215` for LDAP failures)
