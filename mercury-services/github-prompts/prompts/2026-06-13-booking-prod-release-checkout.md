---
name: 2026-06-13-booking-prod-release-checkout
description: Post-release production checkout for booking module AWS SDK v2 upgrade. Verify ECS deployment, booking volume, Lambda health, API traffic, outbound processing, and DynamoDB record integrity.
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

# Booking Production Release Checkout — Post-Deployment Verification

## CRITICAL CONSTRAINTS

1. **READ-ONLY** — You CANNOT make any changes to AWS configurations, code, or infrastructure. All AWS interactions must be read/query operations only (describe, get-item, query, filter-log-events, logs insights, list-queues, etc.).
2. **NO FILE DELETION** — You can read git history and filesystem but CANNOT delete any files.
3. **NO CODE CHANGES** — You cannot modify any code in mercury-services.
4. AWS credentials are available in the terminal (profile: `642960533737_INTTRA2-QATeam`). Use `--profile 642960533737_INTTRA2-QATeam` for all AWS CLI commands. Region is `us-east-1`.
5. **NEVER SCAN DYNAMODB TABLES** — The production BookingDetail table has over **147 million records**. A scan will cause contention, consume massive RCU, and potentially impact production traffic. **ALWAYS use Query operations with key conditions on partition keys or GSIs.** Use CloudWatch Logs Insights for aggregate analytics (counts, grouping by state, etc.) instead of DynamoDB scans.
6. **MINIMIZE AWS RESOURCE CONTENTION** — Use optimal query patterns:
   - DynamoDB: Query via partition key or GSI only. Never scan. Use `--max-items` and `--select SPECIFIC_ATTRIBUTES` with projection expressions to minimize RCU.
   - CloudWatch Logs Insights: Prefer `stats` aggregations over retrieving raw logs. Use tight time windows.
   - SQS: Use `get-queue-attributes` only (read-only, no receives).
   - ECS: Use `describe-*` operations only.

---

## Session Context Protocol — FOLLOW THIS STRICTLY

Before starting ANY work:
1. Call `session_list` to check for existing sessions related to `booking-prod-release-checkout` or `ION-14382`.
2. If a relevant session exists, call `session_get` to load its context and resume from where you left off.
3. If no session exists, call `session_create` with:
   - name: `booking-prod-release-checkout-2026-06-13`
   - project: `mercury-services`
   - tags: `["booking", "ION-14382", "production", "post-release", "checkout", "aws-sdk-v2"]`

**DURING** work — call `session_add_context` after EVERY significant finding:
- After ECS task verification → category: `finding`
- After booking volume analysis → category: `finding`
- After Lambda log analysis → category: `finding`
- After API traffic analysis → category: `finding`
- After exception classification → category: `finding`
- After outbound processing check → category: `finding`
- After DynamoDB record verification → category: `finding`
- After multi-version booking analysis → category: `finding`
- Log your model info with category: `model_info`

**CONTEXT MANAGEMENT** — If context window fills above 85%:
1. Persist ALL important details in session context with `session_add_context` (category: `progress`, include full summary of everything found so far)
2. Write all findings to the output documents immediately
3. Note in session context where you left off and what remains

---

## Goal Overview

The booking module with AWS SDK v2 upgrade (ticket ION-14382) was released to Production on **2026-06-13**. This prompt drives a comprehensive post-release checkout to verify the deployment is healthy, bookings are flowing correctly, all downstream systems (Lambdas, SQS, S3, Elasticsearch) are working, and no regressions have been introduced.

---

## Environment Details

### Production Environment (POST-UPGRADE — now running AWS SDK v2 code)
| Resource | ARN / Identifier |
|----------|-----------------|
| ECS Cluster | `arn:aws:ecs:us-east-1:642960533737:cluster/ANEPRBK-001` |
| Booking Service | `arn:aws:ecs:us-east-1:642960533737:service/ANEPRBK-001/Booking-prod` (verify exact name) |
| DynamoDB Table | `inttra2_prod_booking_BookingDetail` |
| DynamoDB env prefix | `inttra2_prod_booking` |
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
| SNS Event Topic | `inttra2_pr_sns_event` |
| SQS Booking S3 | `inttra2-pr-sqs-bookingdetail-s3` |
| SQS Partner Integration | `inttra2-pr-sqs-booking-partner-integration` |
| SQS Watermill BK | `inttra2_pr_sqs_watermill_bk` |
| SQS BK Inbound | `inttra2_pr_sqs_bk_inbound` |
| SQS File Delivery | `inttra2_pr_sqs_file_delivery` |
| SQS REST Delivery | `inttra2_pr_sqs_rest_delivery` |

