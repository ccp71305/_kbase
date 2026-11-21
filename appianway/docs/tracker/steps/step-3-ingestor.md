# Step 3 — ingestor (`WI01124532-aws-sdk-upgrade-ingestor`)

← [Tracker home](../README.md) · [All steps](README.md)

Cut 2026-11-20 from the feature branch at `bef71a96` (after PR #9). Design page: [ingestor design](../../redesign/2026-10-30-apway-WI01124532-ingestor.md). Existing defects from the [review summary §4](../../redesign/2026-10-30-apway-WI01124532-review-summary.md): any exception drops and deletes the whole batch; event documents are indexed without ids, so a redelivered batch duplicates them; the Jest pool defaults to 2 connections per route against 8 listener threads (performance, not a test).

**Baseline (2026-11-20, `bef71a96`):** ingestor runs 179 tests, 0 failures, 0 skipped (`mvn -o -pl ingestor clean test`, 41 s). 36 production classes, 7 import SDK v1 directly (the two modules, the listener-side task classes on `Message`, the error handler).

**What ingestor does:** reads the SNS-wrapped lifecycle events from its queue (`inttra2_qa_sqs_ingest`, subscribed to the event topic) with 8 listener threads, builds tracking attributes per workflow (Network Services format and integration profile lookups), reads the annotations of a failed `closeRun` from the workspace, writes one bulk request of event documents to `txtrack-event-<date>` and one upsert per workflow to `txtrack-agg-<date>` in Elasticsearch (Jest with the SigV4 signer), and deletes every message, whatever happened. A job deletes indices older than 7 (events) / 30 (aggregates) days in QA, first 24 h after start.

**AWS today (SDK v1):** `ExternalServicesModule` builds `AmazonSQS` ×2 (listener, sender) and `AmazonS3`; `ParameterStoreModule` (SDK v1 SSM) for the Network Services credentials; the health check `InboundSqsHealthCheck` builds its own default client; `JestModule` signs with the v1 `DefaultAWSCredentialsProviderChain` (kept, design option 1). No event topic: ingestor publishes nothing.

<a id="findings"></a>
**Findings while preparing (2026-11-20):**
- The functional test runs nothing: one empty `@Test` method, the four real ones commented out since 2018 ("TODO: Will fix functional test"); `FakeJestClientImpl` supports only `Index`, while the code sends `Bulk` and `Update`. So today no test checks the Elasticsearch requests end to end: the golden test is the first.
- The module `ErrorHandler` has no caller (design open issue 6): retype only.
- Index names use `LocalDateTime.now()` in the JVM's default zone (UTC on ECS; the golden test normalizes the date).
- The purge job (Wisp `fixedDelaySchedule(24 h)`) first runs 24 h after start (`FixedDelaySchedule.nextExecutionInMillis` = now + frequency, checked in the jar), so a short local run never deletes an index.
- QA's Elasticsearch has a public endpoint (`search-inttra2-qa-es-tx-tracker-….es.amazonaws.com`); a local run would **write** test documents into QA's daily indices (Arijit's OK needed, [README](../README.md)).
- The 8 listeners share one synchronous dispatcher (each batch runs on its listener thread), so the drain ([A28](../closed-items.md#a28)) goes into the dispatcher: count the batches in progress, refuse new ones after stop, wait once (20 s, as the shared manager).

<a id="plan"></a>
**Plan:**
1. **Golden test on v1** (`IngestorWireCompatibilityTest`, JUnit 4 on the v1 fakes): real QA events from the two traces ([fixtures](../runtime/README.md)), sent as their services published them (one SNS message per publish); a recording Jest client captures every request (action, method, URI, body); plus a failed `closeRun` whose annotations are read from the workspace, a failed one whose annotations object is missing, an unparsable message in a batch, and an Elasticsearch failure. Network Services stubbed by id. Expected files written by v1.
2. Red/green pairs: task, dispatcher, factory on `QueueMessage<String>` (delete through `MessageQueueClient`); `ErrorTransformer` on `WorkspaceService`; the service on `CloudServicesModule` (no event topic) with the health check on the injected client; the drain; logger lines; boundary test (the v1 credentials chain in `JestModule` allowed).
3. Known defects (disabled tests): the whole batch dropped on one bad message; a redelivered batch duplicating event documents.
4. Full build, pre-review, PR; runtime test 7 (QA with Arijit's OK, or INT).

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `e2c4b5ad` test: characterize what ingestor sends to Elasticsearch | test | Golden test on v1, 7 cases, real QA events (54 booking events one message each; 50 confirmation events in one message: 1 bulk of 50 + 3 upserts); failed run with annotations from the workspace / annotations missing; `HEALTHCHECK` on the topic (no request); Elasticsearch 400 (logged, upserts still sent) and unreachable (bulk tried 3 times, no upsert). `RecordingJestClient` records method, URI, body as the HTTP client builds them (`ElasticsearchVersion.UNKNOWN`). Inputs generated from the trace fixtures (script: [fixtures/ingestor-golden/make-golden.py](../runtime/fixtures/ingestor-golden/make-golden.py), `python -I make-golden.py <repo>`). Stable on 3 runs; 179 → 186 |
| 2–3 | `36963169` / `8c0cb5e9` task and dispatcher on received queue messages | red / green | `TestQueueMessage` (8th copy); the task deletes through `MessageQueueClient` (on v1 wiring `@ImplementedBy` resolves it to the v1 `SQSClient`); the dispatcher's v1 `submit` bridges to `dispatch` (`V1MessageBridge.toQueueMessage`) until the module pair. Logic unchanged (diff: types only). 186 → 191 |
| 4–5 | `41c746ed` / `1a9b0497` error transformer on the workspace interface | red / green | `ErrorTransformer` takes `WorkspaceService` instead of the v1 `S3WorkspaceService`; tests: annotations read from the event's bucket and file; a failed read leaves no annotations (already true). 191 → 193 |
| 6–7 | `621f657d` / `8d6854cf` ingestor on the shared cloud-sdk clients | red / green | `ExternalServicesModule(config, lifecycle)` installs `CloudServicesModule(lifecycle, pickup, null)` (no topic) `.withParameters(clientId, clientSecret)`: always the parameter store, as v1 (ignored `usePassThrough`); `JestModule` unchanged. `listenerThreads` × `MessageQueueListener` on the listener client sharing the synchronous dispatcher; module `ListenerManager` on `Listener`; `StorageConfigurationProvider` ([D31](../decisions.md#d31)); health check on the injected client (same name, default + ops); yaml loggers. Tests: functional base on JUnit 5 + cloud fakes, golden test unchanged expected files, `IngestorFuncTest` (health checks, loggers) replaces the empty test, wiring test, boundary test (allowed: the signer's v1 credentials, design NFR 1; the v1 `Message` of `Dispatcher.submit` until step 5, [D19](../decisions.md#d19)). Removed: `FakeJestClientImpl` (Index only), the commented-out tests' fixtures. 193 → 198 |
| 8–9 | `a0c84470` / `fe428633` error handler on received queue messages | red / green | No caller (design open issue 6): retype only; `ErrorHandlerTest` (35) on `TestQueueMessage`, assertions unchanged, the `ErrorHelper` queue-message overloads. The v1 `Message` is now left only in `AsyncDispatcher.submit` (allowed until step 5) and `JestModule` uses the v1 credentials chain (design exception). 198 |
| 10–11 | `62951869` / `8077d56d` shutdown drain ([A28](../closed-items.md#a28)) | red / green | The 8 listeners share one synchronous dispatcher, so the dispatcher counts the batches in progress; `drain` refuses new batches (left on the queue) and waits; the module `ListenerManager` shuts every listener down, then drains within one 20 s deadline (warning if not done). Tests: `AsyncDispatcherDrainTest` (3), `ListenerManagerTest` (3). 198 → 204. To check on the runtime test: Ctrl+C with a batch in progress |
| 12 | `431d7316` test: characterize how the Elasticsearch requests are signed | test | `ElasticsearchSigningCompatibilityTest`: the signer signs a bulk, an upsert, a settings read and an index delete (fixed example credentials and clock), each handed over as the Apache client does (wrapped, relative URI, `Host`/`Content-Length`/`Content-Type` already set: the signer is added last). Expected file written with 0.0.16. 204 → 205 |
| 13 | `497fd620` build: drop the SDK v1 SQS dependency, keep the signer version | build | `aws-java-sdk-sqs` removed; SDK v1 core from shared (1.12.730), the signer's old core excluded. **Signer kept at 0.0.16** ([F30](../findings.md#f30)): with 0.0.22 the signing test fails (no longer signs `Content-Length`). The functional tests failed once in the main tree after `clean`: VS Code's Java build emptied `target/classes` mid-run ([F7](../findings.md#f7)); module runs with `clean` now go to the build worktree too |
| 14 | `157c54e9` known defects [KD-15](../known-defects.md#kd-15), [KD-16](../known-defects.md#kd-16) | test | `IngestorKnownDefectsTest` (2, disabled) on the real task and repository with the recording client. Checked both ways: enabled, both fail for the stated reason (no request at all; `{"index":{}}` without id); with the fixes (read each message on its own; index with `eventId` as id), both pass; fixes removed. 205 → 207, 2 skipped |
| 15 | `b343f2cc` known defect [KD-17](../known-defects.md#kd-17) | test | From the pre-review: when Elasticsearch cannot be reached, the batch is deleted (process swallows the `RecoverableException`). Disabled test; checked both ways (enabled: deleted; with the rethrow: kept); fix removed. 207 → 208, 3 skipped |
| 16 | `0c31d34b` pre-review fixes | fix | INFO line when the drain leaves a batch on the queue; `submit` javadoc; signing test with session credentials (`x-amz-security-token` signed, recorded on 0.0.16). 208 → 209, 3 skipped |

<a id="pre-review"></a>
**Pre-review (2026-11-20):** `code-review` skill, high, on `bef71a96..157c54e9`. 5 points:

| # | Point | Severity | Verdict |
|---|---|---|---|
| 1 | Shutdown closes the listener client while the 8 listener threads may still be in a 20 s receive; the aborted receive would log "Exception in SQS Listener" at ERROR on every deploy | important | **Not reproduced.** Local boot of `0c31d34b` against QA (borrowed `inttra2_qa_sqs_ingest_dlq`, empty before and after; Elasticsearch pointed at `http://localhost:9`, so nothing reached QA's domain): 8 listeners started, health check healthy (0.6 s); Ctrl+C while all 8 were in their long poll, 3 runs: 0 ERROR or exception lines, the 4 clients closed, exit in 1.5–1.8 s (logs: [fixtures/test7-ingestor-boot/](../runtime/fixtures/test7-ingestor-boot/)). Transformer's runs (same shared listener) showed none either |
| 2 | When Elasticsearch fails, the batch is deleted and its events lost; the module `ErrorHandler` is dead code | pre-existing | **Agreed**: [KD-17](../known-defects.md#kd-17) (commit 15). `ErrorHandler`: no caller since 2018 (design open issue 6) |
| 3 | A batch skipped during the drain leaves no log line | nit | **Fixed** (commit 16) |
| 4 | The signing test uses only long-term credentials; ECS uses the task role's session credentials | nit | **Fixed** (commit 16) |
| 5 | `submit` javadoc out of date | nit | **Fixed** (commit 16) |

**Full reactor build** in the build worktree: `157c54e9` BUILD SUCCESS, 14:03 min; **`0c31d34b` (PR head) BUILD SUCCESS, 26 modules, 15:38 min**.

**PR [#10](https://github.com/wtg-e2open/INTTRA.appianway/pull/10) raised 2026-11-20** from `0c31d34b` (feature tip `bef71a96` is an ancestor: no rebase). Description: [PR doc](../../redesign/pr-details/2026-11-20-apway-pr-3-ingestor-description.md) (Part 1 GitHub, Part 2 review guide).

**Runtime test 7 passed (2026-11-20):** [runtime/ingestor.md](../runtime/ingestor.md#test-7).

**Merged 2026-11-20 19:41 UTC** (PR #10, merge commit `e90a355a`).
