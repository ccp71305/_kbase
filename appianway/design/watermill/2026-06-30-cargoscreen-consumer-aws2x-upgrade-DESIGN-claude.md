# `cargoscreen-consumer` — AWS SDK v2 (cloud-sdk) Upgrade DESIGN (claude)

> Module: `com.inttra.mercury:cargoscreen-consumer` (sub-module of `watermill`) · Date: 2026-06-30 · Author: Claude (Opus 4.8)
> **Chosen option: B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws` (`1.0.26-SNAPSHOT`) on Dropwizard 5**, consuming cloud-sdk as a normal client with **zero module-specific cloud-sdk changes** (all S3 writes are metadata-free ⇒ **S-G2 not required**).
> Companion plan: [`2026-06-30-cargoscreen-consumer-aws2x-upgrade-plan-claude.md`](2026-06-30-cargoscreen-consumer-aws2x-upgrade-plan-claude.md).
> MASTERs: [shared DESIGN](../../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6 · [watermill DESIGN](../../docs/2026-05-31-watermill-aws2x-upgrade-DESIGN-claude.md) (offset-store remap + `consumer-commons` consolidation).

---

## 1. Overview & chosen option

`cargoscreen-consumer` is an **S3-only sink** consumer for 3rd-party cargo security-screening results. It subscribes to a single e2open Watermill gRPC cargoscreen topic, parses proto `CargoScreeningOutboundChangeEvent`, and for each non-error upsert writes the `CargoScreeningOutbound` JSON to **S3** as `{YYYYMMdd}/{offset}_{sourceSourceTxId}.json`; error results are **logged only** (no downstream queue). It **does not send to SQS and does not publish SNS**.

Its AWS surface is **S3 (write, metadata-free) + DynamoDB (single consumption offset) + SSM (gRPC credentials)**. The gRPC/Watermill layer (`ResponseConsumerObserver`, `ConsumerInitUtil`, the ION-14324 reconnect logic with 20 s channel-stabilization) is **not AWS** and is untouched.

**Governing rule (master plan §0):** consume cloud-sdk as a client; **no cloud-sdk/commons change.** cargoscreen satisfies it cleanly:

- **DynamoDB offset** → re-annotate the offset entity to cloud-sdk-api `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, replace the v1 `DynamoDBMapper` path with `DatabaseRepository<WatermillOffset,String>` via `DynamoRepositoryFactory`, and **consolidate this module's fully-local Dynamo layer** (`DynamoSupport`, `DynamoTableCommand`, **its own `vo/WatermillOffset`**, `vo/DateToEpochSecond`) onto the migrated `consumer-commons` (watermill DESIGN §1–§2, §9).
- **S3 write** → `S3PublishService` over cloud-sdk-api `StorageClient.putObject(bucket,key,bytes)` — metadata-free, **S-G2 not used**.
- **SSM gRPC credentials** (`AuthCredentials`) → `shared` `ParameterStore` over `CloudParameterStore`.
- **Dead AWS bindings** → the Guice-bound but never-invoked `AmazonSNS` and the declared-but-unused `aws-java-sdk-sqs` are removed.
- **Dropwizard 4→5** → move the application onto `commons` `InttraServer` with the composed appianway config command (master §5).

> Of the five consumers, cargoscreen has the **most local DynamoDB duplication** — it carries its *own* `vo/WatermillOffset` entity (not just a local `DynamoSupport`), so the consolidation onto `consumer-commons` is the largest cleanup win here.

---

## 2. Class diagram (target offset persistence)

