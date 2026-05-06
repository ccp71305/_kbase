# Visibility Audit Unconvert Issue — Critical Review & Consolidated Analysis

**Date**: 2026-05-06  
**Author**: Claude Sonnet 4.6 (critical review of `2026-05-06-visibility-audit-unconvert-issue-copilot.md`)  
**Cross-references**:
- `booking/docs/2026-05-06-visibility-audit-unconvert-issue-copilot.md` (reviewed document)
- `booking/docs/2026-05-05-booking-redshift-audit-field-issue.md`
- `booking/docs/2026-04-17-booking-dataformat-issue-fixes.md`
- `booking/docs/visibility-integration-issue-04212026.md`

---

## Executive Summary

The copilot document (`2026-05-06-…-copilot.md`) is **technically accurate in its core diagnosis** — the visibility crash is real, the root cause is correctly identified, and the proposed fix is architecturally sound. However it contains **three significant discrepancies** inherited from the prior day's analysis that need correction, and the proposed `DYNAMO_OBJECT_MAPPER` fix is **not yet implemented** in the current code. This document consolidates the full chain of events, annotates all three format fields with production data proof, and provides a validated implementation path.

---

## Part 1: The Chain of Events — How Three Fixes Broke Each Other

The core story is a sequence of well-intentioned fixes that each addressed one consumer's needs while inadvertently breaking another's, because the AWS SDK v2 upgrade silently **coupled** two serialization paths that were previously independent.

### 1.1 The Three Consumers and What Format They Need

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONSUMER FORMAT REQUIREMENTS                          │
│                                                                              │
│  ┌──────────────┐  ┌──────────────────────────────────────────────────────┐  │
│  │  VISIBILITY  │  │  Reads DynamoDB DIRECTLY via SDK v1 DynamoDBMapper   │  │
│  │  (SDK v1)    │  │  Uses OffsetDateTimeTypeConverter.unconvert()         │  │
│  │              │  │  Needs: "Z" or "+00:00" (ISO 8601)                   │  │
│  │              │  │  Cannot parse: "+0000" (RFC 822, no colon)           │  │
│  └──────────────┘  └──────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────────────────────────────────────────────┐  │
│  │  REDSHIFT    │  │  Reads REST API / outbound pipeline output            │  │
│  │  ETL (Glue)  │  │  Uses unix_timestamp(col, "yyyy-MM-dd'T'HH:mm:ss.SSSZ")│  │
│  │              │  │  Needs: "+0000" (RFC 822, Z pattern letter)           │  │
│  │              │  │  Cannot parse: "Z" literal (ISO 8601)                │  │
│  └──────────────┘  └──────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────────────────────────────────────────────┐  │
│  │  BOOKING     │  │  Reads DynamoDB via SDK v2 AuditAttributeConverter   │  │
│  │  (SDK v2)    │  │  Uses OffsetDateTimeTypeConverter.unconvert()         │  │
│  │              │  │  Handles: "Z", "+0000", "+00:00", variable decimals  │  │
│  └──────────────┘  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**The fundamental constraint**: No single `@JsonFormat` pattern can simultaneously produce `Z` (for visibility) and `+0000` (for ETL). This is the root of every problem in this chain.

---

### 1.2 Complete Timeline With Actual Data at Each Stage

#### STAGE 0 — Pre-Upgrade Production (SDK v1, still running in production today)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 0: PRE-UPGRADE  (SDK v1)  — PRODUCTION TODAY                         ║
║  Audit.java: @JsonFormat(pattern="SSSZ")  ← always existed, SDK v1 IGNORED  ║
╚══════════════════════════════════════════════════════════════════════════════╝

                            Java OffsetDateTime
                                    │
              ┌─────────────────────┴─────────────────────┐
              │                                           │
              ▼                                           ▼
    ┌─────────────────────┐                   ┌────────────────────────┐
    │  DynamoDB WRITE     │                   │  REST API / Jackson    │
    │  (SDK v1 engine)    │                   │  (Dropwizard JAX-RS)   │
    │                     │                   │                        │
    │  OffsetDateTimeType │                   │  @JsonFormat("SSSZ")   │
    │  Converter.convert()│                   │  pattern Z = RFC 822   │
    │  ISO_DATE_TIME      │                   │  UTC → +0000           │
    │  UTC → literal Z    │                   │  SSS → millis only     │
    └──────────┬──────────┘                   └───────────┬────────────┘
               │                                          │
               ▼                                          ▼
    ┌─────────────────────────────┐         ┌────────────────────────────────┐
    │  DynamoDB stored value:     │         │  REST API response:             │
    │  "2026-05-05T15:19:27       │         │  "2026-05-05T15:19:27          │
    │           .210972723Z"      │         │           .210+0000"           │
    │            ─────────────    │         │            ───────────         │
    │            9 digits         │         │            3 digits            │
    │            literal Z        │         │            +0000 RFC 822       │
    └─────────────────────────────┘         └────────────────────────────────┘

 ★ PROOF: Production DynamoDB audit (actual data from booking 2105729968):
   DynamoDB:   "2026-05-05T15:19:27.210972723Z"    ← 9 fractional digits, Z
   REST API:   "2026-05-05T15:19:27.210+0000"      ← 3 fractional digits, +0000

 VISIBILITY reads DynamoDB ✅  (ISO_OFFSET_DATE_TIME parses "...Z")
 ETL reads REST API      ✅  (unix_timestamp "SSSZ" parses "+0000")

 KEY: @JsonFormat was a REST-API-ONLY annotation. SDK v1 DynamoDBMapper ignored it.
      The two paths were INDEPENDENT. Changing one did NOT affect the other.
```

---

#### STAGE 1 — AWS SDK v2 Upgrade Initial (2026-03-27, commit `74f36e7a71`)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 1: AWS SDK v2 UPGRADE  (2026-03-27)                                   ║
║  Audit.java: @JsonFormat(pattern="SSSZ")  ← SAME annotation, NEW engine      ║
╚══════════════════════════════════════════════════════════════════════════════╝

                            Java OffsetDateTime
                                    │
              ┌─────────────────────┴─────────────────────┐
              │                                           │
              ▼                                           ▼
    ┌──────────────────────────────────┐       ┌────────────────────────┐
    │  DynamoDB WRITE                  │       │  REST API / Jackson    │
    │  AuditAttributeConverter         │       │                        │
    │  .transformFrom()                │       │  @JsonFormat("SSSZ")   │
    │                                  │       │  ← same annotation     │
    │  OBJECT_MAPPER.convertValue()    │       │                        │
    │  Jackson now READS @JsonFormat   │       │                        │
    │  "SSSZ" → +0000 for UTC         │       │  "SSSZ" → +0000        │
    └──────────────┬───────────────────┘       └───────────┬────────────┘
                   │                                       │
                   ▼                                       ▼
    ┌──────────────────────────────┐       ┌──────────────────────────────────┐
    │  DynamoDB stored value:      │       │  REST API response:               │
    │  "2026-05-04T06:29:32        │       │  "2026-05-04T06:29:32            │
    │           .691+0000"         │       │           .691+0000"             │
    │  ◄──── CHANGED! ────────     │       │  ◄──── Same as before ────       │
    │  Was: ...Z (nanoseconds)     │       │                                  │
    │  Now: ...+0000 (millis)      │       │                                  │
    └──────────────────────────────┘       └──────────────────────────────────┘

 COUPLING INTRODUCED: DynamoDB path and REST API path now share @JsonFormat.
                      Changing @JsonFormat changes BOTH outputs simultaneously.

 VISIBILITY reads DynamoDB ❌  (ISO_OFFSET_DATE_TIME cannot parse "+0000")
 ETL reads REST API        ✅  (unchanged — +0000 still works)
 BOOKING reads DynamoDB    ❌  (old records have "Z" with 6 digits — fails SSS)

 NEW PROBLEM: Booking's OWN reads broke — legacy records stored as
              "2020-11-30T04:23:30.153845Z" (6 fractional digits + Z)
              but @JsonFormat(SSSZ) expects exactly 3 digits and +0000 suffix.
```

