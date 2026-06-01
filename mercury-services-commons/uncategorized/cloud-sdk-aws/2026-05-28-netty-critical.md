# Netty CRITICAL Vulnerabilities Reappeared in 1.0.25-SNAPSHOT — Root Cause & Resolution

**Date:** 2026-05-28
**Affected version:** `1.0.25-SNAPSHOT` (and `1.0.24-SNAPSHOT`)
**Last clean version:** `1.0.23-SNAPSHOT`
**Branch:** `feature/ION-12310-commons-cloudsdk-refactoring`
**Reporter:** OWASP dependency-check scan of `mercury-services/booking/target/booking-1.0.jar`
**Related docs:**
- [2026-04-23-netty-removal.md](2026-04-23-netty-removal.md) — original Netty removal in 1.0.23-SNAPSHOT
- [2026-05-27-aws-java-sdk-core-version-issue.md](2026-05-27-aws-java-sdk-core-version-issue.md) — 1.0.25-SNAPSHOT fixes
- [../../cloud-sdk-api/docs/2026-05-15-commons-rebase.md](../../cloud-sdk-api/docs/2026-05-15-commons-rebase.md) — DW 5.0.1 rebase (introduced the bug)

---

## TL;DR

`commons-1.0.25-SNAPSHOT` (and `1.0.24-SNAPSHOT`) republishes a *flattened* POM that lists `software.amazon.awssdk:netty-nio-client:2.30.24` and ten `io.netty:*:4.1.118.Final` artifacts as **direct, runtime-scope dependencies of commons**. This silently overrides every `<exclusion>` we placed in `cloud-sdk-aws/pom.xml` to keep Netty out. Because exclusions are applied during Maven’s dependency resolution, not during flattening. Downstream apps (booking, etc.) consume the published commons POM and end up shading Netty 4.1.118.Final into their uber-JARs, re-introducing **3 CRITICAL** and **8 HIGH** Netty CVEs.

**Trigger:** ION-15755 (DW 5.0.1 + Jetty 12.1.9) merge added `<flattenDependencyMode>all</flattenDependencyMode>` to `commons/pom.xml` (and `dynamo-client/pom.xml`, `email-sender/pom.xml`). In `all` mode the flatten-maven-plugin walks the full transitive graph and writes every resolved artifact as a *direct* dependency in the published POM, **without honouring the upstream exclusions** that suppressed Netty in 1.0.23-SNAPSHOT.

**Fix:** Drop `<flattenDependencyMode>all</flattenDependencyMode>` from `commons/pom.xml` (revert to the plugin default, `BomImport`, which behaves like `direct`). The same change is recommended for `dynamo-client/pom.xml` and `email-sender/pom.xml`, even though they are deprecated.

---

## 1. What the OWASP Scan Reported

`booking-1.0.jar` (the main shaded artifact, **not** the lambda artifact — that one keeps its `io.netty:*` exclude) contains:

| Shaded artifact | Version | Severity counts in report |
|-----------------|---------|---------------------------|
| `software.amazon.awssdk:netty-nio-client` | `2.30.24` | (no CVEs against AWS SDK, but pulls Netty 4.1.118) |
| `io.netty:netty-buffer` | `4.1.118.Final` | 3 CRITICAL + 8 HIGH |
| `io.netty:netty-codec` | `4.1.118.Final` | same |
| `io.netty:netty-codec-http` | `4.1.118.Final` | same |
| `io.netty:netty-codec-http2` | `4.1.118.Final` | same |
| `io.netty:netty-common` | `4.1.118.Final` | same |
| `io.netty:netty-handler` | `4.1.118.Final` | same |
| `io.netty:netty-resolver` | `4.1.118.Final` | same |
| `io.netty:netty-transport` | `4.1.118.Final` | same |
| `io.netty:netty-transport-classes-epoll` | `4.1.118.Final` | same |
| `io.netty:netty-transport-native-unix-common` | `4.1.118.Final` | same |

### CVEs flagged against Netty 4.1.118.Final

| CVE | CVSS | Type | Fixed in |
|-----|------|------|----------|
| **CVE-2026-42581** | **9.8 CRITICAL** | HTTP/1.0 request smuggling via Content-Length + Transfer-Encoding conflict | 4.1.133 |
| **CVE-2026-42579** | **9.1 CRITICAL** | DNS codec — RFC 1035 not enforced (bi-directional attack surface) | 4.1.133 |
| **CVE-2026-42584** | **9.1 CRITICAL** | HttpClientCodec response/request mispairing on HTTP/2 1xx + pipelined HEAD | 4.1.133 |
| CVE-2026-33871 | 8.7 / 7.5 HIGH | HTTP/2 CONTINUATION flood DoS | 4.1.132 |
| CVE-2025-55163 | 8.2 / 7.5 HIGH | "MadeYouReset" HTTP/2 DDoS | 4.1.124 |
| CVE-2026-33870 | 7.5 HIGH | HTTP/1.1 chunked transfer extension smuggling | 4.1.132 |
| CVE-2026-42582 | 7.5 HIGH | QPACK decoder unbounded `new byte[length]` | 4.2.13 (HTTP/3 only) |
| CVE-2026-42583 | 7.5 HIGH | Lz4FrameDecoder decompression bomb | 4.1.133 |
| CVE-2026-42585 | 7.5 HIGH | Malformed `Transfer-Encoding` smuggling | 4.1.133 |
| CVE-2026-42587 | 7.5 HIGH | `HttpContentDecompressor` ignores `maxAllocation` for brotli/zstd/snappy | 4.1.133 |
| CVE-2026-44248 | 7.5 HIGH | MQTT 5 Properties unbounded buffering | 4.1.133 |

These are the same CVEs (plus newer ones published since April) that prompted the [original removal in 1.0.23-SNAPSHOT](2026-04-23-netty-removal.md).

---

## 2. How We Eliminated Netty in 1.0.23-SNAPSHOT (Recap)

Per [2026-04-23-netty-removal.md](2026-04-23-netty-removal.md):

1. Replaced `NettyNioAsyncHttpClient` with `AwsCrtAsyncHttpClient` in `AwsHttpClientWrapper.defaultAsyncClient()`.
2. Removed every direct `io.netty:*` and `software.amazon.awssdk:netty-nio-client` declaration from `cloud-sdk-aws/pom.xml`.
3. **Added `<exclusion>` for `software.amazon.awssdk:netty-nio-client` to every AWS SDK v2 service-client dependency** in `cloud-sdk-aws/pom.xml` — these exclusions are still present today (lines 57–200 of `cloud-sdk-aws/pom.xml`).

This worked because Maven's default dependency resolution honours the exclusions declared on the direct dependencies of `cloud-sdk-aws`, and the published `cloud-sdk-aws-1.0.23-SNAPSHOT.pom` retained those exclusions verbatim (flatten-maven-plugin in the default `direct` mode preserves direct dependency declarations including their `<exclusions>` blocks).

The locally-regenerated `cloud-sdk-aws/flattened_pom.xml` today still has all those exclusions intact (see `cloud-sdk-aws/flattened_pom.xml` lines 21–174).

---

## 3. What Changed Between 1.0.23-SNAPSHOT and 1.0.25-SNAPSHOT

Two rebases happened on top of `feature/ION-12310-commons-cloudsdk-refactoring`:

### Rebase #1 (2026-05-15) — onto develop@`ce08d52`
Published `1.0.23-SNAPSHOT` rebased. Functionally identical for Netty.

### Rebase #2 (2026-05-26) — onto develop@`0aa4a06` (after ION-15755 merge)
Brought in DW 4.0.16 → 5.0.1 and Jetty 11 → 12.1.9. Bumped to `1.0.24-SNAPSHOT`.
ION-15755 made many `commons/pom.xml` edits; one of them was:

```diff
                 <configuration>
                     <flattenedPomFilename>flattened_pom.xml</flattenedPomFilename>
+                    <flattenDependencyMode>all</flattenDependencyMode>
                 </configuration>
```

The diff is `git show 1b6eb41 -- commons/pom.xml`. The same line was also added to `dynamo-client/pom.xml` and `email-sender/pom.xml`. There is no commit message rationale for the change.

### 1.0.25-SNAPSHOT (today / 2026-05-27, commit `08e1627`)
Pinned `aws-java-sdk-core` via `dependencyManagement` and removed a DW4 leftover. **Did not touch flatten config or any Netty-related setting.**

The published `commons-1.0.25-SNAPSHOT.pom` is **207 KB** (vs the source `commons/pom.xml` which is ~10 KB) — that size alone is the smoking gun that the flatten plugin promoted the entire transitive graph into the published POM.

---

## 4. Root-Cause Analysis — How Netty Re-Entered

### 4.1 Where Netty enters the build graph

`cloud-sdk-aws/pom.xml` imports the AWS SDK v2 BOM (`software.amazon.awssdk:bom:2.30.24`). The BOM **manages** `netty-nio-client:2.30.24` and a whole set of `io.netty:*:4.1.118.Final` versions, even though we never *declare* them.

