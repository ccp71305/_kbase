# WI01124532 PR: distributor on cloud-sdk

Part 1 is the GitHub description (between the ✂ lines). Part 2 is the review guide, per commit, for Arijit only.

## Part 1: GitHub description

✂ ---------------------------------------------------------------------------------------------------------------

## Link to Story/Defect this work relates to

**WI01124532**: AppianWay AWS SDK v1 → v2 upgrade. This PR moves distributor onto the `shared` cloud-sdk adapters, as #4–#10 did for the earlier services, and makes `shared` store a null user-metadata value as SDK v1 did.

## What/Why I Did the changes

distributor takes each outbound document's `MetaData` from its queue, resolves the delivery file name and the delivery and archive paths from Network Services, optionally zips the document, copies it from the workspace to the outbound bucket twice (delivery, then archive) with workflow user metadata, and publishes a close-workflow event. It now does this through cloud-sdk (AWS SDK 2.x) instead of AWS SDK v1. Delivered objects, keys, metadata, content type, messages and events are unchanged.

| | Before (SDK v1) | After (cloud-sdk) |
|---|---|---|
| Clients | `ExternalServicesModule`: `AmazonSQS` ×2, `AmazonS3`, `AmazonSNS`; `ParameterStoreModule` (SDK v1 SSM) | `ExternalServicesModule` installs `shared` `CloudServicesModule` (parameters as before, pass-through honoured) |
| Listener, message type | `SQSListener`, SDK v1 `Message` | `MessageQueueListener` (the shared listener manager drains it on stop), `QueueMessage<String>` |
| Workspace, event publisher | `S3WorkspaceService`, `SNSEventPublisher` | `StorageWorkspaceService`, `NotificationEventPublisher` |
| Health checks | each built its own default client | run on the service's clients; same names and placement |
| Functional tests | JUnit 4, all `@Ignore`d (they bound the wrong Network Services types) | JUnit 5 on the cloud-sdk fakes |

### Changes

1. **Proof first: a golden test, written on the v1 code.** It passes on cloud-sdk with the same expected files.
    - **What it records:** every object delivered and archived (key, content, user metadata), every object written to the workspace, every queue message and every event.
    - **The cases:**
      - a CONTRL FA and an X12 301 confirmation, the two real QA distributor inputs (the 301 also takes file-name tokens from its projections);
      - the same FA zipped;
      - the FA without its optional metadata;
      - two error paths.
    - **Network Services** is stubbed with the delivery settings QA uses.
