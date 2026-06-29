# Visibility AWS SDK 2.x (cloud-sdk) Upgrade — Correctness Review

**Jira**: ION-12316 · **Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot` (single squashed commit `0f5fa309fc` on `develop`, merge-base `f992aaa631`)
**Reviewer**: Claude Opus 4.8 (1M context) · **Date**: 2026-06-27
**Method**: Independent verification of the actual branch code against the pre-upgrade `develop` baseline, the deprecated `dynamo-client` / `mercury-services-commons` models, the cloud-sdk `1.0.26-SNAPSHOT` source (`C:\Users\arijit.kundu\projects\mercury-services-commons`), and the **live QA/CVT/PROD tables** documented in [2026-06-26-aws-service-resource-details.md](./2026-06-26-aws-service-resource-details.md). Read-only.

**Inputs cross-checked**: [DESIGN-curr-state.md](./DESIGN-curr-state.md), [2026-06-01 design/impl review](./2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md), [06-23 rebase-refactor](./2026-06-23-visibility-rebase-refactor.md), [06-24 sns-sqs-coverage](./2026-06-24-visibility-refactor-sns-sqs-coverage.md), [06-25 sns-sqs-refactor](./2026-06-25-visibility-sns-sqs-refactor.md).

---

## 0. Verdict

The DynamoDB, S3, SQS, SNS, SES and SSM migrations are **functionally faithful for the existing QA/CVT/PROD/INT environments**. All entity re-annotations map **1:1** to the v1 schema and **match the live tables exactly** (keys, GSIs, projections, TTL). The two HIGH defects from the 2026-06-01 review (`metaData` S→M; missing dynamo config) are **confirmed fixed**, and SQS delete/DLQ/retry semantics are preserved.

**Not yet fully release-clean.** One **latent HIGH** defect affects *fresh* table provisioning, plus several MEDIUM/LOW behavioral drifts that the green test suite does not catch:

| # | Severity | Area | One-line |
|---|----------|------|----------|
| **F1** | **HIGH (latent — fresh-env/DR only)** | DynamoDB table creation | New admin command derives key/GSI **attribute names from getter property names**, ignoring `@DynamoDbAttribute`; a freshly-created `container_events` would get PK **`hashKey`** (not `id`) and `blNumber-index` keyed on **`billOfLading`** (not `blNumber`). Existing tables are safe (describe→skip). |
| **F2** | MEDIUM | S3 (s3-archiver lambda) | `createDefaultS3Client()` regresses socket read-timeout **5 min → 30 s** and maxConnections **100 → 50** on the archive **write** path. |
| **F8** | MEDIUM | DynamoDB TTL (outbound) | Live `container_events_outbound` has **TTL DISABLED** in QA/CVT/PROD, but the model now declares `@TTL expiresOn` → `dynamo-create` would **enable TTL** on next run, starting background expiry that isn't happening today. |
| **F3** | LOW–MEDIUM | S3 (commons client) | New **30 s `apiCallTimeout`** introduced (none in v1); bespoke retry policy replaced by SDK-v2 standard (≈equivalent). |
| **F4** | LOW | Lambda (s3-archiver) | Numeric `N` attributes (e.g. `expiresOn`) now archived to S3 JSON as **quoted strings** (`"177..."`) instead of numbers (carried-over LOW-8, still open, untested). |
| **F5** | LOW | DynamoDB streams | Neither the v1 nor the new command manages **DynamoDB Streams**; a fresh `container_events` would have **no stream** → matcher/archiver silent. (Parity with v1 — out-of-band today.) |
| **F6** | LOW (info) | SNS | Published payload is `List<Event>`→JSON via cloud-sdk `JsonSupport` (same shape as legacy); residual risk is only the serializer config vs the old `messaging` `Json`. See §6. |
| **F7** | LOW (edge) | DynamoDB | New `OffsetDateTimeTypeConverter` throws on `null` (v1 returned null); unreachable in normal saves (enhanced client skips nulls). |

Detail, evidence and recommendations below. **Remedy options for F1, F2, F4, F7, F8 are collected in [§11](#11-remedy-options).**

> ✅ **Live-AWS confirmation (2026-06-27).** Beyond the source diff, I ran read-only `describe-table` + `describe-time-to-live` against the real tables (profile `642960533737_INTTRA2-QATeam`). `container_events` in **QA (`inttra2_qa`)**, **CVT (`inttra2_test`)** and **PROD (`inttra2_prod`)** all confirm: partition key attribute **`id`**; the 5 GSIs keyed on `blNumber` / `bkInttraReferenceNumber`+`equipmentIdentifier` / `equipmentIdentifier` / `bookingNumber` / `siInttraReferenceNumber`, all **KEYS_ONLY**; stream **KEYS_ONLY**; **TTL ENABLED on `expiresOn`**. `container_events_pending` → keys `createDate`/`inboundContainerEventId` (S), **TTL ENABLED on `expiresOn`**. `container_events_outbound` → keys `integrationProfileFormatId`/`sequenceNumber`, **TTL DISABLED** (⚠ see F8). The entity models match the live schema exactly. *(This also corrects the 2026-06-26 inventory: `booking_ContainerTrackingEvent` is a booking-module table, not a visibility one — see §3.1.)*

---

## 1. DynamoDB — entity / key / GSI / TTL parity (per table)

**Method**: `git diff develop..HEAD` on each entity, mapped against the v1 `@DynamoDB*` annotations (`dynamo-client`) and the live tables. **Verdict: PASS** — every entity is a faithful 1:1 re-annotation.

| Table (logical) | Entity | Partition / Sort key | GSIs | TTL | Live-table match |
|-----------------|--------|----------------------|------|-----|------------------|
| `container_events` | `ContainerEvent` | `id` (`getHashKey` `@DynamoDbPartitionKey @DynamoDbAttribute("id")`) | 5: `bookingNumber-index`, `blNumber-index`(attr `blNumber`), `equipmentIdentifier-index`, `bkInttraReferenceNumber-equipmentIdentifier-index`(hash `bkInttraReferenceNumber`, sort `equipmentIdentifier`), `siInttraReferenceNumber-index` — all KEYS_ONLY | `@TTL expiresOn` (epoch-sec `N`) | ✅ exact (keys, 5 GSIs, KEYS_ONLY) |
| `container_events` (shared) | `ContainerTrackingEvent` | `id` | same 5 GSI names (alternate model over the same table) | `@TTL expiresOn` | ✅ shares `container_events` |
| `container_events_outbound` | `ContainerEventOutbound` | `integrationProfileFormatId` / `sequenceNumber` | none | `@TTL expiresOn` | ✅ exact (no GSI) |
| `container_events_pending` | `ContainerEventPending` | `createDate` / `inboundContainerEventId` | none | `@TTL expiresOn` | ✅ exact |
| `booking_BookingDetail` | `BookingDetailVisibility extends BookingDetail` | inherited from booking `BookingDetail` (`bookingId`/`sequenceNumber`) | inherited (4) | inherited | ✅ owned by **booking** module |
| `CargoVisibilitySubscription` | `cargo.visibility.model.CargoVisibilitySubscription` | `id` | `bookingNumber-index`, `subscriptionReference-index` (subset; the 2 carrierScac GSIs are owned by watermill-publisher) | `@TTL`? no — `expiresOn` via `DateEpochSecondAttributeConverter` (`N`) | ✅ shared table; visibility maps a subset |

Notable, all verified against the diff:
- **Keys/GSIs**: v1 `@DynamoDBHashKey`/`@DynamoDBIndexHashKey`/`@DynamoDBIndexRangeKey` → v2 `@DynamoDbPartitionKey`/`@DynamoDbSecondaryPartitionKey`/`@DynamoDbSecondarySortKey` translate exactly; the `attributeName="id"`/`"blNumber"` overrides are reproduced as `@DynamoDbAttribute("id")`/`("blNumber")`; the upper-casing setters on `bookingNumber`/`billOfLading`/`equipmentIdentifier` are retained.
- **`ContainerEventOutbound`**: the v1 `@DynamoDBAutoGeneratedKey` on the `sequenceNumber` range key is **dropped** (v2 has no equivalent). This is correct **only because** `sequenceNumber` is always set explicitly in code (`{timestamp}_{ceId}`); verified there is no save path relying on auto-generation. The old `getHashKey`/`getSortKey` are kept as `@DynamoDbIgnore` aliases for source compatibility.
- **`ContainerEventPending`**: `createDate` changed from `LocalDate` (`@DynamoDBTypeConverted(DateToIso8601)`) to `String` to satisfy the admin command's key-type resolver (see §3); the single caller persists `LocalDate.now(Clock.systemUTC()).toString()` → `yyyy-MM-dd`, **byte-identical** to the v1 physical key. (`ContainerEventPendingDao.java:70`).
- **`CargoVisibilitySubscription`**: real bug fixed — `createdOn`/`modifiedOn` (`java.util.Date`, **no** v1 converter → DynamoDBMapper default ISO-8601 `S`) now carry `@DynamoDbConvertedBy(LegacyDynamoDbDateAttributeConverter)` (ISO-8601 UTC `S`, lenient epoch read); `expiresOn` stays epoch-sec `N`. The SDK-2 enhanced client has **no** built-in `Date` converter, so without this the WM repository fails to build at startup. **PASS.**

### 1.1 `CargoVisibilitySubscription` — the "real bug", and cross-module sharing (answering the review question)

**Is the table used?** Yes. `visibility-wm-inbound-processor`'s `CargoVisibilitySubscriptionProcessor` actively reads and writes it (`findById`, `findBySubscriptionReference`, **`subscriptionDao.save(...)`** — `CargoVisibilitySubscriptionProcessor.java:50,52,67`), wired via `VisibilityWMEventApplicationInjector`. It is the durable store for the cargo-visibility subscription lifecycle (SUBMITTED/APPROVED/…). Live counts: QA `inttra2_qa_*` 26,978 items, CVT `inttra2_cv_*` 97, PROD `inttra2_pr_*` 0 (per the 06-26 inventory).

**What "the WM repository fails to build at startup" means.** The AWS SDK 2.x **Enhanced Client** builds a `TableSchema` for a `@DynamoDbBean` by reflecting over every persisted property and resolving an `AttributeConverter` for each property *type*. `createdOn`/`modifiedOn` are `java.util.Date`. The enhanced client has **no built-in `java.util.Date` converter**, and the v1 model had **no** explicit converter on these fields (it relied on `DynamoDBMapper`'s default `Date` marshalling). So when the cloud-sdk repository/`TableSchema` for `CargoVisibilitySubscription` is **constructed** — which happens during Guice provisioning at **application boot** — it throws `IllegalStateException: Converter not found for EnhancedType(java.util.Date)`. "Fails to build" = the `TableSchema`/repository object cannot be constructed → the `visibility-wm-inbound-processor` service **crashes on startup**. The defect was masked pre-fix because every existing test **mocked** the DAO/repository, so the real schema-construction path was never exercised. The fix adds `LegacyDynamoDbDateAttributeConverter` (and explicit annotated getters).

**Why the fix format matters for cross-module sharing.** The table is shared with the **`watermill-publisher/watermill-cargo-visibility-subscription`** module, which is **still on AWS SDK v1** (its upgrade is scheduled **after** visibility ships). The two modules use different model classes over the same physical table (the watermill-publisher model is richer — confirmed by the live attributes/GSIs: `carrierBookingNumber`, `billOfLadingNumber`, `carrierScac`, and GSIs `billOfLading-carrierScac-index`, `bookingNumber-carrierScac-index`, `bookingNumber-index`, `subscriptionReference-index`). The chosen converter writes `createdOn`/`modifiedOn` as an **ISO-8601 UTC String (`S`)** — exactly what the v1 `DynamoDBMapper` default produced — so items written by upgraded visibility remain **byte-compatible** with what the still-v1 watermill-publisher reads and writes. Had the fix used epoch-`N` instead, it would have **broken** the un-upgraded watermill-publisher's reads. So this fix is both correct *and* a prerequisite for the staged rollout. **PASS.**

> ⚠ **Pre-existing cross-module caveat (NOT introduced by this upgrade).** The visibility WM model declares `bookingNumber-index` keyed on its `bookingNumber` field, but the **live** `bookingNumber-index` is keyed on attribute **`carrierBookingNumber`** (the watermill-publisher schema). This divergence predates the SDK upgrade (the v1 visibility model had the same `bookingNumber-index` on `bookingNumber`) and is harmless here only because **visibility does not create this table** — no admin command includes `CargoVisibilitySubscription`. It should be reconciled when watermill-publisher is upgraded; flag it for that effort, not this one.

---

## 2. DynamoDB — attribute converters (on-disk format parity)

**Verdict: PASS** — writes reproduce the v1 on-disk format; reads are leniently backward-compatible.

| Converter (v2) | v1 equivalent | Wire type | Parity |
|----------------|---------------|-----------|--------|
| `MetaDataAttributeConverter` | `MetaDataConverter` (`<String,MetaData>`) | **S** via `MetaData.toJsonString()` | ✅ **HIGH-1 fixed** — was `M` in the first cut; now `S`, lenient `M`-read fallback. Restores the s3-archiver contract. |
| `ContainerEventSubmissionAttributeConverter` | `ContainerEventSubmissionConverter` | **S**, bare `ObjectMapper` (`WRITE_DATES_AS_TIMESTAMPS` default true) | ✅ **MEDIUM-4 fixed** — date encoding reverted to byte-identical; `FAIL_ON_UNKNOWN_PROPERTIES=false` affects reads only. |
| `ContainerEventEnrichedPropertiesAttributeConverter` | `...EnrichedPropertiesConverter` | **S**, bare `ObjectMapper` | ✅ same as above |
| `SubscriptionAttributeConverter`, `GISOutboundDetailsAttributeConverter`, `ContainerTrackingEventMessageAttributeConverter` | v1 `*Converter` | **S** JSON | ✅ tested (`*AttributeConverterTest`, `ConverterTestSupport`) |
| `OffsetDateTimeTypeConverter` (cloud-sdk) | `dynamo.converter.OffsetDateTimeTypeConverter` | **S** | ✅ output identical for `OffsetDateTime` (`ISO_DATE_TIME` ≡ `ISO_OFFSET_DATE_TIME` when an offset is present); read uses `ISO_OFFSET_DATE_TIME` in both. ⚠ **F7**: v2 `transformFrom` **throws on null** (v1 returned null) — unreachable because the enhanced client omits null attributes. |
| `DateEpochSecondAttributeConverter` (cloud-sdk) | `DateToEpochSecond` | **N** (`getTime()/1000`) | ✅ epoch-seconds, matches; `expiresOn` already millis-truncated in the setters. |
| `LegacyDynamoDbDateAttributeConverter` (new) | DynamoDBMapper default `Date` | **S** ISO-8601 UTC | ✅ matches v1 default marshalling. |

---

## 3. DynamoDB — table creation: how it worked, and parity (USER-REQUESTED)

### 3.1 How each table was created/maintained **pre-upgrade**

| Table | Pre-upgrade creator | Mechanism |
|-------|--------------------|-----------|
| `container_events`, `container_events_outbound`, `container_events_pending` | **visibility-inbound** `create-tables` Dropwizard command (`CreateTables` → `DynamoContainerEventsTableCommand` + `...OutboundTableCommand` + `...PendingTableCommand`) | Each sub-command extended the `dynamo-client` `AbstractDynamoCommand`, calling `createTableAndWaitUntilActive(client, DynamoDBMapper, <Entity>.class, read, write, gsis)`. The v1 `DynamoDBMapper` derived key/GSI **attribute names from the v1 annotations** (`@DynamoDBHashKey(attributeName="id")`, `@DynamoDBIndexHashKey(attributeName="blNumber")`), and read GSI list, projection (**KEYS_ONLY**) and throughput (**5/5**) from the **`dynamoDbTableCreationCommandConfig:`** YAML block. `container_events` was built from **`ContainerTrackingEvent.class`**. |
| `booking_BookingDetail`, `booking_ContainerTrackingEvent` | **booking** module (not visibility) | Visibility only *reads* `booking_BookingDetail` (via `BookingDao`/`BookingDetailVisibility`). The separate `booking_ContainerTrackingEvent` table (`hashKey`/`sortKey`, stream `NEW_IMAGE`) is a **booking-module** table — not the visibility `ContainerTrackingEvent`, which maps to `container_events`. *(Corrects the mapping in the 2026-06-26 doc.)* |
| `CargoVisibilitySubscription` | **watermill-publisher** / WM side | Shared table; visibility-wm reads/writes a subset of attributes & GSIs. Live creation dates are 2026 (QA 01-19, CV 02-05, PR 02-21). |
| **TTL & Streams (all tables)** | **out-of-band** (infra / manual) | Neither the v1 `dynamoDbTableCreationCommandConfig` nor the v1 commands set TTL or Streams. The live `container_events` stream (KEYS_ONLY) and the 400d/3y/40d TTLs were provisioned outside the command. |

> Physical names are `<environment>_<logical>` — QA `inttra2_qa_*`, **CVT `inttra2_test_*`**, PROD `inttra2_prod_*` (CargoVisibilitySubscription uses `inttra2_pr_*`). See the 06-26 doc for the prefix map.

#### `booking_ContainerTrackingEvent` — who owns it (answering the review question)

This table is **not a visibility table and is not created, written, or read by any visibility module.** Evidence:
- The visibility `ContainerTrackingEvent` model (`visibility-commons/.../common/model/ContainerTrackingEvent.java`) is annotated `@Table(name = "container_events")` — it is an alternate read-model over the **`container_events`** table (PK `id`, the 5 booking/equipment GSIs). It has **no** `hashKey`/`sortKey` keys and **no** `inttraReferenceNumber_equipmentId` GSI.
- The live `booking_ContainerTrackingEvent` table is structurally different: composite key **`hashKey`/`sortKey`**, a single GSI **`inttraReferenceNumber_equipmentId`** (hash `inttraReferenceNumber`, range `equipmentId`), and stream **`NEW_IMAGE`** (confirmed via `describe-table`).
- Its physical name decomposes as the **booking** prefix `inttra2_<env>_booking_` + `@Table("ContainerTrackingEvent")`, i.e. it belongs to the **booking** module's container-tracking-event import feature — corroborated by the booking SNS topics in the 06-26 inventory: `inttra2_<env>_sns_booking_ContainerTrackingEvent_ImportEventsPipeline{Success,Failure}Topic` and `..._BulkContTrackingEvent_...`.
- A repo-wide search of the checked-out `mercury-services` tree found **no** Java `@DynamoDbBean`/`@Table("ContainerTrackingEvent")` with this `hashKey`/`sortKey`+`inttraReferenceNumber_equipmentId` shape (neither in visibility nor in the visible booking sources). That strongly suggests the model/owner lives in a **booking sub-component or import-pipeline not present in this working tree** (or the table is provisioned via infra/CFN). It was **not** part of the visibility scope, which is why it wasn't seen during the booking AWS upgrade either — it is a distinct booking artifact.

**Bottom line for this review:** disregard `booking_ContainerTrackingEvent` for the visibility upgrade. The only booking table visibility touches is `booking_BookingDetail` (read-only, via `BookingDao`/`BookingDetailVisibility`, owned by the already-upgraded booking module).

### 3.2 How it works **post-upgrade**

`create-tables` (+ the three `DynamoContainerEvents*TableCommand` and `DynamoDbTableCreationCommandConfig`) and the `dynamoDbTableCreationCommandConfig:` YAML block are **removed**. Replaced by **`dynamo-create`** = `VisibilityInboundDynamoDbAdminCommand extends cloudsdk.database.command.DynamoDbAdminCommand`, managing `ContainerEvent`, `ContainerEventOutbound`, `ContainerEventPending`. All metadata is derived from the entity annotations by `EntityTableMetadata.fromEntityClass`.

### 3.3 Idempotency / skip-if-exists — **PASS (CONFIRMED)**

`DynamoDbAdminCommand.createTableWithGsisIfNotExists` (cloud-sdk):
- `describeTable` → if present, **skip creation**, then *ensure* GSIs/TTL/streams.
- `DynamoDbAdminUtil.addGlobalSecondaryIndexIfNotExists` skips when the **index name** already exists.
- `enableTimeToLive` first `describeTimeToLive`; if `ENABLED`, **skip** (no error on already-enabled).
- `enableStreams` skips when stream already enabled with the same view type.
- The `VisibilityInboundDynamoDbAdminCommandIT.IdempotentCreation` test runs the command **twice** and asserts the key schema + GSI set are unchanged.

→ Running `dynamo-create` against the **existing** QA/CVT/PROD/INT tables is a **safe no-op**.

### 3.4 Capacity / projection / TTL parity — **PASS (capacity/projection); CAUTION (TTL on outbound — F8)**

`EntityTableMetadata`: default RCU/WCU = **5/5** (`READ_CAPACITY_UNITS`/`WRITE_CAPACITY_UNITS`); `@Table` declares no override → 5/5, matching the v1 YAML. GSI projection defaults to **KEYS_ONLY** (`buildGlobalSecondaryIndex`/`extractGsiMetadata`), GSI throughput 5/5 — matching v1 and the live tables.

**TTL — codified now, but one divergence (F8).** `@TTL expiresOn` makes the command enable TTL on attribute `expiresOn` (epoch-sec `N`). Confirmed against live (`describe-time-to-live`, 2026-06-27):

| Table (model has `@TTL expiresOn`) | Live TTL status | Verdict |
|-------------------------------------|-----------------|---------|
| `container_events` (QA/CVT/PROD) | **ENABLED** on `expiresOn` | ✅ idempotent no-op |
| `container_events_pending` (QA) | **ENABLED** on `expiresOn` | ✅ idempotent no-op |
| `container_events_outbound` (QA) | **DISABLED** | ⚠ **F8** — command would *enable* it |

> 🟧 **F8 (MEDIUM).** `ContainerEventOutbound` now carries `@TTL expiresOn`, but the live `container_events_outbound` table has TTL **DISABLED** in every environment (neither the v1 command nor infra ever enabled it). The first time `dynamo-create` runs against an existing environment it will issue `UpdateTimeToLive(enabled=true, attribute=expiresOn)` and DynamoDB will begin **background-expiring** outbound rows whose `expiresOn` is in the past — behaviour that is **not happening today**, on a table holding ~2.7 B items in PROD. This is `enableTimeToLive`'s one non-idempotent edge (it only skips when status is already `ENABLED`). **Decide intentionally**: either (a) remove `@TTL` from `ContainerEventOutbound` to preserve the current "no expiry" state, or (b) keep it but treat enabling TTL as a deliberate, separately-reviewed data-lifecycle change (validate the distribution of `expiresOn` first). See [§11](#11-remedy-options). Everything else here is an idempotent no-op on existing tables.

### 3.5 🟥 **F1 — HIGH (latent): attribute names diverge on a fresh create** &nbsp;<span style="color:#d00;">**[TODO — ION-12316 follow-up]**</span>

> 🟥🛠️ **TODO (HIGH — fix before any fresh-environment / DR provisioning).** Preferred fix = visibility-module override + IT assertion (options **b2 + c** in [§11.1](#111-f1--fresh-create-attribute-name-mismatch)). Existing QA/CVT/PROD/INT are **not** at risk (describe→skip, confirmed against live AWS 2026-06-27 — PK `id`, GSIs on `blNumber`/`bookingNumber`/… all present and correct). This is a latent defect that only manifests when `dynamo-create` builds a brand-new `container_events`.

`EntityTableMetadata` resolves key/GSI attribute names from the **getter property name**, not `@DynamoDbAttribute`:
- `extractKeySchema`/`extractAttributeDefinitions` → `extractPropertyNameFromGetter("getHashKey")` = **`hashKey`**.
- `extractGsiMetadata` → `extractAttributeName("getBillOfLading")` = **`billOfLading`**.

Neither reads `@DynamoDbAttribute`. Consequently, a **freshly created** `container_events` would have:

| Element | v1 command (and live tables) | New `dynamo-create` (fresh) | Match? |
|---------|------------------------------|------------------------------|--------|
| Partition key attribute | **`id`** | **`hashKey`** | ❌ |
| `blNumber-index` hash attr | **`blNumber`** | **`billOfLading`** | ❌ |
| `bookingNumber-index` / `equipmentIdentifier-index` / `bkInttra…-equipmentIdentifier-index` / `siInttraReferenceNumber-index` | (own attrs) | (same — no `@DynamoDbAttribute` override) | ✅ |
| Outbound / Pending keys | `integrationProfileFormatId`/`sequenceNumber`, `createDate`/`inboundContainerEventId` | same (getter name == attribute name) | ✅ |

The runtime **enhanced client** correctly uses `id`/`blNumber` (it *does* honor `@DynamoDbAttribute`). So a fresh table created by `dynamo-create` would be written to by the app on attribute `id` while the table's key is `hashKey` → **`ValidationException` on first PutItem**, and `blNumber-index` would index a non-existent `billOfLading` attribute (queries return nothing).

- **Existing QA/CVT/PROD/INT: NOT affected** — `describeTable` finds the table, creation is skipped, GSIs already exist by name. This is why the build/ITs are green.
- **Affected scenario**: provisioning a brand-new environment / region / DR rebuild via `dynamo-create`.
- **Why the IT misses it**: `VisibilityInboundDynamoDbAdminCommandIT.createsContainerEventsWith5Gsis` asserts only GSI **index names** and `keySchema().size()/keyType()==HASH` — it never asserts the partition-key **attribute name** or GSI key attribute names.
- **Root cause is a cloud-sdk gap** (`EntityTableMetadata` ignores `@DynamoDbAttribute`); `booking` avoids it because its getters are named to match the attribute (no override). 

**Recommendation**: detailed fix options (SDK-level **a**, module-level **b1/b2**, IT **c**) with risk analysis are in **[§11.1](#111-f1--fresh-create-attribute-name-mismatch)**. Until fixed, **do not provision a new environment with `dynamo-create`** as-is.

### 3.6 🟧 **F5 — LOW: streams not managed (fresh-env)** &nbsp;<span style="color:#e67e00;">**[TODO — agreed, deferred ~2026-06-28]**</span>

> 🟧📌 **TODO (user-accepted — to address later, ~tomorrow).** Codify the `container_events` stream so a fresh environment is correct by construction.

`ContainerEvent` has no `@DynamoDBStream` annotation, so `extractStreamViewType` returns null and the command does not enable the stream. This is **parity** with the v1 command (which also didn't), but a fresh `container_events` would lack the **KEYS_ONLY** stream the matcher and s3-archiver depend on (confirmed live: stream `KEYS_ONLY` is enabled on `container_events` in all three envs). **Fix**: add the cloud-sdk `@DynamoDBStream(StreamViewType.KEYS_ONLY)` class annotation to `ContainerEvent` — `extractStreamViewType` will then drive `DynamoDbAdminUtil.enableStreams` (which is idempotent: it skips when a stream with the same view type is already enabled, so it is safe to run against the existing QA/CVT/PROD tables). Verify with an IT assertion on `StreamSpecification.streamViewType == KEYS_ONLY`.

---

## 4. S3 — **CONCERN (2 items)**

| Aspect | develop (v1) | HEAD (cloud-sdk) | Verdict |
|--------|--------------|------------------|---------|
| Commons client connect / socket / maxConn | 1000 ms / 5000 ms / 50 | `S3_CONNECTION_TIMEOUT=1000ms` / `S3_SOCKET_TIMEOUT=5000ms` / `S3_MAX_CONNECTIONS=50` (custom Apache client) | ✅ preserved |
| Commons retry | `maxErrorRetry=3` + bespoke `FullJitter(500,5000)` + `AwsRetryCondition` | SDK-v2 **standard** retry (3 attempts, jittered) | ≈ equivalent (**F3**) |
| Commons `apiCallTimeout` | none (commented out) | **30 s** (`BaseAwsConfig` default) | ⚠ **F3** new ceiling |
| `S3WorkspaceService.getContent/putObject` | `AmazonS3` getObject/putObject | `StorageClient` getContent/putObject | ✅ equivalent; `putObject` now sets `text/plain; charset=UTF-8` and returns `void` (was `PutObjectResult`) — minor |
| itv-gps / wm-inbound reads | v1 | shared commons `StorageClient` (correct 1s/5s) | ✅ |
| **s3-archiver lambda client** | connect 5s, **socket 300s**, execTimeout 300s, retries 3, **maxConn 100** | `StorageClientFactory.createDefaultS3Client()` → connect 5s, **socket 30s**, maxConn 50 | ⚠ **F2** read-timeout 5min→30s, maxConn 100→50 on the **write** path |

> **F3 — risk of the new 30 s `apiCallTimeout` ceiling.** `apiCallTimeout` bounds the **entire** S3 operation **including all retries and backoff** (unlike the per-attempt `socketTimeout`/`connectionTimeout`). In v1 it was commented out → effectively **unbounded** (a slow call could hang but would eventually complete). Now any single `getObject`/`putObject` that, across its ≤3 attempts + jittered backoff, exceeds **30 s** is aborted with `ApiCallTimeoutException`. *Practical risk: LOW* — visibility S3 objects are small EDI/JSON payloads and the 5 s socket timeout caps each attempt, so 3 attempts + backoff stay well under 30 s. It becomes relevant only for unusually large objects or sustained S3 throttling/retry storms, where a call that previously completed (slowly) would now fail fast. This is a **behavioral addition, not parity** — flag it; no change needed unless large-object workspace I/O is expected.

**Recommendations**: F2 (s3-archiver write timeout / maxConnections) remedy options are in **[§11.2](#112-f2--s3-archiver-socket-timeout--max-connections)**. F3 — accept the 30 s ceiling per the LOW-risk assessment above, or set `clientExecutionTimeout` explicitly on the commons S3 config if unbounded behaviour must be preserved.

---

## 5. SQS — **PASS**

`messaging.sqs.SQSClient` (v1 `Message`) → `cloudsdk.messaging.api.MessagingClient<String>` (`QueueMessage<String>`), with a new mutable `SqsMessage` wrapper carrying `doNotDelete`/`doNotSendToDlq`.

- **Receive**: `listMessages(url, messagesPerRead, waitInSeconds)` — same batch/wait from unchanged `SQSConfig`.
- **Success → delete**: `deleteMessage(url, receiptHandle)` in `finally` unless `doNotDelete`.
- **Failure → DLQ then delete**: `sendMessage(dlqUrl, body)` unless `doNotSendToDlq`, then delete. **DLQ-then-delete ordering and flag branches are identical**; flags default `false` → default delete+DLQ, exactly as v1. No inverted/lost flag, no delete-without-DLQ, no stuck message.
- **Body**: `QueueMessage.getPayload()` (`String`) == v1 `Message.getBody()`; all 11+ consumers are pure type/import substitution with unchanged body parsing and unchanged downstream `sendMessage(url, body)`.
- **Config**: across all 37 changed YAMLs, **no** `url`/`dlqUrl`/`messagesPerRead`/`waitInSeconds` value changed.
- **Note (info)**: the v1-only `catch (AbortedException)` (stop + interrupt on shutdown) is removed (`AbortedException` is v1-specific). Shutdown-time aborts now fall into the generic catch-and-continue — behaviorally benign.

---

## 6. SNS — **PASS (1 caveat)**

- `createEventLoggingPublisher`: same enable/disable gate; disabled → `EmptyEventPublisher` (now implementing the cloud-sdk `EventPublisher`); `snsEventTopicArn` wiring unchanged; publisher swap `new SNSEventPublisher(arn, client)` → `NotificationClientFactory.createDefaultClient(arn)` (same ARN).
- `EventLogHandler`, `EmptyEventPublisher`: imports-only diff; `SNSMapper` (DynamoDB-stream→SNS envelope parse used by matcher & archiver) **zero diff**.
**F6 caveat — explained in detail.** "What actually gets published to the SNS topic" is no longer assembled by visibility code; it is produced inside the cloud-sdk. I read that path to scope the residual risk:
- `EventLogger.logCloseRunEvent(...)` builds an `Event` via `EventGenerator` and calls `eventPublisher.publishEvent(List.of(event))` (`cloud-sdk-api/.../notification/workflow/EventLogger.java:91-102`).
- `SnsEventPublisher.publishEvent(List<Event>)` serialises with **`JsonSupport.toJsonString(events)`** and does `SnsClient.publish(topicArn, <that JSON>)` (`cloud-sdk-aws/.../notification/workflow/SnsEventPublisher.java:52-61`). So the wire payload is the JSON of a **`List<Event>`** — the **same shape** the legacy `messaging.logging.SNSEventPublisher` produced.
- The serializer config is now pinned and visible: `JsonSupport.OBJECT_MAPPER` = `JavaTimeModule` + `Jdk8Module`, **`WRITE_DATES_AS_TIMESTAMPS=false`** (dates → ISO-8601 strings), **`Include.NON_NULL`**, `READ_UNKNOWN_ENUM_VALUES_AS_NULL=true`, custom `MultiFormatLocalDateTimeDeserializer` (`cloud-sdk-api/.../notification/util/JsonSupport.java:48-59`).

So the **only** residual risk is whether that `JsonSupport` config is byte-identical to the **old `messaging` `Json`** mapper (field ordering, date pattern, null inclusion) — the `Event`/`MetaData` classes themselves are field-and-builder-identical mirrors. The old `messaging.*` serializer is not in the checked-out tree (it shipped in `commons 1.R.01.x`, now removed), so I cannot byte-diff it here. **Risk is LOW** (both are ISO-8601-date + NON_NULL Jackson mappers over identical models). **Action**: confirm once — either diff `JsonSupport` against the legacy `messaging.util.Json` config, or capture one published message in INT and compare to a pre-upgrade sample. If SNS consumers are schema-tolerant JSON parsers (they are), even minor ordering differences are inert.

---

## 7. SES — **PASS (untouched), but uses the raw SES client, not the cloud-sdk wrapper**

There are **two distinct email paths** in visibility; only one touches SES directly:

**Path 1 — `visibility-inbound` `EmailSender` → raw AWS SDK v2 `SesClient` (direct SES).**
`EmailSender.java:27-49` imports `software.amazon.awssdk.services.ses.SesClient` and calls `sesClient.sendRawEmail(SendRawEmailRequest…)`; the client is `SesClient.create()` bound in `VisibilityInboundApplicationInjector`. This was **already AWS SDK v2 before ION-12316** (the lone v2 usage pre-upgrade) and the upgrade left it **completely unchanged** (zero diff). So it is correct as a *migration* (nothing to migrate), but note:

> **Answering the review question — "are we not using the SES wrappers in cloud-sdk-api?"** Correct: visibility does **not** use them. cloud-sdk **does** ship a SES email wrapper — `com.inttra.mercury.cloudsdk.email.api.EmailService` / `MailContent` / `EmailRequest` with `com.inttra.mercury.cloudsdk.email.config.AwsSesEmailConfig` (`cloud-sdk-api` + `cloud-sdk-aws`). `EmailSender` predates that wrapper and still calls `SesClient` directly. This is an **inconsistency/opportunity, not a defect**: adopting `cloudsdk.email.EmailService` would align SES with the rest of the cloud-sdk wrapping (region/credentials/retry handled by the factory, config-driven source identity), but it is **out of scope** for a v1→v2 migration since SES was never on v1. Recommend a follow-up to migrate `EmailSender` onto `cloudsdk.email.EmailService` for consistency. No verified import of `cloudsdk.email.*` exists in visibility today.

**Path 2 — `visibility-error-email` lambda → Network "error-email" REST API (no SES in visibility).**
`ErrorEmailService.java:16,34-41` holds `SERVICE_KEY = "error-email"` and calls `networkServiceClient.post(serviceDefinition.getUri()+"/companyId|ediId/"+id, …)` — i.e. it **HTTP-POSTs to the Network module's `error-email` endpoint**, and the **Network service** performs the actual email send. This lambda never constructs an `SesClient`. Since **Network is already AWS-2.x-upgraded** and owns that endpoint (and its own SES interaction), there is nothing SES-related to migrate in `visibility-error-email`; the upgrade there only swapped SSM (`ParameterStoreResolver`) and added the Guava pin. **PASS.**

**Net**: SES (Path 1) is untouched and correct; the only note is the missed opportunity to use the cloud-sdk `EmailService` wrapper. The "network API" (Path 2) is a separate, HTTP-based email trigger handled by the already-upgraded Network module.

---

## 8. SSM Parameter Store — **PASS**

v1 `AWSSimpleSystemsManagement` → cloud-sdk `CloudParameterStore` via `ParameterStoreClientFactory`.
- `${awsps:...}` is **not** a Dropwizard config-source here — it is plain prefix-stripping in `ParameterStoreResolver.lookup` (`replace("${awsps:","").replaceAll("}$","")`), **byte-for-byte preserved**.
- error-email `ParameterStoreResolver` and outbound-poller `HandlerSupport.resolveSsmPath`: same keys, `withDecryption=true`, same "missing → throw" / "missing → null" semantics; outbound-poller now lazily inits the client (improvement). **No parameter path changed** (`{root}/user`, `{root}/password`, auth client secret).

---

## 9. Lambda — **PASS (1 carried-over LOW)**

| Lambda | Verdict | Notes |
|--------|---------|-------|
| **s3-archiver** | PASS + **F4** | Raw schemaless `DynamoDbClient.getItem` (key `id`, consistentRead=true) replaces the v1 Document API. `metaData` read as **String** (`av.s()` branch first; `(String)` cast safe) — the 06-01 `M` regression is **not** reintroduced. MODIFY-only / INSERT+REMOVE skipped; GPS skip (`statusEventCode == "CI"` via `ProcessingConstants`, unchanged). S3 key `yyyy/MM/dd/HH/{id}.json` + bucket unchanged. **F4**: `toJavaObject` returns `av.n()` as a raw `String`, so top-level `N` attrs (e.g. `expiresOn`) archive as **quoted strings** — schema drift vs v1's `BigDecimal` numbers; untested (`VisibilityS3ArchiverTest` only asserts `putObject` was called). |
| **outbound-poller** | PASS | SQS→`MessagingClient.sendMessage(url, json)` (same URL/body); SSM lazy `ParameterStoreClientFactory` (same paths, decryption); JDBC `OutboundThreshold` query + threshold→SQS JSON byte-identical. |
| **pending-start** | PASS | Fan-out unchanged: `IntStream.range(1,8)` days + `range(2,5)` weeks × prefixes (hex `0-9`/`a-f`, unchanged vs develop); SQS send via `MessagingClient` same body/queue. |
| **error-email** | PASS | SES unaffected (see §7); `ParameterStoreResolver` migrated (same lookups); subscription filter on `contextCode == "errorReport"` unchanged. **Guava `33.5.0-jre` pin** added in `pom.xml` (removing `dynamo-client` let stale Guava 18.0 leak via `mybatis-guice`, breaking Guice 7 `buildOrThrow`) — a dependency-convergence fix. |
| all four | PASS | Lambda runtime event models (`com.amazonaws.services.lambda.runtime.events.*`, `OperationType`, `S3EventNotification`) **deliberately retained** (no v2 equivalent) — expected, not a defect. |

---

## 10. Findings register & recommendations

| ID | Sev | Fix |
|----|-----|-----|
| **F1** | HIGH (latent) | Make `EntityTableMetadata` honor `@DynamoDbAttribute` for key & GSI attribute names (cloud-sdk), or rename the `ContainerEvent` PK getter / handle the `blNumber` override; add IT assertions on the PK & `blNumber-index` attribute names. Until then, don't provision a fresh env via `dynamo-create`. |
| **F2** | MEDIUM | Give the s3-archiver a tuned `AwsStorageConfig` (socket ≈300 s, maxConn 100) or consciously accept SDK-v2 defaults. → [§11.2](#112-f2--s3-archiver-socket-timeout--max-connections) |
| **F8** | MEDIUM | Decide TTL on `container_events_outbound`: remove `@TTL` to keep current "no expiry", or enable as a reviewed data-lifecycle change. → [§11.5](#115-f8--outbound-ttl-divergence) |
| **F3** | LOW–MED | Document/justify the new 30 s `apiCallTimeout`; confirm no slow workspace read exceeds it. |
| **F4** | LOW | If any S3-archive consumer parses numbers, return `BigDecimal`/numeric from `toJavaObject` for `N` attrs; add a JSON-content assertion. |
| **F5** | LOW | Add `@DynamoDBStream(KEYS_ONLY)` to `ContainerEvent` or document stream provisioning as an explicit out-of-band step. |
| **F6** | LOW | Add a contract/IT confirming the cloud-sdk `SnsEventPublisher` payload is byte-identical to the legacy event JSON. |
| **F7** | LOW | (Optional) make `OffsetDateTimeTypeConverter.transformFrom(null)` return null for defensiveness. |

**Confirmed-fixed from the 2026-06-01 review**: HIGH-1 (`metaData` S→M) ✅, HIGH-2 (missing dynamo config; converged to a single `dynamoDbConfig`) ✅, HIGH-3 (table-prefix == legacy physical names) ✅, MEDIUM-4 (JSON date encoding reverted) ✅, MEDIUM-6 (retry narrowed to transient via `DynamoDbErrorHandler.isRetryableError`) ✅ (per 06-23 doc).

**Net**: safe to deploy to the **existing** QA/CVT/PROD environments from a DynamoDB-schema standpoint (tables already exist; `dynamo-create` is an idempotent no-op there — **confirmed against live AWS 2026-06-27**), **with one caveat**: do not let a deploy run `dynamo-create` against PROD unguarded until **F8** (outbound TTL) is decided, since that one path is not a pure no-op. The headline latent risk is **F1** (fresh-provisioning attribute-name mismatch), followed by **F8** (outbound TTL enable) and the **s3-archiver write-timeout regression (F2)**.

---

## 11. Remedy options

Each finding below has its own subsection with concrete options and trade-offs. **F1/F5** are the deferred TODO items (highlighted in §3.5/§3.6).

### 11.1 F1 — fresh-create attribute-name mismatch

**Root cause**: `EntityTableMetadata` (`cloud-sdk-aws`) derives key & GSI attribute names from the **getter property name** and ignores `@DynamoDbAttribute`. Only `ContainerEvent` is affected: PK getter `getHashKey()`→`hashKey` (should be `id`) and GSI getter `getBillOfLading()`→`billOfLading` (should be `blNumber`). The runtime enhanced client is unaffected (it honors `@DynamoDbAttribute`); the divergence is purely in the DDL the admin command would emit for a **fresh** table.

#### Option A — fix in the cloud-sdk library *(correct long-term; defer to a later cloud-sdk upgrade)*
In `EntityTableMetadata`, when a key/GSI getter carries `@DynamoDbAttribute("x")`, use `"x"` as the attribute name instead of the derived property name (`extractKeySchema`, `extractAttributeDefinitions`, `extractGsiMetadata`/`extractAttributeName`). One-line lookup per getter.
- **Pros**: fixes every consumer once; no per-module override drift; the "right" fix.
- **Risk / impact of doing A**: **broad blast radius.** It changes table-creation attribute-name derivation for **all** cloud-sdk consumers (booking, network, auth, webbl, ssr…). Entities whose getter name already equals the attribute (the common case — that's why no other module hit this) are unaffected; but any entity relying on the *current* property-name behaviour would shift, so every dependent module's fresh-create path must be re-validated. It also requires a **cloud-sdk release + version bump across all dependents + full regression**, i.e. release coupling and scheduling cost. Given no other module is broken today, the marginal urgency is low → **schedule with a planned cloud-sdk upgrade**, not as part of ION-12316.

#### Option B2 — fix in the visibility module by overriding the admin command *(RECOMMENDED — your preference)*
Override `VisibilityInboundDynamoDbAdminCommand` to supply a **corrected `EntityTableMetadata` for `ContainerEvent`** (explicit attribute names) and delegate the other two tables to the annotation-derived path. `EntityTableMetadata` has a public `@Builder`, and `createTableWithGsisIfNotExists(EntityTableMetadata)` is `protected`, so this is clean:

```java
@Override
protected void run(Bootstrap<VisibilityInboundApplicationConfig> b, Namespace ns,
                   VisibilityInboundApplicationConfig cfg) {
    this.clientConfig = resolveClientConfig(cfg);          // same as base
    // container_events: hand-built metadata with correct attribute names
    createTableWithGsisIfNotExists(containerEventsMetadata());
    // outbound + pending: getter names already == attribute names → annotation path is correct
    for (Class<?> e : List.of(ContainerEventOutbound.class, ContainerEventPending.class)) {
        createTableWithGsisIfNotExists(EntityTableMetadata.fromEntityClass(e));
    }
}

