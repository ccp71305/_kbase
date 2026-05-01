# Booking Integration Issues — April 2026

**Date**: 2026-04-22  
**Session ID**: `2686c49ecbb241e3`  
**Related Sessions**: `9d0caeabd6394be2` (DataFormat Fixes), `ad378beb151a432f` (Visibility Compatibility)  
**Agent Model**: Claude Opus 4.6  

---

## 1. Reported Issues

### Issue 1: Visibility DynamoDB unconvert failure — ContainerType.lastModifiedDateUtc
**Error**: `BookingDetailVisibility[enrichedAttributes] → EnrichedAttributes[containerTypeList] → ContainerType[lastModifiedDateUtc]; could not unconvert attribute`  
**Exception**: `java.lang.IllegalArgumentException: Invalid format: "2018-02-27 16:59:38" is malformed at " 16:59:38"`  
**Module**: visibility-matcher (AWS SDK v1, uses `booking:2.1.8.M`)

### Issue 2: Booking Outbound SQS MetaData.timestamp format breaking transformer
**Error**: `DateTimeParseException: Text '2026-04-21T14:30:18.66' could not be parsed at index 10`  
**Module**: transformer (appianway workspace, expects `"yyyy-MM-dd HH:mm:ss.SS"` pattern)

### Issue 3 & 4: Distributor and bridge module impact assessment
**Result**: Same root cause as Issue 2 — all downstream modules use identical `Json.DEFAULT_DATE_TIME_PATTERN = "yyyy-MM-dd HH:mm:ss.SS"`.

---

## 2. Root Cause Analysis

### Issue 1: ContainerType.lastModifiedDateUtc

**Data path**:  
`BookingDetail → enrichedAttributes (EnrichedAttributes) → containerTypeList (List<ContainerType>) → lastModifiedDateUtc (Date)`

**Serialization chain** (booking module, post AWS upgrade):
1. `EnrichedAttributesConverter.transformFrom(enrichedAttributes)` calls `OBJECT_MAPPER.convertValue(input, Map.class)`
2. Jackson serializes `ContainerType.lastModifiedDateUtc` using `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")`
3. Produces: `"2018-02-27 16:59:38"` (space separator, no milliseconds, no timezone marker)
4. Stored in DynamoDB as `S:"2018-02-27 16:59:38"`

**Reading chain** (visibility module, AWS SDK v1):
1. `DynamoDBMapper` reads BookingDetailVisibility from DynamoDB
2. `enrichedAttributes` has `@DynamoDBDocument` → recursive unconvert
3. `ContainerType` has `@DynamoDBDocument` → unconvert fields
4. `lastModifiedDateUtc` (Date) → SDK v1 uses `DateUtils.parseISO8601Date()` which calls Joda's `ISODateTimeFormat.dateTime()`
5. Expects ISO format (T separator), gets space separator → **FAILS**

**Production data** (old format written by SDK v1):
```json
"lastModifiedDateUtc": { "S": "2018-02-27T16:59:38.000Z" }
```

**Root cause**: The `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` on `ContainerType.lastModifiedDateUtc` writes a non-ISO format that AWS SDK v1's `DateUtils.parseISO8601Date()` cannot parse.

### Issue 2: MetaData.timestamp SQS format

**Before the previous fix (session `9d0caeabd6394be2`)**: MetaData.timestamp had `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss.SS")`.  
- SQS serialization via `Json.toJsonString()`: `"2026-04-22 18:32:37.65"` (space) ✅ for transformer  
- DynamoDB deserialization of old records with T format: **FAILED** (the reason for the previous fix)

**After the previous fix**: Changed to `@JsonFormat(shape = JsonFormat.Shape.STRING)`.  
- SQS serialization via `Json.toJsonString()`: `"2026-04-21T14:30:18.66"` (ISO T) ❌ for transformer  
- DynamoDB deserialization: ✅ handled by `FlexibleLocalDateTimeDeserializer`  

**The previous fix solved DynamoDB deserialization but broke SQS serialization.**