2. The task works on `QueueMessage<String>`; the zip handler reads and writes through the `WorkspaceService` interface (and no longer uses SDK v1's `IOUtils`).
3. `ExternalServicesModule` installs `CloudServicesModule`; `DistributorModule` builds the cloud-sdk listener; `DistributorApplication` uses `StorageConfigurationProvider` and registers the health checks on the injected clients. A test builds the production module with the real clients (no request sent) and checks every binding.
4. **`shared`: a missing metadata value is stored as empty, as before.** When a delivery has no context code or EDI id, SDK v1 stored those metadata entries as empty values; SDK 2.x would leave them out. `shared` now stores them as empty, so delivered files keep the same metadata (checked on QA).
5. Delivered and archived objects are stored as `application/octet-stream`, as with SDK v1, whose client added that content type to the copy (tested on the fakes and checked on QA).
6. `distributor.yaml`: cloud-sdk logs at WARN, except the one line per client that shows it closing at shutdown.
7. An architecture test fails the build if distributor uses an AWS SDK type or a `shared` SDK v1 class.
8. pom: the direct SDK v1 SQS dependency is removed.
9. Two existing defects are kept, each with a disabled test asserting the correct behaviour; each fails when enabled and passes with a small fix. This PR does not change them.
    - **Every failure loops until the redrive** (since March 2021). The task passes a `pickupQueue` token to the shared error handler, which adds it again; building the failure event fails on the duplicate key.
      *Functional effect:* a failing delivery is retried on every receive, with an error-queue message each time, until the queue's redrive; its lineage gets no failure event.
    - **The error-rate health check never turns unhealthy** (since June 2017). It reads a meter that no failure marks.
      *Functional effect:* `/healthcheck` stays healthy however many deliveries fail.

### Backward compatibility

- **Same deliveries:** every delivered and archived object (bytes, key, user metadata, content type), message and event is identical to v1 for the golden inputs, and on QA for real documents.
- **Same metadata for missing values:** stored as empty, as before (item 4).
- **Same retry path:** a recoverable failure (for example a missing workspace document) goes back to the pickup queue with the shared retry setting, then to its dead-letter queue.
- **Same client settings** as the SDK v1 clients, and the same parameter names.
- **Same health checks:** names and placement.
- **Same configuration keys.** The only YAML change is the logger lines.

## Next Steps

> ✅ **Verified on QA (2026-11-20):** the v1 build and this build were run locally against QA, with the pickup messages on a borrowed DLQ and real deliveries into QA's outbound bucket under marked workflow ids.

- ✅ **Real documents:** a CONTRL FA and an X12 301 confirmation to a QA customer, and the FA without its optional metadata. Both builds delivered and archived byte-identical objects with the same content type and user metadata, under keys of the same shape from QA's real Network Services settings, with the same events.
- ✅ **Same as QA's own deliveries** of those two documents the day before: body, content type and metadata identical.
- ✅ **Downstream:** QA's FTP bridge picked up the new build's deliveries as it does v1's.
- ✅ **Null metadata on real S3:** the new build stored the missing values as empty, as v1.
- ✅ **Boot and shutdown:** the health checks are healthy; Ctrl+C closes the four clients and exits in under 2 s.

## Testing Notes

- **Test counts:** distributor ran 48 tests, 4 of them skipped. It now runs **61**, 2 of them skipped (the known-defect tests):
  - golden (6), functional (4: content type, a missing document retried then sent to the dead-letter queue, health checks, loggers), production wiring (2), architecture (2);
  - task (2), zip (2: the zip's entry, name, location and extension), the existing unit tests unchanged;
  - known defects (2, disabled).
- **Removed:** the four `@Ignore`d functional tests and their fixtures (the golden test covers their flows).
- **`shared`:** +2 tests (a null metadata value on a copy and on a put); 1846 tests, 1 skipped.
- **Test-first:** each behaviour change has a failing test first, then the change.
- **Full reactor build** (`mvn -B clean verify`) at the PR head: BUILD SUCCESS, all 26 modules, 11:08 min.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

✂ ---------------------------------------------------------------------------------------------------------------

## Part 2: review guide (for Arijit)

Commit by commit. Tracker log: [step-3-distributor](../../tracker/steps/step-3-distributor.md); runtime: [test 8](../../tracker/runtime/distributor.md#test-8).

| # | Commit | Look at |
|---|---|---|
| 1 | `6b3bd51d` golden test | Copy metadata from the copy request (the v1 fake drops it); zip by entry; the error cases' "not deleted" wait; stubs giving QA's key shapes |
| 2–3 | `7d909297` / `f7c5af6e` task | Payload instead of body; error-handler queue-message overload |
| 4–5 | `cf136a58` / `2f921625` zip | `WorkspaceService`; the new zip test |
| 6, 10 | `6d850283` / `5f15beca` module | `CloudServicesModule` with pass-through; listener; health checks; `readAllBytes`; tests on the cloud fakes |
| 7–8 | `5d3bf3bc` / `c50b8f0c` shared | `trimmed`: null → ""; the QA evidence in the message |
| 9 | `385559f2` golden correction | Only the two `null` values of one case, with the evidence |
| 11 | `d1bc2836` known defects | Both checked both ways |
| 12 | `d879fe3e` pom | SDK v1 SQS removed |
| 13 | `007d96cd` pre-review | Retry test; names; imports |

Pre-review: no new bug; 7 points (table in the tracker step page).
