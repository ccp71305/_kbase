# ION-16417 — partner-integrator: clear the OWASP CRITICAL/HIGH findings

**Date:** 2026-09-02
**Branch:** `feature/ION-16417-pi-owasp-issue-fix` (off `develop`)
**Modules:** `partner-integrator` (reactor pom) — the dependency pins flow to every deployable module
through the reactor pom.
**Follows the pattern established for visibility:**
`visibility/docs/2026-08-31-visibility-owasp-refactor.md` and
`visibility/docs/2026-09-01-visibility-lambda-owasp.md`.
**Related:** PI AWS SDK 1.x→2.x upgrade (already on `develop`, commit `8bba065f0e` and follow-ups);
MCP Context session `1ec936447f7145c6` (this work), `59a4c1b2109b487d` (PI AWS upgrade).

---

## 1. Summary

The partner-integrator module was upgraded to the cloud-sdk libraries on commons `1.0.33-SNAPSHOT`
(ION-16417, already merged to `develop`). The Jenkins OWASP dependency-check scans of the seven
deployable PI packages still report CRITICAL/HIGH findings that are identical in nature to the ones
cleared in visibility, because the deployables pull the same third-party stack (Jetty via
`dropwizard-core`, `httpclient5`, `jackson-databind`, `guava`, `jsoup`, …).

**This document covers three rounds of work on this branch:**
1. **Jetty** (§2–§6) — the first finding, done first as requested.
2. **The remaining dependency findings** (§8) — httpclient5 CRITICAL, guava, gson, logback (jsoup and
   jackson-databind deliberately left under the code-freeze release exception).
3. **A latent, pre-existing lambda cold-start bug** (§9) found while boot-checking the lambdas —
   unrelated to OWASP, but fixed here because it would break `pi-bl-es-lambda` when the AWS upgrade rolls
   to QA/prod.

| # | Round | Change | Where | Closes |
|---|---|---|---|---|
| 1 | Jetty | Import `jetty-bom` + `jetty-ee10-bom` at **12.1.12** | `partner-integrator/pom.xml` | CVE-2026-10050 (HIGH 9.1), CVE-2026-10051 (MED) |
| 2 | Deps | Pin `httpclient5` **5.6.4** | `partner-integrator/pom.xml` | CVE-2026-71290 (CRITICAL 9.1), CVE-2026-40542 (HIGH) |
| 3 | Deps | Pin `guava` **33.5.0-jre** | `partner-integrator/pom.xml` | CVE-2023-2976 (HIGH) |
| 4 | Deps | Pin `gson` **2.10.1** | `partner-integrator/pom.xml` | CVE-2022-25647 (HIGH) |
| 5 | Deps | Pin `logback-core`+`logback-classic` **1.5.38** (aligned) | `partner-integrator/pom.xml` | CVE-2026-13006 (HIGH) |
| 6 | Deps | Exclude `jetty-setuid-jna` (removes `jna-jpms` false positive) | `pi-lambda-streamToSns/pom.xml` | jna-jpms HIGH (false positive) |
| 7 | Latent | Add `aws-java-sdk-core` **1.12.730** (restores `AwsRegionProvider`) | `pi-bl-es-lambda/pom.xml` | NoClassDefFoundError at Lambda cold start |

Deliberately **left** under the two-week release exception (code freeze), unchanged: `jsoup` 1.17.2
(CVE-2026-75140) and `jackson-databind` (CVE-2026-68497). Nothing about the runtime behaviour of any PI
module changes except the intended one in §9.

---

## 2. The Jetty finding — root cause

### 2.1 What OWASP reported

`CVE-2026-10050` (Jetty Digest authentication, CVSS v3 **9.1**, **HIGH**) and its companion
`CVE-2026-10051` (HTTP/1.1 trailer bleed, MEDIUM) affect Jetty `12.1.x` below `12.1.10`. The 26.09
scans of the PI deployables report `CVE-2026-10050` against these shaded artifacts, all at **12.1.9**:

| Module (deployable) | Jetty artifacts flagged @ 12.1.9 |
|---|---|
| `pi-booking-processor` | `jetty-server`, `jetty-util`, `jetty-security`, `jetty-ee10-servlet` |
| `pi-si-in-processor` | `jetty-server`, `jetty-util`, `jetty-security`, `jetty-ee10-servlet` |
| `pi-si-out-processor` | `jetty-server`, `jetty-util`, `jetty-security`, `jetty-ee10-servlet` |
| `pi-statusevents-out-processor` | `jetty-server`, `jetty-util`, `jetty-security`, `jetty-ee10-servlet` |
| `pi-lambda-streamToSns` | `jetty-io`, `jetty-server` (and 5 more) |
| `pi-bl-es-lambda` | **none** — the lambda already excludes all of `org.eclipse.jetty*` |
| `pi-bl-in-processor` | **not flagged** in the `PIBL_IN` scan — treated as OK |

> Note on `pi-bl-in-processor`: it is a Dropwizard application (`BLPIApplication`) and does bundle Jetty,
> but its `PIBL_IN-26.09.001` OWASP scan does **not** report `CVE-2026-10050`, so it is already OK from
> the CI perspective. The reactor pin still lifts any Jetty it carries to 12.1.12 as a harmless
> side-effect, keeping every PI service on one Jetty release.

Confirmed against the authoritative **Jenkins OWASP scans** (`~/Downloads`, build 26.09.00x):
`CVE-2026-10050` is **present** in `PIBK`, `PISI_IN`, `PISI_OUT`, `PISE_OUT` and `PI_StreamToSNS`, and
**absent** in `PIBL_IN` and `PIBL_ES_Lambda` — exactly matching the table above. In `PI_StreamToSNS`
the scan lists `jetty-ee10-servlet`, `jetty-http`, `jetty-io`, `jetty-security`, `jetty-server`,
`jetty-session` and `jetty-util`, all at `12.1.9`.

