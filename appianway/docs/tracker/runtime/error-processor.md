# Runtime verification: error-processor

← [Runtime index](README.md) · [Plan](../runtime-verification.md) · [Tracker home](../README.md)

error-processor reads failure `MetaData` from its queue, archives the whole message into the bucket the message names (under `<rootWorkflowId>/<id>`), sends one email-queue message per recipient to its drop-off queue, and publishes a close event (`closeWorkflow`) to the event topic. Migrated in PR #5.

| | QA (real) | Local test |
|---|---|---|
| Input queue | `inttra2_qa_sqs_subscription_errors` | `inttra2_qa_sqs_subscription_errors_dlq` (borrowed, empty) |
| Drop-off (email) queue | `inttra2_qa_sqs_email_outbound` (QA's email-sender reads it) | `inttra2_qa_sqs_email_outbound_dlq` (borrowed, empty; so QA's email-sender sends nothing) |
| Archive | the bucket named in the message: `inttra2-qa-workspace` | the same, under the test's root ids `wi01124532-rt-ep-v1` / `-v2` |
| Events | `inttra2_qa_sns_event` | the same (real topic) |
| Recipient | `appianway@inttra.com` | unchanged |
| Local port | | 18082 |

Local properties (only the marked lines differ from `error-processor/conf/qa/error-processor.properties`; note that file has no final newline, so the added line needs one first):

```properties
error-processor.pickupSQSConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_subscription_errors_dlq   # changed
error-processor.dropOffSQSConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_email_outbound_dlq      # changed
error-processor.snsEventConfig.topicArn=arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event
error-processor.s3WorkspaceConfig.bucket=inttra2-qa-workspace
error-processor.errorEmailRecipient=appianway@inttra.com
componentName=error-processor
server.connector.port=18082                                                                                                          # added
```

<a id="summary"></a>
## Summary in functional terms

When any AppianWay service reports a failed file, error-processor keeps a copy of the failure, asks email-sender to mail the support address, and records the step in the lineage. **On the new build all three happen exactly as before:** the same archived copy in the same place, the same email request for the same recipient, the same lineage event. It starts, reports healthy and uses the same queues, bucket and topic. Two differences, neither functional: its queue health check answers faster, and it logs one extra error line per storage health check (cosmetic; a fix is requested from commons as U15).

<a id="pr-next-steps"></a>
## PR #5 Next Steps: covered?

