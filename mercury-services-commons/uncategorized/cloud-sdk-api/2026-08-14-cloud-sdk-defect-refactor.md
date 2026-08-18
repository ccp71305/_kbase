# ION-16431 follow-up — D-1, D-5, D-10/D-11, and client lifecycle

**Author:** Arijit Kundu · **Date:** 2026-08-14
**Repo:** `mercury-services-commons`, branch `feature/ION-12310-commons-cloudsdk-refactoring`
**Source document:** `mercury-services/visibility/docs/2026-08-12-visibility-shared-http-client-dynamo-refactoring.md` §6 (Defect Register)
**AWS SDK v2 version in scope:** `software.amazon.awssdk:bom:2.30.24` (declared in `cloud-sdk-aws/pom.xml`)

This document answers four questions raised against the defect register:

1. **D-1** — explain the breaking change in plain terms, and give the *complete* Option A change set (no per-factory branching), including how `mercury-services` modules call and initialise it.
2. **D-5** — how do we add a retry predicate for `Crc32MismatchException`?
3. **D-11 / D-10** — "this is unit tested, why is it dead code?"
4. **`MessagingClient extends AutoCloseable`** (§4) — does `close()` help the `mercury-services` modules, what leak is actually saved, is it a breaking API change, and what is the best way to introduce lifecycle into `cloud-sdk-api`?

Sections **§1–§4** are the technical analysis. **§5** narrows it to what actually ships in `1.0.31-SNAPSHOT` — D-1 Option A, the HTTP-timeout units fix with reachable tuned defaults (§1.7), and the lifecycle redesign — **§6** records everything deferred, and **§7** is copy-ready announcement text for the `1.0.30-SNAPSHOT` release.

Everything asserted here about SDK behaviour was verified by decompiling the jars in the local `~/.m2` repository at version 2.30.24. The commands are in Appendix A.

---

## 0. Summary of conclusions

| Item | Conclusion |
|---|---|
| **D-1** | Real. `AwsHttpClientWrapper` has 4 legal states but only 2 are honoured, and only by `S3ClientFactory`. Every other factory funnels the wrapper through `getTypedClient()` straight into `.httpClient(...)`, so a builder-mode wrapper becomes `ClassCastException` at client construction. Fix: move the "instance vs builder" decision *into the wrapper* (`applyToSync` / `applyToAsync`). Call sites become one line each. |
| **D-1 correction** | The source document's Option A sketch puts `applyToSync` on `CloudHttpClient` (in `cloud-sdk-api`). **That will not compile** — `cloud-sdk-api` has no AWS SDK dependency and must stay provider-neutral. The methods belong on `AwsHttpClientWrapper`. This costs nothing: every AWS config already returns `AwsHttpClientWrapper`, not `CloudHttpClient`. |
| **D-1 correction** | `EmailClientFactory` (SES) and `ParameterStoreClientFactory` (SSM) are **not** affected by the `ClassCastException` — they never call `.httpClient(...)` at all. They have a *different* defect: they silently discard a configured HTTP client. |
| **D-5** | Root cause confirmed at bytecode level, and it is **not** what the register implies. `Crc32MismatchException.retryable()` returns `true`, but the SDK's default retry predicate (`RetryUtils.isRetryableException`) only consults `retryable()` on `SdkServiceException`. `Crc32MismatchException` extends `SdkClientException`, so its own `retryable()` flag is never read, and it is not in the SDK's `RETRYABLE_EXCEPTIONS` set either. It is unretryable by construction, on every AWS SDK v2 client, not just DynamoDB. |
| **D-1 root cause** | Not "the field is `Object`". `underlyingClient` has been `Object` since ION-11759, and pre-PR #46 that was safe: `ofSync`/`ofAsync` both enforced `instanceof`, giving a construction-time invariant that `isAsync` alone fully described the contents. PR #46 added two factory methods with **no** `instanceof` validation, breaking that invariant and adding a second discriminator — without updating any of the six callers that relied on the old one. See §1.0. |
| **D-10** | The dead-code finding is **D-10**, not D-11. The `try/catch (ClassCastException)` in `AwsHttpClientWrapper.getTypedClient()` is unreachable. The unit test that appears to cover it passes for a different reason: the `checkcast` is emitted in the *test's* bytecode, not the method's. Proof in §3. **Predates PR #46** — it is not a regression from that change. |
| **D-11** | ✅ **Closed — already committed in 1.0.30.** `"Unexpected error during S3 read"` → `"Unexpected error during S3 write"` at `S3StorageClient.java:720`. One residual inconsistency remains, deferred to §6.1 (see §3.4). |
| **Units bug** 🔴 | Found during this review, **not** an ION-16431 regression, and **live in production**. `S3ClientFactory.createHttpClient()` applies `ofSeconds`/`ofMinutes` to `…_MILLIS` constants → every `StorageClientFactory.createDefaultS3Client()` client runs with an **83-minute connect** and **6.9-day connection-acquisition** timeout. Reached by `booking` ×2 (incl. a Lambda), `bill-of-lading-v2`, `tx-tracking`. Highest-severity item here. Fixed in 1.0.31 — §1.7. |
| **Release scope** | `1.0.31-SNAPSHOT` carries D-1 Option A, the units fix + reachable tuned defaults (§1.7), and the `CloudResource` lifecycle redesign. **No source change in any consumer; recompile required.** §1.7 changes runtime timeouts deliberately — smoke-test. D-5, `findAll()`, and all `mercury-services` items are deferred — §6. |
| **`AutoCloseable`** | Defensible but oversold, and **its Javadoc is false**. `SqsMessagingClient.close()` claims to close "the underlying SqsClient and its connection pools"; verified, it does not close the pool — `httpClient(instance)` wraps the transport in `NonManagedSdkHttpClient`, whose `close()` is `return;`. Only builder mode would, which makes **D-1's Option A a prerequisite for `close()` to mean anything**. Real value is multi-instance test harnesses, not production sockets. Breaking twice over, and only 1 of 5 modules calls it. Recommended replacement in §4.5. |

---

# 1. D-1 — builder mode is honoured by exactly one factory out of six

## 1.0 Foundation — what `underlyingClient` is, and what PR #46 actually changed

Everything in D-1 follows from one field, so it is worth being exact about it — including about what PR #46 did and did not do to it.

### The field

```java
public class AwsHttpClientWrapper implements CloudHttpClient {
    private final Object underlyingClient;   // ← type Object
    @Getter private final boolean isAsync;
    @Getter private final boolean isBuilder; // ← added by PR #46
```

`underlyingClient` is a box. Whatever you hand to one of the static factory methods is stored there, and the box forgets what kind of thing it was. The only surviving record is the booleans beside it.

### A client and a builder-for-a-client are unrelated types

This is the distinction the whole defect turns on:

```java
ApacheHttpClient.Builder recipe = ApacheHttpClient.builder().maxConnections(50);
// runtime class: software.amazon.awssdk.http.apache.ApacheHttpClient$DefaultBuilder
// Holds SETTINGS. No sockets, no connection pool. Cannot send a request.

SdkHttpClient live = recipe.build();
// runtime class: software.amazon.awssdk.http.apache.ApacheHttpClient
// A LIVE client owning a PoolingHttpClientConnectionManager. Can send requests.
```

Separate `.class` files in `apache-client-2.30.24.jar`, and — verified by `javap` — separate hierarchies:

```
ApacheHttpClient            implements SdkHttpClient                      →  SdkAutoCloseable
ApacheHttpClient$Builder    extends    SdkHttpClient$Builder<...>         →  SdkBuilder
```

`ApacheHttpClient$DefaultBuilder` **is not an** `SdkHttpClient`. Casting one to the other is as illegal as `String` → `Integer`, and that cast is what fails at `DynamoRepositoryFactory` bytecode offset 59.

### Why the field cannot simply be narrowed

There is no type below `Object` that fits all four possible contents:

| Content | Supertype chain |
|---|---|
| `SdkHttpClient` | → `SdkAutoCloseable` |
| `SdkAsyncHttpClient` | → `SdkAutoCloseable` |
| `SdkHttpClient.Builder<T>` | → `SdkBuilder<T, SdkHttpClient>` |
| `SdkAsyncHttpClient.Builder<T>` | → `SdkBuilder<T, SdkAsyncHttpClient>` |

The two clients share `SdkAutoCloseable`. The two builders share `SdkBuilder`. Clients and builders share **nothing but `Object`**. So "just give the field a proper type" is not available as a fix.

### ⚠️ Correcting the obvious-but-wrong reading: `Object` is not PR #46's doing

`underlyingClient` has been `Object` since the original ION-11759 refactor, long before PR #46 (`a4b6d11`). So were the unchecked `getTypedClient()` and its dead `try/catch` (**D-10 is therefore not a PR #46 regression — it predates it**), and so was the `defaultAsyncClient()` units bug noted in §1.1.

Here is the wrapper as it stood at `a4b6d11^` — immediately before PR #46:

```java
private final Object underlyingClient;              // already Object
@Getter private final boolean isAsync;              // ONE discriminator

public static AwsHttpClientWrapper ofSync(Object client) {
    if (client == null) throw new IllegalArgumentException("Sync HTTP client must not be null");
    if (!(client instanceof SdkHttpClient))                                    // ← VALIDATED
        throw new IllegalArgumentException("Client must be either SdkHttpClient or SdkAsyncHttpClient");
    return new AwsHttpClientWrapper(client, false);
}

public static AwsHttpClientWrapper ofAsync(Object client) {
    if (client == null) throw new IllegalArgumentException("Async HTTP client must not be null");
    if (!(client instanceof SdkAsyncHttpClient))                               // ← VALIDATED
        throw new IllegalArgumentException("Client must be either SdkHttpClient or SdkAsyncHttpClient");
    return new AwsHttpClientWrapper(client, true);
}
```

Those two `instanceof` checks are the point. They enforced a **construction-time invariant**:

> `underlyingClient` is an `SdkHttpClient` whenever `isAsync == false`, and an `SdkAsyncHttpClient` whenever `isAsync == true`. Always. There is no third possibility.

Under that invariant the unchecked cast in `getTypedClient()` was *provably safe* for every caller that respected `isAsync` — and every factory did, implicitly, by only ever building sync clients and only ever asking for `SdkHttpClient`. The field was loosely typed, but the invariant closed the gap at the boundary where values entered. `Object` was untidy (`SdkAutoCloseable` would have covered both cases), not dangerous.

> **This does not mean the `try/catch` in `getTypedClient()` was working pre-#46 (D-10).** Two different subjects with independent causes, easily conflated:
>
> | Property | Caused by | Depends on the invariant? |
> |---|---|---|
> | The **catch** is unreachable | **Type erasure.** The method's descriptor is `()Ljava/lang/Object;`, so javac emits no `checkcast` inside it; the try region is `aload_0; getfield; areturn`. See §3.2. | **No** — nothing to do with the box's contents |
> | The **cast** is safe | **The `instanceof` invariant** — contents always matched what callers asked for | **Yes** |
>
> Remove the invariant and the catch is still dead. The catch was equally dead before and after PR #46.
>
> The existing test proves it *on the pre-#46 code*: `shouldThrowClassCastExceptionForIncorrectType` builds a sync wrapper and requests the async type — caller error, not an invariant violation, so a `ClassCastException` was reachable even then. The catch still did not fire; the CCE came from the test's own `checkcast` and the custom message never appeared.
>
> | | Catch reachable? | Could a CCE occur anywhere? | Verdict on the catch |
> |---|---|---|---|
> | Pre-#46 | No — dead | Only via caller error | Harmless clutter — a guard for a hazard that could not arise |
> | Post-#46 | No — dead | **Yes, routinely**, at the caller's `checkcast` | **Actively misleading** — looks like a guard, is not one, and a test asserts it works |
>
> Only the last column changed. Stated plainly: the `try/catch` was dead code in an era when it was also unnecessary; PR #46 removed the invariant, making a guard like it necessary. The dead code is still dead — what changed is that its absence now matters.

### What PR #46 actually changed

It added two more factory methods — with **no `instanceof` validation at all**:

```java
public static AwsHttpClientWrapper ofSyncBuilder(ApacheHttpClient.Builder httpClientBuilder) {
    if (httpClientBuilder == null) throw new IllegalArgumentException(...);   // null check only
    return new AwsHttpClientWrapper(httpClientBuilder, false, true);
}

public static AwsHttpClientWrapper ofAsyncBuilder(Object httpClientBuilder) {
    if (httpClientBuilder == null) throw new IllegalArgumentException(...);   // null check only
    return new AwsHttpClientWrapper(httpClientBuilder, true, true);           // param is Object!
}
```

`ofSyncBuilder` at least has a typed parameter. `ofAsyncBuilder(Object)` accepts literally anything — `ofAsyncBuilder("hello")` constructs a wrapper successfully and fails much later, somewhere else.

Three consequences, in order of importance:

1. **The invariant is gone.** `isAsync == false` no longer implies `SdkHttpClient`; it now means "sync, and it could be either a client or a builder."
2. **A second discriminator appeared.** Correct use now requires reading `isAsync` *and* `isBuilder`. Neither is enough alone.
3. **No existing caller was updated.** Six factories still read `isAsync` or nothing at all — which was sufficient before, and silently is not now.

| | Before PR #46 | After PR #46 |
|---|---|---|
| Legal contents of the box | 2 | 4 |
| Validated at construction | 2 of 2 ✅ | 2 of 4 ⚠️ |
| Discriminators a caller must read | `isAsync` | `isAsync` **and** `isBuilder` |
| Call sites reading them correctly | all | **1 of 6** (`S3ClientFactory`) |

> **The defect is not "the field is `Object`."** It is: **an invariant that made the `Object` field safe was removed, and the code that depended on that invariant was not updated.** The untyped field is the pre-existing condition; PR #46 is what made it load-bearing.

### Why this framing determines the fix

If the problem were "the field is too loose," the fix would be to narrow it — and as shown above, you cannot.

Because the real problem is a *lost invariant*, the fix is to establish one that holds across all four states. Option A (§1.2) does exactly that: it moves the only operation that depends on the distinction — attaching the transport to an SDK client builder — inside the wrapper, where both the discriminators and the real runtime class are known. The new invariant becomes:

> A wrapper always attaches itself to a client builder correctly, or fails at that point with a message naming its actual state.

That is enforceable inside the class and impossible for a caller to violate, because there is no longer a cast for a caller to get wrong. The `Mode` enum makes the four states explicit and exhaustive so a `switch` is forced to cover them, and tightening `ofAsyncBuilder(Object)` → `SdkAsyncHttpClient.Builder<?>` restores construction-time validation to the two states PR #46 left unchecked.

## 1.1 What the defect actually is, in plain terms

`AwsHttpClientWrapper` is a small box that carries "the HTTP client you want this AWS service client to use". Before PR #46 the box could hold exactly two kinds of thing:

* a **pre-built sync client** (`SdkHttpClient`), or
* a **pre-built async client** (`SdkAsyncHttpClient`).

PR #46 added a second dimension — *builder mode* — so the box can now also hold:

* a **sync client builder** (`ApacheHttpClient.Builder`), or
* an **async client builder** (any `Object`, unvalidated).

Four legal states, tracked by two independent booleans:

```java
// cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/AwsHttpClientWrapper.java
private final Object  underlyingClient;   // instance OR builder — untyped
@Getter private final boolean isAsync;
@Getter private final boolean isBuilder;  // added by PR #46
```

The problem is that **only `S3ClientFactory` reads `isBuilder`.** It branches correctly:

```java
// S3ClientFactory.java:53-62
if (config.getHttpClient() != null) {
    if (config.getHttpClient().isBuilder()) {
        builder.httpClientBuilder(config.getHttpClient().getTypedClient());   // ✅ builder mode
    } else {
        builder.httpClient(config.getHttpClient().getTypedClient());          // ✅ instance mode
    }
} else {
    builder.httpClient(createHttpClient());
}
```

Every other factory does only the second half:

```java
// DynamoRepositoryFactory.java:319-321
.httpClient(config.getHttpClient() != null
    ? config.getHttpClient().getTypedClient()
    : createHttpClient());
```

### Why this compiles and then explodes at runtime

`getTypedClient()` is declared as:

```java
@SuppressWarnings("unchecked")
public <T> T getTypedClient() {
    return (T) underlyingClient;   // unchecked cast — T is inferred at the CALL SITE
}
```

`T` is inferred from the *target type* of the expression. In `.httpClient(x)`, the parameter type is `SdkHttpClient`, so javac infers `T = SdkHttpClient` and the call compiles with **no type error whatsoever**. The compiler cannot know that the box actually contains an `ApacheHttpClient.Builder`.

At runtime javac inserts a `checkcast SdkHttpClient` at the call site. `ApacheHttpClient.Builder` is not an `SdkHttpClient`, so:

```
java.lang.ClassCastException: class software.amazon.awssdk.http.apache.ApacheHttpClient$DefaultBuilder
    cannot be cast to class software.amazon.awssdk.http.SdkHttpClient
        at com.inttra.mercury.cloudsdk.database.factory.DynamoRepositoryFactory.createDynamoDbClient(...)
```

This is thrown **during Guice module construction / application startup**, not on the first DynamoDB call. The service fails to boot, with a stack trace pointing at the factory rather than at the config that caused it.

> **The one-sentence version:** PR #46 added a new kind of value to a shared, untyped box, taught exactly one of six consumers to recognise it, and relied on an unchecked generic cast that hides the mismatch from the compiler. The safety net that was supposed to catch it — the `try/catch (ClassCastException)` inside `getTypedClient()` — does not work either (that is D-10, §3).

### The exact blast radius, verified against the current tree

| # | Call site | Kind | What happens with a builder-mode wrapper |
|---|---|---|---|
| 1 | `S3ClientFactory.createConfiguredClient` L53-62 | sync | ✅ **Works** — the only site that branches |
| 2 | `DynamoRepositoryFactory.createDynamoDbClient` L319-321 | sync | ❌ `ClassCastException` at `.httpClient(...)` |
| 3 | `MessagingClientFactory.createConfiguredClient` L88-90 | sync | ❌ `ClassCastException` |
| 4 | `MessagingClientFactory` (extended/S3-payload SQS) L281-283 | sync | ❌ `ClassCastException` |
| 5 | `NotificationClientFactory.createConfiguredClient` L72-73 | sync | ❌ `ClassCastException` |
| 6 | `TransferManagerFactory.resolveAsyncHttpClient` L75-80 | async | ❌ `ClassCastException` at the `return` statement (method returns `SdkAsyncHttpClient`) |
| 7 | `AwsStorageConfig.getHttpClientForTesting` L85-95 | sync | ❌ `ClassCastException` at `return` — instead of the documented `IllegalStateException` |
| 8 | `AwsStorageConfig.getAsyncHttpClientForTesting` L104-113 | async | ❌ same |
| 9 | `EmailClientFactory.createSesV2Client` L134-151 | — | ⚠️ **No CCE — because it never calls `.httpClient(...)` at all.** A configured HTTP client is silently ignored. |
| 10 | `ParameterStoreClientFactory` L24-30 | — | ⚠️ Same — silently ignored |

**Correction to the register:** §7.1 lists `EmailClientFactory` and `ParameterStoreClientFactory` among the factories that need the branch replicated. They do not have the branch *or* the bug, because they never consume `config.getHttpClient()`. They have a quieter defect — a caller who tunes timeouts/pool size for SES or SSM gets AWS SDK defaults and no warning. Option A fixes both classes of problem in the same edit.

### Why the wrapper is not null-safe-by-accident

`BaseAwsConfig` never leaves `httpClient` null:

```java
// BaseAwsConfig.java:32-34
this.httpClient = builder.httpClient != null
    ? builder.httpClient
    : (useAsyncClient ? AwsHttpClientWrapper.defaultAsyncClient() : AwsHttpClientWrapper.defaultClient());
```

