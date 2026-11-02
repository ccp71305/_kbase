# WI01124532 AppianWay AWS SDK 2.x Redesign — Review Summary and Rationale

> **Date:** 2026-10-30 · **Reviewed set:** the 17 docs in `docs/redesign/` (program, shared, 15 modules) and `docs/2026-10-30-apway-design-update-plan.md`
> **Baseline:** appianway `develop`; mercury-services-commons 1.0.38-SNAPSHOT (`commons`, `cloud-sdk-api`, `cloud-sdk-aws`)
> **Status:** Review complete. All 17 docs edited in place and checked with `convert_design_doc.py` (`self-check: OK`). Nothing published, nothing staged.
> This page is a local working document (it is not one of the pages to publish) and records rationale the published pages deliberately leave out (CVE context, file:line evidence).

---

## 1. The question: keep `shared` with v2 wrappers, or align with commons?

**Answer: keep `shared` (same artifact, same packages) but re-base it on commons, so it stops being a parallel platform.** The Rev 3 draft kept `shared` as a self-managed library that just gained SDK 2.x adapters. That still left AppianWay with its own AWS client builders, its own configuration loader and its own third-party dependency stack, which is exactly the maintenance and CVE burden you wanted to remove. The revised design splits `shared` into three tiers:

| Tier | What | Where it comes from |
|---|---|---|
| 1 | AWS clients and HTTP tuning, retry condition, credentials/region, Parameter Store, DynamoDB, SES, exception model, `CloudResource` lifecycle, **configuration transform chain**, **third-party dependency versions** | commons / cloud-sdk directly. `shared` equivalents are deprecated, then deleted in wave 4 |
| 2 | S3 workspace, SQS sender, back-pressure SQS listener, SNS event publisher, health checks, S3 config source, exception → `RecoverableException` mapping | Thin `shared` adapters over cloud-sdk interfaces, kept only because wire format or runtime behaviour must stay identical |
| 3 | `MetaData` / `Event` / `Annotations` / `Json`, task / dispatcher / `ErrorHandler`, network services, structural validation, XML, external-call wrapper | Unchanged in `shared` (AppianWay domain code) |

### Why not retire `shared` completely and use commons directly

Doing that would break wire compatibility or runtime behaviour in four places (all verified in code):

1. **JSON:** cloud `JsonSupport` registers `Jdk8Module`, sets global `NON_NULL`, writes `LocalDateTime` without `@JsonFormat` as ISO strings (shared `Json` writes arrays) and reads unknown enums as null. `shared` `Json` must stay for every wire payload.
2. **Listener back-pressure:** cloud-sdk `SqsListener` receives a fixed `maxNumberOfMessages` regardless of free workers. `shared` `SQSListener` receives at most `dispatcher.getIdleThreadCount()`. Without that, a busy service holds received messages past their visibility timeout and SQS redelivers them, causing duplicate processing. It also hands the SDK-typed `Message` to callers.
3. **Network services:** the commons package has different models and no caching, message-register or auth-token support.
4. **Task / error model:** every service is built on `AbstractTask` / `ErrorHandler` / `ErrorHelper` (failedAttempts, exponential `DelaySeconds`, DLQ, errors queue); commons has no equivalent.

### What the re-base buys (CVE and maintenance)

- **Dependency versions come from commons.** A concrete problem found: the AppianWay root pom pins Jetty 12.1.9, Jackson 2.21.4, logback 1.5.33 and slf4j 2.0.17 through `<dependencyManagement>`, while commons 1.0.38 ships Jetty 12.1.14, Jackson 2.21.8, logback 1.5.38 and slf4j 2.0.18. **Maven dependency management overrides transitive versions**, so simply adding commons would have *downgraded* the libraries commons already patched (the commons pom notes the Jetty 12.1.13+ fixes for CVE-2026-19863 Critical, CVE-2026-19864 and CVE-2026-76182). Wave 0 now aligns the pins, and acceptance criterion 5 checks the dependency tree. The longer-term fix is a commons BOM (U4), so AppianWay imports it instead of copying pins.
- **Configuration loading matches mercury-services.** commons 1.0.38 already contains `PropertiesSubstitutionConfigProvider`, written for parity with `shared`'s substitution (environment first, then properties, `${k:-default}`, fail fast). Services move to the commons chain `PropertiesSubstitutionConfigProvider → TrimConfigCommentsTransform → ParameterStoreConfigTransform` while keeping today's CLI `run (yaml) (properties...)`, so ECS task definitions and `run.sh` are unchanged. AppianWay also gains `${awsps:...}` like the mercury-services apps (none are introduced now). Proof of no change: a config golden test across every module YAML × every environment's `.properties`.
- **`shared`'s own dependency list shrinks** to what commons does not manage. Still AppianWay-only and end-of-life: Hystrix 1.5.18 + hystrix-dropwizard-bundle + guava-retrying 2.0.0. These are kept as they are for now, because Hystrix is live in the call path: `ExternalCallWrapper` runs every `@ExternalCall` in a `HystrixCommand` with thread-pool isolation and a queue of 20, so replacing it changes concurrency limits. **Recommendation: a separate follow-up design under this WI.** Also, `dropwizard-testing-junit4` is a compile-scope dependency of `shared` and ships in every service jar; it moves to test scope in wave 0.

