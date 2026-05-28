# Booking Module — DW5 / Jetty 12 Upgrade Issues (commons 1.0.25-SNAPSHOT)

**Date:** 2026-05-27
**Branch:** `feature/ION-15743-jetty-compile-issue`
**Commons version:** `1.0.23-SNAPSHOT` → `1.0.24-SNAPSHOT` → `1.0.25-SNAPSHOT`
**Key change in commons:** Dropwizard 5 + Jetty 12 (Jakarta EE 10); `aws-java-sdk-core` forced to a modern version in `1.0.25-SNAPSHOT`

---

## Summary

Upgrading `mercury.commons.version` from `1.0.23-SNAPSHOT` to `1.0.24-SNAPSHOT` introduced compilation and runtime failures in the booking module. The new commons ships Dropwizard 5 (DW5) with Jetty 12, which brings Jackson 2.21.0 and Jakarta EE 10 APIs. A follow-up bump to `1.0.25-SNAPSHOT` resolved the `AwsRegionProvider` runtime issue at the commons layer. All booking-side compilation and test failures have been resolved — `mvn clean verify -pl booking -am` now passes (984 unit + 149 integration tests, 0 failures).

---

## Issues Found & Fixed

### 1. `com.sun.el.ExpressionFactoryImpl` — Package Not Found

**File:** `booking/src/main/java/com/inttra/mercury/booking/util/MessageSupport.java`  
**Error:** `package com.sun.el does not exist`  
**Cause:** `com.sun.el.ExpressionFactoryImpl` is a GlassFish EL implementation class no longer transitively available in DW5/Jetty 12.  
**Fix:** Replaced `new ExpressionFactoryImpl()` with `ExpressionFactory.newInstance()` (standard Jakarta EL API, uses service loader).  

### 2. `jackson-annotations` Version Mismatch

**Error:** `NoClassDefFoundError: JsonSerializeAs` at runtime (jackson-databind 2.21.0 expected jackson-annotations 2.21.0)  
**Cause:** Booking explicitly declared `jackson-annotations:2.18.1`, overriding the 2.21.0 version from DW5.  
**Fix:** Removed the explicit `jackson-annotations` dependency. It now comes transitively from `jackson-databind:2.21.0` via DW5/commons.  

### 3. `jackson-module-afterburner` — Unused & Poisonous

**Error:** `NoSuchMethodError: SettableBeanProperty.<init>` at runtime  
**Cause:** Two problems:
  - Booking declared `jackson-module-afterburner` directly (unused — zero imports in code). DW5 uses `jackson-module-blackbird` instead.
  - `hystrix-dropwizard-bundle` pulled `hystrix-serialization:1.5.12` → `jackson-module-afterburner:2.7.5` transitively. This ancient version auto-registered via SPI (`META-INF/services/com.fasterxml.jackson.databind.Module`) and was incompatible with Jackson 2.21.0.  
**Fix:** Removed the explicit `jackson-module-afterburner` dependency and its version property. Also removed the shade plugin exclusion (no longer needed).

### 4. `hystrix-dropwizard-bundle` — Replaced with `hystrix-core`

**Dependency:** `org.zapodot:hystrix-dropwizard-bundle:1.0.2`  
**Analysis:** Booking only uses `com.netflix.hystrix.HystrixCommand` and related core classes (circuit breaker pattern) in `externalwrapper/hystrix/` package. Zero usage of:
  - `HystrixBundle` (zapodot DW integration)
  - `hystrix-metrics-event-stream` (metrics servlet)
  - `hystrix-serialization` (Jackson serializers)
  - Any `org.zapodot` or `com.netflix.hystrix.contrib` imports  
**Fix:** Replaced `hystrix-dropwizard-bundle` with `hystrix-core:1.5.12` directly. This eliminates the transitive chain: `hystrix-metrics-event-stream` → `hystrix-serialization` → `jackson-module-afterburner:2.7.5`.

### 5. Jackson Version Alignment

**Fix:** Updated all remaining explicit Jackson versions from `2.18.1` to `2.21.0` to match DW5:
  - `jackson-dataformat-xml` (used in `S3ArchiveHandler.java` for `XmlMapper`)
  - `jackson-module-jsonSchema` (test scope, used in `JsonSchemaTest.java`)

