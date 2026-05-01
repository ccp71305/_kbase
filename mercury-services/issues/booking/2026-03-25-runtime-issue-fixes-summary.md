# Runtime Issue Fixes Summary

**Date:** 2026-03-25 (Updated: 2026-03-26)  
**Ticket:** ION-14382  
**Status:** IMPLEMENTED (Issues 1 & 2 fixed; Issue 3 SUBMITTER fix reverted — pre-existing bug, not related to AWS upgrade)  
**Related:** [2026-03-24-lambda-jar-size-fix-summary.md](2026-03-24-lambda-jar-size-fix-summary.md)  
**Session IDs:** `6790c561ea174275` (initial), `461148258696485b` (verification & undo)  
**Previous Sessions:** `145646203c574b32` (lambda JAR size fix), `dbdbd4a24ab54c33` (root cause analysis)  
**Model:** Claude Opus 4.6

---

## Issues Reported

1. **IndexerHandler Lambda ClassNotFoundException** — `org.eclipse.jetty.io.RuntimeIOException` — **FIXED**
2. **Booking detail 400 Bad Request** — Date deserialization failure for `ContainerType.lastModifiedDateUtc` — **FIXED**
3. **RapidReservation date deserialization check** — Requested investigation — **No issue found**
4. **"Unknown target SUBMITTER"** — `IllegalArgumentException` on booking submission — **Pre-existing bug, fix REVERTED** (not related to AWS upgrade)

---

## Issue 1: IndexerHandler ClassNotFoundException

### Symptom
```
java.lang.NoClassDefFoundError: org/eclipse/jetty/io/RuntimeIOException
    at com.inttra.mercury.booking.lambda.IndexerHandler.<init>(IndexerHandler.java:60)
INIT_REPORT Init Duration: 2332.54 ms  Phase: invoke  Status: error  Error Type: Runtime.BadFunctionCode
```

### Root Cause
`Indexer.java` directly imported and used `org.eclipse.jetty.io.RuntimeIOException` in 3 locations:
- Line 61: `throw new RuntimeIOException("Retry again...Conflict!!!")` (409 conflict)
- Line 64: `throw new RuntimeIOException(e)` (IOException wrapper in `index()`)
- Line 95: `throw new RuntimeIOException(e)` (IOException wrapper in `delete()`)

The lambda JAR shade configuration excluded `org.eclipse.jetty:*` to reduce JAR size. When the Lambda runtime tried to instantiate `IndexerHandler`, it loaded `Indexer` which referenced `RuntimeIOException` — a class that no longer existed in the JAR.

### Fix
Replaced all `org.eclipse.jetty.io.RuntimeIOException` usage with `java.io.UncheckedIOException` (JDK standard library — always available):
- **`Indexer.java`**: Removed Jetty import, added `import java.io.UncheckedIOException`, changed 3 throw sites.  
  Note: `RuntimeIOException(String)` became `new UncheckedIOException(new IOException(message))` since `UncheckedIOException` requires an `IOException` cause.
- **`IndexerUnitTest.java`**: Updated 3 test assertions from `RuntimeIOException.class` to `UncheckedIOException.class`.

### Note on Lambda JAR Size
The Lambda JAR shade exclusions work correctly in CI/CD — the deployed Lambda JAR is smaller as expected. A local build investigation initially suggested the exclusions were ineffective (local JAR showed 324 MB), but this was a **misleading local artifact** — CI/CD does clean builds (`mvn clean`) where the shade plugin dual-execution produces the correct output. The local discrepancy was likely due to stale incremental build artifacts or inspecting the wrong output file.

**Our code fix resolves the ClassNotFoundException regardless**, since `UncheckedIOException` is from the JDK and always available.

---

## Issue 2: Date Deserialization Error (400 Bad Request)

### Symptom
```
GET https://api-alpha.inttra.e2open.com/booking/2011830011
400 Bad Request
{"code":"000200","message":"Cannot deserialize value of type `java.util.Date` from String 
\"2020-12-08T18:07:00.000Z\": expected format \"yyyy-MM-dd HH:mm:ss\"
 at ... ContainerType[\"lastModifiedDateUtc\"]"}
```

### Root Cause
`ContainerType.lastModifiedDateUtc` had `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")` which only accepts that exact format. However, existing records in DynamoDB had dates stored in ISO 8601 format (`2020-12-08T18:07:00.000Z`) because:
1. The `EnrichedAttributesConverter` uses an `ObjectMapper` configured with `WRITE_DATES_AS_TIMESTAMPS=false`, which writes dates in ISO 8601 format.
2. Legacy data or data migrated from the old AWS SDK v1 converter also used ISO dates.

When the booking API reads a `BookingDetail` from DynamoDB with `EnrichedAttributes` containing a `ContainerType` with an ISO-formatted `lastModifiedDateUtc`, Jackson fails to parse it against the strict `@JsonFormat` pattern.

### Fix
Created `FlexibleDateDeserializer.java` — a custom Jackson deserializer that tries multiple date formats:
1. `yyyy-MM-dd HH:mm:ss` (canonical format)
2. `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'` (ISO 8601 with millis)
3. `yyyy-MM-dd'T'HH:mm:ss.SSSZ` (ISO 8601 with timezone offset)
4. `yyyy-MM-dd'T'HH:mm:ss'Z'` (ISO 8601 without millis)
5. `yyyy-MM-dd'T'HH:mm:ssZ` (ISO 8601 with offset, no millis)

Applied to `ContainerType.lastModifiedDateUtc` via:
```java
@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")
@JsonDeserialize(using = FlexibleDateDeserializer.class)
private Date lastModifiedDateUtc;
```

The `@JsonFormat` still controls **serialization** (writes `yyyy-MM-dd HH:mm:ss`), while `@JsonDeserialize` controls **deserialization** (accepts multiple formats).

### RapidReservation Analysis
No similar issue found. RapidReservation uses `OffsetDateTime` via the `Audit` class with `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSSZ")`, which is consistent with ISO 8601. No `java.util.Date` fields with strict `@JsonFormat` exist in RapidReservation models.

### Other Models Checked
- `PackageType.lastModifiedDateUtc`: No `@JsonFormat` annotation — uses Jackson defaults (flexible). No fix needed.
- `BookingDetailReport` dates: Uses `LocalDateTime`, computed from code not from DynamoDB. Safe.
- `Token`, `Alias`, `Address`, `ParticipantAddOn` etc.: All use `@JsonFormat("yyyy-MM-dd HH:mm:ss")` but receive data from Network REST APIs which consistently use that format. These don't pass through DynamoDB. No fix needed.

---

## Issue 3: "Unknown target SUBMITTER" — Pre-existing Bug (NOT FIXED in this deployment)

