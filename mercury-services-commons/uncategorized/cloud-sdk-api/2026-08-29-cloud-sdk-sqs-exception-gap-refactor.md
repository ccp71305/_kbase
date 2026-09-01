# cloud-sdk 1.0.33 — SQS Delay Gap & Cloud Exception Model: Implementation Record

| Field | Value |
|---|---|
| Document date | 2026-08-29 |
| Repository | `mercury-services-commons` |
| Branch | `feature/ION-12310-commons-cloudsdk-refactoring` |
| Base commit | `ea154df` (1.0.32-SNAPSHOT) |
| Commits | `ee17374` (Section A — S1), `f151367` (Section B — E1–E6), `9dd413c` (version/README). Rewritten 2026-08-31: messages shortened, review comment edits folded in, `cloud-sdk-aws/pom.xml` revert folded into `f151367`. |
| Version | `1.0.32-SNAPSHOT` → `1.0.33-SNAPSHOT` |
| Implements | [`2026-08-29-sqs-gaps-design.md`](./2026-08-29-sqs-gaps-design.md) |
| Verification | `mvn verify` on `cloud-sdk-api`, `cloud-sdk-aws`, `commons`, `dynamo-integration-test` after **each** commit; `mvn install` across the full reactor |
| Status | Implemented, verified, **not pushed** — pending review |

---

## 1. What was built, in one page

Two independent gaps kept consumers of `cloud-sdk` coupled to raw AWS SDK v2 types. Both are now
closed, additively.

**Gap 1 — no send-time delay (S1).** `MessagingClient` exposed `sendMessage(String, T)` and
`sendMessage(String, T, Map)`. Neither could set the SQS `DelaySeconds` request parameter, so any
consumer implementing exponential-backoff redelivery had to inject a raw
`software.amazon.awssdk.services.sqs.SqsClient` purely to build a `SendMessageRequest` with
`.delaySeconds(...)`. This was the *last* remaining capability forcing the raw client
(`changeMessageVisibility` was closed in 1.0.32), and it is independently reproduced in two places by
two different teams — `aw-bridge-shared.SQSClient` and `partner-integrator/pi-commons.SQSClient` —
which is the strongest available evidence that it is a genuine platform gap rather than one team's
quirk.

**Gap 2 — the exception contract carried no retry signal (E1–E6).** `SqsMessagingClient` wrapped
everything in a flat `MessagingException`: a socket timeout, a throttle, a non-existent queue and a
`NullPointerException` from a broken message converter all arrived as the same type with the same
(absent) retry semantics. A caller wanting "retry on transient failure" could only write
`catch (RuntimeException)`, which also swallows genuine bugs and retries them forever — and
`watermill-publisher` does exactly that today. On the SNS side there was no abstraction at all:
`SnsExceptionHandler` returned a bare `RuntimeException`, and `SnsService` caught only `SnsException`,
so every `SdkClientException` (network, timeout, retry exhaustion) escaped completely unwrapped as an
AWS type — because `SdkClientException` is **not** an `SnsException`; the hierarchy branches at
`SdkException`.

The shape of the fix:

```
                       cloud-sdk-api  (no AWS types — P5)
                       ┌─────────────────────────────────────────────┐
                       │  CloudSdkException                          │
                       │    isRetryable() / getOperation()           │
                       │    getResource()                            │
                       │      ├── MessagingException    (re-parented)│
                       │      └── NotificationException (new)        │
                       │                                             │
                       │  SendMessageOptions  (new)                  │
                       │    delaySeconds 0..900, attributes          │
                       │                                             │
                       │  MessagingClient                            │
                       │    + default sendMessage(url, body, opts)   │
                       │    + default sendMessage(url, body, int)    │
                       └───────────────────┬─────────────────────────┘
                                           │
                       cloud-sdk-aws       │ (AWS types confined here)
                       ┌───────────────────┴─────────────────────────┐
                       │  AwsFailureClassifier  (new)                │
                       │    Throwable -> boolean, one tested place   │
                       │       ▲                    ▲                │
                       │       │                    │                │
                       │  SqsMessagingClient   SnsExceptionHandler   │
                       │   handleException()    handle(op, res, t)   │
                       │   + options send       SnsService (6 sites) │
                       │   + receiveMessages wrap (E5)               │
                       └─────────────────────────────────────────────┘
```

---

## 2. Files changed

### 2.1 New files (7)

