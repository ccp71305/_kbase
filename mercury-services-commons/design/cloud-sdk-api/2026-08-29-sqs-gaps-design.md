# cloud-sdk — SQS Delay Gap & Cloud Exception Model Design

| Field | Value |
|---|---|
| Document date | 2026-08-29 |
| Author | Design review (Claude) |
| Repository | `mercury-services-commons` |
| Modules touched | `cloud-sdk-api` (new types), `cloud-sdk-aws` (implementations) |
| Current version | `1.0.32-SNAPSHOT` |
| Target version | `1.0.33-SNAPSHOT` → released as `1.0.33` |
| AWS SDK v2 BOM | `2.30.24` (`cloud-sdk-aws/pom.xml:26`) — every API used by this design verified present at this version by disassembly (§8.3, §14 step 6) |
| Drivers | `mft-s3-aqua-appia` / `aw-bridge-ob` review findings B1–B4 (ION-16416); `aw-bridge-shared.SQSClient` cannot be retired because `MessagingClient` has no `DelaySeconds` surface |
| Compatibility | **Strictly additive.** No existing method signature, return type, or supertype relationship is removed or narrowed. All new interface methods are `default`. One deliberate *behavioural* change is proposed (SNS catch widening) and is called out explicitly in §9.3. |
| Command log | All command logs live in the companion **[2026-08-29-sqs-gaps-design-command.md](./2026-08-29-sqs-gaps-design-command.md)** (§14, §15.7, §16.11), split out to keep this document readable. Section numbering there mirrors this document. |
| Related | `cloud-sdk-api/docs/2026-08-21-cloudsdk-gaps-mft-s3-aqua-appia-design.md`; `aw-bridge-ob/docs/2026-08-29-aws-upgrade-code-review-claude.md` (§10–§11, findings B1–B4) |

---

## 1. Executive summary

Two independent gaps keep consumers of `cloud-sdk` coupled to raw AWS SDK v2 types.

**Gap 1 — no send-time delay.** `MessagingClient` exposes `sendMessage(String, T)` and
`sendMessage(String, T, Map<String,String>)`. Neither can set the SQS `DelaySeconds` request
parameter. `aw-bridge-shared`'s `SQSClient` therefore injects a raw
`software.amazon.awssdk.services.sqs.SqsClient` purely to build a `SendMessageRequest` with
`.delaySeconds(...)`, which its exponential-backoff retry path
(`ErrorHelper.calculateDelay` → `2^attempts × multiplier`) depends on. As of `1.0.32` this is the
*only* remaining capability that forces the raw client — `changeMessageVisibility` was closed in
`1.0.32`, and the other four `SQSClient` methods could move to the abstraction today.

**Gap 2 — the exception contract is unusable for retry decisions.**
`SqsMessagingClient` wraps everything it catches in `MessagingException extends RuntimeException`.
That is the right abstraction shape — unchecked, AWS-free — but it is *flat*: a socket timeout, a
throttle, a non-existent queue, and a `NullPointerException` from a broken message converter all
arrive as the same type with the same (absent) retry semantics. A caller that wants "retry on
transient failure" has no option except `catch (RuntimeException e)`, which also swallows genuine
programming bugs. On the SNS side the abstraction is not merely flat but *missing*:
`SnsExceptionHandler.handleSnsException` returns a bare `java.lang.RuntimeException`, and
`SnsService` catches only `SnsException` — so `SdkClientException` (network, timeout, retry
exhaustion) escapes to callers completely unwrapped as an AWS type.

This document specifies both fixes as purely additive changes shipped together in `1.0.33`.

### 1.1 Gap inventory

| ID | Gap | Module | Severity | Fix shape |
|---|---|---|---|---|
| **S1** | `MessagingClient` cannot set `DelaySeconds` | `cloud-sdk-api` | High — blocks retiring `SQSClient`'s raw client | New `SendMessageOptions` + `default` overloads |
| **S2** | No FIFO fields (`MessageGroupId`, `MessageDeduplicationId`) reachable | `cloud-sdk-api` | Low — no consumer today | Reserved slots on `SendMessageOptions` (§4.5) |
| **E1** | `MessagingException` carries no retryability signal | `cloud-sdk-api` | High — forces blanket `catch (RuntimeException)` | New `CloudSdkException` base + `isRetryable()` |
| **E2** | No common cloud-sdk exception supertype; six unrelated `extends RuntimeException` classes | `cloud-sdk-api` | Medium | Introduce `CloudSdkException`, re-parent incrementally |
| **E3** | `SnsExceptionHandler` returns raw `RuntimeException` | `cloud-sdk-aws` | High — no SNS abstraction at all | New `NotificationException`; narrow *runtime* type only |
| **E4** | `SnsService` catches only `SnsException`; `SdkClientException` escapes raw | `cloud-sdk-aws` | High — AWS types leak to clients | Widen catch to `Exception` (behavioural — see §9.3) |
| **E5** | `SqsMessagingClient.receiveMessages(String,int,int)` has no `try/catch` — the one unwrapped method | `cloud-sdk-aws` | Medium | Route through the shared handler |
| **E6** | `SnsService` javadoc references a `CloudSdkException` type that does not exist | `cloud-sdk-aws` | Cosmetic | Resolved for free by E2 |

---

## 2. Design principles

These constrain every decision below. They are derived from the release contract stated for
`mercury-services-commons`: *every release is a version bump, every release is backward compatible
and non-breaking, and consumers are always recompiled against the new version.*

| # | Principle |
|---|---|
| **P1** | **Additive only.** Never delete, rename, or change the parameter list of an existing public member. |
| **P2** | **New interface methods are `default`.** An abstract method added to `MessagingClient` would break every existing implementor and test double at compile time. |
| **P3** | **Never silently degrade.** A `default` that quietly ignores a parameter it cannot honour is worse than one that throws — see §4.4. |
| **P4** | **Recompilation is assumed, but binary compatibility is still preserved where it is free.** The consumer contract says modules are always recompiled, so source compatibility is the hard requirement. Where binary compatibility costs nothing extra (as in §8.2) we keep it anyway, because it protects consumers that are *not* in the recompile set — shaded fat JARs and already-published artifacts. |
| **P5** | **No AWS types in `cloud-sdk-api` signatures.** Retryability must be a boolean/enum the caller can read without importing `software.amazon.awssdk.*`. |
| **P6** | **No checked exceptions.** Confirmed requirement. Everything stays under `RuntimeException`. |
| **P7** | **Follow the established house patterns.** `ReceiveMessageOptions` is the builder precedent; `changeMessageVisibility` (added in `1.0.32`) is the `default`-method precedent. Mirror both rather than inventing a third style. |

---

# SECTION A — The `DelaySeconds` gap (S1)

## 3. Current state

### 3.1 What `MessagingClient` offers today

`cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/messaging/api/MessagingClient.java`:

```java
public interface MessagingClient<T> extends CloudResource {
    void sendMessage(String queueUrl, T messageBody);
    void sendMessage(String queueUrl, T messageBody, Map<String, String> attributes);
    void deleteMessage(String queueUrl, String receiptHandle);

    default void changeMessageVisibility(String queueUrl, String receiptHandle,
                                         int visibilityTimeoutSeconds) {
        throw new UnsupportedOperationException(
            "changeMessageVisibility is not supported by this MessagingClient implementation");
    }

    List<QueueMessage<T>> listMessages(String queueUrl, int maxMessages, int waitTimeSeconds);
    List<QueueMessage<T>> receiveMessages(ReceiveMessageOptions options);
    default List<QueueMessage<T>> receiveMessages(String queueUrl, int maxMessages,
                                                  int waitTimeSeconds) { /* delegates */ }
    Map<String, String> getQueueAttributes(String queueUrl);
}
```

There is no path to `DelaySeconds`. The receive side already solved the
"too many parameters, more coming" problem with an options object; the send side never did.

### 3.2 What the consumer needs

From `aw-bridge-shared`:

```java
// SQSClient — requires the raw v2 client solely for this
sqsClient.sendMessage(SendMessageRequest.builder()
        .queueUrl(target).messageBody(content)
        .delaySeconds(delay)                                  // ← the gap
        .messageAttributes(Map.of("failedAttempts", ...))     // ← already covered by the Map overload
        .build());

// ErrorHelper — the load-bearing caller
private int sendMessageForRetry(int failedAttempts, String content, String pickupQueue) {
    int updfailedAttempts = failedAttempts + 1;
    int delay = calculateDelay(updfailedAttempts);            // (int)(2^n × multiplier)
    sqsClient.sendMessage(pickupQueue, content, delay, updfailedAttempts);
    return delay;
}
```

So the required surface is **delay + attributes together**, not delay alone.

## 4. Design — `SendMessageOptions` + `default` overloads

### 4.1 Why an options object rather than more overloads

The naïve fix is two overloads: `sendMessage(String, T, int)` and
`sendMessage(String, T, Map, int)`. Rejected because:

- It does not scale. FIFO (`MessageGroupId`, `MessageDeduplicationId`) would add two more string
  parameters, producing a `sendMessage(String, T, Map, int, String, String)` that is unreadable at
  the call site and impossible to extend again without another combinatorial round.
- It is inconsistent with `ReceiveMessageOptions`, which already established the house answer to
  exactly this problem on the receive side.
- Positional `int`/`String` parameters are easy to transpose silently.

An options object makes every future addition a **new builder field**, which is both source- and
binary-compatible with zero interface churn.

### 4.2 New type — `cloud-sdk-api`

`com/inttra/mercury/cloudsdk/messaging/model/SendMessageOptions.java` — modelled field-for-field on
the existing `ReceiveMessageOptions` (private constructor taking a `Builder`, `@Getter`, static
`builder()`, null-tolerant setters, unmodifiable collections):

```java
package com.inttra.mercury.cloudsdk.messaging.model;

import lombok.Getter;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Options for a send operation.
 *
 * <p>Introduced in 1.0.33 to close the {@code DelaySeconds} gap. Deliberately <b>not</b> generic:
 * the payload stays an explicit parameter of
 * {@link com.inttra.mercury.cloudsdk.messaging.api.MessagingClient#sendMessage(String, Object,
 * SendMessageOptions)} so that this class mirrors the non-generic
 * {@link ReceiveMessageOptions}.
 *
 * <p>Every future send-time parameter is added here as a new builder field, which is source- and
 * binary-compatible; it never requires a new interface method.
 */
@Getter
public final class SendMessageOptions {

    /** SQS hard limit on {@code DelaySeconds} (15 minutes). */
    public static final int MAX_DELAY_SECONDS = 900;

    private final int delaySeconds;
    private final Map<String, String> attributes;

    private SendMessageOptions(Builder builder) {
        this.delaySeconds = builder.delaySeconds;
        this.attributes = builder.attributes.isEmpty()
                ? Collections.emptyMap()
                : Collections.unmodifiableMap(new LinkedHashMap<>(builder.attributes));
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private int delaySeconds = 0;                              // SQS default
        private Map<String, String> attributes = Collections.emptyMap();

        /**
         * @param delaySeconds 0..900. Values outside the range are rejected here rather than at the
         *                     service, so the caller gets a precise message instead of an opaque
         *                     {@code InvalidParameterValue}.
         */
        public Builder delaySeconds(int delaySeconds) {
            if (delaySeconds < 0 || delaySeconds > MAX_DELAY_SECONDS) {
                throw new IllegalArgumentException(
                        "delaySeconds must be between 0 and " + MAX_DELAY_SECONDS
                                + " (inclusive), got: " + delaySeconds);
            }
            this.delaySeconds = delaySeconds;
            return this;
        }

        public Builder attributes(Map<String, String> attributes) {
            this.attributes = attributes == null ? Collections.emptyMap() : attributes;
            return this;
        }

        public Builder attribute(String name, String value) {
            if (this.attributes.isEmpty()) {
                this.attributes = new LinkedHashMap<>();
            }
            this.attributes.put(name, value);
            return this;
        }

        public SendMessageOptions build() {
            return new SendMessageOptions(this);
        }
    }
}
```

### 4.3 New interface methods — `MessagingClient`

Two additions, both `default`. Only the first is a real extension point; the second is sugar that
delegates, so an implementor overrides exactly one method.

```java
    /**
     * Sends a message with full send-time options (delay, attributes).
     *
     * <p>Additive method introduced in 1.0.33 closing the {@code DelaySeconds} gap
     * (exponential-backoff redelivery in {@code aw-bridge-shared}). The default implementation
     * throws {@link UnsupportedOperationException} so that existing implementors and test doubles
     * remain source- and binary-compatible.
     *
     * <p>Implementors <b>must not</b> silently ignore {@code delaySeconds}: dropping the delay
     * turns a backoff into a hot redelivery loop.
     *
     * @throws com.inttra.mercury.cloudsdk.messaging.exception.MessagingException on send failure
     */
    default void sendMessage(String queueUrl, T messageBody, SendMessageOptions options) {
        throw new UnsupportedOperationException(
            "sendMessage(String, T, SendMessageOptions) is not supported by this "
                + "MessagingClient implementation");
    }

    /**
     * Convenience overload for the delay-only case. Delegates to
     * {@link #sendMessage(String, Object, SendMessageOptions)}; implementors should override that
     * method, not this one.
     */
    default void sendMessage(String queueUrl, T messageBody, int delaySeconds) {
        sendMessage(queueUrl, messageBody,
                SendMessageOptions.builder().delaySeconds(delaySeconds).build());
    }
```

