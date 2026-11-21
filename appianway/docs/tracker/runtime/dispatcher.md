# Runtime verification: dispatcher

← [Runtime index](README.md) · [Plan](../runtime-verification.md) · [Tracker home](../README.md)

dispatcher takes each file that lands in the inbound bucket: it reads the S3 notification, looks up the sender's integration profile in Network Services, refuses empty or unknown files (to the error queue, with annotations), copies the file into the workspace under a new root id with its user metadata, and routes it to the next queue (splitter, CE splitter, WebBL or booking bridge) with a lineage event. Migrated in PR #7.

| | QA (real) | Local test |
|---|---|---|
| Input queue | `inttra2_qa_sqs_dispatcher_pu` | `inttra2_qa_sqs_dispatcher_pu_dlq` (borrowed) |
| Routed (this file type, `315_IFTSTA`) | `inttra2_qa_sqs_splitter_ce_pu` | `inttra2_qa_sqs_splitter_ce_pu_dlq` (borrowed) |
| Splitter and WebBL | `inttra2_qa_sqs_splitter_pu` | `inttra2_qa_sqs_splitter_pu_dlq` (borrowed) |
| Booking bridge | `inttra2_qa_sqs_booking_bridge_inbound` | `inttra2_qa_sqs_booking_bridge_inbound_dlq` (borrowed) |
| Error queue | `inttra2_qa_sqs_subscription_errors` | `inttra2_qa_sqs_subscription_errors_dlq` (borrowed) |
| Inbound bucket (read only) | `inttra2-qa-inbound-pickup` | the same: the real object `315_IFTSTA/20261119/carriers/CA2000/IFTSTA_BK_Ansi_01` (555 bytes, from partner `CA2000`), only read |
| Workspace | `inttra2-qa-workspace` | the same: the copies land under their own new root ids |
| Events | `inttra2_qa_sns_event` | the same |
| Network Services | QA endpoints (`api-beta.inttra.com`, credentials from SSM) | the same (VPN) |
| Local port | | 18084 |

Local properties (only the queue URLs and the port differ from `dispatcher/conf/qa/dispatcher.properties`):

```properties
componentName=dispatcher
dispatcher.sqsDispatcherConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_dispatcher_pu_dlq                 # changed
dispatcher.sqsSplitterConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_splitter_pu_dlq                    # changed
dispatcher.sqsCESplitterConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_splitter_ce_pu_dlq               # changed
dispatcher.sqsWebBLPDF.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_splitter_pu_dlq                          # changed
dispatcher.sqsErrorSubscriptionConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_subscription_errors_dlq   # changed
dispatcher.snsEventConfig.topicArn=arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event
dispatcher.s3WorkspaceConfig.bucket=inttra2-qa-workspace
dispatcher.s3InboundPickupConfig.bucket=inttra2-qa-inbound-pickup
dispatcher.sqsBKBridge.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_booking_bridge_inbound_dlq               # changed
server.connector.port=18084                                                                                                               # added
```

