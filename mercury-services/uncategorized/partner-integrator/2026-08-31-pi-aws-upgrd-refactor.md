# ION-16417 — partner-integrator: SQS delay via cloud-sdk, align with commons 1.0.33-SNAPSHOT

**Date:** 2026-08-31
**Branch:** `feature/ION-16417-pi-aws-upgr-refactor`
**Modules:** `pi-commons`, `pi-si-out-processor`, `pi-statusevents-out-processor` (+ reactor-wide version bump)
**Related docs:** `docs/2026-0825-pi-refactor-pr-fix.md`, `docs/2026-08-20-pi-awsupgrade-refactoring.md`

---

## 1. Summary

`SQSClient` kept a raw AWS SDK 2.x `SqsClient` alongside the cloud-sdk `MessagingClient` purely to
serve the per-message delay send. commons **1.0.33-SNAPSHOT** exposes a delay overload on
`MessagingClient`, so the raw client is no longer needed: the delay path now routes through the
cloud-sdk like every other send, and the second AWS client — plus the two Guice providers that built
it — is gone.

| Change | Where |
|---|---|
| Drop the `SqsClient` field, constructor argument and its imports | `pi-commons` `SQSClient` |
| Route the delay send through `messagingClient.sendMessage(target, content, delay)` | `pi-commons` `SQSClient` |
| Collapse `catch (MessagingException \| SdkException)` to `catch (MessagingException)` | `pi-commons` `SQSClient` |
| Remove `provideSqsClient()` and the now-unused `SqsClient` import | `SIFeedApplicationInjector`, `SEFeedApplicationInjector` |
| `mercury.commons.version` `1.0.31-SNAPSHOT` → `1.0.33-SNAPSHOT` | `partner-integrator/pom.xml` |
| Rewrite the `SQSClient` test suite around the single-client shape | `pi-commons` `SQSClientTest` |

After the change, `software.amazon.awssdk.services.sqs.SqsClient` no longer appears anywhere in
`partner-integrator`, and `SQSClient` matches the single-dependency shape the other services already
use (`booking`, `booking-bridge`, `watermill-publisher`, `webbl`).

---

## 2. Behaviour change: the accepted delay range

This is the one caller-visible difference and it is worth stating plainly.

| | Before | After |
|---|---|---|
| Lower bound | `Math.max(0, delay)` — a negative delay was silently rewritten to `0` | rejected with `IllegalArgumentException` |
| Upper bound | not checked locally — AWS rejected it at the service | rejected locally with `IllegalArgumentException` |
| Accepted range | effectively `(-∞, ∞)` locally, `[0, 900]` at the service | `[0, 900]`, both bounds inclusive |

The new bound comes from the cloud-sdk (`SendMessageOptions.MAX_DELAY_SECONDS == 900`), which
validates in its `Builder.delaySeconds(int)` and therefore applies before any network call. An
out-of-range delay is a caller error, so it surfaces as `IllegalArgumentException` rather than being
wrapped as a retryable `RecoverableException` — the wrapping is reserved for `MessagingException`,
i.e. genuine messaging failures.

**Blast radius:** none today. The three-argument `SQSClient.sendMessage` has no production call site
in the repo — the only callers were the tests. Nothing was relying on the negative-delay clamp.

### 2.1 Why `catch (SdkException)` could go

The cloud-sdk translates transport failures into `MessagingException` before they reach the caller,
so with the raw `SqsClient` gone there is no longer any path that can surface a bare
`SdkException` from these two methods. A non-`MessagingException` runtime exception now propagates
unwrapped instead of being relabelled as recoverable — covered by tests in §4.

---

## 3. The diff

### 3.1 `pi-commons` — `SQSClient.java`

