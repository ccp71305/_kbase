# Visibility Matcher — Old Booking Records with Invalid Audit Timestamp Format

**Date**: 2026-05-15  
**Module**: `visibility` (consumer) / `booking` (source)  
**Agent Model**: Claude Opus 4.6 (model ID: claude-opus-4.6)  
**Session ID**: `e526ff4ca5174854`  
**Related**: `booking/docs/2026-05-06-visibility-audit-unconvert-issue-copilot.md` (previous fix)

---

## 1. Reported Error

QA reported failures in the Visibility Matcher for a booking created **today** (2026-05-15):

- **Container No**: CONT2711952  
- **Booking Number**: EDIF1000098366ALL  
- **IR**: 2010326020  

CloudWatch log group: `inttra2-ecs-logs`, log stream: `VisibilityMatcher-latest-qa`

```
Container Event Id: ce:XXXX - Failed Matching Processor

com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMappingException:
  BookingDetailVisibility[audit]; could not unconvert attribute

Caused by: java.time.format.DateTimeParseException:
  Text '2026-05-12T05:57:03.018+0000' could not be parsed, unparsed text found at index 10
    at OffsetDateTimeTypeConverter.unconvert(...)
```

**7 instances** of this exception found in the last 24 hours. All 7 reference the **same** poisoned timestamp: `2026-05-12T05:57:03.018+0000`.

---

## 2. Summary

### What is happening?

The Visibility Matcher crashes when processing **new** container events (created today, 2026-05-15) because the matching workflow reads an **old** booking (IR 2010312288, created 2026-05-12) from DynamoDB. That old booking's `audit.createdDateUtc` is stored as `"2026-05-12T05:57:03.018+0000"` — a format the visibility module's `OffsetDateTimeTypeConverter` cannot parse.

### Why does a new container event read an old booking?

The Visibility Matcher uses **Elasticsearch** to find all related transactions (bookings, SIs, BLs) that share common references (carrier booking number, BOL, etc.) with the incoming container event. In QA, many test bookings reuse the **same BOL**: `BM_BK_TT_Web_07`. The ES query returns up to **10,000** matching bookings across all time. The matcher then attempts to load **every** matched booking from DynamoDB — including old ones created before the fix was deployed.

### Why does the old booking have the `+0000` format?

The `AuditAttributeConverter` fix (decoupling DynamoDB writes from REST API formatting) was deployed to QA on **2026-05-13 00:40:53**. IR 2010312288 was created on **2026-05-12**, during the `+0000` poisoning window (May 5–13), when the `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ")` annotation was coupled to both REST API and DynamoDB write paths.

### Is the reported booking (IR 2010326020) itself broken?

**No.** The reported booking was created after the fix and has a correct DynamoDB audit timestamp:

```
DynamoDB: 2026-05-15T12:22:26.315472624Z  ← correct Z format
REST API: 2026-05-15T12:22:26.315+0000    ← correct for REST
```

The error occurs when the matcher reads a **different** booking (IR 2010312288) that ES found via the shared BOL `BM_BK_TT_Web_07`.

---

## 3. Root Cause Chain

```
1. Container event arrives for new booking (IR 2010326020)
     ↓
2. MatchingProcessor.process() → TransactionSearchService.findMatchingTransactions()
     ↓
3. ES query searches _all index for matching Bookings/SIs/BLs
   Query uses: carrierId=802435, references=[EDIF1000098366ALL, BM_BK_TT_Web_07]
   Returns 196 hits (136 Bookings, 16 SIs, 44 BLs) — all sharing BOL BM_BK_TT_Web_07
     ↓
4. enrichContainerEvent() iterates ALL 136 Booking hits
   For each Booking hit, calls bookingService.getBookingByInttraRef(inttraRef)
     ↓
5. BookingDao.findByInttraReferenceNumber() queries DynamoDB
   - Step 1: GSI (INTTRA_REFERENCE_NUMBER_INDEX) → gets bookingId + sequenceNumber
             (GSI does NOT project the audit field — no crash here)
   - Step 2: findBookingDetail() reads FULL record from main table via query()
             DynamoDBMapper.query() → unconverts ALL attributes including audit Map
     ↓
6. CRASH: SDK v1 DynamoDBMapper → BookingDetailVisibility model → old OffsetDateTimeTypeConverter
   Old converter calls LocalDate.parse() with ISO_DATE_TIME → cannot parse +0000 suffix
```

### Stack trace (key frames)

