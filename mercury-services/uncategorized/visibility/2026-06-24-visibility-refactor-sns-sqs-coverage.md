# Visibility — SNS/SQS Completion, Config Re-alignment & Coverage Hardening

**Jira**: ION-12316
**Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot`
**Date**: 2026-06-24
**Model**: Claude Opus 4.8 (1M context)
**Backup**: branch `feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-24`, tag `ION-12316-pre-coverage-backup-2026-06-24` (pre-change tip `35c1414cdd`)
**Pushed commit**: `dd46b95a3460f6a171a864b657284476953ffc63` (`dd46b95a34`) — single outgoing commit on `feature/ION-12316-visibiilty-aws-upgrade-copilot` (force-with-lease over `35c1414cdd`); PR [#1066](https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/1066)
**Prior write-up (read first)**: [`2026-06-23-visibility-rebase-refactor.md`](./2026-06-23-visibility-rebase-refactor.md)
**Prompt**: `.github/prompts/refactor/2026-06-24-visibility-refactor-sns-sqs-config-coverage.prompt.md`

---

## 1. Summary

This change continues the ION-12316 visibility AWS SDK 2.x (cloud-sdk) upgrade. It re-aligns the DynamoDB
configuration with the `booking`/`network` modules, hardens DynamoDB DAO + converter backward-compatibility with
exhaustive unit and DynamoDB-Local **integration** tests, restores the legacy S3 client tuning that
`createDefaultS3Client()` dropped, fixes a **latent `java.util.Date` schema bug** in `CargoVisibilitySubscription`,
adds integration coverage for the `visibility-s3-archiver` lambda, raises the Sonar new-code coverage for the listed
classes, and documents the remaining SQS/SNS backbone migration with a concrete plan.

Everything is verified with `mvn verify -f visibility/pom.xml` (unit + integration + DynamoDB Local). The work
was landed as a single commit referencing `ION-12316` and pushed with `--force-with-lease`:
**`dd46b95a34`** (full SHA `dd46b95a3460f6a171a864b657284476953ffc63`), PR #1066.

> **Headline correction to the 2026-06-23 §6 note:** the SQS/SNS backbone migration does **not** require the
> `commons` 1.0.26 (Dropwizard 5 / Jakarta) bump. The cloud-sdk `1.0.26` already ships a **consumer** messaging API
> (`MessagingClient.listMessages/receiveMessages/deleteMessage` + `QueueMessage`) and `NotificationService` for SNS, so
> the backbone can migrate on the current dependency set (see §10).

---

## 2. Goal-by-goal outcome

| # | Goal | Status |
|---|------|--------|
| 1 | Reuse existing `dynamoDbConfig`, drop `cloudSdkDynamoDbConfig` | ✅ Done |
| 2 | Complete SQS + SNS cloud-sdk migration | ⏳ Documented + planned (see §10) — not landed this pass; see reason/TODO |
| 3 | Add integration tests where possible | ✅ Done (DAO round-trips, WM, s3-archiver lambda) |
| 4 | DynamoDb CRUD + boundary tests | ✅ Done |
| 5 | AssertJ + `@Nested` + `@ParameterizedTest` | ✅ Done |
| 6 | S3 client socket-timeout / max-connections vs `createDefaultS3Client()` | ✅ Done (gap + fix) |
| 7 | Rework `*DaoIT` comments → full CRUD + all GSIs + boundaries | ✅ Done |
| 8 | Exhaustive converter `transformFrom`/`transformTo` tests | ✅ Done |
| 9 | Verify every DAO is 1.x-compatible | ✅ Done (found + fixed a real bug) |
| 10 | Round-trip ITs for the DAOs | ✅ Done |
| 11 | Document lambda AWS-client injection | ✅ Done (§9) |
| 12 | s3-archiver direct `DynamoDbClient` gap + lambda IT | ✅ Done (gap documented + IT added) |
| 13 | Package modules + verify Dropwizard INT init | ✅ Done (see §11) |
| 14 | Sufficient logging for init + main events | ✅ Reviewed; additions noted (§12) |
| 15 | Sonar new-code coverage for the listed classes | ✅ Done (§13) |

---

## 3. Goal 1 — DynamoDB config re-alignment

**Finding.** `booking`/`network` expose a **single** `dynamoDbConfig` field of cloud-sdk type
`BaseDynamoDbConfig`. Visibility diverged: it kept the legacy `dynamoDbConfig` (`com.inttra.mercury.dynamo…DynamoDbConfig`)
**and** added a separate `cloudSdkDynamoDbConfig` (`BaseDynamoDbConfig`). The legacy getter was referenced only by a
test, never by main code.

**Change.**
- `VisibilityApplicationConfig.dynamoDbConfig` retyped to `BaseDynamoDbConfig`; `cloudSdkDynamoDbConfig` field +
  accessors removed; added a `setDynamoDbTableCreationCommandConfig` setter.
- `VisibilityDynamoModule` and `VisibilityInboundDynamoDbAdminCommand` now read `getDynamoDbConfig()`.
- All **36** `config.yaml` files: the `cloudSdkDynamoDbConfig:` block was removed and its `sseEnabled` merged into the
  single `dynamoDbConfig:` block. The cloud-sdk `environment` equalled the legacy `environment` in **every** file, so
  physical table names are unchanged.

**Backward-compat proof.** `VisibilityDynamoModuleTest` builds the real repositories and the logs show the legacy
physical names: `inttra_int_container_events`, `inttra_int_container_events_outbound`,
`inttra_int_container_events_pending`, `inttra_int_booking_BookingDetail`.

---

## 4. Goals 4/7/9/10 — DAO backward-compatibility, CRUD, GSIs, round-trip ITs

**Per-DAO 1.x compatibility check** (Goal 9). `VisibilityDynamoModuleTest` constructs the **real** cloud-sdk
repositories for `ContainerEvent`, `ContainerTrackingEvent`, `ContainerEventOutbound`, `ContainerEventPending` and
`BookingDetailVisibility` — all build cleanly. This exercise surfaced a **real latent bug** in
`CargoVisibilitySubscription` (§7).

**`ContainerEventDaoIT`** (Goal 7) — the class javadoc was reworded: backward-compat **is** covered **and** full CRUD
is exercised across **every** GSI plus boundary conditions and data formats. New coverage:
- **All 5 GSIs** queried via a `@ParameterizedTest` (`bookingNumber-index`, `blNumber-index`,
  `equipmentIdentifier-index`, `bkInttraReferenceNumber-equipmentIdentifier-index`, `siInttraReferenceNumber-index`)
  plus an empty-result case.
- CRUD: `update` round-trip and `findAll` batch (incl. a missing id).

**New round-trip ITs** (Goal 10), DynamoDB Local via `BaseDynamoDbIT`:
- `ContainerEventOutboundDaoIT` — composite-key create/read + the `getUnprocessedTransactions` range query + boundaries.
- `ContainerEventPendingDaoIT` — create / `BEGINS_WITH` query / delete + boundaries.
- `CargoVisibilitySubscriptionDaoIT` — create/read, both GSIs, and the legacy Date on-disk format (§7).

**New DAO unit tests** (Goal 4 / coverage): `ContainerEventDao` (`findOne`, `findAll`, `queryIndex`, GPS-hash-key
branches), `ContainerEventOutboundDao.findOne`, `ContainerEventPendingDao.delete`.

---

## 5. Goal 8 — Exhaustive converter tests

Added `transformFrom`/`transformTo` unit tests (AssertJ + `@Nested`, parameterized boundaries for the date converters)
for the SDK-2.x `AttributeConverter`s that previously had **no** tests:
`ContainerEventSubmissionAttributeConverter`, `ContainerEventEnrichedPropertiesAttributeConverter`,
`SubscriptionAttributeConverter`, `GISOutboundDetailsAttributeConverter`, `DateIso8601AttributeConverter`,
`DateEpochMilliSecondAttributeConverter`, `ContainerTrackingEventMessageAttributeConverter`, plus a shared
`ConverterTestSupport` helper (builds a legacy Map (M) attribute from a POJO).

Every test asserts: `null → NUL`; the **on-disk byte-identical** `S`/`N` format vs the converter's own `ObjectMapper`
(the legacy-compat contract); read of `S`; lenient read of a legacy Map (M); `empty/NUL → null`; and the `type()` /
`attributeValueType()` metadata.

---

## 6. Goal 6 — S3 client socket-timeout / max-connections

**Finding.** The pre-upgrade `VisibilityApplicationInjector.bindS3()` built `AmazonS3` with
`connectionTimeout=1000ms`, `socketTimeout=5000ms`, `maxConnections=50`, `maxErrorRetry=3`. The migrated code used
`StorageClientFactory.createDefaultS3Client()`, which applies **AWS SDK 2.x defaults** (≈2s connect / **30s** read /
50 max-connections) — so the **read timeout silently changed 5s → 30s** and connect 1s → 2s.

**cloud-sdk gap.** `AwsStorageConfig`'s builder has **no** first-class `socketTimeout`/`connectionTimeout`/
`maxConnections` knobs; the only lever is `httpClient(AwsHttpClientWrapper)`.

**Fix.** `bindStorageClient()` now builds the config explicitly with a custom Apache `SdkHttpClient`
(`apache-client` 2.30.24 is already on the classpath) carrying the legacy 1s/5s/50 values, via
`StorageClientFactory.createS3Client(visibilityS3StorageConfig())`. The values are `S3_CONNECTION_TIMEOUT` /
`S3_SOCKET_TIMEOUT` / `S3_MAX_CONNECTIONS` constants. Region resolves from `DefaultAwsRegionProviderChain`; credentials
from `DefaultCredentialsProvider`.

> **Note / TODO (cloud-sdk):** `createS3Client(config)` **requires** an explicit `credentialsProvider` (it does not fall
> back to the default chain like `createDefaultS3Client()` does). Recommend adding timeout/max-connection setters to
> `AwsStorageConfig.Builder` (and a default-credentials fallback) so callers don't have to hand-build an `ApacheHttpClient`.

Covered by `VisibilityApplicationInjectorTest` (constants, config carries a custom Apache client, the injector resolves
a `StorageClient`).

---

## 7. Goal 9 (bug) — `CargoVisibilitySubscription` `java.util.Date` schema failure

**Bug.** `CargoVisibilitySubscription.createdOn` and `modifiedOn` are `java.util.Date` with **no**
`@DynamoDbConvertedBy`. The AWS SDK 2.x Enhanced Client has **no built-in `java.util.Date` converter**, so building the
real repository throws `IllegalStateException: Converter not found for EnhancedType(Date)`. This was **masked** because
every existing test mocked the repository — the real construction path was never exercised. The WM processor would have
failed at startup.

**1.x format.** On `develop`, these fields used `@DynamoDBAttribute` with **no** converter, i.e. the DynamoDBMapper
**default** `Date` marshalling: an ISO-8601 UTC **String** `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`
(`com.amazonaws.util.DateUtils.formatISO8601Date`). `expiresOn` used `DateToEpochSecond` (→ `DateEpochSecondAttributeConverter`, already correct).

**Fix.** New `LegacyDynamoDbDateAttributeConverter` (`java.util.Date` ↔ ISO-8601 UTC `S`, lenient read of numeric epoch
seconds/millis) + explicit `getCreatedOn()`/`getModifiedOn()` getters annotated with it.

**Verification.** `VisibilityWMDynamoModuleTest` (real repo now builds), `LegacyDynamoDbDateAttributeConverterTest`
(10 tests), and `CargoVisibilitySubscriptionDaoIT` (asserts `createdOn`/`modifiedOn` stored as ISO-8601 `S`, `expiresOn`
as `N`, plus both GSIs and case-insensitive id lookup).

---

## 8. Goal 12 — `visibility-s3-archiver` direct `DynamoDbClient`

**Why it resolves the raw client.** `HandlerSupport.getDynamoDbClient()` + `VisibilityS3Archiver` do a **schemaless**
`GetItem` on `<env>_container_events` and archive **whatever attributes exist** as a generic `Map<String,Object>`. There
is **no `@DynamoDbBean`** for this read — the archive must faithfully serialize arbitrary stored attributes.

**Booking comparison.** `booking`'s `S3ArchiveHandler` does **not** resolve a raw client: it reads a **typed**
`BookingDetail` through the cloud-sdk `BookingDetailDao` (it has a bean) and reads the keys from the DynamoDB **stream
event**. So the difference is *typed read* (booking) vs *schemaless raw read* (visibility).

**Conclusion — genuine cloud-sdk gap.** `cloud-sdk-api`'s `DatabaseRepository<T,K>` is **bean-typed only**; there is no
low-level "get raw item by key → `Map<String,CloudAttributeValue>`" operation. The visibility archiver legitimately
needs schemaless access, so dropping to the AWS SDK 2.x `DynamoDbClient` is the correct, narrowly-scoped exception.

> **TODO (cloud-sdk enhancement):** add a `RawItemRepository`/`getItem(tableName, key) → Optional<Map<String,CloudAttributeValue>>`
> (and a matching factory) to `cloud-sdk-api`/`-aws` so lambdas like the archiver don't bypass the abstraction. Until
> then, the direct `DynamoDbClient` use is documented and accepted.

**IT added.** `VisibilityS3ArchiverIT` (3 tests, DynamoDB Local) persists a real `ContainerEvent` through the cloud-sdk
converters and drives `handleRequest` through the **raw** client read + archive: a `MODIFY` event writes the archive
JSON to a mocked `StorageClient`; `GPS` and `REMOVE` events are skipped.

---

## 9. Goal 11 — Lambda AWS-client injection (documentation)

The visibility lambdas do **not** use Guice; they wire AWS clients through a static `HandlerSupport` per module, all on
the cloud-sdk factories (AWS SDK 2.x), with region/credentials from the default provider chains:

| Lambda | Client wiring (`HandlerSupport`) |
|--------|----------------------------------|
| `visibility-s3-archiver` | `StorageClientFactory.createDefaultS3Client()` (S3); **raw** `DynamoDbClient.builder()` with 3 retries (schemaless read, §8); `ObjectMapper` with Joda + JavaTime + custom `LocalDateTime` pattern |
| `visibility-outbound-poller` | `MessagingClientFactory.createDefaultStringClient()` (SQS); `ParameterStoreClientFactory.createParameterStore(...)` (SSM, lazy); region via `DefaultAwsRegionProviderChain` |
| `visibility-pending-start` | same pattern (SQS + parameter store) |

The Dropwizard **services** (inbound/outbound/pending/matcher/itv-gps/wm) inject AWS clients via Guice (`VisibilityApplicationInjector`,
`VisibilityDynamoModule`, `VisibilityWMDynamoModule`). Contrast with `booking`, whose lambdas inject a typed
`BookingDetailDao` (cloud-sdk repository) rather than a raw client.

---

## 10. Goal 2 — SQS/SNS backbone migration (plan; not landed this pass)

**Reason it is documented rather than landed now.** The legacy `SqsMessageHandler` exposes its work unit as an AWS SDK
v1 `com.amazonaws.services.sqs.model.Message` (`Consumer<Message>`). Migrating the consumer backbone to the cloud-sdk
`MessagingClient<String>` changes that work-unit type to `QueueMessage<String>`, which **ripples through ~12 main
classes and ~30 test files** (every processor that builds the task, plus `SqsMessageHandlerManager` and the SNS
publisher path). There is no clean, independently-verifiable small slice — it is effectively all-or-nothing for the
backbone — and a true end-to-end verification needs live SQS/SNS. Landing a partial migration would destabilize the
**currently green** build, so it is captured here as the primary follow-up with a concrete, low-risk plan. This does
**not** block the config/coverage/DAO goals delivered in this commit.

**Feasibility (confirmed).** cloud-sdk `1.0.26` already provides the full surface (no DW5/Jakarta bump needed):

| Legacy (`com.inttra.mercury.messaging.*`) | cloud-sdk `1.0.26` replacement |
|---|---|
| `sqs.SQSClient.receiveMessage(url,n,wait) → List<Message>` | `messaging.api.MessagingClient.listMessages(url,n,wait) → List<QueueMessage<String>>` |
| `sqs.SQSClient.sendMessage(url, body)` | `MessagingClient.sendMessage(url, payload[, attrs])` |
| `sqs.SQSClient.deleteMessage(url, receipt)` | `MessagingClient.deleteMessage(url, receipt)` |
| `Message.getMessageId/getReceiptHandle/getBody/getAttributes` | `QueueMessage.getMessageId/getReceiptHandle/getPayload/getAttributes` |
| `sns.SNSClient` / `logging.SNSEventPublisher` | `notification.api.NotificationService` / `notification.impl.SnsService` / `notification.workflow.SnsEventPublisher` |
| `messaging.model.MetaData/Event`, `logging.Event*`, `annotation.*`, `util.RandomGenerator` | `cloudsdk.notification.workflow.*` / `notification.annotation.*` / `notification.util.RandomGenerator` |

**Ordered plan (TODO).**
1. Introduce a `MessagingClient<String>` Guice provider (via `MessagingClientFactory`) and a `NotificationService`
   provider (via the notification factory); add the messaging/notification config blocks to each `config.yaml`
   (mirroring `booking`).
2. Change `SqsMessageHandler` to consume `QueueMessage<String>` (replace `receiveMessage`→`listMessages`,
   `deleteMessage(url, receiptHandle)`, DLQ `sendMessage`), and update `Consumer<Message>` → `Consumer<QueueMessage<String>>`.
3. Update each consumer that builds the task: `-inbound` `CargoVisibilityService`/`InboundEdiProcessor`/`ReprocessService`;
   `-matcher` `MatchingProcessor`/`AbstractMatcher`; `-outbound` `Outbound*Processor`/`OutboundGenerator`; `-pending`
   `PendingSqsProcessor`; `-itv-gps` `GPSEventProcessor`; `-wm` `WMEventProcessor`.
4. Migrate the SNS publisher (`VisibilityApplicationInjector` `SNSEventPublisher`) to `SnsEventPublisher`/`NotificationService`;
   replace `SQSModule`/`SNSModule` with the cloud-sdk factories.
5. Remap the 1:1 `messaging.*` classes to `cloudsdk.notification.*`.
6. Rewrite the ~30 affected tests to mock `MessagingClient`/`NotificationService`; add a DynamoDB-Local/localstack-style
   IT for at least one consumer.
7. Remove the legacy `SQSClient`/`SNSClient` deps once all references are gone.

---

## 11. Goal 13 — Package & INT startup

`mvn -f visibility/pom.xml clean verify` builds and packages all modules and runs unit + integration tests (incl.
DynamoDB Local). Dropwizard configuration deserialization of the re-aligned `dynamoDbConfig` block is exercised by the
config tests; the migrated apps resolve the table prefix from `dynamoDbConfig.environment` and the table names match the
legacy physical names (§3), so no `IllegalStateException`/`ResourceNotFound` at boot. Full `server` startup against INT
additionally needs live AWS (DynamoDB/SQS/ES) and is validated in the INT environment.

**Packaging.** `mvn -f visibility/pom.xml clean verify` → **BUILD SUCCESS**, all **12** modules; 11 executable
sub-module jars produced under `visibility/*/target/`.

**Dropwizard INT config deserialization** (the HIGH-2 startup concern) verified offline with the `check` command —
each prints `Configuration is OK`:

```
java -jar visibility/visibility-inbound/target/visibility-inbound-1.0.jar  check visibility/visibility-inbound/conf/int/config.yaml   # Configuration is OK
java -jar visibility/visibility-matcher/target/visibility-matcher-1.0.jar  check visibility/visibility-matcher/conf/int/config.yaml   # Configuration is OK
java -jar visibility/visibility-outbound/target/visibility-outbound-1.0.jar check visibility/visibility-outbound/conf/int/config.yaml  # Configuration is OK
java -jar visibility/visibility-pending/target/visibility-pending-1.0.jar  check visibility/visibility-pending/conf/int/config.yaml   # Configuration is OK
```

This proves the re-aligned single `dynamoDbConfig` (`BaseDynamoDbConfig`) block deserializes and validates with no
`cloudSdkDynamoDbConfig` present. Full `server` startup against INT additionally needs live AWS (DynamoDB/SQS/ES).

---

## 12. Goal 14 — Logging review

- `VisibilityApplicationInjector` now logs S3 client creation with the resolved timeouts/max-connections.
- `VisibilityDynamoModule`/`VisibilityWMDynamoModule` already log module configuration and per-repository/table creation
  (confirmed in test output: e.g. *"Creating ContainerEvent partition-key repository for table: inttra_int_container_events"*).
- DAOs, `SqsMessageHandler`, services and processors already use `@Slf4j` with DEBUG/INFO/WARN/ERROR at the main events
  (message received/processed, DLQ, delete, query failures, retries). No PII/secret logging was introduced.

---

## 13. Goal 15 — Sonar new-code coverage

| Class | Before | Action |
|-------|--------|--------|
| a) `VisibilityApplicationConfig` | 3 lines, 0% | Rewrote `VisibilityApplicationConfigTest` (AssertJ/`@Nested`, all accessors + `getTableConfig`) |
| b) `VisibilityApplicationInjector` | 1 line, 0% | `S3StorageClient` tests (constants, config, client, injector resolves) |
| c) `VisibilityDynamoModule` | 49 lines, 8 cond, 0% | New `VisibilityDynamoModuleTest` (injector builds all DAOs + client config + missing-config guard) |
| d) `ContainerEventDao` | 13 lines, 56.7% | Added `findOne`/`findAll`/`queryIndex`/GPS-branch tests |
| e) `VisibilityInboundDynamoDbAdminCommand` | 1 line, 1 cond, 76.5% | Added the success path (table-prefix) test |
| f) `ContainerEventTableDao` | 2 cond, 86.7% | Covered by the inbound module tests / IT path |
| g) `ContainerEventOutboundDao` | 1 line, 93.8% | Added `findOne` test + IT |
| h) `ContainerEventPendingDao` | 1 line, 93.8% | Added `delete` test + IT |
| i) `VisibilityWMDynamoModule` | 16 lines, 2 cond, 0% | New `VisibilityWMDynamoModuleTest` + DAO IT |
| j) `CargoVisibilitySubscriptionDao` | 7 lines, 50% | Existing exhaustive unit tests + new round-trip IT |
| k) `visibility-s3-archiver HandlerSupport` | 5 lines, 0% | New `HandlerSupportTest` (8 tests) |
| l) `visibility-outbound-poller HandlerSupport` | 20 lines, 0% | New `HandlerSupportTest` (8 tests) |

---

## 14. Test & build results

`mvn -f visibility/pom.xml clean verify` → **BUILD SUCCESS** for all 12 modules; **0 failures, 0 errors** across all
unit + integration (DynamoDB Local) tests. The 6 skips are pre-existing in unrelated lambda `HandlerSupportTest`s.

New tests added this pass (all green):
- `visibility-commons`: `VisibilityApplicationConfigTest` (rewrite), `VisibilityDynamoModuleTest`,
  `VisibilityApplicationInjectorTest` (+S3 config), `ContainerEventDaoTest` (+6), `ContainerEventOutboundDaoTest` (+2),
  `ContainerEventPendingDaoTest` (+1); 7 `*AttributeConverterTest` classes + `ConverterTestSupport`;
  `ContainerEventDaoIT` (expanded: all 5 GSIs + CRUD), `ContainerEventOutboundDaoIT`, `ContainerEventPendingDaoIT`.
- `visibility-inbound`: `VisibilityInboundDynamoDbAdminCommandTest` (rewrite + success path).
- `visibility-wm-inbound-processor`: `VisibilityWMDynamoModuleTest`, `LegacyDynamoDbDateAttributeConverterTest` (10),
  `CargoVisibilitySubscriptionDaoIT` (5, DynamoDB Local).
- `visibility-s3-archiver`: `HandlerSupportTest` (8), `VisibilityS3ArchiverIT` (3, DynamoDB Local).
- `visibility-outbound-poller`: `HandlerSupportTest` (8).

Production changes: `VisibilityApplicationConfig`, `VisibilityDynamoModule`, `VisibilityApplicationInjector`,
`VisibilityInboundDynamoDbAdminCommand`, all 36 `config.yaml`, `CargoVisibilitySubscription` (+ new
`LegacyDynamoDbDateAttributeConverter`), and IT infra in the `wm` / `s3-archiver` poms.

---

## 15. References

- ION-12316
- Prior doc: `visibility/docs/2026-06-23-visibility-rebase-refactor.md`
- Reference modules: `booking` (`BookingConfig`, `BookingDynamoModule`, `S3ArchiveHandler`), `network`
- cloud-sdk `1.0.26`: `MessagingClient`/`QueueMessage`, `NotificationService`, `AwsStorageConfig`, `BaseDynamoDbConfig`
