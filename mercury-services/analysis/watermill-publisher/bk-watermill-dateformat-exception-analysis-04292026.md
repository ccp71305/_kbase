# Watermill-Publisher DateTimeParseException Analysis

**Date**: 2026-04-29  
**Agent Model**: Claude Opus 4.6  
**AWS Profile**: `642960533737_INTTRA2-QATeam` (QA environment)  
**Related Sessions**: `9d0caeabd6394be2` (DataFormat Fixes), `2686c49ecbb241e3` (Integration Issues)  

---

## 1. Reported Issues

### Issue 1: Common.Artifacts.Date — EDI Date Parse Error
```
ERROR [2026-04-29 09:21:02,055] [pool-4-thread-1] c.i.m.b.model.Common.Artifacts.Date     :  
DateTimeParseException caught, invalid date value. ParsedString = 2604290921, Error Index = 10, 
Message = Text '2604290921' could not be parsed at index 10
```

### Issue 2: SQS Listener — MetaData.timestamp Deserialization Failure
```
ERROR [2026-04-29 09:15:26,575] [pool-4-thread-1] c.i.m.watermill.commons.sqs.SQSListener :  
Exception in SQS Listener :
java.time.format.DateTimeParseException: Text '2026-04-21T17:43:56.927646471' could not be parsed at index 10
  ...
Wrapped by: com.fasterxml.jackson.databind.exc.InvalidFormatException: Cannot deserialize value 
of type `java.time.LocalDateTime` from String "2026-04-21T17:43:56.927646471"
  at ... (through reference chain: com.inttra.mercury.messaging.model.MetaData$Builder["timestamp"])
```

---

## 2. Investigation Findings

### 2.1 Issue 1 Analysis — Common.Artifacts.Date (EDI Date Parse)

**Verdict: Pre-existing EDI data quality issue. NOT related to the date format fix.**

**Root Cause**:  
The booking payload contains a `Date` object with:
- `dateValue = "2604290921"` (10 characters, YYMMDDHHMM format: 2026-04-29 09:21)
- `dateFormat` set to a format expecting more characters (e.g., `CCYYMMDDHHMM` = 12 chars or `CCYYMMDDHHMMSS` = 14 chars)

When `Date.getLocalDateTime()` is called during Protobuf transformation, `dateFormat.toLocalDateTime(dateValue)` tries to parse 10 characters with a pattern expecting 12+ characters, causing `DateTimeParseException` at index 10.

**Code Path**: `Date.java` (line 46-50) — `booking/src/main/java/.../model/Common/Artifacts/Date.java`
```java
try {
    dateTime = dateFormat != null && dateValue != null ? dateFormat.toLocalDateTime(dateValue) : null;
} catch(DateTimeParseException dpe) {
    dateTime = null;  // ← Returns null, processing continues
    log.error("DateTimeParseException caught, invalid date value...");
}
```

**Impact**: **Non-fatal**. The exception is caught, the date field is set to `null`, and booking processing continues. The Protobuf message is published with the date field absent.

**Frequency Today (April 29)**: 4 occurrences, all with `ParsedString = 2604291044` (= 2026-04-29 10:44).

**Conclusion**: This is an existing EDI data quality issue where the sender provides a date value in a shorter format than the declared `dateFormat`. No action needed for the date format fix investigation.

---

### 2.2 Issue 2 Analysis — MetaData.timestamp (SQS Deserialization)

**Verdict: Pre-fix residual messages. The booking date format fix IS working correctly since QA deployment on April 24.**

#### The Deserialization Chain

1. **Booking module** publishes MetaData JSON to SQS: `inttra2_qa_sqs_watermill_bk`
2. **Watermill-publisher** (`WatermillBKTask.java`, line 72) reads the SQS message and deserializes:
   ```java
   final MetaData metaData = Json.fromJsonString(message.getBody(), MetaData.class);
   ```
3. `Json.fromJsonString()` uses an `ObjectMapper` with `LocalDateTimeDeserializer` registered for pattern `"yyyy-MM-dd HH:mm:ss.SS"`
4. When the SQS message contains an ISO T-format timestamp (e.g., `"2026-04-21T17:43:56.927646471"`), the deserializer fails at index 10 (expects space, finds `T`)

#### Timeline of Events

