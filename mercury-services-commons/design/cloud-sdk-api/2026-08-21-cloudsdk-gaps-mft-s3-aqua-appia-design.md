# cloud-sdk-api / cloud-sdk-aws Gap Closure for `mft-s3-aqua-appia` (aw-bridge IB/OB)

| Field | Value |
|---|---|
| Document date | 2026-08-21 |
| Jira | ION-12310 |
| Author | Cloud SDK refactoring agent (Copilot, Claude Opus 4.8) |
| Repository | `mercury-services-commons` |
| Branch | `feature/ION-12310-commons-cloudsdk-refactoring` |
| Target version | `1.0.32-SNAPSHOT` (`<dependency.version>` in root `pom.xml`) |
| Modules touched | `cloud-sdk-api`, `cloud-sdk-aws` |
| Drivers | `mft-s3-aqua-appia/aw-bridge-ib/docs/2026-08-20-aw-bridge-ib-current-state-design.md`, `mft-s3-aqua-appia/aw-bridge-ob/docs/2026-08-20-aw-bridge-ob-current-state-design.md` |
| Compatibility | **Additive, backward-compatible, non-breaking** (see §5) |

---

## 1. Executive Summary

The two Appian Way bridge modules (`aw-bridge-ib`, `aw-bridge-ob`) in the `mft-s3-aqua-appia`
workspace are migrating from **AWS Java SDK v1.12.716** to **AWS SDK 2.x** through the
`cloud-sdk-api` / `cloud-sdk-aws` libraries published by `mercury-services-commons`. Their
current-state design docs enumerate a set of **blocking prerequisites** — capabilities the bridges
rely on today that the cloud-sdk did not yet expose. Until they are closed, the bridge port either
cannot proceed or would have to regress behaviour (e.g. download every object body just to read
metadata).

This document specifies and records the closure of those gaps in `1.0.32-SNAPSHOT`. **Every change
is purely additive**: new `default` interface methods, new builder fields, and one new model class.
No existing signature, semantic, or wire behaviour changes, so every current consumer across the
`mercury-services` and `mft-s3-aqua-appia` workspaces continues to compile and run unchanged after a
straight recompile against `1.0.32-SNAPSHOT`.

`mercury-services-commons` is now consumed by most `mercury-services` modules and by
`mft-s3-aqua-appia`; preserving binary and source compatibility is therefore **paramount** and is
the governing constraint of every decision below.

---

## 2. Gap Inventory (from the bridge design docs)

| # | Gap (as stated by the bridge docs) | Consumer impact if unaddressed | Bridge doc reference |
|---|---|---|---|
| G1 | No `HeadObject`-style metadata read on `StorageClient` | `aw-bridge-ob` `BridgeTask` reads S3 user metadata on **every** message; `getObject().getMetadata()` would download the full object body twice per file | OB §11.2, §11.3(1) |
| G2 | No `File` + user-metadata `putObject` overload | `aw-bridge-ib` uploads an on-disk file **and** three user-metadata headers in one call, streaming from disk (no heap buffering for large EDI/PDF) | IB §11.3(1) |
| G3 | No `changeMessageVisibility` on `MessagingClient` | `aw-bridge-ob` adaptively extends SQS visibility for slow large-object downloads; losing it causes premature redelivery | OB §11.2, §11.3(2) |
| G4 | No per-message-attribute receive filter / attribute surface | `aw-bridge-ob` `SQSListenerClient` always requests the `failedAttempts` message attribute and reads it back for back-off accounting | OB §11.3(5) |
| G5 | No S3 event-notification model | `aw-bridge-ob` `S3EventParser` has nothing to bind the SQS-delivered S3 `ObjectCreated` JSON to (v1 `S3EventNotification.parseJson` is retired) | OB §11.2, §11.3(3) |
| G6 | `CloudParameterStore` has no batch `getParameters(String...)` with invalid-key detection | `aw-bridge-ob` `SsmParameterSupplier` uses an all-or-nothing batch `GetParameters` that fails fast on any unknown name | OB §11.3(4) |
| G7 | S3 metadata **key casing** on `HeadObject` (verification, not an API change) | Highest silent-failure risk during cut-over | OB §11.3(6), §4.1 |

---

## 3. Design Principles

1. **Additive only.** New capability arrives as `default` methods on existing interfaces, new
   builder setters, or brand-new classes. No existing method is removed, renamed, or has its
   contract changed. This mirrors the earlier **S-G2** wave (metadata/content-type write & copy
   overloads) already merged on this branch.
