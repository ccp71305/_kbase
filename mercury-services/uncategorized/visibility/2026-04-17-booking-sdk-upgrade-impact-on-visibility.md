# Impact Analysis: Booking AWS SDK v2 Upgrade on Visibility Module

> **Date**: 2026-04-17  
> **Module**: `visibility/` (AWS SDK v1) consuming `booking/` models (AWS SDK v2)  
> **Session ID**: `ad378beb151a432f`  
> **Agent Model**: Claude Opus 4.6  
> **Status**: Active  

---

## 1. Executive Summary

The booking module has been upgraded from AWS SDK v1 (`DynamoDBMapper`) to AWS SDK v2 (`Enhanced Client`) using `cloud-sdk-api` and `cloud-sdk-aws` libraries (commit `59ebf93a2aed`, reapply of `74f36e7a71fa`). The visibility module, which depends on `booking:2.1.8.M` and extends `BookingDetail` via `BookingDetailVisibility`, remains on AWS SDK v1 using the deprecated `dynamo-client` library.

This analysis documents **all breaking changes** — both the reported `DateTimeParseException` and several hidden issues that will surface when visibility uses the post-upgrade booking classes.

**Severity: HIGH** — Multiple compile-time and runtime failures confirmed.

---

## 2. Architecture: How Visibility Uses Booking

```
┌──────────────────────────────────────────────────────────┐
│  visibility-commons                                      │
│                                                          │
│  BookingDetailVisibility                                 │
│  ├── @DynamoDBTable(tableName="booking_BookingDetail")   │ ← SDK v1 annotation
│  └── extends BookingDetail                               │ ← from booking module
│                                                          │
│  BookingDao                                              │
│  ├── extends DynamoDBCrudRepository (dynamo-client, v1)  │
│  ├── uses DynamoDBMapper (SDK v1)                        │
│  └── calls bookingDetail.getHashKey() (REMOVED)          │
│                                                          │
│  Reads from DynamoDB table: booking_BookingDetail         │
│  (same data as BookingDetail but different table name)    │
└──────────────────────────────────────────────────────────┘
           ▲ depends on
┌──────────────────────────────────────────────────────────┐
│  booking module (UPGRADED to SDK v2)                     │
│                                                          │
│  BookingDetail                                           │
│  ├── @Table(name="BookingDetail") + @DynamoDbBean        │ ← cloud-sdk / SDK v2
│  ├── @DynamoDbPartitionKey on getBookingId()             │ ← SDK v2 annotation
│  ├── @DynamoDbConvertedBy(MetaDataConverter.class)       │ ← SDK v2 converter
│  └── implements Expires (no longer DynamoHashAndSortKey) │
│                                                          │
│  Writes to DynamoDB table: BookingDetail                 │
└──────────────────────────────────────────────────────────┘
```

**Key dependency**: `visibility-commons/pom.xml` → `booking:2.1.8.M`  
**Key class**: `BookingDetailVisibility extends BookingDetail` (empty subclass, only overrides table name)  
**Key DAO**: `BookingDao extends DynamoDBCrudRepository<BookingDetailVisibility>` (SDK v1)  

---

## 3. Reported Issue: DateTimeParseException on MetaData.timestamp

### 3.1 Root Cause (confirmed via git diff and code analysis)

**Chain of failure:**

1. `BookingDetail` upgrade removed `@DynamoDBDocument` from `MetaData.java`
2. `BookingDetail` upgrade removed `@DynamoDBTypeConverted(converter = LocalDateTimeTypeConverter.class)` from `MetaData.timestamp` field
3. New SDK v2 annotation `@DynamoDbConvertedBy(MetaDataConverter.class)` added to `BookingDetail.getMetaData()`
4. Visibility's SDK v1 `DynamoDBMapper` **ignores** the SDK v2 annotation
5. Without `@DynamoDBDocument` on MetaData and without a converter on `timestamp`, SDK v1 falls back to **native type marshalling**
6. For `LocalDateTime`, native marshalling uses `DateTimeFormatter.ISO_LOCAL_DATE_TIME` (expects `T` separator)
7. Stored data contains `"2020-04-14 10:21:53.78"` (space separator) → **DateTimeParseException at index 10**

### 3.2 Timestamp Format Discrepancy