### Status: REVERTED
The SUBMITTER fix was initially implemented but **reverted on 2026-03-26** because this is a pre-existing bug (6+ years old, since November 2019) that is NOT caused by our AWS SDK upgrade. It will be addressed in a separate ticket.

### Root Cause — Pre-existing Bug (NOT caused by our deployment)

**Git history proves SUBMITTER was NEVER handled in the switch:**

| Date | Commit | Author | What happened |
|------|--------|--------|---------------|
| 2019-06-20 | `90ae6c07de` | pgi001 | Original switch: BOOKER, PLACE_OF_RECEIPT, CHANNEL, PLACE_OF_DELIVERY only |
| 2019-11-04 | `912aa30430d7` | hemanthvakkkapatla | `TargetType.SUBMITTER` enum value added ("preference Evaluation") |
| 2019-11-05 | `f4a5e48b3a3e` | hemanthvakkkapatla | "SubmitterLocationBug" — added `BOOKERS_LOCATION` + `SUBMITTER_LOCATION` to switch, but **NOT** `SUBMITTER` |
| 2025-02 | `97f216e9b4b0` | Ananya Antony | Added `OOG_HEIGHT/WIDTH/LENGTH` — still no SUBMITTER |

The `SUBMITTER` enum value has existed since November 2019, but the switch case implementation was **never added in 6+ years**.

### Why It Fails For One Carrier But Not Others

This is **not** a carrier-specific code path — it's about **carrier rule configuration**:
- Carrier rules (optional validations) are stored per carrier in DynamoDB  
- Each carrier configures their own rules with specific `TargetType` conditions
- **Most carriers** use conditions like `BOOKER`, `CHANNEL`, `PLACE_OF_RECEIPT` — these ARE handled in the switch
- **Only the specific carrier** that configured a rule with `TargetType.SUBMITTER` triggers this error
- The error was always latent for ANY carrier with SUBMITTER rules — it predates our AWS upgrade work

### Exception Flow
```
ValidationContext.isActivated() → switch default → IllegalArgumentException("Unknown target SUBMITTER")
  ↓ (REST API path)
BookingApplication.getExceptionMappers() → BookingExceptionMapper<IllegalArgumentException>
  → genericToResponse(e, CODE_000200, HttpStatus.BAD_REQUEST_400)
  → HTTP 400 {"code":"000200","message":"Unknown target SUBMITTER"}
```

### Open Question
**TODO**: Determine whether this carrier recently added/changed their SUBMITTER rules, or if this error has been silently occurring since the rule was configured. Check carrier rule DynamoDB table for rule creation/modification dates.

### Fix — REVERTED
The fix was initially implemented (adding `SUBMITTER` case to `isActivated()`) but has been **reverted** since this is a pre-existing bug unrelated to the AWS SDK upgrade. The SUBMITTER case and 4 associated tests were removed on 2026-03-26.

**Recommendation**: Address in a separate Jira ticket. The fix approach (comparing `actor.getCompanyId()` against condition values) was validated but should be tracked separately.

### Risk: Other Unhandled TargetTypes
Many other `TargetType` enum values also have no case in the switch:
- `PORT_OF_DISCHARGE`, `PORT_OF_LOAD`, `PARTY_ROLE`, `CONTEXT_CODE`, `IS_DGS_BOOKING`
- `BOOKING_SOURCE`, `TRANSACTION_PARTY`, `TRANSACTION_PARTY_WO_4F`
- `BOOKING_ORIGINATED_CHANNEL`, `CARRIER`, `REQUESTER`, `IDP_PROVIDER`
- `EVENT_CODE`, `BOOKING_OFFICE`, `BOOKING_STATE`

These will all throw `IllegalArgumentException` if any carrier configures rules using them. **This is the same latent bug pattern** — enum values exist but switch handling was never added.

---

## Files Changed

| File | Change |
|------|--------|
| `booking/src/main/java/.../elasticsearch/Indexer.java` | Replaced `RuntimeIOException` with `UncheckedIOException` |
| `booking/src/main/java/.../referencedata/model/ContainerType.java` | Added `@JsonDeserialize(using = FlexibleDateDeserializer.class)` |
| `booking/src/main/java/.../referencedata/model/FlexibleDateDeserializer.java` | **NEW** — Multi-format date deserializer |
| `booking/src/test/.../elasticsearch/IndexerUnitTest.java` | Updated 3 tests for `UncheckedIOException` |
| `booking/src/test/.../elasticsearch/IndexerJettyFreeTest.java` | **NEW** — 2 tests verifying no Jetty dependency |
| `booking/src/test/.../referencedata/model/FlexibleDateDeserializerTest.java` | **NEW** — 9 tests for date format handling |
| `booking/src/test/.../outbound/services/OutboundServiceImplTest.java` | Fixed pre-existing `EmailSenderConfig` → `BookingEmailConfig` compilation error |

**Note:** `ValidationContext.java` and `ValidationContextTest.java` SUBMITTER changes were reverted on 2026-03-26.

## Build Verification

```
mvn clean verify -pl booking -am → BUILD SUCCESS (2026-03-26)
Surefire (unit tests):
  JUnit5:  1837 tests, 0 failures, 0 errors, 1 skipped
  TestNG:   913 tests, 0 failures, 0 errors, 9 skipped  
Failsafe (integration tests):
  DynamoDB IT (JUnit5): 138 tests, 0 failures, 0 errors
  Flow/Service IT (TestNG): 149 tests, 0 failures, 0 errors
Total: 3037 tests, 0 failures, 0 errors
```

### JAR Verification (2026-03-26 clean build)
| JAR | Size | Purpose |
|-----|------|---------|
| `booking-1.0.jar` | 134 MB | Main server (Dropwizard) shaded JAR |
| `booking-lambdas-1.0.jar` | 75 MB | Lambda handlers (IndexerHandler, S3ArchiveHandler) |
| `original-booking-1.0.jar` | 1.8 MB | Unshaded classes only |

**Fixes verified in `booking-lambdas-1.0.jar`:**
- `Indexer.class`: Uses `java.io.UncheckedIOException` (no Jetty references)
- `FlexibleDateDeserializer.class`: Present in JAR
- `ContainerType.class`: Has `@JsonDeserialize(using=FlexibleDateDeserializer.class)` annotation

**Fixes verified in `booking-1.0.jar`:**
- `FlexibleDateDeserializer.class`: Present
- `ContainerType.class`: Has `@JsonDeserialize` annotation

---

## Analysis: Why These Errors Happened and How to Prevent Them

### Why No Tests Caught These Issues

