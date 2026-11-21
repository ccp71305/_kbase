# Step 2 — error-processor (`WI01124532-aws-sdk-upgrade-error-processor`)

← [Tracker home](../README.md) · [All steps](README.md)


Cut 2026-11-18 from the feature branch at `58aee71b`; not stacked on event-writer (PR #4), because the two modules are independent. Local only. Design page: `docs/redesign/2026-10-30-apway-WI01124532-error-processor.md`. error-processor ran 2 tests: the functional test had no `@Test` ([F13](../closed-items.md#f13)). It now runs 11, plus 1 disabled.

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `0f5f3037` test: characterize what error-processor archives, sends and publishes | test | [F13](../closed-items.md#f13): the functional test was re-enabled. Its event fixture was stale (now has `subType` closeWorkflow and the `pickupQueue` token), and the pickup body is taken from the fixture file instead of a CRLF copy. `ErrorProcessorWireCompatibilityTest` (design test 2) is functional-level and compares the exact archive, email-queue and event strings with `wire/happy.expected.txt`, written by v1 (messageId and CRLF normalized; same output on two runs) |
| 2 | `289603a2` red: error-processor's task handles received queue messages … | red | `ErrorProcessorTaskTest` now JUnit 5 + `TestQueueMessage`, extended (design tests 1, 3): verbatim archive key and body, one message per recipient, workflow ids, today's recipient behaviour, failure → error handler with nothing sent. Skeleton: `MessageQueueClient` constructor. 4 fail |
| 3 | `9695f10e` green: … | green | `process(QueueMessage<String>)`; field `queueClient`. Golden and functional tests pass on v1 through the bridge. 6 tests |
| 4 | `b6c21143` red: error-processor runs on the cloud-sdk clients … | red | `AwsSdkBoundaryArchTest` (15 + 18 violations); `ExternalServicesModuleTest` (S3/SNS settings = v1 `new ClientConfiguration().withMaxErrorRetry(0)`, read from the v1 class; null skeleton); functional and golden tests on `CloudFunctionalTestBase` (events from the notification fake), plus archive `text/plain` and 4 health-check names |
| 5 | `b0542f42` green: … | green | [D38](../decisions.md#d38). `ExternalServicesModule(configuration, lifecycle)` installs `CloudServicesModule(pickup, topic)` with storage, storage-download and notification = `parameterStore().withMaxRetries(0)`, and keeps `Clock`. `MessageQueueListener`; health checks on the injected clients; `StorageConfigurationProvider`. The golden test passes on the fakes. 10 tests |
| 6 | `d5100c3d` red: cloud-sdk logs only warnings in error-processor | red | Logger level test |
| 7 | `754785f8` green: … | green | `error-processor.yaml`: `com.inttra.mercury.cloudsdk: WARN`. 11 tests |
| 8 | `6b123918` test: disabled test for the known error-processor recipient defect | test | [A12](../actions.md#a12), design open issue 6. Fails when enabled |
**Full reactor build of `6b123918`** ([G4](../rules.md#g4) worktree): green. The first run (6:16 min) stopped at `consumer-commons` on the [F14](../findings.md#f14) time-zone flake; it was resumed with `-rf :consumer-commons` and `JAVA_TOOL_OPTIONS=-Duser.timezone=UTC` and passed (3:31 min). error-processor 12 (1 skipped); every other count unchanged (shared 1818, functional-testing 48, event-writer 3 on this branch, consumer-commons 149). PR description: `pr-details/2026-11-18-apway-pr-2-error-processor-description.md`.


**Rebase and pre-review (2026-11-19).** PR #4 merged as `62b07687`; the local branch was rebased onto it (clean, old hashes in the PR doc). Before publishing, an independent review (`code-review` skill, high) plus my own read: 10 points, outcomes in the PR doc's Part 2. Changes made:

| # | Commit | Type | Change |
|---|---|---|---|
| 9 | `4302af53` refactor: v1 storage and notification settings spelled out | refactor | `V1_DEFAULTS_WITHOUT_RETRIES` no longer derived from the parameter-store role |
| 10 | `4b410a4e` refactor: names the email queue, not SQS | refactor | [D25](../decisions.md#d25) |
| 11–12 | `9ee58250` / `64b1e2d4` logs the cloud clients closing at shutdown | red / green | `ManagedCloudResource` logger at INFO under the cloud-sdk WARN ([A27](../actions.md#a27) needs the close lines) |
| 13 | `bd4ea501` test: production external services module binds what the service injects | test | `ExternalServicesModuleWiringTest`: real clients, no request |
| 14–15 | `5035f0fd` / `a36edccc` health checks retry like v1 | red / green | Arijit's decision: shared `RetryingHealthCheck` (3 retries, 100/200/400 ms); storage-read and publish wrapped. +6 shared, +4 error-processor tests |

Kept as is: payload parsed outside the `try` (existing defect), recipients not trimmed (existing), the pom's `aws-java-sdk-sqs` pin (removing it would downgrade v1 sqs/core 1.12.730 → 1.12.720; goes with step 5). Deferred: shared constant for the v1-defaults-without-retries settings (decide with email-sender), shared test helpers (functional-testing follow-up).

**Full reactor build of `a36edccc`:** green in 8:48 min; error-processor 17 (1 skipped), shared 1831, every other count unchanged. Pushed and raised as [PR #5](https://github.com/wtg-e2open/INTTRA.appianway/pull/5) (mergeStateStatus CLEAN).
