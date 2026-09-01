# ION-16693 — visibility lambdas: the `jna-jpms` HIGH OWASP finding

**Date:** 2026-09-01
**Branch:** `feature/ION-16693-vis-lambda-owasp-fix`
**Modules:** `visibility-s3-archiver`, `visibility-error-email`, `visibility-pending-start`,
`visibility-outbound-poller` (the four visibility lambda deployment packages)
**Follow-up to:** `visibility/docs/2026-08-31-visibility-owasp-refactor.md` (commons 1.0.33-SNAPSHOT
bump + the reactor-wide Jetty/httpclient5/log4j/guava pins)
**CI reports analysed:** `VisibilityS3Archiver-26.09.002-OWASP.html`,
`VisibilityOutboundPoller-26.09.002-OWASP.html`, `VisibilityErrorEmail-26.09.002-OWASP.html`,
`VisibilityPendingStart-26.09.002-OWASP.html`

---

## 1. Summary

The 26.09.002 Jenkins OWASP scans of the four visibility lambdas each report the **same three HIGH**
findings:

| # | Dependency | CVEs | CPE confidence | In scope here? |
|---|---|---:|---|---|
| 1 | `jna-jpms-5.14.0.jar` | 9 | **Low** | **yes — this ticket** |
| 2 | `jackson-databind-2.22.0.jar` | 5 | Highest | no — release exception (code freeze) |
| 3 | `jsoup-1.17.2.jar` | 2 | Highest | no — release exception (code freeze) |

(2) and (3) also affect other modules on commons 1.0.33-SNAPSHOT and are being carried under a
two-week exception; they are untouched by this branch and both jars still ship.

**The `jna-jpms` finding is a false positive**, and it is one the dependency-check project itself
has already classified as such. It has been closed at the root by removing the dependency, which is
genuinely dead code inside a Lambda:

| Change | File(s) |
|---|---|
| Exclude `org.eclipse.jetty.toolchain.setuid:jetty-setuid-jna` (which drags in `net.java.dev.jna:jna-jpms`) | the 4 lambda `pom.xml` files |
| Fix a pre-existing, unrelated broken integration test: `log4j-core` `2.23.1` → `${log4j.version}` (2.25.5) | `visibility-s3-archiver/pom.xml` |

Result: `jna-jpms-5.14.0.jar` and `jetty-setuid-jna-2.0.3.jar` no longer exist in any lambda
deployment package, all four lambdas still boot, and no other visibility module is affected.

---

## 2. Where `jna-jpms` comes from

`mvn dependency:tree` on each lambda, filtered to the two artifacts (§8, command 3):

```
visibility-s3-archiver / visibility-pending-start / visibility-outbound-poller
  \- com.inttra.mercury:cloud-sdk-api:jar:1.0.33-SNAPSHOT:compile
     \- io.dropwizard:dropwizard-core:jar:5.0.2:compile
        \- org.eclipse.jetty.toolchain.setuid:jetty-setuid-jna:jar:2.0.3:compile
           \- net.java.dev.jna:jna-jpms:jar:5.14.0:compile

visibility-error-email
  \- com.inttra.mercury:visibility-commons:jar:1.0:compile
     \- com.inttra.mercury:commons:jar:1.0.33-SNAPSHOT:compile
        \- io.dropwizard:dropwizard-core:jar:5.0.2:compile
           \- org.eclipse.jetty.toolchain.setuid:jetty-setuid-jna:jar:2.0.3:compile
              \- net.java.dev.jna:jna-jpms:jar:5.14.0:compile
```

Three of the four reach it through `cloud-sdk-api`; `visibility-error-email` reaches it one level
deeper through `visibility-commons → commons`. In every case the real source is
**`dropwizard-core` 5.0.2, which declares `jetty-setuid-jna` as a direct compile dependency**
(`dropwizard-core-5.0.2.pom` lines 166-169; the version property `jetty-setuid-jna.version = 2.0.3`
lives in `dropwizard-dependencies-5.0.2.pom`). Nothing in visibility asks for it.

`jetty-setuid-jna` is the Jetty helper that calls `setuid(2)`/`setgid(2)` through JNA so a server can
bind a privileged port as root and then drop to an unprivileged user. `jna-jpms` is the JNA runtime it
needs, and it ships native `jnidispatch` binaries for every platform
(`com/sun/jna/win32-x86-64/jnidispatch.dll`, `linux-x86-64/libjnidispatch.so`, …).

### 2.1 Correction — `commons 1.0.27-SNAPSHOT` was a probe artifact, not reality

An earlier draft of this note reported the `visibility-error-email` path as going through
`commons:1.0.27-SNAPSHOT`. **That was wrong**, and the reason is worth recording because it is an easy
trap to fall into anywhere in this repo.