1. **Jetty RuntimeIOException (Issue 1)**: The unit tests for `Indexer` ran with Jetty on the classpath (full test dependencies). The Lambda JAR exclusion of Jetty was a _deployment-time_ issue — no test simulated the Lambda classpath. The instruction "make sure the dependencies included in the new shaded jar for the 2 lambdas are sufficient" was followed for verifying that required classes were present, but not for verifying that _code references to excluded classes_ were also removed. The verification checked 31 essential class names in the JAR but did not scan the source code for imports of excluded packages.

2. **Date Deserialization (Issue 2)**: Tests used `java.util.Date` objects directly or formatted dates as `yyyy-MM-dd HH:mm:ss`. No test deserialized a `ContainerType` from an ISO 8601 date string, because all test data used the canonical format. The actual DynamoDB data was written by the `EnrichedAttributesConverter` which uses a different ObjectMapper configuration. The disconnect between "how data is written" and "how data is read" was not tested end-to-end.

### Recommendations to Prevent Similar Issues

1. **Lambda Classpath Verification Test**: Create a test that loads the Lambda handler classes using a classloader restricted to only the classes in the lambda JAR. This would catch `ClassNotFoundException` at build time. Alternatively, after building the lambda JAR, run a post-build check that scans all classes in the JAR for unresolved class references.

2. **Source Code Import Scanner**: Before building the lambda JAR, scan all classes reachable from Lambda handlers for imports that reference excluded packages (e.g., `org.eclipse.jetty.*`). Flag these as errors.

3. **DynamoDB Round-Trip Tests**: For any model stored in DynamoDB, test the full write→read cycle using the same converters. Write the object, read it back, and verify all fields. This would have caught the date format mismatch.

4. **Exhaustive Switch Coverage**: Consider replacing the `default: throw` pattern with explicit handling (even if just `return true` or `return false`) for all enum values, or use IDE/linter settings to warn on non-exhaustive switches.

5. **Agent Instruction Improvement**: The instruction "make sure the dependencies included in the new shaded jar for the 2 lambdas are sufficient" should be expanded to: "make sure (a) all classes referenced by Lambda handler code are present in the JAR, AND (b) Lambda handler code does NOT reference any classes from excluded packages. Scan all transitive imports from Lambda entry points."

---

## Lambda Deployment Verification

To verify the IndexerHandler will work after deployment:

1. The code fix removes the Jetty dependency entirely — `UncheckedIOException` is `java.io.*` (JDK standard library), always available.
2. The `IndexerJettyFreeTest` confirms the `Indexer` class loads and works without Jetty.
3. The `IndexerUnitTest` confirms the exception wrapping behavior is correct.
4. No additional Lambda-specific testing infrastructure is needed for this fix.

For the date deserialization fix:
1. The `FlexibleDateDeserializerTest` covers both old and new date formats.
2. Existing `BookingDetailDaoIT` integration tests verify the full DynamoDB write/read cycle.

---

## Status (2026-03-26)

- **Issue 1 (Jetty ClassNotFoundException)**: FIXED — verified in clean build JAR
- **Issue 2 (Date Deserialization 400)**: FIXED — verified in clean build JAR
- **Issue 3 (SUBMITTER)**: Fix REVERTED — pre-existing bug, to be addressed separately
- **Build**: `mvn clean verify -pl booking -am` → BUILD SUCCESS, all 3037 tests pass
- **Ready for deployment**: Commit (minus SUBMITTER changes), push, and deploy via Jenkins

---

## Detailed Test Categorization (from `mvn clean verify -pl booking -am` on 2026-03-26)

### Test Execution Summary

| Phase | Plugin | Framework | Tests | Passed | Failed | Skipped |
|-------|--------|-----------|-------|--------|--------|---------|
| Surefire (unit tests) | maven-surefire-plugin 3.5.2 | JUnit5 (JUnitPlatform) | 1837 | 1836 | 0 | 1 |
| Surefire (unit tests) | maven-surefire-plugin 3.5.2 | TestNG | 913 | 904 | 0 | 9 |
| Failsafe (DynamoDB IT) | maven-failsafe-plugin 3.5.2 | JUnit5 (JUnitPlatform) | 138 | 138 | 0 | 0 |
| Failsafe (Flow/Service IT) | maven-failsafe-plugin 3.5.2 | TestNG | 149 | 149 | 0 | 0 |
| **Total** | | | **3037** | **3027** | **0** | **10** |

### Configuration
- Surefire excludes groups: `integration,canary` (unit tests only)
- Failsafe includes groups: `integration` (integration tests)
- Failsafe includes: `**/*Test.java`, `**/*IT.java`, `**/FlowTests.java`
- Failsafe excludes: `**/FlowTest.java` (discovered dynamically by `FlowTests::factory`)

### Phase 1: Surefire JUnit5 Unit Tests (1837 tests)