This mirrors the `receiveMessages(ReceiveMessageOptions)` / `receiveMessages(String,int,int)` pair
already in the interface — one canonical method, one convenience delegate.

### 4.4 Why the default throws instead of degrading

An alternative default would be:

```java
default void sendMessage(String queueUrl, T body, SendMessageOptions options) {
    sendMessage(queueUrl, body, options.getAttributes());   // silently drops the delay
}
```

**Rejected.** The only production consumer of the delay is an exponential-backoff retry path. If the
delay is dropped, a message that failed is redelivered immediately, fails again, and is redelivered
again — a hot loop against the failing downstream, with SQS receive charges and log volume scaling
with it. That failure mode is silent and expensive. `UnsupportedOperationException` at the first call
is loud, immediate, and caught in the consumer's own integration tests. This is principle **P3**, and
it is the same choice `changeMessageVisibility` made in `1.0.32`.

### 4.5 Reserved extension slots (S2)

Not implemented in `1.0.33` — no consumer needs them — but the shape is fixed now so a later
addition is a pure builder-field change:

| Field | Purpose | Notes |
|---|---|---|
| `messageGroupId` | FIFO ordering key | Required by SQS for FIFO queues |
| `messageDeduplicationId` | FIFO explicit dedup token | Mutually exclusive with content-based dedup |
| `messageSystemAttributes` | e.g. `AWSTraceHeader` | X-Ray propagation |

Note that SQS **rejects `DelaySeconds` on FIFO queues** at the message level. When FIFO support is
added, `SqsMessagingClient` should surface that as a clear `MessagingException` rather than letting
the raw `InvalidParameterValue` through — the existing `handleException` already has an arm for
FIFO-related `UnsupportedOperationException`.

## 5. Implementation — `cloud-sdk-aws`

`SqsMessagingClient` overrides the canonical method only. The existing two-arg and three-arg
`sendMessage` methods are refactored to delegate, so there is exactly one request-building and one
exception-handling site.

```java
    @Override
    public void sendMessage(String queueUrl, T messageBody) {
        sendMessage(queueUrl, messageBody, SendMessageOptions.builder().build());
    }

    @Override
    public void sendMessage(String queueUrl, T messageBody, Map<String, String> attributes) {
        sendMessage(queueUrl, messageBody,
                SendMessageOptions.builder().attributes(attributes).build());
    }

    @Override
    public void sendMessage(String queueUrl, T messageBody, SendMessageOptions options) {
        try {
            SendMessageRequest.Builder request = SendMessageRequest.builder()
                    .queueUrl(queueUrl)
                    .messageBody(messageConverter.toString(messageBody))
                    .delaySeconds(options.getDelaySeconds());

            if (!options.getAttributes().isEmpty()) {
                request.messageAttributes(toMessageAttributes(options.getAttributes()));
            }
            sqsClient.sendMessage(request.build());
        } catch (Exception e) {
            throw handleException("sendMessage", queueUrl, e);
        }
    }
```

> **Refactor note.** The delegation above must preserve the existing behaviour of the two- and
> three-arg methods exactly: `delaySeconds(0)` is the SQS default and is what an omitted
> `DelaySeconds` already produced, so passing it explicitly is a no-op on the wire. The
> `attributes.isEmpty()` guard preserves the current "omit `MessageAttributes` entirely when empty"
> behaviour rather than sending an empty map. Verify against the existing `SqsMessagingClientTest`
> request-captor assertions before merging.

Also register the new operation in the existing `OPERATION_DESCRIPTIONS` map so error text stays
consistent — `sendMessage` is already present, so no change is required beyond confirming the
delegating methods pass the same `"sendMessage"` operation key.

## 6. Consumer migration — `aw-bridge-shared.SQSClient`

With S1 closed, the raw `SqsClient` has **no remaining justification**. The migration
(a separate PR in `mft-s3-aqua-appia`, not part of this release):

| `SQSClient` method | Today | After `1.0.33` |
|---|---|---|
| `sendMessage(target, content)` | raw v2 | `messagingClient.sendMessage(target, content)` |
| `sendMessage(target, content, delay)` | raw v2 — **the gap** | `sendMessage(target, content, delay)` |
| `sendMessage(target, content, delay, failedAttempts)` | raw v2 — **the gap** | `sendMessage(target, content, SendMessageOptions.builder().delaySeconds(delay).attribute("failedAttempts", String.valueOf(n)).build())` |
| `changeMessageVisibility(...)` | raw v2 | already available since `1.0.32` |
| `deleteMessage(...)` | raw v2 | already available |
| `getQueueAttributes(...)` | raw v2 | already available |

This lets `ExternalServicesModule` delete the `@Named("amazonSQSForSender") SqsClient` provider
entirely, collapsing the two independently-built SQS clients into one (review finding **B2**) and
removing the last `software.amazon.awssdk.services.sqs` import from `aw-bridge-shared`.

### 6.1 Consumer-side defect surfaced by the range validation

`ErrorHelper.calculateDelay` computes `(int)(Math.pow(2, failedAttempts) * multiplier)`. With
`multiplier = 1` this exceeds the SQS 900-second ceiling at **10 failed attempts** (`2^10 = 1024`).

This is a **pre-existing** defect, not one introduced here: SQS itself rejects `DelaySeconds > 900`
today with `InvalidParameterValue`, so the current code already fails at attempt 10. The builder
validation in §4.2 changes only *where* and *how clearly* it fails — `IllegalArgumentException` with
an explicit message at build time, instead of an opaque service error after a network round trip.

Recommendation for the consuming PR: clamp at the call site,
`Math.min(calculateDelay(n), SendMessageOptions.MAX_DELAY_SECONDS)`. Clamping deliberately belongs
to the consumer, not the builder — a library that silently rewrites the value it was given makes the
backoff curve a lie and would hide the same bug in the next consumer.

---

# SECTION B — Exception handling (E1–E6)

> This section is deliberately separate from Section A. The two ship together in `1.0.33` but are
> independently reviewable and independently revertible.

## 7. Problem statement

The requirement, stated precisely:

1. No checked exceptions. *(P6)*
2. Client code must not import or handle `software.amazon.awssdk.*` types. *(P5)*
3. `MessagingException` is the right abstraction and must be kept.
4. Client code must be able to **classify a failure as retryable/recoverable** — without
   `catch (RuntimeException)`, which would also catch `NullPointerException` and other programming
   bugs and retry them forever.
5. SNS must reach the same standard: today it throws bare `RuntimeException`.
6. Nothing may break.

### 7.1 Why the current shape fails requirement 4

`SqsMessagingClient.handleException` classifies for *message text* but throws away the
classification:

```java
private MessagingException handleException(String operation, String queueUrl, Exception e) {
    String message;
    if (e instanceof InvalidMessageContentsException)     message = "Invalid message content";
    else if (e instanceof UnsupportedOperationException)  message = "Operation not supported for FIFO queues";
    else if (e instanceof QueueDoesNotExistException)     message = String.format("Queue %s does not exist", queueUrl);
    else if (e instanceof AwsServiceException)            { /* ... "AWS service error: %s" ... */ }
    else if (e instanceof SdkClientException)             message = "Client-side error (network/retry issues)";
    else                                                  message = String.format("Unexpected SDK error while %s queue %s", opDesc, queueUrl);
    log.error(message, e);
    return new MessagingException(message, e);            // ← all six arms collapse to one type
}
```

The information needed to answer "should I retry this?" is computed and then discarded. The caller
receives a `MessagingException` and cannot distinguish "socket timeout, retry in 4s" from "queue
does not exist, this will never succeed" from "your converter threw an NPE".

The catch is also `catch (Exception e)` — so a `NullPointerException` thrown inside
`messageConverter` is wrapped as a `MessagingException` reading *"Unexpected SDK error while sending
a message to queue …"*, which is actively misleading during triage.

### 7.2 Why the SNS side is worse

`cloud-sdk-aws/.../notification/exception/SnsExceptionHandler.java`:

```java
public class SnsExceptionHandler {
    public static RuntimeException handleSnsException(SnsException e) {
        String errorMessage = e.awsErrorDetails() != null
                ? e.awsErrorDetails().errorMessage() : e.getMessage();
        log.error("Error performing SNS operation: {}", errorMessage);
        return new RuntimeException("SNS error: " + errorMessage, e);   // ← bare RuntimeException
    }
}
```

Two distinct defects:

1. **No abstraction type.** A caller cannot write `catch (NotificationException e)` because no such
   type exists. The only option is `catch (RuntimeException e)`.
2. **The catch is too narrow.** `SnsService` catches only `SnsException` (six sites: lines 86, 113,
   139, 161, 183, 205). `SdkClientException` is **not** a subclass of `SnsException` — the hierarchy
   is `SdkException` → `SdkServiceException` → `AwsServiceException` → `SnsException`, with
   `SdkClientException` branching off `SdkException` directly. So every network failure, connection
   timeout, and retry exhaustion propagates out of `SnsService` as a raw AWS type, straight through
   the abstraction the module exists to provide.

(`SnsService`'s own class javadoc references a `CloudSdkException` — a type that does not exist
anywhere in the repository. The intended design was evidently a common base; it was never built.
E6 resolves as a side effect of §8.1.)

## 8. Design — a classified, unchecked, AWS-free exception model

### 8.1 New base type — `CloudSdkException`

`cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/exception/CloudSdkException.java`:

```java
package com.inttra.mercury.cloudsdk.exception;

/**
 * Base type for every exception thrown across the cloud-sdk abstraction boundary.
 *
 * <p>Unchecked by design: cloud failures are not something most call sites can meaningfully
 * recover from inline, and a checked hierarchy would force {@code throws} clauses through every
 * caller.
 *
 * <p>Carries a {@link #isRetryable()} classification so a caller can implement backoff without
 * catching bare {@link RuntimeException} (which would also catch programming errors such as
 * {@link NullPointerException}) and without importing any AWS SDK type.
 *
 * @since 1.0.33
 */
public class CloudSdkException extends RuntimeException {

    private final boolean retryable;
    private final String operation;
    private final String resource;

    public CloudSdkException(String message) {
        this(message, null, false, null, null);
    }

    public CloudSdkException(String message, Throwable cause) {
        this(message, cause, false, null, null);
    }

    public CloudSdkException(String message, Throwable cause, boolean retryable,
                             String operation, String resource) {
        super(message, cause);
        this.retryable = retryable;
        this.operation = operation;
        this.resource  = resource;
    }

    /**
     * {@code true} when the failure is transient and the same call may succeed on a later attempt:
     * network/connection errors, timeouts, throttling, 5xx service errors, clock skew.
     *
     * <p>{@code false} for deterministic failures (missing queue/topic, malformed payload,
     * authorization) and for non-AWS programming errors that were wrapped at the boundary.
     */
    public boolean isRetryable() {
        return retryable;
    }

    /** Logical operation, e.g. {@code "sendMessage"} / {@code "publish"}. May be {@code null}. */
    public String getOperation() {
        return operation;
    }

    /** Queue URL, topic ARN, bucket name, … May be {@code null}. */
    public String getResource() {
        return resource;
    }
}
```

### 8.2 Re-parenting `MessagingException` — and why it is safe

```java
// before
public class MessagingException extends RuntimeException { ... }

// after
public class MessagingException extends CloudSdkException { ... }
```

This is the one change in the document that touches an existing type's declaration, so it needs to
be justified precisely rather than asserted.

**Source compatibility.** `CloudSdkException extends RuntimeException`, so `MessagingException`
`IS-A` `RuntimeException` exactly as before. Every existing
`catch (MessagingException e)`, `catch (RuntimeException e)`, `catch (Exception e)`,
`instanceof RuntimeException`, and `throws` clause continues to compile and behave identically.

**Binary compatibility.** Guaranteed by **JLS §13.4.4**: changing the direct superclass of a class
does not break compatibility with pre-existing binaries *provided the total set of superclasses
loses no members*. Here the set grows from `{RuntimeException, Exception, Throwable, Object}` to
`{CloudSdkException, RuntimeException, Exception, Throwable, Object}` — a strict superset. Nothing
is lost, so already-compiled consumers (including shaded fat JARs that will never be rebuilt) keep
working. This satisfies **P4** at zero cost.

**Both existing constructors are retained verbatim** — `MessagingException(String)` and
`MessagingException(String, Throwable)` — plus a new one carrying the classification:

```java
public class MessagingException extends CloudSdkException {

    /** @deprecated since 1.0.33 — prefer the classifying constructor. Retained for compatibility. */
    public MessagingException(String message) { super(message); }

    /** @deprecated since 1.0.33 — prefer the classifying constructor. Retained for compatibility. */
    public MessagingException(String message, Throwable cause) { super(message, cause); }

    public MessagingException(String message, Throwable cause, boolean retryable,
                              String operation, String queueUrl) {
        super(message, cause, retryable, operation, queueUrl);
    }
}
```

