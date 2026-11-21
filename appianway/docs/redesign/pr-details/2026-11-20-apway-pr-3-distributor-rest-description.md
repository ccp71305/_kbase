# WI01124532 PR: distributor-rest on cloud-sdk

Part 1 is the GitHub description (between the ✂ lines). Part 2 is the review guide, per commit, for Arijit only.

## Part 1: GitHub description

✂ ---------------------------------------------------------------------------------------------------------------

## Link to Story/Defect this work relates to

**WI01124532**: AppianWay AWS SDK v1 → v2 upgrade. This PR moves distributor-rest onto the `shared` cloud-sdk adapters, as #4–#11 did for the earlier services.

## What/Why I Did the changes

distributor-rest takes each REST-delivery `MetaData` from its queue, reads the document from the workspace, finds the subscription in Network Services, gets an OAuth token from the subscriber and posts the document to the subscriber's webhook, then publishes a close-workflow event. It now reaches AWS through cloud-sdk (AWS SDK 2.x) instead of AWS SDK v1. The HTTP calls to subscribers are unchanged.

| | Before (SDK v1) | After (cloud-sdk) |
|---|---|---|
| AWS clients | SQS ×2, S3, SNS, SSM (SDK v1) | `shared` `CloudServicesModule`; the Network Services credentials are still read from Parameter Store (or taken from the config when `usePassThrough` is set) |
| Listener, message type | `SQSListener`, SDK v1 `Message` | `MessageQueueListener` (drained on stop), `QueueMessage<String>` |
| Subscriber HTTP calls | Jersey, OAuth client, REST retryer | unchanged |
| Functional tests | none | JUnit 5 on the cloud-sdk fakes, with a local subscriber server |

### Changes

1. **Proof first: a golden test, written on the v1 code.** It passes on cloud-sdk with the same expected files.
    - **What it records:** every request to the subscriber (token request and POST: path, headers, body), every queue message, every event, every delete.
    - **The cases:** a delivery; no subscription; a 401 then a new token; a FAILURE answer; two subscribers; a webhook that is not the subscription's first action.
    - **The subscriber** is a local HTTP server; Network Services is stubbed with subscriptions pointing to it.
2. The task works on `QueueMessage<String>`.
3. `ExternalServicesModule` installs `CloudServicesModule`; `DistributorModule` builds the cloud-sdk listener; `DistributorApplication` uses `StorageConfigurationProvider`. A test builds the production module with the real clients and checks every binding.
4. `distributor-rest.yaml`: cloud-sdk logs at WARN, except the line per client that shows it closing at shutdown.
5. An architecture test fails the build if distributor-rest uses an AWS SDK type or a `shared` SDK v1 class. pom: the direct SDK v1 SQS dependency is removed.
6. Four existing defects are kept, each with a disabled test asserting the correct behaviour; each fails when enabled and passes with a small fix. This PR does not change them.
    - **One OAuth token for every subscriber (security):** the token one subscriber issued is sent to other subscribers' endpoints, until one answers 401.
    - **A rejected document is retried until the redrive:** a FAILURE answer is treated as a temporary failure, and no error-queue message is written.
    - **A handled failure loops:** no failure event is published and the message is not deleted (duplicate token in the failure event).
    - **A webhook that is not the subscription's first action is never delivered:** the request is built from the first action's settings.

### Backward compatibility

- **Same HTTP calls:** token requests and posts (paths, headers, body) identical to v1 for the golden inputs.
- **Same messages and events**, the same client settings and parameter names, the same configuration keys (only the logger lines change).
- **Health checks:** as before, distributor-rest registers none of its own.

## Next Steps

> ✅ **Verified on QA (2026-11-20):** the v1 build and this build were run locally against QA, with the pickup message on a borrowed DLQ.

- ✅ **Start, health and stop:** both start, report healthy, and stop on Ctrl+C in about 2 s; this build closes its four clients.
- ✅ **A delivery message without a subscription:** processed and deleted, with the same close-workflow event as v1.
- The webhook delivery itself is covered by the golden test: QA's distributor-rest had no traffic in the previous two weeks, and a real delivery would post to a real subscriber.

## Testing Notes

- **Test counts:** distributor-rest ran 142 tests, none skipped. It now runs **147**, 4 of them skipped (the known-defect tests):
  - golden (6), functional (2: health checks, loggers), production wiring (2), architecture (2), known defects (4, disabled);
  - the module test keeps its listener and configuration tests; its 11 tests of the removed SDK v1 event-publisher and listener providers go.
- **Test-first:** each behaviour change has a failing test first, then the change.
- **No change to `shared` or `functional-testing`.**
- **Full reactor build** (`mvn -B clean verify`): BUILD SUCCESS, all 26 modules, 11:53 min (the last commit changes tests only; the module was re-run on it).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

✂ ---------------------------------------------------------------------------------------------------------------

## Part 2: review guide (for Arijit)

Tracker log: [step-3-distributor-rest](../../tracker/steps/step-3-distributor-rest.md); runtime: [test 9](../../tracker/runtime/distributor-rest.md#test-9).

| # | Commit | Look at |
|---|---|---|
| 1 | `ef5598e6` golden test | The local `HttpServer` (OAuth and webhook), headers shown, the production HTTP bindings (the unqualified client and Network Services retryer, then the `@Named` final fields) |
| 2–3 | `72b7eb09` / `9daad89e` task | Payload instead of body |
| 4–5 | `1448aa42` / `49034d10` module | `CloudServicesModule` with pass-through; HTTP pieces unchanged; `DistributorModuleTest` 41 → 30 |
| 6 | `c3075b06` known defects | All four checked both ways |
| 7 | `1c8900da` pom | SDK v1 SQS removed |
| 8 | `22ae5a87` pre-review | Unused SDK v1 import in a test helper; names; javadoc |
| 9 | `23f13414` Copilot | Bodies recorded exactly (escaped, no trim); expected files re-recorded on v1: only the final line break appears |

Pre-review: no new bug; 10 points (table in the tracker step page).
