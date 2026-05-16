# Rebase Analysis: feature/ION-12310-commons-cloudsdk-refactoring → develop

**Date:** 2026-05-15  
**Branch:** `feature/ION-12310-commons-cloudsdk-refactoring`  
**Target:** `develop`  
**Merge Base:** `cc001e3b08a903828856fa8e3f5637164fc4dbba`  
**Current Version (feature):** `1.0.23-SNAPSHOT` (used by mercury-services applications: network, auth, booking, etc.)

---

## 1. Branch Divergence Summary

| Metric | Count |
|--------|-------|
| Feature branch ahead of develop | **36 commits** |
| Develop ahead of feature branch | **10 commits** |

### Feature Branch Commits (36 commits, 2025-06-28 → 2026-04-23)

```
e3b3267 2026-04-23 ION-12310: remove netty
c721662 2026-02-26 feature/ION-12310 fix for numeric partition and sort keys
98565a9 2026-01-12 feature/ION-12310 allow pr in table prefix pattern
79fdcd5 2025-12-26 feature/ION-12310 default messaging client factory method and MetaData Builder()
77a9536 2025-12-01 feature/ION-12310 fixes for LongEpochSecondAttributeConverter and checks for non-null htmlBody/textBody
b382f7b 2025-11-xx feature/ION-12310 fixes (see README.md v1.0.17-SNAPSHOT) and logging
359e29a           ION-12310 - Fix for Jersey Critical Vulnerability
f7263b6           feature/ION-12310 null check in EnhancedDynamoRepository:findAll()
d5c30af           feature/ION-12310 DW Command name update to dynamo-create
7bc79ff           feature/ION-12310 README.md has list of changes
f00e3d1           feature/ION-12310 refactored DynamoDbAdminCommand, new BaseDynamoDbConfig
0597d5e           feature/ION-12310 DynamoRepositoryFactory createDefault
5d09e9b           feature/ION-12310 changes documented in README.md
55b56ca           ION-12310 changes documented in README.md
d9bb4c7           ION-12310 pom version upgrade to 1.0.10-SNAPSHOT
4c895d8           ION-12310 NullifyEmptyStringConverter, dynamo-integration-test module
8cf11ff           ION-12310 findById with consistentRead, SSE flag, Netty 4.1.122
1177f07           ION-12310 removed entitymapper, now using TableSchema
c83ace1           ION-12310 fixed typo in pom file for dynamo-integration-test deploy
375cb0f           ION-12310 add DynamoDbExtension.java, SampleIntegrationTest.java
71192a5           ION-12310 export(), fixed saveIfNotExists/findAll/save, dynamo-integration-test
9284e6e           ION-12310 table prefix regex fix, EmailClientFactory templates
8f77c49           ION-12310 content-disposition presigned url, S3Presigner reuse
8b5da03           ION-12310 StorageClient generatePresignedUrl with filename
8aa8364           ION-12310 pom version 1.0.3-SNAPSHOT
d270b6d           ION-12310 decryption flag, deleteById cleanup
a6e7115           ION-12310 updated to 1.0.2-SNAPSHOT
fdb7f68           ION-12310 fix SSM bug
1a6af1c           ION-12310 AWS BOM 2.30.24, exception message handling
15d12bc           ION-12310 AWS BOM 2.30.24 (duplicate)
bce9ea8           ION-12310 flatten-maven-plugin, mvn deploy for cloud-sdk-api/aws
ad29e36           ION-12310 added missing Annotations classes
6671dbf           ION-12310 pom versions
738af6b 2025-08-19 ION-12310 pom changes
6937c81 2025-06-28 ION-12310 missed one pom file
c13b2a9 2025-06-28 ION-12310 removed aws deps from commons, SSM refactor, moved classes
```

### Develop Commits (10 commits, 2025-11-11 → 2026-01-13)

```
ce08d52 2026-01-13 Pull request #39: ION-14340: Apache commons-text dependency upgrade
f77ddd4 2026-01-13 ION-14340: Apache commons-text dependency upgrade
97b9b25 2025-11-24 Pull request #38: ION-13822: Dropwizard upgrade to version 4.0.16 - other fixes
1dba34e 2025-11-24 ION-13822: Dropwizard upgrade to version 4.0.16 - other fixes
b953e4e 2025-11-24 Pull request #37: ION-13822: Dropwizard upgrade to version 4.0.16
2794632 2025-11-24 ION-13822: Dropwizard upgrade to version 4.0.16
2f10d93 2025-11-24 Pull request #36: ION-13822: Dropwizard upgrade to version 4.0.16
cf0e233 2025-11-21 ION-13822: Dropwizard upgrade to version 4.0.16
96835ee 2025-11-11 Pull request #35: ION-13833 - External Monitoring API excluded from Authentication
24c303f 2025-11-11 ION-13833 - External Monitoring API excluded from Authentication
```

---

## 2. Files Changed Summary

### Files Changed ONLY on Feature Branch (no conflict risk)

These files were added, modified, or deleted exclusively by the feature branch. They will apply cleanly.

**New modules added:**
- `dynamo-integration-test/` — entire new module (pom.xml, source files, test files, native libs)

**New files in cloud-sdk-api:**
- `cloud-sdk-api/src/main/java/.../config/ElasticSearchServiceConfig.java`
- `cloud-sdk-api/src/main/java/.../elasticsearch/JestClientBuilder.java`
- `cloud-sdk-api/src/main/java/.../elasticsearch/JestClientRetryHandler.java`
- `cloud-sdk-api/src/main/java/.../notification/annotation/Annotations.java`

**Modified cloud-sdk-api files:**
- `cloud-sdk-api/pom.xml`
- `cloud-sdk-api/src/main/java/.../database/api/DatabaseRepository.java`
- `cloud-sdk-api/src/main/java/.../notification/workflow/Event.java`
- `cloud-sdk-api/src/main/java/.../notification/workflow/MetaData.java`
- `cloud-sdk-api/src/main/java/.../storage/api/StorageClient.java`

