# ION-12310 — 1.0.31-SNAPSHOT implementation: units bug, D-1 HTTP client, lifecycle

**Author:** Arijit Kundu · **Date:** 2026-08-16
**Repo:** `mercury-services-commons`, branch `feature/ION-12310-commons-cloudsdk-refactoring`
**Design source:** [2026-08-14-cloud-sdk-defect-refactor.md](2026-08-14-cloud-sdk-defect-refactor.md) §1.7, §1.2–§1.6, §4.5, §5
**Baseline:** `1e2fcd6` (1.0.30-SNAPSHOT) · **Ships as:** `1.0.31-SNAPSHOT`

This is the implementation record for the four commits designed in the 2026-08-14 document. It states what was built, where it deviates from the design, and what a consumer has to do.

---

## 0. The premise, and how it was met

> **No source change in any `mercury-services` module. Recompile is not even required — old bytecode still links. Two deliberate runtime corrections, both in the safe direction.**

The design document accepted binary breakage and mandated a recompile of the whole fleet (§5.3, "The one non-negotiable"). This implementation is **stricter**: every signature change is accompanied by a bridge overload, so a class compiled against 1.0.30 links against 1.0.31 without `NoSuchMethodError`. The recompile is still recommended — it is how consumers pick up the fix — but it is no longer a correctness requirement.

| Compatibility axis | Design | Implemented |
|---|---|---|
| Source compatibility for consumers | ✅ required | ✅ held |
| Binary compatibility for consumers | ❌ explicitly given up | ✅ **held** |
| Runtime behaviour | ⚠️ two deliberate corrections | ⚠️ same, unchanged from design |

---

## 1. Commits

Five commits, each independently revertible in reverse order.

| # | Commit | Subject |
|---|---|---|
| 1 | `9958924` | fix HTTP timeout units bug — consolidate tuned transports into `AwsHttpDefaults` |
| 2 | `0801e66` | make the tuned HTTP defaults reachable via `BaseAwsConfigBuilder.defaultHttpClient` |
| 3 | `27402e4` | D-1 Option A — `AwsHttpClientWrapper` attaches itself to AWS client builders |
| 4 | `cfa27f9` | `CloudResource` replaces `AutoCloseable` on the cloud-sdk client interfaces |
| 5 | `8ee8315` | bump to 1.0.31-SNAPSHOT and add the release note |
| 6 | `f21c80f` | keep the connection pool at 50 for DynamoDB too — no runtime delta |

> **Commit 6 partially reverts commit 2.** See §3.1. The net effect of 2 + 6 is that the `defaultHttpClient` hook does not ship; the tuned defaults are reachable purely through commit 1's delegation.

---

## 2. Commit 1 — the units bug

### What was wrong

`S3ClientFactory.createHttpClient()` and `AwsHttpClientWrapper.defaultAsyncClient()` applied `Duration.ofSeconds` / `ofMinutes` to constants named `..._MILLIS`:

```java
.connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))               // ofSeconds(5000)  ≈ 83 min
.connectionAcquisitionTimeout(Duration.ofMinutes(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))  // ofMinutes(10000) ≈ 6.9 days
```

`S3ClientFactory.createDefaultS3Client()` calls `createHttpClient()` directly, so this is **live in production** — `booking` ×2 (including the `S3ArchiveHandler` Lambda), `bill-of-lading-v2` and `tx-tracking`. A 6.9-day acquisition timeout means a thread parks in `PoolingHttpClientConnectionManager.leaseConnection` with no error, no timeout and no log line.

Three other factories carried near-identical copies of the same builder with their own duplicated constants and got the units right. Four copies, three constant sets, one bug.

### What was built

New `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/AwsHttpDefaults.java` — the single home for tuned transports. Durations are `Duration` constants, so a unit mismatch is now a **compile error**:

```java
public static final Duration CONNECTION_TIMEOUT = Duration.ofSeconds(5);
public static final Duration SOCKET_TIMEOUT = Duration.ofSeconds(30);
public static final Duration CONNECTION_ACQUISITION_TIMEOUT = Duration.ofSeconds(10);
public static final int MAX_CONNECTIONS = 50;
public static final int MAX_ASYNC_CONCURRENCY = 100;

public static ApacheHttpClient.Builder syncBuilder() { ... }
public static AwsCrtAsyncHttpClient.Builder asyncBuilder() { ... }
public static AwsHttpClientWrapper sync() / async() { ... }
```

All four `createHttpClient()` copies and both `AwsHttpClientWrapper` defaults collapse to a single delegation each.

### Deviation from the design

