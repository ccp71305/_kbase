---
name: 2026-06-12-booking-qa-cvt-prod-analysis
description: Trace booking lifecycle across QA, CVT, and Production environments. Analyze CloudWatch, DynamoDB, Lambda, SQS for pre-release verification.
argument-hint: "none"
agent: agent
model: Claude Opus 4.6 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# Booking QA / CVT / Production — Pre-Release Trace & Verification

## CRITICAL CONSTRAINTS

1. **READ-ONLY** — You CANNOT make any changes to AWS configurations, code, or infrastructure. All AWS interactions must be read/query operations only (describe, get-item, query, filter-log-events, logs insights, list-queues, etc.).
2. **NO FILE DELETION** — You can read git history and filesystem but CANNOT delete any files.
3. **NO CODE CHANGES** — You cannot modify any code in mercury-services.
4. AWS credentials are available in the terminal (profile: `642960533737_INTTRA2-QATeam`). Use `--profile 642960533737_INTTRA2-QATeam` for all AWS CLI commands. Region is `us-east-1`.

---

## Session Context Protocol — FOLLOW THIS STRICTLY

Before starting ANY work:
1. Call `session_list` to check for existing sessions related to `booking-qa-cvt-prod-analysis` or `ION-14382`.
2. If a relevant session exists, call `session_get` to load its context and resume from where you left off.
3. If no session exists, call `session_create` with:
   - name: `booking-qa-cvt-prod-analysis-2026-06-12`
   - project: `mercury-services`
   - tags: `["booking", "ION-14382", "qa", "cvt", "production", "pre-release", "aws-trace"]`

**DURING** work — call `session_add_context` after EVERY significant finding:
- After each environment's DynamoDB query results → category: `finding`
- After each CloudWatch log analysis → category: `finding`
- After each Lambda invocation trace → category: `finding`
- After each SQS trace → category: `finding`
- After cross-environment comparison → category: `decision`
- After git history review → category: `finding`
- After production release impact assessment → category: `decision`
- Log your model info with category: `model_info`

**CONTEXT MANAGEMENT** — If context window fills above 85%:
1. Persist ALL important details in session context with `session_add_context` (category: `progress`, include full summary of everything found so far)
2. Write all findings to the output document immediately
3. Note in session context where you left off and what remains

---

## Goal Overview

Trace the full lifecycle of bookings across three environments (QA, CVT, Production) to verify that the AWS SDK v2 upgrade (ticket ION-14382) has not broken any booking flows. The release to production is scheduled for **tomorrow (2026-06-13)**.

---

## Environment Details

### CVT Environment
| Resource | ARN / Identifier |
|----------|-----------------|
| ECS Cluster | `arn:aws:ecs:us-east-1:642960533737:cluster/ANECVBK-001` |
| Booking Service | `arn:aws:ecs:us-east-1:642960533737:service/ANECVBK-001/Booking-cvt` |
| Booking Task | `arn:aws:ecs:us-east-1:642960533737:task/ANECVBK-001/88186f993adc4ca7be3b78bfbf771ba5` |
| DynamoDB Table | `inttra2_test_booking_BookingDetail` |
| DynamoDB env prefix | `inttra2_test_booking` |
| CloudWatch Log Group | Derive from ECS — likely `inttra2-cv-lg-bkapi` or similar (check with `aws logs describe-log-groups --log-group-name-prefix inttra2-cv`) |
| S3 Workspace | `inttra2-cv-workspace` |
| S3 Archive | `inttra2-cv-s3-bookingdetail-s3archive` |
| SNS Topic | `arn:aws:sns:us-east-1:642960533737:inttra2_cv_sns_event` |
| SQS Inbound | `inttra2_cv_sqs_bk_inbound` |
| SQS Watermill | `inttra2_cv_sqs_watermill_bk` |

