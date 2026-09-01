# ION-16380 — watermill-publisher: S3 `NoSuchKey` investigation, commons 1.0.33 alignment, SQS/SNS refactor

**Date:** 2026-08-31
**Branch:** `feature/ION-16380-wm-refactor`
**Modules:** `watermill-commons`, `watermill-booking`, `watermill-booking-aperak`, `watermill-cargo-visibility-subscription`
**Follows:** `32608bbccb` — *ION-16380: watermill-publisher AWS SDK 2.x (cloud-sdk) upgrade*
**Related docs:** `docs/2026-06-30-watermill-publisher-aws2x-DESIGN-claude.md`, `docs/2026-06-30-watermill-publisher-current-state-DESIGN-claude.md`

---

## 1. The reported issue

Reported from INT (Teams screenshot, 2026-08-31 09:31):

```
INFO  [...] c.i.m.w.booking.task.WatermillBKTask  : Processing workflowId :6f595959-0369-4e01-93d3...
INFO  [...] c.i.m.w.commons.sqs.DeadLetterService : Moving SQS Message to DLQ -293f537e-f956-4214...
INFO  [...] c.i.m.w.commons.sqs.DeadLetterService : Moving SQS Message to DLQ -c886a5af-6ab2-48cd...
ERROR [...] c.i.m.c.s.impl.AbstractStorageObject  : Message : The specified key does not exist. (
software.amazon.awssdk.services.s3.model.NoSuchKeyException: The specified key does not exist.
        (Service: S3, Status Code: 404 ...)
ERROR [...] c.i.m.w.booking.task.WatermillBKTask  : Exception in Watermill publisher
software.amazon.awssdk.services.s3.model.NoSuchKeyException: The specified key does not exist. ...
```

Two things about the screenshot are worth correcting up front, because both make the failure look
worse than it is:

* **It is not a startup failure.** Jetty had already started (`Started application@…`, `Started
  admin@…`) and the listener was processing queue messages. The 404 happens on the S3 read for a
  specific message, well after boot.
* **The raw AWS exception is not leaking.** The INT `config.yaml` log format ends in `%rEx{3}`,
  which is logback's *root-cause-first* renderer. It prints `NoSuchKeyException` at the top and the
  wrapping exceptions after it. The wrapper was always there; the format just hides it behind the
  3-line-per-frame cap.

---

## 2. Root cause — and the answer to "is this a bug introduced by the upgrade?"

**No. The `NoSuchKeyException` itself is not a regression from the AWS SDK 2.x upgrade.**
It is a genuine data condition — the S3 object named by the SQS message no longer exists in
`inttra-int-workspace` — combined with a **pre-existing poison-message loop** that predates the
upgrade. Two further problems in the same area turned up while tracing it. All three are fixed
here.

### 2.1 Why the error repeats forever (the actual defect, pre-existing)

`DeadLetterService` does not move messages *to* the DLQ, despite its log line saying so. It reads
the **`<queue>_dlq`** and writes back to the **live pickup queue** — a redrive, running every 30
minutes:

```java
new DeadLetterService(sqsListener, sqsSender,
        pickupSqsConfig.getQueueUrl() + "_dlq",   // sourceQueue  == the DLQ
        pickupSqsConfig.getQueueUrl());           // targetQueue  == the live queue
```

Meanwhile `WatermillBKTask` rethrew **every** S3 failure:

```java
} catch (Exception e) {
    log.error("Exception in Watermill publisher", e);
    throw new RuntimeException(e);      // message is never deleted
}
```

So a message pointing at a deleted S3 object went round this cycle indefinitely:

```
pickup queue → 404 → rethrow → not deleted → redelivered ×5 (maxReceiveCount)
             → redrive policy parks it in _dlq
             → DeadLetterService pushes it back to the pickup queue 30 min later
             → 404 → …
```

That is exactly the screenshot: two `DeadLetterService` redrive lines immediately followed by
repeated `NoSuchKeyException`s. `watermill-booking` and `watermill-booking-aperak` had **no**
permanent-vs-transient classification at all.
(`watermill-cargo-visibility-subscription` already had one — `RetryClassifier` +
`ReprocessibleException`, added under ION-16235 — which is why only the booking publishers were
reported.)

This behaved identically before the upgrade, so it is **not** an upgrade regression — but it is the
reason the operator saw the same error over and over.

#### Was this already happening pre-upgrade, and was it silent?

**It was already happening, and it was never silent.** The pre-upgrade code logged the failure at
ERROR on every single delivery attempt, and logged the DLQ redrive too. The distinction is therefore
*not* "silent before, logged after" — it is **"logged forever and never resolved" versus "logged
once, resolved and reported"**.

