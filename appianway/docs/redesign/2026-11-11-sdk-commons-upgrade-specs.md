# mercury-services-commons: upstream changes U1–U14 for AppianWay (WI01124532), functional and technical specification

> **Date:** 2026-11-11 · **Work item:** WI01124532 (AWS SDK Upgrade, AppianWay)

**Target repository:** `mercury-services-commons` (local checkout `C:\Users\arijit.kundu\projects\mercury-services-commons`, branch `feature/ION-12310-commons-cloudsdk-refactoring`, head `c353706`). Work continues **on this branch**, and the first commit bumps the version from `1.0.38-SNAPSHOT` to **`1.0.39-SNAPSHOT`** (§5, decision 1).

**Revision 2026-11-12:** §5 decisions recorded. First-release scope fixed (§1). mercury-services impact check done (new §4, replacing the PR grouping). U3, U5, U13 and U14 updated to match. Appendix B rewritten. New §7: investigation findings (F-1..F-27, including booking) and the full command log (C-01..C-86).

**Revision 2026-11-12 (b):** **U12 added to 1.0.39** (§5, decision 8), implemented right after U9 as priority 3a. Its impact check (§4.5) found no SSM caller that sets a retry strategy. New last step: the **`README.md` release note for 1.0.39-SNAPSHOT** (§2.4, §5 decision 9). §1, §3 (U12 moved after U9), §4, §6, Appendix A and Appendix B updated.