Plus the QA `network-services.properties` and `datadog.properties`, unchanged. Build, credentials and start: the same steps as [error-processor](error-processor.md#how-it-is-run-locally), with `dispatcher` and port 18084. For the shutdown check the service was started differently, see [How the shutdown check is run](#how-the-shutdown-check-is-run).

**Test inputs.** Hand-made SNS-wrapped S3 notifications, as QA's bucket notification would send them, for the real inbound object above. Each is marked by its SNS `MessageId` (`wi01124532-rt-dsp-v1-routed`, `…-v2-routed`, `…-v1-empty`, `…-v2-empty`, `…-burst-01` … `-20`). The "empty" ones give `size: 0` for the same key; dispatcher decides "empty" from the notification's size, so no empty object had to be written to the real inbound bucket. The new build's routed notification:

```json
{"Type":"Notification","MessageId":"wi01124532-rt-dsp-v2-routed","TopicArn":"arn:aws:sns:us-east-1:642960533737:wi01124532-rt-test-notification","Subject":"wi01124532 runtime test","Message":"{\"Records\":[{\"eventVersion\":\"2.1\",\"eventSource\":\"aws:s3\",\"awsRegion\":\"us-east-1\",\"eventTime\":\"2026-11-19T20:16:00.000Z\",\"eventName\":\"ObjectCreated:Put\",\"s3\":{\"s3SchemaVersion\":\"1.0\",\"configurationId\":\"wi01124532-rt\",\"bucket\":{\"name\":\"inttra2-qa-inbound-pickup\",\"arn\":\"arn:aws:s3:::inttra2-qa-inbound-pickup\"},\"object\":{\"key\":\"315_IFTSTA/20261119/carriers/CA2000/IFTSTA_BK_Ansi_01\",\"size\":555,\"sequencer\":\"0\"}}}]}","Timestamp":"2026-11-19T20:16:00.000Z"}
```

<a id="summary"></a>
## Summary in functional terms

dispatcher is the front door: every file a partner sends goes through it. **On the new build a file is taken in exactly as before.** It is copied into the workspace byte for byte, with the same content type and the same partner metadata (the xlog id, the original file name, the pickup time). It is routed to the same next queue with the same routing message, and recorded in the lineage with the same event. An empty file is refused exactly as before: the same error message, the same error details ("Zero byte file") and the same event. **Stopping the service is safe:** when told to stop while 20 files were arriving, it took no new files, finished the 10 it had started, closed its connections, and stopped within 9 seconds. The other 10 stayed in the queue and were processed by the next start. Each of the 20 was processed exactly once: none lost, none twice. Two differences, neither functional: the storage health check takes about 4.7 s instead of 0.6 s (it retries an expected "not found" 3 times, [F25](../findings.md#f25)), and it logs one extra error line per check (U15, as in error-processor).

<a id="pr-next-steps"></a>
## PR #7 Next Steps: covered?

| PR Next Step | Covered | Where |
|---|---|---|
| Boot dispatcher, drop an EDI file and a zip; compare the routed `MetaData`, the workspace copy, the zip entries and the events with the v1 build | ✅ **EDI file:** routed message, copy and events identical; also the empty-file refusal. **Zip: dropped from the PR's Next Steps (Arijit, 2026-11-19).** QA confirmed partners send only flat zips, which `DispatcherFuncTest` (zip expansion) and the golden tests cover. A local zip test would write its entries into the **real** inbound bucket, where QA's own dispatcher would pick them up | [Test 4a](#test-4a) |
| A file with `xlogid` and `originalfilename` user metadata: both reach the projections and the event tokens; each zip entry dispatched with the zip's `rootworkflowid` | ✅ **Metadata:** the real object carries both; both builds copy them to the workspace copy, the `MetaData` projections (`xlogId`, `originalFileName`) and the event tokens, identically. Zip entries' root id: dropped with the zip (see above), covered by `DispatcherFuncTest` | [Test 4a](#test-4a), steps 6 and 8 |
| Stop the service while files are being processed: the clients close; each message fully processed and deleted, or delivered again | ✅ **Yes** (new build): stopped by Ctrl+C with 10 messages in progress and 10 waiting. Receiving stopped at once, the 10 finished (drain 8 s of the 20 s allowed), the 4 clients closed after that, exit at 8.7 s; the 10 waiting ones processed by the next start. CloudWatch: 20 sent, 20 received, 20 deleted, no redelivery | [Test 4b](#test-4b) |

The shutdown check stands for every migrated service: the drain (`ListenerManager`), the listener and the close order (`CloudServicesModule`) are the same shared code in each. [A27](../actions.md#a27), the INT check of a real ECS task stop, is now optional: Ctrl+C and SIGTERM run the same JVM shutdown hooks, and the exit took 9 s against the 30 s stop timeout.

**PR descriptions updated 2026-11-19:** the Next Steps of PRs #4–#7 now show the QA verification (✅), with only email-sender's actual send left open (⏳, to test on INT through the ECS task).

<a id="test-4a"></a>
## Test 4a: a routed file and an empty file (2026-11-19, approved by Arijit)

Plan: run v1 on its two notifications, then the new build on its own two; compare the copies, the routed and error messages, the annotations and the events. v1 build = `origin/develop`, new build = feature `07b5106f`. Times are local (EST).

| # | Time | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 15:13–15:15 | Built the jars in the build worktree | v1 `origin/develop`; new `07b5106f` | Both built |
| 2 | 15:15 | Read the test object's headers (read), wrote the four notifications (scratchpad) | `inttra2-qa-inbound-pickup/315_IFTSTA/20261119/carriers/CA2000/IFTSTA_BK_Ansi_01` | 555 bytes, user metadata `xlogid`, `originalfilename`, `inftpfilepickuptime` |
| 3 | 15:15 | Pre-checks (read) | the five borrowed queues | All empty |
| 4 | 15:15 | Started the **v1 build** | port 18084 | Started; Network Services token fetched |
| 5 | 15:15 | v1 `/admin/healthcheck` (read) | local | All healthy; 6.1 s in total (the queue check uses the queue's default 5 s wait, [F10](../findings.md#f10)) |
| 6 | 15:16 | **WRITE** `sqs send-message` of `routed-v1.json` | `inttra2_qa_sqs_dispatcher_pu_dlq` | Consumed and deleted. Copy stored at `inttra2-qa-workspace/8d0acc82-…/61fe664b-…`: `text/plain`, 555 bytes, **byte-identical to the inbound object**, user metadata `originalfilename`, `xlogid`, `inftpfilepickuptime`. Routed `MetaData` to `inttra2_qa_sqs_splitter_ce_pu_dlq` with projections `originalFileName`, `inboundS3FileName`, `pickupFileName`, `originalFileSize`, `mftId`, `xlogId`, `fileType` and the times |
| 7 | 15:17 | **WRITE** `sqs send-message` of `empty-v1.json` | `inttra2_qa_sqs_dispatcher_pu_dlq` | "Message is zero byte", non-recoverable: error `MetaData` to `inttra2_qa_sqs_subscription_errors_dlq`, annotations `{"Annotations":[{"type":"error","code":"/exception/dispatcher/business/messagePipeline/emptyFile","value":"Zero byte file"}]}` stored in the workspace. Consumed and deleted |
| 8 | 15:17 | Read the two close events from QA's event store, the messages from the borrowed queues (peek), the copy and the annotations (read) | `inttra2-qa-workspace/eventstore/2026-11-19/…`, borrowed queues | Saved for the comparison. Routed event tokens: `originalFileName`, `inboundS3FileName`, `pickupQueue`, `originalFileSize`, `mftId`, `dropOffQueue`, `inftpfilepickuptime`, `xlogId`, `fileType` |
| 9 | 15:17 | Stopped v1 | local | Port free |
| 10 | 15:18 | Started the **new build** | port 18084 | Started; token fetched |
| 11 | 15:18 | New build `/admin/healthcheck` (read) | local | Same checks, all healthy. The queue check is faster; the **storage-read check took 4.7 s with 4 GETs** of `anykey` (v1: 0.6 s, one GET): cloud-sdk retries the expected 404 three times, "SDK Attempt Count: 4" ([F25](../findings.md#f25)). One ERROR line for the missing key ([F21](../findings.md#f21), U15) |
| 12 | 15:18 | **WRITE** `sqs send-message` of `routed-v2.json` | `inttra2_qa_sqs_dispatcher_pu_dlq` | As step 6: copy at `inttra2-qa-workspace/f86a46d2-…/6d4b28a2-…`, same content type, length and user metadata, byte-identical |
| 13 | 15:19 | **WRITE** `sqs send-message` of `empty-v2.json` | `inttra2_qa_sqs_dispatcher_pu_dlq` | As step 7 |
| 14 | 15:20 | Read the new build's outputs as in step 8, stopped the new build | | Port free |
| 15 | 15:20 (re-checked 15:50) | Compared v1 with the new build (scratchpad) | | **All identical** after normalizing random ids, times and the marker: the copy (byte for byte, also with the source), its headers and user metadata, the routed `MetaData`, the error `MetaData`, the annotations, both close events (same keys in the same order, same tokens) |

**Result of test 4a: passed.**

<a id="test-4b"></a>
## Test 4b: graceful shutdown with messages in progress (2026-11-19, approved by Arijit)

Plan: start the new build, send a burst of 20 routed notifications (two `send-message-batch` calls of 10), press Ctrl+C about 2 s later, then check the log (the drain, "Closing … on application shutdown" once per client, no "Messages still in progress after 20 s"), the exit time, and where each of the 20 messages ended up. What the code does on stop ([ListenerManager](../../../shared/src/main/java/com/inttra/mercury/shared/listener/support/ListenerManager.java)): the listener stops receiving, the messages in progress get up to 20 s, then Dropwizard closes the cloud clients (registered first, so stopped last).

| # | Time | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 15:28 | Started the new build in its own console (first method: PowerShell `Start-Process`, launched from the tool's shell) | PID 19432 | Started |
| 2 | 15:32:45 | **WRITE** `sqs send-message-batch` ×2 of `burst-a.json`, `burst-b.json` | `inttra2_qa_sqs_dispatcher_pu_dlq` | 20 sent |
| 3 | 15:32:51 | Ctrl+C (`send-ctrl-c.ps1 -ProcessId 19432`) | local | **Not delivered**: the script reported success, but java logged nothing about stopping and kept working. Cause: a process started from the tool's shell inherits the "ignore Ctrl+C" flag, and java inherited it. The exit check of that run was also wrong (it reported the process gone while it was still running). **Not a dispatcher finding:** the service simply carried on, as it would with no stop request |
| 4 | 15:33–15:34 | What that run shows anyway | `inttra2_qa_sqs_splitter_ce_pu_dlq`; CloudWatch on the pickup queue | All 20 processed normally (CE queue 2 → 22); CloudWatch 20 received, 20 deleted. Network Services calls take about 5 s each, so a file takes about 11 s |
| 5 | 15:41 | Found PID 19432 still listening on 18084; pickup queue empty (0/0), so stopped it hard (`Stop-Process -Force`) | local | Port free |
| 6 | 15:41 | Launcher fixed: it clears the inherited flag (`SetConsoleCtrlHandler(NULL, FALSE)`) before starting java | `start-java.ps1` | |
| 7 | 15:41–15:45 | **Idle** check: started the new build (PID 21948), Ctrl+C with nothing in progress | local | Exit in **1 s**: Jetty stopped, then "Closing message queue sender client", "… message queue listener client", "… storage download client", "… storage client on application shutdown" (4 clients, after the listener) |
| 8 | 15:45:27 | Started the new build (PID 6956) | port 18084 | Started |
| 9 | 15:45:39 | **WRITE** `sqs send-message-batch` ×2 of `burst-a.json`, `burst-b.json` | `inttra2_qa_sqs_dispatcher_pu_dlq` | 20 sent |
| 10 | 15:45:45.1 | Ctrl+C | PID 6956 | Delivered |
| 11 | 15:45:45.6 | Jetty stopped (connector, admin context) | log | |
| 12 | 15:45:45.8 | "Listener … MessageQueueListener has been shut down." | log | **Receiving stopped** 0.7 s after the Ctrl+C; the second 10 were never received |
| 13 | 15:45:46–51 | The 10 messages already received go on: Network Services calls (4.6 s, 5.7 s), copies, routed sends, events | log | Still processed during the drain |
| 14 | 15:45:53.8 | "Closing message queue sender client / message queue listener client / storage download client / storage client on application shutdown" | log | **The clients close after the drain** (8 s, inside the 20 s limit). No "Messages still in progress" warning, no "Exception in SQS Listener" |
| 15 | 15:45:53.9 | java exited | local | **8.7 s** after the Ctrl+C |
| 16 | 15:46:04 | Queue attributes (read) | pickup; CE; errors | Pickup **10 visible, 0 in flight** (the 10 never received); CE queue 22 → **32** (+10, the drained ones); errors 2 (unchanged) |
| 17 | 15:46:25 | Started the new build again (PID 15328) | port 18084 | Started; only log WARN: logback-access's version notice at startup (both builds) |
| 18 | 15:46:54 | Queue attributes (read) | pickup; CE | Pickup **0/0**; CE queue **42** (+10) |
| 19 | 15:47:12 | Ctrl+C (idle) | PID 15328 | Exit in 1 s, the 4 "Closing …" lines |
| 20 | 15:48 | CloudWatch `NumberOfMessagesSent / Received / Deleted` (read) | `inttra2_qa_sqs_dispatcher_pu_dlq`, 15:44–15:50 | Sent **20**; received **10 + 10**; deleted **10 + 10**. Every message received once and deleted once: **none lost, none redelivered, none processed twice** |

**Result of test 4b: passed.** Stop while busy: receiving stops at once, the work in progress finishes, the clients close only after it, the process exits well inside the container's 30 s, and the untouched messages wait for the next start.

Observation (not a defect): on an idle stop the listener's "has been shut down" line may be missing. The drain returns at once, the clients close and the JVM exits while the listener is still in its long poll (at most 20 s). Nothing is lost: a message received in that last poll is not deleted, so it comes back after the visibility timeout.

<a id="how-the-shutdown-check-is-run"></a>
## How the shutdown check is run

A task stop in ECS sends SIGTERM; locally on Windows the equivalent is Ctrl+C to the java console (it runs the JVM's shutdown hooks). `taskkill /F` or `Stop-Process -Force` does **not**: the JVM dies without its hooks. Two small scripts in the scratchpad (`rt4/`):

```powershell
# start-java.ps1 -Jar dispatcher-v2.jar -Log run-burst
[CtrlFlag]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)        # stop ignoring Ctrl+C, so java inherits that
$p = Start-Process -FilePath java.exe -PassThru -WindowStyle Minimized `
    -ArgumentList '-Xmx384m','-jar',$Jar,'run','dispatcher.yaml','dispatcher.properties','network-services.properties','datadog.properties' `
    -RedirectStandardOutput "$Log.log" -RedirectStandardError "$Log.err"
$p.Id | Out-File -Encoding ascii "$Log.pid"
```

```powershell
# send-ctrl-c.ps1 -ProcessId <java pid>
[ConsoleControl]::FreeConsole()                          # leave this script's own console
[ConsoleControl]::AttachConsole($ProcessId)              # join java's console
[ConsoleControl]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)   # this script itself ignores the Ctrl+C
[ConsoleControl]::GenerateConsoleCtrlEvent(0, 0)         # 0 = CTRL_C_EVENT, to every process on that console
```

The launcher runs in the background (its output redirected to a file), and the AWS credentials are exported into its environment first, as for every local run ([credentials](aws/basics.md#7-credentials)). Exit is measured with `(Get-Process -Id $pid).WaitForExit(90000)`. More on the commands: [local run commands](../commands/local-run.md#8-local-run-and-stop).

<a id="left-in-qa"></a>
## Left in QA

- Workspace (kept, per Arijit): the four copies and the two annotations objects of test 4a, the 40 copies of test 4b, each under its own root id.
- Borrowed queues: **empty.** 16:10–16:12 **WRITE** (agreed) deleted our 42 messages from `inttra2_qa_sqs_splitter_ce_pu_dlq` (2 from 4a, 20 from the first attempt, 20 from 4b) and our 2 from `inttra2_qa_sqs_subscription_errors_dlq` (4a's empty-file errors). `rt4/cleanup.py` received with a 60 s visibility and deleted a message only when its body matched every marker (`"component":"dispatcher"` and the test object's key; for the errors also `"exitStatus":"failure"`); any other message would have been returned at once (none was). `purge-queue` was not used: these are real DLQs, and a purge would also remove a real failure arriving meanwhile. Afterwards all five borrowed queues 0 visible, 0 in flight.
- Events: one close event per processed file in QA's event store (real topic, as agreed).
- Pickup queue: empty.
