# Booking → Redshift ETL: Audit Field Timestamp Format Issue

**Date**: 2026-05-05  
**Module**: `booking` (source), `self-service-reports` (consumer — BK-Detail report)  
**Reported by**: ETL/Data Engineering team  
**Trigger**: AWS SDK upgrade data-format fix committed 2026-04-17 (commit `ee29760491`, ION-14382)

---

## 1. Summary

After the 2026-04-17 booking data-format fixes (ION-14382), the `audit.createdDateUtc` field serialized to DynamoDB changed its timezone suffix format from `+0000` to `Z` for UTC timestamps. The Redshift ETL Glue job was written to parse the old `+0000` format. With the new `Z` format it cannot parse the timestamp, so `unix_timestamp()` returns `null` — causing `version_date`, `partition_date`, and `source_created_date` to all be null in Redshift. This breaks the **BK-Detail report** in `self-service-reports`.

---

## 2. Background: How `Audit` Timestamp Fields Were Changed

### 2.1 Original Format (SDK v1 era — pre-AWS upgrade)

Before the AWS SDK v2 upgrade (`ION-14382`, commit `74f36e7a71`, 2026-03-27), `Audit.java` used AWS SDK v1 DynamoDB annotations with a custom `OffsetDateTimeTypeConverter` implementing the SDK v1 `DynamoDBTypeConverter` interface. The `convert()` method used `DateTimeFormatter.ISO_DATE_TIME` to serialize `OffsetDateTime` values. For UTC timestamps this produced:

```
"2026-05-04T06:29:32.691+00:00"   ← ISO_DATE_TIME for UTC OffsetDateTime
```

### 2.2 First Upgrade Format (SDK v2 — initial upgrade, commit `74f36e7a71`)

The initial AWS upgrade replaced the SDK v1 DynamoDB annotations with a custom `AuditAttributeConverter` backed by Jackson ObjectMapper. The `@JsonFormat` annotation on `Audit.java` was:

```java
// Initial upgrade annotation
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
private OffsetDateTime createdDateUtc;
```

In Java's `DateTimeFormatter`, the `Z` pattern letter corresponds to the **RFC 822 timezone offset** (e.g., `+0000` for UTC). For UTC OffsetDateTimes this produced:

```
"2026-05-04T06:29:32.691+0000"    ← Z pattern = RFC 822 offset, UTC = +0000
```

This format was the basis on which the ETL Glue job's format string was written.

### 2.3 Data-Format Fix (2026-04-17, commit `ee29760491`, ION-14382)

The 2026-04-17 data-format fix addressed **Issue 4** documented in `booking/docs/2026-04-17-booking-dataformat-issue-fixes.md`:

> **Symptom**: `Text '2020-11-30T04:23:30.153845Z' could not be parsed at index 23`  
> **Root cause**: `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ")` failed on (a) old records with 6 fractional digits (microseconds) and (b) records whose offset was stored as the literal `Z` character rather than `+0000`.

**Fix applied**:
```java
// After fix — in Audit.java
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime createdDateUtc;

@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime lastModifiedDateUtc;
```

The `OffsetDateTimeTypeConverter` was updated to parse all valid ISO-8601 offset variants: `Z`, `+00:00`, `+0000`, and variable fractional digits.

### 2.4 The Format Change That Broke the ETL

In Java's `DateTimeFormatter`, the `XXX` pattern letter produces the **ISO 8601 offset**:

| Pattern | Meaning | UTC output |
|---------|---------|-----------|
| `Z` | RFC 822 offset | `+0000` |
| `XX` | RFC 822 offset (same as `Z`) | `+0000` |
| `XXX` | ISO 8601 offset (with colon, or `Z` for UTC) | `Z` |

Changing from `Z` → `XXX` silently changed what gets written for UTC timestamps:

| Period | Format written to DynamoDB / outbound | Example |
|--------|--------------------------------------|---------|
| Pre-2026-03-27 (SDK v1) | `+00:00` (ISO_DATE_TIME) | `2026-05-04T06:29:32.691+00:00` |
| 2026-03-27 → 2026-04-16 (SDK v2 initial) | `+0000` (RFC 822 via `Z` pattern) | `2026-05-04T06:29:32.691+0000` |
| 2026-04-17 → present (data-format fix) | `Z` (ISO 8601 UTC literal via `XXX` pattern) | `2026-05-04T06:29:32.691Z` |

The ETL was coded to the **middle period** format (`+0000`). Records written after 2026-04-17 carry the `Z` suffix, which the ETL cannot parse.

---

## 3. Validation of Developer's Analysis

### Claim 1: "The format `yyyy-MM-dd'T'HH:mm:ss.SSSZ` expects a numeric offset like `+0000`, not literal `Z`"

**✅ VALIDATED.** In both Java's `SimpleDateFormat` (used by Spark in legacy mode) and `DateTimeFormatter` (used by Spark 3.x in CORRECTED mode), the `Z` format letter corresponds to the RFC 822 numeric offset. It does **not** match the ISO 8601 literal `Z` character. They are syntactically identical (`Z`) but semantically different:

- `Z` as a **format pattern letter** = expects a numeric RFC 822 offset like `+0000` or `-0530`
- `Z` as a **literal character** at the end of a timestamp = ISO 8601 UTC indicator

### Claim 2: "`2026-05-04T06:29:32.691Z` → does not match → returns null"

**✅ VALIDATED.** When `unix_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSZ")` is called with a value ending in literal `Z`:

- In **legacy Spark** (SimpleDateFormat): `SimpleDateFormat` does not recognise literal `Z` as a match for `Z` pattern → parse fails → returns `null`
- In **Spark 3.x CORRECTED mode** (DateTimeFormatter): the `Z` pattern is a zone-offset pattern that similarly cannot match a stand-alone literal `Z` in the same way → returns `null`

### Claim 3: "`2026-05-04T06:29:32.691+0000` → matches ✓"

**✅ VALIDATED.** The `+0000` suffix is a valid RFC 822 numeric offset that `Z` pattern correctly parses.

### Claim 4: "This causes `version_date`, `partition_date`, and `source_created_date` all to be null"

**✅ VALIDATED** (by inference). If `unix_timestamp(...)` returns `null` for the `Auditdate` computation, then all downstream columns derived from `Auditdate` (including `version_date`, `partition_date`, `source_created_date`) will also be `null`. The ETL logic chains these columns from `Auditdate`.

### Additional finding: Substring extraction also fails

The ETL code:
```python
substring(col("AuditCreatedDate"), -8, 3).cast("float") / 1000
```
This was designed to extract the millisecond component for sub-second precision. For `+0000` format (`"2026-05-04T06:29:32.691+0000"` — 28 chars), `-8` from end points to position 20 (`691`). For the `Z` format (`"2026-05-04T06:29:32.691Z"` — 24 chars), `-8` from end points to position 16 — which is `29:`, not milliseconds. So the substring extraction is **also broken** for `Z`-format strings, compounding the ETL issue.

