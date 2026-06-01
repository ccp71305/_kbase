# `error-processor` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener for `sqs_subscription_errors` fan-in), G2 (S3 archive putObject with metadata), G6 (config), G7 (health checks). Email fan-out is via the email-sender queue (no direct SES here).
> Sections below are retained as the Option-A fallback reference.

> Module: `error-processor` (fan-in for `sqs_subscription_errors`: archives to S3, fans out to email) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
- **`modules/ExternalServicesModule`** ([src](../src/main/java/com/inttra/mercury/error/processor/modules/ExternalServicesModule.java)) binds `AmazonSQS` listener+sender, `AmazonS3`, `AmazonSNS`.
- **`ErrorProcessorTask`** ([src](../src/main/java/com/inttra/mercury/error/processor/task/ErrorProcessorTask.java)) consumes `com.amazonaws.services.sqs.model.Message` (shared listener DTO).
- No module-unique AWS model types beyond the listener DTO and the standard `shared` wrappers (S3 archive write, SNS lineage, SQS fan-out to email queue).

## 2. Migration concerns
Pure **standard consumer** profile: rebind Guice clients to `cloud-sdk-aws`, swap `Message`→`MessageRef`. Archive-to-S3 and email-fan-out go through `shared` wrappers, all migrated in the `shared` deliverable.

## 3. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8. **Option A recommended** — rebind + DTO swap; keep Dropwizard 4 / JUnit 4.

## 4. Maven impact
Remove `aws-java-sdk-{sqs,sns,s3}`; add `cloud-sdk-api` only if naming interface types. v2 runtime transitive via `shared`.

## 5. Test impact
Functional tests via `functional-testing` fakes (migrate first). Keep tests: error archival to S3, fan-out routing, error-code mapping. DTO → `MessageRef`. JUnit 4 retained.

## 6. Recommendation
**Option A.** Effort: **Low** (clean standard consumer). Good early-rollout candidate after `event-writer`.

## 7. Peer review outcome
Peer-reviewed (Explore subagent). Confirmed no module-unique AWS model usage beyond the listener DTO; ExternalServicesModule is the single binding point. Reviewer note: error-processor is itself the error sink, so its own `ErrorHandler` must not create a loop when the archive write fails — verify the existing `RecoverableException`/delete semantics survive the wrapper swap unchanged (no behavior change intended). Recommendation unchanged.

## 8. Sequencing
After `shared` + `functional-testing`. Low risk; migrate alongside `event-writer` in the first wave.

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Archive-write failure loop | Preserve existing `RecoverableException`/delete semantics; test the failure path |
| DTO swap misses a site | Compiler-driven type change |
| Functional fakes not ready | Sequence behind `functional-testing` |
