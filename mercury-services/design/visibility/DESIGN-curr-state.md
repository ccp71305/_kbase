# Visibility Module — Current State Design Document

> **Status**: Pre-AWS 2.x Upgrade  
> **Date**: 2026-03-30  
> **Module**: `visibility/` (multi-module Maven project)  
> **AWS SDK**: AWS SDK v1 (legacy) — upgrade NOT STARTED

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)  
2. [Module Overview](#2-module-overview)  
3. [High-Level Architecture](#3-high-level-architecture)  
4. [Data Flow Pipeline](#4-data-flow-pipeline)  
5. [Sub-Module Deep Dives](#5-sub-module-deep-dives)  
   - 5.1 [visibility-commons](#51-visibility-commons)  
   - 5.2 [visibility-inbound](#52-visibility-inbound)  
   - 5.3 [visibility-matcher](#53-visibility-matcher)  
   - 5.4 [visibility-outbound](#54-visibility-outbound)  
   - 5.5 [visibility-pending](#55-visibility-pending)  
   - 5.6 [visibility-wm-inbound-processor](#56-visibility-wm-inbound-processor)  
   - 5.7 [visibility-itv-gps-processor](#57-visibility-itv-gps-processor)  
   - 5.8 [visibility-s3-archiver (Lambda)](#58-visibility-s3-archiver-lambda)  
   - 5.9 [visibility-error-email (Lambda)](#59-visibility-error-email-lambda)  
   - 5.10 [visibility-pending-start (Lambda)](#510-visibility-pending-start-lambda)  
   - 5.11 [visibility-outbound-poller (Lambda)](#511-visibility-outbound-poller-lambda)  
6. [Database & Storage Layer](#6-database--storage-layer)  
7. [AWS Services Usage](#7-aws-services-usage)  
8. [Network Services Integration](#8-network-services-integration)  
9. [Build & Deployment](#9-build--deployment)  
10. [Sub-Module Dependency Matrix](#10-sub-module-dependency-matrix)  
11. [Key Configuration](#11-key-configuration)  
12. [Summary of AWS SDK v1 Usage](#12-summary-of-aws-sdk-v1-usage)  

---

## 1. Executive Summary

The **Visibility module** is a multi-module Maven project within the `mercury-services` monorepo that provides container tracking and shipment visibility services. It processes container status events (milestones like gate-in, gate-out, vessel departure, vessel arrival, etc.) from multiple sources — EDI feeds, Watermill/Shippeo premium providers, and ITV GPS feeds — matches them to existing bookings/shipments in Elasticsearch, and delivers outbound status notifications to subscribers in various formats (GIS/EDI).

The module consists of **11 sub-modules**:
- **6 Dropwizard services** (long-running, deployed as Docker containers)
- **4 AWS Lambda functions** (event-driven, deployed as ZIP packages)
- **1 shared library** (`visibility-commons`)

All sub-modules currently use **AWS SDK v1** for DynamoDB, SQS, SNS, and S3 operations, with the `dynamo-client` library providing DynamoDB abstraction. The commons module also uses the legacy `mercury-services-commons` artifact (`com.inttra.mercury:commons:1.R.01.021`).

---

## 2. Module Overview

```
visibility/                           (parent POM, packaging=pom)
├── visibility-commons/               Shared library (models, DAOs, services, configs)
├── visibility-inbound/               Dropwizard: REST API + EDI SQS processor
├── visibility-wm-inbound-processor/  Dropwizard: Watermill/Shippeo SQS processor
├── visibility-itv-gps-processor/     Dropwizard: ITV GPS event SQS processor
├── visibility-matcher/               Dropwizard: DynamoDB Stream → match to bookings
├── visibility-outbound/              Dropwizard: Generate outbound GIS/EDI files
├── visibility-pending/               Dropwizard: Retry unmatched events
├── visibility-s3-archiver/           Lambda: Archive container events to S3
├── visibility-error-email/           Lambda: Send automated error report emails
├── visibility-pending-start/         Lambda: Trigger pending retry via SQS
└── visibility-outbound-poller/       Lambda: Poll MySQL thresholds → trigger outbound
```

### Sub-Module Classification

| Sub-Module | Type | Deployment | Entry Point |
|---|---|---|---|
| `visibility-commons` | Library (JAR) | Not deployed standalone | N/A |
| `visibility-inbound` | Dropwizard Service | Docker container | `VisibilityInboundApplication` |
| `visibility-wm-inbound-processor` | Dropwizard Service | Docker container | `VisibilityWMEventApplication` |
| `visibility-itv-gps-processor` | Dropwizard Service | Docker container | `VisibilityGPSEventApplication` |
| `visibility-matcher` | Dropwizard Service | Docker container | `VisibilityMatcherApplication` |
| `visibility-outbound` | Dropwizard Service | Docker container | `VisibilityOutboundApplication` |
| `visibility-pending` | Dropwizard Service | Docker container | `VisibilityPendingApplication` |
| `visibility-s3-archiver` | AWS Lambda | ZIP deployment | `VisibilityS3Archiver.handleRequest` |
| `visibility-error-email` | AWS Lambda | ZIP deployment | `VisibilityErrorEmail.handleRequest` |
| `visibility-pending-start` | AWS Lambda | ZIP + CloudFormation | `VisibilityPendingStart.handleRequest` |
| `visibility-outbound-poller` | AWS Lambda | ZIP + CloudFormation | `VisibilityOutboundPoller.handleRequest` |

---

## 3. High-Level Architecture

```
                                    ┌──────────────────────────────┐
                                    │      External Sources        │
                                    │  EDI / Watermill / ITV GPS   │
                                    └──────────┬───────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
        ┌──────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
        │  visibility-     │   │  visibility-wm-      │   │  visibility-itv- │
        │  inbound         │   │  inbound-processor   │   │  gps-processor   │
        │  (EDI + REST)    │   │  (Watermill/Shippeo) │   │  (GPS Events)    │
        └─────────┬────────┘   └──────────┬───────────┘   └─────────┬────────┘
                  │                       │                          │
                  │   ┌───────────────────┘                          │
                  │   │                                              │
                  ▼   ▼                                              ▼
        ┌───────────────────────────────────────────────────────────────────┐
        │                     DynamoDB: container_events                    │
        │                     (with DynamoDB Streams enabled)               │
        └─────────────────────────────┬─────────────────────────────────────┘
                                      │ DynamoDB Stream (INSERT)
                                      │ via SNS → SQS
                                      ▼
                          ┌──────────────────────┐
                          │  visibility-matcher   │
                          │  (Match to bookings)  │    Elasticsearch
                          └──────────┬───────────┘    (Booking/SI index)
                                     │
                         ┌───────────┴───────────┐
                         │                       │
                    ┌────▼─────┐         ┌───────▼──────┐
                    │ Matched  │         │ Not Matched  │
                    └────┬─────┘         └───────┬──────┘
                         │                       │
                         ▼                       ▼
              ┌────────────────────┐   ┌──────────────────────┐
              │  SQS: Outbound     │   │  DynamoDB:           │
              │  (single/multi)    │   │  container_events_   │
              └────────┬───────────┘   │  pending             │
                       │               └──────────┬───────────┘
                       ▼                          │
              ┌────────────────────┐    ┌─────────▼──────────┐
              │  visibility-       │    │  visibility-        │
              │  outbound          │    │  pending            │
              │  (GIS/EDI files)   │    │  (Retry matching)   │
              └────────┬───────────┘    └────────────────────┘
                       │
                       ▼
              ┌────────────────────┐
              │  S3: Outbound      │
              │  bucket (GIS files)│
              └────────────────────┘

   ┌─────────────┐   ┌──────────────────┐   ┌──────────────────┐
   │ Lambda:      │   │ Lambda:          │   │ Lambda:          │
   │ S3 Archiver  │   │ Outbound Poller  │   │ Pending Start    │
   │ (archive CE) │   │ (poll thresholds)│   │ (trigger retry)  │
   └──────────────┘   └──────────────────┘   └──────────────────┘

   ┌──────────────┐
   │ Lambda:      │
   │ Error Email  │
   │ (send errors)│
   └──────────────┘
```

---

## 4. Data Flow Pipeline

The core data processing follows an event-driven pipeline pattern:

### 4.1 Inbound Processing

```
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 1: INBOUND                                                        │
│                                                                          │
│  Source → S3 → SQS → InboundEdiProcessor                                │
│                                                                          │
│  1. SQS message contains MetaData with S3 bucket & filename             │
│  2. Retrieve EDI content from S3                                         │
│  3. Apply carrier-specific custom transformations                        │
│  4. Map EDI → canonical ContainerEventSubmission                         │
│     (supports IFTSTA and T315 EDI formats)                               │
│  5. Validate and enrich (geography, participant, status code)            │
│  6. Persist ContainerEvent to DynamoDB (container_events table)          │
│  7. DynamoDB Stream fires on INSERT                                      │
│                                                                          │
│  Error handling:                                                         │
│  - ProvisionedThroughputExceededException → retry (don't DLQ)           │
│  - NetworkServicesException → retry (don't DLQ)                          │
│  - WebApplicationException (validation) → discard (no DLQ)              │
│  - Other errors → send to DLQ                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Matching

```
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 2: MATCHING                                                        │
│                                                                          │
│  DynamoDB Stream (INSERT) → SNS → SQS → MatchingProcessor               │
│                                                                          │
│  1. Extract container event ID from DynamoDB stream record               │
│  2. Read full ContainerEvent from DynamoDB                               │
│  3. Skip GPS events (eventCode = "GPS")                                  │
│  4. Search Elasticsearch for matching bookings/SIs by:                   │
│     - Carrier SCAC + Booking Number                                      │
│     - Carrier SCAC + Bill of Lading Number                               │
│     - Equipment Reference                                                │
│  5. Update ContainerEvent with matched booking references                │
│  6. Get outbound subscriptions per matched recipient                     │
│  7. Create ContainerEventOutbound records → send to outbound SQS         │
│  8. If no match → save to container_events_pending table                 │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Outbound Processing

```
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 3: OUTBOUND                                                        │
│                                                                          │
│  Two modes:                                                              │
│                                                                          │
│  SINGLE TRANSACTION (transactionsPerFile = 1):                           │
│  SQS → OutboundSingleTransactionProcessor                               │
│  1. Save ContainerEventOutbound to DynamoDB                              │
│  2. Get IPF (Integration Profile Format) config                          │
│  3. Generate GIS/EDI outbound file                                       │
│  4. Upload to S3 outbound bucket                                         │
│                                                                          │
│  MULTI TRANSACTION (transactionsPerFile > 1):                            │
│  SQS → OutboundSingleTransactionProcessor (increment threshold)          │
│  Then:                                                                   │
│  Lambda OutboundPoller → SQS → OutboundMultiTransactionProcessor         │
│  1. Lock outbound threshold row in MySQL                                 │
│  2. Read all unprocessed outbound transactions from DynamoDB             │
│  3. Batch into files of N transactions                                   │
│  4. Generate GIS/EDI outbound file per batch                             │
│  5. Upload to S3, unlock threshold row                                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Pending Retry

```
┌──────────────────────────────────────────────────────────────────────────┐
│  STEP 4: PENDING RETRY                                                   │
│                                                                          │
│  Lambda PendingStart (scheduled) → SQS → PendingSqsProcessor            │
│                                                                          │
│  1. PendingStart Lambda sends PendingFilter messages to SQS              │
│     (date ranges: last 7 days daily + weeks 2-4)                         │
│  2. PendingSqsProcessor queries container_events_pending by date         │
│  3. For each pending event:                                              │
│     a. Read full ContainerEvent from DynamoDB                            │
│     b. Re-run matching in Elasticsearch                                  │
│     c. If matched → create outbound records, delete from pending         │
│     d. If still not matched → leave in pending                           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Sub-Module Deep Dives

### 5.1 visibility-commons

**Purpose**: Shared library containing models, DAOs, network service clients, configuration, and processing infrastructure used by all other sub-modules.

**Key Packages & Classes**:

| Package | Key Classes | Responsibility |
|---|---|---|
| `common.model.containerEvent` | `ContainerEvent`, `ContainerEventSubmission`, `ContainerEventOutbound`, `ContainerEventPending`, `ContainerEventOutboundMetaData`, `ContainerEventResponse`, `MatchedBooking`, `GISOutboundDetails` | Core domain models stored in DynamoDB |
| `common.model` | `ContainerTrackingEvent`, `ContainerTrackingEventMessage`, `Container` | Legacy tracking models |
| `common.persistence` | `ContainerEventDao`, `ContainerEventOutboundDao`, `ContainerEventPendingDao`, `ContainerTrackingEventDao`, `ContainerEventOutboundThresholdDao` | DynamoDB DAO layer (extends `DynamoDBCrudRepository` from `dynamo-client`) |
| `common.processor` | `StatusEventProcessor<T>`, `StatusEventProcessorManagedHandler`, `ProcessingConstants` | SQS processor interface and lifecycle management |
| `common.processor.sqs` | `SqsMessageHandler`, `SqsMessageHandlerManager` | SQS polling loop with bounded thread pool, DLQ handling |
| `common.service` | `S3WorkspaceService`, `SNSMapper` | S3 read/write operations, SNS message deserialization |
| `common.config` | `VisibilityApplicationConfig`, `VisibilityApplicationInjector`, `SQSConfig`, `ThreadPoolConfig`, `ESConfiguration` | Base Guice module and Dropwizard config |
| `common.networkservices` | `SubscriptionService`, `IntegrationProfileFormatService`, `GeographyService`, `ParticipantService`, `NetworkServiceClient`, `AuthClient`, `FormatService`, `StatusEventCodeService`, `ContainerTypeService`, `BlacklistEmailService` | REST clients to Network module APIs |
| `common.booking` | `BookingService`, `BookingDao` | Integration with the booking module |
| `subscription` | `SubscriptionHelper`, `ConditionEvaluator` | Subscription filtering logic (condition-based matching) |

**Dependencies**:
- `com.inttra.mercury:commons:1.R.01.021` (legacy mercury-services-commons)
- `com.inttra.mercury:dynamo-client:1.R.01.021` (DynamoDB DynamoDBMapper abstraction)
- `com.inttra.mercury:booking:2.1.8.M` (booking module for cross-module data access)
- `com.amazonaws:aws-lambda-java-events` (DynamoDB stream event models)
- Elasticsearch REST high-level client 6.8.13
- Jackson, Lombok, Guice, Dropwizard

**AWS SDK v1 Classes Used**:
- `com.amazonaws.services.s3.AmazonS3`, `AmazonS3ClientBuilder`
- `com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapper`
- `com.amazonaws.services.dynamodbv2.model.ProvisionedThroughputExceededException`
- `com.amazonaws.services.sqs.model.Message`
- `com.amazonaws.services.lambda.runtime.events.*`

---

### 5.2 visibility-inbound

**Purpose**: Main REST API service and EDI inbound processor. Receives container events via REST API and SQS, validates, enriches, and persists them to DynamoDB.

**Deployment**: Dropwizard service → Docker container  
**Main Class**: `VisibilityInboundApplication`  
**Port**: 8080 (app), 8081 (admin)  
**Root Path**: `/visibility`

**Guice Modules**:
- `VisibilityInboundApplicationInjector` → binds `InboundEdiProcessor`, `IFTSTAMapper`, `T315Mapper`, carrier-specific `InboundTransformer`s
- `MyCustomBatisModule` x3 (MySQL read/write, MySQL readonly, Oracle legacy)
- `DynamoDBModule`, `LocalCacheModule`, `SQSModule`, `SNSModule`
- `ElasticSearchClientModule`, `MetricsInstrumentationModule`

**REST Resources**:

| Resource | Path | Description |
|---|---|---|
| `VisibilityResource` (deprecated) | `GET /containers` | Legacy container search by various identifiers |
| `ContainerTrackingResource` | `GET /track` | v1 search: by INTTRA ref, booking ref, BL, equipment |
| `ContainerTrackingResource` | `GET /v1.2/track` | v1.2 search: same with enriched container model |
| `ContainerTrackingResource` | `POST /v1.2/event` | Submit container status event via API |
| `ContainerTrackingResource` | `GET /v1.2/track/{broad_search_key}` | Broad search across all indexes |
| `CargoVisibilityResource` | `POST /cargo-visibility/submit/json` | Bulk cargo visibility submission (JSON) |
| `CargoVisibilityResource` | `POST /cargo-visibility/submit/csv` | Cargo visibility submission (CSV upload) |
| `SupportResource` | Various | Admin/support operations |

**SQS Processor — InboundEdiProcessor**:

```
SQS (ce_validate queue)
  │
  ▼
InboundEdiProcessor.process(Message)
  │
  ├─ 1. Parse MetaData from SQS body
  ├─ 2. getEdiContainerEventFromS3() → S3WorkspaceService.getContent()
  ├─ 3. applyCustomizations() → InboundTransformerFactory (carrier-specific)
  │     ├─ USAIDGrossWeightTransformer
  │     ├─ WWACarrierTransformer
  │     ├─ WHLCStatusTransformer
  │     └─ EVGCarrierTransformer
  ├─ 4. createContainerEventSubmission() → InboundMapperFactory
  │     ├─ IFTSTAMapper (IFTSTA EDI format)
  │     └─ T315Mapper (T315 EDI format)
  ├─ 5. containerEventService.validateAndPersist() → ContainerEventDao.save()
  └─ 6. eventLogHandler.logEvent()
```

**Databases**:
- **MySQL (ContainerEvent)**: Read/write for `OutboundThreshold` table
- **MySQL Read-Only**: Replica for threshold reads
- **Oracle (inttra)**: Legacy subscription data (`ContainerEventSubscriptionDao`)
- **DynamoDB**: `container_events`, `container_events_outbound`, `container_events_pending`
- **Elasticsearch**: For container tracking search queries

**Key Dependencies**: `visibility-commons`, Oracle JDBC, SES SDK v2 (for email), Jakarta Mail

---

### 5.3 visibility-matcher

**Purpose**: Consumes DynamoDB Stream events (via SNS→SQS) for newly inserted container events, matches them against booking/shipping instruction data in Elasticsearch, and routes matched events to outbound processing.

**Deployment**: Dropwizard service → Docker container  
**Main Class**: `VisibilityMatcherApplication`

**Guice Modules**:
- `VisibilityMatcherApplicationInjector` → binds `MatchingProcessor`
- `DynamoDBModule`, `LocalCacheModule`, `SQSModule`, `SNSModule`, `MetricsInstrumentationModule`

**Processing Flow — MatchingProcessor**:

```
DynamoDB Stream (container_events INSERT)
  │
  ▼ (via SNS → SQS)
MatchingProcessor.process(Message)
  │
  ├─ 1. getContainerEventIdFromSqsMessage()
  │     └─ Parse SNS → DynamoDB Stream Record → extract "id" key
  ├─ 2. containerEventDao.getSingleById() → read from DynamoDB
  ├─ 3. Skip if GPS event (statusEventCode = "GPS")
  ├─ 4. transactionSearchService.findMatchingTransactions()
  │     └─ Search Elasticsearch: booking/SI by carrier+booking#, carrier+BL#, equipment#
  ├─ 5. containerEventDao.save() → update with matched bookings
  ├─ 6. integrationSubscriptionService.getOutboundSubscriptionsByParticipant()
  │     └─ Get subscriptions for requested recipients + matched company IDs
  ├─ 7. processOutbound() → AbstractMatcher
  │     ├─ Filter subscriptions (PremiumVisibility, CargoVisibility programs)
  │     ├─ SubscriptionHelper.filterSubscriptions() (condition evaluation)
  │     ├─ Create ContainerEventOutbound per IPF
  │     └─ sendToOutboundSqs() → SQS (outbound queue)
  └─ 8. If not matched → processPending()
        └─ containerEventPendingDao.save()
```

**Key Classes**:

| Class | Responsibility |
|---|---|
| `MatchingProcessor` | Main SQS processor, extends `AbstractMatcher` |
| `AbstractMatcher` | Shared logic for matching + outbound routing (used by both matcher and pending) |
| `TransactionSearchService` | Elasticsearch queries for booking/SI matching |
| `TransactionScrollSearch` | Scroll-based Elasticsearch pagination |
| `TransactionQueryUtil` | Query builders for Elasticsearch |
| `IntegrationSubscriptionService` | Maps subscriptions to IPF configurations |

---

### 5.4 visibility-outbound

**Purpose**: Generates outbound files (GIS/EDI format) from matched container events and uploads them to S3 for downstream delivery.

**Deployment**: Dropwizard service → Docker container  
**Main Class**: `VisibilityOutboundApplication`

**Guice Modules**:
- `VisibilityOutboundApplicationInjector` → binds `OutboundSingleTransactionProcessor`, `OutboundMultiTransactionProcessor`
- `DynamoDBModule`, `MyCustomBatisModule` (MySQL), `SQSModule`, `SNSModule`, `LocalCacheModule`

**Two Processing Modes**:

#### Single Transaction Mode (transactionsPerFile = 1)

```
SQS (outbound single queue) → OutboundSingleTransactionProcessor
  │
  ├─ 1. Parse MetaData + ContainerEventOutbound JSON from SQS
  ├─ 2. Save ContainerEventOutbound to DynamoDB
  ├─ 3. Get IntegrationProfileFormat (IPF) from Network service
  ├─ 4. If transactionsPerFile == 1:
  │     └─ OutboundGenerator.createAndSendSingleTransaction()
  │         ├─ Apply subscription-based filtering/enrichment
  │         ├─ Generate GIS transaction content
  │         └─ Upload to S3 outbound bucket
  └─ 5. If transactionsPerFile > 1:
        └─ containerEventOutboundThresholdDao.incrementTransactionCount()
```

#### Multi Transaction Mode (batched)

```
Lambda OutboundPoller (scheduled) → SQS (outbound multi queue)
  │
  ▼
OutboundMultiTransactionProcessor.process(Message)
  │
  ├─ 1. Get IPF ID from SQS message (OutboundThreshold)
  ├─ 2. Read OutboundThreshold from MySQL (via read-only DAO)
  ├─ 3. Check if time threshold or transaction count threshold crossed
  ├─ 4. Lock threshold row in MySQL
  ├─ 5. OutboundGenerator.createAndSendBatchTransactions()
  │     ├─ Read all unprocessed ContainerEventOutbound from DynamoDB
  │     ├─ Batch into groups of N
  │     ├─ Generate GIS file per batch
  │     └─ Upload to S3
  └─ 6. Update threshold row (reset count, update timestamp), unlock
```

**Key Classes**:

| Class | Responsibility |
|---|---|
| `OutboundSingleTransactionProcessor` | Single-event outbound processing |
| `OutboundMultiTransactionProcessor` | Batched outbound processing (time/count thresholds) |
| `OutboundGenerator` | GIS file generation, S3 upload, enrichment |
| `GISTransaction` | GIS format (IFTSTA/T315) file content builder |
| `GISFileSegmentFormat` | Format-specific segment templates |
| `OutboundEnrichmentUtil` | Enriches outbound events with additional data |

---

### 5.5 visibility-pending

**Purpose**: Retries matching for container events that were not matched initially. Scheduled via a Lambda trigger.

**Deployment**: Dropwizard service → Docker container  
**Main Class**: `VisibilityPendingApplication`

**Processing Flow — PendingSqsProcessor**:

```
Lambda PendingStart → SQS (pending queue) → PendingSqsProcessor
  │
  ├─ 1. Parse PendingFilter (processDate + prefix) from SQS
  ├─ 2. containerEventPendingDao.getPendingTransactionsByDate()
  │     └─ Query DynamoDB: container_events_pending by date + prefix
  ├─ 3. For each pending Container Event:
  │     ├─ Read full ContainerEvent from DynamoDB
  │     ├─ Re-run Elasticsearch matching
  │     ├─ If matched:
  │     │   ├─ Create outbound records
  │     │   ├─ Send to outbound SQS
  │     │   └─ Delete from pending table
  │     └─ If not matched: leave in pending
  └─ 4. Events expire from pending table after 40 days (TTL)
```

`PendingSqsProcessor` extends `AbstractMatcher`, sharing the same matching and outbound-routing logic as `MatchingProcessor`.

---

### 5.6 visibility-wm-inbound-processor

**Purpose**: Processes container visibility events from the Watermill platform (e2open). Handles three message types: Shippeo container events, cargo visibility subscription responses, and cargo visibility events.

**Deployment**: Dropwizard service → Docker container  
**Main Class**: `VisibilityWMEventApplication`

**Architecture — Pluggable Processor Pattern**:

```
SQS → WMEventProcessor (orchestrator)
  │
  ├─ Parse MetaData, retrieve payload from S3
  ├─ Determine WatermillMessageType from metadata projections
  └─ Route to appropriate MessageTypeProcessor:
      │
      ├─ ShippeoContainerEventProcessor
      │   ├─ Parse Shippeo-format container event
      │   ├─ Map to canonical ContainerEventSubmission
      │   ├─ Resolve network participant
      │   ├─ Validate and persist to DynamoDB
      │   └─ (triggers DynamoDB Stream → Matcher)
      │
      ├─ CargoVisibilitySubscriptionProcessor
      │   ├─ Parse subscription response
      │   └─ Update subscription state in DynamoDB
      │
      └─ CargoVisibilityEventProcessor
          ├─ Parse cargo visibility event
          ├─ Map to ContainerEventSubmission
          ├─ Validate and persist to DynamoDB
          └─ (triggers DynamoDB Stream → Matcher)
```

**Key Classes**:

| Class | Responsibility |
|---|---|
| `WMEventProcessor` | Orchestrator — SQS consumer, message routing |
| `MessageTypeProcessor` (interface) | Contract for type-specific processors |
| `ShippeoContainerEventProcessor` | Shippeo premium event processing |
| `CargoVisibilitySubscriptionProcessor` | Subscription lifecycle management |
| `CargoVisibilityEventProcessor` | Cargo visibility event processing |
| `PremiumEventProvider` | Configuration of premium event sources |
| `CargoVisibilitySubscriptionDao` | DynamoDB DAO for subscriptions |
| `WatermillMessageType` (enum) | Message type classification |

**DynamoDB Models**:
- `ContainerEvent` (from visibility-commons — Shippeo container events written to `container_events` table)
- `CargoVisibilitySubscription` (own DynamoDB table `CargoVisibilitySubscription` — **this is a dedicated DynamoDB table**, NOT in visibility-commons)
- `CargoVisibilitySubscriptionResponse` (DTO only — not a DynamoDB entity)

**CargoVisibilitySubscription DynamoDB Details**:

| Attribute | Description |
|---|---|
| **Table** | `CargoVisibilitySubscription` |
| **Hash Key** | `id` (String) via `@DynamoDBHashKey(attributeName = "id")` |
| **TTL** | `expiresOn` (epoch seconds) via `@DynamoDBTypeConverted(converter = DateToEpochSecond.class)` |
| **GSI `bookingNumber-index`** | Hash: `bookingNumber` |
| **GSI `subscriptionReference-index`** | Hash: `subscriptionReference` |
| **Enum fields** | `state` (`SubscriptionState`: SUBMITTED, APPROVED, REJECTED, CANCELLED), `type` (`SubscriptionSource`: INTTRA, CUSTOMER) — both via `@DynamoDBTypeConvertedEnum` |
| **Nested beans** | `List<Reference>` (with `@DynamoDBDocument` + `ReferenceType` enum), `List<TransportLeg>` (with `@DynamoDBDocument` + 4 enum fields + nested `Location` with `LocationDate`) |

**CargoVisibilitySubscriptionDao** extends `DynamoDBCrudRepository<CargoVisibilitySubscription, DynamoHashKey<String>>`:
- `findById(id)` — loads by primary key (lowercased)
- `findBySubscriptionReference(ref)` — queries GSI `subscriptionReference-index`, loads full objects, sorts by `modifiedOn` desc, returns newest
- `save(subscription)` — inherited from `DynamoDBCrudRepository`

> **Note**: The `watermill-publisher/watermill-cargo-visibility-subscription` module (outside the visibility module) has a SECOND `CargoVisibilitySubscription` model class accessing the SAME DynamoDB table with additional GSIs (`bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index`) and additional fields (`carrierBookingNumber`, `billOfLadingNumber`, `serviceType`). The watermill-publisher version also has `@DynamoDBIndexRangeKey` on `carrierScac` for composite GSI keys.

---

### 5.7 visibility-itv-gps-processor

**Purpose**: Processes ITV (Intermodal Terminal Visibility) GPS events. These are vessel/container GPS coordinate updates from third-party tracking providers.

**Deployment**: Dropwizard service → Docker container  
**Main Class**: `VisibilityGPSEventApplication`

**Processing Flow — GPSEventProcessor**:

```
S3 (ITV file) → SNS → SQS → GPSEventProcessor
  │
  ├─ 1. Parse SNS → S3Event → read ITV file from S3
  ├─ 2. Parse ITVEvent (contains list of Upserts)
  ├─ 3. For each Upsert (parallelStream):
  │     ├─ ITVGPSEventMapper.createContainerEventSubmission()
  │     │   ├─ Map GPS coordinates, vessel details, parties
  │     │   └─ Set statusEventCode = "GPS"
  │     ├─ ContainerEventValidator.validate()
  │     ├─ ContainerEventDao.save() → DynamoDB
  │     └─ (Note: GPS events are SKIPPED by Matcher — no outbound)
  └─ 4. Log events
```

**Key Classes**:

| Class | Responsibility |
|---|---|
| `GPSEventProcessor` | SQS consumer for GPS events |
| `ITVGPSEventMapper` | Maps ITV GPS format → ContainerEventSubmission |
| `ITVEvent`, `Upsert`, `GPSEvent` | ITV-specific domain models |
| `GeoCoordinates`, `Conveyance` | GPS location and vessel models |

**Important**: GPS events (statusEventCode = "GPS") are stored in DynamoDB but are **explicitly skipped** by the Matcher — they do not trigger outbound processing. They are also skipped by the S3 Archiver.

---

### 5.8 visibility-s3-archiver (Lambda)

**Purpose**: Archives container event records from DynamoDB to S3 for long-term storage. Triggered by DynamoDB Stream changes (via SNS→SQS).

**Trigger**: SQS (fed by SNS from DynamoDB Streams on `container_events` MODIFY events)  
**Handler**: `VisibilityS3Archiver implements RequestHandler<SQSEvent, Boolean>`

**Processing Flow**:

```
DynamoDB Stream (MODIFY on container_events)
  │ → SNS → SQS
  │
  ▼
VisibilityS3Archiver.handleRequest(SQSEvent)
  │
  ├─ 1. Parse SQS → SNS → DynamoDB Stream Record
  ├─ 2. Skip REMOVE and INSERT events (only process MODIFY)
  ├─ 3. Extract container event ID from stream record keys
  ├─ 4. Read full item from DynamoDB (consistent read)
  ├─ 5. Skip GPS events (statusEventCode = "GPS")
  ├─ 6. Deserialize nested JSON fields (containerEventSubmission, enrichedProperties, metaData)
  ├─ 7. Enrich transportation locations with resolved geography
  ├─ 8. Create S3 key: yyyy/MM/dd/HH/{containerEventId}.json
  └─ 9. Write JSON to S3 archive bucket
```

**AWS SDK v1 Usage**:
- `AmazonS3`, `AmazonDynamoDB`, `DynamoDB` (Document API)
- Direct DynamoDB Item-level reads (not DynamoDBMapper)

---

### 5.9 visibility-error-email (Lambda)

**Purpose**: Sends automated error report emails to subscribers. Runs on a schedule (CloudWatch Events).

**Trigger**: CloudWatch Scheduled Event  
**Handler**: `VisibilityErrorEmail.handleRequest()`

**Processing Flow**:

```
CloudWatch Schedule → Lambda
  │
  ▼
VisibilityErrorEmail.handleRequest()
  │
  ├─ 1. SubscriptionService.getSubscriptions()
  │     └─ Filter by contextCode == "REPORT"
  ├─ 2. For each matching subscription:
  │     ├─ If EDI ID is set → ErrorEmailService.sendEmailByEdiId()
  │     └─ If Company ID is set → ErrorEmailService.sendEmailByCompanyId()
  └─ 3. Log results
```

**Key Classes**:
- `VisibilityErrorEmail` — Lambda handler
- `SubscriptionService` — REST client to Network module subscription API
- `ErrorEmailService` — Email composition and sending
- `ParameterStoreResolver` — AWS SSM Parameter Store for secrets
- Uses Guice injection via `HandlerSupport.createInjector()`

---

### 5.10 visibility-pending-start (Lambda)

**Purpose**: Triggers the pending retry process by sending `PendingFilter` messages to the pending SQS queue. Runs on a schedule.

**Trigger**: CloudWatch Scheduled Event  
**Handler**: `VisibilityPendingStart.handleRequest(ScheduledEvent)`

**Processing Flow**:

```
CloudWatch Schedule → Lambda
  │
  ▼
VisibilityPendingStart.handleRequest()
  │
  ├─ 1. For days 1-7: sendPendingFilterToSqs(today - N days)
  │     └─ For each prefix (A-Z, 0-9): send PendingFilter(date, prefix) to SQS
  └─ 2. For weeks 2-4: sendPendingFilterToSqs(today - N*7 days)
        └─ Same prefix loop
```

This generates a fan-out of messages: `7 days × 36 prefixes + 3 weeks × 36 prefixes = 360 messages` to the pending SQS queue, which are then consumed by the `visibility-pending` Dropwizard service.

**AWS SDK v1 Usage**: `AmazonSQS` client for sending messages.

---

### 5.11 visibility-outbound-poller (Lambda)

**Purpose**: Polls the MySQL `OutboundThreshold` table to find Integration Profile Formats (IPFs) that are ready for batch outbound processing, and sends them to the outbound multi-transaction SQS queue.

**Trigger**: CloudWatch Scheduled Event  
**Handler**: `VisibilityOutboundPoller.handleRequest(ScheduledEvent)`

**Processing Flow**:

```
CloudWatch Schedule → Lambda
  │
  ▼
VisibilityOutboundPoller.handleRequest()
  │
  ├─ 1. Connect to MySQL (Aurora) via JDBC
  │     └─ Credentials from SSM Parameter Store
  ├─ 2. Query OutboundThreshold table:
  │     SELECT integrationProfileFormatId, transactionCount,
  │            lastExecutionDatetime, transactionsPerFile, timeLimitInMinutes
  │     FROM ContainerEvent.OutboundThreshold
  ├─ 3. For each row:
  │     └─ If transactionCount > 0 OR exceededExecutionPeriod:
  │         └─ Send OutboundThreshold JSON to SQS (outbound IPF queue)
  └─ 4. OutboundMultiTransactionProcessor consumes these messages
```

**AWS SDK v1 Usage**: `AmazonSQS` for sending, SSM `AWSSimpleSystemsManagement` for parameter resolution.  
**Database**: Direct JDBC to MySQL Aurora (not through DynamoDB).

---

## 6. Database & Storage Layer

### 6.1 DynamoDB Tables

| Table | Hash Key | Sort Key | Purpose | TTL |
|---|---|---|---|---|
| `{env}_container_events` | `id` (String, prefix `CE_`) | — | Core container event records | 400 days |
| `{env}_container_events_outbound` | `integrationProfileFormatId` (String) | `sequenceNumber` (String: `{timestamp}_{ceId}`) | Outbound transaction queue per IPF | 3 years |
| `{env}_container_events_pending` | `createDate` (String: `yyyy-MM-dd`) | `inboundContainerEventId` (String) | Unmatched events awaiting retry | 40 days |
| `{env}_CargoVisibilitySubscription` | `id` (String) | — | Cargo visibility subscriptions (Watermill/Shippeo subscription lifecycle) | Yes (expiresOn, epoch seconds) |

**DynamoDB Global Secondary Indexes (container_events)**:

| Index Name | Hash Key | Sort Key | Projection |
|---|---|---|---|
| `bkInttraReferenceNumber-equipmentIdentifier-index` | `bkInttraReferenceNumber` | `equipmentIdentifier` | KEYS_ONLY |
| `bookingNumber-index` | `bookingNumber` | — | KEYS_ONLY |
| `siInttraReferenceNumber-index` | `siInttraReferenceNumber` | — | KEYS_ONLY |
| `equipmentIdentifier-index` | `equipmentIdentifier` | — | KEYS_ONLY |
| `blNumber-index` | `blNumber` | — | KEYS_ONLY |

**DynamoDB Global Secondary Indexes (CargoVisibilitySubscription)**:

| Index Name | Hash Key | Sort Key | Projection |
|---|---|---|---|
| `bookingNumber-index` | `bookingNumber` | — | KEYS_ONLY |
| `subscriptionReference-index` | `subscriptionReference` | — | KEYS_ONLY |

> **Note**: The `watermill-publisher/watermill-cargo-visibility-subscription` module (outside visibility scope) accesses the same `CargoVisibilitySubscription` table with a different model class having additional GSIs: `bookingNumber-carrierScac-index` (Hash: carrierBookingNumber, Range: carrierScac), `billOfLading-carrierScac-index` (Hash: billOfLadingNumber, Range: carrierScac), and `subscriptionReference-index`.

### 6.2 MySQL (Aurora)

| Database | Table | Purpose | Used By |
|---|---|---|---|
| `ContainerEvent` | `OutboundThreshold` | Tracks per-IPF batch outbound thresholds (count, last execution, lock) | outbound, outbound-poller |

### 6.3 Oracle (Legacy)

| Schema | Table | Purpose | Used By |
|---|---|---|---|
| `inttra` | `ContainerEventSubscription` | Legacy subscription mappings | inbound (read-only) |

### 6.4 Elasticsearch

| Index | Purpose | Used By |
|---|---|---|
| Booking/Shipping Instruction index | Match container events to bookings | matcher, pending |

### 6.5 S3 Buckets

| Bucket | Purpose | Used By |
|---|---|---|
| Inbound workspace bucket | Store raw EDI/Watermill/ITV payloads | inbound, wm-inbound-processor, itv-gps-processor |
| Outbound bucket | Store generated GIS/EDI outbound files | outbound |
| Archive bucket | Long-term container event archives | s3-archiver |

---

## 7. AWS Services Usage

| AWS Service | SDK Version | Usage | Sub-Modules |
|---|---|---|---|
| **DynamoDB** | v1 (`DynamoDBMapper`) | Container events, outbound records, pending records, cargo visibility subscriptions | All Dropwizard services (incl. wm-inbound-processor for CargoVisibilitySubscription) |
| **DynamoDB Streams** | v1 (event models) | Trigger matcher on INSERT, trigger archiver on MODIFY | matcher, s3-archiver |
| **SQS** | v1 (`AmazonSQS`, `SQSClient`) | Inter-service messaging (all queues) | All services & lambdas |
| **SNS** | v1 (`SNSClient`) | DynamoDB stream fanout, event logging | commons (via SNSEventPublisher) |
| **S3** | v1 (`AmazonS3`) | Read/write EDI payloads, outbound files, archives | All services |
| **SES** | v2 (`SesClient`) | Email sending from inbound service | inbound |
| **SSM Parameter Store** | v1 | Secrets resolution in lambdas | outbound-poller, error-email |
| **Lambda** | v1 (runtime) | 4 lambda functions | s3-archiver, error-email, pending-start, outbound-poller |
| **CloudWatch Events** | — | Scheduled triggers for lambdas | pending-start, outbound-poller, error-email |

---

## 8. Network Services Integration

The visibility module heavily depends on the **Network module** REST APIs for reference data and configuration. These are accessed through HTTP clients defined in `visibility-commons`:

| Service | Network API Endpoint | Purpose | Client Class |
|---|---|---|---|
| Auth | `/auth` | OAuth token acquisition | `AuthClient` |
| Geography | `/network/reference/geography` | Location/port resolution | `GeographyService` |
| Geography Alias | `/network/geography/aliases` | Location alias resolution | `GeographyAliasService` |
| Participants | `/network/reference/participants` | Company/participant lookup | `NetworkParticipantService` |
| Participant Alias | `/network/participants/aliases` | Alias resolution | `ParticipantAliasService` |
| Subscription | `/network/subscription` | Outbound subscription config | `SubscriptionService` |
| Integration Profile | `/network/participant/integrationProfile` | Integration profile lookup | `IntegrationProfileService` |
| Integration Profile Format | `/network/participant/integrationProfile/format` | Format/delivery config | `IntegrationProfileFormatService` |
| Status Event Code | `/network/statuseventcode` | Valid status event codes | `StatusEventCodeService` |
| Container Type | `/network/containertype` | Container type reference data | `ContainerTypeService` |
| Format | (via IPF) | EDI format definitions | `FormatService` |
| Blacklist Email | `/network/blacklist-email` | Email blacklist check | `BlacklistEmailService` |

All network service calls are authenticated via OAuth tokens obtained from the Auth service. Service URLs are configured in Dropwizard YAML config files under `serviceDefinitions`.

---

## 9. Build & Deployment

### 9.1 Build Structure

All sub-modules are built from the parent `visibility/pom.xml` which declares them as `<modules>`. The commons version used is `1.R.01.021` (not the latest `1.0.22-SNAPSHOT`).

#### Dropwizard Services (Docker)

These use `maven-shade-plugin` to produce fat JARs and are containerized via Docker:

```bash
# Build example (from repo root):
mvn package -pl visibility/visibility-inbound --also-make

# The build.sh scripts run:
# 1. mvn package sonar:sonar (with Sonar analysis)
# 2. Move JAR to build_tmp/
# 3. Copy config YAMLs for each environment
# 4. Build Docker image from base OpenJRE image
```

| Sub-Module | Build Script | Output | Docker Base |
|---|---|---|---|
| `visibility-inbound` | `build.sh` | `visibility-inbound-1.0.jar` → Docker | `e2openjre11` |
| `visibility-matcher` | `build.sh` | `visibility-matcher-1.0.jar` → Docker | `e2openjre11` |
| `visibility-outbound` | `build.sh` | `visibility-outbound-1.0.jar` → Docker | `e2openjre11` |
| `visibility-pending` | `build.sh` | `visibility-pending-1.0.jar` → Docker | `e2openjre11` |
| `visibility-wm-inbound-processor` | `build.sh` | `visibility-wm-inbound-processor-1.0.jar` → Docker | `e2openjre11` |
| `visibility-itv-gps-processor` | `build.sh` | `visibility-itv-gps-processor-1.0.jar` → Docker | `e2openjre11` |

#### Lambda Functions (ZIP)

These use `maven-assembly-plugin` to produce deployment ZIPs and have CloudFormation scripts:

```bash
# Build example:
mvn package -pl visibility/visibility-s3-archiver --also-make

# The build.sh scripts run:
# 1. Package cfscripts.tar.gz (CloudFormation templates)
# 2. mvn package sonar:sonar
# 3. Move deployment ZIP to out/
```

| Sub-Module | Build Script | Output | CF Scripts |
|---|---|---|---|
| `visibility-s3-archiver` | `build.sh` | `visibility-s3-archiver-1.0-deployment_package.zip` | `cfscripts/` |
| `visibility-error-email` | `build.sh` | `visibility-error-email-1.0-deployment_package.zip` | `cfscripts/` |
| `visibility-pending-start` | `build.sh` | `visibility-pending-start-1.0-deployment_package.zip` | `cfscripts/` |
| `visibility-outbound-poller` | `build.sh` | `visibility-outbound-poller-1.0-deployment_package.zip` | `cfscripts/` |

### 9.2 Configuration Per Environment

Dropwizard services have environment-specific YAML configs in `conf/{env}/config.yaml` where `{env}` is one of: `int`, `qa`, `cvt`, `prod`. Secrets are resolved via AWS SSM Parameter Store using the pattern `${awsps:/path/to/secret}`.

---

## 10. Sub-Module Dependency Matrix

```
                     commons  inbound  matcher  outbound  pending  wm-inbound  itv-gps  s3-archiver  error-email  pending-start  outbound-poller
commons                 —       ←         ←        ←        ←         ←          ←          ←            ←             ←               ←
visibility-inbound      ✓       —                                     ⬡          ⬡
visibility-matcher      ✓                 —
visibility-outbound     ✓                          —
visibility-pending      ✓       ⬡         ⬡                 —
visibility-wm           ✓       ⬡                                     —
visibility-itv          ✓       ⬡                                                —
visibility-s3-archiver  ✓                                                                  —
visibility-error-email             (standalone Lambda, uses commons models)                              —
visibility-pending-start           (standalone Lambda, uses commons models)                                             —
visibility-outbound-poller         (standalone Lambda, uses commons models)                                                             —

✓ = direct Maven dependency
← = depended upon by
⬡ = code dependency (imports classes from other sub-module but may compile via transitive)
```

**Key dependency chains**:
- `visibility-pending` imports from both `visibility-matcher` (`AbstractMatcher`, `TransactionSearchService`, `IntegrationSubscriptionService`) and `visibility-inbound` (validator)
- `visibility-wm-inbound-processor` imports from `visibility-inbound` (`ContainerEventValidator`)
- `visibility-itv-gps-processor` imports from `visibility-inbound` (`ContainerEventValidator`)
- All Dropwizard services depend on `visibility-commons`

### Maven Dependency Graph (compile scope)

```
visibility-commons
  ├── com.inttra.mercury:commons:1.R.01.021
  ├── com.inttra.mercury:dynamo-client:1.R.01.021
  ├── com.inttra.mercury:booking:2.1.8.M
  ├── org.elasticsearch.client:elasticsearch-rest-high-level-client:6.8.13
  └── com.amazonaws:aws-lambda-java-events

visibility-inbound
  ├── visibility-commons
  ├── software.amazon.awssdk:ses (v2 — only SES)
  ├── com.oracle.database.jdbc:ojdbc11
  └── jakarta.mail:jakarta.mail-api

visibility-matcher
  ├── visibility-commons
  └── com.inttra.mercury:booking:2.1.8.M

visibility-outbound
  └── visibility-commons

visibility-pending
  └── visibility-commons (+ transitive matcher/inbound via source imports)

visibility-wm-inbound-processor
  └── visibility-commons (+ transitive inbound via source imports)

visibility-itv-gps-processor
  └── visibility-commons (+ transitive inbound via source imports)
```

---

## 11. Key Configuration

### 11.1 SQS Queues Used

| Queue Purpose | Config Key | Consumer | Producer |
|---|---|---|---|
| CE Validate (inbound EDI) | `inboundProcessorConfig.inboundSqsConfig.url` | `visibility-inbound` | External EDI pipeline |
| CE Matcher | `matcherProcessorConfig.inboundSqsConfig.url` | `visibility-matcher` | DynamoDB Stream → SNS → SQS |
| CE Outbound (single) | `outboundProcessorConfig.singleTransactionSqsProcessConfig` | `visibility-outbound` | `visibility-matcher` |
| CE Outbound (multi/IPF) | `outboundProcessorConfig.multiTransactionSqsProcessConfig` | `visibility-outbound` | `visibility-outbound-poller` |
| CE Pending | `pendingProcessorConfig.inboundSqsConfig.url` | `visibility-pending` | `visibility-pending-start` |
| WM Events | `wmEventProcessorConfig.inboundSqsConfig.url` | `visibility-wm-inbound-processor` | Watermill pipeline |
| GPS Events | `gpsEventProcessorConfig.inboundSqsConfig.url` | `visibility-itv-gps-processor` | ITV S3 → SNS → SQS |
| S3 Archiver | (Lambda trigger) | `visibility-s3-archiver` | DynamoDB Stream → SNS → SQS |

Each queue has a corresponding Dead Letter Queue (DLQ) for failed messages.

### 11.2 SQS Processing Configuration

All SQS consumers use the same `SqsMessageHandler` pattern:
- **messagesPerRead**: 10 (SQS long polling)
- **waitInSeconds**: 10 (SQS wait time)
- **threadPoolConfig**: Configurable threads and max queued tasks per processor
- **DLQ handling**: Failed messages are moved to DLQ unless explicitly flagged as retryable

---

## 12. Summary of AWS SDK v1 Usage

This section catalogs all direct AWS SDK v1 usages that will need to be migrated to cloud-sdk-api/cloud-sdk-aws during the upgrade.

### 12.1 By Category

| Category | AWS SDK v1 Classes | Locations |
|---|---|---|
| **DynamoDB** | `DynamoDBMapper`, `DynamoDBMapperConfig`, `DynamoDB` (Document API), `Table`, `GetItemSpec`, `Item`, `AttributeValue`, `ProvisionedThroughputExceededException`, `OperationType` | `ContainerEventDao`, `ContainerEventOutboundDao`, `ContainerEventPendingDao`, `ContainerTrackingEventDao`, `ContainerEventOutboundThresholdDao`, `CargoVisibilitySubscriptionDao`, `VisibilityS3Archiver` |
| **SQS** | `AmazonSQS`, `Message`, `SQSClient` (custom wrapper) | All processors (`InboundEdiProcessor`, `MatchingProcessor`, `OutboundSingleTransactionProcessor`, `OutboundMultiTransactionProcessor`, `PendingSqsProcessor`, `WMEventProcessor`, `GPSEventProcessor`), Lambda functions |
| **S3** | `AmazonS3`, `AmazonS3ClientBuilder`, `GetObjectRequest`, `PutObjectResult`, `S3Object`, `S3Event`, `S3EventNotification` | `S3WorkspaceService`, `VisibilityApplicationInjector`, `VisibilityS3Archiver`, `GPSEventProcessor` |
| **SNS** | `SNSClient` (custom wrapper), `SNSEvent.SNS` | `SNSMapper`, `SNSEventPublisher`, `MatchingProcessor`, `GPSEventProcessor`, `VisibilityS3Archiver` |
| **Lambda Events** | `DynamodbEvent.DynamodbStreamRecord`, `SQSEvent`, `SNSEvent`, `S3Event`, `ScheduledEvent` | Matcher, S3 Archiver, GPS processor, all Lambdas |
| **SSM** | `AWSSimpleSystemsManagement` | `VisibilityOutboundPoller.HandlerSupport`, `VisibilityErrorEmail.ParameterStoreResolver` |

### 12.2 Notable Exception: SES v2

The `visibility-inbound` module already uses **AWS SDK v2** for SES:
```java
import software.amazon.awssdk.services.ses.SesClient;
```
This is the only v2 usage in the entire visibility module. It was added directly rather than through `cloud-sdk-api`.

### 12.3 DynamoDB Access Pattern

All DynamoDB access goes through `DynamoDBCrudRepository` from the `dynamo-client` library (`com.inttra.mercury:dynamo-client:1.R.01.021`). This wraps `DynamoDBMapper` and provides:
- `query()`, `save()`, `update()`, `findById()`, `findAll()`, `queryWithSizeLimit()`
- Table prefix support via `DynamoDBMapperConfig` (environment-based table naming: `{env}_container_events`)
- CONSISTENT and EVENTUAL read behaviors

The S3 Archiver Lambda uses the DynamoDB **Document API** directly (`DynamoDB`, `Table`, `GetItemSpec`, `Item`) instead of `DynamoDBMapper`, as it was written independently from the shared DAO layer.

---

## Appendix A: Class Responsibility Summary

### Processors (StatusEventProcessor implementations)

| Class | Module | Input | Output |
|---|---|---|---|
| `InboundEdiProcessor` | inbound | SQS (EDI metadata) → S3 (EDI content) | DynamoDB (container_events) |
| `MatchingProcessor` | matcher | SQS (DynamoDB stream via SNS) | DynamoDB (container_events update), SQS (outbound) |
| `OutboundSingleTransactionProcessor` | outbound | SQS (outbound metadata) | DynamoDB (container_events_outbound), S3 (GIS file) |
| `OutboundMultiTransactionProcessor` | outbound | SQS (OutboundThreshold) | S3 (GIS file), MySQL (threshold update) |
| `PendingSqsProcessor` | pending | SQS (PendingFilter) | DynamoDB (container_events update), SQS (outbound) |
| `WMEventProcessor` | wm-inbound-processor | SQS (WM metadata) → S3 (WM payload) | DynamoDB (container_events) |
| `GPSEventProcessor` | itv-gps-processor | SQS (S3 event via SNS) → S3 (ITV file) | DynamoDB (container_events) |

### Lambda Handlers

| Class | Module | Trigger | Action |
|---|---|---|---|
| `VisibilityS3Archiver` | s3-archiver | SQS (DynamoDB stream MODIFY via SNS) | Archive JSON to S3 |
| `VisibilityErrorEmail` | error-email | CloudWatch Schedule | Send error report emails |
| `VisibilityPendingStart` | pending-start | CloudWatch Schedule | Send PendingFilter messages to SQS |
| `VisibilityOutboundPoller` | outbound-poller | CloudWatch Schedule | Poll MySQL → send IPF thresholds to SQS |

### DAO Classes

| Class | Table | Key Schema |
|---|---|---|
| `ContainerEventDao` | `{env}_container_events` | Hash: `id` |
| `ContainerEventOutboundDao` | `{env}_container_events_outbound` | Hash: `integrationProfileFormatId`, Sort: `sequenceNumber` |
| `ContainerEventPendingDao` | `{env}_container_events_pending` | Hash: `createDate`, Sort: `inboundContainerEventId` |
| `ContainerTrackingEventDao` | `{env}_container_tracking_events` | Hash: `id` + multiple GSIs |
| `CargoVisibilitySubscriptionDao` | `{env}_CargoVisibilitySubscription` | Hash: `id`, GSIs: `bookingNumber-index`, `subscriptionReference-index` |
| `BookingDao` | `booking_BookingDetail` | Hash: `bookingId`, Sort: `sequenceNumber` |
| `ContainerEventOutboundThresholdDao` | MySQL `ContainerEvent.OutboundThreshold` | PK: `integrationProfileFormatId` |
| `ContainerEventOutboundThresholdReadOnlyDao` | MySQL (read replica) `ContainerEvent.OutboundThreshold` | PK: `integrationProfileFormatId` |

> **Note**: `ContainerEventDao`, `ContainerEventOutboundDao`, `ContainerEventPendingDao`, `ContainerTrackingEventDao`, and `BookingDao` are in `visibility-commons`. `CargoVisibilitySubscriptionDao` is in `visibility-wm-inbound-processor`. All extend `DynamoDBCrudRepository` from `dynamo-client`.

---

## Appendix B: Common Pattern — StatusEventProcessor Lifecycle

All Dropwizard services follow the same pattern for managing SQS-consuming processors:

```java
// 1. Application registers processors via Guice Multibinder
Multibinder<StatusEventProcessor> processorBinder = 
    Multibinder.newSetBinder(binder(), StatusEventProcessor.class);
processorBinder.addBinding().to(MyProcessor.class);

// 2. Application startListeners() hook
Set<StatusEventProcessor> processors = injector.getInstance(Key.get(lit));
for (StatusEventProcessor processor : processors) {
    if (processor.isEnabled()) {
        StatusEventProcessorManagedHandler handler = 
            new StatusEventProcessorManagedHandler(processor);
        env.lifecycle().manage(handler);  // Dropwizard managed lifecycle
    }
}

// 3. Each processor delegates to SqsMessageHandler
// SqsMessageHandler runs a polling loop:
//   while (notStopped) {
//     messages = sqsClient.receiveMessage(url, 10, 10);
//     for (message : messages) {
//       threadPool.execute(() -> processor.process(message));
//     }
//   }

// 4. Error handling in SqsMessageHandler:
//   - Normal errors → move message to DLQ, delete from source
//   - DO_NOT_DELETE flag → leave message in source (auto-retry)
//   - DO_NO_SEND_TO_DLQ flag → don't send to DLQ
```

---

## Appendix C: External Module Dependencies

| External Module | Artifact | Used For |
|---|---|---|
| `mercury-services-commons` | `com.inttra.mercury:commons:1.R.01.021` | Base server framework (`InttraServer`), auth, database, messaging, cache |
| `dynamo-client` | `com.inttra.mercury:dynamo-client:1.R.01.021` | DynamoDB abstraction (`DynamoDBCrudRepository`, `DynamoDBModule`) |
| `booking` | `com.inttra.mercury:booking:2.1.8.M` | Cross-module booking data access, JSON utilities |

## Appendix D: Cross-Module DynamoDB Table Sharing

The `CargoVisibilitySubscription` DynamoDB table is accessed by **two separate modules** with different model classes:

| Module | Model Location | GSIs | Extra Fields |
|---|---|---|---|
| `visibility/visibility-wm-inbound-processor` | `com.inttra.mercury.cargo.visibility.model.CargoVisibilitySubscription` | `bookingNumber-index`, `subscriptionReference-index` | — |
| `watermill-publisher/watermill-cargo-visibility-subscription` | `com.inttra.mercury.cargo.visibility.model.CargoVisibilitySubscription` (same package, different module) | `bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index`, `subscriptionReference-index` | `carrierBookingNumber`, `billOfLadingNumber`, `serviceType`, `@DynamoDBIndexRangeKey` on `carrierScac` |

Both models share the same `@DynamoDBTable(tableName = "CargoVisibilitySubscription")` annotation and the same primary key (`id`). The watermill-publisher version has a more evolved schema with composite GSIs and additional fields. This is an important consideration during the AWS SDK 2.x upgrade — changes to the visibility-wm-inbound-processor model must remain compatible with items written by the watermill-publisher model.

---

*End of Document*
