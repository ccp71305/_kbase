# `cargoscreen-consumer` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury:cargoscreen-consumer` (sub-module of `watermill`) · Date: 2026-06-30 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`mercury-services-commons` `1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Guice **7.0.0**, Jackson **2.21.0**).
> Companion DESIGN: [`2026-06-30-cargoscreen-consumer-aws2x-upgrade-DESIGN-claude.md`](2026-06-30-cargoscreen-consumer-aws2x-upgrade-DESIGN-claude.md).
> MASTERs: [shared plan](../../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §10/§11 · [watermill plan](../../docs/2026-05-31-watermill-aws2x-upgrade-plan-claude.md).

---

## 0. Scope note (vs. the watermill aggregator plan)

`cargoscreen-consumer` is an **S3-only sink** (no SQS, no SNS), matching the watermill aggregator plan's generic consumer profile. Module-specific deltas recorded here: (1) it has the **most local DynamoDB duplication** of the fleet — its own `vo/WatermillOffset` entity plus `DynamoSupport`, `DynamoTableCommand`, `vo/DateToEpochSecond` — all to be consolidated onto `consumer-commons`; (2) a **dead `AmazonSNS` binding** and a **declared-but-unused `aws-java-sdk-sqs`** to remove; (3) it is on **JUnit 4** (needs `junit-vintage-engine`); (4) its reconnect carries an ION-14324 20 s channel-stabilization (gRPC, non-AWS, unchanged). Everything else inherits the watermill plan unchanged.

---

## 1. Executive summary

`cargoscreen-consumer` is a Dropwizard 4 application running a single e2open Watermill gRPC stream consumer for cargo-screening results. It parses proto `CargoScreeningOutboundChangeEvent`, writes successful `CargoScreeningOutbound` results to S3 as `{YYYYMMdd}/{offset}_{sourceSourceTxId}.json` (errors logged only), persists one consumption offset in DynamoDB, and reads gRPC credentials from SSM. AWS footprint: **S3(write) + DynamoDB(offset) + SSM** on AWS Java SDK **v1 `1.12.720`**, Dropwizard **4.0.16**, gRPC **1.77.0**.

Per the directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§5): consume cloud-sdk **as a client** (no cloud-sdk/commons change, **S-G2 not used**); remap the DynamoDB offset onto `DatabaseRepository`/`@Table`/`LongEpochSecondAttributeConverter` **consolidated in `consumer-commons`** (eliminating cargoscreen's own entity copy), preserving the exact physical table + attribute names; rebind S3/SSM onto cloud-sdk via `shared`; delete the dead SNS binding, unused SQS dep, and local Dynamo duplicates; move onto `InttraServer`/DW5. The gRPC layer is non-AWS and out of scope.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

AWS Java SDK **v1** `1.12.720`; Dropwizard `4.0.16`; gRPC `1.77.0`. Direct AWS deps: `aws-java-sdk-sqs` (pom :64, **unused**), `aws-java-sdk-dynamodb` (pom :70); transitive S3/SSM via `shared`; `dynamo-client` supplies `DynamoDBCrudRepository` (with `aws-java-sdk-dynamodb` excluded to avoid dual-SDK conflict, pom :80-81).

### 2.1 S3 — write (metadata-free)
- `S3PublishService.uploadToS3(fullS3Path, payload)` → `s3Client.putObject(bucket, key, String)`; **no `ObjectMetadata`** (`S3PublishService:36-40`). Client `AmazonS3ClientBuilder.standard().build()` (`ExternalServicesModule:31-32`). Key `{YYYYMMdd}/{offset}_{sourceSourceTxId}.json` (`ResponseConsumerObserver:113-122`); bucket = `s3WorkspaceConfig.bucket`. **⇒ S-G2 not required.**

### 2.2 SQS — absent (declared, unused)
- `aws-java-sdk-sqs` in pom (:64) but **no `AmazonSQS` instantiation or `sendMessage`** anywhere. Remove the dep.

### 2.3 SNS — dead binding
- `ExternalServicesModule:29-30` binds `AmazonSNS` via `AmazonSNSClientBuilder.standard().withClientConfiguration(AWSClientConfiguration.sns_publish)`, **never injected/invoked**. Remove.

### 2.4 DynamoDB — single offset (fully-local duplicate)
- **Own local classes:** `dynamodb/DynamoSupport` (`AmazonDynamoDBClientBuilder.standard()`, `DynamoDBMapper`, `DynamoDBMapperConfig` with prefix override, `:36/:47-50/:70`), `dynamodb/command/DynamoTableCommand` (`TableUtils.createTableIfNotExists`, `SSESpecification`, 10/10 throughput, `:30-40/:56`), **`vo/WatermillOffset`** (`@DynamoDBTable("watermill_offset")` :19, `@DynamoDBHashKey("topicName")` :29, `@DynamoDBAttribute offset/readDateTime/writeDateTime`, `@DynamoDBTypeConverted(DateToEpochSecond)` :38/:42, `@DynamoDBStream(KEYS_ONLY)` :24, implements `DynamoHashKey<String>`), `vo/DateToEpochSecond` (`DynamoDBTypeConverter<Long,Date>` :7).
- Table prefix `"{environment}_watermill_offset"`; single topic → single row. One `OffsetUtil` + one `OffsetUpdateScheduler` (fixed-rate, minutes).

### 2.5 SSM — gRPC credentials
- `AuthCredentials:27-32` reads `watermillServiceConfig.userIdKey`/`passwordKey` via shared `ParameterSupplier`/`ParameterStoreModule` (`AWSSimpleSystemsManagementClientBuilder.defaultClient()`).

### 2.6 Config / Dropwizard
- `CargoScreenConsumerApplication extends Application<WatermillConsumerConfiguration>`; `S3ConfigurationProvider` (conditional) + `ConfigProcessingServerCommand` + local `DynamoTableCommand` (:40-41). **Tests: JUnit 4** (`junit:4.13.2`, `MockitoJUnitRunner`).

### 2.7 Model jar — none
- No booking/visibility domain model dependency; consumes the e2open proto and emits JSON only.

---

## 3. Findings

- **The offset store is the only correctness-critical AWS surface.** Highest risk: mapping the migrated/consolidated `WatermillOffset` to a different physical table or renamed attribute → silent re-consumption from 0.
- **cargoscreen owns the most Dynamo duplication** (its own `WatermillOffset` entity). Consolidation onto `consumer-commons` must be **field-for-field identical** (table name, attribute names, epoch-seconds) — diff before deleting.
- **S3 write is metadata-free ⇒ S-G2 not consumed.**
- **Dead AWS code:** `AmazonSNS` binding + unused `aws-java-sdk-sqs` — remove.
- **JUnit 4** — needs `junit-vintage-engine` during transition.
- **No model jar / no SQS / no SNS** ⇒ no cross-workspace contract risk.
- **gRPC** (topic, reconnect, ION-14324 20 s stabilization) is non-AWS — untouched.

---

## 4. Option A — keep DW4; swap AWS internals to cloud-sdk

Keep DW 4.0.16/app/`ConfigProcessingServerCommand`; remap+consolidate the offset onto `consumer-commons`; rebind S3 → `StorageClient`, SSM → `CloudParameterStore` via migrated `shared`; delete dead SNS/SQS.

- **Pros:** smallest blast radius; reversible; identical cloud-sdk consumption to Option B.
- **Cons:** keeps bespoke DW4 base.
- **Effort:** Low–Medium (the entity consolidation is the main work). **Risk:** Low–Medium.

---

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A plus moving the application onto `commons` `InttraServer` (DW 5.0.1) with the composed appianway `ServerCommand`; add `junit-vintage-engine`. Keep the gRPC consumer, reconnect logic, single `OffsetUpdateScheduler`.

- **Pros:** platform convergence; removes bespoke DW plumbing.
- **Cons:** DW4→5 + JUnit4→5 platform move.
- **Effort:** Medium. **Risk:** Low–Medium.

---

## 6. Comparison matrix

| Criterion | Option A (DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 → cloud-sdk | ✅ | ✅ |
| Required cloud-sdk change | none (no S-G2) | none (no S-G2) |
| Impact on mercury-services | none | none |
| Effort | Low–Medium | Medium |
| Risk | Low–Medium | Low–Medium |
| Framework churn | none | DW4→5 + JUnit4→5 |
| Consistency w/ platform | AWS layer only | full |
| Incremental / reversible | ✅ | stage carefully |

> **Verdict:** the directive makes **Option B** authoritative; both share the identical cloud-sdk contract and zero cloud-sdk changes. cargoscreen and itv-gps are good early pilots (no SQS/SNS/model-jar coupling).

---

## 7. Recommendation

**Adopt Option B**, consuming cloud-sdk `1.0.26-SNAPSHOT` as a client with **no cloud-sdk change and no S-G2**. The defining task is the **DynamoDB consolidation** — delete cargoscreen's own `WatermillOffset`/`DynamoSupport`/`DynamoTableCommand`/`DateToEpochSecond` and adopt the migrated `consumer-commons` entity + `DynamoDbAdminUtil`, verifying byte-identical offset round-trip. Remove dead SNS/SQS; add `junit-vintage-engine`.

> **Residual caution:** the consolidation must not change the physical table name or any attribute name — gate cutover on a real-item offset fixture.

---

## 8. Peer review (incorporated)

- **Offset round-trip after consolidation** — `dynamo-integration-test` fixture seeded from the real cargoscreen item; diff local vs commons entity first. **Resolved (test plan).**
- **S3 metadata** — metadata-free `putObject`; **no S-G2.** **Resolved.**
- **Dead SNS / unused SQS** — confirmed; remove. **Resolved.**
- **JUnit 4** — add `junit-vintage-engine`. **Tracked.**
- **Credential/region parity** — v2 default providers; `regionEndpoint`/`signingRegion` → `DynamoDbClientConfig`. **Resolved (verify in dev run).**
- **Reconnect/ION-14324** — gRPC, non-AWS; unchanged. **Out of scope.**

---

## 9. Open questions / dependencies / sequencing

- **Depends on:** `consumer-commons` Dynamo pilot landing first; `shared` migrating before S3/SSM rebind.
- **Open question:** whether the v2 create path must set `@DynamoDBStream(KEYS_ONLY)`; whether cargoscreen's own entity has any field the `consumer-commons` entity lacks (diff before deletion).
- **Sequencing:** offset remap (consumer-commons) → delete local Dynamo duplicates (incl. own `WatermillOffset`) + dead SNS/SQS → rebind S3/SSM → DW5/`InttraServer` + `junit-vintage-engine` → `mvn -pl watermill/cargoscreen-consumer -am verify` → aggregator `mvn verify`.
- **Cutover gate:** backward-compat offset fixture against the real cargoscreen `{env}_watermill_offset` item.

---

## 10. Configuration changes (ref master §10)

- **Preserve all keys:** cargoscreen topic name, `s3WorkspaceConfig.bucket`, `dynamoDbConfig.{environment,regionEndpoint,signingRegion,sseEnabled}`, `watermillServiceConfig.{userIdKey,passwordKey,maxRetry,retryDelay,offsetUpdateDelay,...}`.
- **DynamoDB:** explicit physical `tableName = "{environment}_watermill_offset"`; `DynamoDbClientConfig.endpointOverride(regionEndpoint)` + `Region.of(signingRegion)`; SSE + 10/10 throughput on create.
- **Credentials/region:** env/IAM via v2 default providers; `${PROFILE}/${ENV}` unchanged; any `${awsps:…}` via commons `ParameterStoreConfigTransform`.
- **Option B:** register the composed appianway `ServerCommand` on the `InttraServer` bootstrap.

---

## 11. cloud-sdk gaps — **NONE for cargoscreen-consumer**

| Need | cloud-sdk artifact (existing) |
|---|---|
| Single offset store | `DatabaseRepository`/`DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminCommand`, `dynamo-integration-test` |
| S3 write (metadata-free) | `StorageClient.putObject(bucket,key,bytes)` — **S-G2 not needed** |
| SSM gRPC credentials | `CloudParameterStore` (via shared `ParameterStore`) |
| DW5 base + config | `commons` `InttraServer` + composed appianway `ServerCommand` |

No `cloud-sdk-api`/`cloud-sdk-aws`/`commons` change required. The non-trivial work beyond the offset remap is **consolidating cargoscreen's own Dynamo layer onto `consumer-commons`**, removing dead SNS/SQS, and the **JUnit4→5 bridge** — none is a library change.

---

> **Scope boundary.** The gRPC/Watermill consumption layer (`e2open.watermill.proto.*` `CargoScreeningOutboundChangeEvent`, `ResponseConsumerObserver`, `ConsumerInitUtil`, reconnect/ION-14324 20 s stabilization) is **not AWS** and is out of scope — carried unchanged through both options.
