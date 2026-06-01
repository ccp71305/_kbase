# Booking Module — AWS SDK 2.x Upgrade: Design & Implementation Review

**Jira (umbrella)**: ION-14382 (+ data-format/integration follow-ups: ION-15691, ION-15708, ION-15743, ION-15856)
**Reviewer**: Claude Opus 4.8 (enterprise refactoring review)
**Date**: 2026-06-01
**Baseline reviewed**: `booking/` on the current branch — confirmed **byte-identical to `develop`** (`git diff develop...HEAD -- booking/src booking/pom.xml` is empty). This review therefore reflects the production-candidate code.
**Release context**: Booking v2 is running in QA with **no open bugs / no integration issues reported as of today**; production release planned **2026-06-13**.
**Inputs**: the 24 docs under `booking/docs/` (digested), the `ION-14382` commit series, and the live converter/entity code.

---

## 0. Verdict

The booking AWS v1→v2 migration is **fundamentally sound and the hard problem was solved correctly.** The central architectural insight — that SDK v1 kept *DynamoDB serialization* and *REST/SQS serialization* on independent engines, and that v2's Jackson-based attribute converters accidentally **coupled** them through shared `@JsonFormat` annotations — was correctly diagnosed, and the final design **re-decouples** them. The converter set is internally consistent, the read paths are deliberately tolerant, and QA is clean.

I am **cautiously confident this is releasable on Jun 13**, with the following framing:

- The long "audit timestamp saga" (`Z` ↔ `+0000` ↔ space) churned through **QA only**. Production has **never run an interim build**, so production DynamoDB contains only original-format (`Z`, nanosecond, Map) records, which the final converters read and rewrite faithfully. **The poisoned-record backlog described in the docs is a QA artifact, not a production hazard** — *provided* the Jun 13 deploy ships the final converter code (it does, per the develop baseline) and prod has genuinely never received an intermediate build.
- The residual risks below are mostly **latent / low-probability** given the clean QA signal, but three deserve explicit sign-off before release (§2: cross-module write-format lock, MixIn fragility regression test, and the precision split).

No blocker found. Recommendations are confirmations and guardrails, not rework.

---

## 1. What the migration got right (confirmed against code)

### 1.1 The decoupling of DynamoDB vs REST/SQS serialization is correct
[AuditAttributeConverter.java](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java) uses **two** ObjectMappers:
- `DYNAMO_OBJECT_MAPPER` registers a custom `OffsetDateTime` serializer (`addSerializer(... ISO_DATE_TIME)`) → writes **literal `Z`, full precision** to DynamoDB. This is what the still-on-v1 **visibility** module needs (its `booking:2.1.8.M` `OffsetDateTimeTypeConverter` parses ISO-8601 `Z`/offset but **cannot** parse RFC-822 `+0000`).
- The REST path is left to Dropwizard's mapper honoring [`Audit.java`](../src/main/java/com/inttra/mercury/booking/dynamodb/Audit.java)'s `@JsonFormat(pattern="yyyy-MM-dd'T'HH:mm:ss.SSSZ")` → emits **`+0000`** for the Redshift Glue ETL (`unix_timestamp(...SSSZ)`).

This mirrors the pre-upgrade architecture exactly and is the right fix. Critically, a custom `addSerializer` **does** override `@JsonFormat` (a second bare mapper instance would not) — the implementation relies on this correctly.

### 1.2 Map (M) storage format is the correct backward-compatible choice *for booking*
[`AuditAttributeConverter`](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/AuditAttributeConverter.java), [`MetaDataConverter`](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java), [`EnrichedAttributesConverter`](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverter.java), [`RangeAttributeConverter`](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/RangeAttributeConverter.java) all write **`M`** (`attributeValueType() == M`, `AttributeValue.fromM(LegacyMapConverter…)`). This matches booking v1's `@DynamoDBDocument` nested-map storage, so visibility-v1 (which recurses into these maps via its frozen mapper) keeps reading them.