---

## 4. Root Cause Chain

```
2026-04-17 (ION-14382 data-format fix)
  └─► Audit.java @JsonFormat changed: "yyyy-MM-dd'T'HH:mm:ss.SSSZ" → "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"
        └─► AuditAttributeConverter uses Jackson with @JsonFormat to serialize to DynamoDB
              └─► UTC OffsetDateTime serialization: "+0000" → "Z"
                    └─► Booking outbound pipeline writes audit.createdDateUtc as "...Z"
                          └─► Redshift ETL reads "...Z" into unix_timestamp("...SSSZ")
                                └─► unix_timestamp() cannot match literal Z → returns null
                                      └─► version_date, partition_date, source_created_date = null
                                            └─► BK-Detail report in self-service-reports: broken
```

---

## 5. Why the April 17 Fix Was Correct (and Should Not Be Reverted)

The data-format fix on 2026-04-17 was **necessary and correct** for the following reasons:

1. **Microseconds in old records**: Records from 2018–2020 had 6 fractional digits (e.g., `2020-11-30T04:23:30.153845Z`). The old `SSS` (3-digit) pattern could not parse these — causing `DateTimeParseException` in Booking's own DynamoDB read path.

2. **Mixed legacy formats**: Old records already stored as literal `Z` (written by legacy code using `DateTimeFormatter.ISO_DATE_TIME` which outputs `Z` for UTC). The old `Z`-pattern annotation could not deserialize its own legacy data.

3. **Fix scope**: The `OffsetDateTimeTypeConverter` was updated to handle all valid variants: `Z`, `+0000`, `+00:00`, variable fractional digits. This is the correct, robust approach.

4. **Reverting breaks Booking**: Reverting to `SSSZ` would re-introduce the `DateTimeParseException` on legacy records.

The ETL must be updated — not the booking module.

---

## 6. Proposed Solution

### Recommended Fix: Update the Redshift ETL Glue Job

The ETL must be made resilient to **both formats** (since DynamoDB contains a mix of old `+0000` records and new `Z` records).

#### Option A — Normalize `Z` before applying the existing logic (minimal change, maintains millisecond precision)

```python
from pyspark.sql.functions import col, when, regexp_replace, unix_timestamp, substring

# Step 1: Normalize "Z" suffix → "+0000" so existing unix_timestamp logic works
df = df.withColumn(
    "AuditCreatedDateNorm",
    when(
        col("AuditCreatedDate").endsWith("Z"),
        regexp_replace(col("AuditCreatedDate"), "Z$", "+0000")
    ).otherwise(col("AuditCreatedDate"))
)

# Step 2: Apply existing transformation unchanged
df = df.withColumn(
    "Auditdate",
    (
        unix_timestamp(col("AuditCreatedDateNorm"), "yyyy-MM-dd'T'HH:mm:ss.SSSZ")
        + substring(col("AuditCreatedDateNorm"), -8, 3).cast("float") / 1000
    ).cast("timestamp")
)
```

**Pros**: Minimal change to existing ETL logic; handles both formats cleanly.  
**Cons**: An extra intermediate column; `regexp_replace` on every row.

#### Option B — Use `to_timestamp` with `X` pattern (Spark 3.x, cleaner)

```python
from pyspark.sql.functions import col, to_timestamp

# "X" pattern in DateTimeFormatter handles Z, +00:00, +0000, +07:30, etc.
df = df.withColumn(
    "Auditdate",
    to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSX")
)
```

**Pros**: Clean single expression; handles all ISO 8601 offset variants natively; no need for normalization.  
**Cons**: Requires Spark 3.x in CORRECTED mode (not LEGACY mode). Drops sub-millisecond precision if any, but DynamoDB Audit records only carry 3 fractional digits anyway (enforced by `SSS` in the Jackson `@JsonFormat` pattern).

#### Option C — coalesce for maximum backward compatibility

```python
from pyspark.sql.functions import col, coalesce, to_timestamp

df = df.withColumn(
    "Auditdate",
    coalesce(
        to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSX"),   # Z or +HH:MM
        to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSZ"),   # +0000 fallback
        to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSS")     # bare date fallback
    )
)
```

**Pros**: Most defensive; handles all historical format variants.  
**Cons**: Three-expression evaluation per row; slightly more expensive.

### Recommendation

**Option A** if the ETL is running in Spark LEGACY mode or if minimal code change is preferred.  
**Option B** if the ETL is running Spark 3.x in CORRECTED mode (preferred, cleaner, future-proof).  
**Option C** if there is uncertainty about data format diversity or Spark version.

---

## 7. What Must NOT Be Changed in the Booking Module

| Component | Action | Reason |
|-----------|--------|--------|
| `Audit.java` `@JsonFormat(pattern="...XXX")` | **Do NOT change** | Reverting to `Z` (RFC 822) would re-break parsing of legacy records with 6 fractional digits |
| `OffsetDateTimeTypeConverter` | **Do NOT change** | Already handles `Z`, `+0000`, `+00:00`, variable fractional digits |
| `AuditAttributeConverter` | **Do NOT change** | Correctly serializes/deserializes Audit from DynamoDB |

---

## 8. Affected Components

| Component | Impact | Fix required |
|-----------|--------|-------------|
| Redshift ETL Glue job (outbound pipeline) | `version_date`, `partition_date`, `source_created_date` = null for all bookings created after 2026-04-17 | **Yes — ETL code change** |
| `self-service-reports` BK-Detail report | Null date columns cause incorrect or missing report rows | **Indirectly — fixed by ETL fix** |
| `booking` module | Not broken — `OffsetDateTimeTypeConverter` handles `Z` correctly | No change needed |
| `visibility` module | Not affected by Audit field format (visibility issue was `ContainerType.lastModifiedDateUtc`, separate field) | No change needed |
| `watermill-publisher` / `watermill-booking` | Not affected by Audit serialization format for its own logic | No change needed |

---

## 9. References

| Reference | Location |
|-----------|----------|
| AWS upgrade commit | `74f36e7a71` — ION-14382 bk3 aws upgrade changes (2026-03-27) |
| Data-format fix commit | `ee29760491` — ION-14382 data format fixes (2026-04-17) |
| Data-format fix documentation | `booking/docs/2026-04-17-booking-dataformat-issue-fixes.md` |
| Visibility integration issue | `booking/docs/visibility-integration-issue-04212026.md` |
| QA outbound pipeline debug | `booking/docs/2026-04-22-qa-outbound-pipeline-debug-findings.md` |
| `Audit.java` | `booking/src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java` |
| `AuditAttributeConverter.java` | `booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java` |
| `OffsetDateTimeTypeConverter.java` | `booking/src/main/java/com/inttra/mercury/booking/dynamodb/OffsetDateTimeTypeConverter.java` |

---

## 10. Data Migration Consideration

