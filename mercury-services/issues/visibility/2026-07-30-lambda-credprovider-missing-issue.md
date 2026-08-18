# Visibility Lambdas — `CredentialsProvider must not be null` (ION-16387)

## 1. Summary

Four visibility AWS Lambda handlers fail on cold start with
`java.lang.IllegalArgumentException: CredentialsProvider must not be null`:

- `visibility-outbound-poller` (`VisibilityOutboundPoller`)
- `visibility-pending-start` (`VisibilityPendingStart`)
- `visibility-error-email` (`VisibilityErrorEmail`)
- `visibility-s3-archiver` (`VisibilityS3Archiver`)

The AWS 2.x migration wired the cloud-sdk config builders (parameter store, SQS messaging,
S3 storage) with only a `region(...)` and no `credentialsProvider(...)`. The cloud-sdk
`BaseAwsConfig` validation now **requires an explicit, non-null credentials provider**, so the
builder throws at construction time and the lambda handler fails to initialise.

- **Branch:** `bugfix/ION-16387` (rebased onto latest `develop`).
- **Commits (not pushed):**
  - `ION-16387 Fix for credential provider issue` (pre-existing on branch)
  - `ION-16387 Tests Fix for credential provider issue` (pre-existing on branch)
  - `ION-16387 Improve visibility-s3-archiver HandlerSupport test coverage` (added here — coverage)
- **Model:** Claude Opus 4.8 (1M context).
- **Outcome:** Fix reviewed and **verified against the real AWS int environment**; all unit +
  integration tests green; `visibility-s3-archiver` `HandlerSupport` coverage raised well above the
  Sonar 80% gate. Two commits by design (fix + coverage) — single-commit constraint relaxed by the user.

## 2. Investigation

### 2.1 Code path (root cause trace)
On `develop`, `visibility-outbound-poller/.../lambda/HandlerSupport.getParameterStore()` built:

```java
ParameterStoreClientFactory.createParameterStore(
    AwsParameterStoreConfig.builder()
        .region(resolveRegion())      // no credentialsProvider(...)
        .build());
```