| Jenkins report | Module |
|---|---|
| `PIBK-26.09.002-OWASP.html` | `pi-booking-processor` |
| `PISI_IN-26.09.002-OWASP.html` | `pi-si-in-processor` |
| `PISI_OUT-26.09.002-OWASP.html` | `pi-si-out-processor` |
| `PISE_OUT-26.09.002-OWASP.html` | `pi-statusevents-out-processor` |
| `PI_StreamToSNS-26.09.001-OWASP.html` | `pi-lambda-streamToSns` |
| `PIBL_IN-26.09.001-OWASP.html` | `pi-bl-in-processor` (no Jetty) |
| `PIBL_ES_Lambda-26.09.001-OWASP.html` | `pi-bl-es-lambda` (no Jetty) |

### 2.2 Why 12.1.9 was winning

commons `1.0.33-SNAPSHOT` pins Jetty **12.1.12** in its own dependencies, but the PI deployables reach
that pin only transitively and at depth. `cloud-sdk-api` is a *direct* dependency of each deployable and
brings **`dropwizard-core` 5.0.2, which declares Jetty 12.1.9 from a nearer path**. Maven's
nearest-wins resolution therefore picked 12.1.9 for the artifacts Dropwizard names, leaving a genuinely
mixed/vulnerable set on the classpath.

`dependency:tree` on `pi-si-out-processor` before the fix showed `jetty-server`, `jetty-util`,
`jetty-security` and `jetty-ee10-servlet` at 12.1.9.

---

## 3. The fix

A `<dependencyManagement>` import of both Jetty BOMs at 12.1.12 was added to the PI reactor pom. A
single-artifact pin would not be enough — Dropwizard pulls ~10 Jetty artifacts and the BOM is the only
thing that settles *all* of them (including the ones nothing names directly) at one release:

```xml
<!-- partner-integrator/pom.xml -->
<properties>
    ...
    <jetty.version>12.1.12</jetty.version>
</properties>

<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.eclipse.jetty</groupId>
            <artifactId>jetty-bom</artifactId>
            <version>${jetty.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
        <dependency>
            <groupId>org.eclipse.jetty.ee10</groupId>
            <artifactId>jetty-ee10-bom</artifactId>
            <version>${jetty.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
        <!-- existing jackson-bom / aws-lambda-events / cloud-sdk entries unchanged -->
    </dependencies>
</dependencyManagement>
```

After the change, `dependency:tree` shows **every** Jetty artifact at 12.1.12 in both a DW service and
the lambda that bundles Jetty:

```
pi-si-out-processor:
  jetty-security  12.1.12   jetty-server 12.1.12   jetty-util 12.1.12
  jetty-http 12.1.12   jetty-io 12.1.12   jetty-session 12.1.12
  jetty-ee10-servlet 12.1.12   jetty-ee10-servlets 12.1.12

pi-lambda-streamToSns:
  jetty-io 12.1.12   jetty-http 12.1.12   jetty-security 12.1.12
  jetty-server 12.1.12   jetty-session 12.1.12   jetty-util 12.1.12
  jetty-ee10-servlet 12.1.12
```

---

## 4. Backward compatibility

* **Patch-level bump only.** 12.1.9 → 12.1.12 is inside the same 12.1 minor line; the Jetty 12.1 public
  API is unchanged, so no PI code, resource or config needs to change.
* **No dependency added or removed.** The `dependencyManagement` block only overrides version selection.
  Every module keeps exactly the same artifact set; the four/two flagged artifacts simply move up three
  patch releases.
* **Lambdas that exclude Jetty are unaffected.** `pi-bl-es-lambda` excludes all of `org.eclipse.jetty*`
  from `commons`/`cloud-sdk-api`/`cloud-sdk-aws`, so it has no Jetty on its classpath and the pin is a
  no-op for it. `pi-lambda-streamToSns` does bundle Jetty (it does not exclude it) and is lifted to
  12.1.12 like the DW services.
* **commons already wanted 12.1.12.** The pin aligns the PI reactor with the version commons
  `1.0.33-SNAPSHOT` already declares, so it cannot introduce a version the rest of the platform has not
  already validated.

---

## 5. Remaining OWASP findings (identified — to be addressed next)

Captured from the current `owasp-reports/pi-*/dependency-check-report.json`. Left untouched in this
round per the "Jetty first" instruction; they mirror the visibility fixes and the two library findings
carried under the code-freeze release exception.

| Dependency | Version | Severity | CVE | Affected PI modules | Planned action |
|---|---|---|---|---|---|
| `httpclient5` | 5.4.4 | **CRITICAL** | CVE-2026-71290 (+ HIGH CVE-2026-40542) | all DW services + `pi-bl-es-lambda`, `pi-bl-in-processor` | pin 5.6.4 (as visibility) |
| `guava` | 31.0.1-jre / 18.0 | HIGH | CVE-2023-2976 | `pi-si-in-processor`, `pi-bl-es-lambda`, `pi-lambda-streamToSns` | pin 33.5.0-jre (as visibility) |
| `jackson-databind` | 2.21.4 / 2.17.1 | HIGH | CVE-2026-68497 (+ 54512/54513 on 2.17.1) | all | assess bump / release exception |
| `jsoup` | 1.17.2 | HIGH | CVE-2026-75140 | DW services | assess (visibility carried under exception) |
| `gson` | 2.8.0 | HIGH | CVE-2022-25647 | `pi-lambda-streamToSns` | assess bump |
| `logback-core` | 1.5.33 | HIGH | CVE-2026-13006 | `pi-lambda-streamToSns` | assess bump |

---

## 6. Verification

All commands run with INT AWS credentials on the shell (SSO, `aws sts get-caller-identity` →
`arn:aws:sts::081020446316:...INTTRA-Dev-Engg...`). Concurrent Maven builds were deliberately avoided.

### 6.1 Tests — `mvn -f partner-integrator/pom.xml clean verify`

