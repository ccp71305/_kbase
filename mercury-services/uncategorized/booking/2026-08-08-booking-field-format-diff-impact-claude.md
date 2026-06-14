# Booking Field Format Diff — Critical Review & Independent Impact Assessment

**Date:** 2026-06-08
**Reviewer model:** Claude Opus 4.8 (1M context)
**Nature of this document:** A *critical, adversarial re-review* of [2026-08-08-booking-field-format-diff-impact.md](2026-08-08-booking-field-format-diff-impact.md), independently verifying every load-bearing claim against the actual code, the AWS SDK source jars, and git history — and surfacing what that document under-stated or missed.

**Inputs re-examined:**
- [2026-06-08-booking-req-field-format-diff.md](2026-06-08-booking-req-field-format-diff.md) (REQUEST diff)
- [2026-06-08-booking-conf-field-format-diff.md](2026-06-08-booking-conf-field-format-diff.md) (CONFIRM diff)
- [2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md](2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md) (design review)
- [2026-08-08-booking-field-format-diff-impact.md](2026-08-08-booking-field-format-diff-impact.md) (the document under review)
- Live converter/entity code, AWS SDK v1 (`1.12.638`) and SDK v2 enhanced (`2.30.24`) **source jars**, and the `ION-14382` git history.

**Release context (per user, confirmed):** PROD runs **only** pre-upgrade (SDK v1) code today. QA runs post-upgrade (SDK v2) code. QA certified for release **Jun 13**, including integration testing with Visibility, Watermill, and Redshift. *QA certification is treated as supporting evidence, not proof.* PROD has very high daily volume, so any latent format defect is high-blast-radius.

> **Revision 2026-06-09 (post-review verification).** After this review the raw PROD/QA DynamoDB dumps were diffed field-by-field, the published `booking:2.1.8.M` jar was inspected, and guard tests were written. Net effect: **F1/R3 and F5 downgraded** (the "data loss" is master-data drift, not a regression; the empty-string collapse is pre-existing, not new), **R1 and R6 closed**, and the F6 line references corrected. Each affected section below carries an inline **[UPDATE 2026-06-09]** note; the risk register (§3) reflects the revised status.

---

## 0. Bottom line

**I concur with the prior document's headline conclusion — none of the 7 documented format differences is a functional regression, and the release is not blocked by them — but I reach it on firmer evidence, and I reject the prior document's reasoning in three places where it asserted compatibility without proof or leaned on a comparison that cannot support the claim.**

The prior document is *directionally correct but over-confident*. It presents "NO IMPACT" verdicts as settled facts where several rested on unverified assertions ("SDK v1 reads both N and BOOL", "SDK v2 handles N→boolean coercion", "consumers access by role not index"). I verified each of these at source/code level. They happen to hold — but the prior document had not earned those conclusions, and one of them (the migration-boundary boolean read) is **not covered by any test**, which means QA's clean signal does *not* actually exercise it.

**The single most important reframing:** the risk that matters is not "QA records differ from PROD records." It is **"on Jun 13, v2 code begins reading the entire existing v1-written PROD table"** (every in-flight booking created before the cutover, every amend/confirm/query against historical records). That is the real compatibility surface, and — critically — it is the one surface QA's data may *never* have exercised, because QA records were largely written by v2 already. Everything below is organized around that reframing.

| Area | Prior doc verdict | My verdict | Confidence basis |
|---|---|---|---|
| Top-level boolean N→BOOL read by **v2 itself** (migration boundary) | "handles coercion" (asserted) | **Safe** — but **untested** | SDK v2 `BooleanAttributeConverter` 2.30.24 source: `convertNumber` maps "0"/"1" |
| Nested boolean N→BOOL read by v2 | Safe | **Safe** | `LegacyMapConverter` N→Integer + Jackson int→boolean coercion |
| BOOL read by **Visibility v1** | "SDK v1 reads both" (asserted) | **Safe** | SDK v1 `BooleanUnmarshaller` source: handles BOOL *and* N, schema-independent |
| `partyId`/`partyScac` removal | Safe | **Safe** (and *more* benign than argued) | Visibility never reads `partyId`; both are `@JsonIgnore`-driven |
| `splitCopy` removal | Safe (bug fix) | **Safe** | git confirms `@DynamoDBIgnore` on field pre-upgrade; `@DynamoDbIgnore` on getter now |
| `notificationParties` empty-list absence | Safe | **Safe** | `@JsonInclude(NON_EMPTY)` now respected |
| Null expansion (153/314) | Benign | **Benign functionally**; minor cost/ops note at PROD volume | DynamoDB NULL == absent on read |
| Party/location reordering | Safe (per user) | **Safe for all *production* code** | No order-dependent positional access in prod code |
| **Location/address "data loss" (Cat 3c/3d)** | "data-dependent, no impact" | **Master-data-driven, not a regression** (verified against raw dumps) | Same company IDs resolve to *different* master records per environment |
| **DynamoDB Streams / CDC consumers** | *not addressed* | **Safe** — stream is `KEYS_ONLY` | `@DynamoDBStream(KEYS_ONLY)`; consumers re-fetch via typed DAO |