| # | Test Class | Tests | Pass | Fail | Skip |
|---|-----------|-------|------|------|------|
| 1 | BookingApplicationTest | 2 | 2 | 0 | 0 |
| 2 | carrierrule.OptionalValidationServiceCacheTest | 4 | 4 | 0 | 0 |
| 3 | carrierrule.OptionalValidationServiceTest | 5 | 5 | 0 | 0 |
| 4 | carrierspotrates.dao.SpotRatesDaoTest | 3 | 3 | 0 | 0 |
| 5 | carrierspotrates.dao.SpotRatesToInttraRefDaoTest | 3 | 3 | 0 | 0 |
| 6 | carrierspotrates.mapping.MaerskResponseToCanonicalTest | 6 | 6 | 0 | 0 |
| 7 | carrierspotrates.resource.CarrierSpotRatesResourceTest | 13 | 13 | 0 | 0 |
| 8 | carrierspotrates.service.CarrierSpotRatesServiceTest | 13 | 13 | 0 | 0 |
| 9 | carrierspotrates.service.MaerskApiClientTest | 6 | 6 | 0 | 0 |
| 10 | common.AWSUtilTest | 4 | 4 | 0 | 0 |
| 11 | common.event.EventGeneratorTest | 4 | 4 | 0 | 0 |
| 12 | common.event.EventLoggerTest | 4 | 4 | 0 | 0 |
| 13 | common.event.EventTest | 7 | 7 | 0 | 0 |
| 14 | common.event.RandomGeneratorTest | 5 | 5 | 0 | 0 |
| 15 | common.event.SNSEventPublisherTest | 2 | 2 | 0 | 0 |
| 16 | common.listener.SQSListenerTest (4 nested classes) | 13 | 13 | 0 | 0 |
| 17 | common.messaging.SNSClientTest$SendMessageTests | 6 | 6 | 0 | 0 |
| 18 | common.messaging.SQSClientTest (3 nested classes) | 11 | 11 | 0 | 0 |
| 19 | common.MessagingExceptionTest | 4 | 4 | 0 | 0 |
| 20 | common.s3.S3WorkspaceServiceTest (4 nested classes) | 15 | 15 | 0 | 0 |
| 21 | common.s3.UnableToReadS3ObjectExceptionTest | 2 | 2 | 0 | 0 |
| 22 | config.AppianWayConfigTest | 3 | 3 | 0 | 0 |
| 23 | config.BookingAppLifecycleListenerTest | 5 | 5 | 0 | 0 |
| 24 | config.BookingConfigTest | 7 | 7 | 0 | 0 |
| 25 | config.BookingMessagingModuleTest (2 nested classes) | 5 | 5 | 0 | 0 |
| 26 | config.ElasticsearchConfigTest | 6 | 6 | 0 | 0 |
| 27 | config.SpotRateConfigTest | 8 | 8 | 0 | 0 |
| 28 | dao.BookingDetailDaoQueryTest | 7 | 7 | 0 | 0 |
| 29 | dgs.service.DGSServiceImplTest | 6 | 6 | 0 | 0 |
| 30 | dgs.validation.DGSApiValidationsTest | 19 | 19 | 0 | 0 |
| 31 | dgs.validation.DGSRulesFactoryTest | 13 | 13 | 0 | 0 |
| 32 | dgs.validation.cargo.DGSEndOfHoldingRuleTest | 32 | 32 | 0 | 0 |
| 33 | dgs.validation.cargo.DGSExplosiveCargoRuleTest | 29 | 29 | 0 | 0 |
| 34 | dgs.validation.cargo.DGSFireworksClassificationTest | 28 | 28 | 0 | 0 |
| 35 | dgs.validation.cargo.DGSMedDangerPackingGrpFlashTempRuleTest | 35 | 35 | 0 | 0 |
| 36 | dgs.validation.cargo.DGSMinorDangerPackingGrpFlashTempRuleTest | 29 | 29 | 0 | 0 |
| 37 | dgs.validation.cargo.DGSMinorDangerPackingGrpFlashTempViscousRuleTest | 30 | 30 | 0 | 0 |
| 38 | dgs.validation.cargo.DGSTechnicalNameReqdRuleTest | 17 | 17 | 0 | 0 |
| 39 | dgs.validation.equipment.DGSEquipmentFumigationRuleTest | 22 | 22 | 0 | 0 |
| 40 | dynamodb.ContractAttributeConverterTest (4 nested classes) | 15 | 15 | 0 | 0 |
| 41 | dynamodb.ListOfChargeTypeConverterTest | 2 | 2 | 0 | 0 |
| 42 | dynamodb.LocalDateTimeTypeConverterTest | 2 | 2 | 0 | 0 |
| 43 | dynamodb.SpotRatesConverterTest | 5 | 5 | 0 | 0 |
| 44 | dynamodb.converter.AuditAttributeConverterTest (5 nested) | 14 | 14 | 0 | 0 |
| 45 | dynamodb.converter.ConditionListAttributeConverterTest (5 nested) | 11 | 11 | 0 | 0 |
| 46 | dynamodb.converter.EnrichedAttributesConverterTest (4 nested) | 10 | 10 | 0 | 0 |
| 47 | dynamodb.converter.LegacyMapConverterTest (3 nested) | 9 | 9 | 0 | 0 |
| 48 | dynamodb.converter.MetaDataConverterTest (5 nested) | 12 | 12 | 0 | 0 |
| 49 | dynamodb.converter.RangeAttributeConverterTest (5 nested) | 11 | 11 | 0 | 0 |
| 50 | dynamodb.converter.SpotRatesAttributeConverterTest (4 nested) | 14 | 14 | 0 | 0 |
| 51 | elasticsearch.CoordinateTest | 8 | 8 | 0 | 0 |
| 52 | elasticsearch.CreateIndexTest | 10 | 10 | 0 | 0 |
| 53 | elasticsearch.DeleteIndexTest | 3 | 3 | 0 | 0 |
| 54 | elasticsearch.ExistsTest | 4 | 4 | 0 | 0 |
| 55 | elasticsearch.FilterTest | 6 | 6 | 0 | 0 |
| 56 | elasticsearch.GeoDistanceSerializerTest | 2 | 2 | 0 | 0 |
| 57 | elasticsearch.GeoDistanceTest | 3 | 3 | 0 | 0 |
| 58 | elasticsearch.HasChildSerializerTest | 4 | 4 | 0 | 0 |
| 59 | elasticsearch.HasChildTest | 4 | 4 | 0 | 0 |
| 60 | elasticsearch.IndexedLocationTest | 2 | 2 | 0 | 0 |
| 61 | **elasticsearch.IndexerJettyFreeTest** ★ | 2 | 2 | 0 | 0 |
| 62 | **elasticsearch.IndexerUnitTest** ★ | 7 | 7 | 0 | 0 |
| 63 | elasticsearch.MatchAllSerializerTest | 3 | 3 | 0 | 0 |
| 64 | elasticsearch.MatchAllTest | 4 | 4 | 0 | 0 |
| 65 | elasticsearch.MultiMatchTest | 1 | 1 | 0 | 0 |
| 66 | elasticsearch.NestedTest | 4 | 4 | 0 | 0 |
| 67 | elasticsearch.PrefixSerializerTest | 3 | 3 | 0 | 0 |
| 68 | elasticsearch.PrefixTest | 7 | 7 | 0 | 0 |
| 69 | elasticsearch.QuerySerializerTest | 5 | 5 | 0 | 0 |
| 70 | elasticsearch.QueryTest | 10 | 10 | 0 | 0 |
| 71 | elasticsearch.RangeTest | 8 | 8 | 0 | 0 |
| 72 | elasticsearch.ScriptSortSpecTest | 5 | 5 | 0 | 0 |
| 73 | elasticsearch.ScriptTest | 5 | 5 | 0 | 0 |
| 74 | elasticsearch.SimpleQueryStringSerializerTest | 3 | 3 | 0 | 0 |
| 75 | elasticsearch.SortSerializerTest | 4 | 4 | 0 | 0 |
| 76 | elasticsearch.SortTest | 7 | 7 | 0 | 0 |
| 77 | elasticsearch.SuggestOptionTest | 1 | 1 | 0 | 0 |
| 78 | elasticsearch.SuggestResultTest | 6 | 6 | 0 | 0 |
| 79 | elasticsearch.UpdateByQueryTest | 6 | 6 | 0 | 0 |
| 80 | elasticsearch.UpdateTest | 6 | 6 | 0 | 0 |
| 81 | enrichment.LocationEnrichmentTest | 4 | 4 | 0 | 0 |
| 82 | exceptions.InternalExceptionTest | 7 | 7 | 0 | 0 |
| 83 | exceptions.StructuralValidationExceptionTest | 5 | 5 | 0 | 0 |
| 84 | exceptions.TransformationExceptionTest | 8 | 8 | 0 | 0 |
| 85 | externalwrapper.ExternalCallSettingsTest | 4 | 4 | 0 | 0 |
| 86 | externalwrapper.ExternalCallWrapperFactoryTest | 7 | 7 | 0 | 0 |
| 87 | externalwrapper.ExternalCallWrapperTest | 3 | 3 | 0 | 0 |
| 88 | externalwrapper.MixedStopStrategyTest | 6 | 6 | 0 | 0 |
| 89 | externalwrapper.ThrowablesTest | 6 | 6 | 0 | 0 |
| 90 | externalwrapper.exception.ExternalCallExecutionExceptionTest | 3 | 3 | 0 | 0 |
| 91 | externalwrapper.exception.RecoverableExceptionTest | 3 | 3 | 0 | 0 |
| 92 | externalwrapper.exception.UnrecoverableAWSExceptionTest | 3 | 3 | 0 | 0 |
| 93 | externalwrapper.guice.ExternalCallAnnotationListenerTest | 4 | 4 | 0 | 0 |
| 94 | externalwrapper.guice.ExternalWrapperModuleTest | 2 | 2 | 0 | 0 |
| 95 | externalwrapper.guice.RetriableMethodInterceptorTest | 5 | 5 | 0 | 0 |
| 96 | externalwrapper.guice.annotation.ExternalCallTest | 11 | 11 | 0 | 0 |
| 97 | externalwrapper.hystrix.GenericHystrixCommandWithCallableTest | 6 | 6 | 0 | 0 |
| 98 | externalwrapper.hystrix.GenericHystrixCommandWithInvocationTest | 6 | 6 | 0 | 0 |
| 99 | inbound.MigrationLogicTest | 6 | 6 | 0 | 0 |
| 100 | inbound.NonInttraBookingValidatorTest | 1 | 1 | 0 | 0 |
| 101 | inbound.confirmation.ConfirmPendingMessageTest | 36 | 36 | 0 | 0 |
| 102 | inbound.confirmation.validation.CargoValidationsTest | 28 | 28 | 0 | 0 |
| 103 | inbound.confirmation.validation.HeaderLocationValidationsTest | 6 | 6 | 0 | 0 |
| 104 | inbound.confirmation.validation.NumberDeserializerTest | 7 | 7 | 0 | 0 |
| 105 | inbound.decline.DeclineReplaceMessageTest | 39 | 39 | 0 | 0 |
| 106 | inbound.decline.validation.DeclineMessageTest | 2 | 2 | 0 | 0 |
| 107 | inbound.decline.validation.HeaderValidationsTest | 4 | 4 | 0 | 0 |
| 108 | lambda.TrackAndTraceServiceTest | 10 | 10 | 0 | 0 |
| 109 | model.BookingDetailTest | 1 | 1 | 0 | 0 |
| 110 | model.Common.Artifacts.AddressTest | 9 | 9 | 0 | 0 |
| 111 | model.Common.Artifacts.ContactTest | 1 | 1 | 0 | 0 |
| 112 | model.INTTRACommon.Types.SegregationGroupTest | 3 | 3 | 0 | 0 |
| 113 | model.request.artifacts.BRTransactionPartyTest | 5 | 5 | 0 | 0 |
| 114 | model.request.validation.CargoValidationsTest | 86 | 86 | 0 | 0 |
| 115 | networkservices.alias.ParticipantAliasServiceImplTest | 4 | 4 | 0 | 0 |
| 116 | networkservices.blacklistemail.BlacklistEmailServiceTest | 1 | 1 | 0 | 0 |
| 117 | networkservices.connections.ConnectionsServiceTest | 2 | 2 | 0 | 0 |
| 118 | networkservices.geography.GeographyServiceCacheTest | 22 | 22 | 0 | 0 |
| 119 | networkservices.geography.GeographyServiceImplTest | 8 | 8 | 0 | 0 |
| 120 | networkservices.integrationprofile.IntegrationProfileAttributeTest | 4 | 4 | 0 | 0 |
| 121 | networkservices.integrationprofile.IntegrationProfileRequestParamsTest | 4 | 4 | 0 | 0 |
| 122 | networkservices.integrationprofile.IntegrationProfileServiceTest | 1 | 1 | 0 | 0 |
| 123 | networkservices.integrationprofile.IntegrationProfileTest | 6 | 6 | 0 | 0 |
| 124 | networkservices.integrationprofileformat.IntegrationProfileFormatAttributeTest | 3 | 3 | 0 | 0 |
| 125 | networkservices.integrationprofileformat.IntegrationProfileFormatServiceImplTest | 4 | 4 | 0 | 0 |
| 126 | networkservices.integrationprofileformat.IntegrationProfileFormatTest | 4 | 4 | 0 | 0 |
| 127 | networkservices.NetworkServiceClientTest | 4 | 4 | 0 | 0 |
| 128 | networkservices.NetworkServicesExceptionTest | 4 | 4 | 0 | 0 |
| 129 | networkservices.NoDataFoundExceptionTest | 2 | 2 | 0 | 0 |
| 130 | networkservices.participant.NetworkParticipantQueryTest | 1 | 1 | 0 | 0 |
| 131 | networkservices.participant.NetworkParticipantServiceCacheTest | 13 | 13 | 0 | 0 |
| 132 | networkservices.participant.NetworkParticipantServiceTest | 9 | 9 | 0 | 0 |
| 133 | networkservices.participant.SubmitterPartyValidatorTest | 8 | 8 | 0 | 0 |
| 134 | networkservices.participantaddon.ParticipantAddOnServiceCacheImplTest | 20 | 20 | 0 | 0 |
| 135 | networkservices.participantaddon.ParticipantAddOnServiceImplTest | 16 | 16 | 0 | 0 |
| 136 | networkservices.partnerships.PartnershipServiceImplTest | 3 | 3 | 0 | 0 |
| 137 | **networkservices.referencedata.model.FlexibleDateDeserializerTest** ★ | 9 | 9 | 0 | 0 |
| 138 | networkservices.referencedata.PackageTypeQueryTest | 6 | 6 | 0 | 0 |
| 139 | networkservices.referencedata.ReferenceDataServiceTest | 5 | 5 | 0 | 0 |
| 140 | networkservices.subscription.model.PreferenceBasedEnhancementsTest | 12 | 12 | 0 | 0 |
| 141 | networkservices.subscription.SubscriptionServiceCacheTest | 7 | 7 | 0 | 0 |
| 142 | networkservices.subscription.SubscriptionServiceTest | 3 | 3 | 0 | 0 |
| 143 | networkservices.userservice.UserServiceCacheImplTest | 8 | 8 | 0 | 0 |
| 144 | networkservices.userservice.UserServiceImplTest | 5 | 5 | 0 | 0 |
| 145 | networkservices.WebhookServiceTest | 3 | 3 | 0 | 0 |
| 146 | outbound.custom.DarigoldCustomizationsTest | 21 | 21 | 0 | 0 |
| 147 | outbound.diffGenerator.CommonDiffTest | 5 | 5 | 0 | 0 |
| 148 | outbound.diffGenerator.TransportLegDiffTest | 4 | 4 | 0 | 0 |
| 149 | outbound.diffGenerator.UtilTest | 9 | 9 | 0 | 0 |
| 150 | outbound.email.converter.ConfirmPendingEmailVariablesConverterTest | 11 | 11 | 0 | 0 |
| 151 | outbound.email.converter.RequestAmendEmailVariablesConverterTest | 14 | 14 | 0 | 0 |
| 152 | outbound.email.LegalTermsEmailTest | 15 | 15 | 0 | 0 |
| 153 | outbound.email.OutBoundEmailSenderTest | 42 | 41 | 0 | 1 |
| 154 | outbound.email.subject.ErrorEmailSubjectGeneratorTest | 6 | 6 | 0 | 0 |
| 155 | outbound.enrichment.EquipmentEnrichmentTest | 4 | 4 | 0 | 0 |
| 156 | outbound.model.MultiVersionAttributesTest | 28 | 28 | 0 | 0 |
| 157 | outbound.resources.OutboundResourceTest | 6 | 6 | 0 | 0 |
| 158 | outbound.services.CustomerLoadReferenceSupplementationTest | 68 | 68 | 0 | 0 |
| 159 | outbound.services.DGSPSNPreferenceTest | 29 | 29 | 0 | 0 |
| 160 | outbound.services.LegalTermsTest | 47 | 47 | 0 | 0 |
| 161 | **outbound.services.OutboundServiceImplTest** ★ | 8 | 8 | 0 | 0 |
| 162 | outbound.services.ServiceHelperTest | 24 | 24 | 0 | 0 |
| 163 | outbound.services.SubscriptionPreferenceProcessorTest | 3 | 3 | 0 | 0 |
| 164 | outbound.services.WatermillServiceTest | 5 | 5 | 0 | 0 |
| 165 | preferences.PreferenceEvaluatorTest | 3 | 3 | 0 | 0 |
| 166 | preferences.SpotRatePreferenceTest | 8 | 8 | 0 | 0 |
| 167 | rapidreservation.persistence.RapidReservationDaoTest | 3 | 3 | 0 | 0 |
| 168 | rapidreservation.resource.RapidReservationResourceTest | 5 | 5 | 0 | 0 |
| 169 | reporting.BookingDetailReportTest | 3 | 3 | 0 | 0 |
| 170 | resources.BookingExceptionMapperTest | 2 | 2 | 0 | 0 |
| 171 | resources.BookingModelConverterTest | 6 | 6 | 0 | 0 |
| 172 | resources.BookingResourceUtilTest | 9 | 9 | 0 | 0 |
| 173 | resources.BookingResponseTest | 4 | 4 | 0 | 0 |
| 174 | resources.CarrierBookingResourceTest | 8 | 8 | 0 | 0 |
| 175 | resources.CustomerBookingResourceTest | 18 | 18 | 0 | 0 |
| 176 | resources.DangerousGoodsResourceTest | 2 | 2 | 0 | 0 |
| 177 | resources.SearchResponseSerializerTest | 3 | 3 | 0 | 0 |
| 178 | resources.SearchResponseTest | 2 | 2 | 0 | 0 |
| 179 | resources.SearchResultSummaryEntryTest | 4 | 4 | 0 | 0 |
| 180 | service.BookingCodedPartiesTest | 5 | 5 | 0 | 0 |
| 181 | service.BookingEventRelayTest | 4 | 4 | 0 | 0 |
| 182 | service.BookingReinstatementServiceTest | 7 | 7 | 0 | 0 |
| 183 | template.persistence.TemplateSummaryDaoTest | 5 | 5 | 0 | 0 |
| 184 | template.TemplateResourceTest | 5 | 5 | 0 | 0 |
| 185 | util.BookingControlTotalsCalculatorTest | 40 | 40 | 0 | 0 |
| 186 | util.BookingServiceUtilTest | 14 | 14 | 0 | 0 |
| 187 | util.CappedExponentialBackOffTest | 2 | 2 | 0 | 0 |
| 188 | util.DoubleLengthValidatorTest | 2 | 2 | 0 | 0 |
| 189 | util.JsonTest | 6 | 6 | 0 | 0 |
| 190 | util.MetadataTest | 7 | 7 | 0 | 0 |
| 191 | util.SequenceIdTest | 11 | 11 | 0 | 0 |
| 192 | validation.CarrierValidationsTest | 45 | 45 | 0 | 0 |
| 193 | validation.DateValidationsTest | 5 | 5 | 0 | 0 |
| 194 | validation.DimensionValidationsTest | 4 | 4 | 0 | 0 |
| 195 | validation.InttraValidationsTest | 6 | 6 | 0 | 0 |
| 196 | validation.MoveTypeValidationsTest | 1 | 1 | 0 | 0 |
| 197 | validation.ReferenceValidationsTest | 5 | 5 | 0 | 0 |
| 198 | validation.RequestAmendDocumentValidationsTest | 7 | 7 | 0 | 0 |
| 199 | validation.ValidationHelperTest | 3 | 3 | 0 | 0 |
| 200 | validation.ValidationMessageHelperTest | 5 | 5 | 0 | 0 |