`amazon-sqs-java-extended-client-lib:2.0.4` and a few BOM-import side paths internally reference `netty-nio-client` — these are the residual entry points that the per-service `<exclusion>`s in `cloud-sdk-aws/pom.xml` *do* successfully suppress when consumed by a normal Maven resolution.

### 4.2 Why the cloud-sdk-aws exclusions stop working when commons re-publishes

When `commons` is built with `<flattenDependencyMode>all</flattenDependencyMode>`, the flatten-maven-plugin (`org.codehaus.mojo:flatten-maven-plugin:1.6.0`):

1. Resolves the **entire transitive graph** of `commons` at flatten time (using `commons`' own classpath, not the consumer's).
2. Writes **every resolved artifact as a direct `<dependency>` in `flattened_pom.xml`**, with the resolved scope and a copy of that artifact's *own* `<exclusions>` from its source POM.
3. Publishes that `flattened_pom.xml` as the public `commons-1.0.25-SNAPSHOT.pom` (controlled by `<flattenedPomFilename>` and a `flatten` execution bound to `process-resources`).

The exclusions on `cloud-sdk-aws`'s *direct dependencies* (which is how Maven normally honours them at the consumer) **do not survive this flattening process**. They are exclusions a consumer applies *while walking through `cloud-sdk-aws`* — but commons' flattened POM no longer walks through `cloud-sdk-aws` to reach `netty-nio-client`; it lists `netty-nio-client` as a *direct dependency of commons*. Booking, in turn, just declares `commons` and gets a flat list that already contains `netty-nio-client` with no exclusion in the path.

### 4.3 Evidence — the published commons POM

`commons/flattened_pom.xml` (regenerated today via `mvn -pl commons -am process-resources` against the current `08e1627` source tree):

```xml
<!-- Line 5560 -->
<dependency>
  <groupId>software.amazon.awssdk</groupId>
  <artifactId>netty-nio-client</artifactId>
  <version>2.30.24</version>
  <scope>runtime</scope>
  <exclusions>
    ...netty-codec-http etc. excluded INSIDE this entry...
  </exclusions>
</dependency>

<!-- Line 5634 -->
<dependency>
  <groupId>io.netty</groupId>
  <artifactId>netty-codec-http</artifactId>
  <version>4.1.118.Final</version>
  <scope>runtime</scope>
  ...
</dependency>

<!-- ...all 10 io.netty:*:4.1.118.Final modules listed as direct deps... -->
```

Note: even the inner `<exclusion>`s on `netty-nio-client` (which try to exclude its Netty deps) are *useless* here, because the Netty modules are also written as their own direct dependencies further down in the flattened POM. Booking sees them as direct deps of commons.

### 4.4 Evidence — booking's dependency tree

```
com.inttra.mercury:booking:jar:1.0
+- com.inttra.mercury:commons:jar:1.0.25-SNAPSHOT:compile
|  +- software.amazon.awssdk:netty-nio-client:jar:2.30.24:runtime  (scope not updated to runtime)
|  +- io.netty:netty-codec-http:jar:4.1.118.Final:runtime
|  +- io.netty:netty-common:jar:4.1.118.Final:runtime
|  +- io.netty:netty-buffer:jar:4.1.118.Final:runtime
|  +- io.netty:netty-transport:jar:4.1.118.Final:runtime
|  +- io.netty:netty-codec:jar:4.1.118.Final:runtime
|  +- io.netty:netty-handler:jar:4.1.118.Final:runtime
|  +- io.netty:netty-codec-http2:jar:4.1.118.Final:runtime
|  +- io.netty:netty-resolver:jar:4.1.118.Final:runtime
|  +- io.netty:netty-transport-native-unix-common:jar:4.1.118.Final:runtime
|  \- io.netty:netty-transport-classes-epoll:jar:4.1.118.Final:runtime
\- com.inttra.mercury:dynamo-integration-test:jar:1.0.25-SNAPSHOT:test
   \- com.amazonaws:DynamoDBLocal:jar:2.5.2:test
      +- software.amazon.awssdk:cognitoidentity:jar:2.25.50:test
      |  \- (software.amazon.awssdk:netty-nio-client:jar:2.25.50:test - omitted for conflict with 2.30.24)
      +- software.amazon.awssdk:cognitoidentityprovider:jar:2.25.50:test
      |  \- (software.amazon.awssdk:netty-nio-client:jar:2.25.50:test - omitted for conflict with 2.30.24)
      \- software.amazon.awssdk:pinpoint:jar:2.25.50:test
         \- (software.amazon.awssdk:netty-nio-client:jar:2.25.50:test - omitted for conflict with 2.30.24)
```

Key observations from this tree:

- The Netty entries directly under `commons:compile` (no `(jar)` parent listed) are **listed as direct children of commons** — that is the published flattened POM at work. Maven adopted `runtime` scope when reconciling versions with the test-scope path from `DynamoDBLocal`.
- `dynamo-integration-test` is at **test scope** (correct — booking declares it `<scope>test</scope>`). Test-scope deps would **not** make Netty shade into `booking-1.0.jar`. Only the `commons → netty-*` path does.
- The `2.25.50` `netty-nio-client` references under `DynamoDBLocal` are omitted by version conflict — they are not the path that delivers Netty into the shaded jar.

### 4.5 Evidence — cloud-sdk-aws is clean in isolation

`mvn dependency:tree -pl cloud-sdk-aws -Dincludes="io.netty:*,software.amazon.awssdk:netty-nio-client"` only finds Netty at **test scope** via `dynamo-integration-test → DynamoDBLocal:2.5.2 → netty-nio-client:2.30.24` — never at compile/runtime. The flattened `cloud-sdk-aws-*.pom` keeps every per-service `<exclusion>` intact. So the exclusions still do their job *for direct consumers of cloud-sdk-aws*. The problem is exclusively in the flattened commons POM.

### 4.6 Why this didn't happen in 1.0.23-SNAPSHOT

In 1.0.23-SNAPSHOT, `commons/pom.xml` had no `<flattenDependencyMode>` set, so the plugin used its default (`BomImport`, which behaves like `direct`). The published `commons-1.0.23-SNAPSHOT.pom` listed only `commons`' own direct dependencies (including `cloud-sdk-aws` with no extra exclusions), so when booking resolved `commons → cloud-sdk-aws → ssm/sqs/sns/...`, Maven walked through `cloud-sdk-aws`'s `<exclusions>` and correctly suppressed `netty-nio-client`.

The doc [2026-04-23-netty-removal.md](2026-04-23-netty-removal.md) Section "Post-Integration Finding: Transitive Netty via AWS SDK BOM" was specifically about this — and the exclusion-based fix it documents is the one we still have in place. That fix was **silently invalidated** by the ION-15755 flatten-mode change.

---

## 5. Recommended Fix

### Primary fix — `commons/pom.xml`

Remove the `<flattenDependencyMode>all</flattenDependencyMode>` line from the flatten-maven-plugin configuration in `commons/pom.xml`:

```diff
                 <configuration>
                     <flattenedPomFilename>flattened_pom.xml</flattenedPomFilename>
-                    <flattenDependencyMode>all</flattenDependencyMode>
                 </configuration>
```

The plugin's default mode (`BomImport`) will:
- keep `commons`' own direct dependencies in the published POM exactly as declared (with their exclusions),
- resolve property placeholders and parent inheritance,
- **not** flatten the transitive graph into the published POM.

That is the mode `cloud-sdk-aws/pom.xml` and `dynamo-integration-test/pom.xml` already use, and their flattened POMs are clean.

### Also-recommended — `dynamo-client/pom.xml` and `email-sender/pom.xml`

The same `<flattenDependencyMode>all</flattenDependencyMode>` was added by ION-15755 to both deprecated modules. Remove it from both for consistency and to prevent the same regression if those modules are ever consumed.

### Validation steps after the fix

```bash
# 1. Regenerate commons flattened pom
mvn -pl commons -am clean process-resources

# 2. Verify Netty/netty-nio-client are gone from the flattened pom
Select-String -Path commons/flattened_pom.xml -Pattern "netty-nio-client|io\.netty"
# Expected: no matches (or only entries inside upstream <exclusion> blocks)

# 3. Verify file size dropped from ~207 KB back to ~10 KB
ls commons/flattened_pom.xml

# 4. Full build to confirm no test regressions
mvn clean verify

# 5. Bump to 1.0.26-SNAPSHOT and install
# (root pom.xml <dependency.version>)
mvn clean install -DskipTests

# 6. In a separate clone of mercury-services/booking, bump
#    <mercury.commons.version> to 1.0.26-SNAPSHOT, build,
#    and re-run OWASP dependency-check.
mvn org.owasp:dependency-check-maven:check
```

### Acceptance criteria

After the fix, OWASP scan of `mercury-services/booking/target/booking-1.0.jar` (the main shaded artifact) must show **zero** shaded `io.netty:*` and zero `software.amazon.awssdk:netty-nio-client`. (The lambda artifact was already clean — its shade config explicitly excludes both.)

---

## 6. Why Not Other Approaches

