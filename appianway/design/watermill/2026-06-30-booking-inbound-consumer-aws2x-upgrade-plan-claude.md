# `booking-inbound-consumer` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury:booking-inbound-consumer` (sub-module of `watermill`) · Date: 2026-06-30 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`mercury-services-commons` `1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Guice **7.0.0**, Jackson **2.21.0**).
> Companion DESIGN: [`2026-06-30-booking-inbound-consumer-aws2x-upgrade-DESIGN-claude.md`](2026-06-30-booking-inbound-consumer-aws2x-upgrade-DESIGN-claude.md).
> MASTERs: [shared plan](../../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §10/§11 · [watermill plan](../../docs/2026-05-31-watermill-aws2x-upgrade-plan-claude.md).

---

## 0. Scope note (vs. the watermill aggregator plan)

`booking-inbound-consumer` is a **full pipeline-entry** consumer — like `visibility-inbound-consumer` but single-topic. The watermill aggregator plan under-describes it the same way: it is **also an active SQS producer (1 queue) and SNS publisher**, and it **depends on the `mercury-services` `booking` model jar** for `BookingRequestContract`. This per-module plan records those surfaces explicitly. Distinguishing traits vs. the S3-only siblings (itv-gps/cargoscreen) and vs. visibility-inbound:

| Trait | booking-inbound | itv-gps / cargoscreen | visibility-inbound |
|---|---|---|---|
| Topics / offsets | 1 | 1 | 3 |
| SQS send | **1 queue** | none | 3 queues |
| SNS publish | **yes** | dead binding | yes |
| Dynamo layer | **reuses `consumer-commons`** (no dup) | local duplicate | reuses `consumer-commons` |
| Model jar | **`booking:2.1.1.M`** | none | `visibility:1.0.M` |
| Tests | **JUnit 5** | JUnit 4 | JUnit 5 |

Everything else inherits the watermill plan unchanged.

---

## 1. Executive summary

`booking-inbound-consumer` is a Dropwizard 4 application running a single e2open Watermill gRPC booking-stream consumer. It parses proto `BookingChangeEvent`, transforms it to `BookingRequestContract` (via `BookingTransformer` + ~41 type-maps), archives JSON to S3 (`{rootWorkflowId}/{uuid}`), sends a `MetaData` envelope to one SQS queue (`bookingInboundQueueUrl`), logs `START`/`CLOSE_WORKFLOW` to SNS, persists one consumption offset in DynamoDB, and reads gRPC credentials from SSM. AWS footprint: **S3(write) + SQS(send) + SNS + DynamoDB(offset) + SSM** on AWS Java SDK **v1 `1.12.720`**, Dropwizard **4.0.16**, gRPC **1.77.0**.

Per the directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§5): consume cloud-sdk **as a client** (no cloud-sdk/commons change, **S-G2 not used**); the DynamoDB offset rides the **already-reused `consumer-commons`** remap; S3/SQS/SNS/SSM ride `shared`'s migrated wrappers; **align the `booking` model jar** so the SQS body stays byte-compatible with the booking workflow engine; move onto `InttraServer`/DW5. The gRPC layer is non-AWS and out of scope.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

