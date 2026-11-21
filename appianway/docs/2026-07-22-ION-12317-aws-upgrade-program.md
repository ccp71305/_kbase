# ION-12317 — AppianWay AWS SDK v2 (cloud-sdk) Upgrade — Program Design

> Program landing page for the AppianWay AWS-layer upgrade. Migrate the 14 AppianWay apps off **AWS Java SDK v1 (1.12.720) + the appianway `shared` module** onto **`mercury-services-commons 1.0.27-SNAPSHOT`** (`commons` + `cloud-sdk-api` + `cloud-sdk-aws`) + a slim appianway-owned **`appianway-commons`** residue library. Per-module design lives in the 14 child pages nested under this page.

---

## Contents

---

## Requirements

### Jira Tickets

| Key | Summary | Type | Priority | Status | Assignee |
|-----|---------|------|----------|--------|----------|
| ION-12317 | Appianway - AWS SDK Upgrade | Story | Medium | Documenting Design / Tests | Arijit Kundu |

**Sub-tasks (verification tracks):** ION-14598 (OS – Verification), ION-14599 (Visibility – Verification), ION-14600 (Booking – Verification), ION-15259 (MFT – AWS Upgrade).

### Summary

AppianWay's 14 deployable apps currently reach AWS through **AWS Java SDK v1 (1.12.720)** wrapped by the bespoke **appianway `shared`** module. This program migrates the AWS layer to **AWS SDK v2** via `mercury-services-commons` (`cloud-sdk-api` + `cloud-sdk-aws`), replaces `shared` with `commons` + a slim appianway-owned `appianway-commons` residue library, and re-bases config/SSM handling onto the commons config command. It is an **AWS-layer + drop-`shared` change only** — no framework jump: the Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 baseline (ION-16098) is already in `develop` and all 14 apps boot clean on it against INT.

**Status:** Design phase. No queue/topic/bucket/SSM-path renames anywhere. Every cloud-sdk/commons change this program relies on is strictly additive/behavior-preserving (these libraries are consumed in production by mercury-services).

### Technology Stack

| Component | Before | After |
|-----------|--------|-------|
| AWS SDK | v1 `aws-java-sdk 1.12.720` | **v2** (BOM via cloud-sdk-aws) |
| AWS wrapper layer | appianway `shared` (hand-rolled v1 wrappers) | `cloud-sdk-api` + `cloud-sdk-aws` + slim `appianway-commons` |
| Config command / network-services / health | appianway `shared` | `commons` (`ConfigProcessingServerCommand`, `networkservices.*`, health base, `InttraServer`) |
| Workflow/event model | `shared.event.*` / `MetaData` / `Annotations` | `cloud-sdk-api` `notification.*` (subject to W-G9 parity) |
| Target commons line | — | `mercury-services-commons 1.0.27-SNAPSHOT` |
| Framework baseline (unchanged) | Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4 (ION-16098) | same |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | DW5/Jetty12/Java17/Jackson2.21.4 baseline is already in `develop` (ION-16098); this program is AWS-layer only. | Assumption | Resolved | Verified — all 14 apps boot clean on the baseline against INT. |
| 2 | `cloud-sdk-api`/`cloud-sdk-aws`/`commons` changes this program needs (S-G2, W-G9, X-G7) are done or will be done, strictly additively. | Assumption | Open | Land in cloud-sdk first; gate on cloud-sdk CI + full mercury-services build green before/after. |
| 3 | Retire `shared` → `commons`/`cloud-sdk-api`/`cloud-sdk-aws` + slim `appianway-commons` (Option B, locked 2026-07-22). | Decision | Resolved | See governing decisions below. |
| 4 | Target `mercury-services-commons 1.0.27-SNAPSHOT`; pin exact released coordinate at GA hardening. | Decision | Open | Pin at GA. |
| 5 | No queue/topic/bucket/SSM-path/`${key}`-default renames — they are environment contracts. | Constraint | Resolved | Any rename must be called out explicitly in the module page. |

---

## Governing decisions (locked 2026-07-22)

