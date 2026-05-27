# Dispatcher Module — Design Document

> **Module:** `dispatcher`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.dispatcher:dispatcher:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Guice 7.x

---

## 1. Executive Summary

The **Dispatcher** is the gateway microservice of the AppianWay pipeline. It monitors an S3 inbound bucket via SQS event notifications, extracts metadata from file paths, applies preprocessors (ZIP decompression, integration profile filtering), and routes files to the appropriate downstream queue based on file type.

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    S3["S3 Inbound Bucket"] -->|ObjectCreated Event| SNS["SNS Topic"]
    SNS --> SQS["SQS Dispatcher Queue"]
    SQS --> D["🔷 DISPATCHER"]
    D -->|"Copy"| WS["S3 Workspace"]
    D -->|"Route by type"| Q1["SQS Splitter"]
    D -->|"Route 315_IFTSTA"| Q2["SQS CE-Splitter"]
    D -->|"Route WEBBL_PDF"| Q3["SQS WebBL-PDF"]
    D -->|"Booking Request"| Q4["SQS Booking Bridge"]
    D -->|"Events"| EVT["SNS Event Store"]
    D -->|"Errors"| ERR["SQS Errors"]
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Dispatcher Service"
        APP[DispatcherApplication]
        MOD[DispatcherModule + ExternalServicesModule]
        LM[ListenerManager]
        SL[SQSListener]
        AD[AsyncDispatcher]
        TF[TaskFactory]
        DT[DispatcherTask]
        
        subgraph "Preprocessing"
            PP[PreProcessors]
            IP[IgnorePreprocessor]
            ZP[ZipPreprocessor]
        end
        
        subgraph "Routing"
            RM[RouterManager]
        end
        
        subgraph "Services"
            SEP[S3EventParser]
            FFS[FileFilterService]
            EL[EventLogger]
            EH[DispatcherErrorHandler]
        end
    end
    
    APP --> MOD
    MOD --> LM --> SL --> AD --> TF --> DT
    DT --> SEP
    DT --> PP --> IP & ZP
    DT --> RM
    DT --> EL
    DT --> EH
    IP --> FFS
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class DispatcherApplication {
        -externalServiceModule: Module
        +main(String[] args)
        +initialize(Bootstrap)
        +run(DispatcherConfiguration, Environment)
    }

    class DispatcherTask {
        -configuration: DispatcherConfiguration
        -sqsClient: SQSClient
        -workspaceService: WorkspaceService
        -errorHandler: DispatcherErrorHandler
        -eventLogger: EventLogger
        -preProcessors: PreProcessors
        -routerManager: RouterManager
        +process(Message, String)
        -getArchiveFormatType(String): String
        -buildMetaData(): MetaData
        -copyInitialFileToWorkspace()
        -sendMessageAndPublishCloseRunEvent()
    }

    class S3EventParser {
        +parse(String json): S3Event
    }

    class S3Event {
        -bucket: String
        -key: String
        -size: long
        -createdTime: String
        +isValid(): boolean
        +getMftId(): String
    }

    class RouterManager {
        -routeMappings: Map~String,String~
        +getRoutingQueue(MetaData): String
    }

    class PreProcessors {
        -preprocessors: List~PreProcessor~
        +process(S3Event, Message, String)
    }

    class PreProcessor {
        <<interface>>
        +process(S3Event, Message, String)
    }

    class IgnorePreprocessor {
        -fileFilterService: FileFilterService
        +process(S3Event, Message, String)
    }

    class ZipPreprocessor {
        -workspaceService: WorkspaceService
        +process(S3Event, Message, String)
    }

    class FileFilterService {
        -cache: LoadingCache
        +isMatch(String, String): boolean
    }

    class DispatcherErrorHandler {
        +handleException(Message, ...)
    }

    DispatcherApplication --> DispatcherTask
    DispatcherTask --> S3EventParser
    DispatcherTask --> RouterManager
    DispatcherTask --> PreProcessors
    PreProcessors --> PreProcessor
    PreProcessor <|.. IgnorePreprocessor
    PreProcessor <|.. ZipPreprocessor
    IgnorePreprocessor --> FileFilterService
    DispatcherTask --> DispatcherErrorHandler
    S3EventParser --> S3Event
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant S3 as S3 Inbound
    participant SQS as SQS Pickup
    participant DT as DispatcherTask
    participant SEP as S3EventParser
    participant PP as PreProcessors
    participant WS as S3 Workspace
    participant RM as RouterManager
    participant OUT as Target Queue
    participant SNS as SNS Events

    SQS->>DT: receiveMessage (batch 10, long poll 20s)
    DT->>SEP: parse(messageBody)
    SEP-->>DT: S3Event {bucket, key, size}
    DT->>S3: getObjectMetadata(bucket, key)
    S3-->>DT: xlogId, originalFileName, rootWorkflowId
    DT->>PP: process(s3Event, message, queueUrl)
    Note over PP: IgnorePreprocessor: check integration profile
    Note over PP: ZipPreprocessor: decompress if .zip
    DT->>WS: copyObject(inbound → workspace)
    DT->>RM: getRoutingQueue(metaData)
    RM-->>DT: target queue URL
    DT->>OUT: sendMessage(metaData JSON)
    DT->>SNS: logCloseRunEvent(SUCCESS)
