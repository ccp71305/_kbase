# cloud-sdk gap register — open items as of 2026-09-02

**Scope:** gaps in `cloud-sdk-api` / `cloud-sdk-aws` that are still open at **`1.0.33-SNAPSHOT`**, collected from the
`watermill-publisher` AWS SDK 2.x upgrade (ION-16380) and the `visibility` upgrade (ION-12316).

**Why this file exists.** These items were previously scattered across consumer-side design documents in
`mercury-services`, where the cloud-sdk team does not read them. This register is the cloud-sdk-side backlog.

**Consumer-side sources**

| Document | Repo |
|---|---|
| `watermill-publisher/docs/2026-09-02-wmpub-upgrade-summary.md` §8, §12.10, §13 | `mercury-services` |
| `watermill-publisher/docs/2026-08-31-wm-aws-upgrade-refactor.md` §7 | `mercury-services` |
| `watermill-publisher/watermill-booking/docs/2026-07-30-waermillpub-awsupgrade-confluence-design.md` | `mercury-services` |

**Status legend:** 🔴 open, correctness risk · 🟠 open, usability/API-shape · ⚪ open, documented workaround in place

---

## Summary

| ID | Area | Title | Severity | Status |
|---|---|---|---|---|
| **SDK-1** | DynamoDB | `DefaultQuerySpec.queryExpression` is silently ignored by `EnhancedDynamoRepository` | 🔴 **Critical — caused a confirmed PROD outage** (ION-16663) | Open |
| **SDK-2** | DynamoDB | `sortKeyName` is never validated or used by `EnhancedDynamoRepository.query` | 🟠 Medium | Open |
| **SDK-3** | DynamoDB | A partially-specified sort key is silently dropped instead of rejected | 🔴 High | Open |
| **SDK-4** | DynamoDB | `query` and `queryPages` support different sort-key conditions and different guards | 🟠 Medium | Open |
| **SDK-5** | DynamoDB | `BETWEEN` sort-key condition unsupported — **contributing cause of SDK-1** | 🟠 Medium | Open |
| **SDK-6** | DynamoDB | `DynamoDbAdminCommand` derives the partition key from the bean property, ignoring `@DynamoDbAttribute` (was G3) | 🟠 Medium | Open |
| **SDK-7** | S3 | `StorageClient.getMetadata` returns an empty map for a missing **bucket** (was G4 residual) | 🟠 Medium | Open |
| **SDK-8** | S3 | `S3OperationException` extends `RuntimeException`, not `CloudSdkException` — no `isRetryable()` | 🔴 High | Open |
| **SDK-9** | Core | `CloudSdkException.isRetryable()` defaults to `true`; "true" is indistinguishable from "unset" | 🟠 Medium | Open |
| **SDK-10** | Notification | `workflow.MetaData` cannot be Jackson-deserialised and `parseJson` is strict | 🟠 Medium | Open |

**Closed since the 2026-07-30 design review:** G2 (`ApproximateReceiveCount` via
`ReceiveMessageOptions.messageSystemAttributeNames`) and the main body of G4 (`StorageClient.getMetadata` now issues a
real `headObject`). Both shipped in 1.0.33.

---

## SDK-1 🔴 `DefaultQuerySpec.queryExpression` is silently ignored by `EnhancedDynamoRepository`

> **Highest-priority item in this register.** This is the only gap here with a confirmed production incident behind it.

**Where:** `cloud-sdk-aws/src/main/java/.../database/impl/DefaultQuerySpec.java` (field, builder, getter) vs
`EnhancedDynamoRepository.java`.

`DefaultQuerySpec` declares and documents the property:

```java
/**
 * A custom query expression to use for the query.
 * If null, the query will be constructed using the other fields.
 */
private final String queryExpression;
```

It is consumed by `StandardDynamoRepository` (lines 679, 681, 691) but **never read by
`EnhancedDynamoRepository`** — which is the implementation returned by
`DynamoRepositoryFactory.createEnhancedRepository(...)` and therefore the one every `watermill-*` and `visibility`
module actually uses.

