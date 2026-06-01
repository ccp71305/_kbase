# `email-sender` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** **G5 (Thymeleaf template engine — email-sender renders Thymeleaf; cloud-sdk `EmailService` uses Handlebars. Add a `ThymeleafTemplateService` impl of `cloud-sdk-api` `TemplateService` to cloud-sdk-aws, or migrate templates to Handlebars; see master DESIGN §1A.6 G5)**, plus G1 (concurrent SQS listener) and G6 (config). SES classic→SES v2 is already covered by `SesEmailServiceImpl`; rate-limiting stays appianway-local.
> Sections below are retained as the Option-A fallback reference.

> Module: `email-sender` (Thymeleaf-templated SES emails, rate-limited) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
- **Consume:** `com.amazonaws.services.sqs.model.Message` (shared listener DTO) in `EmailSenderTask`.
- **Send (module-unique):** `com.amazonaws.services.simpleemail.AmazonSimpleEmailService` + `simpleemail.model.{SendEmailRequest, SendEmailResult, Message, ...}` — **SES "classic" (v1) API**.
- Rate-limiting + Thymeleaf templating are local logic (no AWS).

## 2. Migration concerns specific to email-sender
1. **SES classic → SES v2.** `cloud-sdk-api` exposes `EmailService`; `cloud-sdk-aws` provides `SesEmailServiceImpl(SesV2Client)` and `EmailClientFactory.createDefaultSesClient(templates)`. This is **not** a like-for-like swap: the v1 `AmazonSimpleEmailService.sendEmail(SendEmailRequest)` maps to the SES **v2** `SesV2Client.sendEmail` (different request/response model — `Destination`, `Content`, `Body` shapes differ). **Behavior/contract change** — must map fields carefully (From, To/Cc/Bcc, Subject, HTML/Text body, charset, configuration set if used).
2. **Templating:** today Thymeleaf renders HTML locally and the rendered body is sent via `SendEmailRequest`. Decide whether to keep local Thymeleaf rendering + raw/simple send, or adopt SES v2 templates. **Recommend keeping local Thymeleaf rendering** and sending the rendered content through `EmailService` to preserve existing template behavior and tests.
3. **Rate limiting:** keep the existing local rate-limiter; SES v2 has its own throttling but the app-level limiter is intentional — retain it.
4. **`simpleemail.model.Message` name clash:** note tests import both `simpleemail.model.Message` and `sqs.model.Message` — keep these straight when swapping (SQS side → `MessageRef`; SES side → v2 content model).

## 3. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8.
- **Option A (recommended):** consume `cloud-sdk-api` `EmailService` (SES v2) for sending; rebind Guice to `cloud-sdk-aws` `SesEmailServiceImpl`; swap SQS DTO → `MessageRef`; keep local Thymeleaf + rate limiter; keep Dropwizard 4 / JUnit 4.
- **Option B:** additionally move to commons `InttraServer`/Dropwizard 5 — unnecessary churn for this module.

## 4. Maven impact
Remove `com.amazonaws:aws-java-sdk-ses` (+ `-sqs` if declared). Add `cloud-sdk-api` (for `EmailService`); `cloud-sdk-aws` SES v2 runtime arrives via the factory/`shared`. Ensure `software.amazon.awssdk:sesv2` is on the runtime classpath (transitively via `cloud-sdk-aws`).

## 5. Test impact
- `MailingServiceTest`, `EmailSenderTaskTest`, `EmailSenderFuncTest`, `PropertyPlaceholdersResolverTest` reference v1 SES model types → re-point to the `EmailService` interface / SES v2 content model.
- `functional-testing` `AmazonSESAdaptor` (implements v1 `AmazonSimpleEmailService`) must be migrated to back `EmailService` (see [`functional-testing` plan](../../functional-testing/docs/2026-05-31-functional-testing-aws2x-upgrade-plan-copilot.md)) — this is a hard dependency for email-sender functional tests.
- Add tests asserting From/To/Subject/HTML-body/charset map correctly into the SES v2 send. JUnit 4 retained.

## 6. Recommendation
**Option A**, keeping local Thymeleaf rendering and the app rate-limiter, sending via `cloud-sdk-api` `EmailService` (SES v2). Effort: **Medium-High** — the SES classic→v2 model mapping and the SES fake rework are the real work.

## 7. Peer review outcome
Peer-reviewed (Explore subagent). Confirmed SES is the module-unique surface and that `cloud-sdk-aws` uses **SES v2** (`SesV2Client`), making this a contract change not a rename. Reviewer notes incorporated: (a) call out the `simpleemail.model.Message` vs `sqs.model.Message` import clash; (b) explicitly decide to keep local Thymeleaf rendering rather than adopt SES templates (lower risk, preserves tests); (c) flag the `functional-testing` `AmazonSESAdaptor` rework as a blocking prerequisite; (d) verify whether a configuration-set/source-ARN is used today and preserve it in the v2 request. Recommendation unchanged.

## 8. Sequencing
After `shared` **and** `functional-testing` (SES fake). Treat as a **later wave** due to the SES model change; do not bundle with the trivial DTO-only consumers.

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| SES classic→v2 field mapping errors (From/To/body/charset) | Field-by-field mapping tests; compare against a captured v1 request |
| Configuration set / source ARN dropped | Inventory current usage; assert preserved in v2 request |
| SES fake not ready | Gate behind `functional-testing` SES migration |
| `Message` type confusion (SES vs SQS) | Keep SQS→`MessageRef`, SES→v2 content model; review imports |
| Rate-limiter regression | Keep app-level limiter; test throttling behavior |