**Downstream consumers** (all expect `"yyyy-MM-dd HH:mm:ss.SS"` space format):
| Module | Workspace | Config |
|--------|-----------|--------|
| transformer | appianway | `shared/support/Json.DEFAULT_DATE_TIME_PATTERN` |
| distributor | appianway | same shared Json class |
| aw-bridge-ib | mft-s3-aqua-appia | `aw-bridge-shared/support/Json.DEFAULT_DATE_TIME_PATTERN` |
| aw-bridge-ob | mft-s3-aqua-appia | same shared Json class |

### Additional Gap Found: PackageType.lastModifiedDateUtc

`PackageType.lastModifiedDateUtc` is a `java.util.Date` field **without** `@JsonFormat`. In `EnrichedAttributesConverter` (which has `WRITE_DATES_AS_TIMESTAMPS=false`), Jackson's `DateSerializer` uses `StdDateFormat` producing a format like `"2018-02-27T16:59:38.000+0000"`. SDK v1's Joda ISO parser may not handle `+0000` (no colon). Proactive fix recommended.

### Issue 5 (Found during FlowTests): FlexibleDateDeserializer cannot parse epoch millis

**Error**: `ProcessingException: com.fasterxml.jackson.databind.JsonMappingException: Cannot parse date: "1528891200000". Supported formats: yyyy-MM-dd HH:mm:ss, yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`  
**Trigger**: Network API (`GET /network/packagetype?edifactCode=PK`) returns `lastModifiedDateUtc` as epoch milliseconds string `"1528891200000"` (= 2018-06-13T12:00:00Z)  
**Impact**: FlowTests failed with 39 retry attempts. Any booking flow that enriches package type data would fail in production.  
**Root cause**: `FlexibleDateDeserializer` only handled date-string formats (space-separated, ISO 8601), not numeric epoch timestamps.  
**Fix**: Added epoch millis detection before trying date-string formats:
```java
if (dateStr.matches("\\d+")) {
    return new Date(Long.parseLong(dateStr));
}
```

---

## 3. MetaData Timestamp Format — Before and After

### SQS Serialization Path
`EventLogger → Json.toJsonString(metaData) → SNS/SQS message`

| State | Annotation | SQS Format | DynamoDB Format | SQS OK? | DDB OK? |
|-------|-----------|------------|-----------------|---------|---------|
| Pre-upgrade (SDK v1) | `@DynamoDBTypeConverted(LocalDateTimeTypeConverter)` | `"yyyy-MM-dd HH:mm:ss.SS"` (via Json.toJsonString) | `"2020-04-14T10:21:53.78"` (ISO via LocalDateTimeTypeConverter) | ✅ | ✅ |
| Post-upgrade before fix | `@JsonFormat(pattern="yyyy-MM-dd HH:mm:ss.SS")` | `"2026-04-21 14:30:18.66"` (space) | `"2026-04-21 14:30:18.66"` (space) | ✅ | ❌ can't read old T records |
| Post previous fix | `@JsonFormat(shape=STRING)` | `"2026-04-21T14:30:18.66"` (ISO T) | `"2026-04-21T14:30:18.66"` (ISO T) | ❌ transformer fails | ✅ |
| **This fix** | `@JsonFormat(pattern="yyyy-MM-dd HH:mm:ss.SS")` + MixIn in MetaDataConverter | `"2026-04-21 14:30:18.66"` (space) | `"2026-04-21T14:30:18.66"` (ISO T via MixIn) | ✅ | ✅ |

### The Dual-Format Challenge

MetaData.timestamp serves two contexts with **conflicting** format requirements:
1. **SQS messages** → all downstream consumers expect `"yyyy-MM-dd HH:mm:ss.SS"` (space separator)
2. **DynamoDB storage** → visibility SDK v1 reads with `ISO_DATE_TIME` parser (needs T separator)

**Solution**: Use `@JsonFormat(pattern)` on the class for SQS serialization, and a Jackson MixIn in `MetaDataConverter` to override the format for DynamoDB serialization.

---

## 4. Fix Plan

### Fix 1: MetaData.timestamp — Restore SQS format + DynamoDB MixIn

**File**: `booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java`  
**Change**: `@JsonFormat(shape = JsonFormat.Shape.STRING)` → `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss.SS")`  
**Effect**: SQS messages use space format (transformer/distributor/bridge compat)