```mermaid
classDiagram
    class ResponseConsumerObserver { <<StreamObserver~RawData~; parses CargoScreeningOutboundChangeEvent; NON-AWS>> }
    class S3PublishService { <<consumer-commons, over StorageClient>> }
    class WatermillOffsetService { <<consumer-commons, retained>> }
    class WatermillOffsetDao { <<consumer-commons, adapter over DatabaseRepository>> }
    class OffsetUtil { <<consumer-commons, in-memory>> }
    class AuthCredentials { <<gRPC creds from CloudParameterStore>> }

    class WatermillOffset { <<entity: @Table/@DynamoDbPartitionKey/@DynamoDbField (consolidated)>> }
    class DatabaseRepository~T,ID~ { <<cloud-sdk-api>> +findById(ID) +save(T) }
    class DynamoRepositoryFactory { <<cloud-sdk-aws>> +createEnhancedRepository(...) }
    class StorageClient { <<cloud-sdk-api>> +putObject(bucket,key,bytes) }
    class CloudParameterStore { <<cloud-sdk-api>> }
    class LongEpochSecondAttributeConverter { <<cloud-sdk-api>> }

    ResponseConsumerObserver --> S3PublishService
    ResponseConsumerObserver --> OffsetUtil --> WatermillOffsetService
    WatermillOffsetService --> WatermillOffsetDao --> DatabaseRepository
    DatabaseRepository <.. DynamoRepositoryFactory : builds (default extensions)
    S3PublishService --> StorageClient
    AuthCredentials --> CloudParameterStore
    WatermillOffset ..> LongEpochSecondAttributeConverter
```

**Removed v1 types:** `AmazonS3`/`AmazonS3ClientBuilder`, `AmazonDynamoDB`/`AmazonDynamoDBClientBuilder`, `DynamoDBMapper`/`DynamoDBMapperConfig`, **local** `@DynamoDBTable/@DynamoDBHashKey/@DynamoDBAttribute/@DynamoDBTypeConverted` on the module's own `WatermillOffset`, `DynamoDBTypeConverter`(`DateToEpochSecond`), `TableUtils`/`CreateTableRequest`/`SSESpecification`, `AwsClientBuilder.EndpointConfiguration`, `AWSSimpleSystemsManagement`, `DefaultAWSCredentialsProviderChain`, **dead** `AmazonSNS`/`AmazonSNSClientBuilder`.
**Consumed cloud-sdk:** `StorageClient`, `CloudParameterStore`, `DatabaseRepository<WatermillOffset,String>`, `DynamoRepositoryFactory`, `@Table`/`@DynamoDbPartitionKey`/`@DynamoDbField`, `LongEpochSecondAttributeConverter`, `DynamoDbClientConfig`, `DynamoDbAdminUtil`/`DynamoDbAdminCommand`.

---

## 3. Component diagram

```mermaid
flowchart LR
    subgraph e2o[e2open Watermill gRPC  NON-AWS]
      T[(cargoscreen outbound topic)]
    end
    subgraph svc[cargoscreen-consumer]
      OBS[ResponseConsumerObserver]
      OU[OffsetUtil + OffsetUpdateScheduler]
      AC[AuthCredentials]
    end
    subgraph cc[consumer-commons consolidated]
      Svc[WatermillOffsetService]
      Dao[WatermillOffsetDao adapter]
      S3P[S3PublishService]
    end
    subgraph cs[cloud-sdk 1.0.26-SNAPSHOT]
      Repo[DatabaseRepository / DynamoRepositoryFactory]
      Store[StorageClient]
      CPS[CloudParameterStore]
    end
    DDB[(DynamoDB watermill_offset)]
    S3[(S3 workspace)]

    T --> OBS
    OBS -->|exStatus != ERROR| S3P --> Store --> S3
    OBS -->|exStatus == ERROR| LOG[log only]
    OBS --> OU --> Svc --> Dao --> Repo --> DDB
    AC --> CPS
    CPS -. gRPC credentials .-> OBS
```

The spine is **gRPC stream → (success → write JSON to S3 / error → log) → commit offset to DynamoDB**, with SSM-sourced gRPC credentials on the side. No SQS, no SNS.

---

## 4. Sequence diagrams