---

#### STAGE 2 — Data Format Fix (2026-04-17, commit `ee29760491`) — Fixed booking reads, BROKE ETL

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 2: DATA FORMAT FIX  (2026-04-17)  ION-14382                           ║
║  Audit.java: @JsonFormat changed "SSSZ" → "SSSXXX"                          ║
║  + @JsonDeserialize(using=OffsetDateTimeTypeConverter.class) added           ║
╚══════════════════════════════════════════════════════════════════════════════╝

 WHY: "@JsonFormat(SSSZ)" could not parse:
      "2020-11-30T04:23:30.153845Z" — 6 fractional digits (fails SSS)
                                      + literal Z  (fails Z pattern)
      → "could not be parsed at index 23"
      → QA booking REST API returned HTTP 500 for any booking touched since 2018

 FIX APPLIED:
   @JsonFormat pattern: "SSSZ" → "SSSXXX"
   Effect: Jackson now writes "Z" for UTC (XXX pattern = ISO 8601)
   Also added: @JsonDeserialize(OffsetDateTimeTypeConverter.class)
   Effect: Deserialization now uses robust unconvert() — handles Z, +0000, +00:00,
           any fractional precision. @JsonFormat no longer used for READING.

                            Java OffsetDateTime
                                    │
              ┌─────────────────────┴─────────────────────┐
              │                                           │
              ▼                                           ▼
    ┌──────────────────────────────────┐       ┌────────────────────────────┐
    │  DynamoDB WRITE (coupled)        │       │  REST API / Jackson        │
    │  OBJECT_MAPPER.convertValue()    │       │                            │
    │  @JsonFormat("SSSXXX")          │       │  @JsonFormat("SSSXXX")    │
    │  XXX → literal Z for UTC        │       │  XXX → literal Z for UTC   │
    └──────────────┬───────────────────┘       └───────────┬────────────────┘
                   │                                       │
                   ▼                                       ▼
    ┌──────────────────────────────┐       ┌──────────────────────────────────┐
    │  DynamoDB stored value:      │       │  REST API response:               │
    │  "2026-05-04T06:29:32.691Z" │       │  "2026-05-04T06:29:32.691Z"     │
    │  ◄──── CHANGED again! ───   │       │  ◄──── CHANGED from production   │
    │  Was: ...+0000 (stage 1)    │       │  Prod was: ...+0000              │
    │  Now: ...Z (3 millis digits)│       │  Now:  ...Z                      │
    └──────────────────────────────┘       └──────────────────────────────────┘

 VISIBILITY reads DynamoDB ✅  (ISO_OFFSET_DATE_TIME can parse "...Z")
 ETL reads REST API        ❌  BROKEN! unix_timestamp("SSSZ") cannot parse "Z" literal
                               → version_date, partition_date, source_created_date = NULL
                               → BK-Detail Redshift report: broken for all post-2026-04-17 bookings
 BOOKING reads DynamoDB    ✅  (OffsetDateTimeTypeConverter handles all variants)
```

---

#### STAGE 3 — Redshift ETL Revert (2026-05-05, commit `c12750e13e47`) — Fixed ETL, BROKE Visibility

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  STAGE 3: REDSHIFT REVERT  (2026-05-05)  ION-15691                           ║
║  Audit.java: @JsonFormat changed BACK "SSSXXX" → "SSSZ"                     ║
║  CURRENT STATE IN CODE (verified in Audit.java line 32, 38)                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

 WHY: ETL Glue job unix_timestamp("...SSSZ") cannot parse literal "Z" suffix.
      Decision: revert @JsonFormat faster than ETL QA cycle before release.
      Reasoning: @JsonDeserialize keeps robust reading regardless of @JsonFormat.

 UNINTENDED CONSEQUENCE (not in prior analysis):
      Visibility reads DynamoDB directly with OLD SDK v1 OffsetDateTimeTypeConverter
      from booking:2.1.8.M. That converter has NO +0000 normalization.

                            Java OffsetDateTime
                                    │
              ┌─────────────────────┴─────────────────────┐
              │                                           │
              ▼                                           ▼
    ┌──────────────────────────────────┐       ┌────────────────────────────┐
    │  DynamoDB WRITE (still coupled)  │       │  REST API / Jackson        │
    │  OBJECT_MAPPER.convertValue()    │       │                            │
    │  @JsonFormat("SSSZ")            │       │  @JsonFormat("SSSZ")       │
    │  Z pattern → +0000 RFC 822      │       │  Z pattern → +0000         │
    └──────────────┬───────────────────┘       └───────────┬────────────────┘
                   │                                       │
                   ▼                                       ▼
    ┌──────────────────────────────┐       ┌──────────────────────────────────┐
    │  DynamoDB stored value:      │       │  REST API response:               │
    │  "2026-05-06T12:47:47        │       │  "2026-05-06T12:47:47            │
    │           .044+0000"         │       │           .044+0000"             │
    │  ◄──── This broke Visibility │       │  ◄──── ETL can parse this ✅    │
    └──────────────────────────────┘       └──────────────────────────────────┘

 ★ PROOF: Actual QA error (2026-05-06 12:48:39):
   DynamoDB had: "2026-05-06T12:47:47.044+0000"
   Visibility tried: ISO_OFFSET_DATE_TIME.parse("2026-05-06T12:47:47.044+0000") → FAIL
   Fallback tried:   LocalDate.parse("2026-05-06T12:47:47.044+0000") → FAIL at index 10

   Error: DynamoDBMappingException: BookingDetailVisibility[audit]; could not unconvert
          Audit[createdDateUtc]; could not unconvert
          DateTimeParseException: Text '2026-05-06T12:47:47.044+0000'
                                  could not be parsed, unparsed text found at index 10

 VISIBILITY reads DynamoDB ❌  BROKEN! Can't parse "+0000"
 ETL reads REST API        ✅  unix_timestamp("SSSZ") parses "+0000"
 BOOKING reads DynamoDB    ✅  OffsetDateTimeTypeConverter normalizes "+0000" → "+00:00"
```

---