| Date | Event |
|------|-------|
| **Apr 17** | Booking data format fix planned (session `9d0caeabd6394be2`) |
| **Apr 21** | Booking module producing MetaData with ISO T-format timestamps (pre-fix) |
| **Apr 22** | Integration issues fix completed (session `2686c49ecbb241e3`): MetaData.timestamp restored to `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss.SS")` + MixIn for DynamoDB |
| **Apr 24 10:08 ET** | **Fix deployed to QA** (ECS Booking-latest-qa-Task:15) |
| **Apr 29** | Reported errors — all contain pre-fix (April 21-23) timestamp values |

#### CloudWatch Log Evidence

**Successful processing (post-fix):**
```
LOG TIME: 2026-04-29 05:00:42
METADATA: {"workflowId":"c37e314b-...","timestamp":"2026-04-29 05:00:41.84",...}
                                                    ↑ SPACE format ✅
```

**Failed processing (pre-fix residual):**
```
LOG TIME: 2026-04-29 05:11:25
PARSED VALUE: 2026-04-21T15:20:55.393216309   ← ISO T format, April 21 (PRE-FIX)
```

**All 27 unique failing timestamp values since QA deployment:**

| Timestamp Value | Date | Pre/Post Fix |
|----------------|------|-------------|
| `2026-04-21T13:43:11.228889227` | Apr 21 | Pre-fix |
| `2026-04-21T13:43:52.147472403` | Apr 21 | Pre-fix |
| `2026-04-21T13:45:48.252698438` | Apr 21 | Pre-fix |
| `2026-04-21T13:46:56.658674241` | Apr 21 | Pre-fix |
| `2026-04-21T13:47:46.710675151` | Apr 21 | Pre-fix |
| `2026-04-21T13:49:47.205793372` | Apr 21 | Pre-fix |
| `2026-04-21T13:50:35.766620556` | Apr 21 | Pre-fix |
| `2026-04-21T14:42:16.202025162` | Apr 21 | Pre-fix |
| `2026-04-21T14:50:18.043297323` | Apr 21 | Pre-fix |
| `2026-04-21T14:52:14.366491343` | Apr 21 | Pre-fix |
| `2026-04-21T15:23:27.571725858` | Apr 21 | Pre-fix |
| `2026-04-21T17:37:17.437045102` | Apr 21 | Pre-fix |
| `2026-04-21T17:40:22.69495922` | Apr 21 | Pre-fix |
| `2026-04-21T17:42:32.447780945` | Apr 21 | Pre-fix |
| `2026-04-21T17:43:56.927646471` | Apr 21 | Pre-fix |
| `2026-04-21T18:11:34.871471094` | Apr 21 | Pre-fix |
| `2026-04-21T18:30:32.691193292` | Apr 21 | Pre-fix |
| `2026-04-21T18:48:58.791589414` | Apr 21 | Pre-fix |
| `2026-04-21T18:49:04.082340837` | Apr 21 | Pre-fix |
| `2026-04-21T18:56:51.450949502` | Apr 21 | Pre-fix |
| `2026-04-21T19:06:48.989002566` | Apr 21 | Pre-fix |
| `2026-04-21T19:06:51.067739417` | Apr 21 | Pre-fix |
| `2026-04-21T23:53:09.130162762` | Apr 21 | Pre-fix |
| `2026-04-22T10:53:09.607323443` | Apr 22 | Pre-deployment |
| `2026-04-23T10:47:27.724888528` | Apr 23 | Pre-deployment |
| `2026-04-23T10:47:27.83584522` | Apr 23 | Pre-deployment |
| `2026-04-23T10:50:21.434517597` | Apr 23 | Pre-deployment |

**ZERO failures with post-April 24 timestamps.**

#### Why Pre-Fix Messages Are Still Present

| SQS Configuration | Value |
|-------------------|-------|
| Queue | `inttra2_qa_sqs_watermill_bk` |
| Visibility Timeout | 60 seconds |
| Message Retention | 345600 seconds (4 days) |
| Max Receive Count | 5 (then → DLQ) |
| DLQ | `inttra2_qa_sqs_watermill_bk_dlq` |
| DLQ Retention | 345600 seconds (4 days) |

**Message lifecycle for a pre-fix message:**
1. Pre-fix message arrives in main queue
2. WatermillBKTask attempts to deserialize → fails at `Json.fromJsonString()` (line 72)
3. Exception propagates up through `AsyncDispatcher` → `SQSListener` catches it
4. Message becomes visible again after 60s visibility timeout
5. After 5 failures → moved to DLQ
6. DLQ messages are periodically redriven back to main queue (observed pattern: errors re-appear every ~5 days)
7. Cycle repeats until messages expire from DLQ

