# Booking — commons 1.0.31-SNAPSHOT Checkout & AWS Startup Verification

**Date:** 2026-08-16
**Module:** `booking`
**Change:** `mercury.commons.version` `1.0.27-SNAPSHOT` → `1.0.31-SNAPSHOT`
**Session:** `ec3111711f2e4b66` (linked upstream: `7164c414d551444a` — ION-12310 cloud-sdk 1.0.31 defect fix)
**Agent model:** Claude Opus 5 (GitHub Copilot)

---

## 1. Summary

Booking was upgraded to the `commons` / `cloud-sdk-api` / `cloud-sdk-aws` **1.0.31-SNAPSHOT** line, rebuilt, and
booted against the **INT** configuration using live AWS **dev** credentials (account `081020446316`, `us-east-1`).

| Outcome | Result |
| --- | --- |
| Java source changes required in `booking` | **None** |
| POM changes required in `booking` | **One line** — the version bump only (after the upstream fix, §4.3) |
| Build | **BUILD SUCCESS**, 997 tests run, 0 failures, 0 errors, 9 skipped |
| Application boot | **PASS** |
| AWS clients started | SSM, DynamoDB, SQS, SNS, S3, SES, Elasticsearch (SigV4) — all **PASS** |
| Blocking defect found | **Yes** — split `logback` pair from `commons` 1.0.31; **fixed upstream and re-verified** |

The upstream constraint *"zero source changes required in mercury-services modules"* **holds**.

---

## 2. Changes applied to `booking/pom.xml`

**Final state — a one-line diff:**

```diff
-        <mercury.commons.version>1.0.27-SNAPSHOT</mercury.commons.version>
+        <mercury.commons.version>1.0.31-SNAPSHOT</mercury.commons.version>
```

A temporary `logback` `<dependencyManagement>` block was needed mid-exercise to work around the defect in
§3. **It has since been removed** — the fix was applied upstream in `mercury-services-commons` and both
`commons` and `dynamo-integration-test` were reinstalled (§4.3). Booking now needs **nothing** beyond the
version bump, so the *"zero changes required in consumers"* goal is fully met.

---

## 3. Blocker: split logback pair breaks application boot

### 3.1 Symptom

First boot attempt died before Jetty started:

```
java.lang.NoSuchMethodError: 'void ch.qos.logback.classic.LoggerContext.initCollisionMaps()'
    at ch.qos.logback.classic.LoggerContext.reset(LoggerContext.java:381)
    at io.dropwizard.logging.common.DefaultLoggingFactory.configureLoggers(DefaultLoggingFactory.java:222)
    at io.dropwizard.logging.common.DefaultLoggingFactory.configure(DefaultLoggingFactory.java:120)
    at io.dropwizard.core.cli.ConfiguredCommand.run(ConfiguredCommand.java:94)
    at com.inttra.mercury.config.ConfigProcessingServerCommand.run(ConfigProcessingServerCommand.java:23)
    at com.inttra.mercury.booking.BookingApplication.main(BookingApplication.java:325)
```

Resolved classpath: **`logback-core:1.5.38` + `logback-classic:1.5.18`**.

### 3.2 Root cause

`mvn -pl booking dependency:tree -Dverbose` traced two independent depth-2 declarations:

| Artifact | Declares | Note |
| --- | --- | --- |
| `commons:1.0.31-SNAPSHOT` | `<exclusion>` of `ch.qos.logback:logback-core` from `io.dropwizard:dropwizard-core:5.0.2`, **plus** a direct `ch.qos.logback:logback-core:1.5.38` (compile) | **NEW in 1.0.31.** `commons:1.0.27-SNAPSHOT` has *no* logback declarations at all |
| `dynamo-integration-test:1.0.31-SNAPSHOT` | `ch.qos.logback:logback-classic:1.5.18` | Pre-existing. Declared `test` scope in booking, but Maven's *nearest-wins version / widest-scope* rule promotes the **1.5.18 version** to the compile classpath |
| `dropwizard-core:5.0.2` | matched pair `logback-classic` + `logback-core` **1.5.33** | Both `omitted for conflict` — loses on depth |

At 1.0.27 both halves resolved to 1.5.18 (consistent → app booted).
At 1.0.31 `logback-core` jumps to 1.5.38 while `logback-classic` stays 1.5.18 → **split pair → hard boot failure**.

### 3.3 Bytecode evidence