**BUILD SUCCESS** — all 8 modules, unit **and** integration (`*IT`, DynamoDB Local) tests, **0 failures /
0 errors**:

| Module | Result |
|---|---|
| partner-integrator | SUCCESS |
| pi-commons | SUCCESS |
| pi-booking-processor | SUCCESS (incl. `BookingDaoIT`, DynamoDB Local IT) |
| pi-statusevents-out-processor | SUCCESS |
| pi-lambda-streamToSns | SUCCESS |
| pi-si-in-processor | SUCCESS |
| pi-bl-in-processor | SUCCESS (incl. `BLFeedDynamoDbAdminCommandIT`) |
| pi-si-out-processor | SUCCESS |
| pi-bl-es-lambda | SUCCESS |

The shaded jars produced by the run bundle `jetty-*-12.1.12.jar` (server, util, security, http, io,
session, ee10-servlet/servlets) — confirmed from the shade plugin output — proving the pin takes effect
in the actual deployable artifacts, not just in `dependency:tree`.

### 6.2 Boot check — DW services + lambdas

**DW services** (`java -jar <shaded-jar>` with no args → Dropwizard bootstraps and prints its command
list; exit code 0 for each):

| Service | Boot result |
|---|---|
| pi-booking-processor | `Starting BookingPIApplication...` → `usage: ... {server,check}` — exit 0 |
| pi-si-in-processor | Dropwizard usage printed — exit 0 |
| pi-si-out-processor | Dropwizard usage printed — exit 0 |
| pi-statusevents-out-processor | Dropwizard usage printed — exit 0 |
| pi-bl-in-processor | `Starting BLPIApplication...` → `usage: ... {server,check,dynamo-create,re-index,create-index}` — exit 0 |

A successful no-arg run means the shaded Jetty 12.1.12 + Jersey classpath assembles and the Application
bootstraps with no `NoClassDefFoundError`/linkage error — the exact failure mode a bad Jetty bump would
produce.

**Lambdas** (handler class load + link from the shaded artifact via `jshell`):

| Lambda | Handler(s) | Result |
|---|---|---|
| pi-lambda-streamToSns | `StreamToSnSProcessor`, `StreamStatusEventsToSnsProcessor` | `LOADED` |
| pi-bl-es-lambda | `IndexerHandler` | `LOADED` |

`pi-bl-es-lambda` excludes Jetty entirely (pin is a no-op for it); `pi-lambda-streamToSns` carries Jetty
only as unused transitive weight, now at 12.1.12. Both handlers link cleanly.

### 6.3 OWASP re-scan (Jetty)

The `dependency:tree` proof (§3) plus the `jetty-*-12.1.12.jar` set in the shaded jars (§6.1) establish
that `CVE-2026-10050`/`CVE-2026-10051` (both fixed in Jetty ≥ 12.1.10) no longer apply. A full Jenkins
OWASP re-scan will confirm on the next CI run. Re-scanning the remaining findings (httpclient5 CRITICAL,
etc.) is deferred to the follow-up round per the "Jetty first" instruction.

---

## 7. Commands (with syntax explanation)

All commands are PowerShell on Windows, run from the repo root
`C:\Users\arijit.kundu\projects\mercury-services`.

### 7.1 Read the current findings from the existing OWASP JSON reports

```powershell
$mods='pi-bl-es-lambda','pi-bl-in-processor','pi-booking-processor','pi-lambda-streamToSns',
       'pi-si-in-processor','pi-si-out-processor','pi-statusevents-out-processor'
foreach($m in $mods){
  $j = Get-Content "owasp-reports\$m\dependency-check-report.json" -Raw | ConvertFrom-Json
  foreach($d in $j.dependencies){ foreach($v in $d.vulnerabilities){
    if($v.severity -match 'CRITICAL|HIGH'){ "{0,-9} {1,-16} {2}" -f $v.severity,$v.name,$d.fileName }
  }}
}
```
* `ConvertFrom-Json` parses each dependency-check JSON report.
* The nested loop walks `dependencies[].vulnerabilities[]` and prints only CRITICAL/HIGH rows with the
  CVE id and the flagged jar, giving the per-module baseline in §2.1.

### 7.2 Verify the Jetty version Maven resolves (before/after the pin)

```powershell
mvn -o dependency:tree -pl partner-integrator/pi-si-out-processor "-Dincludes=org.eclipse.jetty" |
  Select-String 'org\.eclipse\.jetty'
mvn -o dependency:tree -pl partner-integrator/pi-si-out-processor "-Dincludes=org.eclipse.jetty.ee10" |
  Select-String 'org\.eclipse\.jetty'
mvn -o dependency:tree -pl partner-integrator/pi-lambda-streamToSns "-Dincludes=org.eclipse.jetty" |
  Select-String 'org\.eclipse\.jetty'
```
* `-o` runs Maven **offline** (fast; everything needed is already in the local repo).
* `dependency:tree` prints the resolved dependency graph; `-Dincludes=<groupId>` filters it to only the
  matching coordinates so the Jetty rows are easy to read.
* `-pl <path>` selects a single module. **No `-am`** is needed here: `dependency:tree` only *resolves*
  (does not build) siblings, and the module's parent — the working-tree `partner-integrator/pom.xml`
  that carries the new pin — is read directly through its `<relativePath>`. Adding `-am` would drag the
  whole repo reactor (network, …) into the resolution and slow it down for no benefit.
* Quoting `"-Dincludes=..."` is required in PowerShell so the `.` and `,` are not reinterpreted.

> **Repo gotcha (from the visibility notes):** for `dependency:tree` / `help:effective-pom` probes that
> must reflect *working-tree* POM edits of an in-reactor sibling, either run the whole reactor or add
> `-am`. Here the edit is on the module's own **parent** pom, which is always read from disk via
> `relativePath`, so the single-module probe already sees the pin.

### 7.3 Build + run all tests (unit + integration) for the PI reactor