---

## 1. Where the prior document was right but under-proven (now verified)

### 1.1 Top-level boolean `N`→`BOOL` — the migration-boundary read **(the one that mattered most)**

The prior doc (Gap 1) said: *"Top-level fields: SDK v2 Enhanced Client handles N→boolean coercion."* This was an **assertion with no evidence**, and it is the highest-stakes claim in the entire analysis, because:

- `coreBooking` ([BookingDetail.java:154](../src/main/java/com/inttra/mercury/booking/model/BookingDetail.java#L154)) and `nonInttraBooking` ([BookingDetail.java:152](../src/main/java/com/inttra/mercury/booking/model/BookingDetail.java#L152)) are bare `private boolean` with **no `@DynamoDbConvertedBy`** — they do **not** go through `LegacyMapConverter`. They are handled by the Enhanced Client's *default* `BooleanAttributeConverter`.
- On Jun 13, every existing PROD record (booleans stored as `{"N":"0"/"1"}` by v1) will be read by v2. If the default converter rejected `N`, **every legacy record read would throw** — a catastrophic, high-volume failure on day one.

**Verified (SDK v2 `dynamodb-enhanced:2.30.24` sources jar):**
`BooleanAttributeConverter.transformTo()` does not require BOOL; it dispatches through `TypeConvertingVisitor`, whose `convertNumber(String)` is overridden:
```java
case "0": return false;
case "1": return true;
default:  throw new IllegalArgumentException("Number could not be converted to boolean: " + value);
```
So the accepted types are **BOOL, String, and N("0"/"1")**. Reading a v1 record's `N`-typed top-level boolean **coerces cleanly**. ✅ Not a blocker.

> ⚠️ **Gap the prior doc did not flag: this path has ZERO test coverage.** The fixtures `request_detail.json` / `confirm_detail.json` carry `"coreBooking": 0` but are loaded by **Jackson** (`JsonSupport.OBJECT_MAPPER`), not the Enhanced Client — so they exercise Jackson's coercion, not `BooleanAttributeConverter`. `BookingDetailDateFormatCompatibilityTest` tests raw-`AttributeValue` reads for the *custom* converters and feeds the one boolean it touches (`bookingWithMigratedParties`) as **BOOL**, never `N`. **No test maps an `N`-typed top-level boolean into `BookingDetail` via the Enhanced Client.** QA's clean signal therefore likely never exercised the actual migration-boundary read (QA records were written by v2 as BOOL). The behavior is correct *today* by SDK source, but it is unguarded against an SDK bump. **See R1.**
>
> **[UPDATE 2026-06-09 — R1 now closed.]** A guard test was added: [`BookingFieldFormatMigrationTest`](../src/test/java/com/inttra/mercury/booking/dynamodb/converter/BookingFieldFormatMigrationTest.java) (`LegacyBooleanMigrationBoundaryRead`) builds the real `TableSchema.fromBean(BookingDetail.class)` and maps a v1-shaped item with `coreBooking`/`nonInttraBooking` as `AttributeValue.fromN("0"/"1")`, asserting they coerce to the correct booleans — the exact Jun-13 cutover read QA never exercised — plus the native-BOOL read and the v2-writes-BOOL forward format. 5/5 pass.

### 1.2 Nested boolean `N`→`BOOL` (inside `enrichedAttributes`)

Verified the full chain in [LegacyMapConverter.java:68-85](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java#L68-L85): an `N` value is parsed to **`Integer`/`Long`/`Double`** (never Boolean), then [EnrichedAttributesConverter.java:52](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverter.java#L52) runs `OBJECT_MAPPER.convertValue(map, EnrichedAttributes.class)`, and Jackson coerces `Integer 0/1 → boolean`. ✅ Works for `bookingWithMigratedParties`, `displayFlag`, `oogFlag`, `spareIndicator`. The prior doc described this correctly.

### 1.3 BOOL read by Visibility v1 — **proven, not assumed**

The prior doc asserted *"SDK v1 DynamoDBMapper (v1.11.x+) reads both N and BOOL types natively."* I verified this two independent ways against the **SDK v1 `1.12.638` sources jar**:

1. **The read path is schema-independent.** All three conversion schemas (V1, V1_COMPATIBLE, V2) share the same `StandardUnmarshallerSet`. `BooleanUnmarshaller.unmarshall()` returns `value.getBOOL()` if present, else parses `N` "1"/"0" (its javadoc literally cites "backwards compatibility"). So *regardless* of schema, v1 reads BOOL.
2. **The effective schema is `V2_COMPATIBLE` anyway.** Visibility wires its mapper via [`DynamoDBModule`](../../libs/dynamo-client/src/main/java/com/inttra/mercury/dynamo/respository/module/DynamoDBModule.java) which never calls `.withConversionSchema(...)`; the unset value resolves through `DynamoDBMapperConfig.DEFAULT.merge(...)` to `ConversionSchemas.DEFAULT = V2_COMPATIBLE`.

✅ Visibility v1 reading v2-written BOOL records is safe. **Residual:** I inspected the working-tree (already-migrated) `BookingDetail`, not the *published* `booking:2.1.8.M` jar visibility actually compiles against. The boolean read mechanics don't depend on it, but a 1-line confirmation against the real 2.1.8.M `BookingDetail` removes all residual doubt (R6).

### 1.4 `partyId` / `partyScac` / `splitCopy` / `notificationParties` — intentional, git-confirmed

git `6cdba47f53^` confirms the prior doc's annotation archaeology:
- **TransactionParty (pre-upgrade):** `@DynamoDBDocument` on class; `@JsonIgnore private String partyScac` (line 88-89); `@JsonIgnore getPartyId()` with **no** `@DynamoDBIgnore` (line 168-169). → v1 wrote `partyId`/`partyScac` because it ignores `@JsonIgnore`. Post-upgrade Jackson respects `@JsonIgnore` → both dropped. ✅
- **BookingDetail (pre-upgrade):** `@DynamoDBIgnore private boolean isSplitCopy` — annotation on the **field**, while Lombok `@Data` generated the getter without it → v1 wrote `splitCopy`. Post-upgrade [BookingDetail.java:227-229](../src/main/java/com/inttra/mercury/booking/model/BookingDetail.java#L227-L229) puts `@DynamoDbIgnore` on the **explicit getter** → correctly dropped. ✅
- **`partyId` is even more benign than the prior doc argued.** The prior doc constructed an elaborate "visibility calls `setPartyId()` from the attribute, falls back to `partyINTTRACompanyId` for new records" argument. **Independent search found visibility never reads `partyId` at all** (no attribute reader, no getter use on the booking read path). The fallback argument is unnecessary; absence is simply invisible to visibility.

---

## 2. New findings the prior document missed or under-stated

### 🟠 F1 — The diff's "data loss" categories (Cat 3c/3d) are **unprovable from the diff itself** — methodology flaw

This is my most important substantive disagreement. The prior doc dismisses location/address "data loss" as *"data-dependent, NO IMPACT."* That is the *likely* explanation, but the prior doc treats it as a conclusion when **the diff is structurally incapable of supporting either conclusion**:

- The REQUEST diff compares PROD bookingId **`70e09110…`** against QA bookingId **`ab762edd…`** ([req diff, Appendix](2026-06-08-booking-req-field-format-diff.md)). **These are two different bookings**, with different parties, carriers, locations, and company profiles.
- Therefore a field that is `"SALTA"` in PROD and `NULL` in QA, or a location resolved in PROD but not in QA, **tells us nothing** about whether v2's enrichment/resolution logic regressed. It could be a genuine resolution bug *or* simply different input data — and the diff cannot distinguish them.

The "data-dependent" reading is plausible (different test companies, different location sets) and is *consistent* with the CONFIRM diff's own observation that the apparent location[0] loss is really just reordering with the data present elsewhere. But **"consistent with benign" is not "proven benign."** The only way to actually rule out a location-resolution regression is a **same-input replay**: feed one identical booking payload through v1 and v2 and diff the outputs. Nothing in the evidence chain does this.

**Net:** I downgrade Cat 3c/3d from "NO IMPACT (proven)" to **"probably data-dependent; not provable from this diff — verify by replay before relying on it."** Given PROD volume and that location resolution drives downstream visibility/reporting, this is worth one controlled replay rather than an assumption. (Severity moderate, not blocking — enrichment code itself was not changed by the format migration; the converters only change *serialization*, not *resolution* logic. But the diff was offered as evidence and cannot bear that weight.)

> **[UPDATE 2026-06-09 — verified against the raw dumps; downgraded to non-regression.]** I diffed the two REQUEST dumps (`PROD-/QA-DianamoDBJSON-RequestBK.txt`) field-by-field. The booking *template* is identical (same `shipmentId` `BK3PATRG22MAY26_RR101`, same `senderID` `CU2100`, same `messageDate`, and **the same company IDs** — Booker/Forwarder `802442`, Carrier `802435`, CustomsBroker `802443`, Shipper `802437`), confirming QA's "same input relay." **But the master/reference records keyed by those same IDs differ per environment:** company `802437` resolves to "TestCompany007 / RESDA, ARGENTINA, state SALTA" in PROD vs "TESTqaSHIPPER X12 / ANDULO, INDIA, state null" in QA; company `802442` resolves to Finland in PROD vs Parsippany, US in QA; `802443` is Finland (PROD) vs Brazil (QA). So the Cat 3d "`Shipper.state SALTA → null`" loss is simply the same company ID having a state in one environment's master data and not the other's — **master-data drift, not a v2 serialization/resolution regression.** This corroborates the user's read. The methodology caveat survives only in weak form (a cross-environment diff can never *prove* the absence of a resolution regression because the resolved inputs differ), so the same-input replay (R3) is now a nice-to-have, not a release gate.

### 🟡 F2 — `partyName` is a **newly persisted attribute**, not merely a null-expansion field

The prior doc folds `partyName` into the null-expansion bucket. git shows the real change: pre-upgrade `@JsonProperty @DynamoDBIgnore private String partyName` (field **was excluded** from DynamoDB by `@DynamoDBIgnore`); post-upgrade [TransactionParty.java:47-49](../src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/TransactionParty.java#L47-L49) drops `@DynamoDBIgnore`, so Jackson now **serializes `partyName`** (type `S` when populated). This is an *additive* schema change in the opposite direction from the dropped fields. Functional risk is low (it's a derived concat of `partyName1`+`partyName2` via `getPartyName()`, and no consumer was found reading it), but it should be recorded honestly as **"field added,"** not "null when empty," and it contributes to item-size growth (F4).

### 🟡 F3 — DynamoDB Streams / CDC was never assessed; it is **safe, but for a non-obvious reason**

The REQUEST diff explicitly warned that NULL expansion could affect *"DynamoDB Streams consumers that diff old/new images."* The prior doc never addressed streams at all. I checked:

- [BookingDetail.java:54](../src/main/java/com/inttra/mercury/booking/model/BookingDetail.java#L54): `@DynamoDBStream(StreamViewType.KEYS_ONLY)` — the stream carries **keys only, never the attribute image**. Confirmed in design docs ("DynamoDB Streams are enabled on BookingDetail with KEYS_ONLY").
- Both stream consumers — the ES `IndexerHandler` and the S3-archive Lambda ([S3ArchiveHandler.java](../src/main/java/com/inttra/mercury/booking/lambda/S3ArchiveHandler.java)) — read only `bookingId`/`sequenceNumber` from the stream, then **re-fetch the full record through the typed v2 DAO** and serialize the Java object. The S3/Redshift JSON mapper (`S3ARCHIVE_OBJECT_MAPPER`) is configured `NON_NULL`/`NON_EMPTY`, so it omits nulls regardless.

**Consequence:** the raw DynamoDB attribute image (N-vs-BOOL, `{"NULL":true}`, dropped attributes) is **never exposed to any stream/CDC consumer**. This is a genuine *strengthening* of the safety case the prior doc didn't make. The one residual: the `*_TableStreamTopic` SNS fan-out exists; if any consumer **outside this repo** were ever wired to consume a raw image it would be exposed — but `KEYS_ONLY` means there is no image to consume, so this is moot as long as the table's stream view type stays `KEYS_ONLY`. (R7.)

### 🟡 F4 — Null expansion at PROD volume: not a *correctness* issue, but a real *write-cost / throughput* one

The prior doc calls the size impact "negligible." Functionally for reads, yes. But at "huge daily volume":
- CONFIRM records gain **~314 explicit `{"NULL":true}` attributes** (plus the new `partyName` S-values). DynamoDB **write capacity is billed per 1 KB rounded up**, so any record pushed across a 1 KB boundary costs an extra WCU on *every* write — and booking writes multiple versions per booking lifecycle. At high volume this is a measurable cost and, under provisioned/burst limits, a **throttling** risk, not just a storage line-item.
- The 400 KB item-limit headroom is almost certainly fine for normal bookings, but a worst-case booking (many parties × many containers × NULL-expanded nested objects) moves materially closer to the ceiling than the v1 representation did. Worth a one-time check of the largest existing PROD items' projected post-upgrade size.

**Not blocking.** The clean, low-effort mitigation already exists and is noted in both the prior doc and design review R-items: skip nulls on write in `LegacyMapConverter.toAttributeValueMap` (don't emit `fromNul(true)` for null values) or add `@JsonInclude(NON_NULL)`. I'd schedule this as fast-follow, not pre-release, *unless* a size projection shows items near the limit.

### 🟡 F5 — Empty-string → NULL collapse is a real round-trip change (design review R4, not in the impact doc)

[LegacyMapConverter.java:135-137](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java#L135-L137): on write, an **empty `String` becomes `{"NULL":true}`**; on read it returns `null`. So any field that was `""` in a v1 record (or set to `""` at runtime) round-trips to `null` after a v2 save. The impact doc omits this entirely. For audit/metadata it's harmless; the open question is whether any field in `EnrichedAttributes`/`Range`/`Condition` *semantically distinguishes* empty-string from null (e.g., a code that means "explicitly cleared" vs "never set"). I found no such field in the party/address/location models, but this wasn't exhaustively proven across all nested types. Low risk; worth a grep during hardening.

> **[UPDATE 2026-06-09 — verified as a non-regression.]** Checked the raw dumps: **`grep '"S": ""'` returns 0 in all four PROD and QA records.** SDK v1 also never persisted empty strings (DynamoDB historically rejected them), so the `"" → null` collapse is **pre-existing behavior unchanged by the upgrade**, not a new round-trip regression. And no converter-path model field distinguishes `""` from `null` semantically (the only status-like string, `ValidationMessage.messageCode`, is not persisted). F5 stays Low and needs no pre-release action.

### 🟢 F6 — Ordering: confirmed safe for **production** code; the only positional access is in **tests**

The prior doc asserted "all consumers access by role, not index." I verified across booking/visibility/watermill:
- **Production main code is safe.** `EnrichedAttributes.getResolvedParty(role)` filters by `calcPartyRole()`; `OutboundServiceImpl.java:246-250` loops but matches on `PartyRole.Carrier` *inside* the loop (order-independent); `HeaderLocationValidations.java:61,64` accesses `.get(0)` only when `size()==1`. No production consumer relies on party/location list order.
- **Test code does rely on order** (`BookingDetailDaoIT` lines 676/736/934, `OutboundServiceTest` 2205-2206 use `.get(0)`). These are test brittleness, not a production data risk — but they mean the test suite *bakes in a specific order*, so if those tests pass in QA it does **not** prove order-independence of any real consumer (it only proves the QA serialization order happened to match the fixtures). The production safety comes from the code review above, not from the green tests.

> **[UPDATE 2026-06-09 — line references corrected.]** Re-checked against current files. The genuinely order-imposing assertions are **`OutboundServiceTest` [:227-229](../src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceTest.java#L227-L229) and [:234](../src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceTest.java#L234)** — `contract.getTransactionParties().get(0)` / `.get(1)` `.getPartyResolvedAlias()` and `getTransactionLocations().get(0)` (flat list, multiple indices). The other cited references are **not** actually order-sensitive: `BookingDetailDaoIT` [:676](../src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoIT.java#L676) and [:736](../src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoIT.java#L736) are each guarded by `hasSize(1)` on the line above; [:934](../src/test/java/com/inttra/mercury/booking/dao/BookingDetailDaoIT.java#L934) and `OutboundServiceTest` 2205-2206 index into a **role-keyed `partyMap` list**, not the flat reordered `transactionPartyList`. The §F6 conclusion is unchanged; only the citations are tightened.

This matters for the user's "don't treat QA as foolproof" instruction: the ordering tests passing is **not** evidence; the code-level role-keyed access is.

---

## 3. Consolidated risk register

| ID | Risk | Severity | Status | Action |
|----|------|----------|--------|--------|
| **R1** | Migration-boundary read of `N`-typed **top-level** booleans by v2 is correct but **untested**; QA likely never exercised it | Medium (latent) | **CLOSED 2026-06-09** — guard test added (`BookingFieldFormatMigrationTest`), 5/5 pass | — (test pins behavior against SDK bumps) |
| **R2** | Audit/MetaData DynamoDB write-format coupling (`Z`/`T`, not `+0000`/space) can silently regress visibility v1 | Medium | Guarded (design-review R1/R2 + new tripwire test) | Keep negative-assertion guard tests; **most important standing pre-release tripwire** |
| **R3** | Location/address "data loss" (Cat 3c/3d) | Low (was Moderate) | **Master-data drift, not a regression** — verified against raw dumps 2026-06-09 | Optional same-input replay for completeness; **no longer a release gate** |
| **R4** | Null expansion → write-cost/throttling at high volume; worst-case item size | Low-Moderate (ops/cost) | Functional reads fine | Project largest-item size; optionally suppress null writes as fast-follow |
| **R5** | Empty-string→null round-trip collapse | Low | **Non-regression** — v1 never stored empty strings either (verified) | No action; note for hardening only |
| **R6** | Conclusions verified against working-tree `BookingDetail`, not the published `booking:2.1.8.M` jar visibility compiles against | Low | **CLOSED 2026-06-09** — `javap` of `booking-2.1.8.M.jar` confirms plain `boolean` getters, SDK-v1 annotations, no boolean type converter (reads both `N` and `BOOL`) | — |
| **R7** | Any out-of-repo consumer of the table's stream image | None while `KEYS_ONLY` | Mooted by KEYS_ONLY | Don't change stream view type to `NEW_IMAGE` without re-assessing |

**No blocker.** As of 2026-06-09, R1 and R6 are closed by verification, R3 and R5 are downgraded to non-regressions, and R2 remains the standing write-format tripwire (now guarded by tests).

---

## 4. Recommendations

1. **(R1 — ✅ DONE 2026-06-09)** Guard test added: [`BookingFieldFormatMigrationTest`](../src/test/java/com/inttra/mercury/booking/dynamodb/converter/BookingFieldFormatMigrationTest.java) maps an `N("0"/"1")`-typed item through the real `TableSchema.fromBean(BookingDetail.class)` and asserts `coreBooking`/`nonInttraBooking`. Covers the Jun-13 cutover read and pins it against a future `dynamodb-enhanced` upgrade. 5/5 pass.
2. **(R3 — downgraded, optional)** Raw-dump diff (2026-06-09) showed Cat 3c/3d is **master-data drift, not a resolution regression** (same company IDs resolve to different master records per environment). A same-input replay is now optional for completeness, not a release gate.
3. **(R2)** Negative-assertion guard tests for `Audit` (`Z`, not `+0000`) and `MetaData.timestamp` (`T`, not space) exist in `BookingDetailDateFormatCompatibilityTest` and now also in `BookingFieldFormatMigrationTest` (`WriteFormatVisibilityTripwire`). Keep them running in CI. (Carried from design review §5.)
4. **(R4 — fast-follow)** Project post-upgrade item size for the largest existing PROD records; if any approach the 400 KB ceiling or sit just above a 1 KB WCU boundary, suppress null writes in `LegacyMapConverter`/via `@JsonInclude(NON_NULL)`.
5. **(R6 — ✅ DONE 2026-06-09)** `javap` of `booking-2.1.8.M.jar` confirms `coreBooking`/`nonInttraBooking` are plain `boolean` getters with SDK-v1 annotations and **no** boolean type converter → default unmarshaller reads both `N` and `BOOL`. Visibility read path fully closed.
6. **(documentation)** Record `partyName` as a *newly persisted* attribute (F2) so a future reader doesn't mistake it for a regression in the other direction.

---

## 5. What I did *not* find (honest negatives)

- No raw-DynamoDB-image consumer (stream is `KEYS_ONLY`; all consumers re-fetch typed).
- No production code with order-dependent positional access to party/location lists.
- No consumer that reads `partyId`/`partyScac` as a raw attribute.
- No custom `AttributeConverterProvider`/boolean-converter override in booking or cloud-sdk (so the default-converter behavior in §1.1 is authoritative).
- No evidence the migration changed enrichment/resolution *logic* (only serialization), which is the main reason F1/R3 is "probably benign" — but I did not prove it by replay.

---

## Appendix A: Evidence trail (files / sources inspected)

| Item | Location | What it proved |
|---|---|---|
| Default SDK v2 boolean converter accepts `N` | `dynamodb-enhanced:2.30.24` sources → `BooleanAttributeConverter` / `TypeConvertingVisitor` | §1.1 — `N "0"/"1"` coerces, else `IllegalArgumentException` |
| SDK v2 version in use | [booking/pom.xml:86](../pom.xml#L86) → `cloud-sdk-aws:1.0.26` → `dynamodb-enhanced:2.30.24` | §1.1 version pin |
| SDK v1 boolean read is schema-independent | `aws-java-sdk-dynamodb:1.12.638` sources → `ConversionSchemas`, `BooleanUnmarshaller` | §1.3 — v1 reads BOOL *and* N |
| Visibility mapper schema = V2_COMPATIBLE | [DynamoDBModule.java](../../libs/dynamo-client/src/main/java/com/inttra/mercury/dynamo/respository/module/DynamoDBModule.java) + `ConversionSchemas.DEFAULT` | §1.3 |
| Nested boolean coercion chain | [LegacyMapConverter.java:68-85](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java#L68-L85), [EnrichedAttributesConverter.java:52](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/EnrichedAttributesConverter.java#L52) | §1.2 |
| Top-level booleans use default converter | [BookingDetail.java:152-154](../src/main/java/com/inttra/mercury/booking/model/BookingDetail.java#L152-L154) (no `@DynamoDbConvertedBy`) | §1.1 |
| Pre-upgrade annotations | `git show 6cdba47f53^:…/TransactionParty.java`, `…/BookingDetail.java` | §1.4 (`@JsonIgnore`, `@DynamoDBIgnore`, `@DynamoDBDocument`) |
| `partyName` newly persisted | git pre: `@DynamoDBIgnore private String partyName`; now [TransactionParty.java:47-49](../src/main/java/com/inttra/mercury/booking/model/Common/Artifacts/TransactionParty.java#L47-L49) | F2 |
| Stream is KEYS_ONLY | [BookingDetail.java:54](../src/main/java/com/inttra/mercury/booking/model/BookingDetail.java#L54), [S3ArchiveHandler.java](../src/main/java/com/inttra/mercury/booking/lambda/S3ArchiveHandler.java) | F3 |
| Empty-string→null collapse | [LegacyMapConverter.java:135-137](../src/main/java/com/inttra/mercury/booking/dynamodb/converter/LegacyMapConverter.java#L135-L137) | F5 |
| Cross-booking diff | [req diff Appendix](2026-06-08-booking-req-field-format-diff.md) (PROD `70e09110…` vs QA `ab762edd…`) | F1/R3 |
| No positional prod access | `EnrichedAttributes.getResolvedParty`, `OutboundServiceImpl:246-250`, `HeaderLocationValidations:61,64` | F6 |

## Appendix B: How this review differs from the document it reviews

| Dimension | Prior impact doc | This review |
|---|---|---|
| Boolean compat | Asserted "both read both" | Proven against v1 **and** v2 SDK source; flagged the untested migration-boundary path |
| Streams/CDC | Not addressed | Assessed; safe because `KEYS_ONLY` |
| "Data loss" (Cat 3c/3d) | "data-dependent, NO IMPACT" | Methodology flaw exposed: unprovable from a cross-booking diff; replay required |
| `partyName` | Treated as null-expansion | Identified as a newly-persisted attribute |
| Item size | "negligible" | WCU/throughput + worst-case-size note at PROD volume |
| Empty-string→null | Omitted | Surfaced (design-review R4) |
| Test coverage | Cited QA as confirmation | Distinguished what QA actually exercised vs asserted; named the specific missing test (R1) |
| Stance | Closes every item "NO IMPACT" | Concurs on releasability; leaves R1/R3 explicitly open as cheap closes |