### 4.1 Steady state — consume → (S3 or log) → advance offset
```mermaid
sequenceDiagram
    participant G as gRPC stream (cargoscreen)
    participant O as ResponseConsumerObserver
    participant S3P as S3PublishService
    participant SC as StorageClient (cloud-sdk)
    participant OU as OffsetUtil (in-memory)
    G-->>O: RawData @ offset k (CargoScreeningOutboundChangeEvent)
    loop each upsert
        alt exStatus != ERROR
            O->>S3P: uploadToS3(bucket, "{offset}_{txId}.json", json)
            S3P->>SC: putObject(bucket, key, bytes)  %% metadata-free
        else exStatus == ERROR
            O->>O: log BPResult messages (terminal)
        end
    end
    O->>OU: updateOffset(k)
```

### 4.2 Startup seed + periodic offset flush
```mermaid
sequenceDiagram
    participant M as WatermillConsumerModule
    participant Svc as WatermillOffsetService
    participant Dao as WatermillOffsetDao
    participant R as DatabaseRepository (cloud-sdk)
    participant DDB as DynamoDB {env}_watermill_offset
    participant Sched as OffsetUpdateScheduler
    M->>Svc: getOffset(topicName)
    Svc->>Dao: findOne(topicName)
    Dao->>R: findById(topicName)
    R->>DDB: GetItem(PK topicName)
    alt present
        R-->>M: offset=N => startOffset = N+1
    else absent
        M->>Svc: initializeOffset(topic, -1L) => save() => startOffset = 0
    end
    Note over Sched: every offsetUpdateDelay (minutes)
    Sched->>Svc: updateOffset(topic, OU.getOffset())
    Svc->>R: save(WatermillOffset{topic,k})  %% last-writer-wins
```

### 4.3 Reconnect (ION-14324; non-AWS, AWS offset write only on flush)
```mermaid
sequenceDiagram
    participant O as ResponseConsumerObserver
    participant Svc as WatermillOffsetService
    participant DDB as DynamoDB
    Note over O: onError
    O->>Svc: persist current offset
    Svc->>DDB: save(...)  %% via DatabaseRepository
    O->>O: channel.shutdownNow(); awaitTermination(20s)
    O->>O: new channel; sleep 20s stabilization; consumeForever(persisted+1)
```

**At-least-once preserved:** the cursor advances in-memory per message and flushes on the scheduler; on restart the stream resumes at `persisted+1`. The 20 s channel stabilization (ION-14324) is a gRPC concern and is unchanged.

---

## 5. Configuration (ref master DESIGN §5)

- **Single topic / single offset row:** the configured cargoscreen topic; one `WatermillOffset` row keyed by topic name.
- **Physical table name preserved:** `"{dynamoDbConfig.environment}_watermill_offset"` passed explicitly to `DynamoRepositoryFactory.createEnhancedRepository(...)`.
- **DynamoDB endpoint/region:** v1 `AwsClientBuilder.EndpointConfiguration` → `DynamoDbClientConfig.endpointOverride(regionEndpoint)` + `Region.of(signingRegion)`. SSE/throughput (10/10 RCU/WCU today) via `DynamoDbAdminUtil`.
- **S3 bucket:** `s3WorkspaceConfig.bucket`; metadata-free `StorageClient.putObject`; key `{YYYYMMdd}/{offset}_{sourceSourceTxId}.json` preserved.
- **gRPC credentials:** `watermillServiceConfig.userIdKey`/`passwordKey` from `ParameterStore` → `CloudParameterStore`. gRPC `maxRetry`/`retryDelay` and the 20 s stabilization (ION-14324) are non-AWS and unchanged.
- **Config loading:** v1 `S3ConfigurationProvider` + `ConfigProcessingServerCommand`. **Option B:** register the composed appianway `ServerCommand` (master §5/§10.3) on the `InttraServer` bootstrap. Config keys unchanged.

---

## 6. cloud-sdk gaps — **NONE (full mapping below)**

