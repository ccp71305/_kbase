# Rates — OWASP Dependency-Check Fix + AWS SDK 2.x (cloud-sdk) Upgrade

**Jira:** ION-16110
**Module:** `rates`
**Branch:** `feature/ION-16110-rates-owasp-aws-upgrade` (created from the latest `develop` @ `8dad1d555c`)
**Model:** Claude Opus 4.8 (1M context)
**Date:** 2026-07-28
**Reference design:** `rates/docs/2026-06-30-rates-aws2x-DESIGN-claude.md`
**Reference modules:** `booking` (byte-for-byte `SpotRatesDetail` twin — primary), `network`/`auth`/`visibility`

> This document is internal reference only. Code comments and commit messages do **not** cite it (per policy).

---

## 1. Summary

Two backward-compatible changes were delivered on `rates`, as **two separate commits** (the OWASP fix has no
compile-time dependency on the AWS migration, so the preferred split was possible):

| Commit | Hash | Scope |
|--------|------|-------|
| OWASP fix | `1ee54add12` | Bump `commons` → `1.0.28-SNAPSHOT`, pin Jackson to `2.21.4` (jackson-bom import), and let `jackson-dataformat-xml` be BOM-managed (dropped its hard-coded `2.19.2`). Clears all 6 HIGH CVEs. No functional code change. |
| AWS SDK 2.x upgrade | `598e382de2` | Migrate the spot-rates DynamoDB persistence from AWS SDK v1 (`dynamo-client`/`DynamoDBMapper`) to the cloud-sdk enhanced client (AWS SDK 2.x), mirroring the booking `SpotRatesDetail` twin. |

These are **two separate commits** — the OWASP fix has no compile-time dependency on the AWS migration, so the
preferred split (per the goal / Constraint 3) was possible. Both messages contain `ION-16110`; the branch sits on top of
the latest develop (`8dad1d555c`). (History was tidied once via `--force-with-lease` to fold PR-review fixes into the
two commits — see the note at the end of §8.)

- **DynamoDB is the only AWS service in scope** — no S3/SQS/SNS/SES/Kinesis exists in `rates`.
- All wire/disk formats stay compatible with the shared `*_booking_SpotRatesDetail` table already migrated by booking.
- `mvn -f rates/pom.xml clean verify` → **BUILD SUCCESS**: **421 unit tests + 9 DynamoDB-Local integration tests, 0 failures / 0 errors**.
- No rebase was required (branch created fresh from the latest develop; no new `rates/` commits landed after branching).

---

## 2. Rebase

Not required. `feature/ION-16110-rates-owasp-aws-upgrade` did not previously exist, so it was created from the
just-pulled latest develop (`8dad1d555c`). `git log --oneline HEAD..origin/develop -- rates/` returned nothing after
branching, so there were no incoming functional changes to reconcile.

---

## 3. OWASP dependency-check (pre/post CVE delta)

Tool: `dependency-check` (installed at `C:\dependency-check\...`), scanning the shaded jar with the module
suppression file and the NVD API key.

```powershell
mvn package -pl rates -DskipTests -am                       # baseline jar (develop)
dependency-check --project rates --scan .\target\rates-1.0.jar --out <tmp> `
    --format HTML --format JSON --suppression .\suppressions.xml --nvdApiKey $env:NVD_API_KEY