The probe was run as:

```powershell
mvn -o dependency:tree -pl visibility-error-email "-Dincludes=com.inttra.mercury:*"
#   -> com.inttra.mercury:commons:jar:1.0.27-SNAPSHOT:compile     <-- WRONG
```

With `-pl` but **without `-am`**, `visibility-commons:1.0` is not in the reactor, so Maven resolves it
from the local repository. Its installed POM inherits `${mercury.commons.version}` from the installed
**parent** POM, `~/.m2/repository/com/inttra/mercury/visibility/1.0/visibility-1.0.pom`, which on this
workstation was last installed on 2026-07-24 and still contains:

```xml
<mercury.commons.version>1.0.27-SNAPSHOT</mercury.commons.version>
```

Adding `-am` puts `visibility` and `visibility-commons` back in the reactor, so the *working tree*
POMs are used and the correct version appears:

```powershell
mvn -o dependency:tree -pl visibility-error-email -am "-Dincludes=com.inttra.mercury:*"
#   +- com.inttra.mercury:commons:jar:1.0.33-SNAPSHOT:compile      <-- correct
#   +- com.inttra.mercury:cloud-sdk-api:jar:1.0.33-SNAPSHOT:compile
#   \- com.inttra.mercury:cloud-sdk-aws:jar:1.0.33-SNAPSHOT:compile
```

`visibility/pom.xml` has carried `1.0.33-SNAPSHOT` since yesterday's commit `08a0c83d41`, and
`visibility-commons/pom.xml` declares `commons` as `${mercury.commons.version}` — there is no
per-module override anywhere. **All four lambdas and all seven services are on
`commons 1.0.33-SNAPSHOT`.**

Two takeaways:

* **Always use `-am` (or run the whole reactor) for any `dependency:tree` / `help:effective-pom`
  probe in this repo.** Without it you are reading whatever was last `mvn install`ed, which can be
  weeks out of date and silently wrong.
* The CI job already does this — it passes `--also-make` (see §5.4) — so CI was never affected.
* **The fix is unaffected either way.** The exclusion in `visibility-error-email/pom.xml` is declared
  on the `visibility-commons` dependency itself, so it applies regardless of which `commons` version
  resolves underneath it.

---

## 3. Why it only shows up on the lambdas

**Because of how the lambdas are packaged, not because of what they depend on.**

The seven non-lambda visibility modules ship a `maven-shade-plugin` uber-jar: JNA's classes are merged
into one artifact, so dependency-check never creates a standalone `jna-jpms-5.14.0.jar` node and never
runs its CPE analyzer against it.

The four lambdas additionally run `maven-assembly-plugin` with
`src/assembly/deployment_package.xml`, which produces a **ZIP whose `lib/` folder keeps every runtime
dependency as its own jar**:

```xml
<dependencySets>
    <dependencySet>
        <outputDirectory>lib</outputDirectory>
        <useProjectArtifact>false</useProjectArtifact>
    </dependencySet>
</dependencySets>
```

dependency-check therefore sees `lib/jna-jpms-5.14.0.jar` as a first-class dependency, unpacks it,
also catalogues the three bundled `jnidispatch` native libraries, and assigns it a CPE.

Confirmed by counting occurrences of `jna-jpms` in the CI reports (§8, command 2):

| Report | packaging | `jna-jpms` mentions |
|---|---|---:|
| `Visibility-26.09.005-OWASP.html` (shaded app) | shaded uber-jar | **0** |
| all four lambda reports | ZIP with exploded `lib/` | **53** each |

Both sets of modules resolve `jna-jpms` on the compile classpath. Only the lambdas *expose it to the
scanner as a separate file*.

---

## 4. Why the finding is a false positive

The CI report row is:

```
jna-jpms-5.14.0.jar   cpe:2.3:a:sun:java_se:5.14.0:*:*:*:*:*:*:*
                      pkg:maven/net.java.dev.jna/jna-jpms@5.14.0    HIGH  9   Low   54
                                                                     ^    ^    ^
                                                        highest severity  |    CPE confidence
                                                                   CVE count
```

dependency-check matched `net.java.dev.jna:jna-jpms` to **`cpe:2.3:a:sun:java_se`** — Oracle/Sun
**Java SE** — at **Low** confidence, because the jar's package namespace is `com/sun/jna/**` and the
evidence harvested from the embedded natives is literally `Vendor = jnidispatch (file name)`,
`Product = jnidispatch (file name)`.

Reproducing that match locally with the hosted suppression list removed (§8, command 10) returns the
exact nine CVEs Jenkins reports:

