# WI01124532 PR: watermill-publisher on cloud-sdk

Part 1 is the GitHub description (between the ✂ lines). Part 2 is the review guide, per commit, for Arijit only.

## Part 1: GitHub description

✂ ---------------------------------------------------------------------------------------------------------------

## Link to Story/Defect this work relates to

**WI01124532**: AppianWay AWS SDK v1 → v2 upgrade. This PR moves watermill-publisher onto the `shared` cloud-sdk adapters, as #4–#12 did for the other AppianWay services.

## What/Why I Did the changes

watermill-publisher takes each status-event `MetaData` from its queue, reads the status-event XML from the workspace (ISO-8859-1), turns it into a `ShipmentStatusChangeEvent` and streams it to e2open Watermill over gRPC. The message is deleted when Watermill acks the event, or at once when the document cannot be transformed. Every 30 minutes it moves the dead-letter queue's messages back to the pickup queue. It now reaches AWS through cloud-sdk (AWS SDK 2.x) instead of AWS SDK v1. The gRPC publish, the protobuf payload and the Watermill credentials are unchanged.

| | Before (SDK v1) | After (cloud-sdk) |
|---|---|---|
| AWS clients | SQS ×2, S3, SNS (built, never used), SSM (SDK v1) | `shared` `CloudServicesModule`; the Watermill username and password still come from Parameter Store at startup; no notification client |
| Listener, message type | `SQSListener` ×`listenerThreads`, SDK v1 `Message` | `MessageQueueListener` ×`listenerThreads`, `QueueMessage<String>` |
| Shutdown | listeners stopped, nothing waited for | every listener stops receiving and every dispatcher stops taking batches; the batch in progress, its acks and a redrive run in progress get up to 20 s, then the clients close |
| gRPC to Watermill | `publishShipmentStatusMicroBatch`, gzip, call credentials | unchanged |
| Load-test harness | `task/Test.java` in the main sources (SDK v1, INT names in code) | a harness in the test sources, everything as arguments |
| Functional tests | none | JUnit 5 on the cloud-sdk fakes, with a local gRPC server playing Watermill |

### Changes

1. **Proof first: a golden test, written on the v1 code.** It passes on cloud-sdk with the same expected files.
    - **Watermill** is played by a local gRPC server. The production modules run unchanged; only the gRPC connection points at that server.
    - **What it records:**
        - each gRPC call, with the metadata the service sets: username, password, tenant, compression;
        - each event sent to Watermill;
        - each ping;
        - each message sent to or deleted from a queue;
        - each document read from the workspace.
    - **The cases:**
        - two real QA status events: published, then deleted when Watermill acknowledges them;
        - a document stored in real ISO-8859-1, with routes (tenants) and another event provider;
        - a document that is not a status event: deleted, nothing published;
        - a document missing from the workspace: the message stays on the queue;
        - Watermill does not acknowledge: the message stays on the queue;
        - Watermill drops the stream: the next message waits for Watermill, opens a new stream and is published;
        - the dead-letter queue is moved back to the pickup queue (message body only).
2. The task, dispatcher and ack observer work on `QueueMessage<String>` and the `shared` `MessageQueueClient`.
3. `ExternalServicesModule` installs `CloudServicesModule`; `WatermillPubModule` builds the cloud-sdk listeners and the redrive on the cloud clients; `WatermillPubApplication` uses `StorageConfigurationProvider`. A test builds the production module with the real clients and checks every binding.
4. **Shutdown drain:** a message is deleted only when Watermill acknowledges its event, so work counts as finished only when the acknowledgements are back. On stop:
    - no listener takes a new batch (those messages stay on the queue for the next start);
    - the batch in progress and its acknowledgements get up to 20 s, as does a dead-letter move in progress;
    - only then are the cloud clients closed.
5. `watermill-publisher.yaml`: cloud-sdk logs at WARN, except the line per client that shows it closing at shutdown.
6. An architecture test fails the build if watermill-publisher uses an AWS SDK type or a `shared` SDK v1 class. pom: the direct SDK v1 SQS dependency is removed.
7. Existing defects are kept, three of them with a disabled test asserting the correct behaviour (each fails when enabled and passes with a small fix). This PR does not change them.
    - **Failed events stop being retried:** every 30 minutes the service moves failed messages from its dead-letter queue back for another try. One SQS error during that move (a throttle or a network blip) stops the moves for good, until the service is restarted. Failed status events then pile up in the dead-letter queue and never reach e2open.
    - **Each Watermill reconnect leaks a thread:** every time the connection to Watermill drops and is re-opened, one more background thread is left running. A service that reconnects often slowly uses more memory and threads.
    - **One failed delete causes duplicates:** after Watermill acknowledges an event, the service deletes its message. If one delete fails, the whole connection is dropped, and every other event sent on it but not yet acknowledged is sent to e2open a second time.
    - Without a test:
        - **Garbled place names at e2open (seen in QA):** the producer of these documents writes them in UTF-8 but labels them ISO-8859-1, so e2open receives "Tokyo, TÃ´kyÃ´" instead of "Tokyo, Tôkyô". The fix belongs to the producer, not to this service.
        - **A message that never succeeds is retried for ever:** it moves between the dead-letter queue and the pickup queue every 30 minutes, with no limit.

