# PIBK — `EDataSupplementationException: Cannot parse date "…+00:00"` — Analysis & Fix

- **Date:** 2026-09-09
- **Module:** `partner-integrator` (`pi-booking-processor`, aka **PIBK**) + `booking` (root cause lives here)
- **Environment:** QA — log group `642960533737:inttra2-qa-lg-pi`, stream `PIBK-latest-qa-Task/PIBK-qa-Container/…`
- **Session:** `59a4c1b2109b487d` (ION-16417 PI AWS Upgrade)
- **Related upstream change:** booking `bk3` AWS SDK v1→v2 upgrade (`ION-14382`)
- **Model used:** Claude Opus 4.8 (GitHub Copilot CLI)
- **Status:** **Two fixes now implemented & verified.** (1) *Fix S (source, self-contained in this repo):* added `@JsonFormat` to pi-commons `PackageType.lastModifiedDateUtc` — a new `EnrichmentServiceTest` reproduces the exact production error without it and passes with it, **against the current (unfixed) vendored booking jar**, so this alone unblocks PIBK with no booking release. **Committed on branch `bugfix/ION-16819-pibk-dateformat-fix` (commit `7390ae6877`).** (2) *Fix R (reader hardening in booking):* `XXX` patterns in `FlexibleDateDeserializer` (15/15 tests green), **stashed** for the next booking-model release (§9, §18).

---

## 1. Issue Summary

PIBK (partner-integrator booking processor) fails to process booking messages in QA with:

```
com.inttra.mercury.common.exception.EDataSupplementationException:
  com.fasterxml.jackson.databind.JsonMappingException: Unexpected IOException (of type java.io.IOException):
  Cannot parse date: "2018-06-13T12:00:00.000+00:00".
  Supported formats: epoch millis, yyyy-MM-dd HH:mm:ss, yyyy-MM-dd'T'HH:mm:ss.SSS'Z'
```

The date value `2018-06-13T12:00:00.000+00:00` is an **ISO-8601 timestamp with a colon in the timezone offset** (`+00:00`). The failure aborts the entire booking-feed message (the handler wraps *any* exception into `EDataSupplementationException`).

---

## 2. Root Cause Analysis

**Failing class:** `com.inttra.mercury.booking.networkservices.referencedata.model.FlexibleDateDeserializer` (in the **booking** module, shipped to PIBK via the committed `booking-3.0.0.M.jar`).

Its supported `SimpleDateFormat` patterns are:

```java
private static final String[] FORMATS = {
    "yyyy-MM-dd HH:mm:ss",
    "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
    "yyyy-MM-dd'T'HH:mm:ss.SSSZ",   // 'Z' = RFC-822 offset -> accepts +0000, NOT +00:00
    "yyyy-MM-dd'T'HH:mm:ss'Z'",
    "yyyy-MM-dd'T'HH:mm:ssZ"
};
```

The only numeric-offset patterns use the RFC-822 `Z` token, which parses `+0000` (no colon). **None of the patterns accept an ISO-8601 offset containing a colon (`+00:00`)**, so `2018-06-13T12:00:00.000+00:00` matches nothing and the deserializer throws `IOException`.

**Empirically verified** (JDK `SimpleDateFormat`, `setLenient(false)`, UTC):

| Input value | Current FORMATS | With `XXX` patterns added |
|---|---|---|
| `2018-06-13T12:00:00.000+00:00` | ❌ fail | ✅ parse |
| `2020-12-08T18:07:00.000+0000` | ✅ | ✅ |
| `2020-12-08T18:07:00.000Z` | ✅ | ✅ |
| `2020-12-08 18:07:00` | ✅ | ✅ |
| `2020-12-08T18:07:00Z` | ✅ | ✅ |

### Execution path (confirmed against live QA logs — see §10)

1. `BookingFeedHandler.processMessage` → `BookingService.processBookingMessage` → transformer → `EnrichmentService`.
2. `EnrichmentService.collectContainerTypes()` / `collectPackageTypes()` call `pi-commons` `ReferenceDataService.getContainerGroupType()` / `getPackageType()`, which hit the network **reference-data API** (`GET https://api-beta.inttra.com/network/containertype?typeCode=42R1` and `…/network/packagetype?edifactCode=PK`). That API returns `lastModifiedDateUtc` as **epoch milliseconds** — `1528891200000` (= `2018-06-13T12:00:00Z`).
3. `EnrichmentService.getFromBookingClass()` (line 235) does a JSON round-trip: `JsonSupport.toJson(piCommonsModel)` → `JsonSupport.fromJson(json, bookingModel.class)`. **This re-serialization step is what mints the `+00:00` string.**
4. The failing field is **`PackageType.lastModifiedDateUtc`**: the **pi-commons** `PackageType` has **no `@JsonFormat`** on that `Date`, so `JsonSupport.toJson` falls back to Jackson's default `StdDateFormat` (ISO-8601 = `yyyy-MM-dd'T'HH:mm:ss.SSSXXX`), which renders the instant as `2018-06-13T12:00:00.000+00:00` (millis + **colon** offset). (`ContainerType` does **not** fail — its pi-commons copy carries `@JsonFormat("yyyy-MM-dd HH:mm:ss")`, so it round-trips as the space format, which `FlexibleDateDeserializer` accepts.)
5. `JsonSupport.fromJson(...)` deserializes into the **booking** `PackageType`, whose `lastModifiedDateUtc` uses `@JsonDeserialize(using = FlexibleDateDeserializer.class)`. The colon offset matches none of its patterns → `IOException`.
6. `BookingFeedHandler`'s `catch (Exception e)` rewraps it as `EDataSupplementationException`, failing the whole message.

### Why it worked before and breaks now (corrected — the trigger is the model's *reader*, not the Jackson version)

Evidence from the pre-upgrade vs post-upgrade jars and a direct Jackson probe:

- **Before the PI AWS upgrade**, `pi-booking-processor` used booking model **`2.1.7.M`** (`partner-integrator/pi-booking-processor/pom.xml` at `8bba065f0e^`). In that jar, `…referencedata.model.PackageType.lastModifiedDateUtc` is a **bare `java.util.Date` with NO `@JsonDeserialize`** (only AWS SDK v1 `@DynamoDBDocument` annotations). So on the `fromJson` side Jackson used its **default `StdDateFormat` reader**.
- **Jackson's default `StdDateFormat` natively parses ISO-8601 colon offsets.** Proven with a plain `ObjectMapper` (no custom deserializer):

  | Input | default `ObjectMapper` |
  |---|---|
  | `2018-06-13T12:00:00.000+00:00` | ✅ → epoch `1528891200000` |
  | `2018-06-13T12:00:00.000+0000` | ✅ |
  | `2018-06-13T12:00:00.000Z` | ✅ |
  | `1528891200000` | ✅ |

  So with the old model, this value parsed **regardless of the Jackson version** — there was nothing to break.
- **After the upgrade**, booking model **`3.0.0.M`** (introduced by the booking `bk3` upgrade `ION-14382`) added **`@JsonDeserialize(using = FlexibleDateDeserializer.class)`** to `PackageType.lastModifiedDateUtc`. That custom deserializer **replaces** Jackson's capable default `StdDateFormat` with a **hardcoded list of `SimpleDateFormat` patterns that omits the ISO colon offset** → it rejects `+00:00`.

**So the decisive change is the booking-model upgrade swapping the tolerant default reader for a stricter custom one — not the Jackson library version.**

