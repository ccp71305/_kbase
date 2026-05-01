# Booking Data Format Fixes — Backward Compatibility

**Date**: 2026-04-17  
**Session ID**: `9d0caeabd6394be2`  
**Related Session**: `ad378beb151a432f` (Visibility-Booking Model Compatibility Analysis)  
**Agent Model**: Claude Opus 4.6  

---

## 1. Reported Issues

### Issue 1: DateTimeParseException on MetaData.timestamp
- **Symptom**: `Text '2026-03-27T09:29:31.15' could not be parsed at index 10`
- **Root Cause**: `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss.SS")` on `MetaData.timestamp` was used for both serialization AND deserialization. When deserializing old records with ISO T-separator format, it fails because the pattern expects a space at index 10 (after the date).
- **Fix**: Changed to `@JsonFormat(shape = JsonFormat.Shape.STRING)` + `@JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)`. Serialization now writes ISO format (T separator), and deserialization accepts both T and space formats.

### Issue 2: Same as Issue 1
- Same root cause — the MetaData timestamp format mismatch.

### Issue 3: boolean "1" deserialization failure on ContainerType.displayFlag
- **Symptom**: `Cannot deserialize value of type 'boolean' from String "1"`
- **Root Cause**: Old DynamoDB records store boolean fields as DynamoDB Number type (`N("1")`). `LegacyMapConverter.toSimpleValue()` was returning the number as a String (e.g., `"1"`). Jackson cannot coerce String `"1"` to primitive `boolean`.
- **Fix**: Changed `LegacyMapConverter.toSimpleValue()` to return actual Java numbers (Integer/Long/Double) for N-type attributes. Jackson can coerce Integer `1` → `true` and `0` → `false`.

### Issue 4: OffsetDateTime parse failure on Audit.lastModifiedDateUtc
- **Symptom**: `Text '2020-11-30T04:23:30.153845Z' could not be parsed at index 23`
- **Root Cause**: `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ")` on Audit date fields expects exactly 3 fractional digits. Old records have 6 fractional digits (microseconds). Also, `Z` pattern format doesn't handle all offset variants.
- **Fix**: Changed to `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSXXX")` + `@JsonDeserialize(using = OffsetDateTimeTypeConverter.class)`. The deserializer handles all standard ISO offset formats including variable fractional digits and both `Z` and `+00:00`/`+0000` offsets.

---

## 2. Booking Model Version Control

### How booking:2.1.8.M is produced
- The `booking/pom.xml` has a Maven profile `booking-model` (line 400)
- `maven-jar-plugin` creates a JAR containing only model/dynamodb/util/outbound classes:
  - `com/inttra/mercury/booking/model/**`
  - `com/inttra/mercury/booking/inbound/**`
  - `com/inttra/mercury/booking/dynamodb/**`
  - `com/inttra/mercury/booking/util/**`
  - `com/inttra/mercury/booking/outbound/model/**`
  - `com/inttra/mercury/booking/networkservices/**`
  - `com/inttra/mercury/booking/validation/**`
  - `com/inttra/mercury/booking/common/event/**`
- `maven-deploy-plugin` deploys to S3 as `com.inttra.mercury:booking:${project.version}.M`
- Since `project.version` = `1.0`, the published artifact version would be `1.0.M`
- The `2.1.8.M` version was published from an older branch/tag where `project.version` was `2.1.8`

### The pre-upgrade booking model (2.1.8.M)
- Contains OLD SDK v1 annotations: `@DynamoDBTable`, `@DynamoDBHashKey`, `@DynamoDBRangeKey`, `@DynamoDBDocument`, `@DynamoDBTypeConverted`, etc.
- Contains OLD converters: `LocalDateTimeTypeConverter`, `OffsetDateTimeTypeConverter`, `ContractTypeConverter`, `DateToEpochSecond`
- These all implement SDK v1 `DynamoDBTypeConverter` interface

### Did the AWS upgrade create a new booking model version?
**No.** The AWS upgrade did NOT publish a new version of the booking model. The `booking-model` profile must be explicitly activated during build. The upgrade changes are only in the workspace code, not in the published `2.1.8.M` artifact.

---

## 3. Modules Using booking:2.1.8.M

| Module | POM File | Purpose |
|--------|----------|---------|
| `visibility-commons` | `visibility/visibility-commons/pom.xml` | `BookingDetailVisibility extends BookingDetail` |
| `visibility-matcher` | `visibility/visibility-matcher/pom.xml` | Booking matching logic |
| `watermill-booking` | `watermill-publisher/watermill-booking/pom.xml` | Watermill booking publisher |
| `pi-statusevents-out-processor` | `partner-integrator/pi-statusevents-out-processor/pom.xml` | Partner integration events |

All these modules use the **pre-upgrade** booking model with SDK v1 annotations. There are no compilation issues because they reference the old published artifact, not the current workspace code.

---

## 4. Visibility Dependency Analysis

