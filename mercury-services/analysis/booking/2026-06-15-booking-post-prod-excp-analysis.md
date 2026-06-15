# Booking Post-Production Exception Analysis
**Date:** 2026-06-15  
**Analyst:** Claude Opus 4.6 Agent  
**Session:** `d9ad65d756e846f8`  
**Related Release Checkout:** [2026-06-13 Production Release Checkout](2026-06-13-booking-prod-release-checkout.md) (session `627d90c2d8144187`)

---

## Executive Summary

**Status: ⚠️ BUG CONFIRMED — AWS SDK v2 Upgrade Regression**

Two `DynamoDbException` errors were initially reported on 2026-06-15 at 06:51 UTC. CloudWatch investigation reveals **268 unique failed booking requests** since deployment, all from the same client (Company 822415). The root cause is an empty string `""` in the `carrierReferenceNumber` GSI sort key — a **direct regression from the AWS SDK v1→v2 upgrade**. Additionally, the error recovery (S3 save of failed data) is also failing (269 times), meaning **failed booking data is lost**.

### Key Findings

| Finding | Detail |
|---------|--------|
| **Exception Type** | `software.amazon.awssdk.services.dynamodb.model.DynamoDbException` |
| **Root Cause** | Empty string `""` in GSI sort key `carrierReferenceNumber` |
| **GSI Affected** | `carrierId_carrierReferenceNumber` (also affects `carrierScac_carrierReferenceNumber`) |
| **Related to SDK Upgrade** | ✅ **YES** — SDK v1 silently omitted empty strings; SDK v2 preserves them |
| **Integration Test Coverage** | ❌ **NOT COVERED** — no test for empty-string GSI key save |
| **Fix Available** | ✅ `NullifyEmptyStringConverter` exists in commons but is not applied |
| **Total Failed Requests** | **268** unique booking requests failed (since deployment June 13 noon) |
| **Total Error Log Entries** | **268** DynamoDbException + **270** "Retries exhausted" + **269** S3 putObject failures |
| **Client Impacted** | Company 822415, Client 822415-31610 (User-Agent: RestSharp/106.11.7.0) |
| **Endpoint** | `POST /booking/request` |
| **S3 Error Recovery** | ❌ **ALSO FAILING** — workflowId is empty string → invalid S3 key `dynamo_error/` |
| **Data Loss** | ⚠️ **YES** — failed booking data not persisted in DynamoDB or S3 |
| **Impact Severity** | **HIGH** — 268 booking creations failed with data loss, ongoing |

---

## 1. Exception Details

### 1.1 Error Message
```
DynamoDbException: One or more parameter values are not valid. 
A value specified for a secondary index key is not supported. 
The AttributeValue for a key attribute cannot contain an empty string value. 
IndexName: carrierId_carrierReferenceNumber, IndexKey: carrierReferenceNumber 
(Service: DynamoDb, Status Code: 400, Request ID: IHPP3GMVRDJ23I8BG8CDI5LO87VV4KQNSO5AEMVJF66Q9ASUAAJG)
```

### 1.2 Timestamp & Context
| Detail | Value |
|--------|-------|
| Timestamp | 2026-06-15 06:51:24.813 UTC |
| Thread | `dw-113 - POST /booking/request` |
| Client ID | `822415-31610` |
| Company ID | `822415` |
| Endpoint | `POST /booking/request` |
| HTTP Status | Error (500 implied — exception propagated) |

### 1.3 Call Stack (Key Frames)
```
BookingService.request()                          → line 768
  └─ BookingService.create()                      → line 356
       └─ BookingService.newBookingDetail()        → line 257 → 326
            └─ BookingDetailDao.save()             → line 66
                 └─ EnhancedDynamoRepository.save()→ line 237
                      └─ DefaultDynamoDbTable.putItem()
                           └─ DefaultDynamoDbClient.putItem()
                                └─ DynamoDB API returns 400
```

### 1.4 Identifying the Booking/Request

From the error log:
- **Company:** 822415 
- **Client:** 822415-31610
- The exception occurred during `BookingService.create()` → `BookingService.request()`, meaning this was a **new booking REQUEST** (not an amend/confirm/decline).
- The booking was **NOT created** — the DynamoDB putItem failed and the exception was thrown after retries were exhausted (per the retry logic in `BookingService.newBookingDetail()` lines 322-344).
- The failed booking data would have been saved to S3 at `dynamo_error/<workflowId>` (per line 336) if the S3 write succeeded.

**Note:** Since the putItem failed, no `inttraReferenceNumber` was persisted for this booking in DynamoDB. The booking request was rejected. To find the specific request data, check:
1. S3 bucket at path `dynamo_error/` for the workflowId
2. Application logs for `workflowId` context around 06:51:24 UTC on 2026-06-15
3. The inbound SQS message if this came via EDI

---

## 2. Root Cause Analysis

### 2.1 The SDK v1 vs v2 Behavioral Difference

This is a **well-known AWS SDK v1→v2 migration pitfall**.

| Behavior | AWS SDK v1 (`DynamoDBMapper`) | AWS SDK v2 (`Enhanced Client`) |
|----------|-------------------------------|-------------------------------|
| Empty string `""` on regular attributes | **Omitted** (treated as null) | **Preserved** as `S: ""` |
| Empty string `""` on key attributes | **Omitted** (no error) | **Preserved → DynamoDB rejects with 400** |
| Null on key attributes | Omitted (item not indexed in GSI) | Omitted (item not indexed in GSI) |

