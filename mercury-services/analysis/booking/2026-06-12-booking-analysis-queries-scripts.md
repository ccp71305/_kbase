# Booking Analysis — Reusable DynamoDB Queries & Python Scripts

**Date:** 2026-06-12  
**Companion to:** [2026-06-12-booking-cvt-qa-prod-analysis.md](2026-06-12-booking-cvt-qa-prod-analysis.md)

---

## 1. DynamoDB CLI Queries

### 1.1 List All Booking Tables
```bash
aws dynamodb list-tables \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --query "TableNames[?contains(@, 'ooking')]" \
  --output json
```

### 1.2 Describe Table Schema (keys + GSIs)
```bash
aws dynamodb describe-table \
  --table-name inttra2_qa_booking_BookingDetail \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --query "Table.{KeySchema: KeySchema, GlobalSecondaryIndexes: GlobalSecondaryIndexes[].{IndexName: IndexName, KeySchema: KeySchema}}" \
  --output json
```

### 1.3 Find All Versions by InttraRef (via GSI)
```bash
# Key schema: bookingId (HASH) + sequenceNumber (RANGE)
# GSI: INTTRA_REFERENCE_NUMBER_INDEX on inttraReferenceNumber
# Replace TABLE and INTTRA_REF

aws dynamodb query \
  --table-name <TABLE> \
  --index-name INTTRA_REFERENCE_NUMBER_INDEX \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```

**Environment table mapping:**
| Environment | Table Name |
|-------------|-----------|
| QA | `inttra2_qa_booking_BookingDetail` |
| CVT | `inttra2_test_booking_BookingDetail` |
| PROD | `inttra2_prod_booking_BookingDetail` |

### 1.4 Count Versions Only (fast)
```bash
aws dynamodb query \
  --table-name <TABLE> \
  --index-name INTTRA_REFERENCE_NUMBER_INDEX \
  --key-condition-expression "inttraReferenceNumber = :ref" \
  --expression-attribute-values '{":ref": {"S": "<INTTRA_REF>"}}' \
  --select COUNT \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json
```

### 1.5 Get Full Item by Primary Key
```bash
# Use bookingId + sequenceNumber from the GSI query above
aws dynamodb get-item \
  --table-name <TABLE> \
  --key '{"bookingId": {"S": "<BOOKING_ID>"}, "sequenceNumber": {"S": "<SEQ_NUM>"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json > booking_full.json
```

### 1.6 Get Full Item and Save to File (pipe pattern)
```bash
aws dynamodb get-item \
  --table-name inttra2_qa_booking_BookingDetail \
  --key '{"bookingId": {"S": "e23f7fe4eb154cf298592d2fbdc75c78"}, "sequenceNumber": {"S": "m_1781276439310_REQUEST_2010402133"}}' \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json > booking_record.json
```

---

## 2. SQS Queue Health Check

```bash
# Check message counts for a queue
# Replace QUEUE_NAME with e.g. inttra2_qa_sqs_bk_inbound
aws sqs get-queue-attributes \
  --queue-url https://sqs.us-east-1.amazonaws.com/642960533737/<QUEUE_NAME> \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1
```

**Key queues per environment:**
| Purpose | QA | CVT | PROD |
|---------|-----|-----|------|
| BK Inbound | `inttra2_qa_sqs_bk_inbound` | `inttra2_cv_sqs_bk_inbound` | `inttra2_pr_sqs_bk_inbound` |
| Watermill BK | `inttra2_qa_sqs_watermill_bk` | `inttra2_cv_sqs_watermill_bk` | `inttra2_pr_sqs_watermill_bk` |

---

## 3. CloudWatch Logs Insights — Async Query Pattern

```bash
# Step 1: Start query (returns queryId)
QUERY_ID=$(aws logs start-query \
  --log-group-name "<LOG_GROUP>" \
  --start-time $(date -d "2026-06-12 00:00:00" +%s) \
  --end-time $(date -d "2026-06-13 00:00:00" +%s) \
  --query-string "fields @timestamp, @message | filter @message like /<PATTERN>/ | sort @timestamp asc | limit 200" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output text --query 'queryId')

# Step 2: Wait a few seconds, then get results
sleep 15
aws logs get-query-results --query-id "$QUERY_ID" \
  --profile 642960533737_INTTRA2-QATeam \
  --region us-east-1 \
  --output json > cw_results.json
```

