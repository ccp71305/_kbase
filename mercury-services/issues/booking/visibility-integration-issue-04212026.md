# Visibility Integration Issue — ContainerType.lastModifiedDateUtc Format Break

**Date**: 2026-04-21
**Related Issue**: Follows from data format fixes done on 2026-04-17 (see `booking/docs/2026-04-17-booking-dataformat-fixes.md`)
**Affected Module**: `visibility-matcher`
**Root Table**: `BookingDetail` (DynamoDB)

---

## 1. Error Reported

```
visibility-matcher/exception/visibility-matcher -> BookingDetailVisibility[enrichedAttributes]; could not unconvert attribute
com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMappingException: BookingDetailVisibility[enrichedAttributes]; could not unconvert attribute
  -> EnrichedAttributes[containerTypeList]; could not unconvert attribute
    -> ContainerType[lastModifiedDateUtc]; could not unconvert attribute
      -> java.lang.IllegalArgumentException: Invalid format: "2018-02-27 16:59:38" is malformed at " 16:59:38"
         at com.amazonaws.util.DateUtils.doParseISO8601Date (Joda time)
```

---

## 2. Background: How enrichedAttributes Was Stored Before the AWS Upgrade

### Pre-Upgrade Stack (SDK v1)

Before the AWS upgrade (`ION-14382`), `BookingDetail` and its nested models used AWS SDK v1 annotations exclusively.

**`BookingDetail.java` (pre-upgrade):**
```java
@DynamoDBAttribute
private EnrichedAttributes enrichedAttributes;
```

There was no custom converter. `@DynamoDBAttribute` alone told the SDK v1 `DynamoDBMapper` to serialize the field using its native reflection-based mechanism.

**`EnrichedAttributes.java` (pre-upgrade):**
```java
@DynamoDBDocument
public class EnrichedAttributes {
    private List<LocationAdditionalInfo> transactionLocationInfoList;
    private List<TransactionParty> transactionPartyList;
    private List<PackageType> packageTypeList;
    private Set<ContainerType> containerTypeSet;   // Note: Set, not List
}
```

**`ContainerType.java` (pre-upgrade):**
```java
@DynamoDBDocument
@JsonIgnoreProperties(ignoreUnknown = true)
public class ContainerType {
    ...
    @DynamoDBTypeConvertedEnum
    private Status statusCode;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")
    private Date lastModifiedDateUtc;
    ...
}
```

### How SDK v1 Serialized Date Fields

AWS SDK v1 `DynamoDBMapper` serializes `java.util.Date` fields using `StandardTypeConverters.ToDate` which calls `DateUtils.formatISO8601Date()` internally. This produces **ISO 8601 format with T separator**, e.g.:

```
"2018-02-27T16:59:38.000Z"
```

**Critical point:** SDK v1 `DynamoDBMapper` does NOT read or respect Jackson annotations (`@JsonFormat`, `@JsonDeserialize`). The `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` annotation on `ContainerType.lastModifiedDateUtc` was entirely ignored for DynamoDB serialization. It was only ever used by Jackson when serializing the model to HTTP JSON responses in the REST API.

### How Visibility Read These Records (Pre-Upgrade)

Visibility uses SDK v1 `DynamoDBMapper` with the pre-upgrade booking model artifact (`booking:2.1.8.M`). Both booking and visibility used the same SDK v1 serialization engine:

- Booking writes: `DateUtils.formatISO8601Date()` → `"2018-02-27T16:59:38.000Z"` (ISO, T separator)
- Visibility reads: `DateUtils.parseISO8601Date()` (Joda time) → parses ISO T-separator format ✅

**Everything was in sync because both sides used the same SDK v1 date formatting engine, which ignored Jackson's `@JsonFormat` annotation completely.**

---

## 3. What the AWS Upgrade Changed

### Post-Upgrade Stack (SDK v2)

