---
name: build-errors
description: >
  **WORKFLOW SKILL** — Diagnose and fix CI/CD build failures and flaky integration tests.
  USE FOR: Jenkins build errors; test failures from Maven verify; Jackson deserialization errors;
  EDI timestamp flakiness; DynamoDB round-trip precision issues; config deserialization failures.
  INVOKES: session context tools, git tools, kb tools, terminal commands.
---

# Build Error Diagnosis & Fix Skill

## When to Use

Use this skill when:
- A Jenkins CI build fails and you need to diagnose and fix the root cause
- Integration tests are failing or flaky
- Maven `verify` reports test failures
- Configuration deserialization errors occur (e.g., unrecognized fields in Jackson/Dropwizard)

## Workflow

### 1. Gather Context
```
session_list(project="mercury-services", status="active")
# Create or load session for tracking
session_create(name="<TICKET> fix build error", project="mercury-services", tags=["CI-fix", "<module>"])
```

Collect the build error details:
- Jenkins console output or local Maven output
- Identify the failing module, test class, and test method
- Note the exact error message

### 2. Classify the Error

Common error categories in this codebase:

#### A. Jackson Deserialization Errors
**Pattern**: `Unrecognized field "X"` or `UnrecognizedPropertyException`
**Root cause**: A Java getter method (e.g., `getX()`) produces a property during Jackson serialization that doesn't exist as a settable field. When Dropwizard re-reads the serialized config, it rejects the unknown field.
**Fix**: Add `@JsonIgnore` on the getter, or use a MixIn class if the source is in a shared library.
**Example**: `ServiceDefinition.getPreppedUri()` — computed getter serialized by Jackson but rejected on re-read. Fixed via `ServiceDefinitionMixIn` with `@JsonIgnore` on `getPreppedUri()`.

#### B. Timestamp Precision Mismatches (DynamoDB round-trip)
**Pattern**: `assertEquals` fails with `OffsetDateTime` values differing in nanosecond precision
**Root cause**: In-memory `OffsetDateTime` has nanosecond precision, but DynamoDB stores via `@JsonFormat(pattern="yyyy-MM-dd'T'HH:mm:ss.SSSZ")` which truncates to milliseconds.
**Fix**: Normalize timestamps with `truncatedTo(ChronoUnit.MILLIS)` before comparison.
**Example**: `testFindBooking` — audit timestamps truncated during DynamoDB round-trip via `AuditAttributeConverter`.

#### C. EDI Timestamp Flakiness (minute boundary)
**Pattern**: EDI string comparison fails with timestamps differing by 1 minute (e.g., `1557` vs `1558`)
**Root cause**: `TransformationProcessor` uses system clock internally, while test templates use a fixed clock captured earlier. If execution crosses a minute boundary, they disagree.
**Fix**: Extract actual timestamps from generated EDI output and use them when rendering the expected template.
**Example**: `FlowTest.doTest` — added `overrideEdiTimestampsFromActual()` to align expected template with actual EDI timestamps.

#### D. DynamoDB SDK v2 Behavioral Differences
**Pattern**: `assertEquals` fails on fields like `version` (Integer vs Long), or attribute types differ
**Root cause**: DynamoDB Enhanced Client (SDK v2) returns numeric values as `Long` instead of `Integer`, and uses `@DynamoDbVersionAttribute` differently than SDK v1's `DynamoDBMapper`.
**Fix**: Normalize the in-memory object to match the DB round-trip behavior before assertion.
**Example**: `testFindBooking` — version field normalized: `if (d.getVersion() == null) d.setVersion(1);`

#### E. MixIn Pattern for Shared Library Classes
**Pattern**: Need to customize Jackson serialization for classes in `commons` or other shared libraries
**Fix**: Create a MixIn inner class with the desired annotations and register via `ObjectMapper.addMixIn()`.
**Example**: `AbstractIntegrationTest.ServiceDefinitionMixIn` — `@JsonIgnore` on `getPreppedUri()` registered in test setup.

### 3. Diagnose

```bash
# Read the failing test
kb_grep(pattern="<TestClass>", file_pattern="*.java")

# Check test reports for details
cat <module>/target/failsafe-reports/testng-results.xml | grep -A5 "<testMethod>"

# Look at the assertion line
read_file("<test-file>", startLine=<error-line - 20>, endLine=<error-line + 20>)

# Check the model class involved
kb_grep(pattern="<FieldName>", file_pattern="<ModelClass>.java")
```

### 4. Fix & Verify

```bash
# Make the fix
# ...

# Compile to catch syntax errors
mvn test-compile -pl <module> -q

# Run the specific failing test (unit tests)
mvn test -pl <module> -Dtest=<TestClass>#<testMethod>

# Run full integration suite
mvn verify -pl <module> -DbookingConfig=conf/pullRequest/config.yaml

# Track progress
session_add_context(session_id, summary="Fixed <test>", category="test_result", detail="...")
```

### 5. Verify Complete Suite

```bash
# Run full verify to ensure no regressions
mvn verify -pl <module>
# Confirm: Tests run: N, Failures: 0, Errors: 0
```

## Key Files

| Module | Integration Test Base | Config |
|--------|----------------------|--------|
| booking | `AbstractIntegrationTest` | `conf/pullRequest/config.yaml` |
| booking | `BookingServiceIntegrationTest` | Uses `newBookingService()` |
| booking | `FlowTest` / `FlowStep` | YAML-driven flow tests with EDI verification |
| network | `AbstractIntegrationTest` | Module-specific config |

## Rules

- Always run the full `mvn verify` after fixing, not just the single failing test
- Track all fixes in the session context with `test_result` category
- For flaky tests, prefer deterministic fixes (extract actual values) over tolerance-based fixes
- Follow existing normalization patterns in the codebase (e.g., version normalization in `testFindBooking`)
- When fixing ObjectMapper issues, check `AbstractIntegrationTest` for existing MixIn patterns