```
CPE: cpe:2.3:a:sun:java_se:5.14.0:*:*:*:*:*:*:*  | confidence: LOW
vulnerabilities: 9   ->   {HIGH: 4, MEDIUM: 5}
  CVE-2009-2476  HIGH     CVE-2009-2689  HIGH     CVE-2009-2475  HIGH     CVE-2009-2716  HIGH
  CVE-2009-2676  MEDIUM   CVE-2009-2717  MEDIUM   CVE-2009-2690  MEDIUM   CVE-2009-2719  MEDIUM
  CVE-2009-2720  MEDIUM
```

**All nine are 2009 Sun Java SE JRE defects** — reported against a JNA library released in 2024. They
have nothing to do with JNA.

This is not merely our opinion. dependency-check's own hosted false-positive list, which the tool
downloads to `<data>/publishedSuppressions.xml`, contains this base rule:

```xml
<suppress base="true">
    <notes>FP per issue #8257, #8701, #8718, #8719, #8720, #8721, #8722, #8723</notes>
    <packageUrl regex="true">^pkg:maven/.*@.*$</packageUrl>
    <cpe regex="true">cpe:/a:oracle:java_se(:.*)?$</cpe>
    <cpe regex="true">cpe:/a:sun:java_se(:.*)?$</cpe>
    <cpe regex="true">cpe:/a:sun:java_system_web_server(:.*)?$</cpe>
</suppress>
```

i.e. **upstream declares `sun:java_se` on any Maven artifact to be a false positive.**

---

## 5. Why local scans disagreed with Jenkins

A local scan run before this fix reported the `jackson-databind` and `jsoup` HIGHs but **not** the
`jna` one, and showed far fewer dependencies than Jenkins:

```powershell
dependency-check --project visibility-ob-poller `
  --scan .\visibility-outbound-poller-1.0-deployment_package.zip `
  --out owasp --suppression ..\suppressions.xml --nvdApiKey $env:NVD_API_KEY
```

**That command was correct.** There are two independent causes, both confirmed by experiment. Note
first that this is *not* a version gap — the Jenkins HTML footer states `dependency-check version :
13.0.0`, the same build used locally.

### 5.1 The missing `jna` finding — hosted suppressions

A developer workstation has internet access, so dependency-check downloads
`<data>/publishedSuppressions.xml` and applies the upstream `sun:java_se` rule from §4. The CPE is
stripped before the vulnerability lookup, so the dependency reports **0 vulnerabilities and an empty
`vulnerabilityIds` list**. The Jenkins agent evidently cannot reach that URL, so the rule is not
applied and the false positive surfaces.

A useful subtlety: **`--disableHostedSuppressions` is not enough to reproduce Jenkins.** That flag
stops the file being *refreshed*, not being *used* — an already-downloaded copy is still applied. The
CI behaviour only reproduces once the file is actually absent from the data directory (§8, commands
9-10):

| Local run | `publishedSuppressions.xml` | CPE assigned | Vulnerabilities |
|---|---|---|---:|
| default | present | none | 0 |
| `--disableHostedSuppressions` | present (still applied) | none | 0 |
| cloned data dir with the file deleted | **absent** | `cpe:2.3:a:sun:java_se:5.14.0` (LOW) | **9 (4 HIGH)** |

### 5.2 The dependency count — Jenkins scans the package twice

| | Dependencies Scanned |
|---|---:|
| Jenkins, `VisibilityOutboundPoller-26.09.002` | **490** |
| Jenkins, `VisibilityS3Archiver-26.09.002` | **492** |
| local, scanning the ZIP | **240 / 241** |

Parsing the file paths in the CI report (§8, command 11) shows the scanned Jenkins workspace holds
**both** the exploded package **and** the ZIP it came from:

```
<ws>/VisibilityOutboundPoller-26.09.002-<ts>/lib/<jar>             -> 221 distinct jars
<ws>/VisibilityOutboundPoller-26.09.002-<ts>/<pkg>.zip/lib/<jar>   -> the same 221 jars
jars appearing in BOTH forms: 221 (100%)
```

So every jar is catalogued twice — 221 × 2 = 442, plus the native `.dll`/`.so` entries and the ZIP
itself ≈ 490. The 206 “Related Dependencies” blocks in the report are dependency-check merging those
pairs back together. (221 is exactly the pre-fix `lib/` jar count reproduced locally, which
corroborates the reading.)

Importantly, an A/B control (§8, commands 7-8) scanning identical content **as a ZIP** and **as an
exploded directory** produced *identical* results locally — 206 dependency entries and the same
findings either way. **The layout inflates the count; it does not change the findings.** The only
behavioural difference between local and CI is §5.1.

### 5.3 Recommendation for the CI/platform team

