# cargoscreen-consumer — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `com.inttra.mercury:cargoscreen-consumer` (sub-module of the standalone `watermill` reactor, **no parent pom**) · Main: `CargoScreenConsumerApplication` · Port 8085 · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only cargoscreen-consumer's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`) — verified booting clean against INT (DynamoDB offset read + gRPC channel live).
> **Scope:** AWS v1→v2 + drop-`shared` only. The gRPC/proto consume layer (`ResponseConsumerObserver`, `ConsumerInitUtil`, ION-14324 reconnect/20 s stabilization, `maxRetry=25`) is **not AWS** and is untouched. `watermill/consumer-commons` migrates alongside.

---

## Contents

---

## 1. Overview

`cargoscreen-consumer` is a **single-topic, S3-only-sink** Watermill gRPC consumer: it subscribes to `INTTRA_INT-CARGOSCREENINGOUTBOUND`, parses proto `CargoScreeningOutboundChangeEvent`, and for every upsert whose `exStatus != ERROR` writes the `CargoScreeningOutbound` result as JSON to S3 at `{YYYYMMdd}/{offset}_{sourceSourceTxId}.json`; `ERROR` upserts are **logged only** — there is no downstream SQS queue and **no SNS publish**. It persists exactly one consumption offset (`WatermillOffset`, keyed by topic name) in DynamoDB and reads gRPC basic-auth credentials from SSM Parameter Store.

- **Current state (post ION-16098):** DW5 baseline done, still wired to **AWS Java SDK v1 (1.12.720)** via a **fully-local** DynamoDB/S3 layer (its own `vo/WatermillOffset`, `dynamodb/DynamoSupport`, `dynamodb/command/DynamoTableCommand`, `service/S3PublishService`, `dao/WatermillOffsetDao`) plus `shared` for `ConfigProcessingServerCommand`, `S3ConfigurationProvider`, `ParameterStoreModule`/`ParameterSupplier`, `NetworkRetryerModule`.
- **Target state:** AWS v2 via `cloud-sdk-api`/`cloud-sdk-aws` `1.0.27-SNAPSHOT`, `commons` for the config command, and slim `appianway-commons` for the appianway-only residue. `shared` dropped entirely. The module's **local Dynamo/S3 duplicates are deleted and consolidated onto `watermill/consumer-commons`**, which migrates to cloud-sdk **alongside** this module (consumer-commons is currently still on AWS v1 too).
- **Headline change:** two isolated AWS-layer swaps — (1) **DynamoDB offset** (`DynamoDBMapper`/`DynamoDBCrudRepository` → `DatabaseRepository[WatermillOffset,String]` via cloud-sdk-aws `DynamoRepositoryFactory`, preserving the physical table name `{env}_watermill_offset` and every attribute name/epoch-seconds encoding), and (2) **S3 write** (`AmazonS3.putObject` → `StorageClient.putObject`, metadata-free — **S-G2 not exercised**).

---

## 2. Current vs Target architecture

```
BEFORE — AWS v1, module-local Dynamo/S3
  e2open Watermill gRPC topic INTTRA_INT-CARGOSCREENINGOUTBOUND (NON-AWS) ─▶ ResponseConsumerObserver
     ─▶ S3PublishService (local) ─▶ AWS v1 AmazonS3
     ─▶ OffsetUtil + OffsetUpdateScheduler ─▶ WatermillOffsetDao (local, DynamoDBCrudRepository) ─▶ DynamoSupport (local) ─▶ AWS v1 AmazonDynamoDB + DynamoDBMapper
     ─▶ AuthCredentials ─▶ shared ParameterStoreModule/ParameterSupplier ─▶ AWS v1 AWSSimpleSystemsManagement
  shared: ConfigProcessingServerCommand, S3ConfigurationProvider, NetworkRetryerModule
  dead: AmazonSNS binding (bound in ExternalServicesModule, never invoked)

AFTER — AWS v2, consolidated on consumer-commons
  same gRPC topic (NON-AWS, unchanged) ─▶ ResponseConsumerObserver (unchanged)
     ─▶ S3PublishService (consumer-commons) ─▶ cloud-sdk-api StorageClient ─▶ cloud-sdk-aws S3StorageClient ─▶ AWS v2 BOM
     ─▶ OffsetUtil + OffsetUpdateScheduler (consumer-commons) ─▶ WatermillOffsetDao (over DatabaseRepository) ─▶ cloud-sdk-aws DynamoRepositoryFactory ─▶ AWS v2
     ─▶ AuthCredentials ─▶ cloud-sdk-api CloudParameterStore ─▶ cloud-sdk-aws ParameterStoreClient ─▶ AWS v2
  commons: ConfigProcessingServerCommand + appianway transform ; appianway-commons: AsyncDispatcher, config-transform glue
  AmazonSNS binding deleted (not replaced — module has zero SNS/SQS surface)
```