★ = Tests new or modified in this change

All class names are under package `com.inttra.mercury.booking.*`

### Phase 2: Surefire TestNG Unit Tests (913 tests, 9 skipped)

| # | Test Class | Tests | Pass | Fail | Skip |
|---|-----------|-------|------|------|------|
| 1 | dynamodb.BookingStateConverterTest | 9 | 9 | 0 | 0 |
| 2 | dynamodb.ContractTypeConverterTest | 15 | 15 | 0 | 0 |
| 3 | dynamodb.OffsetDateTimeTypeConverterTest | 2 | 2 | 0 | 0 |
| 4 | dynamodb.QuantityTypeConverterTest | 2 | 2 | 0 | 0 |
| 5 | elasticsearch.IndexedBookingTest | 2 | 2 | 0 | 0 |
| 6 | elasticsearch.SearcherTest | 1 | 1 | 0 | 0 |
| 7 | elasticsearch.SerializationTest | 3 | 3 | 0 | 0 |
| 8 | inbound.BookingProcessorTaskTest | 39 | 39 | 0 | 0 |
| 9 | inbound.confirmation.validation.EquipmentValidationsTest | 34 | 34 | 0 | 0 |
| 10 | inbound.confirmation.validation.HeaderValidationsTest | 22 | 22 | 0 | 0 |
| 11 | inbound.confirmation.validation.LegValidationsTest | 20 | 20 | 0 | 0 |
| 12 | inbound.confirmation.validation.PartyValidationsTest | 11 | 11 | 0 | 0 |
| 13 | inbound.confirmation.validation.ReferenceValidationsTest | 8 | 8 | 0 | 0 |
| 14 | inbound.decline.validation.CommentValidationsTest | 4 | 4 | 0 | 0 |
| 15 | lambda.HandlerSupportTest | 9 | 9 | 0 | 0 |
| 16 | lambda.IndexerHandlerTest | 6 | 6 | 0 | 0 |
| 17 | lambda.LongDateDeserializerTest | 2 | 2 | 0 | 0 |
| 18 | lambda.RetryTest | 1 | 1 | 0 | 0 |
| 19 | lambda.S3ArchiveHandlerTest | 6 | 6 | 0 | 0 |
| 20 | model.BookingStateTest | 19 | 19 | 0 | 0 |
| 21 | model.BookingTest | 34 | 34 | 0 | 0 |
| 22 | model.Common.Artifacts.CountryTest | 1 | 1 | 0 | 0 |
| 23 | model.Common.Artifacts.HaulagePointTest | 3 | 3 | 0 | 0 |
| 24 | model.INTTRACommon.Artifacts.LocationTest | 2 | 2 | 0 | 0 |
| 25 | model.JsonSchemaTest | 4 | 4 | 0 | 0 |
| 26 | model.request.validation.EquipmentValidationsTest | 34 | 34 | 0 | 0 |
| 27 | model.request.validation.LocationValidationsTest | 13 | 13 | 0 | 0 |
| 28 | networkservices.auth.AuthClientStubTest | 1 | 0 | 0 | 1 |
| 29 | networkservices.geography.GeographyServiceStubTest | 4 | 0 | 0 | 4 |
| 30 | networkservices.NetworkServiceClientIntegrationTest | 2 | 0 | 0 | 2 |
| 31 | networkservices.referencedata.ReferenceDataServiceCacheImplTest | 8 | 8 | 0 | 0 |
| 32 | networkservices.subscription.SubscriptionServiceImplIntegrationTest | 1 | 1 | 0 | 0 |
| 33 | outbound.custom.CustomizationHandlerTest | 10 | 10 | 0 | 0 |
| 34 | outbound.custom.EdiCustomizationsTest | 41 | 41 | 0 | 0 |
| 35 | outbound.custom.TransportLegCustomizationTest | 5 | 5 | 0 | 0 |
| 36 | outbound.diffGenerator.DiffGeneratorTest | 14 | 14 | 0 | 0 |
| 37 | outbound.enrichment.LocationEnrichmentTest | 6 | 6 | 0 | 0 |
| 38 | outbound.enrichment.PackageEnrichmentTest | 7 | 7 | 0 | 0 |
| 39 | outbound.enrichment.PartyEnrichmentTest | 11 | 11 | 0 | 0 |
| 40 | outbound.services.EnrichmentServiceTest | 1 | 1 | 0 | 0 |
| 41 | outbound.services.OutboundServiceAddnlTest | 14 | 14 | 0 | 0 |
| 42 | outbound.services.OutboundServiceTest | 40 | 40 | 0 | 0 |
| 43 | outbound.services.PartyAddressGeneralCommentsFormatterTest | 48 | 48 | 0 | 0 |
| 44 | outbound.services.SubscriptionConditionEvaluatorTest | 14 | 14 | 0 | 0 |
| 45 | outbound.services.SupplementationUtilTest | 4 | 4 | 0 | 0 |
| 46 | outbound.services.TransformerServiceTest | 1 | 1 | 0 | 0 |
| 47 | rapidreservation.service.RapidReservationServiceTest | 18 | 18 | 0 | 0 |
| 48 | resources.BookingResourceTest | 1 | 1 | 0 | 0 |
| 49 | resources.SearchResourceTest | 12 | 12 | 0 | 0 |
| 50 | service.BookingAuthorizerTest | 24 | 24 | 0 | 0 |
| 51 | service.BookingLocatorTest | 25 | 25 | 0 | 0 |
| 52 | service.BookingServiceTest | 54 | 54 | 0 | 0 |
| 53 | service.PartyLocatorTest | 8 | 8 | 0 | 0 |
| 54 | service.ValidationServiceTest | 14 | 14 | 0 | 0 |
| 55 | template.service.TemplateServiceTest | 8 | 8 | 0 | 0 |
| 56 | util.BackwardCompatibilityUtilTest | 9 | 9 | 0 | 0 |
| 57 | util.FlexibleLocalDateTimeDeserializerTest | 2 | 2 | 0 | 0 |
| 58 | util.IdGeneratorTest | 3 | 3 | 0 | 0 |
| 59 | util.MessageSupportTest | 7 | 7 | 0 | 0 |
| 60 | validation.BookerValidationsTest | 10 | 10 | 0 | 0 |
| 61 | validation.BookingReinstatementValidationsTest | 5 | 5 | 0 | 0 |
| 62 | validation.HeaderLocationValidationsTest | 10 | 10 | 0 | 0 |
| 63 | validation.OptionalValidationsTest | 47 | 47 | 0 | 0 |
| 64 | validation.PartyValidationsTest | 65 | 65 | 0 | 0 |
| 65 | validation.RequestLegValidationsTest | 15 | 15 | 0 | 0 |
| 66 | validation.ValidationContextTest | 25 | 25 | 0 | 0 |
| 67 | validation.ValidationPlanFactoryTest | 7 | 7 | 0 | 0 |
| 68 | validation.ValidationPlanTest | 2 | 2 | 0 | 0 |
| 69 | validation.ValidationSupportTest | 6 | 6 | 0 | 0 |