private static EntityTableMetadata containerEventsMetadata() {
    // PK attribute "id" (S); 5 KEYS_ONLY GSIs with correct key attributes:
    //   blNumber-index(HASH blNumber), bookingNumber-index(HASH bookingNumber),
    //   equipmentIdentifier-index(HASH equipmentIdentifier),
    //   siInttraReferenceNumber-index(HASH siInttraReferenceNumber),
    //   bkInttraReferenceNumber-equipmentIdentifier-index(HASH bkInttraReferenceNumber, RANGE equipmentIdentifier)
    // attributeDefinitions: id, blNumber, bookingNumber, equipmentIdentifier,
    //   siInttraReferenceNumber, bkInttraReferenceNumber  (all S)
    // ttlAttributeName "expiresOn"; provisioned 5/5; streamViewType null (see F5)
    return EntityTableMetadata.builder()...build();
}
```
- **Pros**: self-contained in `visibility-inbound`; **no entity rename, no runtime ripple**; existing QA/CVT/PROD/INT remain describe→skip; ships with ION-12316.
- **Risk of doing it in the module**: **low.** (1) The override restates a small amount of `ContainerEvent`'s schema; if its keys/GSIs ever change, this method must change too — mitigate by deriving the GSI list from the entity constants and only overriding the two attribute names. (2) If Option A later lands in cloud-sdk, this override becomes **redundant but harmless** (it produces the identical correct DDL) — remove it then to avoid drift. (3) Must stay consistent with any future base-command signature change. **Zero runtime risk to the services** and zero risk to existing tables.

#### Option B1 — rename the entity properties to match attributes *(NOT recommended)*
Rename field/getter `hashKey`→`id` and `billOfLading`→`blNumber` so the property name equals the attribute. **Ripple ≈ 60 references across ~10 main files** (`ContainerEventDao`, `ContainerTrackingEventDao`, `ContainerEventTableDao`, `InboundEdiProcessor`, `ContainerEventService`, `ContainerEventMigrationService`, `ExternalContainerTrackingService`, the error-email lambda, plus tests) and `billOfLading` carries a custom upper-casing setter and domain naming. High churn, high regression surface for no runtime benefit. Avoid.

#### Option C — strengthen the IT *(do alongside B2)*
Extend `VisibilityInboundDynamoDbAdminCommandIT` to assert **attribute names**, not just GSI names/key counts:
```java
assertThat(table.keySchema().get(0).attributeName()).isEqualTo("id");
var bl = table.globalSecondaryIndexes().stream()
    .filter(g -> g.indexName().equals("blNumber-index")).findFirst().orElseThrow();
