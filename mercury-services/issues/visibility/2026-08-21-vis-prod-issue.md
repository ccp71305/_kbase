# Visibility Outbound — Prod Issue Analysis: "Could not find inbound transaction" vs. Console Query Discrepancy

- **Date:** 2026-08-21
- **Module:** `visibility/visibility-outbound`, `visibility/visibility-commons`
- **Environment:** PROD (`Inttra2_prod_container_events_outbound`)
- **Affected IPF (this report):** `5680` (same class of failure previously seen on `4486`)
- **Deployed commons version (visibility):** `mercury.commons.version = 1.0.29-SNAPSHOT` (`visibility/pom.xml:24`)

---

## 1. Symptom

```
ERROR ... OutboundMultiTransactionProcessor: Failed to process SQS message
{"integrationProfileFormatId":5680,"transactionCount":570,"lastExecutionDatetime":1787462780297,
 "lastTransactionCreationDatetime":1787404082482,"locked":0,"transactionsPerFile":100,"timeLimitInMinutes":10},
 Outbound IPF: 5680
java.lang.IllegalArgumentException: Could not find inbound transaction with ID ce:505efc6b-4cd8-4654-bc37-5a90c58a635a
    at ...OutboundGenerator.getInboundContainerEvent(OutboundGenerator.java:196)
    at ...OutboundGenerator.lambda$createAndSendBatchTransactions$0(OutboundGenerator.java:102)
    ...
    at ...OutboundGenerator.createAndSendBatchTransactions(OutboundGenerator.java:104)
    at ...OutboundMultiTransactionProcessor.process(OutboundMultiTransactionProcessor.java:97)
```

The threshold cursor (`lastTransactionCreationDatetime`) is **`1787404082482`**. The application fails looking up
an **inbound** `ContainerEvent` `ce:505efc6b-4cd8-4654-bc37-5a90c58a635a` that no longer exists (TTL-deleted).

## 2. The Reported Discrepancy

The support/ops team reproduced the DynamoDB **Query** from the AWS console:

- Table: `Inttra2_prod_container_events_outbound`
- Partition key: `integrationProfileFormatId = 5680`
- Sort key: `sequenceNumber` **Greater than or equal to** `1787404082482` (String)
- Filters: none
- Iterated **all pages** → exported to `results (2).csv`

**Observation:** All records returned were within range; **no old record** was found that could reference a
TTL-deleted inbound event. So the console "could not reproduce" the application's failure.

> Question: *Why did the application find the old record `ce:505efc6b...` but the console query did not? Where is the
> disconnect? Is the deployed QuerySpec accurate?*

## 3. CSV Evidence (`results (2).csv`)

Programmatic analysis of the export:

| Metric | Value |
|---|---|
| Data rows | **4226** |
| Distinct `integrationProfileFormatId` | `5680` only |
| `sequenceNumber` timestamp — min | **1787404082482** (== cursor) |
| `sequenceNumber` timestamp — max | 1787582240279 |
| Rows with ts **< cursor** | **0** |
| Rows with ts **>= cursor** | **4226** |
| Rows where `inboundContainerEventId == ce:505efc6b-...` | **0** |
| Rows where `sequenceNumber` contains `ce:505efc6b-...` | **0** |
| Lexicographic min `sequenceNumber` | `1787404082482_ce:e40da339-c862-4245-ba91-1bb5bd05041c` |

**Key takeaways:**
1. Every row in the export is `>= cursor` — the console's `>= 1787404082482` sort-key condition **was enforced**
   (server-side, as expected).
2. The failing id `ce:505efc6b-...` is **absent** from the export. It therefore lives **below** the cursor
   (`sequenceNumber` timestamp `< 1787404082482`) — exactly the region the console query **excluded**.

## 4. Root Cause of the Discrepancy — The Two Queries Are Not Equivalent

The console query and the deployed application query are **not the same query**.

### 4.1 What the application code *intends*

`ContainerEventOutboundDao.getUnprocessedTransactions` (`visibility-commons`) builds a bounded key-condition:

```java
String sortKeyLowerLimit = creationTimestamp.getTime() + "_g";   // cursor
String sortKeyUpperLimit = Instant.now().minusMillis(100).toEpochMilli() + "_g";
String queryExpression =
    "integrationProfileFormatId = :hashKeyValue AND sequenceNumber BETWEEN :srtKeyLower AND :srtKeyUpper";

DefaultQuerySpec.builder()
    .partitionKeyName("integrationProfileFormatId").partitionKeyValue(...)
    .queryExpression(queryExpression)                       // <-- the intended bound
    .expressionAttributeValues(Map.of(":srtKeyLower", ..., ":srtKeyUpper", ...))
    .consistentRead(true)
    .limit(RESULT_SIZE_LIMIT).maxResultSize(RESULT_SIZE_LIMIT)   // 1000
    .build();
```

Note it sets **`queryExpression`** only — it does **not** set `sortKeyName`/`sortKeyCondition`/`sortKeyValue`,
and it does **not** set `filterExpression`.

### 4.2 What the deployed code *actually executes*

Visibility wires the **enhanced** repository:

- `VisibilityDynamoModule.createCompositeKeyRepository(...) -> DynamoRepositoryFactory.createEnhancedRepository(...)`
  → `EnhancedDynamoRepository` (`ContainerEventOutbound` = composite key `integrationProfileFormatId` + `sequenceNumber`).

The **deployed** `EnhancedDynamoRepository.query()` (verified by disassembling the shipped jar
`cloud-sdk-aws-1.0.29-SNAPSHOT`) does the following:

```java
final QueryConditional conditional =
    querySpec.getSortKeyCondition() != null && querySpec.getSortKeyValue() != null
        ? buildSortKeyConditional(...)
        : QueryConditional.keyEqualTo(Key.builder().partitionValue(partitionKeyValue).build()); // <-- TAKEN
...
if (querySpec.getFilterExpression() != null && !querySpec.getFilterExpression().isEmpty()) { // <-- FALSE
    requestBuilder.filterExpression(buildFilterExpression(querySpec));
}
```

**Bytecode confirmation (deployed 1.0.29 jar):**

| Class | `getQueryExpression` references in `query()` |
|---|---|
| `EnhancedDynamoRepository` (used by visibility) | **0** |
| `StandardDynamoRepository` (NOT used by visibility) | 3 |

Because the DAO only populated `queryExpression` (never `sortKeyCondition`/`sortKeyValue`/`filterExpression`), and the
enhanced `query()` **never reads `getQueryExpression()`**, the entire `BETWEEN` bound is **silently dropped**. The
executed request degrades to:

> **`integrationProfileFormatId = 5680`** only — **no sort-key restriction**, `scanIndexForward = true` (ascending),
> capped at `maxResultSize = 1000`.

That means the application reads the **oldest 1000** rows from the **start of the partition** — i.e. the region
with `sequenceNumber` timestamp **`< cursor`** — which is precisely the region the console query filtered out. Those
oldest outbound rows reference the oldest inbound `ContainerEvent`s, some of which have already been removed by the
inbound 400-day TTL → `getInboundContainerEvent` throws `IllegalArgumentException`.

### 4.3 The disconnect in one sentence

> The console query enforced `sequenceNumber >= cursor` and so never looked at the old rows; the deployed application
> query **does not enforce any sort-key bound at all** and reads oldest-first from the beginning of the partition, so
> it hits old rows (like the one referencing `ce:505efc6b-...`) that the console query excluded.

## 5. Why This Did Not Surface Before the AWS SDK 2.x Upgrade

Pre-upgrade (`git 9a04010f1d^`), `getUnprocessedTransactions` passed the **same** `queryExpression` string into the
AWS SDK v1 low-level helper `queryWithSizeLimit(...)`, where it became the DynamoDB **`keyConditionExpression`**. So
`BETWEEN` executed server-side and the lower/upper bounds were honored — the poller only ever read rows `>= cursor`
and advanced the cursor forward. The migration kept the identical `DefaultQuerySpec`/`queryExpression` shape but swapped
the executor to the **enhanced** repository, whose `query()` has no branch that reads `queryExpression`. The bound was
lost purely in the executor swap, not in the DAO source.

## 6. Answering the Specific Questions

1. **Why did the app find `ce:505efc6b...` but the console did not?**
   The app query has no sort-key bound (enhanced repo ignores `queryExpression`) and reads oldest-first; the console
   query applied `sequenceNumber >= 1787404082482`, excluding the older rows where `ce:505efc6b...` lives.

2. **Where is the disconnect / are we missing anything?**
   The two queries are not equivalent. To reproduce the app's behavior in the console, run **partition key only**
   (`integrationProfileFormatId = 5680`, no sort-key condition, ascending) **or** `sequenceNumber < 1787404082482`.
   The old rows (including the one referencing `ce:505efc6b...`) will appear at the top.

