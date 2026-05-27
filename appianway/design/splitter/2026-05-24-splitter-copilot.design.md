# Splitter Module — Design Document

> **Module:** `splitter`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.splitter:splitter:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Guice 7.x

---

## 1. Executive Summary

The **Splitter** is the message parsing and decomposition engine of AppianWay. It receives batch EDI files from the Dispatcher, identifies the message format (EDIFACT, ANSI X12, XML, Rates, etc.), splits multi-transaction batches into individual messages, validates EDI envelopes, authenticates senders via integration profiles, and routes each message to context-specific downstream queues.

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    DISP["Dispatcher"] -->|"Batch file"| SQ["SQS Splitter"]
    SQ --> SP["🔷 SPLITTER"]
    SP -->|"Split messages"| WS["S3 Workspace"]
    SP -->|"Route by context"| RQ["SQS Router"]
    SP -->|"Booking"| BK["SQS Booking"]
    SP -->|"Schedule"| SCH["SQS Schedule"]
    SP -->|"Container Events"| CE["SQS CE"]
    SP -->|"Errors"| ERR["SQS Errors"]
    SP -->|"Events"| EVT["SNS Event Store"]
    
    style SP fill:#e67e22,color:#fff
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Splitter Service"
        APP[SplitterApplication]
        ST[SplitterTask]
        
        subgraph "Parser Selection"
            MPM[MessageParserManager]
            P1[Gen2EdifactMessageParser]
            P2[Gen2AnsiMessageParser]
            P3[RatesParser]
            P4[BKRequestXMLParser]
            P5[BKConfirmXMLParser]
            P6[ForecastParser]
            P7[SupplyParser]
            P8[BookingDesktop]
        end
        
        subgraph "Processing"
            STP[SplitTransactionProcessor]
            GH[GroupingHelper]
            MI[NetworkMessageIdentifier]
        end
        
        subgraph "Routing"
            RM[RouterManager]
            FBR[FormatBasedSQSRouter]
        end
        
        subgraph "Error Handling"
            SEH[SplitErrorHandler]
            BEH[BatchErrorHandler]
        end
    end
    
    APP --> ST
    ST --> MPM --> P1 & P2 & P3 & P4 & P5 & P6 & P7 & P8
    ST --> STP --> MI
    ST --> GH
    STP --> RM --> FBR
    ST --> SEH & BEH
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class SplitterTask {
        -workspaceService: WorkspaceService
        -parserManager: MessageParserManager
        -splitTransactionProcessor: SplitTransactionProcessor
        -groupingHelper: GroupingHelper
        -executor: ExecutorService
        +process(Message, String)
        -splitAndProcess()
        -processAllTransactions()
    }

    class MessageParser {
        <<interface>>
        +match(MetaData, String): boolean
        +init(String content)
        +getMessages(): List~Message~
        +groupMessage(MessageBatch, Message): MessageGroup
        +requiresSplitting(): boolean
        +getAttributes(): Map
        +validate(): List~BatchError~
    }

    class AbstractGen2Parser {
        #splitter: IMessageSplitter
        +match(MetaData, String): boolean
        +init(String content)
        +getMessages(): List~Message~
    }

    class SplitTransactionProcessor {
        -routerManager: RouterManager
        -messageIdentifier: NetworkMessageIdentifier
        -formatService: FormatService
        +validate(Message, String, Map): boolean
        +routeMessages()
    }

    class RouterManager {
        -routers: List~SQSRouter~
        +route(MetaData): RoutingResult
    }

    class FormatBasedSQSRouter {
        -formatService: FormatService
        -routeMappings: Map
        +tryRoute(MetaData): RoutingResult
    }

    class SplitErrorHandler {
        +handleSplitException()
        +handleRecoverableException()
        +handleNonRecoverableException()
    }

    SplitterTask --> MessageParser
    MessageParser <|.. AbstractGen2Parser
    AbstractGen2Parser <|-- Gen2EdifactMessageParser
    AbstractGen2Parser <|-- Gen2AnsiMessageParser
    MessageParser <|.. XMLParser
    MessageParser <|.. PassThroughParser
    SplitterTask --> SplitTransactionProcessor
    SplitTransactionProcessor --> RouterManager
    RouterManager --> FormatBasedSQSRouter
    SplitterTask --> SplitErrorHandler
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SQS as SQS Splitter
    participant ST as SplitterTask
    participant S3 as S3 Workspace
    participant MPM as ParserManager
    participant P as Parser
    participant MI as MessageIdentifier
    participant STP as TransactionProcessor
    participant RM as RouterManager
    participant OUT as Target Queue
    participant SNS as SNS Events

    SQS->>ST: receiveMessage (MetaData JSON)
    ST->>S3: getContent(bucket, fileName)
    S3-->>ST: file content
    ST->>MPM: getMessageParser(metaData, content)
    MPM->>P: match(metaData, content)
    P-->>MPM: true
    MPM-->>ST: selected parser
    ST->>P: init(content)
    ST->>P: validate()
    ST->>MI: authenticate(ediId, mftId)
    MI-->>ST: AuthorizationResponse (integrationProfileId)
    alt Parser requires splitting
        ST->>P: getMessages()
        P-->>ST: List<Message> (individual transactions)
        loop For each message group (parallel)
            ST->>STP: validate(message, ipId)
            ST->>STP: routeMessages()
            STP->>S3: putObject(split message)
            STP->>RM: route(metaData)
            RM->>OUT: sendMessage(metaData)
        end
    else Pass-through
        ST->>STP: routeMessages(singleMessage)
        STP->>RM: route(metaData)
        RM->>OUT: sendMessage(metaData)
    end
    ST->>SNS: logCloseRunEvent(SUCCESS)
