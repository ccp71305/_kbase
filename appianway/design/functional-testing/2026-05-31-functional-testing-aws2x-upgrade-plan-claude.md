# `functional-testing` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.test:functional-testing:1.0` (the shared functional-test SDK; **test scope in every appianway service**) · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Jackson **2.21.0**).
> References the **MASTER**: [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) (§0, §8, §10, §11) and [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) (§6 specs).
> **This is the lockstep module:** it must be reworked **immediately after `shared` and BEFORE any downstream service**, or no downstream service functional test compiles.

---

## 0. What this document changes vs. the Copilot plan (critical review)

I reviewed [`2026-05-31-functional-testing-aws2x-upgrade-plan-copilot.md`](2026-05-31-functional-testing-aws2x-upgrade-plan-copilot.md) and [`…-DESIGN.md`](2026-05-31-functional-testing-aws2x-upgrade-DESIGN.md) against the actual fakes, adaptors and assertion DSL.

| Copilot position | Evidence (this review) | This plan |
|---|---|---|
| "Fakes implement the **full v1 interfaces** (`AmazonS3Adaptor implements AmazonS3`, `AmazonSESAdaptor implements AmazonSimpleEmailService`); rework them to implement `cloud-sdk-api` interfaces (**F1**)." | Confirmed. [`AmazonSQSAdaptor implements AmazonSQS`](../src/main/java/com/inttra/mercury/test/aws/AmazonSQSAdaptor.java) (≈60 stubbed methods); `AmazonS3Adaptor`/`AmazonSESAdaptor`/`AmazonDynamoDBAdaptor` similarly. Impls back them with in-memory maps ([`FakeS3Impl`](../src/main/java/com/inttra/mercury/test/aws/impl/FakeS3Impl.java), [`FakeSQSImpl`](../src/main/java/com/inttra/mercury/test/aws/impl/FakeSQSImpl.java)). | **Agree with F1**, but with a sharper boundary analysis (below) and an explicit DSL-stability contract. |
| Recommends **"Option A + keep JUnit 4, no Jupiter."** | The program directive is **Option B + DW5 + JUnit 5 new fixtures (Vintage during transition)**; the Copilot body still recommends Option A and "JUnit 4 retained / No Jupiter". | **Option B.** Keep the JUnit-4 lifecycle (`IntegrationTestRule`/`FunctionalTestBase`) on **Vintage** during transition; write **new fixtures in JUnit 5**. |
| Treats the rework as "mostly deletion; downstream tests compile unchanged." | Partly true, but **understates the unavoidable test-API ripples**: the `Fake*` interfaces and the SNS assertion path **leak v1 types into the DSL surface** (`FakeSQS.getMessages(...)→List<v1.Message>` [`FakeSQS.java:18,24`](../src/main/java/com/inttra/mercury/test/aws/FakeSQS.java); `FakeS3.putObject(...)` v1 return/`ObjectMetadata` [`FakeS3.java:14-16,22`](../src/main/java/com/inttra/mercury/test/aws/FakeS3.java); `FakeSES.getEmailsSent→List<v1.SendEmailRequest>` [`FakeSES.java:9`](../src/main/java/com/inttra/mercury/test/aws/FakeSES.java); `FakeDynamoDB.putItem→v1.PutItemResult` [`FakeDynamoDB.java:8`](../src/main/java/com/inttra/mercury/test/aws/FakeDynamoDB.java); `SnsAssert extends AbstractAssert<…, ArgumentCaptor<PublishRequest>>` [`SnsAssert.java:17`](../src/main/java/com/inttra/mercury/test/assertions/SnsAssert.java)). | **Call out the specific test-API changes + a migration note** (§9, DESIGN §6/§10). The internal-store-backed assertions (`S3Assert`, `SqsAssert` body, `DynamoDBAssert`) survive unchanged; the v1-typed surfaces must change. |
| Silent on **SNS becoming a real fake**. | Today SNS is **not a fake** — `FunctionalTestBase` mocks `AmazonSNS` and captures `PublishRequest` via Mockito ([`FunctionalTestBase.java:38,86-90`](../src/main/java/com/inttra/mercury/test/FunctionalTestBase.java)); `SnsAssert` asserts over the captor. Under cloud-sdk this becomes `InMemoryNotificationService` with a published-message store. | **Replace the SNS Mockito-captor pattern with an `InMemoryNotificationService`**; re-point `SnsAssert` to its store. This is the one DSL signature that must change for SNS. |
| Silent on **`functional-testing` declaring no AWS deps**. | Confirmed: [`pom.xml`](../pom.xml) declares **no `com.amazonaws`** — the v1 types come **transitively from `mercury-shared:1.0`**. So when `shared` drops v1, the fakes stop compiling automatically; this module must add `cloud-sdk-api` explicitly. | **Add `cloud-sdk-api` (compile) + `cloud-sdk-aws`/`dynamo-integration-test` as needed**; rely on `shared` to stop exporting v1. |
| Silent on **`IntegrationTestSupport` coupling to `shared`'s config command**. | [`IntegrationTestSupport.java:4,59`](../src/main/java/com/inttra/mercury/test/IntegrationTestSupport.java) constructs `shared`'s `ConfigProcessingServerCommand` directly and is on DW4 (`io.dropwizard.core.*`). When `shared` moves to the composed appianway `ServerCommand` (master §10) + DW5, this harness must follow. | **Lockstep extends to the config-command + DW5 harness**, not just the fakes. |