```
at OffsetDateTimeTypeConverter.unconvert(...)
at DynamoDBMapperTableModel.unconvert(DynamoDBMapperTableModel.java:271)
at DynamoDBMapper.privateMarshallIntoObject(DynamoDBMapper.java:472)
at DynamoDBMapper.query(DynamoDBMapper.java:1619)
at DynamoDBCrudRepository.query(DynamoDBCrudRepository.java:380)
at BookingDao.findBookingDetail(BookingDao.java:118)          ← reads full record
at BookingDao.findByInttraReferenceNumber(BookingDao.java:49)
at BookingDao.findBookingByInttraReference(BookingDao.java:81)
at BookingServiceImpl.getBookingByInttraRef(BookingServiceImpl.java:22)
at TransactionSearchService.addInttraReference(TransactionSearchService.java:204) ← iterates ES hits
at TransactionSearchService.enrichContainerEvent(TransactionSearchService.java:177)
at TransactionSearchService.findMatchingTransactions(TransactionSearchService.java:61)
at MatchingProcessor.process(MatchingProcessor.java:105)
```

---

## 4. Poisoned Records in QA DynamoDB

### Confirmed poisoned (will crash visibility)

| IR | bookingId | createdDateUtc (DynamoDB) | Format |
|----|-----------|--------------------------|--------|
| 2010312288 | 014ca0aa46f94b1d8fc9cad5bc67231d | `2026-05-12T05:57:03.018+0000` | `+0000` (millis) |
| 2010311223 | bd2a2573c3eb41d098f7bea2a73c7cd6 | `2026-05-12T03:47:56.506+0000` | `+0000` (millis) |
| 2010312007 | b2611f454c354d7ab7d13e8111a2e867 | `2026-05-12T00:53:13.576+0000` | `+0000` (millis) |
| 2010292107 | *(checked)* | `05/05/2026 15:46:59` | `MM/dd/yyyy` ⚠️ |
| 2010291106 | *(checked)* | `05/05/2026 15:35:13` | `MM/dd/yyyy` ⚠️ |

### Confirmed clean (will NOT crash visibility)

| IR | createdDateUtc (DynamoDB) | Format |
|----|--------------------------|--------|
| 2010326020 | `2026-05-15T12:22:26.315472624Z` | `Z` (nano) — post-fix |
| 2010292010 | `2026-05-05T12:41:03.862Z` | `Z` (millis) |
| 2010303010 | `2026-05-09T01:03:13.956437035Z` | `Z` (nano) |
| 2010302297 | `2026-05-08T08:13:10.31002393Z` | `Z` (nano) |
| 2010305010 | `2026-05-10T00:57:27.009675205Z` | `Z` (nano) |
| 2010308010 | `2026-05-11T01:20:53.215804156Z` | `Z` (nano) |
| 2010183241 | `2026-04-07T02:04:14.375494307Z` | `Z` (nano) |
| 2010202035 | `2026-04-13T11:32:34.961718264Z` | `Z` (nano) |
| 2010177141 | `2026-04-06T08:56:10.467592846Z` | `Z` (nano) |

### Key observations

1. The **3 confirmed `+0000` poisoned records** are all from **2026-05-12** — one day before the fix deployment (2026-05-13).
2. Two additional records (IR 2010292107, 2010291106) from **2026-05-05** have an entirely different invalid format: `MM/dd/yyyy HH:mm:ss`. This format would also crash the old converter.
3. The ES query returns **136 Booking hits** for BOL `BM_BK_TT_Web_07`. Of these 136, at least **5 are poisoned**. Any container event matching this BOL will crash.
4. There may be additional poisoned records among the untested bookings from the 03/27–04/16 and 05/05–05/13 poisoning windows.

---

## 5. Audit Timestamp Format Timeline

This timeline is from the previous analysis (`2026-05-06-visibility-audit-unconvert-issue-copilot.md`) and explains why different periods produced different formats:

| Period | Format | Mechanism | Visibility can read? |
|--------|--------|-----------|---------------------|
| Pre-upgrade (before 03/27) | `Z` (nano) | SDK v1 `OffsetDateTimeTypeConverter.convert()` → `ISO_DATE_TIME` | ✅ Yes |
| 03/27 – 04/16 | `+0000` (millis) | `@JsonFormat(SSSZ)` coupled to DynamoDB via Jackson in `AuditAttributeConverter` | ❌ No |
| 04/17 – 05/04 | `Z` (millis) | `@JsonFormat(SSSXXX)` data-format fix (produced `+00:00`, but `Z` in some cases) | ✅ Yes |
| 05/05 – 05/13 | `+0000` (millis) | `@JsonFormat(SSSZ)` after redshift revert | ❌ No |
| 05/13+ (fix deployed) | `Z` (nano) | Decoupled `DYNAMO_OBJECT_MAPPER` with `ISO_DATE_TIME` formatter | ✅ Yes |

