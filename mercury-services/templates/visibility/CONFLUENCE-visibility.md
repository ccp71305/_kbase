# Visibility Service - Design Document (AWS SDK 2.x Migration)

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

The **Visibility Service** is a Mercury platform multi-module microservice responsible for processing container tracking and shipment visibility events. It ingests container status events (milestones like gate-in, gate-out, vessel departure, vessel arrival, etc.) from multiple sources — EDI feeds, Watermill/Shippeo premium providers, and ITV GPS feeds — matches them against booking/shipping instruction data in Elasticsearch, and delivers outbound status notifications to subscribers in GIS/EDI formats.

The module consists of **11 sub-modules**:
- **6 Dropwizard Services** (long-running, deployed as Docker containers): `visibility-inbound`, `visibility-matcher`, `visibility-outbound`, `visibility-pending`, `visibility-wm-inbound-processor`, `visibility-itv-gps-processor`
- **4 AWS Lambda Functions** (event-driven, deployed as ZIP packages): `visibility-s3-archiver`, `visibility-error-email`, `visibility-pending-start`, `visibility-outbound-poller`
- **1 Shared Library**: `visibility-commons`

This document covers the AWS SDK 1.x → 2.x migration via `cloud-sdk-api` and `cloud-sdk-aws` libraries, following the same patterns established in the `webbl`, `booking-bridge`, `booking`, `network`, `auth`, `registration`, `tx-tracking`, `self-service-reports`, and `db-migration` modules.

### Key Responsibilities
- **Message Consumption**: Listens to SQS queues for incoming container events (EDI, Watermill, GPS)
- **Event Processing**: Validates, enriches, and persists container events to DynamoDB
- **Event Matching**: Matches container events to bookings/shipping instructions via Elasticsearch
- **Outbound Generation**: Generates GIS/EDI outbound files for subscribers uploaded to S3
- **Pending Retry**: Retries matching for unmatched events on a schedule
- **Archival**: Archives container events to S3 for long-term storage
- **Error Reporting**: Sends automated error report emails to subscribers
- **REST APIs**: Exposes container tracking search and event submission endpoints

### Technology Stack
- **Framework**: Dropwizard 4.0.x
- **Dependency Injection**: Google Guice
- **AWS SDK**: Version 2 (via cloud-sdk-aws 1.0.22-SNAPSHOT)
- **Messaging**: SQS, SNS (via cloud-sdk-api)
- **Storage**: S3 (via cloud-sdk-api StorageClient)
- **Email**: SES (via cloud-sdk-api EmailService)
- **Database**: DynamoDB (via cloud-sdk-api Enhanced Client), MySQL (via MyBatis), Oracle (via MyBatis)
- **Search**: Elasticsearch 6.8.13 (via REST high-level client)
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

### Assumptions
- The `cloud-sdk-api` and `cloud-sdk-aws` libraries (version `1.0.22-SNAPSHOT`) provide full coverage for all AWS service operations required by the visibility module
- The booking module's AWS 2.x upgrade commit (`74f36e7a71` from branch `feature/ION-14382-bk3-aws-upgrade-2`) is cherry-picked onto the visibility feature branch to provide upgraded booking models during development. This commit only touches `booking/` files (223 files, zero overlap with other modules)
- When the booking PR merges to `develop`, a `git rebase -i develop` with drop of the cherry-picked commit will produce a clean visibility-only PR
- DynamoDB Local (embedded, no Docker) via `dynamo-integration-test` is sufficient for integration testing of all 4 DynamoDB table operations
- Nested model objects previously annotated with `@DynamoDBDocument` (SDK 1.x) can be fully serialized/deserialized via Jackson JSON through `@DynamoDbConvertedBy` `AttributeConverter` implementations

### Open Issues
- **Booking dependency version**: `com.inttra.mercury:booking:2.1.8.M` compiled against the cherry-picked booking commit. Final version number will be set once the booking PR merges to `develop` and a release version is published
- **BookingDetailVisibility model**: Needs alignment with the booking module's migrated `BookingDetail` entity annotations

### Branch Strategy

The visibility feature branch uses a **cherry-pick + rebase-drop** workflow to unblock development while the booking PR is pending:

1. **Create branch**: `git checkout -b feature/visibility-aws-sdk-2x-upgrade` from latest `develop`
2. **Cherry-pick booking commit**: `git cherry-pick 74f36e7a71` — this single commit (from `feature/ION-14382-bk3-aws-upgrade-2`) provides the upgraded booking models with cloud-sdk annotations. It changes **223 files exclusively in `booking/`** with zero overlap to any other module, so the cherry-pick is conflict-free.
3. **Do visibility work**: All upgrade phases (POM changes, commons, services, lambdas, booking alignment) on top as separate commits
4. **When booking merges to develop**: `git rebase -i develop` and **drop** the cherry-picked booking commit (it's now in develop). Force push with `--force-with-lease`. The PR will show only visibility changes.
5. **If visibility finishes before booking merges**: Open a **draft PR** (it will include the booking diff in `booking/` only), or temporarily set the PR base branch to `feature/ION-14382-bk3-aws-upgrade-2` to see only the visibility diff.

**Key facts (verified 2026-03-30)**:
- Booking commit `74f36e7a71` only touches `booking/` files — zero visibility, db-migration, or network files
- `develop` is 11 commits ahead of the booking branch base with zero file overlap to the booking commit
- Cherry-pick and subsequent rebase-drop are guaranteed conflict-free

---

## High Level Design

### Architecture Overview

The visibility service is a multi-module Dropwizard application suite with supporting Lambda functions. All AWS service interactions are abstracted through the cloud-sdk layer:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           Visibility Service Suite                                │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        INBOUND SERVICES                                     │ │
│  │                                                                             │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │ │
│  │  │  visibility-     │  │  visibility-wm-  │  │  visibility-itv- │          │ │
│  │  │  inbound         │  │  inbound-proc    │  │  gps-processor   │          │ │
│  │  │  (EDI + REST)    │  │  (Watermill)     │  │  (GPS Events)    │          │ │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │ │
│  │           │                      │                      │                    │ │
│  │           └──────────────────────┼──────────────────────┘                    │ │
│  └──────────────────────────────────┼──────────────────────────────────────────┘ │
│                                     │                                            │
│                                     ▼                                            │
│                         ┌───────────────────────┐                                │
│                         │   DynamoDB             │                                │
│                         │   container_events     │                                │
│                         │  (DynamoDB Streams)    │                                │
│                         └──────────┬────────────┘                                │
│                                    │                                             │
│                        ┌───────────┼──────────┐                                  │
│                        ▼                      ▼                                  │
│            ┌──────────────────┐   ┌──────────────────┐                          │
│            │ visibility-      │   │ visibility-       │                          │
│            │ matcher          │   │ s3-archiver       │                          │
│            │ (Match→Outbound) │   │ (Lambda: Archive) │                          │
│            └────────┬─────────┘   └──────────────────┘                          │
│                     │                                                            │
│            ┌────────┼────────┐                                                   │
│            ▼                 ▼                                                   │
│    ┌──────────────┐  ┌──────────────┐                                           │
│    │ visibility-  │  │ visibility-  │                                           │
│    │ outbound     │  │ pending      │                                           │
│    │ (GIS/EDI)    │  │ (Retry)      │                                           │
│    └──────────────┘  └──────────────┘                                           │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                     LAMBDA FUNCTIONS                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │ │
│  │  │ error-email  │  │ pending-     │  │ outbound-    │                      │ │
│  │  │ (Send emails)│  │ start        │  │ poller       │                      │ │
│  │  └──────────────┘  │ (Trigger)    │  │ (Poll MySQL) │                      │ │
│  │                     └──────────────┘  └──────────────┘                      │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Cloud SDK Integration Architecture

All AWS service integrations are abstracted via the cloud-sdk layer:

```
Visibility Service
      │
      ├─▶ cloud-sdk-api (Vendor-Neutral Interfaces)
      │     ├─▶ MessagingClient<T>        — SQS operations
      │     ├─▶ QueueMessage<T>           — Immutable message wrapper
      │     ├─▶ ReceiveMessageOptions     — Builder for receive config
      │     ├─▶ NotificationService       — SNS publish
      │     ├─▶ StorageClient             — S3 read/write
      │     ├─▶ StorageObject             — S3 object with content stream
      │     ├─▶ DatabaseRepository<T, ID> — DynamoDB CRUD + query
      │     ├─▶ DefaultCompositeKey<P,S>  — Composite key (PK + SK)
      │     ├─▶ DefaultPartitionKey<P>    — Simple partition key
      │     ├─▶ DynamoDbClientConfig      — DynamoDB client configuration
      │     └─▶ EmailService              — SES v2 email sending
      │
      └─▶ cloud-sdk-aws (AWS SDK v2 Implementations)
            ├─▶ SqsMessagingClient            — SQS via SqsClient
            ├─▶ SnsNotificationService        — SNS via SnsClient
            ├─▶ S3StorageClient               — S3 via S3Client
            ├─▶ EnhancedDynamoRepository      — DynamoDB Enhanced Client
            ├─▶ SesEmailServiceImpl           — SES via SesV2Client
            └─▶ Factories: MessagingClientFactory, NotificationClientFactory,
                           StorageClientFactory, DynamoRepositoryFactory,
                           EmailClientFactory
```

### Summary of Changes per Service Area

| Area | Pre-Migration (SDK 1.x) | Post-Migration (SDK 2.x) | Key Changes |
|------|------------------------|--------------------------|-------------|
| **DynamoDB** | `DynamoDBMapper` + `@DynamoDBTable` / `@DynamoDBDocument` via `dynamo-client` | `DynamoDbEnhancedClient` + `@DynamoDbBean` + `@DynamoDbConvertedBy` via cloud-sdk `DatabaseRepository` | Removed `@DynamoDBDocument` from ~20 nested models; created ~11 `AttributeConverter` implementations; migrated 6 DAO classes (5 in visibility-commons + 1 CargoVisibilitySubscriptionDao in visibility-wm-inbound-processor) |
| **SQS** | AWS SDK 1.x `AmazonSQS` + `Message` via custom `SqsMessageHandler` | cloud-sdk `MessagingClient<String>` + `QueueMessage<String>` | Immutable `QueueMessage<String>`, `getPayload()` replaces `getBody()` |
| **SNS** | Custom `SNSClient` wrapper (SDK 1.x) | cloud-sdk `NotificationService` | `publish(topicArn, content)` replaces direct SNS client calls |
| **S3** | AWS SDK 1.x `AmazonS3` / `AmazonS3ClientBuilder` | cloud-sdk `StorageClient` | `StorageObject` wrapper, `getContent()` returns `InputStream` |
| **SES (Email)** | AWS SDK 2.x `SesClient` directly (inbound only) | cloud-sdk `EmailService` (SDK 2.x `SesV2Client`) | New `VisibilityEmailModule`; template-based email via cloud-sdk |
| **SSM** | AWS SDK 1.x `AWSSimpleSystemsManagement` (lambdas) | AWS SDK 2.x `SsmClient` or cloud-sdk paramstore API | Updated client construction in Lambda functions |
| **Lambda Events** | `aws-lambda-java-events` with SDK 1.x DynamoDB models | `aws-lambda-java-events` 3.16.1 (embedded DynamoDB event models) | Import path change for `AttributeValue`, `OperationType` |

### Data Flow Pipeline (Post-Migration)

```
                INBOUND FLOW                            MATCHING FLOW
                ──────────                              ─────────────

  SQS Queue (EDI/WM/GPS)
         │
         ▼
  SQSClient.receiveMessage()                              DynamoDB Stream (INSERT)
  → List<QueueMessage<String>>                               │ via SNS → SQS
         │                                                    ▼
         ▼                                          MatchingProcessor.process(QueueMessage<String>)
  Processor.process(QueueMessage<String>)                     │
         │                                               ┌────┴────┐
         ├─▶ message.getPayload()                        │         │
         ├─▶ StorageClient.getObject() → S3 content    Matched   Not Matched
         ├─▶ Validate & enrich                           │         │
         └─▶ ContainerEventDao.save() → DynamoDB         ▼         ▼
                                                    SQS Outbound  DynamoDB Pending


                OUTBOUND FLOW                            LAMBDA FLOWS
                ─────────────                            ────────────

  SQS Outbound Queue
         │                                           S3 Archiver:
         ▼                                             DynamoDB Stream MODIFY → Archive to S3
  Outbound*Processor.process(QueueMessage<String>)
         │                                           Pending Start:
         ├─▶ ContainerEventOutboundDao.save()          CloudWatch → MessagingClient.sendMessage()
         ├─▶ Generate GIS/EDI file
         └─▶ StorageClient.putObject() → S3          Outbound Poller:
                                                       CloudWatch → MySQL → MessagingClient.sendMessage()

                                                     Error Email:
                                                       CloudWatch → EmailService → SES
```

---

## Low Level Design

### Server

Following are the key changes:

#### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| VisibilityApplicationConfig | `visibility-commons/.../config.VisibilityApplicationConfig` | Base configuration with `BaseDynamoDbConfig` |
| VisibilityApplicationInjector | `visibility-commons/.../config.VisibilityApplicationInjector` | Core Guice module: installs DynamoDB, Messaging, Storage modules |
| VisibilityDynamoModule | `visibility-commons/.../config.VisibilityDynamoModule` | Guice module: DynamoDbClientConfig, 5 DAOs via DynamoRepositoryFactory |
| VisibilityMessagingModule | `visibility-commons/.../config.VisibilityMessagingModule` | Guice module: MessagingClient (SQS), NotificationService (SNS) |
| VisibilityStorageModule | `visibility-commons/.../config.VisibilityStorageModule` | Guice module: StorageClient for S3 |
| SQSClient | `visibility-commons/.../messaging.SQSClient` | SQS operations via MessagingClient<String> |
| SNSClient | `visibility-commons/.../messaging.SNSClient` | SNS publishing via NotificationService |
| S3WorkspaceService | `visibility-commons/.../service.S3WorkspaceService` | S3 file operations via StorageClient |
| ContainerEventDao | `visibility-commons/.../persistence.ContainerEventDao` | DynamoDB DAO wrapping DatabaseRepository |
| ContainerEventOutboundDao | `visibility-commons/.../persistence.ContainerEventOutboundDao` | DynamoDB DAO wrapping DatabaseRepository |
| ContainerEventPendingDao | `visibility-commons/.../persistence.ContainerEventPendingDao` | DynamoDB DAO wrapping DatabaseRepository |
| ContainerTrackingEventDao | `visibility-commons/.../persistence.ContainerTrackingEventDao` | DynamoDB DAO wrapping DatabaseRepository |
| ContainerEvent | `visibility-commons/.../model.containerEvent.ContainerEvent` | DynamoDB entity with SDK 2.x Enhanced Client annotations |
| VisibilityDynamoDbAdminCommand | `visibility-inbound/.../config.VisibilityDynamoDbAdminCommand` | Dropwizard command for DynamoDB table creation/management |

#### Guice Module Loading Order

1. **VisibilityApplicationInjector** (Core bindings)
   - Installs `VisibilityDynamoModule`, `VisibilityMessagingModule`, `VisibilityStorageModule`
   - Binds network service clients (Auth, Geography, Subscription, etc.)
   - Binds `SQSClient`, `SNSClient` wrappers
   - Provides `SqsMessageHandler` with cloud-sdk `MessagingClient`

2. **VisibilityDynamoModule** (DynamoDB — 4 tables)
   - Provides `DynamoDbClientConfig` from `BaseDynamoDbConfig.toClientConfigBuilder()`
   - Creates repositories via `DynamoRepositoryFactory.createEnhancedRepository()`
   - Provides 5 DAOs: `ContainerEventDao`, `ContainerEventOutboundDao`, `ContainerEventPendingDao`, `ContainerTrackingEventDao`, `BookingDao`
   - **Note**: `CargoVisibilitySubscriptionDao` (6th DAO) is provided by the `visibility-wm-inbound-processor` Guice module, not by `VisibilityDynamoModule`, since the `CargoVisibilitySubscription` model class resides in that sub-module. The DynamoDB client config is shared.

3. **VisibilityMessagingModule** (SQS + SNS)
   - Provides `MessagingClient<String>` via `MessagingClientFactory.createDefaultStringClient()`
   - Provides `NotificationService` via `NotificationClientFactory.createDefaultClient(topicArn)`
   - Provides `EventPublisher` via lambda wrapping `SNSClient`

4. **VisibilityStorageModule** (S3)
   - Provides `StorageClient` via `StorageClientFactory.createDefaultS3Client()`

5. Sub-module-specific injectors (per Dropwizard service) install the above shared modules plus their own bindings.

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
Table: {prefix}_container_events
  Partition Key: id (String, prefix "CE_")
  GSIs:
    - bkInttraReferenceNumber-equipmentIdentifier-index (PK: bkInttraReferenceNumber, SK: equipmentIdentifier)
    - bookingNumber-index (PK: bookingNumber)
    - siInttraReferenceNumber-index (PK: siInttraReferenceNumber)
    - equipmentIdentifier-index (PK: equipmentIdentifier)
    - blNumber-index (PK: blNumber)
  TTL Attribute: expiresOn (400 days)
  Nested Beans: ContainerEventSubmission, ContainerEventEnrichedProperties, GISOutboundDetails, MetaData (serialized as JSON via AttributeConverter)

Table: {prefix}_container_events_outbound
  Partition Key: integrationProfileFormatId (String)
  Sort Key: sequenceNumber (String: "{timestamp}_{ceId}")
  TTL Attribute: expiresOn (3 years)

Table: {prefix}_container_events_pending
  Partition Key: createDate (String: "yyyy-MM-dd")
  Sort Key: inboundContainerEventId (String)
  TTL Attribute: expiresOn (40 days)

Table: {prefix}_CargoVisibilitySubscription
  Partition Key: id (String)
  GSIs:
    - bookingNumber-index (PK: bookingNumber)
    - subscriptionReference-index (PK: subscriptionReference)
  TTL Attribute: expiresOn (epoch seconds)
  Nested Beans: Reference, TransportLeg (serialized natively by DynamoDB Enhanced Client as List<Map>; Reference contains ReferenceType enum, TransportLeg contains Location→LocationDate nested hierarchy with multiple enum fields)
  Note: This table is also accessed by watermill-publisher module (separate upgrade scope) which has additional GSIs (bookingNumber-carrierScac-index, billOfLading-carrierScac-index) and a range key on carrierScac
  Location: visibility-wm-inbound-processor (NOT in visibility-commons)
```

#### DynamoDB Annotation Mapping (SDK 1.x → 2.x)

| SDK 1.x Annotation | SDK 2.x / cloud-sdk Annotation |
|---------------------|-------------------------------|
| `@DynamoDBTable(tableName = "...")` | `@DynamoDbBean` + `@Table(name = "...")` |
| `@DynamoDBHashKey` | `@DynamoDbPartitionKey` |
| `@DynamoDBRangeKey` | `@DynamoDbSortKey` |
| `@DynamoDBIndexHashKey(globalSecondaryIndexName = "...")` | `@DynamoDbSecondaryPartitionKey(indexNames = {"..."})` |
| `@DynamoDBTypeConverted(converter = X.class)` | `@DynamoDbConvertedBy(XAttributeConverter.class)` |
| `@DynamoDBDocument` | *(removed — nested objects serialized via AttributeConverter)* |
| `@DynamoDBTypeConvertedEnum` | *(removed — Enhanced Client handles enums as strings by default)* |

#### Component Interaction Flow

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 EXTERNAL SYSTEMS                                                  │
│                                                                                                  │
│   EDI Feeds ───▶ SQS (ce-validate)                                                              │
│   Watermill  ───▶ SQS (wm-events)                                                               │
│   ITV/GPS    ───▶ SQS (gps-events)                                                              │
│   REST API   ───▶ visibility-inbound (Dropwizard REST)                                           │
└──────────────┬───────────────┬──────────────┬────────────────────────────────────────────────────┘
               │               │              │
               ▼               ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              INBOUND LAYER                                                        │
│                                                                                                  │
│  ┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐                 │
│  │ visibility-inbound   │  │ visibility-wm-inbound │  │ visibility-itv-gps     │                 │
│  │ InboundEdiProcessor  │  │ CargoVisibility       │  │ GPSEventProcessor      │                 │
│  │ (256 lines)          │  │ EventProcessor        │  │ (168 lines)            │                 │
│  │                      │  │ (289 lines)           │  │                        │                 │
│  │ SQS → Parse →        │  │ SQS → Parse →         │  │ SQS → Parse →          │                 │
│  │ Validate → Enrich →  │  │ Validate → Enrich →   │  │ Validate → Enrich →    │                 │
│  │ ContainerEventDao    │  │ ContainerEventDao      │  │ ContainerEventDao      │                 │
│  │   .save()            │  │   .save()              │  │   .save()              │                 │
│  └──────────┬───────────┘  └───────────┬────────────┘  └───────────┬────────────┘                │
└─────────────┼──────────────────────────┼───────────────────────────┼─────────────────────────────┘
              │                          │                           │
              └──────────────────────────┼───────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           DynamoDB: container_events                                              │
│                                                                                                  │
│   INSERT triggers DynamoDB Stream → SNS → SQS (matcher queue)                                    │
│   MODIFY triggers DynamoDB Stream → visibility-s3-archiver (Lambda)                              │
│                                    → Archive to S3                                               │
└──────────────────────────┬─────────────────────────────┬────────────────────────────────────────┘
                           │                             │
                           ▼                             ▼
┌──────────────────────────────────────────┐  ┌──────────────────────────────────────────────────┐
│     MATCHING LAYER                        │  │     LAMBDA LAYER                                  │
│                                          │  │                                                    │
│  ┌────────────────────────┐              │  │  ┌───────────────────────────┐                     │
│  │ visibility-matcher     │              │  │  │ visibility-s3-archiver    │                     │
│  │ MatchingProcessor      │              │  │  │ VisibilityS3Archiver      │                     │
│  │ (195 lines)            │              │  │  │ (206 lines)               │                     │
│  │                        │              │  │  │ DynamoDB Stream MODIFY →  │                     │
│  │ SQS → ContainerEvent → │              │  │  │ StorageClient.putObject() │                     │
│  │ ES lookup (booking/SI) │              │  │  └───────────────────────────┘                     │
│  │                        │              │  │                                                    │
│  │    ┌────────┬──────┐   │              │  │  ┌───────────────────────────┐                     │
│  │    │Matched │ Not  │   │              │  │  │ visibility-error-email    │                     │
│  │    │        │Matched│  │              │  │  │ VisibilityErrorEmail      │                     │
│  │    ▼        ▼       │  │              │  │  │ (65 lines)               │                     │
│  │ SQS     DynamoDB    │  │              │  │  │ CloudWatch → EmailService │                     │
│  │ Outbound Pending    │  │              │  │  └───────────────────────────┘                     │
│  └────────────────────────┘              │  │                                                    │
└──────────────────────────────────────────┘  │  ┌───────────────────────────┐                     │
                           │                  │  │ visibility-pending-start  │                     │
              ┌────────────┼──────────┐       │  │ VisibilityPendingStart    │                     │
              ▼            ▼          │       │  │ (59 lines)               │                     │
┌─────────────────────┐ ┌─────────────┴───┐  │  │ CloudWatch →              │                     │
│ visibility-outbound │ │ visibility-     │  │  │ MessagingClient           │                     │
│ OutboundSingle      │ │ pending         │  │  │   .sendMessage()          │                     │
│ Transaction (203)   │ │ PendingSqs      │  │  └───────────────────────────┘                     │
│ OutboundMulti       │ │ Processor       │  │                                                    │
│ Transaction (176)   │ │ (211 lines)     │  │  ┌───────────────────────────┐                     │
│                     │ │                 │  │  │ visibility-outbound-poller│                     │
│ SQS → Generate     │ │ DynamoDB →      │  │  │ VisibilityOutboundPoller  │                     │
│ GIS/EDI file →     │ │ Re-match via    │  │  │ (166 lines)              │                     │
│ StorageClient      │ │ ES → promote    │  │  │ CloudWatch → MySQL →      │                     │
│ .putObject() → S3  │ │ to outbound     │  │  │ MessagingClient           │                     │
└─────────────────────┘ └─────────────────┘  │  │   .sendMessage()          │                     │
                                             │  └───────────────────────────┘                     │
                                             └────────────────────────────────────────────────────┘
```

#### Key Components (Detailed)

| Component | Location | Lines | Purpose |
|-----------|----------|-------|---------|
| **Commons — Configuration** | | | |
| VisibilityApplicationConfig | `visibility-commons/.../config.VisibilityApplicationConfig` | 51 | Base configuration with `BaseDynamoDbConfig`, SQS configs, ES config |
| VisibilityApplicationInjector | `visibility-commons/.../config.VisibilityApplicationInjector` | 73 | Core Guice module: installs DynamoDB, Messaging, Storage modules |
| **Commons — Messaging** | | | |
| SqsMessageHandler | `visibility-commons/.../processor.sqs.SqsMessageHandler` | 164 | SQS polling loop, message acknowledgement, DLQ routing |
| StatusEventProcessorManagedHandler | `visibility-commons/.../processor.StatusEventProcessorManagedHandler` | — | Dropwizard managed lifecycle for SQS processor start/stop |
| **Commons — Persistence (DAOs)** | | | |
| ContainerEventDao | `visibility-commons/.../persistence.ContainerEventDao` | 156 | DynamoDB DAO: CRUD + 5 GSI queries for `container_events` |
| ContainerEventOutboundDao | `visibility-commons/.../persistence.ContainerEventOutboundDao` | 132 | DynamoDB DAO: composite key CRUD for `container_events_outbound` |
| ContainerEventPendingDao | `visibility-commons/.../persistence.ContainerEventPendingDao` | 75 | DynamoDB DAO: composite key CRUD for `container_events_pending` |
| ContainerTrackingEventDao | `visibility-commons/.../persistence.ContainerTrackingEventDao` | 56 | DynamoDB DAO: CRUD for `container_tracking_events` |
| BookingDao | `visibility-commons/.../booking.BookingDao` | 122 | DynamoDB DAO: booking lookup for matching |
| **Commons — Storage** | | | |
| S3WorkspaceService | `visibility-commons/.../service.S3WorkspaceService` | 77 | S3 file read/write operations via `StorageClient` |
| **Commons — DynamoDB Entities** | | | |
| ContainerEvent | `visibility-commons/.../model.containerEvent.ContainerEvent` | 105 | Primary DynamoDB entity with 5 GSIs, TTL, nested beans |
| ContainerEventOutbound | `visibility-commons/.../model.containerEvent.ContainerEventOutbound` | 81 | Outbound DynamoDB entity with composite key (IPF ID + sequence) |
| ContainerEventPending | `visibility-commons/.../model.containerEvent.ContainerEventPending` | 68 | Pending retry DynamoDB entity with composite key (date + CE ID) |
| ContainerTrackingEvent | `visibility-commons/.../model.ContainerTrackingEvent` | 64 | Container tracking event entity |
| BookingDetailVisibility | `visibility-commons/.../booking.BookingDetailVisibility` | 11 | Booking entity interface for visibility module (SDK 2.x aligned) |
| **Inbound Service** | | | |
| VisibilityInboundApplication | `visibility-inbound/.../VisibilityInboundApplication` | 117 | Dropwizard app entry point: Guice modules, commands, resources |
| InboundEdiProcessor | `visibility-inbound/.../processor.InboundEdiProcessor` | 256 | EDI message processor: parse → validate → enrich → persist |
| ElasticSearchClientModule | `visibility-inbound/.../config.ElasticSearchClientModule` | — | Guice module for Elasticsearch client setup |
| **Matcher Service** | | | |
| VisibilityMatcherApplication | `visibility-matcher/.../VisibilityMatcherApplication` | 54 | Dropwizard app entry point |
| MatchingProcessor | `visibility-matcher/.../processor.MatchingProcessor` | 195 | Match container events to bookings/SIs via Elasticsearch |
| **Outbound Service** | | | |
| VisibilityOutboundApplication | `visibility-outbound/.../VisibilityOutboundApplication` | 83 | Dropwizard app entry point |
| OutboundSingleTransactionProcessor | `visibility-outbound/.../processor.OutboundSingleTransactionProcessor` | 203 | Generate single-transaction GIS/EDI files → S3 |
| OutboundMultiTransactionProcessor | `visibility-outbound/.../processor.OutboundMultiTransactionProcessor` | 176 | Generate multi-transaction GIS/EDI files → S3 |
| **Pending Service** | | | |
| VisibilityPendingApplication | `visibility-pending/.../VisibilityPendingApplication` | 54 | Dropwizard app entry point |
| PendingSqsProcessor | `visibility-pending/.../processor.PendingSqsProcessor` | 211 | Retry unmatched events: DynamoDB → ES lookup → promote to outbound |
| **Watermill Inbound Service** | | | |
| VisibilityWMEventApplication | `visibility-wm-inbound-processor/.../VisibilityWMEventApplication` | 54 | Dropwizard app entry point |
| CargoVisibilityEventProcessor | `visibility-wm-inbound-processor/.../processor.CargoVisibilityEventProcessor` | 289 | Watermill/Shippeo event processor (largest processor) |
| CargoVisibilitySubscriptionProcessor | `visibility-wm-inbound-processor/.../processor.CargoVisibilitySubscriptionProcessor` | ~90 | Subscription lifecycle management (APPROVED/REJECTED state updates) |
| **Watermill Inbound — DynamoDB (CargoVisibilitySubscription)** | | | |
| CargoVisibilitySubscription | `visibility-wm-inbound-processor/.../cargo.visibility.model.CargoVisibilitySubscription` | ~85 | DynamoDB entity: `CargoVisibilitySubscription` table with 2 GSIs, TTL, nested Reference/TransportLeg beans |
| CargoVisibilitySubscriptionDao | `visibility-wm-inbound-processor/.../wm.dao.CargoVisibilitySubscriptionDao` | ~100 | DynamoDB DAO wrapping `DatabaseRepository<CargoVisibilitySubscription, DefaultPartitionKey<String>>` |
| **GPS Inbound Service** | | | |
| VisibilityGPSEventApplication | `visibility-itv-gps-processor/.../VisibilityGPSEventApplication` | 55 | Dropwizard app entry point |
| GPSEventProcessor | `visibility-itv-gps-processor/.../processor.GPSEventProcessor` | 168 | ITV/GPS event processor |
| **Lambda — S3 Archiver** | | | |
| VisibilityS3Archiver | `visibility-s3-archiver/.../lambda.VisibilityS3Archiver` | 206 | DynamoDB Stream MODIFY → archive to S3 via `StorageClient` |
| **Lambda — Error Email** | | | |
| VisibilityErrorEmail | `visibility-error-email/.../lambda.VisibilityErrorEmail` | 65 | CloudWatch scheduled → send error report emails via `EmailService` |
| VisibilityErrorEmailModule | `visibility-error-email/.../module.VisibilityErrorEmailModule` | — | Guice module for email Lambda (SES, SSM bindings) |
| **Lambda — Pending Start** | | | |
| VisibilityPendingStart | `visibility-pending-start/.../lambda.VisibilityPendingStart` | 59 | CloudWatch scheduled → send SQS trigger to pending service |
| **Lambda — Outbound Poller** | | | |
| VisibilityOutboundPoller | `visibility-outbound-poller/.../lambda.VisibilityOutboundPoller` | 166 | CloudWatch scheduled → MySQL query → SQS messages for outbound |

#### DAO Classes

| DAO | Repository Type | Key Methods |
|-----|----------------|-------------|
| `ContainerEventDao` | `DefaultPartitionKey<String>` | `save`, `findById`, `findByBookingInttraReference` (GSI), `findByBookingNumber` (GSI), `findBySiInttraReference` (GSI), `findByEquipmentIdentifier` (GSI), `findByBlNumber` (GSI), `delete` |
| `ContainerEventOutboundDao` | `DefaultCompositeKey<String, String>` | `save`, `findByIntegrationProfileFormatId` (PK query), `findByIntegrationProfileFormatIdAndSequenceNumber` (composite key), `delete` |
| `ContainerEventPendingDao` | `DefaultCompositeKey<String, String>` | `save`, `findByCreateDate` (PK query), `findByCreateDateAndContainerEventId` (composite key), `delete` |
| `ContainerTrackingEventDao` | `DefaultPartitionKey<String>` | `save`, `findById`, `delete` |
| `BookingDao` | `DefaultCompositeKey<String, String>` | `findByBookingId`, `findByBookingIdAndSequenceNumber` |
| `CargoVisibilitySubscriptionDao` | `DefaultPartitionKey<String>` | `save`, `findById` (PK), `findBySubscriptionReference` (GSI query + full load + sort by modifiedOn desc) |

#### AttributeConverter Implementations

All converters implement `software.amazon.awssdk.enhanced.dynamodb.AttributeConverter<T>`:

| Converter | Type | Serialization Strategy | Location |
|-----------|------|----------------------|----------|
| `ContainerEventSubmissionConverter` | `ContainerEventSubmission` → String | Jackson JSON serialization | `model/containerEvent/converters/` |
| `ContainerEventEnrichedPropertiesConverter` | `ContainerEventEnrichedProperties` → String | Jackson JSON serialization | `model/containerEvent/converters/` |
| `GISOutboundDetailsConverter` | `GISOutboundDetails` → String | Jackson JSON serialization | `model/containerEvent/converters/` |
| `MetaDataConverter` | `MetaData` → String | Jackson JSON serialization | `model/containerEvent/converters/` |
| `SubscriptionConverter` | `List<Subscription>` → String | Jackson JSON with `TypeReference<List<Subscription>>` | `model/containerEvent/converters/` |
| `ContainerTrackingEventMessageConverter` | `ContainerTrackingEventMessage` → String | Jackson JSON serialization | `model/` |
| `DateToEpochMilliSecond` | `Date` → Number | Epoch milliseconds | `model/containerEvent/converters/` |
| `DateToIso8601` | `Date` → String | ISO 8601 format | `model/containerEvent/converters/` |
| `DateToEpochSecond` | `Date` → Number | Epoch seconds (for TTL fields) | `model/` |
| `ReferencesAttributeConverter` | `List<Reference>` → String | Jackson JSON with `TypeReference<List<Reference>>` | `wm-inbound-processor/.../model/converters/` |
| `TransportLegsAttributeConverter` | `List<TransportLeg>` → String | Jackson JSON with `TypeReference<List<TransportLeg>>` | `wm-inbound-processor/.../model/converters/` |

All converters follow the standard pattern:
- Return `AttributeValue.builder().nul(true).build()` for null inputs
- Return `null` for null/empty `AttributeValue` inputs
- Use `AttributeValueType.S` (string) or `AttributeValueType.N` (number) for serialization
- Are thread-safe (static `ObjectMapper` instances)

#### DynamoDB Annotation Removal (~20 nested model classes)

All AWS SDK 1.x DynamoDB annotations are removed from nested model/DTO classes:

| Annotation Removed | Approx Count | Description |
|--------------------|-------------|-------------|
| `@DynamoDBDocument` | ~19 classes | Previously marked nested objects for DynamoDB Map serialization (includes ~15 in visibility-commons + 4 in visibility-wm-inbound-processor: Reference, TransportLeg, Location, LocationDate) |
| `@DynamoDBIgnore` | ~6 fields | No longer needed — SDK 2.x uses `@DynamoDbIgnore` only on top-level entities (includes LocationDate.getLocalDateTime() in wm-inbound-processor) |
| `@DynamoDBTypeConvertedEnum` | ~14 fields | Replaced by SDK 2.x Enhanced Client default enum handling (~3 in commons + 11 in CargoVisibilitySubscription nested models: Reference.referenceType, TransportLeg.stage/mode/means/transportMode, Location.locationType/identifierType, LocationDate.type/dateFormat, CargoVisibilitySubscription.state/type) |
| `@DynamoDBTypeConverted` | ~9 fields | Replaced by `@DynamoDbConvertedBy` on top-level entities (includes CargoVisibilitySubscription.expiresOn) |
| `@DynamoDBAttribute` | ~5 fields | Replaced by `@DynamoDbAttribute` on top-level entities |

**Why this is safe:** Nested classes (e.g., `ContainerEventSubmission`, `GISOutboundDetails`, `MetaData`, `ContainerEventEnrichedProperties`, `Location`, `VesselDetail`, `TransportationDetail`) are serialized to JSON strings by `AttributeConverter` implementations. They only need to be valid Jackson-serializable POJOs — they do NOT need any DynamoDB annotation.

#### Lambda Handler Migration

Lambda functions require import changes for DynamoDB event models:

```java
// Before (SDK 1.x — depends on aws-java-sdk-dynamodb)
import com.amazonaws.services.dynamodbv2.model.AttributeValue;
import com.amazonaws.services.dynamodbv2.model.OperationType;

// After (lambda-events v3.16.1 — embedded DynamoDB event models)
import com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue;
import com.amazonaws.services.lambda.runtime.events.models.dynamodb.OperationType;
```

API difference:
```java
// Before: OperationType.fromValue(record.getEventName()) == OperationType.INSERT
// After:  OperationType.INSERT.name().equals(record.getEventName())
```

Affected Lambda handlers:
- `VisibilityS3Archiver` (206 lines) — processes DynamoDB Streams events
- `VisibilityOutboundPoller` (166 lines) — if referencing DynamoDB models

#### Exception Changes

| Old (SDK 1.x) | New (SDK 2.x) |
|---------------|----------------|
| `com.amazonaws.services.dynamodbv2.model.ProvisionedThroughputExceededException` | `software.amazon.awssdk.services.dynamodb.model.ProvisionedThroughputExceededException` |
| `com.amazonaws.AmazonServiceException` | `software.amazon.awssdk.core.exception.SdkServiceException` |
| `com.amazonaws.SdkClientException` | `software.amazon.awssdk.core.exception.SdkClientException` |
| `com.amazonaws.AbortedException` | Handle via `SdkClientException` or `CancellationException` |

#### POM Dependency Changes

| Change Type | Dependency | Old Version | New Version | Reason |
|-------------|------------|-------------|-------------|--------|
| **Added** | `cloud-sdk-api` (mercury-services-commons) | N/A | 1.0.22-SNAPSHOT | AWS service abstraction interfaces |
| **Added** | `cloud-sdk-aws` (mercury-services-commons) | N/A | 1.0.22-SNAPSHOT | AWS SDK 2.x implementations |
| **Added** | `dynamo-integration-test` (mercury-services-commons) | N/A | 1.0.22-SNAPSHOT (test) | DynamoDB Local for integration tests |
| **Removed** | `dynamo-client` (mercury-services-commons) | 1.R.01.021 | — | Replaced by cloud-sdk Enhanced Client |
| **Scope Changed** | `aws-java-sdk-dynamodb` | compile | test | Required only for DynamoDB Local in integration tests |
| **Version Updated** | `aws-lambda-java-events` | 3.14.0 | 3.16.1 | Unified version; embeds DynamoDB event models |
| **Version Updated** | `commons` (mercury-services-commons) | 1.R.01.021 | 1.0.22-SNAPSHOT | cloud-sdk-api + cloud-sdk-aws transitive dependencies |

> **Note:** The `commons` dependency version update to `1.0.22-SNAPSHOT` brings in the cloud-sdk libraries transitively. The `mercury.commons.version` property in the parent POM is updated from `1.R.01.021` to `1.0.22-SNAPSHOT`.

#### Import Package Changes

| Old Package (SDK 1.x / Legacy) | New Package (SDK 2.x / cloud-sdk) |
|---------------------------------|-----------------------------------|
| `com.inttra.mercury.module.JestModule` | `com.inttra.mercury.cloudsdk.aws.module.JestModule` |
| `com.inttra.mercury.config.ElasticSearchServiceConfig` | `com.inttra.mercury.cloudsdk.config.ElasticSearchServiceConfig` |
| `com.amazonaws.services.dynamodbv2.datamodeling.*` | `software.amazon.awssdk.enhanced.dynamodb.mapper.annotations.*` |
| `com.amazonaws.services.dynamodbv2.model.AttributeValue` | `software.amazon.awssdk.services.dynamodb.model.AttributeValue` |
| `com.amazonaws.services.dynamodbv2.model.AttributeValue` (Lambda) | `com.amazonaws.services.lambda.runtime.events.models.dynamodb.AttributeValue` |
| `com.amazonaws.services.dynamodbv2.model.OperationType` (Lambda) | `com.amazonaws.services.lambda.runtime.events.models.dynamodb.OperationType` |
| `com.amazonaws.services.s3.AmazonS3` / `AmazonS3ClientBuilder` | `com.inttra.mercury.cloudsdk.api.storage.StorageClient` |
| `com.amazonaws.services.s3.model.S3Object` / `GetObjectRequest` | `com.inttra.mercury.cloudsdk.api.storage.StorageObject` |
| `com.amazonaws.services.sqs.model.Message` | `com.inttra.mercury.cloudsdk.api.messaging.QueueMessage<String>` |
| `com.inttra.mercury.dynamo.DynamoDBCrudRepository` | `com.inttra.mercury.cloudsdk.api.database.DatabaseRepository` |
| `com.inttra.mercury.dynamo.DynamoDBTableCreator` | `com.inttra.mercury.cloudsdk.aws.dynamodb.DynamoDbAdminCommand` |
| `com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapper` | `software.amazon.awssdk.enhanced.dynamodb.DynamoDbEnhancedClient` (via cloud-sdk) |

### UI

NA

### API Architecture

| Use Case | API | Body | Method (GET/POST/PUT/DELETE) | Query Parameter | Access Privilege (Admin/Non-Admin user) | Authorization Yes/No | Authentication Yes/No | Remarks |
|----------|-----|------|------------------------------|-----------------|----------------------------------------|---------------------|----------------------|---------|
| Container Track v1 | `/visibility/track` | - | GET | inttraRef, bookingRef, blRef, equipRef, carrierId | Non-Admin | Yes | Yes | Elasticsearch search |
| Container Track v1.2 | `/visibility/v1.2/track` | - | GET | inttraRef, bookingRef, blRef, equipRef, carrierId | Non-Admin | Yes | Yes | Enriched container model |
| Submit Event | `/visibility/v1.2/event` | ContainerEventSubmission JSON | POST | - | Non-Admin | Yes | Yes | REST event submission |
| Cargo Visibility JSON | `/cargo-visibility/submit/json` | Bulk JSON | POST | - | Non-Admin | Yes | Yes | Bulk submit |
| Cargo Visibility CSV | `/cargo-visibility/submit/csv` | CSV file | POST | - | Non-Admin | Yes | Yes | CSV upload |

---

## Configuration

### Component-Level Configuration

#### Configuration Hierarchy

```yaml
VisibilityApplicationConfig (extends ApplicationConfiguration)
  │
  ├─▶ dynamoDbConfig: BaseDynamoDbConfig
  │     ├─▶ environment: String (e.g., "inttra_int_visibility")
  │     ├─▶ region: String (AWS region)
  │     ├─▶ endpointOverride: String (Optional, for testing)
  │     ├─▶ readCapacityUnits: Long
  │     ├─▶ writeCapacityUnits: Long
  │     └─▶ sseEnabled: boolean
  │
  ├─▶ inboundProcessorConfig: ProcessorConfig
  │     ├─▶ inboundSqsConfig: SQSConfig
  │     │     ├─▶ url: String (SQS queue URL)
  │     │     ├─▶ dlqUrl: String (DLQ URL)
  │     │     ├─▶ waitInSeconds: int
  │     │     └─▶ messagesPerRead: int
  │     └─▶ threadPoolConfig: ThreadPoolConfig
  │
  ├─▶ matcherProcessorConfig: ProcessorConfig
  ├─▶ outboundProcessorConfig: OutboundProcessorConfig
  │     ├─▶ singleTransactionSqsProcessConfig: SQSConfig
  │     └─▶ multiTransactionSqsProcessConfig: SQSConfig
  │
  ├─▶ pendingProcessorConfig: ProcessorConfig
  ├─▶ wmEventProcessorConfig: ProcessorConfig
  ├─▶ gpsEventProcessorConfig: ProcessorConfig
  │
  ├─▶ esConfiguration: ESConfiguration
  ├─▶ eventLoggingConfig: EventLoggingConfig
  │     └─▶ snsTopicARN: String
  │
  ├─▶ s3ArchiveBucket: String
  └─▶ s3WorkspaceLocation: String
```

#### Configuration File Example

```yaml
# visibility-config.yaml (per service)

dynamoDbConfig:
  environment: "inttra_int_visibility"
  region: "us-east-1"
  readCapacityUnits: 5
  writeCapacityUnits: 5
  sseEnabled: true

inboundProcessorConfig:
  inboundSqsConfig:
    url: "https://sqs.us-east-1.amazonaws.com/123456789/ce-validate"
    dlqUrl: "https://sqs.us-east-1.amazonaws.com/123456789/ce-validate_dlq"
    waitInSeconds: 10
    messagesPerRead: 10
  threadPoolConfig:
    threads: 10
    maxQueuedTasks: 100

eventLoggingConfig:
  snsTopicARN: "arn:aws:sns:us-east-1:123456789:visibility-events"

s3ArchiveBucket: "visibility-archive-bucket"
s3WorkspaceLocation: "visibility-workspace"
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
- `START_RUN_EVENT`: Processing workflow started (inbound message received)
- `CLOSE_RUN_EVENT`: Processing workflow completed (success or error)
- `INFO_EVENT`: Informational events during processing

### Lifecycle Events
- Each Dropwizard service registers `StatusEventProcessorManagedHandler` for SQS processor lifecycle management
- `SqsMessageHandler` manages polling loop start/stop
- Lambda functions use `RequestHandler` interface with single invocation lifecycle

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

### DLQ Strategy
- Convention: append `_dlq` suffix to queue URL
- Failed messages are sent to DLQ before deletion from original queue
- Retryable errors (e.g., `ProvisionedThroughputExceededException`, `NetworkServicesException`) leave message in queue for auto-retry via SQS visibility timeout

### Error Handling

1. **Inbound Processing Errors**
   - `ProvisionedThroughputExceededException` → retry (don't DLQ)
   - `NetworkServicesException` → retry (don't DLQ)
   - `WebApplicationException` (validation) → discard (no DLQ)
   - Other errors → send to DLQ

2. **SQS Message Processing**
   - Messages acknowledged (deleted) after processing unless flagged for retry
   - `DO_NOT_DELETE` flag → leave message in source for auto-retry
   - `DO_NOT_SEND_TO_DLQ` flag → don't send to DLQ on failure

3. **Pending Retry**
   - Unmatched events stored in `container_events_pending` table
   - Lambda `PendingStart` triggers retry on schedule (daily for 7 days, weekly for weeks 2-4)
   - Events expire after 40 days (TTL)

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

The `commons` dependency remains at version **1.R.01.021** to maintain compatibility with `com.inttra.mercury.messaging` packages and the base `InttraServer` framework. Only cloud-sdk dependencies use the SNAPSHOT version.

---

## New/Upgraded Third party Applications/Jars

| Library | Old Version | New Version | Purpose |
|---------|-------------|-------------|---------|
| cloud-sdk-api | N/A (new) | 1.0.22-SNAPSHOT | AWS service abstractions |
| cloud-sdk-aws | N/A (new) | 1.0.22-SNAPSHOT | AWS SDK 2.x implementations |
| dynamo-integration-test | N/A (new) | 1.0.22-SNAPSHOT | DynamoDB integration test support (DynamoDB Local) |
| dynamo-client | 1.R.01.021 | Removed | Replaced by cloud-sdk DynamoDB |
| AWS SDK | 1.x (transitive via commons) | 2.x (via cloud-sdk-aws) | AWS service integration |
| aws-lambda-java-events | 3.14.0 / 3.16.1 | 3.16.1 (unified) | Lambda event models |
| Dropwizard | 4.0.x | 4.0.x (unchanged) | Application framework |
| Google Guice | - | - (unchanged) | Dependency injection |
| JUnit Jupiter | 6.1.0-M1 | 6.1.0-M1 (unchanged) | Unit testing |
| Mockito | 5.20.0 | 5.20.0 (unchanged) | Mocking framework |
| AssertJ | 4.0.0-M1 | 4.0.0-M1 (unchanged) | Assertion library |
| Elasticsearch | 6.8.13 | 6.8.13 (unchanged) | Search engine |

---

## Unit Test Plan

### Test Summary

| Category | Test Count (estimate) | Description |
|----------|----------------------|-------------|
| Unit Tests | 134 (existing) + ~30 new | All core logic, DAO, messaging, storage, DynamoDB converters, and configuration tests |
| Integration Tests | ~30-40 new | DynamoDB integration tests using DynamoDB Local (via `dynamo-integration-test`) |

### Existing Unit Tests (134 files across all sub-modules)

All 134 existing test files need migration from AWS SDK v1 mocks to cloud-sdk mocks:
- **DAO Tests**: Replace `DynamoDBCrudRepository` mocks with `DatabaseRepository` mocks
- **SQS Tests**: Replace `com.amazonaws.services.sqs.model.Message` with `QueueMessage<String>`
- **S3 Tests**: Replace `AmazonS3` mocks with `StorageClient` mocks
- **SNS Tests**: Replace direct SNS client mocks with `NotificationService` mocks
- **Lambda Tests**: Update event model classes
- **Injector/Config Tests**: Update Guice module bindings

### New Unit Tests

| Test Class | Sub-Module | Description |
|------------|------------|-------------|
| `VisibilityDynamoModuleTest` | commons/inbound | Test Guice DynamoDB module configuration |
| `VisibilityMessagingModuleTest` | commons/inbound | Test SQS/SNS module configuration |
| `VisibilityStorageModuleTest` | commons/inbound | Test S3 module configuration |
| `ContainerEventSubmissionAttributeConverterTest` | commons | Test round-trip serialization |
| `ContainerEventEnrichedPropertiesAttributeConverterTest` | commons | Test round-trip serialization |
| `MetaDataAttributeConverterTest` | commons | Test round-trip serialization |
| `GISOutboundDetailsAttributeConverterTest` | commons | Test round-trip serialization |
| `SubscriptionAttributeConverterTest` | commons | Test round-trip serialization |
| `DateEpochMilliSecondAttributeConverterTest` | commons | Test date conversion |
| `DateIso8601AttributeConverterTest` | commons | Test date conversion |
| `DateEpochSecondAttributeConverterTest` | commons | Test date conversion |
| `VisibilityDynamoDbAdminCommandTest` | inbound | Test table creation command |
| `SQSClientTest` | commons | Test MessagingClient wrapper |
| `SNSClientTest` | commons | Test NotificationService wrapper |
| `ReferencesAttributeConverterTest` | wm-inbound-processor | Test List<Reference> round-trip serialization |
| `TransportLegsAttributeConverterTest` | wm-inbound-processor | Test List<TransportLeg> round-trip serialization |
| `CargoVisibilitySubscriptionDaoTest` | wm-inbound-processor | Test CargoVisibilitySubscriptionDao with mocked DatabaseRepository |

### DynamoDB Integration Tests

Uses `BaseDynamoDbIT` from `dynamo-integration-test` (mercury-services-commons) with embedded DynamoDB Local.

| Test Class | Sub-Module | Tests (estimate) | Description |
|------------|------------|------------------|-------------|
| `ContainerEventDaoIT` | commons/inbound | 8-12 | CRUD, TTL, GSI queries, nested object serialization |
| `ContainerEventOutboundDaoIT` | commons/inbound | 6-8 | Composite key CRUD, TTL, query by IPF ID |
| `ContainerEventPendingDaoIT` | commons/inbound | 6-8 | Composite key CRUD, query by date, delete |
| `ContainerTrackingEventDaoIT` | commons/inbound | 4-6 | CRUD, GSI queries |
| `CargoVisibilitySubscriptionDaoIT` | wm-inbound-processor | 6-8 | CRUD, TTL, GSI queries (bookingNumber-index, subscriptionReference-index), nested Reference/TransportLeg serialization |
| `VisibilityDynamoDbAdminCommandIT` | inbound | 8-12 | Table creation, PK/SK validation, GSI validation, TTL config |

### Test Execution Commands

```bash
# Run All Tests (unit + integration)
mvn clean verify -pl visibility -am

# Run Unit Tests Only (specific sub-module)
mvn test -pl visibility/visibility-commons
mvn test -pl visibility/visibility-inbound
mvn test -pl visibility/visibility-matcher
mvn test -pl visibility/visibility-outbound

# Run Specific Test Class
mvn test -pl visibility/visibility-commons -Dtest=ContainerEventDaoTest
mvn test -pl visibility/visibility-commons -Dtest=SQSClientTest

# Run Integration Tests Only
mvn verify -pl visibility/visibility-inbound -Dtest=none -DfailIfNoTests=false -Dit.test=ContainerEventDaoIT
mvn verify -pl visibility/visibility-inbound -Dtest=none -DfailIfNoTests=false -Dit.test=VisibilityDynamoDbAdminCommandIT
```

### QA Note

All unit tests pass with `mvn verify -pl visibility -am`. DynamoDB integration tests use embedded DynamoDB Local
(via `dynamo-integration-test`), requiring no external infrastructure. Integration tests are marked with
`@Category(IntegrationTests.class)` and run during the `verify` phase.

---

## Pre-Dev Security

| TOPIC | Valid (Y/N) | Comments |
|-------|-------------|----------|
| New UI pages/data exposed to users | N | No UI components |
| Use of new services/ports | N | Uses existing SQS, SNS, S3, DynamoDB, SES services |
| Authentication changes | N | No authentication changes |
| New/changed encryption | N | Uses existing AWS encryption |
| Changes in the way data is transmitted | N | Standard AWS SDK 2.x communication (same protocols, TLS) |
| Changes in the way/location data is being stored | N | DynamoDB storage unchanged; same tables, same attributes |
| New API implementation / change of existing APIs | N | No new external APIs |
| New / Change in existing file upload functionality | N | No file upload functionality changes |
| New / Change in integration within e2open or third party apps | N | Same AWS services, upgraded SDK version |
| New / Existing UI functionality support querying | N | No UI functionality |

---

## REQUIRED: Documentation Changes

| Question | Answer |
|----------|--------|
| Do end users interact with this feature? | No |
| Do project teams/SIs/BIT teams need to enable or configure this feature? | Yes (DynamoDB config uses `BaseDynamoDbConfig` in YAML configs) |
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
# Build All Sub-Modules
mvn clean package -pl visibility -am

# Build Specific Service
mvn clean package -pl visibility/visibility-inbound -am
# Output: visibility/visibility-inbound/target/visibility-inbound-1.0.jar

# Build Specific Lambda
mvn clean package -pl visibility/visibility-s3-archiver -am
# Output: visibility/visibility-s3-archiver/target/visibility-s3-archiver-1.0-deployment_package.zip
```

### Environment Configuration

Each Dropwizard service has environment-specific YAML configs in `conf/{env}/config.yaml`:
- `int` — Integration environment
- `qa` — QA environment
- `cvt` — CVT environment
- `prod` — Production environment

DynamoDB table names follow the pattern: `{environment}_{table_name}` (e.g., `inttra_int_visibility_container_events`).

### DynamoDB Table Management

```bash
# Create DynamoDB tables (via CLI command)
java -jar visibility/visibility-inbound/target/visibility-inbound-1.0.jar dynamo-create visibility/visibility-inbound/conf/int/config.yaml
```