> **On `@Deprecated`:** apply the `@Deprecated` *javadoc tag* for guidance but consider omitting the
> *annotation* on these two constructors. They are correct for hand-constructed non-AWS failures and
> annotating them emits warnings in existing consumer builds — noise for a call that is not actually
> wrong. Recommendation: javadoc `@deprecated` note only, no annotation. Flagged as a reviewer
> decision, not a blocker.

### 8.3 The classifier — one shared, tested translation of AWS → retryable

AWS SDK v2 already answers the retryability question; the current code simply never asks it. Verified
by disassembly against **`2.30.24`** — the version declared by the AWS SDK v2 BOM at
`cloud-sdk-aws/pom.xml:26`, which is what this module actually compiles and runs against:

| Method | Declared on | Present in 2.30.24 | Meaning |
|---|---|---|---|
| `boolean retryable()` | `SdkException` | ✅ | SDK's own "safe to retry" flag |
| `boolean isRetryableException()` | `SdkServiceException` | ✅ | service-level retryable |
| `boolean isThrottlingException()` | `SdkServiceException` | ✅ | throttling / rate limit |
| `boolean isClockSkewException()` | `SdkServiceException` | ✅ | clock skew — retryable after correction |
| `int statusCode()` | `SdkServiceException` | ✅ | HTTP status |

Hierarchy confirmed at the same version: `SdkClientException extends SdkException` and
`AwsServiceException extends SdkServiceException extends SdkException`.

> **Virtual dispatch is load-bearing here.** `AwsServiceException` *overrides*
> `isThrottlingException()` and `isClockSkewException()` to consult `awsErrorDetails()` rather than
> only the HTTP status. Because the classifier tests against `SdkServiceException`, an
> `SqsException`/`SnsException` instance resolves to those AWS-aware overrides automatically. A
> separate `AwsServiceException` arm is therefore unnecessary — and adding one above the
> `SdkServiceException` arm would be harmless but redundant. This was verified in the 2.30.24
> bytecode, not assumed from the class names.

New shared helper, `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/exception/AwsFailureClassifier.java`:

```java
package com.inttra.mercury.cloudsdk.exception;

import software.amazon.awssdk.core.exception.SdkClientException;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.core.exception.SdkServiceException;

/**
 * Single point of translation from AWS SDK v2 failure semantics to the boolean carried by
 * {@link com.inttra.mercury.cloudsdk.exception.CloudSdkException#isRetryable()}.
 *
 * <p>Lives in {@code cloud-sdk-aws} — it imports AWS types and must never be referenced from
 * {@code cloud-sdk-api} (principle P5).
 *
 * @since 1.0.33
 */
public final class AwsFailureClassifier {

    private AwsFailureClassifier() { }

    public static boolean isRetryable(Throwable t) {
        // Client-side: connection reset, socket/connect timeout, retry exhaustion, DNS.
        if (t instanceof SdkClientException) {
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
        // NOT an AWS failure: NullPointerException, IllegalStateException, converter bugs, …
        // Deterministic — retrying re-executes the same bug. Never retryable.
        return false;
    }
}
```

> **Deliberately absent: an `IOException` / `InterruptedException` arm.** An earlier draft of this
> classifier ended with
> `if (t instanceof IOException || t instanceof InterruptedException) return true;`
> on the reasoning that IO and interruption are transient. Both halves are wrong here, and the arm
> was removed. It is recorded rather than silently dropped because it is an easy thing to re-add:
>
> - **`IOException` would misclassify serialization failures as retryable.**
>   `com.fasterxml.jackson.core.JsonProcessingException` extends `JacksonException` extends
>   `java.io.IOException` (verified in `jackson-core` 2.22.0 bytecode). A Jackson-backed
>   `MessageConverter` that cannot serialize a payload fails *identically on every attempt* — exactly
>   the deterministic case that must return `false`. Classifying it `true` would turn an
>   unserializable message into an infinite exponential-backoff loop: the precise retry storm §4.4
>   exists to prevent, reintroduced by the component meant to prevent it.
>   Genuine socket-level IO never reaches this arm anyway — the SDK wraps it in `SdkClientException`,
>   which the first arm already catches and classifies `true`.
> - **`InterruptedException` would invert the correct response.** Interruption is a request to *stop*,
>   not a hint to try again; the correct handling is to restore the interrupt flag and abort. It is
>   also unreachable at the top level: it is a checked exception and neither
>   `MessageConverter.toString`/`fromString` nor the SQS sync client declares it, so it can only
>   appear as a *cause* inside an `SdkClientException` — and this classifier tests the top-level
>   throwable, not the cause chain.
>
> Net effect: the arm was unreachable for `InterruptedException`, and reachable-but-harmful for
> `IOException`. Deleting it makes both cases fall through to `return false`, which is correct for
> serialization failures and irrelevant for interruption.

The final `return false` is the direct answer to the requirement *"not catch blanket
RuntimeException which would include null pointers etc as well."* A `NullPointerException` from the
message converter is still **wrapped** as a `MessagingException` (removing the wrap would be a
behavioural break for anyone catching it today), but it arrives with `isRetryable() == false`, so a
retry loop keyed on `isRetryable()` correctly refuses to retry it. The bug surfaces instead of being
retried into a storm.

> **Ordering matters.** `SdkClientException extends SdkException`, and
> `AwsServiceException extends SdkServiceException extends SdkException`. The checks must run
> most-specific-first exactly as written; reordering them silently degrades the classification to
> `SdkException.retryable()` for everything.

### 8.4 Wiring it into `SqsMessagingClient`

`handleException` gains the classification. The message-selection logic is unchanged, so error text
in existing log assertions stays stable:

```java
private MessagingException handleException(String operation, String queueUrl, Exception e) {
    String message;
    if (e instanceof InvalidMessageContentsException)      message = "Invalid message content";
    else if (e instanceof UnsupportedOperationException)   message = "Operation not supported for FIFO queues";
    else if (e instanceof QueueDoesNotExistException)      message = String.format("Queue %s does not exist", queueUrl);
    else if (e instanceof AwsServiceException ase)         { /* unchanged */ }
    else if (e instanceof SdkClientException)              message = "Client-side error (network/retry issues)";
    else {
        String opDesc = OPERATION_DESCRIPTIONS.getOrDefault(operation, operation);
        message = String.format("Unexpected SDK error while %s queue %s", opDesc, queueUrl);
    }

    boolean retryable = AwsFailureClassifier.isRetryable(e);
    if (retryable) {
        log.warn("{} (retryable)", message, e);     // transient — warn, the caller will retry
    } else {
        log.error(message, e);
    }
    return new MessagingException(message, e, retryable, operation, queueUrl);
}
```

Two notes:

- `InvalidMessageContentsException` and `QueueDoesNotExistException` are `AwsServiceException`
  subtypes with 4xx status codes, so the classifier returns `false` for them — correct, they are
  deterministic.
- The log-level split is a small behavioural improvement: transient failures that the caller will
  retry no longer emit `ERROR`. If any consumer alerts on `ERROR` volume from this logger, this
  *reduces* noise; it cannot create new alerts.

**E5** is closed in the same change: `receiveMessages(String, int, int)` at line 206 — currently the
only method in the class with no `try/catch` — is routed through the same handler, so an
`SdkClientException` during long-polling is wrapped like every other operation instead of escaping
raw.

### 8.5 Consumer adoption — `aw-bridge` (illustrative, not part of this release)

The retry decision becomes expressible without any AWS import and without a blanket catch:

```java
// ErrorHelper — additive: the existing RecoverableException branch is untouched
public boolean isRecoverable(Exception e) {
    if (e instanceof RecoverableException) {
        return recoveryConfig.isEnabled();
    }
    if (e instanceof CloudSdkException cse && cse.isRetryable()) {
        return recoveryConfig.isEnabled();
    }
    return false;
}
```

This also gives review finding **B4** (a failed `changeMessageVisibility` silently consuming a
message, because the resulting exception is not a `RecoverableException`, so `ErrorHandler` logs
without rethrowing, `process()` returns normally, and `AbstractTask` deletes the message) its first
clean fix: a transient visibility-extension failure now classifies as recoverable and the message is
redelivered rather than dropped.

> To be explicit about scope: that fix lands in `mft-s3-aqua-appia`, not here. `1.0.33` supplies the
> signal; the consumer decides what to do with it. B4 remains open until the consumer PR ships.

### 8.6 The SNS half (E3, E4, E6)

#### New type

`cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/notification/exception/NotificationException.java`:

```java
package com.inttra.mercury.cloudsdk.notification.exception;

import com.inttra.mercury.cloudsdk.exception.CloudSdkException;

/**
 * Thrown by {@link com.inttra.mercury.cloudsdk.notification.api.NotificationService} operations.
 * The SNS counterpart of
 * {@link com.inttra.mercury.cloudsdk.messaging.exception.MessagingException}.
 *
 * @since 1.0.33
 */
public class NotificationException extends CloudSdkException {
    public NotificationException(String message) { super(message); }
    public NotificationException(String message, Throwable cause) { super(message, cause); }
    public NotificationException(String message, Throwable cause, boolean retryable,
                                 String operation, String topicArn) {
        super(message, cause, retryable, operation, topicArn);
    }
}
```

#### E3 — narrow the *runtime* type, keep the *static* return type

The tempting change is to narrow the declared return type of `handleSnsException` from
`RuntimeException` to `NotificationException`. That is source-compatible (covariant narrowing is
fine for `throw` and for assignment to `RuntimeException`) but **binary-incompatible**: the return
type is part of the JVM method descriptor, so any pre-compiled caller would hit `NoSuchMethodError`.
Under the stated contract every consumer is recompiled, so this would *probably* be fine — but it is
an unnecessary risk when a zero-cost alternative exists.

**Recommended: keep the signature exactly as it is and change only the object returned.**

```java
public class SnsExceptionHandler {

    /**
     * @deprecated since 1.0.33 — prefer {@link #handle(String, String, Throwable)}, which classifies
     *             retryability and accepts non-{@code SnsException} failures such as
     *             {@code SdkClientException}. Retained unchanged for compatibility.
     *
     * <p>Note the declared return type is deliberately left as {@link RuntimeException}: narrowing
     * it would change the method descriptor and break pre-compiled callers. The <i>runtime</i> type
     * is now always a {@link NotificationException}, so new code can catch the specific type while
     * old code catching {@code RuntimeException} is unaffected.
     */
    public static RuntimeException handleSnsException(SnsException e) {
        return handle(null, null, e);                       // ← same descriptor, better object
    }

    /** @since 1.0.33 */
    public static NotificationException handle(String operation, String topicArn, Throwable e) {
        String errorMessage = (e instanceof AwsServiceException ase && ase.awsErrorDetails() != null)
                ? ase.awsErrorDetails().errorMessage()
                : e.getMessage();

        boolean retryable = AwsFailureClassifier.isRetryable(e);
        String message = operation == null
                ? "SNS error: " + errorMessage
                : String.format("SNS error during %s on %s: %s", operation, topicArn, errorMessage);

        if (retryable) {
            log.warn("{} (retryable)", message, e);
        } else {
            log.error(message, e);
        }
        return new NotificationException(message, e, retryable, operation, topicArn);
    }
}
```

This is the key move: **100% source *and* binary compatible, while every SNS failure becomes
catchable as `NotificationException` and carries a retryability signal.** Existing
`catch (RuntimeException e)` sites keep working unchanged; new code can be specific.

The message format of the legacy path is preserved byte-for-byte (`"SNS error: " + errorMessage`)
when `operation` is `null`, so existing log-assertion tests stay green.

#### E4 — widen the catch in `SnsService`

At all six sites (lines 86, 113, 139, 161, 183, 205):

```java
// before
} catch (SnsException e) {
    throw SnsExceptionHandler.handleSnsException(e);
}

// after
} catch (Exception e) {
    throw SnsExceptionHandler.handle("publish", topicArn, e);
}
```

This brings SNS to parity with `SqsMessagingClient`, which has caught `Exception` all along.

## 9. Compatibility analysis

### 9.1 Section A

| Change | Source | Binary | Notes |
|---|---|---|---|
| New class `SendMessageOptions` | ✅ | ✅ | Purely additive |
| `default sendMessage(String, T, SendMessageOptions)` | ✅ | ✅ | Existing implementors inherit the default |
| `default sendMessage(String, T, int)` | ✅ | ✅ | See §9.2 for the overload-resolution check |
| `SqsMessagingClient` overrides + delegation | ✅ | ✅ | Behaviour of existing methods preserved (§5) |

### 9.2 Overload-resolution check for `sendMessage(String, T, int)`

The one place an additive overload could bite is ambiguity with the existing
`sendMessage(String, T, Map<String,String>)`. Worked through:

| Existing call site | Before | After | Verdict |
|---|---|---|---|
| `sendMessage(url, body, someMap)` | Map overload | Map overload | ✅ `Map` is not convertible to `int` |
| `sendMessage(url, body, null)` | Map overload | Map overload | ✅ `null` is not convertible to the primitive `int`, so only one overload is applicable — **no ambiguity** |
| `sendMessage(url, body, someInt)` | did not compile | `int` overload | ✅ new capability, cannot break anything |
| `sendMessage(url, body, someInteger)` | did not compile | `int` overload (unboxing) | ✅ new capability |