### Upstream asks to commons (all additive; fallbacks used first; U8–U9 must be in a commons release before the AppianWay release; U7 optional)

| Id | Change | Why | Fallback (interface only) |
|---|---|---|---|
| U1 | A config command with CLI `run (yaml) (properties...)`, YAML from the classpath, properties via the bootstrap provider, and a `(app, name, description)` constructor | The commons `ConfigProcessingServerCommand` is fixed to `server` + one YAML. Ingestor's `create-mapping-template` and transformer's `DynamoTableCommand` extend the config command under other names | ~50-line subclass over the same commons classes |
| U2 | Allow zero-length `putObject` | `AbstractStorageObject.validateContent` / `validateInputStream` reject length 0; SDK v1 wrote empty objects (dispatcher zip entries, splitter, possibly transformer) | `StorageClient.putObject(bucket, key, File, metadata, contentType)` with one empty temporary file (the `File` path does not reject length 0) |
| U3 | Size-only HEAD (content length) | `getMetadata` returns user metadata only; `getObject` downloads the body; splitter reads every split file's size | None kept. **Release prerequisite with U8–U9** (decision 2026-10-30, Option A): keeps today's HEAD, no download |
| U4 | Importable commons BOM | Root pom currently has to copy pins | Copy pins and check with `dependency:tree` |
| U5 | Send `VisibilityTimeout` on receive only when explicitly set | `InboundSqsHealthCheck` probes at visibility 0; cloud-sdk never sends it (the builder default is 30 but unused), so a direct port would hide a real message | Probe with `MessagingClient.getQueueAttributes` instead of a receive (never hides a message; `sqs:GetQueueAttributes`) |
| U6 | Consistent-read flag on the repository scan | Transformer keeps today's consistent scan and "more than one item" guard; `EnhancedDynamoRepository` scans are never consistent | `DatabaseRepository.findById(SequenceId, consistentRead=true)`: same item, same consistency; the "more than one item" error waits for U6 |
| U7 | Factory configs take an optional CloudWatch metrics namespace; commons attaches one SDK `CloudWatchMetricPublisher` | Transformer keeps the SDK CloudWatch metrics (v1 `AwsSdkMetrics` namespace `AWSSDK_{environment}_{componentName}`); the factories accept no metric publisher today | `shared` client-profile helper builds transformer's SDK clients with the same profile plus the publisher and wraps them in the public `cloud-sdk-aws` implementations. **Optional** |
| U8 | `EmailService` returns the SES message id (`EmailSendResult` exists in `cloud-sdk-api`) | email-sender's `CLOSE` event carries it | None. **Must be in a commons release before this release** |
| U9 | `EmailClientFactory` honours a configured `RetryStrategy` | email-sender sends with zero retries today (no duplicate emails) | None. **Must be in a commons release before this release** |
| U10 | Repository maps a version conflict to a `cloud-sdk-api` exception | `EnhancedDynamoRepository.save` propagates the SDK `ConditionalCheckFailedException` unwrapped | Transformer catches the SDK exception, as mercury-services booking `SequenceIdProvider` does (an allowed SDK type) |


