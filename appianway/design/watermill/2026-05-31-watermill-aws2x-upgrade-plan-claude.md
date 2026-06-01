# `watermill` (aggregator + sub-modules) — AWS SDK v2 (cloud-sdk) Upgrade PLAN (claude)

> Module: `com.inttra.mercury:watermill:1.0` (aggregator) · sub-modules: `consumer-commons`, `itv-gps-consumer`, `cargoscreen-consumer`, `booking-inbound-consumer`, `visibility-inbound-consumer` · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Guice **7.0.0**, Jackson **2.21.0**).
> References the MASTER docs: [shared plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [shared DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6. Companion: [watermill DESIGN](2026-05-31-watermill-aws2x-upgrade-DESIGN-claude.md).

---

## 0. What this document changes vs. the Copilot plan (critical review)

Reviewed against [`2026-05-31-watermill-aws2x-upgrade-plan-copilot.md`](2026-05-31-watermill-aws2x-upgrade-plan-copilot.md) and the actual source of all five sub-modules. The Copilot plan's inventory is accurate, but it overstates the difficulty ("the single biggest code change in the program", "no drop-in equivalent") and under-specifies the one risk that actually matters: **the migrated entity must map to the SAME existing `watermill_offset` attribute names** so in-flight offsets survive the cutover.

| Copilot position | Evidence (this codebase) | This plan |
|---|---|---|
| "DynamoDB v1 `DynamoDBMapper` has **no drop-in equivalent**; this is the largest rewrite in the repo." | The offset surface is **one tiny entity** (`WatermillOffset`: 1 hash key + 3 attrs) + one converter + a DAO with `findOne`/`save`/`update`. cloud-sdk ships `DatabaseRepository`/`EnhancedDynamoRepository`/`DynamoRepositoryFactory` + `@Table`/`@DynamoDbField` + converters. | **No cloud-sdk gap.** A bounded, mechanical entity+converter+DAO remap, not a "rewrite". Effort: Low–Medium. |
| "Route through `cloud-sdk-aws` Dynamo support **if it provides a repository**; otherwise hit the v2 Enhanced Client directly." | `DynamoRepositoryFactory.createEnhancedRepository(DynamoDbClientConfig, tableName, Class<T>, DynamoRepositoryConfig)` exists and is what `mercury-services` (`booking` `SequenceId`) uses. | **Always** use `DynamoRepositoryFactory` + `DatabaseRepository`; never touch the raw v2 Enhanced Client. |
| "`DateToEpochSecond` (`DynamoDBTypeConverter`) → v2 `AttributeConverter`." (correct but generic) | cloud-sdk already ships **`LongEpochSecondAttributeConverter`** / `DateEpochSecondAttributeConverter`. `DateToEpochSecond` does exactly `date.getTime()/1000` ↔ `new Date(epoch*1000)`. | Reuse `LongEpochSecondAttributeConverter` (epoch **seconds**, `Long` stored) — matches the existing stored shape exactly. No custom converter unless a byte-level diff is found. |
| "`DynamoTableCommand` → v2 `DynamoDbClient.createTable` / Enhanced `createTable`; preserve SSE + throughput." | cloud-sdk ships `DynamoDbAdminCommand`/`DynamoDbAdminUtil`; `@Table(onDemand,readCapacity,writeCapacity)` carries throughput. | Replace per-consumer `DynamoTableCommand` with `DynamoDbAdminCommand` (or a thin appianway command over `DynamoDbAdminUtil`); SSE via the create request. No cloud-sdk gap. |
| "verify **G4** (version attribute) only if an entity uses one." | `WatermillOffset` has **no** `@DynamoDBVersionAttribute`; `updateOffset` is last-writer-wins per topic partition. | **G4 is a non-gap here** — no optimistic locking is used or needed (§3.4). Plain `save()`/`update()` suffices; native v2 `@DynamoDbVersionAttribute` is available if ever wanted. |
| "watermill **may not depend on `shared`** → migrates independently." | All sub-modules depend on `mercury-shared` (`SNSClient`, `SNSEventPublisher`, `ParameterStoreModule`, `NetworkRetryerModule`, `AWSClientConfiguration`, and the `dynamo-client` repo base `com.inttra.mercury.dynamo.respository.*` which is shipped from the appianway side). | **Partially coupled.** The offset/Dynamo path can pilot independently, but SNS/SSM/S3 wiring rides on `shared`'s migration. Sequence after `shared` for those; the Dynamo entity remap can be prototyped earlier. |
| "consolidate duplicated `DynamoSupport`/`WatermillOffsetDao`/`DynamoTableCommand` into `consumer-commons` (opportunity)." | Confirmed duplication: `cargoscreen-consumer` and `itv-gps-consumer` carry **their own copies** of `vo/WatermillOffset`, `vo/DateToEpochSecond`, `dynamodb/DynamoSupport`, `dao/WatermillOffsetDao`; `booking-inbound` and `visibility-inbound` **reuse `consumer-commons`**. | Migrate `consumer-commons` once; **fold the duplicated copies onto `consumer-commons`** during the migration so there is **one** entity/converter/repo definition, eliminating divergent conversions. |
| "keep watermill tests on JUnit 4 unless forced." | `consumer-commons` and the consumer poms **already declare `junit-jupiter`** and `mockito-junit-jupiter`. | Tests are **already JUnit 5**; new offset/integration tests go straight to Jupiter + `dynamo-integration-test`. No vintage bridge needed for watermill. |

Net: watermill is **not** the program's biggest change — it is a contained DynamoDB entity remap with **zero required cloud-sdk gaps**. The only first-order risk is offset-table data-shape backward compatibility (§9, DESIGN §10).

---

## 1. Executive summary

watermill is the **side-bus aggregator**: five gRPC stream consumers that read an at-least-once stream from the watermill broker and persist a per-topic cursor in the DynamoDB table **`watermill_offset`**. The **only AWS surface** is:

1. **DynamoDB** — the offset store (`WatermillOffset` entity + `DateToEpochSecond` converter + `WatermillOffsetDao` + `DynamoSupport` client/mapper builders + per-consumer `DynamoTableCommand`). Currently on **AWS v1 `DynamoDBMapper`** via appianway's in-house `dynamo-client` repo base (`com.inttra.mercury.dynamo.respository.DynamoDBCrudRepository`).
2. **S3** — `S3PublishService` writes a payload with `putObject(bucket,key,String)` (**no metadata**).
3. **SNS** — `SNSEventPublisher` over `shared`'s `SNSClient` (publish only).
4. **SSM** — credentials via `shared`'s `ParameterStoreModule`.

**gRPC stream consumption is NOT AWS and is entirely out of scope** (the `e2open.watermill.proto` client, `ConsumptionRequest`, `ResponseConsumerObserver`, transformers, type-maps — all untouched).

Per the program directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§7), implemented so that:

1. the offset store moves from v1 `DynamoDBMapper`/`DynamoDBCrudRepository` to cloud-sdk `DatabaseRepository` built by `DynamoRepositoryFactory.createEnhancedRepository(...)`;
2. `WatermillOffset` is re-annotated with `cloud-sdk-api` `@Table(name="watermill_offset")` / `@DynamoDbField`, **preserving every stored attribute name** (§DESIGN §10);
3. S3/SNS/SSM ride the `shared` migration (S3 read/write via `StorageClient`, SNS via `NotificationService`, SSM via `CloudParameterStore`);
4. **NO module-specific cloud-sdk change is required** (§11). watermill-publisher references S-G2 only; watermill needs nothing.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

AWS Java SDK **v1** (`com.amazonaws.*`), `1.12.720`. Dropwizard `4.0.16` ([watermill/pom.xml](../pom.xml) L19, L24). gRPC `1.77.0`.

### 2.1 DynamoDB — offset store (the principal surface)

**`consumer-commons` (canonical; reused by `booking-inbound` + `visibility-inbound`):**
- [`vo/WatermillOffset.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/vo/WatermillOffset.java) L1–57 — `@DynamoDBTable(tableName="watermill_offset")` (L19); `@DynamoDBHashKey(attributeName="topicName") String hashKey` (L29–30); `@DynamoDBAttribute Long offset` (L33–34); `@DynamoDBAttribute @DynamoDBTypeConverted(converter=DateToEpochSecond.class) Date readDateTime` (L37–39) and `Date writeDateTime` (L41–43). Implements in-house `DynamoHashKey<String>`; carries appianway `@DynamoDBStream(KEYS_ONLY)` (L24).
- [`vo/DateToEpochSecond.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/vo/DateToEpochSecond.java) L7–17 — `DynamoDBTypeConverter<Long,Date>`: `convert` = `date.getTime()/1000`; `unconvert` = `new Date(epoch*1000)`. **Stored type = `Long` epoch-seconds.**
- [`vo/Expires.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/vo/Expires.java) L8–14 — TTL marker interface (`expiresOn`); `WatermillOffset` does **not** implement it (no TTL on offsets).
- [`dao/WatermillOffsetDao.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/dao/WatermillOffsetDao.java) L13–25 — `extends DynamoDBCrudRepository<WatermillOffset, DynamoHashKey<String>>` (in-house `dynamo-client`), constructed from injected `DynamoDBMapper` + `DynamoDBMapperConfig`.
- [`dynamodb/DynamoSupport.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/dynamodb/DynamoSupport.java) L18–75 — v1 `DynamoDBMapper`/`AmazonDynamoDBClientBuilder`; `newClient(regionEndpoint,signingRegion)` uses `AwsClientBuilder.EndpointConfiguration` (L61–73) for DynamoDB-Local/regional endpoints; `newDynamoDBMapperConfig` applies a **table-name prefix `"{environment}_"`** (L44–51).
- [`service/WatermillOffsetService.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/service/WatermillOffsetService.java) L25–55 — `getOffset` → `offsetDao.findOne(builder().hashKey(topic))`; `updateOffset` → `offsetDao.update(...)`; `initializeOffset` → `offsetDao.save(...)`.
- [`util/OffsetUtil.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/util/OffsetUtil.java) — in-memory cursor; seeds from `getOffset()` or `-1L`.
- [`task/OffsetUpdateScheduler.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/task/OffsetUpdateScheduler.java) — periodically flushes the in-memory offset via the service (the actual DynamoDB write cadence).

**Per-consumer duplicates / wiring:**
- `cargoscreen-consumer` and `itv-gps-consumer` carry **their own copies** under `com.inttra.watermill.gps.consumer.{vo,dao,dynamodb}` (e.g. [`cargoscreen .../vo/WatermillOffset.java`](../cargoscreen-consumer/src/main/java/com/inttra/watermill/gps/consumer/vo/WatermillOffset.java), [`.../dao/WatermillOffsetDao.java`](../cargoscreen-consumer/src/main/java/com/inttra/watermill/gps/consumer/dao/WatermillOffsetDao.java), [`.../dynamodb/DynamoSupport.java`](../cargoscreen-consumer/src/main/java/com/inttra/watermill/gps/consumer/dynamodb/DynamoSupport.java)) — byte-identical logic, different package.
- Each consumer's `modules/WatermillConsumerModule` binds the v1 `AmazonDynamoDB`/`DynamoDBMapper`/`DynamoDBMapperConfig` (e.g. [`cargoscreen WatermillConsumerModule.java`](../cargoscreen-consumer/src/main/java/com/inttra/watermill/gps/consumer/modules/WatermillConsumerModule.java) L40–46; [`booking-inbound WatermillConsumerModule.java`](../booking-inbound-consumer/src/main/java/com/inttra/watermill/consumer/bookinginbound/modules/WatermillConsumerModule.java) L43–50).
- Each consumer has a `dynamodb/command/DynamoTableCommand` (create-table): [`cargoscreen DynamoTableCommand.java`](../cargoscreen-consumer/src/main/java/com/inttra/watermill/gps/consumer/dynamodb/command/DynamoTableCommand.java) — v1 `TableUtils.createTableIfNotExists` + `dynamoDBMapper.generateCreateTableRequest` + `ProvisionedThroughput(10,10)` + `SSESpecification(isSseEnabled)` (L53–67).

### 2.2 S3 — `S3PublishService` (write, no metadata)
- [`consumer-commons .../service/S3PublishService.java`](../consumer-commons/src/main/java/com/inttra/mercury/watermill/consumer/service/S3PublishService.java) L20–36 — injects `AmazonS3`; `uploadToS3` calls `s3Client.putObject(bucket, key, String payload)` and **ignores the `PutObjectResult`** (L33). No `ObjectMetadata`. (cargoscreen has a near-identical copy taking the bucket from config.)

### 2.3 SNS — publish only
- Each `WatermillConsumerModule`/`ExternalServicesModule` binds v1 `AmazonSNS` (`AmazonSNSClientBuilder...sns_publish`) and provides `EventPublisher` = `SNSEventPublisher(topicArn, SNSClient)` (e.g. booking-inbound module L56–58). `SNSClient`/`SNSEventPublisher` are **`shared`** types.

### 2.4 SSM / credentials / client config
- `ExternalServicesModule` installs `shared`'s `ParameterStoreModule(userIdKey, passwordKey)` and `NetworkRetryerModule`, and binds S3/SNS via `shared`'s `AWSClientConfiguration` (e.g. [`cargoscreen ExternalServicesModule.java`](../cargoscreen-consumer/src/main/java/com/inttra/watermill/gps/consumer/modules/ExternalServicesModule.java) L29–36).

### 2.5 gRPC (NON-AWS — out of scope)
`com.e2open.watermill.proto.*` client, `ConsumptionRequest` (seeded from the offset — e.g. cargoscreen module L55–71), `ResponseConsumerObserver`, `AuthCredentials`, `MessageKeys`, all transformers/type-maps and `WatermillConsumerTask`. **No AWS dependency; untouched by this migration.**

### 2.6 Maven & tests
- `consumer-commons/pom.xml` depends on `mercury-shared`, the in-house `dynamo-client`, and declares `aws-java-sdk-sqs` + `aws-java-sdk-dynamodb` (`1.12.720`). Tests **already use `junit-jupiter` + `mockito-junit-jupiter`** (JUnit 5).
- Tests touching AWS: `WatermillOffsetDaoTest`, `DynamoSupportTest`, `S3PublishServiceTest`, `WatermillOffsetServiceTest`, `DateToEpochSecondTest`, `OffsetUpdateSchedulerTest`, each consumer's `WatermillConsumerModuleTest`/`DynamoTableCommandTest`.

---

## 3. Findings

1. **The AWS footprint is small and offset-centric.** One 4-field entity, one converter, a CRUD DAO with `findOne`/`save`/`update`, a client/mapper builder, and a create-table command — duplicated across modules. Everything else AWS-related (S3 write, SNS publish, SSM) is thin and rides `shared`.
2. **cloud-sdk fully covers it.** `DatabaseRepository<T,ID>` + `DynamoRepositoryFactory.createEnhancedRepository(DynamoDbClientConfig, tableName, Class<T>, DynamoRepositoryConfig)` replaces `DynamoDBCrudRepository`+`DynamoDBMapper`. `@Table`/`@DynamoDbField`/`@TTL` replace the v1 datamodeling annotations. `LongEpochSecondAttributeConverter` replaces `DateToEpochSecond`. `DynamoDbAdminCommand`/`DynamoDbAdminUtil` replaces `DynamoTableCommand`. `dynamo-integration-test` (DynamoDB-Local, JUnit 5) replaces v1 local-dynamo test setup.
3. **The `DynamoRepositoryFactory` enhanced client carries the DEFAULT extensions** (`VersionedRecordExtension` + `AtomicCounterExtension`). This is harmless for watermill: with no `@DynamoDbVersionAttribute`/`@DynamoDbAtomicCounter` on `WatermillOffset`, the extensions are inert and `save`/`update` behave as plain puts.
4. **Offset semantics = last-writer-wins per topic partition (no optimistic locking).** `updateOffset` does an unconditional `update`; the cursor only moves forward and is flushed by `OffsetUpdateScheduler`; at-least-once is provided by the **table itself** (cursor persisted, +1 on resume — see consumer module L62–68), not by conditional writes. ⇒ **Copilot's G4 does not apply**; plain `save()`/`update()` is behavior-identical.
5. **Table-name prefixing must be preserved.** v1 resolves the physical name as `"{environment}_watermill_offset"` (DynamoSupport L44–51). The migration must reproduce the **same physical table name** (pass `"{env}_watermill_offset"` as the `tableName` to `DynamoRepositoryFactory`, since cloud-sdk's `@Table(name=...)` is the logical name and the factory takes an explicit `tableName`). Getting this wrong points at a different/empty table → silent re-consumption from offset 0.
6. **S3 write needs no metadata** ⇒ the existing `StorageClient.putObject(bucket,key,bytes)` / `putObject(bucket,key,String)` overloads suffice; **S-G2 is NOT needed by watermill.**
7. **Duplication is a maintenance hazard, not a blocker.** Folding the per-consumer copies onto `consumer-commons` during the migration yields one authoritative entity/converter/repo and prevents four divergent conversions.

---

## 4. Option A — keep watermill bootstrap; swap Dynamo/S3/SNS internals to cloud-sdk (DW4 retained)

Keep the watermill aggregator's own Dropwizard-4 bootstrap and per-consumer applications; replace only the AWS internals: `WatermillOffset` annotations → `cloud-sdk-api`; `WatermillOffsetDao`/`DynamoSupport` → `DatabaseRepository` + `DynamoRepositoryFactory`; `DynamoTableCommand` → `DynamoDbAdminUtil`; `S3PublishService` → `StorageClient`; SNS via `NotificationService`. Tests already Jupiter.
- **Pros:** smallest blast radius; the Dynamo path can pilot the cloud-sdk DynamoDB approach for the whole program independently and early; reversible per sub-module.
- **Cons:** keeps the bespoke DW4 base (long-term divergence from `mercury-services`); S3/SNS/SSM still want `shared`'s migrated wrappers, so a full A is only clean for the pure-Dynamo path.
- **Effort:** Low–Medium. **Risk:** Low–Medium (the one real risk is offset table-name/attribute compatibility).

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A for the AWS internals, **plus** move the consumer applications onto `commons` `InttraServer` (DW 5.0.1) and the composed appianway config command (master plan §10), converging with `mercury-services`. Keep all gRPC consumer logic, transformers, `OffsetUtil`/`OffsetUpdateScheduler` and error model.
- **Pros:** platform convergence (shared CVE/Jackson/Jetty cadence, one AWS abstraction, `dynamo-integration-test` harness); removes the bespoke DW4 base.
- **Cons:** forces DW4→5 across five sub-modules; couples the offset cutover to the `shared`/framework move for the S3/SNS pieces.
- **Effort:** Medium–High. **Risk:** Medium (framework move on a live cursor store; mitigated by offset backward-compat tests).

> Both options use the **same** cloud-sdk consumption and require **no** module-specific cloud-sdk change. They differ only in the Dropwizard base.

## 6. Comparison matrix

| Criterion | Option A (keep bootstrap/DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 (Dynamo/S3/SNS) | ✅ | ✅ |
| Required cloud-sdk library change | **None** | **None** |
| Impact on mercury-services apps | None (client-only) | None (client-only) |
| Effort | Low–Medium | Medium–High |
| Risk to offset store | Low–Medium | Medium |
| Framework churn | None | DW4→5 ×5 sub-modules |
| Consistency w/ mercury-services | AWS layer only | Full |
| Independent pilot of cloud-sdk DynamoDB path | ✅ (best candidate) | ✅ but coupled to shared/DW5 |

## 7. Recommendation

**Adopt Option B** per the program directive, but **sequence the Dynamo offset remap first as an early, low-risk pilot** of the cloud-sdk DynamoDB path (it has the fewest dependencies on `shared`). Rationale:

1. **Directive + convergence** onto the `mercury-services` platform.
2. **Backward-compat guarantee:** watermill consumes cloud-sdk exactly as `booking` does for DynamoDB; **no cloud-sdk change** ⇒ provably zero impact on other apps.
3. **Behavior preserved:** entity remap keeps identical attribute names; last-writer-wins offset semantics keep plain `save()`/`update()`; `LongEpochSecondAttributeConverter` keeps the stored epoch-seconds shape.
4. **De-duplication win:** consolidate to `consumer-commons` to avoid four divergent conversions.

> **Residual caution:** the offset table is a live cursor; the **only** way this migration causes harm is mapping to a different physical table name or renaming an attribute (DESIGN §10). Gate the cutover on a `dynamo-integration-test` round-trip against a snapshot of real `{env}_watermill_offset` items.

## 8. Peer review note

Self-review + cross-module verification resolved every Copilot open item: (a) watermill **does** depend on `shared` (SNS/SSM/S3 + the `dynamo-client` repo base) — only the pure-Dynamo path is truly independent; (b) offset semantics are **last-writer-wins, no version attribute** ⇒ G4 N/A; (c) duplication confirmed across `cargoscreen`/`itv-gps` vs `consumer-commons` — consolidate; (d) tests are **already JUnit 5** ⇒ no vintage bridge; (e) the converter maps to cloud-sdk's existing `LongEpochSecondAttributeConverter` (epoch-seconds) — no new converter expected. New finding: the table-name **prefix** (`{env}_`) is the load-bearing compatibility detail, not the annotations.

## 9. Open questions / dependencies / sequencing

- **Sequence after `shared` + `functional-testing`** for the S3/SNS/SSM rebind; the **Dynamo offset remap can be prototyped earlier** as the cloud-sdk DynamoDB pilot (it only needs `cloud-sdk-api`/`cloud-sdk-aws` + `dynamo-integration-test`).
- **Consolidate first:** migrate `consumer-commons`, then fold `cargoscreen`/`itv-gps` duplicates onto it, then the two reusing consumers.
- **Confirm the physical table name** in each environment (`{environment}_watermill_offset`) and pass it explicitly to `DynamoRepositoryFactory` (DESIGN §10). **Critical.**
- **Confirm stored attribute names** by inspecting a live item: expect `topicName` (PK), `offset`, `readDateTime`, `writeDateTime` (epoch-seconds Numbers). The `@DynamoDbField` names MUST match exactly.
- **`@DynamoDBStream(KEYS_ONLY)`** is an appianway annotation read at table-create time — confirm whether the v2 create path (DynamoDbAdminUtil) must reproduce the stream spec, or whether the stream is managed out-of-band.
- **No `mft-s3-aqua-appia` interaction** for watermill (no SQS/S3-event pipeline here).

## 10. Configuration changes

Per master plan §10 (config composition) and §DESIGN §5. watermill-specific:
- Replace the v1 `EndpointConfiguration` (DynamoSupport L61–73, used for DynamoDB-Local/regional endpoints) with cloud-sdk `DynamoDbClientConfig` **endpoint override** + region. Credentials/region remain env/IAM-driven (v2 default providers).
- `DynamoDbConfig` YAML (`environment`, `regionEndpoint`, `signingRegion`, `sseEnabled`) maps to: physical `tableName = "{environment}_watermill_offset"`, `DynamoDbClientConfig.endpointOverride(regionEndpoint)` + `Region.of(signingRegion)`, and SSE on the create request.
- Under Option B, register the composed appianway `ServerCommand` (master §10.3) on each consumer's `InttraServer` bootstrap.

## 11. cloud-sdk gaps — **NONE for watermill**

watermill requires **no** cloud-sdk-api/cloud-sdk-aws/commons change. The DynamoDB migration is fully served by existing artifacts:

| Need | cloud-sdk artifact (existing) |
|---|---|
| Repository / CRUD | `DatabaseRepository<T,ID>`, `EnhancedDynamoRepository`/`StandardDynamoRepository`, `DynamoRepositoryFactory.createEnhancedRepository(DynamoDbClientConfig, tableName, Class<T>, DynamoRepositoryConfig)` |
| Entity annotations | `@Table(name,onDemand,readCapacity,writeCapacity)`, `@DynamoDbField(value)`, `@TTL` (cloud-sdk-api) |
| Date→epoch-seconds converter | `LongEpochSecondAttributeConverter` (matches `DateToEpochSecond`); `DateEpochSecondAttributeConverter` available |
| Table create (SSE + throughput) | `DynamoDbAdminCommand` / `DynamoDbAdminUtil` |
| Local / regional endpoint | `DynamoDbClientConfig` endpoint override |
| Integration testing | `dynamo-integration-test` (DynamoDB-Local, JUnit 5) |
| Optimistic locking (if ever needed) | native v2 `@DynamoDbVersionAttribute` + default `VersionedRecordExtension` (already wired by the factory) — **not used by watermill** |

S3 write here is metadata-free ⇒ **S-G2 is not needed by watermill** (it is referenced only by watermill-publisher's sibling plan, and there only if it wrote metadata — it does not; see that plan §11).