### 6. `AWSUtil.java` — Removed (pre-existing fix)

**File:** `booking/src/main/java/com/inttra/mercury/booking/common/AWSUtil.java`
**Cause:** Referenced `com.amazonaws.SdkClientException` and `com.amazonaws.retry.RetryUtils` from AWS SDK v1 (not available at compile scope). Was breaking Lombok annotation processing chain.
**Fix:** Removed `AWSUtil.java` and `AWSUtilTest.java` (already replaced by cloud-sdk retry mechanisms).

### 7. `AwsRegionProvider` — Runtime `NoClassDefFoundError` (fixed in commons 1.0.25-SNAPSHOT)

**Error:** `NoClassDefFoundError: com/amazonaws/regions/AwsRegionProvider` at app startup
**Cause:** `vc.inreach.aws:aws-signing-request-interceptor:0.0.22` (transitively from `cloud-sdk-aws`) pulled `aws-java-sdk-core:1.10.19`. This ancient version won Maven's nearest-first conflict resolution over `1.12.721`/`1.12.730` from other deps. Version `1.10.19` predates the `AwsRegionProvider` class (added ~1.11.x), so code that expected it failed at runtime.
**Fix:** Resolved in **commons** (`cloud-sdk-aws`) by forcing a modern `aws-java-sdk-core` version. Booking picks this up by bumping `mercury.commons.version` to `1.0.25-SNAPSHOT`.

### 8. Remaining AWS SDK v1 References in Production Code

| File | Import | Resolution |
|---|---|---|
| `OutboundServiceImpl.java` | `com.amazonaws.util.CollectionUtils` | **Fixed** — inlined to `coll != null && !coll.isEmpty()`; import removed |
| `MigrationLogic.java` | `com.amazonaws.util.CollectionUtils` | **Fixed** — inlined to `coll == null \|\| coll.isEmpty()`; import removed |
| Lambda handlers | `com.amazonaws.services.lambda.runtime.events.*` | From `aws-lambda-java-events` — kept (this artifact is part of the Lambda v1 runtime SDK, not the AWS SDK v1 client) |

### 9. WireMock — `FatalStartup: Jetty 11 is not present`

**Error:** `NetworkServiceIntegrationTest.init` failed with `Jetty 11 is not present and no suitable HttpServerFactory extension was found.`
**Cause:** The vanilla `org.wiremock:wiremock:3.5.4` artifact expects Jetty 11 on the classpath. With booking on Jetty 12 (DW5), WireMock could not boot its embedded server.
**Fix:** Switched the test dependency to `org.wiremock:wiremock-jetty12:3.5.4`, which provides the Jetty 12 `HttpServerFactory` implementation. All Jetty exclusions on the old `wiremock` artifact were dropped — `wiremock-jetty12` resolves cleanly against the project's Jetty 12 BOM.

### 10. Integration tests — `RejectedExecutionException` from the `outbound` thread pool

