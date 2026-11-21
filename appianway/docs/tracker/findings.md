# Findings (F#)

← [Tracker home](README.md) · Closed findings: [closed-items.md](closed-items.md#closed-findings)

Facts found during development: what was found, and its effect or what was done.

| ID | Date | Title |
|---|---|---|
| [F1](#f1) | 2026-10-31 | Local full build fails at registration-inbound-consumers |
| [F3](#f3) | 2026-10-31 | cargoscreen-consumer runs 0 tests |
| [F4](#f4) | 2026-10-31 | A lone -pl build uses a stale mercury-shared jar |
| [F7](#f7) | 2026-10-31 | VS Code autobuild corrupts target/ during Maven builds |
| [F9](#f9) | 2026-11-17 | cloud-sdk logs every SNS publish at INFO |
| [F10](#f10) | 2026-11-17 | Inbound health probe sends WaitTimeSeconds 0 |
| [F11](#f11) | 2026-11-17 | Modules outside the reactor build |
| [F12](#f12) | 2026-11-18 | event-writer drops a message for an unknown event field |
| [F14](#f14) | 2026-11-18 | consumer-commons time-zone test flake in the evening |
| [F15](#f15) | 2026-11-19 | cloud-sdk storage client's close() does nothing |
| [F16](#f16) | 2026-11-19 | email-sender: failure events fail (pickupQueue twice) |
| [F17](#f17) | 2026-11-19 | cloud-sdk email service's close() does nothing |
| [F18](#f18) | 2026-11-19 | dispatcher: failed routed send cannot build its failure event |
| [F19](#f19) | 2026-11-19 | dispatcher: error-rate check reads a meter nothing marks |
| [F20](#f20) | 2026-11-19 | dispatcher: zip storage failures are not retried |
| [F21](#f21) | 2026-11-19 | cloud-sdk logs the health probe missing key at ERROR |
| [F22](#f22) | 2026-11-19 | SDK v1 S3 fake returns hard-coded metadata |
| [F23](#f23) | 2026-11-19 | dispatcher: zip entries inside folders cannot be routed |
| [F24](#f24) | 2026-11-19 | cloud-sdk email module warns about 12 missing templates at startup |
| [F25](#f25) | 2026-11-19 | cloud-sdk retries the storage health probe's expected "not found" 3 times |
| [F26](#f26) | 2026-11-19 | splitter: split documents of mixed message types get the format id of the last one checked |
| [F27](#f27) | 2026-11-19 | splitter: per-document failure events take their start time from the wall clock |
| [F28](#f28) | 2026-11-19 | SDK v1 S3 fake reports size 0 for every object |
| [F29](#f29) | 2026-11-20 | Commons DynamoDB factory applies only a retry mode; DynamoDB retries 8 times (v1 10) |
| [F30](#f30) | 2026-11-20 | Elasticsearch signer 0.0.22 (commons) no longer signs Content-Length; ingestor kept at 0.0.16 |
| [F31](#f31) | 2026-11-20 | A null user-metadata value: SDK v1 stores it empty, SDK 2.x drops it; shared now writes it as "" |

Closed: [F2](closed-items.md#f2) Transformer's JUnit 5 tests not run on develop, [F5](closed-items.md#f5) watermill-publisher logback pair mismatch, [F6](closed-items.md#f6) Stress configuration cannot resolve, [F8](closed-items.md#f8) New config chain ignores unused unresolvable placeholders, [F13](closed-items.md#f13) error-processor's functional test had not run since 2021.

---

<a id="f1"></a>
### F1 · Local full build fails at registration-inbound-consumers (2026-10-31)

**Finding.** The full reactor build of `develop` fails locally at `registration-inbound-consumers`: `dynamo-client:1.0` is only in the local repository, cached from other watermill modules' `lib/` file repositories, and Maven 3.9's enhanced local repository refuses artifacts whose recorded origin is not one of the module's repositories. There is no `~/.m2/settings.xml` locally

**Effect.** Local builds use flag [G2](rules.md#g2); CI presumably resolves it from the corporate repository ([A15](actions.md#a15))

<a id="f3"></a>
### F3 · cargoscreen-consumer runs 0 tests (2026-10-31)

**Finding.** watermill `cargoscreen-consumer` runs 0 tests on `develop`: its 2 JUnit 4 test classes are on the JUnit Platform provider (auto-detected) with no Vintage engine. The watermill tree does not inherit the root pom, so 1a does not change it

**Effect.** Fix in the cargoscreen-consumer PR (step 4): add `junit-vintage-engine` ([A16](actions.md#a16))

<a id="f4"></a>
### F4 · A lone -pl build uses a stale mercury-shared jar (2026-10-31)

**Finding.** Building a single service with `-pl <module>` (without `shared` in the reactor) resolves `mercury-shared:1.0` from `~/.m2`, which can be a stale jar from another branch. watermill-publisher then failed 57 tests (Mockito "Could not create type"); with `-pl shared,<module>` all 153 pass

**Effect.** Always build a service together with `shared` (`-pl shared,<module>` or `-am`); never trust a lone `-pl` result ([commands: Maven builds](commands/maven.md#s9-4))

<a id="f7"></a>
### F7 · VS Code autobuild corrupts target/ during Maven builds (2026-10-31)

**Finding.** A full build failed in gen2-parser with `NoClassDefFoundError: com/inttra/mis/data/IMessage` (Vintage engine discovery). Maven had compiled 48 classes; at 18:06:25, before the tests, `target/classes` held one class written by the VS Code Java extension, which rebuilds the workspace automatically

**Effect.** Environmental, not caused by the change. Builds now run in a separate worktree ([G4](rules.md#g4))

<a id="f9"></a>
### F9 · cloud-sdk logs every SNS publish at INFO (2026-11-17)

**Finding.** cloud-sdk `SnsService.publish` logs `Published message to topic: <arn>` at INFO for every publish; v1 logged nothing. More log volume on every lineage event (once per task step)

**Effect.** Accept for now; candidate commons ask (DEBUG), or a logger level for `com.inttra.mercury.cloudsdk.notification.impl.SnsService` in the service logging config if INT shows noise

<a id="f10"></a>
### F10 · Inbound health probe sends WaitTimeSeconds 0 (2026-11-17)

**Finding.** cloud-sdk always sends `WaitTimeSeconds`, so the v2 inbound health probe asks for 0 (short poll); v1 left it unset, which uses the queue's `ReceiveMessageWaitTimeSeconds`. Same result when that attribute is 0 (the usual setting; the listener sets its own 20 s); if a queue had a non-zero default, v1 health checks long-polled and v2 answers faster

**Effect.** No action; check on INT if a health check behaves differently

<a id="f11"></a>
### F11 · Modules outside the reactor build (2026-11-17)

**Finding.** Root pom `<modules>` does not build cerberus, fulfiller, router, mftdispatcher, validator. Their v1 code is out of scope and untouched; the `shared` signature changes stay compatible with them (`SQSClient` is-a `MessageQueueClient`; none implements `WorkspaceService` or uses the put results)

**Effect.** None

<a id="f12"></a>
### F12 · event-writer drops a message for an unknown event field (2026-11-18)

**Finding.** An event with a field `Event` does not know makes event-writer drop the **whole message**: `Event` has `@JsonIgnoreProperties(ignoreUnknown = true)`, but Jackson deserializes through `Event.Builder` (`@JsonDeserialize(builder = …)`), which lacks it (`UnrecognizedPropertyException`). The handler then tries the SNS shape, fails and swallows the error, and the message is deleted. Found while building the event-writer golden fixture

**Effect.** Existing v1 behaviour, unchanged (no change to existing behaviour in this program); the fixture has no unknown field. Candidate for the defects list ([A12](actions.md#a12)) and a later fix in `shared` (`@JsonIgnoreProperties(ignoreUnknown = true)` on the builder)

<a id="f14"></a>
### F14 · consumer-commons time-zone test flake in the evening (2026-11-18)

**Finding.** `watermill/consumer-commons` `S3PublishServiceTest.testGetFullS3Path_ShouldReturnPathWithCurrentDate` fails every evening from 19:00 to 24:00 EST (20:00 to 24:00 in summer time). `S3PublishService.getFullS3Path` uses the **UTC** date, and the test compares it with the **local** date. It failed the full build of `6b123918` at 19:10 EST; the module is untouched by WI01124532 so far

**Effect.** Not a regression. Full builds in that window: resume with `JAVA_TOOL_OPTIONS=-Duser.timezone=UTC mvn -B verify -rf :consumer-commons …` ([G2](rules.md#g2) flag as usual). Fix (test uses the UTC date) belongs to the watermill step (step 4) or a separate change

<a id="f15"></a>
### F15 · cloud-sdk storage client's close() does nothing (2026-11-19)

**Finding.** cloud-sdk's `S3StorageClient` does not override `CloudResource.close()`, so closing it does nothing: its connection pool is never closed, and the client keeps working after "close". Found while checking Copilot's third review on PR #4 with the real clients (a closed real storage client still sent a PUT; the closed real sender refused a delete).

**Effect.** Harmless: it only matters at shutdown, where the JVM exits anyway, and it makes in-flight writes safer. The shutdown fix relies only on the sender (tested on the real client, `89a6077d`). A real `close()` would be a commons cloud-sdk change

<a id="f16"></a>
### F16 · email-sender: failure events fail (pickupQueue twice) (2026-11-19)

**Finding.** email-sender: every failure fails again while its failure event is built. The task passes the token `pickupQueue` and the shared `ErrorHandler` adds `pickupQueue` too, so `ImmutableMap` throws "Multiple entries with same key". The message was already sent back or to the error queue, but no failure event is published and the message is not deleted, so it returns until the queue's redrive. Hidden because the v1 error-flow functional test had no `@Test` since 2017 (`4c4863c8`). Same exists in v1

**Effect.** Kept (known-defects policy). `EmailSenderKnownDefectsTest` (disabled, PR #6) asserts the correct behaviour; verified to pass with the one-line fix (task passes no `pickupQueue` token) and fail without. **Arijit to decide:** fix now or later Details, QA table and fix: [known-defects.md](known-defects.md#kd-4).

<a id="f17"></a>
### F17 · cloud-sdk email service's close() does nothing (2026-11-19)

**Finding.** cloud-sdk's `SesEmailServiceImpl` (like `SnsService`) does not override `close()`, so the SES client and its connection pool are never closed; `CloudServicesModule` therefore does not register it for closing. Found in the PR #6 pre-review

**Effect.** Harmless at shutdown (JVM exit). Commons ask alongside [F15](#f15)

<a id="f18"></a>
### F18 · dispatcher: failed routed send cannot build its failure event (2026-11-19)

**Finding.** dispatcher: a failure after the routed (or booking-bridge) send was attempted cannot build its failure event. The task has already put `pickupQueue` and `dropOffQueue` into its token map; the shared `ErrorHandler` adds both again and `ImmutableMap` throws "Multiple entries with same key". For a recoverable failure the retry copy was already sent to the pickup queue, so on SQS the original returns too and the file is routed twice. Same family as [F16](#f16)

**Effect.** Kept (known-defects policy). `DispatcherKnownDefectsTest.aFailedRoutedSendIsRetriedOnceAndItsFailureEventPublished` (disabled, PR dispatcher); verified to pass with the fix "remove the two tokens before `handleException`" and fail without. **Arijit to decide** with [F16](#f16) Details, QA table and fix: [known-defects.md](known-defects.md#kd-1).

<a id="f19"></a>
### F19 · dispatcher: error-rate check reads a meter nothing marks (2026-11-19)

**Finding.** dispatcher: the error-rate health check gets the meter `DispatcherTask.messages-failed`, but `@Metered` on `ErrorHandler.handleException` marks `com.inttra.mercury.shared.task.ErrorHandler.messages-failed` (metrics-guice names the meter after the declaring class). `errorsPerSecondAverage` never sees a failure. Same kind as event-writer's known defect

**Effect.** Kept. `DispatcherKnownDefectsTest.theErrorRateHealthCheckCountsFailedMessages` (disabled) reads the meter the registered check holds, so any fix passes it; verified with `name(ErrorHandler.class, ...)`. Probably every service whose handler extends the shared `ErrorHandler` has it Details, QA table and fix: [known-defects.md](known-defects.md#kd-2).

<a id="f20"></a>
### F20 · dispatcher: zip storage failures are not retried (2026-11-19)

**Finding.** dispatcher: `ZipPreprocessor` wraps every failure in `RuntimeException("Exception in zip processor")`, so a recoverable storage failure while a zip is read or its entries written is not retried: the zip goes to the error queue and is never expanded. The dispatcher design page says the opposite ("re-expanded on retry")

**Effect.** Kept. `DispatcherKnownDefectsTest.aStorageFailureWhileExpandingAZipIsRetried` (disabled); verified with "rethrow `RecoverableException`". Design page to correct ([A21](actions.md#a21) batch) Details, QA table and fix: [known-defects.md](known-defects.md#kd-3).

<a id="f21"></a>
### F21 · cloud-sdk logs the health probe missing key at ERROR (2026-11-19)

**Finding.** cloud-sdk `AbstractStorageObject.handleNoSuchKeyException` logs every missing key at ERROR with the stack trace. `StorageReadHealthCheck` is healthy exactly when its probe key `anykey` is missing, so each run of the check logs one ERROR line (dispatcher; error-processor too, merged). v1 logged nothing. The logger also carries real S3 errors, so a logger level cannot hide it. Found by the dispatcher pre-review

**Effect.** Stated in the dispatcher PR. **Decided 2026-11-19 (Arijit):** commons ask **U15**, low priority ([spec](../redesign/2026-11-11-sdk-commons-upgrade-specs.md), [A3](actions.md#a3)); accepted until released. Options that were considered: commons change (missing key at DEBUG / WARN without stack) recommended; alternative HEAD probe ([D28](decisions.md#d28) rejected it: a deleted bucket would look healthy)

<a id="f22"></a>
### F22 · SDK v1 S3 fake returns hard-coded metadata (2026-11-19)

**Finding.** The SDK v1 `FakeS3Impl.getObjectMetadata` is hard-coded to return `xlogid=123456789` for any bucket and key, and never fails. dispatcher's v1 booking-bridge functional test stored its file under another key and still passed

**Effect.** Test-only. The cloud tests store the inbound files with that metadata (`V1_FAKE_METADATA`) and under the notification's key

<a id="f23"></a>
### F23 · dispatcher: zip entries inside folders cannot be routed (2026-11-19)

**Finding.** `ZipPreprocessor` writes every zip entry next to the zip under the entry's own name, and each written object raises a new notification. dispatcher needs keys of exactly five parts (`format/date/customers/MFT-id/file`). A zip with a folder, e.g. `invoices/a.edi`, writes `…/CU2000/invoices/` (an empty folder object: five parts, so it fails as an empty file) and `…/CU2000/invoices/a.edi` (six parts: the format cannot be resolved, so it goes to the error queue and is never routed). Flat zips are fine. Unchanged since 2018 (`8841f14b`); characterized by `ZipPreprocessorTest` (`nested/` entries). Found in the dispatcher pre-review (point 4)

**Effect.** Logged as a finding only, no test and no fix (Arijit, 2026-11-19): unchanged since 2018 and nobody has reported it. **QA confirmed (2026-11-19) that partners send only flat zips**, so it does not occur in practice

<a id="f24"></a>
### F24 · cloud-sdk email module warns about 12 missing templates at startup (2026-11-19)

**Finding.** When email-sender (new build) starts, cloud-sdk's `EmailTemplatesLoader` logs 12 WARN lines "Unable to find template <name>.json" (ExampleTemplate, RequestAmendTemplate, …, InternalErrorTemplate): it looks for mercury-services' email templates, which AppianWay does not use (email-sender renders its own Thymeleaf templates). They pass the `com.inttra.mercury.cloudsdk: WARN` filter. Seen in runtime test 3 ([runtime/email-sender.md](runtime/email-sender.md#test-3), step 14)

**Effect.** Cosmetic: 12 lines once per start. Candidate commons ask (load templates only when the templated API is used, or log at DEBUG), or a logger level for `com.inttra.mercury.cloudsdk.email.loader.api.EmailTemplatesLoader` in `email-sender.yaml`

<a id="f25"></a>
### F25 · cloud-sdk retries the storage health probe's expected "not found" 3 times (2026-11-19)

**Finding.** `StorageReadHealthCheck` reads the probe key `anykey`, which must be missing (healthy = 404). The storage client's retry rule retries every failure, a 404 included, so each health check makes **4 GETs** ("SDK Attempt Count: 4", three suppressed "Request attempt n failure" lines) and takes **about 4.7 s** instead of v1's 0.6 s with one GET. Seen in runtime test 4 on dispatcher ([runtime/dispatcher.md](runtime/dispatcher.md#test-4a), step 11). Every service with that check is expected to do the same (error-processor's was not timed in test 2). Real reads are affected only when the key is missing, which dispatcher does not expect (the notification names an existing object). Related: [F21](#f21) (the same probe logged at ERROR)

**Effect.** Not functional: the check stays healthy. Costs 3 extra GETs and about 4 s per health check. That matters if ECS or a load balancer calls `/admin/healthcheck` with a short timeout: the container health-check timeouts must be checked before release. Candidate commons ask with U15: do not retry a 404 (`NoSuchKeyException`) in the storage retry rule. Alternatively, the probe could use a client without retries

<a id="f26"></a>
### F26 · splitter: split documents of mixed message types get the format id of the last one checked (2026-11-19)

**Finding.** `NetworkMessageIdentifier` keeps the `formatId` and `integrationProfileFormatId` of its **last** `isAuthorized` call in fields, and `SplitTransactionProcessor.routeToQueue` stamps every split document with `identifier.getFormatId()`. `SplitterTask` checks every document of a batch first and routes afterwards, and repeated checks of the same type and version are answered from a per-batch cache without calling the identifier. So when one file holds documents of two message types or versions (for example IFTMIN and IFTSTA), every split document is routed with the format of the last type checked. The routing itself (`FormatBasedSQSRouter`) looks the format up by that id, so the context code and the target queue follow the wrong format too. Since February 2018 (`74a0fb23`). Found by the splitter pre-review; read from the code, not reproduced

**Effect.** None in practice. "Message type" here is the EDI message (IFTMBF, IFTSTA, IFTMIN …) and its version. **Arijit, 2026-11-20:** files do not mix message types, so every document of a file has the same format and the last one checked is the right one. Stays a finding, no test (as [F23](#f23))

<a id="f27"></a>
### F27 · splitter: per-document failure events take their start time from the wall clock (2026-11-19)

**Finding.** `SplitTransactionProcessor.handleError` passes `LocalDateTime.now()` (the JVM's default zone) as the failure event's start time, where everything else uses the injected UTC clock. The golden test normalizes that one timestamp. Since February 2021 (`c88bfab9`). Found while writing the golden test and again by the pre-review

**Effect.** On a host whose zone is not UTC, the start time of a per-document failure event is in local time while its other times are UTC. ECS tasks run in UTC, so no effect there. Cosmetic; a one-word fix (`now(clock)`)

<a id="f28"></a>
### F28 · SDK v1 S3 fake reports size 0 for every object (2026-11-19)

**Finding.** The SDK v1 `FakeS3Impl.getObjectMetadata` returns a new `ObjectMetadata` with only `xlogid` set ([F22](#f22)), so its content length is always 0. splitter's v1 golden files therefore have `"splitterFileSize":"0"` everywhere. Real S3 and the cloud-sdk fake return the length

**Effect.** Test-only. splitter's golden test checks that each routed `MetaData` carries the stored object's real length, then prints it as 0 to match the v1 files

<a id="f29"></a>
### F29 · Commons DynamoDB factory applies only a retry mode (2026-11-20)

**Finding.** `DynamoRepositoryFactory.createOverrideConfig` reads only `DynamoDbClientConfig.retryMode`; a `retryStrategy` set on the config is ignored. Setting a mode also replaces the SDK's own DynamoDB retry policy (9 attempts, 25 ms base backoff). `createRepository` with the enhanced client builds two SDK clients, neither closed (they live until the JVM exits, as the v1 client did)

**Effect.** transformer's DynamoDB client keeps the SDK 2.x DynamoDB default: retryable failures tried 9 times (v1 `DYNAMODB_DEFAULT`: 11). Only matters during throttling or a DynamoDB outage; the control-number provider's own 10 conflict retries are unchanged. Possible commons item: honour `retryStrategy` (not needed for this upgrade)

<a id="f30"></a>
### F30 · Elasticsearch signer 0.0.22 no longer signs Content-Length (2026-11-20)

**Finding.** ingestor pinned `aws-signing-request-interceptor` 0.0.16; the design planned the commons version 0.0.22 (open issue 3, "verified by an INT signed request"). `ElasticsearchSigningCompatibilityTest` (written on 0.0.16, requests as the Apache client hands them to the signer) fails on 0.0.22: the signed headers drop `content-length` (`content-type;host;x-amz-date` instead of `content-length;content-type;host;x-amz-date`) on the bulk and upsert requests, so every signature differs. Still valid SigV4 (host and date are the only required signed headers).

**Effect.** None in this PR: ingestor stays on 0.0.16 (commit 13 of [step-3-ingestor](steps/step-3-ingestor.md)), signing exactly as before. Moving to 0.0.22 is a separate change and needs a signed request against a real domain first ([A10](actions.md#a10), now "before moving the signer", not "before the ingestor PR"). cloud-sdk's own Jest builder uses 0.0.22; ingestor does not use it (design open issue 2).

<a id="f31"></a>
### F31 · A null user-metadata value: SDK v1 stores it empty, SDK 2.x drops it (2026-11-20)

**Finding.** distributor puts its outbound integration profile format id, context code and outbound EDI id into the delivered objects' user metadata unconditionally, so a value can be null (distributor design open issue 3). Checked on QA with a marked object in `inttra2-qa-workspace` (`wi01124532-rt-dist-nullmeta/`): a REPLACE copy with `{workflowId, contextCode=null, outboundEdiId=null}` made with SDK v1 (as distributor's v1 code) stored `contextcode: ""`, `outboundediid: ""`; the same copy with SDK 2.x (as cloud-sdk's `S3StorageClient` makes it) stored only `workflowid`: the null entries are dropped. Both stored `Content-Type: application/octet-stream` (design open issue 2 confirmed). Tools: [NullMetaV1.java](runtime/fixtures/test8-distributor/NullMetaV1.java), [NullMetaV2.java](runtime/fixtures/test8-distributor/NullMetaV2.java); log: [runtime/distributor.md](runtime/distributor.md#experiment).

**Effect.** Fixed in the distributor PR: `StorageWorkspaceService` writes a null value as `""` (commits 7–8 of [step-3-distributor](steps/step-3-distributor.md)), so delivered objects keep the empty keys as before. The golden file's v1 capture had shown the request's `null`; corrected to the stored `""` with this evidence (commit 9). Commons could do the same in `S3StorageClient` (not asked).

