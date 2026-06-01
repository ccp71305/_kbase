# `functional-testing` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 — provide a concurrent-listener/AsyncDispatcher test fake. Re-implement all in-memory fakes against the `cloud-sdk-api` interfaces (`StorageClient`/`MessagingClient`/`QueueMessage`/`NotificationService`/`CloudParameterStore`/`DatabaseRepository`/`EmailService`) and add JUnit 5 (`dropwizard-testing`) support. Fakes must also cover G2 (putObject metadata) and G4 (version attribute) so consumer tests compile.
> Sections below are retained as the Option-A fallback reference.

> Module: `functional-testing` (shared functional-test SDK; test scope in every service) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface (the biggest fake-rework in the repo)
`functional-testing` provides **in-memory AWS fakes** implementing the full **AWS SDK v1 interfaces**:
- **`aws/AmazonS3Adaptor`** ([src](../src/main/java/com/inttra/mercury/test/aws/AmazonS3Adaptor.java)) `implements com.amazonaws.services.s3.AmazonS3` — hundreds of v1 methods, `S3ClientOptions`, `S3ResponseMetadata`, and the entire `s3.model.*` surface.
- **`aws/AmazonSESAdaptor`** ([src](../src/main/java/com/inttra/mercury/test/aws/AmazonSESAdaptor.java)) `implements com.amazonaws.services.simpleemail.AmazonSimpleEmailService` — full SES classic surface + waiters.
- **`AmazonSQS` / `AmazonSNS` fakes** wired through `FunctionalTestBase` ([src](../src/main/java/com/inttra/mercury/test/FunctionalTestBase.java)).
These fakes are injected in place of the real AWS clients so every service's "functional" test runs without live AWS.

## 2. Why this module is the lockstep enabler
Once `shared` no longer exposes v1 client types (it consumes `cloud-sdk-api` interfaces), the fakes must implement/back the **same `cloud-sdk-api` interfaces** the wrappers now depend on — otherwise **no downstream service functional test compiles**. `functional-testing` must migrate **immediately after `shared`** and **before** any service.

## 3. Migration approach
Two sub-options for the fakes:
- **(F1) Implement `cloud-sdk-api` interfaces directly (recommended).** Replace `AmazonS3Adaptor`→`InMemoryStorageClient implements StorageClient`, `AmazonSESAdaptor`→`InMemoryEmailService implements EmailService`, plus `InMemoryMessagingClient implements MessagingClient<String>` and `InMemoryNotificationService implements NotificationService`. These interfaces are **small** (a handful of methods each) versus the giant v1 interfaces — the fakes get **dramatically smaller and simpler**. Back them with the existing in-memory maps/lists so assertions keep working.
- **(F2) Implement the v2 SDK client interfaces (`S3Client`, `SqsClient`, `SnsClient`, `SesV2Client`).** Much larger surface (like the v1 pain) and unnecessary if `shared` accepts the `cloud-sdk-api` interfaces. **Not recommended.**

The AssertJ DSL and JUnit-4 lifecycle stay; only the fake backing types change. If a `dynamo`/DynamoDB fake exists for watermill tests, align it with `dynamo-integration-test` (or keep a local in-memory fake for the v2 Enhanced Client).

## 4. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8. **Option A recommended**, with fakes implemented via **F1** (`cloud-sdk-api` interfaces). Keep JUnit 4.

## 5. Maven impact
Remove `com.amazonaws:aws-java-sdk-{s3,ses,sqs,sns}` from `functional-testing/pom.xml`. Add `cloud-sdk-api` (compile, to implement the interfaces). Possibly add `dynamo-integration-test` (test) if watermill DynamoDB tests are hosted here.

## 6. Test impact
- The fakes themselves shrink to the small `cloud-sdk-api` interfaces.
- `FunctionalTestBase` rewires injection to the new fakes.
- All downstream service functional tests then compile/run unchanged **provided** they consume `shared` wrappers (not v1 clients directly) — verify each.
- JUnit 4 retained. No Jupiter.

## 7. Recommendation
**Option A + F1.** Migrate immediately after `shared`. Effort: **High** (it is the most code, but most of it is *deletion* — the v1 giant-interface stubs disappear).

## 8. Peer review outcome
Peer-reviewed (Explore subagent). Confirmed `AmazonS3Adaptor`/`AmazonSESAdaptor` implement the full v1 interfaces and are the compile-blocking dependency for downstream tests. Reviewer notes incorporated: (a) prefer F1 — implementing the narrow `cloud-sdk-api` interfaces collapses hundreds of stub methods to a few; (b) sequence this module **first after `shared`, before all services**; (c) verify the AssertJ DSL accessors read from the in-memory stores, not from v1 model objects, so they survive the backing-type change; (d) check for a DynamoDB fake and align it with `dynamo-integration-test` for watermill. Recommendation unchanged.

## 9. Sequencing
**`shared` → `functional-testing` → all services.** Hard prerequisite for every downstream functional test.

## 10. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Downstream tests fail to compile mid-migration | Migrate `functional-testing` right after `shared`, before services; build the aggregator test scope |
| AssertJ DSL coupled to v1 model objects | Re-point DSL to in-memory stores; keep assertion API stable |
| Hidden direct v1-client usage in a service test | Audit each service test; route through `shared` wrappers/fakes |
| DynamoDB fake parity for watermill | Use `dynamo-integration-test` or a v2-Enhanced-Client in-memory fake |
