# `distributor-rest` — AWS SDK v2 (cloud-sdk) Upgrade DESIGN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata), G6 (config), G7 (health checks). REST/OAuth bearer egress stays appianway-local (no cloud-sdk gap).
> Sections below are retained as the Option-A fallback reference.

> Module: `distributor-rest` · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8) · Option **A**
> Companion: [plan](2026-05-31-distributor-rest-aws2x-upgrade-plan-copilot.md). Foundation: [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md). Session `83b822b011714117`.

## 1. Overview
Standard-consumer rebind only. Replace v1 `Amazon{SQS,S3,SNS}` bindings with `cloud-sdk-aws` `MessagingClient`/`StorageClient`/`NotificationService`; switch the egress task to `MessageRef`. HTTP/OAuth subscriber-POST logic unchanged. Dropwizard 4 / JUnit 4 retained.

## 2. Class diagram
```mermaid
classDiagram
    class ExternalServicesModule_v1 { bind AmazonSQS(listener/sender); bind AmazonS3; bind AmazonSNS }
    class ExternalServicesModule_v2 { bind MessagingClient~String~(listener/sender); bind StorageClient; bind NotificationService }
    class HttpEgressClient { <<JAX-RS + OAuth, unchanged>> }
    ExternalServicesModule_v1 ..> ExternalServicesModule_v2 : rebind
    ExternalServicesModule_v2 --> HttpEgressClient : unchanged
```

## 3. Component diagram
```mermaid
flowchart LR
    SQS[(inbound SQS)] --> L[shared SQSListener → MessagingClient]
    L --> T[RestEgress Task]
    T --> WS[WorkspaceService → StorageClient]
    WS --> S3[(S3 SDK v2)]
    T --> HTTP[HTTP POST OAuth bearer → subscriber endpoint]
    T --> EL[EventLogger → NotificationService]
    EL --> SNS[(SNS SDK v2)]
    note[HTTP/OAuth egress is non-AWS, unchanged]
```

## 4. Sequence diagram
```mermaid
sequenceDiagram
    participant L as SQSListener (MessagingClient)
    participant T as RestEgress Task
    participant WS as WorkspaceService (StorageClient)
    participant H as Subscriber endpoint
    participant EL as EventLogger (NotificationService)
    L->>T: dispatch(MessageRef)
    T->>WS: getObject(payload)
    WS-->>T: bytes
    T->>H: POST payload (OAuth bearer)
    H-->>T: 2xx
    T->>EL: CLOSE_ delivery event (success)
    T->>L: deleteMessage(receiptHandle)
```

## 5. Configuration changes
Per-role client config maps to `cloud-sdk-aws` options via `shared`. Subscriber-endpoint / OAuth config unchanged. `${PROFILE}`/`${ENV}` naming unchanged.

## 6. Maven dependency changes
- **Remove:** `aws-java-sdk-{sqs,s3,sns}` from `distributor-rest/pom.xml`.
- **Add:** `cloud-sdk-api`, `cloud-sdk-aws`. Versions from root `dependencyManagement` (v2 BOM 2.30.24).

## 7. Test details
- Functional tests use `functional-testing` fakes re-pointed to `cloud-sdk-api`.
- HTTP-egress tests (WireMock) unaffected. `Message`→`MessageRef` in any affected test. JUnit 4 retained.

## 8. Rollout & verification
After `shared` + `functional-testing`. `mvn -pl distributor-rest -am verify`.

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Override-config mapping gaps | Centralize in `shared`; functional-test assert |
| `Message`→`MessageRef` drift | Parity tests in `shared` |
| Egress regression | Keep AWS-boundary-only scope; WireMock tests green |
