# Watermill Module — Design Document

> **Module:** `watermill`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.watermill:watermill:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Guice 7.x + gRPC 1.77.0 + Protobuf 4.33.1

---

## 1. Executive Summary

The **Watermill** is a multi-module gRPC streaming consumer suite that ingests real-time events from E2Open's event streaming platform. It subscribes to topics (Booking, ITV/GPS, Cargo Screen, Visibility) via bidirectional gRPC streams, transforms incoming Protobuf messages into AppianWay's canonical XML format, and injects them into the pipeline via S3 + SQS. It includes DynamoDB-based offset tracking for reliable at-least-once delivery.

---

## 2. Sub-Module Structure

```mermaid
graph TB
    subgraph "watermill (parent POM)"
        CC[consumer-commons]
        BIC[booking-inbound-consumer]
        ITV[itv-gps-consumer]
        CS[cargoscreen-consumer]
        VIC[visibility-inbound-consumer]
    end
    
    CC -->|"dependency"| BIC & ITV & CS & VIC
    
    style CC fill:#2980b9,color:#fff
    style BIC fill:#27ae60,color:#fff
    style ITV fill:#f39c12,color:#fff
    style CS fill:#8e44ad,color:#fff
    style VIC fill:#c0392b,color:#fff
```

---

## 3. Role in the Pipeline

```mermaid
flowchart LR
    E2O["E2Open Event Stream<br/>(gRPC)"] --> WM["🔷 WATERMILL"]
    
    subgraph WM["Watermill Consumers"]
        BIC["Booking Consumer"]
        ITV["ITV/GPS Consumer"]
        CS["CargoScreen Consumer"]
        VIC["Visibility Consumer"]
    end
    
    BIC -->|"Canonical XML"| S3["S3 Workspace"]
    ITV -->|"Canonical XML"| S3
    CS -->|"Canonical XML"| S3
    VIC -->|"Canonical XML"| S3
    
    S3 -->|"Triggers"| DISP["Dispatcher → Pipeline"]
    WM -->|"Offsets"| DDB["DynamoDB"]
    
    style WM fill:#2c3e50,color:#fff
```

---

## 4. Consumer-Commons Architecture

The shared infrastructure for all consumers:

```mermaid
classDiagram
    class AbstractStreamConsumer {
        #grpcChannel: ManagedChannel
        #offsetManager: OffsetManager
        #configuration: ConsumerConfiguration
        +start()
        +stop()
        #onMessage(StreamMessage): void
        #buildChannel(): ManagedChannel
    }

    class OffsetManager {
        -dynamoDBClient: DynamoDB
        -tableName: String
        -scheduler: OffsetUpdateScheduler
        +getCurrentOffset(String topic): Long
        +updateOffset(String topic, Long offset)
        +persistOffsets()
    }

    class OffsetUpdateScheduler {
        -scheduler: ScheduledExecutorService
        -pendingOffsets: ConcurrentHashMap
        +schedule(String topic, Long offset)
        +flush()
    }

    class ConsumerConfiguration {
        -grpcHost: String
        -grpcPort: int
        -topics: List~String~
        -clientId: String
        -offsetTable: String
    }

    class StreamMessage {
        -topic: String
        -offset: Long
        -key: String
        -payload: byte[]
        -timestamp: Instant
    }

    AbstractStreamConsumer --> OffsetManager
    OffsetManager --> OffsetUpdateScheduler
    AbstractStreamConsumer --> ConsumerConfiguration
    AbstractStreamConsumer --> StreamMessage
```

---

## 5. Booking-Inbound-Consumer

The largest sub-module (81 files) handling booking message transformation:

```mermaid
graph TB
    subgraph "Booking Inbound Consumer"
        BC[BookingConsumer]
        BT[BookingTransformer]
        
        subgraph "TypeMap Transformers (60+)"
            TM1[BookingHeaderTypeMap]
            TM2[CarrierTypeMap]
            TM3[ContainerTypeMap]
            TM4[LocationTypeMap]
            TM5[PartyTypeMap]
            TM6[CommodityTypeMap]
            TM7["... 54 more"]
        end
        
        subgraph "Output"
            XB[XML Builder]
            S3W[S3 Writer]
        end
    end
    
    BC --> BT --> TM1 & TM2 & TM3 & TM4 & TM5 & TM6 & TM7
    BT --> XB --> S3W
```

### BookingTransformer Chain

```mermaid
sequenceDiagram
    participant BC as BookingConsumer
    participant BT as BookingTransformer
    participant TM as TypeMappers
    participant XB as XML Builder
    participant S3 as S3 Workspace
    participant SQS as SQS Pipeline

    BC->>BT: transform(protobufBooking)
    BT->>TM: mapHeader(booking.header)
    BT->>TM: mapCarrier(booking.carrier)
    BT->>TM: mapLocations(booking.locations)
    BT->>TM: mapContainers(booking.containers)
    BT->>TM: mapParties(booking.parties)
    BT->>TM: mapCommodities(booking.commodities)
    TM-->>BT: mapped XML elements
    BT->>XB: buildCanonicalXML(elements)
    XB-->>BT: canonical XML string
    BT->>S3: putObject(bucket, key, xml)
    BT->>SQS: sendMessage(metaData)
```