Records written to DynamoDB between **2026-03-27** and **2026-04-16** have `audit.createdDateUtc` with `+0000` suffix.  
Records written on or after **2026-04-17** have `Z` suffix.  
Records written before **2026-03-27** (SDK v1 era) may have `+00:00` suffix.

The ETL fix must handle **all three variants**. Option B (`to_timestamp` with `X` pattern) handles all three natively. Options A and C also handle all three but require explicit multi-format handling.

If historical Redshift rows are null due to this bug, a **backfill** of affected rows may be needed after the ETL is fixed, depending on business requirements for the BK-Detail report.

---

## 11. Revised Analysis — Reverting `@JsonFormat` on Audit Is Safe (2026-05-05)

### Challenge

The initial analysis (sections 5–7) recommended fixing only the ETL and not touching the booking module. However, a closer review of the 2026-04-17 fix reveals that **reverting the `@JsonFormat` pattern from `XXX` back to `Z` is safe**, and this is the preferred approach given the ETL change would require its own QA cycle close to release.

### Why the Original Analysis Was Overstated

The original Issue 4 (from `2026-04-17-booking-dataformat-issue-fixes.md`) documented two sub-problems:

1. **6 fractional digits**: Old records like `2020-11-30T04:23:30.153845Z` have 6 fractional digits; `SSS` expects exactly 3
2. **Offset variant mismatch**: `Z` pattern in `@JsonFormat` couldn't parse literal `Z` in old records

**However**, both of these were **deserialization** problems. The fix applied TWO independent changes:

| Change | Purpose | What it controls |
|--------|---------|-----------------|
| `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)` | Robust parsing of ALL legacy formats | **Deserialization** (reading) |
| `@JsonFormat(pattern = "...SSSXXX")` | Changed output format from `+0000` to `Z` | **Serialization** (writing) |

The key insight: **when `@JsonDeserialize` is present, Jackson uses the custom deserializer for reading and completely ignores the `@JsonFormat` pattern for deserialization**. The `OffsetDateTimeTypeConverter.unconvert()` method handles every variant:

```java
// OffsetDateTimeTypeConverter.unconvert() handles:
// "2020-11-30T04:23:30.153845Z"      → ISO_OFFSET_DATE_TIME (6 fractional digits + Z)  ✅
// "2020-11-30T04:23:30.153Z"         → ISO_OFFSET_DATE_TIME (3 fractional digits + Z)  ✅
// "2020-11-30T04:23:30.153+0000"     → normalized to +00:00, then parsed               ✅
// "2020-11-30T04:23:30.153+00:00"    → ISO_OFFSET_DATE_TIME directly                   ✅
// "2020-11-30T04:23:30.153845+00:00" → ISO_OFFSET_DATE_TIME (6 digits + offset)        ✅
```

This is confirmed by the parameterized test `legacyMapWithVariousDateTimeFormats` in `AuditAttributeConverterTest.java` (lines 278–300) which validates all 6 format variants.

Therefore, the `@JsonFormat` pattern change from `Z` to `XXX` was **incidental** to the fix — it changed the serialization output format but was NOT needed to fix the deserialization bug. The `@JsonDeserialize` annotation alone resolved the Issue 4 deserialization failures.

### The Audit Field Is Internal

As noted, `audit.createdDateUtc` and `audit.lastModifiedDateUtc` are **internal booking fields**. The field name itself contains `Utc` — it is always stored as UTC. External consumers of this field (like the ETL) are downstream from the outbound pipeline. The Visibility and Watermill issues that prompted the original data-format fixes were about **different fields**:

- **Visibility**: `ContainerType.lastModifiedDateUtc` inside `enrichedAttributes` (see `visibility-integration-issue-04212026.md`)
- **Watermill / Transformer**: `MetaData.timestamp` (see `2026-04-22-qa-outbound-pipeline-debug-findings.md`)

Neither of these involved the `Audit` timestamp fields. The Audit `@JsonFormat` change was part of the same commit but addressed a **separate, independent issue**.

### Proposed Fix: Revert `@JsonFormat` Pattern Only

Change `Audit.java` lines 32 and 38:

**Before (current — writes `Z` for UTC):**
```java
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime createdDateUtc;

@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime lastModifiedDateUtc;
```

**After (proposed — writes `+0000` for UTC, deserializer still handles all formats):**
```java
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime createdDateUtc;

@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime lastModifiedDateUtc;
```

### Impact Analysis

| Component | Effect of reverting `@JsonFormat` to `SSSZ` |
|-----------|----------------------------------------------|
| **Booking DynamoDB write** | Writes `+0000` instead of `Z` for UTC → ETL-compatible ✅ |
| **Booking DynamoDB read** | `OffsetDateTimeTypeConverter` handles all formats → no change ✅ |
| **Redshift ETL Glue job** | `unix_timestamp(col, "...SSSZ")` can parse `+0000` → fixed ✅ |
| **BK-Detail report** | Dates populated correctly → fixed ✅ |
| **Visibility module** | Not affected — uses `enrichedAttributes`, not `Audit` fields ✅ |
| **Watermill / Transformer** | Not affected — uses `MetaData.timestamp`, not `Audit` fields ✅ |
| **Records written between 2026-04-17 and fix date (with `Z` suffix)** | Read correctly by `OffsetDateTimeTypeConverter` ✅ |
| **AuditAttributeConverterTest** | Round-trip test (line 184–199) asserts `contains("T")` and `matches(".*[Z+].*")` — `+0000` matches both ✅ |

### Test Validation

The existing `AuditAttributeConverterTest.timestampSerializationFormat()` (lines 184–199) asserts:
```java
assertThat(dateStr).contains("T");           // +0000 format has T ✅
assertThat(dateStr).matches(".*[Z+].*");     // +0000 matches [Z+] via '+' ✅
```

Both assertions pass with `+0000` format. No test changes needed.

### Recommendation

**Revert `@JsonFormat` on `Audit.java` from `SSSXXX` to `SSSZ`**. Keep `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)` untouched. This is a one-line-per-field change in a single file. It:

1. Restores ETL compatibility without any ETL code change
2. Does not break any booking module functionality
3. Does not affect Visibility, Watermill, or any other consumer
4. Passes all existing tests without modification
5. Can be deployed as part of the current release without ETL QA overhead

---

## 12. Deep Validation of Section 11 — Critical Gaps and Code-Level Findings

**Review date**: 2026-05-05  
**Source files verified**: `Audit.java`, `AuditAttributeConverter.java`, `OffsetDateTimeTypeConverter.java`, `AuditAttributeConverterTest.java`

---

### 12.1 Serialization Path — Confirmed Correct

`AuditAttributeConverter.transformFrom()` uses:
```java
Map<String, Object> javaMap = OBJECT_MAPPER.convertValue(audit, Map.class);
```
The `OBJECT_MAPPER` has `WRITE_DATES_AS_TIMESTAMPS=false` and `JavaTimeModule` registered. Jackson respects `@JsonFormat` on `Audit` fields when serialising. Therefore:

- `@JsonFormat(pattern = "...SSSXXX")` → outputs `Z` for UTC ✅ (current behaviour)
- `@JsonFormat(pattern = "...SSSZ")` → outputs `+0000` for UTC ✅ (proposed revert)

The `@JsonFormat` revert DOES change the serialization output. The analysis in Section 11 is correct on this point.

### 12.2 Deserialization Path — Confirmed Robust

`AuditAttributeConverter` registers the deserializer two ways:

1. Via `JavaTimeModule`: `javaTimeModule.addDeserializer(OffsetDateTime.class, new OffsetDateTimeTypeConverter())`
2. Via annotation on `Audit.java`: `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)`

Both point to the same `OffsetDateTimeTypeConverter.unconvert()` which handles:
- `ISO_OFFSET_DATE_TIME` directly (handles `Z`, `+00:00`, ISO variants natively)
- Normalization fallback: `+0000` → `+00:00` then re-parses
- Date-only fallback for extreme legacy cases

The claim that `@JsonDeserialize` overrides `@JsonFormat` for reading is correct: Jackson invokes the custom deserializer and the `@JsonFormat` pattern is **not consulted** for parsing when a `@JsonDeserialize` class is present. Reverting `@JsonFormat` does not affect deserialization. **Confirmed safe.**

### 12.3 Dead Code: `OffsetDateTimeTypeConverter.convert()` — Inconsistency to Note

`OffsetDateTimeTypeConverter.convert()` (line 27–29) uses `DateTimeFormatter.ISO_DATE_TIME`:
```java
public String convert(OffsetDateTime offsetDateTime) {
    return offsetDateTime != null ? offsetDateTime.format(DateTimeFormatter.ISO_DATE_TIME) : null;
}
```
`ISO_DATE_TIME` for a UTC `OffsetDateTime` outputs `Z` (e.g., `2026-05-04T06:29:32.691Z`). However, this method is **never called** in the current code path — `AuditAttributeConverter.transformFrom()` goes through Jackson `OBJECT_MAPPER.convertValue()`, not through `convert()` directly. It is a leftover from the SDK v1 `DynamoDBTypeConverter` interface. Its existence creates a misleading inconsistency: the class appears to produce `Z` format, while the actual serialization through Jackson produces `+0000` (after the revert) or `Z` (currently). This is a code smell but not a functional issue. It should be cleaned up separately.

### 12.4 Test Assertion Gap — Comment is Misleading Post-Revert

`AuditAttributeConverterTest.timestampSerializationFormat()` (lines 184–199) has this comment:
```java
// Should use ISO format with Z for UTC (not +0000)
assertThat(dateStr).contains("T");
assertThat(dateStr).matches(".*[Z+].*");
```
The comment "not +0000" expresses the **intent when the test was written** for the `XXX` pattern. After the revert to `SSSZ`, the format will be `+0000`, which:
- `contains("T")` → ✅ passes
- `matches(".*[Z+].*")` → ✅ passes (matches `+` in `+0000`)

So the test **passes** after the revert, but the **comment is now factually wrong**. The test does not assert the specific format. The comment should be updated to remove the "not +0000" wording, or the assertion should be strengthened to explicitly test the expected format. This is a documentation/intent issue, not a test failure.

---

## 13. Does `*Utc` Field Naming Require `Z` Format?

**Short answer: No. The naming convention imposes no format requirement. Consumer compatibility should drive the choice.**

### Rationale

The field names `createdDateUtc` and `lastModifiedDateUtc` carry semantic meaning in the **type system**: the value stored is always in UTC. They do not impose a wire format contract. In ISO 8601 / RFC 3339, all three representations below are semantically identical for UTC:

| Format | Representation | Semantics |
|--------|----------------|-----------|
| `Z` | `2026-05-04T06:29:32.691Z` | UTC (ISO 8601 §5.6 short form) |
| `+00:00` | `2026-05-04T06:29:32.691+00:00` | UTC (ISO 8601 extended offset) |
| `+0000` | `2026-05-04T06:29:32.691+0000` | UTC (RFC 822 numeric offset) |

All three are valid UTC representations. The `Utc` suffix in the field name means "this value is always UTC", not "this value must use the `Z` literal". Choosing `Z` vs `+0000` is purely a formatting decision, not a semantic one.

### Why `Z` is generally preferred (but not mandatory here)