| File | Module | Lines | Purpose |
|---|---|---:|---|
| `.../cloudsdk/messaging/model/SendMessageOptions.java` | cloud-sdk-api | 131 | Send-time options (delay + attributes). The S1 fix. |
| `.../cloudsdk/exception/CloudSdkException.java` | cloud-sdk-api | 109 | Common unchecked base with `isRetryable()`. The E1/E2 fix. |
| `.../cloudsdk/notification/exception/NotificationException.java` | cloud-sdk-api | 57 | SNS abstraction type. The E3 fix. |
| `.../cloudsdk/exception/AwsFailureClassifier.java` | cloud-sdk-aws | 88 | AWS v2 → retryable translation, in one tested place. |
| `.../cloudsdk/messaging/model/SendMessageOptionsTest.java` | cloud-sdk-api | 289 | 38 cases, 5 nested groups. |
| `.../cloudsdk/exception/CloudSdkExceptionHierarchyTest.java` | cloud-sdk-api | 187 | Re-parenting compatibility guards. |
| `.../cloudsdk/exception/AwsFailureClassifierTest.java` | cloud-sdk-aws | 348 | 49 cases, 6 nested groups. |
| `.../cloudsdk/notification/exception/SnsExceptionHandlerTest.java` | cloud-sdk-aws | 188 | Descriptor + legacy-format guards. |

### 2.2 Changed files (10)

| File | Module | Δ | Change |
|---|---|---:|---|
| `pom.xml` (root) | — | 1 | `dependency.version` `1.0.32-SNAPSHOT` → `1.0.33-SNAPSHOT` |
| `README.md` | — | +146 | New `v1.0.33-SNAPSHOT` section, incl. a behavioural-change table |
| `.../messaging/api/MessagingClient.java` | cloud-sdk-api | +54/−1 | +2 `default` methods |
| `.../messaging/exception/MessagingException.java` | cloud-sdk-api | +47/−17 | Re-parented; +1 classifying constructor |
| `.../messaging/aws/impl/SqsMessagingClient.java` | cloud-sdk-aws | +157/−58 | Send delegation; classification; E5 wrap |
| `.../notification/exception/SnsExceptionHandler.java` | cloud-sdk-aws | +63/−12 | Returns `NotificationException`; +`handle(...)` |
| `.../notification/impl/SnsService.java` | cloud-sdk-aws | +51/−24 | 6 catches widened (E4); javadoc corrected (E6) |
| `.../messaging/api/MessagingClientDefaultsTest.java` | cloud-sdk-api | +218/−28 | Hand-written legacy/modern implementors (P2/P3 guard) |
| `.../messaging/aws/impl/SqsMessagingClientTest.java` | cloud-sdk-aws | +442 | 5 new nested classes |
| `.../notification/impl/SnsServiceTest.java` | cloud-sdk-aws | +166/−8 | New `ExceptionHandlingTests`; 2 assertions updated for E4 |

**Totals across both code commits:** 16 files, **+2,483 / −112** (`cloud-sdk-aws/pom.xml` reverted — see §3.2).
Full diff: `git diff ea154df..HEAD`.

---

## 3. Implementation, section by section

### 3.1 Section A — the `DelaySeconds` gap (commit `ee17374`)

**Why an options object and not two more overloads.** The naïve fix — `sendMessage(String, T, int)`
and `sendMessage(String, T, Map, int)` — does not scale: FIFO support would add two more `String`
parameters and produce a six-argument method that is unreadable at the call site and impossible to
extend again. `ReceiveMessageOptions` already established the house answer to exactly this problem on
the receive side. Every future send-time parameter is now a new builder field, which is source- and
binary-compatible and never requires a new interface method.

**Why the `default` throws instead of degrading.** A default that quietly forwards to the no-delay
send would compile everywhere and be catastrophic in exactly one place: the only production consumer
of the delay is an exponential-backoff retry path. Drop the delay and a message that failed is
redelivered immediately, fails again, and is redelivered again — a hot loop against the failing
downstream, with SQS receive charges and log volume scaling with it. That failure mode is silent and
expensive. `UnsupportedOperationException` fails loudly on the first call, in the consumer's own
tests. Same reasoning `changeMessageVisibility` used in 1.0.32.