| Writer | Converter | Format | Example |
|--------|-----------|--------|---------|
| **Old booking (SDK v1)** | `LocalDateTimeTypeConverter` | `ISO_DATE_TIME` (T separator) | `2020-04-14T10:21:53.78` |
| **New booking (SDK v2)** | `MetaDataConverter` (Jackson ObjectMapper) | `@JsonFormat("yyyy-MM-dd HH:mm:ss.SS")` | `2020-04-14 10:21:53.78` |
| **Visibility (SDK v1 reader)** | None (native marshalling fallback) | Expects `ISO_DATE_TIME` (T separator) | **FAILS** on space-separated |

**Additional concern in booking module**: The new `MetaDataConverter`'s `ObjectMapper` does NOT register a custom `LocalDateTimeDeserializer` with the `"yyyy-MM-dd HH:mm:ss.SS"` pattern. The `Json.java` class explicitly notes: *"Default LocalDateTimeDeserializer does not respect @JsonFormat setting on the POJO, so registering the formatter is required here."* This means the MetaDataConverter may also fail to read old ISO-format timestamps written by the pre-upgrade booking code (data written with `T` separator). The round-trip test in `MetaDataConverterTest` does NOT set a timestamp, so this bug is untested.

---

## 4. Complete List of Breaking Changes

### 4.1 Compile-Time Breaks

| # | Issue | File | Lines | Severity |
|---|-------|------|-------|----------|
| C1 | **`getHashKey()` removed** — method no longer exists on BookingDetail (was from `DynamoHashAndSortKey<String,String>` interface) | `BookingDao.java` | L42, L52 | COMPILE ERROR |
| C2 | **`getSortKey()` removed** — method no longer exists | N/A (not called in visibility) | — | LOW |
| C3 | **`DynamoHashAndSortKey` interface removed** — if visibility references this type | — | — | LOW |

> **UPDATE 2026-04-17**: Section 4.1 is **NOT APPLICABLE** to current visibility module. Visibility uses the pre-upgrade booking model `booking:2.1.8.M` — a published Maven artifact containing OLD pre-upgrade code with all SDK v1 annotations intact (`@DynamoDBTable`, `@DynamoDBHashKey`, `getHashKey()`, etc.). These compile-time breaks would only occur if visibility updated its booking dependency to a post-upgrade version, which has NOT happened. **No compilation issues exist.**

### 4.2 Runtime Breaks — All `@DynamoDBDocument` Annotations Removed

When SDK v1 `DynamoDBMapper` loads `BookingDetailVisibility` from DynamoDB, it processes ALL fields. The following classes lost their `@DynamoDBDocument` annotation, so SDK v1 can no longer recursively marshal them from DynamoDB Maps:

| # | Class | Old Annotation | Effect Without It |
|---|-------|----------------|-------------------|
| R1 | **`MetaData`** | `@DynamoDBDocument` + `@DynamoDBTypeConverted(LocalDateTimeTypeConverter.class)` on `timestamp` | **DateTimeParseException** — SDK v1 can't parse LocalDateTime with native marshalling |
| R2 | **`Audit`** | `@DynamoDBDocument` + `@DynamoDBTypeConverted(OffsetDateTimeTypeConverter.class)` on `createdDateUtc`, `lastModifiedDateUtc` | **OffsetDateTime parse failure** — similar issue with OffsetDateTime fields |
| R3 | **`EnrichedAttributes`** | `@DynamoDBDocument` + `@DynamoDBIgnore` on computed getters | **Deserialization failure** — nested location info objects can't be unmarshalled |

> **UPDATE 2026-04-17**: Section 4.2 describes what would happen if visibility used post-upgrade booking classes. Since visibility uses `booking:2.1.8.M` (pre-upgrade), the model classes have ALL SDK v1 annotations (`@DynamoDBDocument`, `@DynamoDBTypeConverted`, etc.). **These annotations are present in the published artifact.**
>
> The real concern is the DATA FORMAT written by the upgraded booking service — see Section 4.5. Fixes applied in booking module (session `9d0caeabd6394be2`) ensure new records are written in formats compatible with the old SDK v1 converters.

### 4.3 Runtime Breaks — All `@DynamoDBTypeConverted` Annotations Removed from BookingDetail Fields