**PowerShell variant:**
```powershell
$startTime = [int](Get-Date "2026-06-12 00:00:00Z" -UFormat %s)
$endTime = [int](Get-Date "2026-06-13 00:00:00Z" -UFormat %s)
$result = aws logs start-query `
  --log-group-name "inttra2-qa-lg-bkapi" `
  --start-time $startTime --end-time $endTime `
  --query-string "fields @timestamp, @message | filter @message like /2010402133/ | sort @timestamp asc | limit 200" `
  --profile 642960533737_INTTRA2-QATeam --region us-east-1 --output json
$queryId = ($result | ConvertFrom-Json).queryId

Start-Sleep -Seconds 15
aws logs get-query-results --query-id $queryId `
  --profile 642960533737_INTTRA2-QATeam --region us-east-1 --output json |
  Out-File cw_results.json -Encoding utf8
```

---

## 4. Python Parsing Scripts

### 4.1 Analyze DynamoDB Booking Record Format (SDK version detection)

```python
"""
Analyze a DynamoDB booking record to detect SDK version and key field formats.
Usage: python analyze_booking.py booking_record.json
"""
import json, sys

def analyze_booking(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    item = data['Item']

    print('=== TOP LEVEL KEYS ===')
    for k in sorted(item.keys()):
        val_type = list(item[k].keys())[0] if isinstance(item[k], dict) else type(item[k]).__name__
        print(f'  {k}: type={val_type}')

    print('\n=== BOOLEAN FIELDS (SDK version indicator) ===')
    for field in ['coreBooking', 'nonInttraBooking', 'splitCopy']:
        v = item.get(field, 'MISSING')
        print(f'  {field}: {json.dumps(v)}')

    # Detect SDK version
    cb = item.get('coreBooking', {})
    if 'BOOL' in cb:
        print('\n  >>> SDK VERSION: v2 (BOOL type booleans)')
    elif 'N' in cb:
        print('\n  >>> SDK VERSION: v1 (N type booleans)')

    print('\n=== AUDIT ===')
    audit = item.get('audit', {}).get('M', {})
    for k in sorted(audit.keys()):
        val = json.dumps(audit[k])
        if len(val) > 120:
            val = val[:120] + '...'
        print(f'  {k}: {val}')

    print('\n=== ENRICHED ATTRIBUTES BOOLEANS ===')
    ea = item.get('enrichedAttributes', {}).get('M', {})
    if ea.get('bookingWithMigratedParties'):
        print(f'  bookingWithMigratedParties: {json.dumps(ea["bookingWithMigratedParties"])}')
    ct = ea.get('containerTypeList', {}).get('L', [])
    if ct:
        m = ct[0].get('M', {})
        for f in ['displayFlag', 'oogFlag', 'spareIndicator']:
            if m.get(f):
                print(f'  containerTypeList[0].{f}: {json.dumps(m[f])}')

    print('\n=== KEY FIELDS ===')
    print(f'  state: {json.dumps(item.get("state", "MISSING"))}')
    print(f'  channel: {json.dumps(item.get("channel", "MISSING"))}')

    raw = json.dumps(data)
    null_count = raw.count('"NULL"')
    print(f'\n=== NULL EXPANSION ===')
    print(f'  Total NULL fields: {null_count}')

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'booking_record.json'
    analyze_booking(path)
```

### 4.2 Parse CloudWatch Logs Insights Results

```python
"""
Parse CW Logs Insights JSON results and display key lifecycle events.
Usage: python parse_cw_results.py cw_results.json [--all] [--max N]
"""
import json, sys

LIFECYCLE_KEYWORDS = [
    'Created new booking', 'Published message to topic',
    'Email processing done', 'Watermill OB sent', 'EDI/SQS OB sent',
    'Outbound processing started', 'End - Subscription',
    'Start - Subscription', 'transformer Uploaded',
    'ERROR', 'Exception', 'FATAL', 'timeout'
]

def parse_cw(path, show_all=False, max_show=50):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    status = data.get('status', 'unknown')
    results = data.get('results', [])
    print(f'Status: {status}, Total results: {len(results)}')
    print('=' * 80)

    shown = 0
    for r in results:
        msg = next((x['value'] for x in r if x['field'] == '@message'), '')
        ts = next((x['value'] for x in r if x['field'] == '@timestamp'), '')

        if show_all:
            print(f'{ts} | {msg[:250].strip()}')
            shown += 1
        else:
            for kw in LIFECYCLE_KEYWORDS:
                if kw in msg:
                    print(f'{ts} | {msg[:250].strip()}')
                    shown += 1
                    break

        if shown >= max_show:
            remaining = len(results) - max_show
            if remaining > 0:
                print(f'\n... and {remaining} more results')
            break

    print(f'\nShown: {shown}/{len(results)}')

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'cw_results.json'
    show_all = '--all' in sys.argv
    max_show = 50
    for i, arg in enumerate(sys.argv):
        if arg == '--max' and i + 1 < len(sys.argv):
            max_show = int(sys.argv[i + 1])
    parse_cw(path, show_all, max_show)
```

### 4.3 Compare Two Booking Records (cross-environment format diff)

```python
"""
Compare two DynamoDB booking records and highlight format differences.
Usage: python compare_bookings.py prod_record.json qa_record.json
"""
import json, sys

def get_type(val):
    if isinstance(val, dict):
        return list(val.keys())[0]
    return type(val).__name__

def compare(path_a, path_b, label_a='ENV_A', label_b='ENV_B'):
    with open(path_a, 'r', encoding='utf-8') as f:
        a = json.load(f)['Item']
    with open(path_b, 'r', encoding='utf-8') as f:
        b = json.load(f)['Item']

    all_keys = sorted(set(list(a.keys()) + list(b.keys())))

    print(f'{"Field":<30} {"Type in "+label_a:<15} {"Type in "+label_b:<15} {"Match?":<8}')
    print('-' * 70)

    diffs = []
    for k in all_keys:
        type_a = get_type(a[k]) if k in a else 'MISSING'
        type_b = get_type(b[k]) if k in b else 'MISSING'
        match = '✅' if type_a == type_b else '❌'
        print(f'{k:<30} {type_a:<15} {type_b:<15} {match:<8}')
        if type_a != type_b:
            diffs.append((k, type_a, type_b))

    # Boolean comparison
    print(f'\n=== BOOLEAN FIELDS ===')
    for field in ['coreBooking', 'nonInttraBooking', 'splitCopy']:
        va = json.dumps(a.get(field, 'MISSING'))
        vb = json.dumps(b.get(field, 'MISSING'))
        match = '✅' if va == vb else '❌'
        print(f'  {field}: {label_a}={va}  {label_b}={vb}  {match}')

    # NULL counts
    null_a = json.dumps(a).count('"NULL"')
    null_b = json.dumps(b).count('"NULL"')
    print(f'\n=== NULL COUNTS ===')
    print(f'  {label_a}: {null_a}')
    print(f'  {label_b}: {null_b}')

    if diffs:
        print(f'\n=== {len(diffs)} TYPE DIFFERENCES ===')
        for k, ta, tb in diffs:
            print(f'  {k}: {label_a}={ta}, {label_b}={tb}')

if __name__ == '__main__':
    path_a = sys.argv[1]
    path_b = sys.argv[2]
    label_a = sys.argv[3] if len(sys.argv) > 3 else 'PROD'
    label_b = sys.argv[4] if len(sys.argv) > 4 else 'QA'
    compare(path_a, path_b, label_a, label_b)
```

### 4.4 Categorize CloudWatch Errors

```python
"""
Categorize CW error results by type.
Usage: python categorize_errors.py cw_errors.json [--show-non-404]
"""
import json, sys

def categorize(path, show_non_404=False):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    results = data.get('results', [])
    print(f'Status: {data.get("status")}, Total: {len(results)}')

    cats = {}
    non_404 = []
    for r in results:
        msg = next((x['value'] for x in r if x['field'] == '@message'), '')
        ts = next((x['value'] for x in r if x['field'] == '@timestamp'), '')

        if 'NotFoundException' in msg:
            cats['NotFoundException (404)'] = cats.get('NotFoundException (404)', 0) + 1
        elif 'timeout' in msg.lower() or 'timed out' in msg.lower():
            cats['Timeout'] = cats.get('Timeout', 0) + 1
            non_404.append((ts, msg))
        elif 'ERROR' in msg:
            cats['ERROR'] = cats.get('ERROR', 0) + 1
            non_404.append((ts, msg))
        elif 'Exception' in msg:
            cats['Exception'] = cats.get('Exception', 0) + 1
            non_404.append((ts, msg))
        else:
            cats['Other'] = cats.get('Other', 0) + 1
            non_404.append((ts, msg))

    print('\n=== CATEGORIES ===')
    for k, v in sorted(cats.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')

    if show_non_404 and non_404:
        print(f'\n=== NON-404 ENTRIES ({len(non_404)}) ===')
        for ts, msg in non_404[:30]:
            print(f'  {ts} | {msg[:220].strip()}')

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'cw_errors.json'
    show = '--show-non-404' in sys.argv
    categorize(path, show)
```

### 4.5 Batch SQS Health Check (PowerShell)

```powershell
# Check all booking SQS queues across environments
$profile = "642960533737_INTTRA2-QATeam"
$region = "us-east-1"
$acct = "642960533737"

$queues = @(
    @{name="inttra2_qa_sqs_bk_inbound"; env="QA"},
    @{name="inttra2_cv_sqs_bk_inbound"; env="CVT"},
    @{name="inttra2_pr_sqs_bk_inbound"; env="PROD"},
    @{name="inttra2_qa_sqs_watermill_bk"; env="QA"},
    @{name="inttra2_cv_sqs_watermill_bk"; env="CVT"},
    @{name="inttra2_pr_sqs_watermill_bk"; env="PROD"}
)

foreach ($q in $queues) {
    $url = "https://sqs.$region.amazonaws.com/$acct/$($q.name)"
    $result = aws sqs get-queue-attributes `
        --queue-url $url `
        --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible `
        --profile $profile --region $region --output json 2>&1
    $parsed = $result | ConvertFrom-Json
    $msgs = $parsed.Attributes.ApproximateNumberOfMessages
    $inflight = $parsed.Attributes.ApproximateNumberOfMessagesNotVisible
    Write-Host "$($q.env) $($q.name): msgs=$msgs inflight=$inflight"
}
```

### 4.6 Batch Lambda Error Check (PowerShell)

```powershell
$startTime = [int](Get-Date "2026-06-12 00:00:00Z" -UFormat %s)
$endTime = [int](Get-Date "2026-06-13 00:00:00Z" -UFormat %s)
$profile = "642960533737_INTTRA2-QATeam"

$lambdas = @(
    "inttra2-qa-lambda-bookingdetail-S3ArchiveLambda",
    "inttra2-qa-lambda-bookingdetail-ElasticsearchLambda",
    "inttra2-qa-lambda-bookingdetail-SendLambda",
    "inttra2-pr-lambda-bookingdetail-S3ArchiveLambda",
    "inttra2-pr-lambda-bookingdetail-ElasticsearchLambda",
    "inttra2-pr-lambda-bookingdetail-SendLambda"
)

foreach ($l in $lambdas) {
    $qid = aws logs start-query `
        --log-group-name "/aws/lambda/$l" `
        --start-time $startTime --end-time $endTime `
        --query-string "fields @timestamp, @message | filter @message like /(?i)ERROR|Exception|FATAL|timeout/ | sort @timestamp desc | limit 50" `
        --profile $profile --region us-east-1 `
        --output text --query queryId 2>&1
    Write-Host "Started $l : $qid"
}
# Wait then get results:
# aws logs get-query-results --query-id <ID> --profile $profile --region us-east-1
```

---

## 5. Quick Reference — Environment Prefixes

| Environment | DynamoDB prefix | S3/Lambda/CW prefix | SQS underscore |
|------------|----------------|---------------------|----------------|
| QA | `inttra2_qa_booking_` | `inttra2-qa-` | `inttra2_qa_` |
| CVT | `inttra2_test_booking_` | `inttra2-cv-` | `inttra2_cv_` |
| PROD | `inttra2_prod_booking_` | `inttra2-pr-` | `inttra2_pr_` |

> **Note:** CVT uses `_test_` for DynamoDB but `-cv-` / `_cv_` for other resources.
