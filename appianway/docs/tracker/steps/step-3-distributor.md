# Step 3 — distributor (`WI01124532-aws-sdk-upgrade-distributor`)

← [Tracker home](../README.md) · [All steps](README.md)

Cut 2026-11-20 from the feature branch at `e90a355a` (after PR #10). Design page: [distributor design](../../redesign/2026-10-30-apway-WI01124532-distributor.md). distributor-rest follows in its own PR (Arijit agreed to separate PRs 2026-11-20).

**Baseline (2026-11-20, `e90a355a`):** distributor runs 48 tests, 0 failures, 4 skipped (the 4 functional tests, `@Ignore`d: they bind the wrong Network Services types) (`mvn -o -pl distributor clean test`, 21 s). 28 production classes, 5 use SDK v1 or the shared v1 classes.

**What distributor does:** reads the `MetaData` from its pickup queue (`inttra2_qa_sqs_file_delivery`), resolves the delivery file name, delivery path and archive path from Network Services attributes and tokens, optionally zips the workspace document (stored as `{rootWorkflowId}/{uuid}.zip`), copies it from the workspace bucket to the outbound bucket twice (delivery key, then archive key) with replaced user metadata (root, parent and workflow ids, outbound integration profile format id, context code, outbound EDI id, pick-up time and reprocess flag when present), and publishes a `CLOSE_WORKFLOW` event.

**AWS today (SDK v1):** `ExternalServicesModule` (SQS ×2, S3, SNS clients, `ParameterStoreModule`), `DistributorModule` (v1 listener), `DistributorTask` (v1 `Message`, `SQSClient`), `ZipCompression` (concrete `S3WorkspaceService`), `DistributorApplication` (`S3ConfigurationProvider`, v1 health checks).

<a id="findings"></a>
**Findings while preparing (2026-11-20):**
- The v1 S3 fake drops the user metadata on a copy and stores content as text: the golden test captures each copy request (target bucket and key, user metadata) through a spy instead; after the port, the cloud-sdk fake stores both.
- The zip's key has a `UUID.randomUUID()` (not the injectable random generator) and the zip bytes carry the entry time: the golden test normalizes the key and compares the entry name and content, not the bytes.
- Design open issue 2: v1 sends no content type on the copy (the v1 client adds `application/octet-stream`); the shared adapter passes it explicitly. Checked on QA's real objects in the runtime test.
- The two error cases hit the duplicate-token defect the [known-defects page](../known-defects.md) predicted for distributor ("every failure"): the shared error handler fails on `pickupQueue` given twice, so the error-queue message and annotations are written, no event is published and the message is not deleted (in QA: delivered again until the redrive). To record as a known-defect test.
- Design open issue 3: three metadata values can be null (outbound IPF id, context code, outbound EDI id). What v1 stores then is not known; to characterize from a real QA-delivered object (read) and in the runtime test.

<a id="plan"></a>
**Plan:**
1. Golden test on v1: real `MetaData` from the QA traces (file-delivery inputs), plain and zipped, a missing attribute (error path), Network Services stubbed by id; captures queue messages, copy requests, workspace objects, events.
2. Red/green pairs as for the earlier services: task on `QueueMessage<String>`; `ZipCompression` on `WorkspaceService`; the service on `CloudServicesModule` with health checks on the injected clients; logger lines; boundary test.
3. Known defects (disabled tests), from the review summary §4.
4. Full build, pre-review, PR; runtime test 8 on QA: borrowed DLQ; **real deliveries into QA's outbound bucket approved by Arijit 2026-11-20** ("ok to use outbound bucket, we are not changing anything and it is QA only"), marked workflow ids.

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `6b3bd51d` test: characterize what distributor delivers, stores, sends and publishes | test | Golden test on v1, 6 cases from the two real QA distributor inputs (CONTRL FA, X12 301 with `fileNameToken.*`), zipped, optional metadata absent + reprocess, no outbound IPF id, no delivery path. Delivery attributes as QA uses them: the 301 key has the shape of QA's real one. Captures copy metadata from the copy request (the v1 fake drops it), zip by entry, queues, events, deletes. v1 sends `contextcode=null`, `outboundediid=null` in the copy when absent (stored result: QA check). Inputs: [fixtures/distributor-golden/make-golden.py](../runtime/fixtures/distributor-golden/make-golden.py). Stable on 3 runs; 48 → 54 (4 skipped) |
| 2–3 | `7d909297` / `f7c5af6e` task on received queue messages | red / green | `TestQueueMessage` (9th copy); `MessageQueueClient` (v1 wiring: `@ImplementedBy` → `SQSClient`); payload instead of body; error handler queue-message overload. 54 (4 skipped) |
| 4–5 | `cf136a58` / `2f921625` zip handler on the workspace interface | red / green | `ZipCompression` takes `WorkspaceService`; new test checks the zip (entry name and bytes, ISO-8859-1 names, `<root>/<uuid>.zip` as the source, `.zip` extension). 54 → 55 (4 skipped) |
| 6–7 | `6d850283` / `5f15beca` distributor on the shared cloud-sdk clients | red / green | As transformer: `CloudServicesModule(lifecycle, pickup, topic).withParameters(usePassThrough, …)`; `MessageQueueListener` + the shared `ListenerManager` (drain); health checks on the injected clients (same names; default: pickup, Network Services, error rate; ops: + error queue, event topic); `StorageConfigurationProvider`; yaml loggers; `ZipCompression` without SDK v1 `IOUtils` (the boundary test found it). Tests: JUnit 5 base on cloud fakes, golden unchanged, `DistributorFuncTest` (content type `application/octet-stream`, health checks, loggers) replaces the 4 `@Ignore`d tests, wiring test (pass-through both ways), boundary test (no allowance). Removed: the ignored tests' fixtures. 55 → 58, 0 skipped. Committed after 8–10 |
| 8–9 | `5d3bf3bc` / `c50b8f0c` shared: a null user-metadata value stored as "" ([F31](../findings.md#f31)) | red / green | Found by the golden test on the cloud fake (null rejected) and the QA experiment (SDK 2.x drops it, v1 stored ""). `StorageWorkspaceService.trimmed`: null → "". Callers: distributor (copy), dispatcher (put: values from S3, never null). shared 1846 tests, 1 skipped |
| 10 | `385559f2` golden file: v1's null shown as stored | test | The v1 capture read the copy request (`contextcode=null`); S3 stored `""` (QA experiment): those two values corrected in `optional-metadata.expected.txt`, nothing else |
| 11 | `d1bc2836` known defects [KD-18](../known-defects.md#kd-18), [KD-19](../known-defects.md#kd-19) | test | `DistributorKnownDefectsFuncTest` (2, disabled), checked both ways (enabled: never deleted / meter 0; with the fixes: pass); fixes removed. [KD-20](../known-defects.md#kd-20) (not idempotent on redelivery) listed without a test (no small fix). 58 → 60, 2 skipped |
| 12 | `d879fe3e` build: drop the SDK v1 SQS dependency | build | Direct `aws-java-sdk-sqs` removed; upper-bound rule passes; 60 tests in the build worktree (clean) |
| 13 | `007d96cd` pre-review fixes | fix | A storage failure and its retry tested again (no document: `RecoverableException`, back on the pickup queue with `failedAttempts` 1 to 5, then the `_dlq`, nothing delivered); names after the cloud-sdk concepts (`queueClient`, `workspaceService`); imports sorted. 60 → 61, 2 skipped |

<a id="pre-review"></a>
**Pre-review (2026-11-20):** `code-review` skill, high, on `e90a355a..d879fe3e`. No new bug; 7 points:

| # | Point | Severity | Verdict |
|---|---|---|---|
| 1 | Every failure loops (duplicate `pickupQueue` token) | pre-existing | Already [KD-18](../known-defects.md#kd-18), disabled test |
| 2 | The error-rate check reads the wrong meter | pre-existing | Already [KD-19](../known-defects.md#kd-19), disabled test |
| 3 | An unparsable `MetaData` body loops until the redrive | pre-existing | **Agreed**: [KD-21](../known-defects.md#kd-21), no test (the fix needs a decision) |
| 4 | `ZipCompression` writes the zip to the message's bucket, the copy reads the configured workspace bucket | pre-existing | **Latent**: both are `inttra2-qa-workspace` in QA (and the same in production); unchanged, noted here |
| 5 | No test of a storage failure and its retry | nit | **Fixed** (commit 13) |
| 6 | SQS/S3 names in migrated code ([D25](../decisions.md#d25)) | nit | **Fixed** (commit 13) |
| 7 | Import order | nit | **Fixed** (commit 13) |

**Full reactor build:** `d879fe3e` BUILD SUCCESS 10:46 min; **`007d96cd` (PR head) BUILD SUCCESS, 26 modules, 11:08 min**. **Runtime test 8 passed** ([runtime/distributor.md](../runtime/distributor.md#test-8)).

**PR [#11](https://github.com/wtg-e2open/INTTRA.appianway/pull/11) raised 2026-11-20** from `007d96cd` (feature tip `e90a355a` an ancestor: no rebase). Description: [PR doc](../../redesign/pr-details/2026-11-20-apway-pr-3-distributor-description.md).