**Impact — this has already caused a production outage.** A caller migrating a legacy AWS SDK v1 call by moving the
expression string into `.queryExpression("…")` gets **no error, no warning, and a wrong result set**.

**Confirmed incident:** `visibility` / `ContainerEventOutboundDao.getUnprocessedTransactions`, PROD table
`Inttra2_prod_container_events_outbound`, IPF `5680` (earlier `4486`), on `cloud-sdk-aws-1.0.29-SNAPSHOT`.
Root-cause analysis: `visibility/docs/2026-08-21-vis-prod-issue.md`. Fix: ION-16663 / `8bd89dffbd`.

The DAO expressed a bounded key condition as a string:

```java
"integrationProfileFormatId = :hashKeyValue AND sequenceNumber BETWEEN :srtKeyLower AND :srtKeyUpper"
```

Pre-upgrade this string was handed to the AWS SDK v1 helper `queryWithSizeLimit(...)`, where it became the actual
DynamoDB **`keyConditionExpression`** — so the `BETWEEN` executed server-side and worked. The migration kept the DAO
source essentially unchanged but swapped the executor to `EnhancedDynamoRepository`. **The bound was lost purely in
the executor swap, not in the DAO source.** Bytecode evidence from the deployed jar:

| Class | `getQueryExpression` references inside `query()` |
|---|---|
| `EnhancedDynamoRepository` (what visibility is wired to) | **0** |
| `StandardDynamoRepository` | 3 |

The executed request degraded to `integrationProfileFormatId = 5680` only, `scanIndexForward = true`, capped at
`maxResultSize = 1000` — i.e. **the oldest 1000 rows from the start of the partition**, exactly the region the bound
was meant to exclude. Those rows referenced inbound `ContainerEvent`s already removed by the 400-day TTL, so outbound
processing stalled with:

```
java.lang.IllegalArgumentException: Could not find inbound transaction with ID ce:505efc6b-4cd8-4654-bc37-5a90c58a635a
```

Diagnosis was slow because an ops-run console query *did* apply `sequenceNumber >= cursor` and returned a clean result
set — the console and the application were not running the same query, and nothing in the application said so.

The fix had to move the **upper** bound to a client-side `removeIf`, because DynamoDB bars key attributes from
`FilterExpression` and `DefaultQuerySpec` cannot express `BETWEEN` (**SDK-5**). SDK-5 is therefore a direct
contributing cause: it is *why* callers reach for `queryExpression` at all.

A second, benign instance of the same trap exists in `ContainerEventDao.findById`
(`query(id, "id = :hashKeyValue", CONSISTENT)`), where the expression merely restates the partition key on a
partition-key-only table and is inert. That one shipped no defect — but it shows how naturally the pattern spreads.

**Requested fix (any one of):**
1. Throw `UnsupportedOperationException` from `EnhancedDynamoRepository.query` when `queryExpression` is non-empty; or
2. honour it by translating to a `filterExpression`; or
3. deprecate `queryExpression` on `DefaultQuerySpec` and javadoc it as *"`StandardDynamoRepository` only — ignored by
   `EnhancedDynamoRepository`"*.

Option 1 is preferred: fail loudly at the point of misuse.

---

## SDK-2 🟠 `sortKeyName` is never validated or used by `EnhancedDynamoRepository.query`

**Where:** `EnhancedDynamoRepository.query`, lines 418–421 and `buildSortKeyConditional`, lines 468–495.

```java
final QueryConditional conditional = querySpec.getSortKeyCondition() != null
    && querySpec.getSortKeyValue() != null
    ? buildSortKeyConditional(querySpec, partitionKeyValue)
    : QueryConditional.keyEqualTo(Key.builder().partitionValue(partitionKeyValue).build());
```

