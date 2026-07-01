# `visibility-inbound-consumer` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury:visibility-inbound-consumer` (sub-module of `watermill`) · Date: 2026-06-30 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`mercury-services-commons` `1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Guice **7.0.0**, Jackson **2.21.0**).
> Companion DESIGN: [`2026-06-30-visibility-inbound-consumer-aws2x-upgrade-DESIGN-claude.md`](2026-06-30-visibility-inbound-consumer-aws2x-upgrade-DESIGN-claude.md).
> MASTERs: [shared plan](../../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §10 (config) / §11 (cloud-sdk change list) · [watermill plan](../../docs/2026-05-31-watermill-aws2x-upgrade-plan-claude.md) (offset-store remap + `consumer-commons` consolidation).

---

## 0. What this document adds vs. the watermill aggregator plan (scope note)

The [watermill aggregator plan](../../docs/2026-05-31-watermill-aws2x-upgrade-plan-claude.md) covers all five consumers **uniformly**, characterising the consumer AWS surface as *"the DynamoDB `watermill_offset` cursor store, plus a metadata-free S3 write, SNS publish, and SSM credential lookup that ride `shared`"*, with SQS framed as not-a-producer. That generalisation is accurate for `cargoscreen-consumer` and `itv-gps-consumer` (which are **S3-only sinks**), but it **under-describes `visibility-inbound-consumer`**, which is materially larger:

| Surface | watermill aggregator framing | `visibility-inbound-consumer` reality |
|---|---|---|
| Watermill gRPC topics | 1 | **3** (container / CW-subscription / CW-event) |
| Offset rows / schedulers | 1 | **3** (one per topic) |
| SQS | "consumer is not a producer" | **active producer to 3 queues** (`SQSClient.sendMessage`) |
| SNS | rides shared | rides shared (✔, confirmed) |
| S3 | metadata-free write | metadata-free write (✔ — **S-G2 not needed**) |
| Reconnect | per-observer | **`ConsumerManager`** (reused observer, swapped channel) |
| Domain model | none | **depends on `mercury-services` `visibility` model jar** (`1.0.M`) |

This per-module plan therefore (a) inventories the **SQS-producer** and **SNS** surfaces explicitly, (b) records the **three-topic / three-offset / three-scheduler** topology, and (c) adds the **`visibility` model-jar version alignment** with ION-12316 as a first-class dependency and risk — none of which the aggregator plan addresses. Everything else (DynamoDB offset remap, consolidation onto `consumer-commons`, Option B, no cloud-sdk gaps) **inherits the watermill plan unchanged**.

---

## 1. Executive summary

`visibility-inbound-consumer` is a Dropwizard 4 application that runs **three concurrent e2open Watermill gRPC stream consumers**, transforms each protobuf event into an INTTRA `visibility` domain model, archives the payload to S3, and routes a `MetaData` envelope to one of three SQS queues consumed by the `mercury-services` `visibility` service; it also publishes workflow events to SNS and persists a **per-topic consumption offset** in DynamoDB. Its AWS v1 footprint is **S3 + SQS(send) + SNS + DynamoDB + SSM**, all on AWS Java SDK **v1 `1.12.720`**, Dropwizard **4.0.16**.

Per the program directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§5), implemented so that:

1. appianway consumes cloud-sdk **as a client only** — **no cloud-sdk/commons change**, and **S-G2 is not used** (all S3 writes are metadata-free);
2. the **DynamoDB offset store** is remapped to cloud-sdk's `DatabaseRepository`/`@Table`/`LongEpochSecondAttributeConverter`, **consolidated in `consumer-commons`** (the watermill pilot), preserving the **exact physical table name and attribute names per topic**;
3. **S3/SQS/SNS/SSM** ride `shared`'s migrated wrappers (`S3WorkspaceService`/`S3PublishService`, `SQSClient`→`MessagingClient<String>`, `SNSEventPublisher`→`NotificationService`, `ParameterStore`→`CloudParameterStore`);
4. the **`visibility` model jar is bumped** to the ION-12316 cloud-sdk-aligned release so the transformer output stays byte-compatible with `mercury-services` `visibility`;
5. the application moves onto `commons` `InttraServer`/DW5 with the composed appianway config command, **retaining the three offset schedulers and `ConsumerManager`**;
6. rollout is staged behind `mvn -pl <module> -am verify` and gated on a **per-topic backward-compat offset fixture** + an **SQS body contract check** against the downstream visibility processor.

