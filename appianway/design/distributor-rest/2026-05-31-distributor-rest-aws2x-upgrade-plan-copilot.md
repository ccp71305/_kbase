# `distributor-rest` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata), G6 (config), G7 (health checks). REST/OAuth bearer egress stays appianway-local (no cloud-sdk gap).
> Sections below are retained as the Option-A fallback reference.

> Module: `distributor-rest` (REST/HTTP egress; POSTs payload to subscriber endpoints, OAuth bearer) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
`distributor-rest` is a **standard consumer** — it binds its own AWS clients in [`modules/ExternalServicesModule`](../src/main/java/com/inttra/mercury/distributorrest/modules/ExternalServicesModule.java):
- `AmazonSQS` (`amazonSQSForListener` → `sqs_listener`; `amazonSQSForSender` → `sqs_sender`)
- `AmazonS3` (`s3_read_put_copy`)
- `AmazonSNS` (`sns_publish`)

The HTTP/OAuth egress (JAX-RS client POST to subscriber endpoints) is **not AWS** and is unchanged. AWS is used only for the SQS consume loop, S3 payload read, and SNS lineage — all flowing through `shared`.

## 2. Migration concerns specific to distributor-rest
1. **Guice rebind** of `ExternalServicesModule` v1 `Amazon{SQS,S3,SNS}` → `cloud-sdk-aws` `MessagingClient`/`StorageClient`/`NotificationService` (canonical standard-consumer change; see [dispatcher DESIGN](../../dispatcher/docs/2026-05-31-dispatcher-aws2x-upgrade-DESIGN.md)).
2. **`Message` DTO → `MessageRef`** in the egress task.
3. The HTTP/OAuth client, retry, and subscriber-endpoint logic are untouched — keep the migration strictly to the AWS boundary.

## 3. Dependencies on `shared`
**Hard dependency.** Migrate after `shared` + `functional-testing`.

## 4. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8.
- **Option A (recommended):** rebind to `cloud-sdk-aws`; keep Dropwizard 4 / JUnit 4; no egress-logic change.
- **Option B:** commons → Dropwizard 4→5; no benefit for this module.

## 5. Maven impact
Remove `aws-java-sdk-{sqs,s3,sns}`. Add `cloud-sdk-api` + `cloud-sdk-aws` (versions from root `dependencyManagement`, v2 BOM 2.30.24).

## 6. Test impact
Functional tests use `functional-testing` fakes (re-pointed to `cloud-sdk-api`). HTTP-egress tests (WireMock/JAX-RS) unaffected. JUnit 4 retained.

## 7. Recommendation
**Option A.** Effort: **Low–Medium** (mechanical rebind + `Message`→`MessageRef`).

## 8. Peer review outcome
Peer-reviewed (Explore subagent). **Correction applied:** distributor-rest was initially mis-classified as DTO-only; it is a standard consumer binding SQS/S3/SNS in its own `ExternalServicesModule` (confirmed by direct read). Reviewer confirmed the HTTP/OAuth egress path is non-AWS and out of scope. Recommendation: Option A.

## 9. Sequencing
After `shared` + `functional-testing`; with the hot-pipeline egress group (alongside `distributor`).

## 10. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Override-config mapping gaps | Centralize in `shared`; functional-test assert |
| `Message`→`MessageRef` drift | Parity tests in `shared` |
| Accidental egress-logic change | Keep migration at AWS boundary only |