The word *silent* does apply, but on a different axis: the loop was silent in **workflow terms**.
Nothing ever classified the failure as permanent, nothing emitted a terminal event, nothing ended it.
Monitoring and downstream never saw a resolution — only the same ERROR reappearing every 30 minutes,
indefinitely. Loud in the log, silent in the workflow.

Under AWS SDK v1 a 404 arrived as `AmazonS3Exception`, which extends `AmazonServiceException` — a
*sibling* of `SdkClientException` under `AmazonClientException`, not a subclass. So it slipped past
`catch (SdkClientException | UnableToReadS3Object)` untouched and surfaced at exactly one place:

```java
} catch (Exception e) {
    log.error("Exception in Watermill publisher", e);   // AmazonS3Exception, status 404
    throw new RuntimeException(e);
}
```

The upgrade changed the *signature* of the failure, not its behaviour:

| | pre-upgrade (AWS SDK v1) | post-upgrade, before this fix | after this fix |
|---|---|---|---|
| ERROR lines per attempt | 1 — from `WatermillBKTask` | **2** — cloud-sdk's `AbstractStorageObject` logs its own, then rethrows | 1, and only once |
| exception shown | `AmazonS3Exception` (404) | `NoSuchKeyException` → `S3OperationException` | same, wrapped in `NonRecoverableException` |
| logging class in the line | `c.i.m.w.booking.task.WatermillBKTask` | also `c.i.m.c.s.impl.AbstractStorageObject` — a name nobody had seen before | `WatermillBKTask` |
| message deleted? | no | no | **yes** |
| retried indefinitely? | **yes** | **yes** | **no** |
| terminal failure event? | no | no | **yes** (SNS) |

The cloud-sdk logs the failure itself *and* rethrows it, so every 404 produced a duplicate ERROR with
a stack trace from an unfamiliar logger. Combined with `%rEx` printing the raw AWS exception at the
top (section 1), a long-standing condition acquired a brand-new signature — which is why it was read
as a new defect.

One honest caveat: the *code path* is unchanged, but the *trigger* may well be recent. These
messages only became poison once their S3 objects disappeared from `inttra-int-workspace`. If the
INT bucket has a lifecycle expiry, a batch of messages could have gone poison together well after
the upgrade shipped — which would explain why the report arrived when it did rather than in July.
Worth a glance at the bucket's lifecycle rules before concluding anything about timing.

### 2.2 Second finding — permanent failures were relabelled "recoverable"

AWS SDK v1 exception hierarchy made the distinction for us. `SdkClientException` is a *client-side*
failure; a 404 arrives as `AmazonS3Exception extends AmazonServiceException`, which is **not** an
`SdkClientException`. The v1 code therefore only wrapped transport failures:

```java
// BEFORE (AWS SDK v1)
} catch (SdkClientException | UnableToReadS3Object ex) {
    throw new RecoverableException(ex);          // a 404 propagated untouched
}
```

The migration replaced that with a blanket catch, because cloud-sdk collapses every S3 outcome into
`S3OperationException`:

```java
// AFTER the upgrade (cloud-sdk 1.0.28) — every failure is now "Recoverable"
} catch (RecoverableException | UnableToReadS3Object ex) {
    throw new RecoverableException(ex);
} catch (RuntimeException ex) {
    throw new RecoverableException(ex);
}
```

A permanent 404 is now labelled `RecoverableException`. That is a latent trap: `RetryClassifier`
treats `RecoverableException` as *authoritatively transient* and short-circuits on it, so the moment
a booking-style S3 failure reaches that classifier it becomes an infinite retry by construction.

### 2.3 Third finding — two `RecoverableException` types

The upgrade left `com.…commons.s3.RecoverableException` and `com.…commons.sqs.RecoverableException`
as separate classes. `RetryClassifier` imports only the **sqs** one, so the exception
`S3WorkspaceService` actually throws was never matched by the rule written for it. It happened to
reach the right verdict via the inner AWS exception — by luck, not by design.

---

## 3. What changed

### 3.1 Version bump to 1.0.33-SNAPSHOT

| Artifact | Before | After |
|---|---|---|
| `com.inttra.mercury:commons` | 1.0.28-SNAPSHOT | **1.0.33-SNAPSHOT** |
| `com.inttra.mercury:cloud-sdk-api` | 1.0.28-SNAPSHOT | **1.0.33-SNAPSHOT** |
| `com.inttra.mercury:cloud-sdk-aws` | 1.0.28-SNAPSHOT | **1.0.33-SNAPSHOT** |
| `com.inttra.mercury:dynamo-integration-test` (test) | 1.0.28-SNAPSHOT | **1.0.33-SNAPSHOT** |

Three cloud-sdk capabilities added since 1.0.28 are what make this refactor possible:

| New in 1.0.33 | Replaces |
|---|---|
| `ReceiveMessageOptions.messageSystemAttributeNames(List<String>)` | the direct AWS SDK v2 `SqsClient` in the listener |
| `StorageClient.getMetadata(bucket, key)` — a real `headObject` | the fetch-whole-object-and-close-the-stream workaround |
| `StorageClient.getContent(bucket, key, charset)` | manual `getObject` + `readAllBytes` + decode |

### 3.2 Removing the direct AWS 2.x `SqsClient`

`SQSListenerClient` existed only because cloud-sdk 1.0.28's `MessagingClient` could not request the
`ApproximateReceiveCount` SQS system attribute, which the retry framework needs to tell a first
delivery from a redelivery. It held a raw `SqsClient`, and `SqsQueueMessage` hand-adapted AWS
`Message` objects to the cloud-sdk `QueueMessage` contract.

cloud-sdk 1.0.33's `SqsMessagingClient` now passes `messageSystemAttributeNamesWithStrings(...)` to
the underlying request, and its `SqsMessage.getAttributes()` exposes system attributes keyed by
their SQS wire names (`"ApproximateReceiveCount"`) — byte-identical to what the hand-written adapter
produced. Both classes are therefore deleted.

**Verified:** no `software.amazon.awssdk.services.sqs` reference remains anywhere in
`watermill-publisher` outside javadoc and one test that constructs an `SqsException` fixture.

### 3.3 `SQSClient` → `SQSClientAdapter` — and yes, it is still needed

The question was whether the class still earns its keep now that `MessagingClient` does most of the
work. It does, but not in its old shape — the right move was to **merge** it with `SQSListenerClient`
rather than keep two clients:

| | before | after |
|---|---|---|
| send / delete | `SQSClient` (cloud-sdk `MessagingClient`) | `SQSClientAdapter` |
| receive | `SQSListenerClient` (raw AWS v2 `SqsClient`) | `SQSClientAdapter` |
| visibility timeout | `SQSClient` | `SQSClientAdapter` |
| AWS `Message` → `QueueMessage` | `SqsQueueMessage` | *(cloud-sdk does it)* |

Four reasons it stays rather than injecting `MessagingClient` directly:

1. It is the single place translating cloud-sdk `MessagingException`s into the recoverable /
   non-recoverable taxonomy the task and DLQ framework depend on.
2. It pins the receive request to `ApproximateReceiveCount` in one place, so no caller can forget it
   and silently break redelivery detection.
3. It turns the `VisibilityTimeout` queue attribute — a `Map<String,String>` lookup that can come
   back absent — into a typed value with a documented fallback (see §3.5).
4. It narrows the ten-method `MessagingClient` surface, which includes queue administration, to the
   four operations the publishers actually perform.

`MessageSender` is kept as the send-side port; `SQSClientAdapter` implements it.

DI is correspondingly simpler — one provider instead of two, and no `@Named` qualifiers:

```java
// BEFORE                                        // AFTER
@Named("amazonSQSForListener") SqsClient …       MessagingClient<String> sqsMessagingClient()
@Named("amazonSQSForSender")   MessagingClient…
```

### 3.3a Connection pooling and long polling after the client merge

The provider that was removed carried this comment:

```java
// These replace the two separately-built @Named("amazonSQSForListener"/"amazonSQSForSender") AmazonSQS
// instances; they must stay distinct so a blocking 20s long-poll receive cannot starve DLQ sends.
```

Collapsing two clients into one `MessagingClient` removes that separation, so the concern it describes
deserves a quantified answer rather than an assurance. Two questions: is long polling still honoured,
and can a 20-second poll now starve sends on the shared connection pool?

#### The tuning that is actually applied

`MessagingClientFactory.createDefaultStringClient()` builds its HTTP client from
`AwsHttpDefaults.syncBuilder()`, which sets these explicitly on an `ApacheHttpClient`:

| setting | value |
|---|---|
| `maxConnections` | **50** |
| `connectionTimeout` | 5 s |
| `socketTimeout` | **30 s** |
| `connectionAcquisitionTimeout` | 10 s |

#### Long polling is honoured

`socketTimeout` is 30 s and `waitTimeSeconds` is 20 s in every environment. The margin is not merely
configured, it is structural: the SQS API caps `WaitTimeSeconds` at 20, so a long poll can never
outlast a 30-second socket timeout regardless of what is put in `config.yaml`.

Confirmed on the live INT run, using `DeadLetterService` (which long-polls the DLQ):

```
20:05:05.255  Redriving messages from …_watermill_bk_dlq back to …_watermill_bk
20:06:08.364  DeadLetterService redrove 5 message(s)
```

63.1 seconds: five messages redriven quickly, then three empty polls before the drain stopped —
3 x 20 s = 60 s plus overhead. Had long polling been broken, those three polls would have returned
immediately and the run would have finished in well under a second.

#### Pool demand does not come close to starvation

Concurrent SQS callers in one JVM:

| caller | count | connection held for |
|---|---|---|
| SQS listener thread (long-poll receive) | **1** — `listenerThreads: 1` in int, qa, cvt and prod, across all three modules | up to 20 s |
| DLQ scheduler thread (`newScheduledThreadPool(1)`, every 30 min) | **1** | up to 20 s; its receive, send and delete run sequentially on that one thread, so never more than one connection |
| gRPC ack callbacks calling `deleteMessage` | a trickle, bounded by `maxNumberOfMessages: 3` in flight | sub-second |

Peak demand is therefore roughly two long-lived connections plus a few short ones, against a pool of
50 — about 4% utilisation. Starvation would require more than 50 concurrent in-flight SQS calls.

One detail matters here: `SQSListener.pollAndExecute` releases the connection when `receiveMessage`
*returns*, before dispatching the batch for processing. The poll therefore never holds a connection
across the slow gRPC publish that follows.

#### Was the old split protecting anything?

Not at these settings, and the comparison is the opposite of what the comment implies. The old
*listener* client was built as `SqsClient.builder().region(Region.US_EAST_1).build()` — raw AWS SDK
defaults, with none of the cloud-sdk tuning above. Only the sender had it. The merge therefore gives
the receive path *better*-defined tuning than it previously had, not worse, and unifies two divergent
configurations rather than creating a divergence.

#### Do the tuning parameters need to differ per environment?

No, and there is nothing to diverge. `SQSConfig` — the type behind `sqsPickupConfig` in every
`config.yaml` — exposes only `queueUrl`, `waitTimeSeconds` and `maxNumberOfMessages`. No HTTP or
client tuning appears in any environment config, before or after this change.

| | before | after |
|---|---|---|
| receive path | raw AWS SDK defaults, untuned | 50 connections, 5 s connect, 30 s socket, 10 s acquisition |
| send / delete path | cloud-sdk defaults, as above | same |

#### The one real trade, and the guardrail it needs

The merge does change something: two pools of 50 (partitioned) become one pool of 50 (shared). That
is irrelevant at `listenerThreads: 1`, but it introduces a coupling that did not exist before.

**`listenerThreads` must stay well below 50.** If it were raised toward that number, the long-polling
listener threads would occupy the shared pool and sends and deletes would begin waiting out the 10 s
`connectionAcquisitionTimeout` before failing. Revisit pool sizing before taking `listenerThreads`
above roughly 30; previously the listener had its own pool, so this ceiling did not apply.

If that ceiling ever becomes a live constraint, the fix is to size `maxConnections` from
`listenerThreads` in the provider rather than to reintroduce a second client — a second client would
bring back the two divergent tunings this change removed.

### 3.4 Exception handling — a real recoverable / non-recoverable split

New package `com.inttra.mercury.watermill.commons.exception`:

| Type | Meaning | Caller must |
|---|---|---|
| `RecoverableException` | transient — 5xx, throttling, transport, I/O | leave the message on the queue |
| `NonRecoverableException` | permanent — `NoSuchKey`, `NoSuchBucket`, `AccessDenied`, argument validation | **delete** the message, log a terminal failure event |
| `AwsFailureClassifier` | decides which, from the cause chain | — |

Deleted: `s3.RecoverableException`, `sqs.RecoverableException` (the duplicate pair from §2.3),
`s3.UnableToWriteToFile` and `task.UnrecoverableAWSException` (both dead code).

`AwsFailureClassifier` walks the cause chain (cycle-guarded, depth-capped at 25) and stops at the
first throwable that yields a verdict:

* `RecoverableException` / `NonRecoverableException` — an existing verdict short-circuits.
* `IllegalArgumentException` — cloud-sdk argument validation; fails identically every time.
* `CloudSdkException.isRetryable() == false` — the cloud-sdk's own verdict, populated for SQS and SNS,
  honoured only in the `false` direction (section 3.4a explains why `true` cannot be trusted).
* `AwsServiceException` — 5xx or 429 → transient; every other 4xx → permanent; plus an explicit
  throttling error-code allow-list and `isThrottlingException()` for 400-shaped throttles.
* Any other `SdkException`, `SocketTimeoutException`/`ConnectException`/`UnknownHostException`, or
  `IOException` → transient.
* **Default: permanent.** This matches the existing convention in `RetryClassifier` — a failure not
  positively recognised as transient is finalised and reported rather than looped forever.

Two design notes:

* **Why the AWS SDK types appear here.** The verdict needs the HTTP status code and AWS error code,
  which only `AwsServiceException` carries; the cloud-sdk wrapper preserves it in the cause chain but
  exposes no equivalent. The AWS coupling is deliberately confined to this one class — everything
  else in watermill stays on cloud-sdk abstractions.