**What role does the Jackson version actually play?** A supporting (necessary-but-not-new) one. Jackson `StdDateFormat` *serializes* the offset with a colon (`+00:00`) since **2.9** (jackson-databind #1744); pre-2.9 it wrote `+0000` (which the new `FlexibleDateDeserializer` *does* accept via its `…SSSZ` pattern). So the failure needs the produced string to be the **colon** form. But the pre-upgrade stack was already on a modern (Jakarta) Dropwizard → Jackson **≥ 2.9** (the local `.m2` even resolves `jackson-databind 2.10.0`), so the colon form was **already being produced before the upgrade** and the old tolerant reader simply accepted it. The current pin is `jackson-bom 2.21.4` (added in the upgrade commit `8bba065f0e`; partner-integrator pinned **no** Jackson before that — it was transitive, but still ≥ 2.9).

> **Bottom line:** the version bump did *not* flip `+0000`→`+00:00` at the 2.9 boundary in this change (both old and new were ≥ 2.9). The behaviour changed because the **model upgrade replaced Jackson's default `StdDateFormat` reader with `FlexibleDateDeserializer`**, whose format list is missing the colon-offset pattern. Jackson ≥ 2.9 emitting the colon form is a *precondition* for the new reader to trip, but it was already true beforehand.

`FlexibleDateDeserializer`'s patterns cover literal `Z`, space, epoch-millis and RFC-822 `+0000`, but **not** ISO-8601 `+00:00`. The existing unit test `shouldDeserializeIso8601WithTimezoneOffset` only exercises `+0000`, so the gap was never caught.

---

## 3. Impact Assessment

- **Affected models:** booking `ContainerType.lastModifiedDateUtc` and `PackageType.lastModifiedDateUtc` (both use `FlexibleDateDeserializer`).
- **Affected flow:** every PIBK booking message that enriches a container/package type whose reference-data record carries a colon-offset `lastModifiedDateUtc` fails end-to-end (message-level failure, not field-level degradation).
- **Blast radius:** any consumer of the booking jar that deserializes reference-data dates via `FlexibleDateDeserializer`. The enrichment path is shared across booking states (REQUEST/AMEND/CONFIRM/PENDING/CANCEL/DECLINE/REPLACE).
- **Data-dependent:** triggered by the *format* the reference-data API returns per record, so it is intermittent and record-specific.

---

## 4. Fix Options

| # | Option | Description | Pros | Cons | Security |
|---|--------|-------------|------|------|----------|
| A | **Add ISO-8601 colon-offset patterns to `FlexibleDateDeserializer.FORMATS`** (`yyyy-MM-dd'T'HH:mm:ss.SSSXXX`, `yyyy-MM-dd'T'HH:mm:ssXXX`) | `SimpleDateFormat` `XXX` accepts both `+00:00` and `Z`. Minimal, additive, contained in the deserializer already responsible for this. | Surgical; preserves all existing formats; no API change; easy to test | Still enumerates formats (acceptable) | None |
| B | Parse with `java.time.OffsetDateTime` / `DateTimeFormatter.ISO_OFFSET_DATE_TIME` then convert to `Date`, with fallbacks | Robust ISO-8601 handling | Larger rewrite of the deserializer; behavioural risk across all existing inputs | None |
| C | Fix at source: make the reference-data API always emit non-colon `+0000` | Removes variance | Out of partner-integrator/booking scope; doesn't fix already-stored/other callers; slow cross-team change | None |
| D | Align pi-commons/booking `@JsonFormat` and drop the flexible deserializer | Single canonical format | High risk to backward-compat with existing records; broad regression surface | None |

---

## 5. Recommended Fix — IMPLEMENTED

**Option A.** Added two ISO-8601 offset patterns using the `XXX` token to `FlexibleDateDeserializer.FORMATS` (applied):

```java
private static final String[] FORMATS = {
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",   // ISO-8601 millis + colon offset (+00:00) or Z  <-- NEW
        "yyyy-MM-dd'T'HH:mm:ssXXX",       // ISO-8601 no-millis + colon offset or Z         <-- NEW
        "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
        "yyyy-MM-dd'T'HH:mm:ss.SSSZ",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ssZ"
};
```

Rationale: additive and contained; keeps epoch-millis and all currently-supported string forms; `XXX` covers the missing `+00:00` (and also `Z`). No public API or wire-format change.

### 5.1 Do we even need the booking change? (honest trade-off)

**Your instinct is right:** booking and visibility **are** working fine and need no fix to function, and adding `@JsonFormat` to the **pi-commons `PackageType`** alone **would** stop the PIBK crash **without touching booking at all**. These are two *independent* fixes for the same bug, at two different points:

| | **Fix S — source** (`@JsonFormat` on pi-commons `PackageType`) | **Fix R — reader** (`XXX` in booking `FlexibleDateDeserializer`) |
|---|---|---|
| Where | `partner-integrator/pi-commons` (this repo) | `booking` module → booking-model jar |
| What it does | Makes the PIBK round-trip write `…Z`/space instead of `+00:00` | Makes the reader accept `+00:00` from **any** source |
| Delivery | **Self-contained** — no booking release, no jar re-vendor | Needs a booking-model release + re-vendor (§9) |
| Blast radius | Fixes **only** this field/path; must be repeated for every bare-`Date` field that gets round-tripped (e.g. also `Geography`/`Country` via `getFromBookingClass`) | Fixes **all** consumers/fields/paths centrally, once |
| Future-proofing | If the reference-data API ever returns a `+00:00` **string** (not epoch-millis), booking-the-service would still break | Protects booking-the-service too against that same hypothetical |
| Precedent | — | Same `XXX` approach already used for the Audit `OffsetDateTimeTypeConverter` fix (visibility/booking AWS upgrade) |

**So why keep the booking change?** Not because booking is broken today — it isn't. It's because `FlexibleDateDeserializer` is the **shared reader** every consumer relies on, and hardening it once removes the entire *class* of `+00:00` failures (any field, any path, any future producer) instead of patching one annotation at a time. It also matches the pattern the team already adopted for the sibling OffsetDateTime issue.

**Practical recommendation (revised):**
- **To unblock PIBK fastest, with the smallest blast radius → Fix S** (add `@JsonFormat` to pi-commons `PackageType`). It's entirely within this repo, needs no booking release, and is safe (mirrors what pi-commons `ContainerType` already does).
- **For durability → Fix R** (the `XXX` reader change) shipped with the next booking-model release.
- **Ideal = both** (belt-and-suspenders): Fix S stops the bad string being minted; Fix R guarantees the reader can cope even if it ever is. Neither is "wrong"; if only one is chosen now, **Fix S alone is sufficient to resolve the reported PIBK crash.**

> The booking `FlexibleDateDeserializer` change (Fix R) is already implemented and tested (§6). **Fix S is now also implemented and verified** in this repo: `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")` on `pi-commons/.../referencedata/model/PackageType.lastModifiedDateUtc`, with a new regression test `EnrichmentServiceTest#testGetEnrichedAttributes_PackageTypeWithLastModifiedDate_DoesNotThrowOnRoundTrip`. Verified both ways: **without** the annotation the test fails with the exact production error (`Cannot parse date: "2018-06-13T12:00:00.000+00:00"`); **with** it, `mvn -pl pi-booking-processor -am test -Dtest=EnrichmentServiceTest` → `Tests run: 17, Failures: 0` against the **unfixed vendored booking jar** — confirming Fix S alone unblocks PIBK.

---

## 6. Implementation — DONE (source + tests)

Completed in the `booking` module (root-cause location):

1. **Fix applied** — added `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` and `yyyy-MM-dd'T'HH:mm:ssXXX` to `FlexibleDateDeserializer.FORMATS`.
2. **Tests added** to `FlexibleDateDeserializerTest`:
   - `shouldDeserializeIso8601WithColonTimezoneOffset` — `2018-06-13T12:00:00.000+00:00` → `1528891200000L` (the exact failing value).
   - `shouldDeserializeIso8601WithColonOffsetNoMillis` — `2018-06-13T12:00:00+00:00`.
   - `shouldDeserializeIso8601WithNonZeroColonOffset` — `2018-06-13T18:00:00.000+05:30` → `1528893000000L`.
   - `shouldDeserializeIso8601WithColonTimezoneOffsetForPackageType` — same colon value on `PackageType`.
3. **Verified** — `mvn -pl booking test -Dtest=FlexibleDateDeserializerTest`: `Tests run: 15, Failures: 0, Errors: 0` → **BUILD SUCCESS** (10 pre-existing + 4 new… kept all regressions green).

Pre-fix behaviour was empirically confirmed: the original 5 patterns cannot parse `2018-06-13T12:00:00.000+00:00` (colon offset), while the two new `XXX` patterns parse it and also still accept `+0000`, `Z`, space, and no-millis forms.

**Files changed**
- `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java`
- `booking/src/test/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializerTest.java`

---

## 7. Testing Strategy

- **New unit tests** (`FlexibleDateDeserializerTest`):
  - `shouldDeserializeIso8601WithColonOffset` — `"2018-06-13T12:00:00.000+00:00"` → `getTime() == 1528891200000L`.
  - No-millis colon offset — `"2018-06-13T12:00:00+00:00"`.
  - Non-zero colon offset — e.g. `"2018-06-13T12:00:00.000+05:30"` → correct UTC instant.
  - Same coverage mirrored for `PackageType`.
- **Regression:** keep the existing cases (`+0000`, `Z`, space format, no-millis `Z`, epoch millis, null, invalid) green.
- **Boundary/edge:** negative offset (`-05:00`), and confirm the invalid-format case still throws `JsonMappingException`.
- Verify with `mvn test -pl booking` then `mvn verify -pl booking` and a partner-integrator `pi-booking-processor` build after re-vendoring the jar.

---

## 8. References

| Type | Key / Path | Note |
|---|---|---|
| Root-cause class | `booking/.../referencedata/model/FlexibleDateDeserializer.java` | Missing colon-offset pattern |
| Affected models | `booking/.../referencedata/model/{ContainerType,PackageType}.java` | `@JsonDeserialize(using=FlexibleDateDeserializer)` |
| Consumer | `pi-booking-processor/.../transform/EnrichmentService.java` | `getFromBookingClass` JSON round-trip |
| Failure wrap | `pi-booking-processor/.../handler/impl/BookingFeedHandler.java` | Rewraps to `EDataSupplementationException` |
| Existing test | `booking/.../FlexibleDateDeserializerTest.java` | Covers `+0000`, not `+00:00` |
| Upstream change | `ION-14382` (booking bk3 AWS SDK v2 upgrade) | Introduced the deserializer |
| PI upgrade session | `ION-16417` / session `59a4c1b2109b487d` | Context |

---

## 9. Remaining Delivery Step (cross-team — booking model release)

The fix is in `booking` source, but PIBK consumes the compiled **`booking-model`** jar, published to the S3 repo and vendored into partner-integrator. The source fix does **not** reach PIBK until the model jar is re-released:

1. **Release booking-model** — build the `booking-model` Maven profile (`booking/pom.xml`, profile id `booking-model`) which packages `com/inttra/mercury/booking/**/model/**` (incl. `networkservices/referencedata/model/**`) and deploys `booking-model-<ver>.jar` to `s3://inttra-deployment/Booking/repo/release`. Cut a new version (e.g. `3.0.1.M`) — do **not** overwrite the released `3.0.0.M` artifact.
2. **Bump + re-vendor** in partner-integrator:
   - `pi-booking-processor/pom.xml` — dependency `com.inttra.mercury:booking` and the two shade `manualInclude`/`artifact` entries → new version.
   - Place the new jar under `pi-booking-processor/lib/com/inttra/mercury/booking/<ver>/` (local `file:${basedir}/lib` repo).
   - Repeat for `pi-statusevents-out-processor` (vendors the same model jar).
3. **Verify** — `mvn verify -pl pi-booking-processor -am` and re-run the failing QA scenario (a booking whose reference-data record has a colon-offset `lastModifiedDateUtc`).

> This step requires the booking release pipeline / S3 publish credentials and a version bump, so it is owned by the booking module maintainers and was intentionally not executed here.

---

## 10. Live QA Evidence (CloudWatch + ECS)

**Cluster / service:** `arn:aws:ecs:us-east-1:642960533737:service/ANEQAAPWY-001/PIBK-qa` — ACTIVE, desired/running 2/2, task def `PIBK-latest-qa-Task:6`, image `…/centos:PIBK-qa`, PRIMARY deployment `2026-09-04` (rollout COMPLETED). AWS account `642960533737` (INTTRA2-QATeam), region `us-east-1`.

**Log group:** `inttra2-qa-lg-pi`, stream `PIBK-latest-qa-Task/PIBK-qa-Container/…`. Reconstructed sequence around the failure (`pool-5-thread-1`, `2026-09-02 00:40:55 → 00:41:04`):

```
00:40:55  c.i.m.bkfeed.service.BookingService : Booking transformation Started...
00:41:00  JerseyClientRequestLoggingFilter : request:[URI: https://api-beta.inttra.com/network/containertype?typeCode=42R1]
00:41:01  JerseyClientRequestLoggingFilter : request:[URI: https://api-beta.inttra.com/network/packagetype?edifactCode=PK]
00:41:01  at com.inttra.mercury.bkfeed.transform.EnrichmentService.getFromBookingClass(EnrichmentService.java:235)
00:41:01  ...EDataSupplementationException: JsonMappingException: ... Cannot parse date: "2018-06-13T12:00:00.000+00:00".
          Supported formats: epoch millis, yyyy-MM-dd HH:mm:ss, yyyy-MM-dd'T'HH:mm:ss.SSS'Z'
00:41:03  c.i.m.c.listener.mq.AbstractMQListener : Error in AbstractMQListener - <same exception>
```

Confirmations from the live logs:
- The crash is at `EnrichmentService.getFromBookingClass:235` (the `JsonSupport.toJson → fromJson` round-trip), **not** at the network read — proving the `+00:00` string is minted by the re-serialization, not returned raw by the API.
- The two reference-data calls immediately preceding are `containertype?typeCode=42R1` and `packagetype?edifactCode=PK`; the epoch instant `1528891200000` = `2018-06-13T12:00:00Z` matches the failing value exactly.
- The message repeats continuously (the MQ listener retries the poisoned message), so PIBK is stuck reprocessing it.

## 11. Why booking / visibility / watermill-publisher do NOT break

The bug is specific to **PIBK's pi-commons → booking JSON round-trip through `JsonSupport`** (default `StdDateFormat`). The other consumers never produce a `+00:00` string for these reference-data fields:

| Consumer | How it handles the same reference-data date | Breaks? |
|---|---|---|
| **PIBK** (`pi-booking-processor`) | `EnrichmentService.getFromBookingClass` re-serializes a **no-`@JsonFormat`** pi-commons `PackageType` via default `StdDateFormat` → `+00:00`, then reads it with `FlexibleDateDeserializer` | **Yes** |
| **booking** service (write path) | Serializes its own `ContainerType`/`PackageType` to DynamoDB using `@JsonFormat(pattern="…SSS'Z'")` → emits `Z`; reads back via `FlexibleDateDeserializer` (handles `Z`/space/epoch). Never a colon offset. | No |
| **visibility** | Reads booking's already-normalized DynamoDB records (`Z`/space). Its own `OffsetDateTime` audit fields were fixed in the AWS upgrade to use the `XXX` pattern (`OffsetDateTimeTypeConverter`), which *does* accept `+00:00`. | No |
| **watermill-publisher** (cargo-visibility-subscription) | Consumes already-normalized/serialized messages; no pi-commons→booking `StdDateFormat` round-trip of a bare `Date`. | No |

In short: only PIBK round-trips a bare `java.util.Date` (no format annotation) through Jackson's default ISO serializer, which under Jackson 2.21.4 emits the colon-offset form that `FlexibleDateDeserializer` cannot read.

## 12. Why this wasn't factored in earlier (prior-doc history)

It **was** raised — and deliberately deprioritised. During the ION-14382 booking AWS-upgrade integration-issue review:

- `booking/docs/claude-review-integration-issue-fix.md` §3b ("ORIGINAL CONCERN (`+00:00` offset) — Downgraded to Informational / Not a Real Risk") explicitly noted `FlexibleDateDeserializer` handles RFC-822 `+0000` but not ISO-8601 `+00:00`, then concluded: *"The `+00:00` (ISO 8601 colon offset) format does NOT appear in any test or production data for these fields … a theoretical robustness issue … not blocking."* The active defect fixed then was the **epoch-millis** case (`shouldDeserializeEpochMillis`).
- `booking/docs/booking-integration-issues-04222027-copilot.md` documented that the network `packagetype` API returns `lastModifiedDateUtc` as epoch-millis `"1528891200000"`, and even flagged that `PackageType.lastModifiedDateUtc` has **no `@JsonFormat`** and that Jackson's `StdDateFormat` would then emit `"…+0000"` — but assumed the RFC-822 (`+0000`) shape, which the deserializer already tolerated.

Two things invalidated that "not a real risk" assessment:
1. The review assumed `StdDateFormat` emits `+0000` (RFC-822) — but Jackson has emitted the **colon** form `+00:00` by default since 2.9, so the string reaching `FlexibleDateDeserializer` was already the unhandled shape. Crucially, the review also didn't weigh that the model's date **reader** had been swapped from Jackson's tolerant default `StdDateFormat` (which parses `+00:00`) to the custom `FlexibleDateDeserializer` (which doesn't) — that reader swap is what actually exposed the gap (see §2 "Why it worked before and breaks now").
2. The colon-offset value does occur in practice for real 2018-era reference-data records (`1528891200000`), contradicting the "does not appear in production data" premise.