3. **Is the latest deployed code's QuerySpec definition accurate?**
   The DAO's `DefaultQuerySpec` is syntactically correct (proper `BETWEEN` + attribute values), but it is
   **semantically inert on the deployed enhanced-client path**: `cloud-sdk-aws 1.0.29-SNAPSHOT`
   `EnhancedDynamoRepository.query()` never consumes `getQueryExpression()`. Net effect: **the deployed query does not
   enforce the intended time-window bound** — so, functionally, **no, it is not accurate as deployed.**

## 7. Contributing Factor (Trigger)

Independent of the dropped bound, there is a retention mismatch that guarantees orphaned references exist:

- Inbound `ContainerEvent` TTL: **400 days** (`ContainerEventDao.DAYS_BEFORE_EXPIRING = 400`, reduced from `3*365`
  in commit `c68faab8ec`).
- Outbound `ContainerEventOutbound` TTL: **1095 days** (`ContainerEventOutboundDao.DAYS_BEFORE_EXPIRING = 3*365`).

Outbound rows outlive the inbound rows they point to by ~695 days. The dropped sort-key bound then forces the poller
to re-read those oldest outbound rows every cycle, so it deterministically hits inbound events already TTL-purged. It
also explains why the cursor never advances and the backlog never drains (the batch is a poison message).

## 8. How to Verify on the Console (repro steps)

1. Query `Inttra2_prod_container_events_outbound`, partition `integrationProfileFormatId = 5680`, **no sort-key
   condition**, **Sort ascending**, page through the first ~1000 items.
2. Confirm rows with `sequenceNumber` timestamp `< 1787404082482` are present, and that
   `ce:505efc6b-4cd8-4654-bc37-5a90c58a635a` appears as the trailing segment of one such `sequenceNumber` (and/or in
   `inboundContainerEventId`).
3. Cross-check that a Query for that inbound id against `Inttra2_prod_container_events` returns **no item** (TTL-expired).

## 9. Recommended Fixes (in priority order)

1. **Restore the sort-key bound on the enhanced path (DAO fix).** Replace the inert `queryExpression` usage with a
   form the enhanced client actually honors — either a supported range key condition or a real `filterExpression`
   (set `.filterExpression(...)`, not `.queryExpression(...)`). Add a DAO integration test asserting that rows with
   `sequenceNumber < cursor` are excluded. *(This is the primary regression fix.)*
2. **Add first-class `BETWEEN` support to `EnhancedDynamoRepository`** in `mercury-services-commons`
   (map to `QueryConditional.sortBetween(...)`), since any migrated DAO relying on `queryExpression` on the enhanced
   path is silently broken. Currently `buildSortKeyConditional` explicitly throws "BETWEEN ... not supported yet."
3. **Make `getInboundContainerEvent` non-fatal per record** — skip/dead-letter an orphaned outbound row instead of
   throwing, so one missing inbound cannot poison the entire IPF batch/SQS message.
4. **Align the two TTLs** (or guarantee outbound rows are processed well within the 400-day inbound retention) to
   eliminate orphaned references at the source.

## 10. Evidence Index

- `results (2).csv` — 4226 rows, all IPF 5680, all `ts >= 1787404082482`, target id absent (§3).
- `ContainerEventOutboundDao.getUnprocessedTransactions` — builds `queryExpression` BETWEEN; sets no
  `sortKeyCondition`/`filterExpression` (§4.1).
- `VisibilityDynamoModule.createCompositeKeyRepository` → `createEnhancedRepository` (§4.2).
- Deployed jar `cloud-sdk-aws-1.0.29-SNAPSHOT`: `EnhancedDynamoRepository.query()` has **0** `getQueryExpression`
  references (disassembly); `StandardDynamoRepository` has 3 (§4.2).
- Pre-upgrade DAO (`git 9a04010f1d^`) passed `queryExpression` to SDK-v1 `queryWithSizeLimit` as
  `keyConditionExpression` (§5).
- TTL constants: `ContainerEventDao.DAYS_BEFORE_EXPIRING = 400` (commit `c68faab8ec`) vs
  `ContainerEventOutboundDao.DAYS_BEFORE_EXPIRING = 3*365` (§7).

## 11. Related Issues & Blast Radius

Beyond the single failing query, the same defect class and adjacent gaps exist. Each is listed with
severity and status.

### 11.1 Other DAOs using the silently-dropped `queryExpression` on the enhanced client
- **`webbl/.../dao/BLDao.java:28`** — `load(id)` builds `.queryExpression("id = :hashKeyValue")` and is wired
  to the **enhanced** repository (`WebBLDynamoModule` → `createEnhancedRepository`). The `queryExpression`
  is ignored exactly as in the outbound DAO.
  - **Severity: currently benign.** The dropped expression only restates the partition-key equality, which is
    exactly what the enhanced `query()` falls back to (`keyEqualTo(partitionValue)`), so results are correct.
    It also never binds `:hashKeyValue` (no `expressionAttributeValues`), confirming the placeholder is dead.
  - **Risk:** latent trap — if anyone later adds a sort-key range or filter into this string expecting it to
    take effect, it will be silently dropped, reproducing this incident. **Recommend** removing the
    `queryExpression` and relying on the explicit partition-key query for clarity.
- A repo-wide scan found **no other** production `.queryExpression(...)` usages. All other DAOs express sort
  conditions through the supported `sortKeyCondition` values (`EQ`, `BEGINS_WITH`, `>=`), which the enhanced
  client honors — e.g. `RegistrationDao` (`>=`), `ContainerEventPendingDao` (`BEGINS_WITH`),
  `BookingDetailDao`/`SubscriptionsDao`/`BookingDao`/`CargoVisibilitySubscriptionDao` (`EQ`).

### 11.2 Systemic root: enhanced repository silently ignores `queryExpression`
- `EnhancedDynamoRepository.query()` never reads `getQueryExpression()` (0 references, verified in deployed
  `cloud-sdk-aws-1.0.29`). It does **not** throw when an unsupported `queryExpression` is supplied — it
  silently degrades to a partition-key-only read.
- **Severity: high (systemic).** Any current or future migrated DAO relying on `queryExpression` for a
  sort-key/filter constraint is silently broken with no error surfaced.
- **Recommend (commons):** make `query()`/`queryPages()` **fail-fast** (throw `UnsupportedOperationException`)
  when a `queryExpression` is present but unconsumed, so misuse is loud, not silent.

### 11.3 Enhanced client has no `BETWEEN` sort-key conditional
- `EnhancedDynamoRepository.buildSortKeyConditional` throws *"BETWEEN sort key condition is not supported yet"*,
  and `queryPages()` throws *"BETWEEN not yet implemented"*.
- **Severity: medium.** No DAO can express a native two-sided sort-key range on the enhanced client; callers
  must fall back to `>=` plus client-side trimming (as done here) which is less efficient and easy to get wrong.
- **Recommend (commons):** implement `BETWEEN` → `QueryConditional.sortBetween(lowerKey, upperKey)` (requires
  `DefaultQuerySpec` to carry a second/upper sort value). This is the durable fix that lets the outbound DAO
  express both bounds server-side.

### 11.4 `queryPages()` shares the same gaps (latent)
- `EnhancedDynamoRepository.queryPages()` also ignores `queryExpression` and throws for `BETWEEN`.
- **Severity: low today** (no production caller found), but latent — any future paginated DAO would inherit the
  identical silent-drop / unsupported-range behavior.

### 11.5 Poison-message / whole-IPF abort is independent of the query bound
- Even with the bound restored, a single in-window outbound row that references a TTL-deleted inbound event
  still makes `OutboundGenerator.getInboundContainerEvent` (`OutboundGenerator.java:196`) throw
  `IllegalArgumentException`, which aborts the entire `.map(...).toList()` for the IPF
  (`OutboundGenerator.java:101-104`). `OutboundMultiTransactionProcessor.process` re-throws as
  `ProcessingException`, the SQS message is not deleted, and the threshold is unlocked with `0` processed and
  the unchanged cursor — so the message is redelivered indefinitely and the cursor never advances.
- **Severity: high (resilience).** Orphans can still arise from reprocessing of historical inbound events
  (`ReprocessService`), retroactive subscription changes, or the TTL mismatch below.
- **⚠️ CORRECTION — NOT actually implemented (superseded by §16).** This bullet previously stated that
  `getInboundContainerEvent` had been replaced by a skip-and-continue `toOutboundMetaDataOrSkip`. Production
  log verification on 2026-08-24 proved that change **is not in the shipped build, nor in the source tree** —
  `getInboundContainerEvent` (`OutboundGenerator.java:193-202`) still **throws**, and it is still called
  inside the stream at `OutboundGenerator.java:102`, so a single orphan still poisons the whole IPF batch.
  Only Fix A (the query bound, §12.1) was actually implemented and deployed. See **§16** for the evidence and
  the remaining work.

