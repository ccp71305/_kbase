# `email-sender` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.appian-way:email-sender:1.0` · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, AWS SDK v2 BOM **2.30.24**, Guice **7.0.0**, Jackson **2.21.0**).
> Master references (do not duplicate): [shared plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [shared DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6.

---

## 0. What this document changes vs. the Copilot plan (critical review)

I reviewed [`2026-05-31-email-sender-aws2x-upgrade-plan-copilot.md`](2026-05-31-email-sender-aws2x-upgrade-plan-copilot.md) and [`...-DESIGN.md`](2026-05-31-email-sender-aws2x-upgrade-DESIGN.md) against the **actual** email-sender source. The biggest correction is **G5**.

| Copilot position | Evidence | This plan |
|---|---|---|
| **G5 — add a `ThymeleafTemplateService` impl of cloud-sdk-api `TemplateService` to cloud-sdk-aws** (or migrate templates to Handlebars) | email-sender renders Thymeleaf **locally** in `TemplateMode.TEXT` ([`EmailSenderModule.java:109-116`](../src/main/java/com/inttra/mercury/email/modules/EmailSenderModule.java)) and sends the **already-rendered** subject+body string ([`PropertyPlaceholdersResolver.java:23-31`](../src/main/java/com/inttra/mercury/email/services/resolvers/PropertyPlaceholdersResolver.java)). cloud-sdk's `EmailService` accepts pre-rendered `MailContent`; it needs no template engine to send rendered text. | **DE-SCOPED ENTIRELY.** Adding Thymeleaf to cloud-sdk-aws would force a **heavy Thymeleaf transitive dependency on every mercury-services consumer** — a direct violation of the zero-impact constraint. **Keep Thymeleaf LOCAL in email-sender (unchanged)** and send the finished text via `EmailService.sendEmail(from, to, MailContent)` over SES v2. **No cloud-sdk change.** |
| **G1** (concurrent listener), **G6** (config) module-specific gaps | Master review de-scoped both to appianway-local | **No module-specific cloud-sdk gap** from these. email-sender keeps its `SQSListener`+`AsyncDispatcher`. |
| SES classic→v2 "behavior/contract change" needing careful field mapping | Correct — `MailingService` builds v1 `SendEmailRequest`/`Destination`/`Message` and reads `SendEmailResult.getMessageId()` ([`MailingService.java:86-105`](../src/main/java/com/inttra/mercury/email/services/MailingService.java)) | **Confirmed — this is the real work.** Map the v1 SES model to cloud-sdk `EmailService`/`MailContent` (SES v2). See §3, DESIGN §6. |
| `maxErrorRetry(0)` not called out | `new ClientConfiguration().withMaxErrorRetry(0)` ([`ExternalServicesModule.java:30-33`](../src/main/java/com/inttra/mercury/email/modules/ExternalServicesModule.java)) | **Must preserve.** Express via cloud-sdk-aws SES client config / v2 `ClientOverrideConfiguration` retry policy = none (see §3.4). |
| S-G2 implied for S3 consumers | email-sender S3 use is **read-only** (`getContent`, [`ContentLoaderService.java:36`](../src/main/java/com/inttra/mercury/email/services/ContentLoaderService.java)) | **S-G2 does NOT apply to email-sender.** |

Net effect: email-sender consumes cloud-sdk **as a normal client** — SES v2 send via `EmailService`, SQS + S3-read + SNS via shared — with **zero module-specific cloud-sdk change** and **Thymeleaf kept out of the shared library**.

---

## 1. Executive summary

`email-sender` consumes the email queue, loads the original event + contents from S3, renders **subject and body locally with Thymeleaf in `TemplateMode.TEXT`**, applies a **local rate limiter**, and sends via **v1 SES** (`AmazonSimpleEmailService`, retries disabled). Its AWS surface: **SES** (send), **SQS** (listener + sender), **S3** (read), **SNS** (event publish).

Per the master directive the recommendation is **Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5** (§7). The module-unique work is the **v1 SES → cloud-sdk `EmailService` (SES v2) model mapping** and **reworking the SES fake in `functional-testing`**. Thymeleaf rendering and the rate limiter stay **local and unchanged**.

---

## 2. Current state — AWS v1 inventory (verified, file:line)

| Area | Symbol / call | Location |
|---|---|---|
| SES client (retries off) | `new ClientConfiguration().withMaxErrorRetry(0)` → `AmazonSimpleEmailServiceClientBuilder` → `bind(AmazonSimpleEmailService)` | [`ExternalServicesModule.java:30-33`](../src/main/java/com/inttra/mercury/email/modules/ExternalServicesModule.java) |
| SES send (v1 model) | `SendEmailRequest`/`Destination`/`simpleemail.model.Message`/`SendEmailResult.getMessageId()` | [`MailingService.java:4-8,86-105`](../src/main/java/com/inttra/mercury/email/services/MailingService.java) |
| SES v1 `Message` in domain model | `com.amazonaws.services.simpleemail.model.Message message` field | [`MailDetails.java:3,22`](../src/main/java/com/inttra/mercury/email/model/MailDetails.java) |
| Thymeleaf render → v1 SES `Body`/`Content`/`Message` | `templateEngine.process(...)` → `new Body(new Content(body))`, `new Message(subject, body)` | [`PropertyPlaceholdersResolver.java:3-5,23-31`](../src/main/java/com/inttra/mercury/email/services/resolvers/PropertyPlaceholdersResolver.java) |
| Thymeleaf engine (local) | `TemplateEngine` + `StringTemplateResolver`, `TemplateMode.TEXT` | [`EmailSenderModule.java:31-33,109-116`](../src/main/java/com/inttra/mercury/email/modules/EmailSenderModule.java) |
| SQS listener / sender | `bind(AmazonSQS)` `amazonSQSForListener`/`amazonSQSForSender` | [`ExternalServicesModule.java:22-25`](../src/main/java/com/inttra/mercury/email/modules/ExternalServicesModule.java) |
| S3 client + read | `bind(AmazonS3)`; `workspaceService.getContent(bucket, fileName)` | [`ExternalServicesModule.java:26-27`](../src/main/java/com/inttra/mercury/email/modules/ExternalServicesModule.java), [`ContentLoaderService.java:36`](../src/main/java/com/inttra/mercury/email/services/ContentLoaderService.java) |
| SNS publish | `bind(AmazonSNS)` `sns_publish`; `SNSEventPublisher` over `SNSClient` | [`ExternalServicesModule.java:28-29`](../src/main/java/com/inttra/mercury/email/modules/ExternalServicesModule.java), [`EmailSenderModule.java:70-74`](../src/main/java/com/inttra/mercury/email/modules/EmailSenderModule.java) |
| SQS DTO leak | `com.amazonaws.services.sqs.model.Message` in task | [`EmailSenderTask.java:3,56,88`](../src/main/java/com/inttra/mercury/email/task/EmailSenderTask.java) |
| Rate limiter (local) | `RateLimiterService.filterByRate()` | [`EmailSenderTask.java:67`](../src/main/java/com/inttra/mercury/email/task/EmailSenderTask.java) |
| pom v1 deps | `aws-java-sdk-sqs`, `aws-java-sdk-ses`; `thymeleaf 3.0.7.RELEASE` pinned | [`pom.xml:44-54,71-75`](../pom.xml) |

Concurrency: one `SQSListener` → `AsyncDispatcher`/`EmailSenderTask` ([`EmailSenderModule.java:57-93`](../src/main/java/com/inttra/mercury/email/modules/EmailSenderModule.java)) — appianway-owned, **kept**.

---

## 3. Findings

### 3.1 Thymeleaf rendering is local and produces a finished string
`PropertyPlaceholdersResolver` renders subject + body text via `TemplateEngine.process` and wraps them only in v1 SES `Content`/`Body`/`Message` DTOs ([`PropertyPlaceholdersResolver.java:23-31`](../src/main/java/com/inttra/mercury/email/services/resolvers/PropertyPlaceholdersResolver.java)). The template engine itself never touches AWS. ⇒ The v1 SES DTOs here are just a carrier for the rendered text; **migration only re-targets the carrier**, not the rendering. **No template engine belongs in cloud-sdk.**

### 3.2 v1 SES → cloud-sdk EmailService mapping (the real work)
`MailingService.sendMail` builds a v1 `SendEmailRequest` with `source`, `Destination(toAddresses)`, `message(subject+body)`, `replyToAddresses` and returns `SendEmailResult.getMessageId()` ([`MailingService.java:49-105`](../src/main/java/com/inttra/mercury/email/services/MailingService.java)). Map to cloud-sdk `EmailService.sendEmail(from, List<to>, MailContent)`:
- `source` → `from`;
- `Destination.toAddresses` → `to` list;
- subject + body text → `MailContent` (subject + text body);
- `replyToAddresses` → reply-to on `MailContent`/request (verify the cloud-sdk `MailContent` exposes reply-to; if not, see §11);
- return value → cloud-sdk send result message id.

### 3.3 SES is v2 in cloud-sdk
cloud-sdk-aws's `SesEmailServiceImpl` is backed by SES **v2** (`SesV2Client`). This is a model change, not a rename (Copilot was right). The mapping is contained to `MailingService` + `MailDetails` + `PropertyPlaceholdersResolver`'s return type.

### 3.4 `maxErrorRetry(0)` must be preserved
email-sender intentionally disables SES SDK retries ([`ExternalServicesModule.java:30`](../src/main/java/com/inttra/mercury/email/modules/ExternalServicesModule.java)) because the app rate-limits and the workflow handles retries itself. Express the same in v2: configure the cloud-sdk-aws SES client (via `EmailClientFactory`/config) with `ClientOverrideConfiguration` retry policy = **none** (`RetryPolicy.none()` / `retryStrategy(none)`). Confirm the factory exposes this knob (see §11).

### 3.5 S3 read-only; the SQS DTO is `QueueMessage<String>`
`getContent` only ([`ContentLoaderService.java:36`](../src/main/java/com/inttra/mercury/email/services/ContentLoaderService.java)) ⇒ **S-G2 not applicable**. `EmailSenderTask` reads `message.getBody()` ([`EmailSenderTask.java:59,96`](../src/main/java/com/inttra/mercury/email/task/EmailSenderTask.java)) → `QueueMessage<String>.getPayload()`.

### 3.6 `Message` name clash
Both `simpleemail.model.Message` (SES) and `sqs.model.Message` (SQS) are used. After migration: SQS side → `QueueMessage<String>`; SES side → cloud-sdk `MailContent` — the clash disappears.

---

## 4. Option A — keep `email-sender` on DW4, rebind to cloud-sdk

Rebind SES to cloud-sdk `EmailService` (SES v2 via `EmailClientFactory`); SQS/S3-read/SNS to shared cloud-sdk wrappers; swap `Message` → `QueueMessage<String>`; keep Thymeleaf + rate limiter local; keep DW4/JUnit4.

- **Pros:** smallest blast radius; reversible. **Cons:** keeps DW4 base. **Effort:** Medium (SES model mapping + SES fake rework). **Risk:** Medium.

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A, plus move onto `commons` `InttraServer` (DW5) + appianway `ServerCommand`, JUnit 5 new tests. email-sender keeps its `SQSListener`/`AsyncDispatcher`, Thymeleaf engine, and rate limiter.

- **Pros:** platform convergence; JUnit 5. **Cons:** DW4→5 (inherited from shared). **Effort:** Medium–High. **Risk:** Medium.

## 6. Comparison

| Criterion | Option A (DW4) | Option B (commons/DW5) |
|---|---|---|
| Off AWS v1 (SES/SQS/S3/SNS) | ✅ | ✅ |
| Required cloud-sdk change | **None** (G5 de-scoped) | **None** |
| Thymeleaf in shared library | **No** | **No** |
| Impact on mercury-services | None | None |
| Effort | Medium | Medium–High |
| Risk | Medium | Medium |
| Framework churn | None | DW4→5 (inherited) |

## 7. Recommendation

**Option B** per directive, consuming cloud-sdk as a normal client with **no module-specific cloud-sdk change** and **Thymeleaf kept entirely local**. Treat email-sender as a **later wave** (after shared + functional-testing SES fake) because of the SES v1→v2 model mapping and the SES fake rework — do not bundle with trivial DTO-only consumers. Effort: **Medium–High**, concentrated in `MailingService`/`MailDetails`/`PropertyPlaceholdersResolver` and the `functional-testing` SES fake.

## 8. Peer review note

Self-review against source: (1) **G5 de-scoped entirely** — Thymeleaf stays local; sending pre-rendered text via `EmailService`/`MailContent` needs no cloud-sdk template engine and keeps a heavy Thymeleaf dependency out of every mercury-services consumer (the zero-impact constraint); (2) SES classic→v2 is a genuine model change, contained to three classes + the SES fake; (3) `maxErrorRetry(0)` must be preserved via v2 `ClientOverrideConfiguration` retry=none; (4) S-G2 not applicable (S3 read-only); (5) SQS DTO → `QueueMessage<String>` resolves the `Message` name clash.

## 9. Open questions / sequencing

- Migrate **after** `shared` **and** `functional-testing` (SES fake). **Later wave** due to the SES model change.
- **Verify in cloud-sdk-api/aws:** (a) `MailContent` carries **reply-to** (`MailingService` sets `replyToAddresses`); if not, see §11; (b) `EmailClientFactory`/SES client config exposes a **retry=none** knob to preserve `maxErrorRetry(0)`; (c) `EmailService.sendEmail` returns/propagates a **message id** (current code logs/returns it).
- Confirm no SES **configuration set** / **source ARN** is configured today (none seen in `MailingService`); if added later, ensure it maps to the v2 request.

## 10. Configuration changes

Defers to master plan [§10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md). email-sender-specific: `MailConfig` (sender/reply-to addresses) unchanged; SES region/source map to the cloud-sdk-aws SES client via `EmailClientFactory`. **SES retry must map to v2 retry=none** (preserving `maxErrorRetry(0)`). Rate-limit and Thymeleaf config unchanged. `${PROFILE}`/`${ENV}` unchanged.

## 11. cloud-sdk gaps — email-sender

**No module-specific cloud-sdk change.**
- **G5 (Thymeleaf): explicitly DE-SCOPED.** No `ThymeleafTemplateService` is added to cloud-sdk-aws. Thymeleaf rendering stays **local** in email-sender (`TemplateMode.TEXT`); the finished subject+body text is sent via `EmailService.sendEmail(from, to, MailContent)` over SES v2. This keeps Thymeleaf out of the shared library ⇒ zero transitive impact to mercury-services consumers.
- **S-G2:** not applicable (email-sender reads S3 only; no metadata write/copy).
- **Contingent additive items (only if verification §9 finds a gap, and only then strictly additive):** if `MailContent` lacks **reply-to**, or the SES client config lacks a **retry=none** knob, these would be small **additive** overloads/config options in cloud-sdk-api/aws (new field/method only, existing signatures untouched), filed under the master's additive-only contract. **Preferred path is to use existing API**; reply-to/retry are expected to be expressible without any library change (verify first).
- Master gaps **G1/G6** de-scoped to appianway-local (master §0/§11): email-sender keeps its `SQSListener`+`AsyncDispatcher` and composes config via the appianway `ServerCommand`.
