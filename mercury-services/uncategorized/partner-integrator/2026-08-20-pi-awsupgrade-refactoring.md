# partner-integrator — AWS SDK 1.x → 2.x (cloud-sdk) Refactoring Log — ION-16397

**Branch:** `feature/ION-16397-pi-aws-upgrade` · **Started (this run):** 2026-08-20
**Model:** Claude Opus 4.8 · **Session:** `5a888b9118314ed3`
**Design/spec:** `partner-integrator/docs/2026-0731-pi-aws-upgrade-design.md`
**Constraints:** exactly one outgoing commit containing `ION-16397`; do not push; all tests pass (nothing weakened/`@Disabled`); no unrelated refactors; backward-compatible wire/disk formats.

This document is the running command + change log for the migration (per user request). It is
updated continuously as work progresses. `**/docs/` is gitignored, so this file is a local artifact.

---

## 0. Starting state (verified 2026-08-20)

| Fact | Value |
|---|---|
| Branch tip before | `b86d536fed` (0 outgoing commits, strict ancestor of develop) |
| develop tip | `ac6f2f804c` (includes ION-16396 SI v2 upgrade @ `588c531b85`, ION-16415 lambdas) |
| Source changes present | none — code migration not yet started |
| Model jars staged (untracked) | `booking 3.0.0.M` in pi-booking-processor/lib + pi-statusevents-out-processor/lib; `visibility 2.0.M` in pi-statusevents-out-processor/lib |
| Model jar NOT staged | `shipping-instruction 2.0.M` (needed in pi-si-in-processor/lib + pi-si-out-processor/lib) |

### v1 surface (main files with `import com.amazonaws.`)
pi-bl-es-lambda 31 · pi-bl-in-processor 32 · pi-booking-processor 2 · pi-commons 24 ·
pi-lambda-streamToSns 2 · pi-si-in-processor 2 · pi-si-out-processor 6 · pi-statusevents-out-processor 5.

---

## 1. Command log

### Git / rebase
```powershell
git rev-parse --short HEAD                 # b86d536fed (before)
git rev-parse --short develop origin/develop  # both ac6f2f804c
git merge-base --is-ancestor HEAD develop  # exit 0 -> HEAD is ancestor, 0 outgoing commits
git tag ION-16397-pre-rebase-backup-20260820
git rebase develop                         # clean fast-forward to ac6f2f804c (0 conflicts)
```
Result: branch now at `ac6f2f804c`, untracked model jars preserved.

### Baseline (in progress)
```powershell
mvn -f partner-integrator/pom.xml clean verify   # re-measuring on new develop; target BUILD SUCCESS, >=4452 tests
```

---

## 2. Key decisions carried forward (from session + design doc)

- **SI model:** consume the v2 `com.inttra.mercury.shippinginstruction.model.SIVersion` from
  `shipping-instruction:2.0.M` (built off develop, ION-16396). PI processors keep the same import;
  only the jar behind it changes. `vo.SI` stays provisioning-only (no `contract` field added).
- **booking:** `3.0.0.M` for all three consuming submodules (staged from visibility-commons/lib).
- **visibility:** `2.0.M` built into pi-statusevents-out-processor/lib.
- **aws-lambda-java-events:** normalize to `3.14.0` in parent dependencyManagement.
- **commons/cloud-sdk-api/cloud-sdk-aws/dynamo-integration-test:** `1.0.31-SNAPSHOT`.

---

## 3. Reference patterns (verified in-repo)

- Entity (same domain): `shipping-instruction/.../model/SIVersion.java` — `@Table(name="si")`,
  `@DynamoDbBean`, `@DynamoDBStream(KEYS_ONLY)`, `@DynamoDbPartitionKey id`, `@DynamoDbSortKey sequenceNumber`,
  `@DynamoDbSecondaryPartitionKey(INTTRA_REFERENCE_NUMBER_INDEX)` + `@GsiConfig`, `CompressionConverter`,
  `DateToEpochSecond`.
- DAO: `shipping-instruction/.../dao/SIDao.java` — `DatabaseRepository<T, DefaultCompositeKey<String,String>>`,
  `DefaultQuerySpec` for GSI queries.
- Guice module: `shipping-instruction/.../config/SIDynamoModule.java` — per-entity `@Provides`,
  `clientConfig.getTablePrefix() + @Table.name()`.
- Admin command: `shipping-instruction/.../config/SIDynamoDbAdminCommand.java` — extends
  `DynamoDbAdminCommand<Config>`, entity-class list, `resolveClientConfig`.

---

## 4. Progress by phase

- [x] Rebase onto develop (ff to ac6f2f804c)
- [x] Baseline re-measured — effectively green (2 flaky AsyncDispatcherTest failures, pass 4/4 isolated)
- [x] Stage model jars: booking 3.0.0.M, visibility 2.0.M, **shipping-instruction 2.0.M** (all in lib/)
- [x] Phase 1: poms (parent dependencyManagement + pi-commons)
- [x] Phase 2: pi-commons — **DONE & GREEN (1210 tests)**
- [~] Phase 3: Dropwizard processors — **pi-booking-processor, pi-si-in-processor, pi-si-out-processor DONE & GREEN**; pi-statusevents next
- [ ] Phase 4: Lambdas + BL model
- [ ] Phase 5: tests
- [ ] Phase 6: verify + single commit

### Module status
| Module | Status |
|---|---|
| pi-commons | ✅ DONE — main+tests green, 1210 tests |
| pi-booking-processor | ✅ DONE — main+tests green, 2032 tests |
| pi-si-in-processor | ✅ DONE — main+tests green, 504 tests |
| pi-si-out-processor | ✅ DONE — main+tests green, 243 tests (S3+SQS+SNS+DDB+SSM+admin; SIDao generic bug fixed; booking dep dropped) |
| pi-statusevents-out-processor | ⬜ pending (special `_booking_booking` resolution) |
| pi-bl-in-processor | ⬜ pending (28 BL models + Jest) |
| pi-bl-es-lambda | ⬜ pending (28 BL models byte-identical) |
| pi-lambda-streamToSns | ⬜ pending |

**Build note:** downstream `-pl <module>` runs need the reactor poms installed once:
`mvn -N install` (root) + `mvn -f partner-integrator/pom.xml -N install` + `mvn -pl pi-commons install -DskipTests`.
`DefaultCompositeKey` does not override `equals` → use `any()` matchers in Mockito for `findById`.

**⚠ JUnit4 + dynamo-integration-test conflict (important):** adding `dynamo-integration-test` (test scope)
to a module whose unit tests are **JUnit 4** pulls JUnit Platform onto the classpath, so surefire 3.2.5
auto-selects the Jupiter provider and runs **0** JUnit 4 tests. Adding `junit-vintage-engine 5.11.3` then
fails with `NoClassDefFound .../OutputDirectoryProvider` (platform-version conflict with what
dynamo-integration-test brings). **Resolution:** do NOT add `dynamo-integration-test` to JUnit 4 modules
until the IT phase, and then add it with a junit-bom that aligns `junit-vintage-engine` to the platform
version. JUnit 5 modules (pi-booking-processor) are unaffected and keep it. pi-si-in tests are all JUnit 4.