| PR Next Step | Covered | Where |
|---|---|---|
| Boot error-processor and send a failure message; check that the archive, the email-queue message and the event match the v1 build | ✅ Yes | [Test 2](#test-2): archive byte-identical, email request and event identical apart from random ids and time |
| Stop the service while messages are being processed: clients close; every message either fully processed and deleted, or delivered again | ➖ By the dispatcher check | Agreed 2026-11-19: the shutdown check runs once, on dispatcher. The drain and the close order are in the shared listener and `CloudServicesModule`, the same code in every migrated service |

<a id="how-it-is-run-locally"></a>
## How it is run locally

All commands in Git Bash, from the scratchpad folder that holds the jar and the configuration (`S=...scratchpad/<test>`). Explanations of each AWS CLI command: [AWS commands](aws/README.md).

**1. Build both jars** in the build worktree (`C:\Users\arijit.kundu\projects\appianway-build`, so VS Code's background compiler cannot interfere):

```bash
cd ../appianway-build
git fetch -q origin
git checkout -q --detach origin/develop          # the SDK v1 build ("v1")
mvn -B -q -pl shared,error-processor -am package -DskipTests -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
cp error-processor/target/error-processor-*.jar $S/error-processor-v1.jar          # the shaded jar (not original-*.jar)
git checkout -q --detach 07b5106f                # the feature branch with the service migrated ("new")
mvn -B -q -pl shared,error-processor -am package -DskipTests -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
cp error-processor/target/error-processor-*.jar $S/error-processor-v2.jar
```
- `-pl shared,error-processor -am`: build only the service and the modules it needs (`-am` = also make), shared included so a stale `mercury-shared` jar from `~/.m2` is never used.
- `package -DskipTests`: compile and shade the jar; the tests already ran in the PR build.
- `-Daether…=_any.repositories`: the local resolver flag (guard G2).

**2. Configuration:** the service's QA properties with only the queues (and a local port) changed, plus QA's shared property files, exactly as the container gets them (`run.sh`):

```bash
cp configuration/qa/network-services.properties configuration/qa/datadog.properties $S/
```

**3. Start** (one build at a time, in the background):

```bash
cd $S && eval "$(aws configure export-credentials --profile 642960533737_INTTRA2-QATeam --format env)" \
  && export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 \
  && exec java -Xmx384m -jar error-processor-v1.jar run error-processor.yaml error-processor.properties network-services.properties datadog.properties > run-v1.log 2>&1
```
- `eval "$(aws configure export-credentials …)"`: temporary QA credentials into this process environment only (never written down).
- `AWS_REGION` / `AWS_DEFAULT_REGION`: the region for SDK 2.x and SDK v1.
- `exec java -Xmx384m`: the same heap limit as the QA task (`JVM_Xmx`); `exec` replaces the shell, so stopping the background task stops Java.
- `-jar … run error-processor.yaml <properties…>`: the same command line as `run.sh` in the container: the `run` command of the shared `ConfigProcessingServerCommand`, the YAML from inside the jar, then the property files in order.
- `> run-v1.log 2>&1`: the console log to a file.

**4. Wait until started, then check health:**

```bash
until grep -qE "Started oejs.Server|Exception in thread" run-v1.log; do sleep 1; done
curl -s -m 60 http://localhost:18082/admin/healthcheck          # read only
```
`/admin/healthcheck` runs the default checks (reads only). **The ops endpoint `/admin/opsHealthcheck` also runs the write checks** (it sends `HEALTHCHECK` to the outbound queue and publishes to the event topic), so it is not called in these tests.

**5. Stop:** stop the background task (on Windows this is a hard stop: no shutdown hooks). Check the port is free: `curl -s -m 3 http://localhost:18082/admin/healthcheck || echo stopped`.

<a id="test-2"></a>
## Test 2 (2026-11-19, approved by Arijit)

Plan: one failure message per build on the borrowed input queue; each local run archives it, sends one email-queue message to the borrowed drop-off queue, and publishes a close event to the real QA topic; compare the archives, the email-queue messages and the logs. v1 build = `develop` `05a1d8fb`, new build = feature `07b5106f`. Times are local (EST).

**Test inputs** (two dispatcher-style failure `MetaData`, one per build, marked by their root id):

```json
{"messageId":"wi01124532-rt-ep-v1-message","workflowId":"wi01124532-rt-ep-v1","rootWorkflowId":"wi01124532-rt-ep-v1","parentWorkflowId":"wi01124532-rt-ep-v1","bucket":"inttra2-qa-workspace","fileName":"wi01124532-rt-ep-v1/annotations","component":"dispatcher","exitStatus":"failure","timestamp":"2026-11-19 18:55:00.00","projections":{"mftId":"CA2000","pickupFileName":"315_IFTSTA/20261119/carriers/CA2000/wi01124532-rt-test.edi"}}
```
(the v2 one is the same with `-v2`).

| # | Time | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 13:52 | Built the jars in the build worktree | v1: `develop` `05a1d8fb`; new: `07b5106f` | Both built: 44 MB / 92 MB |
| 2 | 13:53 | Local config: QA `error-processor.properties` with the input and drop-off queues changed and port 18082 added (the file had no final newline: the first attempt glued the port onto `componentName`; fixed before any run) | scratchpad | |
| 3 | 13:53 | Pre-checks (read) | `inttra2_qa_sqs_subscription_errors_dlq`, `inttra2_qa_sqs_email_outbound_dlq` | Both 0 visible, 0 in flight; queue receive wait 5 s |
| 4 | 13:54 | Started the **v1 build** locally | port 18082 | Started in 0.4 s |
| 5 | 13:54 | v1 `/admin/healthcheck` (read) | local | `InboundQueue -> …subscription_errors_dlq` (5.5 s), `S3 read -> inttra2-qa-workspace` (0.6 s), `deadlocks`: all healthy |
| 6 | 13:54 | **Unplanned WRITE:** v1 `/admin/opsHealthcheck` | local | All healthy, but the ops checks **write**: one `HEALTHCHECK` message to `inttra2_qa_sqs_email_outbound_dlq` (message `671fa523-…`) and one `HEALTHCHECK` publish to `inttra2_qa_sns_event` (the routine message QA's own ops checks send). Not called again |
| 7 | 13:54 | **WRITE** `sqs send-message` of `failure-v1.json` | `inttra2_qa_sqs_subscription_errors_dlq` | MessageId `19b8b9c8-fc86-4483-9b95-c6d79450f12a` |
| 8 | 13:54 | Read back the archive (read) | `inttra2-qa-workspace/wi01124532-rt-ep-v1/46a8b8de-4b0b-4c7b-bcde-44525e827a17` | Stored within 4 s: `text/plain`, 431 bytes, no user metadata, **byte-identical to the input message**. Input queue: 0/0 (consumed and deleted) |
| 9 | 13:56 | Peeked the drop-off queue (read, visibility 2 s, repeated) | `inttra2_qa_sqs_email_outbound_dlq` | 2 messages: the `HEALTHCHECK` and the email request `1264d08b-…` (new workflow id, parent and root `wi01124532-rt-ep-v1`, `fileName` = the archive, projection `recipientEmailId=appianway@inttra.com`, `exitStatus` success, `component` error-processor). A first peek with visibility 0 returned the `HEALTHCHECK` ten times (see [AWS commands](aws/sqs.md#4-sqs-queues-and-messages)) |
| 10 | 13:57 | Checked the close event in QA's event store (read) | `inttra2-qa-workspace/eventstore/2026-11-19/wi01124532-rt-ep-v1/` | Not there: QA's event-writer is not consuming (see Observations) |
| 11 | 13:57 | QA ECS services (read) | `ANEQAAPWY-001`: event-writer-qa, error-processor-qa, email-sender-qa, dispatcher-qa | Each 1 desired, 1 running (task definitions `…-qa-Task:5`, dispatcher `:6`) |
| 12 | 13:57 | Stopped the v1 process | local | Port free |
| 13 | 13:58 | Started the **new build** | port 18082 | Started in 0.4 s |
| 14 | 13:58 | New build `/admin/healthcheck` (read) | local | Same three checks, all healthy. `InboundQueue` 0.5 s (v1 5.5 s: [F10](../findings.md#f10)). One cloud-sdk **ERROR** "The specified key does not exist" from `AbstractStorageObject` for the S3-read probe of `anykey`: [F21](../findings.md#f21) (commons ask U15), seen for real |
| 15 | 13:58 | **WRITE** `sqs send-message` of `failure-v2.json` | `inttra2_qa_sqs_subscription_errors_dlq` | MessageId `8d36cd0b-fd17-4cd6-8ab6-efb3d391a750` |
| 16 | 13:58 | Read back the archive (read) | `inttra2-qa-workspace/wi01124532-rt-ep-v2/24fc8124-dc51-4f30-9185-4095fbd2a274` | `text/plain`, 431 bytes, no user metadata, **byte-identical to the input message**. Input queue: 0/0 |
| 17 | 13:58 | Peeked the drop-off queue (read) | `inttra2_qa_sqs_email_outbound_dlq` | 3 messages: `HEALTHCHECK`, v1's `1264d08b-…`, the new build's `4b69d895-…` |
| 18 | 13:58 | Compared the two email-queue messages (scratchpad) | | **Identical** after normalizing what is random or run-specific: `messageId`, `workflowId` (random), the root marker, the archive id in `fileName`, `timestamp`. Same keys in the same order, same projections in the same order |
| 19 | 13:59–14:00 | QA event queue metrics and the event-writer task's log (read) | `inttra2_qa_sqs_event` (CloudWatch `AWS/SQS`), log group `inttra2-qa-lg-app-way` | See Observations |
| 20 | 14:00 | Stopped the new build | local | Port free. Log: no cloud-sdk INFO line; one ERROR, the F21 line |
| 21 | 14:43 | **WRITE** (agreed) `sqs receive-message` (visibility 30 s) then `sqs delete-message` of the stray `HEALTHCHECK` only, by its receipt handle | `inttra2_qa_sqs_email_outbound_dlq` | `671fa523-…` deleted; the two email requests not received, untouched. Queue: 2 visible |
| 22 | 14:43 | QA event-writer task and service events (read) | `ANEQAAPWY-001`, task `dff5528c…`, service `event-writer-qa` | **Cause found:** the task `STOPPED` with reason "Host EC2 (instance i-095c596e376849f4c) terminated". ECS started a replacement task `8ac99662…` at 14:40:32 and reached a steady state at 14:41. CloudWatch: 210 received, 104 deleted in the 14:38 period; queue 0 visible, 0 in flight at 14:43 |
| 23 | 14:44 | Read the two close events from QA's event store (read) | `inttra2-qa-workspace/eventstore/2026-11-19/wi01124532-rt-ep-v1/error-processor-closeRun-1657a8d0-….json`, `…-ep-v2/error-processor-closeRun-5d43fcfa-….json` | Both stored by QA's (replacement) event-writer: `closeRun` / `closeWorkflow`, status success, runTag `error-processorRun`, tokens `pickupQueue` and `dropOffQueue` (the borrowed queues). **Identical** after normalizing ids, the marker and times; same fields in the same order |

**Result of test 2: passed.** The archive is byte-identical with the same headers, the email-queue message and the close event are identical apart from random ids and time, the input is consumed and deleted, the health checks keep their names and are healthy, and cloud-sdk logs nothing at INFO (only the known F21 line).

<a id="observations"></a>
### Observations

- **QA's event-writer stopped consuming at about 13:44 EST**, before this test, **because its EC2 host was terminated** (found at 14:43, step 22); ECS replaced the task at 14:40 and the backlog drained. CloudWatch on `inttra2_qa_sqs_event`: received and deleted normal through the 13:39 period (228 in 5 minutes), then 0; the oldest message's age rising (830 s at 13:55); 15 messages waiting at 13:58, none in flight. `event-writer-qa` has 1 running task (`dff5528c…`, started 07:10), which logged nothing after its startup lines (normal for v1, which logs a stored event only at DEBUG). **Not caused by these tests:** test 1's local event-writer read only `inttra2_qa_sqs_splitter_pu_dlq` (its configuration and its health-check name show it), and nothing touched `inttra2_qa_sqs_event` or the service. Reported to Arijit; nothing was changed in ECS.
- **Left in QA:** the two archives under `wi01124532-rt-ep-v1/` and `-v2/` in `inttra2-qa-workspace` (kept, per Arijit); two messages in the borrowed `inttra2_qa_sqs_email_outbound_dlq`: v1's and the new build's email requests, the inputs of test 3 (the stray `HEALTHCHECK` was deleted in step 21); the two close events in QA's event store.

