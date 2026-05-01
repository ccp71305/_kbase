# WebBL Service - Design Document

**Contributors:** Arijit Kundu

---

## Contents

1. [Requirements](#requirements)
2. [Assumptions and Open Issues](#assumptions-and-open-issues)
3. [High Level Design](#high-level-design)
4. [Low Level Design](#low-level-design)
5. [Configuration](#configuration)
6. [Auditing/Logging](#auditinglogging)
7. [Metrics and Statistics](#metrics-and-statistics)
8. [Impact on Current Application](#impact-on-current-application)
9. [Resiliency](#resiliency)
10. [Backwards Compatible](#backwards-compatible)
11. [Unit Test Plan](#unit-test-plan)
12. [Pre-Dev Security](#pre-dev-security)
13. [Documentation Changes](#documentation-changes)
14. [Review](#review)

---

## Requirements

The **WebBL Service** is a Mercury platform microservice responsible for processing inbound Bill of Lading (BL) documents (PDF and ZIP formats), archiving BL data in DynamoDB and S3, and distributing outbound notifications to subscribers. It integrates with multiple data stores (DynamoDB, Elasticsearch, Oracle, MySQL) and AWS services (S3, SQS, SNS, SES).

This document covers the AWS SDK 1.x → 2.x migration via `cloud-sdk-api` and `cloud-sdk-aws` libraries, following the same patterns established in the `network`, `auth`, `registration`, `tx-tracking`, and `booking-bridge` modules.

### Key Responsibilities
- **Message Consumption**: Listens to SQS queues for incoming BL documents (ZIP and PDF)
- **Document Processing**: Parses, validates, and transforms BL documents
- **Data Persistence**: Stores BL versions in DynamoDB with TTL and GSI indexes
- **Document Storage**: Archives BL documents in S3
- **Event Publishing**: Publishes BL workflow events to SNS topics
- **BL Retrieval**: Exposes REST APIs backed by Elasticsearch for BL search and retrieval
- **Email Notifications**: Sends status emails on processing success/failure
- **Subscription Distribution**: Routes BL documents to subscribers via email/FTP

### Technology Stack
- **Framework**: Dropwizard 4.0.x
- **Dependency Injection**: Google Guice
- **AWS SDK**: Version 2 (via cloud-sdk-aws 1.0.22-SNAPSHOT)
- **Messaging**: SQS, SNS (via cloud-sdk-api)
- **Storage**: S3 (via cloud-sdk-api StorageClient)
- **Email**: SES (via cloud-sdk-api EmailService)
- **Event Workflow**: `MetaData`, `Event`, `EventLogger`, `EventGenerator`, `EventPublisher` (via cloud-sdk-api `notification.workflow` — replaces legacy `messaging-helper` commons)
- **Database**: DynamoDB (via cloud-sdk-api Enhanced Client), MySQL, Oracle (via MyBatis)
- **Search**: Elasticsearch (via Jest)
- **Testing**: JUnit Jupiter 6.1.0-M1, Mockito 5.20.0, AssertJ 4.0.0-M1

Detailed design documents for "cloud-sdk-api" and "cloud-sdk-aws" implementations are available at the below locations. This has been extensively reviewed with Development team over various team meetings:

1. [AWS Java SDK upgrade - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
2. [High Level Design for AWS Simple Email Service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
3. [High Level Design for AWS Systems Manager Service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
4. [High Level Design for AWS S3 Service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
5. [High Level Design for AWS SNS service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
6. [High Level Design for AWS SQS service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)
7. [High Level Design for AWS Dynamo DB service - INTTRA Ocean Network - e2open Confluence Wiki](https://confluence.e2open.com)

---

## Assumptions and Open Issues

NA

---

## High Level Design

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         WebBL Service                                │
│                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐                         │
│  │ SQS Listener     │  │ SQS Listener     │                         │
│  │ (ZIP Queue)      │  │ (PDF Queue)      │                         │
│  └────────┬─────────┘  └────────┬─────────┘                         │
│           │                      │                                   │
│           ▼                      ▼                                   │
│  ┌──────────────────┐  ┌──────────────────┐                         │
│  │ Zip Inbound      │  │ PDF Inbound      │                         │
│  │ Processor Task   │  │ Processor Task   │                         │
│  └────────┬─────────┘  └────────┬─────────┘                         │
│           │                      │                                   │
│           └──────────┬───────────┘                                   │
│                      ▼                                               │
│           ┌──────────────────┐                                       │
│           │ WebBL Service    │                                       │
│           │ (Business Logic) │                                       │
│           └──────────────────┘                                       │
│                      │                                               │
│     ┌────────────────┼────────────────┬──────────────┐              │
│     ▼                ▼                ▼              ▼              │
│ ┌─────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐         │
│ │ BLDao   │  │ S3Workspace  │  │ SNS      │  │ Email    │         │
│ │         │  │ Service      │  │ Client   │  │ Sender   │         │
│ └─────────┘  └──────────────┘  └──────────┘  └──────────┘         │
│      │              │               │               │               │
└──────┼──────────────┼───────────────┼───────────────┼───────────────┘
       ▼              ▼               ▼               ▼
┌──────────┐  ┌──────────┐   ┌──────────┐    ┌──────────┐
│ DynamoDB │  │   S3     │   │   SNS    │    │   SES    │
│(BL Store)│  │(Archives)│   │  Topic   │    │  Email   │
└──────────┘  └──────────┘   └──────────┘    └──────────┘
```

### Component Interaction Flow

```
External Systems                    WebBL                       AWS Services
┌─────────────┐                                                ┌─────────────┐
│ SQS Queue   │──┐                                            │  DynamoDB   │
│ (ZIP)       │  │                                            │  (BL Store) │
└─────────────┘  │                                            └─────────────┘
                 │                                                   ▲
┌─────────────┐  │                                                   │
│ SQS Queue   │──┤                                            ┌──────────────┐
│ (PDF)       │  │                                            │   BLDao      │
└─────────────┘  │                                            └──────────────┘
                 │                                                   ▲
                 ▼                                                   │
         ┌───────────────┐                               ┌──────────────────┐
         │ SQS Listeners │                               │  WebBL Service   │
         │ (cloud-sdk)   │─────────────────────────────▶│  (Business Logic) │
         └───────────────┘                               └──────────────────┘
                                                                  │
                                                  ┌───────────────┼───────────┐
                                                  ▼               ▼           ▼
                                           ┌───────────┐  ┌──────────┐ ┌──────────┐
                                           │ S3 Storage│  │  SNS     │ │  Email   │
                                           │ (Archive) │  │  Events  │ │  Sender  │
                                           └───────────┘  └──────────┘ └──────────┘
                                                  │              │           │
                                                  ▼              ▼           ▼
                                           ┌───────────┐  ┌──────────┐ ┌──────────┐
                                           │  AWS S3   │  │ AWS SNS  │ │ AWS SES  │
                                           └───────────┘  └──────────┘ └──────────┘
```

### Message Processing Flow

```
SQS Queue (ZIP/PDF)
  │
  ├─▶ SQSListener (cloud-sdk MessagingClient)
  │     └─▶ pollAndExecute()
  │           └─▶ SQSClient.receiveMessage() → List<QueueMessage<String>>
  │
  ├─▶ Processor Task (ZIP or PDF)
  │     ├─▶ Extract payload from QueueMessage<String>.getPayload()
  │     ├─▶ Parse document content
  │     ├─▶ Process BL documents
  │     ├─▶ Store to DynamoDB via BLDao
  │     └─▶ Archive to S3 via StorageClient
  │
  └─▶ Delete message callback
        └─▶ SQSClient.deleteMessage()
```

---

## Low Level Design

### Server

Following are the key changes:

#### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| WebBLApplication | `com.inttra.mercury.webbl.WebBLApplication` | Main application entry point and server configuration |
| WebBLInjector | `com.inttra.mercury.webbl.config.WebBLInjector` | Core Guice module: ES, Auth, SQS listeners |
| WebBLStorageModule | `com.inttra.mercury.webbl.config.WebBLStorageModule` | Guice module: StorageClient for S3 |
| WebBLMessagingModule | `com.inttra.mercury.webbl.config.WebBLMessagingModule` | Guice module: MessagingClient (SQS), NotificationService (SNS), EventPublisher |
| WebBLDynamoModule | `com.inttra.mercury.webbl.config.WebBLDynamoModule` | Guice module: DynamoDbClientConfig, BLDao via DynamoRepositoryFactory |
| S3WorkspaceService | `com.inttra.mercury.webbl.common.s3.S3WorkspaceService` | S3 file operations via StorageClient |
| SNSClient | `com.inttra.mercury.webbl.common.messaging.SNSClient` | SNS publishing via NotificationService |
| SQSClient | `com.inttra.mercury.webbl.common.messaging.SQSClient` | SQS operations via MessagingClient<String> |
| SQSListener | `com.inttra.mercury.webbl.common.listener.SQSListener` | Long-polling SQS listener with QueueMessage<String> |
| BLDao | `com.inttra.mercury.webbl.dao.BLDao` | DynamoDB DAO wrapping DatabaseRepository |
| BLVersion | `com.inttra.mercury.webbl.model.BLVersion` | DynamoDB entity with SDK 2.x Enhanced Client annotations |

#### Guice Module Loading Order

1. **WebBLInjector** (Core bindings)
   - Installs `JestModule` for Elasticsearch
   - Installs `WebBLEmailModule` for SES email via cloud-sdk
   - Binds `AuthClient` singleton
   - Binds `Clock`
   - Provides `@Named("zip")` and `@Named("pdf")` `SQSListener` instances

2. **WebBLStorageModule** (S3)
   - Provides `StorageClient` via `StorageClientFactory.createDefaultS3Client()`

3. **WebBLMessagingModule** (SQS + SNS)
   - Provides `MessagingClient<String>` via `MessagingClientFactory.createDefaultStringClient()`
   - Provides `NotificationService` via `NotificationClientFactory.createDefaultClient(topicArn)`
   - Provides `EventPublisher` via lambda wrapping `SNSClient`

4. **WebBLDynamoModule** (DynamoDB)
   - Provides `DynamoDbClientConfig` from `BaseDynamoDbConfig.toClientConfigBuilder()`
   - Creates `DatabaseRepository<BLVersion, DefaultCompositeKey<String, String>>` via `DynamoRepositoryFactory`
   - Provides `BLDao` wrapping the repository

5. **WebBLEmailModule** (SES email via cloud-sdk)
   - Provides `EmailService` via `EmailClientFactory.createDefaultSesClient(templateFiles)`
   - Provides `@Named("sourceEmail")` from `WebBLConfig.getEmailSenderConfig()`

6. **MyCustomBatisModule** (MySQL + Oracle via MyBatis)

#### AWS Service Integration

| AWS Service | Integration Layer | Implementation |
|-------------|-------------------|----------------|
| S3 | cloud-sdk-api `StorageClient` interface | Default S3 client from cloud-sdk-aws |
| SQS | cloud-sdk-api `MessagingClient<String>` interface | `SqsMessagingClient` from cloud-sdk-aws |
| SNS | cloud-sdk-api `NotificationService` interface | `SnsNotificationService` from cloud-sdk-aws |
| DynamoDB | cloud-sdk-api `DatabaseRepository` interface | AWS SDK v2 Enhanced Client via cloud-sdk-aws |
| SES | cloud-sdk-api `EmailService` interface | `SesEmailServiceImpl` from cloud-sdk-aws |

#### DynamoDB Table Structure

```
Table: {prefix}_bill_of_lading
  Partition Key: id (String)
  Sort Key: sequenceNumber (String)
  GSI: INTTRA_REFERENCE_NUMBER_INDEX
    Partition Key: blInttraReferenceNumber (String)
  TTL Attribute: expiresOn (epoch seconds)
  Nested Beans: 26 @DynamoDbBean model classes
```

#### DynamoDB Annotation Mapping (SDK 1.x → 2.x)

| SDK 1.x Annotation | SDK 2.x / cloud-sdk Annotation |
|---------------------|-------------------------------|
| `@DynamoDBTable(tableName = "...")` | `@DynamoDbBean` + `@Table(name = "...")` |
| `@DynamoDBHashKey` | `@DynamoDbPartitionKey` |
| `@DynamoDBRangeKey` | `@DynamoDbSortKey` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "...")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"..."})` |
| `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` | `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter.class)` |
| `@DynamoDBDocument` | `@DynamoDbBean` |
| `@DynamoDBTypeConvertedEnum` | *(removed — Enhanced Client handles enums as strings by default)* |

### UI

NA

### API Architecture

| Use Case | API | Body | Method (GET/POST/PUT/DELETE) | Query Parameter | Access Privilege (Admin/Non-Admin user) | Authorization Yes/No | Authentication Yes/No | Remarks |
|----------|-----|------|------------------------------|-----------------|----------------------------------------|---------------------|----------------------|---------|
| Retrieve BL | `/{carrierId}/{blNumber}` | - | GET | - | Non-Admin (companyId = 1000 only) | Yes | Yes | Returns BLContract JSON |

---

## Configuration

### Component-Level Configuration

#### Configuration Hierarchy

```yaml
WebBLConfig (extends ApplicationConfiguration)
  │
  ├─▶ dynamoDbConfig: BaseDynamoDbConfig
  │     ├─▶ environment: String (e.g., "inttra_int_webbl")
  │     ├─▶ region: String (AWS region)
  │     ├─▶ endpointOverride: String (Optional, for testing)
  │     ├─▶ readCapacityUnits: Long
  │     ├─▶ writeCapacityUnits: Long
  │     └─▶ sseEnabled: boolean
  │
  ├─▶ appianWayConfig: AppianWayConfig (@Valid @NotNull)
  │     ├─▶ inPDFQueueUrl: String (SQS PDF queue URL)
  │     ├─▶ inZIPQueueUrl: String (SQS ZIP queue URL)
  │     ├─▶ s3WorkSpaceLocation: String (S3 working bucket)
  │     ├─▶ waitTimeSeconds: int (SQS long polling)
  │     ├─▶ maxNumberOfMessages: int (SQS batch size)
  │     └─▶ listenerEnabled: boolean (Enable/disable listeners)
  │
  ├─▶ blElasticSearchConfig: ESConfiguration
  ├─▶ emailSenderConfig: EmailSenderConfig
  ├─▶ snsEventTopicArn: String (SNS topic ARN)
  ├─▶ retryConfig: RetryConfig
  └─▶ s3ArchiveBucket: String (S3 archive bucket)
```

#### Configuration File Example

```yaml
# webbl-config.yaml

snsEventTopicArn: "arn:aws:sns:us-east-1:123456789:webbl-events"
s3ArchiveBucket: "webbl-archive-bucket"

appianWayConfig:
  inPDFQueueUrl: "https://sqs.us-east-1.amazonaws.com/123456789/webbl-pdf-queue"
  inZIPQueueUrl: "https://sqs.us-east-1.amazonaws.com/123456789/webbl-zip-queue"
  s3WorkSpaceLocation: "webbl-workspace"
  waitTimeSeconds: 20
  maxNumberOfMessages: 10
  listenerEnabled: true
  outboundEnabled: true

dynamoDbConfig:
  environment: "inttra_int_webbl"
  region: "us-east-1"
  readCapacityUnits: 5
  writeCapacityUnits: 5
  sseEnabled: true

blElasticSearchConfig:
  host: "http://localhost:9200"
  indexName: "bill_of_lading"

emailSenderConfig:
  fromAddress: "noreply@inttra.com"

retryConfig:
  maxRetries: 5
  firstRetryGapInMinutes: 5
  secondRetryGapInMinutes: 15
  thirdRetryGapInMinutes: 60
  fourthRetryGapInMinutes: 240
  lastRetryGapInDays: 1
```

#### DynamoDB Provisioned Throughput
- Read Capacity Units (RCU): 5 (configurable)
- Write Capacity Units (WCU): 5 (configurable)
- Auto-scaling enabled in production

### Model-Level Configuration

NA

### Stack-Level Configuration

NA

### Professional Services/System Integrator Configuration

NA

---

## Auditing/Logging

### Event Types Published to SNS
- `START_WORKFLOW`: BL processing begins
- `CLOSE_WORKFLOW`: BL processing completes (success/failure)

### Workflow Token Metadata
- `blNumber` - Bill of Lading number
- `bookingNumber` - Associated booking
- `blId` - DynamoDB ID
- `attemptCount` - Retry attempt number
- `nextRetryDate` - Scheduled retry time

### Lifecycle Events
- `configureLifecycle()`: Register `WebBLAppLifecycleListener`, configure ObjectMapper
- `startListener()`: Start SQS listeners (ZIP/PDF), DB listeners (Oracle/MySQL)

---

## Metrics and Statistics

NA

---

## Installer Changes

NA

---

## Impact on Current Application

NA

---

## Resiliency

### Error Handling

1. **PDF Processing Errors**
   - `BLNumberNotFound` — Cannot parse BL from filename → retry table
   - `CarrierNotFound` — SCAC code not resolved → retry table
   - `BillOfLadingNotFound` — BL not in Elasticsearch → retry with backoff
   - Max 5 retries over configurable time periods

2. **SQS Message Processing**
   - Messages acknowledged (deleted) after processing regardless of outcome
   - Failed messages logged and routed to retry mechanism via MySQL

3. **S3 Operations**
   - Non-retryable errors wrapped in `UnrecoverableAWSException`

### Retry Schedule (configurable)
- 1st retry: `firstRetryGapInMinutes`
- 2nd retry: `secondRetryGapInMinutes`
- 3rd retry: `thirdRetryGapInMinutes`
- 4th retry: `fourthRetryGapInMinutes`
- 5th retry: `lastRetryGapInDays`

---

## Temporary object cleanup, temporary files cleanup

NA

---

## Impact on Tools

NA

---

## Impact on Other Components

NA

---

## Backwards Compatible

This uses `cloud-sdk-api` and `cloud-sdk-aws` version **1.0.22-SNAPSHOT** which integrate AWS SDK 2.x through abstraction interfaces (`StorageClient`, `MessagingClient`, `NotificationService`, `DatabaseRepository`, `EmailService`).

The `commons` dependency remains at version **1.R.01.021** to maintain compatibility with `com.inttra.mercury.messaging` packages. Only cloud-sdk dependencies use the SNAPSHOT version.

---

## New/Upgraded Third party Applications/Jars

| Library | Old Version | New Version | Purpose |
|---------|-------------|-------------|---------|
| cloud-sdk-api | N/A (new) | 1.0.22-SNAPSHOT | AWS service abstractions |
| cloud-sdk-aws | N/A (new) | 1.0.22-SNAPSHOT | AWS SDK 2.x implementations |
| dynamo-integration-test | N/A (new) | 1.0.22-SNAPSHOT | DynamoDB integration test support (DynamoDB Local) |
| dynamo-client | 1.R.01.021 | Removed | Replaced by cloud-sdk DynamoDB |
| email-sender | 1.R.01.021 | Removed | Replaced by cloud-sdk EmailService |
| AWS SDK | 1.x (transitive via commons) | 2.x (via cloud-sdk-aws) | AWS service integration |
| Dropwizard | 4.0.x | 4.0.x (unchanged) | Application framework |
| Google Guice | - | - (unchanged) | Dependency injection |
| JUnit Jupiter | 6.1.0-M1 | 6.1.0-M1 (unchanged) | Unit testing |
| Mockito | 5.20.0 | 5.20.0 (unchanged) | Mocking framework |
| AssertJ | 4.0.0-M1 | 4.0.0-M1 (unchanged) | Assertion library |

---

## Unit Test Plan

### Test Summary

| Category | Test Count | Description |
|----------|------------|-------------|
| Unit Tests | 308 | All core logic, DAO, messaging, storage, email, DynamoDB, and configuration tests |
| Integration Tests | 19 | DynamoDB integration tests using DynamoDB Local (via `dynamo-integration-test`) |

### Unit Tests (308 total)

#### Configuration Tests
- **WebBLInjectorTest**: 5 tests — Verifies Guice bindings for all components
- **WebBLDynamoModuleTest**: 3 tests — Constructor null validation for config & environment
- **WebBLMessagingModuleTest**: 4 tests — Constructor null validation, SNS topic ARN blank/null validation
- **WebBLStorageModuleTest**: 2 tests — Constructor null validation for config

#### DAO Tests
- **BLDaoTest**: 2 tests — Load query via DefaultQuerySpec and repository access

#### DynamoDB Admin Tests
- **CreateTablesTest**: 6 tests — Entity class initialization (BLVersion), resolveClientConfig null validation, config retrieval

#### Email Tests
- **WebBLEmailModuleTest**: 3 tests — Module creation, source email delegation to config

#### Messaging Tests
- **SNSClientTest**: Tests for NotificationService publish
- **SQSClientTest**: 4 tests — Send, delete, receive operations with MessagingClient<String>
- **SQSListenerTest**: 6 tests — Poll/execute, shutdown, QueueMessage<String> processing

#### Storage Tests
- **S3WorkspaceServiceTest**: 12 tests — Upload, download, exists, delete operations with StorageClient

#### Inbound Processing Tests
- **WebBLZipInboundProcessorTaskTest**: Tests for ZIP message processing with QueueMessage<String>
- **WebBLPDFInboundProcessorTaskTest**: Tests for PDF message processing with QueueMessage<String>
- **WebBLArchiveTaskTest**: Tests for S3 archive operations with StorageClient

#### Other Tests
- Multiple test classes for business logic, REST API, outbound processing, Elasticsearch, and email

### DynamoDB Integration Tests (19 total)

Uses `BaseDynamoDbIT` from `dynamo-integration-test` (mercury-services-commons) with embedded DynamoDB Local.

- **BLDaoIT**: 9 tests — BLDao CRUD operations, TTL, GSI queries, field mapping, repository access
- **CreateTablesIT**: 10 tests — Table creation, partition/sort keys, GSI validation, TTL configuration, idempotent creation

### Test Execution Commands

```bash
# Run All Tests (unit + integration)
mvn clean verify -pl webbl -am

# Run Unit Tests Only
mvn test -pl webbl

# Run Specific Test Class
mvn test -pl webbl -Dtest=BLDaoTest
mvn test -pl webbl -Dtest=SQSClientTest
mvn test -pl webbl -Dtest=WebBLInjectorTest
mvn test -pl webbl -Dtest=WebBLDynamoModuleTest
mvn test -pl webbl -Dtest=CreateTablesTest

# Run Integration Tests Only
mvn verify -pl webbl -Dtest=none -DfailIfNoTests=false -Dit.test=BLDaoIT
mvn verify -pl webbl -Dtest=none -DfailIfNoTests=false -Dit.test=CreateTablesIT
```

### QA Note

All unit tests pass with `mvn verify -pl webbl -am`. DynamoDB integration tests use embedded DynamoDB Local
(via `dynamo-integration-test`), requiring no external infrastructure. Integration tests are marked with
`@Category(IntegrationTests.class)` and run during the `verify` phase.

---

## Pre-Dev Security

| TOPIC | Valid (Y/N) | Comments |
|-------|-------------|----------|
| New UI pages/data exposed to users | N | No UI components |
| Use of new services/ports | N | Uses existing SQS, SNS, S3, DynamoDB services |
| Authentication changes | N | No authentication changes |
| New/changed encryption | N | Uses existing AWS encryption |
| Changes in the way data is transmitted | N | Standard AWS SDK 2.x communication (same protocols) |
| Changes in the way/location data is being stored | N | DynamoDB storage unchanged; same table, same attributes |
| New API implementation / change of existing APIs | N | No new external APIs |
| New / Change in existing file upload functionality | N | No file upload functionality changes |
| New / Change in integration within e2open or third party apps | N | Same AWS services, upgraded SDK version |
| New / Existing UI functionality support querying | N | No UI functionality |

---

## REQUIRED: Documentation Changes

| Question | Answer |
|----------|--------|
| Do end users interact with this feature? | No |
| Do project teams/SIs/BIT teams need to enable or configure this feature? | Yes (DynamoDB config uses `BaseDynamoDbConfig`) |
| Does the feature require special migration from prior releases? | No |
| What guides or content sections need updating? | NA |

---

## Blocking Issues and Actions from the Design Review

NA

---

## Review

| Stage | Reviewer | Status | Notes |
|-------|----------|--------|-------|
| Design | Arijit Kundu | Approved | |
| Product Owner | | | |
| Pre Dev Security | | | |
| Pre Dev Architecture | Arijit Kundu | Approved | |
| Browser | NA | | |
| UX | NA | | |
| Post Dev Security | | | |
| Post Dev Architecture | NA | | |
| QA | | | |

---

## Deployment

### Build Artifacts

```bash
# Build Uber JAR
mvn clean package -pl webbl -am
# Output: webbl/target/webbl-1.0.jar
```

### Environment Configuration

**AWS Credentials** (in order of preference):
- EC2 Instance Profile (recommended for EC2/ECS)
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Shared credentials file: `~/.aws/credentials`

### Command-Line Interface

```bash
# Start server
java -jar webbl/target/webbl-1.0.jar server webbl/conf/int/config.yaml

# Check configuration
java -jar webbl/target/webbl-1.0.jar check webbl/conf/int/config.yaml
```

---

## References

### External Documentation
- [AWS SDK for Java v2](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/)
- [DynamoDB Enhanced Client](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/dynamodb-enhanced-client.html)
- [Dropwizard Documentation](https://www.dropwizard.io/en/stable/)
- [Google Guice User Guide](https://github.com/google/guice/wiki)

### Internal Documentation
- cloud-sdk-api Javadoc
- cloud-sdk-aws Javadoc
- booking-bridge DESIGN.md (reference implementation)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-07-18 | Initial design document — AWS SDK 1.x → 2.x migration via cloud-sdk |