```diff
--- a/partner-integrator/pi-commons/src/main/java/com/inttra/mercury/common/messaging/SQSClient.java
+++ b/partner-integrator/pi-commons/src/main/java/com/inttra/mercury/common/messaging/SQSClient.java
@@ -6,9 +6,6 @@ import com.google.inject.name.Named;
 import com.inttra.mercury.cloudsdk.messaging.api.MessagingClient;
 import com.inttra.mercury.cloudsdk.messaging.exception.MessagingException;
 import lombok.extern.slf4j.Slf4j;
-import software.amazon.awssdk.core.exception.SdkException;
-import software.amazon.awssdk.services.sqs.SqsClient;
-import software.amazon.awssdk.services.sqs.model.SendMessageRequest;
 
 
 @Slf4j
@@ -16,20 +13,17 @@ import software.amazon.awssdk.services.sqs.model.SendMessageRequest;
 public class SQSClient implements MessageSender {
 
     private final MessagingClient<String> messagingClient;
-    private final SqsClient sqsClient;
 
     @Inject
-    public SQSClient(@Named("amazonSQSForSender") MessagingClient<String> messagingClient,
-                     SqsClient sqsClient) {
+    public SQSClient(@Named("amazonSQSForSender") MessagingClient<String> messagingClient) {
         this.messagingClient = messagingClient;
-        this.sqsClient = sqsClient;
     }
 
     @Override
     public void sendMessage(String target, String content) {
         try {
             messagingClient.sendMessage(target, content);
-        } catch (MessagingException | SdkException ex) {
+        } catch (MessagingException ex) {
             throw new RecoverableException(ex);
         }
     }
@@ -37,22 +31,14 @@ public class SQSClient implements MessageSender {
     /**
      * Sends a message with a per-message delay.
      *
-     * <p>The cloud-sdk {@link MessagingClient} has no per-message delay parameter (its 3-arg overload
-     * carries message attributes, not a delay), so this path uses the AWS SDK 2.x {@link SqsClient}
-     * built from the same cloud-sdk messaging configuration to preserve the legacy
-     * {@code SendMessageRequest.delaySeconds} behaviour.
+     * <p>The delay is validated by the cloud-sdk against the SQS range [0, 900]; an out-of-range
+     * delay is a caller error and surfaces as {@link IllegalArgumentException}, not as a
+     * {@link RecoverableException}.
      */
     public void sendMessage(String target, String content, int delay) {
         try {
-            // AWS SQS only accepts a delay in [0, 900]; normalise a negative delay to 0 so the request
-            // is always valid (the SDK would otherwise reject it with a validation error).
-            SendMessageRequest request = SendMessageRequest.builder()
-                    .queueUrl(target)
-                    .messageBody(content)
-                    .delaySeconds(Math.max(0, delay))
-                    .build();
-            sqsClient.sendMessage(request);
-        } catch (SdkException ex) {
+            messagingClient.sendMessage(target, content, delay);
+        } catch (MessagingException ex) {
             throw new RecoverableException(ex);
         }
     }
```

### 3.2 `pi-si-out-processor` — `SIFeedApplicationInjector.java`

```diff
@@ -42,7 +42,6 @@ import com.inttra.mercury.sifeed.outprocessor.dao.SIDao;
 import com.inttra.mercury.sifeed.outprocessor.processor.OutboundProcessor;
 import io.dropwizard.core.setup.Environment;
 import lombok.extern.slf4j.Slf4j;
-import software.amazon.awssdk.services.sqs.SqsClient;
 
 import java.time.Clock;
 
@@ -131,16 +130,6 @@ public class SIFeedApplicationInjector extends AbstractModule {
         return MessagingClientFactory.createDefaultStringClient();
     }
 
-    /**
-     * The AWS SDK 2.x {@link SqsClient} retained for the per-message delay send path that the cloud-sdk
-     * {@code MessagingClient} does not expose (design R5); default region and credentials provider.
-     */
-    @Provides
-    @Singleton
-    public SqsClient provideSqsClient() {
-        return SqsClient.create();
-    }
-
     @Provides
     @Singleton
     public StorageClient provideStorageClient() {
```

### 3.3 `pi-statusevents-out-processor` — `SEFeedApplicationInjector.java`

Identical removal (import at line 47, provider at lines 141–150):

```diff
@@ -44,7 +44,6 @@ import com.inttra.mercury.sefeed.outprocessor.processor.OutboundProcessor;
 import com.inttra.mercury.visibility.common.model.containerEvent.ContainerEvent;
 import io.dropwizard.core.setup.Environment;
 import lombok.extern.slf4j.Slf4j;
-import software.amazon.awssdk.services.sqs.SqsClient;
 
 import java.time.Clock;
 
@@ -138,16 +137,6 @@ public class SEFeedApplicationInjector extends AbstractModule {
         return MessagingClientFactory.createDefaultStringClient();
     }
 
-    /**
-     * The AWS SDK 2.x {@link SqsClient} retained for the per-message delay send path that the cloud-sdk
-     * {@code MessagingClient} does not expose (design R5); default region and credentials provider.
-     */
-    @Provides
-    @Singleton
-    public SqsClient provideSqsClient() {
-        return SqsClient.create();
-    }
-
     @Provides
     @Singleton
     public StorageClient provideStorageClient() {
```

The removed binding was unreferenced after §3.1 — nothing else in `partner-integrator` injects
`SqsClient` — so both Guice graphs still resolve (proved by the boots in §5).

### 3.4 `partner-integrator/pom.xml`