The gRPC/Watermill layer (`e2open.watermill.proto`, the three `StreamObserver`s, transformers, type-maps, `ConsumerInitUtil`, the >10 MB `maxInboundMessageSize` from ION-15497) is **not AWS and is out of scope**.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

AWS Java SDK **v1** (`com.amazonaws.*`) `1.12.720`; Dropwizard `4.0.16`; gRPC `1.77.0`. Direct AWS deps live in `consumer-commons` (`aws-java-sdk-sqs`, `aws-java-sdk-dynamodb`) and transitively via `shared` (`s3`, `sns`, `ssm`); the `dynamo-client` jar supplies the in-house `DynamoDBCrudRepository` over v1.

### 2.1 S3 — archive (metadata-free)
- `consumer-commons` `S3PublishService.uploadToS3(bucket, fullS3Path, payload)` → `s3Client.putObject(bucket, key, String payload)`; **`PutObjectResult` ignored**; **no `ObjectMetadata`/content-type**. Date-partitioned key `YYYYMMdd/UUID/...`.
- Client built in `ExternalServicesModule` via `AmazonS3ClientBuilder.standard().build()` (default credential/region chain).
- **⇒ S-G2 not required.**

### 2.2 SQS — producer to three queues
- `shared` `SQSClient` injected with `@Named("amazonSQSForSender") AmazonSQS` (built with `AWSClientConfiguration.sqs_sender`: `maxErrorRetry(3)`, 500 ms–5 s backoff, 1 s connect, 10 s exec, 5 s socket, 50 conns).
- `SQSClient` overloads: `sendMessage(target, content)`, `sendMessage(target, content, delay)`, `sendMessage(target, content, delay, failedAttempts)` (writes `MessageAttributeValue` keyed `FAILED_ATTEMPTS`), `deleteMessage`, `getVisibilityTimeout`.
- Three send sites — one per consumer — to `shippeoInboundQueueUrl`, `cargoVisibilitySubscriptionQueueUrl`, `cargoVisibilityEventQueueUrl` (`VisibilityInboundConsumerConfiguration`), each sending `MetaData.toJsonString()`.

### 2.3 SNS — event publish
- `shared` `SNSClient` (`AmazonSNS` via `AWSClientConfiguration.sns_publish`); `SNSEventPublisher(topicArn, SNSClient)` provided in `WatermillConsumerModule` from `snsEventConfig.topicArn`; `publishEvent(List<Event>)` → JSON → `PublishRequest`.

### 2.4 DynamoDB — per-topic offset store
- `consumer-commons` `WatermillOffset`: `@DynamoDBTable("watermill_offset")`, `@DynamoDBHashKey("topicName") String hashKey`, `@DynamoDBAttribute Long offset`, `@DynamoDBAttribute @DynamoDBTypeConverted(DateToEpochSecond) Date readDateTime/writeDateTime`, `@DynamoDBStream(KEYS_ONLY)`.
- `DateToEpochSecond` (`com.amazonaws...datamodeling.DynamoDBTypeConverter`): `getTime()/1000` ↔ `new Date(epoch*1000)`.
- `WatermillOffsetDao extends DynamoDBCrudRepository<WatermillOffset, DynamoHashKey<String>>` (injected `DynamoDBMapper` + `DynamoDBMapperConfig`); `findOne/update/save`.
- `WatermillOffsetService.getOffset/updateOffset/initializeOffset`; `OffsetUtil` (in-memory) + `OffsetUpdateScheduler` (flush) — **three instances**, one per topic (`VisibilityInboundConsumerApplication`).
- `DynamoSupport` builds `AmazonDynamoDBClientBuilder.standard()` (or `.withEndpointConfiguration(new AwsClientBuilder.EndpointConfiguration(regionEndpoint, signingRegion))`); table prefix `"{environment}_{tableName}"` via `DynamoDBMapperConfig.TableNameOverride`.
- `DynamoTableCommand` (TableUtils + SSE + throughput) creates the table.