1. **No longer using `shared`.** The appianway `shared` module is retired. Everything it provided is replaced by `commons`/`cloud-sdk-api`/`cloud-sdk-aws` **except** a small appianway-specific residue, which moves to a new slim **`appianway-commons`** library.
2. **Target line: `mercury-services-commons 1.0.27-SNAPSHOT`** (Dropwizard 5.0.x, AWS SDK v2 BOM, Guice 7, Jackson 2.21.x).
3. **Workflow model** (`MetaData`/`Event`/`Annotations`/`EventLogger`/`EventGenerator`/`EventPublisher`) comes from **cloud-sdk-api `notification.*`**; **network-services** (Auth/Format/IntegrationProfile/Geography) from **commons**.
4. **Config/SSM:** compose appianway `${key}` property substitution → commons `TrimConfigCommentsTransform` → `ParameterStoreConfigTransform` (`${awsps:/path}` resolved at boot).

**Non-negotiable contract:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` are consumed in **production by mercury-services**. Every change this program relies on MUST be strictly additive (new `default` methods, overloads, types, visibility-widening only). AppianWay consumes them as a normal client.

---

## High Level Design — what actually changes

```
BEFORE — each of the 14 apps (DW5 baseline, AWS v1)
┌───────────┐     ┌────────────────────────────────────────────┐     ┌────────────────────┐
│  app code  │───▶│  appianway `shared`                          │───▶│  AWS Java SDK v1    │
│            │     │  config cmd · SQS/SNS/S3 v1 wrappers ·        │     │  1.12.720           │
│            │     │  event model · health · network-services ·   │     │                     │
│            │     │  MetaData/Annotations · AsyncDispatcher ·     │     │                     │
│            │     │  ErrorHandler                                │     │                     │
└───────────┘     └────────────────────────────────────────────┘     └────────────────────┘

