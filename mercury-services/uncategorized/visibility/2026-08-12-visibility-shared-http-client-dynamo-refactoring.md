# ION-16431 — Visibility Outbound Stall: HTTP Connection-Pool Death and DynamoDB Auto-Pagination

**Author:** Arijit Kundu (analysis) · **Date:** 2026-08-12
**Scope:** `mercury-services-commons` PR #46, #47, #48 · `mercury-services` PR #1165, #1166
**Related:** ION-16431 "SDK Upgrade | Outbound files are not triggering"
**Incident:** `visibility-outbound`, **2026-07-30 11:49 → 2026-08-04 12:12 UTC (~5 days)**, QA (account 642960533737)
**Status:** Root cause **confirmed at stack-frame level** against CloudWatch Logs — see §1.1.

> **Note on the stated incident window.** `incident-analysis-2026-08-04.md` gives the window as 2026-08-01 12:12 → 2026-08-04 11:11 (~71 h). CloudWatch shows that is the *tail* of the event, not the event. The failure began **2026-07-30 11:49:09** and ran for roughly **five days** across ~13 ECS task generations. The supplied CSV export starts at exactly `2026-08-01 12:12:02` because that is where the second spinning task's log stream ends — a query-window artefact, not the onset.

---

## 0. Executive Summary