---

## Reference Documents — READ THESE FIRST

Before starting any AWS queries, read these documents from the workspace:

1. `booking/docs/aws-architecture-diagram.md` — Full production architecture with Mermaid diagrams showing ECS clusters, SNS→SQS message flows, Lambda triggers, DynamoDB streams, S3 buckets. This is your map.
2. `booking/docs/aws-resources.md` — Complete inventory of all production AWS resources.
3. `booking/docs/2026-06-12-booking-cvt-qa-prod-analysis.md` — **Pre-release analysis from yesterday** showing QA/CVT/PROD comparisons, known format differences, and GO recommendation. Use this as baseline for comparison.
4. `booking/docs/2026-06-12-booking-analysis-queries-scripts.md` — **Reusable queries and scripts from pre-release analysis**. Reuse and extend these if helpful.
5. `booking/docs/2026-06-08-booking-conf-field-format-diff.md` — CONFIRM record format differences.
6. `booking/docs/2026-06-08-booking-req-field-format-diff.md` — REQUEST record format differences.
7. `booking/docs/2026-08-08-booking-field-format-diff-impact-claude.md` — Impact analysis of field format differences.
8. `booking/docs/2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md` — Design and implementation review of the AWS 2.x upgrade.
9. `booking/docs/2026-03-27-booking-dev-log-review.md` — Example log trace showing all log patterns.

Focus ONLY on booking-related AWS components. Do not trace non-booking services.

---

## Checkout Tasks

### Task 1: ECS Deployment Verification

Verify the ECS deployment timeline and application startup health.

**What to check:**
- When were the ECS tasks started for the booking service? It appears deployment happened **after noon** and tasks were **restarted around 2000 hours (8 PM ET)**.
- Verify the exact deployment/task start timestamps
- Confirm application startup completed successfully with all AWS services initialized

**How:**
```bash
# List ECS tasks (running and stopped)
aws ecs list-tasks \
  --cluster ANEPRBK-001 \
  --service-name Booking-prod \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1

# Describe tasks for start times and status
aws ecs describe-tasks \
  --cluster ANEPRBK-001 \
  --tasks <TASK_ARN> \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1

# Also check stopped tasks to see restart history
aws ecs list-tasks \
  --cluster ANEPRBK-001 \
  --service-name Booking-prod \
  --desired-status STOPPED \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1

# Check service events for deployment timeline
aws ecs describe-services \
  --cluster ANEPRBK-001 \
  --services Booking-prod \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --query "services[0].events[:20]"
```

**CloudWatch startup verification:**
```
fields @timestamp, @message
| filter @message like /Starting InttraServer|Booking life cycle started|Creating.*repository for table|using cloud-sdk-aws factory|SQSListener|Started application/
| sort @timestamp asc
| limit 100
```
Run this for the time window covering the deployment (noon onwards) and the restart (~2000 hours).

Document:
- First deployment task start time
- Restart task start time (~2000 hours)
- Application startup log entries confirming all services initialized
- Any startup errors or warnings

---

### Task 2: Booking Volume Since Release

Count how many bookings have been created since the release went live.

**CloudWatch Logs Insights:**
```
fields @timestamp, @message
| filter @message like /Created new booking/
| sort @timestamp asc
| limit 1000
```
Set the time window from when the new deployment started (from Task 1) to now.

Also count by booking state:
```
fields @timestamp, @message
| filter @message like /Creating booking in state/
| parse @message /Creating booking in state (?<state>\w+)/
| stats count(*) as booking_count by state
```

Document:
- Total number of bookings created since release
- When the first booking was created after release
- Breakdown by booking state (REQUEST, CONFIRM, AMEND, CANCEL, etc.)