2. **Legacy implementors keep compiling.** Any third party (or test double) that implements
   `StorageClient`, `MessagingClient`, `QueueMessage`, or `CloudParameterStore` today must continue
   to compile without edits. Hence defaults with sensible fallbacks (G1, G2, G4, G6) or an explicit
   `UnsupportedOperationException` where no safe fallback exists (G3).
3. **Preserve performance characteristics.** G1 must be a true metadata-only `HeadObject`; G2 must
   stream from disk (`RequestBody.fromFile`), never buffer the payload in heap.
4. **Reuse existing infrastructure.** JSON parsing uses the shared `JsonSupport.OBJECT_MAPPER`;
   exception wrapping reuses `S3OperationException` / `MessagingException` / `ParameterStoreException`
   and the existing validation/`handle*` helpers in `AbstractStorageObject`.
5. **Thorough, edge-focused tests** aligned with the house framework: JUnit 5 (`@Nested`,
   `@ParameterizedTest`), AssertJ fluent assertions, Mockito. DynamoDB-touching behaviour is
   unchanged, so `dynamo-integration-test` is exercised only as a regression guard.

---

## 4. Detailed Design & Implementation Sequence

The work was executed in the order below. Each step compiles and its tests pass before the next
begins, so the branch is green at every commit boundary.

### Step 0 — Version bump

* `root pom.xml`: `<dependency.version>` `1.0.31-SNAPSHOT` → `1.0.32-SNAPSHOT`. All modules derive
  both their own version and inter-module dependency versions from this single property, so the
  reactor stays internally consistent.

### Step 1 — G1: `StorageClient.getMetadata(bucket, key)` (HeadObject)

**API (`cloud-sdk-api`)** — new `default` method on `StorageClient`:

```java
default Map<String, String> getMetadata(String bucketName, String key) {
    StorageObject object = getObject(bucketName, key);
    Map<String, String> metadata = object == null ? null : object.getMetadata();
    return metadata == null ? Map.of() : metadata;
}
```

The default preserves correctness for legacy implementors (fetches via `getObject`) but the
performance-correct path is the AWS override.

**Impl (`cloud-sdk-aws`)** — `S3StorageClient` overrides with a metadata-only `HeadObject`:

* Validates bucket/key via inherited `validateBucketName` / `validateKey`.
* Calls `s3Client.headObject(...)`, returns `response.metadata()` (never `null`; empty map when
  absent).
* Maps failures through the existing `handleNoSuchKeyException` / `handleS3Exception` /
  `handleSdkException` / `handleUnexpectedException` helpers → `S3OperationException`.

**Tests** — `S3StorageClientMetadataTest.GetMetadata`: reads metadata via HeadObject and asserts
`getObjectAsBytes` is **never** called (proving no body transfer); empty-metadata; `NoSuchKey` and
generic S3 error wrapping; blank-bucket validation. `StorageClientDefaultsTest`: default falls back
to `getObject().getMetadata()`, and is null-safe for a null object and null metadata.

### Step 2 — G2: `StorageClient.putObject(bucket, key, File, metadata, contentType)`

**API** — new `default` overload falling back to the metadata-less `putObject(bucket, key, File)`.

**Impl** — `S3StorageClient` override builds a `PutObjectRequest` with metadata/content-type applied
only when non-empty/non-blank (identical guard style to the existing byte[]/stream overloads) and
uploads with `RequestBody.fromFile(file)` — **stream-from-disk, no heap buffering**.

**Tests** — `S3StorageClientMetadataTest.PutFileWithMetadata` (uses `@TempDir`): asserts metadata +
content-type on the captured request and that the `RequestBody.optionalContentLength()` equals the
file length (streamed, not buffered); null metadata/content-type not applied; invalid/missing file
fails validation before any S3 call. `StorageClientDefaultsTest`: default overload delegates to
`putObject(File)`.

### Step 3 — G3: `MessagingClient.changeMessageVisibility(queueUrl, receiptHandle, seconds)`

**API** — new `default` method throwing `UnsupportedOperationException` (no safe generic fallback
exists for a broker visibility change), documented as override-required.

**Impl** — `SqsMessagingClient` overrides using `SqsClient.changeMessageVisibility(...)`; errors run
through the existing `handleException(...)` → `MessagingException`; `changeMessageVisibility` added
to the `OPERATION_DESCRIPTIONS` map for consistent unexpected-error messaging.

**Tests** — `SqsMessagingClientTest.ChangeMessageVisibilityTests`: captures the request
(queueUrl/receiptHandle/timeout) and asserts `QueueDoesNotExist` is wrapped as `MessagingException`.
`MessagingClientDefaultsTest`: default throws `UnsupportedOperationException`.

### Step 4 — G4: message-attribute receive support