### 2.1 Class/type mapping

| Area | Current (AWS v1 + `shared`, module-local) | Target (cloud-sdk-api/aws + commons/appianway-commons) | Notes |
|---|---|---|---|
| S3 client | `AmazonS3`/`AmazonS3ClientBuilder` bound in `ExternalServicesModule` | `StorageClient` (cloud-sdk-api) impl `S3StorageClient` (cloud-sdk-aws), Guice-bound | metadata-free `putObject` — **S-G2 not needed** |
| S3 write | local `service/S3PublishService.uploadToS3(fullS3Path,payload)` → `s3Client.putObject(bucket,key,String)` | `consumer-commons S3PublishService.uploadToS3(bucket,fullS3Path,payload)` → `StorageClient.putObject(bucket,key,bytes)` | consumer-commons' `S3PublishService` **already takes `bucket` as a param** — cargoscreen just passes its bucket in; only the injected client type changes (v1→v2) |
| Offset entity | local `vo/WatermillOffset` — `@DynamoDBTable("watermill_offset")`, `@DynamoDBHashKey("topicName")`, `@DynamoDBAttribute offset/readDateTime/writeDateTime`, `@DynamoDBTypeConverted(DateToEpochSecond)`, `@DynamoDBStream(KEYS_ONLY)` | `consumer-commons vo/WatermillOffset` re-annotated to cloud-sdk-api `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField` + `LongEpochSecondAttributeConverter` | Delete cargoscreen's own copy; adopt consumer-commons' (currently byte-identical AWS-v1 twin) |
| Offset DAO | local `dao/WatermillOffsetDao extends DynamoDBCrudRepository[WatermillOffset,DynamoHashKey[String]]` | `consumer-commons WatermillOffsetDao` over `DatabaseRepository[WatermillOffset,String]` (via `DynamoRepositoryFactory`) | table name resolved by the same prefix-`{environment}_` convention, explicit `tableName="watermill_offset"` preserved |
| DynamoDB support/mapper | local `dynamodb/DynamoSupport` (`AmazonDynamoDBClientBuilder`, `DynamoDBMapper`, prefix override) | `consumer-commons DynamoSupport` rebased on `DynamoDbClientConfig` + `DynamoRepositoryFactory.createEnhancedRepository(...)` | delete cargoscreen's local copy entirely |
| Create-table CLI | local `dynamodb/command/DynamoTableCommand` (`TableUtils`, `SSESpecification`, RCU/WCU 25/25) | cloud-sdk-aws `DynamoDbAdminCommand`/`DynamoDbAdminUtil` | preserve SSE + throughput (INT yaml: `readCapacityUnits: 25`, `writeCapacityUnits: 25`, `sseEnabled: false`) |
| Offset service/scheduler/util | local `WatermillOffsetService`, `OffsetUpdateScheduler`, `OffsetUtil` | `consumer-commons` equivalents (already present, same logic — in-memory cursor + 15-min flush) | consolidate; behavior unchanged |
| gRPC creds | `grpc/AuthCredentials` via shared `ParameterSupplier`/`ParameterStoreModule` | `CloudParameterStore` — same 2-key lookup (`userIdKey`/`passwordKey`) | resolution mechanism only changes; SSM paths unchanged (§5) |
| Config command | `shared.command.ConfigProcessingServerCommand` + `shared.config.S3ConfigurationProvider` | `commons ConfigProcessingServerCommand` + composed appianway property-substitution transform | §5 |
| Networking glue | `shared.networkservices.NetworkRetryerModule` (installed but no `networkServiceConfig` block — dead weight) | dropped — no replacement (module never calls `AuthClient`) | confirmed by yaml |
| Dead AWS binding | `AmazonSNS`/`AmazonSNSClientBuilder` bound, **never injected/invoked** | removed entirely | no cloud-sdk `NotificationService` needed |
| gRPC transport | `io.grpc.netty.shaded`, `ConsumerInitUtil`, `ResponseConsumerObserver`, ION-14324 reconnect (20 s), `maxRetry=25` | **unchanged** — non-AWS | out of scope |