**Overload-resolution safety.** The one place an additive overload could bite is ambiguity with the
existing `Map` overload. It cannot, because the new parameter is a **primitive** `int`: neither a
`Map` nor `null` is convertible to it, so `sendMessage(url, body, null)` still resolves to the `Map`
overload unambiguously. Verified by sweep that no in-scope module declares a conflicting
`sendMessage(..., int)` on a `MessagingClient` implementor — indeed **no module implements
`MessagingClient` at all** (§5.2).

```java
// MessagingClient — the two additions (javadoc elided)
default void sendMessage(String queueUrl, T messageBody, SendMessageOptions options) {
    throw new UnsupportedOperationException(
        "sendMessage(String, T, SendMessageOptions) is not supported by this MessagingClient implementation");
}

default void sendMessage(String queueUrl, T messageBody, int delaySeconds) {
    sendMessage(queueUrl, messageBody,
        SendMessageOptions.builder().delaySeconds(delaySeconds).build());
}
```

**The delegation refactor.** `SqsMessagingClient` had two independent request-building sites with
duplicated exception handling. It now has one:

```java
 @Override
 public void sendMessage(String queueUrl, T messageBody) {
-    log.debug(...);
-    try {
-        SendMessageRequest request = SendMessageRequest.builder()
-            .queueUrl(queueUrl)
-            .messageBody(messageConverter.toString(messageBody))
-            .build();
-        SendMessageResponse response = sqsClient.sendMessage(request);
-        log.debug("Message sent successfully. MessageId: {}", response.messageId());
-    } catch (Exception e) {
-        throw handleException("sendMessage", queueUrl, e);
-    }
+    log.debug(...);
+    sendMessage(queueUrl, messageBody, SendMessageOptions.builder().build());
 }

 @Override
 public void sendMessage(String queueUrl, T messageBody, Map<String, String> attributes) {
-    try {
-        Map<String, MessageAttributeValue> messageAttributes = attributes.entrySet().stream()
-            .collect(Collectors.toMap(...));
-        SendMessageRequest request = SendMessageRequest.builder()
-            .queueUrl(queueUrl)
-            .messageBody(messageConverter.toString(messageBody))
-            .messageAttributes(messageAttributes)
-            .build();
-        sqsClient.sendMessage(request);
-    } catch (Exception e) {
-        throw handleException("sendMessage", queueUrl, e);
-    }
+    sendMessage(queueUrl, messageBody, SendMessageOptions.builder().attributes(attributes).build());
 }

+@Override
+public void sendMessage(String queueUrl, T messageBody, SendMessageOptions options) {
+    try {
+        SendMessageRequest.Builder requestBuilder = SendMessageRequest.builder()
+            .queueUrl(queueUrl)
+            .messageBody(messageConverter.toString(messageBody));
+
+        if (options.getDelaySeconds() > 0) {
+            requestBuilder.delaySeconds(options.getDelaySeconds());
+        }
+        if (!options.getAttributes().isEmpty()) {
+            requestBuilder.messageAttributes(toMessageAttributes(options.getAttributes()));
+        }
+
+        SendMessageResponse response = sqsClient.sendMessage(requestBuilder.build());
+        log.debug("Message sent successfully to queue {}. MessageId: {}", queueUrl,
+            response == null ? null : response.messageId());
+    } catch (Exception e) {
+        throw handleException("sendMessage", queueUrl, e);
+    }
+}
```

#### Two deviations from the design document, both deliberate

**(a) `DelaySeconds` is set only when `> 0`.** Design §5 sets it unconditionally. That is wrong twice
over. It breaks the existing exact-equality assertion in
`SqsMessagingClientTest.shouldSendMessageWithAttributesSuccessfully`, which is a *symptom*; the
*cause* is a real wire-semantic change. In SQS, an **omitted** `DelaySeconds` means "apply the
queue's own `DelaySeconds` attribute", while an **explicit 0** overrides that queue default to "no
delay". Sending `0` unconditionally would therefore silently suppress queue-level delay configuration
for every existing caller. Accepted trade-off: a caller cannot force an explicit `0` over a queue
default. No consumer needs that today, and it can be added later as an explicit builder flag without
breaking anything.

**(b) The response is dereferenced null-safely.** This was caught *by the existing test suite*, which
is the delegation refactor working as intended. `shouldSendMessageWithAttributesSuccessfully` never
stubbed a `SendMessageResponse`, because the old three-argument path ignored the return value.
Unifying the paths made the shared site read `response.messageId()` for a debug log, which NPE'd on
the unstubbed mock. **Fixed in production code, not by editing the test** — the whole point of the
refactor is that legacy paths keep behaving identically, and a logging concern must never be able to
fail a successful send.