**Note**: The `MM/dd/yyyy` format found on two records (IR 2010292107, 2010291106) does not match any known converter output. This may indicate a one-off code path or manual data modification during testing.

---

## 6. Why the Previous Fix Did Not Prevent This

The fix deployed on 2026-05-13 (`AuditAttributeConverter` decoupling) ensures that **new** bookings written to DynamoDB have the correct `Z` format. However:

1. **Old records are not migrated**: Bookings written during the two poisoning windows (03/27–04/16 and 05/05–05/13) retain their `+0000` timestamps in DynamoDB. The fix only affects **writes**, not existing data.
2. **Visibility uses old booking artifact**: `visibility-commons` depends on `booking:2.1.8.M` (see `visibility/visibility-commons/pom.xml` line 24). This published artifact contains the **old** `OffsetDateTimeTypeConverter` that lacks `+0000 → +00:00` normalization.
3. **ES cross-matching**: The matcher's ES query uses `size: 10000` and returns ALL bookings matching any shared reference. With QA test data reusing the same BOL (`BM_BK_TT_Web_07`), the query pulls in hundreds of bookings spanning months — including the poisoned ones.

---

## 7. Why This Appears on "New" Bookings

The error manifests on new bookings because:

1. QA creates a **new** booking (IR 2010326020) with BOL `BM_BK_TT_Web_07`
2. A container event triggers the matcher
3. ES returns **136 booking hits** — all sharing the same BOL
4. The matcher iterates ALL hits and tries to load each from DynamoDB
5. When it reaches IR 2010312288 (the poisoned record), the DynamoDBMapper crashes
6. The exception is logged against the **container event** being processed, making it look like the **new** booking is broken

The new booking itself is perfectly fine. The crash is caused by an old record that ES includes in the search results.

---

## 8. Affected Container Events

All 7 failing container events from CloudWatch logs share:

- **BOL**: `BM_BK_TT_Web_07`
- **Carrier**: inttraCompanyId `802435` (TESTqaCARRIER EDIF, SCAC: CA20)
- **Same poisoned timestamp**: `2026-05-12T05:57:03.018+0000`

The error occurs every time any container event with this BOL is processed, because the ES query will always return the poisoned booking IR 2010312288 in the results.

---

## 9. Possible Remediation Options

### Option A: Fix the poisoned DynamoDB records (QA data fix)

Directly update the 5 known poisoned records in DynamoDB to use `Z` format:
- `2026-05-12T05:57:03.018+0000` → `2026-05-12T05:57:03.018Z`
- `2026-05-12T03:47:56.506+0000` → `2026-05-12T03:47:56.506Z`
- `2026-05-12T00:53:13.576+0000` → `2026-05-12T00:53:13.576Z`
- `05/05/2026 15:46:59` → `2026-05-05T15:46:59.000Z`
- `05/05/2026 15:35:13` → `2026-05-05T15:35:13.000Z`

**Pros**: Immediate fix, no code change needed.  
**Cons**: Only fixes known records; there may be more. Does not prevent the same issue if it happens again.  
**Risk**: If done only in QA, production may still have poisoned records from the 03/27–04/16 window.

### Option B: Shadow the OffsetDateTimeTypeConverter in visibility-commons

Add a `+0000 → +00:00` normalization step to the converter used by `BookingDetailVisibility`. This mirrors what was already done in the booking module's converter.

**Pros**: Permanent fix; visibility can read all timestamp formats.  
**Cons**: Requires code change and redeployment of visibility services.

### Option C: Upgrade visibility-commons dependency to latest booking artifact

Update `visibility-commons/pom.xml` to use a newer `booking` artifact version that includes the fixed `OffsetDateTimeTypeConverter` with `+0000` normalization.

**Pros**: Gets all fixes from the booking module.  
**Cons**: Requires publishing a new booking artifact; may introduce other breaking changes. The visibility module is pending AWS 2.x upgrade and uses SDK v1 DynamoDBMapper — a wholesale upgrade is complex.

### Option D: Wrap the DynamoDB read in a try-catch (defensive)

In `TransactionSearchService.addInttraReference()`, catch the `DynamoDBMappingException` and log a warning instead of crashing the entire container event processing.

**Pros**: Prevents one bad record from blocking all matching; the matcher can still process the other 135 bookings.  
**Cons**: Does not fix the underlying data or converter issue; the poisoned booking will never be successfully read.

### Recommended approach

