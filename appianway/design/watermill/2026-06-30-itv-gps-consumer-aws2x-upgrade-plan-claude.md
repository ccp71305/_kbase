# `itv-gps-consumer` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury:itv-gps-consumer` (sub-module of `watermill`) · Date: 2026-06-30 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`mercury-services-commons` `1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Guice **7.0.0**, Jackson **2.21.0**).
> Companion DESIGN: [`2026-06-30-itv-gps-consumer-aws2x-upgrade-DESIGN-claude.md`](2026-06-30-itv-gps-consumer-aws2x-upgrade-DESIGN-claude.md).
> MASTERs: [shared plan](../../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §10/§11 · [watermill plan](../../docs/2026-05-31-watermill-aws2x-upgrade-plan-claude.md).

---

## 0. Scope note (vs. the watermill aggregator plan)

`itv-gps-consumer` is the **simplest** of the appianway Watermill consumers — a pure **S3-only sink** (no SQS, no SNS). It matches the watermill aggregator plan's generic consumer profile almost exactly, with three module-specific deltas this per-module plan records: (1) it carries **local DynamoDB duplicates** (`DynamoSupport`, `DynamoTableCommand`, `vo/DateToEpochSecond`, plus an unused `vo/Expires` TTL helper) to be consolidated; (2) it has a **dead `AmazonSNS` binding** and an unused transitive `aws-java-sdk-sqs` to remove; (3) it is on **JUnit 4**, so a `junit-vintage-engine` bridge is needed (unlike booking-inbound/visibility-inbound, which are already Jupiter). Everything else inherits the watermill plan unchanged.

---

## 1. Executive summary

`itv-gps-consumer` is a Dropwizard 4 application running a single e2open Watermill gRPC stream consumer for topic **`INTTRA-ITVGPSUPDATE`**. It parses proto `ITVShipmentStatusChangeEvent`, serializes to JSON, and writes `{offset}.json` to S3 `inttra-int-watermill-gps`; it persists one consumption offset in DynamoDB and reads gRPC credentials from SSM. AWS footprint: **S3(write) + DynamoDB(offset) + SSM** on AWS Java SDK **v1 `1.12.720`**, Dropwizard **4.0.16**, gRPC **1.77.0**.

Per the directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§5): consume cloud-sdk **as a client** (no cloud-sdk/commons change, **S-G2 not used**); remap the DynamoDB offset onto `DatabaseRepository`/`@Table`/`LongEpochSecondAttributeConverter` **consolidated in `consumer-commons`**, preserving the exact physical table + attribute names; rebind S3/SSM onto cloud-sdk via `shared`; delete the dead SNS binding and local Dynamo duplicates; move onto `InttraServer`/DW5. The gRPC layer is non-AWS and out of scope.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

AWS Java SDK **v1** `1.12.720`; Dropwizard `4.0.16`; gRPC `1.77.0`. Direct AWS deps come via `consumer-commons` (`aws-java-sdk-dynamodb`, unused `aws-java-sdk-sqs`) and transitively via `shared` (`s3`, `ssm`); `dynamo-client` supplies the in-house `DynamoDBCrudRepository`.

### 2.1 S3 — write (metadata-free)
- `S3PublishService.uploadToS3(bucket, "{offset}.json", payload)` → `s3Client.putObject(bucket, key, String)`; **no `ObjectMetadata`**. Client `AmazonS3ClientBuilder.standard().build()` (`ExternalServicesModule:32`). Bucket = `s3WorkspaceConfig.bucket` (`inttra-int-watermill-gps`). **⇒ S-G2 not required.**

### 2.2 SQS — absent
- No `AmazonSQS` instantiation or `sendMessage`. `aws-java-sdk-sqs` is declared transitively (consumer-commons) but **never referenced** here.

### 2.3 SNS — dead binding
- `ExternalServicesModule:29-30` binds `AmazonSNS` via `AmazonSNSClientBuilder.standard().withClientConfiguration(AWSClientConfiguration.sns_publish)`, but it is **never injected or invoked**. Dead code → remove.