### 11.6 Inbound/outbound TTL retention mismatch
- Inbound `ContainerEvent` TTL = **400 days**; outbound `ContainerEventOutbound` TTL = **1095 days** (§7).
- **Severity: medium.** Guarantees outbound rows can outlive the inbound rows they reference, continuously
  producing the orphans that trigger §11.5.
- **Deferred (product/retention decision, no longer correctness-critical):** with §11.5 now fixed, orphaned
  references are skipped gracefully, so this is an optimization rather than a defect. The mismatch can be
  resolved either by lowering outbound retention to 400 d or raising inbound retention — a data-retention /
  compliance decision that should not be made unilaterally in code. Left unchanged pending that decision.

### 11.7 Test-coverage gap pattern (false-confidence ITs)
- The pre-existing `ContainerEventOutboundDaoIT.returnsRowsInWindow` only asserted an in-window row is
  returned; it never inserted an out-of-range row to assert **exclusion**, so it passed against the buggy
  code. This is why the regression shipped.
- **Severity: medium (process).** Other range/filter DAO ITs may share this gap.
- **Action taken:** added `excludesRowsBelowCursor` and `excludesRowsNewerThanUpperBound` (see §12).
  **Recommend:** audit sibling DAO ITs to add negative (exclusion) assertions for every bounded query.

## 12. Fix Implemented & Validated (this change)

Two visibility-side fixes were implemented and tested. The commons cloud-sdk hardening (§11.2/§11.3/§11.4)
is deferred to a separate session per decision.

### 12.1 Fix A — restore the query bound (`ContainerEventOutboundDao.getUnprocessedTransactions`)
- Replaced the ignored `.queryExpression("... sequenceNumber BETWEEN ...")` with a native, server-side
  lower bound: `.sortKeyName("sequenceNumber").sortKeyCondition(">=").sortKeyValue(<cursor>_g)`.
- Enforced the upper bound (`now - TIME_DELAY_IN_MILLISECONDS`) **client-side**
  (`results.removeIf(ts > upperBoundMillis)`) because DynamoDB forbids the sort key in a `FilterExpression`
  and the enhanced client has no `BETWEEN` conditional. Rows return oldest-first, so this only trims the
  most-recent tail. Results are wrapped in a mutable `ArrayList` for the trim + existing dedup logic.
- Updated the Javadoc to warn that `queryExpression` is a no-op on the enhanced-client path.
- Tests (`ContainerEventOutboundDaoIT`, DynamoDB Local): `excludesRowsBelowCursor`,
  `excludesRowsNewerThanUpperBound`.

### 12.2 Fix B — batch resilience to orphaned inbound (`OutboundGenerator`) — ⚠️ NOT SHIPPED (see §16)
> **This fix was documented as done but was never actually implemented.** Production verification on
> 2026-08-24 (§16) confirmed `OutboundGenerator` still throws on a missing inbound and still poisons the
> whole IPF batch. Treat the description below as the *intended* design, not the current state.

- **Intended:** Replace `getInboundContainerEvent` (which throws `IllegalArgumentException` on a missing
  inbound) with `toOutboundMetaDataOrSkip`, which logs at ERROR and returns `null` so the single orphaned
  outbound row is filtered out and the rest of the IPF batch proceeds. This stops the poison-message loop and
  lets the cursor advance.
- **Intended test:** `OutboundGeneratorTest.skipsOrphanedInboundWithoutFailingBatch` — a 3-row batch with one
  orphan writes the 2 valid transactions and does not throw.
- **Actual state:** neither `toOutboundMetaDataOrSkip` nor the test exist in the code; `getInboundContainerEvent`
  is unchanged and still called from the stream at `OutboundGenerator.java:102`. **Still to be done — §16.4.**

### 12.3 Validation
- **Fix A red→green:** against the unfixed DAO, `UnprocessedTransactions` ran 4 with **2 failures**
  (`old-orphan`, `too-new` wrongly returned); after the fix, all pass.
- `mvn -pl visibility/visibility-commons verify`: **459 unit (1 pre-existing skip) + 41 IT, 0 failures**.
- `mvn -pl visibility/visibility-outbound test`: **43 unit (2 pre-existing skips), 0 failures**.
- Both builds: **BUILD SUCCESS**.

### 12.4 Boundary-semantics equivalence: `>=` fix vs. pre-upgrade 1.x `BETWEEN`

A follow-up question was raised on whether the `>=` fix changes the include/exclude semantics of the
query window relative to the pre-upgrade AWS SDK 1.x code. **It does not — the fix restores the original
semantics; it does not alter them.** Verified by comparing the pre-upgrade source (`git 9a04010f1d^`)
against the current fix.

**Lower bound — identical (inclusive):**

| | Lower-bound expression | Semantics |
|---|---|---|
| Pre-upgrade 1.x | `sequenceNumber BETWEEN :srtKeyLower AND :srtKeyUpper` (server-side `keyConditionExpression`), `srtKeyLower = creationTimestamp.getTime() + "_g"` | `BETWEEN` is inclusive on the low end → effectively `sequenceNumber >= <cursor>_g` |
| Current fix | `.sortKeyCondition(">=").sortKeyValue(<cursor>_g)` (native server-side condition) | inclusive `>=` on the **same** `<cursor>_g` value |

The lower-bound value (`creationTimestamp.getTime() + "_g"`) is **byte-for-byte identical** in both
versions, so the `>=` is an exact restoration of the `BETWEEN` low end.

**Upper bound — identical semantics (inclusive), enforcement relocated:**

| | Upper-bound expression | Semantics |
|---|---|---|
| Pre-upgrade 1.x | `... AND ... :srtKeyUpper` inside `BETWEEN` (server-side), `srtKeyUpper = (now - TIME_DELAY)_g` | inclusive `<= (now-delay)_g`, enforced by DynamoDB |
| Current fix | client-side `results.removeIf(sequenceNumber.compareTo(<upper>_g) > 0)` | inclusive `<= (now-delay)_g`, enforced in-process |

The upper bound could **not** remain a server-side key condition: `DefaultQuerySpec` exposes only one
sort-key condition (spent on the `>=` lower bound), and DynamoDB forbids key attributes in a
`FilterExpression`. It is therefore enforced client-side, but the boundary result is identical
(inclusive `<= upper`, same `_g` value). Because rows return oldest-first (default ascending
`ScanIndexForward`) under `limit(1000)`, any row `> upper` sorts last and is only ever fetched when
fewer than 1000 in-window rows exist — so the client-side trim never drops an in-window record.

**The `_g` sentinel is unchanged** in both versions, so same-millisecond boundary handling is identical:
`<millis>_g` sorts immediately after every real `<millis>_<id>`, so the inclusive `>=`/`<=` on the `_g`
value consistently treats the boundary millisecond the same way pre- and post-upgrade.

**Conclusion:** the SDK-2.x regression was never an include/exclude semantics change — it was that the
`BETWEEN` bound was passed via `queryExpression`, which the enhanced client silently ignored (§4, §5).
The `>=` rewrite makes the lower bound take effect again with the **exact same inclusivity** as the 1.x
`BETWEEN`, and the client-side upper-bound check preserves the inclusive upper. No behavioral drift is
introduced by the fix.

**Residual note (not a regression):** correctness of the "oldest contiguous 1000" read relies on
DynamoDB's default ascending `ScanIndexForward`, which is left implicit (as it was pre-upgrade). Making
it explicit and asserting sort-key order in a test would harden this; tracked as an optional follow-up.

**Scope note:** these restore correct behavior on the deployed enhanced client (commons 1.0.29). The commons
`BETWEEN`/`sortBetween` + fail-fast hardening (§11.2/§11.3), `webbl/BLDao` cleanup (§11.1), and the TTL
retention decision (§11.6) remain as separately-tracked follow-ups.

---

## 13. Step-by-step: "If the SDK throws on `BETWEEN`, why did the query silently return wrong results instead of erroring?"

This is the most common point of confusion, so it is walked out in full below. The short answer:
**the exception and the silent-drop are two different code paths, and the visibility DAO only ever took
the silent-drop path.** The `BETWEEN` that throws is a *structured sort-key condition*; the `BETWEEN` the
DAO wrote was *free text inside `queryExpression`* — a field the enhanced client never reads. The two
never meet.