assertThat(bl.keySchema().get(0).attributeName()).isEqualTo("blNumber");
// + assert each GSI's key attribute names and projection == KEYS_ONLY
```
This closes the assertion gap that let F1 pass unnoticed.

**Recommendation**: ship **B2 + C** under ION-12316; file **A** as a cloud-sdk backlog item for a later upgrade.

### 11.2 F2 — s3-archiver socket timeout / max-connections

`visibility-s3-archiver` `HandlerSupport` uses `StorageClientFactory.createDefaultS3Client()` → SDK-v2 defaults (socket **30 s**, maxConn **50**), regressing from the v1 archiver client (socket **300 s**, maxConn **100**) on the archive **write** path.

- **Option 1 (recommended) — reapply the legacy tuning.** Mirror what `visibility-commons` already does for `bindStorageClient()`: build an `AwsStorageConfig` with a custom Apache `SdkHttpClient` (`socketTimeout=Duration.ofMinutes(5)`, `connectionTimeout=5s`, `maxConnections=100`) + an explicit `DefaultCredentialsProvider`, and call `StorageClientFactory.createS3Client(config)` in `HandlerSupport`. ~15 lines, isolated to the lambda.
- **Option 2 — consciously accept the SDK-v2 defaults.** Archive objects are small JSON (one container event), and the archiver processes SQS batches at low concurrency, so 30 s socket / 50 connections are ample in practice. If accepted, **document the decision** (and note the prod archive Lambda log group is ~30 GB/14 d, i.e. high volume but small objects).
- **Option 3 (cloud-sdk enhancement, later)** — add first-class `socketTimeout`/`connectionTimeout`/`maxConnections` setters (and a default-credentials fallback) to `AwsStorageConfig.Builder` (this is cloud-sdk gap #3 from the 06-25 doc), then the archiver sets three fields instead of hand-building an Apache client.

**Recommendation**: Option 1 if any large-payload archive is possible; otherwise Option 2 with a documented rationale. Track Option 3 in the cloud-sdk backlog.

### 11.3 F4 — numeric `N` attributes archived as quoted strings

`VisibilityS3Archiver.toJavaObject` returns `av.n()` as a raw `String`, so top-level `N` attributes (notably `expiresOn`) serialize into the archived S3 JSON as **`"expiresOn":"1776158934"`** instead of v1's unquoted **`"expiresOn":1776158934`**.

- **Fix.** Return a numeric type for `N` so Jackson emits an unquoted number:
```java
// VisibilityS3Archiver.toJavaObject(...)
if (av.n() != null) {
    return new java.math.BigDecimal(av.n());   // was: return av.n();  (String)
}
```
`BigDecimal` round-trips arbitrary-precision DynamoDB numbers and matches the v1 `Item.asMap()` behaviour (which also yielded `BigDecimal`). Only **top-level** `N` attributes flow through `toJavaObject`; the nested `containerEventSubmission`/`enrichedProperties`/`metaData` blobs are already JSON strings and are unaffected.
- **Test (the gap that hid this).** Today `VisibilityS3ArchiverTest`/`IT` only assert `putObject` was called. Capture the written content and assert the numeric is unquoted, e.g.:
```java
ArgumentCaptor<String> body = ArgumentCaptor.forClass(String.class);
verify(storageClient).putObject(eq(bucket), anyString(), body.capture());
assertThat(body.getValue()).contains("\"expiresOn\":1776158934")
                           .doesNotContain("\"expiresOn\":\"1776158934\"");