### 2.4 DynamoDB — single offset (with local duplicates)
- Uses `consumer-commons` `vo/WatermillOffset` (`@DynamoDBTable("watermill_offset")`, `@DynamoDBHashKey("topicName")`, `@DynamoDBAttribute offset/readDateTime/writeDateTime`, `@DynamoDBTypeConverted(DateToEpochSecond)`) and `WatermillOffsetDao`/`WatermillOffsetService`.
- **Local duplicates in this module:** `dynamodb/DynamoSupport` (`AmazonDynamoDBClientBuilder`, `DynamoDBMapper`, `DynamoDBMapperConfig`), `dynamodb/command/DynamoTableCommand` (`TableUtils.createTableIfNotExists`, SSE, 10/10 throughput), `vo/DateToEpochSecond` (duplicate converter), `vo/Expires` (TTL `expiresOn` interface; appears unused).
- Table prefix `"{environment}_watermill_offset"`; single topic → single row. One `OffsetUtil` + one `OffsetUpdateScheduler` (`WatermillGpsConsumerApplication:60`).

### 2.5 SSM — gRPC credentials
- `AuthCredentials` reads `watermillServiceConfig.userIdKey`/`passwordKey` via shared `ParameterSupplier`/`ParameterStoreModule` (`AWSSimpleSystemsManagementClientBuilder.defaultClient()`).

### 2.6 Config / Dropwizard
- `WatermillGpsConsumerApplication extends Application<WatermillConsumerConfiguration>`; `S3ConfigurationProvider` (conditional) + `ConfigProcessingServerCommand`; local `DynamoTableCommand`. **Tests: JUnit 4** (surefire-junit47, `@RunWith(MockitoJUnitRunner)`).

### 2.7 Model jar — none
- No booking/visibility domain model dependency; consumes the e2open proto and emits JSON only.

---

## 3. Findings

- **The offset store is the only correctness-critical AWS surface.** Highest risk: mapping the migrated `WatermillOffset` to a different physical table or renamed attribute → silent re-consumption from 0 (GPS replay).
- **S3 write is metadata-free ⇒ S-G2 not consumed.**
- **Local Dynamo duplication** (`DynamoSupport`/`DynamoTableCommand`/`DateToEpochSecond`) should be **deleted and consolidated** onto the migrated `consumer-commons` (watermill plan §9), removing divergence.
- **Dead AWS code:** `AmazonSNS` binding + unused `aws-java-sdk-sqs` — remove during the migration.
- **`vo/Expires` TTL:** confirm whether any persisted entity uses `expiresOn`; map to `@TTL` if so, else delete.
- **JUnit 4** — needs `junit-vintage-engine` during transition (unlike the Jupiter-based siblings).
- **No model jar / no SQS / no SNS** ⇒ no cross-workspace contract risk; this is the lowest-risk consumer to migrate.
- **gRPC** (topic, `maxInboundMessageSize`, `MAX_RETRY_LIMIT=100`) is non-AWS — untouched.

---

## 4. Option A — keep DW4; swap AWS internals to cloud-sdk

Keep DW 4.0.16/app/`ConfigProcessingServerCommand`; remap the offset (consolidated in `consumer-commons`); rebind S3 → `StorageClient`, SSM → `CloudParameterStore` via migrated `shared`; delete dead SNS/SQS.

- **Pros:** smallest blast radius; no framework jump; reversible. Identical cloud-sdk consumption to Option B.
- **Cons:** keeps bespoke DW4 base; long-term divergence.
- **Effort:** Low. **Risk:** Low.

---

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A plus moving the application onto `commons` `InttraServer` (DW 5.0.1) with the composed appianway `ServerCommand`; add `junit-vintage-engine`. Keep the gRPC consumer, `ConsumerInitUtil`, single `OffsetUpdateScheduler`.

- **Pros:** platform convergence; removes bespoke DW plumbing.
- **Cons:** DW4→5 + JUnit4→5 platform move (low complexity here given the small surface).
- **Effort:** Low–Medium. **Risk:** Low–Medium.

---

## 6. Comparison matrix