```powershell
mvn -f partner-integrator/pom.xml clean verify 2>&1 |
  Tee-Object -FilePath pi-verify.log |
  Select-String 'BUILD|Tests run|Building pi-|ERROR'
```
* `-f partner-integrator/pom.xml` builds just the partner-integrator reactor (its 8 modules), using the
  local repo for the already-installed `commons` / `cloud-sdk-*` `1.0.33-SNAPSHOT` artifacts.
* `verify` runs the full lifecycle including `maven-failsafe-plugin` (the `*IT` DynamoDB integration
  tests), so both unit and integration tests execute.
* `Tee-Object` keeps the full log on disk while `Select-String` surfaces the reactor summary lines.
* Requires INT AWS credentials on the shell (the `pi-booking-processor` build fetches
  `booking:3.0.0.M` from `s3://inttra-deployment` via the `aws-maven` extension). Confirm with
  `aws sts get-caller-identity`.

### 7.4 Boot check — DW services

```powershell
# each DW service is a shaded jar with a Dropwizard Application main class
java -jar partner-integrator/pi-si-out-processor/target/pi-si-out-processor-1.0.jar --help
```
* A successful `--help` (or `check <config.yml>`) proves the shaded Jetty 12.1.12 classpath assembles
  and the Application boots far enough to parse commands, without needing live queues.

### 7.5 Boot check — lambdas

```powershell
# the lambda handler class must load from the shaded/zip artifact
java -cp partner-integrator/pi-lambda-streamToSns/target/<shaded-or-zip> <HandlerFqcn>
```
* Lambdas have no server to start; the boot check is that the handler class and its (now 12.1.12) Jetty
  transitive classes load without `NoClassDefFoundError`/linkage errors.

### 7.6 OWASP re-scan for a module (optional, to confirm the Jetty CVE is gone)

```powershell
./dependency-check.sh partner-integrator/pi-si-out-processor   # repo helper; add --no-update to reuse NVD cache
```
* Rebuilds nothing; scans the shaded jar plus the module `suppressions.xml` and writes the report under
  `owasp-reports/`. The Jetty `CVE-2026-10050` rows should be gone and Jetty should read 12.1.12.

---

## 8. Round 2 — the remaining dependency findings

Added to the `partner-integrator/pom.xml` `<dependencyManagement>` (properties + managed versions),
mirroring the visibility fix. All are transitive-version floors: nothing adds or removes a dependency,
so every module keeps its dependency set — the flagged jars simply move to a fixed version.

| Library | Was | Now | Severity | CVE | Notes |
|---|---|---|---|---|---|
| `httpclient5` | 5.4.4 | **5.6.4** | CRITICAL | CVE-2026-71290 (+ HIGH CVE-2026-40542) | async TLS hostname-verification bypass, fixed 5.6.4; SCRAM bypass fixed 5.6.1 — 5.6.4 clears both. `httpcore5` stays 5.4.3 (5.6.4 is built against it). |
| `guava` | 31.0.1-jre / 18.0 | **33.5.0-jre** | HIGH | CVE-2023-2976 | `FileBackedOutputStream` temp-dir perms, fixed 32.0.0. 33.5.0-jre is the platform-standard version. |
| `gson` | 2.8.0 | **2.10.1** | HIGH | CVE-2022-25647 | `writeReplace()` deserialization DoS, fixed 2.8.9. Only `pi-lambda-streamToSns` resolved 2.8.0. |
| `logback-core` + `logback-classic` | core 1.5.38 / classic 1.5.33 (split) | **both 1.5.38** | HIGH | CVE-2026-13006 | logback-core ACE via conditional config, affects ≤1.5.36. **Both pinned together** — a core/classic version split causes runtime `NoClassDefFoundError` between the two jars (and, per the visibility experience, IT failures). This also removes the pre-existing split. |

**Deliberately not touched** (release exception, code freeze): `jsoup` 1.17.2 (CVE-2026-75140),
`jackson-databind` (CVE-2026-68497).

### 8.1 httpclient5 — confirmed non-breaking