| # | Field | Old Converter | New Converter | SDK v1 Behavior Without Old Annotation |
|---|-------|---------------|---------------|----------------------------------------|
| R4 | `payload` (Contract) | `@DynamoDBTypeConverted(ContractTypeConverter.class)` | `@DynamoDbConvertedBy(ContractAttributeConverter.class)` | **Cannot deserialize** — Contract stored as compressed JSON string, native marshalling can't handle it |
| R5 | `expiresOn` (Date) | `@DynamoDBTypeConverted(DateToEpochSecond.class)` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` | **Wrong value** — epoch SECONDS read as epoch MILLIS (Date off by 1000x) |
| R6 | `payloadType` (enum) | `@DynamoDBTypeConvertedEnum` | Removed (Enhanced Client handles natively) | May work via native marshalling, but behavior differs |
| R7 | `state` (BookingState enum) | `@DynamoDBTypeConvertedEnum` | Removed | Same as R6 |
| R8 | `channel` (Channel enum) | `@DynamoDBTypeConvertedEnum` | Removed | Same as R6 |

> **UPDATE 2026-04-17**: Section 4.3 is **NOT APPLICABLE** to current visibility module. Since visibility uses `booking:2.1.8.M`, all `@DynamoDBTypeConverted` annotations are PRESENT in the model classes. The old converters work with SDK v1 DynamoDBMapper.
>
> **Data format verification confirms full compatibility:**
> - `payload`: `ContractAttributeConverter` (SDK v2) writes identical format to `ContractTypeConverter` (SDK v1) — `className:json` with GZIP compression
> - `expiresOn`: Same epoch-second Long format
> - `payloadType`, `state`, `channel`: Enhanced Client stores enums as `.name()` strings — same as SDK v1

### 4.4 Runtime Breaks — DynamoDB Key/Index Annotations Changed

| # | Annotation | Old (SDK v1) | New (SDK v2) | Impact |
|---|------------|-------------|-------------|--------|
| R9 | Hash key | `@DynamoDBHashKey` on `getHashKey()` | `@DynamoDbPartitionKey` on `getBookingId()` | SDK v1 can't determine partition key |
| R10 | Sort key | `@DynamoDBRangeKey` on `getSortKey()` | `@DynamoDbSortKey` on `getSequenceNumber()` | SDK v1 can't determine sort key |
| R11 | Version | `@DynamoDBVersionAttribute` | `@DynamoDbVersionAttribute` | Optimistic locking may fail |
| R12 | GSI keys | `@DynamoDBIndexHashKey`, `@DynamoDBIndexRangeKey` | `@DynamoDbSecondaryPartitionKey`, `@DynamoDbSecondarySortKey` | GSI queries may fail |

> **UPDATE 2026-04-17**: Section 4.4 is **NOT APPLICABLE** to current visibility module. Visibility uses `booking:2.1.8.M` which has ALL SDK v1 key/index annotations intact. The `DynamoDBMapper` in visibility correctly resolves partition keys, sort keys, version attributes, and GSI keys because these annotations are present in the pre-upgrade published artifact. The `BookingDetailVisibility` class inherits all SDK v1 annotations from the pre-upgrade `BookingDetail`.

### 4.5 Data Format Changes in DynamoDB (Cross-Service Impact)

Even if visibility keeps the pre-upgrade booking dependency, the **deployed booking service** (SDK v2) may write data in different formats to the DynamoDB tables that visibility reads:

| Field | Old Format | New Format | Risk |
|-------|------------|------------|------|
| `metaData.timestamp` | `"2020-04-14T10:21:53.78"` (ISO, T separator) | `"2020-04-14T10:21:53.78"` (ISO, T separator — **FIXED**) | **RESOLVED** — booking now writes ISO T-separator format |
| `audit.createdDateUtc` | ISO-8601 string via `OffsetDateTimeTypeConverter` | ISO-8601 string via `AuditAttributeConverter` (Jackson with `@JsonFormat`) | **RESOLVED** — format is ISO-compatible, flexible parsing added |
| `payload` | JSON string via `ContractTypeConverter` | JSON string via `ContractAttributeConverter` | **LOW** — verified identical format |
| `expiresOn` | Epoch seconds (Long) via `DateToEpochSecond` | Epoch seconds via `DateEpochSecondAttributeConverter` | **LOW** — verified identical format |

> **UPDATE 2026-04-17**: Section 4.5 data format issues have been **FIXED** in booking module (session `9d0caeabd6394be2`):
> - **MetaData.timestamp**: Changed from `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss.SS")` to `@JsonFormat(shape = STRING)`. New records now write ISO T-separator format, matching the old `LocalDateTimeTypeConverter`. Deserialization handles both formats via `FlexibleLocalDateTimeDeserializer`.
> - **Audit dates**: Added `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)` for flexible parsing of all ISO offset formats (variable fractional digits, Z/+00:00/+0000 offsets).
> - **EnrichedAttributes boolean fields**: Fixed `LegacyMapConverter` to return Java numbers (Integer) instead of strings for DynamoDB N-type values. Jackson coerces int 1→true, 0→false.
> - **Contract and expiresOn**: Verified identical format — no changes needed.

