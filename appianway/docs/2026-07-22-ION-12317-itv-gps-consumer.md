# itv-gps-consumer — AWS SDK v2 (cloud-sdk) Upgrade Design

> Module: `com.inttra.mercury:itv-gps-consumer` (standalone project under `watermill/`, parent = the `watermill` aggregator pom only — no appianway root parent) · Main: `WatermillGpsConsumerApplication` · Port 8085 · Part of the ION-12317 AppianWay AWS SDK v2 upgrade program.
> **Shared foundation** (mapping, slim `appianway-commons`, config/SSM model, cloud-sdk gaps S-G2/W-G9/X-G7/X-G8, Maven template, rollout) lives on the program page — this page adds only itv-gps-consumer's module-specific detail.
> **Baseline (unchanged):** Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098, in `develop`) — verified booting clean against INT.
> **Scope:** AWS v1 → v2 + drop `shared` only. The gRPC/Watermill consume layer (`ITVShipmentStatusChangeEvent`, `ResponseConsumerObserver`, `ConsumerInitUtil`, `WatermillConsumerTask`/`AsyncDispatcher`, `MAX_RETRY_LIMIT=100` reconnect) is **not AWS** and is untouched. `watermill/consumer-commons` migrates alongside.

---

## Contents

---

## 1. Overview

`itv-gps-consumer` is the **simplest** of the four appianway Watermill gRPC consumers: a pure **S3-only sink**. It opens a single gRPC stream, subscribes to tenant **`INTTRA`** / topic **`INTTRA-ITVGPSUPDATE`**, parses the proto `ITVShipmentStatusChangeEvent`, serializes it to JSON with `JsonFormat`, and writes it to S3 bucket `inttra-int-watermill-gps` as `{offset}.json`. Downstream, a separate `mercury-services` component (`visibility-itv-gps-processor`, out of scope) picks the file up via an S3→SNS→SQS notification pipeline that this module does **not** participate in — itv-gps-consumer makes **no SQS calls and publishes no SNS**.