Related prior fixes that used the correct `XXX` approach (and are the precedent for this fix): visibility/booking `OffsetDateTimeTypeConverter` — see `visibility/docs/visibility-aws2x-plan.md` §"Issue 3: OffsetDateTime Parse Errors" ("Changed pattern to `yyyy-MM-dd'T'HH:mm:ss.SSSXXX`") and `visibility/docs/CONFLUENCE-visibility.md` ("Pattern must use `XXX` (not `Z`) to handle `+00:00` zone offsets"). The reference-data `FlexibleDateDeserializer` simply never received the same `XXX` treatment.

### Complementary hardening (IMPLEMENTED — Fix S)
Added `@JsonFormat(pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"...` — implemented as `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")` on **pi-commons** `PackageType.lastModifiedDateUtc` (to match pi-commons `ContainerType`). This makes the PIBK round-trip emit a canonical, deserializer-friendly format and removes reliance on Jackson's default `StdDateFormat`. Because it is entirely within `pi-commons`, it needs **no booking-model release** and unblocks PIBK on its own (verified — see §5.1). The `FlexibleDateDeserializer` `XXX` fix (§5/§6) remains the defence-in-depth reader fix.

---

## 13. Additional References (this investigation)

| Type | Key / Path | Note |
|---|---|---|
| Failing line | `pi-booking-processor/.../transform/EnrichmentService.java:235` | `JsonSupport.toJson → fromJson` round-trip (confirmed in QA stack) |
| No-format model | `pi-commons/.../referencedata/model/PackageType.java` | `Date lastModifiedDateUtc` with **no** `@JsonFormat` → default `StdDateFormat` |
| Formatted model | `pi-commons/.../referencedata/model/ContainerType.java` | Has `@JsonFormat("yyyy-MM-dd HH:mm:ss")` → does not fail |
| Prior triage | `booking/docs/claude-review-integration-issue-fix.md` §3b | `+00:00` gap downgraded to "not a real risk" |
| Prior analysis | `booking/docs/booking-integration-issues-04222027-copilot.md` | Network API returns epoch-millis; PackageType no-`@JsonFormat` noted |
| `XXX` precedent | `visibility/docs/visibility-aws2x-plan.md` §"Issue 3"; `visibility/docs/CONFLUENCE-visibility.md` | OffsetDateTime fixed with `XXX` (not `Z`) for `+00:00` |
| QA log group | `inttra2-qa-lg-pi` (acct `642960533737`, `us-east-1`) | Stream `PIBK-latest-qa-Task/PIBK-qa-Container/…` |
| ECS service | `arn:aws:ecs:us-east-1:642960533737:service/ANEQAAPWY-001/PIBK-qa` | task def `PIBK-latest-qa-Task:6`, image `…/centos:PIBK-qa` |
| Jackson version | `booking/pom.xml` `jackson.version=2.21.4` | `StdDateFormat` default → colon offset (`XXX`) |

