# ION-12317 — AppianWay AWS SDK v2 Upgrade — Implementation Progress (Waves 1 & 2)

> **Ticket:** ION-12317 · **Branch:** `feature/ION-12317-apway-aws-upgrade` · **Started:** 2026-07-31
> **Design sources:** [program page](2026-07-22-ION-12317-aws-upgrade-program.md) ·
> [design summary](2026-07-23-appway-awsupgrade-design-summary.md) · the 14 per-module pages in this folder.
> **Target commons line:** `mercury-services-commons 1.0.28-SNAPSHOT` (the design said `1.0.27-SNAPSHOT`;
> the cloud-sdk gap work actually landed on `.28`).

Running implementation log. **Structure: one section per wave; every module in that wave is a sub-section of
it.** Wave 0 (pre-flight verification) and the cross-cutting deviation register come first because both waves
depend on them.

---

## Contents

- [Wave 0 — pre-flight](#wave-0--pre-flight-cloud-sdk-gap-verification)
- [Cross-cutting: deviations from the published design](#cross-cutting--deviations-from-the-published-design)
- [Wave 1](#wave-1--appianway-commons--functional-testing--event-writer)
  - [1.1 `appianway-commons`](#11-appianway-commons-new-reactor-module)
  - [1.2 `functional-testing`](#12-functional-testing-cloud-sdk-fakes-additive)
  - [1.3 `event-writer` (pilot)](#13-event-writer-pilot)
  - [1.4 Wave 1 verification & commit](#14-wave-1-verification--commit)
- [Wave 2](#wave-2--distributor-rest--splitter--ingestor)
  - [2.1 `appianway-commons` (wave-2 additions)](#21-appianway-commons-wave-2-additions)
  - [2.2 `distributor-rest`](#22-distributor-rest)
  - [2.3 `splitter`](#23-splitter)
  - [2.4 `ingestor`](#24-ingestor)
  - [2.5 Wave 2 verification & commit](#25-wave-2-verification--commit)
- [Tomorrow — open items](#tomorrow--open-items)
  - [T1 Close the QueueClient gap upstream in cloud-sdk](#t1-close-the-queueclient-gap-upstream-in-cloud-sdk--yes-this-is-doable-additively)
  - [T2 The AWS v1 leakage, restated](#t2-the-aws-v1-leakage--restated-plainly)
  - [T3 Should ingestor use cloud-sdk's JestModule?](#t3-should-ingestor-use-cloud-sdks-jestmodule-instead-of-its-own)

---

## Scope

| Wave | Modules | Status |
|---|---|---|
| **1** | `appianway-commons` (new) · `functional-testing` · **event-writer** (pilot) | done — commit `c1fe0d5` |
| **2** | `appianway-commons` (extended) · `distributor-rest` · `splitter` · `ingestor` | done — see §2.5 |

Waves 3–5 (`dispatcher`, `distributor`, `error-processor`, `email-sender`, `transformer`,
`watermill-publisher`, the 4 watermill consumers) are **out of scope here** and keep building against the
still-present `shared` module.

**Backward compatibility is the governing constraint.** No queue/topic/bucket/SSM-path/`${key}`-default
renames. No wire-format change. `shared` stays in the reactor until the last wave-5 module is off it.

---

## Wave 0 — pre-flight (cloud-sdk gap verification)

Verified against the `mercury-services-commons` working tree (`git log`) and the resolved artifacts in `~/.m2`.

| Gap | Commit | Verified API |
|---|---|---|
| **S-G2** | `b25ae16` | `StorageClient.putObject(bucket,key,byte[],Map,String)`, `putObject(bucket,key,InputStream,long,Map,String)`, `copyObject(...,Map,String)` — all `default` methods, so existing implementors are unaffected |
| **W-G9.1** | `116fb02` | `Event.Builder.setAnnotations(...)` + `annotations` copied in `Builder(Event)` → `Event.parseJson` now round-trips annotations |
| **W-G9.2** | `116fb02` | `MetaData.Projection` extended (incl. `DISTRIBUTOR_REST`, `ORIGINAL_IB_WORKSPACE_FILE`, `SPLITTER_FILE_SIZE`, `EVENT_PROVIDER`); `Event.Token` extended (incl. `ORIGINAL_FILE_SIZE`) |
| **X-G7** | `bfb03bd` | `MailContent.replyTo` + SES mapping (wave 4 — not exercised here) |
| **C-G6** | `1293c50` | `ConfigProcessingServerCommand.getConfigTransformer` widened to `protected`; new `PropertiesSubstitutionConfigProvider` |
| X-G8 | — | No cloud-sdk change by design; ingestor keeps the AWS **v1** Jest/OpenSearch SigV4 signer |

Field-by-field re-check of the wire model (`shared` vs `cloud-sdk-api`) confirmed identical:
`Event` field set/order/`@JsonInclude(NON_EMPTY)`/`@JsonFormat("yyyy-MM-dd HH:mm:ss.SS")`, `MetaData`,
`Annotations` (`@JsonProperty("Annotations")`), `Annotation` (`@JsonInclude(NON_NULL)`).

**Branch:**
```
git checkout -b feature/ION-12317-apway-aws-upgrade   # from develop
```
The pre-existing, unrelated whitespace edit in `dispatcher/.../DispatcherApplication.java` is left unstaged.

---

## Cross-cutting — deviations from the published design

| # | Design says | What was built | Rationale |
|---|---|---|---|
| **D1** | Target `1.0.27-SNAPSHOT` | `1.0.28-SNAPSHOT` | The S-G2/W-G9/X-G7/C-G6 gap work landed on `.28`; `.27` predates it. |
| **D2** | `com.inttra.mercury:appianway-commons:1.0-SNAPSHOT` | `com.inttra.mercury.appianway:appianway-commons:1.0` | Built as a reactor module inheriting the `appian-way:1.0` parent, matching every other AppianWay module. A distinct groupId keeps it unambiguously AppianWay-owned and un-publishable to the mercury-services line. |
| **D3** | network-services comes from **commons** | AppianWay's `networkservices` + `parameterstore` **moved as-is** into `appianway-commons`; only the SSM supplier is rebound v1 → cloud-sdk `CloudParameterStore` | commons' network-services has a materially different API/model surface (no `IntegrationProfileBy{Id,Params}Service`, no `Cache*` decorators, no `MessageRegisterService`/`SubscriptionPreferences`/`ConditionEvaluator`; models live under `.model` sub-packages with different shapes). Swapping them is a **behaviour-risk refactor with no AWS/CVE benefit** — it is not an AWS-layer change. Waves 1–2 keep AppianWay's clients byte-identical and still achieve the program goal (AWS v1→v2, `shared` retired per module). Re-pointing onto commons' network-services is tracked as follow-up for a later wave. |
| **D4** | `shared` is retired | `shared` remains in the reactor | 10 of the 14 apps (waves 3–5) still consume it; it is retired module-by-module. |

---

## Wave 1 — `appianway-commons` + `functional-testing` + `event-writer`

### 1.1 `appianway-commons` (new reactor module)

**Coordinates:** `com.inttra.mercury.appianway:appianway-commons:1.0`, parent `appian-way:1.0`, inserted into the
reactor immediately after `shared` so every consumer sees it. Package root `com.inttra.mercury.appianway.*`,
mirroring the `com.inttra.mercury.shared.*` layout so a call site migrates by import rename plus a type swap.

Depends on `cloud-sdk-api`, `cloud-sdk-aws` and `commons` at `1.0.28-SNAPSHOT`. **No `com.amazonaws.*` (AWS v1)
anywhere.** AWS SDK v2 arrives transitively, BOM-managed, via `cloud-sdk-aws`. Netflix Hystrix is dropped.

#### Class inventory

| Package | Classes | Notes |
|---|---|---|
| `config` | `S3Config`, `SQSConfig`, `SNSConfig`, `NetworkServiceConfig`, `RecoveryConfig`, `BaseConfiguration` | YAML shape byte-identical to `shared`; only the package moved |
| `config` | `S3ConfigurationProvider` | rebound to cloud-sdk `StorageClient`; client created **lazily** on first `open()` so the `requiresS3Configuration()` guard never touches AWS |
| `config` | `AwsClientTuning`, `AwsClients` | v2 replacements for `AWSClientConfiguration`/`AWSClientConfigHelper`; see "client tuning" below |
| `config.lookup` | `EnvironmentVariableLookup`, `PropertiesLookup`, `ValidatingLookup`, `VariableLookupProvider`, `ProcessedConfigProvider`, `DeferredPlaceholders` | ported verbatim (no AWS in them) + the `awsps:` exemption |
| `command` | `ConfigProcessingServerCommand` | keeps CLI name `run`; chains AppianWay substitution → commons trim → commons Parameter Store |
| `messaging` | `QueueClient`, `SqsQueueClient`, `AppianWayQueueMessage`, `SQSClient`, `SQSListenerClient`, `SNSClient`, `MessageSender`, `MessagingException` | see "the QueueClient decision" below |
| `listener` | `Listener`, `SQSListener`, `support.ListenerManager` | unchanged poll loop and back-pressure |
| `threaddispatcher` | `Dispatcher`, `AsyncDispatcher`, `TaskMessage` | AppianWay's semaphore-bounded pool, verbatim |
| `task` | `Task`, `TaskFactory`, `AbstractTask`, `ErrorHandler`, `ErrorMessage`, `ResourceBundleErrorMessage`, `errorhandler.ErrorHelper` | AppianWay error taxonomy and retry arithmetic unchanged |
| `externalwrapper.exception` | `RecoverableException`, `ExternalCallExecutionException` | unchanged |
| `healthcheck` | `HealthCheckRegistrar`, `RegistryBuilder`, `OpsHealthCheckServlet`, `indicator.*` (`HasName`, `ErrorThreshold`, `InboundSqs`, `OutboundSqs`, `S3Read`, `S3Write`, `SnsPublish`, `HttpGet`) | indicators now take **injected** clients |
| `workspace` | `WorkspaceService`, `S3WorkspaceService`, `S3ObjectWrapper`, `UnableToReadS3Object`, `UnableToWriteToFile` | on `StorageClient`; S-G2 overloads added |
| `support` | `Json`, `Files` | ported verbatim |
| `event` | `SNSEventPublisher` | publishes cloud-sdk `Event`s via `SNSClient` |

Everything with a cloud-sdk home is **consumed, not re-implemented**: the workflow model (`Event`, `MetaData`,
`Annotations`, `EventGenerator`, `EventLogger`, `EventPublisher`, `RandomGenerator`) all come from
`cloud-sdk-api` `notification.*`, which is a near-verbatim port of the `shared` originals.

#### The `QueueClient` decision (the one substantive design departure)

The design has the task chain typed on cloud-sdk `MessagingClient<String>` / `QueueMessage<String>`. The
message type is exactly that. The **client** is not, and deliberately so: cloud-sdk's `MessagingClient` cannot
express two things the AppianWay redelivery model is built on.

1. **Per-message `DelaySeconds`.** `ErrorHelper.sendMessageForRetry` re-queues a failed message with a computed
   exponential backoff (`2^attempt × delayMultiplier`). `MessagingClient.sendMessage(url, body, attributes)`
   maps its map to SQS *message attributes*, not to `DelaySeconds` — routing the delay through it would have
   silently dropped the backoff **and** invented a junk `delaySeconds` attribute on the wire.
2. **Reading user message attributes.** The retry counter travels as the `failedAttempts` message attribute.
   cloud-sdk's receive path requests no `messageAttributeNames`, and its `QueueMessage.getAttributes()`
   surfaces SQS *system* attributes — so the counter would never come back and **every redelivery would look
   like a first attempt**, defeating the max-attempts cap and the DLQ hand-off.

`QueueClient` is therefore a small AppianWay port over AWS SDK v2 SQS that preserves both, while still handing
back cloud-sdk `QueueMessage<String>` so the task chain is typed exactly as designed. `AppianWayQueueMessage`
differs from cloud-sdk's `SqsMessage` in one documented way: `getAttributes()` returns the **user** message
attributes.

#### Client tuning parity (`AwsClientTuning`)

The v1 `ClientConfiguration` presets are carried over one-for-one, including the detail that matters most:
`sqs_listener` had **no socket timeout**, because a 20-second long poll holds the connection open. The v2
listener client therefore also sets no socket timeout and no api-call timeout; a naive port to a shared
"default client" would have aborted every empty poll. Retry counts (3, or 2 for SNS) and the 500 ms→5 s
exponential backoff are preserved; v1 counted *retries*, v2 counts *attempts*, so the cap is `maxErrorRetry + 1`.

#### Config chain

```
classpath [module].yaml
    -> [AppianWay ${key} substitution]        multi-.properties + env, ${key:-default}, fail-fast
    -> [commons TrimConfigCommentsTransform]
    -> [commons ParameterStoreConfigTransform]  ${awsps:/path} from SSM at boot
    -> Dropwizard Configuration factory
```

Two details keep this backward compatible: `DeferredPlaceholders` exempts `awsps:`-prefixed names from the
AppianWay stage's fail-fast validation (otherwise it would reject tokens meant for the downstream transform),
and the Parameter Store lookup is **lazily constructed**, so a module with no `${awsps:}` token in its YAML —
which is all of waves 1 and 2 — makes no SSM call at boot, exactly as before.

commons' `ConfigProcessingServerCommand` is composed rather than extended, because it hard-codes Dropwizard's
default command name (`server`) and the AppianWay deployment contract is `run`. C-G6 is consequently not needed.

#### Behaviour notes worth flagging at review

- `WorkspaceService.put*` returns `void` instead of the AWS v1 `PutObjectResult` — no AppianWay caller read it.
- `S3WorkspaceService.getContent(bucket, key)` still joins lines with `\n` (the `shared` behaviour that golden-file
  assertions depend on); the `Charset` overload still reads verbatim. The line-joining read is now pinned to
  **UTF-8** rather than the JVM default charset — deliberate: the deployed containers are already UTF-8, and the
  old code would have decoded differently on a Windows developer machine.
- `InboundSqsHealthCheck` probes with `GetQueueAttributes` rather than a zero-visibility `ReceiveMessage`. Same
  intent (prove the queue is reachable and authorised), same IAM class, and it cannot consume or hide a message.
- `S3ReadHealthCheck` walks the exception cause chain for the "no such key" marker; cloud-sdk wraps the S3
  error, so checking only `getMessage()` would report a healthy bucket as unhealthy.
- `OpsHealthCheckServlet` uses plain `200`/`500` literals instead of Apache HttpClient 4's `HttpStatus`, so the
  residue library does not drag in httpclient for two integers. URL and payload unchanged.

### 1.2 `functional-testing` (cloud-sdk fakes, additive)

**Strictly additive** — this module is consumed by all ten unmigrated (wave 3–5) modules, so not one existing
class changed behaviour. The AWS v1 fakes (`FakeS3Impl`, `FakeSQSImpl`, `AmazonS3Adaptor`, `AmazonSQSAdaptor`,
`FunctionalTestBase`) stay exactly as they are and are deleted only when the last module leaves `shared`.

New, in `com.inttra.mercury.test.cloudsdk`:

| Class | Purpose |
|---|---|
| `FakeStorageClient` / `FakeStorage` | in-memory `StorageClient`. Stores bytes **plus** content type and user metadata, so S-G2 is assertable — the v1 fake could not observe either |
| `FakeQueueClient` / `FakeQueue` | in-memory `QueueClient`. Records send/deletion history **and per-send `DelaySeconds`**, so the retry backoff is assertable |
| `FakeNotificationService` | recording `NotificationService`, replacing the Mockito `AmazonSNS` + `ArgumentCaptor` pairing |
| `CloudSdkFunctionalTestBase` | binds `StorageClient`, listener + sender `QueueClient`, `NotificationService`, `RandomGenerator`, fixed `Clock`, `RecoveryConfig` — the same seams a migrated `ExternalServicesModule` binds in production |
| `assertions.{StorageAssert, QueueAssert, NotificationAssert, CloudResourceAssertions}` | cloud-sdk counterparts of `S3Assert`/`SqsAssert`/`SnsAssert`, plus `hasContentType`, `hasMetadataEntry`, `hasRetryDelays` |
| `util.CloudSdkMetaDataUtil` | `MetaDataUtil` against cloud-sdk `MetaData` |

`FakeStorageClient` is a real implementation rather than a throw-on-everything adaptor: `StorageClient` is a
small interface, so the ~700-line `AmazonS3Adaptor` has no cloud-sdk equivalent to write.

One existing class gained an **overload only**: `IntegrationTestSupport` / `IntegrationTestRule` now accept an
optional `Function<Application<C>, ServerCommand<C>>`. Existing callers are unchanged and still get `shared`'s
command; a migrated module passes its own, so the functional test boots through the config-transform chain that
actually ships.

### 1.3 `event-writer` (pilot)

| Change | Detail |
|---|---|
| Maven | `mercury-shared` **removed** (and with it AWS SDK v1, which arrived only transitively) → `appianway-commons`. Nothing orphaned. |
| Task chain | `SQSMessageWriterTask`, `SQSMessageHandler`, `S3StoringMessageHandler`, `SQSMessageToEventConverter` retyped from AWS v1 `Message` to `QueueMessage<String>`; `getBody()` → `getPayload()`. |
| Workflow model | `shared.event.Event` → `cloud-sdk-api notification.workflow.Event`. |
| **S-G2** | The S3 write now uses `putObject(bucket, key, byte[], metadata, contentType)` with `application/json`. Every object this component writes is a `.json` audit record; the old `putObject(bucket, key, String)` path left them all `text/plain`. Key and bytes unchanged — header-only. |
| **W-G9.1** | Events are parsed and serialised through cloud-sdk's `JsonSupport`, so an `annotations` block round-trips. This is the highest-severity item in the program: event-writer is the only module that archives raw `Event` JSON to durable storage, so a dropped annotation block is silent, permanent audit-trail data loss. |
| `SNSNotification` | moved from `shared.event` into `event-writer`. It is the raw SNS *delivery envelope*, not a workflow type, and event-writer is its only consumer — so it belongs neither in the residue library nor in cloud-sdk's workflow model. |
| Health checks | the three indicators now take the app's injected `QueueClient`/`StorageClient` instead of building their own default v1 clients. |
| Config | **nothing renamed.** Same YAML keys and defaults, same queue `inttra_int_sqs_event`, same bucket `inttra-int-workspace`, same `eventstore` prefix, same CLI arg shape, same `CONFIG_REGION`. No `${awsps:}` introduced — event-writer has no `networkServiceConfig` and makes no SSM call at boot, before or after. |

**Tests.** `SQSMessageWriterTaskTest` and `S3StoringMessageHandlerTest` retyped; the latter now also asserts the
S-G2 content type. Added `archivesAnnotationsInsteadOfSilentlyDroppingThem` — the W-G9.1 guard — with a new
`event-with-annotations.json` fixture; it asserts annotations survive both the parse and the write into the
archived bytes. `EventWriterFuncTest` moved to `CloudSdkFunctionalTestBase` and boots through AppianWay commons'
command; it additionally asserts the stored content type.

### 1.4 Wave 1 verification & commit

```
mvn -o -pl event-writer clean verify
  Tests run: 2  S3StoringMessageHandlerTest
  Tests run: 1  SQSMessageWriterTaskTest
  Tests run: 1  EventWriterFuncTest
  Tests run: 4, Failures: 0, Errors: 0, Skipped: 0   BUILD SUCCESS

mvn -o clean verify -DskipTests        # whole reactor, all 23 modules  -> BUILD SUCCESS
mvn -o verify                          # whole reactor with tests
```

The full-reactor test run is green through `Watermill-publisher`. It then fails in **`consumer-commons`** on
`S3PublishServiceTest.testGetFullS3Path_ShouldReturnPathWithCurrentDate`.

**This failure is pre-existing and unrelated** — verified by running the same test on `develop`, where it fails
identically (`expected: <true> but was: <false>`, "Path should start with today's date"). It is a UTC-vs-local
date-boundary bug in the test itself; `consumer-commons` is a wave-5 module and depends on nothing this wave
touched. Left alone as out of scope, and flagged here for the wave-5 work.

> Also seen in the reactor log: `Invalid packaging for parent POM com.inttra.mercury:visibility-commons` /
> "parents form a cycle" around `visibility-inbound-consumer`. Pre-existing, non-fatal resolution noise against
> the external mercury-services POMs — the module builds and its tests run.

---

## Wave 2 — `distributor-rest` + `splitter` + `ingestor`

### 2.1 `appianway-commons` (wave-2 additions)

| Package | Added | Notes |
|---|---|---|
| `parameterstore` | `ParameterStore`, `ParameterSupplier`, `SsmParameterSupplier`, `PassThroughParameterSupplier`, `ParameterStoreModule` | rebound from AWS v1 `AWSSimpleSystemsManagement` to cloud-sdk `CloudParameterStore`. SSM paths, decryption, the `usePassThrough` switch and the eager-singleton fetch (so a bad path fails the boot, not the first request) are all unchanged. `usePassThrough=true` now builds **no** SSM client at all. The v1 `GetParameters` call returned an invalid-name list in one round trip; cloud-sdk exposes per-name lookups, so misses are collected and reported together in the same `ParameterNameNotFound`. |
| `externalwrapper` | `ExternalCallWrapper`, `ExternalCallWrapperFactory`, `ExternalCallSettings`, `MixedStopStrategy`, `Throwables`, `guice.*`, `guice.annotation.ExternalCall` | **Hystrix removed.** Retry behaviour is unchanged (same exponential wait, same combined attempt-count/execution-timeout stop strategy, same `RecoverableException` vs `ExternalCallExecutionException` translation). `hystrixCommandKey`/`hystrixGroupKey` are renamed `commandKey`/`groupKey` — they were only ever the method and class names used to label retry logs. |
| `networkservices` | the whole tree, 68 files, moved verbatim | See **D3**. `package-info.java` records the rationale and the follow-up. |
| `event` | `EventConstants`, `SNSNotification` | |

**`EventConstants`.** `shared`'s `EventGenerator` carried ten public constants; cloud-sdk's carries the three it
uses itself. The other seven (`START_RUN`, `START_WORKLOW`, `CLOSE_WORKLOW`, `TRANSFORMATION_SUPPLEMENT_TOKEN`,
`NEXT_RETRY_TIME`, `TIME_TAKEN_FOR_*`) are AppianWay pipeline vocabulary with no cloud-sdk consumer, so they
live here rather than being pushed into a production mercury-services dependency to earn nothing. The three
that do exist upstream are **re-exported** from cloud-sdk's `EventGenerator` rather than re-declared, so each
wire value has exactly one source of truth. All values byte-identical — these strings are on the wire and in
the S3 event archive.

**`SNSNotification`** moved from event-writer (where wave 1 put it) into `appianway-commons`, because ingestor
is a second consumer.

Every `MetaData.Projection` and `Event.Token` constant the three modules use is present in cloud-sdk —
W-G9.2 confirmed by inspection against the actual call sites, including `SPLITTER_FILE_SIZE`,
`DISTRIBUTOR_REST` and `ORIGINAL_FILE_SIZE`.

### 2.2 `distributor-rest`

- Maven: `mercury-shared` **and** its orphan `aws-java-sdk-sqs` declaration removed → `appianway-commons`.
- Four AWS v1 clients (`AmazonSQS` ×2, `AmazonS3`, `AmazonSNS`) → cloud-sdk equivalents via `AwsClients`.
- `DistributorTask` retyped to `QueueMessage<String>`; `MetaData` parsed with `MetaData.parseJson` so the
  same cloud-sdk mapper handles both parse and serialise for that type.
- `IOException` dropped from the `catch` in `DistributorTask.process`: `shared`'s `WorkspaceService`
  *interface* declared `throws IOException` on `getContent`, but its S3 implementation never threw it — every
  failure was already wrapped as `RecoverableException`, which propagates exactly as before.
- Dead `HystrixBundle` import removed (the registration was already commented out).
- Test fix: `Helper.java` had a stray `import static com.amazonaws...HistoryItemType.Action` shadowing the
  subscription model's `Action`, which the code worked around with a fully-qualified name. Both are gone.
- **142 tests green.**

### 2.3 `splitter`

- Same Maven and client changes as distributor-rest.
- **Retype care:** splitter has its own `com.inttra.mercury.splitter.core.Message`. A blanket
  `Message` → `QueueMessage<String>` rewrite silently corrupted it (45 files), so that pass was reverted and
  redone: package rewrites applied mechanically, the AWS-v1-message retype applied only to the six files that
  genuinely handle a queue message. Worth knowing for waves 3–5 — `transformer` and `distributor` should be
  checked for the same name collision before any bulk rewrite.
- Health checks now take the app's injected `QueueClient`/`StorageClient`/`NotificationService`.
- Functional test moved to `CloudSdkFunctionalTestBase`, booting through AppianWay commons' command. The v1
  `AmazonServiceException(500)` used to simulate a transient S3 fault becomes cloud-sdk's
  `S3OperationException` — both are what `S3WorkspaceService` wraps into `RecoverableException`, so the retry
  path under test is unchanged.
- Test fix in `SplitterTaskTest.shouldHandleGenericException`: it stubbed `getContent` to throw a checked
  `IOException`, which Mockito now rejects (see the interface note above). Replaced with
  `UnableToReadS3Object` carrying the same `IOException` as its cause — the real post-migration failure, and
  it lands in the same generic `catch (Exception)` branch the test exercises.
- **179 tests green** (2 pre-existing `@Ignore`).

### 2.4 `ingestor`

- Same Maven and client changes, plus the module's own task package (`Task`, `TaskFactory`,
  `AsyncDispatcher`, `IngestorTask`, `ErrorHandler`) retyped from `List<Message>` to
  `List<QueueMessage<String>>`.
- **X-G8 (corrected) honoured:** `JestModule` is untouched and keeps the AWS **v1** SigV4 signer
  (`vc.inreach.aws.request.AWSSigner`) for OpenSearch. Jest (`io.searchbox` 6.3.1, Apache HttpClient 4.x) is
  not compatible with AWS SDK v2 and no mercury-services module migrates it. The two SDKs coexist —
  different namespaces. These two imports are the only `com.amazonaws.*` source references left in any
  wave-1/2 module.
- **Caught a real regression:** `aws-signing-request-interceptor` drags in `aws-java-sdk-core` **1.10.19**
  transitively. That was previously masked by `mercury-shared`'s 1.12.720; removing `mercury-shared` would
  have silently rolled the signer's credentials core back nine years of AWS v1 security fixes. The
  interceptor's transitive core is now excluded and `aws-java-sdk-core` pinned explicitly at the reactor's
  `${aws-java-sdk.version}`. This is the only AWS v1 artifact declared in any wave-1/2 module.
- Test fixes: `ErrorHandlerTest`/`IngestorTaskTest` build `AppianWayQueueMessage` instead of the v1 fluent
  `Message` builders; attribute values are plain Strings (AppianWay only ever sent String-typed attributes,
  and `QueueClient` preserves that on the wire).
- Functional harness moved to `CloudSdkFunctionalTestBase`; the Jest/OpenSearch fake is untouched.
- **179 tests green.**

### 2.5 Wave 2 verification & commit

```
mvn -o -pl distributor-rest clean verify   -> 142 tests, BUILD SUCCESS
mvn -o -pl splitter         clean verify   -> 179 tests (2 skipped), BUILD SUCCESS
mvn -o -pl ingestor         clean verify   -> 179 tests, BUILD SUCCESS
mvn -o clean verify -DskipTests            -> all 23 modules, BUILD SUCCESS
mvn -o verify                              -> whole reactor with tests
```

Whole-reactor test run: **every module green except the pre-existing `consumer-commons`
`S3PublishServiceTest` date-boundary failure** documented in §1.4 (verified failing identically on `develop`).

Post-migration audit:

```
grep -rn "com.inttra.mercury.shared|import com.amazonaws" \
     event-writer/src distributor-rest/src splitter/src ingestor/src appianway-commons/src
  -> only ingestor/.../JestModule.java:3,4  (the deliberate X-G8 v1 signer)
```

#### Open finding — AWS SDK v1 still on the classpath, declared by cloud-sdk-aws

`mvn dependency:tree` on all four migrated modules shows AWS SDK **v1 1.12.730** (`aws-java-sdk-sqs`, `-sns`,
`-s3`, `-kms`, `-core`, `jmespath-java`) still present at compile scope. It no longer comes from AppianWay
code — `cloud-sdk-aws` **declares it directly**, already flagged with a TODO by its author:

```xml
<!-- cloud-sdk-aws/pom.xml, lines 203-227 -->
<!-- AWS SDK v1 (legacy) - version managed by root pom.xml dependencyManagement.
     TODO: Remove once all apps are migrated to AWS SDK v2 and Jest Client is replaced. -->
com.amazonaws:aws-java-sdk-core          (version from root dependencyManagement)
com.amazonaws:aws-java-sdk-sqs:1.12.730
com.amazonaws:aws-java-sdk-sns:1.12.730
com.amazonaws:aws-java-sdk-s3:1.12.730
+ io.searchbox:jest:6.3.1  and  vc.inreach.aws:aws-signing-request-interceptor:0.0.22
```

> **Correction.** An earlier revision of this document blamed
> `com.amazonaws:amazon-sqs-java-extended-client-lib:2.0.4`. That was a misreading of the indented
> `dependency:tree` output — the extended client and the v1 jars are *siblings*, both direct dependencies of
> `cloud-sdk-aws`. The extended client 2.0.4 is v2-only (`software.amazon.awssdk:sqs`, `:s3`,
> `payloadoffloading-common`) and is not the source of the leak.

They exist to support a **v1-based legacy Guice module set** inside cloud-sdk-aws:
`com.inttra.mercury.cloudsdk.aws.module.{SQSModule, SNSModule, SQSReader, SQSWriter, JestModule,
AwsRetryCondition, AWSConstants}`.

**Who actually uses those legacy modules** (`grep -rl "cloudsdk.aws.module"`):

| Repo | Consumers |
|---|---|
| mercury-services | `booking` (5 files), `webbl`, `tx-tracking`, `visibility/visibility-commons` |
| **appianway** | **none** — no AppianWay module references them, before or after this migration |

**Consequence:** the AppianWay apps no longer *use* AWS v1, but an OWASP dependency-check still sees v1 jars
on their classpath, so "AWS SDK v1 eliminated" is not yet true at the artifact level.

**Fix options (upstream in `mercury-services-commons`, own ticket + branch):**

- **Option A — minimal.** Mark the four v1 dependencies `<optional>true</optional>` in `cloud-sdk-aws`. They
  stop propagating transitively, so every consumer that does *not* touch the legacy modules — all 14 AppianWay
  apps — drops v1 entirely. The four mercury-services apps that do use them declare v1 in their own POM
  (exactly the pattern ingestor already follows for its Jest signer). No source change, no behaviour change.
  Note this is **not** an additive change — it breaks transitive inheritance — so it needs the program's usual
  gate: land it, then a full mercury-services build green. Failures would be loud compile errors, not silent.
- **Option B — clean end state.** Split `cloudsdk.aws.module.*` plus Jest and the signer into a separate
  `cloud-sdk-aws-legacy` artifact that owns the v1 dependency; `cloud-sdk-aws` becomes pure v2. The four apps
  switch to the legacy artifact, which is then deleted outright when they migrate. This is what the existing
  TODO is really describing.

**Recommendation:** A now (it unblocks the AppianWay CVE story immediately and is a four-line POM change),
B as the eventual shape. Either way it is a prerequisite before claiming the v1 CVE surface is gone.

---

## Tomorrow — open items

Three things, in priority order. Nothing below is implemented; waves 1 and 2 are complete and green as they
stand.

### T1. Close the `QueueClient` gap upstream in cloud-sdk — **yes, this is doable additively**

**The question:** appianway-commons owns `QueueClient`/`SqsQueueClient`/`AppianWayQueueMessage` only because
cloud-sdk's `MessagingClient` can't do two things (§2.1). Can those two things be added to cloud-sdk instead,
so AppianWay deletes its port and uses `MessagingClient` directly?

**Answer: yes, and it fits the program's strictly-additive contract** — same shape as S-G2 and W-G9. Three
changes, none of which alters existing behaviour or breaks an existing implementor:

| # | Change | Where | Additive because |
|---|---|---|---|
| **M-G1** | `default void sendMessage(String queueUrl, T body, int delaySeconds, Map<String,String> attributes)` | `cloud-sdk-api` `MessagingClient` | new `default` method; its default body delegates to the existing `sendMessage(url, body, attributes)` and ignores the delay, so every current implementor still compiles. `SqsMessagingClient` overrides it with `SendMessageRequest.builder().delaySeconds(...)`. |
| **M-G2** | `messageAttributeNames(List<String>)` on `ReceiveMessageOptions.Builder`, honoured by `SqsMessagingClient.receiveMessages(options)` | `cloud-sdk-api` + `cloud-sdk-aws` | new optional builder field defaulting to empty; today's call sites request no attribute names, which is exactly what an empty default produces. `ReceiveMessageOptions` already carries `queueUrl`, `maxMessages`, `visibilityTimeoutSeconds`, `waitTimeSeconds`, `attributes` — this slots in beside them. |
| **M-G3** | `default Map<String,String> getMessageAttributes()` returning `Map.of()` | `cloud-sdk-api` `QueueMessage` | **new method, not a change to `getAttributes()`.** `SqsMessage.getAttributes()` returns SQS *system* attributes and some consumer may rely on that; repurposing it would be a silent behaviour change. Adding a separate accessor for *user* attributes is safe. `SqsMessage` overrides it from `sqsMessage.messageAttributes()`. |

**Payoff.** With M-G1..M-G3 landed, `QueueClient`, `SqsQueueClient` and `AppianWayQueueMessage` are deleted
from appianway-commons; `SQSClient`/`SQSListenerClient` bind plain `MessagingClient<String>`; the
`FakeQueueClient` in functional-testing implements `MessagingClient<String>` instead. Roughly 300 lines of
AppianWay code retired, and the AppianWay retry model runs on the same client every other mercury-services app
uses. Worth doing **before** wave 3, since dispatcher/distributor/error-processor lean on the retry path even
harder than wave 2 did.

**Cost/risk.** Small: three additive signatures, one real implementation change (`SqsMessagingClient`), gated
as usual on cloud-sdk CI + a full mercury-services build green. If it slips, waves 3-5 proceed on
`QueueClient` unchanged — nothing blocks on it.

### T2. The AWS v1 leakage — restated plainly

Forget dependency trees for a second. The situation in one paragraph:

> `cloud-sdk-aws` is *mostly* an AWS SDK v2 library, but it also still ships a handful of **old v1-based Guice
> modules** left over from before the v2 work. Because those modules exist, `cloud-sdk-aws`'s POM has to
> declare AWS SDK **v1** jars. Maven then hands those v1 jars to **everyone** who depends on `cloud-sdk-aws` —
> including all 14 AppianWay apps, which never touch those old modules. So AppianWay ships v1 jars it doesn't
> use, and OWASP flags them.

Which v1 jar is needed by what — **corrected 2026-08-01 after checking the actual imports rather than the
package prefix**:

| v1 jar | Classes in `cloudsdk.aws.module.*` that need it | Consumers of those classes | Verdict |
|---|---|---|---|
| `aws-java-sdk-core` | `JestModule` (`AWSCredentialsProvider`, `DefaultAwsRegionProviderChain`), `AWSConstants`, `AwsRetryCondition` | **`JestModule`: 31 files** across mercury-services | **Keep** — genuinely needed for ES SigV4 signing, no v2 equivalent |
| `aws-java-sdk-sqs` | `SQSModule`, `SQSReader`, `SQSWriter` | **zero** | **Remove** — dead code |
| `aws-java-sdk-sns` | `SNSModule` | **zero** | **Remove** — dead code |
| `aws-java-sdk-s3` | nothing — no `com.amazonaws.services.s3` import anywhere in `cloud-sdk-aws/src` | **zero** | **Remove** — never used |

> **Correction — an earlier revision of this section was wrong twice over.** It claimed the v1 leak was
> "~75% not Jest" and named `booking`, `webbl`, `tx-tracking` and `visibility-commons` as consumers of the
> legacy v1 SQS/SNS modules. Both claims came from `grep -rl "cloudsdk.aws.module"`, which matches the
> *package prefix* and says nothing about which class is imported. Checking the actual imports:
>
> - every one of those four apps imports **only `JestModule`** from that package;
> - `booking-cargoscreen` does import `SQSModule`/`SNSModule`/`AwsRetryCondition`, but from
>   **`com.inttra.mercury.messaging.config.*`** — a different, app-side package, not cloud-sdk's;
> - `visibility-commons`' `VisibilityMessagingModule` only *mentions* `SQSModule`/`SNSModule` in a javadoc
>   line saying it **replaces** them; it binds `MessagingClient`/`MessagingClientFactory` (v2).
>
> So `cloudsdk.aws.module.{SQSModule, SNSModule, SQSReader, SQSWriter, AWSConstants}` have **no consumers at
> all**, and the original recollection — *"the 1.x dep is only for the JestClient and ES signing"* — is
> correct.

**Revised plan, simpler than before.** In `cloud-sdk-aws`:

1. Delete the dead legacy classes `SQSModule`, `SNSModule`, `SQSReader`, `SQSWriter` (and `AWSConstants` if
   nothing else references it) — zero consumers, so this is a straight deletion.
2. Drop `aws-java-sdk-sqs`, `aws-java-sdk-sns` and `aws-java-sdk-s3` from the POM with them.
3. Keep `aws-java-sdk-core` for `JestModule` / `AwsRetryCondition`; optionally mark it
   `<optional>true</optional>` so only apps that actually sign ES requests inherit it.

That removes AWS v1 SQS/SNS/S3 from the classpath of **every** cloud-sdk-aws consumer, AppianWay included,
with no change to any consuming app. The residual `aws-java-sdk-core` is the honest remainder, and it goes
when Jest is replaced — exactly what cloud-sdk's own TODO says.

### T3. Ingestor should adopt cloud-sdk's `JestModule` — **recommended** (earlier objection was wrong)

Your recollection was right on both halves. cloud-sdk has `cloudsdk.aws.module.JestModule`, and AppianWay
ingestor still carries its own near-duplicate at `com.inttra.mercury.ingestor.modules.JestModule`; wave 2 left
it alone because X-G8 said "keep the v1 signer as-is" and I read that as "don't touch this module".

> **Correction.** An earlier revision of this section objected that adopting cloud-sdk's `JestModule` would
> force a **YAML-shape change** (`ElasticSearchConfig` -> `ElasticSearchServiceConfig`) and therefore break the
> program's no-config-change rule. **That is wrong.** `ElasticSearchServiceConfig` is an *interface* in
> `cloud-sdk-api` (`com.inttra.mercury.cloudsdk.config`), and the established pattern across mercury-services
> is that an app keeps its **own** config POJO with its **own** YAML field names and simply implements it:
>
> ```java
> public class ElasticsearchConfig implements ElasticSearchServiceConfig      // booking
> public class ElasticSearchConfig  implements ElasticSearchServiceConfig     // oceanschedules loader
> ```
>
> Same in bill-of-lading, booking-cargoscreen, oceanschedules aggregator and port-pair-generator. No YAML
> changes anywhere.

**What ingestor actually needs.** Its `ElasticSearchConfig` already has `endpointUrl`, `region`, `service`.
The interface additionally wants `username`, `password`, `connTimeoutMillis`, `readTimeoutMillis`,
`maxRetries` — all **optional** with sensible defaults, so adding them as fields with defaults keeps
`ingestor.yaml` valid exactly as it stands. Then:

- `ElasticSearchConfig implements ElasticSearchServiceConfig`;
- delete `com.inttra.mercury.ingestor.modules.JestModule`, install `cloudsdk.aws.module.JestModule`;
- drop ingestor's own `vc.inreach:aws-signing-request-interceptor` and the explicit `aws-java-sdk-core` pin
  from §2.4 — both then arrive via `cloud-sdk-aws`, which is where the ES-signing v1 dependency belongs.

Net: one duplicated class and two POM entries removed from AppianWay, ingestor gains username/password auth
and a configurable retry handler for free, and the v1 dependency lives in exactly one place. Do this together
with T2, since T2 step 3 decides whether `aws-java-sdk-core` is inherited or declared per-app.
