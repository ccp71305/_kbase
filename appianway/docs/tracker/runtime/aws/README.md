# AWS CLI commands: index

← [Runtime index](../README.md) · [Plan](../../runtime-verification.md) · [Tracker home](../../README.md)

Every AWS CLI command used to look at QA and to run the runtime tests, one page per AWS service, each with its syntax explained. Commands are shown as run, in Git Bash on Windows, with AWS CLI v2. **R** = read only, **W** = changes something in AWS (each W was agreed with Arijit before it ran).

Resource names are always QA's (`inttra2_qa_*`, `inttra2-qa-*`) or borrowed test queues. CVT is never touched; PROD only with Arijit's OK per query. No ECS change, no deploy.

| Page | What is in it |
|---|---|
| [basics.md](basics.md) | Options in every command (`--profile`, `--query`, `--output`), shell helpers, who am I and the SSO login, times in milliseconds, credentials for the local service |
| [sqs.md](sqs.md) | Listing queues, counts and settings, sending (single and batch), peeking, deleting only our messages, visibility |
| [s3.md](s3.md) | Listing, headers, download, upload, copying a real object to a marked root, reading production, searching every bucket |
| [logs-metrics.md](logs-metrics.md) | Log streams, filtering log lines, SQS metrics, tracing a real file, reading which maps transformer used |
| [dynamodb.md](dynamodb.md) | The control-number sequence table: describe, scan, get-item |
| [ecs-iam.md](ecs-iam.md) | Clusters, services, tasks, task definitions; simulating a task role's permissions |
| [elasticsearch.md](elasticsearch.md) | Signed reads from an Elasticsearch domain (the EsRead tool on ingestor's jar): health, indices, count, search |
| [ssm-ses.md](ssm-ses.md) | Checking parameters without printing them; SES account and sender identity |

Not AWS, but used in every test: starting and stopping the service locally, in [commands/local-run.md](../../commands/local-run.md).

<a id="by-test"></a>
## Commands by test

| Test | AWS commands used |
|---|---|
| [1 event-writer](../event-writer.md#test-1), [2 error-processor](../error-processor.md#test-2), [3 email-sender](../email-sender.md#test-3) | [Queue counts, send, peek, delete](sqs.md#4-sqs-queues-and-messages); [object headers, download, upload](s3.md#5-s3); [logs and SQS metrics](logs-metrics.md#6-cloudwatch); [parameters, SES](ssm-ses.md) |
| [4 dispatcher](../dispatcher.md#test-4a) | The same, plus [send-message-batch](sqs.md#4-sqs-queues-and-messages) for the burst, [credentials](basics.md#7-credentials) and the [Ctrl+C scripts](../../commands/local-run.md#8-local-run-and-stop) |
| [5 splitter](../splitter.md#test-5) | [Tracing a real file by its log lines](logs-metrics.md#9-tracing-a-file); [copying it to a marked root, reading production](s3.md#copy-object) |
| [6 transformer](../transformer.md#test-6) | [SSO login check](basics.md#2-identity); [which maps QA used](logs-metrics.md#map-names); [searching the buckets for the maps](s3.md#list-buckets); [pre-check of the seven borrowed queues](sqs.md#dlq-precheck); [the sequence table](dynamodb.md#sequence-table); [collect and clean up](sqs.md#collect); [the task role's permissions](ecs-iam.md#11-iam-simulate) |
| [7 ingestor](../ingestor.md#test-7) | [Queue counts and send](sqs.md#4-sqs-queues-and-messages); [upload the annotations objects](s3.md#5-s3); [Elasticsearch reads](elasticsearch.md); [credentials](basics.md#7-credentials) |
| [8 distributor](../distributor.md#test-8) | [Queue counts and send](sqs.md#4-sqs-queues-and-messages); [copy to marked roots](s3.md#copy-object), [headers and download](s3.md#5-s3); the S3 null-metadata experiment ([distributor.md](../distributor.md#experiment)) |
| [10 watermill-publisher](../watermill-publisher.md#test-10) | [Queue counts and send](sqs.md#4-sqs-queues-and-messages) (borrowed queue); [object headers](s3.md#5-s3) (read in place, no copy); [parameters, names only](ssm-ses.md); [tracing a file by its log lines](logs-metrics.md#9-tracing-a-file) across `inttra2-qa-lg-app-way` and `inttra2-qa-lg-pi` (finding the inputs); [credentials](basics.md#7-credentials) |