### 1.3 The Three-Fix Cycle Summarized

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║               COMPLETE FORMAT HISTORY — ALL THREE FIELDS                      ║
╠═══════════════════╦═════════════════════╦═══════════════╦════════════════════╣
║   Period          ║  DynamoDB Audit     ║  REST API     ║  Status            ║
║                   ║  Format             ║  Audit Format ║                    ║
╠═══════════════════╬═════════════════════╬═══════════════╬════════════════════╣
║  Pre-2026-03-27   ║  ...210972723Z      ║  ...210+0000  ║  ✅ Both work      ║
║  (SDK v1, prod)   ║  9 digits, Z        ║  3 digits,+0K ║  Decoupled paths   ║
╠═══════════════════╬═════════════════════╬═══════════════╬════════════════════╣
║  2026-03-27 →     ║  ...691+0000        ║  ...691+0000  ║  ❌ Vis broken     ║
║  2026-04-16       ║  3 digits, +0000    ║  3 digits,+0K ║  ETL ok            ║
║  (SDK v2 initial) ║  Coupled via SSSZ   ║  SSSZ        ║  Booking reads ❌  ║
╠═══════════════════╬═════════════════════╬═══════════════╬════════════════════╣
║  2026-04-17 →     ║  ...691Z            ║  ...691Z      ║  ✅ Vis ok         ║
║  2026-05-04       ║  3 digits, Z        ║  3 digits, Z  ║  ❌ ETL broken     ║
║  (data fmt fix)   ║  Coupled via SSSXXX ║  SSSXXX      ║  Booking reads ✅  ║
╠═══════════════════╬═════════════════════╬═══════════════╬════════════════════╣
║  2026-05-05 →     ║  ...044+0000        ║  ...044+0000  ║  ❌ Vis BROKEN     ║
║  present          ║  3 digits, +0000    ║  3 digits,+0K ║  ✅ ETL ok         ║
║  (revert, CURRENT)║  Coupled via SSSZ   ║  SSSZ        ║  Booking reads ✅  ║
╚═══════════════════╩═════════════════════╩═══════════════╩════════════════════╝

Root cause of the cycle: DynamoDB and REST API share @JsonFormat → changing one
changes both. There is no single format that satisfies ALL consumers simultaneously.
```

---

## Part 2: The Three-Field Format Comparison

The problem manifests differently across three fields. Here is the complete picture with actual production values.

### 2.1 `Audit.createdDateUtc` (today's issue)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FIELD: Audit.createdDateUtc                                                 │
│                                                                              │
│  Class: booking/dynamodb/Audit.java (line 32)                               │
│  Current annotations:                                                        │
│    @JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")   │
│    @JsonDeserialize(using = OffsetDateTimeTypeConverter.class)               │
│                                                                              │
│  PRODUCTION (SDK v1 — pre-upgrade):                                          │
│    DynamoDB:   "2026-05-05T15:19:27.210972723Z"   ← 9 digits, literal Z     │
│    REST API:   "2026-05-05T15:19:27.210+0000"     ← 3 digits, RFC 822       │
│                                                                              │
│  QA CURRENT (post-revert, SDK v2):                                           │
│    DynamoDB:   "2026-05-06T12:47:47.044+0000"     ← 3 digits, RFC 822       │
│    REST API:   "2026-05-06T12:47:47.044+0000"     ← same (coupled)          │
│                                                                              │
│  WHO IS BROKEN:                                                              │
│    Visibility (booking:2.1.8.M OffsetDateTimeTypeConverter) ← TODAY'S BUG   │
│                                                                              │
│  WHO IS OK:                                                                  │
│    Booking SDK v2 AuditAttributeConverter (normalizes +0000→+00:00) ✅       │
│    ETL (expects +0000 via unix_timestamp "SSSZ") ✅                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 `MetaData.timestamp` (previously fixed issue)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FIELD: MetaData.timestamp                                                   │
│                                                                              │
│  Class: booking/util/MetaData.java                                          │
│  Current annotations:                                                        │
│    @JsonFormat(shape = JsonFormat.Shape.STRING)  ← ISO T-separator          │
│    @JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)        │
│                                                                              │
│  PRODUCTION (SDK v1):                                                        │
│    DynamoDB:   "2020-04-14T10:21:53.78"     ← ISO, T separator              │
│    LocalDateTime — no timezone component                                     │
│                                                                              │
│  QA (post data-format fix):                                                  │
│    DynamoDB:   "2020-04-14T10:21:53.78"     ← ISO, T separator (restored)   │
│                                                                              │
│  STATUS: ✅ FIXED — ISO T-separator restored for DynamoDB write              │
│  The @JsonDeserialize handles both T-separator and space-separator (legacy)  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 `EnrichedAttributes.containerTypeList[].lastModifiedDateUtc` (prior issue, latent risk)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FIELD: ContainerType.lastModifiedDateUtc (inside enrichedAttributes)        │
│                                                                              │
│  Class: booking/.../referencedata/model/ContainerType.java                  │
│  Current annotations:                                                        │
│    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")   ← SPACE │
│    @JsonDeserialize(using = FlexibleDateDeserializer.class)                  │
│                                                                              │
│  PRODUCTION (SDK v1 — pre-upgrade):                                          │
│    DynamoDB:   "2018-02-27T16:59:38.000Z"   ← ISO, T separator (SDK v1)    │
│    REST API:   "2018-02-27 16:59:38"        ← Space format (@JsonFormat)    │
│                                                                              │
│  QA CURRENT (post data-format fix):                                          │
│    DynamoDB:   "2018-02-27 16:59:38"        ← SPACE! EnrichedAttributesConverter│
│                                               uses Jackson → respects @JsonFormat│
│    REST API:   "2018-02-27 16:59:38"        ← same                          │
│                                                                              │
│  STATUS: ⚠️ LATENT BUG — Visibility STILL cannot read new records with       │
│            containerTypeList dates, because:                                  │
│            - EnrichedAttributesConverter writes space-format to DynamoDB     │
│            - Visibility's Joda time parser needs T-separator (ISO 8601)      │
│            - Fix was only applied to READING (FlexibleDateDeserializer)      │
│            - The WRITE path (EnrichedAttributesConverter) was never fixed    │
│                                                                              │
│  COPILOT DOC NOTES THIS (Section 11.4) ✅ — but marks it as "may not be    │
│  reported." It IS a real ongoing bug for records written post-upgrade.       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 3: Why Visibility DynamoDBMapper DOES Process `audit`

The prior analysis (2026-05-05, Section 15.4) incorrectly concluded visibility is unaffected. Here is the precise code path that proves it wrong.

### 3.1 Visibility's Read Path Through `audit`

```
visibility-matcher calls:
  BookingDao.getBookingDetail(containerEventId)
      │
      ▼
  DynamoDBMapper.query(BookingDetailVisibility.class, queryExpression)
      │
      ▼
  SDK v1 reads DynamoDB item (a Map of attribute name → AttributeValue)
  Item keys: "bookingId", "state", "audit", "enrichedAttributes", "metaData", ...
      │
      ├── "audit" attribute found → type M (nested Map)
      │       │
      │       ▼
      │   BookingDetail field: @DynamoDBAttribute private Audit audit
      │   Audit class has:     @DynamoDBDocument   ← tells mapper to recurse
      │       │
      │       ▼
      │   Inside Audit Map: "createdDateUtc" → S("2026-05-06T12:47:47.044+0000")
      │   Audit.createdDateUtc has: @DynamoDBTypeConverted(OffsetDateTimeTypeConverter)
      │       │
      │       ▼
      │   OffsetDateTimeTypeConverter.unconvert("2026-05-06T12:47:47.044+0000")
      │       │
      │       ├─ STEP 1: ISO_OFFSET_DATE_TIME.parse("...+0000") → FAIL ❌
      │       │          "+0000" needs colon: "+00:00" for ISO 8601
      │       │
      │       └─ STEP 2 (FALLBACK): LocalDate.parse("...+0000", ISO_DATE) → FAIL ❌
      │                             ISO_DATE reads "2026-05-06" (10 chars)
      │                             then finds "T" at index 10 → exception!
      │
      ▼
  DynamoDBMappingException: BookingDetailVisibility[audit]; could not unconvert
  → com.inttra.mercury.visibility.matcher.processor.MatchingProcessor CRASH