**API** — `ReceiveMessageOptions` gains two builder fields, both defaulting to empty and null-normalised:
`messageAttributeNames` (custom attributes, e.g. `failedAttempts`) and `messageSystemAttributeNames`
(e.g. `ApproximateReceiveCount`, `SentTimestamp`). `QueueMessage` gains a new
`default Map<String,String> getMessageAttributes()` returning an empty map, so the pre-existing
`getAttributes()` (system attributes) keeps its exact semantics.

**Impl** — `SqsMessagingClient.receiveMessages(ReceiveMessageOptions)` now sets
`.messageAttributeNames(...)` and `.messageSystemAttributeNamesWithStrings(...)` only when the
corresponding lists are non-empty (unset ⇒ prior behaviour byte-for-byte). `SqsMessage` implements
`getMessageAttributes()` from `message.messageAttributes()` (string values), returned unmodifiable.

**Tests** — `ReceiveMessageOptionsTest`: defaults empty, retained, null-normalised, unmodifiable.
`SqsMessagingClientTest.ReceiveMessageAttributeNamesTests`: attribute names populate the request and
`getMessageAttributes()` surfaces `failedAttempts`; when unset, the request requests no attributes.
`SqsMessageTest`: message vs. system attribute separation, unmodifiability, empty case.
`MessagingClientDefaultsTest`: `getMessageAttributes()` default is empty.

### Step 5 — G5: S3 event-notification model

**API** — new package `com.inttra.mercury.cloudsdk.storage.event` with immutable, Jackson-bound
`S3EventNotification`:

* `static S3EventNotification parseJson(String json)` using `JsonSupport.OBJECT_MAPPER`; throws
  `IllegalArgumentException` on null/blank/malformed input.
* Nested `S3EventNotificationRecord` → `S3Entity` → `S3BucketEntity` / `S3ObjectEntity`.
* Every level is `@JsonIgnoreProperties(ignoreUnknown = true)` so future S3 fields never break
  parsing.
* `S3ObjectEntity.getKey()` returns the raw (URL-encoded) key; `getUrlDecodedKey()` returns the
  UTF-8 URL-decoded key (S3 encodes spaces as `+`). `getRecords()` is immutable; `firstRecord()`
  convenience for the common single-record S3→SQS case.

This is a drop-in replacement for the retired v1 `com.amazonaws.services.s3.event.S3EventNotification`
and validates against the bridge golden fixtures (`aw-bridge-ob/src/test/resources/s3_event*.json`).

**Tests** — `S3EventNotificationTest`: parses the canonical fixture (all modelled fields incl.
`eventTime` as `Instant`); ignores unknown properties at every level; multiple/zero/missing records;
URL-decoding of `+` and `%XX`; null-key decode; immutability; blank/null/malformed input.

### Step 6 — G6: `CloudParameterStore.getParameters(String...)` (batch, fail-fast)

**API** — new `default` method that loops `getParameter(name)`, preserves request order, and throws
`ParameterStoreException` listing **every** unknown name (all-or-nothing); `null` names ⇒
`IllegalArgumentException`.

**Impl** — `SsmCloudParameterStore` overrides with a true batched `GetParameters`, chunked at the AWS
limit of 10 names/request, aggregating `invalidParameters` across chunks and re-establishing request
order; `withDecryption(true)` matches `getParameter`. `SsmException` → `ParameterStoreException`.

**Tests** — `SsmCloudParameterStoreTest` (batch section): order re-established from an out-of-order
response; fail-fast lists invalid names; empty input short-circuits with no AWS call; null throws
IAE; >10 names chunked into two calls; `SsmException` wrapped. `CloudParameterStoreDefaultsTest`:
default loops, orders, fail-fast, null-guards.

### Step 7 — G7: metadata key-casing verification (no API change)

S3 lower-cases user-metadata keys on the wire. `HeadObjectResponse.metadata()` returns keys as
stored. The bridge writes `xlogid`, `originalfilename`, `inftpfilepickuptime` (already lower-case),
so round-tripping is safe. Unit tests assert the returned map preserves the keys the SDK provides;
**a real-bucket integration check remains a cut-over acceptance step for the bridge team** (localstack
or a cvt/int bucket), since it depends on live S3 semantics not reproducible with a mocked client.

---

## 5. Backward-Compatibility Analysis

