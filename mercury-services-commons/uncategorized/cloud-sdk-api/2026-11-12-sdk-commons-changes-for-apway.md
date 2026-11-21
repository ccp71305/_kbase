# mercury-services-commons 1.0.39: cloud-sdk changes for AppianWay (WI01124532): progress and change log

> **Work item:** WI01124532 (AWS SDK Upgrade, AppianWay)
> **Specification:** `C:\Users\arijit.kundu\projects\appianway\docs\redesign\2026-11-11-sdk-commons-upgrade-specs.md` (revision 2026-11-12). It is the source of truth for every item: functional need, current code, technical change, tests and acceptance criteria.
> **Branch:** `feature/ION-12310-commons-cloudsdk-refactoring`. Work goes directly on it, with no sub-branches and no PRs per group. Start point: `c353706`.
> **Version:** `1.0.38-SNAPSHOT` → `1.0.39-SNAPSHOT` (first commit).
> **This file is local only.** `docs/` is gitignored. Never commit it, and never `git add -A`.
> **Who updates it:** the commons agent, after every commit.

---

## 0. Status summary

| Field | Value |
|---|---|
| Overall | **Done** (2026-11-12). All 12 steps committed: version bump, §2.3 flag, U3, U8, U9, U12, U2, U5, U13 (steps 1-3), U11 (incl. the optional SES part), U14, README note. U1, U4, U6, U7, U10 not touched |
| Commits | 22 on top of `c353706` (`91cde62` .. `aa52175`); full list in §8. Pushed to origin (fast-forward), not released |
| Last commit on branch | `aa52175` `WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT` |
| Last `mvn clean verify` | `61ebc1f`: green, **2695** tests, 0 failures/errors/skips (baseline at the version bump: 2601; +94 new tests: cloud-sdk-api +12, cloud-sdk-aws +82) |
| Installed locally (`mvn clean install`) | **yes**, at `aa52175`: BUILD SUCCESS, 2695 tests green. `com.inttra.mercury:{cloud-sdk-api, cloud-sdk-aws, commons, dynamo-client, email-sender, dynamo-integration-test}:1.0.39-SNAPSHOT` are in `~/.m2/repository` |
| Existing tests changed | Only the pre-approved `S3StorageClientGetObjectTest.testGetObjectSuccessfully` (U14; setup and HEAD verify only, assertions unchanged). Every other existing test is unchanged and green |
| Deviations | D1 (U9/U12 regression-guard form: the SDK reports its resolved default strategy, so "empty" is not observable), D2 (red-phase stubs), D3 (U11: one reset line in five config subclasses for "last call wins"). See §6 |
| Blockers / questions for Arijit | Q1, Q2 in §6 (none blocking) |

---

## 1. Backups taken before any change (2026-11-12)

| What | Where |
|---|---|
| commons local backup branch | `backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12` → `c353706` |
| commons bundle (feature branch, backup branch, develop; verified) | `C:\Users\arijit.kundu\backups\2026-11-12\commons-feature-ION-12310-c353706.bundle` |
| commons untracked docs | `C:\Users\arijit.kundu\backups\2026-11-12\commons-untracked-docs.tar.gz` (file list in `commons-untracked-docs.txt`) |
| AppianWay feature branch | branch `backup/WI01124532-aws-sdk-upgrade-pre-commons-u-items-2026-11-12` → `fa3efede`, bundle `appianway-WI01124532-aws-sdk-upgrade-fa3efede.bundle`, docs `appianway-untracked-docs.tar.gz` (same folder) |

Both feature branches matched `origin` (0 ahead / 0 behind) when the backups were taken.

**Restore commons:**
- `git reset --hard backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12`, or
- `git fetch <bundle> feature/ION-12310-commons-cloudsdk-refactoring:restored`

---

## 2. Scope and order (spec §1 and §5, decisions 2, 8 and 9)

Implement strictly in this order. Nothing outside this list: U1, U4, U6, U7 and U10 are **out**. U12 was added on 2026-11-12 (spec §5, decision 8), and so was the README release note (decision 9).

| # | Item | Short description | Spec section | Status | Commits |
|---|---|---|---|---|---|
| 1 | Version | root `pom.xml:20` `dependency.version` → `1.0.39-SNAPSHOT` (commit `WI01124532 ION-12310 build: commons 1.0.39-SNAPSHOT`) | §2.2 | Done | `91cde62` |
| 2 | §2.3 flag | `BaseAwsConfig.isRetryStrategyConfigured()` | §2.3 | Done (no refactor needed) | `025f398` red, `8129389` green |
| 3 | U3 | `StorageClient.getObjectSize` (default) + `S3StorageClient` HEAD override. **No** `getObjectProperties` | U3 | Done (no refactor needed) | `784af59` red, `74445d1` green |
| 4 | U8 | `EmailService.sendEmailWithResult` (2 defaults) + `SesEmailServiceImpl` | U8 | Done (no refactor needed) | `a87a1d5` red, `8d45475` green |
| 5 | U9 | `EmailClientFactory` applies `RetryStrategy` only when configured | U9 | Done (no refactor needed) | `9a884d9` red, `620c44c` green |
| 6 | U12 | `ParameterStoreClientFactory` applies `RetryStrategy` only when configured (same pattern as U9) | U12 | Done (no refactor needed) | `0ad8576` red, `37da891` green |
| 7 | U2 | zero-length puts (byte[], stream, String) | U2 | Done (no refactor needed) | `44de9af` red, `ba487cb` green |
| 8 | U5 | **new** `ReceiveMessageOptions.Builder.requestVisibilityTimeoutSeconds(int)`, sent on receive. The old `visibilityTimeoutSeconds(int)` is unchanged and never sent | U5 | Done (no refactor needed) | `cd343e2` red, `6cb949f` green |
| 9 | U13 | step 1: no access-key log, no eager credential resolution. Step 2: `createS3Client(config)` presigner uses the config region and provider. Step 3: `paramstore/main/Main.java:77` | U13 | Done (no refactor needed) | `de5485b` red, `6b91c33` green |
| 10 | U11 | `noClientExecutionTimeout()` on `BaseAwsConfigBuilder`; factories skip `apiCallTimeout` (SES part optional) | U11 | Done (no refactor needed; SES part done) | `fe7269b` red, `58f6a52` green |
| 11 | U14 | `getObject`: one GET, no HEAD | U14 | Done (no refactor needed) | `19762c8` red, `61ebc1f` green |
| 12 | README | root `README.md`: append `### Commons v1.0.39-SNAPSHOT`, brief and clear, describing the code as built (commit `WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT`) | §2.4 | Done | `aa52175` |

Status values: Not started · Red committed · Green committed · Done (refactor done or not needed) · Blocked (see §6).

---

## 3. Rules recap (spec §2)

- **Additive only.**
  - New interface methods are `default` methods: they delegate, or throw `UnsupportedOperationException`.
  - New switches are off by default, and an unconfigured client is byte-identical to today.
  - Never change a signature or return type, and never add a dependency.
  - Log changes are allowed only for U13.
- **Commit messages.** Every first line starts with **`WI01124532 ION-12310`**: the work item code and the Jira key, as in the last commit `c353706` (`WI01124532-xray-cve-fixes ION-12310 commons 1.0.38-SNAPSHOT: Xray CVE fixes`). Format: `WI01124532 ION-12310 <phase>: <summary>`.
- **TDD.** Each item gets `WI01124532 ION-12310 red: …`, then `WI01124532 ION-12310 green: …`, then `WI01124532 ION-12310 refactor: …` (only if needed). Use JUnit 5 + AssertJ + Mockito, one test class per unit.
- **Build.** `mvn clean verify` from the root after each green commit must be green.
- **Existing tests stay unchanged.** The **only** pre-approved exception is U14 `S3StorageClientGetObjectTest.testGetObjectSuccessfully`: move `contentLength`/`eTag` from the `headObject` stub to the `GetObjectResponse`, and replace the HEAD verify with `never()`. Assertions stay unchanged. Any other existing test change means stop and record it in §6.
- **Re-check file:line references** before each item (the spec was written against `c353706`).
- **Do not** push, release or deploy without asking.

---

## 4. mercury-services impact check (done 2026-11-12, spec §4)

`mercury-services` `develop` @ `53e77f4e8f`:

| Item | Finding | Consequence |
|---|---|---|
| U2 | Nothing relies on the empty-content exception. booking `S3WorkspaceServiceTest.putObject_emptyContent` already expects an empty-string put to succeed | In scope |
| U5 | bill-of-lading-v2 `QueueConfig.toReceiveMessageOptions()` calls `visibilityTimeoutSeconds(300)` (all environments); `BillOfLadingInjectorTest` asserts the getter. The value is never sent today (commons `SqsListener` builds its own options) | New name `requestVisibilityTimeoutSeconds`. The old method and getter stay unchanged |
| U13 step 2 | All presigned-URL users (network `ServerModule`, tx-tracking) use `createDefaultS3Client()`, which is untouched. `createS3Client(config)` users don't presign | In scope, no output change in mercury-services |
| U14 | No mercury-services code builds `S3StorageClient` or stubs `headObject`; nobody reads size/eTag from `getObject` | In scope. One commons test setup changes (pre-approved) |
| U9 | Every SES client is built by `createDefaultSesClient(..)` without a retry strategy (F-26) | No caller behaviour changes |
| booking (all items) | `putObject(String)` with JSON, `getObject` body-only reads, `copyObject`; booking on `createDefaultS3Client()`, cargoscreen on `createS3Client(config)` with us-east-1 and the default singleton; no presign (§10.2a, F-20..F-25) | No impact on any item |

---

## 5. Change log per item

Fill in one block per item as you go. Use repo-relative paths.

### 5.1 Version bump
- Files: `pom.xml` line 20 `dependency.version` `1.0.38-SNAPSHOT` → `1.0.39-SNAPSHOT` (the only declaration).
- Commit: `91cde62` `WI01124532 ION-12310 build: commons 1.0.39-SNAPSHOT`
- Build: `mvn clean verify` **green**, 2601 tests, 0 failures/errors/skips (cloud-sdk-api 158, dynamo-integration-test 6, cloud-sdk-aws 1105 + 149, commons 951, dynamo-client 27, email-sender 9, local-dynamodb 1, local-elasticsearch 2, wtg-federation 193). This is the **baseline** for later items.
- Note: the first run failed with ~315 `NoClassDefFoundError`s for cloud-sdk-aws **main** classes (`target/classes` emptied mid-run). Cause: the VS Code Java extension re-imports the Maven project after a `pom.xml` change and rebuilds `target/classes` while Maven runs. Not a code problem: the re-run on the same tree was green. If it recurs, wait for the IDE to finish building before running Maven.

### 5.2 §2.3 `isRetryStrategyConfigured()`
- Main changes (class → members): `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/BaseAwsConfig.java` → new field `private final boolean retryStrategyConfigured` (set from `builder.retryStrategy != null` **before** the null → commons-default line), new public `isRetryStrategyConfigured()` with Javadoc. `getRetryStrategy()` unchanged (still never null). Line refs re-checked: `retryStrategy(..)` 88-91, default at 39, as in the spec.
- Tests added (class → test methods): new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/aws/config/BaseAwsConfigTest.java`, `@Nested RetryStrategyConfigured`: `falseByDefault`, `trueWhenConfigured`, `falseWhenConfiguredWithNull`, `lastCallWins` (each also asserts `getRetryStrategy()` non-null). Built through `AwsStorageConfig.builder()`. U11 adds its own `@Nested` group to this class.
- Commits (red / green / refactor): `025f398` `WI01124532 ION-12310 red: BaseAwsConfig must record whether retryStrategy(..) was set` / `8129389` `WI01124532 ION-12310 green: BaseAwsConfig.isRetryStrategyConfigured() records an explicit retryStrategy(..)` / refactor not needed.
- Build (tests run / failures / skipped): `mvn clean verify` green, **2605** tests (cloud-sdk-aws 1109 = baseline 1105 + 4), 0 failures/errors/skips.
- Notes / deviations: **Red-commit convention (applies to every item):** where the red test calls an API that does not exist yet, the red commit also carries a minimal compile-only stub (marked `// red-phase stub: replaced in the green commit`; returns a neutral value or throws `UnsupportedOperationException`). The red commit then compiles and fails on assertions, instead of failing compilation. The green commit replaces the stub. Red failure here: `trueWhenConfigured` (1 of 4).