AFTER — same apps on commons + cloud-sdk (AWS v2)
┌───────────┐     ┌────────────────────────────────────────────┐
│  app code  │───▶│  appianway-commons (slim)                    │
│            │     │  AsyncDispatcher/AbstractTask ·              │
│            │     │  ErrorHandler/RecoverableException ·         │
│            │     │  error codes · health-registrar wrappers     │
│            │     └────────────────────────────────────────────┘
│            │     ┌────────────────────────────────────────────┐     ┌────────────────────┐
│            │───▶│  cloud-sdk-api                               │───▶│  cloud-sdk-aws      │
│            │     │  StorageClient · MessagingClient ·           │     │  S3/SQS/SNS/SSM/    │
│            │     │  NotificationService · EmailService ·        │     │  SES/DynamoDB impls │
│            │     │  CloudParameterStore · MetaData/Event/       │     └─────────┬──────────┘
│            │     │  EventLogger · Annotations                   │               │
│            │     └────────────────────────────────────────────┘               ▼
│            │     ┌────────────────────────────────────────────┐     ┌────────────────────┐
│            │───▶│  commons                                     │     │  AWS Java SDK v2    │
│            │     │  ConfigProcessingServerCommand ·             │     │  BOM                │
│            │     │  networkservices (Auth/Format/IP) ·          │     └────────────────────┘
│            │     │  health base · InttraServer                  │
└───────────┘     └────────────────────────────────────────────┘
```

- The **AWS layer** flips from v1 hand-rolled `shared` wrappers to cloud-sdk client interfaces (`StorageClient`, `MessagingClient<T>`, `NotificationService`, `CloudParameterStore`, `EmailService`, DynamoDB enhanced client).
- The **framework/config layer** flips from appianway's bespoke `ConfigProcessingServerCommand` to commons' command + composed transforms.
- The **INTTRA network-services** clients (Auth/Format/IntegrationProfile/Geography) come from **commons**.
- The **workflow/event model** comes from **cloud-sdk-api** (`notification.*`).
- The **appianway-only residue** (concurrent dispatcher, error handling, health-registrar glue, dispatcher's S3-event parser) moves to **`appianway-commons`**.

---

## Low Level Design

### `shared` → replacement mapping (authoritative)

| appianway `shared` (`com.inttra.mercury.shared.*`) | Replacement | Home |
|---|---|---|
| `command.ConfigProcessingServerCommand` | `com.inttra.mercury.config.ConfigProcessingServerCommand` + composed appianway transform | commons (+ appianway-commons) |
| `config.BaseConfiguration`, `S3Config`, `SQSConfig`, `SNSConfig`, `AWSClientConfig*` | cloud-sdk config types (`CloudStorageConfig`, `AwsMessagingClientConfig`, `NotificationClientConfig`, `AwsParameterStoreConfig`) + module POJOs | cloud-sdk-aws / module |
| `config.S3ConfigurationProvider` | keep appianway-local (YAML-from-S3 provider) or drop if unused | appianway-commons / module |
| `messaging.SQSClient` / `SQSListenerClient` / `MessageSender` (v1 `AmazonSQS`) | `cloud-sdk-api` `MessagingClient<T>` + cloud-sdk-aws SQS impl; listener via `Listener`/`SqsListener` or appianway `AsyncDispatcher` | cloud-sdk + appianway-commons |
| `messaging.SNSClient` / `event.SNSEventPublisher` (v1 `AmazonSNS`) | `cloud-sdk-api` `NotificationService` + `notification.workflow.EventPublisher`/`SnsEventPublisher` | cloud-sdk |
| S3 wrappers `S3WorkspaceService`/`WorkspaceService` (v1 `AmazonS3`, `ObjectMetadata`) | `cloud-sdk-api` `StorageClient` (put/get/copy/getContent/listObjects) + **S-G2** metadata/content-type overloads | cloud-sdk |
| `event.Event`, `EventGenerator`, `EventLogger`, `EventPublisher`, `SNSNotification` | `cloud-sdk-api` `notification.workflow.{Event,EventGenerator,EventLogger,EventPublisher,WorkflowAware}` | cloud-sdk-api |
| `MetaData`, `Annotations`, `Annotation`, `ErrorHelper` | `cloud-sdk-api` `notification.workflow.MetaData`, `notification.annotation.{Annotations,Annotation,ErrorHelper}` | cloud-sdk-api |
| `networkservices.*` (auth/format/integrationprofile/geography/messageRegister) | `commons` `com.inttra.mercury.networkservices.*` + `client.AuthClient` | commons |
| `healthcheck.*` (`HealthCheckRegistrar`, `OpsHealthCheckServlet`, indicators) | commons `health.*` base + appianway-commons indicator wrappers re-pointed to injected cloud-sdk clients | commons + appianway-commons |
| `listener.SQSListener`/`ListenerManager`/`Listener` | `cloud-sdk-api` `messaging.Listener` (+ `SqsListener`) or appianway `AsyncDispatcher` | cloud-sdk + appianway-commons |
| `externalwrapper.*` (`ExternalCallWrapper`, `RecoverableException`, retry/hystrix) | `RecoverableException` + retry → appianway-commons; Hystrix dead → drop | appianway-commons |
| `mail.MailContext` | `cloud-sdk-api` `email.MailContent` (+ local render); reply-to needs **X-G7** | cloud-sdk-api + module |
| task base `AbstractTask`, `AsyncDispatcher` | appianway-commons (appianway concurrency model) | appianway-commons |
| dispatcher S3-event parser | dispatcher-local (single consumer) | module |

> **DynamoDB** (transformer sequence, watermill offset tables): use the native v2 enhanced client via cloud-sdk-aws (`DynamoRepositoryConfig`, `@DynamoDbVersionAttribute` for optimistic lock). Not a `shared` concern.

### The slim `appianway-commons` library

Holds ONLY appianway-specific code with no `commons`/`cloud-sdk` equivalent that more than one app needs.

| Cluster | Classes (moved from `shared`) | Why it can't be commons |
|---|---|---|
| Concurrency | `AsyncDispatcher`, `AbstractTask`, task lifecycle | appianway's semaphore-bounded worker-pool model |
| Error handling | `ErrorHandler`, `RecoverableException`, `ExternalCallExecutionException`, error codes | appianway-specific error taxonomy/redelivery |
| Health glue | thin indicator wrappers binding cloud-sdk clients into commons health base + `OpsHealthCheckServlet` mapping | appianway ops-healthcheck servlet + injected-client wiring |
| Config glue | appianway property-substitution transform (`${key}` from multiple `.properties` + env) | appianway's multi-properties-file substitution isn't in commons |

- **Coordinates:** `com.inttra.mercury:appianway-commons:1.0-SNAPSHOT` (appianway-owned; NOT published to mercury-services).
- **NOT in the slim lib:** anything with a commons/cloud-sdk home (network-services, event model, MetaData/Annotations, SQS/SNS/S3/SSM/SES clients, config command). Dispatcher's S3-event parser stays dispatcher-local.

### Configuration, property substitution & SSM — change model

**Today (DW5 baseline, appianway-bespoke):** appianway `ConfigProcessingServerCommand` (in `shared`) reads all `.properties` files + OS env into a `VariableLookupProvider`, then substitutes every `${key}` in the classpath YAML (defaults via `${key:-fallback}`). SSM today = auth secrets only: `network-services.properties` holds SSM paths with `usePassThrough=false`; the `AuthClient` fetches them at runtime. Watermill modules resolve gRPC creds from SSM at runtime.

**After (commons command + composed transforms):** each app composes —

```
classpath [module].yaml (template)
    │
    ▼