```diff
@@ -16,7 +16,7 @@
 
     <properties>
         <maven.compiler.release>17</maven.compiler.release>
-        <mercury.commons.version>1.0.31-SNAPSHOT</mercury.commons.version>
+        <mercury.commons.version>1.0.33-SNAPSHOT</mercury.commons.version>
         <aws.lambda.events.version>3.14.0</aws.lambda.events.version>
         <jackson-bom.version>2.21.4</jackson-bom.version>
     </properties>
```

One property drives `commons`, `cloud-sdk-api`, `cloud-sdk-aws` and `dynamo-integration-test` for
every PI module.

---

## 4. Tests — `SQSClientTest` (39 tests, rewritten)

The suite is organised by method and covers both the accepted (inclusive) and the rejected
(exclusive) side of every boundary.

| Group | Coverage |
|---|---|
| Construction | non-null; still a `MessageSender` |
| `sendMessage(target, content)` | delegation; distinct queue URLs; distinct, empty, `null` and 42 KB bodies; never touches the delay overload; `MessagingException` → `RecoverableException` (cause preserved); a non-`MessagingException` propagates unwrapped |
| `sendMessage(target, content, delay)` routing | routes to the cloud-sdk delay overload and *not* the two-argument one; `0`, `900` and `-1` handed over verbatim (no local clamp); `MessagingException` → `RecoverableException`; non-`MessagingException` unwrapped; mixed send sequence counts per overload |
| Accepted delay range (inclusive) | `0`, `1`, `60`, `899`, `900` — each accepted, with target, content and `getDelaySeconds()` asserted |
| Rejected delay range (exclusive) | `-1`, `-60`, `Integer.MIN_VALUE`, `901`, `1000`, `Integer.MAX_VALUE` — each `IllegalArgumentException`, with the assertion that **nothing was sent** |
| Bound provenance | `SendMessageOptions.MAX_DELAY_SECONDS == 900`, and that constant accepted while `+ 1` is rejected — the test tracks the SDK rather than a hard-coded literal |
| Error classification | an out-of-range delay is **not** wrapped as `RecoverableException`; a `MessagingException` raised from the real default method **is** |
| `deleteMessage` | delegation; distinct queue URLs and receipt handles; repeated calls; `MessagingException` propagates unwrapped (that method has no try/catch) |

### 4.1 Why the range tests need a real `MessagingClient`

`sendMessage(String, T, int)` is an **interface `default` method** on `MessagingClient` — it builds a
`SendMessageOptions` (where the `[0, 900]` validation lives) and delegates to the
`SendMessageOptions` overload. Mockito stubs default methods like any other, so against a plain
`@Mock` the validation never runs and every out-of-range delay would appear to succeed.

The suite therefore uses two doubles deliberately:

* the **Mockito mock** for delegation and exception mapping — what `SQSClient` itself does;
* a small real implementation, `RecordingMessagingClient`, for the range tests — it implements only
  the `SendMessageOptions` overload (recording target, content and options) and leaves the `default`
  delay method in place, so the cloud-sdk's own validation actually executes.

---

## 5. Verification

| Check | Command | Result |
|---|---|---|
| `pi-commons` unit tests | `mvn -f partner-integrator/pom.xml -pl pi-commons clean test` | **1254 tests, 0 failures** (`SQSClientTest`: 39) |
| Full PI reactor, all modules | `mvn -f partner-integrator/pom.xml clean install` | **BUILD SUCCESS**, all 8 modules, tests green on 1.0.33-SNAPSHOT |
| Config validation, all 5 DW apps | `java -jar <app>.jar check conf/int/config.yaml` | `Configuration is OK` (exit 0) for `pi-si-out`, `pi-statusevents-out`, `pi-booking`, `pi-si-in`, `pi-bl-in` |
| Real boot of the two touched apps | `java -jar <app>.jar server conf/int/config.yaml` | `Started application@…{0.0.0.0:8080}` + `Started admin@…{0.0.0.0:8081}`, no Guice `CreationException` |

The `server` boots are the check that matters for §3.2–3.3: Dropwizard's `check` command validates
the YAML but never builds the injector, so only a real boot proves the Guice graph still resolves
with the `SqsClient` binding removed. Both apps reached the Jetty connectors and were then stopped.

> Note: an offline (`-o`) full-reactor run fails in `pi-booking-processor` at
> `maven-dependency-plugin:get` for `com.inttra.mercury:booking:jar:3.0.0.M`, which lives in the
> module's file-based `lib/` repo. That is a pre-existing offline-mode limitation, unrelated to this
> change — the online run above is clean.