```

### 3.2 Why the Old Converter Cannot Handle `+0000`

The `OffsetDateTimeTypeConverter` in `booking:2.1.8.M` (the artifact visibility uses) is **NOT** the same as the current workspace version. The key difference:

```
WORKSPACE VERSION (current, in booking module):          booking:2.1.8.M VERSION (visibility):
─────────────────────────────────────────────           ──────────────────────────────────────
public OffsetDateTime unconvert(String date) {          public OffsetDateTime unconvert(String date) {
    if (date == null) return null;                          try {
    try {                                                       return OffsetDateTime.parse(date,
        return OffsetDateTime.parse(date,                           DateTimeFormatter.ISO_OFFSET_DATE_TIME);
            DateTimeFormatter.ISO_OFFSET_DATE_TIME);        } catch (Exception e) {
    } catch (Exception e) {                                     // FALLBACK: date-only (no normalization!)
        try {                                                   return OffsetDateTime.of(
            // ★ THIS STEP MISSING FROM 2.1.8.M ★               LocalDate.parse(date,
            String normalized = date.replaceAll(                     DateTimeFormatter.ISO_DATE),  ← line 39
                "([+-])(\\d{2})(\\d{2})$", "$1$2:$3");         LocalTime.MIDNIGHT, ZoneOffset.UTC);
            if (!normalized.equals(date)) {                 }
                return OffsetDateTime.parse(normalized,     }
                    DateTimeFormatter.ISO_OFFSET_DATE_TIME);
            }
        } catch (Exception ignored) {}
        return OffsetDateTime.of(
            LocalDate.parse(date, DateTimeFormatter.ISO_DATE),
            LocalTime.MIDNIGHT, ZoneOffset.UTC);
    }
}

The normalization step (+0000 → +00:00) was added DURING the SDK v2
upgrade. booking:2.1.8.M was published BEFORE this change.
```

---

## Part 4: Discrepancies in the Copilot Document

### Discrepancy 1 — Pre-Upgrade DynamoDB Format (Critical)

**Location**: `2026-05-05-booking-redshift-audit-field-issue.md`, Section 2.1 (line 23)

```
COPILOT CLAIMS:
  Pre-2026-03-27 (SDK v1) DynamoDB format: "2026-05-04T06:29:32.691+00:00"
  (ISO_DATE_TIME produces "+00:00")

ACTUAL FACT:
  Pre-2026-03-27 DynamoDB format: "2026-05-05T15:19:27.210972723Z"
  (ISO_DATE_TIME produces literal "Z" for UTC — NOT "+00:00")

WHY: DateTimeFormatter.ISO_DATE_TIME uses appendOffsetId() internally.
     ZoneOffset.UTC.getId() returns "Z" — not "+00:00".
     Java normalizes all zero offsets to ZoneOffset.UTC singleton.
     There is no zero-offset ZoneOffset that returns "+00:00" from getId().

PROOF: Actual production DynamoDB value provided (booking 2105729968):
       "2026-05-05T15:19:27.210972723Z" ← literal Z, 9 fractional digits

IMPACT: The copilot document correctly fixes this in its own Sections 13 and 17,
        and in the 2026-05-05 document Section 17. But Section 2.1 was never
        updated, creating internal inconsistency within that document.
        ETL gap analysis referencing "+00:00" records is invalidated
        (those records don't exist — they were always Z format).
```

### Discrepancy 2 — "Visibility Does Not Touch Audit" (Critical)

**Location**: `2026-05-05-booking-redshift-audit-field-issue.md`, Section 15.4

```
COPILOT CLAIMS:
  "Visibility's SDK v1 DynamoDBMapper does not touch the audit attribute
   at all. No impact."

ACTUAL FACT:
  Visibility's DynamoDBMapper DOES process the audit attribute.

WHY:
  @DynamoDBAttribute on BookingDetail.audit tells DynamoDBMapper: map this field.
  @DynamoDBDocument on Audit class tells DynamoDBMapper: recurse into this Map.
  @DynamoDBTypeConverted on Audit.createdDateUtc tells DynamoDBMapper: use converter.
  There is no mechanism to selectively skip annotated fields during query mapping.

CONFUSION: The analyst correctly noted audit ≠ enrichedAttributes (different fields).
           But then incorrectly generalized: "not in enrichedAttributes" → "not read at all".
           These are two entirely different claims.

PATH A: enrichedAttributes → EnrichedAttributesConverter (Jackson-based) → prev. issue
PATH B: audit → @DynamoDBDocument unconversion → OffsetDateTimeTypeConverter → TODAY'S ISSUE
```

### Discrepancy 3 — Completeness of the Revert Fix (Moderate)

**Location**: `2026-05-05-booking-redshift-audit-field-issue.md`, Section 11 (Recommended Fix)

```
COPILOT CLAIMS:
  "Revert @JsonFormat on Audit.java from SSSXXX to SSSZ"
  This is the complete fix. "Visibility: Not affected — confirmed."

ACTUAL FACT:
  This revert WAS ALREADY DONE (commit c12750e13e47, 2026-05-05).
  The revert ITSELF caused today's visibility crash.
  The revert is not a complete fix — it traded ETL compatibility for
  visibility breakage.

CORRECT FRAMING:
  The revert was the right decision for ETL given no time for ETL QA.
  But Section 11 was written WITHOUT knowledge that the revert would
  also break visibility. Section 15.4's incorrect "no impact" claim
  was the source of this blind spot.
```

---

## Part 5: Proposed Solution — Validation

The `2026-05-06-visibility-audit-unconvert-issue-copilot.md` document proposes decoupling the two paths by using a `DYNAMO_OBJECT_MAPPER` in `AuditAttributeConverter`. This is the correct architectural approach.

### 5.1 Current Code State (Verified)

```java
// AuditAttributeConverter.java (CURRENT — actual file)
public final class AuditAttributeConverter implements AttributeConverter<Audit> {

    private static final ObjectMapper OBJECT_MAPPER = createObjectMapper();
    //                                ^^^^^^^^^^^^
    //                   SINGLE mapper — used for both read AND write
    //                   Reads @JsonFormat from Audit.java
    //                   @JsonFormat(SSSZ) → +0000 for UTC

    @Override
    public AttributeValue transformFrom(Audit audit) {
        Map<String, Object> javaMap = OBJECT_MAPPER.convertValue(audit, Map.class);
        //                            ^^^^^^^^^^^^ writes "+0000" because @JsonFormat(SSSZ)
        return AttributeValue.fromM(LegacyMapConverter.toAttributeValueMap(javaMap));
    }
```

```java
// Audit.java (CURRENT — actual file, lines 32-34, 38-40)
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")   // ← SSSZ (reverted)
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime createdDateUtc;

@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone = "UTC")   // ← SSSZ (reverted)
@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)
private OffsetDateTime lastModifiedDateUtc;
```

The proposed `DYNAMO_OBJECT_MAPPER` does **not exist** in the current codebase. The fix must be implemented.

### 5.2 Why the Fix Is Correct

```
                    PROPOSED FIX — DECOUPLED PATHS (restores pre-upgrade architecture)

                                   Java Audit object
                                          │
                     ┌────────────────────┴────────────────────┐
                     │                                         │
                     ▼                                         ▼
          ┌──────────────────────────────┐         ┌──────────────────────────────┐
          │  DynamoDB WRITE              │         │  REST API (JAX-RS Jackson)    │
          │  AuditAttributeConverter     │         │                              │
          │  .transformFrom()            │         │  Uses shared ObjectMapper    │
          │                              │         │  Reads @JsonFormat("SSSZ")   │
          │  DYNAMO_OBJECT_MAPPER        │         │                              │
          │  Custom serializer for       │         │                              │
          │  OffsetDateTime:             │         │                              │
          │  ISO_DATE_TIME → "Z"         │         │  @JsonFormat("SSSZ") → +0000 │
          └──────────────┬───────────────┘         └───────────────┬──────────────┘
                         │                                         │
                         ▼                                         ▼
             "...210972723Z"  (Z, full precision)     "...210+0000"  (RFC 822, 3 digits)
              ─────────────────────                    ────────────────────────────────
              Matches production DynamoDB ✅            Matches production REST API ✅
              Visibility can parse ✅                   ETL can parse ✅