---

## 5. Visibility Module Usage of Affected BookingDetail Fields

### Fields Actually Accessed by Visibility Code

| Field | Used? | Where | Purpose |
|-------|-------|-------|---------|
| `getBookingId()` (was `getHashKey()`) | YES | `BookingDao.java` L42, L52 (as `getHashKey()`) | Logging carrier/customer booking lookups |
| `getSequenceNumber()` | YES | `BookingDao.java` L42, L52, L106 | Sorting, querying, logging |
| `getPayload()` | YES | `TransactionSearchService.java` L206 | Extract sender EDI ID from booking contract |
| `getMetaData()` | **NO** (not from BookingDetail) | — | visibility uses `com.inttra.mercury.messaging.model.MetaData` on ContainerEvent, NOT booking's MetaData |
| `getAudit()` | NO | — | Not accessed in visibility code |
| `getEnrichedAttributes()` | NO | — | Not accessed in visibility code |
| `getExpiresOn()` | NO | — | Not accessed in visibility code |
| `inttraReferenceNumber` | YES | `BookingDao.java` L95 (constant reference for GSI name) | GSI query for bookings by INTTRA ref |

### Key Insight

Although visibility does NOT directly call `getMetaData()`, `getAudit()`, or `getEnrichedAttributes()` on BookingDetail, the SDK v1 `DynamoDBMapper` **deserializes ALL fields** when loading an object from DynamoDB — including ones the business logic never touches. This means the `DateTimeParseException` on MetaData occurs during DynamoDB load, before any business code runs.

> **UPDATE 2026-04-17**: Section 5 correctly identifies that DynamoDBMapper deserializes all fields. However, since visibility uses `booking:2.1.8.M` (pre-upgrade model with SDK v1 annotations), the DynamoDBMapper uses the OLD converters from the published artifact:
> - `MetaData`: Uses `@DynamoDBDocument` + `@DynamoDBTypeConverted(LocalDateTimeTypeConverter.class)` from the pre-upgrade model. The `LocalDateTimeTypeConverter` uses `ISO_DATE_TIME` formatter which expects T separator. **After the booking fix**, new records are written with T separator, so this converter works correctly for both old and new records.
> - `Audit`: Uses `@DynamoDBDocument` + `@DynamoDBTypeConverted(OffsetDateTimeTypeConverter.class)`. This converter handles ISO offset format and is compatible with the data written by the fixed `AuditAttributeConverter`.
> - `EnrichedAttributes`: Uses `@DynamoDBDocument` + `@DynamoDBIgnore` on computed getters. The data format in DynamoDB Map is unchanged.
>
> **Conclusion**: With the booking module fixes applied, the visibility module using `booking:2.1.8.M` and SDK v1 `DynamoDBMapper` should be able to read ALL records (old and new) without errors.

---

## 6. Fix Strategy

### 6.1 Immediate Fix — Keep Pre-Upgrade Booking Dependency (Recommended Short-Term)

**Approach**: Ensure `visibility-commons/pom.xml` pins `booking` to a version published BEFORE the SDK v2 upgrade.

```xml
<!-- Ensure this is the LAST pre-upgrade published version -->
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>booking</artifactId>
    <version>2.1.8.M</version>  <!-- Verify this is pre-upgrade -->
</dependency>
```

**Verification**: Check if `booking:2.1.8.M` artifact contains pre-upgrade code by inspecting:
```bash
# Check if the published artifact has SDK v1 annotations
mvn dependency:unpack -Dartifact=com.inttra.mercury:booking:2.1.8.M -DoutputDirectory=/tmp/booking-check
grep -r "DynamoDBTable" /tmp/booking-check/
```

If `2.1.8.M` is already post-upgrade, find the last pre-upgrade version and update the dependency.

**Risk**: If the deployed booking service (SDK v2) writes MetaData timestamps with SPACE separator (new format), visibility reading with the old `LocalDateTimeTypeConverter` (which expects ISO `T` separator) will still fail on NEW records. This means there's a **data format migration issue** regardless of dependency version.