Give the Jenkins agent egress to the hosted-suppression URL, or commit a copy of
`publishedSuppressions.xml` and pass it via `--suppression`. Otherwise every upstream-known false
positive will keep appearing in CI only, and each will cost a manual investigation like this one.

---

## 6. The fix

### 6.1 What changed

`jetty-setuid-jna` is excluded in the four lambda poms — on `cloud-sdk-api`, `cloud-sdk-aws` and
`visibility-commons`, so the exclusion holds whichever of the three paths in §2 is in play:

```xml
<!-- ION-16693: jetty-setuid-jna (via dropwizard-core) drags in net.java.dev.jna:jna-jpms, which
     dependency-check mis-identifies as Oracle Java SE (cpe:2.3:a:sun:java_se) and reports HIGH.
     SetUIDListener is only used by Dropwizard's AbstractServerFactory to drop root privileges
     after binding a privileged port; a Lambda never builds a Jetty Server, so it is unreachable
     here. Excluded in the lambda modules only - the Dropwizard services in this reactor need it. -->
<exclusion>
    <groupId>org.eclipse.jetty.toolchain.setuid</groupId>
    <artifactId>jetty-setuid-jna</artifactId>
</exclusion>
```

An exclusion was chosen over `<scope>provided</scope>` deliberately: an exclusion removes the jar from
the **compile, test and runtime** classpaths, so `mvn verify` exercises exactly the classpath that is
deployed. `provided` would have kept it at compile time and hidden any real need until the Lambda ran.

A `suppressions.xml` entry would also have silenced the finding, but removing the artifact is
strictly better — it cannot recur under a different scanner configuration, and it drops a genuinely
unused jar (plus its Windows/macOS/Linux native binaries) from the deployment package.

### 6.2 Why this is safe

`io.dropwizard.core.server.AbstractServerFactory` is the **only** class in `dropwizard-core` that
references `org.eclipse.jetty.setuid` (established by extracting the jar and scanning every `.class`,
§8 command 5), and its `buildServer(...)` calls `buildSetUIDListener()` **unconditionally**:

```
protected org.eclipse.jetty.server.Server buildServer(LifecycleEnvironment, ThreadPool);
   ...
   11: invokevirtual #338  // Method buildSetUIDListener:()Lorg/eclipse/jetty/setuid/SetUIDListener;
   14: invokevirtual #342  // Method org/eclipse/jetty/server/Server.addEventListener:(...)Z
```

So this exclusion **must not** be applied reactor-wide — it would break every Dropwizard service in
visibility at startup. It is applied to the four lambda modules only, and those are leaf modules that
nothing else depends on.

The lambdas never build a Jetty `Server`: they are AWS `RequestHandler` classes, and a grep across all
four `src/` trees for `io.dropwizard`, `jetty` and `Configuration` returns **no matches** (§8, command
4). A constant-pool scan of the whole deployed classpath (~220 jars per lambda, §8 command 13)
confirms that after the change the only remaining reference to `org/eclipse/jetty/setuid` anywhere is
Dropwizard's own `AbstractServerFactory`, and the only jar referencing any Dropwizard `ServerFactory`
type is `dropwizard-core` itself — no visibility or commons code can reach it.

### 6.3 The unrelated log4j fix

The first full `mvn verify` failed in `VisibilityS3ArchiverIT`:

```
java.lang.NoSuchMethodError: 'java.util.stream.Stream
  org.apache.logging.log4j.util.ServiceLoaderUtil.loadServices(java.lang.Class,
  java.lang.invoke.MethodHandles$Lookup, boolean)'
```

This is **pre-existing and unrelated to this branch**. `visibility-s3-archiver` was the only module
hardcoding `log4j-core` at `2.23.1` while every other module uses `${log4j.version}`; yesterday's bump
of that property to 2.25.5 left `log4j-core` 2.23.1 running against `log4j-api` 2.25.5 (resolved
transitively via `visibility-commons`), and the two are not binary compatible. It went unnoticed
because yesterday's verification used `mvn package`, which does not run failsafe.

Fixed by making it track the property, consistent with `visibility-commons`,
`visibility-inbound` and `visibility-wm-inbound-processor`:

```xml
<version>${log4j.version}</version>
```

---

## 7. Verification

### 7.1 Dependency resolution

| Module set | `jetty-setuid-jna` / `jna-jpms` after the change |
|---|---|
| the 4 lambdas | **absent** |
| `visibility-commons`, `-inbound`, `-wm-inbound-processor`, `-matcher`, `-outbound`, `-pending`, `-itv-gps-processor` | still `jetty-setuid-jna:2.0.3` → `jna-jpms:5.14.0`, **unchanged** |

### 7.2 Deployment packages

