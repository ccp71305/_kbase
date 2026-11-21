# Elasticsearch (Jest) SigV4 signing: the AWS SDK v1 / `vc.inreach` constraint, and the tx-tracking v2 fix

**Date:** 2026-11-11
**Scope:** `mercury-services-commons` (cloud-sdk-api, cloud-sdk-aws, commons) and `mercury-services/tx-tracking`
**Change verified:** mercury-services commit `a64be209d4` (Sumesh Jacob), merged to `develop` as PR #1334 (`53e77f4e8f`):
*"WI01134742 Replace cloud-sdk-aws JestModule with a local SigV4 Jest client provider so tx-tracking runs on AWS SDK v2 alone"*
**commons version consumed:** `1.0.38-SNAPSHOT`

---

## 1. Summary

| Question | Answer |
|---|---|
| Why did commons still need AWS SDK v1? | Jest (`io.searchbox`) calls to the IAM-protected Amazon Elasticsearch/OpenSearch domains are SigV4-signed by `vc.inreach.aws:aws-signing-request-interceptor:0.0.22`. That library only works with AWS SDK v1: its public constructor takes a `com.amazonaws.auth.AWSCredentialsProvider`, and it pulls in `aws-java-sdk-core`. |
| Does the tx-tracking change remove that dependency for tx-tracking? | **Yes.** After the change tx-tracking resolves **no** `com.amazonaws` artifact. ES requests are signed by a small local interceptor built on the AWS SDK v2 signer (`AwsV4HttpSigner`) and v2 credentials (`DefaultCredentialsProvider`). |
| Will it work? | **Yes, with one config fix.** The build is green (346 tests, 0 failures). A wire-level harness sent every tx-tracking request shape through the real `TxTrackingJestModule`, and an independent SigV4 verifier accepted all 11 requests. The verifier also accepted the old v1 signer (the control) and rejected 3 out of 3 tampered requests. |
| Must fix before release | **Timeout regression.** The old commons client hardcoded read/connect timeouts of 15000/7500 ms. The new module uses the config values, which default to 3000/3000 ms because no `config.yaml` sets them. Add `readTimeoutMillis: 15000` and `connTimeoutMillis: 7500` to `txTrackingElasticSearch` in all four environment configs (§6.1). |
| Does this lift the constraint for commons as a whole? | **No.** The fix is local to tx-tracking. booking, webbl, visibility, shipping-instruction and booking-cargoscreen still get their `JestClient` from the commons `JestModule`, which still signs with `vc.inreach` and SDK v1. §7 explains how to promote the approach into commons. |

---

## 2. Background: the constraint and where it was documented

### 2.1 Original finding

[`cloud-sdk-aws/docs/2026-05-27-aws-java-sdk-core-version-issue.md`](../../cloud-sdk-aws/docs/2026-05-27-aws-java-sdk-core-version-issue.md):

- `commons` depends on `vc.inreach.aws:aws-signing-request-interceptor:0.0.22` "used for AWS request signing with the Jest Elasticsearch client". It transitively pulls `com.amazonaws:aws-java-sdk-core:1.10.19`, which won Maven's nearest-wins resolution and broke client apps.
- The fix pinned `aws-java-sdk-core` to `${aws.java.sdk.version}` (1.12.730) in the root `dependencyManagement`, with this comment:

  ```xml
  <!-- AWS SDK v1 (legacy) — pulled transitively by aws-signing-request-interceptor
       (used by Jest/Elasticsearch in commons) and by cloud-sdk-aws for SNS/SQS modules.
       TODO: Remove once Jest Client is replaced with OpenSearch SDK and all modules
       have fully migrated to AWS SDK v2 (software.amazon.awssdk). -->
  ```
- Its "Future cleanup" section lists: remove `aws-signing-request-interceptor`, then remove `aws-java-sdk-core` from root `dependencyManagement`.

### 2.2 Related documents

| Document | Relevant content |
|---|---|
| [`2026-07-17-rebase-with-develop-owasp-jackson.md`](2026-07-17-rebase-with-develop-owasp-jackson.md) §11–§12 | HttpComponents 4.x pins (`httpcore` 4.4.16, `httpcore-nio` 4.4.16, `httpclient` 4.5.14) are kept specifically for Jest and `vc.inreach`; a compatibility review proves the pins don't break them. |
| [`2026-07-23-sdk-gap-appway-aws-upgrade-design.md`](2026-07-23-sdk-gap-appway-aws-upgrade-design.md) §7.1, gap **X-G8** | The decision record: "no cloud-sdk change and no v2 signing migration"; Jest usage "compatible with the `vc.inreach` 1.x signer only". |
| [`docs/2026-10-28-aws-commons-xray-cve-analysis.md`](../../docs/2026-10-28-aws-commons-xray-cve-analysis.md) | `jackson-dataformat-cbor` CVEs reach apps through `aws-java-sdk-core` (SDK v1) via `vc.inreach`. |
| `mercury-services/docs/2026-0730-mercury-services-aws-pending.md` | "Elasticsearch request signing legitimately needs the AWS v1 `AWS4Signer` … until [the Jest → OpenSearch] migration happens." |
| `mercury-services/lambda/docs/2026-08-19-lambda-aws-refactor.md` §9–§11 | Estate-wide analysis of ES signing; evaluation of the `io.github.acm19` v2 interceptor; validation of what the real constraint is (§11.3–§11.5). |

### 2.3 How Jest signing was wired before (still the path for every other app)

```
App Guice module
  └─ install(new com.inttra.mercury.cloudsdk.aws.module.JestModule(esConfig))      [cloud-sdk-aws]
       └─ newAwsSigningClient(...)
            ├─ new DefaultAWSCredentialsProviderChain()                            [AWS SDK v1]
            ├─ new DefaultAwsRegionProviderChain()                                 [AWS SDK v1]
            ├─ new vc.inreach.aws.request.AWSSigner(v1CredsProvider, region, "es", clock)
            ├─ new vc.inreach.aws.request.AWSSigningRequestInterceptor(signer)
            └─ new JestClientBuilder(interceptor, endpoint, retryHandler).getJestClient()   [cloud-sdk-api]
                   ├─ sync HttpClientBuilder:  stripContentLengthOnDelete → vc.inreach signer, retry handler
                   ├─ async HttpAsyncClientBuilder: vc.inreach signer
                   └─ HttpClientConfig: multiThreaded, readTimeout(15000), connTimeout(7500)  ← hardcoded
```

---

## 3. Why we did not take this approach during the commons upgrade and refactoring

This is the constraint you remember. There were **two** problems: a library that only supports v1, and a shared commons API that is hard-typed to that library. Program policy then decided against working around them.

### 3.1 The signing library only supports AWS SDK v1

