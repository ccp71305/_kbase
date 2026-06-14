# Booking Production Release Checkout — Reusable Queries & Scripts
**Date:** 2026-06-13  
**Companion to:** [2026-06-13-booking-prod-release-checkout.md](2026-06-13-booking-prod-release-checkout.md)

---

## Usage Notes

- All queries use `--profile 642960533737_INTTRA2-QATeam` and `--region us-east-1`
- For CloudWatch Logs Insights queries, specify time range via `--start-time` and `--end-time` (epoch seconds)
- **NEVER scan DynamoDB** — production table has 147M+ records
- Always use Query with GSI or primary key

### Time Conversion Helpers

**⚠️ IMPORTANT:** Always verify your epoch corresponds to the correct **year**. A common mistake is generating an epoch for 2025 instead of 2026 (or vice versa), which will query the wrong time period and produce inflated/incorrect results.

```bash
# PowerShell - Get current epoch
$now = [int](Get-Date -UFormat %s)

# PowerShell - Specific time (EDT = UTC-4)
$start = [int](Get-Date "2026-06-13 12:00:00" -UFormat %s)

# PowerShell - Relative (12 hours ago)
$start = [int](Get-Date -UFormat %s) - 43200

# Linux/Mac - RECOMMENDED: use explicit date format
START=$(date -d "2026-06-13 12:00:00 EDT" +%s)
END=$(date +%s)

# Verify your epoch is correct!
date -d @$START   # Should show the date you expect
```

---

## 1. ECS Queries

### 1.1 Check Service Status & Events
```bash
aws ecs describe-services \
  --cluster ANEPRBK-001 \
  --services Booking-prod \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --query "services[0].{serviceName:serviceName,status:status,runningCount:runningCount,desiredCount:desiredCount,taskDefinition:taskDefinition,deployments:deployments,events:events[:20]}" \
  --output json
```
**Usage:** Run anytime to check deployment status. Events show last 20 actions (target registrations, task starts/stops).

### 1.2 List Running Tasks
```bash
aws ecs list-tasks \
  --cluster ANEPRBK-001 \
  --service-name Booking-prod \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 --output json
```

### 1.3 Describe Tasks (start times, status)
```bash
aws ecs describe-tasks \
  --cluster ANEPRBK-001 \
  --tasks <TASK_ARN_1> <TASK_ARN_2> \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --query "tasks[].{taskArn:taskArn,createdAt:createdAt,startedAt:startedAt,lastStatus:lastStatus}" \
  --output json
```

### 1.4 Check Task Definition
```bash
aws ecs describe-task-definition \
  --task-definition "Booking-latest-prod-Task:16" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --query "taskDefinition.containerDefinitions[].{name:name,image:image}" \
  --output json
```

---

## 2. CloudWatch Logs Insights Queries

### 2.1 Parameterized Query Runner Template

```powershell
# PowerShell template for running any Logs Insights query
$LOG_GROUP = "inttra2-pr-lg-bkapi"  # Change as needed
$START_EPOCH = [int](Get-Date "2026-06-13 12:00:00" -UFormat %s)
$END_EPOCH = [int](Get-Date -UFormat %s)
$QUERY = "fields @timestamp, @message | filter @message like /YOUR_PATTERN/ | sort @timestamp asc | limit 200"

$queryId = aws logs start-query `
  --log-group-name $LOG_GROUP `
  --start-time $START_EPOCH `
  --end-time $END_EPOCH `
  --query-string $QUERY `
  --profile 642960533737_INTTRA2-QATeam `
  --region us-east-1 `
  --output text --query 'queryId'

Start-Sleep -Seconds 15  # Wait for query to complete

aws logs get-query-results --query-id $queryId `
  --profile 642960533737_INTTRA2-QATeam `
  --region us-east-1 --output json
```

```bash
# Bash template
LOG_GROUP="inttra2-pr-lg-bkapi"
START_EPOCH=$(date -d "2026-06-13 12:00:00 EDT" +%s)
END_EPOCH=$(date +%s)
QUERY='fields @timestamp, @message | filter @message like /YOUR_PATTERN/ | sort @timestamp asc | limit 200'