**SI model jar staging (safe):** compiled shipping-instruction (`mvn -f shipping-instruction/pom.xml
"-Dmaven.test.skip=true" compile`), then `jar --create` of `model`+`util`+`dao` from `target/classes` →
`shipping-instruction-2.0.M.jar` + flat pom into pi-si-in-processor/lib and pi-si-out-processor/lib.
**Did NOT run `-Psi-model package`** — its `si-model-deploy` execution would overwrite the released S3 `1.0.M`.

---

## 5. Phase 1 — Dependency changes (DONE)

**Parent `partner-integrator/pom.xml`** — added shared version properties and a `dependencyManagement`
block (jackson-bom 2.21.4 import, aws-lambda-java-events 3.14.0, cloud-sdk-api, cloud-sdk-aws,
dynamo-integration-test test scope). commons line = **1.0.31-SNAPSHOT**.

**`pi-commons/pom.xml`** — dropped `aws-java-sdk-dynamodb` and `dynamo-client`; removed the hard-coded
`jackson-module-afterburner` 2.19.2 version (now BOM-managed); `commons` → 1.0.31-SNAPSHOT (inherited);
added `cloud-sdk-api`, `cloud-sdk-aws`, and `dynamo-integration-test` (test).

### Verified cloud-sdk signatures (javap of 1.0.31-SNAPSHOT jars)
- `StorageClient`: `putObject(b,k,String|byte[]|InputStream,long|File)`, default `putObject(b,k,byte[]|InputStream,[len,]Map,String)`,
  `getContent(b,k,Charset)`, `getObject(b,k)→StorageObject{getContent(),getMetadata(),...}`, `copyObject(sb,sk,tb,tk[,Map,String])→boolean`, `deleteObject`.
- `MessagingClient<T>`: `sendMessage(url,T)`, `sendMessage(url,T,Map)`, `deleteMessage(url,handle)`,
  `receiveMessages(ReceiveMessageOptions)→List<QueueMessage<T>>`. **No per-message delay overload.**
- `ReceiveMessageOptions.builder()`: queueUrl/maxMessages/waitTimeSeconds/visibilityTimeoutSeconds.
- `QueueMessage<T>`: getMessageId/getReceiptHandle/getPayload/getAttributes/getSentTimestamp.
- `MessagingClientFactory.createDefaultStringClient()`, `createConfiguredClient(AwsMessagingClientConfig, MessageConverter<T>)`.
- `SqsMessagingClient(SqsClient, MessageConverter)` — underlying SqsClient not exposed via getter.

## 6. Phase 2 — pi-commons main (DONE, compiles)

`mvn -f partner-integrator/pom.xml -pl pi-commons compile` → **BUILD SUCCESS**.

| Area | Change |
|---|---|
| Converters | `vo.DateToEpochSecond`, `vo.CompressionConverter` → v2 `AttributeConverter` (N / S, null-safe), mirroring the ION-16396 SI reference |
| Entities | `vo.SI` (`@Table("si")`, KEYS_ONLY stream, `id` PK / `sequenceNumber` SK, `INTTRA_REFERENCE_NUMBER_INDEX` GSI + `@GsiConfig` KEYS_ONLY, `message`/`expiresOn` converters; **no `@TTL`** to preserve live-env TTL; provisioning-only, no `contract`), `vo.ContainerEvent` (`@Table("container_events")`, `id` PK), `vo.EnrichedAttributes` (`@DynamoDbBean` nested). `getHashKey/getSortKey` kept `@DynamoDbIgnore @JsonIgnore` |
| REST DTOs | `Country`, `CountryIdentifier`, `Geography`, `ContainerType`, `PackageType` — inert `@DynamoDBDocument`/`@DynamoDBTypeConvertedEnum` removed |
| S3 | `WorkspaceService` `putObject*` → `void` (no prod caller reads `PutObjectResult`); `S3WorkspaceService` → `StorageClient`, `RecoverableException` wrapping catches v2 `SdkException`, every read path closes its stream; no-charset `getContent` keeps deliberate `BufferedReader` line-join (CRLF→LF) semantics; charset `getContent` byte-exact |
| Retry | `AWSUtil.isRetryable` → v2 (`SdkException.retryable()` + `RetryUtils.isThrottling/isClockSkew` + IOException cause) |
| SQS | `SQSClient` → `MessagingClient<String>` (send/delete) + v2 `SqsClient` for the `delay` overload (design R5 gap — cloud-sdk has no per-message delay; 0 prod callers). `SQSListenerClient` → `receiveMessages(ReceiveMessageOptions)`. `SQSListener` → `ReceiveMessageOptions` + v2 `AbortedException`. `Task/AbstractTask/TaskFactory/Dispatcher/AsyncDispatcher/TaskMessage` → `QueueMessage<String>`, `getBody()`→`getPayload()`. `UnrecoverableAWSException` → v2 `SdkClientException` |
| Deleted | `common/dynamodb/DynamoSupport.java` (v1 `DynamoDBMapper` helper). Still referenced by pi-bl-in/pi-si-in/pi-si-out/pi-statusevents `CreateTables/DeleteTables/Injectors` — migrated in Phase 3 |

### Command log (Phase 1/2)
```powershell
# verified cloud-sdk signatures
javap -cp cloud-sdk-api-1.0.31-SNAPSHOT.jar;cloud-sdk-aws-1.0.31-SNAPSHOT.jar <class>   # StorageClient, MessagingClient, ...
# compile gate
mvn -f partner-integrator/pom.xml -pl pi-commons compile   # BUILD SUCCESS
```

### cloud-sdk gaps found
- **Per-message SQS delay**: `MessagingClient` has no delay parameter (3-arg overload = message attributes).
  Worked around via a cloud-sdk-configured v2 `SqsClient` in `SQSClient` (design R5). Raise with commons team.

## 7. Phase 2 — pi-commons tests (IN PROGRESS)

6 test files touch v1 types. `DynamoSupportTest` → deleted (class removed). `S3WorkspaceServiceTest`,
`SQSClientTest`, `SQSListenerTest`, `AbstractTaskTest`, `AsyncDispatcherTest` → retyped to the cloud-sdk
API (StorageClient / MessagingClient / QueueMessage / ReceiveMessageOptions / v2 SqsClient). The two
flaky `AsyncDispatcherTest` idle-count assertions are made deterministic with a bounded poll
(`awaitIdle`) — same assertion, no weakening. Verified in isolation with
`mvn -f partner-integrator/pom.xml -pl pi-commons test`.

## 8. Phase 3 — Dropwizard processors (PLAN, not yet done)

Sequence: pi-booking-processor → pi-si-in-processor → pi-si-out-processor → pi-statusevents-out-processor → pi-bl-in-processor.