#### One minor behaviour change

`sendMessage(url, body, (Map) null)` previously threw a `MessagingException` wrapping an NPE
(`attributes.entrySet()` on null). It is now normalised to "no attributes", following the options
builder's null tolerance. Covered by a named test.

---

### 3.2 Section B — the exception model (commit `f151367`)

**Why re-parenting `MessagingException` is safe.** This is the only change in the release touching an
existing type's declaration, so it is asserted in code rather than argued.

- *Source compatibility.* `CloudSdkException extends RuntimeException`, so `MessagingException`
  IS-A `RuntimeException` exactly as before. Every existing `catch`, `instanceof`, `throws` clause,
  and multi-catch such as `partner-integrator`'s `catch (MessagingException | SdkException ex)`
  compiles and behaves identically — the last one specifically because the cloud-sdk and AWS
  hierarchies remain disjoint.
- *Binary compatibility.* **JLS §13.4.4**: changing a direct superclass does not break pre-existing
  binaries provided the total set of superclasses loses no members. Here the set grows from
  `{RuntimeException, Exception, Throwable, Object}` to a strict superset. Already-compiled consumers
  — including shaded fat JARs that will never be rebuilt — keep working.

Both original constructors are retained verbatim. They carry a javadoc `@deprecated` tag but
deliberately **no `@Deprecated` annotation**: the annotation would emit warnings in every consumer
build for a call that is not actually wrong (they remain correct for hand-constructed failures with no
cause).

**The classifier.** The previous `handleException` computed a classification for the error *message*
and then discarded it — the information needed to answer "should I retry this?" was derived and
thrown away. `AwsFailureClassifier` is the single place that translation now lives:

```java
public static boolean isRetryable(Throwable t) {
    if (t == null) {
        return false;
    }
    // Poison payload. MUST precede the IOException arm:
    // JsonProcessingException extends JacksonException extends IOException.
    if (t instanceof JacksonException) {
        return false;
    }
    if (t instanceof SdkClientException) {                 // reset, timeout, retry exhaustion, DNS
        return true;
    }
    if (t instanceof SdkServiceException sse) {
        return sse.isRetryableException()
            || sse.isThrottlingException()
            || sse.isClockSkewException()
            || sse.statusCode() >= 500;
    }
    if (t instanceof SdkException sdke) {
        return sdke.retryable();
    }
    if (t instanceof IOException) {                        // genuine socket IO the SDK did not wrap
        return true;
    }
    return false;                                          // NPE, converter bugs, interruption
}
```

Three things about this are load-bearing and easy to get wrong later:

1. **Arm order.** `SdkClientException extends SdkException`, and
   `AwsServiceException extends SdkServiceException extends SdkException`. Reordering silently
   degrades every classification to `SdkException.retryable()` — which is `false` — turning every
   network failure into "do not retry". There is a named test for this
   (`isClassifiedByItsOwnArmNotBySdkExceptionRetryable`).
2. **The Jackson guard precedes the `IOException` arm.** This is the reviewer decision recorded in
   design §17.4(1): adopt `visibility`'s ordering guard rather than the doc's simpler proposal of
   deleting the `IOException` arm entirely. Both are safe — neither produces a retry storm — but the
   ordering guard is strictly more capable: it still retries a genuine socket `IOException` the SDK
   did not wrap, instead of sacrificing that case to avoid the Jackson subclass. It also means the
   platform classifier and `visibility`'s existing `RetryClassifier` agree rather than diverge.
3. **Virtual dispatch is relied on deliberately.** `AwsServiceException` *overrides*
   `isThrottlingException()` and `isClockSkewException()` to consult `awsErrorDetails()` rather than
   only the HTTP status, so an `SqsException`/`SnsException` resolves to those AWS-aware overrides
   through the `SdkServiceException` arm. A separate `AwsServiceException` arm would be redundant.

Every fact above was verified by disassembling the pinned **2.30.24** jars, not assumed from class
names (§6). `jackson-core` is **not** declared in `cloud-sdk-aws`: every Jackson artifact is
governed by the Dropwizard BOM and reaches the module transitively, and the project keeps those
versions consistent by declaring them in exactly one place. `JacksonException` (jackson-core 2.21.4)
is on the compile classpath through `dropwizard-core` → `jackson-databind` → `jackson-core`.

