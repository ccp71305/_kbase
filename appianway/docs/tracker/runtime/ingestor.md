# Runtime verification: ingestor (PR #10)

← [Runtime index](README.md) · [Tracker home](../README.md)

How the builds are built and run: [how-to](../howto/build-and-run-a-service-locally.md). Commands of this test: [AWS commands by test](aws/README.md#by-test), the Elasticsearch read tool: [aws/elasticsearch.md](aws/elasticsearch.md). Inputs, scripts, outputs and logs: [fixtures/test7-ingestor/](fixtures/test7-ingestor/); the boot and Ctrl+C checks: [fixtures/test7-ingestor-boot/](fixtures/test7-ingestor-boot/).

<a id="summary"></a>
## In functional terms

ingestor turns every lifecycle event into transaction-tracking documents in Elasticsearch: one event document per event, and one aggregate per workflow that collects its tracking attributes. **The new build indexes exactly what the old one does:** for 105 real QA events (one booking request traced through 8 services, a carrier file with two confirmations, and a failed run with its annotations), both builds wrote the same 105 event documents and the same 7 aggregates, field for field. They are also identical to what QA's own ingestor indexed for the same events on 2026-11-19 (104 of 104 events; 5 of 6 aggregates, the sixth differing only in which of 7 delivery file names was upserted last). Starts, reports healthy, stops on Ctrl+C in under 2 s with no error. Requests are signed exactly as before (same signer, 0.0.16).

## Configuration

| | Value |
|---|---|
| Builds | v1 = `bef71a96` (feature tip, ingestor on SDK v1); new = `0c31d34b` (PR #10 head). Shaded jar `ingestor-1.0.jar` (95 MB); yaml from each jar (they differ only in the cloud-sdk logger lines) |
| Pickup queue | borrowed `inttra2_qa_sqs_ingest_dlq` (empty before and after) |
| Elasticsearch | QA's domain `search-inttra2-qa-es-tx-tracker-…` (**WRITE**, approved by Arijit 2026-11-20); for the boot and Ctrl+C checks `http://localhost:9` (unreachable, nothing written) |
| Network Services, parameters | QA (read) |
| `ingestor.listenerThreads` | 1 for the indexing test (batches in send order, so the aggregates are comparable); 8 (production) for the boot and Ctrl+C checks |
| Port | 18087 |
| Local properties | [ingestor.local.properties](fixtures/test7-ingestor/ingestor.local.properties) |

<a id="test-7"></a>
## Test 7 (2026-11-20, approved by Arijit)

Inputs ([make-inputs.py](fixtures/test7-ingestor/make-inputs.py)): the 54 events of the IFTMBF booking trace, one SNS message each, in time order; the 50 events of the IFTMBC trace in one message; one failed dispatcher `closeRun` whose annotations object is in the workspace. Every workflow id replaced by a marked one per build (`wi01124532-rt-ing-v1-01` … `-06`, `-fail`; the same for `v2`); event ids kept, to compare with QA's own documents. 56 messages per build.

| # | Time (UTC) | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 18:52–18:56 | **Boot and Ctrl+C check** of the new build, 3 runs, 8 listeners, Elasticsearch unreachable (pre-review point 1) | local, `ingest_dlq` | 8 listeners; health check healthy (`InboundQueue`, 0.6 s); Ctrl+C while all 8 were in their long poll: 0 ERROR lines, 4 clients closed, exit in 1.5–1.8 s |
| 2 | 19:0x | Elasticsearch access (read: `_cluster/health`, `_cat/indices`) | QA domain | Reachable with the QATeam role, signed as ingestor signs ([EsRead](aws/elasticsearch.md)); daily `txtrack-event-*` indices of 156k–605k documents |
| 3 | 19:0x | Pre-check (read): marked documents | `txtrack-event-*`, `txtrack-agg-*` | 0 and 0 |
| 4 | 19:0x | Built the v1 jar | build worktree at `bef71a96` | exit 0; worktree back at `0c31d34b` |
| 5 | 19:0x | **WRITE** `s3api put-object` ×2: the annotations object for `wi01124532-rt-ing-{v1,v2}-fail/annotations` | `inttra2-qa-workspace` | 2 objects |
| 6 | 19:08:57–19:12:01 | **WRITE** v1: started, 56 `send-message`, waited for the queue to empty, Ctrl+C ([run.sh](fixtures/test7-ingestor/run.sh)) | `ingest_dlq`, QA Elasticsearch | All 56 consumed, queue 0/0; 0 ERROR lines, 0 Elasticsearch failures; stopped in 3.2 s |
| 7 | 19:12:24–19:15:46 | **WRITE** new build: the same | `ingest_dlq`, QA Elasticsearch | All 56 consumed, queue 0/0; 0 ERROR lines, 0 Elasticsearch failures; 4 clients closed; stopped in 1.6 s |
| 8 | 19:1x | Collected (read: `_search`) | event and aggregate indices | Each build: 105 event documents (one per event, no duplicate) in `txtrack-event-2026-11-20`, 7 aggregates in `txtrack-agg-2026-11-20` ([outputs](fixtures/test7-ingestor/outputs/)) |
| 9 | 19:2x | Compared ([compare.py](fixtures/test7-ingestor/compare.py), [compare_qa.py](fixtures/test7-ingestor/compare_qa.py)) | | below |

**v1 vs the new build** ([compare.txt](fixtures/test7-ingestor/compare.txt)), marks normalized:

| Output | Result |
|---|---|
| Event documents (105) | identical, field for field, including the failed run's annotations read from the workspace |
| Aggregates (7) | identical |

**The new build vs QA's own run** of the same events on 2026-11-19 ([compare-qa.txt](fixtures/test7-ingestor/compare-qa.txt)), marks mapped back to the real workflow ids:

| Output | Result |
|---|---|
| Event documents (104 real events) | **identical**, all 104 (QA: `txtrack-event-2026-11-19`) |
| Aggregates (6 workflows) | 5 identical; `1c224a22` differs only in `ftpArchiveDeliveryFileName` / `ftpCarrierArchiveFileName`: its 7 delivery events each name a different archive file and the upsert keeps the last one processed (QA's 8 listeners processed `IFTMBFBK2ToBK1…` last, the test in time order `DESC_APERAK…`). Order, not code: v1 and the new build agree |

**Result of test 7: passed.**

**Left in QA:** 210 marked event documents and 14 marked aggregates in today's indices (`wi01124532-rt-ing-*`; purged by QA's ingestor with the indices after 7 and 30 days); the two marked annotations objects in `inttra2-qa-workspace`. Queues: empty.

<a id="notes"></a>
## Notes

- The index date comes from the local clock (`LocalDateTime.now()`); both runs were on 2026-11-20 UTC and EST.
- Both builds sign with the same signer (0.0.16): the PR keeps it ([F30](../findings.md#f30)).
- The known defects [KD-15](../known-defects.md#kd-15) to [KD-17](../known-defects.md#kd-17) were not triggered (no unreadable message mixed into a batch, no redelivery, Elasticsearch available).