No existing call site changes resolution. The `null` case is the one worth stating explicitly, and
it is safe precisely because the new parameter is a primitive.

> **Residual risk (negligible, stated for completeness):** an existing implementor that already
> declares its own `sendMessage(String, T, int)` with unrelated semantics would silently become an
> override of the new default. Verify with a repository-wide grep before release; no such
> implementor exists today.

### 9.3 Section B

| Change | Source | Binary | Behavioural | Notes |
|---|---|---|---|---|
| New `CloudSdkException` | ✅ | ✅ | — | Additive |
| `MessagingException extends CloudSdkException` | ✅ | ✅ | — | JLS §13.4.4, §8.2 |
| New `MessagingException` classifying constructor | ✅ | ✅ | — | Old constructors retained |
| New `NotificationException` | ✅ | ✅ | — | Additive |
| `AwsFailureClassifier` | ✅ | ✅ | — | New, `cloud-sdk-aws` only |
| `handleSnsException` returns a `NotificationException` instance | ✅ | ✅ | Low | Descriptor unchanged; runtime type narrowed |
| New `SnsExceptionHandler.handle(...)` | ✅ | ✅ | — | Additive overload |
| Log level `ERROR`→`WARN` for retryable | ✅ | ✅ | Low | Strictly reduces `ERROR` volume |
| `SqsMessagingClient.receiveMessages(String,int,int)` gains `try/catch` (E5) | ✅ | ✅ | **Medium** | See below |
| **`SnsService` catch widened to `Exception` (E4)** | ✅ | ✅ | **Medium** | See below |

**The two deliberate behavioural changes.** Both are the *point* of the fix, so they cannot be
avoided — but they must be shipped knowingly rather than discovered:

- **E4.** Today an `SdkClientException` thrown inside `SnsService.publish` escapes raw. After the
  change it is wrapped in a `NotificationException`. A consumer that today writes
  `catch (SdkClientException e)` around a `publish()` call would stop catching it. Such a consumer
  is doing exactly what the abstraction exists to prevent, and none is known — but the assumption
  must be verified, not assumed.
- **E5.** Same shape for `receiveMessages(String,int,int)`: raw AWS exceptions from long-polling
  become `MessagingException`.

Anyone catching `RuntimeException`, `Exception`, `MessagingException`, or `NotificationException` is
unaffected in both cases.

**Required pre-release verification** — run across every consuming workspace
(`mft-s3-aqua-appia`, booking, visibility, …):

```bash
git grep -nE "catch\s*\(\s*(Sns|Sqs|Sdk|Aws)[A-Za-z]*Exception" -- '*.java'
```

Ship E4/E5 only if this returns nothing outside `mercury-services-commons` itself. If it returns
hits, fix those call sites in the same coordinated release.

### 9.4 What is explicitly *not* being done

| Rejected | Why |
|---|---|
| Re-parenting the other five exception classes (`DynamoSupportException`, `SendEmailException`, `TemplateProcessingException`, `ParameterStoreException`, `StorageClientInitializationException`) under `CloudSdkException` in `1.0.33` | Each is individually as safe as §8.2, but each also expands the blast radius of a release whose purpose is the SQS delay gap. Do them in `1.0.34` as a mechanical follow-up, after `1.0.33` has proven the pattern in production. |
| Making `CloudSdkException` abstract | It would prevent `new CloudSdkException(...)` in consumer test doubles and in any future generic wrap site. No benefit. |
| A `FailureKind` enum (`THROTTLED`, `TIMEOUT`, `NOT_FOUND`, `CLIENT_BUG`, …) instead of a boolean | Richer, and a plausible `1.0.34` addition as an *added* accessor with a derived default. Not in `1.0.33`: the requirement is a retry decision, a boolean answers it exactly, and an enum locks in a taxonomy before there is evidence for its categories. |
| Removing the `catch (Exception e)` wrap so `NullPointerException` propagates raw | Behavioural break for anyone catching `MessagingException` today. `isRetryable() == false` solves the actual problem — the NPE is not retried — without changing what is caught. |
| Checked exceptions | Explicitly ruled out (**P6**). |
| Narrowing `handleSnsException`'s declared return type | Binary-incompatible for no functional gain (§8.6). |

### 9.5 AWS SDK version floor

`AwsFailureClassifier` (§8.3) is the only new code that touches AWS types, so it is the only place
this design could impose a minimum SDK version. It does not raise one: all five predicates and both
inheritance edges it relies on are present in the pinned `2.30.24` and have been stable across the
2.x line — the identical surface was observed at `2.42.28`. `1.0.33` therefore compiles against the
existing BOM with **no SDK bump required**.

Two notes for the reviewer:

- The classifier is confined to `cloud-sdk-aws`. `cloud-sdk-api` — where `CloudSdkException`,
  `MessagingException`, `NotificationException` and `SendMessageOptions` live — gains **no** AWS
  dependency, preserving principle **P5**. A consumer can read `isRetryable()` with no
  `software.amazon.awssdk` type on its compile classpath.
- A consumer that force-overrides the transitive SDK to something *older* than 2.30.24 is outside
  the tested configuration. That is already true today for the existing `handleException`
  (which uses `AwsServiceException.awsErrorDetails()` and `SdkClientException`), so this design adds
  no new exposure — but consumers should pin the BOM rather than let Maven nearest-wins resolution
  decide.

## 10. Release plan

| Step | Action |
|---|---|
| 1 | Bump root `pom.xml` `<dependency.version>` from `1.0.32-SNAPSHOT` to `1.0.33-SNAPSHOT` |
| 2 | **PR 1** — Section A: `SendMessageOptions`, two `default` methods, `SqsMessagingClient` override + delegation refactor, unit tests |
| 3 | **PR 2** — Section B: `CloudSdkException`, `AwsFailureClassifier`, `MessagingException` re-parent, `NotificationException`, `SnsExceptionHandler.handle`, `SnsService` catch widening, E5 |
| 4 | Run the §9.3 consumer grep across all downstream workspaces — **gate for PR 2** |
| 5 | Release `1.0.33`; release notes must call out the two behavioural changes in §9.3 explicitly |
| 6 | Downstream (`mft-s3-aqua-appia`): bump to `1.0.33`, migrate `SQSClient` off the raw `SqsClient` (§6), delete the `@Named("amazonSQSForSender")` provider, adopt `isRetryable()` in `ErrorHelper` (§8.5), clamp the delay (§6.1) |
| 7 | Downstream (booking, visibility): bump to `1.0.33` — **no code change required**; every addition is `default`/additive |

Steps 2 and 3 are independent and can land in either order.

## 11. Test plan

### 11.1 Section A

| Test | Assertion |
|---|---|
| `SendMessageOptionsTest` | defaults are `delaySeconds == 0` and an empty attribute map |
| `SendMessageOptionsTest` | `delaySeconds(-1)` and `delaySeconds(901)` throw `IllegalArgumentException`; `0` and `900` are accepted |
| `SendMessageOptionsTest` | `attributes(null)` yields an empty map, not an NPE |
| `SendMessageOptionsTest` | the returned attribute map is unmodifiable, and mutating the source map after `build()` does not affect the built object |
| `SqsMessagingClientTest` | request captor: `delaySeconds` is present and correct on the built `SendMessageRequest` |
| `SqsMessagingClientTest` | **regression** — `sendMessage(url, body)` and `sendMessage(url, body, attrs)` produce byte-identical requests before and after the delegation refactor, including the "omit `MessageAttributes` when empty" behaviour |
| `MessagingClientDefaultsTest` | a bare `MessagingClient` test double (implementing only the abstract methods) still **compiles**, and both new defaults throw `UnsupportedOperationException` — this is the P2/P3 guard |
| `MessagingClientDefaultsTest` | a double overriding only `sendMessage(String,T,SendMessageOptions)` correctly receives delegated calls from the `int` overload |

### 11.2 Section B

| Test | Assertion |
|---|---|
| `AwsFailureClassifierTest` | `SdkClientException` → `true` |
| `AwsFailureClassifierTest` | throttling `AwsServiceException` (`isThrottlingException()`) → `true` |
| `AwsFailureClassifierTest` | 503 `AwsServiceException` → `true`; 400 → `false` |
| `AwsFailureClassifierTest` | `QueueDoesNotExistException` → `false` |
| `AwsFailureClassifierTest` | **`NullPointerException` → `false`** — the headline requirement |
| `AwsFailureClassifierTest` | **`JsonProcessingException` → `false`** — the regression guard for the removed `IOException` arm (§8.3). It extends `IOException`, so a naïve "IO is transient" rule would classify an unserializable payload as retryable and loop forever |
| `AwsFailureClassifierTest` | a generic `IOException` → `false` — same guard, stated independently of Jackson |
| `AwsFailureClassifierTest` | ordering: an `SdkClientException` is classified by the `SdkClientException` arm, not by `SdkException.retryable()` |
| `MessagingExceptionTest` | `new MessagingException("x") instanceof RuntimeException` — the §8.2 compatibility guard |
| `MessagingExceptionTest` | `instanceof CloudSdkException`; both legacy constructors still exist and yield `isRetryable() == false` |
| `SqsMessagingClientTest` | a converter-thrown NPE surfaces as `MessagingException` with `isRetryable() == false` |
| `SqsMessagingClientTest` | a simulated `SdkClientException` surfaces as `MessagingException` with `isRetryable() == true` |
| `SqsMessagingClientTest` | E5 — `receiveMessages(String,int,int)` wraps an `SdkClientException` instead of letting it escape |
| `SnsExceptionHandlerTest` | `handleSnsException(e)` returns an instance of `NotificationException` while the declared return type stays `RuntimeException` |
| `SnsExceptionHandlerTest` | the legacy message format `"SNS error: <detail>"` is preserved exactly when `operation` is `null` |
| `SnsServiceTest` | E4 — a simulated `SdkClientException` from the underlying `SnsClient` emerges as `NotificationException` with `isRetryable() == true`, not as a raw AWS type |

### 11.3 Cross-cutting

- **`japicmp` / `revapi`** against `1.0.32` in the build, configured to fail on any binary-incompatible
  change. This mechanically enforces §9 instead of relying on this document being read. If neither
  plugin is currently configured, adding one is the single highest-value follow-up from this design —
  it converts the entire compatibility contract from a review convention into a build gate.
- **Compile-only consumer smoke test**: a test module implementing `MessagingClient` with *only* the
  abstract methods must compile against `1.0.33` without modification.

## 12. Open questions for the reviewer

1. **`@Deprecated` annotation vs javadoc tag** on the legacy `MessagingException` constructors
   (§8.2). Recommendation: javadoc tag only — the annotation emits warnings in consumer builds for a
   call that is not wrong.
2. **Ship E4/E5 in `1.0.33` or hold them for `1.0.34`?** They are the only behavioural changes in the
   release. Recommendation: ship in `1.0.33`, gated on the §9.3 grep returning clean — splitting them
   out means SNS keeps leaking raw AWS types for another release cycle, which is the defect being
   fixed.
3. **Re-parent the other five exception classes now or in `1.0.34`?** Recommendation: `1.0.34`
   (§9.4).
4. **Is `japicmp`/`revapi` already wired into the build?** If not, §11.3 should become a blocking
   item rather than a follow-up.

---

## 13. Summary of new and changed files

### New — `cloud-sdk-api`

| File | Purpose |
|---|---|
| `.../messaging/model/SendMessageOptions.java` | Send-time options (delay, attributes); the S1 fix |
| `.../exception/CloudSdkException.java` | Common base with `isRetryable()`; the E1/E2 fix |
| `.../notification/exception/NotificationException.java` | SNS abstraction type; the E3 fix |

### New — `cloud-sdk-aws`

| File | Purpose |
|---|---|
| `.../exception/AwsFailureClassifier.java` | AWS v2 → retryable translation, in one tested place |

### Changed — `cloud-sdk-api`

| File | Change |
|---|---|
| `.../messaging/api/MessagingClient.java` | +2 `default` methods (additive) |
| `.../messaging/exception/MessagingException.java` | Re-parent to `CloudSdkException`; +1 constructor; existing constructors retained |

### Changed — `cloud-sdk-aws`

| File | Change |
|---|---|
| `.../messaging/aws/impl/SqsMessagingClient.java` | Override the options-based `sendMessage`; delegate the existing two; classify in `handleException`; wrap `receiveMessages(String,int,int)` (E5) |
| `.../notification/exception/SnsExceptionHandler.java` | Return a `NotificationException` instance (descriptor unchanged); +`handle(String,String,Throwable)` |
| `.../notification/impl/SnsService.java` | Widen six `catch (SnsException)` to `catch (Exception)`; route through `handle(...)`; fix the dangling `CloudSdkException` javadoc reference (E6) |

### Changed — root

| File | Change |
|---|---|
| `pom.xml` | `<dependency.version>` `1.0.32-SNAPSHOT` → `1.0.33-SNAPSHOT` |

---

## 14. Investigation log

Moved. The full log — every command run to establish the facts in §1–§13, with its syntax
explained, plus §14.1 *What was not done* — now lives in the companion document:

> **[2026-08-29-sqs-gaps-design-command.md](./2026-08-29-sqs-gaps-design-command.md) → §14**

It was moved out to keep this document readable. Nothing was changed in the process; the
section numbering there mirrors the numbering here, so every `§14` cross-reference in this
document still resolves.

---

## 15. Appendix — AWS SDK v2's own retry behaviour (reviewer question)

> **Status: informational.** This section answers a review question. It proposes **no change** to the
> design in §1–§14 — and the answers turn out to support that design rather than alter it.

### 15.1 What the SDK does before your `catch` block ever runs

Every `SqsClient` / `SnsClient` call already retries internally. All values below were read from the
pinned **2.30.24** bytecode (commands in §15.7), not from documentation.

| Setting | Value at 2.30.24 | Source |
|---|---|---|
| Default retry mode | **`LEGACY`** | `RetryMode.Resolver.SDK_DEFAULT_RETRY_MODE` |
| Max attempts — `LEGACY` | **4** (1 initial + 3 retries) | `DefaultRetryStrategy$Legacy.MAX_ATTEMPTS` |
| Max attempts — `STANDARD` / `ADAPTIVE` | 3 | `DefaultRetryStrategy$Standard` / `$Adaptive` |
| Base delay | 100 ms | `BASE_DELAY` |
| Throttled base delay (`LEGACY`) | 500 ms | `THROTTLED_BASE_DELAY` |
| Max backoff | **20 s** | `MAX_BACKOFF` |
| Retry token bucket | 500 tokens | `TOKEN_BUCKET_SIZE` |
| Cost per retried failure | 5 tokens | `DEFAULT_EXCEPTION_TOKEN_COST` |
| Cost per throttling failure (`LEGACY`) | 0 tokens | `THROTTLE_EXCEPTION_TOKEN_COST` |

What it retries on:

| Category | Members | Source |
|---|---|---|
| HTTP status | `500`, `502`, `503`, `504` | `SdkDefaultRetrySetting.RETRYABLE_STATUS_CODES` |
| Exception types | `RetryableException`, **`java.io.IOException`**, `UncheckedIOException`, `ApiCallAttemptTimeoutException` | `SdkDefaultRetrySetting.RETRYABLE_EXCEPTIONS` |
| Predicates | throttling, clock skew, service-flagged retryable | `RetryUtils.isThrottlingException` / `isClockSkewException` / `isRetryableException` |

Backoff is exponential with jitter, capped at 20 s. So a single `sendMessage(...)` call can already
consume up to roughly **20 seconds** internally before it throws.

### 15.2 Q1 — Is `isRetryable()` double plumbing?

**No. The two retries operate on different units of work, over different time horizons, with
different failure coverage.** They are tiers, not duplicates.

| | AWS SDK retry | Application retry (SQS redelivery + `DelaySeconds`) |
|---|---|---|
| Unit retried | one HTTP API call | the **entire** message-processing unit: parse → HeadObject → download 30 MiB → FTP write → SNS publish |
| Horizon | 100 ms … ~20 s | seconds … hours (`2^n × multiplier`) |
| State | in-process, same connection pool | durable — the message is still in SQS |
| Survives process crash / redeploy / AZ loss | ❌ | ✅ |
| Survives an outage longer than 20 s | ❌ | ✅ |
| Covers non-AWS failures (FTP disk full, downstream 500) | ❌ | ✅ |
| Visible to operators | no (silent) | yes (`failedAttempts` attribute, redelivery) |

The SDK cannot help with the failures that actually matter to `aw-bridge-ob`: a crash halfway
through a large download, a full destination filesystem, or an S3/SQS degradation lasting minutes.
Those are precisely what the `DelaySeconds` backoff of Section A exists to handle. Removing the
application tier because "the SDK already retries" would trade a durable, observable, whole-operation
retry for a 20-second in-process one.

### 15.3 Q2 — Will a retryable exception ever actually reach client code?

**Yes — routinely, by four distinct mechanisms.** This is the load-bearing answer: if it were "no",
`isRetryable()` would be dead code.

1. **Attempt exhaustion.** After 4 attempts (`LEGACY` default) the SDK rethrows the *last* failure.
   Its `retryable()` flag is **still `true`** — the flag describes the *nature* of the failure, not
   whether budget remains. `SdkException.numAttempts()` reports how many were made.
2. **Retry-budget (token bucket) exhaustion — the important one.** The bucket holds 500 tokens and
   each retried failure costs 5, so after ~100 retried failures in flight the budget is empty and the
   SDK **stops retrying entirely and fails fast on the first attempt**. This is deliberate circuit
   breaking to avoid retry storms — which means that during a *sustained* outage, exactly when one
   might assume the SDK is covering the application, it is by design not retrying at all. Every
   failure lands directly in client code, `retryable() == true`, `numAttempts() == 1`.
3. **Outage longer than the backoff window.** Max backoff is 20 s. Any degradation lasting longer
   than the attempt budget exhausts it and surfaces.
4. **Transient failures outside the SDK's retry predicate** — e.g. DNS resolution failures and
   throttle variants not matching `RETRYABLE_STATUS_CODES` or `RetryUtils`.

**Therefore `CloudSdkException.isRetryable() == true` should be read as:**

> *"This failure is transient in nature. The SDK has already exhausted its own retries, or
> deliberately declined to retry because its budget was spent. Escalating to the durable
> application-level retry is the correct next step."*

It does **not** mean "nobody has tried yet". Cases 2 and 4 are the strongest argument that the
classifier is necessary rather than redundant: in a real outage the SDK hands failures straight
through, and without `isRetryable()` the consumer's only options are a blanket
`catch (RuntimeException)` or dropping the message (review finding **B4**).

### 15.4 Real interactions worth knowing (not defects, and not design changes)

The tiers do not duplicate each other, but they do compose — with consequences:

1. **Latency amplification.** Each SQS/SNS call may silently burn up to ~20 s. Total time-to-give-up
   is *(SDK internal backoff) × (application attempts)*. Worth knowing when reasoning about
   throughput during a degradation, and when setting any API-call timeout.
2. **Visibility-timeout interaction in `BridgeTask` — the sharpest one.**
   `changeMessageVisibility` is called *before* the large download. If that call spends ~20 s on
   internal retries and then fails, the message's current visibility timeout has been ticking
   throughout. The extension can therefore fail *and* arrive too late, making duplicate delivery more
   likely precisely in the large-object case the extension exists to protect. This compounds finding
   **B4** rather than replacing it.
3. **The retry budget is per client instance.** The token bucket lives on the client. Finding **B2**
   (two independently-built `SqsClient` instances — sender and listener) therefore means **two
   independent circuit breakers** that cannot see each other's failures. Consolidating onto one
   `MessagingClient` (§6) unifies the retry budget as a side effect — a concrete benefit of B2 that
   was not visible when B2 was first raised.
4. **`sendMessage` is retried internally, so duplicates are possible** when a response is lost after
   the service accepted the message. Harmless here: standard SQS queues are at-least-once regardless,
   and the pipeline already has duplicate suppression.

### 15.5 Why the SDK retries on `IOException` but §8.3 must not

The SDK's `RETRYABLE_EXCEPTIONS` set includes `java.io.IOException` and `UncheckedIOException`. This
is worth stating explicitly because it looks like it contradicts the removal of the `IOException` arm
from `AwsFailureClassifier` (§8.3). It does not — **the same rule is correct at one layer and wrong
at the other**:

| | AWS SDK retry layer | `AwsFailureClassifier` (§8.3) |
|---|---|---|
| Position in the stack | inside the HTTP client, **below** any serialization | in `SqsMessagingClient`, **above** `MessageConverter` |
| What an `IOException` can be there | only transport IO — socket reset, connect timeout, truncated read | transport IO (already converted to `SdkClientException` by the time it arrives) **or** `JsonProcessingException extends JacksonException extends IOException` from a converter |
| Correct classification | retryable ✅ | **not** retryable — an unserializable payload fails identically forever |

At the SDK's position, "IOException ⇒ transient" is sound because nothing else can produce one. At
the classifier's position it is unsound, because the converter sits above it and Jackson's failures
are `IOException`s. Copying the SDK's rule upward would have reintroduced the retry storm described
in §8.3. This also explains where the deleted arm's intuition came from — it is the SDK's own rule,
lifted one layer too high.

### 15.6 Consequences for the design in §1–§14

None. Specifically:

- §8.3 `AwsFailureClassifier` — unchanged and confirmed necessary by §15.3.
- §8.5 consumer adoption (`ErrorHelper.isRecoverable`) — unchanged; it correctly sits *above* the
  SDK tier.
- Section A `DelaySeconds` — unchanged and reinforced: it is the durable tier the SDK cannot provide.

The one thing a reviewer may want to add as a **follow-up outside this release** is an explicit
`apiCallTimeout` / `apiCallAttemptTimeout` on the SQS client so the ~20 s worst case is bounded
relative to the visibility timeout (§15.4 item 2). That is a client-configuration change in
`cloud-sdk-aws`, orthogonal to everything proposed here, and deliberately **not** folded into
`1.0.33`.

### 15.7 Verification commands for this appendix

Moved to **[2026-08-29-sqs-gaps-design-command.md](./2026-08-29-sqs-gaps-design-command.md) → §15.7**
— the `unzip`/`javap` sequence used to read the SDK's own retry defaults out of the resolved
`sdk-core-2.30.24.jar`, together with the caveat on consumer overrides.

---

## 16. Impact assessment — `mercury-services` applications

This section answers the reviewer's question: *what is the footprint of the API call sites and the
exception changes across the mercury applications, and what breaks?*

Nothing in this section changes the design in §1–§15. It is an assessment of the blast radius, plus
three findings that came out of the sweep and that the reviewer should weigh **before** approving
implementation. No code was modified in either repository.

### 16.1 Scope, method, and exclusions

| Item | Value |
| --- | --- |
| Repository | `C:\Users\arijit.kundu\projects\mercury-services` |
| Branch | `feature/ION-16417-pibl-es-lambda-size-fix` |
| HEAD | `886e867480` |
| Method | Static sweep only — `git grep` over tracked sources. No build, no test run, no bytecode diff. |
| Modules in scope | booking, visibility, network, auth, watermill-publisher (high volume); booking-cargoscreen, shipping-instruction, partner-integrator, lambda, registration, tx-tracking; plus booking-bridge, booking-downstream-processor, webbl, value-added-service, rates, libs, self-service-reports as incidental consumers |
| **Excluded — reviewer instruction** | `bill-of-lading`, `bill-of-lading-v2` |
| **Excluded — still AWS SDK v1** | `oceanschedules`, `oceanschedules-process` (pinned `1.R.01.025`, use `com.amazonaws.*`). They are unaffected by anything in this design; they are a *future* migration target, not a compatibility risk. |
| `aw-bridge` | Lives in the `mft-s3-aqua-appia` repo and is not yet merged. Assessed separately in §8.5; not re-counted here. |

### 16.2 Verdict

**No mercury-services module breaks — at compile time or at runtime — from either Section A or
Section B, at any commons version, with zero source changes required.**

Every change in the design is additive, and the sweep confirms the specific hazards flagged as
*residual* in §9.2 and §9.3 are **not realised anywhere in the repo**:

| Hazard flagged in the design | Status after sweep |
| --- | --- |
| §9.2 — a caller writes `sendMessage(url, body, null)` and the new `int` overload makes it ambiguous | **Not realised.** Zero three-argument `sendMessage` call sites exist anywhere in mercury-services. |
| §9.2 — a subclass accidentally overrides a new `default` method | **Not realised for `MessagingClient`.** Every `SQSClient` wrapper uses *composition* (`private final MessagingClient<String>`), never `implements MessagingClient`. |
| §9.3 — re-parenting `MessagingException` under `CloudSdkException` breaks an existing `catch` | **Not realised.** Exactly one production `catch` names our type, and it stays valid (§16.7). |
| §9.3 — E3 (`SnsExceptionHandler` return type) has downstream callers | **Not realised.** `SnsExceptionHandler` has zero callers outside commons. |
| §9.3 — E4/E5 behavioural change is caught by a downstream `catch (SdkException)` around SNS or SQS-receive | **Not realised.** All surviving AWS-exception catches are either SDK v1 modules or **storage** (S3) paths, which E4/E5 do not touch. |

The sweep did, however, surface three things that are **not** breakage but that materially affect the
value and the sequencing of the work: a hazard the design under-specifies (§16.6), a **retraction** of
an earlier proposed third gap that turned out to be already closed (§16.8), and prior art in
`visibility` that the design should adopt rather than duplicate (§16.9).

### 16.3 Consumer footprint

Files importing the cloud-sdk messaging / notification packages, per module. This is the surface that
a version bump touches.