### 5.3 U3 `getObjectSize`
- Main changes:
  - `cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/storage/api/StorageClient.java` → new `default long getObjectSize(String bucketName, String key)`: `getObject(..)`, then `getSize()`, `0` when the object is null. Javadoc as spec.
  - `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java` → `@Override getObjectSize`, placed after `getMetadata`: validate bucket/key, one `headObject`, `contentLength()` or `0` when null, DEBUG log `Size retrieved for bucket='{}', key='{}', size={}`. Errors as `getMetadata`: `NoSuchKeyException` → `handleNoSuchKeyException`; `S3Exception` 404 → wrapped in a `NoSuchKeyException` (cause = the original) and passed to `handleNoSuchKeyException`, so the message is the same `Bucket %s does not contain key %s : ...`; other `S3Exception` → `handleS3Exception`; `SdkClientException` → `handleSdkException`; other → `handleUnexpectedException`. **No** `getObjectProperties`.
  - Line refs re-checked: `getMetadata` at 722-747, `objectExists` 404 comment at 919-920, as in the spec.
- Tests added:
  - new `cloud-sdk-api/src/test/java/com/inttra/mercury/cloudsdk/storage/api/StorageClientObjectSizeDefaultTest.java`: `defaultDelegatesToGetObjectSize`, `defaultReturnsZeroWhenObjectIsNull`.
  - new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientObjectSizeTest.java`: `Success` (`returnsContentLengthFromASingleHead`: one HEAD with the right bucket/key, `never()` `getObject`/`getObjectAsBytes`; `zeroLengthObjectReturnsZero`; `missingContentLengthReturnsZero`), `Errors` (`noSuchKeyMapsLikeGetMetadata`, `bare404IsTreatedAsMissingKey`, `otherS3ExceptionMapsLikeGetMetadata` (403), `sdkClientExceptionMapsLikeGetMetadata`; each compares type and message with `getMetadata`), `Validation` (null/blank bucket or key → IAE, `verifyNoInteractions`).
- Commits: `784af59` `WI01124532 ION-12310 red: getObjectSize must use a single HEAD` (13 tests red) / `74445d1` `WI01124532 ION-12310 green: StorageClient.getObjectSize with an S3 HEAD override` / refactor not needed.
- Build: `mvn clean verify` green, **2618** tests (cloud-sdk-api 160 = 158 + 2, cloud-sdk-aws 1120 = 1109 + 11), 0 failures/errors/skips.
- Notes / deviations: none.

### 5.4 U8 `sendEmailWithResult`
- Main changes:
  - `cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/email/api/EmailService.java` → two new default methods: `sendEmailWithResult(from, to, cc, bcc, content)` throws `UnsupportedOperationException("sendEmailWithResult is not supported by this EmailService implementation")` (does **not** fall back to the `void` method); `sendEmailWithResult(from, to, content)` delegates to the 5-argument form with `null` cc/bcc. Javadoc on both.
  - `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImpl.java` → the body of `sendEmail(from, to, cc, bcc, content)` moved unchanged into new `@Override sendEmailWithResult(from, to, cc, bcc, content)`, which returns `EmailSendResult.builder().messageId(response.messageId()).emailAddress(String.join(",", to)).build()`. `sendEmail(5 args)` now calls `sendEmailWithResult(..)` and discards the result. `sendEmail(3 args)`, `sendTemplatedEmail`, `sendTemplateEmail` untouched. The 3-argument `sendEmailWithResult` is the interface default (delegates to the 5-argument override). Validation, exception types/messages and log lines are the same.
  - Line refs re-checked: `EmailService.java:25/40`, `SesEmailServiceImpl.java:118-151`, response at 140-141, as in the spec.
- Tests added:
  - new `cloud-sdk-api/src/test/java/com/inttra/mercury/cloudsdk/email/api/EmailServiceSendWithResultDefaultTest.java`: `fiveArgumentDefaultThrowsUnsupportedOperation` (exact message; `void sendEmail` never called), `threeArgumentDefaultDelegatesWithNullCcAndBcc`.
  - new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImplSendWithResultTest.java`: `Result` (`returnsSesMessageIdAndJoinedRecipients` → `"abc"`, `"a@x.com,b@y.com"`; `threeArgumentFormReturnsSesMessageIdWithoutCcOrBcc`), `SameRequestAsSendEmail` (`simplePathRequestIsIdentical` and `threeArgumentFormRequestIsIdentical`: captured `SendEmailRequest`s are `equals`, incl. reply-to; `rawMimePathRequestIsEquivalent`: from, destination, empty reply-to on the request, and parsed MIME subject/from/reply-to/to/cc are equal; raw bytes are not compared because Message-ID, Date and boundary are generated per call), `Errors` (`SdkClientException` / `SdkServiceException` / other → `SendEmailException` with the same message and cause as `sendEmail`), `Validation` (blank sender, empty recipients, missing subject → IAE, no SDK call), `VoidSendEmailUnchanged` (5- and 3-arg `sendEmail` call the SDK exactly once).
- Commits: `a87a1d5` `WI01124532 ION-12310 red: sendEmailWithResult must return the SES message id` (13 red; the 2 `VoidSendEmailUnchanged` guards pass) / `8d45475` `WI01124532 ION-12310 green: EmailService.sendEmailWithResult returns the SES message id` / refactor not needed.
- Build: `mvn clean verify` green, **2633** tests (cloud-sdk-api 162 = 160 + 2, cloud-sdk-aws 1133 = 1120 + 13). Existing `SesEmailServiceImplTest` (23) and `SesEmailReplyToAndAttachmentTest` (9) unchanged and green.
- Notes / deviations: none.

### 5.5 U9 SES retry strategy
- Main changes: `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/factory/EmailClientFactory.java` → in `createSesV2Client`'s `overrideConfiguration` lambda, after the unchanged timeout block: `if (config.isRetryStrategyConfigured()) { overrideBuilder.retryStrategy(config.getRetryStrategy()); }`. Javadoc on both `createSesClient(..)` overloads: strategy applied when set, otherwise the AWS SDK default (unchanged), with the `doNotRetry()` example. Line refs re-checked: `createSesV2Client` 136-155, lambda 147-152, as in the spec.
- Tests added: new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/email/factory/EmailClientFactoryRetryStrategyTest.java` (reads `SesEmailServiceImpl.sesClient` by reflection, then `serviceClientConfiguration().overrideConfiguration()`): `doNotRetryReachesTheClient` (maxAttempts 1), `customStandardStrategyReachesTheClient` (maxAttempts 2), `unconfiguredClientKeepsTheAwsSdkDefault` (regression guard, see deviation D1), `timeoutsAreUnchangedWhenARetryStrategyIsSet` (apiCallTimeout and apiCallAttemptTimeout = configured value). The flag tests are in `BaseAwsConfigTest` (§5.2).
- Commits: `9a884d9` `WI01124532 ION-12310 red: EmailClientFactory must apply a configured retry strategy` (2 red: got 4 attempts instead of 1 and 2) / `620c44c` `WI01124532 ION-12310 green: EmailClientFactory applies the retry strategy only when configured` / refactor not needed.
- Build: `mvn clean verify` green, **2637** tests (cloud-sdk-aws 1137 = 1133 + 4), 0 failures/errors/skips.
- Notes / deviations: **D1** (§6): the spec's regression guard "no `retryStrategy` → `overrideConfiguration().retryStrategy()` is empty" cannot hold on AWS SDK 2.30: the built client's `serviceClientConfiguration().overrideConfiguration()` always reports the strategy the SDK resolved (here the legacy strategy, 4 attempts). The guard instead compares with a client built directly from `SesV2Client.builder()` with no strategy (same strategy class and max attempts) and, when the resolved retry mode is LEGACY, asserts 4 attempts (so the commons standard default, 3 attempts, is not applied). Existing `EmailClientFactoryTest` unchanged and green.

### 5.5a U12 SSM retry strategy
- Main changes: `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactory.java` → the `overrideConfiguration` lambda became a block: `b.apiCallTimeout(config.getClientExecutionTimeout())` (unchanged), then `if (config.isRetryStrategyConfigured()) { b.retryStrategy(config.getRetryStrategy()); }`. Javadoc on `createParameterStore`. Line refs re-checked: 26-38, lambda 31-32, as in the spec. U11 edits the same lambda later.
- Tests added: new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactoryRetryStrategyTest.java` (real `AwsParameterStoreConfig` builder, static credentials, `clientExecutionTimeout(12s)`; reads `SsmCloudParameterStore.ssmClient` by reflection): `doNotRetryReachesTheClient` (1 attempt), `customStandardStrategyReachesTheClient` (2 attempts), `unconfiguredClientKeepsTheAwsSdkDefault` (regression guard as U9, deviation D1); `apiCallTimeout()` = 12 s in all three.
- Existing tests (`CloudParameterStoreClientFactoryTest`, `AllFactoriesBuilderModeTest`) unchanged and green? : **yes** (2 and 14 tests). Mockito config mocks return `false` for the new flag, as predicted in spec §4.5.
- Commits: `0ad8576` `WI01124532 ION-12310 red: ParameterStoreClientFactory must apply a configured retry strategy` (2 red) / `37da891` `WI01124532 ION-12310 green: ParameterStoreClientFactory applies the retry strategy only when configured` / refactor not needed.
- Build: `mvn clean verify` green, **2640** tests (cloud-sdk-aws 1140 = 1137 + 3), 0 failures/errors/skips.
- Notes / deviations: D1 applies (regression guard form).

### 5.6 U2 zero-length puts
- Main changes:
  - `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/AbstractStorageObject.java` → `validateContent(byte[])` rejects only `null` (same `CONTENT_VALIDATION_MESSAGE`). `validateInputStream(InputStream, long)`: `null` → `CONTENT_VALIDATION_MESSAGE`; `< 0` → `CONTENT_LENGTH_VALIDATION_MESSAGE`; `> Integer.MAX_VALUE` unchanged; `== 0` → accepted with no `available()`/mark/read probe; `> 0` → today's probe unchanged. Javadoc on both. `validateFile` untouched.
  - `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java` → `putObject(String, String, String)` rejects only `null` content (message text unchanged); `""` and whitespace-only strings are uploaded as is (`text/plain; charset=UTF-8`). Javadoc updated. No change to the `RequestBody` calls: `fromBytes(new byte[0])`, `fromInputStream(in, 0)` and `fromString("")` already give a body with `Content-Length: 0` (asserted through `optionalContentLength()`).
  - Line refs re-checked: `validateContent` 48-52, `validateInputStream` 70-94 as in the spec; the String `putObject` moved from 760 to 806 because of U3 (+46 lines).
- Tests added: new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientZeroLengthPutTest.java`: `Bytes` (`emptyArrayIsWritten`, `emptyArrayWithMetadataAndContentTypeIsWritten`, `nullArrayIsStillRejected`), `Streams` (`emptyNonMarkableStreamIsWritten`, `emptyNonMarkableStreamWithMetadataAndContentTypeIsWritten` (both with a `FilterInputStream` whose `markSupported()` is false), `nullStreamIsStillRejected`, `negativeLengthIsStillRejected`), `Strings` (`emptyOrBlankStringIsWrittenAsIs` for `""` and `"  "`: content type and exact bytes; `nullStringIsStillRejected`). Each write test checks one `putObject`, bucket/key, `optionalContentLength() == 0` and an empty body; the metadata variants also check `contentLength`, metadata and content type.
- Commits: `44de9af` `WI01124532 ION-12310 red: putObject must accept zero-length content` (6 red; the 4 null/negative guards pass) / `ba487cb` `WI01124532 ION-12310 green: putObject writes zero-length content as an empty object` / refactor not needed.
- Build: `mvn clean verify` green, **2650** tests (cloud-sdk-aws 1150 = 1140 + 10), 0 failures/errors/skips.
- Notes / deviations: the spec says "null stream / negative length → `IllegalArgumentException` (unchanged)". The **unchanged** behaviour of both stream overloads is an `S3OperationException` whose cause is the `IllegalArgumentException` (they validate inside their `try`, and `handleUnexpectedException` wraps it; the existing `S3StorageClientPutObjectTest` asserts exactly that). The new tests assert that existing behaviour; nothing was changed there. Existing `S3StorageClientPutObjectTest` (62, incl. `testPutObjectWithClosedInputStream` for a positive length) unchanged and green.

### 5.7 U5 `requestVisibilityTimeoutSeconds`
- Main changes:
  - `cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/messaging/model/ReceiveMessageOptions.java` → new field `private final Integer requestedVisibilityTimeoutSeconds` with `@Getter(AccessLevel.NONE)` (null = not requested); new getters `isVisibilityTimeoutRequested()` and `getRequestedVisibilityTimeoutSeconds()` (`OptionalInt`); `Builder`: new field, private constant `MAX_VISIBILITY_TIMEOUT_SECONDS = 43200`, new `requestVisibilityTimeoutSeconds(int)` (IAE outside 0..43200, message `Visibility timeout must be in 0..43200 seconds, was <n>`). **Unchanged:** `visibilityTimeoutSeconds(int)` (no validation, still not sent; only a Javadoc sentence added: "Stored only; not sent on receive. Use `requestVisibilityTimeoutSeconds(int)` ...") and `getVisibilityTimeoutSeconds()` (int, default 30).
  - `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsMessagingClient.java` → `receiveMessages(ReceiveMessageOptions)`: `options.getRequestedVisibilityTimeoutSeconds().ifPresent(requestBuilder::visibilityTimeout)` before `build()`. `listMessages`, `receiveMessages(String,int,int)` and `SqsListener.createReceiveMessageOptions()` untouched.
  - Line refs re-checked: builder field at `ReceiveMessageOptions.java:42`, `receiveMessages(options)` at `SqsMessagingClient.java:264-298`, `listMessages` 193, `receiveMessages(String,int,int)` 238, as in the spec.
- Tests added:
  - new `cloud-sdk-api/src/test/java/com/inttra/mercury/cloudsdk/messaging/model/ReceiveMessageOptionsRequestVisibilityTest.java`: `notRequestedByDefault` (false, empty, old getter 30), `requestedValueIsKept` (0, 45, 43200), `outOfRangeIsRejected` (-1, 43201), `oldBuilderMethodIsStoredButNotRequested` (300: bill-of-lading-v2 regression guard), `bothMethodsAreIndependent`.
  - new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsMessagingClientReceiveVisibilityTest.java` (captures the `ReceiveMessageRequest`): `notRequestedSendsNoVisibilityTimeout`, `oldBuilderValueIsStillNotSent` (300 → null), `requestedValueIsSent` (0, 45), `otherFieldsAreUnchanged` (request minus visibility equals the expected request with queue URL, max messages, wait time, message and system attribute names).
  - Existing `ReceiveMessageOptionsTest` (4), `SqsMessagingClientTest`, `SqsListenerTest` unchanged and green.
