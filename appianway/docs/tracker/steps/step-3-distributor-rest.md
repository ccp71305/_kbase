# Step 3 — distributor-rest (`WI01124532-aws-sdk-upgrade-distributor-rest`)

← [Tracker home](../README.md) · [All steps](README.md)

Cut 2026-11-20 from the feature branch at `7f186c89` (after PR #11). Design page: [distributor-rest design](../../redesign/2026-10-30-apway-WI01124532-distributor-rest.md). The shared bearer token is recorded as an existing defect, not raised with QA ([A5](../closed-items.md#a5), Arijit 2026-11-20).

**Baseline (2026-11-20, `7f186c89`):** distributor-rest runs 142 tests, 0 failures, 0 skipped (`mvn -o -pl distributor-rest clean test`, 32 s). 19 production classes, 4 use SDK v1 or the shared v1 classes. No functional test.

**What distributor-rest does:** reads the `MetaData` from its pickup queue (`inttra2_qa_sqs_rest_delivery`); with a subscription id, reads the document from the workspace (ISO-8859-1), finds the subscription in Network Services, gets an OAuth token from the subscriber (Basic credentials), POSTs the document to the subscriber's webhook (`application/json`, bearer token, the subscription's message headers) and publishes a close-workflow event with the e2open transaction id; without one, only the event (empty transaction id).

<a id="findings"></a>
**Findings while preparing (2026-11-20):**
- QA's distributor-rest is running (1 task) but processed **no message in the last 14 days** (CloudWatch, read): no real QA traffic to borrow for the runtime test.
- No health check is registered (only Dropwizard's deadlocks), although the configuration has `healthCheckConfig`; kept as is.
- `DistributorApplication.run` catches an injector failure, prints it and continues, then fails on the null injector (a less clear error); kept as is.
- `RestServiceClient` is built with the unqualified `Client` and the Network Services `Retryer` (constructor), then Guice injects its `@Inject @Named` **final** fields with the REST client (60 s timeouts) and the REST retryer: what is used is right, by an unusual route. The golden test binds the same.
- Existing defects seen in the golden test: one cached OAuth token for all subscribers (the second subscriber gets the first's token); a FAILURE answer is wrapped as recoverable (no event, not deleted, back until the redrive); the request is built from the subscription's **first** action's parameters, not the EDI_WEBHOOK one (nothing posted, not deleted).
- The document is read as ISO-8859-1 and posted as UTF-8 JSON (`é` → `C3 A9` on the wire): existing behaviour, recorded.

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `ef5598e6` test: characterize what distributor-rest posts, sends and publishes | test | Golden test on v1, 6 cases: delivery, no subscription, 401 then new token, FAILURE answer, shared token across two subscribers, webhook not the first action. A local `HttpServer` plays the subscribers; requests recorded with the headers the service sets and the body bytes. Stable on 3 runs; 142 → 148 |
| 2–3 | `72b7eb09` / `9daad89e` task on received queue messages | red / green | `TestQueueMessage` (10th copy); `MessageQueueClient` (v1 wiring: `SQSClient`); payload instead of body; error handler queue-message overload. 148 |
| 4–5 | `1448aa42` / `49034d10` distributor-rest on the shared cloud-sdk clients | red / green | As distributor: `CloudServicesModule(lifecycle, pickup, topic).withParameters(usePassThrough, …)`; `MessageQueueListener` + the shared `ListenerManager` (drain); `StorageConfigurationProvider`; no health check (as v1); HTTP pieces unchanged; yaml loggers. Tests: JUnit 5 base (cloud fakes + subscriber server), golden unchanged, `DistributorRestFuncTest` (deadlocks only, loggers), wiring test (REST client timeouts, REST retryer, cached subscriptions), boundary test; `DistributorModuleTest` 41 → 30 (the removed v1 providers). 148 → 143 |
| 6 | `c3075b06` known defects [KD-22](../known-defects.md#kd-22) to [KD-25](../known-defects.md#kd-25) | test | `DistributorRestKnownDefectsFuncTest` (4, disabled): per-subscriber token, FAILURE answer handled, handled failure deleted with its event, webhook not first. Checked both ways (enabled: all 4 fail; with the 4 fixes: pass); fixes removed. 143 → 147, 4 skipped |
| 7 | `1c8900da` build: drop the SDK v1 SQS dependency | build | Upper-bound rule passes; 147 tests in the build worktree (clean) |
| 8 | `22ae5a87` pre-review fixes | fix | Unused SDK v1 CloudWatch import in a test helper removed; module-test names after the cloud-sdk concepts; the golden test's javadoc. 147, 4 skipped |

<a id="pre-review"></a>
**Pre-review (2026-11-20):** `code-review` skill, high, on `7f186c89..1c8900da`. No new bug; 10 points:

| # | Point | Severity | Verdict |
|---|---|---|---|
| 1–4 | Duplicate token on a handled failure; FAILURE answer wrapped as recoverable; one OAuth token for all subscribers; webhook not the first action | pre-existing | Already [KD-24](../known-defects.md#kd-24), [KD-23](../known-defects.md#kd-23), [KD-22](../known-defects.md#kd-22), [KD-25](../known-defects.md#kd-25) with disabled tests |
| 5 | An unparsable pickup message loops until the redrive | pre-existing | **Agreed**: [KD-26](../known-defects.md#kd-26), no test (as KD-21) |
| 6 | `run` swallows an injector failure; now slightly more likely (cloud clients and parameters built at injection) | pre-existing | **Noted**, kept: the service still fails to start, with the cause on standard error |
| 7 | No event topic now fails the start (v1 failed at the first publish) | nit | **Noted**: every environment sets `distributor.snsEventConfig.topicArn` |
| 8 | An unused SDK v1 import in `Helper.java` | nit | **Fixed** (commit 8) |
| 9 | `Sqs` names in the module test | nit | **Fixed** (commit 8) |
| 10 | The golden test's javadoc | nit | **Fixed** (commit 8) |

**Full reactor build:** `1c8900da` BUILD SUCCESS, 26 modules, 11:53 min (the PR head `22ae5a87` changes tests only; distributor-rest re-run: 147 tests, 4 skipped). **Runtime test 9 passed** ([runtime/distributor-rest.md](../runtime/distributor-rest.md#test-9)).

**PR:** [#12](https://github.com/wtg-e2open/INTTRA.appianway/pull/12) raised 2026-11-20 to `feature/WI01124532-aws-sdk-upgrade` (head `22ae5a87`). Description: [PR doc](../../redesign/pr-details/2026-11-20-apway-pr-3-distributor-rest-description.md).

**Copilot review (2026-11-20):** one comment, accepted: the subscriber server trimmed the bodies, so a whitespace change would pass. `23f13414` records them exactly (backslash, CR, LF escaped); re-recorded on v1 (`ef5598e6`): only the document's final LF appears on the 6 body lines, and v1 posts it too. 147 tests, 4 skipped. Replied on the thread.

**Merged 2026-11-20** as `36a14ced` (9 commits, head `23f13414`).
