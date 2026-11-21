# Runtime verification: watermill-publisher

← [Runtime index](README.md) · [Tracker home](../README.md)

<a id="summary"></a>
## In functional terms

watermill-publisher sends INTTRA's container status events to e2open Watermill. **On QA the new build starts, reports healthy, reads the two real QA status events from the workspace, sends exactly the same events as the old build (with the Watermill credentials from QA's Parameter Store), deletes each message when its event is acknowledged, and stops cleanly, closing its four cloud clients. Stopped while Watermill's acknowledgements are still on their way, it waits for them and deletes the messages before closing (the old build stops at once, and those messages come back to be sent again).** Nothing went to e2open ([D48](../decisions.md#d48)): the service's Watermill address pointed at a local stand-in that speaks the same gRPC service over TLS, records what arrives and acknowledges each event. The run also shows today's garbled characters ([KD-27](../known-defects.md#kd-27)) in both builds.

How the builds are built and run: [how-to](../howto/build-and-run-a-service-locally.md). Files: [fixtures/test10-watermill-publisher/](fixtures/test10-watermill-publisher/).

<a id="test-10"></a>
## Test 10 (2026-11-21, 02:13–02:20 UTC)

v1 = `36a14ced` (feature tip); new = the PR #13 head `61f2489f`. Pickup `inttra2_qa_sqs_rest_delivery_dlq` (borrowed, as in test 9, empty before and after); error queue `inttra2_qa_sqs_subscription_errors_dlq` (borrowed; the service sends nothing to it); workspace bucket and Parameter Store: QA's. Watermill: `localhost:18443`, a local stand-in (`LocalWatermill.java`, run on each build's own jar) with a self-signed certificate for `localhost`; the service's JVM trusts it through a copy of the JDK's CA list plus that one certificate (`-Djavax.net.ssl.trustStore`), so AWS TLS works as usual. The stand-in records whether username and password are present, never their values. Inputs: the two real QA status events of 2026-11-19 (Z9 and Z7, [fixtures/qa-se-watermill](fixtures/qa-se-watermill/README.md)), **read in place** from QA's workspace, with the producer's real `MetaData` and workflow ids marked `wi01124532-rt-wmp-<build>-<z9|z7>`.

| # | Time (UTC) | Action | Result |
|---|---|---|---|
| 1 | 02:0x | Pre-checks (read): borrowed queue, both workspace objects, the two Watermill parameters (names only) | queue 0/0 (visibility 30 s); objects 5112 / 5117 bytes; both parameters found |
| 2 | 02:1x | Built the jars (`-pl watermill-publisher -am package -DskipTests`; full build of the PR content green, [step-4a](../steps/step-4a-watermill-publisher.md)) | 109 MB each; the yaml differs only in the two logger lines |
| 3 | 02:13–02:15 | **WRITE** v1, first attempt | Worked (2 published, 2 deleted); the script's start-wait pattern was wrong (waited its full 90 s), so rerun |
| 4 | 02:15:57–02:16:30 | **WRITE** v1: start, health check, 2 `send-message`, Ctrl+C | started (2 listeners); `/admin/healthcheck` HTTP 200, `deadlocks` healthy only (the service registers no check, as before); 2 events at the stand-in, both acked, both messages deleted (queue 0/0); stopped in 1.5 s |
| 5 | 02:16:31–02:17:03 | **WRITE** new build: the same | the same; **4 clients closed**; stopped in 1.4 s |
| 6 | 02:17 | Compare (local files) | **events identical** v1 / new, and identical to the golden test's expected events; call metadata identical: `PublishShipmentStatusMicroBatch`, username and password present, tenant `INTTRA`, `grpc-encoding=gzip`, one stream per listener |
| 7 | 02:18–02:20 | New build: start, 8 s idle (listeners in their long poll), Ctrl+C, twice more | 1.4–1.5 s each; 0 "Exception in SQS Listener", 0 other ERROR; 4 clients closed each time |
| 8 | 02:20 | Final check (read): borrowed queue | 0/0 |