**Wiring it in.** Message selection is untouched, so existing log and message assertions stay green:

```java
 private MessagingException handleException(String operation, String queueUrl, Exception e) {
     String message;
     ... unchanged six-arm message selection ...
-    log.error(message, e);
-    return new MessagingException(message, e);
+
+    boolean retryable = AwsFailureClassifier.isRetryable(e);
+    if (retryable) {
+        log.warn("{} (retryable)", message, e);   // transient — the caller will retry
+    } else {
+        log.error(message, e);
+    }
+    return new MessagingException(message, e, retryable, operation, queueUrl);
 }
```

**The SNS half.** `handleSnsException` keeps its exact JVM method descriptor — narrowing the declared
`RuntimeException` return type would break pre-compiled callers with `NoSuchMethodError` for no
functional gain — and returns a `NotificationException` instance. Its legacy `"SNS error: <detail>"`
format is preserved byte-for-byte, asserted directly. The new entry point accepts `Throwable`, not
`SnsException`, which is the whole point:

```java
public static RuntimeException handleSnsException(SnsException e) {
    return handle(null, null, e);                      // same descriptor, better object
}

public static NotificationException handle(String operation, String topicArn, Throwable e) {
    String errorMessage = (e instanceof AwsServiceException ase && ase.awsErrorDetails() != null)
        ? ase.awsErrorDetails().errorMessage()
        : e.getMessage();
    boolean retryable = AwsFailureClassifier.isRetryable(e);
    String message = operation == null
        ? "SNS error: " + errorMessage                 // legacy format, byte-for-byte
        : String.format("SNS error during %s on %s: %s", operation, topicArn, errorMessage);
    ...
    return new NotificationException(message, e, retryable, operation, topicArn);
}
```

All six `SnsService` catches were widened (E4):

```java
-} catch (SnsException e) {
-    log.error("Failed to publish message to topic: {}", topicArn, e);
-    throw SnsExceptionHandler.handleSnsException(e);
+} catch (Exception e) {
+    throw SnsExceptionHandler.handle("publish", topicArn, e);
 }
```

Argument validation runs *before* each `try` block in every method, so the widened catch cannot turn a
caller's `IllegalArgumentException` into a `NotificationException`. There is a test for that.

E5 gave `receiveMessages(String, int, int)` — the one method in the class with no `try/catch` — the
shared handler. E6 resolved for free: `SnsService`'s javadoc referenced a `CloudSdkException` that did
not exist anywhere in the repository until this release, and several `@throws` tags named AWS types
that were never imported.

#### The `no-cause` default — the one place this contradicts the design document

`new MessagingException("queue unavailable")` reports `isRetryable() == **true**`. Design §8.1's code
sketch passes `false`; §16.9.3 and §17.4(2) recommend `true`. Resolved in favour of `true`, and
confirmed by the reviewer.

The reasoning: with no cause there is nothing to classify, and downstream classifiers have always
treated a hand-constructed messaging failure as reprocessible.
`visibility/RetryClassifierTest:169` asserts exactly that, and
`WMEventProcessorTest:503,550` depend on it. Defaulting to `false` would silently convert
transient-failure handling into permanent-failure handling the moment `visibility` starts consulting
`isRetryable()`. Every wrap site inside cloud-sdk uses the classifying constructor and passes an
explicit verdict, so a wrapped `NullPointerException` still reports `false` — the headline requirement
is unaffected.

---

## 4. Tests

| Suite | Module | Cases | What it guards |
|---|---|---:|---|
| `SendMessageOptionsTest` | cloud-sdk-api | 38 | Delay range at and beyond both boundaries; null tolerance; copy-on-write; unmodifiability; builder reuse |
| `MessagingClientDefaultsTest` | cloud-sdk-api | 15 | **P2/P3.** Hand-written `LegacyClient` (abstract members only) must compile; every unoverridden default must throw; `ModernClient` receives delegated `int` calls |
| `CloudSdkExceptionHierarchyTest` | cloud-sdk-api | 15 | Re-parenting compatibility; sibling disjointness; no-cause default; classifying constructor |
| `AwsFailureClassifierTest` | cloud-sdk-aws | 49 | Whole AWS v2 hierarchy; poison-payload ordering; never-retry-a-bug; `UncheckedIOException` boundary |
| `SnsExceptionHandlerTest` | cloud-sdk-aws | 17 | Descriptor preserved (by reflection); legacy format byte-for-byte; `SdkClientException` acceptance |
| `SqsMessagingClientTest` (5 new nested) | cloud-sdk-aws | 43 | Delay on the wire; **byte-identical request regressions** for both legacy paths; classification; E5 |
| `SnsServiceTest` (`ExceptionHandlingTests`) | cloud-sdk-aws | 13 | E4 across all six operations; validation still unwrapped |

