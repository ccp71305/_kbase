# cloud-sdk Gap — appianway AWS v2 Upgrade — Design & Implementation Plan

> Date: 2026-07-23 · Author: Copilot (Claude Opus 4.8) · Workspace: `mercury-services-commons`
> MCP context session: **`35cb592127df48b2`** — `ION-12310 cloud-sdk Gap Impl (appianway AWS upgrade)` (load this session when resuming/continuing this work).
> Target line: **`mercury-services-commons 1.0.27-SNAPSHOT`** (`cloud-sdk-api` + `cloud-sdk-aws` + `commons`).
> Scope: the strictly-additive `cloud-sdk-api` / `cloud-sdk-aws` / `commons` enhancements required by the **appianway** AWS Java SDK v1 → v2 (cloud-sdk) migration.
> Source-of-truth inputs reviewed: appianway `2026-07-22-…-ROLLUP-claude.md`, `2026-07-22-…-foundation-claude.md`, `2026-06-30-…-cloud-sdk-gap-DESIGN.md`, the ION-12317 program + 9 module docs, and the 14 per-module `2026-07-22-…-awsupgrade-claude.md` docs. Every **cloud-sdk-side** "current state" below is **verified against the live source in this workspace** (`mercury-services-commons`). **Cross-repo facts** (appianway `shared` constants/`setAnnotations`, the mercury-services consumer usages in §2.1, `ingestor`'s `vc.inreach` v1 signer, the v1 `DynamoTableCommand`) were **verified against the appianway / mercury-services workspaces per Appendix A** — not this workspace (F5).

---

## 0. The non-negotiable contract (read first)

`cloud-sdk-api`, `cloud-sdk-aws`, and `commons` are **live libraries consumed in production** by already-upgraded mercury-services apps: **booking, visibility, auth, network, booking-bridge, registration, tx-tracking** (all on cloud-sdk + AWS 2.x). appianway is the **ETL hub** for EDI/publisher-consumer processing used across mercury-services, so `1.0.27-SNAPSHOT` and every WIRE format must stay byte-stable.

> **Binding rule for every change in this document:** strictly **additive and behavior-preserving** — new `default` interface methods, new overloads, new classes/fields, or visibility-widening only. **No existing signature, return type, default value, generic bound, serialization key, or runtime default may change.** A non-upgraded mercury-services app — recompiled or not — must behave **identically** before and after.

| Change kind used here | Binary compat | Source compat | Why safe |
|---|:---:|:---:|---|
| New `default` method on existing interface | ✅ | ✅ | Existing implementors inherit; no new abstract method |
| New overload (distinct parameter list) | ✅ | ✅ | Overload resolution is additive; existing overloads untouched |
| New concrete class / builder field | ✅ | ✅ | Nothing references it until adopted |
| New `public static final String` constant | ✅ | ✅ | Pure source addition; used only as a `Map` key → zero wire change |
| Visibility widening (`private`→`protected`) | ✅ | ✅ | Strictly relaxes access |

**Verification gate (applies to the whole change set):** `cloud-sdk` CI green **and** the **upgraded mercury-services consumer modules only** built green against the same `1.0.27-SNAPSHOT` — **before and after** each commit. **Do NOT run a full mercury-services reactor build** (the other modules are not yet on cloud-sdk); build just the upgraded modules with their upstream deps:
```
mvn -pl network,auth,registration,self-service-reports,tx-tracking,booking,visibility,webbl,booking-bridge,db-migration -am verify
```
That scoped green build (before and after) is the proof of zero impact.

---

## 1. Executive summary — the whole gap surface

| ID | Title | Status | Library | Verified current state | Backward-compat |
|----|-------|--------|---------|------------------------|-----------------|
| **S-G2** | `StorageClient` write-with-metadata/content-type + copy-with-replaced-metadata | **REQUIRED** | api + aws | ✅ Confirmed absent — `StorageClient` has only metadata-less `putObject`/4-arg `copyObject` | 3 new `default` methods + impl overrides |
| **W-G9.1** | `Event.Builder` annotations round-trip | **REQUIRED** | api | ✅ Confirmed defect — builder has no `annotations`; `parseJson` silently drops them | Additive builder field/method |
| **W-G9.2** | `MetaData.Projection` (+6) & `Event.Token` (+9) constant parity | **REQUIRED** | api | ✅ Confirmed — 6 Projection + 9 Token constants absent | New `String` constants (zero wire) |
| **X-G7** | `replyTo` on `MailContent` / SES send | **REQUIRED** (confirmed absent) | api + aws | ✅ Confirmed absent — `MailContent` exposes subject/html/text/attachments only | Additive `default` getter + field + SES mapping |
| **X-G10** | `EmailService` first-class **attachment** support (raw MIME) | **REQUIRED** (confirmed absent) | aws (+ api convenience) | ✅ Confirmed — `SesEmailServiceImpl.buildEmailContent` builds a `simple` message only and **ignores `MailContent.getAttachments()`** | Additive raw-MIME branch; simple path unchanged |
| **X-G8** | Jest/OpenSearch signing | **NO CHANGE** (verify-confirmed) | aws | ✅ ingestor and mercury-services both sign via the **`vc.inreach` (v1) signer**; `JestClientBuilder` takes the interceptor from the caller | n/a — ingestor keeps the `vc.inreach` 1.x signer (same as booking/visibility/webbl) |
| **X-G11** | Null-safe SSM **profile-file** supplier (`ParameterStoreClientFactory` boot resilience) | **RECOMMENDED** (hardening; **boot-path modification**; **deferred to separate `1.0.29`**) | aws | ✅ `ParameterStoreClientFactory` sets **no** profile-file supplier → relies on the SDK default that NPEs on a null `user.home` under a future BOM bump/skew | Adds the null-safe supplier only (**no `defaultProfileName`**); credentials/region **unchanged**. **Not "inert" like the other five** — modifies the boot-time `createParameterStore` path; **deferred to a separate `1.0.29` effort**, not merged with `1.0.28` (F1/F2) |
| **C-G6** | Widen commons `getConfigTransformer` `private`→`protected` | **OPTIONAL** | commons | ✅ Confirmed `private` today; composition already works without it | Visibility widening only |
| ~~O-G1 / O-G3 / G4 / G5 / G7~~ | concurrent SQS listener / S3-event parser / DynamoDB lock / Thymeleaf / health helpers | **DE-SCOPED** | — | Handled inside appianway on existing public API | n/a |

**Bottom line:** five required additive changes — **S-G2, W-G9.1, W-G9.2, X-G7, X-G10** — plus one approved visibility widen (**C-G6**) and the approved commons config-substitution contribution (§7.3), all landing together as **`1.0.28-SNAPSHOT`**; and one **recommended hardening** (**X-G11**, SSM profile-file resilience) **deferred to a separate later `1.0.29-SNAPSHOT`** (it modifies a boot path — F2 — so it is not merged with the `1.0.28` set). **X-G8 needs no library change.** **No DynamoDB SDK change is required** (transformer + watermill offsets use the native v2 enhanced client / `@DynamoDbVersionAttribute`), so there is no DynamoDB wire surface to alter here.

### 1.1 Open questions raised in review (2026-07-23) — answered inline
| # | Question | Answer | Where |
|---|----------|--------|-------|
| Q1 | Does ingestor supply a **v2** Jest signer? Isn't it AWS 1.x like booking/visibility/webbl? | **Corrected — yes, 1.x.** ingestor's `JestModule` signs with `vc.inreach.aws.request.AWSSigner` over a v1 `DefaultAWSCredentialsProviderChain`; mercury-services `JestClientBuilder` uses the same `vc.inreach` interceptor. **X-G8 is a no-op** — keep the `vc.inreach` 1.x signer. | §7.1 |
| Q2 | Do the `Event`/`MetaData`/`Annotations` changes break upgraded mercury-services apps (booking, booking-bridge, network, tx-tracking, visibility, webbl)? | **No — verified against live mercury-services source.** No app calls cloud-sdk `Event.parseJson`/`Event.Builder(Event)` (the only paths W-G9.1 alters); booking-bridge uses the **object-level** `setAnnotations` (untouched); constants are additive. | §2.1 |
| Q3 | Is C-G6 (`private`→`protected`) safe? | **Yes — zero breakage confirmed** (no override/subclass conflict in mercury-services or appianway). | §7.2 |
| Q4 | Should appianway's multi-`.properties` substitution move into commons? | **APPROVED (decision 2026-07-23)** — lift it into commons as a reusable `ConfigurationSourceProvider` (pairs with C-G6). Additive, zero risk. | §7.3 |
| Q5 | How are DynamoDB tables created in appianway? Is the `DynamoDbAdminCommand` (that booking/network now use) needed? | appianway today uses **module-local v1 `DynamoTableCommand`** (DW command). **Recommended:** adopt cloud-sdk-aws **`DynamoDbAdminCommand`** (`dynamo-create`) as visibility/booking did — **already in the SDK, not a new change**. | §9 |
| Q6 | Address the **SES email gap in visibility** (ION-12316)? | **Added as X-G10.** `SesEmailServiceImpl` ignores `MailContent.getAttachments()`, forcing `visibility-inbound` onto a direct `SesV2Client`. Add an additive raw-MIME branch so attachment mail flows through the wrapper; simple path unchanged. Composes with X-G7 reply-to. | §6.5 |
| Q7 | Does X-G10 impact **booking** (sends attachment email) or **auth**? | **No — verified.** booking sends **all** mail via `sendTemplateEmail(...)` (the **template** MIME path, which X-G10 does not touch); its "attachment" is the `IsIncludeHTMLAttachment` template var. auth's `SimpleMailContent.getAttachments()` returns `emptyList()` → unchanged simple path. X-G10 adds a **new** `EmailMimeUtils` overload + a branch that fires only on non-empty attachments. | §2.1, §6.5 |
| Q8 | Risk of the **SSM profile-file resilience** (X-G11) to already-upgraded apps? | **None** — the hardening **only adds** a null-safe `defaultProfileFileSupplier`; region + `config.getCredentialsProvider()` are **unchanged**. It yields ProfileFile content equivalent to today in both local (`~/.aws`) and ECS (empty) — just NPE-proof. **Include it.** | §7.4 |

---

## 2. Consumer-impact proof — why already-upgraded mercury-services apps cannot break

| Change | Reaches booking / visibility / auth / network / booking-bridge / registration / tx-tracking? | Evidence |
|---|---|---|
| **S-G2** | No | New 5-/6-arg overloads; nobody calls them today. Existing `putObject`/`copyObject` byte-for-byte unchanged. |
| **W-G9.1** | No | `booking`, `auth`, `network` use their **own** `MetaData`/`Event` (not cloud-sdk's). The only cloud-sdk `notification.workflow` consumers — **visibility / webbl / booking-bridge** — construct+publish via `EventGenerator`/`EventLogger` + the primary `Event.Builder` ctor + object-level `setAnnotations`; none use `Event.parseJson`/copy-ctor, the only paths W-G9.1 touches. W-G9.1 **restores** the historical `shared` round-trip additively. |
| **W-G9.2** | No | Pure new `String` constants used as `Map` keys → serialization is identical; existing keys untouched. |
| **X-G7** | No | New `default List<String> getReplyTo()` returns empty; existing `MailContent` impls and `sendEmail` callers unchanged; SES maps reply-to only when non-empty. |
| **X-G10** | No | Raw-MIME branch fires **only when `getAttachments()` is non-empty**, and adds a **new** `EmailMimeUtils` overload (the template `createMimeMessage(EmailRequest,vars)` used by booking is untouched). Verified: **booking** sends via `sendTemplateEmail(...)` (template path → unaffected); **auth** `SimpleMailContent.getAttachments()` returns `emptyList()` → unchanged simple path; network sends attachment-less mail. |
| **X-G11** | No | Adds a null-safe `defaultProfileFileSupplier` only (no `defaultProfileName`); **region + credentials provider unchanged** (`config.getCredentialsProvider()`). Produces ProfileFile content equivalent to today in local (`~/.aws`) and ECS (empty) — behavior-identical, just NPE-proof. **Caveat (F2):** unlike the other rows this **modifies an existing boot path** (`createParameterStore`, run by every app at startup) rather than adding an uncalled surface — behavior-equivalent but a *modification*, so it is **deferred to a separate later `1.0.29` bump** (not in the `1.0.28` landing) and carries an explicit `AWS_PROFILE`-set test. |
| **C-G6** | No | `private`→`protected` relaxes access only; no caller affected. |

### 2.1 Verified against live mercury-services source (2026-07-23)

Searched the mercury-services workspace (`booking, booking-bridge, network, tx-tracking, visibility/*, webbl, partner-integrator, watermill-publisher, …`) for every path the workflow-model changes could touch:

| Finding | Evidence (mercury-services) | Impact of W-G9 |
|---|---|---|
| Modules importing cloud-sdk `notification.workflow`/`annotation` | **booking, booking-bridge, visibility/\*, webbl** only | Candidate surface — analyzed below |
| **No** module calls cloud-sdk `Event.parseJson(...)` | grep for `Event.parseJson` → only `S3Event.parseJson` (unrelated) and **local** `MetaData.parseJson` | W-G9.1's deserialization fix is **unreachable** → no behavior change |
| **No** module uses the `new Event.Builder(Event)` copy-ctor | grep for `new Event.Builder(<var>)` → none | W-G9.1's copy-ctor annotations line is **unreachable** |
| booking-bridge sets annotations via the **object-level** `@Data` setter | `booking-bridge/.../EventLogger.java:64` `closeRunEvent.setAnnotations(annotations)` | W-G9.1 adds a setter to the **Builder**, not the object — this call is **untouched** |
| `network`, `auth`, `partner-integrator`, `tx-tracking`, `watermill-publisher` use their **own** `MetaData`/`Event` classes | e.g. `tx-tracking/.../model/MetaData.java`, `partner-integrator/pi-commons/.../task/MetaData.java`, `watermill-commons/.../task/MetaData.java` | cloud-sdk changes **cannot reach** them |
| visibility/webbl call cloud-sdk `MetaData.parseJson(...)` (e.g. `MetaDataAttributeConverter`, persisted to DynamoDB) | `visibility-commons/.../MetaDataAttributeConverter.java:53` | W-G9.2 only **adds** `Projection` constants (Map keys) → serialization byte-identical → safe |
| Event construction everywhere goes through the primary builder ctor + `.setX().build()` (annotations never set on builder) | booking / booking-bridge / visibility `EventGenerator`/`EventLogger` | New `Event(Builder)` line assigns `builder.annotations == null` → identical to today |

**Conclusion:** W-G9.1 + W-G9.2 are provably behavior-neutral for every upgraded mercury-services app — the only behavioral delta (annotations surviving a `parseJson`) is on a code path **no mercury-services app exercises**, and it *restores* the historical `shared` contract that appianby cross-service messages already assume. S-G2 and X-G7 are new overloads / defaulted accessors with no existing caller. Gate remains: the scoped upgraded-consumer build green before/after (§0 — no reactor build).

---

## 3. S-G2 — `StorageClient` metadata/content-type write & copy *(REQUIRED)*

### 3.1 Verified current state
`cloud-sdk-api/.../storage/api/StorageClient.java` exposes:
```java
void putObject(String bucketName, String key, byte[] content);
void putObject(String bucketName, String key, InputStream content, long contentLength);
void putObject(String bucketName, String key, File file);
void putObject(String bucket, String fileName, String content);
boolean copyObject(String srcBucket, String srcFileName, String dstBucket, String dstFileName);
```
None carry user metadata or content-type. `S3StorageClient` (the sole impl) already imports `PutObjectRequest`, `CopyObjectRequest`, `RequestBody` — but **not** `MetadataDirective` yet.

### 3.2 Consumers (from module docs)
| Module | Use case | Overload exercised |
|---|---|---|
| **event-writer** (primary) | `{component}-{type}-{eventId}.json` audit objects tagged `application/json` | `putObject(bucket,key,byte[],Map,String)` |
| **dispatcher** | `ZipPreprocessor` writes unzipped entries with user metadata + content-type | `putObject(bucket,key,byte[],Map,String)` |
| **distributor** | delivery + archive copies that **replace** destination metadata (workflow IDs + projection keys), ×2 in `FileDeliveryService` | `copyObject(src,srcKey,dst,dstKey,Map,String)` |
| **error-processor** | archive put with optional metadata/content-type | `putObject(bucket,key,byte[],Map,String)` |
| **transformer**, **splitter** | *reference only* (used iff a write carries metadata/content-type) | put overload |

### 3.3 Design — `cloud-sdk-api` `StorageClient` (add 3 `default` methods)
```java
import java.util.Map;

/** Write bytes with user metadata and an explicit content-type. */
default void putObject(String bucketName, String key, byte[] content,
                       Map<String, String> metadata, String contentType) {
    putObject(bucketName, key, content);                 // safe fallback: ignores metadata/contentType
}

/** Streaming variant with known content length. */
default void putObject(String bucketName, String key, InputStream content, long contentLength,
                       Map<String, String> metadata, String contentType) {
    putObject(bucketName, key, content, contentLength);  // safe fallback
}

/** Copy that REPLACES destination metadata/content-type (S3 REPLACE directive). */
default boolean copyObject(String srcBucket, String srcKey, String dstBucket, String dstKey,
                           Map<String, String> replacedMetadata, String contentType) {
    return copyObject(srcBucket, srcKey, dstBucket, dstKey);   // safe fallback: ignores metadata
}
```

### 3.4 Design — `cloud-sdk-aws` `S3StorageClient` (override all 3; add `MetadataDirective` import)
```java
import software.amazon.awssdk.services.s3.model.MetadataDirective;

@Override
public void putObject(String bucketName, String key, byte[] content,
                      Map<String, String> metadata, String contentType) {
    PutObjectRequest.Builder b = PutObjectRequest.builder()
        .bucket(bucketName).key(key).contentLength((long) content.length);
    if (metadata != null && !metadata.isEmpty()) b.metadata(metadata);
    if (contentType != null && !contentType.isBlank()) b.contentType(contentType);
    executePut(() -> s3Client.putObject(b.build(), RequestBody.fromBytes(content)), bucketName, key);
}

@Override
public void putObject(String bucketName, String key, InputStream content, long contentLength,
                      Map<String, String> metadata, String contentType) {
    PutObjectRequest.Builder b = PutObjectRequest.builder()
        .bucket(bucketName).key(key).contentLength(contentLength);
    if (metadata != null && !metadata.isEmpty()) b.metadata(metadata);
    if (contentType != null && !contentType.isBlank()) b.contentType(contentType);
    executePut(() -> s3Client.putObject(b.build(), RequestBody.fromInputStream(content, contentLength)),
               bucketName, key);
}

@Override
public boolean copyObject(String srcBucket, String srcKey, String dstBucket, String dstKey,
                          Map<String, String> replacedMetadata, String contentType) {
    CopyObjectRequest.Builder b = CopyObjectRequest.builder()
        .sourceBucket(srcBucket).sourceKey(srcKey)
        .destinationBucket(dstBucket).destinationKey(dstKey)
        .metadataDirective(MetadataDirective.REPLACE);   // without REPLACE, COPY keeps SOURCE metadata
    if (replacedMetadata != null && !replacedMetadata.isEmpty()) b.metadata(replacedMetadata);
    if (contentType != null && !contentType.isBlank()) b.contentType(contentType);
    return executeCopy(() -> s3Client.copyObject(b.build()), srcBucket, srcKey, dstBucket, dstKey);
}
```
> `executePut` / `executeCopy` above denote the module's existing try/catch → `S3OperationException` wrapping pattern already used by the current `putObject`/`copyObject` methods; reuse it verbatim (do not introduce a new error path).

### 3.5 Files touched
- `cloud-sdk-api/.../storage/api/StorageClient.java` (+3 `default` methods, +`java.util.Map` import).
- `cloud-sdk-aws/.../storage/impl/S3StorageClient.java` (+3 overrides, +`MetadataDirective` import).

### 3.6 Backward-compatibility — zero risk
- Interface methods are `default` → no new abstract method; existing/test implementors keep compiling with the metadata-less fallback.
- `S3StorageClient` only **adds** overrides; the existing 3-/4-arg `putObject` and 4-arg `copyObject` are untouched. `REPLACE` is reachable only through the new 6-arg copy that nobody calls today (default `COPY` keeps source metadata).

### 3.7 Tests (JUnit 5 + AssertJ + Mockito; 100% of new methods)
Unit (`S3StorageClientTest`, mock `S3Client`, `ArgumentCaptor<PutObjectRequest>` / `CopyObjectRequest`):
1. put(bytes, metadata, contentType) → captured request has `.metadata()` == map and `.contentType()` == given.
2. put(stream, len, metadata, contentType) → captured request has content-length, metadata, content-type; `RequestBody` length == len.
3. put with `null`/empty metadata and `null` content-type → neither `.metadata()` nor `.contentType()` set (no accidental empty map).
4. copy(…, replacedMetadata, contentType) → captured request has `metadataDirective == REPLACE`, metadata, content-type.
5. copy with `null` metadata → `REPLACE` set, no metadata applied.
6. **Regression:** existing `putObject(bytes)` / `copyObject(4-arg)` request-shape tests unchanged.
7. **Compat:** an anonymous `StorageClient` implementing only the pre-existing methods compiles and the new defaults fall back (asserts the metadata-less method is invoked).

Integration (optional, real/localstack-style S3 already used by the storage test suite): put-with-metadata then `getObject` → metadata + `Content-Type` round-trip; copy-with-`REPLACE` → destination shows the **new** metadata, not the source's.

---

## 4. W-G9.1 — `Event.Builder` annotations round-trip *(REQUIRED)*

### 4.1 Verified current defect
`cloud-sdk-api/.../notification/workflow/Event.java`:
- The `Event` class **has** `private Annotations annotations;` (mutable via Lombok `@Data` setter) and serializes it (getter present).
- `Event` is `@JsonDeserialize(builder = Event.Builder.class)`, `@JsonIgnoreProperties(ignoreUnknown = true)`.
- **`Event.Builder` has NO `annotations` field, NO `setAnnotations`, and `Builder(Event e)` does NOT copy annotations. `Event(Builder)` never assigns `annotations`.**

Consequence: `Event.parseJson(json)` runs through the builder → an `Event` JSON carrying `annotations` is **silently dropped** (asymmetric: write-only). appianway `shared` `Event.Builder` (verified) *does* have `setAnnotations`, copies it in `Builder(Event)`, and the ctor sets `this.annotations = builder.annotations`. W-G9.1 **restores** that historical behavior in cloud-sdk-api.

### 4.2 Design (additive, exactly mirrors `shared`)
In `Event.Builder`:
```java
// add field alongside the other optional parameters
private Annotations annotations;

// add to Builder(Event e), next to the other copies
this.annotations = e.getAnnotations();

// add setter (JsonPOJOBuilder withPrefix="set" → maps the "annotations" JSON key)
public Builder setAnnotations(Annotations val) {
    annotations = val;
    return this;
}
```
In the `Event(Builder builder)` constructor, add:
```java
this.annotations = builder.annotations;
```
> `Annotations` is already imported in `Event.java`. `annotations` stays a non-`final` `@Data` field (object-level `setAnnotations` used by `EventLogger.logCloseRunEvent(...,Annotations)` remains valid). No `@JsonInclude`/format/field-order change.

### 4.3 Backward-compatibility — zero risk / restorative
- Adds one builder field + one builder method + one ctor assignment. No existing signature/field/format changes.
- Apps that never send annotations serialize/deserialize identically (`@JsonInclude(NON_EMPTY)` omits a null/empty `annotations`).
- Restores parity with `shared`, which appianway cross-service messages already assume.

### 4.4 Tests
1. `Event` built with `setAnnotations(a)` → `toJsonString()` contains the `Annotations` payload (unchanged behavior).
2. **Defect guard:** `Event.parseJson(jsonWithAnnotations).getAnnotations()` is non-null **and its inner `List<Annotation>` is non-empty and equals the source** (F4 — assert inner content, not just a non-null wrapper: `Annotations` has no `@JsonCreator`/setter and Jackson populates its list via the getter, so a key/casing mismatch would yield an **empty-but-non-null** `Annotations` that a non-null check would wrongly pass).
3. **Round-trip stability:** `parseJson(json) → toJsonString()` is byte-stable for a payload **with** annotations and one **without**.
4. `new Event.Builder(existingEventWithAnnotations).build().getAnnotations()` preserved (copy-ctor).
5. Cross-impl equivalence in the corpus test (§8).

---

## 5. W-G9.2 — constant parity: `MetaData.Projection` (+6) & `Event.Token` (+9) *(REQUIRED)*

### 5.1 Verified gap (exact names, from appianway `shared` sources)

**`MetaData.Projection` — add these 6** (absent in cloud-sdk today):
```java
public static final String REPROCESS = "reprocess";
public static final String SUBSCRIPTION_ID = "subscriptionId";
public static final String DISTRIBUTOR_REST = "distributorRest";
public static final String ORIGINAL_IB_WORKSPACE_FILE = "originalInboundWorkspaceFile";
public static final String SPLITTER_FILE_SIZE = "splitterFileSize";
public static final String EVENT_PROVIDER = "eventProvider";
```

**`Event.Token` — add these 9** (absent in cloud-sdk today):
```java
public static final String ORIGINAL_FILE_SIZE = "originalFileSize";
public static final String FTP_DELIVERY_FILE_NAME = "ftpDeliveryFileName";
public static final String FTP_ARCHIVE_FILE_NAME = "ftpArchiveDeliveryFileName";
public static final String FTP_CUSTOMER_DELIVERY_FILE_NAME = "ftpCustomerDeliveryFileName";
public static final String FTP_CUSTOMER_DELIVERY_DROP_OFF = "ftpCustomerDeliveryDropOff";
public static final String FTP_CARRIER_DELIVERY_FILE_NAME = "ftpCarrierDeliveryFileName";
public static final String FTP_CARRIER_DELIVERY_DROP_OFF = "ftpCarrierDeliveryDropOff";
public static final String FTP_CUSTOMER_ARCHIVE_FILE_NAME = "ftpCustomerArchiveFileName";
public static final String FTP_CARRIER_ARCHIVE_FILE_NAME = "ftpCarrierArchiveFileName";
```
> The literal **values** exactly match `shared`, so appianway code that reads/writes these `Map` keys is wire-identical across the two libraries. These are pure source-compat additions (compilation parity); **zero wire change**.

### 5.2 Backward-compat — zero risk
New `public static final String` constants only. Existing constants and the `projections`/`tokens` `Map` serialization are untouched.

### 5.3 Tests
- Assert each new constant's value (guards against typos that would silently split a `Map` key across services) — parameterized test over `{constantName → expectedValue}`.
- A `MetaData` with a projection under `Projection.EVENT_PROVIDER` (and an `Event` token under `Token.FTP_DELIVERY_FILE_NAME`) round-trips through `parseJson`/`toJsonString` with the key preserved.

---

## 6. Email gaps — X-G7 (`replyTo`) & X-G10 (attachments) *(REQUIRED)*

### 6.0 Why grouped
Both are additive `cloud-sdk` email enhancements on the **same** `MailContent` / `SesEmailServiceImpl` surface and **compose cleanly**: X-G7 adds reply-to (applied on the `SendEmailRequest` for both the simple and raw paths); X-G10 adds attachments (switches to a raw-MIME `EmailContent` when attachments are present). X-G7 is driven by appianway **email-sender**; X-G10 is driven by mercury-services **visibility-inbound** (ION-12316) and benefits email-sender too.

## 6a. X-G7 — `replyTo` on `MailContent` / SES send *(REQUIRED — confirmed absent)*

### 6.1 Verified current state
`cloud-sdk-api/.../email/api/MailContent.java` exposes only `getSubject`/`getHtmlBody`/`getTextBody`/`getAttachments` — **no reply-to**. `MailContentImpl` (`@Data @Builder`) has no `replyTo`. `SesEmailServiceImpl.sendEmail(...)` builds `SendEmailRequest` **without** `.replyToAddresses(...)`. appianway email-sender needs the v1 `withReplyToAddresses` equivalent.

### 6.2 Design (additive; no `EmailService` signature change)
**`MailContent` interface — add a `default` accessor** (existing impls keep compiling):
```java
import java.util.Collections;
/** Reply-To addresses; empty means "none" (SES then omits the header). */
default List<String> getReplyTo() { return Collections.emptyList(); }
```
**`MailContentImpl` — add the field** (Lombok generates the getter; `@Builder.Default` keeps it non-null):
```java
@Builder.Default
private List<String> replyTo = new ArrayList<>();
```
**`SesEmailServiceImpl` — map it in the non-templated `sendEmail(from,to,cc,bcc,content)`** (the request-build site at **L120** — **not** the legacy template path at L371):
```java
SendEmailRequest.Builder req = SendEmailRequest.builder()
    .fromEmailAddress(from)
    .destination(buildDestination(to, cc, bcc))
    .content(buildEmailContent(content));
List<String> replyTo = content.getReplyTo();
if (replyTo != null && !replyTo.isEmpty()) {
    req.replyToAddresses(replyTo);   // SES v2 SendEmailRequest supports replyToAddresses
}
SendEmailResponse response = sesClient.sendEmail(req.build());
```
> **F6 (precision):** there are two `SendEmailRequest.builder()` sites — the non-templated one at **L120** (scoped here) and the legacy template path at **L371**. The newer `sendTemplatedEmail(...)` (L157) routes through this `sendEmail(...)` and so **inherits reply-to for free**; the legacy `sendTemplateEmail(...)` (L231) keeps its own template-var reply-to and is **untouched**. (Beware the two near-identical names `sendTemplatedEmail` vs `sendTemplateEmail`.)
> **F7 (preserve error handling):** the snippet elides the wrapper for brevity — the real method wraps the send in the existing `try/catch` mapping `SdkClientException`/`SdkServiceException`/`Exception` → `SendEmailException` (L119-137). **Keep that try/catch**; only the `.replyToAddresses(...)` line and the `req` builder variable are new (same instruction as §3.4 for S-G2).

### 6.3 Backward-compat — zero risk
`getReplyTo()` is a `default` returning empty → every existing `MailContent` implementor is unaffected; SES adds the header only when non-empty. No change to any `EmailService` method signature.

### 6.4 Tests
1. `MailContentImpl` default → `getReplyTo()` empty; `SendEmailRequest` built with **no** `replyToAddresses`.
2. `MailContentImpl` with `replyTo=[a@x, b@y]` → captured `SendEmailRequest.replyToAddresses()` == list.
3. Interface default: a bare `MailContent` anonymous impl (no `replyTo`) compiles and yields empty.
4. Regression: existing `SesEmailServiceImplTest` send paths unchanged.

## 6b. X-G10 — `EmailService` first-class attachment support (raw MIME) *(REQUIRED — confirmed absent)*

> **Origin:** mercury-services `visibility/docs/2026-07-16-ION-12316-inbound-ses-startup-issue.md` §12. During the ION-12316 SES/AWS-SDK-skew fix, `visibility-inbound` had to keep a **direct `SesV2Client`** (with a `TODO`) purely because the cloud-sdk wrapper cannot carry the CSV error-report attachment.

### 6b.1 Verified current defect
`MailContent` already models attachments — `List<Attachment> getAttachments()` with `Attachment{getFilename(), getContent(), getContentType()}` (impl `MailContentImpl.AttachmentImpl`). **But `SesEmailServiceImpl.buildEmailContent(MailContent)` builds only a `simple` `Message` (subject + html/text `Body`) and never reads `getAttachments()`** (verified). So any attachment-bearing mail cannot go through `EmailService.sendEmail(...)`; visibility-inbound therefore bypasses the wrapper with a raw `SesV2Client`. The library already owns the MIME machinery (`EmailMimeUtils` on `javax.mail` + `RawMessage` + `EmailContent.raw(...)`) — but it is wired only into the **template** path (`sendTemplateEmail`), not `sendEmail(MailContent)`.

### 6b.2 Consumers
| Module | Use case | Effect |
|---|---|---|
| **visibility-inbound** (primary, ION-12316) | CSV `INTTRA_CE_ERROR_*.csv` error report as `text/csv` attachment | replace direct `SesV2Client` with injected `EmailService` |
| **appianway email-sender** | any report/attachment mail (also uses X-G7 reply-to) | one wrapper path for reply-to + attachments |
| booking / auth / network | attachment-less mail | **unchanged** (stay on the simple path) |

### 6b.3 Design (additive; `MailContent` API unchanged)
**a) `cloud-sdk-aws` `EmailMimeUtils` — add a `MailContent`-driven overload** producing the correct `multipart/mixed > (multipart/alternative[text, html]) + attachments` layout (attachments directly under `mixed`, not `alternative`):
```java
public static MimeMessage createMimeMessage(String from, List<String> to, List<String> cc, List<String> bcc,
                                            MailContent content) throws MessagingException {
    // from/to/cc/bcc + subject; multipart/mixed wrapping a multipart/alternative(text,html);
    // each MailContent.Attachment -> MimeBodyPart(ByteArrayDataSource(content, contentType|application/octet-stream),
    //   setFileName, setDisposition(ATTACHMENT)) added directly under multipart/mixed. saveChanges().
}
```
> Keep `javax.mail`/`javax.activation` for consistency with the existing `EmailMimeUtils` (do **not** mix `jakarta.mail`). Reuse its existing reply-to handling if present so raw sends can also carry reply-to.

**b) `cloud-sdk-aws` `SesEmailServiceImpl.sendEmail(from,to,cc,bcc,content)` — branch on attachments** (composes with X-G7 reply-to on the same request):
```java
boolean hasAttachments = content.getAttachments() != null && !content.getAttachments().isEmpty();
EmailContent emailContent = hasAttachments
    ? buildRawEmailContent(from, to, cc, bcc, content)   // NEW raw MIME path
    : buildEmailContent(content);                        // EXISTING simple path (unchanged)

SendEmailRequest.Builder req = SendEmailRequest.builder()
    .fromEmailAddress(from)
    .destination(buildDestination(to, cc, bcc))          // SESv2 derives recipients from MIME too; keep explicit for cc/bcc + event tracking
    .content(emailContent);
List<String> replyTo = content.getReplyTo();               // X-G7
if (replyTo != null && !replyTo.isEmpty()) req.replyToAddresses(replyTo);
sesClient.sendEmail(req.build());
```
```java
private EmailContent buildRawEmailContent(String from, List<String> to, List<String> cc, List<String> bcc,
                                          MailContent content) {
    try {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        EmailMimeUtils.createMimeMessage(from, to, cc, bcc, content).writeTo(out);
        return EmailContent.builder()
            .raw(RawMessage.builder().data(SdkBytes.fromByteArray(out.toByteArray())).build())
            .build();
    } catch (MessagingException | IOException e) {
        throw new SendEmailException("Failed to build raw MIME email", e);
    }
}
```
**c) `cloud-sdk-api` (optional convenience, non-breaking):** add `MailContentImpl.MailContentImplBuilder` helper `addAttachment(String filename, byte[] content, String contentType)` for terse call sites. No interface signature change.