`vc.inreach.aws:aws-signing-request-interceptor:0.0.22` is the latest version we use, and the project is no longer maintained. It has no v2 variant. Its public API (from `javap`, §8.6) **requires v1 types**:

```
public vc.inreach.aws.request.AWSSigner(
        com.amazonaws.auth.AWSCredentialsProvider,          ← AWS SDK v1 type
        java.lang.String region, java.lang.String service,
        com.google.common.base.Supplier<java.time.LocalDateTime> clock);
public vc.inreach.aws.request.AWSSigningRequestInterceptor(vc.inreach.aws.request.AWSSigner);
```

Its own POM declares `aws-java-sdk-core:1.10.19`, `guava:18.0` and `httpcore:4.4.1`. You cannot hand it a v2 `AwsCredentialsProvider`, so **the library itself cannot sign with SDK v2**. Getting off v1 means **replacing** the library, not upgrading it.

### 3.2 The shared commons API is hard-typed to that v1 class

`cloud-sdk-api/.../elasticsearch/JestClientBuilder.java` (and the legacy `commons/.../elasticsearch/JestClientBuilder.java`) take the **concrete** class, not the Apache interface:

```java
public JestClientBuilder(AWSSigningRequestInterceptor requestInterceptor, String endpointURL, HttpRequestRetryHandler retryHandler)
//                       ^ vc.inreach.aws.request.AWSSigningRequestInterceptor, not org.apache.http.HttpRequestInterceptor
```

`cloud-sdk-aws/.../module/JestModule.java` builds the signer with v1 `DefaultAWSCredentialsProviderChain` and `DefaultAwsRegionProviderChain`, and uses v1 `com.amazonaws.util.StringUtils`. Any v2 interceptor, whether a third-party one or a hand-written one, is **not a subtype** of `vc.inreach`'s class, so it can't be passed in. To support v2 we would have had to either:

- widen the `JestClientBuilder` constructor and rewrite `JestModule.newAwsSigningClient(...)`, a **breaking change** to a published shared library used by booking, webbl, tx-tracking, visibility, shipping-instruction, booking-cargoscreen (and appianway's ingestor uses the same pattern); or
- add a parallel v2 path.

### 3.3 Program rules and the recorded decision (gap X-G8)

- The appianway / commons AWS-upgrade program ran under a **strictly-additive** rule for the shared library: no breaking changes to published commons APIs. That ruled out widening or replacing the `JestClientBuilder`/`JestModule` signatures during the upgrade.
- Gap **X-G8** (`2026-07-23-sdk-gap-appway-aws-upgrade-design.md` §7.1) records, after checking live source, that an earlier "v2 interceptor" note was wrong. Jest usage is "compatible with the `vc.inreach` 1.x signer only". Elasticsearch is reached over **signed HTTP, not an AWS SDK service client**, so it is "orthogonal to the AWS SDK v1→v2 flip". The outcome was **no cloud-sdk change and no v2 signing migration**.
- The agreed long-term direction was to **replace Jest with the OpenSearch Java client** (`opensearch-java` + `AwsSdk2Transport`), which signs natively with SDK v2 and needs no interceptor. That also retires Jest itself, which is end-of-life (last release around 2019). Hence the TODO in the root pom.

### 3.4 Why a third-party v2 interceptor was not adopted either

`mercury-services/lambda/docs/2026-08-19-lambda-aws-refactor.md` §10 evaluated `io.github.acm19:aws-request-signing-apache-interceptor:3.0.0`, the community successor to AWS's archived interceptor, which signs with SDK v2. It was rejected as an estate-wide answer:

1. It swaps only the signer and **keeps the end-of-life Jest client**: throwaway glue.
2. It adds a new community dependency with **no active maintainers** to a security-critical path across many services.
3. It still required the **breaking commons API change** in §3.2.
4. At the time, booking and tx-tracking jars also shaded **other v1 modules** (`aws-java-sdk-s3/-sns/-sqs/-kms/-ses`). Swapping only the ES signer would not have made those apps free of v1.
5. It declares HttpClient 4.5.x and 5.x as `provided`, which needed extra care against commons' pinned HttpComponents 4.x line.

### 3.5 What was always technically possible (and what changed since)

The lambda doc §11.3 (`javap` of both interceptors) had already shown there is **no runtime reason** Jest can't be signed with SDK v2. Signing happens behind Jest, in a plain `org.apache.http.HttpRequestInterceptor.process(HttpRequest, HttpContext)` hook, and the interceptor buffers the request body. **The blocker was architectural and policy-driven, not technical.**

Sumesh's change takes the route that was technically open all along, and avoids each of the objections:

| Earlier objection | How the tx-tracking change avoids it |
|---|---|
| `vc.inreach` only supports v1 | Doesn't use it; signs with the AWS SDK v2 `AwsV4HttpSigner` directly |
| Breaking change to shared `JestClientBuilder`/`JestModule` | Doesn't touch commons; builds its own `JestClientFactory` in a **local** `TxTrackingJestModule` |
| New, unmaintained third-party dependency (acm19) | No new library; about 160 lines of in-repo code on the official AWS SDK v2 `http-auth-aws` module, already on the classpath via `cloud-sdk-aws` |
| App still had other v1 usages (S3, SES, SQS) | tx-tracking has since moved all of these to cloud-sdk v2 (`StorageClient`, `SesEmailServiceImpl`, `SqsMessagingClient`). The ES signer and one `IOUtils` call were the last v1 uses, so `com.amazonaws:*` can now be excluded wholesale |

---

## 4. What the tx-tracking change does

Files (`git show --stat a64be209d4`):

| File | Change |
|---|---|
| `config/elasticsearch/AwsV4SigningRequestInterceptor.java` (new) | Apache HttpClient 4 `HttpRequestInterceptor`. It builds a v2 `SdkHttpRequest` from the Apache request: method; absolute URI, resolved from `HttpCoreContext.HTTP_TARGET_HOST` when the request line is relative; all headers except `Host` and `Content-Length`. It buffers the entity and signs with `AwsV4HttpSigner` (`SERVICE_SIGNING_NAME`, `REGION_NAME`, `PAYLOAD_SIGNING_ENABLED=true`). It copies the signed headers back and **replaces the entity with a repeatable `ByteArrayEntity`** so the retry handler can resend it. |
| `config/elasticsearch/TxTrackingJestModule.java` (new) | Local copy of the commons `JestModule` plus `JestClientBuilder` wiring. It uses v2 `DefaultCredentialsProvider` and `DefaultAwsRegionProviderChain` (fallback only). The sync client gets the DELETE `Content-Length` strip, then the signer, then `JestClientRetryHandler`; the async client gets the signer. The username/password path is unchanged. Timeouts now come **from config**. |
| `config/TxTrackingModule.java` | `install(new JestModule(...))` replaced by `install(new TxTrackingJestModule(...))` |
| `report/S3QueryService.java` | `com.amazonaws.util.IOUtils` replaced by `software.amazon.awssdk.utils.IoUtils` |
| `pom.xml` | Excludes `com.amazonaws:*` from `commons`, `cloud-sdk-api` and `cloud-sdk-aws`. Excludes `com.sun.mail:javax.mail` and adds `com.sun.mail:jakarta.mail:1.6.8`, which still provides the `javax.mail` package. Excludes `mysql:mysql-connector-java` and adds `com.mysql:mysql-connector-j`. Moves versions into properties (guava, commons-lang3, httpclient5, poi, slf4j, jackson, and others). Removes the redundant `<version>1.0</version>`, which matches the parent version, so this has no effect. |
| Tests (new) | `AwsV4SigningRequestInterceptorTest` (20), `TxTrackingJestModuleTest` (14) |

---

## 5. Verification performed

### 5.1 Dependency tree: no AWS SDK v1 left

`mvn dependency:tree` with an include filter (§8.3) on tx-tracking:

```
com.inttra.mercury:tx-tracking:jar:1.0
+- com.inttra.mercury:commons:jar:1.0.38-SNAPSHOT:compile
|  +- io.searchbox:jest:jar:5.3.3:compile
|  |  \- io.searchbox:jest-common:jar:5.3.3:compile
|  \- vc.inreach.aws:aws-signing-request-interceptor:jar:0.0.22:compile     ← still present, never loaded (see 6.2)
\- com.inttra.mercury:cloud-sdk-aws:jar:1.0.38-SNAPSHOT:compile
   \- software.amazon.awssdk:ssm:jar:2.30.24:compile
      +- software.amazon.awssdk:http-auth-aws:jar:2.30.24:compile          ← provides AwsV4HttpSigner
      \- software.amazon.awssdk:auth:jar:2.30.24:compile                   ← provides DefaultCredentialsProvider
```

No `com.amazonaws:*` artifact is resolved.

### 5.2 Static scan: no code path that still needs v1

- tx-tracking `src/` contains **no** `com.amazonaws` or `vc.inreach` imports. The only matches are the three `<exclusion>` blocks in the pom.
- Main-code users of `com.amazonaws` / `vc.inreach` in commons:
  - `commons`: `elasticsearch/JestClientBuilder`
  - `cloud-sdk-api`: `elasticsearch/JestClientBuilder`
  - `cloud-sdk-aws`: `module/JestModule`, `SNSModule`, `SQSModule`, `SQSReader`, `SQSWriter`, `AwsRetryCondition`, `AWSConstants`
- tx-tracking imports **none** of these. From cloud-sdk it uses only v2-based classes: `ElasticSearchServiceConfig`, `JestClientRetryHandler` (no AWS imports), `SqsMessagingClient`, `MessagingClientFactory`, `StorageClient(Factory)`, `EmailClientFactory`, `SesEmailServiceImpl`, `MailContentImpl`.
- No classpath scanning (`Reflections`, `ClassGraph`, Jersey package scanning) exists in commons that could load the v1 classes indirectly.
- Mail and activation classes still resolve: `com.sun.mail:jakarta.mail:1.6.8` provides `javax.mail.*`, and `com.sun.activation:jakarta.activation:1.2.1` plus `javax.activation-api:1.2.0` provide `javax.activation.*`. `EmailSenderTest` passes.

### 5.3 Build and unit tests

`mvn test` on `tx-tracking`: **BUILD SUCCESS, Tests run: 346, Failures: 0, Errors: 0, Skipped: 0**, including the 34 new tests. `mysql-connector-j` and `poi-ooxml` were missing from the local `~/.m2`; they resolve from the remote repository on an online build.

Limitation: Sumesh's unit tests confirm that `Authorization`, `X-Amz-Date`, the token and the payload hash are **present**. They do not confirm that AWS would **accept** the signature. §5.4 closes that gap.

### 5.4 Wire-level SigV4 harness (independent verification)

**Design.**

1. `SigV4WireHarness.java` (Appendix A) starts a local HTTP server (`com.sun.net.httpserver`). For every request it records the method, the **raw** path and query, all headers and the exact body bytes, i.e. what an AWS endpoint would receive.
2. It sends **tx-tracking's real request shapes** through the **real** `TxTrackingJestModule.newClient(config)`. Credentials (access key, secret, session token) are supplied as system properties and picked up by v2 `DefaultCredentialsProvider`.
3. **Control:** it sends the same requests through the **old** path: commons `JestClientBuilder` plus `vc.inreach` `AWSSigner` with v1 static session credentials. This path is known to work in production.
4. `verify_sigv4.py` (Appendix B) is an **independent, standard-library-only** SigV4 implementation written from the AWS spec, from the server's side. It rebuilds the canonical request from what arrived on the wire (double-encoded canonical URI for non-S3 services, sorted and encoded query, the listed signed headers, SHA-256 of the real body) and recomputes the HMAC chain. It also checks `x-amz-content-sha256` against the body and that `host` is signed.
5. **Negative control:** the verifier is run against 3 deliberately tampered requests to prove it can fail.

**Scenarios** (taken from tx-tracking's `TxElasticSearchService`, `ElasticSearchUtil`, `ReprocessService`, `TxTrackingService` and `IndexPatternBuilder`):

| Scenario | Why it matters |
|---|---|
| Search `txtrack-agg-*` + `addType` | `*` in path (index pattern) |
| Search `txtrack-event-2026-11-05,…-06,…-07` + type | Jest sends `%2C`; tests the double-encoding rule |
| Search with `size=10000&scroll=1m` | Query-string canonicalisation (report export) |
| Search with a UTF-8 body (`Müller – 東京`) | Payload hash over the actual byte encoding |
| SearchScroll with id `…+…/…==` | `+ / =` encoded in the query (`%2B %2F %3D`) |
| MultiSearch `/_msearch` | NDJSON body |
| Update id `wf-123:abc` | `:` in path (`%3A`) |
| Delete | `Content-Length` strip and an empty body |
| Search, first attempt dropped by the server | `JestClientRetryHandler` resends; the **re-signed** request must be valid and the entity repeatable |
| `executeAsync` Search | `HttpAsyncClient` path and its context target-host resolution |

**Results:**

```
VALID    NEW:search-agg-wildcard+type    POST   /txtrack-agg-*/attribute/_search  | signed=accept-encoding;content-type;host;x-amz-content-sha256;x-amz-date;x-amz-security-token
VALID    NEW:search-comma-indices        POST   /txtrack-event-2026-11-05%2Ctxtrack-event-2026-11-06%2Ctxtrack-event-2026-11-07/event/_search
VALID    NEW:search-size-scroll-params   POST   /txtrack-event-*/event/_search?size=10000&scroll=1m
VALID    NEW:search-utf8-body            POST   /txtrack-event-*/_search
VALID    NEW:scroll                      GET    /_search/scroll?scroll_id=DXF1ZXJ5QW5k%2BRmV0Y2g%2FBAAAAAAAAAD4Wb%3D%3D&scroll=1m
VALID    NEW:msearch                     POST   /_msearch
VALID    NEW:update                      POST   /txtrack-event-2026-11-05/event/wf-123%3Aabc/_update
VALID    NEW:delete                      DELETE /txtrack-event-2026-11-05/event/doc-1
(dropped) NEW:search-retry#dropped       POST   /txtrack-agg-*/attribute/_search
VALID    NEW:search-retry                POST   /txtrack-agg-*/attribute/_search
VALID    NEW:search-async                POST   /txtrack-agg-*/_search  | signed=content-type;host;x-amz-content-sha256;x-amz-date;x-amz-security-token
VALID    OLD:…  (same 10 scenarios, all VALID)  | signed=accept-encoding;content-type;host;user-agent;x-amz-date;x-amz-security-token

22 captured, 0 invalid
```

Negative control:

```
INVALID  TAMPER:path    (agg → event in path)       signature mismatch
INVALID  TAMPER:body    (one byte appended)          x-amz-content-sha256 does not match the body actually sent
INVALID  TAMPER:query   (size=10000 → 10001)          signature mismatch
3 captured, 3 invalid
```

**Observations from the wire capture:**

- The verifier accepted both the new and the old signer under the **same** canonicalisation rules, including the double-encoded `%2C` / `%3A` / `%2B` cases. Since the old signer works in production, the new signer will behave the same against the real domain.
- Differences in signed headers are expected and harmless. The new signer adds and signs `x-amz-content-sha256`, which Amazon OpenSearch accepts (`opensearch-java`'s `AwsSdk2Transport` does the same). It does not sign `user-agent`, which the v2 signer deliberately leaves out.
- The retry is re-signed correctly. Apache `RetryExec` restores the original headers before retrying, and the interceptor's `ByteArrayEntity` is repeatable, so the body is resent intact.
- On the async path, `HTTP_TARGET_HOST` is populated in the context, so relative request lines resolve.
- The session token (`X-Amz-Security-Token`) is present and signed. This matters on ECS/EC2 role credentials.

---

## 6. Findings and risks

### 6.1 Timeout regression (medium, fix before release)

| | Old (commons `JestClientBuilder`) | New (`TxTrackingJestModule`) |
|---|---|---|
| Read timeout | **15000 ms** (hardcoded; config ignored on the AWS-signing path) | `config.getReadTimeoutMillis()` → **3000 ms** default |
| Connect timeout | **7500 ms** (hardcoded) | `config.getConnTimeoutMillis()` → **3000 ms** default |

None of `tx-tracking/conf/{int,qa,cvt,prod}/config.yaml` set these, so `TxTrackingESConfiguration`'s defaults (3000) apply. Heavy calls such as the report export (`size=10000` + scroll), aggregations and MultiSearch can take longer than 3 s. `JestClientRetryHandler` retries **any** `IOException`, including `SocketTimeoutException` on POST searches, with 1 s/2 s/4 s back-off. One slow query therefore becomes up to four timed-out attempts taking about 19 s before failing.

**Fix:** add the following to every environment `config.yaml`. Alternatively, change the defaults in `TxTrackingESConfiguration`.

```yaml
txTrackingElasticSearch:
  endpointUrl: ...
  region: us-east-1
  service: es
  readTimeoutMillis: 15000
  connTimeoutMillis: 7500
```

### 6.2 Low / housekeeping

- **The `vc.inreach` jar is still on the classpath** via `commons`. It is never loaded; if it were, it would fail with `NoClassDefFoundError` because `com.amazonaws` is excluded. Xray and OWASP still scan it. Add an `<exclusion>` for `vc.inreach.aws:aws-signing-request-interceptor` on the `commons` dependency.
- **Startup no longer fails fast without credentials.** The old module called `getCredentials()` at startup to log the key id. The v2 provider resolves on the first request. This is acceptable, but worth knowing when diagnosing.
- **Web-identity (IRSA) credentials** need `software.amazon.awssdk:sts` on the classpath, and it is not there. The v1 chain didn't have `aws-java-sdk-sts` either, so behaviour is unchanged. Environment/system properties, profile, ECS container and EC2 instance-profile credentials all work.
- **The INT endpoint has a trailing `/`** (`…amazonaws.com/`). This is the same as before. Jest concatenates the URL, and the v2 signer normalises paths, so this case should be smoke-tested in INT.
- **No live AWS test was performed.** Everything above is offline. Do a smoke test in INT: workflow search, workflow details, a report export (scroll) and a reprocess (update).
- **Unit-test gap.** Consider adding a known-answer test: fixed `AwsV4FamilyHttpSigner.SIGNING_CLOCK`, compare against an AWS SigV4 test-suite vector. The current tests assert only that headers are present.

---

## 7. Implications for commons and recommendation

The constraint in `2026-05-27-aws-java-sdk-core-version-issue.md` **still holds for commons**:
- `vc.inreach` is still a dependency of `commons` and `cloud-sdk-api`;
- `JestModule` and `JestClientBuilder` still use v1;
- the legacy v1 `SNSModule`/`SQSModule`/`SQSReader`/`SQSWriter` remain in `cloud-sdk-aws`.

tx-tracking only steps around it.

Recommended next step (a non-breaking way to do in commons what tx-tracking did):

1. Move `AwsV4SigningRequestInterceptor` into `cloud-sdk-aws` (for example `cloudsdk.aws.elasticsearch`), with a known-answer unit test.
2. **Add** a `JestClientBuilder(HttpRequestInterceptor, String, HttpRequestRetryHandler, int connTimeout, int readTimeout)` constructor alongside the existing one. This is additive, so the strictly-additive rule is respected.
3. **Add** a v2 path to `JestModule` (for example `JestModule.v2(config)` or a flag), keeping the 15000/7500 defaults unless the caller overrides them. Migrate apps one at a time.
4. Once every consumer has moved: deprecate and remove the `vc.inreach` constructor, drop `aws-signing-request-interceptor`, then the `aws-java-sdk-core` pin (after SNS/SQS legacy modules are retired).
5. The long-term target is unchanged: `opensearch-java` + `AwsSdk2Transport`, which also retires the end-of-life Jest client.

The harness in Appendices A and B can serve as the regression check for steps 1–3: point it at the commons module instead of `TxTrackingJestModule`.

---

## 8. Commands reference (with syntax explained)

Conventions:
- All commands were run in **Git Bash** on Windows.
- The workspace layout is `~/projects/mercury-services-commons` (this repo) and `~/projects/mercury-services` (sibling).
- `$S` is a scratch directory for the harness. Any empty directory works.
- The tool resets the working directory between calls, so commands start with `cd`.

### 8.1 Finding the documentation

```bash
cd ~/projects
grep -rli --include=*.md -e "jest" -e "sdk v1" -e "aws-java-sdk" mercury-services-commons | grep -v target
```
- `grep -r`: recurse into directories. `-l`: print only the **names** of matching files. `-i`: case-insensitive.
- `--include=*.md`: search only Markdown files.
- `-e PATTERN` (repeatable): several patterns OR-ed together.
- `| grep -v target`: `-v` inverts the match, dropping paths under Maven `target/` build output.

```bash
grep -rn -i "jest\|AWSRequestSigning\|signing interceptor" mercury-services-commons --include=*.md | grep -v target | head -40
```
- `-n`: show line numbers. `\|`: alternation in basic regular expressions (GNU grep).
- `head -40`: limit to the first 40 lines of output.

```bash
grep -n -i "jest\|inreach\|sdk v1\|sdk-core\|v1 " \
  cloud-sdk-aws/docs/2026-05-27-aws-java-sdk-core-version-issue.md \
  docs/2026-10-28-aws-commons-xray-cve-analysis.md docs/2026-10-29-aws-commons-xray-cve-fix.md
cat cloud-sdk-aws/docs/2026-05-27-aws-java-sdk-core-version-issue.md
```
- Narrows the search to candidate docs, then prints the main one in full with `cat`.

```bash
grep -rn -i "inreach\|signing-request-interceptor\|AwsRequestSigningApacheInterceptor\|aws-request-signing\|Aws4Signer\|AwsV4HttpSigner" \
  --include=*.md mercury-services-commons mercury-services | grep -v "/target/" | cut -c1-260 | head -60
```
- Finds every document that discusses the signer choice. `cut -c1-260` truncates long lines to 260 characters for readability.

```bash
cd ~/projects/mercury-services
sed -n 10,50p docs/2026-0730-mercury-services-aws-pending.md
grep -n "^## \|^### " lambda/docs/2026-08-19-lambda-aws-refactor.md
sed -n 470,535p lambda/docs/2026-08-19-lambda-aws-refactor.md
sed -n 596,710p lambda/docs/2026-08-19-lambda-aws-refactor.md
sed -n 400,420p ../mercury-services-commons/cloud-sdk-api/docs/2026-07-23-sdk-gap-appway-aws-upgrade-design.md
```
- `sed -n A,Bp FILE`: `-n` suppresses default output; `A,Bp` prints only lines A to B.
- `grep -n "^## \|^### "`: lists Markdown headings with line numbers, an outline used to find the sections to read.

### 8.2 Finding Sumesh's change (git)

```bash
cd ~/projects/mercury-services
git fetch -q --all
git branch --show-current && git status -s | head
git log --all --since=2026-08-01 --format='%h %ad %an %d %s' --date=short -- tx-tracking | head -30
git log --all -i --author=sumesh --format='%h %ad %an %d %s' --date=short | head -20
```
- `git fetch -q --all`: update remote-tracking refs from every remote, quietly.
- `git branch --show-current`: prints the checked-out branch (`develop`). `git status -s`: short status.
- `git log --all`: all refs, not just HEAD. `--since=DATE`: commits after that date.
- `--format='%h %ad %an %d %s'`: abbreviated hash, author date, author name, ref decorations (branch/tag names), subject.
- `--date=short`: `YYYY-MM-DD`. `-- tx-tracking`: the `--` ends options; what follows is a **path filter**, so only commits touching `tx-tracking/` are shown.
- `-i --author=sumesh`: `--author` is a regex on the author field; `-i` makes it (and other regex filters) case-insensitive.

```bash
git show --stat a64be209d4
git show a64be209d4 -- '*.java' '*.xml' '*.yml' '*.yaml'
```
- `git show --stat COMMIT`: commit header plus per-file change counts.
- `git show COMMIT -- 'glob'…`: the full diff limited to the given path globs. Quote the globs so git expands them, not the shell.

### 8.3 Comparing with the commons implementation

```bash
cd ~/projects/mercury-services-commons
f=$(find . -name JestModule.java -path '*main*' | grep -v target); echo $f; cat $f
cat $(find . -name JestClientBuilder.java -path '*main*' | grep -v target)
cat $(find . -name JestClientRetryHandler.java -path '*main*' | grep -v target) | head -40
```
- `find . -name X -path '*main*'`: files named X whose path contains `main` (production code, not tests).
- `$( … )`: command substitution, which passes the found paths to `cat`.

```bash
for m in commons cloud-sdk-api cloud-sdk-aws; do
  echo "-- $m"; grep -rl "import com\.amazonaws\|import vc\.inreach" $m/src/main | sed 's#.*/java/##'
done
```
- Loops over the three published modules and lists main-code files that import v1 or `vc.inreach`.
- `\.` escapes the dot. `sed 's#.*/java/##'` strips everything up to `/java/` to show package paths. `#` is used as the `s` delimiter so the `/` characters need no escaping.

```bash
cat cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/config/ElasticSearchServiceConfig.java
find ../mercury-services/tx-tracking -name TxTrackingESConfiguration.java | xargs cat
```
- Reveals the 3000 ms timeout defaults. `xargs cat` turns `find`'s output lines into arguments for `cat`.

### 8.4 Scanning tx-tracking for v1 usage and wiring

```bash
cd ~/projects/mercury-services/tx-tracking
grep -rn "com\.amazonaws\|vc\.inreach" src pom.xml | head
grep -rhoE "^import com\.inttra\.mercury\.[a-zA-Z0-9_.]+" src/main | sort -u
grep -rn -A12 "txTrackingElasticSearch" --include=*.yml --include=*.yaml . | grep -v target | head -40
```
- `-h`: omit file names. `-o`: print only the matched part. `-E`: extended regex (so `+` and `[]` need no escaping). `sort -u`: sort and de-duplicate, giving the unique set of commons classes tx-tracking imports.
- `-A12`: print 12 lines **after** each match, which shows the full `txTrackingElasticSearch` YAML block.

```bash
cd ~/projects
grep -rn "SNSModule\|SQSModule\|SQSReader\|SQSWriter\|AwsRetryCondition\|AWSConstants\|cloudsdk.aws.module.JestModule\|elasticsearch.JestClientBuilder\|Reflections\|ClassGraph\|scanPackages\|resourcePackage" \
  mercury-services-commons/commons/src/main \
  mercury-services-commons/cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/{messaging,email,storage} \
  mercury-services/tx-tracking/src
```
- Checks whether anything tx-tracking reaches could load a v1 class directly or by classpath scanning. It returned no matches.
- `{messaging,email,storage}`: bash brace expansion, producing three paths.

```bash
grep -n "<parent>" -A5 mercury-services/tx-tracking/pom.xml
grep -rn "mercury.commons.version" mercury-services/pom.xml mercury-services/tx-tracking/pom.xml
```
- Confirms the parent version is `1.0`, so removing `<version>1.0</version>` changes nothing, and that commons `1.0.38-SNAPSHOT` is consumed.

```bash
cd ~/projects/mercury-services/tx-tracking
grep -rhoE "new (Search|SearchScroll|Get|Delete|DeleteByQuery|Count|Index|Bulk|Update|MultiSearch)[A-Za-z.]*Builder|\.setParameter\([^)]*\)|\.addIndex\([^)]*\)|executeAsync|Parameters\.[A-Z_]+" src/main \
  | sort | uniq -c | sort -rn
grep -rn -B2 -A6 "new Search.Builder\|new SearchScroll.Builder\|new Update.Builder\|new MultiSearch.Builder" src/main
sed -n 1,60p src/main/java/com/inttra/mercury/txtracking/service/IndexPatternBuilder.java
```
- Inventories the Jest actions and parameters tx-tracking really uses, to design realistic harness scenarios.
- `uniq -c` counts adjacent duplicates (hence the `sort` first); `sort -rn` orders numerically, highest first.
- `-B2 -A6`: 2 lines of context before and 6 after each match.

### 8.5 Maven

```bash
cd ~/projects/mercury-services/tx-tracking
mvn -o dependency:tree -Dincludes='com.amazonaws,vc.inreach.aws,software.amazon.awssdk:sts,software.amazon.awssdk:http-auth-aws,software.amazon.awssdk:auth,io.searchbox'
```
- `-o`: offline, using only `~/.m2`. `dependency:tree`: the `tree` goal of `maven-dependency-plugin` prints the resolved graph.
- `-Dincludes=…`: a comma-separated filter of `groupId[:artifactId[:type[:version]]]` patterns; only matching nodes and their path from the root are shown.
- An empty `com.amazonaws` branch proves v1 is gone. `sts` being absent shows web-identity credentials are unavailable.

```bash
mvn test -Djacoco.skip=true 2>&1 | grep -E "Tests run:|FAIL|ERROR|BUILD|Could not|missing" | tail -40
```
- `mvn test`: runs the lifecycle through the `test` phase (compile, then surefire). Online, so missing artifacts such as `mysql-connector-j` and `poi-ooxml` are downloaded.
- `-Djacoco.skip=true`: skips the JaCoCo agent for speed.
- `2>&1`: merges stderr into stdout so `grep` sees everything. `grep -E` keeps only result lines.

```bash
mvn -q dependency:build-classpath -Dmdep.includeScope=test -Dmdep.outputFile="$S/cp.txt"
tr ';' '\n' < "$S/cp.txt" | grep -iE "jest|httpasync|httpclient-4|httpcore|inreach|http-auth-aws|mail|activation|/sts/"
```
- `dependency:build-classpath`: writes the resolved classpath. `-Dmdep.includeScope=test`: include test-scope dependencies. `-Dmdep.outputFile`: write it to a file. `-q`: quiet.
- On Windows the separator is `;`. `tr ';' '\n'` splits it one jar per line for inspection.

### 8.6 Inspecting the `vc.inreach` library

```bash
cd ~/.m2/repository/vc/inreach/aws/aws-signing-request-interceptor/0.0.22
javap -cp aws-signing-request-interceptor-0.0.22.jar vc.inreach.aws.request.AWSSigner vc.inreach.aws.request.AWSSigningRequestInterceptor
unzip -p aws-signing-request-interceptor-0.0.22.jar META-INF/maven/vc.inreach.aws/aws-signing-request-interceptor/pom.xml \
  | grep -A3 -E "<artifactId>(aws-java-sdk-core|guava|httpcore)" | grep -E "artifactId|version"
```
- `javap -cp JAR CLASS…`: JDK class-file disassembler. Without `-c` it prints public signatures, which shows the constructor requires `com.amazonaws.auth.AWSCredentialsProvider`.
- `unzip -p JAR ENTRY`: extract one entry to stdout (`-p` means pipe) without unpacking. Used to read the library's embedded POM (aws-java-sdk-core 1.10.19, guava 18.0, httpcore 4.4.1).

### 8.7 Wire harness: compile, run, verify

```bash
S=/path/to/scratch/harness                                    # holds src/, verify_sigv4.py, cp.txt
T=~/projects/mercury-services/tx-tracking/target              # after `mvn test`: classes + test-classes
R=~/.m2/repository
CL=$(ls -d $R/commons-logging/commons-logging/*/ | tail -1); CLJ=$(ls $CL*.jar | grep -v sources | head -1)
V1="$R/com/amazonaws/aws-java-sdk-core/1.12.730/aws-java-sdk-core-1.12.730.jar;$CLJ;$R/joda-time/joda-time/2.12.7/joda-time-2.12.7.jar"
CP="$T/classes;$T/test-classes;$(cat $S/cp.txt);$V1"
```
- Builds the harness classpath: tx-tracking's compiled classes, its full test classpath, and **for the OLD control only** the v1 `aws-java-sdk-core` jar plus its runtime dependencies (commons-logging, joda-time). The v1 jar is needed only because the control path deliberately uses `vc.inreach`; the NEW path never touches it.
- `ls -d DIR/*/ | tail -1`: picks the newest-sorting version directory.

```bash
cd "$S"
javac -encoding UTF-8 -d out -cp "$CP" src/com/inttra/mercury/txtracking/config/elasticsearch/SigV4WireHarness.java
java -Dfile.encoding=UTF-8 -cp "out;$CP" com.inttra.mercury.txtracking.config.elasticsearch.SigV4WireHarness "$S/captured.json"
python -I verify_sigv4.py "$S/captured.json"
```
- `javac -encoding UTF-8`: the source contains non-ASCII test text. The Windows default (cp1252) fails with "unmappable character".
- `-d out`: output directory for `.class` files. `-cp`: compile classpath.
- The harness is in package `com.inttra.mercury.txtracking.config.elasticsearch`, the same package as the production classes, so it could reach package-private members if needed.
- `java -Dfile.encoding=UTF-8 -cp "out;$CP" MAIN ARG`: runs the harness. `ARG` is where the captured requests are written as JSON.
- `python -I`: isolated mode. It ignores `PYTHON*` environment variables and the user site-packages, and does not put the script directory on `sys.path`, so a stray local module cannot shadow the standard library.

```bash
python -I -c "
import json,base64
r=json.load(open('captured.json',encoding='utf-8'))
a=dict(r[0]); a['label']='TAMPER:path';  a['path']=a['path'].replace('agg','event')
b=dict(r[0]); b['label']='TAMPER:body';  b['body_b64']=base64.b64encode(base64.b64decode(b['body_b64'])+b' ').decode()
c=dict(r[2]); c['label']='TAMPER:query'; c['query']='size=10001&scroll=1m'
json.dump([a,b,c],open('tampered.json','w',encoding='utf-8'))"
python -I verify_sigv4.py tampered.json
```
- `python -c "…"`: runs inline code. It copies three valid captured requests, changes the path, body or query of each, and re-verifies. All three must report `INVALID`, which proves the verifier really checks signatures.

---

## Appendix A: `SigV4WireHarness.java`

```java
package com.inttra.mercury.txtracking.config.elasticsearch;

import com.inttra.mercury.cloudsdk.elasticsearch.JestClientBuilder;
import com.inttra.mercury.cloudsdk.elasticsearch.JestClientRetryHandler;
import com.inttra.mercury.txtracking.config.TxTrackingESConfiguration;
import com.sun.net.httpserver.HttpServer;
import io.searchbox.client.JestClient;
import io.searchbox.client.JestResult;
import io.searchbox.client.JestResultHandler;
import io.searchbox.core.*;
import io.searchbox.params.Parameters;

import java.io.FileWriter;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Sends tx-tracking-shaped Jest requests through (a) the real TxTrackingJestModule (SDK v2 signer) and
 * (b) the legacy vc.inreach (SDK v1) signer, capturing every request exactly as it arrives on the wire.
 */
public class SigV4WireHarness {

    static final String AK = "AKIDEXAMPLE", SK = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY", TOKEN = "IQoJb3JpZ2luX2VjEXAMPLETOKEN+/=";
    static volatile String label = "";
    static final AtomicBoolean dropNext = new AtomicBoolean(false);
    static final List<String> captured = Collections.synchronizedList(new ArrayList<>());

    public static void main(String[] args) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", ex -> {
            byte[] body = ex.getRequestBody().readAllBytes();
            if (dropNext.compareAndSet(true, false)) {          // simulate a dropped connection -> IOException -> retry
                captured.add(json(label + "#dropped", ex.getRequestMethod(), ex.getRequestURI().getRawPath(),
                        ex.getRequestURI().getRawQuery(), ex.getRequestHeaders(), body));
                ex.close();
                return;
            }
            captured.add(json(label, ex.getRequestMethod(), ex.getRequestURI().getRawPath(),
                    ex.getRequestURI().getRawQuery(), ex.getRequestHeaders(), body));
            String resp = ex.getRequestURI().getRawPath().endsWith("_msearch") ? "{\"responses\":[]}"
                    : "{\"took\":1,\"_scroll_id\":\"abc\",\"hits\":{\"total\":0,\"hits\":[]},\"_index\":\"i\",\"_id\":\"1\",\"result\":\"updated\"}";
            byte[] r = resp.getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(200, r.length);
            ex.getResponseBody().write(r);
            ex.close();
        });
        server.start();
        String endpoint = "http://127.0.0.1:" + server.getAddress().getPort();

        // ---- NEW: the actual TxTrackingJestModule code path, credentials resolved by SDK v2 DefaultCredentialsProvider
        System.setProperty("aws.accessKeyId", AK);
        System.setProperty("aws.secretAccessKey", SK);
        System.setProperty("aws.sessionToken", TOKEN);
        TxTrackingESConfiguration cfg = new TxTrackingESConfiguration();
        cfg.setEndpointUrl(endpoint);
        cfg.setRegion("us-east-1");
        cfg.setService("es");
        JestClient newClient = TxTrackingJestModule.newClient(cfg);
        runScenarios("NEW", newClient);
        newClient.close();

        // ---- OLD (control): legacy commons path = vc.inreach AWSSigner (SDK v1 credentials) via JestClientBuilder
        com.amazonaws.auth.AWSCredentialsProvider v1 = new com.amazonaws.auth.AWSStaticCredentialsProvider(
                new com.amazonaws.auth.BasicSessionCredentials(AK, SK, TOKEN));
        vc.inreach.aws.request.AWSSigner signer = new vc.inreach.aws.request.AWSSigner(v1, "us-east-1", "es",
                () -> LocalDateTime.now(ZoneOffset.UTC));
        JestClient oldClient = new JestClientBuilder(new vc.inreach.aws.request.AWSSigningRequestInterceptor(signer),
                endpoint, new JestClientRetryHandler(3)).getJestClient();
        runScenarios("OLD", oldClient);
        oldClient.close();

        server.stop(0);
        try (FileWriter w = new FileWriter(args[0], StandardCharsets.UTF_8)) {
            w.write("[\n" + String.join(",\n", captured) + "\n]\n");
        }
        System.out.println("captured " + captured.size() + " requests -> " + args[0]);
    }

    static void runScenarios(String who, JestClient c) throws Exception {
        String q = "{\"query\":{\"bool\":{\"must\":[{\"match\":{\"workflowId\":\"wf-1 2\"}}]}},\"size\":50}";
        String qUtf8 = "{\"query\":{\"match\":{\"name\":\"Müller – 東京\"}}}";

        exec(c, who + ":search-agg-wildcard+type", new Search.Builder(q).addIndex("txtrack-agg-*").addType("attribute").build());
        exec(c, who + ":search-comma-indices", new Search.Builder(q)
                .addIndex("txtrack-event-2026-11-05,txtrack-event-2026-11-06,txtrack-event-2026-11-07").addType("event").build());
        exec(c, who + ":search-size-scroll-params", new Search.Builder(q).addIndex("txtrack-event-*").addType("event")
                .setParameter(Parameters.SIZE, 10000).setParameter(Parameters.SCROLL, "1m").build());
        exec(c, who + ":search-utf8-body", new Search.Builder(qUtf8).addIndex("txtrack-event-*").build());
        exec(c, who + ":scroll", new SearchScroll.Builder("DXF1ZXJ5QW5k+RmV0Y2g/BAAAAAAAAAD4Wb==", "1m").build());
        exec(c, who + ":msearch", new MultiSearch.Builder(Arrays.asList(
                new Search.Builder(q).addIndex("txtrack-event-*").build(),
                new Search.Builder(q).addIndex("txtrack-agg-*").build())).build());
        exec(c, who + ":update", new Update.Builder("{\"doc\":{\"status\":\"SUCCESS\"}}")
                .index("txtrack-event-2026-11-05").type("event").id("wf-123:abc").build());
        exec(c, who + ":delete", new Delete.Builder("doc-1").index("txtrack-event-2026-11-05").type("event").build());

        // retry: first attempt is dropped by the server, JestClientRetryHandler resends -> must be re-signed correctly
        dropNext.set(true);
        exec(c, who + ":search-retry", new Search.Builder(q).addIndex("txtrack-agg-*").addType("attribute").build());

        // async transport (HttpAsyncClient) path
        label = who + ":search-async";
        CountDownLatch latch = new CountDownLatch(1);
        c.executeAsync(new Search.Builder(q).addIndex("txtrack-agg-*").build(), new JestResultHandler<JestResult>() {
            public void completed(JestResult r) { latch.countDown(); }
            public void failed(Exception e) { System.out.println(label + " FAILED " + e); latch.countDown(); }
        });
        latch.await(10, TimeUnit.SECONDS);
    }

    static void exec(JestClient c, String l, io.searchbox.action.Action<?> a) {
        label = l;
        try {
            c.execute(a);
        } catch (Exception e) {
            System.out.println(l + " client exception: " + e);
        }
    }

    static String json(String label, String method, String path, String query,
                       Map<String, List<String>> headers, byte[] body) {
        StringBuilder h = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, List<String>> e : headers.entrySet()) {
            for (String v : e.getValue()) {
                h.append(first ? "" : ",").append("\"").append(e.getKey()).append("\":").append(q(v));
                first = false;
                break;
            }
            if (e.getValue().size() > 1) { // keep all values, joined as the canonical form expects
                h.setLength(h.lastIndexOf(":") + 1);
                h.append(q(String.join(",", e.getValue())));
            }
        }
        h.append("}");
        return "{\"label\":" + q(label) + ",\"method\":" + q(method) + ",\"path\":" + q(path)
                + ",\"query\":" + (query == null ? "null" : q(query)) + ",\"headers\":" + h
                + ",\"body_b64\":" + q(Base64.getEncoder().encodeToString(body)) + "}";
    }

    static String q(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char ch : s.toCharArray()) {
            if (ch == '"' || ch == '\\') b.append('\\').append(ch);
            else if (ch < 0x20) b.append(String.format("\\u%04x", (int) ch));
            else b.append(ch);
        }
        return b.append('"').toString();
    }
}
```

## Appendix B: `verify_sigv4.py` (independent server-side SigV4 check, standard library only)

```python
"""Independent, server-side style SigV4 verification of captured wire requests (stdlib only)."""
import base64, hashlib, hmac, json, re, sys
from urllib.parse import quote, unquote

SECRET = "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"


def canonical_uri(raw_path):
    # AWS (non-S3): normalise, then URI-encode each segment of the path *as received* (i.e. double-encoding)
    segs, out = raw_path.split("/"), []
    for s in segs:
        if s == ".":
            continue
        if s == ".." and out:
            out.pop(); continue
        out.append(s)
    path = "/".join(out) or "/"
    return quote(path, safe="/-_.~")


def canonical_query(raw_query):
    if not raw_query:
        return ""
    pairs = []
    for part in raw_query.split("&"):
        k, _, v = part.partition("=")
        pairs.append((quote(unquote(k), safe="-_.~"), quote(unquote(v), safe="-_.~")))
    return "&".join(f"{k}={v}" for k, v in sorted(pairs))


def verify(r):
    h = {k.lower(): v for k, v in r["headers"].items()}
    auth = h.get("authorization")
    if not auth:
        return False, "NO Authorization header"
    m = re.match(r"AWS4-HMAC-SHA256 Credential=([^/]+)/(\d{8})/([^/]+)/([^/]+)/aws4_request, ?"
                 r"SignedHeaders=([^,]+), ?Signature=([0-9a-f]+)", auth)
    if not m:
        return False, "unparseable Authorization: " + auth
    ak, date, region, service, signed, sig = m.groups()
    body = base64.b64decode(r["body_b64"])
    payload_hash = hashlib.sha256(body).hexdigest()
    notes = []
    if "x-amz-content-sha256" in h and h["x-amz-content-sha256"] != payload_hash:
        return False, "x-amz-content-sha256 does not match the body actually sent"
    names = signed.split(";")
    if "host" not in names:
        return False, "host not signed"
    missing = [n for n in names if n not in h]
    if missing:
        return False, f"signed header(s) not present on the wire: {missing}"
    canon_headers = "".join(f"{n}:{' '.join(h[n].strip().split())}\n" for n in names)
    creq = "\n".join([r["method"], canonical_uri(r["path"]), canonical_query(r["query"]),
                      canon_headers, signed, payload_hash])
    amz_date = h["x-amz-date"]
    scope = f"{date}/{region}/{service}/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(creq.encode()).hexdigest()])
    k = ("AWS4" + SECRET).encode()
    for p in (date, region, service, "aws4_request"):
        k = hmac.new(k, p.encode(), hashlib.sha256).digest()
    expect = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    if "x-amz-security-token" not in h:
        notes.append("NO session token header")
    ok = expect == sig
    return ok, (f"signed={signed}" + ("" if ok else f"  creq=\n{creq}") + (" " + ";".join(notes) if notes else ""))


reqs = json.load(open(sys.argv[1], encoding="utf-8"))
fails = 0
for r in reqs:
    if r["label"].endswith("#dropped"):
        print(f"{'(dropped)':8} {r['label']:38} {r['method']:6} {r['path']}{'?' + r['query'] if r['query'] else ''}")
        continue
    ok, info = verify(r)
    fails += 0 if ok else 1
    print(f"{'VALID' if ok else 'INVALID':8} {r['label']:38} {r['method']:6} "
          f"{r['path']}{'?' + r['query'] if r['query'] else ''}  | {info}")
print(f"\n{len(reqs)} captured, {fails} invalid")
```

**Key algorithm points in the verifier**, so it can be reviewed against the AWS SigV4 specification:
- **Canonical URI:** the raw path as received, URI-encoded again. This is the "double encoding" rule for every service except S3; Amazon OpenSearch is `es`, so double encoding applies.
- **Canonical query:** each name and value is decoded, re-encoded per RFC 3986 (unreserved `A-Z a-z 0-9 - _ . ~`), sorted by name then value, and joined with `&`.
- **Canonical headers:** exactly the `SignedHeaders` list, lower-case names, trimmed values with runs of spaces collapsed, each line ending in `\n`.
- **Payload hash:** SHA-256 hex of the bytes that actually arrived, so the payload hash is checked against the real body rather than trusted from the client.
- **Signing key:** `HMAC(HMAC(HMAC(HMAC("AWS4"+secret, date), region), service), "aws4_request")`, then HMAC over the string-to-sign.