---

## 14. Where the 2018 data comes from and how it loads into PIBK

**Short answer:** the `2018-06-13T12:00:00.000+00:00` value is **not** customer/booking transaction data. It is the `lastModifiedDateUtc` of a **network reference-data (master-data) record** — the definition of package type `PK` — which has not been edited since 2018. It is pulled into PIBK on demand while enriching any booking that uses that package type.

### Traced end-to-end from the QA logs (`pool-5-thread-1`, `2026-09-02 00:40:55–00:41:04`)

1. **A booking message arrives on the MQ** and is dispatched to `BookingFeedHandler` via `AbstractMQListener`. The logged `bkHarmPayload` (a `ValidateAdditionalSync` XML, ~7 KB) contains the codes that drive enrichment:
   ```xml
   <PackageType Code="PK">Package</PackageType>
   ...
   <SizeType><Code Type="ISO">42R1</Code><Description>Therm…</Description></SizeType>
   ```
   So the transaction references **package type `PK`** and **equipment ISO size `42R1`** (a thermal/reefer container).

2. **`EnrichmentService` turns those codes into reference-data lookups** against the network reference-data microservice (`api-beta.inttra.com`):
   ```
   GET https://api-beta.inttra.com/network/containertype?typeCode=42R1   → 200
   GET https://api-beta.inttra.com/network/packagetype?edifactCode=PK    → 200
   ```
   - `collectPackageTypes()` → `ReferenceDataService.getPackageType(EDI/X12/Xml, "PK")`
   - `collectContainerTypes()` → `ReferenceDataService.getContainerGroupType("42R1")`