Skipped tests are in classes that require live network services (stubs/integration placeholders excluded from surefire).

### Phase 3: Failsafe DynamoDB Integration Tests — JUnit5 (138 tests)

| # | Test Class | Tests | Pass | Fail | Skip |
|---|-----------|-------|------|------|------|
| 1 | carrierspotrates.dao.SpotRatesDaoIT (5 nested classes) | 8 | 8 | 0 | 0 |
| 2 | carrierspotrates.dao.SpotRatesToInttraRefDaoIT (5 nested classes) | 8 | 8 | 0 | 0 |
| 3 | dao.BookingDetailDaoIT (10 nested classes) | 30 | 30 | 0 | 0 |
| 4 | dynamodb.BookingDynamoDbAdminCommandIT (4 nested classes) | 32 | 32 | 0 | 0 |
| 5 | rapidreservation.persistence.RapidReservationDaoIT (5 nested classes) | 15 | 15 | 0 | 0 |
| 6 | template.persistence.TemplateDaoIT (5 nested classes) | 13 | 13 | 0 | 0 |
| 7 | template.persistence.TemplateSummaryDaoIT (6 nested classes) | 10 | 10 | 0 | 0 |
| 8 | util.SequenceIdDaoIT (5 nested classes) | 10 | 10 | 0 | 0 |
| 9 | util.UniqueIdDaoIT (7 nested classes) | 12 | 12 | 0 | 0 |