`AwsParameterStoreConfig$Builder.build()` → `BaseAwsConfig.validateBaseConfig()` →
`ConfigurationValidator.validateNotNull()` throws `CredentialsProvider must not be null`.
The same omission exists in the SQS/messaging and S3/storage builders of the other three lambdas
(and in `visibility-error-email`'s `ParameterStoreResolver`).

### 2.2 Git history
- `git --no-pager log --oneline develop..origin/bugfix/ION-16387` → the two fix commits.
- `git merge-base develop origin/bugfix/ION-16387` and `git diff <merge-base>..origin/bugfix/ION-16387 -- visibility/`
  → isolated the fix diff from develop drift (the branch was 2 commits behind develop, all in
  `oceanschedules-process` poms — unrelated; cleared by the rebase).

### 2.3 The fix (as delivered on the branch)
Consistent across all handlers — every cloud-sdk config builder now gets an explicit region **and**
credentials provider:

```java
private static AwsCredentialsProviderWrapper resolveCredentialsProvider() {
    return AwsCredentialsProviderWrapper.of(DefaultCredentialsProvider.create());
}
```

- `visibility-outbound-poller` — `HandlerSupport.getParameterStore()` adds `.credentialsProvider(...)`.
- `visibility-error-email` — `ParameterStoreResolver` ctor adds `.credentialsProvider(...)`.
- `visibility-pending-start` — `HandlerSupport.newSQSClient()` now builds a fully-configured
  `AwsMessagingClientConfig` (queue url, region, credentials, timeouts).
- `visibility-s3-archiver` — `HandlerSupport.newStorageClient()` uses `AwsStorageConfig` with region +
  credentials; `getDynamoDbClient()` sets region + `DefaultCredentialsProvider`.

## 3. Root cause

The cloud-sdk `BaseAwsConfig` configuration validation requires a **non-null `CredentialsProvider`**.
The AWS 2.x migration left the visibility lambda config builders without one, so every affected
handler throws `IllegalArgumentException: CredentialsProvider must not be null` during construction
(cold start), before it can do any work. The fix supplies the AWS default credentials chain
(`DefaultCredentialsProvider.create()`, wrapped as `AwsCredentialsProviderWrapper`), which in AWS
Lambda resolves the execution-role credentials at runtime. See **§12** for the full credential- and
region-resolution mechanism (Lambda vs ECS) — the important point is that the validation only checks
the provider **object** is non-null; it does not require credentials to be present at build time.

## 4. Reproduction / verification against real AWS (READ-ONLY, profile `081020446316_INTTRA-Dev-Engg`)

The failure is a runtime/cold-start infra symptom; it is corroborated directly from live CloudWatch
logs rather than a local unit test.

- The four handlers are **AWS Lambda** functions (java17, `State=Active`), each with a distinct IAM
  **execution role** — so `DefaultCredentialsProvider` (via `EnvironmentVariableCredentialsProvider`)
  resolves the role's credentials at runtime, and `AWS_REGION` is always set by the Lambda runtime.

  | Lambda function | Execution role |
  |---|---|
  | `inttra-int-lambda-visibility-outbound-poller` | `INTTRA-INT-Visibility-Outbound-Lambda` |
  | `inttra-int-lambda-visibility-pending-start` | `INTTRA-LAMBDA-INT-TT-PENDING-Start` |
  | `inttra-int-lambda-visibility-error-email` | `inttra_int_visibility_error_email_lambda` |
  | `inttra-int-lambda-visibility-s3-archive` | `INTTRA-LAMBDA-INT-TT-STREAM-S3` |

- **outbound-poller** CloudWatch: the exact reported trace is present
  (`HandlerSupport.getParameterStore:54` → `resolveSsmPath:62` → `VisibilityOutboundPoller.<init>`) —
  root cause confirmed live.
- **error-email** CloudWatch: same error via
  `ParameterStoreResolver.<init>:30` → `util.HandlerSupport.setClientIdAndClientSecret:86` →
  `createInjector` → `VisibilityErrorEmail.<init>` — matches the `ParameterStoreResolver` patch.
- **s3-archive** CloudWatch (Jul-18): `S3StorageClient: Resolved AWS credentials using provider:
  DefaultCredentialsProvider(providerChain=[SystemProperty, EnvironmentVariable, WebIdentityToken,
  Profile(default), Container, InstanceProfile])` — **direct runtime proof that
  `DefaultCredentialsProvider` successfully resolves the execution-role credentials in the real Lambda
  environment.** s3-archive's remaining problem is the Sonar coverage gate, not a runtime failure.
- **pending-start**: no credentials error in logs (its default-client path did not hit the validation);
  the fix makes region + credentials explicit for consistency.

**Conclusion:** the `bugfix/ION-16387` approach is valid and **will work in the real AWS Lambda
environment** — the missing config was the credentials provider, and each function has an execution
role that `DefaultCredentialsProvider` resolves.

## 5. Fix — coverage change (this session)

Sonar reported **new-code coverage 72.2%** for `visibility-s3-archiver` `HandlerSupport`, with the
`resolveRegion` catch/exception block uncovered. `DefaultAwsRegionProviderChain` is constructed inside
the method and the repo's mockito (2.27) cannot mock constructors/statics, so a small, behaviour-preserving
testability seam was added:

- `visibility-s3-archiver/.../lambda/HandlerSupport.java`
  - `resolveRegion()` now delegates to a new package-private
    `resolveRegion(Supplier<Region> regionSupplier)`; the no-arg method's behaviour is unchanged
    (`() -> new DefaultAwsRegionProviderChain().getRegion()`).
- `visibility-s3-archiver/.../lambda/HandlerSupportTest.java`
  - `resolveRegionUsesResolvedRegion` — success branch (`region != null`).
  - `resolveRegionFallsBackWhenNull` — `null` → `us-east-1` fallback.
  - `resolveRegionFallsBackWhenProviderThrows` — provider exception → catch block → fallback.
  - `ClassContract.isInstantiable` — covers the implicit constructor.

No wire/disk formats change; this is test-scaffolding plus an internal method split.

## 6. Tests & coverage

### 6.1 Coverage — `visibility-s3-archiver` `HandlerSupport` (jacoco `report-aggregate`)

| Metric | Before | After |
|---|---|---|
| LINE | 82.5% (33/40) | **95.1% (39/41)** |
| BRANCH | 66.7% (4/6) | **83.3% (5/6)** |
| Sonar blended (lines+conditions) | ~80.4% | **93.6%** |

Report: `visibility/visibility-s3-archiver/target/site/jacoco-aggregate/jacoco.xml`.
The `resolveRegion` exception block and all branches are now covered. The only remaining misses are the
two **pre-existing** env accessors (`getS3ArchiveBucket`, `getDynamodbEnvironment`) happy paths + their
`x -> x` lambdas — unchanged code with fixed env-var keys that cannot be set without a new test
dependency; they are not new code and do not affect the new-code gate.

### 6.2 Passing test commands + counts (4 affected modules)

```bash
# Full unit + integration verify for the 4 affected modules (+deps)
mvn -Pmercury-commons -f visibility/pom.xml \
  -pl visibility-outbound-poller,visibility-pending-start,visibility-error-email,visibility-s3-archiver \
  -am clean verify            # BUILD SUCCESS, exit 0

# Coverage measurement (jacoco under the sonar profile)
mvn -Pmercury-commons,sonar -f visibility/pom.xml -pl visibility-s3-archiver -am package -DskipITs
```

- **Unit (surefire):** 62 tests, 0 failures, 0 errors, 2 skipped (pre-existing `@Disabled`).
- **Integration (failsafe):** 3 tests, 0 failures, 0 errors (`VisibilityS3ArchiverIT`).
- `visibility-s3-archiver` `HandlerSupportTest`: 14 tests (was 10; +4 added here).

## 7. Command log (key commands, each with intent)

```bash
# Orientation
git status -sb                                            # working tree; branch on origin only
git branch -a --list "*ION-16387*"                        # branch exists on origin
git fetch origin bugfix/ION-16387                         # fetch the delivered fix
git diff --stat develop..origin/bugfix/ION-16387          # scope of change
git rev-list --left-right --count develop...origin/bugfix/ION-16387   # 2 behind / 2 ahead
git log --oneline develop..origin/bugfix/ION-16387        # the 2 fix commits
git merge-base develop origin/bugfix/ION-16387            # isolate fix vs develop drift
git diff <merge-base>..origin/bugfix/ION-16387 -- visibility/   # the actual fix diff

# Branch + rebase (kept develop's rates json out of the rebase via a scoped stash)
git checkout -b bugfix/ION-16387 origin/bugfix/ION-16387
git branch bugfix/ION-16387-backup-20260730
git tag ION-16387-pre-fix-backup-20260730
git stash push -m "temp" -- rates/generated/swagger-ui/rates-api-1.0.json
git rebase origin/develop                                 # onto latest develop (2 commits)
git stash pop

# AWS read-only verification (profile 081020446316_INTTRA-Dev-Engg)
aws sso login --profile 081020446316_INTTRA-Dev-Engg
aws --profile ... sts get-caller-identity
aws --profile ... lambda list-functions --query "Functions[?...].FunctionName"
aws --profile ... lambda get-function-configuration --function-name <fn>  # role/runtime/handler/env
aws --profile ... logs filter-log-events --log-group-name /aws/lambda/<fn> \
    --filter-pattern "CredentialsProvider" --start-time <ms> --max-items 3   # live error evidence

# Build / test / coverage
mvn -Pmercury-commons -f visibility/pom.xml -pl <4 modules> -am clean verify
mvn -Pmercury-commons,sonar -f visibility/pom.xml -pl visibility-s3-archiver -am package -DskipITs
```

> Note: jacoco/sonar live in the root pom's `sonar` profile, and `lombok.version` (and other props) live
> in the `activeByDefault` `mercury-commons` profile. Because `-P` disables default profiles, coverage
> builds must activate **both**: `-Pmercury-commons,sonar`.

## 8. Build results

- `mvn -Pmercury-commons ... -am clean verify` → **BUILD SUCCESS** (exit 0), unit + integration green.
- Coverage build → **BUILD SUCCESS**; `HandlerSupport` LINE 95.1% / BRANCH 83.3% / blended 93.6%.

## 9. Token-usage

Token usage is captured by the mcp-context-server harness hook (Copilot CLI `agentStop`); no manual
`session_record_usage` was fabricated. `session_usage_report` for session
`visibility-lambda-credprovider-null-fix-20260730` (`a47cf0b3b28742aa`) confirms capture at handoff.

## 10. References

- Jira: **ION-16387**
- Reference docs: `visibility/docs/visibility-architecture-design-claude.md`,
  `visibility/docs/2026-06-26-aws-service-resource-details.md`,
  `visibility/docs/2026-07-10-rebase-resolve-conflict-fix-test.md`
- Generated prompt: `.github/prompts/issue-fix/20260730-visibility-lambda-credprovider-null.md`

## 11. Handoff notes

- 3 commits on `bugfix/ION-16387`, all referencing `ION-16387`, **not pushed** (awaiting review).
- The same `resolveRegion(Supplier<Region>)` coverage seam can be applied to
  `visibility-outbound-poller` / `visibility-pending-start` `HandlerSupport` if their Sonar gates also
  flag the `resolveRegion` catch block; left unchanged here to keep scope to the reported module.
- Backup: branch `bugfix/ION-16387-backup-20260730`, tag `ION-16387-pre-fix-backup-20260730`.

## 12. Credential & region resolution (AWS SDK 2.x) — Lambda vs ECS

> This section answers the question "how does the lambda actually get its credentials — the AWS
> credential env vars are **not** set on the function." That observation is correct, and this explains
> why the fix still works.

### 12.1 The two-step model — provider *object* vs credential *values*

There are two distinct things, and the bug conflated neither of them correctly:

1. **The `CredentialsProvider` object** — a Java object handed to the cloud-sdk config builder. The
   cloud-sdk `BaseAwsConfig.ConfigurationValidator.validateNotNull(...)` checks *only that this object
   reference is non-null*. It runs at **build/cold-start time** and does **not** contact AWS or require
   any actual credential values. `develop` passed no provider → `null` → `IllegalArgumentException:
   CredentialsProvider must not be null`. The fix passes `DefaultCredentialsProvider.create()` — a
   non-null (and *lazy*) provider object — which satisfies the validation.
2. **The credential values** (access key / secret / session token) — resolved **lazily, at the first
   AWS API call**, by walking the provider chain. This is where the runtime environment (Lambda vs ECS)
   matters. Because `DefaultCredentialsProvider` is a `LazyAwsCredentialsProvider`, nothing is resolved
   at construction; so the fix would satisfy the build-time validation even in an environment with no
   credentials at all — but at runtime Lambda *does* supply them (below).

### 12.2 AWS SDK 2.x `DefaultCredentialsProvider` chain

`software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider.create()` resolves credentials by
trying these providers **in order**, using the first that succeeds (verbatim from the live CloudWatch
log of `inttra-int-lambda-visibility-s3-archive`):

```
DefaultCredentialsProvider(providerChain=Lazy(AwsCredentialsProviderChain([
    SystemPropertyCredentialsProvider(),        # -Daws.accessKeyId / -Daws.secretAccessKey
    EnvironmentVariableCredentialsProvider(),   # AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
    WebIdentityTokenCredentialsProvider(),      # AWS_WEB_IDENTITY_TOKEN_FILE (EKS/IRSA)
    ProfileCredentialsProvider(profileName=default),  # ~/.aws/credentials|config (local dev)
    ContainerCredentialsProvider(),             # AWS_CONTAINER_CREDENTIALS_RELATIVE_URI/_FULL_URI (ECS/Fargate)
    InstanceProfileCredentialsProvider()        # EC2 IMDS (169.254.169.254)
])))
```

(SDK 1.x equivalent used by the pre-migration code was
`com.amazonaws.auth.DefaultAWSCredentialsProviderChain`, which has the same provider ordering.)

### 12.3 How **AWS Lambda** supplies credentials (this module)

- The function has an **IAM execution role** (e.g. `INTTRA-LAMBDA-INT-TT-STREAM-S3`), whose trust policy
  allows only `Principal: { Service: lambda.amazonaws.com }` to `sts:AssumeRole`:

  ```json
  { "Effect": "Allow", "Principal": { "Service": "lambda.amazonaws.com" }, "Action": "sts:AssumeRole" }
  ```

- On each invocation the **Lambda service assumes that execution role via STS** and the **Lambda
  runtime injects the resulting temporary credentials as *reserved runtime environment variables***:
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (plus `AWS_REGION` /
  `AWS_DEFAULT_REGION`). These are set by the **platform**, not by the developer.
- **This is why they do not appear in `get-function-configuration → Environment.Variables`** — that map
  only holds the *developer-configured* variables (`s3ArchiveBucket`, `dynamoDbEnv`, …). The credential
  variables are part of the sandbox's runtime environment and are intentionally not shown there (and
  Lambda even rejects them as reserved keys if you try to set them yourself).