---

### Task 3: Booking State Classification

Classify bookings by state using **CloudWatch Logs Insights ONLY** — do NOT scan DynamoDB.

```
fields @timestamp, @message
| filter @message like /Creating booking in state/
| parse @message /Creating booking in state (?<state>\w+)/
| stats count(*) as count by state
| sort count desc
```

Also use this query to identify specific bookings per state for later DynamoDB lookup:
```
fields @timestamp, @message
| filter @message like /Created new booking/
| parse @message /Created new booking.*inttraReferenceNumber[=: ]+(?<inttraRef>\d+).*state[=: ]+(?<state>\w+)/
| display @timestamp, inttraRef, state
| sort @timestamp desc
| limit 100
```

From these results, pick 1-2 representative inttraReferenceNumbers per state for DynamoDB Query (Task 13).

**DO NOT USE `aws dynamodb scan`** — the production table has 147M+ records.

Document count of bookings per state.

---

### Task 4: Lambda Log Analysis — All Lambdas

Check logs for ALL booking Lambdas since release. For each Lambda, check its `/aws/lambda/<FUNCTION_NAME>` log group.

**Lambdas to check:**
1. `inttra2-pr-lambda-bookingdetail-S3ArchiveLambda`
2. `inttra2-pr-lambda-bookingdetail-ElasticsearchLambda`
3. `inttra2-pr-lambda-bookingdetail-SendLambda`
4. `inttra2-pr-lambda-bookingdetail-CargoScreen`
5. `inttra2-pr-lambda-booking-partner-integration`

For each Lambda, run:
```
fields @timestamp, @message
| filter @message like /ERROR|Exception|FATAL|timeout|task timed out/
| sort @timestamp desc
| limit 200
```

Document all exceptions and errors per Lambda.

---

### Task 5: ElasticsearchLambda Deep Dive

**Check for exceptions:**
```
fields @timestamp, @message
| filter @message like /(?i)exception|error|stacktrace|failed/
| filter @message not like /START|END|REPORT/
| sort @timestamp desc
| limit 200
```

**Count bookings indexed since release:**
```
fields @timestamp, @message
| filter @message like /(?i)index|indexed|indexing/
| stats count(*) as indexed_count
```

**Count bookings deleted since release:**
```
fields @timestamp, @message
| filter @message like /(?i)delete|deleted|removing/
| stats count(*) as deleted_count
```

Document: exception count, indexed count, deleted count, any patterns.

---

### Task 6: S3ArchiveLambda Deep Dive

**Check for exceptions:**
```
fields @timestamp, @message
| filter @message like /(?i)exception|error|stacktrace|failed/
| filter @message not like /START|END|REPORT/
| sort @timestamp desc
| limit 200
```

**Count S3 archiving operations:**
```
fields @timestamp, @message
| filter @message like /(?i)archiv|stored|uploaded|put.*object|s3/
| stats count(*) as archive_count
```

Document: exception count, archive count, any patterns.

---

### Task 7: Partner Integration Lambda Deep Dive

**Check for exceptions:**
```
fields @timestamp, @message
| filter @message like /(?i)exception|error|stacktrace|failed/
| filter @message not like /START|END|REPORT/
| sort @timestamp desc
| limit 200
```

**Count successful OB requests:**
```
fields @timestamp, @message
| filter @message like /(?i)successful|success|completed|200|sent/
| stats count(*) as success_count
```

**CRITICAL: DateTimeParseException Investigation**
There are reports of `DateTimeParseException` in this Lambda. Determine if this is a pre-existing issue or introduced by the release.

```
# Check for DateTimeParseException SINCE release
fields @timestamp, @message
| filter @message like /DateTimeParseException/
| sort @timestamp desc
| limit 200
```

```
# Check for DateTimeParseException BEFORE release (use time window before deployment)
# Set time range to 2026-06-10 00:00 — 2026-06-13 <deployment_time>
fields @timestamp, @message
| filter @message like /DateTimeParseException/
| sort @timestamp desc
| limit 200
```

Compare the frequency and stack traces before and after release. Document whether this is pre-existing or new.

---

### Task 8: API Request Analysis

Analyze API traffic since release.