The AWS upgrade (`ION-14382`) changed `BookingDetail.getEnrichedAttributes()` to use a custom Jackson-based converter:

**`BookingDetail.java` (post-upgrade):**
```java
@DynamoDbConvertedBy(EnrichedAttributesConverter.class)
public EnrichedAttributes getEnrichedAttributes() {
    return enrichedAttributes;
}
```

**`EnrichedAttributesConverter.java` (introduced in upgrade):**
```java
private static ObjectMapper createObjectMapper() {
    ObjectMapper mapper = new ObjectMapper();
    mapper.registerModule(new JavaTimeModule());
    mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, false);
    return mapper;
}

public AttributeValue transformFrom(EnrichedAttributes input) {
    Map<String, Object> javaMap = OBJECT_MAPPER.convertValue(input, Map.class);  // Jackson used here
    return AttributeValue.fromM(LegacyMapConverter.toAttributeValueMap(javaMap));
}
```

`OBJECT_MAPPER.convertValue(input, Map.class)` now uses Jackson to serialize the entire `EnrichedAttributes` object graph — including all nested `ContainerType` objects.

**`ContainerType.java` (post-upgrade):**
```java
// @DynamoDBDocument removed (no longer needed for SDK v2)
// @DynamoDBTypeConvertedEnum removed from statusCode

@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")  // still present, unchanged
@JsonDeserialize(using = FlexibleDateDeserializer.class)         // added in data format fix
private Date lastModifiedDateUtc;
```

### The Breaking Change

Because Jackson is now used for DynamoDB serialization, `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` is now **actively applied** to DynamoDB storage. This annotation — which had always existed but was silently ignored by SDK v1 for DynamoDB purposes — now controls what gets written to DynamoDB:

| | Serialization Engine | Date Format Written to DynamoDB |
|---|---|---|
| **Pre-upgrade** | SDK v1 `DateUtils.formatISO8601Date()` | `"2018-02-27T16:59:38.000Z"` (ISO, T separator) |
| **Post-upgrade** | Jackson with `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` | `"2018-02-27 16:59:38"` (space separator) |

The annotation was not newly added — it was always there. The upgrade changed *which serialization engine* writes to DynamoDB, and the new engine (Jackson) respects the annotation while the old one (SDK v1 mapper) did not.

---

## 4. Why Visibility Now Fails

Visibility still uses SDK v1 `DynamoDBMapper` with the pre-upgrade `booking:2.1.8.M` artifact. Its read path is unchanged:

1. Reads `enrichedAttributes` as a DynamoDB Map (M-type)
2. Reflects through `@DynamoDBDocument` classes to deserialize nested `ContainerType` objects
3. For `lastModifiedDateUtc` (type `java.util.Date`), calls `DateUtils.parseISO8601Date()` (Joda time)
4. Joda time receives `"2018-02-27 16:59:38"` (space format) → **expects T separator at index 10 → throws IllegalArgumentException**

The pre-upgrade `booking:2.1.8.M` artifact's `ContainerType` class does NOT have `@JsonDeserialize(using = FlexibleDateDeserializer.class)` — that annotation was only added to the workspace code during the data format fixes on 2026-04-17. Even if it did have it, SDK v1 would still ignore it because `DynamoDBMapper` uses Joda time, not Jackson, for `Date` field deserialization.

---

## 5. containerTypeSet → containerTypeList: Not an AWS Upgrade Change

A thorough check of the git history confirms the field was **already `containerTypeList` before the AWS upgrade**. The full commit sequence for `EnrichedAttributes.java` shows:

| Commit | Message | containerType field |
|--------|---------|---------------------|
| `be3c6f2149` | Enrichment for PackageCode & ContainerType | `Set<ContainerType> containerTypeSet` |
| `193a9b3336` | Enrichment for PackageCode & ContainerType test case fixes | `List<ContainerType> containerTypeList` ← changed here |
| `de2711a8ba` | trir-6440-initial commit | `List<ContainerType> containerTypeList` |
| `53c1dd6680` | ION-8601 Remove country check in location match | `List<ContainerType> containerTypeList` |
| `74f36e7a71` | **ION-14382 AWS upgrade** | `List<ContainerType> containerTypeList` — **no change** |