**U7 — SDK 2.x options checked:** v1 `AwsSdkMetrics.enableDefaultMetrics()` is JVM-wide; SDK 2.x has no global switch. A global execution interceptor (classpath registration) cannot add a publisher: the generated clients (`DefaultSqsClient` 2.30.24) resolve their metric publishers from the client and original request configuration before interceptors run, and use a no-op collector when there are none. The SDK 2.x replacement is a per-client `ClientOverrideConfiguration.addMetricPublisher(CloudWatchMetricPublisher)`, which `shared` applies itself for modules that set a metrics namespace (`shared` open issue 13), so no commons change is needed. Dropwizard timers were rejected (different metric set).

**U8–U9 (email-sender, OI 2–3 on its page):** today `MailingService` returns the SES `MessageId` and `EmailSenderTask` puts it on the `CLOSE` event as `messageId`; a null id writes `messageDropped=true` instead. The commons `EmailService.sendEmail` returns `void`, so without U8 every email would be reported as dropped. U9: today's SES client has zero retries (`withMaxErrorRetry(0)`, no duplicate emails); `EmailClientFactory` ignores a configured `RetryStrategy` and uses SDK standard retries (3 attempts).

---

## 1a. AWS SDK boundary (no direct AWS clients)

Rule (program Functional Requirement 6, `shared` open issue 14): AppianWay code builds and calls no AWS SDK client. Module and `shared` code depend only on `cloud-sdk-api` interfaces (`MessagingClient`, `StorageClient`, `NotificationService`, `DatabaseRepository`, `CloudParameterStore`, `EmailService`); implementations come only from `cloud-sdk-aws` factories in Guice wiring. An ArchUnit test (`AwsSdkBoundaryArchTest`) enforces it.

Allowed SDK types, matching mercury-services (204 entity classes there use the enhanced-client annotations; booking `SequenceIdProvider` catches `ConditionalCheckFailedException`):

| Type | Where | Why |
|---|---|---|
| `RetryStrategy` (config value) | `shared` client-profile helper only | `cloud-sdk-aws` `BaseAwsConfig` takes it |
| SDK clients + `CloudWatchMetricPublisher` | `shared` client-profile helper only, when a module sets a metrics namespace (transformer) | SDK 2.x metrics are per client and the factories take no publisher; clients are wrapped in `cloud-sdk-aws` implementations, so callers see only `cloud-sdk-api` |
| DynamoDB enhanced-client entity annotations | transformer, watermill entities | Required by `EnhancedDynamoRepository` |
| `ConditionalCheckFailedException` (catch only) | transformer `ControlNumberSequenceProvider` | Propagated unwrapped by the repository; U10 removes it |
| v1 `DefaultAWSCredentialsProviderChain` | ingestor `JestModule` (Elasticsearch SigV4 signer) | `cloud-sdk-api` `JestClientBuilder` itself takes the v1 signer interceptor; not an AWS service client |

Audit of the pages against the rule (2026-10-30). Four pages broke it and were changed:

| Page | Was | Now |
|---|---|---|
| transformer | DAO on an SDK `DynamoDbEnhancedClient` / `DynamoDbTable` (consistent scan) | `DatabaseRepository.findById(.., true)`; scan returns with U6 |
| shared | U2/U3 fallback used an SDK `S3Client`; U5 fallback used `changeMessageVisibility` (not on `MessagingClient`); metrics helper built SDK clients and wrapped them | Interface-only fallbacks (U2 empty file, U3 `getObject` size, U5 `getQueueAttributes`); metrics helper kept as the one allowed exception (transformer) |
| email-sender | Fallback was a module-local SESv2 client | Removed; U8–U9 must be in a commons release first |
| watermill platform | "One `DynamoDbClient` per application" or a module-built client | `DatabaseRepository` from `createEnhancedRepository` |

Every other page already used only the `shared` adapters and `cloud-sdk-api` interfaces.

---

## 2. Corrections to the Copilot plan and the Rev 3 drafts

