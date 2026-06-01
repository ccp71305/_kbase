# `splitter` — AWS SDK v2 (cloud-sdk) Upgrade DESIGN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata), G6 (config), G7 (health checks). The split-strategy parsing stays appianway-local (no cloud-sdk gap).
> Sections below are retained as the Option-A fallback reference.

> Module: `splitter` · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8) · Option **A**
> Companion: [plan](2026-05-31-splitter-aws2x-upgrade-plan-copilot.md). Foundation: [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md). Session `83b822b011714117`.

## 1. Overview
Standard-consumer rebind: replace v1 `Amazon{SQS,S3,SNS}` bindings in `ExternalServicesModule` with `cloud-sdk-aws` `MessagingClient`/`StorageClient`/`NotificationService`; switch task code from the v1 SQS `Message` DTO to `shared`'s `MessageRef`. Split-strategy logic unchanged. Dropwizard 4 / JUnit 4 retained.

## 2. Class diagram (Guice bindings before → after)
```mermaid
classDiagram
    class ExternalServicesModule_v1 {
        bind AmazonSQS(listener/sender)
        bind AmazonS3
        bind AmazonSNS
    }
    class ExternalServicesModule_v2 {
        bind MessagingClient~String~ (listener/sender)
        bind StorageClient
        bind NotificationService
    }
    class MessagingClient~String~ { <<cloud-sdk-api>> }
    class StorageClient { <<cloud-sdk-api>> }
    class NotificationService { <<cloud-sdk-api>> }
    ExternalServicesModule_v1 ..> ExternalServicesModule_v2 : rebind
    ExternalServicesModule_v2 --> MessagingClient
    ExternalServicesModule_v2 --> StorageClient
    ExternalServicesModule_v2 --> NotificationService
```

## 3. Component diagram
```mermaid
flowchart LR
    SQS[(inbound SQS)] --> L[shared SQSListener]
    L --> T[Splitter Task]
    T --> WS[shared WorkspaceService → StorageClient]
    WS --> S3[(S3 SDK v2)]
    T --> SPLIT[split strategy → child MetaData]
    T --> EL[shared EventLogger → NotificationService]
    EL --> SNS[(SNS SDK v2)]
    T --> OUT[MessagingClient.sendMessage → next stage SQS]
```

## 4. Sequence diagram
```mermaid
sequenceDiagram
    participant L as SQSListener (MessagingClient)
    participant T as Splitter Task
    participant WS as WorkspaceService (StorageClient)
    participant EL as EventLogger (NotificationService)
    L->>T: dispatch(MessageRef)
    T->>WS: getObject(bucket,key) container
    WS-->>T: payload
    T->>T: split → N child MetaData
    loop each child
        T->>WS: putObject(child body)
        T->>EL: START_/CLOSE_ split event
        T->>L: sendMessage(child) to next stage
    end
    T->>L: deleteMessage(receiptHandle)
```

## 5. Configuration changes
Per-role client config (`sqs_listener`/`sqs_sender`/`s3_read_put_copy`/`sns_publish`) maps to `cloud-sdk-aws` factory options via `shared`. `${PROFILE}`/`${ENV}` queue/bucket naming unchanged.

## 6. Maven dependency changes
- **Remove:** `aws-java-sdk-{sqs,s3,sns}` from `splitter/pom.xml`.
- **Add:** `cloud-sdk-api`, `cloud-sdk-aws`. Versions from root `dependencyManagement` (v2 BOM 2.30.24).

## 7. Test details
- Functional tests use `functional-testing` in-memory fakes re-pointed to `cloud-sdk-api` interfaces.
- Split-strategy unit tests unaffected.
- Any test referencing the v1 SQS `Message` → `MessageRef`/`QueueMessage`. JUnit 4 retained.

## 8. Rollout & verification
After `shared` + `functional-testing`. `mvn -pl splitter -am verify`.

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Override-config mapping gaps | Centralize in `shared`; functional-test assert |
| `Message`→`MessageRef` drift | Parity tests in `shared` |
| Child-message lineage regression | Preserve rootWorkflowId/workflowId/parentWorkflowId; assert |