| Module | jars in `lib/` | `jna`/`setuid` jars |
|---|---:|---|
| visibility-s3-archiver | 220 | **NONE** |
| visibility-error-email | 219 | **NONE** |
| visibility-pending-start | 219 | **NONE** |
| visibility-outbound-poller | 219 | **NONE** |

(pre-fix the count was 221 for outbound-poller — the two removed jars.)

### 7.3 Build and tests — `mvn -o clean verify`, all 12 modules

```
visibility ......................................... SUCCESS
visibility-commons ................................. SUCCESS [02:31 min]
visibility-inbound ................................. SUCCESS [01:21 min]
visibility-wm-inbound-processor .................... SUCCESS [ 30.767 s]
visibility-matcher ................................. SUCCESS [ 25.935 s]
visibility-outbound ................................ SUCCESS [ 27.499 s]
visibility-pending ................................. SUCCESS [ 33.538 s]
visibility-s3-archiver ............................. SUCCESS [ 43.294 s]
visibility-pending-start ........................... SUCCESS [ 26.034 s]
visibility-error-email ............................. SUCCESS [01:06 min]
visibility-outbound-poller ......................... SUCCESS [ 28.211 s]
visibility-itv-gps-processor ....................... SUCCESS [ 26.287 s]
BUILD SUCCESS
```

Unit **and** integration tests (failsafe, DynamoDB Local) all pass, including
`VisibilityS3ArchiverIT` which was failing before the log4j fix.

### 7.4 Lambda boot test

Unit tests still run against the Maven classpath, so they cannot prove the *deployment package* is
bootable. Each ZIP was therefore extracted and its handler loaded exactly the way the AWS Lambda Java
runtime does on a cold start — `Class.forName(handler, initialize = true)` (which links, verifies and
runs `<clinit>` for the handler and everything it references), then the public no-arg constructor
(§8, commands 12-13):

```
===== visibility-s3-archiver -> com.inttra.mercury.visibility.lambda.VisibilityS3Archiver
  [OK] linked + verified + <clinit> : com.inttra.mercury.visibility.lambda.VisibilityS3Archiver
  [OK] constructor reached app code, threw java.lang.IllegalArgumentException
       (no AWS creds/env locally): Environment setting for 's3ArchiveBucket' is missing
  [OK] org.eclipse.jetty.setuid.SetUIDListener absent, and the handler booted anyway
  exit=0
```

…and identically for `visibility-error-email` (`Environment setting for 'env' is missing`),
`visibility-pending-start` (`'pendingSqsUrl'`) and `visibility-outbound-poller`
(`'outboundIpfSqs'`). **All four exit 0.**

No `NoClassDefFoundError` / `ClassNotFoundException` / `LinkageError` anywhere. Each constructor got
all the way into application code and stopped only at `HandlerSupport`'s environment validation, which
is the correct behaviour off-Lambda where those env vars are not set.

### 7.5 OWASP re-scan of the rebuilt packages

| Module | CRITICAL | HIGH | MEDIUM | LOW | `jna` artifact present |
|---|---:|---:|---:|---:|---|
| visibility-s3-archiver | 0 | 0 | 3 | 0 | **False** |
| visibility-error-email | 0 | 0 | 4 | 0 | **False** |
| visibility-pending-start | 0 | 0 | 3 | 0 | **False** |
| visibility-outbound-poller | 0 | 0 | 3 | 0 | **False** |

**Read the `HIGH = 0` column with §5.1 in mind.** A local scan also suppresses the `jackson-databind`
and `jsoup` HIGHs (this NVD snapshot only rates `jackson-databind` MEDIUM via CVE-2026-54515), so this
is *not* a like-for-like prediction of the next Jenkins run.

The tool-independent guarantee is the last column: **`jna-jpms-5.14.0.jar` is no longer in the
artifact**, so the finding cannot be reported again by any scanner configuration. `jsoup-1.17.2.jar`
and `jackson-databind-2.22.0.jar` are still present, as intended.

**Expected next Jenkins scan:** 2 HIGH (`jackson-databind`, `jsoup` — under the agreed exception)
instead of 3, with the `jna-jpms` row gone entirely, and ~2 fewer jars per package.

---

## 8. Commands used

Every command below was run from PowerShell on Windows. `$env:TEMP` is used for scratch work so
nothing lands in the repo.

**1 — Branch off `develop`.**
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services
git checkout -b feature/ION-16693-vis-lambda-owasp-fix
```

**2 — Establish that `jna-jpms` only appears in the lambda CI reports.**
Counts `jna-jpms` mentions in each 26.09 report; the shaded app report returns 0, the four lambda
reports return 53 each. This is what proves the difference is *packaging*, not dependencies.
```powershell
@'
import re, glob
from pathlib import Path
for f in glob.glob(r"C:\Users\arijit.kundu\Downloads\Visibility*26.09*OWASP*.html"):
    c = Path(f).read_text(encoding="utf-8", errors="ignore")
    print(Path(f).name, "| jna-jpms hits:", len(re.findall(r"jna-jpms", c)))