**Renamed/moved files from commons → cloud-sdk-api/cloud-sdk-aws:**
- `Annotation.java` → `cloud-sdk-api/.../notification/annotation/Annotation.java`
- `ErrorHelper.java` → `cloud-sdk-api/.../notification/annotation/ErrorHelper.java`
- `AWSConstants.java` → `cloud-sdk-aws/.../aws/module/AWSConstants.java`
- `AwsRetryCondition.java` → `cloud-sdk-aws/.../aws/module/AwsRetryCondition.java`
- `JestModule.java` → `cloud-sdk-aws/.../aws/module/JestModule.java`
- `SNSModule.java` → `cloud-sdk-aws/.../aws/module/SNSModule.java`
- `SQSModule.java` → `cloud-sdk-aws/.../aws/module/SQSModule.java`
- `SQSReader.java` → `cloud-sdk-aws/.../aws/module/SQSReader.java`
- `SQSWriter.java` → `cloud-sdk-aws/.../aws/module/SQSWriter.java`

**New files in cloud-sdk-aws:**
- `cloud-sdk-aws/src/main/java/.../aws/retry/AwsRetryCondition.java`
- `cloud-sdk-aws/src/main/java/.../database/config/BaseDynamoDbConfig.java`
- `cloud-sdk-aws/src/main/java/.../database/converter/LongEpochSecondAttributeConverter.java`
- `cloud-sdk-aws/src/main/java/.../database/converter/NullifyEmptyStringConverter.java`
- Multiple new test files

**Modified cloud-sdk-aws files (extensive):**
- `cloud-sdk-aws/pom.xml` and ~25 source/test files (database, email, messaging, storage)

**Deleted DynamoDB Local jars** — ~60+ jar/so/dll files removed from cloud-sdk-aws test resources

**Modified commons files:**
- `commons/pom.xml` — removed AWS 1.x SDK dependencies
- `commons/src/main/java/.../config/ParameterStoreConfigTransform.java` — migrated to commons-text `StringSubstitutor`
- `commons/src/main/java/.../config/ParameterStoreLookup.java` — migrated to commons-text `StringLookup`
- `commons/src/test/java/.../config/ParameterStoreConfigTransformTest.java`
- `commons/src/test/java/.../config/ParameterStoreLookupTest.java`

**Deleted commons files:**
- `commons/src/main/java/.../messaging/logging/EventGenerator.java`
- `commons/src/main/java/.../messaging/logging/EventLogger.java`
- `commons/src/main/java/.../messaging/logging/EventPublisher.java`
- `commons/src/main/java/.../messaging/logging/SNSEventPublisher.java`
- `commons/src/main/java/.../messaging/model/Annotations.java`
- `commons/src/main/java/.../messaging/model/Event.java`
- `commons/src/main/java/.../messaging/model/MetaData.java`
- `commons/src/main/java/.../messaging/model/WorkflowAware.java`
- `commons/src/main/java/.../messaging/sns/MessageSender.java`
- `commons/src/main/java/.../messaging/sns/SNSClient.java`
- `commons/src/main/java/.../messaging/sqs/SQSClient.java`
- `commons/src/main/java/.../messaging/util/RandomGenerator.java`

**Other modified:**
- `build_deploy.sh` — added cloud-sdk-api, cloud-sdk-aws, dynamo-integration-test deploy steps
- `dynamo-client/pom.xml`
- `email-sender/pom.xml`

### Files Changed ONLY on Develop (no conflict risk)

- `.gitignore` — **new file** added (standard Java/Maven/IDE ignores)
- `commons/src/main/java/.../auth/AuthenticationFilter.java` — added `/network/monitoring/status/current` to excluded paths
- `commons/src/main/java/.../config/ServiceDefinition.java` — added `preppedUri` field
- `utils/local-elasticsearch/pom.xml` — logback version `1.5.6` → `1.5.18`

### Files Changed on BOTH Branches (CONFLICT CANDIDATES)

| File | Feature Change | Develop Change |
|------|---------------|----------------|
| **`pom.xml`** | Major refactoring (version, modules, dependencies) | Version bump, DW upgrade, commons-text |
| **`README.md`** | Added v1.0.4 through v1.0.18 changelog (appended at bottom) | Added v1.R.01.020-022 changelog (inserted near top) |

---

## 3. Conflict Analysis — Detailed

### CONFLICT 1: `pom.xml` (ROOT) — ⚠️ HIGH COMPLEXITY

Both branches modified the root `pom.xml` from the same base (`1.R.01.019`). The changes overlap in the `<properties>` section.

#### Property-by-Property Comparison

| Property | Merge Base | Feature Branch | Develop | Resolution |
|----------|-----------|----------------|---------|------------|
| `dependency.version` | `1.R.01.019` | `1.0.23-SNAPSHOT` | `1.R.01.022` | **Feature** — SNAPSHOT versioning for cloud-sdk work |
| `utils.dependency.version` | `1.R.01.003` | `1.R.01.003` (unchanged) | `1.R.01.004` | **Develop** — take `1.R.01.004` |
| `dropwizard.version` | `4.0.10` | `4.0.16` | `4.0.16` | **Same** — both upgraded to 4.0.16 ✅ |
| `dropwizard-metrics-datadog` | `4.0.2` | `4.0.2` (unchanged) | `4.0.16` | **Develop** — take `4.0.16` |
| `jackson-dataformat-csv` | `2.16.2` | `2.19.2` | `2.19.2` | **Same** ✅ |
| `jackson-datatype-joda` | `2.16.2` | `2.19.2` | `2.19.2` | **Same** ✅ |
| `jackson-dataformat-jsr310` | `2.16.2` | `2.19.2` | `2.19.2` | **Same** ✅ |
| `assertj.core.version` | `3.8.0` | `3.27.2` | `3.8.0` (unchanged) | **Feature** — take `3.27.2` |
| `jackson-datatype-jdk8.version` | `2.17.2` | `2.19.2` | `2.19.2` | **Same** ✅ |
| `jackson-datatype-jsr310.version` | `2.17.2 ` | `2.19.2 ` (trailing space) | `2.19.2` (no trailing space) | **Develop** — take without trailing space |
| `commons-lang3.version` | `3.18.0` | `3.18.0` (unchanged) | `3.18.0` (unchanged) | **Same** ✅ |