The design deprecates the old `int ..._MILLIS` constants. Implemented as `@Deprecated` **without** `forRemoval`, in `StorageConfigConstants` and in the three factories that duplicate them. `NotificationClientFactoryTest:168-171` asserts those constant values and still passes unchanged.

### Test

`AwsHttpDefaultsTest` — constant assertions, a parameterised "no tuned duration exceeds one minute" guard, builder-independence checks, and the rule that would have caught the defect at review:

```java
Pattern.compile("Duration\\.of(Seconds|Minutes|Hours|Days|Nanos)\\s*\\(\\s*[A-Za-z0-9_.]*_MILLIS\\b")
```

scanned across every `.java` file under `cloud-sdk-aws/src/main/java`. This is a source-level guard rather than an ArchUnit rule — no new dependency, and it catches the mistake in any file, not just the ones a rule remembers to cover.

---

## 3. Commit 2 — making the tuned defaults reachable

`BaseAwsConfig` filled `httpClient` with a bare `ApacheHttpClient.builder().build()` whenever a caller supplied none. Because the field is never null afterwards, the `config.getHttpClient() != null ? ... : createHttpClient()` ternary in every factory **always took the first branch** — so each factory's tuned `createHttpClient()` was dead code and every service silently ran on AWS SDK defaults (50 connections, 2 s connect).

**Commit 1 alone fixes this.** `BaseAwsConfig`'s fallback is `AwsHttpClientWrapper.defaultClient()`, which now delegates to `AwsHttpDefaults.sync()`. Nothing further is needed for the tuned values to apply.

Commit 2 added an overridable `defaultHttpClient(boolean)` hook on the builder for one reason only: to let DynamoDB take a *different*, larger pool. Commit 6 withdrew that, and the hook with it.

### 3.1 Why the DynamoDB 100-connection pool was withdrawn

The 2026-08-14 design (§1.7 Part 3) gives DynamoDB a 100-connection pool, on the grounds that `DynamoRepositoryFactory.DEFAULT_MAX_CONNECTIONS = 100` documents that intent and the constant had become unreachable. Checked against what consumers actually run, that reasoning does not hold:

| Path | Reaches `DynamoRepositoryFactory.createHttpClient()`? |
|---|---|
| `createDynamoDbClient(config)` — the only configured path | ❌ No. It is the fallback arm of a ternary `BaseAwsConfig` never lets fire. |
| `createDefaultDynamoClient()` | ❌ No. It is `return DynamoDbClient.create();` — pure SDK defaults. |
| Any consumer supplying an explicit HTTP client for DynamoDB | ❌ None exists — see §6.2. |

So the 100 was **never applied to a single client, ever**. Every module has run DynamoDB on the AWS SDK default of 50 for the whole life of the constant. Raising it to 100 would not have been "restoring documented intent" — it would have been an untested capacity change to every DynamoDB client in the fleet, shipped inside a release whose selling point is that nothing surprising happens.

Withdrawn accordingly:

* `AwsHttpDefaults.DYNAMODB_MAX_CONNECTIONS`, `dynamoDbSyncBuilder()`, `dynamoDbSync()`
* `DynamoDbClientConfig.Builder.defaultHttpClient(...)` override
* `BaseAwsConfigBuilder.defaultHttpClient(boolean)` — no longer has a purpose

`AwsHttpDefaults.MAX_CONNECTIONS` (50) is now the single pool size for S3, DynamoDB, SQS, SNS, SES and SSM. `DynamoRepositoryFactory.DEFAULT_MAX_CONNECTIONS = 100` is retained (deprecated) for source compatibility, with Javadoc saying plainly that it was never applied.

`getHttpClient()` remains **non-null on every config** — that guarantee is declared on the published `CloudStorageConfig` interface and asserted by `NotificationClientConfigTest:205` and `AwsCloudParameterStoreConfigTest:116`, both unchanged and passing.

`DynamoDbClientConfig.maxConnections` (default 100, no reader anywhere in `src/main`) remains unread, per the design's deferral.

### Test

`BaseAwsConfigDefaultHttpClientTest` — parameterised across `AwsStorageConfig`, `DynamoDbClientConfig`, `AwsMessagingClientConfig` and `NotificationClientConfig` asserting the non-null sync-instance guarantee; plus "DynamoDB gets the same pool as every other service", "explicit wins", and the async default.

---

## 4. Commit 3 — D-1, builder mode honoured by one factory out of six

### What was wrong

PR #46 added builder mode to `AwsHttpClientWrapper` and taught **only `S3ClientFactory`** to recognise it. Every other factory funnelled the wrapper through the unchecked `getTypedClient()` straight into `.httpClient(...)`:

```java
.httpClient(config.getHttpClient() != null ? config.getHttpClient().getTypedClient() : createHttpClient());
```

`T` is inferred from the target type, so javac infers `T = SdkHttpClient` and compiles this with no error at all. At runtime the `checkcast` is emitted **in the caller's bytecode**, and an `ApacheHttpClient.Builder` is not an `SdkHttpClient`:

```
java.lang.ClassCastException: class ...ApacheHttpClient$DefaultBuilder cannot be cast to class ...SdkHttpClient
    at ...DynamoRepositoryFactory.createDynamoDbClient(...)
```

Thrown during Guice module construction — the service fails to boot.

The root cause is not that the field is `Object`; it has been `Object` since ION-11759. Pre-#46, `ofSync`/`ofAsync` both enforced `instanceof`, giving a construction-time invariant that `isAsync` alone fully described the contents. PR #46 added two factory methods with no validation, removing the invariant and adding a second discriminator, without updating any of the six callers that relied on the old one.

### What was built — Option A

The wrapper is the only object that knows which of the four states it is in, so it is the only object that decides how to attach itself. *Tell, don't ask.*

```java
public enum Mode { SYNC_INSTANCE, SYNC_BUILDER, ASYNC_INSTANCE, ASYNC_BUILDER }

public void applyToSync(SdkSyncClientBuilder<?, ?> clientBuilder) {
    switch (mode) {
        case SYNC_INSTANCE -> clientBuilder.httpClient((SdkHttpClient) underlyingClient);
        case SYNC_BUILDER  -> clientBuilder.httpClientBuilder((SdkHttpClient.Builder<?>) underlyingClient);
        default -> throw new IllegalStateException("Cannot apply an asynchronous HTTP client (" + describe() + ") ...");
    }
}
```

plus the null-tolerant static forms `applyToSync(wrapper, clientBuilder, fallbackSupplier)` / `applyToAsync(...)` that every factory now calls. There is no longer a cast for a caller to get wrong.

The methods live on `AwsHttpClientWrapper` in `cloud-sdk-aws`, **not** on `CloudHttpClient` in `cloud-sdk-api`, which has no AWS SDK dependency and must stay provider-neutral. This costs nothing: `BaseAwsConfig.getHttpClient()` already returns the concrete wrapper type. **`cloud-sdk-api` is untouched by commit 3.**

The unreachable `try/catch (ClassCastException)` inside `getTypedClient()` was removed (**D-10**). It was dead because erasure gives the method the descriptor `()Ljava/lang/Object;`, so javac emits no `checkcast` inside it — the try region is `aload_0; getfield; areturn`. The existing test that appears to cover it passes because the CCE comes from the *test's own* `checkcast`, which is still true, so that test is unchanged and still green.

### Call sites changed

| File | Change |
|---|---|
| `storage/factory/S3ClientFactory` | the `isBuilder` branch → one `applyToSync` call |
| `database/factory/DynamoRepositoryFactory` | `applyToSync` |
| `messaging/factory/MessagingClientFactory` | two call sites; the second lifted out of a constructor argument |
| `notification/factory/NotificationClientFactory` | `applyToSync` |
| `storage/factory/TransferManagerFactory` | `applyToAsync`; `resolveAsyncHttpClient` **kept**, deprecated |
| `email/factory/EmailClientFactory` | now honours the configured HTTP client (was silently ignored) |
| `paramstore/factory/ParameterStoreClientFactory` | same |
| `storage/config/AwsStorageConfig` | `get*HttpClientForTesting()` → explanatory `IllegalStateException` in builder mode instead of a bare CCE |

### Deviations from the design — all in favour of compatibility

| Design | Implemented | Why |
|---|---|---|
| `ofSyncBuilder(ApacheHttpClient.Builder)` **replaced** by `ofSyncBuilder(SdkHttpClient.Builder<?>)` | both, the Apache one delegating | The widened signature is source-compatible but binary-incompatible. Overload resolution picks the most specific applicable method, so existing `ApacheHttpClient.Builder` call sites bind to the bridge and behave identically — and old bytecode still links. |
| `ofAsyncBuilder(Object)` **replaced** by `ofAsyncBuilder(SdkAsyncHttpClient.Builder<?>)` | both; the `Object` one is `@Deprecated` and now **validates** with `instanceof` | Same reasoning. The validation closes the hole where `ofAsyncBuilder("hello")` constructed a wrapper successfully and failed much later somewhere else. |
| `resolveAsyncHttpClient` **deleted** from `TransferManagerFactory` | kept, `@Deprecated`, delegating | `TransferManagerFactoryTest:96,174` call it. Deleting it would have broken tests for no compatibility gain. |
| `getTypedClient()` `@Deprecated(forRemoval = true)` | `@Deprecated` only | `forRemoval` produces warnings that some consumer builds escalate. The removal is a 1.1.0 decision, not this release's. |
| Replace the "dead code" CCE test in `AwsHttpClientWrapperTest` | left unchanged; new coverage added alongside | The test still passes and still documents the deprecated method's real behaviour. Less churn, nothing broken. |