QUERY_ID=$(aws logs start-query \
  --log-group-name "$LOG_GROUP" \
  --start-time $START_EPOCH \
  --end-time $END_EPOCH \
  --query-string "$QUERY" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output text --query 'queryId')

sleep 15
aws logs get-query-results --query-id "$QUERY_ID" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

### 2.2 Query Reference Table

| # | Query Name | Description | Parameters | Query |
|---|-----------|-------------|-----------|-------|
| 1 | Booking volume count | Total bookings created in time window | Time range | `fields @timestamp, @message \| filter @message like /Created new booking/ \| stats count(*) as total` |
| 2 | Bookings by state | Count bookings per state (REQUEST, CONFIRM, etc.) | Time range | `fields @timestamp, @message \| filter @message like /Created new booking/ \| parse @message /in state (?<state>\w+)/ \| stats count(*) as count by state \| sort count desc` |
| 3 | First N bookings | See earliest bookings in window | Time range, limit | `fields @timestamp, @message \| filter @message like /Created new booking/ \| sort @timestamp asc \| limit 5` |
| 4 | Exception classification | Group all exceptions by type with counts | Time range | `fields @timestamp, @message \| filter @message like /(?i)exception/ \| filter @message not like /ping\|healthcheck/ \| parse @message /(?<exception_type>[A-Za-z\.]+Exception)/ \| stats count(*) as count by exception_type \| sort count desc \| limit 50` |
| 5 | Exception hourly pattern | Exceptions over time (excluding benign) | Time range | `fields @timestamp, @message \| filter @message like /(?i)exception/ \| filter @message not like /NotFoundException\|DateTimeParseException\|ping\|healthcheck/ \| stats count(*) as count by bin(1h) as hour \| sort hour asc` |
| 6 | API traffic by endpoint | Group API requests by method+URI | Time range | `fields @timestamp, @message \| filter @message like /MercuryRequestLoggingFilter/ \| filter @message not like /ping\|healthcheck/ \| parse @message /(?<method>GET\|POST\|PUT\|DELETE\|PATCH)\s+(?<uri>\/[^\s?]+)/ \| stats count(*) as count by method, uri \| sort count desc \| limit 50` |
| 7 | Search API count | Count search requests specifically | Time range | `fields @timestamp, @message \| filter @message like /MercuryRequestLoggingFilter/ \| filter @message like /search\|Search/ \| stats count(*) as search_count` |
| 8 | Email processing | Count email processing events | Time range | `fields @timestamp, @message \| filter @message like /Email processing done\|email.*sent\|email.*failed/ \| stats count(*) as count` |
| 9 | Watermill OB | Count watermill outbound events | Time range | `fields @timestamp, @message \| filter @message like /Watermill OB sent\|Watermill metadata sent/ \| stats count(*) as count` |
| 10 | Subscription processing | Count subscription events | Time range | `fields @timestamp, @message \| filter @message like /(?i)subscription.*process\|processing.*subscription/ \| stats count(*) as count` |
| 11 | Partner integration OB | Count partner integration requests | Time range | `fields @timestamp, @message \| filter @message like /outbound.*partnerintegration\|partner.*integration/ \| stats count(*) as count` |
| 12 | DateTimeParseException detail | See specific DateTimeParseException occurrences | Time range | `fields @timestamp, @message \| filter @message like /DateTimeParseException/ \| sort @timestamp desc \| limit 10` |
| 13 | DateTimeParseException count | Total count for rate comparison | Time range | `fields @timestamp, @message \| filter @message like /DateTimeParseException/ \| stats count(*) as count` |
| 14 | Outbound errors | Find errors in outbound processing | Time range | `fields @timestamp, @message \| filter @message like /(?i)outbound\|watermill\|email.*processing\|file.*delivery/ \| filter @message like /(?i)error\|exception\|failed\|failure/ \| sort @timestamp desc \| limit 50` |
| 15 | Trace by inttraRef | All log entries for a specific booking | Time range, `<INTTRA_REF>` | `fields @timestamp, @message \| filter @message like /<INTTRA_REF>/ \| sort @timestamp asc \| limit 200` |
| 16 | Trace by workflowId | Follow a booking workflow | Time range, `<WORKFLOW_ID>` | `fields @timestamp, @message \| filter @message like /<WORKFLOW_ID>/ \| sort @timestamp asc \| limit 200` |
| 17 | Lambda errors (generic) | Find errors in any Lambda log group | Time range, change log group | `fields @timestamp, @message \| filter @message like /(?i)exception\|error\|stacktrace\|failed/ \| filter @message not like /START\|END\|REPORT/ \| sort @timestamp desc \| limit 100` |
| 18 | Lambda invocation count | Count Lambda invocations via REPORT | Time range | `fields @timestamp, @message \| filter @message like /REPORT/ \| stats count(*) as invocation_count` |
| 19 | ES Lambda indexing count | Count ES index operations | Time range | `fields @timestamp, @message \| filter @message like /(?i)index\|indexed\|indexing/ \| filter @message not like /REPORT\|START\|END\|error\|exception/ \| parse @message /(?<action>index\|delete\|Index\|Delete)/ \| stats count(*) as cnt by action \| sort cnt desc` |
| 20 | Application startup | Find startup markers after deployment | Time range | `fields @timestamp, @message \| filter @message like /(?i)started\|startup\|initializ\|InttraServer\|cloud-sdk\|DynamoDb.*repository\|SQSListener/ \| sort @timestamp asc \| limit 100` |
| 21 | ERROR level hourly | ERROR log rate over time | Time range | `fields @timestamp, @message \| filter @message like /ERROR/ \| filter @message not like /ping\|healthcheck/ \| stats count(*) as error_count by bin(1h) as hour \| sort hour asc` |

