# Ocean Schedules AWS SDK 2.x Upgrade — Resume Progress Summary

**Date:** 2026-05-31
**Jira:** ION-11462
**Branch:** `feature/ION-11462-os-aws-upgrade-copilot`
**MCP session:** `5438b56c73c04f94` (status: active)
**Agent model:** copilot-claude-opus-4.8

> This is a working resume/progress note so the migration can be picked back up
> cleanly. It complements the design doc
> [`2026-05-31-os-aws2x-upgrade-design-copilot.md`](2026-05-31-os-aws2x-upgrade-design-copilot.md)
> and the process-module plan
> `oceanschedules-process/docs/2026-05-31-os-aws-upgrade-plan.md`.

---

## Scope & Constraints (unchanged)

- Migrate `oceanschedules` (and later `oceanschedules-process`) from AWS SDK v1 to
  the cloud-sdk-api / cloud-sdk-aws libraries from `com.inttra.mercury:commons`.
- **Kafka and Spark code remain UNCHANGED** (neither exists in `oceanschedules`;
  Spark only in `oceanschedules-process/aggregator`).
- Only modify `oceanschedules/` and `oceanschedules-process/`.
- Cannot delete files — gut them to deprecated empty stubs instead.
- Documented cloud-sdk gaps use in-module adapter workarounds, each marked
  `// TODO(ION-11462): requires commons change GAP-n`.
- Commit messages MUST contain `ION_11462`. **NEVER push / no PR.**
- `git add` specific files only — never `git add -A`.
- Build offline-friendly: `mvn -o -pl oceanschedules -am ...`.

---

## Status Overview

| Area | State |
|------|-------|
| Main sources (oceanschedules) | ✅ Migrated, compiles cleanly |
| Unit tests — all 6 rewritten | ✅ RealTimeCacheDaoTest, SchedulesProStagingDaoTest, AWSUtilTest, SNSClientTest, S3ServiceTest, CarrierServiceTest |
| Test-compile verification | ✅ Passes offline |
| Unit tests (`surefire:test`) | ✅ 572 run, 0 failures |
| DynamoDB integration tests | ✅ RealTimeCacheDaoIT (7) + SchedulesProStagingDaoIT (4) — 11 green |
| YAML config updates | ✅ `region: us-east-1` added to cvt/int/prod/qa |
| IT dependency conflict (GAP-7) | ✅ Excluded stale `aws-java-sdk-dynamodb` from `integration-test-commons` |
| Full `mvn verify` | ✅ via `failsafe:integration-test/verify` (shade blocked offline only — unrelated) |
| Commit | ⏳ Pending (this session) |
| oceanschedules-process | ⏳ Not started |

---

## Completed Main Sources (all compile)

- `module/OceanschedulesModule.java` — rewired Guice: `OceanSchedulesDynamoModule`,
  `@Provides` for `NotificationService` (NotificationClientFactory), `StorageClient`,
  raw `S3Client` (GAP-3). `resolveDefaultTopicArn(SNSConfig)`.
- `config/OceanSchedulesConfig.java` — `dynamoDbConfig` type → `BaseDynamoDbConfig`.
- `config/DynamoTableCommand.java` — SDK v2 `ConfiguredCommand`; `DynamoDbAdminUtil`
  for realtime cache table; inline `createTable` (PAY_PER_REQUEST + GSI) for
  schedules_pro_staging (GAP-7 note: `addGlobalSecondaryIndexIfNotExists` forces
  provisioned GSI throughput, invalid on-demand).
- `util/AWSUtil.java` — `isRetryable(SdkException)`.
- `util/sns/SNSClient.java` — injects `NotificationService`, retry loop.
- `util/s3/S3Service.java` — raw SDK v2 `S3Client` (GAP-3): listObjectsV2 delimiter
  paging, deleteObjects chunked, copyObject.
- `service/CarrierService.java` — `List<S3Object>`, `.key()`.
- `client/external/ExternalClient.java` — removed v1 `IOUtils`.
- `module/AWSClientConfiguration.java` — gutted to deprecated empty final class.
- `pom.xml` — removed v1 `dynamo-client` dependency.

### Prior-session main sources (compiling)
RealTimeCache, SchedulesProStaging (both `@DynamoDbBean`, non-generic),
DynamoSupport (gutted), RealTimeCacheConditionalWriter (GAP-6 adapter),
RealTimeCacheDao, SchedulesProStagingDao, SharedConstants (`CACHE_KEY_ATTRIBUTE`),
OceanSchedulesDynamoModule (booking pattern).

---

## Test Files Rewritten This Session (4 of 6)

