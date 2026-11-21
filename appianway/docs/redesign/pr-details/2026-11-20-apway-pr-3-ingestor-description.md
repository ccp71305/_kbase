# WI01124532 PR: ingestor on cloud-sdk

Part 1 is the GitHub description (between the ✂ lines). Part 2 is the review guide, per commit, for Arijit only.

## Part 1: GitHub description

✂ ---------------------------------------------------------------------------------------------------------------

## Link to Story/Defect this work relates to

**WI01124532**: AppianWay AWS SDK v1 → v2 upgrade. This PR moves ingestor's queue, workspace and parameter-store access onto the `shared` cloud-sdk adapters, as #4–#9 did for the earlier services. Elasticsearch access (Jest and its SigV4 signer) is unchanged.

## What/Why I Did the changes

ingestor reads the lifecycle events every service publishes (SNS-wrapped, from its queue, 8 listener threads), builds tracking attributes per workflow (Network Services format and integration profile), reads the annotations of a failed run from the workspace, writes a bulk request of event documents and one upsert per workflow to the daily Elasticsearch indices, and deletes every message. It now does this through cloud-sdk (AWS SDK 2.x) instead of AWS SDK v1. The Elasticsearch requests are unchanged.

| | Before (SDK v1) | After (cloud-sdk) |
|---|---|---|
| Clients | `ExternalServicesModule`: `AmazonSQS` ×2, `AmazonS3`; `ParameterStoreModule` (SDK v1 SSM) | `ExternalServicesModule` installs `shared` `CloudServicesModule` (no event topic: ingestor publishes nothing); credentials always from the parameter store, as before |
| Listeners | 8 × `SQSListener` on SDK v1 `Message` | 8 × `MessageQueueListener` on `QueueMessage<String>`, same shared synchronous dispatcher |
| Shutdown | listeners told to stop; clients never closed | listeners stop, then the batches in progress get up to 20 s, then the clients close |
| Workspace, health check | `S3WorkspaceService`; `InboundSqsHealthCheck` built its own client | `StorageWorkspaceService`; the same check on the injected client, same name and placement |
| Elasticsearch | Jest 6.3.1, SigV4 signer 0.0.16 with the SDK v1 credentials chain | unchanged (signer kept at 0.0.16, see below) |
| Functional tests | one empty test (the real ones commented out since 2018) | JUnit 5 on the cloud-sdk fakes: golden test, health checks, loggers |

### Changes

1. **Proof first:** a golden test, written on the v1 code, records every request ingestor sends to Elasticsearch (method, URI, body, as the HTTP client builds them) and every delete, for real QA lineage events: the 54 events of an IFTMBF booking (one message each) and the 50 events of a carrier file with two IFTMBC confirmations (one message: one bulk request, one upsert per workflow); a failed run whose annotations are read from the workspace, and one whose annotations are missing; a `HEALTHCHECK` published to the event topic; Elasticsearch answering 400, and not reachable. It passes on cloud-sdk with the same expected files.
2. The task, the dispatcher and the module error handler work on `QueueMessage<String>` and delete through `MessageQueueClient`; the error transformer reads annotations through the `WorkspaceService` interface.
3. `ExternalServicesModule` installs `CloudServicesModule`; `IngestorModule` builds the 8 cloud-sdk listeners; `IngestorApplication` uses `StorageConfigurationProvider` and registers the health check on the injected client. A test builds the production module with the real clients (no request sent) and checks every binding.
4. **Shutdown drain:** the 8 listeners run their batches on their own threads through one dispatcher, so the dispatcher counts the batches in progress. On stop, the listeners stop receiving, new batches are left on the queue (logged), and the ones in progress get up to 20 s before the clients close.
5. **Signing kept as it is:** a new test records the exact SigV4 headers of a bulk request, an upsert, the settings read and an index delete (long-term credentials, and session credentials as the ECS task role gives), written with the signer ingestor uses today (0.0.16). With 0.0.22 (the version commons uses) it fails: 0.0.22 no longer signs `Content-Length`. So the signer stays at 0.0.16; moving is a separate change that needs a signed request against a real domain first.
6. `ingestor.yaml`: cloud-sdk logs at WARN, except the one line per client that shows it closing at shutdown.
7. An architecture test fails the build if ingestor uses an AWS SDK type, except the SDK v1 credentials chain the signer takes and the v1 message of the shared dispatcher interface's old method (removed with that method in the last step), or a `shared` SDK v1 class.
8. pom: the direct SDK v1 SQS dependency is removed; the signer's own old SDK v1 core is excluded (the core comes from `shared` at 1.12.730).
9. Three existing defects are kept, each with a disabled test asserting the correct behaviour. Each test fails when enabled and passes with a small fix. This PR does not change them.
    - **One unreadable message drops its batch** (since July 2018). The task reads every message of a batch inside one try/catch.
      *Functional effect:* a `HEALTHCHECK` published to the event topic in a batch loses the events of the other messages of that batch (up to 10); they are deleted and never indexed.
    - **A batch delivered again duplicates its event documents** (since July 2018). Event documents are indexed without an id.
      *Functional effect:* after a failed delete or a visibility timeout, each event appears twice in transaction tracking.
    - **A batch Elasticsearch could not take is deleted** (since July 2018). The task catches the repository's recoverable failure and only logs it.
      *Functional effect:* during an Elasticsearch outage longer than its three tries (about a second), every batch is lost for tracking.

