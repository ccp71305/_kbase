# Runtime verification plan: local runs against QA

← [Tracker home](README.md)

How to verify on real AWS what the tests and fakes cannot: the runtime checks promised in the PRs of the migrated services, the shutdown check ([A27](actions.md#a27)) and the IAM check ([A8](actions.md#a8)). Revised 2026-11-19 after Arijit's standing rule. Status: **plan; QA read access confirmed** (see [§10](#access-log)); decisions in [§8](#decisions); first test waiting for the OK in [§9](#what-i-need).

Services in scope now: event-writer (PR #4), error-processor (#5), email-sender (#6), dispatcher (#7). Each later service adds its own section.

## 1. Standing rule and approach

> **No change to any ECS environment and no deploys** (Arijit, 2026-11-19). No task-definition or service updates, no task stops, nowhere.

So each service runs **locally on the laptop**: the migrated build and, for the baseline, the SDK v1 build, both pointed at the **QA** AWS resources. Results are checked with the AWS CLI (S3, SQS). QA is preferred over INT because it is more robust and holds more real files.

| | QA (chosen) | INT |
|---|---|---|
| Account, CLI profile | `642960533737`, `642960533737_INTTRA2-QATeam` | `081020446316`, `default` |
| Resource names | `inttra2_qa_sqs_*`, `inttra2-qa-*` buckets, `inttra2_qa_sns_event` | `inttra_int_sqs_*`, `inttra-int-*` |
| ECS services (read only, for reference) | `ANEQAAPWY-001` (dispatcher, event-writer, error-processor, email-sender, distributor, distributor-rest, ingestor), `ANEQAAPWY-002` (splitter) | |

> ⚠️ **The QA account also hosts CVT and PROD.** It has the `inttra2_cv_*` and `inttra2_pr_*` queues and buckets, and the `ANECV*` and `ANEPR*` clusters (for example `dispatcher-prod`). Only `inttra2_qa_*`, `inttra2-qa-*` and test resources named `wi01124532-rt-*` are ever used. Every command names its resource explicitly; there are no wildcards over the account.
>
> **Rule (Arijit, 2026-11-19): never go to CVT. PROD only for read-only queries, and only after asking Arijit each time.** Discovery before this rule listed the service names of the CVT and PROD clusters once, read-only (§9).

## 2. Safety rules

- **Read-only by default.** Before any write I say exactly what it changes and wait for your OK. That covers creating or deleting a test queue, putting or deleting a test object, and sending or publishing a message. Every write is logged on this page.
- **No competing consumer.** A local service never reads a queue that a QA ECS service reads, because it would steal real messages. Its input and output queues are **test queues** (`wi01124532-rt-*`), created for the test and deleted after it (with your OK).
- **Real inputs are read, not moved.** Real files are read from `inttra2-qa-inbound-pickup` and `inttra2-qa-workspace`. For dispatcher, a test notification on the test queue points at a real inbound object, so nothing needs to be uploaded to the inbound bucket (an upload there would also trigger QA's own dispatcher).
- **Credentials stay in the AWS CLI SSO cache.** The local JVM gets only `AWS_PROFILE` and `AWS_REGION` (cloud-sdk's SDK 2.x has the SSO modules on its classpath). Nothing is written into the repository, the docs or the scratchpad.
- **The test window is agreed with you,** and the QA team is told if test objects land in shared buckets.

## 3. How a local run is set up

1. **Build** in the build worktree ([G4](rules.md#g4)): the feature branch (`07b5106f` or later) for the new build; `develop` for the SDK v1 baseline. `mvn -B -pl shared,<service> -am package -DskipTests` gives the shaded jar.
2. **Configuration:** the service's `conf/qa/<service>.properties`, `configuration/qa/network-services.properties` and `datadog.properties`, copied to the scratchpad. The queue URLs are replaced by the test queues of [§4](#scenarios); bucket names and the topic as agreed in [§8](#what-i-need) item 3. Config only, no code change.
3. **Run** as `run.sh` does: `java -Xmx384m -jar <service>.jar run <service>.yaml <service>.properties network-services.properties datadog.properties`, with `AWS_PROFILE=642960533737_INTTRA2-QATeam` and `AWS_REGION=us-east-1`. Dropwizard on local ports.
4. **Feed** the test input queue with the AWS CLI (`sqs send-message`). **Read** the outputs from the test output queues (`sqs receive-message`; nobody else reads them), from S3 (`s3api head-object` / `get-object`) and from the service's console log.
5. **Compare** the new build's outputs with the v1 build's, for the same input, after the golden tests' normalization (random ids and timestamps).

<a id="scenarios"></a>
## 4. Scenarios per service

Test queues (created with your OK): one input queue per service, plus output queues where the service sends somewhere: `wi01124532-rt-dispatcher-in`, `-routed`, `-bridge`, `-errors`; `wi01124532-rt-error-processor-in`, `-email`; `wi01124532-rt-email-sender-in`; `wi01124532-rt-event-writer-in`. Each gets a `_dlq` if the redrive behaviour is checked. Events: a test topic `wi01124532-rt-events` subscribed to a test queue `wi01124532-rt-events` (so events can be read directly), or the real `inttra2_qa_sns_event` ([§8](#what-i-need) item 3).

### 4.1 dispatcher (PR #7)

| # | Scenario | Input | Expected (same as the v1 build) |
|---|---|---|---|
| D1 | Routed file | A test notification for a real QA inbound object of a format and MFT id with an active profile | Workspace copy `<root id>/<id>`; `MetaData` on the routed test queue; close-run event |
| D2 | User metadata | A real object that has `xlogid` / `originalfilename` metadata (found in phase 0) | Both in the `MetaData` projections and the event tokens |
| D3 | Zip | A real zip in the inbound bucket (or a test zip under a test key) | Entries written next to the zip with its metadata plus `rootworkflowid`, `application/octet-stream`; one event per entry. Each entry's own notification is not raised by S3 for test keys, so it is sent by hand |
| D4 | Booking bridge | A notification for a `300_IFTMBF` object without a profile, with `xlogid` | `MetaData` on the bridge test queue, no workspace copy |
| D5 | Empty file | A notification with size 0 | Annotations in the workspace; failure `MetaData` on the errors test queue: the input of E1 |
| D6 | No profile | A notification for an MFT id without a profile | Message deleted; nothing sent |
| D7 | Parameters and Network Services | Startup | The Network Services credentials loaded from the QA parameter store; token fetched; profiles read |

### 4.2 error-processor (PR #5) and email-sender (PR #6)

| # | Check | Input | Expected (same as v1) |
|---|---|---|---|
| E1 | error-processor | D5's failure `MetaData` | Archive object in the workspace; one email-queue message per recipient on the email test queue; close event |
| E2 | email-sender | E1's email-queue message | The email arrives (recipient: [§8](#what-i-need) item 5): same sender, reply-to, subject and text as v1; CLOSE event with the SES message id; a second one within 120 s is dropped |
| E3 | SESv2 permission | E2 | The SESv2 `SendEmail` call succeeds with the QA identity ([A8](actions.md#a8) for the SES part) |

### 4.3 event-writer (PR #4)

| # | Check | Input | Expected (same as v1) |
|---|---|---|---|
| W1 | Store events | The events produced by D, E (or one sent by hand) | Stored under `eventstore/<yyyy-MM-dd>/…`: same key layout, UTF-8 body, `text/plain`, no user metadata |

<a id="boot"></a>
## 5. Startup checks (every service and build)

| Check | Expected |
|---|---|
| Starts | Dropwizard "Started", no stack trace |
| Credentials and region | Resolved from `AWS_PROFILE` (SSO) and `AWS_REGION` |
| Log level | No cloud-sdk INFO lines; "Closing … on application shutdown" only at stop |
| Health checks | The admin `/healthcheck` and ops endpoints on the local port: same names as v1, all healthy. The storage-read check logs one cloud-sdk ERROR "does not contain key anykey" per run until commons U15 ([F21](findings.md#f21)) |

<a id="shutdown"></a>
## 6. Shutdown check ([A27](actions.md#a27)), locally

**Done 2026-11-19 on dispatcher:** passed ([runtime/dispatcher.md](runtime/dispatcher.md#test-4b)). A27 is now optional.

1. Send a burst to the test input queue (for example 20 notifications for dispatcher).
2. While they are being processed, stop the local process **gracefully** (console Ctrl+C, which runs the JVM shutdown hooks. To be confirmed in phase 0: a hard kill on Windows skips them).
3. Check: the drain and then "Closing … on application shutdown" (one line per client) in the log; no "still in progress after 20 s" warning; every input processed exactly once or left on the test queue; start the service again and check the leftovers are processed.
4. event-writer needs `com.inttra.mercury.cloudsdk.config.ManagedCloudResource: INFO` in its YAML to log the close lines: a small PR before its check, or a local logging override for the run.

## 7. What a local run cannot show

These stay for the first real deployment through the normal release process (not part of this work, per the standing rule):

- **The ECS task roles' IAM permissions.** Local calls run as the QATeam SSO role. They can be checked by reading the roles' policies, if that read is allowed ([A8](actions.md#a8)).
- **Region and credential resolution inside the container** (EC2, bridge networking, instance metadata). It is the same chain as SDK v1, but not exercised locally.
- **The ECS stop timeout** (30 s) around the 20 s drain.

<a id="decisions"></a>
## 8. Decisions (Arijit, 2026-11-19) and the resulting setup

| Question | Decision |
|---|---|
| Test queues | **No new queues.** Use existing ones. A local service must not read a queue a QA ECS service reads, so the inputs and output sinks are **existing, empty `_dlq` queues that nothing consumes** (checked: 0 messages, last changed 2021–2024). `inttra2_qa_sqs_event_dlq` holds one real message and is not used |
| Workspace outputs | A **test bucket** (proposed name `inttra2-qa-wi01124532-rt`, created once with your OK, deleted at the end) |
| Events | The **real** `inttra2_qa_sns_event`; QA's event-writer stores them in `inttra2-qa-workspace/eventstore/`, where they are read back |
| Test partner | Picked from the inbound objects: **`315_IFTSTA` / `CA2000`** (`carriers/CA2000/`, daily automated QA files). Others seen: `323_IFTSAI` / `CA2000`, `301_IFTMBC` / `mram5166` |
| Email recipient | Unchanged: `appianway@inttra.com` |
| Network Services | Reachable over the VPN; the QATeam role reads the parameter store |
| Order | **Smallest first:** event-writer, then error-processor, email-sender, dispatcher; one test at a time, each agreed first |

**Queue mapping for the local runs** (configuration only; the rest of each service's QA properties unchanged):

| Service | Input (borrowed, empty) | Outputs | Workspace |
|---|---|---|---|
| event-writer | `inttra2_qa_sqs_splitter_pu_dlq` | Event objects | test bucket |
| error-processor | `inttra2_qa_sqs_subscription_errors_dlq` | Email queue → `inttra2_qa_sqs_email_outbound_dlq` (so QA's email-sender does not send it); events → real topic | test bucket |
| email-sender | `inttra2_qa_sqs_email_outbound_dlq` (error-processor's output) | SES email to `appianway@inttra.com`; error queue → `inttra2_qa_sqs_subscription_errors_dlq`; events → real topic | test bucket (reads error-processor's objects) |
| dispatcher | `inttra2_qa_sqs_dispatcher_pu_dlq` (hand-made notifications pointing at real `inttra2-qa-inbound-pickup` objects, read only) | Routed → `inttra2_qa_sqs_splitter_ce_pu_dlq` / `inttra2_qa_sqs_splitter_pu_dlq`; booking bridge → `inttra2_qa_sqs_booking_bridge_inbound_dlq`; errors → `inttra2_qa_sqs_subscription_errors_dlq` (the input of error-processor); events → real topic | test bucket |

Limits of borrowing a `_dlq`: a retry goes back to the borrowed queue (fine), and a sixth failure would target `<queue>_dlq_dlq`, which does not exist; the scenarios avoid it. Every message we send is removed by the local service or by us at the end.

<a id="what-i-need"></a>
## 9. Before the first test (event-writer): your OK for these writes

1. Create the test bucket `inttra2-qa-wi01124532-rt` (and later delete it), if the QATeam role allows `s3:CreateBucket`.
2. Send two test events (copied from a real QA event, ids marked `wi01124532-rt-`) to `inttra2_qa_sqs_splitter_pu_dlq`: one for the v1 build, one for the new build.
3. The two local runs write one event object each into the test bucket, and delete the messages they consumed.

Result to compare: the two stored objects (key layout, body, `Content-Type`, metadata), via `s3api head-object` / `get-object`. Plus each run's log (cloud-sdk at WARN; health checks).

<a id="access-log"></a>
## 10. Access and evidence log

| Date | What | Result |
|---|---|---|
| 2026-11-19 | `sts get-caller-identity` (QA profile) | `642960533737`, role `AWSReservedSSO_INTTRA2-QATeam` |
| 2026-11-19 | `ecs list-clusters`, `ecs list-services` (read) | QA AppianWay services on `ANEQAAPWY-001` / `-002`. This also listed service names on the CVT (`ANECVAPWY-001/002`) and PROD (`ANEPRAPWY-001/002`) clusters, read-only, before the rule above; not repeated |
| 2026-11-19 | `sqs list-queues --queue-name-prefix inttra2_qa_sqs_`, `s3 ls` (read) | QA queues and buckets visible |
| 2026-11-19 | `sqs get-queue-attributes` on seven QA `_dlq` queues; `s3 ls` of `inttra2-qa-inbound-pickup` format prefixes and latest objects (read) | DLQs empty except `inttra2_qa_sqs_event_dlq` (1); formats `300_IFTMBF`, `301_IFTMBC`, `315_IFTSTA`, `323_IFTSAI`, `Rates_v1`, `WEBBL_PDF`; daily files from `CA2000` |
| 2026-11-19 | `sqs get-queue-attributes` on `inttra2_qa_sqs_dispatcher_pu` (read) | Visibility timeout 30 s, wait 5 s, redrive to `_dlq` after 5 receives, 0 messages waiting |

<a id="test-log"></a>
## 11. Test logs

Moved 2026-11-19 to one page per service under [runtime/](runtime/README.md), each with its build, configuration and run commands and the detailed log of every test: [event-writer](runtime/event-writer.md) (test 1), [error-processor](runtime/error-processor.md) (test 2). The AWS CLI commands, explained: [runtime/aws/](runtime/aws/README.md).