| # | Plan / draft said | Reality | Effect |
|---|---|---|---|
| 1 | Watermill models: a Jackson mix-in that **omits every `false` boolean** keeps byte parity | Today's output already contains `"cargoHazardousIndicator":false` (booking) and `"ignoreForOutbound":false` (visibility). The mix-in would have **removed fields from today's wire format** | Replaced with `@JsonIgnoreProperties` on exactly the new properties (`cargoRoRoIndicator`, `cargoBreakBulkIndicator`, `viaExternalLink`; `transportationDetailsPresent`). Verified byte-identical, key order included, by running the real transformers over the module fixtures with old and new jars |
| 2 | Shared C2: copy-with-metadata "sets no content type" | SDK v1 `AmazonS3Client.invoke` adds `Content-Type: application/octet-stream` to every request without one, so today's REPLACE copies store it; an SDK 2.x copy without it stores `binary/octet-stream` | C2 now passes `application/octet-stream` explicitly. Affects distributor's delivered files |
| 3 | Client profile: 10 s API-call timeout for S3 (mirroring v1 `clientExecutionTimeout`) | The v1 timeout ended when the response arrived and excluded reading the streamed body; an SDK 2.x API-call timeout covers the body, and cloud-sdk reads bodies fully | S3 client has no API-call timeout (stalls bounded by the 5 s socket timeout); SQS send / SNS keep 10 s |
| 4 | `S3ReadHealthCheck` ported as is | It matches the v1 message text "The specified key does not exist"; cloud-sdk changes the message | v2 check decides by exception type |
| 5 | Module docs called `StorageClient` / `NotificationService` directly for workspace writes | That bypasses the one place wire parity is enforced | All SQS/SNS/workspace-S3 calls go through the `shared` adapters; direct cloud-sdk use only for DynamoDB, SES and module-specific buckets |
| 6 | Watermill platform used its own C1–C8 numbering (its C6 = SSM, shared C6 = SES) | Conflicting references | All docs use the shared C1–C9 |
| 7 | Transformer: X12/EDIFACT control numbers from DynamoDB; cloud-sdk repository rejected because "table name comes from prefix + annotation" | Only EDIFACT (not ZIM), FF and XML use DynamoDB; X12 is random. `createEnhancedRepository(config, tableName, …)` takes an explicit table name | DynamoDB is now Tier 1 via `EnhancedDynamoRepository`; `VersionedRecordExtension` reproduces v1 optimistic locking (first write `attribute_not_exists`, then `version = :old`) |
| 8 | Watermill offset init was "put-if-absent" | Unconditional write after a read miss | Corrected |
| 9 | Ingestor / watermill-publisher listener "module-local" | Both use the shared `SQSListener` with a synchronous module `AsyncDispatcher` that always reports `maxNumberOfMessages` idle | Back-pressure rule applies |
| 10 | DelaySeconds "explicit 0" concern | Retry delay is `2^attempt × delayMultiplier` (≥ 20 s with defaults), so cloud-sdk omitting 0 never applies on the retry path | Removed as a risk |
| 11 | Event-writer stored `Content-Type` change to `application/json` (old ION-12317 design) | Behaviour change | Already dropped in Rev 3; confirmed |
| 12 | `appianway-commons` module (feature branch) | Superseded | Not used; the re-based `shared` replaces it |

---

## 3. Performance, reliability and scalability changes in the design

- **Listener back-pressure kept** (see §1). The busy-spin while no worker is free (`SQSListener.java:92-99`) becomes a blocking wait for a permit: same receive pattern, no wasted CPU core per service.
- **One client per role, reused by health checks.** Today each health-check instance builds its own default v1 client (`InboundSqsHealthCheck` etc.), so each service runs several extra connection pools.
- **Client profile reproduces today's per-role settings** (connect 1 s, socket 5 s, 50 connections, 3 retries / SNS 2, backoff 500 ms–5 s, retry-on-everything via cloud-sdk `AwsRetryCondition`, which behaves like v1 `CustomRetryCondition`). Modules that differ today (error-processor: zero retries, v1 default timeouts) pass overrides.
- **DynamoDB clients use the SDK standard retry strategy, not `AwsRetryCondition`.** Retrying every failure would resend conditional writes that failed on version conflicts.
- **`createEnhancedRepository`, not `createRepository`:** the latter builds two DynamoDB clients per repository.
- **HEAD for size** instead of downloading (U3); streaming copy to file kept.
- **Logging:** `com.inttra.mercury.cloudsdk` set to WARN. cloud-sdk logs every S3 call at INFO and logs the **AWS access key ID at INFO** on credential resolution (`S3StorageClient.java:104`).

---

## 4. Existing defects found during verification (not caused by the migration)

