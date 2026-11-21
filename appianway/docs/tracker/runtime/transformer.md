# Runtime verification: transformer

← [Runtime index](README.md) · [Plan](../runtime-verification.md) · [Tracker home](../README.md)

transformer reads each document routed to it from the workspace, looks up its integration profile format (Network Services), validates its structure and transforms it with the Contivo map that format names, writes the result to the workspace and routes it by context and direction (inbound bookings to the booking queue; outbound files and FAs to file or REST delivery), with lineage events. Outbound documents draw control numbers from a DynamoDB sequence. Migrated in [PR #9](https://github.com/wtg-e2open/INTTRA.appianway/pull/9).

How the two builds are built and run, every command explained: **[how-to: build and run a service locally](../howto/build-and-run-a-service-locally.md)**. Other commands of this test: [commands by step](../commands/README.md#by-step), [AWS commands by test](aws/README.md#by-test). All data (inputs, outputs, scripts, step log): [fixtures/test6-transformer/](fixtures/test6-transformer/).

| | QA (real) | Local test |
|---|---|---|
| Input queue | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_transformer_inbound_dlq` (borrowed) |
| Booking (inbound `requestBooking` / `confirmBooking`, success and error) | `inttra2_qa_sqs_bk_inbound` (legacy URL form `https://queue.amazonaws.com/…`) | `inttra2_qa_sqs_bk_inbound_dlq`, same URL form |
| File delivery / REST delivery (outbound) | `…file_delivery`, `…rest_delivery` | their `_dlq` |
| Container-event validation, schedules | `…ce_validate`, `…os_inbound` | their `_dlq` |
| Error queue | `inttra2_qa_sqs_subscription_errors` | `inttra2_qa_sqs_subscription_errors_dlq` |
| Workspace, events | `inttra2-qa-workspace`, `inttra2_qa_sns_event` | the same |
| Control-number table | `inttra2_qa_controlnumber_sequence` | **the same** (outbound agreed by Arijit 2026-11-20: advancing QA's sequence is harmless). The boot check used a non-existent table name |
| Maps | ECS host `/app01/maps` | `rt6/maps/`: 29 jars of `mercury-services/booking/maps/lib/` + the 4 FA maps of `transformer/lib/maps/` |
| Local port | | 18086 |

<a id="summary"></a>
## Summary in functional terms

transformer turns partner EDI into INTTRA's booking documents and back. **On the new build every case comes out exactly as before:** a booking request and two booking confirmations are validated and transformed into the same booking documents, byte for byte, and sent to the booking service with the same message; the booking request's acknowledgement (FA) is produced and delivered the same way; an outbound FA and an outbound confirmation (EDI X12 301 to the customer) are produced identically except for their control numbers, which come, as before, from QA's shared sequence. Everything is also identical to what QA's own (old) transformer produced for the same files. Both builds share the control-number sequence correctly: the new build continued the item v1 had just written. Starts, reports healthy, stops on Ctrl+C. Differences, none functional: the queue health check answers faster (5.6 s → 0.6 s), and the old build's SDK metrics upload (dropped, [D45](../decisions.md#d45)) no longer logs a permission error locally.

<a id="pr-next-steps"></a>
## PR #9 Next Steps: covered?

| PR Next Step | Covered | Where |
|---|---|---|
| QA: inbound and outbound documents with the real maps, compared with v1 and with QA's own run; the control-number sequence item read and advanced by the new build; boot, health checks, Ctrl+C | ✅ **Yes** | [Test 6](#test-6) |

<a id="maps"></a>
## The Contivo maps

QA's own transformer log for the traced files (read 2026-11-20, [AWS commands: logs](aws/logs-metrics.md#map-names)):

| Case | IPF | Map | Structural map |
|---|---|---|---|
| booking request `BK3_Request_MinMSC` (`CU2100`) | 131 | `IFTMBF_D99B_IN_V1` | `IFTMBF_D99B_IN_V1_STRUCT` |
| confirmations `BK3_SAConfirm_Max` (`CA2000`) | 26 | `IFTMBC_D99B_IN_V1` | `IFTMBC_D99B_IN_V1_STRUCT` |

`IFTMBF2_D99B_IN_V20` (named in an earlier note) is the **format code**, not a map: the map comes from the integration profile format. Outbound maps are not logged; they were simply all present. The jars are **not** on the internal Maven site (it holds only the two IFTSTA maps `build.sh` downloads) nor in S3. They are in **`mercury-services/booking/maps/lib/`** (sources `.xbm` in `maps/inbound/`, `maps/outbound/`), tracked in git and identical to mercury-services `origin/develop` (checked blob by blob); found by Arijit's pointer. SHA-256 (first 16 hex): `IFTMBF_D99B_IN_V1` `ef1c85f8176cfabf`, `…_STRUCT` `b4b105226a7ef149`, `IFTMBC_D99B_IN_V1` `6921df67040db408`, `…_STRUCT` `76785a0c454a8181`.

<a id="test-6"></a>
## Test 6 (2026-11-20, approved by Arijit)

v1 = `222d58be` (feature tip, transformer on SDK v1), new = `d937538e` (PR #9 head). Times local (EST). Cases, each run by both builds on its own marked copy (`wi01124532-rt-tf-{v1,v2}-<case>/`):

| Case | Input | Context | What transformer does |
|---|---|---|---|
| `bf` | splitter's test-5 booking request (467 B, IFTMBF) | inbound `requestBooking`, IPF 131, FA requested | structural validation, booking document to the booking queue, **FA request back to its own pickup queue**, which it then turns into a CONTRL FA to file delivery (QA's FA chain) |
| `bc` ×2 | splitter's two split confirmations (53,607 B each, IFTMBC) | inbound `confirmBooking`, IPF 26 | validation, booking document (203,430 B) to the booking queue |
| `ob-fa` | QA's FA request for the booking (1,594 B, from the QA trace) | outbound `messageFA`, target IPF 2366 | CONTRL FA with a control number from the sequence, to file delivery |
| `ob-bc` | QA's booking JSON for a confirmation (551,811 B) | outbound `confirmBooking`, target IPF 1709 | X12 301 to `CU2100` with control numbers, to file delivery |

| # | Time | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 09:0x | SSO login check (read) | STS | Valid: account `642960533737`, QATeam role |
| 2 | 09:1x | PR #9 status (read) | GitHub | Open; only the automated Copilot review ("No open issues") |
| 3 | 09:1x | Map names (read) | QA transformer log, Maven site, S3 | Names found; jars not on the Maven site or in S3 |
| 4 | 09:2x | Pre-checks (read) | the seven borrowed DLQs | All exist; 0 visible, 0 in flight |
| 5 | 09:26–09:30 | Built the jars in the build worktree | v1 `222d58be`, new `d937538e` | Both exit 0, 201 MB shaded |
| 6 | 09:31–09:35 | **Boot check** of both builds, no messages, non-existent table | port 18086 | v1: `SQSListener`; one `AmazonCloudWatchException` from v1's SDK metrics uploader (local role may not `PutMetricData`). New: `MessageQueueListener`, no such error; the missing table does not stop the start. Health: the same four checks healthy, `InboundQueue` 5.6 s (v1) / 0.6 s (new) ([F10](../findings.md#f10)). Ctrl+C: exit in 3 s / 2 s; new build: "Closing message queue sender / listener / storage download / storage client"; the DynamoDB client lives until the JVM exits, by design, as v1's did |
| 7 | 10:2x | Maps copied from `mercury-services/booking/maps/lib/` (Arijit's pointer) | local | 33 jars in `rt6/maps/` |
| 8 | 10:29 | **WRITE** `s3api copy-object` ×6: the three test-5 documents to `wi01124532-rt-tf-{v1,v2}-{bf,bc}/` | workspace | Sizes, content types, user metadata kept |
| 9 | 10:29–10:36 | First v1 start; stopped idle when outbound was added | | Nothing sent (a pipe on the launcher hung the shell: [pitfall](../howto/build-and-run-a-service-locally.md#8-pitfalls)) |
| 10 | 10:36:04 | Sequence item before (read, `scan --consistent-read`) | `inttra2_qa_controlnumber_sequence` | 1 item: `keyId=SequenceId`, `id=100029603000`, `version=29603` |
| 11 | 10:36:55 | **WRITE** `s3api copy-object` ×4: the two outbound objects to `wi01124532-rt-tf-{v1,v2}-ob-{fa,bc}/` | workspace | 1,594 B `text/plain`; 551,811 B `text/plain; charset=UTF-8` |
| 12 | 10:37:04 | Started **v1** (maps, real table) | PID 9760 | `SQSListener` started; healthy |
| 13 | 10:37:23–10:37:40 | **WRITE** `sqs send-message` ×5 | `transformer_inbound_dlq` | All 5 processed plus the FA request (6 runs), no error; one Contivo warning "Data has been truncated" (W0908 in the 301 map, test data), the same in both builds |
| 14 | 10:38 | Counts and sequence (read); Ctrl+C | | `bk_inbound_dlq` 3, `file_delivery_dlq` 3 (after ~20 s: counts lag), others 0. Sequence `100029604000` / 29604: **v1 took one block** |
| 15 | 10:39:16 | Started the **new build** | PID 28536 | `MessageQueueListener` started; healthy |
| 16 | 10:39:28–10:39:54 | **WRITE** `sqs send-message` ×5 | `transformer_inbound_dlq` | Same 6 runs, no error, the same Contivo warning |
| 17 | 10:40:58 | Counts and sequence (read); Ctrl+C | | `bk_inbound_dlq` 6, `file_delivery_dlq` 6, others 0. Sequence `100029605000` / 29605: **the new build took the next block, from the item v1 had just written**. Exit in 2 s, 4 clients closed |
| 18 | 10:42 | Collected (read: receive with visibility 30 s, `get-object`, events) | 12 messages, 12 documents, 12 events | [outputs](fixtures/test6-transformer/outputs/) |
| 19 | 10:43–10:47 | Compared v1 / new, and new / QA (scratchpad) | | **All identical** (below) |
| 20 | 10:48:31 | **WRITE** deleted our 12 messages, each matched by `"component":"transformer"` and a `wi01124532-rt-tf-` root (`cleanup.sh`) | `bk_inbound_dlq` 6, `file_delivery_dlq` 6 | 12 of 12 deleted, no other message touched. All seven borrowed queues 0/0 at 10:49 |
| 21 | 14:0x | IAM simulation of QA's task role `INTTRA2-ECS-QA-Transformer-Task` (task definition rev 6; read, [commands](aws/ecs-iam.md#11-iam-simulate)) | IAM | **All allowed:** DynamoDB `GetItem`, `PutItem`, `Scan`, `DescribeTable` on the sequence table; SQS receive, delete, change visibility, `GetQueueUrl`, `GetQueueAttributes` on the pickup queue, and send on all 7 configured queues; S3 get, put, list on the workspace; SNS publish to the event topic; SSM `GetParameter(s)` on the two Network Services parameters |

**v1 vs the new build** ([compare.txt](fixtures/test6-transformer/compare.txt)): ids, roots and times normalized.

| Output | Result |
|---|---|
| Booking queue `MetaData` (bf, bc ×2) | identical |
| Booking documents (1,304 B; 203,430 B ×2) and headers | byte-identical, `application/octet-stream` |
| File delivery `MetaData` (bf FA, ob-fa, ob-bc) | identical |
| FA CONTRL (201 B ×2) | identical except the control number (`100029604001` / `100029605001`: each build's own block) and the time |
| X12 301 (41,985 B) | identical except the time and ISA13, a random 9-digit interchange number by design (`AnsiControlNumGenerator`) |
| Events (bf 2, bc 2, ob-fa 1, ob-bc 1, per build) | identical |

**The new build vs QA's own run** of the same files on 2026-11-19 ([compare-qa.txt](fixtures/test6-transformer/compare-qa.txt); QA's outputs found as the next service's input in QA's events):

| Output | Result |
|---|---|
| Booking document of the request (1,304 B), FA request (1,594 B), both confirmation documents (203,430 B) | **byte-identical**, same content types |
| Structural-validation result (209 B), FA CONTRL ×2 (201 B), X12 301 (41,985 B) | identical except control numbers (QA's block then: `100029580…`), dates and times, and the random ISA13 |

**Result of test 6: passed.**

**Left in QA:** the ten marked input copies and the transformed outputs under `wi01124532-rt-tf-*` in `inttra2-qa-workspace`; twelve events in QA's event store; the control-number sequence advanced by two blocks (`100029603000` → `100029605000`), harmless (each running instance holds its own block). Queues: empty.

<a id="notes"></a>
## Notes

- Times inside the outbound EDI (`1037`, `1039`) are the local clock (EST): the JVM's default time zone. On ECS it is UTC. Both builds the same; not a migration difference.
- The new build's queue health check takes 0.6 s instead of 5.6 s, as for every migrated service ([F10](../findings.md#f10)).