| Module | Files using `cloudsdk.messaging` | Files using `cloudsdk.notification` | Total `cloudsdk` imports | Section A relevance | Section B relevance |
| --- | ---: | ---: | ---: | --- | --- |
| **visibility** (high volume) | 49 | 46 | 117 | none — no delay use | **high** — owns its own `RetryClassifier` (§16.9) |
| **partner-integrator** | 20 | 14 | 77 | **high** — dual-client delay wrapper | **high** — only real `catch (MessagingException)` |
| **booking** (high volume) | 10 | 4 | 69 | none | low |
| **watermill-publisher** (high volume) | 28 | 30 | 60 | none — but see §16.8 (stale workaround, already fixable) | **high** — blanket `catch (RuntimeException)` |
| **network** (high volume) | 0 | 0 | 52 | none | none — storage/other cloud-sdk only |
| **auth** (high volume) | 0 | 0 | 45 | none | none |
| webbl | 4 | 5 | 36 | none | none — has its *own* `MessagingException` |
| lambda (6 sub-modules) | 0 | 4 | 32 | none | low — notification only |
| booking-bridge | 3 | 10 | 28 | none | low |
| shipping-instruction | 0 | 0 | 26 | none | none |
| booking-downstream-processor / booking-cargoscreen | 10 | 8 | 17 | none | **medium** — tests assert on `MessagingException` |
| value-added-service | — | 2 | 15 | none | none |
| registration | 0 | 0 | 15 | none | none |
| tx-tracking | 3 | 0 | 13 | none | low |
| rates | — | — | 7 | none | none |
| self-service-reports | 0 | 0 | 3 | none | none — S3 only |

Read this table with §16.4: a module with a large import count is not necessarily *affected*; it is
merely *exposed to the version bump*. `network` and `auth` have 52 and 45 cloud-sdk imports and
**zero** messaging or notification imports — their cloud-sdk usage is storage, config and logging, so
neither Section A nor Section B reaches them.

### 16.4 Version-pin reality — who can actually take 1.0.33

This is the practical constraint on rollout, and it is more significant than any compatibility risk.
Modules are pinned across **six different commons versions**:

| Pinned `mercury.commons.version` | Modules |
| --- | --- |
| `1.0.31-SNAPSHOT` | booking, booking-bridge, booking-cargoscreen, partner-integrator, registration, shipping-instruction, value-added-service, rates, all six `lambda/*` |
| `1.0.29-SNAPSHOT` | visibility |
| `1.0.28-SNAPSHOT` | watermill-publisher (`watermill-commons`) |
| `1.0.27-SNAPSHOT` | auth, network, tx-tracking, db-migration |
| `1.0.26-SNAPSHOT` | webbl, self-service-reports |
| `1.R.01.025` (SDK v1 era) | oceanschedules, oceanschedules-process — out of scope |

Consequences:

1. **The bump is not uniform.** A module on `1.0.27` moving to `1.0.33` absorbs six releases of
   change, not one. The design's backward-compatibility guarantee covers all of them, but the *test*
   burden for auth/network/tx-tracking/webbl is a six-version jump, not a one-version jump.
2. **The modules that need Section A are already on `1.0.31`** — partner-integrator is the only
   in-repo consumer of the delay path, and it is one release behind. That is the cheapest possible
   upgrade path.
3. **The modules that benefit most from Section B are the ones furthest behind.** watermill-publisher
   (`1.0.28`) has the blanket `catch (RuntimeException)`; visibility (`1.0.29`) has the duplicated
   classifier. Both need a two-to-five-version jump to realise the benefit.
4. Nothing forces a big-bang. Because every change is additive, modules can adopt `1.0.33`
   independently and in any order, and a module that never bumps is unaffected.

### 16.5 Section A — the delay gap: who actually needs it

Direct AWS SDK v2 `SqsClient`/`SnsClient` usage in main sources exists in exactly **two** in-scope
modules, for **two different reasons**:

| Module | File | Why it bypasses `MessagingClient` | Fixed by |
| --- | --- | --- | --- |
| partner-integrator | `pi-commons/.../messaging/SQSClient.java` | **Delay on send** — javadoc states the gap explicitly | **Section A (S1)** |
| watermill-publisher | `watermill-commons/.../sqs/SQSListenerClient.java`, `SqsQueueMessage.java` | **System attributes on receive** (`ApproximateReceiveCount`) — javadoc claim is **stale** | **Nothing to build — already shipped in `1.0.32`.** Pure upgrade debt; see §16.8 |

Plus the wiring that exists only to support them:

- `partner-integrator/pi-si-out-processor/.../SIFeedApplicationInjector.java:140` — `provideSqsClient()`, javadoc: *"retained for the per-message delay send path that the cloud-sdk …"*
- `partner-integrator/pi-statusevents-out-processor/.../SEFeedApplicationInjector.java:147` — identical
- `watermill-publisher/watermill-booking`, `watermill-booking-aperak`,
  `watermill-cargo-visibility-subscription` — three `sqsListenerClient()` providers, all for the
  receive path

**`partner-integrator/pi-commons/SQSClient` is a second, independent reproduction of the exact
aw-bridge pattern** (and, after the §16.8 retraction, the *only* live case in mercury-services of a
module holding a raw `SqsClient` because the abstraction genuinely cannot express something), written by a different team on a different module, with javadoc naming the same
missing capability. That is the strongest possible evidence that S1 is a genuine platform gap and not
an aw-bridge quirk. It is the single most important input to the "should we do this" decision.

Two qualifications that *lower* the urgency:

1. **The delay path has no production caller in-repo.** `sendMessage(String, String, int)` in
   `pi-commons` is exercised only by `SQSClientTest` (10 assertions). `AbstractTask` exposes
   `protected SQSClient sqs`, so a subclass *could* call it, but none does today. Migration is
   therefore a low-risk change to dead-ish infrastructure, not a change to a hot path.
2. **The existing implementation clamps only the lower bound** — `.delaySeconds(Math.max(0, delay))`
   at `SQSClient.java:52`. It has no 900-second upper clamp, so a delay above the SQS maximum reaches
   AWS and fails there. The design's `SendMessageOptions` validation (§3, `MAX_DELAY_SECONDS = 900`,
   throwing `IllegalArgumentException`) is **stricter** than today's behaviour: a caller passing
   1200 currently gets an AWS-side error and would afterwards get a client-side
   `IllegalArgumentException`. That is a better failure, but it is a *behavioural change* on
   migration, and it belongs in the migration note. It is not a breakage of the commons contract,
   because no such caller exists.

**Section A migration shape.** Each module defines its own copy of a 2-arg
`@FunctionalInterface MessageSender` — four identical copies, in `partner-integrator/pi-commons`,
`watermill-commons`, `oceanschedules`, `oceanschedules-process`. Adding delay to `MessageSender`
would ripple across all of them. It is not necessary: `pi-commons/SQSClient` already exposes the
delay method as a *concrete class* method outside the interface, and `AbstractTask` and
`OutboundProcessor` inject the concrete `SQSClient`, not `MessageSender`. So the migration is:

```java
// after 1.0.33 — pi-commons/SQSClient, delay path
public void sendMessage(String target, String content, int delay) {
    try {
        messagingClient.sendMessage(target, content, Math.max(0, delay));
    } catch (MessagingException ex) {
        throw new RecoverableException(ex);
    }
}
```

…which deletes the `SqsClient` field, the constructor parameter, both `provideSqsClient()`
providers, and the `software.amazon.awssdk.services.sqs` imports from a module that should not have
them. `MessageSender` is untouched.

### 16.6 A hazard the design under-specifies: `default` methods on `QueueMessage` and `EventPublisher`

§9.2 assessed accidental-override risk for `MessagingClient` and found it acceptable. That is
correct — but `MessagingClient` is not the only cloud-sdk-api interface, and the other two **do** have
hand-written implementors outside commons:

| Interface | External implementors found |
| --- | --- |
| `MessagingClient` | **none** (all consumers compose; all 12 test doubles are Mockito `mock(MessagingClient.class)`) |
| `QueueMessage` | `watermill-commons/.../sqs/SqsQueueMessage.java:21`, `booking-cargoscreen/.../sqs/CargoScreenQueueMessage.java:20`, `libs/atlantida/.../SimpleQueueMessage.java:12` |
| `EventPublisher` | `booking/.../SNSEventPublisher.java:12`, `booking/.../DummyEventPublisher.java:11`, `booking-bridge/.../SNSEventPublisher.java:13`, `booking-cargoscreen/.../EmptyEventPublisher.java:11`, `visibility/.../EmptyEventPublisher.java:11`, `libs/atlantida/.../LoggingDummyEventPublisher.java:21`, `oceanschedules-process/.../SNSEventPublisher.java:12` |

**Implication for design principle P2.** P2 ("new interface methods are `default`") is currently
justified as good hygiene. For `QueueMessage` and `EventPublisher` it is a **hard requirement**: seven
hand-written `EventPublisher` implementations and three `QueueMessage` implementations exist outside
commons, and any non-`default` addition to either interface is an immediate compile break across
booking, booking-bridge, booking-cargoscreen, visibility, watermill-publisher and libs.

Section B as designed does not add methods to either interface, so **there is no impact today**. But
P2 should be restated as a rule with the reason attached, because the next SNS change is likely to
want a method on `EventPublisher`.

One additional fragility worth noting: `libs/atlantida/.../SimpleQueueMessage.java:12` declares
`implements QueueMessage` — **raw type**, no type argument. Raw-typed implementors are the ones most
likely to break on a generic signature change, and it sits in `libs`, which everything depends on.

### 16.7 Section B — exception changes, call site by call site

**Catches naming `MessagingException`.** Four modules define their *own* class with that name, so a
textual grep massively over-reports. Disambiguated by import:

| Site | Which `MessagingException` | Impact |
| --- | --- | --- |
| `partner-integrator/pi-commons/SQSClient.java:32` — `catch (MessagingException \| SdkException ex)` | **ours** (`cloudsdk.messaging.exception`, imported at line 7) | **The only production catch of our type in the repo.** Still compiles and still behaves identically after re-parenting: `MessagingException` and `SdkException` remain disjoint (`CloudSdkException extends RuntimeException`; `SdkException` is a separate hierarchy), so the multi-catch stays legal. |
| `booking/.../common/messaging/MessagingException.java` + its test | **local class**, own hierarchy | none |
| `webbl/.../common/messaging/MessagingException.java` + its test | **local class** | none |
| `oceanschedules-process/.../messaging/MessagingException.java` + its test | **local class**, SDK v1 module | none |
| `partner-integrator/pi-commons/.../messaging/MessagingException.java` | **local class**, unused by `SQSClient` (which imports ours) | none |
| `libs/email-sender/RawEmailSender.java:244` | **`javax.mail.MessagingException`** (import line 20) — checked, unrelated | none |

The `pi-commons` case deserves emphasis because it is precisely the shape the design is meant to
eliminate: the module catches `SdkException` — an AWS type — in application code, which is exactly
what §7's abstraction exists to prevent. After Section B it collapses to a single
`catch (MessagingException ex)`, because `SqsMessagingClient` will already have wrapped the
`SdkException`. **That is the clearest demonstration of Section B's value in the repository.**

**Blanket `catch (RuntimeException)` around messaging.** One site, in a high-volume module:

```java
// watermill-publisher/watermill-commons/.../sqs/SQSClient.java:21-29
public void sendMessage(String target, String content) {
    try {
        messagingClient.sendMessage(target, content);
    } catch (RecoverableException ex) {
        throw ex;
    } catch (RuntimeException ex) {          // <-- catches NullPointerException too
        throw new RecoverableException(ex);
    }
}
```

This is verbatim the anti-pattern the reviewer described when commissioning Section B: *"we also need
to be able to retry and classify as recoverable for SdkException and not catch blanket
RuntimeException which would include null pointers etc as well."* Today a `NullPointerException` from
a converter bug is re-labelled `RecoverableException` and retried forever. After Section B:

```java
} catch (MessagingException ex) {
    if (ex.isRetryable()) {
        throw new RecoverableException(ex);
    }
    throw ex;                                 // deterministic failure — fail fast, do not redeliver
}
```

No other `catch (RuntimeException)` in the repo sits on a messaging path — the remaining 30-odd are
lambda `HandlerSupport` top-level guards, DAO wrappers, resource-layer handlers, and
`watermill-commons/s3/S3WorkspaceService` (storage, 9 sites). None is affected.

**E4 (SNS `SnsService` catch widening) — blast radius zero.** The only SNS exception handling outside
commons is `oceanschedules/.../util/sns/SNSClient.java`, which imports `com.amazonaws.SdkClientException`
and `com.amazonaws.services.sns.AmazonSNS` — **SDK v1**. E4 cannot reach it. `SnsExceptionHandler`
itself has no callers outside commons, so E3's return-type narrowing (§8.6) is invisible to every
application.

**E5 (`receiveMessages(String,int,int)` gains try/catch) — 8 call sites, all safe.**

| Module | File |
| --- | --- |
| tx-tracking | `ReprocessService.java` (2 calls) |
| visibility | `visibility-commons/.../sqs/SqsMessageHandler.java` |
| partner-integrator | `pi-commons/.../SQSListenerClient.java`, `pi-commons/.../listener/sqs/SQSListener.java` |
| booking-cargoscreen | `.../processor/sqs/SqsMessageHandler.java` |
| booking | `.../common/messaging/SQSClient.java` |
| booking-bridge | `.../common/messaging/SQSClient.java` |
| webbl | `.../common/messaging/SQSClient.java` |