**Total API requests (excluding health checks):**
```
fields @timestamp, @message
| filter @message like /MercuryRequestLoggingFilter/
| filter @message not like /ping|healthcheck/
| stats count(*) as request_count
```

**Group by API endpoint/URI:**
```
fields @timestamp, @message
| filter @message like /MercuryRequestLoggingFilter/
| filter @message not like /ping|healthcheck/
| parse @message /(?<method>GET|POST|PUT|DELETE|PATCH)\s+(?<uri>\/[^\s?]+)/
| stats count(*) as count by method, uri
| sort count desc
| limit 50
```

**Search API requests specifically:**
```
fields @timestamp, @message
| filter @message like /MercuryRequestLoggingFilter/
| filter @message like /search|Search/
| stats count(*) as search_count
```

Document: total requests, requests grouped by endpoint, search API count.

---

### Task 9: Booking Application Log Exception Analysis — CRITICAL

This is a key post-release health indicator. Scan the **booking application log group** (`inttra2-pr-lg-bkapi`) for ALL exceptions since release and categorize them.

**Step 1: Count all exceptions since release by type:**
```
fields @timestamp, @message
| filter @message like /(?i)exception/
| filter @message not like /ping|healthcheck/
| parse @message /(?<exception_type>[A-Za-z\.]+Exception)/
| stats count(*) as count by exception_type
| sort count desc
| limit 50
```

**Step 2: Count ERROR-level log entries:**
```
fields @timestamp, @message
| filter @message like /ERROR/
| filter @message not like /ping|healthcheck/
| stats count(*) as error_count by bin(1h) as hour
| sort hour asc
```

**Step 3: Identify unique exception stack traces:**
```
fields @timestamp, @message
| filter @message like /(?i)exception|ERROR|FATAL|stacktrace|caused by/
| filter @message not like /ping|healthcheck|NotFoundException.*geography|NotFoundException.*participant/
| sort @timestamp desc
| limit 500
```

**Step 4: Check for new exception types not seen pre-release:**
From the pre-release analysis (`2026-06-12-booking-cvt-qa-prod-analysis.md`), the known pre-existing exceptions were:
- `NotFoundException` (INFO level, benign — geography/participant 404s from NetworkServiceClient)
- Pre-existing Lambda timeouts (S3ArchiveLambda, SendLambda)

Any exception type NOT in this list is potentially introduced by the release and must be flagged as **CRITICAL** or **WARNING**.

**Step 5: Group exceptions by time window to detect patterns:**
```
fields @timestamp, @message
| filter @message like /(?i)exception/
| filter @message not like /ping|healthcheck/
| parse @message /(?<exception_type>[A-Za-z\.]+Exception)/
| stats count(*) as count by exception_type, bin(30m) as time_bucket
| sort time_bucket asc, count desc
```

This shows if exceptions are clustered around specific times (e.g., the restart at ~2000h).

**Document:**
- Complete exception type inventory with counts
- Severity classification: CRITICAL (breaks booking flow) / WARNING (may affect data) / INFO (benign/expected)
- Whether each exception type is pre-existing or new since release
- Time-based patterns (clustered around deployment? Continuous? Sporadic?)
- Comparison with pre-release baseline from yesterday's analysis

---

### Task 10: Outbound Processing Verification

Check outbound processing pipeline for issues.

**Email processing:**
```
fields @timestamp, @message
| filter @message like /Email processing done|email.*sent|email.*failed/
| sort @timestamp desc
| limit 200
```

**Watermill outbound:**
```
fields @timestamp, @message
| filter @message like /Watermill OB sent|Watermill metadata sent/
| sort @timestamp desc
| limit 200
```

**EDI/SQS outbound:**
```
fields @timestamp, @message
| filter @message like /EDI.*OB sent|SQS OB sent/
| sort @timestamp desc
| limit 200
```

**S3 uploads (transformer):**
```
fields @timestamp, @message
| filter @message like /transformer Uploaded to bucket|Uploading object to S3/
| sort @timestamp desc
| limit 200
```