```

| Severity | Baseline (develop) | Post-fix | Delta |
|----------|--------------------|----------|-------|
| HIGH     | **6**              | **0**    | −6    |
| MEDIUM   | 49                 | 42       | −7    |
| low      | 8                  | 8        | 0     |

**HIGH CVEs cleared (all 6):**

| CVE | Component (baseline) | Fixed by |
|-----|----------------------|----------|
| CVE-2026-54512 | jackson-databind 2.21.0 | Jackson pin → 2.21.4 (jackson-bom) |
| CVE-2026-54513 | jackson-databind 2.21.0 | Jackson pin → 2.21.4 (jackson-bom) |
| CVE-2026-54399 | httpcore5 5.4 / httpcore5-h2 5.3.4 | commons 1.0.28-SNAPSHOT (patched httpcore5) |
| CVE-2026-54428 | httpcore5 5.4 / httpcore5-h2 5.3.4 | commons 1.0.28-SNAPSHOT (patched httpcore5) |

Both scans copied to:
- `C:\temp\latest-dep-chk-reports\rates\baseline\dependency-check-report.{html,json}`
- `C:\temp\latest-dep-chk-reports\rates\post\dependency-check-report.{html,json}`

Remaining MEDIUM/low findings are pre-existing transitive advisories with no available HIGH-severity fix in scope for
this ticket; they are unchanged or reduced vs baseline.

---

## 4. Design plan

Implemented per `2026-06-30-rates-aws2x-DESIGN-claude.md`, adjusted only where the goal overrode the design
(commons `1.0.28-SNAPSHOT`, not `1.0.26`). Target state:

- Replace `dynamo-client` + prod `aws-java-sdk-dynamodb` with `cloud-sdk-api` + `cloud-sdk-aws`; add
  `dynamo-integration-test` (+ test-scoped `aws-java-sdk-dynamodb` for DynamoDB Local).
- `SpotRatesDetail`: v1 ORM → `@DynamoDbBean`/`@Table` enhanced annotations + `@DynamoDbConvertedBy` converters,
  `@DynamoDbPartitionKey` `spotRateKey`, `@GsiConfig`/`@DynamoDbSecondaryPartitionKey` `SPOT_RATE_ID_INDEX`
  (KEYS_ONLY), `@TTL` `expiresOn`.
- Converters ported into `rates` (no dependency on booking): `SpotRatesAttributeConverter` (S, `className:json` /
  `size|className:base64(gzip)` above 300 KB), `AuditAttributeConverter` + `LegacyMapConverter` (native Map),
  tolerant `OffsetDateTimeTypeConverter`; `expiresOn` via the cloud-sdk built-in `DateEpochSecondAttributeConverter`.
- `SpotRatesDao`: injected `DatabaseRepository<SpotRatesDetail, DefaultPartitionKey<String>>` + `DefaultQuerySpec`,
  preserving the GSI→hash-key two-step and the existing public API.
- `SpotRatesModule`: cloud-sdk providers (`DynamoDbClientConfig` from `BaseDynamoDbConfig.toClientConfigBuilder()`,
  `SpotRatesDao` from `DynamoRepositoryFactory.createEnhancedRepository`). `SpotRateConfig.dynamoDbConfig` →
  `BaseDynamoDbConfig`.
- Drop stray v1 annotations (`@DynamoDBDocument`, `@DynamoDBTypeConverted*`) from `Audit` and the non-persisted
  `ContainerType` REST DTO so no `com.amazonaws` remains on the prod classpath.

**Backward-compatibility guarantees (proven by tests):** the `spotRates` JSON string (incl. GZIP-above-300 KB branch),
the `audit` native Map with ISO_DATE_TIME (`Z`) timestamps, and the `expiresOn` epoch-seconds (`N`, ms dropped) all
reproduce the legacy 1.x / booking encodings; reads tolerate legacy `+0000`/`+00:00`/`Z`/date-only timestamps and a
foreign (booking) class prefix.

---

## 5. VS Code run configs

Added **Run Rates Service** and **Debug Rates Service** launch configurations to `.vscode/launch.json`
(`mainClass=com.inttra.mercury.rates.RatesApplication`, `args=server .../rates/conf/int/config.yaml`), mirroring the
existing booking/value-added-service entries. `.vscode/launch.json` is git-ignored, so these remain developer-local
and are not part of the commit.

---

## 6. Develop boot-check (FLAGGED — root cause confirmed as an INT platform outage)

`java -jar rates/target/rates-1.0.jar server rates/conf/int/config.yaml` on the latest develop:

- The app **compiles** (BUILD SUCCESS) and **Dropwizard initializes** (Jersey `/` and admin `/admin` handlers register,
  and the v1 `DynamoSupport` mapper initializes cleanly with prefix `inttra_int_booking_`).
- Full boot then fails during Guice provisioning: `ContainerTypeClient` cache is **eagerly warmed** at startup by the
  `ISOContainerToTmContainer` `@Singleton` constructor → `NetworkClient` → `AuthClient.newToken()` → the INT gateway
  returns **HTTP 502** (3 retries) → `WebApplicationException: Could not retrieve a new token` → essential container
  exits with code 1. Reproduced twice locally.

**Root cause (verified against the live environment):** the failure is an **INT platform/infrastructure outage**, not a
code defect and not specific to the local machine:

- The **deployed develop artifact** `Rates-26.06.003.jar` on INT ECS `Rates-dev` fails **identically** — CloudWatch
  (`inttra-int-lg-rates`) shows the same sequence ending in `AuthClient.newToken (AuthClient.java:56)` → `HTTP 502` from
  `ContainerTypeClient$3.load`, and the task stops with `EssentialContainerExited`, exitCode 1. So INT's own deployment
  is in the same state as the local boot-check.
- Direct probing shows the **entire INT `api-alpha.inttra.com` gateway is down** — HTTP 502 on `/auth`, `/auth/validate`
  **and** `/network/containertype` (not auth-specific). By contrast QA `api-beta.inttra.com` returns 400/401 (up), and
  CVT `api-test` / PROD `api` return 400 (up).

**Decision (endorsed by the user):** proceeding past the boot-check was the correct call. The boot failure is an INT
gateway outage that also takes down the deployed develop build, is orthogonal to the DynamoDB migration (the DynamoDB
layer initialized fine before the 502), and cannot be resolved from this change. The local correctness gate is
`mvn clean verify` (421 unit + 9 DynamoDB-Local IT, all green); runtime boot verification belongs in an environment
whose gateway is healthy (e.g. QA — see §9, where the rates service is running at steady state).

### Why does this crash `rates` at boot when `booking`/`network` stay up on the same outage?

Both `rates` and `booking` INT point at the **same** `api-alpha.inttra.com` gateway (booking's `securityResources`
and outbound `auth` service both use `api-alpha`). The difference is **when** the gateway is called:

| | `rates` | `booking` / `network` |
|---|---------|------------------------|
| Auth/downstream call timing | **Eager at startup** — `ISOContainerToTmContainer` (`@Singleton`) constructor synchronously warms the container-type cache (`getIsoContainerCodesFromMap` → `ContainerTypeClient.getContainerGroupType` per ISO code → `NetworkClient` → `AuthClient`). | **Lazy** — inbound token validation via commons `securityResources` runs per-request; their Guava `ServiceCache`/`CacheLoader` caches also load on first `get`, not at boot. |
| Effect of an `api-alpha` 502 | Constructor throws → Guice provisioning fails → **container exits at boot**. | Boot **succeeds**; only requests that need the down gateway return errors until it recovers. |

`rates`' own `ServiceCache` is a lazy Guava `LoadingCache`; the boot-fragility comes solely from the eager warm-up in
the `ISOContainerToTmContainer` constructor (an eager-cache-warm anti-pattern), not from the cache itself. This is the
one behavioural difference that makes `rates` uniquely sensitive to an INT gateway outage at startup.

---

## 7. Implementation

### pom.xml
- `mercury.commons.version` `1.R.01.023` → `1.0.28-SNAPSHOT`; removed `mercury.dynamodbclient.version` and
  `dynamodb-local.version`.
- Removed `dynamo-client` and prod `aws-java-sdk-dynamodb 1.12.655`; added `cloud-sdk-api`, `cloud-sdk-aws`
  (`${mercury.commons.version}`), test-scoped `dynamo-integration-test` and `aws-java-sdk-dynamodb 1.12.721` (DynamoDB
  Local only).
- `dependencyManagement`: import `jackson-bom 2.21.4` (OWASP) and pin `com.google.guava:guava 33.5.0-jre`.
- `jackson-dataformat-xml` is left **BOM-managed** — its hard-coded `2.19.2` was dropped (in the OWASP commit) so the
  patched 2.21.4 line actually applies; a direct `<version>` would otherwise override the BOM and keep the old module.
  (No `lombok.version` override is used — the parent's annotation-processor `1.18.30` builds cleanly against the
  `1.18.32` `commons` puts on the classpath; see §8 issue 1.)
- `maven-dependency-plugin` `copy-native-libs` (sqlite native libs → `target/native-libs`) and `maven-failsafe-plugin`
  wired with `<groups>integration</groups>`, `**/*IT.java`, `sqlite4java.library.path`, and the
  `integration-test`+`verify` execution.

### Java (main)
| Class | Change |
|-------|--------|
| `spot/model/canonical/SpotRatesDetail` | v1 ORM → `@DynamoDbBean`/`@Table` + enhanced key/GSI/TTL/converter annotations; deprecated `getHashKey`/`setHashKey` retained. |
| `spot/dynamodb/SpotRatesAttributeConverter` | **new** — v2 `AttributeConverter<SpotRates>` (S; `className:json` / gzip-above-300 KB); `transformTo` reads into `rates.SpotRates` ignoring the stored class prefix (robust cross-module reads). |
| `spot/dynamodb/AuditAttributeConverter` + `LegacyMapConverter` | **new** — v2 `AttributeConverter<Audit>` (native Map, ISO_DATE_TIME `Z`), + Map/List ↔ AttributeValue helper. |
| `spot/dynamodb/OffsetDateTimeTypeConverter` | rewritten to the v2 form (Jackson `StdDeserializer`, tolerant of `Z`/`+00:00`/`+0000`/date-only). |
| `spot/dynamodb/SpotRatesDao` | `extends DynamoDBCrudRepository` → injected `DatabaseRepository` + `DefaultQuerySpec`; `findByOfferKey`/`findBySpotRateId`/`saveSpotRates(4-arg)`/`save` preserved. |
| `spot/module/SpotRatesModule` | cloud-sdk providers (`DynamoDbClientConfig`, `SpotRatesDao`); kept the `@Named ExternalServiceDefinition` bindings. |
| `config/SpotRateConfig` | `dynamoDbConfig` type `DynamoDbConfig` → `BaseDynamoDbConfig`. |
| `spot/model/Audit` | dropped `@DynamoDBDocument`/`@DynamoDBTypeConverted`; kept `@JsonFormat` (REST). |
| `networkservices/containertype/model/ContainerType` | dropped stray `@DynamoDBDocument`/`@DynamoDBTypeConvertedEnum`. |
| `common/GZip` | **bug fix** — `compress()` returned `toByteArray()` inside the try-with-resources before the `GZIPOutputStream` closed → truncated gzip (any >300 KB spotRates was corrupt/unreadable). Now closes before reading. |
| Removed | `DynamoSupport`, `DateToEpochSecond`, `SpotRatesConverter` (replaced by cloud-sdk / new converters). |

`config.yaml` files were unchanged: the existing `dynamoDbConfig` keys (`readCapacityUnits`, `writeCapacityUnits`,
`environment`, `sseEnabled`) map directly onto `BaseDynamoDbConfig` (identical to booking).

---

## 8. Tests & coverage

`mvn -f rates/pom.xml clean verify` → **BUILD SUCCESS**.

| Runner | Type | Tests | Failures | Errors | Suites |
|--------|------|-------|----------|--------|--------|
| JUnit 5 (surefire) | unit | **421** | 0 | 0 | 45 |
| JUnit 5 (failsafe) | integration (DynamoDB Local) | **9** | 0 | 0 | 6 |

Only one test runner (JUnit 5) is in play; no TestNG.

**Passing test commands:**
- `mvn -f rates/pom.xml clean test` — unit only (421).
- `mvn -f rates/pom.xml clean verify` — unit + DynamoDB-Local integration (421 + 9).
- `mvn -pl rates -Pmercury-commons,sonar clean verify -Dsonar.skip=true` — same tests + JaCoCo (UT `jacoco-ut.exec`,
  IT `jacoco-it.exec`; report `rates/target/site/jacoco-aggregate/`).

**New tests:** `SpotRatesDaoTest`, `SpotRatesAttributeConverterTest`, `AuditAttributeConverterTest`,
`LegacyMapConverterTest`, `OffsetDateTimeTypeConverterTest`, `SpotRatesModuleTest` (offline dummy-credentials
technique via `aws.accessKeyId`/`aws.secretAccessKey`/`aws.region` system props), and `SpotRatesDaoIT` (DynamoDB Local
— save/find round-trip, GSI two-step, TTL epoch-seconds `N`, gzip>300 KB fidelity, **null-attribute omission**).

**JaCoCo coverage (new classes, instruction):** `SpotRatesDao` 100%, `LegacyMapConverter` 100%,
`AuditAttributeConverter` 100%, `SpotRatesAttributeConverter` 96%, `OffsetDateTimeTypeConverter` 97%,
`SpotRatesModule` 95%. Residual uncovered lines are unreachable defensive guards (e.g. the `@Table`-missing
`IllegalStateException`, which cannot occur because `SpotRatesDetail` is always annotated) and serialization
catch-blocks that valid inputs cannot trigger.

### Issues found and fixed during the migration
1. **Lombok processor/classpath skew (flaky testCompile).** `commons` brings `lombok 1.18.32` (compile) while the
   parent pins the annotation processor to `1.18.30`, which *intermittently* produced `@Builder` "bad class file /
   package does not exist" during testCompile from stale incremental output. Re-checked during PR review: repeated
   `clean test-compile`/`clean verify` runs are green with **no** `lombok.version` override (the parent `1.18.30`
   processor works against the `1.18.32` classpath, same as booking), so the earlier temporary pin was **removed** —
   the failures were stale-target flakiness, resolved by a clean build.
2. **Guava downgrade breaking Guice.** After dropping `dynamo-client`, old swagger dragged `guava 27.0.1-android` in via
   nearest-wins, breaking Guice (`ImmutableMap.buildOrThrow` `NoSuchMethodError`, `MoreTypes` `NoClassDefFound`). Fixed
   by pinning `guava 33.5.0-jre` (matches booking).
3. **Latent `GZip.compress` truncation bug** (see §7) — reproduced by `SpotRatesAttributeConverterTest.compressedRoundTrip`
   and the `SpotRatesDaoIT` gzip test before fixing.

### PR-review fixes (folded into the two commits via `--force-with-lease`)
- **Jackson still vulnerable (reviewer):** the direct `jackson-dataformat-xml` dependency pinned `2.19.2`, overriding the
  jackson-bom. Dropped its explicit `<version>` so it is BOM-managed to `2.21.4` (verified: `dependency:tree` shows
  `2.21.4`, no `2.19.x` remains; OWASP rescan still 0 HIGH). — folded into the **OWASP** commit.
- **`DynamodbClientConfig` provider self-containment (reviewer, importance 8):** `provideDynamoDbClientConfig` no longer
  takes an injected `RatesConfig` (which only worked because `RatesModule` happens to bind it); it now reuses the
  `ratesConfig` passed to the module constructor, so `SpotRatesModule` is self-contained. `SpotRatesModuleTest` updated
  to build the injector from `SpotRatesModule` alone. — folded into the **AWS** commit.
- **Redundant lombok pin removed** (see issue 1 above). — folded into the **AWS** commit.

---

## 9. Live AWS verification (Step 3B)

### (a) DynamoDB schema parity — matches the v2 entity annotations in every environment

| Env | Table | Hash key | GSI `SPOT_RATE_ID_INDEX` | TTL | Stream | SSE |
|-----|-------|----------|--------------------------|-----|--------|-----|
| INT (`081020446316`) | `inttra_int_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | ENABLED `expiresOn` | disabled | disabled |
| QA (`642960533737`) | `inttra2_qa_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | ENABLED `expiresOn` | disabled | ENABLED |
| CVT (`642960533737`) | `inttra2_test_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | ENABLED `expiresOn` | disabled | ENABLED |
| PROD (`642960533737`) | `inttra2_prod_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | ENABLED `expiresOn` | disabled | ENABLED |

All match `@DynamoDbPartitionKey spotRateKey`, `@GsiConfig(KEYS_ONLY)`/`@DynamoDbSecondaryPartitionKey`, and
`@TTL expiresOn`. Note the CVT prefix is `inttra2_test_booking` (not `inttra2_cvt`).

### (b) TTL / stream divergence — none
TTL is ENABLED on `expiresOn` and streams are DISABLED in **all** environments — no divergence. SSE differs (INT off;
QA/CVT/PROD on) but that is table-level encryption owned by the (external) provisioning, matching each env's
`sseEnabled` config. `rates` has **no** table-admin command, so it never creates/alters tables and therefore never
overrides SSE / TTL / stream in any environment.

### (c) ECS deployment health
- **INT `Rates-dev`** (cluster `ANEINWEBSVC-001`, taskDef `Rates-latest-dev-Task:7`): `status=ACTIVE`,
  `rolloutState=COMPLETED`, but `runningCount=0`. Tasks stop with `EssentialContainerExited` / exitCode 1; CloudWatch
  shows the `api-alpha` **HTTP 502** during the eager `ContainerTypeClient` warm-up (see §6). This is the **deployed
  develop** artifact failing on the INT gateway outage — independent of this change (the feature branch is not
  deployed). Flagged for the INT platform/deploy owners.
- **QA `Rates-qa`** (cluster `ANEQAWEBSVC-001`, taskDef `Rates-latest-qa-Task:5`): `status=ACTIVE`, `desired=1`,
  **`running=1`**, `rolloutState=COMPLETED`, *"has reached a steady state."* The rates application **is running** in
  QA. QA executes the **identical startup steps** (same eager `ISOContainerToTmContainer` → `ContainerTypeClient` →
  `AuthClient` path) but against the healthy `api-beta.inttra.com` gateway (400/401), so it boots cleanly. This
  isolates the INT failure to the `api-alpha` gateway outage, not the code.

**Gateway health probe (root-cause evidence):**

| Env | Gateway | `/auth` | `/network/containertype` | State |
|-----|---------|---------|--------------------------|-------|
| INT | `api-alpha.inttra.com` | 502 | 502 | **DOWN** (502 on all paths) |
| QA  | `api-beta.inttra.com`  | 400 | 401 | up |
| CVT | `api-test.inttra.com`  | 400 | — | up |
| PROD| `api.inttra.com`       | 400 | — | up |

### (d) Dropwizard command-name / CI `$task` — no change needed
The current single-module `rates` has **no** Dropwizard table-admin command (no `ConfiguredCommand`/
`AbstractDynamoCommand`/`CreateTables`/`dynamo-create`). `SpotRatesDetail` is externally provisioned. `run.sh` deploys
`java -jar rates-1.0.jar server ./config.yaml` (task = `server`). Therefore the `create-tables → dynamo-create` CI
`$task` migration does **not** apply to `rates`. (`DynamoTableCommand.java` seen in git history belongs to a
long-removed `rates-api`/`rates-batch` structure, not this module.)

---

## 10. cloud-sdk gaps

**None found.** Every capability required by `rates` is provided by `cloud-sdk-api`/`cloud-sdk-aws`:
`DatabaseRepository` + `DefaultQuerySpec` (partition-key consistent read, GSI query), `DynamoRepositoryFactory`,
`BaseDynamoDbConfig`/`DynamoDbClientConfig`, the enhanced-client annotations (`@Table`/`@GsiConfig`/`@TTL`/
`@DynamoDbSecondaryPartitionKey`), and the built-in `DateEpochSecondAttributeConverter` (byte-identical to the legacy
`DateToEpochSecond`). Module-specific JSON/Map encodings were implemented locally as `AttributeConverter`s, which is the
intended extension point.

---

## 11. Command log (key commands + why)

```powershell
# Orientation / baseline
git merge --ff-only origin/develop                        # fast-forward develop to latest (network fetch unavailable)
git checkout -b feature/ION-16110-rates-owasp-aws-upgrade develop
mvn package -pl rates -DskipTests -am                      # baseline shaded jar
dependency-check --project rates --scan .\target\rates-1.0.jar --out <tmp> --format HTML --format JSON \
    --suppression .\suppressions.xml --nvdApiKey $env:NVD_API_KEY      # baseline OWASP scan (6 HIGH)
java -jar target\rates-1.0.jar server conf\int\config.yaml # develop boot-check (external auth 502 — flagged)

# OWASP fix + verification
mvn -f rates/pom.xml clean test                            # 385 tests green on commons 1.0.28 + jackson pin
dependency-check ... (post-fix rescan)                     # 0 HIGH

# AWS migration verification
mvn -f rates/pom.xml clean compile / test-compile / verify # 421 unit + 9 IT green
mvn -pl rates -Pmercury-commons,sonar clean verify -Dsonar.skip=true   # JaCoCo report
mvn -f rates/pom.xml dependency:tree -Dincludes=com.google.guava:guava # diagnose guava 27.0.1-android downgrade

# Reference lookups (kb tooling over this repo + mercury-services-commons)
kb_find_files BaseDynamoDbConfig.java / DateEpochSecondAttributeConverter.java / DefaultQuerySpec.java / BaseDynamoDbIT.java
kb_grep DefaultQuerySpec: getIndexName / isConsistentRead ; CloudAttributeValue: ofString / getValue

# Live AWS (read-only)
aws sts get-caller-identity --profile 081020446316_INTTRA-Dev-Engg
aws dynamodb describe-table / describe-time-to-live --table-name inttra_int_booking_SpotRatesDetail  (INT)
aws dynamodb describe-table / describe-time-to-live  (QA/CVT/PROD via qa-team-static profile)
aws ecs describe-services --cluster ANEINWEBSVC-001 --services Rates-dev
git log --all --pretty=format: --name-only | grep 'rates/.*(CreateTables|Command).*\.java'   # CI $task check
```

---

## 12. Build / packaging results

- `mvn -f rates/pom.xml clean verify` → **BUILD SUCCESS** (421 unit + 9 integration, 0 failures/errors).
- `mvn package -pl rates -DskipTests` → **BUILD SUCCESS** (shaded `rates-1.0.jar`, ~73 MB).
- End state: exactly **two** outgoing commits on top of the latest develop, each containing `ION-16110`; pushed to
  `origin` (`598e382de2`), PR **#1126** open (`feature/ION-16110-rates-owasp-aws-upgrade → develop`).

---

## 13. Token-usage

Token-usage telemetry is captured by the mcp-context-server harness hook (Copilot CLI `agentStop`). The model cannot
observe its own usage block, so no figures are fabricated here; see the session's `session_usage_report`
(session `0177e780785546df`).

---

## 14. References

- Jira: ION-16110
- Reference design: `rates/docs/2026-06-30-rates-aws2x-DESIGN-claude.md`
- Reference modules: `booking` (`carrierspotrates` SpotRatesDetail twin + `dynamodb/converter/*`), `network`, `auth`,
  `visibility`; completed VAS upgrade `value-added-service/docs/2026-07-24-vas-aws-upgrade.md`.
- OWASP reports: `C:\temp\latest-dep-chk-reports\rates\{baseline,post}\`.
- Session context: `0177e780785546df` (cross-linked to VAS session `078302148c5345a0`).
- Commits: `1ee54add12` (OWASP) and `598e382de2` (AWS SDK 2.x upgrade) — two separate commits, both containing `ION-16110`. PR: #1126.

---

## 15. PR review — comments, resolutions, and full command playbook

### 15.1 Reviewer comments → resolutions

| # | Reviewer comment | Resolution | Landed in |
|---|------------------|------------|-----------|
| 1 | `ContainerType` has no `@DynamoDbDocument` — how is it persisted? | It is **not** persisted. `ContainerType` is a network REST DTO (deserialized from the `containertype` API via Jackson, held in memory). The old `@DynamoDBDocument`/`@DynamoDBTypeConvertedEnum` were **dead v1 annotations** (would not compile once `com.amazonaws` left the prod classpath). Correctly dropped — no persistence path exists. | AWS commit `598e382de2` |
| 2 | Same for `Audit` | `Audit` **is** persisted, as a nested DynamoDB **Map (M)** via `@DynamoDbConvertedBy(AuditAttributeConverter.class)` on `SpotRatesDetail.getAudit()`. The enhanced client needs no `@DynamoDbBean`/annotation on `Audit` itself (mirrors booking's `Audit`). | AWS commit `598e382de2` |
| 3 | Provider injects `RatesConfig` even though the module never binds one → Guice "No implementation for RatesConfig" (importance 8) | `provideDynamoDbClientConfig()` now reuses the `ratesConfig` passed to the module constructor instead of an injected `RatesConfig`, so `SpotRatesModule` is self-contained. `SpotRatesModuleTest` rebuilt to create the injector from `SpotRatesModule` alone. | AWS commit `598e382de2` |
| 4 | Why pin `jackson.version` and `lombok.version` — aren't they transitive from `commons`? | **jackson pin kept** — without it the transitive resolves to `2.19.2` (vulnerable); the BOM forces the patched 2.21.4 across all jackson modules. **lombok pin removed** — verified the parent's `1.18.30` processor builds cleanly against the `1.18.32` classpath `commons` ships (the earlier failures were stale-target flakiness), so the temporary override was dropped. | OWASP `1ee54add12` / AWS `598e382de2` |
| 5 (follow-up) | Jackson still vulnerable: direct `jackson-dataformat-xml` pins `2.19.2`, overriding the BOM | Dropped the hard-coded `<version>2.19.2</version>` so `jackson-dataformat-xml` is BOM-managed to `2.21.4` (verified via `dependency:tree`; OWASP rescan still 0 HIGH). | OWASP commit `1ee54add12` |

> **Q1 vs Q2 in one line:** `ContainerType` = transient REST DTO (never in DynamoDB); `Audit` = persisted, but through a
> parent-level `AttributeConverter`, not its own bean annotation.

### 15.2 Full command playbook (steps + explanations)

All commands were run from the repo root `C:\Users\arijit.kundu\projects\mercury-services` (PowerShell) unless noted.

**A. Orientation & branch setup**
```powershell
git merge --ff-only origin/develop                     # fast-forward local develop to the already-fetched origin/develop
                                                        #   (network fetch needs creds; the remote-tracking ref was already present)
git checkout -b feature/ION-16110-rates-owasp-aws-upgrade develop   # branch off the latest develop (8dad1d555c)
git check-ignore rates/docs .vscode/launch.json        # confirm docs + run configs are git-ignored (local deliverables)
```

**B. OWASP dependency-check — baseline then post**
```powershell
mvn package -pl rates -DskipTests -am                   # build the shaded jar to scan (baseline, on develop)
dependency-check --project rates --scan .\target\rates-1.0.jar --out <tmp> `
    --format HTML --format JSON --suppression .\suppressions.xml --nvdApiKey $env:NVD_API_KEY   # scan the jar
# Parse JSON: group vulnerabilities by severity; list HIGH/CRITICAL CVEs.  Baseline = 6 HIGH.
# ...apply the OWASP fix, rebuild, and rescan into a 'post' folder the same way.  Post = 0 HIGH.
Copy-Item <tmp>\dependency-check-report.{html,json} C:\temp\latest-dep-chk-reports\rates\{baseline|post}\
```
*Why:* establishes the pre/post CVE delta and archives both reports. The jar must be rebuilt before each scan so the
scan reflects the current dependency set.

**C. Develop boot-check + INT/QA auth-gateway root-cause analysis**
```powershell
java -jar rates\target\rates-1.0.jar server rates\conf\int\config.yaml   # boot-check; fails at the eager ContainerTypeClient load (auth 502)
# Probe each environment's gateway directly to localise the outage:
Invoke-WebRequest https://api-alpha.inttra.com/auth -SkipHttpErrorCheck   # INT  -> 502 (down)
Invoke-WebRequest https://api-beta.inttra.com/auth  -SkipHttpErrorCheck   # QA   -> 400 (up)
# Confirm the deployed INT artifact fails identically, from CloudWatch:
aws ecs list-tasks --cluster ANEINWEBSVC-001 --service-name Rates-dev --desired-status STOPPED --profile 081020446316_INTTRA-Dev-Engg
aws ecs describe-tasks --cluster ANEINWEBSVC-001 --tasks <taskArn> --profile 081020446316_INTTRA-Dev-Engg `
    --query "tasks[0].{stoppedReason:stoppedReason,stopCode:stopCode,containers:containers[].exitCode}"     # EssentialContainerExited, exitCode 1
aws logs get-log-events --log-group-name inttra-int-lg-rates `
    --log-stream-name Rates-latest-dev-Task/Rates-dev-Container/<taskId> --start-from-head --limit 40 `
    --profile 081020446316_INTTRA-Dev-Engg --region us-east-1     # shows AuthClient 502 from ContainerTypeClient$3.load
```
*Why:* proves the boot failure is the **INT `api-alpha` gateway outage** (502 on all paths), reproduced by the deployed
develop build too — not a code defect. QA (`api-beta`) is healthy and its ECS service runs at steady state.

**D. Reference lookups (knowledge base over this repo + `mercury-services-commons`)**
```
kb_find_files BaseDynamoDbConfig.java | DateEpochSecondAttributeConverter.java | DefaultQuerySpec.java | BaseDynamoDbIT.java
kb_read_file  <path>            # read cloud-sdk sources to mirror exact APIs
kb_grep       DefaultQuerySpec.java  "getIndexName|isConsistentRead"   ; CloudAttributeValue.java "ofString|getValue"
```
*Why:* confirm the exact cloud-sdk API surface (accessor names, converter behaviour) before writing code/tests.

**E. Live AWS verification (read-only) — DynamoDB parity + ECS**
```powershell
aws sts get-caller-identity --profile 081020446316_INTTRA-Dev-Engg           # confirm INT account before the batch
aws dynamodb describe-table        --table-name inttra_int_booking_SpotRatesDetail --profile <int> --region us-east-1
aws dynamodb describe-time-to-live --table-name inttra_int_booking_SpotRatesDetail --profile <int> --region us-east-1
# QA/CVT/PROD via the QA account (see the static-profile note below):
aws dynamodb describe-table --table-name inttra2_qa_booking_SpotRatesDetail   --profile qa-team-static --region us-east-1
aws dynamodb describe-table --table-name inttra2_test_booking_SpotRatesDetail --profile qa-team-static --region us-east-1   # CVT
aws dynamodb describe-table --table-name inttra2_prod_booking_SpotRatesDetail --profile qa-team-static --region us-east-1
aws ecs describe-services --cluster ANEQAWEBSVC-001 --services Rates-qa --profile qa-team-static --region us-east-1        # running=1, steady state
```
*QA static profile:* the QA account is reached via a static-credentials profile added to `~/.aws/credentials`
(`[qa-team-static]`, access key / secret / session token). A duplicate section header caused
`aws: Unable to parse config file` — resolved by removing the duplicate `[qa-team-static]` block so only one remains.
STS session tokens expire, so the block is refreshed as needed. Credentials are never committed.

**F. Build / test / coverage**
```powershell
mvn -f rates/pom.xml clean compile                       # main compile only (fast API-mismatch check)
mvn -f rates/pom.xml clean test-compile                  # compile tests (used to isolate the flaky lombok skew)
mvn -f rates/pom.xml clean verify                        # unit (surefire, 421) + DynamoDB-Local IT (failsafe, 9)
mvn -pl rates "-Pmercury-commons,sonar" clean verify "-Dsonar.skip=true"   # + JaCoCo (jacoco-aggregate/jacoco.csv)
# Long builds are teed to a log and grepped, never piped live into Select-String:
mvn -f rates/pom.xml clean verify 2>&1 | Tee-Object $env:TEMP\rates-verify.log | Select-String 'Tests run:|BUILD'
```

**G. Dependency analysis (jackson, guava, lombok)**
```powershell
# Guava downgrade diagnosis (Guice buildOrThrow NoSuchMethod):
mvn -f rates/pom.xml dependency:tree "-Dverbose" "-Dincludes=com.google.guava:guava"   # showed 27.0.1-android winning
#  -> pinned guava 33.5.0-jre (matches booking); re-checked the tree shows 33.5.0-jre.
# Jackson: prove the transitive (unmanaged) version, then that the BOM+fix wins:
#  (temporarily removed the jackson-bom import) tree -> jackson-databind 2.19.2  (vulnerable, hence the pin is required)
mvn -f rates/pom.xml dependency:tree "-Dincludes=com.fasterxml.jackson.dataformat:jackson-dataformat-xml"   # after fix -> 2.21.4
mvn -f rates/pom.xml dependency:tree | Select-String 'jackson.*:2\.19\.'                                     # empty = no 2.19.x remains
# Lombok bisect (is the pin needed?): removed <lombok.version> then compiled repeatedly:
mvn -f rates/pom.xml clean test-compile   # run x3 -> all BUILD SUCCESS  => pin unnecessary, removed
```

**H. Git — two-commit construction, PR-review fold, the rebase issue, and force-push**
```powershell
# Two separate commits (OWASP first, then AWS):
git add rates/pom.xml
git commit -m "ION-16110: rates OWASP dependency-check fix - commons 1.0.28-SNAPSHOT + Jackson 2.21.4 pin ..."
git add rates/                                           # all migration source/tests
git commit -m "ION-16110: rates AWS SDK 2.x (cloud-sdk) upgrade - DynamoDB migration + tests ..."

# ---- PR-review fixes folded into the existing two commits (Option B) ----
git branch rates-review-backup-20260728                  # SAFETY backup before rewriting history

# 1) AWS-commit fixes (self-contained provider + lombok-pin removal). jackson-xml kept at 2.19.2 for this step
#    so it does NOT land in the AWS commit:
git add rates/pom.xml rates/src/main/.../SpotRatesModule.java rates/src/test/.../SpotRatesModuleTest.java
git commit --amend --no-edit                             # -> new AWS commit (432b86e09c)

# 2) OWASP-commit fix (drop jackson-dataformat-xml <version>) via fixup + autosquash so it folds into commit 1:
#    (edit pom to remove the version), then:
git add rates/pom.xml
git commit --fixup=7ae0f4eadc                            # creates a "fixup! ..." commit targeting the OWASP commit
git rebase -i --autosquash develop                       # <-- FAILED here (see the rebase issue below)
```

**The rebase issue (and fix).** `git rebase -i --autosquash` needs a *sequence editor* to accept the auto-arranged todo
list. Passing `GIT_SEQUENCE_EDITOR="cmd /c exit 0"` broke: Git appends the todo-file path
(`.git\rebase-merge\git-rebase-todo`), and `cmd`'s parsing of that backslashed path split it, yielding
`'ebase-merge' is not recognized` and `error: there was a problem with the editor`. The rebase aborted, leaving a stray
`fixup!` commit on top.

Resolution — use a real no-op editor **script file** (ignores its argument, exits 0) referenced with forward slashes:
```powershell
if (Test-Path .git\rebase-merge) { git rebase --abort }          # clean up the failed rebase (none was mid-apply here)
Set-Content $env:TEMP\git-noop-editor.cmd '@exit /b 0'           # no-op editor: consumes the todo path, exits 0
$noop = "C:/Users/arijit.kundu/AppData/Local/Temp/git-noop-editor.cmd"
git -c "sequence.editor=$noop" -c "core.editor=$noop" rebase -i --autosquash develop   # squashes fixup! into the OWASP commit
# Result: clean two commits again -> 1ee54add12 (OWASP, now incl. jackson-xml fix) + 598e382de2 (AWS).
```
*Why a script file, not an inline command:* Git invokes the editor as `<editor> <todo-path>`; a `.cmd` file that does
`@exit /b 0` reliably ignores the extra path argument on Windows, whereas an inline `cmd /c ...` string mis-parses the
backslashed todo path.

**Verify the split, then push:**
```powershell
git show 1ee54add12 -- rates/pom.xml | Select-String '2.19.2|jackson-bom|commons.version'   # OWASP commit owns the jackson-xml fix
git show 598e382de2 -- rates/pom.xml | Select-String '[+-].*jackson-dataformat-xml'          # empty = AWS commit doesn't touch it
mvn -f rates/pom.xml clean verify                                                            # 421 unit + 9 IT green on the rebased tree
# Push: the branch already existed on origin (pushed earlier at ffaa38442a), so the folded history is non-fast-forward:
git push --force-with-lease=feature/ION-16110-rates-owasp-aws-upgrade:ffaa38442a20d743f6e4fb3133e079de9c3040a7 `
    origin feature/ION-16110-rates-owasp-aws-upgrade    # lease scoped to the expected remote SHA -> safe forced update
```
*Why `--force-with-lease` (not `--force`):* the lease is scoped to the exact SHA I expected on the remote, so the push
aborts if anyone else had pushed in the meantime — a rewrite that never clobbers someone else's work.
