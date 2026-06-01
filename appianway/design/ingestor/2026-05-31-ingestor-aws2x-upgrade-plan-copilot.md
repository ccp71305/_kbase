# `ingestor` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G6 (config), G7 (health checks). **Elasticsearch/Jest is now IN SCOPE via cloud-sdk `JestClientBuilder`/`JestModule`** (previously noted out-of-scope) — adopt it instead of a standalone Jest client; no new gap.
> Sections below are retained as the Option-A fallback reference.

> Module: `ingestor` (event indexer into Elasticsearch; despite the name, NOT a first-stage receiver) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
`ingestor` is a **standard consumer** — it binds its own AWS clients in [`modules/ExternalServicesModule`](../src/main/java/com/inttra/mercury/ingestor/modules/ExternalServicesModule.java):
- `AmazonSQS` (`amazonSQSForListener` → `sqs_listener`; `amazonSQSForSender` → `sqs_sender`)
- `AmazonS3` (`s3_read_put_copy`)

(No `AmazonSNS` binding here.) Indexing into **Elasticsearch via the Jest client** is **not AWS SDK** and is out of scope for this AWS-v2 migration (a separate OpenSearch-SDK migration is tracked elsewhere). AWS is used only for the SQS consume loop and S3 payload read via `shared`.

## 2. Migration concerns specific to ingestor
1. **Guice rebind** of `ExternalServicesModule` v1 `AmazonSQS`/`AmazonS3` → `cloud-sdk-aws` `MessagingClient`/`StorageClient`.
2. **`Message` DTO → `MessageRef`** in the indexing task.
3. **Do not touch** the Jest/Elasticsearch indexing path in this change.

## 3. Dependencies on `shared`
**Hard dependency.** Migrate after `shared` + `functional-testing`.

## 4. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8.
- **Option A (recommended):** rebind to `cloud-sdk-aws`; keep Dropwizard 4 / JUnit 4.
- **Option B:** commons → Dropwizard 4→5; no benefit here.

## 5. Maven impact
Remove `aws-java-sdk-{sqs,s3}`. Add `cloud-sdk-api` + `cloud-sdk-aws` (versions from root `dependencyManagement`, v2 BOM 2.30.24). Jest dependency unchanged.

## 6. Test impact
Functional tests use `functional-testing` fakes (re-pointed to `cloud-sdk-api`). Elasticsearch-indexing tests unaffected. JUnit 4 retained.

## 7. Recommendation
**Option A.** Effort: **Low** (smallest standard-consumer surface — SQS+S3 only, no SNS).

## 8. Peer review outcome
Peer-reviewed (Explore subagent). **Correction applied:** ingestor was initially mis-classified as DTO-only; it is a standard consumer binding SQS + S3 in its own `ExternalServicesModule` (confirmed by direct read — note **no SNS**). Reviewer confirmed Jest/Elasticsearch is non-AWS-SDK and out of scope. Recommendation: Option A.

## 9. Sequencing
After `shared` + `functional-testing`; can be migrated early as the simplest consumer (no SNS, no DynamoDB).

## 10. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Override-config mapping gaps | Centralize in `shared`; functional-test assert |
| `Message`→`MessageRef` drift | Parity tests in `shared` |
| Scope creep into Jest path | Keep AWS-boundary-only scope |