#### Structural Changes in `pom.xml`

| Change | Feature Branch | Develop |
|--------|---------------|---------|
| `<module>dynamo-integration-test</module>` | ✅ Added | Not present |
| Removed `aws-java-sdk-core` dependency block | ✅ Removed | Unchanged |
| Removed `aws-java-sdk-ssm` dependency block | ✅ Removed | Unchanged |
| Removed `aws-java-sdk-s3` dependency block | ✅ Removed | Unchanged |
| `commons-text` version | Unchanged (`1.10.0`) | **`1.15.0`** |

#### Resolution Strategy for `pom.xml`

During rebase, when the conflict occurs on this file:

1. **Keep feature branch version** for `dependency.version` → `1.0.23-SNAPSHOT`
2. **Accept develop's** `utils.dependency.version` → `1.R.01.004`
3. **Accept develop's** `dropwizard-metrics-datadog` → `4.0.16`
4. **Keep feature branch's** `assertj.core.version` → `3.27.2`
5. **Accept develop's** `jackson-datatype-jsr310.version` → `2.19.2` (without trailing space)
6. **Keep feature branch's** `<module>dynamo-integration-test</module>`
7. **Keep feature branch's** removal of AWS 1.x SDK dependencies
8. **Accept develop's** `commons-text` version → `1.15.0`

> ⚠️ **IMPORTANT:** The feature branch's `ParameterStoreConfigTransform.java` and `ParameterStoreLookup.java` 
> already migrated from `commons-lang3 StrSubstitutor` to `commons-text StringSubstitutor`. 
> The develop branch's commons-text upgrade to `1.15.0` is compatible and should be accepted.

### CONFLICT 2: `README.md` — ⚠️ MEDIUM COMPLEXITY

Both branches modified `README.md` but in **different sections**:

- **Develop** inserted 3 new changelog entries **near the top** (after line 9, before the existing "OWASP Issues" entry):
  ```
  #### Dropwizard minor version upgrade (v1.R.01.022)
  #### Dropwizard minor version upgrade (v1.R.01.021)
  #### Site247 Monitoring - ION-13833 (v1.R.01.020)
  ```

- **Feature branch** appended cloud-sdk version changelog entries **at the bottom** (after line 153):
  ```
  ### Commons v1.0.4-SNAPSHOT through v1.0.18-SNAPSHOT
  ```

**Resolution:** Git may auto-merge this cleanly since changes are in different regions of the file. If it does conflict (e.g., due to context line overlap), accept both sets of changes:
- Keep develop's entries near the top
- Keep feature branch's entries at the bottom

---

## 4. Non-Conflicting Changes to Accept from Develop

These changes from develop touch files the feature branch did NOT modify. They will apply cleanly:

| File | Change | Action |
|------|--------|--------|
| `.gitignore` | New file with standard Java/Maven/IDE ignores | Accept as-is |
| `AuthenticationFilter.java` | Added `/network/monitoring/status/current` to auth-excluded paths | Accept as-is |
| `ServiceDefinition.java` | Added `preppedUri` field | Accept as-is |
| `utils/local-elasticsearch/pom.xml` | logback `1.5.6` → `1.5.18` | Accept as-is |

---

## 5. Risk Assessment

### Low Risk ✅
- `.gitignore`, `AuthenticationFilter.java`, `ServiceDefinition.java`, `local-elasticsearch/pom.xml` — clean merges
- `README.md` — different sections, likely auto-merges

### Medium Risk ⚠️
- `pom.xml` — overlapping property changes require careful manual resolution
- The `commons-text` upgrade in develop (`1.10.0` → `1.15.0`) is **compatible** with the feature branch's migration from `StrSubstitutor` (commons-lang3) to `StringSubstitutor` (commons-text), but verify no API breaks in 1.15.0

### High Risk ❌
- None identified. All develop changes are additive and do not conflict with the cloud-sdk refactoring architecture.

### Impact on Downstream Applications
- **mercury-services applications (network, auth, booking, etc.)** use `1.0.23-SNAPSHOT` of commons/cloud-sdk libraries
- The rebase will NOT change the API surface of cloud-sdk-api or cloud-sdk-aws
- The `dropwizard-metrics-datadog` bump from `4.0.2` → `4.0.16` should be validated against downstream apps
- The `commons-text` `1.15.0` and `utils.dependency.version` `1.R.01.004` should be validated

---

## 6. Rebase Commands & Steps

### Pre-Rebase Preparation

#### Working Directory Status (verified 2026-05-15 19:56)

| Check | Result |
|-------|--------|
| **Staged files** | ✅ None |
| **Unstaged modifications** | ✅ None |
| **Local ↔ Remote sync** | ✅ Both at `e3b3267` — 0 ahead, 0 behind |
| **Untracked files** | 6 items (see below) — **no stash needed** |

**Untracked files (will NOT interfere with rebase):**
```
.claude/settings.local.json                       ← Claude local settings
.github/copilot-instructions.md                   ← Copilot instructions
.github/java-upgrade/                             ← Java upgrade hooks/scripts
.gitignore                                        ← local gitignore (not yet tracked)
cloud-sdk-api/docs/                               ← this rebase doc + architecture doc
cloud-sdk-aws/docs/                               ← OWASP/netty/architecture docs
commons/docs/                                     ← architecture doc
```

> **No stash is required.** Untracked files are ignored by `git rebase` — they stay in the working
> directory untouched. A stash is only needed for **uncommitted tracked changes** (staged or unstaged
> modifications to files git already tracks), which we have none of.
>
> **Caution:** If any ION-15755 commit on Monday creates a file at the same path as an untracked file
> (e.g., `.gitignore`), the rebase will refuse to overwrite it and stop. In that case you would need
> to temporarily move or `git stash --include-untracked` first. For today's rebase, develop does add
> `.gitignore` — but since our local `.gitignore` is untracked and develop adds one, git may warn.
> If this happens: `mv .gitignore .gitignore.local`, rebase, then reconcile afterward.