---

## 3. DynamoDB Queries

### 3.1 Query by InttraReferenceNumber (via GSI)
```bash
# Get all versions of a booking
# Replace: <INTTRA_REF>
aws dynamodb query \
  --table-name inttra2_prod_booking_BookingDetail \
  --index-name INTTRA_REFERENCE_NUMBER_INDEX \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```
**Usage:** Returns all versions (bookingId + sequenceNumber keys) for a given inttraReferenceNumber. GSI projects: bookingId, sequenceNumber, inttraReferenceNumber.

### 3.2 Get Full Record by Primary Key
```bash
# Get complete DynamoDB record with all attributes
# Replace: <BOOKING_ID>, <SEQUENCE_NUMBER>
aws dynamodb get-item \
  --table-name inttra2_prod_booking_BookingDetail \
  --key '{"bookingId": {"S": "<BOOKING_ID>"}, "sequenceNumber": {"S": "<SEQUENCE_NUMBER>"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```
**Usage:** First use 3.1 to get bookingId+sequenceNumber, then use this to get the full record.

### 3.3 Describe Table Schema
```bash
aws dynamodb describe-table \
  --table-name inttra2_prod_booking_BookingDetail \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --query "Table.{KeySchema: KeySchema, GlobalSecondaryIndexes: GlobalSecondaryIndexes[].{IndexName: IndexName, KeySchema: KeySchema, Projection: Projection}}" \
  --output json
```

### 3.4 ⚠️ NEVER USE SCAN
```
# DO NOT USE — production table has 147M+ records
# aws dynamodb scan ... ← NEVER DO THIS IN PRODUCTION
#
# Instead:
# - Use CloudWatch Logs Insights for aggregate analytics
# - Use GSI Query (3.1) for specific booking lookups
# - Use get-item (3.2) for full records
```

---

## 4. SQS Queries

### 4.1 Check Queue Health (All Booking Queues)
```powershell
# PowerShell - Check all booking SQS queues
$queues = @(
    "inttra2_pr_sqs_bk_inbound",
    "inttra2_pr_sqs_watermill_bk",
    "inttra2-pr-sqs-bookingdetail-s3",
    "inttra2-pr-sqs-booking-partner-integration"
)
foreach ($q in $queues) {
    Write-Host "=== $q ==="
    aws sqs get-queue-attributes `
      --queue-url "https://sqs.us-east-1.amazonaws.com/642960533737/$q" `
      --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible ApproximateNumberOfMessagesDelayed `
      --profile 642960533737_INTTRA2-QATeam `
      --region us-east-1
}
```