These tests use DynamoDB Local (in-memory) and require `sqlite4java` native libraries.

### Phase 4: Failsafe Flow/Service Integration Tests — TestNG (149 tests)

| # | Test Class | Tests | Pass | Fail | Skip |
|---|-----------|-------|------|------|------|
| 1 | flow.FlowTest | 25 | 25 | 0 | 0 |
| 2 | service.BookingServiceIntegrationTest | 44 | 44 | 0 | 0 |
| 3 | networkservices.participant.NetworkParticipantServiceIntegrationTest | 10 | 10 | 0 | 0 |
| 4 | networkservices.referencedata.ReferenceDataServiceIntegrationTest | 7 | 7 | 0 | 0 |
| 5 | elasticsearch.SearcherTest | 21 | 21 | 0 | 0 |
| 6 | dao.BookingDetailDaoTest | 11 | 11 | 0 | 0 |
| 7 | template.persistence.TemplateSummaryDaoIntegrationTest | 5 | 5 | 0 | 0 |
| 8 | outbound.services.SubscriptionConditionEvaluatorIntegrationTest | 5 | 5 | 0 | 0 |
| 9 | networkservices.geography.GeographyServiceTest | 4 | 4 | 0 | 0 |
| 10 | inbound.BookingProcessorTaskIntegrationTest | 4 | 4 | 0 | 0 |
| 11 | networkservices.connections.ConnectionsServiceTest | 3 | 3 | 0 | 0 |
| 12 | template.persistence.TemplateDaoTest | 2 | 2 | 0 | 0 |
| 13 | elasticsearch.IndexerTest | 2 | 2 | 0 | 0 |
| 14 | outbound.services.OutboundServiceIntegrationTest | 1 | 1 | 0 | 0 |
| 15 | networkservices.auth.AuthClientTest | 1 | 1 | 0 | 0 |
| 16 | networkservices.alias.ParticipantAliasServiceTest | 1 | 1 | 0 | 0 |
| 17 | networkservices.userservice.UserServiceTest | 1 | 1 | 0 | 0 |
| 18 | outbound.services.PartyNameAddressFormatterIntegrationTest | 1 | 1 | 0 | 0 |
| 19 | enrichment.LocationEnrichmentIntegrationTest | 1 | 1 | 0 | 0 |