**Status 2026-11-17 (reviewed from AppianWay):** the whole 1.0.39 scope is **implemented** on the commons branch: version bump, §2.3 flag, U3, U8, U9, U12, U2, U5, U13, U11, U14, README note. 22 commits `91cde62` … `aa52175`, 2695 tests green, pushed (commons PR #29, Bitbucket), installed in the local `~/.m2` only. APIs spot-checked in the source. Not yet deployed to the shared Maven repository (AppianWay progress doc A26). U10, U6, U7, U4, U1 stay for a later release. The §6 checklist is now the 1d plan (progress doc §R.0000).

Progress log for the commons agent: `C:\Users\arijit.kundu\projects\mercury-services-commons\cloud-sdk-api\docs\2026-11-12-sdk-commons-changes-for-apway.md`.

> **Modules touched:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons`, root `pom.xml`
> **Audience:** a Claude agent working in the commons workspace, and the commons reviewer. Each item is written to stand on its own. All file:line references were checked against `c353706` on 2026-11-11.

 **Sources:** `docs/redesign/2026-10-30-apway-WI01124532-review-summary.md` §1 (U1–U10), 
`docs/redesign/2026-10-31-apway-aws-upgrade-dev-progress.md` (A1–A3, A22, D13, D16, R.4; moved 2026-11-19 to `docs/tracker/`: actions.md, closed-items.md, decisions.md, cloud-sdk-facts.md), 
`docs/redesign/2026-10-30-apway-WI01124532-shared.md` (open issues 2–5, 11, 13, 14), and the module pages for transformer and email-sender.
> Local working document (`docs/` is gitignored). Do not commit it.

---

## 0. Correction to the list: U10 is not the last item

The full list is now **U1–U15** (U15 added 2026-11-19):

| Id | Origin | Short name |
|---|---|---|
| U1–U10 | Review summary §1 (2026-10-30) | As before |
| **U11** | A22 / D13 (2026-10-31) | Factories can express "no API-call timeout" |
| **U12** | A22 / R.4 (2026-10-31) | `ParameterStoreClientFactory` honours the configured `RetryStrategy` |
| **U13** | A22 / review summary §3 (2026-10-30) | `S3StorageClient` stops logging the AWS access key id (and stops resolving credentials when it is built) |
| **U14** | New, this review (2026-11-11) | `S3StorageClient.getObject` makes one GET, with no extra HEAD |
| **U15** | AppianWay finding F21, dispatcher pre-review (2026-11-19); added by Arijit's decision, low priority | A missing key is not logged at ERROR with a stack trace |

Update the progress doc A1/A3/A22 and the review summary table when this spec is agreed.

---

## 1. Summary: classification and priority order

**Must have** = no fallback, or the fallback breaks a promise in the published design. These must be in a released commons version before the AppianWay release.
**Optional (recommended)** = a fallback exists, but it is costly, adds risk, or leaves an AWS SDK type or a security issue in AppianWay. Do these now: each one is small and removes code from step 1d.
**Optional** = a working fallback is already in place or planned. Nice to have. Can go in a later commons release.

Priority order is the order to implement in. It puts the 1d dependencies first (workspace S3 adapter, health checks, client profile), then the step 2 and 3 modules (email-sender, transformer), then housekeeping.

| Priority | Id | Class | Change (one line) | Module(s) | AppianWay consumer / step | Fallback today |
|---|---|---|---|---|---|---|
| 1 | **U3** | **Must** | `StorageClient.getObjectSize(bucket, key)`: content length by HEAD, no download | api + aws | `shared` workspace `getFileSize` (1d), splitter (3) | None that avoids a download (A2) |
| 2 | **U8** | **Must** | `EmailService.sendEmailWithResult(...)` returns `EmailSendResult` with the SES message id | api + aws | email-sender `CLOSE` event (2) | None |
| 3 | **U9** | **Must** | `EmailClientFactory` applies an explicitly configured `RetryStrategy` | aws | email-sender zero retries (2) | None |
| 3a | U12 | Optional (in 1.0.39, decision 8) | `ParameterStoreClientFactory` applies an explicitly configured `RetryStrategy` | aws | `shared` `${awsps:}` lookup, watermill-publisher SSM (4) | SDK default retries |
| 4 | U2 | Optional (recommended) | `putObject` accepts zero-length content (byte[], stream, String) | aws | `shared` workspace adapter (1d): dispatcher zip entries, splitter, transformer | Empty temp file through the `File` overload |
| 5 | U5 | Optional (recommended) | `ReceiveMessageOptions` sends `VisibilityTimeout` only when explicitly set | api + aws | `shared` `InboundSqsHealthCheck` (1d) | Probe with `getQueueAttributes` (different check, needs `sqs:GetQueueAttributes` on every role, A8) |
| 6 | U13 | Optional (recommended) | No access-key-id log, no credential resolution in the `S3StorageClient(S3Client)` constructor | aws | Every service (security) | Logger `com.inttra.mercury.cloudsdk` at WARN (A22) |
| 7 | U11 | Optional (recommended) | `noClientExecutionTimeout()` on the base config; factories then set no API-call timeout | aws | `shared` client profile (1d): S3, SQS listener | 10-minute S3 / 60 s listener caps (D13, A23) |
| 8 | U14 | Optional (recommended) | `getObject` builds the result from the GET response, with no extra HEAD | aws | `shared` workspace `read` (1d), every workspace read | None (one extra round trip per read) |
| 9 | U10 | Optional | Version conflict on `save` mapped to a `cloud-sdk-api` exception (opt-in) | api + aws | transformer `ControlNumberSequenceProvider` (3) | Catch SDK `ConditionalCheckFailedException` (allowed SDK type) |
| 10 | U6 | Optional | Consistent full-table scan on `DatabaseRepository` | api + aws | transformer DAO "more than one item" guard (3) | `findById(SequenceId, true)` with no guard |
| 12 | U7 | Optional | Base config takes a `MetricPublisher`; every factory attaches it | aws | transformer SDK CloudWatch metrics (3) | `shared` helper builds SDK clients itself and wraps them |
| 13 | U4 | Optional | Importable `mercury-services-commons-bom` | new pom module | AppianWay root pom | Copied pins plus `PlatformLibraryVersionsTest` |
| 14 | U1 | Optional | Commons `run (yaml) (properties...)` config command | commons | `shared` `ConfigProcessingServerCommand` | Already merged in 1b (`shared` fallback) |
| 15 | U15 | Optional (low) | A missing key is logged at DEBUG, not at ERROR with a stack trace (the exception is still thrown) | aws | `shared` `StorageReadHealthCheck` (every service with a storage-read health check) | None: one ERROR line with a stack trace per health-check run |

**First commons release (1.0.39), decided 2026-11-12 (§5, decisions 2 and 8):** the §2.3 flag, then **U3, U8, U9, U12, U2, U5, U13 (steps 1 and 2), U11, U14**, in that order, and last the `README.md` release note (§2.4).

- U3 **without** the optional `getObjectProperties` method.
- U12 goes straight after U9: it is the same few lines on top of the §2.3 flag, for SSM instead of SES.
- U2, U5, U12, U13 step 2 and U14 are in scope because the mercury-services impact check (§4) found no caller impact and no API break. U5 uses the new builder name `requestVisibilityTimeoutSeconds(..)`. U14 needs one existing commons unit test updated (§4.4).
- Every item is a small, local change in `cloud-sdk-api` / `cloud-sdk-aws`.

**Later (not in 1.0.39):** U10, U6, U7, U4, U1.
**AppianWay 1d waits for this commons release** (§5, decision 7).

---

## 2. Rules for every change (read first)

These rules apply to all items. Each item section only adds to them.

### 2.1 Strictly additive. No behaviour change for existing callers

mercury-services (about 200 entity classes and many services) and AppianWay both consume these artifacts.

1. **Never change an existing method's signature or return type.** That includes `void` → non-void: it breaks binary compatibility (`NoSuchMethodError` in jars compiled against the old version) and breaks every class that implements the interface.
2. **New interface methods are `default` methods.** Test fakes in mercury-services and in AppianWay `functional-testing` implement `StorageClient`, `MessagingClient`, `EmailService` and `DatabaseRepository`, and they must keep compiling. The default either delegates to existing methods (when that is semantically correct), or throws `UnsupportedOperationException("<method> is not supported by this <Interface> implementation")`. The second form is the existing convention: see `MessagingClient.sendMessage(String, T, SendMessageOptions)` at `cloud-sdk-api/.../messaging/api/MessagingClient.java:57-59`.
3. **New configuration switches default to today's behaviour.** A config built without calling the new builder method must produce a byte-identical SDK client and identical requests.
4. **Do not change existing log levels or messages**, except the U13 lines.
5. **No new third-party dependencies.** Everything below uses the AWS SDK 2.x modules already on the `cloud-sdk-aws` classpath (`sdk-core`, `metrics-spi`, `retries-spi`, `s3`, `sqs`, `sesv2`, `ssm`, `dynamodb-enhanced`). U7 uses only the `MetricPublisher` SPI interface. It does **not** add `cloudwatch-metric-publisher` to commons.

### 2.2 Process

| Rule | Detail |
|---|---|
| Branch | Commit directly on `feature/ION-12310-commons-cloudsdk-refactoring`. No sub-branches, no PR per group. A backup was taken before work started (§5, row 1). Do not push without asking |
| Progress log | Keep `cloud-sdk-api/docs/2026-11-12-sdk-commons-changes-for-apway.md` up to date after every commit: item status, classes/methods/tests added or changed, commit ids, build results, deviations and open questions. `docs/` is gitignored in commons, so it is never committed |
| Commit messages | First line starts with **`WI01124532 ION-12310`**: the work item code (Bitbucket hook convention, as in AppianWay) **and** the Jira key `ION-12310`, as in the last commons commit `c353706` (`WI01124532-xray-cve-fixes ION-12310 commons 1.0.38-SNAPSHOT: Xray CVE fixes`). Format: `WI01124532 ION-12310 <phase>: <summary>`, for example `WI01124532 ION-12310 red: getObjectSize must use a single HEAD` |
| TDD | One commit per phase: red (failing test, `WI01124532 ION-12310 red: …`), then green (`WI01124532 ION-12310 green: …`), then refactor (`WI01124532 ION-12310 refactor: …`, only when there is something to clean up) |
| Tests | JUnit 5 (Jupiter) + AssertJ + Mockito, one test class per unit, in the existing package next to the existing test classes. Follow `S3StorageClientMetadataTest` (Mockito `S3Client` mock, `@Nested` groups) and `EmailClientFactoryTest` / `MessagingClientFactoryTest` (inspect the built client) |
| Inspecting built SDK clients | `client.serviceClientConfiguration().overrideConfiguration()` gives `retryStrategy()`, `apiCallTimeout()`, `metricPublishers()` (SDK 2.x ≥ 2.20). Use it to assert factory output without network calls |
| Build | `mvn clean verify` from the commons root, with the full test suite green. Existing tests must pass unchanged. If an existing test has to change, the change is not additive: stop and flag it |
| Version | First commit: `dependency.version` in the root `pom.xml` (line 20, the only place it is declared) `1.0.38-SNAPSHOT` → `1.0.39-SNAPSHOT`, message `WI01124532 ION-12310 build: commons 1.0.39-SNAPSHOT`. `mvn clean verify` must be green on that commit alone |
| Javadoc | Each new public method or switch gets Javadoc stating the default and what the switch changes |
| Release note | Last commit: a `### Commons v1.0.39-SNAPSHOT` section at the end of the root `README.md` (§2.4), message `WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT`. The root `README.md` is tracked, so it is committed (unlike `docs/`) |

### 2.3 Shared building block used by U9, U11, U12 (implement once, first)

**In one sentence.** U9 and U12 need to know whether the caller **explicitly** set a retry strategy, and `BaseAwsConfig` loses that information in its constructor. This section adds a flag that keeps it.

#### 2.3.1 Current behaviour

**(a) The builder stores whatever the caller passes.** The field is null if the caller never calls `retryStrategy(..)` (`BaseAwsConfig.java:88-91`):

```java
public B retryStrategy(RetryStrategy strategy) {
    this.retryStrategy = strategy;
    return builder();
}
```

**(b) The constructor replaces null with a commons default** (`BaseAwsConfig.java:39`). After this line, nothing can tell "caller set it" apart from "defaulted":

```java
this.retryStrategy = builder.retryStrategy != null
        ? builder.retryStrategy
        : DefaultRetryStrategy.standardStrategyBuilder().build();   // getRetryStrategy() is never null afterwards
```

**(c) The factories treat the value differently.**

S3 and SQS always apply it. Their `== null` branches are dead code because of (b) (`S3ClientFactory.java:86-97`, `MessagingClientFactory.java:142-147`):

```java
if (config.getRetryStrategy() == null) { ... }        // never true
return ClientOverrideConfiguration.builder()
    .retryStrategy(config.getRetryStrategy())          // caller's strategy, or the commons default
    .apiCallTimeout(config.getClientExecutionTimeout())
    .build();
```

SES and SSM ignore it. `AwsSesEmailConfig` and `AwsParameterStoreConfig` both extend `BaseAwsConfig`, so a caller can call `.retryStrategy(..)`, but the factory never reads the value (`EmailClientFactory.java:147-152`, `ParameterStoreClientFactory.java:31-32`):

```java
builder.overrideConfiguration(o -> {
    if (config.getClientExecutionTimeout() != null) {
        o.apiCallTimeout(config.getClientExecutionTimeout());
        o.apiCallAttemptTimeout(config.getClientExecutionTimeout());
    }
    // no o.retryStrategy(..), so the AWS SDK picks its own default
});
```

**Result today:**

| Client | Caller called `retryStrategy(x)` | Caller did not |
|---|---|---|
| S3, SQS | `x` | commons default (2.3.3, column B) |
| SES, SSM | **`x` silently ignored**, so the AWS SDK default applies | AWS SDK default (2.3.3, column A) |

#### 2.3.2 Why the obvious fix is wrong

The obvious U9/U12 fix is one line in each factory: `o.retryStrategy(config.getRetryStrategy())`. It fixes email-sender, which passes `doNotRetry()`. But because of (b), it also forces the commons default onto **every SES and SSM client that never asked for one**. Every mercury-services app using SES or SSM would quietly move from column A to column B of 2.3.3 on its next commons upgrade, with no config change and no failing test. That breaks rule 2.1 (additive only). The natural guard `if (config.getRetryStrategy() != null)` doesn't help either: it is always true because of (b).

#### 2.3.3 Commons default vs AWS SDK default: what actually differs

Both rows were verified against the AWS SDK 2.30.24 sources: `retries` `DefaultRetryStrategy`, `LegacyRetryStrategy` and `StandardRetryStrategy`; `retries-spi` backoff classes; `aws-core` `AwsDefaultClientBuilder.configureRetryStrategy` / `resolveAwsRetryStrategy`; `sdk-core` `RetryMode.Resolver`.

**A. What "AWS SDK default" means.** If no strategy is set on a client, `AwsDefaultClientBuilder.resolveAwsRetryStrategy` resolves a *retry mode* in this order:

1. the `aws.retryMode` system property or the `AWS_RETRY_MODE` environment variable;
2. `retry_mode` in the AWS profile;
3. the defaults mode. The SDK default defaults mode is `LEGACY`, whose attribute map is empty, so it contributes nothing.
4. `RetryMode.LEGACY`.

Neither SES v2 nor SSM ships a service-specific retry policy (DynamoDB does: `DynamoDbRetryPolicy`). So on our hosts, unless someone sets `AWS_RETRY_MODE`, the AWS SDK default for SES and SSM is **`AwsRetryStrategy.legacyRetryStrategy()`**.

**B. What "commons default" means.** `DefaultRetryStrategy.standardStrategyBuilder().build()`, which is a **standard** strategy. It is fixed in code, so it ignores `AWS_RETRY_MODE` and the profile.

**Which errors are retried: the same.** When a caller-supplied strategy reaches the client, `configureRetryStrategy` sees `useClientDefaults() == true` (the default) and adds the same AWS and SDK retry conditions that the legacy default has: throttling codes, 5xx, transient I/O, clock skew. The difference is only in *how many times* and *how long between attempts*.

| | A. AWS SDK default (LEGACY) | B. Commons default (STANDARD) |
|---|---|---|
| Max attempts (first try + retries) | **4** (3 retries) | **3** (2 retries) |
| Backoff, ordinary errors (full jitter, base 100 ms) | before retry 1: 0–100 ms, retry 2: 0–200 ms, retry 3: 0–400 ms | retry 1: 0–100 ms, retry 2: 0–200 ms |
| Backoff, throttling errors | **half jitter, base 500 ms**: 250–500 ms, 500–1000 ms, 1–2 s | **full jitter, base 1 s**: 0–1 s, 0–2 s |
| Max single backoff | 20 s | 20 s |
| Retry token bucket (circuit breaker) | 500 tokens, 5 per retry; **throttling retries cost 0** | 500 tokens, 5 per retry, **throttling included** |
| Honours `AWS_RETRY_MODE` / profile `retry_mode` | yes | no (fixed in code) |
| Server `Retry-After` hint | the larger of the hint and the backoff | same |

**What this means in practice:**

- **Throttled SES send (for example, the sending rate is exceeded).** Legacy makes up to 4 attempts with about 1.75–3.5 s of total waiting. Standard makes up to 3 attempts with 0–3 s of waiting. Under standard, a burst of throttling can also drain the token bucket, so retries stop entirely until calls succeed again. Legacy never stops retrying because of throttling.
- **Transient 5xx or a connection reset.** Legacy makes one more attempt than standard. The waits are similar.
- **Operations.** Today an operator can switch SES and SSM to standard or adaptive with `AWS_RETRY_MODE`. After the naive fix, that setting would silently stop working for those clients.

Neither column is wrong. The point is that the naive fix moves existing SES and SSM users from A to B **without anyone asking for it**. Moving them should be a deliberate per-service decision.

#### 2.3.4 The change

Record whether the caller set a strategy **before** (b) fills in the default:

```java
// BaseAwsConfig
private final boolean retryStrategyConfigured;   // true only when retryStrategy(..) was called with a non-null value

protected BaseAwsConfig(BaseAwsConfigBuilder<?, ?> builder, boolean useAsyncClient) {
    ...
    this.retryStrategyConfigured = builder.retryStrategy != null;          // read BEFORE defaulting
    this.retryStrategy = builder.retryStrategy != null
            ? builder.retryStrategy
            : DefaultRetryStrategy.standardStrategyBuilder().build();      // unchanged
}

public boolean isRetryStrategyConfigured() { return retryStrategyConfigured; }
```

`getRetryStrategy()` is unchanged and still never null, so S3, SQS, SNS and DynamoDB keep their current behaviour. U9 (SES) and U12 (SSM) then apply the strategy only when it was asked for:

```java
builder.overrideConfiguration(o -> {
    ...existing timeout code, unchanged...
    if (config.isRetryStrategyConfigured()) {
        o.retryStrategy(config.getRetryStrategy());
    }
    // otherwise set nothing: the AWS SDK default (2.3.3 column A) applies, exactly as today
});
```

**Result after the change:**

| Caller | Before | After |
|---|---|---|
| Existing SES/SSM user, no `retryStrategy(..)` | AWS SDK default (A) | **AWS SDK default (A), unchanged** |
| email-sender: `.retryStrategy(DefaultRetryStrategy.doNotRetry())` | ignored, so up to 4 attempts | **1 attempt** (U9) |
| Any caller: `.retryStrategy(x)` on SES/SSM | ignored | `x` |
| S3, SQS, SNS, DynamoDB users | as before | as before (the flag is not read by these factories) |

**Tests (`BaseAwsConfigTest`, or the nearest existing test class for the base config):**

- the flag is false by default;
- the flag is true after `retryStrategy(x)`;
- the flag is false after `retryStrategy(null)`;
- `getRetryStrategy()` is still non-null in all three cases.

#### 2.3.5 Same pattern for U11 (timeout)

The timeout has the same problem: `BaseAwsConfig.java:36-37` turns a null `clientExecutionTimeout` into 30 s, so "no API-call timeout" cannot be expressed by passing null. U11 adds `noClientExecutionTimeout()` on the builder and a `clientExecutionTimeoutDisabled` flag on the config. Factories skip `apiCallTimeout(..)` when the flag is set. `getClientExecutionTimeout()` still returns 30 s, so existing readers see no change. Details are in U11.

**Why "implement once, first".** U9 and U12 both read `isRetryStrategyConfigured()`, and U11 copies the pattern. So the flag goes in right after the version bump, before U3 and U9. That avoids each item adding its own variant.

### 2.4 `README.md` release note for 1.0.39-SNAPSHOT (last step)

**What.** Append a `### Commons v1.0.39-SNAPSHOT` section at the end of `C:\Users\arijit.kundu\projects\mercury-services-commons\README.md`, after `### Commons v1.0.38-SNAPSHOT` and in the same style: a short lead paragraph, then one numbered entry per change. Do not change the `Latest release version` line at the top or any earlier section.

**When.** One commit after U14 is green, once every item is done: `WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT`. Stage only `README.md`.

**How to write it.**
- One to three sentences per entry, and the class and method names as they are in the code.
- Say what is new and what default applies. Leave out internals, test names, file:line references and AppianWay detail.
- Separate the two changes that existing callers can notice (U2, U13 step 2) from the rest, so that a reader can see them without reading everything.
- If an item was dropped or changed during implementation, the note describes the code, not this spec. Record the difference in the progress log.

**Draft** (check each line against the final code before committing):

```markdown
### Commons v1.0.39-SNAPSHOT

cloud-sdk additions for the AWS SDK 2.x upgrade of AppianWay (WI01124532). The API changes are additive:
new methods are interface default methods, and new switches are off by default. No dependency versions change.

New:

1. **`StorageClient.getObjectSize(bucket, key)`** returns an object's size in bytes from one S3 HEAD,
without downloading the body. Errors are the same as `getMetadata`.

2. **`EmailService.sendEmailWithResult(...)`** sends exactly like `sendEmail` and returns an
`EmailSendResult` holding the SES message id.

3. **SES and SSM clients now apply `retryStrategy(..)` when the caller sets it.** `EmailClientFactory` and
`ParameterStoreClientFactory` used to ignore it. A client built without one keeps the AWS SDK default
retries, as before. `BaseAwsConfig.isRetryStrategyConfigured()` tells the two cases apart.

4. **`ReceiveMessageOptions.Builder.requestVisibilityTimeoutSeconds(int)`** (0..43200) sends
`VisibilityTimeout` on the receive request. The existing `visibilityTimeoutSeconds(int)` is unchanged: its
value is stored but still not sent.

5. **`noClientExecutionTimeout()`** on the AWS config builders. The S3, SQS, SNS, SSM and DynamoDB factories
then set no API-call timeout, and calls stay bounded by the HTTP client's socket timeout.
`getClientExecutionTimeout()` still returns the 30 s default.

6. **`S3StorageClient.getObject` makes one GET** instead of a GET plus a HEAD. Size, eTag and last-modified
come from the GET response.

7. **The AWS access key id is no longer logged.** `S3StorageClient` no longer resolves credentials when it is
built. The presigner resolves them when a URL is signed.

Changes that existing callers may notice:

8. **Zero-length S3 writes are allowed.** `putObject` with empty `byte[]`, a 0-length stream, or an empty or
blank `String` now writes an empty object. Before, it threw `IllegalArgumentException`. `null` content is
still rejected.

9. **Presigned URLs from `StorageClientFactory.createS3Client(config)` are signed with the config's region
and credentials provider.** Before, they always used us-east-1 and the default credentials chain, so URLs for
buckets in other regions were signed for the wrong region. `createDefaultS3Client()` is unchanged.
```

---

## 3. Item specifications (in priority order)

### U3. Size-only HEAD: `StorageClient.getObjectSize` (MUST, priority 1)

**Functional need.** AppianWay `shared` `WorkspaceService.getFileSize(bucket, key)` returns an object's size. Today it is one S3 HEAD (`S3WorkspaceService.java:128-138`, v1 `getObjectMetadata(...).getContentLength()`). The splitter calls it for every split file. The published design (program NFR 4, `shared` NFR 3) promises "HEAD, no download". Today commons has no size-only call: `getMetadata` returns only user metadata, and `getObject` downloads the whole body into memory (and then sends a HEAD as well; see U14). This item is a release prerequisite (review summary §9 tracker 1, action A1), and it also closes A2, the open interim-approach question for 1d.

**Current code.**
- `cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/storage/api/StorageClient.java`: no size method.
- `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClient.java:722-747` `getMetadata`. This is already a HEAD, and its error handling is the pattern to copy.

**Technical change.**

1. `StorageClient` (api), new default method:
   ```java
   /**
    * Returns the object's size in bytes (Content-Length) without transferring the body where the implementation
    * supports it (S3: HeadObject). The default implementation downloads the object; implementations should override.
    * @throws IllegalArgumentException if bucketName or key is null/blank
    * @throws RuntimeException implementation-specific, the same types as getMetadata(bucket, key), including a missing key
    */
   default long getObjectSize(String bucketName, String key) {
       StorageObject object = getObject(bucketName, key);
       return object == null ? 0L : object.getSize();
   }
   ```
2. `S3StorageClient` (aws) overrides it:
   - `validateBucketName(bucketName); validateKey(key);`
   - `HeadObjectResponse r = s3Client.headObject(HeadObjectRequest.builder().bucket(bucketName).key(key).build());`
   - return `r.contentLength() == null ? 0L : r.contentLength()` (v1 returned 0 when no length was present).
   - Error handling identical to `getMetadata` (lines 735-746): `NoSuchKeyException` → `handleNoSuchKeyException`, `S3Exception` → `handleS3Exception`, `SdkClientException` → `handleSdkException`, other → `handleUnexpectedException`. Also map an `S3Exception` with `statusCode() == 404` the same way as `NoSuchKeyException`: HEAD responses have no body, so S3 often returns a bare 404 rather than `NoSuchKey` (see the comment in `objectExists`, line 919).
   - Log at DEBUG (not INFO) `size retrieved bucket='{}', key='{}', size={}`.
3. **Out of scope (decision 2, 2026-11-12):** do **not** add a `getObjectProperties(bucket, key)` method returning a `StorageObject`. Only `getObjectSize` is added.

**Behaviour / compatibility.** New method only. No existing call path changes.

**Tests.** New `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientObjectSizeTest.java`:
- returns `contentLength` from a mocked `headObject`. Verify exactly one `headObject` call and **no** `getObject` / `getObjectAsBytes` call (`verify(s3, never())…`).
- zero-length object → `0`.
- `contentLength` null → `0`.
- `NoSuchKeyException` → same exception type and message as `getMetadata` for a missing key.
- bare `S3Exception` 404 → same as the missing-key case.
- other `S3Exception` (403) → `handleS3Exception` type.
- `SdkClientException` → `handleSdkException` type.
- null/blank bucket or key → `IllegalArgumentException`, no SDK call.

In `cloud-sdk-api`: a small test that the default method delegates to `getObject(...).getSize()` (anonymous or stub `StorageClient`).

**Acceptance.** Size comes from one HEAD. Nothing is downloaded. Error types are the same as `getMetadata`.

**AppianWay follow-up (not for the commons agent).** The 1d workspace adapter's `getFileSize` calls `storageClient.getObjectSize`, and cloud-sdk failures map to `RecoverableException` (C9). The A2 interim fallback is no longer needed.

---

### U8. SES message id: `EmailService.sendEmailWithResult` (MUST, priority 2)

**Functional need.** email-sender today returns the SES `MessageId` from `MailingService`, and `EmailSenderTask` puts it on the `CLOSE` event as `messageId`. A null id writes `messageDropped=true` instead. Commons `EmailService.sendEmail` returns `void`. `SesEmailServiceImpl` receives the `SendEmailResponse` and discards it after a debug log. Without U8, every email would be reported as dropped. There is no fallback, because a module-local SES client is not allowed (AWS SDK boundary rule, `shared` OI 14).

**Current code.**
- `cloud-sdk-api/.../email/api/EmailService.java:25` `void sendEmail(String from, List<String> to, MailContent content)`, and `:40` `void sendEmail(String from, List<String> to, List<String> cc, List<String> bcc, MailContent content)`.
- `cloud-sdk-api/.../email/model/EmailSendResult.java`: `@Value @Builder` with `messageId`, `emailAddress`, `exception`, `emailRequest`. It already exists and is already used by `sendTemplateEmail`.
- `cloud-sdk-aws/.../email/impl/SesEmailServiceImpl.java:118-151` `sendEmail(from, to, cc, bcc, content)`. At line 140 `SendEmailResponse response = sesClient.sendEmail(...)` and at line 141 `logDebugMessage(to, response)`. The response is never returned.

**Technical change.**

1. `EmailService` (api), two new default methods:
   ```java
   /**
    * Same as sendEmail(from, to, cc, bcc, content) but returns the provider's result.
    * @return result whose messageId is the provider message id (SES MessageId); emailAddress = recipients joined with ","
    * @throws SendEmailException / IllegalArgumentException exactly as sendEmail
    */
   default EmailSendResult sendEmailWithResult(String from, List<String> to, List<String> cc, List<String> bcc, MailContent content) {
       throw new UnsupportedOperationException("sendEmailWithResult is not supported by this EmailService implementation");
   }

   default EmailSendResult sendEmailWithResult(String from, List<String> to, MailContent content) {
       return sendEmailWithResult(from, to, null, null, content);
   }
   ```
   The default must **not** delegate to the `void` method and return a null id. email-sender would then silently report every email as dropped. Failing loudly is the right behaviour for a fake that has not implemented it.
2. `SesEmailServiceImpl` (aws):
   - Move the body of `sendEmail(from, to, cc, bcc, content)` (validation, simple/raw content choice, reply-to rule X-G7, `sesClient.sendEmail`, the three catch blocks) into `sendEmailWithResult(from, to, cc, bcc, content)`. It returns `EmailSendResult.builder().messageId(response.messageId()).emailAddress(String.join(",", to)).build()`.
   - The existing `void sendEmail(from, to, cc, bcc, content)` becomes `sendEmailWithResult(from, to, cc, bcc, content);`, discarding the result. `void sendEmail(from, to, content)` is unchanged (it delegates to the 5-argument form).
   - Exception types, messages and log lines stay the same, so the `void` path behaves exactly as before.
   - `sendTemplatedEmail` and `sendTemplateEmail` are unchanged.

**Behaviour / compatibility.** Existing `sendEmail` callers see the same requests, the same exceptions and the same logs.

**Tests.** Extend `SesEmailServiceImplTest` or add `SesEmailServiceImplSendWithResultTest`:
- mocked `SesV2Client.sendEmail` returns `messageId("abc")` → result `messageId == "abc"`, `emailAddress == "a@x,b@y"`.
- the request sent is identical to the one `sendEmail` sends (capture both with `ArgumentCaptor` and compare): From, To/Cc/Bcc, subject, text body, reply-to on the simple path, raw MIME on the attachment path.
- `SdkClientException` / `SdkServiceException` / other exception → `SendEmailException` with the same messages as `sendEmail`.
- invalid input → `IllegalArgumentException` before any SDK call.
- `void sendEmail` still calls the SDK exactly once.

In `cloud-sdk-api`: the default 5-argument method throws `UnsupportedOperationException`, and the 3-argument default delegates to the 5-argument one with null cc/bcc.

**Acceptance.** `sendEmailWithResult` returns the SES message id. `sendEmail` behaves exactly as before.

**AppianWay follow-up.** email-sender `MailingService` calls `sendEmailWithResult(from, List.of(to), content)` and returns `result.getMessageId()`. The AppianWay `EmailService` fake in `functional-testing` implements it.

---

### U9. SES retry strategy: `EmailClientFactory` honours a configured `RetryStrategy` (MUST, priority 3)

**Functional need.** email-sender sends with **zero retries** today (v1 `withMaxErrorRetry(0)`), so that a timeout after SES accepted the email does not send a duplicate. `EmailClientFactory` ignores `BaseAwsConfig.retryStrategy`, so the SES client always uses the SDK's default retry behaviour (several attempts). The region is already taken from the config through `createSesClient(config)` (AppianWay passes the environment's region). No region change is needed: the "and region" in the program page's U9 text is already satisfied by `createSesClient(config)`.