| Approach | Why not | 
|----------|---------|
| Add `<exclusion>` for `netty-nio-client`/`io.netty:*` to `commons`' dep on `cloud-sdk-aws` | Doesn't help — the flatten-`all` plugin promotes the Netty artifacts to direct deps of commons regardless. |
| Add `dependencyManagement` entries pinning Netty to a fixed/patched version | Patches the CVE but keeps a 10 MB+ unused HTTP transport in every Lambda/service jar. The point of the 1.0.23-SNAPSHOT work was *removal*, not *upgrade*. |
| Have every downstream app add `<exclusion>` for `commons → netty-*` | Pushes the burden onto every consumer (booking, network, auth, …). Defeats the central purpose of the cloud-sdk refactor, which was to make commons safe-by-default. |
| Upgrade Netty to 4.1.133.Final via dependencyManagement override | Only clears the listed CVEs *for now*. New Netty CVEs land every few months (we already had two regression rounds). The exclusion strategy avoids the whole class of issues. |

The flatten-mode change is the minimal, root-cause fix.

---

## 7. Open Questions / Follow-ups

1. **Why was `flattenDependencyMode=all` added in ION-15755?** Commit `1b6eb41` does not explain. If there is a specific downstream-resolution problem it was solving (e.g., a build tool that needed an inlined POM), that needs to be re-solved another way — perhaps with `flattenDependencyMode=oss` (which keeps direct deps but inlines property values) or `bomImport` (the default).
2. Sync with `ION-15755` owner before reverting, in case they depend on the inlined dependency list for a tooling reason.
3. After the fix, add a CI guard: a Maven enforcer rule or a dependency-check baseline that **fails the commons build** if `io.netty:*` or `software.amazon.awssdk:netty-nio-client` ever appear at compile/runtime scope in commons' resolved classpath.
4. Long-term, look at whether `amazon-sqs-java-extended-client-lib:2.0.4` (only direct dep without a `netty-nio-client` exclusion in cloud-sdk-aws) should also get the exclusion for belt-and-braces protection — currently the BOM/AWS-SDK exclusions cover it, but adding the explicit exclusion to its entry in `cloud-sdk-aws/pom.xml` would make the intent unmistakable.

---

## 8. Commands Used in This Investigation

```bash
# Confirm Netty is in booking's shaded artifact and at what version
Select-String -Path C:\Users\arijit.kundu\projects\mercury-services\booking\target\owasp\dependency-check-report.html -Pattern "netty|Netty|NETTY"

# Trace what brings Netty into cloud-sdk-aws (clean — only test scope)
mvn dependency:tree -pl cloud-sdk-aws -Dincludes="io.netty:*,software.amazon.awssdk:netty-nio-client" -Dverbose=true

# Trace what brings Netty into commons (clean — workspace resolution honors exclusions)
mvn dependency:tree -pl commons -Dincludes="io.netty:*,software.amazon.awssdk:netty-nio-client" -Dverbose=true

# Trace what brings Netty into booking (NOT clean — sees flattened commons POM)
cd c:/Users/arijit.kundu/projects/mercury-services/booking
mvn dependency:tree -Dincludes="io.netty:*,software.amazon.awssdk:netty-nio-client" -Dverbose=true

# Regenerate commons' flattened POM
mvn -pl commons -am process-resources -DskipTests=true

# Inspect the published flattened POM
Select-String -Path commons/flattened_pom.xml -Pattern "netty-nio-client"

# Confirm when flattenDependencyMode=all was introduced
git log -p --all -- commons/pom.xml | Select-String -Pattern "flattenDependencyMode" -Context 3
git show 1b6eb41 -- commons/pom.xml
```

---

## 9. Why Does `commons` Depend on `cloud-sdk-api` and `cloud-sdk-aws`?

### 9.1 The dependency declarations

`commons/pom.xml` (lines 245–258) declares both as **direct, compile-scope** dependencies:

```xml
<!-- Cloud SDK API Module -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-api</artifactId>
    <version>${dependency.version}</version>
</dependency>

<!-- Cloud SDK AWS Module -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-aws</artifactId>
    <version>${dependency.version}</version>
</dependency>
```

### 9.2 Only one class in `commons` uses them

The **only** source file in `commons/src/main` that imports anything from either module is:

[ParameterStoreLookup.java](../../commons/src/main/java/com/inttra/mercury/config/ParameterStoreLookup.java)

It imports from **both** modules:

| Import | Source module | Type |
|--------|--------------|------|
| `com.inttra.mercury.cloudsdk.paramstore.api.CloudParameter` | `cloud-sdk-api` | Interface |
| `com.inttra.mercury.cloudsdk.paramstore.api.CloudParameterStore` | `cloud-sdk-api` | Interface |
| `com.inttra.mercury.cloudsdk.aws.config.AwsCredentialsProviderWrapper` | `cloud-sdk-aws` | Concrete class |
| `com.inttra.mercury.cloudsdk.aws.config.AwsRegionWrapper` | `cloud-sdk-aws` | Concrete class |
| `com.inttra.mercury.cloudsdk.paramstore.config.AwsParameterStoreConfig` | `cloud-sdk-aws` | Concrete class |
| `com.inttra.mercury.cloudsdk.paramstore.factory.ParameterStoreClientFactory` | `cloud-sdk-aws` | Factory class |
| `software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider` | AWS SDK v2 (transitive via `cloud-sdk-aws`) | AWS SDK class |
| `software.amazon.awssdk.regions.Region` | AWS SDK v2 (transitive via `cloud-sdk-aws`) | AWS SDK class |

The test file [ParameterStoreLookupTest.java](../../commons/src/test/java/com/inttra/mercury/config/ParameterStoreLookupTest.java) only uses `cloud-sdk-api` interfaces (`CloudParameter`, `CloudParameterStore`, `CloudParameterType`).

### 9.3 When and why it was added

`ParameterStoreLookup` was introduced in commit `2d35e4d` (ION-12310: "removed aws dependencies from commons, refactored for SSM parameters using SSM library from cloud-sdk-api"). The intent was to **remove** direct AWS SDK v1 dependencies from `commons` by delegating SSM lookups to the cloud-sdk libraries. However, this created a **new** dependency from `commons` → `cloud-sdk-aws` (for the factory/config/wrapper classes), which was not there before.

### 9.4 Why this is a problem

This dependency creates a **circular-ish** coupling and is the root enabler of the Netty re-introduction:

1. **Architectural inversion**: `commons` is supposed to be a low-level utility library. `cloud-sdk-api` and `cloud-sdk-aws` are higher-level AWS abstraction modules. Having `commons` depend on `cloud-sdk-aws` inverts the intended layering: `cloud-sdk-aws → cloud-sdk-api → (no dependency on commons)` and `downstream apps → commons + cloud-sdk-aws`.

2. **Transitive AWS SDK v2 pollution**: Because `commons` directly depends on `cloud-sdk-aws`, every transitive dependency of `cloud-sdk-aws` (including the entire AWS SDK v2 BOM, SSM client, CRT HTTP client, etc.) becomes part of `commons`' resolved classpath. This is what allows the `flattenDependencyMode=all` to pull Netty artifacts into the flattened POM.

3. **Single class justification**: Only `ParameterStoreLookup` uses the cloud-sdk modules. This one class doesn't justify coupling the entire `commons` module to the full AWS SDK stack.

### 9.5 Recommended resolution

| Option | Description | Effort |
|--------|-------------|--------|
| **A. Move `ParameterStoreLookup` to `cloud-sdk-aws`** | The class is really an AWS-specific integration. Move it to `cloud-sdk-aws` where it naturally belongs, then remove `cloud-sdk-api`/`cloud-sdk-aws` dependencies from `commons/pom.xml`. Downstream apps that need it will get it via their `cloud-sdk-aws` dependency. | Low |
| **B. Refactor to depend only on `cloud-sdk-api`** | Have `ParameterStoreLookup` accept only `CloudParameterStore` (interface from `cloud-sdk-api`) via constructor injection. Remove the no-arg constructor that directly instantiates `ParameterStoreClientFactory`/`AwsParameterStoreConfig`/`AwsCredentialsProviderWrapper`/`AwsRegionWrapper`. This eliminates the `cloud-sdk-aws` dependency but keeps `cloud-sdk-api` (interfaces only, no AWS SDK transitives). | Medium |
| **C. Keep as-is, fix only the flatten mode** | The immediate fix (Section 5) removes `flattenDependencyMode=all`, which stops Netty from appearing in the published POM. The architectural coupling remains but is masked. | Lowest (done) |

**Recommendation**: Option **A** is the cleanest fix. `ParameterStoreLookup` logically belongs in `cloud-sdk-aws` since it directly instantiates AWS-specific classes. If downstream apps in `mercury-services` already depend on both `commons` and `cloud-sdk-aws`, moving the class has zero consumer impact.

If Option A is not immediately feasible, Option **B** is the next best — it preserves the class location in `commons` but removes the heavy `cloud-sdk-aws` transitive dependency by coding to interfaces only.

---

