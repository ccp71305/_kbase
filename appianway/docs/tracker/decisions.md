# Decisions (D#) and decision records (DR#)

← [Tracker home](README.md) · Superseded decisions: [closed-items.md](closed-items.md#closed-decisions)

D# = a decision taken during development, with its reason. DR# = the full record of a question asked: the explanation, the options and the answer.

| ID | Date | Title |
|---|---|---|
| [D1](#d1) | 2026-10-31 | This document is the main work document |
| [D2](#d2) | 2026-10-31 | Library-version guard test (at least the commons version) |
| [D3](#d3) | 2026-10-31 | logback-core pinned next to logback-classic |
| [D4](#d4) | 2026-10-31 | HttpComponents 4.x not asserted |
| [D5](#d5) | 2026-10-31 | Enforcer rule for the logback pair |
| [D6](#d6) | 2026-10-31 | 1b stacked on 1a |
| [D7](#d7) | 2026-10-31 | shared excludes unused heavy commons transitives |
| [D8](#d8) | 2026-10-31 | U1 fallback keeps ConfigProcessingServerCommand |
| [D9](#d9) | 2026-10-31 | Parameter Store lookup created lazily |
| [D10](#d10) | 2026-10-31 | Red commits carry compiling skeletons |
| [D11](#d11) | 2026-10-31 | Properties read failure stays a RuntimeException |
| [D12](#d12) | 2026-10-31 | Guava 33.6.0-jre |
| [D14](#d14) | 2026-10-31 | Client profile follows today's real v1 values |
| [D15](#d15) | 2026-10-31 | QueueMessage overloads on the v1-typed classes |
| [D16](#d16) | 2026-10-31 | Retry strategy: standard, 4 attempts, retry every failure |
| [D17](#d17) | 2026-10-31 | HTTP transport per client |
| [D18](#d18) | 2026-10-31 | AbstractTask picks the process method once |
| [D19](#d19) | 2026-10-31 | v2 dispatcher method named dispatch |
| [D20](#d20) | 2026-10-31 | Both metered execute methods share one run |
| [D21](#d21) | 2026-10-31 | Type witnesses for ambiguous any()/null in tests |
| [D23](#d23) | 2026-10-31 | Stress environment ignored |
| [D24](#d24) | 2026-11-09 | Listener receives min(idle workers, 10) |
| [D25](#d25) | 2026-11-17 | Naming rule: cloud-sdk-api concept names |
| [D26](#d26) | 2026-11-17 | WorkspaceService puts return void |
| [D27](#d27) | 2026-11-17 | MessageQueueClient with SQSClient extending it |
| [D28](#d28) | 2026-11-17 | StorageReadHealthCheck keeps the GET of anykey |
| [D29](#d29) | 2026-11-17 | Parameter store role settings |
| [D30](#d30) | 2026-11-17 | CloudServicesModule shape |
| [D31](#d31) | 2026-11-17 | StorageConfigurationProvider replaces S3ConfigurationProvider |
| [D32](#d32) | 2026-11-17 | Storage has two roles (download without timeout) |
| [D33](#d33) | 2026-11-17 | Cloud-sdk fakes keep the test-facing APIs |
| [D34](#d34) | 2026-11-17 | Boundary test on ArchUnit core |
| [D35](#d35) | 2026-11-18 | functional-testing imports junit-bom 5.14.4 |
| [D36](#d36) | 2026-11-18 | FakeQueue peek with visibility 0 |
| [D37](#d37) | 2026-11-18 | event-writer: ExternalServicesModule deleted |
| [D38](#d38) | 2026-11-18 | error-processor keeps ExternalServicesModule |
| [D39](#d39) | 2026-11-19 | dispatcher: withParameters, no pass-through, no overrides |
| [D40](#d40) | 2026-11-19 | dispatcher parser keeps two v1 edge cases |
| [D41](#d41) | 2026-11-19 | dispatcher golden test sends LF inputs |
| [D42](#d42) | 2026-11-19 | dispatcher drops its direct SQS v1 dependency |
| [D43](#d43) | 2026-11-20 | Known existing defects are not fixed in this program |
| [D44](#d44) | 2026-11-20 | splitter's golden test runs with one pickup worker |
| [D45](#d45) | 2026-11-20 | transformer drops the AWS SDK CloudWatch metrics |
| [D46](#d46) | 2026-11-20 | Watermill consumers may advance QA's offsets in runtime tests |
| [D47](#d47) | 2026-11-20 | QA DynamoDB writes allowed for runtime tests |
| [D48](#d48) | 2026-11-20 | watermill-publisher verified up to the publish call only |
| [D49](#d49) | 2026-11-20 | billoflading consumers are in scope |

Superseded: [D13](closed-items.md#d13) (superseded by U11 (no API-call timeout) and [D32](#d32)), [D22](closed-items.md#d22) (superseded by [D24](#d24)).

Decision records: [DR-1](#dr-1), [DR-2](#dr-2), [DR-3](#dr-3), [DR-4](#dr-4).

---

<a id="d1"></a>
### D1 · This document is the main work document (2026-10-31)

**Decision.** The progress document is the main work document; pending items from the review summary are tracked here (§2)

**Reason.** User request

<a id="d2"></a>
### D2 · Library-version guard test (at least the commons version) (2026-10-31)

**Decision.** The library-version guard is a unit test reading `pom.properties` from the test classpath and asserting "at least the commons version" (not equality), except Dropwizard (exact) and the logback pair (equal to each other)

**Reason.** Detects any AppianWay pin that downgrades commons without breaking on later commons upgrades

<a id="d3"></a>
### D3 · logback-core pinned next to logback-classic (2026-10-31)

**Decision.** `logback-core` is pinned next to `logback-classic` in the root pom

**Reason.** Today only classic is pinned; core comes from the Dropwizard BOM, so bumping classic alone would create a mismatched pair

<a id="d4"></a>
### D4 · HttpComponents 4.x not asserted (2026-10-31)

**Decision.** HttpComponents 4.x is not asserted in the version test

**Reason.** It reaches `shared` only through AWS SDK v1, which step 5 removes; covered by `dependency:tree` instead

<a id="d5"></a>
### D5 · Enforcer rule for the logback pair (2026-10-31)

**Decision.** The logback pair is guarded per module by a Maven Enforcer `requireSameVersions` rule in the root pom, in addition to the `shared` unit test

**Reason.** A unit test only sees its own module's classpath; the enforcer rule checks every child's resolved dependencies at `validate`, so one rule covers all services and future modules

<a id="d6"></a>
### D6 · 1b stacked on 1a (2026-10-31)

**Decision.** Step 1b is cut from the 1a sub-branch (stacked), not from the feature branch

**Reason.** 1b needs 1a's commons coordinates and JUnit Platform; #76 is not merged yet. After #76 merges: `git rebase --onto feature/WI01124532-aws-sdk-upgrade WI01124532-aws-sdk-upgrade-pom WI01124532-aws-sdk-upgrade-shared-config`, then open the 1b PR

<a id="d7"></a>
### D7 · shared excludes unused heavy commons transitives (2026-10-31)

**Decision.** `shared` depends on `commons` with the unused heavy transitives excluded (mysql-connector-java, MyBatis + mybatis-guice, Apache POI, Jest 5.3.3 + aws-signing-request-interceptor, junit:junit, dropwizard-db, dropwizard-forms)

**Reason.** User decision: smaller service jars and CVE surface; the full reactor tests prove nothing needs them

<a id="d8"></a>
### D8 · U1 fallback keeps ConfigProcessingServerCommand (2026-10-31)

**Decision.** The U1 fallback keeps `com.inttra.mercury.shared.command.ConfigProcessingServerCommand` (same name, constructors, `run (yaml) (properties...)`) and replaces only its internals with the commons chain

**Reason.** No service or subclass (ingestor `CreateMappingTemplate`, transformer / cargoscreen / itv-gps `DynamoTableCommand`) changes

<a id="d9"></a>
### D9 · Parameter Store lookup created lazily (2026-10-31)

**Decision.** The Parameter Store lookup is created lazily, only when the configuration contains `${awsps:`

**Reason.** commons `ParameterStoreLookup()` builds an SSM client in its constructor; no AppianWay config uses `${awsps:}` today, so eager creation would add a client and startup time to every service

<a id="d10"></a>
### D10 · Red commits carry compiling skeletons (2026-10-31)

**Decision.** Red commits contain the new tests plus compiling skeletons (signatures that throw `UnsupportedOperationException`), so each red commit builds and fails only at test time

**Reason.** Keeps every commit compilable for review and bisect

<a id="d11"></a>
### D11 · Properties read failure stays a RuntimeException (2026-10-31)

**Decision.** The command keeps wrapping a properties read failure in a `RuntimeException` (`UncheckedIOException`); the new JUnit 5 test's first expectation (`IOException`) was corrected in the green commit

**Reason.** The existing JUnit 4 tests are the compatibility contract; the new test had asserted a behaviour change

<a id="d12"></a>
### D12 · Guava 33.6.0-jre (2026-10-31)

**Decision.** Guava pinned to 33.6.0-jre (the Dropwizard 5.0.2 managed version), not commons' 33.5.0-jre

**Reason.** `shared` already resolves 33.6.0-jre from the Dropwizard BOM; pinning modules to 33.5.0-jre would itself be a downgrade for the upper-bound rule

<a id="d14"></a>
### D14 · Client profile follows today's real v1 values (2026-10-31)

**Decision.** The client profile follows **today's real v1 values**, not the design table: SNS **3** retries (v1 `RetryPolicy(…, 3, honorMaxErrorRetryInClientConfig=false)` ignores SNS's `withMaxErrorRetry(2)`), SQS listener socket timeout **50 s** (v1 default; `sqs_listener` sets none)

**Reason.** User decision: backward compatibility first. Design pages corrected later via the review-summary post-publish tracker ([A21](actions.md#a21))

<a id="d15"></a>
### D15 · QueueMessage overloads on the v1-typed classes (2026-10-31)

**Decision.** Transition of the v1-typed APIs (`Task`, `TaskFactory`, `Dispatcher`, `AbstractTask`, `ErrorHandler`, `ErrorHelper`, `TaskMessage`): `QueueMessage<String>` **overloads on the same classes** (v2 methods as defaults / concrete methods), used by the v2 listener and dispatcher; each module PR switches its tasks to the v2 overloads; step 5 deletes the v1 methods so the final API matches the design (same packages and class names)

**Reason.** User decision; no second import change in every module

<a id="d16"></a>
### D16 · Retry strategy: standard, 4 attempts, retry every failure (2026-10-31)

**Decision.** Retry strategy for SQS/SNS/S3: SDK 2.x standard strategy, 4 max attempts (= v1 3 retries), `BackoffStrategy.exponentialDelayWithoutJitter(500 ms, 5 s)` for both normal and throttling backoff (v1 `ExponentialBackoffStrategy(500, 5000)` has no jitter), **retry on every exception** (v1 `CustomRetryCondition` always returns true). cloud-sdk `AwsRetryCondition` is not used: it is the legacy SDK 2 `RetryPolicy` API and cannot be passed to `BaseAwsConfig.retryStrategy(RetryStrategy)`. Circuit breaker (retry token bucket) left at the SDK default, comparable to v1's default throttled retries

**Reason.** Same retry behaviour as v1; fits the factories

<a id="d17"></a>
### D17 · HTTP transport per client (2026-10-31)

**Decision.** HTTP transport per client via `AwsHttpClientWrapper.ofSyncBuilder(ApacheHttpClient.builder()…)` (connect 1 s; socket 5 s, listener 50 s; max connections 50); builder mode, so each SDK client owns and closes its own pool

**Reason.** Same per-role connection settings as v1; the cloud-sdk default transport (connect 5 s, socket 30 s) differs

<a id="d18"></a>
### D18 · AbstractTask picks the process method once (2026-10-31)

**Decision.** `AbstractTask` picks the `process` method by checking once whether the subclass overrides the `QueueMessage` one, rather than bridging every call

**Reason.** A v1 task keeps receiving the original `Message` instance (existing tests and code may rely on identity or on fields the bridge does not carry, e.g. MD5s); avoids mutual recursion between two default methods

<a id="d19"></a>
### D19 · v2 dispatcher method named dispatch (2026-10-31)

**Decision.** The v2 dispatcher method is named `dispatch` and keeps that name after step 5

**Reason.** `submit(List<Message>)` and `submit(List<QueueMessage<String>>)` have the same erasure; a permanent new name avoids a second rename in ingestor and watermill-publisher

<a id="d20"></a>
### D20 · Both metered execute methods share one run (2026-10-31)

**Decision.** Both metered `execute` methods share one private `run` method

**Reason.** Guice AOP intercepts self-calls (generated subclass), so calling the public v2 method from the v1 one would double-count `messages-processed`

<a id="d21"></a>
### D21 · Type witnesses for ambiguous any()/null in tests (2026-10-31)

**Decision.** The `QueueMessage` overloads make untyped `any()` / `null` arguments ambiguous in existing tests; the shared PR adds a type witness at each such call site — `ArgumentMatchers.<Message>any()` (still matches `null`, unlike `any(Message.class)`) or `(Message) null` — and changes nothing else in those tests. 20 sites so far: shared `AsyncDispatcherTest` (2, `any(Message.class)`; arguments are never null there), shared `ErrorHandlerTest` (2), ingestor `ErrorHandlerTest` (6), splitter `SplitErrorHandlerTest` (9), transformer `TransformerTaskTest` (1)

**Reason.** Keeps the reactor compiling with unchanged test meaning; the module PRs later move those tests to `QueueMessage` anyway

<a id="d23"></a>
### D23 · Stress environment ignored (2026-10-31)

**Decision.** The stress environment is not used and is ignored: no fix for its incomplete `network-services.properties` ([F6](closed-items.md#f6)). `ConfigResolutionGoldenTest` keeps its stress cases (they still prove "both resolvers fail the same way"); they may be dropped from the test later without loss

**Reason.** User decision

<a id="d24"></a>
### D24 · Listener receives min(idle workers, 10) (2026-11-09)

**Decision.** The v2 listener asks for `min(idle workers, 10)` per receive (`9a05bdc5` red, `0dc30210` green)

**Reason.** PR #80 review comment. The reviewer's premise was wrong: there are no 20–50 worker defaults, pools = `maxNumberOfMessages` ≤ 10, so no current config breaks, and v1 `SQSListener` has the same unclamped code. But SQS rejects > 10 with `InvalidParameterValue` and neither cloud-sdk nor v1 clamps, so an override above 10 would break every receive. The cap costs nothing and changes no current request. User decision

<a id="d25"></a>
### D25 · Naming rule: cloud-sdk-api concept names (2026-11-17)

**Decision.** **Naming rule** ([rules](rules.md)): client code uses cloud-sdk-api concept names, not AWS names (PR #80 review, Arijit). Applied retroactively to 1c in the 1d branch: `CloudSdkSQSListener` → `MessageQueueListener` (+ test), `SQS_MAX_MESSAGES_PER_RECEIVE` → `MESSAGING_QUEUE_MAX_MESSAGES_PER_RECEIVE`, `CloudSdkFailures` → `CloudServiceFailures` (`isCloudSdkFailure` → `isCloudServiceFailure`; test `CloudSdkExceptionMappingTest` → `CloudServiceFailuresTest`), `ClientSettings.sqsListener/sqsSender/s3/sns` → `messageQueueListener/messageQueueSender/storage/notification`, `ClientProfile.sqs/s3/sns` → `messaging/storage/notification`. Log texts kept as v1. **1d names (confirmed by Arijit 2026-11-17)**, replacing the `shared` design page's test plan names: workspace adapter `StorageWorkspaceService` (test was `CloudSdkWorkspaceServiceTest`), message queue sender `MessageQueueClient` (was `CloudSdkSQSClient`), notification publisher `NotificationEventPublisher` (was `CloudSdkSnsEventPublisher`), parameter supplier `CloudParameterSupplier` (was `CloudSdkParameterSupplier`, matches cloud-sdk-api `CloudParameterStore`), health checks `StorageReadHealthCheck` / `InboundMessageQueueHealthCheck` (registered check names unchanged), Guice module `CloudServicesModule`

**Reason.** Client applications stay implementation-agnostic: AWS is reached only through cloud-sdk-aws, so AppianWay names follow cloud-sdk-api. Renames are `refactor` commits (behaviour and tests unchanged), no extra sub-PR

<a id="d26"></a>
### D26 · WorkspaceService puts return void (2026-11-17)

**Decision.** `WorkspaceService` put methods return `void` instead of the SDK v1 `PutObjectResult` (`94a264a2`, before the adapter). The v1 `S3WorkspaceService`, its test and the transformer test double `InboundTransformationTest` follow. `StorageWorkspaceService.copyS3FileToFileSystem` reads the body with one GET and writes it to the file; it does not stream from the socket as v1 did

**Reason.** Shared design open issue 8 (SDK-neutral signatures replace the v1 ones). No production code uses the return value (checked: no chained call, assignment or mock stub in any module), so this saves a second change in step 5. Streaming would need the cloud-sdk transfer manager (a separate async client); `copyS3FileToFileSystem` has no caller outside `shared`

<a id="d27"></a>
### D27 · MessageQueueClient with SQSClient extending it (2026-11-17)

**Decision.** Transition of the message queue sender: v2 `MessageQueueClient` (on the sender-role `MessagingClient<String>`, `@Named("messageQueueSender")`) is the type `shared` and the services use; until step 5 the v1 `SQSClient extends MessageQueueClient` and overrides every method with the unchanged v1 code. `AbstractTask` and `ErrorHelper` take a `MessageQueueClient`; `@ImplementedBy(SQSClient.class)` on it gives a service still on SDK v1 its own `SQSClient` singleton; the v2 module binds `MessageQueueClient` explicitly. Each module PR changes its `SQSClient` references to `MessageQueueClient`. Step 5 deletes `SQSClient`, the annotation and the protected no-argument constructor

**Reason.** User decision (Arijit, 2026-11-17, option "v1 extends v2"; alternatives were a permanent `shared` interface, or one `SQSClient` class with two constructors that would keep the AWS name against [D25](#d25)). About 40 production classes in 15 modules use `SQSClient`; no extra type remains after step 5

<a id="d28"></a>
### D28 · StorageReadHealthCheck keeps the GET of anykey (2026-11-17)

**Decision.** `StorageReadHealthCheck` keeps the v1 GET of `anykey` and treats only a missing **key** as healthy, decided by the AWS error code `NoSuchKey` in the cause chain (`CloudServiceFailures.isMissingStorageKey`, core `AwsServiceException`, no S3 model type in main code). Not `objectExists` (HEAD)

**Reason.** v1 matched the text "The specified key does not exist"; cloud-sdk words it differently (design item 13: decide by type). A HEAD answers 404 for a missing bucket too, so a deleted bucket would look healthy; the GET tells `NoSuchKey` from `NoSuchBucket`. The classification lives next to the other AWS exception mapping (C9)

<a id="d29"></a>
### D29 · Parameter store role settings (2026-11-17)

**Decision.** Parameter store role: `ClientSettings.parameterStore()` = connect 10 s, socket 50 s, no API-call timeout, 50 connections, 3 retries, with the AWS **legacy** retry strategy (retryable failures only), not [D16](#d16)'s retry-every-failure

**Reason.** v1 `ParameterStoreModule` built its client with `defaultClient()`, i.e. the plain v1 defaults and `PredefinedRetryPolicies.DEFAULT` (characterized in `51bc70d1`), not an `AWSClientConfiguration` role

<a id="d30"></a>
### D30 · CloudServicesModule shape (2026-11-17)

**Decision.** `CloudServicesModule` shape: explicit inputs `(LifecycleEnvironment, queueUrl, eventTopicArn)` instead of a configuration class; optional event topic (no `NotificationService` / `EventPublisher` without one); `with...Settings(..)` per role for per-service v1 values (OI 12); `withParameters(..)` replaces `ParameterStoreModule`; clients built eagerly at module configuration and closed through `ManagedCloudResource` (the notification service and parameter store are not `CloudResource`s, v1 never closed them either); package-private `CloudClients` seam over the cloud-sdk-aws factories for tests; region and credentials from the AWS default chains (`ClientProfile.fromDefaultChains()`), as the v1 builders

**Reason.** Not every service extends `BaseConfiguration` (ingestor, event-writer, watermill consumers do not); queue URL only because cloud-sdk requires one in the messaging configuration (every call passes its own)

<a id="d31"></a>
### D31 · StorageConfigurationProvider replaces S3ConfigurationProvider (2026-11-17)

**Decision.** `StorageConfigurationProvider` replaces `S3ConfigurationProvider` (in 1d, Arijit 2026-11-17): same switches, key and message; builds its own storage client at bootstrap (before Guice) with the cloud-sdk-aws factory and the v1 `defaultClient()` settings (`configurationStorage` role, like [D29](#d29)), reads with one GET and closes the client. The 11 service applications switch in their own PR; v1 class until step 5

**Reason.** Bootstrap runs before Guice, so the provider cannot use `CloudServicesModule`; v1 also built the client inside `open` and never closed it

<a id="d32"></a>
### D32 · Storage has two roles (download without timeout) (2026-11-17)

**Decision.** Storage has **two roles**: `storage()` keeps v1's 10 s API-call timeout for PUT, COPY and HEAD; `storageDownload()` has none, for the GETs that read the body (`getContent`, `getS3ObjectWrapper`, `getS3InputStream`, `copyS3FileToFileSystem`). Corrects the storage half of `80c2ec9c` (U11)

**Reason.** PR #2 review (Copilot), agreed by Arijit (option A). v1's 10 s ran until S3 answered: for a GET that is the headers (body read outside), for PUT/COPY/HEAD the whole request. [DR-2](#dr-2) had analysed only downloads. Per-request timeouts are not possible with cloud-sdk `StorageClient`; cost: one more storage client (pool 50) per service

<a id="d33"></a>
### D33 · Cloud-sdk fakes keep the test-facing APIs (2026-11-17)

**Decision.** Cloud-sdk fakes keep the existing test-facing APIs: `FakeQueue implements MessagingClient<String>, FakeSQS`; `FakeStorage implements StorageClient` with an `asFakeS3()` view (Java forbids both interfaces on one class: `putObject(String,String,String)` returns `PutObjectResult` in `FakeS3`, `void` in `StorageClient`). Receives wait at most 1 s; delays are recorded, not applied

**Reason.** Services switch fakes without rewriting `SqsAssert` / `S3Assert` checks; tests stay fast

<a id="d34"></a>
### D34 · Boundary test on ArchUnit core (2026-11-17)

**Decision.** The boundary test (shared test plan 9) is `AwsSdkBoundary` in functional-testing on **ArchUnit core** only, called from a plain JUnit 5 test (`AwsSdkBoundary.check(packages)`), not `@ArchTest`

**Reason.** `archunit-junit5` 1.3.0 brings an older JUnit Platform engine than Jupiter 5.12 needs (surefire fork failed: `OutputDirectoryProvider` missing). `check` reads main classes only and fails on an empty import. `shared` applies it in step 5. **Update 2026-11-18:** after [D35](#d35) the bom would line up `archunit-junit5`'s Platform version anyway. Core stays because services call the rule from a plain JUnit 5 test and need no `@ArchTest` runner (item 6 of the PR #3 description says so)

<a id="d35"></a>
### D35 · functional-testing imports junit-bom 5.14.4 (2026-11-18)

**Decision.** functional-testing (no parent) imports `org.junit:junit-bom` **5.14.4**, the version the reactor gets from the Dropwizard 5.0.2 BOM. It declares `junit-jupiter-api` (compile, used by its main code) and `junit-jupiter-engine` (test) without versions, and pins Surefire **3.2.5**, the same as the root pom. Guarded by `FunctionalTestingLibraryVersionsTest`: the `Bundle-Version` of the Jupiter and Platform classes, and XPath checks of the pom against `../pom.xml`

**Reason.** PR #3 review R1. Before, Jupiter 5.12.2 came only through Jersey's test framework, and Surefire was Maven's default (Maven 3.8 → 2.12.4, which has no JUnit Platform provider and would skip every Jupiter test). A first fix pinned 5.12.2; it was redone at 5.14.4 to match the services (Arijit). The module manages its own bom, as commons does, instead of leaving it to Dropwizard

<a id="d36"></a>
### D36 · FakeQueue peek with visibility 0 (2026-11-18)

**Decision.** `FakeQueue.receiveMessages` with a request visibility of 0 leaves the messages in the queue (peek); other receives take them. The wait follows `waitTimeSeconds`, at most 1 s ([D33](#d33)). A message received but not deleted is still never redelivered

**Reason.** PR #3 review R2. SQS never deletes on receive, and visibility 0 keeps the message visible; `InboundMessageQueueHealthCheck` relies on that (U5). The v1 `FakeSQSImpl` has the same simplification and stays as is until step 5

<a id="d37"></a>
### D37 · event-writer: ExternalServicesModule deleted (2026-11-18)

**Decision.** event-writer: `ExternalServicesModule` is deleted, not turned into a wrapper. `EventWriterApplication()` (production) builds `CloudServicesModule(lifecycle, pickup queue URL, no topic)` in `run`, because the module needs the configuration and the lifecycle. `EventWriterApplication(Module)` takes the bindings to use instead (functional tests: `cloudBindings(null)`). No `with...Settings`: the v1 clients used exactly the role defaults

**Reason.** The design (item 1) said "installs the shared v2 module"; with nothing else to bind, a wrapper would add a class and a second constructor parameter. Services with their own bindings (DynamoDB, SES) keep an `ExternalServicesModule` for those

<a id="d38"></a>
### D38 · error-processor keeps ExternalServicesModule (2026-11-18)

**Decision.** error-processor keeps an `ExternalServicesModule` (unlike event-writer, [D37](#d37)): it installs `CloudServicesModule` and binds `Clock`, which the functional tests replace with the fixed clock of `cloudBindings`. Storage (both roles) and notification use `ClientSettings.parameterStore().withMaxRetries(0)` (connect 10 s, socket 50 s, no API-call timeout, 50 connections, 0 retries) = v1 `new ClientConfiguration().withMaxErrorRetry(0)`, proven against the v1 class by `ExternalServicesModuleTest`

**Reason.** Design open issue 3: keep today's values. The default `ClientConfiguration` retry policy honours `maxErrorRetry`, so v1 really retried 0 times

<a id="d39"></a>
### D39 · dispatcher: withParameters, no pass-through, no overrides (2026-11-19)

**Decision.** dispatcher: `ExternalServicesModule(configuration, lifecycle)` installs `CloudServicesModule(lifecycle, pickup, topic).withParameters(clientId, clientSecret)`, no pass-through and no `with...Settings`

**Reason.** v1 built `ParameterStoreModule(clientId, clientSecret)` and ignored `networkServiceConfig.usePassThrough` (distributor and transformer pass it; dispatcher never did). The four v1 clients used exactly the role defaults, and the v1 SSM client the plain defaults (= `ClientSettings.parameterStore()`)

<a id="d40"></a>
### D40 · dispatcher parser keeps two v1 edge cases (2026-11-19)

**Decision.** dispatcher `S3EventParser` on the cloud-sdk-api model keeps two v1 edge cases explicitly: a record without a key fails the parse (`requireNonNull` on `getUrlDecodedKey()`, which would return null), and a missing event time prints the time of parsing in the JVM zone (`ZonedDateTime.now()`)

**Reason.** Both were characterized on v1 first. Without them, a keyless notification would go to the error queue instead of staying on the queue, and a timeless one would fail instead of being processed

<a id="d41"></a>
### D41 · dispatcher golden test sends LF inputs (2026-11-19)

**Decision.** dispatcher golden test: inputs are sent with LF line breaks; only the `MetaData` message id is normalized

**Reason.** Pre-review point 9: normalizing CRLF in the output would hide a line-break change on the wire. The fixtures are CRLF in a Windows checkout (`core.autocrlf=true`), LF in git and CI

<a id="d42"></a>
### D42 · dispatcher drops its direct SQS v1 dependency (2026-11-19)

**Decision.** dispatcher drops its direct `aws-java-sdk-sqs` dependency in its PR (not in step 5)

**Reason.** `shared` brings it at the same 1.12.730, so nothing changes (unlike email-sender's SES pin, where removal would downgrade). The design page lists it as removed

<a id="d43"></a>
### D43 · Known existing defects are not fixed in this program (2026-11-20)

**Decision.** None of the known defects ([KD-1 to KD-11](known-defects.md)) is fixed in this program; they keep their disabled tests (Arijit, on PR #8)

**Reason.** No one has reported any of them. It confirms review summary decision 4 and [A12](actions.md#a12)

<a id="d44"></a>
### D44 · splitter's golden test runs with one pickup worker (2026-11-20)

**Decision.** `SplitterWireCompatibilityTest` uses its own properties file with `maxNumberOfMessages=1`; the other functional tests keep ten workers (`e36bc10f`)

**Reason.** Copilot on PR #8: the fake queue delivers a retry at once, so with ten workers a retry could publish before its first attempt had finished, and the golden test compares the event order. A `ConfigOverride` was not used: it sets a JVM-wide system property that would leak into the later test classes


<a id="d45"></a>
### D45 · transformer drops the AWS SDK CloudWatch metrics (2026-11-20)

**Decision.** The new build removes `AwsSdkMetrics.enableDefaultMetrics()` and publishes no `AWSSDK_{environment}_{componentName}` metrics (Arijit). No `shared` metrics helper, no `cloudwatch-metric-publisher` dependency. The design's open issue 3 and `shared` open issue 13 are superseded; [A9](actions.md#a9) (dashboards) no longer applies

**Reason.** QA receives 74 such metrics (`AWSSDK_qa_transformer`: SQS, S3, SNS, DynamoDB, JVM), but nothing in the account uses them: `describe-alarms` shows no alarm on any `AWSSDK*` namespace, and the one transformer dashboard (`BK_Transformer_Performance`) charts log queries only. The account also hosts CVT and production, so this covers them too. SDK 2.x has no global switch and commons has no metric-publisher option yet (U7); SDK 2.x metric names differ anyway. They can be added back once commons ships U7

<a id="d46"></a>
### D46 · Watermill consumers may advance QA's offsets in runtime tests (2026-11-20)

**Decision.** A consumer run locally against QA may use QA's consumer id and offset rows, and so advance QA's Watermill offsets and take events from the QA consumer (Arijit). A separate consumer id is not needed.

**Reason.** QA only, and the events go on to the same QA flow. Asked in the [step 4 plan](steps/step-4-plan.md#decisions-for-arijit-before-the-runtime-tests).

<a id="d47"></a>
### D47 · QA DynamoDB writes allowed for runtime tests (2026-11-20)

**Decision.** Runtime tests may write to QA DynamoDB tables (offset rows, consumer tables) as each test needs (Arijit). No table or setting changes: data only, as the standing environment rule.

**Reason.** As the Elasticsearch writes of test 7: the writes the service itself makes in QA.

<a id="d48"></a>
### D48 · watermill-publisher verified up to the publish call only (2026-11-20)

**Decision.** Nothing is published to the e2open Watermill staging broker (Arijit). The runtime test runs watermill-publisher locally against QA up to the publish call, which is captured instead of sent; the publish itself is covered by the golden test.

**Reason.** The broker is an external e2open system.

<a id="d49"></a>
### D49 · billoflading consumers are in scope (2026-11-20)

**Decision.** `watermill/billoflading` (ebl- and registration-inbound consumers) is part of this program, as wave 4d (Arijit).

**Reason.** They use SDK v1 and DynamoDB like the other consumers; step 5 cannot remove SDK v1 from `shared` while they depend on it.

---


Each record keeps the question as asked, a plain explanation, the options, the answer and the follow-up. The short form is in [decisions](decisions.md).

<a id="dr-1"></a>
### DR-1 (2026-10-31) — How `shared` takes the commons dependency → D7

**Question:** the `commons` artifact also brings mysql-connector-java, MyBatis, Apache POI, Jest 5.3.3, dropwizard-db/forms, bucket4j and compile-scope junit; AppianWay uses none. Exclude them, take commons as-is, or depend only on cloud-sdk?
**Answer:** exclude the unused ones. **Follow-up:** done in step 1b (`9a704fb0`); re-check the exclusion list whenever the commons version changes.

<a id="dr-2"></a>
### DR-2 (2026-10-31) — API-call timeout for the S3 and SQS-listener clients → D13

**What an "API-call timeout" is.** It is the longest time one AWS SDK call may take end to end, including its retries. In SDK 2.x (`apiCallTimeout`) it also covers reading the response body, because cloud-sdk's `getContent` / `getObject` read the whole object inside the call. It is different from the **socket timeout**, which only fires when the connection stays silent (no bytes) for that long.

> **Correction 2026-11-17 ([D32](#d32), PR #2 review):** this record looked only at downloads. v1's 10 s also covered PUT, COPY and HEAD in full, so storage now has two clients: downloads without an API-call timeout, everything else with 10 s.

**What happens today (SDK v1).**

| Client | v1 setting | Effect |
|---|---|---|
| S3 | `clientExecutionTimeout` 10 s, socket 5 s | The 10 s clock stops once S3 has *started* answering; reading a large document's body afterwards has no total limit. It only fails if the stream stalls for 5 s |
| SQS listener | no execution timeout, socket 50 s | A 20 s long poll can never be cut short |
| SQS sender, SNS | 10 s execution, socket 5 s | Small requests; 10 s total is ample |

**Why v1's 10 s never cut off a large read, but a v2 cap would.** Both SDKs call the setting a call timeout; what differs is *where the body is read*:

- **SDK v1 (today):** `shared` `S3WorkspaceService` calls `s3Client.getObject(...)`, which returns as soon as S3 sends the response headers; the 10 s clock covers only that call. The body is then read by `shared`'s own code (`read(s3object.getObjectContent())`, `IOUtils.toByteArray(...)` — `S3WorkspaceService.java:150-189`), outside the SDK call, so it is not timed.
- **SDK 2.x via cloud-sdk:** `S3StorageClient` reads the body *inside* the SDK call — `getObjectAsBytes(...)` and `getObject(request, ResponseTransformer.toBytes())` (`S3StorageClient.java:364, 553, 845`); the call returns only when every byte has arrived, and the API-call timeout covers the whole call including the download.

So the same-named limit measures something larger in v2: with a 30 s cap a document that takes 35 s to download fails in v2 but works in v1.

**Why the design asked for "no API-call timeout".** S3: exactly the point above — copying v1's 10 s (the obvious mapping) would cap the whole download, so the design chose no cap and left stalls to the 5 s socket timeout, as in v1. SQS listener: v1 `sqs_listener` sets no execution timeout at all (a receive is bounded only by the 20 s long poll and the 50 s socket timeout), so "none" was simply today's behaviour. That the factories cannot express "none" was found only in step 1c.

**The problem.** The design said "no API-call timeout" for S3 and the listener, but the cloud-sdk factories cannot express "none": they always set one (S3 30 s, SQS 30 s, SNS 10 s, SSM 10 s), and zero is rejected. With a 30 s cap on S3, reading a large document that keeps flowing but takes over 30 s (big EDI files, slow network, an ECS task under load) would **fail where it works today** — the task then raises `RecoverableException`, the message is retried with delay and can end in the DLQ. For the listener, 30 s leaves little margin over a 20 s long poll plus one retry.

**Options.**

| Option | Meaning | Trade-off |
|---|---|---|
| A. Generous cap through the factories (**chosen**) | S3 **10 min**, SQS listener **60 s**; sender and SNS stay 10 s | Stays inside the AWS SDK boundary rule (clients only from cloud-sdk factories). Practically the same as today: a stall is still caught by the socket timeout (5 s / 50 s); only a transfer that keeps trickling bytes for over 10 minutes would be stopped |
| B. Build the SDK clients in `shared` and wrap them | Use the public cloud-sdk-aws constructors with no API-call timeout | Exact v1 parity, but widens the exception to the boundary rule (today only for transformer metrics) |
| C. Factory defaults (30 s) | Nothing configured | Simplest, but not backward compatible for large documents |

**Your answer:** A — generous cap via the factories.

**Follow-up actions.**

| # | Action | Where | Status |
|---|---|---|---|
| 1 | Encode the caps in the client-profile settings (S3 10 min, listener 60 s, sender / SNS 10 s), each with a comment naming the v1 setting it replaces | Step 1c, `ClientSettings` | In progress |
| 2 | Correct the `shared` design page Client Profile table ("none" → the caps) in the batched post-publish edit | [A21](actions.md#a21) | Open |
| 3 | Ask commons to allow "no API-call timeout" in the factory configs; once released, switch S3 / listener to it | [A22](closed-items.md#a22) | Open |
| 4 | On INT, confirm the largest workspace documents read well within 10 minutes (expected: seconds) | [A23](closed-items.md#a23) | Open |

<a id="dr-3"></a>
### DR-3 (2026-10-31) — Client settings: today's real v1 values or the design table → D14

**What was found.** Reading `shared` `AWSClientConfiguration` against the SDK v1 source showed two values in the published Client Profile table that do not match what runs today:

1. **SNS retries.** The code says `sns_publish ... .withMaxErrorRetry(2)`, so the design table says 2. But every client also gets `.withRetryPolicy(retryPolicy)`, and that policy is built as `new RetryPolicy(condition, backoff, 3, false)`. The last argument, `honorMaxErrorRetryInClientConfig = false`, tells SDK v1 to **ignore** `withMaxErrorRetry(...)` and use the policy's own number, **3**. So SNS publishing today makes up to 4 attempts (1 + 3 retries), like SQS and S3.
2. **SQS listener socket timeout.** `sqs_listener` sets connection timeout and max connections but **no socket timeout**, so SDK v1's default applies: **50 s**. The design table says 30 s (chosen because it must exceed the 20 s long poll). Both are above 20 s; 50 s is what production uses.

**Why it matters.** Backward compatibility is the rule for this program. With the design values, a failing SNS publish would give up after 3 attempts instead of 4 (SNS failures are logged and processing continues, so the visible difference is one fewer retry and about 2 s less waiting before the log line), and the listener would drop a silent connection after 30 s instead of 50 s. Small, but a change nobody asked for.

**Options:** follow today's real values (**chosen**), or the design table.

**Your answer:** today's real values — SNS 3 retries, listener socket 50 s.

**Follow-up actions.**

| # | Action | Where | Status |
|---|---|---|---|
| 1 | Encode SNS 3 retries and listener socket 50 s in `ClientSettings`, with comments | Step 1c | In progress |
| 2 | Add a characterization test that reads the **v1** `AWSClientConfiguration` objects (still on the classpath until step 5) and proves the facts above: policy max retries 3, `isMaxErrorRetryInClientConfigHonored() == false`, listener socket timeout = v1 default 50 s. It is the evidence for the reviewers and is deleted with the v1 code in step 5 | Step 1c | Open |
| 3 | Correct the design page Client Profile table (SNS 2 → 3, listener socket 30 s → 50 s) in the batched post-publish edit | [A21](actions.md#a21) | Open |

<a id="dr-4"></a>
### DR-4 (2026-10-31) — Carrying v1 and v2 task signatures during the transition → D15

**Question:** every module's `Task` / `TaskFactory` / `Dispatcher` / `AbstractTask` / `ErrorHandler` uses the v1 `Message`; modules migrate one PR at a time. Overloads on the same classes, or a parallel v2 package?
**Answer:** overloads on the same classes (`QueueMessage<String>`); step 5 deletes the v1 methods. **Follow-up:** implemented in step 1c; each module PR switches its tasks to the v2 overloads.