**Check for outbound errors:**
```
fields @timestamp, @message
| filter @message like /(?i)outbound|watermill|email.*processing|file.*delivery/
| filter @message like /(?i)error|exception|failed|failure/
| sort @timestamp desc
| limit 200
```

Document any issues found in outbound processing.

---

### Task 11: OB Subscription Processing

Count OB subscriptions processed by workflowId and/or inttraReferenceNumber.

```
fields @timestamp, @message
| filter @message like /subscription/
| filter @message like /workflowId/
| stats count(*) as sub_count
```

```
fields @timestamp, @message
| filter @message like /OB.*subscription|subscription.*processed|Processing.*subscription/
| parse @message /workflowId[=: ]+(?<wfId>[a-f0-9-]+)/
| stats count(*) as count by wfId
| sort count desc
| limit 50
```

```
fields @timestamp, @message
| filter @message like /OB.*subscription|subscription.*processed/
| parse @message /inttraReferenceNumber[=: ]+(?<inttraRef>\d+)/
| stats count(*) as count by inttraRef
| sort count desc
| limit 50
```

Also check the outbound Lambda (`inttra2-pr-lambda-booking-outbound`) logs for subscription processing.

Document: total subscription count, breakdown by workflow/inttraRef.

---

### Task 12: Email Processing Verification

Verify email processing in outbound is working correctly.

```
fields @timestamp, @message
| filter @message like /Email processing done|email|Email/
| sort @timestamp desc
| limit 200
```

Check for email-related errors:
```
fields @timestamp, @message
| filter @message like /(?i)email/
| filter @message like /(?i)error|exception|failed/
| sort @timestamp desc
| limit 100
```

Document: email processing count, any failures, comparison with pre-release patterns.

---

### Task 13: DynamoDB Record Integrity Verification

For a sample of bookings in each booking state (REQUEST, CONFIRM, AMEND, CANCEL, etc.), retrieve the full DynamoDB record and verify it conforms to the AWS SDK v2 upgrade expectations.

**Step 1: Use CloudWatch results from Task 3** to identify specific inttraReferenceNumbers per booking state.

**Step 2: Query DynamoDB via GSI** for each selected booking (NEVER scan):
```bash
aws dynamodb query \
  --table-name inttra2_prod_booking_BookingDetail \
  --index-name INTTRA_REFERENCE_NUMBER_INDEX \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```

**For each sampled booking, check:**
- Boolean field types: Should now be `{"BOOL": true/false}` (SDK v2 format)
- Null handling: May now include `{"NULL": true}` for absent fields
- Party list completeness and presence of expected fields
- Location list completeness
- Date/time field formats (verify no precision loss)
- Numeric precision
- `splitCopy` field absence (intentionally removed in v2)
- `partyId`/`partyScac` field handling

Select at least **one booking per state** (REQUEST, CONFIRM, and any other states found in Task 3). Compare the record format with the expected SDK v2 format documented in the pre-release analysis.

---

### Task 14: Multi-Version Booking Analysis

Find bookings created today that have multiple versions and document them.

**Use CloudWatch Logs Insights to identify candidates** (NOT DynamoDB scan):
```
fields @timestamp, @message
| filter @message like /Created new booking/
| parse @message /inttraReferenceNumber[=: ]+(?<inttraRef>\d+)/
| stats count(*) as version_count by inttraRef
| filter version_count > 1
| sort version_count desc
| limit 30
```

Then, for the top multi-version bookings found, **Query DynamoDB via GSI** to get all versions:
```bash
aws dynamodb query \
  --table-name inttra2_prod_booking_BookingDetail \
  --index-name INTTRA_REFERENCE_NUMBER_INDEX \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --projection-expression "inttraReferenceNumber, sequenceNumber, #st, createdDate, bookingId, workflowId" \
  --expression-attribute-names '{"#st": "state"}' \
  --select SPECIFIC_ATTRIBUTES \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```

**DO NOT USE `aws dynamodb scan`** — always use Query with GSI.

Document:
- InttraReferenceNumbers with multiple versions
- The states and sequence numbers of each version
- Any anomalies in the version progression

---

### Task 15: SQS Queue Health

Check all booking SQS queues for message backlogs or dead-letter queue activity.