**Error:** `BookingServiceIntegrationTest.testUnauthorizedAmend` and `testUnauthorizedCancel` failed with `RejectedExecutionException` thrown from `OutboundServiceImpl.processOutbound` during test setup, before the call that was supposed to throw `AuthorizationException`. The bounded `ArrayBlockingQueue(60)` was full and 20/20 threads were busy because integration tests submit real outbound tasks (BookingService injects the concrete `OutboundServiceImpl`, not the interface, so Guice's `OutboundService → DummyOutboundService` binding does not apply).
**Cause:** In `OutboundServiceModule`, the `outboundEnabled=true` branch (production) already uses `ThreadPoolExecutor.CallerRunsPolicy()`, but the `outboundEnabled=false` branch (PR/integration config) used the default `AbortPolicy`. Once 80 outbound tasks accumulated across the 149 integration tests, new submissions were rejected.
**Fix:** Added `.rejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy())` to the `outboundEnabled=false` branch so the calling (test) thread runs the task synchronously when the queue is full. Production behavior is unchanged.

---

## Files Changed

| File | Change |
|---|---|
| `booking/pom.xml` | Commons 1.0.23 → 1.0.25-SNAPSHOT, removed `jackson-annotations`, removed `jackson-module-afterburner`, replaced `hystrix-dropwizard-bundle` with `hystrix-core`, aligned Jackson versions to 2.21.0, switched `wiremock` → `wiremock-jetty12` |
| `booking/src/main/java/.../util/MessageSupport.java` | `ExpressionFactoryImpl` → `ExpressionFactory.newInstance()` |
| `booking/src/main/java/.../common/AWSUtil.java` | Deleted |
| `booking/src/test/java/.../common/AWSUtilTest.java` | Deleted |
| `booking/src/main/java/.../outbound/services/OutboundServiceImpl.java` | Removed `com.amazonaws.util.CollectionUtils` import; inlined `isNullOrEmpty` call |
| `booking/src/main/java/.../inbound/MigrationLogic.java` | Removed `com.amazonaws.util.CollectionUtils` import; inlined `isNullOrEmpty` call |
| `booking/src/main/java/.../config/OutboundServiceModule.java` | Added `CallerRunsPolicy` to the `outboundEnabled=false` executor (test/PR config only) |

---

## Dependency Cleanup Summary

| Dependency | Action | Reason |
|---|---|---|
| `mercury.commons.version` | **Bumped** 1.0.23 → 1.0.25-SNAPSHOT | DW5 + Jetty 12 + `aws-java-sdk-core` upgrade pulled in from commons |
| `jackson-annotations:2.18.1` | **Removed** | Transitive from jackson-databind via DW5 |
| `jackson-module-afterburner` | **Removed** | Zero code usage, DW5 uses blackbird, was excluded from shade JAR |
| `hystrix-dropwizard-bundle:1.0.2` | **Replaced** with `hystrix-core:1.5.12` | Only HystrixCommand used; bundle dragged in poisonous afterburner 2.7.5 |
| `wiremock:3.5.4` | **Replaced** with `wiremock-jetty12:3.5.4` | Vanilla `wiremock` expects Jetty 11; `-jetty12` variant provides the Jetty 12 `HttpServerFactory` |
| `com.amazonaws.util.CollectionUtils` | **Removed** | Inlined to plain null/empty check in `OutboundServiceImpl` and `MigrationLogic`; eliminates AWS SDK v1 surface in production code |
| `jackson-module-jsonSchema:2.21.0` | **Kept** | Used in tests (JsonSchemaTest, GenerateBookingSampleFiles) |
| `jackson-dataformat-xml:2.21.0` | **Kept** | Used in S3ArchiveHandler (XmlMapper) |

---

## Open Issue: Netty 4.1.118 in Shaded JAR (OWASP flagged CRITICAL)

**Status:** Root cause identified — requires commons rebuild  
**OWASP Finding:** 10 Netty artifacts (`netty-buffer`, `netty-codec-http`, `netty-handler`, etc.) at `4.1.118.Final` flagged with 18 CRITICAL CVEs each (224 total findings). These are **false positives** for Netty 4.1.118 but the jars should not be in the shaded JAR regardless.

**Root Cause:** `software.amazon.awssdk:netty-nio-client:2.30.24` (AWS SDK v2 async HTTP client) leaks into the dependency tree at `runtime` scope. All cloud-sdk-aws service dependencies (`s3`, `dynamodb`, `sqs`, etc.) correctly exclude `netty-nio-client`, but the **installed** `cloud-sdk-aws-1.0.25-SNAPSHOT.pom` in the local Maven repo is stale — it has only 13 exclusion entries whereas the source POM has 14. Two exclusions were added after the last `mvn install`:
  - `cloud-sdk-api` — exclusion present in source, missing from installed POM  
  - `amazon-sqs-java-extended-client-lib` — exclusion present in source, missing from installed POM

The `netty-nio-client` is not needed at runtime — booking uses sync HTTP clients only (`apache-client`, `url-connection-client`, `aws-crt-client`).

**Fix:** Rebuild and install commons from the mercury-services-commons workspace:
```sh
cd C:/Users/arijit.kundu/projects/mercury-services-commons
mvn clean install -DskipTests
```
Then rebuild booking (`mvn clean package -pl booking -am -DskipTests`) and re-run the OWASP scan to confirm Netty jars are gone.

---

## Verification

`mvn clean verify -pl booking -am` — **BUILD SUCCESS**

| Phase | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| Surefire (unit) | 984 | 0 | 0 | 10 |
| Failsafe (integration, TestNG) | 149 | 0 | 0 | 0 |
| **Total** | **1133** | **0** | **0** | **10** |