| v1 element | cloud-sdk replacement | Notes |
|---|---|---|
| `S3PublishService.uploadToS3` → `s3.putObject(bucket,key,String)`, result ignored | `StorageClient.putObject(bucket,key,bytes)` | **metadata-free ⇒ S-G2 NOT required** |
| **local** `@DynamoDBTable("watermill_offset")` + `@DynamoDBHashKey("topicName")` + `@DynamoDBAttribute offset/readDateTime/writeDateTime` + `@DynamoDBTypeConverted(DateToEpochSecond)` | `@Table("watermill_offset")` + `@DynamoDbPartitionKey @DynamoDbField("topicName")` + `@DynamoDbField(...)` + `LongEpochSecondAttributeConverter` | **attribute names + epoch-seconds preserved; consolidate onto `consumer-commons` entity** |
| local `DynamoSupport` (`DynamoDBMapper`/config/`AmazonDynamoDBClientBuilder`) | `DynamoDbClientConfig` + `DynamoRepositoryFactory` | **delete local duplicate** |
| local `DynamoTableCommand` (`TableUtils`+SSE+10/10 throughput) | `DynamoDbAdminCommand`/`DynamoDbAdminUtil` | preserve SSE + RCU/WCU |
| local `vo/DateToEpochSecond` | `LongEpochSecondAttributeConverter` | duplicate — delete |
| `AWSSimpleSystemsManagement` (`ParameterStore`) | `CloudParameterStore` (via shared) | gRPC `AuthCredentials` source |
| `AwsClientBuilder.EndpointConfiguration` | `DynamoDbClientConfig` endpoint override | DynamoDB-Local / regional |
| **dead** `AmazonSNS` binding + unused `aws-java-sdk-sqs` dep | — | **remove** (never invoked) |
| `DefaultAWSCredentialsProviderChain` | v2 `DefaultCredentialsProvider`/`DefaultAwsRegionProviderChain` | env/IAM unchanged |

`@DynamoDbVersionAttribute` available but **unused**. **S-G2 not used.** No module-specific cloud-sdk change required.

---

## 7. Maven dependency changes (pin `1.0.26-SNAPSHOT`)

`watermill` aggregator `dependencyManagement` + this module's `pom.xml`:
```xml
<properties><mercury.commons.version>1.0.26-SNAPSHOT</mercury.commons.version></properties>
<dependency><groupId>com.inttra.mercury</groupId><artifactId>cloud-sdk-api</artifactId><version>${mercury.commons.version}</version></dependency>
<dependency><groupId>com.inttra.mercury</groupId><artifactId>cloud-sdk-aws</artifactId><version>${mercury.commons.version}</version></dependency>
<!-- Option B -->
<dependency><groupId>com.inttra.mercury</groupId><artifactId>commons</artifactId><version>${mercury.commons.version}</version></dependency>
<dependency><groupId>com.inttra.mercury</groupId><artifactId>dynamo-integration-test</artifactId><version>${mercury.commons.version}</version><scope>test</scope></dependency>
```
**Remove:** `com.amazonaws:aws-java-sdk-{dynamodb,sqs,s3,ssm}` (direct in pom / transitive via `shared`); the **dead** SNS binding and the **declared-but-unused** `aws-java-sdk-sqs`; the in-house `dynamo-client` once local `DynamoSupport`/`DynamoDBCrudRepository` usage is gone; drop `<aws-java-sdk.version>`. `cloud-sdk-aws` transitively brings `software.amazon.awssdk:{dynamodb-enhanced,s3,ssm,apache-client}` with **Netty excluded**.
**Tests:** module is on **JUnit 4** (`junit:junit:4.13.2`, `@RunWith(MockitoJUnitRunner)`) — add `junit-vintage-engine` during transition; write new offset tests in Jupiter.
**gRPC/proto:** `io.grpc:*` `1.77.0` + the `e2open.watermill.proto` cargoscreen deps are **unchanged** (non-AWS).

---

## 8. Test details