```bash
# Check each queue's attributes
for QUEUE in inttra2_pr_sqs_bk_inbound inttra2_pr_sqs_watermill_bk inttra2-pr-sqs-bookingdetail-s3 inttra2-pr-sqs-booking-partner-integration; do
  echo "=== $QUEUE ==="
  aws sqs get-queue-url --queue-name "$QUEUE" --profile 642960533737_INTTRA2-QATeam --region us-east-1 2>/dev/null && \
  aws sqs get-queue-attributes \
    --queue-url "https://sqs.us-east-1.amazonaws.com/642960533737/$QUEUE" \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible ApproximateNumberOfMessagesDelayed \
    --profile 642960533737_INTTRA2-QATeam \
    --region us-east-1 2>/dev/null
done
```

Document any queues with non-zero message counts that could indicate issues.

---

## Output Documents

### Primary findings document
Write ALL findings to: **`booking/docs/2026-06-13-booking-prod-release-checkout.md`**

Structure:
```markdown
# Booking Production Release Checkout
**Date:** 2026-06-13
**Ticket:** ION-14382
**Release Date:** 2026-06-13
**Analyst:** Claude Opus 4.6 Agent

## Executive Summary
[Overall health assessment. Is the release healthy? Any issues found? Key metrics.]

## 1. ECS Deployment Timeline
### 1.1 Initial Deployment (afternoon)
[Task start time, startup logs, service initialization confirmation]
### 1.2 Task Restart (~2000 hours)
[Restart time, reason if discoverable, startup confirmation]

## 2. Booking Volume Since Release
### 2.1 Total Bookings Created
[Count, first booking timestamp]
### 2.2 Bookings by State
| State | Count |
|-------|-------|
[Breakdown table]

## 3. Lambda Health
### 3.1 ElasticsearchLambda
[Exceptions, indexed count, deleted count]
### 3.2 S3ArchiveLambda
[Exceptions, archive count]
### 3.3 Partner Integration Lambda
[Exceptions, successful OB count, DateTimeParseException analysis — pre-existing vs new]
### 3.4 SendLambda
[Exceptions, activity]
### 3.5 CargoScreen Lambda
[Exceptions, activity]
### 3.6 Outbound Lambda
[Exceptions, activity]

## 4. API Traffic Analysis
### 4.1 Total Requests Since Release
### 4.2 Requests by Endpoint
| Method | URI | Count |
|--------|-----|-------|
### 4.3 Search API Requests

## 5. Exception Classification
### 5.1 Exception Summary
| Exception Type | Count | Severity | Pre-existing? | Notes |
|---------------|-------|----------|---------------|-------|
### 5.2 New Exceptions (if any)
### 5.3 Comparison with Pre-Release Baseline

## 6. Outbound Processing
### 6.1 Email Processing
[Count, status, any failures]
### 6.2 Watermill Outbound
[Count, status]
### 6.3 EDI/SQS Outbound
[Count, status]
### 6.4 S3 Uploads
[Count, status]
### 6.5 Outbound Errors

## 7. OB Subscription Processing
### 7.1 Total Subscriptions Processed
### 7.2 By WorkflowId
### 7.3 By InttraReferenceNumber

## 8. DynamoDB Record Integrity
### 8.1 REQUEST Record Sample
[InttraRef, key fields, boolean format, null handling verification]
### 8.2 CONFIRM Record Sample
[Same]
### 8.3 Other State Samples
[As found]
### 8.4 Format Compliance Summary
[Does the record format match SDK v2 expectations from pre-release analysis?]

## 9. Multi-Version Bookings
### 9.1 Bookings with Multiple Versions Today
| InttraRef | Versions | States | Notes |
|-----------|----------|--------|-------|
### 9.2 Detailed Trace of Selected Multi-Version Bookings

## 10. SQS Queue Health
| Queue | Messages | In-Flight | Delayed | Status |
|-------|----------|-----------|---------|--------|

## 11. Conclusions & Recommendations
[Overall assessment, any action items, monitoring recommendations]
```

### Scripts and queries document
Write ALL CloudWatch queries, AWS CLI commands, and DynamoDB queries to: **`booking/docs/2026-06-13-booking-prod-release-checkout-scripts.md`**