#### Backup branch: ✅ Created
```
backup/feature-ION-12310-pre-rebase → e3b3267
```

```bash
# 1. Verify working directory is clean (already confirmed ✅)
cd C:\Users\arijit.kundu\projects\mercury-services-commons
git status

# 2. Backup branch already created ✅
# git branch backup/feature-ION-12310-pre-rebase

# 3. Fetch latest from remote (already done ✅)
# git fetch origin develop

# 4. Handle .gitignore conflict if git warns about untracked file
#    (develop adds .gitignore — may conflict with local untracked copy)
mv .gitignore .gitignore.local
```

### Rebase Execution

```bash
# 4. Start the rebase
git rebase origin/develop
```

### Expected Conflict Resolution Steps

#### Step A: pom.xml Conflict

When `pom.xml` conflicts during rebase:

```bash
# Open pom.xml in editor and resolve conflicts:
# The conflict markers will look like:
#
# <<<<<<< HEAD (develop)
#     <dependency.version>1.R.01.022</dependency.version>
#     <utils.dependency.version>1.R.01.004</utils.dependency.version>
# =======
#     <dependency.version>1.0.23-SNAPSHOT</dependency.version>
#     <utils.dependency.version>1.R.01.003</utils.dependency.version>
# >>>>>>> feature commit
#
# RESOLVE TO:
#     <dependency.version>1.0.23-SNAPSHOT</dependency.version>
#     <utils.dependency.version>1.R.01.004</utils.dependency.version>

# For dropwizard-metrics-datadog:
# RESOLVE TO: <dropwizard-metrics-datadog>4.0.16</dropwizard-metrics-datadog>

# For assertj.core.version:
# RESOLVE TO: <assertj.core.version>3.27.2</assertj.core.version>

# For jackson-datatype-jsr310.version:
# RESOLVE TO: <jackson-datatype-jsr310.version>2.19.2</jackson-datatype-jsr310.version>
# (no trailing space)

# For commons-text version:
# RESOLVE TO: <version>1.15.0</version>

# Keep the dynamo-integration-test module entry
# Keep the removal of AWS 1.x SDK dependency blocks

# After resolving:
git add pom.xml
```

#### Step B: README.md Conflict (if occurs)

```bash
# If README.md conflicts:
# Keep BOTH sets of changes:
# - Develop's entries near the top (v1.R.01.020 - v1.R.01.022)
# - Feature's entries at the bottom (v1.0.4-SNAPSHOT - v1.0.18-SNAPSHOT)

git add README.md
```

#### Step C: Continue Rebase

```bash
# After resolving each conflict:
git rebase --continue

# If more conflicts appear, repeat resolution steps
# If things go wrong:
git rebase --abort
```

### Post-Rebase Validation

```bash
# 5. Verify the rebase result
git log --oneline -50

# 6. Verify no files were lost
git diff origin/develop --name-status

# 7. Build and test
mvn clean verify -pl cloud-sdk-api -am
mvn clean verify -pl cloud-sdk-aws -am
mvn clean verify -pl commons -am

# 8. If all tests pass, force-push the rebased branch
git push origin feature/ION-12310-commons-cloudsdk-refactoring --force-with-lease
```

---

## 7. Final Merged State — Expected pom.xml Properties

After a successful rebase, the root `pom.xml` properties should be:

```xml
<properties>
    <dependency.version>1.0.23-SNAPSHOT</dependency.version>
    <utils.dependency.version>1.R.01.004</utils.dependency.version>
    <maven-surefire-plugin.version>3.1.2</maven-surefire-plugin.version>
    <maven-failsafe-plugin.version>3.1.2</maven-failsafe-plugin.version>
    <maven-shade-plugin.version>3.5.1</maven-shade-plugin.version>
    <maven.compiler.version>3.12.1</maven.compiler.version>
    <maven.compiler.release>17</maven.compiler.release>
    <aws.java.sdk.version>1.12.638</aws.java.sdk.version>
    <guice.version>7.0.0</guice.version>
    <lombok.version>1.18.32</lombok.version>
    <dropwizard.version>4.0.16</dropwizard.version>
    <dropwizard-metrics-datadog>4.0.16</dropwizard-metrics-datadog>
    <dropwizard-core-metrics>4.2.30</dropwizard-core-metrics>
    <jackson-dataformat-csv>2.19.2</jackson-dataformat-csv>
    <jackson-datatype-joda>2.19.2</jackson-datatype-joda>
    <jackson-dataformat-jsr310>2.19.2</jackson-dataformat-jsr310>
    <mockito.version>5.10.0</mockito.version>
    <junit.version>4.13.2</junit.version>
    <slf4j.version>2.0.16</slf4j.version>
    ...
    <assertj.core.version>3.27.2</assertj.core.version>
    ...
    <jackson-datatype-jdk8.version>2.19.2</jackson-datatype-jdk8.version>
    <jackson-datatype-jsr310.version>2.19.2</jackson-datatype-jsr310.version>
    <commons-lang3.version>3.18.0</commons-lang3.version>
</properties>
```

Modules list should include:
```xml
<modules>
    <module>commons</module>
    <module>dynamo-client</module>
    <module>email-sender</module>
    <module>utils/dropwizard-metrics-datadog</module>
    <module>utils/local-dynamodb</module>
    <module>utils/local-elasticsearch</module>
    <module>cloud-sdk-aws</module>
    <module>cloud-sdk-api</module>
    <module>dynamo-integration-test</module>
</modules>
```

AWS 1.x SDK dependency blocks should remain **removed** (as per feature branch).

`commons-text` version should be `1.15.0` (from develop).

---

## 8. FAQ — Pre-Rebase Questions

### Q1: Will the rebase create a new commit? Should I bump the SNAPSHOT version and update README.md?

**No, a rebase does not create a "new" merge commit.** A rebase replays your 36 feature commits on top of
the latest develop. Each of your existing commits gets re-applied (with new commit hashes) but their content
stays the same. The only commits where you intervene are the ones that conflict — you resolve the conflict
and `git rebase --continue` re-applies that commit with your resolution folded in.

