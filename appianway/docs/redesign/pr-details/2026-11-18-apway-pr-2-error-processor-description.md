# PR — WI01124532 error-processor: cloud-sdk clients and the shared adapters

Branch `WI01124532-aws-sdk-upgrade-error-processor` → `feature/WI01124532-aws-sdk-upgrade` (rebased onto `62b07687`, after PR #4) · 15 commits `33e3ff98` … `a36edccc` · [PR #5](https://github.com/wtg-e2open/INTTRA.appianway/pull/5), **merged** 2026-11-19 as `ff281fa1` (no Copilot comments)

- **Part 1** is the PR description for GitHub; copy everything between the two `✂` lines.
- **Part 2** is your review guide, for you only. It does not go into the PR.

Suggested PR title: `WI01124532 error-processor: cloud-sdk clients and the shared adapters`

---

## Part 1 — PR description (GitHub)

✂ ------------------------------------------------------------------

## Link to Story/Defect this work relates to

**WI01124532**: AppianWay AWS SDK v1 → v2 upgrade. This PR moves error-processor onto the `shared` cloud-sdk adapters, as #4 did for event-writer.

## What/Why I Did the changes

error-processor reads failure messages from its pickup queue, archives each one in the workspace bucket, sends one message per configured recipient to the email queue, and publishes a CLOSE_WORKFLOW event. It now does this through cloud-sdk (AWS SDK 2.x) instead of AWS SDK v1. The archive, the email-queue messages and the event are unchanged.

| | Before (SDK v1) | After (cloud-sdk) |
|---|---|---|
| Clients | `ExternalServicesModule`: `AmazonSQS` ×2, `AmazonS3`, `AmazonSNS` | `ExternalServicesModule` installs `shared` `CloudServicesModule`; `Clock` binding kept |
| Storage and notification settings | `new ClientConfiguration().withMaxErrorRetry(0)`: SDK v1 defaults, no retries | The same values, as settings overrides |
| Listener | `SQSListener` | `MessageQueueListener` |
| Task message type | SDK v1 `Message` | `QueueMessage<String>` |
| Event publisher | `SNSEventPublisher` | `NotificationEventPublisher` |
| Health checks | each built its own default client (3 retries) | run on the service's clients; same names, placement and retries |
| Configuration from storage | `S3ConfigurationProvider` | `StorageConfigurationProvider` |
| Functional tests | JUnit 4, SDK v1 fakes | JUnit 5 `CloudFunctionalTestBase`, cloud-sdk fakes |

### Changes

1. **Proof first**
   - **Functional test re-enabled:** the happy-flow test had not run since 2021, when its `@Test` was removed. It passes on the v1 code once its event fixture matches today's event.
   - **Golden test:** compares the exact archived object, email-queue message and CLOSE_WORKFLOW event with output written by the v1 code. It passes before and after the change.
2. The task works on `QueueMessage<String>`. Its tests cover the archive key and body, one message per recipient, the workflow ids and the failure path.
3. `ExternalServicesModule` installs `CloudServicesModule` with the v1 storage and notification settings. The application builds it from its configuration; the functional tests pass the fakes instead. A separate test builds the production module with the real clients (no request is sent) and checks every binding.
4. `error-processor.yaml`: cloud-sdk logs at WARN (it logs every storage call at INFO), except the one line per client that shows it closing at shutdown.
5. An architecture test fails the build if error-processor uses an AWS SDK type or a `shared` SDK v1 class.
6. One existing defect is kept, with a disabled test asserting the correct behaviour: with several recipients, every email-queue message carries the first address.
7. **Health checks retry like v1** (`shared` `RetryingHealthCheck`, new): the storage-read and publish checks run again up to 3 times while unhealthy, with a short doubling pause, as the v1 default clients retried. The queue checks need no wrapper: their clients retry 3 times.

Shutdown needs no change here: the shared listener manager from #4 lets the messages in progress finish, and closes the queue clients before storage.

### Backward compatibility

- **Same output:** the archive (key, body, `text/plain`), the email-queue messages and the event are byte-identical (golden test).
- **Same client settings** for the clients that process messages (queues, storage, notification) as their SDK v1 counterparts, including no retries for storage and notification.
- **Same health checks:** the same names on the default and the ops endpoint, and the same retries. In v1 each check built its own default client, which retried a failed call 3 times. The checks now run on the clients above; the storage-read and publish checks, whose clients have no retries, retry 3 times themselves.
- **Same configuration keys;** the only YAML change is the logger lines.

## Next Steps

- INT: boot error-processor and send a failure message. Check that the archive, the email-queue message and the event match the v1 build.
- INT: stop the service while messages are being processed. The log should show the clients closing, and every message in progress should be either fully processed and deleted or delivered again.
- Next service: email-sender.

## Testing Notes

- **Test counts:** error-processor ran 2 tests (the functional test was off). It now runs **17**, 1 of them skipped (the disabled defect test):
  - task (4), client settings (1), production module wiring (1), health checks (4), architecture (2);
  - functional (3): happy flow, health checks, logger levels;
  - golden (1);
  - known defect (1, disabled). It fails when enabled.
- `shared` gains 6 tests (`RetryingHealthCheckTest`).
- **Test-first:** each behaviour change has a failing test first, then the change.
- **Full reactor build** (`mvn -B clean verify`) of `a36edccc`: **BUILD SUCCESS** in 8:48 min, all 26 build units, 0 failures and 0 errors. Only error-processor (2 → 17) and shared (1825 → 1831) changed their test counts.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

✂ ------------------------------------------------------------------

---

## Part 2 — Review guide (for you only, not in the PR)

### Commits

Rebased on 2026-11-19 onto the feature branch after PR #4 merged (`62b07687`); the rebase was clean. Old hashes in brackets.

| # | Commit | What to look at |
|---|---|---|
| 1 | `33e3ff98` (`0f5f3037`) test: characterize … | F13. `notifications.json` diff (stale fixture), the pickup body added from the fixture file (the old CRLF copy only matched on Windows), `wire/happy.expected.txt` (v1 output, never regenerated) |
| 2–3 | `dd4a2879` / `1ce61e24` | Task test now JUnit 5; `getBody()` → `getPayload()`; `sqsClient` → `queueClient` (D25) |
| 4–5 | `83fb8e32` / `3d607a10` | D38: `ExternalServicesModule` kept (it binds `Clock`); `ExternalServicesModuleTest` against the v1 `ClientConfiguration`. Health checks now on the injected clients (sender client for the outbound check). The golden test passes on the fakes |
| 6–7 | `beabb256` / `0f42b19c` | Logger WARN |
| 8 | `37381790` | Recipient defect (design open issue 6), disabled |
| 9 | `4302af53` refactor | Pre-review: `V1_DEFAULTS_WITHOUT_RETRIES` spelled out (10 s, 50 s, no API-call timeout, 50, 0) instead of `parameterStore().withMaxRetries(0)`, which only happened to match |
| 10 | `4b410a4e` refactor | Pre-review: `sendMailMessageToSQS` → `sendMailMessageToEmailQueue` (D25) |
| 11–12 | `9ee58250` / `64b1e2d4` | Pre-review: WARN on the whole cloud-sdk tree also hid `ManagedCloudResource`'s "Closing … on application shutdown" lines, which the INT shutdown check (A27) needs. YAML keeps that one logger at INFO |
| 13 | `bd4ea501` test | Pre-review: `ExternalServicesModuleWiringTest`, the production module with real clients (`aws.region` system property, no request), every binding plus 4 managed clients. Fails if the `Clock` binding or the topic is dropped. Does not check the client settings (not visible from outside shared); `ExternalServicesModuleTest` pins the values |
| 14–15 | `5035f0fd` / `a36edccc` | Your decision (2026-11-19): health checks retry like v1. Shared `RetryingHealthCheck` (decorator, keeps the name via `HasName`; 3 retries, pause 100/200/400 ms; retries any failure, where v1's SDK retried only retryable ones: same result, slower on a permanent error). `ErrorProcessorApplication.readHealthChecks` / `writeHealthChecks` (package-private, structure only, in red) so `ErrorProcessorHealthChecksTest` runs the real checks on mock clients that fail, then recover. Only storage-read and publish are wrapped |

### Pre-review (2026-11-19): what was checked and why

An independent code review of the branch (the `code-review` skill, high), plus my own read, before publishing. 10 points:

| # | Point | Outcome |
|---|---|---|
| 1 | Payload parsed outside the `try`: a malformed message never reaches the error handler, and is redelivered until the queue's redrive | Existing v1 defect, unchanged. Kept (known-defects policy); could join `ErrorProcessorKnownDefectsTest` later |
| 2 | Storage-read and publish health checks now have 0 retries (v1 checks: default clients, 3 retries) | Real change. **Fixed on your decision** (commits 14–15): they retry 3 times again |
| 3 | WARN on the whole cloud-sdk tree hides the shutdown close lines | Fixed (commits 11–12). **event-writer (merged) has the same broad WARN**: tracked under A27 |
| 4 | Production `ExternalServicesModule` wiring untested | Fixed (commit 13) |
| 5 | Pom still declares `aws-java-sdk-sqs` | Checked: removing it downgrades `aws-java-sdk-sqs`/`-core` from 1.12.730 to shared's 1.12.720 (it pins the newer v1). Kept until step 5 removes SDK v1 |
| 6 | Move the v1-defaults constant to shared `ClientSettings` | Deferred to email-sender (next service with `withMaxErrorRetry(0)` clients) |
| 7–8 | Duplicated test helpers (`TestQueueMessage`, the shared v1 class list) | Follow-up for functional-testing |
| 9 | Golden test's `await()` 10 s default | False positive: `IntegrationTestExtension` sets Awaitility's default to 30 s |
| 10 | Recipients not trimmed; SQS in a method name | Trim: existing defect, kept. Name: fixed (commit 10) |

### Notes

- **The functional test is back on after 5 years.** Enabling it is a test-only change, but it is why the error-processor test count rises by more than the new tests alone.
- **Health-check retries:** decided (align with v1), done in commits 14–15.