```

### 5.3 Validated Implementation

The key is registering a custom `OffsetDateTime` **serializer** in the DynamoDB-specific mapper that uses `ISO_DATE_TIME` (same as the old `DynamoDBTypeConverter.convert()`), overriding whatever `@JsonFormat` says.

```java
// AuditAttributeConverter.java — PROPOSED CHANGES

public final class AuditAttributeConverter implements AttributeConverter<Audit> {

    // Shared mapper for READING — handles all formats via OffsetDateTimeTypeConverter
    private static final ObjectMapper OBJECT_MAPPER = createObjectMapper();

    // DynamoDB-specific mapper for WRITING — uses ISO_DATE_TIME regardless of @JsonFormat
    private static final ObjectMapper DYNAMO_OBJECT_MAPPER = createDynamoObjectMapper();

    private static ObjectMapper createObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        JavaTimeModule javaTimeModule = new JavaTimeModule();
        javaTimeModule.addDeserializer(OffsetDateTime.class, new OffsetDateTimeTypeConverter());
        mapper.registerModule(javaTimeModule);
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
        return mapper;
    }

    private static ObjectMapper createDynamoObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        JavaTimeModule javaTimeModule = new JavaTimeModule();
        javaTimeModule.addDeserializer(OffsetDateTime.class, new OffsetDateTimeTypeConverter());
        // Custom serializer: ISO_DATE_TIME → "Z" for UTC, same as old DynamoDBTypeConverter.convert()
        javaTimeModule.addSerializer(OffsetDateTime.class,
            new com.fasterxml.jackson.databind.ser.std.StdSerializer<OffsetDateTime>(OffsetDateTime.class) {
                @Override
                public void serialize(OffsetDateTime value, com.fasterxml.jackson.core.JsonGenerator gen,
                                      com.fasterxml.jackson.databind.SerializerProvider provider)
                        throws java.io.IOException {
                    gen.writeString(value.format(DateTimeFormatter.ISO_DATE_TIME));
                }
            });
        mapper.registerModule(javaTimeModule);
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
        return mapper;
    }

    @Override
    public AttributeValue transformFrom(Audit audit) {
        if (audit == null) {
            return AttributeValue.builder().nul(true).build();
        }
        Map<String, Object> javaMap = DYNAMO_OBJECT_MAPPER.convertValue(audit, Map.class);
        //                            ^^^^^^^^^^^^^^^^^^ uses ISO_DATE_TIME → "Z"
        return AttributeValue.fromM(LegacyMapConverter.toAttributeValueMap(javaMap));
    }

    @Override
    public Audit transformTo(AttributeValue attributeValue) {
        // ... unchanged — OBJECT_MAPPER handles reading (robust via OffsetDateTimeTypeConverter)
    }
}
```

### 5.4 What This Achieves — Full Compatibility Matrix

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║             AFTER FIX — COMPATIBILITY MATRIX                                  ║
╠══════════════════════╦═══════════════════════════════╦════════════════════════╣
║  Consumer            ║  Format seen                  ║  Can parse?            ║
╠══════════════════════╬═══════════════════════════════╬════════════════════════╣
║  Visibility          ║  DynamoDB: "...Z" (ISO_DATE)  ║  ✅ ISO_OFFSET_DATE    ║
║  (SDK v1,            ║  restored to production fmt   ║  handles "Z"           ║
║  booking:2.1.8.M)    ║                               ║                        ║
╠══════════════════════╬═══════════════════════════════╬════════════════════════╣
║  ETL Glue job        ║  REST API: "...+0000"         ║  ✅ unix_timestamp      ║
║  (Redshift)          ║  @JsonFormat(SSSZ) unchanged  ║  "SSSZ" parses +0000   ║
╠══════════════════════╬═══════════════════════════════╬════════════════════════╣
║  Booking SDK v2      ║  DynamoDB: "...Z" or "+0000"  ║  ✅ OffsetDateTimeType  ║
║  (AuditConverter)    ║  (mixed historical records)   ║  Converter handles both ║
╠══════════════════════╬═══════════════════════════════╬════════════════════════╣
║  Production REST API ║  "...210+0000" (prod today)   ║  ✅ No change to API    ║
║  consumers           ║  Fix keeps @JsonFormat(SSSZ)  ║  format for callers    ║
╚══════════════════════╩═══════════════════════════════╩════════════════════════╝
```

### 5.5 Validation Checklist

| Claim in Copilot Fix | Verified? | Notes |
|----------------------|-----------|-------|
| `DYNAMO_OBJECT_MAPPER` uses `ISO_DATE_TIME` → produces `Z` | ✅ Logic correct | Need to implement custom serializer (not just different mapper instance) |
| `@JsonFormat(SSSZ)` on `Audit.java` unchanged → REST API still `+0000` | ✅ Correct | Current `Audit.java` has `SSSZ` (verified) |
| Visibility reads `Z` via `ISO_OFFSET_DATE_TIME` | ✅ Correct | Both `Z` and `+00:00` are valid for `ISO_OFFSET_DATE_TIME` |
| ETL reads `+0000` from REST API | ✅ Correct | `unix_timestamp("...SSSZ")` handles `+0000` |
| `transformTo()` (read path) unchanged | ✅ Correct | `OBJECT_MAPPER` with `OffsetDateTimeTypeConverter` handles all variants |
| `@JsonDeserialize` on `Audit.java` is irrelevant to DynamoDB write | ✅ Correct | `@JsonDeserialize` only controls Jackson deserialization (reading), not writing |
| Existing tests pass | ⚠️ Needs verification | `timestampSerializationFormat()` asserts `matches(".*[Z+].*")` — `Z` satisfies this ✅ |

### 5.6 One Gap in the Proposed Fix

The copilot doc mentions `DYNAMO_OBJECT_MAPPER` but does not provide the actual implementation detail of **how** it ignores `@JsonFormat`. A custom serializer registered via `JavaTimeModule.addSerializer()` takes priority over `@JsonFormat` annotations — this is the required mechanism. Simply creating a second `ObjectMapper` instance with the same modules would NOT override `@JsonFormat`.