The Set → List rename happened in `193a9b3336`, well before the AWS upgrade, and is therefore already reflected in the pre-upgrade booking model artifact `booking:2.1.8.M`. The AWS upgrade did not change this field.

**This means there is no field-rename compatibility issue between booking and visibility for `containerTypeList`.** Both sides have been using `containerTypeList` since before `2.1.8.M` was published. This section of the earlier analysis was incorrect and is now corrected.

---

## 6. Design Decision: Why Jackson Was Used for DynamoDB Serialization

### The Core Design Decision in the AWS Upgrade

The AWS upgrade (`ION-14382`, commit `74f36e7a71`) made a deliberate architectural decision to replace SDK v1's native `DynamoDBMapper` annotation-driven serialization with **custom `AttributeConverter` implementations backed by Jackson ObjectMapper**.

This is documented in `booking/docs/DESIGN-AWS2x.md` under **"DynamoDB Model Annotation Removal (v1.1)"**:

> *All 90+ model/DTO classes had AWS SDK 1.x DynamoDB annotations removed since the cloud-sdk Enhanced Client uses its own annotation model (`@DynamoDbBean`, etc.) managed at the repository layer rather than on business model classes.*

The removed annotations included:

| Annotation | Count | Purpose |
|------------|-------|---------|
| `@DynamoDBDocument` | ~70 | Mark class as DynamoDB nested document |
| `@DynamoDBIgnore` | ~15 | Skip field during DynamoDB serialization |
| `@DynamoDBTypeConvertedEnum` | ~10 | Enum serialization |
| `@DynamoDBAttribute` | ~8 | Field-to-attribute mapping |
| `@DynamoDBTypeConverted` | ~5 | Custom type converter |

### Why Jackson for `enrichedAttributes` Specifically

`EnrichedAttributesConverter` was one of **5 new custom converters added in the upgrade** (confirmed in the Added Files list from the 223-file commit):

- `EnrichedAttributesConverter` — Jackson-based, converts `EnrichedAttributes` ↔ DynamoDB Map
- `AuditAttributeConverter` — Jackson-based
- `MetaDataConverter` — Jackson-based
- `LegacyMapConverter` — utility, bridges Jackson Map output to DynamoDB AttributeValue types
- Others: `ConditionListAttributeConverter`, `RangeAttributeConverter`, `SpotRatesAttributeConverter`

The `LegacyMapConverter` class comment explicitly states the intent:

> *"This preserves the native DynamoDB Map format used by AWS SDK v1's `@DynamoDBDocument`."*

The design intent was correct: store `enrichedAttributes` as a DynamoDB native Map (M-type), mirroring what SDK v1's `@DynamoDBDocument` produced — so that both booking (SDK v2) and visibility (SDK v1) could read the same data. Jackson was used as the serialization engine because it was already present in the codebase and provided a clean way to convert complex nested objects to/from Java Maps.

### Where the Design Fell Short

The design assumed Jackson would produce the **same field-level data formats** that SDK v1's `@DynamoDBDocument` produced for nested types. This assumption was wrong for `Date` fields:

| Field type | SDK v1 `@DynamoDBDocument` format | Jackson with `WRITE_DATES_AS_TIMESTAMPS=false` |
|---|---|---|
| `Date` with `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` | ISO format `"2018-02-27T16:59:38.000Z"` (annotation ignored by SDK v1) | Space format `"2018-02-27 16:59:38"` (annotation respected by Jackson) |
| `Date` with no annotation | ISO format `"2018-02-27T16:59:38.000Z"` | ISO format `"2018-02-27T16:59:38.153+0000"` (mostly compatible) |