These are in today's code. The docs record them as risks / open issues and keep behaviour unchanged unless you decide otherwise. Decision 4 (§5): not fixed; each gets a disabled known-defect test.

| Module | Defect | Evidence |
|---|---|---|
| distributor-rest | **Security:** one singleton `AuthClient` caches one OAuth token for all subscribers, so one subscriber's bearer token is sent to other subscribers' endpoints until a 401 | `distributorrest/auth/AuthClient.java:19,27-31` — **recommend a separate security ticket now** |
| distributor-rest | Worst-case POST ≈ 3 × 120 s; if the queue visibility timeout is shorter, a duplicate POST runs in parallel | `RestServiceClient` retryer + 60 s/60 s timeouts |
| splitter | Data race: parallel group routing writes the parent `MetaData` projections `HashMap` while other threads copy it, so a child envelope can get another group's control number | `SplitTransactionProcessor.java:175-183` vs `:248` |
| splitter | Full document content logged at INFO | `SplitterTask.java:103` |
| event-writer | A failed S3 write is swallowed and the message deleted (event lost); the `messages-failed` meter is on a private method Guice cannot intercept, so the error-rate health check is always healthy | `S3StoringMessageHandler.java:49,63`; `EventWriterApplication.java:65` |
| error-processor | `sqsErrorConfig` points at its own pickup queue (endless loop on a repeating failure); with several recipients the first address is written into shared projections, so every email message carries the first recipient | `error-processor.yaml`; `ErrorProcessorTask` lines 96-99 |
| ingestor | Any exception drops and deletes the whole batch; documents are indexed without ids, so a redelivery duplicates them; the Jest pool defaults to 2 connections per route against 8 listener threads | `IngestorTask.java:65,84` |
| transformer | Retry counter only resets on success; the non-recoverable path re-reads S3, writes another supplement and reserves another control number, and can NPE and loop | `ControlNumberSequenceProvider.java:149`; `TransformerErrorHandler.java:46,50` |
| distributor | Not idempotent on retry: random file names and zip keys create a second delivered file and an orphan zip | `FileDeliveryService`, `ZipCompression` |
| watermill-publisher | DLQ redrive under `scheduleAtFixedRate` stops forever after one exception; non-daemon `CleanerThread` leaks per reconnect; non-volatile `resetStream`; poison messages cycle DLQ ↔ pickup forever | `DeadLetterService`, `ResponseObserver.java:36-41` |
| watermill platform | Offset flush scheduler stops after one DynamoDB error; if `onError`'s DynamoDB calls throw, no reconnect is ever scheduled; `YYYYMMdd` is a week-based year (late-December objects land in next year's folder; kept for key parity) | `AbstractWatermillConsumerService.java:227,237`; `S3PublishService.java:18` |
| booking / visibility consumers | Retry count resets on reconnect (poison record retried forever); visibility swallows per-message S3/SQS failures and advances the offset (message never retried); `references` order varies per JVM run (golden tests must compare as a set) | `BookingInboundConsumer.java:55,223` |

---

## 5. Decisions (recorded 2026-10-30)