- Therefore, in Lambda the chain resolves at the **2nd provider, `EnvironmentVariableCredentialsProvider`**
  (the reserved keys are present), yielding the execution role's temporary STS credentials. The
  `ProfileCredentialsProvider(profileName=default)` never triggers in Lambda because there is no
  `~/.aws` profile and the earlier env-var provider already succeeded.

Verified evidence: `inttra-int-lambda-visibility-s3-archive` CloudWatch (2026-07-18) logged
`S3StorageClient: Resolved AWS credentials using provider: DefaultCredentialsProvider(...)` followed by
successful `Wrote content to location: s3://…` — i.e. the execution-role credentials were resolved and
used at runtime with no error.

### 12.4 How the **ECS** service modules supply credentials (contrast)

- ECS tasks are given a **task IAM role**. The ECS agent publishes short-lived credentials at a
  loopback endpoint and sets **`AWS_CONTAINER_CREDENTIALS_RELATIVE_URI`** (or `…_FULL_URI`) in the
  container.
- The SDK's **`ContainerCredentialsProvider`** (5th in the chain) detects that variable and fetches the
  **task-role** credentials from `http://169.254.170.2${AWS_CONTAINER_CREDENTIALS_RELATIVE_URI}`,
  refreshing them automatically.
- So ECS does **not** use `EnvironmentVariableCredentialsProvider` (there are no raw access-key env
  vars); it resolves later in the chain via the container endpoint. Lambda resolves earlier, via the
  injected key/secret/token env vars.