The implementation in Section 5.3 above provides the correct approach.

---

## Part 6: Records Already Written with `+0000` in QA

### Current State of QA DynamoDB

Records written between these periods have `+0000` format in QA DynamoDB:
- **2026-03-27 → 2026-04-16** (Stage 1: SDK v2 initial, `SSSZ`)
- **2026-05-05 → present** (Stage 3: revert, `SSSZ`)

```
╔═══════════════════════════════════════════════════════════╗
║  EXISTING QA RECORDS: VISIBILITY READ COMPATIBILITY       ║
╠════════════════════════╦══════════════╦═══════════════════╣
║  Record created        ║  DynamoDB    ║  Visibility reads?║
║                        ║  format      ║                   ║
╠════════════════════════╬══════════════╬═══════════════════╣
║  Pre-2026-03-27        ║  "...Z"      ║  ✅ Yes           ║
║  (SDK v1 in QA, old)   ║  (nanosecs)  ║                   ║
╠════════════════════════╬══════════════╬═══════════════════╣
║  2026-03-27→2026-04-16 ║  "...+0000"  ║  ❌ No            ║
║  (SDK v2 initial)      ║              ║                   ║
╠════════════════════════╬══════════════╬═══════════════════╣
║  2026-04-17→2026-05-04 ║  "...Z"      ║  ✅ Yes           ║
║  (SSSXXX fix period)   ║  (millis)    ║                   ║
╠════════════════════════╬══════════════╬═══════════════════╣
║  2026-05-05→present    ║  "...+0000"  ║  ❌ No ← CURRENT  ║
║  (revert period)       ║              ║   PROBLEM         ║
╚════════════════════════╩══════════════╩═══════════════════╝

After the fix: new records will write "Z" → Visibility reads ✅
Old "+0000" records: still unreadable by Visibility until rewritten by Booking.
```

**Options for existing `+0000` records** (as correctly stated in copilot doc):
1. Accept — records age out or will be rewritten when booking updates them
2. Data migration — normalize `audit.createdDateUtc` value in DynamoDB from `+0000` → `Z`
3. Publish `booking:2.1.9.M` with fixed converter — but this requires a model artifact release

---

## Part 7: The Latent `containerTypeList` Issue

The copilot document raises this in Section 11.4 and it warrants emphasis. Unlike `Audit`, the `containerTypeList.lastModifiedDateUtc` fix was **incomplete**:

```
                    WHAT WAS FIXED vs WHAT REMAINS BROKEN

Audit.createdDateUtc:                        ContainerType.lastModifiedDateUtc:
──────────────────────                        ────────────────────────────────────
Write path (@JsonFormat): SSSZ → +0000       Write path (@JsonFormat): space format → "2018-02-27 16:59:38"
Read  path (@JsonDeserialize): ✅ robust     Read  path (@JsonDeserialize): ✅ FlexibleDateDeserializer

Proposed fix decouples write path ✅          Write path STILL broken — fix not applied ❌
                                              Visibility STILL fails if it reads any
                                              BookingDetail with containerTypeList
                                              entries written post-upgrade.

This is not today's crash (today's crash is audit), but it is a REAL bug
that will surface whenever visibility processes a booking that was enriched
with container type data after 2026-03-27.
```

---

## Part 8: Summary — What the Copilot Document Got Right and Wrong

### Got Right ✅

- Root cause identification: visibility reads `audit` via `@DynamoDBDocument` recursion
- The "coupling" concept: single `@JsonFormat` controlling both DynamoDB and REST API
- The `Z` vs `+0000` parsing difference in `ISO_OFFSET_DATE_TIME`
- The proposed fix direction (DYNAMO_OBJECT_MAPPER decoupling)
- The `Z` pattern letter = RFC 822 `+0000` explanation (Section 10)
- The nanosecond vs millisecond precision difference between production and QA
- Correction that pre-upgrade format was `Z` not `+00:00` (Sections 13, 17)
- Identification of the `+0000` normalization step missing from `booking:2.1.8.M`
- The latent `containerTypeList` issue (Section 11.4)

### Got Wrong / Needs Clarification ⚠️

| Issue | Location | Severity |
|-------|----------|----------|
| Pre-upgrade format claimed as `+00:00` | 2026-05-05 doc §2.1 (line 23) | High — invalidates ETL backlog gap analysis |
| "Visibility doesn't touch audit" | 2026-05-05 doc §15.4 | Critical — caused today's crash to be missed |
| Proposed fix is complete for ETL revert | 2026-05-05 doc §11 | High — the revert itself broke visibility |
| `DYNAMO_OBJECT_MAPPER` has no implementation detail | 2026-05-06 doc §6.2 | Moderate — implementation needed (see §5.3 above) |
| `ContainerType` fix marked as low severity | Both docs | Moderate — it's a continuing write-path bug |

---

## Part 9: Recommended Actions

### Immediate (current release — single file change)

**File**: [AuditAttributeConverter.java](booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java)

Add `DYNAMO_OBJECT_MAPPER` with a custom `OffsetDateTime` serializer that uses `ISO_DATE_TIME` (see Section 5.3). Change `transformFrom()` to use `DYNAMO_OBJECT_MAPPER`. Leave `@JsonFormat(SSSZ)` on `Audit.java` untouched.

**Expected result**: DynamoDB writes `Z`, REST API writes `+0000`, visibility reads `Z`, ETL reads `+0000`. All consumers satisfied.

### Post-Release

1. **ETL backlog** — Records from 2026-03-27→2026-04-16 and 2026-05-05→fix date have `+0000` in QA DynamoDB. These remain unreadable by visibility unless rewritten. Assess volume; consider a targeted DynamoDB scan and update.

2. **`ContainerType.lastModifiedDateUtc` write path** — `EnrichedAttributesConverter` still writes space-format dates for container type data. This is a separate ongoing visibility breakage for enriched bookings. Fix `@JsonFormat` on `ContainerType.lastModifiedDateUtc` to use ISO pattern (and ensure `FlexibleDateDeserializer` covers backward compat).

3. **Publish `booking:2.1.9.M`** — A new model artifact with the fixed `OffsetDateTimeTypeConverter` (with `+0000` normalization) would allow visibility to read both `Z` and `+0000` records without requiring DynamoDB data migration. This is the correct long-term solution.

4. **ETL Glue job** — Regardless of the booking fix, update the ETL to use `to_timestamp` with `SSSXXX` pattern (handles `Z`, `+0000`, `+00:00` natively). Eliminates fragile substring millisecond extraction and pre-existing `+00:00` parse failure.

---

## Part 10: Fix for the Latent `enrichedAttributes.containerType.lastModifiedDateUtc` Bug

### 10.1 Updated Status (After Source Verification)

A code-level fix for `ContainerType.lastModifiedDateUtc` was already applied on **2026-04-22** in commit `b2be757726` ("ION-14382-integration issue fixes"). The current source state is:

```java
// booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java
// Line 64-66 (verified)

@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", timezone = "UTC")    // ← LITERAL Z (good)
@JsonDeserialize(using = FlexibleDateDeserializer.class)
private Date lastModifiedDateUtc;
```

The same fix was applied to `PackageType.lastModifiedDateUtc` (commit `b2be757726`).