| Criterion | Option A (DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 → cloud-sdk | ✅ | ✅ |
| Required cloud-sdk change | none (no S-G2) | none (no S-G2) |
| Impact on mercury-services | none | none |
| Effort | Low | Low–Medium |
| Risk | Low | Low–Medium |
| Framework churn | none | DW4→5 + JUnit4→5 |
| Consistency w/ platform | AWS layer only | full |
| Incremental / reversible | ✅ | stage carefully |

> **Verdict:** the directive makes **Option B** authoritative; both share the identical cloud-sdk contract and zero cloud-sdk changes. itv-gps is the **ideal early pilot** for the watermill consumer fleet given its minimal surface.

---

## 7. Recommendation

**Adopt Option B**, consuming cloud-sdk `1.0.26-SNAPSHOT` as a client with **no cloud-sdk change and no S-G2**. Migrate itv-gps **early** (right after the `consumer-commons` Dynamo pilot) to de-risk the pattern: it has no SQS/SNS/model-jar coupling, so the only real hazard is offset backward-compat. Delete the local Dynamo duplicates and the dead SNS/SQS during the move; add `junit-vintage-engine`.

> **Residual caution:** preserve the offset table/attribute shape and the S3 bucket/key (`inttra-int-watermill-gps` / `{offset}.json`) exactly — the latter is the contract the downstream `visibility-itv-gps-processor` S3→SNS→SQS pickup depends on.

---

## 8. Peer review (incorporated)

- **Offset round-trip** — `dynamo-integration-test` fixture seeded from the real ITV item; gate cutover. **Resolved (test plan).**
- **S3 metadata** — metadata-free `putObject(bucket,key,bytes)`; **no S-G2.** **Resolved.**
- **Dead SNS / unused SQS** — confirmed never invoked; remove. **Resolved.**
- **`vo/Expires` TTL** — verify usage; map to `@TTL` or delete. **Tracked (§9).**
- **JUnit 4** — add `junit-vintage-engine`. **Tracked.**
- **Credential/region parity** — v2 default providers; `regionEndpoint`/`signingRegion` → `DynamoDbClientConfig`. **Resolved (verify in dev run).**

---

## 9. Open questions / dependencies / sequencing

- **Depends on:** `consumer-commons` Dynamo pilot landing first; `shared` migrating before S3/SSM rebind.
- **Open question:** whether the v2 create path must set `@DynamoDBStream(KEYS_ONLY)`; whether any entity persists `expiresOn` (→ `@TTL`).
- **Sequencing:** offset remap (consumer-commons) → delete local Dynamo duplicates + dead SNS/SQS → rebind S3/SSM → DW5/`InttraServer` + `junit-vintage-engine` → `mvn -pl watermill/itv-gps-consumer -am verify` → aggregator `mvn verify`.
- **Cutover gate:** backward-compat offset fixture **and** confirmation that `{offset}.json` files still land in `inttra-int-watermill-gps`.

---

## 10. Configuration changes (ref master §10)

- **Preserve all keys:** topic name (`INTTRA-ITVGPSUPDATE`), `s3WorkspaceConfig.bucket`, `dynamoDbConfig.{environment,regionEndpoint,signingRegion,sseEnabled}`, `watermillServiceConfig.{userIdKey,passwordKey,...}`.
- **DynamoDB:** explicit physical `tableName = "{environment}_watermill_offset"`; `DynamoDbClientConfig.endpointOverride(regionEndpoint)` + `Region.of(signingRegion)`; SSE/throughput on create.
- **Credentials/region:** env/IAM via v2 default providers; `${PROFILE}/${ENV}` unchanged; any `${awsps:…}` via commons `ParameterStoreConfigTransform`.
- **Option B:** register the composed appianway `ServerCommand` on the `InttraServer` bootstrap.

---

## 11. cloud-sdk gaps — **NONE for itv-gps-consumer**

| Need | cloud-sdk artifact (existing) |
|---|---|
| Single offset store | `DatabaseRepository`/`DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminCommand`, `dynamo-integration-test` |
| S3 write (metadata-free) | `StorageClient.putObject(bucket,key,bytes)` — **S-G2 not needed** |
| SSM gRPC credentials | `CloudParameterStore` (via shared `ParameterStore`) |
| DW5 base + config | `commons` `InttraServer` + composed appianway `ServerCommand` |
| TTL (if any) | `@TTL` (cloud-sdk-api) |

No `cloud-sdk-api`/`cloud-sdk-aws`/`commons` change required. The only non-trivial work beyond the offset remap is **deleting local duplicates + dead SNS/SQS** and the **JUnit4→5 bridge** — neither is a library change.

---

> **Scope boundary.** The gRPC/Watermill consumption layer (`e2open.watermill.proto.logistics.itv.*`, `ResponseConsumerObserver`, `ConsumerInitUtil`, `maxInboundMessageSize`, `MAX_RETRY_LIMIT=100`) is **not AWS** and is out of scope — carried unchanged through both options.