**One deliberate behaviour change:** `TransferManagerFactory` previously substituted a default CRT client when a *sync* wrapper was configured. `applyToAsync` now throws `IllegalStateException` naming the actual mode. The path is unreachable for well-formed configs — `BaseAwsConfig.validateBaseConfig()` already rejects a sync/async mismatch at build time — and failing loudly beats silently discarding tuned settings.

### Tests

* `AwsHttpClientWrapperApplyTest` (18 tests) — instance vs builder dispatch for both sync and async, the null-tolerant static forms including "the fallback is never evaluated when a wrapper is present", mode/flag consistency, the typed accessors' `IllegalStateException` messages, and all four compatibility bridges.
* `AllFactoriesBuilderModeTest` (14 tests) — **the regression guard.** Parameterised over all seven factories × {builder mode, instance mode}. Without it the same defect reappears the next time a factory is added.

---

## 5. Commit 4 — lifecycle

1.0.30 made `MessagingClient extends AutoCloseable` with an abstract `close()`. That broke twice: an `AbstractMethodError` for implementors compiled against an earlier version, and it newly legalised `try (var c = ...)` on a process-scoped singleton owned by the DI container — closing one in a lexical block leaves every injected holder with a dead reference and no way to publish a replacement.

New `cloud-sdk-api/config/CloudResource`:

```java
public interface CloudResource {
    default void close() { }
}
```

`MessagingClient`, `StorageClient`, `NotificationService` and `EmailService` now extend it. Because the body is a `default`, this is source- **and** binary-compatible for implementors, and it is uniform across all five interfaces rather than strict on one. It deliberately does **not** extend `AutoCloseable`.

New `cloud-sdk-api/config/ManagedCloudResource` adapts any `CloudResource` to a Dropwizard `Managed`, with a `catch (RuntimeException)` around `close()` — Dropwizard stops the remaining `Managed` objects in reverse order and one throwing `stop()` can abort the rest.

`SqsMessagingClient.close()` Javadoc corrected. It claimed to close "the underlying SqsClient and its connection pools". It does not close the pool: clients built with `httpClient(instance)` are wrapped by the SDK in `NonManagedSdkHttpClient`, whose `close()` is a no-op. Only builder mode makes the SDK the transport owner — **which is why commit 3 is a prerequisite for `close()` to mean anything.**

Rebuild-on-pool-death (a stable façade holding a `volatile SqsClient`) is explicitly **not** in scope. It is a distinct capability from lifecycle and should not be conflated with it.

### Test

`CloudResourceTest` (9 tests) — the `default` no-op, override dispatch and idempotence, `CloudResource` is not an `AutoCloseable`, `ManagedCloudResource.stop()` closes / `start()` does not / a throwing `close()` is swallowed / argument validation, and a structural check that all four client interfaces are `CloudResource`s and `MessagingClient` is no longer `AutoCloseable`.

---

## 6. Consumer impact

### Source

**None.** Verified across `booking`, `booking-bridge`, `bill-of-lading-v2`, `auth`, `visibility` and `tx-tracking`:

* `visibility`'s `VisibilityApplicationInjector.buildS3HttpClientWrapper()` passes an `ApacheHttpClient.Builder` to `ofSyncBuilder` — binds to the bridge overload, unchanged.
* `VisibilityApplicationInjectorTest.s3HttpClientWrapperIsBuilderBacked()` asserts `wrapper.isBuilder()` — retained as a derived getter, still true.
* `VisibilityMessagingModule:56-67` calls `messagingClient.close()` inside a hand-rolled `Managed` — `close()` is still declared (inherited from `CloudResource`) and `SqsMessagingClient` still overrides it, so virtual dispatch is identical. Adopting `ManagedCloudResource` is optional tidy-up.
* No module calls `getTypedClient()` or `ofAsyncBuilder`, and nothing uses try-with-resources on a `MessagingClient`.

### Binary

**None** — bridge overloads retain every original descriptor. Recompiling is still the recommended way to adopt.

### Runtime — the part to smoke-test