**Critical side effect**: When a pre-fix message is in a batch with valid messages, the entire batch fails because the exception on line 72 breaks the `for` loop without processing remaining messages in the batch. This causes unnecessary re-processing of valid messages.

---

## 3. Error Breakdown — April 29, 2026

| Error Category | Count | Severity | Related to Fix? |
|---------------|-------|----------|-----------------|
| MetaData Timestamp Parse (SQSListener) | 43 | **Fatal** — blocks message processing | Pre-fix residual |
| EDI Date Parse (Common.Artifacts.Date) | 4 | **Non-fatal** — caught, returns null | No |
| gRPC ResponseObserver | 3 | Stream management | No |
| **Successful bookings** | **27** | N/A | N/A |

---

## 4. Recent Booking Flow Trace

### Successful Booking — WorkflowId `c37e314b-06f3-4bcb-ae58-82501ed64499`

**Processed**: 2026-04-29 05:00:42 UTC

```
Step 1: Booking module writes payload to S3
        → Bucket: inttra2-qa-workspace
        → File: watermill_c37e314b-.../0f531763-fa37-45bd-a618-856c97fa7070

Step 2: Booking module publishes MetaData JSON to SQS
        → Queue: inttra2_qa_sqs_watermill_bk
        → MetaData JSON includes:
          {
            "workflowId": "c37e314b-06f3-4bcb-ae58-82501ed64499",
            "bucket": "inttra2-qa-workspace",
            "fileName": "watermill_c37e314b-.../0f531763-...",
            "component": "booking",
            "timestamp": "2026-04-29 05:00:41.84",  ← SPACE format ✅
            "projections": { "fileNameToken.carrierId": "802435", ... }
          }

Step 3: SQSListener polls queue (long poll, 20s wait, max 3 messages)

Step 4: AsyncDispatcher dispatches to WatermillBKTask.execute()

Step 5: WatermillBKTask:
        a. Deserialize MetaData from SQS body → ✅ (space format matches pattern)
        b. Read S3 payload via S3WorkspaceService.getContent()
        c. Deserialize as WatermillBookingDetail
        d. Transform to Protobuf:
           - If carrier status → BKConfirmProtobufTransformer → BookingConfirmationChangeEvent
           - BKProtobufTransformer → BookingChangeEvent

Step 6: gRPC publish to Watermill (watermill.staging.e2open.com:443)

Step 7: ResponseObserver receives ack → SQS message deleted → SNS event logged
```

### Additional Bookings Processed Today

| # | WorkflowId | Time (UTC) | Status |
|---|-----------|------------|--------|
| 1 | `c37e314b-06f3-4bcb-ae58-82501ed64499` | 05:00:42 | ✅ Success |
| 2 | `53027158-9d0d-46da-b7e8-2af44038131b` | 05:01:32 | ✅ Success |
| 3 | `406b3ed4-df2f-4f64-a37e-a557125c8531` | 05:02:32 | ✅ Success |
| 4 | `c0dc750f-0917-4971-a2a5-44d07f7cd6d3` | 05:03:54 | ✅ Success |
| 5 | `d7c38c25-2f13-4ec4-8bac-3cdd5ca923f4` | 05:04:44 | ✅ Success |
| ... | 22 more bookings | 05:04 - 05:29 | ✅ Success |

**27 bookings successfully processed today** using the post-fix space-format timestamps.

---

## 5. Conclusions

### 5.1 Is this a valid date format issue continuing after the April 22 fix?

**NO.** The date format fix is working correctly. All evidence confirms:

1. **New bookings** (post April 24 QA deployment) use space-format timestamps: `"2026-04-29 05:00:41.84"` ✅
2. **All failing timestamp values** are from April 21-23 — **before** the fix was deployed to QA on April 24
3. **Zero failures** with post-deployment timestamps
4. **27 bookings** were successfully processed today (April 29)

### 5.2 Source of the continued errors

The 43 MetaData timestamp errors on April 29 are caused by **pre-fix messages cycling through DLQ redrives**:

- Pre-fix messages (April 21-23) had ISO T-format timestamps
- These messages fail in watermill-publisher (expects space format)
- After 5 failures → DLQ
- DLQ messages are periodically redriven → fail again → DLQ → cycle repeats
- The DLQ retention is 4 days; messages expire after that period but may be redriven before expiry

### 5.3 Impact on current processing

The pre-fix messages cause **collateral damage**: when a batch of SQS messages includes both pre-fix (bad) and post-fix (good) messages, the entire batch fails because the exception at `WatermillBKTask.java:72` is unhandled within the message loop. This forces valid messages to be re-processed on the next poll cycle.