### 6.2 Immediate Fix — Dual-Annotate BookingDetail Model Classes (If Pre-Upgrade Dep Not Available)

If visibility MUST use the post-upgrade booking classes, add SDK v1 annotations back to the booking model classes as `@Deprecated` alongside SDK v2 annotations. Changes needed in booking module:

**6.2.1 MetaData.java** — Restore SDK v1 annotations:
```java
@DynamoDBDocument                                                    // RESTORE
@JsonInclude(JsonInclude.Include.NON_EMPTY)
@JsonIgnoreProperties(ignoreUnknown = true)
public class MetaData implements WorkflowAware {
    // ...
    @JsonFormat(pattern = Json.DEFAULT_DATE_TIME_PATTERN)
    @DynamoDBTypeConverted(converter = LocalDateTimeTypeConverter.class)  // RESTORE
    private LocalDateTime timestamp;
    
    @JsonIgnore
    @DynamoDBIgnore                                                       // RESTORE
    public String getTimestampAsString() { ... }
}
```

**6.2.2 Audit.java** — Restore SDK v1 annotations:
```java
@DynamoDBDocument                                                    // RESTORE
public class Audit {
    @DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)  // RESTORE
    private OffsetDateTime createdDateUtc;
    
    @DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)  // RESTORE
    private OffsetDateTime lastModifiedDateUtc;
}
```

**6.2.3 EnrichedAttributes.java** — Restore SDK v1 annotations:
```java
@DynamoDBDocument                                                    // RESTORE
public class EnrichedAttributes {
    @DynamoDBIgnore                                                  // RESTORE
    public Optional<LocationAdditionalInfo> getLocationAdditionalInfoForLocation(Location location) { ... }
    
    @DynamoDBIgnore                                                  // RESTORE
    private boolean isMatch(...) { ... }
}
```

**6.2.4 LocalDateTimeTypeConverter.java** — Restore DynamoDBTypeConverter interface:
```java
public class LocalDateTimeTypeConverter implements DynamoDBTypeConverter<String, LocalDateTime> {
    // ... (restore the `implements` clause)
}
```

**6.2.5 BookingDetail.java** — Add SDK v1 field annotations back alongside SDK v2 getter annotations. This is complex because SDK v1 uses field-level annotations while SDK v2 uses getter-level annotations. Both can coexist since they're different annotation types from different packages.

**Risk**: Increases maintenance burden. Both SDK v1 and v2 annotations must be kept in sync. Should be REMOVED once visibility upgrade is complete.

### 6.3 Medium-Term Fix — Complete Visibility AWS SDK v2 Upgrade (Recommended Long-Term)

Complete the upgrade as planned in `visibility/docs/visibility-aws2x-plan.md`:
- Phase 5 specifically covers `BookingDetailVisibility` alignment
- Replace `DynamoDBCrudRepository` with `DatabaseRepository` (cloud-sdk)
- Replace `DynamoDBMapper` with Enhanced Client
- Remove all SDK v1 dependencies

### 6.4 Data Format Migration Fix (Required Regardless of Approach)

The new `MetaDataConverter` writes timestamps with SPACE separator (`"yyyy-MM-dd HH:mm:ss.SS"`) while the old `LocalDateTimeTypeConverter` wrote with T separator (`ISO_DATE_TIME`). Both formats exist in DynamoDB.

**Fix for MetaDataConverter** (in booking module): Register a lenient deserializer that handles both formats:

```java
private static ObjectMapper createObjectMapper() {
    ObjectMapper mapper = new ObjectMapper();
    JavaTimeModule javaTimeModule = new JavaTimeModule();
    // Register deserializer that handles both ISO (T) and space-separated formats
    DateTimeFormatter flexibleFormatter = new DateTimeFormatterBuilder()
        .appendPattern("yyyy-MM-dd")
        .appendOptional(DateTimeFormatter.ofPattern("'T'"))
        .appendOptional(DateTimeFormatter.ofPattern(" "))
        .appendPattern("HH:mm:ss")
        .appendOptional(DateTimeFormatter.ofPattern(".SS"))
        .toFormatter();
    javaTimeModule.addDeserializer(LocalDateTime.class, 
        new LocalDateTimeDeserializer(flexibleFormatter));
    mapper.registerModule(javaTimeModule);
    mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
    return mapper;
}
```