[ appianway property subst ]   ${key} from .properties + env   (appianway-commons transform)
    │
    ▼
[ commons TrimConfigCommentsTransform ]
    │
    ▼
[ commons ParameterStoreConfigTransform ]   ${awsps:/path} → SSM value at boot
    │
    ▼
Dropwizard Configuration factory
```

commons' `ParameterStoreConfigTransform` resolves **`${awsps:/path}`** placeholders from SSM at boot. commons' command does **not** do appianway's multi-`.properties` `${key}` substitution, so each app composes the appianway transform first (the C-G6 composition point; C-G6 = optionally widen commons' `getConfigTransformer` visibility, not required).

**Each module page enumerates:** (1) property keys the YAML references with INT values; (2) SSM parameters + resolution mechanism (runtime vs boot `${awsps:}`); (3) config-command transform composition/order; (4) what's unchanged (CLI arg shape, `CONFIG_REGION`, `datadog.properties`, `S3ConfigurationProvider`).

> Do not silently change queue names, topic ARNs, bucket names, SSM paths, or `${key}` defaults — environment contracts.

### cloud-sdk enhancements this program assumes (all strictly additive)

| ID | Assumed change | Library | Consumers | Status |
|----|----------------|---------|-----------|--------|
| **S-G2** | `StorageClient.putObject(bucket,key,byte[],Map metadata,String contentType)` + `InputStream` variant + `copyObject(...,Map replacedMetadata,String contentType)` (S3 REPLACE) | cloud-sdk-api + aws | event-writer, dispatcher, distributor, error-processor, transformer/splitter (ref) | NOT present yet → assume added |
| **W-G9** | Workflow-model parity: `Event.Builder.setAnnotations` (round-trip) + missing `MetaData.Projection`/`Event.Token` constants | cloud-sdk-api | ALL event/MetaData publishers+consumers | Confirmed gap — see wire-compat audit |
| **X-G7** | `replyTo` on `EmailService.sendEmail(...)`/`MailContent` | cloud-sdk-api (+ SES) | email-sender | Confirmed gap → assume added, else local reply-to |
| **X-G8** | Jest/OpenSearch AWS request-signing (ingestor). **Correction (verified against mercury-services visibility-inbound / oceanschedules / elasticsearch-purge):** Jest (`io.searchbox` 6.3.1, Apache HttpClient 4.x) + the `vc.inreach` v1 SigV4 signer stay **as-is** — AWS SDK v2 is not compatible with that Jest/signer stack, and no module in mercury-services adopts a v2 Jest signer. ingestor retains `vc.inreach:aws-signing-request-interceptor` + a minimal AWS v1 auth/credentials jar **alongside** the cloud-sdk v2 stack. | module (not cloud-sdk) | ingestor | no cloud-sdk change; keep v1 signer |
| C-G6 | widen commons `getConfigTransformer` `private→protected` | commons | any app composing config | Optional; composition works without it |

**De-scoped (NOT cloud-sdk changes):** DynamoDB optimistic lock (native v2 `@DynamoDbVersionAttribute`), Thymeleaf/Handlebars template (local or cloud-sdk `TemplateService`), health helpers (re-point to injected clients).

### Workflow-model wire-compatibility audit (W-G9)

AppianWay is the ETL hub — it **publishes and consumes** `MetaData` (SQS envelopes), `Event` (SNS event topic → event-writer S3 archive), and `Annotations` to/from many mercury-services apps. Source-verified field-by-field comparison of appianway `shared` vs cloud-sdk-api `notification.*`:

| Aspect | Verdict |
|---|---|
| Date-time pattern (`yyyy-MM-dd HH:mm:ss.SS`) | identical |
| `MetaData` fields / order / `@JsonInclude` / builder | identical |
| `MetaData.Projection` keys | source-compat gap — cloud-sdk has 26, appianway uses 32 (Map keys → wire OK, add 6 for compile) — W-G9.2 |
| `Event` fields / order / date formats / SubType | identical |
| **`Event.Builder` annotations** | **WIRE round-trip DEFECT** — builder has no `annotations`/`setAnnotations`; `Event.parseJson` silently drops an `annotations` block. Write-only, asymmetric. Must fix — W-G9.1 |
| `Event.Token` keys | source-compat gap — 9 vs 17 (add 8 for compile) — W-G9.2 |
| `Annotations` / `Annotation` | identical |

**W-G9 (REQUIRED, additive, restores historical `shared` behavior):** (1) add `annotations` + `setAnnotations` to `Event.Builder` and copy in `Builder(Event)`; (2) add the 6 missing `Projection` + 8 missing `Token` constants (pure `String` constants, zero wire change).

**W-G9 does NOT break already-upgraded production apps** (evidence-verified): `booking`/`auth`/`network` use their own `MetaData`/`Event`; the only cloud-sdk `notification.workflow` consumers (`visibility`/`webbl`/`booking-bridge`) construct+publish via `EventGenerator`/`EventLogger` and don't use `Event.parseJson`/copy-ctor — the only paths W-G9.1 alters.

**Verification gate (every module references this):** a JSON round-trip corpus test using representative production `MetaData`/`Event`/`Annotations` JSON (e.g. event-writer's S3 archives) asserting appianway-`shared` serialization ≡ cloud-sdk-api serialization, byte-stable parse→serialize, including an annotations-bearing payload (guards W-G9.1). Gates the event-writer pilot; stays green through rollout.

---

## Maven dependency changes — common template

**Remove:** `com.inttra.mercury:shared`; all `com.amazonaws:aws-java-sdk-*` v1 (incl. orphan v1 deps like structuralvalidator's stray `aws-java-sdk-sqs`); Netflix Hystrix (dead).
**Add:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` (all `1.0.27-SNAPSHOT`), `appianway-commons:1.0-SNAPSHOT`. AWS SDK v2 comes transitively via cloud-sdk-aws (BOM-managed) — do not declare v1 or v2 directly.
**Align (already done by ION-16098):** Dropwizard 5.0.2 / Jetty 12.1.9 / Jackson 2.21.4 / Java 17 — inherit from mercury-services-commons where possible. `watermill/pom.xml` has no parent → mirror BOM/version pins there for the 4 consumers.
**Verify:** `mvn -pl <module> -am clean verify` green (shade needs `clean`); fat-jar boot + `/admin/opsHealthcheck` (or boot evidence) green against INT.