Module standards followed throughout: AssertJ, `@Nested` grouping with `@DisplayName`, and
`@ParameterizedTest` (`@ValueSource`, `@MethodSource`, `@NullAndEmptySource`) wherever a case differs
only by data.

Two existing `SnsServiceTest` assertions were **updated, not deleted**: E4 changes `SnsService`'s
message format by design. The legacy format survives on the direct `handleSnsException` path and is
asserted byte-for-byte there.

### 4.1 Verification results

`mvn verify` was run on all four named modules after **each** commit, and `mvn install` across the
full reactor after the version bump.

| Module | 1.0.32 | 1.0.33 | Result |
|---|---:|---:|---|
| `cloud-sdk-api` | 140 | **158** | 0 failures, 0 errors |
| `cloud-sdk-aws` | 1012 | **1105** | 0 failures, 0 errors |
| `commons` | 931 | 931 | 0 failures, 0 errors |
| `dynamo-integration-test` | 149 + 6 | 149 + 6 | 0 failures, 0 errors |
| **cloud-sdk total** | **1152** | **1263** | **+111** |

The full-reactor `mvn install` also built and installed `dynamo-client` (27) and `email-sender` (9) at
1.0.33-SNAPSHOT. **This matters:** `commons`, `dynamo-client`, `email-sender`, `cloud-sdk-api`,
`cloud-sdk-aws` and `dynamo-integration-test` all take their version from the single root
`${dependency.version}` property, so installing only the four verified modules would have left
`dynamo-client` and `email-sender` absent at 1.0.33-SNAPSHOT and unresolvable for any consumer pinning
that version. `utils/*` and `libs/*` carry their own version properties and are unaffected.

---

## 5. Impact analysis across `mercury-services`

| Item | Value |
|---|---|
| Repository | `C:\Users\arijit.kundu\projects\mercury-services` |
| Branch / HEAD | `feature/ION-16417-pibl-es-lambda-size-fix` @ `886e867480` |
| Method | Static sweep (`git grep` over tracked sources) — no build, no test run |
| Excluded per instruction | `bill-of-lading`, `bill-of-lading-v2`, `oceanschedules`, `oceanschedules-process`, `libs/atlantida` |

### 5.1 Verdict

**No in-scope `mercury-services` module breaks — at compile time or at runtime — from either section,
at any commons version, with zero source changes required.**

Every hazard the design flagged as *residual* was checked directly and none is realised:

| Hazard | Sweep result |
|---|---|
| §9.2 — the new `int` overload makes an existing `sendMessage(url, body, null)` ambiguous | **Not realised.** No three-argument `sendMessage` call on a `MessagingClient` exists anywhere. All 10 hits are on `pi-commons`'s own concrete `SQSClient`. |
| §9.2 — an implementor accidentally overrides a new `default` | **Not realised, and structurally impossible.** `git grep "implements MessagingClient"` returns **zero** in-scope hits — every consumer composes (`private final MessagingClient<String>`). `pi-commons.SQSClient` does declare `sendMessage(String, String, int)`, but it implements `MessageSender`, not `MessagingClient`. |
| §9.3 — re-parenting breaks an existing `catch` | **Not realised.** Exactly one production catch names our type: `pi-commons/SQSClient.java:32`, `catch (MessagingException \| SdkException ex)`. It stays legal because the two hierarchies remain disjoint (asserted by a test in `CloudSdkExceptionHierarchyTest`). |
| §9.3 — E3's return type has downstream callers | **Not realised.** `git grep "SnsExceptionHandler\|cloudsdk.notification.exception"` returns **zero** hits outside commons. |
| §9.3 — E4/E5 caught by a downstream `catch (SdkException)` | **Not realised.** All 13 surviving AWS-exception catches are **storage** (S3) paths in `pi-commons/S3WorkspaceService` and `self-service-reports/S3Service`, plus the one messaging catch above. E4/E5 touch neither S3 nor that site's behaviour. |
| §16.6 — `default` additions to `QueueMessage`/`EventPublisher` | **Not applicable.** Neither interface was touched. Confirmed 7 external implementors exist (`booking`, `booking-bridge`, `booking-cargoscreen`, `visibility`, `watermill-commons`), so this remains a hard constraint for future work — but nothing in 1.0.33 reaches them. |

