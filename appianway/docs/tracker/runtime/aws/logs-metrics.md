# CloudWatch Logs and metrics commands

← [AWS commands index](README.md) · [Runtime index](../README.md)

Commands shown as run, in Git Bash on Windows, with AWS CLI v2. **R** = read only, **W** = changes something in AWS (each W agreed with Arijit before it ran). `P=642960533737_INTTRA2-QATeam`, options and helpers: [basics.md](basics.md).

<a id="6-cloudwatch"></a>
## CloudWatch Logs and metrics (all R)

```bash
aws logs describe-log-streams --profile $P --region us-east-1 --log-group-name inttra2-qa-lg-app-way \
    --log-stream-name-prefix AppianWay-event-writer-latest-qa/ \
    --query 'logStreams[?contains(logStreamName,`dff5528c913e4cd996908721cf55fd81`)].{name:logStreamName,first:firstEventTimestamp,last:lastEventTimestamp}'
```
Lists the log streams (one per ECS task container) of a group. `--order-by LastEventTime` cannot be combined with a name prefix (the CLI refuses it), so the stream is picked by task id in `--query`. Timestamps are milliseconds since 1970.

```bash
now=$(($(date +%s)*1000))
aws logs filter-log-events --profile $P --region us-east-1 --log-group-name inttra2-qa-lg-app-way \
    --log-stream-name-prefix AppianWay-event-writer-latest-qa --start-time $((now-3600000)) \
    --query 'events[].[timestamp,message]' --output text
```
Returns the log lines of the matching streams from `--start-time` (ms) on; `--filter-pattern` could narrow them further. `$(date +%s)` is the current Unix time in seconds.

```bash
aws cloudwatch get-metric-statistics --profile $P --region us-east-1 --namespace AWS/SQS \
    --metric-name NumberOfMessagesDeleted --dimensions Name=QueueName,Value=inttra2_qa_sqs_event \
    --start-time $(date -u -d '-75 minutes' +%Y-%m-%dT%H:%M:%SZ) --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
    --period 300 --statistics Sum Maximum --query 'sort_by(Datapoints,&Timestamp)[].[Timestamp,Sum,Maximum]' --output text
```
SQS publishes per-queue metrics to CloudWatch. `--namespace AWS/SQS` and `--dimensions Name=QueueName,Value=<queue>` pick the queue; `--period 300` gives 5-minute buckets; `--statistics Sum Maximum` how to combine the data points in a bucket. Metrics used: `NumberOfMessagesSent`, `NumberOfMessagesReceived`, `NumberOfMessagesDeleted`, `ApproximateAgeOfOldestMessage` (seconds). This is how we saw QA's event-writer stop consuming at about 13:44 EST on 2026-11-19 ([error-processor page](../error-processor.md#observations)).

<a id="9-tracing-a-file"></a>
## Tracing a real file through QA by its log lines (R)

```bash
aws logs filter-log-events --profile $P --region us-east-1 --log-group-name inttra2-qa-lg-app-way \
    --log-stream-name-prefix AppianWay-splitter --start-time $S0 --end-time $E0 \
    --filter-pattern '"String content of file"' --query 'events[].message' --output text      # R
```
Finds which workspace object splitter read for a file uploaded at a known time: splitter logs `String content of file <root>/<id> is …` at INFO (known defect KD-9, useful here). `--filter-pattern '"…"'` matches the quoted phrase; `--start-time`/`--end-time` are milliseconds, from the inbound object's `LastModified`. The `<root>` is the file's root workflow id; its lineage is then `eventstore/<date>/<root>/` in the workspace bucket (one JSON per event; each event's `messages.pickUpMessage` is the input that service received).

<a id="map-names"></a>
## Reading which maps QA's transformer used (test 6)

`ms` turns a UTC time into milliseconds ([basics.md](basics.md#ms)).

```bash
aws logs filter-log-events --profile $P --region us-east-1 --log-group-name inttra2-qa-lg-app-way \
    --log-stream-name-prefix AppianWay-transformer --start-time $(ms "2026-11-19 17:50:00") --end-time $(ms "2026-11-20 06:00:00") \
    --filter-pattern '"Transformer name"' --query 'events[].[message]' --output text \
  | grep -E "1c224a22|bc95ae83|1519b31d" \
  | sed -E 's/^INFO  \[([^]]+)\].*Transformer name : ([A-Z0-9_]+) , IPF: ([0-9]+) .*StructuralMapName : ([A-Za-z0-9_]+) +for workflowId ([0-9a-f-]+).*/\1 map=\2 ipf=\3 struct=\4 wf=\5/'   # R
```
Reads which Contivo maps QA's own transformer used for the traced files. transformer logs, per inbound document, `Transformer name : <map> , IPF: <id> , FormatConfigs : {…} … StructuralMapName : <map>_STRUCT for workflowId <id>` (`InboundTransformation`). The map name comes from the integration profile format in Network Services (`ipf.getTransformer()`), **not** from the `formatCode` projection, so it can only be learnt from the log or Network Services.
- `--log-stream-name-prefix AppianWay-transformer` covers every transformer task's stream (one per container); `--filter-pattern '"Transformer name"'` (double quotes inside single quotes) matches the exact phrase, server-side.
- `--query 'events[].[message]'` wraps each message in its own list, so `--output text` prints **one event per line**. With `events[].message` (no inner brackets) the text output puts all messages on one tab-separated line.
- `grep -E "a|b|c"`: keep only lines with one of the workflow ids (`-E` = extended regular expressions, so `|` means "or").
- `sed -E 's/<regex>/<replacement>/'`: rewrites each line; `( … )` capture groups are inserted as `\1`…`\5`. `[^]]+` = one or more characters other than `]`; `.*` = anything; ` +` = one or more spaces. Result: `2026-11-19 17:55:37,536 map=IFTMBF_D99B_IN_V1 ipf=131 struct=IFTMBF_D99B_IN_V1_STRUCT wf=1c224a22-…`.
- The log time is GMT (the yaml's `%date{ISO8601,GMT}`), and the `timestamp` in a `MetaData` is also UTC. The confirmation file ran on **2026-11-19 00:08 UTC** (not 2026-11-20): a window on the wrong day returns nothing, without an error. For the confirmations the same call with `--filter-pattern '"IFTMBC_D99B_IN_V1"'` showed IPF 26 (our file's) and others all resolving to `IFTMBC_D99B_IN_V1` / `…_STRUCT`.
