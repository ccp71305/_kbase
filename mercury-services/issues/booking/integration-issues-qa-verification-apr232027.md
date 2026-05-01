# QA Integration Verification — Booking Service Build 26.04.014
**Date:** 2026-04-23  
**Environment:** QA (`ANEQABK-001`)  
**Service ARN:** `arn:aws:ecs:us-east-1:642960533737:service/ANEQABK-001/Booking-qa`  
**Task Definition:** `Booking-latest-qa-Task:15`  
**Log Group:** `inttra2-qa-lg-bkapi`  
**Verified by:** GitHub Copilot CLI (Claude Sonnet 4.6)

---

## 1. Deployment Summary

| Field | Value |
|-------|-------|
| Deployment ID | `ecs-svc/2855553534909918737` |
| Deployment started | `2026-04-23 10:14:23 EDT` |
| Deployment completed | `2026-04-23 10:19:06 EDT` |
| Running containers | 2 / 2 desired |
| Failed tasks | 0 |
| Rollout state | `COMPLETED` |

---

## 2. Server Startup Verification — ✅ SUCCESSFUL

Both containers started cleanly with all lifecycle components initialised.

**Container 1:** `Booking-latest-qa/Booking-qa-Container/cd98a58cdfae4eb1a0854e478271220a`  
**Container 2:** `Booking-latest-qa/Booking-qa-Container/d8dc9b23c4bc44b088c40bce3b5fc3b1`

### Startup Sequence (UTC times)

| Time (UTC) | Event |
|------------|-------|
| `14:14:58` | SQS MessagingClient created successfully (both containers) |
| `14:14:58` | S3 StorageClient created successfully (both containers) |
| `14:14:59` | SNS NotificationService created — topic: `arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event` |
| `14:14:59` | JaVers instance started |
| `14:15:01` | Outbound executor started |
| `14:15:01` | Processor executor started |
| `14:15:01` | ListenerManager started |
| `14:15:01` | **Dropwizard application started on port 8080** ✅ |
| `14:15:01` | `Booking life cycle started` |

All messaging infrastructure (SQS, S3, SNS), Jetty server, and background executors started without errors.

---

## 3. Bookings Processed Since Redeploy

**Window:** `2026-04-23 10:19 EDT` → `2026-04-23 11:35 EDT`  
**Total workflow events:** 21  
**New bookings created:** At least 8 unique INTTRA references  
**Outbounds completed:** 18 ✅ | In progress: 1 ⏳ | Very recent (REQUEST state): 2

> **Note:** Multiple workflow IDs sharing the same INTTRA Reference Number represent booking **amendments/updates**, not duplicates — confirmed by `Applied action CONFIRM` log entries.

### 3.1 Booking Workflow Table

