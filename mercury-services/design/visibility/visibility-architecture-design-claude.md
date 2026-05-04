# Visibility Module — Architecture & Design Document

**Document version:** 1.0  
**Generated:** 2026-05-04  
**Author:** Claude Sonnet 4.6 (automated analysis)  
**Codebase root:** `c:\Users\arijit.kundu\projects\mercury-services\visibility`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [High-Level Architecture Diagram](#3-high-level-architecture-diagram)
4. [Submodule Breakdown](#4-submodule-breakdown)
5. [Key Classes Reference](#5-key-classes-reference)
6. [End-to-End Data Flow](#6-end-to-end-data-flow)
7. [AWS Lambda Function Designs](#7-aws-lambda-function-designs)
8. [SQS Queue Topology](#8-sqs-queue-topology)
9. [GPS Event Flow (ITV + Shippeo)](#9-gps-event-flow-itv--shippeo)
10. [Cargo Visibility Bulk Submission Flow](#10-cargo-visibility-bulk-submission-flow)
11. [Batching Logic Design](#11-batching-logic-design)
12. [Pending Retry Schedule Design](#12-pending-retry-schedule-design)
13. [DynamoDB Table Schemas](#13-dynamodb-table-schemas)
14. [REST API Summary](#14-rest-api-summary)
15. [Guice DI Module Wiring](#15-guice-di-module-wiring)
16. [Configuration Properties Reference](#16-configuration-properties-reference)
17. [Design Patterns Used](#17-design-patterns-used)

---

## 1. Executive Summary

The **Visibility** module of Mercury Services is a container-tracking and event-routing platform built on top of the INTTRA ocean freight network. It receives container status events from multiple inbound channels, matches them to known shipments (bookings, shipping instructions, bills of lading), stores them in a purpose-built multi-tier data store, and fans out enriched events to downstream customers via format-specific outbound pipelines.

### Core Responsibilities

| Responsibility | Description |
|---|---|
| **Inbound event ingestion** | Accepts EDI (IFTSTA / T315) events via SQS, REST API direct post, Shippeo GPS events via Watermill, ITV GPS events via S3/SNS/SQS, and CargoWise subscription data |
| **Booking matching** | Searches Elasticsearch indices (bookings, shipping instructions, BLs) to correlate container events with known transactions |
| **Pending retry** | Events that cannot be matched are queued in DynamoDB and retried on a 7-day daily + 28-day weekly schedule |
| **Outbound delivery** | Matched events are routed to each subscribed integration profile format via either legacy GIS (S3 file drop) or modern Cloud-Map transformer pipeline |
| **Cargo Visibility API** | Allows INTTRA network participants to submit carrier bookings for third-party GPS tracking through Shippeo |
| **Error email** | A scheduled Lambda discovers failed subscriptions and sends diagnostic emails |
| **Archive** | DynamoDB change-stream events are captured and written to S3 for long-term archival |

### Deployment Landscape

The module comprises **7 long-running Java services** (Dropwizard / AWS ECS containers) and **4 AWS Lambda functions**, all communicating via SQS queues, SNS topics, DynamoDB streams, and S3 objects.

---

## 2. Technology Stack

### Core Framework & Runtime

| Artifact | GroupId | Version | Role |
|---|---|---|---|
| Java | — | **17** | Language version (`maven.compiler.release=17`) |
| Dropwizard | io.dropwizard | **2.1.1** (parent pom) | HTTP framework for all long-running services |
| Google Guice | com.google.inject | **4.1.0** (parent pom) | Dependency injection |
| Lombok | org.projectlombok | **1.18.30** (parent pom) | Boilerplate reduction |

### AWS SDKs

| Artifact | GroupId | Version | Role |
|---|---|---|---|
| aws-lambda-java-core | com.amazonaws | **1.2.3** | Lambda handler interface |
| aws-lambda-java-events | com.amazonaws | **3.16.1** | SQS/SNS/DynamoDB/S3 event types |
| aws-java-sdk-dynamodb | com.amazonaws | (via commons) | DynamoDB mapper & document API |
| aws-java-sdk-s3 | com.amazonaws | (via commons) | S3 read/write |
| aws-java-sdk-sqs | com.amazonaws | (via commons) | SQS polling & publishing |
| ses (SDK v2) | software.amazon.awssdk | **2.42.28** | Email sending (SES v2) |

### Persistence

| Artifact | GroupId | Version | Role |
|---|---|---|---|
| ojdbc11 | com.oracle.database.jdbc | **23.26.0.0.0** | Oracle JDBC for legacy INTTRA DB |
| aws-mysql-jdbc | software.aws.rds | **1.1.15** | Aurora MySQL with RDS IAM auth |
| mysql-connector-j | com.mysql | **9.5.0** | Fallback MySQL connector |
| dynamo-client | com.inttra.mercury | **1.R.01.021** | Internal DynamoDB abstraction |
| elasticsearch-rest-high-level-client | org.elasticsearch.client | **6.8.13** | Elasticsearch search (booking matching) |

### Serialisation & Utilities

| Artifact | GroupId | Version | Role |
|---|---|---|---|
| jackson-databind | com.fasterxml.jackson.core | **2.18.1** | JSON serialisation |
| jackson-datatype-jsr310 | com.fasterxml.jackson.datatype | **2.18.1** | Java 8 date/time support |
| jackson-datatype-joda | com.fasterxml.jackson.datatype | **2.18.1** | Joda-time support |
| snakeyaml | org.yaml | **2.2** | YAML config parsing |
| jakarta.mail-api | jakarta.mail | **2.2.0-M1** | MIME mail API |
| angus-mail | org.eclipse.angus | **2.1.0-M1** | SMTP / SES integration |
| metrics-guice | com.palominolabs.metrics | **3.2.2** | Dropwizard metrics via Guice |
| swagger-annotations | io.swagger | **1.6.2** | REST API documentation |

### Build / Packaging

| Plugin | Version | Role |
|---|---|---|
| maven-compiler-plugin | **3.12.1** | Java 17 compilation |
| maven-shade-plugin | **3.5.1** | Fat-JAR for services |
| maven-assembly-plugin | **3.7.1** | Lambda deployment zip |
| maven-surefire-plugin | **3.5.2** | Unit test runner |
| jaxb2-maven-plugin | **3.1.0** | JAXB XSD → Java (visibility-commons) |
| swagger-maven-plugin (kong) | **3.1.7** | Swagger spec generation |

### Internal Libraries

| Artifact | GroupId | Version | Role |
|---|---|---|---|
| commons | com.inttra.mercury | **1.R.01.021** | Shared Dropwizard utilities, auth |
| booking | com.inttra.mercury | **2.1.8.M** | Booking model & JSON utilities |
| dynamo-client | com.inttra.mercury | **1.R.01.021** | DynamoDB repository abstractions |

### Test Stack

| Artifact | Version |
|---|---|
| junit-jupiter-api / engine / params | **6.1.0-M1** |
| mockito-core / mockito-junit-jupiter | **5.20.0** |
| assertj-core | **4.0.0-M1** |

---

## 3. High-Level Architecture Diagram

```
  EXTERNAL SOURCES                  VISIBILITY MODULE                              CONSUMERS
  ===============                   ================                               =========

  EDI Carriers                      ┌─────────────────────────────────────────┐
  (IFTSTA / T315)  ──SQS──────────► │  visibility-inbound                     │
                                    │  (Dropwizard service, port 8080)        │
  REST API clients ──HTTP POST────► │  - InboundEdiProcessor (SQS)           │
                                    │  - ContainerTrackingResource (REST)     │
  INTTRA network   ──HTTP GET/────► │  - CargoVisibilityResource (REST)       │
  participants      POST            │  - ContainerEventService                │
                                    │  - CargoVisibilityService               │
  CargoWise (CW)                    └───────────────┬─────────────────────────┘
  Subscriptions ──SQS──────────────────────────────►│
                    ┌──────────────────────────────────────────────────┐       │
                    │ visibility-wm-inbound-processor                   │ ◄─────┘
                    │ (Dropwizard service)                             │
                    │ - WMEventProcessor (SQS)                        │
                    │ - ShippeoContainerEventProcessor                 │
                    │ - CargoVisibilitySubscriptionProcessor           │
                    │ - CargoVisibilityEventProcessor                  │
                    └────────────────────┬─────────────────────────────┘

  ITV GPS         ──S3 Event──SNS──SQS►  ┌──────────────────────────────────┐
                                          │ visibility-itv-gps-processor     │
                                          │ (Dropwizard service)             │
                                          │ - GPSEventProcessor (SQS)        │
                                          │ - ITVGPSEventMapper              │
                                          └────────────────┬─────────────────┘

                     All three inbound paths write ContainerEvent to DynamoDB
                     DynamoDB stream ──SNS──► SQS ──► visibility-matcher
                                                         │
                                    ┌────────────────────┼─────────────────────────┐
                                    │ visibility-matcher  │                         │
                                    │ (Dropwizard service)│                         │
                                    │ - MatchingProcessor (SQS)                    │
                                    │ - TransactionSearchService (ES)              │
                                    │ - IntegrationSubscriptionService             │
                                    │   ┌─── matched? ───────────────────────────► ContainerEventOutbound (DynamoDB)
                                    │   └─── not matched? ────────────────────────► ContainerEventPending (DynamoDB)
                                    └──────────────────────────────────────────────┘

  EventBridge Cron ──Scheduled──►  ┌──────────────────────────────────────────┐
  (daily)                          │ VisibilityPendingStart (Lambda)          │
                                   │ Emits PendingFilter messages to SQS      │
                                   └──────────────────┬───────────────────────┘
                                                      │ SQS
                                   ┌──────────────────▼───────────────────────┐
                                   │ visibility-pending                        │
                                   │ (Dropwizard service)                     │
                                   │ - PendingSqsProcessor                    │
                                   │ - Bulk ES match + re-outbound            │
                                   └──────────────────────────────────────────┘

  EventBridge Cron ──Scheduled──►  ┌──────────────────────────────────────────┐
  (every N min)                    │ VisibilityOutboundPoller (Lambda)        │
                                   │ Queries MySQL OutboundThreshold table    │
                                   │ Sends ready IPF records to SQS          │
                                   └──────────────────┬───────────────────────┘
                                                      │ SQS (ce_outbound + ce_outbound_ipf)
                                   ┌──────────────────▼───────────────────────┐
                                   │ visibility-outbound                       │
                                   │ (Dropwizard service)                     │
                                   │ - OutboundSingleTransactionProcessor     │
                                   │ - OutboundMultiTransactionProcessor      │
                                   │ - OutboundGenerator → GIS (S3)          │
                                   │                    → Transformer (SQS)  │
                                   └──────────────────────────────────────────┘

  DynamoDB stream ──SNS──► SQS ─►  ┌──────────────────────────────────────────┐
  (MODIFY events)                  │ VisibilityS3Archiver (Lambda)            │
                                   │ Reads full record from DynamoDB          │
                                   │ Writes enriched JSON to S3 archive       │
                                   └──────────────────────────────────────────┘

  EventBridge Cron ──Scheduled──►  ┌──────────────────────────────────────────┐
  (periodic)                       │ VisibilityErrorEmail (Lambda)            │
                                   │ Queries Network Services subscriptions   │
                                   │ Sends error-report emails via SES        │
                                   └──────────────────────────────────────────┘
```

---

## 4. Submodule Breakdown

| # | Submodule | Maven Artifact | Deployment | Port | Purpose |
|---|---|---|---|---|---|
| 1 | `visibility-commons` | `visibility-commons:1.0` | Shared library (JAR) | — | Shared models, persistence DAOs, network-services clients, config base classes, DynamoDB table definitions, SQS/ES abstractions |
| 2 | `visibility-inbound` | `visibility-inbound:1.0` | **Long-running service** (ECS) | 8080 | EDI ingestion via SQS (IFTSTA, T315), REST container-tracking API, REST cargo-visibility bulk submission API, Oracle subscription queries |
| 3 | `visibility-wm-inbound-processor` | `visibility-wm-inbound-processor:1.0` | **Long-running service** (ECS) | 8080 | Watermill SQS consumer — routes Shippeo GPS, CargoWise subscription, and CargoWise event messages |
| 4 | `visibility-itv-gps-processor` | `visibility-itv-gps-processor:1.0` | **Long-running service** (ECS) | 8080 | ITV GPS event SQS consumer — reads S3-backed ITVEvent JSON, maps to ContainerEventSubmission |
| 5 | `visibility-matcher` | `visibility-matcher:1.0` | **Long-running service** (ECS) | 8080 | DynamoDB-stream/SNS/SQS consumer — runs Elasticsearch booking matching, routes to outbound or pending |
| 6 | `visibility-outbound` | `visibility-outbound:1.0` | **Long-running service** (ECS) | 8080 | Two SQS consumers: single-transaction outbound per event, multi-transaction batch outbound per IPF; writes to GIS S3 or Transformer SQS |
| 7 | `visibility-pending` | `visibility-pending:1.0` | **Long-running service** (ECS) | 8080 | SQS consumer for retry schedule — bulk re-matches pending container events via ES scroll |
| 8 | `visibility-pending-start` | `visibility-pending-start:1.0` | **AWS Lambda** | — | EventBridge-triggered Lambda that calculates daily + weekly retry date windows and sends `PendingFilter` messages to SQS |
| 9 | `visibility-s3-archiver` | `visibility-s3-archiver:1.0` | **AWS Lambda** | — | SQS-triggered Lambda consuming DynamoDB stream notifications — archives MODIFY-type container events to S3 |
| 10 | `visibility-error-email` | `visibility-error-email:1.0` | **AWS Lambda** | — | EventBridge-triggered Lambda — discovers error-subscriptions from Network Services and sends SES emails |
| 11 | `visibility-outbound-poller` | `visibility-outbound-poller:1.0` | **AWS Lambda** | — | EventBridge-triggered Lambda — polls `ContainerEvent.OutboundThreshold` MySQL table and sends ready IPF IDs to SQS |

---

## 5. Key Classes Reference

### visibility-commons

| Class | Package | Role |
|---|---|---|
| `ContainerEvent` | `…common.model.containerEvent` | DynamoDB entity: hash key `id`, embedded `ContainerEventSubmission`, `ContainerEventEnrichedProperties`, `MetaData`; 5 GSIs |
| `ContainerEventOutbound` | `…common.model.containerEvent` | DynamoDB entity: hash key `integrationProfileFormatId`, sort key `sequenceNumber` (auto-gen); holds subscription + GIS details |
| `ContainerEventPending` | `…common.model.containerEvent` | DynamoDB entity: hash key `createDate` (ISO date string), sort key `inboundContainerEventId` |
| `ContainerEventSubmission` | `…common.model.containerEvent` | Value object embedded in ContainerEvent: event details, location, transportation, references |
| `ContainerEventEnrichedProperties` | `…common.model.containerEvent` | Enrichment: matchedBookings, matchedBILLs, recipientCompanyIds, requestedRecipients, statusEventCode, geography |
| `OutboundThreshold` | `…common.model.containerEvent` | MySQL row model: IPF ID, transactionCount, lastExecutionDatetime, transactionsPerFile, timeLimitInMinutes, locked |
| `ContainerEventDao` | `…common.persistence` | DynamoDB CRUD for `container_events` |
| `ContainerEventOutboundDao` | `…common.persistence` | DynamoDB CRUD for `container_events_outbound` |
| `ContainerEventPendingDao` | `…common.persistence` | DynamoDB CRUD for `container_events_pending` |
| `ContainerEventOutboundThresholdDao` | `…common.persistence` | MySQL read/write for `OutboundThreshold` (lock/unlock) |
| `ContainerEventOutboundThresholdReadOnlyDao` | `…common.persistence` | MySQL read-only access to `OutboundThreshold` |
| `SQSConfig` | `…common.config` | SQS URL, DLQ URL, messagesPerRead (1–10), waitInSeconds |
| `VisibilityApplicationConfig` | `…common.config` | Base Dropwizard config: DynamoDbConfig, ESConfiguration, EventLoggingConfig |
| `VisibilityApplicationInjector` | `…common.config` | Abstract Guice module: binds S3, SNS EventPublisher, RandomGenerator, Clock |

### visibility-inbound

| Class | Package | Role |
|---|---|---|
| `VisibilityInboundApplication` | `…inbound` | Dropwizard main; bootstraps Guice, registers resources and processors |
| `ContainerTrackingResource` | `…inbound.resource` | JAX-RS: `GET /track`, `GET /v1.2/track`, `POST /v1.2/event`, `GET /v1.2/event/{id}` |
| `CargoVisibilityResource` | `…inbound.resource` | JAX-RS: `POST /cargo-visibility/submit/json`, `POST /cargo-visibility/submit/csv` |
| `VisibilityResource` | `…inbound.resource` | JAX-RS: `GET /containers` (deprecated) |
| `SupportResource` | `…inbound.resource` | Internal support endpoints (migration, rollback) |
| `InboundEdiProcessor` | `…inbound.processor` | SQS consumer for `ce_validate` queue — validates & saves ContainerEvents |
| `ContainerEventService` | `…inbound.service` | Orchestrates ContainerEvent creation, DynamoDB save |
| `CargoVisibilityService` | `…inbound.service` | Bulk JSON/CSV submission logic — parallel ≥10 or sequential, carrier preload cache, SQS publish |
| `ContainerTrackingSearchService` | `…inbound.service` | Elasticsearch-backed container search (v1 / v1.2 API) |
| `EmailService` | `…inbound.service` | SES email via `EmailSender` wrapper |
| `IFTSTAMapper` | `…inbound.processor.mapper` | EDI IFTSTA → ContainerEventSubmission |
| `T315Mapper` | `…inbound.processor.mapper` | EDI T315 → ContainerEventSubmission |
| `InboundTransformerFactory` | `…inbound.processor.customTransformer` | Selects carrier-specific transformer (EVG, WWA, WHLC, USAID) |
| `ContainerEventValidator` | `…inbound.processor.validator` | Validates submission fields, resolves geography, sets enriched properties |
| `ContainerEventTableDao` | `…inbound.persistence.dynamodb` | DynamoDB read for inbound ContainerEvent lookups |
| `ContainerEventSubscriptionDao` | `…inbound.persistence.oracle` | Oracle DB queries for legacy subscription data |
| `VisibilityInboundApplicationInjector` | `…inbound.config` | Guice module for inbound: binds EDI mappers, transformers, SES client, InboundEdiProcessor |

### visibility-matcher

| Class | Package | Role |
|---|---|---|
| `VisibilityMatcherApplication` | `…matcher` | Dropwizard main |
| `MatchingProcessor` | `…matcher.processor` | SQS consumer for `ce_match` — drives ES matching, dispatches outbound/pending |
| `AbstractMatcher` | `…matcher.processor` | Shared matching/outbound logic used by both `MatchingProcessor` and `PendingSqsProcessor` |
| `TransactionSearchService` | `…matcher.processor.elasticsearch` | ES bulk queries: single match + bulk scroll for pending retry |
| `TransactionScrollSearch` | `…matcher.processor.elasticsearch` | ES scroll API wrapper |
| `IntegrationSubscriptionService` | `…matcher.processor` | Resolves outbound subscriptions for matched recipients |
| `VisibilityMatcherApplicationInjector` | `…matcher.config` | Guice: binds `MatchingProcessor` |

### visibility-outbound

| Class | Package | Role |
|---|---|---|
| `VisibilityOutboundApplication` | `…outbound` | Dropwizard main |
| `OutboundSingleTransactionProcessor` | `…outbound.processor` | SQS consumer for `ce_outbound` — processes one event per message |
| `OutboundMultiTransactionProcessor` | `…outbound.processor` | SQS consumer for `ce_outbound_ipf` — batch threshold logic (lock/unlock) |
| `OutboundGenerator` | `…outbound.processor.gis` | Builds GIS transactions and routes to S3 (GIS) or SQS (Cloud-Map transformer) |
| `GISTransaction` | `…outbound.processor.gis` | Constructs GIS file segments (T315/IFTSTA format strings) |
| `OutboundEnrichmentUtil` | `…outbound.processor` | Enriches outbound payload for Cloud-Map transformer |
| `VisibilityOutboundApplicationInjector` | `…outbound.config` | Guice: binds both processors, provides named `IPFService` |

### visibility-pending

| Class | Package | Role |
|---|---|---|
| `PendingSqsProcessor` | `…pending.processor` | SQS consumer for `ce_pending` — reads `PendingFilter`, queries DynamoDB, bulk-matches via ES, deletes matched records |

### visibility-pending-start (Lambda)

| Class | Package | Role |
|---|---|---|
| `VisibilityPendingStart` | `…lambda` | `handleRequest(ScheduledEvent)` — computes daily (days 1–7) and weekly (weeks 2–4) windows, sends 256 PendingFilter messages (16 hex-prefix pairs × date) |
| `HandlerSupport` | `…lambda` | SQS client factory, env variable reader, prefix list generator (`ce:00`–`ce:ff`) |

### visibility-s3-archiver (Lambda)

| Class | Package | Role |
|---|---|---|
| `VisibilityS3Archiver` | `…lambda` | `RequestHandler<SQSEvent, Boolean>` — extracts DynamoDB MODIFY record from SNS wrapper, reads full item from DynamoDB, enriches location, writes to S3 with path `YYYY/MM/DD/HH/{id}` |
| `HandlerSupport` | `…lambda` | DynamoDB/S3 client factory, env var reader |

### visibility-error-email (Lambda)

| Class | Package | Role |
|---|---|---|
| `VisibilityErrorEmail` | `…lambda` | `handleRequest()` — gets subscriptions from Network Services, filters by `REPORT` context code, sends email per EDI ID or INTTRA company ID |
| `SubscriptionService` | `…lambda.networkservices.subscription` | HTTP client to Network Services subscription API |
| `ErrorEmailService` | `…lambda.networkservices.erroremail` | HTTP client to generate error email report |
| `ParameterStoreResolver` | `…lambda.util` | AWS SSM Parameter Store lookup |

### visibility-outbound-poller (Lambda)

| Class | Package | Role |
|---|---|---|
| `VisibilityOutboundPoller` | `…lambda` | `handleRequest(ScheduledEvent)` — queries `ContainerEvent.OutboundThreshold` via JDBC, selects rows with `transactionCount > 0` or `lastExecution > 30 min`, sends to SQS in parallel |

### visibility-wm-inbound-processor

| Class | Package | Role |
|---|---|---|
| `VisibilityWMEventApplication` | `…wm` | Dropwizard main |
| `WMEventProcessor` | `…wm.processor` | SQS consumer — dispatches to typed sub-processors via `WatermillMessageType` map |
| `ShippeoContainerEventProcessor` | `…wm.processor` | Processes Shippeo GPS container events → ContainerEventSubmission → DynamoDB |
| `CargoVisibilitySubscriptionProcessor` | `…wm.processor` | Processes CargoWise subscription payloads |
| `CargoVisibilityEventProcessor` | `…wm.processor` | Processes CargoWise event payloads |
| `CargoVisibilitySubscriptionDao` | `…wm.dao` | DynamoDB DAO for cargo visibility subscription records |
| `VisibilityWMEventApplicationInjector` | `…wm.config` | Guice: provides `Set<MessageTypeProcessor>`, ObjectMapper with Joda/Java8 time |

### visibility-itv-gps-processor

| Class | Package | Role |
|---|---|---|
| `VisibilityGPSEventApplication` | `…itv` | Dropwizard main |
| `GPSEventProcessor` | `…itv.processor` | SQS consumer — unwraps SNS→S3 event, reads ITVEvent JSON from S3, maps each upsert in parallel |
| `ITVGPSEventMapper` | `…itv.processor` | Maps ITV `Upsert` model → `ContainerEventSubmission` |

---

## 6. End-to-End Data Flow

### 6A. Standard EDI Container Event Flow

```
  1. INBOUND
  ──────────
  EDI Carrier/System
       │
       │  (SNS wrapping DynamoDB-style notification OR raw SQS message)
       ▼
  SQS: inttra2_{env}_sqs_ce_validate
       │
       ▼
  visibility-inbound :: InboundEdiProcessor.process(Message)
       │
       ├─ Parse SQS body → retrieve MetaData (bucket/file) from S3
       ├─ Parse EDI payload (IFTSTA via IFTSTAMapper or T315 via T315Mapper)
       ├─ Apply carrier-specific transformer (EVG / WWA / WHLC / USAID)
       ├─ ContainerEventValidator.validate()
       │     ├─ Validate equipment, event code, dates
       │     ├─ Resolve geography via Network Services
       │     └─ Enrich ContainerEventEnrichedProperties
       └─ ContainerEventDao.save(containerEvent)
              │
              ▼
       DynamoDB: {env}_container_events
              │
              ▼  (DynamoDB Streams → SNS topic → SQS)
  2. MATCHING
  ──────────
  SQS: inttra2_{env}_sqs_ce_match
       │
       ▼
  visibility-matcher :: MatchingProcessor.process(Message)
       │
       ├─ Extract ContainerEvent ID from DynamoDB INSERT stream record
       ├─ ContainerEventDao.getSingleById(id)
       ├─ Skip GPS_EVENT_CODE events (GPS handled separately)
       │
       ├─ TransactionSearchService.findMatchingTransactions(containerEvent)
       │     ├─ Query ES: bookingNumber-index → matched bookings
       │     ├─ Query ES: siInttraReferenceNumber-index → matched SIs
       │     ├─ Query ES: blNumber-index → matched BLs
       │     └─ Populate enrichedProperties.matchedBookings/SIs/BLs
       │         + recipientCompanyIds
       │
       ├─ ContainerEventDao.save(containerEvent)   ← save enriched version
       │
       ├─ IntegrationSubscriptionService.getOutboundSubscriptionsByParticipant(requestedRecipients)
       ├─ IntegrationSubscriptionService.getOutboundSubscriptionsByCompanyId(recipientCompanyIds)
       │
       ├─ AbstractMatcher.processOutbound(containerEvent, subscriptions, ...)
       │     └─ For each Subscription:
       │           ├─ Build ContainerEventOutbound record
       │           └─ ContainerEventOutboundDao.save()  → DynamoDB: container_events_outbound
       │                (also sends to SQS: ce_outbound for single-tx processing)
       │
       └─ if (!foundMatchedTransactions):
             ContainerEventPendingDao.save(containerEvent.hashKey)
                   → DynamoDB: container_events_pending

  3. OUTBOUND (Single Transaction)
  ────────────────────────────────
  SQS: inttra2_{env}_sqs_ce_outbound
       │
       ▼
  visibility-outbound :: OutboundSingleTransactionProcessor.process(Message)
       │
       ├─ Deserialize ContainerEventOutbound from SQS
       ├─ OutboundGenerator.createAndSendSingleTransaction(outboundEvent, sqsMessage)
       │     ├─ Check IPF transformer prefix:
       │     │     ├─ if CLOUD_* → sendToTransformer() → put S3 + send SQS (transformer queue)
       │     │     └─ else       → sendToGIS()          → GISTransaction.build() → put S3 (GIS bucket)
       └─ EventLogHandler.logEvent(...)

  4. OUTBOUND (Multi-Transaction / Batched by IPF)
  ──────────────────────────────────────────────────
  SQS: inttra2_{env}_sqs_ce_outbound_ipf
       │  (message body: OutboundThreshold JSON with IPF ID + threshold data)
       ▼
  visibility-outbound :: OutboundMultiTransactionProcessor.process(Message)
       │
       ├─ ContainerEventOutboundThresholdReadOnlyDao.getOutboundThreshold(ipfId)
       ├─ Check crossedTimeThreshold OR crossedTransactionThreshold
       │
       ├─ if ready:
       │     ContainerEventOutboundThresholdDao.lockThreshold(ipfId, now)
       │     OutboundGenerator.createAndSendBatchTransactions(ipfId, transactionsPerFile, lastDate)
       │           ├─ Query DynamoDB: getUnprocessedTransactions(ipfId, lastDate)
       │           ├─ Filter: excludeTransaction (carrier exclusion list, non-INTTRA booking)
       │           ├─ Partition into batches of `transactionsPerFile`
       │           └─ For each batch: createAndSendTransactions()
       │     ContainerEventOutboundThresholdDao.unlockThreshold(ipfId, count, now, lastTs)
       │
       └─ if locked > MAX_MINUTES_BETWEEN_EXECUTIONS (120):
             forcedUnlockThreshold()

```

---

## 7. AWS Lambda Function Designs

### 7.1 VisibilityPendingStart

```
  Trigger: AWS EventBridge Scheduled Rule (cron, daily)
  Handler: VisibilityPendingStart.handleRequest(ScheduledEvent)
  Runtime: Java 17
  Package: visibility-pending-start-1.0.jar (assembly zip)

  Input:  ScheduledEvent (EventBridge)
  Output: void (side effect: SQS messages)

  Environment Variables:
    pendingSqsUrl  → URL of inttra2_{env}_sqs_ce_pending

  Logic:
  ┌─────────────────────────────────────────────────────────┐
  │ LocalDate now = LocalDate.now(UTC)                      │
  │                                                         │
  │ Daily window (last 7 days):                             │
  │   for day in [1..7]:                                    │
  │     sendPendingFilterToSqs(now.minusDays(day))          │
  │                                                         │
  │ Weekly window (weeks 2, 3, 4 = 14, 21, 28 days ago):   │
  │   for week in [2..4]:                                   │
  │     sendPendingFilterToSqs(now.minusDays(week * 7))     │
  │                                                         │
  │ For each date × 256 hex prefixes (ce:00..ce:ff):        │
  │   sqsClient.sendMessage(PendingFilter{date, prefix})    │
  └─────────────────────────────────────────────────────────┘

  Total SQS messages per invocation:
    (7 + 3) dates × 256 prefixes = 2,560 SQS messages
```

### 7.2 VisibilityErrorEmail

```
  Trigger: AWS EventBridge Scheduled Rule (cron, configurable)
  Handler: VisibilityErrorEmail.handleRequest()
  Runtime: Java 17
  Package: visibility-error-email assembly zip

  Environment Variables:
    environment           → e.g. "int" / "qa" / "pr"
    (SSM paths resolved at startup via ParameterStoreResolver)

  DI: Guice injector via HandlerSupport.createInjector()
    → VisibilityErrorEmailModule
      → SubscriptionService, ErrorEmailService, config

  Logic:
  ┌─────────────────────────────────────────────────────────┐
  │ subscriptions = subscriptionService.getSubscriptions()  │
  │   .filter(s -> s.contextCode == "REPORT")              │
  │                                                         │
  │ for each subscription:                                  │
  │   if ediId is blank AND inttraCompanyId != null:        │
  │     errorEmailService.sendEmailByCompanyId(companyId)   │
  │   else if ediId is not blank:                           │
  │     errorEmailService.sendEmailByEdiId(ediId)           │
  └─────────────────────────────────────────────────────────┘

  Output: SES emails sent to subscribed parties
```

### 7.3 VisibilityS3Archiver

```
  Trigger: SQS Event (backed by DynamoDB Stream → SNS → SQS)
  Handler: VisibilityS3Archiver.handleRequest(SQSEvent, Context)
  Runtime: Java 17

  Environment Variables:
    s3ArchiveBucket      → archive S3 bucket name
    dynamoDbEnvironment  → e.g. "inttra2_qa"

  Logic per SQSMessage:
  ┌─────────────────────────────────────────────────────────┐
  │ Unwrap: SQSMessage.body → SNS.message                   │
  │       → DynamodbStreamRecord                            │
  │                                                         │
  │ Guard clauses (return true = silent skip):              │
  │   - REMOVE or INSERT event type → skip                  │
  │   - Missing keys / missing primary key "id" → skip      │
  │   - GPS_EVENT_CODE status → skip                        │
  │                                                         │
  │ id = keys["id"]                                         │
  │ item = dynamoDB.getTable("{env}_container_events")      │
  │               .getItem("id", id)  [consistent read]    │
  │                                                         │
  │ Enrich: merge resolvedLocation into transportationLocations│
  │         remove bulk enrichedProperties.transportationLocationGeography│
  │                                                         │
  │ s3Key = YYYY/MM/DD/HH/{id}                              │
  │ s3Client.putObject(archiveBucket, s3Key, json)          │
  └─────────────────────────────────────────────────────────┘

  S3 key pattern: {year}/{month}/{day}/{hour}/{container-event-id}
  e.g. 2026/05/04/14/ce:3f7a...
```

### 7.4 VisibilityOutboundPoller

```
  Trigger: AWS EventBridge Scheduled Rule (every ~5 min)
  Handler: VisibilityOutboundPoller.handleRequest(ScheduledEvent)
  Runtime: Java 17

  Environment Variables:
    outboundIpfSqsUrl    → URL of inttra2_{env}_sqs_ce_outbound_ipf
    dbUrl                → jdbc:mysql:aws://... ContainerEvent DB
    dbSsmRootPath        → SSM path prefix for /user and /password
    inttraLogLevel       → logback level string

  SQL Query:
  ┌─────────────────────────────────────────────────────────┐
  │ SELECT integrationProfileFormatId, transactionCount,   │
  │        lastExecutionDatetime,                           │
  │        lastTransactionCreationDatetime, locked,         │
  │        transactionsPerFile, timeLimitInMinutes          │
  │ FROM ContainerEvent.OutboundThreshold                   │
  └─────────────────────────────────────────────────────────┘

  Selection criteria per row:
    transactionCount > 0  OR  minutesSinceLastExecution > 30

  Retry logic: Aurora failover (SQLState "08S02") — up to 5 retries

  Output: For each selected row:
    sqsClient.sendMessage(outboundIpfSqsUrl, JSON(OutboundThreshold))

  Processing: parallelStream() — all eligible IPF rows sent concurrently
```

---

## 8. SQS Queue Topology

```
  QUEUE NAME (QA)                           PRODUCER                      CONSUMER
  ═══════════════════════════════════════════════════════════════════════════════════

  inttra2_qa_sqs_ce_validate               External EDI systems          visibility-inbound
                                                                         (InboundEdiProcessor)
  inttra2_qa_sqs_ce_validate_dlq           [dead letters from above]     Manual reprocess

  inttra2_qa_sqs_ce_match                  DynamoDB Stream→SNS fanout    visibility-matcher
                                                                         (MatchingProcessor)
  inttra2_qa_sqs_ce_match_dlq             [dead letters]                Manual reprocess

  inttra2_qa_sqs_ce_pending               VisibilityPendingStart(Lambda) visibility-pending
                                                                         (PendingSqsProcessor)
  inttra2_qa_sqs_ce_pending_dlq           [dead letters]                Manual reprocess

  inttra2_qa_sqs_ce_outbound              visibility-matcher             visibility-outbound
                                          (AbstractMatcher.processOutbound)(OutboundSingleTransactionProcessor)
  inttra2_qa_sqs_ce_outbound_dlq          [dead letters]                Manual reprocess

  inttra2_qa_sqs_ce_outbound_ipf          VisibilityOutboundPoller(Lambda)visibility-outbound
                                                                         (OutboundMultiTransactionProcessor)
  inttra2_qa_sqs_ce_outbound_ipf_dlq      [dead letters]                Manual reprocess

  inttra2_qa_sqs_transformer_ce           visibility-outbound            External transformer
                                          (OutboundGenerator)            service (Cloud-Map)

  inttra2_qa_sqs_watermill_itv_gps        ITV GPS system                visibility-itv-gps-processor
                                                                         (GPSEventProcessor)
  inttra2_qa_sqs_watermill_itv_gps_dlq    [dead letters]                Manual reprocess

  inttra2_qa_sqs_ce_wm_inbound            Watermill / Shippeo            visibility-wm-inbound-processor
                                                                         (WMEventProcessor: Shippeo events)
  inttra2_qa_sqs_ce_wm_inbound_dlq        [dead letters]                Manual reprocess

  inttra2_qa_sqs_ce_cw_subscription_inbound CargoWise / Watermill        visibility-wm-inbound-processor
                                                                         (WMEventProcessor: CW subscriptions)
  inttra2_qa_sqs_ce_cw_subscription_inbound_dlq [dead letters]          Manual reprocess

  inttra2_qa_sqs_cargo_visibility_subscription_watermill
                                          CargoVisibilityService (inbound)visibility-wm-inbound-processor
                                                                         (CargoVisibilitySubscriptionProcessor)

  inttra2_qa_sqs_pi_statusevents         visibility-inbound              Partner Integrator service
  inttra2_qa_sqs_pi_statusevents_dlq     [dead letters]                  Manual reprocess


  SNS TOPICS
  ══════════
  inttra2_qa_sns_event_ce                 All visibility services         Event tracking / audit log consumers
  inttra2_qa_sns_event (legacy)           visibility-inbound (inbound-only)Legacy consumer


  DLQ RELATIONSHIPS
  ══════════════════
  Every SQS queue has a paired DLQ (suffix _dlq).
  On ProvisionedThroughputExceededException or RecoverableException:
    → Message is NOT sent to DLQ and NOT deleted → automatic re-delivery
  On all other exceptions:
    → Message IS sent to DLQ and deleted from main queue
  Forced unlock: if OutboundThreshold locked > (timeLimitInMinutes + 120 min),
    forcedUnlockThreshold() resets the lock.
```

---

## 9. GPS Event Flow (ITV + Shippeo)

### 9A. ITV GPS Event Flow

```
  ITV Provider
       │
       │ Upload ITVEvent JSON file
       ▼
  S3 Bucket (ITV workspace)
       │
       │ S3 Create Event Notification
       ▼
  SNS Topic (S3 event notification)
       │
       ▼
  SQS: inttra2_{env}_sqs_watermill_itv_gps
       │
       ▼
  visibility-itv-gps-processor :: GPSEventProcessor.process(Message)
       │
       ├─ Unwrap: SQS.body → SNS.message → S3EventNotification
       ├─ s3WorkspaceService.getEncodedContent(bucket, key)
       ├─ Deserialize → ITVEvent
       │
       └─ For each Upsert in itvEvent.getUpserts() [parallelStream]:
             ITVGPSEventMapper.createContainerEventSubmission(upsert)
               ├─ Map shipmentUnit → equipment (container number)
               ├─ Map transportLeg → transportation details
               ├─ Map geoCoordinates → location
               └─ Set statusEventCode = GPS_EVENT_CODE
             ContainerEventValidator.validate(submission)
             ContainerEventDao.save(containerEvent)

  ITVEvent model:
    messageId: String
    upserts: List<Upsert>
      primaryKey, shipmentUnit, transportLeg, carrier,
      mainParty, geoCoordinates, auditDetails

  GPS events are tagged with status code GPS_EVENT_CODE.
  The MatchingProcessor explicitly SKIPS GPS-tagged events
  (they do not go through the booking-match / outbound pipeline).
  The S3Archiver also skips GPS events.
```

### 9B. Shippeo GPS Event Flow

```
  Shippeo Provider (Premium GPS provider, ownerNetworkParticipateId: 5305414)
       │
       │ Shippeo event message via Watermill
       ▼
  SQS: inttra2_{env}_sqs_ce_wm_inbound
       │
       ▼
  visibility-wm-inbound-processor :: WMEventProcessor.process(Message)
       │
       ├─ Parse MetaData from SQS body
       ├─ Retrieve payload from S3 (bucket/fileName from MetaData)
       ├─ Determine WatermillMessageType from MetaData.projections["messageType"]
       │     Default: SHIPPEO_CONTAINER_EVENT
       │
       └─ Dispatch to ShippeoContainerEventProcessor.transformAndProcess(payload, metaData)
             ├─ Parse Shippeo container event JSON
             ├─ Map to ContainerEventSubmission
             ├─ ContainerEventValidator.validate()
             └─ ContainerEventDao.save()

  WatermillMessageType enum values:
    SHIPPEO_CONTAINER_EVENT     → ShippeoContainerEventProcessor
    CARGO_VISIBILITY_SUBSCRIPTION → CargoVisibilitySubscriptionProcessor
    CARGO_VISIBILITY_EVENT       → CargoVisibilityEventProcessor
```

---

## 10. Cargo Visibility Bulk Submission Flow

The `CargoVisibilityService` handles both JSON bulk and CSV bulk submissions with identical logic, differentiated only by the parsing step.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  POST /visibility/cargo-visibility/submit/json                  │
  │  POST /visibility/cargo-visibility/submit/csv                   │
  └───────────────────────────┬─────────────────────────────────────┘
                              │ CargoVisibilityResource → CargoVisibilityService
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 1. Generate rootWorkflowId (UUID)                              │
  │ 2. Upload raw request to S3 workspace                          │
  │    bucket: {s3WorkspaceConfig.bucket}                          │
  │    key: {rootWorkflowId}/cargo_visibility_submission_{id}.json │
  │ 3. Create MetaData (rootWorkflowId, bucket, fileName, now)     │
  │ 4. validator.validatePermission(actor, metaData)               │
  │    → Checks actor's company has cargo-visibility permission    │
  │ 5. Parse CSV if CSV submission (CsvParserUtil.parseFromBytes)  │
  └───────────────────────────┬─────────────────────────────────────┘
                              │
                              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 6. Carrier preload (batch optimisation)                        │
  │    Collect unique SCAC codes from all requests                 │
  │    For each unique SCAC: validator.validateAndGetCarrier(scac) │
  │    Build Map<String, NetworkParticipant> carrierCache          │
  │    (Reduces N HTTP calls to M unique carriers)                 │
  └───────────────────────────┬─────────────────────────────────────┘
                              │
              ┌───────────────┴──────────────┐
              │  requests.size() >= 10?       │
              │                               │
         YES  ▼                         NO   ▼
  ┌────────────────────┐        ┌────────────────────────┐
  │ PARALLEL PROCESSING │        │ SEQUENTIAL PROCESSING   │
  │ CompletableFuture  │        │ for loop               │
  │ per request        │        │                        │
  │ ExecutorService    │        │                        │
  │ (20 threads)       │        │                        │
  └────────┬───────────┘        └───────────┬────────────┘
           │                                │
           └──────────────┬─────────────────┘
                          │ Per request:
                          ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ For each CargoVisibilityRequest:                               │
  │   a. validator.validateRequest(request)                        │
  │      → carrier SCAC not null, booking or BoL required          │
  │   b. Look up carrier from carrierCache (or re-validate)        │
  │   c. buildSubscription(request, carrier, actor):               │
  │         CargoVisibilitySubscription {                           │
  │           carrierName, carrierInttraId, carrierScac,           │
  │           originUNLOC, destinationUNLOC,                       │
  │           carrierBookingNumber, billOfLadingNumber,             │
  │           state=SUBMITTED, type=CUSTOMER,                      │
  │           references=[BookingNumber, BillOfLadingNumber],       │
  │           enableLocationTracking=false,                         │
  │           requestedRecipients={actor.companyId}                │
  │         }                                                       │
  │   d. s3WorkspaceService.putObject(bucket, fileName, subscription JSON)│
  │   e. sqsClient.sendMessage(cargoVisibilitySubscriptionQueue, metaData JSON)│
  │   f. Return CargoVisibilityResponse {status=ACCEPTED, ...}     │
  └─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ Aggregate results:                                              │
  │   JSON: always status=SUCCESS, summary message                  │
  │   CSV:  status=SUCCESS if all accepted, else PARTIAL_SUCCESS   │
  │   Return CargoVisibilityBatchResponse { items, status, message }│
  └─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
  SQS: inttra2_{env}_sqs_cargo_visibility_subscription_watermill
       │
       ▼
  visibility-wm-inbound-processor :: WMEventProcessor
       → CargoVisibilitySubscriptionProcessor
         (processes CargoVisibilitySubscription into tracking subscription in DB)
```

**Parallelism thresholds (hardcoded constants):**

| Constant | Value | Meaning |
|---|---|---|
| `PARALLEL_PROCESSING_THRESHOLD` | **10** | Requests ≥ 10 → parallel mode |
| `THREAD_POOL_SIZE` | **20** | Fixed thread pool for `CompletableFuture` |

---

## 11. Batching Logic Design

### 11A. OutboundThreshold Model

The `OutboundThreshold` entity stored in MySQL `ContainerEvent.OutboundThreshold` controls when a batch file is generated for each Integration Profile Format (IPF):

| Column | Type | Meaning |
|---|---|---|
| `integrationProfileFormatId` | INT (PK) | Unique identifier for a customer's delivery format |
| `transactionCount` | INT | Pending transactions accumulated since last flush |
| `lastExecutionDatetime` | BIGINT (epoch ms) | Timestamp of last batch generation |
| `lastTransactionCreationDatetime` | BIGINT (epoch ms) | Timestamp of most recent outbound transaction |
| `locked` | INT (0/1) | Mutex: 1 = currently being processed |
| `transactionsPerFile` | INT | Maximum transactions per generated file |
| `timeLimitInMinutes` | INT | Maximum age before forced flush |

### 11B. Batch Trigger Logic

```
  VisibilityOutboundPoller (Lambda, every ~5 min):
  ──────────────────────────────────────────────────
  SELECT all rows from OutboundThreshold
  Filter: transactionCount > 0 OR minutesSinceLastExecution > 30
  Send selected rows to SQS: ce_outbound_ipf

  OutboundMultiTransactionProcessor (visibility-outbound service):
  ────────────────────────────────────────────────────────────────
  For each SQS message (OutboundThreshold):

    minutesSinceLastProcessed = ceil((now - lastExecutionDatetime) / 60s)
    crossedTimeThreshold      = minutesSinceLastProcessed >= timeLimitInMinutes
    crossedTransactionThreshold = transactionCount >= transactionsPerFile

    if (crossedTimeThreshold OR crossedTransactionThreshold):
      if lockThreshold(ipfId, now):
        results = OutboundGenerator.createAndSendBatchTransactions(
                    ipfId, transactionsPerFile, lastTransactionCreationDatetime)
        unlockThreshold(ipfId, results.count, now, results.lastTimestamp)
      else:
        if minutesSinceLastProcessed > (timeLimitInMinutes + 120):
          # Stale lock — force unlock
          forcedUnlockThreshold(ipfId, lastExecutionDatetime, now)
```

### 11C. Batch File Generation

```
  OutboundGenerator.createAndSendBatchTransactions(ipfId, batchSize, lastDate):
    transactions = ContainerEventOutboundDao.getUnprocessedTransactions(ipfId, lastDate)
    qualifiedEvents = transactions.stream()
                        .map(tx → ContainerEventOutboundMetaData{tx, inboundEvent})
                        .filter(!excludeTransaction)

    batches = Lists.partition(qualifiedEvents, batchSize)

    for each batch:
      ipf = IntegrationProfileFormatService.getIntegrationProfileFormat(ipfId)
      if ipf.transformer.startsWith("CLOUD_"):
        → sendToTransformer(): put S3 + send SQS (transformer queue)
      else:
        → sendToGIS(): GISTransaction.build() each event, join with "\n", put S3 (GIS bucket)

    return OutboundTransactionResults { processedCount, lastTransactionCreateTimestamp }
```

**Exclusion rules (per transaction):**

| Rule | Logic |
|---|---|
| No preferences defined | Exclude |
| SCAC in `excludedCarrierList` preference | Exclude |
| `sendOnlyInttraBooking=true` AND all matched bookings are non-INTTRA | Exclude |

---

## 12. Pending Retry Schedule Design

### 12A. Schedule Windows

When `VisibilityPendingStart` Lambda fires, it generates `PendingFilter` SQS messages covering two overlapping retry windows:

```
  Today = D

  Daily window (recent events, 7 days):
  ┌────┬────┬────┬────┬────┬────┬────┐
  │D-1 │D-2 │D-3 │D-4 │D-5 │D-6 │D-7 │
  └────┴────┴────┴────┴────┴────┴────┘

  Weekly window (older events, weeks 2-4):
  ┌──────┬──────┬──────┐
  │D-14  │D-21  │D-28  │
  └──────┴──────┴──────┘

  Note: Day D-7 is shared (daily day 7 == week 1).
  Days D-8 through D-13 are NOT retried (gap by design).
```

### 12B. Prefix Partitioning

Each date is split into **256 partitions** using the 2-character hex suffix of the ContainerEvent primary key (`ce:00` to `ce:ff`):

```java
// PREFIX_LIST generation (HandlerSupport.java)
PREFIX = ["0","1","2","3","4","5","6","7","8","9","a","b","c","d","e","f"]
PREFIX_LIST = PREFIX.flatMap(first -> PREFIX.map(second -> "ce:" + first + second))
// Result: ["ce:00", "ce:01", ..., "ce:ff"]  (256 entries)
```

Total messages per Lambda invocation: **10 dates × 256 prefixes = 2,560 SQS messages**

### 12C. Retry Processing (PendingSqsProcessor)

```
  For each PendingFilter{processDate, prefix}:
    1. containerEventPendingDao.getPendingTransactionsByDate(processDate, prefix)
       → DynamoDB query: hashKey=processDate, sortKey BEGINS_WITH prefix
    2. Group into batches of elasticsearchRequestLimit (50) events
    3. parallelStream().forEach(batch):
         transactionSearchService.bulkMatchTransactions(batch.containerEvents)
         for each matched:
           containerEventDao.save(enrichedContainerEvent)
           integrationSubscriptionService.getOutboundSubscriptionsByCompanyId(recipients)
           processOutbound(containerEvent, subscriptions)
           containerEventPendingDao.delete(pendingRecord)
           eventLogHandler.logEvent(...)
```

---

## 13. DynamoDB Table Schemas

### 13A. container_events (primary event store)

```
  Table name: {env}_container_events
  Billing mode: Provisioned (readThroughput=25, writeThroughput=200)

  Primary Key:
    Hash Key:  id  (String)  — format: "ce:{uuid}"

  Attributes:
    id                   String  Hash Key
    containerEventSubmission  String  (JSON-serialised ContainerEventSubmission)
    enrichedProperties   String  (JSON-serialised ContainerEventEnrichedProperties)
    metaData             String  (JSON-serialised MetaData)
    expiresOn            Number  (epoch seconds, TTL attribute)
    lastModifiedDateUtc  String  (ISO-8601 OffsetDateTime)
    createdDate          String  (ISO-8601 OffsetDateTime)
    bookingNumber        String  (uppercase)
    blNumber             String  (uppercase, bill of lading)
    equipmentIdentifier  String  (uppercase, container number)
    bkInttraReferenceNumber  String
    siInttraReferenceNumber  String

  Global Secondary Indexes (KEYS_ONLY projection):
  ┌────────────────────────────────────────────────────────────────┐
  │ Index Name                              Hash Key    Sort Key  │
  │ bkInttraReferenceNumber-equipmentIdentifier-index             │
  │                              bkInttraReferenceNumber equipmentIdentifier│
  │ bookingNumber-index          bookingNumber           —        │
  │ siInttraReferenceNumber-index siInttraReferenceNumber —       │
  │ equipmentIdentifier-index   equipmentIdentifier     —        │
  │ blNumber-index              blNumber                —        │
  └────────────────────────────────────────────────────────────────┘
  Each GSI: readThroughput=10, writeThroughput=40

  DynamoDB Streams: ENABLED (NEW_AND_OLD_IMAGES)
  Stream consumers:
    → SNS → SQS ce_match    (MatchingProcessor)
    → SNS → SQS archiver    (VisibilityS3Archiver Lambda)
```

### 13B. container_events_outbound (outbound queue)

```
  Table name: {env}_container_events_outbound
  Billing mode: Provisioned (readThroughput=25, writeThroughput=200)

  Primary Key:
    Hash Key:  integrationProfileFormatId  (String)
    Sort Key:  sequenceNumber              (String, auto-generated)
               Format: "{epochMillis}_{random}"

  Attributes:
    integrationProfileFormatId  String  Hash Key (integer as string)
    sequenceNumber              String  Sort Key
    inboundContainerEventId     String  FK → container_events.id
    subscription                String  (JSON-serialised Subscription)
    gisOutboundDetails          String  (JSON-serialised GISOutboundDetails)
    expiresOn                   Number  (epoch seconds, TTL)

  No GSIs.
  Usage: queried by IPF ID + date range (getUnprocessedTransactions)
```

### 13C. container_events_pending (unmatched events)

```
  Table name: {env}_container_events_pending
  Billing mode: Provisioned (readThroughput=50, writeThroughput=50)

  Primary Key:
    Hash Key:  createDate               (String)  — "YYYY-MM-DD"
    Sort Key:  inboundContainerEventId  (String)  — "ce:{uuid}"

  Attributes:
    createDate               String  Hash Key
    inboundContainerEventId  String  Sort Key
    expiresOn                Number  (epoch seconds, TTL)

  Queried with: hashKey=date, sortKey BEGINS_WITH "ce:{hexPrefix}"
  This enables the 256-partition retry pattern.
```

### 13D. MySQL: ContainerEvent.OutboundThreshold

```
  Database: ContainerEvent (Aurora MySQL)
  Table: OutboundThreshold

  Schema (inferred from code):
  ┌──────────────────────────────────────────────────────────────┐
  │ integrationProfileFormatId  INT         PK                   │
  │ transactionCount            INT         pending tx count      │
  │ lastExecutionDatetime       BIGINT      epoch ms last flush  │
  │ lastTransactionCreationDatetime BIGINT  epoch ms last tx     │
  │ locked                      INT (0/1)  processing mutex      │
  │ transactionsPerFile         INT         batch size config     │
  │ timeLimitInMinutes          INT         time-based flush cfg  │
  └──────────────────────────────────────────────────────────────┘

  Operations:
    getOutboundThreshold(ipfId)   → SELECT by PK
    lockThreshold(ipfId, now)     → conditional UPDATE SET locked=1, lastExecutionDatetime=now
    unlockThreshold(ipfId, ...)   → UPDATE locked=0, transactionCount -= processed, lastExecutionDatetime=now
    forcedUnlockThreshold(...)    → forced unlock when stale > (timeLimitInMinutes + 120 min)
```

### 13E. Oracle: INTTRA Core DB (Legacy)

```
  JDBC URL: jdbc:oracle:thin:@10.1.37.22:1521/qa.nj.inttra.com
  Used by: visibility-inbound (ContainerEventSubscriptionDao)

  Queried for: ContainerEventSubscription (legacy INTTRA booking subscriptions)
  Mapper: ContainerEventSubscriptionMapper, ContainerEventSubscriptionSqlBuilder

  Note: This is a read-only legacy integration. The Oracle DB is the INTTRA
  Core system. Visibility queries it to resolve subscription information for
  legacy EDI integration profiles.
```

---

## 14. REST API Summary

Base path: `/visibility`  
Service: `visibility-inbound`  
Auth: OAuth Bearer token (validated via `/auth/validate` Network Services endpoint)

### Container Tracking (v1, deprecated)

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/visibility/containers` | Any authenticated | Search container events by `inttra_reference`, `bill_of_lading`, `booking_number`, `equipment_id`, or `broad_search_key` — **deprecated** |

### Container Tracking v1 API

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/visibility/track` | Any | Search by `inttra_booking_reference`, `carrier_booking_reference`, `bill_of_lading_number`, or `equipment_reference` — returns `List<Container>` (v1 model) |
| GET | `/visibility/track/{broad_search_key}` | Any | Broad search across all indexes — returns v1 Container list |

### Container Tracking v1.2 API

| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/visibility/v1.2/track` | Any | Same as v1 track but returns enriched external `Container` model (v1.2) |
| GET | `/visibility/v1.2/track/{broad_search_key}` | Any | Broad search — v1.2 model |
| POST | `/visibility/v1.2/event` | NETWORK_USER, NETWORK_ADMIN | Submit a `ContainerEventSubmission` directly; sets channel=API, provider=companyId |
| GET | `/visibility/v1.2/event/{id}` | NETWORK_USER, NETWORK_ADMIN | Retrieve container events by internal ID (hidden, for support) |

### Cargo Visibility API

| Method | Path | Roles | Consumes | Description |
|---|---|---|---|---|
| POST | `/visibility/cargo-visibility/submit/json` | NETWORK_USER, NETWORK_ADMIN | `application/json` | Bulk JSON submission of `List<CargoVisibilityRequest>` |
| POST | `/visibility/cargo-visibility/submit/csv` | NETWORK_USER, NETWORK_ADMIN | `multipart/form-data` | CSV file upload — columns: `carrier_scac`, `booking_number`, `bill_of_lading_number`, optionally `start_location_unloc`, `end_location_unloc` |

### CargoVisibilityRequest Model

```json
{
  "carrier_scac": "MAEU",
  "booking_number": "BKG123456",
  "bill_of_lading_number": "BL789012",
  "start_location_unloc": "USNYC",
  "end_location_unloc": "DEHAM"
}
```

### CargoVisibilityBatchResponse Model

```json
{
  "status": "SUCCESS | PARTIAL_SUCCESS | ERROR",
  "message": "N of M were successfully processed.",
  "items": [
    {
      "status": "ACCEPTED | REJECTED",
      "message": "Shipment was accepted for processing.",
      "carrier_scac": "MAEU",
      "booking_number": "BKG123456",
      "bill_of_lading_number": "BL789012"
    }
  ]
}
```

### Support API

| Method | Path | Description |
|---|---|---|
| POST | `/visibility/support/...` | Migration and rollback operations (SupportResource — internal use) |

---

## 15. Guice DI Module Wiring

### Base Module: VisibilityApplicationInjector (abstract)

All service injectors extend this abstract Guice module.

```
  VisibilityApplicationInjector (AbstractModule)
  ├─ bind(RandomGenerator)       → new RandomGenerator()
  ├─ bind(Clock)                 → Clock.systemUTC()
  ├─ @Provides AmazonS3          → AmazonS3ClientBuilder (retry policy: 3 retries, 500-5000ms jitter)
  ├─ @Provides EventPublisher    → SNSEventPublisher(snsTopicArn) or EmptyEventPublisher if disabled
  ├─ bindNetworkServices(...)    → @Named("auth"), @Named("geography"), etc.
  └─ bindJestClient(...)         → JestModule(ESConfiguration)
```

### visibility-inbound: VisibilityInboundApplicationInjector

```
  extends VisibilityApplicationInjector
  ├─ super.configure()
  ├─ bindNetworkServices(config.getServiceDefinitions())
  ├─ bindJestClient(esConfiguration)
  ├─ bind(EventLoggingConfig)          → config.getEventLoggingConfig()
  ├─ bind(InboundProcessorConfig)      → config.getInboundProcessorConfig()
  │
  ├─ Multibinder<InboundToSubmissionMapper>:
  │    addBinding → IFTSTAMapper
  │    addBinding → T315Mapper
  │
  ├─ Multibinder<StatusEventProcessor>:
  │    addBinding → InboundEdiProcessor
  │
  ├─ MapBinder<String, InboundTransformer>:
  │    "USAIDGrossWeightTransformer" → USAIDGrossWeightTransformer
  │    "WWACarrierTransformer"       → WWACarrierTransformer
  │    "WHLCStatusTransformer"       → WHLCStatusTransformer
  │    "EVGCarrierTransformer"       → EVGCarrierTransformer
  │
  └─ bind(SesClient)                   → SesClient.create()
```

### visibility-matcher: VisibilityMatcherApplicationInjector

```
  extends VisibilityApplicationInjector
  ├─ bindNetworkServices, bindJestClient, bind(EventLoggingConfig)
  ├─ bind(MatcherProcessorConfig)       → config.getMatcherProcessorConfig()
  └─ Multibinder<StatusEventProcessor>:
       addBinding → MatchingProcessor
```

### visibility-outbound: VisibilityOutboundApplicationInjector

```
  extends VisibilityApplicationInjector
  ├─ bindNetworkServices, bindJestClient, bind(EventLoggingConfig)
  ├─ bind(OutboundProcessorConfig)      → config.getOutboundProcessorConfig()
  │
  ├─ Multibinder<StatusEventProcessor>:
  │    addBinding → OutboundMultiTransactionProcessor
  │    addBinding → OutboundSingleTransactionProcessor
  │
  └─ @Provides @Named("IPFService") IntegrationProfileFormatService
       → IntegrationProfileFormatServiceForOutboundImpl
         (overrides base to use outbound-specific IPF fetch logic)
```

### visibility-pending: VisibilityPendingApplicationInjector

```
  extends VisibilityApplicationInjector
  ├─ bindNetworkServices, bindJestClient, bind(EventLoggingConfig)
  ├─ bind(PendingProcessorConfig)       → config.getPendingProcessorConfig()
  └─ Multibinder<StatusEventProcessor>:
       addBinding → PendingSqsProcessor
```

### visibility-wm-inbound-processor: VisibilityWMEventApplicationInjector

```
  extends VisibilityApplicationInjector
  ├─ bindNetworkServices, bind(EventLoggingConfig)
  ├─ bind(WMEventProcessorConfig)       → config.getWmEventProcessorConfig()
  ├─ bind(VisibilityWMEventApplicationConfig) → config
  │
  ├─ Multibinder<StatusEventProcessor>:
  │    addBinding → WMEventProcessor
  │
  ├─ @Provides @Singleton ObjectMapper:
  │    → Jackson with JodaModule + JavaTimeModule + LongDateDeserializer
  │    → ACCEPT_CASE_INSENSITIVE_PROPERTIES, !FAIL_ON_UNKNOWN_PROPERTIES
  │
  └─ @Provides @Singleton Set<MessageTypeProcessor>:
       → ShippeoContainerEventProcessor(validator, dao, mapper, participantService, config)
       → CargoVisibilitySubscriptionProcessor(mapper, subscriptionDao)
       → CargoVisibilityEventProcessor(mapper, validator, dao, subscriptionDao)
```

### visibility-itv-gps-processor: VisibilityGPSEventApplicationInjector

```
  extends VisibilityApplicationInjector
  ├─ bindNetworkServices, bind(EventLoggingConfig)
  ├─ bind(GPSEventProcessorConfig)      → config.getGpsEventProcessorConfig()
  └─ Multibinder<StatusEventProcessor>:
       addBinding → GPSEventProcessor
```

### visibility-error-email: VisibilityErrorEmailModule

```
  (Lambda — Guice used but not a Dropwizard service)
  ├─ bind(VisibilityErrorEmailConfig)   → loaded from YAML in classpath
  ├─ bind(SubscriptionService)          → HTTP client to NS subscription endpoint
  └─ bind(ErrorEmailService)            → HTTP client to NS error-email endpoint
```

---

## 16. Configuration Properties Reference

### Common Properties (all Dropwizard services)

| Key | Type | Example | Description |
|---|---|---|---|
| `server.rootPath` | String | `/visibility` | JAX-RS root path |
| `server.applicationConnectors[0].port` | Int | `8080` | HTTP port |
| `server.adminConnectors[0].port` | Int | `8081` | Dropwizard admin port |
| `dynamoDbConfig.environment` | String | `inttra2_qa` | DynamoDB table name prefix |
| `dynamoDbTableCreationCommandConfig` | List | — | Table provisioning settings |
| `eventLoggingConfig.snsEventTopicArn` | String | `arn:aws:sns:...` | SNS topic for event audit log |
| `eventLoggingConfig.enabled` | Boolean | `true` | Enable/disable event logging |
| `esConfiguration.endpointUrl` | String | `https://search-...` | Elasticsearch endpoint URL |
| `esConfiguration.region` | String | `us-east-1` | AWS region for ES signing |
| `jerseyClient.*` | — | — | HTTP client pool settings (32–128 threads) |
| `serviceDefinitions` | List | — | Network Services URL and credentials |
| `securityResources.*` | — | — | Auth validation URIs |

### visibility-inbound Specific

| Key | Example | Description |
|---|---|---|
| `inttraDatabase.*` | Oracle JDBC | Legacy INTTRA Oracle DB connection |
| `database.*` | Aurora MySQL writer | ContainerEvent MySQL DB (read/write) |
| `readOnlyDatabase.*` | Aurora MySQL reader | ContainerEvent MySQL DB (read-only) |
| `inboundProcessorConfig.enabled` | `true` | Enable InboundEdiProcessor |
| `inboundProcessorConfig.threadPoolConfig.threads` | `10` | SQS consumer thread count |
| `inboundProcessorConfig.inboundSqsConfig.url` | SQS URL | `ce_validate` queue |
| `inboundProcessorConfig.inboundSqsConfig.dlqUrl` | SQS URL | `ce_validate_dlq` queue |
| `inboundProcessorConfig.outboundSqsConfig.url` | SQS URL | `ce_outbound` queue |
| `inboundProcessorConfig.piSqsConfig.url` | SQS URL | `pi_statusevents` queue |
| `esTrackingConfig.endpointUrl` | ES URL | Transaction tracking ES cluster |
| `esTrackingConfig.index` | `txtrack-event-*` | TX tracking index pattern |
| `esTrackingConfig.maxResultSize` | `1000` | Max ES result window |
| `emailSenderConfig.sourceEmail` | `no-reply@...` | SES from address |
| `emailSenderConfig.internalEmails` | List | Internal alert recipients |
| `s3WorkspaceConfig.bucket` | `inttra2-qa-workspace` | S3 workspace bucket |
| `cargoVisibilityConfig.cargoVisibilitySubscriptionQueue` | SQS URL | Cargo visibility subscription queue |

### visibility-matcher Specific

| Key | Example | Description |
|---|---|---|
| `matcherProcessorConfig.enabled` | `true` | Enable MatchingProcessor |
| `matcherProcessorConfig.threadPoolConfig.threads` | `10` | SQS consumer threads |
| `matcherProcessorConfig.inboundSqsConfig.url` | SQS URL | `ce_match` queue |
| `matcherProcessorConfig.pendingSqsConfig.url` | SQS URL | `ce_pending` queue |
| `matcherProcessorConfig.outboundSqsConfig.url` | SQS URL | `ce_outbound` queue |

### visibility-outbound Specific

| Key | Example | Description |
|---|---|---|
| `outboundProcessorConfig.enabled` | `true` | Enable outbound processors |
| `outboundProcessorConfig.outboundS3Bucket` | `inttra2-qa-workspace` | Transformer S3 bucket |
| `outboundProcessorConfig.outboundS3BucketGIS` | `inttra2-qa-gis-delivery` | GIS S3 delivery bucket |
| `outboundProcessorConfig.outboundS3path` | `app/ob/315_IFTSTA_STAGE` | GIS S3 key prefix |
| `outboundProcessorConfig.outboundTransformerQueue` | SQS URL | `sqs_transformer_ce` queue |
| `outboundProcessorConfig.singleTransactionSqsProcessConfig.sqsConfig.url` | SQS URL | `ce_outbound` |
| `outboundProcessorConfig.multiTransactionSqsProcessConfig.sqsConfig.url` | SQS URL | `ce_outbound_ipf` |
| `outboundProcessorConfig.singleTransactionSqsProcessConfig.sqsThreadPoolConfig.threads` | `15` | Single-tx threads |
| `outboundProcessorConfig.multiTransactionSqsProcessConfig.sqsThreadPoolConfig.threads` | `15` | Multi-tx threads |

### visibility-pending Specific

| Key | Example | Description |
|---|---|---|
| `pendingProcessorConfig.enabled` | `true` | Enable PendingSqsProcessor |
| `pendingProcessorConfig.elasticsearchRequestLimit` | `50` | Max container events per ES bulk query |
| `pendingProcessorConfig.sqsThreadPoolConfig.threads` | `2` | Low thread count (large batch scanning) |
| `pendingProcessorConfig.inboundSqsConfig.url` | SQS URL | `ce_pending` queue |
| `pendingProcessorConfig.outboundSqsConfig.url` | SQS URL | `ce_outbound` queue |

### visibility-itv-gps-processor Specific

| Key | Example | Description |
|---|---|---|
| `gpsEventProcessorConfig.enabled` | `true` | Enable GPSEventProcessor |
| `gpsEventProcessorConfig.threadPoolConfig.threads` | `8` | SQS consumer threads |
| `gpsEventProcessorConfig.inboundSqsConfig.url` | SQS URL | `sqs_watermill_itv_gps` |

### visibility-wm-inbound-processor Specific

| Key | Example | Description |
|---|---|---|
| `wmEventProcessorConfig.enabled` | `true` | Enable WMEventProcessor |
| `wmEventProcessorConfig.componentName` | `visibility-wm-inbound-processor` | Log component name |
| `wmEventProcessorConfig.threadPoolConfig.threads` | `8` | SQS consumer threads |
| `wmEventProcessorConfig.inboundSqsConfig.url` | SQS URL | `sqs_ce_wm_inbound` or `sqs_ce_cw_subscription_inbound` |
| `premiumEventProviders[0].name` | `SHIPPEO` | Premium provider identifier |
| `premiumEventProviders[0].ownerNetworkParticipateId` | `5305414` | Network participant ID for Shippeo |

### Lambda Environment Variables

| Lambda | Variable | Description |
|---|---|---|
| VisibilityPendingStart | `pendingSqsUrl` | Target SQS queue for PendingFilter messages |
| VisibilityS3Archiver | `s3ArchiveBucket` | S3 bucket for archived container events |
| VisibilityS3Archiver | `dynamoDbEnvironment` | DynamoDB table prefix (e.g. `inttra2_qa`) |
| VisibilityOutboundPoller | `outboundIpfSqsUrl` | Target SQS for IPF threshold messages |
| VisibilityOutboundPoller | `dbUrl` | JDBC connection string for Aurora MySQL |
| VisibilityOutboundPoller | `dbSsmRootPath` | SSM path for `/user` and `/password` |
| VisibilityOutboundPoller | `inttraLogLevel` | Logback level (e.g. `INFO`) |
| VisibilityErrorEmail | `environment` | Deployment environment (int/qa/pr) |

### SSM Parameter Store Naming Convention

All secrets are resolved at runtime from AWS Systems Manager Parameter Store:

```
  Pattern: ${awsps:/inttra2/{env}/mercuryservices/{path}}

  Examples:
    /inttra2/qa/mercuryservices/db/user
    /inttra2/qa/mercuryservices/db/password
    /inttra2/qa/mercuryservices/ssr/inttradb/user
    /inttra2/qa/mercuryservices/ssr/inttradb/password
    /inttra2/qa/visibility/mercuryservices/authclientsecret
```

---

## 17. Design Patterns Used

### Structural Patterns

| Pattern | Location | How Used |
|---|---|---|
| **Module (Guice AbstractModule)** | All injectors | Each submodule has a dedicated Guice module that binds its specific processors and configs. The abstract `VisibilityApplicationInjector` encapsulates shared bindings (S3, SNS, Clock). |
| **Multibinder (Guice)** | All injectors | `Multibinder<StatusEventProcessor>` registers one or more SQS processor implementations per service. At startup, the application iterates the set and calls `start()` on each enabled processor. |
| **MapBinder (Guice)** | VisibilityInboundApplicationInjector | Maps carrier SCAC strings to carrier-specific `InboundTransformer` implementations. |
| **Named Binding (Guice)** | VisibilityOutboundApplicationInjector | `@Named("IPFService")` selects the outbound-specific IPF service implementation. |
| **Template Method** | `AbstractMatcher` | Defines the matching + outbound algorithm; `MatchingProcessor` and `PendingSqsProcessor` inherit and specialise `getMetadataComponentName()` and `processPending()`. |
| **Factory** | `InboundTransformerFactory`, `InboundMapperFactory` | Selects the correct transformer or mapper implementation at runtime based on EDI type or carrier code. |
| **Strategy** | `InboundTransformer` (EVGCarrierTransformer, etc.) | Each carrier transformer is a strategy; the factory selects at runtime. |
| **Strategy** | `MessageTypeProcessor` (Shippeo, CW Subscription, CW Event) | WMEventProcessor dispatches to the correct strategy via a `Map<WatermillMessageType, MessageTypeProcessor>`. |

### Behavioural Patterns

| Pattern | Location | How Used |
|---|---|---|
| **Producer-Consumer (SQS polling)** | All long-running services | `SqsMessageHandler` wraps long-poll SQS reads with a configurable thread pool; the processor `Function<Message, Void>` is the consumer. |
| **Dead Letter Queue** | All SQS queues | Every queue has a paired DLQ. Non-recoverable errors route the message to the DLQ via `SqsMessageHandler`. Recoverable errors (`ProvisionedThroughputExceededException`, `RecoverableException`) suppress the DLQ routing and suppress message deletion — causing automatic redelivery. |
| **Optimistic Locking (mutex via MySQL)** | `OutboundMultiTransactionProcessor` | `lockThreshold()` executes a conditional UPDATE; if it returns false, another worker already locked the row. A forced-unlock safeguard fires when the lock is stale beyond `timeLimitInMinutes + 120 min`. |
| **Batch / Bulk Processing** | `OutboundGenerator`, `PendingSqsProcessor` | Transactions are fetched and processed as batches (`Lists.partition`, `bulkMatchTransactions`). |
| **Parallel Processing** | `CargoVisibilityService`, `GPSEventProcessor`, `PendingSqsProcessor`, `VisibilityOutboundPoller` | `CompletableFuture`/`parallelStream` for CPU-bound or I/O-bound parallel execution with configurable threshold (≥10 for cargo visibility). |
| **Retry with Prefix Partitioning** | `VisibilityPendingStart` / `PendingSqsProcessor` | Pending retry is partitioned across 256 DynamoDB hash-key prefixes (`ce:00`–`ce:ff`) to parallelise the scan workload and avoid hot-partition issues. |
| **Event Sourcing (partial)** | DynamoDB Streams + S3 Archive | Every ContainerEvent MODIFY event is captured as an immutable S3 object (`YYYY/MM/DD/HH/{id}`), providing a point-in-time history of event state changes. |
| **Command (DynamoDB table creation)** | `DynamoContainerEventsTableCommand` etc. | Table creation is encapsulated as command objects that execute against DynamoDB at service startup if the table does not exist. |

### Integration Patterns

| Pattern | Location | How Used |
|---|---|---|
| **Messaging / Event-Driven** | Entire module | All cross-service communication flows through SQS queues; no direct service-to-service synchronous calls between visibility services. |
| **Claim Check (S3 + SQS)** | `CargoVisibilityService`, `WMEventProcessor`, `GPSEventProcessor` | Large payloads are stored in S3; SQS messages carry only the `MetaData` reference (bucket + fileName). The consumer fetches the actual payload from S3. |
| **Content-Based Router** | `WMEventProcessor` | Routes to the correct `MessageTypeProcessor` based on `messageType` from MetaData projections. |
| **Aggregator/Fan-Out** | `MatchingProcessor` | For each inbound event, discovers all matching subscriptions and creates one `ContainerEventOutbound` record per subscription (fan-out). |
| **Polling Consumer** | `VisibilityOutboundPoller` (Lambda) | Periodically queries a relational table and emits messages for ready items — decoupling the batch scheduler from the batch executor. |
| **Idempotent Consumer** | `OutboundMultiTransactionProcessor` | The lock/unlock pattern combined with `getUnprocessedTransactions` pagination ensures each outbound batch is processed exactly once per IPF threshold crossing. |
| **Anti-Corruption Layer** | `IFTSTAMapper`, `T315Mapper`, `ITVGPSEventMapper` | Each external EDI or GPS format is translated to the internal `ContainerEventSubmission` model before any domain logic is applied. |

---

*End of document*