**You do NOT need to bump the SNAPSHOT version or update README.md as part of the rebase itself.** The version
`1.0.23-SNAPSHOT` and the README changelog entries you already have will carry forward as-is. A version bump
would only be warranted if you are making new functional changes. The rebase is purely a housekeeping operation
to bring in develop's latest changes beneath your work.

**However**, after the rebase you should do a full `mvn clean verify` build. If you discover that the newly
incorporated changes (e.g., `dropwizard-metrics-datadog 4.0.16`, `commons-text 1.15.0`, `logback 1.5.18`)
require any code adjustments, then those adjustments would be a new commit on top — and at that point you
could bump to `1.0.24-SNAPSHOT` and add a README entry. But this is unlikely given the compatibility analysis.

### Q2: What about the ION-15755 branch (DW 5.0.1 / Jetty 12.1.9 upgrade)?

**Decided approach:** Rebase today (Thursday) with current develop to sync up, then rebase again
Monday after ION-15755 merges to develop. See **Section 10** below for the full Monday rebase analysis.

### Q3: Backup Branch Safety

✅ **Backup branch confirmed created:**
```
backup/feature-ION-12310-pre-rebase → e3b3267 (ION-12310: remove netty)
```

If anything goes wrong during rebase:
```bash
# Abort the in-progress rebase
git rebase --abort

# Or, nuclear option — reset to the backup
git checkout feature/ION-12310-commons-cloudsdk-refactoring
git reset --hard backup/feature-ION-12310-pre-rebase
```

---

## 9. Post-Rebase Checklist

- [ ] All conflicts resolved correctly
- [ ] `mvn clean verify` passes for cloud-sdk-api, cloud-sdk-aws, commons
- [ ] No regression in downstream mercury-services applications (network, auth, booking)
- [ ] `dependency.version` remains `1.0.23-SNAPSHOT`
- [ ] `dropwizard-metrics-datadog` is `4.0.16`
- [ ] `utils.dependency.version` is `1.R.01.004`
- [ ] `commons-text` is `1.15.0`
- [ ] `.gitignore` present in repo
- [ ] `AuthenticationFilter.java` includes `/network/monitoring/status/current`
- [ ] `ServiceDefinition.java` includes `preppedUri` field
- [ ] `utils/local-elasticsearch/pom.xml` has logback `1.5.18`
- [ ] Force-push with `--force-with-lease` (safe force push)

---

## 10. Monday Rebase — ION-15755 (DW 5.0.1 + Jetty 12.1.9 Upgrade)

> **Prerequisite:** Today's rebase with develop (Sections 1–9) is completed first.
> After today's rebase, the feature branch will be on top of develop at `ce08d52`.
> Once ION-15755 is merged to develop, we rebase again to pick up those changes.

### 10.1 ION-15755 Branch Overview

| Attribute | Value |
|-----------|-------|
| Branch | `origin/ION-15755` |
| Commits | 2 (on top of current develop) |
| Theme | **Dropwizard 4.0.16 → 5.0.1**, **Jetty 11 → 12.1.9**, remove Datadog metrics module |

**Commits:**
```
1b6eb41 2026-05-15 ION-15755 - DW 5.0.1 and Jetty 12.1.9 upgrade
ab1d0bf 2026-05-11 ION-15755 - Remove Datadog dropwizard metrics implementation
```

### 10.2 What ION-15755 Changes

#### Root `pom.xml` — Major Version Bumps

| Property | After Today's Rebase | After ION-15755 | Impact on Feature |
|----------|---------------------|-----------------|-------------------|
| `dropwizard.version` | `4.0.16` | **`5.0.1`** | ⚠️ Major upgrade |
| `jetty.version` | _(not set)_ | **`12.1.9`** (new property) | ⚠️ New property to accept |
| `dropwizard-metrics-datadog` | `4.0.16` | **REMOVED** | ⚠️ Property deleted |
| `dropwizard-core-metrics` | `4.2.30` | **REMOVED** | ⚠️ Property deleted |
| `jackson-dataformat-csv` | `2.19.2` | **`2.21.0`** | ⚠️ Version bump |
| `jackson-datatype-joda` | `2.19.2` | **`2.21.0`** | ⚠️ Version bump |
| `jackson-dataformat-jsr310` | _(removed in ION-15755)_ | — | Check |
| `jackson-datatype-jdk8.version` | `2.19.2` | **`2.21.0`** | ⚠️ Version bump |
| `jackson-datatype-jsr310.version` | `2.19.2` | **`2.21.0`** | ⚠️ Version bump |
| `slf4j.version` | `2.0.16` | **`2.0.17`** | Minor bump |
| `google.guava.version` | `32.1.3-jre` | **`33.5.0-jre`** | ⚠️ Major bump |
| `assertj.core.version` | `3.27.2` | `3.8.0` (ION-15755 base) | Keep **`3.27.2`** |
| `commons-lang3.version` | `3.18.0` | **`3.20.0`** | Version bump |
| `dependency.version` | `1.0.23-SNAPSHOT` | `1.R.01.023` | Keep **`1.0.23-SNAPSHOT`** |

#### Root `pom.xml` — Structural Changes

- **New BOM imports** added to `<dependencyManagement>`:
  - `org.eclipse.jetty:jetty-bom:${jetty.version}` (Jetty core BOM)
  - `org.eclipse.jetty.ee10:jetty-ee10-bom:${jetty.version}` (Jetty EE10 BOM)
  - `io.dropwizard:dropwizard-dependencies:${dropwizard.version}` (DW BOM import)
- **Module removed:** `utils/dropwizard-metrics-datadog` deleted from `<modules>`
- **Duplicate property removed:** second `<jknack.handlebars.version>` entry cleaned up

#### `commons/pom.xml` Changes

