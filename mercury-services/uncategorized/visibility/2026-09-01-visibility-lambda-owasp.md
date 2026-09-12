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
| 2 | `jackson-databind-2.22.0.jar` | 5 | Highest | no — release exception (code freeze); see §9 |
| 3 | `jsoup-1.17.2.jar` | 2 | Highest | no — release exception (code freeze); see §9 |

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

**That command was correct — nothing was being done wrong.** There are *three* independent causes,
each confirmed by a controlled experiment below. All three are environmental, not a mistake in how
the scan was invoked.

The single most useful summary is that **the three HIGHs come from two different data sources**, and
each source is disabled in a different place:

| Finding | Source | Local (DC 12.2.2) | Local (DC 13.0.0) | Jenkins (DC 13.0.0) |
|---|---|---|---|---|
| `jna-jpms` — `sun:java_se`, 9 CVEs | **NVD** | hidden (hosted suppressions) | hidden (hosted suppressions) | **shown** |
| `jackson-databind` CVE-2026-68497 | **OSS Index** | **shown** | hidden (no token) | **shown** |
| `jsoup` CVE-2026-75140 | **OSS Index** | **shown** | hidden (no token) | **shown** |

That single table explains the whole puzzle: the scan that showed jackson+jsoup-but-not-jna was
column 3, and the current local scans are column 4.

### 5.1 The missing `jna` finding — hosted suppressions

A developer workstation has internet access, so dependency-check downloads
`<data>/publishedSuppressions.xml` and applies the upstream `sun:java_se` rule from §4. The CPE is
stripped before the vulnerability lookup, so the dependency reports **0 vulnerabilities and an empty
`vulnerabilityIds` list**. The Jenkins agent evidently cannot reach that URL, so the rule is not
applied and the false positive surfaces.

A useful subtlety: **`--disableHostedSuppressions` is not enough to reproduce Jenkins.** That flag
stops the file being *refreshed*, not being *used* — an already-downloaded copy is still applied. The
CI behaviour only reproduces once the file is actually absent from the data directory.

**Proof — rename the file in place and rescan the pre-fix package (§8, command 10).** This was run
against a reconstructed pre-fix `visibility-s3-archiver` deployment ZIP (222 jars = the current 220
plus `jna-jpms-5.14.0.jar` and `jetty-setuid-jna-2.0.3.jar`):

| Local run | `publishedSuppressions.xml` | CPE assigned | Vulnerabilities on `jna-jpms-5.14.0.jar` |
|---|---|---|---:|
| default | present | none | **0** |
| `--disableHostedSuppressions` | present (still applied) | none | **0** |
| **renamed to `.DISABLED`** | **absent** | `cpe:2.3:a:sun:java_se:5.14.0` (LOW) | **9 → 4 HIGH + 5 MEDIUM** |
| renamed back | present again | none | **0** |

```
jna-jpms   VisibilityS3Archiver-prefix.zip: jna-jpms-5.14.0.jar   {'HIGH': 4, 'MEDIUM': 5}
           ['CVE-2009-2476', 'CVE-2009-2689', 'CVE-2009-2475', 'CVE-2009-2716', ...]
```

This is an exact match for the Jenkins report, on a full package scan rather than an isolated jar,
and it is fully reversible — renaming the file back returns the count to 0.

> **Gotcha when doing this.** With the file renamed away, DC logs
> `Hosted suppressions using snapshot as of this Dependency-Check release` and **writes a fresh
> `publishedSuppressions.xml` from the snapshot bundled inside the jar** (82,965 B) into the data
> directory. That is *not* your original downloaded list (85,038 B). To restore properly you must
> delete the snapshot copy and rename your backup back — see §8 command 10.

### 5.2 The missing `jackson`/`jsoup` HIGHs — OSS Index needs a token in DC 13

Both of those HIGHs are **OSS Index findings, not NVD findings** — the CI report labels them
`(OSSINDEX)`. And DC 13.0.0 logs this on a local run:

```
[WARN] Sonatype OSS Index Analyzer disabled due to missing credentials. Authentication with token
       is now required, and OSS Index is migrating to Sonatype Guide.
```

Confirmed from the local JSON reports — every finding is NVD-sourced, and the HTML contains the
string `OSSINDEX` **zero** times:

```
visibility-error-email   vuln sources present: ['NVD']
OSSINDEX mentions in local HTML report: 0
```

whereas the Jenkins reports contain 25-41 `OSSINDEX` hits each, on the same DC 13.0.0. **So the CI
job has an OSS Index token configured and the workstation does not.**

Under **DC 12.2.2** the OSS Index analyzer still worked anonymously. That is why the earlier local
scan surfaced jackson and jsoup: it was run on 12.2.2, before today's upgrade.

Consequence: **a local DC 13.0.0 scan without a token cannot see roughly a third of what CI sees.**
Treat a local `HIGH = 0` as "no NVD HIGHs", never as "clean".

#### 5.2.1 How to supply the token

The relevant CLI options on 13.0.0 (`dependency-check.bat --advancedHelp`):

| Option | Meaning |
|---|---|
| `--ossIndexPassword <token>` | **The token.** "Sets the Sonatype Guide personal access token or (deprecated) legacy OSS Index API token" |
| `--ossIndexUsername <user>` | Only for **legacy** OSS Index API tokens; not needed with a Guide PAT |
| `--ossIndexUrl <url>` | Defaults to `https://api.guide.sonatype.com` on 13.0.0 — do **not** override |
| `--ossIndexCacheValidForHours <h>` | Default 24. Raise it to burn fewer Sonatype Guide credits |
| `--ossIndexRemoteErrorWarnOnly <bool>` | Downgrade an OSS Index failure from fatal to a warning |
| `--disableOssIndex` | Turn the analyzer off entirely |

There is no `--ossIndexToken` option — the token goes in the ***password*** slot either way.