`getSortKeyName()` is not referenced. The DynamoDB enhanced client resolves the sort-key attribute name from the
`TableSchema` metadata for the index, so whatever the caller passes to `.sortKeyName(...)` is decorative.

**Impact.** A caller who supplies a **wrong or misspelt** `sortKeyName` gets a silently different query than they
believe they wrote. Their unit tests — which typically capture the `DefaultQuerySpec` and assert `getSortKeyName()` —
will happily pass, because they assert the value they put in.

**Requested fix:** validate `sortKeyName` against `schema.tableMetadata().indexSortKey(indexName)` (or
`primarySortKey()` for base-table queries) and throw `IllegalArgumentException` on mismatch. If validation is
undesirable, at minimum javadoc the property as advisory-only.

---

## SDK-3 🔴 A partially-specified sort key is silently dropped

**Where:** `EnhancedDynamoRepository.query`, lines 418–421 (same ternary as SDK-2).

If `sortKeyCondition` **or** `sortKeyValue` is null, the whole sort-key criterion is discarded and the query silently
degrades to partition-key-only.

**Why this is high severity.** The degraded query **succeeds** and returns a **superset** of the intended rows. There
is no exception and no log line. Callers that take `results.get(0)` — a very common pattern — will read a row belonging
to a different sort-key value. In `watermill-cargo-visibility-subscription` that would mean *resolving a subscription
to the wrong carrier* for a booking number or bill of lading shared between carriers. **==AK>> what is the call site ??** 2

Contrast with a **misspelt** condition, which correctly fails loudly:

```java
default -> throw new IllegalArgumentException("Unsupported sort key condition: " + …);
```

So the API is inconsistent: wrong-value fails fast, missing-value fails silently.

**Requested fix:** treat a partially-specified sort key as a programming error. **== AK>> quite ambiguous code suggestion below.**

```java
final boolean anySortKeyPart = querySpec.getSortKeyName() != null
        || querySpec.getSortKeyCondition() != null
        || querySpec.getSortKeyValue() != null;
final boolean allSortKeyParts = querySpec.getSortKeyName() != null
        && querySpec.getSortKeyCondition() != null
        && querySpec.getSortKeyValue() != null;
if (anySortKeyPart && !allSortKeyParts) {
    throw new IllegalArgumentException(
        "Incomplete sort key specification: name/condition/value must all be supplied or all omitted");
}
```

Ideally validate in `DefaultQuerySpec.Builder.build()` so the failure surfaces at construction time.

**Consumer-side note.** `watermill-cargo-visibility-subscription` was verified against DynamoDB Local on 2026-09-02 and
**does** supply all three parts, so it is not affected today. But the repository had **no test capable of detecting the
degradation** — every integration-test row shared a single `carrierInttraId`. Regression ITs that store two rows
differing only by sort key, plus a negative control asserting the degraded query returns both, are held in
`mercury-services` stash `dc17db80a1`. Any consumer relying on a GSI sort key should add the equivalent.

---

## SDK-4 🟠 `query` and `queryPages` diverge

| | `query` (L412) | `queryPages` (L844) |
|---|---|---|
| Guard | `sortKeyCondition != null && sortKeyValue != null` | `sortKeyName != null && sortKeyCondition != null && sortKeyValue != null` |
| Conditions supported | `BEGINS_WITH`, `>=`/`GE`/`GTE`, `>`/`GT`, `<=`/`LE`/`LTE`, `<`/`LT`, `=`/`EQ` | `BEGINS_WITH`, `=`/`EQ` **only** |
| `maxResultSize` | honoured | ignored |

A caller who switches from `query` to `queryPages` for memory reasons can find a previously working `>=` sort-key
condition now throws `IllegalArgumentException`, and `maxResultSize` silently stops applying.

**Requested fix:** extract the conditional-building and limit-resolution logic into one shared private method used by
both, so the two paths cannot drift.

---

## SDK-5 🟠 `BETWEEN` sort-key condition unsupported