```
- **Caveat**: confirm with the downstream archive consumer(s) whether they expect numbers; if they already tolerate strings, this is cosmetic and can be deprioritised — but restoring v1 parity is the safe default.

### 11.4 F7 — `OffsetDateTimeTypeConverter.transformFrom(null)` throws

The cloud-sdk converter throws `IllegalArgumentException` on null (v1 returned null). It is **unreachable in normal saves** because the enhanced client omits null attributes and never invokes the converter for them.

- **Option 1 (recommended) — no code change; add a guard test + comment.** Document the invariant and add a converter unit test asserting current behaviour, so a future change to `ignoreNulls(false)` on the enhanced client is caught. `createdDate`/`lastModifiedDateUtc` are set on create, so null never occurs in practice.
- **Option 2 — fix in cloud-sdk (shared converter).** Make `transformFrom(null)` return `AttributeValue.builder().nul(true).build()` (defensive, symmetric with the other converters). This is a `cloud-sdk-aws` change → same release-coupling considerations as F1 Option A; bundle it with that cloud-sdk pass.
- **Note**: the visibility module **cannot** fix this locally (the converter is owned by cloud-sdk); the module-side mitigation is simply guaranteeing non-null (already true). Lowest priority.

### 11.5 F8 — outbound TTL divergence

Live `container_events_outbound` has **TTL DISABLED** (all envs); the model now declares `@TTL expiresOn`, so `dynamo-create` would enable it (non-idempotent on this table — `enableTimeToLive` only skips when already `ENABLED`).

- **Option 1 (recommended unless expiry is intended) — remove `@TTL` from `ContainerEventOutbound`.** Keeps the field as a plain attribute (still written via `DateEpochSecondAttributeConverter`), preserving the current "no background expiry" state and matching live/pre-upgrade. Outbound retention then stays managed however it is today.
- **Option 2 — keep `@TTL` and treat enabling TTL as a deliberate change.** First sample the distribution of `expiresOn` on `container_events_outbound` (it holds ~2.7 B items in PROD); only enable once you've confirmed the volume of immediately-expirable rows and the desired retention. Roll out in a controlled window, not via an incidental `dynamo-create` on deploy.
- **Either way** — confirm whether the deployment pipeline runs `dynamo-create` automatically; if it does, F8 (and F1) must be resolved before the next PROD deploy. If it is a manual ops command (as `create-tables` was), the immediate risk is lower.