**The exact enable/disable rule.** Simply setting a password is *not* enough, which cost me two
failed attempts before I disassembled `OssIndexAnalyzer.prepareAnalyzer()`
(`javap -p -c`, see §8 command 22). The gate is:

```java
// paraphrased from the 13.0.0 bytecode
if (password.isEmpty()
        || (user.isEmpty() && !password.startsWith("sonatype_pat_"))) {
    LOG.warn("{} disabled due to missing credentials...");
    setEnabled(false);
}
```

So the analyzer only switches on when **either**:

* **Sonatype Guide PAT (preferred)** — `analyzer.ossindex.password` starts with the literal prefix
  **`sonatype_pat_`**, and *no username is needed*; **or**
* **Legacy OSS Index token** — **both** `analyzer.ossindex.user` *and* `analyzer.ossindex.password`
  are set. This path additionally logs a deprecation warning: legacy tokens must be replaced with a
  Guide PAT **before 2026-12-31**.

A password that is neither prefixed nor accompanied by a username is silently ignored and you get
the exact WARN we were chasing. Get a PAT from <https://guide.sonatype.com/>.

**Do not put the token on the command line.** DC itself objects:

```
[WARN] ossIndexPassword used on the command line, consider moving the password to a properties
       file using the key `analyzer.ossindex.password` and using the --propertyfile argument instead
```

— and, as with the NVD key, a command-line value is readable by any local process via
`Get-CimInstance Win32_Process` and lands in your PowerShell history. Use `-P`/`--propertyfile`.
The keys were confirmed against the string constants compiled into
`dependency-check-core-13.0.0.jar`:

```powershell
# one-time: write a private property file outside the repo
$props = "$env:USERPROFILE\.dependency-check\dc.properties"
New-Item -ItemType Directory -Force -Path (Split-Path $props) | Out-Null
@"
analyzer.ossindex.password=sonatype_pat_XXXXXXXXXXXXXXXX
analyzer.ossindex.cache.validforhours=168
nvd.api.key=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
"@ | Set-Content $props -Encoding ascii

# lock it down to your account only
icacls $props /inheritance:r /grant:r "$($env:USERNAME):(R)" | Out-Null

# safer alternative to typing the token into the file: paste it at a prompt, so the
# value never appears in the script, on a command line, or in PowerShell history
$sec   = Read-Host "Paste your Sonatype Guide PAT" -AsSecureString
$plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
           [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
(Get-Content $props) -replace 'PASTE_TOKEN_HERE', $plain | Set-Content $props -Encoding ascii
Remove-Variable plain, sec

# then every scan just references it - no secrets on the command line or in history
dependency-check.bat --project "visibility-s3-archiver" `
  --scan "path\to\deployment_package" `
  --propertyfile $props `
  --out "owasp-reports\s3-archiver" --format HTML --format JSON
```

For a **legacy** token add `analyzer.ossindex.user=<your-oss-index-email>` alongside the password.

**Verified behaviour** (dummy values, single-jar scan, §8 command 22):

| `analyzer.ossindex.password` | `analyzer.ossindex.user` | Result |
|---|---|---|
| *(unset)* | *(unset)* | `disabled due to missing credentials` — analyzer never runs |
| `DUMMY_TOKEN` | *(unset)* | **still** `disabled due to missing credentials` — no `sonatype_pat_` prefix |
| `sonatype_pat_DUMMY…` | *(unset)* | **enabled** → runs, then `invalid credentials` from the API (expected with a fake PAT) |
| `legacy_api_token…` | `someone@e2open.com` | **enabled** → runs, plus the "replace legacy token before 2026-12-31" warning |

The transition from *"disabled due to missing credentials"* to *"invalid credentials"* is the signal
that the credential was actually picked up. With a real PAT that second message disappears too.

**Confirming it worked on a real scan:**

```powershell
# 1. the disabled-analyzer WARN must be gone
dependency-check.bat ... --propertyfile $props 2>&1 | Select-String "OSS Index Analyzer disabled"
#    -> no output when the token is accepted