`ContextBase.initCollisionMaps()` was **removed from `logback-core` between 1.5.18 and 1.5.33**:

```
$ javap -p ch.qos.logback.core.ContextBase        # from each logback-core jar
core 1.5.18 ->  protected void initCollisionMaps();   public void reset();
core 1.5.33 ->                                        public void reset();     # REMOVED
core 1.5.38 ->                                        public void reset();     # REMOVED
```

And only `logback-classic` **1.5.18** still calls it:

```
$ javap -c -p ch.qos.logback.classic.LoggerContext   # body of reset()

classic 1.5.18:                                   classic 1.5.33:
  invokespecial ContextBase.reset:()V               invokespecial ContextBase.reset:()V
  invokevirtual initEvaluatorMap:()V                invokevirtual initEvaluatorMap:()V
  invokevirtual initCollisionMaps:()V   <-- BOOM    (absent)
  invokevirtual Logger.recursiveReset:()V           invokevirtual Logger.recursiveReset:()V
  ...                                               ...
```

**`logback-classic:1.5.18` is the sole offender.** Any `logback-classic >= 1.5.33` is compatible with
`logback-core 1.5.38`.

### 3.4 Verification of the fix

```
$ mvn -pl booking dependency:tree | grep logback
[INFO] |  \- ch.qos.logback:logback-core:jar:1.5.38:compile
[INFO] |  +- ch.qos.logback:logback-classic:jar:1.5.38:compile
```

### 3.5 Residual (non-fatal)

One WARN at boot, emitted once, access logging works normally:

```
|-WARN in LogbackAccessRequestLog - For logback-core, expected version 1.5.32 but found 1.5.38
```

Dropwizard's `logback-access-common` / `logback-access-jetty12` 2.0.12 are compiled against logback-core 1.5.32.

---

## 4. Answer: is a `dynamo-integration-test` fix enough to spare every consumer?

**Yes.** Bumping `logback-classic` in `dynamo-integration-test` from **1.5.18 → 1.5.38** removes the need for
*any* consumer-side change. Both consumer shapes are covered:

| Consumer shape | `logback-classic` source | Resolved pair after upstream bump | Boots? |
| --- | --- | --- | --- |
| **With** `dynamo-integration-test` (booking, network, auth, registration, booking-bridge, webbl, …) | `dynamo-integration-test` at depth 2 wins | classic **1.5.38** + core **1.5.38** | ✅ exact match |
| **Without** `dynamo-integration-test` | `dropwizard-core:5.0.2` supplies classic **1.5.33** | classic **1.5.33** + core **1.5.38** | ✅ — 1.5.33 no longer calls `initCollisionMaps()` (see §3.3) |

So the *only* thing that has to change upstream is that one version, and the booking `<dependencyManagement>`
logback block in §2 can then be **deleted**.

### Recommended upstream fix (preferred form)

Bumping `dynamo-integration-test` is *sufficient*, but it leaves the pairing implicit and free to drift again.
The more robust fix is to make the pair explicit and unbreakable in the **`commons` parent POM**:

```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>ch.qos.logback</groupId>
            <artifactId>logback-classic</artifactId>
            <version>${logback.version}</version>
        </dependency>
        <dependency>
            <groupId>ch.qos.logback</groupId>
            <artifactId>logback-core</artifactId>
            <version>${logback.version}</version>
        </dependency>
    </dependencies>
</dependencyManagement>
```

`dependencyManagement` in the parent wins over transitive depth entirely, so no consumer can ever receive a
split pair again regardless of which test artifacts they pull in. Doing **both** (bump
`dynamo-integration-test` *and* add the managed pair) is the recommended action.

> Version choice note: `1.5.32` would additionally silence the §3.5 `logback-access` WARN, but `1.5.38` was kept
> here to preserve the security intent behind the original `commons` pin.

### 4.3 Upstream fix — APPLIED and re-verified (2026-08-16)

The fix landed in `mercury-services-commons` and both artifacts were reinstalled:

| Artifact | Change |
| --- | --- |
| `commons-1.0.31-SNAPSHOT` | now excludes **both** `logback-core` *and* `logback-classic` from `dropwizard-core:5.0.2`, and declares **both** at `1.5.38` |
| `dynamo-integration-test-1.0.31-SNAPSHOT` | `logback-classic` `1.5.18` → **`1.5.38`**, plus `logback-core` `1.5.38` |