AWS Java SDK **v1** `1.12.720`; Dropwizard `4.0.16`; gRPC `1.77.0`. Direct AWS deps via `consumer-commons` (`aws-java-sdk-sqs`, `aws-java-sdk-dynamodb`) and transitively via `shared` (`s3`, `sns`, `ssm`); `dynamo-client` supplies `DynamoDBCrudRepository` (v1 SDK jars excluded on its and the `booking` jar's deps).

### 2.1 S3 — write (metadata-free)
- `S3PublishService.uploadToS3(...)` → `s3Client.putObject(bucket, key, String payload)`; **no `ObjectMetadata`** (`S3PublishService:32-34`). Client `AmazonS3ClientBuilder.standard().build()` (`ExternalServicesModule:35`). Key `{YYYYMMdd}/{rootWorkflowId}/{randomUUID}` (`BookingInboundConsumer:128-129`); bucket = `s3WorkspaceConfig.bucket`. **⇒ S-G2 not required.**

### 2.2 SQS — producer (1 queue)
- `@Named("amazonSQSForSender") AmazonSQS` (`ExternalServicesModule:39`) → shared `SQSClient.sendMessage(target, content)` (`SQSClient:29-37`).
- Send: `sqsClient.sendMessage(bookingInboundQueueUrl, metaData.toJsonString())` (`BookingInboundConsumer:273`). One queue; **no `FAILED_ATTEMPTS`** attribute used here.

### 2.3 SNS — event publish
- `EventLogger.logCloseRunEvent(...)` (`BookingInboundConsumer:136-143/149-156`) → shared `SNSEventPublisher` (provided in `WatermillConsumerModule:56-58`) over `AmazonSNS` (`ExternalServicesModule`). Topic = `snsEventConfig.topicArn`. Emits `START_WORKFLOW` (success) and `CLOSE_WORKFLOW` (on `TransformationException`).

### 2.4 DynamoDB — single offset (reuses consumer-commons)
- **Reuses** `consumer-commons` `WatermillOffset`/`WatermillOffsetService`/`WatermillOffsetDao` (NOT a local duplicate). `@DynamoDBTable("watermill_offset")`, `@DynamoDBHashKey("topicName")`, `@DynamoDBAttribute offset/readDateTime/writeDateTime`, `@DynamoDBTypeConverted(DateToEpochSecond)`. Table prefix `"{environment}_watermill_offset"`; single topic → single row; one `OffsetUtil` + one `OffsetUpdateScheduler` (`BookingInboundConsumerApplication:57`).

### 2.5 SSM — gRPC credentials
- `AuthCredentials:28-31` reads `watermillServiceConfig.userIdKey`/`passwordKey` via shared `ParameterSupplier`/`ParameterStoreModule`.

### 2.6 Config / Dropwizard
- `BookingInboundConsumerApplication extends Application<BookingInboundConsumerConfiguration>`; `S3ConfigurationProvider` (conditional) + `ConfigProcessingServerCommand`; `ExternalServicesModule` + `WatermillConsumerModule`. **Tests: JUnit 5** (Jupiter `5.10.1`).

### 2.7 Model jar (module-specific)
- `BookingRequestContract` from `com.inttra.mercury:booking:2.1.1.M` (pom :85-86). The `booking` pom excludes v1 SDK jars (`aws-java-sdk-{sns,sqs,dynamodb,datapipeline}`) — consistent with `booking` being an already-cloud-sdk-upgraded `mercury-services` consumer. ~41 transformer/type-map classes map proto → contract.

---

## 3. Findings

- **The offset store is the only correctness-critical AWS surface** and it **already rides `consumer-commons`** — no local duplicate to delete (unlike itv-gps/cargoscreen). Highest risk remains offset backward-compat (wrong table/attribute → re-consumption from 0 → duplicate booking workflows).
- **SQS (1 queue) + SNS are real surfaces** — `sendMessage` → `MessagingClient<String>.sendMessage`; `EventLogger` → `NotificationService`. Body = `MetaData.toJsonString()`; the heavy `BookingRequestContract` lives in S3, so SQS stays small.
- **S3 write is metadata-free ⇒ S-G2 not consumed.**
- **`booking` model jar is a cross-workspace contract.** Align the version so `BookingRequestContract` JSON stays byte-compatible with the booking workflow engine; the jar already excludes v1 SDK so it should not drag AWS v1 back in.
- **Already JUnit 5** — no vintage bridge.
- **gRPC** (topic, reconnect) is non-AWS — untouched.

---

## 4. Option A — keep DW4; swap AWS internals to cloud-sdk

Keep DW 4.0.16/app/`ConfigProcessingServerCommand`; offset rides the `consumer-commons` remap; rebind S3 → `StorageClient`, SQS → `MessagingClient<String>`, SNS → `NotificationService`, SSM → `CloudParameterStore` via migrated `shared`; align the `booking` jar.

- **Pros:** smallest blast radius; reversible; identical cloud-sdk consumption to Option B.
- **Cons:** keeps bespoke DW4 base; diverges from the cloud-sdk-aligned `booking` platform.
- **Effort:** Low–Medium. **Risk:** Low–Medium.

---

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A plus moving the application onto `commons` `InttraServer` (DW 5.0.1) with the composed appianway `ServerCommand`. Keep the gRPC consumer, transformers/type-maps, single `OffsetUpdateScheduler`.

- **Pros:** platform convergence with the booking platform it feeds; one AWS abstraction; removes bespoke DW plumbing.
- **Cons:** DW4→5 on a live booking feed; config composition work.
- **Effort:** Medium. **Risk:** Medium.

---

## 6. Comparison matrix

| Criterion | Option A (DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 → cloud-sdk | ✅ | ✅ |
| Required cloud-sdk change | none (no S-G2) | none (no S-G2) |
| Impact on mercury-services | none | none |
| Effort | Low–Medium | Medium |
| Risk | Low–Medium | Medium |
| Framework churn | none (already JUnit 5) | DW4→5 |
| Consistency w/ booking platform | AWS layer only | full |
| Incremental / reversible | ✅ | stage carefully |

> **Verdict:** the directive makes **Option B** authoritative; both share the identical cloud-sdk contract and zero cloud-sdk changes. A late A↔B switch costs nothing at the AWS layer.

---

## 7. Recommendation

**Adopt Option B**, consuming cloud-sdk `1.0.26-SNAPSHOT` as a client with **no cloud-sdk change and no S-G2**. The offset rides the `consumer-commons` remap (no local cleanup needed here); the focus is rebinding S3/SQS/SNS/SSM and **aligning the `booking` model jar** so the SQS body stays byte-compatible with the booking workflow engine.

> **Residual caution:** preserve the offset table/attribute shape; verify the `BookingRequestContract` JSON shape after any `booking` jar bump; sequence DW4→5 after `shared`.

---

## 8. Peer review (incorporated)

- **Offset round-trip** — `dynamo-integration-test` fixture seeded from the real booking item; gate cutover. **Resolved (test plan).**
- **SQS body** — `MetaData.toJsonString()`; heavy contract offloaded to S3; assert send on success / none on failure. **Resolved.**
- **S3 metadata** — metadata-free `putObject`; **no S-G2.** **Resolved.**
- **`booking` model jar** — align version; add SQS-body contract test. **Tracked (§9).**
- **JUnit** — already Jupiter; no bridge. **Resolved.**
- **Credential/region parity** — v2 default providers; `regionEndpoint`/`signingRegion` → `DynamoDbClientConfig`. **Resolved (verify in dev run).**

---

## 9. Open questions / dependencies / sequencing

- **Depends on:** `consumer-commons` Dynamo pilot landing first; `shared` + `functional-testing` migrating before S3/SQS/SNS/SSM rebind; the aligned `booking` jar version.
- **Open question:** the exact `booking` jar coordinate/version to align to (does `BookingRequestContract` move package or change fields in the cloud-sdk-aligned release?); whether the v2 create path must set `@DynamoDBStream(KEYS_ONLY)`.
- **Sequencing:** offset remap (consumer-commons) → rebind S3/SQS/SNS/SSM → align `booking` jar + recompile transformers → DW5/`InttraServer` move → `mvn -pl watermill/booking-inbound-consumer -am verify` → aggregator `mvn verify`.
- **Cutover gate:** backward-compat offset fixture **and** an SQS-body contract check against the booking workflow engine.

---

## 10. Configuration changes (ref master §10)

- **Preserve all keys:** booking topic name, `bookingInboundQueueUrl`, `snsEventConfig.topicArn`, `s3WorkspaceConfig.bucket`, `dynamoDbConfig.{environment,regionEndpoint,signingRegion,sseEnabled}`, `watermillServiceConfig.{userIdKey,passwordKey,...}`.
- **DynamoDB:** explicit physical `tableName = "{environment}_watermill_offset"`; `DynamoDbClientConfig.endpointOverride(regionEndpoint)` + `Region.of(signingRegion)`; SSE/throughput on create.
- **Credentials/region:** env/IAM via v2 default providers; `${PROFILE}/${ENV}` unchanged; any `${awsps:…}` via commons `ParameterStoreConfigTransform`.
- **Option B:** register the composed appianway `ServerCommand` on the `InttraServer` bootstrap.
- **Retry/timeout:** reapply the v1 `sqs_sender`/`sns_publish` tuning via `ClientOverrideConfiguration` + `ApacheHttpClient` at the shared/factory boundary.

---

## 11. cloud-sdk gaps — **NONE for booking-inbound-consumer**

| Need | cloud-sdk artifact (existing) |
|---|---|
| Single offset store | `DatabaseRepository`/`DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminCommand`, `dynamo-integration-test` |
| S3 write (metadata-free) | `StorageClient.putObject(bucket,key,bytes)` — **S-G2 not needed** |
| SQS send (1 queue) | `MessagingClient<String>.sendMessage(url, body)` |
| SNS event publish | `NotificationService` (via shared `SNSEventPublisher`/`EventLogger`) |
| SSM gRPC credentials | `CloudParameterStore` (via shared `ParameterStore`) |
| DW5 base + config | `commons` `InttraServer` + composed appianway `ServerCommand` |

No `cloud-sdk-api`/`cloud-sdk-aws`/`commons` change required. The only module-specific non-library task is **aligning the `booking` model jar** version and recompiling the transformers (§7, §9).

---

> **Scope boundary.** The gRPC/Watermill consumption layer (`e2open.watermill.proto.*` `BookingChangeEvent`, `BookingInboundConsumer`, `BookingTransformer` + ~41 type-maps, reconnect) is **not AWS** and is out of scope — carried unchanged through both options.