**Net:** F1 is correct, but the rework is **lockstep + test-API surgery**, not pure deletion. The fakes become small in-memory `cloud-sdk-api` implementations; the AssertJ store-backed DSL is preserved where it never touched v1 types, and the **v1-typed DSL surfaces (SQS message lists, S3 put, SES, DynamoDB put, SNS captor) change with a documented migration note.** This is **appianway-internal test code → zero impact to mercury-services** (which have their own, separate test patterns).

---

## 1. Executive summary
`functional-testing` is the shared in-memory AWS-fake harness consumed at **test scope by every appianway service**. Today its fakes emulate the **AWS v1 client interfaces** (`AmazonS3`/`AmazonSQS`/`AmazonSimpleEmailService`/`AmazonDynamoDB` via `Amazon*Adaptor` stubs), wired into Guice by `FunctionalTestBase`, with an AssertJ DSL (`S3Assert`/`SqsAssert`/`SnsAssert`/`DynamoDBAssert`) and a JUnit-4 lifecycle (`IntegrationTestRule`/`IntegrationTestSupport`). When `shared` stops exporting v1 types and routes AWS through `cloud-sdk-api`, the fakes must be **re-pointed to implement the `cloud-sdk-api` interfaces** (`StorageClient`, `MessagingClient<String>`→`QueueMessage<String>`, `NotificationService`, `EmailService`, and a DynamoDB `DatabaseRepository`/`dynamo-integration-test`) so every downstream service's functional test still compiles and passes. There is **no cloud-sdk library gap**: this module **consumes `cloud-sdk-api` as a client and builds its own in-memory implementations**. Recommendation: **Option B + F1**, in lockstep with `shared`, before service rollouts, preserving the AssertJ DSL surface wherever it does not currently leak v1 types.

## 2. Current state — AWS v1 inventory (file:line)
v1 types reach this module **transitively via `mercury-shared:1.0`** ([pom.xml:27-31](../pom.xml) — no direct `com.amazonaws` declaration).

**Adaptors (full v1 client stubs):**
- [`aws/AmazonSQSAdaptor.java`](../src/main/java/com/inttra/mercury/test/aws/AmazonSQSAdaptor.java) `implements com.amazonaws.services.sqs.AmazonSQS` — ~60 stub methods (lines 63-293).
- [`aws/AmazonS3Adaptor.java`](../src/main/java/com/inttra/mercury/test/aws/AmazonS3Adaptor.java) `implements com.amazonaws.services.s3.AmazonS3`.
- [`aws/AmazonSESAdaptor.java`](../src/main/java/com/inttra/mercury/test/aws/AmazonSESAdaptor.java) `implements com.amazonaws.services.simpleemail.AmazonSimpleEmailService`.
- [`aws/AmazonDynamoDBAdaptor.java`](../src/main/java/com/inttra/mercury/test/aws/AmazonDynamoDBAdaptor.java) `implements com.amazonaws.services.dynamodbv2.AmazonDynamoDB`.