Everything below is for the **only** repository visibility uses: `EnhancedDynamoRepository`
(all visibility modules wire `DynamoRepositoryFactory.createEnhancedRepository(...)` — there is no
`StandardDynamoRepository` anywhere in `visibility/`). Bytecode references are from the deployed
`cloud-sdk-aws-1.0.29-SNAPSHOT` jar.

### 13.1 First, distinguish the two things both called "BETWEEN"

There are two *completely different* ways a caller could express a range, and they are handled by
different fields on `DefaultQuerySpec`:

| # | How the range is expressed | Field(s) set on the spec | What the enhanced client does with it |
|---|---|---|---|
| **A** | **Structured** sort-key condition | `.sortKeyCondition("BETWEEN")` **+** `.sortKeyValue(...)` | Enters `buildSortKeyConditional`'s `switch`, hits the `BETWEEN` case → **throws** `IllegalArgumentException("BETWEEN sort key condition is not supported yet...")` |
| **B** | **Free-text** key-condition string | `.queryExpression("... BETWEEN :lo AND :hi")` **+** `.expressionAttributeValues(...)` | `query()` **never reads `getQueryExpression()`** → the string (and its placeholders) are ignored → **no error, no bound** |

The pre-fix visibility DAO used **path B**. It never set `sortKeyCondition`/`sortKeyValue`, so it never
went near the `switch` that throws. **The exception in path A is therefore irrelevant to what actually
ran** — it guards a door the DAO never walked through.

### 13.2 Trace the pre-fix `DefaultQuerySpec` through `EnhancedDynamoRepository.query()`

The pre-fix spec (path B) had exactly these fields populated:

```java
DefaultQuerySpec.builder()
    .partitionKeyName("integrationProfileFormatId").partitionKeyValue(ipfId)
    .queryExpression("integrationProfileFormatId = :hashKeyValue "
                   + "AND sequenceNumber BETWEEN :srtKeyLower AND :srtKeyUpper")   // ← set
    .expressionAttributeValues(Map.of(":hashKeyValue", ipfId,
                                      ":srtKeyLower", <cursor>_g,
                                      ":srtKeyUpper", <now-delay>_g))              // ← set
    .consistentRead(true).limit(1000).maxResultSize(1000)
    .build();
// NOT set: sortKeyName, sortKeyCondition, sortKeyValue, filterExpression, indexName
```

Now step through what `query()` reads, in order:

1. **Build the key condition.** It checks the *structured* fields:
   ```
   if (getSortKeyCondition() != null && getSortKeyValue() != null)
        conditional = buildSortKeyConditional(...);   // NOT taken — both are null
   else
        conditional = QueryConditional.keyEqualTo(partitionValue);   // ← TAKEN
   ```
   Because the DAO set neither `sortKeyCondition` nor `sortKeyValue`, the condition collapses to
   **partition key equality only**: `integrationProfileFormatId = 5680`. No sort-key bound.
   *(And because `buildSortKeyConditional` is never called, its `BETWEEN`-throw is never reached.)*

2. **`getQueryExpression()` is never called.** There is no line in `query()` that reads it. The entire
   `"... BETWEEN :srtKeyLower AND :srtKeyUpper"` string is dead on this path. So the only place that
   *references* the `:srtKeyLower` / `:srtKeyUpper` placeholders does not execute.

3. **`expressionAttributeValues` has nothing to bind to.** That map is not a condition by itself — it is
   only a lookup table for placeholders **inside an expression**. The enhanced client reads it in exactly
   one method, `buildFilterExpression(...)` (via `getExpressionAttributeValuesAsAws()`), and that method
   runs only when `getFilterExpression() != null`. Here `filterExpression` is null, so
   `buildFilterExpression` is never invoked. The three map entries — including both bounds — are
   **orphaned**: no expression consumes them.

4. **Filter step is skipped.** `getFilterExpression()` → null → no `filterExpression` is attached.

5. **Request is executed** as: `keyEqualTo(integrationProfileFormatId = 5680)`,
   `scanIndexForward = true` (ascending), `limit = 1000`. DynamoDB happily returns the **oldest 1000
   rows of the partition** — a perfectly valid query that simply isn't the one we intended.

### 13.3 Why no exception surfaced anywhere

- **Not from DynamoDB:** the request that reached DynamoDB was a valid partition-key query; there is no
  malformed expression in it (the bad expression was dropped *before* the request was built).
- **Not from the enhanced client:** `query()` does not validate or reject an unrecognised
  `queryExpression`; it simply never looks at it. There is no "unknown field" guard.
- **Not from the `BETWEEN` guard:** that guard lives inside `buildSortKeyConditional` (path A), which is
  only reached when `sortKeyCondition` is set. It was null, so the guard never ran.

The result: **a silent semantic error**, not a crash. The code returned the wrong rows (oldest-first,
unbounded) with a `200 OK` from DynamoDB.

### 13.4 Why the wrong rows caused the visible production failure

Reading oldest-first from the start of the partition means the query returns the *oldest* outbound rows —
the ones most likely to reference inbound `ContainerEvent`s already deleted by the 400-day inbound TTL
(§7). `OutboundGenerator.getInboundContainerEvent` then threw `IllegalArgumentException("Could not find
inbound transaction ...")`, poisoning the whole IPF batch and stalling the cursor. So the *only*
exception observed in prod came from the **application** (missing inbound lookup), **not** from the SDK —
another reason the "SDK throws on BETWEEN" intuition doesn't match the observed symptom.

### 13.5 Why the fix is correct on this same path

The fix stops relying on the ignored `queryExpression` field and instead sets the **structured** field the
enhanced client *does* read:

```java
.sortKeyName("sequenceNumber").sortKeyCondition(">=").sortKeyValue(<cursor>_g)
```

In step 1 above, `getSortKeyCondition()`/`getSortKeyValue()` are now non-null, so `buildSortKeyConditional`
**is** called; its `switch` has a real `">="` case → `QueryConditional.sortGreaterThanOrEqualTo`, enforced
**server-side**. The upper bound is applied in Java (`results.removeIf(seq > upper)`) because the enhanced
client accepts only one structured sort-key condition and DynamoDB forbids a key attribute in a
`filterExpression`. Note the fix deliberately does **not** use `.sortKeyCondition("BETWEEN")` — that is
path A, which would hit the throw; `">="` + client-side trim is the supported equivalent.

### 13.6 One-paragraph summary

The SDK throws on `BETWEEN` **only** when `BETWEEN` is supplied as a structured `sortKeyCondition`
(path A). The visibility upgrade instead put `BETWEEN` inside a free-text `queryExpression` string
(path B), which `EnhancedDynamoRepository.query()` never reads. With no structured sort condition set, the
query degraded to partition-key-only (oldest 1000, ascending), the bound placeholders in
`expressionAttributeValues` had no expression to bind to, and — crucially — the code path containing the
`BETWEEN` guard was never entered. So the failure mode was a **silent wrong-results** query, not an
exception. The fix re-expresses the lower bound as a structured `>=` (honored server-side) plus a
client-side upper-bound trim.

---

## 14. The three code states, side by side (pre-upgrade → post-upgrade → post-fix)

The same method, `ContainerEventOutboundDao.getUnprocessedTransactions(...)`, in its three historical
states. Only the query-building/execution part is shown; the trailing same-millisecond dedup block is
identical in all three and omitted for brevity. Commit references are exact.

### 14.1 PRE-UPGRADE — AWS SDK v1 (correct) — `git 9a04010f1d^`

```java
// DAO extends DynamoDBCrudRepository (low-level AWS SDK v1 helper)
String sortKeyLowerLimit = creationTimestamp.getTime() + "_g";
String sortKeyUpperLimit = Instant.now().minusMillis(TIME_DELAY_IN_MILLISECONDS).toEpochMilli() + "_g";

final Map<String, AttributeValue> expressionAttributeValues = new HashMap<>();
expressionAttributeValues.put(":hashKeyValue", new AttributeValue().withS(ipfId));
expressionAttributeValues.put(":srtKeyLower",  new AttributeValue().withS(sortKeyLowerLimit));
expressionAttributeValues.put(":srtKeyUpper",  new AttributeValue().withS(sortKeyUpperLimit));

String queryExpression =
    "integrationProfileFormatId = :hashKeyValue AND sequenceNumber BETWEEN :srtKeyLower AND :srtKeyUpper";

results = queryWithSizeLimit(null,
        expressionAttributeValues,
        queryExpression,          // ← passed straight through as DynamoDB keyConditionExpression
        null,
        DYNAMO_READ_BEHAVIOUR.CONSISTENT,
        RESULT_SIZE_LIMIT);
```