```
DECONSTRUCTING THE PATTERN: "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"
                                            ────       ───
                                            literal    literal
                                            T          Z

NOTE: Single quotes in @JsonFormat patterns escape the character to a LITERAL.
      'Z' (single-quoted) → produces the literal character "Z" in the output
      Z   (unquoted)      → produces RFC 822 numeric offset "+0000"

This pattern produces:  "2018-02-27T16:59:38.000Z"   ← ISO 8601 with literal Z
Visibility's Joda time DateUtils.parseISO8601Date() can parse this format ✅
```

This means the **WRITE-PATH BUG IS ALREADY FIXED** in source — the copilot doc's claim that "EnrichedAttributesConverter still writes space-format" is no longer accurate (it was correct on 2026-04-21 when `visibility-integration-issue-04212026.md` was written, but stale by 2026-05-06).

### 10.2 What Actually Remains as a Latent Issue

While source is fixed, two real concerns persist:

#### Issue A — Backlog records in QA DynamoDB

Records written between **2026-03-27 → 2026-04-22** (initial AWS upgrade through ContainerType fix deployment) have space-format `lastModifiedDateUtc` in QA DynamoDB:

```
Stored value: "2018-02-27 16:59:38"   ← space separator (legacy bug period)

When visibility's SDK v1 Joda time DateUtils.parseISO8601Date() reads:
  → "Invalid format: '2018-02-27 16:59:38' is malformed at ' 16:59:38'"
  → IllegalArgumentException
  → BookingDetailVisibility[enrichedAttributes]; could not unconvert
```

These records remain unreadable by visibility until they are rewritten by booking. The exact same backlog problem applies to `Audit.createdDateUtc` for the corresponding `+0000` periods.

#### Issue B — Other date fields in EnrichedAttributes sub-models

Audit of the `EnrichedAttributes` object graph for date fields:

| Sub-model | Date field | Annotation | Status |
|-----------|-----------|-----------|--------|
| `ContainerType.lastModifiedDateUtc` | `Date` | `'Z'` literal + FlexibleDateDeserializer | ✅ Fixed |
| `PackageType.lastModifiedDateUtc` | `Date` | `'Z'` literal + FlexibleDateDeserializer | ✅ Fixed |
| `LocationAdditionalInfo` | (no Date field) | — | ✅ N/A |
| `TransactionParty` | (no Date field) | — | ✅ N/A |
| `MultiVersionAttributes` | (no Date field) | — | ✅ N/A |

No additional `enrichedAttributes` date fields require source-level changes.

### 10.3 The Fix — Two Components

#### Component 1: Confirm `'Z'` Literal Pattern Is Bulletproof

The `'Z'` literal pattern is correct, but it has one subtle edge case worth verifying — when `Date` field value is `null`. Jackson with `WRITE_DATES_AS_TIMESTAMPS=false` writes `null` as a JSON null, which `LegacyMapConverter` should map to a DynamoDB `NULL` AttributeValue (not the string `"null"`). Verify the existing converter handles this. Spot-check verifies it does — `OBJECT_MAPPER.convertValue()` produces a Java `null` in the Map, and `LegacyMapConverter.toAttributeValueMap()` handles nulls correctly.

#### Component 2: Make Visibility's Read Path Resilient (the real fix)

Even after the source fix and any backlog migration, the architecture remains brittle: visibility depends on a **published artifact (`booking:2.1.8.M`) frozen at SDK v1 vintage** which has no flexibility for format variations. Rather than relying on the booking module to never produce non-ISO-8601 dates for visibility, the durable fix is to **publish an updated `booking:2.1.9.M` artifact** with a more permissive Joda time fallback.

However, that's a larger change. The minimum viable fix for the current release window is to **also** decouple the `EnrichedAttributesConverter` write path the same way as `AuditAttributeConverter`, so that DynamoDB always sees the most permissive format regardless of what `@JsonFormat` says on individual fields.

```
                    ENRICHED ATTRIBUTES CONVERTER FIX

                              EnrichedAttributes (with nested ContainerType, PackageType, ...)
                                          │
                       ┌──────────────────┴──────────────────┐
                       │                                     │
                       ▼                                     ▼
            ┌─────────────────────────┐        ┌──────────────────────────┐
            │  DynamoDB WRITE         │        │  REST API / Outbound     │
            │  EnrichedAttributes     │        │  Pipeline                │
            │  Converter              │        │                          │
            │  .transformFrom()       │        │  Uses shared mapper      │
            │                         │        │  Reads @JsonFormat('Z')  │
            │  DYNAMO_OBJECT_MAPPER   │        │  Date → "...000Z"        │
            │  Custom Date serializer │        │                          │
            │  → ISO 8601 with        │        │                          │
            │    literal Z, always    │        │                          │
            └─────────────────────────┘        └──────────────────────────┘
                       │                                     │
                       ▼                                     ▼
            "...T16:59:38.000Z"                    "...T16:59:38.000Z"
            ──────────────────                     ──────────────────
            Even if a future @JsonFormat           Same format — both
            change inadvertently introduces        consumers protected
            a space pattern, DynamoDB still
            gets ISO format → visibility safe
```

### 10.4 Recommended Implementation

Apply the same `DYNAMO_OBJECT_MAPPER` defense pattern used for `AuditAttributeConverter` in §5.3:

```java
// EnrichedAttributesConverter.java — PROPOSED CHANGES

import com.fasterxml.jackson.databind.ser.std.StdSerializer;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.SerializerProvider;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.TimeZone;

public final class EnrichedAttributesConverter implements AttributeConverter<EnrichedAttributes> {

    // Shared mapper for READING — handles all formats via FlexibleDateDeserializer
    private static final ObjectMapper OBJECT_MAPPER = createObjectMapper();

    // DynamoDB-specific mapper for WRITING — pins Date to ISO 8601 with literal Z
    private static final ObjectMapper DYNAMO_OBJECT_MAPPER = createDynamoObjectMapper();

    private static ObjectMapper createObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        mapper.registerModule(new Jdk8Module());
        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
        return mapper;
    }

    private static ObjectMapper createDynamoObjectMapper() {
        ObjectMapper mapper = new ObjectMapper();
        mapper.registerModule(new JavaTimeModule());
        mapper.registerModule(new Jdk8Module());

        // Register a Date serializer that always writes ISO 8601 with literal Z, UTC.
        // This OVERRIDES any @JsonFormat annotation on individual Date fields.
        SimpleModule dateModule = new SimpleModule();
        dateModule.addSerializer(Date.class, new StdSerializer<Date>(Date.class) {
            private final ThreadLocal<SimpleDateFormat> sdf = ThreadLocal.withInitial(() -> {
                SimpleDateFormat fmt = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'");
                fmt.setTimeZone(TimeZone.getTimeZone("UTC"));
                return fmt;
            });
            @Override
            public void serialize(Date value, JsonGenerator gen, SerializerProvider provider)
                    throws IOException {
                gen.writeString(sdf.get().format(value));
            }
        });
        mapper.registerModule(dateModule);

        mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
        mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
        return mapper;
    }

    @Override
    @SuppressWarnings("unchecked")
    public AttributeValue transformFrom(EnrichedAttributes input) {
        if (input == null) {
            return AttributeValue.builder().nul(true).build();
        }
        Map<String, Object> javaMap = DYNAMO_OBJECT_MAPPER.convertValue(input, Map.class);
        //                            ^^^^^^^^^^^^^^^^^^ guarantees ISO 8601 with literal Z
        return AttributeValue.fromM(LegacyMapConverter.toAttributeValueMap(javaMap));
    }

    @Override
    public EnrichedAttributes transformTo(AttributeValue attributeValue) {
        // ... unchanged — OBJECT_MAPPER handles reading via @JsonDeserialize(FlexibleDateDeserializer)
    }
    // ... rest unchanged
}
```