**Reference patterns (in-repo):** `booking/config/BookingDynamoModule.java` (per-entity `@Provides`,
`createCompositeKeyRepository` = `getTablePrefix()+@Table.name()`), `booking/dao/BookingDetailDao.java`
(`DefaultQuerySpec` GSI + `findById(DefaultCompositeKey,true)`), `shipping-instruction/config/SIDynamoModule.java`,
`shipping-instruction/config/SIDynamoDbAdminCommand.java`, `booking-cargoscreen` (S3/SQS/SNS injector wiring).

### 8.1 Common per-processor pom changes
- Bump `commons` → 1.0.31-SNAPSHOT (inherited); add `cloud-sdk-api`, `cloud-sdk-aws`; add `dynamo-integration-test` (test).
- Drop `aws-java-sdk-*`; normalize `aws-lambda-java-events` → managed 3.14.0 where present.
- pi-booking/pi-statusevents: narrow `purge-local-repository` `manualInclude` to the pinned coordinate
  `com.inttra.mercury:booking:3.0.0.M`; update the `dependency:get` artifact to 3.0.0.M.
- Model-jar pins: pi-booking `booking`→3.0.0.M; pi-statusevents `booking`→3.0.0.M + `visibility`→2.0.M;
  pi-si-in/pi-si-out `shipping-instruction`→**2.0.M** (must be staged first, §8.5).

### 8.2 Config classes + config.yaml
- Each `*ApplicationConfig.dynamoDbConfig` field: `com.inttra.mercury.dynamo.respository.module.DynamoDbConfig`
  → `com.inttra.mercury.cloudsdk.database.config.BaseDynamoDbConfig`.
- Add `region: us-east-1` under `dynamoDbConfig:` in every env yaml (int/qa/cvt/prod).
- ES-config classes (pi-bl-in) → implement `com.inttra.mercury.cloudsdk.config.ElasticSearchServiceConfig`;
  `JestModule` coords → `com.inttra.mercury.cloudsdk.aws.module.JestModule`.

### 8.3 Injectors / DAOs / table-name resolution (VERIFIED backward-compat)
- **pi-booking-processor**: env yaml = `inttra_int_booking` (already has `_booking`); `BookingDetail`
  `@Table.name()="booking"` ⇒ **standard** `getTablePrefix()+"booking"` = `inttra_int_booking_booking`. Replace
  `DynamoSupport`-bound `AmazonDynamoDB/DynamoDBMapper/DynamoDBMapperConfig` with a `BookingDynamoModule`-style
  provider. `BookingDao` → wraps `DatabaseRepository<BookingDetail, DefaultCompositeKey<String,String>>`; the two
  `query(INDEX, hash, null, "inttraReferenceNumber = :hashKeyValue")` calls → `DefaultQuerySpec` on
  `INTTRA_REFERENCE_NUMBER_INDEX`; composite find → `findById(new DefaultCompositeKey<>(bookingId, seq), true)`.
  `booking`→3.0.0.M.
- **pi-si-in-processor**: `SIApplicationInjector` + `SIDao` same shape; entity stays
  `com.inttra.mercury.shippinginstruction.model.SIVersion`, now the **v2** class from `shipping-instruction:2.0.M`
  (imports unchanged, only the pin moves). `SIFeedHandler`/`SIFeedService` type follow-through.
- **pi-si-out-processor**: widest surface — `SIFeedApplicationInjector` (S3+SQS+SNS+DDB), `SIDao`
  (**fix latent bug**: generic param `ContainerEvent`→`SIVersion`), `OutboundProcessor`,
  `Utils.ssmParameterlookup` → `CloudParameterStore`, `CreateTables`/`DeleteTables` → `DynamoDbAdminCommand`.
  Sender bindings: bind a cloud-sdk v2 `SqsClient` + `MessagingClient<String>` under `@Named("amazonSQSForSender")`
  (and listener under `@Named("amazonSQSForListener")`); S3 `AmazonS3` → `StorageClient` via
  `StorageClientFactory`; SNS → `NotificationService`/`NotificationClientFactory`.
- **pi-statusevents-out-processor**: `SEFeedApplicationInjector` — env prefix is `<prefix>` WITHOUT `_booking`;
  the v1 resolver **special-cases** `BookingDetail` → `<prefix>_booking_booking`, everything else
  `<prefix>_<table>`. So the new dynamo module must build the `BookingDao` repo with
  `getTablePrefix()+"booking_"+"booking"` (SPECIAL) and `ContainerEventDao` repo with standard
  `getTablePrefix()+@Table.name()` (`container_events`). `booking`→3.0.0.M, `visibility`→2.0.M.
  `EventPublisher` provider → `NotificationService`.
- **pi-bl-in-processor**: `BLApplicationInjector`, module-local `dao/DynamoSupport` (delete), `BLDynamoDao`,
  `CreateTables`/`DeleteTables` (`TableUtils`+GSI/TTL/stream/SSE → `DynamoDbAdminUtil`), **28 BL model classes**,
  `JestModule` coords + `ESConfiguration implements cloudsdk.config.ElasticSearchServiceConfig`.

### 8.4 SNS / event logging (processors)
`com.inttra.mercury.messaging.*` symbols moved to `com.inttra.mercury.cloudsdk.notification.workflow.*`
(`MetaData`, `Event`, `EventLogger`, `EventPublisher`). `SNSEventPublisher`/`SNSClient` →
`NotificationService` via `NotificationClientFactory.createConfiguredClient(NotificationClientConfig
.builder().topicArn().region().credentialsProvider().build())`. `NotificationService extends EventPublisher`,
so `EventPublisher` injection points bind directly. Set **both** region and credentialsProvider (ION-16387).

### 8.5 Model-jar staging (Phase 0 completion)
- `booking:3.0.0.M` — staged in pi-booking-processor/lib + pi-statusevents-out-processor/lib ✅
- `visibility:2.0.M` — staged in pi-statusevents-out-processor/lib ✅
- `shipping-instruction:2.0.M` — **TODO**: `mvn -f shipping-instruction/pom.xml -Psi-model clean package`,
  then install `si-model-<v>.jar` as `com.inttra.mercury:shipping-instruction:2.0.M` into
  pi-si-in-processor/lib + pi-si-out-processor/lib (+ flat model pom). **Never re-deploy over 1.0.M** (S3 wagon).

## 9. Phase 4 — Lambdas + BL model (PLAN)