'@ | python -
```

**3 — Find where the dependency enters, per lambda.**
`-Dincludes` must be quoted in PowerShell, otherwise `net.java.dev.jna` is parsed as a lifecycle
phase and Maven fails with “Unknown lifecycle phase .java.dev.jna”. Run from the `visibility`
directory so the reactor is small and resolution is quick.
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services\visibility
mvn -o dependency:tree `
    -pl visibility-s3-archiver,visibility-error-email,visibility-pending-start,visibility-outbound-poller `
    "-Dincludes=org.eclipse.jetty.toolchain.setuid:*,net.java.dev.jna:*"
```

**4 — Check whether the lambdas use Dropwizard/Jetty at all.** (no matches ⇒ they never build a server)
```powershell
# ripgrep equivalent of the grep tool used:
rg "io\.dropwizard|jetty|Configuration" `
   visibility\visibility-s3-archiver\src visibility\visibility-error-email\src `
   visibility\visibility-pending-start\src visibility\visibility-outbound-poller\src
```

**5 — Find which `dropwizard-core` class actually needs `jetty-setuid-jna`.**
A raw byte scan of the jar does not work (class entries are deflated), so extract first, then scan the
extracted `.class` files. Then disassemble the hit to see whether the call is conditional.
```powershell
$d="$env:TEMP\dwcore"
Expand-Archive "$env:USERPROFILE\.m2\repository\io\dropwizard\dropwizard-core\5.0.2\dropwizard-core-5.0.2.jar" -DestinationPath $d
Get-ChildItem $d -Recurse -Filter *.class | ForEach-Object {
  $t=[System.Text.Encoding]::ASCII.GetString([System.IO.File]::ReadAllBytes($_.FullName))
  if ($t -match 'jetty/setuid') { $_.FullName.Replace($d,'') }
}
# -> \io\dropwizard\core\server\AbstractServerFactory.class
& "$env:JAVA_HOME\bin\javap.exe" -p -c -classpath $d io.dropwizard.core.server.AbstractServerFactory |
  Select-String -Pattern "setuid" -Context 12,12
```

**6 — After editing the four poms, confirm the dependency is gone from the lambdas and still present
everywhere else.** The second command is the “no impact on other modules” check.
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services\visibility
mvn -o dependency:tree `
    -pl visibility-s3-archiver,visibility-error-email,visibility-pending-start,visibility-outbound-poller `
    "-Dincludes=org.eclipse.jetty.toolchain.setuid:*,net.java.dev.jna:*"        # -> no jna lines

mvn -o dependency:tree `
    -pl visibility-commons,visibility-inbound,visibility-wm-inbound-processor,visibility-matcher,visibility-outbound,visibility-pending,visibility-itv-gps-processor `
    "-Dincludes=org.eclipse.jetty.toolchain.setuid:*,net.java.dev.jna:*"        # -> all 7 unchanged
```

**7 — Full build with unit + integration tests.**
`verify` (not `package`) is required — failsafe/DynamoDB-Local ITs only run under `verify`, and that
is precisely why the log4j breakage in §6.3 had gone unnoticed.
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services\visibility
mvn -o clean verify
```