All six configs (`AwsStorageConfig`, `DynamoDbClientConfig`, `AwsMessagingClientConfig`, `NotificationClientConfig`, `AwsSesEmailConfig`, `AwsParameterStoreConfig`) extend `BaseAwsConfig` and call `super(builder, ...)`, so `getHttpClient()` is **never null** for any config built through the normal path. (The only way to observe null is a Mockito mock of the config, which is why the tests never noticed.)

The `config.getHttpClient() != null ? ... : createHttpClient()` ternary therefore **always takes the first branch**. That much is straightforward. The part worth being precise about is *what is on that branch*.

### Which branch carries the tuning — it is not the one that runs

The natural reading is: "the wrapper is always present, so the wrapper's client is what gets used, and that is the tuned one." The first half is right and the second is backwards. `BaseAwsConfig`'s fallback is:

```java
// BaseAwsConfig.java:34  →  AwsHttpClientWrapper.defaultClient()
public static AwsHttpClientWrapper defaultSyncClient() {
    return ofSync(ApacheHttpClient.builder().build());   // ← no tuning calls at all
}
```

`ApacheHttpClient.builder().build()` sets nothing. `ApacheHttpClient$DefaultBuilder.buildWithDefaults` merges `standardOptions` (empty here) with `SdkHttpConfigurationOption.GLOBAL_HTTP_DEFAULTS`, so the result is pure AWS SDK defaults.

The tuning constants are referenced **only** inside each factory's private `createHttpClient()` — the branch that is never reached:

```java
// DynamoRepositoryFactory.java:412-419 — the tuned client, never constructed on the config path
private static ApacheHttpClient createHttpClient() {
    return (ApacheHttpClient) ApacheHttpClient.builder()
        .maxConnections(DEFAULT_MAX_CONNECTIONS)                                        // 100
        .connectionTimeout(Duration.ofMillis(DEFAULT_CONNECTION_TIMEOUT_MILLIS))        // 5 s
        .socketTimeout(Duration.ofSeconds(DEFAULT_SOCKET_TIMEOUT_SECONDS))              // 30 s
        .connectionAcquisitionTimeout(Duration.ofMillis(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
        .build();                                                                       // 10 s
}
```

Side by side, for a `DynamoDbClientConfig` built without an explicit `.httpClient(...)`:

| Setting | **Actually applied** (`BaseAwsConfig` → `defaultSyncClient()`) | **Intended** (`DynamoRepositoryFactory.createHttpClient()`) |
|---|---|---|
| `maxConnections` | **50** (SDK `GLOBAL_HTTP_DEFAULTS`) | **100** |
| `connectionTimeout` | **2 s** | **5 s** |
| `socketTimeout` (read/write) | 30 s | 30 s |
| `connectionAcquisitionTimeout` | 10 s | 10 s |

SQS and SNS are the same story with `maxConnections = 50` on both sides, so only `connectionTimeout` (2 s vs 5 s) diverges there.

SDK default values verified from `SdkHttpConfigurationOption.GLOBAL_HTTP_DEFAULTS` bytecode: `MAX_CONNECTIONS = 50` (`bipush 50`), `DEFAULT_CONNECTION_TIMEOUT = 2 s`, `DEFAULT_SOCKET_READ/WRITE_TIMEOUT = 30 s`, `DEFAULT_CONNECTION_ACQUIRE_TIMEOUT = 10 s`.

> **The finding, stated exactly:** the per-factory tuning constants in `DynamoRepositoryFactory`, `MessagingClientFactory` and `NotificationClientFactory` are unreachable for any caller that builds a config through `BaseAwsConfig` without an explicit `.httpClient(...)`. Those services run on SDK defaults. The gap is modest (DynamoDB gets half the intended connection pool and a 2 s instead of 5 s connect timeout) but it is silent, and it means the constants are documentation rather than configuration.

### ⚠️ Before making that fallback reachable — it has a units bug

**Do not simply "wire the fallback up" as a fix.** Two of these methods pass a `…_MILLIS` constant to a `Duration` factory that is not milliseconds:

```java
// S3ClientFactory.java:113-120
.connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))               // ofSeconds(5000)  = 5 000 s  ≈ 83 min
.connectionAcquisitionTimeout(Duration.ofMinutes(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
                                                                                        // ofMinutes(10000) = 10 000 min ≈ 6.9 days

// AwsHttpClientWrapper.java:84-91  (defaultAsyncClient)
.connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))               // ofSeconds(5000)  = 5 000 s
.connectionAcquisitionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
                                                                                        // ofSeconds(10000) ≈ 2 h 47 min
```

Both constants are `5000` and `10000` in `StorageConfigConstants`, named `…_MILLIS`. `DynamoRepositoryFactory`, `MessagingClientFactory` and `NotificationClientFactory` use `Duration.ofMillis(...)` correctly; only these two do not.

**Reachability — and it is not merely theoretical:**

| Path | Live today? |
|---|---|
| `S3ClientFactory.createHttpClient()` via the config ternary | ❌ dead (the ternary never falls through) |
| `S3ClientFactory.createHttpClient()` via `StorageClientFactory.createDefaultS3Client()` → `S3ClientFactory.createDefaultS3Client():85` | ✅ **live, and actually reached in production** |
| `AwsHttpClientWrapper.defaultAsyncClient()` via `BaseAwsConfig` when `useAsyncClient == true` | ✅ live, but **no consumer reaches it** — no `TransferManager` or `withAsyncClient()` usage anywhere in `mercury-services` |

The S3 path is not a latent hazard. Four production call sites, in three services plus a Lambda, are running on it right now:

```
booking/config/BookingMessagingModule.java:81      StorageClientFactory.createDefaultS3Client()
booking/lambda/S3ArchiveHandler.java:99            StorageClientFactory.createDefaultS3Client()
bill-of-lading-v2/config/BillOfLadingInjector.java:84
tx-tracking/config/TxTrackingModule.java:77
```

Every one of those S3 clients has an **83-minute TCP connect timeout** and a **6.9-day connection-acquisition timeout**. Concretely: if the S3 endpoint blackholes, a thread blocks for up to 83 minutes instead of 5 seconds; if all 50 pooled connections are busy, a thread parks in `PoolingHttpClientConnectionManager.leaseConnection` for up to 6.9 days with no error, no timeout and no log line. That is functionally "block forever", and it is the single hardest failure shape to diagnose — precisely the class of hang that made ION-16431 take five days to understand. In `S3ArchiveHandler` it is worse still: a Lambda burns its entire billed duration on a hung connect.

> **This is not caused by ION-16431 and is not a regression from PR #46** — the units have been wrong since the constants were introduced. It is the highest-severity item found during this review, and §5 folds it into 1.0.31.

**The fix:**

```diff
// S3ClientFactory.createHttpClient()
-            .connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))
+            .connectionTimeout(Duration.ofMillis(DEFAULT_CONNECTION_TIMEOUT_MILLIS))
             .socketTimeout(Duration.ofSeconds(DEFAULT_SOCKET_TIMEOUT_SECONDS))
-            .connectionAcquisitionTimeout(Duration.ofMinutes(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
+            .connectionAcquisitionTimeout(Duration.ofMillis(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))

// AwsHttpClientWrapper.defaultAsyncClient()
-            .connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))
+            .connectionTimeout(Duration.ofMillis(DEFAULT_CONNECTION_TIMEOUT_MILLIS))
             .maxConcurrency(DEFAULT_MAX_ASYNC_CONCURRENCY)
-            .connectionAcquisitionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
+            .connectionAcquisitionTimeout(Duration.ofMillis(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
```

The durable fix is to stop encoding units in names and start encoding them in types — make the constants `Duration` rather than `int`:

```java
// StorageConfigConstants
Duration DEFAULT_CONNECTION_TIMEOUT = Duration.ofMillis(5000);
Duration DEFAULT_SOCKET_TIMEOUT = Duration.ofSeconds(30);
Duration DEFAULT_CONNECTION_ACQUISITION_TIMEOUT = Duration.ofMillis(10000);
```
Then a units mismatch is a compile error rather than a 7-day timeout.

**Note on §1.4:** the `applyToSync(wrapper, builder, fallback)` form preserves today's reachability exactly — the fallback still runs only when the wrapper is null, which `BaseAwsConfig` never produces. Making the tuned defaults genuinely reachable is a separate change, designed in §1.7, and the units fix above is its hard prerequisite. Both ship together in 1.0.31.

---

## 1.2 Option A — resolve inside the wrapper

**The principle:** the wrapper is the only object that knows which of the four states it is in. It should therefore be the only object that decides how to attach itself to an SDK client builder. No factory should ever ask "are you a builder?" — it should say "attach yourself to this."

This is the *Tell, Don't Ask* refactoring. It removes the branch from six call sites, makes a fifth illegal state impossible, and — because the factories stop calling `getTypedClient()` entirely — it also closes D-10.

### Where the methods go — and why not on `CloudHttpClient`

The source document sketches:

```java
// §7.1 of the source document — DO NOT DO THIS
public interface CloudHttpClient {
    void applyToSync(SdkSyncClientBuilder<?, ?> builder);
    void applyToAsync(SdkAsyncClientBuilder<?, ?> builder);
}
```

`CloudHttpClient` lives in **`cloud-sdk-api`**, whose entire dependency list is Dropwizard, Jackson, Guice, commons-lang3, Lombok and SLF4J — **no AWS SDK at all** (verified in `cloud-sdk-api/pom.xml`). Putting `SdkSyncClientBuilder` on that interface forces an AWS SDK dependency into the provider-neutral module and defeats the abstraction it exists to provide. If Azure or GCP support is ever added, `CloudHttpClient` would carry AWS types into it.

**The methods belong on `AwsHttpClientWrapper` in `cloud-sdk-aws`.** This costs nothing, because every AWS config is already statically typed to the concrete wrapper:

```java
// BaseAwsConfig.java:12,17
public abstract class BaseAwsConfig
        implements CloudStorageConfig<AwsCredentialsProviderWrapper, AwsRegionWrapper, AwsHttpClientWrapper> {
    private final AwsHttpClientWrapper httpClient;   // @Getter → getHttpClient() returns the concrete type
```

So `config.getHttpClient().applyToSync(builder)` resolves against `AwsHttpClientWrapper` with no cast and no interface change. **`cloud-sdk-api` is untouched by this change set.**

---

## 1.3 The new `AwsHttpClientWrapper`

Replace the file with the version below. Changes from today:

* a `Mode` enum replaces the two independent booleans (4 states instead of 4-of-4-possible-combinations, one of which is meaningless);
* `isAsync()` / `isBuilder()` are kept as derived getters — **source- and binary-compatible** for existing callers;
* `applyToSync` / `applyToAsync` are the new attach points, plus static null-tolerant overloads that take a fallback supplier;
* `ofSyncBuilder` widens `ApacheHttpClient.Builder` → `SdkHttpClient.Builder<?>` so `UrlConnectionHttpClient` / `AwsCrtHttpClient` builders work;
* `ofAsyncBuilder` tightens `Object` → `SdkAsyncHttpClient.Builder<?>`;
* typed accessors (`syncClient()`, `asyncClient()`, `syncClientBuilder()`, `asyncClientBuilder()`) that fail with a *useful* `IllegalStateException` instead of a bare CCE;
* the dead `try/catch` in `getTypedClient()` is gone (**D-10**), and the method is deprecated.

```java
package com.inttra.mercury.cloudsdk.aws.config;

import com.inttra.mercury.cloudsdk.config.CloudHttpClient;
import software.amazon.awssdk.core.client.builder.SdkAsyncClientBuilder;
import software.amazon.awssdk.core.client.builder.SdkSyncClientBuilder;
import software.amazon.awssdk.http.SdkHttpClient;
import software.amazon.awssdk.http.async.SdkAsyncHttpClient;
import software.amazon.awssdk.http.apache.ApacheHttpClient;
import software.amazon.awssdk.http.crt.AwsCrtAsyncHttpClient;

import java.time.Duration;
import java.util.function.Supplier;

import static com.inttra.mercury.cloudsdk.storage.util.StorageConfigConstants.DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS;
import static com.inttra.mercury.cloudsdk.storage.util.StorageConfigConstants.DEFAULT_CONNECTION_TIMEOUT_MILLIS;
import static com.inttra.mercury.cloudsdk.storage.util.StorageConfigConstants.DEFAULT_MAX_ASYNC_CONCURRENCY;

/**
 * Carries the HTTP transport an AWS service client should use, in one of four states
 * (see {@link Mode}), and knows how to attach itself to an AWS SDK client builder.
 *
 * <p><b>Attach, do not unwrap.</b> Callers must use {@link #applyToSync} /
 * {@link #applyToAsync} rather than unwrapping the underlying object. Unwrapping is what
 * made builder mode a runtime landmine before 1.0.30: a builder-mode wrapper passed to
 * {@code .httpClient(...)} compiles cleanly and throws {@link ClassCastException} at
 * client construction.
 *
 * <p><b>Instance mode vs builder mode — the only real difference.</b>
 * {@code SdkSyncClientBuilder.httpClient(SdkHttpClient)} wraps the argument in
 * {@code NonManagedSdkHttpClient}, whose {@code close()} is a no-op: the SDK will never
 * close a transport you hand it pre-built, so one instance can be shared by several
 * service clients and outlives all of them.
 * {@code httpClientBuilder(...)} makes the SDK construct and <em>own</em> the transport,
 * so {@code serviceClient.close()} closes it too and the transport cannot be shared.
 * Builder mode is the more idiomatic SDK v2 form and gives each service client a private,
 * correctly-disposed connection pool.
 *
 * <p><b>What neither mode protects against.</b> Apache HttpClient 4.x calls
 * {@code connManager.shutdown()} from its {@code catch (Error)} handler in
 * {@code MainClientExec.execute}. An {@link OutOfMemoryError} raised in a thread that is
 * mid-request permanently destroys that client's pool regardless of who owns it. Ownership
 * mode is irrelevant to that failure; only not exhausting the heap prevents it
 * (see {@code QuerySpec.maxResultSize}).
 */
public class AwsHttpClientWrapper implements CloudHttpClient {

    /** The four legal states of this wrapper. */
    public enum Mode {
        SYNC_INSTANCE(false, false),
        SYNC_BUILDER(false, true),
        ASYNC_INSTANCE(true, false),
        ASYNC_BUILDER(true, true);

        private final boolean async;
        private final boolean builder;

        Mode(boolean async, boolean builder) {
            this.async = async;
            this.builder = builder;
        }
    }

    private final Object underlyingClient;
    private final Mode mode;

    private AwsHttpClientWrapper(Object client, Mode mode) {
        if (client == null) {
            throw new IllegalArgumentException("HTTP client must not be null");
        }
        this.underlyingClient = client;
        this.mode = mode;
    }

    // ---------------------------------------------------------------- factories

    public static AwsHttpClientWrapper ofSync(Object client) {
        if (client == null) {
            throw new IllegalArgumentException("Sync HTTP client must not be null");
        }
        if (!(client instanceof SdkHttpClient)) {
            throw new IllegalArgumentException("Client must be either SdkHttpClient or SdkAsyncHttpClient");
        }
        return new AwsHttpClientWrapper(client, Mode.SYNC_INSTANCE);
    }

    /**
     * Builder mode: the AWS SDK constructs and owns the transport.
     * Widened from {@code ApacheHttpClient.Builder} so that
     * {@code UrlConnectionHttpClient.builder()} and {@code AwsCrtHttpClient.builder()} are usable.
     */
    public static AwsHttpClientWrapper ofSyncBuilder(SdkHttpClient.Builder<?> httpClientBuilder) {
        if (httpClientBuilder == null) {
            throw new IllegalArgumentException("Sync HTTP client builder must not be null");
        }
        return new AwsHttpClientWrapper(httpClientBuilder, Mode.SYNC_BUILDER);
    }

    public static AwsHttpClientWrapper ofAsync(Object client) {
        if (client == null) {
            throw new IllegalArgumentException("Async HTTP client must not be null");
        }
        if (!(client instanceof SdkAsyncHttpClient)) {
            throw new IllegalArgumentException("Client must be either SdkHttpClient or SdkAsyncHttpClient");
        }
        return new AwsHttpClientWrapper(client, Mode.ASYNC_INSTANCE);
    }

    /** Tightened from {@code Object} — {@code ofAsync} already validates its argument, this now matches. */
    public static AwsHttpClientWrapper ofAsyncBuilder(SdkAsyncHttpClient.Builder<?> httpClientBuilder) {
        if (httpClientBuilder == null) {
            throw new IllegalArgumentException("Async HTTP client builder must not be null");
        }
        return new AwsHttpClientWrapper(httpClientBuilder, Mode.ASYNC_BUILDER);
    }

    public static AwsHttpClientWrapper defaultClient() {
        return defaultSyncClient();
    }

    public static AwsHttpClientWrapper defaultSyncClient() {
        return ofSync(ApacheHttpClient.builder().build());
    }

    public static AwsHttpClientWrapper defaultAsyncClient() {
        return ofAsync(AwsCrtAsyncHttpClient.builder()
            .connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))
            .maxConcurrency(DEFAULT_MAX_ASYNC_CONCURRENCY)
            .connectionAcquisitionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
            .build());
    }

    // ---------------------------------------------------------------- attach points (the Option A core)

    /**
     * Attaches this transport to a synchronous AWS service client builder,
     * choosing {@code httpClient(...)} or {@code httpClientBuilder(...)} automatically.
     *
     * @throws IllegalStateException if this wrapper holds an asynchronous transport
     */
    public void applyToSync(SdkSyncClientBuilder<?, ?> clientBuilder) {
        if (clientBuilder == null) {
            throw new IllegalArgumentException("Client builder must not be null");
        }
        switch (mode) {
            case SYNC_INSTANCE -> clientBuilder.httpClient((SdkHttpClient) underlyingClient);
            case SYNC_BUILDER  -> clientBuilder.httpClientBuilder((SdkHttpClient.Builder<?>) underlyingClient);
            default -> throw new IllegalStateException(
                "Cannot apply an asynchronous HTTP client (" + describe()
                    + ") to a synchronous AWS client builder. "
                    + "Use AwsHttpClientWrapper.ofSync(...) or ofSyncBuilder(...).");
        }
    }

    /**
     * Attaches this transport to an asynchronous AWS service client builder.
     *
     * @throws IllegalStateException if this wrapper holds a synchronous transport
     */
    public void applyToAsync(SdkAsyncClientBuilder<?, ?> clientBuilder) {
        if (clientBuilder == null) {
            throw new IllegalArgumentException("Client builder must not be null");
        }
        switch (mode) {
            case ASYNC_INSTANCE -> clientBuilder.httpClient((SdkAsyncHttpClient) underlyingClient);
            case ASYNC_BUILDER  -> clientBuilder.httpClientBuilder((SdkAsyncHttpClient.Builder<?>) underlyingClient);
            default -> throw new IllegalStateException(
                "Cannot apply a synchronous HTTP client (" + describe()
                    + ") to an asynchronous AWS client builder. "
                    + "Use AwsHttpClientWrapper.ofAsync(...) or ofAsyncBuilder(...).");
        }
    }

    /**
     * Null-tolerant form for factories: applies {@code wrapper} if present, otherwise the
     * factory's own tuned default. Keeps per-service tuning (max connections, socket
     * timeout) reachable instead of silently falling through to SDK defaults.
     */
    public static void applyToSync(AwsHttpClientWrapper wrapper,
                                   SdkSyncClientBuilder<?, ?> clientBuilder,
                                   Supplier<SdkHttpClient> fallback) {
        if (wrapper == null) {
            clientBuilder.httpClient(fallback.get());
            return;
        }
        wrapper.applyToSync(clientBuilder);
    }

    public static void applyToAsync(AwsHttpClientWrapper wrapper,
                                    SdkAsyncClientBuilder<?, ?> clientBuilder,
                                    Supplier<SdkAsyncHttpClient> fallback) {
        if (wrapper == null) {
            clientBuilder.httpClient(fallback.get());
            return;
        }
        wrapper.applyToAsync(clientBuilder);
    }

    // ---------------------------------------------------------------- typed accessors (replace getTypedClient)

    /** @throws IllegalStateException unless this wrapper is in {@link Mode#SYNC_INSTANCE} */
    public SdkHttpClient syncClient() {
        require(Mode.SYNC_INSTANCE);
        return (SdkHttpClient) underlyingClient;
    }

    /** @throws IllegalStateException unless this wrapper is in {@link Mode#ASYNC_INSTANCE} */
    public SdkAsyncHttpClient asyncClient() {
        require(Mode.ASYNC_INSTANCE);
        return (SdkAsyncHttpClient) underlyingClient;
    }

    /** @throws IllegalStateException unless this wrapper is in {@link Mode#SYNC_BUILDER} */
    public SdkHttpClient.Builder<?> syncClientBuilder() {
        require(Mode.SYNC_BUILDER);
        return (SdkHttpClient.Builder<?>) underlyingClient;
    }

    /** @throws IllegalStateException unless this wrapper is in {@link Mode#ASYNC_BUILDER} */
    public SdkAsyncHttpClient.Builder<?> asyncClientBuilder() {
        require(Mode.ASYNC_BUILDER);
        return (SdkAsyncHttpClient.Builder<?>) underlyingClient;
    }

    private void require(Mode expected) {
        if (mode != expected) {
            throw new IllegalStateException(
                "Expected " + expected + " but this wrapper is " + describe()
                    + ". Prefer applyToSync(...)/applyToAsync(...) over unwrapping.");
        }
    }

    private String describe() {
        return mode + " holding " + underlyingClient.getClass().getName();
    }

    // ---------------------------------------------------------------- state / compatibility

    public Mode getMode() {
        return mode;
    }

    public boolean isAsync() {
        return mode.async;
    }

    public boolean isBuilder() {
        return mode.builder;
    }

    @Override
    public Object getUnderlyingClient() {
        return underlyingClient;
    }

    /**
     * @deprecated Unchecked: {@code T} is inferred at the call site, so a mismatch surfaces
     *     as a bare {@link ClassCastException} in the caller's frame with no context. Use
     *     {@link #applyToSync}/{@link #applyToAsync} to attach, or {@link #syncClient()} /
     *     {@link #asyncClient()} / {@link #syncClientBuilder()} / {@link #asyncClientBuilder()}
     *     to unwrap with a checked, self-describing failure. Scheduled for removal in 1.1.0.
     */
    @Deprecated(since = "1.0.30", forRemoval = true)
    @SuppressWarnings("unchecked")
    public <T> T getTypedClient() {
        return (T) underlyingClient;
    }
}
```