## Per-module page template

Every child page follows: (1) Overview; (2) Current vs Target architecture (before/after + class mapping); (3) AWS touchpoints (SQS/SNS/S3/DynamoDB/SES/SSM/gRPC + INT resource names + cloud-sdk client); (4) Sequence diagram; (5) Configuration changes (property/SSM tables, transform composition, run profiles, what's unchanged); (6) cloud-sdk/commons deps & assumed gaps; (7) Maven changes; (8) Tests; (9) Rollout & verification; (10) Risks & mitigations.

---

## Rollout (verify-gated; each behind `mvn -pl <m> -am verify` + INT boot/health check)

```
0  Land S-G2 + W-G9 + X-G7 in cloud-sdk-api/aws  →  cloud-sdk CI + full mercury-services build GREEN (zero-impact proof)
1  appianway-commons (slim residue) + functional-testing fakes (lockstep)  →  event-writer (pilot; W-G9 round-trip corpus test gates here)
2  distributor-rest · splitter · ingestor (light; ingestor = X-G8 verify)
3  dispatcher · distributor · error-processor (S-G2 write/copy)
4  email-sender (X-G7) · transformer (DynamoDB v2 + Contivo pre-flight)
5  watermill-publisher  →  consumer-commons (v2 rebind)  →  the 4 watermill consumers (gRPC + DynamoDB offset; port 8085)
```

---

## The 14 module pages

| # | Module | Headline change | Gaps | Wave | Design page |
|---|--------|------------------|------|:---:|-------------|
| 1 | event-writer | `application/json` audit writes; archives Event JSON | S-G2, **W-G9** | 1 (pilot) | [event-writer](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212105) |
| 2 | distributor-rest | pure client rebind, S3 read-only | W-G9 | 2 | [distributor-rest](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212106) |
| 3 | splitter | canonical consumer rebind; ce- variant | W-G9 | 2 | [splitter](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212107) |
| 4 | ingestor | Jest/OpenSearch **v1 signer retained** (X-G8 corrected); ce- variant | **X-G8**, W-G9 | 2 | [ingestor](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212108) |
| 5 | dispatcher | local S3-event parser; zip put-with-metadata | S-G2, W-G9 | 3 | [dispatcher](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212125) |
| 6 | distributor | copy-with-replaced-metadata ×2 | **S-G2**, W-G9 | 3 | [distributor](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212126) |
| 7 | error-processor | archive put; email fan-out; closeWorkflow | S-G2, **W-G9** | 3 | [error-processor](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212128) |
| 8 | email-sender | SES v2; local Thymeleaf; reply-to | **X-G7** | 4 | [email-sender](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212131) |
| 9 | transformer | DynamoDB v2 `@DynamoDbVersionAttribute`; Contivo; ce-/os- | S-G2, W-G9 | 4 | [transformer](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212132) |
| 10 | watermill-publisher | AWS-layer rebind (gRPC untouched); boot `${awsps:}` creds | — | 5 | [watermill-publisher](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212135) |
| 11 | booking-inbound-consumer | DynamoDB v2 offset; port 8085 | W-G9 | 5 | [booking-inbound-consumer](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212136) |
| 12 | cargoscreen-consumer | DynamoDB v2 offset; S3-only | — | 5 | [cargoscreen-consumer](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212137) |
| 13 | itv-gps-consumer | DynamoDB v2 offset; S3-only (tenant INTTRA) | — | 5 | [itv-gps-consumer](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212138) |
| 14 | visibility-inbound-consumer | 3 gRPC consumers / 3 DynamoDB offsets; 3 SQS + SNS | W-G9 | 5 | [visibility-inbound-consumer](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212139) |

> Library modules (`schema-beans`, `gen2-parser`, `structuralvalidator`, `functional-testing`, `watermill/consumer-commons`) are not separate pages but are called out in each dependent module's Maven section; `consumer-commons` and `functional-testing` migrate alongside their consumers.

---

## Reference

- DW5/CVE baseline: [ION-16098 — AppianWay Dropwizard 4→5 / Jetty 12 CVE Remediation](https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212099)
- Related tickets: ION-16098 (DW5/Jetty12/CVE baseline), and the ION-12317 sub-tasks (OS/Visibility/Booking/MFT verification).

---

## Review

| Stage | Reviewer | Status | Notes |
|-------|----------|--------|-------|
| Design | @Arijit Kundu | Approved | |
| Product Owner | @Mahendran Pandian | Pending | |
| Pre Dev Security | @Kamalesh Bhol | Pending | cloud-sdk additive-change contract |
| Pre Dev Architecture | @Arijit Kundu | Pending | |
| QA | @Venkat Ganga | Pending | INT boot/health per module |