---

## 6. Visibility-Inbound-Consumer

Handles container visibility events with multiple consumer types:

```mermaid
graph TB
    subgraph "Visibility Inbound Consumer"
        CM[ConsumerManager]
        
        subgraph "Consumers"
            VC[VisibilityConsumer]
            SC[SubscriptionConsumer]
            EC[EventConsumer]
        end
        
        subgraph "Transformation"
            CET[ContainerEventTransformer]
        end
        
        subgraph "Reconnection"
            RCN[ReconnectionHandler]
        end
    end
    
    CM --> VC & SC & EC
    CM --> RCN
    VC & SC & EC --> CET
```

### ConsumerManager Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Starting
    Starting --> Connected: gRPC stream established
    Connected --> Consuming: Receiving messages
    Consuming --> Consuming: onMessage()
    Consuming --> Disconnected: Stream error/timeout
    Disconnected --> Reconnecting: Exponential backoff
    Reconnecting --> Connected: Reconnection success
    Reconnecting --> Disconnected: Reconnection failed
    Connected --> Stopping: shutdown()
    Consuming --> Stopping: shutdown()
    Stopping --> [*]
```

---

## 7. DynamoDB Offset Tracking

```mermaid
flowchart TD
    MSG["Message received (offset=12345)"] --> PEND["pendingOffsets.put(topic, 12345)"]
    PEND --> SCHED["OffsetUpdateScheduler (every N seconds)"]
    SCHED --> FLUSH["Batch write to DynamoDB"]
    FLUSH --> DDB["DynamoDB offset-table<br/>PK: clientId-topic<br/>offset: 12345"]
    
    subgraph "On Restart"
        START["Consumer starts"] --> READ["Read current offset from DynamoDB"]
        READ --> RESUME["Subscribe from offset + 1"]
    end
```

**Offset persistence strategy:**
- Offsets are batched in memory (ConcurrentHashMap)
- Periodic flush (scheduler) persists to DynamoDB
- On graceful shutdown: final flush
- On crash: messages since last flush are re-delivered (at-least-once)

---

## 8. gRPC Streaming Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `grpcHost` | String | — | E2Open streaming endpoint |
| `grpcPort` | int | `443` | gRPC port |
| `useTls` | boolean | `true` | Enable TLS |
| `clientId` | String | — | Consumer identity |
| `topics` | List | — | Subscribed topics |
| `keepAliveTime` | Duration | `30s` | gRPC keepalive |
| `keepAliveTimeout` | Duration | `10s` | Keepalive timeout |
| `maxInboundMessageSize` | int | `4MB` | Max message bytes |
| `reconnectBackoff` | Duration | `5s` | Initial reconnect delay |
| `reconnectMaxBackoff` | Duration | `60s` | Max reconnect delay |

---

## 9. Configuration Details

| Property | Type | Description |
|----------|------|-------------|
| `consumers[].type` | String | `booking`, `visibility`, `itv-gps`, `cargoscreen` |
| `consumers[].grpcConfig.*` | Object | Per-consumer gRPC settings |
| `consumers[].topics` | List | Topic subscriptions |
| `dynamoDBConfig.tableName` | String | Offset tracking table |
| `dynamoDBConfig.region` | String | AWS region |
| `s3WorkspaceConfig.bucket` | String | Output bucket |
| `sqsDropOffConfig.queueUrl` | String | Pipeline entry queue |
| `offsetFlushInterval` | Duration | DynamoDB write frequency |
| `healthCheck.maxLag` | Duration | Max acceptable consumer lag |

---

## 10. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `grpc-netty-shaded` | 1.77.0 | gRPC transport |
| `grpc-protobuf` | 1.77.0 | Protobuf serialization |
| `grpc-stub` | 1.77.0 | Generated stubs |
| `protobuf-java` | 4.33.1 | Protobuf runtime |
| `mercury-shared` | 1.0 | S3, SQS, DynamoDB |
| `dropwizard-core` | 4.0.16 | Application framework |
| `guice` | 7.0.0 | DI container |
| `aws-java-sdk-dynamodb` | 1.12.720 | Offset persistence |
| `netty-*` | 4.2.7 | Network I/O |

---

## 11. Error Handling

| Scenario | Behavior |
|----------|----------|
| gRPC stream error | Reconnect with exponential backoff |
| Transformation failure | Log error, skip message, advance offset |
| DynamoDB write failure | Retry; consumer pauses if persistent |
| S3 upload failure | Retry (shared ExternalCallWrapper) |
| Protobuf parse error | Log + skip (corrupted message) |
| Consumer lag excessive | Health check fails |

---

## 12. Design Patterns

| Pattern | Usage |
|---------|-------|
| **Template Method** | AbstractStreamConsumer base for all consumers |
| **Observer** | gRPC StreamObserver for message delivery |
| **Mapper** | 60+ TypeMap classes (Protobuf → XML) |
| **Scheduler** | OffsetUpdateScheduler for batched persistence |
| **Circuit Breaker** | Reconnection with backoff |
| **Pipeline** | ConsumerManager → Transformer → Writer chain |