### 5.2 E5 is not merely safe here — it is corrective

`booking-cargoscreen`'s `SqsMessageHandler.getMessages()` is the **only** main-source caller of
`receiveMessages(String, int, int)` repo-wide. It deserves individual attention because it is the one
place E5 could plausibly change behaviour. It does not, and the reason is worth recording.

Its receive loop catches `Exception` (line 81) and routes through `isAbortSignal`, which walks the
**full cause chain** starting at the top-level throwable. That method's own javadoc already states:

> *cloud-sdk's `SqsMessagingClient` instead routes **every** failure through a private
> `handleException(...)` that always returns a `MessagingException`, so the abort now only ever
> arrives as a **cause**.*

That assumption was **false for precisely this one method** before 1.0.33 — `receiveMessages(String,
int, int)` had no `try/catch`, so an `AbortedException` arrived bare at the top level. The cause-chain
walk handled both shapes, so nothing was broken; but E5 now makes reality match what the module
already documents and already expects. No change is required in `booking-cargoscreen`.

### 5.3 Footprint and version pins

Modules are pinned across six commons versions, so rollout is necessarily staged. Nothing forces a
big-bang: every change is additive, so modules can adopt 1.0.33 independently and in any order, and a
module that never bumps is unaffected.

| Pin | Modules | Relevance to 1.0.33 |
|---|---|---|
| `1.0.31-SNAPSHOT` (14) | booking, booking-bridge, booking-cargoscreen, **partner-integrator**, registration, shipping-instruction, value-added-service, rates, lambda ×6 | partner-integrator is the only in-repo consumer of the delay path — and the cheapest upgrade, one release behind |
| `1.0.29-SNAPSHOT` (1) | **visibility** | Benefits most from Section B; needs a four-version jump |
| `1.0.28-SNAPSHOT` (2) | **watermill-publisher** | Owns the blanket `catch (RuntimeException)`; five-version jump |
| `1.0.27-SNAPSHOT` (4) | auth, network, tx-tracking, db-migration | auth/network have **zero** messaging or notification imports — unaffected |
| `1.0.26-SNAPSHOT` (2) | webbl, self-service-reports | Unaffected paths |
| `1.R.01.025` / `1.R.01.021` (3) | oceanschedules, oceanschedules-process | Excluded; AWS SDK v1, out of reach of this design entirely |

### 5.4 Follow-up refactors this release enables

These are **not** part of 1.0.33 and are listed because 1.0.33 is what unblocks them. Each should be
its own PR.

| # | Module | Work | Type |
|---|---|---|---|
| 1 | `partner-integrator/pi-commons` | Route the delay path through `messagingClient.sendMessage(target, content, delay)`. Deletes the `SqsClient` field, the constructor argument, both `provideSqsClient()` providers in `SIFeedApplicationInjector:140` / `SEFeedApplicationInjector:147`, and the `software.amazon.awssdk.services.sqs` imports. `catch (MessagingException \| SdkException)` collapses to `catch (MessagingException)`. **Note:** the new 900 s upper bound is stricter than today's lower-bound-only `Math.max(0, delay)` — clamp at the call site. | refactor |
| 2 | `watermill-publisher/watermill-commons` | Replace the blanket `catch (RuntimeException ex) { throw new RecoverableException(ex); }` in `SQSClient.sendMessage` — which today re-labels a converter `NullPointerException` as recoverable and retries it forever — with a classified `catch (MessagingException ex)`. Independently, its `SQSListenerClient`/`SqsQueueMessage` workaround is now pure redundancy: the system-attribute capability it bypasses the abstraction for shipped in **1.0.32**; its javadoc claiming otherwise is stale at 1.0.28. | refactor |
| 3 | `visibility/visibility-commons` | `RetryClassifier` returns `TRUE` unconditionally for any `MessagingException` — a sound heuristic while the type was opaque, now a discarded verdict. Consulting `ex.isRetryable()` is a one-line change and the only deliberate behavioural change in a high-volume module: **bump first, change the line second, as two separate commits.** The no-cause default (§3.2) was chosen specifically to keep `RetryClassifierTest:169` and `WMEventProcessorTest:503,550` green through that transition. | **behaviour change** |
| 4 | `mft-s3-aqua-appia` / `aw-bridge` | Retire `SQSClient`'s raw `SqsClient`, collapsing the two independently-built SQS clients into one — which also unifies their two independent retry-token buckets, i.e. two uncoordinated circuit breakers. Adopt `isRetryable()` in `ErrorHelper.isRecoverable`, which gives finding **B4** (a failed `changeMessageVisibility` silently consuming a message) its first clean fix. | refactor |
| 5 | `booking-cargoscreen` | `SqsMessageHandlerSuppressionTest` compiles and passes unchanged, but encodes the current classification. Extend it to assert the new verdicts so module and platform cannot silently diverge. | test-only |
| — | auth, network, webbl, tx-tracking, self-service-reports, booking, booking-bridge, registration, shipping-instruction, value-added-service, rates, lambda ×6 | **No action.** Opportunistic bump when convenient. | — |

