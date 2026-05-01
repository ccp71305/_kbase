# QA Outbound Pipeline Debug Findings — 2026-04-22

**Session date:** 2026-04-21 / 2026-04-22  
**Environment:** AWS QA (`642960533737`, region `us-east-1`)  
**AWS Profile:** `642960533737_INTTRA2-QATeam`  
**Triggered by:** New build deployed to QA at ~9:44 AM EDT (13:44 UTC) on 2026-04-21

---

## 1. Summary

A new booking build (`Booking-latest-qa-Task:15`) was deployed to QA on 2026-04-21. After deployment, all **outbound EDI files stopped being generated** for bookings created through the system. The investigation traced the full outbound pipeline from booking creation through SNS → SQS → transformer → distributor, and identified **three bugs**, with the outbound EDI failure being caused by a **breaking timestamp serialization change** introduced in commit `ee29760491` (ION-14382).

---

## 2. ECS Services & Log Groups Involved

| Service | ECS Cluster | Log Group | Stream Prefix |
|---|---|---|---|
| Booking-qa | ANEQABK-001 | `inttra2-qa-lg-bkapi` | `Booking-latest-qa` |
| transformer-qa | ANEQACONTIVO-001 | `inttra2-qa-lg-app-way` | `AppianWay-transformer-latest-qa` |
| distributor-qa | ANEQAAPWY-001 | `inttra2-qa-lg-app-way` | `AppianWay-distributor-latest-qa` |
| ingestor-qa | ANEQAAPWY-001 | `inttra2-qa-lg-app-way` | `AppianWay-ingestor-latest-qa` |
| event-writer-qa | ANEQAAPWY-001 | `inttra2-qa-lg-app-way` | `AppianWay-event-writer-latest-qa` |
| TxTracking-qa | ANEQAWEBSVC-001 | `inttra2-ecs-logs` | `TxTracking-latest-qa` |

---

## 3. Outbound Pipeline Architecture

```
Booking-qa
  └─► S3 workspace (inttra2-qa-workspace/{rootWorkflowId}/{fileId})
  └─► SQS: inttra2_qa_sqs_transformer_inbound  ◄─── BROKEN POINT (see Bug #1)
        └─► transformer-qa
              └─► S3 (transformed EDI file)
              └─► SQS: inttra2_qa_sqs_file_delivery
                    └─► distributor-qa
                          └─► S3: inttra2-qa-outbound-delivery/customers/{id}/outbound/

  └─► SNS: inttra2_qa_sns_event
        ├─► SQS: inttra2_qa_sqs_ingest  →  ingestor-qa
        └─► SQS: inttra2_qa_sqs_event   →  event-writer-qa
```

---

## 4. Bookings Created After Redeploy (13:44–15:30 UTC)

| Inttra Ref | Workflow ID |
|---|---|
| 2010253003 | *(resolved from logs)* |
| 2010253005 | *(resolved from logs)* |
| 2010253006 | `a12a334e-...` |
| 2010253007 | `2a763995-...` |
| 2010253008 | *(resolved from logs)* |
| 2010253009 | *(resolved from logs)* |
| 2010254003 | `c304a43a-9819-4a23-85f8-411b922a8fa6` *(focus of investigation)* |
| 2010254004 | *(resolved from logs)* |
| 2010254005 | *(resolved from logs)* |

**Key S3 resources:**
- Workspace bucket: `inttra2-qa-workspace`
- Outbound delivery bucket: `inttra2-qa-outbound-delivery`
- SNS topic: `arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event`

---

## 5. Bug #1 — CRITICAL: Outbound EDI Files Not Generated (Timestamp Format Regression)

### Status: ⛔ Blocking — All outbound EDI broken since new build

### Root Cause

Commit `ee29760491` (ION-14382 data format fixes, 2026-04-17) changed the `@JsonFormat` annotation on `booking/util/MetaData.timestamp`:

**Before (working):**
```java
@JsonFormat(pattern = Json.DEFAULT_DATE_TIME_PATTERN)  // "yyyy-MM-dd HH:mm:ss.SS"
private LocalDateTime timestamp;
```

**After (broken):**
```java
@JsonFormat(shape = JsonFormat.Shape.STRING)           // no pattern → ISO-8601 with 'T'
@JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)
private LocalDateTime timestamp;
```

Removing the `pattern` from `@JsonFormat` caused Jackson to serialize `LocalDateTime` in ISO-8601 format:
- **Old serialized value:** `"2026-04-21 14:30:18.66"` (space separator)
- **New serialized value:** `"2026-04-21T14:30:18.66"` (ISO 'T' separator)

The **transformer** (`appianway/shared`) deserializes `MetaData.timestamp` using a `LocalDateTimeDeserializer` registered with pattern `"yyyy-MM-dd HH:mm:ss.SS"` (space separator). It cannot parse the 'T' format and throws:

```
DateTimeParseException: Text '2026-04-21T14:30:18.66' could not be parsed at index 10
→ MetaData$Builder["timestamp"]
→ TransformerTask.process(TransformerTask.java:82)
→ "Message is not processed; Message will reappear"
```

### Impact

- **519 messages** stuck in `inttra2_qa_sqs_transformer_inbound_dlq`
- Every outbound EDI subscription since 13:44 UTC on 2026-04-21 failed silently
- All 9 bookings created post-redeploy have no outbound EDI files delivered

### Fix

In `booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java`, restore the `pattern` to the `@JsonFormat` annotation while keeping the new flexible deserializer:

```java
// Before (broken — no pattern means ISO-8601 with 'T'):
@JsonFormat(shape = JsonFormat.Shape.STRING)
@JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)
private LocalDateTime timestamp;

// After (fixed — pattern controls serialization; deserializer handles flexible parsing):
@JsonFormat(pattern = Json.DEFAULT_DATE_TIME_PATTERN)
@JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)
private LocalDateTime timestamp;
```