`buildSortKeyConditional` throws for `BETWEEN`, because `DefaultQuerySpec` holds a single `CloudAttributeValue`:

```java
case "BETWEEN" -> throw new IllegalArgumentException(
        "BETWEEN sort key condition is not supported yet. Use separate >= and <= conditions instead.");
```

This fails loudly and the suggested workaround requires two round trips. **Requested fix:** add
`sortKeyUpperBoundValue` (or a `sortKeyRange(lower, upper)` builder method) and map to
`QueryConditional.sortBetween(...)`.

---

## SDK-6 🟠 `DynamoDbAdminCommand` partition-key naming ignores `@DynamoDbAttribute` *(was G3)*

The admin command derives the partition-key attribute name from the **bean property name** rather than the
`@DynamoDbAttribute` override.

`CargoVisibilitySubscription` has property `hashKey` annotated `@DynamoDbAttribute("id")`. Verified empirically on
1.0.33: `EntityTableMetadata.fromEntityClass(CargoVisibilitySubscription.class)` returns key schema attribute
**`hashKey`**, but the DAO reads and writes **`id`**.

GSIs *are* derived correctly (`billOfLading-carrierInttraId-index`, `bookingNumber-carrierInttraId-index`,
`subscriptionReference-index`, all `KEYS_ONLY`, capacity from `dynamoDbConfig` per ION-16650), and no TTL attribute is
derived (correct — the entity has no `@DynamoDbTtl`).

**Impact.** None on existing environments: every live table already exists with the `id` schema and the command is
describe-then-skip. The failure is confined to **standing up a brand-new environment**, where the table would be
created with the wrong key name and every DAO read would miss.

**Requested fix:** resolve the key attribute name through the same `TableSchema` metadata the enhanced client uses,
rather than by reflecting on the property name.

---

## SDK-7 🟠 `StorageClient.getMetadata` swallows a missing bucket

`getMetadata(bucket, key)` returns an **empty map** when the *bucket* does not exist; a missing *key* correctly throws.

**Impact.** A misconfigured bucket name is indistinguishable from an object that simply has no user metadata. Callers
must add their own bucket-existence check to tell a configuration error from an empty result.

**Requested fix:** propagate `NoSuchBucketException` (wrapped) rather than returning an empty map. If the current
behaviour is intentional, return `Optional<Map<String,String>>` so absence is explicit in the type.

---

## SDK-8 🔴 `S3OperationException` does not extend `CloudSdkException`

Every other cloud-sdk service exception extends `CloudSdkException` and therefore exposes `isRetryable()`.
`S3OperationException` extends `RuntimeException`, so **S3 is the only service without a retryability verdict.**

**Impact.** Every consumer must re-derive the verdict from the wrapped AWS exception. `watermill-commons`'
`AwsFailureClassifier` exists largely for this reason, and each consuming module has had to reimplement equivalent
logic. Getting it wrong in either direction is costly: classify a permanent failure as transient and the message
poison-loops; classify a transient failure as permanent and data is dropped.

**Requested fix:** make `S3OperationException extend CloudSdkException` and implement `isRetryable()` from the
underlying `S3Exception` (`statusCode() >= 500`, `SlowDown`, `RequestTimeout`, throttling → retryable;
`NoSuchKey`, `NoSuchBucket`, `AccessDenied`, `InvalidObjectState` → not retryable). This is a source-compatible change
for callers that catch `RuntimeException`.

---

## SDK-9 🟠 `CloudSdkException.isRetryable()` defaults to `true`

Because the default is `true`, a caller cannot distinguish *"the SDK has determined this is retryable"* from *"the SDK
has no opinion"*. Defaulting to `true` is the dangerous direction: an unclassified permanent failure is retried
forever.

**Requested fix:** expose the tri-state, e.g. `Optional<Boolean> retryable()` or a
`RetryVerdict { RETRYABLE, NOT_RETRYABLE, UNKNOWN }`, keeping `isRetryable()` as a deprecated convenience.