| Change | Kind | Source-compat | Binary-compat | Risk |
|---|---|---|---|---|
| `StorageClient.getMetadata` | new `default` | ✅ | ✅ | none — legacy impls inherit fallback |
| `StorageClient.putObject(File,Map,String)` | new `default` | ✅ | ✅ | none — falls back to `putObject(File)` |
| `MessagingClient.changeMessageVisibility` | new `default` (throws) | ✅ | ✅ | callers must use an impl that overrides it; SQS impl does |
| `ReceiveMessageOptions` new fields | additive builder setters | ✅ | ✅ | none — default empty ⇒ identical request |
| `QueueMessage.getMessageAttributes` | new `default` (empty) | ✅ | ✅ | none — `getAttributes()` unchanged |
| `CloudParameterStore.getParameters` | new `default` | ✅ | ✅ | none — legacy impls inherit loop fallback |
| `storage.event.S3EventNotification` | new class | ✅ | ✅ | none |
| version bump | property | n/a | n/a | consumers recompile against `1.0.32-SNAPSHOT` |

No consumer requires source changes. Overriding implementations gain new capability transparently;
the AWS implementations in `cloud-sdk-aws` provide the performance-correct behaviour.

---

## 6. Test Strategy & Results

* **Frameworks:** JUnit 5 (`@Nested`, `@ParameterizedTest`, `@ValueSource`, `@MethodSource`),
  AssertJ (`assertThat` / `assertThatThrownBy`), Mockito (mocks, `ArgumentCaptor`, `thenCallRealMethod`
  / `doCallRealMethod` for default-method verification), `@TempDir` for file streaming.
* **New test classes:** `S3EventNotificationTest`, `StorageClientDefaultsTest`,
  `MessagingClientDefaultsTest`, `ReceiveMessageOptionsTest`, `CloudParameterStoreDefaultsTest`
  (api); `SqsMessageTest` (aws). **Extended:** `S3StorageClientMetadataTest`,
  `SqsMessagingClientTest`, `SsmCloudParameterStoreTest`.
* **Result:** `mvn -pl cloud-sdk-api,cloud-sdk-aws -am test` → **1076 tests, 0 failures, 0 errors**.
* **Full gate:** `mvn verify` across `cloud-sdk-api`, `cloud-sdk-aws`, `commons`,
  `dynamo-integration-test` (unit + `maven-failsafe-plugin` integration, incl. local DynamoDB) must
  be green before commit.

---

## 7. Bridge Adoption Notes (for the `mft-s3-aqua-appia` team)

Once consuming `1.0.32-SNAPSHOT`:

* **IB:** replace `S3Service` v1 `putObject(...).withMetadata(...)` with
  `StorageClient.putObject(bucket, key, file, metadataMap, contentType)` — streaming and the three
  user-metadata headers are preserved.
* **OB metadata read:** replace `getObjectMetadata(...).getUserMetadata()` with
  `StorageClient.getMetadata(bucket, key)` (single HeadObject, no double download).
* **OB visibility:** replace `amazonSQS.changeMessageVisibility(...)` with
  `MessagingClient.changeMessageVisibility(queueUrl, receiptHandle, seconds)`.
* **OB back-off attribute:** build `ReceiveMessageOptions` with
  `.messageAttributeNames(List.of("failedAttempts"))` and read it back via
  `QueueMessage.getMessageAttributes()`.
* **OB event parse:** replace v1 `S3EventNotification.parseJson(...)` with
  `com.inttra.mercury.cloudsdk.storage.event.S3EventNotification.parseJson(...)`, using
  `getUrlDecodedKey()` for filesystem/GetObject resolution. Validate against the existing
  `s3_event*.json` golden fixtures.
* **OB SSM:** replace the batched supplier with `CloudParameterStore.getParameters(names...)` — the
  all-or-nothing invalid-name semantics are preserved.
* **G7:** run a real-bucket metadata round-trip in cvt/int before production cut-over.

---

## 8. Appendix — Changed Files

| Concern | File |
|---|---|
| G1/G2 API | `cloud-sdk-api/.../storage/api/StorageClient.java` |
| G1/G2 impl | `cloud-sdk-aws/.../storage/impl/S3StorageClient.java` |
| G3 API | `cloud-sdk-api/.../messaging/api/MessagingClient.java` |
| G3/G4 impl | `cloud-sdk-aws/.../messaging/aws/impl/SqsMessagingClient.java`, `SqsMessage.java` |
| G4 API | `cloud-sdk-api/.../messaging/model/ReceiveMessageOptions.java`, `messaging/api/QueueMessage.java` |
| G5 API | `cloud-sdk-api/.../storage/event/S3EventNotification.java` (new) |
| G6 API | `cloud-sdk-api/.../paramstore/api/CloudParameterStore.java` |
| G6 impl | `cloud-sdk-aws/.../paramstore/impl/SsmCloudParameterStore.java` |
| Version | `pom.xml` (`<dependency.version>`) |
| Release note | `README.md` |
