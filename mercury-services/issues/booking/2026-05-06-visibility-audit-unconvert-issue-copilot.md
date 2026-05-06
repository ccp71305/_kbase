# Visibility Audit Unconvert Exception — Root Cause Analysis

**Date**: 2026-05-06  
**Module**: `visibility` (consumer) / `booking` (source)  
**Agent Model**: Claude Opus 4.6  
**Session ID**: `15c46f32e8c84851`  
**Related**: `booking/docs/2026-05-05-booking-redshift-audit-field-issue.md` (yesterday's analysis)

---

## 1. Reported Error

```
ERROR [pool-4-thread-9] [2026-05-06 12:48:39.053]
com.inttra.mercury.visibility.matcher.processor.MatchingProcessor:
Container Event Id: ce:b2715f13-88fc-498c-beb4-da0658af37f8 - Failed Matching Processor

com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMappingException:
  BookingDetailVisibility[audit]; could not unconvert attribute

Caused by: DynamoDBMappingException:
  Audit[createdDateUtc]; could not unconvert attribute

Caused by: java.time.format.DateTimeParseException:
  Text '2026-05-06T12:47:47.044+0000' could not be parsed, unparsed text found at index 10
    at LocalDate.parse(...)
    at OffsetDateTimeTypeConverter.unconvert(OffsetDateTimeTypeConverter.java:39)
```

---

## 2. Quick Summary (For Everyone)

### What broke?

The **Visibility Matcher** service crashed when trying to read a booking record from DynamoDB.
The timestamp field `audit.createdDateUtc` was stored as `"2026-05-06T12:47:47.044+0000"` (with `+0000` at the end).
The old timestamp parser used by visibility does **not** understand `+0000` — it only understands `Z` or `+00:00`.

### Why did it break?

Yesterday's commit (`c12750e13e47`) changed how the **booking module** formats timestamps when saving to DynamoDB.
The change was made to fix a Redshift ETL issue — but it accidentally introduced a format that **visibility cannot read**.

### Why wasn't this caught?

Yesterday's analysis incorrectly concluded that "visibility doesn't touch the `audit` field."
In fact, visibility DOES read the `audit` field — the analysis confused two different parts of the data.

### The real root cause

Before the AWS upgrade, the booking module had **two separate formatting paths**:
1. **DynamoDB storage** used a converter that always wrote `Z` (e.g., `...210972723Z`)
2. **REST API responses** used Jackson `@JsonFormat` that wrote `+0000` (e.g., `...210+0000`)

These were **independent**. After the upgrade, both paths now go through the same Jackson `@JsonFormat`,
which means changing the format for one also changes it for the other. This coupling is the fundamental problem.

### The fix

**Re-decouple these two paths.** Modify `AuditAttributeConverter` to use a DynamoDB-specific formatter
that writes `Z` (matching pre-upgrade behavior), while keeping `@JsonFormat(SSSZ)` for REST API output
(which produces `+0000` for ETL compatibility).

- **DynamoDB** → `Z` → visibility can read ✅, matches production ✅
- **REST API** → `+0000` → ETL can read ✅

---

## 3. Detailed Technical Analysis

### 3.1 Terminology: Serialization vs Deserialization

These terms are used throughout this document and are often confused:

| Term | Direction | What it means | Example |
|------|-----------|---------------|---------|
| **Serialization** | Java object → output format | **Writing/formatting** a Java object into a string, JSON, or DynamoDB attribute | `OffsetDateTime` → `"2026-05-06T12:47:47.044+0000"` |
| **Deserialization** | Input format → Java object | **Reading/parsing** a string, JSON, or DynamoDB attribute into a Java object | `"2026-05-06T12:47:47.044+0000"` → `OffsetDateTime` |

When a REST API returns booking data, **two steps** happen:
1. **Read from DynamoDB** → Java `Audit` object (this is **deserialization** — converting stored data to a Java object)
2. **Java `Audit` object** → JSON response (this is **serialization** — converting the Java object to output format for the API consumer)

`@JsonFormat` controls step 2 — it tells Jackson how to **serialize** (format/write) the `OffsetDateTime` field when producing JSON output.

### 3.2 How Timestamps Were Formatted BEFORE the AWS Upgrade (Production Today)

In production, the booking module still runs the **pre-upgrade SDK v1 code**. The `Audit` class has TWO different formatting mechanisms that operate **independently**:

#### Path 1: DynamoDB Storage (Writing to the database)

```
Java OffsetDateTime object
    ↓
@DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)
    ↓
OffsetDateTimeTypeConverter.convert(offsetDateTime)
    ↓
offsetDateTime.format(DateTimeFormatter.ISO_DATE_TIME)
    ↓
Stored in DynamoDB as String: "2026-05-05T15:19:27.210972723Z"
                                                          ^^^
                                              LITERAL Z = UTC indicator
```

`DateTimeFormatter.ISO_DATE_TIME` always outputs the literal `Z` character for UTC timestamps.
It also preserves **full precision** (nanoseconds — 9 fractional digits).

#### Path 2: REST API Response (Sending JSON to API consumers / outbound pipeline)

```
Java OffsetDateTime object (read from DynamoDB via Path 1 in reverse)
    ↓
Jackson serialization
    ↓
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
    ↓
JSON output: "2026-05-05T15:19:27.210+0000"
                                      ^^^^^
                                 RFC 822 offset = "+0000"
```

In the `@JsonFormat` pattern, the capital `Z` is a **Java pattern letter** (not a literal `Z` character).
It means "RFC 822 timezone offset" which formats UTC as `+0000` (four digits, no colon).
The `SSS` means exactly 3 fractional digits (milliseconds), so nanoseconds are **truncated**.

#### Key insight: these paths were DECOUPLED

```
                    ┌─── Path 1: DynamoDB ────→ "...Z"         (ISO_DATE_TIME)
Java Audit object ──┤
                    └─── Path 2: REST API ────→ "...+0000"     (@JsonFormat SSSZ)
```

Each path had its own formatter. Changing `@JsonFormat` did NOT affect what was stored in DynamoDB.

#### Production data proof

From production DynamoDB (booking that was just created):
```
DynamoDB stored value:    "2026-05-05T15:19:27.210972723Z"     ← Z format, nanoseconds
REST API response:        "2026-05-05T15:19:27.210+0000"       ← +0000 format, milliseconds
```

Same booking, same timestamp, but **different formats** — because different formatters are used.

### 3.3 How Timestamps Are Formatted AFTER the AWS Upgrade (QA Today)

The AWS upgrade replaced the SDK v1 `@DynamoDBTypeConverted` annotation with an SDK v2 `AuditAttributeConverter`.
This converter uses **Jackson** (with `@JsonFormat`) to convert `Audit` to a DynamoDB Map:

```java
// AuditAttributeConverter.transformFrom() — post-upgrade
public AttributeValue transformFrom(Audit audit) {
    // Uses Jackson ObjectMapper — which respects @JsonFormat
    Map<String, Object> javaMap = OBJECT_MAPPER.convertValue(audit, Map.class);
    return AttributeValue.fromM(LegacyMapConverter.toAttributeValueMap(javaMap));
}
```

`OBJECT_MAPPER.convertValue(audit, Map.class)` uses Jackson serialization internally.
Jackson sees `@JsonFormat(pattern = "SSSZ")` on `createdDateUtc` and formats it as `+0000`.

**This is the coupling**: DynamoDB storage now goes through the SAME `@JsonFormat` as REST API responses.

```
                    ┌─── Path 1: DynamoDB ──┐
Java Audit object ──┤                       ├──→ BOTH use @JsonFormat ──→ "...+0000"
                    └─── Path 2: REST API ──┘
```

With `@JsonFormat(pattern = "SSSZ")`: BOTH paths produce `+0000`
With `@JsonFormat(pattern = "SSSXXX")`: BOTH paths produce `Z`

There is no way to produce `Z` for DynamoDB and `+0000` for REST using a single `@JsonFormat` — 
**unless we decouple them again**.

### 3.4 How Visibility Reads the `audit` Field

The visibility module depends on `booking:2.1.8.M` — a **pre-upgrade** published artifact containing the OLD model classes with SDK v1 annotations.

```java
// BookingDetailVisibility (in visibility-commons)
@DynamoDBTable(tableName = "booking_BookingDetail")
public class BookingDetailVisibility extends BookingDetail { }

// BookingDetail (from booking:2.1.8.M — pre-upgrade)
@DynamoDBTable(tableName = "BookingDetail")
public class BookingDetail implements Expires {
    @DynamoDBAttribute
    private Audit audit;    // ← DynamoDB reads this field
    // ... other fields
}

// Audit (from booking:2.1.8.M — pre-upgrade)
@DynamoDBDocument
public class Audit {
    @DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)
    @JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")
    private OffsetDateTime createdDateUtc;
}
```

When visibility calls `DynamoDBMapper.query()` to read a `BookingDetailVisibility` record, the SDK v1 mapper:

1. Reads the top-level DynamoDB item (a Map of attributes)
2. Finds the `audit` attribute (which is a nested Map — DynamoDB type `M`)
3. Sees `@DynamoDBDocument` on the `Audit` class → knows to recursively process it
4. Inside the Audit map, finds `createdDateUtc` (a String — DynamoDB type `S`)
5. Sees `@DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)` → calls the converter
6. Calls `OffsetDateTimeTypeConverter.unconvert("2026-05-06T12:47:47.044+0000")`

**This is why the analysis was wrong**: it said "visibility doesn't touch the `audit` attribute."
In reality, the SDK v1 `DynamoDBMapper` reads and processes **every** annotated field on the model class,
including nested `@DynamoDBDocument` objects like `audit`.

### 3.5 Why the Old Converter Cannot Parse `+0000`

The old `OffsetDateTimeTypeConverter` in `booking:2.1.8.M`:

```java
// OLD converter (pre-upgrade, in booking:2.1.8.M)
public OffsetDateTime unconvert(String date) {
    try {
        //──── STEP 1: Try ISO_OFFSET_DATE_TIME ────
        return date != null
            ? OffsetDateTime.parse(date, DateTimeFormatter.ISO_OFFSET_DATE_TIME)
            : null;
    } catch (Exception e) {
        //──── STEP 2: Fallback to date-only parsing ────
        return OffsetDateTime.of(
            LocalDate.parse(date, DateTimeFormatter.ISO_DATE),  // ← line 39
            LocalTime.MIDNIGHT, ZoneOffset.UTC);
    }
}
```

**Step 1 fails** — `ISO_OFFSET_DATE_TIME` is a Java standard formatter that requires the timezone offset
in one of these formats:

| Accepted by `ISO_OFFSET_DATE_TIME` | Example | Works? |
|-------------------------------------|---------|--------|
| Literal `Z` | `...044Z` | ✅ Yes |
| `+HH:MM` (with colon) | `...044+00:00` | ✅ Yes |
| `+HHMM` (no colon) | `...044+0000` | ❌ **No** |

The `+0000` format (no colon between hours and minutes) is an **RFC 822** offset format.
It is NOT valid for `ISO_OFFSET_DATE_TIME`, which only accepts ISO 8601 offsets (with colon or `Z`).

**Step 2 fails** — After Step 1 throws an exception, the code falls back to parsing just a date:
```
Input: "2026-05-06T12:47:47.044+0000"
        ^^^^^^^^^^
        ISO_DATE parses this (10 chars = "2026-05-06")
                  ^^^^^^^^^^^^^^^^^
                  "T12:47:47.044+0000" is UNPARSED TEXT → exception at index 10
```

`DateTimeFormatter.ISO_DATE` only parses `YYYY-MM-DD`. It successfully parses the first 10 characters
but then finds unexpected text starting with `T` at position 10. This is a strict parse failure.

### 3.6 What the Current (Upgraded) Converter Does Differently

The current workspace converter has an **additional normalization step** that the old one lacks:

```java
// CURRENT converter (post-upgrade, in workspace)
public OffsetDateTime unconvert(String date) {
    if (date == null) return null;
    try {
        //──── STEP 1: Same as old ────
        return OffsetDateTime.parse(date, DateTimeFormatter.ISO_OFFSET_DATE_TIME);
    } catch (Exception e) {
        try {
            //──── STEP 2: ★ NORMALIZATION — MISSING FROM OLD CONVERTER ★ ────
            // Convert "+0000" → "+00:00" (insert colon between hours and minutes)
            String normalized = date.replaceAll("([+-])(\\d{2})(\\d{2})$", "$1$2:$3");
            if (!normalized.equals(date)) {
                return OffsetDateTime.parse(normalized, DateTimeFormatter.ISO_OFFSET_DATE_TIME);
            }
        } catch (Exception ignored) {
            // fall through
        }
        //──── STEP 3: Date-only fallback ────
        return OffsetDateTime.of(
            LocalDate.parse(date, DateTimeFormatter.ISO_DATE),
            LocalTime.MIDNIGHT, ZoneOffset.UTC);
    }
}
```

The normalization step transforms `+0000` → `+00:00`, which IS valid for `ISO_OFFSET_DATE_TIME`.
This step was added during the AWS upgrade. The old `2.1.8.M` artifact was published before this change.

---

## 4. Why Yesterday's Analysis Was Wrong

Section 15.4 of `2026-05-05-booking-redshift-audit-field-issue.md` stated:

> "Visibility's SDK v1 `DynamoDBMapper` does not touch the `audit` attribute at all. **No impact.**"

This claim confused **two completely different data paths**:

| # | Data path | What reads it | When it was broken (previously) | Current issue? |
|---|-----------|---------------|---------------------------------|----------------|
| **A** | `enrichedAttributes` → `ContainerType.lastModifiedDateUtc` | Jackson-based `EnrichedAttributesConverter` | Yes — documented in `visibility-integration-issue-04212026.md` | No |
| **B** | `audit` → `Audit.createdDateUtc` | SDK v1 `DynamoDBMapper` + `@DynamoDBDocument` | **Never broke before** (format was always `Z` until now) | **YES — current issue** |

The previous visibility issue (Path A) was about the `enrichedAttributes` field using a Jackson converter.
The analysis correctly noted that `audit` is NOT inside `enrichedAttributes`.

But then it **incorrectly generalized** this to mean visibility never reads the `audit` field at all.
In reality, `audit` is a **separate top-level field** on `BookingDetail`. The SDK v1 `DynamoDBMapper`
reads ALL annotated fields — it has no mechanism to skip specific fields during query results mapping.

---

## 5. Format Compatibility Matrix

### 5.1 DynamoDB Timestamp Format History

| Period | Who writes | How it serializes | DynamoDB value | Visibility reads? | ETL reads? |
|--------|-----------|-------------------|----------------|-------------------|------------|
| **Pre-2026-03-27** (SDK v1, production today) | `DynamoDBTypeConverter.convert()` | `ISO_DATE_TIME` | `...Z` | ✅ Yes | ❌ No (but ETL reads REST, not DynamoDB directly) |
| **2026-03-27 → 2026-04-16** (SDK v2 initial, QA) | `AuditAttributeConverter` + Jackson | `@JsonFormat(SSSZ)` | `...+0000` | ❌ No | ✅ Yes |
| **2026-04-17 → 2026-05-04** (data-format fix, QA) | `AuditAttributeConverter` + Jackson | `@JsonFormat(SSSXXX)` | `...Z` | ✅ Yes | ❌ No |
| **2026-05-05 → present** (redshift revert, QA) | `AuditAttributeConverter` + Jackson | `@JsonFormat(SSSZ)` | `...+0000` | ❌ **No — BROKEN** | ✅ Yes |

### 5.2 The Fundamental Problem: No Single `@JsonFormat` Satisfies All

| Java pattern | What it produces for UTC | Visibility (old converter) | ETL (`SSSZ` parse pattern) |
|--------------|-------------------------|----------------------------|----------------------------|
| `Z` (RFC 822) | `+0000` | ❌ Cannot parse | ✅ Can parse |
| `XX` | `+0000` | ❌ Cannot parse | ✅ Can parse |
| `XXX` (ISO 8601) | `Z` (literal) | ✅ Can parse | ❌ Cannot parse |
| `xxx` | `+00:00` | ✅ Can parse | ❌ Cannot parse |

There is **no single pattern** that produces a format parseable by both consumers.
This is why the fix must **decouple the two paths** rather than trying to find a one-size-fits-all pattern.

---

## 6. The Actual Fix: Decouple DynamoDB and REST API Serialization

### 6.1 The Principle

Restore the **pre-upgrade architecture** where DynamoDB storage and REST API output used different formatters:

```
                                 PRE-UPGRADE (production)
                    ┌─── Path 1: DynamoDB ────→ "...Z"         (ISO_DATE_TIME via DynamoDBTypeConverter)
Java Audit object ──┤
                    └─── Path 2: REST API ────→ "...+0000"     (@JsonFormat SSSZ via Jackson)


                                 POST-UPGRADE (after this fix)
                    ┌─── Path 1: DynamoDB ────→ "...Z"         (ISO_DATE_TIME via DynamoDB-specific mapper)
Java Audit object ──┤
                    └─── Path 2: REST API ────→ "...+0000"     (@JsonFormat SSSZ via Jackson — unchanged)
```

### 6.2 Implementation

**Modify `AuditAttributeConverter`** to use a **DynamoDB-specific ObjectMapper** for writing to DynamoDB.
This mapper uses `DateTimeFormatter.ISO_DATE_TIME` (same as the old `DynamoDBTypeConverter.convert()`),
ignoring `@JsonFormat` on the fields.

**Keep `@JsonFormat(pattern = "SSSZ")` on `Audit.java`** — it continues to control REST API output,
producing `+0000` for ETL compatibility. But it no longer affects DynamoDB storage.

### 6.3 What Changes

| Component | Before fix | After fix | Impact |
|-----------|-----------|-----------|--------|
| `AuditAttributeConverter.transformFrom()` | Uses shared `OBJECT_MAPPER` (reads `@JsonFormat`) | Uses `DYNAMO_OBJECT_MAPPER` (ignores `@JsonFormat`, uses `ISO_DATE_TIME`) | DynamoDB stores `Z` instead of `+0000` |
| `AuditAttributeConverter.transformTo()` | Uses shared `OBJECT_MAPPER` | No change — shared `OBJECT_MAPPER` still handles deserialization | Reads both `Z` and `+0000` ✅ |
| `Audit.java` `@JsonFormat` | `SSSZ` | `SSSZ` — **no change** | REST API still produces `+0000` ✅ |
| DynamoDB stored value | `...+0000` | `...Z` (matches production) | Visibility can read ✅ |
| REST API JSON output | `...+0000` | `...+0000` — **no change** | ETL can read ✅ |

### 6.4 Result: Full Compatibility

| Consumer | Format it sees | Can parse? |
|----------|---------------|------------|
| **Visibility** (reads DynamoDB directly via SDK v1) | `Z` (from DynamoDB) | ✅ `ISO_OFFSET_DATE_TIME` handles `Z` |
| **Booking** (reads DynamoDB via SDK v2 `AuditAttributeConverter`) | `Z` or `+0000` (mixed historical data) | ✅ `OffsetDateTimeTypeConverter` handles both |
| **ETL** (reads from REST API / outbound pipeline) | `+0000` (from `@JsonFormat SSSZ`) | ✅ `unix_timestamp("SSSZ")` handles `+0000` |
| **Watermill / Transformer** | Not affected (uses `MetaData.timestamp`) | ✅ N/A |

---

## 7. Why the Previous Analysis Claim Was Wrong (Detailed)

### 7.1 The Incorrect Claim

From `2026-05-05-booking-redshift-audit-field-issue.md`, Section 15.4:

> "From `visibility-integration-issue-04212026.md`: the Visibility break was caused by
> `ContainerType.lastModifiedDateUtc` inside `enrichedAttributes` using a space-format `@JsonFormat`
> pattern applied by the Jackson-based `EnrichedAttributesConverter`. `Audit` fields are not part of
> `enrichedAttributes` — they are a separate top-level DynamoDB Map attribute on `BookingDetail`.
> Visibility's SDK v1 `DynamoDBMapper` does not touch the `audit` attribute at all. **No impact.**"

### 7.2 Why It's Wrong

The claim "DynamoDBMapper does not touch the `audit` attribute at all" is factually incorrect.

The SDK v1 `DynamoDBMapper` works by **reflection**: when you call `mapper.query(BookingDetailVisibility.class, ...)`,
it reads the DynamoDB item and maps EVERY attribute to the corresponding Java field based on annotations.
There is no mechanism to selectively skip fields during a query result mapping.

The `BookingDetail` class (from `booking:2.1.8.M`) has:
```java
@DynamoDBAttribute
private Audit audit;
```

The `@DynamoDBAttribute` annotation tells `DynamoDBMapper`: "this field corresponds to a DynamoDB attribute;
read it and write it." When the mapper reads a `BookingDetailVisibility` record, it processes the `audit`
attribute just like any other field.

The `Audit` class has `@DynamoDBDocument`, which tells the mapper: "this is a nested object stored as a
DynamoDB Map; recursively process its fields." Inside `Audit`, `createdDateUtc` has
`@DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)`, which tells the mapper: "use this
converter to transform the stored String into an `OffsetDateTime`."

### 7.3 The Confusion

The analysis confused two different things:
1. **The `enrichedAttributes` field** — which uses a Jackson-based converter (`EnrichedAttributesConverter`)
   and was the subject of the PREVIOUS visibility break
2. **The `audit` field** — which uses SDK v1's native `@DynamoDBDocument` unconversion mechanism
   and is the subject of the CURRENT break

The analysis correctly determined that `audit` is not inside `enrichedAttributes`. But it then incorrectly
concluded that the DynamoDBMapper doesn't process `audit` at all — confusing "not part of enrichedAttributes"
with "not read by DynamoDBMapper."

---

## 8. Architectural Lesson

### Before the upgrade:
```
@DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)
    → OffsetDateTimeTypeConverter.convert() uses ISO_DATE_TIME → writes "Z"
    → This is the DynamoDB serialization path
    → Independent of @JsonFormat

@JsonFormat(pattern = "SSSZ")
    → Jackson uses this for REST API responses → writes "+0000"
    → This is the REST API serialization path
    → Independent of DynamoDB storage
```

### After the upgrade (before this fix):
```
AuditAttributeConverter.transformFrom() uses Jackson OBJECT_MAPPER
    → Jackson sees @JsonFormat(SSSZ) → writes "+0000" to DynamoDB
    → SAME Jackson is used for REST API responses
    → DynamoDB and REST API are NOW COUPLED through @JsonFormat
```

### After this fix:
```
AuditAttributeConverter.transformFrom() uses DYNAMO_OBJECT_MAPPER
    → Custom serializer uses ISO_DATE_TIME → writes "Z" to DynamoDB
    → DECOUPLED from @JsonFormat

@JsonFormat(SSSZ) still controls REST API responses → writes "+0000"
    → DECOUPLED from DynamoDB storage
```

**The fundamental architectural principle**: when upgrading from SDK v1 to SDK v2, the DynamoDB storage format
must be preserved. If the pre-upgrade code used a specific formatter for DynamoDB writes, the upgrade must
replicate that formatter — not replace it with a different one (like `@JsonFormat`) that serves a different purpose.

---

## 9. Records Already Written With `+0000` in QA

Records written between 2026-03-27 → 2026-04-16 and 2026-05-05 → present have `+0000` format in QA DynamoDB.

| Consumer | Can read `+0000`? | Impact |
|----------|-------------------|--------|
| **Booking** (new converter) | ✅ Yes (normalization step) | No impact |
| **Visibility** (old converter) | ❌ No | Will fail if visibility reads these specific records |

Options for existing `+0000` records:
1. **Data migration** — normalize `+0000` → `Z` in DynamoDB for affected records in QA
2. **Accept and wait** — these records age out; new records will be `Z`
3. **Publish updated `booking:2.1.9.M`** with a fixed converter (longer-term)

---

## 10. Tutorial: The "Z" Confusion — Pattern Letters vs Literal Characters

### 10.1 The Two Meanings of "Z"

The letter `Z` appears in two completely different contexts in timestamp handling. They LOOK the same but mean different things:

#### Meaning 1: `Z` as a **literal character** at the end of a timestamp

```
"2026-05-05T15:19:27.210972723Z"
                               ^
                               This is the literal character Z
                               It means "UTC" in ISO 8601 standard
                               It's a shorthand for "+00:00"
```

When you see `Z` at the end of a timestamp in actual data, it's a literal character meaning "this time is in UTC."
It's called "Zulu time" in military/aviation terminology.

#### Meaning 2: `Z` as a **pattern letter** inside a Java DateTimeFormatter pattern

```java
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ")
                                                  ^
                                                  This is a PATTERN LETTER
                                                  It means "format as RFC 822 offset"
                                                  For UTC, it outputs: +0000
```

In Java's `DateTimeFormatter`, uppercase `Z` is a pattern letter that means "RFC 822 timezone offset."
For UTC, RFC 822 offset is `+0000` (four digits, no colon, no literal Z!).

### 10.2 Complete Pattern Letter Reference (with examples for UTC)

Using the production timestamp `OffsetDateTime.of(2026, 5, 5, 15, 19, 27, 210000000, ZoneOffset.UTC)`:

| Pattern | Standard | What it produces for UTC | Example output |
|---------|----------|--------------------------|----------------|
| `Z` | RFC 822 | `+0000` (no colon) | `2026-05-05T15:19:27.210+0000` |
| `ZZ` | RFC 822 | `+0000` (same as Z) | `2026-05-05T15:19:27.210+0000` |
| `ZZZ` | RFC 822 | `+0000` (same as Z) | `2026-05-05T15:19:27.210+0000` |
| `X` | ISO 8601 | `Z` (literal) | `2026-05-05T15:19:27.210Z` |
| `XX` | ISO 8601 | `+0000` (no colon) for non-zero, `Z` for zero | `2026-05-05T15:19:27.210Z` |
| `XXX` | ISO 8601 | `Z` (literal) for UTC, `+HH:MM` for others | `2026-05-05T15:19:27.210Z` |
| `x` | ISO 8601 (no Z) | `+00` (always numeric, never literal Z) | `2026-05-05T15:19:27.210+00` |
| `xx` | ISO 8601 (no Z) | `+0000` (always numeric) | `2026-05-05T15:19:27.210+0000` |
| `xxx` | ISO 8601 (no Z) | `+00:00` (always numeric, with colon) | `2026-05-05T15:19:27.210+00:00` |

**Key difference between `X` and `x`**: Uppercase `X` outputs the literal `Z` for zero offset. Lowercase `x` always outputs a numeric offset.

### 10.3 `DateTimeFormatter.ISO_OFFSET_DATE_TIME` — What It Accepts

This is the standard parser used by the old `OffsetDateTimeTypeConverter.unconvert()`:

```java
OffsetDateTime.parse(text, DateTimeFormatter.ISO_OFFSET_DATE_TIME)
```

| Input | Can parse? | Why |
|-------|-----------|-----|
| `"2026-05-05T15:19:27.210Z"` | ✅ Yes | Literal `Z` is valid ISO 8601 UTC |
| `"2026-05-05T15:19:27.210+00:00"` | ✅ Yes | `+HH:MM` with colon is valid ISO 8601 |
| `"2026-05-05T15:19:27.210+05:30"` | ✅ Yes | Any `+HH:MM` is valid |
| `"2026-05-05T15:19:27.210972723Z"` | ✅ Yes | Variable fractional digits + Z |
| `"2026-05-05T15:19:27.210+0000"` | ❌ **No** | `+HHMM` (no colon) is RFC 822, NOT ISO 8601 |
| `"2026-05-05T15:19:27.210+0530"` | ❌ **No** | Same — no colon = not ISO 8601 |

### 10.4 Applying This to Our Production Data

**Production DynamoDB** (written by old SDK v1 `DynamoDBTypeConverter.convert()` using `ISO_DATE_TIME`):
```
"2026-05-05T15:19:27.210972723Z"
```
- `ISO_DATE_TIME` outputs the literal `Z` character for UTC
- This is the ISO 8601 standard representation
- `ISO_OFFSET_DATE_TIME` can parse it ✅

**Production REST API** (written by Jackson with `@JsonFormat(pattern = "SSSZ")`):
```
"2026-05-05T15:19:27.210+0000"
```
- The `Z` pattern letter formats UTC as RFC 822 offset `+0000`
- This is NOT the literal Z character — it's the digits +0000
- `ISO_OFFSET_DATE_TIME` CANNOT parse `+0000` (needs a colon) ❌

**QA DynamoDB** (written by `AuditAttributeConverter` using Jackson with `@JsonFormat(SSSZ)`):
```
"2026-05-06T12:47:47.044+0000"
```
- Same format as REST API — because `AuditAttributeConverter` goes through Jackson
- The `@JsonFormat(SSSZ)` pattern letter `Z` produces `+0000`
- Visibility's old parser (`ISO_OFFSET_DATE_TIME`) CANNOT parse this ❌

### 10.5 The Irony

The pattern `@JsonFormat(pattern = "...Z")` does NOT produce the literal character `Z`.
It produces `+0000`. To produce the literal `Z`, you need `@JsonFormat(pattern = "...XXX")`.

This naming is confusing because in the TIMESTAMP ITSELF, `Z` means UTC.
But in the PATTERN, `Z` means "format as RFC 822 numeric offset."

```
Pattern letter Z  →  produces "+0000"  (NOT the literal Z character!)
Pattern XXX       →  produces "Z"      (the literal Z character for UTC)
```

---

## 11. Summary of All AWS Upgrade Format Issues

The AWS upgrade introduced **three format issues**, all caused by the same architectural mistake:
**Jackson-based converters now respect `@JsonFormat` annotations that SDK v1 ignored for DynamoDB.**

### 11.1 Issue Matrix

| # | Field | What broke | Old SDK v1 DynamoDB format | New Jackson DynamoDB format | Affected consumer |
|---|-------|-----------|----------------------------|------------------------------|-------------------|
| 1 | `MetaData.timestamp` | Booking itself couldn't read old records | `"2020-04-14T10:21:53.78"` (ISO, T-separator) | `"2020-04-14 10:21:53.78"` (space-separator) | Booking + Watermill |
| 2 | `ContainerType.lastModifiedDateUtc` (inside `enrichedAttributes`) | Visibility couldn't read new records | `"2018-02-27T16:59:38.000Z"` (ISO 8601) | `"2018-02-27 16:59:38"` (space-separator) | Visibility |
| 3 | `Audit.createdDateUtc` | Visibility couldn't read new records | `"2026-05-05T15:19:27.210972723Z"` (ISO, literal Z) | `"2026-05-06T12:47:47.044+0000"` (RFC 822 offset) | Visibility |

### 11.2 The Common Root Cause

In ALL three cases:
1. A `@JsonFormat` annotation existed on the model field **before the upgrade**
2. SDK v1's `DynamoDBMapper` / `DynamoDBTypeConverter` **completely ignored** `@JsonFormat` — it used its own serialization engine
3. The upgrade replaced SDK v1 converters with **Jackson-based `AttributeConverter`** implementations
4. Jackson **reads and respects** `@JsonFormat` on fields
5. The DynamoDB stored format **silently changed** because a previously-inert annotation became active

```
        BEFORE UPGRADE                              AFTER UPGRADE

  @JsonFormat("space")                        @JsonFormat("space")
         │                                           │
         │ (IGNORED by SDK v1                        │ (RESPECTED by Jackson
         │  for DynamoDB)                            │  for DynamoDB)
         │                                           │
         ▼                                           ▼
  DynamoDB: ISO format                        DynamoDB: space format  ← CHANGED!
  (via SDK v1 engine)                         (via Jackson engine)
```

### 11.3 How Each Was Fixed

| # | Field | Fix applied | Fix approach |
|---|-------|-------------|--------------|
| 1 | `MetaData.timestamp` | Changed `@JsonFormat` + added `@JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)` | Booking reads both formats; writes ISO (T-separator) |
| 2 | `ContainerType.lastModifiedDateUtc` | Added `@JsonDeserialize(using = FlexibleDateDeserializer.class)` | Booking reads both formats; **still writes space-format** ⚠️ |
| 3 | `Audit.createdDateUtc` | **This is today's issue** | Needs decoupling fix (see Section 6) |

### 11.4 Why Issue 2 (ContainerType) May Still Be a Problem

The fix for Issue 2 only added a flexible **deserializer** — it helps the booking module read old records.
But `EnrichedAttributesConverter.transformFrom()` still uses Jackson with `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")`,
so it still WRITES space-format to DynamoDB. Visibility's SDK v1 Joda time parser can't read space-format.

This means: **any new records written by the upgraded booking module that have `enrichedAttributes.containerTypeList[].lastModifiedDateUtc`
will have space-format in DynamoDB, and visibility will fail when reading them** — the same pattern as the audit issue.

This may not have been reported because:
- Only records where a container type is being actively modified would get rewritten
- Visibility may not query those specific records frequently
- Or it's a latent bug waiting to surface

---

## 12. How We Missed the "Dual Formatting" — SDK v2 Architecture vs Reality

### 12.1 The Correct Understanding

> "AWS SDK v2 Enhanced Client uses its own mappers and converters.
> It doesn't need `@DynamoDBDocument` annotations."

This is **true**. AWS SDK v2 uses:
- `@DynamoDbBean` — marks a class as a DynamoDB-mapped bean (replaces `@DynamoDBTable`)
- `@DynamoDbConvertedBy(MyConverter.class)` — uses custom converter (replaces `@DynamoDBTypeConverted`)
- Built-in converters handle primitives, strings, numbers, enums, lists, maps automatically
- NO `@DynamoDBDocument` needed — nested objects use either `@DynamoDbBean` or a custom converter

### 12.2 The Design Choice That Created the Coupling

The upgrade team chose to implement custom converters using **Jackson ObjectMapper** internally:

```java
// AuditAttributeConverter (SDK v2 converter)
public AttributeValue transformFrom(Audit audit) {
    Map<String, Object> javaMap = OBJECT_MAPPER.convertValue(audit, Map.class);  // ← Jackson!
    return AttributeValue.fromM(LegacyMapConverter.toAttributeValueMap(javaMap));
}
```

This was a deliberate choice to:
1. Produce DynamoDB Maps that match the old `@DynamoDBDocument` structure (for backward compatibility)
2. Leverage Jackson's existing serialization for complex nested objects

### 12.3 Why Jackson Was Chosen (the good reasons)

- The `Audit` class has 8+ fields including nested types
- Writing a manual converter (field by field) is error-prone
- Jackson's `convertValue()` handles the entire object graph in one call
- `LegacyMapConverter` bridges the Jackson Map output to DynamoDB `AttributeValue` types
- The Map structure produced is identical to what SDK v1 `@DynamoDBDocument` produced

### 12.4 What Was Tested (and what wasn't)

**What was verified:**
- ✅ The DynamoDB attribute is type M (Map) — same as before
- ✅ The Map keys match the field names — same as before
- ✅ String fields, boolean fields, enum fields, nested maps — all correct
- ✅ Round-trip: write → read within the booking module — works

**What was NOT verified:**
- ❌ The exact STRING FORMAT of timestamp values inside the Map
- ❌ Whether `@JsonFormat` annotations (previously dormant for DynamoDB) would change string values
- ❌ Whether visibility (SDK v1) could still read records written by the upgrade
- ❌ Cross-module read compatibility testing

### 12.5 The Specific Miss for Audit

The `Audit` class had:
```java
@DynamoDBTypeConverted(converter = OffsetDateTimeTypeConverter.class)  // SDK v1 annotation
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC") // Jackson annotation
private OffsetDateTime createdDateUtc;
```

Before the upgrade:
- `@DynamoDBTypeConverted` → SDK v1 uses `OffsetDateTimeTypeConverter.convert()` → `ISO_DATE_TIME` → writes `Z`
- `@JsonFormat(SSSZ)` → completely ignored for DynamoDB; only used for REST API

After the upgrade:
- `@DynamoDBTypeConverted` removed (SDK v2 doesn't use it)
- `@DynamoDbConvertedBy(AuditAttributeConverter.class)` on `BookingDetail.getAudit()`
- `AuditAttributeConverter` uses Jackson → Jackson sees `@JsonFormat(SSSZ)` → writes `+0000` to DynamoDB

**The `@JsonFormat` that was previously "REST-API-only" suddenly became "DynamoDB-too."**
Nobody noticed because the annotation text `SSSZ` didn't change — it was always there.
What changed was the ENGINE (SDK v1 → Jackson) that now pays attention to it.

### 12.6 The Fundamental Lesson

When replacing a serialization engine, you must verify that **pre-existing annotations** on the model
don't unintentionally change behavior. The new engine (Jackson) respects annotations that the old
engine (SDK v1 DynamoDBMapper) ignored. This creates silent format changes that don't show up as
compilation errors or even as test failures in the module being changed — they only manifest
when a DIFFERENT module (visibility) tries to read the data using the OLD engine.

**Testing principle**: when upgrading a data serialization layer, test cross-module read compatibility
explicitly. Write data with the new code, read it with ALL known consumers (including legacy ones).

---

## 13. Correction: Yesterday's Analysis Got `ISO_DATE_TIME` Output Wrong

### 13.1 What Yesterday's Document Claims

Section 2.1 of `2026-05-05-booking-redshift-audit-field-issue.md` (line 79) states:

| Period | Format written to DynamoDB / outbound | Example |
|--------|--------------------------------------|---------|
| Pre-2026-03-27 (SDK v1) | `+00:00` (ISO_DATE_TIME) | `2026-05-04T06:29:32.691+00:00` |

And at line 23:
```
"2026-05-04T06:29:32.691+00:00"   ← ISO_DATE_TIME for UTC OffsetDateTime
```

**This is WRONG.** `DateTimeFormatter.ISO_DATE_TIME` does NOT produce `+00:00` for UTC. It produces `Z`.

### 13.2 Why `ISO_DATE_TIME` Produces `Z`, Not `+00:00`

Here is the actual Java source for `DateTimeFormatter.ISO_DATE_TIME` (from `java.time.format.DateTimeFormatter`):

```java
ISO_DATE_TIME = new DateTimeFormatterBuilder()
    .append(ISO_LOCAL_DATE_TIME)
    .optionalStart()
    .appendOffsetId()          // ← KEY: this calls ZoneOffset.getId()
    .optionalStart()
    .appendLiteral('[')
    .parseCaseSensitive()
    .appendZoneRegionId()
    .appendLiteral(']')
    .toFormatter(ResolverStyle.STRICT, IsoChronology.INSTANCE);
```

The critical method is `appendOffsetId()`. This appends the result of `ZoneOffset.getId()`.

For `ZoneOffset.UTC`:
```java
ZoneOffset.UTC.getId()  →  "Z"     // the literal character Z
```

Java normalizes ALL zero offsets to the `ZoneOffset.UTC` singleton:
```java
ZoneOffset.of("+00:00")      →  ZoneOffset.UTC  →  getId() = "Z"
ZoneOffset.ofHoursMinutes(0,0)  →  ZoneOffset.UTC  →  getId() = "Z"
ZoneOffset.of("Z")           →  ZoneOffset.UTC  →  getId() = "Z"
```

There is **no way** to construct a zero-offset `ZoneOffset` in Java that returns `"+00:00"` from `getId()`.
Every zero offset normalizes to `ZoneOffset.UTC`, which always returns `"Z"`.

### 13.3 The Old Converter — Proof

The pre-upgrade `OffsetDateTimeTypeConverter.convert()` (from `git show 74f36e7a71fa~1`):

```java
@Override
public String convert(OffsetDateTime offsetDateTime) {
    return offsetDateTime != null ? offsetDateTime.format(DateTimeFormatter.ISO_DATE_TIME) : null;
}
```

For a UTC `OffsetDateTime` (e.g., `OffsetDateTime.now(ZoneOffset.UTC)`), this produces:

```
2026-05-05T15:19:27.210972723Z
                              ^
                              Z — the literal character, NOT +00:00
```

**Production confirms this.** The user provided the actual DynamoDB value from production:
```
"2026-05-05T15:19:27.210972723Z"
```

This matches `ISO_DATE_TIME` output: literal `Z`, nanosecond precision (9 fractional digits).

### 13.4 How To Get `+00:00` (If You Wanted To)

To get `+00:00` instead of `Z`, you would need a pattern with **lowercase `xxx`**:

```java
DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSxxx")
// Lowercase xxx: always numeric offset, never Z
// Output: 2026-05-05T15:19:27.210+00:00
```

Or equivalently:
```java
DateTimeFormatter.ISO_OFFSET_DATE_TIME  // uses appendOffsetId() → Z for UTC
DateTimeFormatter.ISO_DATE_TIME         // uses appendOffsetId() → Z for UTC
// Neither of these produces +00:00
```

### 13.5 Why the Confusion Likely Arose

The previous analysis may have confused:

1. **`ISO_DATE_TIME`** → uses `appendOffsetId()` → outputs `Z` for UTC
2. **`ofPattern("xxx")`** → lowercase x = always numeric → outputs `+00:00` for UTC

Or the analyst may have read Java's `DateTimeFormatter` Javadoc examples like
`"2011-12-03T10:15:30+01:00"` (non-UTC) and assumed that for UTC the output would follow
the same `+HH:MM` pattern as `+00:00`. In reality, the `appendOffsetId()` method special-cases
UTC to output `Z` instead of `+00:00`.

### 13.6 The Corrected Format Timeline

The format timeline from yesterday's doc (Section 2.4, line 77-81) should be:

| Period | DynamoDB format | Pattern used | Example |
|--------|----------------|--------------|---------|
| Pre-2026-03-27 (SDK v1) | `Z` literal (ISO 8601 UTC) | `ISO_DATE_TIME` via `convert()` | `2026-05-04T06:29:32.691Z` |
| 2026-03-27 → 2026-04-16 (SDK v2 initial) | `+0000` (RFC 822) | `@JsonFormat(SSSZ)` via Jackson | `2026-05-04T06:29:32.691+0000` |
| 2026-04-17 → 2026-05-04 (data-format fix) | `Z` literal (ISO 8601 UTC) | `@JsonFormat(SSSXXX)` via Jackson | `2026-05-04T06:29:32.691Z` |
| 2026-05-05 → present (redshift revert) | `+0000` (RFC 822) | `@JsonFormat(SSSZ)` via Jackson | `2026-05-04T06:29:32.691+0000` |

**Key correction**: The pre-upgrade format was `Z` (NOT `+00:00`). This means:
- The pre-upgrade format and the data-format-fix format were **identical** (`Z`)
- The data-format fix (`SSSXXX`) correctly restored the pre-upgrade behavior
- Yesterday's analysis incorrectly classified `+00:00` as a third distinct format

### 13.7 Impact on Our Fix Design

This correction actually **strengthens** our fix design:

- We want DynamoDB to store `Z` (matching production / pre-upgrade behavior)
- The old converter used `ISO_DATE_TIME` → produces `Z` ✅
- Our fix uses `ISO_DATE_TIME` in `DYNAMO_OBJECT_MAPPER` → produces `Z` ✅
- Production has `Z`, our fix writes `Z` — **exact match**

If the previous analysis were correct (`+00:00`), we would have needed to choose between
`Z` and `+00:00` for the DynamoDB path. Since the previous analysis was wrong and production
actually uses `Z`, our fix matches production exactly.

### 13.8 Nanosecond Precision — Another Difference

The previous analysis also used 3-digit fractional seconds in its example:
```
"2026-05-04T06:29:32.691+00:00"   ← 3 fractional digits (milliseconds)
```

But `ISO_DATE_TIME` preserves ALL available fractional digits:
```
"2026-05-05T15:19:27.210972723Z"  ← 9 fractional digits (nanoseconds)
```

This means:
- `ISO_DATE_TIME` → outputs 0-9 fractional digits (as many as the source has)
- `@JsonFormat(pattern = "...SSS...")` → always outputs exactly 3 fractional digits (truncates to millis)

Our fix using `ISO_DATE_TIME` in the DynamoDB serializer will preserve nanosecond precision,
matching production behavior. The `@JsonFormat(SSSZ)` for REST API will continue to truncate
to milliseconds, which is what ETL expects.

| Path | Formatter | Fractional precision | Example |
|------|-----------|---------------------|---------|
| DynamoDB (our fix) | `ISO_DATE_TIME` | Full (0-9 digits) | `.210972723` |
| REST API (unchanged) | `@JsonFormat(SSS)` | 3 digits (millis) | `.210` |
| Production DynamoDB | Old `convert()` with `ISO_DATE_TIME` | Full (0-9 digits) | `.210972723` |

---

## 14. References

| Reference | Location |
|-----------|----------|
| Redshift ETL analysis | `booking/docs/2026-05-05-booking-redshift-audit-field-issue.md` |
| Data-format fix docs | `booking/docs/2026-04-17-booking-dataformat-issue-fixes.md` |
| Visibility integration issue (enrichedAttributes) | `booking/docs/visibility-integration-issue-04212026.md` |
| Yesterday's revert commit | `c12750e13e47` — "ION-14382 redshift audit ts restore per ticket ION-15691" |
| Old `OffsetDateTimeTypeConverter` (pre-upgrade) | `git show 74f36e7a71fa~1:booking/src/main/java/.../OffsetDateTimeTypeConverter.java` |
| Old `Audit.java` (pre-upgrade) | `git show 74f36e7a71fa~1:booking/src/main/java/.../Audit.java` |
| Old `BookingDetail.java` (pre-upgrade) | `git show 74f36e7a71fa~1:booking/src/main/java/.../BookingDetail.java` |
| `BookingDetailVisibility.java` | `visibility/visibility-commons/src/main/java/.../BookingDetailVisibility.java` |
| `AuditAttributeConverter.java` | `booking/src/main/java/.../converter/AuditAttributeConverter.java` |
| `EnrichedAttributesConverter.java` | `booking/src/main/java/.../converter/EnrichedAttributesConverter.java` |
| Visibility `BookingDao.java` | `visibility/visibility-commons/src/main/java/.../BookingDao.java` |