Re-verification with the booking workaround **removed**:

```
$ mvn -pl booking dependency:tree | grep 'logback:'
[INFO] |  +- ch.qos.logback:logback-core:jar:1.5.38:compile
[INFO] |  \- ch.qos.logback:logback-classic:jar:1.5.38:compile

$ mvn -pl booking clean package
[WARNING] Tests run: 997, Failures: 0, Errors: 0, Skipped: 9
[INFO] BUILD SUCCESS

$ java -jar booking/target/booking-1.0.jar server booking/conf/int/config.yaml
... Booking life cycle started        # 0 ERROR lines, no NoSuchMethodError
```

`booking/pom.xml` is back to a **single-line diff**. The only residual is the harmless §3.5 WARN.

### 4.4 Blast radius (now resolved)

Every module that upgrades to commons 1.0.31 would have hit the same boot failure:
`auth`, `booking-bridge`, `db-migration`, `registration`, `tx-tracking`, `network`, `rates`,
`value-added-service`, `visibility`, `webbl`, `bill-of-lading-v2`, `watermill-publisher`.
With §4.3 in place they each need **only** the `mercury.commons.version` bump — no logback workaround.

---

## 5. Build result

```sh
mvn -pl booking clean package
```

```
[WARNING] Tests run: 998, Failures: 0, Errors: 0, Skipped: 10, Time elapsed: 46.25 s -- in TestSuite
[WARNING] Tests run: 997, Failures: 0, Errors: 0, Skipped: 9
[INFO] BUILD SUCCESS
```

Shaded jar `booking/target/booking-1.0.jar` confirmed to contain `commons-1.0.31-SNAPSHOT.jar`,
`cloud-sdk-api-1.0.31-SNAPSHOT.jar`, `cloud-sdk-aws-1.0.31-SNAPSHOT.jar`.

---

## 6. Application boot & AWS service startup verification

```sh
aws sso login
java -jar booking/target/booking-1.0.jar server booking/conf/int/config.yaml
```

Identity used:
`arn:aws:sts::081020446316:assumed-role/AWSReservedSSO_INTTRA-Dev-Engg_.../arijit.kundu@E2OPEN.onmicrosoft.com`,
region `us-east-1`, resolved through `DefaultCredentialsProvider` (SSO profile) and
`DefaultAwsRegionProviderChain`.

Result: **`Booking life cycle started`**, **0 `ERROR` lines** in the boot log, app listening on `8080`
(admin `8081`).

### 6.1 Per-service evidence

| AWS service | cloud-sdk entry point | Boot-log evidence |
| --- | --- | --- |
| **SSM / Parameter Store** | `cloudsdk.paramstore.impl.SsmCloudParameterStore` | `${awsps:...}` placeholders in `config.yaml` resolved during `ConfigProcessingServerCommand`. Proven live by negative test (§6.2) |
| **DynamoDB** | `BaseDynamoDbConfig` → `DynamoRepositoryFactory` | `Resolved AWS region from DefaultAwsRegionProviderChain: us-east-1`; `Using DefaultCredentialsProvider for DynamoDbClientConfig`; all **7** repository objects bound (§6.3 — no tables created, see §6.5) |
| **SQS** | `MessagingClientFactory.createDefaultStringClient()` | `SQS MessagingClient created successfully`; `SQSListener ... starting.` then polled the live INT inbound queue for **>2 min with zero errors** |
| **SNS** | `NotificationClientFactory.createDefaultClient(topicArn)` | `SNS NotificationService created successfully for topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` |
| **S3** | `StorageClientFactory.createDefaultS3Client()` | `Creating S3Client with defaults`; `S3StorageClient: Resolved AWS credentials using provider: DefaultCredentialsProvider(...)`; `Using Access Key ID: ASIARFXJR4ZW...`; `S3 StorageClient created successfully`. Bucket `inttra-int-s3-bookingdetail-s3archive` |
| **SES / email** | `EmailClientFactory.createDefaultSesClient(...)` | `Creating SES client with default configuration and List of template files`; all **6** templates cached: `RequestAmend`, `Cancel`, `DeclineReplace`, `InternalError`, `PendingConfirm`, `ValidationError` |
| **Elasticsearch (SigV4)** | `cloudsdk.aws.module.JestModule` | `Created client with endpoint https://search-inttra-int-es-bk-search-*.us-east-1.es.amazonaws.com, signer ASIARFXJR4ZW..., region us-east-1` |

