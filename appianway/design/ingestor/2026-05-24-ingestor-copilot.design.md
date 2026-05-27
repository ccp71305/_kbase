# Ingestor Module — Design Document

> **Module:** `ingestor`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.ingestor:ingestor:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Guice 7.x + Elasticsearch (Jest)

---

## 1. Executive Summary

The **Ingestor** is the real-time analytics and tracking engine of AppianWay. It subscribes to the SNS event topic, enriches events with business metadata (formats, integration profiles, file tracking), builds searchable aggregate documents, and indexes everything into Elasticsearch — powering the transaction tracking dashboard.

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    ALL["All Pipeline Components"] -->|"Events"| SNS["SNS Event Store"]
    SNS -->|"Subscribe"| SQS["SQS Ingestor"]
    SQS --> ING["🔷 INGESTOR"]
    ING -->|"Index events"| ES["Elasticsearch<br/>txtrack-event-*"]
    ING -->|"Upsert aggregates"| ESA["Elasticsearch<br/>txtrack-agg-*"]
    ING -->|"Enrich"| NET["Network Services"]
    
    style ING fill:#9b59b6,color:#fff
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Ingestor Service"
        APP[IngestorApplication]
        LM[ListenerManager]
        IT[IngestorTask]
        
        subgraph "Event Processing"
            B[Builders - Attribute Extraction]
            T[Transformers - Enrichment]
            ER[ElasticSearchEventRepository]
        end
        
        subgraph "Builders (8 strategies)"
            B1[StartWorkflowAttributeBuilder]
            B2[EndWorkflowAttributeBuilder]
            B3[ErrorAttributeBuilder]
            B4[SplitterAttributeBuilder]
            B5[TokenAttributeBuilder]
            B6[OutTransformerAttributeBuilder]
            B7[PropagateBatchAttributes]
            B8[OBBridgeAttributeBuilder]
        end
        
        subgraph "Maintenance"
            DEL[DeleteExpiredIndex]
            SCH[Scheduler - wisp]
        end
    end
    
    APP --> LM --> IT
    IT --> B --> B1 & B2 & B3 & B4 & B5 & B6 & B7 & B8
    IT --> T
    IT --> ER
    DEL --> SCH
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class IngestorTask {
        -eventRepository: EventRepository
        -builders: Builders
        -sqsClient: SQSClient
        -transformers: List~Transformer~
        +process(List~Message~)
        +execute(List~Message~, String)
    }

    class Builders {
        -builders: TrackingBuilder[]
        +getTrackingMetaData(Event): List~TrackingMetaData~
    }

    class TrackingBuilder {
        <<interface>>
        +match(Event): boolean
        +build(Event): List~TrackingMetaData~
    }

    class EventRepository {
        <<interface>>
        +submitEvent(List~Event~, Map~String,List~TrackingMetaData~~)
    }

    class ElasticSearchEventRepository {
        -client: JestClient
        -retryer: Retryer
        +submit(Action): JestResult
        +submitEvent(List~Event~, Map)
        -buildUpsertTrackingAggregate(Map, String, String): Action
        -getCurrentEventIndexName(): String
        -getCurrentAggIndexName(): String
    }

    class Transformer {
        <<interface>>
        +match(Event): boolean
        +transform(Event)
    }

    class ErrorTransformer {
        -s3WorkspaceService: S3WorkspaceService
        +match(Event): boolean
        +transform(Event)
    }

    class DeleteExpiredIndex {
        -indexESService: IndexESService
        -clock: Clock
        +deleteExpiredIndexes()
    }

    IngestorTask --> Builders
    IngestorTask --> EventRepository
    Builders --> TrackingBuilder
    EventRepository <|.. ElasticSearchEventRepository
    Transformer <|.. ErrorTransformer
    IngestorTask --> Transformer
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SQS as SQS Ingestor
    participant IT as IngestorTask
    participant T as Transformers
    participant B as Builders
    participant ES as Elasticsearch

    SQS->>IT: receiveMessages (batch)
    IT->>IT: Parse events from SNS notifications
    IT->>T: transform(events)
    Note over T: ErrorTransformer: fetch error annotations from S3
    loop For each Event
        IT->>B: getTrackingMetaData(event)
        Note over B: Match applicable builders<br/>Extract attributes
        B-->>IT: List<TrackingMetaData>
    end
    IT->>ES: submitEvent(events, trackingMap)
    Note over ES: Bulk index events → txtrack-event-yyyy-MM-dd
    Note over ES: Upsert aggregates → txtrack-agg-yyyy-MM-dd