### 2.5 SSM — gRPC credentials
- `shared` `ParameterStoreModule(userIdKey, passwordKey)` installs `AWSSimpleSystemsManagementClientBuilder.defaultClient()`; `SsmParameterSupplier` caches `ParameterStore.getParameters(keys)`.
- `AuthCredentials` (per topic) reads `watermillServiceConfig.userIdKey`/`passwordKey` at injection → gRPC call credentials.

### 2.6 Config / Dropwizard
- `VisibilityInboundConsumerApplication extends Application<VisibilityInboundConsumerConfiguration>`; `initialize()` sets `S3ConfigurationProvider` (if required) + `ConfigProcessingServerCommand`.
- Guice: `ExternalServicesModule` (S3/SQS/SNS clients + `ParameterStoreModule`) + `WatermillConsumerModule` (DynamoDB mapper, three named `OffsetUtil`/`ConsumptionRequest` beans, `EventPublisher`).
- Tests already JUnit 5 (Jupiter) + Mockito 5.

### 2.7 Domain model coupling (module-specific)
- Depends on `com.inttra.mercury:visibility:1.0.M` for `com.inttra.mercury.visibility.common.model.*` (`ContainerEventSubmission`, `ContainerEvent`, `CargoVisibilitySubscription`). The transformers (`ContainerEventTransformer`, `ContainerEventProtoMapper`, `CargoVisibilitySubscriptionTransformer`) map e2open proto → these types, then serialise to the SQS body. **That jar is itself migrating under ION-12316** — version alignment is mandatory (§3, §9).

---

## 3. Findings

- **The offset store is the only load-bearing AWS surface** for correctness; everything else (S3/SQS/SNS/SSM) is behavior-preserving plumbing that rides `shared`. The **highest risk** is mapping the migrated `WatermillOffset` to a different physical table name or renaming an attribute → silent re-consumption from 0 (per topic), exactly as the watermill plan warns.
- **SQS is a real producer surface here** (3 queues), unlike the S3-only siblings. It maps cleanly to `MessagingClient<String>.sendMessage(url, body)`; `FAILED_ATTEMPTS` round-trips as a `Map<String,String>` attribute (master plan §3 evidence).
- **S3 writes carry no metadata** ⇒ **S-G2 is not consumed** by this module (it is required only by dispatcher/distributor).
- **Three offset rows coexist** in one `{env}_watermill_offset` table keyed by topic name; the migration must keep all three keys working independently.
- **`ConsumerManager`** persists the offset before reconnecting and reuses the observer; the migrated `WatermillOffsetService.save` must keep last-writer-wins semantics (no conditional write) so reconnect resume is unchanged.
- **`visibility` model jar is a cross-workspace contract.** Because `mercury-services` `visibility` migrated (ION-12316), the cloud-sdk `MetaData` (`cloudsdk.notification.workflow.MetaData`) and any model/converter package moves must be matched here, or the SQS body the downstream `visibility-wm-inbound-processor` consumes will drift.
- **No JUnit 4→5 churn** — already Jupiter. **gRPC is non-AWS** — untouched, including the ION-15497 >10 MB inbound limit.

---

## 4. Option A — keep the consumer bootstrap; swap AWS internals to cloud-sdk (DW4 retained)

Keep DW 4.0.16, the application/`ConfigProcessingServerCommand`, and class names; swap each AWS wrapper's internals to cloud-sdk via `shared`/`consumer-commons`:
- offset DAO → `DatabaseRepository` (entity remap, consolidated in `consumer-commons`);
- S3 → `StorageClient`; SQS → `MessagingClient<String>`; SNS → `NotificationService`; SSM → `CloudParameterStore` (all via migrated `shared`);
- bump the `visibility` model jar to the ION-12316 release.

- **Pros:** smallest blast radius; no framework jump; incremental/reversible; identical cloud-sdk consumption to Option B.
- **Cons:** keeps the bespoke DW4 base (long-term divergence from `mercury-services` `visibility`, which is already on `InttraServer`/DW5).
- **Effort:** Low–Medium. **Risk:** Low–Medium (offset shape is the only real hazard).

