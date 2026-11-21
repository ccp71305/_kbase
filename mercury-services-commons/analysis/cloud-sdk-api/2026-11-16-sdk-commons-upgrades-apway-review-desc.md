# SDK commons upgrades for appway: review description (commits 91cde62 .. aa52175, HEAD)

| Field | Value |
|---|---|
| PR | [INT/mercury-services-commons PR #29](https://git.dev.e2open.com/projects/INT/repos/mercury-services-commons/pull-requests/29) |
| Branch | `feature/ION-12310-commons-cloudsdk-refactoring` |
| Work item / Jira | WI01124532 / ION-12310 |
| Release | commons / cloud-sdk 1.0.39-SNAPSHOT |
| Items | version bump, §2.3 `isRetryStrategyConfigured` flag, U3 `getObjectSize`, U8 `sendEmailWithResult`, U9 SES retry, U12 SSM retry, U2 zero-length puts, U5 SQS visibility timeout, U13 presigner and key log, U11 `noClientExecutionTimeout()`, U14 single-GET `getObject`, README note |
| Commits | 22, `91cde62` .. `aa52175` (HEAD, pushed; see [Commit map](#commit-map)) |
| Full design / progress | [2026-11-12-sdk-commons-changes-for-apway.md](2026-11-12-sdk-commons-changes-for-apway.md) §2, §5.1–5.11, §6 D1–D3, §12 R1–R9 and N1–N6 |

Note: both links in the review request point to `0ad8576`. That commit is the red half of a TDD pair, so its green partner `37da891` is described with it. This document covers **every commit on the branch, from the version bump to HEAD** (22 commits, oldest first).

## Table of contents

- [Commit map](#commit-map)
- [Background](#background)
- [Why the factories silently ignored the retry strategy](#why-the-factories-silently-ignored-the-retry-strategy)
- Commits
  1. [91cde62 build: commons 1.0.39-SNAPSHOT](#1-91cde62-build-commons-1039-snapshot)
  2. [025f398 red: BaseAwsConfig must record whether retryStrategy was set](#2-025f398-red-baseawsconfig-must-record-whether-retrystrategy-was-set)
  3. [8129389 green: BaseAwsConfig.isRetryStrategyConfigured()](#3-8129389-green-baseawsconfigisretrystrategyconfigured)
  4. [784af59 red: getObjectSize must use a single HEAD](#4-784af59-red-getobjectsize-must-use-a-single-head)
  5. [74445d1 green: StorageClient.getObjectSize with an S3 HEAD override](#5-74445d1-green-storageclientgetobjectsize-with-an-s3-head-override)
  6. [a87a1d5 red: sendEmailWithResult must return the SES message id](#6-a87a1d5-red-sendemailwithresult-must-return-the-ses-message-id)
  7. [8d45475 green: EmailService.sendEmailWithResult returns the SES message id](#7-8d45475-green-emailservicesendemailwithresult-returns-the-ses-message-id)
  8. [9a884d9 red: EmailClientFactory must apply a configured retry strategy](#8-9a884d9-red-emailclientfactory-must-apply-a-configured-retry-strategy)
  9. [620c44c green: EmailClientFactory applies the retry strategy only when configured](#9-620c44c-green-emailclientfactory-applies-the-retry-strategy-only-when-configured)
  10. [0ad8576 red: SSM factory must apply a configured retry strategy](#10-0ad8576-red-ssm-factory-must-apply-a-configured-retry-strategy)
      - [Why each test behaves the way it does](#why-each-test-behaves-the-way-it-does)
  11. [37da891 green: SSM factory applies the retry strategy only when configured](#11-37da891-green-ssm-factory-applies-the-retry-strategy-only-when-configured)
  12. [44de9af red: putObject must accept zero-length content](#12-44de9af-red-putobject-must-accept-zero-length-content)
  13. [ba487cb green: putObject writes zero-length content as an empty object](#13-ba487cb-green-putobject-writes-zero-length-content-as-an-empty-object)
  14. [cd343e2 red: receive must send VisibilityTimeout only when requested](#14-cd343e2-red-receive-must-send-visibilitytimeout-only-when-requested)
  15. [6cb949f green: requestVisibilityTimeoutSeconds is sent on receive](#15-6cb949f-green-requestvisibilitytimeoutseconds-is-sent-on-receive)
  16. [de5485b red: S3 presigner must not resolve credentials eagerly and must use the config region](#16-de5485b-red-s3-presigner-must-not-resolve-credentials-eagerly-and-must-use-the-config-region)
  17. [6b91c33 green: no access key id log, lazy presigner credentials, presigner from config](#17-6b91c33-green-no-access-key-id-log-lazy-presigner-credentials-creates3client-presigner-from-config)
  18. [fe7269b red: noClientExecutionTimeout() must leave the API-call timeout unset](#18-fe7269b-red-noclientexecutiontimeout-must-leave-the-api-call-timeout-unset)
  19. [58f6a52 green: noClientExecutionTimeout() lets the factories set no API-call timeout](#19-58f6a52-green-noclientexecutiontimeout-lets-the-factories-set-no-api-call-timeout)
  20. [19762c8 red: getObject must make one GET and no HEAD](#20-19762c8-red-getobject-must-make-one-get-and-no-head)
  21. [61ebc1f green: getObject builds the result from the GET response](#21-61ebc1f-green-getobject-builds-the-result-from-the-get-response-no-extra-head)
  22. [aa52175 docs: README release note for 1.0.39-SNAPSHOT](#22-aa52175-docs-readme-release-note-for-1039-snapshot)
- [Verification (2026-11-16)](#verification-2026-11-16)
- [Command reference: how to read each command](#command-reference-how-to-read-each-command)
  - [git](#git) · [grep](#grep-ripgrep) · [PowerShell](#powershell-helpers-used-in-the-pipes) · [mvn](#mvn) · [jshell](#checking-sdk-behaviour-quickly-jshell) · [Git Bash](#git-bash-equivalents)
- [Review notes](#review-notes)

## Commit map

| # | Commit | Kind | Item | Module(s) | In one line |
|---|---|---|---|---|---|
| 1 | `91cde62` | build | - | root `pom.xml` | Version 1.0.38 → 1.0.39-SNAPSHOT |
| 2 | `025f398` | red | §2.3 flag | cloud-sdk-aws | Tests for a new "was retryStrategy set?" flag |
| 3 | `8129389` | green | §2.3 flag | cloud-sdk-aws | `BaseAwsConfig.isRetryStrategyConfigured()` |
| 4 | `784af59` | red | U3 | api + aws | Tests: object size from one S3 HEAD |
| 5 | `74445d1` | green | U3 | api + aws | `StorageClient.getObjectSize` + S3 override |
| 6 | `a87a1d5` | red | U8 | api + aws | Tests: sending an email returns the SES message id |
| 7 | `8d45475` | green | U8 | api + aws | `EmailService.sendEmailWithResult` |
| 8 | `9a884d9` | red | U9 | cloud-sdk-aws | Tests: SES factory must apply a set retry strategy |
| 9 | `620c44c` | green | U9 | cloud-sdk-aws | SES factory applies it only when set |
| 10 | `0ad8576` | red | U12 | cloud-sdk-aws | Tests: SSM factory must apply a set retry strategy |
| 11 | `37da891` | green | U12 | cloud-sdk-aws | SSM factory applies it only when set |
| 12 | `44de9af` | red | U2 | cloud-sdk-aws | Tests: empty `byte[]`, stream and `String` puts are allowed |
| 13 | `ba487cb` | green | U2 | cloud-sdk-aws | Validation rejects only `null` |
| 14 | `cd343e2` | red | U5 | api + aws | Tests: send `VisibilityTimeout` only when requested |
| 15 | `6cb949f` | green | U5 | api + aws | `requestVisibilityTimeoutSeconds(int)`, sent on receive |
| 16 | `de5485b` | red | U13 | cloud-sdk-aws | Tests: lazy credentials, no key log, presigner region from config |
| 17 | `6b91c33` | green | U13 | cloud-sdk-aws | Key log removed, lazy presigner, `createS3Client` presigner from config |
| 18 | `fe7269b` | red | U11 | cloud-sdk-aws | Tests: `noClientExecutionTimeout()` leaves `apiCallTimeout` unset |
| 19 | `58f6a52` | green | U11 | cloud-sdk-aws | Flag in `BaseAwsConfig` and 6 factories |
| 20 | `19762c8` | red | U14 | cloud-sdk-aws | Tests: `getObject` makes one GET and no HEAD |
| 21 | `61ebc1f` | green | U14 | cloud-sdk-aws | Metadata taken from the GET response |
| 22 | `aa52175` | docs | - | `README.md` | Release note for 1.0.39-SNAPSHOT (**HEAD**) |

```
 91cde62 ─► 025f398 ─► 8129389 ─┬─► 784af59 ─► 74445d1          (U3, independent)
 version     flag red  flag green│─► a87a1d5 ─► 8d45475          (U8, independent)
                                 ├─► 9a884d9 ─► 620c44c          (U9, uses the flag)
                                 ├─► 0ad8576 ─► 37da891          (U12, uses the flag)
                                 ├─► 44de9af ─► ba487cb          (U2, independent)
                                 ├─► cd343e2 ─► 6cb949f          (U5, independent)
                                 ├─► de5485b ─► 6b91c33          (U13, independent)
                                 ├─► fe7269b ─► 58f6a52          (U11, edits the U9/U12 lambdas)
                                 ├─► 19762c8 ─► 61ebc1f          (U14, independent)
                                 └─► aa52175                     (README, describes everything above)
```

The commits form one linear history. The branches in this diagram show **logical** dependencies, not git branches.

Red commits add only tests (plus compile-only stubs where a new method does not exist yet, deviation D2). Green commits add only production code. Every public change is **additive**: no signature is removed or changed.

## Background

Before U12, `ParameterStoreClientFactory.createParameterStore(AwsParameterStoreConfig)` set only `apiCallTimeout` on the SSM client. Any `retryStrategy(..)` set on `AwsParameterStoreConfig.Builder` was silently ignored, so callers (for example appway) could not turn retries off or tune them for SSM. SES had the same gap (U9).

`BaseAwsConfig.getRetryStrategy()` never returns `null`: with nothing set it returns the commons default (STANDARD, 3 attempts). Applying `getRetryStrategy()` unconditionally would therefore change every existing unconfigured SSM client from the AWS SDK default (LEGACY, 4 attempts) to 3 attempts. Commit `8129389` added `BaseAwsConfig.isRetryStrategyConfigured()` (true only when `retryStrategy(..)` was given a non-null value) so factories can tell "explicitly set" from "defaulted".

## Why the factories silently ignored the retry strategy

In short: **the setting lived in a shared base class, but each factory decides which settings it copies to the AWS client, and the SSM and SES factories never copied this one.** Nothing checks for that, so no error, warning or test failure ever appeared.

```
 BaseAwsConfig (ION-11759, 2025-05-16)       shared by ALL services
   region, credentials, endpoint, timeouts,
   threadPoolSize, retryStrategy  ◄── every builder inherits retryStrategy(..)
        │
        ├── AwsStorageConfig     ──► S3ClientFactory          reads getRetryStrategy()  ✔
        ├── AwsMessagingConfig   ──► MessagingClientFactory   reads getRetryStrategy()  ✔
        ├── AwsNotificationConfig──► NotificationClientFactory reads getRetryStrategy() ✔
        ├── AwsSesEmailConfig    ──► EmailClientFactory        never read it  ✘ (until U9)
        └── AwsParameterStoreConfig ► ParameterStoreClientFactory never read it ✘ (until U12)
```

Step by step:

1. **The option exists everywhere.** `BaseAwsConfig` was created in ION-11759 to hold settings common to all AWS services, including `retryStrategy`. `AwsParameterStoreConfig extends BaseAwsConfig`, and its `Builder extends BaseAwsConfigBuilder`, so `AwsParameterStoreConfig.builder().retryStrategy(x)` compiles and stores `x`.
2. **The factory copies settings one by one.** `ParameterStoreClientFactory` (ION-11762, 2025-05) builds the `SsmClient` from region, endpoint, credentials, `clientExecutionTimeout` and the HTTP client only. Before `37da891` it read:

   ```java
   .overrideConfiguration(b -> b
       .apiCallTimeout(config.getClientExecutionTimeout()));   // no getRetryStrategy() anywhere
   ```

3. **Nothing complains.** There is no validation ("you set X but this factory does not support it"), no log line, and the client works normally, with the SDK's default retries. The caller's value is stored in the config and then never used.
4. **No test caught it.** The existing factory tests checked that a client is created, not that each inherited option reaches it. The new `*RetryStrategyTest` classes close that gap for SES and SSM.

Evidence (commands in [Commands used for this analysis](#commands-used-for-this-analysis)):
- `git grep -n "getRetryStrategy()" 0ad8576^ -- 'cloud-sdk-aws/src/main/*'`: before U12, readers were S3, SQS, SNS and SES (SES only after `620c44c`). No SSM.
- `git show 0ad8576^:.../ParameterStoreClientFactory.java`: the code above.
- `git log -S "retryStrategy" -- .../BaseAwsConfig.java`: the field was added in `0cc96c1` (ION-11759).

Lesson for future configs: **an inherited option needs a test per factory showing it reaches the client**, or an explicit "not supported" note in that factory's Javadoc.

### Commands used for this analysis

| Command | Why | Remember it as |
|---|---|---|
| `git show 0ad8576^:cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactory.java` | Print the whole file **as it was in the parent** of `0ad8576`. `^` means "parent of", `<rev>:<path>` means "this file at that commit" | "file at a point in time" |
| `git log --format="%h %ad %s" --date=short -- <file>` | Every commit that touched the file | "history of one file" |
| `git log -S "retryStrategy" -- <file>` | **Pickaxe:** only commits where the number of occurrences of the text changed (added or removed) | "who added or removed this word?" |
| `git grep -n "getRetryStrategy()" 0ad8576^ -- 'cloud-sdk-aws/src/main/*'` | Search the code **at a given commit**, not the working copy. `-n` adds line numbers | "grep back in time" |

## 1. 91cde62 build: commons 1.0.39-SNAPSHOT

`WI01124532 ION-12310 build: commons 1.0.39-SNAPSHOT`

**Change:** root `pom.xml`, one line: `<dependency.version>1.0.38-SNAPSHOT</dependency.version>` → `1.0.39-SNAPSHOT`.

**Why:** every module (`cloud-sdk-api`, `cloud-sdk-aws`, `commons`, `dynamo-integration-test`, ...) takes its version from this one property. The commits that follow add new public API (`getObjectSize`, `sendEmailWithResult`, `isRetryStrategyConfigured`, ...), so they need a new version. Consumers such as appway can then opt in by moving to 1.0.39 while 1.0.38 stays as it was.

**Tests:** none (build-only). Checked by the full build at `aa52175`: `mvn clean install` gave BUILD SUCCESS and installed every artifact as `1.0.39-SNAPSHOT` in `~/.m2`.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 91cde62 --stat --format="%h %ad %s%n%b" --date=short` | `pom.xml \| 2 +-` |
| `git --no-pager show 91cde62 --format=""` | The single `dependency.version` line |

## 2. 025f398 red: BaseAwsConfig must record whether retryStrategy was set

`WI01124532 ION-12310 red: BaseAwsConfig must record whether retryStrategy(..) was set`

**Change:**
- New test `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/aws/config/BaseAwsConfigTest.java` (69 lines, `@Nested RetryStrategyConfigured`).
- Compile-only stub in `BaseAwsConfig`: `public boolean isRetryStrategyConfigured() { return false; }` (deviation D2: the red commit must compile and fail on an **assertion**, not a compile error).

**Why it is needed:** `getRetryStrategy()` can never tell "the caller chose STANDARD/3" from "nobody chose anything, so commons filled in STANDARD/3". The flag tells the two apart, so a factory can apply a strategy only when one was asked for.

**Tests and why they behave as they do:**

| Test | Input | Expected | Red result | Why |
|---|---|---|---|---|
| `falseByDefault` | builder without `retryStrategy(..)` | flag `false`, `getRetryStrategy()` not null | pass | the stub returns `false`, which is right here; the getter still gives the commons default |
| `trueWhenConfigured` | `retryStrategy(doNotRetry())` | flag `true`, getter returns the **same** object (`isSameAs`) | **fail** | stub returns `false`. This is the test that drives the green commit |
| `falseWhenConfiguredWithNull` | `retryStrategy(null)` | flag `false`, getter not null | pass | `null` means "not set" and must not count as configured |
| `lastCallWins` | `retryStrategy(x)` then `retryStrategy(null)` | flag `false` | pass | the builder field is simply overwritten, so the last call decides |

Why `AwsStorageConfig` in a `BaseAwsConfig` test: `BaseAwsConfig` is abstract. Any concrete subclass exercises the shared constructor; the storage config is the simplest one to build (region and anonymous credentials only).

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 025f398 --stat --format="%h %ad %s%n%b" --date=short` | 2 files, +74 |
| `git --no-pager show 025f398 --format=""` | The stub and the 4 tests |

## 3. 8129389 green: BaseAwsConfig.isRetryStrategyConfigured()

`WI01124532 ION-12310 green: BaseAwsConfig.isRetryStrategyConfigured() records an explicit retryStrategy(..)`

**Change:** `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/aws/config/BaseAwsConfig.java` (+14/-2):

```java
private final boolean retryStrategyConfigured;   // new field
...
this.retryStrategyConfigured = builder.retryStrategy != null;  // read BEFORE the default below replaces null
this.retryStrategy = builder.retryStrategy != null ? builder.retryStrategy
                                                   : DefaultRetryStrategy.standardStrategyBuilder().build();
...
public boolean isRetryStrategyConfigured() { return retryStrategyConfigured; }
```

**The key detail is order:** the flag is read from the **builder** before the constructor replaces `null` with the commons default. Reading it afterwards would always give `true`.

```
builder.retryStrategy ──► null? ──yes──► flag=false, field=commons default (STANDARD, 3)
                            └─────no───► flag=true,  field=caller's strategy
```

- `final` field: the config is immutable, so it is safe to share between threads (Dropwizard resources).
- Additive public method with Javadoc; `getRetryStrategy()` behaves exactly as before.

**Tests:** the 4 tests from `025f398` all pass; `trueWhenConfigured` turns green.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 8129389 --stat --format="%s"` | `BaseAwsConfig.java` +14/-2 |
| `git --no-pager show 8129389 --format="" -- '*BaseAwsConfig.java' \| Select-Object -First 60` | The field, the constructor line, and the Javadoc |

## 4. 784af59 red: getObjectSize must use a single HEAD

`WI01124532 ION-12310 red: getObjectSize must use a single HEAD`

**Need (U3):** callers wanted an object's size. The only way was `getObject(..).getSize()`, which **downloads the whole object** just to read its length. An S3 `HeadObject` returns the `Content-Length` header with no body.

**Change:**
- Stub in `cloud-sdk-api/.../storage/api/StorageClient.java`: `default long getObjectSize(String bucketName, String key) { throw new UnsupportedOperationException("not implemented yet"); }`.
- New `cloud-sdk-api/src/test/.../storage/api/StorageClientObjectSizeDefaultTest.java` (40 lines).
- New `cloud-sdk-aws/src/test/.../storage/impl/S3StorageClientObjectSizeTest.java` (156 lines).

**Why a `default` method:** `StorageClient` is a public interface in `cloud-sdk-api`. Adding an abstract method would break every other implementation and every hand-written test double in consumer services. A `default` method keeps them compiling (API compatibility rule).

**Tests and why they behave as they do:**

`StorageClientObjectSizeDefaultTest` (the interface's own fallback):

| Test | Expects | How | Red |
|---|---|---|---|
| `defaultDelegatesToGetObjectSize` | 42, and `getObject` was called | Mockito `mock(StorageClient.class)` with `thenCallRealMethod()` on `getObjectSize`, so the **real default method** runs on top of a mocked `getObject` | fail (stub throws) |
| `defaultReturnsZeroWhenObjectIsNull` | 0 | `getObject` returns `null` | fail |

`S3StorageClientObjectSizeTest` (the S3 override; `S3Client` is a Mockito mock, so no network):

| Group | Test | Expects | Why |
|---|---|---|---|
| `Success` | `returnsContentLengthFromASingleHead` | 12345; `headObject` called once with the right bucket and key; `never()` `getObject` / `getObjectAsBytes` | `never()` proves nothing is downloaded |
| | `zeroLengthObjectReturnsZero` | 0 | an empty object is valid |
| | `missingContentLengthReturnsZero` | 0 | the SDK returns `Long` (nullable). Without a null check, unboxing would throw `NullPointerException` |
| `Errors` | `noSuchKeyMapsLikeGetMetadata` | same exception class and message as `getMetadata` | `getMetadata` also uses HEAD, so it is the reference for "same behaviour" |
| | `bare404IsTreatedAsMissingKey` | "Bucket ... does not contain key ..." | **a HEAD response has no body**, so S3 cannot send the `NoSuchKey` error code. The SDK then throws a plain `S3Exception` with status 404 instead of `NoSuchKeyException` |
| | `otherS3ExceptionMapsLikeGetMetadata` | 403 maps to `S3OperationException("Access Denied")` | same mapping as `getMetadata` |
| | `sdkClientExceptionMapsLikeGetMetadata` | `S3OperationException("connection reset")` | network errors are mapped the same way |
| `Validation` | `invalidBucketOrKeyIsRejectedWithoutAnSdkCall` (×4, `@ParameterizedTest @CsvSource(nullValues="NULL")`) | `IllegalArgumentException` and `verifyNoInteractions(s3ClientMock)` | null or blank bucket or key is rejected **before** any AWS call |

At red, all of these fail (the stub throws), except the `getMetadata` half of each comparison.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 784af59 --stat --format="%h %ad %s%n%b" --date=short` | 3 files, +201 |
| `git --no-pager show 784af59 --format=""` | The stub and both test classes |

## 5. 74445d1 green: StorageClient.getObjectSize with an S3 HEAD override

`WI01124532 ION-12310 green: StorageClient.getObjectSize with an S3 HEAD override`

**Change:**
- `StorageClient.getObjectSize` default (cloud-sdk-api): `StorageObject o = getObject(bucket, key); return o == null ? 0L : o.getSize();`. Correct for any implementation, but it downloads the object, so the Javadoc says implementations should override it.
- `S3StorageClient.getObjectSize` override (cloud-sdk-aws, +46):

```java
validateBucketName(bucketName); validateKey(key);              // fail fast, no SDK call
HeadObjectResponse r = s3Client.headObject(HeadObjectRequest.builder().bucket(b).key(k).build());
return r.contentLength() == null ? 0L : r.contentLength();
// catch order matters:
//   NoSuchKeyException          → "does not contain key"        (the most specific first)
//   S3Exception, status 404     → wrapped as NoSuchKeyException  (bare HEAD 404)
//   S3Exception, other          → handleS3Exception
//   SdkClientException          → handleSdkException
//   Exception                   → handleUnexpectedException      (existing pattern in this class)
```

`NoSuchKeyException` is a **subclass** of `S3Exception`, so it must be caught first. Otherwise the `S3Exception` block would swallow it.

**Tests:** all 13 from `784af59` pass (2 default + 11 S3, counting the 4 parameterised cases).

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 74445d1 --stat --format="%h %ad %s%n%b" --date=short` | 2 files, +64/-2 |
| `git --no-pager show 74445d1 --format=""` | The default body and the S3 override |

## 6. a87a1d5 red: sendEmailWithResult must return the SES message id

`WI01124532 ION-12310 red: sendEmailWithResult must return the SES message id`

**Need (U8):** `EmailService.sendEmail(..)` is `void`, so callers cannot record the SES `MessageId` needed to trace bounces and deliveries.

**Change:**
- Two stubs in `cloud-sdk-api/.../email/api/EmailService.java`, both `default` methods throwing `UnsupportedOperationException("not implemented yet")`:
  - `sendEmailWithResult(from, to, cc, bcc, content)` (5 arguments)
  - `sendEmailWithResult(from, to, content)` (3 arguments)
- New `cloud-sdk-api/src/test/.../EmailServiceSendWithResultDefaultTest.java` (55 lines).
- New `cloud-sdk-aws/src/test/.../SesEmailServiceImplSendWithResultTest.java` (247 lines).

**Tests and why they behave as they do:**

`EmailServiceSendWithResultDefaultTest` (interface defaults, via Mockito `thenCallRealMethod()`):

| Test | Expects | Why | Red |
|---|---|---|---|
| `fiveArgumentDefaultThrowsUnsupportedOperation` | `UnsupportedOperationException` with message "sendEmailWithResult is not supported by this EmailService implementation"; `sendEmail` **never** called | design choice: do **not** fall back to `void sendEmail`, because a result without a message id would look like a dropped email | fail (the stub message is different) |
| `threeArgumentDefaultDelegatesWithNullCcAndBcc` | the 3-argument form calls the 5-argument form with `null, null` | one real code path | fail (the stub throws) |

`SesEmailServiceImplSendWithResultTest` (`SesV2Client` is a mock; requests are captured with `ArgumentCaptor`):

| Group | Tests | Proves |
|---|---|---|
| `Result` (2) | `returnsSesMessageIdAndJoinedRecipients`, `threeArgumentFormReturnsSesMessageIdWithoutCcOrBcc` | `messageId` = SES `MessageId`; `emailAddress` = `to` joined with `","` |
| `SameRequestAsSendEmail` (3) | `simplePathRequestIsIdentical`, `threeArgumentFormRequestIsIdentical`, `rawMimePathRequestIsEquivalent` | Call `sendEmail` and `sendEmailWithResult` with the same input, capture both SDK requests, and compare them. The simple path must be **equal**. The raw MIME path (with an attachment) is compared **part by part** (subject, from, reply-to, to, cc, attachment name), because MIME output contains a generated `Message-ID`, `Date` and boundary that differ on every call |
| `Errors` (3) | SDK client, SDK service and other exceptions | same `SendEmailException` type and message as `sendEmail` |
| `Validation` (3) | blank sender, empty recipients, missing subject | `IllegalArgumentException` **before** any SDK call |
| `VoidSendEmailUnchanged` (2) | both `sendEmail` forms | the SDK is still called **exactly once**. This guards against double sending once `sendEmail` delegates (see green) |

At red, every test that calls `sendEmailWithResult` fails; the `VoidSendEmailUnchanged` tests pass.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show a87a1d5 --stat --format="%h %ad %s%n%b" --date=short` | 3 files, +313 |
| `git --no-pager show a87a1d5 --format="" -- '*EmailService.java' '*DefaultTest.java'` | Only the stubs and the default test (two pathspecs) |
| `git --no-pager show a87a1d5 --format="" -- '*SesEmailServiceImplSendWithResultTest.java' \| Select-String '^\+\s*(@Nested\|@Test\|void \|class )'` | An **outline** of the 247-line test: only the added lines (`^\+`) with annotations, classes and method names |
| `... \| Select-String -Pattern 'rawMimePathRequestIsEquivalent' -Context 0,40` | That one test plus the 40 lines after it |

## 7. 8d45475 green: EmailService.sendEmailWithResult returns the SES message id

`WI01124532 ION-12310 green: EmailService.sendEmailWithResult returns the SES message id`

**Change:**
- `EmailService` (cloud-sdk-api): the 5-argument default throws with a clear message; the 3-argument default delegates with `null` cc and bcc. Full Javadoc.
- `SesEmailServiceImpl` (cloud-sdk-aws, +24):

```java
public void sendEmail(from, to, cc, bcc, content) {
    sendEmailWithResult(from, to, cc, bcc, content);       // void now delegates: ONE code path
}
public EmailSendResult sendEmailWithResult(...) {
    validateEmailRequest(...);                             // the existing body moved here, unchanged
    ...
    SendEmailResponse response = sesClient.sendEmail(request);
    return EmailSendResult.builder()
        .messageId(response.messageId())
        .emailAddress(String.join(",", to))
        .build();
}
```

**Why delegate instead of copying the body:** with one code path the request, validation, logs and exceptions are the same **by construction**. The `SameRequestAsSendEmail` tests prove it, and `VoidSendEmailUnchanged` proves the delegation did not cause a second SES call.

**Tests:** all 15 pass (2 default + 13 SES). Review note R6: `emailAddress` holds only `to` (not cc or bcc), as the Javadoc says.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 8d45475 --stat --format="%h %ad %s%n%b" --date=short` | 2 files, +56/-4 |
| `git --no-pager show 8d45475 --format=""` | The delegation and the result builder |

## 8. 9a884d9 red: EmailClientFactory must apply a configured retry strategy

`WI01124532 ION-12310 red: EmailClientFactory must apply a configured retry strategy`

**Change:** test only. New `cloud-sdk-aws/src/test/.../email/factory/EmailClientFactoryRetryStrategyTest.java` (107 lines). Same design as the SSM test in commit 10; it was written first, and U12 copies it.

| Test | Expects | Red | Why |
|---|---|---|---|
| `doNotRetryReachesTheClient` | `maxAttempts` 1 | **fail** (reports 4) | the factory ignored the strategy (see [why](#why-the-factories-silently-ignored-the-retry-strategy)) |
| `customStandardStrategyReachesTheClient` | 2 | **fail** (reports 4) | 2 differs from every default (1, 3 and 4) |
| `unconfiguredClientKeepsTheAwsSdkDefault` | same as a reference `SesV2Client` with no strategy; 4 if LEGACY | pass | regression guard, deviation D1 |
| `timeoutsAreUnchangedWhenARetryStrategyIsSet` | `apiCallTimeout` **and** `apiCallAttemptTimeout` = 7 s | pass | SES sets **both** timeouts from `clientExecutionTimeout`. This proves the new retry code does not disturb them (SSM sets only `apiCallTimeout`, so its test checks just that one) |

The detailed reasoning (attempt counting, LEGACY vs STANDARD, the reference client, reflection) is the same as in [Why each test behaves the way it does](#why-each-test-behaves-the-way-it-does). Here reflection reads `SesEmailServiceImpl.sesClient`.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 9a884d9 --stat --format="%h %ad %s%n%b" --date=short` | 1 file, +107 |
| `git --no-pager show 9a884d9 --format="" \| Select-Object -First 70` and `... -Skip 70` | The test in two halves (to keep the output short) |

## 9. 620c44c green: EmailClientFactory applies the retry strategy only when configured

`WI01124532 ION-12310 green: EmailClientFactory applies the retry strategy only when configured`

**Change:** `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/factory/EmailClientFactory.java` (+10), inside the `overrideConfiguration` lambda of `createSesV2Client`, after the existing timeout lines:

```java
if (config.isRetryStrategyConfigured()) {
    overrideBuilder.retryStrategy(config.getRetryStrategy());
}
```

Javadoc was added to `createSesClient` and to the template variant, including an example: `AwsSesEmailConfig.builder()...retryStrategy(DefaultRetryStrategy.doNotRetry()).build()`.

| Caller config | Before | After |
|---|---|---|
| `retryStrategy(..)` set | ignored (SDK LEGACY, 4) | the given strategy |
| nothing set | SDK default | SDK default (unchanged) |

**Tests:** the 4 new tests and the existing `EmailClientFactoryTest` (4) pass.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 620c44c --stat --format="%h %ad %s%n%b" --date=short` | 1 file, +10 |
| `git --no-pager show 620c44c --format=""` | The `if` block and the Javadoc |

## 10. 0ad8576 red: SSM factory must apply a configured retry strategy

`WI01124532 ION-12310 red: ParameterStoreClientFactory must apply a configured retry strategy`

**Change:** test only. New file `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactoryRetryStrategyTest.java` (101 lines). No production code changed.

**Test setup:**
- Real `AwsParameterStoreConfig` builder: region `us-east-1`, static dummy credentials, `clientExecutionTimeout(12s)`.
- The factory returns a `CloudParameterStore`. The test asserts it is an `SsmCloudParameterStore`, reads its private `ssmClient` field by reflection, and inspects `ssmClient.serviceClientConfiguration().overrideConfiguration()`.
- No AWS call is made; only the built client configuration is checked.

**Tests:**

| Test | Input | Asserts |
|---|---|---|
| `doNotRetryReachesTheClient` | `retryStrategy(DefaultRetryStrategy.doNotRetry())` | strategy present, `maxAttempts() == 1`, `apiCallTimeout == 12s` |
| `customStandardStrategyReachesTheClient` | `standardStrategyBuilder().maxAttempts(2)` | strategy present, `maxAttempts() == 2`, `apiCallTimeout == 12s` |
| `unconfiguredClientKeepsTheAwsSdkDefault` (regression guard) | no `retryStrategy(..)` | same strategy class and max attempts as a reference `SsmClient` built directly from the SDK with no strategy; 4 attempts when `RetryMode.defaultRetryMode()` is LEGACY (so the commons 3-attempt default is **not** applied); `apiCallTimeout == 12s` |

**Expected result at this commit:** the first two tests fail (the factory ignores the strategy, so the client reports the SDK default of 4 attempts). The regression guard passes; it protects existing behaviour.

### Why each test behaves the way it does

#### Key idea: `maxAttempts` counts every try, including the first

```
maxAttempts = 1 first call + N retries

doNotRetry()          [call]                              = 1
standard maxAttempts(2) [call] → [retry]                    = 2
commons default (STANDARD) [call] → [retry] → [retry]          = 3
SDK default (LEGACY)  [call] → [retry] → [retry] → [retry] = 4
```

#### Three retry strategies are involved

| Name | Where it comes from | Class | `maxAttempts` |
|---|---|---|---|
| **SDK default** | Resolved by the AWS SDK when the client is built and **no** strategy was given | `DefaultLegacyRetryStrategy` | **4** |
| **Commons default** | `BaseAwsConfig` constructor when `retryStrategy(..)` is not called: `DefaultRetryStrategy.standardStrategyBuilder().build()` | `StandardRetryStrategy` | **3** |
| **Caller's strategy** | What the test passes to `retryStrategy(..)` | depends | 1 or 2 here |

Verified on 2026-11-16 with jshell against the module's test classpath (AWS SDK 2.30.24, `AWS_RETRY_MODE` not set, and `~/.aws/config` has no `retry_mode` or `max_attempts`):

```
defaultRetryMode=LEGACY
sdkDefault=DefaultLegacyRetryStrategy maxAttempts=4
commonsDefault(standard)=3
doNotRetry=1
standard(2)=2
```

#### How the strategy reaches the client (after the fix in `37da891`)

```
AwsParameterStoreConfig.builder()...retryStrategy(X)?.build()
        │
        ├─ X given     → retryStrategy = X,                 isRetryStrategyConfigured() = true
        └─ X not given → retryStrategy = commons default(3), isRetryStrategyConfigured() = false
                │
ParameterStoreClientFactory.createParameterStore(config)
        │
        ├─ flag true  → b.retryStrategy(X)    → SsmClient uses X
        └─ flag false → nothing set           → SDK resolves its own default:
                                                 AWS_RETRY_MODE env / aws.retryMode property / profile retry_mode
                                                 → none set → LEGACY → DefaultLegacyRetryStrategy (4)
```

The commons default (3) sits in the config but is **never passed on** when the flag is false. That is why the unconfigured client shows 4 attempts and not 3.

#### `doNotRetryReachesTheClient`: 1 attempt

- `DefaultRetryStrategy.doNotRetry()` is a strategy with `maxAttempts = 1`: one call and no retries.
- It is set explicitly, so `isRetryStrategyConfigured()` is true and the factory passes it to the `SsmClient` builder.
- The built client reports the strategy it was given, so `maxAttempts()` is 1.
- **At the red commit it failed:** the factory ignored the strategy, so the client reported the SDK default of 4, and `4 != 1`.

#### `customStandardStrategyReachesTheClient`: 2 attempts

- `standardStrategyBuilder().maxAttempts(2).build()` is the STANDARD strategy (exponential backoff with jitter, plus a token bucket) with the attempt limit lowered from its default of 3 to **2**: one call and one retry.
- 2 was chosen on purpose. It differs from **every** default (commons 3, SDK 4, `doNotRetry` 1), so the test can only pass if this exact strategy reached the client.
- **At the red commit it failed:** `4 != 2`.

#### `unconfiguredClientKeepsTheAwsSdkDefault`: LEGACY with 4 attempts, not the commons 3

- `retryStrategy(..)` is not called, so `BaseAwsConfig` stores the commons default (STANDARD, 3) and sets `retryStrategyConfigured = false`. The flag is read **before** the null is replaced by the default (see `8129389`).
- The factory sees `false` and sets no strategy.
- When `SsmClient.builder().build()` runs, the SDK fills in the missing strategy. In SDK 2.30 the default retry mode is **LEGACY** unless `AWS_RETRY_MODE`, the `aws.retryMode` system property or the profile's `retry_mode` says otherwise. LEGACY means `DefaultLegacyRetryStrategy` with 4 attempts (3 retries) for SSM.
- This matches the behaviour before 1.0.39. If the commons default were applied, every existing SSM consumer would quietly drop from 4 attempts to 3. The test guards against that.

Why the test compares with a reference client instead of asserting "empty" (deviation D1):

| What the spec expected | What SDK 2.30 actually does |
|---|---|
| No strategy set → `overrideConfiguration().retryStrategy()` is `Optional.empty()` | The built client reports the **resolved** strategy, so it is always present |

So the test:
1. Builds a reference `SsmClient` directly from the SDK, with no strategy.
2. Asserts **same class** and **same `maxAttempts`** as the factory's client. This holds in any environment.
3. Only when `RetryMode.defaultRetryMode() == LEGACY`, also asserts **4**. This rules out the commons 3. On a machine with `AWS_RETRY_MODE=standard` the SDK default becomes 3 and this assertion is skipped, so the test does not fail falsely (review note N6).

**At the red commit it passed:** the factory set nothing then too. That is expected for a regression guard.

#### Why `apiCallTimeout` is 12 s in all three

`clientExecutionTimeout(12s)` maps to `apiCallTimeout` (the total time for one API call, including all retries). The fix only adds the retry block and leaves the timeout line as it was. 12 s was chosen because it differs from the commons default of 30 s.

#### Why the test uses reflection

`CloudParameterStore` does not expose its `SsmClient`. The test reads the private `ssmClient` field of `SsmCloudParameterStore` to call `serviceClientConfiguration()`. This needs no network: the client is only built, never called. The trade-off: renaming the field makes the test fail with `NoSuchFieldException` (review note N4).

**Deviation D1:** the spec asked for "unconfigured → `overrideConfiguration().retryStrategy()` is empty". On AWS SDK 2.30 the built client always reports the strategy the SDK resolved, so "empty" cannot be observed. The guard compares against a reference SDK client instead. Same approach as U9 (`EmailClientFactory`).

### Commands used to review `0ad8576`

Full syntax breakdown for each command is in [Command reference](#command-reference-how-to-read-each-command).

| # | Command | Why | What it showed |
|---|---|---|---|
| 1 | `git --no-pager log --oneline -15 --all` | Get a quick view of recent commits on all branches | Latest commits (local agent checkpoints and the branch head `aa52175`) |
| 2 | `git --no-pager branch --show-current` | Find which branch is checked out | `feature/ION-12310-commons-cloudsdk-refactoring` |
| 3 | `git --no-pager show --stat --format="%H%n%an %ad%n%s%n%b" 0ad8576e...` | Commit header plus a per-file change summary, without the diff | Author Arijit Kundu, 2026-11-12, one file, +101 lines, test only |
| 4 | `git --no-pager log --format="%h %ad %s" --date=short feature/ION-12310-commons-cloudsdk-refactoring -25 --no-merges \| Select-String -NotMatch "Agent host"` | List the branch history without checkpoint noise, to find the green partner | `0ad8576` (red) directly followed by `37da891` (green) |
| 5 | `git --no-pager show 0ad8576 --format=""` | Show the diff only (no header) | The full new test class |
| 6 | `grep` tool (ripgrep): pattern `U12`, `-n`, `-C 2`, path `cloud-sdk-api\docs\2026-11-12-sdk-commons-changes-for-apway.md` | Find every mention of U12 in the design and progress doc | Spec §5.5a, deviation D1, review notes R7, N4, N6 |

## 11. 37da891 green: SSM factory applies the retry strategy only when configured

`WI01124532 ION-12310 green: ParameterStoreClientFactory applies the retry strategy only when configured`

**Change:** `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactory.java` (+10/-2).

```java
.overrideConfiguration(b -> {
    b.apiCallTimeout(config.getClientExecutionTimeout());
    // Apply the retry strategy only when the caller set one; otherwise leave the AWS SDK default (unchanged).
    if (config.isRetryStrategyConfigured()) {
        b.retryStrategy(config.getRetryStrategy());
    }
});
```

- The one-line lambda became a block. `apiCallTimeout` is unchanged.
- `retryStrategy` is set only when `isRetryStrategyConfigured()` is true.
- The `createParameterStore` Javadoc now states that the configured strategy is applied when set, otherwise the AWS SDK default applies.

**Behaviour:**

| Caller config | Before | After |
|---|---|---|
| `retryStrategy(..)` set | ignored, SDK default (LEGACY, 4 attempts) | the given strategy is used |
| nothing set | SDK default | SDK default (unchanged) |

**API compatibility:** no public signature changed. Only additive: callers who already set a retry strategy now get it honoured. Unconfigured clients are identical to before.

**Tests at this commit:** all three tests in `ParameterStoreClientFactoryRetryStrategyTest` pass. Existing `CloudParameterStoreClientFactoryTest` is unchanged and green.

### Commands used to review `37da891`

| # | Command | Why | What it showed |
|---|---|---|---|
| 1 | `git --no-pager show 37da891 --stat --format="%s%n%b"` | Subject, body and the files touched | One file, `ParameterStoreClientFactory.java`, +10/-2 |
| 2 | `git --no-pager show 37da891 --format=""` | Show the diff only | The lambda became a block with `if (config.isRetryStrategyConfigured())` |
| 3 | `git --no-pager show 8129389 --stat --format="%s"` | Inspect the prerequisite commit | `BaseAwsConfig.java` +14/-2 |
| 4 | `git --no-pager show 8129389 --format="" -- '*BaseAwsConfig.java' \| Select-Object -First 60` | Diff of one file only (pathspec), first 60 lines | The `retryStrategyConfigured` field is set before the null default is applied |
| 5 | `Test-Path cloud-sdk-api\docs; Get-ChildItem cloud-sdk-api\docs -Name` | Check that the docs folder exists and see how files are named | Folder exists; files are named `YYYY-MM-DD-slug.md` |
| 6 | `mvn -q -o test -pl cloud-sdk-aws -am "-Dtest=ParameterStoreClientFactory*Test" "-Dsurefire.failIfNoSpecifiedTests=false" 2>&1 \| Select-Object -Last 30` | Run only the SSM factory tests | BUILD SUCCESS |
| 7 | `Get-ChildItem cloud-sdk-aws\target\surefire-reports\*ParameterStoreClientFactory*.txt \| Get-Content` | Read the per-class test result files | 3/0/0 and 2/0/0 (see [Verification](#verification-2026-11-16)) |
| 8 | `"AWS_RETRY_MODE=[$env:AWS_RETRY_MODE]"`; `Select-String -Path ~\.aws\config -Pattern 'retry_mode\|max_attempts'` | Check whether anything overrides the SDK retry mode | Env var not set; the profile file exists but has no `retry_mode` or `max_attempts`, so the SDK uses LEGACY |
| 9 | `mvn -q -o dependency:build-classpath -pl cloud-sdk-aws -am "-Dmdep.outputFile=$env:TEMP\cp.txt" "-Dmdep.includeScope=test"` | Write the module's full test classpath (all jar paths) to a file | `cp.txt` with SDK 2.30.24 jars |
| 10 | `jshell --class-path $cp "$env:TEMP\r.jsh"` (`$cp` = only the `.jar` entries from `cp.txt`) | Run a small Java script that builds an `SsmClient` and prints each strategy's `maxAttempts` | LEGACY / 4, commons 3, `doNotRetry` 1, `standard(2)` 2 |

## 12. 44de9af red: putObject must accept zero-length content

`WI01124532 ION-12310 red: putObject must accept zero-length content`

**Need (U2):** AppianWay writes empty marker or placeholder files. `putObject` rejected an empty `byte[]`, a stream with length 0, and an empty or blank `String` as "invalid input", even though S3 stores empty objects without any problem.

**Change:** test only. New `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientZeroLengthPutTest.java` (199 lines). `S3Client` is a Mockito mock; the `PutObjectRequest` and `RequestBody` are captured with `ArgumentCaptor`.

**Tests and why they behave as they do** (10 tests; red: 6 fail, 4 pass):

| Group | Test | Expects | Red | Why |
|---|---|---|---|---|
| `Bytes` | `emptyArrayIsWritten` | one `putObject`; body `optionalContentLength() == 0`; empty body | **fail** | the old `validateContent` rejected `length == 0` |
| | `emptyArrayWithMetadataAndContentTypeIsWritten` | as above, plus `contentLength` 0, metadata and content type kept | **fail** | same validation |
| | `nullArrayIsStillRejected` | `IllegalArgumentException`; `verifyNoInteractions` | pass | `null` stays invalid (guard) |
| `Streams` | `emptyNonMarkableStreamIsWritten` | 0-byte object | **fail** | the old `validateInputStream` rejected `contentLength == 0` |
| | `emptyNonMarkableStreamWithMetadataAndContentTypeIsWritten` | 0-byte object, metadata kept | **fail** | same |
| | `nullStreamIsStillRejected` | rejected, no SDK call | pass | guard |
| | `negativeLengthIsStillRejected` | rejected, no SDK call | pass | guard |
| `Strings` | `emptyOrBlankStringIsWrittenAsIs` (`""`, `"  "`) | written with exactly those bytes, `text/plain; charset=UTF-8` | **fail** ×2 | the old String overload rejected `isBlank()` |
| | `nullStringIsStillRejected` | rejected, no SDK call | pass | guard |

Why a **non-markable** stream (a `FilterInputStream` whose `markSupported()` is false): validation used to probe the stream (`available()`, mark and reset) to see whether it held data. An empty or non-markable stream cannot pass that probe, so the test proves that a length of 0 skips the probe completely.

Why the stream "rejected" tests do not expect a plain `IllegalArgumentException`: the stream overloads validate **inside** their `try`, so the existing `handleUnexpectedException` wraps it in an `S3OperationException` (cause: `IllegalArgumentException`). The tests assert that existing behaviour; it was not changed.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 44de9af --stat=160 --format="%h %ad %s" --date=short` | 1 file, +199 (`--stat=160` widens the column so long paths are not cut) |
| `git --no-pager show 44de9af --format="" -- '*Test.java' \| Select-String '^\+\s*(@Nested\|@Test\|@ParameterizedTest\|@ValueSource\|void \|class \|.*assertThat\|.*verify)' \| ForEach-Object { $_.Line.Substring(1).TrimEnd() }` | Outline: groups, tests and assertions. `Substring(1)` removes the leading `+` |

## 13. ba487cb green: putObject writes zero-length content as an empty object

`WI01124532 ION-12310 green: putObject writes zero-length content as an empty object`

**Change:**
- `AbstractStorageObject.validateContent(byte[])`: `content == null || content.length == 0` → `content == null`.
- `AbstractStorageObject.validateInputStream(InputStream, long)`:

```
null stream            → reject (unchanged)
contentLength < 0      → reject (unchanged)
contentLength > MAX    → reject (unchanged)
contentLength == 0     → return early: no probe, accepted     ◄── new
contentLength > 0      → probe available() as before (unchanged)
```

- `S3StorageClient.putObject(String, String, String)`: `content == null || content.isBlank()` → `content == null`. Javadoc: "empty or blank content is written as is".

No `RequestBody` code changed: `fromBytes(new byte[0])`, `fromInputStream(in, 0)` and `fromString("")` already produce `Content-Length: 0`.

**Tests:** all 10 pass; the existing `S3StorageClientPutObjectTest` is unchanged and green.

**Caller-visible change** (README item 8; review notes R2 and R3):
- A stream with a declared length of 0 is now written as an empty object, **without reading the stream**. A caller that passes 0 to mean "unknown length" now silently gets an empty object instead of an error.
- The error messages still say "null or empty", although only `null` is rejected. The text was kept so that callers matching on it do not break.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show ba487cb --format=""` | The three relaxed checks |

## 14. cd343e2 red: receive must send VisibilityTimeout only when requested

`WI01124532 ION-12310 red: receive must send VisibilityTimeout only when requested`

**Need (U5):** AppianWay needs a per-receive SQS `VisibilityTimeout`, the time a received message stays hidden from other consumers. `ReceiveMessageOptions.Builder.visibilityTimeoutSeconds(int)` already existed, but `SqsMessagingClient` **never sent it**.

**Why a new method instead of fixing the old one:** existing consumers already call the old method; bill-of-lading-v2, for example, sets 300. They have always run with the queue's default. Starting to send their value now would silently change how their queues behave. So the old method stays "stored, not sent", and a **new** method sends its value.

```
visibilityTimeoutSeconds(300)          → stored, getVisibilityTimeoutSeconds() = 300, NOT sent   (unchanged)
requestVisibilityTimeoutSeconds(45)    → validated 0..43200, SENT as VisibilityTimeout=45      (new)
neither                                → nothing sent, the queue default applies               (unchanged)
```

**Change:**
- Stubs in `cloud-sdk-api/.../messaging/model/ReceiveMessageOptions.java`: `isVisibilityTimeoutRequested()` returns `false`, `getRequestedVisibilityTimeoutSeconds()` returns `OptionalInt.empty()`, and `Builder.requestVisibilityTimeoutSeconds(int)` does nothing.
- New `cloud-sdk-api/src/test/.../ReceiveMessageOptionsRequestVisibilityTest.java` (72 lines).
- New `cloud-sdk-aws/src/test/.../SqsMessagingClientReceiveVisibilityTest.java` (94 lines). The `SqsClient` is mocked, and the `ReceiveMessageRequest` is captured.

**Tests and why they behave as they do** (13 tests; red: 8 fail):

| Class | Test | Expects | Red | Why |
|---|---|---|---|---|
| Options | `notRequestedByDefault` | `false`, empty, old getter 30 | pass | the stub defaults are already correct |
| | `requestedValueIsKept` (0, 45, 43200) | `true`, value kept, old getter still 30 | **fail** ×3 | the stub stores nothing. 0 and 43200 are the SQS limits (43200 s = 12 h) |
| | `outOfRangeIsRejected` (-1, 43201) | `IllegalArgumentException` | **fail** ×2 | the stub does not validate. These are the values just outside the limits |
| | `oldBuilderMethodIsStoredButNotRequested` | 300 stored, not requested | pass | regression guard for bill-of-lading-v2 |
| | `bothMethodsAreIndependent` | 300 stored **and** 0 requested | **fail** | 0 is a valid request ("visible again now"), so it must not be confused with "not set" |
| SQS client | `notRequestedSendsNoVisibilityTimeout` | `request.visibilityTimeout()` is `null` | pass | nothing is sent today |
| | `oldBuilderValueIsStillNotSent` | 300 → `null` | pass | guard |
| | `requestedValueIsSent` (0, 45) | the request carries 0 or 45 | **fail** ×2 | the client does not read the option yet |
| | `otherFieldsAreUnchanged` | the request, apart from visibility, equals the expected request | pass | the new code must not touch queue URL, max messages, wait time or attribute names |

Why `Integer` and `OptionalInt`, not `int`: `0` is a legal value, so "not set" needs its own state (`null` → `OptionalInt.empty()`).

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show cd343e2 --stat=160 --format="%h %ad %s" --date=short` | 3 files, +182 |
| `git --no-pager show cd343e2 --format="" -- '*ReceiveMessageOptions.java'` | The three stubs |
| Outline command as in section 12 | The 13 tests and their assertions |

## 15. 6cb949f green: requestVisibilityTimeoutSeconds is sent on receive

`WI01124532 ION-12310 green: ReceiveMessageOptions.requestVisibilityTimeoutSeconds is sent on receive`

**Change:**
- `ReceiveMessageOptions` (cloud-sdk-api, +47/-5):
  - New field `private final Integer requestedVisibilityTimeoutSeconds` with `@Getter(AccessLevel.NONE)`. That stops Lombok generating a plain `Integer` getter beside the `OptionalInt` one.
  - Builder constant `MAX_VISIBILITY_TIMEOUT_SECONDS = 43200`; `requestVisibilityTimeoutSeconds(int)` validates the range and stores the value.
  - The old `visibilityTimeoutSeconds(int)` gets Javadoc only: "Stored only; not sent on receive".
- `SqsMessagingClient.receiveMessages(ReceiveMessageOptions)` (+2):

```java
options.getRequestedVisibilityTimeoutSeconds().ifPresent(requestBuilder::visibilityTimeout);
```

`ifPresent(...)` means nothing is added when the value was not requested, so existing requests are byte-for-byte the same.

**Tests:** all 13 pass; the existing `ReceiveMessageOptionsTest`, `SqsMessagingClientTest` and `SqsListenerTest` are unchanged and green.

**Review note N1:** deprecate the old `visibilityTimeoutSeconds(int)` in a later release. Also, `SqsListener` cannot pass the new option yet.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 6cb949f --format=""` | The field, the validation and the one-line send |

## 16. de5485b red: S3 presigner must not resolve credentials eagerly and must use the config region

`WI01124532 ION-12310 red: S3 presigner must not resolve credentials eagerly and must use the config region`

**Need (U13), three problems in the old code:**

| # | Problem | Impact |
|---|---|---|
| 1 | `S3StorageClient.createPresigner()` called `resolveCredentials()` **at construction** and logged `Using Access Key ID: <id>` at INFO | a credential identifier in the logs (security finding); a credential lookup on every client build, and WARN noise when no credentials exist |
| 2 | `StorageClientFactory.createS3Client(config)` built the presigner with **us-east-1 and the default credentials chain**, ignoring the config | presigned URLs for buckets in other regions were signed for the wrong region, and possibly with different credentials than the `S3Client` |
| 3 | `paramstore/main/Main.java` logged `accessKeyId().substring(0, 20) + "..."` | an access key id **is** 20 characters, so this "prefix" was the whole key |

**Change:**
- Stub (deviation D2): `createPresigner()` now delegates to a new package-private `createPresigner(AwsCredentialsProvider)`, which still has the **old eager behaviour**. This gives the test a seam, so it can pass a counting provider.
- New `cloud-sdk-aws/src/test/.../storage/impl/S3StorageClientConstructionTest.java` (89 lines). It attaches a Logback `ListAppender` to the `S3StorageClient` logger to capture log events.
- New `cloud-sdk-aws/src/test/.../storage/factory/StorageClientFactoryPresignerTest.java` (87 lines). It signs URLs **offline** with the static key `AKIDEXAMPLE`; presigning needs no network.

**Tests and why they behave as they do** (6 tests; red: 4 fail):

| Class | Test | Expects | Red | Why |
|---|---|---|---|---|
| Construction | `creatingThePresignerResolvesNoCredentials` | counting provider: **0** calls | **fail** (1) | the old code resolves at once |
| | `constructorLogsNoAccessKeyId` | no log event contains "Access Key" or "Resolved AWS credentials" | pass *on this machine* | there are no default-chain credentials here, so the old code logged a WARN and never reached the key line. The counting-provider test is the one that proves the fix on any machine |
| | `credentialsAreResolvedOnlyWhenAUrlIsSigned` | 0 calls after construction, > 0 after `generatePresignedUrl`, and the URL carries `X-Amz-Credential=AKIDEXAMPLE/` | **fail** | eager resolution |
| Factory | `urlIsSignedForTheConfiguredRegionAndCredentials` | eu-west-1 config: host contains `eu-west-1`, scope `/eu-west-1/s3/aws4_request` | **fail** | the old presigner was always us-east-1 |
| | `usEast1ConfigIsStillSignedForUsEast1` | `X-Amz-Credential=AKIDEXAMPLE/` and `/us-east-1/s3/` | **fail** | the region matches, but the old presigner used the **default chain**, not the config's `AKIDEXAMPLE` |
| | `defaultClientIsUnchanged` | `createDefaultS3Client()` still signs for us-east-1 | pass | guard. It sets the `aws.accessKeyId` and `aws.secretAccessKey` system properties so the default chain resolves on a machine without credentials, and restores them in `finally` (review note N5) |

How to read a SigV4 presigned URL (this is what the assertions look at):

```
https://bucket.s3.eu-west-1.amazonaws.com/key?...&X-Amz-Credential=AKIDEXAMPLE/20261116/eu-west-1/s3/aws4_request&...
                     └── host region ──┘                           └ key id ┘ └ date ┘ └region┘└svc┘
```

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show de5485b --stat=160 --format="%h %ad %s" --date=short` | 3 files, +181/-1 |
| `git --no-pager show de5485b --format="" -- '*S3StorageClient.java'` | The stub seam |
| Outline command as in section 12, with `.*System\.setProperty` added to the pattern | The tests and the system-property setup |

## 17. 6b91c33 green: no access key id log, lazy presigner credentials, createS3Client presigner from config

`WI01124532 ION-12310 green: no access key id log, lazy presigner credentials, createS3Client presigner from config`

**Change:**
- **Step 1, `S3StorageClient.createPresigner(AwsCredentialsProvider)`:** the eager `resolveCredentials()`, both INFO lines and both WARN catch blocks are removed. One DEBUG line logs only the provider's **class name**. The SDK presigner resolves credentials **lazily**, when a URL is signed.
- **Step 2, `StorageClientFactory.createS3Client(config)`:**

```java
S3Presigner presigner = S3Presigner.builder()
    .region(config.getRegion().getRegionDelegate())                                 // was always us-east-1
    .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate()) // was the default chain
    .build();
return new S3StorageClient(s3Client, presigner);                                   // existing constructor
```

  Javadoc: the presigner shares the caller's credentials provider, and closing a presigner closes its provider, so the client **never closes** its presigner.
- **Step 3, `paramstore/main/Main.java`:** the access-key log line is deleted.
- `createDefaultS3Client()` is unchanged (us-east-1, default chain).

**Tests:** all 6 pass; the existing `S3StorageClientGeneratePresignedUrlTest` and `StorageClientFactoryTest` are unchanged and green.

**Review note R9 / F1:** the presigner still ignores `endpointOverride` (LocalStack, VPC endpoints). That is not a regression.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 6b91c33 --format=""` | The three steps |

## 18. fe7269b red: noClientExecutionTimeout() must leave the API-call timeout unset

`WI01124532 ION-12310 red: noClientExecutionTimeout() must leave the API-call timeout unset`

**Need (U11):** every factory turned `clientExecutionTimeout` into the SDK's `apiCallTimeout`, the cap on one whole API call including all retries. The default is 30 s for S3. AppianWay has calls that can legitimately take longer, such as large transfers, and needs a way to switch that cap **off**. Before this, the only option was to set a very large value.

The two timeouts:

```
apiCallTimeout        ├──────────── whole call: attempt 1 + backoff + attempt 2 + ... ────────────┤
apiCallAttemptTimeout ├── attempt 1 ──┤        ├── attempt 2 ──┤
socket timeout          (HTTP client) idle time between bytes on one read only
```

**Change:**
- Stubs in `BaseAwsConfig`: `Builder.noClientExecutionTimeout()` does nothing, and `isClientExecutionTimeoutDisabled()` returns `false`.
- `BaseAwsConfigTest`: new `@Nested ClientExecutionTimeoutDisabled` (3 tests).
- New `cloud-sdk-aws/src/test/.../aws/config/NoClientExecutionTimeoutFactoryTest.java` (315 lines), with one `@Nested` class per factory. Each builds a real client and reads `serviceClientConfiguration().overrideConfiguration()` (by reflection on the private client field). For DynamoDB it calls the public `createOverrideConfig` instead.

**Tests and why they behave as they do** (22 tests; red: 7 fail, one "disabled" test per factory plus one flag test):

| Group | Test | Expects | Red |
|---|---|---|---|
| `BaseAwsConfigTest` | `falseByDefault` | `false`, 30 s | pass |
| | `trueAfterNoClientExecutionTimeout` | `true`; the getter **still** returns 30 s (never null, so existing readers do not get an NPE) | **fail** |
| | `laterTimeoutReEnables` | `noClientExecutionTimeout().clientExecutionTimeout(5s)` → `false`, 5 s (**last call wins**) | pass (the stub never disables) |
| Per factory: `S3`, `Sqs`, `Sns`, `Ssm`, `DynamoDb`, `Ses` | `defaultConfigKeepsTodaysTimeout(s)` | today's `apiCallTimeout` (S3 30 s, SSM 10 s, SES 10 s/10 s, ...) | pass (guard) |
| | `noClientExecutionTimeoutSets…None` | `apiCallTimeout` **empty**; everything else kept: S3 retry (2 attempts), SQS/SNS attempt timeout 3 s, SSM `doNotRetry` (1 attempt) | **fail** ×6 |
| | `laterClientExecutionTimeoutWins` | 5 s | pass |
| `DynamoDb` only | `explicitApiCallTimeoutStillApplies` | an explicit `apiCallTimeout(20s)` / `apiCallAttemptTimeout(4s)` is still applied | pass |
| `Ses` only | `noClientExecutionTimeoutSetsNeitherTimeout` | **both** SES timeouts empty, because SES derives both from the same setting | **fail** (counted in the ×6) |

Why each "disabled" test also checks that **other** settings are kept: the green change edits each factory's override builder, and these checks prove it removes only the one timeout.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show fe7269b --stat=160 --format="%h %ad %s" --date=short` | 3 files, +359 |
| `git --no-pager show fe7269b --format="" -- '*BaseAwsConfig.java'` | The two stubs |
| Outline command as in section 12, with `@DisplayName` added and `\| Select-Object -First 140` | The 22 tests, grouped by factory |

## 19. 58f6a52 green: noClientExecutionTimeout() lets the factories set no API-call timeout

`WI01124532 ION-12310 green: noClientExecutionTimeout() lets the factories set no API-call timeout`

**Change** (12 files, +66/-25):

| File | Change |
|---|---|
| `BaseAwsConfig` | New `final boolean clientExecutionTimeoutDisabled` and `isClientExecutionTimeoutDisabled()`. `noClientExecutionTimeout()` sets the flag and clears the base field. `clientExecutionTimeout(d)` now also clears the flag (last call wins) |
| `AwsMessagingClientConfig`, `NotificationClientConfig`, `DynamoDbClientConfig`, `AwsParameterStoreConfig`, `AwsSesEmailConfig` | One line in each builder's own `clientExecutionTimeout(Duration)`: `this.clientExecutionTimeoutDisabled = false;` |
| `S3ClientFactory.createOverrideConfig` | Rewritten onto one builder: retry logic unchanged, `apiCallTimeout` only if not disabled |
| `MessagingClientFactory`, `NotificationClientFactory` | The timeout block is wrapped in `if (!config.isClientExecutionTimeoutDisabled())`. `requestTimeout` → `apiCallAttemptTimeout` is unchanged |
| `DynamoRepositoryFactory` | Only the clientExecutionTimeout-derived default is skipped; an explicit `apiCallTimeout` still applies |
| `ParameterStoreClientFactory` | `apiCallTimeout` only if not disabled; the U12 retry block is unchanged |
| `EmailClientFactory` | Neither `apiCallTimeout` nor `apiCallAttemptTimeout` is set when disabled |

**Why five subclasses needed a one-line change (deviation D3):** these subclasses **shadow** `clientExecutionTimeout(Duration)` with their own builder field and method, which never reach the base builder. Without the reset line, `noClientExecutionTimeout().clientExecutionTimeout(5s)` would stay disabled for SQS, SNS, DynamoDB, SSM and SES.

```
AwsStorageConfig.Builder ──inherits──► BaseAwsConfigBuilder.clientExecutionTimeout()   (resets the flag)
AwsSesEmailConfig.Builder ──overrides─► own clientExecutionTimeout()                    (needed its own reset)
```

**Tests:** all 22 pass. Existing `AllFactoriesBuilderModeTest`, `MessagingClientFactoryTest`, `EmailClientFactoryTest`, `CloudParameterStoreClientFactoryTest` and `*ConfigTest` are unchanged and green.

**Review notes:**
- R1: "bounded by the socket timeout" over-promises. A socket timeout is an idle timeout per read, so the total call time has **no** upper bound.
- R8: after `noClientExecutionTimeout()`, the subclass getters still return the old value.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 58f6a52 --stat=160 --format="%h %ad %s" --date=short` | 12 files |
| `git --no-pager show 58f6a52 --format=""` | Every per-factory `if (!config.isClientExecutionTimeoutDisabled())` |

## 20. 19762c8 red: getObject must make one GET and no HEAD

`WI01124532 ION-12310 red: getObject must make one GET and no HEAD`

**Need (U14):** `S3StorageClient.getObject` made a GET (the body) and **then a HEAD** (size, eTag, last-modified). That cost two S3 requests per read and added latency. If the object was overwritten between the two calls, the metadata could also describe a **different version** than the body. The GET response already has all of these fields.

**Change:** `cloud-sdk-aws/src/test/.../storage/impl/S3StorageClientGetObjectTest.java` (+82/-7):
- **One pre-approved change to an existing test**, `testGetObjectSuccessfully`: `contentLength` and `eTag` moved from a `HeadObjectResponse` onto the `GetObjectResponse`; the HEAD stub was deleted; and `verify(headObject(..))` became `verify(s3ClientMock, never()).headObject(any())`. Its four assertions (key, size, eTag, content) are unchanged.
- 4 new tests appended.

**Tests and why they behave as they do** (red: 4 fail):

| Test | Expects | Red | Why |
|---|---|---|---|
| `testGetObjectSuccessfully` (changed) | same values, from the GET only; `never()` HEAD | **fail** | the old code still calls `headObject`. It is no longer stubbed, so Mockito returns `null` and `null.contentLength()` throws an NPE |
| `getObjectMakesOneGetAndNoHead` | `times(1)` GET, `never()` HEAD | **fail** | same NPE path |
| `getObjectTakesEveryFieldFromTheGetResponse` | size, eTag, lastModified, contentType, metadata and content all come from the GET | **fail** | same |
| `sizeFallsBackToTheBodyLengthWhenTheGetCarriesNoContentLength` | size = body length | **fail** | same |
| `errorMappingIsUnchangedAndNoHeadIsMade` | `NoSuchKeyException`, 403 and `SdkClientException` from the GET map to `S3OperationException` as before; `never()` HEAD | pass | the GET throws before the HEAD is reached. `reset(mock)` between cases gives each scenario a clean mock |

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 19762c8 --format=""` | The changed test (the `-` and `+` lines show exactly what moved) and the 4 new tests |

## 21. 61ebc1f green: getObject builds the result from the GET response, no extra HEAD

`WI01124532 ION-12310 green: getObject builds the result from the GET response, no extra HEAD`

**Change:** `S3StorageClient.getObject` (+9/-10):

```java
GetObjectResponse response = objectContent.response();          // metadata that came with the GET
long size = response.contentLength() != null ? response.contentLength()
                                             : objectContent.asByteArray().length;   // fallback
... .size(size).eTag(response.eTag()).lastModified(response.lastModified()) ...
// the headObject(...) call is deleted
```

```
before:  GET (body) ──► HEAD (size, eTag, lastModified)    2 requests, possible version mismatch
after:   GET (body + size, eTag, lastModified)             1 request, always the same version
```

- The INFO log line keeps its text and level; it now logs `size` (the same value).
- Error handling is unchanged.

**Tests:** all `S3StorageClientGetObjectTest` tests pass.

**Review notes:**
- N2: `getObject` still logs at INFO on every read.
- N3: the fallback `asByteArray()` copies the whole buffer just to measure it; `asByteBuffer().remaining()` would avoid the copy.
- F4: the body is still fully buffered; streaming would need a new method.

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show 61ebc1f --format=""` | The removed HEAD and the fields taken from the GET |

## 22. aa52175 docs: README release note for 1.0.39-SNAPSHOT

`WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT`

**Change:** `README.md` (+45): a new section `### Commons v1.0.39-SNAPSHOT` after the 1.0.38 notes. Line endings are CRLF, like the rest of the file. No code and no tests.

| README item | Commits | Section here |
|---|---|---|
| 1 `getObjectSize` | `784af59`, `74445d1` | 4–5 |
| 2 `sendEmailWithResult` | `a87a1d5`, `8d45475` | 6–7 |
| 3 SES and SSM honour `retryStrategy(..)` | `025f398` .. `37da891` | 2–3, 8–11 |
| 4 `requestVisibilityTimeoutSeconds` | `cd343e2`, `6cb949f` | 14–15 |
| 5 `noClientExecutionTimeout()` | `fe7269b`, `58f6a52` | 18–19 |
| 6 `getObject` makes one GET | `19762c8`, `61ebc1f` | 20–21 |
| 7 access key id no longer logged | `de5485b`, `6b91c33` | 16–17 |
| 8 zero-length writes allowed (**noticeable**) | `44de9af`, `ba487cb` | 12–13 |
| 9 presigner uses the config region and credentials (**noticeable**) | `de5485b`, `6b91c33` | 16–17 |

Items 1–7 are additive or opt-in. Items 8 and 9 are listed under "Changes that existing callers may notice".

**Commands used**

| Command | What it showed |
|---|---|
| `git --no-pager show aa52175 --format=""` | The 45 added README lines |
| `git --no-pager log --oneline -1 feature/ION-12310-commons-cloudsdk-refactoring` and `git --no-pager rev-parse --short origin/feature/ION-12310-commons-cloudsdk-refactoring` | The local branch tip and the remote tip are both `aa52175`, so this is HEAD and it has been pushed |

## Verification (2026-11-16)

All tests added in commits 2–11, plus the existing factory tests, re-run on the branch head (`aa52175`):

```
mvn -q -o test -pl cloud-sdk-api,cloud-sdk-aws "-Dtest=BaseAwsConfigTest,StorageClientObjectSizeDefaultTest,S3StorageClientObjectSizeTest,EmailServiceSendWithResultDefaultTest,SesEmailServiceImplSendWithResultTest,EmailClientFactoryRetryStrategyTest,EmailClientFactoryTest,ParameterStoreClientFactory*Test,CloudParameterStoreClientFactoryTest" "-Dsurefire.failIfNoSpecifiedTests=false"
```

- `-pl a,b`: both modules are listed, so `-am` is not needed (`cloud-sdk-api` is the only upstream module of `cloud-sdk-aws` that matters here).
- `-Dtest=A,B,C*`: a comma-separated list; `*` is a wildcard.

| Commit(s) | Test class | Module | Run | Failures + errors |
|---|---|---|---|---|
| 2–3 | `BaseAwsConfigTest` | aws | 7 (4 from `025f398`, 3 added later by U11) | 0 |
| 4–5 | `StorageClientObjectSizeDefaultTest` | api | 2 | 0 |
| 4–5 | `S3StorageClientObjectSizeTest` | aws | 11 (3 + 4 + 4 parameterised) | 0 |
| 6–7 | `EmailServiceSendWithResultDefaultTest` | api | 2 | 0 |
| 6–7 | `SesEmailServiceImplSendWithResultTest` | aws | 13 (2 + 3 + 3 + 3 + 2) | 0 |
| 8–9 | `EmailClientFactoryRetryStrategyTest` | aws | 4 | 0 |
| 8–9 | `EmailClientFactoryTest` (existing) | aws | 4 | 0 |
| 10–11 | `ParameterStoreClientFactoryRetryStrategyTest` | aws | 3 | 0 |
| 10–11 | `CloudParameterStoreClientFactoryTest` (existing) | aws | 2 | 0 |
| | **Subtotal, commits 1–11** | | **48** | **0** |

Second run, for commits 12–22:

```
mvn -q -o test -pl cloud-sdk-api,cloud-sdk-aws "-Dtest=S3StorageClientZeroLengthPutTest,S3StorageClientPutObjectTest,ReceiveMessageOptionsRequestVisibilityTest,ReceiveMessageOptionsTest,SqsMessagingClientReceiveVisibilityTest,StorageClientFactoryPresignerTest,S3StorageClientConstructionTest,S3StorageClientGeneratePresignedUrlTest,NoClientExecutionTimeoutFactoryTest,BaseAwsConfigTest,S3StorageClientGetObjectTest" "-Dsurefire.failIfNoSpecifiedTests=false" *> $env:TEMP\mvn-rest.log
```

`*>` sends **all** PowerShell output streams to the file, so the console stays clean; `$LASTEXITCODE` then gives Maven's exit code (0 means success).

| Commit(s) | Test class | Module | Run | Failures + errors |
|---|---|---|---|---|
| 12–13 | `S3StorageClientZeroLengthPutTest` | aws | 10 | 0 |
| 12–13 | `S3StorageClientPutObjectTest` (existing) | aws | 62 | 0 |
| 14–15 | `ReceiveMessageOptionsRequestVisibilityTest` | api | 8 | 0 |
| 14–15 | `ReceiveMessageOptionsTest` (existing) | api | 4 | 0 |
| 14–15 | `SqsMessagingClientReceiveVisibilityTest` | aws | 5 | 0 |
| 16–17 | `S3StorageClientConstructionTest` | aws | 3 | 0 |
| 16–17 | `StorageClientFactoryPresignerTest` | aws | 3 | 0 |
| 16–17 | `S3StorageClientGeneratePresignedUrlTest` (existing) | aws | 15 | 0 |
| 18–19 | `NoClientExecutionTimeoutFactoryTest` | aws | 19 | 0 |
| 18–19 | `BaseAwsConfigTest` (4 from section 2 + 3 from section 18) | aws | 7 | 0 |
| 20–21 | `S3StorageClientGetObjectTest` (5 existing, one changed, + 4 new) | aws | 9 | 0 |
| | **Subtotal, commits 12–22** | | **145** | **0** |

All tests added on the branch pass (`BaseAwsConfigTest` was counted in both runs).

JUnit 5 `@Nested` classes get their own report file (`Outer$Inner.txt`), so the counts above add up the outer and inner files. The PowerShell used:

```powershell
$files = Get-ChildItem cloud-sdk-api\target\surefire-reports\*.txt, cloud-sdk-aws\target\surefire-reports\*.txt
foreach ($n in 'BaseAwsConfigTest','S3StorageClientObjectSizeTest' <# ... #>) {
  $m = $files | Where-Object { $_.Name -match "\.$n(\$.*)?\.txt$" }   # Outer.txt and Outer$Inner.txt
  # read "Tests run: N, Failures: F, Errors: E" from each file and add them up
}
```

Git Bash equivalent: `cat cloud-sdk-aws/target/surefire-reports/*S3StorageClientObjectSizeTest*.txt | grep "Tests run" | awk -F'[ ,]+' '{s+=$3} END {print s}'` (`awk` splits on spaces and commas, and field 3 is N).

Full build at `aa52175` (`mvn clean install`, recorded 2026-11-12): BUILD SUCCESS, 2695 tests green.

## Command reference: how to read each command

### The review flow at a glance

```
 git log ──► find commits ──► git show --stat ──► which files?
                                    │
                                    ▼
                             git show --format=""  ──► the diff
                                    │
                                    ▼
                  grep the design doc ──► why (spec, deviations, review notes)
                                    │
                                    ▼
                  mvn test (only these tests) ──► proof that it works
```

### Red / green pairs (TDD)

```
 0ad8576  red    add a test that FAILS   (test only, no production code)
    │
    ▼
 37da891  green  smallest fix so it PASSES   (production code only)
```

Rule of thumb: **red = what should happen, green = how it happens**. Review the red commit first.

### git

Remember: **`git log` = which commits, `git show` = what is inside one commit.**

| Piece | Meaning | Remember it as |
|---|---|---|
| `--no-pager` | Print straight to the terminal; do not open `less`. Put it before the subcommand | "no scrolling trap" |
| `log` | List commits, newest first | the history book |
| `--oneline` | One line per commit: short hash and subject | headline view |
| `-15` / `-25` | Show at most N commits | "top N" |
| `--all` | Include every branch, not just the current one | widest view |
| `--no-merges` | Leave out merge commits | real work only |
| `branch --show-current` | Print the name of the checked-out branch | "where am I?" |
| `show <sha>` | Header and full diff of one commit | open one commit |
| `--stat` | Per-file summary (`file \| 12 ++--`) instead of the full diff | table of contents |
| `--format="..."` | Custom header. `--format=""` means print **no header**, so only the diff is shown | template |
| `-- <path>` | Pathspec: limit the output to matching files. `'*BaseAwsConfig.java'` matches the file in any folder | "only this file" |
| `--date=short` | Show dates as `YYYY-MM-DD` | ISO date |
| `<sha>^` | The parent of a commit (`^^` is the grandparent, `~3` is three back) | "one step up" |
| `show <rev>:<path>` | The whole file as it was at that commit | "file at a point in time" |
| `log -S "text"` | Pickaxe: only commits that added or removed `text` | "who introduced this?" |
| `grep -n "text" <rev> -- <pathspec>` | Search the code as it was at `<rev>` (the working copy is not touched) | "grep back in time" |
| `-- 'a' 'b'` | Several pathspecs at once | "only these files" |
| `--stat=160` | Make the `--stat` output 160 columns wide, so long paths are not shortened to `...` | wide table of contents |
| `rev-parse --short <ref>` | Print the short hash a name points to (for example `origin/<branch>`) | "which commit is this name?" |

Placeholders used in `--format`:

| Placeholder | Prints | Mnemonic |
|---|---|---|
| `%H` | full commit hash | **H**ash (big) |
| `%h` | short hash | **h**ash (small) |
| `%an` | author name | **a**uthor **n**ame |
| `%ad` | author date (uses `--date`) | **a**uthor **d**ate |
| `%s` | subject (first line) | **s**ubject |
| `%b` | body (the rest of the message) | **b**ody |
| `%n` | newline | **n**ewline |

Example: `--format="%h %ad %s"` prints `37da891 2026-11-12 WI01124532 ION-12310 green: ...`.

### grep (ripgrep)

The agent's `grep` tool runs ripgrep. The equivalent command line is:

```
rg -n -C 2 "U12" cloud-sdk-api\docs\2026-11-12-sdk-commons-changes-for-apway.md
```

| Flag | Meaning | Remember it as |
|---|---|---|
| `"U12"` | Regex pattern to find | what |
| `-n` | Show line numbers | **n**umbers |
| `-C 2` | Show 2 lines of **C**ontext before and after each match (`-B` = before only, `-A` = after only) | **C**ontext / **B**efore / **A**fter |
| `<path>` | File or folder to search | where |

PowerShell equivalent: `Select-String -Pattern U12 -Context 2,2 <file>`.

### PowerShell helpers used in the pipes

| Piece | Meaning |
|---|---|
| `\|` (pipe) | Pass the output of the left command to the right command |
| `Select-String -NotMatch "Agent host"` | Drop lines that contain the text (like `grep -v`) |
| `Select-Object -First 60` / `-Last 30` | Keep only the first or last N lines (like `head` / `tail`) |
| `2>&1` | Merge errors (stream 2) into normal output (stream 1), so the pipe sees both |
| `Test-Path <dir>` | Prints `True` or `False`: does the path exist? |
| `Get-ChildItem <dir> -Name` | List the names in a folder (like `ls`) |
| `Get-Content` | Print a file (like `cat`) |
| `;` | Run the next command whatever the result (`&&` runs it only on success) |

### mvn

```
mvn -q -o test -pl cloud-sdk-aws -am "-Dtest=ParameterStoreClientFactory*Test" "-Dsurefire.failIfNoSpecifiedTests=false"
 │   │  │   │    │              │    │                                         │
 │   │  │   │    │              │    │                                         └─ don't fail modules with no matching test
 │   │  │   │    │              │    └─ run only test classes matching this pattern
 │   │  │   │    │              └─ also make: build what cloud-sdk-aws depends on
 │   │  │   │    └─ project list: target this module
 │   │  │   └─ lifecycle phase: compile, then run unit tests
 │   │  └─ offline: use ~/.m2 only, no downloads
 │   └─ quiet: errors only
 └─ Maven
```

| Piece | Meaning | Remember it as |
|---|---|---|
| `-q` | Quiet: print errors only | **q**uiet |
| `-o` | Offline: use only `~/.m2`, never download | **o**ffline |
| `test` | Phase: runs `validate → compile → test-compile → test` (surefire unit tests). It does **not** run `package` or `verify`, so no integration tests | stop at unit tests |
| `-pl <module>` | **P**roject **l**ist: build only these modules (comma-separated) | "pick list" |
| `-am` | **A**lso **m**ake: also build the modules that `-pl` depends on (here `cloud-sdk-api`), so the current source is used instead of an old jar in `~/.m2` | "bring my dependencies" |
| `-amd` | Also make dependents: the opposite direction (modules that use this one). Not used here | "bring my users" |
| `-Dtest=Pattern*Test` | Surefire filter: `*` is a wildcard, so it matches `ParameterStoreClientFactoryRetryStrategyTest`. `-D` sets a property | "**D**efine a property" |
| `-Dsurefire.failIfNoSpecifiedTests=false` | With `-am`, `cloud-sdk-api` is built too and has no matching test. Without this flag surefire fails that module with "No tests matching pattern" | "no match is OK" |
| Quotes around `-D...` | PowerShell can split arguments that contain `.` or `=`. Quoting keeps each one whole | PowerShell safety |

How `-pl` and `-am` choose modules:

```
            -pl cloud-sdk-aws  -am
                    │
   cloud-sdk-api ◄──┘ (dependency: built because of -am)
        ▲
   cloud-sdk-aws    (target: built and tested)
        ▲
   commons, ...     (dependents: built only with -amd, so skipped)
```

Where results go: `<module>\target\surefire-reports\<TestClass>.txt` (summary) and `.xml` (details, used by CI).

### Checking SDK behaviour quickly (jshell)

**What is jshell?** jshell is the Java REPL (Read, Evaluate, Print, Loop). It has shipped with every JDK since Java 9. You type or load Java statements and they run at once, with no class, no `main` method, no `pom.xml` and no compile step. Here: `C:\Program Files\Eclipse Adoptium\jdk-17.0.17.10-hotspot\bin\jshell.exe` (jshell 17.0.17).

```
Normal Java:   write class + main → javac → java → read output     (4 steps, needs a project)
jshell:        type a statement   → see the result                (1 step)
```

| Use it for | Example |
|---|---|
| Asking a library "what do you really do?" | `DefaultRetryStrategy.doNotRetry().maxAttempts()` prints `1` |
| Checking an API before writing a test | build an `SsmClient` and inspect `serviceClientConfiguration()` |
| Quick maths and string checks | `Duration.ofSeconds(12).toMillis()` prints `12000` |

Interactive use:

```
> jshell
jshell> 1 + 2
$1 ==> 3
jshell> /exit
```

| jshell command | Does |
|---|---|
| `/exit` | Quit |
| `/imports` | List the active imports |
| `/vars` | List the variables you created |
| `/help` | Help |

Here it ran in **batch mode**: the statements were saved in a `.jsh` file ending with `/exit`, and jshell was given the module's jars so that AWS SDK classes could be imported.

| Piece | Meaning | Remember it as |
|---|---|---|
| `dependency:build-classpath` | maven-dependency-plugin goal: print every jar the module needs | "give me the classpath" |
| `-Dmdep.outputFile=<file>` | Write the classpath to a file instead of the console | output file |
| `-Dmdep.includeScope=test` | Include test-scope jars as well as compile scope | widest scope |
| `jshell` | Interactive Java (JDK 9+). Runs Java snippets without a project or `main` method | Java REPL |
| `--class-path <jars>` | Jars to load, separated by `;` on Windows. Only `.jar` files: native `.dll`/`.so` entries are rejected as "Invalid '--class-path' argument" | where classes come from |
| `<script>.jsh` ending in `/exit` | Run the snippets in the file, then quit | batch mode |

### Git Bash equivalents

Everything above ran in PowerShell. The same steps in **Git Bash** (`C:\Program Files\Git\bin\bash.exe`) are below; all of them were run on 2026-11-16 and gave the same results.

> Watch out: a plain `bash` typed in PowerShell or CMD may start **WSL** (`C:\WINDOWS\system32\bash.exe`), not Git Bash. Use the "Git Bash" shortcut or the full path.

**`git` and `mvn` commands are identical** in both shells. Only the helpers around them change:

| Task | PowerShell | Git Bash |
|---|---|---|
| Drop matching lines | `\| Select-String -NotMatch "Agent host"` | `\| grep -v "Agent host"` |
| Keep matching lines | `\| Select-String "U12"` | `\| grep "U12"` |
| First N lines | `\| Select-Object -First 60` | `\| head -n 60` |
| Last N lines | `\| Select-Object -Last 30` | `\| tail -n 30` |
| List a folder | `Get-ChildItem cloud-sdk-api\docs -Name` | `ls cloud-sdk-api/docs` |
| Does a folder or file exist? | `Test-Path cloud-sdk-api\docs` | `test -d cloud-sdk-api/docs` (folder), `test -f <file>` (file) |
| Print a file | `Get-Content <file>` | `cat <file>` |
| Read an env var | `$env:AWS_RETRY_MODE` | `$AWS_RETRY_MODE` |
| Temp folder | `$env:TEMP` | `$TEMP` |
| Path separator | `\` | `/` (`C:\Users` is `/c/Users`) |
| Home folder | `~` or `$HOME` | `~` |
| Run next whatever the result | `;` | `;` |
| Run next only on success | `&&` (native commands only) | `&&` |

The review commands in Git Bash:

```bash
cd /c/Users/arijit.kundu/projects/mercury-services-commons

# Which branch, and where are the red/green commits?
git --no-pager branch --show-current
git --no-pager log --format="%h %ad %s" --date=short \
    feature/ION-12310-commons-cloudsdk-refactoring -25 --no-merges | grep -v "Agent host"

# What is inside each commit?
git --no-pager show 0ad8576 --stat --format="%H%n%an %ad%n%s%n%b"
git --no-pager show 0ad8576 --format=""
git --no-pager show 37da891 --format=""
git --no-pager show 8129389 --format="" -- '*BaseAwsConfig.java' | head -n 60

# Why? (design doc)
grep -n -C 2 "U12" cloud-sdk-api/docs/2026-11-12-sdk-commons-changes-for-apway.md

# Prove it: run only these tests, then read the results
mvn -q -o test -pl cloud-sdk-aws -am \
    -Dtest='ParameterStoreClientFactory*Test' -Dsurefire.failIfNoSpecifiedTests=false 2>&1 | tail -n 30
cat cloud-sdk-aws/target/surefire-reports/*ParameterStoreClientFactory*.txt | grep "Tests run"

# Is the retry mode overridden?
echo "AWS_RETRY_MODE=[${AWS_RETRY_MODE:-}]"
grep -E "retry_mode|max_attempts" ~/.aws/config || echo "no override in ~/.aws/config"
```

Bash syntax used above:

| Piece | Meaning |
|---|---|
| `\` at end of line | Continue the command on the next line (PowerShell uses a backtick `` ` ``) |
| `'...'` | Single quotes: no expansion. Stops bash expanding `*` in `-Dtest='...*Test'` or `'*BaseAwsConfig.java'` against local files |
| `"..."` | Double quotes: `$VAR` is expanded, spaces are kept |
| `${VAR:-}` | The value of `VAR`, or empty if it is not set (avoids errors) |
| `a \|\| b` | Run `b` only if `a` failed (here: grep found nothing) |
| `grep -E` | Extended regex, so `a\|b` means "a or b" |
| `2>&1` | Same as PowerShell: merge errors into normal output |

The jshell check in Git Bash:

```bash
mvn -q -o dependency:build-classpath -pl cloud-sdk-aws -am \
    -Dmdep.outputFile="$TEMP/cp.txt" -Dmdep.includeScope=test

# Keep only the .jar entries; java on Windows still wants ';' between them
CP=$(tr ';' '\n' < "$TEMP/cp.txt" | grep '\.jar$' | paste -sd ';')

cat > "$TEMP/r.jsh" <<'EOF'
import software.amazon.awssdk.retries.DefaultRetryStrategy;
import software.amazon.awssdk.core.retry.RetryMode;
System.out.println("defaultRetryMode=" + RetryMode.defaultRetryMode());
System.out.println("doNotRetry=" + DefaultRetryStrategy.doNotRetry().maxAttempts());
System.out.println("standard(2)=" + DefaultRetryStrategy.standardStrategyBuilder().maxAttempts(2).build().maxAttempts());
/exit
EOF

jshell --class-path "$CP" "$(cygpath -w "$TEMP/r.jsh")"
rm -f "$TEMP/cp.txt" "$TEMP/r.jsh"
```

| Piece | Meaning | Remember it as |
|---|---|---|
| `$( ... )` | Command substitution: run the command and use its output as a value | "capture output" |
| `tr ';' '\n'` | **Tr**anslate characters: put each classpath entry on its own line | split |
| `< file` | Read input from a file | feed in |
| `grep '\.jar$'` | Keep lines ending in `.jar` (`\.` is a literal dot, `$` is end of line). This drops the native `.dll`/`.so` entries that jshell rejects | jars only |
| `paste -sd ';'` | Join all lines into one, separated by `;` | glue back |
| `cat > file <<'EOF' ... EOF` | Heredoc: write the following lines to a file. Quoting `'EOF'` stops `$` expansion inside | inline file |
| `cygpath -w <path>` | Convert a Git Bash path (`/tmp/r.jsh`) to a Windows path (`C:\...\r.jsh`) for Windows programs like jshell | "to Windows path" |
| `;` inside `--class-path` | `jshell.exe` is a Windows program, so it uses the Windows separator `;`, even in Git Bash (not Linux's `:`) | Windows rules for Windows tools |

Split, filter, glue:

```
cp.txt:  a.jar;b.dll;c.jar
   tr        → a.jar \n b.dll \n c.jar
   grep .jar → a.jar \n c.jar
   paste     → a.jar;c.jar   → $CP
```

## Review notes

- **Later edit to the same lambda (U11, `58f6a52`):** `apiCallTimeout` is now set only when `noClientExecutionTimeout()` was not called. The U12 retry block is unchanged.
- **R7, inconsistent defaults:** with no `retryStrategy(..)`, S3/SQS/SNS get the commons STANDARD default (3 attempts), while SES/SSM keep the SDK default (LEGACY, 4 attempts). This is intentional for 1.0.39 (no behaviour change for unconfigured clients). A follow-up should pick one documented default and use `isRetryStrategyConfigured()` in every factory.
- **N4, reflection:** the test reads the private `ssmClient` field. Renaming it fails with `NoSuchFieldException` instead of an assertion message.
- **N6, environment dependency:** if `AWS_RETRY_MODE` or the AWS profile sets a retry mode, the 4-attempt check is skipped and only the comparison with the reference client runs. This is intended.