**8 — Extract each deployment ZIP and assert no `jna`/`setuid` jar remains in `lib/`.**
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services\visibility
$root = "$env:TEMP\lambda-boot"; New-Item -ItemType Directory $root -Force | Out-Null
foreach ($m in "visibility-s3-archiver","visibility-error-email","visibility-pending-start","visibility-outbound-poller") {
  $zip = Get-ChildItem "$m\target\*-deployment_package.zip" | Select-Object -First 1
  Expand-Archive $zip.FullName -DestinationPath "$root\$m"
  $libs = Get-ChildItem "$root\$m\lib" -Filter *.jar
  $bad  = $libs | Where-Object { $_.Name -match 'jna|setuid' }
  "{0,-28} libJars={1,3}  jna/setuid={2}" -f $m, $libs.Count, $(if($bad){($bad.Name -join ',')}else{"NONE"})
}
```

**9 — Reproduce the pre-fix package in both scan layouts** (to test whether ZIP-vs-directory changes
the findings). The pre-fix `lib/` is the current one plus the two removed jars.
```powershell
$t = "$env:TEMP\prefix-test"
New-Item -ItemType Directory "$t\pkg","$t\jenkinslike","$t\ziponly" -Force | Out-Null
Copy-Item "$env:TEMP\lambda-boot\visibility-outbound-poller\*" "$t\pkg" -Recurse
Copy-Item "$env:USERPROFILE\.m2\repository\net\java\dev\jna\jna-jpms\5.14.0\jna-jpms-5.14.0.jar" "$t\pkg\lib\"
Copy-Item "$env:USERPROFILE\.m2\repository\org\eclipse\jetty\toolchain\setuid\jetty-setuid-jna\2.0.3\jetty-setuid-jna-2.0.3.jar" "$t\pkg\lib\"
Compress-Archive -Path "$t\pkg\*" -DestinationPath "$t\jenkinslike\VisibilityOutboundPoller-prefix.zip" -Force
Copy-Item "$t\pkg\lib" "$t\jenkinslike\lib" -Recurse -Force            # Jenkins layout: exploded lib/ AND the zip
Copy-Item "$t\jenkinslike\VisibilityOutboundPoller-prefix.zip" "$t\ziponly\" -Force
```
```powershell
# A/B scan - identical findings (206 entries) either way; only the reported count differs
foreach ($v in @(@("ziponly","A-zip-only"), @("jenkinslike","B-exploded-dir"))) {
  dependency-check.bat --project $v[1] --scan "$t\$($v[0])" --out "owasp-reports\ab\$($v[1])" --noupdate --format JSON
}
```

**10 — Prove the `jna` finding is a suppressed false positive.**
`--disableHostedSuppressions` alone is *not* sufficient: an already-downloaded
`publishedSuppressions.xml` is still applied. Clone the data directory (so the shared
dependency-check install is never modified) and delete the file there.
```powershell
# (a) confirm the upstream FP rule exists locally
Select-String -Path "C:\dependency-check\dependency-check-current\data\publishedSuppressions.xml" `
              -Pattern "sun:java_se" -Context 4,4

# (b) clone the data dir WITHOUT the hosted suppression list
$dst = "$env:TEMP\dc-data-nosupp"
New-Item -ItemType Directory $dst -Force | Out-Null
Copy-Item "C:\dependency-check\dependency-check-current\data\*" $dst -Recurse -Force
Remove-Item "$dst\publishedSuppressions.xml","$dst\publishedSuppressions.xml.properties" -Force

# (c) scan the jar alone -> reproduces Jenkins exactly (sun:java_se, LOW, 9 CVEs / 4 HIGH)
dependency-check.bat --project "jna-nosupp" `
  --scan "$env:USERPROFILE\.m2\repository\net\java\dev\jna\jna-jpms\5.14.0\jna-jpms-5.14.0.jar" `
  --data $dst --out "owasp-reports\jna-nosupp" --noupdate --disableHostedSuppressions --format JSON
```

**11 — Show that Jenkins catalogues every jar twice.**
```powershell
@'
import re
from pathlib import Path
c = Path(r"C:\Users\arijit.kundu\Downloads\VisibilityOutboundPoller-26.09.002-OWASP.html").read_text(encoding="utf-8", errors="ignore")
loose = set(re.findall(r"/VisibilityOutboundPoller-26\.09\.002-\d+/lib/([A-Za-z0-9_.\-]+\.jar)", c))
inzip = set(re.findall(r"/VisibilityOutboundPoller-26\.09\.002\.zip/lib/([A-Za-z0-9_.\-]+\.jar)", c))
print("loose lib/ jars:", len(loose), "| in-zip jars:", len(inzip), "| in BOTH:", len(loose & inzip))
'@ | python -
```

**12 — Boot each lambda from its deployment package.**
`BootCheck.java` (kept out of the repo, in `$env:TEMP\lambda-boot`) mimics the AWS Lambda cold start:
`Class.forName(handler, initialize=true)` then the public no-arg constructor. It exits **2** on any
`NoClassDefFoundError` / `ClassNotFoundException` / `LinkageError`, and treats a constructor that
fails on missing AWS env vars as success, because that means application code was reached.
```powershell
$root = "$env:TEMP\lambda-boot"
& "$env:JAVA_HOME\bin\javac.exe" -d $root "$root\BootCheck.java"
$env:AWS_REGION="us-east-1"; $env:AWS_DEFAULT_REGION="us-east-1"
$map = @{
 "visibility-s3-archiver"     = "com.inttra.mercury.visibility.lambda.VisibilityS3Archiver"
 "visibility-error-email"     = "com.inttra.mercury.visibility.lambda.VisibilityErrorEmail"
 "visibility-pending-start"   = "com.inttra.mercury.visibility.lambda.VisibilityPendingStart"
 "visibility-outbound-poller" = "com.inttra.mercury.visibility.lambda.VisibilityOutboundPoller"
}
foreach ($m in $map.Keys | Sort-Object) {
  # classpath = zip root (handler classes) + every jar in lib/, exactly as Lambda sees it
  & "$env:JAVA_HOME\bin\java.exe" -cp "$root;$root\$m;$root\$m\lib\*" BootCheck $map[$m]
  "  exit=$LASTEXITCODE"
}
```