1. **RealTimeCacheDaoTest.java** — mocks
   `DatabaseRepository<RealTimeCache, DefaultPartitionKey<String>>` +
   `RealTimeCacheConditionalWriter`; new constructor; non-generic `RealTimeCache`;
   `addCache`→`verify(repository).save`; `acquireLock`→stub
   `conditionalWriter.acquireLock`; added `findCacheByCacheKey` tests
   (unexpired / expired-filtered / empty / exception→`isReadWriteError`).
2. **SchedulesProStagingDaoTest.java** — mocks
   `DatabaseRepository<SchedulesProStaging, DefaultCompositeKey<String,String>>`;
   single-arg constructor; non-generic entity; `stubQueryByScac` uses
   `repository.query(any(DefaultQuerySpec.class))` `thenAnswer` reading
   `spec.getPartitionKeyAttributeValue().s()`.
3. **AWSUtilTest.java** — SDK v2 exceptions (AwsServiceException throttling,
   SdkClientException w/ IOException cause, plain non-retryable, null).
4. **SNSClientTest.java** — mocks `NotificationService`; `doThrow(throttling)` /
   `doNothing` on `publish(anyString, anyString)`; retry + fail paths.

### Key API facts discovered
- `CloudAttributeValue` has **no** public string getter — use
  `DefaultQuerySpec.getPartitionKeyAttributeValue().s()` (returns AWS v2
  `AttributeValue`).
- Throttling in SDK v2: `AwsServiceException.builder().awsErrorDetails(
  AwsErrorDetails.builder().errorCode("ThrottlingException").build()).build()`.

---

## Remaining Test Rewrites (next 2)

5. **S3ServiceTest.java** — mock `software.amazon.awssdk.services.s3.S3Client`;
   stub `listObjectsV2(...)` → `ListObjectsV2Response` (commonPrefixes / contents /
   isTruncated / nextContinuationToken), `deleteObjects`, `copyObject`; change
   `List<S3ObjectSummary>` → `List<S3Object>` (`S3Object.builder().key(...).build()`).
   Currently still references v1 `AmazonS3` (line 43) and `S3ObjectSummary`
   (lines 368, 391, 435).
6. **CarrierServiceTest.java** — line ~396 `thenReturn(...)` change from
   `List<S3ObjectSummary>` to `List<S3Object>`
   (`List.of(S3Object.builder().key("...").build())`).

---

## Continuation Plan (in order)

1. Rewrite **S3ServiceTest.java** and **CarrierServiceTest.java** (above).
2. Verify test-compile:
   `mvn -o -pl oceanschedules -am install -DskipTests -Dmaven.test.skip=false`.
3. Run unit tests; fix any failures.
4. Create **DynamoDB integration tests** `RealTimeCacheDaoIT`,
   `SchedulesProStagingDaoIT` using `BaseDynamoDbIT` (dynamo-integration-test);
   composite key + GSI + TTL + conditional lock; pre-populate legacy epoch-second
   fixtures for backward compat.
5. Update **YAML configs** `oceanschedules/conf/*/config.yaml` — `dynamoDbConfig`
   block to `BaseDynamoDbConfig` shape
   `{environment, region, readCapacityUnits, writeCapacityUnits, sseEnabled,
   endpointOverride}`.
6. Full `mvn -o -pl oceanschedules -am verify` (integration tests may need DynamoDB
   Local; note offline limitation: `integration-test-commons` transitive deps
   absent offline).
7. **Commit** — `git add` specific files only; message prefixed `ION_11462`.
   **NEVER push.**
8. Update design-doc GAP-7 resolution + change-log; create final
   `2026-XX-XX-aws-sdk-upgrade-summary.md`.
9. Log decisions / code_change / test_result to MCP session `5438b56c73c04f94`.

### Then (subsequent, not immediate)
- Migrate `oceanschedules-process` 8 sub-modules — **Kafka & Spark UNCHANGED**.
- GAP-1 / GAP-2 SQS adapters. Phases 8–10 (NO push/PR).

---

## Known Gaps (cloud-sdk)

| Gap | Issue | Workaround |
|-----|-------|------------|
| GAP-3 | `StorageClient` lacks delimiter listing & batch delete | `S3Service` uses raw SDK v2 `S3Client` |
| GAP-4 | No multipart copy for objects > 5 GB | `copyObject` single-part; TODO marker |
| GAP-6 | No generic conditional save | `RealTimeCacheConditionalWriter` adapter |
| GAP-7 | `addGlobalSecondaryIndexIfNotExists` forces provisioned GSI throughput (invalid on-demand) | inline `createTable` for schedules_pro_staging |
| GAP-1/2 | SQS adapter needs (process module) | pending |