| Path | Reached today by | Before | After |
|---|---|---|---|
| `StorageClientFactory.createDefaultS3Client()` | `booking` ×2, `bill-of-lading-v2`, `tx-tracking` | connect **83 min**, acquire **6.9 days** | connect **5 s**, acquire **10 s** |
| `AwsHttpClientWrapper.defaultAsyncClient()` | nobody | connect 5 000 s, acquire 10 000 s | 5 s / 10 s |
| DynamoDB / SQS / SNS / S3 via config, no explicit client | all | connect 2 s, acquire 10 s, **50 conns** | connect **5 s**, acquire 10 s, **50 conns** |
| SES / SSM | `tx-tracking` (SES) | configured client **ignored**; SDK defaults | honoured; tuned defaults |
| S3 via an explicit builder-mode wrapper | `visibility` | caller-supplied (1 s / 5 s / 50) | **unchanged** |

Every delta moves in the safe direction. The two absurd timeouts collapse to sane ones, the connect timeout becomes more tolerant rather than less, **the connection pool is unchanged at 50 everywhere**, and a caller-supplied transport always wins.

### Rollout order

By exposure to the timeout correction: `tx-tracking` → `bill-of-lading-v2` → `booking` (all three run the defaulted S3 client) → `visibility` → `booking-bridge` → `auth`. Per app: recompile, then verify (a) a clean application boot — D-1 failed at client construction, so booting is the signal — and (b) S3 and DynamoDB round-trips. **`booking`'s `S3ArchiveHandler` Lambda needs its own check**; it builds an S3 client through the same defaulted path and does not follow the service release train.

---

## 7. Verification

| Module | Result |
|---|---|
| `cloud-sdk-api` | 61 tests, 0 failures |
| `cloud-sdk-aws` | 964 tests, 0 failures |
| Full reactor | `mvn -DskipTests install` clean; `mvn verify` clean |

No pre-existing test was modified. All new coverage is additive.

---

## 8. Still deferred

Unchanged from [2026-08-14-cloud-sdk-defect-refactor.md](2026-08-14-cloud-sdk-defect-refactor.md) §6:

* **D-5** — retrying `Crc32MismatchException`. Genuine behaviour change; wants its own release. Note the mutual-exclusion trap in §2.3 before implementing.
* **`DynamoDbClientConfig.maxConnections`** — still unread by anything.
* **D-2 remainder** — `findAll()` still does an unbounded scan, guarded by a flag that defaults off.
* **D-3** — `query()` returns a bare `List<T>` with no pagination signal.
* **§3.4** — `S3StorageClient` write path throws bare `RuntimeException` where siblings throw `S3OperationException`; a possible NPE while logging an S3 error.
* **Client rebuild on pool death** — a stable façade over a `volatile SqsClient`.
* **japicmp / revapi in CI** — would have caught both 1.0.30 breaks automatically. Strongly recommended, independent of any release.

---

# 9. The change, as a diff

Aggregate against the 1.0.30 baseline `1e2fcd6`: **24 files, +1320 / −139.** Of that, 794 lines are new tests. The production diff is small; what follows is all of it that matters.

```
 cloud-sdk-api/                                                 (lifecycle only)
   config/CloudResource.java                         |  24 ++      NEW
   config/ManagedCloudResource.java                  |  53 ++      NEW
   messaging/api/MessagingClient.java                |  10 +-
   storage/api/StorageClient.java                    |   4 +-
   notification/api/NotificationService.java         |   3 +-
   email/api/EmailService.java                       |   3 +-
 cloud-sdk-aws/
   aws/config/AwsHttpDefaults.java                   |  61 ++      NEW
   aws/config/AwsHttpClientWrapper.java              | 292 +++--   rewritten
   storage/factory/S3ClientFactory.java              |  20 +-
   database/factory/DynamoRepositoryFactory.java     |  27 +-
   messaging/factory/MessagingClientFactory.java     |  48 +-
   notification/factory/NotificationClientFactory.java|  28 +-
   storage/factory/TransferManagerFactory.java       |  27 +-
   email/factory/EmailClientFactory.java             |   4 +
   paramstore/factory/ParameterStoreClientFactory.java|  13 +-
   storage/config/AwsStorageConfig.java              |  16 +-
   storage/util/StorageConfigConstants.java          |  17 +
   messaging/aws/impl/SqsMessagingClient.java        |  13 +-      (Javadoc only)
 pom.xml                                             |   2 +-
```

Note `aws/config/BaseAwsConfig.java` and `database/config/DynamoDbClientConfig.java` do **not** appear — commit 6 returned them to their 1.0.30 state.

### 9.1 The units bug