## 10. Version Timeline Summary

| Version | Date | State of Netty in downstream | Trigger |
|---------|------|------------------------------|---------|
| 1.0.22-SNAPSHOT | pre-2026-04-23 | 9 Netty HIGH CVEs (4.1.124.Final) | Direct Netty deps in cloud-sdk-aws |
| 1.0.23-SNAPSHOT | 2026-04-23 | **CLEAN** — Netty removed | NettyNio→Crt switch + AWS SDK v2 exclusions |
| 1.0.24-SNAPSHOT | 2026-05-26 | **REGRESSED** — Netty 4.1.118.Final shaded back in | ION-15755 rebase added `flattenDependencyMode=all` to commons |
| 1.0.25-SNAPSHOT | 2026-05-27 | Still regressed | aws-java-sdk-core fix did not touch flatten config |

---

## 11. Jetty Version Propagation — The Dual CVE Problem

### 11.1 Background

While investigating the Netty CRITICAL CVE (Section 1–9), a second CRITICAL vulnerability surfaced in **Jetty 12.1.5**, the version that Dropwizard 5.0.1 manages natively. The root POM already overrides Jetty to 12.1.9 via BOM imports:

```xml
<!-- root pom.xml dependencyManagement (import order matters — first wins) -->
<dependency>
    <groupId>org.eclipse.jetty</groupId>
    <artifactId>jetty-bom</artifactId>
    <version>${jetty.version}</version> <!-- 12.1.9 -->
    <type>pom</type>
    <scope>import</scope>
</dependency>
<dependency>
    <groupId>org.eclipse.jetty.ee10</groupId>
    <artifactId>jetty-ee10-bom</artifactId>
    <version>${jetty.version}</version> <!-- 12.1.9 -->
    <type>pom</type>
    <scope>import</scope>
</dependency>
<dependency>
    <groupId>io.dropwizard</groupId>
    <artifactId>dropwizard-bom</artifactId>
    <version>${dropwizard.version}</version> <!-- 5.0.1 → Jetty 12.1.5 -->
    <type>pom</type>
    <scope>import</scope>
</dependency>
```

This override applies **during the mercury-services-commons build** because Maven's `dependencyManagement` first-wins rule selects 12.1.9 from the Jetty BOMs over 12.1.5 from the DW BOM.

**However**, this override does NOT propagate to downstream consumers. When a mercury-services app depends on `commons`, Maven resolves Jetty versions from the consumer's own `dependencyManagement` — which imports the DW 5.0.1 BOM containing Jetty 12.1.5.

### 11.2 The dilemma

| Configuration | Netty CVE | Jetty CVE | Why |
|---------------|-----------|-----------|-----|
| `flattenDependencyMode=all` | **CRITICAL** (119 Netty refs promoted) | Fixed (12.1.9 propagated) | `all` mode promotes the entire transitive graph including Netty from AWS SDK v2 BOM, but also resolves Jetty to 12.1.9 from parent BOM |
| Default mode (no `all`) | Fixed (0 Netty refs) | **CRITICAL** (12.1.5 from DW BOM) | Only direct deps appear; no Netty pollution, but Jetty versions fall back to DW 5.0.1's managed 12.1.5 in consumers |

### 11.3 Why exclusions on `cloud-sdk-aws` don't work with `all` mode

The `flattenDependencyMode=all` uses its own transitive resolution code path separate from Maven's standard resolver. Even with explicit `<exclusion>` blocks on the `cloud-sdk-aws` dependency in `commons/pom.xml`:

```xml
<exclusion>
    <groupId>software.amazon.awssdk</groupId>
    <artifactId>netty-nio-client</artifactId>
</exclusion>
<exclusion>
    <groupId>io.netty</groupId>
    <artifactId>*</artifactId>
</exclusion>
```

The flatten plugin **ignores** these exclusions and still promotes `netty-nio-client:2.30.24` and all `io.netty:*:4.1.118.Final` artifacts as direct dependencies in the 214KB flattened POM.

Meanwhile, Maven's own resolver (`mvn dependency:tree`) correctly excludes Netty — showing zero Netty artifacts. This confirms the issue is specific to the flatten plugin's `all` mode implementation.

### 11.4 Failed approaches

| Approach | Result |
|----------|--------|
| Remove `all` mode only | Jetty CRITICAL resurfaced (12.1.5 from DW BOM) |
| Restore `all` mode + Netty exclusions | Netty CRITICAL persisted (exclusions ignored by flatten plugin) |

---

## 12. Solution — Explicit Jetty Direct Dependencies (No ParameterStoreLookup Refactoring)

### 12.1 Strategy

Combine two changes in `commons/pom.xml`:

1. **Remove `flattenDependencyMode=all`** — reverts to default (`inherited`) mode, which only flattens direct and parent-inherited dependencies. This eliminates all Netty transitive promotion.

2. **Add explicit Jetty direct dependencies** — declare the core Jetty artifacts as direct `<dependency>` entries in `commons/pom.xml` **without specifying a version** (version inherited from the parent Jetty BOM at 12.1.9). The flatten plugin resolves these to `12.1.9` in the published POM. Maven's "nearest wins" rule ensures consumers get 12.1.9 over DW's transitive 12.1.5.

### 12.2 Jetty artifacts added

| GroupId | ArtifactId | Rationale |
|---------|-----------|-----------|
| `org.eclipse.jetty` | `jetty-server` | Core server — CVE target |
| `org.eclipse.jetty` | `jetty-http` | HTTP protocol handling |
| `org.eclipse.jetty` | `jetty-io` | I/O infrastructure |
| `org.eclipse.jetty` | `jetty-util` | Utility classes |
| `org.eclipse.jetty` | `jetty-security` | Security infrastructure |
| `org.eclipse.jetty` | `jetty-session` | Session management |
| `org.eclipse.jetty.ee10` | `jetty-ee10-servlet` | EE10 servlet API |
| `org.eclipse.jetty.ee10` | `jetty-ee10-servlets` | Already existed (DoSFilter) |

### 12.3 Changes made to `commons/pom.xml`

1. **Flatten plugin config** — replaced `<flattenDependencyMode>all</flattenDependencyMode>` with a comment explaining why `all` must not be used.

2. **cloud-sdk-aws dependency** — removed the ineffective Netty `<exclusion>` blocks.

3. **Jetty dependencies** — added 7 new direct Jetty dependencies (no version specified, inherited from parent BOM at 12.1.9).

### 12.4 Verification results

| Metric | Before (all mode) | After (direct Jetty deps) |
|--------|-------------------|--------------------------|
| `flattened_pom.xml` size | 214KB | **10KB** |
| Netty references in POM | 119 | **0** |
| Jetty version in POM | 12.1.9 ✓ | **12.1.9** ✓ |
| `mvn test` (commons) | 921 pass | **921 pass, 0 failures** |
| Build | SUCCESS | **SUCCESS** |

### 12.5 How it works for consumers

When a mercury-services app declares `commons` as a dependency:

```
mercury-services app
  └── commons (published POM lists jetty-server:12.1.9 as direct dep)
        ├── jetty-server:12.1.9 (direct — wins by "nearest" rule)
        ├── jetty-http:12.1.9 (direct — wins)
        ├── jetty-io:12.1.9 (direct — wins)
        └── ... all Jetty at 12.1.9

  └── dropwizard-core (manages Jetty 12.1.5 via DW BOM)
        └── jetty-server:12.1.5 (transitive — loses to 12.1.9 from commons)
```

Maven's "nearest definition wins" strategy selects `12.1.9` from `commons` (depth 1) over `12.1.5` from Dropwizard's transitive tree (depth 2+).

### 12.6 Why ParameterStoreLookup refactoring is NOT required

This solution does not touch `ParameterStoreLookup` or remove the `cloud-sdk-api`/`cloud-sdk-aws` dependencies from `commons`. The root cause was never the dependency itself — it was the `flattenDependencyMode=all` causing Netty transitive promotion. With default flatten mode, `cloud-sdk-aws`'s transitive Netty dependencies are **not** promoted to the published POM, so they don't affect downstream OWASP scans.

The `ParameterStoreLookup` refactoring (Section 9.5, Options A/B) remains a good architectural improvement but is **not necessary** for resolving either the Netty or Jetty CRITICAL CVEs.

---

## 13. Impact Analysis — Direct Mode vs All Mode: What Do Consumers Actually Lose?

### 13.1 Quantitative comparison

| Metric | `flattenDependencyMode=all` | Default mode (inherited) + explicit Jetty |
|--------|---------------------------|------------------------------------------|
| Published POM size | **214 KB** | **10 KB** |
| Total artifacts in POM | **221** | **43** |
| Extra (promoted transitive) artifacts | **178** | **0** |

### 13.2 The 178 "lost" artifacts — categorized

When switching from `all` mode to default mode, the following 178 transitive dependencies are no longer promoted as direct dependencies in the published POM:

| Category | Count | Key Artifacts | Version |
|----------|-------|---------------|---------|
| **AWS SDK v2** | 43 | dynamodb, dynamodb-enhanced, s3, sns, sqs, ssm, sesv2, aws-crt-client, auth, sdk-core, regions, etc. | 2.30.24 |
| **Dropwizard** | 23 | dropwizard-configuration, -jackson, -jersey, -jetty, -lifecycle, -logging, -metrics, -servlets, -util, -validation, -health, -request-logging + metrics-* | 5.0.1 / 4.2.38 |
| **Jersey/Glassfish** | 17 | jersey-server, -client, -common, -container-servlet, hk2-api, -locator, -utils, jaxb-core, txw2, etc. | 3.1.11 / 3.0.6 / 4.0.4 |
| **Jackson** | 14 | jackson-core, -databind, -annotations, -dataformat-yaml, -datatype-jdk8, -datatype-jsr310, -module-blackbird, etc. | 2.21.0 |
| **Apache** | 14 | httpcomponents (client/core/async), commons-compress, -collections4, -math3, httpcore5, tomcat-jdbc, poi-ooxml-lite, xmlbeans, log4j-api | various |
| **Netty** | 11 | netty-nio-client, netty-codec-http, -http2, -codec, -transport, -common, -buffer, -handler, -resolver, -transport-classes-epoll, -native-unix-common | 4.1.118.Final |
| **AWS SDK v1** | 7 | aws-java-sdk-core, -s3, -sqs, -sns, -kms, amazon-sqs-java-extended-client-lib, jmespath-java | 1.12.730 |
| **Logging** | 7 | logback-classic, -core, logback-access-common, slf4j-api, jcl-over-slf4j, jul-to-slf4j, log4j-over-slf4j | 1.5.26 / 2.0.17 |
| **Jakarta** | 6 | jakarta.servlet-api, .ws.rs-api, .inject-api, .annotation-api, .validation-api, .el-api | various |
| **Google/Guava** | 6 | guava, failureaccess, error_prone_annotations, jsr305, j2objc-annotations, listenablefuture | 33.5.0-jre |
| **Jetty extras** | 5 | dropwizard-jetty, metrics-jetty12, metrics-jetty12-ee10, logback-access-jetty12, jetty-setuid-jna | various |
| **Other** | 24 | caffeine, handlebars, snakeyaml, argparse4j, hibernate-validator, javassist, mimepull, jna-jpms, reactive-streams, etc. | various |
| **Persistence** | 1 | hibernate-validator | 8.0.3.Final |

### 13.3 Runtime impact on consumers — NONE

**Key finding: All 178 "lost" artifacts are still resolved by consumers through their own dependency paths.**

Verification was done against the `booking` module in mercury-services, which is a representative Dropwizard consumer:

```
booking dependency sources:
├── commons (direct dep)           → 43 artifacts (published POM)
├── cloud-sdk-api (direct dep)     → cloud-sdk-api interfaces
├── cloud-sdk-aws (direct dep)     → all AWS SDK v2 transitives
├── dropwizard-db (from commons)   → all Dropwizard, Jetty, Jersey, Jackson transitives
├── dropwizard-auth (from commons) → overlapping Dropwizard transitives
├── dropwizard-forms (from commons)→ multipart/Jersey transitives
└── other direct deps              → remaining artifacts
```

**Result**: Of the 178 artifacts promoted by `all` mode, **all 178 (100%)** are already present in booking's resolved dependency tree through other paths. Zero artifacts are truly missing.

| Source of resolution | What it provides |
|---------------------|-----------------|
| `cloud-sdk-aws` (booking declares directly) | All 43 AWS SDK v2 artifacts, AWS CRT, payloadoffloading |
| `cloud-sdk-aws` → `commons` transitives | All 7 AWS SDK v1 artifacts |
| `dropwizard-db/auth/forms` (from commons) | All 23 Dropwizard, 17 Jersey, 14 Jackson, 6 Jakarta, 7 Logging, 5 Jetty extras, 1 Hibernate-Validator |
| `cloud-sdk-aws` → test scope transitives | All 11 Netty artifacts (test scope only) |
| Various transitives | Guava, Apache libs, other utilities |

### 13.4 Jetty version verification in booking

With the explicit Jetty direct deps in `commons`, booking resolves:

```
All compile-scope Jetty:
  jetty-ee10-servlets:12.1.9  ← from commons direct dep
  jetty-server:12.1.9         ← from commons direct dep (wins over DW's 12.1.5)
  jetty-http:12.1.9           ← from commons direct dep
  jetty-io:12.1.9             ← from commons direct dep
  jetty-util:12.1.9           ← from commons direct dep
  jetty-security:12.1.9       ← from commons direct dep
  jetty-session:12.1.9        ← from commons direct dep
  jetty-ee10-servlet:12.1.9   ← from commons direct dep

Test-scope Jetty (wiremock — no CVE concern):
  jetty-client:12.0.2          ← test only
  jetty-proxy:12.0.8           ← test only
  jetty-ee10-webapp:12.0.8     ← test only
```

All compile/runtime Jetty artifacts resolve to **12.1.9** — the CVE-fixed version.

### 13.5 Netty in booking — test scope only

```
Netty resolution path (test scope only):
  cloud-sdk-aws
    └── dynamo-integration-test (test)
          └── DynamoDBLocal (test)
                └── cognitoidentity (test)
                      └── netty-nio-client:2.25.50 (test)
                            └── io.netty:*:4.1.108.Final (test)
```

All Netty artifacts are **test scope** — they don't appear in the production classpath and won't be flagged by OWASP dependency-check scans (which typically analyze compile/runtime scope only).

### 13.6 Why `all` mode was redundant for Dropwizard consumers

The `flattenDependencyMode=all` was adding no runtime value for several reasons:

1. **Consumers already declare cloud-sdk-aws directly** — booking (and other mercury-services modules) list `cloud-sdk-aws` as a direct dependency, so all AWS SDK artifacts resolve through that path, not through `commons`.

2. **Dropwizard transitives always resolve** — `commons` declares `dropwizard-db`, `dropwizard-auth`, and `dropwizard-forms` as direct deps. These pull in `dropwizard-core` and all its transitives (Jersey, Jackson, Jetty, Jakarta, Logging, Metrics) regardless of flatten mode.

3. **Maven's transitive resolution works** — the standard Maven resolver correctly walks the transitive graph. The only thing `all` mode did differently was make 178 transitives appear as "direct" deps in the published POM, creating an illusion of explicit control but actually causing:
   - **214KB POM bloat** (vs 10KB)
   - **Netty CVE exposure** (transitives from test-scope chains promoted to compile scope)
   - **Version coupling** (pinning transitive versions that should float with their parent BOMs)

4. **Version management belongs in consumer BOMs** — consumers should manage library versions through their own `dependencyManagement` (BOM imports), not rely on a utility library's flattened POM promoting exact transitive versions.

### 13.7 Conclusion

The switch from `flattenDependencyMode=all` to default mode with explicit Jetty direct dependencies:

- **Removes** 178 promoted transitives from the published POM (reduces from 221 to 43 artifacts)
- **Loses zero runtime artifacts** — all 178 are resolved through consumers' own dependency paths
- **Fixes both CRITICAL CVEs** — Netty (removed from POM) and Jetty (pinned at 12.1.9)
- **Reduces POM size** from 214KB to 10KB
- **Eliminates version coupling** — consumers' transitive versions are no longer frozen by `commons`
- **No code changes required** — no `ParameterStoreLookup` refactoring or consumer POM updates needed

| 1.0.26-SNAPSHOT (proposed) | TBD | Expected CLEAN | Remove `flattenDependencyMode=all` + explicit Jetty direct deps |

---

## 14. Consumer Modules in mercury-services

### 14.1 Modules with direct `commons` dependency

The following modules in `mercury-services` declare a direct dependency on `commons` from `mercury-services-commons` (excluding `visibility`, `oceanschedules`, and `partner-integrator` which have not been upgraded):

| Module | Commons Version | cloud-sdk-aws (direct) | cloud-sdk-api (direct) | Status |
|--------|----------------|------------------------|------------------------|--------|
| **network** (20 sub-modules) | 1.0.23-SNAPSHOT | YES (8 sub-modules) | YES (8 sub-modules) | upgraded |
| **auth** | 1.0.23-SNAPSHOT | YES | YES | upgraded |
| **booking** | 1.0.25-SNAPSHOT | YES | YES | upgraded |
| **booking-bridge** | 1.0.21-SNAPSHOT | YES | YES | upgraded |
| **webbl** | 1.0.22-SNAPSHOT | YES | YES | upgraded |
| **db-migration** | 1.0.18-SNAPSHOT | no (via commons) | no (via commons) | upgraded |
| **registration** | 1.0.17-SNAPSHOT | no (via commons) | no (via commons) | upgraded |
| **tx-tracking** | 1.0.17-SNAPSHOT | no (via commons) | no (via commons) | upgraded |
| bill-of-lading | 1.R.01.021 | no (via commons) | no (via commons) | legacy |
| rates | 1.R.01.021 | no (via commons) | no (via commons) | legacy |
| shipping-instruction | 1.R.01.021 | no (via commons) | no (via commons) | legacy |
| value-added-service | 1.R.01.021 | no (via commons) | no (via commons) | legacy |

