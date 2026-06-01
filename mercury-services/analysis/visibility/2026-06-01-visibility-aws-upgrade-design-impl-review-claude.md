# Visibility Module — AWS SDK 2.x Upgrade: Design & Implementation Review

**Jira Ticket**: ION-12316
**Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot`
**Reviewer**: Claude Opus 4.8 (enterprise refactoring review)
**Date**: 2026-06-01
**Scope reviewed**: cloud-sdk migration of the 11 `visibility` sub-modules (entities, converters, DAOs, Guice modules, lambdas, app wiring) on this branch vs `develop`.
**Inputs**: `05042026-visibility-business-rules-claude.md`, `2026-05-31-visibility-aws-upgrade-copilot.md`, `2026-06-01-aws-sdk-upgrade-summary.md`, and the actual branch diff.

---

## 0. Verdict

The migration is **structurally sound and broad in coverage** — entity re-annotation, DAO delegation onto `DatabaseRepository`, S3 → `StorageClient`, SQS → `MessagingClient`, and SSM → `CloudParameterStore` are all done consistently and the test suites pass. The Guice module restructuring is clean.

**However, the change is NOT release-ready.** There are concrete backward-compatibility and runtime-completeness defects that the green test suite masks. Two are blockers:

1. **`MetaData` on-disk format silently changed from String (S) to Map (M)** — this breaks the `visibility-s3-archiver` lambda at runtime and diverges from the two sibling converters. (HIGH / data-format regression)
2. **No environment carries the `cloudSdkDynamoDbConfig:` block the new module requires** — every migrated Dropwizard app will fail to boot with `IllegalStateException`. (HIGH / runtime-incomplete)

Details, severities, and recommended fixes below.

---

## 1. Findings by severity

### 🔴 HIGH-1 — `MetaData` storage format changed S → M; breaks the S3 archiver

**Files**:
- [MetaDataAttributeConverter.java](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/model/containerEvent/converters/MetaDataAttributeConverter.java) (`transformFrom` → `AttributeValue.fromM(...)`, `attributeValueType()` → `M`)
- [VisibilityS3Archiver.java:119-120](../visibility-s3-archiver/src/main/java/com/inttra/mercury/visibility/lambda/VisibilityS3Archiver.java#L119-L120)

**What the legacy code actually did** (verified against `develop`):

```java
// develop: MetaDataConverter implements DynamoDBTypeConverter<String, MetaData>
public String convert(MetaData metaData) { return metaData.toJsonString(); }   // → stored as S (JSON string)
```

The v1 converter is a **`<String, MetaData>` converter**, so `metaData` has always been persisted as a DynamoDB **String (S)** attribute. The same is true for `containerEventSubmission` and `enrichedProperties` (both `<String, …>` converters on `develop`).

**What the new code does**: the two sibling converters correctly keep `S`:
- `ContainerEventSubmissionAttributeConverter` → `fromS(...)`, type `S` ✅
- `ContainerEventEnrichedPropertiesAttributeConverter` → `fromS(...)`, type `S` ✅

…but `MetaDataAttributeConverter` is the **odd one out** — it writes `M` and declares type `M`. Its javadoc claims it *"preserves the native DynamoDB Map format used by AWS SDK v1's `@DynamoDBDocument`."* That premise is **factually wrong**: v1 never used `@DynamoDBDocument` for this field — it used a String converter. So this converter is not *preserving* a format, it is *changing* one.

**Concrete runtime break** — `visibility-s3-archiver` reads the raw item and casts:

```java
// VisibilityS3Archiver.java:119
String metaDataJson = (String) itemAsMap.getOrDefault("metaData", null);  // expects S
Map<String,Object> metaData = stringToMap(metaDataJson);
```

After migration, the inbound/matcher/etc. services persist `metaData` as **M**. `toJavaObject` (line 189) maps an `M` value to a `java.util.Map`, so the `(String)` cast throws **`ClassCastException`**, which bubbles to the catch at line 154 and is rethrown as `VisibilityS3ArchiveException`. **Every MODIFY-stream record written by a migrated service will fail to archive.** (Pre-existing records written as `S` still work — so this surfaces gradually as data is rewritten, which is worse for detection.)

The unit tests don't catch it because the archiver test feeds a hand-built `S` map, not data produced by the new `MetaDataAttributeConverter`.

**Recommendation**: make `MetaDataAttributeConverter` symmetric with its siblings — **write `S`** (a JSON string, ideally via the canonical `MetaData.toJsonString()`), keep the lenient `M`-or-`S` read path for legacy rows. This restores both backward compatibility and the s3-archiver contract. (Then re-point the archiver test through the real converter.)

---

### 🔴 HIGH-2 — `cloudSdkDynamoDbConfig:` is absent from every environment YAML → apps cannot start

**Files**:
- [VisibilityDynamoModule.java:49-57](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/config/VisibilityDynamoModule.java#L49-L57)
- [VisibilityApplicationConfig.java:13,26-32](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/config/VisibilityApplicationConfig.java#L13)
- `visibility/conf/*/config.yaml` (only legacy `dynamoDbConfig:` present)

```java
final BaseDynamoDbConfig dynamoConfig = config.getCloudSdkDynamoDbConfig();
if (dynamoConfig == null) {
    throw new IllegalStateException("cloudSdkDynamoDbConfig is not configured in VisibilityApplicationConfig");
}
```

A repo-wide search confirms **`cloudSdkDynamoDbConfig` appears in zero YAML files**. Therefore `getCloudSdkDynamoDbConfig()` returns `null` and `provideDynamoDbClientConfig()` throws on the first repository injection — i.e. at application boot — for `visibility-inbound`, `-outbound`, `-pending`, `-matcher`, `-wm-inbound-processor`, and `-itv-gps-processor`.

Unit/integration tests pass because the injector tests **bind mocked `DatabaseRepository` instances** and never exercise `provideDynamoDbClientConfig()`. **"All tests pass" therefore does not demonstrate the services run.** The summary doc frames the YAML work as an "out-of-scope operational task," but functionally this means the code is not runtime-complete — the migration and its config are a single atomic unit and should ship together.

**Design divergence (root cause)**: the already-migrated sibling modules took a *different, simpler* approach. In `booking`, `auth`, `network`, and `webbl`, the cloud-sdk `BaseDynamoDbConfig` **reuses the existing `dynamoDbConfig:` key** (its shape changed, the key did not):

```java
// booking/config/BookingConfig.java
private BaseDynamoDbConfig dynamoDbConfig;          // single field, single yaml key
```

Visibility instead **kept the legacy `dynamoDbConfig` (old type) and added a second `cloudSdkDynamoDbConfig`** field+key. That choice is defensible *only because* the legacy `dynamoDbConfig` is still consumed by the still-on-v1 table-creation command config and ES wiring — but it creates the missing-YAML trap and a dual-config smell that no other module carries.

**Recommendation**: (a) add the `cloudSdkDynamoDbConfig:` block to **every** `visibility/conf/*/config.yaml` in this branch (sample/qa/int/cvt/prod/pullRequest), and (b) state explicitly why visibility keeps two dynamo configs while siblings keep one — or follow the sibling convention and migrate the table-creation command too, retiring the legacy block.

---

### 🟠 HIGH/MEDIUM-3 — Table-name derivation switched from `environment + "_"` to `tablePrefix`; verify the prefix actually matches

**Files**: [VisibilityDynamoModule.java:68,89](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/config/VisibilityDynamoModule.java#L68); old [ContainerEventTableDao (develop)] used `dynamoDbConfig.getEnvironment() + "_" + tableName`.

Old physical table name = `inttra2_qa` + `_` + `container_events` = `inttra2_qa_container_events`.
New physical table name = `clientConfig.getTablePrefix()` + `container_events`.

For these to match, the new `cloudSdkDynamoDbConfig` must produce `getTablePrefix() == "inttra2_qa_"` (note the **trailing underscore**). In `booking`'s cloud-sdk config the equivalent value is set as `environment: inttra2_qa_booking`. If the visibility YAML is populated with `environment: inttra2_qa` but `getTablePrefix()` does **not** append the separator, every table name will be wrong (`inttra2_qacontainer_events`) and the services will silently read/write the wrong (non-existent) tables — a `ResourceNotFound` at best, data divergence at worst.

This is currently **unverifiable** because the YAML doesn't exist (see HIGH-2). It must be validated against `BaseDynamoDbConfig.getTablePrefix()` semantics when the config is added, with one round-trip integration check per table.

**Recommendation**: when populating the YAML, assert the resolved table name equals the legacy name for at least `container_events`, `container_events_outbound`, `container_events_pending`, and `booking_BookingDetail`.

---

### 🟠 MEDIUM-4 — JSON serializer settings drift inside the S/JSON blobs

**Files**: `ContainerEventSubmissionAttributeConverter`, `ContainerEventEnrichedPropertiesAttributeConverter` (new) vs `ContainerEventSubmissionConverter`, `ContainerEventEnrichedPropertiesConverter` (develop).

- **Old**: `private static ObjectMapper OBJECT_MAPPER = new ObjectMapper();` — no `JavaTimeModule`, `WRITE_DATES_AS_TIMESTAMPS` defaults **true** (dates → numeric epoch), strict unknown-property handling.
- **New**: registers `JavaTimeModule`, sets `WRITE_DATES_AS_TIMESTAMPS=false` (dates → ISO-8601 strings) and `FAIL_ON_UNKNOWN_PROPERTIES=false`.

Reads are tolerant (good for legacy data), but **newly written blobs will encode date fields differently** from every historically written blob and from any external/non-Java consumer of these JSON columns (e.g. analytics/Redshift export, downstream services, the S3 archive itself). You now have **two date encodings co-existing in the same attribute** across the table.

If the intent was purely to make Java time types serializable, that is a *behavioral* change beyond a pure SDK swap and should be called out and validated against real stored payloads — not introduced incidentally. Prefer matching the legacy encoding unless there is a deliberate, documented reason to change it.

---

### 🟠 MEDIUM-5 — `MetaData` (de)serialized via a private ObjectMapper instead of the canonical `Json` helper

**File**: [MetaDataAttributeConverter.java:32-41,60,72](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/model/containerEvent/converters/MetaDataAttributeConverter.java#L32-L41)

`MetaData` (in `messaging-helper`) is `@JsonDeserialize(builder = MetaData.Builder.class)`, `@JsonInclude(NON_EMPTY)`, with `@JsonFormat(pattern = Json.DEFAULT_DATE_TIME_PATTERN)` on `timestamp`, and ships canonical `toJsonString()` / `parseJson()` built on a shared `Json` mapper. The new converter bypasses all of that with its own `ObjectMapper` plus a `MetaDataDynamoDbMixIn` that forces a *different* (`T`-separator, `shape=STRING`) timestamp format than the class's own (`space`-separator) default.

So beyond the S→M container change (HIGH-1), the **timestamp inside metadata also changes representation**, and the round-trip no longer goes through the authoritative serializer. This is fragile (any future `MetaData` field/annotation change won't be reflected here) and is the kind of parallel-serialization logic that drifts silently.

**Recommendation**: fold this into the HIGH-1 fix — serialize/deserialize `MetaData` as `S` using `MetaData.toJsonString()` / `MetaData.parseJson()`, and delete the mixin + bespoke mapper. That keeps one source of truth and matches what the s3-archiver already expects.

---

### 🟠 MEDIUM-6 — Retry net widened from `ProvisionedThroughputExceededException` to all `RuntimeException`

**File**: [ContainerEventDao.java:47-69](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/persistence/ContainerEventDao.java#L47-L69)

```java
// develop: catch (ProvisionedThroughputExceededException e)  // throttling only
// branch:  catch (RuntimeException e)                        // everything
```

The migrated `findById` now retries (with sleeps, up to 3×) on **any** `RuntimeException`. Non-transient faults — a deserialization failure on bad data, a validation error, a `ResourceNotFoundException` (very relevant given HIGH-3), a NPE — now incur ~0.2–1.2 s of pointless back-off before surfacing, and transient-vs-permanent is no longer distinguished. On a hot read path this both adds latency to genuine errors and hides their immediacy.

**Recommendation**: catch only the cloud-sdk's throughput/throttling equivalent (or a narrow transient set), and let other exceptions propagate immediately.

---

### 🟡 LOW-7 — GSI lookups now fully deserialize every matched row just to read the `id`

**Files**: [ContainerEventDao.queryIndex](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/persistence/ContainerEventDao.java#L116-L124), [ContainerEventTableDao.queryIndex](../visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/persistence/dynamodb/ContainerEventTableDao.java#L97-L112)

The old code queried the GSI and read only the `id` projection (no entity mapping). The new code runs `repository.query(...)` which **maps every returned row into a `ContainerEvent`**, invoking the JSON/`MetaData` attribute converters, purely to extract `getHashKey()` and split CE vs CTE ids — after which it does a second `findAll` to fetch the full items anyway. Two concerns:

1. **Perf**: on indexes projecting `ALL`, this is a wasted full deserialization of the GSI page on a hot lookup path. (`KEYS_ONLY` indexes are cheap, since only keys are present.)
2. **Correctness/robustness**: the table is shared with `ContainerTrackingEvent` rows (different model). Mapping a foreign-model row into `ContainerEvent` via the enhanced client relies on every converter tolerating missing/foreign attributes. It currently does (nulls), but it's an implicit invariant worth a comment/test.

**Recommendation**: if the cloud-sdk repo/`QuerySpec` supports a projection or a keys-only/attributes-to-project option, use it to fetch only `id` for the discriminator step; otherwise document the deliberate trade-off.

---

### 🟡 LOW-8 — S3 archive numeric attributes change type (BigDecimal → String)

**File**: [VisibilityS3Archiver.toJavaObject:183-185](../visibility-s3-archiver/src/main/java/com/inttra/mercury/visibility/lambda/VisibilityS3Archiver.java#L183-L185)

The SDK v1 `Item.asMap()` represented `N` attributes as `BigDecimal`; the new `toJavaObject` returns `av.n()` as a raw `String`. Top-level numeric attributes (`expiresOn`, and any numeric in the reconstructed map) will now serialize into the S3 JSON as **quoted strings** instead of numbers. Likely cosmetic, but it changes the archived document schema — confirm no downstream consumer of the archive parses these as numbers.

---

### 🟡 LOW-9 — Binary `booking-3.0.0.M.jar` committed into the source tree

**Files**: `visibility/visibility-commons/lib/com/inttra/mercury/booking/3.0.0.M/booking-3.0.0.M.jar` (+ pom)

A 669 KB binary built locally from `develop` source is checked into the repo as a file-system Maven repo. This is a pre-existing pattern (the old `booking-2.1.8.M.jar` was there too), but the upgrade is a good moment to flag it: it's not reproducible (the jar's provenance is a manual `jar cf` of a developer's `target/classes`), it bypasses the artifact registry, and `3.0.0.M` is a synthetic version that won't correspond to any published `booking` release. Risk: the visibility runtime classpath silently diverges from the real `booking` module. **Recommendation**: source this artifact from the shared registry with a real coordinate, or document the rebuild procedure and pin it to a known booking commit.

---

## 2. What was done well (no action needed)

- **DAO delegation** onto `DatabaseRepository` is clean and consistent across all six DAOs; key construction (`DefaultPartitionKey` / `DefaultCompositeKey`) is correct, and the outbound `BETWEEN` sort-key query plus the `RESULT_SIZE_LIMIT` boundary-trim logic were preserved faithfully ([ContainerEventOutboundDao.java:47-92](../visibility-commons/src/main/java/com/inttra/mercury/visibility/common/persistence/ContainerEventOutboundDao.java#L47-L92)).
- **Entity re-annotation** of `ContainerEvent` is faithful: partition key `id`, the five GSIs, `@TTL` on `expiresOn`, and the `bkRef`/`equipment` composite GSI (one partition + one sort annotation) all map 1:1 to the v1 annotations. Field-level upper-casing setters were retained.
- **`containerEventSubmission` / `enrichedProperties` converters** correctly keep the `S` format and add a tolerant `M`-or-`S` read — this is exactly the right backward-compat shape (and is the template HIGH-1 should follow).
- **S3 / SQS / SSM swaps** (`StorageClient`, `MessagingClient`, `CloudParameterStore`) are idiomatic; the `${awsps:...}` prefix handling and the lazy `getParameterStore()` init (avoiding client construction at class-load for `mockStatic`) are sensible.
- **Deliberate v1 retentions** are correct: Lambda runtime event models (`com.amazonaws.services.lambda.runtime.events.*`) and `OperationType` for stream parsing have no v2 equivalent and rightly stay.
- **`VisibilityWMDynamoModule` split** to keep `DynamoDbClientConfig` out of the injector (so the injector unit test can bind a mocked repo) is a pragmatic, well-reasoned isolation choice.
- **Region resolution** (`DefaultAwsRegionProviderChain` → `AwsRegionWrapper`, US-EAST-1 fallback) is uniform.

---

## 3. Documentation accuracy comments

The two companion docs overstate completeness in ways a reviewer should correct:

- *"ALL PHASES COMPLETE … BUILD SUCCESS, 0 failures"* and *"Implementation complete"* — true for compilation/tests, but **the services do not start without the missing YAML (HIGH-2)**, and the s3-archiver has a latent runtime break (HIGH-1). "Tests pass" ≠ "runtime-complete" here because the tests mock the repositories.
- *"MetaDataAttributeConverter — Serializes metadata with backward compat for SDK v1 Map format"* and §12 *"All converters handle both legacy (SDK v1) and new (SDK v2) data formats"* — the SDK v1 format for `metaData`/`submission`/`enriched` was **String, not Map**. The "Map" framing is the source of the HIGH-1 defect and should be removed/corrected.
- The summary should record the **table-prefix equivalence check** (HIGH-3) as an explicit acceptance criterion, not leave it implicit.

---

## 4. Recommended pre-merge checklist

1. **(HIGH-1/5)** Change `MetaDataAttributeConverter` to write `S` via `MetaData.toJsonString()`; keep lenient read; drop the mixin. Re-point the s3-archiver test through the real converter.
2. **(HIGH-2)** Add `cloudSdkDynamoDbConfig:` to all `visibility/conf/*/config.yaml`; decide whether to keep dual config or converge on the sibling-module single-`dynamoDbConfig` pattern.
3. **(HIGH-3)** Verify `getTablePrefix()` yields the exact legacy physical table names (trailing-underscore check) with one integration round-trip per table.
4. **(MEDIUM-4)** Decide intentionally on the date encoding inside the submission/enriched JSON blobs; align with legacy unless a documented reason exists.
5. **(MEDIUM-6)** Narrow `ContainerEventDao.findById` retry to transient/throttling exceptions.
6. **(LOW-7/8/9)** Track as follow-ups: GSI projection optimisation, S3 numeric-type drift, and sourcing `booking-3.0.0.M.jar` from the registry.

The headline risk is **silent data-format drift** (`metaData` S→M, date encodings) that the mocked test suite cannot see and that surfaces only against real DynamoDB data and the s3-archiver — fix HIGH-1 and HIGH-2 before any deployment.