* **Overlap with `RetryClassifier`.** They operate at different layers: `AwsFailureClassifier` at
  the cloud-sdk boundary (storage/messaging), `RetryClassifier` at the CVS task layer (also gRPC,
  JAX-RS, DynamoDB, network services). `RetryClassifier` gained one rule so the two agree:
  `NonRecoverableException` now short-circuits to *permanent*.

`S3WorkspaceService` classifies every operation and attaches the bucket and key to the message, so
the offending object is identifiable from the log line alone:

```
NonRecoverableException: S3 getContent failed for bucket=inttra-int-workspace key=watermill_…/4b2ed386-…
```

### 3.4a Does this work for S3, SQS *and* SNS? — and why the S3 exception classes were removed

Two review questions, answered from what cloud-sdk 1.0.33 actually does rather than from its release
notes. Everything below was verified by driving the real cloud-sdk handlers with synthetic AWS
exceptions and inspecting the results.

#### What 1.0.33 gives each service

The observation behind the question is correct: **1.0.33 added a structured exception model for SQS
and SNS, but not for S3.**

| | wrapper type | extends | `isRetryable()` | AWS cause preserved |
|---|---|---|---|---|
| SQS | `MessagingException` | `CloudSdkException` | **yes** — computed | yes |
| SNS | `NotificationException` | `CloudSdkException` | **yes** — computed | yes |
| S3 | `S3OperationException` | `RuntimeException` | **no such method** | yes |

`CloudSdkException` carries `isRetryable()`, `getOperation()` and `getResource()`.
`S3OperationException`, `S3UploadException` and `FileTransferException` extend plain
`RuntimeException` and carry none of it.

Measured verdicts:

| call | wrapper | `isRetryable()` |
|---|---|---|
| `SqsMessagingClient.handleException(403 AccessDenied)` | `MessagingException` | `false` |
| `SqsMessagingClient.handleException(503 ServiceUnavailable)` | `MessagingException` | `true` |
| `SqsMessagingClient.handleException(400 NonExistentQueue)` | `MessagingException` | `false` |
| `SnsExceptionHandler.handle(403 AuthorizationError)` | `NotificationException` | `false` |
| `SnsExceptionHandler.handle(503 ServiceUnavailable)` | `NotificationException` | `true` |

#### So will S3 still be classified properly? Yes — because the cause is always preserved

S3 has no retryability flag, so its verdict has to come from the wrapped AWS exception. All five
cloud-sdk S3 handlers were exercised, and **every one keeps the originating AWS exception as the
cause**:

| handler | wrapper | cause |
|---|---|---|
| `handleNoSuchKeyException` (404) | `S3OperationException` | `NoSuchKeyException` |
| `handleS3Exception` (503 SlowDown) | `S3OperationException` | `S3Exception` |
| `handleS3Exception` (403 AccessDenied) | `S3OperationException` | `S3Exception` |
| `handleSdkException` | `S3OperationException` | `SdkClientException` |
| `handleUnexpectedException` | `S3OperationException` | the original throwable |

`AwsFailureClassifier` reads the cause chain, so the missing S3 retryability model costs it nothing —
the HTTP status and AWS error code it needs are always reachable. This is precisely why the
classifier was built around the cause chain rather than around `isRetryable()`: had it been built on
the flag, S3 would have had no verdict at all and every S3 failure would have fallen through to the
default.

The live INT run confirms the full chain end to end:

```
NoSuchKeyException (404)
  wrapped by S3OperationException: Bucket inttra-int-workspace does not contain key watermill_…
  wrapped by NonRecoverableException: S3 getContent failed for bucket=… key=…
```

#### How the classifier uses the flag where it exists

`isRetryable()` is consulted for SQS and SNS, but **only a `false` is treated as authoritative**. The
reason is a trap worth recording: `CloudSdkException.isRetryable()` **defaults to `true`**.

```
new MessagingException("m")                              -> isRetryable = true
new MessagingException("m", cause)                       -> isRetryable = true
new MessagingException("m", cause, false, "op", "res")   -> isRetryable = false
```

A `true` therefore cannot be distinguished from "nobody set a verdict". Trusting it would recreate
exactly the mislabelling of section 2.2, one layer up. So:

* `isRetryable() == false` → **permanent, authoritative** (never a default).
* `isRetryable() == true` → **no opinion**; classification continues to the wrapped AWS exception,
  which decides.

The two-argument `MessagingException(String, Throwable)` constructor is deprecated in 1.0.33, which
corroborates that the flag-carrying constructor is the intended one.

#### Coverage across the three services

| path | classified? | permanent failure | transient failure |
|---|---|---|---|
| **S3** — `S3WorkspaceService`, all ten operations | yes, from the wrapped AWS exception | `NonRecoverableException` → task deletes the message and writes a terminal event | `RecoverableException` → message left for redelivery |
| **SQS** — `SQSClientAdapter`: send, delete, receive, queue attributes | yes, from `isRetryable()==false` then the wrapped AWS exception | `NonRecoverableException` | `RecoverableException` |
| **SNS** — `EventLogHandler` → `EventLogger` → `SnsService` | **deliberately not classified** | logged, swallowed | logged, swallowed |

