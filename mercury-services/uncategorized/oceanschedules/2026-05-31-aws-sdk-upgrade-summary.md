# Ocean Schedules AWS SDK 2.x Upgrade — Summary

**Date:** 2026-05-31
**Jira:** ION-11462
**Branch:** `feature/ION-11462-os-aws-upgrade-copilot`
**MCP session:** `5438b56c73c04f94`
**Agent model:** copilot-claude-opus-4.8

Companion to the design doc
[`2026-05-31-os-aws2x-upgrade-design-copilot.md`](2026-05-31-os-aws2x-upgrade-design-copilot.md)
and progress note
[`2026-05-31-os-aws2x-upgrade-resume-progress.md`](2026-05-31-os-aws2x-upgrade-resume-progress.md).

---

## 1. Outcome

The `oceanschedules` module is fully migrated from AWS SDK v1 (`com.amazonaws.*`)
to the cloud-sdk-api / cloud-sdk-aws libraries (AWS SDK v2) from
`com.inttra.mercury:commons`.

- **Unit tests:** 572 run, 0 failures, 0 errors.
- **Integration tests (DynamoDB Local 2.5.2):** 11 run, 0 failures
  (`RealTimeCacheDaoIT` 7, `SchedulesProStagingDaoIT` 4).
- No remaining `com.amazonaws` / `AmazonS3` / `S3ObjectSummary` references in
  `oceanschedules/src` (one javadoc-only mention remains).

> The offline `mvn -am verify` fails only at the `maven-shade-plugin` (`package`
> phase) because `org.vafer:jdependency:2.10` is absent from the local repo — an
> environment-only limitation unrelated to the migration. Integration tests were
> therefore run directly via `failsafe:integration-test failsafe:verify`.

---

## 2. What changed

### Main sources (SDK v1 → cloud-sdk / SDK v2)
- `module/OceanschedulesModule.java`, `module/OceanSchedulesDynamoModule.java` —
  Guice rewiring for `NotificationService`, `StorageClient`, raw `S3Client`.
- `config/OceanSchedulesConfig.java` — `dynamoDbConfig` → `BaseDynamoDbConfig`.
- `config/DynamoTableCommand.java` — SDK v2 table provisioning (GAP-7).
- `dynamodb/RealTimeCache.java`, `dynamodb/SchedulesProStaging.java` —
  `@DynamoDbBean` entities with epoch-second TTL converters.
- `persistence/cache/RealTimeCacheDao.java` + `RealTimeCacheConditionalWriter.java`
  (GAP-6 compare-and-set lock adapter).
- `persistence/portpair/SchedulesProStagingDao.java`.
- `util/AWSUtil.java`, `util/sns/SNSClient.java`, `util/s3/S3Service.java`
  (raw SDK v2 `S3Client` — GAP-3), `service/CarrierService.java`,
  `client/external/ExternalClient.java`.
- `pom.xml` — added cloud-sdk deps, removed v1 `dynamo-client`.

### Tests
- Rewrote `S3ServiceTest`, `CarrierServiceTest` to SDK v2 `S3Client` / `S3Object`.
- Fixed a stray brace in `SNSClientTest`.
- Added DynamoDB Local integration tests `RealTimeCacheDaoIT` and
  `SchedulesProStagingDaoIT` (modelled on the completed webbl / booking-bridge ITs,
  `extends BaseDynamoDbIT`, `@Tag("integration")`).

### Config
- Added `region: us-east-1` to `dynamoDbConfig` in
  `conf/{cvt,int,prod,qa}/config.yaml`.

---

## 3. Notable fix — DynamoDB Local dependency conflict

DynamoDB Local 2.5.2 failed to start with
`NoClassDefFoundError: com/amazonaws/services/dynamodbv2/model/OnDemandThroughput`.

**Cause:** the test dependency `integration-test-commons:1.0` pins
`aws-java-sdk-dynamodb:1.12.638` (no `OnDemandThroughput`), winning Maven mediation
over the `1.12.721` that DynamoDB Local 2.5.2 requires.

**Fix:** exclude `com.amazonaws:aws-java-sdk-dynamodb` from `integration-test-commons`
in `oceanschedules/pom.xml`, letting DynamoDB Local's `1.12.721` resolve. The new
ITs use only `dynamo-integration-test` (`BaseDynamoDbIT`), so dropping the stale
transitive jar is safe.

---

## 4. Cloud-sdk gaps still requiring commons changes

| Gap | Description | In-module workaround |
|-----|-------------|----------------------|
| GAP-3 | StorageClient lacks delimiter listing / batch delete | `S3Service` uses raw SDK v2 `S3Client` |
| GAP-4 | No multipart copy for objects > 5 GB | n/a (current objects small) |
| GAP-6 | No generic conditional save | `RealTimeCacheConditionalWriter` adapter |
| GAP-7 | DDL helper forces provisioned GSI throughput (invalid on-demand) | inline `createTable` in `DynamoTableCommand`; IT dependency exclusion |
| GAP-1/2 | SQS adapter / process module | pending (`oceanschedules-process`) |

---

## 5. Follow-up (not in this change)

- Migrate the 8 `oceanschedules-process` sub-modules (Kafka & Spark code remain
  unchanged) — GAP-1 / GAP-2 SQS adapters.
- Raise commons enhancements for GAP-3/4/6/7 to remove the in-module adapters.