# 2. the report must now carry OSSINDEX-sourced findings
(Select-String -Path "owasp-reports\s3-archiver\dependency-check-report.html" `
               -Pattern "OSSINDEX" -AllMatches).Matches.Count
#    -> 0 before, 25-41 after (matching the Jenkins reports, i.e. the jackson + jsoup HIGHs appear)
```

Note that an OSS Index auth/remote failure is **fatal by default** — the run above exited with code
`14`. Add `--ossIndexRemoteErrorWarnOnly true` (verified: exit code returns to `0`) if you do not
want a flaky OSS Index to break a build.

> **Credit warning.** Sonatype Guide free accounts are metered per component report, unlike the old
> anonymous OSS Index. Preserve the DC `data` directory between runs (the OSS Index cache lives
> there) and consider `analyzer.ossindex.cache.validforhours=168` locally, so repeated scans of the
> same 200+ jars do not burn credits. This is also an argument for enabling OSS Index on a scheduled
> CI job rather than on every commit.

#### 5.2.2 The NVD API key is a *separate* concern — and is **not** read from the environment

Worth stating plainly, because it is easy to assume otherwise (I initially did, and was wrong):
**dependency-check does not read an `NVD_API_KEY` environment variable.** The string `NVD_API_KEY`
does appear inside `dependency-check-cli-13.0.0.jar` and `dependency-check-utils-13.0.0.jar`, but
only as the *Java constant name* for `CliParser.ARGUMENT.NVD_API_KEY` and `Settings.KEYS.NVD_API_KEY`
— whose value is the property `nvd.api.key`. Disassembling the only two classes in the whole
distribution that call `System.getenv` confirms it:

* `App.determineName()` reads **`ODC_NAME`** only (used to label the run)
* `utils/scarf/TelemetryCollector` — telemetry

So if you have `$env:NVD_API_KEY` set, DC silently ignores it. You must pass `--nvdApiKey` or, better,
put `nvd.api.key=...` in the property file.

**What you lose by omitting it — and what you don't.** The NVD key affects **only the download /
refresh of the NVD cache**, never the analysis of data already cached. Concretely:

* with `--noupdate`, the key is irrelevant — nothing is missed;
* without `--noupdate`, DC first checks whether the cache is stale. `nvd.api.check.validforhours=4`
  (shipped default) means it will not even contact the NVD if the cache was refreshed in the last
  4 hours;
* when it *does* update, the shipped rate limits are
  `nvd.api.requestsperthirtysecondswithoutapikey=5` versus
  `nvd.api.requestsperthirtysecondswithapikey=50` — a **10x** difference. Without a key an update is
  very slow and prone to throttling/timeouts, and a failed update leaves you analysing **stale NVD
  data**, i.e. blind to recently published CVEs.

The bookkeeping lives in the H2 database, not in a file, so it can be inspected directly:

```powershell
$h2 = Get-ChildItem "C:\dependency-check\dependency-check-current\lib" -Filter "h2-*.jar" |
        Select-Object -First 1
java -cp $h2.FullName org.h2.tools.Shell `
  -url "jdbc:h2:file:C:\dependency-check\dependency-check-current\data\odc;ACCESS_MODE_DATA=r;IFEXISTS=TRUE" `
  -user dcuser -password "DC-Pass1337!" -sql "select * from properties"
```
```
ID                    | VALUE
version               | 5.6
nvd.api.last.checked  | 2026-09-01T19:35:37-04
nvd.api.last.modified | 2026-09-01T23:30:58Z
kev.checked           | 1788305738
```

`ACCESS_MODE_DATA=r` opens it read-only so an inspection cannot corrupt the cache; `dcuser` /
`DC-Pass1337!` are dependency-check's built-in defaults. This is the quickest way to answer "is my
NVD data actually current?" — and it explains why a scan run at 21:00 on 2026-09-01 needed no key at
all: the cache had been refreshed at 19:35, well inside the 4-hour window.

**Recommended final property file** (single place for both credentials, ACL-restricted, nothing on
the command line):

```properties
# ~/.dependency-check/dc.properties   - DO NOT COMMIT
analyzer.ossindex.password=<sonatype_pat_...>
analyzer.ossindex.cache.validforhours=168
nvd.api.key=<uuid>
```

### 5.3 Was copying the 12.2.2 `data` directory into 13.0.0 a mistake?

**No — it is not the cause of anything here, and the suppression file is not invalid.** Evidence:

| Check | Result |
|---|---|
| `dependency-check-current` | symlink → `dependency-check-13.0.0` |
| `12.2.2/data` last refreshed | 2026-08-31 19:48 (`publishedSuppressions.xml` 84,781 B) |
| `13.0.0/data` after the copy + first run | 2026-09-01 15:16 (`publishedSuppressions.xml` **85,038 B**) |
| `*.properties` marker | grew 56 → 59 bytes — rewritten by 13.0.0 |
| `odc.mv.db` | 249,405,440 → **249,643,008 B**, 2026-09-01 15:30 |
| H2 schema | accepted; no schema-mismatch error, scans complete normally |
| Suppression file functional? | **yes** — §5.1 shows renaming it flips `jna` 0 → 9 vulns and back |

So 13.0.0 took over the inherited data directory cleanly, re-downloaded the hosted suppression list
and `jsrepository.json` under its own version marker, and updated the NVD H2 database. The copy was
harmless.

The 12.2.2 → 13.0.0 **upgrade itself** is what changed the result — via §5.2, not via the data
directory. If you want to eliminate the variable entirely, point 13.0.0 at an empty `--data` dir and
let it build its own; it costs one full NVD download.

### 5.4 The dependency count — Jenkins scans the package twice

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
findings either way. **The layout inflates the count; it does not change the findings.**

Note also that the OWASP report is *not* produced by `dependency-check-maven` — that plugin is
commented out in the root `pom.xml`. The Jenkins job runs the DC CLI as its own step and feeds the
result to Sonar via `-Dsonar.dependencyCheck.htmlReportPath=...`, which is why its scan root is a
workspace directory rather than a single artifact.

### 5.5 Recommendations for the CI/platform team

1. **Give the Jenkins agent egress to the hosted-suppression URL** (or commit a copy of
   `publishedSuppressions.xml` and pass `--suppression`). Otherwise every upstream-known false
   positive will keep appearing in CI only, and each will cost a manual investigation like this one.
2. **Publish the OSS Index token to developers** (a shared read-only Sonatype Guide token, or
   document `--ossIndexUsername` / `--ossIndexApiToken`). Without it, no one can reproduce a CI
   finding locally on DC 13, and local scans give a false sense of safety.
3. **Point the CLI at the artifact, not the workspace directory** (`--scan .../target/*.zip`), to
   halve the reported dependency count and make CI and local numbers comparable.

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
hardcoding `log4j-core` at `2.23.1` while every other module uses `${log4j.version}`.

Before yesterday the two agreed, so nothing was broken:

```
before 08a0c83d41:   visibility/pom.xml   <log4j.version>2.23.1</log4j.version>
                     s3-archiver/pom.xml  log4j-core 2.23.1            -> match, IT passes
after  08a0c83d41:   visibility/pom.xml   <log4j.version>2.25.5</log4j.version>
                     s3-archiver/pom.xml  log4j-core 2.23.1 (hardcoded) -> log4j-api 2.25.5
                                                                          + log4j-core 2.23.1
                                                                          = NoSuchMethodError
```

Fixed by making it track the property, consistent with `visibility-commons`,
`visibility-inbound` and `visibility-wm-inbound-processor`:

```xml
<version>${log4j.version}</version>
```

**Note the scope**: `log4j-core` is `<scope>test</scope>` in this module — it exists only because
embedded DynamoDB Local needs a logging backend at IT runtime. So this fix **changes nothing in the
deployed artifact**; it only repairs the integration test.

#### Why nobody saw it — the IT is never executed

The obvious question is how this survived a full reactor build. It survived because
**neither the documented local command nor the CI job ever reaches the `integration-test` phase.**

Yesterday's local verification, as recorded in `2026-08-31-visibility-owasp-refactor.md` line 199:

```
mvn -pl visibility -amd clean package
```

`maven-failsafe-plugin` binds to `integration-test` / `verify`, both of which come *after* `package`
in the default lifecycle. `package` stops one phase short, so `VisibilityS3ArchiverIT` never ran.

The Jenkins job for this module does the same thing:

```sh
$M2_HOME/bin/mvn -ntp -Dorg.slf4j.simpleLogger.defaultLogLevel=warn \
    package sonar:sonar -P mercury-commons,sonar \
    -Dsonar.projectName=Ocean-Logistics-VisibilityS3Archiver \
    -Dsonar.projectKey=mercury-services.visibility-visibility-s3-archiver \
    -Dsonar.dependencyCheck.htmlReportPath=visibility/visibility-s3-archiver/target/dependency-check-report.html \
    -Dsonar.projectVersion=${RELEASE} -pl ${app_dir} --also-make
```

`package sonar:sonar` — again, no `verify`. The timeline confirms CI genuinely ran the broken
combination and still went green:

| Event | Time (UTC) |
|---|---|
| PR #1226 (`Feature/ION-16693 visibility owasp`) merged to `develop`, bumping `log4j.version` to 2.25.5 | **2026-09-01 07:18** |
| Jenkins built `VisibilityS3Archiver-26.09.002` (workspace stamp `1788253326`) | **2026-09-01 09:02** |
| That build **succeeded** and published an OWASP report | — |

So the CI build ran ~1h44m *after* the version bump landed, with `log4j-core 2.23.1` against
`log4j-api 2.25.5` on the test classpath, and passed — because it never ran the test.

**You were not missing anything.** `mvn -o clean verify` on this branch is, as far as I can tell, the
first time `VisibilityS3ArchiverIT` has been executed since the bump. Two follow-ups worth raising
separately:

* the CI job should run `verify` (or `mvn package failsafe:integration-test failsafe:verify`) so
  DynamoDB-Local ITs actually gate the build;
* until it does, use `mvn -o clean verify` locally rather than `package` when changing shared
  version properties.

---

## 7. Verification

### 7.1 Dependency resolution

Re-run with `-am` after the §2.1 discovery, so these figures are not subject to the stale-POM trap:

| Module set | `jetty-setuid-jna` / `jna-jpms` after the change |
|---|---|
| the 4 lambdas | **absent** |
| `visibility-commons`, `-inbound`, `-wm-inbound-processor`, `-matcher`, `-outbound`, `-pending`, `-itv-gps-processor` | still `jetty-setuid-jna:2.0.3` → `jna-jpms:5.14.0`, **unchanged** (7/7) |

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

**Read the `HIGH = 0` column with §5 firmly in mind — it does *not* mean the packages are clean.**
Two independent local blind spots produce that zero:

* `jna-jpms` would have been hidden anyway by the hosted suppression list (§5.1);
* the `jackson-databind` and `jsoup` HIGHs are **OSS Index** findings, and the OSS Index analyzer is
  disabled on this workstation for lack of a token (§5.2). Locally, `jackson-databind` shows only
  CVE-2026-54515 (MEDIUM, from NVD) and `jsoup` shows nothing at all.

So this table is **not** a like-for-like prediction of the next Jenkins run.

The tool-independent guarantee is the last column: **`jna-jpms-5.14.0.jar` is no longer in the
artifact**, so the finding cannot be reported again by any scanner configuration. `jsoup-1.17.2.jar`
and `jackson-databind-2.22.0.jar` are still present, as intended.

### 7.6 Definitive re-scan *with* an OSS Index token (2026-09-01 21:32)

Once the Sonatype Guide PAT was configured per §5.2.1, the s3-archiver package was re-scanned with
the exact command documented above. This is the like-for-like comparison against Jenkins that §7.5
could not provide, and it closes out every claim in this document:

```powershell
$props = "$env:USERPROFILE\.dependency-check\dc.properties"
dependency-check.bat --project "VisibilityS3Archiver" `
  --scan "...\visibility-s3-archiver-1.0-deployment_package.zip" `
  --propertyfile $props --out "owasp-reports\verify-s3-archiver" `
  --format HTML --format JSON --ossIndexRemoteErrorWarnOnly true
```
```
[INFO] Skipping the NVD API Update as it was completed within the last 240 minutes
[INFO] Finished Sonatype OSS Index Analyzer (7 seconds)
[INFO] Analysis Complete (37 seconds)          exit 0
```

Report contents:

| Metric | Before token | After token | Meaning |
|---|---:|---:|---|
| `OSSINDEX` mentions | 0 | **25** | token accepted; the analyzer really ran (§5.2) |
| `jna-jpms` mentions | 0 | **0** | the fix holds — artifact absent, not merely suppressed (§6) |
| `jetty-setuid` mentions | 0 | **0** | the excluded parent artifact is gone too |
| HIGH findings | 0 | **2** | both OSS Index-sourced, both expected |

Severity/source breakdown and the surviving HIGHs:

```
severity counts: {'MEDIUM': 10, 'HIGH': 2}
vuln sources   : {'OSSINDEX': 8, 'NVD': 4}

HIGH  OSSINDEX  CVE-2026-68497  ...deployment_package.zip: jackson-databind-2.22.0.jar
HIGH  OSSINDEX  CVE-2026-75140  ...deployment_package.zip: jsoup-1.17.2.jar
```

Four conclusions are now evidence-backed rather than inferred:

1. **The `jna-jpms` HIGH is gone** — zero mentions in a fully-credentialed scan.
2. **The two remaining HIGHs are exactly the two under the release exception**, and their CVE ids
   match §9 precisely (`CVE-2026-68497` jackson-databind, `CVE-2026-75140` jsoup).
3. **Both are `OSSINDEX`-sourced**, confirming the §5.2 diagnosis that the earlier local/Jenkins
   disagreement was a missing OSS Index credential, not a data-directory or suppression problem.
4. **The NVD-vs-OSS Index split is real**: 4 NVD findings vs 8 OSS Index findings in one package —
   i.e. a token-less local scan was blind to two-thirds of the vulnerabilities.

The `Skipping the NVD API Update as it was completed within the last 240 minutes` line is also direct
confirmation of the `nvd.api.check.validforhours=4` behaviour described in §5.2.2.

**Expected next Jenkins scan:** 2 HIGH (`jackson-databind`, `jsoup` — under the agreed exception)
instead of 3, with the `jna-jpms` row gone entirely, and ~2 fewer jars per package.

---

## 8. Commands used

Every command below was run from PowerShell on Windows. `$env:TEMP` is used for scratch work so
nothing lands in the repo.

> **Two safety notes.**
> 1. Pass the NVD key as `--nvdApiKey $env:NVD_API_KEY`, never inline. A literal key on the command
>    line is visible to any user on the box via `Get-CimInstance Win32_Process` and is retained in
>    PowerShell history.
> 2. Commands 10(c) and 10a temporarily modify the **shared** `C:\dependency-check` install. They are
>    wrapped in `try/finally` for that reason — check the data directory is restored before moving on.

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

> **Always add `-am`.** Without it, sibling modules such as `visibility-commons` are resolved from
> `~/.m2` using their *installed* POMs, which may be weeks stale — that is exactly what produced the
> bogus `commons 1.0.27-SNAPSHOT` reading described in §2.1.

```powershell
cd C:\Users\arijit.kundu\projects\mercury-services\visibility
mvn -o dependency:tree -am `
    -pl visibility-s3-archiver,visibility-error-email,visibility-pending-start,visibility-outbound-poller `
    "-Dincludes=org.eclipse.jetty.toolchain.setuid:*,net.java.dev.jna:*"
```

**3a — Demonstrate the stale-POM trap (§2.1).** Compare the two forms and inspect the installed
parent POM that supplies the property.
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services\visibility
mvn -o dependency:tree -pl visibility-error-email     "-Dincludes=com.inttra.mercury:*"   # -> 1.0.27-SNAPSHOT (wrong)
mvn -o dependency:tree -pl visibility-error-email -am "-Dincludes=com.inttra.mercury:*"   # -> 1.0.33-SNAPSHOT (right)

# the culprit: the installed parent POM still carries the old property value
Select-String -Path "$env:USERPROFILE\.m2\repository\com\inttra\mercury\visibility\1.0\visibility-1.0.pom" `
              -Pattern "mercury.commons.version"
Get-Item "$env:USERPROFILE\.m2\repository\com\inttra\mercury\visibility\1.0\visibility-1.0.pom" |
  Select-Object LastWriteTime      # -> 2026-07-24, i.e. five weeks stale
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
`publishedSuppressions.xml` is still applied. Two ways to get past it — (b) is non-destructive,
(c) is the in-place rename and is the one that produced the §5.1 table.

```powershell
# (a) confirm the upstream FP rule exists locally
Select-String -Path "C:\dependency-check\dependency-check-current\data\publishedSuppressions.xml" `
              -Pattern "sun:java_se" -Context 4,4

# (b) NON-DESTRUCTIVE: clone the data dir WITHOUT the hosted suppression list
$dst = "$env:TEMP\dc-data-nosupp"
New-Item -ItemType Directory $dst -Force | Out-Null
Copy-Item "C:\dependency-check\dependency-check-current\data\*" $dst -Recurse -Force
Remove-Item "$dst\publishedSuppressions.xml","$dst\publishedSuppressions.xml.properties" -Force

dependency-check.bat --project "jna-nosupp" `
  --scan "$env:USERPROFILE\.m2\repository\net\java\dev\jna\jna-jpms\5.14.0\jna-jpms-5.14.0.jar" `
  --data $dst --out "owasp-reports\jna-nosupp" --noupdate --disableHostedSuppressions --format JSON
```

**(c) In-place rename against a full pre-fix package.** First rebuild a pre-fix ZIP (220 current jars
+ the 2 removed ones = 222), then rename the suppression file, scan, and restore. The `try/finally`
guarantees the shared install is restored even if the scan throws.

```powershell
# --- rebuild the pre-fix deployment package -------------------------------
$t = "$env:TEMP\prefix2"
Remove-Item $t -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory "$t\pkg","$t\zip" -Force | Out-Null
Copy-Item "$env:TEMP\lambda-boot\visibility-s3-archiver\*" "$t\pkg" -Recurse -Force
Copy-Item "$env:USERPROFILE\.m2\repository\net\java\dev\jna\jna-jpms\5.14.0\jna-jpms-5.14.0.jar" "$t\pkg\lib\"
Copy-Item "$env:USERPROFILE\.m2\repository\org\eclipse\jetty\toolchain\setuid\jetty-setuid-jna\2.0.3\jetty-setuid-jna-2.0.3.jar" "$t\pkg\lib\"
Compress-Archive -Path "$t\pkg\*" -DestinationPath "$t\zip\VisibilityS3Archiver-prefix.zip" -Force
"lib jars: " + (Get-ChildItem "$t\pkg\lib" -Filter *.jar).Count      # -> 222

# --- rename the hosted suppression list, scan, restore --------------------
$data = "C:\dependency-check\dependency-check-current\data"
$out  = "owasp-reports\q5-renamed-supp"
New-Item -ItemType Directory $out -Force | Out-Null
try {
  Rename-Item "$data\publishedSuppressions.xml" "publishedSuppressions.xml.DISABLED" -Force
  & "C:\dependency-check\dependency-check-current\bin\dependency-check.bat" `
      --project "q5-prefix-supp-renamed" --scan "$t\zip\VisibilityS3Archiver-prefix.zip" `
      --out $out --noupdate --disableHostedSuppressions `
      --format JSON --format HTML --log "$out\dc.log"
} finally {
  # DC writes a FRESH bundled snapshot (82,965 B) while the real file is renamed away.
  # Delete that, then put the original (85,038 B) back.
  Remove-Item "$data\publishedSuppressions.xml" -Force -ErrorAction SilentlyContinue
  Rename-Item "$data\publishedSuppressions.xml.DISABLED" "publishedSuppressions.xml" -Force
}
Get-ChildItem $data -Filter "publishedSuppressions*" | Select-Object Name,Length,LastWriteTime
```

Result — an exact match for Jenkins:

```
jna-jpms   VisibilityS3Archiver-prefix.zip: jna-jpms-5.14.0.jar   {'HIGH': 4, 'MEDIUM': 5}
           ['CVE-2009-2476', 'CVE-2009-2689', 'CVE-2009-2475', 'CVE-2009-2716', ...]
```

**10a — Confirm the restore actually worked** (must print 0; also confirms the file is *functional*,
which is the direct answer to “is my copied-over suppressions file valid?”).
```powershell
dependency-check.bat --project "q5-restored" `
  --scan "$env:USERPROFILE\.m2\repository\net\java\dev\jna\jna-jpms\5.14.0\jna-jpms-5.14.0.jar" `
  --out "owasp-reports\q5-restored-check" --noupdate --format JSON
@'
import json
d=json.load(open(r"owasp-reports\q5-restored-check\dependency-check-report.json",encoding="utf-8"))
print("jna vulns after restore:", sum(len(x.get("vulnerabilities") or []) for x in d["dependencies"]))
'@ | python -      # -> 0
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

**17 — Determine which vulnerability sources actually ran locally.** This is what exposed the OSS
Index gap in §5.2. The `--log` file carries the analyzer warnings; the JSON carries the sources.
```powershell
# the WARN that explains the missing jackson/jsoup HIGHs
Select-String -Path "owasp-reports\q5-renamed-supp\dc.log" -Pattern "OSS Index"
# -> [WARN] Sonatype OSS Index Analyzer disabled due to missing credentials.

@'
import json
d = json.load(open(r"owasp-reports\visibility-lambda-after\visibility-error-email\dependency-check-report.json", encoding="utf-8"))
srcs = {v.get("source") for dep in d["dependencies"] for v in (dep.get("vulnerabilities") or [])}
print("vuln sources present:", sorted(x for x in srcs if x))     # -> ['NVD']  (no OSSINDEX)
'@ | python -

# corroborate from the HTML
(Select-String -Path "owasp-reports\visibility-lambda-after\visibility-s3-archiver\dependency-check-report.html" `
               -Pattern "OSSINDEX" -AllMatches).Matches.Count      # -> 0
```

**18 — Audit the dependency-check installs and their data directories** (§5.3 — “was copying the
12.2.2 data dir wrong?”). The `Where-Object` filter hides the ~170 two-hex-character cache
subdirectories so the interesting files are readable.
```powershell
foreach ($p in "dependency-check-12.2.1","dependency-check-12.2.2","dependency-check-13.0.0","dependency-check-current") {
  $d = "C:\dependency-check\$p\data"
  Write-Host "=== $p ==="
  if (Test-Path $d) {
    Get-ChildItem $d | Where-Object { $_.Name -notmatch '^[0-9a-f]{2}$' } |
      ForEach-Object { "   {0,-38} {1,10} {2}" -f $_.Name, $_.Length, $_.LastWriteTime }
  } else { "   (no data dir)" }
}
# also confirm what 'current' points at
(Get-Item "C:\dependency-check\dependency-check-current").Target    # -> dependency-check-13.0.0
```

**19 — Confirm the Jenkins scanner version and its OSS Index usage.** Proves the local/CI gap is a
*credentials* difference, not a version difference: both are 13.0.0, but only CI has OSSINDEX rows.
```powershell
@'
import re, glob
from pathlib import Path
for f in sorted(glob.glob(r"C:\Users\arijit.kundu\Downloads\Visibility*OWASP*.html")):
    c = Path(f).read_text(encoding="utf-8", errors="ignore")
    t = " ".join(re.sub(r"<[^>]+>", " ", c).split())
    v = sorted(set(re.findall(r"[Dd]ependency-?[Cc]heck\s*(?:version)?\s*:?\s*v?(\d+\.\d+\.\d+)", t)))
    print(f"{Path(f).name:52} versions={v[:3]}  OSSINDEX_hits={len(re.findall('OSSINDEX', c))}")
'@ | python -
```

**20 — Map every CVE in a Jenkins report to the jar it was reported against.** Used to attribute the
two out-of-scope HIGHs in §9. Anchors each CVE to the nearest preceding `*.jar` heading.
```powershell
@'
import re
from pathlib import Path
c = Path(r"C:\Users\arijit.kundu\Downloads\VisibilityS3Archiver-26.09.002-OWASP.html").read_text(encoding="utf-8", errors="ignore")
heads = [(m.start(), m.group(1)) for m in re.finditer(r'>([A-Za-z0-9_.\-]+\.jar)\s*<', c)]
res = {}
for m in re.finditer(r'(CVE-\d{4}-\d{4,7}|GHSA-[a-z0-9\-]+)', c):
    prev = [h for pos, h in heads if pos < m.start()]
    if prev: res.setdefault(prev[-1], []).append(m.group(1))
for jar in ("jsoup-1.17.2.jar", "jackson-databind-2.22.0.jar", "jna-jpms-5.14.0.jar"):
    ids = list(dict.fromkeys(res.get(jar, [])))
    print(f"{jar:32} -> {', '.join(ids)}")
'@ | python -
```

**21 — Establish the CI timeline for the integration-test question (§6.3).** The workspace directory
name in the CI report embeds a Unix timestamp; compare it with the merge commit date.
```powershell
# build timestamp baked into the Jenkins workspace path
@'
import re
from pathlib import Path
c = Path(r"C:\Users\arijit.kundu\Downloads\VisibilityS3Archiver-26.09.002-OWASP.html").read_text(encoding="utf-8", errors="ignore")
print(sorted(set(re.findall(r"VisibilityS3Archiver-26\.09\.002-(\d+)", c))))
'@ | python -                                             # -> 1788253326
[DateTimeOffset]::FromUnixTimeSeconds(1788253326).ToString("yyyy-MM-dd HH:mm:ss 'UTC'")
#   -> 2026-09-01 09:02:06 UTC

cd C:\Users\arijit.kundu\projects\mercury-services
git --no-pager log -1 --format="%h %ad %s" --date=iso 7573ea93aa   # PR #1226 merge
#   -> 7573ea93aa 2026-09-01 07:18:04 +0000 Pull request #1226: Feature/ION-16693 visibility owasp

# and show the property values on either side of the bump
git --no-pager show 08a0c83d41^:visibility/pom.xml | Select-String "log4j.version>"   # 2.23.1
git --no-pager show HEAD:visibility/pom.xml        | Select-String "log4j.version>"   # 2.25.5
```

**22 — Discover the OSS Index authentication options on the installed CLI (§5.2.1).** The `--help`
output is truncated; `--advancedHelp` lists every option. The property-file keys and the actual
enable/disable rule are not documented in the help at all, so they were read out of the jar:

```powershell
$bat = "C:\dependency-check\dependency-check-current\bin\dependency-check.bat"
& $bat --advancedHelp 2>&1 | Out-String | Out-File "$env:TEMP\dc-help.txt" -Encoding utf8
Get-Content "$env:TEMP\dc-help.txt" | Select-String "oss|Sonatype|propertyfile"
#   -> --ossIndexPassword <password>   Sonatype Guide personal access token or legacy API token
#   -> --ossIndexUsername <username>   (deprecated) only for legacy tokens
#   -> -P, --propertyfile <file>       A property file to load.

# the property keys accepted in that file - read out of the compiled constants
python -c @"
import zipfile,re
z=zipfile.ZipFile(r'C:\dependency-check\dependency-check-current\lib\dependency-check-core-13.0.0.jar')
keys=set()
for n in z.namelist():
    if n.endswith('.class'):
        for m in re.finditer(rb'analyzer\.ossindex\.[a-z.]+', z.read(n)):
            keys.add(m.group().decode())
for k in sorted(keys): print(k)
"@
#   -> analyzer.ossindex.password / .user / .url / .enabled / .cache.validforhours / ...

# and the shipped default URL (already migrated to Sonatype Guide on 13.0.0 - do not override)
python -c @"
import zipfile
z=zipfile.ZipFile(r'C:\dependency-check\dependency-check-current\lib\dependency-check-core-13.0.0.jar')
print([l for l in z.read('dependencycheck.properties').decode().splitlines() if 'ossindex' in l])
"@
#   -> ['analyzer.ossindex.enabled=true', 'analyzer.ossindex.url=https://api.guide.sonatype.com', ...]
```

**22a — Disassemble the credential gate.** Setting only a password still produced the "missing
credentials" WARN, so the condition had to be read directly:

```powershell
# extract the analyzer class and disassemble it
$core = "C:\dependency-check\dependency-check-current\lib\dependency-check-core-13.0.0.jar"
python -c @"
import zipfile
z=zipfile.ZipFile(r'$core')
[z.extract(n, r'$env:TEMP\dcoss') for n in z.namelist() if 'OssIndexAnalyzer' in n]
"@
javap -p -c "$env:TEMP\dcoss\org\owasp\dependencycheck\analyzer\OssIndexAnalyzer.class" |
  Out-File "$env:TEMP\ossidx.txt" -Encoding utf8

# prepareAnalyzer() -> disables unless password non-empty AND (user non-empty OR password
#                      startsWith "sonatype_pat_")
Get-Content "$env:TEMP\ossidx.txt" | Select-String "sonatype_pat_|missing credentials|setEnabled"
```

**22b — Empirically confirm the rule** with dummy values against a single jar (fast, no NVD update).
The message changing from *"disabled due to missing credentials"* to *"invalid credentials"* proves
the credential was accepted and the analyzer actually ran:

```powershell
$jar   = "$env:USERPROFILE\.m2\repository\net\java\dev\jna\jna-jpms\5.14.0\jna-jpms-5.14.0.jar"
$props = "$env:TEMP\dc-oss.properties"

# (a) no prefix, no user -> still disabled
"analyzer.ossindex.password=DUMMY_TOKEN" | Set-Content $props -Encoding ascii
& $bat --project oss-a --scan $jar --propertyfile $props --out "$env:TEMP\dc-a" --noupdate --format JSON 2>&1 |
  Select-String "OSS Index"
#   -> [WARN] ... disabled due to missing credentials

# (b) Sonatype Guide PAT prefix, no user -> ENABLED
"analyzer.ossindex.password=sonatype_pat_DUMMYVALUE" | Set-Content $props -Encoding ascii
& $bat --project oss-b --scan $jar --propertyfile $props --out "$env:TEMP\dc-b" --noupdate --format JSON 2>&1 |
  Select-String "OSS Index"
#   -> [ERROR] Sonatype OSS Index / Guide has invalid credentials, disabling the analyzer.  (exit 14)

# (c) legacy token: user + password -> ENABLED, with a migration deprecation warning
@"
analyzer.ossindex.user=someone@e2open.com
analyzer.ossindex.password=legacy_api_token_value
"@ | Set-Content $props -Encoding ascii
& $bat --project oss-c --scan $jar --propertyfile $props --out "$env:TEMP\dc-c" --noupdate --format JSON `
       --ossIndexRemoteErrorWarnOnly true 2>&1 | Select-String "OSS Index"
#   -> [WARN] ... not yet using a Sonatype Guide personal access token ... before December 31, 2026
#   -> exit 0, because --ossIndexRemoteErrorWarnOnly downgrades the failure

# putting the token on the command line instead of in the file is possible but DC objects:
& $bat --project oss-d --scan $jar --ossIndexPassword "sonatype_pat_X" --out "$env:TEMP\dc-d" --noupdate 2>&1 |
  Select-String "used on the command line"
#   -> [WARN] ossIndexPassword used on the command line, consider moving the password to a
#             properties file using the key `analyzer.ossindex.password`
```

---

## 9. The other two HIGHs — origin, and whether a fix exists

Out of scope for this branch (covered by the agreed two-week release exception), but recorded here so
the follow-up ticket does not have to redo the research.

### 9.1 Where they come from

```
visibility-s3-archiver
 \- visibility-commons
    +- com.inttra.mercury:commons:1.0.33-SNAPSHOT
    |   \- org.jsoup:jsoup:1.17.2                     <-- transitive, NOT declared in visibility
    \- com.fasterxml.jackson.core:jackson-databind:2.22.0
                                                      <-- declared in visibility-commons/pom.xml:51-54
                                                          as ${jackson.version}, set in visibility/pom.xml:36
```

| Jar | Declared where | Controlled by |
|---|---|---|
| `jackson-databind` 2.22.0 | `visibility/visibility-commons/pom.xml` | `<jackson.version>` in `visibility/pom.xml` — **we own this** |
| `jsoup` 1.17.2 | nowhere in visibility | transitive from `commons` — **owned by `mercury-services-commons`** |

That asymmetry matters: bumping jackson is a one-line change in `visibility/pom.xml`; bumping jsoup
requires either a change in `mercury-services-commons`, or a `dependencyManagement` pin in
`visibility/pom.xml` to override the transitive version.

### 9.2 The findings, and fix availability

Both HIGHs are CWE-770 (allocation without limits) with an identical CVSSv4 base score of **8.7**, and
both come from **OSS Index**, not NVD (§5.2).

| Jar | CVE | Sev | What it is | Fixed in |
|---|---|---|---|---|
| `jsoup` 1.17.2 | **CVE-2026-75140** | **HIGH** | `XmlTreeBuilder` copies the whole inherited namespace map on every start element → quadratic time/memory on deeply nested, uniquely-namespaced XML → `OutOfMemoryError`. Affects jsoup **through 1.23.2**; fix commit `862ba2f`, PR jhy/jsoup#2556 | **jsoup 1.23.3** |
| `jsoup` 1.17.2 | CVE-2026-71497 | MEDIUM | XSS | included in the same upgrade |
| `jackson-databind` 2.22.0 | **CVE-2026-68497** | **HIGH** | no `StreamReadConstraints` number-length limit on `XMLGregorianCalendar` / `Duration` deserialization; PR FasterXML/jackson-databind#6127 | confirmed in **3.1.6**; a 2.22.x backport is **not yet published** |
| `jackson-databind` 2.22.0 | CVE-2026-54515, CVE-2026-59889, CVE-2026-77310, CVE-2026-19032 | MEDIUM | various | **2.22.1** fixes 54515 / 59889 / 77310 |

### 9.3 Suggested follow-up when the exception expires

* **jsoup** — clean, low-risk win. Ask `mercury-services-commons` to move to **1.23.3**; if that is
  slow, pin it in `visibility/pom.xml` `<dependencyManagement>` in the same style as the Jetty /
  httpclient5 / guava pins added yesterday. This clears one of the two remaining HIGHs outright.
* **jackson-databind** — bumping `<jackson.version>` to **2.22.1** clears three MEDIUMs but,
  as of this writing, **not** the CVE-2026-68497 HIGH, which is only confirmed fixed on the 3.x line.
  Re-check the 2.22.x release notes before the exception lapses; if no backport has shipped, the
  exception will need to be renewed for that one CVE alone.
* Do the jsoup bump first — it is the one that actually reduces the HIGH count.

---

## 10. Files changed

| File | Change |
|---|---|
| `visibility/visibility-s3-archiver/pom.xml` | exclude `jetty-setuid-jna` (×3 deps); `log4j-core` → `${log4j.version}` |
| `visibility/visibility-pending-start/pom.xml` | exclude `jetty-setuid-jna` (×3 deps) |
| `visibility/visibility-outbound-poller/pom.xml` | exclude `jetty-setuid-jna` (×3 deps) |
| `visibility/visibility-error-email/pom.xml` | exclude `jetty-setuid-jna` (on `visibility-commons`) |

No production Java source changed; no other visibility module is affected.

---

## 11. Residual risk

| Risk | Assessment |
|---|---|
| A lambda needs `SetUIDListener` at runtime | None. It is only reachable via `AbstractServerFactory.buildServer(...)`, and the lambdas never build a Jetty `Server`. Proven by boot-testing all four handlers from their actual deployment ZIPs (§7.4) and by a constant-pool scan of ~220 jars per package (§7.5 / §8 command 13). |
| A future dependency reintroduces `jetty-setuid-jna` on a fourth path | The exclusion is applied to all three `com.inttra.mercury` compile dependencies in each lambda, covering every current path. A new path would reappear in CI as the same FP; re-run §8 command 6 if it does. |
| Other visibility modules regress | None. All seven still resolve `jetty-setuid-jna:2.0.3 → jna-jpms:5.14.0` unchanged (§7.1), and the full reactor builds and tests green (§7.3). |
| `jackson-databind` / `jsoup` HIGHs | Knowingly deferred under the agreed two-week release exception; both jars still ship unchanged. See §9 for origin and fix availability. |
| `VisibilityS3ArchiverIT` regresses again | Real. It is not run by the Jenkins job (`package sonar:sonar`, §6.3), so only a local `mvn -o clean verify` will catch it. Raising a ticket to add `verify` to CI is the durable fix. |
| Local OWASP scans give false assurance | Real. Without an OSS Index token, local DC 13.0.0 sees NVD findings only and silently misses ~1/3 of what CI reports (§5.2). Do not sign off a security fix on a local scan alone. |