**File**: `booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java`  
**Change**: Add MixIn `MetaDataDynamoDbMixIn` that overrides `@JsonFormat(shape = STRING)` for DynamoDB serialization  
**Effect**: DynamoDB stores ISO T format (visibility SDK v1 compat)

### Fix 2: ContainerType.lastModifiedDateUtc — ISO format for DynamoDB

**File**: `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java`  
**Change**: `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` → `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")`  
**Effect**: Matches SDK v1 `DateUtils.formatISO8601Date()` output

### Fix 3: PackageType.lastModifiedDateUtc — Proactive ISO format

**File**: `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/PackageType.java`  
**Change**: Add `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", timezone = "UTC")` and `@JsonDeserialize(using = FlexibleDateDeserializer.class)`  
**Effect**: Prevents same issue as ContainerType from occurring in production

### Fix 4: FlexibleDateDeserializer — Epoch millis support

**File**: `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java`  
**Change**: Added epoch millis detection before date-string parsing: `if (dateStr.matches("\\d+")) return new Date(Long.parseLong(dateStr))`  
**Effect**: Network API returns `lastModifiedDateUtc` as epoch millis — this format must be handled to avoid `ProcessingException` during booking enrichment flows

---

## 5. Files Changed

### Modified Files
1. `booking/src/main/java/com/inttra/mercury/booking/util/MetaData.java` — @JsonFormat pattern restored
2. `booking/src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java` — MixIn for DynamoDB ISO format
3. `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java` — ISO date format
4. `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/PackageType.java` — ISO date format + FlexibleDateDeserializer
5. `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java` — Epoch millis support

### New/Modified Test Files
6. `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverterTest.java` — SQS vs DynamoDB format tests + Sonar coverage (lines 80, 83-85)
7. `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverterTest.java` — ContainerType date format tests
8. `booking/src/test/java/com/inttra/mercury/booking/util/MetaDataSerializationTest.java` — SQS serialization format verification
9. `booking/src/test/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializerTest.java` — Updated assertions + epoch millis tests
10. `booking/src/test/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataDynamoDbMixInTest.java` — MixIn behavior coverage (Sonar line 52)

---

## 6. Backward Compatibility Matrix (Post-Fix)

| Field | Old DynamoDB Format (SDK v1) | New DynamoDB Format (SDK v2 post-fix) | Visibility SDK v1 Readable? | SQS Format |
|-------|------|------|------|------|
| `metaData.timestamp` | `"2020-04-14T10:21:53.78"` | `"2026-04-21T14:30:18.66"` (ISO via MixIn) | ✅ | `"2026-04-21 14:30:18.66"` (space) |
| `containerType.lastModifiedDateUtc` | `"2018-02-27T16:59:38.000Z"` | `"2018-02-27T16:59:38.000Z"` (ISO) | ✅ | N/A |
| `packageType.lastModifiedDateUtc` | `"2018-02-27T16:59:38.000Z"` | `"2018-02-27T16:59:38.000Z"` (ISO) | ✅ | N/A |
| `audit.createdDateUtc` | `"2020-11-30T04:23:30.153+0000"` | `"2020-11-30T04:23:30.153+00:00"` | ✅ | N/A |
| `audit.lastModifiedDateUtc` | Same | Same | ✅ | N/A |

---

## 7. Test Results

### Build Command
```sh
mvn clean verify -pl booking -am
```

### Aggregate Results

| Phase | Runner | Tests | Failures | Errors | Skipped |
|-------|--------|-------|----------|--------|---------|
| Surefire (unit tests) | JUnit5 | 1920 | 0 | 0 | 1 |
| Failsafe IT (DynamoDB) | JUnit5 | 971 | 0 | 0 | 9 |
| Failsafe IT (DynamoDB) | JUnit5 | 138 | 0 | 0 | 0 |
| Failsafe IT (FlowTests) | TestNG | 149 | 3 | 0 | 0 |

**All unit tests and DynamoDB integration tests PASS.** The 3 FlowTest failures are caused by a separate bug introduced by the AWS SDK v2 upgrade (not by our date format changes). See analysis below.

### FlowTest Failure Analysis

#### Failure 1 & 2: `FlowTest.doTest on 05_confirm_split_split` and `BookingServiceIntegrationTest.testRequestConfirmSplit`