**13 — Constant-pool scan of the whole deployed classpath** for anything still referencing the removed
package (only Dropwizard's own dead `AbstractServerFactory` remains).
```powershell
@'
import zipfile, glob, os
root = os.path.join(os.environ["TEMP"], "lambda-boot")
needle = b"org/eclipse/jetty/setuid"
for mod in sorted(os.listdir(root)):
    d = os.path.join(root, mod, "lib")
    if not os.path.isdir(d): continue
    for jar in glob.glob(os.path.join(d, "*.jar")):
        with zipfile.ZipFile(jar) as z:
            for n in z.namelist():
                if n.endswith(".class") and needle in z.read(n):
                    print(f"{mod}: {os.path.basename(jar)} :: {n}")
'@ | python -
```

**14 — OWASP re-scan of the four rebuilt packages.**
`--noupdate` reuses the local NVD cache (fast); drop it, or use `--nvdApiKey $env:NVD_API_KEY`, to
refresh first.
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services
foreach ($m in "visibility-s3-archiver","visibility-error-email","visibility-pending-start","visibility-outbound-poller") {
  $zip = (Get-ChildItem "visibility\$m\target\*-deployment_package.zip" | Select-Object -First 1).FullName
  dependency-check.bat --project "$m-deployment-package" --scan "$zip" `
      --out "owasp-reports\visibility-lambda-after\$m" `
      --suppression "visibility\$m\suppressions.xml" `
      --noupdate --format HTML --format JSON
}
```

**15 — Summarise the JSON reports by severity** (and assert no `jna` artifact survives).
```powershell
@'
import json, os
from collections import Counter
base = r"C:\Users\arijit.kundu\projects\mercury-services\owasp-reports\visibility-lambda-after"
for mod in sorted(os.listdir(base)):
    d = json.load(open(os.path.join(base, mod, "dependency-check-report.json"), encoding="utf-8"))
    counts, jna = Counter(), False
    for dep in d.get("dependencies", []):
        if "jna" in dep.get("fileName","").lower(): jna = True
        sevs = {(v.get("severity") or "").upper() for v in (dep.get("vulnerabilities") or [])}
        if sevs:
            for s in ("CRITICAL","HIGH","MEDIUM","LOW"):
                if s in sevs: counts[s] += 1; break
    print(f"{mod:30} CRITICAL={counts['CRITICAL']} HIGH={counts['HIGH']} "
          f"MEDIUM={counts['MEDIUM']} LOW={counts['LOW']}  jna present={jna}")
'@ | python -
```

**16 — Keep the change set clean.** The build regenerates
`visibility-inbound/generated/swagger-ui/visibility-1.0.json`; revert it so the diff is only the poms.
```powershell
git checkout -- visibility/visibility-inbound/generated/swagger-ui/visibility-1.0.json
git --no-pager diff --stat
```

---

## 9. Files changed

| File | Change |
|---|---|
| `visibility/visibility-s3-archiver/pom.xml` | exclude `jetty-setuid-jna` (×3 deps); `log4j-core` → `${log4j.version}` |
| `visibility/visibility-pending-start/pom.xml` | exclude `jetty-setuid-jna` (×3 deps) |
| `visibility/visibility-outbound-poller/pom.xml` | exclude `jetty-setuid-jna` (×3 deps) |
| `visibility/visibility-error-email/pom.xml` | exclude `jetty-setuid-jna` (on `visibility-commons`) |

No production Java source changed; no other visibility module is affected.

---

## 10. Residual risk

| Risk | Assessment |
|---|---|
| A lambda needs `SetUIDListener` at runtime | None. It is only reachable via `AbstractServerFactory.buildServer(...)`, and the lambdas never build a Jetty `Server`. Proven by boot-testing all four handlers from their actual deployment ZIPs (§7.4) and by a constant-pool scan of ~220 jars per package (§7.5 / §8 command 13). |
| A future dependency reintroduces `jetty-setuid-jna` on a fourth path | The exclusion is applied to all three `com.inttra.mercury` compile dependencies in each lambda, covering every current path. A new path would reappear in CI as the same FP; re-run §8 command 6 if it does. |
| Other visibility modules regress | None. All seven still resolve `jetty-setuid-jna:2.0.3 → jna-jpms:5.14.0` unchanged (§7.1), and the full reactor builds and tests green (§7.3). |
| `jackson-databind` / `jsoup` HIGHs | Knowingly deferred under the agreed two-week release exception; both jars still ship unchanged. |