The `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` annotation on `ContainerType.lastModifiedDateUtc` had been present since the field was first introduced (commit `d953471abd`, "Container Type Reference Data Service"). It was always intended for the REST API JSON response layer only. SDK v1 ignored it for DynamoDB purposes, so it was harmless. When Jackson took over DynamoDB serialization, it started respecting this annotation, silently changing the on-disk format.

### `FlexibleDateDeserializer` Was Added for This Exact Reason

Notably, `FlexibleDateDeserializer.java` is listed as one of the **37 Added Files** in the upgrade commit (`74f36e7a71`). It was added precisely because the upgrade team anticipated that switching from SDK v1 to Jackson could produce different date formats for existing records. The deserializer supports both formats for backward compatibility when the booking module reads from DynamoDB.

However, the deserializer only protects the **booking module's own read path**. It cannot help visibility's SDK v1 `DynamoDBMapper`, which uses Joda time internally and has no knowledge of Jackson deserializers.

### Root Gap in Design

The design correctly handled the booking-side read path with `FlexibleDateDeserializer`, but did not account for the **write path changing the on-disk format** in a way that would break other modules still using SDK v1. The `LegacyMapConverter` comment claimed format preservation, but the preservation broke down for `Date` fields annotated with `@JsonFormat` space-separator patterns.

---

## 8. Scope: What Other Fields Are Affected?

### ContainerType — AFFECTED
- `lastModifiedDateUtc`: `java.util.Date` with `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` → space format stored → **breaks Joda time in visibility** ❌

### PackageType — NOT AFFECTED
- `lastModifiedDateUtc`: `java.util.Date` with **no `@JsonFormat`** annotation
- Jackson with `WRITE_DATES_AS_TIMESTAMPS=false` defaults to ISO 8601 for bare `Date` fields: `"2020-11-30T04:23:30.153+0000"`
- Joda time can parse this format ✅

### Other EnrichedAttributes sub-models (LocationAdditionalInfo, TransactionParty, MultiVersionAttributes)
- Need to audit for any `Date` fields with space-format `@JsonFormat` patterns
- Run: `grep -r "@JsonFormat" booking/src/main/java/com/inttra/mercury/booking/model/`

---

## 9. Why the April 17 Fixes Didn't Catch This

The 2026-04-17 fixes addressed data format issues **within the booking module itself** — making the booking module able to read its own old records. The backward compatibility matrix in that document covers `MetaData.timestamp`, `Audit` dates, `expiresOn`, `payload`, `state`, `channel`, and `payloadType`. 

`ContainerType.lastModifiedDateUtc` inside `enrichedAttributes` was not in scope because:
1. The failure manifests in **visibility**, not in the booking read path
2. The booking module's own reading is protected by `FlexibleDateDeserializer` on the field
3. The failure only becomes visible when visibility's Joda time parser encounters the space-format date stored by the upgraded booking module

---

## 10. Proposed Fix Plan

### Fix 1 — Change ContainerType serialization format to ISO 8601 (Core Fix)

**File:** `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java`

```java
// Before
@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")
@JsonDeserialize(using = FlexibleDateDeserializer.class)
private Date lastModifiedDateUtc;

// After
@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", timezone = "UTC")
@JsonDeserialize(using = FlexibleDateDeserializer.class)
private Date lastModifiedDateUtc;
```

**Backward compatibility:**
- `FlexibleDateDeserializer` already handles `"yyyy-MM-dd HH:mm:ss"` as its first listed format → booking module can still read old space-format records from DynamoDB ✅
- New records written by booking will use ISO format → visibility's Joda time can parse ✅
- Old records in DynamoDB already written in space format will still fail in visibility until booking rewrites them (see Fix 4 on data migration)

### Fix 2 — Extend FlexibleDateDeserializer for microsecond precision

**File:** `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java`

The current formats handle up to 3 fractional digits (`SSS`). Some existing records contain 6 fractional digits (microseconds). Add:

```java
"yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'",   // microseconds, UTC
"yyyy-MM-dd'T'HH:mm:ss.SSSSSSZ"       // microseconds with timezone offset
```

### Fix 3 — Audit other EnrichedAttributes sub-model date fields

Check all models referenced from `EnrichedAttributes` for `@JsonFormat` with space patterns:
```bash
grep -r "@JsonFormat" booking/src/main/java/com/inttra/mercury/booking/model/
grep -r "java.util.Date" booking/src/main/java/com/inttra/mercury/booking/model/Common/
```

Apply the same ISO format fix to any field found with `pattern = "yyyy-MM-dd HH:mm:ss"`.

### Fix 4 — Data Migration for Existing Records (Decision Required)

Records already written to DynamoDB in space format will continue to fail in visibility until the booking module next writes/updates them. Two options:

**Option A — Gradual (no action):** Records naturally migrate to ISO format whenever booking next updates them. Acceptable only if the volume of visibility failures is low and records are frequently touched.

**Option B — Migration Script:** Write a one-off DynamoDB scan that reads all BookingDetail records, reformats `enrichedAttributes.containerTypeList[*].lastModifiedDateUtc` from space to ISO format, and writes them back. Required if visibility failure volume is significant.

### Fix 5 — Tests to Add

| Test | File | Assertion |
|------|------|-----------|
| `ContainerType` round-trip via `EnrichedAttributesConverter` | `EnrichedAttributesConverterTest` | `lastModifiedDateUtc` stored as ISO format (T separator) |
| `FlexibleDateDeserializer` — ISO format with milliseconds | `FlexibleDateDeserializerTest` | Parses `"2020-12-08T18:07:00.000Z"` |
| `FlexibleDateDeserializer` — space format (backward compat) | `FlexibleDateDeserializerTest` | Parses `"2018-02-27 16:59:38"` |
| `FlexibleDateDeserializer` — microseconds | `FlexibleDateDeserializerTest` | Parses `"2020-11-30T04:23:30.153845Z"` |
| Simulate visibility read | `EnrichedAttributesConverterTest` | Write record → extract raw DynamoDB S value for `lastModifiedDateUtc` → assert T separator present (what Joda time will see) |

---

## 11. Summary

| Aspect | Detail |
|--------|--------|
| **Root cause (date format)** | AWS upgrade introduced `EnrichedAttributesConverter` (Jackson-based). Jackson now respects `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` for DynamoDB storage, writing space-format dates. Before the upgrade, SDK v1 `DynamoDBMapper` ignored this annotation and wrote ISO format. |
| **Who is broken** | `visibility-matcher`: date format error when reading any BookingDetail record that contains `enrichedAttributes.containerTypeList` with a date value. |
| **Why it worked before** | Both booking (SDK v1) and visibility (SDK v1) used `DateUtils.formatISO8601Date()` for DynamoDB Date serialization. Jackson annotations were irrelevant to DynamoDB storage. `containerTypeList` field name was consistent in both sides since long before the upgrade. |
| **Design intent** | `LegacyMapConverter` was designed to "preserve the native DynamoDB Map format used by SDK v1 `@DynamoDBDocument`". The intent was correct but failed for `Date` fields with space-format `@JsonFormat` annotations. `FlexibleDateDeserializer` was added to protect the booking read path but not the write path format. |
| **Core date fix** | Change `@JsonFormat` on `ContainerType.lastModifiedDateUtc` to ISO 8601 pattern. `FlexibleDateDeserializer` already handles backward compat for booking reading old space-format records. |
| **containerTypeSet/List** | The Set→List rename happened in commit `193a9b3336`, well before the AWS upgrade. The `2.1.8.M` artifact already has `containerTypeList`. No compatibility issue here. |
| **Data migration** | Old records with space-format dates will still fail in visibility until rewritten by booking. Assess error volume to decide between gradual vs. scripted migration. |