### Backward compatibility

- **Same gRPC traffic:** the events, the call metadata and the pings are identical to v1 for the golden inputs.
- **Same queue behaviour:** delete on ack or on a transform failure, the ack expiry from the queue's visibility timeout, the redrive's receive (10 messages, 20 s) and body-only move. cloud-sdk asks for all queue attributes where v1 asked for `VisibilityTimeout` only (same IAM action).
- **Same documents read:** whole-object bytes decoded as ISO-8859-1.
- The same parameter names, client settings and configuration keys (only the logger lines change). No health checks, as before.

## Next Steps

> ✅ **Verified on QA (2026-11-21):** the v1 build and this build were run locally against QA, with the pickup messages on a borrowed queue. Watermill was a local stand-in with the same gRPC service over TLS, so nothing was sent to e2open.

- ✅ **Start and health:** both start with 2 listeners and report healthy (Dropwizard's own check only, as before).
- ✅ **Publish:** the two real QA status events, read from QA's workspace, are sent with the credentials from QA's Parameter Store, and each message is deleted when its event is acknowledged. The events and the call metadata are **identical** between the two builds, and identical to the golden test's expected events.
- ✅ **Stop when idle:** Ctrl+C stops this build in about 1.4 s with its four cloud clients closed; on three idle stops no listener error was logged.
- ✅ **Stop while acknowledgements are pending** (Watermill delayed them by 5 s): this build waited for them (5.6 s), deleted both messages, then closed its clients, and the queue stayed empty. The old build stopped at once, and both messages came back on the queue: in production they would have been sent to e2open a second time.
- ✅ **Stop when Watermill never acknowledges:** this build waits the 20 s limit, logs a warning and closes; the unconfirmed messages are delivered again, as intended.

## Testing Notes

- **Test counts:** watermill-publisher ran 153 tests, none skipped. It now runs **181**, 3 of them skipped (the known-defect tests):
  - golden (7), boot through the server command (2), production wiring (1), architecture (2), dispatcher and drain (7), stream acks (4), shutdown manager (5), known defects (3, disabled);
  - the module test keeps its listener, channel and redrive tests; its 3 tests of the removed SNS event publisher go.
- **Test-first:** each behaviour change has a failing test first, then the change.
- **No change to `shared` or `functional-testing`.**
- **Full reactor build** (`mvn -B clean verify`): BUILD SUCCESS, all 26 modules, 11:55 min (the later commits change watermill-publisher only; the module was re-run on each).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

✂ ---------------------------------------------------------------------------------------------------------------

## Part 2: review guide (for Arijit)

Tracker log: [step-4a-watermill-publisher](../../tracker/steps/step-4a-watermill-publisher.md); inputs: [fixtures/qa-se-watermill](../../tracker/runtime/fixtures/qa-se-watermill/README.md).

| # | Commit | Look at |
|---|---|---|
| 1 | `0c37be0a` golden test | The local Netty server (interceptor for the metadata, acks by message id), the one `Modules.override` (the channel), the byte-exact workspace stub, `.gitattributes` `-text` for the XML inputs, the mojibake line (KD-27) |
| 2–3 | `b64b7597` / `a79f6eb1` task | Payload instead of body; `submit` bridges until step 5 |
| 4–5 | `93dc9b51` / `7490fd1f` ack observer | `MessageQueueClient` in place of `SQSClient` (types only) |
| 6 | `760ce872` golden adjustments | Only the attribute-read line changed in the expected files (re-written by v1); the missing-document case waits for its batch |
| 7 | `5412587a` harness | `Test.java` gone from main; the new harness |
| 8–9 | `2738f0d3` / `008afec2` module | `CloudServicesModule` (no topic, parameters); one listener + dispatcher + stream per thread; redrive receive options; golden on the cloud fakes, expected files unchanged |
| 10–11 | `19915445` / `968f535a` drain | Batch counter + `awaitAcks`; one deadline |
| 12 | `d207d9b0` pom | SDK v1 SQS removed |
| 13 | `4f0c89f0` known defects | All three checked both ways |
| 15–16 | `790ddc09` / `db2769aa` Copilot: ack expiry race | Deletes in progress counted in `pendingAcks` |
| 17 | `6d69eb47` Copilot: tests | Managed objects started before stopped; test scheduler shut down |
| 18 | `98d5f8fb` Copilot: golden test | The service list read under its lock |
| 14 | `61f2489f` pre-review fix | Dispatchers all stop taking batches before any wait; the redrive scheduler stopped and waited for; harness futures; javadoc |