**Same root cause**: Jackson `Optional<String>` serialization error.

```
java.lang.RuntimeException: com.fasterxml.jackson.databind.exc.InvalidDefinitionException: 
Java 8 optional type `java.util.Optional<java.lang.String>` not supported by default: 
add Module "com.fasterxml.jackson.datatype:jackson-datatype-jdk8" to enable handling 
(through reference chain: 
  BookingDetail["enrichedAttributes"] -> 
  EnrichedAttributes["transactionLocationInfoList"] -> 
  ArrayList[0] -> 
  LocationAdditionalInfo["countryISO2Code"])
```

**This is NOT a flaky test — it is a real bug introduced by the AWS SDK v2 upgrade.**

##### Git History Analysis

1. **2019-05-20** (commit `2867c9d937`): `getCountryISO2Code()` returning `Optional<String>` was added to `LocationAdditionalInfo.java` with `@DynamoDBIgnore` annotation. The SDK v1 annotation told the DynamoDB mapper to skip this getter during serialization. Jackson was never used to serialize `BookingDetail` in this code path.

2. **2026-02-20** (commit `74f36e7a71`, ION-14382 bk3 aws upgrade): Two changes happened simultaneously:
   - **Removed** all `@DynamoDB*` annotations from `LocationAdditionalInfo.java` — including `@DynamoDBIgnore` on `getCountryISO2Code()`. **No `@JsonIgnore` was added as a replacement.**
   - **Added** `Json.toJsonString(detail)` call in `BookingService.newBookingDetail()` (lines 334-336) inside a new DynamoDB retry/error-handling block. This serializes the full `BookingDetail` (including `enrichedAttributes` → `transactionLocationInfoList` → `LocationAdditionalInfo`) via Jackson.

3. **The result**: Jackson discovers `getCountryISO2Code()` as a bean property, tries to serialize `Optional<String>`, but `Json.java`'s ObjectMapper lacks `Jdk8Module` → `InvalidDefinitionException`.

##### Why it only manifests on split-confirm

The `Json.toJsonString(detail)` call is **only in the error handling path** of `newBookingDetail()` — it's called when DynamoDB writes fail with `ConditionalCheckFailedException` after retries exhaust:

```java
// BookingService.java lines 322-341 (added in AWS upgrade)
} catch (DynamoDbException awsException) {
    ++noOfRetries;
    if (noOfRetries > config.getDynamoExceptionMaxRetryCount()) {
        log.error("Error occurred for workflowId {} and data {}", 
            Booking.getWorkflowId(metaData), Json.toJsonString(detail));  // <-- FAILS HERE
        s3WorkspaceService.putObject(..., Json.toJsonString(detail));      // <-- AND HERE
    }
}
```

The split-confirm flow triggers `ConditionalCheckFailedException` (version conflict during concurrent split), enters the retry loop, retries exhaust, then the error-logging path calls `Json.toJsonString(detail)` which fails with the `Optional` serialization error. The original `ConditionalCheckFailedException` is masked.

##### Recommended fix (separate PR)

**Option A** (minimal): Add `@JsonIgnore` to `getCountryISO2Code()` in `LocationAdditionalInfo.java` — matches the original `@DynamoDBIgnore` intent:
```java
@JsonIgnore
public Optional<String> getCountryISO2Code() { ... }
```

**Option B** (comprehensive): Register `Jdk8Module` in `Json.java` — enables `Optional` support globally:
```java
objectMapper.registerModule(new com.fasterxml.jackson.datatype.jdk8.Jdk8Module());
```

Option A is safer and more targeted. Option B is more future-proof but has broader impact.

#### Failure 3: `BookingServiceIntegrationTest.testUnauthorizedCancel`

**Error**: `RejectedExecutionException: Task rejected from ThreadPoolExecutor[pool size = 20, active threads = 20, queued tasks = 60, completed tasks = 4]`

**Root cause**: The `OutboundServiceImpl` thread pool (size 20, queue 60) is saturated from earlier split/confirm test outbound processing. When `testUnauthorizedCancel` runs, it calls `BookingService.pending()` → `OutboundServiceImpl.processOutbound()` which submits a task to the already-full pool. The expected `"not authorized to cancel"` exception is masked by the `RejectedExecutionException`.