| # | INTTRA Ref | Workflow ID | Time (UTC) | Booking State | Outbound |
|---|------------|-------------|------------|---------------|----------|
| 1 | `2010262001` | `4de96c6a-fe53-4aab-988b-9cb3d614a009` | 14:29:55 | REQUEST | ✅ Completed |
| 2 | `2010261001` | `b4ca22c2-2883-43ea-98c6-7f639541730a` | 14:58:59 | REQUEST | ✅ Completed |
| 3 | `2010261001` | `7764ae14-796e-48f0-9c4f-b999669e8ae4` | 14:59:47 | REQUEST | ✅ Completed |
| 4 | `2010261002` | `ff795d72-fbdb-4bc6-b6f6-3f615bca4228` | 15:02:58 | REQUEST | ✅ Completed |
| 5 | `2010261002` | `57581a7a-e7d8-469c-965d-78786633cc04` | 15:05:02 | REQUEST | ✅ Completed |
| 6 | `2010262002` | `2b9dbf39-966c-41cd-8514-0e0166b4461c` | 15:06:01 | REQUEST | ✅ Completed |
| 7 | `2010261002` | `054a2f3b-36c6-441e-9a9d-f9a487033eeb` | 15:06:51 | REQUEST | ✅ Completed |
| 8 | `2010261002` | `61c1fc26-1399-41cf-9608-fa496d9e9696` | 15:08:36 | REQUEST | ✅ Completed |
| 9 | `2010261002` | `20dde669-4919-46e8-9d21-5f7ebfb28da5` | 15:10:25 | REQUEST | ✅ Completed |
| 10 | `2010261002` | `8bdb60dd-6141-4513-ba60-90c1003aba87` | 15:12:11 | REQUEST | ✅ Completed |
| 11 | `2010262003` | `51dc313c-df54-4f58-adce-c83d0cd7b0f2` | 15:14:03 | REQUEST | ✅ Completed |
| 12 | `2010262003` | `627a0e54-b99c-41ac-9631-7b1f0f418207` | 15:17:21 | REQUEST | ✅ Completed |
| 13 | `2010262003` | `d3293299-c840-464c-8f57-dc80ea8a9dba` | 15:20:17 | REQUEST | ✅ Completed |
| 14 | `2010262004` | `1c414d1b-a8b7-4fe8-83d7-10a28eb95be5` | 15:23:24 | REQUEST | ✅ Completed |
| 15 | `2010262005` | `896ad33d-d32c-4412-9670-abd4b73c71f1` | 15:24:24 | REQUEST | ✅ Completed |
| 16 | `2010262004` | `9beaf2ed-e50a-4ce8-8be9-ff11d7f2eb7c` | 15:25:01 | REQUEST | ✅ Completed |
| 17 | `2010262005` | `e46f15e0-be7c-484e-89e5-3befc299041a` | 15:25:15 | REQUEST | ✅ Completed |
| 18 | `2010262004` | `b79a3276-732f-43b2-aaa1-cd9286600162` | 15:25:43 | REQUEST | ✅ Completed |
| 19 | `2010261003` | `63a5fefe-ed81-47c2-96ee-99d576c9b98d` | 15:28:21 | REQUEST | ⏳ In Progress |
| 20 | `2010262006` | `dbd265b4-12e2-4038-8091-737a37ed894f` | 15:28:47 | REQUEST | 🆕 New (pending outbound) |
| 21 | `2010261004` | `dfb017d9-c248-47d3-a5e5-93adbd0e0b31` | 15:33:21 | REQUEST | 🆕 New (pending outbound) |

### 3.2 CONFIRM Actions (Amendments on `2010261003`)

These represent carrier confirmation events processed through the inbound pipeline:

| Workflow ID | Time (UTC) | Action | Result |
|-------------|------------|--------|--------|
| `1513c07e-76f7-464f-804e-73bc23dfa51b` | 15:33:20 | CONFIRM | Applied ✅ |
| `491bcd70-3669-435c-80b7-5d3c86dbcd24` | 15:34:27 | CONFIRM | Applied ✅ |
| `7893afa6-0396-4b7a-9121-5221300272c3` | 15:31:55 | CONFIRM | Applied ✅ |
| `c978d267-445f-4444-a1c9-da2813ab0db2` | 15:30:39 | CONFIRM | Applied ✅ |
| `e7642cad-86e7-43d2-a78e-c1af9556940f` | 15:29:22 | CONFIRM | Applied ✅ |

---

## 4. Outbound Pipeline Verification — ✅ HEALTHY

- **Class:** `OutboundServiceImpl`
- **No outbound errors detected** across all processed bookings
- Each outbound processed: subscriptions evaluated → APERAK generated → emails dispatched

### Outbound flow confirmed per booking:
1. `Outbound processing started for inttraRef {ref} with workflowId {id}`
2. Subscription count evaluated (non-grouped and grouped)
3. APERAK sent per subscription (EDI id + FTP id)
4. `Email processing done for workflowId {id}` per subscription
5. `End Supplement OB for workflowId {id}`