| # | Topic | Decision | Effect on the docs |
|---|---|---|---|
| 1 | Architecture | Re-base `shared` on commons, three tiers (§1) | As written |
| 2 | Upstream U1–U10 | Use the fallbacks first; plan the upstream changes on the branch | Fallbacks use only `cloud-sdk-api` interfaces (§1a). U8–U9 (email-sender) have no fallback and must be in a commons release before the AppianWay release; U7 is optional (per-client publisher in `shared`) |
| 3 | Hystrix / guava-retrying | Keep for now; replacement is a separate follow-up | `shared` open issue 9 and program open issue 3 resolved |
| 4 | Existing defects (§4) | Do not fix. Each module adds a test per defect that asserts the correct behaviour, committed disabled (`@Ignore` / `@Disabled` with the defect reference) so the build stays green | Paragraph under "Existing Test Impact" in the program page and in each affected module page. Races that cannot be reproduced deterministically get a repeated stress test, also disabled. The distributor-rest token caching is followed up by the author with QA (tracker entry 7) |
| 5 | Model artifacts | Vendor `booking:3.0.0.M` and `visibility:2.0.M` into each consumer's `lib/` file repository, as today | Program open issue 1 and the consumer open issues resolved |
| 6 | Modules on v1 client defaults | Keep current values through client-profile overrides, each with a code comment naming the v1 setting it reproduces | error-processor (S3/SNS: 0 retries, 10 s / 50 s, no API-call timeout); booking, visibility, cargoscreen, itv-gps (S3: 10 s / 50 s, 3 retries) |
| 7 | `cerberus`, `mftdispatcher`, `validator` | `cerberus` and `mftdispatcher` are retired; `validator` is not in the reactor build. Out of scope | Recorded in the plan; not listed on the program page |
| 8 | Transformer DynamoDB read and SDK metrics | Keep as today | Read is a consistent `findById` of the same single item; the "more than one item" error returns with U6. SDK metrics are kept under the same namespace by a per-client `CloudWatchMetricPublisher` that the `shared` helper attaches (user relaxed the cloud-sdk-only rule for this). SDK 2.x metric names differ, so check dashboards and alarms |
| 10 | One release | One branch `WI01124532-aws-sdk-upgrade`, merged once; all modules released together; v1 code removed from `shared` in the same release; per-service rollback kept by identical formats | Program page: build order, NFR 3, options 2b/4; `shared`: v1 removal; module pages: single-release assumptions |
| 9 | Watermill-publisher `task/Test.java` | Replace with a v2 harness | `WatermillPublisherLoadHarness` in test sources (not packaged, not run by Surefire), using the `shared` v2 workspace adapter and SQS sender, with all resource names passed as arguments. The unused SNS binding stays as proposed (not bound in v2; open issue 3) |

Scope as you confirmed: fulfiller, router and load-testing are out. gen2-parser has no AWS code and stays as splitter's compile-time library.

---

## 6. Per-doc change log (condensed)

| Doc | Main changes |
|---|---|
| program | Re-base architecture; FRs 3–5 and NFRs 4–5; config golden test; options table (parallel platform / retire shared / re-base ✅); open issues 6–10 (upstream U1–U5, root pins, Hystrix, out-of-reactor modules, out-of-scope modules); Jetty/Jackson convergence decided; model JSON rule corrected |
| shared | Rewritten: three-tier boundary; config chain; Client Profile table and notes; C1 (JsonSupport differences spelled out), C2 (octet-stream on REPLACE copy), C3 (idle-permit receive, no visibility timeout), C8 (commons chain); open issues U1–U5, Hystrix, test-scope jar, per-module overrides; health checks by exception type; listener wait instead of spin; tests 6 (config golden) and 8 (client profile) |
| event-writer | Writes via the shared workspace adapter; envelope is shared `SNSNotification`; meter / swallowed-failure defects; health-probe issue |
| error-processor | Archive bucket = `MetaData` bucket; SNS failures swallowed, not recoverable; zero-retry client override; self-loop and recipient defects |
| email-sender | SES Tier 1 via commons `EmailService`; reads use the JVM default charset with line joining (not UTF-8); `IllegalArgumentException` / `SendEmailException` → recoverable; v1 SES types in three more classes |
| dispatcher | Routing by `sqsRouteMappingConfig`; HEAD + `rootworkflowid` reuse; parse outside try; zip entries octet-stream; empty-entry dependency on U2; zip memory |
| splitter | Retry config `(true, 1, 150)`; two error paths; ISO-8859-1 full read; race and logging defects |
| ingestor | Keeps its own Jest module (commons `JestModule` differs on timeouts, retry handler, logs the access key); signer moves to 0.0.22 (INT check); Jest 6.3.1 must not be downgraded by commons' 5.3.3 |
| transformer | DynamoDB via `EnhancedDynamoRepository` + versioning; `@DynamoDbIgnore` on the Lombok `getKeyId()`; standard retry for DynamoDB; FA goes to its own pickup queue |
| distributor | All S3 via the shared adapter; REPLACE copy content type; idempotency and zip-memory risks |
| distributor-rest | Real retry path is SQS redelivery (not `failedAttempts`); payload re-encoded by Jersey; token-sharing defect |
| watermill-publisher | Shared listener + back-pressure; SSM via `CloudParameterStore`; DLQ redrive details; thread and redrive defects |
| watermill (platform) | v1 code is all in `consumer-commons`; offset table schema; `@DynamoDbAttribute("topicName")` required (otherwise offsets reset to 0); `S3PublishService` via the workspace adapter |
| booking / visibility consumers | `@JsonIgnoreProperties` instead of the false-omitting mix-in (byte-verified); model availability |
| cargoscreen / itv-gps consumers | `OffsetUtil` provider; keep `create-table` CLI (not commons `dynamo-create`); itv-gps `onError` does not flush offsets |