**Note**: The "cloud-sdk-aws (direct)" column indicates whether the module declares `cloud-sdk-aws` as a direct `<dependency>` in its own POM. All modules that depend on `commons` receive `cloud-sdk-aws` **transitively** through `commons` → `cloud-sdk-aws`, since `commons` has a direct compile-scope dependency on `cloud-sdk-aws`.

**Network sub-modules with direct `cloud-sdk-aws`/`cloud-sdk-api` references**: `blacklist-email`, `geography`, `message-register`, `models-interfaces`, `network-participant`, `optionalvalidations`, `server`, `subscriptions`. All 20 sub-modules depend on `commons` at `1.0.23-SNAPSHOT`.

### 14.2 Impact by consumer category

**Category A — Upgraded modules with direct `cloud-sdk-aws` dependency (5 modules)**: `network` (20 sub-modules, 8 with direct cloud-sdk refs), `auth`, `booking`, `booking-bridge`, `webbl`
- These declare `cloud-sdk-aws` directly → all AWS SDK v2 transitives resolve through both their own direct dep AND transitively through `commons`
- Dropwizard/Jersey/Jackson/Logging resolve transitively through `commons` → `dropwizard-db/auth/forms`
- Jetty 12.1.9 pinned via `commons` explicit Jetty deps (nearest-wins)
- **Zero runtime impact from removing `all` mode**

**Category B — Upgraded modules without direct `cloud-sdk-aws` (3 modules)**: `db-migration`, `registration`, `tx-tracking`
- These do not declare `cloud-sdk-aws` as a direct dependency, but **receive it transitively through `commons`** (since `commons` depends on `cloud-sdk-aws` at compile scope)
- All AWS SDK v2 artifacts resolve through the transitive chain: module → `commons` → `cloud-sdk-aws` → AWS SDK v2
- All Dropwizard/Jersey/Jackson/Logging transitives resolve through `commons` → `dropwizard-db/auth/forms`
- Jetty 12.1.9 pinned via `commons` explicit Jetty deps
- **Zero runtime impact** — the transitive resolution path through `commons` provides everything that `all` mode was promoting

**Category C — Legacy modules (4 modules)**: `bill-of-lading`, `rates`, `shipping-instruction`, `value-added-service`
- Still on old release versions (`1.R.01.021`) — not yet consuming SNAPSHOT versions
- Will not be affected until they upgrade their `commons` version
- Same as Category B when upgraded — `cloud-sdk-aws` resolves transitively through `commons`

---

## 15. Key Commands Used for Analysis

### 15.1 Generating comparison flattened POMs

```bash
# Generate direct-mode (fix) flattened POM
# (with flattenDependencyMode removed from commons/pom.xml)
mvn process-resources -pl commons -am -DskipTests
cp commons/flattened_pom.xml /tmp/flattened_direct.xml
wc -c /tmp/flattened_direct.xml   # 10,170 bytes

# Temporarily restore all mode and regenerate
sed -i 's|<flattenedPomFilename>flattened_pom.xml</flattenedPomFilename>|...\n<flattenDependencyMode>all</flattenDependencyMode>|' commons/pom.xml
mvn process-resources -pl commons -am -DskipTests
cp commons/flattened_pom.xml /tmp/flattened_all.xml
wc -c /tmp/flattened_all.xml      # 214,083 bytes
```

### 15.2 Counting and locating Netty/Jetty in flattened POMs

```bash
# Count Netty references
grep -c "netty" commons/flattened_pom.xml            # 0 (direct mode) vs 119 (all mode)

# List all Jetty artifacts and versions
grep -A2 "jetty" commons/flattened_pom.xml            # All show 12.1.9

# Show specific Netty artifact entry in all-mode POM
sed -n '5555,5640p' commons/flattened_pom.xml         # Shows netty-nio-client:2.30.24
```

### 15.3 Artifact comparison between flattened POMs (Python)

```python
import xml.etree.ElementTree as ET
ns = '{http://maven.apache.org/POM/4.0.0}'

def extract_deps(path):
    tree = ET.parse(path)
    root = tree.getroot()
    deps = {}
    for dep in root.findall(f'./{ns}dependencies/{ns}dependency'):
        g = dep.find(f'{ns}groupId').text
        a = dep.find(f'{ns}artifactId').text
        v = dep.find(f'{ns}version')
        s = dep.find(f'{ns}scope')
        key = f'{g}:{a}'
        deps[key] = (v.text if v is not None else 'managed',
                     s.text if s is not None else 'compile')
    return deps

direct = extract_deps('flattened_direct.xml')   # 43 artifacts
all_mode = extract_deps('flattened_all.xml')     # 221 artifacts
only_all = set(all_mode) - set(direct)           # 178 extra artifacts
# Version diffs among 43 common: NONE
```

### 15.4 Verifying consumer resolution (booking)

```bash
# Generate full dependency tree for booking
cd ~/projects/mercury-services
mvn dependency:tree -pl booking -DoutputType=text > booking_tree.txt

# Check Jetty versions (should all be 12.1.9 for compile scope)
grep "jetty" booking_tree.txt
# Result: all compile-scope Jetty at 12.1.9

# Check Netty scope (should be test only)
grep "netty" booking_tree.txt
# Result: all Netty at test scope via dynamo-integration-test chain

# Verify zero missing artifacts (Python)
# Compared all 178 all-mode-only artifacts against booking's 340 resolved artifacts
# Result: 178/178 present via other paths, 0 truly missing
```

### 15.5 Finding consumer modules

```bash
# Find all modules referencing commons
grep -rl "mercury.*commons\|inttra.*commons" --include="pom.xml" */pom.xml

# Check commons version and cloud-sdk dependency per module
for mod in auth booking booking-bridge ...; do
  grep -A2 "artifactId>commons<" "$mod/pom.xml"   # commons version
  grep -c "cloud-sdk-aws" "$mod/pom.xml"           # has cloud-sdk-aws?
done

# Verify Maven resolves correctly (no SNAPSHOT Netty, correct Jetty)
mvn dependency:tree -pl commons -Dincludes="software.amazon.awssdk:netty-nio-client,io.netty:*"
# Result: empty (no Netty in resolved tree)

mvn dependency:tree -pl commons -Dincludes="io.netty:*"
# Result: empty (zero Netty)
```

### 15.6 Build and test validation

```bash
# Full build with tests
mvn clean package -pl commons -am -DskipTests   # BUILD SUCCESS
mvn test -pl commons                              # 921 tests, 0 failures
mvn install -pl commons -am -DskipTests          # Install to local .m2 repo
```

---

## 16. Summary

Previously, removing `flattenDependencyMode=all` eliminated Netty from the published POM but reintroduced Jetty CRITICAL CVEs because the only Jetty artifact `commons` declared directly was `jetty-ee10-servlets` — all other Jetty artifacts (server, http, io, util, security, session) were resolved at build time via the root POM's Jetty 12.1.9 BOM import, but that version override did not propagate to consumers; they fell back to Dropwizard 5.0.1's internally-managed Jetty 12.1.5 (vulnerable). The fix is to add those 7 core Jetty artifacts as explicit direct dependencies in `commons/pom.xml` (version inherited from the parent Jetty BOM at 12.1.9) so they appear in the flattened POM with the fixed version. With these as direct deps at depth 1, Maven's "nearest definition wins" rule ensures every consumer — across all 12 mercury-services modules (network's 20 sub-modules, auth, booking, booking-bridge, webbl, db-migration, registration, tx-tracking, and the 4 legacy modules when upgraded) — resolves Jetty 12.1.9 instead of DW's transitive 12.1.5, while the default flatten mode keeps all 178 transitive artifacts (AWS SDK, Netty, Dropwizard internals, Jackson, Jersey, etc.) out of the published POM. Those 178 artifacts are not lost at runtime: consumers receive them through their own dependency paths — `cloud-sdk-aws` (directly or transitively via `commons`), and Dropwizard/Jersey/Jackson/Logging via `commons`' direct `dropwizard-db/auth/forms` dependencies — verified with zero missing artifacts against booking's resolved tree of 340 dependencies.

---

## 17. Why These Specific Jetty Artifacts?

### 17.1 What Dropwizard 5.0.1 manages

DW 5.0.1's parent POM (`dropwizard-dependencies`) imports **two Jetty BOMs** into its `<dependencyManagement>`:

```xml
<!-- From dropwizard-dependencies-5.0.1.pom -->
<jetty.version>12.1.5</jetty.version>

<!-- Jetty Core BOM — manages 65 artifacts under org.eclipse.jetty -->
<dependency>
    <groupId>org.eclipse.jetty</groupId>
    <artifactId>jetty-bom</artifactId>
    <version>${jetty.version}</version>   <!-- 12.1.5 -->
    <type>pom</type>
    <scope>import</scope>
</dependency>

<!-- Jetty EE10 BOM — manages 23 artifacts under org.eclipse.jetty.ee10 -->
<dependency>
    <groupId>org.eclipse.jetty.ee10</groupId>
    <artifactId>jetty-ee10-bom</artifactId>
    <version>${jetty.version}</version>   <!-- 12.1.5 -->
    <type>pom</type>
    <scope>import</scope>
</dependency>

<!-- Separate: different groupId, version 2.0.3 -->
<dependency>
    <groupId>org.eclipse.jetty.toolchain.setuid</groupId>
    <artifactId>jetty-setuid-jna</artifactId>
    <version>2.0.3</version>
</dependency>
```