> Option A and Option B require the **same** cloud-sdk consumption and the **same** zero cloud-sdk changes; they differ only in whether the application also moves onto `commons`/DW5.

---

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

Replace the DW4 base/config command with `commons` `InttraServer` (DW 5.0.1) + the composed appianway `ServerCommand`; rebind S3/SQS/SNS/SSM onto cloud-sdk; remap the offset store; bump the `visibility` model jar. **Keep** the three gRPC consumers, `ConsumerManager`, the three `OffsetUtil`/`OffsetUpdateScheduler` instances, and all transformers/type-maps.

- **Pros:** platform convergence with `mercury-services` `visibility` (shared `InttraServer`, one AWS abstraction, shared CVE/Jackson/Jetty cadence); removes bespoke DW plumbing; the two halves of the visibility integration run the same stack.
- **Cons:** forces DW 4→5 on a live three-stream consumer; config composition work.
- **Effort:** Medium. **Risk:** Medium (framework move on a live tracking feed; mitigated by sequencing the Dynamo remap first and per-module verify gates).

---

## 6. Comparison matrix

| Criterion | Option A (keep DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 → cloud-sdk | ✅ | ✅ |
| Required cloud-sdk change | none (S-G2 not used) | none (S-G2 not used) |
| Impact on mercury-services apps | none (client-only) | none (client-only) |
| Effort | Low–Medium | Medium |
| Risk to live feed | Low–Medium | Medium |
| Framework churn | none (DW4/JUnit5) | DW4→5 forced |
| Consistency w/ `mercury-services` `visibility` | AWS layer only | full (`InttraServer`/DW5) |
| Long-term maintainability | Good | Best |
| Incremental / reversible | ✅ | stage carefully |

> **Verdict:** matrix favors A on risk/effort, but the program directive (DW5 + convergence) — and the fact that the **sibling `mercury-services` `visibility` module is already on `InttraServer`/DW5** — make **Option B** authoritative. Both share the identical cloud-sdk contract and zero cloud-sdk changes, so a late A↔B switch costs nothing at the AWS layer.

---

## 7. Recommendation

**Adopt Option B**, consuming cloud-sdk `1.0.26-SNAPSHOT` as a client with **no cloud-sdk change and no S-G2 dependency**. Justification:

1. **Directive + convergence** onto the `mercury-services` platform — and specifically onto the same stack the `visibility` module it feeds already runs.
2. **Backward-compat guarantee:** client-only consumption + zero library delta ⇒ provably no impact on other mercury-services apps.
3. **Correctness preserved:** per-topic offset rows keep exact table/attribute names + epoch-seconds via `LongEpochSecondAttributeConverter`; last-writer-wins offset writes; SQS/SNS/S3 semantics unchanged.
4. **Contract preserved downstream:** bumping the `visibility` model jar keeps the SQS body byte-compatible with `visibility-wm-inbound-processor`.

> **Residual caution:** the real costs are (a) DW4→5 on a live three-stream consumer and (b) `visibility` model-jar alignment. Sequence the Dynamo remap (via `consumer-commons`) first, rebind S3/SQS/SNS/SSM after `shared`, bump the model jar deliberately, then do the framework move — each behind a verify gate.

---

## 8. Peer review (incorporated)

- **Offset round-trip per topic** — covered by a `dynamo-integration-test` fixture seeded with real items for all three topic keys; gate cutover on it. **Resolved (test plan).**
- **SQS `FAILED_ATTEMPTS` attribute** — `Map<String,String>` round-trips (master plan §3). **Resolved.**
- **S3 `PutObjectResult` ignored** — change to metadata-free `putObject(bucket,key,bytes)`; **no S-G2.** **Resolved.**
- **Credential/region parity** — v2 default providers honor `AWS_*`/`AWS_REGION`; `regionEndpoint`/`signingRegion` → `DynamoDbClientConfig`. **Resolved (verify in dev run).**
- **`visibility` model jar version** — new finding this review adds: must align with ION-12316; add a contract test on the SQS body shape. **Tracked (§9).**
- **gRPC `maxInboundMessageSize` (ION-15497)** — non-AWS; unchanged. **Out of scope.**

---

## 9. Open questions / dependencies / sequencing

- **Depends on:** (1) `consumer-commons` Dynamo pilot landing first (watermill plan §9); (2) `shared` + `functional-testing` migrating (master §9) before S3/SQS/SNS/SSM rebind; (3) the **ION-12316 `visibility` model-jar release version** being published and pinned.
- **Open question:** exact GA version/coordinate of the cloud-sdk-aligned `visibility` jar, and whether `MetaData` moved from `shared` to `cloudsdk.notification.workflow.MetaData` in the types this module serialises — confirm with the mercury-services `visibility` owners.
- **Open question:** whether the v2 create path must set the `@DynamoDBStream(KEYS_ONLY)` stream spec on `{env}_watermill_offset`, or whether the stream is managed out-of-band.
- **Sequencing:** Dynamo offset remap (in `consumer-commons`) → rebind S3/SQS/SNS/SSM → bump `visibility` jar + recompile transformers → DW5/`InttraServer` move (keep 3 schedulers + `ConsumerManager`) → `mvn -pl watermill/visibility-inbound-consumer -am verify` → aggregator `mvn verify`.
- **Cutover gate:** per-topic backward-compat offset fixture **and** an end-to-end SQS-body contract check against `visibility-wm-inbound-processor`.

---

## 10. Configuration changes (ref master §10)

- **Preserve all config keys unchanged:** three topic names, three queue URLs, `snsEventConfig.topicArn`, `s3WorkspaceConfig.bucket`, `dynamoDbConfig.{environment,regionEndpoint,signingRegion,sseEnabled}`, `watermillServiceConfig.{userIdKey,passwordKey,...}`.
- **DynamoDB:** physical `tableName = "{environment}_watermill_offset"` passed explicitly to `DynamoRepositoryFactory`; `DynamoDbClientConfig.endpointOverride(regionEndpoint)` + `Region.of(signingRegion)`; SSE/throughput on the create path.
- **Credentials/region:** env/IAM via v2 default providers; `${PROFILE}/${ENV}` expansion unchanged; any `${awsps:…}` resolves via commons `ParameterStoreConfigTransform`.
- **Option B:** register the composed appianway `ServerCommand` (master §10.3) on the consumer's `InttraServer` bootstrap, replacing the default; `S3ConfigurationProvider` behavior preserved or folded into the composed chain.
- **Retry/timeout:** reapply the v1 `sqs_sender`/`sns_publish` tuning (1 s connect, 5 s socket, 50 conns, bounded retries) via `ClientOverrideConfiguration` + `ApacheHttpClient` at the shared/factory boundary.

---

## 11. cloud-sdk gaps — **NONE for visibility-inbound-consumer**

This module requires **no** `cloud-sdk-api`/`cloud-sdk-aws`/`commons` change. Existing artifacts cover everything:

| Need | cloud-sdk artifact (existing) |
|---|---|
| Per-topic offset store | `DatabaseRepository`/`DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminCommand`/`DynamoDbAdminUtil`, `dynamo-integration-test` |
| S3 archive (metadata-free) | `StorageClient.putObject(bucket,key,bytes)` — **S-G2 not needed** |
| SQS send (3 queues) | `MessagingClient<String>.sendMessage(url, body[, attrs])` |
| SNS event publish | `NotificationService` (via shared `SNSEventPublisher`) |
| SSM gRPC credentials | `CloudParameterStore` (via shared `ParameterStore`) |
| DW5 base + config | `commons` `InttraServer` + composed appianway `ServerCommand` (public transforms) |

**Module-specific deliverable that is NOT a cloud-sdk change:** bump the `com.inttra.mercury:visibility` model jar to the ION-12316 cloud-sdk-aligned release and recompile the transformers (§7, §9). This is a dependency-version alignment, not a library modification.

---

> **Note on scope boundary.** The gRPC/Watermill consumption layer (`e2open.watermill.proto`, the three `StreamObserver`s, `ConsumerManager`, transformers, type-maps, `ConsumerInitUtil`, `maxInboundMessageSize`/ION-15497) is **not AWS** and is explicitly out of scope for this upgrade — it is carried unchanged through both options.