### QA Environment
| Resource | ARN / Identifier |
|----------|-----------------|
| ECS Cluster | `arn:aws:ecs:us-east-1:642960533737:cluster/ANEQABK-001` |
| DynamoDB env prefix | `inttra2_qa_booking` |
| DynamoDB Table | `inttra2_qa_booking_BookingDetail` |
| CloudWatch Log Group | Derive — likely `inttra2-qa-lg-bkapi` (verify with `aws logs describe-log-groups --log-group-name-prefix inttra2-qa`) |
| S3 Workspace | `inttra2-qa-workspace` |
| S3 Archive | `inttra2-qa-s3-bookingdetail-s3archive` |
| SNS Topic | `arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event` |
| SQS Inbound | `inttra2_qa_sqs_bk_inbound` |

### Production Environment (PRE-UPGRADE — running old AWS SDK v1 code)
| Resource | ARN / Identifier |
|----------|-----------------|
| ECS Cluster | `arn:aws:ecs:us-east-1:642960533737:cluster/ANEPRBK-001` |
| DynamoDB env prefix | `inttra2_prod_booking` |
| DynamoDB Table | `inttra2_prod_booking_BookingDetail` (NOTE: prod table may not have `booking` in prefix — check `inttra2_pr_*_BookingDetail` pattern — the production resources doc shows no booking-specific DynamoDB table under `_pr_` naming. The table might be shared or use a different naming. Query DynamoDB to discover the exact table name.) |
| CloudWatch Log Group | `inttra2-pr-lg-bkapi` |
| S3 Workspace | `inttra2-pr-workspace` |
| S3 Archive | `inttra2-pr-s3-bookingdetail-s3archive` |
| Lambda - S3 Archive | `inttra2-pr-lambda-bookingdetail-S3ArchiveLambda` |
| Lambda - ES Index | `inttra2-pr-lambda-bookingdetail-ElasticsearchLambda` |
| Lambda - Send | `inttra2-pr-lambda-bookingdetail-SendLambda` |
| Lambda - CargoScreen | `inttra2-pr-lambda-bookingdetail-CargoScreen` |
| Lambda - Partner Integration | `inttra2-pr-lambda-booking-partner-integration` |
| Lambda - Outbound | `inttra2-pr-lambda-booking-outbound` |
| SNS BookingDetail Stream | `inttra2_pr_sns_bookingdetail_TableStreamTopic` |
| SQS Booking S3 | `inttra2-pr-sqs-bookingdetail-s3` |
| SQS Partner Integration | `inttra2-pr-sqs-booking-partner-integration` |
| SQS Watermill BK | `inttra2_pr_sqs_watermill_bk` |
| SQS BK Inbound | `inttra2_pr_sqs_bk_inbound` |

**IMPORTANT**: For QA and CVT, derive Lambda, SQS, SNS names by substituting the environment prefix (`_qa_`, `_cv_`/`_test_`, `-qa-`, `-cv-`) in place of `_pr_`/`-pr-`. Mind the `_` and `-` separators — some resources use underscore (`_cv_`, `_qa_`, `_pr_`) and some use hyphen (`-cv-`, `-qa-`, `-pr-`). Verify each resource exists before querying.

---

## Reference Documents — READ THESE FIRST

Before starting any AWS queries, read these documents from the workspace:

1. `booking/docs/aws-architecture-diagram.md` — Full production architecture with Mermaid diagrams showing ECS clusters, SNS→SQS message flows, Lambda triggers, DynamoDB streams, S3 buckets. This is your map.
2. `booking/docs/aws-resources.md` — Complete inventory of all production AWS resources (DynamoDB tables, S3 buckets, Lambda functions, SQS queues, SNS topics, CloudWatch log groups).
3. `booking/docs/2026-03-27-booking-dev-log-review.md` — Example of a dev environment log trace showing all the log patterns to search for (Published message to topic, Email processing done, Watermill OB sent, etc.).
4. `booking/docs/2026-06-08-booking-conf-field-format-diff.md` — CONFIRM record format differences between PROD (SDK v1) and QA (SDK v2).
5. `booking/docs/2026-06-08-booking-req-field-format-diff.md` — REQUEST record format differences.
6. `booking/docs/2026-08-08-booking-field-format-diff-impact-claude.md` — Impact analysis of field format differences.
7. `booking/docs/2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md` — Design and implementation review of the AWS 2.x upgrade.