**Why it worked:** `queryWithSizeLimit(...)` fed `queryExpression` into the low-level DynamoDB
`QueryRequest.keyConditionExpression`, and `expressionAttributeValues` bound the `:srtKeyLower` /
`:srtKeyUpper` placeholders. DynamoDB evaluated `BETWEEN` **server-side**, so only rows in
`[cursor, now-delay]` were returned. Both bounds were honored by the engine.

### 14.2 POST-UPGRADE — AWS SDK 2.x / cloud-sdk (BROKEN) — `git 316b5da457` (as deployed in prod)

```java
// DAO now delegates to an injected EnhancedDynamoRepository (cloud-sdk enhanced client)
String sortKeyLowerLimit = creationTimestamp.getTime() + "_g";
String sortKeyUpperLimit = Instant.now().minusMillis(TIME_DELAY_IN_MILLISECONDS).toEpochMilli() + "_g";

String queryExpression =
    "integrationProfileFormatId = :hashKeyValue AND sequenceNumber BETWEEN :srtKeyLower AND :srtKeyUpper";

DefaultQuerySpec querySpec = DefaultQuerySpec.builder()
        .partitionKeyName("integrationProfileFormatId")
        .partitionKeyValue(CloudAttributeValue.ofString(ipfId))
        .queryExpression(queryExpression)                         // ← IGNORED by EnhancedDynamoRepository
        .expressionAttributeValues(Map.of(                        // ← orphaned: no expression consumes these
                ":hashKeyValue", CloudAttributeValue.ofString(ipfId),
                ":srtKeyLower",  CloudAttributeValue.ofString(sortKeyLowerLimit),
                ":srtKeyUpper",  CloudAttributeValue.ofString(sortKeyUpperLimit)))
        .consistentRead(true)
        .limit(RESULT_SIZE_LIMIT)
        .maxResultSize(RESULT_SIZE_LIMIT)
        .build();

results = repository.query(querySpec);                            // → partition-key-only, oldest 1000, ascending
```