> **Note for cross-team awareness**: this is the *opposite* conclusion from the sibling visibility-commons migration, where `MetaData`/`submission` were v1 **String** converters and must stay `S`. The format choice is per-field-history, not a blanket rule — both modules are individually correct. (See the companion visibility review.)

### 1.3 Read paths are uniformly tolerant
Every converter has the same robust shape: **primary `M` read**, **`S` JSON fallback** for interim records, and flexible date deserializers:
- [`OffsetDateTimeTypeConverter`](../src/main/java/com/inttra/mercury/booking/dynamodb/OffsetDateTimeTypeConverter.java) — tries `ISO_OFFSET_DATE_TIME`, then normalizes `+0000`→`+00:00`, then a date-only fallback. Handles `Z`, `+00:00`, `+0000`, and variable (milli→nano) precision.
- `FlexibleLocalDateTimeDeserializer` (MetaData) — accepts both `T` and space separators.
- `FlexibleDateDeserializer` (ContainerType/PackageType) — accepts ISO, space, **and epoch-millis strings**.

This means even the QA-poisoned `+0000`/space records are *readable* by booking-v2; only the *write* contract toward v1 consumers ever mattered.

### 1.4 The reference-data date fields are correctly pinned
[ContainerType.java:64-66](../src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/ContainerType.java#L64-L66) and [PackageType.java:36-38](../src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/PackageType.java#L36-L38) both carry `@JsonFormat(pattern="yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")` (**literal** `Z`) + `@JsonDeserialize(FlexibleDateDeserializer)`. These live inside `enrichedAttributes` (M) and are written in the ISO-`T`-with-`Z` form that visibility-v1's `DateUtils.parseISO8601Date()` requires. Correct.

### 1.5 `EnrichedAttributesConverter` registers `Jdk8Module`
[EnrichedAttributesConverter.java:28](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverter.java#L28) registers `Jdk8Module`, which addresses the `Optional<String>` serialization class of bug flagged in the April docs (`LocationAdditionalInfo.getCountryISO2Code()`). Good — though see §2.6 for the separate `Json.toJsonString` error-path instance.

### 1.6 SQS/transformer contract preserved
`MetaData.timestamp` keeps the class-level `@JsonFormat(space pattern)` for `Json.toJsonString()` (SQS → transformer/distributor/aw-bridge), while the DynamoDB-only `MetaDataDynamoDbMixIn` forces ISO-`T`. This is what unblocked the 519-message DLQ outbound-pipeline incident and keeps **watermill / messaging consumers** (which consume the SQS `MetaData` contract, not DynamoDB) on the unchanged space format.

---

## 2. Findings & risks (none blocking; ordered by release relevance)

### 🟠 R1 — Lock the DynamoDB write-format with a guard test before every release
The entire v1-visibility compatibility rests on **two** behaviors that are easy to regress silently:
1. `AuditAttributeConverter.DYNAMO_OBJECT_MAPPER` writing `Z` (not `+0000`).
2. `MetaDataConverter`'s MixIn writing ISO-`T` (not space).

Both are "invisible" couplings: a future dev "tidying up" to a single ObjectMapper, or removing the MixIn, would compile, pass most tests, and **silently re-break visibility-v1 in production** (the exact failure mode of the 03/27 and 05/05 windows). 

**Recommendation**: ensure there is an explicit, assertive unit test that pins the **serialized DynamoDB string** for both `Audit.createdDateUtc` (asserts trailing `Z`, asserts *not* `+0000`) and `MetaData.timestamp` (asserts `T`-separator, asserts *not* space). The docs reference `MetaDataConverterTest.timestampSerializationFormat`; confirm an equivalent exists for `Audit` and that both assert the *negative* case. This is the cheapest insurance for the Jun 13 release and beyond.

### 🟠 R2 — `MetaDataConverter` MixIn fragility (getter vs field annotation)
[MetaDataConverter.java:52-56](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/MetaDataConverter.java#L52-L56): the MixIn annotates the **getter** `getTimestamp()`, while `MetaData` annotates the **field**. The April review (`claude-review-integration-issue-fix.md`) explicitly flagged that in some Jackson introspection orderings a field annotation can win over a MixIn getter annotation, which would silently emit space-format to DynamoDB. QA being clean indicates it currently resolves correctly, but it is **load-bearing and fragile**. Folded into R1's guard test — keep it.

### 🟡 R3 — Nanosecond (DynamoDB) vs millisecond (REST/Redshift) precision split is intentional but under-documented
The same logical audit timestamp is persisted at **nanosecond** precision in DynamoDB (`ISO_DATE_TIME`, e.g. `…210972723Z`) but exposed at **millisecond** precision over REST/to Redshift (`SSS` + `+0000`). This was deliberate (ticket "fix integration test audit field precision to nano") and is fine, but any consumer that joins/dedupes/compares the DynamoDB value against the REST/Redshift value must **not** assume bit-for-bit equality. Worth one sentence in the runbook so nobody "fixes" the apparent mismatch later.

### 🟡 R4 — `LegacyMapConverter` collapses empty string → NULL and decimals → `double`
[LegacyMapConverter.java:133-138](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java#L133-L138): on **write**, an empty `String` becomes a DynamoDB `NUL`. On read, `NUL` → `null`. So a field that was `""` round-trips to `null` after a save+load. For audit/metadata this is harmless, but confirm no field in `EnrichedAttributes`/`Range`/`Condition` semantically distinguishes empty-string from null.

[LegacyMapConverter.java:68-81](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java#L68-L81): on read, any numeric (`N`) containing `.` is parsed as **`double`**. If any M-stored attribute holds a high-precision `BigDecimal` (money, rates, weights), this is a **precision/representation loss**. Booking's precision-sensitive **spot rates avoid this** — [`SpotRatesAttributeConverter`](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/SpotRatesAttributeConverter.java) serializes to an `S` JSON string (`attributeValueType() == S`), preserving exact text. Good. But `RangeAttributeConverter` and `EnrichedAttributesConverter` *do* route through `LegacyMapConverter` — see R5.

### 🟡 R5 — `Range<E>` generic erasure can change value *type* on round-trip
`Range` is generic (`E gte`, `E lte`). `OBJECT_MAPPER.convertValue(range, Map.class)` erases `E`, and on read `convertValue(simpleMap, Range.class)` rehydrates with `E` erased to `Object`. So a `Range` whose bounds were (say) `BigDecimal` or `Integer` may come back as `Double`/`String`. If RapidReservation `Range` bounds are only ever dates-as-strings or plain ints, this is moot; if they can be decimals, R4's precision loss applies and the **runtime type changes**. Given QA is clean this is low-probability, but worth a targeted round-trip test on the actual `Range` instances RapidReservation produces.

### 🟡 R6 — `SpotRates` stored as `S` while siblings store `M` — confirm this matches v1
`SpotRatesAttributeConverter` writes `S` (JSON string), unlike the `M`-writing converters. This is the *right* call for precision (R4), **but only if v1 also stored spotRates as a JSON string** (not `@DynamoDBDocument`/M). If v1 stored it as M and any v1 reader still consumes it, the type flip (`M`→`S`) would break that reader — the same failure class as the visibility-commons `MetaData` finding. Spot rates are almost certainly not read by visibility-v1, so this is likely safe; **confirm the v1 on-disk type for `spotRates`** and that no external consumer reads it.

### 🟢 R7 — Backlog/data-migration gap is QA-only, but verify the prod premise
Every doc closes with the same caveat: format fixes correct **future writes only**; interim poisoned records (`+0000` audit, space-format containerType, stray `MM/dd/yyyy`) persist until rewritten. **My assessment: this does not affect the Jun 13 production release**, because those bad records were created by intermediate builds that only ever ran in QA. 

**Recommendation (sign-off item)**: explicitly confirm that (a) production has never had any pre-final `ION-14382` build deployed, and (b) the Jun 13 artifact is built from the reviewed develop baseline. If both hold, no production backfill is required. (QA itself may still throw sporadic visibility-matcher errors on its poisoned backlog — that's the `2026-05-15` doc — but that's a QA-data issue, not a code defect, and should not gate the release.)

### 🟢 R8 — Minor code smell: `OffsetDateTimeTypeConverter.convert()` appears unused
[OffsetDateTimeTypeConverter.java:27-29](../src/main/java/com/inttra/mercury/booking/dynamodb/OffsetDateTimeTypeConverter.java#L27-L29) — the public `convert()` (ISO_DATE_TIME → `Z`) is a v1-style holdover; the v2 write path now goes through `AuditAttributeConverter.DYNAMO_OBJECT_MAPPER`'s inline serializer instead. It's harmless (and consistent, both produce `Z`) but is dead/duplicated logic — candidate for cleanup post-release, not now.

---

## 3. Cross-module integration assessment

| Consumer | Reads/needs | Booking-v2 produces | Status |
|---|---|---|---|
| **Visibility (v1, `booking:2.1.8.M`)** — reads `booking_BookingDetail` audit/metaData/enrichedAttributes maps | `M` maps; ISO-8601 `Z`/offset timestamps; ISO-`T` `'Z'` for container/package dates | `M`; `Z` (nanos) for audit; ISO-`T` for MetaData; ISO-`T`-`'Z'` for ref-data dates | ✅ Compatible (the whole point of the decoupling) — gated on R1/R2 not regressing |
| **Redshift Glue ETL** — `unix_timestamp(audit,"…SSSZ")` over REST/export | RFC-822 `+0000`, millis | REST path `@JsonFormat(SSSZ)` → `+0000` millis | ✅ Compatible (R3: precision differs from DynamoDB copy, by design) |
| **Transformer / distributor / aw-bridge (SQS)** | `MetaData.timestamp` space format `yyyy-MM-dd HH:mm:ss.SS` | class-level `@JsonFormat(space)` via `Json.toJsonString()` | ✅ Compatible (DLQ incident resolved) |
| **Watermill / messaging consumers** | SQS `MetaData` contract (space) | unchanged space format | ✅ No DynamoDB coupling; unaffected |

The design satisfies all four simultaneously **only because** the DynamoDB and REST/SQS write formats are decoupled. That decoupling is the single most important property to protect (R1).

---

## 4. Documentation quality

The `booking/docs/` trail is unusually thorough and is the main reason this complex, multi-cycle fix is auditable. Two observations:
- The docs are **honest about the iteration** (three reversals of the audit offset format) and about residual backlog — good engineering hygiene.
- A few intermediate docs draw conclusions later proven wrong (e.g. `2026-05-05` §15.4 claimed visibility was unaffected by the audit revert; `2026-05-06` disproved it). For a future reader, a **one-page "final state" summary** stating the *settled* answer (DynamoDB=`Z`/nanos/M, REST=`+0000`/millis, SQS=space) would prevent someone from re-applying a superseded fix. Consider adding it alongside this review.

---

## 5. Pre-release sign-off checklist (Jun 13)

1. **(R7)** Confirm production has never run a pre-final `ION-14382` build, and the release artifact = reviewed develop baseline → then **no backfill needed**.
2. **(R1/R2)** Confirm assertive guard tests pin DynamoDB write format for `Audit` (`Z`, not `+0000`) **and** `MetaData.timestamp` (`T`, not space), including negative assertions. These are the regression tripwires for visibility-v1 compatibility.
3. **(R3)** Add the nanosecond-vs-millisecond precision note to the release runbook.
4. **(R6)** Confirm `spotRates` v1 on-disk type and that no v1 consumer reads it (then the `S` choice is safe).
5. **(R4/R5)** Optional: targeted round-trip tests for `Range`/`EnrichedAttributes` decimal fields if any carry `BigDecimal` bounds.
6. **(R8)** Backlog (post-release): remove dead `OffsetDateTimeTypeConverter.convert()`; add the "final state" summary doc.

**Bottom line**: the implementation is correct and complete for its scope, backward-compatible with v1 visibility and the SQS/watermill and Redshift consumers, and the QA-clean signal is credible. The Jun 13 release is reasonable to proceed with once items 1–2 are confirmed; everything else is low-risk hardening.