A combination of **Option A** (immediate data fix in QA to unblock testing) + **Option B or D** (code-level resilience for production) is recommended. A full audit of DynamoDB records with `+0000` or `MM/dd/yyyy` audit timestamps should be performed across all environments.

---

## 10. Key Files

| File | Role |
|------|------|
| `visibility/visibility-matcher/.../MatchingProcessor.java` | Entry point; `process()` at line 86; error log at line 144 |
| `visibility/visibility-matcher/.../TransactionSearchService.java` | ES search + DynamoDB enrichment; crash at line 204 (`bookingService.getBookingByInttraRef`) |
| `visibility/visibility-matcher/.../TransactionQueryUtil.java` | ES query builder; `RESULT_SIZE = 10000` at line 33 |
| `visibility/visibility-matcher/.../IndexAttributes.java` | ES field mappings per index type |
| `visibility/visibility-commons/.../BookingDao.java` | DynamoDB read; crash at line 118 (`findBookingDetail`) |
| `visibility/visibility-commons/.../BookingDetailVisibility.java` | Extends `BookingDetail` from `booking:2.1.8.M` with old converter |
| `visibility/visibility-commons/pom.xml` | Declares `booking:2.1.8.M` dependency (line 24) |
| `booking/.../AuditAttributeConverter.java` | The fix: decoupled DynamoDB/REST formatting |
| `booking/.../OffsetDateTimeTypeConverter.java` | Current version has `+0000` normalization; old `2.1.8.M` does not |
| `booking/docs/2026-05-06-visibility-audit-unconvert-issue-copilot.md` | Previous fix analysis |

---

## 11. ES Query That Returns Poisoned Records

The matcher builds this query for container event with BOL `BM_BK_TT_Web_07` and carrier `802435`:

```json
{
  "size": 10000,
  "query": {
    "bool": {
      "should": [
        {
          "bool": {
            "must": [
              { "term": { "_type": "Booking" } },
              { "range": { "lastModifiedDateUtc": { "gte": "now-400d" } } },
              { "match_phrase": { "carrierId": "802435" } }
            ],
            "should": [
              { "match_phrase": { "carrierReferenceNumber": "EDIF1000098366ALL" } },
              { "match_phrase": { "billOfLadingNumbers": "BM_BK_TT_Web_07" } }
            ],
            "minimum_should_match": 1
          }
        },
        {
          "bool": {
            "must": [
              { "term": { "_type": "si" } },
              { "range": { "lastModifiedDateUtc": { "gte": "now-400d" } } },
              { "match_phrase": { "carrierId": "802435" } }
            ],
            "should": [
              { "match_phrase": { "carrierBookingReference": "EDIF1000098366ALL" } },
              { "match_phrase": { "billOfLadingNumber": "BM_BK_TT_Web_07" } }
            ],
            "minimum_should_match": 1
          }
        },
        {
          "bool": {
            "must": [
              { "term": { "_type": "bl" } },
              { "range": { "lastModifiedDateUtc": { "gte": "now-400d" } } },
              { "match_phrase": { "carrierId": "802435" } }
            ],
            "should": [
              { "match_phrase": { "carrierBookingReference": "EDIF1000098366ALL" } },
              { "match_phrase": { "billOfLadingNumber": "BM_BK_TT_Web_07" } }
            ],
            "minimum_should_match": 1
          }
        }
      ]
    }
  },
  "_source": [
    "inttraReferenceNumber", "carrierReferenceNumber", "carrierId",
    "billOfLadingNumbers", "nonInttraBooking", "lastModifiedDateUtc",
    "billOfLadingNumber", "carrierBookingReference", "companyIds",
    "purchaseOrderNumber", "contractPartyReferenceNumber",
    "consigneeReferenceNumber", "shipperReferenceNumber",
    "freightForwarderRefNumber", "bookingShipmentId"
  ]
}
```

This returns **196 total hits** (136 Booking, 16 SI, 44 BL) — all because they share BOL `BM_BK_TT_Web_07` and carrier `802435`.

---

## 12. Conclusion

The visibility matcher crash is **not caused by the new booking** (IR 2010326020). It is caused by **old DynamoDB records** with invalid `audit.createdDateUtc` timestamps that were written during the two poisoning windows before the `AuditAttributeConverter` fix was deployed. These old records surface during matching because ES returns all bookings sharing common references (specifically the widely-reused QA test BOL `BM_BK_TT_Web_07`), and the matcher iterates every hit, loading full records from DynamoDB.

The immediate impact is limited to QA test data with the reused BOL. However, the same issue could occur in production if any bookings from the 03/27–04/16 or 05/05–05/13 windows share references with newer bookings and the visibility module's old converter encounters those poisoned records.
