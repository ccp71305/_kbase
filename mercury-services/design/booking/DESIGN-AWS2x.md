# Booking Service - Design Documentation (Post AWS SDK 2.x Migration)

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
10. [Outbound Processing Flow](#outbound-processing-flow)
11. [Lambda Architecture](#lambda-architecture)
12. [Dependency Diagram](#dependency-diagram)
13. [Test Coverage](#test-coverage)
14. [Email Library Migration (v1.1)](#email-library-migration-v11)
15. [DynamoDB Model Annotation Removal (v1.1)](#dynamodb-model-annotation-removal-v11)
16. [POM Dependency Changes (v1.1)](#pom-dependency-changes-v11)

---

## Overview

The **Booking Service** is the core microservice in the Mercury platform responsible for
managing ocean freight booking lifecycle — from request submission through carrier confirmation,
amendment, decline, and cancellation. It processes inbound booking messages from SQS queues,
validates and enriches data with network services, persists booking details in DynamoDB,
indexes to Elasticsearch for search, archives to S3, publishes events to SNS, and routes
outbound responses back to trading partners.

### Key Responsibilities
- **Message Consumption**: Listens to SQS queues for incoming booking messages (requests, confirmations, declines)
- **Booking Lifecycle Management**: State machine for booking request → confirmation → amendment → cancellation flows
- **Data Persistence**: Stores booking details in DynamoDB with optimistic locking and TTL
- **Search Indexing**: Indexes booking data to Elasticsearch for carrier/customer search
- **S3 Archival**: Archives booking snapshots to S3 via DynamoDB Streams and Lambda
- **Event Publishing**: Publishes workflow events to SNS topics for downstream consumers
- **Outbound Processing**: Routes booking responses to distribution SQS queue for partner delivery
- **REST APIs**: Exposes carrier/customer booking, search, template, and spot-rates endpoints
- **Enrichment**: Resolves location codes, participant details, and subscription preferences via network services

### Technology Stack
- **Framework**: Dropwizard 4.0.x
- **Dependency Injection**: Google Guice
- **AWS SDK**: Version 2 (via cloud-sdk-aws)
- **Messaging**: SQS, SNS (via cloud-sdk-api)
- **Storage**: S3 (via cloud-sdk-api)
- **Database**: DynamoDB (via cloud-sdk-api Enhanced Client)
- **Search**: Elasticsearch (via Jest client)
- **Testing**: JUnit 5, TestNG, Mockito 5, AssertJ 3

---

## Architecture

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              Booking Service                                     │
│                                                                                  │
│  ┌────────────────┐        ┌──────────────────┐       ┌──────────────────┐       │
│  │ SQS Listener   │───────▶│ BookingProcessor │──────▶│  BookingService  │       │
│  │  (Consumer)    │        │   Task (Async)   │       │ (Business Logic) │       │
│  └────────────────┘        └──────────────────┘       └──────────────────┘       │
│                                                                │                 │
│                                    ┌───────────────────────────┼───────┐         │
│                                    │               │           │       │         │
│                                    ▼               ▼           ▼       ▼         │
│                             ┌───────────┐   ┌──────────┐ ┌────────┐ ┌────────┐  │
│                             │ Booking   │   │ Outbound │ │  S3    │ │ Event  │  │
│                             │ DetailDao │   │ Service  │ │Workspace│ │ Logger │  │
│                             └───────────┘   └──────────┘ │Service │ └────────┘  │
│                                    │              │      └────────┘      │       │
│  ┌────────────────┐                │              │           │          │       │
│  │  REST APIs     │                │              │           │          │       │
│  │ ┌────────────┐ │                │              │           │          │       │
│  │ │ Carrier    │ │                │              │           │          │       │
│  │ │ Resource   │ │                │              │           │          │       │
│  │ ├────────────┤ │                │              │           │          │       │
│  │ │ Customer   │ │                │              │           │          │       │
│  │ │ Resource   │ │                │              │           │          │       │
│  │ ├────────────┤ │                │              │           │          │       │
│  │ │ Search     │ │                │              │           │          │       │
│  │ │ Resource   │ │                │              │           │          │       │
│  │ └────────────┘ │                │              │           │          │       │
│  └────────────────┘                │              │           │          │       │
└────────────────────────────────────┼──────────────┼───────────┼──────────┼───────┘
                                     │              │           │          │
                          ┌──────────┘    ┌─────────┘     ┌─────┘    ┌────┘
                          ▼               ▼               ▼          ▼
                   ┌──────────┐    ┌──────────┐    ┌──────────┐ ┌──────────┐
                   │ DynamoDB │    │  SQS     │    │    S3    │ │   SNS    │
                   │ (Tables) │    │ (Dist Q) │    │ (Archive)│ │  (Topic) │
                   └──────────┘    └──────────┘    └──────────┘ └──────────┘
```

### Component Interaction

```
External Systems                   Booking Service                        AWS Services
┌─────────────┐                                                    ┌──────────────────┐
│ Transformer │                                                    │    DynamoDB       │
│ SQS Queue   │──┐                                                │  (7 tables)      │
└─────────────┘  │                                                └──────────────────┘
                 │                                                        ▲
                 ▼                                                        │
         ┌───────────────┐     ┌──────────────────────┐          ┌──────────────┐
         │ SQS Listener  │────▶│ BookingProcessorTask │─────────▶│ BookingDetail│
         │  (cloud-sdk)  │     │  (8-thread executor) │          │     DAO      │
         └───────────────┘     └──────────┬───────────┘          └──────────────┘
                                          │
                              ┌───────────┼───────────────┐
                              │           │               │
                              ▼           ▼               ▼
                       ┌───────────┐ ┌──────────┐  ┌───────────────┐
                       │S3Workspace│ │ Event    │  │   Outbound    │
                       │ Service   │ │ Logger   │  │   Service     │
                       └─────┬─────┘ └────┬─────┘  └──────┬────────┘
                             │            │               │
                             ▼            ▼               ▼
                       ┌──────────┐ ┌──────────┐  ┌──────────────┐
                       │   S3     │ │   SNS    │  │ Distributor  │
                       │ (Bucket) │ │  (Topic) │  │  SQS Queue   │
                       └──────────┘ └──────────┘  └──────────────┘
                                                         │
                                                         ▼
                                                  ┌──────────────┐
                                                  │   Partners   │
                                                  │  (via EDI)   │
                                                  └──────────────┘

┌─────────────┐
│ DynamoDB    │                    ┌──────────────────────┐
│ Streams     │───────────────────▶│  S3ArchiveHandler   │
│ (INSERT)    │                    │   (AWS Lambda)       │
└─────────────┘                    └──────────┬───────────┘
                                              │
                                   ┌──────────┼──────────┐
                                   ▼          ▼          ▼
                            ┌──────────┐ ┌────────┐ ┌────────┐
                            │   S3     │ │  SNS   │ │DynamoDB│
                            │ Archive  │ │(Track) │ │(Read)  │
                            └──────────┘ └────────┘ └────────┘
```

### Inbound vs Outbound Flow

```
                INBOUND FLOW                            OUTBOUND FLOW
                ──────────                              ─────────────

  SQS (Transformer Queue)                       BookingService.process()
         │                                               │
         ▼                                               ▼
  SQSListener.pollAndExecute()              OutboundService.processOutboundMessage()
         │                                               │
         ▼                                               ▼
  BookingProcessorTask.process()              Enrichment (Location, Party)
         │                                               │
    ┌────┴────┐                                          ▼
    │         │                               S3 putObject (workspace)
    ▼         ▼                                          │
 executeRAC  executeCPD                                  ▼
    │         │                               SQSClient.sendMessage()
    ▼         ▼                                (Distributor Queue)
 BookingService                                          │
    │                                                    ▼
    ├─▶ validate()                            EventLogger.logCloseRunEvent()
    ├─▶ transform()                                      │
    ├─▶ save() → DynamoDB                                ▼
    ├─▶ index() → Elasticsearch                     SNS Publish
    ├─▶ S3 putObject (workspace)
    └─▶ OutboundService (async)
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
  │     │     ├─▶ BookingApplicationInjector  (Core bindings: Listener, DAO, services)
  │     │     ├─▶ BookingDynamoModule          (DynamoDB repositories, 7 tables)
  │     │     ├─▶ BookingMessagingModule        (SQS/SNS/S3 via cloud-sdk-aws)
  │     │     ├─▶ BookingApplicationModule      (XSS filters, email templates)
  │     │     ├─▶ LocalCacheModule              (Guava caches for network services)
  │     │     ├─▶ MetricsInstrumentationModule  (Dropwizard metrics)
  │     │     ├─▶ JestModule                    (Elasticsearch Jest client)
  │     │     ├─▶ SystemUTCClockModule          (Clock.systemUTC())
  │     │     ├─▶ EmailSenderModule             (Email sending)
  │     │     ├─▶ OutboundServiceModule         (32-thread outbound executor)
  │     │     └─▶ InboundServiceModule          (8-thread inbound executor)
  │     │
  │     ├─▶ Register Commands
  │     │     ├─▶ BookingDynamoDbAdminCommand  (DynamoDB table create/delete)
  │     │     ├─▶ CreateIndex                   (Elasticsearch index create)
  │     │     └─▶ DeleteIndex                   (Elasticsearch index delete)
  │     │
  │     ├─▶ Register Jersey Resources
  │     │     ├─▶ CarrierBookingResource       (/booking/carrier-bookings)
  │     │     ├─▶ CustomerBookingResource      (/booking/customer-bookings)
  │     │     ├─▶ SearchResource               (/booking/search)
  │     │     ├─▶ OutboundResource             (/booking/outbound)
  │     │     ├─▶ RapidReservationResource     (/booking/rapid-reservations)
  │     │     ├─▶ TemplateResource             (/booking/templates)
  │     │     ├─▶ CarrierSpotRatesResource     (/booking/spot-rates)
  │     │     └─▶ DangerousGoodsResource       (/booking/dangerous-goods)
  │     │
  │     ├─▶ Register Post-Setup Hooks
  │     │     ├─▶ configureLifecycle()          (Register lifecycle listener)
  │     │     └─▶ startListener()               (Start SQS listener if enabled)
  │     │
  │     └─▶ build()
  │
  └─▶ server.run(args)
```

### 2. Guice Module Loading Order

1. **BookingApplicationInjector** — Core bindings
   - Binds `Listener` → `SQSListener`
   - Binds named `ServiceDefinition` instances (auth, participant, geography, etc.)
   - Provides `SQSListener` with `SQSClient` + `BookingProcessorTask::process` processor
   - Provides `S3ArchiveHandler` with `StorageClient` injection

2. **BookingDynamoModule** — DynamoDB (7 tables)
   - Provides `DynamoDbClientConfig` from `BaseDynamoDbConfig`
   - Creates repositories via `DynamoRepositoryFactory.createEnhancedRepository()`
   - Provides 7 DAOs: `BookingDetailDao`, `UniqueIdDao`, `SequenceIdDao`,
     `RapidReservationDao`, `TemplateSummaryDao`, `SpotRatesDao`, `SpotRatesToInttraRefDao`

3. **BookingMessagingModule** — SQS / SNS / S3
   - Provides `MessagingClient<String>` for SQS operations
   - Provides `NotificationService` for SNS event publishing
   - Provides `StorageClient` for S3 read/write
   - Uses cloud-sdk-aws factories for AWS SDK v2 integration

4. **OutboundServiceModule** — Outbound processing
   - Creates 32-thread executor with queue size 60
   - Conditionally binds `OutboundServiceImpl` + `SNSEventPublisher` (or dummy variants)

5. **InboundServiceModule** — Inbound processing
   - Creates 8-thread executor with `CallerRunsPolicy` (back-pressure)
   - Binds processor work queue and executor with `@Named("processor")`

### 3. Lifecycle Events

```
Application Start
  │
  ├─▶ BookingAppLifecycleListener.onStarting()
  │     └─▶ Log service start with configuration
  │
  ├─▶ ListenerManager.start()   (Dropwizard Managed lifecycle)
  │     └─▶ SQSListener.startup()
  │           └─▶ Poll SQS queue continuously (long polling)
  │
  ├─▶ Application Ready
  │     ├─▶ REST APIs accepting requests on port 23493
  │     ├─▶ Inbound processor consuming from SQS
  │     └─▶ Outbound executor routing responses to partners
  │
  └─▶ BookingAppLifecycleListener.onShutdown()
        ├─▶ SQSListener.shutdown() (stop polling)
        ├─▶ Processor executor graceful shutdown (30s timeout)
        ├─▶ Outbound executor graceful shutdown
        └─▶ Log shutdown complete
```

---

## Configuration Management

### Configuration Hierarchy

```
BookingConfig (extends ApplicationConfiguration)
  │
  ├─▶ appianWayConfig: AppianWayConfig
  │     ├─▶ s3WorkSpaceLocation: String (S3 workspace bucket)
  │     ├─▶ transformerSQSUrl: String (Transformer output SQS URL)
  │     ├─▶ inQueueUrl: String (Inbound SQS queue URL)
  │     ├─▶ distributorQueueUrl: String (Outbound distributor SQS URL)
  │     ├─▶ snsTopicARN: String (SNS topic ARN for events)
  │     ├─▶ waitTimeSeconds: int (SQS long polling, default 20s)
  │     ├─▶ maxNumberOfMessages: int (SQS batch size, default 10)
  │     ├─▶ parallelism: int (Processing parallelism)
  │     ├─▶ listenerEnabled: boolean (Enable/disable SQS listener)
  │     └─▶ outboundEnabled: boolean (Enable/disable outbound processing)
  │
  ├─▶ dynamoDbConfig: BaseDynamoDbConfig
  │     ├─▶ environment: String (e.g., "inttra_int_booking")
  │     ├─▶ region: String (AWS region)
  │     ├─▶ endpointOverride: String (Optional, for local DynamoDB)
  │     ├─▶ readCapacityUnits: Long
  │     ├─▶ writeCapacityUnits: Long
  │     └─▶ sseEnabled: boolean (Server-side encryption)
  │
  ├─▶ elasticsearchConfig: ElasticsearchConfig
  │     ├─▶ endpoint: String
  │     ├─▶ shards: int
  │     └─▶ replicas: int
  │
  ├─▶ s3ArchiveBucket: String (S3 bucket for booking archive)
  │
  ├─▶ emailSenderConfig: BookingEmailConfig
  │     ├─▶ sourceEmail: String (Sender email address)
  │     └─▶ internalEmails: List<String> (Internal notification recipients)
  │
  ├─▶ customizationConfig: CustomizationConfig
  │     └─▶ Carrier-specific region routing rules
  │
  ├─▶ spotRatesConfig: SpotRateConfig
  │
  ├─▶ watermillConfig: WatermillConfig
  │     └─▶ aperakQueueUrl: String (APERAK SQS queue)
  │
  ├─▶ bookingBridgeSQS: String (Booking Bridge SQS queue URL)
  │
  ├─▶ maxRetries: int (Max retry attempts)
  ├─▶ maxDelay: int (Max retry delay in ms)
  └─▶ baseDelay: int (Base retry delay in ms)
```

### Configuration File Example

```yaml
server:
  type: default
  rootPath: /booking
  applicationConnectors:
    - type: http
      port: 23493
  adminConnectors:
    - type: http
      port: 23494

appianWayConfig:
  s3WorkSpaceLocation: "booking-workspace-bucket"
  transformerSQSUrl: "https://sqs.us-east-1.amazonaws.com/123456789/transformer-out"
  inQueueUrl: "https://sqs.us-east-1.amazonaws.com/123456789/booking-inbound"
  distributorQueueUrl: "https://sqs.us-east-1.amazonaws.com/123456789/booking-distributor"
  snsTopicARN: "arn:aws:sns:us-east-1:123456789:booking-events"
  waitTimeSeconds: 20
  maxNumberOfMessages: 10
  listenerEnabled: true
  outboundEnabled: true

dynamoDbConfig:
  environment: "inttra_int_booking"
  region: "us-east-1"
  readCapacityUnits: 5
  writeCapacityUnits: 5
  sseEnabled: true

s3ArchiveBucket: "booking-archive-bucket"
bookingBridgeSQS: "https://sqs.us-east-1.amazonaws.com/123456789/booking-bridge"
```

---

## Key Components

### 1. BookingApplication

**Location**: `com.inttra.mercury.booking.BookingApplication`

**Purpose**: Main application entry point. Builds and configures the InttraServer with all
Guice modules, Jersey resources, CLI commands, and post-setup hooks.

**Key Methods**:
- `main()`: Entry point
- `newServer()`: Creates InttraServer with 11 Guice modules
- `configureLifecycle()`: Registers `BookingAppLifecycleListener` for executor monitoring
- `startListener()`: Starts `ListenerManager` → `SQSListener` (if `listenerEnabled`)

---

### 2. BookingProcessorTask

**Location**: `com.inttra.mercury.booking.inbound.BookingProcessorTask` (716 lines)

**Purpose**: Core inbound message processing coordinator. Receives SQS messages, reads
canonical booking JSON from S3, and routes to the appropriate processing path.

**Injected Dependencies**:
- `S3WorkspaceService` — Reads canonical booking XML/JSON from S3
- `BookingService` — Core business logic
- `PartyLocator` — Resolves party information
- `OutboundService` — Routes outbound responses
- `EventLogger` — Publishes workflow events to SNS
- `ExecutorService("processor")` — 8-thread executor for async processing
- `MigrationLogic` — Handles legacy migration rules
- `BookingConfig` — Application configuration
- `NonInttraBookingValidator` — Validates non-INTTRA bookings
- `SQSClient` — Routes messages to Booking Bridge and DLQ

**Key Methods**:
- `process(List<QueueMessage<String>>, Consumer<QueueMessage<String>>)`: Batch processor entry point
- `execute(QueueMessage<String>, Consumer<QueueMessage<String>>)`: Single message processor
- `executeRAC(MetaData, ...)`: Handles Request A Change (booking request) flow
- `executeCPD(MetaData, QueueMessage<String>, ...)`: Handles Confirm Pending (carrier confirmation) flow
- `routeToBookingBridge(MetaData)`: Routes message to Booking Bridge SQS queue

**Flow**:
```
process(messages, deleteCallback)
  │
  ├─▶ For each QueueMessage<String>:
  │     └─▶ executor.submit(() -> execute(message, deleteCallback))
  │
  └─▶ execute(message, callback)
        │
        ├─▶ Deserialize MetaData from message.getPayload()
        │
        ├─▶ Read S3 bucket/key from MetaData projections
        │
        ├─▶ EventLogger.logStartRunEvent()
        │
        ├─▶ s3WorkspaceService.getContent(bucket, inboundFile) → canonical JSON
        │
        ├─▶ Route by contextCode:
        │     ├─▶ "RAC" → executeRAC()
        │     │     ├─▶ Parse BookingMessage
        │     │     ├─▶ BookingService.processRAC()
        │     │     ├─▶ Process outbound response
        │     │     └─▶ routeToBookingBridge() if applicable
        │     │
        │     └─▶ "CPD" → executeCPD()
        │           ├─▶ Parse ConfirmPendingMessage
        │           ├─▶ Validate BookingState, carrier party
        │           ├─▶ Handle NIB (Non-INTTRA Booking) logic
        │           ├─▶ BookingService.processCPD()
        │           └─▶ Process outbound response
        │
        ├─▶ On Success:
        │     ├─▶ EventLogger.logCloseRunEvent()
        │     └─▶ deleteCallback.accept(message)  (Delete from SQS)
        │
        └─▶ On Error:
              ├─▶ Comprehensive exception handling:
              │     TransformationException, StructuralValidationException,
              │     AuthorizationException, BookingNotFoundException,
              │     ResolutionException, BookingValidationException,
              │     StateTransitionException, InternalException
              ├─▶ EventLogger.logCloseRunEvent() with error
              └─▶ Retry-eligible errors leave message in SQS
                   (visibility timeout re-delivers)
```

**Dependencies**:
- BookingService
- S3WorkspaceService
- EventLogger
- SQSClient
- OutboundService
- ExecutorService (named "processor")
- BookingConfig

---

### 3. BookingService

**Location**: `com.inttra.mercury.booking.service.BookingService` (1,227 lines)

**Purpose**: Core business logic for the entire booking lifecycle.

**Injected Dependencies**:
- `BookingDetailDao` — DynamoDB persistence
- `BookingLocator` — Booking lookup (by various keys)
- `BookingEventRelay` — Event relay to external systems
- `ValidationService` — Business rule validation (24 validator classes)
- `OutboundServiceImpl` — Outbound message routing
- `IdGenerator` — `UniqueIdDao` + `SequenceIdDao` for booking ID generation
- `EventLogger` — Workflow event publishing
- `S3ArchiveHandler` — S3 archival (injected for direct archival use)
- `RapidReservationService` — Rapid reservation management
- `MigrationLogic` — Legacy system migration
- `CarrierSpotRatesService` — Carrier spot rates
- `NetworkParticipantService` — Participant resolution
- `BookingConfig` / `S3WorkspaceService` / `AppianWayConfig`

**Key Operations**:
```
BookingService
  │
  ├─▶ processRAC(BookingMessage):   Request booking flow
  │     ├─▶ Validate → Transform → Generate IDs
  │     ├─▶ Save to DynamoDB
  │     ├─▶ Index to Elasticsearch
  │     ├─▶ Write to S3 workspace
  │     └─▶ Trigger outbound
  │
  ├─▶ processCPD(ConfirmPendingMessage):   Confirmation flow
  │     ├─▶ Locate existing booking
  │     ├─▶ Validate state transition
  │     ├─▶ Update booking state
  │     ├─▶ Save to DynamoDB
  │     ├─▶ Index to Elasticsearch
  │     └─▶ Write to S3 workspace
  │
  ├─▶ processDecline(DeclineMessage):   Decline flow
  │
  ├─▶ processCancel(CancelMessage):    Cancellation flow
  │
  └─▶ processAmendment(AmendmentMessage):   Amendment flow
```

---

### 4. SQSClient

**Location**: `com.inttra.mercury.booking.common.messaging.SQSClient`

**Purpose**: Thin wrapper around cloud-sdk `MessagingClient<String>` that adds error handling
and logging.

**Constructor**: `@Inject SQSClient(MessagingClient<String> messagingClient)`

**Key Methods**:
```java
public void sendMessage(String target, String content)
    // Delegates to messagingClient.sendMessage(target, content)
    // Wraps errors in UnrecoverableAWSException

public void deleteMessage(String queueUrl, String receiptHandle)
    // Delegates to messagingClient.deleteMessage(queueUrl, receiptHandle)
    // Wraps errors in UnrecoverableAWSException

public List<QueueMessage<String>> receiveMessage(String queueUrl, int maxMessages, int waitTime)
    // Builds ReceiveMessageOptions via builder pattern
    // Delegates to messagingClient.receiveMessages(queueUrl, options)
    // Returns List<QueueMessage<String>>
```

---

### 5. SNSClient

**Location**: `com.inttra.mercury.booking.common.messaging.SNSClient`

**Purpose**: Thin wrapper around cloud-sdk `NotificationService` for publishing events.

**Constructor**: `@Inject SNSClient(NotificationService notificationService)`

**Key Method**:
```java
public void sendMessage(String target, String content)
    // Delegates to notificationService.publish(target, content)
    // Wraps errors in UnrecoverableAWSException
```

---

### 6. SQSListener

**Location**: `com.inttra.mercury.booking.common.listener.SQSListener`

**Purpose**: Continuous SQS polling loop. Implements `Listener` (startup/shutdown).
Managed by `ListenerManager` which implements Dropwizard `Managed` lifecycle.

**Constructor**:
```java
public SQSListener(SQSClient sqs, String queueUrl, int waitTimeSeconds,
                   int maxNumberOfMessages,
                   BiConsumer<List<QueueMessage<String>>, Consumer<QueueMessage<String>>> taskProcessor)
```

**Flow**:
```
startup()
  │
  └─▶ while (running):
        │
        ├─▶ sqs.receiveMessage(queueUrl, maxMessages, waitTimeSeconds)
        │     └─▶ Returns List<QueueMessage<String>> (long polling, up to 20s)
        │
        ├─▶ If messages received:
        │     └─▶ taskProcessor.accept(messages, this::deleteAndCount)
        │           │
        │           └─▶ BookingProcessorTask.process(messages, deleteCallback)
        │
        └─▶ deleteAndCount(message):
              └─▶ sqs.deleteMessage(queueUrl, message.getReceiptHandle())

shutdown()
  └─▶ running = false (exits polling loop)
```

---

### 7. S3WorkspaceService

**Location**: `com.inttra.mercury.booking.common.s3.S3WorkspaceService`

**Purpose**: Implements `WorkspaceService` for S3 read/write operations using cloud-sdk
`StorageClient`.

**Constructor**: `@Inject S3WorkspaceService(StorageClient storageClient)`

**Key Methods**:
```java
public void copyObject(String srcBucket, String srcKey, String destBucket, String destKey)
    // Delegates to storageClient.copyObject(...)

public boolean putObject(String bucket, String fileName, String content)
    // Delegates to storageClient.putObject(bucket, fileName, content)
    // Returns boolean (success/failure)

public String getContent(String bucket, String fileName)
    // Gets StorageObject from storageClient.getObject(bucket, fileName)
    // Reads InputStream via BufferedReader.lines()
    // Catches IOException and UncheckedIOException → UnableToReadS3Object
    // Wraps all errors in UnrecoverableAWSException

public String getContent(String bucket, String fileName, Charset charset)
    // Same as above with charset support
    // Wraps errors in IOException
```

---

### 8. ListenerManager

**Location**: `com.inttra.mercury.booking.common.listener.support.ListenerManager`

**Purpose**: Dropwizard `Managed` lifecycle adapter for the SQS listener.

```java
public class ListenerManager implements Managed {
    private final Listener sqsListener;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @Override
    public void start() { executor.submit(sqsListener::startup); }

    @Override
    public void stop() { sqsListener.shutdown(); executor.shutdown(); }
}
```

---

### 9. SNSEventPublisher

**Location**: `com.inttra.mercury.booking.common.event.SNSEventPublisher`

**Purpose**: Publishes workflow events (`START_RUN`, `CLOSE_RUN`, `ERROR`) to SNS topic
for downstream consumers such as monitoring and tracking.

```java
public class SNSEventPublisher implements EventPublisher {
    private final String topicArn;
    private final SNSClient messageSender;

    @Inject
    public SNSEventPublisher(AppianWayConfig config, SNSClient snsClient) { ... }

    @Override
    public void publishEvent(List<Event> events) {
        // Serializes events to JSON
        // Sends to SNS topic via SNSClient.sendMessage(topicArn, json)
        // On failure: logs "SNS_Failed_AFTER_RETRY" with payload
    }
}
```

---

### 10. EventLogger

**Location**: `com.inttra.mercury.booking.common.event.EventLogger` (158 lines)

**Purpose**: High-level abstraction for workflow event lifecycle. Creates and publishes
structured workflow events (open/close/error) to SNS via `EventPublisher`.

**Key Methods**:
```java
public Event logStartRunEvent(MetaData metaData, String componentSuffix)
    // Creates START_RUN event with workflowId
    // Publishes via eventPublisher
    // Caches MetaData for workflow tracking

public void logCloseRunEvent(Event event, MetaData metaData, boolean success, Map<String,String> tokens)
    // Creates CLOSE_RUN event
    // Publishes via eventPublisher
    // Removes workflow from cache
```

---

## AWS Service Integration

### 1. SQS (Simple Queue Service)

**Integration via**: `cloud-sdk-api` `MessagingClient<String>` interface

**Implementation**: `SqsMessagingClient` from `cloud-sdk-aws` (AWS SDK v2)

**Configuration**:
```java
// Provided by BookingMessagingModule
@Provides @Singleton
public MessagingClient<String> provideMessagingClient() {
    return MessagingClientFactory.createDefaultStringClient();
}
```

**Usage Points**:

| Component | Operation | Purpose |
|-----------|-----------|---------|
| `SQSListener` | `receiveMessage()` | Long-poll inbound queue for booking messages |
| `SQSListener` | `deleteMessage()` | Acknowledge processed messages |
| `BookingProcessorTask` | `sendMessage()` | Route to Booking Bridge queue |
| `OutboundService` | `sendMessage()` | Route outbound responses to distributor queue |

**Queue URLs** (from configuration):
```
inQueueUrl:          SQS queue for inbound booking messages
distributorQueueUrl: SQS queue for outbound distribution to partners
bookingBridgeSQS:    SQS queue for booking bridge routing
watermillConfig.aperakQueueUrl: SQS queue for APERAK messages
```

**Key Behavioral Change** (AWS SDK 2.x):
```java
// OLD: AWS SDK 1.x — Message is mutable
Message message = ...;
message.getBody();          // Read message body

// NEW: cloud-sdk — QueueMessage<String> is IMMUTABLE
QueueMessage<String> message = ...;
message.getPayload();       // Read message payload

```

---

### 2. SNS (Simple Notification Service)

**Integration via**: `cloud-sdk-api` `NotificationService` interface

**Implementation**: `SnsNotificationService` from `cloud-sdk-aws` (AWS SDK v2)

**Configuration**:
```java
// Provided by BookingMessagingModule
@Provides @Singleton
public NotificationService provideNotificationService(BookingConfig config) {
    String topicArn = config.getAppianWayConfig().getSnsTopicARN();
    return NotificationClientFactory.createDefaultClient(topicArn);
}
```

**Usage in SNSEventPublisher**:
```java
public class SNSEventPublisher implements EventPublisher {
    @Override
    public void publishEvent(List<Event> events) {
        String json = objectMapper.writeValueAsString(events);
        messageSender.sendMessage(topicArn, json);
    }
}
```

**Event Types Published**:
- `START_RUN_EVENT`: Workflow started (inbound message received)
- `CLOSE_RUN_EVENT`: Workflow completed (success or error)
- `INFO_EVENT`: Informational events during processing

---

### 3. S3 (Simple Storage Service)

**Integration via**: `cloud-sdk-api` `StorageClient` interface

**Implementation**: `S3StorageClient` from `cloud-sdk-aws` (AWS SDK v2)

**Configuration**:
```java
// Provided by BookingMessagingModule
@Provides @Singleton
public StorageClient provideStorageClient() {
    return StorageClientFactory.createDefaultS3Client();
}
```

**Usage Points**:

| Component | Operation | Purpose |
|-----------|-----------|---------|
| `S3WorkspaceService` | `getObject()` | Read canonical booking JSON/XML from workspace |
| `S3WorkspaceService` | `putObject()` | Write transformed booking content to workspace |
| `S3WorkspaceService` | `copyObject()` | Copy objects between buckets |
| `S3ArchiveHandler` | `putObject()` | Archive booking snapshots (Lambda) |

**S3 Buckets** (from configuration):
```
appianWayConfig.s3WorkSpaceLocation:  Workspace bucket for booking processing
s3ArchiveBucket:                      Archive bucket for booking snapshots
```

**StorageObject Usage**:
```java
StorageObject storageObject = storageClient.getObject(bucket, fileName);
InputStream content = storageObject.getContent();
// Read content via BufferedReader or byte array
```

---

### 4. DynamoDB

**Integration via**: `cloud-sdk-api` `DatabaseRepository<T, ID>` interface

**Implementation**: AWS SDK v2 Enhanced Client via `cloud-sdk-aws`

**7 DynamoDB Tables**:

| Table Name | Entity | Key Type | Partition Key | Sort Key | GSIs |
|------------|--------|----------|---------------|----------|------|
| BookingDetail | `BookingDetail` | Composite | `bookingId` | `sequenceNumber` | 4 |
| UniqueId | `UniqueId` | Partition | `id` (Long) | — | 0 |
| SequenceId | `SequenceId` | Partition | `id` (String) | — | 0 |
| RapidReservation | `RapidReservation` | Composite | — | — | — |
| TemplateSummary | `TemplateSummary` | Composite | — | — | — |
| SpotRatesDetail | `SpotRatesDetail` | Partition | — | — | — |
| SpotRatesToInttraRefDetail | `SpotRatesToInttraRefDetail` | Partition | — | — | — |

**BookingDetail GSIs** (all `ProjectionType.ALL`):

| Index Name | Partition Key | Sort Key |
|------------|---------------|----------|
| `carrierId_carrierReferenceNumber` | `carrierId` | `carrierReferenceNumber` |
| `bookerId_shipmentId` | `bookerId` | `shipmentId` |
| `INTTRA_REFERENCE_NUMBER_INDEX` | `inttraReferenceNumber` | — |
| `carrierScac_carrierReferenceNumber` | `carrierScac` | `carrierReferenceNumber` |

**Configuration**:
```java
// Provided by BookingDynamoModule
@Provides @Singleton
public DynamoDbClientConfig provideDynamoDbClientConfig(BookingConfig config) {
    final BaseDynamoDbConfig dynamoConfig = config.getDynamoDbConfig();
    return dynamoConfig.toClientConfigBuilder()
        .consistentRead(false)
        .build();
}

@Provides @Singleton
public BookingDetailDao provideBookingDetailDao(DynamoDbClientConfig clientConfig) {
    DatabaseRepository<BookingDetail, DefaultCompositeKey<String, String>> repo =
        createCompositeKeyRepository(clientConfig, BookingDetail.class, false);
    return new BookingDetailDao(repo);
}
```

**Table Naming Convention**:
```
Pattern: {environment}_{table_name}
Example: inttra_int_booking_BookingDetail
```

---

## Cloud SDK Integration

### Architecture Overview

```
Booking Service
      │
      ├─▶ cloud-sdk-api (Vendor-Neutral Interfaces)
      │     ├─▶ MessagingClient<T>        — SQS operations
      │     ├─▶ QueueMessage<T>           — Immutable message wrapper
      │     ├─▶ ReceiveMessageOptions     — Builder for receive config
      │     ├─▶ NotificationService       — SNS publish
      │     ├─▶ StorageClient             — S3 read/write/copy
      │     ├─▶ StorageObject             — S3 object with content stream
      │     ├─▶ DatabaseRepository<T, ID> — DynamoDB CRUD
      │     ├─▶ DefaultCompositeKey<P,S>  — Composite key (PK + SK)
      │     ├─▶ DefaultPartitionKey<P>    — Simple partition key
      │     └─▶ DynamoDbClientConfig      — Client configuration
      │
      └─▶ cloud-sdk-aws (AWS SDK v2 Implementations)
            ├─▶ SqsMessagingClient            — SQS via SqsClient
            ├─▶ SnsNotificationService        — SNS via SnsClient
            ├─▶ S3StorageClient               — S3 via S3Client
            ├─▶ EnhancedDynamoRepository      — DynamoDB Enhanced Client
            ├─▶ MessagingClientFactory        — SQS client factory
            ├─▶ NotificationClientFactory     — SNS client factory
            ├─▶ StorageClientFactory          — S3 client factory
            └─▶ DynamoRepositoryFactory       — Repository factory
```

### Factory Pattern

All cloud-sdk clients are created via factory methods in the Guice modules:

```java
// SQS — MessagingClientFactory
MessagingClient<String> sqs = MessagingClientFactory.createDefaultStringClient();

// SNS — NotificationClientFactory
NotificationService sns = NotificationClientFactory.createDefaultClient(topicArn);

// S3 — StorageClientFactory
StorageClient s3 = StorageClientFactory.createDefaultS3Client();

// DynamoDB — DynamoRepositoryFactory
DatabaseRepository<T, ID> repo = DynamoRepositoryFactory.createEnhancedRepository(
    clientConfig, tableName, domainType, repositoryConfig);
```

### Annotation-Driven DynamoDB Configuration

```java
@Table(name = "BookingDetail")
@DynamoDbBean
public class BookingDetail implements Expires {

    @DynamoDbPartitionKey
    private String bookingId;

    @DynamoDbSortKey
    private String sequenceNumber;

    @DynamoDbVersionAttribute
    private Integer version;                    // Optimistic locking

    @TTL(name = "expiresOn")
    @DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)
    private Date expiresOn;                     // Auto-delete TTL

    @DynamoDbConvertedBy(ContractAttributeConverter.class)
    private Contract payload;                   // Complex nested object

    @DynamoDbSecondaryPartitionKey(indexNames = "carrierId_carrierReferenceNumber")
    private String carrierId;

    @DynamoDbSecondarySortKey(indexNames = {
        "carrierId_carrierReferenceNumber",
        "carrierScac_carrierReferenceNumber"
    })
    private String carrierReferenceNumber;      // Shared sort key across 2 GSIs
}
```

---

## Data Access Layer

### DAO Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                     BookingService                               │
│                  (Business Logic Layer)                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BookingDetailDao                               │
│                  (Data Access Layer)                              │
│                                                                   │
│  + save(BookingDetail): BookingDetail                            │
│  + findByBookingId(String): List<BookingDetail>                 │
│  + findByBookingIds(Set<String>): List<BookingDetail>           │
│  + findByInttraReferenceNumber(String): List<BookingDetail>     │
│  + findByCarrierIdAndCarrierRefNum(String, String): List<...>  │
│  + findBySubmitterIdAndShipmentId(String, String): List<...>   │
│  + findByCarrierScacAndCarrierRefNum(String, String): List<...>│
│  + findByBookingIdSequenceNumber(String, String): BookingDetail│
│  + findLatestCarrierAndCustomerVersions(String): List<...>     │
│  + delete(String, String): void                                 │
│  + update(BookingDetail): BookingDetail                         │
│                                                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│     DatabaseRepository<BookingDetail, CompositeKey<S, S>>       │
│                  (cloud-sdk-api Interface)                       │
│                                                                   │
│  + save(T): T                                                    │
│  + findById(ID, boolean): Optional<T>                           │
│  + deleteById(ID): void                                         │
│  + findAll(): List<T>                                           │
│  + query(IndexQuery): List<T>   (GSI queries)                   │
│                                                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              EnhancedDynamoRepository                             │
│            (cloud-sdk-aws Implementation)                        │
│                                                                   │
│  Uses: DynamoDbEnhancedClient (AWS SDK v2)                      │
│  Uses: DynamoDbTable<T>                                         │
│  Uses: TableSchema.fromBean()                                   │
│                                                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
              ┌───────────────────────────┐
              │  DynamoDB Tables (7)      │
              │  (AWS Service)            │
              │                           │
              │  inttra_int_booking_      │
              │  BookingDetail            │
              │  (+ 6 more tables)        │
              └───────────────────────────┘
```

### GSI Query Pattern

All GSI queries in `BookingDetailDao` follow a consistent pattern:
1. Query the GSI (eventually consistent) to get matching items
2. Re-fetch each result from the main table with `consistentRead(true)` for strong consistency

```java
// Example: findByCarrierIdAndCarrierReferenceNumber
public List<BookingDetail> findByCarrierIdAndCarrierReferenceNumber(
        String carrierId, String carrierRefNum) {
    // 1. GSI query (eventually consistent)
    List<BookingDetail> gsiResults = repository.query(
        IndexQuery.builder()
            .indexName("carrierId_carrierReferenceNumber")
            .partitionKeyValue(carrierId)
            .sortKeyValue(carrierRefNum)
            .build()
    );

    // 2. Re-fetch from main table (strongly consistent)
    return gsiResults.stream()
        .map(bd -> repository.findById(
            new DefaultCompositeKey<>(bd.getBookingId(), bd.getSequenceNumber()),
            true))
        .filter(Optional::isPresent)
        .map(Optional::get)
        .collect(Collectors.toList());
}
```

---

## Message Processing Flow

### End-to-End Inbound Flow

```
┌──────────────────┐
│   SQS Queue      │
│  (Inbound)       │
│                  │
│ [Message 1]      │    MetaData JSON containing:
│ [Message 2]      │    - s3Bucket, s3Key (canonical booking location)
│ [Message N]      │    - contextCode: "RAC" or "CPD"
└──────┬───────────┘    - projections: XLOG_ID, BOOKING_ID, etc.
       │
       │ (1) Long Polling (20s, max 10 messages)
       ▼
┌──────────────────────┐
│   SQSListener        │
│   pollAndExecute()   │
│                      │
│   QueueMessage<String>│  (immutable, no setPayload())
└──────┬───────────────┘
       │
       │ (2) Submit to 8-thread executor
       ▼
┌───────────────────────────────────────────────────────────┐
│   BookingProcessorTask                                     │
│   execute(QueueMessage<String>, Consumer<QueueMessage>)   │
└──────┬────────────────────────────────────────────────────┘
       │
       │ (3) Deserialize MetaData, read from S3
       ▼
┌──────────────────────────────────────────────────────────┐
│   S3WorkspaceService.getContent(bucket, s3Key)           │
│                                                            │
│   StorageClient → StorageObject → InputStream → String   │
└──────┬───────────────────────────────────────────────────┘
       │
       │ (4) Route by contextCode
       ▼
┌──────────────────────────┐     ┌──────────────────────────┐
│   "RAC" → executeRAC()  │     │   "CPD" → executeCPD()   │
│                          │     │                          │
│   Parse BookingMessage   │     │   Parse ConfirmPending   │
│   Validate booking       │     │   Validate state         │
│   Transform content      │     │   Handle NIB logic       │
│   Generate IDs           │     │   Update booking state   │
│   Save to DynamoDB       │     │   Save to DynamoDB       │
│   Index to ES            │     │   Index to ES            │
│   Write to S3            │     │   Write to S3            │
│   Trigger outbound       │     │   Trigger outbound       │
└──────────────────────────┘     └──────────────────────────┘
       │                                  │
       │ (5) On Success                   │
       ▼                                  ▼
┌─────────────────────────────────────────────────────┐
│   EventLogger.logCloseRunEvent()                     │
│   → SNSEventPublisher.publishEvent()                │
│   → SNSClient.sendMessage(topicArn, json)           │
│   → NotificationService.publish()  (cloud-sdk-api)  │
└─────────────────────────────────────────────────────┘
       │
       │ (6) Acknowledge message
       ▼
┌─────────────────────────────────────────────────────┐
│   deleteCallback.accept(message)                     │
│   → SQSListener.deleteAndCount(message)             │
│   → SQSClient.deleteMessage(queueUrl, receiptHandle)│
│   → MessagingClient.deleteMessage()  (cloud-sdk-api)│
└─────────────────────────────────────────────────────┘
```

### Error Handling Flow

```
execute() throws Exception
  │
  ├─▶ TransformationException       → Log error, close workflow, delete message
  ├─▶ StructuralValidationException → Log error, close workflow, delete message
  ├─▶ AuthorizationException        → Log error, close workflow, delete message
  ├─▶ BookingNotFoundException      → Log error, close workflow, delete message
  ├─▶ ResolutionException           → Leave in queue for retry (visibility timeout)
  ├─▶ BookingValidationException    → Log error, close workflow, delete message
  ├─▶ StateTransitionException      → Log error, close workflow, delete message
  ├─▶ InternalException             → Leave in queue for retry (visibility timeout)
  └─▶ Exception (unexpected)        → Log error, close workflow, delete message
```

### Message Format

**SQS Message Body (MetaData)**:
```json
{
  "workflowId": "wf-12345-abc",
  "parentWorkflowId": "parent-wf-67890",
  "rootWorkflowId": "root-wf-11111",
  "s3Bucket": "booking-workspace",
  "s3Key": "bookings/2026/02/request-12345.json",
  "executionName": "booking-inbound",
  "timestamp": "2026-02-20T10:30:00Z",
  "projections": {
    "XLOG_ID": "XLOG-12345-ABC",
    "BOOKING_ID": "BK-UUID-001",
    "CONTEXT_CODE": "RAC",
    "INBOUND_S3_FILENAME": "inbound/request.xml",
    "CANONICAL_JSON_PATH": "canonical/booking.json",
    "IS_NON_INTTRA_BOOKING": "false"
  }
}
```

---

## Outbound Processing Flow

```
BookingProcessorTask.execute()
  │
  ├─▶ BookingService.processRAC() / processCPD()
  │     └─▶ Returns outbound response data
  │
  └─▶ OutboundService.processOutboundMessage(response)
        │
        │ (Submitted to 32-thread outbound executor)
        ▼
  ┌──────────────────────────────────────────────────────┐
  │  OutboundServiceImpl                                  │
  │                                                        │
  │  1. Enrich booking response                           │
  │     ├─▶ Location enrichment (GeographyService)       │
  │     ├─▶ Party resolution (ParticipantService)        │
  │     └─▶ Subscription lookup (SubscriptionService)    │
  │                                                        │
  │  2. Transform to outbound format                      │
  │                                                        │
  │  3. Write to S3 workspace                             │
  │     └─▶ s3WorkspaceService.putObject(bucket, key, content)
  │                                                        │
  │  4. Send to distributor SQS queue                     │
  │     └─▶ sqsClient.sendMessage(distributorQueueUrl, metaDataJson)
  │                                                        │
  │  5. Publish close event to SNS                        │
  │     └─▶ eventLogger.logCloseRunEvent()                │
  └──────────────────────────────────────────────────────┘
        │
        ▼
  ┌──────────────┐        ┌──────────────────┐
  │ Distributor  │───────▶│ Partner Delivery │
  │ SQS Queue    │        │ (via EDI/API)    │
  └──────────────┘        └──────────────────┘
```

---

## Lambda Architecture

### S3ArchiveHandler

**Location**: `com.inttra.mercury.booking.lambda.S3ArchiveHandler` (320 lines)

**Purpose**: AWS Lambda function triggered by DynamoDB Streams on `BookingDetail` table
INSERT events. Archives booking snapshots to S3 and sends to Track & Trace.

**Trigger Chain**:
```
DynamoDB BookingDetail Table
  │
  └─▶ DynamoDB Streams (INSERT event)
        │
        └─▶ SNS Topic
              │
              └─▶ SQS Queue
                    │
                    └─▶ S3ArchiveHandler Lambda (SQSEvent trigger)
```

**Processing Flow**:
```
handleRequest(SQSEvent)
  │
  ├─▶ For each SQS record:
  │     │
  │     ├─▶ Extract SNS message from SQS body
  │     │
  │     ├─▶ Extract DynamodbEvent from SNS message
  │     │
  │     ├─▶ For each DynamoDB record (INSERT only):
  │     │     │
  │     │     ├─▶ Deserialize BookingDetail from DynamoDB image
  │     │     │
  │     │     ├─▶ Determine archive bucket:
  │     │     │     ├─▶ Core booking → s3ArchiveBucket
  │     │     │     └─▶ SO booking → soArchiveBucket
  │     │     │
  │     │     ├─▶ Generate S3 key:
  │     │     │     └─▶ YYYY/MM/DD/HH/bookingId_sequenceNumber
  │     │     │
  │     │     ├─▶ Archive to S3:
  │     │     │     └─▶ storageClient.putObject(bucket, key, serializedBooking)
  │     │     │
  │     │     └─▶ Send to Track & Trace:
  │     │           └─▶ snsClient.sendMessage(trackTraceTopicArn, trackingPayload)
  │     │
  │     └─▶ Return success
  │
  └─▶ HandlerSupport utility methods:
        ├─▶ newBookingDetailDao()  → DynamoRepositoryFactory (Lambda environment)
        ├─▶ getSNSClient()        → NotificationClientFactory.createDefaultClient()
        └─▶ getStorageClient()    → StorageClientFactory.createDefaultS3Client()
```

**Key Difference (Lambda vs Server)**:
```
Server:  Clients injected via Guice from BookingMessagingModule
Lambda:  Clients created directly via cloud-sdk-aws factories
         (no DI container in Lambda cold start)
```

---

## Dependency Diagram

### Class Dependency Graph

```
                           ┌─────────────────────────┐
                           │  BookingApplication      │
                           │     (Main Entry Point)   │
                           └────────────┬─────────────┘
                                        │
          ┌──────────────┬──────────────┼──────────────┬──────────────┐
          │              │              │              │              │
          ▼              ▼              ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐
│ Application  │ │  Messaging   │ │   Dynamo     │ │ Inbound  │ │ Outbound │
│  Injector    │ │   Module     │ │   Module     │ │  Module  │ │  Module  │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └───┬──────┘ └───┬──────┘
       │                │                │             │             │
       │           ┌────┴────┐      ┌────┴────┐        │             │
       │           │         │      │         │        │             │
       │           ▼         ▼      ▼         ▼        ▼             ▼
       │    ┌──────────┐ ┌──────┐ ┌─────┐ ┌──────┐ ┌────────┐ ┌──────────┐
       │    │Messaging │ │Notif.│ │Store│ │Dynamo│ │8-thread│ │32-thread │
       │    │Client    │ │Serv. │ │Client│ │Repos │ │executor│ │executor  │
       │    │(SQS)     │ │(SNS) │ │(S3) │ │(DDB) │ │(inbound│ │(outbound)│
       │    └──────────┘ └──────┘ └─────┘ └──────┘ └────────┘ └──────────┘
       │
       ├─▶ SQSListener ─────────────▶ SQSClient ────────▶ MessagingClient<String>
       │
       ├─▶ SNSEventPublisher ────────▶ SNSClient ────────▶ NotificationService
       │
       ├─▶ S3WorkspaceService ───────────────────────────▶ StorageClient
       │
       └─▶ S3ArchiveHandler ─────────────────────────────▶ StorageClient
```

### Guice Dependency Injection

```
BookingConfig ──────────────────────────────┐
  │                                         │
  ├─▶ AppianWayConfig ─────────────────┐    │
  │                                    │    │
  │                                    ▼    ▼
  │                        ┌─────────────────────────┐
  │                        │  BookingMessagingModule  │
  │                        └───────────┬─────────────┘
  │                                    │
  │                                    ├─▶ MessagingClient<String>
  │                                    │     └─▶ MessagingClientFactory.createDefaultStringClient()
  │                                    │
  │                                    ├─▶ NotificationService
  │                                    │     └─▶ NotificationClientFactory.createDefaultClient(topicArn)
  │                                    │
  │                                    └─▶ StorageClient
  │                                          └─▶ StorageClientFactory.createDefaultS3Client()
  │
  ├─▶ BaseDynamoDbConfig ─────────────────┐
  │                                       │
  │                                       ▼
  │                        ┌─────────────────────────┐
  │                        │   BookingDynamoModule    │
  │                        └───────────┬─────────────┘
  │                                    │
  │                                    ├─▶ DynamoDbClientConfig
  │                                    ├─▶ BookingDetailDao      (Composite key)
  │                                    ├─▶ UniqueIdDao           (Partition key Long)
  │                                    ├─▶ SequenceIdDao         (Partition key String)
  │                                    ├─▶ RapidReservationDao   (Composite key)
  │                                    ├─▶ TemplateSummaryDao    (Composite key)
  │                                    ├─▶ SpotRatesDao          (Partition key String)
  │                                    └─▶ SpotRatesToInttraRefDao (Partition key String)
  │
  └─▶ Environment (Dropwizard)
        │
        ├─▶ InboundServiceModule
        │     ├─▶ ExecutorService("processor")  — 8 threads, CallerRunsPolicy
        │     └─▶ Queue("processor")
        │
        └─▶ OutboundServiceModule
              ├─▶ ExecutorService("outbound")   — 32 threads, CallerRunsPolicy
              ├─▶ Queue("outbound")             — ArrayBlockingQueue(60)
              ├─▶ OutboundService               → OutboundServiceImpl (or Dummy)
              └─▶ EventPublisher                → SNSEventPublisher (or Dummy)
```

### Network Services Dependencies

```
BookingService / BookingProcessorTask
  │
  ├─▶ GeographyService (cached)
  │     └─▶ GET /network/geography/locations/{code}
  │
  ├─▶ NetworkParticipantService (cached)
  │     └─▶ GET /network/participants/{id}
  │
  ├─▶ SubscriptionService (cached)
  │     └─▶ GET /network/subscriptions/{id}
  │
  ├─▶ IntegrationProfileService (cached)
  │     └─▶ GET /network/integration-profiles/{id}
  │
  ├─▶ ReferenceDataService (cached)
  │     └─▶ GET /network/reference-data/{type}/{code}
  │
  └─▶ AuthClient
        └─▶ POST /auth/token (OAuth2 client credentials)
```

---

## Test Coverage

### Test Infrastructure

**Frameworks**:
- **JUnit 5**: Primary test framework (new and rewritten tests)
- **TestNG**: Legacy tests (e.g., `TransformerServiceTest`, `TransformerTest`)
- **Mockito 5**: Mocking with strict stubbing (`MockitoExtension`)
- **AssertJ 3**: Fluent assertions

**Test File Count**: ~306 test files across all packages

### AWS Integration Tests (Post AWS SDK 2.x Migration)

#### Messaging Tests

| Test Class | Tests | Framework | Description |
|------------|-------|-----------|-------------|
| `SQSClientTest` | 11 | JUnit 5 | `sendMessage`, `deleteMessage`, `receiveMessage` with `MessagingClient` mock |
| `SNSClientTest` | 6 | JUnit 5 | `sendMessage` with `NotificationService` mock, error handling, validation |

**SQSClientTest Details**:
- **SendMessageTests** (5): success, error handling, null/blank target, null content
- **DeleteMessageTests** (2): success, error handling
- **ReceiveMessageTests** (4): success, empty results, error handling, options building

**SNSClientTest Details**:
- **SendMessageTests** (6): success, error handling, multiple topics, null target, null content, blank target

---

#### Storage Tests

| Test Class | Tests | Framework | Description |
|------------|-------|-----------|-------------|
| `S3WorkspaceServiceTest` | 15 | JUnit 5 | `getContent`, `putObject`, `copyObject` with `StorageClient` mock |

**S3WorkspaceServiceTest Nested Groups**:
- **GetContentTests** (5): success, S3 error, IO error → `UnableToReadS3Object`, null stream, error message format
- **GetContentWithCharsetTests** (5): success, S3 error, IO error, null stream, charset handling
- **PutObjectTests** (3): success, error handling, content verification
- **CopyObjectTests** (2): success, error handling

---

#### Listener Tests

| Test Class | Tests | Framework | Description |
|------------|-------|-----------|-------------|
| `SQSListenerTest` | 13 | JUnit 5 | Polling, deletion, lifecycle, error handling |

**SQSListenerTest Nested Groups**:
- **ConstructorTests** (3): valid construction, null SQSClient, null queue URL
- **PollAndExecuteTests** (3): with messages, no messages, processor throws
- **StartupTests** (5): processes in loop, max messages, continues on error, interrupt stops
- **ShutdownTests** (2): stops listener, handles already stopped

---

#### Configuration Tests

| Test Class | Tests | Framework | Description |
|------------|-------|-----------|-------------|
| `BookingMessagingModuleTest` | 5 | JUnit 5 | Guice module factory methods, validation |

**BookingMessagingModuleTest Nested Groups**:
- **ConstructorTests** (2): valid config, null config
- **NotificationServiceValidationTests** (3): null topic ARN, blank topic ARN, valid topic ARN

---

#### Lambda Tests

| Test Class | Tests | Framework | Description |
|------------|-------|-----------|-------------|
| `S3ArchiveHandlerTest` | ~15 | TestNG | Archive flow with `StorageClient` mock |
| `HandlerSupportTest` | ~8 | TestNG | Factory method validation |

---

#### Processor Tests

| Test Class | Tests | Framework | Description |
|------------|-------|-----------|-------------|
| `BookingProcessorTaskTest` | ~85 | TestNG | Full message processing with `QueueMessage<String>`, `MessagingClient` |
| `BookingProcessorTaskIntegrationTest` | ~12 | TestNG | Integration-level processor testing |

---

### Test Execution

**Run All Booking Tests**:
```bash
mvn test -pl booking
```

**Run AWS Integration Tests Only**:
```bash
mvn test -pl booking -Dtest="SQSClientTest,SNSClientTest,S3WorkspaceServiceTest,SQSListenerTest,BookingMessagingModuleTest"
```

**Run Specific Test Class**:
```bash
mvn test -pl booking -Dtest=SQSClientTest
mvn test -pl booking -Dtest=BookingProcessorTaskTest
```

**Build with All Dependencies**:
```bash
mvn clean package -pl booking -am
```

### DynamoDB Integration Tests (DynamoDB Local)

All DynamoDB IT tests extend `BaseDynamoDbIT` from the `dynamo-integration-test` module,
use embedded DynamoDB Local (no Docker), and are tagged with `@Tag("integration")`.
Run via Maven Failsafe plugin.

| Test Class | Tests | Table | Key Type | GSIs | Description |
|------------|------:|-------|----------|------|-------------|
| `BookingDetailDaoIT` | ~22 | BookingDetail | Composite | 4 | CRUD, all 4 GSI queries, multi-ID batch, version increment, latest versions |
| `TemplateSummaryDaoIT` | ~12 | Template | Composite | — | Save, find by company/carrier/port/name, delete |
| `RapidReservationDaoIT` | ~12 | RapidReservation | Composite | — | CRUD, version auto-increment, batch delete |
| `SpotRatesDaoIT` | ~6 | SpotRatesDetail | Partition | 1 | Save, find by key/GSI, `saveSpotRates` |
| `SpotRatesToInttraRefDaoIT` | ~6 | SpotRatesToInttraRefDetail | Partition | 2 | Save, find by key/GSI, `saveSpotRatesToInttraRef` |
| `UniqueIdDaoIT` | 11 | UniqueId | Partition (Long) | — | CRUD, `saveIfNotExist`, TTL/expiresOn, OffsetDateTime converter |
| `SequenceIdDaoIT` | 10 | SequenceId | Partition | — | CRUD, version increment (optimistic locking) |
| `TemplateDaoIT` | 12 | Template | Composite | — | CRUD, sort key prefix (`t_`), TTL, delete-non-existent |
| `BookingDynamoDbAdminCommandIT` | 27 | All 7 tables | — | All | Table creation, GSI validation, TTL, idempotent creation, config resolution |

**Run DynamoDB Integration Tests Only**:
```bash
mvn verify -pl booking -Dit.test="*DaoIT,*CommandIT" -DfailIfNoTests=false
```

**Run Specific DynamoDB IT Test Class**:
```bash
mvn verify -pl booking -Dit.test=UniqueIdDaoIT -DfailIfNoTests=false
```

---

## Deployment

### Build Artifacts

**Uber JAR**:
```bash
mvn clean package -pl booking -am
# Output: booking/target/booking-1.0.jar
```

**Run Server**:
```bash
java -jar booking/target/booking-1.0.jar server booking/conf/int/config.yaml
```

**DynamoDB Table Management**:
```bash
java -jar booking/target/booking-1.0.jar dynamo-create booking/conf/int/config.yaml
```

### Environment Configuration

**AWS Credentials**:
- EC2 Instance Profile (recommended for EC2/ECS)
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- Shared credentials file: `~/.aws/credentials`

**AWS Parameter Store**:
Configuration values support Parameter Store lookups:
```yaml
clientSecret: ${awsps:/booking/auth/client-secret}
```

---

## Email Library Migration (v1.1)

### Overview

The booking service email infrastructure was migrated from the legacy `email-sender` library
(AWS SDK 1.x, `com.inttra.mercury.email`) to the cloud-sdk-aws email library
(AWS SDK 2.x, `com.inttra.mercury.cloudsdk.email`).

### Architecture Changes

**Before (AWS SDK 1.x)**:
```
BookingApplication
  └─▶ EmailSenderModule (from email-sender library)
        └─▶ EmailSenderConfig (source, internalEmailAddresses)
        └─▶ EmailSender → AmazonSimpleEmailService (SDK 1.x)
```

**After (AWS SDK 2.x)**:
```
BookingApplication
  └─▶ BookingEmailSenderModule (booking-specific Guice module)
        └─▶ BookingEmailConfig (sourceEmail, internalEmails)
        └─▶ EmailService → SesEmailServiceImpl (cloud-sdk-aws, SDK 2.x)
              └─▶ SesV2Client (AWS SDK 2.x)
```

### Key Components

#### BookingEmailSenderModule
**Location**: `com.inttra.mercury.booking.config.BookingEmailSenderModule`

Guice module that binds `EmailService` using `EmailClientFactory.createDefaultSesClient()`.
Replaces the old `EmailSenderModule` from `email-sender` library.

```java
@Provides @Singleton
public EmailService provideEmailService() {
    return EmailClientFactory.createDefaultSesClient(EMAIL_TEMPLATE_LIST);
}
```

Templates loaded: `RequestAmendTemplate.json`, `CancelTemplate.json`,
`DeclineReplaceTemplate.json`, `InternalErrorTemplate.json`,
`PendingConfirmTemplate.json`, `ValidationErrorTemplate.json`

#### BookingEmailConfig
**Location**: `com.inttra.mercury.booking.config.BookingEmailConfig`

Replaces legacy `EmailSenderConfig`. Mapped to YAML key `emailSenderConfig`:

| Old Field (`EmailSenderConfig`)  | New Field (`BookingEmailConfig`) |
|----------------------------------|----------------------------------|
| `source: String`                 | `sourceEmail: String`            |
| `internalEmailAddresses: List`   | `internalEmails: List<String>`   |

#### Email Variable Converters
The email variable converter classes (`RequestAmendEmailVariablesConverter`,
`ConfirmPendingEmailVariablesConverter`, `DeclineReplaceEmailVariablesConverter`,
`CancelEmailVariablesConverter`) now inject `BookingEmailConfig` instead of
`EmailSenderConfig`, using `getSourceEmail()` and `getInternalEmails()`.

#### OutboundEmailSender
**Location**: `com.inttra.mercury.booking.outbound.email.OutboundEmailSender`

Uses `EmailService.sendTemplateEmail()` which returns `EmailResultCollector<EmailSendResult>`.
The result collector pattern uses `EmailResultCollectorImpl` (non-generic) from
`com.inttra.mercury.cloudsdk.email.legacy.api`.

### Affected Files

| File | Change |
|------|--------|
| `BookingApplication.java` | `EmailSenderModule` → `BookingEmailSenderModule` |
| `BookingEmailSenderModule.java` | New file: Guice module for `EmailService` |
| `BookingEmailConfig.java` | New file: Replaces `EmailSenderConfig` |
| `BookingConfig.java` | Field type `EmailSenderConfig` → `BookingEmailConfig` |
| `OutboundEmailSender.java` | Inject `BookingEmailConfig`, use `EmailService` |
| `OutboundEmailService.java` | Inject `BookingEmailConfig` |
| `OutboundServiceImpl.java` | Inject `BookingEmailConfig` |
| `*EmailVariablesConverter.java` (4 files) | Inject `BookingEmailConfig` |
| `MetadataVariableConverter.java` | Updated constructor |

---

## DynamoDB Model Annotation Removal (v1.1)

### Overview

All 90+ model/DTO classes had AWS SDK 1.x DynamoDB annotations removed since the
cloud-sdk Enhanced Client uses its own annotation model (`@DynamoDbBean`, etc.)
managed at the repository layer rather than on business model classes.

### Removed Annotations

| Annotation | Count | Description |
|------------|-------|-------------|
| `@DynamoDBDocument` | ~70 | Class-level annotation for DynamoDB documents |
| `@DynamoDBIgnore` | ~15 | Skip field during DynamoDB serialization |
| `@DynamoDBTypeConvertedEnum` | ~10 | Enum conversion annotation |
| `@DynamoDBAttribute` | ~8 | Field-to-attribute mapping |
| `@DynamoDBTypeConverted` | ~5 | Custom type converter annotation |

### Converter Classes

The following converter classes had `implements DynamoDBTypeConverter<X,Y>` removed
since they are now plain utility converters (some also serve as Jackson deserializers):

| Converter | Still Used As |
|-----------|--------------|
| `BookingStateConverter` | Jackson `@JsonDeserialize` |
| `ContractTypeConverter` | JSON converter in tests |
| `OffsetDateTimeTypeConverter` | Jackson `@JsonDeserialize` |
| `ListOfChargeTypeConverter` | Retained (dead code candidate) |
| `QuantityTypeConverter` | Retained (dead code candidate) |
| `SpotRatesConverter` | Retained (dead code candidate) |
| `DateToEpochSecond` | Retained (dead code candidate) |
| `LocalDateTimeTypeConverter` | Retained (dead code candidate) |

---

## POM Dependency Changes (v1.1)

### Removed Dependencies

| Dependency | Reason |
|------------|--------|
| `dynamo-client` (mercury-services-commons) | Replaced by `cloud-sdk-aws` Enhanced Client |
| `email-sender` (mercury-services-commons) | Replaced by `cloud-sdk-aws` email library |
| `aws-java-sdk-datapipeline` | Unused |

### Scope Changes

| Dependency | Old Scope | New Scope | Reason |
|------------|-----------|-----------|--------|
| `aws-java-sdk-dynamodb` | compile | test | Required only for DynamoDB Local integration tests |

### Version Updates

| Dependency | Old Version | New Version | Reason |
|------------|-------------|-------------|--------|
| `aws-lambda-java-events` | 2.2.2 | 3.14.0 | Embeds DynamoDB models (`AttributeValue`, `OperationType`) |
| `mercury.commons.version` | — | 1.0.22-SNAPSHOT | cloud-sdk-api + cloud-sdk-aws (includes numeric PK fix) |

### Import Package Changes

| Old Package | New Package | Affected |
|-------------|-------------|----------|
| `com.inttra.mercury.module.JestModule` | `com.inttra.mercury.cloudsdk.aws.module.JestModule` | 7 files |
| `com.inttra.mercury.config.ElasticSearchServiceConfig` | `com.inttra.mercury.cloudsdk.config.ElasticSearchServiceConfig` | 2 files |
| `com.amazonaws.services.dynamodbv2.model.AmazonDynamoDBException` | `software.amazon.awssdk.services.dynamodb.model.DynamoDbException` | 2 files |
| `com.amazonaws.services.dynamodbv2.model.ConditionalCheckFailedException` | `software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException` | 1 file |
| `com.amazonaws.services.dynamodbv2.model.AttributeValue` | `com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue` | 2 files |
| `com.amazonaws.services.dynamodbv2.model.OperationType` | `com.amazonaws.services.lambda.runtime.events.models.dynamodb.OperationType` | 2 files |

### Exception Changes

| Old Pattern | New Pattern |
|-------------|-------------|
| `new AmazonDynamoDBException(msg)` | `DynamoDbException.builder().message(msg).build()` |
| `new ConditionalCheckFailedException(msg)` | `ConditionalCheckFailedException.builder().message(msg).build()` |
| `DBRecordNotFoundException extends Exception` | `DBRecordNotFoundException extends RuntimeException` |

---

## References

### External Documentation
- [AWS SDK for Java v2](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/)
- [DynamoDB Enhanced Client](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/dynamodb-enhanced-client.html)
- [Dropwizard 4.0 Documentation](https://www.dropwizard.io/en/stable/)
- [Google Guice User Guide](https://github.com/google/guice/wiki)

### Internal Documentation
- cloud-sdk-api Javadoc
- cloud-sdk-aws Javadoc

---

## Version History

| Version | Date       | Changes                                                   |
|---------|------------|-----------------------------------------------------------|
| 1.1     | 2026-02-24 | Email library migration to cloud-sdk-aws SES              |
|         |            | DynamoDB model annotation removal (90 model files)        |
|         |            | Lambda handler DynamoDB model migration (events v3.14.0)  |
|         |            | POM dependency cleanup (removed dynamo-client, email-sender) |
|         |            | JestModule and ElasticSearchServiceConfig import updates   |
|         |            | Exception class migration (DynamoDbException SDK v2)       |
| 1.2     | 2026-02-26 | DynamoDB integration tests: 4 new IT classes (60 tests)   |
|         |            | Library bug fix: numeric partition key type mismatch       |
|         |            | commons version: 1.0.21-SNAPSHOT → 1.0.22-SNAPSHOT        |
| 1.0     | 2026-02-20 | Initial design document (post AWS SDK 2.x migration)      |
|         |            | Covers SQS, SNS, S3, DynamoDB via cloud-sdk abstraction   |

---