**The mistake (literal v1→2.x text port):** the v1 `keyConditionExpression` string was mapped 1:1 onto
`.queryExpression(...)`, and the attribute-value map onto `.expressionAttributeValues(...)`. But the
injected repository is `EnhancedDynamoRepository`, whose `query()` **never reads `getQueryExpression()`**
and reads `expressionAttributeValues` only inside `buildFilterExpression(...)` (which runs only when a
`filterExpression` is set — it wasn't). Because no structured `sortKeyCondition`/`sortKeyValue` was set
either, the query collapsed to `QueryConditional.keyEqualTo(partition)`:

> `integrationProfileFormatId = 5680` only — **no sort-key bound**, ascending, capped at 1000
> → returns the **oldest 1000 rows of the partition** (the region the intended `BETWEEN` excluded).

No exception was thrown (the `BETWEEN`-reject guard lives on the *structured* path, never entered here —
see §13). Result: a **silent wrong-results** query. Reading oldest-first surfaced outbound rows whose
inbound `ContainerEvent` had been TTL-deleted → `OutboundGenerator` threw
`"Could not find inbound transaction ..."` and stalled the IPF.

### 14.3 POST-FIX — today (`git 8bd89dffbd`, current `HEAD`)

```java
String sortKeyLowerLimit = creationTimestamp.getTime() + "_g";
String sortKeyUpperLimit = Instant.now().minusMillis(TIME_DELAY_IN_MILLISECONDS).toEpochMilli() + "_g";

DefaultQuerySpec querySpec = DefaultQuerySpec.builder()
        .partitionKeyName("integrationProfileFormatId")
        .partitionKeyValue(CloudAttributeValue.ofString(ipfId))
        .sortKeyName("sequenceNumber")                            // ← structured sort-key fields the
        .sortKeyCondition(">=")                                   //    enhanced client actually reads →
        .sortKeyValue(CloudAttributeValue.ofString(sortKeyLowerLimit))  //    QueryConditional.sortGreaterThanOrEqualTo (server-side)
        .consistentRead(true)
        .limit(RESULT_SIZE_LIMIT)
        .maxResultSize(RESULT_SIZE_LIMIT)
        .build();

results = new ArrayList<>(repository.query(querySpec));           // mutable copy for the trims below

// Defence-in-depth + upper bound: re-verify BOTH bounds client-side, mirroring
// "sequenceNumber BETWEEN lower AND upper". Upper cannot be a server-side key condition
// (enhanced client allows one sort-key op; DynamoDB forbids key attrs in filterExpression).
results.removeIf(r -> {
    String sequenceNumber = r.getSequenceNumber();
    return sequenceNumber.compareTo(sortKeyLowerLimit) < 0
        || sequenceNumber.compareTo(sortKeyUpperLimit) > 0;
});
```

**Why it is correct:** `sortKeyCondition(">=")` + `sortKeyValue(...)` are the structured fields
`EnhancedDynamoRepository.query()` consumes; `">="` maps to `QueryConditional.sortGreaterThanOrEqualTo`,
so the lower bound is enforced **server-side** — restoring the exact inclusive lower bound of the v1
`BETWEEN` (§12.4). The upper bound is enforced **client-side** (`removeIf`), inclusive, because the
enhanced client accepts only one sort-key condition and DynamoDB disallows the sort key in a
`filterExpression`. Rows return oldest-first, so the upper trim only ever drops the most-recent tail and
never an in-window row. The structured `>=` is used deliberately instead of structured `BETWEEN` — the
latter would hit the enhanced client's `IllegalArgumentException("BETWEEN ... not supported yet")`.

### 14.4 At-a-glance

| | Query field used | Read by enhanced client? | Bound enforcement | Outcome |
|---|---|---|---|---|
| **Pre-upgrade (v1)** | `keyConditionExpression` (`BETWEEN`) | n/a (low-level v1 path honors it) | both bounds server-side | ✅ correct |
| **Post-upgrade (broken)** | `.queryExpression(BETWEEN)` + `expressionAttributeValues` | ❌ **no** (`getQueryExpression` never called) | none — degrades to partition-key-only | ❌ oldest-1000, wrong rows, silent |
| **Post-fix (today)** | `.sortKeyCondition(">=") + .sortKeyValue(...)` (+ client-side `removeIf`) | ✅ **yes** (structured) | lower server-side, upper client-side | ✅ correct |

**Bottom line:** the upgrade changed the *executor* (v1 low-level → enhanced client) but kept the v1
*query shape* (`queryExpression`), and the enhanced client silently ignores that field. The fix switches
the query shape to the structured `sortKeyCondition`/`sortKeyValue` the enhanced client honors, plus a
client-side upper-bound trim.

### 14.5 Why the pre-fix integration test did not catch it

The DAO *did* have an integration test at upgrade time (`ContainerEventOutboundDaoIT`, added during
ION-12316), yet the regression still shipped. The reason: it was a **false-confidence test** — it asserted
*inclusion* only, never *exclusion*. This is the exact shipped pre-fix test (`git 316b5da457`):

```java
@Test
@DisplayName("returns rows whose sequenceNumber falls inside the [creationTimestamp, now) window")
void returnsRowsInWindow() {
    dao.save(sample("200", ts, "in-1"));                 // ONE in-window row, nothing out-of-range
    List<ContainerEventOutbound> results = dao.getUnprocessedTransactions(200, new Date(ts - 1));
    assertThat(results).isNotEmpty();                                             // positive-only
    assertThat(results).anyMatch(r -> "200".equals(r.getIntegrationProfileFormatId())); // superset-tolerant
}

@Test
@DisplayName("returns empty when no row matches the partition key")
void returnsEmptyForUnknownPartition() {
    assertThat(dao.getUnprocessedTransactions(12345, new Date(0L))).isEmpty();    // empty partition
}
```

Why this passes against the **broken** (partition-key-only) query:

1. **No out-of-range row was ever seeded.** The broken query (partition-key-only, oldest-first) and a
   correctly-bounded query return the **same rows** whenever all data is in-window. They diverge *only*
   when a row **below the cursor** or **above the upper bound** exists — which the test never inserted. So
   the two behaviors had nothing to disagree on.
2. **Positive-only, superset-tolerant assertions.** `isNotEmpty()` + `anyMatch(IPF == 200)` check that the
   wanted row is *present*, not that unwanted rows are *absent*. A query returning a superset (or the whole
   partition) still satisfies both. There is no `hasSize` and no "does not contain the old row" assertion.
3. **The empty-partition test is indistinguishable.** IPF `12345` has zero rows, so partition-key-only and
   bounded queries both return empty — it passes either way.
4. **Tiny single-partition dataset.** A few rows in one IPF: the "oldest 1000" cap never triggered and
   there were no older-than-cursor rows to wrongly include. The production trigger (old rows referencing
   TTL-deleted inbounds) was never modeled.

The test exercised the **happy path** (an in-window row comes back) but never the **discriminating negative
path** (out-of-range rows must be excluded) — and exclusion is precisely the behavior the sort-key bound is
responsible for. A query that dropped the bound entirely therefore still passed. (Unit tests didn't catch
it either: they mock `repository`, so the real `EnhancedDynamoRepository.query()` never executed.)

**What the fix added** (both **red** against the unfixed DAO, **green** after — §12.3 recorded the run as
"4 with 2 failures"):

```java
@Test void excludesRowsBelowCursor()        { /* seed a row with ts < cursor; assert it is NOT returned */ }
@Test void excludesRowsNewerThanUpperBound() { /* seed a row with ts > now-delay; assert it is NOT returned */ }
```

**Lesson (generalised in §11.7):** every bounded/range query needs a **negative** integration test that
seeds out-of-range data and asserts it is excluded — a positive "the wanted row is returned" assertion
cannot distinguish a correct bound from a dropped one.

---

## 15. The proper (durable) fix, the cloud-sdk gap to implement, and blast radius across upgraded apps

### 15.1 Interim fix (shipped) vs. proper fix (needs a library change)

The shipped visibility fix (§12.1 / §14.3) is the **correct *interim*** fix **given the current library**:
a server-side `>=` lower bound plus a client-side `removeIf` upper bound. It is correct but not ideal —
the upper bound is enforced in the app after paging up to 1000 rows, not by DynamoDB.

The **proper end-state** fix expresses *both* bounds server-side as a single native range. That is exactly
what the entity intends (`sequenceNumber BETWEEN lower AND upper`) and what the v1 code did. **It cannot be
written today** because the cloud-sdk enhanced client has no `BETWEEN` conditional — so the proper fix
requires a **library change first**, then a small visibility change.

**Proper visibility DAO once the library supports it:**
```java
DefaultQuerySpec.builder()
    .partitionKeyName("integrationProfileFormatId").partitionKeyValue(CloudAttributeValue.ofString(ipfId))
    .sortKeyName("sequenceNumber")
    .sortKeyCondition("BETWEEN")
    .sortKeyValue(CloudAttributeValue.ofString(sortKeyLowerLimit))       // lower
    .sortKeyUpperValue(CloudAttributeValue.ofString(sortKeyUpperLimit))  // upper  ← NEW field
    .consistentRead(true).limit(RESULT_SIZE_LIMIT).maxResultSize(RESULT_SIZE_LIMIT)
    .build();
// → both bounds enforced server-side; the client-side upper-bound removeIf can then be dropped
//   (the lower/upper defence-in-depth re-verification may be kept until the library is trusted).
```

> **So yes — to do this "the right way" in cloud-sdk we must implement the `BETWEEN` conditional in the
> library.** Until then, the `>=` + client-side-trim form is the correct interim.

### 15.2 The cloud-sdk gap to implement (`mercury-services-commons`, `cloud-sdk-aws`)

Three changes, in priority order. All are in `EnhancedDynamoRepository` / `DefaultQuerySpec` /
`QuerySpec` (module `cloud-sdk-aws`, repo `mercury-services-commons`).

1. **Fail-fast on an unconsumed `queryExpression` (highest priority, cheapest).**
   `EnhancedDynamoRepository.query()` and `queryPages()` currently **never read `getQueryExpression()`** and
   do not error when it is set — the exact silent-drop that caused this incident. Change: if
   `getQueryExpression()` is non-null/non-blank on the enhanced path, throw
   `UnsupportedOperationException("queryExpression is not supported by the enhanced client; use sortKeyCondition/sortKeyValue or filterExpression")`.
   This converts any *future* mis-port from a silent wrong-results bug into a loud startup/first-call
   failure. **This single change would have turned the visibility incident into an immediate test failure.**

2. **Implement the `BETWEEN` sort-key conditional.**
   - `DefaultQuerySpec` / `QuerySpec`: add an **upper** sort value (e.g. `sortKeyUpperValue` +
     `getSortKeyUpperValue()`). Today the spec carries only a single `sortKeyValue` (verified: the builder
     exposes `sortKeyName`/`sortKeyCondition`/`sortKeyValue` only) — a two-sided range is currently
     inexpressible.
   - `EnhancedDynamoRepository.buildSortKeyConditional`: replace the
     `IllegalArgumentException("BETWEEN sort key condition is not supported yet...")` with
     `QueryConditional.sortBetween(lowerKey, upperKey)`.
   - `EnhancedDynamoRepository.queryPages`: same — replace the `UnsupportedOperationException("BETWEEN not
     yet implemented")`.
   - Add commons unit/IT coverage: a `BETWEEN` query returns only rows within `[lower, upper]`, inclusive.

3. **(Optional) Static/build-time guard.** A test (or annotation-processor check) that fails the build if a
   cloud-sdk DAO calls `.queryExpression(...)` on a spec destined for the enhanced client, catching the
   anti-pattern at compile/CI time across all modules.

After (1) and (2), the visibility DAO switches to structured `BETWEEN` (§15.1) and the client-side upper
trim is removed.

### 15.3 Blast radius across the upgraded applications

**Key structural fact:** *every* AWS-2.x-upgraded module wires **`createEnhancedRepository`** exclusively —
there is **no `createStandardRepository` in production anywhere** in the repo. So both library gaps
(silent `queryExpression` drop; no `BETWEEN`) apply uniformly to every upgraded app. What differs is
whether a given DAO actually *relies* on the ignored field.

**Current production `.queryExpression(...)` usages on the enhanced client (repo-wide scan):**

| Location | Expression | Impact | Status |
|---|---|---|---|
| `visibility ContainerEventOutboundDao` | `... sequenceNumber BETWEEN :lo AND :hi` | **Silent bound drop → wrong rows (this incident)** | **Fixed** (now structured `>=`) |
| `webbl BLDao.java:28` | `id = :hashKeyValue` (partition key only) | **Benign** — merely restates the partition-key equality the enhanced client already falls back to; never binds `:hashKeyValue` | Latent trap only (§11.1) |

No *other* active upgraded module currently passes a **real sort-key/filter bound** through
`.queryExpression(...)`. So the **immediate** blast radius beyond visibility is effectively **zero** —
webbl is benign today.

**Structured sort-key conditions in use elsewhere are all supported ops** (`EQ`, `BEGINS_WITH`, `>=`):
`registration RegistrationDao` (`>=`), `booking BookingDetailDao`/`TemplateSummaryDao`
(`EQ`/`BEGINS_WITH`), `network SubscriptionsDao`/`OptionalValidationsDao` (`EQ`), `visibility
ContainerEventPendingDao`/`BookingDao` (`BEGINS_WITH`/`EQ`), `watermill CargoVisibilitySubscriptionDao`
(`EQ`). **None use structured `BETWEEN`**, so nothing is currently throwing, and `booking
TemplateSummaryDao` correctly uses `.filterExpression(...)` + `.expressionAttributeValues(...)` (the
honored pattern) — a good reference for how to do secondary filtering.

**Latent / forward-looking risk (the real blast radius):**

1. **Future migrations repeating the mistake.** Any not-yet-upgraded DAO that mechanically ports a v1
   `keyConditionExpression` containing a range onto `.queryExpression(...)` will silently lose the bound —
   an exact repeat of this incident. Modules still on v1 with such DAOs are the exposed surface (e.g.
   `lambda`, `oceanschedules`/`oceanschedules-process`, `rates` remaining DAOs, `value-added-service`,
   `visibility` remaining, plus non-active `bill-of-lading`). Concrete example waiting to happen:
   **`bill-of-lading EblProviderDocumentDao.getDocumentsSummery`** issues
   `actionDateTime BETWEEN :fromDate AND :toDate` on a GSI. It is safe **today** because that module is
   still AWS SDK v1 (low-level `query(...)`, `com.amazonaws...AttributeValue`), where
   `keyConditionExpression` is honored — but if it is upgraded to the enhanced client via the same 1:1
   text port, it becomes the **same silent-wrong-results defect**, and it is a *two-sided* range, so it
   also needs the `sortBetween` capability from §15.2.
2. **Any DAO needing a genuine two-sided sort-key range** cannot express it server-side until §15.2(2)
   lands; each such case must otherwise use the `>=` + client-side-trim workaround (less efficient, easy
   to get wrong).

**Priority takeaway:** implement §15.2(1) (fail-fast on `queryExpression`) **now** — it is a few lines and
immediately protects every current and future enhanced-client DAO across all upgraded apps from a silent
recurrence. Implement §15.2(2) (`sortBetween`) to enable the proper server-side visibility fix and to
unblock any future two-sided range query (including `bill-of-lading` when it upgrades).

---

## 16. Production verification (2026-08-24) — what is actually deployed, and what still needs to be done

This section records a **read-only** production check performed with the QA/read-only SSO profile
`642960533737_INTTRA2-QATeam` (`describe-services`, `describe-task-definition`, CloudWatch Logs
`filter-log-events`). No AWS resources or configuration were modified. It exists because the earlier
sections (§11.5, §12.2) recorded a fix ("Fix B") that turned out **not to be in the shipped code**.

### 16.1 In plain terms

Today's prod release (commit `8bd89dffbd`, ION-16663) contains **two intended fixes**:

- **Fix A — "read the right records."** Before, the outbound poller had lost its time-window filter and was
  re-reading the *oldest* 1000 records of each profile from the start of the partition. Fix A restores the
  "only records at or after the cursor" bound. **This fix is deployed and working.**
- **Fix B — "don't let one bad record kill the whole batch."** When one outbound record points at an inbound
  event that has already been deleted (by the 400-day TTL), the code throws and **the entire batch for that
  profile fails**, so the profile's cursor never moves and the same 1000 records are re-read forever (a
  "poison message" loop). Fix B was supposed to make that single bad record be *skipped and logged* instead
  of aborting the batch. **This fix was written up in this document but never actually put into the code, so
  it is NOT working in production.**