- **Current state:** DW5 baseline done + **AWS Java SDK v1 (1.12.720)**, consumed via `shared` (`ConfigProcessingServerCommand`, `S3ConfigurationProvider`, `ParameterSupplier`/`ParameterStoreModule`) plus **local, duplicated** DynamoDB v1 plumbing (`dynamodb/DynamoSupport`, `dynamodb/command/DynamoTableCommand`, and consumer-commons' `vo/DateToEpochSecond`/`vo/Expires`) and a **dead** `AmazonSNS` binding.
- **Target:** AWS SDK **v2** via `cloud-sdk-api`/`cloud-sdk-aws` (`StorageClient` for S3, `DatabaseRepository`/`DynamoRepositoryFactory` for the DynamoDB offset, `CloudParameterStore` for the SSM gRPC creds) + `commons` (config command) + slim `appianway-commons` (nothing this module strictly needs beyond the composed config transform — it has no error-handling/health/dispatcher residue worth moving). `shared` dropped entirely.
- **Headline change:** re-platform the single-row DynamoDB offset (`WatermillOffset`, table `inttra_int_watermill_offset`) onto the cloud-sdk-aws v2 enhanced client via a **consolidated `consumer-commons`** (deleting this module's local Dynamo duplicates), rebind the metadata-free S3 write onto `StorageClient`, and rebind the SSM-sourced gRPC credentials onto `CloudParameterStore` — while proving the offset value (verified at **1353** on 2026-07-22) survives the cut exactly.
- **Tenant/topic note (do not rename):** unlike the other three watermill consumers (`INTTRA_INT-...`), this module's gRPC tenant header is **`INTTRA`** (not `INTTRA_INT`) and its topic is **`INTTRA-ITVGPSUPDATE`**. Both are baked into `conf/int/itv-gps-consumer.properties` and MUST be preserved exactly.

---

## 2. Current vs Target architecture

```
BEFORE — AWS v1 + shared
  e2open Watermill gRPC INTTRA-ITVGPSUPDATE (NON-AWS) ─▶ ResponseConsumerObserver
     ─▶ S3PublishService ─▶ AmazonS3 v1
     ─▶ AuthCredentials ─▶ shared ParameterSupplier/ParameterStoreModule ─▶ AWSSimpleSystemsManagement v1
     ─▶ WatermillOffsetDao (extends DynamoDBCrudRepository) ─▶ local DynamoSupport + consumer-commons DynamoSupport ─▶ AmazonDynamoDB v1 + DynamoDBMapper
  dead: AmazonSNS binding (never invoked)

AFTER — cloud-sdk v2 + commons
  same gRPC topic (NON-AWS, unchanged) ─▶ ResponseConsumerObserver (unchanged)
     ─▶ S3PublishService (consumer-commons) ─▶ StorageClient (cloud-sdk-api)
     ─▶ AuthCredentials ─▶ CloudParameterStore (cloud-sdk-api)
     ─▶ WatermillOffsetDao adapter (consumer-commons, consolidated) ─▶ DatabaseRepository / DynamoRepositoryFactory (cloud-sdk-aws)
```

### 2.1 Class-level mapping

| Current (`shared` / AWS v1) | Replacement | Home | Notes |
|---|---|---|---|
| `shared.command.ConfigProcessingServerCommand` | `commons ConfigProcessingServerCommand` + composed appianway property-substitution transform | commons + appianway-commons | §5.3 |
| `shared.config.S3ConfigurationProvider` | keep appianway-local (unchanged behaviour) — only when `CONFIG_LOCATION=s3` | appianway-commons or module | not exercised on the INT boot |
| `shared.parameterstore.ParameterSupplier` / `ParameterStoreModule` | `cloud-sdk-api CloudParameterStore` | cloud-sdk | `AuthCredentials` resolves `userIdKey`/`passwordKey` through it — §3, §5.2 |
| `AmazonS3`/`AmazonS3ClientBuilder` bound in `ExternalServicesModule` | `cloud-sdk-api StorageClient` | cloud-sdk | `S3PublishService.uploadToS3` becomes `storageClient.putObject(bucket, key, bytes)` — metadata-free, **S-G2 not exercised** |
| `AmazonSNS`/`AmazonSNSClientBuilder` (dead binding) | — | **delete** | confirmed never injected/invoked anywhere |
| `AmazonDynamoDB`/`AmazonDynamoDBClientBuilder`, `DynamoDBMapper`/`DynamoDBMapperConfig` (local `dynamodb/DynamoSupport` **and** the duplicate in `consumer-commons`) | `DynamoDbClientConfig` + `DynamoRepositoryFactory.createEnhancedRepository(...)` | cloud-sdk-aws | **delete this module's local `dynamodb/DynamoSupport` entirely** — consolidate onto the migrated `consumer-commons` |
| `WatermillOffsetDao extends DynamoDBCrudRepository[WatermillOffset,...]` (`consumer-commons`) | thin adapter over `DatabaseRepository[WatermillOffset,String]` (`findOne`/`save`/`update` preserved) | consumer-commons | `WatermillOffsetService`/`OffsetUtil`/`OffsetUpdateScheduler` call sites **unchanged** |
| `vo.WatermillOffset` — `@DynamoDBTable("watermill_offset")` + `@DynamoDBHashKey("topicName")` + `@DynamoDBAttribute offset/readDateTime/writeDateTime` + `@DynamoDBTypeConverted(DateToEpochSecond)` + `@DynamoDBStream(KEYS_ONLY)` | `@Table("watermill_offset")` + `@DynamoDbPartitionKey @DynamoDbField("topicName")` + `@DynamoDbField(...)` + `LongEpochSecondAttributeConverter` | consumer-commons | **attribute names + epoch-seconds encoding preserved exactly** — highest-risk item, §10 |
| local `dynamodb/command/DynamoTableCommand` (`TableUtils.createTableIfNotExists` + `SSESpecification` + 10/10 `ProvisionedThroughput`) | `DynamoDbAdminCommand`/`DynamoDbAdminUtil` (cloud-sdk-aws) | cloud-sdk-aws | preserve SSE flag + RCU/WCU; consolidate, do not keep a second copy |
| `vo/DateToEpochSecond` (consumer-commons `DynamoDBTypeConverter[Long,Date]`) | `LongEpochSecondAttributeConverter` (cloud-sdk-api) | cloud-sdk-api | **delete** the local duplicate; assert identical epoch-seconds output |
| `vo/Expires` (`EXPIRES_ON_ATTRIBUTE_NAME`/TTL interface) | `@TTL` (cloud-sdk-api) **if** any entity persists `expiresOn` (it does not appear used by `WatermillOffset`) | cloud-sdk-api / delete | confirm unused before deleting (§10) |
| gRPC layer: `ResponseConsumerObserver`, `ConsumerInitUtil`, `WatermillConsumerTask`, `AsyncDispatcher`, `AuthCredentials` header-injection, `MAX_RETRY_LIMIT=100` | **unchanged** — not AWS | module | out of scope |

---

## 3. AWS touchpoints

| Touchpoint | Direction | INT resource | cloud-sdk client | Notes |
|---|---|---|---|---|
| SQS | — | none | — | sends/receives no SQS messages |
| SNS | — | none (dead binding removed) | — | `AmazonSNS` was bound but never invoked; **deleted**, not replaced |
| S3 | write only | `inttra-int-watermill-gps`, key `{offset}.json` | `StorageClient.putObject(bucket, key, bytes)` | metadata-free write ⇒ **S-G2 not exercised** |
| DynamoDB | read + write (offset) | table `inttra_int_watermill_offset` (physical = `{dynamoDbConfig.environment}_watermill_offset`, env = `inttra_int`), hash key `topicName` = `INTTRA-ITVGPSUPDATE` | `DatabaseRepository[WatermillOffset,String]` via `DynamoRepositoryFactory` | single row; last-writer-wins (no `@DynamoDbVersionAttribute`); offset verified at **1353** on 2026-07-22 |
| SES | — | none | — | not used |
| Param Store (SSM) | read (resolved at gRPC-call time) | `/inttra/int/appianway/watermill-grpc/se/username`, `.../password` | `CloudParameterStore` | resolved by `AuthCredentials` when the gRPC `CallCredentials.applyRequestMetadata` executes — **not** a boot-time `AuthClient` call (no `networkServiceConfig` block) |
| gRPC | consume (non-AWS) | `watermill.staging.e2open.com:443`, tenant `INTTRA`, topic `INTTRA-ITVGPSUPDATE` | — | untouched; Netty gRPC channel via `ConsumerInitUtil` |
| Port / health | — | `8085` | — | **no health checks registered**; `/admin/opsHealthcheck` → 404; boot-evidence only |

---

## 4. Sequences

### 4.1 Steady-state consume → parse → S3 write → in-memory offset advance

```
  gRPC (topic INTTRA-ITVGPSUPDATE, tenant INTTRA) ─▶ ResponseConsumerObserver.onNext(RawData @ offset k)   [NON-AWS, unchanged]
     ITVShipmentStatusChangeEvent.parseFrom(rawData.getData())
     JsonFormat.printer().print(event) ─▶ jsonPayload
     S3PublishService.getFullS3Path("{k}.json") ; uploadToS3(bucket, path, jsonPayload) ─▶ StorageClient.putObject("inttra-int-watermill-gps", "{yyyyMMdd}/{k}.json", bytes)   [metadata-free, S-G2 not exercised]
     OffsetUtil.updateOffset(k)   [in-memory only; not yet persisted]
```

### 4.2 Startup offset seed + periodic DynamoDB flush (offset-store v2 rebind)

```
  WatermillConsumerModule ─▶ WatermillOffsetService.getOffset("INTTRA-ITVGPSUPDATE")
     ─▶ WatermillOffsetDao.findOne(hashKey=topic) ─▶ DatabaseRepository.findById(topic) ─▶ GetItem(PK=topicName)
        present ─▶ offset=N (e.g. 1353) ─▶ startOffset = N+1 (1354)
        absent  ─▶ initializeOffset(topic, -1L) ─▶ save(WatermillOffset{topic,-1L}) ─▶ PutItem ; startOffset = 0
  OffsetUpdateScheduler (every offsetUpdateDelay=15 min):
     WatermillOffsetService.updateOffset(topic, OffsetUtil.getOffset()) ─▶ DatabaseRepository.save ─▶ PutItem (last-writer-wins, no version attribute)
```

### 4.3 Create-table admin command (`create-table` CLI verb)

```
  DynamoTableCommand (consolidated onto cloud-sdk-aws) ─▶ DynamoDbAdminUtil.ensureTable("inttra_int_watermill_offset", WatermillOffset.class, RCU=10, WCU=10, sse=config)
     ─▶ CreateTable if absent (PK topicName, SSE per config, KEYS_ONLY stream) ─▶ wait until ACTIVE
```

**At-least-once preserved:** the in-memory cursor (`OffsetUtil`) advances per message; `OffsetUpdateScheduler` flushes to DynamoDB on a fixed cadence and on graceful `stop()`. A crash between flushes resumes the gRPC stream at `persisted_offset + 1` — identical before and after the v2 rebind.

---

## 5. Configuration changes

### 5.1 Property-key table — exact INT values

| Property key | INT value | Consumed by (yaml path) | Changes? |
|---|---|---|---|
| `componentName` | `itv-gps-consumer` | (metrics/logging tag) | no |
| `watermill-grpc.consumer.username.key` | `/inttra/int/appianway/watermill-grpc/se/username` | `watermillServiceConfig.userIdKey` | **no** — SSM path unchanged; resolution moves to `CloudParameterStore` (§5.2) |
| `watermill-grpc.consumer.password.key` | `/inttra/int/appianway/watermill-grpc/se/password` | `watermillServiceConfig.passwordKey` | no |
| `watermill-grpc.consumer.tenant` | `INTTRA` | `watermillServiceConfig.tenant` | **no — do NOT rename to `INTTRA_INT`**; this module is the one exception among the 4 consumers |
| `watermill-grpc.consumer.host` | `watermill.staging.e2open.com` | `watermillServiceConfig.host` | no |
| `watermill-grpc.consumer.port` | `443` | `watermillServiceConfig.port` | no |
| `watermill-grpc.consumer.topic.name` | `INTTRA-ITVGPSUPDATE` | `watermillServiceConfig.topicName` | **no — exact topic string, also the DynamoDB hash-key value** |
| `watermill-grpc.dynamo.environment` | `inttra_int` | `dynamoDbConfig.environment` | no — physical table prefix stays `inttra_int_watermill_offset` |
| `watermill-grpc.consumer.s3WorkspaceConfig.bucket` | `inttra-int-watermill-gps` | `s3WorkspaceConfig.bucket` | no |
| `watermill-grpc.consumer.offsetUpdateDelay` | `15` (minutes) | `watermillServiceConfig.offsetUpdateDelay` | no |
| `watermill-grpc.consumer.keepAliveTime.seconds`/`keepAliveTimeout.seconds`/`idleTimeout.minutes` | `30`/`20`/`30` | `watermillServiceConfig.*` | no (non-AWS gRPC tuning) |
| `server.connector.port` | default `8085` | `server.connector.port` | no — **port 8085**, not 8081 like the other 13 appianway apps |
| `watermill-grpc.consumer.healthCheckConfig.errorRateThreshold` | default `5.0` | `healthCheckConfig.errorRateThreshold` | **dead config** — no `registerHealthChecks()` is ever called; `HealthCheckConfig` populated but unused |
| `networkservices.healthCheckUrl` | from `network-services.properties` | `healthCheckConfig.networkServiceHealthCheckUrl` | config-resolved only, never probed |

> `watermillServiceConfig.subscriptionTopicName`/`eventTopicName` exist on the shared `WatermillServiceConfig` POJO (for the multi-topic visibility-inbound consumer) but are **not set** here — itv-gps-consumer has exactly one topic.

### 5.2 SSM parameter table — resolution mechanism

| SSM parameter | Purpose | Today | After |
|---|---|---|---|
| `/inttra/int/appianway/watermill-grpc/se/username` | gRPC call-credential username header | shared `ParameterSupplier.getValue(key)` (v1 `AWSSimpleSystemsManagementClientBuilder.defaultClient()`), fetched **once at Guice-provision time** in `AuthCredentials`'s constructor | `CloudParameterStore.getParameter(key)`, same call site (`AuthCredentials` constructor) — **keep runtime resolution, do not move to boot-time `${awsps:...}`** because it's constructed per-connection via Guice, not templated into the YAML |
| `/inttra/int/appianway/watermill-grpc/se/password` | gRPC call-credential password header | same | same |

No `usePassThrough` toggle in this module (a `networkservices.*` concept — itv-gps-consumer's yaml has no `networkServiceConfig` block). No boot-time `${awsps:/path}` substitution needed — this module passes the **SSM path itself** as a config value and resolves it lazily per gRPC call via `CloudParameterStore`, preserving today's behaviour.

### 5.3 Config-command composition

- CLI **unchanged**: `run itv-gps-consumer.yaml conf/int/itv-gps-consumer.properties ../../configuration/int/network-services.properties ../../configuration/int/datadog.properties` (**`../../configuration`** — two levels up, because `watermill/itv-gps-consumer/` sits one directory deeper).
- Composed transform chain, via `commons ConfigProcessingServerCommand` in `WatermillGpsConsumerApplication.initialize(bootstrap)`: appianway property-substitution transform (`${key}` from `.properties` + env, appianway-commons) → commons `TrimConfigCommentsTransform` → commons `ParameterStoreConfigTransform` (`${awsps:/path}` at boot) — **not exercised by this module's own keys**, composed anyway for consistency.
- `bootstrap.addCommand(new DynamoTableCommand(this))` stays registered as the `create-table` verb, now backed by `DynamoDbAdminUtil` internally instead of `TableUtils`.
- `S3ConfigurationProvider.requiresS3Configuration()` conditional stays as-is (only when `CONFIG_LOCATION=s3`, not exercised on local/INT).

### 5.4 What is unchanged

- CLI arg shape, `-DCONFIG_REGION=US_EAST_1`, `datadog.properties` passthrough.
- **Port 8085** (not 8081) — `server.connector.port:-8085` default.
- **No health checks registered** — Dropwizard's "no healthchecks" banner is expected; `/admin/opsHealthcheck` → 404. Verification is by **boot evidence**.
- Queue/topic/bucket/SSM-path names — **none renamed**.
- Tenant `INTTRA` and topic `INTTRA-ITVGPSUPDATE` — the two values that make this consumer diverge from its 3 siblings; preserved exactly.

---

## 6. cloud-sdk / commons dependencies & assumed gaps

| Gap ID | Exercised? | Detail |
|---|---|---|
| **S-G2** (metadata/content-type `putObject` overloads) | **No** | `S3PublishService.uploadToS3` calls the plain `putObject(bucket,key,bytes)` overload — no `ObjectMetadata`/content-type set, so the pre-S-G2 signature is sufficient. |
| **W-G9** (workflow-model parity) | **No** | never constructs or parses a `MetaData`/`Event`/`Annotations` object — no SQS/SNS traffic at all. |
| **X-G7 / X-G8** | No | not an email/ES concern |
| **C-G6** | Optional, not required | composition works without it |
| DynamoDB v2 enhanced client (native, not a "gap") | **Yes — the module's headline change** | `DatabaseRepository[WatermillOffset,String]` + `DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminUtil`/`DynamoDbAdminCommand` — all **existing** cloud-sdk-aws surface, no library change needed. |

**Consumes from `commons`:** `ConfigProcessingServerCommand` (already the base since DW5; the config-transform composition changes per §5.3), nothing from `networkservices.*`, no `health.*` base.
**Consumes from `cloud-sdk-api`/`cloud-sdk-aws`:** `StorageClient`, `CloudParameterStore`, `DatabaseRepository`/`DynamoRepositoryFactory`/`@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`/`LongEpochSecondAttributeConverter`/`DynamoDbClientConfig`/`DynamoDbAdminUtil`.
**Moves to `appianway-commons`:** essentially nothing module-specific — this consumer has no `AsyncDispatcher`/`ErrorHandler`/health-indicator residue worth relocating (its local `task/AsyncDispatcher` is a 1-shot gRPC-stream submitter, kept local, non-AWS). The only appianway-commons dependency is the composed config transform.

**No cloud-sdk/commons change is required for this module** — it is a pure client of existing surface.

---

## 7. Maven dependency changes

`itv-gps-consumer/pom.xml` has `<parent>com.inttra.mercury:watermill:1.0</parent>` (the **watermill aggregator**, packaging `pom`) — **not** the appianway root. The `watermill` aggregator has **no parent**, so all BOM/version pins are mirrored directly in `watermill/pom.xml` (already true for the Jetty/Jackson/httpcore pins from ION-16098).

**`watermill/pom.xml` — add to `<properties>`/`<dependencyManagement>`:** `mercury.commons.version=1.0.27-SNAPSHOT`; `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `${mercury.commons.version}`), `appianway-commons:1.0-SNAPSHOT` (listed after the existing jetty-bom/jetty-ee10-bom/jackson-bom/httpcore pins). `io.dropwizard.version` stays 5.0.2. Retire the `mercury.shared.version` property once shared usage is fully removed.

**`itv-gps-consumer/pom.xml` — remove:** transitive `com.amazonaws:aws-java-sdk-dynamodb` / `-s3` / `-ssm` (via `consumer-commons` and the retired `shared`); the **dead** transitive `aws-java-sdk-sqs`; the in-house `dynamo-client` dependency (once `WatermillOffsetDao` no longer extends `DynamoDBCrudRepository`); `com.inttra.mercury:shared` (comes in transitively via `consumer-commons`; drops once that migrates).

**`itv-gps-consumer/pom.xml` — add:** `consumer-commons` (already a direct dependency, version `1.0` — its internals migrate in place); `cloud-sdk-api`, `cloud-sdk-aws`, `commons`, `appianway-commons` (versions managed by `watermill/pom.xml`); `dynamo-integration-test` (test scope). AWS SDK **v2** (`dynamodb-enhanced`, `s3`, `ssm`, `apache-client`, Netty excluded) comes **transitively** via `cloud-sdk-aws` — do not declare v1 or v2 AWS artifacts directly.

**Unchanged (module-specific, non-AWS):** `io.grpc:*` `1.77.0` and the `e2open.watermill.proto` codegen (`protobuf-maven-plugin 0.6.1`, `protoc 4.33.1`, `protoc-gen-grpc-java 1.77.0`); `maven-shade-plugin` fat-jar (main class `com.inttra.watermill.gps.consumer.WatermillGpsConsumerApplication`); `os-maven-plugin`; Lombok, slf4j-api, jackson-datatype-jsr310, assertj-core.

**Tests:** module is on **JUnit 4** (`junit:junit:4.13.2` + `surefire-junit47`) — add `junit-vintage-engine` so existing `@RunWith(MockitoJUnitRunner)` tests keep running on the JUnit 5 platform; write new Dynamo-offset tests in Jupiter against `dynamo-integration-test` (DynamoDB-Local).

**Verify:** `mvn -pl watermill/itv-gps-consumer -am clean verify` (aggregator-relative `-am` pulls in `consumer-commons`) then a full `mvn -f watermill/pom.xml clean verify`; boot the fat jar against INT and confirm the same log evidence (DynamoDB "Offset found" line + gRPC "Initializing ResponseObserver" line), since there is no `/admin/opsHealthcheck` to hit.

---

## 8. Tests

- **Offset persistence (critical path):** move `WatermillOffsetServiceTest`/`WatermillOffsetDaoTest` (currently in `consumer-commons`, duplicated locally as `DynamoSupportTest`/`OffsetUtilTest`) onto `dynamo-integration-test` (DynamoDB-Local). Assert: write→read round-trip; **exact attribute names** `topicName`/`offset`/`readDateTime`/`writeDateTime` stored (not renamed by the `@DynamoDbField` re-annotation); epoch-seconds numeric value unchanged; `findById(absent)` → empty → `initializeOffset(topic, -1L)` path exercised.
- **Backward-compat fixture (gate, do not skip):** seed DynamoDB-Local with a snapshot shaped exactly like the real `inttra_int_watermill_offset` row for key `INTTRA-ITVGPSUPDATE` (offset **1353**, per the 2026-07-22 INT verification) and assert the migrated entity deserializes it and resumes at `1354` — the single highest-value regression test for this module (§10).
- **Converter parity:** assert `LongEpochSecondAttributeConverter` produces the identical stored `Long` as the deleted `DateToEpochSecond` for a fixed `Date`.
- **S3 write:** re-point `S3PublishServiceTest` to a `StorageClient` fake; assert `putObject("inttra-int-watermill-gps", "{yyyyMMdd}/{offset}.json", bytes)` with the exact bucket and date-prefixed key shape; no metadata/content-type asserted (S-G2 not used).
- **gRPC creds:** `AuthCredentials` test re-pointed to a `CloudParameterStore` fake; assert the same two SSM paths are queried and the resulting `username`/`password`/`tenant`/`topic` gRPC metadata headers are unchanged (tenant literal `INTTRA`, topic literal `INTTRA-ITVGPSUPDATE`).
- **Create-table:** `DynamoTableCommandTest` → assert the consolidated `DynamoDbAdminUtil` path creates `inttra_int_watermill_offset` with the configured SSE flag and 10/10 RCU/WCU, plus the `KEYS_ONLY` stream spec.
- **gRPC consumer / reconnect (`MAX_RETRY_LIMIT=100`), `ResponseConsumerObserverTest`, `WatermillConsumerModuleTest`:** unchanged, non-AWS — keep green as a regression guard that the Guice wiring didn't break.
- **JUnit 4→5 bridge:** add `junit-vintage-engine`; migrate opportunistically, no hard deadline.

---

## 9. Rollout & verification

Per the program order, this module is migrated in the **last wave** — after `appianway-commons`, the functional-testing fakes, the 9 core modules, `watermill-publisher`, and (within the 4 watermill consumers) alongside its 3 siblings:

1. Land `cloud-sdk-api`/`cloud-sdk-aws`/`commons` `1.0.27-SNAPSHOT` consumption program-wide.
2. **Pilot the Dynamo offset remap in `consumer-commons`** first (shared by all 4 consumers) — `mvn -pl watermill/consumer-commons -am verify` against `dynamo-integration-test`, including the backward-compat fixture (§8).
3. **Delete this module's local Dynamo duplicates**: `dynamodb/DynamoSupport`, `dynamodb/command/DynamoTableCommand`, and confirm `vo/DateToEpochSecond`/`vo/Expires` are consumer-commons-owned rather than re-duplicated here; repoint `DynamoTableCommand` registration to the consolidated command.
4. Rebind **S3** (`StorageClient`) and **SSM** (`CloudParameterStore`) in `ExternalServicesModule`/`AuthCredentials`; delete the dead `AmazonSNS` binding; drop the unused `aws-java-sdk-sqs` transitive.
5. Compose the config-command transform chain (§5.3); add `junit-vintage-engine`.
6. `mvn -pl watermill/itv-gps-consumer -am verify`; then `mvn -f watermill/pom.xml clean verify` (full aggregator, all 5 modules).
7. **INT boot evidence gate** (no ops health check exists): run from `watermill/itv-gps-consumer/`, confirm the log shows `DynamoSupport : Created mapper with environment prefix 'inttra_int_'` (or the cloud-sdk-aws equivalent init line), `WatermillOffsetService`/repository "Offset found for topic INTTRA-ITVGPSUPDATE . Offset 1353" (or whatever the live value is at cutover time), gRPC `ResponseConsumerObserver : Initializing ResponseObserver`, and zero exceptions; confirm bound port **8085**.
8. **Cutover gate:** the backward-compat offset fixture (§8) passing against a real snapshot of `inttra_int_watermill_offset`, **and** a manual confirmation that a test message still lands as `{offset}.json` in `inttra-int-watermill-gps` (or at minimum that the S3 `StorageClient` fake-backed unit test passes) — this is the contract `visibility-itv-gps-processor`'s S3→SNS→SQS pickup depends on.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Offset-table data-shape incompatibility** — wrong physical table name (`inttra_int_watermill_offset`) or a renamed attribute ⇒ the real ITV offset (verified **1353**) is lost → silent re-consumption from 0, replaying the entire GPS feed downstream | **Highest priority for this module.** Preserve the explicit physical `tableName` and exact `@DynamoDbField` attribute names (`topicName`/`offset`/`readDateTime`/`writeDateTime`); verify with the real-item `dynamo-integration-test` fixture (§8) **before** any INT cutover; re-confirm the offset value via boot-log evidence immediately after cutover. |
| **S3 key/bucket drift breaks the downstream visibility pickup** — `visibility-itv-gps-processor`'s S3→SNS→SQS notification depends on the exact bucket + key shape | Keep bucket `inttra-int-watermill-gps` and key pattern `{yyyyMMdd}/{offset}.json` byte-for-byte; do not introduce metadata/content-type (S-G2 is not needed and must not be silently added). |
| **Tenant/topic literal drift** — this is the one consumer using `INTTRA` (not `INTTRA_INT`) and a hyphenated topic (`INTTRA-ITVGPSUPDATE`) | Do not "normalize" these to match the other 3 consumers; they are the DynamoDB hash-key value and the gRPC metadata header value simultaneously — a rename desyncs the offset row from the live topic. |
| Removing the dead `AmazonSNS` binding / unused `aws-java-sdk-sqs` | Confirmed never invoked (no injection point, no call site); safe to delete — add a compile-time check that no code references `AmazonSNS` post-removal. |
| `vo/Expires` TTL semantics apparently unused | `WatermillOffset` does not implement `Expires` or reference `expiresOn`; confirm via search before deleting; if genuinely unused, delete rather than mapping to `@TTL`. |
| Enhanced-client default extensions (optimistic locking, auto-generated timestamps) silently altering writes | `WatermillOffset` has no `@DynamoDbVersionAttribute` and is not annotated for it post-migration either (last-writer-wins is intentional) — assert plain, unconditional `PutItem` in tests. |
| SSE / throughput / `KEYS_ONLY` stream spec dropped on table create | Carry all three through `DynamoDbAdminUtil`; assert in `DynamoTableCommandTest`. |
| Local `dynamodb/DynamoSupport` duplication silently diverging from `consumer-commons`' copy before this migration lands | Delete the local copy in the same change that lands the consolidated `consumer-commons` version — do not leave both live even briefly. |
| No `/admin/opsHealthcheck` to catch a mis-wired cloud-sdk client at deploy time | Rely on the explicit boot-log evidence checklist (§9 step 7) every deploy — the same gap exists today and is unchanged by this program. |
| SSM path change accidentally rides along with the `CloudParameterStore` rebind | The two paths are **data**, passed through config, not hardcoded in the client rebind — confirm the composed config transform still emits them unchanged into `WatermillServiceConfig`. |