---

## 5. Issues & Errors

### 5.1 `breakbulkAllowed not Found` — ValidationPlanFactory

| Field | Detail |
|-------|--------|
| **Severity** | ERROR (non-fatal — outbound still completed) |
| **Time** | `2026-04-23 14:29:54 UTC` |
| **Workflow** | `4de96c6a-fe53-4aab-988b-9cb3d614a009` |
| **INTTRA Ref** | `2010262001` |
| **Class** | `ValidationPlanFactory.java:338` |
| **User** | `802288` / Company `802442` |

**Stack trace root cause:**
```
java.lang.IllegalArgumentException: Unable to resolve optional rule: breakbulkAllowed
  at ValidationPlanFactory.getOptionalValidationRuleMethodName(ValidationPlanFactory.java:338)
  at ValidationPlanFactory.getOptionalValidationRule(ValidationPlanFactory.java:345)
  at ValidationPlanFactory.addOVRules(ValidationPlanFactory.java:228)
  at ValidationPlanFactory.newValidationPlan(ValidationPlanFactory.java:212)
  at ValidationService.validate(ValidationService.java:388)
  at BookingService.request(BookingService.java:749)
```

**Impact:** The error was caught during validation but outbound processing for `4de96c6a` completed successfully. Likely indicates a missing optional validation rule configuration for `breakbulkAllowed`.

**Recommended Action:** Investigate if `breakbulkAllowed` rule is missing from the validation rule registry or configuration. Low priority — not blocking bookings.

---

### 5.2 Validation Exceptions — BookingProcessorTask

Two workflow events failed with `Validation Exception` in the inbound processor:

| Field | Workflow 1 | Workflow 2 |
|-------|-----------|-----------|
| **Workflow ID** | `0d4ea3ec-6699-4abb-aa2a-82589fd7a7b0` | `ec9c9637-51ca-4109-a53d-3441ff903b3b` |
| **Time (UTC)** | `15:29:50` | `15:34:08` |
| **Class** | `BookingProcessorTask` | `BookingProcessorTask` |
| **Booking ID** | `0977707c68e4463680c6f1e96de618ad` | `3645c25fe87f410b8435c247491d9b20` |
| **Outcome** | Booking skipped / not processed | Booking skipped / not processed |

**Impact:** These two inbound messages were dropped and not processed into bookings. No outbound was generated. Requires investigation to determine root cause (malformed payload, schema mismatch, or missing data).

**Recommended Action:** Pull the full stack trace for both workflow IDs from CloudWatch and identify the validation rule that failed. Check if related to the `breakbulkAllowed` issue above.

---

## 6. Overall Health Assessment

| Area | Status | Notes |
|------|--------|-------|
| Server startup | ✅ Healthy | Both containers up, all services started |
| Messaging infrastructure | ✅ Healthy | SQS, S3, SNS all initialised |
| Booking creation | ✅ Healthy | 21 workflows processed, 8 unique INTTRA refs |
| Outbound pipeline | ✅ Healthy | 18 completed, 0 outbound errors |
| Validation (optional rules) | ⚠️ Warning | `breakbulkAllowed` rule not resolvable |
| Inbound processor | ⚠️ Warning | 2 validation exceptions — messages dropped |

---

## 7. Action Items

| Priority | Item | Owner |
|----------|------|-------|
| Medium | Investigate `breakbulkAllowed` missing from optional validation rule registry (`ValidationPlanFactory.java:338`) | Dev |
| High | Pull full stack traces for `0d4ea3ec` and `ec9c9637` — determine why `BookingProcessorTask` threw `Validation Exception` and whether source data or code is at fault | Dev/QA |
| Low | Monitor outbound for `63a5fefe` (InttraRef `2010261003`) to confirm completion | QA |
| Low | Monitor outbounds for newly created `2010262006` (`dbd265b4`) and `2010261004` (`dfb017d9`) | QA |
