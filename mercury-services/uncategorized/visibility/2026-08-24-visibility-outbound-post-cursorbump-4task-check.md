# Visibility Outbound — Post cursor-bump / 4-task restart check (2026-08-24)

- **When:** 2026-08-25 ~01:29 UTC (2026-08-24 ~21:29 EDT)
- **Context:** After the ION-16663 Fix A deploy (17:33 EDT), the team (a) applied a **MySQL update to advance
  the outbound cursors** so old records are no longer picked, and (b) **scaled the processor back up to 4
  tasks** (from 0). This is a read-only verification that processing is happening and old records are not
  being reprocessed.
- **AWS access:** read-only SSO profile `642960533737_INTTRA2-QATeam` (CloudWatch Logs, ECS describe, SQS
  get-queue-attributes). No scans, no writes. Exact CLI in §5.

---

## 1. Verdict

- ✅ **Processing is happening.** 4/4 tasks running; **426** `DynamoDB query for IPF …` lines in the last
  20 min. Previously-frozen IPFs **5811 and 5857 are actively querying again**.
- ✅ **The cursor bump worked — old records are no longer picked.** **`Could not find inbound transaction` =
  0** over the last 20 min (was the dominant error before). Sampled failing IPF **4452 now has a recent cursor
  `lastTransactionCreationDatetime = 1787404045449` (≈ 2026-08-24)**, not a 2023 value.
- ⚠️ **Throttling still persists even at 4 tasks.** **142** `ProvisionedThroughputExceededException` and
  **177** `Failed to retrieve ContainerEventOutbound` (silent-skip) in 20 min; query latency badly inflated
  (IPF 5857 query took **53,394 ms**). Capacity is still the bottleneck — this is an operational/throughput
  issue, **not** a correctness/old-record issue.
- ⚠️ **Residual fatal errors are no longer orphans.** **26** `Failed to process SQS message` in 20 min, now
  caused by `software.amazon.awssdk.core.exception.AbortedException` (SDK request aborted — consistent with
  api-call timeouts under the slow/throttled reads), not by missing inbound events.

**Bottom line:** the correctness goal is met — processing resumed on **recent** records with **zero orphan
lookups**. The remaining problems are **capacity-driven** (throttling → 53 s queries, silent skips, occasional
aborted-request poison), exactly as predicted in the main checkout doc (§19–§21).

---

## 2. Evidence (last ~20 min, 4 tasks)

### 2.1 Processor state
```
VisibilityOutbound-prod (cluster ANEPRVIS-001): Running 4 / Desired 4
PRIMARY deployment created 2026-08-24 21:23:20 EDT
```

### 2.2 Log signal counts (log group `inttra2-ecs-logs`, stream prefix `VisibilityOutbound-latest-prod`)
| Signal | Count (20 min) | Meaning |
|---|---|---|
| `DynamoDB query for IPF` | **426** | processing active |
| `Could not find inbound transaction` | **0** | **old/orphaned records no longer picked** (cursor bump worked) |
| `Failed to process SQS message` | **26** | fatal batch aborts — now `AbortedException`, not orphans |
| `ProvisionedThroughput` | **142** | DynamoDB read throttling still occurring at 4 tasks |
| `Failed to retrieve ContainerEventOutbound` | **177** | outbound query throttled/timed-out → DAO returns empty → silent skip |

