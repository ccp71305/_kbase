# Runtime verification: distributor-rest

← [Runtime index](README.md) · [Tracker home](../README.md)

<a id="summary"></a>
## In functional terms

distributor-rest posts documents to subscribers' webhooks (EDI_WEBHOOK subscriptions) and records the delivery. **On QA the new build starts, reports healthy, takes a delivery message and publishes the same close-workflow event as the old build, and stops cleanly.** QA's distributor-rest processed no message in the 14 days before the test, and a real webhook delivery would post to a real subscriber's endpoint (outside the QA-only scope), so the HTTP delivery itself is proven by the golden test against a local subscriber server: token request, POST, headers and body identical to v1 for six cases.

How the builds are built and run: [how-to](../howto/build-and-run-a-service-locally.md). Files: [fixtures/test9-distributor-rest/](fixtures/test9-distributor-rest/).

<a id="test-9"></a>
## Test 9 (2026-11-20)

v1 = `7f186c89` (feature tip); new = the PR head's production code (`1c8900da`, the same at `22ae5a87`: later commits change tests only). Pickup `inttra2_qa_sqs_rest_delivery_dlq`, errors `inttra2_qa_sqs_subscription_errors_dlq` (borrowed, empty before and after), event topic and Network Services: QA. Input: the real QA distributor input with workflow ids marked `wi01124532-rt-drest-<build>` and no subscription id (the path that posts nothing).

| # | Time (UTC) | Action | Result |
|---|---|---|---|
| 1 | 22:1x | Pre-checks (read): the 2 borrowed DLQs | 0/0, 0/0 |
| 2 | 22:1x | Built the jars (full build at `1c8900da`: BUILD SUCCESS 11:53 min; v1 at `7f186c89`) | 92 MB each; yaml differs only in the logger lines |
| 3 | 22:23:17–22:23:29 | **WRITE** v1: started, health check, 1 `send-message`, Ctrl+C | healthy (deadlocks only, as configured); processed and deleted; ERROR only "No subscriptionId !!!" (expected); stopped in 2.2 s |
| 4 | 22:23:36–22:23:48 | **WRITE** new build: the same | the same; 4 clients closed; stopped in 2.5 s |
| 5 | 22:24 | Events (read: the event store under each marked root) | 1 per build: `closeRun` / `closeWorkflow`, tokens `E2openTransactionId: ""`, `pickupQueue`: **identical** (times and ids normalized) |

**Result of test 9: passed.** **Left in QA:** the two events under `wi01124532-rt-drest-v1` and `-v2`. Queues: empty.