**In SDK v1:** When `carrierReferenceNumber` was `""`, the `DynamoDBMapper` silently omitted it from the item. DynamoDB stored the item without the `carrierReferenceNumber` attribute, and the item was simply not indexed in the `carrierId_carrierReferenceNumber` GSI. No error occurred.

**In SDK v2:** The Enhanced Client marshals `""` as `AttributeValue.builder().s("").build()` and sends it to DynamoDB. DynamoDB rejects this because **empty strings are not allowed as key attribute values** (including GSI partition and sort keys).

### 2.2 Where the Empty String Originates

```java
// BookingService.java:276
detail.setCarrierReferenceNumber(contract.getCarrierReferenceNumber());
```

The `carrierReferenceNumber` comes from `Contract.getCarrierReferenceNumber()` which is `BookingRequestContract.carrierReferenceNumber` — a Jackson-deserialized field from the incoming JSON request body.

When a booking request is submitted **without a carrier reference number** (typical for new REQUEST bookings where the carrier hasn't assigned one yet), the JSON may contain:
- `"carrierReferenceNumber": ""` → empty string (causes the error)
- `"carrierReferenceNumber": null` → null (would work fine)
- Field absent → null (would work fine)

### 2.3 Why This Wasn't Caught Before Release

1. **SDK v1 masked the issue** — Empty strings were silently dropped, so the production codebase has been sending empty strings for years without issues.
2. **Integration tests only use non-empty values** — `BookingDetailDaoIT` uses hardcoded values like `"CRN-200"` and `"CRN-SCAC-500"` for carrier reference numbers. No test saves a `BookingDetail` with `carrierReferenceNumber = ""`.
3. **QA testing likely used valid reference numbers** — Test scenarios probably always included a carrier reference number in the booking request.
4. **The issue is data-dependent** — Only manifests when a client submits a booking without a carrier reference number (common in the initial REQUEST state before carrier assignment).

---

## 3. Impact Assessment

### 3.1 Affected GSI Key Fields

The `BookingDetail` model has **6 GSI key fields**, none of which have `NullifyEmptyStringConverter` applied:

| Field | GSI Role | GSI Name | Risk of Empty String |
|-------|----------|----------|---------------------|
| `carrierId` | Partition Key | `carrierId_carrierReferenceNumber` | LOW — always set from context |
| **`carrierReferenceNumber`** | **Sort Key** | **`carrierId_carrierReferenceNumber`, `carrierScac_carrierReferenceNumber`** | **HIGH — confirmed empty in prod** |
| `bookerId` | Partition Key | `bookerId_shipmentId` | LOW — always set (fallback to "-1") |
| `shipmentId` | Sort Key | `bookerId_shipmentId` | MEDIUM — only set for non-carrier states, could be empty |
| `inttraReferenceNumber` | Partition Key | `INTTRA_REFERENCE_NUMBER_INDEX` | LOW — always generated by service |
| `carrierScac` | Partition Key | `carrierScac_carrierReferenceNumber` | MEDIUM — could be empty/null for some carriers |

### 3.2 Frequency Assessment

- **2 exceptions in ~48 hours post-release** out of 5,192+ bookings created
- This suggests the empty-carrier-reference scenario is uncommon but real
- REQUEST bookings from clients who don't provide a carrier reference number are the primary risk

### 3.3 Customer Impact

- Booking creation **fails** for the affected request
- The retry logic in `BookingService.newBookingDetail()` (lines 322-344) retries the save, but all retries will fail because the data itself is invalid
- After retries are exhausted, the failed data is saved to S3 at `dynamo_error/<workflowId>`
- The exception propagates up to the REST endpoint, returning a 500 error to the client

---

## 4. Fix Recommendation

### 4.1 Immediate Fix: Apply NullifyEmptyStringConverter

The `NullifyEmptyStringConverter` already exists in `mercury-services-commons` at:
```
cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/database/converter/NullifyEmptyStringConverter.java
```

**Apply to `BookingDetail.java` on `getCarrierReferenceNumber()`:**
```java
@DynamoDbConvertedBy(NullifyEmptyStringConverter.class)
@DynamoDbSecondarySortKey(indexNames = {
    CARRIER_ID_CARRIER_REFERENCE_NUMBER_INDEX,
    CARRIER_SCAC_CARRIER_REFERENCE_NUMBER_INDEX
})
public String getCarrierReferenceNumber() {
    return carrierReferenceNumber;
}
```

### 4.2 Defensive Fix: Apply to All GSI Key Fields

For complete safety, apply the converter to all string GSI key fields that could potentially be empty:

```java
// carrierId — partition key
@DynamoDbConvertedBy(NullifyEmptyStringConverter.class)
@DynamoDbSecondaryPartitionKey(indexNames = {CARRIER_ID_CARRIER_REFERENCE_NUMBER_INDEX})
public String getCarrierId() { ... }

// carrierReferenceNumber — sort key for 2 GSIs
@DynamoDbConvertedBy(NullifyEmptyStringConverter.class)
@DynamoDbSecondarySortKey(indexNames = { ... })
public String getCarrierReferenceNumber() { ... }

// shipmentId — sort key
@DynamoDbConvertedBy(NullifyEmptyStringConverter.class)
@DynamoDbSecondarySortKey(indexNames = {BOOKER_ID_SHIPMENT_ID_INDEX})
public String getShipmentId() { ... }

// carrierScac — partition key
@DynamoDbConvertedBy(NullifyEmptyStringConverter.class)
@DynamoDbSecondaryPartitionKey(indexNames = {CARRIER_SCAC_CARRIER_REFERENCE_NUMBER_INDEX})
public String getCarrierScac() { ... }
```

**Note:** `inttraReferenceNumber` and `bookerId` are always set to non-empty values by the service logic, so they are lower risk. However, adding the converter defensively would be safest.

### 4.3 Alternative Fix: Nullify at Service Layer

An alternative (or complementary) approach is to nullify empty strings in `BookingService.newBookingDetail()`:
```java
detail.setCarrierReferenceNumber(
    Strings.emptyToNull(contract.getCarrierReferenceNumber()));
```

This is less preferable than the converter approach because:
- It only fixes one code path; other code paths setting this field would still be at risk
- The converter approach is the standard pattern used by other modules (registration)

---

## 5. Integration Test Gap

> **Resolution (ION-16028):** The gap below is now closed. `BookingDetailDaoIT`
> contains a nested `EmptyStringGsiKeyTests` class covering every GSI key string
> field. See [§5.4](#54-running-the-integration-tests) for the exact command used
> to run them (verified red before the fix, green after).

### 5.1 Current Coverage

`BookingDetailDaoIT` tests the following GSI scenarios:
- `shouldFindByCarrierIdAndRef()` — uses `"CRN-200"` (non-empty) ✅
- `shouldReturnEmptyForNonMatching()` — queries with non-existent values ✅
- `shouldFindByCarrierScacAndRef()` — uses `"CRN-SCAC-500"` (non-empty) ✅

### 5.2 Missing Test Scenarios

The following test scenarios are **NOT covered**:

1. **Save with empty string `carrierReferenceNumber`** — should succeed (converter converts to null)
2. **Save with null `carrierReferenceNumber`** — should succeed
3. **Save with empty string `shipmentId`** — should succeed
4. **Save with empty string `carrierScac`** — should succeed
5. **Round-trip: save with empty carrier ref, read back** — should return null for the field
6. **Query by carrier ID when records exist with null carrier ref** — should not return those records

### 5.3 Recommended Test

```java
@Test
@DisplayName("should save successfully with empty carrierReferenceNumber (GSI sort key)")
void shouldSaveWithEmptyCarrierReferenceNumber() {
    String bookingId = randomId();
    String seq = "m_" + System.currentTimeMillis() + "_REQUEST_" + bookingId;
    BookingDetail detail = buildBookingDetail(bookingId, seq);
    detail.setCarrierId("CARRIER-100");
    detail.setCarrierReferenceNumber(""); // empty string — was causing DynamoDbException
    detail.setInttraReferenceNumber("IRN-" + randomId());
    
    // Should NOT throw DynamoDbException
    assertDoesNotThrow(() -> dao.save(detail));
    
    // Verify the record was saved
    BookingDetail found = dao.findByBookingIdSequenceNumber(bookingId, seq);
    assertThat(found).isNotNull();
    assertThat(found.getCarrierReferenceNumber()).isNull(); // empty → null via converter
}

@Test
@DisplayName("should save successfully with null carrierReferenceNumber")
void shouldSaveWithNullCarrierReferenceNumber() {
    String bookingId = randomId();
    String seq = "m_" + System.currentTimeMillis() + "_REQUEST_" + bookingId;
    BookingDetail detail = buildBookingDetail(bookingId, seq);
    detail.setCarrierId("CARRIER-100");
    detail.setCarrierReferenceNumber(null);
    detail.setInttraReferenceNumber("IRN-" + randomId());
    
    assertDoesNotThrow(() -> dao.save(detail));
}
```

### 5.4 Running the Integration Tests

`BookingDetailDaoIT` is a failsafe integration test (`@Tag("integration")`,
`*IT.java`) that runs against embedded **DynamoDB Local**. It is excluded from
the Surefire (unit) run and executes in the `integration-test`/`verify` phase.

**Run only this test class (fastest — skips unit tests):**
```bash
mvn -pl booking verify \
  -Dsurefire.skip=true \
  -Dit.test=BookingDetailDaoIT \
  -DfailIfNoTests=false
```
- `-pl booking` — build only the booking module (deps resolved from `~/.m2`).
- `-Dsurefire.skip=true` — skip the Surefire (unit) phase so only failsafe runs.
- `-Dit.test=BookingDetailDaoIT` — narrow failsafe to this class
  (use `-Dit.test=BookingDetailDaoIT$EmptyStringGsiKeyTests` for just the
  empty-string cases, or `-Dit.test='*IT'` for all booking ITs).
- `-DfailIfNoTests=false` — don't fail when Surefire matches nothing.

**Run the full booking integration suite:**
```bash
mvn -pl booking verify
```
> Requires AWS credentials for the Dev/Engineering account — the TestNG
> integration suite (`FlowTest`, `BookingServiceIntegrationTest`, …) calls
> live alpha network services and DynamoDB Dev. Profile used:
> `081020446316_INTTRA-Dev-Engg` (`us-east-1`).

**Verified results for the empty-string fix (single class, DynamoDB Local):**

| Stage | Command | Result |
|-------|---------|--------|
| Before fix (red) | `-Dit.test=BookingDetailDaoIT` on the test-only commit | `Tests run: 42, Failures: 6, Errors: 1` — every empty-string GSI key threw `DynamoDbException: ... cannot contain an empty string value` |
| After fix (green) | `-Dit.test=BookingDetailDaoIT` with the converter applied | `EmptyStringGsiKeyTests: Tests run: 8, Failures: 0`; class total `Tests run: 42, Failures: 0, Errors: 0`; **BUILD SUCCESS** |

**Full-suite `mvn -pl booking verify` (with the fix applied, 2026-06-15, Dev profile):**

| Phase | Framework fork | Tests run | Failures | Skipped |
|-------|----------------|-----------|----------|---------|
| Surefire (unit) | JUnit | 1975 | 0 | 1 |
| Surefire (unit) | TestNG | 983 | 0 | 9 |
| Failsafe (IT) | JUnit (`*IT`) | 150 | 0 | 0 |
| Failsafe (IT) | TestNG suite | 149 | 2 † | 0 |
| **Total** | | **3257** | **2 † (flaky)** | **10** |

The 8 new `EmptyStringGsiKeyTests` are part of the 150 JUnit IT count
(`BookingDetailDaoIT` is now 42 tests, all green).

† **Both failures are pre-existing flaky split tests, not related to this fix:**
- `FlowTest.doTest` on `05_split_decline_no_inttra_ref` — `expected [PENDING] but found [REQUEST]` (async state-propagation timing).
- `BookingServiceIntegrationTest.testRequestConfirmSplit` — `ConditionalCheckFailedException` in the split save path (optimistic-lock race; the service already retries on this).

Both **passed on isolated re-run** with the fix in place
(`-Dit.test=BookingServiceIntegrationTest#testRequestConfirmSplit` → BUILD SUCCESS;
`-Dit.test=FlowTest` → TestNG suite 983 tests, 0 failures). The
`NullifyEmptyStringConverter` only rewrites empty-string GSI keys to NULL;
it does not touch booking state, the primary key, or the version attribute
that these split assertions depend on.

---

## 6. Related Context

### 6.1 Registration Module Precedent

The `registration` module already uses `NullifyEmptyStringConverter` on its model:
```java
// RegistrationDetail.java:300
@DynamoDbConvertedBy(NullifyEmptyStringConverter.class)
public String getScacCode() { return scacCode; }
```

This confirms the pattern is established and the converter is production-tested.

### 6.2 Release Checkout (2026-06-13)

The [production release checkout](2026-06-13-booking-prod-release-checkout.md) on 2026-06-13 found **zero new exception types**. This exception appeared 2 days later (2026-06-15), confirming it's a data-dependent issue that requires specific input conditions (empty carrier reference number) to trigger.

### 6.3 Old SDK v1 Behavior Confirmation

Reviewing the pre-upgrade `BookingDetailDao` (commit `c76288edb7`), the old code used `DynamoDBMapper` which has well-documented behavior of omitting empty strings:
> "AWS SDK v1 DynamoDBMapper treats empty strings as null values and does not persist them." — AWS Documentation

No explicit empty-string handling was present in the old model either — it relied entirely on SDK v1's implicit behavior.

---

## 7. Impacted Requests & Client Details

### 7.1 Affected Client

| Detail | Value |
|--------|-------|
| **Client ID** | `822415-31610` |
| **Company ID** | `822415` |
| **User-Agent** | `RestSharp/106.11.7.0` (automated API integration) |
| **Endpoint** | `POST /booking/request` |
| **Total Failed Requests** | **268** (since deployment June 13 noon UTC through June 15 ~15:00 UTC) |
| **Total HTTP 500 Responses** | **458** (includes retries and other 500s) |
| **Other Clients Affected** | **NONE** — all 268 empty-string errors are from this single client |

### 7.2 Failure Timeline (Hourly Distribution — UTC)

| Hour (UTC) | Failed Requests | Notes |
|------------|----------------|-------|
| 2026-06-14 15:00 | 1 | First occurrence (~3h after deployment) |
| 2026-06-14 19:00 | 2 | |
| 2026-06-15 02:00 | 1 | |
| 2026-06-15 03:00 | 9 | |
| 2026-06-15 05:00 | 2 | |
| **2026-06-15 06:00** | **79** | **Peak hour** — business hours begin for client |
| 2026-06-15 07:00 | 50 | |
| 2026-06-15 08:00 | 25 | |
| 2026-06-15 09:00 | 16 | |
| 2026-06-15 10:00 | 38 | |
| 2026-06-15 11:00 | 19 | |
| 2026-06-15 12:00 | 16 | |
| 2026-06-15 13:00 | 1 | |
| 2026-06-15 14:00 | 9 | |
| **Total** | **268** | **Still ongoing** |

### 7.3 Error Amplification

Each failed request generates **multiple error log entries** due to the retry and error-handling logic:

| Log Entry | Count | Per Request |
|-----------|-------|-------------|
| DynamoDbException (GSI empty string) | 268 | 1 (final exception after retries) |
| "Retries exhausted for workflowId" | 270 | 1 |
| "Exception while calling S3 putObject" | 269 | 1 |
| "Attempting Retry" | ~536 | ~2 (retries 2 and 3) |

**Retry configuration:** `dynamoExceptionMaxRetryCount: 3` — each request is attempted 3 times before failing.

### 7.4 S3 Error Recovery — DOUBLE FAILURE

The error recovery mechanism (`BookingService.newBookingDetail()` lines 333-339) saves failed booking data to S3 at:
```
s3://inttra2-pr-workspace/dynamo_error/<workflowId>
```

**However, this is also failing:**

| Issue | Detail |
|-------|--------|
| **S3 Bucket** | `s3://inttra2-pr-workspace` |
| **S3 Key Prefix** | `dynamo_error/` |
| **WorkflowId for API requests** | `""` (empty string — from `Booking.getWorkflowId()` which returns `EMPTY_STR` when metadata has no workflowId) |
| **Resulting S3 Key** | `dynamo_error/` + `""` = `dynamo_error/` (invalid — treated as prefix, not object) |
| **S3 putObject failures** | **269** (matching the number of failed requests) |
| **S3 object at `dynamo_error/`** | ❌ NOT FOUND — writes are failing |
| **Data Loss** | ⚠️ **YES — 268 failed booking request payloads are permanently lost** |

**Only one post-deployment object exists** in `dynamo_error/`:
- Key: `59f5d33d-36cd-4fd1-b13b-5e458110e246` (an EDI request with a real workflowId)
- This is a **different** DynamoDbException (carrierReferenceNumber was `ZIMUHFA4402681`, not empty)
- State: PENDING, Carrier: ZIM (ZIMU), inttraRef: 2109625678

### 7.5 Identifying the Failed Bookings

Since both DynamoDB and S3 writes failed, the failed booking data is **not persisted anywhere**. To identify what the client was trying to submit:

1. **Contact Company 822415** — They will have their own records of what they submitted via their RestSharp API integration
2. **Check application INFO logs** — The `BookingService.request()` may log the incoming payload at INFO level before the save attempt
3. **Check inbound metrics** — The 268 failed requests are all `POST /booking/request` from the same client

---

## 8. Action Items

| # | Action | Priority | Owner | Status |
|---|--------|----------|-------|--------|
| 1 | Apply `@DynamoDbConvertedBy(NullifyEmptyStringConverter.class)` to `getCarrierReferenceNumber()` | **P0 — CRITICAL** | Dev Team | ✅ Done (commit `4437943641`) |
| 2 | Apply converter to other at-risk GSI key fields (`shipmentId`, `carrierScac`, `carrierId`) | P1 — URGENT | Dev Team | ✅ Done (commit `4437943641`) |
| 3 | Add integration tests for empty-string GSI key save scenarios | P1 — URGENT | Dev Team | ✅ Done (commit `4d58ac19d0`) |
| 4 | Fix S3 error recovery: handle empty workflowId (generate UUID fallback) | P1 — URGENT | Dev Team | 🔴 Pending |
| 5 | Notify company 822415 — 268 booking requests failed, ongoing | **P0 — CRITICAL** | Support | 🔴 Pending |
| 6 | Investigate if client can re-submit the 268 failed requests after fix deployment | P1 — URGENT | Support | 🔴 Pending |
| 7 | Audit other modules' DynamoDB models for similar empty-string GSI key risks | P2 — HIGH | Dev Team | 🔴 Pending |
| 8 | Fix `LocationAdditionalInfo.getCountryISO2Code()` Jackson `Optional` serialization (see Section 12) | P2 — HIGH | Dev Team | 🔴 Pending |

---

## 9. Commands Used for Investigation

### 9.1 Environment

| Setting | Value |
|---------|-------|
| **AWS Profile** | `642960533737_INTTRA2-QATeam` |
| **Region** | `us-east-1` |
| **Log Group** | `inttra2-pr-lg-bkapi` |
| **S3 Bucket** | `inttra2-pr-workspace` |
| **Time Window** | 2026-06-13 16:00 UTC — 2026-06-15 15:00 UTC |
| **S3 Error Path** | `s3://inttra2-pr-workspace/dynamo_error/` |

### 9.2 CloudWatch Insights Queries

**Total empty string GSI exceptions:**
```
fields @timestamp, @message
| filter @message like /empty string value.*carrierReferenceNumber/
| stats count(*) as total
```
Result: **268**

**Exceptions by client/company:**
```
fields @timestamp, @message
| filter @message like /empty string value.*carrierReferenceNumber/
| parse @message /Client: (?<clientId>\S+) COMPANY: (?<companyId>\S+)/
| stats count(*) as count by clientId, companyId
| sort count desc
```
Result: All 268 from Client `822415-31610`, Company `822415`

**Hourly distribution:**
```
fields @timestamp
| filter @message like /empty string value.*carrierReferenceNumber/
| stats count(*) as count by bin(1h)
| sort count desc
```

**Retries exhausted count:**
```
fields @timestamp, @message
| filter @message like /Retries exhausted for workflowId/
| stats count(*) as total
```
Result: **270**

**S3 putObject failures:**
```
fields @timestamp, @message
| filter @message like /Exception while calling S3 putObject/
| stats count(*) as total
```
Result: **269**

**Raw "Retries exhausted" messages (to verify workflowId is empty):**
```
fields @timestamp, @message
| filter @message like /Retries exhausted for workflowId/
| sort @timestamp desc
| limit 10
```

**HTTP 500 responses for this client:**
```
fields @timestamp, @message
| filter @message like /822415-31610/ and @message like /500/ and @message like /POST.*booking.*request/
| stats count(*) as total
```
Result: **458**

### 9.3 S3 Commands

**List all objects in dynamo_error/ prefix:**
```bash
aws s3 ls s3://inttra2-pr-workspace/dynamo_error/ \
  --region us-east-1 \
  --profile 642960533737_INTTRA2-QATeam
```

**Check for post-deployment objects:**
```bash
aws s3 ls s3://inttra2-pr-workspace/dynamo_error/ \
  --region us-east-1 \
  --profile 642960533737_INTTRA2-QATeam \
  | grep "2026-06-1[3-5]"
```
Result: 1 object — `59f5d33d-36cd-4fd1-b13b-5e458110e246` (EDI request, different error)

**Check for empty workflowId key (`dynamo_error/null` and `dynamo_error/`):**
```bash
aws s3api head-object --bucket inttra2-pr-workspace \
  --key "dynamo_error/null" \
  --region us-east-1 \
  --profile 642960533737_INTTRA2-QATeam
# Result: 404 Not Found

aws s3api head-object --bucket inttra2-pr-workspace \
  --key "dynamo_error/" \
  --region us-east-1 \
  --profile 642960533737_INTTRA2-QATeam
# Result: 404 Not Found
```

**Inspect the one post-deployment S3 object:**
```bash
aws s3 cp s3://inttra2-pr-workspace/dynamo_error/59f5d33d-36cd-4fd1-b13b-5e458110e246 - \
  --region us-east-1 \
  --profile 642960533737_INTTRA2-QATeam \
  | python -c "import json,sys; d=json.load(sys.stdin); ..."
```
Result: EDI booking (ZIM carrier), carrierRef=`ZIMUHFA4402681` (NOT empty — different error)

### 9.4 Code Analysis Commands

**Git history of BookingDetailDao:**
```bash
git log --oneline -20 -- booking/src/main/java/com/inttra/mercury/booking/dao/BookingDetailDao.java
```

**Pre-upgrade code (SDK v1):**
```bash
git show c76288edb7:booking/src/main/java/com/inttra/mercury/booking/dao/BookingDetailDao.java
```

**Production config — retry count and S3 bucket:**
```bash
grep -n "dynamoException\|s3WorkSpace" booking/conf/prod/config.yaml
# dynamoExceptionMaxRetryCount: 3
# s3WorkSpaceLocation: inttra2-pr-workspace
```

**Search for NullifyEmptyStringConverter usage:**
```bash
grep -rn "NullifyEmptyStringConverter" --include="*.java" booking/ registration/
```

---

## 10. QA Environment Investigation

### 10.1 QA Test: Booking 2010418020

QA reported successfully creating booking `2010418020` with an empty `carrierReferenceNumber` via API. Investigation reveals the booking **did NOT actually save with an empty `carrierReferenceNumber`**.

| Detail | Value |
|--------|-------|
| **InttraRef** | `2010418020` |
| **BookingId** | `2e94fcdfab2f4038aa90753484842c01` |
| **Client** | `802442-77383`, Company `802442` |
| **Carrier** | `802435` (TESTqaCARRIER EDIF, SCAC: CA20) |
| **Submitted `carrierReferenceNumber`** | `""` (empty string — confirmed in payload log) |
| **Stored `carrierReferenceNumber`** | `"EDIF1000106046ALL"` (**NOT empty**) |

### 10.2 Why QA Succeeded: Rapid Reservation

The `BookingService.request()` method at lines 758-867 includes a **Rapid Reservation** feature:

```java
// BookingService.java:758-762
Optional<BRReference> carrierBookingNumberReference = contract.getReferences().stream()
    .filter(reference -> BRReferenceType.BookingNumber.equals(reference.getReferenceType()))
    .findFirst();

if (!carrierBookingNumberReference.isPresent()) {
    contract = assignRapidReservedCarrierBookingNumber(contract, attributes, metaData);
}
```

When no `BookingNumber` reference is present, the method calls `assignRapidReservedCarrierBookingNumber()`, which:
1. Generates a carrier booking number from the carrier's configuration
2. Sets it on the contract at line 867: `bookingRequestContract.setCarrierReferenceNumber(rrCarrierReferenceNumber)`

**QA carrier 802435** has Rapid Reservation enabled → empty `""` was replaced with `"EDIF1000106046ALL"` **before** the DynamoDB save. CloudWatch confirms:

```
INFO  BookingService: Rapid reserved carrier booking number for 
  CarrierId: 802435, BookerId 802442, assigned: EDIF1000106046ALL
```

### 10.3 Why Prod Fails: No Rapid Reservation

**Prod client 822415's carrier** either:
1. Does **NOT** have Rapid Reservation enabled → `assignRapidReservedCarrierBookingNumber()` doesn't generate a number → `carrierReferenceNumber` stays as `""`
2. OR sends a `BookingNumber` reference in the request → skips rapid reservation entirely → `carrierReferenceNumber` stays as `""`

In either case, the `carrierReferenceNumber` remains as `""` when `BookingDetail.setCarrierReferenceNumber()` is called at line 276, and DynamoDB rejects it.

### 10.4 QA Test Does NOT Disprove the Analysis

The QA test confirms that:
- ✅ The booking flow accepts empty `carrierReferenceNumber` in the API request (no validation rejects it)
- ✅ The Rapid Reservation feature masks the empty-string issue for carriers that support it
- ✅ The DynamoDB GSI configuration in QA is identical to prod (same 4 GSIs)
- ✅ Without Rapid Reservation, the empty string would reach DynamoDB and fail

**The fix (`NullifyEmptyStringConverter`) is the correct solution** because it handles the empty-string-to-null conversion at the persistence layer, regardless of whether Rapid Reservation is enabled.

---

## 12. Jackson Optional Serialization Exception (Pre-Existing)

### 12.1 Exception Details

```
com.fasterxml.jackson.databind.exc.InvalidDefinitionException: 
Java 8 optional type `java.util.Optional<java.lang.String>` not supported by default: 
add Module "com.fasterxml.jackson.datatype:jackson-datatype-jdk8" to enable handling 
(through reference chain: 
  com.inttra.mercury.booking.model.BookingDetail["enrichedAttributes"]
  ->com.inttra.mercury.booking.outbound.model.EnrichedAttributes["transactionLocationInfoList"]
  ->java.util.ArrayList[0]
  ->com.inttra.mercury.booking.model.INTTRACommon.Artifacts.LocationAdditionalInfo["countryISO2Code"])
```

### 12.2 Root Cause

`LocationAdditionalInfo.getCountryISO2Code()` (line 65) returns `Optional<String>`. Jackson discovers this public getter via Lombok `@Data` and attempts to serialize it. The `Json.java` utility (line 23) uses a plain `ObjectMapper` with only `JavaTimeModule` registered — **no `Jdk8Module`** for `Optional` support.

```java
// Json.java:23 — missing Jdk8Module
private static final ObjectMapper objectMapper = new ObjectMapper();

// LocationAdditionalInfo.java:65 — returns Optional<String>
public Optional<String> getCountryISO2Code() { ... }
```

### 12.3 Trigger Path

This exception occurs **only** in the DynamoDB error-recovery path at `BookingService.newBookingDetail()`:

```java
// BookingService.java:334 — serializes BookingDetail for error logging
log.error("Error occurred for workflowId {} and data {}", 
    Booking.getWorkflowId(metaData), Json.toJsonString(detail));  // ← fails here

// BookingService.java:336 — also serializes for S3 error storage
s3WorkspaceService.putObject(..., "dynamo_error/...", Json.toJsonString(detail));  // ← also fails
```

The serialization chain: `BookingDetail` → `enrichedAttributes` (`EnrichedAttributes`) → `transactionLocationInfoList` → `LocationAdditionalInfo` → `getCountryISO2Code()` → `Optional<String>` → **Jackson fails**.

### 12.4 Pre-Existing vs Upgrade-Related

| Aspect | Detail |
|--------|--------|
| **Pre-existing?** | ✅ **YES** — 5 occurrences before deployment (June 10-13), same error path |
| **Related to SDK upgrade?** | **INDIRECTLY** — upgrade caused 268 DynamoDB failures → triggered error recovery 269× → exposed this latent bug |
| **Test gap?** | No test serializes a `BookingDetail` with populated `enrichedAttributes` containing `LocationAdditionalInfo` with country data |

### 12.5 Occurrence Counts

| Period | Count | Context |
|--------|-------|---------|
| **Pre-deployment** (June 10–13 noon) | 5 | All from `[processor]` (EDI), triggered by `ConditionalCheckFailedException` (optimistic locking) |
| **Post-deployment** (June 13 noon – June 15 17:00) | 270 | 269 from client 822415-31610 (empty carrierReferenceNumber), 1 from `[processor]` (ConditionalCheckFailedException) |

### 12.6 Affected Bookings

**Post-deployment EDI booking** (the 1 non-822415 occurrence):

| Detail | Value |
|--------|-------|
| **WorkflowId** | `de3344e0-5b4b-41be-b2eb-b031202fc0db` |
| **InttraRef** | `2107555939` |
| **State** | CONFIRM (carrier confirmation inbound) |
| **Carrier** | Company `800388` (SCAC: `cnaj5171` — CMA CGM based on EDI filename) |
| **DynamoDB Error** | `ConditionalCheckFailedException` (optimistic locking — version conflict) |
| **EDI File** | `301_IFTMBC/20260614/carriers/cnaj5171/IFTMBC_202606142137_4527329884.edi` |
| **S3 Error Object** | `s3://inttra2-pr-workspace/dynamo_error/de3344e0-5b4b-41be-b2eb-b031202fc0db` (7546 bytes — JSON serialization failed but S3 write used the workflowId key, so partial/corrupt data may exist) |

**Pre-deployment bookings** (5 occurrences, all EDI processor):

| WorkflowId | Timestamp (UTC) |
|-----------|-----------------|
| `83c681ed-0c17-45e4-ba6a-f488a9011011` | 2026-06-10 13:51:22 |
| `b6de2c6b-fa72-4df1-bb5e-deabe088d88f` | 2026-06-11 22:11:18 |
| `46e4343a-abdc-444c-bd12-299b58ca4b94` | 2026-06-11 23:52:48 |
| `172b81ed-b51b-4f9c-9721-3a6cd23137fa` | 2026-06-11 23:52:56 |
| `f7124c93-1275-4c04-bc5f-65e859c0c0b4` | 2026-06-11 23:52:56 |
| `8c3d08fa-e34d-4db7-8659-b3abc19f0b1f` | 2026-06-12 07:58:38 |

### 12.7 Cascading Failure Chain

For the 268 API requests from client 822415, the full failure chain is:

```
1. POST /booking/request with carrierReferenceNumber: ""
2. → BookingService.newBookingDetail() → BookingDetailDao.save()
3. → DynamoDB putItem FAILS: empty string on GSI sort key carrierReferenceNumber
4. → Retry 3 times → all fail (same data, same error)
5. → "Retries exhausted" → attempt error recovery:
   a. Json.toJsonString(detail) → FAILS: Optional<String> in LocationAdditionalInfo
   b. S3 putObject → FAILS: both serialization failure AND empty workflowId key
6. → Exception thrown → HTTP 500 returned to client
```

**Triple failure**: DynamoDB → JSON serialization → S3 save. The booking data is permanently lost.

### 12.8 Fix Options

**Option A — `@JsonIgnore` on `getCountryISO2Code()` (Recommended)**

```java
@JsonIgnore
public Optional<String> getCountryISO2Code() { ... }
```

This is the simplest fix. `getCountryISO2Code()` is a **computed/derived** method (not a stored field) that extracts the ISO2 code from the `country.identifiers` list. It should not be serialized — the underlying `country` field is already serialized. Adding `@JsonIgnore` prevents Jackson from attempting to serialize the `Optional` return type.

**Option B — Register `Jdk8Module` in `Json.java`**

```java
static {
    objectMapper.registerModule(new JavaTimeModule());
    objectMapper.registerModule(new com.fasterxml.jackson.datatype.jdk8.Jdk8Module()); // ADD
    objectMapper.enable(DeserializationFeature.READ_UNKNOWN_ENUM_VALUES_AS_NULL);
}
```

This teaches Jackson how to serialize `Optional` types globally. However, this may have broader side effects on other serialization paths using `Json.java`.

**Option C — Both A and B**

Apply `@JsonIgnore` to `getCountryISO2Code()` AND register `Jdk8Module` in `Json.java` for defense-in-depth against future `Optional` return types.

### 12.9 CloudWatch Queries for This Exception

**Count InvalidDefinitionException occurrences:**
```
fields @timestamp, @message
| filter @message like /InvalidDefinitionException/
| stats count(*) as total
```

**InvalidDefinitionException by client/company:**
```
fields @timestamp, @message
| filter @message like /InvalidDefinitionException/
| parse @message /Client: (?<clientId>\S+) COMPANY: (?<companyId>\S+)/
| stats count(*) as count by clientId, companyId
| sort count desc
```

**Context around a specific workflowId (replace `<WORKFLOW_ID>`):**
```
fields @timestamp, @message
| filter @message like /<WORKFLOW_ID>/
| sort @timestamp asc
| limit 50
```

**DynamoDB error type for a specific workflowId:**
```
fields @timestamp, @message
| filter @message like /<WORKFLOW_ID>/ 
  and (@message like /DynamoDb/ or @message like /Retries exhausted/ or @message like /Error occurred/)
| sort @timestamp asc
| limit 20
```

**Pre-deployment baseline comparison (change start/end times as needed):**
```
fields @timestamp, @message
| filter @message like /InvalidDefinitionException/ and @message like /countryISO2Code/
| stats count(*) as total
```

---

## 13. Conclusion

This is a **confirmed HIGH-severity regression from the AWS SDK v2 upgrade** with **data loss**. 

**268 booking requests** from Company 822415 have failed since deployment, and the error recovery (S3 save) is also failing — meaning the failed booking data is **permanently lost**. The issue is **ongoing** and will continue to affect any API client that submits a booking without a `carrierReferenceNumber`.

The primary fix (`NullifyEmptyStringConverter`) is applied in commit `4437943641` and verified with integration tests in commit `4d58ac19d0`.

A secondary pre-existing bug was uncovered: `LocationAdditionalInfo.getCountryISO2Code()` returns `Optional<String>` which Jackson cannot serialize, breaking the entire error-recovery path (failed booking data logging + S3 storage). This existed before the upgrade (5 pre-deployment occurrences) but was massively amplified by the DynamoDB empty-string failures (269 additional occurrences).

**Immediate actions required:**
1. **~~Hotfix deployment~~ ✅** — `NullifyEmptyStringConverter` applied to all GSI key fields (commit `4437943641`)
2. **Client notification** — Company 822415 needs to be informed about 268+ failed bookings and asked to re-submit after fix
3. **Fix S3 error recovery** — `Booking.getWorkflowId()` returns `""` for API requests, making the S3 key invalid
4. **Fix Jackson Optional serialization** — Add `@JsonIgnore` to `LocationAdditionalInfo.getCountryISO2Code()` to unblock the error-recovery path
