# Ocean Schedules — AWS SDK 2.x Upgrade: Design & Implementation Review

**Jira**: ION-11462
**Branch**: `feature/ION-11462-os-aws-upgrade-copilot`
**Reviewer**: Claude Opus 4.8 (enterprise refactoring review)
**Date**: 2026-06-01
**Scope reviewed**: the **`oceanschedules`** Dropwizard API module migration from AWS SDK v1 (`dynamo-client`, `com.amazonaws.*`) to **cloud-sdk-api + cloud-sdk-aws** (AWS SDK v2) on this branch vs `develop`. The 8 `oceanschedules-process` sub-modules are **not yet migrated** (Copilot summary §5) and are out of scope here except where they share contracts.
**Inputs**: `2026-05-31-aws-sdk-upgrade-summary.md`, `2026-05-31-os-aws2x-upgrade-design-copilot.md`, the `ION-11462` commit series, the live branch diff, and the cloud-sdk source in `mercury-services-commons`.
**Companion reviews**: booking (`2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md`), visibility (`2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md`).

---

## 0. Verdict

The `oceanschedules` migration is **structurally sound and backward-compatible on the two properties that actually matter for this module: physical table names and the on-disk date format.** Both were verified against `develop` at byte level, not just asserted:

- Table names are **identical** to v1 — both v1 (`AbstractDynamoCommand`) and v2 (`OceanSchedulesDynamoModule` / `DynamoTableCommand`) derive the prefix as `environment + "_"`, so `inttra2_cv_os_realtime_cache` and `inttra2_cv_schedules_pro_staging` are unchanged.
- Date fields stay **epoch-seconds in `N`** via `DateEpochSecondAttributeConverter`, which is functionally identical to v1's `DateToEpochSecond` (seconds, `N`, null-tolerant). No format coupling exists here — unlike booking/visibility, oceanschedules has **no `@JsonFormat`/timestamp-string fields in DynamoDB**, so the entire class of audit-timestamp bugs that dominated the booking saga **does not apply to this module**.

The four real cloud-sdk gaps (GAP-1/2 SQS, GAP-3 S3 delimiter/batch, GAP-4 multipart, GAP-6 conditional write, GAP-7 DDL) are handled with in-module AWS SDK v2 adapters, each carrying a `TODO(ION-11462): requires commons change GAP-n` marker, and **GAP-6 / GAP-7 are correctly implemented and covered by integration tests** (11 ITs on DynamoDB Local, green).

**This is close to releasable for the `oceanschedules` API module, but it is not a clean merge candidate yet.** The findings below are mostly confirmations and guardrails; the two that need explicit sign-off before merge are the **`1.0.26-SNAPSHOT` cloud-sdk dependency** (R1 — shared with the whole AWS-upgrade train, cannot ship as a snapshot) and the **split version properties** that can drag two commons lines onto one classpath (R2). Neither is a correctness defect in the migrated code; both are release-hygiene blockers.

No data-format regression was found in this module. That is the single most important result, and it is the inverse of the visibility finding (where `MetaData` silently flipped `S`→`M`).

---

## 1. What the migration got right (confirmed against code)