| | |
|---|---|
| **What the team believes the cause was** | AWS service clients (S3 / SQS / DynamoDB) shared one HTTP connection pool; a DynamoDB `ApiCallTimeoutException` closed that shared pool and took S3 and SQS down with it. |
| **What the evidence actually shows** | The service clients did **not** share a pool, and no DynamoDB timeout was involved. The pools died because **`OutOfMemoryError` was thrown while HTTP requests were in flight**, and Apache HttpClient 4.x deliberately calls `connManager.shutdown()` in its `catch (Error)` handler. The OOM came from **DynamoDB Enhanced Client auto-pagination** — confirmed by a stack trace terminating in `EnhancedClientUtils.readAndTransformPaginatedItems` → `SubscriptionAttributeConverter.transformTo` → Jackson `ArrayList.grow`. |
| **Ordering (decisive)** | First `OutOfMemoryError` **11:49:09.608**; first `Connection pool shut down` **11:53:21.501** — the OOM precedes the pool death by **4 min 12 s**. The incident document has the arrow pointing the wrong way. |
| **True scale** | ~**65 million** log records emitted, sustained at **~464 records/second**. One task alone (`f360e23c7e67`) produced **37.2 million** records in 22.3 h. ECS restarted the task ~13 times; **every replacement re-hit the same OOM**, so restarts never recovered it. |
| **Net effect on the fixes** | Of the 5 PRs, **the DynamoDB `maxResultSize` change (PR #48 + #1166) is the real fix** — and the confirmed stack trace makes that unambiguous. The S3 "pool isolation" change (PR #46 + #1165) addresses a failure mode that did not occur, and mildly *increases* lifecycle coupling. The SQS backoff/circuit-breaker (PR #1165) is a genuine and valuable improvement but, as written, converts a loud failure into a **silent zombie service**. |
| **Overall verdict** | **Do not merge to the release line as-is.** The changes are directionally useful and safe to keep, but they do **not** close the incident holistically. Eleven defects remain open — see §6. Three are blocking (B-1, B-2, B-3). |

---

## 1. Evidence Base and Access Status

| Source | Status | Notes |
|---|---|---|
| `incident-analysis-2026-08-04.md` | ✅ Reviewed | Conclusions partially incorrect — corrected in §3. |
| `log-analytics-results-2026-08-04 (3).csv` | ✅ Reviewed in full | 10,000 error records / 665,090 physical lines / 77 MB. Parsed and classified programmatically. |
| Bitbucket PRs 46, 47, 48, 1165, 1166 | ✅ Retrieved | Via Bitbucket REST API + local git; full diffs reviewed. |
| Jira ION-16431 | ❌ **Not retrieved** | Jira SSO cookie expired (`401 Unauthorized` from `jira.dev.e2open.com`); `auth_reload` did not recover it. Re-run `sso_login.py` to refresh. Analysis proceeded from the files, PRs and CloudWatch as instructed. |
| **AWS CloudWatch Logs — log group `inttra2-ecs-logs`, streams `VisibilityOutbound-latest-qa/*`** | ✅ **Retrieved and queried** | SSO refreshed 2026-08-12. Retention is **400 days**, so the full 2026-07-28 → 2026-08-05 period is intact. ~875 M records scanned across the queries in §1.1. **This resolved the one open hypothesis and corrected the incident window, scale, and several conclusions.** |
| Apache HttpClient bytecode | ✅ Verified | `httpclient-4.5.14.jar` decompiled — see §3.2. |

**Caveat on the supplied CSV — now explained.** The export begins at exactly `2026-08-01 12:12:02.099` and carries only `@timestamp` and `@message` (no `@logStream`). CloudWatch shows why: `2026-08-01 12:12:05` is the **last event of task `f7f30dac8a4e`**, the second of two spinning tasks. The CSV is a 10,000-record sample of the *end* of a five-day event, which is why the incident document's window, duration, and error rate are all understated. Everything in §1.1 comes from CloudWatch directly, not the CSV.

### 1.1 CloudWatch validation (the queries that changed the conclusions)

**(a) The storm began 2026-07-30, not 2026-08-01.** Hourly `Connection pool shut down` counts, `VisibilityOutbound-latest-qa`:

```
2026-07-30 11:00      91          ← onset
2026-07-30 12:00   1,137,280
2026-07-30 13:00 → 2026-07-31 11:00   ~1.65–1.73 M per hour, sustained  (episode 1)
2026-07-31 12:00     316,678
2026-07-31 13:00 → 21:00    74–2,237  ← quiet: task replaced, backlog not yet re-hit
2026-07-31 22:00     522,506          ← episode 2 begins
2026-08-01 00:00 → 11:00   ~1.67–1.71 M per hour, sustained
2026-08-01 12:00     348,780          ← where the supplied CSV starts
```

**~1.7 M records/hour ≈ 464/second**, sustained for ~36 hours in total across two episodes — not the ~137/s I estimated from the CSV sample, and not confined to 71 hours.

**(b) The first `OutOfMemoryError` precedes the first pool death by 4 min 12 s.**

| Event | Timestamp | Thread |
|---|---|---|
| **First `OutOfMemoryError`** | **2026-07-30 11:49:09.608** | `pool-11-thread-1` (outbound DAO poller) |
| Second OOM | 2026-07-30 11:51:06.820 | `pool-11-thread-2` |
| Third OOM | 2026-07-30 11:53:21.511 | `pool-11-thread-13` |
| **First `Connection pool shut down`** | **2026-07-30 11:53:21.501** | `pool-11-thread-7`, in `ContainerEventOutboundDao` |
| Spin reaches full rate | 2026-07-30 12:13 → 25,000/min | `pool-14-thread-1` |

The first pool death lands in the **same second** as the third OOM. This is exactly the `catch (Error) → connManager.shutdown()` signature from §3.2, and it is the reverse of the incident document's claim that a DynamoDB timeout closed the pool.

**(c) The OOM stack trace — RC-A confirmed at frame level.** Full trace of the 11:49:09.608 event:

```
Exception in thread "pool-11-thread-1" java.lang.OutOfMemoryError: Java heap space
    at java.util.ArrayList.grow(...)
    at java.util.ArrayList.add(...)
    at com.fasterxml.jackson.databind.deser.std.CollectionDeserializer._deserializeFromArray(CollectionDeserializer.java:371)
    at com.fasterxml.jackson.databind.deser.std.CollectionDeserializer.deserialize(CollectionDeserializer.java:245)
    at com.fasterxml.jackson.databind.deser.BeanDeserializer.vanillaDeserialize(BeanDeserializer.java:302)
    at com.fasterxml.jackson.databind.ObjectMapper.readValue(ObjectMapper.java:3954)
    at com.inttra.mercury.visibility.common.model.containerEvent.converters
             .SubscriptionAttributeConverter.transformTo(SubscriptionAttributeConverter.java:56)   ← per-item JSON blob
    at software.amazon.awssdk.enhanced.dynamodb.internal.mapper.StaticAttributeType.attributeValueToObject(...)
    at software.amazon.awssdk.enhanced.dynamodb.mapper.StaticImmutableTableSchema.mapToItem(...)
    at software.amazon.awssdk.enhanced.dynamodb.internal.EnhancedClientUtils.readAndTransformSingleItem(EnhancedClientUtils.java:121)
    at software.amazon.awssdk.enhanced.dynamodb.internal
             .EnhancedClientUtils.lambda$readAndTransformPaginatedItems$0(EnhancedClientUtils.java:137)   ← ★ AUTO-PAGINATION
    at java.util.stream.ReferencePipeline$3$1.accept(...)
    at java.util.stream.ReduceOps$ReduceOp.evaluateSequential(...)
```

`readAndTransformPaginatedItems` **is** the Enhanced Client's auto-pagination path. This is not an inference from behaviour — the failing frame names the defect. Two amplifiers are visible in the same trace:

* **`SubscriptionAttributeConverter`** deserialises a JSON `Subscription` blob **per item** via Jackson, and the OOM lands inside `CollectionDeserializer` growing a nested `ArrayList`. Each record therefore costs far more than its DynamoDB wire size. See D-12.
* The whole thing runs inside a `ReduceOps` terminal operation — i.e. `collect(toList())` over every page, exactly as in §3.1.

**(d) ECS *did* restart the task — repeatedly — and it never helped.** Task generations during the incident:

```
ecb71e8f7d51  07-30 00:00 -> 07-30 11:18   11.30h        140,089 rec      3/s   (healthy)
a771bf30f4aa … 5d5ed05b6771   07-30 11:14 -> 11:17   five ~25 s tasks, 28 rec each  (deployment churn)
3c1d838acd34  07-30 11:17 -> 07-30 11:55    0.64h         65,947 rec     29/s   ← first OOM at 11:49
75d966e0c2fa  07-30 11:55 -> 07-30 12:12    0.28h          7,611 rec      8/s
f360e23c7e67  07-30 12:10 -> 07-31 10:26   22.26h     37,220,190 rec    464/s   ★ episode 1
07e5cfbd3690  07-31 10:27 -> 07-31 12:12    1.75h      2,911,055 rec    463/s
9f9b0ef414ee  07-31 12:10 -> 07-31 22:27   10.28h        240,091 rec      6/s   (quiet)
f7f30dac8a4e  07-31 22:26 -> 08-01 12:12   13.76h     22,936,453 rec    463/s   ★ episode 2 — CSV starts at its end
1bb4c617f3f7  08-01 12:10 -> 08-02 12:12   24.02h        194,552 rec      2/s
e825ccf4a705  08-02 12:11 -> 08-02 12:21    0.17h        415,082 rec    665/s
b3cb07209406  08-03 12:03 -> 08-03 12:20    0.28h        258,355 rec    253/s
46875821c7d4  08-03 12:21 -> 08-04 11:04   22.72h          1,636 rec      0/s
4b9642ddc1a9  08-04 11:03 -> 08-04 12:12    1.14h        766,752 rec    186/s
                                        TOTAL ≈ 65,000,000 records
```

This materially changes one of my earlier conclusions. **ECS was cycling tasks throughout** — ~13 generations. Restart was never the missing ingredient: each fresh task's poller re-ran the same unbounded query against the same backlog and OOM'd again within minutes. It also means the CloudWatch ingestion cost of this incident (~65 M records) was substantial in its own right.

*(This does not retire B-1 — a handler that stops while the process stays up is still a silent-failure mode — but it does reorder the priorities: the DynamoDB cap is the load-bearing fix, and "let the orchestrator restart it" is demonstrably not a recovery strategy for this class of failure. B-1 is re-scoped accordingly in §5.4.1.)*

### 1.2 Supplied CSV sample — measured error profile (10,000 records)

Retained because it is the artefact the incident document was written from, and because the service-vs-pool-shutdown breakdown below is still the cleanest single refutation of the shared-pool theory. Read it as a sample of the event's tail, not the event.


```
Classification            Count    Attributed AWS call
────────────────────────────────────────────────────────────────
PoolShutDown               9,438    sqs.receiveMessage  9,308
                                    s3.putObject           20
                                    sqs.deleteMessage      10
                                    (unattributed)        106
ApiCallTimeout               238    dynamodb.query        238
SocketTimeout                271    network services (geography/participant/IPF)
Crc32Mismatch                 32    dynamodb.query         32
OutOfMemoryError               1    thread pool-11-thread-12
ProvisionedThroughputExceeded  0    ← NOT PRESENT (see §6.3)
```

### 1.3 Supplied CSV sample — timeline by application clock

```
2026-08-01 12:12:02.099   FIRST visible record: SQS receiveMessage → "Connection pool shut down"
                          (window boundary — earlier events not exported)
2026-08-01 12:12:02–06    1,184 pool-shutdown records in ~4 s  ← spin burst #1
2026-08-01 12:12:06.707   FIRST DynamoDB ApiCallTimeoutException  ← 4.6 s AFTER the pool was already dead
2026-08-01 12:12–12:42    DynamoDB ApiCallTimeout ×66, Crc32Mismatch ×11; SQS handler largely quiet
2026-08-01 12:43:43.763   java.lang.OutOfMemoryError: Java heap space  in thread pool-11-thread-12
                          (pool-11 = the DynamoDB / ContainerEventOutboundDao poller pool)
2026-08-01 12:43:00–59    8,238 pool-shutdown records in one minute (~137/s)  ← spin burst #2
2026-08-02 12:12–12:21    68 ApiCallTimeout, 126 SocketTimeout — no SQS activity at all
2026-08-03 12:04–12:59    36 ApiCallTimeout, 142 SocketTimeout, 2 pool-shutdown
2026-08-04 11:04–11:11    67 ApiCallTimeout, 20 pool-shutdown (S3 putObject), 2 Crc32Mismatch
```

Two facts in this sample break the incident document's causal chain, and CloudWatch (§1.1) then confirmed both:

1. **The pool was already dead before the first DynamoDB timeout** — by 4.6 s within the sample, and by **4 min 12 s** measured against the true onset in CloudWatch. A DynamoDB timeout cannot have caused it.
2. **Within this sample, DynamoDB `query` never hit a dead pool** — 270 DynamoDB failures, zero of them `Connection pool shut down`, while SQS's and S3's pools were dead. *(Do not over-read this: CloudWatch shows DynamoDB's pool **was** destroyed on other tasks. The sample happens to cover two tasks in which only SQS died. The correct — and stronger — refutation of the shared-pool theory is the per-task variation in §3.3, not DynamoDB immunity.)*

Note also that the DynamoDB `ApiCallTimeoutException` and `Crc32MismatchException` bursts visible here recur at roughly the same time every day (12:0x–12:2x on 08-01, 08-02, 08-03, 11:0x on 08-04). They track a scheduled workload, not the incident, and they continued long after the pools were dead. They are background noise that the incident document mistook for the trigger.

---

## 2. What the Code Actually Does (pre-fix)

### 2.1 The clients are already isolated — there is no shared pool

Every cloud-sdk factory builds its **own** `ApacheHttpClient` instance:

| Client | Construction site | HTTP client |
|---|---|---|
| S3 | `VisibilityApplicationInjector.visibilityS3StorageConfig()` → `S3ClientFactory` | `legacyTunedHttpClient()` — a dedicated instance (1 s connect / 5 s socket / 50 conns) |
| SQS | `MessagingClientFactory.createDefaultClient()` L181 | `createHttpClient()` — a fresh instance per call |
| DynamoDB | `DynamoRepositoryFactory.createDynamoDbClient()` L319 | `createHttpClient()` — a fresh instance per call |
| SNS | `NotificationClientFactory` L170 | `createHttpClient()` — a fresh instance per call |

`BaseAwsConfig` (line 34) falls back to `AwsHttpClientWrapper.defaultClient()`, which is:

```java
public static AwsHttpClientWrapper defaultSyncClient() {
    return ofSync(ApacheHttpClient.builder().build());   // NEW instance every call
}
```

There is no static field, no cache, no singleton. **Nothing in `cloud-sdk-aws` shares an `SdkHttpClient` between service clients.** I grepped the entire main source tree of `cloud-sdk-aws` and `cloud-sdk-api`: the only `close()` call on an AWS client anywhere is `DynamoDbAdminCommand.java:204`, a CLI admin path that does not run in these services.

### 2.2 The AWS SDK v2 ownership rule is the reverse of what the incident doc states

The incident document asserts:

> When `.httpClient(instance)` is used, **the SDK considers itself the lifecycle owner** of that client. When `ApiCallTimeoutTrackingStage` fires it calls `sdkHttpClient.close()` on the shared instance…

Both halves are wrong:

* In `SdkDefaultClientBuilder`, `httpClient(SdkHttpClient)` wraps the argument in **`NonManagedSdkHttpClient`**, whose `close()` is a **no-op**. Passing a pre-built instance means the SDK will *never* close it. Ownership is the opposite way round: `httpClientBuilder(...)` is what makes the SDK the owner.
* `ApiCallTimeoutTrackingStage` calls `abortable.abort()` on the in-flight request. It has no reference to, and never closes, the `SdkHttpClient`.

This matters because Fix 1 (S3 → `httpClientBuilder`) was designed from this incorrect premise. See §5.1.

---

## 3. Actual Root Cause

### 3.1 Primary defect — DynamoDB Enhanced Client auto-pagination (RC-A)

`EnhancedDynamoRepository.query()` before PR #48:

```java
if (querySpec.getLimit() != null) {
    requestBuilder.limit(querySpec.getLimit());     // 5000
}
...
return table.query(request)
    .items()          // ← PageIterable.items() — a LAZY iterator over ALL pages
    .stream()
    .collect(Collectors.toList());   // ← forces the full traversal into one List
```

Two independent misunderstandings compound here:

1. **`limit` in DynamoDB is a *per-page* bound, not a total.** It caps items *evaluated* per `Query` request. It does not cap the result set.
2. **`PageIterable.items()` auto-paginates.** It follows `LastEvaluatedKey` until the query is exhausted. `.collect(toList())` therefore materialises **every matching item** in heap.

`ContainerEventOutboundDao.RESULT_SIZE_LIMIT = 5000` was written on the assumption that it capped the result at 5,000 rows. It did not. On 2026-07-30 the outbound backlog for one IPF had grown large enough that a single `getUnprocessedTransactions()` call walked **≈82,476 records** (figure from PR #1166's own description) across ~17 pages into a single `ArrayList` — plus the same number of hydrated `ContainerEventOutbound` POJOs, their nested `Subscription` and `GISOutboundDetails` graphs, and the SDK's intermediate `Map<String, AttributeValue>` per item. That is what exhausted the heap.

**This is confirmed, not inferred.** The 2026-07-30 11:49:09.608 OOM stack (§1.1c) fails inside
`EnhancedClientUtils.lambda$readAndTransformPaginatedItems$0` → `StaticImmutableTableSchema.mapToItem` →
`SubscriptionAttributeConverter.transformTo` → `ObjectMapper.readValue` → `ArrayList.grow`,
running under a `ReduceOps` terminal operation. Every element of the diagnosis above appears in that one trace: the auto-paginating iterator, the per-item POJO hydration, the terminal `collect`, and the allocation that finally failed.

**This is a regression introduced by the AWS SDK v1 → v2 migration.** The v1 code used `DynamoDBMapper.queryPage(...)` / `QueryResultPage`, which returns exactly **one page** and hands the caller a `lastEvaluatedKey`. `withLimit(5000)` under v1 therefore behaved, for this caller, as "give me at most 5,000 rows". The v2 Enhanced Client's `items()` silently changed that contract from *one page* to *the whole table slice* — with no compile error and no behavioural difference under QA-sized data.

### 3.2 The transmission mechanism — Apache HttpClient shuts the pool down on `Error` (RC-B)

This is the piece nobody identified, and it is verifiable from the bytecode. `org.apache.http.impl.execchain.MainClientExec.execute(...)` in httpclient 4.5.14:

```
1226: astore        12
1228: aload_0
1229: getfield      #21    // Field connManager:Lorg/apache/http/conn/HttpClientConnectionManager;
1232: invokeinterface #143 // InterfaceMethod HttpClientConnectionManager.shutdown:()V
1237: aload         12
1239: athrow

Exception table:
   from    to  target type
    327  1107  1226   Class java/lang/Error      ← catch (Error) → connManager.shutdown()
   1108  1119  1226   Class java/lang/Error
```

In Java source terms:

```java
} catch (final RuntimeException ex) {
    connHolder.abortConnection();      // just release the connection
    throw ex;
} catch (final Error error) {
    connManager.shutdown();            // ← DESTROY THE ENTIRE POOL, permanently
    throw error;
}
```

`OutOfMemoryError` **is** a `java.lang.Error`. So:

> **Any thread that is inside an Apache-backed AWS call at the moment the JVM runs out of heap permanently destroys that client's entire connection pool.**

`PoolingHttpClientConnectionManager.shutdown()` is terminal — there is no reopen. Every subsequent request on that `SdkHttpClient` throws `IllegalStateException: Connection pool shut down` from `Asserts.check(...)` at `PoolingHttpClientConnectionManager.java:269`, exactly as seen in all 9,438 records.

**Timing check.** First OOM `11:49:09.608`; first `Connection pool shut down` `11:53:21.501`, in the same second as the third OOM (`11:53:21.511`). The gap is the interval between the first thread dying on the heap and the first thread that was *simultaneously mid-HTTP-request* dying — precisely the behaviour this handler produces.

### 3.3 Which pool dies is a lottery — and that is what refutes the shared-pool theory

> **Correction to an earlier version of this analysis.** I originally wrote that "DynamoDB's pool survived because its thread was past the HTTP layer." That was wrong — an artefact of the supplied CSV covering only two of the ~13 task generations. CloudWatch shows **DynamoDB's pool was destroyed too, on several tasks.** The corrected mechanism below is both more accurate and a *stronger* refutation of the shared-pool theory.

**The rule is: whichever client happens to have a thread inside `MainClientExec.execute()` at the moment the heap gives out loses its pool.** Nothing about the identity of the *allocating* thread matters. Two facts make this work:

1. **`OutOfMemoryError` is not confined to the thread that consumed the heap.** The DynamoDB mapping thread exhausted it; the `OutOfMemoryError` is then thrown in whichever thread next fails to satisfy an allocation — often several at once. In this incident OOMs appear in `pool-11-thread-1, -2, -3, -4, -13, -17` within four minutes.
2. **Only threads inside Apache's exec chain destroy anything.** A thread that OOMs in application code just dies. A thread that OOMs inside `MainClientExec.execute()` triggers `catch (Error) → connManager.shutdown()` on **that client's** pool.

Per-task evidence — every task loses a *different subset* of clients:

| Task | Pools destroyed | First dead-pool error | Records |
|---|---|---|---|
| `3c1d838acd34` | **DynamoDB only** | 07-30 11:53:21 | 91 |
| `f360e23c7e67` | **SQS only** | 07-30 12:13:23 | 36,621,394 |
| `07e5cfbd3690` | **SQS + S3** | 07-31 10:34:46 | 2,554,165 + 8 |
| `9f9b0ef414ee` | **DynamoDB only** | 07-31 12:18:38 | 11,174 |
| `f7f30dac8a4e` | **SQS only** | 07-31 22:39:15 | 22,557,579 |
| `1bb4c617f3f7` | SQS + DynamoDB | 08-01 12:43:16 | 8,166 + 1 |
| `4b9642ddc1a9` | **S3 + DynamoDB** *(no SQS)* | 08-04 11:11:14 | 20 + 26,971 |
| `2b7e8016c553` | **DynamoDB only** | 08-04 14:24:47 | 243 |
| `5554056b979a` | **DynamoDB only** | 08-04 17:01:07 | 298 |

**This is dispositive.** If S3, SQS and DynamoDB shared one `SdkHttpClient`, then a single `connManager.shutdown()` would kill all three simultaneously in *every* task. Instead: task `f360e23c7e67` loses SQS and DynamoDB keeps working for 22 hours; task `9f9b0ef414ee` loses DynamoDB and SQS keeps working for 10 hours; task `4b9642ddc1a9` loses S3 and DynamoDB while SQS is fine. **Three separately-destructible pools, dying independently, on different tasks, minutes to hours apart.** That is only possible with per-client connection managers — exactly what the code in §2.1 builds.

**On the record counts.** The 36 M SQS vs 91 DynamoDB asymmetry measures **call frequency against a dead pool**, not survival:

* `receiveMessage` is called in an unthrottled `while` loop → ~464 failures/second.
* The DynamoDB poller runs on a threshold schedule (every *N* minutes per IPF) → a handful of failures per hour.
* S3 work is triggered *by* SQS messages, so when SQS dies, S3 traffic stops and its dead pool stays largely latent — which is why S3 barely appears at all.

Reading survival from these counts is precisely the mistake the CSV sample invited, and the one I made.

### 3.4 Why a *recovered* JVM keeps failing — the asymmetry that makes this incident possible

The single most counter-intuitive part of this failure, and the one worth internalising:

> **The heap recovers. The connection pool does not.**

Step by step, on the JVM that OOM'd at 11:49:09:

1. **The JVM does not exit on `OutOfMemoryError`.** Java has no such default. An uncaught OOM propagates up and **terminates only that thread**; the process continues.
2. **The dead thread's memory is reclaimed.** The 82 k-item `ArrayList` and every POJO it referenced become unreachable the moment the thread unwinds. GC collects them. Within seconds the heap is healthy again.
3. **`ThreadPoolExecutor` silently replaces the dead worker.** `BoundedThreadPool` extends `ThreadPoolExecutor`, which spawns a replacement thread when a worker dies from an uncaught throwable. So even the thread count recovers.
4. **But `PoolingHttpClientConnectionManager.shutdown()` is irreversible.** It sets an `isShutDown` flag that has no reset path, closes every pooled connection, and rejects all future lease requests. There is no reopen, no reconnect, no self-heal.
5. **And the clients are `@Singleton`s built once at startup.** `bindStorageClient()` and `provideMessagingClient()` are Guice `@Provides @Singleton`. The dead `SdkHttpClient` is captured inside the `S3Client` / `SqsClient` for the life of the JVM. Nothing rebuilds them — pre-fix there was not even a `close()` on `MessagingClient`, let alone a rebuild path.

So the post-OOM steady state is: **a perfectly healthy JVM, with plenty of free heap and a full complement of threads, permanently unable to make an HTTP request on one or more AWS clients.** Every health check passes. Every metric except throughput looks normal.

**And the recovered health is precisely what makes the spin so fast.** Before the pool died, each `SqsMessageHandler` iteration blocked for a 20-second long poll:

```
receiveMessage → connection leased → HTTPS → SQS waits up to 20 s → response
   ≈ 3 iterations per minute
```

After the pool died, the call never reaches the network at all — it fails at the first assertion inside the connection manager:

```java
// PoolingHttpClientConnectionManager.requestConnection(), line 269
Asserts.check(!this.isShutDown, "Connection pool shut down");   // throws IllegalStateException
```

```
receiveMessage → Asserts.check → IllegalStateException
   ≈ 464 iterations per second       (a 9,000× speed-up in the failure path)
```

`SqsMessageHandler` catches `Exception`, logs a ~60-frame stack trace, and re-enters the loop with no sleep. A *sick* JVM could not sustain that rate; a healthy one can, indefinitely. **The heap recovery is not a mitigation here — it is the enabling condition for the 65-million-record log storm.**

This is also why "the orchestrator will restart it" failed (§1.1d): a restart does fix the dead pool — a fresh JVM builds fresh clients — but the *first thing the new task does* is re-run the same unbounded query against the same backlog, and the cycle repeats. **The pool death is the symptom that is trivially cured by a restart; the unbounded query is the cause that a restart faithfully reproduces.**

### 3.5 Amplifier — `SqsMessageHandler` hot spin (RC-C)

```java
public void start() {
    while (notStopped) {
        try {
            if (threadPool.getRemainingTasks() > 0) {
                for (SqsMessage message : getMessages()) { ... }   // throws instantly on dead pool
            }
        } catch (Exception exception) {
            log.error("Exception occurred in SQS Message Handler, continue to next message", exception);
            // no sleep, no backoff, no failure counter, no exit
        }
    }
}
```

With a dead pool, `listMessages()` throws in microseconds instead of blocking on a 20 s long-poll. The loop then re-enters immediately. **Measured from CloudWatch, not the sample: ~1.7 million records per hour ≈ 464 per second, sustained for 22.3 hours on a single task and ~36 hours in total — roughly 65 million log records across the incident**, each carrying a ~60-frame stack trace. (The CSV sample suggested ~137/s; the true rate is 3.4× that.) This did not *cause* the OOM (it began after the pool was already dead) but it:

* burned a full core,
* generated ~65 M log records and the associated `Throwable`/`String` garbage — a material CloudWatch ingestion cost in its own right, and a heap-pressure amplifier,
* and **masked the failure**: the process stayed alive and the admin port kept answering. Where ECS *did* replace the task (~13 times, §1.1d) the replacement immediately re-ran the same unbounded query and OOM'd again, so the cycle never broke. The service was effectively down for **five days**.

**Correction to the incident document's RC-3:** `BoundedThreadPool` is *not* unbounded. It is a `ThreadPoolExecutor` fronted by a `Semaphore(taskLimit)` acquired in `execute()`. The spin loop cannot flood the `LinkedBlockingQueue`, because `getMessages()` throws *before* `threadPool.execute()` is ever reached. RC-3 as written is incorrect; the heap was consumed by the DynamoDB result set (RC-A), not by queued tasks.

### 3.6 The previously-open question — now closed

The earlier draft of this analysis could not see behind the CSV's `2026-08-01 12:12:02` boundary and therefore had to *infer* that an earlier OOM had killed the SQS pool. CloudWatch settles it directly:

| Claim | Status |
|---|---|
| An OOM preceded the first pool death | ✅ **Confirmed** — 11:49:09.608 vs 11:53:21.501 on 2026-07-30 |
| The OOM originated in the DynamoDB auto-pagination path | ✅ **Confirmed at frame level** — `readAndTransformPaginatedItems` (§1.1c) |
| The pool death is Apache's `catch (Error) → connManager.shutdown()` | ✅ **Confirmed** — bytecode (§3.2) + the same-second co-occurrence of OOM #3 and pool death #1 |
| DynamoDB's own pool survived | ⚠️ **Refuted as a general claim** — true only on the two tasks the CSV covers. DynamoDB's pool was destroyed on tasks `3c1d838acd34`, `9f9b0ef414ee`, `4b9642ddc1a9`, `2b7e8016c553`, `5554056b979a`. Which pool dies varies per task (§3.3) |
| The incident started 2026-08-01 12:12 | ❌ **Refuted** — it started 2026-07-30 11:49; the CSV captured only the tail |
| Spin rate ~137/s | ❌ **Understated** — the true sustained rate is ~464/s |
| "Expect process restart by orchestrator" would have recovered it | ❌ **Refuted** — ECS restarted the task ~13 times and every replacement re-hit the same OOM |

**Still worth pulling** (not required for the fix set, useful for sizing): the ECS task-level `MemoryUtilization` metric for the visibility-outbound service across 2026-07-30, and the container's `-Xmx` / task memory reservation. These would tell us how much headroom the 1,000-record cap actually buys and whether the cap should be higher or lower — see B-2's recommendation to make it configurable.

### 3.7 Secondary — `Crc32MismatchException` is not being retried

32 records, all on `dynamodb.query`, all with this frame:

```
RetryableStageHelper.retryPolicyDisallowedRetryException(RetryableStageHelper.java:168)
Crc32MismatchException: Expected 2335829902 ... actual 708209572 (SDK Attempt Count: 1)
```

`SDK Attempt Count: 1` plus `retryPolicyDisallowedRetryException` means the configured retry strategy **refused to retry a checksum failure** — a transient, obviously-retryable network condition. `DefaultRetryStrategy.standardStrategyBuilder()` (used by `DynamoRepositoryFactory.createOverrideConfig`) does not classify `Crc32MismatchException` as retryable. Every CRC32 mismatch therefore became a hard application error. Neither PR addresses this. See D-5.

---

## 4. Corrected Causal Chain

Every step below is evidenced; timestamps are from CloudWatch.

```
AWS SDK v1 → v2 migration
        │
        │  DynamoDBMapper.queryPage()  ──►  DynamoDbTable.query().items()
        │  (one page, caller paginates)     (auto-paginates ALL pages)
        │  RESULT_SIZE_LIMIT=5000 silently changed meaning: total → per-page
        ▼
Outbound backlog grows in QA (~82,476 rows for one IPF)
        │
        ▼
getUnprocessedTransactions() → EnhancedClientUtils.readAndTransformPaginatedItems
   materialises 82 k items, each hydrating a Subscription JSON blob via Jackson
        │
        ▼
07-30 11:49:09.608  java.lang.OutOfMemoryError: Java heap space   [pool-11-thread-1]
   ArrayList.grow ← CollectionDeserializer ← SubscriptionAttributeConverter
                  ← StaticImmutableTableSchema.mapToItem
                  ← EnhancedClientUtils.lambda$readAndTransformPaginatedItems$0   ★
        │
        │  (further OOMs 11:51:06 pool-11-thread-2, 11:53:21 pool-11-thread-13)
        │
        ├──►  Apache MainClientExec  catch (Error) { connManager.shutdown(); }
        │     fires in EVERY thread that happens to be mid-HTTP-request
        │             │
        │             ├──►  SQS pool destroyed   (pool-14-thread-1, receiveMessage)
        │             └──►  S3  pool destroyed   (pool-12-thread-N, putObject)
        │             ( WHICH clients lose their pool varies per task — see §3.3.
        │               Only threads inside MainClientExec destroy anything; a thread
        │               that OOMs in application code merely dies. )
        ▼
07-30 11:53:21.501  first IllegalStateException: Connection pool shut down
        │            ( +4 min 12 s after the first OOM; same second as OOM #3 )
        ▼
SqsMessageHandler catch-log-continue with NO backoff  →  ~464 exceptions/second
        │                                                  (~1.7 M records/hour)
        ├──►  CPU burn + ~65 M log records + Throwable/String garbage
        └──►  process stays "up"; health check stays green
        │
        ▼
ECS replaces the task ~13 times — each replacement re-runs the SAME unbounded
query against the SAME backlog and OOMs again within minutes.  No recovery.
        │
        ▼
~5 days (07-30 11:49 → 08-04 12:12) of zero outbound file generation   ← ION-16431
```

**One-sentence root cause:** *An AWS SDK v2 migration silently converted a bounded single-page DynamoDB read into an unbounded full-result-set read; under a production-sized backlog this exhausted the heap inside `readAndTransformPaginatedItems`, and Apache HttpClient's `catch (Error) → connManager.shutdown()` converted that OOM into permanent, unrecoverable destruction of the SQS and S3 connection pools — after which a backoff-free retry loop masked the dead service as a live one, and task restarts could not help because every fresh task re-ran the same query.*

---

## 5. PR-by-PR Review

### 5.1 commons PR #46 — "Dedicated HTTP Clients" (`a95c66d`, `099c2da`)

**Files:** `MessagingClient.java`, `AwsHttpClientWrapper.java`, `SqsMessagingClient.java`, `S3ClientFactory.java`, `README.md`, +3 test classes.

#### What it does

1. `MessagingClient<T>` now `extends AutoCloseable` and declares `void close()`.
2. `SqsMessagingClient.close()` → `sqsClient.close()`.
3. `AwsHttpClientWrapper` gains an `isBuilder` flag plus `ofSyncBuilder(ApacheHttpClient.Builder)` and `ofAsyncBuilder(Object)`.
4. `S3ClientFactory` branches: `isBuilder()` → `builder.httpClientBuilder(...)`, else `builder.httpClient(...)`.

#### Assessment

| Item | Verdict |
|---|---|
| `MessagingClient extends AutoCloseable` + `SqsMessagingClient.close()` | ✅ **Correct and valuable.** Genuine resource-leak fix, independent of this incident. |
| `S3ClientFactory` builder-mode branch | ⚠️ **Does not address the incident.** Neutral-to-negative. |
| `AwsHttpClientWrapper` builder mode | ❌ **Half-implemented — introduces a runtime landmine.** See D-1. |

#### Why the builder-mode change does not fix anything

`httpClient(instance)` vs `httpClientBuilder(builder)` controls exactly one thing: **whether `s3Client.close()` also closes the underlying HTTP client.** It has no effect whatsoever on `MainClientExec`'s `catch (Error)` handler, which reaches the connection manager directly and destroys it regardless of who "owns" it.

Worse, the change moves in the wrong direction relative to its own stated goal. The Javadoc added in PR #1165 says:

> *"The builder mode delegates pool lifecycle to the AWS SDK so that a DynamoDB timeout cannot close this pool."*

Under `httpClient(instance)` the pool was wrapped in `NonManagedSdkHttpClient` and **could not be closed by the SDK at all**. Under `httpClientBuilder(...)` the SDK becomes the owner and *will* close it on `s3Client.close()`. The change **adds** a lifecycle coupling that previously did not exist. It is harmless in practice today (nothing closes the visibility S3 client), but the comment is the inverse of the truth and will mislead the next reader.

> **Recommendation:** Keep the code (builder mode is the more idiomatic SDK v2 form and is useful for other reasons), but **rewrite the Javadoc in both `S3ClientFactory` and `VisibilityApplicationInjector` to state the real rationale** — and remove the claim that it protects against a DynamoDB timeout.

---

### 5.2 commons PR #47 — Version bump (`6d7785f`)

One line: `dependency.version` → `1.0.29-SNAPSHOT`. ✅ No issues. See §8 for release-line concerns.

---

### 5.3 commons PR #48 — `maxResultSize` (`7fc2303`, `1313d1b`)

**Files:** `QuerySpec.java`, `DefaultQuerySpec.java`, `EnhancedDynamoRepository.java`, `EnhancedDynamoRepositoryQueryTest.java`.

```java
final Integer maxResultSize = querySpec.getMaxResultSize();
final Integer limit = querySpec.getLimit();
final Integer effectiveLimit;
if (maxResultSize != null && maxResultSize > 0) {
    effectiveLimit = limit == null || limit <= 0 ? maxResultSize : Math.min(limit, maxResultSize);
} else {
    effectiveLimit = limit;
}
if (effectiveLimit != null && effectiveLimit > 0) {
    requestBuilder.limit(effectiveLimit);
}

final Iterable<Page<T>> pages = querySpec.getIndexName() != null
    ? table.index(querySpec.getIndexName()).query(request)
    : table.query(request);

final List<T> results = new ArrayList<>();
final int resultCap = maxResultSize != null && maxResultSize > 0 ? maxResultSize : Integer.MAX_VALUE;
for (Page<T> page : pages) {
    for (T item : page.items()) {
        results.add(item);
        if (results.size() >= resultCap) {
            return results;      // early return — PageIterable is lazy, so no further RPC
        }
    }
}
return results;
```

#### Assessment — **this is the real fix, and it is correct**

| Aspect | Verdict |
|---|---|
| Semantics: `limit` = per page, `maxResultSize` = total cap | ✅ Correct, and correctly documented in the Javadoc. |
| Early `return` inside lazy `PageIterable` iteration | ✅ Correct — `PageIterable` issues the next `Query` RPC only when the iterator advances, so breaking out genuinely stops paginating. Memory *and* RCU are both bounded. |
| `Math.min(limit, maxResultSize)` | ✅ Sensible — avoids over-fetching a final page. |
| Unified index/table path | ✅ Good cleanup; removes duplicated stream logic. |
| `getMaxResultSize()` added as a **`default`** method on the interface | ✅ **Excellent call** — source- *and* binary-compatible for any third-party `QuerySpec` implementor. |
| Drive-by removal of two redundant `(T)` casts | ✅ Fine. |

#### Gaps in PR #48

**D-2 (High) — the same defect is still live in three other methods.** The fix was applied only to `query(QuerySpec)`. These remain unbounded:

| Location | Code | Risk |
|---|---|---|
| `EnhancedDynamoRepository:506` | `findAll()` → `table.scan().items().stream().toList()` | Guarded by `isFindAllUnpaginatedScanEnabled()`, default off — but a full-table OOM the moment anyone enables it. |
| `EnhancedDynamoRepository:1010` | `export(projectionExpression, limit)` → `table.scan(req).items().stream().collect(toList())` | **`limit` here is also per-page.** This method carries the same silent v1→v2 semantic inversion as `query()` did, with the same Javadoc claim ("*optional maximum number of items to return*"). It is wrong today. |
| `EnhancedDynamoRepository:442-449` | *fixed* by this PR | ✅ |

`findAll(limit, exclusiveStartKey, filterExpression)` at line ~909 already does the right thing — it takes the first page and returns `lastEvaluatedKey`. **That is the pattern `export()` should follow.**

**D-3 (Medium) — no cursor is returned.** `query()` returns a bare `List<T>`; the caller cannot tell "I got exactly `maxResultSize`, there is more" from "that was everything", and has no `lastEvaluatedKey` to resume from. Visibility works around this with the sort-key timestamp cursor in the DAO, which is fragile (see D-4). Consider adding an overload returning the existing `ScanResult<T>`-style envelope (items + `lastEvaluatedKey`) for query, mirroring `findAll(limit, exclusiveStartKey, filter)`.

**Minor:** `new ArrayList<>()` could be `new ArrayList<>(Math.min(resultCap, 1024))` to avoid repeated array growth on large caps.

#### Test quality

`EnhancedDynamoRepositoryQueryTest` mocks `PageIterable` / `Iterator<Page<T>>` and asserts `verify(pageIterator, times(1)).next()` when `maxResultSize(1000)` is hit on the first page — i.e. it asserts the second page was **never fetched**. That is exactly the right assertion for this fix. ✅ Good test.

Missing cases worth adding:
- `maxResultSize` reached **mid-page** (cap 500, page size 1000) — confirms the inner-loop break, not just the page break.
- `maxResultSize` spanning pages (cap 1500, pages of 1000) — confirms `next()` is called exactly twice, then stops.
- `maxResultSize` combined with a `filterExpression` (post-filter pages return fewer items than `limit`).
- `limit > maxResultSize` and `limit < maxResultSize` both exercised through `effectiveLimit`.

---

### 5.4 mercury-services PR #1165 — Visibility incident fixes

**Files:** `visibility/pom.xml` (1.0.27→1.0.29), `VisibilityApplicationInjector`, `VisibilityDynamoModule`, `VisibilityMessagingModule`, `ContainerEventOutboundDao`, `SqsMessageHandler`, and the 6 application classes.

#### 5.4.1 `SqsMessageHandler` — backoff + circuit breaker

```java
static final int  MAX_CONSECUTIVE_FAILURES = 10;
static final long BASE_BACKOFF_MS = 1_000L;
static final long MAX_BACKOFF_MS  = 30_000L;
...
consecutiveFailures++;
if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
    log.error("SQS Message Handler exceeded {} consecutive failures — stopping ...");
    notStopped = false;
    break;                      // ← thread returns; nothing else happens
}
long backoffMs = Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * (1L << Math.min(consecutiveFailures - 1, 5)));
sleepMillis(backoffMs);
```

| Aspect | Verdict |
|---|---|
| Exponential backoff 1→2→4→8→16→30 s (capped) | ✅ Correct. Total ~151 s before giving up. Kills the 137/s spin. |
| `consecutiveFailures = 0` reset on a clean iteration | ✅ Correct placement. |
| `InterruptedException` re-sets the interrupt flag and exits | ✅ Correct. |
| `protected sleepMillis()` test seam | ✅ Pragmatic and clean. |
| **Circuit breaker sets `notStopped = false` and returns** | ❌ **BLOCKING — see B-1.** |

**B-1 (Blocking) — the circuit breaker creates a silent zombie service, and its stated recovery strategy is disproven by the incident itself.**

The PR description and the code comment both say *"Expect process restart by orchestrator."* Two independent problems with that.

**First — CloudWatch shows orchestrator restart is not a recovery strategy for this failure.** ECS replaced the visibility-outbound task **~13 times** during the incident (§1.1d). Every replacement came up, ran the poller, re-issued the same unbounded DynamoDB query against the same backlog, and OOM'd again within minutes. Task `f360e23c7e67` then spun for 22.3 hours; its successor `f7f30dac8a4e` spun for another 13.8. **Restarting into an unchanged poison input is a loop, not a recovery.** Any design that leans on "the orchestrator will fix it" needs the *input* bounded first — which is exactly what PR #48/#1166 does, and is why that is the load-bearing change.

**Second — nothing will restart it anyway in the new code path.** Tracing the call path:

```
OutboundSingleTransactionProcessor.start()
  → SqsMessageHandler.start()
      → returns normally after 10 failures
  → the Executors task completes; the thread returns to the pool
  → Dropwizard/Jetty keeps running; admin port keeps answering
  → the ECS health check keeps returning 200
  → ECS does nothing
```

The result is strictly **worse than the incident being fixed**. Before: a screaming service producing 137 errors/second — impossible to miss. After: a service that logs *ten* errors, one "stopping" line, and then goes **completely silent while consuming zero SQS messages, indefinitely**. Outbound files stop and nothing alerts. This turns a 71-hour loud outage into a potentially much longer quiet one.

> **Required fix — pick one, in order of preference:**
>
> 1. **Fail the health check.** Expose handler state and register a Dropwizard `HealthCheck` that reports unhealthy when any `SqsMessageHandler` has tripped. Wire the ECS container health check / ALB target-group health check to the admin `/healthcheck` endpoint. This is the idiomatic Dropwizard answer and gives ECS a real signal.
> 2. **Terminate the JVM.** After logging, call `System.exit(1)` (or `Runtime.getRuntime().halt(1)`) so ECS observes a non-zero exit and replaces the task. Blunt but unambiguous.
> 3. At minimum, emit a **CloudWatch metric + alarm** (`visibility.sqs.handler.stopped = 1`) so a human is paged.
>
> Option 1 or 2 is mandatory before release. Option 3 alone is not sufficient. And note the corollary from the paragraph above: whichever option is chosen, it only helps **because** the DynamoDB cap now bounds the input. Restart-based recovery and input-bounding are not alternatives — the first is worthless without the second.

**D-6 (Low) — the hot spin is not fully eliminated.** When `threadPool.getRemainingTasks() == 0` (worker pool saturated), the `while` loop still iterates with no sleep and no exception — a pure busy-wait burning a core. This path is untouched by the PR. Add a short `sleepMillis(50)` in the `else` branch.

**D-7 (Low) — `catch (Exception)` does not catch `Error`.** Given §3.2, an `OutOfMemoryError` in this thread will still terminate it silently, bypassing the new circuit breaker entirely. This is *correct* Java practice (never swallow `Error`), but it means the health-check fix in B-1 must key off "handler is not running" rather than "handler tripped the breaker" — otherwise the OOM path stays invisible.

#### 5.4.2 `VisibilityApplicationInjector` — S3 builder mode

```java
static AwsHttpClientWrapper buildS3HttpClientWrapper() {
    return AwsHttpClientWrapper.ofSyncBuilder(
            ApacheHttpClient.builder()
                    .connectionTimeout(S3_CONNECTION_TIMEOUT)   // 1 s
                    .socketTimeout(S3_SOCKET_TIMEOUT)           // 5 s
                    .maxConnections(S3_MAX_CONNECTIONS));       // 50
}
```

Mechanically correct and the tuning values are preserved. ⚠️ **The Javadoc is wrong** — see §5.1. Rewrite it.

#### 5.4.3 `VisibilityMessagingModule` — lifecycle

```java
public VisibilityMessagingModule(Environment environment) { this(environment, null); }
VisibilityMessagingModule(Environment environment, MessagingClient<String> messagingClientOverride) { ... }

@Provides @Singleton
public MessagingClient<String> provideMessagingClient() {
    MessagingClient<String> messagingClient = (messagingClientOverride != null)
            ? messagingClientOverride : MessagingClientFactory.createDefaultStringClient();
    environment.lifecycle().manage(new Managed() {
        @Override public void start() { }
        @Override public void stop() { messagingClient.close(); }
    });
    return messagingClient;
}
```

| Aspect | Verdict |
|---|---|
| Registering the client as Dropwizard `Managed` | ✅ Correct — real leak fix. |
| All 6 apps updated to `new VisibilityMessagingModule(e)` | ✅ Complete; I verified all six call sites. |
| `messagingClientOverride` test seam in production code | ⚠️ Minor smell — prefer overriding the `@Provides` method in a test module, or a Guice `Modules.override(...)`. Not blocking. |
| `lifecycle().manage(...)` inside a lazy `@Provides` | ⚠️ **D-8 (Low).** Guice `@Provides @Singleton` is lazy. If the first injection of `MessagingClient` happens *after* Jetty has started (e.g. from a lazily-constructed component), the `Managed` is added to an already-started `ContainerLifeCycle`. Jetty will auto-start it and still stop it, so it works — but it is timing-dependent. Safer: register the `Managed` in `configure()` against an eagerly-created client, or use `bind(...).asEagerSingleton()`. |

#### 5.4.4 `VisibilityDynamoModule` — timeouts

`apiCallTimeout` 30 s → 60 s, `apiCallAttemptTimeout` → 20 s (then 25 s in PR #1166).

✅ Arithmetically coherent (2 × 25 s + retry overhead < 60 s). But note the ordering dependency: **raising the timeout without the `maxResultSize` cap would have made things worse**, giving a runaway query twice as long to allocate. It is safe only *because* PR #48/#1166 land with it. Worth stating in the release notes so the two are never split.

#### 5.4.5 `ContainerEventOutboundDao.RESULT_SIZE_LIMIT` 5000 → 1000

⚠️ **B-2 (Blocking) — this creates a backlog-drain throughput problem.** See §5.5.2, where the same change is completed.

---

### 5.5 mercury-services PR #1166 — DynamoDB max record size

**Files:** `VisibilityDynamoModule` (comment + 20→25 s), `ContainerEventOutboundDao` (`.maxResultSize(RESULT_SIZE_LIMIT)` + timing/context logging), 2 test classes.

#### 5.5.1 The DAO change

```java
.limit(RESULT_SIZE_LIMIT)          // per-page  = 1000
.maxResultSize(RESULT_SIZE_LIMIT)  // total cap = 1000   ← the actual fix
```

✅ **Correct.** This is the line that closes RC-A. Setting both is right: `limit` bounds RCU per page, `maxResultSize` bounds heap and stops pagination.

✅ The added logging (`"DynamoDB query for IPF {} returned {} records in {} ms"`) and the enriched error message (now including `ipfId` and the cursor) are good operational improvements — the original `log.error("Failed to retrieve ContainerEventOutbound rows ", e)` gave an operator nothing to act on.

#### 5.5.2 B-2 (Blocking) — backlog drain rate

The `RESULT_SIZE_LIMIT` reduction interacts badly with how the DAO is actually driven. `getUnprocessedTransactions()` is called from `OutboundGenerator.createAndSendBatchTransactions()`, which `OutboundMultiTransactionProcessor` invokes **only when a threshold is crossed**:

```java
boolean crossedTimeThreshold        = minutesSinceLastProcessed >= outboundThreshold.getTimeLimitInMinutes();
boolean crossedTransactionThreshold = outboundThreshold.getTransactionCount() >= outboundThreshold.getTransactionsPerFile();
if (crossedTimeThreshold || crossedTransactionThreshold) {
    ... createAndSendBatchTransactions(ipfId, transactionsPerFile, lastCreationDate);
}
```

So the drain rate is **≤ 1,000 records per threshold window per IPF**, not per fast poll. For the 82,476-record backlog cited in the PR description:

| `timeLimitInMinutes` | Cycles needed | Wall-clock to drain |
|---|---|---|
| 5 | 83 | ~7 hours |
| 15 | 83 | ~21 hours |
| 30 | 83 | ~41 hours |
| 60 | 83 | ~3.5 days |

The previous 5,000 would have needed 17 cycles. **The change makes recovery from exactly the scenario that caused the incident 5× slower.** In QA this is an annoyance; in production, after any incident that builds a backlog, it is a second outage.

> **Required fix:** decouple *heap safety* from *drain rate*. Keep the 1,000-record memory cap, but loop within one processing cycle until the query returns fewer than the cap (or a per-cycle wall-clock/record budget is hit):
>
> ```java
> // in OutboundGenerator.createAndSendBatchTransactions, sketch
> int totalProcessed = 0;
> Date cursor = lastTransactionCreateDate;
> final long deadline = System.currentTimeMillis() + config.getMaxCycleDurationMillis();
> while (totalProcessed < config.getMaxRecordsPerCycle() && System.currentTimeMillis() < deadline) {
>     List<ContainerEventOutbound> batch = containerEventOutboundDao.getUnprocessedTransactions(ipfId, cursor);
>     if (batch.isEmpty()) break;
>     process(batch);
>     totalProcessed += batch.size();
>     cursor = getDateFromContainerEventOutboundSequence(batch.get(batch.size() - 1));
>     if (batch.size() < ContainerEventOutboundDao.RESULT_SIZE_LIMIT) break;   // caught up
> }
> ```
>
> Also make `RESULT_SIZE_LIMIT` a **config value**, not a `public static final int`. A heap-safety bound that requires a rebuild to tune is not operable, and the right value depends on the container's `-Xmx` and the average item size.

#### 5.5.3 B-3 (Blocking) — the trim guard can now stall a partition permanently

The de-duplication guard is unchanged but its risk profile changed with the smaller limit:

```java
if (results.size() >= RESULT_SIZE_LIMIT) {
    ContainerEventOutbound last = results.remove(results.size() - 1);
    String timestamp = last.getSortKey().split("_")[0];
    for (int i = results.size() - 1; i >= 0; i--) {
        if (results.get(i).getSortKey().startsWith(timestamp)) results.remove(i);
        else break;
    }
}
```

**If all `RESULT_SIZE_LIMIT` returned records share the same millisecond timestamp, the loop empties the list.** The caller then sees `transactionCount == 0`, returns `lastTransactionCreateTimestamp = lastCreationDate` unchanged, and the cursor **never advances** — that IPF stalls forever, silently, and re-runs the identical query every cycle.

At 5,000 this required 5,000 events in one millisecond (effectively impossible). At 1,000 it requires 1,000 — still unlikely for organic traffic, but **entirely achievable during a bulk backfill, a replay, or a migration**, which is precisely when the backlog exists. The window was widened 5× by a change whose stated purpose was resilience.

Two further problems in the same block:

* `startsWith(timestamp)` is a **prefix** match on a string timestamp. `"1785841861483"` is a prefix of `"17858418614839"`. Epoch-millis are 13 digits today and will be until 2286, so this is latent rather than live — but it is an incorrect comparison. Split on `_` and compare the first token for equality.
* There is no guard for the empty-result case at all.

> **Required fix:**
> ```java
> if (results.size() >= RESULT_SIZE_LIMIT) {
>     String lastTs = results.get(results.size() - 1).getSortKey().split("_")[0];
>     int keep = results.size();
>     while (keep > 0 && lastTs.equals(results.get(keep - 1).getSortKey().split("_")[0])) keep--;
>     if (keep == 0) {
>         // Every record in the page shares one millisecond. Trimming would stall the cursor.
>         // Process the whole page: correctness of the cursor beats the duplicate-window guard.
>         log.warn("IPF {}: all {} records share timestamp {} — processing full page to avoid cursor stall",
>                  ipfId, results.size(), lastTs);
>     } else {
>         results = new ArrayList<>(results.subList(0, keep));
>     }
> }
> ```
> and add a unit test for the all-same-timestamp page.

#### 5.5.4 D-9 (Low) — an inaccurate code comment

`VisibilityDynamoModule` now reads:

> *"The Crc32MismatchExceptions and **ProvisionedThroughputExceededExceptions** observed in the 2026-08-01 incident indicate network instability and **RCU exhaustion**."*

There are **zero** `ProvisionedThroughputExceededException` occurrences in the log export — I grepped the full 77 MB. There is no evidence of RCU exhaustion anywhere in the data. Remove that clause; it will send the next investigator down a dead end. (The DynamoDB VPC-endpoint suggestion in the same comment is sound and should stay.)

---

## 6. Defect Register

| ID | Sev | Where | Issue | Action |
|---|---|---|---|---|
| **B-1** | 🔴 Blocking | `SqsMessageHandler` (#1165) | Circuit breaker stops the handler but nothing restarts the task → silent zombie, worse than the original outage | Fail the Dropwizard health check (preferred) or `System.exit(1)`; add a CloudWatch alarm |
| **B-2** | 🔴 Blocking | `ContainerEventOutboundDao` + `OutboundGenerator` (#1165/#1166) | 5000→1000 makes backlog drain 5× slower; ≤1000 records per *threshold window* → up to 3.5 days for 82 k | Loop within a cycle until caught up; make the limit configurable |
| **B-3** | 🔴 Blocking | `ContainerEventOutboundDao` (#1166) | Trim guard can empty the page → cursor never advances → permanent silent stall. Risk widened 5× by the smaller limit. `startsWith` is also a wrong comparison | Guard the empty case; use exact token equality; add a test |
| **D-1** | 🟠 High | `AwsHttpClientWrapper` / all factories (#46) | Builder mode honoured **only** by `S3ClientFactory`. Passing an `ofSyncBuilder(...)` wrapper to a DynamoDB / SQS / SNS / SES / SSM config casts `ApacheHttpClient.Builder` → `SdkHttpClient` → `ClassCastException` at client construction | See §7.1 |
| **D-2** | 🟠 High | `EnhancedDynamoRepository:1010`, `:506` | `export(projection, limit)` and `findAll()` still auto-paginate the whole table — same OOM class as the fixed `query()`. `export`'s Javadoc actively misdescribes `limit` | Apply the same `maxResultSize` treatment; correct the Javadoc |
| **D-3** | 🟡 Medium | `EnhancedDynamoRepository.query` | Returns a bare `List<T>` — no `lastEvaluatedKey`, no "more available" signal | Add an overload returning items + cursor, mirroring `findAll(limit, startKey, filter)` |
| **D-4** | 🟡 Medium | `S3ClientFactory`, `VisibilityApplicationInjector` | Javadoc states the inverse of AWS SDK v2 ownership semantics and credits builder mode with protection it does not provide | Rewrite both comments |
| **D-5** | 🟡 Medium | `DynamoRepositoryFactory.createOverrideConfig` | `Crc32MismatchException` is classified non-retryable → 32 hard failures that should have been transparent retries | Add a retry predicate for `Crc32MismatchException`; longer-term add a DynamoDB VPC endpoint |
| **D-6** | 🟢 Low | `SqsMessageHandler.start()` | `getRemainingTasks() == 0` path still busy-waits with no sleep | Add `sleepMillis(50)` in that branch |
| **D-7** | 🟢 Low | `SqsMessageHandler.start()` | `catch (Exception)` misses `Error`; an OOM kills the thread silently, bypassing the breaker | Health check must key off "not running", not "breaker tripped" |
| **D-8** | 🟢 Low | `VisibilityMessagingModule` | `lifecycle().manage()` inside a lazy `@Provides` is start-order dependent | Register eagerly in `configure()` |
| **D-9** | 🟢 Low | `VisibilityDynamoModule` | Comment cites `ProvisionedThroughputExceededException` / RCU exhaustion — **zero occurrences in the logs** | Remove the clause |
| **D-10** | 🟢 Low | `AwsHttpClientWrapper.getTypedClient()` | The `try/catch (ClassCastException)` is **dead code** — erasure means the cast never throws inside the method; the CCE surfaces at the caller with no context | Take an explicit `Class<T>` and check, or drop the misleading catch |
| **D-11** | 🟢 Low | `S3StorageClient.putObject:638` | Throws `RuntimeException("Unexpected error during S3 read")` from a **write** path — actively misleading during triage | Fix the message |
| **D-12** | 🟠 High | `SubscriptionAttributeConverter` + `ContainerEventOutboundDao` | The confirmed OOM frame is `SubscriptionAttributeConverter.transformTo` → Jackson. **Every** row hydrates a full `Subscription` object graph from a JSON blob, even though the outbound poller's cursor logic only needs `sequenceNumber`. Per-row heap cost is far above wire size, so the 1,000-record cap buys less headroom than it appears to | Use a **projection expression** on the poller query to fetch only the attributes the cycle needs, and hydrate `Subscription` lazily (or in the per-record processing step, not the bulk read). This compounds with B-2: a cheaper row means a safely larger cap and a faster drain |

### 6.1 On the developer's stated diagnosis

> *"Shared http clients in different aws service clients was causing issues when one was having issue (S3, SQS, Dynamo etc)"*

The **conclusion** (isolate the pools) is defensible engineering hygiene, but the **premise is not what happened here**. The clients were already isolated — `MessagingClientFactory`, `DynamoRepositoryFactory`, `NotificationClientFactory` and `S3ClientFactory` each construct a private `ApacheHttpClient`, and `AwsHttpClientWrapper.defaultSyncClient()` returns a new instance on every call. The decisive counter-evidence is the **per-task variation** in §3.3: task `f360e23c7e67` lost SQS while DynamoDB kept working for 22 hours; task `9f9b0ef414ee` lost DynamoDB while SQS kept working for 10 hours; task `4b9642ddc1a9` lost S3 and DynamoDB while SQS was fine. A single shared pool cannot die selectively, on different tasks, hours apart. Three separately-destructible connection managers can — and that is exactly what the code in §2.1 builds.

> *"Also there was dynamo DB change to enforce maxresult size, we had only per page fetch size option"*

**This is exactly right and it is the actual root cause — now confirmed at frame level.** The OOM stack terminates in `EnhancedClientUtils.lambda$readAndTransformPaginatedItems$0`. There is no ambiguity left about which half of the diagnosis was load-bearing. This half deserved to be the headline; the HTTP-client half is a distraction that consumed most of PR #46 and #1165.

---

## 7. Recommended Additional Work

### 7.1 D-1 — finish the builder-mode abstraction (High)

Today `isBuilder` is a flag that only one of six factories reads. Every other factory does:

```java
.httpClient(config.getHttpClient() != null ? config.getHttpClient().getTypedClient() : createHttpClient())
```

`getTypedClient()` is `<T> T` with an unchecked cast, so a builder-mode wrapper compiles fine and then throws `ClassCastException` at `SqsClient.builder().httpClient(...)`. Two ways out:

**Option A (preferred) — resolve inside the wrapper.** Give `CloudHttpClient` a single `applyTo(...)` responsibility so no factory has to branch:

```java
public interface CloudHttpClient {
    /** Applies this HTTP client (instance or builder, sync or async) to an SDK client builder. */
    void applyToSync(SdkSyncClientBuilder<?, ?> builder);
    void applyToAsync(SdkAsyncClientBuilder<?, ?> builder);
}
```
Each factory then calls `config.getHttpClient().applyToSync(builder)` and the instance/builder decision disappears from the call sites entirely. This also removes D-10.

**Option B (minimal) — replicate the branch in all six factories** (`DynamoRepositoryFactory`, `MessagingClientFactory` ×2 call sites, `NotificationClientFactory`, `EmailClientFactory`, `ParameterStoreClientFactory`, `TransferManagerFactory`) and add a fast-fail in `ofSyncBuilder`/`ofAsyncBuilder` documenting which factories support it.

Also, while here:
* `ofSyncBuilder(ApacheHttpClient.Builder)` is over-narrow — widen to `SdkHttpClient.Builder<?>` so `UrlConnectionHttpClient` / `AwsCrtHttpClient` builders are usable.
* `ofAsyncBuilder(Object)` accepts anything with no validation, unlike its `ofAsync(Object)` sibling which checks `instanceof SdkAsyncHttpClient`. Tighten to `SdkAsyncHttpClient.Builder<?>`.
* Nothing in the codebase currently calls `ofAsyncBuilder`, and no factory honours it. Either wire it up or drop it — dead API surface in a shared SDK is a liability.

### 7.2 Defend against the real mechanism (High)

The `catch (Error) → connManager.shutdown()` behaviour is a property of Apache HttpClient 4.x that we cannot change. Three defences, in order of value:

1. **Don't run out of heap.** PR #48/#1166 is the fix. Extend it to `export()` and `findAll()` (D-2), and audit every other `.items().stream().collect(...)` in the codebase for the same pattern.
2. **Detect a dead pool and recycle the client.** `IllegalStateException("Connection pool shut down")` is unambiguous and permanent. `SqsMessagingClient` could detect it and rebuild its `SqsClient`, turning a fatal state into a self-healing one. This is a genuinely valuable cloud-sdk feature and is a far better use of effort than the builder-mode change:
   ```java
   } catch (IllegalStateException e) {
       if (e.getMessage() != null && e.getMessage().contains("Connection pool shut down")) {
           log.error("Connection pool is permanently shut down — rebuilding SQS client", e);
           rebuildClient();     // guarded by a lock + a rebuild-attempt cap
       }
       throw handleException(operation, queueUrl, e);
   }
   ```
3. **Consider switching the sync transport.** `UrlConnectionHttpClient` has no shared connection manager and therefore no equivalent global-destruction failure mode. It loses connection pooling, so this is a trade-off worth measuring rather than assuming — but for low-throughput control-plane clients (SSM, SNS) it may be strictly better.

### 7.3 Operational gaps that let a five-day outage go unnoticed (High)

No code change caused the five-day duration — the absence of monitoring did. Note that ECS restarts *were* happening throughout (§1.1d) and nobody noticed those either: ~13 task replacements, two multi-hour spin episodes, and ~65 million error records produced no alert. Independent of these PRs:

* **Alarm on `visibility-outbound` SQS `ApproximateAgeOfOldestMessage`.** A queue with a rising oldest-message age and zero consumption is the single clearest signal that this class of failure produces, and it would have fired within minutes.
* **Alarm on ECS `MemoryUtilization` > 85 %** for the visibility task family.
* **Alarm on ERROR log-rate anomaly** — 464 errors/second sustained for 22 hours is not subtle. A static threshold of, say, 100 ERROR records/minute on this log group would have fired within a minute of onset on 2026-07-30.
* **Alarm on ECS task restart rate** — 13 replacements over five days on a service that should be stable is its own signal, independent of anything in the logs.
* **Budget alarm on CloudWatch Logs ingestion** — 65 M records from one service is a cost event as well as a reliability event.
* **Add `-XX:+ExitOnOutOfMemoryError` and `-XX:+HeapDumpOnOutOfMemoryError`** to the visibility task definitions — but understand precisely what they do and do not buy. **They do not shorten the outage.** They change its *shape*: from an invisible, expensive, undiagnosable stall to a loud, cheap, self-evidencing crash-loop. Full reasoning, including the operational caveats on heap-dump storage, is in **Appendix D.1** — read that before adopting them, because a naïve `-XX:HeapDumpPath` on an ephemeral container filesystem is worse than useless.
* **Include `@logStream` in future log exports.** Its absence in the supplied CSV made it impossible to separate ECS tasks, hid the ~13 restarts, and understated the error rate by 3.4×.

### 7.4 Guard the regression class, not just the instance (Medium)

The v1→v2 pagination inversion is a *category* of defect, not a one-off. Add to the migration checklist and to code review:

* Any `PageIterable`/`SdkIterable` consumed with `.items()`, `.stream()`, or an enhanced-for **must** have an explicit total bound.
* `limit` on any DynamoDB request is **per page**. Any variable named `*_SIZE_LIMIT`, `maxResults`, or similar that is passed to `limit()` is a red flag.
* Prefer returning `(items, lastEvaluatedKey)` over `List<T>` for any repository method that can match an unbounded number of rows.

An ArchUnit or Checkstyle rule matching `.items()` inside `cloud-sdk-aws` would make this enforceable rather than aspirational.

---

## 8. Backward Compatibility — cloud-sdk-api / cloud-sdk-aws

`cloud-sdk-api` and `cloud-sdk-aws` are consumed by most upgraded mercury-services applications, so every API change here is a fleet-wide change.

### 8.1 Current consumer versions (from `pom.xml` scan)

| App | `mercury.commons.version` |
|---|---|
| `auth` | 1.0.27-SNAPSHOT |
| `booking` | 1.0.27-SNAPSHOT |
| `booking-bridge` | 1.0.27-SNAPSHOT |
| `bill-of-lading-v2` | 1.0.28-SNAPSHOT |
| `visibility` | 1.0.29-SNAPSHOT (this PR set) |
| `bill-of-lading` | 1.R.01.021 (legacy line — not on cloud-sdk) |
| `booking-cargoscreen` | 1.R.01.023 (legacy line) |

The fleet is already fragmented across 1.0.27 / 1.0.28 / 1.0.29. Every one of these must move together for the release described below.

### 8.2 Change-by-change compatibility

| Change | Source compat | Binary compat | Risk | Notes |
|---|---|---|---|---|
| `QuerySpec.getMaxResultSize()` as a **`default`** method | ✅ Safe | ✅ Safe | 🟢 None | Correct API-evolution technique. Third-party `QuerySpec` implementors are unaffected. |
| `DefaultQuerySpec` + `maxResultSize` field/builder method | ✅ Safe | ✅ Safe | 🟢 None | Additive only; class is `final` with a private constructor. No `equals`/`hashCode`/`toString`/`toBuilder` exist, so nothing else needs updating. |
| `EnhancedDynamoRepository.query()` behaviour | ✅ Safe | ✅ Safe | 🟡 **Behavioural** | Callers that pass `maxResultSize` get a cap; callers that don't get **identical** behaviour (`resultCap = Integer.MAX_VALUE`). Opt-in. ✅ |
| **`MessagingClient<T> extends AutoCloseable` + abstract `void close()`** | ⚠️ **Breaking for implementors** | ⚠️ **`AbstractMethodError` risk** | 🟠 **Medium** | See §8.3 |
| `AwsHttpClientWrapper.isBuilder()` + `ofSyncBuilder` / `ofAsyncBuilder` | ✅ Safe | ✅ Safe | 🟠 **Medium** | Additive, but D-1 makes it a runtime landmine for any consumer that adopts it outside S3. |
| `S3ClientFactory` branch | ✅ Safe | ✅ Safe | 🟢 None | Default path (`httpClient`) unchanged when `isBuilder == false`. |
| `AwsStorageConfig.getHttpClientForTesting()` | ✅ Safe | ✅ Safe | 🟡 **Latent** | Declared to return `SdkHttpClient`. Against a builder-mode config it now throws `ClassCastException` at the call site instead of the documented `IllegalStateException`. Any consumer test using this on a builder-mode config breaks. |
| `VisibilityMessagingModule(Environment)` constructor | ⚠️ Breaking | ⚠️ Breaking | 🟢 None | Visibility-internal; all 6 call sites updated in the same PR. Not part of the SDK surface. |

### 8.3 The `MessagingClient.close()` change — detail

Adding an abstract method to a published interface is the one genuinely breaking change in this set.

* **Source compatibility:** any class implementing `MessagingClient<T>` without a `close()` method **will not compile** against 1.0.29+.
* **Binary compatibility:** a class compiled against ≤1.0.28 will load against 1.0.29 but throws **`AbstractMethodError`** the moment anything calls `close()` on it — including the new `Managed.stop()` hook.

**Blast radius inside `mercury-services`: nil.** I searched the whole repo:
```
implements MessagingClient   → only cloud-sdk-aws/SqsMessagingClient
new MessagingClient<...>() { → no anonymous implementations
```
Every consumer (`booking/SQSClient`, `booking-bridge/SQSClient`, `tx-tracking`, `bill-of-lading-v2`, `visibility`) *wraps* or *injects* a `MessagingClient` rather than implementing it, and all test doubles are Mockito mocks (which synthesise `close()` automatically). ✅

**Outstanding verification before release:**
1. Search **every** repository that depends on `cloud-sdk-api` — not just `mercury-services` — for `implements MessagingClient`. Any hit is a compile break.
2. Check for hand-written test fakes (not Mockito) implementing `MessagingClient` in downstream repos.
3. Note the secondary effect: `AutoCloseable` makes SpotBugs/Sonar `OBL_UNSATISFIED_OBLIGATION` and IDE "resource leak" inspections fire at every `MessagingClientFactory.create*` call site that doesn't close. Expect new (mostly benign) static-analysis findings across the fleet; budget for triaging them.

**Softer alternative if any external implementor is found:** declare `close()` as a `default` no-op on the interface and `@Override` it in `SqsMessagingClient`. That is fully source- and binary-compatible. It is weaker (an implementor silently gets a no-op close), so prefer the abstract form if §8.3 verification comes back clean.

### 8.4 Recommended release plan for 1.0.30-SNAPSHOT

The current changes sit on `feature/ION-12310-commons-cloudsdk-refactoring`, which is **not** the commons develop line. The OWASP fixes are on `develop` and are not yet rebased in. Sequencing matters:

1. **Rebase** `feature/ION-12310-commons-cloudsdk-refactoring` onto `origin/develop` to pick up the OWASP / dependency fixes. Resolve conflicts in `pom.xml` and any shared config. *(This is the same rebase pattern as the 1.0.24 exercise — reuse that runbook.)*
2. **Land the blocking fixes** in commons before cutting the version: **D-1** (builder mode honoured by all factories, or Option A) and **D-2** (`export()` / `findAll()` pagination caps). These are SDK-surface changes; shipping 1.0.30 without them means a 1.0.31 shortly after.
3. **Bump to `1.0.30-SNAPSHOT`** in the commons root `pom.xml`.
4. **Add a `README.md` release note for v1.0.30** covering: the OWASP rebase; `MessagingClient extends AutoCloseable` **flagged explicitly as a breaking change for implementors**; `QuerySpec.getMaxResultSize()`; HTTP-client builder mode and which factories support it.
5. **Run the §8.3 verification sweep** across all downstream repos before publishing.
6. **Publish 1.0.30-SNAPSHOT**, then raise one PR per consumer app bumping `mercury.commons.version`. Order by blast radius: `visibility` (already validated) → `auth` → `booking-bridge` → `booking` → `bill-of-lading-v2`.
7. **Per app, re-run the AWS-service smoke suite.** The pagination change alters `query()` behaviour only for callers that opt in via `maxResultSize`, but the `AutoCloseable` change touches every SQS consumer's shutdown path — that is what to smoke-test.
8. **Do not split** the DynamoDB timeout increase (60 s) from the `maxResultSize` cap. Shipping the timeout alone gives a runaway query twice as long to exhaust the heap. Note this in the release note.

### 8.5 Migration note for consuming apps

Any app whose DAO passes a "result size limit" to `QuerySpec.limit()` believing it caps the total is **carrying the same latent OOM as visibility did**. Every consumer team should audit their DAOs:

```java
// BEFORE — limit is PER PAGE; the SDK still paginates the entire result set into heap
DefaultQuerySpec.builder().limit(MY_RESULT_LIMIT).build();

// AFTER — limit bounds RCU per page, maxResultSize bounds heap and stops pagination
DefaultQuerySpec.builder().limit(MY_RESULT_LIMIT).maxResultSize(MY_RESULT_LIMIT).build();
```

Grep target for each app: `\.limit\(` on any `DefaultQuerySpec.builder()`.

---

## 9. Root Cause, Detection Gap, and Design Gap

### 9.1 Root cause

An AWS SDK v1 → v2 migration silently changed a bounded, single-page DynamoDB read into an unbounded full-result-set read. Under a production-sized backlog this exhausted the heap inside `EnhancedClientUtils.readAndTransformPaginatedItems`; Apache HttpClient's `catch (Error) → connManager.shutdown()` converted that OOM into permanent destruction of whichever connection pools had a request in flight — SQS's on most tasks, DynamoDB's or S3's on others; a backoff-free, exit-free retry loop then masked the dead service as a running one; and because the poison input was never bounded, the ~13 ECS task restarts that did occur simply reproduced the failure. Five days, ~65 million error records, zero outbound files.

### 9.2 Why it was missed

**Nothing about it was visible at compile time or at QA scale.**

* `DynamoDBMapper.queryPage(...)` → `DynamoDbTable.query().items()` is not a signature change the compiler can flag. Both return "the results". The word *page* simply disappeared.
* `limit` exists in both SDKs with the same name and the same type. Its semantics ("items per page" vs. what the caller assumed, "items total") are documented but easy to read past — and in v1 the two coincided *for this caller* because `queryPage` returned one page.
* **At normal data volumes the two are indistinguishable.** With < 5,000 rows per IPF, `query().items()` fetches one page and the code is correct. The defect only becomes reachable once a backlog builds — which itself only happens after a *different* failure. This is a classic latent, load-dependent regression: correct in unit tests, correct in QA, correct in production, until one bad day.
* The migration's test strategy validated **functional equivalence** (right rows, right order, right fields) but not **resource-consumption equivalence**. No test asserted "this query fetches at most one page."
* The `Crc32MismatchException` bursts (32) and DynamoDB `ApiCallTimeoutException` bursts (238) were genuine noise that made the incident *look* network-shaped. Both the incident document and PR #1165 anchored on that surface signal. CloudWatch shows these recur at the same hour every day and continued long after the pools were dead — they track a scheduled workload, not the failure.
* The initial analysis reached for the most-available explanation ("timeout closed the pool") without checking the AWS SDK's ownership semantics or Apache's `Error` handling. Both are one decompile away — but only if you think to look.
* **The evidence sample itself misled the investigation.** The CSV export was scoped to a window that began at the *end* of the second spinning task, carried no `@logStream`, and contained 10,000 of ~65,000,000 records. From it, the incident looks like a 71-hour event starting on 08-01 at ~137 errors/s with no restarts. It is a five-day event starting 07-30 at ~464 errors/s across ~13 task generations. Every headline number in `incident-analysis-2026-08-04.md` — window, duration, rate, and causal order — is an artefact of that sampling. **Pulling the raw log group first, before writing the analysis, would have prevented all of it.**

### 9.3 Design gaps

**G-1 — Resource-consumption is not part of the repository contract.** `DatabaseRepository.query(QuerySpec) → List<T>` cannot express "there is more," cannot bound its own memory, and gives the caller no cursor. Any API that returns `List<T>` for a potentially unbounded query is a latent OOM. Contrast `findAll(limit, exclusiveStartKey, filterExpression) → ScanResult<T>` in the *same class*, which gets it right. The abstraction was inconsistent with itself.

**G-2 — The SDK migration had no resource-behaviour test class.** Functional parity was tested; pagination, connection, thread, and memory behaviour were not. A single test asserting `verify(pageIterator, times(1)).next()` — the very test PR #48 finally added — would have caught this before the migration shipped.

**G-3 — No failure-mode analysis of the new transport.** Moving to Apache HttpClient introduced a shared, destructible, non-recoverable connection manager per client. Nobody asked "what permanently destroys this, and what happens next?" The `catch (Error) → shutdown()` behaviour is documented Apache 4.x semantics, not obscure.

**G-4 — Retry loops without a terminal state.** `while (notStopped) { try { ... } catch (Exception e) { log; } }` treats every failure as transient. Some failures — a shut-down connection pool, an expired credential chain, a deleted queue — are permanent for the life of the client. The design had no notion of a non-recoverable error, and therefore no way to escalate one. **PR #1165 adds the detection but stops short of the escalation** (B-1) — the loop now knows it has failed permanently, and still nobody finds out.

**G-5 — Liveness was never defined.** The Dropwizard health check reported "the JVM is up," not "this service is doing its job." A service whose entire purpose is to consume a queue and write files was considered healthy while consuming nothing and writing nothing for five days. Health checks must assert *function*, not *process*.

**G-7 — Restart was treated as the recovery mechanism without bounding the input.** The architecture implicitly assumed "if a task goes bad, ECS replaces it and we're fine." CloudWatch shows that assumption failing 13 times in a row: the poller's first act on startup is to re-read the same unbounded backlog that killed its predecessor. **Crash-restart recovery only works when the triggering input is bounded or quarantined.** Neither was true here — there was no cap, no poison-pill detection, and no circuit breaker on the *read* side. This is the gap that PR #48/#1166 actually closes, and it deserves to be recognised as the architectural fix rather than a tuning tweak.

**G-6 — The blast radius of a shared SDK was not reflected in its review bar.** `cloud-sdk-api`/`cloud-sdk-aws` are consumed by most mercury-services applications. A semantic change in `EnhancedDynamoRepository.query()` is a change to every consumer's memory profile simultaneously. That surface deserves API-compatibility gating (japicmp or revapi in CI), documented semantics for every bound, and a released changelog — none of which exist today.

---

## 10. Conclusion

**Does the change set address the issue holistically? No — but the most important piece is there.**

| Root cause | Addressed? | By |
|---|---|---|
| RC-A — DynamoDB unbounded auto-pagination → OOM *(confirmed at frame level)* | ✅ **Yes, correctly** | PR #48 + #1166 |
| RC-B — Apache `catch (Error)` destroys the pool | ❌ No | Mitigated only indirectly by fixing RC-A; see §7.2 |
| RC-C — SQS hot spin with no backoff (~464/s, ~65 M records) | ⚠️ Partly | PR #1165 — backoff ✅, escalation ❌ (B-1) |
| Recovery: restart-into-poison-input loop | ❌ **No** | B-1 / G-7 — only the cap breaks the loop |
| Per-row hydration cost (`SubscriptionAttributeConverter`) | ❌ No | D-12 |
| Backlog drain after any incident | ❌ **No — made 5× slower** | B-2 |
| Silent stall on same-timestamp pages | ❌ **No — risk widened 5×** | B-3 |
| The same pagination defect elsewhere in the SDK | ❌ No | D-2 |
| Builder mode usable outside S3 | ❌ No | D-1 |
| Crc32Mismatch treated as fatal | ❌ No | D-5 |
| Detection / alerting | ❌ No | §7.3 |

**Recommended disposition:** hold the release. Land **B-1, B-2, B-3** in `mercury-services` and **D-1, D-2, D-12** in `mercury-services-commons` / visibility, correct the misleading comments (**D-4, D-9**), then cut `1.0.30-SNAPSHOT` per §8.4.

Two closing points, both sharpened by the CloudWatch evidence:

1. **PR #48/#1166 is not a tuning change — it is the fix.** The OOM stack names `readAndTransformPaginatedItems` directly. Everything else in the five PRs is hardening around a failure that this one change prevents. It should be sequenced first and never split from the DynamoDB timeout increase.
2. **`-XX:+ExitOnOutOfMemoryError` and `-XX:+HeapDumpOnOutOfMemoryError` on the visibility task definitions remain the highest-value items outside the code.** They would have collapsed 22 hours of silent 464/s spinning into a fast, loud crash-loop and handed us the heap dump on day one. But — corrected from my earlier draft — they would **not** by themselves have restored service: ECS was already restarting the task and it never helped. Bound the input first; make failure loud second.

---

## Appendices A–B — superseded

The earlier standalone appendices (CSV parsing script, CloudWatch query set, and the
`javap` verification of Apache's `catch (Error)` handler) are consolidated into
**Appendix D — Analysis Command Log**, which lists every command in execution order:
CSV parsing in **D.7**, the Apache bytecode check in **D.8**, and the CloudWatch
Insights queries in **D.9**.

## Appendix C — Commit map

| PR | Repo | Commits | Merge |
|---|---|---|---|
| #46 | commons | `a95c66d` (tests), `099c2da` (Dedicated HTTP Clients) | `9527ff7` |
| #47 | commons | `6d7785f` (version bump) | `450bea0` |
| #48 | commons | `7fc2303` (tests), `1313d1b` (max size limit) | `b305acc` |
| #1165 | mercury-services | `ce6a773c65` (TDD tests), `167d9dd01f` (incident fixes), `be76d24a0a` (5000→1000) | — |
| #1166 | mercury-services | `316b5da457` (maxResultSize + 25 s + logging) | — |

All five are **MERGED**. Commons PRs target `feature/ION-12310-commons-cloudsdk-refactoring`; mercury-services PRs target `develop`.

---

## Appendix D — Analysis Command Log

Every command used to produce this document, in the order it was run. Reproducible end-to-end on a machine with both repos cloned, `~/.m2` populated, and a live `642960533737_INTTRA2-QATeam` SSO session.

### D.1 Reviewer question: *"How do `-XX:+ExitOnOutOfMemoryError` / `-XX:+HeapDumpOnOutOfMemoryError` help if restarts were already running the poison loop again?"*

**Direct answer: they do not shorten the outage. Nothing in the JVM flags breaks the poison loop — only the DynamoDB cap does that.** The question exposes real sloppiness in my earlier draft, which called these "the single highest-value change in this document." That was wrong, and the CloudWatch task timeline (§1.1d) is what disproves it: ECS restarted the task ~13 times and every replacement re-OOM'd within minutes. Adding a flag that makes the JVM exit *faster* does not change that arithmetic at all.

What the flags change is the **shape** of the failure. Four concrete effects:

**1. They stop the spin — which was ~99.99 % of the damage.**
The OOM killed only the *allocating* thread (`pool-11-thread-1`). The JVM survived, with permanently destroyed SQS and S3 connection pools, and `SqsMessageHandler` then spun at ~464 exceptions/second. That is the origin of the ~65 M log records and the 22-hour-per-task CPU burn — not the OOM itself. With `ExitOnOutOfMemoryError` the JVM is gone at `11:49:09.608`, roughly **four minutes before the first pool death** and ~22 hours before that task actually stopped logging. Per-task volume drops from 37,220,190 records to the few hundred emitted during startup. The outage length is unchanged; the CloudWatch bill, the CPU cost, and the heap-pressure amplification are not.

**2. They convert an unmonitorable state into a monitorable one.** This is the substantive answer.

| Signal | Silent spin (what happened) | Crash-loop (with the flag) |
|---|---|---|
| ECS task state | `RUNNING` for 22 h | repeated `STOPPED`, non-zero exit code |
| ECS `StoppedReason` | — | `Essential container exited` |
| ECS service events | — | task-failure event every cycle |
| Dropwizard health check | 200 OK | unreachable |
| Deployment circuit breaker | never trips | **trips → automatic rollback** |
| What on-call sees | a green service | a service that will not stabilise |

The failure went unnoticed for five days because **a spinning JVM is indistinguishable from a healthy one to every check that existed.** A crash-looping task is not: ECS surfaces it in `DescribeServices` events and the deployment circuit breaker acts on it, with no custom instrumentation. Restarts *did* happen — but each restarted task then sat in `RUNNING` for hours, so the churn looked like ordinary task recycling. Fast, repeated, non-zero exits are what turn "restarts are happening" from noise into a signal.

**3. `HeapDumpOnOutOfMemoryError` addresses investigation MTTR, not outage MTTR.**
A dump from 2026-07-30 would have shown ~82 k `ContainerEventOutbound` instances plus their `Subscription` graphs dominating the heap, naming RC-A in minutes. Instead this took full log forensics plus decompiling `httpclient-4.5.14.jar` to establish a mechanism a dump would have made self-evident. That pays off on the *next* incident, not this one.

**4. It retires D-7 for free.** With the flag, `catch (Exception)` failing to catch `Error` stops mattering — the JVM is gone before the distinction is observable.

**Operational caveats — do not adopt naïvely:**

* `-XX:HeapDumpPath` pointing at the container's ephemeral filesystem **loses the dump when the task dies**, which is precisely when it is written. It needs an EFS mount, or a wrapper/`preStop` that ships the dump to S3. My earlier draft's `/mnt/dumps` was cargo-cult advice.
* A dump is written **once per JVM**, so a crash-loop yields one per restart. Thirteen restarts × a multi-GB heap will fill a shared volume. Cap retention, or write to S3 with a lifecycle rule.
* Writing a large dump takes tens of seconds and stalls the exit, slightly slowing the crash-loop. Harmless here, but worth knowing.
* `ExitOnOutOfMemoryError` needs the ECS restart policy and deployment circuit breaker configured sensibly, or a crash-loop can present a *runtime* failure as a *deployment* failure.

**Correct sequencing:** bound the input first (PR #48/#1166 — the only change that ends the loop); make failure loud second (`ExitOnOutOfMemoryError` + the alarms in §7.3); make failure diagnosable third (heap dumps to durable storage). Presenting the flags as the top-line fix — as I originally did — inverts that order, and would have delivered a service that crash-loops loudly and still processes nothing.

### D.2 Local documents and repository setup

```bash
# Incident artefacts
ls -la "C:/Users/arijit.kundu/OneDrive - WiseTech Global/Documents/platform/aws-upgrade/12.visibility/issues/"
head -c 3000 "log-analytics-results-2026-08-04 (3).csv"
wc -l "log-analytics-results-2026-08-04 (3).csv"          # 665,090 physical lines / 77 MB

# Repos
ls -d /c/Users/arijit.kundu/projects/*/
git -C /c/Users/arijit.kundu/projects/mercury-services         remote -v
git -C /c/Users/arijit.kundu/projects/mercury-services-commons remote -v
git -C /c/Users/arijit.kundu/projects/mercury-services-commons branch -a
git -C /c/Users/arijit.kundu/projects/mercury-services-commons fetch origin --prune
git -C /c/Users/arijit.kundu/projects/mercury-services         fetch origin --prune
```

### D.3 Retrieving the five pull requests

Bitbucket REST, authenticated with the credential already stored for `git.dev.e2open.com`. The secret is read via `git credential fill` into a shell variable and never echoed.

```bash
cd /c/Users/arijit.kundu/projects/mercury-services-commons
CRED=$(printf 'protocol=https\nhost=git.dev.e2open.com\n\n' | git credential fill)
U=$(echo "$CRED" | grep '^username=' | cut -d= -f2-)
P=$(echo "$CRED" | grep '^password=' | cut -d= -f2-)      # never printed

for pr in 46 47 48; do
  curl -s -u "$U:$P" \
    "https://git.dev.e2open.com/rest/api/1.0/projects/INT/repos/mercury-services-commons/pull-requests/$pr" |
  python -c "import sys,json; d=json.load(sys.stdin); print(d['title'], d['state'], d['fromRef']['displayId'], '->', d['toRef']['displayId'], d['fromRef']['latestCommit'], (d.get('description') or '')[:3000])"
done

for pr in 1165 1166; do
  curl -s -u "$U:$P" \
    "https://git.dev.e2open.com/rest/api/1.0/projects/INT/repos/mercury-services/pull-requests/$pr" |
  python -c "import sys,json; d=json.load(sys.stdin); print(d['title'], d['state'], d['fromRef']['latestCommit'], (d.get('description') or '')[:3000])"
done
```

### D.4 Diffing the PRs

```bash
cd /c/Users/arijit.kundu/projects/mercury-services-commons
git log --oneline origin/feature/ION-12310-commons-cloudsdk-refactoring -12
git diff --stat 1293c50 099c2da                                  # PR #46
git diff        1293c50 099c2da -- 'cloud-sdk-api/*' 'cloud-sdk-aws/*' README.md ':(exclude)*/src/test/*'
git diff --stat 099c2da 6d7785f                                  # PR #47
git diff --stat 6d7785f 1313d1b                                  # PR #48
git diff        6d7785f 1313d1b -- ':(exclude)*/src/test/*'
git show 1313d1b:cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/database/impl/EnhancedDynamoRepositoryQueryTest.java

cd /c/Users/arijit.kundu/projects/mercury-services
git log --oneline origin/develop -8
git diff --stat 167d9dd01f~1 be76d24a0a                          # PR #1165
git diff        167d9dd01f~1 be76d24a0a -- ':(exclude)*/src/test/*'
git diff        be76d24a0a  316b5da457                           # PR #1166 (full, incl. tests)
```

### D.5 Reading pre- and post-fix source

```bash
cd /c/Users/arijit.kundu/projects/mercury-services-commons
git show b305acc:cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/AwsHttpClientWrapper.java
git show b305acc:cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/factory/S3ClientFactory.java
git show 1293c50:cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsMessagingClient.java
sed -n '1,80p'     cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/BaseAwsConfig.java
sed -n '290,340p'  cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/database/factory/DynamoRepositoryFactory.java
sed -n '60,200p'   cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/factory/MessagingClientFactory.java
sed -n '1,140p'    cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/factory/StorageClientFactory.java
sed -n '70,130p'   cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/config/AwsStorageConfig.java
sed -n '490,520p;895,925p;975,1020p' \
                   cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/database/impl/EnhancedDynamoRepository.java

cd /c/Users/arijit.kundu/projects/mercury-services
git show be76d24a0a:visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/config/VisibilityApplicationInjector.java
git show 167d9dd01f~1:visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/processor/sqs/SqsMessageHandler.java
git show 167d9dd01f~1:visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/processor/threading/BoundedThreadPool.java
git show 316b5da457:visibility/visibility-commons/src/main/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDao.java
sed -n '60,140p' visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/gis/OutboundGenerator.java
grep -n "createAndSendBatchTransactions" -B 25 -A 25 \
  visibility/visibility-outbound/src/main/java/com/inttra/mercury/visibility/outbound/processor/OutboundMultiTransactionProcessor.java
```

### D.6 Establishing that no HTTP client is shared (§2.1) and sizing the compat blast radius (§8.3)

```bash
cd /c/Users/arijit.kundu/projects/mercury-services-commons
# every httpClient construction site
grep -rn "AwsHttpClientWrapper\|defaultSyncClient\|httpClient(" --include=*.java \
     cloud-sdk-aws/src/main/java | grep -v "/test/"
# the decisive negative: nothing in the SDK closes an AWS client
grep -rn "\.close()\|closeQuietly\|AutoCloseable\|Closeable" --include=*.java \
     cloud-sdk-aws/src/main/java cloud-sdk-api/src/main/java | grep -v "/test/"
#   -> only DynamoDbAdminCommand.java:204 (a CLI admin path, not in these services)

# remaining unbounded pagination (D-2)
grep -nE "\.items\(\)|\.stream\(\)|flatMap\(page|Collectors\.toList|PageIterable|scan\(" \
     cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/database/impl/EnhancedDynamoRepository.java

# backward compatibility
grep -rln "implements QuerySpec\|QuerySpec {"  --include=*.java .
grep -rln "implements MessagingClient"         --include=*.java .
grep -rn  "new MessagingClient<\|implements MessagingClient" --include=*.java \
     /c/Users/arijit.kundu/projects/mercury-services
grep -rn "mercury.commons.version\|<artifactId>cloud-sdk" --include=pom.xml \
     /c/Users/arijit.kundu/projects/mercury-services | grep -v target
```

### D.7 Parsing the supplied CSV (§1.2, §1.3)

```bash
cd "C:/Users/arijit.kundu/OneDrive - WiseTech Global/Documents/platform/aws-upgrade/12.visibility/issues/"
python - <<'PYEOF'
import csv, re, collections
csv.field_size_limit(10**9)
rows = list(csv.reader(open("log-analytics-results-2026-08-04 (3).csv",
                           encoding="utf-8", errors="replace", newline="")))[1:]
svc   = re.compile(r"services\.([a-z0-9]+)\.Default\w+Client\.(\w+)")
appts = re.compile(r"\[(2026-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d)\]")   # in-message app clock
def cls(m):
    for k in ("OutOfMemoryError","Crc32Mismatch","Connection pool shut down",
              "ApiCallTimeoutException","SocketTimeoutException"):
        if k in m: return k
    return "other"
pair, buckets = collections.Counter(), collections.Counter()
for ts, msg in rows:
    m = svc.search(msg); a = appts.search(msg); t = a.group(1) if a else ts
    pair[(cls(msg), f"{m.group(1)}.{m.group(2)}" if m else "-")] += 1
    buckets[(t[:16], cls(msg))] += 1
for k, v in pair.most_common(): print(v, k)          # service x failure-class matrix
for k in sorted(buckets): print(k, buckets[k])       # per-minute timeline
PYEOF
```

This produced the **9,308 SQS / 20 S3 / 0 DynamoDB** pool-shutdown split — the cleanest single refutation of the shared-pool theory.

### D.8 Verifying the Apache `catch (Error)` handler (§3.2)

```bash
ls ~/.m2/repository/org/apache/httpcomponents/httpclient/        # -> 4.5.14 present
cd /tmp && mkdir -p hcchk && cd hcchk
unzip -o -q ~/.m2/repository/org/apache/httpcomponents/httpclient/4.5.14/httpclient-4.5.14.jar \
      org/apache/http/impl/execchain/MainClientExec.class
javap -p -c org/apache/http/impl/execchain/MainClientExec.class | sed -n '600,660p'
#   1226: astore 12
#   1229: getfield        connManager
#   1232: invokeinterface HttpClientConnectionManager.shutdown:()V
#   Exception table:  327 1107 1226  Class java/lang/Error      <- THE MECHANISM
```

### D.9 CloudWatch Logs validation (§1.1)

```bash
export AWS_PROFILE=642960533737_INTTRA2-QATeam AWS_REGION=us-east-1
aws sts get-caller-identity

# locating the log group - it is NOT a per-service group
aws logs describe-log-groups --query 'logGroups[].[logGroupName,retentionInDays,storedBytes]' --output text
aws logs describe-log-streams --log-group-name inttra2-ecs-logs \
    --order-by LastEventTime --descending --max-items 40 \
    --query 'logStreams[].logStreamName' --output text
#   -> group inttra2-ecs-logs, streams VisibilityOutbound-latest-qa/*, retention 400 days
```

Helper used for every Insights query (start, poll to `Complete`, print):

```bash
runq() {                       # runq <startISO> <endISO> <query-string>
  S=$(date -u -d "$1" +%s); E=$(date -u -d "$2" +%s)
  QID=$(aws logs start-query --log-group-name inttra2-ecs-logs \
        --start-time $S --end-time $E --query-string "$3" --query queryId --output text)
  for i in $(seq 1 80); do
    R=$(aws logs get-query-results --query-id "$QID")
    ST=$(echo "$R" | python -c "import sys,json;print(json.load(sys.stdin)['status'])")
    [ "$ST" = "Complete" ] && break
  done
  echo "$R"
}
```

The four queries behind §1.1 (a)–(d):

```bash
# (a) true onset + hourly rate
runq '2026-07-29T00:00:00' '2026-08-02T00:00:00' \
'filter @logStream like /VisibilityOutbound-latest-qa/
 | filter @message like /Connection pool shut down/
 | stats count(*) as n by bin(1h) as hr | sort hr asc | limit 120'

# (b) ordering: first OOM vs first pool death
runq '2026-07-29T00:00:00' '2026-08-05T00:00:00' \
'fields @timestamp, @logStream, @message
 | filter @logStream like /VisibilityOutbound-latest-qa/
 | filter @message like /OutOfMemoryError/ | sort @timestamp asc | limit 40'

runq '2026-07-30T11:00:00' '2026-07-30T12:30:00' \
'fields @timestamp, @logStream, @message
 | filter @logStream like /VisibilityOutbound-latest-qa/
 | filter @message like /Connection pool shut down/ | sort @timestamp asc | limit 5'

runq '2026-07-30T11:00:00' '2026-07-30T12:30:00' \
'filter @logStream like /VisibilityOutbound-latest-qa/
 | filter @message like /Connection pool shut down/ | stats count(*) by bin(1m)'

# (c) THE confirming stack trace - print the whole message, not just line 1
runq '2026-07-30T11:45:00' '2026-07-30T11:50:00' \
'fields @timestamp, @message
 | filter @logStream like /VisibilityOutbound-latest-qa/
 | filter @message like /OutOfMemoryError/ | sort @timestamp asc | limit 1'
#   -> EnhancedClientUtils.lambda$readAndTransformPaginatedItems$0(EnhancedClientUtils.java:137)

# (d) task generations, lifetimes, per-task volume
runq '2026-07-30T00:00:00' '2026-08-05T00:00:00' \
'filter @logStream like /VisibilityOutbound-latest-qa/
 | stats earliest(@timestamp) as first, latest(@timestamp) as last, count(*) as n by @logStream
 | sort first asc | limit 50'
```

```bash
# (e) ADDED AFTER REVIEW FEEDBACK — which pool died, per task?
#     This is the query that corrected the "DynamoDB survived" claim (§3.3).
runq '2026-07-30T00:00:00' '2026-08-05T00:00:00' 'filter @logStream like /VisibilityOutbound-latest-qa/
 | filter @message like /Connection pool shut down/
 | parse @message /services\.(?<svc>[a-z0-9]+)\.Default/
 | stats count(*) as n, earliest(@timestamp) as first, latest(@timestamp) as last by @logStream, svc
 | sort first asc | limit 40'
#   -> every task loses a DIFFERENT subset of clients; a shared pool cannot do that.
```

**Gotchas worth recording for the next investigation:**

* CloudWatch collapses a multi-line Java stack trace into **one** `@message`. Filtering on `/OutOfMemoryError/` returns records whose *first line* is an unrelated DEBUG entry — the OOM sits mid-message. Always print the full `@message` and search within it, otherwise the first OOM looks like a `BoundedThreadPool` debug line and you will miss it.
* `stats ... by bin(1m) as m` silently produced a null grouping key. Dropping the alias (`by bin(1m)`) worked.
* `earliest()` / `latest()` return `@timestamp` as **epoch millis**, unlike `fields @timestamp` which returns a formatted string. Convert with `datetime.datetime.fromtimestamp(ms/1000, datetime.UTC)`.
* **Only the *first* OOM carries a stack trace.** Subsequent `OutOfMemoryError`s in the same JVM print a bare `Exception in thread "..." java.lang.OutOfMemoryError` header with no frames — the JVM cannot allocate the trace array. Do not conclude from a frameless OOM that nothing useful is there; find the earliest one.
* Query (a) scanned 338 M records and (b) 535 M. Both complete in under a minute, but scope the window — Insights bills per byte scanned.

### D.10 Credential troubleshooting (first attempt, before the SSO refresh)

```bash
aws sts get-caller-identity --profile 642960533737_INTTRA2-QATeam   # -> SSO token expired
aws sts get-caller-identity --profile qa-team-static                # -> ExpiredToken
python -c "import configparser,os; p=configparser.RawConfigParser(); \
p.read(os.path.expanduser('~/.aws/credentials')); \
[print(s, sorted(p[s].keys())) for s in p.sections()]"
#   -> all four profiles carry aws_session_token, i.e. temporary SSO-derived credentials.
#      The 'qa-team-static' profile is not static and expires with the SSO session.
```

Jira remained unavailable throughout (`401` from `jira.dev.e2open.com`; `auth_reload` on the MCP context server did not recover it). ION-16431 itself was therefore never read — every finding above comes from the PRs, the source, the CSV, and CloudWatch.

---

## Addendum — Independent Review of the Incoming `commons` Changes (2026-08-13)

**Reviewer:** Copilot CLI (Claude Opus 4.8) · **Scope:** the 8 commits incoming from
`origin/feature/ION-12310-commons-cloudsdk-refactoring` (ION-16431, PRs #46/#47/#48), reviewed **independently
from git** before a planned rebase onto `develop`. This addendum is a **second-reviewer corroboration** of
§5.1–§5.3 and §8 above, written from the rebase author's seat. It does not restate the incident RCA; it
records where I independently agree, and the few things I want to add.

### A.1 What I verified from source (not from the PR descriptions)

Diffed `HEAD..origin/feature` directly (`git diff`, 13 files, +382/−40). The eight commits are all ION-16431,
authored 2026-08-05, and reduce to exactly three substantive changes plus a version bump:

| Change | Files (verified) |
|---|---|
| DynamoDB total-result cap | `cloud-sdk-api/QuerySpec.java` (+default `getMaxResultSize()`), `cloud-sdk-aws/DefaultQuerySpec.java` (+field/builder), `cloud-sdk-aws/EnhancedDynamoRepository.java` (effective-limit + early-return rewrite) |
| Closeable messaging | `cloud-sdk-api/MessagingClient.java` (`extends AutoCloseable`), `cloud-sdk-aws/SqsMessagingClient.java` (`close()` → `sqsClient.close()`) |
| HTTP-client builder mode | `cloud-sdk-aws/AwsHttpClientWrapper.java` (`isBuilder`, `ofSyncBuilder`, `ofAsyncBuilder`), `cloud-sdk-aws/storage/factory/S3ClientFactory.java` (builder-vs-instance branch) |
| Version | root `pom.xml` `→ 1.0.29-SNAPSHOT`, `README.md` `v1.0.29-SNAPSHOT` block |

### A.2 Agreement: the DynamoDB `maxResultSize` change is the load-bearing fix

I reached the same conclusion as §5.3 / §10 **independently from the code**, and the reasoning holds up under
a second read:

* The rewrite replaces `table.query(request).items().stream().collect(toList())` (drain **all** pages into
  heap) with an explicit page loop that **returns early** once `resultCap` items are collected. Because
  `PageIterable` is lazy — the next `Query` RPC fires only when the iterator advances — the early `return`
  genuinely stops pagination. Both **heap** and **RCU** are bounded. This is precisely the defect the OOM
  stack trace in §1.1(c) names (`readAndTransformPaginatedItems`), so this change, and only this change,
  closes the confirmed root cause.
* `effectiveLimit = min(limit, maxResultSize)` correctly keeps `limit` as *per-page* and `maxResultSize` as
  *total cap*, and the `maxResultSize == null` path yields `resultCap = Integer.MAX_VALUE`, i.e. **byte-for-byte
  identical behaviour** for every existing caller. The change is opt-in and safe to carry through the rebase.
* `getMaxResultSize()` added as a **`default`** interface method is the correct source- and binary-compatible
  API-evolution technique. I concur with §8.2 that this is a 🟢-risk addition.

### A.3 Agreement: the other two changes are not load-bearing for this incident

* **Builder mode (PR #46):** `httpClient(instance)` vs `httpClientBuilder(builder)` only decides whether
  `s3Client.close()` also closes the HTTP client. It has no bearing on Apache's `catch (Error) →
  connManager.shutdown()` path (§3.2), so it cannot prevent the pool death. As §5.1 notes, it mildly
  *increases* lifecycle coupling. I add two concrete defects I confirmed in the diff:
  * **Half-implemented (D-1):** `isBuilder` is honoured **only** in `S3ClientFactory`. Any other factory that
    receives a builder-mode `AwsHttpClientWrapper` and calls `getTypedClient()` will hand an
    `ApacheHttpClient.Builder` to an API expecting a built `SdkHttpClient` → `ClassCastException` at client
    construction. The abstraction is a runtime landmine until every factory branches on `isBuilder()`.
  * **Latent test breakage:** `AwsStorageConfig.getHttpClientForTesting()` (declared `SdkHttpClient`) will
    `ClassCastException` against a builder-mode config instead of the documented `IllegalStateException`.
  * **Recommendation:** keep the code (builder mode is the more idiomatic SDK v2 form) but either finish the
    abstraction across all factories or gate it, and fix the Javadoc that claims it protects against a
    DynamoDB timeout — it does the opposite.
* **`MessagingClient.close()` (PR #46):** a genuine and correct resource-leak fix, but unrelated to the
  incident. It is the **one genuinely breaking change** in the set: adding an abstract method to a published
  interface is a compile break for external implementors and an `AbstractMethodError` risk for pre-compiled
  ones. Blast radius inside `mercury-services` is nil (only `SqsMessagingClient` implements it), but the
  cross-repo sweep in §8.3 must complete before publishing. If any external implementor surfaces, prefer the
  `default` no-op form.

### A.4 Additions / gaps I want on the record

* **D-2 is still open and I confirmed it in the current source:** the cap was applied only to
  `query(QuerySpec)`. `export(projectionExpression, limit)` and the guarded `findAll()` scan still drain all
  pages via `stream().collect(toList())`, and `export()`'s `limit` carries the same per-page-vs-total
  semantic inversion this incident was caused by. Fixing `query()` alone leaves the same class of OOM
  reachable through two other methods. This should land before/with the SDK release, not after.
* **No cursor (D-3):** `query()` still returns a bare `List<T>`; a caller that receives exactly
  `maxResultSize` items cannot distinguish "capped, more exists" from "that was everything," and has no
  `lastEvaluatedKey` to resume. `findAll(limit, exclusiveStartKey, filter) → ScanResult<T>` in the same class
  is the pattern to mirror.
* **Minor:** `new ArrayList<>()` in the hot path could pre-size to `min(resultCap, 1024)` to avoid repeated
  growth on large caps.

### A.5 Bearing on the rebase (why this review gates it)

Because the **only** load-bearing change lives in `cloud-sdk-aws` / `cloud-sdk-api` **source**, and the
incoming `develop` OWASP work (ION-16376: Jetty 12.1.12, slf4j 2.0.18, logback-core 1.5.38) touches **only**
`pom.xml`, `commons/pom.xml`, and `README.md`, the DynamoDB fix **cannot be lost or altered** by the rebase —
it is carried verbatim by the feature-commit replay. The rebase's manual work is confined to a 3-file pom/
README union. Full plan, conflict map, and preservation checklist:
`mercury-services-commons/cloud-sdk-api/docs/2026-08-13-sdk-commons-rebase-analysis.md`.

**Net second-reviewer verdict:** I concur with the body of this document. Carry all three ION-16431 changes
through the rebase (they are safe and additive), treat the DynamoDB cap as the fix, and do not let the pom
conflict resolution drop it or the develop OWASP bumps. Land D-1 and D-2 before cutting the consumer release.
