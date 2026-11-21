# Step 1c — shared runtime (`WI01124532-aws-sdk-upgrade-shared-runtime`)

← [Tracker home](../README.md) · [All steps](README.md)


Stacked on `WI01124532-aws-sdk-upgrade-shared-config` ([D6](../decisions.md#d6)). Decisions [D13](../closed-items.md#d13)–[D17](../decisions.md#d17), [DR-2](../decisions.md#dr-2)–[DR-4](../decisions.md#dr-4).

> **Renamed in 1d ([D25](../decisions.md#d25), 2026-11-17).** This log keeps the 1c names as merged: `CloudSdkSQSListener` is now `MessageQueueListener`, `CloudSdkFailures` is now `CloudServiceFailures`, and the `ClientSettings` / `ClientProfile` role methods use messaging / storage / notification names.

**Plan (TDD cycles):**

| Cycle | Scope |
|---|---|
| A | `ClientSettings` (per-role values = today's v1) + `ClientProfile` (cloud-sdk SQS / S3 / SNS configs, retry strategy, HTTP transport); direct `cloud-sdk-api` / `cloud-sdk-aws` dependencies |
| B | v2 overloads on the task model (`Task`, `TaskFactory`, `Dispatcher`, `TaskMessage`, `AsyncDispatcher`, `AbstractTask`) typed on `QueueMessage<String>` ([D15](../decisions.md#d15)) |
| C | Back-pressure listener on `MessagingClient<String>`: receive at most the idle-worker count, `failedAttempts` requested, no visibility timeout, wait for a free worker instead of spinning |
| D | cloud-sdk exception → `RecoverableException` mapping (C9) |

**Key classes (cycle A):**

| Class | Role | Important methods |
|---|---|---|
| `com.inttra.mercury.shared.config.ClientSettings` (new record) | Per-role HTTP and retry values: `connectionTimeout`, `socketTimeout`, `apiCallTimeout`, `maxConnections`, `maxRetries` | `sqsListener()` 1 s / 50 s / 60 s / 50 / 3; `sqsSender()` 1 s / 5 s / 10 s / 50 / 3; `s3()` 1 s / 5 s / 10 min / 50 / 3; `sns()` 1 s / 5 s / 10 s / 50 / 3; `withMaxRetries`, `withTimeouts` for per-module overrides (error-processor etc., [D6](../decisions.md#d6) of the review) — each value commented with the v1 setting it keeps |
| `com.inttra.mercury.shared.config.ClientProfile` (new) | Turns `ClientSettings` into cloud-sdk configs for the factories; the only AppianWay class touching AWS SDK configuration types | `sqs(settings, queueUrl)` → `AwsMessagingClientConfig` (also sets the builder-required `maxMessages(10)`, unused by the factory); `s3(settings)` → `AwsStorageConfig`; `sns(settings, topicArn)` → `NotificationClientConfig`; `retryStrategy(maxRetries)` — SDK standard strategy, `maxAttempts = retries + 1`, `exponentialDelayWithoutJitter(500 ms, 5 s)`, `retryOnException(any)` ([D16](../decisions.md#d16)); private `httpClient(settings)` — `AwsHttpClientWrapper.ofSyncBuilder(ApacheHttpClient.builder()…)` ([D17](../decisions.md#d17)) |

**Tests (cycle A):**

| Test class | Cases |
|---|---|
| `V1ClientConfigurationCharacterizationTest` (evidence, removed in step 5) | every v1 role: policy max retries 3 and `isMaxErrorRetryInClientConfigHonored() == false` (SNS's configured 2 unused); retry condition true for a 403; backoff 500 / 1000 / 2000 ms, capped 5000; listener socket = v1 default 50 000 ms, no execution timeout; sender / S3 / SNS 1 s / 5 s / 10 s / 50 |
| `ClientSettingsTest` | the four role defaults; `withMaxRetries`; `withTimeouts` |
| `ClientProfileTest` | SQS / S3 / SNS configs carry the role values (call timeout, max connections, 4 attempts, region, credentials, sync transport, topic, queue); retry strategy on a non-retryable-looking failure gives delays 500 ms → 1 s → 2 s, then `TokenAcquisitionFailedException`; 0 retries = 1 attempt |

**Commits:**

| # | Commit | Type | Result |
|---|---|---|---|
| 1 | `97987059` WI01124532 test: characterize the SDK v1 client settings used today | test | 5/5 pass (records existing behaviour; [DR-3](../decisions.md#dr-3) follow-up 2 done) |
| 2 | `baa97bb3` WI01124532 red: client profile must reproduce today's v1 client settings | red | 11/11 fail on stubs |
| 3 | `72de727b` WI01124532 green: client profile builds cloud-sdk configs with today's v1 settings | green | Full reactor green (7:39 min); counts unchanged except `shared` +16 |
| 4 | `b951a796` WI01124532 red: task model must accept cloud-sdk QueueMessage alongside the v1 Message | red | 14 of 15 new tests fail on stubs; existing `AsyncDispatcherTest` gets a type witness (`any(Message.class)`) because the overloads make `any()` ambiguous |
| 5 | `d5f78da3` WI01124532 green: task model processes cloud-sdk QueueMessage alongside the v1 Message | green | Full reactor green (8:04 min); all 8 `AbstractTask` services' tests pass unchanged; `shared` +16 |
| 6 | `a852d843` WI01124532 red: error handling must accept cloud-sdk QueueMessage alongside the v1 Message | red | 11/11 new fail on stubs; 18 call sites in existing tests get a type witness ([D21](../decisions.md#d21)) |
| 7 | `b3d10949` WI01124532 green: error handling processes cloud-sdk QueueMessage alongside the v1 Message | green | Full reactor green (6:42 min); counts unchanged except `shared` +11 |

**Cycle B2 details — `ErrorHelper` / `ErrorHandler`:**

| Class | v2 members | Notes |
|---|---|---|
| `task.errorhandler.ErrorHelper` | `getFailedAttempts(QueueMessage<String>)` (String attribute `failedAttempts`, absent → 0), `isRecoverableAttemptsNotMaxed(QueueMessage)`, `sendBackToPickupQueue(QueueMessage, queue)` and `(QueueMessage, MetaData, queue)`, `sendToDLQ(QueueMessage, queue)`, `sendToQueue(QueueMessage, queue)` | Thin; share the existing private `sendToPickupQueue` / `calculateDelay` and a new private `sendBodyToDLQ`, so delay `2^attempt × multiplier`, `failedAttempts + 1`, tokens and log lines are identical |
| `task.ErrorHandler` | `@Metered handleException(QueueMessage<String>, …)` | The logic lives in private methods over a private `FailedMessage` view (body, attempts-not-maxed, send-back, DLQ) with one implementation per message type, so each path calls the `ErrorHelper` overload of its own type. The v1 `handleException` keeps its original call path through the protected hooks (`handleRecoverableException`, `publishCloseRunEvent`, `handleNonRecoverableException`), which now delegate to the private methods. No subclass in the repo overrides a `Message`-typed method (they override `getErrors()` only) |

**Cycle C — back-pressure listener:**

| # | Commit | Type | Result |
|---|---|---|---|
| 8 | `52c36758` WI01124532 red: back-pressure listener on the cloud-sdk MessagingClient | red | 10 of 12 new fail on stubs (the two that pass do so only because the stub's thread dies at once) |
| 9 | `0b8df5d2` WI01124532 green: listener waits for a free worker and receives through cloud-sdk | green | Full reactor green (7:09 min); counts unchanged except `shared` +12 (now 1683); the 4 timing-sensitive classes repeated 5× without a failure |

| Class | Change | Important methods |
|---|---|---|
| `listener.CloudSdkSQSListener` (new; replaces `SQSListener` in step 5) | Same loop as `SQSListener` on `MessagingClient<String>` | `startup()`: while not stopped — `dispatcher.awaitIdleWorker(1 s)`; if a worker is free, `receiveMessages(queueUrl, maxMessages = getIdleThreadCount(), waitTimeSeconds, messageAttributeNames = [failedAttempts])` and `dispatcher.dispatch(...)` when not empty; `InterruptedException` → stop; any other `Throwable` logged ("Exception in SQS Listener :") and the loop continues, as today. No visibility timeout is sent (cloud-sdk never sends it — verified in `SqsMessagingClient`), so the queue default applies, as today. Same start / shutdown log lines. `shutdown()` sets the stop flag; constructor rejects an empty queue URL, as today |
| `threaddispatcher.Dispatcher` | `default awaitIdleWorker(Duration)` | Returns at once if a worker is idle, otherwise sleeps `min(timeout, 50 ms)` — for dispatchers without a pool (ingestor, watermill-publisher) |
| `threaddispatcher.AsyncDispatcher` | `awaitIdleWorker(Duration)` | `semaphore.tryAcquire(timeout)` then `release()`: blocks until a worker finishes, takes nothing (`dispatch` takes the permit) |

**Behaviour versus `SQSListener`:** same receive sizes, attribute, wait time, dispatch and error handling; the only difference is that when every worker is busy the thread now blocks on the dispatcher's semaphore instead of calling `getIdleThreadCount()` in a tight loop (one CPU core per service saved while busy). Worker pools equal `sqsPickupConfig.maxNumberOfMessages` in every service, so the idle count never exceeds the SQS limit of 10 today. A cap at 10 was added on 2026-11-09 after the PR #80 review ([D24](../decisions.md#d24)).

**Cycle D — cloud-sdk exception mapping (C9):**

| # | Commit | Type | Result |
|---|---|---|---|
| 10 | `5a2d0e21` WI01124532 red: cloud-sdk failures must map to RecoverableException as the v1 wrappers did | red | 23/23 new fail on the stub |
| 11 | `d2ce0f82` WI01124532 green: cloud-sdk failures map to RecoverableException by exception type | green | Full reactor green (8:57 min); counts unchanged except `shared` +23 (now 1706) |

| Class | Role | Important methods |
|---|---|---|
| `externalwrapper.exception.CloudSdkFailures` (new) | The single C9 mapping the 1d adapters call: `catch (RuntimeException e) { throw CloudSdkFailures.toRecoverable(e); }` | `isCloudSdkFailure(Throwable)`: `CloudSdkException` (SQS `MessagingException`, SNS `NotificationException`), `ParameterStoreException`, `S3OperationException`, `S3UploadException`, `FileTransferException`, `StorageClientInitializationException`, or anything that is / is caused by an AWS SDK v2 `SdkException` (raw leaks, e.g. reading the S3 response stream, and the bare `RuntimeException` of the S3 string upload). `toRecoverable(RuntimeException)`: `new RecoverableException(failure)` (same constructor and message as v1); any other failure returned unchanged; an existing `RecoverableException` not wrapped again; for `CloudSdkException` logs operation / resource / `isRetryable()` at WARN without narrowing |

**Rebase 2026-11-09:** 1c replayed onto the feature branch's develop merge `34c8fe4e` (commits now `4d097fe5` … `016ffb6e`; own diff unchanged). Full reactor build of `016ffb6e`: **BUILD SUCCESS, 9:54 min**; `shared` 1706 (1 skipped), transformer 665 (5 skipped), other modules unchanged. Ready to push.

**PR #80 review fix 2026-11-09:** cap of 10 messages per receive ([D24](../decisions.md#d24)), `9a05bdc5` red and `0dc30210` green. Full reactor build of `0dc30210`: **BUILD SUCCESS, 12:01 min**; `shared` 1707 (1 skipped), transformer 665 (5 skipped); other modules not re-counted.

**Merged 2026-11-10:** PR #80 → `fa3efede` on the feature branch (head `0dc30210` unchanged).

Notes: second `shared` class referencing an AWS SDK type (`SdkException`), next to `ClientProfile` — justified because v1's catch-all was SDK-typed too. Not mapped on purpose: client-side `IllegalArgumentException` (`delaySeconds` > 900 → 1d SQS sender adapter), `SendEmailException` / `TemplateProcessingException` (email-sender step, U8/U9), `DynamoSupportException` (watermill, outside `shared`).

**Tests (cycle D):** `CloudSdkExceptionMappingTest` (23: 10 failure types × {becomes `RecoverableException` with the failure as cause and the v1 message; recognised} — SQS, SNS, non-retryable `CloudSdkException`, SSM, S3 operation / upload / transfer / client init, raw SDK v2, S3 string upload; `IllegalArgumentException` unchanged; `UncheckedIOException` with a non-SDK cause unchanged; `RecoverableException` not wrapped again). Design test 7.

**Tests (cycle C):** `CloudSdkSQSListenerTest` (7: request = idle count + `failedAttempts` + wait + queue; received messages dispatched to the pickup queue; empty receive not dispatched; no receive while no worker is free; continues after a `MessagingException`; stops on interrupt; empty queue URL rejected), `AsyncDispatcherIdleWorkerTest` (3: returns at once without taking a worker; times out while all are busy; returns when a worker finishes), `DispatcherIdleWorkerDefaultTest` (2: immediate when idle; pauses instead of spinning).

**Tests (cycle B2):** `ErrorHelperQueueMessageTest` (8: attribute → attempts; absent → 0; not-maxed boundary 4/5; disabled recovery; send-back delay 80 s and attempts 3 with `NEXT_RETRY_TIME` from the fixed clock; with-MetaData variant 20 s / 1; DLQ body unchanged + token; send-to-queue), `ErrorHandlerQueueMessageTest` (3: recoverable with attempts left → pickup queue and close event `status=true` with the payload as body; attempts exhausted → DLQ, `status=false`; non-recoverable → errors queue).

**Cycle B1 details — QueueMessage overloads ([D15](../decisions.md#d15), [D18](../decisions.md#d18)–[D20](../decisions.md#d20)):**

| Class | v2 member (stays after step 5) | v1 member (removed in step 5) |
|---|---|---|
| `task.Task` | `default execute(QueueMessage<String>, String)` — until a task overrides it, bridges to the v1 method | `execute(Message, String)` (still the single abstract method, so lambdas keep working) |
| `task.TaskFactory` | `default getTask(QueueMessage<String>)` — bridges to the v1 method, so the services' `message -> taskProvider.get()` lambdas serve both; the same lambda text compiles against the v2-only interface after step 5 | `getTask(Message)` |
| `threaddispatcher.Dispatcher` | `default dispatch(List<QueueMessage<String>>, String)` — bridges to `submit`; own name because `submit(List<…>)` overloads erase to the same signature ([D19](../decisions.md#d19)) | `submit(List<Message>, String)` |
| `threaddispatcher.AsyncDispatcher` | `dispatch(…)` + `work(QueueMessage<String>, …)`: same semaphore permit per message, same logging, `task.execute(QueueMessage, …)` | `submit`, `work(Message, …)` |
| `task.AbstractTask` | `process(QueueMessage<String>, String)` (abstract in step 5); `@Metered execute(QueueMessage<String>, String)` | `process(Message, String)` (no longer abstract; default throws); `@Metered execute(Message, String)` |
| `task.V1MessageBridge` (new, `@Deprecated`) | — | `toQueueMessage(Message)`, `toV1Message(QueueMessage<String>)`: id, receipt handle, body ↔ payload, system attributes, `SentTimestamp` ↔ `Instant`, String message attributes (`failedAttempts`) |

`AbstractTask` decides once per instance (`overridesQueueMessageProcess(getClass())`, reflection) which `process` method the service implements; each `execute` calls that one, converting only when needed, so a v1 task called by the v1 path receives the **same `Message` instance** as before ([D18](../decisions.md#d18)). Both `execute` methods delegate to one private `run(…)`, because Guice intercepts self-calls through its generated subclass: a v1 `execute` calling the public v2 `execute` would count `messages-processed` twice ([D20](../decisions.md#d20)).

**New tests (cycle B1):** `V1MessageBridgeTest` (4), `TaskQueueMessageOverloadTest` (1), `TaskFactoryQueueMessageOverloadTest` (2), `DispatcherQueueMessageOverloadTest` (1), `AsyncDispatcherQueueMessageTest` (3: each message runs the v2 overload; a worker stays busy until its task ends; a failing task releases its worker), `AbstractTaskQueueMessageTest` (5: process then delete by receipt handle; no delete on failure; v1 task via v2 path; migrated task via v1 path; v1 path does not go through the public v2 `execute`). Fixture `TestQueueMessage` (test sources). `shared` gains `awaitility` (test scope).

**Dependencies (cycle A):** `shared` declares `cloud-sdk-api` and `cloud-sdk-aws` directly, excluding Jest and `aws-signing-request-interceptor` (only ingestor needs them and declares its own: Jest 6.3.1, signer 0.0.16 — checked with `dependency:tree`).