**Fake interfaces (DSL-facing; some leak v1 types):**
- [`aws/FakeSQS.java`](../src/main/java/com/inttra/mercury/test/aws/FakeSQS.java) — `getMessages(url)→List<v1.Message>` (line 18), `getHistory(url)→List<v1.Message>` (line 24); the rest are `String`/`int`/`boolean`.
- [`aws/FakeS3.java`](../src/main/java/com/inttra/mercury/test/aws/FakeS3.java) — `putObject(...)→v1.PutObjectResult` (lines 14-16), `getObjectMetadata(GetObjectMetadataRequest)→ObjectMetadata` (line 22).
- [`aws/FakeSES.java`](../src/main/java/com/inttra/mercury/test/aws/FakeSES.java) — `getEmailsSent(recipient)→List<v1.SendEmailRequest>` (line 9).
- [`aws/FakeDynamoDB.java`](../src/main/java/com/inttra/mercury/test/aws/FakeDynamoDB.java) — `putItem(...)→v1.PutItemResult` (line 8).

**Fake impls (in-memory backing — the valuable, reusable part):**
- [`aws/impl/FakeSQSImpl.java`](../src/main/java/com/inttra/mercury/test/aws/impl/FakeSQSImpl.java) — `BlockingQueue<Message>` per URL, sent/deletion history, `SQS_HOST` URL normalization, `FAILED_ATTEMPTS`-carrying `MessageAttributes`.
- [`aws/impl/FakeS3Impl.java`](../src/main/java/com/inttra/mercury/test/aws/impl/FakeS3Impl.java) — `Map<bucket,Map<key,content>>`; put/get/copy/list; `SdkClientException` on read error (line 71).
- [`aws/impl/FakeSESImpl.java`](../src/main/java/com/inttra/mercury/test/aws/impl/FakeSESImpl.java) — `Map<recipient,List<SendEmailRequest>>`.
- [`aws/impl/FakeDynamoDBImpl.java`](../src/main/java/com/inttra/mercury/test/aws/impl/FakeDynamoDBImpl.java) — `Map<table,List<eventId>>`; reads `item.get("eventId").getS()` (line 48).
- [`aws/impl/ReadOnlySQS.java`](../src/main/java/com/inttra/mercury/test/aws/impl/ReadOnlySQS.java), [`aws/impl/ReadOnlyS3Workspace.java`](../src/main/java/com/inttra/mercury/test/aws/impl/ReadOnlyS3Workspace.java).

**Wiring & DSL:**
- [`FunctionalTestBase.java`](../src/main/java/com/inttra/mercury/test/FunctionalTestBase.java) — Guice binds `AmazonS3`/`AmazonSQS`(named for-listener/for-sender)/`AmazonSNS`(Mockito mock) to the fakes (lines 66-69); SNS via `ArgumentCaptor<PublishRequest>` (lines 38,86-90); JUnit-4 `@Rule`/`@Before` (lines 40,47).
- [`IntegrationTestRule.java`](../src/main/java/com/inttra/mercury/test/IntegrationTestRule.java) `extends ExternalResource` (JUnit-4 rule) + Awaitility.
- [`IntegrationTestSupport.java`](../src/main/java/com/inttra/mercury/test/IntegrationTestSupport.java) — `extends DropwizardTestSupport` (DW4 `io.dropwizard.core.*`), constructs `shared`'s `ConfigProcessingServerCommand` (lines 4,59).
- Assertions: [`S3Assert`](../src/main/java/com/inttra/mercury/test/assertions/S3Assert.java) (store-backed, **v1-free**), [`SqsAssert`](../src/main/java/com/inttra/mercury/test/assertions/SqsAssert.java) (store-backed via `getMessages(url, MetaData.class)`, **v1-free at the assertion body**), [`SnsAssert`](../src/main/java/com/inttra/mercury/test/assertions/SnsAssert.java) (**v1 `ArgumentCaptor<PublishRequest>`**), [`DynamoDBAssert`](../src/main/java/com/inttra/mercury/test/assertions/DynamoDBAssert.java), [`ResourceAssertions`](../src/main/java/com/inttra/mercury/test/assertions/ResourceAssertions.java) (overloads keyed on `FakeS3`/`FakeSQS`/`FakeDynamoDB`/`ArgumentCaptor<PublishRequest>`).

