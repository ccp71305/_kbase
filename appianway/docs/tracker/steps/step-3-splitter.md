# Step 3 — splitter (`WI01124532-aws-sdk-upgrade-splitter`)

← [Tracker home](../README.md) · [All steps](README.md)

Cut 2026-11-19 from the feature branch at `07b5106f` (after PR #7). Design page: `docs/redesign/2026-10-30-apway-WI01124532-splitter.md`. Existing defects from the review summary: a data race in parallel group routing (parent `MetaData` projections), full document content logged at INFO ([known defects](../known-defects.md), [A12](../actions.md#a12)).

**Baseline (2026-11-19, `07b5106f`):** splitter runs 179 tests, 0 failures, 2 skipped (`mvn -B -q -pl splitter -am test`). 63 production classes, 4 of them import SDK v1 directly.

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `fcc07a08` test: characterize what splitter sends, stores and publishes | test | Golden test (7 cases) on v1, `wire/*.expected.txt` written by v1. The v1 happy-flow functional tests are `@Ignore`d since 2018 (they stub the wrong format service: NPE, error queue); the golden test stubs `FormatService` correctly. Normalized: message id, wall-clock start time of per-transaction failure events, random ids by first appearance (fake retries race). Stable 4 runs in a row. splitter 179 → 186 |
| 2 | `9568dbdb` test: characterize how splitter writes split documents and retries failures | test | ISO-8859-1 bytes incl. non-ASCII under `<root>/<id>`, size read from that key; retained document not written; real ErrorHelper with `RecoveryConfig(true, 1, 150)`: one retry after 300 s with failedAttempts 1, then `_dlq`. Green on v1. splitter 186 → 189 |

| 3–4 | `c1f337c9` / `06e2bec3` task, transaction processor and error handler on received queue messages | red / green | Tests pass a `TestQueueMessage` record (with `failedAttempts` for a retry) and mock `MessageQueueClient`; JUnit 4 kept; a typed `anyQueueMessage()` matcher keeps stubs unambiguous while both overloads exist. Red: 57 errors (48 "not yet", 9 functional/golden timeouts from the task throwing). Green: v1 overloads removed; `sqsClient` / `sqsMessage` / `sendToSqs` renamed to queue names (D25). splitter 189, 0 failures, 2 skipped, stable on two runs |

**Test-run note (2026-11-19):** `mvn -pl splitter -am test` also runs every upstream module's tests; under that load `SplitterFuncTest` hit its 35 s timeouts while Dropwizard was still starting (twice: red and the first green run). Run alone it passes in 7–13 s. Faster loop: `mvn -o -q -pl splitter -am install -DskipTests` once, then `mvn -o -q -pl splitter test` (46 s).

| 5–6 | `b449af6e` / `691c02cd` the service on `CloudServicesModule` | red / green | Functional tests on `CloudFunctionalTestBase` (2 active v1 tests unchanged; the 2 `@Ignore`d since 2018 not carried over, covered by the golden test); health checks by name and **v1 placement** (default: pickup, Network Services, error rate; ops: no error rate, both outbound queues, topic, workspace write); logger levels; wiring test (replaces 14 constructor-only tests); boundary ArchUnit. Golden: `splitterFileSize` was 0 in v1 only because the v1 fake's HEAD is hard-coded ([F28](../findings.md#f28)); the test checks the real length, then prints 0. splitter 178, 0 failures |
| 7 | `a101fcb1` build | build | Direct `aws-java-sdk-sqs` removed |
| 8 | `68f5ad49` known defects KD-8, KD-9 | test | Race (900/1000 wrong control numbers; the fix needs a deep copy) and content at INFO. Each fails enabled, passes with the fix |
| 9 | `5aad26b2` refactor | refactor | Unused queue client removed from the processor (pre-review point 6) |
| 10 | `337cf1a7` known defects KD-10, KD-11 | test | From the pre-review: validate fall-through, error-rate meter. Verified both ways |
| 11 | `8feabd5f` defect dates | test | `@Disabled` reasons give the start month (`git log -S`) |

**Pre-review (code-review skill, high, 07b5106f..68f5ad49):** 10 points; outcomes in the [PR doc](../../redesign/pr-details/2026-11-19-apway-pr-3-splitter-description.md#pre-review-2026-11-19). New: [KD-10](../known-defects.md#kd-10), [KD-11](../known-defects.md#kd-11), [F26](../findings.md#f26) (Arijit's decision), [F27](../findings.md#f27).

**Result:** splitter 179 (2 skipped) → **182 (4 skipped, the disabled defect tests)**. Full build of `337cf1a7` (`JAVA_TOOL_OPTIONS=-Duser.timezone=UTC mvn -B clean verify -Daether.enhancedLocalRepository.trackingFilename=_any.repositories`): **BUILD SUCCESS**, 10:31 min, 26 units, 0 failures. (An earlier offline `install` run stopped at the watermill consumers on the known `dynamo-client:1.0` resolution, environmental.) **[PR #8](https://github.com/wtg-e2open/INTTRA.appianway/pull/8) raised 2026-11-19.**

| 12 | `e36bc10f` golden test with one pickup worker | test | Copilot review on PR #8: a retry could overtake its first attempt and reorder events; own properties file with `maxNumberOfMessages=1` ([D44](../decisions.md#d44)); thread answered and resolved |

**Runtime test 5 on QA (2026-11-19 evening): passed** ([runtime/splitter.md](../runtime/splitter.md#test-5)). An IFTMBF booking (kept) and an IFTMBC file with two confirmations (split): routed `MetaData`, documents and events identical to v1 and to QA's own run; queue names work; Ctrl+C closes the 4 clients. Inputs and outputs saved for transformer: [fixtures](../runtime/fixtures/test5-splitter-outputs/README.md).

**PR #8 updates (2026-11-20):** Next Steps marked verified on QA; comment answering Copilot's "Needs a closer look" (QA boot, output parity, shutdown) with the run's results; the `splitterFileSize` note removed from the description; known defects not fixed ([D43](../decisions.md#d43)).

**Merged 2026-11-20 01:25 UTC** as `222d58be` (PR #8). Next: [transformer](step-3-transformer.md).