**Diff check performed:** `cargoscreen-consumer`'s `vo/WatermillOffset.java` and `watermill/consumer-commons`'s copy are currently **byte-identical**. Same for `S3PublishService` (consumer-commons' version already takes `bucket` as a call parameter — a strict superset) and `WatermillOffsetDao`/`DynamoSupport`. The consolidation is a **delete-and-repoint**, not a re-design — the main work is the AWS v1→v2 rebind inside `consumer-commons` itself, which cargoscreen then inherits for free.

---

## 3. AWS touchpoints

| Touchpoint | Direction | INT resource | cloud-sdk client | Notes |
|---|---|---|---|---|
| SQS | — | **none** | — | module has no SQS in/out at all |
| SNS | — | **none** (dead v1 binding removed) | — | `AmazonSNS` was bound but never invoked; deleted, not replaced |
| S3 | write only | `inttra-int-watermill-cargoscreen` | `StorageClient.putObject(bucket,key,bytes)` (metadata-free) | key `{YYYYMMdd}/{offset}_{sourceSourceTxId}.json`; **S-G2 not exercised** |
| DynamoDB | read + write (offset) | table `inttra_int_watermill_offset` (prefix `inttra_int` + `watermill_offset`, hash key `topicName`) | `DatabaseRepository[WatermillOffset,String]` via `DynamoRepositoryFactory` | single row, keyed by topic `INTTRA_INT-CARGOSCREENINGOUTBOUND`; RCU/WCU 25/25, SSE disabled |
| SES | — | **none** | — | not applicable |
| Param Store (SSM) | read (boot / call-credentials) | `/inttra/int/appianway/watermill-grpc/se/username`, `.../password` | `CloudParameterStore` | resolved per gRPC call via `AuthCredentials` (unchanged mechanism, new backing client) |
| gRPC (non-AWS) | consume | `watermill.staging.e2open.com:443`, topic `INTTRA_INT-CARGOSCREENINGOUTBOUND`, tenant `INTTRA_INT` | — | `maxRetry=25`, `retryDelay=10s`, keep-alive 30s/20s, idle 30m; ION-14324 20 s channel-stabilization on reconnect |
| Port / health | — | `8085` | — | **no health checks registered**; `/admin/opsHealthcheck` → 404; verification is boot-evidence only |

---

## 4. Sequence — consume → (S3 write or log) → advance offset

```
  startup — seed offset:
     ResponseConsumerObserver ─▶ WatermillOffsetService.getOffset("INTTRA_INT-CARGOSCREENINGOUTBOUND")
        ─▶ WatermillOffsetDao.findOne(hashKey=topic) ─▶ DatabaseRepository.findById(topic) ─▶ GetItem(PK=topicName)
           present ─▶ offset=N ─▶ startOffset = N+1
           absent  ─▶ save(WatermillOffset{topic,-1}) ─▶ PutItem ; startOffset = 0

  steady-state consumption:
     gRPC ─▶ RawData @ offset k (CargoScreeningOutboundChangeEvent)
        for each upsert in the change event:
           exStatus != ERROR ─▶ S3PublishService.uploadToS3(bucket, "{YYYYMMdd}/{offset}_{sourceSourceTxId}.json", json) ─▶ StorageClient.putObject(bucket, key, bytes)   [metadata-free]
           exStatus == ERROR ─▶ log BPResult messages (terminal — no S3/queue write)
        OffsetUtil.updateOffset(k)   [in-memory cursor only]

  every offsetUpdateDelay (15 min):
     OffsetUtil ─▶ WatermillOffsetService.updateOffset(topic, OffsetUtil.getOffset()) ─▶ Dao.update ─▶ DatabaseRepository.save ─▶ PutItem (last-writer-wins)

  onError (reconnect, ION-14324 — non-AWS logic unchanged):
     WatermillOffsetService.updateOffset(topic, currentOffset)   [flush before reconnect]
     channel.shutdownNow(); awaitTermination(20s); new channel; sleep 20s; consumeForever(persisted+1)
```

**At-least-once preserved:** the in-memory cursor advances per message; DynamoDB is flushed on the 15-minute scheduler and on `onError` before reconnect. On restart the stream resumes at `persisted_offset + 1`. The 20 s channel-stabilization window and `maxRetry=25` cap are gRPC concerns, unaffected by the AWS-layer swap.

---

## 5. Configuration changes

### 5.1 Property-key table (INT values)

| Property key | INT value | Consumed by (yaml path) | Change? |
|---|---|---|---|
| `componentName` | `cargoscreen-consumer` | (metrics/logging tag) | unchanged |
| `watermill-grpc.consumer.username.key` | `/inttra/int/appianway/watermill-grpc/se/username` | `watermillServiceConfig.userIdKey` | unchanged (still an SSM *path*, resolved at gRPC-call time via `CloudParameterStore`) |
| `watermill-grpc.consumer.password.key` | `/inttra/int/appianway/watermill-grpc/se/password` | `watermillServiceConfig.passwordKey` | unchanged |
| `watermill-grpc.consumer.tenant` | `INTTRA_INT` | `watermillServiceConfig.tenant` | unchanged |
| `watermill-grpc.consumer.host` | `watermill.staging.e2open.com` | `watermillServiceConfig.host` | unchanged (non-AWS) |
| `watermill-grpc.consumer.port` | `443` | `watermillServiceConfig.port` | unchanged |
| `watermill-grpc.consumer.topic.name` | `INTTRA_INT-CARGOSCREENINGOUTBOUND` | `watermillServiceConfig.topicName` | unchanged — **do not rename** |
| `watermill-grpc.dynamo.environment` | `inttra_int` | `dynamoDbConfig.environment` | unchanged — table-name prefix; **do not rename** |
| `watermill-grpc.consumer.s3WorkspaceConfig.bucket` | `inttra-int-watermill-cargoscreen` | `s3WorkspaceConfig.bucket` | unchanged — **do not rename** |
| `watermill-grpc.consumer.offsetUpdateDelay` | `15` (minutes) | `watermillServiceConfig.offsetUpdateDelay` | unchanged |
| `watermill-grpc.consumer.keepAliveTime.seconds`/`keepAliveTimeout.seconds`/`idleTimeout.minutes` | `30`/`20`/`30` | `watermillServiceConfig.*` | unchanged (non-AWS gRPC) |
| `watermill-grpc.consumer.maxRetry` | `25` | `watermillServiceConfig.maxRetry` | unchanged (non-AWS gRPC retry cap) |
| `watermill-grpc.consumer.retryDelay` | default `10` | `watermillServiceConfig.retryDelay` | unchanged |
| `server.connector.port` | default `8085` | `server.connector.port` | unchanged — port **8085** |
| `watermill-grpc.consumer.healthCheckConfig.errorRateThreshold` | default `5.0` | `healthCheckConfig.errorRateThreshold` | present in config POJO but **unused — no health checks registered** |
| `networkservices.healthCheckUrl` | referenced by yaml but **no `networkServiceConfig` block exists** | n/a | dead reference — carried through unchanged (harmless) |
| `dynamoDbConfig.readCapacityUnits` / `writeCapacityUnits` | `25` / `25` (yaml) | `dynamoDbConfig.*` | unchanged; create-table path only |
| `dynamoDbConfig.sseEnabled` | `false` (yaml) | `dynamoDbConfig.sseEnabled` | unchanged |

### 5.2 SSM parameter table

| SSM path | Purpose | Today | After |
|---|---|---|---|
| `/inttra/int/appianway/watermill-grpc/se/username` | gRPC basic-auth username | shared `ParameterSupplier.getValue(key)` → v1 `AWSSimpleSystemsManagementClientBuilder.defaultClient()`, called once at `AuthCredentials` construction | `CloudParameterStore.getParameter(path)` — same call site (`AuthCredentials` ctor), same one-time-per-singleton resolution. **Not** moved to boot-time `${awsps:/path}`; stays a runtime-resolved credential since it feeds gRPC `CallCredentials`, not a YAML field. |
| `/inttra/int/appianway/watermill-grpc/se/password` | gRPC basic-auth password | same | same |

No `usePassThrough` flag exists in this module (a network-services-specific concept — cargoscreen-consumer has no `networkServiceConfig` block). Both SSM paths remain literal path strings; only the Java-side resolver changes.

### 5.3 Config-command composition

- CLI shape **unchanged**: `run cargoscreen-consumer.yaml conf/int/cargoscreen-consumer.properties ../../configuration/int/network-services.properties ../../configuration/int/datadog.properties` — cwd = `watermill/cargoscreen-consumer/`, **two levels up** to `configuration/` (no parent pom).
- `CargoScreenConsumerApplication.initialize(bootstrap)` swaps `shared.command.ConfigProcessingServerCommand` → `commons ConfigProcessingServerCommand`, composed as appianway property-substitution transform → `TrimConfigCommentsTransform` → `ParameterStoreConfigTransform`. No `${awsps:...}` tokens in this module's yaml, so `ParameterStoreConfigTransform` is a no-op pass-through today, wired for consistency/future use.
- `shared.config.S3ConfigurationProvider` → moved to appianway-commons — still conditional on `CONFIG_LOCATION=s3` (not set in local/INT runs).
- `DynamoTableCommand` bootstrap registration → `DynamoDbAdminCommand` (cloud-sdk-aws), or the consolidated `consumer-commons` equivalent; SSE/throughput carried through.
- **Unchanged:** CLI arg order/shape, `CONFIG_REGION`, `datadog.properties` (passed but nothing in this module's yaml references its keys), no `networkServiceConfig` block.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap ID | Applicable? | Detail |
|---|---|---|
| **S-G2** (metadata/content-type `putObject`) | **No** | S3 write is metadata-free (`putObject(bucket,key,bytes)`, no `ObjectMetadata`/content-type) — plain `putObject` suffices |
| **W-G9** (workflow-model parity) | **No** | this module never publishes/consumes `MetaData`/`Event`/`Annotations` — no SNS, no SQS, no workflow envelope at all |
| **X-G7 / X-G8** | **No** | not applicable |
| **C-G6** | **No — optional** | composition works without it |
| DynamoDB v2 enhanced client (native, not a "gap") | **Yes — headline change** | `DatabaseRepository[WatermillOffset,String]` + `DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminUtil` |

**Consumes from `commons`:** `ConfigProcessingServerCommand`, health base (unused here — no `registerHealthChecks`), `InttraServer` base if adopted (already runs `Application` directly; DW5 base in place).
**Consumes from `cloud-sdk-api`/`cloud-sdk-aws`:** `StorageClient`/`S3StorageClient`, `CloudParameterStore`, `DatabaseRepository[WatermillOffset,String]`/`DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminCommand`/`DynamoDbAdminUtil`.
**Moves to `appianway-commons`:** `AsyncDispatcher`/`AbstractTask` (this module's `task/AsyncDispatcher` — retained, repointed to the slim library instead of `shared`), the appianway config property-substitution transform, `S3ConfigurationProvider` (relocated, conditional path unused today).
**NOT moved / NOT needed:** `NetworkRetryerModule` (dead — drop entirely, no replacement); `HealthCheckConfig`/`errorRateThreshold` (never wired to a live registry — no change).

---

## 7. Maven dependency changes

`watermill/pom.xml` (aggregator, **no parent** — mirrors the BOM/version pins) + this module's `pom.xml`:

**Remove**
- `com.inttra.mercury.shared:mercury-shared`.
- `com.amazonaws:aws-java-sdk-sqs` (**declared but unused** — no `AmazonSQS` instantiation anywhere).
- `com.amazonaws:aws-java-sdk-dynamodb`.
- `com.inttra.mercury:dynamo-client:1.0` (in-house v1 `DynamoDBCrudRepository`, superseded by the cloud-sdk-aws enhanced client).
- Transitive v1 SDK from `mercury-shared` (S3/SSM).
- Dead Guice binding: `AmazonSNS`/`AmazonSNSClientBuilder` in `ExternalServicesModule`.
- `<aws-java-sdk.version>1.12.720</aws-java-sdk.version>` in `watermill/pom.xml` once no module references it.

**Add**
- `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`.
- `com.inttra.mercury:consumer-commons` (this module's reactor sibling — **must itself land its AWS v1→v2 rebind in lockstep**, since it is currently still on `AmazonS3`/`DynamoDBCrudRepository` v1).
- AWS SDK **v2** comes transitively via `cloud-sdk-aws` (managed by the mercury-services-commons BOM); do not declare v2 artifacts directly.

Add `mercury.commons.version=1.0.27-SNAPSHOT` to `watermill/pom.xml` `<properties>` (existing java 17 / dropwizard 5.0.2 / jetty 12.1.9 / jackson 2.21.4 / grpc 1.77.0 pins unchanged).

**Keep unchanged (non-AWS):** gRPC/protobuf stack (`io.grpc:grpc-{netty-shaded,protobuf,stub}:1.77.0` via `grpc-bom`, `protobuf-java{,-util}:4.33.1`, `protobuf-java-format:1.4`, `protobuf-maven-plugin 0.6.1`, all `src/main/proto/**`); `guava`, `guice:7.0.0`, `metrics-guice`, Lombok, `commons-cli`; shade-plugin config (main class `CargoScreenConsumerApplication`, **`clean` required before `package`**); `os-maven-plugin`.

**Tests:** module is on **JUnit 5** already (versions dropped to inherit the DW5 junit-bom) — no JUnit 4→5 migration needed; `mockito-core`, `assertj-core`, `functional-testing:1.0` (test-scope) retained; `functional-testing` migrates its AWS fakes to cloud-sdk-api in lockstep.

**Verify:** `mvn -pl watermill/consumer-commons,watermill/cargoscreen-consumer -am clean verify` green (both move together — consumer-commons is the shared consolidation target). INT boot evidence: `DynamoSupport`/enhanced-client init with `inttra_int_` prefix, `Offset found for topic INTTRA_INT-CARGOSCREENINGOUTBOUND`, `ResponseConsumerObserver : Initializing ResponseObserver`, `ConsumerInitUtil : Channel initialized`, bound `0.0.0.0:8085`, zero errors.

---

## 8. Tests

- **Offset persistence (highest priority — data-plane safety):** move `WatermillOffsetServiceTest`/`OffsetUtilTest` assertions to exercise the `consumer-commons`-consolidated entity against `dynamo-integration-test` (DynamoDB-Local). Assert: table name resolves to `inttra_int_watermill_offset`; attribute names stored exactly as `topicName`/`offset`/`readDateTime`/`writeDateTime`; `readDateTime`/`writeDateTime` still serialize via epoch-seconds (`LongEpochSecondAttributeConverter` matches the old `DateToEpochSecond` byte-for-byte); `findById(absent)` → empty → `initializeOffset(topic, -1L)` → resume at 0.
- **Backward-compat fixture (gate, critical):** seed DynamoDB-Local with a real-shaped `inttra_int_watermill_offset` item keyed `INTTRA_INT-CARGOSCREENINGOUTBOUND` (a snapshot of the real INT row, offset value `0` at last check); assert the migrated entity deserializes it and resumes at `+1`.
- **S3 write:** re-point `S3PublishService` test to a `StorageClient` fake; assert `putObject(bucket="inttra-int-watermill-cargoscreen", key="{YYYYMMdd}/{offset}_{sourceSourceTxId}.json", bytes)` is called for `exStatus != ERROR` upserts, and the `exStatus == ERROR` path performs **no** S3 call (log-only, verified via no-interaction).
- **`buildFileName` unit test:** unchanged logic — assert filename falls back to `{offset}.json` when `sourceTxId` is blank, else `{offset}_{sourceTxId}.json`.
- **AuthCredentials / SSM:** unit test with a `CloudParameterStore` fake returning fixed username/password; assert gRPC `Metadata` headers (`username`/`password`/`tenant`/`topic`) populate identically.
- **Create-table CLI:** `DynamoTableCommandTest` (or its cloud-sdk-aws successor) asserts `DynamoDbAdminUtil`/`DynamoDbAdminCommand` creates `inttra_int_watermill_offset` with SSE disabled + 25/25 RCU/WCU, matching yaml literals.
- **gRPC consumer / reconnect (ION-14324):** unchanged, non-AWS — keep the existing `ResponseConsumerObserver` reconnect tests green (they exercise `watermillOffsetService.updateOffset(...)` on the error path, doubling as an integration check that the new `DatabaseRepository`-backed save still succeeds).
- **`functional-testing` fakes:** re-point shared AWS-fake helpers to cloud-sdk-api interfaces (`StorageClient`, `CloudParameterStore`).

---

## 9. Rollout & verification

Per the program order, this module is in the **last** rollout group — after `watermill-publisher`, alongside the other three watermill consumers (gRPC + DynamoDB offset; port 8085; no parent pom):

1. **Pilot the Dynamo + S3 rebind in `watermill/consumer-commons` first** — currently still on AWS v1; must land the v2 rebind before cargoscreen can consolidate onto it. Verify with `mvn -pl watermill/consumer-commons -am verify` (`dynamo-integration-test` for the offset entity).
2. **Delete cargoscreen-consumer's local duplicates:** `dynamodb/DynamoSupport`, `dynamodb/command/DynamoTableCommand`, `vo/WatermillOffset`, `vo/DateToEpochSecond`, `dao/WatermillOffsetDao`, `service/S3PublishService` — repoint all call sites (`ResponseConsumerObserver`, `WatermillConsumerModule`, `ExternalServicesModule`) to the `consumer-commons` equivalents.
3. **Rebind SSM:** `AuthCredentials` swaps `ParameterSupplier` (shared) for `CloudParameterStore`; remove `ParameterStoreModule`/`NetworkRetryerModule` installs.
4. **Remove dead SNS binding** (`AmazonSNS`) and the unused `aws-java-sdk-sqs` dependency.
5. **Config command swap:** `shared` → `commons`, composed per §5.3; `S3ConfigurationProvider` relocated to appianway-commons.
6. **Maven:** apply §7 remove/add list; add `mercury.commons.version` to `watermill/pom.xml`.
7. `mvn -pl watermill/consumer-commons,watermill/cargoscreen-consumer -am clean verify` green.
8. **INT boot check** — from `watermill/cargoscreen-consumer/`: confirm `DynamoSupport` created with `inttra_int_` prefix, `Offset found for topic INTTRA_INT-CARGOSCREENINGOUTBOUND` (or `initializeOffset` on first-ever boot), `ResponseConsumerObserver : Initializing ResponseObserver`, `ConsumerInitUtil : Channel initialized`, bound `0.0.0.0:8085`, zero errors, no message consumed during the verification window (data-plane-safe, offset stays at `0`).
9. **Gate cutover** on the backward-compat offset fixture (§8) passing against a real snapshot of the INT `inttra_int_watermill_offset` item for this topic.
10. Aggregator-wide `mvn verify` across the full `watermill` reactor once all four consumers + `consumer-commons` land.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Offset-table data-shape incompatibility** — wrong physical table name (`inttra_int_watermill_offset`) or a renamed attribute → cargoscreen silently re-consumes from 0, duplicating S3 writes | **Highest priority.** Preserve the exact table name and attribute names; confirmed the `consumer-commons` entity is currently byte-identical to cargoscreen's local copy — re-verify after cloud-sdk-api re-annotation with a real-item `dynamo-integration-test` fixture before cutover. |
| **`consumer-commons` is itself still AWS v1** — cargoscreen's consolidation is blocked until consumer-commons lands its own v2 rebind | Sequence consumer-commons' migration strictly before this module's Dynamo/S3 delete step (§9 step 1 before step 2); do not attempt partial consolidation. |
| Removing the dead `AmazonSNS` binding / unused `aws-java-sdk-sqs` introduces a missed real usage | Confirmed via source read: no `AmazonSNS`/`AmazonSQS` method call anywhere — safe to delete; add a compile-time check (no import) as regression guard. |
| SSE / 25x25 RCU-WCU throughput dropped on table create | Carry through explicitly in `DynamoDbAdminCommand`/`DynamoDbAdminUtil`; assert in the create-table test. |
| Reconnect parity (20 s stabilization, ION-14324, `maxRetry=25`) regresses due to a refactor touching `ResponseConsumerObserver`'s offset-flush-on-error call | gRPC logic itself is untouched; the only line touched in `onError` is the `watermillOffsetService.updateOffset(...)` call target (same signature, new backing repository) — keep existing reconnect tests green as the regression guard. |
| SSM credential resolution timing change (`ParameterSupplier` one-shot vs `CloudParameterStore`) | `AuthCredentials` is `@Singleton`-scoped and resolves both keys once at construction today; preserve that same one-time-per-process resolution — do not introduce a per-gRPC-call SSM round-trip. |
| `network-services.properties`/`networkServiceConfig` confusion — no auth dependency despite the file being passed on the CLI | No action; `healthCheckConfig.networkServiceHealthCheckUrl` is never wired to an active health check — dead config, carried through as-is per the "do not silently rename" rule. |
| Region/endpoint resolution drift for the new `DynamoDbClientConfig` | Map existing `regionEndpoint`/`signingRegion` (if set) 1:1 to `DynamoDbClientConfig.endpointOverride(...)`/`Region.of(...)`; INT relies on default region resolution (no override) — verify no unintended override is introduced. |