The stated risk was that httpclient5 5.6.4 might break a module. It did not: the full reactor
`clean verify` (all 8 modules, unit + DynamoDB integration tests) passed **0 failures / 0 errors** with
5.6.4 in every shaded jar, and all services/lambdas boot. `httpcore5` is unchanged at 5.4.3 — the pair
is actually more consistent than before (5.4.4 shipped against 5.3.4's successor). Had it broken,
the plan was to drop only the httpclient5 pin and keep the rest; that was not needed.

### 8.2 The `jna-jpms` HIGH false positive (streamToSns)

The `PI_StreamToSNS` Jenkins scan flags `jna-jpms-5.14.0` HIGH (Low CPE confidence) — the same
false positive visibility carried. `jna-jpms` is the JNA runtime for Jetty's `setuid` helper
(`jetty-setuid-jna`), dead code in a Lambda. `pi-bl-es-lambda` already excludes it; `pi-lambda-streamToSns`
did not. Excluding `org.eclipse.jetty.toolchain.setuid:jetty-setuid-jna` on its `cloud-sdk-api` /
`cloud-sdk-aws` deps removes `jna-jpms` (and `jetty-setuid-jna`) from the deployment package —
verified: **0 jna/setuid entries** in both the jar and the zip afterwards; Jetty 12.1.12 stays. The
other DW services shade `jetty-setuid-jna` but the CI does not flag `jna-jpms` there, so they are left
as-is.

---

## 9. A latent, pre-existing lambda cold-start bug (`pi-bl-es-lambda`)

Found while boot-checking the lambdas. **Not caused by this OWASP work** — reproduced identically on a
jetty-only rebuild with zero round-2 pins, i.e. it exists on `develop` today.

### 9.1 Symptom

Instantiating the deployed handler entry point — `new IndexerHandler()`, which AWS Lambda calls on
**every cold start** (handler `com.inttra.mercury.pi.lambda.IndexerHandler::handle`) — throws:

```
java.lang.NoClassDefFoundError: com/amazonaws/regions/AwsRegionProvider
```

### 9.2 Root cause

`IndexerHandler()` builds an AWS-SigV4-signed Elasticsearch (Jest) client via
`vc.inreach.aws:aws-signing-request-interceptor:0.0.22`, which references
`com.amazonaws.regions.AwsRegionProvider` (AWS SDK **v1**). The AWS 1.x→2.x upgrade slimmed the lambda:
commit **`b6463e8e14`** ("ION-16417: shrink pi-bl-es-lambda deploy package under Lambda 250MB limit",
2026-08-28, confirmed with `git log -S'aws-java-sdk-core'`) added an **exclusion of
`com.amazonaws:aws-java-sdk-core`** on `cloud-sdk-aws`. That removed the full v1 core; the only
`aws-java-sdk-core` left is the ancient **1.10.19** the interceptor drags in, which **predates**
`AwsRegionProvider`. Verified directly: 1.10.19 does **not** contain the class, 1.12.730 does.

Pre-upgrade the lambda depended on the old `commons` + `dynamo-client`, which bundled the **full AWS
SDK v1** (with a complete `aws-java-sdk-core`), so the class was present and ES signing worked — which
is why the ~99 MB pre-upgrade jar in QA/prod is fine.

### 9.3 Fix

`aws-java-sdk-core:1.12.730` is the version **declared by `cloud-sdk-aws`** (a direct dependency of
`cloud-sdk-aws:1.0.33-SNAPSHOT`, sibling to `amazon-sqs-java-extended-client-lib`), which **every
non-bl-es PI module resolves transitively** through cloud-sdk-aws — confirmed with
`mvn dependency:tree -Dincludes=com.amazonaws:aws-java-sdk-core`. `pi-bl-es-lambda` is the sole
exception: it **strips that artifact out** via the `<exclusion>` on cloud-sdk-aws (added by the
"shrink" commit `b6463e8e14`), so 1.12.730 never reaches it and only the interceptor's stale 1.10.19
remains. The fix therefore **re-adds** `com.amazonaws:aws-java-sdk-core:1.12.730` as a direct dependency
of `pi-bl-es-lambda`, so it wins nearest-wins over the interceptor's 1.10.19 (which is then *omitted for
conflict with 1.12.730*). This is AWS SDK v1 used **solely** for ES request signing; the data-plane
(DynamoDB, …) stays on AWS SDK v2.

After the fix: `AwsRegionProvider` present in the jar; `new IndexerHandler()` → **INIT_OK** (DynamoDB v2
client + AWS-signing ES client construct cleanly when credentials are present, as the Lambda runtime
injects them); jar 63.5 → **65 MB** (well under the 250 MB unzipped limit); **93 tests pass**.

### 9.4 Environment evidence (why this is latent, and who is exposed)

Invocation path: an **SQS event-source mapping** (Enabled, batch size 1) from `inttra_*_sqs_pi_bl_es`
triggers the handler; AWS constructs it via the no-arg constructor on each cold start.

| Env | Function | CodeSize | Deployed | Code | State |
|---|---|---:|---|---|---|
| INT (`081020446316`) | `inttra_int_lambda_bl_es_stream` | 66,593,467 B (~63.5 MB) | **2026-09-02** (today) | **new** (upgraded) | last invoked **Mar 2025** → bug dormant, would fire on next message |
| QA (`642960533737`) | `inttra2_qa_lambda_bl_es_stream` | 103,995,815 B (~99 MB) | 2026-06-01 | old (pre-upgrade) | processing today, healthy |
| PROD (`642960533737`) | `inttra2_pr_lambda_bl_es_stream` | 103,995,815 B (~99 MB) | 2026-06-13 | old (pre-upgrade) | processing today, healthy |

QA and prod jars are **identical in size** (both 103,995,815 B) and predate the Aug-20 upgrade, so they
still run the working v1 code (logs show `IndexerHandler` running with no `AwsRegionProvider` error; the
`Error in BL ES Delete ... not_found` lines are benign app logs). **The size drop to ~63.5 MB is the
AWS upgrade + the "shrink under 250 MB" commits (Aug 20 / Aug 28), not any change on this branch** — it
was simply deployed to INT today. **When ION-16417 rolls to QA/prod, bl-es would break at cold start
without this fix.**

### 9.5 How the lambda handler / AWS init was verified

```powershell
# instantiate the real cold-start entry point off the shaded jar; env mirrors the Lambda config
$env:AWS_REGION='us-east-1'; $env:AWS_DEFAULT_REGION='us-east-1'
$env:AWS_ACCESS_KEY_ID='<dummy>'; $env:AWS_SECRET_ACCESS_KEY='<dummy>'   # Lambda injects real creds at runtime
$env:elasticsearchEndpointUrl='https://.../es'; $env:dynamoDbEnvironment='inttra_int'
'try { var h = new com.inttra.mercury.pi.lambda.IndexerHandler(); System.out.println("INIT_OK"); } catch (Throwable t) { System.out.println("INIT_FAIL " + t); } /exit' |
  jshell --class-path pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar -
```
* `jshell --class-path <jar>` puts the shaded jar on the execution classpath; `new IndexerHandler()`
  runs the exact no-arg constructor AWS Lambda invokes, so a linkage gap (missing `AwsRegionProvider`)
  surfaces as `INIT_FAIL NoClassDefFoundError` and a healthy build as `INIT_OK`.

```powershell
# read the AWS-upgrade timeline and the exact commit that dropped the v1 core
git log -S'aws-java-sdk-core' -- partner-integrator/pi-bl-es-lambda/pom.xml
# QA/prod use a separate account; check with the QATeam SSO profile
aws lambda get-function-configuration --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --function-name inttra2_pr_lambda_bl_es_stream --query "{CodeSize:CodeSize,LastModified:LastModified}"
aws logs filter-log-events --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --log-group-name /aws/lambda/inttra2_pr_lambda_bl_es_stream --start-time <ms> `
  --filter-pattern '?Exception ?NoClassDefFound ?AwsRegionProvider'