```

---

## 6. Configuration Details

### 6.1 Main Configuration (`dispatcher.yaml`)

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `componentName` | String | `dispatcher` | Service identity |
| `errorRateThreshold` | Double | `5.0` | Max errors/sec (5-min window) |
| `sqsPickupConfig.queueUrl` | String | — | SQS pickup queue URL |
| `sqsPickupConfig.waitTimeSeconds` | int | `20` | Long polling duration |
| `sqsPickupConfig.maxNumberOfMessages` | int | `10` | Batch size |
| `sqsRouteMappingConfig` | Map | — | File type → queue URL mapping |
| `s3InboundPickupConfig.bucket` | String | — | Inbound S3 bucket |
| `s3WorkspaceConfig.bucket` | String | — | Workspace S3 bucket |
| `snsEventConfig.topicArn` | String | — | SNS event topic |
| `sqsErrorConfig.queueUrl` | String | — | Error queue |
| `networkServiceConfig.*` | Object | — | Network service endpoints |
| `bookingBridgeConfig.queueUrl` | String | — | Booking bridge queue |

### 6.2 Route Mappings

| File Type | Target Queue |
|-----------|-------------|
| `315_IFTSTA` | CE-Splitter queue |
| `WEBBL_PDF` | WebBL-PDF queue |
| `default` | Splitter queue |

### 6.3 Validation Rules

- File size must be > 0 bytes (throws `EmptyMessageException`)
- MFT ID must be extractable from S3 path index [3] (throws `UnableToResolveMftIdException`)
- Archive format type must be extractable from path index [0]
- Integration profile must match file type/MFT ID combination

---

## 7. Preprocessing Pipeline

```mermaid
flowchart TD
    A[S3 Event Received] --> B{IgnorePreprocessor}
    B -->|"Not in IP"| C[AbortProcessingException - Skip]
    B -->|"Match found"| D{ZipPreprocessor}
    D -->|".zip extension"| E[Decompress ZIP]
    E --> F[Write each entry to S3]
    F --> G[Publish event per entry]
    G --> H[AbortProcessingException - Done]
    D -->|"Not ZIP"| I[Continue normal processing]
```

---

## 8. Error Handling

| Exception | Error Code | Recovery |
|-----------|-----------|----------|
| `EmptyMessageException` | `/exception/dispatcher/business/messagePipeline/emptyFile` | Non-recoverable |
| `UnableToResolveMftIdException` | `/exception/dispatcher/business/.../unableToResolveMftId` | Non-recoverable |
| `UnableToResolveArchiveFormatTypeException` | `/exception/dispatcher/business/.../unableToResolveArchiveFormatType` | Non-recoverable |
| Unhandled | `/exception/dispatcher/system/messagePipeline/systemException` | System error |

---

## 9. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Base framework |
| `dropwizard-core` | 4.0.16 | REST application |
| `aws-java-sdk-sqs` | 1.12.720 | Queue messaging |
| `guice` | 7.0.0 | DI container |
| `guava` | 33.1.0-jre | Caching (FileFilterService) |
| `metrics-guice` | 3.1.3 | AOP metrics |

---

## 10. Health Checks

| Check | Category | Target |
|-------|----------|--------|
| `InboundSqsHealthCheck` | READ | Pickup queue accessible |
| `S3ReadHealthCheck` | READ | Inbound bucket readable |
| `ErrorThresholdHealthCheck` | READ | Error rate < threshold |
| `OutboundSqsHealthCheck` | WRITE | Output queues accessible |
| `S3WriteHealthCheck` | WRITE | Workspace writable |
| `SnsPublishHealthCheck` | WRITE | SNS topic publishable |

---

## 11. Deployment

```dockerfile
FROM openjdk:8
ADD dispatcher/target/dispatcher-1.0-SNAPSHOT.jar /app/
ADD dispatcher/conf/dispatcher.properties /app/
CMD java -jar /app/dispatcher-1.0-SNAPSHOT.jar run dispatcher.yaml /app/dispatcher.properties
EXPOSE 8080 8081
```

| Port | Purpose |
|------|---------|
| 8080 | Application |
| 8081 | Admin / Health checks |