- Commits: `cd343e2` `WI01124532 ION-12310 red: receive must send VisibilityTimeout only when requested` (8 red, with red-phase stubs) / `6cb949f` `WI01124532 ION-12310 green: ReceiveMessageOptions.requestVisibilityTimeoutSeconds is sent on receive` / refactor not needed.
- Build: `mvn clean verify` green, **2663** tests (cloud-sdk-api 170 = 162 + 8, cloud-sdk-aws 1155 = 1150 + 5), 0 failures/errors/skips.
- Notes / deviations: none. The spec named the test class `ReceiveMessageOptionsTest`; that class already exists, so the new tests are in a new class, leaving the existing file untouched.

### 5.8 U13 access-key log and presigner
- Main changes (step 1, step 2, step 3):
  - **Step 1** `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java` → `protected static createPresigner()` now returns `createPresigner(DefaultCredentialsProvider.create())`. New package-private `static S3Presigner createPresigner(AwsCredentialsProvider)`: one DEBUG line `Creating S3Presigner with provider {}` (simple class name only), then `S3Presigner.builder().region(StorageConfigConstants.DEFAULT_REGION).credentialsProvider(provider).build()`. Removed: the eager `resolveCredentials()` call, the two INFO lines (`Resolved AWS credentials using provider: {}`, `Using Access Key ID: {}`) and the two WARN lines of its catch blocks; unused import `AwsCredentials` → `AwsCredentialsProvider`. Constructors unchanged. No `close()` added.
  - **Step 2** `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/factory/StorageClientFactory.java` → `createS3Client(config)` builds `S3Presigner` with `config.getRegion().getRegionDelegate()` and `config.getCredentialsProvider().getCredentialProviderDelegate()` and uses the existing `S3StorageClient(S3Client, S3Presigner)` constructor. Javadoc states the region/provider source and the guard rule (the presigner shares the caller's provider; the client never closes its presigner). `createDefaultS3Client()` unchanged. No `endpointOverride` passed (follow-up F1).
  - **Step 3** `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/paramstore/main/Main.java` → removed line 77 `log.info("Access Key ID: " + credentials.accessKeyId().substring(0, 20) + "...")`. (Note: an access key id is 20 characters, so that "prefix" was the whole key.)
  - Line refs re-checked: `createPresigner()` at `S3StorageClient.java:99-114`, INFO lines 103-104, `Main.java:77`, as in the spec.
- Tests added:
  - new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientConstructionTest.java` (Logback `ListAppender` on the `S3StorageClient` logger): `creatingThePresignerResolvesNoCredentials` (counting provider: 0 calls), `constructorLogsNoAccessKeyId` (no event contains `Access Key` or `Resolved AWS credentials`), `credentialsAreResolvedOnlyWhenAUrlIsSigned` (0 calls after construction, > 0 after `generatePresignedUrl`, URL carries `X-Amz-Credential=AKIDEXAMPLE/`).
  - new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/factory/StorageClientFactoryPresignerTest.java` (offline signing, static `AKIDEXAMPLE`): `urlIsSignedForTheConfiguredRegionAndCredentials` (eu-west-1: host contains `eu-west-1`, credential scope `/eu-west-1/s3/aws4_request`), `usEast1ConfigIsStillSignedForUsEast1`, `defaultClientIsUnchanged` (`createDefaultS3Client()` → `/us-east-1/s3/`; sets `aws.accessKeyId`/`aws.secretAccessKey` system properties for the test so the default chain resolves on a machine without credentials, and restores them).
  - Existing `S3StorageClientGeneratePresignedUrlTest`, `StorageClientFactoryTest` unchanged and green.
- Commits: `de5485b` `WI01124532 ION-12310 red: S3 presigner must not resolve credentials eagerly and must use the config region` (4 red; the red commit adds a package-private `createPresigner(AwsCredentialsProvider)` stub with the old eager behaviour) / `6b91c33` `WI01124532 ION-12310 green: no access key id log, lazy presigner credentials, createS3Client presigner from config` / refactor not needed.
- Build: `mvn clean verify` green, **2669** tests (cloud-sdk-aws 1161 = 1155 + 6), 0 failures/errors/skips.
- Notes / deviations:
  - `constructorLogsNoAccessKeyId` passed in the red run too, because this build machine has no default-chain credentials (the old code then logged a WARN and never reached the key-id line). The counting-provider test is the one that proves step 1 independent of the machine.
  - Observation, not changed (out of scope): `AwsCredentialsProviderWrapper.getAccessKeyId()` / `getSecretAccessKey()` (`cloud-sdk-aws/.../aws/config/AwsCredentialsProviderWrapper.java:47-55`) still resolve and return the raw values. They are API getters (from `CredentialsProvider` in cloud-sdk-api), not log lines, and no main code calls them.

### 5.9 U11 `noClientExecutionTimeout()`
- Main changes (per factory):
  - `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/BaseAwsConfig.java` → new `private final boolean clientExecutionTimeoutDisabled` + `isClientExecutionTimeoutDisabled()` (Javadoc); builder: new `protected boolean clientExecutionTimeoutDisabled`, new `noClientExecutionTimeout()` (sets the flag, clears the base `clientExecutionTimeout`), and `clientExecutionTimeout(Duration)` now also clears the flag (last call wins). `getClientExecutionTimeout()` unchanged (non-null; 30 s default for S3).
  - **Config subclasses** `AwsMessagingClientConfig`, `NotificationClientConfig`, `DynamoDbClientConfig`, `AwsParameterStoreConfig`, `AwsSesEmailConfig` (all under `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/<area>/config/`): each **shadows** `clientExecutionTimeout(Duration)` with its own builder field and method, which never reaches the base builder. One line added to each: `this.clientExecutionTimeoutDisabled = false;`, so "last call wins" holds for every config (see note).
  - `storage/factory/S3ClientFactory.createOverrideConfig`: rewritten onto one `ClientOverrideConfiguration.Builder` (same retry-strategy logic and WARN), `apiCallTimeout` only when not disabled. Output for an unchanged config is identical.
  - `messaging/factory/MessagingClientFactory.createOverrideConfig` (used by `createConfiguredClient` and `createExtendedSqsClient`) and `notification/factory/NotificationClientFactory.createOverrideConfig`: the `clientExecutionTimeout` block (validate + `apiCallTimeout`) wrapped in `if (!config.isClientExecutionTimeoutDisabled())`. `requestTimeout` → `apiCallAttemptTimeout` and the retry strategy unchanged.
  - `database/factory/DynamoRepositoryFactory.createOverrideConfig`: only the `clientExecutionTimeout` branch is skipped; an explicit `apiCallTimeout` / `apiCallAttemptTimeout` / retry mode still applies.
  - `paramstore/factory/ParameterStoreClientFactory.createParameterStore`: `apiCallTimeout` only when not disabled (U12's retry block unchanged).
  - **SES (optional part): done.** `email/factory/EmailClientFactory.createSesV2Client`: when disabled, neither `apiCallTimeout` nor `apiCallAttemptTimeout` is set (both come from the same SES `clientExecutionTimeout`). Done because `noClientExecutionTimeout()` is inherited by `AwsSesEmailConfig.Builder` anyway; ignoring it there would be a trap.
  - Line refs re-checked: `BaseAwsConfig` 28-40/103, `S3ClientFactory` 86-98, `MessagingClientFactory` 127-149 / `validateDuration` 231, `NotificationClientFactory` 114-137 / 221, `DynamoRepositoryFactory` 353-368, `EmailClientFactory` 136-155 (lambda now 147-156 after U9); `ParameterStoreClientFactory` lambda moved by U12.
- Tests added:
  - `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/aws/config/BaseAwsConfigTest.java` (created in §5.2) → new `@Nested ClientExecutionTimeoutDisabled`: `falseByDefault` (30 s), `trueAfterNoClientExecutionTimeout` (getter still 30 s), `laterTimeoutReEnables` (5 s).
  - new `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/aws/config/NoClientExecutionTimeoutFactoryTest.java`, `@Nested` per factory, inspecting the built client's `serviceClientConfiguration().overrideConfiguration()` (reflection on the private client field) or, for DynamoDB, the public `createOverrideConfig`: `S3` (default 30 s; disabled → empty, retry strategy kept (2 attempts); later timeout 5 s), `Sqs` (default = config value; disabled → empty, attempt timeout 3 s and max attempts kept; later 5 s), `Sns` (same shape), `Ssm` (default 10 s; disabled → empty with `doNotRetry` kept; later 5 s), `DynamoDb` (default; disabled → empty; explicit `apiCallTimeout(20s)` / `apiCallAttemptTimeout(4s)` still apply; later 5 s), `Ses` (default 10 s/10 s; disabled → both empty; later 5 s/5 s).
- Commits: `fe7269b` `WI01124532 ION-12310 red: noClientExecutionTimeout() must leave the API-call timeout unset` (7 red, with red-phase stubs) / `58f6a52` `WI01124532 ION-12310 green: noClientExecutionTimeout() lets the factories set no API-call timeout` / refactor not needed.
- Build: `mvn clean verify` green, **2691** tests (cloud-sdk-aws 1183 = 1161 + 22), 0 failures/errors/skips. Existing factory/config tests (`AllFactoriesBuilderModeTest`, `MessagingClientFactoryTest`, `EmailClientFactoryTest`, `CloudParameterStoreClientFactoryTest`, `*ConfigTest`) unchanged and green.
- Notes / deviations:
  - **D3** (§6): spec step 1 assumed one builder field. Five config subclasses shadow `clientExecutionTimeout(Duration)`; without the one-line reset in each, `noClientExecutionTimeout().clientExecutionTimeout(5s)` would stay disabled for SQS/SNS/DynamoDB/SSM/SES. The added line runs only on that builder call and changes nothing unless `noClientExecutionTimeout()` was called first.
  - For those subclasses, `noClientExecutionTimeout()` clears only the base field, so a subclass value set **before** it (e.g. `clientExecutionTimeout(7s).noClientExecutionTimeout()`) is still returned by `getClientExecutionTimeout()`, but no API-call timeout is applied. Readers of the getter see a non-null value either way, as the spec requires.

### 5.10 U14 `getObject` single GET
- Main changes: `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java` → `getObject`: the `headObject` call is removed. `GetObjectResponse response = objectContent.response()`; `size = response.contentLength()`, or the body length when the GET carries no Content-Length; the `S3Object` gets `.size(size)`, `.eTag(response.eTag())`, `.lastModified(response.lastModified())`. The INFO `Object retrieved successfully ... size={} bytes` line keeps its text and level and now logs `size` (same value). Error handling unchanged. Content type and user metadata already came from the GET (`S3StorageObject`). Line refs re-checked: `getObject` was at 548-590 in the spec (GET then HEAD, as described); after this change it starts at line 556.
- Existing test changed (pre-approved): `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientGetObjectTest.java` → `testGetObjectSuccessfully`: (a) `contentLength(TEST_CONTENT_BYTE_ARRAY.length)` and `eTag("etag123")` moved from the `HeadObjectResponse` onto the `GetObjectResponse` given to `ResponseBytes.fromByteArray`; (b) the `HeadObjectResponse` variable and the `headObject` stub deleted; (c) `verify(s3ClientMock).headObject(argThat(..bucket/key..))` replaced with `verify(s3ClientMock, never()).headObject(any(HeadObjectRequest.class))`. The four assertions (key, size, eTag, content) and the GET verify are unchanged. The now-unused `HeadObjectResponse` import was removed; `never`, `times`, `Instant`, `Map` imports added for the new tests. No other existing test changed.
- Tests added (appended to `S3StorageClientGetObjectTest`, as the spec asks): `getObjectMakesOneGetAndNoHead` (`times(1)` GET, `never()` HEAD), `getObjectTakesEveryFieldFromTheGetResponse` (size, eTag, lastModified, contentType, metadata, content), `sizeFallsBackToTheBodyLengthWhenTheGetCarriesNoContentLength`, `errorMappingIsUnchangedAndNoHeadIsMade` (`NoSuchKeyException`, `S3Exception` 403, `SdkClientException` → `S3OperationException`, no HEAD).
- Commits: `19762c8` `WI01124532 ION-12310 red: getObject must make one GET and no HEAD` (commit body records the pre-approved test change; 4 red: NPE on the missing HEAD stub) / `61ebc1f` `WI01124532 ION-12310 green: getObject builds the result from the GET response, no extra HEAD` / refactor not needed.
- Build: `mvn clean verify` green, **2695** tests (cloud-sdk-aws 1187 = 1183 + 4), 0 failures/errors/skips.
- Notes / deviations: none. Out of scope, noted: `getObject` still buffers the whole body (`getObjectAsBytes`); a streaming variant would be a new method.

### 5.11 README release note
- Section added (`### Commons v1.0.39-SNAPSHOT`): **yes**, appended after `### Commons v1.0.38-SNAPSHOT` (45 lines, CRLF like the rest of the file). `Latest release version` line and earlier sections untouched.
- Differences from the spec §2.4 draft, and why (each line checked against the final code):
  - (1) adds "a bare 404 is reported as a missing key" and the interface default (`getObject(..).getSize()`).
  - (2) adds "(with and without cc/bcc)" and that the interface default throws `UnsupportedOperationException`, so test fakes must implement it (mercury-services and AppianWay fakes compile but would fail at call time).
  - (5) lists **SES** too (the optional part was done), says SES then sets no attempt timeout either, that an explicit DynamoDB `apiCallTimeout(..)` still applies, that a later `clientExecutionTimeout(..)` turns it back on, and names `isClientExecutionTimeoutDisabled()`.
  - (7) adds that the `paramstore` `Main` utility no longer logs the key.
  - (8) "it was rejected as invalid input" instead of "threw `IllegalArgumentException`": the stream overloads report it as an `S3OperationException` caused by the `IllegalArgumentException` (see §5.6).
  - (3), (4), (6), (9): as drafted.
- Commit: `aa52175` `WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT` (only `README.md` staged). No build needed for a README-only commit; the `mvn clean install` below runs on it.

---

## 6. Deviations, blockers and open questions

| # | Item | Description | Raised | Resolution |
|---|---|---|---|---|
| D1 | U9, U12 | Spec regression guard "unconfigured client → `overrideConfiguration().retryStrategy()` is empty" is not observable on AWS SDK 2.30: the built client always reports the SDK-resolved strategy (legacy, 4 attempts, unless `AWS_RETRY_MODE`/profile says otherwise) | 2026-11-12 | Test deviation only (no code impact). Guard compares with a reference client built directly from the SDK with no strategy (same class, same max attempts), plus 4 attempts when the default retry mode is LEGACY. Proves the factory sets nothing and the commons default is not applied |
| D2 | process | Red commits carry compile-only stubs where the new API does not exist yet (see §5.2 notes) | 2026-11-12 | Convention, so red commits compile and fail on assertions |
| D3 | U11 | SQS, SNS, DynamoDB, SSM and SES configs shadow `clientExecutionTimeout(Duration)`; "last call wins" needs one reset line in each of their builder methods | 2026-11-12 | Added (additive; no effect unless `noClientExecutionTimeout()` was called). See §5.9 notes |
| Q1 | release | Push the 22 commits on `feature/ION-12310-commons-cloudsdk-refactoring` and publish 1.0.39-SNAPSHOT? | 2026-11-12 | Pushed 2026-11-12 on approval (fast-forward `c353706..aa52175`; existing PR #29 to develop). Not released or deployed |
| Q2 | U13 | `AwsCredentialsProviderWrapper.getAccessKeyId()` / `getSecretAccessKey()` still expose raw credentials as API getters (not logged anywhere in commons). Leave, or deprecate in a later release? | 2026-11-12 | Open, not in 1.0.39 scope |
| N1 | build | First `mvn clean verify` after the pom change failed with `NoClassDefFoundError`s because the VS Code Java extension rebuilt `target/classes` during the run; re-run green. To avoid it, let the IDE finish its Maven import before running Maven | 2026-11-12 | Environment only |

---

## 7. Follow-ups noted (not in 1.0.39)

| # | Topic | Note |
|---|---|---|
| F1 | U13 presigner `endpointOverride` | Step 2 passes region and provider only. A config with `endpointOverride` (for example LocalStack) still presigns against AWS endpoints |
| F2 | ~~U12 SSM retry strategy~~ | Moved into 1.0.39 on 2026-11-12 (spec decision 8); see §2 row 6 |
| F3 | U7, U10, U6, U4, U1 | Later commons release |
| F4 | U14 streaming read | `getObject` still buffers the whole body (`getObjectAsBytes`); a streaming variant would be a new method |
| F5 | AppianWay | Follow spec §6: bump `mercury.commons.version` to `1.0.39-SNAPSHOT`, then 1d (U3, U2, U14, U5, U11), email-sender (U8, U9), functional-testing fakes (`getObjectSize`, `sendEmailWithResult`) |

---

## 8. Commit log (newest last)

| # | Commit | Message | Item | Phase |
|---|---|---|---|---|
| 1 | `91cde62` | `WI01124532 ION-12310 build: commons 1.0.39-SNAPSHOT` | Version | build |
| 2 | `025f398` | `WI01124532 ION-12310 red: BaseAwsConfig must record whether retryStrategy(..) was set` | §2.3 | red |
| 3 | `8129389` | `WI01124532 ION-12310 green: BaseAwsConfig.isRetryStrategyConfigured() records an explicit retryStrategy(..)` | §2.3 | green |
| 4 | `784af59` | `WI01124532 ION-12310 red: getObjectSize must use a single HEAD` | U3 | red |
| 5 | `74445d1` | `WI01124532 ION-12310 green: StorageClient.getObjectSize with an S3 HEAD override` | U3 | green |
| 6 | `a87a1d5` | `WI01124532 ION-12310 red: sendEmailWithResult must return the SES message id` | U8 | red |
| 7 | `8d45475` | `WI01124532 ION-12310 green: EmailService.sendEmailWithResult returns the SES message id` | U8 | green |
| 8 | `9a884d9` | `WI01124532 ION-12310 red: EmailClientFactory must apply a configured retry strategy` | U9 | red |
| 9 | `620c44c` | `WI01124532 ION-12310 green: EmailClientFactory applies the retry strategy only when configured` | U9 | green |
| 10 | `0ad8576` | `WI01124532 ION-12310 red: ParameterStoreClientFactory must apply a configured retry strategy` | U12 | red |
| 11 | `37da891` | `WI01124532 ION-12310 green: ParameterStoreClientFactory applies the retry strategy only when configured` | U12 | green |
| 12 | `44de9af` | `WI01124532 ION-12310 red: putObject must accept zero-length content` | U2 | red |
| 13 | `ba487cb` | `WI01124532 ION-12310 green: putObject writes zero-length content as an empty object` | U2 | green |
| 14 | `cd343e2` | `WI01124532 ION-12310 red: receive must send VisibilityTimeout only when requested` | U5 | red |
| 15 | `6cb949f` | `WI01124532 ION-12310 green: ReceiveMessageOptions.requestVisibilityTimeoutSeconds is sent on receive` | U5 | green |
| 16 | `de5485b` | `WI01124532 ION-12310 red: S3 presigner must not resolve credentials eagerly and must use the config region` | U13 | red |
| 17 | `6b91c33` | `WI01124532 ION-12310 green: no access key id log, lazy presigner credentials, createS3Client presigner from config` | U13 | green |
| 18 | `fe7269b` | `WI01124532 ION-12310 red: noClientExecutionTimeout() must leave the API-call timeout unset` | U11 | red |
| 19 | `58f6a52` | `WI01124532 ION-12310 green: noClientExecutionTimeout() lets the factories set no API-call timeout` | U11 | green |
| 20 | `19762c8` | `WI01124532 ION-12310 red: getObject must make one GET and no HEAD` | U14 | red |
| 21 | `61ebc1f` | `WI01124532 ION-12310 green: getObject builds the result from the GET response, no extra HEAD` | U14 | green |
| 22 | `aa52175` | `WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT` | README | docs |

---

## 9. Key commands

```bash
# from C:\Users\arijit.kundu\projects\mercury-services-commons
mvn clean verify                                   # full build and tests (after every green commit)
mvn -pl cloud-sdk-aws -am test -Dtest=S3StorageClientObjectSizeTest -Dsurefire.failIfNoSpecifiedTests=false   # one test class
mvn clean install -DskipTests=false                # at the end: install 1.0.39-SNAPSHOT for AppianWay
git add <changed files only>                       # never git add -A; docs/ is gitignored anyway
git log --oneline c353706..HEAD                    # commits made for this work
```

---

## 10. Investigation findings and command log (Claude, 2026-11-11/12, before implementation; booking and cross-cutting checks added 2026-11-12)

This section records **what was checked before any code change, how, and what was found**, so anyone can re-run the checks. All checks are read-only.

| Repository | State checked |
|---|---|
| mercury-services | `develop` @ `53e77f4e8f` |
| mercury-services-commons | `feature/ION-12310-commons-cloudsdk-refactoring` @ `c353706` |
| AWS SDK | 2.30.24, the version pinned in `cloud-sdk-aws/pom.xml` |

### 10.1 Findings summary

| # | Topic | Finding | Evidence (10.4 command ids) |
|---|---|---|---|
| F-1 | Commons version declaration | Declared once: root `pom.xml:20` `<dependency.version>1.0.38-SNAPSHOT</dependency.version>`. Modules use `${dependency.version}` | C-03, C-04 |
| F-2 | U5 callers | One caller sets the old builder value: bill-of-lading-v2 `QueueConfig.java:44` `.visibilityTimeoutSeconds(visibilityTimeoutSeconds)`, with **300** in cvt/int/qa/prod `config.yaml` (30 in test resources). `BillOfLadingInjectorTest:55,64` asserts `getVisibilityTimeoutSeconds()` | C-10, C-11 |
| F-3 | U5: does the 300 reach SQS today? | **No.** `BillOfLadingInjector:103-133` passes only wait time, max messages and queue URL to commons `SqsListener`, whose `createReceiveMessageOptions()` (`SqsListener.java:113-119`) builds new options without visibility. In commons, nothing reads `getVisibilityTimeoutSeconds()` | C-12, C-13 |
| F-4 | U5: other receive callers | booking-bridge, booking, pi-commons, watermill-commons and webbl build options with queue URL, max messages and wait time only. booking-cargoscreen uses `receiveMessages(String,int,int)` | C-14, C-15 |
| F-5 | U5 decision | Existing caller, so use the **new** method `requestVisibilityTimeoutSeconds(int)`. The old method and getter stay unchanged | F-2..F-4 |
| F-6 | U2: reliance on the empty-content exception | None in code or tests that use cloud-sdk. The only text match is oceanschedules `MultiPartUploader.java:126` (its own message, no cloud-sdk) | C-20, C-21 |
| F-7 | U2: tests with empty content | booking `S3WorkspaceServiceTest:142-147` **expects an empty-string put to succeed** (mocked `StorageClient`). With the real 1.0.38 client this call throws, so U2 fixes it | C-22, C-23 |
| F-8 | U2: catch blocks | The 14 main classes that use `StorageClient` and mention `IllegalArgumentException` all throw for their own validation. None catches an empty-put rejection. No `isEmpty()`/`length == 0` guard sits before any `putObject` | C-24, C-25 |
| F-9 | U14: callers | No mercury-services code builds `new S3StorageClient(..)` or stubs `headObject`. No main code reads `getSize()/getETag()/getLastModified()` from `getObject` | C-30, C-31 |
| F-10 | U14: commons tests | `S3StorageClientGetObjectTest.testGetObjectSuccessfully` (50-73) takes size/eTag from a `headObject` stub and verifies HEAD, so it must change (setup only, pre-approved). `S3StorageClientMetadataTest` HEAD stubs are for `getMetadata` and are unaffected | C-32, C-33 |
| F-11 | U13 step 2: subclasses | No subclass of `S3StorageClient` and no use of `createPresigner()` in mercury-services | C-40 |
| F-12 | U13 step 2: presign users | alliance-partner, blacklist-email, commercial-entity, geography, subscriptions (network `ServerModule.java:41-42`) and tx-tracking (`TxTrackingModule.java:77`) all use **`createDefaultS3Client()`**, which step 2 does not touch | C-41, C-42, C-43 |
| F-13 | U13 step 2: `createS3Client(config)` users | booking-cargoscreen, 5 lambdas, shipping-instruction, visibility-commons, visibility-s3-archiver. **None presigns.** Providers: `DefaultCredentialsProvider.create()` or the lambdas' `resolveCredentialsProvider()`. Their unit tests mock the static factory (`mockStatic`), so they never run the factory body | C-44, C-45, C-46 |
| F-14 | U13 step 2: what `S3Presigner.build()` does | With region **and** provider supplied, `DefaultSdkPresigner`'s constructor skips the region chain and does **not** resolve credentials. It only reads profile-file flags (dualstack, FIPS), exactly as today's presigner. No network call | C-50 |
| F-15 | U13 step 2: shared provider and `close()` | `DefaultSdkPresigner.close()` closes the credentials provider when it is closeable. **`S3StorageClient` has no `close()` and never closes its presigner**, so the provider shared with `S3Client` is never closed by this change. This becomes a guard rule (10.2) | C-47, C-50 |
| F-16 | U13 step 2: values | The presigner gets exactly what `S3ClientFactory.createConfiguredClient` already gives the `S3Client` (`S3ClientFactory.java:49-50`: `getRegion().getRegionDelegate()` and `getCredentialsProvider().getCredentialProviderDelegate()`). `validateBaseConfig` guarantees both are non-null. If the `S3Client` builds, so does the presigner | C-48 |
| F-17 | U13 step 1 side note | `DefaultCredentialsProvider.create()` returns a **JVM-wide singleton** (`DefaultCredentialsProvider.java:53,81-83`). Today the eager `resolveCredentials()` in `createPresigner()` warms that singleton at construction, and the default `S3Client` shares it. After step 1, the first credential fetch happens on the first real S3 call. Not functional: today a failure there only logged a WARN, and nothing failed fast. Expect a few ms more on the first S3 call after startup | C-51 |
| F-18 | AppianWay | Doesn't use `StorageClientFactory` or cloud-sdk presigning yet. The only `generatePresignedUrl` hits are the SDK v1 fake in `functional-testing/.../AmazonS3Adaptor.java` | C-52 |
| F-19 | Retry defaults (spec §2.3) | AWS SDK default for SES/SSM with no strategy = **LEGACY** (4 attempts, throttling backoff 500 ms half-jitter, throttling retries free in the token bucket, honours `AWS_RETRY_MODE`). Commons default = **STANDARD** (3 attempts, throttling backoff 1 s full-jitter, throttling costs tokens, fixed in code). Both retry the same error classes | C-60..C-63 |
| F-20 | booking: how the S3 client is built | booking `BookingMessagingModule.java:81` and `lambda/S3ArchiveHandler.java:99` → `createDefaultS3Client()`. booking-cargoscreen `BookingCargoScreenApplicationInjector.java:253` → `createS3Client(config)` with region from `config.yaml` (**us-east-1** in cvt/int/qa/prod) and `DefaultCredentialsProvider.create()` (the JVM singleton). booking-bridge has no S3 | C-80, C-85 |
| F-21 | booking: S3 calls made | booking `common/s3/S3WorkspaceService`: `copyObject` (45), `putObject(String)` (65), `getObject` (86, 97, content only). booking `S3ArchiveHandler.writeToS3`: `putObject(String)` (258, JSON). cargoscreen `service/S3WorkspaceService`: `putObject(String)` (37), `getObject` (65, content only). No presign, `getMetadata`, `objectExists`, list, delete or stream/byte puts | C-81, C-82 |
| F-22 | booking vs U2 | All production puts write JSON (`BookingService.java:336` `Json.toJsonString(detail)`, `S3ArchiveHandler` `toS3Json`), which is never empty. The cargoscreen workspace `putObject` has no production caller. The only empty put is booking's own test `putObject_emptyContent`, which **expects success**. With U2 the real client now matches that test. **No impact** | C-23, C-83 |
| F-23 | booking vs U14 | Both `getContent` methods read only `getContent()` of the returned object. Same bytes, one S3 request fewer per read, and no GET/HEAD version race. **No impact** (improvement) | C-82 |
| F-24 | booking vs U13 | booking (`createDefaultS3Client`): step 1 only. The access-key INFO line disappears, and the first credential fetch moves to the first S3 call (F-17). cargoscreen (`createS3Client(config)`): step 2 builds the presigner with **us-east-1 and the same `DefaultCredentialsProvider` singleton** that today's `createPresigner()` uses, so it is identical in practice, and cargoscreen never presigns. **No impact** | C-80, C-85, C-50, C-51 |
| F-25 | booking vs U5, U8, U9, U11, U3, copyObject | U5: booking and booking-bridge `SQSClient` build options without visibility (C-15). U8/U9: `BookingEmailSenderModule.java:56` → `createDefaultSesClient(..)` (no retry strategy, so the U9 flag is false and nothing changes). U11/U3: not used (cargoscreen sets `clientExecutionTimeout`, which is unaffected). `copyObject`: no item touches it. **No impact** | C-15, C-84 |
| F-26 | U9 across all of mercury-services | Every SES client (auth, booking, network server, registration, tx-tracking, webbl) is built with `EmailClientFactory.createDefaultSesClient(..)`, whose config sets only region and credentials (`EmailClientFactory.java:118-125`). visibility-inbound builds its own `SesV2Client`, not through commons. So no caller has a configured strategy that U9 would suddenly start applying. **No impact** | C-84 |
| F-27 | New API names vs existing code | No class in mercury-services or AppianWay declares `sendEmailWithResult`, `getObjectSize`, `isRetryStrategyConfigured`, `noClientExecutionTimeout`, `requestVisibilityTimeoutSeconds`, `isVisibilityTimeoutRequested` or `getRequestedVisibilityTimeoutSeconds`, so there are no signature clashes. Test fakes implementing the changed interfaces (booking `FlowStep.EmailServiceTestImpl implements EmailService`; pi-commons `RecordingMessagingClient implements MessagingClient`, which gets no new methods) keep compiling through the default methods | C-86 |

### 10.2 U13 step 2: is there any impact? Conclusion

**No impact on any existing caller in mercury-services or AppianWay.** The reasons:

1. **Only one path changes:** `StorageClientFactory.createS3Client(config)`. Both `createDefaultS3Client()` and the public `S3StorageClient(S3Client)` constructor are unchanged (F-12).
2. **The presigner is used only by `generatePresignedUrl`.** No caller on the changed path presigns (F-13). Every caller that presigns is on the unchanged path (F-12).
3. **Building the new presigner does less work than today:** no region lookup, no credential resolution, no network call (F-14). Today's path calls `resolveCredentials()` eagerly.
4. **Same values as the `S3Client`** on that path (F-16), so there is no new failure mode at construction.
5. **The shared provider is never closed** by this change (F-15).
6. **Unit tests that mock the factory** are unaffected (F-13).

**Guard rules for the implementation, so it stays surprise-free:**
- Use the existing `S3StorageClient(S3Client, S3Presigner)` constructor. Do not add a constructor or a `close()` method.
- Do **not** add a `close()` to `S3StorageClient` that closes the presigner. On the step 2 path, the presigner's provider is the caller's provider, shared with the `S3Client`, and `DefaultSdkPresigner.close()` would close it. If a `close()` is ever needed, it must not close a presigner built from a caller-supplied provider. Record this in the Javadoc of `createS3Client`.
- Do not pass `endpointOverride` or `S3Configuration` to the presigner (out of scope, F1 in §7).
- Add the `StorageClientFactoryPresignerTest` cases from the spec, including a regression case that `createDefaultS3Client()` still signs for us-east-1.

**Residual risk outside the checked repos:** a commons consumer outside mercury-services and AppianWay that builds through `createS3Client(config)` with a non-us-east-1 region **and** generates presigned URLs. It would now get a correctly signed URL instead of a us-east-1 one. That is the latent-bug fix, not a regression. No such consumer is known.

### 10.2a booking: item-by-item

booking uses S3 through three classes (F-20, F-21), and every in-scope item was checked against them:

| Item | booking (`booking`) | booking-cargoscreen | Verdict |
|---|---|---|---|
| U2 zero-length puts | `putObject(String)` from `BookingService:336` and `S3ArchiveHandler:258`: JSON, never empty. Test `putObject_emptyContent` expects success | `putObject(String)`: no production caller | No impact. The real client now matches the booking test |
| U14 single GET | `getContent(..)` ×2 read only the body | `getContent(..)` reads only the body | No impact. One S3 request fewer per read |
| U13 step 1 | `createDefaultS3Client()`: no access-key log; credentials fetched on the first S3 call | same, through `createS3Client` (no presigner resolve) | No functional impact |
| U13 step 2 | not on the changed path | presigner = us-east-1 + `DefaultCredentialsProvider` singleton, the same as today's; no presign calls | No impact |
| U5 | `SQSClient` builds options without visibility | — | No impact |
| U8 / U9 | `BookingEmailSenderModule` → `createDefaultSesClient` (no strategy). Test fake `FlowStep.EmailServiceTestImpl` compiles through the default method | — | No impact |
| U3 / U11 / `copyObject` | not used / not affected | `clientExecutionTimeout` set explicitly (U11 only adds an opt-in) | No impact |

### 10.3 Shell syntax used in the commands

The commands run in **Git Bash** on Windows (POSIX shell). Paths like `/c/Users/...` are Git Bash's form of `C:\Users\...`.

| Syntax | Meaning |
|---|---|
| `cd <dir> && <cmd>` | Change directory, then run `<cmd>` only if `cd` succeeded (`&&` = "and then, if OK") |
| `<cmd1>; <cmd2>` | Run both, one after the other, regardless of success |
| `<cmd> \| <cmd2>` | Pipe: the output of `<cmd>` becomes the input of `<cmd2>` |
| `git grep -n "<pattern>" -- '<pathspec>'` | Search **tracked** files only (fast, skips `target/`, `node_modules/`). `-n` shows line numbers. `--` ends the options. `'<pathspec>'` limits the files: `'*.java'` = all Java files; `'*/src/main/*.java'` = production Java only; `'*/src/test/*.java'` = tests only |
| `git grep -l` / `-ln` | Print only the names of matching files (`-l`), optionally with `-n` |
| `grep -v <pat>` | Invert: keep lines that do **not** match |
| `grep -i` | Case-insensitive |
| `grep -c <pat> <file>` | Count matching lines |
| `grep -A6` / `-B3` / `-C2` | Also print 6 lines **after** / 3 **before** / 2 around each match |
| `grep -o` | Print only the matched text, not the whole line |
| `grep -m3` | Stop after 3 matches |
| `sed -n '100,140p' <file>` | Print only lines 100-140 (`-n` suppresses default output; `p` prints the range). `'1,60p;434,468p'` prints two ranges |
| `head -20` | Keep only the first 20 lines of output |
| `for f in a b; do ...; done` | Loop over the listed files and run the body for each `$f` |
| `$(<cmd>)` | Command substitution: insert the output of `<cmd>` into the command line |
| `cut -d/ -f2 \| sort \| uniq -c` | Split on `/`, keep field 2 (the module name), sort, and count duplicates (files per module) |
| `unzip -oq <jar> '<path>' -d <dir>` | Extract (`-o` overwrite, `-q` quiet) files matching `<path>` from a jar (a zip file) into `<dir>` |
| `unzip -l <jar>` | List the jar's contents |
| `git rev-list --left-right --count A...B` | Count commits only in A (left number) and only in B (right number). `0 0` = in sync |
| `git bundle create <file> <refs...>` / `git bundle verify <file>` | Write the named branches with full history into one file, then check it is complete and restorable |
| `tar -czf <out.tar.gz> -T <list.txt>` | Create a gzip-compressed archive of the files named, one per line, in `list.txt` |
| `2>/dev/null` / `2>&1` | Discard error output / merge errors into normal output |

**Regex alternation (OR).** This is shown in a code block because a table would hide the backslash:

```text
"a\|b\|c"          basic regex (git grep, grep):  matches lines containing a OR b OR c
grep -E "a|b"      extended regex (-E):           same OR, without the backslash; ( ) groups alternatives
\(  \[  \.         a literal "(", "[" or "." (escaped, so not treated as regex syntax)
\b                 word boundary, so "s3Presigner\b" does not match "s3PresignerBuilder"
```

### 10.4 Command log

Commands are in code blocks, exactly as run, so that regex characters such as `\|` appear literally. The results are in the table after each block.

Run mercury-services commands from `C:\Users\arijit.kundu\projects\mercury-services`, and commons commands from `C:\Users\arijit.kundu\projects\mercury-services-commons`, unless a `cd` is shown. `<scratch>` = `C:\Users\arijit.kundu\AppData\Local\Temp\claude\a3e686618d402cc8\626f30ee-df2a-4f98-8311-ead65290d3a6\scratchpad\sdksrc` (session scratchpad for the extracted SDK sources).

> **Note:** the first U5 search used the IDE's ripgrep-based search tool over the whole mercury-services tree. It **timed out** (the tree is large, including build output), so its result was incomplete. All searches below were redone with `git grep`, which searches only tracked files.

#### Repository state and version (C-01..C-04)

```bash
# C-01  branch, upstream and short status (-s short, -b branch line)
git status -sb

# C-02  fetch quietly (-q), then count commits only-local / only-remote
git fetch -q origin feature/ION-12310-commons-cloudsdk-refactoring
git rev-list --left-right --count HEAD...origin/feature/ION-12310-commons-cloudsdk-refactoring

# C-03  every place the version string occurs; "\." is a literal dot
git grep -n "1\.0\.38" -- '*pom.xml' '*.sh' '*.properties' '*.yaml' '*.yml'

# C-04  which poms use the version property
git grep -n "dependency.version" -- '*pom.xml'
```

| Id | Purpose | Result |
|---|---|---|
| C-01 | Is the tree clean? Which branch? | commons: feature branch, tracking origin, no tracked changes. mercury-services: `develop` |
| C-02 | Local vs remote | `0 0` for the commons and AppianWay feature branches (in sync) |
| C-03 | Where to bump the version | Only `pom.xml:20` |
| C-04 | Who inherits it | cloud-sdk-api, cloud-sdk-aws, commons, dynamo-client, dynamo-integration-test, email-sender |

#### U5: visibility timeout (C-10..C-15)

```bash
# C-10  (mercury-services) every builder call / getter use of the visibility value; "\|" = OR
git grep -n "visibilityTimeoutSeconds\|getVisibilityTimeoutSeconds\|VisibilityTimeoutSeconds(" -- '*.java'

# C-11  read the caller; find the configured values (-i = ignore case)
sed -n '1,60p' bill-of-lading-v2/src/main/java/com/inttra/mercury/bl/config/QueueConfig.java
git grep -n -i "visibilityTimeout" -- 'bill-of-lading-v2/*.yaml' 'bill-of-lading-v2/**/*.yaml'

# C-12  where the options go (print lines 100-140)
sed -n '100,140p' bill-of-lading-v2/src/main/java/com/inttra/mercury/bl/config/BillOfLadingInjector.java

# C-13  (commons) any production reader of the value? (grep -v drops test paths); how SqsListener builds options
git grep -n "getVisibilityTimeoutSeconds\|visibilityTimeoutSeconds" -- '*.java' | grep -v "/test/"
sed -n '110,122p' cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsListener.java

# C-14  (mercury-services) production classes that receive from SQS (-l = file names only)
git grep -ln "receiveMessages(" -- '*/src/main/*.java'

# C-15  for each of those files: the options builder plus the 6 lines after it (-A6), filtered to relevant lines
for f in booking-bridge/src/main/java/com/inttra/mercury/booking/bridge/common/messaging/SQSClient.java \
         booking-downstream-processor/booking-cargoscreen/src/main/java/com/inttra/mercury/booking/cargoscreen/processor/sqs/SqsMessageHandler.java \
         booking/src/main/java/com/inttra/mercury/booking/common/messaging/SQSClient.java \
         partner-integrator/pi-commons/src/main/java/com/inttra/mercury/common/listener/sqs/SQSListener.java \
         partner-integrator/pi-commons/src/main/java/com/inttra/mercury/common/messaging/SQSListenerClient.java \
         watermill-publisher/watermill-commons/src/main/java/com/inttra/mercury/watermill/commons/sqs/SQSClientAdapter.java \
         webbl/src/main/java/com/inttra/mercury/webbl/common/messaging/SQSClient.java; do
  echo "== $f"
  grep -n -A6 "ReceiveMessageOptions.builder()\|receiveMessages(" "$f" | grep -i "builder\|visib\|receiveMessages\|wait\|max"
done
```

| Id | Purpose | Result |
|---|---|---|
| C-10 | Find callers of the old method | bill-of-lading-v2 `QueueConfig:44` (builder), `BillOfLadingInjectorTest:55-65` (getter), `InboundEblSqsConfig:30` (own field), atlantida (its own v1 interface) |
| C-11 | Values in use | `toReceiveMessageOptions()` sets it from config: 300 in cvt/int/qa/prod, 30 in tests |
| C-12 | Is the 300 sent? | Only wait/max/url passed to `new SqsListener<>(...)`, so no |
| C-13 | Commons readers | None except the model itself. `createReceiveMessageOptions()` sets url/max/wait only |
| C-14 | All receive callers | 7 files |
| C-15 | Do they set visibility? | None does |

#### U2: zero-length puts (C-20..C-25)

```bash
# C-20  (commons) exact rejection messages
grep -n "MESSAGE\|throw new\|length\|available" \
  cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/AbstractStorageObject.java
sed -n '755,775p' cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java

# C-21  (mercury-services) any code/test using those messages or constants
git grep -n -i "content must not be null or empty\|Input stream is closed or empty\|CONTENT_VALIDATION_MESSAGE\|Content length must be greater" -- '*.java'

# C-22  tests that put empty content. -E = extended regex; \( \[ = literal brackets; \"\" = empty string literal
git grep -n -E "putObject\(.*(new byte\[0\]|\"\"|\"  *\"|EMPTY|empty)" -- '*/src/test/*.java'

# C-23  read the booking test and its adapter (-A12 = 12 lines after the match)
sed -n '136,150p' booking/src/test/java/com/inttra/mercury/booking/common/s3/S3WorkspaceServiceTest.java
grep -n -A12 "public boolean putObject(String" booking/src/main/java/com/inttra/mercury/booking/common/s3/S3WorkspaceService.java

# C-24  production files that use StorageClient AND mention IllegalArgumentException; $(...) inserts the file list
for f in $(git grep -l "StorageClient" -- '*/src/main/*.java'); do grep -l "IllegalArgumentException" "$f"; done

# C-25  is any IAE related to a put? any empty-content guard in the 3 lines before (-B3) a put?
for f in <files from C-24>; do echo "== $f"; grep -n "IllegalArgumentException\|putObject" "$f" | head -8; done
git grep -n -B3 "putObject(" -- '*/src/main/*.java' | grep -E "isEmpty\(\)|isBlank\(\)|length == 0|length > 0"
```

| Id | Purpose | Result |
|---|---|---|
| C-20 | Messages to search for | `Content must not be null or empty`, `Input stream is closed or empty`, `Content length must be greater than 0`, and the String path's `content must not be null or empty` (rejects blank) |
| C-21 | Reliance on the messages | Only oceanschedules `MultiPartUploader.java:126` (its own text, no cloud-sdk) |
| C-22 | Empty-content tests | booking `S3WorkspaceServiceTest:144-146`; oceanschedules (SDK v1); lambda archivers (non-empty) |
| C-23 | What booking expects | The test expects success. The adapter wraps any exception in `UnrecoverableAWSException`, so real 1.0.38 would fail it |
| C-24 | Candidate catch sites | 14 files |
| C-25 | Any reliance? | All IAEs are the callers' own validation. No guards |

#### U14: `getObject` single GET (C-30..C-33)

```bash
# C-30  (mercury-services) code/tests that build the real client or depend on HEAD
git grep -n "new S3StorageClient(\|headObject\|HeadObjectResponse" -- '*.java'

# C-31  consumers of the fields U14 sources differently
git grep -n "getSize()\|getETag()\|getEtag()\|getLastModified()" -- '*/src/main/*.java' | grep -i "storage\|s3\|object"

# C-32  (commons) tests that stub GET, with a count (-c) of HEAD mentions in each
for f in $(git grep -l "getObjectAsBytes" -- '*/src/test/*.java'); do echo "$f: heads=$(grep -c 'headObject' "$f")"; done

# C-33  which test relies on HEAD
grep -n "headObject\|getObjectAsBytes\|@Test\|void " \
  cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientGetObjectTest.java
```

| Id | Purpose | Result |
|---|---|---|
| C-30 | Direct dependence on HEAD | Only Javadoc mentions in watermill-commons |
| C-31 | Field consumers | None |
| C-32 | Tests mixing GET and HEAD | `S3StorageClientGetObjectTest` (3), `S3StorageClientMetadataTest` (5, all for `getMetadata`) |
| C-33 | The affected test | `testGetObjectSuccessfully` only (stub 53-59, verify 71-72) |

#### U13 step 2: presigner (C-40..C-52)

```bash
# C-40  (mercury-services) subclasses or overrides a change could break
git grep -n "extends S3StorageClient\|createPresigner" -- '*.java'

# C-41  every production presign call
git grep -n "generatePresignedUrl\|PresignedUrl(" -- '*/src/main/*.java'

# C-42  how the presigning modules build their client
git grep -n -A8 "StorageClientFactory\.\|AwsStorageConfig.builder()" -- 'network/*/src/main/*.java' 'tx-tracking/src/main/*.java' \
  | grep -i "factory\|region\|credential"

# C-43  confirm the network apps share the server's binding
git grep -n "<module>" -- network/pom.xml
git grep -n "bind(StorageClient" -- 'network/*.java'

# C-44  all callers of the path step 2 changes
git grep -n "StorageClientFactory.createS3Client(" -- '*/src/main/*.java'

# C-45  region and provider each caller passes
git grep -n -A6 "StorageClientFactory.createS3Client(AwsStorageConfig.builder()" -- '*/src/main/*.java' | grep -i credential
grep -n "credentialsProvider(\|AwsCredentialsProviderWrapper\|region(" <each caller file>

# C-46  tests that exercise the factory
git grep -n "StorageClientFactory.createS3Client\|StorageClientFactory.createDefaultS3Client" -- '*/src/test/*.java'

# C-47  (commons) does the client ever close its presigner? (\b = word boundary)
grep -n "close\|s3Presigner\b" cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java

# C-48  (commons) current factory code, and the accessors the S3 client uses
sed -n '45,100p' cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/factory/StorageClientFactory.java
grep -n "createConfiguredClient\|\.region(\|credentialsProvider(" \
  cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/factory/S3ClientFactory.java

# C-50  read the SDK's own presigner source (unzip -o overwrite, -q quiet, -d target dir)
unzip -oq ~/.m2/repository/software/amazon/awssdk/s3/2.30.24/s3-2.30.24-sources.jar \
  'software/amazon/awssdk/services/s3/internal/signing/*' -d <scratch>/s3
#   then read DefaultSdkPresigner.java (constructor, close()) and DefaultS3Presigner.java (constructor at line 155)

# C-51  is DefaultCredentialsProvider.create() a singleton?
unzip -oq ~/.m2/repository/software/amazon/awssdk/auth/2.30.24/auth-2.30.24-sources.jar \
  'software/amazon/awssdk/auth/credentials/DefaultCredentialsProvider.java' -d <scratch>/auth
grep -n -A4 "public static DefaultCredentialsProvider create()\|DEFAULT_CREDENTIALS_PROVIDER =" \
  <scratch>/auth/software/amazon/awssdk/auth/credentials/DefaultCredentialsProvider.java

# C-52  (appianway) AppianWay exposure
git grep -n "generatePresignedUrl\|StorageClientFactory\." -- '*.java'
```

| Id | Purpose | Result |
|---|---|---|
| C-40 | Subclass / override risk | None |
| C-41 | Presign callers | network alliance-partner, blacklist-email, commercial-entity, geography, subscriptions; tx-tracking |
| C-42 | Their client path | `ServerModule:41`, `TxTrackingModule:77` → `createDefaultS3Client()` (unchanged) |
| C-43 | Shared binding | `ServerModule.java:42 bind(StorageClient.class).toInstance(...)` |
| C-44 | Changed-path callers | 9 callers (F-13), none presigns |
| C-45 | Their providers | `DefaultCredentialsProvider.create()` or the lambdas' `resolveCredentialsProvider()`; their own region |
| C-46 | Factory tests | auth-tokens-archive, bounceback-email, registration-archive. All `mockStatic` the factory |
| C-47 | Close risk | No `close()`. The presigner is used only at line 1099 (`presignGetObject`) |
| C-48 | Accessor parity | `createS3Client` → `new S3StorageClient(s3Client)`. S3 client uses `getRegion().getRegionDelegate()` / `getCredentialsProvider().getCredentialProviderDelegate()` (lines 49-50) |
| C-50 | Presigner build cost | The region chain and `DefaultCredentialsProvider` are used only when not supplied. No resolve at build. `close()` → `IoUtils.closeIfCloseable(credentialsProvider)` |
| C-51 | Singleton? | Yes (lines 53, 81-83) |
| C-52 | AppianWay exposure | Only the SDK v1 fake in functional-testing |

#### Retry defaults for spec §2.3 (C-60..C-63)

```bash
# C-60  extract the SDK retry sources into the scratchpad
for m in retries aws-core sdk-core retries-spi; do
  unzip -oq ~/.m2/repository/software/amazon/awssdk/$m/2.30.24/$m-2.30.24-sources.jar -d <scratch>/$m
done

# C-61  how a client picks its strategy (run inside <scratch>)
grep -n "RetryStrategy\|retryStrategy\|RetryMode\|retryMode" aws-core/software/amazon/awssdk/awscore/client/builder/AwsDefaultClientBuilder.java
sed -n '434,468p' aws-core/software/amazon/awssdk/awscore/client/builder/AwsDefaultClientBuilder.java
sed -n '168,200p' sdk-core/software/amazon/awssdk/core/retry/RetryMode.java

# C-62  constants and builders of each strategy (sed prints from the class line to end of file)
sed -n '/class DefaultRetryStrategy/,$p' retries/software/amazon/awssdk/retries/DefaultRetryStrategy.java
grep -n -A12 "static Builder builder()" retries/software/amazon/awssdk/retries/LegacyRetryStrategy.java \
  retries/software/amazon/awssdk/retries/StandardRetryStrategy.java

# C-63  backoff formulas; do SES/SSM ship their own retry policy?
grep -rn -A8 "public Duration computeDelay\|int calculateExponentialDelay" retries-spi/
for m in sesv2 ssm dynamodb; do
  unzip -l ~/.m2/repository/software/amazon/awssdk/$m/2.30.24/$m-2.30.24.jar | grep -io '[A-Za-z/]*Retry[A-Za-z]*\.class'
done
```

| Id | Purpose | Result |
|---|---|---|
| C-60 | Sources available | Extracted |
| C-61 | Strategy selection | No strategy → `resolveAwsRetryStrategy` (env/system property → profile → defaults mode → LEGACY). A supplied strategy with `useClientDefaults` gets the AWS and SDK retry conditions added |
| C-62 | Strategy parameters | Legacy: 4 attempts, 100 ms / 500 ms half-jitter, throttle cost 0. Standard: 3 attempts, 100 ms / 1 s, cost 5 |
| C-63 | Backoff and service policies | delay = base × 2^(attempt−2), full or half jitter. SES/SSM: no own policy (DynamoDB: `DynamoDbRetryPolicy`) |

#### booking and cross-cutting checks (C-80..C-86)

```bash
# C-80  (mercury-services) how booking modules create their StorageClient (production only: grep -v drops test paths)
git grep -n "StorageClientFactory\.\|new S3StorageClient\|StorageClient.class\|S3ClientFactory\|StorageObjectTransferManager\|createS3TransferManager" \
  -- 'booking/*.java' 'booking-bridge/*.java' 'booking-downstream-processor/*.java' | grep -v "/test/"

# C-81  every cloud-sdk storage call in booking production files; -E extended regex, \. literal dot, \( literal "("
for f in $(git grep -l "cloudsdk.storage" -- 'booking/*.java' 'booking-bridge/*.java' 'booking-downstream-processor/*.java' | grep "/src/main/"); do
  echo "== $f"
  grep -n -E "\.(putObject|getObject|getMetadata|objectExists|listObjects|listObjectKeys|deleteObject|copyObject|generatePresignedUrl|getObjectSize|getObjectContent|readObject|uploadFile|downloadFile)\(" "$f"
done

# C-82  read the call sites
sed -n '30,110p' booking/src/main/java/com/inttra/mercury/booking/common/s3/S3WorkspaceService.java
sed -n '30,80p'  booking-downstream-processor/booking-cargoscreen/src/main/java/com/inttra/mercury/booking/cargoscreen/service/S3WorkspaceService.java
sed -n '245,262p' booking/src/main/java/com/inttra/mercury/booking/lambda/S3ArchiveHandler.java

# C-83  who passes content to the booking/cargoscreen workspace putObject
git grep -n -E "(s3WorkspaceService|workspaceService|s3Workspace|S3WorkspaceService)\.putObject\(" \
  -- 'booking/src/main/*.java' 'booking-downstream-processor/*/src/main/*.java' 'booking-bridge/src/main/*.java'
git grep -n "\.putObject(" -- 'booking-downstream-processor/*/src/main/*.java' | grep -v "storageClient.putObject"

# C-84  every SES client in mercury-services (U9) and how it is built; then the commons default config
git grep -n "AwsSesEmailConfig\|EmailClientFactory\." -- '*/src/main/*.java'
sed -n '58,75p' visibility/visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/config/VisibilityInboundApplicationInjector.java
#   (commons) sed -n '108,126p' cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/factory/EmailClientFactory.java

# C-85  cargoscreen S3 config and its region per environment
sed -n '183,195p;245,256p' booking-downstream-processor/booking-cargoscreen/src/main/java/com/inttra/mercury/booking/cargoscreen/config/BookingCargoScreenApplicationInjector.java
git grep -n -i "region" -- 'booking-downstream-processor/booking-cargoscreen/conf/*/config.yaml'

# C-86  name clashes with the new API, and fakes implementing the changed interfaces (\b = word boundary)
git grep -n "sendEmailWithResult\|getObjectSize\|isRetryStrategyConfigured\|noClientExecutionTimeout\|requestVisibilityTimeoutSeconds\|isVisibilityTimeoutRequested\|getRequestedVisibilityTimeoutSeconds" -- '*.java'
git grep -n -E "implements .*\b(StorageClient|EmailService|MessagingClient)\b" -- '*.java'
#   and the same name search in C:\Users\arijit.kundu\projects\appianway
```

| Id | Purpose | Result |
|---|---|---|
| C-80 | booking client creation | `BookingMessagingModule:81`, `S3ArchiveHandler:99` → `createDefaultS3Client()`; cargoscreen `:253` → `createS3Client(config)` |
| C-81 | booking S3 calls | booking workspace: copy, put(String), get ×2; archive: put(String); cargoscreen: put(String), get |
| C-82 | How results are used | `getObject` → body only. Puts are String JSON |
| C-83 | Put content sources | `BookingService:336` (JSON). cargoscreen workspace put: no production caller |
| C-84 | SES construction | All via `createDefaultSesClient(..)` (no retry strategy). visibility-inbound uses its own `SesV2Client` |
| C-85 | cargoscreen region | us-east-1 in all environments; `DefaultCredentialsProvider.create()` |
| C-86 | Clashes and fakes | No clashes (mercury-services and AppianWay). Fakes: booking `FlowStep.EmailServiceTestImpl`, pi-commons `RecordingMessagingClient` |

#### Backups (C-70..C-72)

```bash
# C-70  local backup branch at the current tip (commons; AppianWay equivalent with its own names)
git branch backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12 feature/ION-12310-commons-cloudsdk-refactoring

# C-71  full-history single-file copy outside the repo, then integrity check
git bundle create C:/Users/arijit.kundu/backups/2026-11-12/commons-feature-ION-12310-c353706.bundle \
  feature/ION-12310-commons-cloudsdk-refactoring backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12 develop
git bundle verify C:/Users/arijit.kundu/backups/2026-11-12/commons-feature-ION-12310-c353706.bundle

# C-72  archive gitignored/untracked docs (bundles do not contain them); -T reads the file list
git ls-files --others --ignored --exclude-standard | grep -E "(^|/)docs/" | sort -u > commons-untracked-docs.txt
tar -czf commons-untracked-docs.tar.gz -T commons-untracked-docs.txt
```

| Id | Purpose | Result |
|---|---|---|
| C-70 | Backup branches | Created at `c353706` (commons) and `fa3efede` (AppianWay) |
| C-71 | Bundles | "is okay" for both |
| C-72 | Docs archives | 39 commons files, 170 AppianWay files |

---

## 11. Handover summary for AppianWay (fill in at the end)

- Final commit:
- Installed version: `1.0.39-SNAPSHOT` (yes / no)
- New API available: `StorageClient.getObjectSize`, `EmailService.sendEmailWithResult`, `BaseAwsConfig.isRetryStrategyConfigured`, `BaseAwsConfigBuilder.noClientExecutionTimeout`, `ReceiveMessageOptions.Builder.requestVisibilityTimeoutSeconds`
- Behaviour changes callers can see: zero-length puts accepted (U2); `getObject` makes one request (U14); `createS3Client(config)` presigner uses the config region and provider (U13 step 2); no access-key log (U13)
- Anything AppianWay must know (deviations from the spec):

---

## 12. Copilot review

> **Reviewer:** GitHub Copilot CLI (model `claude-opus-5.5`), 2026-11-13.
> **Range reviewed:** `c353706..aa52175` (22 commits) on `feature/ION-12310-commons-cloudsdk-refactoring`: 25 production files, 12 test files, `README.md` and `pom.xml` (+2141 / −58).
> **Method:** read the full production diff and every new or changed test class, then compared them with the stated rules (§3), the impact checks (§4, §10) and the README note. Mercury-services callers were not re-checked; this review relies on §4 and §10. The new and changed test classes were re-run locally (see 12.6).

### 12.1 Verdict

**Approve with comments. Nothing blocks merging the code.** The change is small, additive and well tested. Every new behaviour is opt-in or is a strict improvement (U14, U13). Compatibility rules hold: no signature or return type changed, the new interface methods are `default`, the new switches default to off, and `createPresigner()` stays `protected static`. Most comments below are about **documentation accuracy and edge-case contracts**. Items R1 and R2 should be addressed, or explicitly accepted, before 1.0.39 is released (not just snapshotted). Neither needs a code change for the AppianWay rollout.

| Severity | Count | Ids |
|---|---|---|
| Should fix / accept explicitly before release | 2 | R1, R2 |
| Minor (fix in a later release, or document) | 7 | R3 to R9 |
| Nit / observation | 6 | N1 to N6 |

### 12.2 What is done well

- **Strict TDD trail.** Each item has a red commit and a green commit. Red commits compile, using marked stubs (D2), so the history can be bisected and every test was seen failing first.
- **Additive API discipline.** `sendEmailWithResult` throws `UnsupportedOperationException` by default instead of quietly calling the `void` method. That stops a fake or decorator from returning a result with no message id. `requestVisibilityTimeoutSeconds` is a **new** method because bill-of-lading-v2 already sets `visibilityTimeoutSeconds(300)` (F-2). Changing what that call does would have silently changed production receive behaviour.
- **`isRetryStrategyConfigured()` is captured before the default is applied** (`BaseAwsConfig` constructor). This is the only way to tell "not set" from "set to the commons default", because `getRetryStrategy()` is never null.
- **U14 fixes a correctness issue as well as cost.** Size, eTag and last-modified now come from the same response as the body. Before, a concurrent overwrite between the GET and the HEAD could return metadata from a different object version.
- **U13 removes a credential leak.** The old `Main.java:77` "prefix" was the whole 20-character access key id. Lazy resolution also removes a startup-time network call to the credential chain.
- **D3 was caught.** Five config subclasses shadow `clientExecutionTimeout(Duration)`. Without the reset line in each, "last call wins" would have failed silently for SQS, SNS, DynamoDB, SSM and SES. `NoClientExecutionTimeoutFactoryTest` covers this per factory.
- **Tests assert observable behaviour.** They read the built client's `overrideConfiguration()`, capture SDK requests, sign URLs offline and capture log events. They do not just check that a mock was called.

### 12.3 Findings

#### R1 (should fix the docs, U11): "bounded by the HTTP socket timeout" over-promises

`BaseAwsConfig.noClientExecutionTimeout()` and `isClientExecutionTimeoutDisabled()` Javadoc, the factory comments (`S3ClientFactory:94`, `MessagingClientFactory:130`, `NotificationClientFactory`, `ParameterStoreClientFactory:35`, `EmailClientFactory:154`) and README item 5 all say that calls "stay bounded by the HTTP client's socket timeout". That is only partly true:
- A socket timeout (`AwsHttpDefaults.SOCKET_TIMEOUT` = 30 s) is an **inactivity** timeout per read. A response that sends a byte every few seconds is never cut off. Time spent waiting for retries and backoff is not limited either. The total call time therefore has **no upper bound**.
- The 30 s only applies when the commons default Apache client is used. A caller-supplied `httpClient(..)` brings its own value, which may be infinite.
- For SES the attempt timeout (`apiCallAttemptTimeout`) is also removed. For SQS, SNS and DynamoDB an explicit attempt timeout is kept.

**Risk:** a consumer chooses `noClientExecutionTimeout()` for long S3 transfers and gets a thread that never returns, for example a Dropwizard request thread or an SQS listener thread. **Recommendation:** reword it as "no overall API-call timeout; each read is limited only by the HTTP client's socket (inactivity) timeout, so the total call time is not bounded". Recommend that callers who disable it set an attempt timeout where the config supports one. Doc-only change, no code impact.

#### R2 (should accept explicitly, U2): `contentLength == 0` with a non-empty stream now writes an empty object

Before, `putObject(bucket, key, InputStream, 0)` was rejected. Now validation returns early for `0`, without probing the stream (`AbstractStorageObject.validateInputStream`), and `RequestBody.fromInputStream(in, 0)` uploads 0 bytes. A caller that passes `0` to mean "length unknown", a common mistake when the length is read from a missing `Content-Length` header, used to get an error. It now **silently writes an empty object and returns success**: data loss with no signal. §4 and F-8 found no such caller in mercury-services, and U2 asks for this behaviour, so this is a **contract risk, not a regression found in code**. **Recommendation:** either (a) accept it and say so in the README note ("a length of 0 always writes an empty object; the stream is not read"), or (b) in a later release, check whether the stream has data (a non-blocking `available() > 0` check, or a one-byte read when `markSupported()` is true) and reject a non-empty stream declared as 0 bytes. (a) is enough for 1.0.39.

#### R3 (minor, U2): validation messages no longer match the rule

`CONTENT_VALIDATION_MESSAGE` = `"Content must not be null or empty"` (`AbstractStorageObject.java:22`) and the `String` `putObject` message `"content must not be null or empty"` are now raised only for `null`. Keeping the text avoids breaking anyone who matches the message, which is the right call for this release. Note it as a follow-up: change the text to "must not be null" in a later release, along with a deprecation note on the constant. (`CONTENT_LENGTH_VALIDATION_MESSAGE` = `"Content length must be greater than 0"` is also out of date: `0` is now valid and the message is raised only for negative values.)

#### R4 (minor, U3): a bare 404 from a missing **bucket** is reported as a missing key

`S3StorageClient.getObjectSize` turns any `S3Exception` with status 404 into `NoSuchKeyException`, so the message becomes `Bucket <b> does not contain key <k>`. HEAD responses have no body, so a missing bucket also arrives as a bare 404. The message then misleads people diagnosing a bucket name or region mistake. This also differs slightly from `getMetadata`, which does not remap a bare 404, so the "errors as `getMetadata`" contract holds only for typed `NoSuchKeyException`s. **Recommendation:** accept for 1.0.39. Later, either document "404 means key **or** bucket not found", or apply the same remap in `getMetadata` so the two methods match exactly.

#### R5 (minor, U3 and U8): default methods hide traps for other implementations and decorators

- `StorageClient.getObjectSize` default **downloads the whole object** to read its length. Any non-S3 implementation or decorator, such as a caching, metrics or tenant-prefix wrapper, that does not override it turns a cheap size check into a full download. The Javadoc says so, which is good. AppianWay fakes should override it (F5 lists this).
- `getObjectSize` returns `0` both for an empty object and for "provider reported no length" or `getObject` returning `null`. The spec fixed the `long` return type. Under the project's null-safety rule, `OptionalLong` would have been more accurate. This is a design note only; changing it now would break the spec.
- `EmailService.sendEmailWithResult` default throws. A **decorator** `EmailService` that wraps `SesEmailServiceImpl` without overriding the new method will throw at runtime even though the wrapped service supports it. F-27 found only a test fake, so the risk is in future code. **Recommendation:** add one line to the README note: "decorators must forward `sendEmailWithResult`".

#### R6 (minor, U8): `EmailSendResult.emailAddress` has only the `to` recipients

The result joins `to` with `","` and leaves out cc and bcc. This matches the Javadoc and spec, but a consumer that uses `emailAddress` for audit or delivery tracking will under-report recipients. `EmailSendResult.exception` and `emailRequest` stay `null`, because failures throw. Document both facts on `EmailSendResult` in a later release, so nobody checks `getException()` for errors.

#### R7 (minor, U9, U12 and existing code): retry default is not the same across factories

With 1.0.39, a config with no `retryStrategy(..)` gets:
- **S3, SQS, SNS:** the commons STANDARD strategy (3 attempts), applied by the factory.
- **SES, SSM:** the AWS SDK default (LEGACY, 4 attempts, honours `AWS_RETRY_MODE`).
- **DynamoDB:** `retryMode` if set, otherwise the SDK default.

Keeping each factory's behaviour unchanged is correct for this release (rule: an unconfigured client stays byte-identical). The result is still an inconsistent platform default that consumers cannot see. In addition, the `config.getRetryStrategy() == null` branches in `S3ClientFactory:88`, `MessagingClientFactory:145` and `NotificationClientFactory:133` are **dead code**, because `BaseAwsConfig` never returns null. Their WARN "No retry strategy configured" can never be logged. That predates this change, but U11 rewrote `S3ClientFactory.createOverrideConfig` and kept the dead branch. **Recommendation (follow-up):** decide on one documented default and use `isRetryStrategyConfigured()` everywhere. Remove the dead null branches, or switch them to the flag so the WARN fires when it should.

#### R8 (minor, U11): subclass getters return different values after `noClientExecutionTimeout()`

As §5.9 notes, `noClientExecutionTimeout()` clears only the **base** builder field. Results:
- `AwsStorageConfig.builder().clientExecutionTimeout(7s).noClientExecutionTimeout()`: `getClientExecutionTimeout()` returns **30 s** (base default; asserted in `BaseAwsConfigTest.trueAfterNoClientExecutionTimeout`).
- `AwsMessagingClientConfig` / `AwsSesEmailConfig` / ... with the same calls: `getClientExecutionTimeout()` returns **7 s** (the subclass field is not cleared).

No factory reads the getter when the flag is set, so behaviour is correct. However, any code that logs or reports the getter (for example `paramstore/main/Main.java:65,190` logs `Client Execution Timeout: ...`) will show a timeout that is not applied. **Recommendation:** document "when `isClientExecutionTimeoutDisabled()` is true, ignore `getClientExecutionTimeout()`", and make diagnostic logging print "disabled". Another option is a protected hook in the base builder that subclasses override to clear their own field. That is a larger change and fits a later release better.

Related edge case, not tested: `noClientExecutionTimeout().clientExecutionTimeout(null)` turns the timeout back on with the **default** (30 s for S3, the subclass default elsewhere). This is consistent with "last call wins", but it is not obvious. Add a test or one Javadoc sentence.

#### R9 (minor, U13 step 2 and F1): presigner ignores `endpointOverride`, and a new unclosed presigner is created per client

- `createS3Client(config)` presigns against real AWS endpoints even when the config has `endpointOverride` (LocalStack, VPC endpoint, S3-compatible store). Before this change the same was true (us-east-1 default), so it is **not a regression**. It is now the only setting on the presign path that differs from the `S3Client`. Already tracked as F1. Raise its priority if any AppianWay environment uses an endpoint override with presigned URLs.
- Each `createS3Client(config)` call now creates an `S3Presigner` that is never closed. The guard rule (F-15) is right not to close it, because closing would close the caller's shared provider. The presigner holds no thread pool or HTTP connection, so the leak is only a small object. It does mean a factory called per request would create one presigner per call. This was already the case on the `createDefaultS3Client()` path. Treat `StorageClient` as a long-lived singleton; that is how all callers in §10 already use it.

#### Nits and observations

- **N1 (U5).** `ReceiveMessageOptions.visibilityTimeoutSeconds(int)` is now documented as "stored only; not sent". That is a trap waiting to happen. Mark it `@Deprecated` (pointing to `requestVisibilityTimeoutSeconds`) in the next release, following the project's deprecate-before-remove rule. Also note that `SqsListener` cannot pass the new option yet, so listener-based consumers cannot use U5 without building their own receive loop.
- **N2 (U14).** `getObject` still logs at **INFO** on every read (`Object retrieved successfully ... size=`). Unchanged by this work, but every S3 read in high-volume services adds a log line. Consider DEBUG in a later release, like `getObjectSize`.
- **N3 (U14).** When the GET has no `Content-Length`, the fallback calls `objectContent.asByteArray()`, which **copies** the whole buffer just to measure it. `asByteBuffer().remaining()` gives the length without a copy. This only matters for large objects with chunked responses, which S3 rarely returns for GET.
- **N4 (tests).** `EmailClientFactoryRetryStrategyTest`, `ParameterStoreClientFactoryRetryStrategyTest` and `NoClientExecutionTimeoutFactoryTest` read private fields (`sesClient`, `ssmClient`, ...) by reflection. Renaming a field breaks these tests with a `NoSuchFieldException`, not an assertion message. That is acceptable for now. A package-private accessor, or asserting through `SdkClient.serviceClientConfiguration()` on an injected client, would be sturdier.
- **N5 (tests).** `StorageClientFactoryPresignerTest.defaultClientIsUnchanged` sets JVM-wide system properties. It restores them in `finally`, which is correct, but it is not safe if surefire ever runs tests in parallel (it does not today). Tag the test with `@ResourceLock(Resources.SYSTEM_PROPERTIES)` to make this explicit.
- **N6 (tests, D1).** The U9/U12 "unconfigured" regression guard depends on the environment: if `AWS_RETRY_MODE` or the profile sets a mode on the build agent, the 4-attempt assertion is skipped and only the comparison with the reference client runs. That is the right design. Note it in the test Javadoc so a future reader does not think the guard is weaker than it is.

### 12.4 Test review summary

| Area | Coverage | Gaps |
|---|---|---|
| `BaseAwsConfig` flags | default, set, set-null, last-call-wins, for both flags | only the base builder (`AwsStorageConfig`) is used here; the subclass paths are covered in the factory tests. `clientExecutionTimeout(null)` after `noClientExecutionTimeout()` is not tested (R8) |
| U3 `getObjectSize` | single HEAD, `never()` GET, null length, 404, 403, SDK errors, validation, default method | missing-bucket 404 message (R4) |
| U8 `sendEmailWithResult` | result values; captured request equal to `sendEmail` (simple, three-arg, raw MIME parsed); errors; validation; `void` unchanged | none significant |
| U9 / U12 retry | doNotRetry, custom, unconfigured guard, timeouts unchanged | environment-dependent guard (N6) |
| U2 zero-length | bytes, non-markable stream, strings, with metadata; null / negative still rejected | no test that documents the R2 contract (non-empty stream declared as 0) |
| U5 visibility | range checks, independence of old and new, request capture, other fields unchanged | none |
| U13 | counting provider proves lazy resolution; log capture; offline signing per region; default client unchanged | `endpointOverride` (R9, out of scope) |
| U11 | each of 6 factories: default, disabled, re-enabled, other settings kept | none significant |
| U14 | one GET / no HEAD, every field from GET, Content-Length fallback, error mapping | none |

### 12.5 README note check

The note matches the code, with these exceptions: item 5 repeats the R1 wording ("bounded by the HTTP client's socket timeout"), and item 8 does not mention the R2 behaviour (a length of 0 does not read the stream). Suggest two one-line edits before the release build. `Latest release version` is correctly left unchanged for a SNAPSHOT.

### 12.6 Verification done for this review

- Production diff and all 12 new or changed test classes read in full (`git diff c353706..aa52175`).
- New and changed test classes re-run locally with `mvn -o -pl cloud-sdk-api,cloud-sdk-aws -am test -Dtest=<the U-item test classes>`. Result (2026-11-13, at `aa52175`): **347 tests, 0 failures, 0 errors, 0 skipped** (all `S3StorageClient*Test` classes plus the U-item test classes). The full `mvn clean verify` result (2695 green) is as reported in §0 and was not re-run.

### 12.7 Recommended actions

| # | Action | When | Owner |
|---|---|---|---|
| A1 | Reword the "bounded by socket timeout" Javadoc/comments and README item 5 (R1) | before the 1.0.39 release | commons |
| A2 | Accept and document the zero-length stream contract in README item 8 (R2) | before the 1.0.39 release | commons |
| A3 | One README line: decorators must forward `sendEmailWithResult` / override `getObjectSize` (R5) | before the 1.0.39 release | commons |
| A4 | Unify the retry default and remove the dead null branches (R7) | next commons release | commons |
| A5 | Deprecate `ReceiveMessageOptions.visibilityTimeoutSeconds(int)` (N1); fix validation message text (R3) | next commons release | commons |
| A6 | Presigner `endpointOverride` (F1 / R9) | when an AppianWay environment needs it | commons |