```bash
# Bash - Single queue check
# Replace: <QUEUE_NAME>
aws sqs get-queue-attributes \
  --queue-url "https://sqs.us-east-1.amazonaws.com/642960533737/<QUEUE_NAME>" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible ApproximateNumberOfMessagesDelayed \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```
**Usage:** Messages=0 is healthy. In-flight means actively being processed. High pending count indicates consumer lag.

---

## 5. Lambda Queries

### 5.1 Lambda Log Group Names
| Lambda | Log Group |
|--------|-----------|
| ElasticsearchLambda | `/aws/lambda/inttra2-pr-lambda-bookingdetail-ElasticsearchLambda` |
| S3ArchiveLambda | `/aws/lambda/inttra2-pr-lambda-bookingdetail-S3ArchiveLambda` |
| SendLambda | `/aws/lambda/inttra2-pr-lambda-bookingdetail-SendLambda` |
| CargoScreen | `/aws/lambda/inttra2-pr-lambda-bookingdetail-CargoScreen` |
| Partner Integration | `/aws/lambda/inttra2-pr-lambda-booking-partner-integration` |
| Outbound | `/aws/lambda/inttra2-pr-lambda-booking-outbound` |

### 5.2 Check Lambda Errors (Template)
```bash
# Replace: <LAMBDA_LOG_GROUP>, <START_EPOCH>, <END_EPOCH>
QUERY_ID=$(aws logs start-query \
  --log-group-name "<LAMBDA_LOG_GROUP>" \
  --start-time <START_EPOCH> \
  --end-time <END_EPOCH> \
  --query-string "fields @timestamp, @message | filter @message like /(?i)exception|error|stacktrace|failed/ | filter @message not like /START|END|REPORT/ | sort @timestamp desc | limit 100" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output text --query 'queryId')

sleep 15
aws logs get-query-results --query-id "$QUERY_ID" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

### 5.3 Lambda Invocation Count
```bash
# Replace: <LAMBDA_LOG_GROUP>, <START_EPOCH>, <END_EPOCH>
QUERY_ID=$(aws logs start-query \
  --log-group-name "<LAMBDA_LOG_GROUP>" \
  --start-time <START_EPOCH> \
  --end-time <END_EPOCH> \
  --query-string "fields @timestamp, @message | filter @message like /REPORT/ | stats count(*) as invocation_count" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output text --query 'queryId')

sleep 15
aws logs get-query-results --query-id "$QUERY_ID" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

---

## 6. Aggregate/Analytics Queries