3. **The reference-data records carry a `lastModifiedDateUtc`** describing when that master-data row was last edited. The network API returns it as **epoch milliseconds** — `1528891200000`, which is exactly `2018-06-13T12:00:00Z`. (The `PK` package-type definition simply hasn't been changed since June 2018.)

4. **PIBK re-serializes the record into the booking model** in `EnrichmentService.getFromBookingClass()` (`JsonSupport.toJson → fromJson`). The pi-commons `PackageType` has **no `@JsonFormat`**, so Jackson's default `StdDateFormat` renders the epoch instant as `2018-06-13T12:00:00.000+00:00` (colon offset). That string then fails `FlexibleDateDeserializer` on read (see §2).

### So "how it gets loaded" in one line
`MQ booking message (PackageType Code="PK") → EnrichmentService → GET /network/packagetype?edifactCode=PK → reference-data record with lastModifiedDateUtc = 1528891200000 (2018-06-13Z) → getFromBookingClass round-trip mints "…+00:00" → FlexibleDateDeserializer throws.`

### Which record actually breaks — `PK` vs `42R1`
Both are fetched, but only the **package type `PK`** path fails: its pi-commons model has no `@JsonFormat`, so the round-trip emits the colon offset. The container type `42R1` is enriched through the same mechanism but its pi-commons copy carries `@JsonFormat("yyyy-MM-dd HH:mm:ss")`, so it round-trips as the space format and parses cleanly — even if its own `lastModifiedDateUtc` is also a 2018 value.

### Evidence limitation
The Jersey client response logging records only the HTTP status (`response:[Status:200]`), **not** the response body, so the raw `lastModifiedDateUtc` field is not directly visible in CloudWatch. The origin above is established by: (a) the exact epoch↔date equivalence `1528891200000 == 2018-06-13T12:00:00Z`, (b) the two reference-data GETs immediately preceding the crash, (c) the crash stack at `getFromBookingClass:235`, and (d) the deterministic no-`@JsonFormat` serialization of pi-commons `PackageType`. To capture the literal API payload, hit `GET https://api-beta.inttra.com/network/packagetype?edifactCode=PK` with a valid network auth token (the same token PIBK obtains from `https://api-beta.inttra.com/auth`).

---

## 15. Would the same query trip booking or visibility? Why does enrichment call this data? Is it peculiar to PIBK?

### 15.1 Does the same reference-data call break booking or visibility? — No.
booking and visibility hit the **same** network reference-data endpoints, but each deserializes the response **directly, in one hop, into its own model** — there is no second serialization that could mint a `+00:00` string.

| Consumer | Reference-data client & target model | Date handling of the raw API value | Round-trip? | Breaks? |
|---|---|---|---|---|
| **booking** | `booking/.../ReferenceDataServiceImpl` → `client.get(..., GenericType<List<PackageType/ContainerType>>)` into **booking's own** models | booking `PackageType`/`ContainerType` use `FlexibleDateDeserializer`, whose `dateStr.matches("\\d+")` branch consumes the epoch-millis (`1528891200000`) **directly from the API** | No (1 hop) | No |
| **visibility** | `visibility/.../ContainerTypeServiceImpl` → `client.get(..., GenericType<List<ContainerType>>)` into **visibility's own** model. **No package-type service exists** (grep for `packagetype` in `visibility/` = 0 hits) | visibility `ContainerType.lastModifiedDateUtc` `@JsonFormat("yyyy-MM-dd HH:mm:ss")`; the numeric epoch is read as a timestamp. Never re-serialized to another model. | No (1 hop) | No |
| **PIBK** | `pi-commons/.../ReferenceDataServiceImpl` → **pi-commons** models, then `EnrichmentService.getFromBookingClass` **re-serializes** into the **booking** model via `JsonSupport.toJson → fromJson` | pi-commons `PackageType` has **no `@JsonFormat`** → the bridge step renders the `Date` with Jackson default `StdDateFormat` → `…+00:00`, then the booking `FlexibleDateDeserializer` rejects it | **Yes (2 hops)** | **Yes** |

The decisive difference is not the endpoint or the data — it is the **extra pi-commons → booking JSON conversion hop** that only PIBK performs. booking never converts (it *is* the booking model); visibility never converts (it uses its own model) and never even queries package types.

### 15.2 Why is the `bkHarmPayload` / `ValidateAdditionalSync` calling this reference data?
The harmonized booking payload carries only **raw codes**, e.g. `<PackageType Code="PK">` and `<SizeType><Code Type="ISO">42R1</Code>`. To produce the partner-integrator **outbound** booking message, `EnrichmentService.getEnrichedAttributes()` must resolve those codes into full master-data — container-type category/dimensions/TEU and package-type descriptions — via `getContainerGroupType()` / `getPackageType()`. This enrichment is intrinsic to building `EnrichedAttributes` on the `BookingDetail`, so the package/container reference-data endpoints are called for essentially every booking that carries those codes.

### 15.3 Is this peculiar to PIBK? — Yes.
The **failure** is peculiar to PIBK. The reference-data endpoints are shared infrastructure, but only PIBK bridges two model families (pi-commons for the network client, the booking-model jar for the output) via a JSON round-trip. That bridge — re-serializing a bare `java.util.Date` (no `@JsonFormat`) through Jackson's default ISO `StdDateFormat` — is the sole source of the `+00:00` string. booking and visibility operate in a single native model end-to-end and are therefore immune. This also means the two fixes are complementary: the `FlexibleDateDeserializer` `XXX` patterns (§5) make the *reader* tolerant, while adding `@JsonFormat` to pi-commons `PackageType` (§12 "complementary hardening") removes the `+00:00` at the *source* of the bridge.

---

## 16. Additional Clarification (plain-English walkthrough)

If the earlier sections felt jargon-heavy, here is the whole thing in everyday terms.

### The one idea to hold onto
The broken text `2018-06-13T12:00:00.000+00:00` is **not stored anywhere**. No database, no API sends it in that shape. **PIBK creates it itself, on the fly, in memory**, and then immediately fails to read back what it just wrote. That "write-then-read-my-own-writing" step is the thing no other module does.

### An analogy
Think of a date as a single **moment in time** — "noon UTC on 13 June 2018." Different systems **write that moment down in different handwriting**:
- as a plain **number** (a count of milliseconds): `1528891200000`
- as **`2018-06-13 12:00:00`** (a space in the middle)
- as **`2018-06-13T12:00:00.000Z`** (a "Z" on the end)
- as **`2018-06-13T12:00:00.000+0000`** (offset with **no colon**)
- as **`2018-06-13T12:00:00.000+00:00`** (offset **with a colon**) ← the one that breaks

The network reference-data service hands the moment over as the **plain number** (`1528891200000`). A number is unambiguous — there's no "handwriting" to misread.

PIBK has a **reader** (`FlexibleDateDeserializer`) that recognises most of these handwriting styles — number, space, `Z`, and even `+0000` (no colon) — **but not the one with the colon** (`+00:00`). That's the whole bug in one sentence.

### Why booking and visibility never hit it (one hop)
booking and visibility do the simple thing:

> Take the **number** from the API → drop it **straight into their own object** → done.

One step. The reader is handed the original **number**, which it understands perfectly. Nobody ever rewrites the moment as `+00:00` handwriting, so nobody ever has to read it back. No breakage.

(Extra detail: visibility doesn't even ask for package types at all — it only looks up container types. booking does ask for both, but it reads the API's number directly.)

### Why PIBK trips over it (two hops)
PIBK is built differently. It uses **two different sets of objects**:
1. a **pi-commons** object to *receive* the data from the network, and
2. a **booking-model** object to actually *build the outbound partner message*.

To move the moment from object #1 to object #2, PIBK **writes it onto a slip of paper (JSON) and reads it back into the other object**. That is the extra hop:

> API's number → pi-commons object → **write to JSON text** → **read JSON text** → booking object.

Here's the catch. When PIBK writes the pi-commons **PackageType** onto that JSON slip, that object has **no instruction for how to write the date** (no `@JsonFormat` annotation). So the pen (Jackson) uses its **factory-default handwriting**, which today is exactly the colon style: **`2018-06-13T12:00:00.000+00:00`**. Then, on the very next line, PIBK's booking-side **reader** tries to read that slip — and it doesn't recognise the colon style. It throws, and the whole booking message is aborted.

So PIBK breaks not because it *received* bad data, but because it **rewrote good data (a number) into a style its own reader can't parse.**

### Why "PK" breaks but "42R1" doesn't
Both the package type (`PK`) and the container type (`42R1`) go through that same two-hop bridge. The difference:
- The pi-commons **ContainerType** (`42R1`) **does** carry a "how to write the date" instruction (`@JsonFormat = "yyyy-MM-dd HH:mm:ss"`), so it writes the friendly **space** style, which the reader accepts.
- The pi-commons **PackageType** (`PK`) has **no such instruction**, so it falls back to the default colon style — and breaks.

That's why the log fails specifically on the package-type value.

### Why it started happening only now
Before the AWS upgrade, PIBK used an **older booking model (`2.1.7.M`)** whose `PackageType` date was a plain `Date` with **no custom reader** — so Jackson's **default** date reader handled it, and that default reader **understands the colon style** (`+00:00`) perfectly. The upgrade pulled in the **new booking model (`3.0.0.M`)**, which put a **custom reader** (`FlexibleDateDeserializer`) on that field — and that custom reader only knows a fixed list of styles that **left out** the colon style. So the exact same value that the old default reader accepted now trips the new custom reader. (The JSON library also writes the colon style by default — but it already did so before the upgrade, so that isn't what changed; the reader is.)