**Rationale for the registered Date serializer (vs. relying on `@JsonFormat`):**

The `@JsonFormat(pattern = "...'Z'")` on `ContainerType.lastModifiedDateUtc` is correct today, but it leaves the system one careless edit away from re-introducing the space-format bug. A future developer modifying the annotation (or a new sub-model adding a `Date` field without an annotation, which would default to `+0000` via Jackson's default `Date` serialization with `WRITE_DATES_AS_TIMESTAMPS=false`) could silently re-break visibility. Pinning the format at the converter level provides defense-in-depth: regardless of per-field annotations, DynamoDB will always receive ISO 8601 with literal `Z` for any `Date` field anywhere in the `EnrichedAttributes` graph.

### 10.5 Backlog Records — Decision Required

For QA records written **2026-03-27 → 2026-04-22** with space-format `lastModifiedDateUtc`:

| Option | Description | Effort | Risk |
|--------|-------------|--------|------|
| **A. Accept** | Records age out as visibility skips them; new records work | Zero | Visibility still has intermittent failures on a known cohort |
| **B. Targeted DynamoDB scan** | Read all `BookingDetail` records, normalize space-format dates in `enrichedAttributes.containerTypeList[*].lastModifiedDateUtc` to ISO format, write back | Moderate (one-off Lambda or script) | Low — idempotent, only touches affected fields |
| **C. Trigger booking re-publish** | Cause booking to update affected records, which rewrites `enrichedAttributes` with the fixed format | High | Side effects on downstream consumers (Watermill, transformer) re-processing events |

**Recommendation**: Option B (targeted scan). It is contained, idempotent, and does not trigger downstream event side effects. The scan can be done with a scoped DynamoDB filter expression to limit blast radius.

### 10.6 Validation Checklist for Component 2

| Property | Verified? |
|----------|-----------|
| `DYNAMO_OBJECT_MAPPER` writes ISO 8601 with literal `Z` for any `Date` field | ✅ Custom serializer registered with priority over `@JsonFormat` |
| Existing `@JsonFormat(pattern = "...'Z'")` on `ContainerType` and `PackageType` still produces the same output | ✅ Identical format — no behavior change for these fields |
| REST API output unchanged (still uses field-level `@JsonFormat`) | ✅ DYNAMO_OBJECT_MAPPER is converter-private; Dropwizard JAX-RS uses its own mapper |
| `transformTo()` (read path) handles backlog space-format records | ✅ `FlexibleDateDeserializer` covers `"yyyy-MM-dd HH:mm:ss"` (first format in its array) |
| Visibility (SDK v1 Joda time) can parse new records | ✅ ISO 8601 with literal `Z` is the canonical Joda time `parseISO8601Date()` input |
| No coupling to Redshift ETL | ✅ ETL only consumes `audit.createdDateUtc`, not `containerType` dates |

### 10.7 Bundling With Audit Fix

Both fixes (`AuditAttributeConverter` from §5.3 and `EnrichedAttributesConverter` from §10.4) follow the **same defense pattern**: register a custom serializer in a converter-private `DYNAMO_OBJECT_MAPPER` that overrides per-field `@JsonFormat` for the DynamoDB write path while leaving the REST API path under `@JsonFormat` control.

This is consistent and self-documenting — any future `Xxx → DynamoDB` converter that bridges Java models to DynamoDB Maps via Jackson should follow the same pattern. Consider extracting the pattern into a shared `DynamoJacksonMappers` utility class as a follow-up cleanup once both fixes have shipped.

```
SUMMARY OF THE TWO-CONVERTER FIX

┌────────────────────────────────┬───────────────────────────────┐
│  AuditAttributeConverter       │  EnrichedAttributesConverter  │
├────────────────────────────────┼───────────────────────────────┤
│  Issue: Audit.createdDateUtc   │  Issue: ContainerType         │
│         + lastModifiedDateUtc  │         .lastModifiedDateUtc  │
│         (and lastModifiedDate  │         + PackageType         │
│         Utc)                   │                               │
├────────────────────────────────┼───────────────────────────────┤
│  Field type: OffsetDateTime    │  Field type: Date             │
├────────────────────────────────┼───────────────────────────────┤
│  Pin DynamoDB format via:      │  Pin DynamoDB format via:     │
│  Custom OffsetDateTime         │  Custom Date serializer       │
│  serializer using              │  using SimpleDateFormat       │
│  ISO_DATE_TIME (→ Z)           │  ("...'Z'") in UTC            │
├────────────────────────────────┼───────────────────────────────┤
│  REST API format:              │  REST API format:             │
│  @JsonFormat("SSSZ") → +0000   │  @JsonFormat("...'Z'") → Z   │
│  (decoupled, ETL needs +0000)  │  (same as DynamoDB — no       │
│                                │   diverging consumer)         │
└────────────────────────────────┴───────────────────────────────┘
```

---

## References

| Document | Location |
|----------|----------|
| Copilot review document | `booking/docs/2026-05-06-visibility-audit-unconvert-issue-copilot.md` |
| Redshift ETL analysis (prior day) | `booking/docs/2026-05-05-booking-redshift-audit-field-issue.md` |
| Data format fix documentation | `booking/docs/2026-04-17-booking-dataformat-issue-fixes.md` |
| Visibility enrichedAttributes issue | `booking/docs/visibility-integration-issue-04212026.md` |
| `Audit.java` (current) | [Audit.java](booking/src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java) — line 32: `@JsonFormat(SSSZ)` confirmed |
| `AuditAttributeConverter.java` (current) | [AuditAttributeConverter.java](booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java) — single OBJECT_MAPPER confirmed |
| `OffsetDateTimeTypeConverter.java` (current) | [OffsetDateTimeTypeConverter.java](booking/src/main/java/com/inttra/mercury/booking/dynamodb/OffsetDateTimeTypeConverter.java) — normalization step present (but absent in booking:2.1.8.M) |
| `ContainerType.java` (current) | [ContainerType.java](booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java) — line 64: `'Z'` literal pattern confirmed |
| `PackageType.java` (current) | [PackageType.java](booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/PackageType.java) — line 36: `'Z'` literal pattern confirmed |
| `EnrichedAttributesConverter.java` (current) | [EnrichedAttributesConverter.java](booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverter.java) — single OBJECT_MAPPER, needs DYNAMO_OBJECT_MAPPER |
| `FlexibleDateDeserializer.java` | [FlexibleDateDeserializer.java](booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java) — handles space + ISO formats |
| Redshift ETL revert commit | `c12750e13e47` — ION-14382 redshift audit ts restore per ticket ION-15691 |
| AWS upgrade commit | `74f36e7a71` — ION-14382 bk3 aws upgrade changes (2026-03-27) |
| Data format fix commit | `ee29760491` — ION-14382 data format fixes (2026-04-17) |
| ContainerType integration fix | `b2be757726` — ION-14382-integration issue fixes (2026-04-22) — fixed `'Z'` literal pattern |