- Visibility has **no direct dependency** on the booking module in the workspace
- Visibility depends on `booking:2.1.8.M` — a **published artifact** (pre-upgrade)
- The published artifact contains OLD SDK v1 annotations and converters
- Visibility uses `dynamo-client` library (SDK v1 wrapper) to read BookingDetail from DynamoDB
- **No compilation issues** exist in visibility because it uses the pre-upgrade model

---

## 5. MetaData Timestamp Format Change Explanation

### Before upgrade (SDK v1)
- `MetaData.timestamp` had `@DynamoDBTypeConverted(converter = LocalDateTimeTypeConverter.class)`
- `LocalDateTimeTypeConverter` used `DateTimeFormatter.ISO_DATE_TIME`
- **Format**: `"2020-04-14T10:21:53.78"` (ISO format with T separator)

### After upgrade (SDK v2) — BEFORE this fix
- `MetaData.timestamp` had `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss.SS")`
- `MetaDataConverter` used ObjectMapper with JavaTimeModule and `WRITE_DATES_AS_TIMESTAMPS=false`
- The `@JsonFormat` pattern controlled both serialization AND deserialization
- **Format**: `"2020-04-14 10:21:53.78"` (space separator)
- **Problem**: This created a BACKWARD INCOMPATIBLE data format change

### After this fix
- `MetaData.timestamp` has `@JsonFormat(shape = JsonFormat.Shape.STRING)` + `@JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)`
- `MetaDataConverter` ObjectMapper registers `FlexibleLocalDateTimeDeserializer` for LocalDateTime
- **Serialization**: ISO format with T separator (`"2020-04-14T10:21:53.78"`) — RESTORED backward compatibility
- **Deserialization**: Accepts both T separator and space separator — handles all existing records

### Rationale for original change
The original `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss.SS")` was inherited from `Json.DEFAULT_DATE_TIME_PATTERN`, which was the booking module's standard date format for JSON operations. The upgrade applied this pattern to the DynamoDB converter without considering that the old `LocalDateTimeTypeConverter` used ISO format. This was an unintentional breaking change.

---

## 6. Backward Compatibility Verification

### Data Format Compatibility Matrix

| Field | Old Format (SDK v1) | New Format (SDK v2 post-fix) | Compatible? |
|-------|-------|------|------|
| `metaData.timestamp` | ISO T-separator (`2020-04-14T10:21:53.78`) | ISO T-separator | ✅ Yes |
| `audit.createdDateUtc` | ISO offset (`2020-11-30T04:23:30.153+0000`) | ISO offset with XXX | ✅ Yes |
| `audit.lastModifiedDateUtc` | Same as above | Same as above | ✅ Yes |
| `enrichedAttributes` | DynamoDB Map format | DynamoDB Map format | ✅ Yes |
| `payload` (Contract) | `className:json` string | Same format | ✅ Yes |
| `expiresOn` | Epoch seconds (Long) | Epoch seconds | ✅ Yes |
| `state` (BookingState) | String name | String name | ✅ Yes |
| `payloadType` | String name | String name | ✅ Yes |
| `channel` | String name | String name | ✅ Yes |

### Converter Compatibility

| Converter | Status |
|-----------|--------|
| `MetaDataConverter` | ✅ Fixed — reads both T/space timestamps, writes T format |
| `AuditAttributeConverter` | ✅ Fixed — reads all OffsetDateTime formats |
| `EnrichedAttributesConverter` | ✅ Fixed — handles N("1") → boolean via LegacyMapConverter |
| `ContractAttributeConverter` | ✅ Compatible — identical format to old `ContractTypeConverter` |
| `DateEpochSecondAttributeConverter` | ✅ Compatible — same epoch-second format |
| `LegacyMapConverter` | ✅ Fixed — returns Java numbers for N-type (enables int→boolean coercion) |

---

## 7. Files Changed

### New Files
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/FlexibleLocalDateTimeDeserializer.java`
- `booking/src/test/java/com/inttra/mercury/booking/dynamodb/FlexibleLocalDateTimeDeserializerTest.java`

### Modified Files
- `booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java` — timestamp annotation fix
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java` — OffsetDateTime annotation fix
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/OffsetDateTimeTypeConverter.java` — robust format handling
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java` — FlexibleLocalDateTimeDeserializer registered
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java` — OffsetDateTimeTypeConverter registered
- `booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java` — N-type returns Java numbers
- `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverterTest.java` — timestamp round-trip + format tests
- `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverterTest.java` — OffsetDateTime format tests
- `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverterTest.java` — boolean N-type tests
- `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverterTest.java` — updated N-type assertions

---

## 8. Deprecated Dependencies Status

| Dependency | Status in booking/pom.xml |
|-----------|--------------------------|
| `dynamo-client` | Already removed (comment at line 96) |
| `email-sender` | Already removed (comment at line 97) |
| `aws-java-sdk-dynamodb` (v1) | Present but **test scope only** — needed for DynamoDB Local |