**Impact**: This is a **test ordering/resource exhaustion issue** in the integration test suite. The outbound thread pool doesn't drain fast enough between tests when running against live APIs with ~500ms latency per call. This is a known locally-reproducible issue.

**NOT related to date format changes.**

---

## 8. Sonar Code Coverage — MetaDataConverter.java

**Date**: 2026-04-23  
**Sonar Finding**: Insufficient test coverage on `MetaDataConverter.java`  

### Sonar-Reported Gaps

| Line(s) | Issue | Root Cause |
|---------|-------|------------|
| 52 | Not covered | `MetaDataDynamoDbMixIn` abstract class implicit constructor — JaCoCo flags the synthetic `<init>()` bytecode |
| 80 | Partially covered | `if (json != null && !json.isEmpty())` — `json == null` branch never hit |
| 83-85 | Not covered | `catch (JsonProcessingException e)` block — no test with invalid JSON |

### Approach

**No production code changes** — the code is verified and working in QA. Coverage addressed purely through test additions.

For the MixIn (line 52): Since it's an `abstract static class` used only for Jackson annotation overrides, it cannot be instantiated directly. The correct approach is to test the serialization/deserialization behavior the MixIn enables on `ObjectMapper`, which exercises all three annotations indirectly:
- `@JsonFormat(shape = STRING)` → ISO T-separator serialization
- `@JsonDeserialize(using = FlexibleLocalDateTimeDeserializer.class)` → flexible format parsing
- `@JsonIgnoreProperties(ignoreUnknown = true)` → unknown fields ignored

### Files Changed (test-only)

| File | Change |
|------|--------|
| `MetaDataConverterTest.java` | Added `nonStringNonMapAttribute` test (N-type AttributeValue → `s()` returns null → covers line 80 null branch) |
| `MetaDataConverterTest.java` | Added `invalidJsonString` test (`"{invalid json}"` → `JsonProcessingException` → covers lines 83-85 catch block) |
| `MetaDataDynamoDbMixInTest.java` | **New class** — 4 tests exercising MixIn behavior via ObjectMapper with `addMixIn()` |

### MetaDataDynamoDbMixInTest — Test Summary

| Test | Annotation Covered | Verification |
|------|-------------------|--------------|
| `shouldSerializeTimestampWithTSeparator` | `@JsonFormat(shape = STRING)` | JSON output contains `T` separator, not space |
| `shouldDeserializeTimestampWithTSeparator` | `@JsonDeserialize(FlexibleLocalDateTimeDeserializer)` | Parses `"2020-04-14T10:21:53.78"` correctly |
| `shouldDeserializeTimestampWithSpaceSeparator` | `@JsonDeserialize(FlexibleLocalDateTimeDeserializer)` | Parses `"2020-04-14 10:21:53.78"` correctly |
| `shouldIgnoreUnknownProperties` | `@JsonIgnoreProperties(ignoreUnknown = true)` | Unknown field in JSON does not throw |

### Coverage Result

| Metric | Before | After |
|--------|--------|-------|
| Statements | 25/28 | 27/28 |
| Branches | 10/12 | 12/12 |
| Declarations | 7/8 | 7/8 |
| Overall | ~85% | 95.8% |

**Remaining uncovered**: Line 52 — abstract class implicit constructor (`<init>`). This is a JaCoCo limitation: abstract classes generate a synthetic constructor that is never invoked because Jackson MixIns work through annotation introspection, not instantiation. This is an accepted Sonar false positive for MixIn patterns.

### JaCoCo Workaround Options (available if needed)

If Sonar enforcement requires 100%, two options exist:

**Option 1: JaCoCo exclusion filter** — exclude the inner class from coverage in booking `pom.xml`:
```xml
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <configuration>
        <excludes>
            <exclude>**/MetaDataConverter$MetaDataDynamoDbMixIn</exclude>
        </excludes>
    </configuration>
</plugin>
```

**Option 2: Sonar exclusion** — exclude from Sonar coverage reporting via pom properties:
```xml
<sonar.coverage.exclusions>
    **/MetaDataConverter$MetaDataDynamoDbMixIn.class
</sonar.coverage.exclusions>
```