### The two fixes, in the same plain terms
1. **Teach the reader the colon style** (the implemented fix): add the `XXX` patterns so `FlexibleDateDeserializer` also accepts `+00:00`. Now the reader understands every style. *(Primary fix.)*
2. **Stop writing the colon style in the first place** (recommended hardening): give the pi-commons `PackageType` the same "how to write the date" instruction that `ContainerType` already has, so the bridge writes a friendly style. *(Defence in depth.)*

### One-line summary
booking/visibility read the API's number **once, directly**; PIBK **re-writes that number into text and reads it back**, and only that re-write (of a format-less `PackageType`, under the upgraded Jackson) produces the colon-offset string its reader can't parse — which is why the crash is unique to PIBK.

---

## 17. Illustrated flows + "didn't we fix booking's deserializer?"

### 17.1 "But the deserializer we patched lives in the *booking* module — isn't booking affected too?"
Yes, `FlexibleDateDeserializer` **is** a booking-module class, and it is **shared**: PIBK uses it *through the booking-model jar*. The subtlety is **what each caller feeds it**:

- `FlexibleDateDeserializer` looks at the incoming text and **first checks "is this all digits?"** (`dateStr.matches("\\d+")`). If yes → it treats it as epoch-millis and is done — it **never looks at the format list** (where the `+00:00` gap lived).
- **booking-the-service** and **watermill** only ever hand it a **number** (`1528891200000`) or an already-safe `…Z`/space string → they hit that first short-circuit → they **never touched the missing pattern**, so they never failed, *even before our fix*.
- **PIBK** is the only caller that hands it a **`+00:00` string** (because of the extra re-serialization hop). A string with letters/`+`/`:` is **not** all-digits → it falls through to the format list → no colon pattern → **throws**.
- **visibility** doesn't use this class at all — its model uses `@JsonFormat` only.

So there is no contradiction: **the buggy class is booking's, but the only code path that ever exercises the bug is PIBK's.** Patching booking's class is precisely what fixes PIBK — the fix reaches PIBK when the rebuilt booking-model jar is re-vendored (§9).

### 17.2 Flow diagrams (who re-serializes, and who doesn't)

**booking service** — one hop, fed a number → safe (uses `FlexibleDateDeserializer`):
```
network reference-data API
   │  returns epoch-millis  "1528891200000"   (a NUMBER)
   ▼
booking ReferenceDataServiceImpl.getPackageType()/getContainerGroupType()
   │  deserialize DIRECTLY into booking's own PackageType/ContainerType
   ▼
FlexibleDateDeserializer:  matches("\d+")? → YES → new Date(1528891200000)
   ▼
   ✅ done — never reaches the format list, so the +00:00 gap is irrelevant
```

**visibility** — one hop, own model, does NOT use FlexibleDateDeserializer:
```
network reference-data API  (containertype ONLY — visibility has NO packagetype call)
   │  epoch-millis number
   ▼
visibility ContainerTypeServiceImpl.getContainerGroupType()
   │  deserialize DIRECTLY into visibility's own ContainerType
   ▼
visibility ContainerType.lastModifiedDateUtc  →  @JsonFormat only (no custom deserializer)
   ▼
   ✅ numeric token read as a timestamp; never re-serialized to another model
```

**watermill-publisher** — downstream; never calls reference-data at all:
```
booking service ──(already-enriched BookingDetail; dates already written as "…Z"/space)──▶ SQS
   ▼
watermill WatermillBKTask → BKProtobufTransformer / CargoTransformer
   │  reads the booking-model BookingDetail; any reference date is already a SAFE "…Z" string
   │  (watermill's own "PackageType" is the booking ENUM = packaging nesting level, NOT the
   │   reference-data record with lastModifiedDateUtc)
   ▼
transform to protobuf  →  BookingGrpcClient publishes via gRPC
   ▼
   ✅ no reference-data call, no bare-Date re-serialization → +00:00 can never be produced
```

**PIBK** — two hops; the re-write mints the colon string:
```
network reference-data API
   │  epoch-millis number "1528891200000"
   ▼
pi-commons ReferenceDataServiceImpl → pi-commons PackageType (Date, NO @JsonFormat)   [hop 1: number → Date]
   ▼
EnrichmentService.getFromBookingClass():
   │  JsonSupport.toJson(piCommonsPackageType)                                          [hop 2: Date → TEXT]
   │     no @JsonFormat → Jackson StdDateFormat writes  "2018-06-13T12:00:00.000+00:00"  ← colon minted here
   │  JsonSupport.fromJson(text, booking PackageType) → FlexibleDateDeserializer
   │     input is now a STRING (not all-digits) → falls to format list → no +00:00 pattern
   ▼
   ❌ throws IOException → wrapped as EDataSupplementationException → whole message fails
```

### 17.3 Side-by-side

| Module | Calls reference-data? | Model hops | What the deserializer receives | Uses booking `FlexibleDateDeserializer`? | Breaks? |
|---|---|---|---|---|---|
| **booking** | Yes (pkg + container) | 1 (direct) | the API **number** → short-circuit | Yes | No |
| **visibility** | Yes (container only) | 1 (direct) | numeric via `@JsonFormat` | No (own model) | No |
| **watermill** | **No** | 0 (consumes finished booking) | already-safe `…Z` string (if any) | Yes, but only on safe values | No |
| **PIBK** | Yes (pkg + container) | **2 (pi-commons → booking)** | a **`+00:00` string** it just minted | Yes | **Yes** |

The pattern is consistent: **breakage requires (a) re-serializing a bare `Date` to text and (b) reading that text back with `FlexibleDateDeserializer`.** Only PIBK does both. The booking-module fix is still the right place to fix it, because that shared class is the reader PIBK relies on.

---

## 18. Booking module changes (Fix R) — diffs, class names, and stash

Fix R hardens the **shared reader** in the `booking` module so it accepts ISO-8601 colon offsets (`+00:00`) from any source. It is **not required to unblock PIBK** (Fix S in pi-commons does that on its own — §5.1), and it ships on a **different release train** (the `booking-model` jar, §9). To keep it off the partner-integrator working tree while it awaits that release, **the booking changes have been stashed** (details below). This section preserves the exact changes so nothing is lost.

### 18.1 Classes / files changed

| # | Class (FQN) | File | Change |
|---|---|---|---|
| 1 | `com.inttra.mercury.booking.networkservices.referencedata.model.FlexibleDateDeserializer` | `booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java` | Add two `SimpleDateFormat` patterns using the `XXX` offset token (accepts `+00:00` **and** `Z`) |
| 2 | `com.inttra.mercury.booking.networkservices.referencedata.model.FlexibleDateDeserializerTest` | `booking/src/test/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializerTest.java` | Add 4 colon-offset regression tests (`ContainerType` + `PackageType`) |

Verification: `mvn -pl booking test -Dtest=FlexibleDateDeserializerTest` → `Tests run: 15, Failures: 0, Errors: 0` → BUILD SUCCESS.

### 18.2 Diff — `FlexibleDateDeserializer` (production change)