### Notes on the code above

**The `try/catch (ClassCastException)` is gone.** It was unreachable — see §3. Removing it is not a behaviour change; it is deleting a comment that was pretending to be code.

**`switch` expressions with `->` require Java 14+.** `cloud-sdk-aws/pom.xml` sets `maven.compiler.source/target` to **17**, so this is fine. If you prefer to stay conservative, a classic `if/else` chain is equivalent.

**Generic wildcards.** `SdkSyncClientBuilder<B extends SdkSyncClientBuilder<B,C>, C>` is F-bounded. Declaring the parameter as `SdkSyncClientBuilder<?, ?>` and ignoring the returned `B` compiles cleanly — we call the method for its effect, not its fluent return. Verified against `sdk-core-2.30.24.jar`:

```
public interface SdkSyncClientBuilder<B extends SdkSyncClientBuilder<B, C>, C> {
  public abstract B httpClient(SdkHttpClient);
  public abstract B httpClientBuilder(SdkHttpClient$Builder);
}
```

**Binary compatibility of the widened `ofSyncBuilder`.** Changing `ofSyncBuilder(ApacheHttpClient.Builder)` to `ofSyncBuilder(SdkHttpClient.Builder<?>)` changes the method descriptor. It is **source-compatible** (an `ApacheHttpClient.Builder` *is* an `SdkHttpClient.Builder<ApacheHttpClient.Builder>`) but **binary-incompatible**: a class compiled against 1.0.29 would get `NoSuchMethodError`. Since the §8.4 release plan recompiles every consumer against 1.0.30, this is acceptable. If you want belt-and-braces, add a bridge overload:

```java
public static AwsHttpClientWrapper ofSyncBuilder(ApacheHttpClient.Builder httpClientBuilder) {
    return ofSyncBuilder((SdkHttpClient.Builder<?>) httpClientBuilder);
}
```
Overload resolution picks the most specific applicable method, so existing `ApacheHttpClient.Builder` call sites bind to the bridge and behave identically.

**`ofAsyncBuilder(Object)` → `ofAsyncBuilder(SdkAsyncHttpClient.Builder<?>)`** is a hard source break, but nothing in either repository calls it except one test (§1.6). Register §7.1 recommends either wiring it up or deleting it; this change wires it up.

---

## 1.4 The complete factory change set

Six files. Every diff is a net **reduction** in code.

### 1.4.1 `storage/factory/S3ClientFactory.java`

```diff
-        // Use builder mode if available, otherwise fall back to pre-built client
-        if (config.getHttpClient() != null) {
-            if (config.getHttpClient().isBuilder()) {
-                builder.httpClientBuilder(config.getHttpClient().getTypedClient());
-            } else {
-                builder.httpClient(config.getHttpClient().getTypedClient());
-            }
-        } else {
-            builder.httpClient(createHttpClient());
-        }
+        AwsHttpClientWrapper.applyToSync(config.getHttpClient(), builder, S3ClientFactory::createHttpClient);
```
Add `import com.inttra.mercury.cloudsdk.aws.config.AwsHttpClientWrapper;`.

> While here, fix **D-4**: the Javadoc on `visibilityS3StorageConfig()` / `buildS3HttpClientWrapper()` in `VisibilityApplicationInjector` claims builder mode stops "a DynamoDB timeout" from closing the pool. It does the opposite — `httpClient(instance)` wraps the transport in `NonManagedSdkHttpClient` (close is a no-op), while `httpClientBuilder(...)` makes the SDK the owner. Rewrite text is in §1.5.3.

### 1.4.2 `database/factory/DynamoRepositoryFactory.java`

```diff
     public static DynamoDbClient createDynamoDbClient(DynamoDbClientConfig config) {
 
         var builder = DynamoDbClient.builder()
             .region(config.getRegion().getRegionDelegate())
             .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
-            .overrideConfiguration(createOverrideConfig(config))
-            .httpClient(config.getHttpClient() != null
-                ? config.getHttpClient().getTypedClient()
-                : createHttpClient());
+            .overrideConfiguration(createOverrideConfig(config));
+
+        AwsHttpClientWrapper.applyToSync(config.getHttpClient(), builder,
+            DynamoRepositoryFactory::createHttpClient);
 
         if (config.getEndpointOverride() != null) {
```

`DynamoDbClientBuilder` implements `SdkSyncClientBuilder`, so `var builder` binds correctly.

### 1.4.3 `messaging/factory/MessagingClientFactory.java` — call site 1 (L84-90)

```diff
         SqsClientBuilder sqsClientBuilder = SqsClient.builder()
             .region(config.getRegion().getRegionDelegate())
             .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
-            .overrideConfiguration(createOverrideConfig(config))
-            .httpClient(config.getHttpClient() != null
-                ? config.getHttpClient().getTypedClient()
-                : createHttpClient());
+            .overrideConfiguration(createOverrideConfig(config));
+
+        AwsHttpClientWrapper.applyToSync(config.getHttpClient(), sqsClientBuilder,
+            MessagingClientFactory::createHttpClient);
```

### 1.4.4 `messaging/factory/MessagingClientFactory.java` — call site 2 (L276-286)

This one is nested inside a constructor argument and must be lifted to a local first:

```diff
-        AmazonSQSExtendedClient extendedSqsClient = new AmazonSQSExtendedClient(
-            SqsClient.builder()
-                .region(config.getRegion().getRegionDelegate())
-                .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
-                .overrideConfiguration(createOverrideConfig(config))
-                .httpClient(config.getHttpClient() != null
-                    ? config.getHttpClient().getTypedClient()
-                    : createHttpClient())
-                .build(),
-            extendedClientConfig
-        );
+        SqsClientBuilder extendedSqsClientBuilder = SqsClient.builder()
+            .region(config.getRegion().getRegionDelegate())
+            .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
+            .overrideConfiguration(createOverrideConfig(config));
+
+        AwsHttpClientWrapper.applyToSync(config.getHttpClient(), extendedSqsClientBuilder,
+            MessagingClientFactory::createHttpClient);
+
+        AmazonSQSExtendedClient extendedSqsClient = new AmazonSQSExtendedClient(
+            extendedSqsClientBuilder.build(), extendedClientConfig);
```

### 1.4.5 `notification/factory/NotificationClientFactory.java`

```diff
         SnsClientBuilder snsClientBuilder = SnsClient.builder()
                 .region(config.getRegion().getRegionDelegate())
                 .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
-                .overrideConfiguration(createOverrideConfig(config))
-                .httpClient(config.getHttpClient() != null ? config.getHttpClient().getTypedClient()
-                        : createHttpClient());
+                .overrideConfiguration(createOverrideConfig(config));
+
+        AwsHttpClientWrapper.applyToSync(config.getHttpClient(), snsClientBuilder,
+                NotificationClientFactory::createHttpClient);
```

### 1.4.6 `storage/factory/TransferManagerFactory.java` (async path)

```diff
     private static S3AsyncClient createAsyncClient(AwsStorageConfig config) {
         validateAsyncConfig(config);
-        return S3AsyncClient.builder()
+        S3AsyncClientBuilder asyncBuilder = S3AsyncClient.builder()
             .region(config.getRegion().getRegionDelegate())
             .endpointOverride(config.getEndpointOverride())
-            .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
-            .httpClient(resolveAsyncHttpClient(config))
-            .build();
+            .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate());
+
+        AwsHttpClientWrapper.applyToAsync(config.getHttpClient(), asyncBuilder,
+            () -> AwsHttpClientWrapper.defaultAsyncClient().asyncClient());
+
+        return asyncBuilder.build();
     }
-
-    static SdkAsyncHttpClient resolveAsyncHttpClient(AwsStorageConfig config) {
-        if (config.getHttpClient() != null && config.getHttpClient().isAsync()) {
-            return config.getHttpClient().getTypedClient();
-        }
-        return AwsHttpClientWrapper.defaultAsyncClient().getTypedClient();
-    }
```

**Behaviour change, deliberate:** the old `resolveAsyncHttpClient` silently substituted a default CRT client when a *sync* wrapper was configured. `applyToAsync` now throws `IllegalStateException` with a message naming the actual mode. `validateAsyncConfig` already requires `config.isUseAsyncClient()`, and `BaseAwsConfig.validateBaseConfig()` (L112-114) already rejects a sync/async mismatch at build time, so this path was unreachable for well-formed configs. Failing loudly is strictly better than silently ignoring tuned settings. If any test asserts the old silent-substitution behaviour, update it — the old behaviour was the bug.

Add `import software.amazon.awssdk.services.s3.S3AsyncClientBuilder;`; the `SdkAsyncHttpClient` import may become unused.

### 1.4.7 `email/factory/EmailClientFactory.java` and `paramstore/factory/ParameterStoreClientFactory.java` — wire them up

These two currently discard the configured HTTP client. They should honour it:

```diff
// EmailClientFactory.createSesV2Client
         SesV2ClientBuilder builder = SesV2Client.builder()
             .region(config.getRegion().getRegionDelegate())
             .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate());
+
+        AwsHttpClientWrapper.applyToSync(config.getHttpClient(), builder,
+            () -> ApacheHttpClient.builder().build());
```

```diff
// ParameterStoreClientFactory
-        SsmClient ssmClient = SsmClient.builder()
+        SsmClientBuilder ssmBuilder = SsmClient.builder()
             .region(config.getRegion().getRegionDelegate())
             .endpointOverride(config.getEndpointOverride())
             .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
             .overrideConfiguration(b -> b
-                .apiCallTimeout(config.getClientExecutionTimeout()))
-            .build();
+                .apiCallTimeout(config.getClientExecutionTimeout()));
+
+        AwsHttpClientWrapper.applyToSync(config.getHttpClient(), ssmBuilder,
+            () -> ApacheHttpClient.builder().build());
+
+        SsmClient ssmClient = ssmBuilder.build();
```

> **Judgement call flagged for you.** Wiring SES and SSM changes their effective transport for any caller that previously set `.httpClient(...)` on those configs and (unknowingly) had it ignored. Because `BaseAwsConfig` always populates a default wrapper, today those two clients get `ApacheHttpClient.builder().build()` via the SDK's own default resolution; after the change they get `AwsHttpClientWrapper.defaultSyncClient()`, which is the same thing. **Net behaviour for existing callers is unchanged**; only explicit configuration starts being honoured. Low risk, but it belongs in the release note rather than passing silently.

### 1.4.8 `storage/config/AwsStorageConfig.java` — fail fast in builder mode

```diff
     public SdkHttpClient getHttpClientForTesting() {
         AwsHttpClientWrapper clientWrapper = getHttpClientWrapper();
         if (clientWrapper == null) {
             return null;
         }
         if (clientWrapper.isAsync()) {
             throw new IllegalStateException("Cannot get sync client: configured client is async");
         }
-        return clientWrapper.getTypedClient();
+        if (clientWrapper.isBuilder()) {
+            throw new IllegalStateException(
+                "Cannot get a pre-built sync client: this config is in builder mode; "
+                    + "the transport is constructed and owned by the AWS SDK. "
+                    + "Use getHttpClientWrapper().syncClientBuilder() instead.");
+        }
+        return clientWrapper.syncClient();
     }
```
and the symmetric change in `getAsyncHttpClientForTesting()` using `asyncClient()`. This turns the register's §8.2 "latent" row into a documented, self-explaining failure.

---

## 1.5 How `mercury-services` modules call and initialise this

Nothing about the *call shape* changes for consumers. Applications never touch `applyToSync` — they hand a wrapper to a config, exactly as today. The change is that a builder-mode wrapper now works with **every** service, not just S3.

### 1.5.1 The visibility S3 path — unchanged source, now correct by construction

`VisibilityApplicationInjector` (in `visibility/visibility-commons`) today:

```java
@Provides
@Singleton
protected StorageClient bindStorageClient() {
    return StorageClientFactory.createS3Client(visibilityS3StorageConfig());
}

static AwsStorageConfig visibilityS3StorageConfig() {
    return AwsStorageConfig.builder()
            .region(AwsRegionWrapper.of(resolveRegionId()))
            .credentialsProvider(AwsCredentialsProviderWrapper.of(DefaultCredentialsProvider.create()))
            .httpClient(buildS3HttpClientWrapper())          // ← builder-mode wrapper
            .build();
}

static AwsHttpClientWrapper buildS3HttpClientWrapper() {
    return AwsHttpClientWrapper.ofSyncBuilder(
            ApacheHttpClient.builder()
                    .connectionTimeout(S3_CONNECTION_TIMEOUT)   // 1 s
                    .socketTimeout(S3_SOCKET_TIMEOUT)           // 5 s
                    .maxConnections(S3_MAX_CONNECTIONS));       // 50
}
```

**This code compiles and behaves identically after the change.** `ApacheHttpClient.Builder` satisfies the widened `SdkHttpClient.Builder<?>` parameter. Internally the flow becomes:

```
AwsHttpClientWrapper.ofSyncBuilder(apacheBuilder)
    → Mode.SYNC_BUILDER
    → AwsStorageConfig.builder().httpClient(wrapper).build()
    → StorageClientFactory.createS3Client(config)
        → S3ClientFactory.createConfiguredClient(config)
            → AwsHttpClientWrapper.applyToSync(wrapper, s3Builder, S3ClientFactory::createHttpClient)
                → wrapper.applyToSync(s3Builder)
                    → switch (SYNC_BUILDER) → s3Builder.httpClientBuilder(apacheBuilder)
        → S3Client is built; the SDK constructs and owns a private Apache pool
```

### 1.5.2 The DynamoDB path — the case that used to be a landmine

Today, if visibility wanted the same treatment for DynamoDB, this would fail at startup:

```java
// Today: compiles, then ClassCastException during Guice construction
return dynamoConfig.toClientConfigBuilder()
        .httpClient(AwsHttpClientWrapper.ofSyncBuilder(
                ApacheHttpClient.builder()
                        .maxConnections(100)
                        .socketTimeout(Duration.ofSeconds(30))))
        .apiCallTimeout(Duration.ofSeconds(60))
        .apiCallAttemptTimeout(Duration.ofSeconds(25))
        .build();
```

After the change, exactly the same code works. Suggested addition to `VisibilityDynamoModule.provideDynamoDbClientConfig()`:

```java
@Provides
@Singleton
public DynamoDbClientConfig provideDynamoDbClientConfig() {
    final BaseDynamoDbConfig dynamoConfig = config.getDynamoDbConfig();
    if (dynamoConfig == null) {
        throw new IllegalStateException("dynamoDbConfig is not configured in VisibilityApplicationConfig");
    }
    return dynamoConfig.toClientConfigBuilder()
            .consistentRead(false)
            // Builder mode: the SDK constructs and owns this pool, so it is disposed with
            // the DynamoDbClient and is not shared with S3 or SQS.
            // NOTE: this does NOT protect against Apache's catch(Error) -> connManager.shutdown().
            // Only bounding the result set (QuerySpec.maxResultSize) prevents that.
            .httpClient(buildDynamoHttpClientWrapper())
            .apiCallTimeout(Duration.ofSeconds(60))
            .apiCallAttemptTimeout(Duration.ofSeconds(25))
            .build();
}

static AwsHttpClientWrapper buildDynamoHttpClientWrapper() {
    return AwsHttpClientWrapper.ofSyncBuilder(
            ApacheHttpClient.builder()
                    .maxConnections(DYNAMO_MAX_CONNECTIONS)
                    .connectionTimeout(DYNAMO_CONNECTION_TIMEOUT)
                    .socketTimeout(DYNAMO_SOCKET_TIMEOUT));
}
```

The same three-line shape works for `AwsMessagingClientConfig` (SQS) and `NotificationClientConfig` (SNS).

### 1.5.3 Corrected Javadoc for D-4

Replace the comment on `buildS3HttpClientWrapper()` / `visibilityS3StorageConfig()` with:

```java
/**
 * Returns an {@link AwsHttpClientWrapper} in <em>builder mode</em>, carrying the tuned Apache
 * HTTP client builder (1 s connect / 5 s socket / 50 connections) preserved from the legacy
 * AWS SDK v1 configuration.
 *
 * <p>Builder mode means the AWS SDK constructs and <em>owns</em> the resulting connection pool,
 * so it is closed when {@code S3Client.close()} is called. With {@code httpClient(instance)} the
 * SDK wraps the transport in {@code NonManagedSdkHttpClient} and never closes it. Builder mode is
 * the idiomatic SDK v2 form and guarantees this pool is not shared with any other service client.
 *
 * <p><b>This is not a defence against the ION-16431 failure mode.</b> That failure was Apache
 * HttpClient's {@code catch (Error) -> connManager.shutdown()} in {@code MainClientExec.execute},
 * which destroys a pool from inside regardless of who owns it, triggered by an
 * {@link OutOfMemoryError} originating in DynamoDB Enhanced Client auto-pagination. The fix for
 * that is {@code QuerySpec.maxResultSize} (commons PR #48 / services PR #1166), not this.
 */
```

### 1.5.4 Consumer upgrade checklist

A full sweep of `mercury-services` for `AwsHttpClientWrapper` returns **exactly two files** — `VisibilityApplicationInjector` and its test. Nothing else in the fleet touches the wrapper type at all:

```
visibility-commons/src/main/java/.../config/VisibilityApplicationInjector.java:8,85,89,90
visibility-commons/src/test/java/.../config/VisibilityApplicationInjectorTest.java:7,57
```

| App | Action required for 1.0.30 |
|---|---|
| `visibility` | None for D-1 — existing `ofSyncBuilder(ApacheHttpClient.builder()...)` call compiles unchanged, and `VisibilityApplicationInjectorTest.s3HttpClientWrapperIsBuilderBacked()` still passes because `isBuilder()` is retained as a derived getter. Update one stale comment (below). Optionally adopt builder mode for DynamoDB/SQS per §1.5.2. Rewrite the D-4 Javadoc. |
| `auth`, `booking`, `booking-bridge`, `bill-of-lading-v2` | None. No call site uses `ofSyncBuilder`/`ofAsyncBuilder`; instance mode is unchanged. Recompile against 1.0.30. |
| Any repo outside `mercury-services` depending on `cloud-sdk-aws` | Grep for `getTypedClient(` — it is now `@Deprecated(forRemoval = true)`. Migrate to `applyToSync`/`applyToAsync` or the typed accessors. Grep for `ofAsyncBuilder(` — the parameter narrowed from `Object`. |

The stale comment, in `VisibilityApplicationInjectorTest.buildsStorageConfigWithCustomApacheHttpClient()` (L68-70), documents the D-1 symptom as if it were intended:

```java
// Correctness of the wrapper mode (builder vs. pre-built) is asserted by
// s3HttpClientWrapperIsBuilderBacked() — getHttpClientForTesting() is not called here
// because in builder mode it would throw ClassCastException by design.
```

`ClassCastException` there is not "by design"; it is the unwrapping defect (§1.1 row 7). After the §1.4.8 change the method throws a self-describing `IllegalStateException`, so the comment becomes:

```java
// getHttpClientForTesting() is intentionally not called here: in builder mode there is no
// pre-built transport to return — the SDK constructs it — so the accessor throws
// IllegalStateException. Wrapper mode is asserted by s3HttpClientWrapperIsBuilderBacked().
```

That test can now usefully assert the failure instead of avoiding it:

```java
assertThatThrownBy(() -> VisibilityApplicationInjector.visibilityS3StorageConfig()
        .getHttpClientForTesting())
    .isInstanceOf(IllegalStateException.class)
    .hasMessageContaining("builder mode");
```

---

## 1.6 Tests

**`AwsHttpClientWrapperTest`** — three changes:

1. `BuilderModeTests.shouldExposeBuilderFlagAndTypedClientForAsyncBuilder` declares `Object builder = AwsCrtAsyncHttpClient.builder();`. That no longer compiles against the narrowed `ofAsyncBuilder`. Change to:
   ```java
   SdkAsyncHttpClient.Builder<?> builder = AwsCrtAsyncHttpClient.builder();
   ```
2. `TypeCastingTests.shouldThrowClassCastExceptionForIncorrectType` asserts dead code (§3). Replace with a real assertion against the new accessors:
   ```java
   @Test
   void shouldRejectUnwrappingSyncInstanceAsAsync() {
       AwsHttpClientWrapper wrapper = AwsHttpClientWrapper.ofSync(
           ApacheHttpClient.builder().connectionTimeout(Duration.ofSeconds(5)).build());

       assertThatThrownBy(wrapper::asyncClient)
           .isInstanceOf(IllegalStateException.class)
           .hasMessageContaining("ASYNC_INSTANCE")
           .hasMessageContaining("SYNC_INSTANCE");
   }
   ```
3. New coverage for the attach points:
   ```java
   @Test
   void applyToSyncUsesHttpClientBuilderInBuilderMode() {
       SdkSyncClientBuilder<?, ?> clientBuilder = mock(SdkSyncClientBuilder.class);
       ApacheHttpClient.Builder httpBuilder = ApacheHttpClient.builder();

       AwsHttpClientWrapper.ofSyncBuilder(httpBuilder).applyToSync(clientBuilder);

       verify(clientBuilder).httpClientBuilder(httpBuilder);
       verify(clientBuilder, never()).httpClient(any(SdkHttpClient.class));
   }

   @Test
   void applyToSyncRejectsAsyncWrapper() {
       AwsHttpClientWrapper asyncWrapper = AwsHttpClientWrapper.defaultAsyncClient();

       assertThatThrownBy(() -> asyncWrapper.applyToSync(mock(SdkSyncClientBuilder.class)))
           .isInstanceOf(IllegalStateException.class)
           .hasMessageContaining("asynchronous HTTP client");
   }

   @Test
   void staticApplyToSyncUsesFallbackWhenWrapperIsNull() {
       SdkSyncClientBuilder<?, ?> clientBuilder = mock(SdkSyncClientBuilder.class);
       SdkHttpClient fallback = ApacheHttpClient.builder().build();

       AwsHttpClientWrapper.applyToSync(null, clientBuilder, () -> fallback);

       verify(clientBuilder).httpClient(fallback);
   }
   ```

**`S3ClientFactoryBuilderModeTest`** — the existing assertions (`verify(builder).httpClientBuilder(httpClientBuilder)` and `verify(builder, never()).httpClientBuilder(any())`) remain valid; only the code path behind them changes.

**New — the test that would have caught D-1.** A single parameterised test asserting *every* factory honours builder mode. This is the regression guard; without it the same defect reappears the next time a factory is added:

```java
@ParameterizedTest(name = "{0} honours sync builder mode")
@MethodSource("syncFactories")
void everySyncFactoryHonoursBuilderMode(String name, Consumer<AwsHttpClientWrapper> factoryInvocation) {
    AwsHttpClientWrapper builderMode = AwsHttpClientWrapper.ofSyncBuilder(
        ApacheHttpClient.builder().maxConnections(7));

    assertThatCode(() -> factoryInvocation.accept(builderMode)).doesNotThrowAnyException();
}
// entries: S3ClientFactory, DynamoRepositoryFactory, MessagingClientFactory (both call sites),
//          NotificationClientFactory, EmailClientFactory, ParameterStoreClientFactory
```


## 1.7 Correcting the units bug and making the tuned defaults reachable

Two problems from §1.1, fixed together because the first is a prerequisite for the second:

* **Units.** `S3ClientFactory.createHttpClient()` and `AwsHttpClientWrapper.defaultAsyncClient()` apply `Duration.ofSeconds` / `ofMinutes` to constants named `…_MILLIS`. Live and reached (§1.1).
* **Unreachable tuning.** `BaseAwsConfig` fills `httpClient` with a bare `defaultSyncClient()`, so every factory's tuned `createHttpClient()` is dead code.

### The underlying cause: four copies of the same builder, three constant sets, one bug

```java
// S3ClientFactory:113            MessagingClientFactory:143      NotificationClientFactory:136   DynamoRepositoryFactory:412
maxConnections            50                  50                          50                            100
connectionTimeout   ofSeconds(5000)  ✗   ofMillis(5000)  ✓          ofMillis(5000)  ✓             ofMillis(5000)  ✓
socketTimeout       ofSeconds(30)    ✓   ofSeconds(30)   ✓          ofSeconds(30)   ✓             ofSeconds(30)   ✓
acquisitionTimeout  ofMinutes(10000) ✗   ofMillis(10000) ✓          ofMillis(10000) ✓             ofMillis(10000) ✓
constants from      StorageConfigConstants   own (dup)                  own (dup)                     own (dup)
```

Four near-identical blocks, three duplicated constant sets, and the one copy that reached for a different `Duration` factory got it wrong twice. Deduplicating removes the divergence and the bug in the same edit.

### Part 1 — one home for tuned transports

New `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/AwsHttpDefaults.java`:

```java
package com.inttra.mercury.cloudsdk.aws.config;

import software.amazon.awssdk.http.apache.ApacheHttpClient;
import software.amazon.awssdk.http.crt.AwsCrtAsyncHttpClient;

import java.time.Duration;

/**
 * Tuned HTTP transports for cloud-sdk AWS service clients.
 *
 * <p>Single source of truth. Previously each factory carried its own copy of this builder with
 * its own duplicated constants; one copy applied {@code Duration.ofSeconds} / {@code ofMinutes}
 * to millisecond-named constants, producing an 83-minute connect timeout and a 6.9-day
 * connection-acquisition timeout on every client from
 * {@code StorageClientFactory.createDefaultS3Client()}.
 *
 * <p>Durations are declared as {@link Duration} constants so a unit mismatch is a compile error
 * rather than a runtime hang.
 */
public final class AwsHttpDefaults {

    /** Pool size for general-purpose service clients (S3, SQS, SNS, SES, SSM). */
    public static final int MAX_CONNECTIONS = 50;

    /** DynamoDB is the highest-fan-out client in these services and gets a larger pool. */
    public static final int DYNAMODB_MAX_CONNECTIONS = 100;

    public static final Duration CONNECTION_TIMEOUT = Duration.ofSeconds(5);
    public static final Duration SOCKET_TIMEOUT = Duration.ofSeconds(30);
    public static final Duration CONNECTION_ACQUISITION_TIMEOUT = Duration.ofSeconds(10);

    public static final int MAX_ASYNC_CONCURRENCY = 100;

    private AwsHttpDefaults() {
    }

    /** Tuned Apache builder for general-purpose sync clients. A fresh builder on every call. */
    public static ApacheHttpClient.Builder syncBuilder() {
        return ApacheHttpClient.builder()
            .maxConnections(MAX_CONNECTIONS)
            .connectionTimeout(CONNECTION_TIMEOUT)
            .socketTimeout(SOCKET_TIMEOUT)
            .connectionAcquisitionTimeout(CONNECTION_ACQUISITION_TIMEOUT);
    }

    /** Tuned Apache builder for DynamoDB. Differs from {@link #syncBuilder()} only in pool size. */
    public static ApacheHttpClient.Builder dynamoDbSyncBuilder() {
        return syncBuilder().maxConnections(DYNAMODB_MAX_CONNECTIONS);
    }

    public static AwsCrtAsyncHttpClient.Builder asyncBuilder() {
        return AwsCrtAsyncHttpClient.builder()
            .connectionTimeout(CONNECTION_TIMEOUT)
            .maxConcurrency(MAX_ASYNC_CONCURRENCY)
            .connectionAcquisitionTimeout(CONNECTION_ACQUISITION_TIMEOUT);
    }

    /** Wrapped forms, for {@code BaseAwsConfig} and the factory fallbacks. */
    public static AwsHttpClientWrapper sync() {
        return AwsHttpClientWrapper.ofSync(syncBuilder().build());
    }

    public static AwsHttpClientWrapper dynamoDbSync() {
        return AwsHttpClientWrapper.ofSync(dynamoDbSyncBuilder().build());
    }

    public static AwsHttpClientWrapper async() {
        return AwsHttpClientWrapper.ofAsync(asyncBuilder().build());
    }
}
```

`Duration` constants rather than `int …_MILLIS` is the durable fix: a unit mismatch stops compiling. The old `int` constants in `StorageConfigConstants` and in the four factories stay for source compatibility but are `@Deprecated` and no longer referenced by transport construction.

### Part 2 — `AwsHttpClientWrapper` defaults delegate (fixes the async units bug)

```diff
     public static AwsHttpClientWrapper defaultSyncClient() {
-        return ofSync(ApacheHttpClient.builder().build());
+        return AwsHttpDefaults.sync();
     }

     public static AwsHttpClientWrapper defaultAsyncClient() {
-        return ofAsync(AwsCrtAsyncHttpClient.builder()
-            .connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))       // 5 000 s
-            .maxConcurrency(DEFAULT_MAX_ASYNC_CONCURRENCY)
-            .connectionAcquisitionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
-            .build());                                                                       // 10 000 s
+        return AwsHttpDefaults.async();
     }
```

This alone makes the tuned values reachable for **every** service that goes through `BaseAwsConfig` without an explicit `.httpClient(...)` — which, per §1.1, is every service that does not opt out. No `BaseAwsConfig` change, no nullability change, no new hook.

### Part 3 — the DynamoDB pool, without breaking the non-null guarantee

`defaultSyncClient()` gives 50 connections; `DynamoRepositoryFactory` intends 100. Getting DynamoDB its larger pool needs a per-service default.

**Do not make `BaseAwsConfig.httpClient` nullable to achieve this.** `getHttpClient()` is declared on the published `CloudStorageConfig` interface in `cloud-sdk-api`, and two existing tests assert it is non-null (`NotificationClientConfigTest:205`, `AwsCloudParameterStoreConfigTest:116`). Relaxing the guarantee is a wider, more surprising change than the problem warrants.

Instead, add an overridable hook **on the builder**, which is fully constructed when `build()` runs — so there is no partially-initialised-`this` hazard:

```diff
 // BaseAwsConfig
     protected BaseAwsConfig(BaseAwsConfigBuilder<?, ?> builder, boolean useAsyncClient) {
         this.useAsyncClient = useAsyncClient;
         this.credentialsProvider = builder.credentialsProvider;
         this.region = builder.region;
-        this.httpClient = builder.httpClient != null ?
-            builder.httpClient :
-            (useAsyncClient ? AwsHttpClientWrapper.defaultAsyncClient() : AwsHttpClientWrapper.defaultClient());
+        this.httpClient = builder.httpClient != null
+            ? builder.httpClient
+            : builder.defaultHttpClient(useAsyncClient);
```

```java
 // BaseAwsConfig.BaseAwsConfigBuilder
    /**
     * The transport used when the caller supplies none. Override per service where the
     * general-purpose tuning is not right.
     *
     * <p>Called from the config constructor on a fully-built builder, so overrides may safely
     * read builder state.
     */
    protected AwsHttpClientWrapper defaultHttpClient(boolean async) {
        return async ? AwsHttpDefaults.async() : AwsHttpDefaults.sync();
    }
```

```java
 // DynamoDbClientConfig.Builder — the only override
    @Override
    protected AwsHttpClientWrapper defaultHttpClient(boolean async) {
        return async ? super.defaultHttpClient(true) : AwsHttpDefaults.dynamoDbSync();
    }
```

`getHttpClient()` remains non-null for every config. No test changes, no API semantics change.

> **`DynamoDbClientConfig.maxConnections` stays dead.** The field (default 100, `DynamoDbClientConfig:70`) has no reader anywhere in `src/main`. Honouring it would mean building the transport from config rather than a constant — a larger change with its own compatibility questions. Left in §6; the constant-based 100 above matches its intent in the meantime.

### Part 4 — factories delegate, duplication deleted

Each factory's private `createHttpClient()` collapses to one line, and the duplicated `DEFAULT_*` constants are deprecated:

```diff
 // S3ClientFactory — this is the copy that carried the units bug
     private static ApacheHttpClient createHttpClient() {
-        return (ApacheHttpClient) ApacheHttpClient.builder()
-            .maxConnections(DEFAULT_MAX_CONNECTIONS)
-            .connectionTimeout(Duration.ofSeconds(DEFAULT_CONNECTION_TIMEOUT_MILLIS))
-            .socketTimeout(Duration.ofSeconds(DEFAULT_SOCKET_TIMEOUT_SECONDS))
-            .connectionAcquisitionTimeout(Duration.ofMinutes(DEFAULT_CONNECTION_ACQUISITION_TIMEOUT_MILLIS))
-            .build();
+        return (ApacheHttpClient) AwsHttpDefaults.syncBuilder().build();
     }
```

Identical collapse in `MessagingClientFactory:143`, `NotificationClientFactory:136`, and `DynamoRepositoryFactory:412` (the last using `AwsHttpDefaults.dynamoDbSyncBuilder()`).

This is the edit that fixes the **live, reached** defect: `S3ClientFactory.createDefaultS3Client():85` calls `createHttpClient()` directly, so `booking`, `bill-of-lading-v2`, `tx-tracking` and `S3ArchiveHandler` all pick up 5 s / 10 s instead of 83 min / 6.9 days.

The SES and SSM fallbacks from §1.4.7 also become `AwsHttpDefaults::sync` rather than a bare builder, so all seven services share one tuning.

### Part 5 — the resulting behaviour deltas, in full

Everything below is a **deliberate** change and belongs in the release note.

| Path | Reached today by | Before | After |
|---|---|---|---|
| `StorageClientFactory.createDefaultS3Client()` | `booking` ×2, `bill-of-lading-v2`, `tx-tracking` | connect **83 min**, acquire **6.9 days**, 50 conns, socket 30 s | connect **5 s**, acquire **10 s**, 50 conns, socket 30 s |
| `AwsHttpClientWrapper.defaultAsyncClient()` | nobody | connect **5 000 s**, acquire **10 000 s** | connect 5 s, acquire 10 s |
| DynamoDB via config, no explicit client | `visibility` + all Dynamo users | 50 conns, connect 2 s | **100 conns**, connect 5 s |
| SQS via config, no explicit client | all SQS users | 50 conns, connect 2 s | 50 conns, connect **5 s** |
| SNS via config, no explicit client | `booking`, `visibility` | 50 conns, connect 2 s | 50 conns, connect **5 s** |
| S3 via explicit `AwsStorageConfig`, no wrapper | — | 50 conns, connect 2 s | 50 conns, connect **5 s** |
| SES / SSM | `tx-tracking` (SES) | SDK defaults; a configured client was **ignored** | tuned defaults; a configured client is **honoured** |
| S3 via builder-mode wrapper | `visibility` | 1 s / 5 s / 50 — caller-supplied | **unchanged** — caller-supplied always wins |

Every delta moves in a safe direction:

* The two absurd timeouts collapse to sane ones. Nobody can be relying on a 6.9-day acquisition timeout.
* Connect timeout 2 s → 5 s is more tolerant, not less; the risk of a longer connect timeout is marginally slower failure detection, which 3 s does not meaningfully change.
* DynamoDB's pool doubles 50 → 100. A capacity increase, and it matches what `DynamoRepositoryFactory` always intended. Worth noting that under ION-16431 conditions a larger pool means more sockets a `connManager.shutdown()` destroys at once — but pool death was caused by heap exhaustion, which `maxResultSize` already bounds, and 100 was the documented intent.
* **Explicitly configured transports are untouched.** `visibility`'s S3 builder-mode wrapper still wins; the caller always overrides the default.

### Tests

```java
@Test
void defaultSyncTransportUsesSaneTimeouts() {
    // The regression guard for the units bug. Fails against 1.0.30.
    assertThat(AwsHttpDefaults.CONNECTION_TIMEOUT).isEqualTo(Duration.ofSeconds(5));
    assertThat(AwsHttpDefaults.CONNECTION_ACQUISITION_TIMEOUT).isEqualTo(Duration.ofSeconds(10));
    assertThat(AwsHttpDefaults.CONNECTION_TIMEOUT).isLessThan(Duration.ofMinutes(1));
    assertThat(AwsHttpDefaults.CONNECTION_ACQUISITION_TIMEOUT).isLessThan(Duration.ofMinutes(1));
}

@Test
void dynamoDbConfigDefaultsToTheLargerPool() {
    DynamoDbClientConfig config = DynamoDbClientConfig.builder()
        .region(AwsRegionWrapper.of("us-east-1"))
        .credentialsProvider(...)
        .build();                                    // no explicit .httpClient(...)

    assertThat(config.getHttpClient()).isNotNull();  // non-null guarantee preserved
    assertThat(config.getHttpClient().isBuilder()).isFalse();
}

@Test
void explicitHttpClientStillWins() {
    AwsHttpClientWrapper explicit = AwsHttpClientWrapper.ofSyncBuilder(
        ApacheHttpClient.builder().maxConnections(7));
    AwsStorageConfig config = AwsStorageConfig.builder()
        .region(...).credentialsProvider(...).httpClient(explicit).build();

    assertThat(config.getHttpClient()).isSameAs(explicit);
}
```

An ArchUnit-style guard is worth adding too: no `Duration.ofSeconds`/`ofMinutes` call may take an identifier ending in `_MILLIS`. That is the rule that would have caught this at review.