Focus ONLY on booking-related AWS components. Do not trace non-booking services.

---

## Bookings to Trace

### QA Environment — Trace these bookings (ALL versions)
| InttraReference | Notes |
|----------------|-------|
| `2010402133` | Trace all versions |
| `2010319001` | Has many versions — trace ALL |
| `2010320014` | Has many versions — trace ALL |
| `2010320016` | Has many versions — trace ALL |

### CVT Environment — Trace these bookings (ALL versions)
| InttraReference | Notes |
|----------------|-------|
| `2001538648` | Trace all versions |
| `2001538650` | Trace all versions |

### Production Environment — Trace these bookings PLUS discover more
| InttraReference | Notes |
|----------------|-------|
| `2109566472` | Trace this specific booking |
| *discover* | Find at least **1 EDI booking** from today (2026-06-12) with both REQUEST and CONFIRM versions |
| *discover* | Find at least **1 WEB booking** from today (2026-06-12) with both REQUEST and CONFIRM versions |
| *discover* | Find at least **1 API booking** from today (2026-06-12) with both REQUEST and CONFIRM versions |

To discover bookings by source type, look for:
- EDI bookings: inbound via SQS listener, `source` or `channel` field = `EDI` in DynamoDB
- WEB bookings: created via `POST /booking/request` from UI, `source`/`channel` = `WEB`
- API bookings: created via `POST /booking/request` from API clients, `source`/`channel` = `API`
You can also search CloudWatch logs for `Created new booking` and filter by channel/source.

---

## Tracing Methodology — For EACH Booking

For each booking, trace these stages in order. Use the DynamoDB table and CloudWatch logs for the respective environment.

### Stage 1: DynamoDB Record
```bash
# Query BookingDetail table for all versions of a booking
aws dynamodb query \
  --table-name <ENV_PREFIX>_BookingDetail \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```
Document: Record count, version types (REQUEST, CONFIRM, AMEND, CANCEL, etc.), timestamps, `bookingId` (UUID), `sequenceNumber`, `workflowId`, data format (boolean types, null handling), `source`/`channel` field.

### Stage 2: CloudWatch Application Logs
Use CloudWatch Logs Insights to trace the booking through the application:

```
# Find all log entries for a specific inttraReferenceNumber
fields @timestamp, @message
| filter @message like /<INTTRA_REF>/
| sort @timestamp asc
| limit 200
```

Key log patterns to search for (from dev log review):
- `Creating booking in state` — booking creation
- `Created new booking` — booking created with workflowId  
- `Published message to topic` — SNS notification
- `Email processing done for workflowId` — outbound email
- `Watermill OB sent for workflowId` — Watermill outbound
- `Watermill metadata sent to sqs` — SQS message
- `EDI/SQS OB sent for workflowId` — EDI outbound
- `transformer Uploaded to bucket` — S3 upload
- `Uploading object to S3` — S3 storage
- `Number of coded parties` — party processing
- `outbound/partnerintegration` — partner integration call

### Stage 2b: Exception & Error Logging — MANDATORY
For EVERY booking traced (QA, CVT, and Production — including discovered production bookings), run an exception/error search in the same time window as the booking's lifecycle:

```
fields @timestamp, @message
| filter @message like /<INTTRA_REF>/
| filter @message like /(?i)exception|error|stacktrace|caused by|failed|failure|timeout|rejected/
| sort @timestamp asc
| limit 500
```

Also run a broader error scan around the booking's timestamp (±5 minutes) to catch errors that may not contain the booking reference but are correlated:
```
fields @timestamp, @message
| filter @message like /(?i)exception|ERROR|FATAL|stacktrace/
| filter @message not like /ping|healthcheck/
| sort @timestamp asc
| limit 500
```

For Lambda log groups, run the same exception search:
```
fields @timestamp, @message
| filter @message like /(?i)exception|error|stacktrace|timeout|task timed out|runtime error/
| sort @timestamp desc
| limit 200
```