```diff
diff --git a/booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java b/booking/src/main/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializer.java
--- a/booking/.../referencedata/model/FlexibleDateDeserializer.java
+++ b/booking/.../referencedata/model/FlexibleDateDeserializer.java
@@ -19,6 +19,8 @@ public class FlexibleDateDeserializer extends JsonDeserializer<Date> {
 
     private static final String[] FORMATS = {
             "yyyy-MM-dd HH:mm:ss",
+            "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
+            "yyyy-MM-dd'T'HH:mm:ssXXX",
             "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
             "yyyy-MM-dd'T'HH:mm:ss.SSSZ",
             "yyyy-MM-dd'T'HH:mm:ss'Z'",
             "yyyy-MM-dd'T'HH:mm:ssZ"
     };
```

### 18.3 Diff — `FlexibleDateDeserializerTest` (new tests)

```diff
diff --git a/booking/src/test/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializerTest.java b/booking/src/test/java/com/inttra/mercury/booking/networkservices/referencedata/model/FlexibleDateDeserializerTest.java
--- a/booking/.../referencedata/model/FlexibleDateDeserializerTest.java
+++ b/booking/.../referencedata/model/FlexibleDateDeserializerTest.java
@@ -44,6 +44,41 @@ class FlexibleDateDeserializerTest {
         assertThat(ct.getLastModifiedDateUtc()).isNotNull();
     }
 
+    @Test
+    void shouldDeserializeIso8601WithColonTimezoneOffset() throws Exception {
+        // Reference-data API returns some (older) records with a COLON in the offset (+00:00).
+        // 2018-06-13T12:00:00.000+00:00 == epoch millis 1528891200000
+        String json = "{\"lastModifiedDateUtc\":\"2018-06-13T12:00:00.000+00:00\"}";
+        ContainerType ct = mapper.readValue(json, ContainerType.class);
+        assertThat(ct.getLastModifiedDateUtc()).isNotNull();
+        assertThat(ct.getLastModifiedDateUtc().getTime()).isEqualTo(1528891200000L);
+    }
+
+    @Test
+    void shouldDeserializeIso8601WithColonOffsetNoMillis() throws Exception {
+        String json = "{\"lastModifiedDateUtc\":\"2018-06-13T12:00:00+00:00\"}";
+        ContainerType ct = mapper.readValue(json, ContainerType.class);
+        assertThat(ct.getLastModifiedDateUtc()).isNotNull();
+        assertThat(ct.getLastModifiedDateUtc().getTime()).isEqualTo(1528891200000L);
+    }
+
+    @Test
+    void shouldDeserializeIso8601WithNonZeroColonOffset() throws Exception {
+        // +05:30 offset -> 18:00 local == 12:30 UTC
+        String json = "{\"lastModifiedDateUtc\":\"2018-06-13T18:00:00.000+05:30\"}";
+        ContainerType ct = mapper.readValue(json, ContainerType.class);
+        assertThat(ct.getLastModifiedDateUtc()).isNotNull();
+        assertThat(ct.getLastModifiedDateUtc().getTime()).isEqualTo(1528893000000L);
+    }
+
+    @Test
+    void shouldDeserializeIso8601WithColonTimezoneOffsetForPackageType() throws Exception {
+        String json = "{\"lastModifiedDateUtc\":\"2018-06-13T12:00:00.000+00:00\"}";
+        PackageType pt = mapper.readValue(json, PackageType.class);
+        assertThat(pt.getLastModifiedDateUtc()).isNotNull();
+        assertThat(pt.getLastModifiedDateUtc().getTime()).isEqualTo(1528891200000L);
+    }
+
     @ParameterizedTest
     @ValueSource(strings = {
             "{\"lastModifiedDateUtc\":\"2020-12-08 18:07:00\"}",
```

### 18.4 Stash details

The two booking files above were stashed (they are **not** in the partner-integrator working tree; Fix S in `pi-commons` and this doc remain).

| Field | Value |
|---|---|
| Stash ref | `stash@{0}` |
| Message | `ION-16417-pibk-fixR-booking-FlexibleDateDeserializer-XXX-colon-offset` |
| Stash commit SHA | `06dcc5727df7b3c55243584da48a2d2bbcf5487e` |
| Base commit | `cbc6eccbf192647478b97b48e5ceb8de64287981` |
| Branch when stashed | `develop` |
| Files (2, +37) | `FlexibleDateDeserializer.java` (+2), `FlexibleDateDeserializerTest.java` (+35) |

> ⚠️ `stash@{N}` numbering shifts as stashes are added/removed. Prefer the **stash commit SHA** (`06dcc572…`) or the message to identify it unambiguously.

**Inspect / restore commands**
```bash
# list stashes and confirm the message
git stash list

# view the stashed diff (by SHA — stable) or by ref
git stash show -p 06dcc5727df7b3c55243584da48a2d2bbcf5487e
git stash show -p stash@{0}

# apply (keep the stash) — do this in the BOOKING repo/release branch, not here
git stash apply 06dcc5727df7b3c55243584da48a2d2bbcf5487e

# or apply and drop it once the booking-model release picks up the change
git stash pop stash@{0}
```

**Intended delivery:** apply this stash on the `booking` module release branch, cut a new `booking-model` version, and re-vendor into partner-integrator per §9. It is intentionally kept out of the pi-commons/PIBK change set so the two fixes travel on their correct release trains.


---

## 19. Blast-radius sweep — other partner-integrator modules & watermill-publisher

Question: could the same `+00:00` round-trip bug exist elsewhere? The bug needs BOTH (a) a bare `java.util.Date` (no `@JsonFormat`) **re-serialized** to text via a default mapper, and (b) that text read back by a **strict** reader that rejects `+00:00` (the booking `FlexibleDateDeserializer`). A grep-driven sweep:

### 19.1 pi-booking-processor (PIBK) — the only exposed module
`EnrichmentService.getFromBookingClass` (the risky double-hop) is called for exactly four types:

| Round-tripped type | Has a `Date` field? | Guarded how? | Risk |
|---|---|---|---|
| `PackageType` | Yes (`lastModifiedDateUtc`) | pi-commons had **no** `@JsonFormat` → **was the bug** → **Fix S applied** | resolved |
| `ContainerType` | Yes (`lastModifiedDateUtc`) | pi-commons `@JsonFormat("yyyy-MM-dd HH:mm:ss")` → round-trips as space | safe |
| `Geography` | **No `Date` field** | nothing to serialize | safe |
| `Country` | **No `Date` field** | nothing to serialize | safe |

Party/participant resolution (`PartyLocator`) maps fields **via `TransactionParty.builder()`** (name/scac/address), and **does not carry or re-serialize** the participant's `Date` fields. So the other pi-commons bare-`Date` models (`Address`, `Token`, `NetworkContact`, `SubModuleEntitlement`, `Alias`) are never fed through the strict reader → not exposed.

### 19.2 Other partner-integrator processors (pi-si-*, pi-bl-*, pi-statusevents-out-*)
These read `SIContract` / `BLContract` / `BookingDetail` from stored JSON (SQS/DynamoDB) in a **single hop** — like booking/visibility, they consume already-serialized data. `pi-statusevents-out-processor` deserializes a `BookingDetail` whose `enrichedAttributes.{containerTypeList,packageTypeList}.lastModifiedDateUtc` were **persisted by the producer as `…Z`/space** (booking writes with `@JsonFormat("…SSS''Z''")`). The `+00:00` form is **never persisted** (PIBK throws *before* persisting), so these one-hop readers never see it → not exposed.

