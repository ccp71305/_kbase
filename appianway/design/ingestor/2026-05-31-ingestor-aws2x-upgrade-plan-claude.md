# `ingestor` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.appian-way:ingestor:1.0` · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Guice **7.0.0**, Jackson **2.21.0**).
> Master references (do not duplicate): [shared plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [shared DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6. This module plan only states the **ingestor-specific** deltas.

---

## 0. What this document changes vs. the Copilot plan (critical review)

I reviewed [`2026-05-31-ingestor-aws2x-upgrade-plan-copilot.md`](2026-05-31-ingestor-aws2x-upgrade-plan-copilot.md) and [`...-DESIGN.md`](2026-05-31-ingestor-aws2x-upgrade-DESIGN.md) against the **actual** ingestor source. The Copilot inventory is mostly right (standard SQS + S3 consumer, no SNS) but it (a) treats Elasticsearch/Jest as a non-AWS concern that needs no migration, when in fact ingestor **AWS-signs** its Jest requests with **v1 `DefaultAWSCredentialsProviderChain` + `AWSSigner`** ([`JestModule.java:3,15,37`](../src/main/java/com/inttra/mercury/ingestor/modules/JestModule.java)) — that *is* an AWS-credential v1 dependency that must move; and (b) lists module-specific cloud-sdk gaps G1/G6/G7, which the master review has already de-scoped to **no cloud-sdk change** (appianway-local).

| Copilot position | Evidence | This plan |
|---|---|---|
| Jest/Elasticsearch is non-AWS-SDK and **out of scope** | `JestModule` builds an `AWSSigner` from **v1** `com.amazonaws.auth.DefaultAWSCredentialsProviderChain` ([`JestModule.java:37`](../src/main/java/com/inttra/mercury/ingestor/modules/JestModule.java)) — a v1 credential dependency | **In scope (credential path only).** Migrate the AWS-signing path; **keep the Jest client** (OpenSearch-SDK migration is a separate future effort). Two routes — see §11. |
| Module-specific gaps **G1** (concurrent listener), **G6** (config), **G7** (health) | Master review de-scoped all three to appianway-local with no cloud-sdk change | **No module-specific cloud-sdk gap.** ingestor relies only on shared + existing cloud-sdk Jest support. |
| `Message` DTO → `MessageRef` | shared exposes the element type as `QueueMessage<String>`, not a `MessageRef` | **`Message` → `QueueMessage<String>`**, flowing through ingestor's retained `Task`/`AsyncDispatcher`/`IngestorTask` chain. |
| "Remove `aws-java-sdk-{sqs,s3}`" | `ingestor/pom.xml` declares **only** `aws-java-sdk-sqs` ([`pom.xml:45-50`](../pom.xml)); S3 arrives transitively via `shared` | **Drop `aws-java-sdk-sqs`** here; the v1 S3 drop happens in `shared`. |
| S-G2 (S3 metadata write overloads) implied for S3 consumers | ingestor S3 use is **read-only** (`getContent`, [`ErrorTransformer.java:43`](../src/main/java/com/inttra/mercury/ingestor/transformer/ErrorTransformer.java)) | **S-G2 does NOT apply to ingestor.** No write/copy with metadata. |

Net effect: ingestor consumes cloud-sdk **as a normal client** (SQS + S3-read via shared) plus the **existing** cloud-sdk Jest/Elasticsearch support for the AWS-signed indexing path. **Zero module-specific cloud-sdk change** ⇒ provably no impact to mercury-services.

---

## 1. Executive summary

`ingestor` is the event indexer into Elasticsearch (despite the name, **not** a first-stage receiver). Its AWS surface is:
1. **SQS** consume (`amazonSQSForListener`) + send (`amazonSQSForSender`) via `shared` ([`ExternalServicesModule.java:38-41`](../src/main/java/com/inttra/mercury/ingestor/modules/ExternalServicesModule.java));
2. **S3 read** via `shared` `WorkspaceService.getContent` ([`ErrorTransformer.java:43`](../src/main/java/com/inttra/mercury/ingestor/transformer/ErrorTransformer.java));
3. **AWS-signed Jest/Elasticsearch** requests, signed with **v1** `DefaultAWSCredentialsProviderChain` + a `vc.inreach.aws.request.AWSSigner` interceptor ([`JestModule.java`](../src/main/java/com/inttra/mercury/ingestor/modules/JestModule.java)).

Per the master directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§7). ingestor is a **light** consumer (no SNS, no DynamoDB, no S3 writes), so the only ingestor-specific work beyond the standard rebind is the **Jest AWS-signing credential path** (§11).

---

## 2. Current state — AWS v1 inventory (verified, file:line)

| Area | Symbol / call | Location |
|---|---|---|
| SQS listener client | `bind(AmazonSQS) @Named("amazonSQSForListener")` via `AWSClientConfiguration.sqs_listener` | [`ExternalServicesModule.java:38-39`](../src/main/java/com/inttra/mercury/ingestor/modules/ExternalServicesModule.java) |
| SQS sender client | `bind(AmazonSQS) @Named("amazonSQSForSender")` via `AWSClientConfiguration.sqs_sender` | [`ExternalServicesModule.java:40-41`](../src/main/java/com/inttra/mercury/ingestor/modules/ExternalServicesModule.java) |
| S3 client | `bind(AmazonS3)` via `AWSClientConfiguration.s3_read_put_copy` | [`ExternalServicesModule.java:42-43`](../src/main/java/com/inttra/mercury/ingestor/modules/ExternalServicesModule.java) |
| S3 read (only use) | `s3WorkspaceService.getContent(bucket, fileName)` | [`ErrorTransformer.java:43`](../src/main/java/com/inttra/mercury/ingestor/transformer/ErrorTransformer.java) |
| v1 SQS DTO leak | `com.amazonaws.services.sqs.model.Message` in task | [`IngestorTask.java:3,39,45,79`](../src/main/java/com/inttra/mercury/ingestor/task/IngestorTask.java), `Task.java`, `AsyncDispatcher.java`, `ErrorHandler.java` |
| SQS delete | `sqs.deleteMessage(queueUrl, msg.getReceiptHandle())` | [`IngestorTask.java:92`](../src/main/java/com/inttra/mercury/ingestor/task/IngestorTask.java) |
| **Jest AWS signing (v1 creds)** | `new DefaultAWSCredentialsProviderChain()` → `new AWSSigner(provider, region, service, clock)` | [`JestModule.java:3,15,37-40`](../src/main/java/com/inttra/mercury/ingestor/modules/JestModule.java) |
| Jest client build | `JestClientFactory` + `AWSSigningRequestInterceptor(awsSigner)` | [`JestModule.java:54-74`](../src/main/java/com/inttra/mercury/ingestor/modules/JestModule.java) |
| pom v1 dep | `com.amazonaws:aws-java-sdk-sqs:${aws-java-sdk.version}` (only v1 dep; **no** `aws-java-sdk-s3`) | [`pom.xml:45-50`](../pom.xml) |
| Jest/signer deps | `io.searchbox:jest:6.3.1`, `vc.inreach.aws:aws-signing-request-interceptor:0.0.16` | [`pom.xml:66-81`](../pom.xml) |

Concurrency: ingestor runs **N** `SQSListener` threads (`configuration.getListenerThreads()`) feeding one shared `AsyncDispatcher`/`IngestorTask` ([`IngestorModule.java:80-95`](../src/main/java/com/inttra/mercury/ingestor/modules/IngestorModule.java)) — this is appianway-owned orchestration and is **kept**.

---

## 3. Findings

- **S3 is read-only** in ingestor — only `getContent` ([`ErrorTransformer.java:43`](../src/main/java/com/inttra/mercury/ingestor/transformer/ErrorTransformer.java)). **S-G2 (metadata write overloads) is irrelevant here**; ingestor consumes `StorageClient`'s existing read API as-is.
- The Jest path's only AWS coupling is **credential resolution + request signing**. The `DefaultAWSCredentialsProviderChain` honors the same `AWS_*`/IAM environment as v2's `DefaultCredentialsProvider`, so behavior is preserved across either migration route (§11).
- `IngestorTask` reads `message.getBody()` and `message.getReceiptHandle()` ([`IngestorTask.java:40,92`](../src/main/java/com/inttra/mercury/ingestor/task/IngestorTask.java)) — both available on `QueueMessage<String>` (`getPayload()`/`getReceiptHandle()` per master plan §3). No attribute round-trip is needed (ingestor does not use `FAILED_ATTEMPTS`).
- ingestor has **no SNS, no DynamoDB, no SES, no S3 writes** — the smallest AWS surface among the migrated modules.

---

## 4. Option A — keep `ingestor` on DW4, rebind to cloud-sdk

Rebind `ExternalServicesModule` from v1 `AmazonSQS`/`AmazonS3` to shared's cloud-sdk-backed `SQSClient`/`SQSListenerClient`/`WorkspaceService`; swap the `Message` element type to `QueueMessage<String>` through the retained task chain; migrate the Jest signer to v2 credentials/signing (§11) **or** adopt cloud-sdk's `JestClientBuilder`/`JestModule`. Keep Dropwizard 4 / JUnit 4.

- **Pros:** smallest blast radius; no framework jump; reversible.
- **Cons:** keeps appianway's DW4 base (deferred convergence). Same cloud-sdk consumption as Option B.
- **Effort:** Low. **Risk:** Low.

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A, plus move ingestor onto `commons` `InttraServer` (DW5) + the appianway composed `ServerCommand` (master plan §10), with new tests in JUnit 5. ingestor keeps its multi-`SQSListener` + `AsyncDispatcher`/`IngestorTask` orchestration.

- **Pros:** platform convergence; shared Jackson/Jetty/CVE cadence; JUnit 5.
- **Cons:** DW4→5 jump (paid once at `shared`; here it is mostly inherited).
- **Effort:** Low–Medium (depends on shared landing first). **Risk:** Low–Medium.

## 6. Comparison

| Criterion | Option A (DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 (SQS/S3/Jest creds) | ✅ | ✅ |
| Required cloud-sdk change | **None** | **None** |
| Impact on mercury-services | None | None |
| Effort | Low | Low–Medium |
| Risk | Low | Low–Medium |
| Framework churn | None | DW4→5 (inherited from shared) |
| Consistency w/ mercury-services | AWS layer only | Full |

## 7. Recommendation

**Option B** per the program directive, consuming cloud-sdk as a normal client with **no module-specific cloud-sdk change**. ingestor is a good early-wave candidate after `shared` + `functional-testing` because of its small surface (no SNS/DynamoDB/SES/S3-write). The only genuinely module-specific task is the **Jest AWS-signing credential migration** (§11), which is self-contained in `JestModule`.

## 8. Peer review note

Self-review against source corrected three Copilot items: (1) the Jest path **is** AWS-credential-coupled (v1 `DefaultAWSCredentialsProviderChain`) and must migrate, though the Jest client/protocol stays; (2) the SQS element type is `QueueMessage<String>`, not a `MessageRef`; (3) `aws-java-sdk-s3` is **not** declared in `ingestor/pom.xml` (S3 is transitive via `shared`), so only `aws-java-sdk-sqs` is dropped here. Module-specific gaps G1/G6/G7 are de-scoped to appianway-local (master §0/§11).

## 9. Open questions / sequencing

- Migrate **after** `shared` + `functional-testing`; ingestor can go in the **early wave** (`mvn -pl ingestor -am verify`).
- **Jest decision (§11):** confirm whether cloud-sdk's `JestClientBuilder`/`JestModule` exposes the same `region`/`service`/endpoint knobs ingestor sets ([`JestModule.java:38-40,69-72`](../src/main/java/com/inttra/mercury/ingestor/modules/JestModule.java)). If yes → adopt it (delete local `JestModule` signing). If not → keep the local `JestClientFactory` but swap the credential provider/signer to AWS SDK v2 (local change, no cloud-sdk change).
- Dev-run parity check: v2 `DefaultCredentialsProvider` resolves the same IAM/`AWS_*` env the v1 chain used for ES signing.

## 10. Configuration changes

Defers to master plan [§10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md). ingestor-specific: `ElasticSearchConfig` (`region`, `service`, `endpointUrl`) is unchanged — it continues to drive whichever signer route is chosen (§11). SQS/S3 per-role config (`AWSClientConfiguration.sqs_listener`/`sqs_sender`/`s3_read_put_copy`) maps to cloud-sdk-aws config via `shared`. `${PROFILE}`/`${ENV}` resource-name expansion unchanged.

## 11. cloud-sdk gaps — ingestor

**No module-specific cloud-sdk change.** ingestor relies on `shared` + the **existing** cloud-sdk Jest/Elasticsearch support (master plan §11 "Coverage already present"). Two acceptable routes for the AWS-signing path, **both requiring no cloud-sdk change**:

1. **Adopt cloud-sdk `JestClientBuilder`/`JestModule`** (preferred): cloud-sdk-aws already provides AWS-signed Jest using AWS SDK **v2** (`software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider` + v2 signing). Delete ingestor's local `AWSSigner`/`AWSSigningRequestInterceptor` wiring and consume cloud-sdk's Jest client, passing the existing `region`/`service`/`endpointUrl` from `ElasticSearchConfig`. Drop `vc.inreach.aws:aws-signing-request-interceptor`.
2. **Local v2 signer** (fallback, only if cloud-sdk's Jest builder lacks a needed knob): keep ingestor's `JestClientFactory` but replace `com.amazonaws.auth.DefaultAWSCredentialsProviderChain` with `software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider` and the v1 `AWSSigner` interceptor with a v2 request-signing interceptor. Still entirely local — **no cloud-sdk change**.

- **S-G2:** not applicable (ingestor never writes/copies S3 with metadata — read-only `getContent`).
- The OpenSearch-SDK migration (replacing Jest itself) is a **separate, future** effort — out of scope here.