> **F8 (recipient source):** the raw path sets **both** the explicit `.destination(buildDestination(to,cc,bcc))` (envelope) **and** the MIME `To/Cc/Bcc` headers (via `createMimeMessage(from,to,cc,bcc,content)`). They **cannot diverge by construction** — both derive from the same `to/cc/bcc` args — so there is no double-send today; the explicit `Destination` is kept for the cc/bcc envelope + SES event tracking (as the template raw path already does). A test (§6b.5 #6) asserts they agree, guarding against a future refactor that lets them drift.

### 6b.4 Backward-compatibility — zero risk
- **New `EmailMimeUtils` overload, existing template path untouched:** X-G10 adds `createMimeMessage(from,to,cc,bcc,MailContent)` — the existing `createMimeMessage(EmailRequest, vars)` used by the **template** path is not modified. **booking** sends all mail via `sendTemplateEmail(...)` (its `IsIncludeHTMLAttachment` is a template var handled by that untouched method) → **fully unaffected**.
- **Simple path unchanged:** with no attachments `sendEmail(MailContent)` takes the existing `buildEmailContent(...)` → `EmailContent.simple(...)` branch byte-for-byte; `raw()` stays null. **auth**'s `SimpleMailContent.getAttachments()` returns `emptyList()` → identical behavior; network sends attachment-less mail.
- **New behavior is opt-in** via a populated `getAttachments()` — a path no existing mercury-services caller exercises (only visibility-inbound will, replacing its direct `SesV2Client`).
- Existing exception mapping (`SdkClientException`/`SdkServiceException` → `SendEmailException`) reused.

### 6b.5 Tests (cloud-sdk-aws; 100% of new code)
1. `sendEmail` with one attachment → captured `SendEmailRequest.content().raw() != null`; raw MIME contains the filename, declared content-type, and `Content-Disposition: attachment`.
2. `sendEmail` with **no** attachment → `content().simple() != null` and `raw() == null` (backward-compat proof).
3. cc/bcc propagation in both paths; multiple attachments; null/blank content-type → `application/octet-stream`.
4. Attachment + reply-to together → raw content **and** `replyToAddresses` set (X-G7×X-G10 composition).
5. Mirror existing `SesEmailServiceImplTest` conventions (AssertJ, `@Nested`, `ArgumentCaptor<SendEmailRequest>`).
6. **F8 — recipient-source agreement:** assert the raw MIME `To/Cc/Bcc` headers and the explicit `Destination` carry the **same** addresses (both derive from the same `to/cc/bcc`, so they agree by construction; the test guards against future drift).

### 6b.6 Downstream follow-up (after the library lands — not part of the SDK change)
- **visibility-inbound:** replace the direct `SesV2Client` in `EmailSender` with an injected `EmailService` (module like booking's `BookingEmailSenderModule`), build the report as `MailContentImpl` + `AttachmentImpl(csvBytes, "text/csv")`, delete the `TODO`; this also corrects the pre-existing MIME quirk (attachment nested under `alternative`) by using the `mixed` layout. Removes the module's last direct AWS SDK usage.
- **appianway email-sender:** send reply-to + any attachments through the one `EmailService` path (X-G7 + X-G10).

> **Related but out of scope for this request (flagged for a separate decision):** ION-12316 §11 also proposes a **null-safe profile-file supplier** (`SafeProfileFile`) in `ParameterStoreClientFactory`/all cloud-sdk-aws client factories, so an AWS-SDK BOM bump can't reintroduce the ECS startup NPE (null `user.home`). That is a **commons/cloud-sdk-aws resilience** item (SSM/profile-file), **not** an email gap — but it is relevant to appianway too (all 14 apps boot via commons `ParameterStoreLookup`→SSM). Recommend tracking it as a separate additive hardening; not designed here.

---

## 7. X-G8 (no change) & C-G6 (optional)

### 7.1 X-G8 — Jest/OpenSearch signing — **NO library change (corrected)**
**Correction (2026-07-23):** the earlier note about a "v2 interceptor" was wrong. Verified against live source:
- **appianway ingestor** `JestModule` signs with **`vc.inreach.aws.request.AWSSigner`** built from a **v1** `com.amazonaws.auth.DefaultAWSCredentialsProviderChain`, wrapped in `AWSSigningRequestInterceptor` and added to the `JestClientFactory` HTTP client. This is the **AWS SDK v1** signing path.
- **mercury-services** `cloud-sdk-api/.../elasticsearch/JestClientBuilder.java` likewise takes a caller-supplied `vc.inreach.aws.request.AWSSigningRequestInterceptor`. The already-upgraded **booking / visibility / webbl** Jest usage is compatible with the **`vc.inreach` 1.x signer only**.

Therefore ingestor stays on the **`vc.inreach` 1.x signer** — the same one mercury-services uses — and there is **no cloud-sdk change** and **no v2 signing migration** here. The Jest/`io.searchbox` client + `vc.inreach` interceptor is orthogonal to the AWS SDK v1→v2 flip (Elasticsearch/OpenSearch is reached over signed HTTP, not the AWS SDK service client). Action: none in cloud-sdk; ingestor keeps its local `JestModule`. (OpenSearch-SDK migration, if ever pursued, is a separate future workstream, not part of this program.)

### 7.2 C-G6 — widen commons `getConfigTransformer` *(OPTIONAL — no breakage confirmed)*
Verified: `commons/.../config/ConfigProcessingServerCommand.java` has `private ConfigurationSourceProvider getConfigTransformer(...)` composing `TrimConfigCommentsTransform.andThen(ParameterStoreConfigTransform)`. appianway already **composes** the public transforms in its own command (the proven pattern), so this is not required.

**No-breakage confirmation (Q3):** `private`→`protected` on `getConfigTransformer` **strictly relaxes access** — it introduces no new abstract method, changes no signature/return type, and cannot affect any existing caller (the method is invoked only from this class's own `run(...)`). No subclass in mercury-services or appianway currently declares a same-named method (nothing to accidentally override/shadow). It is **binary- and source-compatible**; **safe to widen**. If elected purely for override ergonomics:
```java
protected ConfigurationSourceProvider getConfigTransformer(ConfigurationSourceProvider configProvider) { … }
```
**Recommendation:** widening is safe; adopt it **together with §7.3** (so appianway can override the chain to prepend its property-substitution transform) — otherwise skip in favour of composition.

### 7.3 Multi-`.properties` substitution → commons *(APPROVED — decision 2026-07-23, additive — Q4)*

> **Decision (2026-07-23):** the reviewer has **approved** lifting the appianway property substitution into commons as suggested. It is now a **planned, in-scope additive contribution** (own branch, after the four required gaps land), adopted **together with C-G6** so appianway overrides the transform chain rather than composing a separate command. This replaces appianway's bespoke config classes and benefits future DW5 adopters.

**What it is (appianway `shared`, verified source).** appianway resolves `${key}` placeholders in the classpath YAML from **multiple `.properties` files + OS env**, via two classes:
- `shared/.../config/lookup/VariableLookupProvider` — concatenates all supplied `.properties` into a `java.util.Properties`, wraps a **`FirstMatchStrLookup`** with priority order **env → properties** (Apache commons-text `StrLookup`), self-substitutes `${key}` *within* the properties (so props can reference each other), and **validates** that every referenced variable resolves (throws if a `${key}` has no value and no `${key:-default}`).
- `shared/.../config/lookup/ProcessedConfigProvider` — a Dropwizard **`ConfigurationSourceProvider`** decorator whose `open(path)` reads the YAML, runs a commons-text **`StrSubstitutor`** with that lookup to replace every `${placeholder}`/`${key:-default}`, validates, and returns the substituted stream.

**Why commons doesn't do this today.** commons' `ConfigProcessingServerCommand` chains only `TrimConfigCommentsTransform` → `ParameterStoreConfigTransform` (`${awsps:/path}` → SSM at boot). It has **no** multi-`.properties` `${key}` substitution. So appianway must place the property-substitution transform **first** in the chain:
```
YAML → [property-substitution ${key} from .properties+env] → TrimConfigCommentsTransform → ParameterStoreConfigTransform (${awsps:} → SSM)
```

**The good-to-have (additive, zero risk).** Lift `VariableLookupProvider` + `ProcessedConfigProvider` into **commons** as a reusable, standalone `ConfigurationSourceProvider` decorator (suggested name `PropertiesSubstitutionConfigProvider` / `MultiPropertiesConfigTransform`), so it can be chained by **any** DW5 app (appianway modules today; oceanschedules-style mercury apps tomorrow) instead of being copy-pasted:
```java
// commons (new class, nothing references it until adopted → strictly additive)
public final class PropertiesSubstitutionConfigProvider implements ConfigurationSourceProvider { … }
```
- **Backward-compat:** brand-new class(es); no existing commons type or behavior changes. Zero risk.
- **Dependency note:** it uses `org.apache.commons.text` (`StrSubstitutor`/`StrLookup`), already on the mercury-services line — confirm it is a `commons` compile dependency (add if absent; commons-text is benign and already transitively present via Dropwizard).
- **Pairs with C-G6:** with `getConfigTransformer` `protected`, an app subclasses `ConfigProcessingServerCommand` and overrides the chain to prepend this provider — cleaner than a separate command. **(F9 — verified in this workspace: `ChainingConfigTransformer`, `ParameterStoreConfigTransform`, `TrimConfigCommentsTransform` are all `public` in commons, so a subclass can reference/compose them.)**
- **Recommendation:** **APPROVED (2026-07-23)** — do it as a small, isolated commons contribution (own branch), *after* the four required gaps land; adopt **with C-G6**. It removes appianway's last bespoke config class and benefits future DW5 adopters.

**Tests:** `${key}` resolved from properties; env overrides property (first-match order); `${key:-default}` fallback; **unresolved `${key}` throws** (validation parity with `shared`); chain order (property-subst before `${awsps:}`) leaves `${awsps:}` for the Parameter Store transform.

### 7.4 X-G11 — null-safe SSM profile-file supplier *(RECOMMENDED hardening, additive — Q8)*

> **Origin:** ION-12316 §11. The visibility-inbound ECS startup NPE (`ProfileFile.java:314`, null `Path`) happened while **building the SSM client during commons config processing** — `ParameterStoreClientFactory` → `ParameterStoreLookup` → `ConfigProcessingServerCommand.getConfigTransformer`. Root cause was AWS-SDK **version skew** (fixed in visibility), but the *latent* fragility remains: a future uniform BOM bump (e.g. to 2.42.x, whose default `ProfileFileSupplier` produced the null path) could reintroduce the NPE on any container with no `user.home`. This affects **appianway too** — all 14 apps boot via the same commons `ParameterStoreLookup`→SSM path.

#### 7.4.1 Verified current state
`ParameterStoreClientFactory.createParameterStore(config)` builds the `SsmClient` with `region`, `endpointOverride`, `credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())`, and `apiCallTimeout` — it sets **no** profile-file supplier, so it relies on the SDK's **global default** `ProfileFileSupplier`, the exact component that returned a null path under skew.

#### 7.4.2 Design (additive, zero-behavior-change)
New shared helper in cloud-sdk-aws (e.g. `com.inttra.mercury.cloudsdk.aws.config.SafeProfileFile`) that **loads `~/.aws/config` + `~/.aws/credentials` when the location is resolvable (local dev), and returns an empty `ProfileFile` when it is not (ECS, no `user.home`)** — so client construction never NPEs:
```java
public final class SafeProfileFile {
    public static ProfileFileSupplier supplier() { return SafeProfileFile::load; }
    private static ProfileFile load() {
        ProfileFile.Aggregator agg = ProfileFile.aggregator();
        addIfReadable(agg, ProfileFile.Type.CONFIGURATION, safe(ProfileFileLocation::configurationFileLocation));
        addIfReadable(agg, ProfileFile.Type.CREDENTIALS,   safe(ProfileFileLocation::credentialsFileLocation));
        return agg.build();  // empty when nothing resolvable -> no NPE
    }
    private static Optional<Path> safe(Supplier<Optional<Path>> loc) {
        try { return loc.get(); } catch (RuntimeException e) { return Optional.empty(); }
    }
    private static void addIfReadable(ProfileFile.Aggregator agg, ProfileFile.Type type, Optional<Path> p) {
        p.filter(Files::isReadable).ifPresent(x -> agg.addFile(ProfileFile.builder().content(x).type(type).build()));
    }
}
```
`ParameterStoreClientFactory` then adds **only** the supplier to the override config — **credentials and region stay exactly as today**:
```java
SsmClient ssmClient = SsmClient.builder()
    .region(config.getRegion().getRegionDelegate())
    .endpointOverride(config.getEndpointOverride())
    .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())   // UNCHANGED
    .overrideConfiguration(b -> b
        .apiCallTimeout(config.getClientExecutionTimeout())
        .defaultProfileFileSupplier(SafeProfileFile.supplier()))   // NEW: add ONLY the null-safe supplier
    .build();
```
> Confirm the exact `ProfileFileLocation` accessor names and `ClientOverrideConfiguration.Builder.defaultProfileFileSupplier(...)` signature against the pinned AWS SDK v2 version at implementation time.
> **F1 (must):** do **NOT** add `.defaultProfileName("default")`. The factory sets no profile name today, so the SDK honours `AWS_PROFILE`/`aws.profile` (falling back to `"default"`); pinning `"default"` would **suppress `AWS_PROFILE`** and change a runtime default — a §0 violation. Add only the supplier, which is all the resilience goal requires.

#### 7.4.3 Risk analysis — **no impact to already-upgraded mercury-services apps**
The change is deliberately scoped so **nothing but null-safety changes**: region and the **explicit `config.getCredentialsProvider()`** are preserved (we do **not** switch to `DefaultCredentialsProvider`), so credential resolution is byte-identical, and **no `defaultProfileName` is set** so `AWS_PROFILE`/`aws.profile` resolution is preserved (F1). Only the default profile-file supplier is replaced — and it yields equivalent `ProfileFile` content:

| Environment | Today (uniform 2.30.24) | After X-G11 | Delta |
|---|---|---|---|
| **Local dev** (`user.home` present, `~/.aws` readable) | SDK default loads `~/.aws/config`+`credentials` | `SafeProfileFile` loads the same `~/.aws/config`+`credentials` | none |
| **ECS** (no `user.home`/`HOME`) | SDK default resolves an **empty** `ProfileFile` (works today) | `SafeProfileFile` resolves an **empty** `ProfileFile` | none (but **NPE-proof** vs a future BOM that would otherwise return a null path) |

Upgraded apps (booking, visibility, auth, network, booking-bridge, registration, tx-tracking) already boot cleanly on 2.30.24; after X-G11 they produce the **same** ProfileFile content in both environments — **no behavior change**, only removal of a latent boot NPE. Strictly additive (new helper class + one override-config line).

#### 7.4.4 Scope
- **Primary (recommended):** `ParameterStoreClientFactory` — the boot-critical SSM client that builds during commons config processing (before the injector). This is where the crash occurs.
- **Optional defense-in-depth:** apply `SafeProfileFile.supplier()` in the other cloud-sdk-aws client factories (SES/SESv2, S3, SQS, SNS, DynamoDB, STS) via the same helper, so the whole library is uniformly resilient before any BOM bump. Same zero-risk argument; these build after startup so are lower priority.
- **Complementary (build-time guard, not code):** an app-parent `maven-enforcer` `dependencyConvergence`/`requireUpperBoundDeps` rule + AWS BOM import prevents a future divergent aws-sdk pin (would have failed the ION-12316 `ses:2.42.28` skew at build time).

#### 7.4.5 Tests (cloud-sdk-aws)
- **Null-home (ECS) reproduction:** clear `user.home` (restore after) and build the SSM client → **no exception** with `SafeProfileFile` (and demonstrate the NPE/skew mode without it).
- **`AWS_PROFILE` honoured (F1):** set `AWS_PROFILE` (env) / `aws.profile` and assert the built client still resolves that profile — i.e. we did **not** pin `defaultProfileName("default")`.
- **Local (profile present):** point at a temp dir with `config`/`credentials` (via `AWS_CONFIG_FILE`/`AWS_SHARED_CREDENTIALS_FILE` or test override) → loaded `ProfileFile` contains the expected profile (local auth preserved).
- **Unresolvable location:** `safe(...)` swallows a throwing locator → empty `ProfileFile`, no NPE.
- Existing `ParameterStoreLookupTest` stays green; assert region + the configured credentials provider are still used (no credential-provider swap).


---

## 8. Wire-compatibility gate — JSON round-trip corpus test *(REQUIRED, gates the pilot)*

A dedicated cloud-sdk-api test (`WorkflowWireCompatTest`) that locks the ETL wire contract:
- **Corpus (F3 — must be real `shared`-produced bytes):** seed the fixtures with **actual JSON emitted by appianway `shared`/event-writer** (e.g. real S3 event-store archive bytes), **not** cloud-sdk-generated strings. A self-referential cloud-sdk↔cloud-sdk round-trip proves only internal self-consistency — it would **pass even if `shared` emits a different outer-key casing** (the `annotations` wrapper field has **no** `@JsonProperty`, and `@JsonIgnoreProperties(ignoreUnknown=true)` would silently drop a mismatched key). Include at least one `Event` carrying `annotations` and payloads exercising the new `Projection`/`Token` keys.
- **Assertions:**
  0. **Cross-library parity (F3):** cloud-sdk `Event.parseJson(realSharedBytes)` retains annotations (**non-null and inner list non-empty**, per F4) and `toJsonString()` re-emits keys **identical to the `shared` fixture** — proving cross-library agreement, not just self-round-trip.
  1. `Event.parseJson(x).toJsonString()` is byte-stable (modulo key order) — **with** and **without** annotations (guards W-G9.1).
  2. `MetaData.parseJson(x).toJsonString()` byte-stable, projections preserved (incl. the 6 new keys).
  3. Date-time pattern `yyyy-MM-dd HH:mm:ss.SS` preserved on all three `Event` timestamps and `MetaData.timestamp` (already identical to `shared`).
  4. `Annotations` `@JsonProperty("Annotations")` wrapper + `Annotation` `@JsonInclude(NON_NULL)`/`@JsonCreator` shape preserved.
- This test **must stay green** through the entire appianway rollout and gates the event-writer pilot.

---

## 9. DynamoDB — table creation & the `DynamoDbAdminCommand` (Q5)

### 9.1 No DynamoDB **SDK** change is required
The appianway modules that touch DynamoDB (**transformer** control-number sequence; the **watermill** consumers' offset tables) use the **native AWS v2 enhanced client** (`@DynamoDbVersionAttribute`, `DynamoRepositoryConfig`) already provided by `cloud-sdk-aws` — the same annotation mercury-services booking `SequenceId` uses. **No DynamoDB interface, mapping, attribute name, or repository behavior in cloud-sdk is modified by this program.** No DynamoDB wire/schema change exists to cover.

### 9.2 How appianway creates tables **today** (verified)
Each DynamoDB-footprint module ships its **own** Dropwizard command using **AWS SDK v1**:
- `transformer/.../command/DynamoTableCommand extends ConfigProcessingServerCommand` (command name **`create-table`**) — builds a v1 `com.amazonaws.services.dynamodbv2.model.CreateTableRequest` (single `HASH` key `keyId`, provisioned 10/10) and calls `TableUtils.waitUntilActive`.
- `watermill/{cargoscreen,itv-gps,…}-consumer/.../dynamodb/command/DynamoTableCommand` — analogous v1 commands for the per-consumer offset tables.

This is exactly the **old 1.x "DW command" pattern** the reviewer recalls booking/network using before the upgrade.

### 9.3 The v2 target already exists in cloud-sdk — `DynamoDbAdminCommand`
`cloud-sdk-aws/.../database/command/DynamoDbAdminCommand` is a Dropwizard `ConfiguredCommand` (command name **`dynamo-create`**) that derives the table (key schema, attribute defs, GSIs, TTL, Streams, PAY_PER_REQUEST/PROVISIONED) from **entity classes** via `EntityTableMetadata.fromEntityClass(...)`, creates it if absent, waits for ACTIVE, and adds missing GSIs. It exposes a `protected DynamoDbClientConfig resolveClientConfig(T config)` override hook. mercury-services already adopted it — e.g. `visibility-inbound` subclasses it:
```java
public class VisibilityInboundDynamoDbAdminCommand extends DynamoDbAdminCommand<VisibilityInboundApplicationConfig> { … }
// registered:  bootstrap … .command(new VisibilityInboundDynamoDbAdminCommand())
// run:         java -jar visibility-inbound-1.0.jar dynamo-create <config>.yaml
```
and covers it with a DynamoDB-Local integration test (`VisibilityInboundDynamoDbAdminCommandIT`).

### 9.4 Recommendation for appianway DynamoDB-footprint modules
**Yes — replace each module-local v1 `DynamoTableCommand` with a thin subclass of `DynamoDbAdminCommand`**, exactly as visibility/booking did. This is an **appianway-side adoption, not an SDK change** (the command already exists). Per module:
1. Annotate the module's entity/domain class (e.g. transformer's control-number sequence record; each consumer's offset record) with the cloud-sdk enhanced-DynamoDB metadata that `EntityTableMetadata` reads (partition/sort key, optional GSI/TTL/stream, billing mode; add `@DynamoDbVersionAttribute` where optimistic lock is needed — transformer).
2. Subclass `DynamoDbAdminCommand<TConfig>` with the entity list and a `resolveClientConfig(...)` mapping the module config (region, endpoint override, table prefix).
3. Register it in the app's `initialize(...)` via `bootstrap...command(new <Module>DynamoDbAdminCommand())`; invoke as `dynamo-create <config>.yaml` (drop the old `create-table`).
4. Delete the v1 `DynamoTableCommand` and its `com.amazonaws.*` imports.

**Coverage check:** the appianway tables are simple (transformer = single `HASH` `keyId`; consumer offsets = single-key), all comfortably expressible via `EntityTableMetadata` (which additionally supports GSI/TTL/Streams/on-demand). **No SDK gap** is anticipated. *If* a future appianway table needs a feature `EntityTableMetadata` cannot express, that would be a separate, **additive** enhancement to `EntityTableMetadata`/`DynamoDbAdminCommand` — none is required for the tables in scope.

### 9.5 DynamoDB integration tests
Because the table-creation logic being adopted is the **existing** cloud-sdk `DynamoDbAdminCommand` (already covered by `DynamoDbAdminCommandTest` + downstream `...DynamoDbAdminCommandIT` against DynamoDB Local), **no new cloud-sdk DynamoDB integration test is required for these gaps**. The appianway modules that adopt it should add their **own** DynamoDB-Local integration test per the mercury-services pattern (subclass boots `dynamo-create` against embedded DynamoDB and asserts the table/GSI/version-attribute), using the `dynamo-integration-test` framework. Existing mercury-services DynamoDB integration tests remain the regression guard and must stay green.

---

## 10. Rollout & verification order

```mermaid
flowchart LR
  A[Land S-G2 + W-G9.1 + W-G9.2 + X-G7 + X-G10\n api + aws] --> B[cloud-sdk CI green]
  B --> C[upgraded consumer modules green\n mvn -pl … -am (no reactor) vs 1.0.27-SNAPSHOT]
  C --> D[WorkflowWireCompatTest green\n gates event-writer pilot]
  D --> E[appianway consumes 1.0.27-SNAPSHOT\n event-writer pilot -> rest]
  F[C-G6 optional / X-G8 verify-only] -. only if elected .-> E
```

1. **One feature branch per gap** (S-G2, W-G9.1+W-G9.2 together as "workflow-model parity", X-G7, X-G10). C-G6 + config-substitution separate.
2. Land in `cloud-sdk-api`/`cloud-sdk-aws`; run cloud-sdk CI **and** the **scoped upgraded-consumer build** (`mvn -pl network,auth,registration,self-service-reports,tx-tracking,booking,visibility,webbl,booking-bridge,db-migration -am verify`, **no reactor build**) against `1.0.27-SNAPSHOT` — green before/after each commit.
3. `WorkflowWireCompatTest` green → unblocks the event-writer pilot.
4. appianway per-module rollout proceeds per the foundation §8 order.

### Per-change file map
| Gap | Files |
|---|---|
| S-G2 | `cloud-sdk-api/…/storage/api/StorageClient.java`; `cloud-sdk-aws/…/storage/impl/S3StorageClient.java` (+ tests) |
| W-G9.1 | `cloud-sdk-api/…/notification/workflow/Event.java` (+ tests) |
| W-G9.2 | `cloud-sdk-api/…/notification/workflow/MetaData.java`, `…/workflow/Event.java` (+ tests) |
| X-G7 | `cloud-sdk-api/…/email/api/MailContent.java`; `cloud-sdk-aws/…/email/impl/MailContentImpl.java`, `…/email/impl/SesEmailServiceImpl.java` (+ tests) |
| X-G10 | `cloud-sdk-aws/…/email/utils/EmailMimeUtils.java`, `…/email/impl/SesEmailServiceImpl.java` (+ optional `MailContentImpl` helper) (+ tests) |
| C-G6 (opt) | `commons/…/config/ConfigProcessingServerCommand.java` |

---

## 11. Risk register

| Risk | Likelihood | Mitigation |
|---|:---:|---|
| A new S-G2 `default` collides with an existing external 5-/6-arg overload | Very low | Verified none exist; overload signatures are distinct |
| `copyObject(...REPLACE)` alters the no-metadata copy path | Low | New behavior only in the new 6-arg overload; 4-arg copy untouched (default `COPY`) |
| Accidentally adding an `abstract` (non-`default`) interface method | Low | Review checklist: every new interface method MUST be `default`; CI compat check vs. a bare stub impl |
| W-G9.1 changes serialization order/format | Low | Field/annotations/`@JsonInclude` unchanged; corpus test asserts byte-stability |
| Constant typo splits a `Map` key across services | Low | Parameterized value-assertion test over every new constant |
| X-G7 alters existing send behavior | Low | Reply-to applied only when non-empty; existing SES tests regression-gated |
| X-G10 raw-MIME branch alters attachment-less sends | Low | Branch fires only when `getAttachments()` non-empty; simple path byte-for-byte unchanged; captured-request regression test asserts `raw()==null` for no-attachment sends |
| `-SNAPSHOT` instability | Medium | Same line mercury-services already runs; pin a release at GA |
| **Any** cloud-sdk change breaking mercury-services | — | Additive-only contract (§0) + cloud-sdk CI + scoped upgraded-consumer build green gate (§0/§10, no reactor) |

---

## 12. Implementation checklist (TDD, 100% coverage of new code)

- [ ] **S-G2** — 3 `default` methods on `StorageClient`; 3 overrides on `S3StorageClient` (+`MetadataDirective` import); unit tests (put+meta/ct, stream put, copy REPLACE, null-handling, regression, compat-stub); optional S3 round-trip integration test.
- [ ] **W-G9.1** — `Event.Builder` `annotations` field + `setAnnotations` + copy in `Builder(Event)`; assign in `Event(Builder)` ctor; unit + parse-drop-guard (**assert inner `List<Annotation>` non-empty & equal — F4**) + round-trip tests.
- [ ] **W-G9.2** — 6 `MetaData.Projection` + 9 `Event.Token` constants (exact values §5.1); value-assertion + key-round-trip tests.
- [ ] **X-G7** — `MailContent.getReplyTo()` default; `MailContentImpl.replyTo`; `SesEmailServiceImpl` `.replyToAddresses(...)` when non-empty **at the L120 non-templated site, preserving the existing try/catch (F6/F7)**; unit tests (default empty, populated, interface-default, regression).
- [ ] **X-G10** — `EmailMimeUtils.createMimeMessage(from,to,cc,bcc,MailContent)` (multipart/mixed + attachments); `SesEmailServiceImpl.sendEmail` branch to raw MIME when attachments present (simple path unchanged); optional `MailContentImpl` `addAttachment(...)`; unit tests (attachment→raw, no-attachment→simple, cc/bcc, multi-attachment, attachment+reply-to, **recipient-source agreement — F8**).
- [ ] **WorkflowWireCompatTest** — corpus seeded with **real `shared`-produced JSON fixtures (F3)**, incl. annotations + new keys; cross-library parity assertion (parse retains inner annotations, re-emit matches the `shared` bytes) + byte-stable round-trips; green gate.
- [ ] **C-G6** *(APPROVED with §7.3)* — widen `getConfigTransformer` to `protected` (safe; adopt with the config-substitution contribution).
- [ ] **Config substitution** *(APPROVED 2026-07-23, §7.3)* — lift `VariableLookupProvider` + `ProcessedConfigProvider` into commons as `PropertiesSubstitutionConfigProvider` (additive); tests for first-match order, defaults, unresolved-throws, chain order.
- [ ] **DynamoDB adoption** *(appianway-side, §9 — not an SDK change)* — replace each module-local v1 `DynamoTableCommand` with a `DynamoDbAdminCommand` subclass + annotated entity + `resolveClientConfig`; add per-module DynamoDB-Local integration test.
- [ ] **X-G8** *(no change)* — ingestor keeps the `vc.inreach` 1.x Jest signer; confirm no cloud-sdk edit.
- [ ] **X-G11** *(**DEFERRED** — separate later `1.0.29-SNAPSHOT` effort, **NOT in the `1.0.28` landing**; do only after appianway consumes `1.0.28`; §7.4/§13.3; F2)* — `SafeProfileFile` helper + `ParameterStoreClientFactory.defaultProfileFileSupplier(...)` **only (NO `defaultProfileName` — F1)**; credentials/region unchanged; optional extension to other client factories; tests (null-home no-NPE, **`AWS_PROFILE`-set honoured — F1/F2**, local profile loaded, unresolvable→empty).
- [ ] **Gate** — cloud-sdk CI green; **scoped upgraded-consumer build** green vs `1.0.27-SNAPSHOT` before/after (`mvn -pl network,auth,registration,self-service-reports,tx-tracking,booking,visibility,webbl,booking-bridge,db-migration -am verify` — **no reactor build**); existing DynamoDB integration tests green.

---

## 13. Delivery process — branching, versioning, commits & README rollover *(instructions)*

> Context: the feature branch **`feature/ION-12310-commons-cloudsdk-refactoring`** carries all AWS-upgrade cloud-sdk/api changes, is **already rebased onto `develop`** (← **no further rebase is part of this gap work**), and publishes the **`1.0.N-SNAPSHOT`** line consumed by ~80% of mercury-services apps (current tip **`1.0.27-SNAPSHOT`**). All the gaps in this document must ultimately land on that feature branch. These instructions follow the repeatable conventions in [2026-07-17-rebase-with-develop-owasp-jackson.md](2026-07-17-rebase-with-develop-owasp-jackson.md) §15 (the §15.1 README rollover applies; §15.2 rebase hygiene applies **only if** a separate rebase is later required — not now).

### 13.1 Confirmed workflow (2026-07-23)

> **This is the agreed process — land the `1.0.28` set first, X-G11 deferred, no rebase of the feature branch.**
> 0. **FIRST, before any work:** take a full **backup of the current feature branch** and **push it to origin** (planned — not optional) —
>    ```
>    git branch backup/feature-ION-12310-pre-sdk-gaps-2026-07-23 feature/ION-12310-commons-cloudsdk-refactoring
>    git push origin backup/feature-ION-12310-pre-sdk-gaps-2026-07-23   # PLANNED: off-machine safety copy on origin
>    ```
>    Create it locally **and push to origin**; keep the remote backup until the `1.0.28` set is merged, published as `1.0.28-SNAPSHOT`, and verified good.
> 1. Cut **`feature/ION-12310-<gap>`** from the **current `feature/ION-12310-commons-cloudsdk-refactoring` tip**.
> 2. Implement + test the gap in isolation. The **agent may make multiple commits** on the gap branch during development.
> 3. When green (incl. the scoped consumer gate, §0), **squash-merge into the main feature branch as ONE commit per gap**.
> 4. The main feature branch gains **~5 new commits** for the `1.0.28` set (S-G2, W-G9, X-G7, X-G10, C-G6+config), one per gap (§13.3).
> 5. **ONE version bump → `1.0.28-SNAPSHOT`** for this set; the `### Commons v1.0.28-SNAPSHOT` README heading lists the **five** set gaps' notes (§13.5). **X-G11 is NOT part of this landing** — it is a **separate later effort** bumped to `1.0.29-SNAPSHOT`, done **after** the `1.0.28` set is rolled out to appianway (§13.2/§13.3).
> 6. **No rebase** of the feature branch onto `develop` happens in this work; each squash-merge simply adds a normal commit on top of the tip → an **ordinary `git push`** (no `--force`).

| Question | Answer |
|---|---|
| **Copy the feature branch per gap, then merge back?** | **Yes.** Cut `feature/ION-12310-<gap>` (`-sg2`, `-wg9`, `-xg7`, `-xg10`, `-config`; **`-xg11` later, separately**) from the current tip, develop + test in isolation (multi-commit OK), then **squash-merge back when green**. Never commit unverified work directly on the shared feature branch. |
| **Multiple commits or one on the feature branch?** | **One squashed commit per gap** → **~5 commits** for the `1.0.28` set on the main feature branch, each isolated and revertible (mirrors the single-commit revert you use in client apps). Collapse the per-gap branch's dev commits into one on squash-merge. |
| **Commit-message ticket?** | **`ION-12310` only** — the primary commons-upgrade Jira ticket. Do **not** put appianway program keys (ION-12317/ION-12316) in commit messages; gap IDs + program context live in this design doc and the README notes text. |
| **How many version bumps?** | **This landing = ONE bump `1.0.28-SNAPSHOT`** (S-G2, W-G9, X-G7, X-G10, C-G6+config). Bump `<dependency.version>` `1.0.27 → 1.0.28-SNAPSHOT` **once** (first set commit, which also creates the `### Commons v1.0.28-SNAPSHOT` heading); each subsequent set commit **appends its note**. **X-G11 is a separate, later effort** → its own `1.0.29-SNAPSHOT` bump, **not merged with this landing** and done only after appianway has consumed `1.0.28`. |

### 13.2 Why the single bump is safe
- **Additive/inert (the five + config) — this is the `1.0.28` landing:** S-G2 (new overloads), W-G9.1/9.2 (builder field + constants), X-G7/X-G10 (new email paths gated on reply-to/attachments), C-G6 (visibility widen), config-substitution (new class). None changes an existing call path — proven in §2/§2.1. A consumer that calls none of them behaves exactly as on `1.0.27`.
- **X-G11 is deferred (F2 — separate later effort):** it **modifies the existing boot-time `createParameterStore` path** that every app runs — behavior-*equivalent* (region/credentials/profile-name unchanged; only a null-safe profile-file supplier added), but a *modification*, **not** a zero-risk addition. **Decision (2026-07-23): X-G11 is NOT merged with the `1.0.28` set.** Land and roll out all the `1.0.28` gaps to appianway first; **then** do X-G11 **separately** as its own commit + its own bump `1.0.29-SNAPSHOT`, isolated and independently revertible.
- **Phased appianway rollout is unaffected:** event-writer (pilot) consumes `1.0.28-SNAPSHOT` and uses S-G2 + W-G9; the other additive changes ride along unused.
- **One consumer version step:** already-upgraded mercury-services apps move `1.0.27 → 1.0.28` once (or stay on `1.0.27` until they choose), and every change is additive so the bump is safe either way. The ~5 per-gap commits keep each gap's **code** independently revertible even though there is a single version.

### 13.3 Landing map — `1.0.28` set (~5 commits, single bump); X-G11 deferred
Each row = one gap branch → one squashed commit on the main feature branch. There is **one** version bump for the `1.0.28` set; the first commit performs it and creates the `v1.0.28` README heading, and each later commit appends its note. **X-G11 is not in this set** — it is a separate later effort (see the note below the table).

### 13.3 Per-gap landing map (~6 commits, single bump to `1.0.28-SNAPSHOT`)
Each row = one gap branch → one squashed commit on the main feature branch. There is **one** version bump for the whole set; the first commit performs it and creates the `v1.0.28` README heading, and each later commit appends its note.

| # | Gap branch → squashed commit | Gaps | Version / README |
|:--:|---|---|---|
| 1 | `-sg2` — StorageClient metadata/copy | **S-G2** | **bump → `1.0.28-SNAPSHOT`**; create `v1.0.28` heading + note 1 |
| 2 | `-wg9` — workflow-model wire parity | **W-G9.1 + W-G9.2** | append note 2 (stays `1.0.28`) |
| 3 | `-xg7` — email reply-to | **X-G7** | append note 3 |
| 4 | `-xg10` — email attachments (raw MIME) | **X-G10** | append note 4 |
| 5 | `-config` — transformer hook + property-substitution | **C-G6 + config-substitution** | append note 5 (**completes `v1.0.28`**) |

> X-G7 lands before X-G10 (both touch `SesEmailServiceImpl`/`MailContent`; attachments build on the reply-to change). Tightly-coupled pairs may be merged into a single commit if you prefer fewer than 5.

**X-G11 — deferred (separate later effort):** after the `1.0.28` set is merged, published, and **rolled out to appianway**, do X-G11 on its own `feature/ION-12310-xg11` branch → one squashed commit that **bumps `1.0.28 → 1.0.29-SNAPSHOT`**, demotes the `v1.0.28` paragraph, and creates a new `### Commons v1.0.29-SNAPSHOT` heading with its own note. It is **not** part of this landing and must **not** block or ride the `1.0.28` rollout.

### 13.4 Per-gap checklist (each `feature/ION-12310-<gap>` → one squashed commit)
0. **(Once, before starting)** back up the feature branch per §13.1 step 0.
1. Cut `feature/ION-12310-<gap>` from the current feature-branch tip; implement + unit/DynamoDB-IT tests; `mvn -pl commons,cloud-sdk-api,cloud-sdk-aws,dynamo-integration-test verify` green (incl. DynamoDB Local ITs).
2. **Consumer zero-impact gate (no reactor build):** build the **upgraded modules only** against the SNAPSHOT **before and after** —
   ```
   mvn -pl network,auth,registration,self-service-reports,tx-tracking,booking,visibility,webbl,booking-bridge,db-migration -am verify
   ```
   (the other mercury-services modules are not yet on cloud-sdk — do **not** run a full reactor build).
3. Squash-merge into the feature branch as **one** commit (commit message references **`ION-12310`** only).
4. **Version bump = ONCE for the `1.0.28` set:** the **first** set commit (S-G2) bumps `<dependency.version>` in root `pom.xml` `1.0.27 → 1.0.28-SNAPSHOT` and creates the `### Commons v1.0.28-SNAPSHOT` heading; the other four set commits **append their note** (no further bump). **X-G11 is out of this set** — its `1.0.29` bump happens later, separately (§13.3).
5. **Roll/append the README** per §13.5 in the same commit.
6. **Ordinary `git push`** after review approval — **no rebase and no force-push** in this workflow (a squash-merge adds a normal commit on the tip). `--force-with-lease` applies only to the separate rebase scenario in §13.6, which is **not** part of this work.

### 13.5 README rollover convention (from §15.1 — apply on every bump)
The 5-line "this is the tip" descriptive paragraph must sit under **exactly one** heading: the **newest** `### Commons v1.0.N-SNAPSHOT`. On each bump (old tip `vX` = `1.0.27`, new `vY` = `1.0.28`):
1. **Demote `vX`:** remove the 5-line descriptive paragraph from `### Commons v1.0.27-SNAPSHOT`, leaving a blank line then its numbered notes (`1. Rebase onto develop (owasp/jackson changes)`).
2. **Create `vY`:** add `### Commons v1.0.28-SNAPSHOT` immediately below `v1.0.27`'s notes; paste the descriptive paragraph, a blank line, then numbered notes describing this landing.
3. Bump `<dependency.version>` in root `pom.xml` to `1.0.28-SNAPSHOT` in the same commit.

**Resulting README shape (final state after the five `1.0.28`-set commits — all five under `v1.0.28`; X-G11 comes later as `v1.0.29`):**
```
### Commons v1.0.27-SNAPSHOT

1. Rebase onto  develop (owasp/jackson changes)

### Commons v1.0.28-SNAPSHOT
This is the latest snapshot version of the commons module from the feature branch 'feature/ION-12310-commons-cloudsdk-refactoring'
This branch is not yet merged to the main branch.
This branch is used for the cloud sdk refactoring and to integrate the Inttra Applications with the latest cloudsdk libraries.
Once all the applications are migrated to the cloudsdk libraries, this branch will be merged to the main branch.

1. ION-12310 S-G2: StorageClient put/copy with user metadata + content-type (additive default overloads; S3 REPLACE on copy).
2. ION-12310 W-G9: Event.Builder annotations round-trip restored; +6 MetaData.Projection & +9 Event.Token constants (wire-parity with appianway shared).
3. ION-12310 X-G7: replyTo on MailContent/SES send (additive).
4. ION-12310 X-G10: EmailService first-class attachment support (raw MIME when MailContent has attachments; simple path unchanged).
5. ION-12310 C-G6 + config: widened ConfigProcessingServerCommand.getConfigTransformer; added reusable multi-.properties substitution ConfigurationSourceProvider.
```
> **This landing = five notes under the one `### Commons v1.0.28-SNAPSHOT` heading** (first set commit adds the heading + note 1; each later set commit appends the next). **X-G11 is not here** — the later, separate X-G11 effort will demote this paragraph and add a `### Commons v1.0.29-SNAPSHOT` heading with its own note.

### 13.6 Rebase hygiene (from §15.2 — reference only; **NOT part of this gap work**)
> This gap work does **not** rebase the feature branch (§13.1). The rules below apply **only if** a separate rebase onto `develop` is required later (e.g. a future OWASP/CVE sync) — they are recorded here so the convention is not lost, not because a rebase is planned now.
- Always create `backup/feature-…-pre-rebase-N` before a rebase; keep until push is confirmed good.
- Resolve `pom.xml`/`commons/pom.xml` conflicts as a **UNION** of both sides (module lists, property blocks, dependencyManagement pins merge additively); keep the feature branch's `1.0.N-SNAPSHOT` scheme over develop's `1.R.01.xxx`.
- After resolving: validate POMs are well-formed XML; assert **zero** conflict markers remain.
- Gate every rebase on `mvn verify` for `commons`, `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test` (incl. DynamoDB Local ITs); roll test totals from surefire/failsafe XML.
- Never push a rewritten shared branch without explicit approval; then use `--force-with-lease`. Every commit carries `ION-12310`.

---

## Appendix A — Source-of-truth inputs (appianway workspace)

### A.1 Program-level docs reviewed for this design (all provided in the 2026-07-23 request)
- `C:\Users\arijit.kundu\projects\appianway\2026-07-22-appianway-awsupgrade-ROLLUP-claude.md`
- `C:\Users\arijit.kundu\projects\appianway\2026-07-22-appianway-awsupgrade-foundation-claude.md` (§5A wire audit)
- `C:\Users\arijit.kundu\projects\appianway\2026-06-30-appianway-aws-upgrade-cloud-sdk-gap-DESIGN.md`

### A.2 ION-12317 program + module docs (`\docs\`)
- `docs\2026-07-22-ION-12317-aws-upgrade-program.md`
- `docs\2026-07-22-ION-12317-booking-inbound-consumer.md`
- `docs\2026-07-22-ION-12317-cargoscreen-consumer.md`
- `docs\2026-07-22-ION-12317-dispatcher.md`
- `docs\2026-07-22-ION-12317-distributor-rest.md`
- `docs\2026-07-22-ION-12317-distributor.md`
- `docs\2026-07-22-ION-12317-email-sender.md`
- `docs\2026-07-22-ION-12317-error-processor.md`
- `docs\2026-07-22-ION-12317-event-writer.md`

### A.3 Per-module `2026-07-22-<module>-awsupgrade-claude.md` docs
- `dispatcher\docs\2026-07-22-dispatcher-awsupgrade-claude.md`
- `distributor\docs\2026-07-22-distributor-awsupgrade-claude.md`
- `distributor-rest\docs\2026-07-22-distributor-rest-awsupgrade-claude.md`
- `email-sender\docs\2026-07-22-email-sender-awsupgrade-claude.md`
- `error-processor\docs\2026-07-22-error-processor-awsupgrade-claude.md`
- `event-writer\docs\2026-07-22-event-writer-awsupgrade-claude.md`
- `ingestor\docs\2026-07-22-ingestor-awsupgrade-claude.md`
- `splitter\docs\2026-07-22-splitter-awsupgrade-claude.md`
- `transformer\docs\2026-07-22-transformer-awsupgrade-claude.md`
- `watermill\booking-inbound-consumer\docs\2026-07-22-booking-inbound-consumer-awsupgrade-claude.md`
- `watermill\cargoscreen-consumer\docs\2026-07-22-cargoscreen-consumer-awsupgrade-claude.md`
- `watermill\itv-gps-consumer\docs\2026-07-22-itv-gps-consumer-awsupgrade-claude.md`
- `watermill\visibility-inbound-consumer\docs\2026-07-22-visibility-inbound-consumer-awsupgrade-claude.md`
- `watermill-publisher\docs\2026-07-22-watermill-publisher-awsupgrade-claude.md`

### A.4 Exact constants & code verified from appianway `shared`- `appianway\shared\src\main\java\com\inttra\mercury\shared\event\Event.java` (`Token` constants, `Builder.setAnnotations`)
- `appianway\shared\src\main\java\com\inttra\mercury\shared\task\MetaData.java` (`Projection` constants)
- `appianway\shared\src\main\java\com\inttra\mercury\shared\config\lookup\{VariableLookupProvider,ProcessedConfigProvider}.java` (config substitution)
- `appianway\ingestor\src\main\java\com\inttra\mercury\ingestor\modules\JestModule.java` (`vc.inreach` v1 signer)
- `appianway\transformer\src\main\java\com\inttra\mercury\transformer\command\DynamoTableCommand.java` (v1 table command)

### A.5 mercury-services input (X-G10 origin)
- `C:\Users\arijit.kundu\projects\mercury-services\visibility\docs\2026-07-16-ION-12316-inbound-ses-startup-issue.md` — §12 (EmailService attachment gap, X-G10) and §11 (null-safe profile-file supplier, related/out-of-scope)

## Appendix B — Verified-in-this-workspace facts (grounding)
| Fact | File |
|---|---|
| `StorageClient` lacks metadata/content-type overloads | `cloud-sdk-api/…/storage/api/StorageClient.java` |
| `S3StorageClient` already imports `PutObjectRequest`/`CopyObjectRequest`/`RequestBody`, not `MetadataDirective` | `cloud-sdk-aws/…/storage/impl/S3StorageClient.java` |
| `Event.Builder` has no `annotations`/`setAnnotations`; `Event(Builder)` never assigns annotations | `cloud-sdk-api/…/notification/workflow/Event.java` |
| `Event.Token` has 9 constants; `MetaData.Projection` missing the 6 named keys | same + `…/workflow/MetaData.java` |
| `MailContent` has no reply-to; `SesEmailServiceImpl` builds `SendEmailRequest` without `replyToAddresses` | `cloud-sdk-api/…/email/api/MailContent.java`, `cloud-sdk-aws/…/email/impl/{MailContentImpl,SesEmailServiceImpl}.java` |
| `SesEmailServiceImpl.buildEmailContent(MailContent)` builds a `simple` message only and **ignores `getAttachments()`** (X-G10); `EmailMimeUtils` (javax.mail) already has MIME machinery wired only into the template path | `cloud-sdk-aws/…/email/impl/SesEmailServiceImpl.java`, `cloud-sdk-aws/…/email/utils/EmailMimeUtils.java` |
| **booking** sends all mail via `sendTemplateEmail(...)` (template path, unaffected by X-G10); **auth** `SimpleMailContent.getAttachments()` returns `emptyList()` | `mercury-services/booking/…/outbound/email/OutboundEmailSender.java`, `mercury-services/auth/…/utils/email/EmailClient.java` |
| `ParameterStoreClientFactory` sets **no** profile-file supplier; uses explicit `config.getCredentialsProvider()` (X-G11 target) | `cloud-sdk-aws/…/paramstore/factory/ParameterStoreClientFactory.java` |
| `JestClientBuilder` accepts an externally-supplied signing interceptor (X-G8 needs no change); ingestor + mercury-services both use the `vc.inreach` **v1** signer | `cloud-sdk-api/…/elasticsearch/JestClientBuilder.java`, `appianway/ingestor/…/modules/JestModule.java` |
| `ConfigProcessingServerCommand.getConfigTransformer` is `private` (C-G6 target); chains Trim → ParameterStore only | `commons/…/config/ConfigProcessingServerCommand.java` |
| `DynamoDbAdminCommand` (`dynamo-create`) already exists and is adopted by mercury-services (`VisibilityInboundDynamoDbAdminCommand`); appianway still uses v1 module-local `DynamoTableCommand` | `cloud-sdk-aws/…/database/command/DynamoDbAdminCommand.java`, `mercury-services/visibility-inbound/…/VisibilityInboundDynamoDbAdminCommand.java`, `appianway/transformer/…/command/DynamoTableCommand.java` |
| No mercury-services app calls cloud-sdk `Event.parseJson`/`Event.Builder(Event)`; booking-bridge uses object-level `setAnnotations` | `mercury-services` grep (booking, booking-bridge, visibility/\*, webbl) |

---

## Final Review by Claude

> Reviewer: Claude Opus 4.8 · Date: 2026-07-23 · Method: every cloud-sdk-side "verified current state" claim below was re-checked against the live source in **this** workspace (`mercury-services-commons`). Claims about `appianway/shared`, the mercury-services consumer apps, `ingestor`, and the v1 `DynamoTableCommand` live in **other** repos and could **not** be verified here — see finding #1.

### Verdict
The design is **sound and the recommendation is correct**: the five required changes are genuinely additive, and I confirmed every gap it claims about the code in this repo. It is safe to proceed. The findings below are **refinements and two real correctness risks** in the *hardening* items (X-G11), not objections to the core five.

### What I independently verified (all accurate)
| Gap | Claim | Verified in source |
|---|---|---|
| S-G2 | `StorageClient` has only metadata-less `putObject`/4-arg `copyObject` | ✅ [StorageClient.java:21-30](../src/main/java/com/inttra/mercury/cloudsdk/storage/api/StorageClient.java#L21-L30) |
| W-G9.1 | `Event` has class-level `annotations` (serialized) but `Builder` has **no** `annotations`/`setAnnotations`, `Builder(Event)` doesn't copy it, `Event(Builder)` doesn't assign it → asymmetric drop on `parseJson` | ✅ [Event.java:65](../src/main/java/com/inttra/mercury/cloudsdk/notification/workflow/Event.java#L65), ctor L67-85, `Builder(Event)` L186-203 |
| W-G9.2 | `Event.Token` has exactly 9 constants; the 6 `Projection` + 9 `Token` names are absent | ✅ [Event.java:136-146](../src/main/java/com/inttra/mercury/cloudsdk/notification/workflow/Event.java#L136-L146), [MetaData.java:96-125](../src/main/java/com/inttra/mercury/cloudsdk/notification/workflow/MetaData.java#L96-L125) |
| X-G7 | `MailContent` exposes subject/html/text/attachments only; `SesEmailServiceImpl` builds `SendEmailRequest` with no `replyToAddresses` | ✅ [MailContent.java:7-17](../src/main/java/com/inttra/mercury/cloudsdk/email/api/MailContent.java#L7-L17), [SesEmailServiceImpl.java:120-124](../../cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImpl.java#L120-L124) |
| X-G10 | `buildEmailContent` builds `EmailContent.simple(...)` only and never reads `getAttachments()`; the raw-MIME machinery is wired only into the legacy template path | ✅ [SesEmailServiceImpl.java:445-465](../../cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImpl.java#L445-L465) vs `createMimeMessage(EmailRequest,vars)` L362 |
| X-G11 | `ParameterStoreClientFactory` sets **no** profile-file supplier; uses explicit `config.getCredentialsProvider()` | ✅ [ParameterStoreClientFactory.java:24-30](../../cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactory.java#L24-L30) |
| C-G6 | `getConfigTransformer` is `private`, chains Trim → ParameterStore only | ✅ [ConfigProcessingServerCommand.java:26-30](../../commons/src/main/java/com/inttra/mercury/config/ConfigProcessingServerCommand.java#L26-L30) |

### Correctness findings (ranked)

**F1 (must fix) — X-G11 hardcodes `defaultProfileName("default")`, which suppresses `AWS_PROFILE`.**
The §7.4.2 code adds `.defaultProfileName("default")` in addition to the supplier. Today the factory sets neither; the SDK resolves the profile name from `AWS_PROFILE`/`aws.profile`, falling back to `"default"`. Explicitly pinning `defaultProfileName("default")` makes the SDK **ignore `AWS_PROFILE`** entirely. Any environment that sets `AWS_PROFILE` (local dev, some CI runners) would silently switch profiles. This **contradicts the §0 contract** ("no runtime default may change") and the §7.4.3 claim that "only the default profile-file supplier is replaced." **Remove the `defaultProfileName("default")` line** — add only the null-safe supplier, which is all the resilience goal actually requires.

**F2 (should fix) — X-G11 is not "strictly additive" in the §0 sense; it edits a boot-critical existing path.**
Every one of the ~7 upgraded apps (and all 14 appianway apps) executes `createParameterStore(...)` at startup. Unlike S-G2/W-G9/X-G7/X-G10 (new overloads/fields nobody calls yet), X-G11 **modifies an existing runtime code path** — it swaps the SDK's default `ProfileFileSupplier`. The equivalence argument in §7.4.3 is plausible and probably correct, but this is *low-risk-modification*, not *zero-risk-addition*, and it should not ride the same single `1.0.28` bump framed as "a consumer that calls none of them behaves exactly as on 1.0.27" (§13.2). **Recommend:** split X-G11 onto its own commit/version step (or its own SNAPSHOT) so it can be reverted independently of the truly-inert five, and gate it with an explicit ECS-like `AWS_PROFILE`-set test, not just null-`user.home`.

**F3 (should fix) — the wire-parity + corpus test cannot actually catch a cloud-sdk-vs-`shared` key mismatch.**
The `annotations` payload serializes as outer key `annotations` (the `Event` field, no `@JsonProperty`) wrapping inner key `Annotations` (the `@JsonProperty("Annotations")` on [Annotations.java:33](../src/main/java/com/inttra/mercury/cloudsdk/notification/annotation/Annotations.java#L33)). The whole W-G9 safety story is "restores parity with `shared`," but `WorkflowWireCompatTest` (§8) round-trips cloud-sdk's *own* serializer on both ends — it will pass even if `shared` emits a **different outer key casing**. **Recommend:** seed the corpus with **real `shared`-produced JSON fixtures** (bytes actually written by appianway/event-writer), not cloud-sdk-generated strings, so a cross-library key/casing divergence fails the gate. I cannot confirm the casing matches because `shared` is not in this workspace (see F5).

**F4 (test gap) — W-G9.1 test #2 can pass with an empty inner list.**
`Annotations` has no setter/`@JsonCreator` for its list; Jackson populates it via the mutable-collection getter ("getter-as-setter"). `getAnnotations() != null` (§4.4 test 2) would be satisfied even if the inner `List<Annotation>` deserialized empty. **Assert the inner annotations are present and equal**, not just that the wrapper is non-null.

**F5 (accuracy of the doc's own framing) — the header overclaims verification scope.**
The header states "Every 'current state' below is verified against the live source **in this workspace**." That holds for the cloud-sdk side (I re-verified it). But the load-bearing safety claims — appianway `shared` having `setAnnotations`/matching constants, the §2.1 mercury-services consumer greps, ingestor's `vc.inreach` v1 signer, the v1 `DynamoTableCommand` — are in **other repos** (`appianway`, `mercury-services`) not present here, so they were *not* verifiable "in this workspace." They may well be true, but they rest on the source-of-truth docs in Appendix A, not this workspace. **Recommend:** relabel those as "verified against the appianway/mercury-services workspaces (per Appendix A)" so the distinction is honest and a future reader knows where to re-check.

### Approach findings (smaller)

- **F6 — "single request-build site" (X-G7 §6.2) is imprecise.** There are two `SendEmailRequest.builder()` sites: the non-templated one at [L120](../../cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImpl.java#L120) and the legacy template path at [L371](../../cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImpl.java#L371). Scoping X-G7 to the former is correct, but note the newer `sendTemplatedEmail` (L157) routes through `sendEmail(...)` and therefore inherits reply-to for free, while the legacy `sendTemplateEmail` (L231) keeps its own template-var reply-to and is untouched. The two similarly-named methods (`sendTemplatedEmail` vs `sendTemplateEmail`) are an existing footgun — state explicitly which one each claim refers to.
- **F7 — X-G7 §6.2 snippet drops the surrounding try/catch.** The current method wraps the send in the `SdkClientException`/`SdkServiceException`/`Exception` → `SendEmailException` mapping (L119-137). The refactored snippet shows a bare `sesClient.sendEmail(req.build())`. Implementation note: preserve the existing try/catch (as §3.4 explicitly instructs for S-G2 but §6.2 omits).
- **F8 — X-G10 dual recipient source.** §6b.3(b) keeps an explicit `.destination(...)` alongside raw MIME. SESv2 also derives recipients from the MIME headers; if `buildDestination` and the MIME `To/Cc/Bcc` ever diverge, recipients can double up or conflict. Add a test asserting the MIME headers and the explicit `Destination` agree (or drop one source for the raw path).
- **F9 — C-G6 + §7.3 override path depends on the transform classes being public.** For a subclass to "prepend" a provider by overriding `getConfigTransformer`, `ChainingConfigTransformer`, `ParameterStoreConfigTransform`, and `TrimConfigCommentsTransform` must be accessible. §7.2 asserts appianway already composes "the public transforms," which implies they are — worth an explicit one-line confirmation in the doc since the whole ergonomic argument for C-G6 rests on it.

### Bottom line
Ship the **core five (S-G2, W-G9.1, W-G9.2, X-G7, X-G10) as designed** — they are exactly as additive as claimed and I verified each against source. Before implementing, apply **F1 (drop `defaultProfileName`)** and reconsider **F2 (isolate X-G11's version/rollout)** — X-G11 is the only item that mutates a boot-time path shared by every app, and its snippet as written is a genuine behavior change, not the zero-risk addition the prose describes. Strengthen the W-G9 gate with a real cross-library fixture (**F3/F4**), and tighten the verification-scope wording (**F5**).

---

## 14. Implementation Log — Completed Actions (2026-07-24)

> Author: Copilot (Claude Opus 4.8) · MCP session `35cb592127df48b2` · Branch: `feature/ION-12310-commons-cloudsdk-refactoring` (tip `cc4a76d`).
> This section records what was **actually implemented and verified** against the plan above. The exact commands are in **Appendix C**.

### 14.1 Status summary

| Gap | Planned | Implemented | Verified (tests) |
|-----|:-------:|:-----------:|------------------|
| **S-G2** — StorageClient metadata/content-type put + copy(REPLACE) | ✅ | ✅ | ✅ `S3StorageClientMetadataTest` (8) |
| **W-G9.1** — `Event.Builder` annotations round-trip | ✅ | ✅ | ✅ `EventBuilderAnnotationsTest` (8) |
| **W-G9.2** — +6 `MetaData.Projection` / +9 `Event.Token` | ✅ | ✅ | ✅ `WorkflowConstantsParityTest` (17) |
| **X-G7** — `replyTo` on `MailContent` / SES send | ✅ | ✅ | ✅ `SesEmailReplyToAndAttachmentTest.ReplyTo` (3) + `MailContentImplTest` |
| **X-G10** — raw-MIME attachment support | ✅ | ✅ | ✅ `SesEmailReplyToAndAttachmentTest.{Attachments,RecipientSourceAgreement}` (6) + `EmailMimeUtilsMailContentTest` (4) |
| **C-G6** — widen `getConfigTransformer` `private`→`protected` | ✅ | ✅ | (compile-verified; exercised via the config test's chain-order case) |
| **config-substitution** — `PropertiesSubstitutionConfigProvider` | ✅ | ✅ | ✅ `PropertiesSubstitutionConfigProviderTest` (10) |
| **Wire gate** — `WorkflowWireCompatTest` with real-format fixtures | ✅ | ✅ | ✅ `WorkflowWireCompatTest` (7) |
| **X-G11** — SSM null-safe profile-file supplier | ⏸ deferred to `1.0.29` | ❌ (not started, as designed) | — |

**Version:** `<dependency.version>` bumped `1.0.27-SNAPSHOT` → **`1.0.28-SNAPSHOT`** in root `pom.xml`; README rolled per §13.5 (demoted the `v1.0.27` descriptive paragraph to its note; added the `### Commons v1.0.28-SNAPSHOT` heading with the 5 landing notes).

### 14.2 Files changed (main)

| Gap | File | Change |
|-----|------|--------|
| S-G2 | `cloud-sdk-api/.../storage/api/StorageClient.java` | +3 `default` overloads (put bytes+meta+ct, put stream+meta+ct, copy REPLACE) + `java.util.Map` import |
| S-G2 | `cloud-sdk-aws/.../storage/impl/S3StorageClient.java` | +3 overrides (reuse existing `validateInput`/`handleS3Exception`/`handleSdkException`/`handleUnexpectedException`) + `MetadataDirective`/`Map` imports |
| W-G9.1 | `cloud-sdk-api/.../notification/workflow/Event.java` | `Builder.annotations` field + `setAnnotations` + copy in `Builder(Event)` + assign in `Event(Builder)` ctor |
| W-G9.2 | `cloud-sdk-api/.../notification/workflow/Event.java` | +9 `Token` constants (`ORIGINAL_FILE_SIZE` + 8 `FTP_*`) |
| W-G9.2 | `cloud-sdk-api/.../notification/workflow/MetaData.java` | +6 `Projection` constants |
| X-G7 | `cloud-sdk-api/.../email/api/MailContent.java` | `default List<String> getReplyTo()` returning empty |
| X-G7/X-G10 | `cloud-sdk-aws/.../email/impl/MailContentImpl.java` | `replyTo` `@Builder.Default` field + `addAttachment(...)` builder helper |
| X-G7/X-G10 | `cloud-sdk-aws/.../email/impl/SesEmailServiceImpl.java` | `sendEmail(from,to,cc,bcc,content)`: attachment→raw-MIME branch (simple path unchanged), `replyToAddresses` when non-empty, `buildRawEmailContent(...)`, `MessagingException` import; **existing try/catch preserved (F6/F7)** |
| X-G10 | `cloud-sdk-aws/.../email/utils/EmailMimeUtils.java` | new `createMimeMessage(from,to,cc,bcc,MailContent)` overload (multipart/mixed > alternative(text,html) + attachments directly under mixed; To/Cc/Bcc headers; reply-to; null/**blank** content-type → `application/octet-stream`) |
| C-G6 | `commons/.../config/ConfigProcessingServerCommand.java` | `getConfigTransformer` `private`→`protected` |
| config-subst | `commons/.../config/PropertiesSubstitutionConfigProvider.java` | **new** `ConfigurationSourceProvider` (env→properties first-match, recursive chains, `${key:-default}`, fail-fast on unresolved, leaves `${awsps:...}` for the downstream transform, `loadClasspathProperties` helper, package-private env-injection ctor for tests) |
| version | `pom.xml` | `<dependency.version>` → `1.0.28-SNAPSHOT` |
| readme | `README.md` | §13.5 rollover + 5 landing notes |

**Test files added:** `S3StorageClientMetadataTest`, `EventBuilderAnnotationsTest`, `WorkflowConstantsParityTest`, `WorkflowWireCompatTest`, `SesEmailReplyToAndAttachmentTest`, `EmailMimeUtilsMailContentTest`, `PropertiesSubstitutionConfigProviderTest`; **modified** `MailContentImplTest` (+replyTo default/populated, +addAttachment). **Fixtures added:** `cloud-sdk-api/src/test/resources/wire/{event-with-annotations,event-without-annotations,metadata-with-projections}.json` and `commons/src/test/resources/config/substitution-base.properties`.

### 14.3 Review findings addressed during implementation

- **F3** — `WorkflowWireCompatTest` reads **external** JSON fixtures authored to the `shared` wire contract (outer `annotations` wrapping inner `Annotations`, `yyyy-MM-dd HH:mm:ss.SS` timestamps, the new projection/token keys) rather than round-tripping cloud-sdk's own serializer, and asserts the re-emitted JSON **tree equals the fixture tree** (cross-library key parity). *(Note: these are hand-authored to the contract, not literal event-writer bytes, since `shared`/`event-writer` are not in this workspace — the fixtures should be replaced with real captured bytes when available.)*
- **F4** — annotations tests assert the **inner `List<Annotation>` is non-empty and equal**, not just a non-null wrapper.
- **F6/F7** — X-G7/X-G10 scoped to the non-templated `sendEmail`; the existing `SdkClientException`/`SdkServiceException`/`Exception` → `SendEmailException` try/catch is preserved; the legacy template path is untouched.
- **F8** — `RecipientSourceAgreement` test asserts the raw-MIME `To/Cc/Bcc` headers and the explicit SES `Destination` carry the same addresses.
- **F1/F2** — honoured by **not** implementing X-G11 in this landing (deferred to `1.0.29`, no `defaultProfileName`).

### 14.4 Bug found & fixed during the build

The initial `EmailMimeUtils` overload used `Strings.isNullOrEmpty(contentType)` for the octet-stream fallback, which let a **whitespace-only** content-type (`"   "`) through → `javax.mail.internet.ParseException: In Content-Type string <   >, expected MIME type`. Fixed to `contentType == null || contentType.isBlank()`, matching the design's "null/**blank** → `application/octet-stream`". Caught by `SesEmailReplyToAndAttachmentTest.blankContentTypeFallsBackToOctetStream` in the first full `cloud-sdk-aws test` run.

### 14.5 Verification results

- **Library gate (green):** `mvn -pl commons,cloud-sdk-api,cloud-sdk-aws,dynamo-integration-test verify` → **BUILD SUCCESS** at `1.0.28-SNAPSHOT`. Reactor: cloud-sdk-api ✅, dynamo-integration-test ✅ (DynamoDB Local ITs), cloud-sdk-aws ✅ (incl. failsafe ITs), commons ✅ (931 unit tests). `commons-1.0.28-SNAPSHOT.jar` produced (confirms bump).
- **New tests:** cloud-sdk-api 29 new tests pass; cloud-sdk-aws suite 901 pass (incl. the new metadata/email tests); commons config-substitution 10 pass.
- **Consumer zero-impact gate (NOT run here):** the `mvn -pl network,...,db-migration -am verify` gate lives in the **`mercury-services`** workspace, which is not open here — it must be run there (§0/§10). See Appendix C §C.7.

### 14.6 Delivery state & remaining actions (git)

- ✅ Local backup branch `backup/feature-ION-12310-pre-sdk-gaps-2026-07-23` created at the pre-work tip `cc4a76d` **and pushed to origin** (2026-07-24) for off-machine safety.
- ✅ **The gap work is COMMITTED and PUSHED** (2026-07-24) — the four Option A commits landed on `feature/ION-12310-commons-cloudsdk-refactoring` and were pushed (`cc4a76d..1293c50`, fast-forward, no force). Local `HEAD` == `origin` == `1293c50`. See §16 for the final status and the commit map.
- ⚠️ Pre-existing untracked artifacts that were **not** committed (deliberately excluded from every `git add`): `.claude/`, `.mcp.json`, `cloud-sdk-aws/effective-pom.xml`, `cloud-sdk-aws/dynamodb-local-metadata.json`, `dynamo-integration-test/dynamodb-local-metadata.json`.
- ℹ️ This design/implementation doc lives under `cloud-sdk-api/docs/`, which is **gitignored** (`.gitignore` line 17 `docs/`), so it is **local-only by repo convention** and is not part of any commit.

### 14.7 Post-review hardening (2026-07-24)

A review of the landed code raised the following; all are addressed (still within the `1.0.28` set — X-G7/X-G10 refinements, no version change):

| # | Observation | Resolution |
|---|-------------|-----------|
| **1 [should-fix]** | Reply-To was set **twice** on the attachment path — once inside the raw MIME (`EmailMimeUtils`) and again via `SendEmailRequest.replyToAddresses(...)` — so SES could emit a **duplicate `Reply-To`** header. | `SesEmailServiceImpl.sendEmail` now applies `replyToAddresses(...)` **only on the simple path** (`if (!hasAttachments && …)`); the raw path carries reply-to solely in the MIME. **Single source per path.** `attachmentAndReplyToComposeTogether` rewritten to assert `hasReplyToAddresses()==false` **and** parse the raw MIME's `Reply-To` header. |
| **2 [minor]** | `MailContentImplBuilder.addAttachment` reaches into Lombok internals (`attachments$value`/`attachments$set`). | Added a javadoc **Lombok-coupling** note; behavior unchanged (it is the documented builder-customization pattern and is covered by `multipleAttachmentsAllIncluded`). |
| **3 [minor]** | Wire fixtures are hand-authored to the `shared` contract, not captured from real event-writer output. | **No change** (accepted): no real `shared`/event-writer JSON is available in this workspace; drop a captured payload in when one exists. Already noted in §14.3/F3. |
| **4 [minor]** | Env lookup uses the literal placeholder key, so a dotted `${db.host}` won't resolve from an OS env var. | Added a javadoc note on `buildLookup` documenting the literal-lookup behavior and when to normalize (dots→underscores) for parity with `shared`. Behavior left literal (matches a plain `StringLookup`). |
| **5 [nit]** | `validateNoUnresolvedPlaceholders` can false-positive if a resolved value legitimately contains a literal `${…}`. | Added a javadoc **edge-case** note; behavior kept (fail-fast trade-off). |
| **6 [nit, no action]** | `Session.getDefaultInstance(new Properties())` returns a JVM-shared session. | **No change** — consistent with the two existing `EmailMimeUtils` call sites; not a regression. |
| **IDE warnings** | Potential-NPE / unsafe-null-conversion flags in the new tests (`getResourceAsStream`, `content().raw()` chains, `getAnnotations()` chains, captor value). | Made the accesses null-safe: `Objects.requireNonNull` on the fixture stream and captured request, a `rawBytes(...)` helper for raw-MIME extraction, and `requireNonNull`-guarded annotation locals. No behavior change. |

**Re-verified:** `cloud-sdk-aws` email tests (44) green incl. the rewritten reply-to test; `cloud-sdk-api` workflow tests (29) green; `commons` config test (10) green.

---

## 15. User Review & Resolutions (2026-07-24)

A user review of the landed `1.0.28` code produced the comments below. **All are resolved**; none changed the gap scope or the `1.0.28-SNAPSHOT` version. (This consolidates §14.7 and adds the IDE / static-analysis explanations — including the `capture#3-of ?` case — so future readers understand both the *what* and the *why*.)

### 15.1 Functional / structural comments

| # | Severity | Comment | Resolution | Where |
|---|----------|---------|-----------|-------|
| 1 | **should-fix** | Reply-To was set **twice** on the attachment path — inside the raw MIME (`EmailMimeUtils`) **and** via `SendEmailRequest.replyToAddresses(...)` — risking a **duplicate `Reply-To`** header (RFC 5322 allows one; clients handle duplicates inconsistently). | Apply `replyToAddresses(...)` **only on the simple path** (`if (!hasAttachments && …)`); the raw path carries reply-to solely in the MIME. **Single source per path.** Test rewritten to assert `hasReplyToAddresses()==false` and parse the raw MIME `Reply-To`. | `SesEmailServiceImpl.sendEmail`; `SesEmailReplyToAndAttachmentTest.attachmentAndReplyToComposeTogether` |
| 2 | minor | `addAttachment` reaches into Lombok internals (`attachments$value`/`attachments$set`). | Added a javadoc **Lombok-coupling** note; behavior unchanged (documented builder-customization pattern, covered by `multipleAttachmentsAllIncluded`). | `MailContentImpl.MailContentImplBuilder` |
| 3 | minor | Wire fixtures are hand-authored to the `shared` contract, not captured from real event-writer output. | **No action** (user confirmed no real event-writer JSON is available). Swap in a captured payload when one exists — closes the last of F3. | `cloud-sdk-api/src/test/resources/wire/*.json` |
| 4 | minor | Env lookup uses the literal placeholder key, so a dotted `${db.host}` won't resolve from an OS env var. | Added a javadoc note on `buildLookup` documenting the literal-lookup behavior and when to normalize (dots→underscores) for parity with `shared`. Behavior kept literal (matches a plain `StringLookup`). | `PropertiesSubstitutionConfigProvider.buildLookup` |
| 5 | nit | `validateNoUnresolvedPlaceholders` can false-positive if a *resolved* value legitimately contains a literal `${…}`. | Added a javadoc **edge-case** note; fail-fast trade-off kept. | `PropertiesSubstitutionConfigProvider` |
| 6 | nit (no action) | `Session.getDefaultInstance(new Properties())` returns a JVM-shared session (the `Properties` arg is ignored after first call). | **No change** — consistent with the two existing `EmailMimeUtils` call sites; not a regression. | `EmailMimeUtils` |

### 15.2 IDE / static-analysis warnings (null-safety)

Flagged spots and the null-safety applied (behavior-preserving):

| Warning | Location | Resolution |
|---------|----------|-----------|
| Potential NPE — `getResourceAsStream` can return `null`, then `in.readAllBytes()` NPEs | `WorkflowWireCompatTest.fixture` | `Objects.requireNonNull(getResourceAsStream(...), "fixture … must exist")` |
| Potential NPE — `request.content().raw()` chains | `SesEmailReplyToAndAttachmentTest` | added a `rawBytes(request)` helper using `Objects.requireNonNull` on `content()`/`raw()`; used everywhere |
| Unsafe null / potential NPE — captured `SendEmailRequest` | `captureRequest()` | returns `Objects.requireNonNull(captor.getValue(), …)` |
| Potential NPE — `getAnnotations()`/`toJsonString()` derefs | `EventBuilderAnnotationsTest` | `requireNonNull`-guarded locals (`Annotations parsedAnnotations = requireNonNull(parsed.getAnnotations())`) |

### 15.3 The `capture#3-of ?` / `Java(976)` warning — explanation & resolution

**Symptom (VS Code Java, Eclipse JDT):**
```
Potential null pointer access: this expression has type 'capture#3-of ?',
a free type variable that may represent a '@Nullable' type   Java(976)
```
seen on a **chained** AssertJ assertion, e.g. `assertThat(json).contains("a").contains("b").contains("c")`.

**What it actually means (it is NOT saying your value is null):**
- The VS Code Java extension runs the **Eclipse JDT** compiler; `Java(976)` is its **null-analysis** diagnostic.
- `AssertJ`'s `Assertions.assertThat(String)` returns `AbstractStringAssert<?>` — a **wildcard** type. Each fluent method returns the recursive self-type `SELF`. When you **chain** calls, the compiler applies *capture conversion*, inventing a fresh anonymous type variable it names **`capture#N-of ?`**.
- JDT's null analysis treats a **free (unbounded) type variable as *potentially* `@Nullable`** — because a caller *could* substitute a `@Nullable` type argument. So dereferencing a value whose *static type* is that captured variable (calling the **second/third** `.contains(...)` on the result of the previous one) trips the warning.
- It is a **conservative false positive** about the *type variable*, not the runtime value: AssertJ always returns `this` (never null). This is also why `requireNonNull(json)` did **not** silence it — the flag is on the **captured self-type receiver of the chained call**, not on `json`.

**Resolution (idiomatic):** collapse the chain into a **single varargs `contains(...)`** call — one dereference, no captured-type receiver, warning gone, and it matches AssertJ's `contains(CharSequence... values)` overload:
```java
// before (chained → Java(976) on the 2nd/3rd .contains):
assertThat(json).contains("\"Annotations\"").contains("\"delivered\"").contains("\"retry-scheduled\"");
// after (single varargs call):
assertThat(json).contains("\"Annotations\"", "\"delivered\"", "\"retry-scheduled\"");
```
Applied in `EventBuilderAnnotationsTest` and `SesEmailReplyToAndAttachmentTest` (`.contains("one.txt", "two.txt")`). Other options (not used): split into separate `assertThat(...)` statements; lower the severity under *Java › Compiler › Errors/Warnings › Null analysis* (project-wide, so the code fix is preferred); or `@SuppressWarnings("null")` (heavy-handed).

**Re-verified after all resolutions:** `cloud-sdk-aws` email suite (44) green incl. the rewritten reply-to test; `cloud-sdk-api` workflow suite (29) green; `commons` config suite (10) green.

---

## 16. Final Status — DELIVERED (2026-07-24)

**The `1.0.28-SNAPSHOT` gap set is complete, committed, pushed, and green.** X-G11 remains intentionally deferred to a separate later `1.0.29-SNAPSHOT` (§7.4/§13.3).

### 16.1 Commits (Option A — 4 commits, `ION-12310` messages only)
On `feature/ION-12310-commons-cloudsdk-refactoring`, stacked on the pre-work tip `cc4a76d`:

| # | SHA | Gap(s) | Notes |
|:-:|-----|--------|-------|
| 1 | `b25ae16` | **S-G2** | StorageClient put/copy w/ user metadata + content-type; **bump `1.0.27`→`1.0.28-SNAPSHOT`** (+`pom.xml`, README rollover) |
| 2 | `116fb02` | **W-G9.1 + W-G9.2** | Event.Builder annotations round-trip; +6 `MetaData.Projection` / +9 `Event.Token`; wire fixtures |
| 3 | `bfb03bd` | **X-G7 + X-G10** | reply-to + raw-MIME attachments on SES email (single-source reply-to per §14.7/§15) |
| 4 | `1293c50` | **C-G6 + config-substitution** | `protected getConfigTransformer`; `PropertiesSubstitutionConfigProvider` |

Push: `cc4a76d..1293c50` — **fast-forward, no `--force`**. Local `HEAD` == `origin/feature/ION-12310-commons-cloudsdk-refactoring` == **`1293c50`**. Backup `backup/feature-ION-12310-pre-sdk-gaps-2026-07-23` on origin at `cc4a76d`. (Remote reports open PR **#29** feature → develop.)

### 16.2 Verification (green)
- **Library gate:** `mvn -pl commons,cloud-sdk-api,cloud-sdk-aws,dynamo-integration-test verify` → **BUILD SUCCESS** at `1.0.28-SNAPSHOT` — cloud-sdk-api ✅, dynamo-integration-test ✅ (DynamoDB Local ITs), cloud-sdk-aws ✅ (incl. failsafe ITs, ~5 min), commons ✅ (931 tests). `commons-1.0.28-SNAPSHOT.jar` built.
- **New/changed suites:** cloud-sdk-api workflow (29) ✅ · cloud-sdk-aws email (44) ✅ · commons config (10) ✅.

### 16.3 Scope delivered vs deferred
| Item | State |
|------|-------|
| S-G2, W-G9.1, W-G9.2, X-G7, X-G10, C-G6, config-substitution, WorkflowWireCompatTest | ✅ delivered in `1.0.28-SNAPSHOT` |
| X-G8 (Jest signer) | ✅ no change required (verified) |
| DynamoDB `DynamoDbAdminCommand` adoption | ↪ appianway-side (existing SDK, not this landing) |
| **X-G11** (SSM null-safe profile-file supplier) | ⏸ **deferred to `1.0.29-SNAPSHOT`** — do after appianway consumes `1.0.28` |

### 16.4 Remaining actions (owned by user / team — outside this workspace)
1. Roll `1.0.28-SNAPSHOT` out to **appianway** (event-writer pilot → rest) and to the upgraded **mercury-services** consumers.
2. Run the **consumer zero-impact gate** in the `mercury-services` workspace (Appendix C §C.7) — could not be run here.
3. After rollout, implement **X-G11** as its own `1.0.29-SNAPSHOT` (§7.4/§13.3, F1/F2).

> **MCP session `35cb592127df48b2`** was marked **completed** on 2026-07-24 with this status.

---

## Appendix C — Commands Used & Reusable Runbook

> Every command below was run from the repo root `C:\Users\arijit.kundu\projects\mercury-services-commons` in a Git-Bash shell. Commands are grouped by phase with a short "why". Sections marked **[EXECUTED]** were actually run in this session; sections marked **[TEMPLATE — not yet run]** are the recommended next steps, written so they can be copy-pasted.

### C.1 Orientation / grounding **[EXECUTED]**
```bash
# What branch am I on, is the tree clean, what are the recent commits?
git status
git branch                 # list local branches (spot existing backups)
git --no-pager log --oneline -4

# Find the version property and the files each gap touches (fast, exact matches)
grep -RIn "<dependency.version>" pom.xml
# (equivalent VS Code tools were used: grep_search for exact strings, file_search for filenames)
```
*Why:* confirm a clean starting point, the current `1.0.27-SNAPSHOT` version, and the exact source files before editing — never edit blind.

### C.2 Safety backup **[EXECUTED]**
```bash
# Snapshot the pre-work tip as a local branch (does NOT switch branches)
git branch backup/feature-ION-12310-pre-sdk-gaps-2026-07-23 feature/ION-12310-commons-cloudsdk-refactoring
git branch --list 'backup/feature-ION-12310-pre-sdk-gaps-2026-07-23'   # verify it exists

# Push the backup to origin for off-machine safety, then verify it landed
git push origin backup/feature-ION-12310-pre-sdk-gaps-2026-07-23
git ls-remote --heads origin 'backup/feature-ION-12310-pre-sdk-gaps-2026-07-23'
```
*Why:* `git branch <new> <start>` creates a pointer at the current tip so the exact pre-change state is always recoverable. Pushing it means the safety copy survives even if the laptop is lost. `git ls-remote` confirms the remote ref without fetching.

### C.3 Build & install upstream libs (unit tests) **[EXECUTED]**
```bash
# Build + unit-test + install commons and cloud-sdk-api into the local ~/.m2 repo
# (-pl = only these modules; install is needed so downstream modules resolve the new bytes)
mvn -pl commons,cloud-sdk-api install
```
*Why:* `cloud-sdk-aws` depends on `commons` and `cloud-sdk-api`; installing them first makes the freshly-changed APIs available to the downstream reactor/test-compile. `install` runs the full lifecycle (compile → test → package → install).

### C.4 Targeted test runs (fast feedback) **[EXECUTED]**
```bash
# Run only the new api tests (comma-separated simple class names, no package)
mvn -pl cloud-sdk-api test -Dtest='EventBuilderAnnotationsTest,WorkflowConstantsParityTest,WorkflowWireCompatTest'

# Full cloud-sdk-aws unit tests (surefire only; no integration/failsafe)
mvn -pl cloud-sdk-aws test

# Re-run just the email/storage tests after a fix (tight loop)
mvn -pl cloud-sdk-aws test -Dtest='SesEmailReplyToAndAttachmentTest,EmailMimeUtilsMailContentTest,MailContentImplTest,SesEmailServiceImplTest,S3StorageClientMetadataTest'

# One commons test class
mvn -pl commons test -Dtest='PropertiesSubstitutionConfigProviderTest'
```
*Why:* `-Dtest='A,B'` scopes surefire to specific classes so each change is validated in seconds instead of running the whole module. `test` phase deliberately skips the slower failsafe integration tests.

### C.5 Diagnose a failing test **[EXECUTED]**
```bash
# 1) Find which surefire report has a non-zero error/failure count
grep -rlE 'errors="[1-9]|failures="[1-9]' cloud-sdk-aws/target/surefire-reports/*.xml

# 2) Grep the human-readable .txt reports for the marker lines
grep -rE '<<< ERROR|<<< FAILURE' cloud-sdk-aws/target/surefire-reports/*.txt | tail -n 20

# 3) Read the full stack trace for the offending test
sed -n '1,60p' 'cloud-sdk-aws/target/surefire-reports/com.inttra.mercury.cloudsdk.email.impl.SesEmailReplyToAndAttachmentTest$Attachments.txt'
```
*Why:* when a big reactor run reports `Errors: 1` at the bottom, these three steps pinpoint the exact failing test and its root cause (here: the whitespace content-type `ParseException`) without scrolling thousands of lines. `-rlE` lists only matching files; `sed -n '1,60p'` prints a line range.

> **Filtering big Maven output:** the summary was extracted with, e.g.
> `mvn ... verify 2>&1 | grep -E "Tests run: [0-9]+, Fail|BUILD SUCCESS|BUILD FAILURE|SUCCESS \[|FAILURE \[|Reactor Summary" | tail -n 40`
> — `2>&1` merges stderr, `grep -E` keeps only the summary/reactor lines, `tail` trims to the end.

### C.6 Full library gate (unit + integration) **[EXECUTED]**
```bash
# The whole additive-library gate incl. DynamoDB Local ITs (failsafe). Must be green before/after.
mvn -pl commons,cloud-sdk-api,cloud-sdk-aws,dynamo-integration-test verify
```
*Why:* `verify` runs the integration-test/failsafe phases (the `test` phase does not). This is the library-side proof that nothing regressed and the `1.0.28-SNAPSHOT` bump builds cleanly across all four modules.

### C.7 Consumer zero-impact gate **[TEMPLATE — run in the `mercury-services` workspace, not here]**
```bash
# Run in C:\Users\arijit.kundu\projects\mercury-services (the consumer repo), BEFORE and AFTER,
# to prove the upgraded apps still build green against the SNAPSHOT. NOT a full reactor build.
mvn -pl network,auth,registration,self-service-reports,tx-tracking,booking,visibility,webbl,booking-bridge,db-migration -am verify
```
*Why:* the other mercury-services modules are not yet on cloud-sdk, so a full reactor build would fail for unrelated reasons; `-pl <upgraded modules> -am` builds just the cloud-sdk consumers plus their upstream deps. This is the §0 zero-impact proof and **could not be run in this (`mercury-services-commons`) workspace**.

### C.8 Commit the gaps **[TEMPLATE — not yet run]**

> **Important:** stage **only** the gap files. Do **not** `git add -A` — that would sweep in the pre-existing untracked artifacts `.claude/`, `.mcp.json`, `cloud-sdk-aws/effective-pom.xml`, and the two `dynamodb-local-metadata.json` files.

Because **X-G7 and X-G10 are interleaved inside the same methods/files** (`SesEmailServiceImpl.sendEmail`, `MailContentImpl`, `MailContentImplTest`), they cannot be split into two separately-**compiling** commits; the design (§13.3) explicitly allows merging tightly-coupled gaps. Two equivalent options:

**Option A — direct per-gap commits on the feature branch (simplest; 4 logical commits):**
```bash
# 1) S-G2 (+ the version bump & README rollover, per design §13.3 note that commit 1 does the bump)
git add cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/storage/api/StorageClient.java \
        cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java \
        cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientMetadataTest.java \
        pom.xml README.md
git commit -m "ION-12310: S-G2 StorageClient put/copy with user metadata + content-type; bump 1.0.28-SNAPSHOT"

# 2) W-G9.1 + W-G9.2 (workflow-model wire parity)
git add cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/notification/workflow/Event.java \
        cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/notification/workflow/MetaData.java \
        cloud-sdk-api/src/test/java/com/inttra/mercury/cloudsdk/notification/workflow/EventBuilderAnnotationsTest.java \
        cloud-sdk-api/src/test/java/com/inttra/mercury/cloudsdk/notification/workflow/WorkflowConstantsParityTest.java \
        cloud-sdk-api/src/test/java/com/inttra/mercury/cloudsdk/notification/workflow/WorkflowWireCompatTest.java \
        cloud-sdk-api/src/test/resources/wire/
git commit -m "ION-12310: W-G9 Event.Builder annotations round-trip + MetaData.Projection/Event.Token parity"

# 3) X-G7 + X-G10 (email reply-to + attachments; interleaved, one commit)
git add cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/email/api/MailContent.java \
        cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/MailContentImpl.java \
        cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImpl.java \
        cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/utils/EmailMimeUtils.java \
        cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailReplyToAndAttachmentTest.java \
        cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/email/impl/MailContentImplTest.java \
        cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/email/utils/EmailMimeUtilsMailContentTest.java
git commit -m "ION-12310: X-G7 replyTo + X-G10 raw-MIME attachment support on SES email"

# 4) C-G6 + config-substitution
git add commons/src/main/java/com/inttra/mercury/config/ConfigProcessingServerCommand.java \
        commons/src/main/java/com/inttra/mercury/config/PropertiesSubstitutionConfigProvider.java \
        commons/src/test/java/com/inttra/mercury/config/PropertiesSubstitutionConfigProviderTest.java \
        commons/src/test/resources/config/substitution-base.properties
git commit -m "ION-12310: C-G6 protected getConfigTransformer + PropertiesSubstitutionConfigProvider"

git --no-pager log --oneline -6   # verify 4 new commits sit on top of cc4a76d
```

**Option B — the design's per-gap branch → squash-merge workflow (§13.4, isolated & revertible):**
```bash
# For each gap: cut a branch from the tip, (changes already exist in the tree), commit, then
# squash-merge back so each gap becomes ONE commit on the feature branch.
git switch -c feature/ION-12310-sg2                 # branch from current tip
# ...stage that gap's files (as above)... then:
git commit -m "ION-12310: S-G2 ..."
git switch feature/ION-12310-commons-cloudsdk-refactoring
git merge --squash feature/ION-12310-sg2 && git commit -m "ION-12310: S-G2 StorageClient metadata/content-type"
# repeat for -wg9, -email (xg7+xg10), -config
```
*Why `--squash`:* collapses a gap branch's WIP commits into a single, cleanly-revertible commit on the shared branch. Commit messages carry **`ION-12310` only** (no appianway keys), per §13.1.

#### C.8.1 How `git merge --squash` actually works (mechanics, syntax & flow)

**The one-sentence model.** `git merge --squash <src>` computes the *same file changes* a normal merge would apply and writes them into your **working tree + staging area (index)**, but then **stops without creating a commit** and **without recording `<src>` as a parent**. You get "all the changes from that branch, staged, ready to become one brand-new commit of your choosing."

**Why it takes two commands.** A normal `git merge <src>` does two things at once: (a) updates the files, and (b) creates a *merge commit* whose history points back to both branches. `--squash` deliberately does only (a). That is why you always follow it with an explicit `git commit` — the merge left the changes staged but uncommitted on purpose, handing you the pen to write a single, clean commit message.

**Step-by-step of the two-command sequence:**
```bash
git switch feature/ION-12310-commons-cloudsdk-refactoring   # 1. stand ON the destination branch
git merge --squash feature/ION-12310-sg2                    # 2. stage the gap branch's net changes (no commit, no parent link)
git commit -m "ION-12310: S-G2 StorageClient metadata/content-type"   # 3. YOU create the single squashed commit
```
1. **`git switch <dest>`** — squash-merge always applies *into the branch you are currently on*. You must be on the feature branch first (the branch that will receive the one commit).
2. **`git merge --squash <src>`** — git finds the merge base (the common ancestor of the two branches), computes the cumulative diff `<src>` introduced since that base, applies it to your working tree, and `git add`s it (stages it). It writes a suggested message to `.git/SQUASH_MSG` but creates **no commit**. Crucially it does **not** advance any branch pointer and does **not** set `MERGE_HEAD`, so the resulting commit will have **one parent** (the feature tip), not two — the gap branch's individual WIP commits never appear in the feature branch's history.
3. **`git commit -m "…"`** — you turn the staged changes into exactly one commit with a curated `ION-12310` message. (Running `git commit` with no `-m` pre-fills the editor with the accumulated messages from `SQUASH_MSG`, which you can rewrite.)

**Visual of the flow.** Say the feature tip is `F` and the gap branch has WIP commits `a → b → c`:
```
before:            after `git merge --squash` + `git commit`:

feature ──● F                     feature ──● F ──● S   ("S" = ONE squashed commit = a+b+c combined)
           \                                 \
   sg2       ●─●─● (a b c)          sg2        ●─●─● (a b c)   ← branch still exists, now redundant; delete it
```
- `S` contains the *identical file contents* that `c` would have produced, but as a single commit authored right now.
- `S`'s parent is `F` only. There is **no merge commit** and **no link** to `a/b/c` — history stays linear and each gap is one atomic, revertible commit (`git revert S` cleanly backs out the whole gap).

**How it differs from the neighbours:**
| Command | Creates a commit? | Parents of result | History shape | WIP commits preserved? |
|---|:---:|---|---|---|
| `git merge <src>` (normal) | yes (auto) | two (merge commit) | branching, non-linear | yes (all of `a,b,c` visible) |
| `git merge --squash <src>` | **no — you commit** | **one** | **linear, one commit per gap** | **no — collapsed into `S`** |
| `git rebase` / cherry-pick | replays commits | one each | linear but **many** commits | yes (each replayed) |

**Conflicts.** If the gap branch's changes overlap something already on the feature tip, `git merge --squash` can still hit conflicts. It pauses with conflict markers in the working tree (exactly like a normal merge), you resolve + `git add` the files, and then run `git commit` yourself. Note there is **no `--continue`** step here — because no merge is "in progress" in the MERGE_HEAD sense, you simply finish by committing. (In this landing the gap branches are cut from the current tip and the tree is already correct, so conflicts are not expected.)

**Cleanup after each squash.** The gap branch has served its purpose once squashed in; delete it so it doesn't linger:
```bash
git branch -D feature/ION-12310-sg2     # -D because --squash leaves it "unmerged" in git's eyes
```
`git branch -d` (lowercase) would refuse, because from git's perspective the gap branch was never truly merged (no parent link was created) — its commits `a,b,c` are unreachable from the feature branch. `-D` (force) is the correct, expected way to remove a squashed branch.

**Applying it to all four gaps (full loop).** Repeat the cut → commit → squash → delete cycle per gap, in the order S-G2 → W-G9 → email(X-G7+X-G10) → config:
```bash
BASE=feature/ION-12310-commons-cloudsdk-refactoring

for gap in sg2 wg9 email config; do
  git switch -c feature/ION-12310-$gap $BASE      # branch from the *current* feature tip each time
  # ...git add ONLY that gap's files (see Option A lists)...
  git commit -m "ION-12310: $gap work"            # WIP commit(s) on the gap branch
  git switch $BASE                                # back to the feature branch
  git merge --squash feature/ION-12310-$gap       # stage the gap's net changes, no commit
  git commit -m "ION-12310: <clear per-gap message>"   # one squashed commit on the feature branch
  git branch -D feature/ION-12310-$gap            # remove the now-redundant gap branch
done

git --no-pager log --oneline -6                   # expect 4 new commits stacked on cc4a76d
```
> Re-cutting each gap branch from the *updated* feature tip (`$BASE` after the previous squash landed) keeps the four squashed commits stacked linearly and conflict-free. The result is identical in file content to Option A's direct commits — Option B just adds the extra isolation of developing/verifying each gap on its own branch before it touches the shared line.


### C.9 Push the feature branch **[TEMPLATE — not yet run; needs explicit approval]**
```bash
# Ordinary push (no rebase/force in this workflow — squash-merge just adds normal commits on the tip)
git push origin feature/ION-12310-commons-cloudsdk-refactoring
```
*Why:* pushing the shared feature branch is the only irreversible step, so it is intentionally left until the commits are reviewed. **No `--force`** is used here (a rebase is explicitly out of scope — §13.6).

### C.10 Rollback levers (if ever needed)
```bash
git reset --hard cc4a76d                                             # local: discard the gap commits
git reset --hard backup/feature-ION-12310-pre-sdk-gaps-2026-07-23    # local: restore the exact pre-work tip
git revert <gap-commit-sha>                                          # surgical: undo a single gap, keep the rest
```
*Why:* every gap is an independent commit, so a single `git revert` backs out exactly one gap; the backup branch (local **and** on origin) is the whole-landing escape hatch.