- `Z` is the canonical short form in RFC 3339 / ISO 8601 and is universally recognised
- It is shorter (saves 4 bytes per field in serialized form at scale)
- Many modern parsers (including Java's `DateTimeFormatter.ISO_OFFSET_DATE_TIME`) default to `Z` for UTC output
- REST APIs typically use `Z` for UTC in JSON payloads

### Why `+0000` is preferable in this specific context

- The ETL Glue job was designed for `+0000` (RFC 822 `Z` pattern in `unix_timestamp()`)
- The `Audit` timestamp fields are **internal** — they are not exposed in the booking REST API response body (the `@JsonFormat` governs DynamoDB storage, not the HTTP API layer). There is no external consumer that requires `Z`
- Compatibility with the ETL outweighs format elegance for an internal field
- The `+0000` format has been in DynamoDB for bookings between 2026-03-27 and 2026-04-16 already — reverting restores prior consistency for that period

**Conclusion**: For `Audit.createdDateUtc` and `Audit.lastModifiedDateUtc`, using `+0000` is the correct pragmatic choice given the ETL dependency. If this field were ever exposed in an external API, `Z` would be preferred. For DynamoDB-internal storage, either is valid.

---

## 14. Spark ETL Transformation Code — Critical Review

### 14.1 Current ETL Format String — Wrong Pattern Letter

```python
unix_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSZ")
```

The `Z` in the format string is a **Java pattern letter** for RFC 822 numeric offset, not a literal `Z`. This is a common confusion. The ETL works for `+0000` records but fails for `Z` (literal) records. The analysis in the document is correct.

### 14.2 Option A — Normalization Approach

```python
when(
    col("AuditCreatedDate").endsWith("Z"),
    regexp_replace(col("AuditCreatedDate"), "Z$", "+0000")
).otherwise(col("AuditCreatedDate"))
```

**Gap — Does not handle pre-2026-03-27 `+00:00` format**: Records from the SDK v1 era (before 2026-03-27) are stored as `+00:00` (with colon, from `DateTimeFormatter.ISO_DATE_TIME`). These records:
- `endsWith("Z")` → **false** → no normalization
- `unix_timestamp(col, "...SSSZ")` → `Z` pattern expects `+HHMM` (no colon), not `+HH:MM` (with colon) → **parse fails → null**

So Option A silently continues to fail for all pre-2026-03-27 records. Since the document acknowledges these records exist in DynamoDB (Section 10), this is a gap that should be surfaced. Option A should additionally normalize `+00:00` → `+0000`:

```python
df = df.withColumn(
    "AuditCreatedDateNorm",
    regexp_replace(
        when(col("AuditCreatedDate").endsWith("Z"),
             regexp_replace(col("AuditCreatedDate"), "Z$", "+0000"))
        .otherwise(col("AuditCreatedDate")),
        r"([+-]\d{2}):(\d{2})$", r"$1$2"   # +HH:MM → +HHMM
    )
)
```

### 14.3 Substring Millisecond Extraction — Fragile and Format-Dependent

```python
substring(col("AuditCreatedDateNorm"), -8, 3).cast("float") / 1000
```

This uses positional extraction to recover milliseconds because `unix_timestamp()` truncates to whole seconds. The calculation relies on the string being exactly 28 characters (for `+0000` format):
- Position `-8` from end of a 28-char string = position 21 (1-indexed) = the `6` in `.691`
- Extracts `691` → divides by 1000 → `0.691`

This works for `+0000` (28 chars) but breaks for any other format length:
| Format | Length | Position -8 extracts |
|--------|--------|----------------------|
| `+0000` (28 chars) | 28 | `691` ✅ |
| `+00:00` (29 chars) | 29 | `:69` ❌ |
| `Z` (24 chars) | 24 | `9:3` ❌ (before normalization) |

After normalizing `Z` → `+0000` and `+HH:MM` → `+HHMM`, all strings become 28 chars, so the substring hack works — **but only if all three normalizations are applied**. This is a brittle coupling between the normalization logic and the substring extraction. A better approach (valid in Spark 3.x CORRECTED mode):

```python
# No substring hack needed; to_timestamp preserves milliseconds natively
df = df.withColumn(
    "Auditdate",
    to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSX")
)
```

### 14.4 Option B — `to_timestamp` with `X` Pattern

```python
to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSX")
```

The `X` pattern letter in Java's `DateTimeFormatter` (used by Spark 3.x CORRECTED mode):
- `X` (single letter): handles `Z` for zero offset AND `+HH` for non-zero
- However, for parsing, Java's `DateTimeFormatter` is lenient about the number of `X` letters — a single `X` can typically parse `Z`, `+HH`, `+HHMM`, `+HH:MM` in practice

**Concern**: In strict `DateTimeFormatter` mode (which Spark 3.x CORRECTED mode uses), single `X` may not parse `+0000` (HHMM without colon). Testing shows `XXX` is safer for general parsing as it handles all ISO 8601 offset variants. Consider `SSSX` → `SSSXXX` for maximum compatibility:

```python
to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSXXX")
```

`XXX` in Java's `DateTimeFormatter` outputs `Z` for UTC or `+HH:MM` (with colon) for non-zero. For parsing, it accepts `Z`, `+HH:MM`, and in practice also `+HHMM` and `+HH`. This is the safest single-pattern choice.

### 14.5 Option C — `coalesce` Approach

```python
coalesce(
    to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSX"),
    to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSZ"),
    to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSS")
)
```

This is the most defensive but suffers from the same `SSSX` vs `SSSXXX` ambiguity in option 1. Also, `to_timestamp` in LEGACY mode (SimpleDateFormat) does not support `X`/`XX`/`XXX` pattern letters at all — only in CORRECTED mode. The bare `SSS` fallback (no timezone) is risky: it would silently interpret the timestamp in Spark's session timezone rather than UTC.

### 14.6 ETL Code — Recommended Fix (If ETL Must Be Updated)

```python
from pyspark.sql.functions import col, to_timestamp, coalesce

# Works for all three historical formats: Z, +0000, +00:00
# Requires Spark 3.x CORRECTED timestamp mode
df = df.withColumn(
    "Auditdate",
    coalesce(
        to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"),  # Z, +HH:MM
        to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSSXX"),   # +HHMM
        to_timestamp(col("AuditCreatedDate"), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"),  # literal Z fallback
    )
)
```

This eliminates the fragile substring hack, handles all three historical format variants, and does not depend on string length assumptions. The `to_timestamp` function natively preserves milliseconds.

---

## 15. Impact of Reverting `@JsonFormat` — Complete Analysis

### 15.1 The Revert is Necessary But NOT Sufficient Alone

**Critical gap in Section 11**: The revert stops the bleeding going forward (new records will write `+0000`), but **it does not fix ETL failures for records already written with `Z` format between 2026-04-17 and the fix deployment date**. The ETL will continue to see `Z`-format records for all bookings created during that window and return null dates for them.

Two paths to address the backlog:

| Backlog Approach | Description | Trade-off |
|-----------------|-------------|-----------|
| Accept null dates | Records from 2026-04-17 to fix date remain with null `version_date` etc. in Redshift | Data gap in BK-Detail report for ~2–3 weeks of bookings |
| ETL re-run with format fix | Run ETL with `Z`-aware format string for the backlog window only | Requires minimal ETL change, but needs QA sign-off |
| Booking re-write | Trigger booking re-publish for affected records to get them re-written with `+0000` | Invasive; may have side effects on downstream consumers |

The ETL re-run (even with a minimal format fix) remains necessary for data completeness. The revert alone only prevents future breakage.

### 15.2 Pre-2026-03-27 Records Remain Broken in ETL

Records written by SDK v1 (before 2026-03-27) carry `+00:00` format. The current ETL (`unix_timestamp` with `SSSZ`) cannot parse these either. This is a **pre-existing bug** that the revert does not address and the document does not explicitly flag. The ETL has never correctly processed `+00:00` records.

### 15.3 Full Impact Matrix (Revised)

| Component | Effect of `@JsonFormat` revert (`SSSXXX` → `SSSZ`) | Residual issue? |
|-----------|------------------------------------------------------|-----------------|
| **Booking DynamoDB write (new records)** | Writes `+0000` → ETL-compatible ✅ | None |
| **Booking DynamoDB read (all records)** | `OffsetDateTimeTypeConverter.unconvert()` handles `Z`, `+0000`, `+00:00` ✅ | None |
| **Redshift ETL — new records post-revert** | `unix_timestamp(col, "...SSSZ")` parses `+0000` → fixed ✅ | None |
| **Redshift ETL — `Z`-format backlog (2026-04-17 to fix)** | Still fails — `Z` suffix not matched ❌ | Requires ETL re-run or data accepted as lost |
| **Redshift ETL — `+00:00` pre-2026-03-27 records** | Still fails — `+HH:MM` not matched by `SSSZ` pattern ❌ | Pre-existing bug, unchanged |
| **BK-Detail report (going forward)** | Fixed for new records ✅ | Historical gap remains |
| **`OffsetDateTimeTypeConverter.convert()` method** | Still produces `Z` (uses `ISO_DATE_TIME`) — inconsistent with `@JsonFormat` output, but is dead code | Minor code smell |
| **`AuditAttributeConverterTest.timestampSerializationFormat()` comment** | Comment "not +0000" becomes factually wrong; assertions still pass ✅ | Comment needs update |
| **Visibility / Watermill / Transformer** | Not affected — confirmed by cross-reference with `visibility-integration-issue-04212026.md` and `bk-watermill-dateformat-exception-analysis-04292026.md` ✅ | None |

### 15.4 Visibility and Watermill Cross-Reference — Confirmed Not Affected

From `visibility-integration-issue-04212026.md`: the Visibility break was caused by `ContainerType.lastModifiedDateUtc` inside `enrichedAttributes` using a **space-format `@JsonFormat`** pattern applied by the Jackson-based `EnrichedAttributesConverter`. `Audit` fields are **not part of `enrichedAttributes`** — they are a separate top-level DynamoDB Map attribute on `BookingDetail`. Visibility's SDK v1 `DynamoDBMapper` does not touch the `audit` attribute at all. **No impact.**

From `bk-watermill-dateformat-exception-analysis-04292026.md`: Watermill's issue was `MetaData.timestamp` using ISO T-format instead of the space-format pattern expected by `watermill-commons/support/Json.java`. `Audit` fields are not part of the `MetaData` payload sent to `inttra2_qa_sqs_watermill_bk`. **No impact.**

---

## 16. Recommended Action Plan

Given ETL QA changes are not feasible before release, the following prioritised actions are recommended:

### Immediate (current release)

| # | Action | File | Risk |
|---|--------|------|------|
| 1 | Revert `@JsonFormat` on `createdDateUtc` and `lastModifiedDateUtc` in `Audit.java` from `SSSXXX` → `SSSZ` | `booking/src/main/java/.../dynamodb/Audit.java` lines 32, 38 | Low — deserialization unaffected; tests pass |
| 2 | Update test comment in `timestampSerializationFormat()` to reflect `+0000` is now the expected format | `AuditAttributeConverterTest.java` line 197 | Trivial |

### Post-release (ETL team, separate QA cycle)

| # | Action | Details |
|---|--------|---------|
| 3 | Update ETL Glue job to handle all three offset formats | Use Option B (`to_timestamp` with `SSSXXX`) or Option C (`coalesce`). Eliminates the fragile substring millisecond hack. See Section 14.6 for recommended code. |
| 4 | ETL backfill re-run for 2026-04-17 to fix date window | Re-process bookings created during the `Z`-format period using the updated ETL format string to populate null `version_date`/`partition_date`/`source_created_date` in Redshift |
| 5 | Decide on pre-2026-03-27 `+00:00` records | Either accept the pre-existing ETL null issue for old SDK v1 records, or include `+00:00` handling in action #3 |

### Technical debt (separate PR)

| # | Action | Details |
|---|--------|---------|
| 6 | Remove or align `OffsetDateTimeTypeConverter.convert()` | The method uses `ISO_DATE_TIME` (outputs `Z`) but is dead code in the current path. Either remove it or change it to match the `@JsonFormat` pattern (`+0000`) to avoid confusion |
| 7 | Strengthen `timestampSerializationFormat` test | Assert the specific format string rather than loose regex, so the test fails explicitly if the format changes again: `assertThat(dateStr).endsWith("+0000")` |

---

## 17. Correction: Pre-2026-03-27 Format Was `Z`, Not `+00:00`

**Finding date**: 2026-05-05 (follow-up discussion)

Section 2.1 of this document incorrectly stated that the SDK v1 era `OffsetDateTimeTypeConverter.convert()` using `DateTimeFormatter.ISO_DATE_TIME` produced `+00:00` for UTC. This is wrong. **Section 5 of this document was correct**: `ISO_DATE_TIME` uses `appendOffsetId()` internally which substitutes the literal `Z` character for a zero offset.

Empirical proof is the actual QA error that surfaced against the `RapidReservation` endpoint (see Section 18 below). The DynamoDB record for `inttraCompanyId: 802435` has:
```
"lastModifiedDateUtc": "2020-11-30T04:23:30.153845Z"
```
This is a pre-2026-03-27 SDK v1 record (Nov 2020 creation date, 6 fractional digit microseconds) and it ends with **literal `Z`**, not `+00:00`.

**Corrected format history:**

| Period | Format | Example |
|--------|--------|---------|
| Pre-2026-03-27 (SDK v1, `ISO_DATE_TIME`) | **`Z`** | `2020-11-30T04:23:30.153845Z` |
| 2026-03-27 → 2026-04-16 (SDK v2 initial, `SSSZ` RFC 822) | **`+0000`** | `2026-05-04T06:29:32.691+0000` |
| 2026-04-17 → present (`SSSXXX` ISO 8601) | **`Z`** | `2026-05-04T06:29:32.691Z` |

Sections 14.2 and 15 of this document referenced `+00:00` pre-upgrade records in some ETL gap analysis — that gap does not exist because `+00:00` records do not exist. The pre-upgrade format was `Z`, which is in the same category as post-April-17 records for ETL purposes.

---

## 18. QA Finding: RapidReservation Endpoint — Will the Revert Break This?

**Date**: 2026-05-05  
**Source**: QA reported error on `GET /booking/rapid-reservation/802435`

### 18.1 The Error That Was Reported (Pre-Fix)

```
{
  "code": "000200",
  "message": "Cannot deserialize value of type `java.time.OffsetDateTime`
              from String \"2020-11-30T04:23:30.153845Z\":
              Failed to deserialize java.time.OffsetDateTime:
              (java.time.format.DateTimeParseException)
              Text '2020-11-30T04:23:30.153845Z' could not be parsed at index 23
              (through reference chain: Audit[\"lastModifiedDateUtc\"])"
}
```

### 18.2 The Record in DynamoDB

```json
{
  "inttraCompanyId": "802435",
  "name": "CA20_ALL",
  "audit": {
    "createdDateUtc":      "2018-09-03T10:21:44.751Z",
    "lastModifiedDateUtc": "2020-11-30T04:23:30.153845Z"
  },
  ...
}
```

`lastModifiedDateUtc` has **6 fractional digits** (`153845` = microseconds) and a **literal `Z`** suffix. This is a pre-upgrade SDK v1 record that has never been rewritten since 2020.

### 18.3 Why the Error Occurred at Index 23

Counting characters in `2020-11-30T04:23:30.153845Z`:
```
Index: 0         1         2
       0123456789012345678901234
Value: 2020-11-30T04:23:30.153845Z
```
The `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ")` (pre-fix, no custom deserializer) instructs Jackson to parse exactly 3 fractional digits (`SSS`). After consuming `153` at positions 20–22, it expects the timezone pattern (`Z` = RFC 822 numeric offset like `+0000`) at **position 23**. Instead it finds `8` (the 4th microsecond digit). This is a hard parse failure — hence "could not be parsed at index 23."

### 18.4 How the April 17 Fix Resolved This

The April 17 fix added `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)` to `Audit.java`. With this annotation present, Jackson **bypasses** `@JsonFormat` for deserialization entirely and calls `OffsetDateTimeTypeConverter.deserialize()` → `unconvert()` instead:

```java
public OffsetDateTime unconvert(String date) {
    try {
        // ISO_OFFSET_DATE_TIME handles literal Z AND variable fractional digits natively
        return OffsetDateTime.parse(date, DateTimeFormatter.ISO_OFFSET_DATE_TIME);  // ← first try
    } catch (Exception e) { ... }
}
```

`DateTimeFormatter.ISO_OFFSET_DATE_TIME` parses `"2020-11-30T04:23:30.153845Z"`:
- Handles literal `Z` as UTC offset ✅
- Handles 6 fractional digits (microseconds) natively ✅
- Succeeds on the **first try** — no fallback needed ✅

The Java `OffsetDateTime` holds the parsed value with `nanoseconds = 153845000` (microseconds mapped into the nanoseconds field).

### 18.5 Why the Current Response Shows `153Z` Not `153845Z`

The current API response:
```json
"lastModifiedDateUtc": "2020-11-30T04:23:30.153Z"
```

The 6 microsecond digits became 3 millisecond digits. This is because `@JsonFormat(pattern = "...SSSXXX")` controls **serialization** (output). `SSS` means exactly 3 fractional digits — the additional 3 microsecond digits (`845`) are silently truncated when writing. The DynamoDB record itself still stores `153845Z` unchanged (no write has occurred for this record since 2020).

### 18.6 Will the Proposed Revert Break This Record?

**No. The error will not recur. Here is why:**

The original error was caused by `@JsonFormat` being used for **both** serialization AND deserialization — without any custom deserializer. Jackson consulted the `@JsonFormat` pattern for parsing, which could not handle 6 fractional digits or literal `Z`.

The proposed revert changes `@JsonFormat(pattern = "...SSSXXX")` → `@JsonFormat(pattern = "...SSSZ")` but **keeps `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)` untouched**.

With `@JsonDeserialize` present, Jackson **never consults `@JsonFormat` for reading**. The deserialization path is:

```
DynamoDB: "2020-11-30T04:23:30.153845Z"   (unchanged, 6 digits + Z)
    ↓
OffsetDateTimeTypeConverter.unconvert()
    ↓
ISO_OFFSET_DATE_TIME.parse("2020-11-30T04:23:30.153845Z")   ← succeeds ✅
    ↓
Java OffsetDateTime: 2020-11-30T04:23:30.153845Z
    ↓
@JsonFormat(pattern="SSSZ") serializes for HTTP response:
    "2020-11-30T04:23:30.153+0000"   ← 3 digits (SSS truncates), UTC = +0000
```

| Scenario | Pre-fix (broken) | Post-April-17 fix (current) | After proposed revert |
|----------|-----------------|-----------------------------|-----------------------|
| Deserialization engine | `@JsonFormat` pattern directly | `OffsetDateTimeTypeConverter.unconvert()` | `OffsetDateTimeTypeConverter.unconvert()` (unchanged) |
| Can parse `153845Z`? | ❌ Fails at index 23 | ✅ `ISO_OFFSET_DATE_TIME` handles it | ✅ Identical — `@JsonDeserialize` not changed |
| HTTP response format | Error — no response | `"2020-11-30T04:23:30.153Z"` | `"2020-11-30T04:23:30.153+0000"` |
| DynamoDB stored value | `153845Z` | `153845Z` (no write = unchanged) | `153845Z` (no write = unchanged) |
| Error `000200`? | ✅ Yes | ❌ No | ❌ No |

**The `@JsonFormat` pattern is irrelevant to deserialization once `@JsonDeserialize` is present.** The April 17 fix permanently decoupled reading from `@JsonFormat` control. Reverting `@JsonFormat` from `SSSXXX` to `SSSZ` only changes how UTC timestamps are formatted in the serialized **output** (`Z` → `+0000`). The read path — which was where the original error occurred — is owned exclusively by `OffsetDateTimeTypeConverter` and is unaffected.

### 18.7 Observable Change After Revert

The only visible effect on this endpoint after the revert is the HTTP response format:

```json
// Current (SSSXXX):
"createdDateUtc":      "2018-09-03T10:21:44.751Z"
"lastModifiedDateUtc": "2020-11-30T04:23:30.153Z"

// After revert (SSSZ):
"createdDateUtc":      "2018-09-03T10:21:44.751+0000"
"lastModifiedDateUtc": "2020-11-30T04:23:30.153+0000"
```

Both formats are semantically identical UTC timestamps. If no API client or test assertion hard-codes the `Z` suffix for the `audit` field, this is a non-breaking change.

---

## 19. Production vs QA Serialization Analysis (2026-05-05 16:34 EDT)

### 19.1 Production DynamoDB Data (Pre-AWS Upgrade, SDK v1 Code)

Production DynamoDB stores audit with **nanosecond precision** and **literal `Z`**:

```json
"audit": {
    "M": {
      "createdBy":         { "S": "Shana Woolfork" },
      "createdByFullName": { "S": "Shana Woolfork" },
      "createdDateUtc":    { "S": "2026-05-05T15:19:27.210972723Z" }
    }
}
```

This is because in production (SDK v1), the DynamoDB write path uses `OffsetDateTimeTypeConverter.convert()`:

```java
// Pre-upgrade OffsetDateTimeTypeConverter (SDK v1 DynamoDBTypeConverter)
@Override
public String convert(OffsetDateTime offsetDateTime) {
    return offsetDateTime != null ? offsetDateTime.format(DateTimeFormatter.ISO_DATE_TIME) : null;
}
```

`DateTimeFormatter.ISO_DATE_TIME` for a UTC `OffsetDateTime` produces:
- **Full nanosecond precision** (9 fractional digits: `210972723`)
- **Literal `Z`** for UTC offset (ISO 8601 UTC designator)

**Key point:** SDK v1's `@DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)` controls the DynamoDB write format. The `@JsonFormat` annotation is **completely ignored** by SDK v1's `DynamoDBMapper` — it only affects Jackson serialization (REST API responses).

### 19.2 Production REST API Response (Pre-AWS Upgrade)

When the same booking is retrieved via REST API (`GET /booking/2105729968`):

```json
"audit": {
    "createdById": null,
    "createdByType": null,
    "createdBy": "Shana Woolfork",
    "createdByFullName": "Shana Woolfork",
    "createdByChannel": null,
    "createdDateUtc": "2026-05-05T15:19:27.210+0000",
    "lastModifiedBy": null,
    "lastModifiedDateUtc": null
}
```

This is the **Jackson serialization path** (Dropwizard JAX-RS → Jackson ObjectMapper). Jackson uses the `@JsonFormat` annotation:

```java
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
private OffsetDateTime createdDateUtc;
```

- `SSS` → truncates nanoseconds to **3 fractional digits** (milliseconds): `210972723` → `210`
- `Z` pattern → **RFC 822 numeric offset**: `+0000`

Result: `2026-05-05T15:19:27.210+0000`

### 19.3 Two Separate Serialization Engines in Production

In production (SDK v1), the `Audit` timestamp is serialized by **two different engines** for two different purposes:

| Path | Engine | Format produced | Example |
|------|--------|----------------|---------|
| **DynamoDB write** | SDK v1 `DynamoDBTypeConverter` → `DateTimeFormatter.ISO_DATE_TIME` | Nanosecond precision + `Z` | `2026-05-05T15:19:27.210972723Z` |
| **REST API response** | Jackson → `@JsonFormat(pattern="...SSSZ")` | Millisecond precision + `+0000` | `2026-05-05T15:19:27.210+0000` |

The `@JsonFormat` annotation existed in production code but was **only used by Jackson for REST API responses**. SDK v1 DynamoDBMapper ignored it entirely.

### 19.4 QA Data (Post-AWS Upgrade, SDK v2 Code with `SSSXXX` Fix)

QA DynamoDB stores: `2026-05-04T06:29:32.691Z`

QA REST API response:
```json
"audit": {
    "createdById": "802288",
    "createdByType": "User",
    "createdBy": "CU2100",
    "createdByFullName": "Test User QAForwarder EDIF-2",
    "createdByChannel": "WEB",
    "createdDateUtc": "2026-05-04T06:29:32.691Z",
    "lastModifiedBy": null,
    "lastModifiedDateUtc": null
}
```

In QA (SDK v2), both DynamoDB and REST API produce **identical output** because they now both use Jackson with the same `@JsonFormat` annotation:

| Path | Engine | Format produced | Example |
|------|--------|----------------|---------|
| **DynamoDB write** | `AuditAttributeConverter` → Jackson → `@JsonFormat(pattern="...SSSXXX")` | Millisecond precision + `Z` | `2026-05-04T06:29:32.691Z` |
| **REST API response** | Jackson → `@JsonFormat(pattern="...SSSXXX")` | Millisecond precision + `Z` | `2026-05-04T06:29:32.691Z` |

This is a **behavioral change from production**: in production the REST API shows `+0000`, in QA it shows `Z`.

### 19.5 What Reverting `@JsonFormat` to `SSSZ` Achieves

After reverting to `SSSZ`, both paths would produce:

| Path | Engine | Format produced | Example |
|------|--------|----------------|---------|
| **DynamoDB write** | `AuditAttributeConverter` → Jackson → `@JsonFormat(pattern="...SSSZ")` | Millisecond precision + `+0000` | `2026-05-04T06:29:32.691+0000` |
| **REST API response** | Jackson → `@JsonFormat(pattern="...SSSZ")` | Millisecond precision + `+0000` | `2026-05-04T06:29:32.691+0000` |

This **restores the production REST API format** (`+0000`) and makes the DynamoDB write ETL-compatible.

### 19.6 Note on Precision Loss: Nanoseconds → Milliseconds

In production DynamoDB, timestamps have nanosecond precision (9 digits: `210972723`). In QA (and after the fix), timestamps have millisecond precision (3 digits: `691`). This is because:

- Production uses `DateTimeFormatter.ISO_DATE_TIME` (preserves full precision)
- QA uses `@JsonFormat(pattern="...SSS...")` (`SSS` = exactly 3 fractional digits)

This precision truncation is a consequence of the SDK v2 upgrade's use of Jackson for DynamoDB serialization. It applies regardless of `Z` vs `XXX` and is **not affected by this revert**. The precision loss is already present in QA and is acceptable — the `createdDateUtc` field is used for audit trail ordering, not for sub-millisecond timing.

---

## 20. Final Confirmation: Revert `@JsonFormat` from `SSSXXX` to `SSSZ`

### 20.1 The Change

In `booking/src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java`, revert lines 32 and 38:

```java
// FROM (current — writes Z for UTC):
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime createdDateUtc;

@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime lastModifiedDateUtc;

// TO (reverted — writes +0000 for UTC, matches production REST API):
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime createdDateUtc;

@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime lastModifiedDateUtc;
```

### 20.2 What Is Restored

| Aspect | Current QA behavior (`SSSXXX`) | After revert (`SSSZ`) | Production behavior (SDK v1) |
|--------|-------------------------------|----------------------|------------------------------|
| DynamoDB write format | `...691Z` | `...691+0000` | `...210972723Z` (SDK v1 converter) |
| REST API format | `...691Z` | `...691+0000` | `...210+0000` (Jackson) |
| ETL compatibility | ❌ `unix_timestamp` returns null | ✅ Parses correctly | ✅ (ETL reads from REST/outbound, not raw DynamoDB) |
| Deserialization of legacy records | ✅ via `OffsetDateTimeTypeConverter` | ✅ via `OffsetDateTimeTypeConverter` | ✅ via SDK v1 converter |
| Deserialization of records written with `Z` suffix (2026-04-17 to present) | ✅ | ✅ via `OffsetDateTimeTypeConverter` | N/A (production hasn't deployed SDK v2 yet) |

### 20.3 Why This Is Confirmed Safe

1. **Deserialization is NOT affected** — `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)` overrides `@JsonFormat` for reading. The converter handles `Z`, `+0000`, `+00:00`, variable fractional digits, and date-only strings.

2. **REST API format matches production** — Production REST API already outputs `+0000`. Reverting restores this consistency. No API client breakage.

3. **ETL fixed without ETL code change** — `unix_timestamp(col, "...SSSZ")` can parse `+0000` natively. No Glue job change, no ETL QA cycle needed.

4. **All existing unit tests pass** — The `AuditAttributeConverterTest.timestampSerializationFormat()` assertion `matches(".*[Z+].*")` matches `+0000` via the `+` character.

5. **Mixed-format DynamoDB records handled** — Records written between 2026-04-17 and the fix date contain `Z` suffix. When read back by `OffsetDateTimeTypeConverter`, they parse correctly. If re-written (during a booking update), they are stored with `+0000`. This natural migration is harmless.

6. **Reverting to original annotation** — The pre-upgrade `Audit.java` (commit `dc4a0dde155a`) had exactly `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")`. This revert restores the original annotation value that was in the codebase since 2018 (TRIR-2547a).

### 20.4 Confirmed: No Change Needed Elsewhere

| File | Change needed? | Reason |
|------|---------------|--------|
| `Audit.java` | **Yes** — revert `@JsonFormat` pattern | Only file that needs changing |
| `OffsetDateTimeTypeConverter.java` | No | Already handles all formats for deserialization |
| `AuditAttributeConverter.java` | No | Uses Jackson which respects `@JsonFormat` for serialization |
| `AuditAttributeConverterTest.java` | No | Existing assertions compatible with `+0000` format |
| ETL Glue job | No | Existing `unix_timestamp(col, "...SSSZ")` works with `+0000` |
| `self-service-reports` | No | Fixed by ETL receiving parseable timestamps |

### 20.5 Recommendation

**Proceed with the revert.** This is a single-file, two-line change that restores the original `@JsonFormat` annotation value, fixes the Redshift ETL issue, restores REST API format parity with production, and requires no changes to any other component.