- **Offset persistence:** move `WatermillOffsetServiceTest` to `dynamo-integration-test` (DynamoDB-Local). Assert write→read round-trip; attribute names `topicName`/`offset`/`readDateTime`/`writeDateTime` stored exactly; epoch-seconds value; `findById(absent)` → empty → `initializeOffset`.
- **Backward-compat fixture (critical):** seed DynamoDB-Local with a real-shaped `{env}_watermill_offset` item for the cargoscreen topic key; assert the **consolidated** entity deserializes it and `+1` resume works.
- **Converter:** assert `LongEpochSecondAttributeConverter` matches the old `DateToEpochSecond` stored `Long`.
- **S3 write:** re-point `S3PublishService` to a `StorageClient` fake; assert `putObject(bucket,"{offset}_{txId}.json",bytes)`; assert the **error path logs and does not write/queue**.
- **Create-table:** `DynamoTableCommandTest` → assert `DynamoDbAdminUtil` creates `{env}_watermill_offset` with SSE + 10/10 throughput.
- **gRPC consumer / reconnect (ION-14324, 20 s stabilization):** unchanged (non-AWS) — keep green.
- **JUnit 4→5:** existing tests run via `junit-vintage-engine`; migrate opportunistically.

---

## 9. Rollout & verification

1. Land cloud-sdk `1.0.26-SNAPSHOT` consumption (no cloud-sdk change required).
2. **Pilot the Dynamo offset path in `consumer-commons`** → `mvn -pl watermill/consumer-commons -am verify` with `dynamo-integration-test`.
3. **Delete this module's local Dynamo layer** (`dynamodb/DynamoSupport`, `dynamodb/command/DynamoTableCommand`, **`vo/WatermillOffset`**, `vo/DateToEpochSecond`); repoint to the migrated `consumer-commons` + `DynamoDbAdminUtil`.
4. After `shared` migrates, rebind **S3 (`StorageClient`)** and **SSM (`CloudParameterStore`)**; remove the dead SNS binding and unused SQS dep.
5. Move the application onto `commons` `InttraServer`/DW5 with the composed config command; add `junit-vintage-engine`.
6. `mvn -pl watermill/cargoscreen-consumer -am verify`; then aggregator `mvn verify`.
7. **Gate cutover** on the backward-compat offset fixture passing against a snapshot of the real cargoscreen `{env}_watermill_offset` item.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Offset-table data-shape incompatibility** — wrong physical table name or renamed attribute ⇒ cargoscreen offset lost → silent re-consumption from 0 | **Highest priority.** Preserve `{env}_watermill_offset` (explicit `tableName`) + exact attribute names; epoch-seconds via `LongEpochSecondAttributeConverter`; verify with a real-item `dynamo-integration-test` fixture before cutover. |
| **Local `WatermillOffset` consolidation regressions** — cargoscreen has its OWN entity copy; merging onto `consumer-commons` must keep the identical table/attribute mapping | Diff the local vs `consumer-commons` entity field-by-field before deletion; assert byte-identical attribute names in the round-trip fixture. |
| Removing the dead SNS binding / unused SQS dep | Confirmed never invoked; safe to delete — assert no runtime wiring references them. |
| Enhanced-client default extensions alter writes | Confirmed inert; assert plain put. |
| SSE / throughput / stream spec dropped on create | Carry through `DynamoDbAdminUtil`; assert in `DynamoTableCommandTest`. |
| **JUnit 4 → 5 platform move** | Add `junit-vintage-engine`; migrate opportunistically. |
| Reconnect parity (20 s stabilization, ION-14324) | gRPC concern — keep unchanged; verify reconnect tests still pass post-DW5. |
| DW4→5 (Option B) | Sequence Dynamo remap first; framework move after `shared`; per-module verify gate. |
| Region/endpoint resolution drift | Map `regionEndpoint`/`signingRegion` to `DynamoDbClientConfig`; dev-run parity check. |