- **New dependency:** `org.eclipse.jetty.ee10:jetty-ee10-servlets` (DoSFilter moved here in Jetty 12)
- **Removed version:** `jersey-media-jaxb` version `3.1.3` → inherits from DW BOM
- **Removed dependency:** `dropwizard-metrics-datadog` (module deleted)
- **Removed dependencies:** `junit-jupiter-params`, `mockito-core` (explicit) — replaced with BOM-managed
- **Added dependency:** `junit-vintage-engine:5.12.2` (for legacy JUnit 4 tests on JUnit Platform)
- **Removed dependency:** `aws-java-sdk-ssm` — note: feature branch already removed this ✅
- **Removed dependencies:** `metrics-core`, `dropwizard-logging` (explicit versions) — replaced with BOM
- **Added dependency:** `org.projectlombok:lombok` (version from parent)
- **Added:** `<flattenDependencyMode>all</flattenDependencyMode>` to flatten-maven-plugin
- **Updated comment:** "All the below dependencies..." → cleaner comment

#### `commons/src/main/java` Changes

| File | Change |
|------|--------|
| `InttraServer.java` | Import changed: `org.eclipse.jetty.servlets.DoSFilter` → `org.eclipse.jetty.ee10.servlets.DoSFilter` |
| `LocalCacheProvider.java` | Added null check before `value.orElse(null)` (bugfix) |

#### New Test File

- `commons/src/test/java/.../InttraServerBootstrapTest.java` — new test for InttraServer bootstrap

#### Other File Changes

| File | Change |
|------|--------|
| `dynamo-client/pom.xml` | Added `<flattenDependencyMode>all</flattenDependencyMode>` |
| `email-sender/pom.xml` | Added `<flattenDependencyMode>all</flattenDependencyMode>` |
| `build_utils_deploy.sh` | Removed `dropwizard-metrics-datadog` build/deploy block |
| `.gitignore` | Added `.codegraph/`, `.github/`, `docs/`, workspace file, `**/flattened_pom.xml` |

#### Deleted Module

- **Entire `utils/dropwizard-metrics-datadog/`** directory deleted (~30 files: source, tests, META-INF services)

### 10.3 Monday Conflict Analysis (after today's rebase)

After today's rebase, our feature branch will already have today's develop changes incorporated.
When ION-15755 merges to develop and we rebase again, the conflicts will be:

#### CONFLICT M1: `pom.xml` — ⚠️ HIGH COMPLEXITY

This will be the main conflict. Almost every property in `<properties>` changes.

**Resolution strategy:**

```xml
<!-- KEEP feature branch -->
<dependency.version>1.0.23-SNAPSHOT</dependency.version>

<!-- ACCEPT from ION-15755 -->
<dropwizard.version>5.0.1</dropwizard.version>
<jetty.version>12.1.9</jetty.version>            <!-- NEW property — accept -->
<jackson-dataformat-csv>2.21.0</jackson-dataformat-csv>
<jackson-datatype-joda>2.21.0</jackson-datatype-joda>
<jackson-datatype-jdk8.version>2.21.0</jackson-datatype-jdk8.version>
<jackson-datatype-jsr310.version>2.21.0</jackson-datatype-jsr310.version>
<slf4j.version>2.0.17</slf4j.version>
<google.guava.version>33.5.0-jre</google.guava.version>
<commons-lang3.version>3.20.0</commons-lang3.version>

<!-- KEEP feature branch (higher than ION-15755 base) -->
<assertj.core.version>3.27.2</assertj.core.version>

<!-- ACCEPT from ION-15755 — properties REMOVED -->
<!-- dropwizard-metrics-datadog — REMOVE this property -->
<!-- dropwizard-core-metrics — REMOVE this property -->

<!-- ACCEPT from ION-15755 — new BOM imports in dependencyManagement -->
<!-- jetty-bom, jetty-ee10-bom, dropwizard-dependencies BOM -->

<!-- KEEP feature branch -->
<module>dynamo-integration-test</module>          <!-- not in ION-15755 -->

<!-- ACCEPT from ION-15755 -->
<!-- REMOVE <module>utils/dropwizard-metrics-datadog</module> -->
```

#### CONFLICT M2: `commons/pom.xml` — ⚠️ HIGH COMPLEXITY

Both the feature branch and ION-15755 modified `commons/pom.xml` significantly.

**Key overlapping changes:**

| Area | Feature Branch | ION-15755 | Resolution |
|------|---------------|-----------|------------|
| AWS SDK deps removed | ✅ Removed `aws-java-sdk-sqs`, `sns`, `core`, `ssm`, `s3` | Removes `aws-java-sdk-ssm` only | Keep feature's more complete removal |
| `dropwizard-metrics-datadog` dep | Still present (version from parent) | **REMOVED** | **Accept removal** — module is deleted |
| `jersey-media-jaxb` version | Has `3.1.3` | Inherits from BOM (no version) | **Accept ION-15755** — remove version |
| `metrics-core` / `dropwizard-logging` | Present with versions | **REMOVED** (BOM-managed) | **Accept removal** |
| `junit-jupiter-params` | Present | **REMOVED** | **Accept removal** |
| `mockito-core` | Present | **REMOVED** (BOM-managed) | **Accept removal** |
| `junit-vintage-engine` | Not present | **ADDED** | **Accept addition** |
| `lombok` dependency | Not present | **ADDED** | **Accept addition** |
| `jetty-ee10-servlets` dep | Not present | **ADDED** | **Accept addition** |
| flatten-maven-plugin config | No `flattenDependencyMode` | Added `<flattenDependencyMode>all</flattenDependencyMode>` | **Accept addition** |
| Comment update | Has old comment | Updated comment | **Accept ION-15755** |

#### CONFLICT M3: `.gitignore` — ⚠️ LOW

After today's rebase, `.gitignore` will have the develop version (14 lines).
ION-15755 adds 5 more lines. Should merge cleanly.

> ⚠️ **NOTE:** ION-15755 adds `docs/` to `.gitignore`. This would ignore the `cloud-sdk-api/docs/`
> directory where this document lives. The `.gitignore` pattern `docs/` matches any `docs/` directory
> at any level. **You may want to adjust this** to not ignore `cloud-sdk-api/docs/` — e.g., change
> the pattern to `/docs/` (root only) or add `!cloud-sdk-api/docs/` as an exception.