```diff
  // S3ClientFactory.createHttpClient() — the copy that was live in production
  private static ApacheHttpClient createHttpClient() {
-     return (ApacheHttpClient) ApacheHttpClient.builder()
-         .maxConnections(DEFAULT_MAX_CONNECTIONS)
-         .connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))          // 83 min
-         .socketTimeout(Duration.ofSeconds(DEFAULT_SOCKET_TIMEOUT_SECONDS))
-         .connectionAcquisitionTimeout(Duration.ofMinutes(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
-         .build();                                                                          // 6.9 days
+     return (ApacheHttpClient) AwsHttpDefaults.syncBuilder().build();
  }
```

```diff
+ // NEW — AwsHttpDefaults: units live in the type, not the name
+ public static final int MAX_CONNECTIONS = 50;
+ public static final Duration CONNECTION_TIMEOUT = Duration.ofSeconds(5);
+ public static final Duration SOCKET_TIMEOUT = Duration.ofSeconds(30);
+ public static final Duration CONNECTION_ACQUISITION_TIMEOUT = Duration.ofSeconds(10);
+ public static final int MAX_ASYNC_CONCURRENCY = 100;
+
+ public static ApacheHttpClient.Builder syncBuilder() { ... }
+ public static AwsCrtAsyncHttpClient.Builder asyncBuilder() { ... }
+ public static AwsHttpClientWrapper sync() / async() { ... }
```

The identical three-line collapse applies to `MessagingClientFactory`, `NotificationClientFactory` and `DynamoRepositoryFactory`. `AwsHttpClientWrapper.defaultSyncClient()` / `defaultAsyncClient()` become one-line delegations — which is what makes the tuned values reachable.

### 9.2 D-1 — the call-site shape, before and after

Six factories all looked like this:

```diff
- .httpClient(config.getHttpClient() != null
-     ? config.getHttpClient().getTypedClient()          // unchecked; T inferred at the call site
-     : createHttpClient());                             // → ClassCastException in builder mode
+ .overrideConfiguration(createOverrideConfig(config));
+
+ AwsHttpClientWrapper.applyToSync(config.getHttpClient(), builder, XxxFactory::createHttpClient);
```

`S3ClientFactory` — the one factory that *did* branch — collapses just as far:

```diff
- if (config.getHttpClient() != null) {
-     if (config.getHttpClient().isBuilder()) {
-         builder.httpClientBuilder(config.getHttpClient().getTypedClient());
-     } else {
-         builder.httpClient(config.getHttpClient().getTypedClient());
-     }
- } else {
-     builder.httpClient(createHttpClient());
- }
+ AwsHttpClientWrapper.applyToSync(config.getHttpClient(), builder, S3ClientFactory::createHttpClient);
```

and the decision moves inside the wrapper, where the runtime type is actually known:

```diff
+ public enum Mode { SYNC_INSTANCE, SYNC_BUILDER, ASYNC_INSTANCE, ASYNC_BUILDER }
+
+ public void applyToSync(SdkSyncClientBuilder<?, ?> clientBuilder) {
+     switch (mode) {
+         case SYNC_INSTANCE -> clientBuilder.httpClient((SdkHttpClient) underlyingClient);
+         case SYNC_BUILDER  -> clientBuilder.httpClientBuilder((SdkHttpClient.Builder<?>) underlyingClient);
+         default -> throw new IllegalStateException("Cannot apply an asynchronous HTTP client (" + describe() + ") ...");
+     }
+ }

  public <T> T getTypedClient() {
-     try {
-         return (T) underlyingClient;
-     } catch (ClassCastException e) {                    // D-10: unreachable — erasure puts the
-         ...                                             // checkcast in the CALLER's bytecode
-     }
+     return (T) underlyingClient;                        // @Deprecated
  }
```

SES and SSM gain the line they never had:

```diff
  SesV2ClientBuilder builder = SesV2Client.builder()
      .region(...).credentialsProvider(...);
+ AwsHttpClientWrapper.applyToSync(config.getHttpClient(), builder, AwsHttpDefaults.syncBuilder()::build);
```

### 9.3 Lifecycle

```diff
- public interface MessagingClient<T> extends AutoCloseable {
+ public interface MessagingClient<T> extends CloudResource {
      ...
-     /** Closes the messaging client and releases its resources. */
-     @Override
-     void close();                                       // abstract → AbstractMethodError risk
  }

+ public interface CloudResource {
+     default void close() { }                            // NOT AutoCloseable, on purpose
+ }
```

### 9.4 The DynamoDB pool, withdrawn (commit 6)