### Post-fix Actions Required

1. Re-deploy booking to QA after the fix
2. Replay the 519 DLQ messages: move from `inttra2_qa_sqs_transformer_inbound_dlq` back to `inttra2_qa_sqs_transformer_inbound`
3. Verify transformer picks them up and distributor delivers EDI files to `inttra2-qa-outbound-delivery`

---

## 6. Bug #2 — ClassCastException in EdiCustomizations for Cancel Workflows

### Status: 🔴 Active bug (pre-existing or introduced in new build)

### Location
`booking/src/main/java/com/inttra/mercury/booking/outbound/custom/EdiCustomizations.java` — line 702

### Error
```
java.lang.ClassCastException: class com.inttra.mercury.booking.model.CancelMessage
cannot be cast to class com.inttra.mercury.booking.model.BookingRequestContract
at EdiCustomizations.mainCarriageCustomization(EdiCustomizations.java:702)
← CustomizationHandler.applyCompanySpecificEDICustomizations(line 183)
← OutboundServiceImpl.processSubscriptions(line 625)
```

### Root Cause
`mainCarriageCustomization()` unconditionally casts the contract to `BookingRequestContract`, but cancel-type workflows pass a `CancelMessage` object.

### Impact
Only affects cancel-type booking workflows sent through EDI customization pipeline. REQUEST-type bookings are unaffected.

### Fix (not yet applied)
Add an `instanceof` check in `mainCarriageCustomization()` before casting, or dispatch to separate handlers based on contract type.

---

## 7. Bug #3 — NPE in TxTracking for Newly Created Workflows

### Status: 🟡 Low severity — self-resolving once ES indexes the workflow

### Location
- `tx-tracking/src/main/java/com/inttra/mercury/txtracking/service/TxTrackingService.java` — line 80
- `tx-tracking/src/main/java/com/inttra/mercury/txtracking/service/GetWorkflowDetailsResolver.java` — line 109

### Error
```
NullPointerException: obj is null
at SearchResult.getHits()
← GetWorkflowDetailsResolver.buildGetWorkflowDetails(line 109)
← TxTrackingResource.getWorkflowDetails(line 109)
```

### Root Cause
Existing null guard at `TxTrackingService.java:80` checks `results.getJsonObject() == null` but NOT `results.getJsonObject().getAsJsonObject("hits") == null`. When Elasticsearch returns an empty/error response for a brand-new workflow not yet indexed, `getHits()` throws NPE.

### Fix (not yet applied)
```java
// Current (insufficient):
if (results == null || results.getJsonObject() == null) { ... }

// Fixed:
if (results == null || results.getJsonObject() == null
        || results.getJsonObject().getAsJsonObject("hits") == null) { ... }
```

### Secondary issue in same file
`GetWorkflowDetailsResolver.java:132` — `IllegalArgumentException: Key must not be null or empty` when generating S3 presigned URLs for metadata that has null bucket/fileName fields. Non-fatal, logged 3x per missing file.

---

## 8. Confirmed Working

- ✅ SNS `inttra2_qa_sns_event` → SQS fanout to `inttra2_qa_sqs_ingest` and `inttra2_qa_sqs_event`
- ✅ `ingestor-qa` consuming `inttra2_qa_sqs_ingest` — no errors
- ✅ `event-writer-qa` consuming `inttra2_qa_sqs_event` — no errors
- ✅ All SQS queues and DLQs empty (except `transformer_inbound_dlq` — 519 messages)
- ✅ `distributor-qa` IS active — processing other workflow types (CONTRL, PI files)
- ✅ Booking `2010253013` (created before the problematic bookings) — full pipeline verified end-to-end

---

## 9. Key Files Referenced

| File | Notes |
|---|---|
| `booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java` | **Fix needed** — timestamp `@JsonFormat` pattern removed in ION-14382 |
| `booking/src/main/java/com/inttra/mercury/booking/util/Json.java` | Defines `DEFAULT_DATE_TIME_PATTERN = "yyyy-MM-dd HH:mm:ss.SS"` |
| `booking/src/main/java/com/inttra/mercury/booking/outbound/services/TransformerService.java` | Uploads to S3 and sends metadata to `sqs_transformer_inbound` |
| `booking/src/main/java/com/inttra/mercury/booking/outbound/custom/EdiCustomizations.java` | Bug #2: ClassCastException at line 702 |
| `tx-tracking/src/main/java/com/inttra/mercury/txtracking/service/TxTrackingService.java` | Bug #3: Insufficient null guard at line 80 |
| `appianway/shared/src/main/java/com/inttra/mercury/shared/task/MetaData.java` | Transformer's MetaData — expects `"yyyy-MM-dd HH:mm:ss.SS"` pattern |
| `appianway/shared/src/main/java/com/inttra/mercury/shared/support/Json.java` | Transformer's Json — registers `LocalDateTimeDeserializer` with space-pattern |
| `appianway/transformer/src/main/java/com/inttra/mercury/transformer/task/TransformerTask.java` | Fails at line 82 deserializing `MetaData` from SQS |

---

## 10. Priority Action Items

| Priority | Action | Owner |
|---|---|---|
| 🔴 P1 | Fix `MetaData.java` timestamp `@JsonFormat` pattern (1-line fix) | Dev |
| 🔴 P1 | Re-deploy booking to QA | DevOps |
| 🔴 P1 | Replay 519 messages from `transformer_inbound_dlq` | DevOps/QA |
| 🟠 P2 | Fix `EdiCustomizations.java:702` ClassCastException for cancel workflows | Dev |
| 🟡 P3 | Fix `TxTrackingService.java:80` null guard for ES hits | Dev |