---

## 6. AWS SDK facts verified by disassembly

Everything the classifier depends on was read out of the pinned `2.30.24` jars with `javap`, not
inferred from class names or documentation. Recorded because the tests encode these facts and a future
SDK bump should re-check them.

| Fact | How verified | Consequence |
|---|---|---|
| `SdkException.retryable()`, `SdkServiceException.isRetryableException()` / `isThrottlingException()` / `isClockSkewException()` / `statusCode()` all present | `javap` on `sdk-core-2.30.24.jar` | No SDK version floor is raised |
| `SdkServiceException.isRetryableException()` is literally `iconst_0; ireturn` on the base class | `javap -c` | The arm exists for service-specific subtypes that override it; the test exercises it via an override, not a builder flag |
| **`SdkServiceException.Builder` and `SdkException.Builder` have no `retryable(...)` setter** | `javap` on both builder interfaces | The design doc's suggested test fixture would not have compiled; tests use anonymous subclasses instead |
| `AwsServiceException.isThrottlingException()` consults `awsErrorDetails().errorCode()` through `Optional.ofNullable` | `javap -c` on `aws-core-2.30.24.jar` | Test fixtures need no `sdkHttpResponse`; throttling is correctly retryable even at HTTP 400 |
| `AwsServiceException.isClockSkewException()` returns early when `clockSkew` or `sdkHttpResponse` is null | `javap -c` | 4xx fixtures cannot accidentally classify as clock skew |
| `"ThrottlingException"` is in `AwsErrorCode`'s throttling set | `javap -c` on `AwsErrorCode.class` | The throttling test fixture is valid |
| `jackson-core` resolves to `2.21.4` transitively on the `cloud-sdk-aws` compile classpath | `mvn dependency:tree -Dverbose -Dincludes=com.fasterxml.jackson.core:jackson-core` — ~18 paths, all governed by the Dropwizard BOM | `JacksonException` (since 2.12) is available with no direct declaration; none was added |

---

## 7. Open items

1. **Not pushed.** Both code commits and the version/README commit are local, pending review.
2. **`japicmp` / `revapi` is still not wired into the build.** Design §11.3 rates this the single
   highest-value follow-up: it would convert the entire compatibility contract from a review
   convention into a build gate. Every compatibility claim in this document is currently asserted by
   hand-written tests and by the sweep in §5 — good, but not mechanical.
3. **S2 (FIFO fields) remains deferred.** `SendMessageOptions` reserves the shape;
   `messageGroupId`, `messageDeduplicationId` and `messageSystemAttributes` become new builder fields
   whenever a consumer needs them. Note SQS rejects `DelaySeconds` on FIFO queues at the message
   level, so that combination should surface as a clear `MessagingException` when FIFO lands.
4. **Re-parenting the other five exception classes** (`DynamoSupportException`, `SendEmailException`,
   `TemplateProcessingException`, `ParameterStoreException`, `StorageClientInitializationException`)
   under `CloudSdkException` is deferred to 1.0.34, per design §9.4 — each is individually as safe as
   §3.2, but doing them here would expand the blast radius of a release whose purpose is these two
   gaps.
5. **An explicit `apiCallTimeout` / `apiCallAttemptTimeout` on the SQS client** is worth considering
   separately. The SDK's internal retry can burn ~20 s inside a single call, which interacts badly
   with a visibility-timeout extension issued just before a long download. Orthogonal to this release.
