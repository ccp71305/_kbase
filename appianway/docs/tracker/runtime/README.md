# Runtime verification: index

← [Plan](../runtime-verification.md) · [Tracker home](../README.md)

Local runs of each migrated service against QA (standing rule: no ECS change, no deploy). One page per service, with how it is built, configured and started, and the detailed log of every test. The AWS CLI commands used, with their syntax explained: [aws/](aws/README.md), one page per AWS service.

| Page | Service | Tests | Status |
|---|---|---|---|
| [event-writer.md](event-writer.md) | event-writer (PR #4) | [Test 1](event-writer.md#test-1) | ✅ passed 2026-11-19 |
| [error-processor.md](error-processor.md) | error-processor (PR #5) | [Test 2](error-processor.md#test-2) | ✅ passed 2026-11-19 (close events checked at 14:44, after QA's event-writer was back) |
| [email-sender.md](email-sender.md) | email-sender (PR #6) | [Test 3](email-sender.md#test-3) | ◐ partly 2026-11-19: everything up to the SES call verified (same `ses:SendEmail` action, SESv2); sending blocked for the local role, to be tried on INT; KD-4 reproduced |
| [dispatcher.md](dispatcher.md) | dispatcher (PR #7) | [Test 4a](dispatcher.md#test-4a) routed and empty file, [Test 4b](dispatcher.md#test-4b) graceful shutdown | ✅ passed 2026-11-19 (zip dropped: QA confirmed partners send only flat zips; covered by the functional tests) |
| [splitter.md](splitter.md) | splitter (PR #8) | [Test 5](splitter.md#test-5): an IFTMBF booking (kept) and an IFTMBC file with two confirmations (split) | ✅ passed 2026-11-19: identical to v1 and to QA's own run; routes to queue names |
| [transformer.md](transformer.md) | transformer (PR #9) | [Test 6](transformer.md#test-6): splitter's booking request and two confirmations, inbound and outbound (FA, X12 301) | ✅ passed 2026-11-20: identical to v1 and to QA's own run (except control numbers and times); the sequence item shared correctly |
| [ingestor.md](ingestor.md) | ingestor (PR #10) | [Test 7](ingestor.md#test-7): 105 real QA events indexed (booking trace, confirmation trace, a failed run) | ✅ passed 2026-11-20: same 105 event documents and 7 aggregates as v1; events identical to QA's own run; boot and Ctrl+C (8 listeners) clean |
| [distributor.md](distributor.md) | distributor (PR #11) | [Test 8](distributor.md#test-8): a real CONTRL FA and X12 301 to CU2100, and the FA without optional metadata | ✅ passed 2026-11-20: delivered and archived objects byte-identical to v1 and to QA's own deliveries; content type and metadata the same; null metadata kept empty |
| [distributor-rest.md](distributor-rest.md) | distributor-rest (PR #12) | [Test 9](distributor-rest.md#test-9): boot, health, a delivery message without subscription, Ctrl+C | ✅ passed 2026-11-20: same event as v1; the HTTP delivery proven by the golden test (no QA traffic; a real webhook is outside QA) |
| [watermill-publisher.md](watermill-publisher.md) | watermill-publisher (PR #13) | [Test 10](watermill-publisher.md#test-10): boot, health, the two real QA status events to a local TLS stand-in for Watermill, Ctrl+C (3 idle stops) | ✅ passed 2026-11-21: events and call metadata identical to v1 and to the golden test; nothing sent to e2open; 4 clients closed |
| [aws/](aws/README.md) | All | | Reference: AWS CLI commands, one page per AWS service, and [by test](aws/README.md#by-test) |
| [fixtures/qa-iftmbf-bk3-minmsc/](fixtures/qa-iftmbf-bk3-minmsc/README.md) | splitter and later (transformer, distributor, booking, ingestor) | Inputs for tests 5+ | Reference: one real QA IFTMBF booking traced through 8 services (54 events, each service's input `MetaData`, queues, workspace keys) |
| [fixtures/qa-iftmbc-2docs-sa-confirm-max/](fixtures/qa-iftmbc-2docs-sa-confirm-max/README.md) | splitter (splitting path) and later | Inputs for tests 5+ | Reference: a real QA carrier file with two IFTMBC confirmations traced through every service (50 events, inputs per service incl. the split document) |
| [fixtures/test5-splitter-outputs/](fixtures/test5-splitter-outputs/README.md) | transformer | Inputs for transformer's test | Reference: splitter's real routed messages from test 5 (a booking request and two confirmations) and the workspace objects they name, kept in QA |
| [fixtures/prod-samples.md](fixtures/prod-samples.md) | splitter and later | | Reference: production IFTMBF / IFTMBC shapes (counts only, no content): no zips; bookings 1 per file; MSC confirmation batches up to 3,479 documents in 26 groups |

Conventions: times are local (EST); **WRITE** marks a change in AWS, each agreed with Arijit first; test data is marked `wi01124532-rt-`; credentials come from the SSO login into the Java process environment only.

<a id="summary"></a>
## Summary so far, in functional terms

| Service | What it does for the business | Verified on QA | PR Next Steps |
|---|---|---|---|
| event-writer | Records the lineage of every file (one event per step) | Events stored exactly as before: same place, content and format | Event check ✅; shutdown ✅ via dispatcher (shared code) |
| error-processor | Keeps a copy of each failure, asks for the support email, records the step | Copy, email request and lineage event exactly as before | Archive, email request, event ✅; shutdown ✅ via dispatcher (shared code) |
| email-sender | Sends the support email for a failure | Up to sending, exactly as before (same sender, same permission needed); the send itself not verified: the local role may not send. On INT later | Email and event: partly; shutdown ✅ via dispatcher (shared code) |
| dispatcher | Takes each inbound file in, filters it, copies it to the workspace and routes it | A file copied, routed and recorded exactly as before, partner metadata included; an empty file refused exactly as before. **Stopping while busy is safe:** it takes no new files, finishes the ones started, closes its connections and stops in 9 s; each of 20 files processed exactly once | EDI file, metadata, shutdown ✅ (zip dropped: flat zips only) |
| transformer | Turns partner EDI into INTTRA's booking documents and back (with acknowledgements and control numbers) | A booking request and two confirmations transformed into the same booking documents, byte for byte; FA and outbound X12 301 identical except control numbers and times; the same as QA's own run; the control-number sequence shared correctly between old and new | Inbound, outbound, sequence, boot, health checks, Ctrl+C ✅ |
| distributor | Delivers each outbound document to the partner's folder and archives it | The same objects (bytes, content type, metadata) as before and as QA's own run; QA's FTP bridge picks them up | Delivery, archive, null metadata, boot, health checks, Ctrl+C ✅ |
| ingestor | Turns every lifecycle event into transaction-tracking documents (one per event, one aggregate per workflow) | The same 105 event documents and 7 aggregates as before, field for field, and the same as QA's own run; requests signed as before | Indexing, annotations, boot, health check, Ctrl+C with 8 listeners ✅ |
| splitter | Splits each partner file into its documents and routes each to the next service | A booking passed on as it is and a two-confirmation file split into the same two documents, byte for byte, with the same routing messages and events as before and as QA's own run | Split and single document, boot, health checks, Ctrl+C ✅ |

Across the five tests: each new build starts cleanly, reports the same health checks as healthy, and uses the same queues, buckets and topic with the same permissions as the old build. Differences seen, none functional: queue health checks answer faster (5.5 s → 0.5 s); one extra error log line per storage health check (cosmetic; commons fix U15 requested); the storage health check takes about 4.7 s instead of 0.6 s because it retries an expected "not found" ([F25](../findings.md#f25)); the jar is about twice as large until the old SDK is removed in step 5.

Unrelated to the tests: QA's event-writer stopped from 13:44 to 14:40 EST on 2026-11-19 because its EC2 host was terminated; ECS replaced it.