---

# 2. D-5 — retrying `Crc32MismatchException`

## 2.1 What was observed

From the incident logs (32 records, all `dynamodb.query`):

```
RetryableStageHelper.retryPolicyDisallowedRetryException(RetryableStageHelper.java:168)
Crc32MismatchException: Expected 2335829902 ... actual 708209572 (SDK Attempt Count: 1)
```

`SDK Attempt Count: 1` means the SDK made one attempt and stopped. `retryPolicyDisallowedRetryException` means the retry strategy was consulted and said no.

## 2.2 Why the SDK refuses — confirmed at bytecode level

The register attributes this to `DefaultRetryStrategy.standardStrategyBuilder()` not classifying the exception as retryable. **That is not quite the mechanism, and the real one matters because it changes the fix.** Four facts, each verified by decompiling `~/.m2` jars at 2.30.24:

**Fact 1 — the exception says it *is* retryable.**
```
$ javap -c -p software.amazon.awssdk.core.exception.Crc32MismatchException
  public boolean retryable();
    Code:
       0: iconst_1     ← returns true
       1: ireturn
```

**Fact 2 — but nothing ever reads that flag for this exception.** The SDK's default "is this retryable" predicate is `SdkDefaultRetryStrategy.retryOnRetryableException`, which delegates to `RetryUtils.isRetryableException`:
```
  public static boolean isRetryableException(SdkException);
       0: invokestatic  isServiceException            ← must be an SdkServiceException
       4: ifeq          21                            ← if not: return false, immediately
       8: invokestatic  toServiceException
      11: invokevirtual SdkServiceException.isRetryableException
```
`Crc32MismatchException extends SdkClientException`, **not** `SdkServiceException`. The predicate short-circuits at the first branch and returns `false` without ever calling `retryable()`.

**Fact 3 — it is not in the retryable-exception allowlist either.** `SdkDefaultRetrySetting.RETRYABLE_EXCEPTIONS` (from the class initialiser):
```
RetryableException, java.io.IOException, java.io.UncheckedIOException, ApiCallAttemptTimeoutException
```
`Crc32MismatchException` is none of these, and is created without an `IOException` cause.

**Fact 4 — a bare strategy still gets the AWS defaults, so "the strategy has no predicates" is not the explanation.** `AwsDefaultClientBuilder.configureRetryStrategy` checks `strategy.useClientDefaults()` and, if true, calls `addDefaults(AwsRetryStrategy.retryStrategyDefaults())` and `addDefaults(SdkDefaultRetryStrategy.retryStrategyDefaults())`. So even a bare `DefaultRetryStrategy.standardStrategyBuilder().build()` ends up with the full default predicate set.

### Conclusion

> **`Crc32MismatchException` is unretryable by construction on every AWS SDK v2 client at 2.30.x** — not because of anything `DynamoRepositoryFactory` configured, but because the exception is a *client* exception whose own `retryable()` flag the default predicates never consult. This affects S3, SQS and SNS identically. The only reason DynamoDB shows it in the logs is that DynamoDB responses carry an `x-amz-crc32` header the SDK validates on every response.

Retrying is unambiguously the right behaviour: a CRC32 mismatch means the response bytes were corrupted in transit. The request itself very likely succeeded server-side; the client simply cannot trust what came back.

## 2.3 The fix

Predicates added via `retryOnException` **accumulate** — verified: `BaseRetryStrategy$Builder.setRetryOnException` does `retryPredicates.add(...)`, and `shouldAttempt` is a logical OR across the list. So adding one predicate augments the defaults; it does not replace them.

There are two ways to inject it, and the choice is forced by a mutual-exclusion rule in the SDK.

### The mutual-exclusion trap — read this before writing the code

`ClientOverrideConfiguration.Builder` has three retry setters, and **each one nulls the other two**:

| Call | Sets | Nulls |
|---|---|---|
| `retryStrategy(RetryStrategy)` | `CONFIGURED_RETRY_STRATEGY` | `CONFIGURED_RETRY_CONFIGURATOR`, `CONFIGURED_RETRY_MODE`, `RETRY_POLICY` |
| `retryStrategy(Consumer<RetryStrategy.Builder<?,?>>)` | `CONFIGURED_RETRY_CONFIGURATOR` | `CONFIGURED_RETRY_STRATEGY`, `CONFIGURED_RETRY_MODE`, `RETRY_POLICY` |
| `retryStrategy(RetryMode)` | `CONFIGURED_RETRY_MODE` | `CONFIGURED_RETRY_STRATEGY`, `CONFIGURED_RETRY_CONFIGURATOR`, `RETRY_POLICY` |

(Verified in `ClientOverrideConfiguration$DefaultBuilder` bytecode — each setter writes its own option then `aconst_null`s the other three.)

So **you cannot** write:

```java
// ❌ WRONG — the second call silently discards config.getRetryMode()
Optional.ofNullable(config.getRetryMode())
    .ifPresent(mode -> overrideBuilder.retryStrategy(RetryMode.valueOf(mode.name())));
overrideBuilder.retryStrategy(b -> b.retryOnException(RETRY_ON_CRC32_MISMATCH));
```

That is the obvious edit, and it would silently downgrade every consumer that configures `retryMode` back to the default `STANDARD` mode. Guard against it in review.

### The correct implementation

`cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/AwsRetryStrategies.java` (new — shared, so S3/SQS/SNS get it too):

```java
package com.inttra.mercury.cloudsdk.aws.config;

import software.amazon.awssdk.awscore.retry.AwsRetryStrategy;
import software.amazon.awssdk.core.client.config.ClientOverrideConfiguration;
import software.amazon.awssdk.core.exception.Crc32MismatchException;
import software.amazon.awssdk.core.retry.RetryMode;
import software.amazon.awssdk.retries.api.RetryStrategy;

import java.util.function.Predicate;

/**
 * Shared retry-strategy augmentation for cloud-sdk AWS clients.
 *
 * <p><b>Why this exists.</b> {@link Crc32MismatchException} reports {@code retryable() == true},
 * but the AWS SDK v2 default retry predicate ({@code RetryUtils.isRetryableException}) only reads
 * that flag on {@code SdkServiceException}. {@code Crc32MismatchException} extends
 * {@code SdkClientException}, so the flag is never consulted, and the exception is not in
 * {@code SdkDefaultRetrySetting.RETRYABLE_EXCEPTIONS} either. The result is that a transient
 * response-checksum corruption becomes a hard, first-attempt application error on every AWS SDK v2
 * client. 32 such failures were observed on {@code dynamodb.query} during ION-16431.
 *
 * <p>Verified against AWS SDK 2.30.24.
 */
public final class AwsRetryStrategies {

    /**
     * Matches a CRC32 response-checksum mismatch, directly or as the cause of a wrapping exception.
     *
     * <p><b>Idempotency note.</b> A checksum mismatch is a corrupted <em>response</em>; the request
     * may already have been applied server-side. Retrying is therefore safe for reads
     * (Query/Scan/GetItem) and for naturally idempotent writes (PutItem, DeleteItem, conditional
     * UpdateItem). It is <em>not</em> strictly safe for a non-idempotent UpdateItem using an
     * {@code ADD} / increment expression, which could be applied twice. This is exactly the hazard
     * the SDK already accepts by retrying on {@link java.io.IOException}, so we are not introducing
     * a new class of risk — but callers performing counter-style updates should use a condition
     * expression or a client request token.
     */
    public static final Predicate<Throwable> CRC32_MISMATCH = throwable -> {
        if (throwable instanceof Crc32MismatchException) {
            return true;
        }
        return throwable != null && throwable.getCause() instanceof Crc32MismatchException;
    };

    private AwsRetryStrategies() {
    }

    /**
     * Applies the retry configuration to {@code overrideBuilder}, always augmenting it with
     * {@link #CRC32_MISMATCH}.
     *
     * <p>{@code retryStrategy(RetryMode)}, {@code retryStrategy(RetryStrategy)} and
     * {@code retryStrategy(Consumer)} are mutually exclusive on
     * {@link ClientOverrideConfiguration.Builder} — each nulls the other two — so this method
     * makes exactly one of those calls.
     *
     * @param retryMode the caller's configured retry mode, or {@code null} to keep the SDK default
     */
    public static void applyRetryStrategy(ClientOverrideConfiguration.Builder overrideBuilder,
                                          RetryMode retryMode) {
        if (retryMode == null) {
            // No explicit mode: the SDK resolves its own default strategy
            // (AwsRetryStrategy.defaultRetryStrategy()), and this configurator is applied on top of
            // it via toBuilder() -> configurator -> build(). All default predicates are preserved.
            overrideBuilder.retryStrategy(builder -> builder.retryOnException(CRC32_MISMATCH));
            return;
        }

        // Explicit mode: materialise the AWS strategy for that mode, then add our predicate.
        RetryStrategy.Builder<?, ?> strategyBuilder = AwsRetryStrategy.forRetryMode(retryMode).toBuilder();
        strategyBuilder.retryOnException(CRC32_MISMATCH);
        overrideBuilder.retryStrategy(strategyBuilder.build());
    }
}
```

Then `DynamoRepositoryFactory.createOverrideConfig`:

```diff
     public static ClientOverrideConfiguration createOverrideConfig(DynamoDbClientConfig config) {
         ClientOverrideConfiguration.Builder overrideBuilder = ClientOverrideConfiguration.builder();
 
         Optional.ofNullable(config.getClientExecutionTimeout())
             .ifPresent(overrideBuilder::apiCallTimeout);
 
         Optional.ofNullable(config.getApiCallTimeout())
             .ifPresent(overrideBuilder::apiCallTimeout);
 
         Optional.ofNullable(config.getApiCallAttemptTimeout())
             .ifPresent(overrideBuilder::apiCallAttemptTimeout);
 
-        Optional.ofNullable(config.getRetryMode())
-            .ifPresent(mode -> overrideBuilder.retryStrategy(RetryMode.valueOf(mode.name())));
+        // Always augments the resolved strategy with a Crc32MismatchException predicate.
+        // Must be a single call: the retryStrategy(...) overloads are mutually exclusive.
+        AwsRetryStrategies.applyRetryStrategy(overrideBuilder, config.getRetryMode());
 
         return overrideBuilder.build();
     }
```

Apply the same one-line substitution in `MessagingClientFactory.createOverrideConfig`, `NotificationClientFactory.createOverrideConfig` and `S3ClientFactory.createOverrideConfig`.

`RetryMode.valueOf(mode.name())` in the removed line was a no-op round-trip — `config.getRetryMode()` already returns a `RetryMode`. Dropping it is a small cleanup.

### Dependency note

`AwsRetryStrategy` lives in `software.amazon.awssdk:aws-core`, which is on the compile classpath transitively via `dynamodb` / `s3` / `sqs`. Add it explicitly to `cloud-sdk-aws/pom.xml` so the build does not depend on a transitive path:

```xml
<dependency>
    <groupId>software.amazon.awssdk</groupId>
    <artifactId>aws-core</artifactId>
</dependency>
```
(version comes from the `bom:2.30.24` import already in `dependencyManagement`)

### Tests

```java
@Test
void crc32MismatchPredicateMatchesDirectly() {
    assertThat(AwsRetryStrategies.CRC32_MISMATCH
        .test(Crc32MismatchException.create("checksum mismatch", null))).isTrue();
}

@Test
void crc32MismatchPredicateMatchesAsCause() {
    Throwable wrapped = SdkClientException.create("wrapped",
        Crc32MismatchException.create("checksum mismatch", null));
    assertThat(AwsRetryStrategies.CRC32_MISMATCH.test(wrapped)).isTrue();
}

@Test
void crc32MismatchPredicateIgnoresUnrelatedExceptions() {
    assertThat(AwsRetryStrategies.CRC32_MISMATCH.test(new IllegalStateException("nope"))).isFalse();
    assertThat(AwsRetryStrategies.CRC32_MISMATCH.test(null)).isFalse();
}

@Test
void explicitRetryModeIsPreserved() {
    ClientOverrideConfiguration config = build(DynamoDbClientConfig.builder()
        .retryMode(RetryMode.STANDARD) /* ...required fields... */ .build());

    // regression guard for the mutual-exclusion trap: the mode must survive
    assertThat(config.retryStrategy()).isPresent();
}

@Test
void crc32MismatchIsRetriedEndToEnd() {
    // Highest-value assertion: exercise the built strategy directly.
    RetryStrategy strategy = /* strategy from createOverrideConfig(...) */;
    AcquireInitialTokenResponse initial = strategy.acquireInitialToken(
        AcquireInitialTokenRequest.create("dynamodb"));

    RefreshRetryTokenResponse refresh = strategy.refreshRetryToken(
        RefreshRetryTokenRequest.builder()
            .token(initial.token())
            .failure(Crc32MismatchException.create("checksum mismatch", null))
            .build());

    assertThat(refresh.delay()).isNotNull();   // a delay implies the retry was granted
}
```

The last test is the one that actually proves the defect is closed — it fails against today's code and passes after the change. Note it uses the public `retries-spi` API and needs no AWS network access.

### Complementary work (from the register, unchanged)

* **DynamoDB VPC endpoint.** CRC32 mismatches are corruption on the wire. Keeping DynamoDB traffic off the public internet removes the cause rather than retrying the symptom. Infrastructure change; track separately.
* **Alarm on retry rate.** If CRC32 retries become common, that is a network-health signal that should be visible. Once retried transparently it will otherwise be invisible — retrying a fault also hides it.

---

# 3. D-11 / D-10 — "this is unit tested, why is it dead code?"

## 3.1 First, the numbering

The register has two adjacent low-severity findings that are easy to conflate:

| ID | Where | Issue |
|---|---|---|
| **D-10** | `AwsHttpClientWrapper.getTypedClient()` | The `try/catch (ClassCastException)` is **dead code** |
| **D-11** | `S3StorageClient` put path | Throws `"Unexpected error during S3 read"` from a **write** path — a wrong message |

The question — *"this is unit tested, why is it dead code?"* — is about **D-10**. D-11 is a string literal with no test attached. Both are answered below.

## 3.2 D-10 — the code, the test, and why both are true at once

The method:

```java
// AwsHttpClientWrapper.java:98-108
@SuppressWarnings("unchecked")
public <T> T getTypedClient() {
    try {
        return (T) underlyingClient;
    } catch (ClassCastException e) {
        String actualType = underlyingClient.getClass().getSimpleName();
        throw new ClassCastException(
            String.format("Cannot cast client of type %s to requested type. Client is %s",
                actualType, isAsync ? "async" : "sync"));
    }
}
```

The test that appears to cover it:

```java
// AwsHttpClientWrapperTest.java:175-185
@Test
void shouldThrowClassCastExceptionForIncorrectType() {
    SdkHttpClient syncClient = ApacheHttpClient.builder()
        .connectionTimeout(Duration.ofSeconds(5)).build();
    AwsHttpClientWrapper wrapper = AwsHttpClientWrapper.ofSync(syncClient);

    assertThatThrownBy(() -> {
        SdkAsyncHttpClient wrongType = wrapper.getTypedClient();
    }).isInstanceOf(ClassCastException.class);
}
```

**The test passes. The catch block never runs. Both statements are true, and the bytecode shows exactly why.**

### The mechanism: erasure moves the cast to the caller

Java generics are erased. `<T> T getTypedClient()` has no runtime knowledge of `T`; its erasure is `Object getTypedClient()`. Inside the method, `(T) underlyingClient` is an **unchecked cast** — that is precisely what `@SuppressWarnings("unchecked")` is acknowledging. javac emits **no `checkcast` instruction** for it, because there is nothing to check against.

The cast that *does* happen is a **synthetic `checkcast` inserted at the call site**, where the static target type is known.

### The proof

Method body, from `cloud-sdk-aws/target/classes`:

```
public <T> T getTypedClient();
  Code:
     0: aload_0
     1: getfield      #21    // Field underlyingClient:Ljava/lang/Object;
     4: areturn                                    ← the whole try block: 3 instructions
     5: astore_1                                   ← catch handler starts here
     6: aload_0
     ...
    17: new           #109   // class java/lang/ClassCastException
    ...
  Exception table:
     from    to  target type
         0     4     5   Class java/lang/ClassCastException
```

The protected region is bytecode offsets **0 to 4**: `aload_0`, `getfield`, `areturn`. **None of those three instructions can throw `ClassCastException`.** `aload` reads a local, `getfield` reads a field, `areturn` returns a reference. The handler at offset 5 is structurally unreachable.

Now the test's lambda, from `cloud-sdk-aws/target/test-classes`:

```
private static void lambda$shouldThrowClassCastExceptionForIncorrectType$0(AwsHttpClientWrapper);
  Code:
     0: aload_0
     1: invokevirtual #43   // AwsHttpClientWrapper.getTypedClient:()Ljava/lang/Object;
     4: checkcast     #85   // class software/amazon/awssdk/http/async/SdkAsyncHttpClient   ← HERE
     7: astore_1
     8: return
```

The sequence at runtime is:

1. `getTypedClient()` is invoked and **returns normally**, handing back an `ApacheHttpClient` as an `Object`.
2. Control returns to the test's lambda.
3. The test's own `checkcast SdkAsyncHttpClient` at offset 4 fails and throws `ClassCastException`.
4. AssertJ catches it and `isInstanceOf(ClassCastException.class)` passes.

So the test asserts a true fact — *"assigning the result to the wrong type throws CCE"* — but that fact is a property of **the Java language**, not of `getTypedClient()`. The method contributed nothing; the identical CCE would occur if the `try/catch` were deleted.

### The one-line experiment that falsifies it

Add a message assertion:

```java
assertThatThrownBy(() -> { SdkAsyncHttpClient wrongType = wrapper.getTypedClient(); })
    .isInstanceOf(ClassCastException.class)
    .hasMessageContaining("Cannot cast client of type");   // ← FAILS
```

The actual message will be the JVM's:
```
class software.amazon.awssdk.http.apache.ApacheHttpClient cannot be cast to
class software.amazon.awssdk.http.async.SdkAsyncHttpClient
```
never the hand-written `"Cannot cast client of type %s ..."`. The custom message is unreachable in the current code and always has been.

### Why "it is unit tested" was misleading

* The test is named after the *behaviour* (`shouldThrowClassCastExceptionForIncorrectType`), not the *implementation*, so reading the test name suggests the handler is covered.
* `isInstanceOf(...)` without `hasMessage*(...)` cannot distinguish "our handler threw a CCE" from "the JVM threw a CCE". Exception *type* assertions are weak; for a hand-written handler, the message is the only evidence the handler ran.
* Line coverage would actually report the catch block as **uncovered** — worth checking JaCoCo output to confirm, since it is a cheap independent signal.

> **General lesson worth carrying into review:** an exception-handling test that asserts only the exception type, for a handler whose entire purpose is a better message, cannot prove the handler ran. Assert the message.

### The fix

Folded into D-1 Option A (§1.3):

1. `applyToSync` / `applyToAsync` mean no production code calls `getTypedClient()` at all.
2. The typed accessors (`syncClient()`, `asyncClient()`, `syncClientBuilder()`, `asyncClientBuilder()`) do a **real** mode check and throw `IllegalStateException` with the actual mode and class name — a genuine, reachable, testable diagnostic.
3. `getTypedClient()` keeps the unchecked cast (for source compatibility with any external caller) but loses the dead `try/catch` and gains `@Deprecated(forRemoval = true)`.
4. The misleading test is replaced by `shouldRejectUnwrappingSyncInstanceAsAsync` (§1.6), which asserts on the message and therefore genuinely covers the handler.

If you would rather keep an unwrap-with-check helper, the standard idiom is to take the class token so the check is real and inside the method:

```java
public <T> T getTypedClient(Class<T> type) {
    if (!type.isInstance(underlyingClient)) {
        throw new ClassCastException(
            String.format("Cannot cast %s (%s) to %s",
                underlyingClient.getClass().getName(), mode, type.getName()));
    }
    return type.cast(underlyingClient);
}
```
Here the `isInstance` check is genuinely reachable and the custom message is genuinely produced.

## 3.3 D-11 — already fixed, uncommitted

The register cites `S3StorageClient.putObject:638` throwing `RuntimeException("Unexpected error during S3 read")` from a write path. The working tree already carries the fix (currently **uncommitted**):

```diff
// S3StorageClient.java:716-721
         } catch (Exception e) {
-            log.error("Unexpected error while reading from S3", e);
-            throw new RuntimeException("Unexpected error during S3 read", e);
+            log.error("Unexpected error while writing to S3", e);
+            throw new RuntimeException("Unexpected error during S3 write", e);
         }
```

**Action: commit this.** `git show HEAD:...S3StorageClient.java` still has `"S3 read"`, so it is only in the working tree today and would be lost on a hard reset.

## 3.4 Residual finding in the same block (new — not in the register)

That method is the only exception path in `S3StorageClient` that does **not** route through the shared handlers. Compare:

```java
// Everywhere else in the class (~20 sites):
} catch (S3Exception e)        { throw handleS3Exception(getAwsErrorDetails(e), e); }  // → S3OperationException
} catch (SdkClientException e) { throw handleSdkException(e); }                        // → S3OperationException
} catch (Exception e)          { throw handleUnexpectedException(e); }                 // → S3OperationException

// S3StorageClient.java:711-721 only:
} catch (S3Exception e)        { throw new RuntimeException("Failed to upload file to S3", e); }
} catch (SdkClientException e) { throw new RuntimeException("AWS SDK client error", e); }
} catch (Exception e)          { throw new RuntimeException("Unexpected error during S3 write", e); }
```

`AbstractStorageObject.handleS3Exception` / `handleSdkException` / `handleUnexpectedException` all return `S3OperationException`. So a caller doing `catch (S3OperationException e)` handles every S3 failure in the class **except** the ones from this one method, which arrive as bare `RuntimeException`. Recommend aligning it:

```diff
         } catch (S3Exception e) {
-            log.error("AWS S3 service error '{}' during upload: bucket='{}', key='{}'",
-                      e.awsErrorDetails().errorMessage(), bucket, fileName);
-            throw new RuntimeException("Failed to upload file to S3", e);
+            String errorMessage = getAwsErrorDetails(e);
+            log.error("AWS S3 service error during upload: bucket='{}', key='{}': {}",
+                      bucket, fileName, errorMessage);
+            throw handleS3Exception(errorMessage, e);
         } catch (SdkClientException e) {
-            log.error("AWS SDK client error", e);
-            throw new RuntimeException("AWS SDK client error", e);
+            throw handleSdkException(e);
         } catch (Exception e) {
-            log.error("Unexpected error while writing to S3", e);
-            throw new RuntimeException("Unexpected error during S3 write", e);
+            throw handleUnexpectedException(e);
         }
```

Note `e.awsErrorDetails().errorMessage()` on the original line 712 is an unguarded chain — `awsErrorDetails()` can be null, in which case the *logging* call NPEs while handling an S3 error. `getAwsErrorDetails(e)` (line 277) already handles that with `Optional`. This is a small latent bug fixed for free by the alignment above.

**This is a behaviour change** (`RuntimeException` → `S3OperationException`, which is itself a `RuntimeException` subclass, so callers catching `RuntimeException` are unaffected; callers matching on the exact type or on message text would be). It is not part of D-11 as filed — raising it here for a decision rather than folding it in silently.

---

# 4. `MessagingClient extends AutoCloseable` — does it earn its keep?

PR #46 made `MessagingClient<T> extends AutoCloseable` with an abstract `void close()`, and `SqsMessagingClient.close()` delegates to `sqsClient.close()`. Three questions follow, and the answers are less comfortable than the change implies.

*(Ticket note: the commits are labelled **ION-16431** — `a4b6d11` "ION-16431 Dedicated HTTP Clients". Worth using that number consistently for traceability.)*

## 4.1 What `close()` actually releases — verified, and it is not what the Javadoc says

`SqsMessagingClient.close()` carries this Javadoc:

> *"Closes the SQS messaging client and releases its resources. This method closes the underlying SqsClient **and its connection pools**."*

**The connection-pool half is false**, for exactly the ownership reason that made the D-4 comment wrong. Trace it:

```
SqsMessagingClient.close()
  → sqsClient.close()                          DefaultSqsClient.close()
      → clientHandler.close()
          → SdkClientConfiguration.close()
              → AttributeMap.close()           closes every closeable attribute, including SYNC_HTTP_CLIENT
```

And what is in `SYNC_HTTP_CLIENT`? `MessagingClientFactory` builds every SQS client with `.httpClient(<instance>)`, and `SdkDefaultClientBuilder.httpClient(SdkHttpClient)` wraps its argument:

```
public final B httpClient(SdkHttpClient);
   0: aload_1
   1: ifnull  14
   4: new     SdkDefaultClientBuilder$NonManagedSdkHttpClient    ← wrapped here
```

whose `close()` is:

```
public void close();
   0: return                                                     ← a no-op. Literally.
```

So `SqsMessagingClient.close()` closes the SDK's internal scheduled executor, future-completion executor, metric publishers and (if closeable) the credentials provider — **but leaves the Apache `PoolingHttpClientConnectionManager` and its sockets fully open.** The one resource the Javadoc names is the one resource it does not release.

Two further measurements that shrink the claimed benefit:

* **Apache's `idle-connection-reaper` thread is a daemon** (`setDaemon(true)` → `iconst_1` in `IdleConnectionReaper`). It does not block JVM exit, so an unclosed client cannot hang a `SIGTERM` shutdown into an ECS `SIGKILL`. That is the usual strongest argument for closing HTTP clients, and it does not apply here.
* **A `@Singleton` alive for the life of the JVM is not a leak.** A leak is repeated allocation without release. There is exactly one SQS client per process, created at startup, referenced until exit. At shutdown the OS reclaims every socket and file descriptor regardless.

### So what leak *is* being saved?

| Scenario | Real benefit of `close()` |
|---|---|
| Normal production shutdown (ECS stops the task) | **Effectively none.** Sockets are reclaimed by the OS; the reaper is a daemon; the pool is not closed anyway. |
| Graceful drain ordering | **Marginal.** An in-flight 20 s long-poll dies with the process instead of being aborted cleanly. |
| **Many app instances in one JVM** — `DropwizardAppExtension`, integration-test suites, embedded/multi-tenant hosting | ✅ **Genuine.** Each un-closed app accumulates an SDK executor, a credentials-provider chain and a connection manager. Across hundreds of tests this is a real, observable leak. |
| Prerequisite for rebuilding a client whose pool has been destroyed (§7.2 of the source document) | ✅ **Genuine, but not delivered** — see §4.2. |

**Verdict: the change is defensible but oversold.** Its honest value is test-harness hygiene plus a foundation for client rebuild. It is not a production resource-leak fix, and it does not do what its Javadoc claims.

### Making it true — and the link back to D-1

`close()` would release the connection pool if the SQS client were built in **builder mode** (`httpClientBuilder(...)`), because then the SDK owns the transport and closes it. That is the *correct* rationale for builder mode — the one the D-4 Javadoc should have given instead of the "DynamoDB timeout" story:

> `httpClient(instance)` → `NonManagedSdkHttpClient` → the SDK **never** closes your transport.
> `httpClientBuilder(...)` → the SDK **owns** the transport and closes it with the service client.

So **D-1's Option A is a prerequisite for `close()` to mean anything.** Today only `S3ClientFactory` can honour builder mode; until `MessagingClientFactory` can too, `MessagingClient.close()` cannot close a pool no matter how it is wired.

**Required, whichever direction you take:** correct the `SqsMessagingClient.close()` Javadoc. It is wrong today and will mislead exactly the way the D-4 comment did.

```java
/**
 * Closes the underlying {@link SqsClient}, releasing the SDK's internal executors, metric
 * publishers and credentials provider.
 *
 * <p><b>Whether the HTTP connection pool is released depends on how the client was built.</b>
 * If the transport was supplied pre-built ({@code httpClient(instance)}) the SDK wraps it in
 * {@code NonManagedSdkHttpClient}, whose {@code close()} is a no-op, and the pool stays open.
 * Only builder mode ({@code httpClientBuilder(...)}) makes the SDK the owner and closes it.
 *
 * <p>This client is a process-scoped singleton. {@code close()} is intended for application
 * shutdown only; a closed instance cannot be reopened and every injected holder keeps a dead
 * reference. See the class Javadoc for the rebuild pattern.
 */
```

## 4.2 "If they are closed while the task is running, how do they restart?" — they do not

This is the sharpest question in the set, and the current design has no answer.

**When does `close()` actually fire today?** Only from `Managed.stop()`, which Dropwizard invokes during `Environment` shutdown — after Jetty has stopped accepting and in-flight requests have drained. So the scenario of a client being closed mid-operation does **not** arise from the lifecycle hook. On that narrow point the current wiring is safe.

**But the moment anything else calls `close()`, the service is permanently broken.** Trace what Guice actually did:

```java
@Provides @Singleton
public MessagingClient<String> provideMessagingClient() { ... }   // ONE instance

// injected BY REFERENCE into every collaborator:
SQSClient          → holds MessagingClient          (booking, booking-bridge)
SqsMessageHandler  → holds MessagingClient          (visibility)
ReprocessService   → holds MessagingClient          (tx-tracking)
```

Guice hands out the **reference**, not a lookup. Close it and every holder keeps pointing at a dead `SqsClient`; the next call throws `IllegalStateException`. There is no indirection through which a replacement could be published — no provider, no supplier, no proxy. **A closed singleton is unrecoverable for the life of the JVM.**

This matters because §7.2 of the source document proposes exactly the thing this design cannot support:

```java
} catch (IllegalStateException e) {
    if (e.getMessage().contains("Connection pool shut down")) {
        rebuildClient();          // ← needs to REPLACE the instance every holder sees
    }
}
```

`AutoCloseable` gives you *teardown*. Rebuild needs *indirection*. They are different capabilities and adding the first does not advance the second.

> **If rebuild is the goal, the shape has to change** — inject `Provider<MessagingClient<String>>` (or a `Supplier`), or keep `SqsMessagingClient` as a stable façade holding a `volatile SqsClient` it can swap internally. The façade is the better fit here: holders keep one stable reference, the swap is invisible, and it is guarded inside the class rather than at every call site. That is a separate piece of work and should not be smuggled in under "add `AutoCloseable`."

## 4.3 Yes, it is a breaking change — and in two ways

**Verified blast radius across both repositories:**

```
implements MessagingClient  → cloud-sdk-aws/SqsMessagingClient      (the only hit)
new MessagingClient<...>(){ → none
```
Searched `booking`, `booking-bridge`, `bill-of-lading-v2`, `auth`, `visibility`, `tx-tracking` and all of `mercury-services-commons`. Every consumer *wraps* or *injects* a `MessagingClient`; all test doubles are Mockito mocks, which synthesise `close()` automatically. Inside these two repos the break is theoretical.

**Break 1 — adding an abstract method to a published interface.**

| | Effect |
|---|---|
| Source | Any class implementing `MessagingClient<T>` without `close()` **fails to compile** against 1.0.29+ |
| Binary | A class compiled against ≤1.0.28 loads fine, then throws **`AbstractMethodError`** the first time anything calls `close()` — including the new `Managed.stop()` hook, i.e. at shutdown, where it is least likely to be noticed |

**Break 2 — the one that is easy to miss: `extends AutoCloseable` changes what *compiles at call sites*, not just what implementors must provide.**

```java
// Does not compile against 1.0.28. Compiles against 1.0.29+. Destroys the app.
try (MessagingClient<String> c = MessagingClientFactory.createDefaultStringClient()) {
    c.sendMessage(queueUrl, body);
}   // ← closes a client that other components may already hold
```

Inheriting `AutoCloseable` makes try-with-resources legal on a process-scoped singleton, where it is *always* a bug. It also switches on SpotBugs/Sonar `OBL_UNSATISFIED_OBLIGATION` and IDE "resource leak" inspections at **every** `MessagingClientFactory.create*` call site that does not close — a wave of warnings that are all false positives for a DI-managed singleton, and which teams typically silence with blanket suppressions that then hide real findings.

Note the interface narrows `AutoCloseable.close() throws Exception` to `void close()` with no `throws`. That narrowing is legal and correct — callers are not forced into try/catch — and should be kept in any redesign.

## 4.4 Only one of five modules actually uses it

The change is 20 % deployed. Verified wiring:

| Module | `MessagingClient` provider | Registers `Managed` / calls `close()`? |
|---|---|---|
| `visibility` | `VisibilityMessagingModule:50` | ✅ **Yes** — anonymous `Managed` in the `@Provides` |
| `booking` | `BookingMessagingModule:45` | ❌ No |
| `booking-bridge` | `BookingBridgeMessagingModule:54` | ❌ No |
| `bill-of-lading-v2` | `BillOfLadingInjector:75` | ❌ No |
| `tx-tracking` | `TxTrackingModule:86` (`bind(...).toInstance(...)`) | ❌ No |

And the same un-closed-singleton pattern applies to every other cloud-sdk client — `StorageClient`, `NotificationService`, `EmailService`, `CloudParameterStore` — **none of which have a `close()` at all.** Every one of those modules also creates an S3 `StorageClient` and never closes it.

So the current state is: one interface out of five gained a breaking `close()`, one module out of five calls it, and what it closes is not the resource the Javadoc names. That is not a coherent lifecycle story — it is a single-service patch wearing an API change.

## 4.5 Recommended approach

The goal should be: **uniform, opt-in-free lifecycle across all cloud-sdk clients, with zero compatibility breakage, and no new footguns.** Four parts.

### Part 1 — a shared `CloudResource` with a `default` no-op, in `cloud-sdk-api`

```java
package com.inttra.mercury.cloudsdk.config;

/**
 * A cloud client whose backing resources can be released at application shutdown.
 *
 * <p><b>Deliberately does not extend {@link AutoCloseable}.</b> These clients are
 * process-scoped singletons created by a DI container. Inheriting {@code AutoCloseable}
 * would make {@code try (var c = factory.create()) { ... }} compile — which is always a bug
 * for a shared singleton — and would trigger resource-leak inspections at every factory call
 * site. Lifecycle here is owned by the container, not by a lexical block.
 *
 * <p><b>Terminal.</b> A closed client cannot be reopened, and every component that was
 * injected with it keeps a dead reference. Call this only during application shutdown.
 */
public interface CloudResource {
    /** Releases backing resources. Idempotent. Default is a no-op. */
    default void close() {
        // no-op: implementations that hold releasable resources override this
    }
}
```

Then:

```java
public interface MessagingClient<T> extends CloudResource { ... }   // drop the abstract close()
public interface StorageClient      extends CloudResource { ... }
public interface NotificationService extends CloudResource { ... }
public interface EmailService        extends CloudResource { ... }
```

Why `default` rather than abstract, given the blast radius inside our repos is nil: because this is being applied to **five** interfaces, and only the `MessagingClient` case has a verified-nil blast radius. A `default` body is source- **and** binary-compatible for all five, needs no downstream verification sweep, and lets `S3StorageClient`, `SnsService` and the SES client adopt real `close()` bodies incrementally. Uniformity of approach across five interfaces beats marginal strictness on one.

Why not `AutoCloseable`: see Break 2 in §4.3. The interop you give up is negligible; the footgun you remove is not. If a caller genuinely needs `AutoCloseable`, `() -> client.close()` is one lambda away.

### Part 2 — a Dropwizard adapter, so modules stop hand-rolling `Managed`

`cloud-sdk-api` already depends on `dropwizard-core` (verified in its `pom.xml`), so this belongs there:

```java
package com.inttra.mercury.cloudsdk.config;

import io.dropwizard.lifecycle.Managed;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Bridges a {@link CloudResource} onto the Dropwizard lifecycle. */
public final class ManagedCloudResource implements Managed {

    private static final Logger LOG = LoggerFactory.getLogger(ManagedCloudResource.class);

    private final CloudResource resource;
    private final String name;

    private ManagedCloudResource(CloudResource resource, String name) {
        this.resource = resource;
        this.name = name;
    }

    public static Managed of(CloudResource resource, String name) {
        return new ManagedCloudResource(resource, name);
    }

    @Override
    public void start() {
        // nothing to do — the client is constructed eagerly by its provider
    }

    @Override
    public void stop() {
        LOG.info("Closing {} on application shutdown", name);
        try {
            resource.close();
        } catch (RuntimeException e) {
            // Never let a shutdown hook abort the rest of the shutdown sequence.
            LOG.warn("Failed to close {} cleanly", name, e);
        }
    }
}
```

The `catch` matters: Dropwizard stops the remaining `Managed` objects in reverse order, and one throwing `stop()` can abort the rest.

### Part 3 — register eagerly, which also closes D-8

The source document's D-8 flags that `environment.lifecycle().manage(...)` inside a lazy `@Provides @Singleton` is start-order dependent: if the first injection happens after Jetty has started, the `Managed` is added to an already-started `ContainerLifeCycle`. Jetty auto-starts and still stops it, so it works — but by accident. Bind eagerly instead.

Using **booking** as the reference call site:

```java
// BEFORE — BookingMessagingModule.java:43-50
@Provides
@Singleton
public MessagingClient<String> provideMessagingClient() {
    log.info("Creating SQS MessagingClient using cloud-sdk-aws factory");
    MessagingClient<String> messagingClient = MessagingClientFactory.createDefaultStringClient();
    log.info("SQS MessagingClient created successfully");
    return messagingClient;          // never closed
}
```

```java
// AFTER
public class BookingMessagingModule extends AbstractModule {

    private final BookingConfig bookingConfig;
    private final Environment environment;                       // ← new ctor arg

    public BookingMessagingModule(BookingConfig bookingConfig, Environment environment) {
        if (bookingConfig == null) throw new IllegalArgumentException("bookingConfig must not be null");
        if (environment == null)   throw new IllegalArgumentException("environment must not be null");
        this.bookingConfig = bookingConfig;
        this.environment = environment;
    }

    @Override
    protected void configure() {
        log.info("Configuring Booking Messaging module (SQS/SNS/S3) ...");

        // Eager: constructed here, so the Managed is registered before Jetty starts (D-8).
        MessagingClient<String> messagingClient = MessagingClientFactory.createDefaultStringClient();
        environment.lifecycle().manage(ManagedCloudResource.of(messagingClient, "SQS MessagingClient"));
        bind(new TypeLiteral<MessagingClient<String>>() {}).toInstance(messagingClient);

        StorageClient storageClient = StorageClientFactory.createDefaultS3Client();
        environment.lifecycle().manage(ManagedCloudResource.of(storageClient, "S3 StorageClient"));
        bind(StorageClient.class).toInstance(storageClient);
    }

    @Provides
    @Singleton
    public NotificationService provideNotificationService() { /* unchanged */ }
}
```

`bind(...).toInstance(...)` is what `tx-tracking` already does, so the pattern is established in the fleet. Downstream code is untouched — `SQSClient`'s `@Inject MessagingClient<String>` constructor keeps working verbatim, which is the point: **no consumer of the client changes, only the module that owns it.**

The same three lines apply to `booking-bridge`, `bill-of-lading-v2` and `tx-tracking`. `visibility` replaces its anonymous `Managed` with `ManagedCloudResource.of(...)` and can drop the `messagingClientOverride` test seam by binding a mock through `Modules.override(...)` instead.

### Part 4 — keep rebuild out of scope, and say so

Do not extend `CloudResource` with `reopen()` / `restart()`. If pool-death self-healing is wanted (source document §7.2), the right shape is a stable façade:

```java
public class SqsMessagingClient<T> implements MessagingClient<T> {
    private volatile SqsClient sqsClient;      // swappable behind a stable reference
    private final Supplier<SqsClient> clientFactory;
    private final AtomicInteger rebuilds = new AtomicInteger();
    // rebuildIfPoolShutDown() guarded by a lock + a rebuild cap
}
```

Holders keep one reference, the swap is invisible to them, and the guard lives in one class instead of at every call site. That is a separate change with its own tests — worth doing, not worth conflating with lifecycle.

## 4.6 Summary of §4

| Question | Answer |
|---|---|
| Does `close()` help the mercury-services modules? | **Barely, in production.** Genuine value is multi-instance test harnesses and as a foundation for client rebuild. |
| What leak is saved? | Not sockets at shutdown — the OS reclaims those and the reaper thread is a daemon. The SDK's executors and credentials provider, per app instance. |
| Does it close the connection pool, as documented? | **No.** `httpClient(instance)` → `NonManagedSdkHttpClient.close()` is a no-op. Only builder mode would. **Javadoc must be corrected.** |
| If a client is closed while running, can it restart? | **No.** Guice injected the reference into every holder; there is no indirection to publish a replacement through. `close()` fires only at shutdown today, so this is latent rather than live. |
| Is it a breaking API change? | **Yes, twice** — `AbstractMethodError` for implementors compiled against ≤1.0.28, and `extends AutoCloseable` newly legalises try-with-resources on a shared singleton plus a static-analysis wave. Blast radius inside our two repos is verified nil. |
| Best approach | `CloudResource` with a `default` no-op close, applied uniformly to all five client interfaces, **not** extending `AutoCloseable`; a `ManagedCloudResource` Dropwizard adapter in `cloud-sdk-api`; eager binding in every module (also closes D-8); rebuild kept as separate work. |

---

# 5. Release plan — what ships in 1.0.31-SNAPSHOT

## 5.0 What 1.0.30-SNAPSHOT already contains

Verified against `HEAD` (`1e2fcd6`) on `feature/ION-12310-commons-cloudsdk-refactoring`, `pom.xml:20 → 1.0.30-SNAPSHOT`:

| In 1.0.30 | Commit | Status |
|---|---|---|
| Rebase onto `develop` — Jetty/logback OWASP hardening | `1e2fcd6` | ✅ Clean |
| Dedicated HTTP clients — `isBuilder` + `ofSyncBuilder`/`ofAsyncBuilder`, `S3ClientFactory` branch | `2f59609` | ⚠️ **Introduces D-1** |
| `MessagingClient extends AutoCloseable` + `SqsMessagingClient.close()` | `2f59609`, `18916ba` | ⚠️ **Breaking + false promise** (§4.1) |
| `QuerySpec.maxResultSize` on `query()` | `ce3e375`, `763fe84` | ✅ The load-bearing ION-16431 fix |
| `export()` result cap (`EnhancedDynamoRepository:1034`) | `ce3e375` | ✅ Closes the `export()` half of D-2 |
| `S3StorageClient` write-path message correction | committed | ✅ D-11 closed |

**Consumers today:** only `visibility` uses either of the two flagged features — builder mode for S3 (`VisibilityApplicationInjector.buildS3HttpClientWrapper`) and `close()` via a hand-rolled `Managed` (`VisibilityMessagingModule:56-67`). No other module touches them.

## 5.1 Scope of 1.0.31-SNAPSHOT — deliberately narrow

Three changes, all confined to `mercury-services-commons`:

1. **D-1 Option A** — `AwsHttpClientWrapper` rewrite and its consumption in the factories (§1.2–§1.4). Removal of the dead `try/catch` (**D-10**) comes with it, since it is the same method in the same file.
2. **Units fix + reachable tuned defaults** — `AwsHttpDefaults`, the `BaseAwsConfigBuilder.defaultHttpClient` hook, factory deduplication (§1.7).
3. **The `AutoCloseable` replacement** — `CloudResource` + `ManagedCloudResource` (§4.5).

Everything else is deferred to §6.

Changes 1 and 3 are behaviour-preserving. **Change 2 is not, deliberately** — it is the point of including it. The premise for consumers is therefore:

> **No source change in any `mercury-services` module. Recompile required. Two intentional behaviour corrections, both in the safe direction, itemised in §1.7 Part 5.**

### Why change 2 belongs here rather than in §6

An earlier draft of this plan deferred it to keep 1.0.31 purely behaviour-preserving. Re-checking reachability changed the answer:

`S3ClientFactory.createHttpClient()` is **not** dead. `S3ClientFactory.createDefaultS3Client():85` calls it directly, and that is reached in production by four call sites across three services and a Lambda (§1.1). Those S3 clients are running with an **83-minute connect timeout** and a **6.9-day connection-acquisition timeout** right now. Holding a defect of that severity to protect the tidiness of a release note is the wrong trade.

And once the units are fixed, making the tuned defaults reachable is nearly free — §1.7 Part 2 is a two-line delegation — so the two ship together rather than leaving a half-finished state in between.

### Does D-1 Option A on its own fix the tuned defaults?

**No.** `applyToSync`/`applyToAsync` change only *how* a wrapper attaches itself. They do not change *which* wrapper `BaseAwsConfig:32-34` creates when a caller supplies none, and the static fallback arm stays dead because `BaseAwsConfig` never yields null:

```java
public static void applyToSync(AwsHttpClientWrapper wrapper,
                               SdkSyncClientBuilder<?, ?> clientBuilder,
                               Supplier<SdkHttpClient> fallback) {
    if (wrapper == null) {                        // BaseAwsConfig never produces null …
        clientBuilder.httpClient(fallback.get()); // … so this arm stays dead
        return;
    }
    wrapper.applyToSync(clientBuilder);
}
```

That is exactly why §1.7 exists as a separate change: it fixes the *default* rather than the *attachment*. Note that §1.7 keeps the non-null guarantee — it corrects what `defaultSyncClient()` builds instead of making the config nullable, so no existing test or API contract moves.

## 5.2 Files touched in 1.0.31

### `cloud-sdk-aws`

| File | Change | § |
|---|---|---|
| `aws/config/AwsHttpClientWrapper.java` | Rewrite: `Mode` enum; `applyToSync`/`applyToAsync` + static null-tolerant forms; typed accessors; widened `ofSyncBuilder`; tightened `ofAsyncBuilder`; dead `try/catch` removed (D-10); `getTypedClient()` deprecated | 1.3 |
| `storage/factory/S3ClientFactory.java` | The `isBuilder` branch → one `applyToSync` call | 1.4.1 |
| `database/factory/DynamoRepositoryFactory.java` | `applyToSync` | 1.4.2 |
| `messaging/factory/MessagingClientFactory.java` | Two call sites → `applyToSync`; the second lifted out of a constructor argument | 1.4.3–4 |
| `notification/factory/NotificationClientFactory.java` | `applyToSync` | 1.4.5 |
| `storage/factory/TransferManagerFactory.java` | `applyToAsync`; `resolveAsyncHttpClient` deleted | 1.4.6 |
| `email/factory/EmailClientFactory.java` | Honour the configured HTTP client (was silently ignored) | 1.4.7 |
| `paramstore/factory/ParameterStoreClientFactory.java` | Honour the configured HTTP client (was silently ignored) | 1.4.7 |
| `storage/config/AwsStorageConfig.java` | `get*HttpClientForTesting()` → explicit `IllegalStateException` in builder mode instead of a bare CCE | 1.4.8 |
| `messaging/aws/impl/SqsMessagingClient.java` | `implements MessagingClient` unchanged; **correct the `close()` Javadoc** — it claims to close connection pools and does not | 4.1 |
| `aws/config/AwsHttpDefaults.java` | **New.** Single home for tuned transports; `Duration` constants so units are compile-checked | 1.7 P1 |
| `aws/config/AwsHttpClientWrapper.java` (defaults) | `defaultSyncClient()` / `defaultAsyncClient()` delegate to `AwsHttpDefaults` — **fixes the async units bug and makes the tuning reachable** | 1.7 P2 |
| `aws/config/BaseAwsConfig.java` | Constructor takes its fallback from a new overridable `BaseAwsConfigBuilder.defaultHttpClient(boolean)`; non-null guarantee preserved | 1.7 P3 |
| `database/config/DynamoDbClientConfig.java` | `Builder` overrides `defaultHttpClient(...)` → the 100-connection pool it always intended | 1.7 P3 |
| `S3ClientFactory` / `MessagingClientFactory` / `NotificationClientFactory` / `DynamoRepositoryFactory` (`createHttpClient`) | Collapse to one `AwsHttpDefaults` call each; **S3's copy is the one carrying the 83-min / 6.9-day units bug**; duplicated `DEFAULT_*` constants deprecated | 1.7 P4 |
| `storage/util/StorageConfigConstants.java` | `int …_MILLIS` constants deprecated in favour of `AwsHttpDefaults`' `Duration` constants | 1.7 P1 |

### `cloud-sdk-api`

| File | Change | § |
|---|---|---|
| `config/CloudResource.java` | **New.** `default void close() {}`; deliberately **not** `AutoCloseable` | 4.5 P1 |
| `config/ManagedCloudResource.java` | **New.** Dropwizard `Managed` adapter with a shutdown-safe `catch` | 4.5 P2 |
| `messaging/api/MessagingClient.java` | `extends AutoCloseable` + abstract `close()` → `extends CloudResource`; drop the abstract declaration | 4.5 P1 |
| `storage/api/StorageClient.java`, `notification/api/NotificationService.java`, `email/api/EmailService.java` | `extends CloudResource` — additive; no implementor changes required | 4.5 P1 |

`CloudHttpClient` is **not** touched — it stays provider-neutral (§1.2).

### Tests

| File | Change |
|---|---|
| `AwsHttpClientWrapperTest` | Fix the `ofAsyncBuilder` declaration; replace the dead-code CCE test with an `IllegalStateException` message assertion; add `applyToSync`/`applyToAsync` coverage (§1.6) |
| `AllFactoriesBuilderModeTest` | **New** — parameterised guard asserting every factory accepts a builder-mode wrapper (§1.6) |
| `CloudResourceTest` / `ManagedCloudResourceTest` | **New** — default no-op; `stop()` swallows a throwing `close()` |
| `AwsHttpDefaultsTest` | **New** — the units regression guard: every default `Duration` is under a minute; DynamoDB gets 100 connections; an explicit wrapper still wins (§1.7) |
| `S3ClientFactoryBuilderModeTest` | Unchanged — assertions remain valid |
| `NotificationClientConfigTest:205`, `AwsCloudParameterStoreConfigTest:116` | Unchanged — `getHttpClient()` is still non-null (§1.7 Part 3) |

## 5.3 The compatibility claim, checked line by line

> **Premise:** no `mercury-services` module needs a source change; recompiling against 1.0.31-SNAPSHOT is sufficient. Modules already upgraded keep their current Dropwizard `Managed` lifecycle without adopting `ManagedCloudResource`.

**Both halves hold — for source.** One qualification: with §1.7 included, 1.0.31 is *not* behaviour-identical. It carries two deliberate corrections (§1.7 Part 5). No module needs editing, but the AWS smoke suite should be run rather than waved through. Evidence:

### D-1 Option A

| Change | Effect on consumers |
|---|---|
| `applyToSync`/`applyToAsync` added | ✅ Purely additive |
| `Mode` enum replaces two booleans; `isAsync()`/`isBuilder()` kept as derived getters | ✅ `VisibilityApplicationInjectorTest.s3HttpClientWrapperIsBuilderBacked()` asserts `wrapper.isBuilder()` — still compiles, still true |
| `ofSyncBuilder(ApacheHttpClient.Builder)` → `ofSyncBuilder(SdkHttpClient.Builder<?>)` | ✅ Source-compatible — `VisibilityApplicationInjector:90` passes an `ApacheHttpClient.Builder`, which *is* an `SdkHttpClient.Builder<…>`. ⚠️ Binary-incompatible → **recompile required** (or add the §1.3 bridge overload) |
| `ofAsyncBuilder(Object)` → `ofAsyncBuilder(SdkAsyncHttpClient.Builder<?>)` | ✅ Zero call sites outside one commons test |
| `getTypedClient()` deprecated | ✅ Warnings only, and only inside `cloud-sdk-aws` — no `mercury-services` module calls it |
| `TransferManagerFactory` silent substitution → `IllegalStateException` | ✅ Unreachable for well-formed configs; `BaseAwsConfig.validateBaseConfig():112-114` already rejects a sync/async mismatch at build time |

### Units fix + reachable defaults (§1.7)

| Change | Effect on consumers |
|---|---|
| `AwsHttpDefaults` added; factories delegate to it | ✅ No source impact — all four `createHttpClient()` methods are `private static` |
| `BaseAwsConfigBuilder.defaultHttpClient(boolean)` hook | ✅ `protected` and additive; no consumer subclasses `BaseAwsConfigBuilder` |
| `getHttpClient()` non-null guarantee | ✅ **Preserved** — `NotificationClientConfigTest:205` and `AwsCloudParameterStoreConfigTest:116` still pass. `CloudStorageConfig.getHttpClient()` semantics unchanged |
| `StorageConfigConstants` `int …_MILLIS` deprecated | ⚠️ Warnings only; constants remain, and no `mercury-services` module references them |
| **Runtime: S3 default client** — 83 min → 5 s connect, 6.9 days → 10 s acquire | ⚠️ **Behaviour change.** Affects `booking` ×2, `bill-of-lading-v2`, `tx-tracking`. A correction of a defect; nobody can depend on the old values |
| **Runtime: DynamoDB pool** 50 → 100 connections | ⚠️ **Behaviour change.** Capacity increase, matches documented intent |
| **Runtime: connect timeout** 2 s → 5 s on DynamoDB / SQS / SNS / S3 | ⚠️ **Behaviour change.** More tolerant, not less |
| **Runtime: SES / SSM** | ⚠️ Now honour a configured HTTP client and use tuned defaults. Unchanged for callers relying on defaults, bar the 2 s → 5 s connect timeout |
| Explicitly configured transports (`visibility` S3 builder mode) | ✅ **Untouched** — a caller-supplied wrapper always wins |

### `AutoCloseable` → `CloudResource`

Verified by search across `booking`, `booking-bridge`, `bill-of-lading-v2`, `auth`, `visibility`, `tx-tracking` and all of `mercury-services-commons`:

```
implements MessagingClient        → cloud-sdk-aws/SqsMessagingClient only
new MessagingClient<...>() {      → none
try (… MessagingClient …)         → none      ← nothing relies on AutoCloseable
.close() on a MessagingClient     → VisibilityMessagingModule:65      (production)
                                    VisibilityMessagingModuleTest:91  verify(mock).close()
```

Exactly two call sites, both in `visibility`, both unaffected:

```java
// VisibilityMessagingModule:56-67 — UNCHANGED, still compiles, still works
environment.lifecycle().manage(new Managed() {
    @Override public void start() { }
    @Override public void stop() {
        messagingClient.close();      // inherited from CloudResource, overridden by
    }                                 // SqsMessagingClient — dispatches identically
});
```

* `close()` is still declared on `MessagingClient` (inherited from `CloudResource`), so the call compiles.
* `SqsMessagingClient` still overrides it, so virtual dispatch is unchanged — the same method body executes.
* The `default` body applies only to implementations that do **not** override; there are none.
* `verify(mockMessagingClient).close()` still works — Mockito mocks interface `default` methods.
* Nothing in any module uses try-with-resources or assigns a `MessagingClient` to an `AutoCloseable`, so dropping the supertype breaks no source.

> **So: visibility keeps its hand-rolled `Managed` verbatim.** Adopting `ManagedCloudResource` is a tidy-up it can take whenever convenient, not a condition of upgrading. The other four modules gain the *ability* to register lifecycle without being forced to.

### The one non-negotiable

**Every consumer must recompile against 1.0.31-SNAPSHOT.** The widened `ofSyncBuilder` descriptor and the removed `AutoCloseable` supertype are both binary-level changes. Dropping the new jar onto classes compiled against 1.0.30 without rebuilding is not supported. Since the fleet already rebuilds per version bump, this is a sequencing note rather than an obstacle.

### Net compatibility direction

**At the API level, 1.0.31 is strictly less breaking than 1.0.30** — it withdraws the `AbstractMethodError` exposure and the accidental try-with-resources hazard, and adds no new source break.

**At the runtime level it is not a no-op**, and that is intentional. The §1.7 corrections change effective timeouts and one pool size. Every delta moves in the safe direction (§1.7 Part 5), and the largest by far is removing a 6.9-day connection-acquisition timeout that is live in three services and a Lambda today. Smoke-test rather than assume.

## 5.4 Release-note text for 1.0.31-SNAPSHOT

```
## cloud-sdk 1.0.31-SNAPSHOT

Three changes, all in mercury-services-commons.
ACTION REQUIRED: recompile against 1.0.31-SNAPSHOT. No source changes needed in any module.
Change 3 corrects HTTP timeouts at runtime — run your AWS smoke suite, do not wave it through.

### 1. HTTP client configuration — builder mode now works everywhere (fixes D-1)

AwsHttpClientWrapper attaches itself to AWS client builders via applyToSync(...) /
applyToAsync(...). Builder mode (ofSyncBuilder / ofAsyncBuilder) is now honoured by EVERY
factory: S3, DynamoDB, SQS (both variants), SNS, SES, SSM and S3 Transfer Manager.

In 1.0.30, only S3ClientFactory read the isBuilder flag. Passing a builder-mode wrapper to
any other factory compiled cleanly and threw ClassCastException at client construction —
i.e. during Guice module setup, before the app could serve traffic. Only visibility used
builder mode, and only for S3, so no service was affected in practice.

  * ofSyncBuilder(...)   widened : ApacheHttpClient.Builder -> SdkHttpClient.Builder<?>
                                   (source-compatible; binary change -> recompile)
  * ofAsyncBuilder(...) tightened: Object -> SdkAsyncHttpClient.Builder<?>  (no call sites)
  * isAsync() / isBuilder()      : retained, now derived from a Mode enum
  * getTypedClient()             : @Deprecated(forRemoval = true). Use applyToSync /
                                   applyToAsync, or syncClient() / asyncClient() /
                                   syncClientBuilder() / asyncClientBuilder().
  * EmailClientFactory and ParameterStoreClientFactory previously IGNORED a configured HTTP
    client entirely; they now honour it. Effective behaviour is unchanged for callers using
    defaults.
  * TransferManagerFactory previously substituted a default CRT client when a sync wrapper
    was configured; it now throws IllegalStateException naming the actual mode. The path was
    already unreachable for well-formed configs (BaseAwsConfig rejects sync/async mismatch).

### 2. HTTP timeout units corrected, and tuned defaults now actually apply

*** THIS CHANGES RUNTIME BEHAVIOUR. READ THE TABLE. ***

Two related defects, neither introduced by ION-16431, both present since the constants were
written:

  (a) UNITS. S3ClientFactory.createHttpClient() and AwsHttpClientWrapper.defaultAsyncClient()
      applied Duration.ofSeconds / ofMinutes to constants named ..._MILLIS. Every S3 client
      from StorageClientFactory.createDefaultS3Client() has been running with an 83-MINUTE
      connect timeout and a 6.9-DAY connection-acquisition timeout. That is live today in
      booking (x2, including the S3ArchiveHandler Lambda), bill-of-lading-v2 and tx-tracking.
      A multi-day acquisition timeout means a thread parks in
      PoolingHttpClientConnectionManager.leaseConnection with no error, no timeout and no log
      line — effectively "block forever", and the hardest failure shape to diagnose.

  (b) UNREACHABLE TUNING. BaseAwsConfig filled in a bare, untuned transport whenever a caller
      did not supply one, so each factory's tuned createHttpClient() was dead code and every
      service silently ran on AWS SDK defaults.

Both are fixed by consolidating all transport construction into a new AwsHttpDefaults class
whose durations are declared as Duration constants — so a unit mismatch is now a compile
error, not a six-day hang.

Effective changes:

  path                                        before                     after
  ------------------------------------------  -------------------------  -----------------
  StorageClientFactory.createDefaultS3Client   connect 83 min             connect 5 s
    (booking x2, bill-of-lading-v2,            acquire 6.9 days           acquire 10 s
     tx-tracking)
  AwsHttpClientWrapper.defaultAsyncClient      connect 5 000 s            connect 5 s
    (no consumer reaches this today)           acquire 10 000 s           acquire 10 s
  DynamoDB via config, no explicit client      50 conns, connect 2 s      100 conns, connect 5 s
  SQS / SNS / S3 via config, no explicit       connect 2 s                connect 5 s
  SES / SSM                                    configured client IGNORED  honoured; tuned
  S3 via an explicit builder-mode wrapper      caller-supplied            UNCHANGED
    (visibility)

Every delta moves in the safe direction: two absurd timeouts collapse to sane ones, the
connect timeout becomes more tolerant rather than less, and DynamoDB's pool doubles to the
100 connections DynamoRepositoryFactory always intended. A caller-supplied transport always
wins — visibility's S3 tuning (1 s / 5 s / 50 connections) is untouched.

Also: DynamoDbClientConfig.maxConnections remains unread by anything (tracked separately).
StorageConfigConstants' int ..._MILLIS constants are deprecated in favour of the Duration
constants on AwsHttpDefaults.

### 3. Client lifecycle — CloudResource replaces AutoCloseable (WITHDRAWS a 1.0.30 break)

MessagingClient no longer extends AutoCloseable. MessagingClient, StorageClient,
NotificationService and EmailService now extend CloudResource, which declares
`default void close() {}`.

This is a REDUCTION in breakage relative to 1.0.30:

  * Source- AND binary-compatible for implementors. The AbstractMethodError exposure
    introduced in 1.0.30 is withdrawn.
  * try-with-resources no longer compiles on these clients. Deliberate: they are
    process-scoped singletons owned by the DI container, and closing one in a lexical block
    leaves every injected holder with a dead reference and no way to publish a replacement.
    The SpotBugs/Sonar OBL_UNSATISFIED_OBLIGATION wave from 1.0.30 also goes away.
  * Existing close() call sites are unaffected. Visibility's hand-rolled Managed in
    VisibilityMessagingModule keeps working verbatim; adopting the new adapter is optional.
  * NEW: ManagedCloudResource.of(resource, name) adapts any CloudResource to a Dropwizard
    Managed, with a shutdown-safe catch so one failing stop() cannot abort the rest of the
    shutdown sequence.
  * CORRECTED JAVADOC on SqsMessagingClient.close(). It previously claimed to close "the
    underlying SqsClient and its connection pools". It does not close the pool: clients are
    built with httpClient(instance), so the SDK wraps the transport in
    NonManagedSdkHttpClient, whose close() is a no-op. close() does release the SDK's
    executors, metric publishers and credentials provider. Only builder mode makes the SDK
    the transport owner — which change 1 above now makes available to every factory.
  * close() is TERMINAL. A closed client cannot be reopened and cannot be replaced through
    Guice. Call it only at application shutdown. Pool-death self-healing is separate work.
```