**Document ALL exceptions found** — even if they appear benign. For each exception:
- Record the full stack trace or error message
- Note the timestamp and which booking it correlates to
- Note the log group and log stream
- Classify as: `CRITICAL` (breaks booking flow), `WARNING` (may affect data), or `INFO` (benign/expected)
- Log each exception in session context with category: `finding` and include `exception` in the references

### Stage 3: Subscription Processing
Trace how subscriptions were processed for the booking's workflowId:
```
fields @timestamp, @message
| filter @message like /workflowId/ and @message like /<WORKFLOW_ID>/
| filter @message like /subscription/
| sort @timestamp asc
```

### Stage 4: Lambda Invocations
Check Lambda logs for each booking-related Lambda:
- `inttra2-<ENV>-lambda-bookingdetail-S3ArchiveLambda` — S3 archival
- `inttra2-<ENV>-lambda-bookingdetail-ElasticsearchLambda` — ES indexing  
- `inttra2-<ENV>-lambda-bookingdetail-SendLambda` — outbound send
- `inttra2-<ENV>-lambda-booking-partner-integration` — partner integration
- `inttra2-<ENV>-lambda-bookingdetail-CargoScreen` — cargo screening

For each Lambda, check its CloudWatch log group:
```bash
aws logs start-query \
  --log-group-name "/aws/lambda/inttra2-<ENV>-lambda-bookingdetail-S3ArchiveLambda" \
  --start-time <EPOCH_START> \
  --end-time <EPOCH_END> \
  --query-string "fields @timestamp, @message | filter @message like /<INTTRA_REF>/ | sort @timestamp asc | limit 100" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```
Then retrieve results with `aws logs get-query-results --query-id <ID>`.

### Stage 5: DynamoDB Record Detail
For selected bookings, retrieve the full record and document:
- Boolean field types (`N` vs `BOOL`)
- Null handling (`NULL: true` presence vs field omission)
- Party list ordering and completeness
- Location list ordering
- `partyId` field presence
- `splitCopy` field presence
- Date/time field formats
- Numeric precision

### Stage 6: Inbound & Outbound Processing
Document the queue names and S3 locations involved:

**Inbound flow:**
- SQS inbound queue: `<ENV_PREFIX>_sqs_bk_inbound`
- SQS booking bridge: `<ENV_PREFIX>_sqs_booking_bridge_inbound`
- Transformer SQS: `<ENV_PREFIX>_sqs_transformer_inbound`
- SNS event topic: `<ENV_PREFIX>_sns_event`

**Outbound flow:**
- SQS watermill: `<ENV_PREFIX>_sqs_watermill_bk`
- SQS file delivery: `<ENV_PREFIX>_sqs_file_delivery`
- SQS rest delivery: `<ENV_PREFIX>_sqs_rest_delivery`
- SQS partner integration: `inttra2-<ENV>-sqs-booking-partner-integration`
- S3 workspace: `inttra2-<ENV>-workspace`
- S3 archive: `inttra2-<ENV>-s3-bookingdetail-s3archive`

Verify each queue exists and check approximate message counts:
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/642960533737/<QUEUE_NAME> \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

---

## Stage 7: Production Release Impact Assessment — CRITICAL

This is the most important part. The production release is tomorrow.

### 7a. Git History Review
Review the booking module git history to understand ALL changes since the AWS SDK v2 upgrade began:

```bash
git log --oneline --since="2026-01-01" -- booking/
```

Focus on:
- Data format changes (boolean serialization, null handling, date formats)
- DynamoDB Enhanced Client migration changes
- S3 client changes
- SQS/SNS client changes
- Lambda handler changes
- Serialization/deserialization changes
- Jackson configuration changes

Also check these specific documents for known issues:
- `booking/docs/2026-06-08-booking-conf-field-format-diff.md`
- `booking/docs/2026-06-08-booking-req-field-format-diff.md`
- `booking/docs/2026-08-08-booking-field-format-diff-impact-claude.md`