### Backward compatibility

- **Same Elasticsearch requests:** every bulk request, upsert and URI is identical to v1 for the golden inputs; same index names, document format and upsert parameters.
- **Same signing:** signer 0.0.16 as before; the signing test proves the headers.
- **Same delete behaviour:** every message is deleted, also when the batch cannot be read or Elasticsearch fails (existing behaviour, recorded above).
- **Same client settings** as the SDK v1 clients, the same parameter names, and the credentials always from the parameter store.
- **Same health check:** name and placement.
- **Same configuration keys.** The only YAML change is the logger lines.
- **Index purge job** unchanged (first run 24 h after start).

## Next Steps

> ✅ **Verified on QA (2026-11-20):** the v1 build and this build were run locally against QA, with the pickup messages on a borrowed DLQ and the documents written to QA's Elasticsearch under marked workflow ids. No real messages, queues or documents were affected.

- ✅ **Real events:** 105 real QA lineage events (a booking request traced through eight services, a carrier file with two confirmations, and a failed run with its annotations in the workspace). Both builds wrote the same 105 event documents and the same 7 aggregates, field for field.
- ✅ **Same as QA's own run:** for the same 104 real events, the event documents are identical to those QA's ingestor indexed the day before. 5 of 6 aggregates are identical; the sixth differs only in which of its seven delivery file names was upserted last (processing order, not code).
- ✅ **Signing and access:** requests are signed as before (same signer version) and accepted by QA's domain; the queue, storage, parameter store and Network Services calls all work.
- ✅ **Boot and shutdown:** the 8 listeners start, the health check is healthy, and Ctrl+C with all 8 in their long poll closes the four clients and exits in under 2 s, with no error (three runs).

## Testing Notes

- **Test counts:** ingestor ran 179 tests, none skipped. It now runs **209**, 3 of them skipped (the known-defect tests):
  - golden (7), functional (2: health checks, loggers), production wiring (2), architecture (2), signing (2);
  - task (3), dispatcher (3), drain (3), listener manager (3), error transformer (3), error handler (35, retyped);
  - known defects (3, disabled).
- **Removed:** the empty functional test, the fake Elasticsearch client that only knew single-document indexing, and the fixtures of the tests commented out since 2018 (the golden test covers those flows).
- **Test-first:** each behaviour change has a failing test first, then the change.
- **No change to `shared`, `functional-testing` or any other module.**
- **Full reactor build** (`mvn -B clean verify`) at the PR head: BUILD SUCCESS, all 26 modules, 15:38 min.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

✂ ---------------------------------------------------------------------------------------------------------------

## Part 2: review guide (for Arijit)

Commit by commit, with what to look at. Tracker log: [step-3-ingestor](../../tracker/steps/step-3-ingestor.md).

| # | Commit | Look at |
|---|---|---|
| 1 | `e2c4b5ad` golden test | `RecordingJestClient` (method, `getURI(UNKNOWN)`, `getData`); inputs generated from the QA trace fixtures; the 7 expected files written by v1 |
| 2–3 | `36963169` / `8c0cb5e9` task, dispatcher | Types only in the task (diff); the dispatcher's v1 `submit` bridges to `dispatch` |
| 4–5 | `41c746ed` / `1a9b0497` error transformer | `WorkspaceService` interface; failure still ignored |
| 6–7 | `621f657d` / `8d6854cf` module | `CloudServicesModule(lifecycle, pickup, null)`; `withParameters` without pass-through (as v1); 8 listeners; health check on the injected client; the boundary test's two allowances; removed test files |
| 8–9 | `a0c84470` / `fe428633` error handler | No caller since 2018; retype only, 35 tests unchanged in substance |
| 10–11 | `62951869` / `8077d56d` drain | Counting in the dispatcher under one lock; one 20 s deadline across the listeners; executor shut down |
| 12 | `431d7316` signing test | Requests handed over as the Apache client does (wrapped, relative URI, Host/Content-Length/Content-Type set) |
| 13 | `497fd620` pom | Signer kept at 0.0.16 (0.0.22 drops Content-Length from the signature); old SDK core excluded; upper-bound rule passes |
| 14–15 | `157c54e9`, `b343f2cc` known defects | Each checked both ways (enabled fails; with the fix passes) |
| 16 | `0c31d34b` pre-review fixes | Drain log line, javadoc, session-credentials signing case |

Pre-review: 5 points (table in the tracker step page): 3 nits fixed, the pre-existing one recorded as the third known defect, the important one (listener receive aborted at shutdown) not reproduced in three local Ctrl+C runs with 8 listeners.