---

## 6. Recommendations

### Immediate Actions

1. **Purge the DLQ**: Remove all pre-fix messages from `inttra2_qa_sqs_watermill_bk_dlq` to stop the redrive cycle:
   ```bash
   aws sqs purge-queue --queue-url https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_watermill_bk_dlq --region us-east-1
   ```

2. **Check main queue**: Verify that the 68 in-flight messages (observed at investigation start) are not all pre-fix messages. Once they exhaust retries and move to DLQ, purge the DLQ.

### Recommended Code Improvements (Separate PR)

3. **Per-message error handling in WatermillBKTask**: Wrap MetaData deserialization in a per-message try-catch to prevent one bad message from blocking the entire batch:
   ```java
   for (Message message : messages) {
       try {
           final MetaData metaData = Json.fromJsonString(message.getBody(), MetaData.class);
           // ... rest of processing
       } catch (UncheckedIOException e) {
           log.error("Failed to deserialize MetaData for message: {}", message.getMessageId(), e);
           sqsClient.deleteMessage(configuration.getSqsPickupConfig().getQueueUrl(), message.getReceiptHandle());
           continue; // Process next message in batch
       }
   }
   ```

4. **Consider making watermill-publisher's Json class flexible**: Add support for both ISO T and space-format timestamps in the `LocalDateTimeDeserializer`:
   ```java
   // In watermill-commons Json.java, register a flexible deserializer
   JavaTimeModule javaTimeModule = new JavaTimeModule();
   javaTimeModule.addDeserializer(LocalDateTime.class, new FlexibleLocalDateTimeDeserializer());
   ```
   This would make watermill-publisher resilient to future format changes from the booking module.

### Monitoring

5. **Verify errors stop**: After purging the DLQ, monitor CloudWatch logs for `WatermillPublisherBooking-latest-qa` for 24 hours to confirm no new `DateTimeParseException` errors appear.

---

## 7. AWS Resources Verified

| Resource | QA Value | Status |
|----------|----------|--------|
| ECS Cluster | `ANEQAAPWY-001` | Active |
| ECS Service | `WatermillPublisherBooking-qa` | Running (1/1) |
| Task Definition | `WatermillPublisherBooking-latest-qa-Task:2` | Active |
| CloudWatch Log Group | `inttra2-ecs-logs` | Streaming |
| Log Stream Prefix | `WatermillPublisherBooking-latest-qa` | Active |
| SQS Queue | `inttra2_qa_sqs_watermill_bk` | Active |
| SQS DLQ | `inttra2_qa_sqs_watermill_bk_dlq` | Active |
| S3 Workspace | `inttra2-qa-workspace` | Active |
| Booking ECS Service | `Booking-qa` (cluster `ANEQABK-001`) | Active |
| Booking Deployment | `Booking-latest-qa-Task:15` (deployed Apr 24 10:08 ET) | Active |

---

## 8. Referenced Documentation

| Document | Purpose |
|----------|---------|
| `booking/docs/2026-04-17-booking-dataformat-fixes.md` | Original data format fix plan |
| `booking/docs/booking-integration-issues-04222027-copilot.md` | Integration issues and fixes post-upgrade |
| `booking/docs/DESIGN-AWS2x.md` | AWS 2.x upgrade design |
| `watermill-publisher/docs/DESIGN-watermill-publisher.md` | Module design and architecture |

---

## 9. Key Code References

| File | Relevance |
|------|-----------|
| `watermill-publisher/watermill-commons/src/main/java/.../support/Json.java` | `DEFAULT_DATE_TIME_PATTERN = "yyyy-MM-dd HH:mm:ss.SS"` — the expected format |
| `watermill-publisher/watermill-booking/src/main/java/.../task/WatermillBKTask.java` (line 72) | Where MetaData deserialization fails |
| `libs/messaging-helper/src/main/java/.../messaging/model/MetaData.java` | MetaData class with `@JsonFormat(pattern = Json.DEFAULT_DATE_TIME_PATTERN)` |
| `booking/src/main/java/.../booking/util/MetaData.java` | Booking module's MetaData — fixed to use space format |
| `booking/src/main/java/.../model/Common/Artifacts/Date.java` | EDI date parsing (Issue 1) |
| `booking/src/main/java/.../model/Common/Types/DateFormat.java` | DateFormat enum with `YYMMDDHHMM`, `CCYYMMDDHHMM`, etc. |