---

## 7. Verification done, and what remains

**Done:** every module claim checked against `develop` sources and commons 1.0.38 sources (file:line in the change logs); SDK v1 behaviour (content type, metadata trimming, DynamoDB mapper save modes) checked in jar bytecode; watermill model JSON compared byte for byte with the old and new jars; all 17 docs keep the 25 template sections, pass `convert_design_doc.py` and contain no CVE notes, account IDs, ARNs, queue URLs, commit hashes or branch names.

**Not done:** no code was built or run against AWS or DynamoDB Local; infrastructure settings (queue visibility timeouts, redrive policies, IAM actions for SESv2 and `ChangeMessageVisibility`) are not in the repo and need INT confirmation; the local commons checkout is on a feature branch whose version property is 1.0.38-SNAPSHOT.

**Branch and review flow:** feature branch with one sub-branch pull request per step or module, `develop` rebased in as needed; see the plan §9.5 (kept out of the published pages).

**Next:** final review of the pages → publish after explicit approval (program page first, then `shared`, then the module pages under it in build order) per the plan's §9.10.

---

## 8. Confluence publishing order

Space BRM. Landing page: [26.4.1 Design Documents](https://confluence.dev.e2open.com/display/BRM/26.4.1+Design+Documents) (`718407506`). Order: program, then `shared`, then the modules in build order, so reviewers read the foundation first. The page title is each page's H1. This review summary is not published.

| # | Source page (`2026-10-30-apway-WI01124532-<name>.md`) | Confluence title | Parent | Status |
|---|---|---|---|---|
| 1 | `program` | WI01124532 AppianWay — AWS SDK 2.x (cloud-sdk) Upgrade Program | 26.4.1 Design Documents (`718407506`) | Published `716084128` (v2); moved to 26.4.1 by the author. Landing page for every row below |
| 2 | `shared` | WI01124532 shared (mercury-shared) — Re-base on commons / cloud-sdk | program (`716084128`) | Published `716084130` (v4) |
| 3 | `event-writer` | WI01124532 event-writer — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084136` (v4) |
| 4 | `error-processor` | WI01124532 error-processor — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084140` (v2) |
| 5 | `email-sender` | WI01124532 email-sender — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084141` (v2) |
| 6 | `dispatcher` | WI01124532 dispatcher — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084143` (v2) |
| 7 | `splitter` | WI01124532 splitter — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084144` (v2) |
| 8 | `transformer` | WI01124532 transformer — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084154` (v1) |
| 9 | `distributor` | WI01124532 distributor — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084155` (v1) |
| 10 | `distributor-rest` | WI01124532 distributor-rest — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084156` (v1) |
| 11 | `ingestor` | WI01124532 ingestor — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084157` (v1) |
| 12 | `watermill-publisher` | WI01124532 watermill-publisher — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084167` (v1) |
| 13 | `watermill` | WI01124532 watermill consumer platform (consumer-commons, consumer-framework, billoflading) — AWS SDK 2.x (cloud-sdk) Upgrade | program (`716084128`) | Published `716084168` (v1) |
| 14 | `booking-inbound-consumer` | WI01124532 watermill booking-inbound-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | watermill platform | Published `716084170` (v1) |
| 15 | `visibility-inbound-consumer` | WI01124532 watermill visibility-inbound-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | watermill platform | Published `716084171` (v1) |
| 16 | `cargoscreen-consumer` | WI01124532 watermill cargoscreen-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | watermill platform | Published `716084172` (v1) |
| 17 | `itv-gps-consumer` | WI01124532 watermill itv-gps-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | watermill platform | Published `716084173` (v1) |

Per page: re-run `sso_login.py` if Confluence returns 401 → `convert_design_doc.py` (exit 0) → `confluence_create_page` (storage) under the parent → read back and check → record the page id here and at the end of the plan.

All 17 pages are published. The watermill consumer pages (14–17) are children of the watermill platform page (`716084168`).

---

## 9. Changes after publishing (tracker)

> **2026-10-31:** open follow-ups from this page (§4–§9) are now tracked in the development work document `2026-10-31-apway-aws-upgrade-dev-progress.md` §2 (actions A1–A12). This table stays the record of design-page changes.

Changes decided after a page was published. Published pages are kept stable: each change is listed here and applied in one batched minor edit (same page id, watchers not notified) when the set is agreed, unless it is urgent. Pages not yet published take the change before they go out.

| # | Date | Change | Reason | Pages affected | Published page action | Status |
|---|---|---|---|---|---|---|
| 1 | 2026-10-30 | U3 (size-only HEAD in commons `StorageClient`) becomes a release prerequisite, together with U8–U9 | The interface-only fallback (`getObject(...).getSize()`) would download every split file to read its size; splitter, `shared` NFR 3 and program NFR 4 all promise HEAD, no download | `shared` (open issue 4, key component 7, impact and dependency lines) | Program `716084128`: prerequisite text "U8–U9" → "U3, U8–U9" in open issue 2, Release and Build Order, option 2b and Major Dependencies. NFR 4 already correct | Applied (`shared` before publish; program in its v2) |
| 2 | 2026-10-30 | New test classes use JUnit 5; existing JUnit 4 tests run unchanged on the Vintage engine; Surefire on the JUnit Platform; test-count check | Author decision | `shared` (NFR 4, acceptance 7, technology stack, key components 17–18, jars, existing test impact); module pages: known-defect tests use `@Disabled` | `shared` `716084130`: updated to v2 together with its source | Applied |
| 3 | 2026-10-30 | `shared` open issue 11 (transitive AWS SDK v1 jars) removed; later issues renumbered 12–15 → 11–14; status set to Resolved wherever the design has decided (2, 3, 5, 8, 10, 11) — only 4 (U3, needs a commons release) stays Open | Author decision; one status rule: Resolved = decided in this design, Open = pending outside it | `shared`; cross-references in program FR 6, event-writer, email-sender, transformer, watermill | `shared` `716084130`: updated to v3. Program `716084128`: FR 6 reference "open issue 14" → "13", pending batch | Applied (`shared` v3; program in its v2) |
| 4 | 2026-10-30 | Same status rule on every page: Resolved = decided in this design, Open = pending outside it. 21 module rows set to Resolved; "Decision needed" / "Proposed" wording replaced by the decision. Still Open: email-sender 2–3 (commons U8–U9), distributor-rest 3 (security ticket), distributor-rest 4 (queue visibility timeout on INT), distributor 3 (null metadata behaviour on INT) | Author decision | booking, visibility, distributor, email-sender, error-processor, event-writer, ingestor, watermill-publisher, watermill | None published at the time; program page already follows the rule | Applied |
| 5 | 2026-10-30 | Deployment text on every module page aligned with the single release ("rolling restart as part of the single AppianWay release"; per-service rollback kept); event-writer health-probe risk marked as mitigated by the `shared` probe | Contradicted the single-release decision | All 15 module pages | None published at the time (event-writer published with the fix); program and `shared` already correct | Applied |
| 6 | 2026-10-30 | "Status: Design — pending review" line removed from every page | Author decision | All 17 pages | Program v2, `shared` v4, event-writer v4, error-processor v2, email-sender v2, dispatcher v2, splitter v2 (minor edits; the program v2 also carries entries 1 and 3) | Applied |
| 7 | 2026-10-30 | distributor-rest `AuthClient` caches one bearer token for all subscriptions; the page states it as existing behaviour (open issue 3 Resolved, risk listed), with no defect wording and no ticket dependency | Security follow-up owned by the author: security defect to be raised with QA, outside this program | distributor-rest | Published without a dependency | **Pending — author to raise the QA security defect and share the reference** |
| 8 | 2026-10-30 | Non-functional requirement 1 no longer says "v1 jars may remain transitively via `cloud-sdk-aws`"; ingestor keeps its exception for the v1 credentials provider used by the Jest SigV4 signer in `JestModule`. Jar tables unchanged | Author request | All 17 pages (published: program, shared, dispatcher, splitter, transformer, distributor, distributor-rest, ingestor) | Program v3, `shared` v5, dispatcher v3, splitter v3, transformer v2, distributor v2, distributor-rest v2, ingestor v2 (minor edits); unpublished pages updated in source | Applied |
