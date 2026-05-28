# aws-java-sdk-core Version Conflict Fix

**Date:** 2026-05-27  
**Version:** 1.0.25-SNAPSHOT  
**Modules affected:** commons, cloud-sdk-aws, root pom.xml

## Problem

Client applications in mercury-services using mercury-services-commons were getting `aws-java-sdk-core:1.10.19` (from 2015) instead of the expected 1.12.x versions. This caused runtime failures due to missing classes and incompatible APIs in the ancient SDK version.

### Dependency tree showing the conflict

```
+- com.inttra.mercury:commons:jar:1.0.24-SNAPSHOT:compile
|  \- com.amazonaws:aws-java-sdk-core:jar:1.10.19:compile (scope not updated to compile)
+- com.inttra.mercury:integration-test-commons:jar:1.0:test
|  |  \- (com.amazonaws:aws-java-sdk-core:jar:1.12.721:test - omitted for conflict with 1.10.19)
|  \- (com.amazonaws:aws-java-sdk-core:jar:1.12.638:test - omitted for conflict with 1.10.19)
+- com.inttra.mercury:cloud-sdk-aws:jar:1.0.24-SNAPSHOT:compile
|  \- (com.amazonaws:aws-java-sdk-core:jar:1.12.730:compile - omitted for conflict with 1.10.19)
```

### Root cause

The `commons` module depends on `vc.inreach.aws:aws-signing-request-interceptor:0.0.22`, which is used for AWS request signing with the Jest Elasticsearch client. This library transitively pulls in `com.amazonaws:aws-java-sdk-core:1.10.19`.

Maven's "nearest definition wins" resolution strategy selects this version because `commons` appears first in the dependency order of client applications, and there was no `dependencyManagement` entry for `aws-java-sdk-core` in the root POM to override it.

The newer versions from `cloud-sdk-aws` (1.12.730) and other modules were all omitted in favor of this ancient 1.10.19.

## Solution

### Changes made

1. **Root pom.xml** — Added `aws-java-sdk-core` to `<dependencyManagement>` with version `${aws.java.sdk.version}` and a `jackson-databind` exclusion to prevent pulling in an older Jackson version that conflicts with the Dropwizard-managed version.

2. **Root pom.xml** — Updated `aws.java.sdk.version` property from `1.12.638` to `1.12.730` to match the latest version used in cloud-sdk-aws.

3. **Root pom.xml** — Updated `dependency.version` from `1.0.24-SNAPSHOT` to `1.0.25-SNAPSHOT`.

4. **cloud-sdk-aws/pom.xml** — Removed hardcoded `aws-java-sdk-core` version; now inherits from root `dependencyManagement`.

5. **dynamo-client and email-sender** — Left unchanged with hardcoded version `1.12.638` (both are deprecated modules).

### Root pom.xml dependencyManagement entry

```xml
<!-- AWS SDK v1 (legacy) — pulled transitively by aws-signing-request-interceptor
     (used by Jest/Elasticsearch in commons) and by cloud-sdk-aws for SNS/SQS modules.
     TODO: Remove once Jest Client is replaced with OpenSearch SDK and all modules
     have fully migrated to AWS SDK v2 (software.amazon.awssdk). -->
<dependency>
  <groupId>com.amazonaws</groupId>
  <artifactId>aws-java-sdk-core</artifactId>
  <version>${aws.java.sdk.version}</version>
  <exclusions>
    <exclusion>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
    </exclusion>
  </exclusions>
</dependency>
```

### Why jackson-databind is excluded

`aws-java-sdk-core:1.12.730` depends on `jackson-databind:2.12.x` which conflicts with the `jackson-databind:2.21.0` version managed by Dropwizard 5.0.1. The exclusion ensures the Dropwizard-managed Jackson version is used consistently.

## Final state — dependency tree

```
Module                   aws-java-sdk-core version   Source
---------------------------------------------------------------------
cloud-sdk-api            1.12.730                     dependencyManagement
dynamo-integration-test  1.12.730                     dependencyManagement
cloud-sdk-aws            1.12.730                     dependencyManagement
commons                  1.12.730                     dependencyManagement (overrides 1.10.19)
local-dynamodb           1.12.730                     dependencyManagement
dynamo-client            1.12.638                     hardcoded (deprecated module)
email-sender             1.12.638                     hardcoded (deprecated module)
```

## Impact on client applications

Client applications in mercury-services that depend on `commons` and `cloud-sdk-aws` will now consistently get `aws-java-sdk-core:1.12.730`. The `dependencyManagement` in this root POM takes precedence over transitive versions, so the 1.10.19 from `aws-signing-request-interceptor` is overridden.

## Dropwizard 4.x Remnants Scan (2026-05-27)

After upgrading to DW 5.0.1 and Jetty 12.1.9 (see `cloud-sdk-api/docs/2026-05-15-commons-rebase.md`), a full scan was performed to identify any remaining Dropwizard 4.x era artifacts.

### Finding 1 — Hardcoded `dropwizard-core:4.0.10` in cloud-sdk-aws

**File:** `cloud-sdk-aws/pom.xml`, line 216–220  
**Status:** ✅ **DONE** — removed in commit `08e1627`

`cloud-sdk-aws/pom.xml` had **two** `dropwizard-core` declarations:
- Line 216: hardcoded `4.0.10` (DW4 leftover)
- Line 257: version-less, inheriting `5.0.1` from root `dependencyManagement`

Maven resolves duplicate deps by using the first occurrence, so the build was silently pulling DW 4.0.10 instead of 5.0.1. The hardcoded entry was removed; the version-less declaration at line 257 now correctly inherits `5.0.1`.

### Finding 2 — Stale `effective-pom.xml`

**File:** `cloud-sdk-aws/effective-pom.xml`  
**Status:** ✅ Safe to delete — untracked generated file