### 7b. Production Data Cross-Check
Compare the production DynamoDB record format (current, pre-upgrade) with the QA/CVT records (post-upgrade):

1. **Boolean fields**: PROD uses `{"N": "0"}` / `{"N": "1"}` — will the upgrade change these to `{"BOOL": false}` / `{"BOOL": true}`? Can downstream consumers (Lambdas, Glue, Snowflake) handle both?
2. **Null fields**: PROD omits null fields — will the upgrade start writing `{"NULL": true}`? Does this affect DynamoDB storage, query costs, or downstream consumers?
3. **Party ordering**: Will `transactionPartyList` ordering change? Does any consumer depend on party position?
4. **Location ordering**: Will `transactionLocationInfoList` ordering change?
5. **`partyId` field**: Is it present in PROD? Will it be missing after upgrade?
6. **Date/time formats**: Any precision changes (epoch millis vs seconds, ISO format changes)?
7. **Lambda compatibility**: Do the booking Lambdas (S3ArchiveLambda, ElasticsearchLambda, SendLambda, CargoScreen, partner-integration) read from DynamoDB streams? Will they handle the new field formats?
8. **Elasticsearch indexing**: Will the ElasticsearchLambda correctly index records with new boolean/null formats?

### 7c. Verify Fixes Applied
Check if the known issues from the format diff documents have been fixed in the current code. Look at recent commits that address:
- Boolean type handling (`N` → `BOOL`)
- Null value serialization
- Party list ordering stability
- `partyId` field preservation
- `splitCopy` field preservation

---

## Output Document

Write ALL findings to: `booking/docs/2026-06-12-booking-cvt-qa-prod-analysis.md`

Structure the document as follows:

```markdown
# Booking Pre-Release Analysis — QA / CVT / Production
**Date:** 2026-06-12
**Ticket:** ION-14382
**Release Date:** 2026-06-13
**Analyst:** Claude Opus Agent

## Executive Summary
[High-level findings: is it safe to release? Any blockers? Key risks?]

## 1. Environment Overview
[Table showing each environment's key resources and current status]

## 2. QA Environment Traces
### 2.1 Booking 2010402133
[DynamoDB records, CloudWatch traces, Lambda invocations, subscription processing]
### 2.2 Booking 2010319001 (multi-version)
[All versions traced]
### 2.3 Booking 2010320014 (multi-version)
[All versions traced]
### 2.4 Booking 2010320016 (multi-version)
[All versions traced]

## 3. CVT Environment Traces
### 3.1 Booking 2001538648
[Full trace]
### 3.2 Booking 2001538650
[Full trace]

## 4. Production Environment Traces
### 4.1 Booking 2109566472
[Full trace]
### 4.2 EDI Booking (discovered)
[Full trace with inttraRef, source confirmation]
### 4.3 WEB Booking (discovered)
[Full trace]
### 4.4 API Booking (discovered)
[Full trace]

## 5. Inbound & Outbound Pipeline
### 5.1 Queue Names by Environment
[Table: QA queues, CVT queues, PROD queues]
### 5.2 S3 Locations by Environment
[Table: workspace buckets, archive buckets, etc.]
### 5.3 Lambda Functions by Environment
[Table showing all booking Lambdas per environment]

## 6. Data Format Comparison (PROD vs QA/CVT)
### 6.1 Boolean Field Types
### 6.2 Null Value Handling
### 6.3 Party List Ordering
### 6.4 Location List Ordering
### 6.5 Missing/Added Fields
### 6.6 Date/Time Format Differences

## 7. Exception & Error Log Summary
### 7.1 QA Exceptions
[Table: Timestamp | Booking | Log Group | Exception/Error | Severity Classification | Notes]
### 7.2 CVT Exceptions
[Table: Timestamp | Booking | Log Group | Exception/Error | Severity Classification | Notes]
### 7.3 Production Exceptions
[Table: Timestamp | Booking | Log Group | Exception/Error | Severity Classification | Notes]
### 7.4 Lambda Exceptions (all environments)
[Table: Lambda Name | Environment | Timestamp | Exception/Error | Severity Classification | Notes]
### 7.5 Exception Analysis Summary
[Are any exceptions blocking? Patterns across environments? New exceptions in QA/CVT vs PROD?]

## 8. Production Release Impact Assessment
### 8.1 Git History Summary (AWS upgrade changes)
### 8.2 Known Issues Status (Fixed / Unfixed)
### 8.3 Downstream Consumer Compatibility
### 8.4 Risk Matrix
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|

## 9. AWS CloudWatch Logs Insights — Reusable Queries

[TABLE FORMAT — see below]

## 10. Conclusions & Recommendations
[Go/No-Go recommendation with evidence]
```