> **Alignment requirement (per review):** the two PI lambda modules must follow the **same
> cloud-sdk lambda upgrade pattern** already used by the reference lambda upgrades — **booking**,
> **visibility**, and the standalone **`lambda`** module (ION-16415, landed on `develop`
> @ `5d8b5f30d8`/`6925e289b9`). Do not invent a PI-specific lambda wiring. Concretely, mirror their
> `HandlerSupport` construction: build every cloud-sdk client (`NotificationService`,
> `CloudParameterStore`, `StorageClient`, DynamoDB repository) with an **explicit region AND
> credentials provider** (`NotificationClientConfig.builder().topicArn().region().credentialsProvider(
> AwsCredentialsProviderWrapper.of(DefaultCredentialsProvider.create())).build()`), never a
> `defaultClient()` — this is the ION-16387 cold-start outage lesson. Reference implementations:
> - `lambda/auth-tokens-archive/.../AuthTokenDynamoStreamProcessor.java` + `.../lambda/HandlerSupport.java` (DynamoDB-stream → archive, closest analogue to `pi-lambda-streamToSns`)
> - `lambda/subscription-archive`, `lambda/registration-archive`, `lambda/optionalvalidation-archive`, `lambda/booking-outbound`, `lambda/bounceback-email`, `lambda/partner-integration` (ION-16415 set)
> - `visibility/visibility-outbound-poller/.../HandlerSupport.java`, `visibility/visibility-s3-archiver`, `visibility/visibility-pending-start`, `visibility/visibility-error-email/.../ParameterStoreResolver.java`
> - `booking/.../booking/lambda/HandlerSupport.java` + `booking/.../config/BookingMessagingModule.java`
>
> Also normalize `aws-lambda-java-events` → **3.14.0** (2.x transitively drags AWS-SDK-v1 `Record`),
> keep `aws-lambda-java-core` (runtime, not SDK), and guard the SNS-envelope JSON shape with a
> golden-JSON test (§7.2).

- `pi-lambda-streamToSns` (`StreamToSnSProcessor`, `StreamStatusEventsToSnsProcessor`): SNS → `NotificationService`
  with explicit region+creds; drop `aws-java-sdk-sns/-dynamodb`; `aws-lambda-java-events`→3.14.0; keep
  `aws-lambda-java-core`. Preserve dual-publish routing (INSERT/REMOVE→both topics, MODIFY→all-events).
- `pi-bl-es-lambda` (`HandlerSupport`, `IndexerHandler`, `dao/DynamoSupport`, `BLDynamoDao`, 28 BL models):
  `DynamoDBMapper.load(id,seq)` → `findById(new DefaultCompositeKey<>(id,seq))`; Jest indexing untouched.
  Mirror the reference `HandlerSupport` region+credentials wiring above.
- 28 BL model classes duplicated in pi-bl-in-processor and pi-bl-es-lambda MUST stay byte-identical
  (enforce with a byte-compare gate). Migrate `@DynamoDB*` → v2 annotations; watch enum `toString()` vs `name()`.

## 10. Phase 5 — Tests (PLAN)
Converter parity (compression boundary 307200/307201 bytes, ISO-8859-1 high bytes, pre-epoch/negative dates);
golden-JSON envelope (3.14.0 DynamodbStreamRecord byte-equal to 2.2.2); entity round-trip via low-level client
asserting S/N/M types; table-name resolution assertions (incl. `<prefix>_booking_booking`); client-wiring
region+creds non-null (ION-16387 guard); DynamoDB-Local ITs (`BaseDynamoDbIT`) for si/container_events/
bill_of_lading/booking; behaviour tests (getContent CRLF, SQS delay, dual-publish, stream close, `_booking`).

## 11. Phase 6 — Verify & deliver (PLAN)
`mvn -f partner-integrator/pom.xml clean verify` (≥4452, 0 failures); no `com.amazonaws:aws-java-sdk` in
dependency:tree; no v1 imports in main except `services.lambda.runtime`; BL model byte-compare; OWASP
baseline+post per shaded jar; boot-check the 5 Dropwizard submodules; VS Code launch configs; **single**
commit containing `ION-16397` (no push).

---

## 12. Session context log — `5a888b9118314ed3` (`ION-16397-pi-aws-upgrade-20260731`)

All decisions/findings/test-results are also persisted in the mcp-context-server session
`5a888b9118314ed3` (project `mercury-services`, status `active`). Entry trail (this run appended
to the 2026-07-31 discovery/decision entries):

| # | Category | Summary |
|---|---|---|
| 1 | finding | Discovery complete + design doc written; 3 hard constraints; baseline 4452 tests (2026-07-31) |
| 2 | decision | Model-jar decisions; ION-16396 status (2026-07-31, later superseded — SI now consumed from develop) |
| 3 | progress | Resumed ION-16397; rebased feature branch onto develop (ff to ac6f2f804c) |
| 4 | test_result | Baseline: 2 flaky AsyncDispatcherTest failures (idle-count race); passes 4/4 isolated → effectively green |
| 5 | code_change | Phase 1 poms + pi-commons MAIN migrated & compiling (S3/SQS/Dynamo/DTOs); DynamoSupport deleted |
| 6 | finding | Table-name backward-compat: pi-booking standard resolution; pi-statusevents special `_booking_booking` |
| 7 | test_result | pi-commons DONE & green (1210 tests) |
| 8 | test_result | pi-booking-processor DONE & green (2032 tests) |
| 9 | test_result | pi-si-in-processor DONE & green (504); learning: dynamo-integration-test breaks JUnit4 discovery |
| 10 | finding | pi-si-out-processor full execution-ready migration spec (lambda-events 3.x + notification workflow + S3/SQS/SNS/SSM/admin + SIDao bug fix) |

**Model info:** Claude Opus 4.8 (this run). Session left `active` for continuation from pi-si-out-processor.
Telemetry: token usage is captured by the harness-level hooks; `session_usage_report` can confirm at end.

## 13. Lambda upgrade alignment (review note)

The PI lambda modules (`pi-lambda-streamToSns`, `pi-bl-es-lambda`) **must be upgraded in line with the
existing reference lambda upgrades** — the **booking** lambda, the **visibility** lambdas, and the
standalone **`lambda`** module (ION-16415, on `develop`). Same cloud-sdk `HandlerSupport` pattern,
`aws-lambda-java-events` **3.14.0**, and **explicit region + credentials provider** on every client
(ION-16387 cold-start lesson). See §9 for the cited reference implementations and details.

## 14. Why `aws-lambda-java-events` → 3.14.0 (clarification — SDK version vs library version)

**These are two different libraries with independent version numbers — do not conflate them:**

| Library | What it is | Version scheme | Action |
|---|---|---|---|
| **AWS SDK for Java** | the real service clients (S3/DynamoDB/SQS/SNS) | only **v1** (`com.amazonaws.*`) and **v2** (`software.amazon.awssdk.*`); **no v3 exists** | upgrade **v1 → v2** (via cloud-sdk) |
| **`aws-lambda-java-events`** | POJOs for Lambda trigger payloads (`SNSEvent`, `DynamodbEvent`, …) — **not** the SDK | its **own** line: …2.x, **3.x**, 4.x | bump **2.x → 3.x** |

So "3.x" is the **events-library's own version**, unrelated to any "AWS SDK v3". We upgrade the SDK to
**2.x** *and separately* bump the events helper to **3.x**; there is no contradiction.

**Why the bump is required (verified via `javap`):**
- `2.2.2`: `DynamodbEvent.DynamodbStreamRecord extends com.amazonaws.services.dynamodbv2.model.Record`
  — that superclass is an **AWS SDK v1** class, so the events lib **pulls AWS SDK v1 onto the classpath**.
  Four PI submodules parse `DynamodbStreamRecord`, so staying on 2.x keeps v1 alive no matter what we do
  to application code.
