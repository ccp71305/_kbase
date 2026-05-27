# Event-Writer Module — Design Document

> **Module:** `event-writer`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.eventstore:event-writer:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Guice 7.x

---

## 1. Executive Summary

The **Event-Writer** is the audit trail and observability backbone of AppianWay. It subscribes to the shared SNS event topic (via SQS), converts workflow events to structured JSON, and persists them to S3 with a date-partitioned, workflow-correlated path structure — forming the platform's event store.

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    D["Dispatcher"] & SP["Splitter"] & TF["Transformer"] & DI["Distributor"] & EP["Error-Processor"] -->|"Events"| SNS["SNS Event Store"]
    SNS -->|"Subscribe"| SQS["SQS Event Store"]
    SQS --> EW["🔷 EVENT-WRITER"]
    EW -->|"Persist"| S3["S3 Event Store"]
    
    style EW fill:#2ecc71,color:#fff
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Event-Writer Service"
        APP[EventWriterApplication]
        LM[ListenerManager]
        SL[SQSListener]
        AD[AsyncDispatcher]
        
        subgraph "Processing"
            TASK[SQSMessageWriterTask]
            HANDLER[S3StoringMessageHandler]
            CONV[SQSMessageToEventConverter]
        end
    end
    
    APP --> LM --> SL --> AD --> TASK --> HANDLER --> CONV
    HANDLER -->|"Write"| S3["S3 Event Store Bucket"]
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class EventWriterApplication {
        -externalServiceModule: Module
        +main(String[] args)
        +run(EventWriterConfiguration, Environment)
    }

    class SQSMessageWriterTask {
        -sqsClient: SQSClient
        -handler: SQSMessageHandler
        +process(Message, String)
    }

    class SQSMessageHandler {
        <<interface>>
        +handle(Message)
    }

    class S3StoringMessageHandler {
        -workspaceService: WorkspaceService
        -configuration: EventWriterConfiguration
        -formatter: DateTimeFormatter
        +handle(Message)
        -composePath(Event): String
        -handleException(Exception)
    }

    class SQSMessageToEventConverter {
        +convert(Message): List~Event~$
        -getEventStoreMsgFromSNSMessage(Message): List~Event~$
    }

    class EventWriterConfiguration {
        -errorRateThreshold: Double
        -pickupSqsConfig: SQSConfig
        -s3Config: S3Config
        -s3EventStorePath: String
    }

    SQSMessageWriterTask --> SQSMessageHandler
    SQSMessageHandler <|.. S3StoringMessageHandler
    S3StoringMessageHandler --> SQSMessageToEventConverter
    EventWriterApplication --> SQSMessageWriterTask
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SQS as SQS Event Queue
    participant TASK as SQSMessageWriterTask
    participant CONV as MessageToEventConverter
    participant HANDLER as S3StoringMessageHandler
    participant S3 as S3 Event Store

    SQS->>TASK: receiveMessage (batch 10, long poll 20s)
    TASK->>HANDLER: handle(message)
    HANDLER->>CONV: convert(message)
    alt Direct JSON Array
        CONV-->>HANDLER: List<Event>
    else SNS-wrapped
        CONV->>CONV: unwrap SNS notification
        CONV-->>HANDLER: List<Event>
    end
    loop For each Event
        HANDLER->>HANDLER: composePath(event)
        Note over HANDLER: eventstore/2026-05-24/{rootWorkflowId}/{component}-{type}-{eventId}.json
        HANDLER->>S3: putObject(bucket, path, event JSON)
    end
```

---

## 6. S3 Path Structure

The event-writer creates a well-organized S3 hierarchy:

```
{s3EventStorePath}/
└── {yyyy-MM-dd}/
    └── {rootWorkflowId}/
        ├── dispatcher-startRun-{eventId}.json
        ├── dispatcher-closeRun-{eventId}.json
        ├── splitter-startRun-{eventId}.json
        ├── splitter-closeRun-{eventId}.json
        ├── transformer-startRun-{eventId}.json
        └── transformer-closeRun-{eventId}.json
```

**Path composition:** `{eventStoreDir}/{date}/{rootWorkflowId}/{component}-{type}-{eventId}.json`

---

## 7. Event JSON Structure

```json
{
  "eventId": "uuid",
  "category": "system|application",
  "component": "dispatcher|splitter|transformer|distributor",
  "timestamp": "2026-05-24T13:24:21.33",
  "workflowId": "uuid",
  "parentWorkflowId": "uuid",
  "rootWorkflowId": "uuid",
  "runId": "uuid",
  "startTimestamp": "timestamp",
  "type": "startRun|closeRun|metrics",
  "subType": "START_WORKFLOW|CLOSE_WORKFLOW",
  "tokens": { "key": "value" },
  "eventContent": { ... }
}
```

---

## 8. Message Conversion (Dual Format Support)

The converter handles two message formats:

```mermaid
flowchart TD
    MSG[SQS Message Body] --> TRY{Parse as JSON Array?}
    TRY -->|Success| LIST["List<Event>"]
    TRY -->|Fail| SNS{Parse as SNS Notification?}
    SNS --> EXTRACT[Extract .message field]
    EXTRACT --> LIST2["List<Event>"]
```

This supports both direct event publishing and SNS-forwarded events.

---

## 9. Configuration Details

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `errorRateThreshold` | Double | `5.0` | Error rate for health check |
| `pickupSqsConfig.queueUrl` | String | — | Event subscription queue |
| `pickupSqsConfig.waitTimeSeconds` | int | `20` | Long poll duration |
| `pickupSqsConfig.maxNumberOfMessages` | int | `10` | Batch size |
| `s3Config.bucket` | String | — | S3 event store bucket |
| `s3EventStorePath` | String | — | Base path (e.g., `eventstore`) |

---

## 10. Error Handling & Metrics

| Metric | Annotation | Purpose |
|--------|-----------|---------|
| `messages-failed` | `@Metered` | Counts failed message processing |

- **Error strategy:** Log exception at ERROR level, increment metric counter
- **No DLQ routing:** Errors are absorbed and metered (events are non-critical)
- **Health check:** `ErrorThresholdHealthCheck` triggers if failure rate exceeds threshold

---

## 11. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Framework, S3, SQS |
| `dropwizard-core` | 4.0.16 | Application framework |
| `guice` | 7.0.0 | DI container |
| `guava` | 33.1.0-jre | Utilities |
| `metrics-guice` | 3.1.3 | AOP metrics |
| `lombok` | 1.18.32 | Code generation |

---

## 12. Health Checks

| Check | Category | Target |
|-------|----------|--------|
| `InboundSqsHealthCheck` | READ | Event queue accessible |
| `ErrorThresholdHealthCheck` | READ | Failure rate < 5.0 |
| `S3WriteHealthCheck` | WRITE | Event store bucket writable |