### 6.2 SSM lookup proven live (negative test)

> **Important operational finding:** the `check` command does **not** perform `${awsps:...}` substitution — a
> deliberately bogus parameter path still reported `Configuration is OK`. Only the `server` command
> (`ConfigProcessingServerCommand`) runs Parameter Store resolution. **Do not use `check` to validate `awsps`
> config.**

Pointing one `awsps` key at a non-existent parameter and running `server` produced:

```
WARN  com.inttra.mercury.cloudsdk.paramstore.impl.SsmCloudParameterStore:
      Parameter not found: /inttra/int/booking/config/DOES_NOT_EXIST_XYZ
java.lang.RuntimeException: No value found for parameter: /inttra/int/booking/config/DOES_NOT_EXIST_XYZ
```

confirming Parameter Store is contacted for real, and that the genuine INT config resolved successfully.

### 6.3 DynamoDB repository objects bound at startup

> **Terminology — no tables were created.** The boot log line
> `Creating <Entity> composite-key repository for table: <name>` is emitted by
> [`BookingDynamoModule`](../src/main/java/com/inttra/mercury/booking/config/BookingDynamoModule.java) and refers to
> constructing an **in-JVM `DatabaseRepository` object** (a Guice singleton wrapping a `DynamoDbEnhancedClient`
> table handle). It is **not** a DynamoDB `CreateTable` call. The INT tables already existed and were untouched.
> See §6.5 for the evidence.

| Table (`tablePrefix` + `@Table` name) | Key style | Bound repository |
| --- | --- | --- |
| `inttra_int_booking_BookingDetail` | composite | `DatabaseRepository<BookingDetail, DefaultCompositeKey<String,String>>` |
| `inttra_int_booking_UniqueId` | partition | `DatabaseRepository<UniqueId, DefaultPartitionKey<K>>` |
| `inttra_int_booking_SequenceId` | partition | `DatabaseRepository<SequenceId, DefaultPartitionKey<K>>` |
| `inttra_int_booking_RapidReservation` | composite | `DatabaseRepository<RapidReservation, DefaultCompositeKey<String,String>>` |
| `inttra_int_booking_SpotRatesDetail` | partition | `DatabaseRepository<SpotRatesDetail, DefaultPartitionKey<K>>` |
| `inttra_int_booking_SpotRatesToInttraRefDetail` | partition | `DatabaseRepository<SpotRatesToInttraRefDetail, DefaultPartitionKey<K>>` |
| `inttra_int_booking_Template` | composite | two repositories — `Template` and `TemplateSummary` share one physical table |

### 6.4 What actually happens per repository

```java
// BookingDynamoModule (booking) — the log line is printed BEFORE any SDK call
final String tableName = clientConfig.getTablePrefix() + tableAnnotation.name();
log.info("Creating {} composite-key repository for table: {}", domainType.getSimpleName(), tableName);
return DynamoRepositoryFactory.createEnhancedRepository(clientConfig, tableName, domainType, repositoryConfig);
```

`DynamoRepositoryFactory.createEnhancedRepository` does exactly four things, all in-process:

1. `validateConfig(clientConfig)`
2. `createDynamoDbClient(clientConfig)` — builds a `DynamoDbClient` (lazy; opens no connection)
3. `DynamoDbEnhancedClient.builder().dynamoDbClient(...).build()`
4. `new EnhancedDynamoRepository(client, enhancedClient, tableName, domainType, config)`

The table name is just a **string handed to the enhanced client** so subsequent `save`/`findById`/`query`
calls know where to go. Nothing is sent to AWS until the application actually reads or writes.

### 6.5 Evidence that no table was created or modified

**1. The factory literally cannot create a table.** Bytecode scan of `cloud-sdk-aws-1.0.31-SNAPSHOT.jar`:

```sh
$ javap -c -p com.inttra.mercury.cloudsdk.database.factory.DynamoRepositoryFactory | grep -ic 'createTable|describeTable'
0

$ grep -rl "createTable" --include=*.class .
com.inttra.mercury.cloudsdk.database.command.DynamoDbAdminCommand
com.inttra.mercury.cloudsdk.database.util.DynamoDbAdminUtil
```