**Build:** DW `4.0.16`, JUnit `4.13.2`, Mockito `2.8.9`, AssertJ `3.19.0`, Awaitility `3.0.0`, Java 17 ([pom.xml:10-24](../pom.xml)).

## 3. Findings
- The **in-memory stores and the store-backed AssertJ assertions are the durable asset**; they are largely v1-type-free and survive the migration.
- The **giant v1 adaptor stubs collapse to a few methods** when re-pointed to `cloud-sdk-api` (`StorageClient`, `MessagingClient<String>`, `NotificationService`, `EmailService` are small interfaces).
- **SNS is currently a Mockito mock + captor, not a fake** — under cloud-sdk it becomes a real `InMemoryNotificationService`, and `SnsAssert` re-points to that store. This is a genuine DSL change.
- **SQS attribute round-trip:** `FakeSQSImpl` already preserves `MessageAttributes`; `QueueMessage<String>.getAttributes():Map<String,String>` cleanly carries the `FAILED_ATTEMPTS` retry counter (master §3 — confirmed compatible).
- **DynamoDB:** the current fake is a trivial `Map<table,List<eventId>>`. Two paths: a tiny in-memory `DatabaseRepository<T,ID>` fake, or adopt **`dynamo-integration-test`** (DynamoDB-Local, JUnit 5) for the watermill/transformer Dynamo paths. Recommend `dynamo-integration-test` for realistic coverage, keeping the trivial fake only where a service test just counts puts.
- **No direct AWS dependency in the POM** — v1 leaks in via `mercury-shared`. This module must add `cloud-sdk-api` explicitly once `shared` stops exporting v1.
- **The DW4/JUnit-4 harness (`IntegrationTestSupport`/`IntegrationTestRule`/`FunctionalTestBase`) is itself coupled to `shared`'s DW4 base and config command** — lockstep covers the harness, not just the fakes.

## 4. Option A — keep `shared`/DW4 (program-wide fallback)
Re-point the fakes to `cloud-sdk-api` (F1) while keeping the DW4 base and JUnit-4 lifecycle. Same fake redesign as Option B minus the DW5/Jupiter move. Lower churn; documented fallback. Shares the identical fake contract with Option B.

## 5. Option B — adopt commons + cloud-sdk on DW5 (directed default)
Re-point all fakes to `cloud-sdk-api` interfaces (F1); move the harness to **DW5** (`IntegrationTestSupport`/`IntegrationTestRule` on DW5 + the composed appianway `ServerCommand` from master §10); write **new fixtures in JUnit 5 (Jupiter)** while existing JUnit-4 fixtures run via **Vintage** during transition. The fakes consume `cloud-sdk-api` as a client and build their own in-memory implementations.

## 6. Comparison
| Criterion | Option A | Option B |
|---|---|---|
| Fakes off v1 (F1) | ✅ | ✅ |
| Fake contract | identical | identical |
| Framework | DW4 / JUnit 4 | DW5 / JUnit 5 (+ Vintage) |
| Lockstep with `shared` | ✅ | ✅ |
| cloud-sdk library change | **none** | **none** |
| Impact on mercury-services | none (appianway-internal) | none (appianway-internal) |
| Effort | Medium | Medium–High (harness DW5 + Jupiter) |