These require AWS credentials and live service endpoints (api-alpha). Config: `booking/conf/pullRequest/config.yaml`.

---

## Maven Commands Reference

### Run All Tests (Unit + Integration)
```bash
mvn clean verify -pl booking -am
```

### Run Only Unit Tests (JUnit5 + TestNG, skip integration)
```bash
mvn test -pl booking -am
```

### Run Only JUnit5 Unit Tests (exclude TestNG)
```bash
mvn test -pl booking -am -Dsurefire.provider=org.apache.maven.surefire.junitplatform.JUnitPlatformProvider
```
Note: This may not work perfectly with dual-provider config. Alternative using include pattern:
```bash
mvn test -pl booking -am -Dtest="com.inttra.mercury.booking.**.*Test" -DfailIfNoTests=false
```

### Run Only TestNG Unit Tests
```bash
mvn test -pl booking -am -Dsurefire.provider=org.apache.maven.surefire.testng.TestNGProvider
```

### Run a Specific JUnit5 Test Class
```bash
mvn test -pl booking -Dtest="com.inttra.mercury.booking.elasticsearch.IndexerUnitTest"
```

### Run a Specific JUnit5 Test Method
```bash
mvn test -pl booking -Dtest="com.inttra.mercury.booking.elasticsearch.IndexerUnitTest#testIndexConflictException"
```

### Run a Specific TestNG Test Class
```bash
mvn test -pl booking -Dtest="com.inttra.mercury.booking.validation.ValidationContextTest"
```

### Run a Specific TestNG Test Method
```bash
mvn test -pl booking -Dtest="com.inttra.mercury.booking.validation.ValidationContextTest#testIsActivatedBooker"
```

### Run Only DynamoDB Integration Tests (JUnit5 IT classes)
```bash
mvn verify -pl booking -am -Dit.test="com.inttra.mercury.booking.**.*IT" -DskipTests=true
```
Or specific DynamoDB IT class:
```bash
mvn verify -pl booking -am -Dit.test="com.inttra.mercury.booking.dao.BookingDetailDaoIT" -DskipTests=true
```

### Run All DynamoDB Integration Tests by Name Pattern
```bash
mvn verify -pl booking -am -Dit.test="com.inttra.mercury.booking.dao.*IT,com.inttra.mercury.booking.dynamodb.*IT,com.inttra.mercury.booking.carrierspotrates.dao.*IT,com.inttra.mercury.booking.rapidreservation.persistence.*IT,com.inttra.mercury.booking.template.persistence.*IT,com.inttra.mercury.booking.util.*IT" -DskipTests=true
```

### Run Only Flow Step Integration Tests
```bash
mvn verify -pl booking -am -Dit.test="com.inttra.mercury.booking.flow.FlowTests" -DskipTests=true
```
Note: `FlowTests.java` discovers flow test cases dynamically via `FlowTests::factory`.

### Run All Integration Tests (excluding unit tests)
```bash
mvn verify -pl booking -am -DskipTests=true
```

### Run Specific Integration Test Class
```bash
mvn verify -pl booking -am -Dit.test="com.inttra.mercury.booking.service.BookingServiceIntegrationTest" -DskipTests=true
```

### Key Notes
- `-pl booking -am` builds booking and its dependencies
- `-DskipTests=true` skips surefire (unit tests) but runs failsafe (integration tests)
- `-Dmaven.test.skip=true` skips ALL tests AND test compilation
- DynamoDB IT tests use DynamoDB Local (in-memory) — no AWS credentials needed
- Flow/Service IT tests require AWS credentials and live endpoints (api-alpha)
- System property for DynamoDB Local native libs: `-Dsqlite4java.library.path=booking/target/native-libs`