`DynamoRepositoryFactory` has **zero** references to `CreateTable` or `DescribeTable`. Table creation lives
only in `DynamoDbAdminCommand.createTableWithGsisIfNotExists(...)`, which is reached exclusively through the
opt-in **`dynamo-create`** CLI command — a *different* command from `server`:

```
usage: java -jar booking-1.0.jar {server,check,dynamo-create,create-index,delete-index}
                                  ^^^^^^                    ^^^^^^^^^^^^
                                  used here                 creates tables — NOT run
```

`BookingDynamoDbAdminCommand` is merely *registered* in the bootstrap (hence the
`initialized with 7 entity classes` line on every start-up, including `--help`); registering a command does
not execute it.

**2. The INT tables long predate this exercise** (`aws dynamodb describe-table`):

| Table | CreationDateTime | ItemCount |
| --- | --- | --- |
| `inttra_int_booking_BookingDetail` | 2018-06-07 | 588 |
| `inttra_int_booking_UniqueId` | 2018-06-07 | 1 |
| `inttra_int_booking_SequenceId` | 2019-02-21 | 1 |
| `inttra_int_booking_RapidReservation` | 2018-08-24 | 10 |
| `inttra_int_booking_SpotRatesDetail` | 2019-10-04 | 0 |
| `inttra_int_booking_SpotRatesToInttraRefDetail` | 2019-10-15 | 11 |
| `inttra_int_booking_Template` | 2018-10-03 | 18 |

All created in 2018–2019, unchanged by the 2026-08-16 boots, with their pre-existing data intact.

**3. Repository binding is offline.** Because step 2 above is lazy, the DynamoDB module never contacts AWS
during wiring. Confirmed indirectly by a bogus-credentials boot: the run died at the **first genuine** AWS
call — SSM — long before the Dynamo module ran:

```
software.amazon.awssdk.services.ssm.model.SsmException:
    The security token included in the request is invalid. (Service: Ssm, Status Code: 400)
```

### 6.6 HTTP checks

| Endpoint | Result |
| --- | --- |
| `GET :8080/booking/services/ping` | `200` |
| `GET :8080/booking/services/version` | `200` |
| `GET :8081/admin/healthcheck` | `200` — `Basic functionality` healthy, `deadlocks` healthy |
| `GET :8080/booking/search/{ref}` | `401 Unauthorized` — auth required, expected, not an AWS fault |

---

## 7. OWASP dependency-check

### 7.1 Reusable runner

A module-agnostic wrapper now lives at the repo root: **`dependency-check.sh`**.

```sh
./dependency-check.sh booking                        # full scan, refreshes NVD
./dependency-check.sh booking --no-update            # fast re-scan off the local NVD cache
./dependency-check.sh network/server -f HTML         # nested module, HTML only
./dependency-check.sh booking --fail-on-cvss 8       # gate a build
./dependency-check.sh --help
```

What it does for you:

| Behaviour | Detail |
| --- | --- |
| Artifact discovery | Auto-detects the shaded jar(s) in `<module>/target`, skipping `original-*`, `*-sources`, `*-javadoc`, `*-tests` |
| Suppressions | Nearest wins — `<module>/suppressions.xml`, falling back to the repo-root `suppressions.xml` |
| Output dir | Defaults to `<repo-root>/owasp-reports/<module>` and is **created if missing**. Deliberately **outside `target/`** — `mvn clean` deletes `target/` and silently destroys the reports (this bit us once). A bare `--out owasp` also fails with `Invalid 'out' argument: path does not exist`, since dependency-check will not `mkdir` |
| Nested modules | `network/server`, `visibility/visibility-inbound`, … all work |
| API key handling | `NVD_API_KEY` is written to a `chmod 600` temp property file (`nvd.api.key`) and passed with `--propertyfile`, so **the key never appears in the process list**; the file is removed on exit via `trap` |
| Windows | Converts paths with `cygpath -w` and sets `MSYS2_ARG_CONV_EXCL` so Git Bash doesn't mangle args for `dependency-check.bat` |
| Summary | Prints dependency-check's own severity roll-up (matching the HTML), plus an `FYI` list of CVEs whose CVSS v3 rating is harsher than the tool's verdict |

Prerequisites: `dependency-check` on `PATH`, `export NVD_API_KEY=...`, and the module built
(`mvn -pl <module> clean package`).

### 7.2 Result for booking @ 1.0.31-SNAPSHOT