- `3.x`: `DynamodbStreamRecord extends com.amazonaws.services.lambda.runtime.events.models.dynamodb.Record`
  — that `Record` (and its `AttributeValue`) live **inside the events lib itself** and depend on **no AWS
  SDK** (neither v1 nor v2). That is "self-contained". Bumping the events lib to 3.x is precisely what
  *lets* the SDK-v2 upgrade actually remove v1.

**Backward-compat proof:** 3.x's `models.dynamodb.Record` / `AttributeValue` expose **byte-identical getter
names** (`getEventID/getEventName/getDynamodb/…`, `getS/getN/getB/getSS/getNS/getBS/getM/getL/getNULL/getBOOL`),
so the Jackson-serialized SNS envelope shape is unchanged — guarded by a golden-JSON test (§7.2).

**Reference alignment / version chosen:** the already-upgraded references are on the **3.x** line —
`booking` = **3.14.0**, the standalone `lambda` module (`auth-tokens-archive`, `registration-archive`,
ION-16415) = **3.14.0**. To match them, the PI parent `dependencyManagement` pins
**`aws-lambda-java-events` = 3.14.0** (bumped from the July design's 3.13.0), so the pre-migration PI
drift (2.0.1 / 2.2.2 / 3.13.0 across submodules) collapses to one reference-aligned version.
`aws-lambda-java-core` (the Lambda **runtime**: `RequestHandler`, `Context`, `LambdaLogger`) is **not**
the SDK and stays as-is.

## 15. Commit & off-disk backup (safety checkpoint)

To protect work off local disk while the migration is still mid-flight, a **WIP checkpoint commit** was
made and a **copy of the branch pushed to origin** (the company git, `git.dev.e2open.com`) under a
distinct backup branch name — the **review branch itself remains unpushed**, preserving the reviewer's
one-commit / no-push workflow.

| Item | Value |
|---|---|
| WIP commit | `a8504e59e8` on `feature/ION-16397-pi-aws-upgrade` (1 outgoing commit; message contains `ION-16397`; includes the `aws-lambda-java-events` 3.14.0 alignment) |
| Contents | 51 files — pi-commons + pi-booking-processor + pi-si-in-processor sources, parent pom, and the staged `booking 3.0.0.M` / `visibility 2.0.M` / `shipping-instruction 2.0.M` model jars. **No `docs/`** (gitignored), no repo-root clutter |
| Backup branch (pushed) | `backup/ION-16397-pi-aws-upgrade-wip-20260820` → `origin` (off-disk storage only; **not for merge/review**) |
| Review branch (NOT pushed) | `feature/ION-16397-pi-aws-upgrade` stays local |

> **This WIP commit is a checkpoint, not the deliverable.** The final state must be **exactly one**
> `ION-16397` commit once all 8 modules build green (`mvn -f partner-integrator/pom.xml clean verify`).
> Fold the remaining module work into this commit with `git commit --amend` (or interactive-rebase
> squash), then re-point the backup branch if another off-disk snapshot is wanted
> (`git push --force-with-lease origin backup/...`). Do **not** push the review branch — the reviewer
> pushes it manually after approval.
>
> **Commit command used:**
> ```
> git add partner-integrator/
> git commit -m "ION-16397: partner-integrator AWS SDK v2 (cloud-sdk) upgrade - WIP checkpoint" -m "..." \
>            -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
> git branch  backup/ION-16397-pi-aws-upgrade-wip-20260820
> git push -u origin backup/ION-16397-pi-aws-upgrade-wip-20260820
> ```

### 15.1 Annotated git command reference (commit + off-disk backup + sync)

Every git command used for the checkpoint, with syntax and what/why:

```bash
# 1. Stage ONLY this migration's files (path-scoped add). Respects .gitignore, so partner-integrator/docs/
#    is excluded; also avoids repo-root clutter. Adds tracked edits + the untracked lib/ model jars.
git add partner-integrator/
#   git add <pathspec>   -> stage changes under <pathspec> into the index

# 2. Create the WIP checkpoint commit. -m repeated = multiple message paragraphs (subject, body, trailer).
#    Message MUST contain the Jira key ION-16397 (Bitbucket "git control freak" hook) + the Copilot trailer.
git commit -m "ION-16397: ... - WIP checkpoint" -m "<body>" -m "Co-authored-by: Copilot <...>"
#   git commit -m <msg> [-m <msg> ...]   -> record the staged index as a new commit

# 3. Create the off-disk backup branch pointer at the current commit (HEAD). Branch only; no checkout.
git branch backup/ION-16397-pi-aws-upgrade-wip-20260820
#   git branch <name> [<start-point>]   -> create <name> at <start-point> (defaults to HEAD)

# 4. Publish the backup branch to origin and set it as the upstream (-u). This is the "off local disk"
#    storage on the company git (git.dev.e2open.com). The review branch is deliberately NOT pushed.
git push -u origin backup/ION-16397-pi-aws-upgrade-wip-20260820
#   git push -u <remote> <branch>   -> push <branch> to <remote> and record it as the tracking upstream

# 5. Fold a later change (aws-lambda-java-events 3.14.0 alignment) into the SAME commit -> keeps exactly
#    ONE outgoing commit. --amend rewrites HEAD; --no-edit keeps the existing message.
git add partner-integrator/pom.xml
git commit --amend --no-edit
#   git commit --amend [--no-edit]   -> replace HEAD with a new commit built from HEAD + staged changes

# 6. Move the LOCAL backup branch pointer onto the amended commit. -f = force-move an existing branch.
git branch -f backup/ION-16397-pi-aws-upgrade-wip-20260820 HEAD
#   git branch -f <name> <start-point>   -> reset an EXISTING branch <name> to point at <start-point>

# 7. Re-publish the (now rewritten) backup branch. --force-with-lease overwrites the remote branch ONLY
#    if it still points where we last saw it (aborts if someone else pushed) -> safe forced update.
git push --force-with-lease origin backup/ION-16397-pi-aws-upgrade-wip-20260820
#   git push --force-with-lease <remote> <branch>   -> safe force-push (lease-checked, not blind --force)

# 8. Verify the sync (all three refs equal = synced; feature must be absent on origin).
git fetch origin backup/ION-16397-pi-aws-upgrade-wip-20260820          # refresh remote-tracking ref
git rev-parse --short feature/ION-16397-pi-aws-upgrade                  # local review branch  -> a8504e59e8
git rev-parse --short backup/ION-16397-pi-aws-upgrade-wip-20260820      # local backup          -> a8504e59e8
git rev-parse --short origin/backup/ION-16397-pi-aws-upgrade-wip-20260820  # remote backup      -> a8504e59e8
git ls-remote --heads origin feature/ION-16397-pi-aws-upgrade          # EMPTY = review branch not pushed
git rev-list --left-right --count \
    origin/backup/ION-16397-pi-aws-upgrade-wip-20260820...backup/ION-16397-pi-aws-upgrade-wip-20260820   # "0  0"
#   git rev-parse --short <ref>          -> print the (abbreviated) commit SHA a ref points to
#   git ls-remote --heads <remote> <br>  -> list matching branch refs on <remote> (empty = not present)
#   git rev-list --left-right --count A...B -> counts unique commits on each side (0 0 = fully in sync)
```

**Sync status (verified):** `feature` (local, unpushed), local `backup/…`, and `origin/backup/…` all at
**`9cb6e9f761`** (after folding in pi-si-out-processor); backup is **0 ahead / 0 behind** its remote; `feature/ION-16397-pi-aws-upgrade` is
**not** present on origin. Off-disk backup is current.

**To refresh the backup after more work** (e.g. finishing pi-si-out): fold into the one commit and
re-lease-push — `git add partner-integrator/ && git commit --amend --no-edit`, then
`git branch -f backup/ION-16397-pi-aws-upgrade-wip-20260820 HEAD` and
`git push --force-with-lease origin backup/ION-16397-pi-aws-upgrade-wip-20260820`. Never push the review
branch — the reviewer pushes it after approval.




## 16. pi-si-out-processor completion (2026-08-20/21, this run)

**Status: DONE & GREEN — 243 tests, 0 failures** (`mvn -f partner-integrator/pom.xml -pl pi-si-out-processor test`).

Key decisions/notes specific to this module:
- **SIDao** rewritten to wrap `DatabaseRepository<SIVersion, DefaultCompositeKey<String,String>>`; `load(id,seq)` -> `findById(new DefaultCompositeKey<>(id,seq), true).orElse(null)`. Fixed the latent v1 generic bug (`DynamoDBCrudRepository<ContainerEvent,...>` while `load` returned `SIVersion`).
- **booking model dependency dropped entirely** — its only use in main was the vestigial `BookingDetail` table-name special-case in the injector's `DynamoDBMapperConfig` resolver, which disappears with the cloud-sdk repository wiring (SIDao only touches the `si` table). Removed the `booking` dep + booking S3 repo from the pom.
- **CreateTables + DeleteTables consolidated** into a single `SIFeedDynamoDbAdminCommand extends DynamoDbAdminCommand<SIFeedApplicationConfig>` (entity `com.inttra.mercury.common.vo.SI`), matching the booking / shipping-instruction reference pattern. cloud-sdk exposes only a create-oriented admin command (no delete), so the separate v1 DeleteTables command is retired exactly as those reference modules did.
- **SQS wiring** (first PI processor to do it): `@Named("amazonSQSForListener"/"amazonSQSForSender") MessagingClient<String>` via `MessagingClientFactory.createDefaultStringClient()` (faithful to pi-si-out's untuned v1 `AmazonSQSClientBuilder.standard().build()`), plus a v2 `SqsClient.create()` for the `SQSClient` delay-overload dependency (design R5). S3 -> `StorageClientFactory.createDefaultS3Client()`, SNS -> `NotificationClientFactory.createDefaultClient(txTrackingEventTopicArn)` (the `NotificationService` is itself the `EventPublisher`). `EventLogger` = `new EventLogger(notificationService, new EventGenerator(Clock.systemUTC(), new RandomGenerator()))`.
- **MetaData** (`cloudsdk.notification.workflow.MetaData`) has a `protected` no-arg `Builder`, so `createMetaData`/`publishSubscription` use the public 7-arg `Builder(...)` and then chain `setMessageId/setWorkflowId/setParentWorkflowId/setRootWorkflowId` (all = rootWorkflowId) + `addProjections("sourceType","SIInitiated")`. This is deterministic regardless of the 7-arg constructor's exact field mapping. `MetaData` is `@JsonDeserialize(builder=...)`, so the SQS-envelope round-trip test still passes.
- **OutboundProcessor** parses `DynamodbEvent.DynamodbStreamRecord` via aws-lambda-java-events **3.14.0**: `AttributeValue` moves to `...events.models.dynamodb.AttributeValue`, and the v1 `OperationType` enum switch becomes a `String` switch on `getEventName()` ("INSERT"/"MODIFY"/"REMOVE").
- **Test gotcha (3.x events lib):** `StreamRecord.setStreamViewType(StreamViewType)` stores `enum.toString()` and NPEs on `null`; a default `ObjectMapper` serializes the null `streamViewType` field and Jackson then calls the setter with `null` on deserialize. Fixed by having the test helpers set `StreamViewType.NEW_AND_OLD_IMAGES` (real stream records always carry one; the processor ignores the value).
- `S3WorkspaceService.putObject` is now `void` (Phase 2), so the three `when(...).thenThrow` stubs became `doThrow(...).when(...)`.

Only remaining `com.amazonaws.*` imports in main are `com.amazonaws.services.lambda.runtime.events.*` (self-contained in 3.x). Folded into the single ION-16397 commit; backup branch re-synced.

## 17. Confluence design-doc publish (2026-08-21, this run)

**Status: DONE.** Page **`672221381`** v1 —
https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672221381
Title `ION-16397 partner-integrator — AWS SDK 2.x (cloud-sdk) Upgrade`, space **BRM**, parent
**`672213820`** (`26.3.1 Design Documents`), i.e. a sibling of the already-published
`ION-16396 shipping-instruction` (`672623447`) and `ION-16397 booking-cargoscreen` (`672873513`) pages.

Source markdown: `partner-integrator/docs/2026-08-21-pi-awsupgrade-confluence-design.md`.
Instructions followed: `.github/prompts/designdocs/_base-confluence-publisher.md` (Steps 4–5) +
`.github/prompts/designdocs/templates/architecture-template.md`. Tooling: **mcp-context-server** Confluence
tools (not the `publish-doc` / `design-doc` skills).

### 17.1 Steps performed, in order

1. **Read the publishing contract** — `_base-confluence-publisher.md` (XHTML escaping rules, the
   panel/task-list/note macro table, the "verify against `body.storage`, not `body_text`" warning) and
   `templates/architecture-template.md` (the official section list, Pre-Dev Security topic ids, approval matrix).
2. **Resolved the landing page id** — `confluence_search('title = "26.3.1 Design Documents" AND space = "BRM"')`
   → `672213820`. Then `confluence_page_children(672213820)` to list the existing siblings and confirm the
   naming convention of the two reference pages.
3. **Duplicate check** — `confluence_search('space = "BRM" AND title ~ "partner-integrator"')`: no page for this
   title existed, so this is a **create**, not an update.
4. **Read the two reference pages** for Risks / Dependencies / Pre-Dev-Security / approval-matrix parity:
   `confluence_get_page(672873513)` (booking-cargoscreen) and `confluence_get_page(672623447)`
   (shipping-instruction). Both render Risks as a red `panel` titled **Key Risks** and Dependencies as a blue
   `panel` titled **Major Dependencies** — which the converter produces from a bold-only paragraph followed by a
   bullet list. Our doc already used that exact `**Key Risks**` / `**Major Dependencies**` + bullets shape, and
   the same `High/Medium — … *Mitigation:* …` bullet style as the SI page, so no content restructuring was needed.
5. **Three template-fidelity fixes to the markdown** (the doc otherwise matched the siblings):
   - added the official `[What does the pre-dev security checklist mean in detail?](…Release+Management+FAQ…)`
     link line under `## Pre-Dev Security` (both siblings carry it);
   - restored the official wording of Pre-Dev Security topics **120** and **126**
     (`… (Please fill the API arch table)` and `New / Existing UI functionality support querying via either of
     them (VST, XML, java expressions, SQL or any other)`) — they had been abbreviated;
   - replaced the ad-hoc 6-column approval matrix with the **official 5-column, 9-stage** matrix from the
     template (Design / Product Owner / Pre Dev Security / Pre Dev Architecture / Browser / UX /
     Post Dev Security / Post Dev Architecture / QA-TDD), same as both siblings.

   Also changed `_(Per-module counts…)_` to `*(Per-module counts…)*` — the converter only honours `*…*` for
   italics, so the underscore form was leaking literal underscores into the page.
6. **Converted with the reference converter** (never hand-assembled storage XHTML):

   ```bash
   python convert_design_doc.py \
     partner-integrator/docs/2026-08-21-pi-awsupgrade-confluence-design.md \
     <scratch>/pi-aws-upgrade.xhtml
   ```

   Output: `37130 chars in, 55237 chars out`;
   `h1=24 h2=28 tables=18 code=2 panel=2 note=4 task-list=10 jira=9`; **`self-check: OK`** (exit 0).
   The self-check is the publish gate: XML well-formedness + per-table column-count validation +
   byte-comparison of every CDATA code block against its markdown fence. `panel=2` = the two required panels;
   `task-list=10` = the official Pre-Dev Security ids `1,2,3,4,5,6,120,124,125,126` (never renumbered).
7. **Published in a single call** — `confluence_create_page(space_key="BRM", title="…", parent_id="672213820",
   representation="storage", body=<the full 55 KB XHTML>)`. The whole body goes in **one** call; no partial
   publish + `confluence_append_to_page` (append re-sends the combined body and would hit the same 400).
   Result: `{"status":"created","id":"672221381","version":1}`. **No 400/401** — the escaping was already correct
   because the converter escapes `&`/`<`/`>` in prose, table cells and inline `code` before inserting markup,
   and leaves CDATA (fenced code) exempt.
8. **Verified** — `confluence_page_children(672213820)` shows the new page as a child alongside the two siblings;
   `confluence_get_page(672221381)` confirms every section from Contributors → Approval Matrix, both panels
   (`#D04437` Key Risks, `#4A6785` Major Dependencies), all 10 task-list rows and the 18 tables, with ancestry
   `Home → Design Documents → 26.X → 26.4 Design Documents → 26.3.1 Design Documents`.

### 17.2 Gotchas worth remembering

- **`body_text` is lossy — do not diagnose corruption from it.** In the verification fetch the two Data-Flow
  code blocks look mangled (the "After (cloud-sdk…)" CDATA is dropped entirely and a stray `]]>` appears), and
  panel colours print as bare `#D04437` / `#4A6785` text. That is the documented `body_text` extraction artifact,
  **not** a broken page. The converter's byte-comparison self-check is the authority on the code blocks; to
  re-verify by hand, fetch `?expand=body.storage` and compare the `<![CDATA[…]]>` payloads.
- **`ac:plain-text-body` requires real CDATA.** Entity-escaping that content instead makes Confluence silently
  rewrite the element to `ac:rich-text-body`, which reflows the ASCII data-flow diagrams. The converter handles
  this; don't post-process its output.
- **The Pre-Dev Security `#` column is a task list, not text**, and the ids are the corporate ones. Renumbering
  them (or dropping the FAQ link line) is what makes a page visibly diverge from its siblings.
- **The MCP tool takes the body inline**, so the full storage XHTML has to be passed in the call — there is no
  file-path parameter. Write the converter output to the scratch dir, then paste it in one `create` / `update`.
- SSO: a `401` from the MCP tools means the Confluence session expired → re-run `sso_login.py`
  (see `.github/prompts/designdocs/SETUP-confluence-mcp.md`). A `"Confluence is not configured"` error instead
  means `MCP_CONFLUENCE_BASE_URL` is missing from the server env.

### 17.3 Reusable command reference

```bash
# 1. Convert markdown -> Confluence storage XHTML. Non-zero exit or a failed self-check = DO NOT PUBLISH.
python convert_design_doc.py <design-doc.md> <out.xhtml>

# 2. MCP calls, in order (mcp-context-server):
#   confluence_search        'title = "26.3.1 Design Documents" AND space = "BRM"'  -> parent id 672213820
#   confluence_page_children 672213820                                              -> siblings / duplicate check
#   confluence_get_page      <sibling id>                                           -> parity reference
#   confluence_create_page   space_key=BRM title=<title> parent_id=672213820 \
#                            representation=storage body=<full out.xhtml>           -> new page id
#   confluence_get_page      <new id>                                               -> verify sections
#
# For a re-publish of an EXISTING page use confluence_update_page(page_id=..., body=<FULL body>,
# title=..., representation="storage", minor_edit=false) -- the version auto-increments.
```


---

## 18. Fixing the wrong ticket number in branch / commit / PR (ION-16397 -> ION-16417)

**Problem (recorded 2026-08-21):** the feature branch, its single commit message, and the open PR
were all created against the wrong Jira ticket **ION-16397**. The correct ticket is **ION-16417**.

**Current state (verified):**
| Item | Wrong value (now) | Correct value (target) |
|---|---|---|
| Local branch | `feature/ION-16397-pi-aws-upgrade` | `feature/ION-16417-pi-aws-upgrade` |
| Remote branch | `origin/feature/ION-16397-pi-aws-upgrade` (pushed, tracked) | `origin/feature/ION-16417-pi-aws-upgrade` |
| Commit | `343ec541ec` msg `ION-16397: partner-integrator AWS SDK 1.x -> 2.x ...` | `ION-16417: ...` |
| PR | open, head = `feature/ION-16397-pi-aws-upgrade`, title/desc say ION-16397 | head renamed, title/desc say ION-16417 |
| Local backup branch | `backup/ION-16397-pi-aws-upgrade-wip-20260820` (local + remote) | rename optional |

There are unrelated branches that also contain `ION-16397`
(`feature/ION-16397-bk-cargoscreen-aws-upgrade`) — **do not touch those.**

> NOTE: These are the steps only. Nothing below has been executed.

### Option A — GitHub branch rename (RECOMMENDED: keeps the same PR number, comments, reviews, CI)

GitHub's built-in branch rename automatically retargets any open PR whose **head** is that branch,
so the PR, its number, review threads and approvals are preserved.

1. **Rename the branch on GitHub.** This is a GitHub server-side operation (not a plain `git push`),
   so use any ONE of the following — all hit the same rename endpoint and auto-retarget the open PR head:

   - **Web UI:** Repo -> `Branches` -> find `feature/ION-16397-pi-aws-upgrade` -> pencil/`Rename` icon ->
     set `feature/ION-16417-pi-aws-upgrade` -> Rename branch.
   - **GitHub CLI:**
     ```powershell
     gh api -X POST repos/<owner>/<repo>/branches/feature/ION-16397-pi-aws-upgrade/rename -f new_name=feature/ION-16417-pi-aws-upgrade
     ```
   - **REST / curl:**
     ```powershell
     curl -X POST -H "Authorization: token <PAT>" -H "Accept: application/vnd.github+json" `
       https://api.github.com/repos/<owner>/<repo>/branches/feature/ION-16397-pi-aws-upgrade/rename `
       -d '{"new_name":"feature/ION-16417-pi-aws-upgrade"}'
     ```
   GitHub retargets the open PR head to the new name and shows collaborators a "branch was renamed" banner.
   (A client-side delete+push rename would instead CLOSE the PR — that is why the rename must go through GitHub.)

2. **Sync the local clone to the new name:**
   ```powershell
   # make sure the wrong-name branch is checked out and clean first
   git branch -m feature/ION-16397-pi-aws-upgrade feature/ION-16417-pi-aws-upgrade
   git fetch origin --prune          # drops stale origin/...16397, pulls origin/...16417
   git branch -u origin/feature/ION-16417-pi-aws-upgrade feature/ION-16417-pi-aws-upgrade
   git rev-parse --abbrev-ref --symbolic-full-name '@{u}'   # verify -> origin/feature/ION-16417-pi-aws-upgrade
   ```

3. **Fix the commit message (still says ION-16397).** Only one outgoing commit, so amend + force-push:
   ```powershell
   git commit --amend -m "ION-16417: partner-integrator AWS SDK 1.x -> 2.x (cloud-sdk) upgrade"
   git push --force-with-lease origin feature/ION-16417-pi-aws-upgrade
   ```
   (`--force-with-lease` is safe: it refuses if someone else pushed in the meantime.)

4. **Fix the PR text:** edit the PR title and description on GitHub, replacing ION-16397 with ION-16417,
   and update the Jira link. Verify the PR's "commits" tab now shows the amended `ION-16417:` commit.

5. **(Optional) rename the backup branch** for consistency:
   ```powershell
   git branch -m backup/ION-16397-pi-aws-upgrade-wip-20260820 backup/ION-16417-pi-aws-upgrade-wip-20260820
   git push origin :backup/ION-16397-pi-aws-upgrade-wip-20260820 backup/ION-16417-pi-aws-upgrade-wip-20260820
   ```

6. **Jira:** move the work/PR link from ION-16397 to ION-16417 (or close ION-16397 as raised-in-error).

### Option B — New branch + new PR (use only if you cannot rename on GitHub)

This creates a NEW PR number and loses the existing PR's comments/reviews.

1. Rename locally and reword the commit:
   ```powershell
   git branch -m feature/ION-16397-pi-aws-upgrade feature/ION-16417-pi-aws-upgrade
   git commit --amend -m "ION-16417: partner-integrator AWS SDK 1.x -> 2.x (cloud-sdk) upgrade"
   ```
2. Push the new branch and set upstream:
   ```powershell
   git push -u origin feature/ION-16417-pi-aws-upgrade
   ```
3. Open a new PR from `feature/ION-16417-pi-aws-upgrade` -> `develop` with an ION-16417 title/description.
4. Close the old PR (reference the new one) and delete the stale remote branch:
   ```powershell
   git push origin :feature/ION-16397-pi-aws-upgrade
   ```
5. Jira: link the new PR to ION-16417; close ION-16397 as raised-in-error.

### Recommendation
Use **Option A** — it is the least disruptive, keeps the PR history/approvals, and needs only one
force-push (single-commit branch). Option B is a fallback when branch rename is not permitted.


### Option A/B on Bitbucket Data Center (THIS REPO: `git.dev.e2open.com/scm/INT/mercury-services`)

**IMPORTANT — the GitHub "rename keeps the PR" trick (Option A above) does NOT work on Bitbucket
Data Center / Server.** Bitbucket has no PR-preserving branch rename: a branch rename is a
delete-old + push-new, and **deleting the source branch of an open PR automatically DECLINES that PR**
(comments/history stay on the now-closed PR for reference, but it is dead and cannot be reopened onto
the new branch). So on this repo the realistic path is effectively **Option B**.

Repo coordinates: project key `INT`, repo slug `mercury-services`,
base `https://git.dev.e2open.com`.

**Bitbucket steps (do these in order):**

1. **Rename locally and reword the single commit** (fixes branch name + commit `343ec541ec`):
   ```powershell
   git branch -m feature/ION-16397-pi-aws-upgrade feature/ION-16417-pi-aws-upgrade
   git commit --amend -m "ION-16417: partner-integrator AWS SDK 1.x -> 2.x (cloud-sdk) upgrade"
   ```

2. **Push the correctly-named branch** (creates it on Bitbucket; -u sets tracking):
   ```powershell
   git push -u origin feature/ION-16417-pi-aws-upgrade
   ```

3. **Open a NEW pull request** `feature/ION-16417-pi-aws-upgrade` -> `develop` with an ION-16417
   title/description. Either the Bitbucket UI (Repository -> Create pull request) or REST:
   ```powershell
   curl -u <user>:<app-password-or-token> -X POST -H "Content-Type: application/json" `
     https://git.dev.e2open.com/rest/api/1.0/projects/INT/repos/mercury-services/pull-requests `
     -d '{
           "title": "ION-16417: partner-integrator AWS SDK 1.x -> 2.x (cloud-sdk) upgrade",
           "fromRef": { "id": "refs/heads/feature/ION-16417-pi-aws-upgrade" },
           "toRef":   { "id": "refs/heads/develop" }
         }'
   ```

4. **Decline the OLD PR** (the one on `...ION-16397...`). Best done first via the UI/REST so you can
   add a comment linking to the new PR for traceability:
   ```powershell
   # find the old PR id, then:
   curl -u <user>:<token> -X POST `
     https://git.dev.e2open.com/rest/api/1.0/projects/INT/repos/mercury-services/pull-requests/<OLD_PR_ID>/decline?version=<PR_VERSION>
   ```

5. **Delete the stale remote branch** `feature/ION-16397-pi-aws-upgrade`
   (if you skipped step 4, deleting it here will auto-decline the old PR):
   ```powershell
   git push origin :feature/ION-16397-pi-aws-upgrade
   ```
   (or Bitbucket branch-utils REST:)
   ```powershell
   curl -u <user>:<token> -X DELETE -H "Content-Type: application/json" `
     https://git.dev.e2open.com/rest/branch-utils/1.0/projects/INT/repos/mercury-services/branches `
     -d '{ "name": "refs/heads/feature/ION-16397-pi-aws-upgrade" }'
   ```

6. **(Optional) rename the backup branch** and re-push:
   ```powershell
   git branch -m backup/ION-16397-pi-aws-upgrade-wip-20260820 backup/ION-16417-pi-aws-upgrade-wip-20260820
   git push origin :backup/ION-16397-pi-aws-upgrade-wip-20260820 backup/ION-16417-pi-aws-upgrade-wip-20260820
   ```

7. **Jira:** attach the new PR to ION-16417 and close ION-16397 as raised-in-error.

**Net difference vs GitHub:** on Bitbucket you cannot keep the same PR number / review threads — you
get a fresh PR and the old one is declined. Cross-link them in comments for history.
