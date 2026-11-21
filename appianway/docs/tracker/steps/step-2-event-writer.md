# Step 2 — event-writer (`WI01124532-aws-sdk-upgrade-event-writer`)

← [Tracker home](../README.md) · [All steps](README.md)


Cut 2026-11-18 from the feature branch at `58aee71b`. Pushed 2026-11-18 as [PR #4](https://github.com/wtg-e2open/INTTRA.appianway/pull/4); description `pr-details/2026-11-18-apway-pr-2-event-writer-description.md`. Design page: `docs/redesign/2026-10-30-apway-WI01124532-event-writer.md`. event-writer had 3 tests (handler 1, task 1, functional 1); it now has 17 run, plus 2 disabled.

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `672034c2` test: characterize the events event-writer stores and the message shapes it reads | test | `EventWireCompatibilityTest` (3, design test 2): the key and body of every stored object, compared with files the v1 build wrote (`wire/raw-array.json` minimal / rich / sparse events, and the functional SNS envelope). The comparison ignores CRLF (`core.autocrlf`). `SQSMessageToEventConverterTest` (4, design test 3). Both pass on v1. [F12](../findings.md#f12) found here |
| 2 | `0b37403f` red: event-writer handles received queue messages instead of SDK v1 messages | red | Tests retargeted to a test `QueueMessage` (`TestQueueMessage` record); the handler and task tests are now JUnit 5; the handler test is extended (design test 1: a failed write and an unreadable body are swallowed). Skeletons: a throwing `handle(QueueMessage)` / `convert(QueueMessage)`; the task takes a `MessageQueueClient` ([D27](../decisions.md#d27)). 10 fail |
| 3 | `fa88d6e4` green: event-writer handles received queue messages instead of SDK v1 messages | green | Handler, converter and task on `QueueMessage<String>`; no v1 `Message` left in them. The unchanged v1 functional test passes through the `AbstractTask` bridge ([D15](../decisions.md#d15)). 13 tests |
| 4 | `4a2d3194` red: event-writer runs on the cloud-sdk clients and the shared adapters | red | `AwsSdkBoundaryArchTest` (2): `AwsSdkBoundary.check`, plus no shared SDK v1 class (12 + 12 violations). Functional test on `CloudFunctionalTestBase` + fakes; the v1 assertions are unchanged (`FakeQueue` is a `FakeSQS`, `storage.asFakeS3()`). New: UTF-8 body, `text/plain`, no metadata (design acceptance 3); health-check names on the default registry and the ops endpoint |
| 5 | `8a076bf1` green: event-writer runs on the cloud-sdk clients and the shared adapters | green | [D37](../decisions.md#d37). The application builds `CloudServicesModule` (default settings = v1 `sqs_listener` / `sqs_sender` / `s3_read_put_copy`, no topic); `ExternalServicesModule` deleted; `MessageQueueListener`; `InboundMessageQueueHealthCheck` / `StorageWriteHealthCheck` on the injected clients (same names); `StorageConfigurationProvider`. 16 tests |
| 6 | `e555d2a7` red: cloud-sdk logs only warnings in event-writer | red | Functional test: effective level of the cloud-sdk `S3StorageClient` logger is WARN, event-writer's own INFO. Checked first: cloud-sdk 1.0.39 still logs every put at INFO (`S3StorageClient.java:437`). U13 only removed the access-key log |
| 7 | `5042748d` green: cloud-sdk logs only warnings in event-writer | green | `event-writer.yaml`: `com.inttra.mercury.cloudsdk: WARN`. 17 tests |
| 8 | `6a0e2381` test: disabled tests for the two known event-writer defects | test | [A12](../actions.md#a12). `EventWriterKnownDefectsTest` (2, `@Disabled` with the reference): a failed write leaves the message on the queue; a failed write marks the meter the error-rate check reads. Both fail when the disabled condition is turned off |

**Full reactor build of `6a0e2381`** ([G4](../rules.md#g4) worktree): green in 9:54 min, all 26 build units; event-writer 19 (2 skipped), every other count unchanged (shared 1818, functional-testing 48, transformer 665 …).

Not covered by an automated test: the production `CloudServicesModule` itself in event-writer, because it builds real AWS clients. The fakes are bound under exactly its keys; 1e's `clientsAreBoundUnderTheNamesTheCloudModuleUses` proves that. INT boot (design manual test 1) covers the rest.

**Review round 1 (Copilot, 2026-11-18):** one high-severity comment. `CloudServicesModule` closes its clients on shutdown, but `ListenerManager.stop()` only set a flag, so a message in progress could write to a closed client, get its failure swallowed, and be deleted. Valid; it came in with #2 (`601e0fb7`). Fixed in PR #4 (Arijit's decision), in `shared`:

| # | Commit | Type | Change |
|---|---|---|---|
| 9 | `c7856876` red: messages in progress finish before the cloud clients close | red | `ListenerManagerTest` (5) on the real `MessageQueueListener` + `AsyncDispatcher`, including a Dropwizard lifecycle attached to Jetty. Stub defaults `Listener.drain` / `Dispatcher.drain`. 4 fail |
| 10 | `9367939c` green: same | green | `ListenerManager.stop()` = stop flag + drain (20 s, inside the container's 30 s stop timeout). `AsyncDispatcher.drain` = executor shutdown + await; a message received after the drain is not run, so the queue delivers it again. Both listeners delegate; other implementations keep today's behaviour through the defaults. Applies to every service on the shared `ListenerManager`. ingestor and watermill-publisher have their own listener manager: unaffected on SDK v1, but their migrations must add the same drain (the close order comes with `CloudServicesModule`) |

Full reactor build of `9367939c`: green in 10:37 min; shared 1818 → 1823, every other count unchanged. Pushed `6a0e2381..9367939c`, replied, thread resolved, PR description updated. The PR doc now also has Part 3 (the round), Part 4 (command log) and Part 5 (event-writer from start to shutdown, with diagrams). error-processor (not stacked) gets the fix when #4 merges into the feature branch.

**Review round 2 (Copilot on `9367939c`, 2026-11-19):** one high-severity comment. A multi-event message that outlives the 20 s drain (one storage put can take about 43 s with its retries) kept running while storage closed before the sender, so a failed write could still be swallowed and the message deleted. Valid; fixed by the close order:

| # | Commit | Type | Change |
|---|---|---|---|
| 11 | `065370bb` red: a message still in progress after the drain timeout is not acknowledged | red | `ShutdownAcknowledgementTest` (1): real `CloudServicesModule` on clients that fail once closed, two-event task that swallows, 200 ms drain, Jetty lifecycle. `ListenerManager(Listener, Duration)` now public. Fails: message deleted with one event missing |
| 12 | `53c9b564` green: same | green | `CloudServicesModule` registers storage, download, listener, sender, so they close sender, listener, download, storage. A late delete fails and the message is redelivered (same keys rewritten). 3 runs in a row green |

Full reactor build of `53c9b564`: green in 9:47 min; shared 1823 → 1824, every other count unchanged. Pushed `9367939c..53c9b564`, replied, thread resolved, PR description updated (change 7 also clarified: closing came with #2, the swallow is the existing defect). Both review threads resolved, `mergeStateStatus` CLEAN.

**Review round 3 (Copilot on `53c9b564`, 2026-11-19):** no inline comment, "No open issues", verdict "Needs a closer look": shutdown safety was only checked with mocks. Checked with the real clients: a closed sender refuses a delete before any request; a closed storage client still works ([F15](../findings.md#f15)). Added `89a6077d` test: `ClosedSenderRefusesDeleteTest` (real sender, production settings, no network). All shared tests green (1825). Pushed `53c9b564..89a6077d`, PR description updated, PR comment posted (issuecomment-7000358258); Arijit re-requests the Copilot review.