#### Why SNS is deliberately excluded

SNS is used here only to publish workflow *audit* events, and `EventLogHandler.logEvent` always runs
**after** the SQS message has been finalised — from the success path in `ResponseObserver.onNext`
(message already deleted), or from a task's own catch block (message already deleted). There is
nothing left to retry and nothing left to leave on the queue.

Classifying an SNS failure would therefore be worse than useless. A transient `NotificationException`
escaping `logEvent` would propagate into the caller's outer handler, replace the real processing
outcome, and resurrect a message whose business work had already completed — republishing it to
watermill on the next delivery. Both transient and permanent SNS failures are therefore logged at
ERROR and swallowed: the audit event is lost, the message outcome is not corrupted. That is the right
trade for a side channel, and it is also why section 3.6 validates the topic ARN at *startup* — a
misconfigured topic is the one SNS failure worth failing loudly on, and startup is the place to do
it.

#### Why the S3 exception classes were removed

No S3 error *handling* was removed. One duplicate was merged and two never-referenced classes were
deleted:

| class | disposition | reason |
|---|---|---|
| `s3.RecoverableException` | **merged** into `exception.RecoverableException` | identical twin of `sqs.RecoverableException`; `RetryClassifier` imports only the sqs one, so the type S3 actually threw was invisible to the very rule written for it (section 2.3) |
| `sqs.RecoverableException` | **merged** into `exception.RecoverableException` | the other half of the same duplicate |
| `s3.UnableToWriteToFile` | **deleted** | zero references in any module, main or test — dead before the upgrade too |
| `task.UnrecoverableAWSException` | **deleted** | zero references; superseded by `NonRecoverableException`, which is actually thrown and handled |
| `s3.UnableToReadS3Object` | **kept** | still thrown by `read(InputStream)` when the object body cannot be drained |
| `s3.S3ObjectWrapper` | **kept** | unchanged return type of `getS3ObjectWrapper` |

The net effect on S3 is *more* error handling, not less: every operation now yields a classified
verdict where it previously yielded an unconditional "recoverable".

#### One cloud-sdk quirk found while verifying

`StorageClient.getMetadata(bucket, key)` returns an **empty map** when the *bucket* does not exist
rather than throwing — `AbstractStorageObject.handleNoSuchBucketException` returns normally instead of
raising. A missing *key* does throw correctly. No production code in watermill-publisher calls
`getMetaData`, so this is recorded rather than worked around, and noted in the method javadoc so a
future caller is not caught out.

### 3.5 Other correctness fixes in the same area

| Fix | Why |
|---|---|
| `getVisibilityTimeout` no longer does `Long.parseLong(map.get("VisibilityTimeout"))` on a possibly-null value | It threw `NumberFormatException` while *constructing* every `ResponseObserver`, i.e. at application start. Now falls back to the SQS default of 30s with a `WARN`. |
| `DeadLetterService` log lines say "Redriving … back to", not "Moving SQS Message to DLQ" | The old wording described the opposite of what the code does and sent readers hunting the wrong queue. |
| `DeadLetterService` contains a per-message failure | One bad message no longer aborts the whole drain; it stays in the DLQ for the next run. |
| `DeadLetterService` reports a redrive count and uses `isEmpty()` | Observability; `messages.size() > 0` replaced. |

None of these change which queue `DeadLetterService` reads from or writes to — see section 3.5a, which
answers that question directly, because the old log line makes it easy to conclude otherwise.

### 3.5a `DeadLetterService`: the direction of travel is unchanged

This came up in PR review and is worth recording, because the old log line invites exactly the wrong
reading: *"we used to move messages **to** the DLQ, and now we redrive **out** of it — is the
behaviour reversed?"*

**No. The direction is identical before and after.** Only the log wording changed.

The constructor arguments are the authority, and they are the same in both versions:

```java
new DeadLetterService(
        /* sourceQueue */ pickupSqsConfig.getQueueUrl() + "_dlq",   // the dead letter queue
        /* targetQueue */ pickupSqsConfig.getQueueUrl());           // the live pickup queue
```

and `run()` has always done, and still does:

| step | queue |
|---|---|
| `receiveMessage(sourceQueue, …)` | reads **from the DLQ** |
| `sendMessage(targetQueue, payload)` | writes **to the live pickup queue** |
| `deleteMessage(sourceQueue, receipt)` | removes **from the DLQ** |

So this class has always been a **redrive out of the DLQ**, on a 30-minute schedule. What it never
did was move anything *into* the DLQ.

The misleading line was:

```java
log.info("Moving SQS Message to DLQ -" + message.getMessageId());   // describes the opposite
```

It now reads `Redrove SQS message {} from {} to {}`, naming both queues so the direction cannot be
misread from a log again.

#### What actually moves messages *to* the DLQ

AWS does, not this code. The queue's own redrive policy parks a message in the DLQ once it has been
received `maxReceiveCount` times without being deleted:

```json
"RedrivePolicy": "{\"deadLetterTargetArn\":\"…inttra_int_sqs_watermill_bk_dlq\",\"maxReceiveCount\":5}"
```

That division of labour is what made the wrong log line survive so long: the class is *named*
`DeadLetterService`, so a line saying "Moving SQS Message to DLQ" looks plausible, and the half of the
cycle it actually performs is the half nobody was looking at.

It is also the second half of the loop described in section 2.1 — AWS parks the poison message, this
service pulls it straight back out 30 minutes later, and before this change nothing ever broke the
cycle.

#### What did change

Behaviour, deliberately, in three narrow ways — none of them the direction:

| change | reason |
|---|---|
| log wording: "Moving SQS Message to DLQ" → "Redrove SQS message {} from {} to {}" | the old text stated the opposite of the code and sent readers to the wrong queue |
| a failure on one message is caught and the drain continues; that message stays in the DLQ for the next run | previously one failed send or delete aborted the entire drain, stranding the remaining messages for 30 minutes |
| a redrive count is logged on completion, and `messages.size() > 0` became `isEmpty()` | observability; the run now states how many messages it moved |

The polling shape is unchanged: long-poll the DLQ at 20 s, up to 10 messages, stop after three
consecutive empty polls.

### 3.6 SNS semantics

* **Fail fast on the topic ARN.** `notificationService()` now validates `snsEventTopicArn` is present
  and is an `arn:aws:sns:…`. Previously a missing or malformed ARN surfaced hours later as a
  `NotificationException` from inside a task's error handler, where it read as a message-processing
  failure.
* **Event logging can no longer break message processing.** `EventLogHandler.logEvent` catches and
  logs `RuntimeException` instead of propagating. This mattered: `logEvent` is called *from the
  caller's own catch block, after the message has already been deleted* — so an SNS failure both
  replaced the real processing outcome and resurrected an already-finalised message.
* `EventPublisher → NotificationService` binding and `EventLogger`/`EventGenerator` JIT bindings were
  checked and are correct (both cloud-sdk classes carry `@Inject`/`@Singleton`); no change needed.

### 3.7 Task-level handling — the fix for the reported symptom

```java
} catch (NonRecoverableException e) {
    finalisePermanentFailure(message, metaData, e);   // log + delete + terminal failure event
} catch (Exception e) {
    log.error("Exception in Watermill publisher", e);
    throw new RuntimeException(e);                     // transient: leave for redelivery
}
```

Applied to `WatermillBKTask` and `WatermillBKAperakTask`. A permanent failure is now finalised
exactly as a transformation failure already was — deleted, with a terminal failure event — and the
rest of the batch continues. Transient failures still leave the message on the queue.

---

## 4. Behaviour change to be aware of at review

**A message whose S3 object is permanently unreadable is now deleted instead of being retried
forever.** That is the intended fix, but it is a real change in production message handling:

* Before: retried 5×, parked in the DLQ, redriven every 30 minutes, forever. Never processed, never
  reported as complete, and permanently noisy.
* After: one ERROR line naming the bucket and key, a terminal failure workflow event on SNS, message
  deleted.

The failure is *more* visible (it is now reported as a terminal failure rather than buried in an
endless retry), but the message is no longer recoverable by simply restoring the S3 object. If the
team would rather park these somewhere for inspection, the natural follow-up is a genuine
quarantine queue — not a return to the loop.

---

## 5. Files changed

**`watermill-commons`**

| | |
|---|---|
| added | `exception/RecoverableException.java`, `exception/NonRecoverableException.java`, `exception/AwsFailureClassifier.java`, `sqs/SQSClientAdapter.java` |
| deleted | `sqs/SQSClient.java`, `sqs/SQSListenerClient.java`, `sqs/SqsQueueMessage.java`, `sqs/RecoverableException.java`, `s3/RecoverableException.java`, `s3/UnableToWriteToFile.java`, `task/UnrecoverableAWSException.java` |
| modified | `s3/S3WorkspaceService.java`, `sqs/DeadLetterService.java`, `sqs/SQSListener.java`, `logging/EventLogHandler.java`, `pom.xml` |

**`watermill-booking` / `watermill-booking-aperak`** — injector (single `MessagingClient` provider,
SNS ARN validation), task (`finalisePermanentFailure`), `SQSClient` → `SQSClientAdapter` renames.