**Recommendation**: Neither exclusion is applied. 95.8% with 12/12 branches is excellent. The uncovered line is a synthetic constructor on an abstract MixIn class — any reviewer would recognize this as a false positive. Adding exclusion config for one implicit constructor would be over-engineering.

---

## 9. Running Code Coverage Locally for Booking Module

### Important: Booking has no JaCoCo Maven plugin configured

Unlike some other modules (e.g., `lambda/bounceback-email`, `shipment`), the `booking/pom.xml` does **not** include `jacoco-maven-plugin`. This means:

- `mvn test` will **not** produce `jacoco.exec` or any coverage report
- `mvn org.jacoco:jacoco-maven-plugin:report` will fail with "missing execution data file"
- Sonar gets coverage data from the CI pipeline (which injects JaCoCo agent externally), not from local Maven builds

### Method 1: VS Code Test Runner (recommended for local dev)

VS Code's "Test Runner for Java" extension (part of the Java Extension Pack) has built-in JaCoCo support. It injects the JaCoCo agent automatically without needing any Maven plugin configuration.

**Steps**:
1. Open VS Code in the `mercury-services` workspace
2. Open the Testing sidebar (flask icon) or press `Ctrl+Shift+;`
3. Find the test class(es) you want to run (e.g., `MetaDataConverterTest`, `MetaDataDynamoDbMixInTest`)
4. Click the **"Run with Coverage"** button (shield icon with play arrow) next to the test class or test method
5. Coverage results appear inline in the editor:
   - Green gutter = covered lines
   - Red gutter = uncovered lines
   - Yellow gutter = partially covered branches
6. The **Test Coverage** panel shows file-level summary (statements, branches, declarations)

**This is how the 95.8% coverage number was obtained in this session.**

### Method 2: Maven CLI with ad-hoc JaCoCo agent injection

If you need a JaCoCo report from the command line without modifying `pom.xml`:

```sh
# Step 1: Run tests with JaCoCo agent (prepare-agent + test + report in one command)
mvn org.jacoco:jacoco-maven-plugin:0.8.12:prepare-agent \
    test \
    org.jacoco:jacoco-maven-plugin:0.8.12:report \
    -pl booking -am \
    -Dtest="com.inttra.mercury.booking.dynamodb.converter.MetaDataConverterTest,com.inttra.mercury.booking.dynamodb.converter.MetaDataDynamoDbMixInTest"
```

**Important**: All three goals (`prepare-agent`, `test`, `report`) must be in a **single** `mvn` invocation. Running them as separate commands will fail because `prepare-agent` sets a JVM arg (`argLine`) that only applies within the same Maven reactor execution. If run separately, `test` won't have the agent attached and `report` won't find `jacoco.exec`.

After the command completes:
- `booking/target/jacoco.exec` — binary execution data
- `booking/target/site/jacoco/index.html` — HTML coverage report (open in browser)
- `booking/target/site/jacoco/jacoco.csv` — CSV for scripted analysis

### Method 3: Add JaCoCo plugin to booking pom.xml (permanent)

If the team wants Maven-integrated coverage for booking (like `bounceback-email`), add to `booking/pom.xml` `<build><plugins>` section:

```xml
<plugin>
    <groupId>org.jacoco</groupId>
    <artifactId>jacoco-maven-plugin</artifactId>
    <version>0.8.12</version>
    <executions>
        <execution>
            <id>prepare-agent</id>
            <goals>
                <goal>prepare-agent</goal>
            </goals>
        </execution>
        <execution>
            <id>report</id>
            <phase>test</phase>
            <goals>
                <goal>report</goal>
            </goals>
            <configuration>
                <outputDirectory>${project.build.directory}/site/jacoco</outputDirectory>
            </configuration>
        </execution>
    </executions>
</plugin>
```

Then simply `mvn test -pl booking -am` will produce coverage reports automatically.

### Filtering coverage to specific classes

To check coverage of a single file (e.g., `MetaDataConverter`):
- **VS Code**: Run coverage on specific test classes, then open the source file — coverage highlights appear inline
- **Maven HTML report**: Open `booking/target/site/jacoco/index.html`, navigate to the package → class
- **Maven CSV**: `grep MetaDataConverter booking/target/site/jacoco/jacoco.csv`
