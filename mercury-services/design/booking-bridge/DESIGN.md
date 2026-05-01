# Booking Bridge Service - Design Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Application Initialization Flow](#application-initialization-flow)
4. [Configuration Management](#configuration-management)
5. [Key Components](#key-components)
6. [AWS Service Integration](#aws-service-integration)
7. [Cloud SDK Integration](#cloud-sdk-integration)
8. [Data Access Layer](#data-access-layer)
9. [Message Processing Flow](#message-processing-flow)
10. [Dependency Diagram](#dependency-diagram)
11. [Test Coverage](#test-coverage)

---

## Overview

The **Booking Bridge Service** is a microservice that enables the following:
1) Stop the cloud booking request/confirms flow to the legacy system
2) Decide which bookings needs to flow to the legacy system
It processes booking messages from SQS queues, validates and transforms data, stores tracking information in DynamoDB, routes messages to IBM MQ, and publishes events to SNS.


### Key Responsibilities
- **Message Consumption**: Listens to SQS queues for incoming booking messages
- **Data Validation**: Validates xlog IDs and prevents duplicate processing
- **Data Persistence**: Stores xlog tracking details in DynamoDB with TTL
- **Message Routing**: Routes validated messages to IBM MQ queues
- **Event Publishing**: Publishes workflow events to SNS topics
- **Lock Management**: Manages distributed locks via Network Services Message Register

### Technology Stack
- **Framework**: Dropwizard 4.0.x
- **Dependency Injection**: Google Guice
- **AWS SDK**: Version 2 (via cloud-sdk-aws)
- **Messaging**: SQS, SNS (via cloud-sdk-api)
- **Database**: DynamoDB (via cloud-sdk-api Enhanced Client)
- **Queue System**: IBM MQ 8.0.x
- **Testing**: JUnit 5, Mockito 5, AssertJ 3

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Booking Bridge Service                        │
│                                                                   │
│  ┌────────────────┐        ┌──────────────────┐                 │
│  │ SQS Listener   │───────▶│ Processor Task   │                 │
│  │ (Consumer)     │        │ (Async Executor) │                 │
│  └────────────────┘        └──────────────────┘                 │
│                                     │                             │
│                                     ▼                             │
│                            ┌────────────────────┐                │
│                            │ BookingBridge      │                │
│                            │ Service            │                │
│                            └────────────────────┘                │
│                                     │                             │
│                    ┌────────────────┼────────────────┐           │
│                    ▼                ▼                ▼           │
│           ┌─────────────┐  ┌──────────────┐ ┌──────────────┐   │
│           │ XlogDetail  │  │ MQ Service   │ │ Message      │   │
│           │ DAO         │  │ (IBM MQ)     │ │ Register Svc │   │
│           └─────────────┘  └──────────────┘ └──────────────┘   │
│                    │                │                │           │
└────────────────────┼────────────────┼────────────────┼───────────┘
                     ▼                ▼                ▼
              ┌──────────┐    ┌──────────┐    ┌────────────┐
              │ DynamoDB │    │ IBM MQ   │    │  Network   │
              │ (XLog)   │    │  Queue   │    │  Services  │
              └──────────┘    └──────────┘    └────────────┘
```

### Component Interaction

```
External Systems                Booking Bridge                  AWS/External Services
┌─────────────┐                                                  ┌─────────────┐
│   SQS       │──┐                                              │  DynamoDB   │
│   Queue     │  │                                              │  (XLog)     │
└─────────────┘  │                                              └─────────────┘
                 │                                                     ▲
                 ▼                                                     │
         ┌───────────────┐                                     ┌──────────────┐
         │ SQS Listener  │                                     │ XlogDetail   │
         │  (cloud-sdk)  │                                     │    DAO       │
         └───────────────┘                                     └──────────────┘
                 │                                                     ▲
                 ▼                                                     │
         ┌───────────────────┐                              ┌─────────────────┐
         │  Processor Task   │                              │ BookingBridge   │
         │  (Async Executor) │────────────────────────────▶│    Service      │
         └───────────────────┘                              └─────────────────┘
                                                                     │
                                                     ┌───────────────┼───────────────┐
                                                     ▼               ▼               ▼
                                              ┌───────────┐  ┌──────────┐  ┌────────────┐
                                              │    MQ     │  │  Event   │  │  Message   │
                                              │  Service  │  │  Logger  │  │  Register  │
                                              └───────────┘  └──────────┘  └────────────┘
                                                     │              │               │
                                                     ▼              ▼               ▼
                                              ┌───────────┐  ┌──────────┐  ┌────────────┐
                                              │  IBM MQ   │  │   SNS    │  │  Network   │
                                              │  Queue    │  │  Topic   │  │  Services  │
                                              └───────────┘  └──────────┘  └────────────┘
```

---

## Application Initialization Flow

### 1. Bootstrap Sequence

```
main()
  │
  ├─▶ InttraServer.builder()
  │     │
  │     ├─▶ Register Guice Modules
  │     │     ├─▶ BookingBridgeApplicationInjector (Core bindings)
  │     │     ├─▶ BookingBridgeApplicationModule (Executor services)
  │     │     ├─▶ BookingBridgeMessagingModule (SQS/SNS clients)
  │     │     └─▶ BookingBridgeDynamoModule (DynamoDB repositories)
  │     │
  │     ├─▶ Register Commands
  │     │     └─▶ CreateTables (DynamoDB table creation command)
  │     │
  │     ├─▶ Register Post-Setup Hooks
  │     │     ├─▶ configureLifecycle() (Register lifecycle listeners)
  │     │     └─▶ startListener() (Start SQS listener if enabled)
  │     │
  │     └─▶ build()
  │
  └─▶ server.run(args)
```

### 2. Guice Module Loading Order

1. **BookingBridgeApplicationInjector**
   - Binds `Listener` to `SQSListener`
   - Binds `EventPublisher` to `SNSEventPublisher`
   - Binds named `ServiceDefinition` instances
   - Provides `MQService` (IBM MQ connection)

2. **BookingBridgeApplicationModule**
   - Creates thread pool executor (`processor`) with 8 threads
   - Binds `ExecutorService` and work `Queue` with named annotations

3. **BookingBridgeMessagingModule**
   - Provides `MessagingClient<String>` for SQS operations
   - Provides `NotificationService` for SNS operations
   - Uses cloud-sdk-aws factories for AWS SDK v2 integration

4. **BookingBridgeDynamoModule**
   - Provides `DynamoDbClientConfig` from `BaseDynamoDbConfig`
   - Creates `DatabaseRepository<XlogDetail, DefaultPartitionKey<String>>`
   - Provides `XlogDetailDao` with configured repository

### 3. Lifecycle Events

```
Application Start
  │
  ├─▶ BookingBridgeAppLifecycleListener.onStarting()
  │     └─▶ Log service start with configuration
  │
  ├─▶ ListenerManager.start()
  │     └─▶ SQSListener.listen()
  │           └─▶ Poll SQS queue continuously
  │
  ├─▶ Application Ready (accepting messages)
  │
  └─▶ BookingBridgeAppLifecycleListener.onShutdown()
        ├─▶ Stop processor executor (graceful shutdown)
        ├─▶ Close MQ connections
        └─▶ Log shutdown complete
```

---

## Configuration Management

### Configuration Hierarchy

```
BookingBridgeConfig (extends ApplicationConfiguration)
  │
  ├─▶ inQueueUrl: String (SQS queue URL)
  ├─▶ snsTopicARN: String (SNS topic ARN)
  ├─▶ waitTimeSeconds: int (SQS long polling)
  ├─▶ maxNumberOfMessages: int (SQS batch size)
  ├─▶ listenerEnabled: boolean (Enable/disable SQS listener)
  ├─▶ maxRetries: int (Max retry attempts)
  ├─▶ maxDelay: int (Max retry delay in ms)
  ├─▶ baseDelay: int (Base retry delay in ms)
  │
  ├─▶ mqConfig: MQConfig
  │     ├─▶ hostName: String
  │     ├─▶ channel: String
  │     ├─▶ port: int
  │     ├─▶ userId: String
  │     ├─▶ password: String
  │     ├─▶ queueMgrName: String
  │     └─▶ queueName: String
  │
  └─▶ dynamoDbConfig: BaseDynamoDbConfig
        ├─▶ environment: String (e.g., "inttra_int_booking_bridge")
        ├─▶ region: String (AWS region)
        ├─▶ endpointOverride: String (Optional, for testing)
        ├─▶ readCapacityUnits: Long
        ├─▶ writeCapacityUnits: Long
        └─▶ sseEnabled: boolean
```

### Configuration File Example

```yaml
# booking-bridge-config.yaml

inQueueUrl: "https://sqs.us-east-1.amazonaws.com/123456789/booking-bridge-queue"
snsTopicARN: "arn:aws:sns:us-east-1:123456789:booking-bridge-events"
waitTimeSeconds: 20
maxNumberOfMessages: 10
listenerEnabled: true
maxRetries: 3
maxDelay: 10000
baseDelay: 100

mqConfig:
  hostName: "mq.example.com"
  channel: "BOOKING.CHANNEL"
  port: 1414
  userId: "mquser"
  password: "${MQ_PASSWORD}"
  queueMgrName: "QM1"
  queueName: "MIS.PICKUP.I"

dynamoDbConfig:
  environment: "inttra_int_booking_bridge"
  region: "us-east-1"
  readCapacityUnits: 5
  writeCapacityUnits: 5
  sseEnabled: true
```

---

## Key Components

### 1. BookingBridgeApplication

**Location**: `com.inttra.mercury.booking.bridge.BookingBridgeApplication`

**Purpose**: Main application entry point and server configuration

**Key Methods**:
- `main()`: Application entry point
- `newServer()`: Creates and configures InttraServer with Guice modules
- `configureLifecycle()`: Registers lifecycle listeners
- `startListener()`: Starts SQS listener if enabled

**Dependencies**:
- InttraServer (Dropwizard server wrapper)
- Guice Injector
- All Guice modules

---

### 2. BookingBridgeProcessorTask

**Location**: `com.inttra.mercury.booking.bridge.inbound.BookingBridgeProcessorTask`

**Purpose**: Asynchronous message processing coordinator

**Key Methods**:
- `process(List<QueueMessage<String>>, Consumer)`: Processes message batch
- `handleMessage(QueueMessage<String>)`: Processes single message
- `handleException()`: Error handling and DLQ routing

**Flow**:
```
process()
  │
  ├─▶ Parse MetaData from message payload
  │
  ├─▶ Extract xlogId from projections
  │
  ├─▶ Delegate to BookingBridgeService.process()
  │
  ├─▶ On Success:
  │     ├─▶ Log close workflow event
  │     └─▶ Delete message from queue (via callback)
  │
  └─▶ On Error:
        ├─▶ Log error event
        ├─▶ Send message to DLQ
        └─▶ Delete from original queue
```

**Dependencies**:
- BookingBridgeService
- EventLogger
- ExecutorService (named "processor")
- SQSClient
- BookingBridgeConfig

---

### 3. BookingBridgeService

**Location**: `com.inttra.mercury.booking.bridge.inbound.service.BookingBridgeService`

**Purpose**: Core business logic for booking message processing

**Key Methods**:
- `process(String xlogId, MQConfig mqConfig)`: Main processing logic
- `routeToMQ(String xlogId, MQConfig mqConfig)`: Routes message to IBM MQ
- `validateAndStore(String xlogId)`: Validates and stores xlog detail

**Processing Logic**:
```
process(xlogId)
  │
  ├─▶ Acquire lock via MessageRegisterService
  │     └─▶ If DUPLICATE: return IGNORED (already processing)
  │
  ├─▶ Check if xlogId exists in DynamoDB
  │     └─▶ If exists: return IGNORED (already processed)
  │
  ├─▶ Create and save XlogDetail with TTL
  │     ├─▶ xlogId: String (partition key)
  │     ├─▶ createdDate: Date (epoch seconds)
  │     └─▶ expiresOn: Date (TTL, epoch seconds)
  │
  ├─▶ Route message to IBM MQ queue
  │
  ├─▶ Release lock via MessageRegisterService
  │
  └─▶ Return ROUTED status
```

**Dependencies**:
- XlogDetailDao
- EventLogger
- MessageRegisterService
- MQService
- BookingBridgeConfig

---

### 4. XlogDetailDao

**Location**: `com.inttra.mercury.booking.bridge.dao.XlogDetailDao`

**Purpose**: Data Access Object for XlogDetail DynamoDB operations

**Key Methods**:
- `save(XlogDetail)`: Saves xlog detail to DynamoDB
- `findByXlogId(String)`: Retrieves xlog detail by ID with consistent read

**Implementation Details**:
```java
public XlogDetail save(XlogDetail xlogDetail) {
    // Validation
    if (xlogDetail == null) {
        throw new IllegalArgumentException("xlogDetail must not be null");
    }
    
    // Logging
    log.info("Saving XlogDetail with xlogId: {}", xlogDetail.getXlogId());
    
    // Delegate to repository (partition key auto-extracted from @DynamoDbPartitionKey)
    return repository.save(xlogDetail);
}

public List<XlogDetail> findByXlogId(String xlogId) {
    log.info("Finding XlogDetail by xlogId: {}", xlogId);
    
    try {
        // Wrap xlogId in DefaultPartitionKey
        final DefaultPartitionKey<String> key = new DefaultPartitionKey<>(xlogId);
        
        // Consistent read for strong consistency
        final Optional<XlogDetail> result = repository.findById(key, true);
        
        // Return list for consistency with existing API
        return result.map(List::of).orElse(List.of());
        
    } catch (Exception e) {
        log.error("Error finding XlogDetail by xlogId: {}", xlogId, e);
        return List.of(); // Return empty list on error
    }
}
```

**Dependencies**:
- DatabaseRepository<XlogDetail, DefaultPartitionKey<String>> (cloud-sdk-api)

---

### 5. XlogDetail Model

**Location**: `com.inttra.mercury.booking.bridge.model.XlogDetail`

**Purpose**: DynamoDB entity for xlog tracking with TTL

**Annotations**:
```java
@Data                           // Lombok: generates getters/setters
@Builder                        // Lombok: builder pattern
@NoArgsConstructor              // Lombok: no-arg constructor
@JsonIgnoreProperties(ignoreUnknown = true)  // Jackson: ignore unknown fields
@Table(name = "XlogDetail")    // cloud-sdk: table name
@DynamoDbBean                   // AWS SDK v2: DynamoDB entity marker
```

**Fields**:
```java
@DynamoDbPartitionKey           // Partition key annotation
private String xlogId;

@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)
private Date createdDate;       // Stored as epoch seconds

@TTL(name = "expiresOn")        // cloud-sdk: TTL attribute
@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)
private Date expiresOn;         // Stored as epoch seconds, DynamoDB TTL
```

**Special Handling**:
- `setExpiresOn()`: Truncates milliseconds to second precision (DynamoDB TTL requirement)
- `DateEpochSecondAttributeConverter`: Converts Date to/from epoch seconds for storage

**Table Structure**:
```
Table: inttra_{env}_booking_XlogDetail
  Partition Key: xlogId (String)
  Attributes:
    - createdDate (Number, epoch seconds)
    - expiresOn (Number, epoch seconds, TTL enabled)
  TTL: expiresOn (automatically deletes expired items)
```

---

### 6. CreateTables Command

**Location**: `com.inttra.mercury.booking.bridge.dynamo.CreateTables`

**Purpose**: Dropwizard command for DynamoDB table creation/management

**Features**:
- Extends `DynamoDbAdminCommand<BookingBridgeConfig>` from cloud-sdk-aws
- Automatic table metadata extraction from entity annotations
- Automatic TTL configuration from `@TTL` annotation
- Idempotent table creation



**Entity Classes**:
```java
private static final List<Class<?>> ENTITY_CLASSES = List.of(
    XlogDetail.class  // Future: Add more entities here
);
```

---

## AWS Service Integration

### 1. SQS (Simple Queue Service)

**Integration via**: `cloud-sdk-api` MessagingClient interface

**Implementation**: `SqsMessagingClient` from `cloud-sdk-aws`

**Configuration**:
```java
// Provided by BookingBridgeMessagingModule
@Provides
@Singleton
public MessagingClient<String> provideMessagingClient() {
    return MessagingClientFactory.createDefaultStringClient();
}
```

**Usage in SQSListener**:
```java
public class SQSListener implements Listener {
    private final MessagingClient<String> messagingClient;
    
    public void listen() {
        while (running) {
            // Receive messages with long polling
            List<QueueMessage<String>> messages = messagingClient.receiveMessages(
                queueUrl,
                maxNumberOfMessages,
                waitTimeSeconds
            );
            
            // Process messages
            processor.process(messages, this::deleteMessage);
        }
    }
    
    private void deleteMessage(QueueMessage<String> message) {
        messagingClient.deleteMessage(queueUrl, message.getReceiptHandle());
    }
}
```

**Key Operations**:
- `receiveMessages()`: Long polling for messages
- `deleteMessage()`: Acknowledges processed messages
- `sendMessage()`: Sends messages to DLQ on error

**DLQ Strategy**:
```java
private String getDLQUrl(String queueUrl) {
    return queueUrl + "_dlq";  // Convention: append "_dlq" suffix
}
```

---

### 2. SNS (Simple Notification Service)

**Integration via**: `cloud-sdk-api` NotificationService interface

**Implementation**: `SnsNotificationService` from `cloud-sdk-aws`

**Configuration**:
```java
// Provided by BookingBridgeMessagingModule
@Provides
@Singleton
public NotificationService provideNotificationService() {
    String topicArn = config.getSnsTopicARN();
    return NotificationClientFactory.createDefaultClient(topicArn);
}
```

**Usage in SNSEventPublisher**:
```java
public class SNSEventPublisher implements EventPublisher {
    private final NotificationService notificationService;
    
    @Override
    public void publish(Event event) {
        notificationService.publish(
            MetaData.builder()
                .workflowId(event.getWorkflowId())
                .eventType(event.getType())
                .build()
        );
    }
}
```

**Event Types Published**:
- `OPEN_WORKFLOW`: Workflow started
- `CLOSE_WORKFLOW`: Workflow completed successfully
- `ERROR_WORKFLOW`: Workflow failed with error
- `INFO`: Informational events

---

### 3. DynamoDB

**Integration via**: `cloud-sdk-api` DatabaseRepository interface

**Implementation**: AWS SDK v2 Enhanced Client via cloud-sdk-aws

**Configuration**:
```java
// Provided by BookingBridgeDynamoModule
@Provides
@Singleton
public DynamoDbClientConfig provideDynamoDbClientConfig(BookingBridgeConfig config) {
    final BaseDynamoDbConfig dynamoConfig = config.getDynamoDbConfig();
    return dynamoConfig.toClientConfigBuilder()
        .consistentRead(false)  // Eventually consistent reads by default
        .build();
}

@Provides
@Singleton
public DatabaseRepository<XlogDetail, DefaultPartitionKey<String>> 
    provideXlogDetailRepository(DynamoDbClientConfig clientConfig) {
    
    final Table tableAnnotation = XlogDetail.class.getAnnotation(Table.class);
    final String tableName = clientConfig.getTablePrefix() + tableAnnotation.name();
    
    final DynamoRepositoryConfig repositoryConfig = DynamoRepositoryConfig.builder()
        .domainType(XlogDetail.class)
        .isFindAllUnpaginatedScanEnabled(false)  // Prevent expensive scans
        .build();
    
    return DynamoRepositoryFactory.createEnhancedRepository(
        clientConfig,
        tableName,
        XlogDetail.class,
        repositoryConfig
    );
}
```

**Repository Operations**:
```java
// Save (PutItem)
XlogDetail saved = repository.save(xlogDetail);

// Get by partition key with consistent read
DefaultPartitionKey<String> key = new DefaultPartitionKey<>(xlogId);
Optional<XlogDetail> result = repository.findById(key, true);

// Batch operations (if needed)
List<XlogDetail> items = ...;
repository.saveAll(items);
```

**Table Naming Convention**:
```
Pattern: {environment}_{table_name}
Example: inttra_int_booking_XlogDetail
```

**Provisioned Throughput**:
- Read Capacity Units (RCU): 5 (configurable)
- Write Capacity Units (WCU): 5 (configurable)
- Auto-scaling enabled in production

---

## Cloud SDK Integration

### Architecture Overview

```
Booking Bridge Service
        │
        ├─▶ cloud-sdk-api (Interfaces)
        │     ├─▶ DatabaseRepository<T, ID>
        │     ├─▶ MessagingClient<T>
        │     ├─▶ NotificationService
        │     └─▶ Common abstractions
        │
        └─▶ cloud-sdk-aws (AWS Implementation)
              ├─▶ EnhancedDynamoRepository
              ├─▶ SqsMessagingClient
              ├─▶ SnsNotificationService
              └─▶ AWS SDK v2 wrappers
```

### 1. cloud-sdk-api

**Purpose**: Provides vendor-agnostic abstractions for cloud services

**Key Interfaces**:

```java
// Database abstraction
public interface DatabaseRepository<T, ID extends EntityId> {
    T save(T entity);
    Iterable<T> saveAll(Iterable<T> entities);
    Optional<T> findById(ID id, boolean consistentRead);
    void deleteById(ID id);
    List<T> findAll();
}

// Messaging abstraction
public interface MessagingClient<T> {
    List<QueueMessage<T>> receiveMessages(String queueUrl, int maxMessages, int waitTimeSeconds);
    void sendMessage(String queueUrl, T message);
    void deleteMessage(String queueUrl, String receiptHandle);
}

// Notification abstraction
public interface NotificationService {
    void publish(MetaData metadata);
    void publish(Event event);
}
```

**Benefits**:
- Decouples business logic from AWS SDK specifics
- Easier to mock in unit tests
- Potential to swap implementations (e.g., LocalStack, other cloud providers)

---

### 2. cloud-sdk-aws

**Purpose**: Provides AWS SDK v2 implementations of cloud-sdk-api interfaces

**Key Components**:

**EnhancedDynamoRepository**:
```java
public class EnhancedDynamoRepository<T> 
    implements DatabaseRepository<T, DefaultPartitionKey<String>> {
    
    private final DynamoDbEnhancedClient enhancedClient;
    private final DynamoDbTable<T> table;
    
    @Override
    public T save(T entity) {
        table.putItem(entity);
        return entity;
    }
    
    @Override
    public Optional<T> findById(DefaultPartitionKey<String> id, boolean consistentRead) {
        GetItemEnhancedRequest request = GetItemEnhancedRequest.builder()
            .key(Key.builder().partitionValue(id.getPartitionKey()).build())
            .consistentRead(consistentRead)
            .build();
        return Optional.ofNullable(table.getItem(request));
    }
}
```

**SqsMessagingClient**:
```java
public class SqsMessagingClient implements MessagingClient<String> {
    private final SqsClient sqsClient;
    
    @Override
    public List<QueueMessage<String>> receiveMessages(
        String queueUrl, int maxMessages, int waitTimeSeconds) {
        
        ReceiveMessageRequest request = ReceiveMessageRequest.builder()
            .queueUrl(queueUrl)
            .maxNumberOfMessages(maxMessages)
            .waitTimeSeconds(waitTimeSeconds)
            .build();
            
        return sqsClient.receiveMessage(request).messages().stream()
            .map(this::toQueueMessage)
            .collect(Collectors.toList());
    }
}
```

**SnsNotificationService**:
```java
public class SnsNotificationService implements NotificationService {
    private final SnsClient snsClient;
    private final String topicArn;
    
    @Override
    public void publish(MetaData metadata) {
        PublishRequest request = PublishRequest.builder()
            .topicArn(topicArn)
            .message(Json.toJsonString(metadata))
            .build();
        snsClient.publish(request);
    }
}
```

---

### 3. Factory Pattern

**DynamoRepositoryFactory**:
```java
public class DynamoRepositoryFactory {
    
    public static DynamoDbClient createDynamoDbClient(DynamoDbClientConfig config) {
        DynamoDbClientBuilder builder = DynamoDbClient.builder()
            .region(config.getRegion())
            .credentialsProvider(config.getCredentialsProvider());
            
        if (config.getEndpointOverride() != null) {
            builder.endpointOverride(URI.create(config.getEndpointOverride()));
        }
        
        return builder.build();
    }
    
    public static <T> DatabaseRepository<T, DefaultPartitionKey<String>> 
        createEnhancedRepository(
            DynamoDbClientConfig clientConfig,
            String tableName,
            Class<T> domainType,
            DynamoRepositoryConfig repositoryConfig) {
        
        DynamoDbClient client = createDynamoDbClient(clientConfig);
        DynamoDbEnhancedClient enhancedClient = DynamoDbEnhancedClient.builder()
            .dynamoDbClient(client)
            .build();
            
        DynamoDbTable<T> table = enhancedClient.table(tableName, 
            TableSchema.fromBean(domainType));
            
        return new EnhancedDynamoRepository<>(enhancedClient, table, repositoryConfig);
    }
}
```

**MessagingClientFactory**:
```java
public class MessagingClientFactory {
    
    public static MessagingClient<String> createDefaultStringClient() {
        SqsClient sqsClient = SqsClient.builder()
            .region(Region.of(System.getenv("AWS_REGION")))
            .credentialsProvider(DefaultCredentialsProvider.create())
            .build();
            
        return new SqsMessagingClient(sqsClient);
    }
}
```

**NotificationClientFactory**:
```java
public class NotificationClientFactory {
    
    public static NotificationService createDefaultClient(String topicArn) {
        SnsClient snsClient = SnsClient.builder()
            .region(Region.of(System.getenv("AWS_REGION")))
            .credentialsProvider(DefaultCredentialsProvider.create())
            .build();
            
        return new SnsNotificationService(snsClient, topicArn);
    }
}
```

---

### 4. Annotation-Driven Configuration

**cloud-sdk Annotations**:

```java
@Table(name = "XlogDetail")           // Table name (prefix added by config)
@TTL(name = "expiresOn")               // TTL attribute configuration
public class XlogDetail {
    
    @DynamoDbPartitionKey              // AWS SDK v2: Partition key
    private String xlogId;
    
    @DynamoDbConvertedBy(              // AWS SDK v2: Custom attribute converter
        DateEpochSecondAttributeConverter.class
    )
    private Date createdDate;
}
```

**Benefits**:
- Declarative configuration
- Automatic table/index creation via CreateTables command
- Type-safe attribute conversion
- Consistent metadata across DAOs and admin commands

---

## Data Access Layer

### DAO Pattern

```
┌─────────────────────────────────────────────────────┐
│              BookingBridgeService                    │
│              (Business Logic)                        │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                 XlogDetailDao                        │
│              (Data Access Layer)                     │
│                                                       │
│  + save(XlogDetail): XlogDetail                     │
│  + findByXlogId(String): List<XlogDetail>           │
│                                                       │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│     DatabaseRepository<XlogDetail, PK<String>>      │
│              (cloud-sdk-api Interface)              │
│                                                       │
│  + save(T): T                                        │
│  + findById(ID, boolean): Optional<T>               │
│  + deleteById(ID): void                             │
│  + findAll(): List<T>                               │
│                                                       │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│         EnhancedDynamoRepository                     │
│        (cloud-sdk-aws Implementation)               │
│                                                       │
│  Uses: DynamoDbEnhancedClient (AWS SDK v2)          │
│  Uses: DynamoDbTable<T>                             │
│  Uses: TableSchema.fromBean()                       │
│                                                       │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────────┐
         │  DynamoDB Table           │
         │  (AWS Service)            │
         │                           │
         │  inttra_int_booking_      │
         │  bridge_xlog_detail       │
         └───────────────────────────┘
```

### Key Abstractions

**EntityId Interface**:
```java
public interface EntityId {
    boolean isValid();
}

public class DefaultPartitionKey<P> implements EntityId {
    private final P partitionKey;
    
    public DefaultPartitionKey(P partitionKey) {
        this.partitionKey = partitionKey;
    }
    
    @Override
    public boolean isValid() {
        return partitionKey != null;
    }
    
    public P getPartitionKey() {
        return partitionKey;
    }
}
```

**Repository Configuration**:
```java
DynamoRepositoryConfig config = DynamoRepositoryConfig.builder()
    .domainType(XlogDetail.class)
    .isFindAllUnpaginatedScanEnabled(false)  // Disable expensive scan operations
    .build();
```

---

## Message Processing Flow

### End-to-End Flow

```
┌──────────────┐
│   SQS Queue  │
│              │
│ [Message 1]  │
│ [Message 2]  │
│ [Message N]  │
└──────┬───────┘
       │
       │ (1) Long Polling (20s)
       ▼
┌──────────────────────┐
│   SQSListener        │
│   receiveMessages()  │
└──────┬───────────────┘
       │
       │ (2) Batch of messages
       ▼
┌───────────────────────────────────────┐
│   BookingBridgeProcessorTask          │
│   process(messages, deleteCallback)   │
└──────┬────────────────────────────────┘
       │
       │ (3) Async execution (thread pool)
       ▼
┌──────────────────────────────────┐
│   For each message:              │
│   1. Parse MetaData              │
│   2. Extract xlogId              │
│   3. Call service.process()      │
└──────┬───────────────────────────┘
       │
       │ (4) Process xlogId
       ▼
┌─────────────────────────────────────────┐
│   BookingBridgeService.process()        │
│                                          │
│   ┌──────────────────────────────────┐  │
│   │ 1. Acquire Lock                  │  │
│   │    messageRegister.lock(xlogId) │  │
│   │    → If DUPLICATE: return IGNORED│  │
│   └──────────────────────────────────┘  │
│                                          │
│   ┌──────────────────────────────────┐  │
│   │ 2. Check DynamoDB               │  │
│   │    dao.findByXlogId(xlogId)     │  │
│   │    → If exists: return IGNORED  │  │
│   └──────────────────────────────────┘  │
│                                          │
│   ┌──────────────────────────────────┐  │
│   │ 3. Save to DynamoDB             │  │
│   │    XlogDetail detail = new...   │  │
│   │    dao.save(detail)              │  │
│   └──────────────────────────────────┘  │
│                                          │
│   ┌──────────────────────────────────┐  │
│   │ 4. Route to IBM MQ              │  │
│   │    mqService.sendToQueue(msg)   │  │
│   │    mqService.commit()            │  │
│   └──────────────────────────────────┘  │
│                                          │
│   ┌──────────────────────────────────┐  │
│   │ 5. Release Lock                 │  │
│   │    messageRegister.releaseLock() │  │
│   └──────────────────────────────────┘  │
│                                          │
│   return "ROUTED"                        │
└─────────────┬────────────────────────────┘
              │
              │ (5) Success/Failure
              ▼
┌─────────────────────────────────────┐
│   BookingBridgeProcessorTask        │
│                                      │
│   ┌──────────────────────────────┐  │
│   │ On Success:                  │  │
│   │ 1. Log CLOSE_WORKFLOW event  │  │
│   │ 2. deleteCallback(message)   │  │
│   └──────────────────────────────┘  │
│                                      │
│   ┌──────────────────────────────┐  │
│   │ On Error:                    │  │
│   │ 1. Log ERROR_WORKFLOW event  │  │
│   │ 2. sendMessage(DLQ)          │  │
│   │ 3. deleteCallback(message)   │  │
│   └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Message Format

**SQS Message Body (MetaData)**:
```json
{
  "workflowId": "wf-12345",
  "parentWorkflowId": "parent-wf-67890",
  "rootWorkflowId": "root-wf-11111",
  "s3Bucket": "booking-bucket",
  "s3Key": "bookings/2025/12/booking-12345.xml",
  "executionName": "booking-inbound",
  "timestamp": "2025-12-26T10:30:00Z",
  "projections": {
    "XLOG_ID": "XLOG-12345-ABC"
  }
}
```

**DynamoDB XlogDetail Item**:
```json
{
  "xlogId": "XLOG-12345-ABC",
  "createdDate": 1735210200,  // Epoch seconds
  "expiresOn": 1737888600     // Epoch seconds (30 days later)
}
```

---

## Dependency Diagram

### Class Dependency Graph

```
                         ┌─────────────────────────┐
                         │ BookingBridgeApplication│
                         │     (Main Entry)        │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
        ┌──────────────────┐ ┌───────────────┐ ┌──────────────────┐
        │ Application      │ │  Messaging    │ │  Dynamo          │
        │ Injector         │ │  Module       │ │  Module          │
        └────────┬─────────┘ └───────┬───────┘ └────────┬─────────┘
                 │                   │                   │
                 │                   │                   │
        ┌────────┼───────────────────┼───────────────────┼────────┐
        │        │                   │                   │        │
        ▼        ▼                   ▼                   ▼        ▼
   ┌────────┐ ┌────────┐      ┌──────────┐       ┌──────────┐ ┌────────┐
   │  SQS   │ │  SNS   │      │Messaging │       │ Database │ │ Xlog   │
   │Listener│ │Event   │      │ Client   │       │Repository│ │Detail  │
   │        │ │Publisher│      │ (SQS)    │       │(DynamoDB)│ │  DAO   │
   └───┬────┘ └────┬───┘      └──────────┘       └──────┬───┘ └───┬────┘
       │           │                                     │         │
       │           │                                     │         │
       └───────────┼─────────────────────────────────────┼─────────┘
                   │                                     │
                   ▼                                     │
        ┌──────────────────────┐                        │
        │  Processor Task      │◀───────────────────────┘
        │  (Async Executor)    │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ BookingBridge Service│
        │  (Business Logic)    │
        └──────────┬───────────┘
                   │
        ┌──────────┼──────────┬──────────┐
        │          │          │          │
        ▼          ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ Xlog   │ │   MQ   │ │ Event  │ │Message │
   │Detail  │ │Service │ │ Logger │ │Register│
   │  DAO   │ │(IBM MQ)│ │        │ │ Service│
   └────────┘ └────────┘ └────────┘ └────────┘
```

### Guice Dependency Injection

```
BookingBridgeConfig ──────────────────┐
                                      │
BaseDynamoDbConfig ───────────────┐   │
                                  │   │
                                  ▼   ▼
                        ┌────────────────────┐
                        │ BookingBridgeDynamo│
                        │      Module        │
                        └─────────┬──────────┘
                                  │
                                  ├─▶ DynamoDbClientConfig
                                  │
                                  ├─▶ DatabaseRepository<XlogDetail, PK>
                                  │
                                  └─▶ XlogDetailDao
                                  
BookingBridgeConfig ──────────────────┐
                                      │
                                      ▼
                        ┌────────────────────┐
                        │ BookingBridgeMsg   │
                        │      Module        │
                        └─────────┬──────────┘
                                  │
                                  ├─▶ MessagingClient<String>
                                  │
                                  └─▶ NotificationService
                                  
BookingBridgeConfig ──────────────────┐
Environment ──────────────────────┐   │
                                  │   │
                                  ▼   ▼
                        ┌────────────────────┐
                        │ BookingBridgeApp   │
                        │    Injector        │
                        └─────────┬──────────┘
                                  │
                                  ├─▶ SQSListener
                                  │
                                  ├─▶ SNSEventPublisher
                                  │
                                  └─▶ MQService
```

---

## Test Coverage

### Unit Tests (63 total)

#### Configuration Tests
1. **BookingBridgeApplicationInjectorTest**
   - `shouldCreateSQSListener()`
   - `shouldBindListenerInterface()`
   - `shouldBindEventPublisher()`
   - `shouldBindServiceDefinitions()`
   - `shouldProvideMQService()`

2. **BookingBridgeApplicationModuleTest**
   - `shouldBindExecutorService()`
   - `shouldBindProcessorQueue()`
   - `shouldConfigureThreadPool()`

3. **BookingBridgeDynamoModuleTest**
   - `shouldProvideDynamoDbClientConfig()`
   - `shouldProvideXlogDetailRepository()`
   - `shouldProvideXlogDetailDao()`
   - `shouldThrowWhenConfigIsNull()`

4. **BookingBridgeAppLifecycleListenerTest**
   - `shouldLogOnStarting()`
   - `shouldLogOnShutdown()`
   - `shouldCloseMQService()`

#### DAO Tests
5. **XlogDetailDaoTest** (28 tests)
   - **ConstructorTests**
     - `shouldCreateDaoWithValidRepository()`
     - `shouldThrowExceptionWhenRepositoryIsNull()`
   
   - **SaveOperationTests**
     - `shouldSaveXlogDetailSuccessfully()`
     - `shouldReturnSavedXlogDetail()`
     - `shouldThrowExceptionWhenSavingNull()`
     - `shouldPassXlogDetailToRepository()`
     - `shouldLogWhenSaving()`
     - `shouldDelegateToRepositorySave()`
   
   - **FindByXlogIdTests**
     - `shouldFindXlogDetailById()`
     - `shouldReturnEmptyListWhenNotFound()`
     - `shouldUseConsistentRead()`
     - `shouldWrapXlogIdInPartitionKey()`
     - `shouldReturnListWithSingleElement()`
     - `shouldHandleFindByIdException()`
     - `shouldLogWhenFinding()`
   
   - **ExceptionHandlingTests**
     - `shouldReturnEmptyListOnException()`
     - `shouldHandleIllegalArgumentException()`
     - `shouldHandleRuntimeException()`
     - `shouldLogErrorOnException()`
   
   - **RepositoryInteractionTests**
     - `shouldCallRepositorySaveExactlyOnce()`
     - `shouldCallRepositoryFindByIdExactlyOnce()`
     - `shouldPassCorrectPartitionKeyToFindById()`
     - `shouldNotCallRepositoryWhenSaveArgumentIsNull()`
   
   - **EdgeCaseTests**
     - `shouldHandleXlogDetailWithNullFields()`
     - `shouldHandleMultipleSaveCalls()`
     - `shouldHandleConsecutiveFindCalls()`
     - `shouldHandleXlogIdWithSpecialCharacters()`
     - `shouldHandleVeryLongXlogId()`
     - `shouldNotSaveWhenArgumentIsNull()`

#### Service Tests
6. **BookingBridgeProcessorTaskTest**
   - `testValidRequest()`
   - `testXlogExistsInXlogDetail()`
   - `testXlogLocked()`
   - `exceptionHandlerShouldMoveMessageToDLQ()`
   - `exceptionHandlerShouldLogErrorWhenDLQFails()`

7. **BookingBridgeServiceTest** (35 tests)
   - **RouteToDestinationTests**
     - `shouldRouteNewXlogToMQAndSaveToDb()`
     - `shouldSkipRoutingWhenXlogAlreadyExists()`
     - `shouldIgnoreRoutingWhenLockFails()`
     - `shouldAddXlogIdToTokens()`
     - `shouldHandleNullXlogList()`
     - `shouldHandleEmptyXlogList()`
     - `shouldNotRouteWhenXlogIdBlankInDB()`
   
   - **ExceptionHandlingTests**
     - `shouldThrowRuntimeExceptionOnMQException()`
     - `shouldThrowRuntimeExceptionOnGenericException()`
     - `shouldAlwaysReleaseLockInFinally()`
     - `shouldNotReleaseLockWhenNotAcquired()`
     - `shouldHandleMQExceptionDuringSendToQueue()`
     - `shouldHandleExceptionDuringCommit()`
   
   - **MessageKeyGenerationTests**
     - `shouldGenerateCorrectMessageKeyFormat()`
     - `shouldUseSameMessageKeyForLockAndRelease()`
   
   - **ExpirationCalculationTests**
     - `shouldCalculateExpiresOnAs7DaysFromNow()`
     - `shouldCalculateExpiresOnConsistently()`
   
   - **MQExceptionHandlingTests**
     - `shouldHandleMQExceptionAndCreateNewConnection()`
     - `shouldLogReasonCodeOnMQException()`
   
   - **TokenManagementTests**
     - `shouldPopulateAllRoutingTokensOnSuccess()`
     - `shouldPopulateIgnoredTokensWhenDuplicate()`
     - `shouldPopulateIgnoredTokensWhenLockFails()`
     - `shouldPreserveExistingTokens()`
   
   - **DynamoDbPersistenceTests**
     - `shouldSaveXlogWithCorrectAttributes()`
     - `shouldSetCreatedDateToCurrentTime()`
     - `shouldOnlySaveAfterSuccessfulMQRouting()`
     - `shouldNotSaveWhenMQSendFails()`
   
   - **MQMessageContentTests**
     - `shouldSendXlogIdInMQMessage()`
     - `shouldCommitMQMessageAfterSending()`

#### Infrastructure Tests
8. **CreateTablesTest**
   - `shouldInitializeWithEntityClasses()`
   - `shouldResolveClientConfig()`
   - `shouldThrowWhenConfigIsNull()`
   - `shouldThrowWhenDynamoConfigIsNull()`

9. **MQServiceTest**
   - `shouldConnectToQueueManager()`
   - `shouldSendMessageToQueue()`
   - `shouldGetMessageFromQueue()`
   - `shouldCommit()`
   - `shouldRollback()`
   - `shouldCloseConnection()`

#### Event Tests
10. **EventGeneratorTest**
   - `shouldGenerateOpenWorkflowEvent()`
   - `shouldGenerateCloseWorkflowEvent()`
   - `shouldGenerateErrorWorkflowEvent()`
   - `shouldAddTokensToEvent()`

11. **EventLoggerTest**
    - `shouldLogOpenRunEvent()`
    - `shouldLogCloseRunEvent()`
    - `shouldLogErrorRunEvent()`
    - `shouldPublishEventToSNS()`

12. **SNSEventPublisherTest**
    - `shouldPublishEvent()`
    - `shouldHandlePublishFailure()`

#### Listener Tests
13. **SQSListenerTest**
    - `shouldReceiveMessagesFromQueue()`
    - `shouldProcessMessages()`
    - `shouldDeleteProcessedMessages()`
    - `shouldHandleReceiveErrors()`

#### Network Service Tests
14. **NetworkServiceClientTest**
    - `shouldMakePostRequest()`
    - `shouldMakePutRequest()`
    - `shouldHandleHttpErrors()`

15. **AuthClientTest**
    - `shouldAuthenticateSuccessfully()`
    - `shouldHandleAuthFailure()`

16. **AuthUtilTest**
    - `shouldGenerateToken()`
    - `shouldValidateToken()`

#### Utility Tests
17. **JsonTest**
    - `shouldSerializeToJson()`
    - `shouldDeserializeFromJson()`
    - `shouldHandleNullValues()`

#### Exception Tests
18. **InternalExceptionTest**
    - `shouldCreateExceptionWithMessage()`
    - `shouldCreateExceptionWithCause()`

19. **NetworkServicesExceptionTest**
    - `shouldCreateExceptionWithMessage()`
    - `shouldCreateExceptionWithCause()`

20. **NonRecoverableExceptionTest**
    - `shouldCreateExceptionWithMessage()`
    - `shouldCreateExceptionWithCause()`

21. **ExternalCallExecutionExceptionTest**
    - `shouldCreateExceptionWithMessage()`
    - `shouldCreateExceptionWithCause()`

---

### Integration Tests (4 total)

#### DAO Integration Tests
22. **XlogDetailDaoIT** (20 tests with DynamoDB Local)
   - **SaveOperations**
     - `shouldSaveXlogDetailSuccessfully()`
     - `shouldSaveWithTTL()`
     - `shouldThrowExceptionWhenSavingNull()`
     - `shouldOverwriteExistingXlogDetail()`
     - `shouldSaveXlogDetailWithSpecialCharacters()`
     - `shouldSaveMultipleXlogDetails()`
     - `shouldTruncateMillisecondsForDates()`
   
   - **FindByXlogIdTests**
     - `shouldFindSavedXlogDetail()`
     - `shouldReturnEmptyListForNonExistentId()`
     - `shouldUseConsistentRead()`
     - `shouldFindAfterSave()`
   
   - **TtlAndDateTests**
     - `shouldStoreCreatedDateAsEpochSeconds()`
     - `shouldStoreExpiresOnAsEpochSeconds()`
     - `shouldHandleTTLConfiguration()`
   
   - **EdgeCaseTests**
     - `shouldHandleNullExpiresOn()`
     - `shouldHandleXlogIdWithUnicodeCharacters()`
     - `shouldHandleVeryLongXlogId()`
     - `shouldHandleEmptyCreatedDate()`
   
   - **RepositoryIntegrationTests**
     - `shouldSaveViaRepository()`
     - `shouldFindByIdViaRepository()`

#### Table Creation Tests
23. **CreateTablesIT** (15 tests with DynamoDB Local)
   - **ClientConfigurationResolution**
     - `shouldResolveClientConfigWithAllProperties()`
     - `shouldThrowExceptionWhenConfigurationIsNull()`
     - `shouldThrowExceptionWhenDynamoDbConfigIsNull()`
   
   - **TableAndTtlValidation**
     - `shouldCreateXlogDetailTable()`
     - `shouldCreateXlogDetailTableWithCorrectPartitionKey()`
     - `shouldCreateXlogDetailTableWithAttributes()`
     - `shouldCreateXlogDetailTableWithThroughput()`
     - `shouldEnableTTLForXlogDetail()`
     - `shouldHaveXlogDetailTableActive()`
     - `shouldCreateXlogDetailTableWithoutGSIs()`
     - `shouldCreateXlogDetailTableWithoutLSIs()`
     - `shouldHandleIdempotentTableCreation()`
   
   - **EdgeCasesAndErrorHandling**
     - `shouldHandleConfigurationWithDifferentEnvironmentPrefix()`
     - `shouldThrowWhenMissingDynamoDbConfig()`
     - `shouldCreateCommandWithDefaultConstructor()`

#### Service Integration Tests
24. **BookingBridgeServiceIT** (23 tests with DynamoDB Local)
   - **DynamoDbPersistenceTests**
     - `shouldPersistXlogDetailToDynamoDB()`
     - `shouldSetExpirationSevenDaysFromNow()`
     - `shouldPersistMultipleXlogsIndependently()`
     - `shouldHandleSpecialCharactersInXlogId()`
   
   - **DuplicateDetectionTests**
     - `shouldDetectDuplicateXlogFromDynamoDB()`
     - `shouldQueryDynamoDBForExistingXlog()`
     - `shouldHandleConcurrentRoutingForSameXlog()`
   
   - **DynamoDBQueryTests**
     - `shouldQueryByPartitionKeyWithConsistentRead()`
     - `shouldReturnEmptyListForNonExistentXlog()`
     - `shouldRetrieveMostRecentlySavedXlog()`
   
   - **EndToEndDynamoDBTests**
     - `shouldCompleteFullRoutingFlowWithDynamoDB()`
     - `shouldPreventReRoutingViaDBCheck()`
     - `shouldHandleRapidSequentialRequests()`
   
   - **DataIntegrityTests**
     - `shouldPreserveAllXlogAttributesInDynamoDB()`
     - `shouldMaintainDataConsistencyAcrossQueries()`
   
   - **TTLAndExpirationTests**
     - `shouldSetTTLExpirationOnSavedRecords()`
     - `shouldCalculateConsistentExpirationDates()`

---

### Test Execution

**Run All Tests**:
```bash
mvn clean verify -pl booking-bridge -am
```

**Run Unit Tests Only**:
```bash
mvn test -pl booking-bridge
```

**Run Integration Tests Only**:
```bash
mvn failsafe:integration-test -pl booking-bridge 
```

**Run Specific Test Class**:
```bash
mvn test -pl booking-bridge -Dtest=XlogDetailDaoTest
mvn verify -pl booking-bridge -Dit.test=XlogDetailDaoIT
```

**Run with Coverage**:
```bash
mvn clean verify -pl booking-bridge -am -Pcoverage
```

---

### Test Infrastructure

**DynamoDB Local**:
- Version: 2.5.3 (compatible with AWS SDK v2)
- SQLite native libraries (Windows: dll, Linux: so, macOS: dylib)
- Configured via BaseDynamoDbIT base class
- Auto-started per test class

**Maven Plugins**:
- **Surefire**: Runs unit tests (**/*Test.java)
- **Failsafe**: Runs integration tests (**/*IT.java)
- **Dependency Plugin**: Copies SQLite native libs to target/native-libs

**Configuration**:
```xml
<systemPropertyVariables>
    <sqlite4java.library.path>${project.build.directory}/native-libs</sqlite4java.library.path>
</systemPropertyVariables>
```

---

## Deployment

### Build Artifacts

**Uber JAR**:
```bash
mvn clean package -pl booking-bridge -am
# Output: booking-bridge/target/booking-bridge-1.0.jar
```

### Environment Configuration

**AWS Credentials**:
- EC2 Instance Profile (recommended for EC2/ECS)
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Shared credentials file: `~/.aws/credentials` 

## References

### External Documentation
- [AWS SDK for Java v2](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/)
- [DynamoDB Enhanced Client](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/dynamodb-enhanced-client.html)
- [Dropwizard Documentation](https://www.dropwizard.io/en/stable/)
- [Google Guice User Guide](https://github.com/google/guice/wiki)
- [IBM MQ Documentation](https://www.ibm.com/docs/en/ibm-mq)

### Internal Documentation
- cloud-sdk-api Javadoc
- cloud-sdk-aws Javadoc

---

## Appendix

### Command-Line Interface

**Server Commands**:
```bash
# Start server
java -jar booking-bridge.jar server config.yaml

# Check configuration
java -jar booking-bridge.jar check config.yaml

# Create DynamoDB tables
java -jar booking-bridge.jar db create-tables config.yaml




---

## Version History

| Version | Date       | Changes                                      |
|---------|------------|----------------------------------------------|
| 1.0     | 2025-12-26 | Initial design document                      |
|         |            |    |

---