Structure:
```markdown
# Booking Production Release Checkout — Reusable Queries & Scripts
**Date:** 2026-06-13
**Companion to:** [2026-06-13-booking-prod-release-checkout.md](2026-06-13-booking-prod-release-checkout.md)

## Usage Notes
- All queries use `--profile 642960533737_INTTRA2-QATeam` and `--region us-east-1`
- For CloudWatch Logs Insights queries, specify time range via the `--start-time` and `--end-time` parameters (epoch seconds)
- Time conversion helper: `date -d "2026-06-13 12:00:00 EDT" +%s`
- Replace `<START_EPOCH>` and `<END_EPOCH>` with your desired time window

## 1. ECS Queries
[Commands with parameterized time windows]

## 2. CloudWatch Logs Insights Queries
### 2.1 Parameterized Query Runner
[Template showing how to run any Logs Insights query with variable time window]

### 2.2 Query Reference Table
| # | Query Name | Description | Parameters to Replace | Usage | Query |
|---|-----------|-------------|----------------------|-------|-------|
[All queries used during checkout, made reusable with parameterized time windows]

## 3. DynamoDB Queries
[All DynamoDB queries used, with parameterized table names and references]

## 4. SQS Queries
[Queue health check commands]

## 5. Lambda Queries
[Lambda-specific log queries]

## 6. Aggregate/Analytics Queries
[Booking volume, API traffic, exception classification queries]

## 7. Environment Prefix Mapping
| Environment | DynamoDB prefix | S3 prefix | SQS underscore prefix | SQS/Lambda hyphen prefix | CloudWatch prefix |
|------------|----------------|-----------|----------------------|--------------------------|-------------------|
| Production | `inttra2_prod_` | `inttra2-pr-` | `inttra2_pr_` | `inttra2-pr-` | `inttra2-pr-` |
| QA | `inttra2_qa_` | `inttra2-qa-` | `inttra2_qa_` | `inttra2-qa-` | `inttra2-qa-` |
| CVT | `inttra2_test_` | `inttra2-cv-` | `inttra2_cv_` | `inttra2-cv-` | `inttra2-cv-` |

**NOTE**: CVT uses `_test_` for DynamoDB table prefix but `_cv_`/`-cv-` for other resources.
```

**IMPORTANT**: For all queries in the scripts document:
- Make time windows parameterized with `<START_EPOCH>` and `<END_EPOCH>` placeholders
- Include usage examples showing how to specify custom time windows
- Include `date` command examples for converting human-readable dates to epoch seconds
- Where possible, show both "since release" and "custom time window" variants

---

## Execution Plan

Execute in this order:

### Phase 1: Setup & Context (do first)
1. Read all reference documents listed above (especially the pre-release analysis from yesterday)
2. Create/resume MCP session
3. Log model info in session context

### Phase 2: ECS & Deployment Verification
4. Check ECS task start times and deployment timeline
5. Verify application startup logs (both initial deployment and ~2000h restart)
6. Confirm all AWS service bindings (DynamoDB, SQS, SNS, S3)

### Phase 3: Booking Volume & Classification
7. Count bookings created since release
8. Classify by booking state
9. Identify first booking timestamp post-release

### Phase 4: Lambda Health Check
10. Check all Lambda log groups for exceptions
11. Deep dive: ElasticsearchLambda — indexed/deleted counts
12. Deep dive: S3ArchiveLambda — archive count
13. Deep dive: Partner Integration Lambda — OB count + DateTimeParseException analysis
14. Check DateTimeParseException pre-release vs post-release

### Phase 5: API Traffic & Exceptions
15. Analyze API request volume and endpoint distribution
16. Count search API requests specifically
17. Classify all exceptions by type and count
18. Compare exception patterns with pre-release baseline

### Phase 6: Outbound & Subscription Processing
19. Check outbound pipeline (email, Watermill, EDI, S3)
20. Count OB subscriptions by workflowId and inttraRef
21. Verify email processing is working
22. Check for any outbound errors

### Phase 7: Data Integrity
23. Sample DynamoDB records per booking state — verify SDK v2 format compliance
24. Find and document multi-version bookings from today
25. Verify record format matches pre-release expectations