**Current code.** `cloud-sdk-aws/.../email/factory/EmailClientFactory.java:136-155` `createSesV2Client`: the `overrideConfiguration` lambda sets only `apiCallTimeout` / `apiCallAttemptTimeout` from `AwsSesEmailConfig.getClientExecutionTimeout()` (default 10 s). It sets no `retryStrategy`.

**Technical change.**
1. §2.3 flag `BaseAwsConfig.isRetryStrategyConfigured()`.
2. In `createSesV2Client`'s `overrideConfiguration` lambda add:
   ```java
   if (config.isRetryStrategyConfigured()) {
       overrideBuilder.retryStrategy(config.getRetryStrategy());
   }
   ```
3. Javadoc on `createSesClient(AwsSesEmailConfig)`: "The configured `RetryStrategy` is applied when set on the builder; otherwise the SDK default applies (unchanged)." Example for no retries: `AwsSesEmailConfig.builder()…retryStrategy(DefaultRetryStrategy.doNotRetry())`.

**Behaviour / compatibility.** No change unless the caller sets `retryStrategy(..)`. `createDefaultSesClient()` is unchanged.

**Tests.** Extend `EmailClientFactoryTest` or add `EmailClientFactoryRetryStrategyTest`:
- config with `retryStrategy(DefaultRetryStrategy.doNotRetry())` → the built client's `overrideConfiguration().retryStrategy()` is present and `maxAttempts() == 1`. If the impl does not expose the client, use a package-private accessor or reflection consistent with `AllFactoriesBuilderModeTest`.
- config with a custom `standardStrategyBuilder().maxAttempts(2)` → `maxAttempts() == 2`.
- config without `retryStrategy` → `overrideConfiguration().retryStrategy()` is empty (same as today). This is the regression guard.
- `BaseAwsConfig` unit test: `isRetryStrategyConfigured()` is false by default, true after `retryStrategy(x)`, false after `retryStrategy(null)`.

**Acceptance.** A configured strategy reaches the SES client. Unconfigured clients are byte-identical to today.

**AppianWay follow-up.** email-sender's `ExternalServicesModule` builds `AwsSesEmailConfig` with `retryStrategy(DefaultRetryStrategy.doNotRetry())` and the environment region.

---

### U12. `ParameterStoreClientFactory` honours a configured `RetryStrategy` (Optional, in 1.0.39 by decision 8; priority 3a)

**Functional need.** AppianWay resolves `${awsps:...}` at startup through the commons `ParameterStoreLookup`, and watermill-publisher reads SSM at runtime through `CloudParameterStore`. The factory ignores `BaseAwsConfig.retryStrategy`, so callers cannot match their other clients' retry profile (D16). Today SDK defaults apply, which is acceptable, so the item is optional. It is in 1.0.39 because it costs a few lines once the §2.3 flag exists (decision 8).

**Current code.** `cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactory.java:26-38` `createParameterStore(AwsParameterStoreConfig)`: the `overrideConfiguration` lambda sets only `apiCallTimeout(config.getClientExecutionTimeout())`. There is no retry strategy.

**Technical change.**
1. Uses the §2.3 flag (already in place by then).
2. Turn the lambda into a block and add the U9 pattern:
   ```java
   .overrideConfiguration(b -> {
       b.apiCallTimeout(config.getClientExecutionTimeout());   // unchanged here; U11 later makes it conditional
       if (config.isRetryStrategyConfigured()) {
           b.retryStrategy(config.getRetryStrategy());
       }
       // otherwise set nothing: the AWS SDK default applies, exactly as today
   })
   ```
3. Javadoc on `createParameterStore`: "The configured `RetryStrategy` is applied when set on the builder; otherwise the SDK default applies (unchanged)."
4. U11 comes later and edits the same lambda to skip `apiCallTimeout` when `isClientExecutionTimeoutDisabled()`. Do not do that here.

**Behaviour / compatibility.** No change unless the caller sets `retryStrategy(..)`, and no current caller does (§4.5). `ParameterStoreLookup` builds its config with region and credentials only, so it is unchanged.

**Tests.** New `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactoryRetryStrategyTest.java`, using real `AwsParameterStoreConfig` builders (region, a static credentials provider). Read the built `SsmClient` from the `ssmClient` field of `SsmCloudParameterStore` by reflection, as the existing `CloudParameterStoreClientFactoryTest` does. Then inspect `serviceClientConfiguration().overrideConfiguration()`:
- `retryStrategy(DefaultRetryStrategy.doNotRetry())` → `retryStrategy()` present, `maxAttempts() == 1`.
- `standardStrategyBuilder().maxAttempts(2).build()` → `maxAttempts() == 2`.
- no `retryStrategy(..)` → `retryStrategy()` empty. This is the regression guard.
- `apiCallTimeout()` is the configured value in all three cases.

The existing `CloudParameterStoreClientFactoryTest` uses Mockito mocks of the config. `isRetryStrategyConfigured()` returns false on a mock, so the test stays green **unchanged**. If it fails, stop and report (§2.2). `AllFactoriesBuilderModeTest` must stay green unchanged too.