## 7. Recommendation
**Option B + F1**, reworked **in lockstep with `shared` and before any downstream service**. Build the fakes as in-memory implementations of the `cloud-sdk-api` interfaces (`InMemoryStorageClient`, `InMemoryMessagingClient<String>`, `InMemoryNotificationService`, `InMemoryEmailService`, plus a Dynamo path via a small `DatabaseRepository` fake or `dynamo-integration-test`). **Preserve the AssertJ DSL surface** wherever it does not currently leak v1 types; for the surfaces that do (`FakeSQS` message lists, `FakeS3` put, `FakeSES`, `FakeDynamoDB` put, `SnsAssert` captor), apply the documented test-API changes (§9). **No cloud-sdk library gap** — this module consumes `cloud-sdk-api` and builds its own fakes. This is appianway-internal test code → **provably no impact to mercury-services**.

## 8. Peer review note
Self-review against source confirms the lockstep role and corrects the Copilot draft on: (a) program option is **B**, not A; (b) the rework is not pure deletion — there are **specific unavoidable test-API changes** at the v1-leaking DSL surfaces; (c) **SNS becomes a real in-memory fake** (was a Mockito captor); (d) v1 reaches this module **transitively via `shared`**, so `cloud-sdk-api` must be added directly; (e) the **DW4 + config-command harness** is part of the lockstep. The store-backed assertions and the in-memory stores are confirmed reusable.

## 9. Open questions / dependencies / sequencing
- **Sequencing (hard):** `shared` → **`functional-testing`** → downstream services (`mvn -pl <svc> -am verify`, starting `event-writer`). This module is the **compile gate** for every service functional test.
- **Unavoidable test-API changes (migration note for test authors):**
  1. `FakeSQS.getMessages/getHistory` return type changes from `List<com.amazonaws…Message>` to `List<QueueMessage<String>>` (most tests use `getMessages(url, Class)` or the `SqsAssert` DSL, which are unaffected).
  2. `FakeS3.putObject` v1 return/`ObjectMetadata` param → cloud-sdk `StorageClient` shapes incl. the **S-G2** metadata overload; `getObjectMetadata` → `Map<String,String>`.
  3. `FakeSES.getEmailsSent` → returns the cloud-sdk `EmailService` `MailContent`/recipient model instead of v1 `SendEmailRequest`.
  4. `FakeDynamoDB.putItem` v1 return → `void`/repository result; or move to `dynamo-integration-test`.
  5. **SNS:** `assertThatResource(ArgumentCaptor<PublishRequest>)` → `assertThatResource(InMemoryNotificationService)`; `FunctionalTestBase` no longer mocks `AmazonSNS`. Test authors update the SNS assertion entry point.
- **Open question:** Dynamo — small in-memory `DatabaseRepository` fake vs `dynamo-integration-test`? (Recommend `dynamo-integration-test` for the real Dynamo paths; keep the trivial put-counter fake only where sufficient.)
- **Open question:** how long to keep Vintage? (Until all downstream fixtures are migrated to Jupiter; no hard deadline.)
- Coordinate with `mft-s3-aqua-appia` (separate workspace, same program) so any shared `QueueMessage`/`StorageClient` test expectations stay aligned; do not edit it from here.

## 10. Configuration changes
Test-wiring only (no runtime config). `FunctionalTestBase` rebinds the `cloud-sdk-api` in-memory fakes instead of v1 clients; `IntegrationTestSupport` moves to DW5 + the composed appianway `ServerCommand` (master [§10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md)). The `network-services.properties`/`datadog.properties` + `${PROFILE}`/`${ENV}` model is preserved.

## 11. cloud-sdk-api / cloud-sdk-aws / commons change list
**NONE.** `functional-testing` **consumes `cloud-sdk-api` as a client and builds its own in-memory fakes** — it requires no library change. The program-wide single required additive change is **S-G2** (StorageClient metadata overloads, [`shared` plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md)): **the in-memory `StorageClient` fake must also implement the new S-G2 metadata/content-type overloads** so downstream tests that exercise `putObjectWithMetaData`/`copyObjectWithMetaDate` compile and assert. That is a fake-implementation obligation here, not a cloud-sdk library change.