```

---

## Appendix A — Full command reference (syntax + bash/Unix equivalents)

Every command below was run in **PowerShell on Windows** from the repo root
`C:\Users\arijit.kundu\projects\mercury-services`. Each entry gives the exact syntax, a per-flag
explanation, and the **bash/Unix equivalent** so the same checks can be reproduced on Linux/macOS or in
CI. PowerShell specifics to know throughout:

* Line continuation is a **backtick** `` ` `` (bash uses a **backslash** `\`).
* `$env:NAME='v'` sets an environment variable for the child process (bash: `export NAME=v` or an
  inline `NAME=v cmd`).
* A multi-line **here-string** `@' ... '@` pipes literal text to a program (bash: a heredoc
  `<<'EOF' ... EOF`).
* `2>&1` merges stderr into stdout in both shells.
* Quote `"-Dprop=a,b"` in PowerShell so `.` `,` `{` are not reinterpreted (bash quoting is only needed
  for spaces/globs).

### A.1 Prerequisites — AWS credentials

```powershell
aws sts get-caller-identity --query "Arn" --output text          # who am I (default INT profile)
aws configure list-profiles                                       # list configured SSO profiles
aws sso login --profile 642960533737_INTTRA2-QATeam               # (re)authenticate a profile if expired
```
* `--query` is a **JMESPath** expression applied client-side to the JSON response; `--output text`
  strips JSON quoting. `--profile` selects a named profile (QA/prod live in a different account).
* **bash:** identical — the AWS CLI is cross-platform. Only the surrounding shell quoting differs.

### A.2 Git — branch, inspect, history, reword, push

```powershell
git checkout develop; git checkout -b feature/ION-16417-pi-owasp-issue-fix   # branch off develop
git --no-pager status -s                                                     # short, non-paged status
git --no-pager log --oneline -3                                              # last 3 commits
git --no-pager log --oneline --date=short --pretty="%h %ad %s" -- <path>     # history of one path
git --no-pager show <sha>:<path> | Select-String 'CVE-'                      # a file *as of* a commit
git --no-pager log -S'aws-java-sdk-core' -- <path>                           # "pickaxe": commits that
                                                                             # added/removed that string
git push -u origin feature/ION-16417-pi-owasp-issue-fix                      # push + set upstream
```
* `--no-pager` prevents the interactive pager (bash: `git --no-pager …` or `git … | cat`).
* `--pretty="%h %ad %s"` = short-hash, author-date, subject; `-S'string'` is the **pickaxe** that finds
  the commit where a string's occurrence count changed — this is how commit `b6463e8e14` (the one that
  added the `aws-java-sdk-core` exclusion) was pinpointed.
* `git show <sha>:<path>` prints a file's contents at a specific commit without checking it out.
* **bash:** all identical; replace `| Select-String 'CVE-'` with `| grep 'CVE-'`.

**Reword commit messages non-interactively** (used to strip the `CVE-####` pattern the Bitbucket
Control-Freak hook mis-parsed as a Jira ticket). Two tiny scripts drive a normally-interactive rebase:

```powershell
# seq.py turns every "pick" line into "reword"; msg.py rewrites each message (CVE- -> "CVE ")
$env:GIT_SEQUENCE_EDITOR="python `"$env:TEMP\seq.py`""   # edits the rebase to-do list
$env:GIT_EDITOR="python `"$env:TEMP\msg.py`""            # edits each commit message
git rebase -i e5bb4889b0~1                               # replay just our commits, base unchanged
```
* `GIT_SEQUENCE_EDITOR` edits the rebase *instruction sheet*; `GIT_EDITOR` edits each *message*. Pointing
  both at scripts makes an `-i` rebase fully non-interactive. `<sha>~1` rebases onto the parent of the
  first commit so the base branch is not moved.
* **bash equivalent** (same idea, sed instead of python):
  ```bash
  GIT_SEQUENCE_EDITOR="sed -i 's/^pick/reword/'" \
  GIT_EDITOR="sed -i 's/CVE-/CVE /g'" \
  git rebase -i e5bb4889b0~1
  ```

### A.3 Maven — dependency resolution, build, targeted build

```powershell
# Resolve the version Maven picks for a group, offline, single module
mvn -o dependency:tree -pl partner-integrator/pi-si-out-processor "-Dincludes=org.eclipse.jetty" |
  Select-String 'org\.eclipse\.jetty'

# Full reactor: compile + unit (surefire) + integration (failsafe *IT) tests
mvn -f partner-integrator/pom.xml clean verify 2>&1 |
  Tee-Object -FilePath pi-verify.log |
  Select-String 'BUILD SUCCESS|BUILD FAILURE|Tests run:|Building pi-'

# One module only (fast re-verify after a single-pom change)
mvn -f partner-integrator/pom.xml -pl pi-bl-es-lambda clean verify
```
* `-o` = **offline** (resolve from the local `~/.m2` only). `-pl <path>` = build/inspect one module;
  `-am` (also-make) additionally builds its upstream reactor deps — **omitted** for `dependency:tree`
  because it only *resolves* (the module's parent pom is read from disk via `<relativePath>`, so the
  working-tree pin is already seen). `-Dincludes=<g>:<a>` filters the tree to matching coordinates.
* `-f <pom>` targets a reactor; `clean verify` runs the whole lifecycle **including failsafe** (the
  `*IT` DynamoDB-Local integration tests) — `mvn test` would run unit tests only.
* `Tee-Object -FilePath f` = write-and-passthrough (**bash:** `tee f`); `Select-String` = **grep**.
* **bash equivalent:**
  ```bash
  mvn -o dependency:tree -pl partner-integrator/pi-si-out-processor -Dincludes=org.eclipse.jetty | grep 'org\.eclipse\.jetty'
  mvn -f partner-integrator/pom.xml clean verify 2>&1 | tee pi-verify.log | grep -E 'BUILD SUCCESS|BUILD FAILURE|Tests run:|Building pi-'
  ```
* **Do not run two Maven builds concurrently** on this workstation (it thrashes); keep them sequential.

### A.4 Reading the OWASP dependency-check JSON reports

```powershell
$mods='pi-bl-es-lambda','pi-booking-processor','pi-lambda-streamToSns'   # etc.
foreach($m in $mods){
  $j = Get-Content "owasp-reports\$m\dependency-check-report.json" -Raw | ConvertFrom-Json
  foreach($d in $j.dependencies){ foreach($v in $d.vulnerabilities){
    if($v.severity -match 'CRITICAL|HIGH'){ "{0,-9} {1,-16} {2}" -f $v.severity,$v.name,$d.fileName }
  }}
}
```
* `Get-Content -Raw` reads the whole file as one string; `ConvertFrom-Json` parses it; the nested loops
  walk `dependencies[].vulnerabilities[]`. `-match` is a regex test; `-f` is .NET format
  (`{index,width}`).
* **bash equivalent with `jq`** (the idiomatic JSON tool):
  ```bash
  for m in pi-bl-es-lambda pi-booking-processor pi-lambda-streamToSns; do
    jq -r --arg m "$m" '.dependencies[] | select(.vulnerabilities) | .fileName as $f
      | .vulnerabilities[] | select(.severity=="CRITICAL" or .severity=="HIGH")
      | "\(.severity)\t\(.name)\t\($f)"' "owasp-reports/$m/dependency-check-report.json"
  done
  ```
* Extracting a CVE's fixed-version range (used to confirm 5.6.4 clears httpclient5):
  ```bash
  jq -r '.dependencies[].vulnerabilities[]? | select(.name=="CVE-2026-71290")
         | .vulnerableSoftware[].software | "\(.id) endExcluding=\(.versionEndExcluding)"' report.json
  ```

### A.5 Searching text — Jenkins HTML, source, logs (grep / ripgrep / sed / awk)

```powershell
Select-String -Path report.html -Pattern 'jna-jpms|CVE-2026-10050'        # grep a file
(Get-Content report.html -Raw | Select-String 'jetty-[a-z]+-12\.1\.\d+\.jar' -AllMatches).Matches.Value |
  Sort-Object -Unique                                                      # extract + de-dup matches
```
* `Select-String -Pattern` = **grep -E**; `-AllMatches).Matches.Value` extracts the matched substrings
  (not whole lines) — like `grep -oE`. `Sort-Object -Unique` = `sort -u`.
* **bash equivalents** (prefer **ripgrep** `rg`; `grep`/`sed`/`awk` shown too):
  ```bash
  rg -n 'jna-jpms|CVE-2026-10050' report.html                 # ripgrep, fast, line numbers
  grep -Eo 'jetty-[a-z]+-12\.1\.[0-9]+\.jar' report.html | sort -u   # extract + de-dup (grep -o)
  sed -nE 's/.*(CVE-[0-9-]+).*/\1/p' report.html | sort -u    # sed: capture & print CVE ids
  awk '/AwsRegionProvider/{c++} END{print c}' file            # awk: count matching lines
  ```
* In this repo the agent used the **grep tool** (ripgrep under the hood); at the shell, `rg <pat> <dir>`
  is the direct equivalent, and `find . -name '*.java' | xargs rg <pat>` mimics a scoped search.

### A.6 Inspecting jar / zip contents (what actually got shaded)

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[System.IO.Compression.ZipFile]::OpenRead((Resolve-Path 'pi-bl-es-lambda\target\pi-bl-es-lambda-1.0.jar'))
[bool]($zip.Entries | Where-Object { $_.FullName -eq 'com/amazonaws/regions/AwsRegionProvider.class' })  # present?
$zip.Entries | Where-Object { $_.FullName -match 'jna|setuid' } | ForEach-Object FullName                 # list jna entries
$zip.Dispose()
```
* Uses the .NET zip API because a shaded jar is just a zip. Reads the central directory without
  extracting.
* **bash equivalents** (`jar`, `unzip`, or `zipinfo`):
  ```bash
  unzip -l pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar | grep -E 'AwsRegionProvider|jna|setuid'
  jar tf pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar | grep 'com/amazonaws/regions/AwsRegionProvider'
  # Main-Class from the manifest:
  unzip -p app.jar META-INF/MANIFEST.MF | grep 'Main-Class'
  ```

### A.7 Boot verification

**DW services** (each is a shaded Dropwizard app; a no-arg run must print the command list and exit 0):

```powershell
java -jar partner-integrator/pi-si-out-processor/target/pi-si-out-processor-1.0.jar   # -> usage {server,check}; exit 0
$LASTEXITCODE                                                                          # 0 == booted cleanly
```
* Running the fat-jar with no command makes Dropwizard's CLI print `usage: … {server,check,…}` and exit.
  Reaching that point proves the shaded Jetty/Jersey classpath assembled with **no
  `NoClassDefFoundError`/linkage error** — the exact failure a bad Jetty/httpclient/logback bump causes.
  `$LASTEXITCODE` is the process exit code (**bash:** `$?`).
* **bash:** `java -jar …/pi-si-out-processor-1.0.jar; echo "exit=$?"`.

**Lambdas** (no server; verify the handler the runtime calls actually constructs). Class-load proves
linkage; full `new Handler()` proves **AWS clients initialize**:

```powershell
$env:AWS_REGION='us-east-1'; $env:AWS_DEFAULT_REGION='us-east-1'
$env:AWS_ACCESS_KEY_ID='<dummy>'; $env:AWS_SECRET_ACCESS_KEY='<dummy>'   # Lambda injects real creds at runtime
$env:elasticsearchEndpointUrl='https://.../es'; $env:dynamoDbEnvironment='inttra_int'
@'
try { var h = new com.inttra.mercury.pi.lambda.IndexerHandler(); System.out.println("INIT_OK"); }
catch (Throwable t) { System.out.println("INIT_FAIL " + t); }
/exit
'@ | jshell --class-path "pi-bl-es-lambda\target\pi-bl-es-lambda-1.0.jar" -
```
* `jshell --class-path <jar> -` starts the Java REPL with the jar on the classpath and reads the script
  from **stdin** (the trailing `-`). `new IndexerHandler()` runs the exact no-arg constructor AWS Lambda
  invokes at cold start, so a missing class surfaces as `INIT_FAIL … NoClassDefFoundError` and a healthy
  build as `INIT_OK`. The env vars mirror the deployed function's configuration; real credentials are
  injected by the Lambda runtime (here dummies suffice because the v1 signing client only *builds*).
* **bash equivalent** (heredoc instead of a here-string):
  ```bash
  export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 \
         AWS_ACCESS_KEY_ID=dummy AWS_SECRET_ACCESS_KEY=dummy \
         elasticsearchEndpointUrl=https://.../es dynamoDbEnvironment=inttra_int
  jshell --class-path pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar - <<'EOF'
  try { var h = new com.inttra.mercury.pi.lambda.IndexerHandler(); System.out.println("INIT_OK"); }
  catch (Throwable t) { System.out.println("INIT_FAIL " + t); }
  /exit
  EOF
  ```

### A.8 AWS CLI — Lambda / SQS / CloudWatch Logs investigation

```powershell
# Function config (handler, runtime, layers, env, size, last deploy) — JMESPath projection
aws lambda get-function-configuration --region us-east-1 --function-name inttra_int_lambda_bl_es_stream `
  --query "{Handler:Handler,Runtime:Runtime,Layers:Layers,Env:Environment.Variables,CodeSize:CodeSize,LastModified:LastModified}"

# Find functions by name fragment (server-side list, client-side JMESPath filter)
aws lambda list-functions --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --query "Functions[?contains(FunctionName,'bl_es')].FunctionName"

# What triggers it? (SQS event-source mapping + enabled state)
aws lambda list-event-source-mappings --function-name inttra_int_lambda_bl_es_stream --region us-east-1 `
  --query "EventSourceMappings[].{UUID:UUID,Source:EventSourceArn,State:State,BatchSize:BatchSize}"

# Queue depth (is work waiting?)
aws sqs get-queue-attributes --region us-east-1 `
  --queue-url https://sqs.us-east-1.amazonaws.com/081020446316/inttra_int_sqs_pi_bl_es `
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# Most-recent log streams (has it run? when?)
aws logs describe-log-streams --region us-east-1 --log-group-name /aws/lambda/inttra_int_lambda_bl_es_stream `
  --order-by LastEventTime --descending --max-items 3 `
  --query "logStreams[].{stream:logStreamName,last:lastEventTimestamp}"

# Search recent log events for cold-start / linkage errors (server-side pattern + time window)
aws logs filter-log-events --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --log-group-name /aws/lambda/inttra2_pr_lambda_bl_es_stream `
  --start-time 1788350000000 `
  --filter-pattern '?Exception ?NoClassDefFound ?AwsRegionProvider'
```
* `--query "..."` is **JMESPath**, evaluated client-side: `{k:Path}` builds an object projection,
  `[?contains(Field,'x')]` filters a list, `Field.Sub` drills in. `--filter-pattern` is a **server-side
  CloudWatch Logs** filter; `?A ?B` means *A OR B* (a leading `?` on each alternative). `--start-time`
  is **epoch milliseconds** (compute with `[DateTimeOffset]::UtcNow.AddHours(-3).ToUnixTimeMilliseconds()`;
  bash: `date -d '3 hours ago' +%s000`). `--order-by LastEventTime --descending` surfaces the newest
  streams; `--profile` targets the QA/prod account.
* **bash:** identical commands. To compute a window: `--start-time "$(( $(date +%s) - 10800 ))000"`.

### A.9 PowerShell → bash quick map (everything used here)

| PowerShell | bash / Unix | Purpose |
|---|---|---|
| `Select-String -Pattern p` | `grep -E p` / `rg p` | search text |
| `Select-String ... -AllMatches).Matches.Value` | `grep -oE p` | extract matches, not lines |
| `Get-Content f -Raw` | `cat f` | read file |
| `Get-ChildItem -Recurse -Filter *.jar` | `find . -name '*.jar'` | list files |
| `Tee-Object -FilePath f` | `tee f` | log + passthrough |
| `ConvertFrom-Json` | `jq` | parse JSON |
| `Sort-Object -Unique` | `sort -u` | de-dup |
| `$env:X='v'` | `export X=v` | set env var |
| `` ` `` (line continuation) | `\` | continue a long line |
| `@' … '@ \| cmd` (here-string) | `cmd <<'EOF' … EOF` (heredoc) | feed literal stdin |
| `$LASTEXITCODE` | `$?` | last exit code |
| `[DateTimeOffset]::UtcNow.AddHours(-3).ToUnixTimeMilliseconds()` | `echo "$(( $(date +%s)-10800 ))000"` | epoch-ms window |

---

## Appendix B — Session / traceability

* **MCP Context session id:** `1ec936447f7145c6` — *"ION-16417 PI OWASP issue fix (Jetty + others)"*
  (project `mercury-services`). All decisions, findings, the latent-bug investigation, test results and
  the prod/QA evidence are logged there. Status: **completed** (marked at end of this work).
* **Related session:** `59a4c1b2109b487d` — the ION-16417 PI AWS 1.x→2.x upgrade.
* **Branch:** `feature/ION-16417-pi-owasp-issue-fix` → `origin` (upstream set).
* **Commits (all `ION-16417`):** `107c743174` (Jetty), `ecd27ab41d` (httpclient5/guava/gson/logback +
  jna false positive), `fc97551fae` (latent bl-es `AwsRegionProvider` fix).
