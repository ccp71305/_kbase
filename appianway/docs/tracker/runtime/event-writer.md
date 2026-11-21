# Runtime verification: event-writer

← [Runtime index](README.md) · [Plan](../runtime-verification.md) · [Tracker home](../README.md)

event-writer reads lineage events from its queue and stores each one in the workspace bucket under `eventstore/<yyyy-MM-dd>/<rootWorkflowId>/<component>-<type>-<eventId>.json`. Migrated in PR #4.

| | QA (real) | Local test |
|---|---|---|
| Input queue | `inttra2_qa_sqs_event` (QA's ECS service reads it) | `inttra2_qa_sqs_splitter_pu_dlq` (borrowed, empty, nothing reads it) |
| Output | `inttra2-qa-workspace/eventstore/…` | the same bucket, under the test's own root ids `wi01124532-rt-v1` / `-v2` (the QATeam role cannot create a test bucket) |
| Local port | | 18081 |

Local properties (only the marked lines differ from `event-writer/conf/qa/event-writer.properties`):

```properties
componentName=event-writer
event-writer.pickupSqsConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_splitter_pu_dlq   # changed
event-writer.s3Config.bucket=inttra2-qa-workspace
event-writer.s3EventStorePath=eventstore
server.connector.port=18081                                                                                         # added
```

<a id="summary"></a>
## Summary in functional terms

event-writer is the service that records the lineage of every file: each step any service reports is stored as one event in the event store. **On the new build an event is stored exactly as before:** the same place in the event store, the same content byte for byte, the same format, and the message is taken off the queue. It starts, reports healthy and uses the same queue and bucket. One difference, not functional: its queue health check answers faster.

<a id="pr-next-steps"></a>
## PR #4 Next Steps: covered?

| PR Next Step | Covered | Where |
|---|---|---|
| Boot event-writer and check that an event lands under the same key with the same body and content type | ✅ Yes | [Test 1](#test-1): byte-identical body, same key layout, `text/plain`, no user metadata; also identical to what QA's own (v1) event-writer stored |
| Stop the service while messages are being processed: the drain, then the clients closing; every message stored and deleted or delivered again, no event missing | ➖ By the dispatcher check | Agreed 2026-11-19: the shutdown check runs once, on dispatcher (shared drain and close order). event-writer also still lacks the `ManagedCloudResource: INFO` log line that shows the clients closing ([A27](../actions.md#a27)) |

<a id="how-it-is-run-locally"></a>
## How it is run locally

All commands in Git Bash, from the scratchpad folder that holds the jar and the configuration (`S=...scratchpad/<test>`). Explanations of each AWS CLI command: [AWS commands](aws/README.md).

**1. Build both jars** in the build worktree (`C:\Users\arijit.kundu\projects\appianway-build`, so VS Code's background compiler cannot interfere):

```bash
cd ../appianway-build
git fetch -q origin
git checkout -q --detach origin/develop          # the SDK v1 build ("v1")
mvn -B -q -pl shared,event-writer -am package -DskipTests -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
cp event-writer/target/event-writer-*.jar $S/event-writer-v1.jar          # the shaded jar (not original-*.jar)
git checkout -q --detach 07b5106f                # the feature branch with the service migrated ("new")
mvn -B -q -pl shared,event-writer -am package -DskipTests -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
cp event-writer/target/event-writer-*.jar $S/event-writer-v2.jar
```
- `-pl shared,event-writer -am`: build only the service and the modules it needs (`-am` = also make), shared included so a stale `mercury-shared` jar from `~/.m2` is never used.
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
  && exec java -Xmx384m -jar event-writer-v1.jar run event-writer.yaml event-writer.properties network-services.properties datadog.properties > run-v1.log 2>&1
```
- `eval "$(aws configure export-credentials …)"`: temporary QA credentials into this process environment only (never written down).
- `AWS_REGION` / `AWS_DEFAULT_REGION`: the region for SDK 2.x and SDK v1.
- `exec java -Xmx384m`: the same heap limit as the QA task (`JVM_Xmx`); `exec` replaces the shell, so stopping the background task stops Java.
- `-jar … run event-writer.yaml <properties…>`: the same command line as `run.sh` in the container: the `run` command of the shared `ConfigProcessingServerCommand`, the YAML from inside the jar, then the property files in order.
- `> run-v1.log 2>&1`: the console log to a file.

**4. Wait until started, then check health:**

```bash
until grep -qE "Started oejs.Server|Exception in thread" run-v1.log; do sleep 1; done
curl -s -m 60 http://localhost:18081/admin/healthcheck          # read only
```
`/admin/healthcheck` runs the default checks (reads only). **The ops endpoint `/admin/opsHealthcheck` also runs the write checks** (it sends `HEALTHCHECK` to the outbound queue and publishes to the event topic), so it is not called in these tests.

**5. Stop:** stop the background task (on Windows this is a hard stop: no shutdown hooks). Check the port is free: `curl -s -m 3 http://localhost:18081/admin/healthcheck || echo stopped`.

<a id="test-1"></a>
## Test 1 (2026-11-19, approved by Arijit)

Plan: one test event per build, sent to the borrowed empty queue `inttra2_qa_sqs_splitter_pu_dlq`; each local run stores it in the test bucket `inttra2-qa-wi01124532-rt`; compare the two stored objects and the logs. v1 build = `develop`, new build = feature `07b5106f`.

| # | Time | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 13:35 | Listed the event-store dates (read) | `s3://inttra2-qa-workspace/eventstore/` | `2026-11-17/` … `2026-11-19/` |
| 2 | 13:36 | Read one real event stored by QA's event-writer (SDK v1, ECS) as the template (read) | `inttra2-qa-workspace/eventstore/2026-11-19/ffd5be1a-…/dispatcher-closeRun-cfc26f0f-….json` | `Content-Type: text/plain`, 4077 bytes, no user metadata. Saved to the scratchpad |
| 3 | 13:36 | Made two test events from it: `eventId` `wi01124532-rt-v1-cfc26f0f-…` / `wi01124532-rt-v2-…`, workflow ids `wi01124532-rt-v1` / `-v2`; sent as a raw JSON array | scratchpad | 4036 bytes each |
| 4 | 13:37 | Built the jars in the build worktree | v1: `develop` `05a1d8fb`; new: feature `07b5106f` | Both built. Jar size 44 MB (v1) vs 92 MB (new: both SDKs until step 5) |
| 5 | 13:37 | Local config: QA `event-writer.properties` with only the queue (`inttra2_qa_sqs_splitter_pu_dlq`), bucket and port (18081) changed; QA `network-services.properties`, `datadog.properties` | scratchpad | |
| 6 | 13:38 | Pre-checks (read) | bucket `inttra2-qa-wi01124532-rt`; queue `inttra2_qa_sqs_splitter_pu_dlq` | Bucket name free (404); queue 0 visible, 0 in flight |
| 7 | 13:38 | **WRITE** `s3api create-bucket` | `inttra2-qa-wi01124532-rt` | **AccessDenied**: the QATeam role has no `s3:CreateBucket`. Nothing created |
| 8 | 13:39 | Fallback, per decision §8 (outputs may go to the real workspace): bucket set to `inttra2-qa-workspace`. Test objects are isolated by their root ids under `eventstore/2026-11-19/wi01124532-rt-v1/` and `-v2/` | local config | |
| 9 | 13:38 | Started the **v1 build** locally (`java -Xmx384m -jar event-writer-v1.jar run event-writer.yaml …`), temporary credentials in its process environment, `AWS_REGION=us-east-1` | local, port 18081 | Started in 0.4 s; no error |
| 10 | 13:40 | v1 `/admin/healthcheck` | local | `InboundQueue -> …splitter_pu_dlq`, `deadlocks`, `errorsPerSecondAverage`: all healthy. InboundQueue took **5.6 s** |
| 11 | 13:40 | **WRITE** `sqs send-message` failed before sending: the CLI needs a Windows path for `file://` | `inttra2_qa_sqs_splitter_pu_dlq` | Nothing sent |
| 12 | 13:41 | **WRITE** `sqs send-message` of `event-v1.json` | `inttra2_qa_sqs_splitter_pu_dlq` | MessageId `4a4d6337-4de0-4696-acf4-074d452153b5` |
| 13 | 13:41 | Read back the stored object (read) | `inttra2-qa-workspace/eventstore/2026-11-19/wi01124532-rt-v1/dispatcher-closeRun-wi01124532-rt-v1-cfc26f0f-….json` | Stored within 10 s: `text/plain`, 4034 bytes, no user metadata. Queue: 0 visible, 0 in flight (consumed and deleted). Log: only SDK v1's "JAXB is unavailable" WARN |
| 14 | 13:41 | Stopped the v1 process (task stop: a hard stop, no shutdown hooks) | local | Port free |
| 15 | 13:41 | Started the **new build** (`event-writer-v2.jar`, feature `07b5106f`), same configuration and environment | local, port 18081 | Started in 0.4 s; no error |
| 16 | 13:41 | New build `/admin/healthcheck` | local | Same three checks, all healthy. InboundQueue took **0.5 s** |
| 17 | 13:41 | Queue attributes (read) | `inttra2_qa_sqs_splitter_pu_dlq` | `ReceiveMessageWaitTimeSeconds=5`, 0 messages |
| 18 | 13:42 | **WRITE** `sqs send-message` of `event-v2.json` | `inttra2_qa_sqs_splitter_pu_dlq` | MessageId `8298226c-7441-4e51-99a6-5c1445c8de0a` |
| 19 | 13:42 | Read back the stored object (read) | `…/eventstore/2026-11-19/wi01124532-rt-v2/dispatcher-closeRun-wi01124532-rt-v2-cfc26f0f-….json` | Stored within 2 s: `text/plain`, 4034 bytes, no user metadata. Queue drained. Log: no cloud-sdk INFO line, no WARN or ERROR (apart from logback-access's version notice, which v1 prints too) |
| 20 | 13:43 | Compared the objects (scratchpad) | `stored-v1.json`, `stored-v2.json`, the ECS-written original | **v1 local and new local byte-identical** after swapping the `-v1`/`-v2` marker. Against the object QA's ECS event-writer wrote: only the four marked fields differ (`eventId`, `workflowId`, `parentWorkflowId`, `rootWorkflowId`); all other fields equal, same order |
| 21 | 13:43 | Stopped the new build (task stop) | local | Port free |

**Result of test 1: passed.** The migrated event-writer stores an event exactly as the SDK v1 build does: same key layout, same body byte for byte, `text/plain`, no user metadata; the message is consumed and deleted; cloud-sdk logs nothing at INFO; the health checks keep their names and are healthy.

Observations:
- **[F10](../findings.md#f10) confirmed on real SQS:** the inbound queue check takes 5.6 s on v1 (no `WaitTimeSeconds` sent, so the queue's 5 s default applies) and 0.5 s on the new build (cloud-sdk sends 0). Same answer, faster. For the real `inttra2_qa_sqs_event` queue the default may differ; harmless either way.
- **Jar size** 44 MB → 92 MB, while both SDKs are on the classpath (until step 5). Startup time and heap (`-Xmx384m`) were not a problem for one event; a burst is part of the shutdown check.
- **Not covered here:** the graceful shutdown ([A27](../actions.md#a27)). The task stop is a hard stop on Windows, and event-writer's YAML still lacks the `ManagedCloudResource: INFO` line. A graceful stop on Windows has to be worked out for the shutdown checks.
- **Left in QA:** the two test objects under `eventstore/2026-11-19/wi01124532-rt-v1/` and `-v2/` in `inttra2-qa-workspace` (marked; deleting them is a write, waiting for Arijit's decision). Nothing left in the queue.