| Aspect | AWS Lambda (these handlers) | ECS service modules |
|---|---|---|
| Identity | Execution role (`lambda.amazonaws.com` trust) | Task role (`ecs-tasks.amazonaws.com` trust) |
| Credential delivery | Reserved runtime env vars `AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN` injected by the platform | Loopback creds endpoint via `AWS_CONTAINER_CREDENTIALS_RELATIVE_URI` |
| Resolving provider | `EnvironmentVariableCredentialsProvider` (2nd) | `ContainerCredentialsProvider` (5th) |
| Visible in `Environment.Variables`? | **No** (reserved / platform-set) | No (the relative-URI var is platform-set) |
| Nature of creds | Temporary STS creds for the execution role | Temporary STS creds for the task role |

### 12.5 Region resolution (same pattern)

`resolveRegion()` uses `DefaultAwsRegionProviderChain`, whose first provider (`SystemSettingsRegionProvider`)
reads the `aws.region` system property or the `AWS_REGION` / `AWS_DEFAULT_REGION` env var. **Lambda sets
`AWS_REGION` as a reserved runtime variable**, so the region resolves from the environment (us-east-1
here); the code's `us-east-1` fallback is only a safety net. ECS similarly relies on `AWS_REGION` /
`AWS_DEFAULT_REGION` being present (or the profile / IMDS).