### 1.1 Table names are byte-identical to v1 — verified, not assumed
The backward-compatibility risk that breaks a DynamoDB migration silently is a changed physical table name. It did **not** happen here:
- v1: `dynamo-client/.../AbstractDynamoCommand.java:74` → `prefix = dynamoDbConfig.getEnvironment() + "_"`.
- v2 repository: [OceanSchedulesDynamoModule.java:139](../src/main/java/com/inttra/mercury/oceanschedules/module/OceanSchedulesDynamoModule.java#L139) → `clientConfig.getTablePrefix() + tableAnnotation.name()`, and `BaseDynamoDbConfig.toClientConfigBuilder()` (commons) sets `tablePrefix = environment + "_"`.
- v2 DDL command: [DynamoTableCommand.java:63](../src/main/java/com/inttra/mercury/oceanschedules/config/DynamoTableCommand.java#L63) → `prefix = dynamoConfig.getEnvironment() + "_"`.

All three converge on the same string. `environment` is unchanged in every config (`inttra2_cv`, etc.; only `region: us-east-1` was added). The `@Table(name=...)` base names (`os_realtime_cache`, `schedules_pro_staging`) match the v1 `@DynamoDBTable` names. **The conditional-writer adapter uses the exact same prefix derivation** ([OceanSchedulesDynamoModule.java:87-88](../src/main/java/com/inttra/mercury/oceanschedules/module/OceanSchedulesDynamoModule.java#L87-L88)), so the lock writes and the repository writes hit the same table.

### 1.2 On-disk date format is unchanged (epoch-seconds `N`)
[RealTimeCache.java:60-68](../src/main/java/com/inttra/mercury/oceanschedules/dynamodb/RealTimeCache.java#L60-L68) and [SchedulesProStaging.java:72-80](../src/main/java/com/inttra/mercury/oceanschedules/dynamodb/SchedulesProStaging.java#L72-L80) annotate `writeDateTime` / `lastUpdated` / `expiresOn` with `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)`. The commons converter writes `AttributeValue.builder().n(epochSeconds)` and reads `new Date(epochSeconds*1000)` — **identical** to v1 `DateToEpochSecond` (`date.getTime()/1000` ↔ `new Date(epochSeconds*1000)`), including null handling. The TTL attribute (`expiresOn`) stays epoch-seconds, so AWS TTL expiry semantics are unchanged. All non-date fields (`inttraSchedules`, `scheduleJson`, etc.) are plain `S` strings in both versions.

> **Cross-module note**: this module is the *easy* case for the format-decoupling lesson recorded in `[[reference_aws2x_format_decoupling]]`. There are no `Date`/`OffsetDateTime` fields serialized as timestamp *strings* into DynamoDB, no shared `@JsonFormat`, and no v1 consumer reading these tables via a frozen mapper. The S-vs-M and `Z`-vs-`+0000` hazards that dominated booking/visibility simply do not exist here.

### 1.3 GAP-6 conditional lock faithfully reproduces v1 compare-and-set semantics
[RealTimeCacheConditionalWriter.java:44-61](../src/main/java/com/inttra/mercury/oceanschedules/persistence/cache/RealTimeCacheConditionalWriter.java#L44-L61) issues `putItem` guarded by `attribute_not_exists(#locked) OR #locked <> :lockedValue`, with `#locked → "locked"` (attribute name, `SharedConstants.LOCKED`) and `:lockedValue → "locked"`.

This is **semantically equivalent** to v1's `ExpectedAttributeValue(new AttributeValue("locked")).withComparisonOperator(NE)` on attribute `"locked"` (verified against `develop` `RealTimeCacheDao.acquireLock`). DynamoDB legacy `NE` evaluates *true* for a missing attribute, which the v2 expression makes explicit via the `attribute_not_exists` OR-branch. The compared value (`"locked"`, lowercase) is the same in both versions, and the caller [ExternalClient.java:212](../src/main/java/com/inttra/mercury/oceanschedules/client/external/ExternalClient.java#L212) sets `cache.setLocked(SharedConstants.LOCKED)` before acquiring, so the guard attribute is actually persisted. `ConditionalCheckFailedException` → `false` (lock held), exactly as v1. **Confirmed by ITs** `shouldAcquireLockWhenAbsent` / `shouldFailWhenAlreadyLocked` / `shouldReacquireAfterUnlock`.

The v1→v2 write-mode change (DynamoDBMapper default `SaveBehavior.UPDATE` → enhanced-client `putItem` full replace) is **not** a regression here: v1 `UPDATE` also nulls-out modeled attributes that are null on the object, so both versions converge on the same item shape, and the lock object is rebuilt fresh on every call.

### 1.4 GAP-7 table command preserves streams, TTL, on-demand billing and SSE
[DynamoTableCommand.java](../src/main/java/com/inttra/mercury/oceanschedules/config/DynamoTableCommand.java) reproduces every v1 provisioning concern on SDK v2 low-level `DynamoDbClient`:
- **Streams**: `enableStreams(..., KEYS_ONLY)` for the cache table (L93) and `StreamSpecification(KEYS_ONLY)` inline for staging (L121-124). This is the correct home for the stream config that v1 carried as `@DynamoDBStream(KEYS_ONLY)` on the *entities* — those annotations were dropped from [RealTimeCache.java](../src/main/java/com/inttra/mercury/oceanschedules/dynamodb/RealTimeCache.java) / [SchedulesProStaging.java](../src/main/java/com/inttra/mercury/oceanschedules/dynamodb/SchedulesProStaging.java) and re-expressed at provisioning time. Net behaviour is unchanged (streams were only ever materialised at table creation).
- **TTL**: `enableTimeToLive(..., "expiresOn")` on both tables, idempotent (`enable-if-not-set`).
- **Billing**: cache table = provisioned (read/write capacity from config); staging = `PAY_PER_REQUEST` with the GSI throughput omitted — the documented reason being that the generic helper attaches provisioned throughput which AWS rejects on an on-demand table. The inline creation correctly avoids that.
- **Idempotency**: `tableExists` / create-if-not-exists, `waitForTableActive`. Existing production tables are untouched.

### 1.5 GAP-3 S3 port is a faithful, paged translation of the v1 logic
[S3Service.java](../src/main/java/com/inttra/mercury/oceanschedules/util/s3/S3Service.java) reimplements the v1 `AmazonS3` logic on SDK v2 `S3Client` 1:1: delimiter listing via `listObjectsV2(...delimiter("/"))` collecting `commonPrefixes()`, truncation paging via `continuationToken`, the same `s3ObjectListLimit`/`OBJECT_LIMIT` guards, batch delete chunked to ≤1000 keys (`DELETE_BATCH_SIZE`), and the same 3-try `AWSUtil.isRetryable` retry loop. `getS3Objects` and `copyObject` are likewise faithful. The `CarrierService.moveS3Objects` change from `summary.getBucketName()` → `sourceBucket` ([CarrierService.java:228](../src/main/java/com/inttra/mercury/oceanschedules/service/CarrierService.java#L228)) is **correct**, not a behaviour change: SDK v2 `S3Object` (from `ListObjectsV2`) does not carry a bucket name, and the value is the same bucket the listing was performed against.

### 1.6 SNS wiring is correct — per-call topic ARN is honoured
[SNSClient.java:35](../src/main/java/com/inttra/mercury/oceanschedules/util/sns/SNSClient.java#L35) calls `notificationService.publish(target, content)` with the **per-call** `target`. Verified against commons `SnsService.publish(topicArn, message)` — it builds `PublishRequest.topicArn(topicArn)` from the argument, **not** from the ARN supplied to the factory at construction. So the `resolveDefaultTopicArn(...)` value passed to `NotificationClientFactory.createDefaultClient(...)` ([OceanschedulesModule.java:116](../src/main/java/com/inttra/mercury/oceanschedules/module/OceanschedulesModule.java#L116)) is only a non-null placeholder to satisfy the constructor and never affects runtime routing. The 3-try retry loop and the null/empty validation mirror v1. ✅

### 1.7 Tests are real, not decorative
- 572 unit tests + 11 ITs green (per summary). The ITs are **substantive**: [RealTimeCacheDaoIT](../src/test/java/com/inttra/mercury/oceanschedules/persistence/cache/RealTimeCacheDaoIT.java) round-trips an item written with explicit epoch-second dates (`shouldReadLegacyEpochSecondItem`, asserting `getExpiresOn().getTime()/1000 == futureEpochSeconds`), proves expiry filtering, and exercises the full lock acquire/fail/reacquire cycle against DynamoDB Local. `SchedulesProStagingDaoIT` covers the composite key + GSI.
- The DynamoDB-Local dependency clash (`integration-test-commons` pinning `aws-java-sdk-dynamodb:1.12.638` without `OnDemandThroughput`) was correctly resolved by excluding that stale transitive jar so DynamoDB Local 2.5.2's `1.12.721` wins mediation ([pom.xml](../pom.xml) exclusion). Safe, because the ITs only use `dynamo-integration-test`/`BaseDynamoDbIT`.

---

## 2. Findings & risks (ordered by merge/release relevance)

### 🔴 R1 — cloud-sdk dependency is `1.0.26-SNAPSHOT` (cannot ship)
[pom.xml](../pom.xml): `<mercury.cloudsdk.version>1.0.26-SNAPSHOT</mercury.cloudsdk.version>` drives `cloud-sdk-api`, `cloud-sdk-aws`, and `dynamo-integration-test`. A `-SNAPSHOT` is mutable, so the bytes reviewed are not the bytes that will build at release time, and snapshots must not reach production. This is **shared with the whole AWS-upgrade train** — booking pins the same `1.0.26-SNAPSHOT` — so it is a release-train gate, not an oceanschedules-specific defect. **Sign-off item**: the umbrella release must pin a *released* cloud-sdk version and rebuild all migrated modules against it. Until then this branch is not mergeable to a release line.

### 🟠 R2 — split version properties can drag two commons lines onto one classpath
Unlike booking (single `mercury.commons.version` property for everything), oceanschedules keeps the **old release** for general commons (`mercury.commons.version = 1.R.01.023`) and a **separate snapshot** for cloud-sdk (`mercury.cloudsdk.version = 1.0.26-SNAPSHOT`). `cloud-sdk-aws:1.0.26-SNAPSHOT` will transitively pull *its own* commons artifacts (a `1.0.x` line), which can coexist on the classpath with the directly-declared `1.R.01.023` commons jars. That is a recipe for duplicate/divergent commons classes (`ServiceDefinition`, `JestModule`, `ParameterStoreLookup`, Jackson `Json`, etc.) resolving by Maven mediation in a way that differs from booking. **Recommendation**: align oceanschedules to a single commons coordinate/property (as booking did) once the released cloud-sdk version exists, and run `mvn dependency:tree -Dincludes=com.inttra.mercury` to confirm only one commons line survives mediation.

### 🟡 R3 — the cloud-sdk `StorageClient` provider is dead wiring
[OceanschedulesModule.java:130-133](../src/main/java/com/inttra/mercury/oceanschedules/module/OceanschedulesModule.java#L130-L133) binds `StorageClient` via `StorageClientFactory.createDefaultS3Client()`, but **nothing injects it** — every S3 operation goes through the raw SDK v2 `S3Client` in `S3Service` (the only other references to `StorageClient` in the module are javadoc/TODO comments). So the "vendor-neutral storage abstraction" goal is **not actually realised** in oceanschedules; the module's entire S3 surface is raw SDK v2 because of GAP-3/GAP-4. That is an acceptable *interim*, but the unused `provideStorageClient()` binding is misleading and should be removed (or a one-line comment should state it is intentionally retained pending GAP-3 closure). Cheap cleanup; prevents a future reader assuming S3 already flows through cloud-sdk.

### 🟡 R4 — raw clients bypass the cloud-sdk factory's tuned HTTP/retry/region config
The two in-module raw clients are built ad-hoc:
- [OceanschedulesModule.java:148](../src/main/java/com/inttra/mercury/oceanschedules/module/OceanschedulesModule.java#L148): `S3Client.builder().region(Region.US_EAST_1).build()` — region **hardcoded**, default credentials, **no** retry/timeout/Netty-vs-UrlConnection HTTP config. By contrast `StorageClientFactory`/`NotificationClientFactory` apply `createDefaultRetryConfig()` + a configured `httpClient` (the same Netty-removal hardening referenced in booking's `2026-05-28-netty-critical.md`).
- The GAP-6 conditional writer's `DynamoDbClient` ([OceanSchedulesDynamoModule.java:97-106](../src/main/java/com/inttra/mercury/oceanschedules/module/OceanSchedulesDynamoModule.java#L97-L106)) at least takes region/endpoint from the resolved config, but is still a *separate* client instance from the repository's, with default retry/HTTP settings.

Consequences: (a) a non-`us-east-1` environment would silently mis-route S3 (latent only because every env is us-east-1 today); (b) S3Service relies entirely on its own app-level 3-try loop rather than the SDK's tuned retry policy; (c) two DynamoDB clients with potentially different transport config serve the same table. **Recommendation**: source the S3 region from `dynamoDbConfig.region` (or a dedicated S3 region field) and route the raw clients through the same HTTP/retry hardening the cloud-sdk factories use — ideally by having the factories expose the underlying client, which is exactly what GAP-3/GAP-4/GAP-6 commons changes should deliver.

### 🟡 R5 — `AWSUtil.isRetryable` dropped the clock-skew classification
v1: `isRetryableServiceException || isThrottlingException || isClockSkewError || cause instanceof IOException`.
v2 [AWSUtil.java](../src/main/java/com/inttra/mercury/oceanschedules/util/AWSUtil.java): `ex.retryable() || (AwsServiceException && isThrottlingException()) || cause instanceof IOException`. The explicit **clock-skew** retry branch is gone. SDK v2 *may* fold some clock-skew (`RequestTimeTooSkewed`/`InvalidSignatureException`) into `retryable()`, but this isn't guaranteed for all of them. Low-probability and only affects the in-module retry loops (S3/SNS), but worth a one-line confirmation or restoring an explicit check if clock skew was ever a real source of transient failures here.

### 🟢 R6 — batch delete silently ignores per-key failures (matches v1, not a regression)
[S3Service.java:155-158](../src/main/java/com/inttra/mercury/oceanschedules/util/s3/S3Service.java#L155-L158) returns `response.deleted().size()` and never inspects `response.errors()`. A partial `DeleteObjects` failure (e.g. access-denied on some keys) is invisible; the returned count is simply lower. v1 behaved the same (`getDeletedObjects().size()`), so this is **not** a regression — but since the code is being rewritten anyway, logging `response.errors()` would close a real observability gap in `deleteFolder`.

### 🟢 R7 — fresh-create GSI projection is `ALL`; confirm parity for any brand-new env
[DynamoTableCommand.java:119](../src/main/java/com/inttra/mercury/oceanschedules/config/DynamoTableCommand.java#L119) creates `schedules_pro_source_index` with `ProjectionType.ALL`. v1's `DynamoDBMapper.generateCreateTableRequest` chose the projection implicitly. Existing tables are untouched (idempotent create-if-not-exists), so this only matters when provisioning a *new* environment from scratch — and only for consumers that read the GSI (the still-on-v1 process modules, not the oceanschedules DAOs, which query the base table by `scac`). Confirm `ALL` matches what the process modules expect from the GSI before standing up a fresh env.

### 🟢 R8 — deprecated husk files retained
`AWSClientConfiguration`, `DynamoSupport` are reduced to empty `@Deprecated` placeholders "because the file cannot be deleted under the current change constraints." Harmless, but they are dead code; delete them in the cleanup pass when the constraint lifts.

---

## 3. Gap-by-gap technical assessment

The user specifically asked for scrutiny of the documented gaps and their workarounds. Summary of where each gap stands **for the `oceanschedules` module only**:

| Gap | Reality in `oceanschedules` | Workaround quality | Residual risk |
|---|---|---|---|
| **GAP-1** SQS delay-send | **Not used in this module.** No SQS code path in `oceanschedules` (collector/ppg live in `oceanschedules-process`, unmigrated). | n/a here | none for this module; design spec is sound for the process phase |
| **GAP-2** SQS large-payload | **Not used in this module.** | n/a here | deferred to process phase |
| **GAP-3** S3 delimiter list + batch delete | **Real and exercised.** `StorageClient` lacks delimiter/common-prefix listing and batch delete; `S3Service` uses raw SDK v2 `S3Client`. | **Good** — faithful port, paged, retried, ITs not present for S3 (unit tests only). | `StorageClient` left unused (R3); raw client unconfigured (R4); partial-delete errors swallowed (R6) |
| **GAP-4** S3 multipart/transfer | **Moot in this module.** v1 `AWSUtil` had *no* `TransferManager`; the only multipart code (`MultiPartUploader`) is in `oceanschedules-process/common`. `copyObject` uses single-request server-side copy (≤5 GB), guarded by a `TODO` comment. | n/a — no large-object path in oceanschedules | none unless OS objects exceed 5 GB (they don't) |
| **GAP-5** SSM | **Confirmed non-gap.** No `AWSSimpleSystemsManagement` usage in oceanschedules; nothing to remove here (the unused `aws-java-sdk-ssm` deps are in `outbound`/`aggregator`). | n/a | none |
| **GAP-6** conditional write (compare-and-set lock) | **Real and correctly solved.** `RealTimeCacheConditionalWriter` uses the enhanced client's `putItem` + `Expression`. | **Strong** — semantics verified equal to v1, IT-covered (acquire/fail/reacquire). | only the commons-API debt (the adapter should migrate to a `saveIf`/`ConditionSpec` API per §11 GAP-6); uses a *separate* DynamoDB client from the repository (R4) |
| **GAP-7** table/TTL/stream DDL | **Real and correctly solved.** `DynamoTableCommand` on SDK v2 low-level client; on-demand-aware GSI, TTL, streams, SSE, idempotent. | **Strong** — IT bring-up validated; the dependency-exclusion fix is sound. | commons-API debt (an on-demand-aware create-with-GSI helper would let the inline block go); GSI projection parity (R7) |

**Bottom line on gaps**: only **GAP-3, GAP-6, GAP-7** are live in this module, and all three are implemented faithfully with correct backward compatibility. GAP-1/2/4 are genuinely not exercised by `oceanschedules` (they belong to the process phase), and GAP-5 is correctly classified as a non-gap. The workarounds are well-isolated and uniformly tagged `TODO(ION-11462): requires commons change GAP-n`, so the commons debt is discoverable. The main *quality* (not correctness) concern across the gaps is that the in-module raw clients (GAP-3, GAP-6) sidestep the cloud-sdk factory hardening (R4) and leave the cloud-sdk `StorageClient` abstraction unused (R3).

---

## 4. Cross-module / consumer integration assessment

| Consumer | Reads / needs | OS-v2 produces | Status |
|---|---|---|---|
| **`oceanschedules-process` (still on SDK v1)** — reads `os_realtime_cache` / `schedules_pro_staging` and the DynamoDB **streams** | same table names; epoch-second `N` dates; `KEYS_ONLY` streams; GSI on `scheduleSource` | identical table names; epoch-second `N`; `KEYS_ONLY` streams provisioned by `DynamoTableCommand`; GSI preserved | ✅ Compatible — this is the key cross-phase contract, and it holds because §1.1/§1.2/§1.4 are unchanged |
| **DynamoDB TTL** | epoch-second `expiresOn` | epoch-second `expiresOn` (TTL enabled on same attribute) | ✅ Unchanged |
| **SNS subscribers** (loader/outbound/staging/aggregator topics) | message published to per-call topic ARN | `publish(target, content)` routes to the per-call ARN | ✅ Unchanged (§1.6) |
| **ElasticSearch/Jest** | unchanged | unchanged (`JestModule` install untouched) | ✅ Out of migration scope |

The decisive cross-module fact: because **the still-v1 process modules read the same tables, same `N` dates, and same streams**, the partial migration (API module on v2, process on v1) is safe to run side-by-side. This mirrors the booking↔visibility cross-version coexistence and is the same property that must be protected: do **not** change table names, the epoch-second format, or the stream type until the process modules are also migrated.

---

## 5. Documentation quality

The Copilot design doc (`...-design-copilot.md`) and summary are thorough and honest — the §11 gap specs are implementation-ready and the gap→call-site map is accurate. Two observations:
- The summary's claim that `DateEpochSecondAttributeConverter` is *"string-N tolerant"* is slightly overstated — the commons converter returns `null` when `input.n()` is absent and does **not** fall back to `input.s()`. This is harmless (v1 always wrote `N`, so no `S`-encoded epoch records exist), but the doc should say "`N`-only, matching v1" rather than implying `S` tolerance.
- The design doc still carries `1.0.26-SNAPSHOT` as the target version (R1). Add the "must pin to a released cloud-sdk before merge" note so a future reader doesn't treat the snapshot as final.

---

## 6. Pre-merge / pre-release checklist

1. **(R1 — blocker)** Pin `cloud-sdk-*` and `dynamo-integration-test` to a **released** version (not `1.0.26-SNAPSHOT`) and rebuild; coordinate with the umbrella AWS-upgrade release.
2. **(R2 — blocker-ish)** Collapse the split version properties to a single commons coordinate (as booking did) and verify via `mvn dependency:tree -Dincludes=com.inttra.mercury` that exactly one commons line survives mediation.
3. **(R3)** Remove the unused `provideStorageClient()` binding, or comment it as intentionally retained pending GAP-3.
4. **(R4)** Source the raw `S3Client` region from config (not hardcoded `US_EAST_1`) and route the raw S3/DynamoDB clients through the same retry/HTTP hardening the cloud-sdk factories apply.
5. **(R5)** Confirm SDK v2 `retryable()` covers the clock-skew cases v1 handled, or restore an explicit check.
6. **(R6/R7/R8)** Backlog cleanup: log `DeleteObjects` per-key errors; confirm GSI `ALL` projection parity for fresh envs; delete the deprecated husk files.
7. **Cross-phase guard**: until `oceanschedules-process` is migrated, treat table names, the epoch-second `N` format, and the `KEYS_ONLY` stream type as frozen contracts (§4).

**Bottom line**: the `oceanschedules` API-module migration is correct, backward-compatible on the contracts that matter, and well-tested; the GAP-3/6/7 workarounds are sound and well-marked. The only true gates are dependency hygiene (R1/R2). Everything else is low-risk hardening and cleanup.

---
*End of review.*