### 6.1 Full Checkout Script (PowerShell)
```powershell
# Run all key health checks in one shot
# Adjust START/END as needed
$START = [int](Get-Date "2026-06-13 12:00:00" -UFormat %s)
$END = [int](Get-Date -UFormat %s)
$PROFILE = "642960533737_INTTRA2-QATeam"
$LOG_GROUP = "inttra2-pr-lg-bkapi"

# Booking count
$q1 = aws logs start-query --log-group-name $LOG_GROUP --start-time $START --end-time $END --query-string "fields @timestamp, @message | filter @message like /Created new booking/ | stats count(*) as total" --profile $PROFILE --region us-east-1 --output text --query 'queryId'

# Exception types
$q2 = aws logs start-query --log-group-name $LOG_GROUP --start-time $START --end-time $END --query-string "fields @timestamp, @message | filter @message like /(?i)exception/ | filter @message not like /ping|healthcheck/ | parse @message /(?<etype>[A-Za-z\.]+Exception)/ | stats count(*) as count by etype | sort count desc | limit 30" --profile $PROFILE --region us-east-1 --output text --query 'queryId'

# State classification
$q3 = aws logs start-query --log-group-name $LOG_GROUP --start-time $START --end-time $END --query-string "fields @timestamp, @message | filter @message like /Created new booking/ | parse @message /in state (?<state>\w+)/ | stats count(*) as count by state | sort count desc" --profile $PROFILE --region us-east-1 --output text --query 'queryId'

Write-Host "Queries started: $q1, $q2, $q3"
Write-Host "Waiting 30s for completion..."
Start-Sleep -Seconds 30

Write-Host "=== BOOKING COUNT ==="
aws logs get-query-results --query-id $q1 --profile $PROFILE --region us-east-1 --output json
Write-Host "`n=== EXCEPTIONS ==="
aws logs get-query-results --query-id $q2 --profile $PROFILE --region us-east-1 --output json
Write-Host "`n=== STATES ==="
aws logs get-query-results --query-id $q3 --profile $PROFILE --region us-east-1 --output json
```

### 6.2 DynamoDB Record Format Analysis (PowerShell)
```powershell
# Analyze DynamoDB record format for SDK v2 compliance
# Replace <BOOKING_ID> and <SEQUENCE_NUMBER>
$result = aws dynamodb get-item `
  --table-name inttra2_prod_booking_BookingDetail `
  --key '{"bookingId": {"S": "<BOOKING_ID>"}, "sequenceNumber": {"S": "<SEQUENCE_NUMBER>"}}' `
  --profile 642960533737_INTTRA2-QATeam `
  --region us-east-1 --output json

$boolTrue = ([regex]::Matches($result, '"BOOL":\s*true')).Count
$boolFalse = ([regex]::Matches($result, '"BOOL":\s*false')).Count
$nullTrue = ([regex]::Matches($result, '"NULL":\s*true')).Count
$nZero = ([regex]::Matches($result, '"N":\s*"0"')).Count
$nOne = ([regex]::Matches($result, '"N":\s*"1"')).Count
$splitCopy = ([regex]::Matches($result, '"splitCopy"')).Count
$partyId = ([regex]::Matches($result, '"partyId"')).Count

Write-Host "BOOL: true=$boolTrue, false=$boolFalse (total=$($boolTrue+$boolFalse))"
Write-Host "NULL: true=$nullTrue"
Write-Host "N(0/1): '0'=$nZero, '1'=$nOne (total=$($nZero+$nOne))"
Write-Host "splitCopy: $splitCopy"
Write-Host "partyId: $partyId"
Write-Host "Size: $($result.Length) chars"
```

---

## 7. Environment Prefix Mapping

| Environment | DynamoDB prefix | S3 prefix | SQS underscore prefix | SQS/Lambda hyphen prefix | CloudWatch prefix |
|------------|----------------|-----------|----------------------|--------------------------|-------------------|
| Production | `inttra2_prod_` | `inttra2-pr-` | `inttra2_pr_` | `inttra2-pr-` | `inttra2-pr-` |
| QA | `inttra2_qa_` | `inttra2-qa-` | `inttra2_qa_` | `inttra2-qa-` | `inttra2-qa-` |
| CVT | `inttra2_test_` | `inttra2-cv-` | `inttra2_cv_` | `inttra2-cv-` | `inttra2-cv-` |

**NOTE**: CVT uses `_test_` for DynamoDB table prefix but `_cv_`/`-cv-` for other resources. Verify carefully.

---

## 8. Quick Reference: Key Resource Identifiers

| Resource | Identifier |
|----------|-----------|
| ECS Cluster | `ANEPRBK-001` |
| ECS Service | `Booking-prod` |
| Task Definition | `Booking-latest-prod-Task:16` |
| DynamoDB Table | `inttra2_prod_booking_BookingDetail` |
| DynamoDB GSI | `INTTRA_REFERENCE_NUMBER_INDEX` |
| DynamoDB Keys | `bookingId` (HASH) + `sequenceNumber` (RANGE) |
| App Log Group | `inttra2-pr-lg-bkapi` |
| AWS Account | `642960533737` |
| AWS Profile | `642960533737_INTTRA2-QATeam` |
| Region | `us-east-1` |