#### CONFLICT M4: `dynamo-client/pom.xml` and `email-sender/pom.xml` — ⚠️ LOW

Feature branch modified both files. ION-15755 adds `<flattenDependencyMode>all</flattenDependencyMode>`
to both. Likely auto-merges since the changes are in different sections. If not, accept both changes.

#### NO CONFLICT — Clean Merges

| File | Reason |
|------|--------|
| `InttraServer.java` | Feature branch didn't touch this file — clean merge |
| `LocalCacheProvider.java` | Feature branch didn't touch this file — clean merge |
| `InttraServerBootstrapTest.java` | New file — clean merge |
| `build_utils_deploy.sh` | Feature branch only modified `build_deploy.sh`, not `build_utils_deploy.sh` |
| Deleted `utils/dropwizard-metrics-datadog/` | Feature branch didn't modify these — clean delete |

### 10.4 ⚠️ CRITICAL: `dynamo-integration-test` Jetty Compatibility

The `dynamo-integration-test` module currently pins:
```xml
<jetty.version>11.0.24</jetty.version>           <!-- Jetty 11 for DynamoDB Local 2.0.0 -->
<dynamodb-local.version>2.0.0</dynamodb-local.version>
<jackson-databind version="2.19.2" />             <!-- hardcoded for DW 4.0.16 -->
```

After ION-15755 is merged, the parent pom will define `<jetty.version>12.1.9</jetty.version>`.
This will **shadow** the local property in `dynamo-integration-test` since the parent defines it too.

**Action required after Monday's rebase:**
1. The `dynamo-integration-test/pom.xml` locally overrides `<jetty.version>11.0.24</jetty.version>` — 
   this should still take precedence over the parent's `12.1.9` because child module properties
   override parent properties. **Verify this with `mvn help:effective-pom -pl dynamo-integration-test`.**
2. The hardcoded `jackson-databind` version `2.19.2` needs to be updated to `2.21.0` to align with 
   DW 5.0.1's Jackson platform.
3. Consider whether DynamoDB Local 2.0.0 (Jetty 11) can coexist with the rest of the project on Jetty 12.
   Since `dynamo-integration-test` is a **test-only** module, the Jetty 11 classes are isolated in test scope
   and should not conflict with the main application's Jetty 12 runtime. **But this must be validated.**
4. Long-term: evaluate upgrading to DynamoDB Local ≥2.1 which uses Jetty 12, eliminating the version split.

### 10.5 Monday Rebase Commands

```bash
# 1. Create a second backup (after today's successful rebase)
git branch backup/feature-ION-12310-post-thursday-rebase

# 2. Fetch latest develop (after ION-15755 is merged)
git fetch origin develop

# 3. Verify ION-15755 commits are in develop
git --no-pager log --oneline origin/develop | head -15

# 4. Rebase
git rebase origin/develop

# 5. Resolve conflicts (see M1–M4 above)
# For each conflict:
#   - Edit the file
#   - git add <file>
#   - git rebase --continue

# 6. After successful rebase — validate
mvn clean verify -pl cloud-sdk-api -am
mvn clean verify -pl cloud-sdk-aws -am
mvn clean verify -pl commons -am
mvn clean verify -pl dynamo-integration-test -am

# 7. Check effective Jetty version in dynamo-integration-test
mvn help:effective-pom -pl dynamo-integration-test | Select-String "jetty"

# 8. Force-push
git push origin feature/ION-12310-commons-cloudsdk-refactoring --force-with-lease
```

### 10.6 Monday Post-Rebase Checklist

- [ ] `dropwizard.version` is `5.0.1`
- [ ] `jetty.version` is `12.1.9` in root pom
- [ ] `dynamo-integration-test` still has local `<jetty.version>11.0.24</jetty.version>` override
- [ ] Effective Jetty version in `dynamo-integration-test` is `11.0.24` (not `12.1.9`)
- [ ] `jackson-databind` in `dynamo-integration-test` updated to `2.21.0`
- [ ] All Jackson versions aligned at `2.21.0`
- [ ] `dropwizard-metrics-datadog` module and property removed
- [ ] `dropwizard-core-metrics` property removed
- [ ] `commons/pom.xml` has `jetty-ee10-servlets` dependency
- [ ] `commons/pom.xml` has `junit-vintage-engine` dependency
- [ ] `commons/pom.xml` has `flattenDependencyMode` set to `all`
- [ ] `InttraServer.java` uses `org.eclipse.jetty.ee10.servlets.DoSFilter`
- [ ] `dependency.version` remains `1.0.23-SNAPSHOT`
- [ ] `.gitignore` does NOT ignore `cloud-sdk-api/docs/`
- [ ] `mvn clean verify` passes for all modules
- [ ] Force-push with `--force-with-lease`

---

## 11. Rebase Execution — Completed ✅

**Date/Time:** 2026-05-15 ~20:15 EDT  
**Performed by:** Copilot CLI assisted  

### 11.1 Pre-Rebase State

| Item | Value |
|------|-------|
| Feature branch HEAD (pre-rebase) | `e3b3267` (ION-12310: remove netty) |
| Remote HEAD | `e3b3267` (in sync) |
| Develop HEAD (target) | `ce08d52` |
| Backup branch | `backup/feature-ION-12310-pre-rebase` → `e3b3267` |
| Working directory | Clean — no staged, unstaged, or stashed changes |
| Untracked files | `.claude/`, `.github/`, `.gitignore`, `cloud-sdk-api/docs/`, `cloud-sdk-aws/docs/`, `commons/docs/` |

### 11.2 Pre-Rebase Preparation

1. **Backup branch created:** `git branch backup/feature-ION-12310-pre-rebase` → confirmed at `e3b3267`
2. **`.gitignore` conflict avoidance:** Renamed local untracked `.gitignore` to `.gitignore.local` before rebase
   (develop introduces a new `.gitignore` file — untracked local copy would cause "would be overwritten" error)
3. **Editor bypass configured:** Used `git -c core.editor=true rebase --continue` to skip vim for commit messages