```

---

## 6. Parser Strategy Matrix

| Parser | Format | Splitting | Match Logic |
|--------|--------|-----------|-------------|
| `Gen2EdifactMessageParser` | UN/EDIFACT | Yes | `matchEnvelope()` → UNB segment |
| `Gen2AnsiMessageParser` | ANSI X12 | Yes | `matchEnvelope()` → ISA segment |
| `RatesParser` | Rate sheets | No (pass-through) | FILE_TYPE contains "rate" |
| `BKRequestXMLParser` | Booking Request XML | No | Root element match |
| `BKConfirmXMLParser` | Booking Confirm XML | No | Root element match |
| `ForecastParser` | CFast Forecast | No | FILE_TYPE match |
| `SupplyParser` | CFast Supply | No | FILE_TYPE match |
| `BookingDesktop` | Desktop Booking | No | FILE_TYPE match |

---

## 7. EDI Splitting Process (EDIFACT Example)

```mermaid
flowchart TD
    FILE["UNB + UNH...UNT + UNH...UNT + UNH...UNT + UNZ"]
    FILE --> INIT["parser.init(content)"]
    INIT --> MSGS["getMessages()"]
    MSGS --> M1["Message 1: UNH...UNT"]
    MSGS --> M2["Message 2: UNH...UNT"]
    MSGS --> M3["Message 3: UNH...UNT"]
    M1 & M2 & M3 --> GROUP["groupMessage() by interchange + group"]
    GROUP --> G1["Group A: M1, M2"]
    GROUP --> G2["Group B: M3"]
    G1 & G2 --> PARALLEL["Process groups in parallel"]
```

**Grouping criteria:** Messages are grouped by:
- Interchange control reference number
- Group control number
- Message type code

---

## 8. Route Mapping Configuration

| Context Code | Target Queue | Business Domain |
|-------------|-------------|-----------------|
| `requestBooking` | Booking queue | Booking requests |
| `confirmBooking` | Booking Confirm queue | Booking confirmations |
| `submitSI` | SI queue | Shipping instructions |
| `publishContainerEvent` | CE queue | Container events |
| `publishSchedule` | Schedule queue | Vessel schedules |
| `publishRate` | Rate queue | Rate publications |
| `publishCFast` | CFast queue | Forecast/Supply |

---

## 9. Error Handling

| Exception | Error Code | Behavior |
|-----------|-----------|----------|
| `MandatoryElementNotProvidedException` | `/exception/splitter/business/.../mandatoryStructuralElementNotProvided` | Non-recoverable |
| `EmptyMessageTypeException` | `/exception/splitter/business/.../emptyMessageType` | Non-recoverable |
| `EmptyReleaseVersionException` | `/exception/splitter/business/.../emptyReleaseVersion` | Non-recoverable |
| `AuthorizationException` | `/exception/splitter/business/.../integrationProfileFormatNotFound` | Non-recoverable |
| `ParserNotFoundException` | `/exception/splitter/business/.../parserNotFound` | Non-recoverable |
| `EdiIdNotProvidedException` | `/exception/splitter/business/.../ediIdNotProvided` | Non-recoverable |
| `RecoverableException` | — | Retry via pickup queue |

### Error Flow

```mermaid
flowchart TD
    EX[Exception Thrown] --> SEH{SplitErrorHandler}
    SEH -->|Recoverable| RETRY[Re-send to pickup queue]
    SEH -->|Non-Recoverable| ANN[Write Annotations to S3]
    ANN --> ERRQ[Send to Error Queue]
    ERRQ --> EP[Error-Processor → Email]
```

---

## 10. Configuration Details

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `componentName` | String | `splitter` | Service identity |
| `healthCheckConfig.errorRateThreshold` | Double | `5.0` | Error rate limit |
| `sqsPickupConfig.queueUrl` | String | — | Splitter pickup queue |
| `sqsPickupConfig.waitTimeSeconds` | int | `20` | Long poll |
| `sqsPickupConfig.maxNumberOfMessages` | int | `10` | Batch/thread count |
| `sqsRouterConfig.queueUrl` | String | — | Default router queue |
| `sqsErrorConfig.queueUrl` | String | — | Error subscription queue |
| `snsEventConfig.topicArn` | String | — | Event topic |
| `s3WorkspaceConfig.bucket` | String | — | Workspace bucket |
| `enabledParsers` | List | 8 parsers | Parser class names (ordered) |
| `routeMappings` | Map | — | Context code → queue URL |
| `routersOrder` | List | `[format_based]` | Router chain priority |
| `networkServiceConfig.*` | Object | — | Network service endpoints |

---

## 11. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Framework, S3, SQS, events |
| `gen2-parser` | 1.0 | EDI splitting engine |
| `dropwizard-core` | 4.0.16 | Application framework |
| `guice` | 7.0.0 | DI container |
| `guava` | 33.1.0-jre | Utilities |
| `metrics-guice` | 3.1.3 | AOP metrics |
| `lombok` | 1.18.32 | Code generation |

---

## 12. Design Patterns

| Pattern | Usage |
|---------|-------|
| **Strategy** | 8 MessageParser implementations |
| **Chain of Responsibility** | RouterManager with ordered routers |
| **Template Method** | AbstractGen2Parser base |
| **Observer** | EventLogger for workflow events |
| **Fork-Join** | CompletableFuture parallel processing of message groups |
| **Factory** | TaskFactory for task instances |