None of these wraps the call in `catch (SdkException)` or `catch (SqsException)`, so converting a raw
AWS exception into a `MessagingException` at that boundary changes nothing any of them observes.
The remaining v2 AWS-exception catches in the repo are all **storage**:
`partner-integrator/.../S3WorkspaceService`, `self-service-reports/.../S3Service`,
`watermill-commons/.../s3/S3WorkspaceService`. E5 does not touch storage.

**`changeMessageVisibility` — zero call sites in mercury-services.** The visibility-timeout work
motivating finding B4 is entirely an `aw-bridge` concern. No mercury application calls it today, so
nothing here is affected by it and nothing here needs to migrate for it.

**Tests that will need review (not repair).** Two suites construct our `MessagingException` directly
and assert classification behaviour:

- `booking-cargoscreen/.../SqsMessageHandlerSuppressionTest.java:218,225,232,265` — builds
  `new MessagingException(msg, AbortedException)`, `(msg, InterruptedException)`,
  `(msg, IllegalStateException)` and asserts suppression. All four constructors are retained by
  §7, so these **compile and pass unchanged**. But they encode the current classification, and once
  `isRetryable()` exists the suite should be extended to assert the new verdicts — otherwise the
  module's behaviour and the platform's classifier can silently diverge.
- `visibility/.../WMEventProcessorTest.java:503,550` and `RetryClassifierTest.java:169` — same
  situation, and directly relevant to §16.9.

### 16.8 Retracted finding — "S3" (SQS system attributes) is **not** a gap; it shipped in 1.0.32

An earlier draft of this section proposed a third gap, **S3 — `receiveMessages` cannot request SQS
system attributes**, on the strength of this javadoc in watermill-publisher:

```java
// watermill-publisher/watermill-commons/.../sqs/SQSListenerClient.java:28-43
 * The cloud-sdk {@code MessagingClient} cannot request SQS system attributes, so the listener receive path
 * uses the AWS SDK v2 {@link SqsClient} directly and adapts each result to the cloud-sdk
 * {@link QueueMessage} contract.
```

**That claim is stale, and the proposed gap does not exist.** Verification against the actual
`1.0.32-SNAPSHOT` sources shows the capability is present and wired end to end:

| Layer | Evidence at `1.0.32-SNAPSHOT` |
| --- | --- |
| Options object | `ReceiveMessageOptions` declares `private final List<String> messageSystemAttributeNames` (line 23) with a documented builder setter (lines 87–99) that null-coalesces to empty |
| SQS implementation | `SqsMessagingClient.receiveMessages(ReceiveMessageOptions)` lines 239–240: `if (options.getMessageSystemAttributeNames() != null && !…isEmpty()) { requestBuilder.messageSystemAttributeNamesWithStrings(options.getMessageSystemAttributeNames()); }` |
| Result surfacing | `convertToQueueMessage` → `new SqsMessage<>(message, payload)`; `SqsMessage.getAttributes()` lines 70–77 maps `sqsMessage.attributes()` (keyed by `MessageSystemAttributeName`) into `Map<String,String>` via `k.toString()` |

The commit that introduced all three is:

```
ea154df  2026-08-21  ION-12310: close cloud-sdk gaps for mft-s3-aqua-appia aw-bridge; bump to 1.0.32-SNAPSHOT
```

— i.e. the **same** gap-closing commit that added `changeMessageVisibility` and
`QueueMessage.getMessageAttributes`. System attributes were closed as part of that aw-bridge work.

**Why the javadoc says otherwise.** watermill-publisher is pinned at **`1.0.28-SNAPSHOT`**
(§16.4) — four releases behind. The statement was *true when written*, against the version that
module compiles against. It has simply not been revisited since `1.0.32` shipped.

**Consequences.**

1. **Nothing is added to `1.0.33` for this.** There is no API to design, no method to add, no
   compatibility question to answer. The capability a consumer needs is already released.
2. **watermill-publisher's workaround is now pure redundancy, not a necessary bypass.** Its
   hand-written `SqsQueueMessage.getAttributes()` (lines 45–51) does *exactly* what
   `SqsMessage.getAttributes()` already does — iterate `message.attributes()` and key by
   `k.toString()`. The semantics are equivalent.
3. **The §16.5 conclusion is narrowed but not weakened.** After this retraction there is exactly
   **one** live instance of "a module holds a raw `SqsClient` because the abstraction cannot express
   something": `partner-integrator`, for delay (S1). The other one, aw-bridge, is the same gap. The
   watermill case is now "a module holds a raw `SqsClient` because it has not upgraded yet" — a
   migration item, not a design input.
4. **watermill's migration gets larger and better.** On bumping `1.0.28` → `1.0.33` it can delete
   `SQSListenerClient`, `SqsQueueMessage`, and all three `sqsListenerClient()` providers, replacing
   the whole thing with:

   ```java
   messagingClient.receiveMessages(ReceiveMessageOptions.builder()
           .queueUrl(queueUrl)
           .waitTimeSeconds(waitTimeSeconds)
           .maxMessages(maxNumberOfMessages)
           .messageSystemAttributeNames(List.of("ApproximateReceiveCount"))
           .build());
   ```

   The cargo-visibility retry framework keeps reading `ApproximateReceiveCount` from
   `QueueMessage.getAttributes()` exactly as it does today.

**Method note.** This retraction is the direct result of checking the claim against source rather
than accepting a javadoc comment as a statement of current fact. A comment records what was true at
the version its author compiled against; in a repository spanning six commons versions (§16.4) that
is not the same as what is true now. The verification commands are logged as step I in §16.11.

### 16.9 The `visibility` interaction, in full

This is the one part of the assessment that is not a simple yes/no, so it is set out from first
principles. It concerns a single class:

`visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/processor/RetryClassifier.java`

#### 16.9.1 What `RetryClassifier` is

`visibility` consumes SQS messages and must decide, when processing a message fails, whether to let
the message be **redelivered** (retry) or to **finalise** it as permanently failed. That decision is
centralised in one static predicate:

```java
public static boolean isReprocessible(final Throwable throwable)
```

It is the same question `AwsFailureClassifier` (§8.3) is designed to answer — *is this failure worth
retrying?* — which is why the two must be reasoned about together rather than built in isolation.

`RetryClassifier` is more elaborate than the classifier proposed in §8.3, in two structural ways:

- **It walks the whole cause chain.** `causeChain(throwable)` unrolls `getCause()` and the classifier
  examines every link, returning on the first link that yields a verdict. §8.3's
  `AwsFailureClassifier.isRetryable` inspects a **single** `Throwable`.
- **It applies domain policy before technical classification.** Two guards run ahead of everything
  else: `containsNonReprocessible(causeChain)` (a failure at or after database persistence must never
  be replayed, however transient it looks) and `containsPermanentPayloadFailure(causeChain)`.

Beyond that it covers the same AWS v2 surface the design proposes — `SdkServiceException`
short-circuiting both ways, `isThrottlingException()`, `isClockSkewException()`, HTTP ≥ 500 and 429,
`SdkClientException` as retryable — plus cases §8.3 does not have: AWS SDK **v1** throttling matched
by class simple-name, `NetworkServicesException`, `WebApplicationException` by HTTP status, and
explicit socket-level exceptions (`SocketTimeoutException`, `ConnectException`, `UnknownHostException`,
`NoRouteToHostException`).

#### 16.9.2 Point one — it independently confirms the §8.3 correction, and solves it better

§14 step 10 records a defect in the first draft of `AwsFailureClassifier`: an arm reading

```java
if (t instanceof java.io.IOException || t instanceof InterruptedException) { return true; }
```

That arm is wrong because `JsonProcessingException extends JacksonException extends java.io.IOException`.
A message whose payload cannot be deserialised is **poison** — deterministic, identical on every
delivery — but it would be classified retryable and redelivered forever. The fix applied in §8.3 was
to **delete the arm**.

`RetryClassifier` hit the same trap and fixed it differently, with the reasoning left in the code:

```java
// A payload that cannot be deserialised is poison; no amount of redelivery will fix it.
// This must be evaluated before the IOException rule because JsonProcessingException extends IOException.
if (containsPermanentPayloadFailure(causeChain)) {
    return false;
}
…
if (throwable instanceof IOException) {
    return Boolean.TRUE;        // genuine socket IO — still retryable
}
```

Worked comparison, on two inputs:

| Input | §8.3 as written (arm deleted) | `RetryClassifier` (ordered guard) |
| --- | --- | --- |
| `JsonProcessingException` — corrupt payload | `false` ✅ (falls through to the final `return false`) | `false` ✅ (caught by the poison-payload guard) |
| A bare `IOException` from a socket that the SDK did **not** wrap | `false` ⚠️ — safe, but the message is finalised when a retry would have succeeded | `true` ✅ — retried |

Both are safe: neither produces the infinite-retry storm. But **visibility's is strictly more
capable** — it preserves the correct behaviour for genuine network IO instead of sacrificing it to
avoid the Jackson subclass. The ordering guard is what makes that possible.

**Recommendation for §8.3:** adopt visibility's shape rather than the deletion. Restore the
`IOException` arm, and place an explicit poison-payload check ahead of it:

```java
public static boolean isRetryable(Throwable t) {
    // Deterministic payload failures are poison. Must precede the IOException arm, because
    // JsonProcessingException extends JacksonException extends java.io.IOException.
    if (t instanceof com.fasterxml.jackson.core.JacksonException) {
        return false;
    }
    if (t instanceof SdkClientException) { return true; }
    if (t instanceof SdkServiceException sse) { … }
    if (t instanceof SdkException sdke) { return sdke.retryable(); }
    if (t instanceof java.io.IOException) { return true; }   // genuine socket IO
    return false;
}
```

This is a change to §8.3 and should be reviewed as such; it is recorded here rather than applied
silently.

#### 16.9.3 Point two — Section B creates a latent semantic conflict in this class

This is the part of the summary that needs the most unpacking, so it is walked through step by step.

**Today.** `RetryClassifier.classify` contains:

```java
if (throwable instanceof MessagingException) {
    return Boolean.TRUE;          // unconditionally retryable
}
```

That line is a **reasonable heuristic given today's constraints**. `MessagingException` currently
carries no information about *why* the messaging call failed — that is precisely finding **E1**. Faced
with an opaque exception, visibility assumes the worst-case-safe answer: retry. Since `SqsMessagingClient`
wraps genuine AWS failures in `MessagingException`, and genuine AWS failures are usually transient,
the heuristic is right most of the time.

**What Section B changes.** After §7, `MessagingException extends CloudSdkException` and carries
`isRetryable()`, computed by `AwsFailureClassifier` at the point of wrapping — where the *original*
AWS exception is still in hand and can be classified accurately. So `MessagingException` stops being
opaque.

**Why the line then becomes wrong.** `SqsMessagingClient.receiveMessages` wraps its failures in a
`catch (Exception e)` (line 258). That catch is deliberately broad, so it wraps **more than AWS
failures** — including a `NullPointerException` thrown inside `messageConverter.fromString(...)` when
a payload has an unexpected shape. Trace that failure through both worlds:

| Step | Today (1.0.29) | After Section B, **if the line is left as-is** | After Section B, **with the line fixed** |
| --- | --- | --- | --- |
| Converter throws `NullPointerException` | — | — | — |
| `SqsMessagingClient` wraps it | `MessagingException(cause=NPE)` | `MessagingException(cause=NPE)`, `isRetryable() == false` | same |
| `RetryClassifier.classify` sees it | `instanceof MessagingException` → `TRUE` | `instanceof MessagingException` → `TRUE` — **the accurate verdict is computed and then ignored** | consults `isRetryable()` → `false` |
| Outcome | Message redelivered forever; the same NPE recurs on every delivery | **Identical — no improvement whatsoever** | Message finalised; the poison message stops circulating |

The crucial and easily-missed point: **this is not a break, and not a regression.** Column two is
byte-for-byte the same behaviour as column one. Nothing fails to compile; no test changes colour;
production behaviour on the version bump is unchanged.

What it means is subtler and, for a high-volume module, more important:

> **In `visibility`, Section B delivers exactly zero benefit until one line changes.** The platform
> computes an accurate retryability verdict and hands it over, and the application throws it away.

The fix is one line, in visibility, after the bump:

```java
// before
if (throwable instanceof MessagingException) {
    return Boolean.TRUE;
}

// after — the platform has already classified this accurately; trust it
if (throwable instanceof MessagingException messagingException) {
    return messagingException.isRetryable();
}
```

Two consequences that must be planned for, because this **is** a deliberate behaviour change in a
high-volume production module — the only one in the whole assessment:

- `RetryClassifierTest.java:169` asserts
  `isReprocessible(new MessagingException("queue unavailable")) == true`. A `MessagingException`
  constructed with a message and **no cause** has nothing to classify. §7 must therefore specify the
  no-cause default explicitly, and the safe choice is `isRetryable() == true` — preserving today's
  behaviour and keeping this test green. **This is an open question for §7 that the sweep surfaced,
  and it is listed in §12.**
- `WMEventProcessorTest.java:503,550` stub `doThrow(new MessagingException("SNS unavailable"))` and
  assert retry behaviour. Same situation, same resolution.

Sequencing follows directly: **bump first, change the line second, as two separate commits.** The
bump is provably behaviour-preserving; the line change is a deliberate behavioural change that
deserves its own review and its own test evidence.