### 19.3 watermill-publisher — not exposed
- **Does not call reference-data** at all (no `getContainerGroupType`/`getPackageType`; grep = 0 hits).
- Consumes an already-enriched, already-serialized booking-model `BookingDetail` via **gRPC/SQS** (`BookingGrpcClient`), then maps to protobuf. Its `PackageType` symbol is the booking **enum** (packaging nesting), not the reference-data record.
- **Does not use `FlexibleDateDeserializer`** anywhere → even if it round-tripped a bare `Date`, there is no strict `+00:00`-rejecting reader to trip.

### 19.4 Conclusion
The **PIBK PackageType enrichment was the only exposed path**, and it is fixed (Fix S). Nothing else in partner-integrator or watermill-publisher performs the bare-`Date` → `FlexibleDateDeserializer` round-trip. The residual, theoretical exposure is: (i) a *future* new `getFromBookingClass`-style round-trip of a bare-`Date` model, or (ii) the reference-data API beginning to emit `+00:00` **strings** (not epoch-millis) that booking/SI/BL read directly. Both are covered by **Fix R** (the `FlexibleDateDeserializer` `XXX` hardening) — which is exactly why it is retained as defence-in-depth even though it is not required to resolve the current PIBK crash.

---

## 20. ContainerType symmetry proof + commit

To prove `ContainerType` is safe **only because of its `@JsonFormat`** (and not for some other reason), a companion regression test was added and the annotation was toggled:

- `EnrichmentServiceTest#testGetEnrichedAttributes_ContainerTypeWithLastModifiedDate_DoesNotThrowOnRoundTrip` — same 2018 value (`1528891200000`) via `getContainerGroupType("42R1")`.
- **With** pi-commons `ContainerType.@JsonFormat` → `EnrichmentServiceTest` **18/18 pass**.
- **Without** it (annotation temporarily removed) → the ContainerType test **fails with the identical** `Cannot parse date: "2018-06-13T12:00:00.000+00:00"` — confirming perfect symmetry with `PackageType`. Annotation restored; 18/18 green again.

**Commit (Fix S):**
- Branch: `bugfix/ION-16819-pibk-dateformat-fix`
- Commit: `7390ae6877` — `ION-16819 fix PIBK date parse: add @JsonFormat to pi-commons PackageType`
- Files: `pi-commons/.../referencedata/model/PackageType.java` (+2), `pi-booking-processor/.../transform/EnrichmentServiceTest.java` (+77 — PackageType **and** ContainerType regression tests)
- `ContainerType.java` has **no net change** (annotation was only toggled for the negative proof, then restored).
- Fix R remains in stash `stash@{0}` / SHA `06dcc5727df7b3c55243584da48a2d2bbcf5487e` (§18.4).

---

## 21. Was it the Jackson version? (before/after evidence)

Common assumption: "the Jackson upgrade flipped the offset from `+0000` to `+00:00`, so it broke." The evidence says the Jackson **version bump is not the trigger** — the booking **model** upgrade swapping the date *reader* is.

### 21.1 Versions
| | Before PI AWS upgrade (`8bba065f0e^`) | After (current) |
|---|---|---|
| booking model (PIBK dep) | **`2.1.7.M`** | **`3.0.0.M`** |
| Jackson pin in `partner-integrator/pom.xml` | **none** (transitive) | **`jackson-bom 2.21.4`** (added in `8bba065f0e`) |
| Effective Jackson | **≥ 2.9** (Jakarta/modern Dropwizard; local `.m2` resolves `2.10.0`) | `2.21.4` |

### 21.2 What the old model did (proven via `javap` on the vendored `booking-2.1.7.M.jar`)
- `…referencedata.model.PackageType.lastModifiedDateUtc` → **bare `java.util.Date`, NO `@JsonDeserialize`** (only SDK v1 `@DynamoDBDocument`). ⇒ Jackson used its **default `StdDateFormat` reader**.
- `ContainerType.lastModifiedDateUtc` → had `@JsonFormat("yyyy-MM-dd HH:mm:ss")` (same as today's pi-commons copy).

### 21.3 The default reader parses `+00:00` (proven with a plain `ObjectMapper`, Jackson `2.10.0` from `.m2`)
```
OK   2018-06-13T12:00:00.000+00:00  -> epoch=1528891200000
OK   2018-06-13T12:00:00.000+0000   -> epoch=1528891200000
OK   2018-06-13T12:00:00.000Z       -> epoch=1528891200000
OK   1528891200000                  -> epoch=1528891200000
```
A no-annotation `Date` field (exactly the old `2.1.7.M` `PackageType`) accepts the colon offset. So **on the old model this value parsed regardless of Jackson version.**

### 21.4 What actually changed
The booking `bk3` upgrade (`ION-14382`, shipped in model `3.0.0.M`) added `@JsonDeserialize(using = FlexibleDateDeserializer.class)` to `PackageType.lastModifiedDateUtc`. That **replaced** Jackson's tolerant default `StdDateFormat` with a **custom, hand-rolled** deserializer whose `SimpleDateFormat` list **omits the ISO colon offset** → it rejects `+00:00`.

### 21.5 Truth table (serialize form × reader)
| Serialized offset | Old reader = default `StdDateFormat` | New reader = `FlexibleDateDeserializer` |
|---|---|---|
| `+0000` (pre-2.9 Jackson) | ✅ | ✅ (via `…SSSZ` RFC-822 pattern) |
| `+00:00` (Jackson ≥ 2.9) | ✅ | ❌ **← the failure** |

The only cell that fails is **new reader + colon offset**. Since the environment was **already ≥ 2.9 before the upgrade** (already producing `+00:00`), the differentiator is the **reader swap**, not the Jackson version. Jackson ≥ 2.9's colon output is a *necessary precondition* that was already satisfied beforehand.

### 21.6 Direct answer
- **Jackson before:** transitive **≥ 2.9** (not pinned; `.m2` shows `2.10.0`). **Jackson now:** `2.21.4`.
- **Would the old setup have been fine?** Yes — but because the old **model** used Jackson's default reader (which parses `+00:00`), **not** because of a different Jackson version. Even on today's `2.21.4`, a plain no-annotation `Date` field parses `+00:00` (§21.3).
- **Does the Jackson version have a role?** A supporting one: the failure needs the colon form, which Jackson ≥ 2.9 emits. But that was already the case pre-upgrade, so the *version change* is not what flipped it — the *reader change* is.

---

## 22. PR description (ready to paste)

> Branch `bugfix/ION-16819-pibk-dateformat-fix` → commit `7390ae6877`

### ION-16819: Fix PIBK booking-feed crash on reference-data date parsing

**Problem**
PIBK (`pi-booking-processor`) fails processing bookings with `EDataSupplementationException: Cannot parse date: "2018-06-13T12:00:00.000+00:00"`. Any booking that enriches package type `PK` (a reference-data record last modified in 2018) poison-loops on the MQ.

**Root cause**
During enrichment, `EnrichmentService.getFromBookingClass` JSON round-trips the pi-commons `PackageType` into the booking model. Because pi-commons `PackageType.lastModifiedDateUtc` had **no `@JsonFormat`**, Jackson serialized it with an ISO-8601 **colon** offset (`+00:00`), which the booking model's date deserializer doesn't accept -> throws. `ContainerType` was never affected because its pi-commons copy already carries `@JsonFormat`.

**Fix**
Add `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "UTC")` to pi-commons `PackageType.lastModifiedDateUtc`, mirroring `ContainerType`. The round-trip now emits the canonical format. One-line, self-contained change.

**Tests**
Added `EnrichmentServiceTest` regression tests for `PackageType` and `ContainerType` with the failing 2018 value. Verified against the current vendored booking jar: reproduces the exact production error without the fix; **18/18 green** with it.

**Scope**
Reviewed all round-trip paths in `pi-booking-processor` (`getFromBookingClass` covers `PackageType`, `ContainerType`, `Geography`, `Country`) — `PackageType` was the only exposed field; the annotation closes it. No other code paths remain.