**Acceptance.** A configured strategy reaches the SSM client. Unconfigured clients are identical to today.

**AppianWay follow-up.** `ClientProfile` can pass its retry strategy to SSM (watermill-publisher). Optional.

---

### U2. Allow zero-length S3 writes (Optional, recommended; priority 4)

**Functional need.** SDK v1 wrote empty objects. AppianWay writes them through the workspace adapter: dispatcher zip entries, splitter output, and possibly a Contivo map in transformer that returns an empty target. Commons rejects length 0 on the byte, stream and String paths. The `File` path accepts an empty file, which is the current fallback: one empty temporary file, created at startup, sent through `putObject(bucket, key, File, metadata, contentType)`. The fallback works, but it adds a temp-file lifecycle and a special case to the 1d adapter.

**Current code.**
- `cloud-sdk-aws/.../storage/impl/AbstractStorageObject.java:48-52` `validateContent(byte[])`: `content == null || content.length == 0` → `IllegalArgumentException(CONTENT_VALIDATION_MESSAGE)`.
- `AbstractStorageObject.java:70-94` `validateInputStream(InputStream, long)`: rejects `contentLength == 0` (line 71) and `content.available() <= 0` (line 81). It also reads one byte and resets (lines 84-88), which fails for empty streams and for streams that do not support `mark`.
- `S3StorageClient.java:760-770` `putObject(String bucket, String fileName, String content)`: `content == null || content.isBlank()` (line 767). This rejects empty **and whitespace-only** strings.
- Callers: `S3StorageClient` `putObject` byte (425, 462), stream (502, 605), String (760).

**Technical change.**
1. `validateContent(byte[])`: reject only `null`. Allow `length == 0`. Keep the message constant for null.
2. `validateInputStream(InputStream, long)`:
   - reject `content == null`; reject `contentLength < 0`; keep the `> Integer.MAX_VALUE` check.
   - when `contentLength == 0`: accept, and skip the `available()` / read-one-byte probe.
   - when `contentLength > 0`: keep today's probe unchanged, so existing non-empty behaviour is identical.
3. String `putObject`: reject only `content == null`. Allow `""` and whitespace-only. `RequestBody.fromString("")` sends `Content-Length: 0`.
4. Zero-length uploads use `RequestBody.empty()`, or `RequestBody.fromBytes(new byte[0])` / `fromInputStream(in, 0)`. Verify the SDK sends `Content-Length: 0` with no chunked encoding (a unit test on the captured `RequestBody.optionalContentLength()` is enough).
5. Do **not** change `validateFile`. It already accepts empty files.

**Behaviour / compatibility.** Previously a call with empty content threw `IllegalArgumentException`. Now it writes an empty object. This loosens validation and changes no successful path. Check mercury-services for code that relies on the exception for empty content: run `grep -rn "Content must not be null or empty\|content must not be null or empty"` over mercury-services tests. If any test asserts it, list it in the progress log. The change is still additive in API terms, but it loosens validation, and that was accepted conditionally (decision 3).

**mercury-services check (2026-11-12): no impact, so U2 is in scope** (§4.1). No code or test relies on the empty-content exception. One test expects the opposite: booking `S3WorkspaceServiceTest.putObject_emptyContent` (mocked `StorageClient`) expects an empty-string put to succeed. Against the real commons client, that call throws today and is wrapped in `UnrecoverableAWSException`, so U2 fixes a latent failure there.

**Tests.** Extend `S3StorageClientMetadataTest` or add `S3StorageClientZeroLengthPutTest`:
- byte[0] with and without metadata/contentType → one `putObject`, `contentLength == 0`, metadata and content type passed through.
- empty stream with `contentLength 0` (with and without metadata) → one `putObject`, length 0. Use a non-markable stream (`new ByteArrayInputStream(new byte[0])` wrapped in a `FilterInputStream` that overrides `markSupported()` to return false).
- String `""` and `"  "` → `putObject` with `text/plain; charset=UTF-8` and the exact bytes.
- null byte[] / null stream / null String → `IllegalArgumentException` (unchanged).
- negative length → `IllegalArgumentException` (unchanged).
- non-empty paths: existing tests unchanged and green.

**Acceptance.** Empty objects can be written through every `putObject` overload with the same metadata and content-type handling as non-empty ones.

**AppianWay follow-up.** The workspace adapter drops the empty-temp-file fallback. The `@Disabled` "commons rejects empty" tests, if 1d adds any, are enabled.

---

### U5. Receive visibility timeout only when explicitly set (Optional, recommended; priority 5)

**Functional need.** `shared` `InboundSqsHealthCheck` proves the pickup queue is readable by receiving with **visibility timeout 0**, so a probed message stays visible to the workers. cloud-sdk never sends `VisibilityTimeout` on receive. The builder's default of 30 is stored but unused, so a direct port would hide a real message for the queue's default visibility timeout. The fallback is a different check (`getQueueAttributes`), which needs `sqs:GetQueueAttributes` on every task role (A8, unconfirmed on INT).

**Current code.**
- `cloud-sdk-api/.../messaging/model/ReceiveMessageOptions.java:42`: builder field `private int visibilityTimeoutSeconds = 30;`. The getter `getVisibilityTimeoutSeconds()` is Lombok `@Getter` and returns an `int`.
- `cloud-sdk-aws/.../messaging/aws/impl/SqsMessagingClient.java:264-298` `receiveMessages(ReceiveMessageOptions)`: the request builder sets queue URL, max messages, wait time, message attribute names, and system attribute names. It never sets the visibility timeout. `listMessages` (193) and `receiveMessages(String,int,int)` (238) build their own requests, also without it.

**mercury-services check (2026-11-12): there is an existing caller, so the new builder name is used** (§5, decision 4; details in §4.2). bill-of-lading-v2 `QueueConfig.toReceiveMessageOptions()` calls `.visibilityTimeoutSeconds(visibilityTimeoutSeconds)` with **300** in every environment's `config.yaml` (30 in test resources), and `BillOfLadingInjectorTest` asserts `getVisibilityTimeoutSeconds()` equals the config value. If the old method's value started being sent, any future path that passes those options to `receiveMessages(options)` would silently send `VisibilityTimeout=300`. So the existing method stays **exactly as it is (stored, never sent)**, and a new method carries the "send it" meaning.

**Technical change.**
1. `ReceiveMessageOptions` (api):
   - new field `private final Integer requestedVisibilityTimeoutSeconds;` (null = not requested). Annotate it `@Getter(AccessLevel.NONE)`, so that the class-level Lombok `@Getter` does not generate an `Integer` getter.
   - new builder field `private Integer requestedVisibilityTimeoutSeconds;` and method:
     ```java
     /**
      * Visibility timeout to send on the receive request (SQS VisibilityTimeout), 0..43200 seconds.
      * Not set (the default): no VisibilityTimeout is sent and the queue's default applies, as before.
      * Unlike visibilityTimeoutSeconds(int), which is stored but never sent, this value IS sent.
      * @throws IllegalArgumentException if seconds is outside 0..43200
      */
     public Builder requestVisibilityTimeoutSeconds(int seconds)
     ```
   - new getters `public boolean isVisibilityTimeoutRequested()` and `public OptionalInt getRequestedVisibilityTimeoutSeconds()` (empty when not requested).
   - **unchanged:** `Builder.visibilityTimeoutSeconds(int)` (no new validation, still not sent) and `getVisibilityTimeoutSeconds()` (int, 30 by default). Add one Javadoc sentence to the old builder method: "Stored only; not sent on receive. Use `requestVisibilityTimeoutSeconds(int)` to send a visibility timeout." This is a Javadoc change only, with no code change.
2. `SqsMessagingClient.receiveMessages(ReceiveMessageOptions)` (aws): `options.getRequestedVisibilityTimeoutSeconds().ifPresent(requestBuilder::visibilityTimeout);`
3. Leave `listMessages`, `receiveMessages(String,int,int)` and `SqsListener.createReceiveMessageOptions()` unchanged.

**Behaviour / compatibility.** Requests change only for callers that call the new method, and today there are none. bill-of-lading-v2 and every other caller send byte-identical requests.

**Tests.**
- `ReceiveMessageOptionsTest`:
  - default → `isVisibilityTimeoutRequested() == false`, `getRequestedVisibilityTimeoutSeconds()` empty, `getVisibilityTimeoutSeconds() == 30`.
  - `requestVisibilityTimeoutSeconds(0)` → requested, 0. 43200 → 43200. Values -1 and 43201 → `IllegalArgumentException`.
  - `visibilityTimeoutSeconds(300)` → `getVisibilityTimeoutSeconds() == 300` and `isVisibilityTimeoutRequested() == false`. This is the regression guard for bill-of-lading-v2.
- `SqsMessagingClient` receive test (capture the `ReceiveMessageRequest`):
  - not requested → `visibilityTimeout()` is null;
  - only `visibilityTimeoutSeconds(300)` → `visibilityTimeout()` still null;
  - requested 0 → 0; requested 45 → 45;
  - other fields unchanged.

**Acceptance.** A receive with explicit visibility 0 sends `VisibilityTimeout=0`. All other receives are byte-identical to today.

**AppianWay follow-up.** `InboundSqsHealthCheck` keeps its v1 semantics (receive 1, `requestVisibilityTimeoutSeconds(0)`, wait 0). The `getQueueAttributes` fallback and the A8 IAM item for `GetQueueAttributes` can go.

---

### U13. Stop logging the AWS access key id; no credential resolution in the constructor (Optional, recommended; priority 6)

**Functional need.** `new S3StorageClient(S3Client)`, used by `StorageClientFactory.createS3Client` and so by every service, calls `createPresigner()`. That method resolves the default credential chain eagerly (a network call to the container or instance metadata endpoint on ECS/EC2) and logs **the access key id at INFO**. The AppianWay mitigation is to set the logger `com.inttra.mercury.cloudsdk` to WARN, which also hides useful INFO logs, and the eager resolution remains. An access key id is an identifier, not a secret, but security scanners flag it, and it should not be in application logs.

**Current code.** `cloud-sdk-aws/.../storage/impl/S3StorageClient.java:99-114` `createPresigner()`: lines 103-104 log `Resolved AWS credentials using provider: {}` and `Using Access Key ID: {}`. Also `cloud-sdk-aws/.../paramstore/main/Main.java:77` logs a prefix of the key. That is a `main` utility, not library code. It is in scope for consistency (step 3).

**Technical change.**
1. `createPresigner()`: remove the `resolveCredentials()` call and both INFO lines. Build `S3Presigner` with the provider. The presigner resolves credentials lazily, when a URL is generated, so behaviour for `generatePresignedUrl` is unchanged. Keep at most one DEBUG line: `Creating S3Presigner with provider {}` (provider class name only).
2. **Step 2, in scope (§5, decision 5: latent bug).** Today the presigner always uses `DefaultCredentialsProvider` and `StorageConfigConstants.DEFAULT_REGION` (us-east-1), even when `AwsStorageConfig` names another region or provider. A presigned URL for a bucket outside us-east-1 is then signed for the wrong region.
   - `StorageClientFactory.createS3Client(AwsStorageConfig config)` builds the presigner from the config and uses the **existing** two-argument constructor `S3StorageClient(S3Client, S3Presigner)`. No new constructor is needed:
     ```java
     S3Presigner presigner = S3Presigner.builder()
         .region(config.getRegion().getRegionDelegate())
         .credentialsProvider(config.getCredentialsProvider().getCredentialProviderDelegate())
         .build();
     return new S3StorageClient(s3Client, presigner);
     ```
     (`validateBaseConfig` already guarantees that region and credentials provider are non-null.)
   - `StorageClientFactory.createDefaultS3Client()` and the public `S3StorageClient(S3Client)` constructor are **unchanged**. They keep `createPresigner()` (us-east-1 plus the default chain, cleaned by step 1).
   - Do not pass `endpointOverride` to the presigner in this release. It is not in the agreed step 2 and has no caller need; note it in the progress log as a possible follow-up.
3. `paramstore/main/Main.java:77`: remove the key prefix from the log.

**Behaviour / compatibility.**
- Step 1: no functional change. The eager resolution only produced log lines, and startup makes one fewer metadata call.
- Step 2: presigned URLs change only for clients built by `createS3Client(config)` whose config region or provider differs from us-east-1 plus the default chain. **mercury-services impact: none** (§4.3). Every mercury-services module that generates presigned URLs gets its `StorageClient` from `createDefaultS3Client()`: network `ServerModule` (alliance-partner, blacklist-email, commercial-entity, geography, subscriptions) and tx-tracking `TxTrackingModule`. None of the `createS3Client(config)` callers generates presigned URLs.
- Step 2, why construction is safe (verified in AWS SDK 2.30.24 source):
  - With region and provider supplied, `S3Presigner.build()` does no region lookup and no credential resolution, so it does less work than today's eager `resolveCredentials()`.
  - It gets the same region and provider objects the `S3Client` already received (`S3ClientFactory.java:49-50`).