#### 16.9.4 Point three — the two classifiers should layer, not compete

The existence of a mature `RetryClassifier` raises a fair design question: *should
`AwsFailureClassifier` simply be visibility's classifier, promoted into commons?*

**No.** They operate at different layers and should keep different scopes:

| | `AwsFailureClassifier` (commons, §8.3) | `RetryClassifier` (visibility) |
| --- | --- | --- |
| Layer | Platform | Application |
| Input | A **single** `Throwable`, at the moment `SqsMessagingClient` wraps it | A `Throwable` **cause chain**, at the message-processing boundary |
| Knows about | AWS SDK v2 exception semantics, and nothing else | Persistence boundaries, poison payloads, JAX-RS status codes, `NetworkServicesException`, AWS SDK **v1** |
| Question answered | "Was this AWS call a transient failure?" | "Should *this message* be redelivered?" |
| Correct home | commons — every consumer needs it | visibility — the policy is domain-specific |

Promoting `RetryClassifier` wholesale would drag JAX-RS, SDK v1 and visibility's persistence policy
into cloud-sdk-api, violating design principle **P5** (no foreign types in the API surface) and
burdening every other consumer with visibility's domain rules.

The right relationship is compositional, and it is what the fix in §16.9.3 produces:

```
SqsMessagingClient catches SdkException
        │
        ├─ AwsFailureClassifier.isRetryable(e)   ← platform: "was the AWS call transient?"
        │
        └─ throws MessagingException(cause=e, retryable=…)
                    │
                    ▼
        RetryClassifier.isReprocessible(t)       ← application: "redeliver this message?"
           ├─ persistence guard        (domain policy — commons must not know this)
           ├─ poison-payload guard     (domain policy)
           ├─ MessagingException → isRetryable()   ← consults the platform verdict
           └─ everything else          (SDK v1, JAX-RS, sockets)
```

Each layer answers the question it is actually equipped to answer. `AwsFailureClassifier` stays
narrow — which is also what makes it cheap to review and safe to depend on.

### 16.10 Implementation sequence

Confirmed with the reviewer: **the partner-integrator and watermill-publisher refactors will be
pushed once `1.0.33` lands**, since both modules are currently in QA.

| Step | Work | Modules | Type | Notes |
| --- | --- | --- | --- | --- |
| **1** | Release `1.0.33` — Section A (S1 delay) + Section B (E1–E6 exceptions), as PR1 and PR2 per §10 | commons | additive | No consumer action required. `japicmp` gate against released `1.0.32` per §11.3. |
| **2** | Migrate **partner-integrator** `1.0.31` → `1.0.33` | pi-commons, pi-si-out-processor, pi-statusevents-out-processor | refactor | Route the delay path through `MessagingClient`; delete the `SqsClient` field and constructor arg, both `provideSqsClient()` providers, the `software.amazon.awssdk.services.sqs` imports, and collapse `catch (MessagingException \| SdkException)` to `catch (MessagingException)`. Note the new 900s upper-bound validation (§16.5). |
| **3** | Migrate **watermill-publisher** `1.0.28` → `1.0.33` | watermill-commons + 3 app injectors | refactor | **Two independent wins.** (a) Delete `SQSListenerClient`, `SqsQueueMessage` and all three `sqsListenerClient()` providers, replacing them with `ReceiveMessageOptions.messageSystemAttributeNames(List.of("ApproximateReceiveCount"))` — available since `1.0.32`, see §16.8. (b) Replace the blanket `catch (RuntimeException)` in `SQSClient.sendMessage` with `catch (MessagingException)` + `isRetryable()`. Five-version jump — budget regression time. |
| **4** | Merge **aw-bridge** on `1.0.33` | mft repo | refactor | Removes the second dual-client instance; the original motivation for this design. |
| **5** | Migrate **visibility** `1.0.29` → `1.0.33` — **bump only, no behaviour change** | visibility-commons | additive | Provably behaviour-preserving. Ship and observe. |
| **6** | **Separately**, change `RetryClassifier` to consult `MessagingException.isRetryable()` | visibility-commons | **behaviour change** | The only deliberate behavioural change in the plan. Own PR, own review, own tests. Update `RetryClassifierTest:169` and `WMEventProcessorTest:503,550`. Depends on the §7 no-cause default (§12). |
| **7** | Extend `SqsMessageHandlerSuppressionTest` to assert the new classification verdicts | booking-cargoscreen | test-only | Compiles and passes unchanged today; extend so module and platform cannot silently diverge. |
| **8** | Opportunistic bumps | booking, booking-bridge, booking-cargoscreen, lambda ×6, registration, shipping-instruction, value-added-service, rates (all `1.0.31`) | additive | No action needed; bump when convenient. |
| **—** | **No action required, ever** | auth, network (zero messaging/notification usage); webbl, tx-tracking, self-service-reports (unaffected paths); oceanschedules, oceanschedules-process (AWS SDK v1) | — | — |

Critical-path note: steps 2, 3 and 4 are mutually independent and can proceed in parallel once
`1.0.33` is published. Step 6 must follow step 5, and must not be folded into it.

### 16.11 Command log — how the footprint was established

Moved to **[2026-08-29-sqs-gaps-design-command.md](./2026-08-29-sqs-gaps-design-command.md) → §16.11**.

That is the largest of the three logs: steps A–I covering the whole `mercury-services` sweep,
each command given in `git grep` form with the idiomatic `rg` / `find` / `awk` / `sed`
equivalent alongside, and the syntax of each explained. Step I is the verification that
produced the §16.8 retraction. The caveats on the method — what a static textual sweep cannot
see — are stated at the end of that section and still apply to every claim in §16.

---

## 17. Consolidated summary

Everything in this document in one place: every finding, where it is designed, whether it ships in
`1.0.33`, and what each consumer must do.

### 17.1 Master findings table

Severity is *impact if left unfixed*. "Ships in" is the release that closes it.

| ID | Finding | Layer | Severity | Resolution | Ships in | Designed in |
| --- | --- | --- | --- | --- | --- | --- |
| **S1** | `MessagingClient` cannot set `DelaySeconds` | `cloud-sdk-api` | **High** — forces two modules to hold a raw `SqsClient` | New `SendMessageOptions` + two `default` overloads on `MessagingClient` | **1.0.33** | §3–§6 |
| **S2** | No FIFO fields (`MessageGroupId`, `MessageDeduplicationId`) reachable | `cloud-sdk-api` | Low — no consumer today | Reserved slots on `SendMessageOptions`; not implemented | deferred | §4.5 |
| ~~**S3**~~ | ~~`receiveMessages` cannot request SQS system attributes~~ | — | — | **RETRACTED — not a gap.** Shipped in `1.0.32` (commit `ea154df`); the watermill javadoc asserting otherwise is stale at `1.0.28` | already released | §16.8 |
| **E1** | `MessagingException` carries no retryability signal | `cloud-sdk-api` | **High** — forces blanket `catch (RuntimeException)` downstream | New `CloudSdkException` base with `isRetryable()`, `getOperation()`, `getResource()` | **1.0.33** | §7, §8.3 |
| **E2** | No common cloud-sdk exception supertype; six unrelated `extends RuntimeException` | `cloud-sdk-api` | Medium | Introduce `CloudSdkException`; re-parent `MessagingException` (binary-safe, JLS §13.4.4) | **1.0.33** | §7 |
| **E3** | `SnsExceptionHandler` returns raw `RuntimeException` | `cloud-sdk-aws` | **High** — no SNS abstraction at all | New `NotificationException`; **keep** the declared return type, narrow only the *runtime* type | **1.0.33** | §8.6 |
| **E4** | `SnsService` catches only `SnsException`; `SdkClientException` escapes raw | `cloud-sdk-aws` | **High** — AWS types leak to clients | Widen catch to `Exception` — *deliberate behavioural change*, blast radius verified zero | **1.0.33** | §8.6, §9.3 |
| **E5** | `receiveMessages(String,int,int)` has no `try/catch` — the one unwrapped method | `cloud-sdk-aws` | Medium | Route through the shared handler — *deliberate behavioural change*, 8 call sites verified safe | **1.0.33** | §8, §16.7 |
| **E6** | `SnsService` javadoc references a `CloudSdkException` type that does not exist | `cloud-sdk-aws` | Cosmetic | Resolved for free by E2 | **1.0.33** | §7 |
| **B2** | Two independently-built `SqsClient` instances in `aw-bridge` (sender + listener) | `aw-bridge` | Medium — also means **two independent retry-token buckets**, so two uncoordinated circuit breakers | Consolidate onto one `MessagingClient` once S1 lands | consumer, post-1.0.33 | §6, §15.4 |
| **B4** | A failed `changeMessageVisibility` silently consumes a message | `aw-bridge` | **High** — silent data loss | `isRetryable()` lets the consumer classify it recoverable, so the message is redelivered rather than dropped | consumer, post-1.0.33 | §8, §15.4 |

Two additional items surfaced by the impact sweep that are **not** numbered findings but do require action:

| Item | Where | Action |
| --- | --- | --- |
| `RetryClassifier` discards the retryability verdict Section B computes (`instanceof MessagingException → TRUE`) | `visibility-commons` | One-line change, **own PR after the bump** — the only deliberate behavioural change in a high-volume module | 
| P2 (`default` methods) is a *hard* requirement, not hygiene: `EventPublisher` has **7** and `QueueMessage` has **3** hand-written implementors outside commons | `cloud-sdk-api` | Restate P2 with the reason attached; no code change today | 

### 17.2 Where to find each part of the argument

| Section | Contents |
| --- | --- |
| §1–§2 | Gap inventory and design principles P1–P7 |
| **§3–§6** | **SECTION A** — `SendMessageOptions`, the `default` overloads, the SQS implementation, consumer adoption |
| **§7–§8** | **SECTION B** — `CloudSdkException`, `MessagingException` re-parenting, `AwsFailureClassifier`, the SNS half (E3/E4/E6) |
| §9 | Compatibility analysis — overload resolution, binary compatibility, rejected alternatives, SDK version floor |
| §10–§11 | Release plan and test plan (incl. `japicmp`/`revapi` gate) |
| §12–§13 | Open questions; new and changed files |
| §14 | Investigation log for §1–§13, including three recorded corrections — **[moved to the command document](./2026-08-29-sqs-gaps-design-command.md)** |
| §15 | Appendix — how AWS SDK v2 retries internally; why `isRetryable()` is not double plumbing |
| **§16** | **Impact assessment across `mercury-services`** — footprint, version pins, call sites, the S3 retraction (§16.8), the `visibility` interaction in full (§16.9), and the implementation sequence (§16.10). The command log (§16.11) is **[in the companion document](./2026-08-29-sqs-gaps-design-command.md)** |
| §17 | This summary |

### 17.3 Implementation sequence at a glance

Full detail, with per-module notes, is in **§16.10**.

```
   ┌─ 1. Release 1.0.33 ─────────────────────────────────────────────┐
   │    PR1 = Section A (S1)      PR2 = Section B (E1–E6)            │
   │    japicmp gate vs released 1.0.32                              │
   └──────────────────────────┬──────────────────────────────────────┘
                              │  (2, 3 and 4 are independent — run in parallel)
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  2. partner-integrator  3. watermill-publisher  4. aw-bridge
     1.0.31 → 1.0.33        1.0.28 → 1.0.33         merge on 1.0.33
     delete dual client     (a) delete stale        remove 2nd dual
     + 2 providers              listener workaround     client instance
     + catch(SdkException)  (b) fix blanket
                                catch(RuntimeException)
        ┌───────────────────────────────────────────┐
        ▼                                           
  5. visibility 1.0.29 → 1.0.33   ── bump only, provably behaviour-preserving
        │
        ▼
  6. visibility RetryClassifier → consult isRetryable()
        ── SEPARATE PR. The only deliberate behaviour change. Own review, own tests.

  7. booking-cargoscreen — extend suppression tests (test-only)
  8. booking, booking-bridge, lambda ×6, registration, shipping-instruction,
     value-added-service, rates — opportunistic bumps, no action needed

  No action ever: auth, network (zero messaging/notification usage);
                  webbl, tx-tracking, self-service-reports (unaffected paths);
                  oceanschedules, oceanschedules-process (AWS SDK v1).
```

**Confirmed with the reviewer:** the partner-integrator and watermill-publisher refactors (steps 2
and 3) will be pushed once `1.0.33` lands, as both modules are currently in QA.

### 17.4 The three things a reviewer should decide

1. **§8.3 classifier shape.** Adopt `visibility`'s ordering guard (poison-payload check *before* an
   `IOException` arm) instead of the current deletion of that arm? Visibility's form is strictly more
   capable — it still retries genuine socket IO. See §16.9.2.
2. **§7 no-cause default.** What should `new MessagingException("msg")` — no cause, nothing to
   classify — report from `isRetryable()`? Recommended: `true`, preserving today's behaviour and
   keeping `RetryClassifierTest:169` green. See §16.9.3.
3. **E4/E5 behavioural changes.** Both are deliberate, and the sweep verified their blast radius is
   zero across mercury-services (§16.7). Confirm and proceed?