**Net result (refined by the 18:20 EDT re-check in §16.7):** this is a **mixed** picture, not a blanket
freeze. Fix A lets the **majority** of profiles progress — their cursor advances normally. A **subset** of
heavily-backlogged profiles whose current 1000-record window still contains a TTL-orphaned inbound (e.g.
5811, 5857) stay **frozen**, because every batch still hits that orphan and aborts. The earlier wording here
("profiles that were badly backlogged are *all* still stuck") was too absolute — see §16.7 for the live
evidence distinguishing an advancing profile (4450) from a frozen one (5811).

#### 16.1.1 "If Fix A restores the query bound, why fetch very old records at all? Why is Fix B still needed?"

This is the most natural objection, so it is answered directly. **Fix A bounds the query to `>= cursor`; it
does not, and cannot, move the cursor.** The two fixes solve different halves of the problem.

- The query window is `[cursor, now − delay]`, where `cursor = lastTransactionCreationDatetime` (the
  profile's stored progress marker). Fix A restored the lower bound so we read **from the cursor** instead of
  from the start of the partition. It has **no influence over the *value* of the cursor**.
- The cursor advances **only when a batch is processed successfully** and the profile's threshold is updated.
- For the backlogged profiles the cursor is frozen **~3 years in the past** (observed live: IPF 5811 cursor
  `1692942388874`, IPF 5857 cursor `1692997897992` — both **2023-08-25**). So a *correct* `>= cursor` query
  legitimately means "records from Aug 2023 onward", and the oldest 1000 of those **are** 2023-era rows.
  Fix A is behaving exactly as designed — the window starts in 2023 because that is where the bookmark sits.
- Those 2023 outbound rows reference inbound events already purged by the 400-day inbound TTL (§11.6:
  outbound retention 1095 d ≫ inbound 400 d), so the lookup throws → the whole batch aborts → the cursor
  stays frozen → the same oldest-1000 rows are re-read forever. **Fix A can never break this loop, because it
  never advances the cursor** — it only reads correctly from wherever the frozen cursor points.
- **Fix B is what breaks the loop:** by skipping the single orphaned row instead of aborting, the batch
  completes, the threshold advances, and the cursor climbs forward through the backlog until it re-enters the
  healthy `< 400-day` window where no orphans exist. From then on orphans essentially stop and Fix B rarely
  fires.

**Analogy:** Fix A fixed *"start reading at the bookmark, not page 1."* But if the bookmark is stuck on a
torn page three years back, you hit that torn page every cycle and give up. Fix B lets you skip the torn
page and move the bookmark forward.

**So the premise "we should not be fetching very old records" is the desired *end state*, not something Fix A
delivers on its own.** Old records stop being fetched only once the cursor has moved out of the old region —
which requires either Fix B (self-healing, gradual) or the one-time cursor bump in §16.6 step 3 (immediate).
And because the TTL mismatch guarantees orphans for *any* profile that ever falls >400 days behind (from the
original bug, downtime, a slow consumer, or reprocessing), **Fix B is a permanent resilience requirement, not
a one-off cleanup** — Fix A keeps healthy profiles correct; Fix B rescues and protects the ones that fall
behind.

### 16.2 Deployment — CONFIRMED

| What | Evidence |
|---|---|
| Service | `VisibilityOutbound-prod` on cluster `ANEPRVIS-001` (task def `VisibilityOutbound-latest-prod-Task:1`) |
| New rollout | PRIMARY deployment **created 2026-08-24 17:33:01 EDT**, reached **8/8 running tasks at 17:35:56 EDT** |
| New build is live | The fix-only INFO line `ContainerEventOutboundDao: DynamoDB query for IPF … returned N records` appears **1,990×** in the 5 min after full rollout (17:37–17:42 EDT) |
| Log location | `inttra2-ecs-logs`, log-stream prefix `VisibilityOutbound-latest-prod` (note: **not** `inttra2-pr-lg-visibility`) |

### 16.3 Behaviour after rollout — Fix A works, Fix B is absent

Measured in the same fully-post-rollout window (17:37–17:42 EDT, all 8 tasks on the new build):

| Signal | Count (≈5 min) | Meaning |
|---|---|---|
| `DynamoDB query for IPF … returned N records` (Fix A fingerprint) | **1,990** | New bounded query is live and executing (e.g. IPF 5904 → 1000 records in 143 ms) |
| `Failed to process SQS message` (fatal, whole-batch abort) | **1,259** | Poison-batch loop is **still happening** — Fix B is not in the build |

The fatal errors carry the **identical** stack trace to the original incident, proving Fix B was never applied:

```
java.lang.IllegalArgumentException: Could not find inbound transaction with ID ce:...
  at OutboundGenerator.getInboundContainerEvent(OutboundGenerator.java:199)
  at OutboundGenerator.lambda$createAndSendBatchTransactions$0(OutboundGenerator.java:102)   // inside .map(...)
  at OutboundGenerator.createAndSendBatchTransactions(OutboundGenerator.java:104)            // .toList()
  at OutboundMultiTransactionProcessor.process(OutboundMultiTransactionProcessor.java:97)
```

Concrete stuck profiles observed (cursor frozen ~3 years in the past, so every read is below the 400-day
inbound horizon and every batch aborts):

- **IPF 5811** — `lastTransactionCreationDatetime = 1692942388874` (**2023-08-25**)
- **IPF 5857** — `lastTransactionCreationDatetime = 1692997897992` (**2023-08-25**, `locked = 1`)

### 16.4 Source-tree confirmation (why Fix B is missing)

- `OutboundGenerator.java:102` still builds each element with
  `...inboundEvent(getInboundContainerEvent(item.getInboundContainerEventId()))...` **inside** the
  `stream().map(...).toList()`.
- `OutboundGenerator.getInboundContainerEvent` (lines 193–202) still **throws**
  `IllegalArgumentException` when the inbound is not found (line 199). That throw is *outside* the per-record
  `catch` in `generateOutboundMessage` (line ~186), so it escapes to
  `OutboundMultiTransactionProcessor.process` and fails the whole SQS message.
- A repo-wide search finds **no** `toOutboundMetaDataOrSkip` method and **no**
  `skipsOrphanedInboundWithoutFailingBatch` test — i.e. the artefacts §11.5/§12.2 claim exist, do not.

### 16.5 QA note

The fix is effectively being validated in **prod, not QA**. In QA, `inttra2-qa-lambda-visibility-outbound-poller`
only *enqueues* IPF IDs onto `inttra2_qa_sqs_ce_outbound_ipf`; the actual processor `VisibilityOutbound-qa`
(cluster `ANEQAVIS-001`) showed **no** `DynamoDB query for IPF` fingerprint activity in the last 5 days, so
the outbound query path is not currently being exercised in QA.

### 16.6 What needs to be done

1. **Implement Fix B for real (primary, unblocks the stuck profiles).** Make a single missing inbound event
   skip that one record instead of aborting the batch. In
   `OutboundGenerator.createAndSendBatchTransactions` change the mapping at line 102 so that a lookup which
   cannot resolve the inbound event is filtered out rather than thrown:

   ```java
   List<ContainerEventOutboundMetaData> qualifiedEvents = containerEventOutboundList.stream()
           .map(this::toOutboundMetaDataOrSkip)          // returns null (logged) when inbound is missing
           .filter(Objects::nonNull)
           .filter(item -> !excludeTransaction(item.getOutboundEvent(), item.getInboundEvent()))
           .toList();

   private ContainerEventOutboundMetaData toOutboundMetaDataOrSkip(ContainerEventOutbound outbound) {
       List<ContainerEvent> inbound = containerEventDao.findById(outbound.getInboundContainerEventId());
       if (inbound == null || inbound.isEmpty()) {
           log.error("Skipping outbound row with orphaned inbound id {} (IPF {}, sortKey {}) - "
                   + "inbound TTL-expired; row will not block the batch",
                   outbound.getInboundContainerEventId(),
                   outbound.getIntegrationProfileFormatId(), outbound.getSortKey());
           return null;   // skip this one record; batch and cursor proceed
       }
       return ContainerEventOutboundMetaData.builder()
               .outboundEvent(outbound).inboundEvent(inbound.get(0)).build();
   }
   ```
   Keep the null/empty **input** guard already added (invalid id → still an error). Retire the throwing
   `getInboundContainerEvent`, or keep it only where a hard failure is genuinely wanted.

2. **Add the regression test that was claimed but is missing:**
   `OutboundGeneratorTest.skipsOrphanedInboundWithoutFailingBatch` — a 3-row batch with one orphaned inbound
   must send the 2 valid transactions and must **not** throw.

3. **Rescue the already-stuck profiles.** Even after (1), backlogged profiles (e.g. 5811, 5857) will churn
   through many thousands of orphaned rows before their cursor climbs back inside the 400-day window. Decide
   and document a remediation for the existing backlog — e.g. a controlled one-time cursor
   (`lastTransactionCreationDatetime`) advance to just inside the inbound-retention horizon for the affected
   IPFs — so they drain promptly instead of skip-logging ~millions of dead rows.

4. **Re-verify in prod after the next deploy** using the exact signals in §16.3: `DynamoDB query for IPF`
   should stay high (processing continues) while `Failed to process SQS message` drops to ≈0, and the
   previously-stuck IPFs (5811, 5857) should show their cursor advancing on subsequent poller cycles.

5. **Address the retention mismatch (§11.6) as a follow-up decision** — outbound TTL (1095 d) outliving
   inbound TTL (400 d) is what continuously manufactures these orphans; with Fix B in place it is no longer
   correctness-critical, but aligning the two (or guaranteeing outbound rows are processed within 400 d) is
   the durable way to stop generating orphans at the source.

6. **Correct the record.** §11.5 and §12.2 have been annotated as superseded by this section; keep future
   "fixed" claims tied to a commit + a prod-log signal so a documented fix cannot drift from the shipped code
   again.

### 16.7 Live re-check (2026-08-24 ~18:20 EDT) — mixed reality, service scaled to 0, and the DB-cursor hypothesis

A follow-up observation from a colleague ("the cursor *was* advancing for IPF 4450, so maybe the process is
working; maybe the DB cursor changes were not committed") prompted a second read-only pass. It refines §16.1
and §16.3 in three important ways.

**(a) The processor is currently scaled to zero — the recent "quiet" is not recovery.**
`describe-services` on `VisibilityOutbound-prod` (ANEPRVIS-001) returns `runningCount = 0, desiredCount = 0`,
with ECS events *"has stopped 8 running tasks … has reached a steady state."* So after the ~16-minute
post-deploy burst (17:33–17:49 EDT), the service was **scaled down to 0 tasks**. This was a **deliberate stop
by the team** (confirmed), done to halt the poison-loop / DLQ growth while the data-side remediation is sorted
out — so the last CloudWatch window shows **0** `DynamoDB query for IPF` and **0** `Failed to process SQS
message` simply because **nothing is processing**, not because the backlog cleared.

**(b) It is a *mixed* reality — some IPFs advance, a subset are frozen. Both halves are now proven:**

| IPF | Fatal errors in burst | Cursor (`lastTransactionCreationDatetime`) behaviour | Verdict |
|---|---|---|---|
| **4450** | **0** (`"Outbound IPF: 4450"` search returned empty) | Advanced `1693243473398 → 1693483075949` (colleague's DB read); `transactionCount` ~157→163 | **Working** — Fix A alone is enough because it has no orphan in-window |
| **5811** | **37**, all identical | `1692942388874` (2023-08-25) **unchanged across all 37 attempts**; `transactionCount` grew 7377→7563 | **Frozen** — poison-loop; cursor never moves |
| **5857** | present in burst | `1692997897992` (2023-08-25), `locked=1`; `transactionCount` 757→773 | **Frozen** |

So the colleague is **right about 4450** (and about the general point that processing works for un-poisoned
profiles), but it does **not** generalise: 5811's cursor is provably frozen (same value 37×). The correct
statement is *"Fix A advances the majority; the orphan-containing subset stays frozen until Fix B or a cursor
bump."*

**(c) Queue/DLQ depths confirm a large stuck backlog:**

| Queue | Approx. messages |
|---|---|
| `inttra2_pr_sqs_ce_outbound_ipf` (IPF work) | 83,672 |
| `inttra2_pr_sqs_ce_outbound_ipf_dlq` | **264,749** |
| `inttra2_pr_sqs_ce_outbound` (transactions) | 554,403 |
| `inttra2_pr_sqs_ce_outbound_dlq` | 4,638 |

The 264,749-message IPF DLQ is where poison IPF messages land after exhausting `maxReceiveCount` — the sink
for the still-frozen profiles.

**(d) On "the DB cursor changes may not have been committed" (leading explanation).** This is **strongly
consistent with the evidence**. The remediation for the stuck profiles was a MySQL `UPDATE` advancing
`lastTransactionCreationDatetime` (the cursor) past the 400-day orphan horizon — and the current working
theory is that a **bulk `UPDATE` run in a MySQL query editor was never committed** (autocommit off / an
explicit `COMMIT` was missed), so it did **not** persist for the application. The AWS-side evidence matches
this exactly: throughout the post-deploy burst the app read the **pre-bump** cursor for every sampled stuck
profile — IPF 5811 = `1692942388874` (2023-08-25) on all 37 attempts, unchanged; 5857 = `1692997897992`,
`locked=1`. If the bump had committed, the app (on its own connection) would have read the new, recent value
and those profiles would have skipped straight past the orphan zone. Because it did not, **no** profile got
the bump: orphan-free profiles (4450) creep forward under Fix A, orphan-containing ones (5811/5857) stay
poisoned.

> **Extra risk from an uncommitted editor transaction:** besides not persisting, an open (uncommitted)
> `UPDATE` **holds row locks** on those threshold rows and keeps a transaction open. That can block the
> application's own writes to the same rows (cursor advance / `locked` flag), and the whole change **silently
> rolls back** if the editor session disconnects or times out. So an uncommitted bulk update can both fail to
> help *and* actively interfere.

**(e) How to confirm and correctly apply the cursor bump (MySQL — needs DB access this AWS profile does not
have).**

1. **Confirm it did not persist:** from a *fresh* connection (not the editor session that ran the `UPDATE`),
   `SELECT integrationProfileFormatId, lastTransactionCreationDatetime FROM <threshold_table>
    WHERE integrationProfileFormatId IN (5811, 5857, 4450);` — if 5811/5857 still show the 2023-08 values,
   the bump is not committed.
2. **Check for a lingering open transaction / locks:**
   `SELECT * FROM information_schema.innodb_trx;` and
   `SELECT * FROM performance_schema.data_locks;` — a long-running `trx` on the threshold table indicates the
   editor's transaction is still open (or was rolled back on disconnect).
3. **Re-apply correctly:** re-run the `UPDATE` and **explicitly `COMMIT;`** (or set `autocommit=1` for the
   session). Bump `lastTransactionCreationDatetime` to a value safely inside the inbound-retention window
   (e.g. `now() − ~390 days` in epoch-ms) for the affected IPFs, then verify with the step-1 `SELECT` from a
   new connection.
4. **Only then scale the processor back up.** Order matters: apply the committed bump (and/or ship Fix B)
   *before* restoring `desiredCount`, otherwise the still-frozen profiles will immediately re-feed the
   264 K IPF DLQ.

**Note on scope of this analysis:** the RDS/MySQL threshold table was **not** queried here — the
`642960533737_INTTRA2-QATeam` profile is read-only against DynamoDB/CloudWatch/ECS/SQS only. Steps (e) must be
run by someone with MySQL access; the AWS-side cursor readings above are the indirect corroboration.

**Net:** deployment of Fix A is confirmed and genuinely working for the bulk of traffic; the still-stuck,
DLQ-feeding subset needs Fix B and/or the cursor bump; and the processor is currently scaled to 0, so no
progress is being made until it is scaled back up (ideally only after Fix B and/or the cursor remediation is
in place, to avoid re-growing the 264 K DLQ).