### Section 8: CloudWatch Logs Insights Query Reference Table

This section MUST contain a table with optimized, reusable CloudWatch Logs Insights queries:

| # | Query Name | Description | How to Modify for Reuse | Query |
|---|-----------|-------------|------------------------|-------|
| 1 | Trace booking by InttraRef | Finds all log entries for a specific booking number across all stages | Replace `<INTTRA_REF>` with the booking number | `fields @timestamp, @message \| filter @message like /<INTTRA_REF>/ \| sort @timestamp asc \| limit 200` |
| 2 | Trace by workflowId | Follows a booking's workflow through outbound processing | Replace `<WORKFLOW_ID>` with the UUID | `fields @timestamp, @message \| filter @message like /<WORKFLOW_ID>/ \| sort @timestamp asc \| limit 200` |
| 3 | New bookings created | Lists all newly created bookings in a time range | Adjust time range in query settings | `fields @timestamp, @message \| filter @message like /Created new booking/ \| sort @timestamp desc \| limit 50` |
| 4 | Booking creation by state | Shows bookings created in a specific state (REQUEST, CONFIRM, etc.) | Replace `<STATE>` | `fields @timestamp, @message \| filter @message like /Creating booking in state/ and @message like /<STATE>/ \| sort @timestamp desc` |
| 5 | SNS publish events | Tracks all SNS publish events for event distribution | Use as-is for monitoring | `fields @timestamp, @message \| filter @message like /Published message to topic/ \| sort @timestamp desc \| limit 100` |
| 6 | Outbound subscription processing | Traces email and EDI subscription processing | Filter by workflowId if needed | `fields @timestamp, @message \| filter @message like /Email processing done\|EDI.SQS OB sent\|Watermill OB sent/ \| sort @timestamp desc \| limit 100` |
| 7 | S3 uploads | Tracks all S3 object uploads (transformer, watermill payloads) | Filter by bucket name if needed | `fields @timestamp, @message \| filter @message like /Uploading object to S3\|transformer Uploaded to bucket/ \| sort @timestamp desc \| limit 100` |
| 8 | Partner integration calls | Traces partner integration callbacks | Filter by bookingId | `fields @timestamp, @message \| filter @message like /partnerintegration/ \| sort @timestamp desc \| limit 100` |
| 9 | Error detection | Finds ERROR-level logs excluding health checks | Add time range filter | `fields @timestamp, @message \| filter @message like /ERROR/ and @message not like /ping/ \| sort @timestamp desc \| limit 200` |
| 10 | SQS listener activity | Monitors SQS listener startup and message processing | Use as-is | `fields @timestamp, @message \| filter @message like /SQSListener/ \| sort @timestamp desc \| limit 50` |
| 11 | DynamoDB repository creation | Verifies table bindings on startup | Use on startup traces | `fields @timestamp, @message \| filter @message like /Creating.*repository for table/ \| sort @timestamp asc` |
| 12 | Cloud SDK factory initialization | Confirms cloud-sdk-aws factories are used (post-upgrade) | Use on startup | `fields @timestamp, @message \| filter @message like /using cloud-sdk-aws factory\|cloud-sdk/ \| sort @timestamp asc \| limit 50` |
| 13 | HTTP request log (non-ping) | Shows all API requests excluding health checks | Filter by URI path | `fields @timestamp, @message \| filter @message like /MercuryRequestLoggingFilter/ and @message not like /ping/ \| sort @timestamp desc \| limit 100` |
| 14 | Booking lifecycle events | Application startup and lifecycle markers | Use for deployment verification | `fields @timestamp, @message \| filter @message like /Booking life cycle started\|Starting InttraServer/ \| sort @timestamp desc \| limit 10` |
| 15 | Lambda S3Archive trace | Traces S3ArchiveLambda processing for a booking | Replace `<INTTRA_REF>`, use Lambda log group | `fields @timestamp, @message \| filter @message like /<INTTRA_REF>/ \| sort @timestamp asc \| limit 50` |
| 16 | Lambda errors | Finds errors in any booking Lambda | Use on Lambda log groups | `fields @timestamp, @message \| filter @message like /ERROR\|Exception\|FATAL/ \| sort @timestamp desc \| limit 100` |
| 17 | Bookings by source/channel | Finds bookings by their entry channel (EDI, WEB, API) | Replace `<CHANNEL>` | `fields @timestamp, @message \| filter @message like /Created new booking/ and @message like /<CHANNEL>/ \| sort @timestamp desc \| limit 50` |
| 18 | Exceptions for specific booking | Finds all exceptions/errors related to a booking | Replace `<INTTRA_REF>` | `fields @timestamp, @message \| filter @message like /<INTTRA_REF>/ \| filter @message like /(?i)exception\|error\|stacktrace\|caused by\|failed\|failure/ \| sort @timestamp asc \| limit 500` |
| 19 | Broad exception scan (time window) | Finds all exceptions in a time window regardless of booking | Set time range to ±5min of booking activity | `fields @timestamp, @message \| filter @message like /(?i)exception\|ERROR\|FATAL\|stacktrace/ \| filter @message not like /ping\|healthcheck/ \| sort @timestamp asc \| limit 500` |
| 20 | Lambda timeout/runtime errors | Finds Lambda-specific runtime failures | Use on Lambda log groups | `fields @timestamp, @message \| filter @message like /(?i)task timed out\|runtime error\|out of memory\|RequestId.*Error/ \| sort @timestamp desc \| limit 100` |
| 21 | DynamoDB errors | Finds DynamoDB-related errors (throttling, conditional check failures) | Use on app or Lambda log groups | `fields @timestamp, @message \| filter @message like /(?i)dynamodb\|ConditionalCheckFailed\|ProvisionedThroughputExceeded\|throttl/ \| filter @message like /(?i)error\|exception\|failed/ \| sort @timestamp desc \| limit 100` |
| 22 | SQS errors | Finds SQS-related errors | Use on app log groups | `fields @timestamp, @message \| filter @message like /(?i)sqs/ \| filter @message like /(?i)error\|exception\|failed\|rejected/ \| sort @timestamp desc \| limit 100` |