### 2.3 Previously-frozen IPFs now processing
```
INFO ContainerEventOutboundDao: DynamoDB query for IPF 5811 returned 1000 records in 5631 ms   (01:28:03 UTC)
INFO ContainerEventOutboundDao: DynamoDB query for IPF 5857 returned 1000 records in 53394 ms  (01:30:16 UTC)
```
(5857's 53 s query time is the throttle/retry latency, not normal.)

### 2.4 Sample residual fatal (cause is no longer an orphan)
```
ERROR OutboundMultiTransactionProcessor: Failed to process SQS message
  {"integrationProfileFormatId":4452,"transactionCount":1822,
   "lastExecutionDatetime":1787577740452,"lastTransactionCreationDatetime":1787404045449,  <- RECENT cursor
   "locked":1,...}, Outbound IPF: 4452
software.amazon.awssdk.core.exception.AbortedException: null (SDK Attempt Count: 1)
```
Cursor `1787404045449` ≈ 2026-08-24 (recent) → confirms the bump; the failure is an SDK `AbortedException`
(request aborted under load), which still propagates → poison → DLQ (per main doc §20).

### 2.5 Queue / DLQ depths (note the trend)
| Queue | Depth now | Earlier (pre-restart) |
|---|---|---|
| `inttra2_pr_sqs_ce_outbound_ipf` (IPF work) | **126,727** | 83,672 (poller keeps enqueuing due IPFs) |
| `inttra2_pr_sqs_ce_outbound_ipf_dlq` | **264,749** | 264,749 (≈ unchanged) |
| `inttra2_pr_sqs_ce_outbound` (single-transaction **input** queue) | **656,673** | 554,403 |

The two `ce_outbound*` queues are the outbound service's **two input work queues** (not output/delivery):
`…_ce_outbound_ipf` = IPF/threshold **batch** path (`multiTransactionSqsProcessConfig` →
`OutboundMultiTransactionProcessor` — the ION-16663 path); `…_ce_outbound` = **single-transaction** real-time
path (`singleTransactionSqsProcessConfig` → `OutboundSingleTransactionProcessor`). Both backed up while the
service was scaled to 0 (poller + matcher kept producing) and drain once tasks run. Generated outbound output
goes to **S3** (`inttra2-pr-gis-delivery`) and/or the `outboundTransformerQueue`
(`inttra2_pr_sqs_transformer_ce`) — **not** to `…_ce_outbound`.

---

## 3. Interpretation

1. **Cursor update = success.** No orphan lookups (`Could not find inbound transaction` = 0) and recent cursor
   values → old records below the 400-day inbound TTL are no longer being read. This is the intended effect
   and it removes the poison-loop root cause **for the bumped profiles**.
2. **Capacity is now the limiter, not correctness.** Even at 4 tasks the DynamoDB reads throttle (142
   `ProvisionedThroughputExceededException`, 177 empty-result skips, 53 s query latencies). Per the main
   checkout doc §19.7, the tables autoscale only to 2000 RCU and the inbound `container_events` table is near
   its ceiling; 4 tasks still exceed that at cold start.
3. **Residual poison is transient, not orphan.** The 26 fatals are `AbortedException` (aborted requests under
   load), consistent with api-call timeouts during throttling — they still DLQ the IPF (§20), so they add a
   little to the DLQ but are not the old orphan class.

---

## 4. Recommendations

1. **Relieve throttling** so the drain actually makes progress and stops generating aborted-request poison:
   put the outbound (and near-cap inbound) tables on **on-demand** for the drain, or raise their RCU max well
   above 2000 and pre-warm; and/or switch the outbound query to **eventually-consistent** reads. (Main doc
   §19.7.)
2. **Keep concurrency modest** (4 tasks is reasonable) until capacity is raised — but monitor inbound-table
   throttle metrics, because inbound throttling poisons to DLQ (§20).
3. **Do not implement "skip orphan."** Per §22 of the main doc, skipping drops the customer's outbound; the
   correct path is keeping outbound current (now achieved via the bump) + making the outbound row
   self-sufficient + recovering any already-orphaned rows.
4. **Plan the DLQ redrive** (264,749) only after capacity is raised — redrive is itself heavy read load.
5. **Watch the transaction queue** (`…_ce_outbound`, 656k and rising) and its sender throughput.

---

## 5. SNS errors & AbortedException DLQ behaviour (post-restart, last ~25 min)

### 5.1 Counts
| Signal | Count (25 min) |
|---|---|
| `SNS_Failed_AFTER_RETRY` | **740** |
| `AbortedException` | **909** |
| `Failed to process SQS message` (fatal) | **26** |
| `Moving SQS Message … to DLQ` | **27** |

### 5.2 SNS errors
- **740 `SNS_Failed_AFTER_RETRY`** in 25 min (up sharply from ~100 during the 8-task burst).
- **Cause:** `SdkInterruptedException` / `AbortedException` from `ApiCallTimeoutTrackingStage` — the SNS
  publish calls are **interrupted / timing out** under the overload (same root cause as the 53 s query
  latencies).
- **What they are:** telemetry / workflow observability events (`category:system`, `type:closeRun`) emitted by
  `SnsEventPublisher` — **not** the customer's outbound transaction. Impact = **lost observability events**;
  they are logged-and-swallowed after retry and do **not** poison the batch (otherwise there would be ~740
  fatals, not 26).

### 5.3 Does `AbortedException` go to the DLQ? — depends where it occurs
909 `AbortedException` but only **26** fatal `Failed to process SQS message` → **27** `Moving SQS Message … to
DLQ`. The split:

| Where the abort occurs | Handling | DLQ? |
|---|---|---|
| **SNS telemetry publisher** (`SnsEventPublisher`) — most of them | caught → logged as `SNS_Failed_AFTER_RETRY` | **No** (telemetry event lost) |
| **DAO outbound query** (`getUnprocessedTransactions`) | caught by the DAO → returns empty | **No** (silent skip) |
| **Critical outbound path** (batch generation / send reaching `process()`) | propagates → `Failed to process SQS message` | **Yes** — 26 ≈ 27 "Moving to DLQ" confirms it |

So **an `AbortedException` on the critical outbound path *does* go to the DLQ** (app-managed, on first failure —
main doc §20); aborts in the telemetry/query paths do not. Because these are **transient overload aborts**
(not orphans), the DLQ'd batches should reprocess successfully after capacity is relieved (redrive).

> Both the SNS failures and the critical-path aborts are downstream of the **same capacity/throttling
> overload** — relieving throttling (on-demand / higher RCU / eventually-consistent reads, §19.7 of the main
> doc) should remove the bulk of them.

---

## 5b. Follow-up snapshot (~01:42 UTC / 21:42 EDT) — caught up, throttling cleared

A second check ~13 min later shows a **major improvement** (4 tasks, last 10 min):

| Signal | Last 10 min |
|---|---|
| `DynamoDB query for IPF` | **12,340** (vs 426 in the earlier 20-min window) |
| `ProvisionedThroughput` (throttle) | **0** |
| `Failed to process SQS message` (fatal) | **0** |
| `Could not find inbound transaction` (orphan) | **0** |
| `Moving SQS Message … to DLQ` | **0** |

- **Throttling cleared** — query latencies back to normal (4–12 ms empty, ~1.8 s for a full 1000-row page, vs
  53 s earlier). Autoscaling caught up / load normalised.
- **IPF work queue drained to 0** (was 126,727) — processor has **caught up**; many queries now
  `returned 0 records` (profiles up to date).
- **Transaction queue draining:** `inttra2_pr_sqs_ce_outbound` **350,193** (down from 656,673) — outbound
  transactions being sent downstream.
- **Cursor bump still holding** — zero orphan lookups.
- **Leftover:** IPF DLQ **264,749** (unchanged historical poison) — needs a **redrive** once stability is
  confirmed.

**High-level: processing is running cleanly and fast — no throttling/poison/orphans, the live IPF backlog is
cleared, and outbound transactions are flowing out.**

### 5c. Third snapshot (~01:48 UTC / 21:48 EDT) — steady & nearly drained

| Signal (last 10 min) | Value |
|---|---|
| `DynamoDB query for IPF` | 6,200 |
| throttle / fatal / orphan / DLQ-send | **0 / 0 / 0 / 0** |
| `SNS_Failed_AFTER_RETRY` | **0** (was 740 — cleared once throttling stopped) |

Queues: IPF work **0** (caught up), transaction queue **70,325** (down from 350,193 → 656,673), IPF DLQ
264,749 (unchanged historical). 4/4 tasks. **Fully recovered and steady; only the historical DLQ redrive
remains.**

### 5d. Fourth snapshot (~01:59 UTC / 21:59 EDT) — backlog fully drained

| Signal (last ~11 min) | Value |
|---|---|
| `DynamoDB query for IPF` | 493 (low — little left to do) |
| throttle / fatal / orphan / DLQ-send / SNS-fail | **0 / 0 / 0 / 0 / 0** |

Queues: IPF work **0**, transaction queue **0** (fully drained, from 70,325 → 656,673 earlier), IPF DLQ
264,749 (unchanged historical). **Complete recovery — both live queues at 0, zero errors; only the historical
DLQ redrive remains.**

### 5e. Fifth snapshot (~02:56 UTC / 22:56 EDT) — stable/steady for ~1 hr

Activity **since the last checkpoint (01:59 UTC, ~57 min elapsed)**. (SSO token had expired; re-authenticated
with `aws sso login` before the check.)

| Log signal (last ~57 min) | Count |
|---|---|
| `DynamoDB query for IPF` | 2,017 (steady low-level polling; little backlog to work) |
| `Could not find inbound transaction` (orphan) | 0 |
| `Failed to process SQS message` (fatal) | 0 |
| `ProvisionedThroughput` (throttle) | 0 |
| `Moving SQS Message` (DLQ send) | 0 |
| `SNS_Failed_AFTER_RETRY` | 0 |

Queue depths now (Visible / InFlight), by name:
| Queue | Role | Now |
|---|---|---|
| `inttra2_pr_sqs_ce_outbound_ipf` | IPF/threshold **batch input** (→ multi processor) | **0 / 0** (caught up) |
| `inttra2_pr_sqs_ce_outbound` | **single-transaction input** (→ single processor) | **0 / 0** (caught up) |
| `inttra2_pr_sqs_transformer_ce` | **generated output** (→ transformer) | 0 / 5 (flowing, not backing up) |
| `inttra2_pr_sqs_ce_outbound_ipf_dlq` | batch dead-letter (historical poison) | **264,749** (unchanged — needs redrive) |
| `inttra2_pr_sqs_ce_outbound_dlq` | single-transaction dead-letter | 4,639 (≈ unchanged) |

ECS: **4/4 tasks**. **Steady state for ~1 hour: both live input queues stay at 0, generated output is flowing
to the transformer queue, zero errors. Only the historical batch DLQ (264,749) remains for redrive.**

### 5f. Sixth snapshot (~03:19 UTC / 23:19 EDT) — scaled up to 8 tasks, clean

Team **scaled the outbound processor from 4 → 8 tasks** (deployment 2026-08-24 23:14 EDT). Last 15 min:

| Log signal | Count |
|---|---|
| `DynamoDB query for IPF` | 444 |
| orphan / fatal / throttle / DLQ-send / SNS-fail | **0 / 0 / 0 / 0 / 0** |

Queues (Visible / InFlight): `…_ce_outbound_ipf` **0 / 0**, `…_ce_outbound` **0 / 6**,
`…_transformer_ce` 0 / 4, `…_ce_outbound_ipf_dlq` **264,749** (unchanged), `…_ce_outbound_dlq` 4,639. ECS **8/8**.

**Clean scale-up — notably ZERO throttling**, unlike the *first* 8-task burst (287
`ProvisionedThroughputExceededException`). Reason: the backlog is already drained and cursors are recent, so
8 tasks have little to do (444 queries ≈ mostly polling that returns 0 records).

> ⚠️ **Caveat:** this clean result holds *because there is no backlog*. **Redriving the historical batch DLQ
> (264,749) will re-introduce the heavy 1000-page reads + inbound `findById` load that throttled the tables
> before** — relieve capacity (on-demand / raise RCU per §19.7) **before** the redrive.

### 5g. Seventh snapshot (overnight, ~12:44 UTC / 08:44 EDT 2026-08-25) — steady & clean for ~9½ h

Overnight progress check, **~9½ hours after §5f** (8-task scale-up at 23:14 EDT). No further deployments —
**same PRIMARY deployment (23:14 EDT), ECS 8/8** the whole time. Log signals over the last 20 min:

| Log signal (last ~20 min) | Count |
|---|---|
| `DynamoDB query for IPF` | 541 (steady polling; little backlog to work) |
| `Could not find inbound transaction` (orphan) | **0** |
| `Failed to process SQS message` (fatal) | **0** |
| `ProvisionedThroughput` (throttle) | **0** |
| `Failed to retrieve ContainerEventOutbound` (silent-skip) | **0** |
| `AbortedException` | **0** |
| `Moving SQS Message` (DLQ send) | **0** |
| `SNS_Failed_AFTER_RETRY` | **0** |

Queues (Visible / InFlight), by name:
| Queue | Role | §5f (03:19Z) | Now (12:44Z) |
|---|---|---|---|
| `inttra2_pr_sqs_ce_outbound_ipf` | IPF/threshold **batch input** | 0 / 0 | **0 / 5** (caught up, flowing) |
| `inttra2_pr_sqs_ce_outbound` | **single-transaction input** | 0 / 6 | **0 / 8** (caught up, flowing) |
| `inttra2_pr_sqs_transformer_ce` | **generated output** | 0 / 4 | 0 / 9 (flowing, not backing up) |
| `inttra2_pr_sqs_ce_outbound_ipf_dlq` | batch dead-letter (historical poison) | 264,749 | **263,629** (≈ unchanged; −1,120) |
| `inttra2_pr_sqs_ce_outbound_dlq` | single-transaction dead-letter | 4,639 | 4,639 (unchanged) |

**Verdict:** stable steady-state for ~9½ hours — both live input queues at 0 visible, output flowing to the
transformer, **zero orphans / fatals / throttling / silent-skips / DLQ-sends / SNS failures**. The historical
batch DLQ is essentially unchanged at **263,629** (a trivial −1,120 drift, **not** a redrive — the redrive
still hasn't been run, and the §5f capacity caveat still applies before it is). See §8b for the per-IPF
backlog progression over the same overnight window.

## 6. AWS CLI queries used (read-only)

> Profile `642960533737_INTTRA2-QATeam`, region `us-east-1`. `$WIN` = epoch-ms start time
> (e.g. `[DateTimeOffset]::UtcNow.AddMinutes(-20).ToUnixTimeMilliseconds()`).

```powershell
# 1) Processor task count / current deployment
aws ecs describe-services --cluster ANEPRVIS-001 --services VisibilityOutbound-prod `
  --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --query "services[0].{Running:runningCount,Desired:desiredCount,Deployments:deployments[].{Created:createdAt,Running:runningCount}}" --output json

# 2) Log signal counts over the last 20 min (repeat --filter-pattern per signal)
#    log group: inttra2-ecs-logs   stream prefix: VisibilityOutbound-latest-prod
aws logs filter-log-events --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --log-group-name inttra2-ecs-logs --log-stream-name-prefix VisibilityOutbound-latest-prod `
  --start-time $WIN --filter-pattern '"DynamoDB query for IPF"'            --query "length(events)" --output json
#   ... repeat with: '"Could not find inbound transaction"'
#                    '"Failed to process SQS message"'
#                    '"ProvisionedThroughput"'
#                    '"Failed to retrieve ContainerEventOutbound"'
#                    '"SNS_Failed_AFTER_RETRY"'
#                    '"AbortedException"'
#                    '"Moving SQS Message"'      (confirms DLQ sends)

# 2b) Full message samples to identify causes (AbortedException origin, SNS failure cause)
aws logs filter-log-events --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --log-group-name inttra2-ecs-logs --log-stream-name-prefix VisibilityOutbound-latest-prod `
  --start-time $WIN --filter-pattern '"AbortedException"'      --query "events[0].message" --output text
aws logs filter-log-events --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --log-group-name inttra2-ecs-logs --log-stream-name-prefix VisibilityOutbound-latest-prod `
  --start-time $WIN --filter-pattern '"SNS_Failed_AFTER_RETRY"' --query "events[0].message" --output text

# 3) Trace previously-frozen IPFs (5811 / 5857)
aws logs filter-log-events --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --log-group-name inttra2-ecs-logs --log-stream-name-prefix VisibilityOutbound-latest-prod `
  --start-time $WIN --filter-pattern '?"IPF 5811" ?"IPF: 5811" ?"IPF 5857" ?"IPF: 5857"' `
  --query "events[0:6].message" --output json

# 4) Sample the cause of a current fatal (to confirm it is not an orphan)
aws logs filter-log-events --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
  --log-group-name inttra2-ecs-logs --log-stream-name-prefix VisibilityOutbound-latest-prod `
  --start-time $WIN --filter-pattern '"Failed to process SQS message"' `
  --query "events[0].message" --output text

# 5) Current queue / DLQ depths
foreach ($q in @("inttra2_pr_sqs_ce_outbound_ipf","inttra2_pr_sqs_ce_outbound_ipf_dlq","inttra2_pr_sqs_ce_outbound")) {
  aws sqs get-queue-attributes `
    --queue-url "https://sqs.us-east-1.amazonaws.com/642960533737/$q" `
    --attribute-names ApproximateNumberOfMessages `
    --profile 642960533737_INTTRA2-QATeam --region us-east-1 `
    --query "Attributes.ApproximateNumberOfMessages" --output text
}
```

*All interactions read-only (CloudWatch Logs `filter-log-events`, ECS `describe-services`, SQS
`get-queue-attributes`). No DynamoDB scans; no writes.*

---

## 7. Progress-check runbook — step-by-step with descriptions

A copy-paste guide to re-run this health check at any time. Read-only throughout. PowerShell syntax
(backtick line-continuation); on bash, replace `` ` `` with `\` and `$env:` with shell vars.

### Step 0 — Prerequisites (one time per shell)
```powershell
# Authenticate the SSO profile (opens browser once); then set common variables.
aws sso login --profile 642960533737_INTTRA2-QATeam
$P  = "642960533737_INTTRA2-QATeam"          # read-only QA/prod SSO profile
$R  = "us-east-1"
$LG = "inttra2-ecs-logs"                       # ECS log group for the outbound service
$SP = "VisibilityOutbound-latest-prod"         # log-stream prefix (this service's tasks)
$WIN = [DateTimeOffset]::UtcNow.AddMinutes(-10).ToUnixTimeMilliseconds()   # look-back window (10 min)
```
*Description:* logs you in and sets the profile/region/log-group/stream-prefix plus a `$WIN` epoch-ms
start-time. Widen the window by changing `-10` (e.g. `-30`).

### Step 1 — Is the processor running? (ECS)
```powershell
aws ecs describe-services --cluster ANEPRVIS-001 --services VisibilityOutbound-prod --profile $P --region $R `
  --query "services[0].{Running:runningCount,Desired:desiredCount}" --output json
```
*Description:* confirms how many tasks are up. **Healthy:** `Running == Desired` (e.g. 4/4). `0/0` means the
service is stopped.

### Step 2 — Is processing happening? (the fix's fingerprint log line)
```powershell
aws logs filter-log-events --profile $P --region $R --log-group-name $LG --log-stream-name-prefix $SP `
  --start-time $WIN --filter-pattern '"DynamoDB query for IPF"' --query "length(events)" --output json
```
*Description:* counts the `ContainerEventOutboundDao: DynamoDB query for IPF … returned N records` line, which
only exists in the fixed build. **Healthy:** a positive number = the fixed code is live and querying. `0` over
a live window = nothing processing (idle or stopped).

### Step 3 — Are there errors? (run once per pattern, compare counts)
```powershell
foreach ($pat in @(
    '"Could not find inbound transaction"',       # orphaned inbound (old records being picked)  -> want 0
    '"Failed to process SQS message"',            # fatal batch abort -> poison -> DLQ            -> want 0
    '"ProvisionedThroughput"',                    # DynamoDB read throttling                      -> want 0
    '"Failed to retrieve ContainerEventOutbound"',# query throttled/timed-out -> silent skip      -> want low/0
    '"Moving SQS Message"',                       # app sent a message to the DLQ                 -> want 0
    '"SNS_Failed_AFTER_RETRY"'                    # telemetry SNS publish failures (overload)     -> want 0
)) {
  $c = (aws logs filter-log-events --profile $P --region $R --log-group-name $LG --log-stream-name-prefix $SP `
        --start-time $WIN --filter-pattern $pat --query "length(events)" --output json | Out-String).Trim()
  Write-Output ("{0,-42} -> {1}" -f $pat, $c)
}
```
*Description & how to read:*
- `Could not find inbound transaction` **> 0** → old/orphaned records are being picked (cursor not advanced /
  bump not applied). **Want 0.**
- `Failed to process SQS message` **> 0** → batches are being poisoned to the DLQ. **Want 0.**
- `ProvisionedThroughput` **> 0** → DynamoDB throttling (capacity too low / cold-start spike). **Want 0.**
- `Failed to retrieve ContainerEventOutbound` **> 0** → query throttled/timed-out; DAO returns empty → silent
  skip (no progress that cycle). **Want low/0.**
- `Moving SQS Message` **> 0** → messages being DLQ'd (should track the fatal count). **Want 0.**
- `SNS_Failed_AFTER_RETRY` **> 0** → telemetry SNS publishing failing (usually an overload symptom). **Want 0.**

### Step 4 — Backlog trend (SQS depths)
```powershell
foreach ($q in @("inttra2_pr_sqs_ce_outbound_ipf",      # IPF/threshold BATCH input queue (poller -> multi processor)
                 "inttra2_pr_sqs_ce_outbound_ipf_dlq",  # IPF batch dead-letter queue (poison/parked)
                 "inttra2_pr_sqs_ce_outbound")) {        # SINGLE-transaction input queue (matcher -> single processor)
  $d = (aws sqs get-queue-attributes --queue-url "https://sqs.us-east-1.amazonaws.com/642960533737/$q" `
        --attribute-names ApproximateNumberOfMessages --profile $P --region $R `
        --query "Attributes.ApproximateNumberOfMessages" --output text | Out-String).Trim()
  Write-Output ("{0,-40} = {1}" -f $q, $d)
}
```
*Description & how to read:* run it a few times over several minutes and watch the **trend**.
- `…_ipf` → **0 / falling** = processor keeping up / caught up. Rising = falling behind.
- `…_ce_outbound` → **falling** = single-transaction input queue being consumed. Rising = the single processor
  is falling behind. (Generated output goes to S3 / the transformer queue, not here.)
- `…_ipf_dlq` → the parked/poison backlog; only clears via an explicit **redrive** (do this after fixes +
  capacity are confirmed).

### Step 5 — (Optional) diagnose a specific error or IPF
```powershell
# Full text + stack of the latest fatal, to see the actual cause (orphan vs throttle vs AbortedException)
aws logs filter-log-events --profile $P --region $R --log-group-name $LG --log-stream-name-prefix $SP `
  --start-time $WIN --filter-pattern '"Failed to process SQS message"' --query "events[0].message" --output text

# Trace one or more IPFs (e.g. previously-stuck 5811 / 5857) and read their cursor + query timing
aws logs filter-log-events --profile $P --region $R --log-group-name $LG --log-stream-name-prefix $SP `
  --start-time $WIN --filter-pattern '?"IPF 5811" ?"IPF: 5811" ?"IPF 5857" ?"IPF: 5857"' `
  --query "events[0:6].message" --output json
```
*Description:* the first prints one full stack trace (identify the exception class + origin); the second traces
named IPFs — check that `lastTransactionCreationDatetime` in any error payload is **recent** (not a years-old
value) and that query times are low (throttle inflates them to tens of seconds).

### Quick verdict
**Healthy** = Step 1 `Running==Desired`, Step 2 count **> 0**, all Step 3 counts **0** (or only low
`Failed to retrieve…`), Step 4 `…_ipf` at/heading to **0** and `…_ce_outbound` falling. **Only** the
`…_ipf_dlq` remaining is expected until it is redriven.

---

## 8. Large-backlog IPF progression (MySQL `OutboundThreshold.transactionCount`)

Some IPFs carry a large **per-profile backlog in MySQL** (`OutboundThreshold.transactionCount`), independent of
the SQS queue depth — the processor drains each profile in pages of ≤1000 (`RESULT_SIZE_LIMIT`) per cycle. The
poller logs `Sending IPF ID <id> … transactionCount = N` every cycle, so `transactionCount` can be traced over
time from the **prod poller lambda** log group `/aws/lambda/inttra2-pr-lambda-visibility-outbound-poller`
(no MySQL access needed).

Progression across the 4-task period (restart ~01:23Z) and the 8-task period (restart ~03:14Z):

| IPF | ~01:20Z (pre-4-task) | ~03:14Z (8-task start) | 03:30Z | 4-task Δ | 8-task Δ (16 min) | Status |
|---|---|---|---|---|---|---|
| **4486** | 568,309 | 665,095 | 661,177 | **+96,786 (grew)** | −3,918 | draining very slowly (huge inflow) |
| **5795** | 197,756 | 203,453 | 196,068 | +5,697 (grew) | −7,385 | now draining |
| **5793** | 194,761 | 197,715 | 190,325 | +2,954 (grew) | −7,390 | now draining |
| **5792** | 89,900 | 65,758 | 58,071 | −24,142 | −7,687 | draining |
| **5695** | 69,542 | 32,003 | 24,756 | −37,539 | −7,247 | draining |
| **5605** | 44,495 | 11,494 | 3,887 | −33,001 | −7,607 | nearly clear |
| **5801** | 41,464 | 2,734 | **128** | −38,730 | −2,606 | ~cleared |

### Findings
1. **The 8-task scale-up helped the big IPFs.** During the 4-task period the three largest (4486, 5795, 5793)
   were **growing** — starved of cycles while 4 tasks drained the broad multi-IPF backlog. After 8 tasks (and
   the broad backlog cleared), **all are net-draining**.
2. **Per-IPF drain is batch-capped (~1000 records/cycle).** The medium IPFs all drain at a near-uniform
   **~7,200–7,700 per 16 min** — that is the `RESULT_SIZE_LIMIT` cap, not the task count. More tasks
   parallelise across *different* IPFs and give each big IPF a cycle more often, but a **single IPF cannot
   exceed the batch cap** (its threshold is locked while one worker processes it).
3. **4486 is the outlier to watch.** Biggest (661k) and highest-inflow → net drain only ~245/min (−3,918 in
   16 min) ⇒ ~**45 hours** to clear at this rate, and sensitive to inflow spikes. Adding more tasks will not
   speed it up; it needs a **higher per-IPF batch limit** (raise `RESULT_SIZE_LIMIT` / `transactionsPerFile`)
   or investigation into why its inflow is so high.
4. **Small/medium backlogs clearing well** — 5801 essentially done (128), 5605 nearly (3,887), the rest
   trending down.

### CLI methodology & commands (how the table above was built)

**The core insight:** `transactionCount` lives in MySQL (`OutboundThreshold`), which this read-only AWS profile
**cannot** query — but the **poller logs it every cycle**, so the value can be reconstructed as a time series
from CloudWatch Logs. The poller emits one line per IPF per run:
```
INFO ... VisibilityOutboundPoller: Sending IPF ID 4486 to SQS, transactionCount = 665095,
     lastExecution = 1787... ( ... ) -> exceed execution period: true
```
The poller runs in a **Lambda** (not the ECS service), so its logs are in a **different** group:
`/aws/lambda/inttra2-pr-lambda-visibility-outbound-poller` (prod). The plan is: pull every `Sending IPF ID
<id>` line over the window, extract `transactionCount = N` with its timestamp, sort, and read off three
checkpoints (pre-4-task, at-8-task, now).

**Step 1 — set variables & the window start.** The window begins just before the 4-task restart so the first
sample reflects the pre-restart backlog. Times are UTC epoch-milliseconds (what `--start-time` expects).
```powershell
$P   = "642960533737_INTTRA2-QATeam"
$R   = "us-east-1"
$PLG = "/aws/lambda/inttra2-pr-lambda-visibility-outbound-poller"   # POLLER lambda log group (not the ECS one)
$start = [DateTimeOffset]::Parse("2026-08-25T01:20:00Z").ToUnixTimeMilliseconds()   # ~3 min before 4-task restart
$ipfs  = @("4486","5795","5793","5792","5695","5605","5801")        # the backlogged IPFs to trace
```

**Step 2 — pull, parse, and summarise per IPF.**
```powershell
foreach ($id in $ipfs) {
  # (a) Fetch all poller lines mentioning this IPF over the window. filter-pattern "IPF ID <id>" narrows
  #     server-side so we only download this profile's lines. --query returns just timestamp + message.
  $raw = (aws logs filter-log-events --profile $P --region $R --log-group-name $PLG `
            --start-time $start --filter-pattern "`"IPF ID $id`"" `
            --query "events[].{t:timestamp,m:message}" --output json | Out-String)
  $ev  = $raw | ConvertFrom-Json

  # (b) Extract (timestamp, transactionCount) pairs. Regex captures the integer after 'transactionCount = '.
  #     '\b' after the id prevents 4486 from also matching 44860, etc. CloudWatch timestamps are epoch-ms.
  $pts = foreach ($e in $ev) {
    if ($e.m -match "IPF ID $id\b.*transactionCount = (\d+)") {
      [pscustomobject]@{ ts = [DateTimeOffset]::FromUnixTimeMilliseconds($e.t).ToUniversalTime(); tc = [int]$matches[1] }
    }
  }
  $pts = @($pts | Sort-Object ts)          # chronological order

  # (c) Pick three checkpoints: first sample, first sample at/after the 8-task restart, and the latest.
  $first = $pts[0]; $last = $pts[-1]
  $at314 = ($pts | Where-Object { $_.ts -ge [DateTimeOffset]::Parse("2026-08-25T03:14:00Z") } | Select-Object -First 1)

  # (d) Emit first / at-8-task / latest, plus the two deltas (4-task period and 8-task period).
  "{0}: first {1:HH:mm}Z={2}  at03:14={3}  latest {4:HH:mm}Z={5}  4taskΔ={6}  8taskΔ={7}" -f `
     $id,$first.ts,$first.tc,$at314.tc,$last.ts,$last.tc,($at314.tc-$first.tc),($last.tc-$at314.tc)
}
```

**Syntax notes:**
- `filter-log-events --filter-pattern '"IPF ID 4486"'` — a **quoted** CloudWatch term match; the double quotes
  make it a literal phrase. This filters **server-side**, so only matching events are returned (cheap).
- `--query "events[].{t:timestamp,m:message}"` — **JMESPath** projection: for every event, keep only the
  `timestamp` (epoch-ms) and `message`. Keeps the payload small and easy to parse.
- `-match "…transactionCount = (\d+)"` — PowerShell regex; `(\d+)` captures the count into `$matches[1]`. The
  `\b` word-boundary after `$id` avoids substring false-positives (e.g. `4486` vs `44860`).
- `[DateTimeOffset]::FromUnixTimeMilliseconds($e.t)` — converts the CloudWatch epoch-ms timestamp to a real
  UTC time so samples sort correctly and checkpoints can be selected by time.
- **Checkpoints** = `first` (≈ pre-4-task backlog), `at03:14` (the 8-task restart boundary), `latest` (now).
  **`4taskΔ = at03:14 − first`** (change during the 4-task period) and **`8taskΔ = latest − at03:14`** (change
  during the 8-task period). Negative Δ = draining; positive Δ = growing.

**How to read it:** a profile is **draining** when `transactionCount` falls over time. Comparing `4taskΔ` vs
`8taskΔ` shows whether the 4→8 scale-up changed a profile's trajectory (e.g. 4486/5795/5793 flipped from a
positive 4-task Δ to a negative 8-task Δ). Because each cycle drains ≤`RESULT_SIZE_LIMIT` (1000) records, a
near-uniform per-cycle Δ across profiles indicates the batch cap — not task count — is the limiter.

*(To re-run later, change `$start`, the `$ipfs` list, and the `03:14` boundary to your periods of interest.)*

### 8b. Overnight progression (03:14Z 8-task start → 12:44Z, ~9½ h)

**All medium/large
IPFs except 4486 have effectively drained.** A broad snapshot of the last 25 min ranked **396 distinct IPFs**;
only 4486 is still large — the entire rest of the fleet is now double/triple digits.

| IPF | @03:14Z (8-task start) | @03:30Z (§8 last) | latest (12:44Z) | overnight Δ (since 03:14) | Status |
|---|---|---|---|---|---|
| **4486** | 665,095 | 661,177 | **566,680** | **−98,415** | still huge; draining ~193/min |
| **5795** | 203,453 | 196,068 | **182** | −203,271 | **cleared** |
| **5793** | 197,715 | 190,325 | **190** | −197,525 | **cleared** |
| **5792** | 65,758 | 58,071 | **116** | −65,642 | **cleared** |
| **5695** | 32,003 | 24,756 | **79** | −31,924 | **cleared** |
| **5605** | 11,494 | 3,887 | **75** | −11,419 | **cleared** |
| **5801** | 2,734 | 128 | **183** | −2,551 | cleared (minor fresh inflow) |

Current top backlogs (last-25-min snapshot, `transactionCount`): **4486 = 566,680**, then a steep cliff —
5793 190, 5801 183, 5795 182, 5788 156, 5792 116, 4540 109, 5695 79, 5605 75, 4879 74, … (everything else ≤ a
few hundred). No *new* large backlog has emerged overnight.

**Findings**
1. **The medium fleet is done.** 5795/5793 (~200k each), 5792, 5695, 5605 all fell from tens/hundreds of
   thousands to <200 overnight — the 8-task scale-up plus drained broad backlog let each profile complete.
2. **4486 remains the sole outlier.** 665,095 → 566,680 overnight (**−98,415**). Measured **last-2h rate
   −193.5/min** (10:46Z 589,513 → 12:44Z 566,680) ⇒ **ETA ≈ 48–49 h** to clear at this rate. Slightly faster
   than the whole-night average (−172.7/min) now that it no longer competes with the medium IPFs for cycles.
3. **Still batch-cap bound, not task bound (per §8 finding 2).** A single locked profile drains ≤~1000/cycle;
   adding tasks won't speed 4486 up. To materially shorten its ~2-day tail it needs a **higher per-IPF batch
   limit** (`RESULT_SIZE_LIMIT` / `transactionsPerFile`) and/or investigation of its high inflow.
4. **DLQ redrive still pending** — batch DLQ 263,629 (≈ unchanged). The §5f/§5g capacity caveat stands:
   relieve DynamoDB capacity **before** redriving, or the historical poison will re-introduce the heavy
   throttling reads.