This file was generated by the Maven Help Plugin during a prior investigation and shows `dropwizard.version=4.0.16` and `dependency.version=1.0.22-SNAPSHOT`. It is NOT a source file; it is not committed, not in `.gitignore`, and has no effect on the build.

### Finding 3 — Stale comment referencing DW 4.0.10

**File:** `pom.xml`, line 194  
**Status:** ✅ **DONE** — fixed in commit `08e1627`

```xml
<!-- OLD --> Dropwizard 4.0.10 uses Jackson 2.x, so we need to add this dependency for now
<!-- NEW --> Dropwizard 5.0.1 uses Jackson 2.21.0; this dependency is still needed until Jackson 3.0
```

### Finding 4 — `javax.xml.bind` (JAXB) dependencies — REDUNDANT

**Files:** `pom.xml` (dependencyManagement, lines 136–150), `commons/pom.xml` (dependencies, lines 216–227)  
**Status:** ✅ Safe to remove — zero Java code uses these

**Evidence:**
- `grep` for `import javax.xml.bind` across all `*.java` files: **0 matches**
- The original comment says "Removed from java11 but required by jersey"
- DW 4.x Jersey used `javax.xml.bind` for XML serialization. DW 5.x Jersey uses Jakarta EE 10 (`jakarta.xml.bind`). The codebase confirms all JAX-RS imports are `jakarta.ws.rs.*` (100+ usages), zero `javax.ws.rs.*`.

**Artifacts to remove:**

| groupId | artifactId | Location |
|---------|-----------|----------|
| `javax.xml.bind` | `jaxb-api` | root `dependencyManagement` + commons `dependencies` |
| `com.sun.xml.bind` | `jaxb-core` | root `dependencyManagement` + commons `dependencies` |
| `com.sun.xml.bind` | `jaxb-impl` | root `dependencyManagement` + commons `dependencies` |

### Finding 5 — `javax.activation-api` — REDUNDANT in commons

**Files:** `pom.xml` (dependencyManagement, lines 152–155), `commons/pom.xml` (dependencies, lines 228–231)  
**Status:** ✅ Safe to remove — no Java code in commons uses it; cloud-sdk-aws gets it transitively

**Evidence:**
- `grep` for `import javax.activation` across all `*.java` files:
  - `cloud-sdk-aws` email utils: 6 matches (`DataHandler`, `DataSource`)
  - `email-sender` (deprecated): 2 matches
  - `commons`: **0 matches**
- `cloud-sdk-aws` gets `javax.activation` transitively from `com.sun.mail:javax.mail:1.6.2` (declared in `cloud-sdk-aws/pom.xml` line 312)
- `commons` module has NO code using `javax.activation` — the dependency is dead weight

**Artifact to remove:**

| groupId | artifactId | Location |
|---------|-----------|----------|
| `javax.activation` | `javax.activation-api` | root `dependencyManagement` + commons `dependencies` |

### Finding 6 — `com.codahale.metrics` imports — NOT an issue

Multiple Java files in `commons` use `com.codahale.metrics.*` (MetricRegistry, HealthCheck, Timer, etc.). This is **correct** — Dropwizard Metrics 4.2.x (used by DW 5.0.1) retains the `com.codahale.metrics` package name. No action needed.

### Finding 7 — `io.dropwizard.metrics` shade/JaCoCo excludes — NOT an issue

`utils/local-dynamodb/pom.xml` and `utils/local-elasticsearch/pom.xml` contain `<exclude>io.dropwizard.metrics:*</exclude>` in shade plugin config. These are filter patterns to prevent metrics jars from being bundled into shaded uber-JARs. The group ID `io.dropwizard.metrics` is still the correct Maven group for Dropwizard Metrics 4.2.x. No action needed.

### Impact assessment — client applications on 1.0.25-SNAPSHOT

**Note:** Findings 4 and 5 (`javax.xml.bind`, `javax.activation-api`) are documented for future cleanup but were NOT removed in this commit. Only the `dropwizard-core:4.0.10` (Finding 1) and stale comment (Finding 3) were addressed.

If these javax deps are removed in a future commit, there is **no impact** on client applications because:

1. **No code in mercury-services-commons uses `javax.xml.bind`** — zero imports found across all modules
2. **`javax.activation` for email** — `cloud-sdk-aws` continues to get it transitively from `com.sun.mail:javax.mail:1.6.2`
3. **Client applications** already migrated to Jakarta EE (`jakarta.ws.rs.*`) as part of the DW 5.0.1 upgrade. They do not import or depend on `javax.xml.bind`
4. **DW 5.0.1 does not need these javax deps** — it uses `jakarta.xml.bind` for XML binding

## Verification

All 4 core modules built and installed successfully with `mvn clean install`:

| Module | Tests | Result |
|--------|-------|--------|
| cloud-sdk-api 1.0.25-SNAPSHOT | unit | ✅ SUCCESS |
| dynamo-integration-test 1.0.25-SNAPSHOT | unit | ✅ SUCCESS |
| cloud-sdk-aws 1.0.25-SNAPSHOT | unit + integration (DynamoDB Local) | ✅ SUCCESS |
| commons 1.0.25-SNAPSHOT | unit | ✅ SUCCESS |

**Commit:** `08e1627` on `feature/ION-12310-commons-cloudsdk-refactoring`  
**Pushed:** 2026-05-27 to remote

## Future cleanup

When the Jest Elasticsearch client is replaced with the OpenSearch SDK:
1. Remove `aws-signing-request-interceptor` from `commons/pom.xml`
2. Remove `aws-java-sdk-core` from root `dependencyManagement` (if no other modules need AWS SDK v1)
3. Remove deprecated `dynamo-client` and `email-sender` modules