Expand this table with any additional useful queries you discover during your analysis.

---

## Execution Plan

Execute in this order:

### Phase 1: Discovery & Setup (do first)
1. Read all reference documents listed above
2. Create/resume MCP session
3. Discover exact resource names for QA and CVT environments (log groups, Lambda names, SQS queue URLs, DynamoDB table names) by running AWS CLI describe/list commands
4. Log all discovered resources in session context

### Phase 2: QA Environment Trace
5. Query DynamoDB for all 4 QA bookings (all versions)
6. Run CloudWatch Logs Insights queries for each booking
7. Check Lambda logs for each booking
8. Document inbound/outbound pipeline for QA
9. Log findings in session context

### Phase 3: CVT Environment Trace
10. Query DynamoDB for both CVT bookings (all versions)
11. Run CloudWatch Logs Insights queries
12. Check Lambda logs
13. Document pipeline
14. Log findings

### Phase 4: Production Environment Trace
15. Query DynamoDB for booking 2109566472
16. Discover 1 EDI + 1 WEB + 1 API booking from today with both REQUEST and CONFIRM
17. Trace all production bookings through logs
18. Document pipeline and Lambda invocations
19. Log findings

### Phase 5: Cross-Environment Comparison & Release Assessment
20. Compare DynamoDB record formats across environments (focus on boolean types, nulls, party ordering, field presence)
21. Review git history for booking module changes since upgrade
22. Cross-reference known format issues with current code state
23. Assess downstream consumer compatibility
24. Build risk matrix