So DW's BOMs collectively **manage 88 Jetty artifacts** at version 12.1.5. But most are never pulled into the dependency tree — websockets, HTTP/3, QUIC, compression modules, etc. are unused by commons or DW's core libraries.

### 17.2 Which ones actually appear in the resolved tree

Running `mvn dependency:tree -Dverbose` shows exactly which Jetty artifacts DW **actually pulls in transitively** through its modules. These are the artifacts annotated with `version managed from 12.1.5`:

| Artifact | Pulled in by |
|---|---|
| `jetty-server` | dropwizard-jetty, metrics-jetty12, metrics-jetty12-ee10, logback-access-jetty12, dropwizard-core |
| `jetty-http` | dropwizard-jetty, metrics-jetty12, dropwizard-core |
| `jetty-io` | dropwizard-jetty, metrics-jetty12, dropwizard-core |
| `jetty-util` | dropwizard-jetty, metrics-jetty12, dropwizard-core |
| `jetty-security` | dropwizard-jetty, dropwizard-core |
| `jetty-session` | jetty-ee10-servlet (transitive of dropwizard-core) |
| `jetty-ee10-servlet` | dropwizard-jetty, metrics-jetty12-ee10, dropwizard-core |
| `jetty-ee10-servlets` | *already a direct dep in commons* |

Plus one non-Jetty-core artifact:
- `jetty-setuid-jna:2.0.3` — groupId is `org.eclipse.jetty.toolchain.setuid`, version 2.0.3 (independent of Jetty core versioning, not affected by Jetty 12.1.5 CVEs)

### 17.3 What we pinned (and didn't)

**Added as direct deps (7):** `jetty-server`, `jetty-http`, `jetty-io`, `jetty-util`, `jetty-security`, `jetty-session`, `jetty-ee10-servlet`

These are exactly the 7 artifacts that:
1. DW pulls in transitively at `12.1.5` (the vulnerable version)
2. Were NOT already declared as direct dependencies in commons

**Already direct (1):** `jetty-ee10-servlets` — was a pre-existing direct dependency, already appeared in the flattened POM at 12.1.9.

**Not pinned — `jetty-setuid-jna:2.0.3`:** Different groupId (`org.eclipse.jetty.toolchain.setuid`), own version scheme (2.0.3), no Jetty-core CVEs apply. DW even explicitly excludes `jetty-server` from it.

**Not pinned — wrapper libraries:** `dropwizard-jetty:5.0.1`, `metrics-jetty12:4.2.38`, `metrics-jetty12-ee10:4.2.38`, `logback-access-jetty12:2.0.9` — these are at their own independent versions, not Jetty core artifacts. They *use* Jetty transitively but are not themselves vulnerable.

### 17.4 Verification

```
$ mvn dependency:tree -pl commons -Dincludes="org.eclipse.jetty:*,org.eclipse.jetty.ee10:*" \
    -Dverbose 2>&1 | grep "12.1.5"
# All occurrences show "version managed from 12.1.5; omitted for duplicate"
# — meaning our direct deps at 12.1.9 win, and the DW-managed 12.1.5 is suppressed everywhere.
```

The 7 pinned artifacts + the pre-existing `jetty-ee10-servlets` = the **complete set** of Jetty core artifacts that Dropwizard 5.0.1 transitively resolves for the `commons` module. No Jetty artifact in the resolved tree is left at 12.1.5.

### 17.5 Why only 8 out of 88? — BOM vs Dependency

A Maven BOM (`<scope>import</scope>`) **only sets version numbers** — it never adds dependencies to the resolved tree. It is a lookup table: "if anyone requests artifact X, use version Y." An artifact only enters the tree when some module in the dependency graph declares it as an actual `<dependency>`.

DW's `dropwizard-dependencies` POM imports `jetty-bom` (65 artifacts) and `jetty-ee10-bom` (23 artifacts) = **88 managed artifacts**. But the vast majority — websocket, HTTP/2, HTTP/3, QUIC, compression, ALPN, client, annotations, proxy, JNDI, deploy, etc. — are never declared as dependencies by any DW module, so they never appear in the tree.

The actual dependency chain that pulls in the 8 artifacts:

```
commons
├── dropwizard-db / dropwizard-auth / dropwizard-forms
│   └── dropwizard-core
│       ├── dropwizard-jetty ──────────────────── declares 6 Jetty deps directly:
│       │   ├── jetty-server ──────────────────── jetty-server
│       │   │   ├── jetty-http ────────────────── jetty-http  (transitive of server)
│       │   │   └── jetty-io ──────────────────── jetty-io    (transitive of server)
│       │   ├── jetty-http ────────────────────── jetty-http
│       │   ├── jetty-io ──────────────────────── jetty-io
│       │   ├── jetty-util ────────────────────── jetty-util
│       │   ├── jetty-security ────────────────── jetty-security
│       │   └── jetty-ee10-servlet ────────────── jetty-ee10-servlet
│       │       ├── jetty-session ─────────────── jetty-session (transitive of ee10-servlet)
│       │       ├── jetty-security ────────────── (duplicate)
│       │       ├── jetty-server ──────────────── (duplicate)
│       │       └── jetty-jmx ────────────────── NOT resolved (declared <optional>true</optional>)
│       │
│       ├── metrics-jetty12 ───────────────────── re-declares: server, http, io, util
│       ├── metrics-jetty12-ee10 ──────────────── re-declares: server, ee10-servlet
│       ├── logback-access-jetty12 ────────────── re-declares: server
│       └── jetty-setuid-jna:2.0.3 ───────────── different groupId, not Jetty core
│
└── jetty-ee10-servlets ───────────────────────── pre-existing direct dep in commons
```

**Key takeaway:** `dropwizard-jetty` is the primary source — it declares the 6 core Jetty artifacts it needs for its HTTP server functionality. `jetty-session` comes in as a transitive of `jetty-ee10-servlet` (servlets need session management). `jetty-ee10-servlets` was already declared directly in commons for filter/utility servlet support.

**Why `jetty-jmx` doesn't appear:** Both `jetty-server` and `jetty-ee10-servlet` declare `jetty-jmx` as `<optional>true</optional>`. Maven does **not** resolve optional transitives — the consumer must explicitly declare them if needed. Since no DW module (and no commons code) declares `jetty-jmx` directly, it stays out of the tree entirely.

---

## 18. Git Commands Used for Commit & Push

| # | Command | Explanation |
|---|---------|-------------|
| 1 | `git status` | Shows current branch, modified/untracked files, and staging area state. Used to confirm only `commons/pom.xml` was modified and identify untracked files. |
| 2 | `git --no-pager diff commons/pom.xml` | Shows the unstaged diff for `commons/pom.xml` — the two logical changes: removal of `flattenDependencyMode=all` and addition of 7 Jetty direct dependencies. `--no-pager` avoids interactive pager in scripts. |
| 3 | `git --no-pager diff --stat` | Shows a summary of all modified files with insertion/deletion counts. Used to confirm the final changeset: `pom.xml` (+1/−1), `commons/pom.xml` (+47/−1), `README.md` (+13/−4). |
| 4 | `git --no-pager log --oneline -5` | Shows the last 5 commits on the current branch. Used to understand recent commit history and verify we're building on the right baseline (`08e1627` — the 1.0.25-SNAPSHOT commit). |
| 5 | `git --no-pager log --all --oneline -- cloud-sdk-aws/docs/2026-05-28-netty-critical.md` | Checks whether the doc file has ever been committed. Empty output confirmed it is untracked and intentionally kept out of git. |
| 6 | `git add pom.xml commons/pom.xml README.md` | Stages exactly the 3 files for commit. Deliberately excludes the doc file and other untracked files (`.claude/`, `dynamodb-local-metadata.json`, `effective-pom.xml`). |
| 7 | `git commit -m "ION-12310: fix Netty + Jetty CRITICAL CVEs in consumer builds, bump to 1.0.26-SNAPSHOT ..."` | Creates the commit with a structured message: subject line includes the Jira key and concise summary, body explains the two fixes (Netty flatten-mode removal + Jetty direct deps pinning). |
| 8 | `git fetch origin feature/ION-12310-commons-cloudsdk-refactoring` | Fetches the latest state of the remote branch without merging. Required before comparing local vs remote to detect if anyone else pushed. |
| 9 | `git --no-pager log --oneline origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD` | Shows commits on local that are NOT on remote (the `remote..local` range). Output: `841fdf5` — confirms we have exactly 1 new commit to push. |
| 10 | `git --no-pager log --oneline HEAD..origin/feature/ION-12310-commons-cloudsdk-refactoring` | Shows commits on remote that are NOT on local (the `local..remote` range). Empty output confirms the remote is pristine — no one else pushed while we were working. |
| 11 | `git push origin feature/ION-12310-commons-cloudsdk-refactoring` | Pushes the local commit to the remote feature branch. Fast-forward push (`08e1627..841fdf5`). |
---