Scanned `booking-1.0.jar` + `booking-lambdas-1.0.jar`. Reports in `owasp-reports/booking/`
(HTML, XML, JSON, CSV, SARIF, JUNIT, GITLAB, Jenkins). Exit code `0`.

```
SUMMARY  booking  -  55 finding(s) across 9 vulnerable dependencies
  MEDIUM    55
No CRITICAL or HIGH findings.
```

**No CRITICAL or HIGH findings.** All 55 are MEDIUM.

Notable MEDIUM components: `log4j-core`/`log4j-api:2.23.1`, `swagger-ui:5.17.14` (~34 of the 55,
mostly XSS in the bundled JS), `commons-configuration:1.8` (CVE-2025-46392),
`jackson-databind:2.21.4` (CVE-2026-54515), `commons-lang3:3.13.0` (CVE-2025-48924),
`httpclient5:5.4.4` (CVE-2026-64607), `metrics-httpclient5:4.2.39` (CVE-2020-13956, CVE-2014-3577).

None are introduced by the 1.0.31 bump — they are pre-existing `log4j` / `swagger-ui` /
Apache Commons versions in the booking POM.

#### Severity caveat — read the tool's verdict, not raw CVSS v3

Four CVEs carry a **CVSS v3 HIGH** rating but dependency-check reports them as **MEDIUM**:

| CVE | CVSS v3 | dependency-check |
| --- | --- | --- |
| CVE-2026-34478 | HIGH 7.5 | MEDIUM |
| CVE-2026-34479 | HIGH 7.5 | MEDIUM |
| CVE-2026-34480 | HIGH 7.5 | MEDIUM |
| CVE-2026-65898 | HIGH 7.2 | MEDIUM |

dependency-check reconciles CVSS v2/v3/v4 and prefers the newer **v4** score when the CNA published
one. For CVE-2026-34478 the v4 vector is
`AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:L/SA:N` — essentially no impact on the vulnerable
system — hence MEDIUM. The HTML report shows MEDIUM; the JSON `severity` field is the authoritative
value, **not** `cvssv3.baseSeverity`. The runner script prints the tool's verdict and lists these four
separately under an `FYI` heading so the harsher v3 rating is still visible without inflating the counts.

### 7.3 Stale suppression rules

The scan reported two rules in `booking/suppressions.xml` with **zero matches**:

1. `pkg:maven/ch.qos.logback/logback-core@1.5.18` → `CVE-2025-11226`
   **Now obsolete** — this is exactly the CVE the `commons` 1.0.31 `logback-core` 1.5.38 pin fixes (§3.2),
   so the suppressed version is no longer on the classpath. **Safe to delete.**
2. `^pkg:javascript/handlebars@.*$` → `CVE-2026-.*`

Cleaning these up keeps the suppression file honest. Item 1 also confirms the *intent* behind the
upstream `logback-core` pin, which is why §4 recommends aligning **up** to 1.5.38 rather than down to 1.5.18.

### 7.4 Scan caveat

`Sonatype OSS Index Analyzer disabled due to missing credentials` — OSS Index now requires a token, so
that data source contributed nothing. Findings above come from NVD + RetireJS only.

---


## 8. Follow-ups

1. ~~Upstream `mercury-services-commons` logback fix~~ — **DONE** (§4.3).
2. ~~Remove the `logback` workaround from `booking/pom.xml`~~ — **DONE**; diff is now the version bump only.
3. Consider aligning on `1.5.32` if the `logback-access` WARN (§3.5) is deemed worth removing.
4. Roll the other commons consumers onto 1.0.31 — they now need **only** the version bump (§4).
5. Remove the two stale suppression rules from `booking/suppressions.xml` (§7.3).
6. Plan a `log4j` 2.23.1 and `swagger-ui` 5.17.14 refresh. Nothing is CRITICAL/HIGH per
   dependency-check (§7.2), so this is housekeeping rather than urgent, but four log4j/swagger CVEs
   do carry a CVSS v3 HIGH rating and are worth a deliberate decision. Independent of the 1.0.31 upgrade.

---

## 9. Note on this document's location

`.gitignore:110` contains `**/docs/`, so **every module `docs/` folder is untracked**, including this file.
If these upgrade/verification records are meant to be reviewable in PRs, the ignore rule needs a negation
such as:

```gitignore
**/docs/
!**/docs/*.md
```

Flagging rather than changing it, since the rule is repo-wide and pre-existing.