---

## SDK-10 🟠 `workflow.MetaData` cannot be Jackson-deserialised, and `parseJson` is strict

**Where:** `cloud-sdk-api/.../notification/workflow/MetaData`.

`javap` on 1.0.33 shows the class is `final`, with **no no-arg constructor and no setters** — only a static `parseJson`
and a nested `Builder`. So `objectMapper.readValue(body, MetaData.class)` is impossible, and `MetaData` cannot be a
field of any other Jackson-mapped type.

`parseJson` is additionally **strict**. Reproduced against a real production SQS envelope:

```
com.fasterxml.jackson.databind.exc.UnrecognizedPropertyException:
  Unrecognized field "notificationParties" (class …workflow.MetaData$Builder), not marked as ignorable
  (10 known properties: "exitStatus", "messageId", "parentWorkflowId", "timestamp", "fileName", …)
```

Producers routinely serialise a **domain** metadata object that carries extra fields alongside the 10 workflow ones
(`notificationParties`, `externalIdentifiers`, …). Every such envelope is rejected.

**Impact.** Each consumer must hand-write a bridge: parse into a lenient domain type, then rebuild the workflow type
field by field. `watermill-booking` (`WatermillBKTask.toWorkflowMetaData`) and
`watermill-cargo-visibility-subscription` (`CargoVisibilitySubscriptionPublisherTask.parseMetaData`) each carry a
near-identical copy. Any field added to `MetaData` must be manually propagated to every bridge or is silently lost.

**Requested fix (either):**
1. Configure the internal mapper with `FAIL_ON_UNKNOWN_PROPERTIES=false` (or annotate the `Builder` with
   `@JsonIgnoreProperties(ignoreUnknown = true)`) so `parseJson` tolerates producer-domain fields; **and/or**
2. add `@JsonPOJOBuilder` support so the type is directly Jackson-deserialisable by consumers using their own mappers.

Item 1 alone removes the need for every bridge and is a strictly widening, backward-compatible change.

---

## Related consumer-side gap (not a cloud-sdk defect)

**G5 — permanent-failure poison loop in `watermill-cargo-visibility-subscription`.** The delete-instead-of-loop fix
(`finalisePermanentFailure`) was applied only to `WatermillBKTask` and `WatermillBKAperakTask`. The cargo-visibility
task catches only `ReprocessibleException`; a permanent failure is rethrown as `RuntimeException`, escapes `execute`,
is merely logged by `SQSListener`, and the message is never deleted → redelivered → DLQ → redriven by
`DeadLetterService` → loops.

Listed here only because **SDK-8** is a contributing factor: had `S3OperationException` carried `isRetryable()`, the
permanent/transient split would have been unambiguous at the point of failure. Tracked for fixing in `mercury-services`
(see `2026-09-02-wmpub-upgrade-summary.md` §12.10), not in cloud-sdk.

---

## Suggested priority for the cloud-sdk backlog

| Priority | Items | Rationale |
|---|---|---|
| **P0** | SDK-1 | Confirmed PROD outage (ION-16663, visibility outbound stall). Fail-fast is a few lines. Fix before anything else |
| **P1** | SDK-3, SDK-8 | Silent wrong results or silent poison loops; both are cheap fail-fast changes |
| **P2** | SDK-10, SDK-6, SDK-7 | Forces duplicated consumer-side workarounds; SDK-6 blocks greenfield environments |
| **P3** | SDK-2, SDK-4, SDK-9 | API-shape and consistency; low runtime risk once P1 lands |
| **P4** | SDK-5 | Feature gap, not a defect — but see SDK-1: its absence is what drives callers to `queryExpression` |

SDK-1, SDK-2, SDK-3 and SDK-4 all live in the same ~80 lines of `EnhancedDynamoRepository.query` /
`buildSortKeyConditional` / `queryPages` and are best addressed as a single change.