### Phase 8: Queue Health
26. Check all SQS queues for backlogs

### Phase 9: Documentation
27. Write findings to `booking/docs/2026-06-13-booking-prod-release-checkout.md`
28. Write all queries/scripts to `booking/docs/2026-06-13-booking-prod-release-checkout-scripts.md`
29. Final session context update

---

## AWS CLI Tips

### CloudWatch Logs Insights (async — start then get results)
```bash
# Start query with parameterized time window
QUERY_ID=$(aws logs start-query \
  --log-group-name "<LOG_GROUP>" \
  --start-time <START_EPOCH> \
  --end-time <END_EPOCH> \
  --query-string "<INSIGHTS_QUERY>" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output text --query 'queryId')

# Wait a few seconds, then get results
aws logs get-query-results --query-id "$QUERY_ID" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

### Time Window Examples
```bash
# Today from noon EDT to now
START=$(date -d "2026-06-13 12:00:00 EDT" +%s)
END=$(date +%s)

# Custom window (e.g., 3 days before release for comparison)
START=$(date -d "2026-06-10 00:00:00 EDT" +%s)
END=$(date -d "2026-06-13 12:00:00 EDT" +%s)

# Specific hour window
START=$(date -d "2026-06-13 20:00:00 EDT" +%s)
END=$(date -d "2026-06-13 21:00:00 EDT" +%s)
```

### DynamoDB Query by InttraRef (via GSI) — ALWAYS USE THIS
```bash
aws dynamodb query \
  --table-name inttra2_prod_booking_BookingDetail \
  --index-name INTTRA_REFERENCE_NUMBER_INDEX \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```

### DynamoDB Query with Projection (minimize RCU)
```bash
aws dynamodb query \
  --table-name inttra2_prod_booking_BookingDetail \
  --index-name INTTRA_REFERENCE_NUMBER_INDEX \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --projection-expression "inttraReferenceNumber, sequenceNumber, #st, #src, createdDate, bookingId, workflowId" \
  --expression-attribute-names '{"#st": "state", "#src": "source"}' \
  --select SPECIFIC_ATTRIBUTES \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```

### ⚠️ NEVER USE DynamoDB Scan
The production table has **147M+ records**. A scan will:
- Consume enormous RCU and throttle production traffic
- Take hours to complete
- Potentially trigger DynamoDB auto-scaling alarms

**Instead, use CloudWatch Logs Insights** for aggregate analytics (booking counts, state classification, volume metrics). Use DynamoDB Query with GSI for specific booking lookups.

### Discover Resources
```bash
# Log groups
aws logs describe-log-groups --log-group-name-prefix "inttra2-pr" --profile 642960533737_INTTRA2-QATeam --region us-east-1

# Lambda functions
aws lambda list-functions --profile 642960533737_INTTRA2-QATeam --region us-east-1 \
  --query "Functions[?contains(FunctionName, 'pr') && contains(FunctionName, 'booking')].[FunctionName]" --output text

# SQS queues
aws sqs list-queues --queue-name-prefix "inttra2_pr_sqs_bk" --profile 642960533737_INTTRA2-QATeam --region us-east-1
aws sqs list-queues --queue-name-prefix "inttra2-pr-sqs-booking" --profile 642960533737_INTTRA2-QATeam --region us-east-1
```

---

## Environment Prefix Mapping

| Environment | DynamoDB prefix | S3 prefix | SQS underscore prefix | SQS/Lambda hyphen prefix | CloudWatch prefix |
|------------|----------------|-----------|----------------------|--------------------------|-------------------|
| Production | `inttra2_prod_` | `inttra2-pr-` | `inttra2_pr_` | `inttra2-pr-` | `inttra2-pr-` |
| QA | `inttra2_qa_` | `inttra2-qa-` | `inttra2_qa_` | `inttra2-qa-` | `inttra2-qa-` |
| CVT | `inttra2_test_` | `inttra2-cv-` | `inttra2_cv_` | `inttra2-cv-` | `inttra2-cv-` |

**NOTE**: CVT uses `_test_` for DynamoDB table prefix but `_cv_`/`-cv-` for other resources. Verify carefully.