```diff
- /** DynamoDB is the highest-fan-out client in these services and gets a larger pool. */
- public static final int DYNAMODB_MAX_CONNECTIONS = 100;
- public static ApacheHttpClient.Builder dynamoDbSyncBuilder() { ... }
- public static AwsHttpClientWrapper dynamoDbSync() { ... }

  // BaseAwsConfig — back to its 1.0.30 form
- this.httpClient = builder.httpClient != null ? builder.httpClient : builder.defaultHttpClient(useAsyncClient);
+ this.httpClient = builder.httpClient != null ? builder.httpClient
+     : (useAsyncClient ? AwsHttpClientWrapper.defaultAsyncClient() : AwsHttpClientWrapper.defaultClient());

  // BaseAwsConfigBuilder
- protected AwsHttpClientWrapper defaultHttpClient(boolean async) { ... }

  // DynamoDbClientConfig.Builder
- @Override
- protected AwsHttpClientWrapper defaultHttpClient(boolean async) { ... }
```

---

# 10. Backward-compatibility audit — every mercury-services module

Verified by direct inspection of `C:\Users\arijit.kundu\projects\mercury-services` on 2026-08-16, not inferred from the design documents.

## 10.1 What was searched, and what was found

| Probe | Hits across the whole repository |
|---|---|
| `AwsHttpClientWrapper` | **2 files**, both `visibility` — `VisibilityApplicationInjector` (`:8, :85, :89, :90`) and its test (`:7, :57`) |
| `getTypedClient(` | **0** |
| `ofAsyncBuilder(` | **0** |
| `try (… MessagingClient / StorageClient / NotificationService / EmailService …)` | **0** |
| `.close()` on a cloud-sdk client | **1** — `VisibilityMessagingModule:65` |
| `implements` a cloud-sdk client interface | **1** — `booking/src/test/…/FlowStep.java:440` (`EmailServiceTestImpl implements EmailService`) |
| `.httpClient(` on any cloud-sdk config | **1** — `VisibilityApplicationInjector:80` |
| `DynamoDbClientConfig` built **with** an explicit HTTP client | **0** |
| YAML/properties binding HTTP pool or timeout settings | **0** — configuration is programmatic only |

The only two API surfaces this release touches that anyone actually uses are `ofSyncBuilder` (visibility, S3) and `close()` (visibility, SQS). Both are preserved exactly.

## 10.2 Per-module verdict

Modules are grouped by whether they consume the cloud-sdk line (`1.0.2x-SNAPSHOT`) or the legacy `commons` line (`1.R.x`, no cloud-sdk dependency).

| Module | Pins today | Uses cloud-sdk? | Source change needed | Recompile needed | Runtime change |
|---|---|---|---|---|---|
| `visibility` | 1.0.29-SNAPSHOT | ✅ S3 (builder mode), SQS, DynamoDB | **None** | Recommended | **None** — its S3 transport is caller-supplied and wins; SQS/DynamoDB connect 2 s → 5 s |
| `bill-of-lading-v2` | 1.0.28-SNAPSHOT | ✅ S3 default client | **None** | Recommended | **S3 connect 83 min → 5 s, acquire 6.9 days → 10 s** |
| `rates` | 1.0.28-SNAPSHOT | commons only | **None** | Recommended | None |
| `value-added-service` | 1.0.28-SNAPSHOT | commons only | **None** | Recommended | None |
| `watermill-publisher/watermill-commons` | 1.0.28-SNAPSHOT | commons only | **None** | Recommended | None |
| `booking` | 1.0.27-SNAPSHOT | ✅ S3 default ×2 (incl. Lambda), SQS, SNS | **None** | Recommended | **S3 connect 83 min → 5 s, acquire 6.9 days → 10 s**; SQS/SNS connect 2 s → 5 s |
| `tx-tracking` | 1.0.27-SNAPSHOT | ✅ S3 default, SQS, SES | **None** | Recommended | **S3 as above**; SES now honours a configured client (none configured → no change bar connect 2 s → 5 s) |
| `booking-bridge` | 1.0.27-SNAPSHOT | ✅ SQS | **None** | Recommended | Connect 2 s → 5 s |
| `auth` | 1.0.27-SNAPSHOT | ✅ DynamoDB | **None** | Recommended | Connect 2 s → 5 s. **Pool unchanged at 50.** |
| `network` | 1.0.27-SNAPSHOT | commons only | **None** | Recommended | None |
| `registration` | 1.0.27-SNAPSHOT | commons only | **None** | Recommended | None |
| `db-migration` | 1.0.27-SNAPSHOT | commons only | **None** | Recommended | None |
| `webbl` | 1.0.26-SNAPSHOT | ✅ cloud-sdk | **None** | Recommended | Connect 2 s → 5 s |
| `self-service-reports` | 1.0.26-SNAPSHOT | commons only | **None** | Recommended | None |
| `bill-of-lading` | 1.R.01.021 | ❌ legacy `dynamo-client` | **None** | Not applicable | None |
| `oceanschedules`, `oceanschedules-process/common` | 1.R.01.025 | ❌ legacy | **None** | Not applicable | None |
| `partner-integrator/pi-commons`, `pi-bl-es-lambda` | 1.R.01.025 / .023 | ❌ legacy | **None** | Not applicable | None |
| `shipping-instruction` | 1.R.01.023 | ❌ legacy | **None** | Not applicable | None |
| `booking-downstream-processor/booking-cargoscreen` | 1.R.01.023 | ❌ legacy | **None** | Not applicable | None |
| `lambda/auth-tokens-archive` | 1.R.01.013 | ❌ legacy | **None** | Not applicable | None |