## 5.5 Suggested sequencing

1. **Branch from the 1.0.30 commit** (`1e2fcd6`).
2. **Commit 1 — units fix.** `AwsHttpDefaults` + the four factory `createHttpClient()` delegations + `defaultSyncClient()`/`defaultAsyncClient()`. **Land this first and independently** — it is the only change in the release that fixes something live and reached, and it should be revertible on its own.
3. **Commit 2 — reachable defaults.** `BaseAwsConfigBuilder.defaultHttpClient(boolean)` hook + the `DynamoDbClientConfig.Builder` override. Depends on commit 1.
4. **Commit 3 — D-1 Option A.** `AwsHttpClientWrapper` rewrite + the eight factory/config edits. These do not compile independently, so they land together. Includes the D-10 dead-catch removal.
5. **Commit 4 — lifecycle.** `CloudResource`, `ManagedCloudResource`, the four interface changes, the `SqsMessagingClient` Javadoc correction.
6. **Commit 5 — tests.** `AwsHttpDefaultsTest` and `AllFactoriesBuilderModeTest` are the two regression guards; do not skip either.
7. **Bump to `1.0.31-SNAPSHOT`**, add the §5.4 release note to `README.md`.
8. **Publish**, then one PR per consumer bumping `mercury.commons.version`. Order by exposure to the §1.7 runtime change: `tx-tracking` → `bill-of-lading-v2` → `booking` (all three run on the 6.9-day-timeout S3 client) → `visibility` → `booking-bridge` → `auth`.
9. **Per app: recompile and run the AWS smoke suite.** Two things to verify: (a) **application startup** — D-1 fails at client construction, so a clean boot is the signal; (b) **S3 and DynamoDB round-trips** — §1.7 changes effective timeouts and one pool size.
10. **`booking`'s `S3ArchiveHandler` Lambda needs its own check.** It builds an S3 client through the same defaulted path, so it picks up the timeout correction, and Lambda deployments do not follow the service release train.

---

# 6. Deferred — not in 1.0.31

Recorded so nothing is lost. None of these is a prerequisite for §5, and each would either break the "behaviour-preserving, recompile-only" premise or belongs in a different repository.

## 6.1 `mercury-services-commons` — deferred

| Item | § | Why deferred |
|---|---|---|
| **D-5** — retry `Crc32MismatchException`: new `AwsRetryStrategies` helper, four `createOverrideConfig` edits, an explicit `aws-core` dependency | §2 | Genuine behaviour change — calls that previously failed hard now retry. Wants its own release and smoke test. Note the mutual-exclusion trap in §2.3 before implementing. |
| **`DynamoDbClientConfig.maxConnections`** — the field (default 100, `:70`) has no reader anywhere in `src/main` | §1.7 P3 | Honouring it means building the transport from config rather than a constant — a larger change with its own compatibility questions. §1.7 gives DynamoDB its 100-connection pool via a constant in the meantime. |
| **D-2 remainder** — `findAll()` at `EnhancedDynamoRepository:521` still does `table.scan().items().stream().toList()` | source doc §5.3 | Guarded by `isFindAllUnpaginatedScanEnabled`, default off. `export()` was already capped in 1.0.30. |
| **D-3** — `query()` returns a bare `List<T>`: no `lastEvaluatedKey`, no "more available" signal | source doc §5.3 | New API surface; additive but wants design. |
| **§3.4** — `S3StorageClient` write path throws bare `RuntimeException` where ~20 sibling sites throw `S3OperationException`; `e.awsErrorDetails().errorMessage()` on L712 can NPE while logging an S3 error | §3.4 | Exception-type change; needs a caller audit. |
| **Client rebuild on pool death** — stable façade holding a `volatile SqsClient` | §4.2 | A distinct capability from lifecycle. Do not conflate. |
| **japicmp / revapi in CI** | source doc §9.3 G-6 | Would have caught both 1.0.30 breaks automatically. Strongly recommended, independent of any release. |

## 6.2 `mercury-services` — deferred (different repository)

| Item | § | Note |
|---|---|---|
| **D-4** — `VisibilityApplicationInjector` Javadoc states the inverse of SDK v2 ownership semantics and credits builder mode with protection it does not provide | §1.5.3 | Documentation only. Replacement text supplied. |
| **D-9** — `VisibilityDynamoModule` comment cites `ProvisionedThroughputExceededException` / RCU exhaustion; **zero occurrences** in the incident logs | source doc §5.5.4 | Documentation only. |
| **D-1 test comment** — `VisibilityApplicationInjectorTest:68-70` calls the `ClassCastException` "by design" | §1.5.4 | Becomes `IllegalStateException` after 1.0.31; the comment should follow. |
| **Optional adoption** — `ManagedCloudResource` in the five messaging modules; builder mode for DynamoDB/SQS | §4.5 P3, §1.5.2 | Purely opt-in. Nothing forces it. |
| **B-1** — SQS circuit breaker creates a silent zombie service | source doc §5.4.1 | 🔴 Blocking. |
| **B-2** — 5000→1000 makes backlog drain 5× slower | source doc §5.5.2 | 🔴 Blocking. |
| **B-3** — trim guard can empty the page → permanent silent cursor stall | source doc §5.5.3 | 🔴 Blocking. |
| **D-6, D-7, D-8, D-12** | source doc §6 | D-8 (lazy `@Provides` + `lifecycle().manage()`) closes for free via eager binding if a module adopts §4.5 Part 3. |

---

# 7. Announcement — 1.0.30-SNAPSHOT release preamble

Copy-ready. Names the two latent breaks, what they falsely promise, and points at 1.0.31.

---

## 📦 cloud-sdk `1.0.30-SNAPSHOT` is published — please read before adopting

**TL;DR — 1.0.30 is safe to build against, but it carries two known API defects introduced by the ION-16431 hardening work. Neither affects a running service today. Both are fixed compatibly in `1.0.31-SNAPSHOT`, which is the version we recommend you upgrade to. If you have not started your bump yet, wait for 1.0.31.**

### What is in 1.0.30

| Change | PR | Status |
|---|---|---|
| Rebase onto `develop` — Jetty / logback OWASP hardening (ION-16376, ION-15990) | — | ✅ |
| **`QuerySpec.maxResultSize`** — caps DynamoDB `query()` results and stops auto-pagination | **#48** | ✅ **The fix for the visibility outbound outage** |
| `export()` result cap in `EnhancedDynamoRepository` | **#48** ff | ✅ |
| `S3StorageClient` write-path log/exception message correction | **#48** ff | ✅ |
| Dedicated HTTP clients — `AwsHttpClientWrapper` builder mode, `MessagingClient.close()` | **#46** | ⚠️ **See below** |
| Version bump to 1.0.30-SNAPSHOT | **#47** | ✅ |

**PR #48 is the important one.** ION-16431 (visibility outbound stall, ~5 days, ~65 M error records) was caused by the AWS SDK v1 → v2 migration silently turning a bounded single-page DynamoDB read into an unbounded full-result-set read. `maxResultSize` closes that. If you have a DAO that passes a "result size limit" to `QuerySpec.limit()` believing it caps the total, **you are carrying the same latent OOM** — `limit` is per *page*. Audit with `grep -n "\.limit(" ` on your `DefaultQuerySpec.builder()` call sites and add `.maxResultSize(...)`.

### ⚠️ Two known API defects in 1.0.30, both from PR #46

Both are **latent** — no running service is affected, because only `visibility` uses either feature and it uses them in the one configuration that happens to work. They matter because the API *invites* you into the broken paths.

#### 1. HTTP-client "builder mode" only works with S3

**What it promises.** `AwsHttpClientWrapper.ofSyncBuilder(...)` looks like a general way to hand any AWS service client a tuned HTTP transport and let the SDK own its lifecycle.

**What it does.** Only `S3ClientFactory` reads the `isBuilder` flag. Every other factory — DynamoDB, SQS (both variants), SNS, SES, SSM, S3 Transfer Manager — passes the wrapper's contents straight into `.httpClient(...)`, which expects a *built client*, not a *builder*.

**How it fails.** It compiles cleanly. `getTypedClient()` is an unchecked generic cast, so the compiler infers whatever the call site wants and inserts the real cast there. At runtime you get:

```
java.lang.ClassCastException: class ...ApacheHttpClient$DefaultBuilder
    cannot be cast to class ...SdkHttpClient
        at ...DynamoRepositoryFactory.createDynamoDbClient(...)
```

thrown **during Guice module construction** — the application fails to start, with a stack trace naming an AWS SDK class you never mentioned and nothing pointing at the config that caused it.

**Also in this defect:** `EmailClientFactory` (SES) and `ParameterStoreClientFactory` (SSM) silently discard a configured HTTP client entirely — no error, no warning, your tuning is simply ignored.

> **Until 1.0.31: use `AwsHttpClientWrapper.ofSync(...)` / `ofAsync(...)` with a pre-built client. Do not use `ofSyncBuilder` / `ofAsyncBuilder` for anything except S3.**

#### 2. `MessagingClient extends AutoCloseable` — breaking, and its `close()` does not do what it says

**What it promises.** The Javadoc on `SqsMessagingClient.close()`: *"closes the underlying SqsClient **and its connection pools**."*

**What it does.** It does **not** close the connection pool. `MessagingClientFactory` builds every SQS client with `.httpClient(<pre-built instance>)`, and the AWS SDK wraps a pre-built transport in `NonManagedSdkHttpClient` — whose `close()` is a literal no-op (`0: return`). The SDK deliberately never closes a transport you hand it. `close()` does release the SDK's internal executors, metric publishers and credentials provider — but not the sockets it names. Only *builder mode* would close the pool, and builder mode is defect #1.

**Why it is breaking, in two ways:**

* **`AbstractMethodError`.** Adding an abstract `close()` to a published interface means any class implementing `MessagingClient<T>` and compiled against ≤1.0.29 will load fine, then throw `AbstractMethodError` the first time `close()` is called — at *shutdown*, where it is least likely to be noticed. We verified there are no such implementors in `mercury-services` or `mercury-services-commons`; if you maintain one in another repository, this hits you.
* **try-with-resources becomes legal on a shared singleton.** This did not compile against 1.0.29. It does now, and it will break your app:

  ```java
  try (MessagingClient<String> c = MessagingClientFactory.createDefaultStringClient()) {
      c.sendMessage(queueUrl, body);
  }   // ← closes a Guice @Singleton that other components still hold
  ```

  These clients are process-scoped singletons injected **by reference**. Close one and every holder keeps a dead reference; there is no provider or proxy through which a replacement could be published. **A closed client is unrecoverable for the life of the JVM.**

  Inheriting `AutoCloseable` also switches on SpotBugs / Sonar `OBL_UNSATISFIED_OBLIGATION` and IDE "resource leak" inspections at every `MessagingClientFactory.create*` call site — all false positives for a DI-managed singleton.

> **Until 1.0.31: never use try-with-resources on a `MessagingClient`. Call `close()` only from a Dropwizard `Managed.stop()` hook. Do not implement `MessagingClient` yourself.**

### What 1.0.31-SNAPSHOT fixes, and why upgrading is cheap

| | 1.0.30 | 1.0.31 |
|---|---|---|
| Builder mode | S3 only; `ClassCastException` elsewhere | Honoured by **every** factory |
| SES / SSM HTTP client | Silently ignored | Honoured |
| **S3 default client connect timeout** | **83 minutes** | **5 seconds** |
| **S3 default client connection-acquisition timeout** | **6.9 days** | **10 seconds** |
| DynamoDB pool (no explicit client) | 50 connections | 100 — the documented intent |
| `MessagingClient` supertype | `AutoCloseable` — `AbstractMethodError` risk, try-with-resources legal | `CloudResource` with a `default` no-op `close()` — **source- and binary-compatible**, try-with-resources no longer compiles |
| `SqsMessagingClient.close()` Javadoc | Claims to close connection pools | Corrected; states exactly what is and is not released |
| Dropwizard lifecycle | Hand-rolled anonymous `Managed` per module | `ManagedCloudResource.of(client, name)` — optional, with a shutdown-safe `catch` |

### 🔴 A third defect, older than ION-16431 — and this one is live in production now

Found during the same review. **Not** introduced by PR #46, and not latent:

`S3ClientFactory.createHttpClient()` applies `Duration.ofSeconds` and `Duration.ofMinutes` to constants named `…_MILLIS`. Every S3 client built by `StorageClientFactory.createDefaultS3Client()` therefore runs with an **83-minute TCP connect timeout** and a **6.9-day connection-acquisition timeout**. Four production call sites are on it today:

```
booking/config/BookingMessagingModule.java:81
booking/lambda/S3ArchiveHandler.java:99          ← Lambda
bill-of-lading-v2/config/BillOfLadingInjector.java:84
tx-tracking/config/TxTrackingModule.java:77
```

If S3 blackholes, a thread blocks for up to 83 minutes instead of 5 seconds. If all 50 pooled connections are busy, a thread parks in `PoolingHttpClientConnectionManager.leaseConnection` for up to 6.9 days — no error, no timeout, no log line. Functionally "block forever", and the hardest failure shape there is to diagnose. In the Lambda it means burning the full billed duration on a hung connect.

`AwsHttpClientWrapper.defaultAsyncClient()` has the same bug (5 000 s connect, 10 000 s acquire), but nothing reaches it — there is no `TransferManager` or async-storage usage anywhere.

**1.0.31 fixes both**, by consolidating all transport construction into one `AwsHttpDefaults` class whose durations are `Duration` constants — so a unit mismatch becomes a compile error rather than a six-day hang. It also makes each factory's tuned defaults actually apply, which they never have: `BaseAwsConfig` was filling in a bare untuned transport, so every service has been running on AWS SDK defaults.

**This is the strongest reason to take 1.0.31.**

### Upgrade cost: recompile, plus a smoke test

* No source change is required in any `mercury-services` module, including `visibility`.
* `visibility`'s existing `ofSyncBuilder(ApacheHttpClient.builder()...)` call compiles unchanged.
* `visibility`'s hand-rolled `Managed` calling `messagingClient.close()` keeps working verbatim — adopting `ManagedCloudResource` is optional tidy-up, not a condition of upgrading.
* Modules that do no lifecycle management at all need no edits.
* **At the API level, 1.0.31 is strictly less breaking than 1.0.30** — it withdraws 1.0.30's `AbstractMethodError` exposure rather than adding anything new.

A rebuild is mandatory: the widened `ofSyncBuilder` signature and the removed `AutoCloseable` supertype are both binary-level changes. Do not drop the 1.0.31 jar onto classes compiled against 1.0.30.

**Run your AWS smoke suite rather than waving the bump through.** 1.0.31 is not a runtime no-op: effective HTTP timeouts change (all in the safe direction — see the table above) and DynamoDB's default pool doubles to 100. Verify (a) the app starts cleanly and (b) S3 and DynamoDB round-trips work. If you own a Lambda that builds a cloud-sdk client, redeploy it too — Lambdas do not follow the service release train.

### Recommendation

| You are… | Do this |
|---|---|
| Not yet started on the bump | **Wait for 1.0.31-SNAPSHOT.** Skip 1.0.30. |
| Already on 1.0.30 | Move to 1.0.31 when it lands — particularly if you use S3 via `StorageClientFactory.createDefaultS3Client()`. Meanwhile: avoid `ofSyncBuilder` outside S3, and never try-with-resources a `MessagingClient`. |
| Blocked and need `maxResultSize` now | Take 1.0.30, observe the two "until 1.0.31" guards above, then bump. |
| Running `booking`, `bill-of-lading-v2` or `tx-tracking` | You are on the 83-minute / 6.9-day S3 timeouts today. Prioritise the 1.0.31 bump. |
| Maintaining a `MessagingClient` implementation outside these two repos | **Contact us before adopting 1.0.30** — you will need a `close()` method. 1.0.31 removes that requirement. |

### Follow-up after 1.0.31

Also found during this review, **not** caused by ION-16431 and **not** in 1.0.31:

* `Crc32MismatchException` is never retried on any AWS SDK v2 client — it reports `retryable() == true`, but the SDK's default predicate only reads that flag on `SdkServiceException`, and this is an `SdkClientException`. 32 hard failures during the ION-16431 window that should have been transparent retries. Deferred because it changes failure behaviour and deserves its own release.
* `EnhancedDynamoRepository.findAll()` still auto-paginates an entire table scan — the same defect class as the one that caused ION-16431. Guarded by `isFindAllUnpaginatedScanEnabled`, default off, so it is a trap rather than a live fault.
* `japicmp` or `revapi` in CI. Both 1.0.30 API breaks would have been caught automatically.

Full technical analysis, including bytecode-level verification of every claim: `cloud-sdk-api/docs/2026-08-14-cloud-sdk-defect-refactor.md`.
