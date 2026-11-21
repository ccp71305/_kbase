# Runtime verification: splitter

← [Runtime index](README.md) · [Plan](../runtime-verification.md) · [Tracker home](../README.md)

splitter reads each file dispatcher routed to it from the workspace, picks its parser, checks the sender's integration profile, splits the file into its documents, checks each against its profile format, writes it to the workspace (unless the file is a single valid document, which is kept) and routes it to the queue of its format's context, with lineage events. Migrated in [PR #8](https://github.com/wtg-e2open/INTTRA.appianway/pull/8).

| | QA (real) | Local test |
|---|---|---|
| Input queue | `inttra2_qa_sqs_splitter_pu` | `inttra2_qa_sqs_splitter_pu_dlq` (borrowed) |
| Routed (booking request and confirmation, container events) | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_transformer_inbound_dlq` (borrowed) |
| Other contexts | `…si_inbound`, `…transformer_os_inbound`, `…rates_inbound`, `…cfast_batch_inbound` | their `_dlq` (`rates_inbound` has none: mapped to `…transformer_os_inbound_dlq`; nothing routed there) |
| Router queue (ops health check) | `inttra2_qa_sqs_router` | `inttra2_qa_sqs_router_dlq` |
| Error queue | `inttra2_qa_sqs_subscription_errors` | `inttra2_qa_sqs_subscription_errors_dlq` (borrowed) |
| Workspace | `inttra2-qa-workspace` | the same: inputs copied to marked roots `wi01124532-rt-sp-{v1,v2}-{bf,bc}/` |
| Events | `inttra2_qa_sns_event` | the same |
| Network Services | QA endpoints (credentials from SSM) | the same (VPN) |
| Local port | | 18085 |

Local properties: the QA `splitter.properties` with the queues above and `server.connector.port=18085` ([copy](fixtures/test5-splitter-outputs/splitter.local.properties)). **The route mappings are queue names, not URLs** (as in QA), so the run also checks that the new build sends to a name. Build, credentials and start/stop: as [dispatcher](dispatcher.md#how-the-shutdown-check-is-run) (`start-java.ps1` with the splitter jar and properties; Ctrl+C with `send-ctrl-c.ps1`).

**Inputs** (QA test data, traced first: [fixtures](fixtures/)):

| Case | File | What splitter does | Fixture |
|---|---|---|---|
| `bf` | IFTMBF booking request `BK3_Request_MinMSC` from `CU2100`, 467 B, one message (the test case of `Downloads\BK3_Request_MinMSC.txt`) | single valid document: **kept**, routed with the original object | [qa-iftmbf-bk3-minmsc](fixtures/qa-iftmbf-bk3-minmsc/README.md) |
| `bc` | IFTMBC carrier file `BK3_SAConfirm_Max_996677102.txt` from `CA2000`, 115,526 B, **two** confirmations | **split** into two documents, written and routed one by one | [qa-iftmbc-2docs-sa-confirm-max](fixtures/qa-iftmbc-2docs-sa-confirm-max/README.md) |

Each input is dispatcher's real `MetaData` for that file (from QA's lineage events), with only the ids, the root and the file name changed to the marked copy. Production's shapes (bookings always one per file, carrier batches up to 3,479 confirmations) are in [prod-samples.md](fixtures/prod-samples.md).

<a id="summary"></a>
## Summary in functional terms

splitter turns each partner file into the documents the next services handle. **On the new build both kinds of file come out exactly as before:** a single booking request is passed on as it is, with its partner details; a carrier file with two confirmations is split into the same two documents, byte for byte, sent to the same next queue with the same routing message, and recorded in the lineage with the same events. They are also identical to what QA's own (old) splitter produced for the same files yesterday. The new build starts, reports healthy, routes to QA's queue names as the old one did, and on stop closes its connections and exits at once. One difference, not functional: its queue health check answers faster (0.5 s instead of 5.5 s).

<a id="pr-next-steps"></a>
## PR #8 Next Steps: covered?

| PR Next Step | Covered | Where |
|---|---|---|
| QA: split a multi-document file and a single document; compare the routed `MetaData`, the split documents and the events with the v1 build; check boot, health checks and the clients closing on Ctrl+C | ✅ **Yes** | [Test 5](#test-5): all identical to v1 and to QA's own run; boot, health checks, queue names, Ctrl+C with the 4 clients closing |

<a id="test-5"></a>
## Test 5 (2026-11-19 evening, approved by Arijit)

Plan: run v1 on its two inputs, then the new build on its own two; compare the routed `MetaData`, the documents and their headers, and the events, with each other and with QA's run of the same files. v1 = `07b5106f` (feature base, splitter on SDK v1), new = `e36bc10f` (PR #8 head). Times are local (EST).

| # | Time | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 2026-11-20 earlier | Traced the two inputs in QA (read only): inbound object, workspace copy, splitter's log, all lineage events | QA inbound, workspace, `inttra2-qa-lg-app-way`, event store | Saved as fixtures; dispatcher's real `MetaData` per file found in splitter's events (`pickUpMessage`) |
| 2 | 20:05–20:06 | Built the jars in the build worktree | v1 `07b5106f`; new `e36bc10f` | Both built (shaded, 102 MB) |
| 3 | 20:07 | **WRITE** `s3api copy-object` ×4: each input object to two marked roots (keeps content type and user metadata) | `inttra2-qa-workspace/wi01124532-rt-sp-{v1,v2}-bf/BK3_Request_MinMSC`, `…-{v1,v2}-bc/BK3_SAConfirm_Max` | 467 B `text/plain` with `originalfilename`, `xlogid`, `inftpfilepickuptime`; 115,526 B likewise |
| 4 | 20:07 | Pre-checks (read) | the six borrowed queues | All 0 visible, 0 in flight |
| 5 | 20:07:33 | Started the **v1 build** | port 18085, PID 16536 | `SQSListener` started |
| 6 | 20:07:55 | v1 `/admin/healthcheck` (read) | local | `HTTP GET -> …/network/services/ping` (0.6 s), `InboundQueue -> …splitter_pu_dlq` (5.5 s), `errorsPerSecondAverage`, `deadlocks`: all healthy |
| 7 | 20:07:57, 20:08:00 | **WRITE** `sqs send-message` of `input-v1-bf.json`, `input-v1-bc.json` | `inttra2_qa_sqs_splitter_pu_dlq` | `8a4c22ab-…`, `c8a37826-…` |
| 8 | 20:07:57–20:08:03 | v1 processed both | log | `bf`: one split workflow, "Split file size = 467" (kept); `bc`: two split workflows, 53,607 B each. Pickup 0/0; `transformer_inbound_dlq` 3; error, router and other queues 0 |
| 9 | 20:08:40 | Ctrl+C | v1 | Exit in 1 s (v1 logs no client lines) |
| 10 | 20:08:47 | Started the **new build** | port 18085, PID 24200 | `MessageQueueListener` started |
| 11 | 20:09:06 | New build `/admin/healthcheck` (read) | local | Same four checks, all healthy; `InboundQueue` **0.5 s** ([F10](../findings.md#f10)) |
| 12 | 20:09:08, 20:09:10 | **WRITE** `sqs send-message` of `input-v2-bf.json`, `input-v2-bc.json` | `inttra2_qa_sqs_splitter_pu_dlq` | `b4a1eeed-…`, `5b703a32-…` |
| 13 | 20:09:08–20:09:14 | New build processed both | log | Same as step 8. **Routed to the queue name `inttra2_qa_sqs_transformer_inbound_dlq`**: cloud-sdk passes it to SDK 2.x as `QueueUrl` and SQS accepts it, as with v1. `transformer_inbound_dlq` 6; errors 0. Only log WARN: logback-access's version notice |
| 14 | 20:09:47 | Ctrl+C | new build | Exit in 1 s; "Closing message queue sender client / message queue listener client / storage download client / storage client on application shutdown" |
| 15 | 20:10 | Peeked the routed messages (read, visibility 2 s, repeated, de-duplicated), downloaded the documents and their headers, read the ten events from QA's event store (read) | `transformer_inbound_dlq`, workspace, `eventstore/2026-11-20/wi01124532-rt-sp-*` | 6 messages, 6 documents, 10 events ([saved](fixtures/test5-splitter-outputs/README.md)) |
| 16 | 20:11 | Compared (scratchpad, `compare.py`, `compare-events.py`) | | **All identical** (below) |
| 17 | 20:12:48 | **WRITE** (agreed) deleted our 6 routed messages, each matched by `"component":"splitter"` and the marked root (`cleanup.py`) | `inttra2_qa_sqs_transformer_inbound_dlq` | 6 of 6 deleted, none returned. All borrowed queues 0/0 at 20:13 |

**Comparison (step 16):**

| | v1 vs new build | new build vs QA's run (2026-11-19) |
|---|---|---|
| Routed `MetaData`, booking | identical (ids, root and times normalized) | identical; only the marked copy's name differs from QA's random object id |
| Routed `MetaData`, confirmations (2) | identical, both | identical, both |
| Booking document | the original object, 467 B, `text/plain`, partner metadata | the same bytes and headers |
| Split confirmation documents (2) | byte-identical, 53,607 B each, `application/octet-stream`, no user metadata | byte-identical to QA's two split documents, same headers |
| Events | identical: booking 2 (`startWorkflow`, `closeWorkflow`), confirmations 3; same tokens incl. `dropOffQueue` = the queue name | |

**Result of test 5: passed.**

**Left in QA:** the four marked input copies and the four split documents under `wi01124532-rt-sp-*` in `inttra2-qa-workspace` (kept, per Arijit; the new build's three routed messages name them, for transformer's test); the ten events in QA's event store. Queues: empty.