"Recompile recommended" rather than required: the bridge overloads mean stale bytecode still links. Recompiling is simply how a module picks up the fixes.

## 10.3 Configuration settings — what changed

**No module needs to change a single configuration value, YAML key, environment variable or system property.** There are no new settings, no renamed settings, and no removed settings.

| Setting | Where it lives | Change in 1.0.31 | Action for consumers |
|---|---|---|---|
| Connection pool size (`maxConnections`) | `AwsHttpDefaults.MAX_CONNECTIONS` | **No change** — 50 before, 50 after, every service including DynamoDB | **None** |
| Connect timeout | `AwsHttpDefaults.CONNECTION_TIMEOUT` | 2 s (SDK default, silently applied) → **5 s** | **None** — more tolerant, not less |
| Socket timeout | `AwsHttpDefaults.SOCKET_TIMEOUT` | **No change** — 30 s | **None** |
| Connection-acquisition timeout | `AwsHttpDefaults.CONNECTION_ACQUISITION_TIMEOUT` | **No change** at 10 s, except the defaulted S3 client where it was 6.9 days → 10 s | **None** |
| S3 default client connect timeout | `S3ClientFactory.createHttpClient()` | **83 min → 5 s** (units defect) | **None** — smoke-test S3 |
| Async concurrency | `AwsHttpDefaults.MAX_ASYNC_CONCURRENCY` | **No change** — 100 | **None** — no consumer builds async clients |
| `DynamoDbClientConfig.maxConnections(...)` | Builder setter | **No change** — still unread by the library | **None** — nobody calls it |
| `AwsMessagingClientConfig.maxConnections(...)` | Builder setter, used by `visibility-pending-start/HandlerSupport:62` | **No change** in how it is read | **None** |
| Any Dropwizard YAML key | — | **No change** — none of these settings are externalised | **None** |
| `mercury.commons.version` | Each module's `pom.xml` | `1.0.2x-SNAPSHOT` → `1.0.31-SNAPSHOT` | **The only edit any module makes** |

## 10.4 The two real call sites, checked line by line

**`visibility` — S3 builder mode** (`VisibilityApplicationInjector:89-94`):

```java
static AwsHttpClientWrapper buildS3HttpClientWrapper() {
    return AwsHttpClientWrapper.ofSyncBuilder(
            ApacheHttpClient.builder()
                    .connectionTimeout(S3_CONNECTION_TIMEOUT)
                    .socketTimeout(S3_SOCKET_TIMEOUT)
                    .maxConnections(S3_MAX_CONNECTIONS));
}
```

The argument is an `ApacheHttpClient.Builder`, so it binds to the retained bridge overload — identical descriptor, identical behaviour, no recompile needed. `VisibilityApplicationInjectorTest:57` asserts `wrapper.isBuilder()`, which is retained as a derived getter and still returns `true`. This transport is caller-supplied, so §9.1's default-tuning changes do not touch it.

**`visibility` — SQS lifecycle** (`VisibilityMessagingModule:65`):

```java
environment.lifecycle().manage(new Managed() {
    @Override public void start() { }
    @Override public void stop() { messagingClient.close(); }
});
```

`close()` is still declared on `MessagingClient` (inherited from `CloudResource`) and still overridden by `SqsMessagingClient`, so this compiles and dispatches identically. Adopting `ManagedCloudResource.of(...)` is optional.

**`booking` — test implementor** (`FlowStep.java:440`): `EmailServiceTestImpl implements EmailService` does not declare `close()`. Under 1.0.30's abstract-method approach this would have been a compile error; with `CloudResource`'s `default` body it inherits a no-op and compiles unchanged. This is precisely the breakage class the lifecycle redesign withdraws.