**`watermill-cargo-visibility-subscription`** — same injector changes, `RetryClassifier` learns
`NonRecoverableException`, `pom.xml` test-dependency bump.

---

## 6. Verification

### 6.1 Tests — full reactor green

```
watermill-commons ..................................  203 tests
watermill-booking ..................................  265 + 17 tests
watermill-booking-aperak ...........................  465 tests
watermill-cargo-visibility-subscription ............   29 tests
--------------------------------------------------------------
Tests run: 979, Failures: 0, Errors: 0, Skipped: 0    BUILD SUCCESS
```

New coverage:

* `AwsFailureClassifierTest` — permanent vs transient across `NoSuchKey`/`NoSuchBucket`/
  `AccessDenied`/validation/5xx/429/throttle-codes/transport, existing-verdict short-circuits, cause
  chain traversal (first-verdict-wins, self-referencing cause, depth cap), and wrapping. A
  `CloudSdkWrappers` group pins the contract from section 3.4a: an `S3OperationException` is
  classified from its wrapped AWS exception, a `false` `isRetryable()` is authoritative for
  SQS/SNS, and a `true` one does not override the wrapped AWS exception.
* `SQSClientAdapterTest` — including a test asserting the receive request actually carries
  `ApproximateReceiveCount`, and the four `VisibilityTimeout` fallback paths.
* `S3WorkspaceServiceTest` — rewritten for the new semantics; pins ISO-8859-1 round-tripping through
  the new `getContent(charset)` delegation and asserts `getMetaData` no longer fetches the body.
* `WatermillBKTaskTest` / `WatermillBKAperakTaskTest` — missing key deletes + logs a terminal event
  and does *not* throw; recoverable failure still leaves the message on the queue; one poison message
  does not stop the rest of the batch.

### 6.2 Live INT run — the reported failure, reproduced and fixed

All three modules booted against `conf/int/config.yaml` with INT credentials. Boot is clean (only
the pre-existing Jersey/logback-version warnings). `watermill-booking` picked up the very messages
from the report:

```
INFO  … WatermillBKTask   : Processing workflowId :6f595959-0369-4e01-93d3-5848ed4bf15e
INFO  … S3StorageClient   : Fetching file from S3: bucket='inttra-int-workspace', key='watermill_6f595959-…'
ERROR … WatermillBKTask   : Permanent failure for workflowId 6f595959-… (bucket=inttra-int-workspace,
                            file=watermill_6f595959-…); deleting the message instead of leaving it for redelivery
software.amazon.awssdk.services.s3.model.NoSuchKeyException: The specified key does not exist. … 404 …
Wrapped by: …cloudsdk.storage.exception.S3OperationException: Bucket inttra-int-workspace does not contain key …
Wrapped by: …watermill.commons.exception.NonRecoverableException: S3 getContent failed for
            bucket=inttra-int-workspace key=watermill_6f595959-…
…
INFO  … DeadLetterService : DeadLetterService redrove 5 message(s) from …_watermill_bk_dlq to …_watermill_bk
```

Queue depths before and after the run:

| Queue | before | after |
|---|---|---|
| `inttra_int_sqs_watermill_bk` | 0 visible (5 cycling via the DLQ) | **0** |
| `inttra_int_sqs_watermill_bk_dlq` | 5 | **0** |

The five poison messages that had been cycling were drained permanently. The loop is broken.

---

## 7. Follow-ups (not done here)

* `WorkspaceService` exposes ten methods; only `getContent(bucket, key, charset)` has a production
  caller — the rest are exercised only by tests. It was left intact (it mirrors the AWS v1 API other
  modules may still want), but it is a candidate for trimming.
* `AwsFailureClassifier` and CVS's `RetryClassifier` share their AWS-service-exception logic.
  Consolidating means moving `RetryClassifier` into `watermill-commons`, which currently drags in its
  `NetworkServicesException`, gRPC and JAX-RS dependencies. Deferred rather than forced.
* Worth raising with the commons team: `S3OperationException` extending `RuntimeException` rather
  than `CloudSdkException` means S3 is the only cloud-sdk service without `isRetryable()`. Every
  caller has to re-derive the verdict from the wrapped AWS exception, as this module now does. Two
  smaller items from the same investigation — `getMetadata` swallowing a missing bucket into an empty
  map (section 3.4a), and `CloudSdkException.isRetryable()` defaulting to `true` so a `true` cannot be
  distinguished from "unset" — are also worth feeding back.
* Verify the `inttra-int-workspace` lifecycle policy to confirm the timing hypothesis in section 2.1:
  whether these messages went poison as a batch when their objects aged out, rather than at the
  upgrade.
* `DeadLetterService`'s unconditional 30-minute DLQ→live redrive is safe now that permanent failures
  are finalised, but "redrive everything, forever" is still a blunt policy. A bounded redrive
  (attempt count or age) would be a better long-term shape.