### 11.3 Rebase Execution

```
git rebase origin/develop
```

**Result:** 36 commits replayed on top of `ce08d52` (origin/develop)

#### Conflicts Encountered — 18 pom.xml conflicts across 36 commits

All 18 conflicts occurred in the **root `pom.xml`** with an identical pattern:

| Conflict Region | Feature Branch Value | Develop Value | Resolution |
|-----------------|---------------------|---------------|------------|
| `<dependency.version>` | Incremental SNAPSHOT versions (`1.0.1-SNAPSHOT` → `1.0.23-SNAPSHOT`) | `1.R.01.022` | **Keep feature** (each commit's SNAPSHOT version) |
| `<utils.dependency.version>` | `1.R.01.003` | `1.R.01.004` | **Accept develop** (`1.R.01.004`) |

**Commits that had conflicts (18 of 36):**
Every commit that touched the `<properties>` section of root `pom.xml` (version bumps, dependency changes) triggered this same two-property conflict.

#### Special Case — Commit 359e29a (Jersey Vulnerability Fix)

This commit produced **nested conflict markers** (3 regions in one file) because it changed:
- Jackson versions (`2.18.x` → `2.19.2`)
- `dropwizard-metrics-datadog` property
- Overlapped with previous unresolved hunk state

**Resolution:** Kept Jackson at `2.19.2`, kept `dropwizard-metrics-datadog` at `4.0.16`, accepted develop's `utils.dependency.version=1.R.01.004`.

#### README.md — Auto-merged cleanly on every commit

Despite both branches modifying `README.md`, changes were in different sections:
- Develop: release entries near top (v1.R.01.020–022)
- Feature: changelog entries at bottom (v1.0.4–v1.0.18 SNAPSHOT)

Git auto-merged cleanly every time — no manual intervention needed.

### 11.4 Post-Rebase State

| Item | Value |
|------|-------|
| Feature branch HEAD (post-rebase) | `2f223af` (ION-12310: remove netty) |
| Commits ahead of origin/develop | **36** (same count, new hashes) |
| Remote HEAD (pre-push) | `e3b3267` (old — needs force-push) |
| Backup branch | `backup/feature-ION-12310-pre-rebase` → `e3b3267` (preserved) |

### 11.5 Build Verification — All Modules ✅

Ran `mvn clean verify` for all modules after rebase. **All builds passed with 0 failures.**

#### Test Statistics by Module

| Module | Phase | Tests | Time | Status |
|--------|-------|------:|------|--------|
| dropwizard-metrics-datadog (4.0.16) | surefire (unit) | 40 | 5.8s | ✅ PASS |
| cloud-sdk-api (1.0.23-SNAPSHOT) | surefire (unit) | 23 | 14.1s | ✅ PASS |
| dynamo-integration-test (1.0.23-SNAPSHOT) | surefire (unit) | 6 | 13.5s | ✅ PASS |
| cloud-sdk-aws (1.0.23-SNAPSHOT) | surefire (unit) | 877 | ~4m | ✅ PASS |
| cloud-sdk-aws (1.0.23-SNAPSHOT) | failsafe (integration) | 137 | ~30s | ✅ PASS |
| commons (1.0.23-SNAPSHOT) | surefire (unit) | 865 | ~37s | ✅ PASS |
| **TOTAL** | | **1,948** | | ✅ **ALL PASS** |

#### Build Commands Executed
```bash
mvn clean verify -pl cloud-sdk-api -am          # ✅ BUILD SUCCESS (14.8s)
mvn clean verify -pl cloud-sdk-aws -am          # ✅ BUILD SUCCESS (4:59 min) — includes cloud-sdk-api + dynamo-integration-test
mvn clean verify -pl commons -am                # ✅ BUILD SUCCESS (5:50 min) — includes all upstream modules
```

#### Pre-existing Warnings (not introduced by rebase)
- `version` contains expression but should be constant — all modules using `${dependency.version}`
- Duplicate dependency declarations in `commons/pom.xml` (junit-jupiter, mockito-junit-jupiter)
- Duplicate `dropwizard-core` in `cloud-sdk-aws/pom.xml`
- UdpTransport unchecked operations in dropwizard-metrics-datadog

### 11.6 Post-Rebase Checklist — Verified ✅

- [x] All 18 pom.xml conflicts resolved correctly
- [x] `dependency.version` = `1.0.23-SNAPSHOT`
- [x] `utils.dependency.version` = `1.R.01.004` (from develop)
- [x] `dropwizard.version` = `4.0.16`
- [x] `dropwizard-metrics-datadog` = `4.0.16`
- [x] All Jackson versions at `2.19.2`
- [x] `assertj.core.version` = `3.27.2`
- [x] `commons-text` = `1.15.0` (from develop)
- [x] `commons-lang3.version` = `3.18.0`
- [x] `.gitignore` present in repo (from develop)
- [x] `AuthenticationFilter.java` includes `/network/monitoring/status/current` (from develop)
- [x] `ServiceDefinition.java` includes `preppedUri` field (from develop)
- [x] `utils/local-elasticsearch/pom.xml` has logback `1.5.18` (from develop)
- [x] `README.md` auto-merged cleanly — both develop and feature entries present
- [x] `mvn clean verify` passes for ALL modules (1,948 tests, 0 failures)
- [x] Backup branch preserved at `backup/feature-ION-12310-pre-rebase` → `e3b3267`
- [x] **Force-push with `--force-with-lease`** — ✅ COMPLETED

### 11.7 Force-Push Confirmation

```
git push origin feature/ION-12310-commons-cloudsdk-refactoring --force-with-lease

Result:
 + e3b3267...2f223af feature/ION-12310-commons-cloudsdk-refactoring -> feature/ION-12310-commons-cloudsdk-refactoring (forced update)
```

Pull Request: https://git.dev.e2open.com/projects/INT/repos/mercury-services-commons/pull-requests/29

### 11.8 Cleanup

- Renamed `.gitignore.local` back / deleted after rebase (develop's `.gitignore` is now tracked)
- No stash was needed (working directory was clean pre-rebase)