### Phase 6: Documentation
25. Write the full analysis document to `booking/docs/2026-06-12-booking-cvt-qa-prod-analysis.md`
26. Include the CloudWatch query reference table
27. Provide Go/No-Go recommendation
28. Final session context update

---

## AWS CLI Tips

### CloudWatch Logs Insights (async — start then get results)
```bash
# Start query
QUERY_ID=$(aws logs start-query \
  --log-group-name "<LOG_GROUP>" \
  --start-time $(date -d "2026-06-12 00:00:00" +%s) \
  --end-time $(date -d "2026-06-12 23:59:59" +%s) \
  --query-string "fields @timestamp, @message | filter @message like /<PATTERN>/ | sort @timestamp asc | limit 200" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output text --query 'queryId')

# Get results (wait a few seconds)
aws logs get-query-results --query-id "$QUERY_ID" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

### DynamoDB Query
```bash
aws dynamodb query \
  --table-name inttra2_qa_booking_BookingDetail \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "2010402133"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```

### Discover Log Groups
```bash
aws logs describe-log-groups --log-group-name-prefix "inttra2-qa" --profile 642960533737_INTTRA2-QATeam --region us-east-1
aws logs describe-log-groups --log-group-name-prefix "inttra2-cv" --profile 642960533737_INTTRA2-QATeam --region us-east-1
```

### Discover SQS Queues
```bash
aws sqs list-queues --queue-name-prefix "inttra2_qa_sqs_bk" --profile 642960533737_INTTRA2-QATeam --region us-east-1
aws sqs list-queues --queue-name-prefix "inttra2_cv_sqs_bk" --profile 642960533737_INTTRA2-QATeam --region us-east-1
```

### Discover Lambda Functions
```bash
aws lambda list-functions --profile 642960533737_INTTRA2-QATeam --region us-east-1 --query "Functions[?contains(FunctionName, 'qa') && contains(FunctionName, 'booking')].[FunctionName]" --output text
aws lambda list-functions --profile 642960533737_INTTRA2-QATeam --region us-east-1 --query "Functions[?contains(FunctionName, 'cv') && contains(FunctionName, 'booking')].[FunctionName]" --output text
```

### DynamoDB — List Tables
```bash
aws dynamodb list-tables --profile 642960533737_INTTRA2-QATeam --region us-east-1 --query "TableNames[?contains(@, 'booking') || contains(@, 'Booking')]" --output text
```

### DynamoDB — Get full item with all attributes
```bash
aws dynamodb query \
  --table-name <TABLE> \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<REF>"}}' \
  --projection-expression "inttraReferenceNumber, sequenceNumber, bookingId, workflowId, #st, #src, createdDate, lastModifiedDate" \
  --expression-attribute-names '{"#st": "state", "#src": "source"}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

---

## Environment Prefix Mapping

| Environment | DynamoDB prefix | S3 prefix | SQS underscore prefix | SQS/Lambda hyphen prefix | CloudWatch prefix |
|------------|----------------|-----------|----------------------|--------------------------|-------------------|
| Production | `inttra2_prod_` | `inttra2-pr-` | `inttra2_pr_` | `inttra2-pr-` | `inttra2-pr-` |
| QA | `inttra2_qa_` | `inttra2-qa-` | `inttra2_qa_` | `inttra2-qa-` | `inttra2-qa-` |
| CVT | `inttra2_test_` | `inttra2-cv-` | `inttra2_cv_` | `inttra2-cv-` | `inttra2-cv-` |

**NOTE**: CVT uses `_test_` for DynamoDB table prefix but `_cv_`/`-cv-` for other resources. Verify carefully.