- **Guard rule:** `DefaultSdkPresigner.close()` closes its credentials provider. On the step 2 path that provider is the caller's own, shared with the `S3Client`.
  - `S3StorageClient` has no `close()` today. Do **not** add one that closes the presigner.
  - State this in the Javadoc of `createS3Client`.
- Full evidence and the commands used: §7.2 and §7.4 (C-40..C-52).

**Tests.** `S3StorageClientConstructionTest` (new):
- constructing with a mocked `S3Client` does not call `resolveCredentials` on any provider. Inject a counting provider through a package-private `createPresigner(AwsCredentialsProvider)` overload, or assert with a log-capturing appender (Logback `ListAppender` on the `S3StorageClient` logger) that no event contains "Access Key".
- `generatePresignedUrl` still works with a stub provider (existing `S3StorageClientGeneratePresignedUrlTest` stays green).
- Step 2, `StorageClientFactoryPresignerTest` (new). Signing is offline, so no network is needed. Use a `StaticCredentialsProvider` with access key `AKIDEXAMPLE`.
  - `createS3Client(config with region eu-west-1 and the static provider)` → the presigned URL's host contains `eu-west-1`, and its `X-Amz-Credential` contains `AKIDEXAMPLE` and `/eu-west-1/s3/`.
  - The same with us-east-1 → the URL is signed for us-east-1 (regression guard).
  - `createDefaultS3Client()` → still us-east-1 (unchanged path).

**Acceptance.** No log line contains an access key id. The constructor makes no credential call.

**AppianWay follow-up.** The `com.inttra.mercury.cloudsdk` WARN override can be relaxed later (separate decision). A22 is closed.

---

### U11. "No API-call timeout" option on the factories (Optional, recommended; priority 7)

**Functional need.** v1 `clientExecutionTimeout` ended when the response headers arrived and did not cover reading a streamed body. In SDK 2.x, `apiCallTimeout` covers the whole call, including the body that cloud-sdk reads fully. Every cloud-sdk factory always sets an API-call timeout (S3 30 s default through `BaseAwsConfig`, SQS 30 s, SNS 10 s, SSM 10 s) and rejects zero. So AppianWay set generous caps through the factories (D13: **S3 10 min, SQS listener 60 s**) and must confirm on INT that no workspace document takes longer (A23). With a real "no timeout" option, stalls stay bounded by the socket timeout, exactly as in v1.

**Current code.**
- `BaseAwsConfig.java:28-40`: `clientExecutionTimeout` defaults to 30 s. `validateBaseConfig` (103) rejects only negative values.
- `S3ClientFactory.java:86-98` `createOverrideConfig`: always `.apiCallTimeout(config.getClientExecutionTimeout())`.
- `MessagingClientFactory.java:127-149` `createOverrideConfig`: always sets `apiCallTimeout` when the timeout is non-null. `validateDuration` (231-235) rejects zero. Used by `createConfiguredClient` (89) and `createExtendedSqsClient` (264).
- `NotificationClientFactory.java:114-137` and `validateDuration` (222): same pattern as messaging.
- `ParameterStoreClientFactory.java:26-38`: always `.apiCallTimeout(config.getClientExecutionTimeout())`.
- `DynamoRepositoryFactory.java:353-368`: `apiCallTimeout` from `clientExecutionTimeout` / `apiCallTimeout`, when non-null.
- `EmailClientFactory.java:136-155`: its own `AwsSesEmailConfig.clientExecutionTimeout` (default 10 s) sets both `apiCallTimeout` and `apiCallAttemptTimeout`.

**Technical change.**
1. `BaseAwsConfigBuilder`: new method `public B noClientExecutionTimeout()`. It sets `protected boolean clientExecutionTimeoutDisabled = true` and clears `clientExecutionTimeout`. Calling `clientExecutionTimeout(d)` afterwards re-enables the timeout (last call wins).
2. `BaseAwsConfig`: `private final boolean clientExecutionTimeoutDisabled;` and `public boolean isClientExecutionTimeoutDisabled()`. `getClientExecutionTimeout()` stays non-null (it still returns the 30 s default), so existing readers are not surprised.
3. Each factory that reads `getClientExecutionTimeout()` for `apiCallTimeout` skips setting it when `isClientExecutionTimeoutDisabled()`: `S3ClientFactory.createOverrideConfig`, `MessagingClientFactory.createOverrideConfig`, `NotificationClientFactory.createOverrideConfig`, `ParameterStoreClientFactory.createParameterStore`, `DynamoRepositoryFactory.createOverrideConfig` (its `clientExecutionTimeout` branch only; an explicit `apiCallTimeout` on `DynamoDbClientConfig` still applies). `apiCallAttemptTimeout` from `requestTimeout` / `apiCallAttemptTimeout` is unaffected.
4. `AwsSesEmailConfig` has its own field, so do the same with its own `noClientExecutionTimeout()` if it is simple. SES is **not** needed by AppianWay (its 10 s is acceptable), so this part is optional.

**Behaviour / compatibility.** No change unless `noClientExecutionTimeout()` is called.

**Tests.** One test class per factory touched, or one parameterised `NoClientExecutionTimeoutFactoryTest`:
- default config → `overrideConfiguration().apiCallTimeout()` equals today's value (regression guard).
- `noClientExecutionTimeout()` → `apiCallTimeout()` empty. Retry strategy and attempt timeout unchanged.
- `noClientExecutionTimeout().clientExecutionTimeout(5s)` → 5 s.
- `BaseAwsConfig`: flag default false.

**Acceptance.** The S3 and SQS clients can be built with no API-call timeout through the factories.

**AppianWay follow-up.** `ClientProfile` drops the D13 caps: S3 and the SQS listener use `noClientExecutionTimeout()`. The SQS sender and SNS keep 10 s. A23 is closed. Design page correction A21 is adjusted.

---

### U14. `S3StorageClient.getObject`: one GET, no extra HEAD (Optional, recommended; priority 8, new)

**Functional need.** The AppianWay rule is "no extra round trips compared with today" (progress doc §3, Performance). The v1 workspace `read` was one GET returning the body and user metadata (`S3WorkspaceService.java:179`). Commons `getObject` makes **two** calls: `getObjectAsBytes` (GET) and then a `headObject` (HEAD) only to fill size, eTag and last-modified. All of those are already in the `GetObjectResponse`. Every workspace read in every service would pay one extra S3 request, plus a race: if the object is replaced between the two calls, the size and eTag can describe a different version from the body.

**Current code.** `S3StorageClient.java:548-590`: GET at 554-557, HEAD at 562-575. The `S3Object` is built from `headObjectResponse`. `S3StorageObject` (impl) reads metadata and content type from the GET response already (lines 46-58).

**Technical change.**
1. In `getObject`, build the `S3Object` from `objectContent.response()`: `.size(resp.contentLength() != null ? resp.contentLength() : bytes.length)`, `.eTag(resp.eTag())`, `.lastModified(resp.lastModified())`. Remove the `headObject` call. The byte-length fallback keeps `getSize()` correct when a response (or a test stub) carries no Content-Length.
2. Change the INFO "retrieved" log to use `resp.contentLength()` instead of `asByteArray().length` (same value). Keep it at INFO, because it is an existing message.
3. Out of scope, note only: `getObject` buffers the whole body in memory (`getObjectAsBytes`). A streaming variant (`ResponseInputStream`) would be a new method. AppianWay does not need it for this release.

**Behaviour / compatibility.** The returned `StorageObject` has the same fields, with values taken from the GET instead of a later HEAD. One request fewer. No API change.

**mercury-services check (2026-11-12): no caller or API impact, so U14 is in scope** (§4.4). No mercury-services code builds an `S3StorageClient` itself or stubs `headObject`, and no main code reads `getSize()` / `getETag()` / `getLastModified()` from `getObject`.

**The one existing commons test that must change (accepted, decision 2).** `cloud-sdk-aws/src/test/java/com/inttra/mercury/cloudsdk/storage/impl/S3StorageClientGetObjectTest.java`, `testGetObjectSuccessfully` (lines 50-73), tests the current implementation detail. It builds an empty `GetObjectResponse`, takes size and eTag from a stubbed `headObject` (lines 53-59), and verifies the HEAD call (lines 71-72). Change only its setup and that verification:
- move `contentLength` / `eTag` onto the `GetObjectResponse`;
- delete the `headObject` stub;
- replace the HEAD `verify` with `verify(s3ClientMock, never()).headObject(any(HeadObjectRequest.class))`.

The assertions on key, size, eTag and content stay exactly as they are. Do this in the **red** commit (the test fails against the current code because a HEAD is made), and record it in the progress log. No other existing test may change. `S3StorageClientMetadataTest`'s `headObject` stubs belong to `getMetadata` and are unaffected.

**New tests** (add to `S3StorageClientGetObjectTest`):
- one `getObjectAsBytes` call, `verify(s3, never()).headObject(any(HeadObjectRequest.class))`.
- size/eTag/lastModified/contentType/metadata come from the GET response.
- error mapping unchanged (`NoSuchKeyException`, `S3Exception`, `SdkClientException`).

**Acceptance.** `getObject` = exactly one S3 request.

**AppianWay follow-up.** None in code. The workspace adapter's `read` gets v1 parity on request count automatically.

---

### U10. Version conflict on `save` as a `cloud-sdk-api` exception (Optional, priority 9)

**Functional need.** Transformer allocates EDIFACT, FF and XML control numbers with optimistic locking. The entity has a `@DynamoDbVersionAttribute`, and the enhanced client's `VersionedRecordExtension` adds `attribute_not_exists` on the first write and `version = :old` afterwards. On a conflict, `EnhancedDynamoRepository.save` lets the SDK `ConditionalCheckFailedException` propagate unwrapped, so transformer must import an AWS SDK type. That is one of the allowed exceptions to the boundary rule, and it is what mercury-services booking `SequenceIdProvider` does. U10 lets AppianWay drop that exception from the allowed list and from `AwsSdkBoundaryArchTest`.

**Current code.**
- `cloud-sdk-aws/.../database/impl/EnhancedDynamoRepository.java:233-239` `save`: `table.putItem(item)`, no catch. `update` (269-282) same. `saveIfNotExist` (299-335) catches `ConditionalCheckFailedException` and returns `Optional.empty()`.
- `StandardDynamoRepository.java:333`: also catches it in its conditional path.
- `cloud-sdk-api/.../database/exception/DynamoSupportException.java`: `RuntimeException`, the only database exception in the api module.
- `cloud-sdk-aws/.../database/config/DynamoRepositoryConfig.java`: `@Builder @Value`, four scan flags.

**Compatibility constraint (important).** mercury-services callers already catch `ConditionalCheckFailedException` from `save`. Changing the thrown type unconditionally would break them at runtime with no compile error. So the mapping must be **opt-in**.

**Technical change.**
1. `cloud-sdk-api`: new `com.inttra.mercury.cloudsdk.database.exception.ConditionalWriteFailedException extends DynamoSupportException`, with constructors `(String message, Throwable cause)`. Javadoc: "A conditional write (version check or condition expression) was rejected because the stored item did not match. The cause is the provider exception."
2. `DynamoRepositoryConfig`: new field `boolean translateConditionalCheckFailures` (Lombok builder default false; `@Builder.Default` not needed for a primitive false).
3. `EnhancedDynamoRepository.save`, `update`, `save(Iterable)` (per item): wrap `table.putItem` / `updateItem` in `try { … } catch (ConditionalCheckFailedException e) { if (repositoryConfig.isTranslateConditionalCheckFailures()) throw new ConditionalWriteFailedException("Conditional write failed for table " + tableName, e); throw e; }`. Check how Lombok names the getter for a field already prefixed `is…` and keep the existing naming style. `saveIfNotExist` is unchanged (it already absorbs the exception).
4. Optional: the same in `StandardDynamoRepository` for symmetry. AppianWay uses only `EnhancedDynamoRepository` (`createEnhancedRepository`).

**Behaviour / compatibility.** Default false → identical behaviour.