**ERROR lines, both builds, expected:** the dead-letter redrive reads `<pickup>_dlq`, here `inttra2_qa_sqs_rest_delivery_dlq_dlq`, which does not exist (a borrowed pickup queue). v1 logs 4 lines (the SDK v1 retry logger), the new build 1 (`SqsMessagingClient: Queue … does not exist`); then the redrive is not scheduled again until a restart, in both, which is [KD-28](../known-defects.md#kd-28) seen live. The redrive itself is covered by the golden test (body only, the attribute left behind). Not run: the redrive against a real dead-letter queue (QA's `inttra2_qa_sqs_watermill_ce_dlq` belongs to QA's running service).

**Pre-review point 7** (an ERROR at every idle shutdown, the listener client closing under the long poll): **not reproduced** on 3 idle Ctrl+C runs (steps 5 and 7), as for ingestor in test 7.

**Result of test 10: passed** (including the busy stop below). **Left in QA:** nothing (the 4 marked messages were deleted by the service; the workspace was only read). Nothing was sent to e2open.

<a id="test-10-busy-stop"></a>
### Busy stop (2026-11-21, 03:34–03:39 UTC)

Added after Copilot's third review of PR #13 ("needs a closer look": the shutdown drain had been stopped only idle at runtime). Same set-up as above; the new build rebuilt at the PR head `98d5f8fb` (with the ack-expiry fix). The local Watermill now delays its acks (`LocalWatermill.java … <ack delay ms>`, `-1` = never). [`run-busy.sh`](fixtures/test10-watermill-publisher/run-busy.sh) `<build> <busy|noack> <delay>`: start, send the two marked messages (`wi01124532-rt-wmp-busy-…` / `-noack-…`), wait until both events reach the stand-in, **Ctrl+C at once** (acks pending), then count the queue right away and 35 s later (after the 30 s visibility timeout, a message not deleted is visible again). [`cleanup.sh`](fixtures/test10-watermill-publisher/cleanup.sh) deletes only messages with the `wi01124532-rt-wmp-` marker.

| # | Time (UTC) | Run | Stop took | Acks handled / deleted | Queue right after → 35 s later | Log |
|---|---|---|---|---|---|---|
| 9 | 03:34:59–03:36:04 | **WRITE** new build, acks after 5 s | **5.6 s** (waited for the acks) | 2 / 2, then the 4 clients closed (log order: both "Response for messageId", then the 4 "Closing") | 0/0 → **0/0** | no drain warning, 0 ERROR |
| 10 | 03:36:13–03:37:09 | **WRITE** v1, acks after 5 s | 1.6 s (no wait) | 0 / 0: the stand-in's acks never came back to a running service | 0/0 → **2/0**: both messages back on the queue, **published a second time in production** | — |
| 11 | 03:37:2x | **WRITE** `cleanup.sh` | | deleted the 2 messages of step 10 (both ours) | | |
| 12 | 03:37:43–03:39:00 | **WRITE** new build, Watermill never acks | **21.3 s** (the 20 s limit) | 0 / 0 | 0/0 → 2/0 (not acknowledged: delivered again, as intended) | WARN "Messages still in progress or not acked after 20 s…", then the 4 clients closed; 0 ERROR |
| 13 | 03:39:xx | **WRITE** `cleanup.sh`; final check (read) | | deleted the 2 messages of step 12 (both ours) | **0/0** | |

**Result:** the drain works with real clients: acknowledgements still on their way when the service stops are waited for, their messages deleted, and only then the clients closed; an event Watermill never confirms is left on the queue within the 20 s limit. The old build loses the pending acknowledgements, so those events would be sent to e2open twice. **Left in QA:** nothing (queue 0/0).

### Commands

```bash
R=<scratchpad>/rt10; cd $R
openssl req -x509 -newkey rsa:2048 -nodes -keyout wm-key.pem -out wm-cert.pem -days 7 \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost"
cp "$(cygpath -u "$JAVA_HOME")/lib/security/cacerts" truststore.jks
keytool -importcert -noprompt -alias local-watermill -file wm-cert.pem -keystore truststore.jks -storepass changeit
eval "$(aws configure export-credentials --profile $P --format env)"; export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
for b in v1 v2; do bash run.sh $b | tee steps-$b.log; done
```

- `openssl req -x509 … -nodes` makes a throw-away self-signed certificate and an unencrypted key (`-nodes`) for `localhost` (the name the service's TLS check compares, from `subjectAltName`); 7 days. Not kept in the fixtures.
- `truststore.jks` is a copy of the JDK's own CA list (`cacerts`) with the stand-in's certificate added, so the service trusts both AWS and the stand-in; passed with `-Djavax.net.ssl.trustStore` and `-Djavax.net.ssl.trustStorePassword=changeit` (the JDK default). gRPC's Netty TLS uses the JDK's default trust store.
- `run.sh <build>` ([fixture](fixtures/test10-watermill-publisher/run.sh)): queue count; starts `java -cp watermill-publisher-<build>.jar LocalWatermill.java 18443 …` (Java 17 runs a single source file directly, with the jar's gRPC and protobuf classes); starts the service with `start-java.ps1`; waits for `Started oejs.Server`; reads `/admin/healthcheck` on port 18090; sends the two marked messages; waits until the queue is 0/0; sends Ctrl+C with `send-ctrl-c.ps1` and times the stop.
- `watermill-publisher.properties` ([fixture](fixtures/test10-watermill-publisher/watermill-publisher.properties)): QA's file with the pickup and error queues borrowed, `watermill-grpc.se.host=localhost`, `port=18443`, `server.connector.port=18090`.