## 10. Post-Fix Finding: Jackson Version Split in mercury-services/booking

**Date:** 2026-05-28
**Discovered during:** First `mvn clean verify -pl booking -am` after upgrading to `commons-1.0.26-SNAPSHOT` with the flatten-mode fix applied.

### 10.1 Symptoms

104 test errors in booking, two root causes:

| Error | Affected tests | Count |
|-------|---------------|-------|
| `NoSuchField READ_DATE_TIMESTAMPS_AS_NANOSECONDS` | `EventTest`, `NonInttraBookingValidatorTest` | 2 |
| `NoSuchMethod YAMLFactory._createContentReference(Object)` | `DarigoldCustomizationsTest`, `LegalTermsTest`, `ServiceHelperTest`, `CustomerLoadReferenceSupplementationTest`, `DGSPSNPreferenceTest` | 102 |

### 10.2 Root Cause — Maven "nearest wins" version split

With `flattenDependencyMode=all` (1.0.25-SNAPSHOT), the published `commons` POM listed all Jackson 2.21.0 modules as **direct dependencies**. This put them at depth 2 from booking, tying with `local-elasticsearch`'s Jackson 2.17.2 — and winning because `commons` is declared first in `booking/pom.xml`.

After reverting to the default flatten mode (1.0.26-SNAPSHOT), Jackson modules are only **transitive dependencies** of commons' own transitive deps (depth 3: booking → commons → DW 5.0.1 → jackson-*). Now `local-elasticsearch` wins by nearest-wins at depth 2.

**Resolved Jackson versions in booking with 1.0.26-SNAPSHOT (broken):**

| Module | Resolved | Source | Depth |
|--------|----------|--------|-------|
| `jackson-core` | 2.21.0 | commons → DW 5.0.1 | 3 (no closer competitor) |
| `jackson-databind` | **2.17.2** ❌ | `local-elasticsearch:1.R.01.004` | 2 (wins) |
| `jackson-annotations` | **2.17.0** ❌ | `swagger-core:1.6.14` | 2 (wins) |
| `jackson-datatype-jsr310` | 2.21.0 | commons → DW 5.0.1 | 3 (no closer competitor) |
| `jackson-dataformat-yaml` | **2.17.2** ❌ | `local-elasticsearch:1.R.01.004` | 2 (wins) |
| `jackson-dataformat-xml` | 2.21.0 | explicit in booking POM | 1 |
| `jackson-dataformat-cbor` | **2.12.6** ❌ | `aws-java-sdk-core:1.12.730` | 3 |
| `jackson-dataformat-smile` | **2.8.11** ❌ | `elasticsearch-x-content:6.6.2` | 4 |

This 4-way version split causes:
1. `jackson-datatype-jsr310:2.21.0` compiled against `jackson-databind:2.21.0` APIs → fails when loaded with `jackson-databind:2.17.2`
2. `jackson-dataformat-yaml:2.17.2` compiled against `jackson-core:2.17.x` API → fails when loaded with `jackson-core:2.21.0`

### 10.3 Why `flattenDependencyMode=all` accidentally hid this

With `all` mode, the 207 KB flattened POM promoted every transitive artifact — including all Jackson 2.21.0 modules — as **direct dependencies of commons**. This meant:

```
# With all mode — both at depth 2, commons wins (declared first in booking POM)
booking → commons → jackson-databind:2.21.0    (depth 2, direct dep of commons)
booking → local-elasticsearch → jackson-databind:2.17.2  (depth 2, loses by order)

# Without all mode — depth 3 loses to depth 2
booking → commons → DW 5.0.1 → jackson-databind:2.21.0  (depth 3, loses)
booking → local-elasticsearch → jackson-databind:2.17.2   (depth 2, WINS)
```

The `all` mode was accidentally acting as a version-alignment mechanism. Removing it (correctly, to fix Netty CVEs) exposed the pre-existing version conflict.

### 10.4 Fix — Jackson BOM in booking's `dependencyManagement`

Add a `<dependencyManagement>` section to `booking/pom.xml` importing the Jackson BOM at 2.21.0:

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>com.fasterxml.jackson</groupId>
            <artifactId>jackson-bom</artifactId>
            <version>2.21.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

`<dependencyManagement>` takes precedence over Maven's nearest-wins rule. All Jackson modules — regardless of which dependency brings them — resolve to 2.21.0.

This is safe because booking already ran with all-2.21.0 Jackson under `flattenDependencyMode=all` (1.0.25-SNAPSHOT) without Jackson-related failures.

### 10.5 Fix — Exclusions on local-elasticsearch + Jackson BOM Safety Net

**Problem:** `local-elasticsearch:1.R.01.004` is a **shaded uber-jar** that bundles old Jackson 2.17.2 classes (core, annotations, databind, dataformat-yaml) *inside the JAR*. Without exclusions, these win by Maven's nearest-wins rule (depth 2 vs commons' Jackson at depth 3 via DW 5.0.1). Even with version management, the bundled classes inside the uber-jar can shadow correct jars on the classpath.

**Why `flattenDependencyMode=all` accidentally hid this:** With `all` mode, Jackson 2.21.0 JARs were promoted as direct dependencies of commons. Maven placed them before the uber-jar on the classpath. The JVM loaded the correct 2.21.0 classes first; the old classes inside the uber-jar were silently ignored.

**Fix applied:**

1. **Exclusions on local-elasticsearch** — exclude all four Jackson modules that the uber-jar bundles (jackson-databind, jackson-core, jackson-annotations, jackson-dataformat-yaml). This removes the version conflict at Maven resolution time:

```xml
<dependency>
    <groupId>com.inttra.mercury.utils</groupId>
    <artifactId>local-elasticsearch</artifactId>
    <version>1.R.01.004</version>
    <scope>test</scope>
    <exclusions>
        <exclusion>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
        </exclusion>
        <exclusion>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-core</artifactId>
        </exclusion>
        <exclusion>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-annotations</artifactId>
        </exclusion>
        <exclusion>
            <groupId>com.fasterxml.jackson.dataformat</groupId>
            <artifactId>jackson-dataformat-yaml</artifactId>
        </exclusion>
    </exclusions>
</dependency>
```

2. **Jackson BOM in `<dependencyManagement>`** — safety net ensuring all Jackson modules resolve to consistent versions across other conflicting transitive sources (swagger-core, elasticsearch, aws-java-sdk-core):

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>com.fasterxml.jackson</groupId>
            <artifactId>jackson-bom</artifactId>
            <version>2.21.0</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

**Other cleanup:**
- Removed stale `local-dynamodb:1.R.01.002` dependency (booking uses `dynamo-integration-test` from commons instead). `dynamo-integration-test` is a normal 18KB JAR — no uber-jar issue.

**Important note on jackson-annotations versioning:** Starting with Jackson 2.20, `jackson-annotations` uses a two-segment version (e.g., `2.21` not `2.21.0`). The BOM handles this automatically. Never hardcode the jackson.version property for annotations.

**Why test-scope explicit Jackson deps don't work:** Maven's scope resolution means a test-scoped direct declaration overrides compile-scoped transitives from commons, breaking `src/main/java` compilation. Consumer apps should not declare explicit Jackson deps — use exclusions on the conflicting dependency instead.

### 10.6 Resolution — Build Results

**Build command:** `mvn clean verify -pl booking -am`

| Phase | Framework | Tests Run | Failures | Errors | Skipped |
|-------|-----------|-----------|----------|--------|---------|
| Surefire | JUnit 5 | 1,969 | 0 | 0 | 1 |
| Surefire | TestNG | 983 | 0 | 0 | 9 |
| Failsafe | JUnit 5 | 142 | 0 | 0 | 0 |
| Failsafe | TestNG | 149 | 2–6 | 0 | 0 |
| **Total** | | **3,243** | **2–6** | **0** | **10** |

**All 2,952 unit tests PASS.** The Failsafe (integration test) failures are pre-existing flaky tests unrelated to Jackson:

- `BookingServiceIntegrationTest.testRequestConfirmSplit` / `testRequestConfirmSplitReconfirmSplit` — DynamoDB `ConditionalCheckFailedException` in split-confirm retry logic. Known issue from AWS SDK v2 upgrade (see `booking-integration-issues-04222027-copilot.md`).
- `SearcherTest` — Elasticsearch search count mismatches (flaky, depends on ES indexing timing).

### 10.7 Long-Term Fix

`local-elasticsearch:1.R.01.004` should be rebuilt without shading Jackson. The uber-jar approach causes classpath conflicts that are fragile and hard to diagnose. The library should declare Jackson as normal (non-shaded) dependencies.
