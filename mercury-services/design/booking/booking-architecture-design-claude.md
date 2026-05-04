# Booking Module — Architecture and Design Document

**Mercury Services Platform | Module: `booking`**
**Version: 1.0 | Java 17 | Dropwizard | Google Guice | AWS SDK 2.x**
**Document Date: 2026-05-04**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [High-Level Architecture Diagram](#3-high-level-architecture-diagram)
4. [Package / Functional Area Breakdown](#4-package--functional-area-breakdown)
5. [Key Classes Reference Table](#5-key-classes-reference-table)
6. [Inbound Processing Data Flow](#6-inbound-processing-data-flow)
7. [Outbound Processing Data Flow](#7-outbound-processing-data-flow)
8. [Booking State Machine](#8-booking-state-machine)
9. [Database Schema Overview](#9-database-schema-overview)
10. [SQS Queue Topology](#10-sqs-queue-topology)
11. [Guice Dependency-Injection Wiring](#11-guice-dependency-injection-wiring)
12. [REST API Summary](#12-rest-api-summary)
13. [Validation Rules Summary](#13-validation-rules-summary)
14. [Design Patterns](#14-design-patterns)
15. [Local Guava Cache Configuration](#15-local-guava-cache-configuration)
16. [Configuration Properties Reference](#16-configuration-properties-reference)
17. [Inter-Service Communication](#17-inter-service-communication)
18. [Lambda Functions](#18-lambda-functions)

---

## 1. Executive Summary

The **Booking module** is the central hub of the Mercury Services platform for managing ocean-freight booking transactions between **shippers/forwarders (Bookers / RAC)** and **carriers (CPD)**. It acts as the single source of truth for all booking lifecycle events, from initial submission through carrier acknowledgement, confirmation, amendment, decline, split, replacement, and cancellation.

The module runs as a standalone **Dropwizard 4.x** microservice packaged as an uber-JAR. It operates in two distinct processing planes:

- **Inbound Plane (EDI / API)** — Receives booking messages from carriers and customers via an AWS SQS queue. Messages have previously been transformed from raw EDI or XML payloads by an upstream Contivo transformer (Appian Way pipeline). The processor deserialises the canonical JSON from S3, routes based on context code (`requestBooking` / `confirmBooking`), validates, and persists to DynamoDB.

- **Outbound Plane (Notifications / EDI)** — After every successful state change the outbound pipeline evaluates each party's subscriptions (email templates, EDI file generation via Appian Way watermill, push webhooks), enriches the booking with reference data, and dispatches notifications. A dedicated thread pool with a bounded queue handles outbound work asynchronously.

- **REST API Plane** — Exposes JAX-RS endpoints for direct API-channel customers, carriers, and internal admin tools. Handles booking request, amend, cancel, confirm, acknowledge, decline, replace, search (Elasticsearch), template management, rapid reservation, dangerous goods, and carrier spot-rates.

---

## 2. Technology Stack

| Layer / Concern | Library / Framework | Exact Version (from pom.xml) |
|---|---|---|
| Runtime | Java | 17 (maven.compiler.release = 17) |
| HTTP Server & DI container | Dropwizard | via parent `mercury-services` pom (Jetty embedded) |
| Dependency Injection | Google Guice | via `mercury-commons` / `cloud-sdk-api` |
| Metrics | Dropwizard Metrics + Guice Metrics | `com.palominolabs.metrics:metrics-guice:3.2.2` |
| Circuit Breaker | Netflix Hystrix + Dropwizard Bundle | `org.zapodot:hystrix-dropwizard-bundle:1.0.2` |
| Database (primary) | AWS DynamoDB (SDK 2.x, Enhanced Client) | `software.amazon.awssdk` via `cloud-sdk-aws:1.0.23-SNAPSHOT` |
| Database (legacy test) | AWS DynamoDB SDK 1.x | `com.amazonaws:aws-java-sdk-dynamodb:1.12.721` (test scope) |
| Search Engine | Elasticsearch | `org.elasticsearch:elasticsearch:6.6.2`; Jest client `io.searchbox:jest:6.3.0` |
| Messaging (SQS) | cloud-sdk-aws `MessagingClient` | `com.inttra.mercury:cloud-sdk-aws:1.0.23-SNAPSHOT` |
| Notification (SNS) | cloud-sdk-aws `NotificationService` | same |
| Object Store (S3) | cloud-sdk-aws `StorageClient` | same |
| Email | cloud-sdk-aws `EmailClientFactory` (SES v2) | same |
| JSON | Jackson | `com.fasterxml.jackson.core:jackson-annotations:2.18.1` |
| Jackson Afterburner | `jackson-module-afterburner:2.18.1` | — |
| Jackson XML | `jackson-dataformat-xml:2.18.1` | — |
| REST API Documentation | Swagger 2.0 | `io.swagger:swagger-core:1.6.14`; swagger-maven-plugin `3.1.7` |
| Swagger UI | `org.webjars:swagger-ui:5.17.14` | — |
| Unit of Measure | `tec.uom:uom-se:1.0.8` | — |
| Retry (Guava) | `com.github.rholder:guava-retrying:2.0.0` | — |
| Object Diff | `org.javers:javers-core:7.4.1` | — |
| Lambda Events | `com.amazonaws:aws-lambda-java-events:3.14.0` | — |
| Lombok | `org.projectlombok:lombok` (provided) | via parent pom |
| Logging | Log4j 2 | `org.apache.logging.log4j:log4j-core:2.23.1` |
| Testing — Unit | JUnit 5 + Mockito | `junit-jupiter:5.12.2`; `mockito-junit-jupiter:5.12.0` |
| Testing — Integration | TestNG + WireMock + DynamoDB Local | `testng:7.10.2`; `wiremock:3.5.4`; `local-dynamodb:1.R.01.002` |
| Build | Maven Shade Plugin (two executions) | `3.5.1` |
| Appian Way transformer | `com.inttra.mercury.appian-way:transformer:1.R.0.001` | test scope |

---

## 3. High-Level Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                       MERCURY BOOKING MICROSERVICE                               ║
║                                                                                  ║
║  ┌─────────────┐    ┌─────────────────────────────────────────────────────────┐ ║
║  │  REST API   │    │                 INBOUND PIPELINE                        │ ║
║  │  (JAX-RS /  │    │                                                         │ ║
║  │  Dropwizard)│    │  ┌───────────────────────────────────────────────────┐  │ ║
║  │             │    │  │  SQS Inbound Queue  (appianWayConfig.inQueueUrl)  │  │ ║
║  │ HTTP Clients│    │  └──────────────────────┬────────────────────────────┘  │ ║
║  │  (Booker /  │    │                         │ long-poll, batch up to 10     │ ║
║  │   Carrier / │    │                         ▼                               │ ║
║  │   Admin)    │    │  ┌────────────────────────────────────────────────────┐ │ ║
║  └──────┬──────┘    │  │  SQSListener  (1 dedicated thread, ListenerManager)│ │ ║
║         │           │  └──────────────────────┬─────────────────────────────┘ │ ║
║         │           │                         │ submit per-message             │ ║
║         │           │                         ▼                               │ ║
║         │           │  ┌─────────────────────────────────────────────────── ┐ │ ║
║         │           │  │  BookingProcessorTask  (ExecutorService "processor" │ │ ║
║         │           │  │   8 threads, SynchronousQueue, CallerRunsPolicy)    │ │ ║
║         │           │  │                                                     │ │ ║
║         │           │  │   1. Parse MetaData JSON from SQS body              │ │ ║
║         │           │  │   2. Fetch canonical payload from S3                │ │ ║
║         │           │  │   3. Route: contextCode == "requestBooking" (RAC)   │ │ ║
║         │           │  │                    OR  "confirmBooking"  (CPD)      │ │ ║
║         │           │  │   4. Custom-deserialize (enum + number tolerant)    │ │ ║
║         │           │  │   5. Dispatch to BookingService                     │ │ ║
║         │           │  └───────────────────────────────────────────────────┘ │ ║
║         │           └─────────────────────────────────────────────────────────┘ ║
║         │                              │                                         ║
║         │ (both paths converge here)   │                                         ║
║         ▼                             ▼                                         ║
║  ┌───────────────────────────────────────────────────────────────────────────┐   ║
║  │                        BookingService  (@Singleton)                        │   ║
║  │                                                                            │   ║
║  │  request()  amend()  cancel()  confirm()  pending()  decline()  replace()  │   ║
║  │                                                                            │   ║
║  │   1. validationService.validate()  → ValidationContext                    │   ║
║  │   2. BookingState.calcTransition() → target state                         │   ║
║  │   3. EnrichedAttributes from context                                      │   ║
║  │   4. bookingDetailDao.save()  (DynamoDB)                                  │   ║
║  │   5. outboundService.processOutbound()                                    │   ║
║  └───────────────────────────────────────────────────────────────────────────┘   ║
║         │                                │                                        ║
║         ▼                               ▼                                        ║
║  ┌──────────────┐            ┌────────────────────────────────────────────────┐  ║
║  │ BookingDetail│            │          OutboundServiceImpl (@Singleton)       │  ║
║  │    DAO       │            │                                                 │  ║
║  │ (DynamoDB    │            │  ExecutorService "outbound" (32 threads,        │  ║
║  │  SDK 2.x)    │            │   ArrayBlockingQueue(60), CallerRunsPolicy)     │  ║
║  └──────┬───────┘            │                                                 │  ║
║         │                   │  ┌──────────────┐  ┌──────────────────────────┐ │  ║
║         │                   │  │EnrichmentSvc │  │SubscriptionConditionEval │ │  ║
║         │                   │  │ - Location   │  │PerSubscription:          │ │  ║
║         │                   │  │ - Equipment  │  │  - email (SES v2)        │ │  ║
║         │                   │  │ - Party      │  │  - EDI (SQS watermill)   │ │  ║
║         │                   │  │ - Package    │  │  - webhook               │ │  ║
║         │                   │  └──────────────┘  └──────────────────────────┘ │  ║
║         │                   │                                                  │  ║
║         │                   │  SNSEventPublisher (bookingWas* events)          │  ║
║         │                   └────────────────────────────────────────────────┘  ║
║         │                                                                        ║
║         ▼                                                                        ║
║  ┌───────────────────────────────┐    ┌──────────────────────────────────────┐  ║
║  │  AWS DynamoDB (SDK 2.x)       │    │  Elasticsearch 6.6  (Jest client)     │  ║
║  │  Table: BookingDetail         │    │  Index: bookings                      │  ║
║  │  Table: UniqueId              │    │  IndexerHandler Lambda → stream        │  ║
║  │  Table: SequenceId            │    └──────────────────────────────────────┘  ║
║  │  Table: RapidReservation      │                                               ║
║  │  Table: Template              │    ┌──────────────────────────────────────┐  ║
║  │  Table: TemplateSummary       │    │  AWS S3                               │  ║
║  │  Table: SpotRatesDetail       │    │  Bucket: appianWayConfig.s3Workspace  │  ║
║  │  Table: SpotRatesToInttraRef  │    │  Bucket: s3ArchiveBucket              │  ║
║  └───────────────────────────────┘    └──────────────────────────────────────┘  ║
║                                                                                  ║
║  ┌───────────────────────────────────────────────────────────────────────────┐  ║
║  │                     Network Services (HTTP via NetworkServiceClient)       │  ║
║  │  GeographyService  NetworkParticipantService  ReferenceDataService         │  ║
║  │  SubscriptionService  ParticipantsAliasService  UserService                │  ║
║  │  OptionalValidationsService  DGSService  IntegrationProfileFormatService   │  ║
║  │  ParticipantAddOnService  PartnershipService                               │  ║
║  │  (All backed by Guava in-memory caches with 30-min / 24-hr TTLs)          │  ║
║  └───────────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════════╝
```

---

## 4. Package / Functional Area Breakdown

| Package / Directory | Purpose | Key Classes |
|---|---|---|
| `booking` (root) | Application entry point | `BookingApplication` |
| `config` | Guice modules, Dropwizard config, lifecycle | `BookingConfig`, `BookingApplicationInjector`, `BookingApplicationModule`, `BookingDynamoModule`, `BookingMessagingModule`, `InboundServiceModule`, `OutboundServiceModule`, `LocalCacheModule`, `BookingEmailSenderModule`, `SystemUTCClockModule` |
| `inbound` | EDI/SQS message processing | `BookingProcessorTask`, `MigrationLogic`, `NonInttraBookingValidator` |
| `inbound.confirmation` | Carrier confirmation/pending/split model | `ConfirmPendingMessage`, `BCEquipment`, `BCCharge`, `Split` |
| `inbound.confirmation.validation` | Structural validation helpers | `HeaderValidations`, `CargoValidations`, `EquipmentValidations`, `LegValidations`, `PartyValidations`, `ReferenceValidations`, `HeaderLocationValidations`, `EnumDeserializer`, `NumberDeserializer` |
| `inbound.decline` | Carrier decline/replace model | `DeclineReplaceMessage`, `DeclineRequest`, `DeclineMessage` |
| `inbound.decline.validation` | Decline validation helpers | `CommentValidations`, `HeaderValidations` |
| `service` | Core domain logic | `BookingService`, `ValidationService`, `BookingLocator`, `BookingAuthorizer`, `BookingEventRelay`, `BookingReinstatementService`, `PartyLocator`, `BookingResult`, `BookingDisposition` |
| `dao` | DynamoDB data access layer | `BookingDetailDao` |
| `model` | Canonical booking domain model | `Booking`, `BookingDetail`, `BookingState` (enum), `BookingRequestContract`, `CancelMessage`, `Channel` |
| `model.Common` | Shared value-object types | `Equipment`, `Contact`, `Address`, `TransactionParty`, `TransactionReference` |
| `model.INTTRACommon` | INTTRA-specific types and enums | `PartyRole`, `BookingResponseType`, `LocationDate`, `LocationAdditionalInfo` |
| `model.request` | RAC request-specific model | `BRReference`, `BRReferenceType` |
| `dynamodb` | DynamoDB SDK 2.x type converters | `ContractAttributeConverter`, `AuditAttributeConverter`, `EnrichedAttributesConverter`, `MetaDataConverter`, `BookingStateConverter`, `LocalDateTimeTypeConverter`, `OffsetDateTimeTypeConverter` |
| `outbound.services` | Outbound notification dispatch | `OutboundServiceImpl`, `EnrichmentService`, `TransformerService`, `WatermillService`, `OutboundEmailService`, `ServiceHelper`, `SubscriptionConditionEvaluator`, `SubscriptionPreferenceProcessor` |
| `outbound.enrichment` | Booking data enrichment | `LocationEnrichment`, `EquipmentEnrichment`, `PartyEnrichment`, `PackageEnrichment` |
| `outbound.email` | Email notification | `OutboundEmailSender`, `RequestAmendEmailVariablesConverter`, `ConfirmPendingEmailVariablesConverter`, `DeclineReplaceEmailVariablesConverter`, `CancelEmailVariablesConverter` |
| `outbound.diffGenerator` | Booking amendment diff | `DiffGenerator`, `EquipmentDiff`, `HeaderPartiesDiff`, `HeaderReferencesDiff`, `OtherAttributesDiff`, `TransportLegDiff`, `PackageDetailsDiff`, `TransactionLocationsDiff` |
| `outbound.model` | Outbound data structures | `EnrichedAttributes`, `MultiVersionAttributes`, `AperakMessage`, `NotificationCollector`, `ValidationMessage` |
| `outbound.custom` | Carrier-specific EDI customisations | `CustomizationHandler`, `EdiCustomizations`, `HeinekenCustomization`, `SpecialCharCustomization` |
| `outbound.resources` | Outbound admin REST endpoints | `OutboundResource` |
| `resources` | Primary REST endpoints | `CustomerBookingResource`, `CarrierBookingResource`, `SearchResource`, `BookingExceptionMapper`, `BookingResourceUtil` |
| `elasticsearch` | Elasticsearch query DSL builder and indexer | `Searcher`, `Indexer`, `IndexedBooking`, `IndexedLocation`, `CompositeQuery`, `Bool`, `Term`, `Range`, `Nested`, `Sort` |
| `networkservices` | HTTP client facade for external services | `NetworkServiceClient`, `GeographyService(Impl/Cache)`, `NetworkParticipantService(Impl/Cache)`, `ReferenceDataService(Impl/Cache)`, `SubscriptionService(Impl/Cache)`, `ParticipantsAliasService(Impl/Cache)`, `UserService(Impl/Cache)`, `IntegrationProfileFormatService(Impl)`, `ParticipantAddOnService(Impl/Cache)`, `PartnershipServiceImpl` |
| `validation` | Cross-cutting validation framework | `ValidationContext`, `ValidationError`, `ValidationHelper`, `MessageGenerator` |
| `carrierrule` | Optional carrier-specific validations | `OptionalValidationsService(Impl/CacheImpl)`, `OptionalValidation`, `ConditionEvaluator` |
| `carrierspotrates` | Carrier spot-rate retrieval (Maersk API) | `CarrierSpotRatesService`, `MaerskApiClient`, `SpotRatesDao`, `SpotRatesToInttraRefDao`, `MaerskResponseToCanonical` |
| `dgs` | Dangerous Goods (IMDG) reference + validation | `DGSService(Impl/CacheImpl)`, `DGSApiValidations`, `DGSRulesFactory`, cargo rules, equipment rules |
| `rapidreservation` | Rapid-reservation number assignment | `RapidReservationService`, `RapidReservationDao`, `RapidReservationResource` |
| `template` | Booking template management | `TemplateService`, `TemplateDao`, `TemplateSummaryDao`, `TemplateResource` |
| `common.listener` | SQS long-poll infrastructure | `SQSListener`, `Listener`, `ListenerManager` |
| `common.messaging` | Cloud-SDK SQS / SNS wrappers | `SQSClient`, `SNSClient` |
| `common.s3` | S3 workspace access | `S3WorkspaceService` |
| `common.event` | Workflow event logging | `EventLogger`, `EventGenerator`, `SNSEventPublisher`, `DummyEventPublisher` |
| `common.validation` | Common header / temperature validators | `CommonHeaderValidation`, `TemperatureFormatValidationAndConversion` |
| `externalwrapper` | Hystrix circuit-breaker + retry wrapper | `ExternalCallWrapper`, `RetriableMethodInterceptor`, `ExternalCallAnnotationListener` |
| `lambda` | AWS Lambda handlers | `IndexerHandler`, `S3ArchiveHandler`, `TrackAndTraceService`, `HandlerSupport` |
| `enrichment` | Location enrichment (shared) | `LocationEnrichment` |
| `util` | Utilities | `IdGenerator`, `Json`, `MetaData`, `MessageSupport`, `BookingServiceUtil`, `BackwardCompatibilityUtil` |

---

## 5. Key Classes Reference Table

| Class | Package (abbreviated) | Role |
|---|---|---|
| `BookingApplication` | `booking` | Entry point; builds InttraServer, registers Guice modules, JAX-RS resources, exception mappers |
| `BookingConfig` | `config` | Dropwizard YAML configuration POJO |
| `BookingApplicationInjector` | `config` | Main Guice module; binds services, SQSListener, SpotRate Jersey client, S3ArchiveHandler |
| `BookingDynamoModule` | `config` | Provides all DynamoDB `DatabaseRepository<>` singletons via `DynamoRepositoryFactory` |
| `BookingMessagingModule` | `config` | Provides `MessagingClient<String>` (SQS), `NotificationService` (SNS), `StorageClient` (S3) |
| `InboundServiceModule` | `config` | Configures the "processor" `ExecutorService` (8 threads, `SynchronousQueue`) |
| `OutboundServiceModule` | `config` | Configures "outbound" `ExecutorService` (32 threads, `ArrayBlockingQueue(60)`); binds `OutboundService` and `EventPublisher` |
| `LocalCacheModule` | `config` | Provides 16 named Guava `LoadingCache` singletons for all external service lookups |
| `SQSListener` | `common.listener` | Infinite poll loop; fetches up to N messages from inbound SQS queue, delegates to `BookingProcessorTask::process` |
| `BookingProcessorTask` | `inbound` | Orchestrates per-message EDI processing; fetches S3 payload; routes RAC vs CPD; calls `BookingService` |
| `BookingService` | `service` | Core domain service; implements all booking operations: request, amend, cancel, confirm, pending, decline, replace, split, delete |
| `ValidationService` | `service` | Runs structural + business + optional-carrier validations; builds `ValidationContext` |
| `BookingLocator` | `service` | Finds `Booking` aggregates from DynamoDB via `BookingDetailDao` |
| `BookingEventRelay` | `service` | Fires `bookingWasCreated` / `bookingWasUpdated` events to `EventPublisher` (SNS) |
| `BookingReinstatementService` | `service` | Validates OCBN / ShipmentId uniqueness during reinstatement scenarios (ION-9016) |
| `PartyLocator` | `service` | Resolves carrier and booker `TransactionParty` from `NetworkParticipantService` |
| `BookingDetailDao` | `dao` | DynamoDB CRUD; 4 GSIs for lookup by inttraRef, carrierId+CBN, bookerId+shipmentId, carrierScac+CBN |
| `BookingDetail` | `model` | DynamoDB entity; annotated with `@DynamoDbBean`, TTL, 4 GSIs, DynamoDB Streams |
| `Booking` | `model` | Domain aggregate; wraps a list of `BookingDetail` versions; provides `calcState()`, `calcBooker()`, etc. |
| `BookingState` | `model` | Enum + finite-state-machine; holds all valid transitions as a static map keyed by `Transition(from, actor, to)` |
| `OutboundServiceImpl` | `outbound.services` | Evaluates subscriptions; dispatches email, EDI (SQS watermill), webhook, and Aperak outbound messages |
| `EnrichmentService` | `outbound.services` | Enriches booking with geography, equipment, party, and package reference data |
| `WatermillService` | `outbound.services` | Serialises booking to S3 and sends metadata to distributor SQS for Appian Way watermill |
| `OutboundEmailSender` | `outbound.email` | Sends template-based email notifications via cloud-sdk `EmailClientFactory` (SES v2) |
| `DiffGenerator` | `outbound.diffGenerator` | Computes field-level diff between booking versions using JaVers; used for amendment highlights in emails |
| `CustomerBookingResource` | `resources` | JAX-RS: GET booking, POST request/amend/cancel, DELETE, GET optional-validations |
| `CarrierBookingResource` | `resources` | JAX-RS: POST confirm/acknowledge/decline/replace; POST s3Archive |
| `SearchResource` | `resources` | JAX-RS: GET/POST Elasticsearch-backed booking search, aggregations |
| `OutboundResource` | `outbound.resources` | JAX-RS: GET enrich, POST reprocess outbound/email/Aperak |
| `TemplateResource` | `template` | JAX-RS: CRUD for booking templates |
| `RapidReservationResource` | `rapidreservation` | JAX-RS: CRUD for Rapid Reservation number series |
| `CarrierSpotRatesResource` | `carrierspotrates` | JAX-RS: GET spot rates from Maersk API |
| `DangerousGoodsResource` | `dgs` | JAX-RS: GET DGS details / search |
| `OptionalValidationsService` | `carrierrule.service` | Fetches and evaluates carrier-specific optional field validation rules |
| `NetworkServiceClient` | `networkservices` | Generic HTTP client with retry and circuit-breaking; used by all network service implementations |
| `Searcher` | `elasticsearch` | Builds and executes Elasticsearch queries via Jest client |
| `Indexer` | `elasticsearch` | Writes `IndexedBooking` documents to Elasticsearch |
| `IndexerHandler` | `lambda` | AWS Lambda; triggered by DynamoDB Streams; indexes changed `BookingDetail` records into Elasticsearch |
| `S3ArchiveHandler` | `lambda` | Archives booking JSON to S3 on demand or via REST trigger |
| `ExternalCallWrapper` | `externalwrapper` | Hystrix command wrapper with configurable timeout, retry (Guava), and fallback |

---

## 6. Inbound Booking Processing Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         INBOUND EDI / BOOKING PROCESSING FLOW                       │
└─────────────────────────────────────────────────────────────────────────────────────┘

   External EDI Partner / Carrier System
           │
           ▼
   ┌───────────────────────────┐
   │ Appian Way (Contivo)      │  Transforms raw EDI (e.g., ANSI X12 310/315,
   │ Transformer Pipeline      │  EDIFACT COPRAR/BAPLIE) → canonical JSON.
   │                           │  Uploads canonical JSON to S3 workspace.
   │   RAW EDI in              │  Produces MetaData message (bucket + fileName
   │   ──────────►             │  + projections incl. contextCode).
   │   Canonical JSON + Meta   │
   └─────────────┬─────────────┘
                 │
                 ▼
   ┌─────────────────────────────┐
   │  SQS: inQueueUrl            │  MetaData JSON body (NOT the booking itself)
   │  (Inbound Booking Queue)    │
   └──────────────┬──────────────┘
                  │  long-poll (waitTimeSeconds, maxNumberOfMessages)
                  ▼
   ┌──────────────────────────────┐
   │  SQSListener                 │  Single-thread infinite loop.
   │  (ListenerManager managed)   │  Calls BookingProcessorTask::process(messages, ackCallback)
   └──────────────┬───────────────┘
                  │  submit to executor
                  ▼
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │  BookingProcessorTask  (ExecutorService "processor", 8 threads)              │
   │                                                                              │
   │  1. Parse MetaData from SQS body (bucket, fileName, projections)            │
   │  2. Fetch canonical JSON from S3:                                            │
   │     - If exitStatus = FAILURE: fetch annotations + canonical separately      │
   │     - Else: fetch single file                                                │
   │  3. Determine contextCode from MetaData.projections                          │
   │                                                                              │
   │  ┌──────────────────────────────────────────────────────────────────────┐  │
   │  │  contextCode == "requestBooking" (RAC)                               │  │
   │  │                                                                      │  │
   │  │  customDeserialize(BookingRequestContract, ...)                       │  │
   │  │   ├── Check bookingState present (else throw ResolutionException)     │  │
   │  │   ├── If REQUEST + inttraRef present → strip inttraRef (re-request)  │  │
   │  │   ├── MigrationLogic.isRACMigrated()? → if No → routeToBookingBridge │  │
   │  │   ├── If structural errors → throw StructuralValidationException      │  │
   │  │   └── Switch on BookingState:                                         │  │
   │  │        REQUEST → bookingService.request()                             │  │
   │  │        AMEND   → bookingService.amend()                               │  │
   │  │        CANCEL  → bookingService.cancel()                              │  │
   │  └──────────────────────────────────────────────────────────────────────┘  │
   │                                                                              │
   │  ┌──────────────────────────────────────────────────────────────────────┐  │
   │  │  contextCode == "confirmBooking" (CPD)                               │  │
   │  │                                                                      │  │
   │  │  customDeserialize(ConfirmPendingMessage, ...)                        │  │
   │  │   ├── Validate bookingState present + carrier party present           │  │
   │  │   ├── If inttraRef absent → NonInttraBookingValidator check           │  │
   │  │   │    ├── isInttraSplitReconfirm? → process as normal INTTRA        │  │
   │  │   │    ├── shouldProcessNIB? → set IS_NON_INTTRA_BOOKING projection  │  │
   │  │   │    └── Else → routeToBookingBridge, ignore=true                  │  │
   │  │   ├── If inttraRef present but < 2,000,000,000 → routeToBookingBridge│  │
   │  │   ├── If structural errors → throw StructuralValidationException      │  │
   │  │   └── Switch on BookingState:                                         │  │
   │  │        CONFIRM  → bookingService.confirm()                            │  │
   │  │        PENDING  → bookingService.pending()                            │  │
   │  │        REPLACE  → bookingService.replace()                            │  │
   │  │        DECLINE  → bookingService.decline()                            │  │
   │  └──────────────────────────────────────────────────────────────────────┘  │
   │                                                                              │
   │  Exception Handling:                                                         │
   │   TransformationException    → outboundService.processTransformationErrors   │
   │   StructuralValidationException → outboundService.processBusinessErrors      │
   │   BookingValidationException  → outboundService.processBusinessErrors        │
   │   StateTransitionException    → outboundService.processBusinessErrors        │
   │   AuthorizationException      → outboundService.processBusinessErrors        │
   │   BookingNotFoundException    → outboundService.processBusinessErrors        │
   │   ResolutionException         → outboundService.processBusinessErrors        │
   │   InternalException (network  → reprocessInbFailure = true; do NOT delete   │
   │     API failure after retries)   SQS message; retry after visibility timeout │
   │                                                                              │
   │  Finally: if !reprocessInbFailure → successCallback.accept(msg) → SQS delete │
   └──────────────────────────────────────────────────────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────┐
   │  BookingService           │  (detail below)
   └──────────────────────────┘
```

---

## 7. Outbound Processing Data Flow

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                        OUTBOUND BOOKING PROCESSING FLOW                            │
└───────────────────────────────────────────────────────────────────────────────────┘

  BookingService  (after successful state transition)
       │
       │  outboundService.processOutbound(booking, metaData, validationErrors, fromState)
       ▼
  ┌───────────────────────────────────────────────────────────────────────────────┐
  │  OutboundServiceImpl  (ExecutorService "outbound", 32 threads,               │
  │                         ArrayBlockingQueue(60), CallerRunsPolicy)            │
  │                                                                               │
  │  1. Fetch latest booking versions (carrier + customer) from DynamoDB         │
  │  2. EnrichmentService.enrich()                                                │
  │       ├─ LocationEnrichment   → GeographyService (Guava cache 30 min)       │
  │       ├─ EquipmentEnrichment  → ReferenceDataService (Guava cache 30 min)   │
  │       ├─ PartyEnrichment      → NetworkParticipantService (Guava cache 30 m)│
  │       └─ PackageEnrichment    → ReferenceDataService                        │
  │                                                                               │
  │  3. For each interested party (booker, carrier, shipper, forwarder, ...):    │
  │     subscriptionService.getSubscriptions(inttraCompanyId)                    │
  │     For each matching Subscription:                                           │
  │                                                                               │
  │     ┌─────────────────────────────────────────────────────────────────────┐ │
  │     │  ActionType == EDI (TransformerService / WatermillService):         │ │
  │     │   1. Apply CustomizationHandler (carrier-specific EDI tweaks)       │ │
  │     │   2. DiffGenerator → compute amendment diff                         │ │
  │     │   3. Serialise enriched booking JSON → S3 (distributorQueueUrl)     │ │
  │     │   4. Post MetaData to SQS distributor queue                         │ │
  │     │      (Appian Way picks up → generates EDI → sends to carrier/party) │ │
  │     └─────────────────────────────────────────────────────────────────────┘ │
  │                                                                               │
  │     ┌─────────────────────────────────────────────────────────────────────┐ │
  │     │  ActionType == EMAIL (OutboundEmailService):                        │ │
  │     │   1. Choose email template based on BookingState                    │ │
  │     │   2. Convert booking to template variables (state-specific converter)│ │
  │     │   3. BlacklistEmailService check                                    │ │
  │     │   4. OutboundEmailSender.send() → cloud-sdk EmailClientFactory      │ │
  │     │                                    (AWS SES v2)                     │ │
  │     └─────────────────────────────────────────────────────────────────────┘ │
  │                                                                               │
  │     ┌─────────────────────────────────────────────────────────────────────┐ │
  │     │  ActionType == WEBHOOK (WebHookService):                            │ │
  │     │   HTTP POST with enriched booking payload to party's webhook URL    │ │
  │     └─────────────────────────────────────────────────────────────────────┘ │
  │                                                                               │
  │     ┌─────────────────────────────────────────────────────────────────────┐ │
  │     │  APERAK (WatermillService / WatermillConfig.aperakWatermillSQS):   │ │
  │     │   Send functional acknowledgement (Aperak) message via SQS         │ │
  │     └─────────────────────────────────────────────────────────────────────┘ │
  │                                                                               │
  │  4. SNSEventPublisher.publish() → Booking event to SNS topic               │
  │     (triggers downstream consumers e.g. Track & Trace, BI reports)          │
  │                                                                               │
  │  Error handling:                                                              │
  │   processTransformationErrors → error email + error EDI                     │
  │   processBusinessErrors       → error email + error EDI                     │
  │   processInternalError        → error notification                           │
  └───────────────────────────────────────────────────────────────────────────────┘
       │
       ▼
  External Parties (email / EDI file / webhook / SNS subscribers)
```

---

## 8. Booking State Machine

### State Definitions

| State | Active | Carrier Status | Context Code | Display Name |
|---|---|---|---|---|
| `REQUEST` | Yes | No | `requestBooking` | Requested |
| `AMEND` | Yes | No | `requestBooking` | Amended |
| `PENDING` | Yes | Yes | `confirmBooking` | Pending |
| `CONFIRM` | Yes | Yes | `confirmBooking` | Confirmed |
| `DECLINE` | No | Yes | `confirmBooking` | Declined |
| `CANCEL` | No | No | `requestBooking` | Cancelled |
| `REPLACE` | No | Yes | `confirmBooking` | Replaced |

### State Transition Diagram

```
                    Actor: Carrier_CounterParty (RAC — Booker side)
                    ╔══════════════════════════════════════════════╗
   NEW              ║                                              ║
  BOOKING ─────────►║  [none] ──request──────────► REQUEST         ║
                    ║                                │             ║
                    ║                    amend ◄─────┤             ║
                    ║                                │             ║
                    ║  REQUEST ──cancel──────────► CANCEL (terminal)║
                    ║  REQUEST ──amend──────────► AMEND            ║
                    ║  AMEND   ──cancel──────────► CANCEL          ║
                    ║  AMEND   ──amend──────────► AMEND            ║
                    ║  PENDING ──amend──────────► AMEND            ║
                    ║  PENDING ──cancel──────────► CANCEL          ║
                    ║  CONFIRM ──amend──────────► AMEND            ║
                    ║  CONFIRM ──cancel──────────► CANCEL          ║
                    ║  DECLINE ──cancel──────────► DECLINE (ignore) ║
                    ║  REPLACE ──cancel──────────► REPLACE (err)   ║
                    ║  CANCEL  ──cancel──────────► CANCEL          ║
                    ║  CANCEL  ──amend──────────► FAILURE (213001) ║
                    ║  CANCEL  ──confirm─────────► FAILURE (213001)║
                    ╚══════════════════════════════════════════════╝

                    Actor: Carrier (CPD — Carrier side)
                    ╔══════════════════════════════════════════════╗
                    ║                                              ║
   NEW              ║  [none] ──confirm───────────► CONFIRM        ║
  CARRIER           ║  [none] ──pending───────────► (Ignored)     ║
  BOOKING           ║  [none] ──decline───────────► (Ignored)     ║
                    ║  [none] ──replace───────────► (Ignored)     ║
                    ║                                              ║
                    ║  REQUEST ──pending──────────► PENDING        ║
                    ║  REQUEST ──confirm──────────► CONFIRM        ║
                    ║  REQUEST ──decline──────────► DECLINE        ║
                    ║  REQUEST ──replace──────────► REPLACE        ║
                    ║                                              ║
                    ║  AMEND ──pending───────────► PENDING         ║
                    ║  AMEND ──confirm───────────► CONFIRM         ║
                    ║  AMEND ──decline───────────► DECLINE         ║
                    ║  AMEND ──replace───────────► REPLACE         ║
                    ║                                              ║
                    ║  PENDING ──pending──────────► PENDING        ║
                    ║  PENDING ──confirm──────────► CONFIRM        ║
                    ║  PENDING ──decline──────────► DECLINE        ║
                    ║  PENDING ──replace──────────► REPLACE        ║
                    ║                                              ║
                    ║  CONFIRM ──confirm──────────► CONFIRM        ║
                    ║  CONFIRM ──decline──────────► DECLINE        ║
                    ║  CONFIRM ──replace──────────► REPLACE        ║
                    ║  CONFIRM ──pending──────────► FAILURE(213001)║
                    ║                                              ║
                    ║  DECLINE ──pending──────────► PENDING (ION-9016)║
                    ║  DECLINE ──confirm──────────► CONFIRM (ION-9016)║
                    ║  DECLINE ──replace──────────► REPLACE (ION-9016)║
                    ║  DECLINE ──decline──────────► DECLINE        ║
                    ║  DECLINE ──amend────────────► FAILURE(213001)║
                    ║                                              ║
                    ║  CANCEL ──pending───────────► PENDING (ION-9016)║
                    ║  CANCEL ──confirm───────────► CONFIRM (ION-9016)║
                    ║  CANCEL ──replace───────────► REPLACE (ION-9016)║
                    ║  CANCEL ──decline───────────► CANCEL (ignore) ║
                    ║                                              ║
                    ║  REPLACE ──confirm/pending/decline/replace   ║
                    ║            ─────────────────► FAILURE(213001)║
                    ╚══════════════════════════════════════════════╝

  SPLIT LOGIC (overlays above)
  ──────────────────────────────
  When ConfirmPendingMessage.isSplit() == true AND:
    fromState ∈ {REQUEST, AMEND, CONFIRM, PENDING, REPLACE}
    AND targetState ∈ {CONFIRM, PENDING, DECLINE}
  → BookingService.doSplit(): creates NEW inttraRef copied from original,
    adds new BookingDetail versions, calls outboundService.processOutbound()
    on the new split booking.

  EQUIVALENCE CHECK (deduplication)
  ───────────────────────────────────
  Before persisting an UPDATE, Booking.isEquivalent(contract) is evaluated.
  If the incoming payload is identical to the previous version → IGNORED,
  no new DynamoDB record is written, no outbound notifications are sent.
```

---

## 9. Database Schema Overview

### DynamoDB — Primary Table: `BookingDetail`

The table name is prefixed with the environment table-prefix configured in `BaseDynamoDbConfig`.

| Attribute | Type | Role |
|---|---|---|
| `bookingId` | String (PK) | UUID hex (32 chars, no dashes) — identifies the booking aggregate |
| `sequenceNumber` | String (SK) | Format: `m_{epochMs}_{BookingState}_{inttraRef}` — version ordering |
| `inttraReferenceNumber` | String | INTTRA unique reference (GSI PK for `INTTRA_REFERENCE_NUMBER_INDEX`) |
| `carrierId` | String | Carrier INTTRA company ID (GSI PK for `carrierId_carrierReferenceNumber`) |
| `carrierReferenceNumber` | String | Ocean carrier booking number (GSI SK for two carrier GSIs) |
| `bookerId` | String | Booker INTTRA company ID (GSI PK for `bookerId_shipmentId`) |
| `shipmentId` | String | Customer shipment reference (GSI SK for `bookerId_shipmentId`) |
| `carrierScac` | String | Carrier SCAC code (GSI PK for `carrierScac_carrierReferenceNumber`) |
| `state` | String (BookingState) | Current booking state |
| `channel` | String | Channel: EDI, API, WEB, DESKTOP |
| `payload` | JSON (ContractAttributeConverter) | Full canonical booking contract |
| `enrichedAttributes` | JSON (EnrichedAttributesConverter) | Enriched party, location, package data |
| `metaData` | JSON (MetaDataConverter) | S3 workspace metadata + workflow IDs |
| `audit` | JSON (AuditAttributeConverter) | Created by, created date UTC |
| `expiresOn` | Epoch seconds (TTL) | DynamoDB TTL — 400 days from creation |
| `nonInttraBooking` | Boolean | True for Non-INTTRA Bookings (NIB) |
| `originalInttraReferenceNumber` | String | For split bookings: the original parent inttraRef |
| `version` | Number (DynamoDbVersionAttribute) | Optimistic locking version |

**Global Secondary Indexes:**

| GSI Name | Partition Key | Sort Key | Projection |
|---|---|---|---|
| `INTTRA_REFERENCE_NUMBER_INDEX` | `inttraReferenceNumber` | — | KEYS\_ONLY |
| `carrierId_carrierReferenceNumber` | `carrierId` | `carrierReferenceNumber` | KEYS\_ONLY |
| `bookerId_shipmentId` | `bookerId` | `shipmentId` | KEYS\_ONLY |
| `carrierScac_carrierReferenceNumber` | `carrierScac` | `carrierReferenceNumber` | KEYS\_ONLY |

Note: All GSI lookups perform a two-phase fetch: (1) GSI query returns booking IDs, (2) consistent-read batch fetch from main table by booking IDs.

DynamoDB Streams are enabled on `BookingDetail` with `KEYS_ONLY` stream view type. The `IndexerHandler` Lambda consumes this stream to update Elasticsearch.

---

### DynamoDB — Supporting Tables

| Table Name | PK | SK | Purpose |
|---|---|---|---|
| `UniqueId` | `id` (Long) | — | Atomic counter for INTTRA reference number generation (per carrier) |
| `SequenceId` | `id` (String) | — | Sequence ID for booking version numbering |
| `RapidReservation` | `carrierId` | `seriesId` | Rapid Reservation number series configuration per carrier |
| `Template` | `companyId` | `templateId` | Saved booking templates per company |
| `TemplateSummary` | `companyId` | `templateId` | Lightweight summary of templates for listing |
| `SpotRatesDetail` | `spotRateId` | — | Cached carrier spot-rate offers (Maersk) |
| `SpotRatesToInttraRef` | `spotRateId` | — | Mapping from spot-rate ID to INTTRA reference |

---

### Elasticsearch Index: `bookings`

Used exclusively for search queries (not authoritative store). Documents are of type `IndexedBooking` and `IndexedLocation`. The `IndexerHandler` Lambda populates this index from DynamoDB Streams.

Key indexed fields include: `inttraReferenceNumber`, `carrierReferenceNumber`, `bookingState`, `carrierId`, `bookerId`, `shipperId`, `forwarderId`, `consigneeId`, `placeOfReceiptCode`, `placeOfDeliveryCode`, `vessel`, `voyage`, `complianceRisk`, `nonInttraBooking`.

---

## 10. SQS Queue Topology

```
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                            SQS QUEUE TOPOLOGY                                   │
  └─────────────────────────────────────────────────────────────────────────────────┘

  INBOUND QUEUES
  ─────────────────────────────────────────────────────────────────────────────────

  [Appian Way Transformer]
        │
        │  MetaData JSON (S3 pointer + projections)
        ▼
  ┌─────────────────────────────────────────────────┐
  │  appianWayConfig.inQueueUrl                     │  ← INBOUND BOOKING QUEUE
  │  (EDI/API submissions transformed by Contivo)   │
  │  contextCode ∈ {"requestBooking", "confirmBooking"} │
  └──────────────────────┬──────────────────────────┘
                         │  SQSListener polls this queue
                         ▼
                  BookingProcessorTask

  OUTBOUND QUEUES
  ─────────────────────────────────────────────────────────────────────────────────

  BookingService / OutboundServiceImpl
        │
        ├──────────────────────────────────────────────────────────────────────┐
        │                                                                      │
        ▼                                                                      ▼
  ┌─────────────────────────────────────────────┐   ┌───────────────────────────┐
  │  appianWayConfig.distributorQueueUrl         │   │  watermillConfig           │
  │  (Outbound EDI Distributor Queue)            │   │  .aperakWatermillSQS      │
  │                                             │   │  (APERAK / Functional ACK) │
  │  WatermillService sends booking payload     │   │                            │
  │  + MetaData for each subscription action    │   │  WatermillService sends    │
  │  that requires EDI output                   │   │  AperakMessage             │
  └─────────────────────────────────────────────┘   └───────────────────────────┘
        │                                                      │
        ▼                                                      ▼
  Appian Way Watermill picks up, generates         Appian Way Watermill generates
  carrier/party-specific EDI, delivers to          functional acknowledgement EDI
  party via MFT/SFTP/AS2 etc.

  ROUTING QUEUE
  ─────────────────────────────────────────────────────────────────────────────────

  BookingProcessorTask
        │  (for legacy / NIB bookings not processed in cloud)
        ▼
  ┌─────────────────────────────────────────────┐
  │  bookingConfig.bookingBridgeSQS             │  ← BOOKING BRIDGE QUEUE
  │  (Legacy core booking system bridge)        │
  │                                             │
  │  Messages routed here when:                 │
  │  - INTTRA ref < 2,000,000,000 (legacy)      │
  │  - RAC message not migrated                 │
  │  - NIB message disabled or carrier not      │
  │    enabled for NIB cloud processing         │
  └─────────────────────────────────────────────┘

  TRANSFORMER QUEUE (used for testing / re-run)
  ─────────────────────────────────────────────────────────────────────────────────
  ┌─────────────────────────────────────────────┐
  │  appianWayConfig.transformerSQSUrl           │  ← TRANSFORMER INPUT QUEUE
  │  (Upstream input to Contivo transformer)    │
  └─────────────────────────────────────────────┘
```

---

## 11. Guice Dependency-Injection Wiring

```
  BookingApplication.newServer()
  └── InttraServer builder registers the following Guice modules (in order):

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 1. BookingApplicationInjector (BookingConfig, Environment)                  │
  │    ├── Provides: SQSListener (binds Listener → SQSListener)                │
  │    ├── Provides: S3ArchiveHandler                                           │
  │    ├── Provides: @Named("spotRateClient") Jersey Client                    │
  │    ├── Binds: ServiceDefinitions from config                               │
  │    ├── Binds: ElasticsearchConfig, BookingEmailConfig, AppianWayConfig,    │
  │    │          CustomizationConfig, WatermillConfig                          │
  │    └── Binds service interfaces:                                            │
  │         GeographyService           → GeographyServiceCacheImpl             │
  │         NetworkParticipantService  → NetworkParticipantServiceCacheImpl    │
  │         ReferenceDataService       → ReferenceDataServiceCacheImpl         │
  │         ParticipantsAliasService   → ParticipantsAliasServiceCacheImpl     │
  │         IntegrationProfileFormatService → IntegrationProfileFormatServiceImpl│
  │         SubscriptionService        → SubscriptionServiceCacheImpl          │
  │         UserService                → UserServiceCacheImpl                  │
  │         OptionalValidationsService → OptionalValidationServiceCacheImpl    │
  │         PartnershipService         → PartnershipServiceImpl                │
  │         DGSService                 → DGSServiceCacheImpl                   │
  │         ParticipantAddOnService    → ParticipantAddOnServiceCacheImpl      │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 2. BookingDynamoModule (BookingConfig, Environment)                         │
  │    Provides (all @Singleton):                                               │
  │    ├── DynamoDbClientConfig                                                 │
  │    ├── BookingDetailDao (DatabaseRepository<BookingDetail, Composite>)      │
  │    ├── UniqueIdDao (DatabaseRepository<UniqueId, PartitionKey<Long>>)       │
  │    ├── SequenceIdDao (DatabaseRepository<SequenceId, PartitionKey<String>>) │
  │    ├── RapidReservationDao (DatabaseRepository<RapidReservation, Composite>)│
  │    ├── TemplateDao (DatabaseRepository<Template, Composite>)               │
  │    ├── TemplateSummaryDao (DatabaseRepository<TemplateSummary, Composite>) │
  │    ├── SpotRatesDao (DatabaseRepository<SpotRatesDetail, Partition>)       │
  │    └── SpotRatesToInttraRefDao                                              │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 3. BookingMessagingModule (BookingConfig)                                   │
  │    Provides (all @Singleton):                                               │
  │    ├── MessagingClient<String>  (SQS via MessagingClientFactory)           │
  │    ├── NotificationService      (SNS via NotificationClientFactory, topicARN)│
  │    └── StorageClient            (S3 via StorageClientFactory)              │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 4. BookingApplicationModule (Environment)                                   │
  │    Registers XSSInterceptor and XSSFilter with Jersey                       │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 5. LocalCacheModule (Environment)                                           │
  │    Provides 16 named Guava LoadingCache singletons:                        │
  │    @Named("GEOGRAPHY_CACHE")           → ServiceCache<GeographyCacheKey, Geography>     │
  │    @Named("COUNTRY_CACHE")             → ServiceCache<CountryCacheKey, Country>        │
  │    @Named("PARTICIPANT_CACHE")         → ServiceCache<String, NetworkParticipant>      │
  │    @Named("CONTAINER_TYPE_CACHE")      → ServiceCache<String, ContainerType>           │
  │    @Named("CONTAINER_TYPE_BY_CATEGORY_CACHE") → ServiceCache<ContainerTypeCategoryCacheKey, List<ContainerType>> │
  │    @Named("PACKAGE_TYPE_CACHE")        → ServiceCache<PackageTypeCacheKey, PackageType>│
  │    @Named("ALIAS_CACHE")               → ServiceCache<ParticipantAliasCacheKey, Alias> │
  │    @Named("MULTIPLE_ALIAS_CACHE")      → ServiceCache<ParticipantAliasCacheKey, List<Alias>> │
  │    @Named("PARTICIPANT_CHILDREN_CACHE")→ ServiceCache<String, List<ParticipantHierarchy>> │
  │    @Named("PARTNER_CUSTOM_LOCATION_CACHE") → ServiceCache<PartnerCustomLocationCacheKey, Geography> │
  │    @Named("SUBSCRIPTION_CACHE")        → ServiceCache<String, List<Subscription>>      │
  │    @Named("EDIID_SUBSCRIPTION_CACHE")  → ServiceCache<String, List<Subscription>>      │
  │    @Named("OV_CACHE")                  → ServiceCache<String, List<OptionalValidation>>│
  │    @Named("USER_CACHE")                → ServiceCache<String, User>                    │
  │    @Named("DGS_DETAILS_CACHE")         → ServiceCache<String, DGSDetails>              │
  │    @Named("DGS_SEARCH_CACHE")          → ServiceCache<String, List<DGSDetails>>        │
  │    @Named("PARTICIPANT_ADDON_CACHE")   → ServiceCache<ParticipantAddOnCacheKey, List<ParticipantAddOn>> │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 6. MetricsInstrumentationModule (Dropwizard MetricRegistry)                 │
  │    Instruments @Timed, @Metered, @Gauge, @ExceptionMetered annotations     │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 7. JestModule (ElasticsearchConfig)                                         │
  │    Provides Jest HttpClientConfig + JestClient for Elasticsearch 6.x       │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 8. SystemUTCClockModule                                                     │
  │    Binds java.time.Clock → Clock.systemUTC()                                │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 9. BookingEmailSenderModule (BookingConfig, Environment)                    │
  │    Provides EmailClientFactory (cloud-sdk SES v2) with email templates      │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 10. OutboundServiceModule (AppianWayConfig, Environment)                   │
  │     If outboundEnabled = true:                                              │
  │       ExecutorService "outbound" (32 threads, ArrayBlockingQueue(60))      │
  │       OutboundService → OutboundServiceImpl                                 │
  │       EventPublisher  → SNSEventPublisher                                   │
  │     Else:                                                                   │
  │       OutboundService → DummyOutboundService                                │
  │       EventPublisher  → DummyEventPublisher                                 │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │ 11. InboundServiceModule (Environment)                                      │
  │     ExecutorService "processor" (8 threads, SynchronousQueue,              │
  │                                   CallerRunsPolicy, 30s shutdown)           │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. REST API Summary

All resources are registered under the Dropwizard application path (`/booking` as per swagger basePath).

### CustomerBookingResource — `@Path("/")`

| Method | Path | Role Required | Request Body | Response | Description |
|---|---|---|---|---|---|
| GET | `/{inttraReferenceId}` | Authenticated | — | `List<BookingDetail>` | Retrieve all versions of a booking by INTTRA ref |
| POST | `/request` | `BOOKING_RAC` | `BookingRequestContract` | `BookingResult` (201) | Submit a new booking request |
| POST | `/{inttraReferenceId}/amend` | `BOOKING_RAC` | `BookingRequestContract` (state=AMEND) | `BookingResult` | Amend an existing submitted booking |
| POST | `/{inttraReferenceId}/cancel` | `BOOKING_RAC` | `CancelRequest` | `BookingResult` | Cancel a booking |
| DELETE | `/{inttraReferenceId}` | `BOOKING_ADMIN` | — | `BookingResult` | Delete all booking versions (admin only) |
| GET | `/ov/{carrierId}` | Authenticated | — | `List<String>` | List optional validations for carrier/route/channel |

### CarrierBookingResource — `@Path("/")`

| Method | Path | Role Required | Request Body | Response | Description |
|---|---|---|---|---|---|
| POST | `/{inttraReferenceId}/confirm` | `BOOKING_CPD` | `ConfirmPendingMessage` | `BookingResult` | Carrier confirms a booking |
| POST | `/{inttraReferenceId}/confirm/validate` | `BOOKING_ADMIN` | `ConfirmPendingMessage` | `ValidationContext` | Validate confirm, no state change |
| POST | `/{inttraReferenceId}/acknowledge` | `BOOKING_CPD` | `ConfirmPendingMessage` | `BookingResult` | Carrier acknowledges (PENDING) a booking |
| POST | `/{inttraReferenceId}/acknowledge/validate` | `BOOKING_ADMIN` | `ConfirmPendingMessage` | `ValidationContext` | Validate acknowledge, no state change |
| POST | `/{inttraReferenceId}/decline` | `BOOKING_CPD` | `DeclineRequest` | `BookingResult` | Carrier declines a booking |
| POST | `/{inttraReferenceId}/decline/validate` | `BOOKING_ADMIN` | `ConfirmPendingMessage` | `ValidationContext` | Validate decline, no state change |
| POST | `/{inttraReferenceId}/replace` | `BOOKING_CPD` | `DeclineReplaceMessage` | `BookingResult` | Carrier replaces (split-replace) a booking |
| POST | `/{inttraReferenceId}/replace/validate` | `BOOKING_ADMIN` | `ConfirmPendingMessage` | `ValidationContext` | Validate replace, no state change |
| POST | `/{inttraReferenceNumber}/s3archive` | Authenticated | — | `List<String>` | Archive booking to S3 |

### SearchResource — `@Path("/search")`

| Method | Path | Role Required | Description |
|---|---|---|---|
| GET | `/search/{inttraReferenceId}` | Authenticated | Get booking by INTTRA ref via Elasticsearch |
| GET | `/search` | Authenticated | Full-text / filtered booking search |
| POST | `/search` | Authenticated | POST-body search with complex filters |
| GET | `/search/aggregations` | Authenticated | Booking status/count aggregations |

### OutboundResource — `@Path("/outbound")`

| Method | Path | Role Required | Description |
|---|---|---|---|
| GET | `/outbound/{inttraReferenceId}` | Authenticated | Retrieve enriched booking detail |
| POST | `/outbound/{inttraReferenceNumber}/reprocess` | `BOOKING_ADMIN` | Reprocess outbound notifications for a booking version |
| POST | `/outbound/{inttraReferenceNumber}/email` | `BOOKING_ADMIN` | Reprocess outbound email for a booking version |
| POST | `/outbound/{inttraReferenceNumber}/aperak` | `BOOKING_ADMIN` | Reprocess Aperak for a booking version |

### TemplateResource — `@Path("/template")`

| Method | Path | Description |
|---|---|---|
| GET | `/template` | List template summaries for authenticated company |
| GET | `/template/{templateId}` | Get a specific template |
| POST | `/template` | Save / update a booking template |
| DELETE | `/template/{templateId}` | Delete a template |

### RapidReservationResource — `@Path("/rapidreservation")`

| Method | Path | Role Required | Description |
|---|---|---|---|
| GET | `/rapidreservation` | Authenticated | List rapid reservation series |
| POST | `/rapidreservation` | Authenticated | Create or update a series |
| DELETE | `/rapidreservation/{seriesId}` | Authenticated | Delete a series |

### CarrierSpotRatesResource — `@Path("/spotrates")`

| Method | Path | Description |
|---|---|---|
| GET | `/spotrates` | Fetch spot rates from Maersk API for given route/equipment |

### DangerousGoodsResource — `@Path("/dgs")`

| Method | Path | Description |
|---|---|---|
| GET | `/dgs/{undgNumber}` | Get DGS details by UNDG number |
| GET | `/dgs/search` | Search DGS by UNDG number prefix |

### HTTP Exception → HTTP Status Mapping

| Exception | HTTP Status |
|---|---|
| `BookingNotFoundException` | 404 Not Found |
| `NotFoundException` | 404 Not Found |
| `DBRecordNotFoundException` | 404 Not Found |
| `JsonProcessingException` | 400 Bad Request |
| `IllegalArgumentException` | 400 Bad Request |
| `IllegalStateException` | 409 Conflict |
| `ForbiddenException` | 403 Forbidden |
| `AuthorizationException` | 403 Forbidden |
| `ResolutionException` | 422 Unprocessable Entity |
| `StateTransitionException` | 422 Unprocessable Entity |
| `BookingValidationException` | 422 Unprocessable Entity |
| `Exception` / `RuntimeException` | 500 Internal Server Error |

---

## 13. Validation Rules Summary

Validation is orchestrated by `ValidationService.validate()` which populates a `ValidationContext` object. The context is then inspected for errors before any state change is persisted.

### Structural Validation (Deserialization-time)

Applied during JSON deserialization of the canonical booking payload:

| Rule | Class | Description |
|---|---|---|
| Enum tolerance | `EnumDeserializer` | Unknown enum values are null-coerced with a `ValidationError` rather than thrown as a parse exception |
| Number tolerance | `NumberDeserializer` | Non-numeric strings in number fields are null-coerced with a `ValidationError` |

### Header Validations

| Area | Class | Sample Rules |
|---|---|---|
| Common headers | `HeaderValidations` (confirmation) | inttraRef format, booking state present |
| Header locations | `HeaderLocationValidations` | Port codes, UNLOC codes, dates |
| Cargo | `CargoValidations` | Weight, volume, commodity code |
| Equipment | `EquipmentValidations` | ISO container type, temperature ranges, OOG dimensions |
| Legs | `LegValidations` | Vessel, voyage, ETD/ETA consistency |
| Party | `PartyValidations` | Required party roles, INTTRA company ID resolution |
| References | `ReferenceValidations` | B/L number, booking number formats |
| Decline/Cancel headers | `HeaderValidations` (decline) | Comments, dates |
| Decline/Cancel comments | `CommentValidations` | Comment length, mandatory fields |

### Business Validations (ValidationService)

| Validation | Description |
|---|---|
| Carrier resolution | Carrier party must resolve to a known INTTRA network participant |
| Booker resolution | Booker party must resolve to a known INTTRA network participant |
| Party access control | Principal's company ID must have access to the booking |
| State transition legality | `BookingState.calcTransition()` must not return a `Failure` |
| Reinstatement uniqueness | OCBN / ShipmentId must be unique when reinstating from CANCEL/DECLINE (ION-9016) |
| Non-INTTRA booking rules | NIB confirm cannot be PENDING; carrier must be enabled for NIB |

### Carrier-Specific Optional Validations

Managed by `OptionalValidationsService` (cached with 30-min TTL):

- Rules are configured per carrier (by INTTRA company ID) and can be scoped by trade lane (place of receipt / delivery location codes) and channel.
- Rules use a `Condition` model with `ConditionEvaluator` supporting operators: `EQUALS`, `NOT_EQUALS`, `IN`, `NOT_IN`, `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`.
- `ValidationType` can be `ERROR` (blocks the booking) or `WARNING` (advisory, recorded in `ValidationContext`).
- `ModuleType` indicates which booking section the rule applies to (e.g., `CARGO`, `EQUIPMENT`, `HEADER`).

### DGS (Dangerous Goods) Validation Rules

Implemented in the `dgs.validation` package via a `DGSRulesFactory` and individual `DGSCargoRule` implementations:

| Rule | Class | Description |
|---|---|---|
| End-of-holding | `DGSEndOfHoldingRule` | Validates end-of-holding date requirements |
| Explosive cargo | `DGSExplosiveCargoRule` | Class 1 explosives special handling |
| Fireworks classification | `DGSFireworksClassification` | Fireworks class 1.4G / 1.4S classification |
| Medium-danger packing flash temp | `DGSMedDangerPackingGrpFlashTempRule` | Packing group II flash point requirements |
| Minor-danger packing flash temp | `DGSMinorDangerPackingGrpFlashTempRule` | Packing group III flash point requirements |
| Minor-danger viscous | `DGSMinorDangerPackingGrpFlashTempViscousRule` | Viscous liquid exception for packing group III |
| Technical name required | `DGSTechnicalNameReqdRule` | Technical name mandatory for certain hazardous classes |
| Equipment fumigation | `DGSEquipmentFumigationRule` | Fumigation marking requirements |

### Temperature Validation

`TemperatureFormatValidationAndConversion` handles:
- Conversion between Celsius and Fahrenheit
- Format validation (e.g., `+/- degrees with decimal`)
- Min/max temperature range validation for reefer containers

---

## 14. Design Patterns

| Pattern | Where Applied | Details |
|---|---|---|
| **Command / Strategy** | `BookingService` operations | Each booking operation (`request`, `confirm`, `amend`, etc.) is a distinct method encapsulating complete domain logic. `BookingProcessorTask.BookingServiceFunction` is a functional interface enabling strategy-based dispatch. |
| **State Machine** | `BookingState` enum | Static transition table (HashMap of `Transition → TransitionResult`) encodes all valid state transitions at startup. `calcTransition()` enforces the state machine at runtime. |
| **Repository** | `BookingDetailDao`, all `*Dao` classes | Thin facade over `cloud-sdk DatabaseRepository<T, K>`; hides DynamoDB SDK 2.x details and GSI query strategy. |
| **Cache-Aside** | All network service `*CacheImpl` classes | Guava `LoadingCache` with TTL per domain. On cache miss, delegates to underlying `*Impl` which calls `NetworkServiceClient`. Cache metrics exposed to Dropwizard MetricRegistry. |
| **Factory Method** | `BookingDynamoModule`, `BookingMessagingModule` | `@Provides @Singleton` Guice provider methods act as factory methods for all AWS SDK 2.x clients and repositories. |
| **Decorator** | `OptionalValidationServiceCacheImpl`, `DGSServiceCacheImpl`, etc. | Each `CacheImpl` wraps the real `*Impl` and intercepts calls to serve from cache. |
| **Observer / Event** | `BookingEventRelay`, `SNSEventPublisher` | Domain events (`bookingWasCreated`, `bookingWasUpdated`) published to SNS after successful persistence. |
| **Mediator** | `ValidationContext` | Carries all resolved domain objects (actor, booking, parties, location info, validation errors) across the validation pipeline without direct coupling between validators. |
| **Template Method** | Email variable converters | `VariablesConverterSupport` provides common conversion logic; state-specific subclasses (`RequestAmendEmailVariablesConverter`, `ConfirmPendingEmailVariablesConverter`, etc.) override only the variable-collection step. |
| **Builder** | `BookingDetail` (Lombok), `ValidationError.builder()`, `IndexedBooking` | Extensive use of Lombok `@Builder` for fluent construction of domain objects. |
| **Composite** | Elasticsearch query DSL | `CompositeQuery`, `Bool`, `Filter`, `Nested`, `HasChild`, etc. form a Composite tree that serialises to Elasticsearch query JSON. |
| **Chain of Responsibility** | `DGSRulesFactory` / cargo/equipment rules | `DGSRulesFactory` selects applicable rules; each rule independently evaluates and appends errors to the context. |
| **Circuit Breaker** | `ExternalCallWrapper` (Hystrix) | Wraps all outbound HTTP calls to Network Services with Hystrix `GenericHystrixCommandWithCallable`; configurable timeout and fallback. |
| **Retry** | `NetworkServiceClient`, `BookingService` DynamoDB writes | Guava Retrying library used in network calls; explicit retry loop (up to `dynamoExceptionMaxRetryCount`) for DynamoDB `DynamoDbException`. |
| **Idempotency / Deduplication** | `Booking.isEquivalent()` | Before persisting an update, payload equivalence is checked; duplicate messages are silently ignored. |
| **Proxy (AOP)** | `ExternalCallAnnotationListener` / `RetriableMethodInterceptor` | Guice AOP intercepts methods annotated with `@ExternalCall` to apply retry / circuit-breaker behaviour transparently. |

---

## 15. Local Guava Cache Configuration

All caches are `@Singleton` instances registered with Dropwizard's `MetricRegistry` for monitoring.

| Cache Name | Key Type | Value Type | TTL | Backing Service |
|---|---|---|---|---|
| `GEOGRAPHY_CACHE` | `GeographyCacheKey` | `Geography` | 30 min | `GeographyServiceImpl` |
| `COUNTRY_CACHE` | `CountryCacheKey` | `Country` | 24 hrs | `GeographyServiceImpl` |
| `PARTICIPANT_CACHE` | `String` (inttraCompanyId) | `NetworkParticipant` | 30 min | `NetworkParticipantServiceImpl` |
| `CONTAINER_TYPE_CACHE` | `String` (ISO code) | `ContainerType` | 30 min | `ReferenceDataServiceImpl` |
| `CONTAINER_TYPE_BY_CATEGORY_CACHE` | `ContainerTypeCategoryCacheKey` | `List<ContainerType>` | 30 min | `ReferenceDataServiceImpl` |
| `PACKAGE_TYPE_CACHE` | `PackageTypeCacheKey` | `PackageType` | 30 min | `ReferenceDataServiceImpl` |
| `ALIAS_CACHE` | `ParticipantAliasCacheKey` | `Alias` | 30 min | `ParticipantsAliasServiceImp` |
| `MULTIPLE_ALIAS_CACHE` | `ParticipantAliasCacheKey` | `List<Alias>` | 30 min | `ParticipantsAliasServiceImp` |
| `PARTICIPANT_CHILDREN_CACHE` | `String` (inttraCompanyId) | `List<ParticipantHierarchy>` | 30 min | `NetworkParticipantServiceImpl` |
| `PARTNER_CUSTOM_LOCATION_CACHE` | `PartnerCustomLocationCacheKey` | `Geography` | 30 min | `GeographyServiceImpl` |
| `SUBSCRIPTION_CACHE` | `String` (inttraCompanyId) | `List<Subscription>` | 30 min | `SubscriptionServiceImpl` |
| `EDIID_SUBSCRIPTION_CACHE` | `String` (ediId) | `List<Subscription>` | 30 min | `SubscriptionServiceImpl` |
| `OV_CACHE` | `String` (companyId) | `List<OptionalValidation>` | 30 min | `OptionalValidationsServiceImpl` |
| `USER_CACHE` | `String` (userId) | `User` | 30 min | `UserServiceImpl` |
| `DGS_DETAILS_CACHE` | `String` (undgNumber[-variant]) | `DGSDetails` | 24 hrs | `DGSServiceImpl` |
| `DGS_SEARCH_CACHE` | `String` (undgNumber prefix) | `List<DGSDetails>` | 24 hrs | `DGSServiceImpl` |
| `PARTICIPANT_ADDON_CACHE` | `ParticipantAddOnCacheKey` | `List<ParticipantAddOn>` | 30 min | `ParticipantAddOnServiceImpl` |

---

## 16. Configuration Properties Reference

All properties live in the Dropwizard YAML configuration file (`conf/pullRequest/config.yaml` for integration tests). The root class is `BookingConfig extends ApplicationConfiguration`.

| Property Path | Type | Description |
|---|---|---|
| `dynamoDbConfig` | `BaseDynamoDbConfig` | DynamoDB endpoint, region, table prefix, consistent read flag |
| `elasticsearchConfig` | `ElasticsearchConfig` | Elasticsearch cluster URL(s), index name |
| `s3ArchiveBucket` | String | S3 bucket name for booking JSON archiving |
| `appianWayConfig.s3WorkSpaceLocation` | String | S3 bucket/prefix for Appian Way workspace files |
| `appianWayConfig.transformerSQSUrl` | String | URL of SQS queue feeding the Contivo transformer |
| `appianWayConfig.inQueueUrl` | String | URL of SQS queue for inbound processed bookings |
| `appianWayConfig.distributorQueueUrl` | String | URL of SQS queue for outbound EDI distribution |
| `appianWayConfig.snsTopicARN` | String | ARN of SNS topic for booking lifecycle events |
| `appianWayConfig.waitTimeSeconds` | int | SQS long-poll wait time (0=short poll, 1-20=long poll) |
| `appianWayConfig.maxNumberOfMessages` | int | Max SQS messages per poll (1-10) |
| `appianWayConfig.parallelism` | int | Listener parallelism hint |
| `appianWayConfig.listenerEnabled` | boolean | Whether to start the SQS listener on startup |
| `appianWayConfig.outboundEnabled` | boolean | Whether outbound processing is active (false → DummyOutboundService) |
| `watermillConfig.aperakWatermillSQS` | String | SQS URL for Aperak (functional acknowledgement) watermill |
| `emailSenderConfig` | `BookingEmailConfig` | SES sender address, reply-to, template configuration |
| `customizationConfig` | `CustomizationConfig` | Carrier-specific EDI customisation flags (e.g., Heineken, special-char) |
| `inttraRefConfig` | `Map<String, List<String>>` | Configuration for INTTRA reference number generation by carrier |
| `spotRatesConfig` | `SpotRateConfig` | Maersk API endpoint, connect/read timeout, carrier configurations |
| `cargoScreenTrialPeriod` | String ("true"/"false") | Enable cargo screening trial period logic |
| `nonInttraEnabled` | String | Enable Non-INTTRA Booking (NIB) processing |
| `bookingAppIdentity` | String | "INTTRA" or "NON_INTTRA" — determines NIB routing |
| `useSequenceId` | String | Flag for sequence ID vs UUID reference generation |
| `removeNestedEmailTag` | boolean | Strip nested email tags from EDI output |
| `maxRetries` | int (max 5, default 3) | Max retry attempts for external HTTP calls |
| `maxDelay` | int (default 10000 ms) | Maximum retry back-off delay |
| `baseDelay` | int (default 100 ms) | Base retry back-off delay |
| `dynamoExceptionMaxRetryCount` | int | Max DynamoDB write retries on `DynamoDbException` |
| `bookingBridgeSQS` | String | SQS URL for routing legacy bookings to the booking bridge |
| `enableSwaggerUI` | boolean (default false) | Expose Swagger UI at `/swagger-ui` |

---

## 17. Inter-Service Communication

```
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                  BOOKING SERVICE — EXTERNAL DEPENDENCIES                     │
  └─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  Mercury NETWORK API                  │  ← HTTP (NetworkServiceClient + Hystrix)
  │  (Internal Microservice)              │
  │  Provides:                            │
  │  - Network Participants (companies)   │  → NetworkParticipantService
  │  - Participant Aliases                │  → ParticipantsAliasService
  │  - Subscriptions                      │  → SubscriptionService
  │  - Geography (UNLOC, ports, countries)│  → GeographyService
  │  - Reference Data (containers, pkgs)  │  → ReferenceDataService
  │  - Integration Profiles / Formats     │  → IntegrationProfileFormatService
  │  - Partnerships                       │  → PartnershipService
  │  - User details                       │  → UserService
  │  - Participant Add-Ons                │  → ParticipantAddOnService
  │  - Optional Validations               │  → OptionalValidationsService
  │  - DGS (Dangerous Goods) details      │  → DGSService
  │  - Blacklist email list               │  → BlacklistEmailService
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  Mercury AUTH API                     │  ← HTTP (AuthClient)
  │  JWT token validation / refresh       │  Provides InttraPrincipal resolution
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  Maersk Spot Rates API               │  ← HTTP (Jersey Client, @Named("spotRateClient"))
  │  External carrier API                │  → MaerskApiClient → CarrierSpotRatesService
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  AWS SQS                              │  ← AWS SDK 2.x (cloud-sdk MessagingClient)
  │  - inQueueUrl        (receive)        │
  │  - distributorQueueUrl (send)         │
  │  - bookingBridgeSQS  (send)           │
  │  - aperakWatermillSQS (send)          │
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  AWS SNS                              │  ← AWS SDK 2.x (cloud-sdk NotificationService)
  │  Booking lifecycle event topic        │  → SNSEventPublisher
  │  Subscribers: Track & Trace, BI,      │
  │  downstream analytics, etc.           │
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  AWS S3                               │  ← AWS SDK 2.x (cloud-sdk StorageClient)
  │  - Workspace bucket (read/write)      │  → S3WorkspaceService
  │  - Archive bucket (write)             │  → S3ArchiveHandler
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  AWS DynamoDB                         │  ← AWS SDK 2.x (cloud-sdk DatabaseRepository)
  │  All booking state persistence        │
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  AWS SES v2                           │  ← AWS SDK 2.x (cloud-sdk EmailClientFactory)
  │  Booking notification emails          │  → OutboundEmailSender
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  Elasticsearch 6.x                    │  ← Jest HTTP client
  │  Read: booking search queries         │  → Searcher
  │  Write: via IndexerHandler Lambda     │  → Indexer / IndexerHandler
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  Appian Way (Contivo) Pipeline        │  ← Asynchronous via SQS + S3
  │  EDI transformation engine            │
  │  Inbound: raw EDI → canonical JSON    │
  │  Outbound: canonical JSON → EDI       │
  └──────────────────────────────────────┘

  ┌──────────────────────────────────────┐
  │  WebHook endpoints (Party-configured) │  ← HTTP POST (WebHookService)
  │  Party-defined URLs for push          │
  │  booking notifications                │
  └──────────────────────────────────────┘
```

---

## 18. Lambda Functions

The booking module produces a secondary `booking-lambdas-{version}.jar` (shade-lambda execution, ~smaller footprint) containing:

### IndexerHandler

| Property | Detail |
|---|---|
| Trigger | DynamoDB Streams on `BookingDetail` table (KEYS\_ONLY) |
| Class | `com.inttra.mercury.booking.lambda.IndexerHandler` |
| Purpose | Reads changed `BookingDetail` record from main table and upserts/deletes corresponding Elasticsearch `IndexedBooking` document |
| Dependencies | `BookingDetailDao` (DynamoDB SDK 2.x), `Indexer` (Jest), `Searcher` |
| Pattern | Pull-from-stream + consistent-read from DynamoDB → index to Elasticsearch |

### S3ArchiveHandler

| Property | Detail |
|---|---|
| Trigger | On-demand (via REST `POST /{inttraReferenceNumber}/s3archive`) or internal call |
| Class | `com.inttra.mercury.booking.lambda.S3ArchiveHandler` |
| Purpose | Serialises all `BookingDetail` versions for a given booking to individual JSON files in S3 archive bucket |
| Dependencies | `BookingDetailDao`, `StorageClient` (S3) |

### TrackAndTraceService / ReportBridgeMessage

Supporting classes in the lambda package used by the indexer for sending Track & Trace events from the Lambda context.

---

## Appendix: Sequence Number Format

The DynamoDB sort key (`sequenceNumber`) follows the format:

```
  m_{epochMilliseconds}_{BookingState}_{inttraReferenceNumber}
  Example: m_1714857600000_CONFIRM_2000001234
```

This format enables:
- Lexicographic ordering of versions (newest = highest sort key)
- Direct extraction of booking state without fetching the full item
- Efficient `findLatestCarrierAndCustomerVersions` by filtering on state prefix segment

---

*Document generated by automated code analysis of the booking module source tree. Last analyzed commit: develop branch, 2026-05-04.*