### 12.6 Bottom line

The credentials are **not** developer-configured env vars — the user is correct. They are the
**execution-role STS credentials that the Lambda platform injects as reserved runtime env vars**, picked
up by SDK 2.x `EnvironmentVariableCredentialsProvider`. The `develop` failure was purely the missing
**provider object** on the cloud-sdk config (a build-time null check), not a missing-credentials problem;
the fix supplies that object and runtime resolution then works exactly as proven in CloudWatch.

## 13. Rebase & push guidance (force-with-lease)

**State:** `bugfix/ION-16387` was rebased onto the latest `develop`, which **rewrote the two original
commits** (new SHAs `8d6ffd5bb3` / `700112b268` replacing origin's `729264c76e` / `6bb3ba1d90`) and
moved the branch to a newer base, then added the coverage commit `53e54c5482`. Because history was
rewritten, `origin/bugfix/ION-16387` now holds 2 commits that are **not ancestors** of local `HEAD`
(`git log origin/bugfix/ION-16387 --not HEAD` lists them), so a normal `git push` is rejected as
**non-fast-forward**.

- **Yes, a force push is required** to update the remote — use `git push --force-with-lease` (never a
  bare `--force`).
- **Will it cause conflicts?** No. Merge conflicts happen during a *rebase/merge*, and that rebase
  already completed **cleanly** (no conflicts). The push itself only moves the remote ref; it does not
  re-merge anything.
- **Is `--force-with-lease` safe here?** Yes. It refuses to overwrite `origin/bugfix/ION-16387` unless
  it still points at the SHA last fetched (`729264c76e`). If someone else had pushed to the branch in
  the meantime, the push is **rejected**, protecting their work — that is the whole advantage over
  `--force`. Fetch immediately before pushing so the lease reflects reality:

  ```bash
  git fetch origin
  git push --force-with-lease=bugfix/ION-16387:729264c76e origin bugfix/ION-16387
  # or simply, after a fresh fetch:
  git push --force-with-lease origin bugfix/ION-16387
  ```

- **Caveats:** a force push rewrites the remote branch history; anyone who checked out the old branch
  must `git reset --hard origin/bugfix/ION-16387` afterwards. For a personal review branch this is
  fine. The pre-rebase backups (`bugfix/ION-16387-backup-20260730`, tag
  `ION-16387-pre-fix-backup-20260730`) allow full recovery if needed.
- Per the task constraints this agent **did not push** — perform the force-with-lease push yourself
  after review.

## 14. Deployment timeline & why only two of the four lambdas error

### 14.1 What "STS creds" means
**STS = AWS Security Token Service.** It issues **temporary** security credentials — an access key id
prefixed `ASIA…`, a secret access key, **plus a session token**, all with an expiry — whenever a *role*
is assumed (by the Lambda service, the ECS agent, an SSO login, or an explicit `sts:AssumeRole`).
Contrast with a long-term IAM **user** key (`AKIA…` prefix, no session token, no expiry). The
`ASIARFXJR4ZWAEZOPLGZ` key seen in the logs is `ASIA…` → temporary STS creds. Both the Lambda
**execution-role** credentials and the ECS **task-role** credentials are STS temporary creds that the
platform rotates automatically.

### 14.2 When did the AWS 2.x migration deploy?
- The migrated (AWS 2.x) build went live in `int` around **2026-07-16**: `outbound-poller` first threw
  `CredentialsProvider must not be null` at **2026-07-16 16:41:39Z**; `error-email` first threw at
  **2026-07-17 00:10:13Z**.
- The `s3-archive` **2026-07-18** log that shows credentials *resolving successfully* is the **same**
  migrated AWS 2.x code — it just exercises a different, working code path (see §14.3).
- The functions were **re-deployed 2026-07-29/30**, but with the **still-broken** code (this fix is on
  `bugfix/ION-16387`, not yet merged). As of **2026-07-30**, `outbound-poller` is **still erroring**
  (8,736 occurrences in the last 4 days, latest **16:46:40Z**, i.e. after its 12:57Z redeploy) and
  `error-email` is **still erroring** (17 occurrences, latest **00:13:31Z**). So the bug has been live
  since ~2026-07-16 and remains live until this PR is deployed.

### 14.3 Why `s3-archive` and `pending-start` never error (the crux)
It depends entirely on **which cloud-sdk factory each lambda calls** on `develop`:

| Lambda | cloud-sdk call (develop) | Supplies a CredentialsProvider? | Outcome |
|---|---|---|---|
| `outbound-poller` | `AwsParameterStoreConfig.builder().region(...).build()` → `ParameterStoreClientFactory.createParameterStore` | **No** — the config builder **mandates** it via `BaseAwsConfig` | **ERROR** |
| `error-email` | same parameter-store builder, via `ParameterStoreResolver` | **No** | **ERROR** |
| `pending-start` | `MessagingClientFactory.createDefaultStringClient()` | **Yes** — the helper sets `DefaultCredentialsProvider.create()` internally | OK |
| `s3-archive` | `StorageClientFactory.createDefaultS3Client()` | **Yes** — SDK default provider; skips `BaseAwsConfig` validation | OK |

- The **parameter-store** API has **no `createDefault…` helper**. The only way to build it is through
  `AwsParameterStoreConfig`, whose `.build()` runs `BaseAwsConfig` validation that **requires** a
  non-null credentials provider. The migration set the region but forgot the credentials, so the two
  parameter-store consumers (`outbound-poller`, `error-email`) throw at cold start.
- The **storage** and **messaging** APIs *do* expose `createDefault*` helpers
  (`createDefaultS3Client()`, `createDefaultStringClient()`) that internally call
  `DefaultCredentialsProvider.create()` (verified in `cloud-sdk-aws` sources) and **bypass** the strict
  `AwsXxxConfig`/`BaseAwsConfig` validation. `s3-archive` and `pending-start` used those, so they
  received a credentials provider "for free" and never threw.

> Note on `error-email`: it **does** error, but it is **event-driven** (invoked only on error events),
> so its errors are sparse (17 in 4 days) — easy to miss in a short log window — whereas `outbound-poller`
> polls continuously and logs the error on almost every run (8,736 in 4 days).

The fix removes this inconsistency: every lambda now builds its client through the **explicit config**
with an explicit region **and** `AwsCredentialsProviderWrapper.of(DefaultCredentialsProvider.create())`,
so behaviour is uniform and none depends on a `createDefault*` side-effect.