**Tests.** `EnhancedDynamoRepositoryConditionalWriteTest` (Mockito `DynamoDbTable`, or DynamoDB Local if the module's IT setup is preferred; `LocalDynamoDBServer` exists under `database/integration`):
- flag false + `putItem` throws CCFE → CCFE propagates (same instance).
- flag true + CCFE → `ConditionalWriteFailedException` with the CCFE as cause.
- flag true + other `DynamoDbException` → propagates unchanged.
- flag true + success → returns the item.
- versioned entity on DynamoDB Local (if an IT is added): two saves of the same stale version → second throws `ConditionalWriteFailedException`.

**Acceptance.** With the flag on, a version conflict surfaces as a `cloud-sdk-api` type. With it off, nothing changes.

**AppianWay follow-up.** Transformer builds its repository config with `translateConditionalCheckFailures(true)` and catches `ConditionalWriteFailedException`. `ConditionalCheckFailedException` is removed from the boundary allow-list.

---

### U6. Consistent full-table scan (Optional, priority 10)

**Functional need.** The transformer v1 DAO reads its control-number table with `DynamoDBMapper.scan` and `ConsistentReads.CONSISTENT`, and fails if **more than one** item exists (a guard against a corrupted table). `DatabaseRepository.findAll()` is never consistent, and it returns an empty list unless `isFindAllUnpaginatedScanEnabled`. The fallback, `findById(SequenceId, consistentRead=true)`, reads the same item with the same consistency but cannot raise the "more than one item" error (transformer OI 2).

**Current code.**
- `cloud-sdk-api/.../database/api/DatabaseRepository.java`: `List<T> findAll()`, no consistency option.
- `EnhancedDynamoRepository.java:517-529` `findAll()`: `table.scan().items()` when enabled, else `log.warn` and an empty list. `findAll(Integer limit, Map exclusiveStartKey, Expression filter)` (911-…) builds a `ScanEnhancedRequest` without `consistentRead`.

**Technical change.**
1. `DatabaseRepository` (api), new default method:
   ```java
   /** Full scan; consistentRead=true requests strongly consistent reads. Default: consistentRead=false delegates to findAll(); true is unsupported. */
   default List<T> findAll(boolean consistentRead) {
       if (!consistentRead) return findAll();
       throw new UnsupportedOperationException("findAll(consistentRead=true) is not supported by this DatabaseRepository implementation");
   }
   ```
2. `EnhancedDynamoRepository` overrides it: the same `isFindAllUnpaginatedScanEnabled` gate and the same warn/empty behaviour when disabled, then `table.scan(ScanEnhancedRequest.builder().consistentRead(consistentRead).build()).items().stream().toList()`.
3. Optional: add `consistentRead` to the paginated `findAll(limit, startKey, filter)` as a new overload. Not needed by AppianWay.

**Behaviour / compatibility.** New method only. `findAll()` is unchanged.

**Tests.** `EnhancedDynamoRepositoryConsistentScanTest`:
- enabled + true → the captured `ScanEnhancedRequest.consistentRead() == true`, items returned.
- enabled + false → `consistentRead` false or null, same as `findAll()`.
- disabled → empty list plus a warn log, no scan call.

In `cloud-sdk-api`: the default method with true → `UnsupportedOperationException`, with false → delegates.

**Acceptance.** A consistent full scan is possible through the interface.

**AppianWay follow-up.** The transformer DAO enables the scan in its `DynamoRepositoryConfig`, calls `findAll(true)`, and restores the "more than one item" error. Transformer OI 2 closes.

---

### U7. Metric publisher on the factory configs (Optional, priority 12)

**Functional need.** Transformer keeps the AWS SDK CloudWatch metrics (v1 `AwsSdkMetrics.enableDefaultMetrics()`, namespace `AWSSDK_{environment}_{componentName}`). SDK 2.x has no JVM-wide switch, and a global execution interceptor cannot add a publisher: generated clients resolve publishers from client and request configuration before interceptors run (checked in `DefaultSqsClient` 2.30.24). The only SDK 2.x way is a per-client `ClientOverrideConfiguration.addMetricPublisher(..)`. The factories accept none, so the `shared` client-profile helper builds transformer's SQS/S3/SNS/DynamoDB SDK clients itself and wraps them in the public cloud-sdk-aws implementations (an allowed exception, `shared` OI 13). U7 removes that helper.

**Design choice.** Pass a `MetricPublisher` (SDK SPI type, `software.amazon.awssdk.metrics.MetricPublisher`, in `metrics-spi`, already on the classpath through `sdk-core`), **not** a namespace. That keeps commons free of the `cloudwatch-metric-publisher` dependency and the CloudWatch client lifecycle. The caller owns one publisher per JVM and closes it. This is the same kind of SDK config value as `RetryStrategy`, so it fits the existing allowed-types rule.

**Technical change.**
1. `BaseAwsConfigBuilder`: `public B metricPublisher(MetricPublisher publisher)`, which appends to a `List<MetricPublisher>` (null ignored). `BaseAwsConfig`: `public List<MetricPublisher> getMetricPublishers()` (unmodifiable, empty by default).
2. Every factory's override configuration adds `config.getMetricPublishers().forEach(overrideBuilder::addMetricPublisher)`: `S3ClientFactory.createOverrideConfig` (and `createS3TransferManager` if it builds a client), `MessagingClientFactory.createOverrideConfig`, `NotificationClientFactory.createOverrideConfig`, `DynamoRepositoryFactory.createOverrideConfig`, `ParameterStoreClientFactory`, `EmailClientFactory`.
3. Commons never closes the publisher. Javadoc states it.

**Behaviour / compatibility.** Empty list by default → identical clients.

**Tests.** `MetricPublisherFactoryTest` (parameterised over the factories): a stub `MetricPublisher` passed in → present in `overrideConfiguration().metricPublishers()`. Not passed → empty. For SQS, an optional test with a stub publisher and a mocked HTTP client to check that `publish` is called after a request (if easy; otherwise the config assertion is enough).

**Acceptance.** Any factory-built client can carry the caller's metric publisher.

**AppianWay follow-up.** `ClientProfile` passes the transformer's `CloudWatchMetricPublisher` through the configs. The helper that builds SDK clients is deleted, and so is the allowed-types entry "SDK clients + CloudWatchMetricPublisher". A9 (dashboards) still applies, because the SDK 2.x metric names differ.

---

### U4. Importable commons BOM (Optional, priority 13)

**Functional need.** Maven `<dependencyManagement>` overrides transitive versions. The AppianWay root pom therefore has to copy every platform pin commons uses (Jetty, Jackson, logback, slf4j, Guava, HttpComponents), or it silently **downgrades** what commons patched (CVE fixes). Today this is done by hand, and `PlatformLibraryVersionsTest` checks it (1a, D2). A BOM lets AppianWay import the pins instead.

**Current state.** The root `pom.xml` is `com.inttra.mercury:mercury-services-commons:1.0` (packaging `pom`, fixed version `1.0`), with modules declared at `${dependency.version}` = `1.0.38-SNAPSHOT`. Its `<dependencyManagement>` (lines 90-304) imports `jetty-bom`, `jetty-ee10-bom`, `jackson-bom` and Dropwizard, and pins many libraries. Importing that parent is unsafe: its version is fixed at `1.0`, so it cannot track releases, and it would bring test and plugin noise.

**Technical change.**
1. New module `bom/` (artifactId `mercury-services-commons-bom`, packaging `pom`, version `${dependency.version}`, parent = the root). Add `<module>bom</module>` to the root.
2. Its `<dependencyManagement>`:
   - the commons artifacts at `${dependency.version}`: `commons`, `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-client`, `email-sender` (only those that are deployed).
   - imports, in the same order as the root (order matters, first import wins): `jackson-bom ${jackson.version}`, `jetty-bom` / `jetty-ee10-bom ${jetty.version}`, `dropwizard-dependencies ${dropwizard.version}`, AWS SDK v2 `bom` at the version `cloud-sdk-aws/pom.xml:24-27` uses.
   - explicit pins that override Dropwizard's: `logback-classic` / `logback-core ${logback.version}`, `slf4j-api ${slf4j.version}`, `guava ${google.guava.version}`, `httpcore5 ${httpcore5.version}`, HttpComponents 4 core/client, `commons-lang3 ${commons-lang3.version}`, log4j (if pinned for CVEs).
   - **Not** jest: `commons` declares 5.3.3 (`io.searchbox.jest.version`) while `cloud-sdk-api` / `cloud-sdk-aws` and AppianWay ingestor use 6.3.1. Pinning 5.3.3 in a BOM would downgrade ingestor. Leave jest unmanaged, or manage 6.3.1 only after the commons owner confirms `commons` works with it.
3. Make sure the BOM is included in `build_deploy.sh` / `build_libs_deploy.sh` so it is published with the other artifacts.

**Tests.** A build check is enough: a tiny test project, or `mvn -pl bom help:effective-pom`, showing the managed versions equal the root properties. Optional enforcer rule: the BOM's managed versions equal the root's.

**Acceptance.** `<scope>import</scope>` of `mercury-services-commons-bom:<release>` gives a consumer the same versions as commons itself.

**AppianWay follow-up.** The root pom imports the BOM and drops its copied pins. `PlatformLibraryVersionsTest` stays as the guard.

---

### U1. Commons config command with `run (yaml) (properties...)` (Optional, priority 14)

**Functional need.** Every AppianWay service starts with `java -jar app.jar run <yaml-on-classpath> <properties...>`. The properties files come from the file system or S3 through the bootstrap's provider. Commons `ConfigProcessingServerCommand` registers as `server` with one YAML file and does no properties substitution. ingestor `create-mapping-template` and transformer / cargoscreen / itv-gps `DynamoTableCommand` reuse the command under other names. The `shared` fallback is **already merged** (1b, PR #78, decision D8: same class name and constructors, internals on the commons chain). So U1 only removes duplication, which makes it the lowest priority.

**Reference implementation (copy the behaviour exactly):**
- `appianway/shared/src/main/java/com/inttra/mercury/shared/command/ConfigProcessingServerCommand.java`: `CLI_COMMAND = "run"`, `PROPERTIES_PARAMS = "properties"` (`nargs("*")`). Constructors `(app)` and `(app, command, description)`. YAML through `ResourceConfigurationSourceProvider`. Protected hooks `createConfigurationSourceProvider(ConfigurationSourceProvider, List<String>)` and `createParameterStoreLookup()`.
- `appianway/shared/src/main/java/com/inttra/mercury/shared/config/PropertiesSources.java`: each path is read through the bootstrap provider as UTF-8, and the files are joined with `System.lineSeparator()` in order before a single `Properties.load`, so a later file overrides an earlier one.
- `appianway/shared/src/main/java/com/inttra/mercury/shared/config/ConfigTransformChain.java`: `variables = properties + environment` (environment wins), `ChainingConfigTransformer(new PropertiesSubstitutionConfigProvider(yaml, variables), new TrimConfigCommentsTransform().andThen(new ParameterStoreConfigTransform(lazyLookup)))`. The `ParameterStoreLookup` is created lazily (memoized), only when a `${awsps:}` placeholder exists, because its constructor builds an SSM client.

**Technical change.**
1. `commons/src/main/java/com/inttra/mercury/config/PropertiesConfigProcessingServerCommand<T extends Configuration> extends ServerCommand<T>`, a new class. The existing `ConfigProcessingServerCommand` is unchanged. Same constructors, CLI, hooks and behaviour as the reference.
2. Public helpers, in the same package: `PropertiesSourcesLoader.load(ConfigurationSourceProvider, List<String>)` and `PropertiesConfigChain.create(yamlSource, properties, environment, Supplier<StringLookup>)`. Or keep them package-private if the reviewer prefers a smaller API.
3. Keep the F8 semantics (accepted 2026-11-09): only placeholders that the YAML references are resolved and validated.

**Tests.** Port the AppianWay tests for these three classes (in `appianway/shared/src/test/java/.../command` and `.../config`) to commons: CLI parsing (`run a.yaml p1.properties p2.properties`, custom name), override order, environment precedence, `${k:-default}`, unresolved → fail fast, comment trimming, lazy `ParameterStoreLookup` (never constructed without `${awsps:}`).

**Acceptance.** An AppianWay service could replace the `shared` command with a 3-line subclass of the commons one and pass `ConfigResolutionGoldenTest` unchanged.

**AppianWay follow-up.** `shared` `ConfigProcessingServerCommand` becomes a thin subclass that keeps its name (D8). `ConfigTransformChain` and `PropertiesSources` are deleted.

### U15. Do not log a missing key at ERROR with a stack trace (Optional, low; priority 15, added 2026-11-19)

**Functional need.** `AbstractStorageObject.handleNoSuchKeyException` (`cloud-sdk-aws/.../storage/impl/AbstractStorageObject.java:186-191`) logs every `NoSuchKeyException` with `log.error("Message : {}, bucket = {}, key = {}", ..., e)`, that is, at ERROR with the full stack trace, and then throws `S3OperationException`. It is reached from `getObject` (`S3StorageClient.java:583`), `getMetadata` (`:742`), `getObjectSize` (`:782`, `:786`) and `getContent` (`:879`). A missing key is often an expected answer that the caller handles. AppianWay's `shared` `StorageReadHealthCheck` GETs the probe key `anykey` and is **healthy exactly when it is missing** (D28: a HEAD cannot tell a missing key from a missing bucket). So every run of the check logs one ERROR line with a stack trace, in every service that has the check (dispatcher, error-processor so far). SDK v1 logged nothing for a 404. The logger cannot simply be turned off in the services: the same logger carries the real S3 errors (`handleS3Exception`, `handleSdkException`, `handleUnexpectedException`).

**Technical change.**
1. In `handleNoSuchKeyException`, log at DEBUG, keeping the exception (`log.debug(..., e)`), instead of ERROR. The thrown `S3OperationException` (message, cause) is unchanged.
2. Nothing else changes: `handleBucketNotFoundError`, `handleS3Exception` and the other handlers keep their ERROR logs.

**Tests.** A logback `ListAppender` on the `AbstractStorageObject` logger: a `getObject`, `getMetadata`, `getObjectSize` and `getContent` of a missing key each log no ERROR event and still throw the same `S3OperationException` (message, cause). A missing bucket still logs at ERROR.

**mercury-services check (before implementing).** Search mercury-services for alerts or tests that depend on the ERROR line "Message : … bucket = …, key = …" (log-based alerts, `ListAppender` tests). If none, no impact: every caller already gets the exception.

**AppianWay follow-up.** None in code. Closes AppianWay finding F21 when released.

---

## 4. mercury-services impact check (2026-11-12)

This section replaces the earlier PR grouping: there are no separate PRs, and work goes directly on the commons feature branch. The full findings list (F-1..F-27), every command used with its syntax explained (C-01..C-86), and the U13 step 2 no-impact argument are in §7 below (a copy of §10 of the commons progress log). booking is covered item by item in §7.2a.

**What was searched.** `C:\Users\arijit.kundu\projects\mercury-services`, branch `develop` at `53e77f4e8f`, using `git grep` over tracked `*.java` and `config.yaml` files. Modules that use `com.inttra.mercury.cloudsdk`: auth, bill-of-lading-v2, booking, booking-bridge, booking-downstream-processor, lambda/*, network/*, partner-integrator, rates, registration, self-service-reports, shipping-instruction, tx-tracking, value-added-service, visibility, watermill-publisher and webbl.

| Item | Result | In 1.0.39? |
|---|---|---|
| U2 | No impact (4.1) | Yes |
| U5 | One caller sets the old builder value, so the new name is used (4.2) | Yes, as `requestVisibilityTimeoutSeconds(..)` |
| U13 step 2 | No impact (4.3) | Yes |
| U14 | No caller or API impact. One commons unit test must change (4.4) | Yes |
| U12 | No SSM caller sets a retry strategy, so nothing starts being applied (4.5) | Yes (decision 8) |
| U3, U8, U9, U11, §2.3 flag | New methods or switches only, off by default. No caller impact by construction. U9: every mercury-services SES client is built by `createDefaultSesClient(..)` with no retry strategy, so nothing starts being applied (F-26). No existing class uses any of the new method names (F-27). Test fakes (booking `FlowStep.EmailServiceTestImpl`) keep compiling through the default methods | Yes |
| **booking** (booking, booking-cargoscreen, booking-bridge), all items | S3: `putObject(String)` with JSON, `getObject` (body only) and `copyObject`. booking uses `createDefaultS3Client()`; cargoscreen uses `createS3Client(config)` with us-east-1 and the default-provider singleton; no presigning. SQS options without visibility. SES via `createDefaultSesClient`. Details item by item in §7.2a (F-20..F-25) | No impact on any item |

### 4.1 U2: zero-length puts

| Search | Hits | Assessment |
|---|---|---|
| The commons messages `Content must not be null or empty`, `content must not be null or empty`, `Input stream is closed or empty`, `Content length must be greater than 0`, and the constants `CONTENT_VALIDATION_MESSAGE` / `CONTENT_LENGTH_VALIDATION_MESSAGE` | Only `oceanschedules-process/common/.../s3/MultiPartUploader.java:126`. It has its own copy of the text, and oceanschedules does not use cloud-sdk | Not affected |
| Tests that put empty content | `booking/.../common/s3/S3WorkspaceServiceTest.java:142-147` `putObject_emptyContent` expects `putObject(bucket, file, "")` to **succeed** (mocked `StorageClient`). `oceanschedules-process` `S3WorkspaceServiceTest:163` uses the SDK v1 client | booking already expects U2 behaviour. Against the real client this throws today, so U2 fixes it |
| Main code that catches `IllegalArgumentException` in classes using `StorageClient` (14 files) | Every catch or throw relates to the caller's own validation (environment settings, missing detail, partner fields). None depends on an empty-put exception. watermill-commons classifies an IAE from `putObject` as `NonRecoverableException`; its test covers a blank **key**, not empty content | Not affected |
| Guards like `isEmpty()` / `length == 0` just before `putObject` | None | Nobody relies on commons to reject empty content |

### 4.2 U5: receive visibility timeout

| Search | Hits | Assessment |
|---|---|---|
| `visibilityTimeoutSeconds(` on `ReceiveMessageOptions.Builder` | **bill-of-lading-v2** `config/QueueConfig.java:44` (`toReceiveMessageOptions()`). Value from `config.yaml`: **300** in cvt, int, qa and prod; 30 in test resources | **A caller exists**, so the new name is used (decision 4) |
| `getVisibilityTimeoutSeconds()` on the options | bill-of-lading-v2 `BillOfLadingInjectorTest:55,64` asserts it equals the config value | Must keep returning the stored value. The old method stays unchanged |
| Where the bill-of-lading-v2 options go | `BillOfLadingInjector.provideEblInboundListener` / `provideEblRegistrationListener` pass only wait time, max messages and queue URL to commons `SqsListener`, which builds new options (`SqsListener.createReceiveMessageOptions()`, no visibility). The 300 is never sent today | With the new name it still won't be. Keeping the old name would have left a latent change for any future path that passes these options to `receiveMessages(options)` |
| Other `receiveMessages(ReceiveMessageOptions)` callers | booking-bridge, booking, partner-integrator (pi-commons), watermill-commons, webbl: all build options with queue URL, max messages and wait time only. booking-cargoscreen uses `receiveMessages(String,int,int)` | Not affected |
| `libs/atlantida` `QueueConfig.getVisibilityTimeoutSeconds` | Its own SDK v1 interface | Not related |

### 4.3 U13 step 2: presigner from the configured region and provider

| Search | Hits | Assessment |
|---|---|---|
| Subclasses of `S3StorageClient` / uses of `createPresigner` | None | Free to leave `createPresigner()` as it is |
| `generatePresignedUrl` callers (main) | network alliance-partner, blacklist-email, commercial-entity, geography and subscriptions (all bound through network `ServerModule.java:41-42`), and tx-tracking (`TxTrackingModule.java:77`) | All use `StorageClientFactory.createDefaultS3Client()`, which step 2 does not touch. **Presigned URLs unchanged** |
| `StorageClientFactory.createS3Client(config)` callers (main) | booking-cargoscreen, lambda auth-tokens-archive, bounceback-email, optionalvalidation-archive, registration-archive, subscription-archive, shipping-instruction `S3ArchiveHandler`, visibility-commons, visibility-s3-archiver | None generates presigned URLs. Their only change is a presigner built with their own region and provider, which is unused |

### 4.4 U14: `getObject` without the extra HEAD

| Search | Hits | Assessment |
|---|---|---|
| mercury-services code or tests that build `new S3StorageClient(..)` or stub `headObject` | None (watermill-commons mentions `headObject` only in Javadoc, about its own metadata read) | Not affected |
| Main code reading `getSize()` / `getETag()` / `getLastModified()` from `getObject` results | None | Not affected. Values would be the same anyway, now taken from the GET |
| commons tests | `S3StorageClientGetObjectTest.testGetObjectSuccessfully` (lines 50-73) gets size and eTag from a `headObject` stub and verifies the HEAD call | **The one existing test that changes.** Setup and verification only; assertions unchanged (see U14). `S3StorageClientMetadataTest`'s HEAD stubs are for `getMetadata` and are unaffected |

### 4.5 U12: SSM retry strategy (checked 2026-11-12)

U12 changes behaviour only for a caller that builds `AwsParameterStoreConfig` with `retryStrategy(..)`. Today that value is silently ignored. Searched with `git grep` over tracked `*.java`: mercury-services `develop` at `53e77f4e8f`, commons at `c353706`, AppianWay at `fa3efede`.

| Search | Hits | Assessment |
|---|---|---|
| mercury-services files using `AwsParameterStoreConfig` / `createParameterStore` | db-migration `ParamStore`, lambda bounceback-email (`HandlerSupport`, `SSMParameterLookUp`), lambda partner-integration `Utils`, partner-integrator pi-si-out-processor and pi-statusevents-out-processor `Utils`, visibility-error-email `ParameterStoreResolver`, visibility-outbound-poller `HandlerSupport` (plus tests) | None of them contains `retryStrategy` / `RetryStrategy`. **Not affected** |
| commons callers | `commons` `ParameterStoreLookup` (region and credentials only), `paramstore/main/Main.java`, tests | No retry strategy set. **Not affected** |
| commons tests on the factory | `CloudParameterStoreClientFactoryTest` (Mockito config mocks), `AllFactoriesBuilderModeTest:105` | Mocks return false for the new flag. Both stay green unchanged |
| AppianWay | `shared` `ConfigProcessingServerCommand.createParameterStoreLookup()` goes through the commons `ParameterStoreLookup` | Not affected |

---

## 5. Decisions (Arijit, 2026-11-12)

| # | Decision | Answer |
|---|---|---|
| 1 | Commons version and branch | **Continue on `feature/ION-12310-commons-cloudsdk-refactoring` and bump to `1.0.39-SNAPSHOT`** (first commit). Backups were taken before any change: local branch `backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12` at `c353706`, plus the verified bundle `C:\Users\arijit.kundu\backups\2026-11-12\commons-feature-ION-12310-c353706.bundle`. The AppianWay feature branch is also backed up (`backup/WI01124532-aws-sdk-upgrade-pre-commons-u-items-2026-11-12` at `fa3efede`, plus a bundle), and the untracked docs of both repos are in `*-untracked-docs.tar.gz` in the same folder |
| 2 | Scope of the first commons release | **U3** (without the optional `getObjectProperties`), **U8, U9, U2** (only if no mercury-services impact: none found, §4.1), **U5, U13, U11, U14** (only if no impact to existing callers and API: none found, §4). Plus the §2.3 flag that U9 needs |
| 3 | U2 validation relaxation | **Only if no impact in mercury-services.** None found (§4.1), so U2 is in |
| 4 | U5 naming | **As recommended:** callers exist (bill-of-lading-v2, §4.2), so use the new name `requestVisibilityTimeoutSeconds(..)`. The old method stays inert |
| 5 | U13 step 2 | **Include it: it is a latent bug.** No mercury-services impact (§4.3) |
| 6 | U7 | **Later.** The `shared` helper stays for this release |
| 7 | 1d timing | **1d waits for the commons release** |
| 8 | U12 | **Include it in 1.0.39**, right after U9 (priority 3a). No impact found (§4.5) |
| 9 | Release note | **Update the root `README.md` with the 1.0.39-SNAPSHOT changes**: brief, to the point, and clear (§2.4). Last commit |

---

## 6. After commons is released: AppianWay checklist

1. Bump `mercury.commons.version` in the AppianWay root pom. Run `PlatformLibraryVersionsTest` and the full reactor build (G2/G4).
2. 1d: the workspace adapter uses `getObjectSize` (U3), direct zero-length puts (U2) and `getObject` (U14). `InboundSqsHealthCheck` receives with `requestVisibilityTimeoutSeconds(0)` (U5). `ClientProfile` uses `noClientExecutionTimeout()` for S3 and the listener (U11).
3. email-sender (step 2): `sendEmailWithResult` (U8), `DefaultRetryStrategy.doNotRetry()` (U9).
3a. watermill-publisher (step 4), optional: `ClientProfile` passes its retry strategy to the SSM config (U12).
4. transformer (step 3): `translateConditionalCheckFailures(true)` (U10), `findAll(true)` with the "more than one item" guard (U6), metric publisher through the configs (U7, if done).
5. Update `AwsSdkBoundaryArchTest` allowed types (remove `ConditionalCheckFailedException` after U10, and the SDK-client helper after U7).
6. Progress doc: close A1, A2, A22, A23 (and A3 for the items done). Review summary §9 tracker: record U11–U14. Program and `shared` page OI texts get the batched minor edit (A21).
7. functional-testing fakes (1e) implement the new methods: `getObjectSize`, `sendEmailWithResult`, `findAll(boolean)`.

---

## 7. Investigation findings and command log (Claude, 2026-11-11/12, before implementation; booking and cross-cutting checks added 2026-11-12)

> Copy of §10 of the commons progress log (`C:\Users\arijit.kundu\projects\mercury-services-commons\cloud-sdk-api\docs\2026-11-12-sdk-commons-changes-for-apway.md`), taken 2026-11-12. The progress log is the living copy. Section numbers 10.x there = 7.x here. Finding (F-) and command (C-) ids are the same in both.

This section records **what was checked before any code change, how, and what was found**, so anyone can re-run the checks. All checks are read-only.

| Repository | State checked |
|---|---|
| mercury-services | `develop` @ `53e77f4e8f` |
| mercury-services-commons | `feature/ION-12310-commons-cloudsdk-refactoring` @ `c353706` |
| AWS SDK | 2.30.24, the version pinned in `cloud-sdk-aws/pom.xml` |

### 7.1 Findings summary

| # | Topic | Finding | Evidence (7.4 command ids) |
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
| F-15 | U13 step 2: shared provider and `close()` | `DefaultSdkPresigner.close()` closes the credentials provider when it is closeable. **`S3StorageClient` has no `close()` and never closes its presigner**, so the provider shared with `S3Client` is never closed by this change. This becomes a guard rule (7.2) | C-47, C-50 |
| F-16 | U13 step 2: values | The presigner gets exactly what `S3ClientFactory.createConfiguredClient` already gives the `S3Client` (`S3ClientFactory.java:49-50`: `getRegion().getRegionDelegate()` and `getCredentialsProvider().getCredentialProviderDelegate()`). `validateBaseConfig` guarantees both are non-null. If the `S3Client` builds, so does the presigner | C-48 |
| F-17 | U13 step 1 side note | `DefaultCredentialsProvider.create()` returns a **JVM-wide singleton** (`DefaultCredentialsProvider.java:53,81-83`). Today the eager `resolveCredentials()` in `createPresigner()` warms that singleton at construction, and the default `S3Client` shares it. After step 1, the first credential fetch happens on the first real S3 call. Not functional: today a failure there only logged a WARN, and nothing failed fast. Expect a few ms more on the first S3 call after startup | C-51 |
| F-18 | AppianWay | Doesn't use `StorageClientFactory` or cloud-sdk presigning yet. The only `generatePresignedUrl` hits are the SDK v1 fake in `functional-testing/.../AmazonS3Adaptor.java` | C-52 |
| F-19 | Retry defaults (§2.3) | AWS SDK default for SES/SSM with no strategy = **LEGACY** (4 attempts, throttling backoff 500 ms half-jitter, throttling retries free in the token bucket, honours `AWS_RETRY_MODE`). Commons default = **STANDARD** (3 attempts, throttling backoff 1 s full-jitter, throttling costs tokens, fixed in code). Both retry the same error classes | C-60..C-63 |
| F-20 | booking: how the S3 client is built | booking `BookingMessagingModule.java:81` and `lambda/S3ArchiveHandler.java:99` → `createDefaultS3Client()`. booking-cargoscreen `BookingCargoScreenApplicationInjector.java:253` → `createS3Client(config)` with region from `config.yaml` (**us-east-1** in cvt/int/qa/prod) and `DefaultCredentialsProvider.create()` (the JVM singleton). booking-bridge has no S3 | C-80, C-85 |
| F-21 | booking: S3 calls made | booking `common/s3/S3WorkspaceService`: `copyObject` (45), `putObject(String)` (65), `getObject` (86, 97, content only). booking `S3ArchiveHandler.writeToS3`: `putObject(String)` (258, JSON). cargoscreen `service/S3WorkspaceService`: `putObject(String)` (37), `getObject` (65, content only). No presign, `getMetadata`, `objectExists`, list, delete or stream/byte puts | C-81, C-82 |
| F-22 | booking vs U2 | All production puts write JSON (`BookingService.java:336` `Json.toJsonString(detail)`, `S3ArchiveHandler` `toS3Json`), which is never empty. The cargoscreen workspace `putObject` has no production caller. The only empty put is booking's own test `putObject_emptyContent`, which **expects success**. With U2 the real client now matches that test. **No impact** | C-23, C-83 |
| F-23 | booking vs U14 | Both `getContent` methods read only `getContent()` of the returned object. Same bytes, one S3 request fewer per read, and no GET/HEAD version race. **No impact** (improvement) | C-82 |
| F-24 | booking vs U13 | booking (`createDefaultS3Client`): step 1 only. The access-key INFO line disappears, and the first credential fetch moves to the first S3 call (F-17). cargoscreen (`createS3Client(config)`): step 2 builds the presigner with **us-east-1 and the same `DefaultCredentialsProvider` singleton** that today's `createPresigner()` uses, so it is identical in practice, and cargoscreen never presigns. **No impact** | C-80, C-85, C-50, C-51 |
| F-25 | booking vs U5, U8, U9, U11, U3, copyObject | U5: booking and booking-bridge `SQSClient` build options without visibility (C-15). U8/U9: `BookingEmailSenderModule.java:56` → `createDefaultSesClient(..)` (no retry strategy, so the U9 flag is false and nothing changes). U11/U3: not used (cargoscreen sets `clientExecutionTimeout`, which is unaffected). `copyObject`: no item touches it. **No impact** | C-15, C-84 |
| F-26 | U9 across all of mercury-services | Every SES client (auth, booking, network server, registration, tx-tracking, webbl) is built with `EmailClientFactory.createDefaultSesClient(..)`, whose config sets only region and credentials (`EmailClientFactory.java:118-125`). visibility-inbound builds its own `SesV2Client`, not through commons. So no caller has a configured strategy that U9 would suddenly start applying. **No impact** | C-84 |
| F-27 | New API names vs existing code | No class in mercury-services or AppianWay declares `sendEmailWithResult`, `getObjectSize`, `isRetryStrategyConfigured`, `noClientExecutionTimeout`, `requestVisibilityTimeoutSeconds`, `isVisibilityTimeoutRequested` or `getRequestedVisibilityTimeoutSeconds`, so there are no signature clashes. Test fakes implementing the changed interfaces (booking `FlowStep.EmailServiceTestImpl implements EmailService`; pi-commons `RecordingMessagingClient implements MessagingClient`, which gets no new methods) keep compiling through the default methods | C-86 |

### 7.2 U13 step 2: is there any impact? Conclusion

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
- Do not pass `endpointOverride` or `S3Configuration` to the presigner (out of scope, F1 in the progress log §7).
- Add the `StorageClientFactoryPresignerTest` cases from the spec, including a regression case that `createDefaultS3Client()` still signs for us-east-1.

**Residual risk outside the checked repos:** a commons consumer outside mercury-services and AppianWay that builds through `createS3Client(config)` with a non-us-east-1 region **and** generates presigned URLs. It would now get a correctly signed URL instead of a us-east-1 one. That is the latent-bug fix, not a regression. No such consumer is known.

### 7.2a booking: item-by-item

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

### 7.3 Shell syntax used in the commands

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

### 7.4 Command log

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

#### Retry defaults for §2.3 (C-60..C-63)

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

## Appendix A. Files to change (absolute paths)

Root: `C:\Users\arijit.kundu\projects\mercury-services-commons\`

| Item | File |
|---|---|
| U3, U2 | `cloud-sdk-api\src\main\java\com\inttra\mercury\cloudsdk\storage\api\StorageClient.java` |
| U3, U2, U13, U14 | `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\storage\impl\S3StorageClient.java` |
| U2 | `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\storage\impl\AbstractStorageObject.java` |
| U13 | `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\paramstore\main\Main.java`, `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\storage\factory\StorageClientFactory.java` (step 2) |
| Version | `pom.xml` (root, line 20: `dependency.version`) |
| Release note | `README.md` (root; append `### Commons v1.0.39-SNAPSHOT` after the 1.0.38 section, §2.4) |
| U12 (test) | new `cloud-sdk-aws\src\test\java\com\inttra\mercury\cloudsdk\paramstore\factory\ParameterStoreClientFactoryRetryStrategyTest.java` |
| U14 (test) | `cloud-sdk-aws\src\test\java\com\inttra\mercury\cloudsdk\storage\impl\S3StorageClientGetObjectTest.java` (`testGetObjectSuccessfully` setup only) |
| U8 | `cloud-sdk-api\src\main\java\com\inttra\mercury\cloudsdk\email\api\EmailService.java`, `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\email\impl\SesEmailServiceImpl.java` |
| U9 | `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\email\factory\EmailClientFactory.java` |
| §2.3, U11, U7 | `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\aws\config\BaseAwsConfig.java` |
| U11, U7 | `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\storage\factory\S3ClientFactory.java`, `…\messaging\factory\MessagingClientFactory.java`, `…\notification\factory\NotificationClientFactory.java`, `…\database\factory\DynamoRepositoryFactory.java`, (`…\email\config\AwsSesEmailConfig.java` optional) |
| U12, U11, U7 | `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\paramstore\factory\ParameterStoreClientFactory.java` |
| U5 | `cloud-sdk-api\src\main\java\com\inttra\mercury\cloudsdk\messaging\model\ReceiveMessageOptions.java`, `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\messaging\aws\impl\SqsMessagingClient.java` |
| U10 | new `cloud-sdk-api\src\main\java\com\inttra\mercury\cloudsdk\database\exception\ConditionalWriteFailedException.java`, `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\database\config\DynamoRepositoryConfig.java`, `…\database\impl\EnhancedDynamoRepository.java` (optional `…\StandardDynamoRepository.java`) |
| U6 | `cloud-sdk-api\src\main\java\com\inttra\mercury\cloudsdk\database\api\DatabaseRepository.java`, `cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\database\impl\EnhancedDynamoRepository.java` |
| U4 | `pom.xml` (add module), new `bom\pom.xml`, `build_deploy.sh` / `build_libs_deploy.sh` |
| U1 | new classes in `commons\src\main\java\com\inttra\mercury\config\` |

AppianWay reference sources for U1 and the consumers: `C:\Users\arijit.kundu\projects\appianway\shared\src\main\java\com\inttra\mercury\shared\` (`command\ConfigProcessingServerCommand.java`, `config\ConfigTransformChain.java`, `config\PropertiesSources.java`, `config\ClientProfile.java`, `workspace\S3WorkspaceService.java`).

## Appendix B. Prompt to hand to the commons agent

Copy everything inside the box.

> You are working in `C:\Users\arijit.kundu\projects\mercury-services-commons` on the existing branch `feature/ION-12310-commons-cloudsdk-refactoring` (head `c353706`, already backed up; do not create sub-branches or PRs). The specification is `C:\Users\arijit.kundu\projects\appianway\docs\redesign\2026-11-11-sdk-commons-upgrade-specs.md`. Read §2 (rules, including §2.3), §4 (mercury-services impact check) and §5 (decisions) before you start.
>
> **Scope: these items only, in this order, one after another.**
> 1. Version bump: root `pom.xml` `dependency.version` `1.0.38-SNAPSHOT` → `1.0.39-SNAPSHOT`, one commit `WI01124532 ION-12310 build: commons 1.0.39-SNAPSHOT`.
> 2. §2.3 flag `BaseAwsConfig.isRetryStrategyConfigured()`.
> 3. U3: `StorageClient.getObjectSize` and its S3 HEAD override. Do **not** add `getObjectProperties`.
> 4. U8: `EmailService.sendEmailWithResult`.
> 5. U9: `EmailClientFactory` applies the retry strategy only when it is configured.
> 6. U12: `ParameterStoreClientFactory` applies the retry strategy only when it is configured (same pattern as U9).
> 7. U2: zero-length puts.
> 8. U5: `ReceiveMessageOptions.requestVisibilityTimeoutSeconds(..)`, a **new** builder method. The existing `visibilityTimeoutSeconds(..)` stays unchanged and is never sent.
> 9. U13: steps 1 **and** 2, plus `Main.java`.
> 10. U11: `noClientExecutionTimeout()`. The `AwsSesEmailConfig` part is optional.
> 11. U14: `getObject` with one GET.
> 12. Release note: append `### Commons v1.0.39-SNAPSHOT` to the root `README.md` (§2.4). Keep it brief, to the point and clear, and describe the code as built. One commit `WI01124532 ION-12310 docs: README release note for 1.0.39-SNAPSHOT`.
>
> Nothing else: not U1, U4, U6, U7 or U10.
>
> **How to work.**
> - Follow §2 strictly: additive only, default interface methods, new switches off by default, no new dependencies, and no log changes except U13.
> - Each item gets a red commit (failing test), then a green commit, then a refactor commit only when there is something to clean up. Every message starts with `WI01124532 ION-12310` (work item code **and** Jira key, as in the last commit `c353706`), in the form `WI01124532 ION-12310 <phase>: <summary>`.
> - Use JUnit 5 + AssertJ + Mockito, one test class per unit.
> - Run `mvn clean verify` from the commons root after each green commit. It must stay green.
> - Before each item, re-check its file:line references against the current code (the spec was written against `c353706`).
>
> **Existing tests.** Existing tests must pass unchanged. The **only** pre-approved exception is U14's `S3StorageClientGetObjectTest.testGetObjectSuccessfully`: change setup and verification only, as described in U14. If any other existing test has to change, or a change cannot be made additively, stop and report instead of working around it.
>
> **Progress log.** Write all progress and details of the changes in `C:\Users\arijit.kundu\projects\mercury-services-commons\cloud-sdk-api\docs\2026-11-12-sdk-commons-changes-for-apway.md`, and update it after every commit. Record:
> - each item's status;
> - classes, methods and tests added or changed, with file paths;
> - commit ids and messages;
> - `mvn clean verify` results (test counts);
> - any deviation from the spec, and why;
> - open questions.
>
> The file is gitignored: never commit it, and never `git add -A`. Stage only the files you changed.
>
> **When done.** Install locally with `mvn clean install` so that AppianWay can build against `1.0.39-SNAPSHOT`, and update the log's summary section. Do not push, release or deploy without asking.