**Fix for LocalDateTimeTypeConverter** (backward compatibility): Make the unconvert method handle both formats:

```java
public LocalDateTime unconvert(String date) {
    if (date == null) return null;
    try {
        return LocalDateTime.parse(date, DateTimeFormatter.ISO_DATE_TIME);
    } catch (DateTimeParseException e) {
        // Fallback: try space-separated format from new MetaDataConverter
        return LocalDateTime.parse(date, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SS"));
    }
}
```

---

## 7. Recommended Action Plan

| Priority | Action | Owner | Risk |
|----------|--------|-------|------|
| **P0** | Verify `booking:2.1.8.M` is pre or post upgrade. If post-upgrade, pin to last pre-upgrade version | Visibility team | Low |
| **P0** | Fix `MetaDataConverter` in booking to handle both timestamp formats (T and space) | Booking team | Low — add round-trip test with timestamp |
| **P1** | If pre-upgrade booking version not available: apply dual-annotation approach (Section 6.2) | Booking team | Medium — temporary coupling |
| **P1** | Fix `BookingDao.java` L42, L52 — replace `getHashKey()` with `getBookingId()` | Visibility team | Low |
| **P2** | Complete visibility AWS SDK v2 upgrade (Phase 5 of `visibility-aws2x-plan.md`) | Visibility team | Medium — large scope |
| **P2** | Remove dual annotations from booking once visibility upgrade is complete | Booking team | Low |

---

## 8. Hidden Issues Found

### 8.1 MetaDataConverter Round-Trip Bug (Booking Module)

The `MetaDataConverterTest` does NOT test timestamp round-trip. The `ObjectMapper` in `MetaDataConverter` does NOT register a custom `LocalDateTimeDeserializer`, so it may fail to deserialize timestamps in either format depending on Jackson version behavior with `@JsonFormat`.

**File**: `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverterTest.java`  
**Fix**: Add a test that sets `MetaData.timestamp` and verifies round-trip through DynamoDB Map format.

### 8.2 Orphaned LocalDateTimeTypeConverter

The `LocalDateTimeTypeConverter` in `booking/src/main/java/.../dynamodb/` still exists but no longer implements `DynamoDBTypeConverter<String, LocalDateTime>`. It's dead code that should be either:
- Restored to implement the interface (if dual-annotation approach is used)
- Deleted entirely (if visibility upgrade is completed first)

### 8.3 Visibility BookingDao Uses Deprecated API Pattern

`BookingDao.java` calls `bookingDetail.getHashKey()` (lines 42, 52) for debug logging. This method was provided by the `DynamoHashAndSortKey<String,String>` interface which was removed. Even if the immediate issue is fixed, this needs updating to `getBookingId()`.

### 8.4 Data Consistency Risk During Transition Period

During the transition period (upgraded booking + non-upgraded visibility):
- Booking writes MetaData timestamps with SPACE format
- Existing data has T format  
- Visibility's old converter (`LocalDateTimeTypeConverter`) only handles T format
- New booking converter (`MetaDataConverter`) only handles SPACE format (unless fixed)

Both converters need to be lenient and accept both formats.

---

## 9. Files Affected

### Booking Module (changes needed for backward compatibility)
- `booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java` — restore `@DynamoDBDocument`, `@DynamoDBTypeConverted`
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java` — restore `@DynamoDBDocument`, `@DynamoDBTypeConverted`
- `booking/src/main/java/com/inttra/mercury/booking/outbound/model/EnrichedAttributes.java` — restore `@DynamoDBDocument`, `@DynamoDBIgnore`
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/LocalDateTimeTypeConverter.java` — restore `implements DynamoDBTypeConverter`
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java` — fix timestamp format handling
- `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverterTest.java` — add timestamp round-trip test

### Visibility Module (changes needed)
- `visibility/visibility-commons/src/main/java/.../BookingDao.java` — replace `getHashKey()` → `getBookingId()`
- `visibility/visibility-commons/pom.xml` — verify booking dependency version

---

## 10. References

- Booking upgrade commit: `74f36e7a71fa` (ION-14382 bk3 aws upgrade changes)
- Reapply commit: `59ebf93a2aed` 
- Pre-upgrade baseline: `c76288edb701` (ION-13060)
- Visibility upgrade plan: `visibility/docs/visibility-aws2x-plan.md`
- Session: `ad378beb151a432f`