```

---

## 6. Builder Strategy Pattern

Each builder extracts specific attributes from events:

| Builder | Matches | Extracts |
|---------|---------|----------|
| `StartWorkflowAttributeBuilder` | `startWorkflow` or `closeRun(START_WORKFLOW)` | `startTimestamp` |
| `EndWorkflowAttributeBuilder` | `closeWorkflow` or `closeRun(CLOSE_WORKFLOW)` | `endTimestamp` |
| `ErrorAttributeBuilder` | `closeRun` with `status=failure` | `status: failure` |
| `TokenAttributeBuilder` | Any `closeRun` | All event tokens |
| `SplitterAttributeBuilder` | Component=splitter + closeRun | format, context, direction, ipName |
| `OutTransformerAttributeBuilder` | Component=transformer + targetId | Outbound format context |
| `PropagateBatchAttributes` | Splitter/CE-splitter + mftId | ediId, xlogId, filenames |
| `OBBridgeAttributeBuilder` | Component=awbridgeob + closeRun | FTP delivery/archive info |

---

## 7. Elasticsearch Index Strategy

### Dual-Index Architecture

| Index Pattern | Purpose | Document Type |
|---------------|---------|---------------|
| `txtrack-event-yyyy-MM-dd` | Raw events | Individual event JSON |
| `txtrack-agg-yyyy-MM-dd` | Workflow aggregates | Merged tracking metadata |

### Aggregate Upsert Strategy

```mermaid
flowchart TD
    E[Event arrives] --> B[Builders extract attributes]
    B --> AGG{Aggregate exists?}
    AGG -->|No| CREATE[doc_as_upsert: create new]
    AGG -->|Yes| UPDATE[Merge attributes into existing]
    AGG -->|409 Conflict| RETRY[Retry with exponential backoff]
```

- **Retry on conflict:** 5 attempts for version conflicts
- **Exponential backoff:** 100ms base, 3 max attempts

---

## 8. Index Maintenance

The `DeleteExpiredIndex` job runs on a scheduled interval:

1. Lists all indices matching `txtrack-event-*` and `txtrack-agg-*`
2. Extracts date from index name
3. Compares against configured retention days
4. Deletes expired indices

---

## 9. Configuration Details

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `pickupSqsConfig.queueUrl` | String | — | Ingestor SQS queue |
| `pickupSqsConfig.waitTimeSeconds` | int | `20` | Long poll |
| `pickupSqsConfig.maxNumberOfMessages` | int | `10` | Batch size |
| `listenerThreads` | int | — | SQS listener thread count |
| `esEventStoreConfig.endpointUrl` | String | — | ES cluster URL |
| `esEventStoreConfig.region` | String | — | AWS region for signing |
| `esEventStoreConfig.service` | String | — | AWS service (`es`) |
| `deleteIndexSchedulerConfig.*` | Object | — | Retention and schedule |
| `networkServiceConfig.*` | Object | — | Format/IP service endpoints |

---

## 10. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Framework, S3, SQS |
| `jest` | 6.3.1 | Elasticsearch REST client |
| `elasticsearch-transport` | 7.17.10 | ES transport client |
| `aws-signing-request-interceptor` | 0.0.16 | AWS Signature V4 for ES |
| `wisp` | 1.0.0 | Job scheduler |
| `gson` | 2.10.1 | JSON for ES |
| `netty-*` | 4.2.7 | Network I/O |
| `dropwizard-core` | 4.0.16 | Application framework |
| `guice` | 7.0.0 | DI container |
