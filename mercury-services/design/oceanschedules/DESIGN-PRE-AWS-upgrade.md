# Ocean Schedules Module — Design & Architecture Document

> **Purpose**: Comprehensive pre-AWS-SDK-upgrade design document capturing the current state of the `oceanschedules` and `oceanschedules-process` modules.  
> **Date**: April 27, 2026  
> **AWS SDK Status**: v1 (upgrade NOT STARTED)  

---

## Table of Contents

- [Ocean Schedules Module — Design \& Architecture Document](#ocean-schedules-module--design--architecture-document)
  - [Table of Contents](#table-of-contents)
  - [1. Overview](#1-overview)
  - [2. Architecture Principles](#2-architecture-principles)
  - [3. Module Structure](#3-module-structure)
    - [oceanschedules (API Module)](#oceanschedules-api-module)
    - [oceanschedules-process (Batch Pipeline)](#oceanschedules-process-batch-pipeline)
  - [4. Technology Stack](#4-technology-stack)
  - [5. Component Deep Dive — oceanschedules (API)](#5-component-deep-dive--oceanschedules-api)
    - [5.1 Application Bootstrap](#51-application-bootstrap)
    - [5.2 Configuration](#52-configuration)
    - [5.3 Guice Dependency Injection](#53-guice-dependency-injection)
    - [5.4 REST Resources (API Layer)](#54-rest-resources-api-layer)
    - [5.5 Service Layer](#55-service-layer)
      - [`ScheduleSearchService` — Core Search Orchestrator](#schedulesearchservice--core-search-orchestrator)
      - [`InttraScheduleCollector` — Data Source Router](#inttraschedulecollector--data-source-router)
      - [`EnrichmentService` — Data Enrichment Pipeline](#enrichmentservice--data-enrichment-pipeline)
      - [`CarrierService` — Carrier \& Port-Pair Management](#carrierservice--carrier--port-pair-management)
      - [`OSProcessService` — Pipeline Trigger](#osprocessservice--pipeline-trigger)
      - [`CutoffOffsetService` — Cutoff Date Lookup (Cached)](#cutoffoffsetservice--cutoff-date-lookup-cached)
      - [`RecentSearchService` — User Search History](#recentsearchservice--user-search-history)
      - [`UserPreferenceService` / `VesselDetailsService` — Simple CRUD](#userpreferenceservice--vesseldetailsservice--simple-crud)
    - [5.6 Client Layer](#56-client-layer)
      - [External Carrier API Clients](#external-carrier-api-clients)
      - [Network Services Clients](#network-services-clients)
      - [Timezone Client](#timezone-client)
    - [5.7 Persistence Layer](#57-persistence-layer)
    - [5.8 DynamoDB Models](#58-dynamodb-models)
      - [`RealTimeCache`](#realtimecache)
      - [`SchedulesProStaging`](#schedulesprostaging)
    - [5.9 Domain Models](#59-domain-models)
      - [`InttraSchedule` — Canonical Schedule Model](#inttraschedule--canonical-schedule-model)
      - [`InttraLeg` — Schedule Leg Model](#inttraleg--schedule-leg-model)
      - [`VesselDetails` — Vessel Information](#vesseldetails--vessel-information)
      - [`CutoffOffset` — Terminal Cutoff Configuration](#cutoffoffset--terminal-cutoff-configuration)
    - [5.10 Exception Handling](#510-exception-handling)
    - [5.11 Utility Classes](#511-utility-classes)
  - [6. Component Deep Dive — oceanschedules-process (Batch Pipeline)](#6-component-deep-dive--oceanschedules-process-batch-pipeline)
    - [6.1 Common (Shared Library)](#61-common-shared-library)
    - [6.2 Collector](#62-collector)
    - [6.3 Inbound](#63-inbound)
    - [6.4 Staging](#64-staging)
    - [6.5 Aggregator](#65-aggregator)
    - [6.6 Loader](#66-loader)
    - [6.7 Outbound](#67-outbound)
    - [6.8 Port-Pair-Generator](#68-port-pair-generator)
    - [6.9 Maps](#69-maps)
  - [7. Data Flow Architecture](#7-data-flow-architecture)
    - [End-to-End Pipeline](#end-to-end-pipeline)
    - [API Schedule Search Flow (Runtime)](#api-schedule-search-flow-runtime)
  - [8. AWS Services Usage](#8-aws-services-usage)
    - [DynamoDB Table Schemas](#dynamodb-table-schemas)
  - [9. External Carrier Integrations](#9-external-carrier-integrations)
  - [10. Security \& Access Control](#10-security--access-control)
    - [OAuth2 Authentication](#oauth2-authentication)
    - [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
    - [Carrier API Credential Management](#carrier-api-credential-management)
  - [11. Maven Dependencies](#11-maven-dependencies)
    - [oceanschedules (API Module)](#oceanschedules-api-module-1)
    - [oceanschedules-process Sub-Module Dependencies](#oceanschedules-process-sub-module-dependencies)
  - [12. Test Strategy](#12-test-strategy)
    - [Framework \& Tooling](#framework--tooling)
    - [Test Coverage](#test-coverage)
    - [Test Patterns](#test-patterns)
    - [Assertion Style](#assertion-style)
    - [SonarQube Coverage Exclusions](#sonarqube-coverage-exclusions)
  - [13. Configuration \& Environments](#13-configuration--environments)
    - [Environment Matrix](#environment-matrix)
    - [Key Configuration Sections](#key-configuration-sections)
    - [SQL DDL Scripts (MySQL)](#sql-ddl-scripts-mysql)
  - [14. Build \& Deployment](#14-build--deployment)
    - [Build Process](#build-process)
    - [Maven Build Plugins](#maven-build-plugins)
    - [Shade Plugin Configuration](#shade-plugin-configuration)
    - [Runtime Execution](#runtime-execution)
    - [OWASP Dependency Check](#owasp-dependency-check)
  - [15. Critical Review](#15-critical-review)
    - [What Is Good](#what-is-good)
    - [What Is Bad](#what-is-bad)
    - [What Can Be Improved](#what-can-be-improved)

---

## 1. Overview

The Ocean Schedules system provides a real-time ocean shipping schedule search and management platform. It aggregates schedule data from **35+ ocean carriers** and serves **15M+ schedules** to users via a REST API and downstream data feeds.

The system is split into two main modules:

| Module | Purpose | Runtime |
|--------|---------|---------|
| `oceanschedules` | REST API — schedule search, carrier management, user preferences, vessel details | Dropwizard HTTP server |
| `oceanschedules-process` | Batch pipeline — data ingestion, transformation, indexing, and export | Spark jobs + Dropwizard services, SQS-driven |

The API module queries Elasticsearch for indexed schedules and falls back to real-time external carrier APIs. The process module handles the ETL pipeline that keeps Elasticsearch populated with up-to-date schedule data.

---

## 2. Architecture Principles

1. **Data Source Abstraction**: Schedule data is fetched from two sources — Elasticsearch (pre-indexed EDI/API data) and direct carrier APIs — with a unified `InttraSchedule` canonical model.

2. **Carrier Pluggability**: Each external carrier integration is encapsulated behind the `PortPairRequestBuilder` interface and registered via Guice multibinding, enabling new carriers to be added without modifying core logic.

3. **Layered Architecture**: Strict separation of Resources (REST) → Services (Business Logic) → Clients (External APIs / ES) → Persistence (DAO/Mapper).

4. **Event-Driven Processing**: The batch pipeline uses SNS/SQS for inter-module communication, enabling loose coupling between processing stages.

5. **Caching Strategy**: Guava `LoadingCache` is used for geography, timezone, carrier data, and cutoff offsets. DynamoDB `RealTimeCache` provides a distributed cache for real-time API responses.

6. **Configuration-Driven External Services**: Carrier API endpoints, authentication, retry policies, and caching behavior are all driven by YAML configuration, not hard-coded.

---

## 3. Module Structure

### oceanschedules (API Module)

```
oceanschedules/
├── pom.xml                    # Maven build (artifactId: ocean-schedules)
├── ApplicationConfig.yml      # Template config
├── securityDefinition.json    # OAuth2 security definition
├── build.sh / build_pr.sh     # Build scripts (CI + PR)
├── run.sh                     # Docker runtime script
├── suppressions.xml           # OWASP CVE suppressions
├── conf/
│   ├── int/   config.yaml     # Integration environment
│   ├── qa/    config.yaml     # QA environment
│   ├── cvt/   config.yaml     # CVT environment
│   └── prod/  config.yaml     # Production environment
├── swagger/                   # API documentation (apiinfo.json, apiauth.json)
├── generated/swagger-ui/      # Generated OpenAPI spec
├── src/main/java/.../oceanschedules/
│   ├── OceanSchedulesApplication.java   # Entry point
│   ├── config/          # 12 configuration classes
│   ├── module/          # Guice module + AWS client config
│   ├── resources/       # 7 JAX-RS resource classes
│   ├── service/         # 8 service classes
│   ├── client/          # ~40 client classes (external, network, timezone)
│   ├── persistence/     # 5 sub-packages (DAO, mapper, model)
│   ├── dynamodb/        # 3 DynamoDB model/support classes
│   ├── model/           # 4 domain model classes
│   ├── exception/       # 5 exception classes
│   ├── controller/      # 4 exception mapper classes
│   └── util/            # 10 utility classes (AWS, S3, SNS, validation)
├── src/main/resources/
│   └── com/inttra/mercury/db/scripts/  # SQL DDL scripts
└── src/test/
    ├── java/   (59 test classes)
    └── resources/  (test config + ES payload fixtures)
```

**Total**: ~132 production Java classes, ~59 test classes.

### oceanschedules-process (Batch Pipeline)

```
oceanschedules-process/
├── common/          # Shared library (~204 Java files)
├── collector/       # Scheduled API polling service (Dropwizard)
├── inbound/         # EDIFACT/ANSI parser (Spark batch)
├── staging/         # Staging transformer (Spark batch)
├── aggregator/      # Multi-source aggregator (Spark + DynamoDB)
├── loader/          # Elasticsearch indexer (Spark + Jest)
├── outbound/        # Export processor — EDIFACT/ANSI/CSV/XML (Spark)
├── port-pair-generator/  # Port-pair route discovery (Dropwizard)
└── maps/            # EDIFACT/ANSI mapping schemas (.xbm files)
    ├── inbound/     # Input format schemas
    └── outbound/    # Output format schemas
```

---

## 4. Technology Stack

| Category | Technology | Version | Notes |
|----------|-----------|---------|-------|
| **JDK** | Java | 17 | `maven.compiler.release=17` |
| **Framework** | Dropwizard | 4.0.16 | JAX-RS (Jersey), Jackson, Jetty |
| **DI** | Google Guice | (via Dropwizard) | Module-based binding |
| **Build** | Maven | 3.x | Shaded JAR packaging |
| **AWS SDK** | AWS SDK v1 | 1.12.558–1.12.773 | **Pre-upgrade — v2 migration pending** |
| **Elasticsearch** | Elasticsearch | 6.8.13 (API) / 8.6.2 (Loader) | Via Jest client 6.3.1 |
| **Database** | MySQL (AWS RDS) | — | MyBatis 3.x ORM |
| **DynamoDB** | AWS DynamoDB | v1 SDK | Tables: `os_realtime_cache`, `schedules_pro_staging` |
| **Messaging** | AWS SNS + SQS | v1 SDK | Inter-module orchestration |
| **Storage** | AWS S3 | v1 SDK | Schedule files, exports |
| **Batch** | Apache Spark | 3.5.3 | With Hadoop 3.3.4 |
| **Serialization** | Jackson | 2.19.2 | JSON, CSV, XML formats |
| **Caching** | Guava LoadingCache | 33.x | In-memory with TTL |
| **Auth (JWT)** | jjwt | 0.11.2 | API token validation |
| **Logging** | SLF4J + Logback | — | MDC for request tracing |
| **Code Gen** | Lombok | 1.18.30 | `@Data`, `@Builder`, `@Slf4j` |
| **API Docs** | Swagger 1.5 | 1.5.22 | Maven plugin generation |
| **Testing** | JUnit 5 (Jupiter) | 5.10.1 | With Mockito 5.8.0 |

---

## 5. Component Deep Dive — oceanschedules (API)

### 5.1 Application Bootstrap

**Entry Point**: `OceanSchedulesApplication` (extends Dropwizard `Application<OceanSchedulesConfig>`)

Uses the `InttraServer.builder()` pattern from the commons library to:

- Register **7 REST resources**: `ScheduleResource`, `RecentSearchResource`, `VesselDetailsResource`, `UserPreferenceResource`, `SubscribedCarrierResource`, `CarrierResource`, `OSProcessResource`
- Register **5 MyBatis mappers**: `DatabaseHealthCheckMapper`, `UserDataMapper`, `ScheduleVesselDetailsMapper`, `ScheduleCutoffOffsetMapper`, `PortPairMapper`
- Register **4 exception mappers**: `RequestExceptionMapper`, `ServiceExceptionMapper`, `SecurityExceptionMapper`, `UnrecognizedPropertyExceptionMapper`
- Register `DynamoTableCommand` for DynamoDB table management
- Bind Guice module: `OceanschedulesModule`

### 5.2 Configuration

**Main Config**: `OceanSchedulesConfig` extends `ApplicationConfiguration`, implements `DatabaseAppConfig`

| Field | Type | Purpose |
|-------|------|---------|
| `database` | `DataSourceFactory` | MySQL RDS connection pool |
| `dynamoDbConfig` | `DynamoDbConfig` | DynamoDB environment/region |
| `surroundingPortMapping` | `Map<String,String>` | Nearby port associations |
| `s3Config` | `S3Config` | Bucket names and paths |
| `snsConfig` | `SNSConfig` | SNS topic ARNs (loader, outbound, staging, aggregator) |
| `elasticSearchConfig` | `ElasticSearchConfig` | ES endpoint, index names, timeouts, retries |
| `mercuryServiceDefinitions` | `List<ServiceDefinition>` | Internal service endpoints (auth, network, geography, etc.) |
| `externalServiceDefinitions` | `List<ExternalServiceDefinition>` | External carrier API configs |
| `mscAuthServiceDefinitions` | `MscAuthServiceDefinition` | MSC OAuth (client assertion, certificate) |
| `oneAuthServiceDefinitions` | `OneAuthServiceDefinition` | ONE alliance auth (basic auth + API key) |
| `zimAuthServiceDefinitions` | `ZimAuthServiceDefinition` | ZIM auth (OAuth2 client credentials) |
| `evergreenAuthServiceDefinitions` | `EvergreenAuthServiceDefinition` | Evergreen auth (bearer token) |

**Carrier-Specific Auth Configs**: Each carrier has a distinct authentication model:
- **MSC**: Client assertion with X.509 certificate hash
- **ONE**: Basic auth + API key
- **ZIM**: OAuth2 client credentials + OCP subscription key
- **Hapag-Lloyd**: IBM API gateway (client ID/secret + user/org/password)
- **Evergreen**: Static bearer authorization header
- **Timezone API**: OAuth2 client credentials

### 5.3 Guice Dependency Injection

**Module**: `OceanschedulesModule` extends `AbstractModule`

Key bindings in `configure()`:

| Binding | Target | SDK |
|---------|--------|-----|
| `AmazonSNS` | `AmazonSNSClientBuilder` with `sns_publish` config | AWS v1 |
| `AmazonS3` | `AmazonS3ClientBuilder` with `s3_read_put_copy` config | AWS v1 |
| `AmazonDynamoDB` | `DynamoSupport.newClient()` | AWS v1 |
| `DynamoDBMapper` | `DynamoSupport.newMapper()` | AWS v1 |
| `DynamoDBMapperConfig` | `DynamoSupport.newDynamoDBMapperConfig()` | AWS v1 |
| `JestModule` | Jest Elasticsearch client | — |
| `ServiceDefinition` (named) | From config YAML | — |
| `ExternalServiceDefinition` (named) | From config YAML | — |
| `Set<PortPairRequestBuilder>` | Multibinder for 12 carrier builders | — |

**AWS Client Configurations** (`AWSClientConfiguration.java`):

| Config Name | Retry | Timeout | Max Connections | Use Case |
|-------------|-------|---------|-----------------|----------|
| `s3_read_put_copy` | 3 | 5 min exec, 5 min socket | 100 | S3 operations |
| `sns_publish` | 3 | 10s exec, 5s socket | 50 | SNS publishing |
| `sqs_listener` | 3 | 1s connection | 50 | SQS polling |
| `sqs_sender` | 3 | 10s exec, 5s socket | 50 | SQS sending |

Retry strategy: Exponential backoff (500ms–5000ms) with custom `RetryCondition` that always returns `true`.

### 5.4 REST Resources (API Layer)

| Resource | Path | Methods | Roles | Injected Service |
|----------|------|---------|-------|-----------------|
| `ScheduleResource` | `/schedule` | `GET` | API_USER, USER, ADMIN | `ScheduleSearchService` |
| `RecentSearchResource` | `/recentsearches` | `GET`, `PUT` | USER | `RecentSearchService` |
| `VesselDetailsResource` | `/vesseldetails` | `GET` | USER, ADMIN | `VesselDetailsService` |
| `UserPreferenceResource` | `/user-preferences` | `GET`, `PUT` | USER | `UserPreferenceService` |
| `SubscribedCarrierResource` | `/apicarriers` | `GET` | USER, ADMIN | `CarrierService` |
| `CarrierResource` | `/carrier` | CRUD (9 methods) | USER, ADMIN | `CarrierService` |
| `OSProcessResource` | `/process-maintenance` | `POST`, `DELETE` | ADMIN | `OSProcessService` |

**Primary API — Schedule Search** (`GET /schedule`):

Query Parameters:
- `originPort` (required) — UN/LOCODE
- `destinationPort` (required) — UN/LOCODE
- `searchDate` (required) — yyyy-MM-dd
- `searchDateType` — ByDepartureDate, ByArrivalDate, ByCutOffDate
- `weeksOut` — Search window (default configurable)
- `scacs` — Carrier filter (comma-separated SCAC codes)
- `directOnly` — Filter transshipment routes
- `includeNearbyOriginPorts` / `includeNearbyDestinationPorts` — Include surrounding ports

**Carrier Port-Pair Management** (`/carrier/port-pair`):
- Full CRUD for carrier port-pair route configurations
- Supports `requestPayload` refresh for individual port-pairs
- Service enablement management (`/carrier/service-enablement`)

**Process Maintenance** (`/process-maintenance`):
- `POST /staging/start` — Trigger staging pipeline for carrier SCAC codes
- `POST /loader/start` — Trigger Elasticsearch loading
- `POST /outbound/start` — Trigger outbound data export
- `DELETE /purge` — Purge Elasticsearch indexes by carrier SCAC

### 5.5 Service Layer

#### `ScheduleSearchService` — Core Search Orchestrator
```
Request → validate(UserSearchRequestValidator) → collect(InttraScheduleCollector) → enrich(EnrichmentService) → Response
```
- Validates all search parameters
- Delegates collection to `InttraScheduleCollector`
- Enriches raw schedules with geography, carrier names, cutoff dates, durations

#### `InttraScheduleCollector` — Data Source Router
- **Primary**: Queries Elasticsearch via `ElasticSearchClient.getSchedules()`
- **Secondary**: Calls external carrier APIs via `ExternalClientFactory.getExternalClient(scac)`
- Applies `directOnly` filter (removes schedules with transshipment legs)
- Deduplicates schedules from overlapping sources

#### `EnrichmentService` — Data Enrichment Pipeline
Enriches `InttraSchedule` with:
1. **Carrier name** — via `NetworkParticipantClient`
2. **Port geography** — city, country, subdivision via `GeographyClient`
3. **Cutoff date offsets** — via `CutoffOffsetService` (SCAC + location-based)
4. **Transit duration** — calculated as departure→arrival days
5. **Leg enrichment** — geography for each transshipment leg
6. **Vessel name defaulting** — "TO BE DECIDED" for blank vessel names
7. **Invalid schedule removal** — filters schedules > 90 days duration

#### `CarrierService` — Carrier & Port-Pair Management
- Fetches carrier data from `NetworkParticipantClient`
- Manages port-pair configurations in MySQL (CRUD via `PortPairDao`)
- Scans S3 for EDI data source carriers
- Purges Elasticsearch indexes by SCAC code
- Manages service enablements (rate limiting config)

#### `OSProcessService` — Pipeline Trigger
- Publishes SNS messages to trigger batch processing stages
- Validates SCAC codes against known carriers (S3 + API sources)
- Three trigger modes: staging, loader, outbound

#### `CutoffOffsetService` — Cutoff Date Lookup (Cached)
- Queries `ScheduleCutoffOffsetDao` for terminal cutoff offsets
- Uses `ServiceCache` (Guava) with 1440-minute TTL
- Keyed by SCAC + UNLOC combination

#### `RecentSearchService` — User Search History
- Persists recent searches as JSON in MySQL (max 12 entries)
- Enriches with geography data on retrieval
- `@Transactional` save operation

#### `UserPreferenceService` / `VesselDetailsService` — Simple CRUD
- Thin wrappers around DAO calls for user preferences and vessel detail lookups

### 5.6 Client Layer

#### External Carrier API Clients

**Architecture**:
```
ExternalClientInterface (interface)
    └── ExternalClient<T> (abstract, extends ExternalCommonClient)
            ├── MaerskExternalClient
            ├── CmaExternalClient
            ├── MscExternalClient
            ├── ZimExternalClient
            ├── ... (11 carrier-specific implementations)
            └── ElasticSearchClient (also implements ExternalClientInterface)
```

**`ExternalClient<T>`** — Abstract base for all carrier API clients:
- Builds requests from port-pair configurations via `PortPairRequestBuilder`
- Processes requests in **parallel streams** with MDC context propagation
- Implements **distributed caching** via `RealTimeCacheDao` (DynamoDB):
  - `acquireLock()` — Conditional DynamoDB write for cache key locking
  - `cacheInttraSchedules()` — Stores serialized schedules with TTL
- Falls back to Elasticsearch on API failure
- Each carrier provides its own `mapCarrierResponseToSchedules()` mapping

**Port-Pair Request Builders** (via `PortPairRequestBuilder` interface):

| Builder | Carrier(s) | SCAC Codes |
|---------|-----------|------------|
| `MaerskPortPairBuilder` | Maersk | MAEU, SEAU, SEJJ, MCPU |
| `CmaPortpairBuilder` | CMA CGM | CMDU, ANNU, CHNL, APLU |
| `MscPortpairBuilder` | MSC | MSCU |
| `ZimPortpairBuilder` | ZIM | ZIMU |
| `HapagLloydPortpairBuilder` | Hapag-Lloyd | HLCU |
| `EvergreenPortPairBuilder` | Evergreen | EGLV |
| `MarfretPortpairBuilder` | Marfret | MFRT |
| `SwirePortpairBuilder` | Swire | CHOL |
| `SeaLeadPortpairBuilder` | Sea Lead | SLXX |
| `NeptunePortpairBuilder` | Neptune | NEPT |
| `HmmPortpairBuilder` | HMM | HDMU |
| `WisetechPortpairBuilder` | Wisetech | Multiple |

**`ElasticSearchClient`** — Elasticsearch Query Client:
- Uses **Jest client** (`io.searchbox.*`) for Elasticsearch 6.x
- Builds queries with `BoolQueryBuilder` (terms, ranges, date filters)
- Handles carrier ID term creation, port filtering, date range calculation
- Supports fallback queries for external API failures

#### Network Services Clients

- `NetworkServiceClient` — Authenticated REST client with bearer token (via `AuthClient`)
- `NetworkParticipantClient` — Carrier data from Participant API; cached in `ConcurrentHashMap`
- `GeographyClient` — Port/location enrichment; Guava cached by UN/LOCODE
- `AuthClient` — OAuth2 client credentials flow for network services auth

#### Timezone Client

- `TimezoneServiceClient` — Port timezone lookup; cached by UN/LOCODE
- `TimezoneAuthClient` — OAuth2 token management for timezone API

### 5.7 Persistence Layer

| DAO | Mapper (MyBatis) | Database | Table |
|-----|-------------------|----------|-------|
| `PortPairDao` | `PortPairMapper` | MySQL | `CarrierPortPair` |
| `ScheduleCutoffOffsetDao` | `ScheduleCutoffOffsetMapper` | MySQL | `ScheduleCutoffOffset` |
| `UserDataDao` | `UserDataMapper` | MySQL | `ScheduleUserData` |
| `ScheduleVesselDetailsDao` | `ScheduleVesselDetailsMapper` | MySQL | `ScheduleVesselDetails` |
| `RealTimeCacheDao` | — (DynamoDB) | DynamoDB | `os_realtime_cache` |
| `SchedulesProStagingDao` | — (DynamoDB) | DynamoDB | `schedules_pro_staging` |

**MyBatis Mappers**: Use annotation-based SQL (`@Select`, `@Insert`, `@Update`, `@Delete`) with `@Results` mapping. `PortPairSQLBuilder` provides dynamic SQL for filtered queries.

**UserDataDao**: Stores user-specific data (recent searches, preferences) as serialized JSON in a single `ScheduleUserData` table using `UserDataType` enum discriminator. Uses `ON DUPLICATE KEY UPDATE` for upsert.

**DynamoDB DAOs**: Extend `DynamoDBCrudRepository` from commons. `RealTimeCacheDao` supports distributed locking via conditional writes on `LOCKED` attribute.

### 5.8 DynamoDB Models

#### `RealTimeCache`
- **Table**: `os_realtime_cache`
- **Hash Key**: `cacheKey` (String — typically `{scac}_{origin}_{destination}`)
- **Attributes**: `carrierConfigName`, `writeDateTime` (epoch), `expiresOn` (epoch/TTL), `inttraSchedules` (JSON), `locked` (lock flag)
- **Stream**: KEYS_ONLY
- **Purpose**: Distributed cache for real-time carrier API responses with TTL auto-cleanup

#### `SchedulesProStaging`
- **Table**: `schedules_pro_staging`
- **Hash Key**: `scac` (String)
- **Range Key**: `portPairIndicator` (String)
- **GSI**: `schedules_pro_source_index` on `scheduleSource`
- **Attributes**: `scheduleJson` (JSON), `lastUpdated` (epoch), `expiresOn` (epoch/TTL)
- **Stream**: KEYS_ONLY
- **Purpose**: Staging area for schedule data between pipeline stages

Both models implement `TimeToLive` for DynamoDB TTL auto-expiry and use `DateToEpochSecond` converter for date fields.

### 5.9 Domain Models

#### `InttraSchedule` — Canonical Schedule Model
The core data transfer object representing a single shipping schedule:

| Field Group | Fields |
|-------------|--------|
| Carrier | `scac`, `carrierName`, `serviceName` |
| Vessel | `vesselName`, `voyageNumber`, `imoNumber` |
| Origin | `originUnloc`, `originCountry`, `originCityName`, `originSubdivision`, `originTerminal` |
| Destination | `destinationUnloc`, `destinationCountry`, `destinationSubdivision`, `destinationCityName`, `destinationTerminal` |
| Dates | `originDepartureDate`, `destinationArrivalDate`, `estimatedTerminalCutoff`, `terminalCutoff`, `bkCutoff`, `siCutoff`, `hazBkCutoff`, `vgmCutoff`, `reeferCutoff` |
| Metadata | `totalDuration` (days), `scheduleType`, `scheduleSource`, `allowsRORO`, `allowsBreakbulk`, `createdDate` |
| Legs | `List<InttraLeg>` — transshipment legs with per-leg details |

#### `InttraLeg` — Schedule Leg Model
Each leg contains: `sequence`, `transportID` (IMO), `serviceName`, `transportType`, `transportName`, `conveyanceNumber`, departure/arrival UNLOC+city+country+terminal+date, `transshipmentIndicator`, `transitDuration`.

#### `VesselDetails` — Vessel Information
18 vessel attributes: name, IMO, owner, operator, flag, callSign, yearBuilt, TEU count, tonnage, dimensions, etc.

#### `CutoffOffset` — Terminal Cutoff Configuration
Per-carrier, per-port offset (in hours) for terminal cutoff date calculation.

### 5.10 Exception Handling

**Exception Hierarchy**:
```
RuntimeException
├── CommonClientException          # Generic API call failures
├── NetworkServiceException        # Network service API failures
└── MercuryUuidException (commons)
    ├── MercuryOSRequestException  # HTTP 400 — Bad Request
    └── MercuryOSServiceException  # HTTP 500 — Internal Server Error
```

**Request Errors** (`MercuryOSRequestException.MER_OSREQ_EX`):

| Code | Name |
|------|------|
| 4000 | GENERIC_BAD_REQUEST |
| 4100 | INVALID_REQUEST_PAYLOAD |
| 4400 | MISSING_REQUIRED_QUERY_PARAM |
| 4410 | INVALID_SEARCH_DATE_FORMAT |
| 4411 | INVALID_SEARCH_DATE_TYPE |
| 4412–4413 | INVALID_NEARBY_PORTS_PARAM_FORMAT |
| 4415 | INVALID_ORIGIN |
| 4420 | INVALID_DESTINATION |
| 4425 | INVALID_WEEKS_OUT |
| 4430 | INVALID_DIRECT_ONLY_FORMAT |

**Service Errors** (`MercuryOSServiceException.MER_OSSVC_EX`):

| Code | Name |
|------|------|
| 3100 | GENERIC_SERVICE_EXCEPTION |
| 3101 | RESOURCE_FETCH_EXCEPTION |
| 3300s | REST_CLIENT_* exceptions |
| 3651 | TERMINAL_CUT_OFF_RETRIEVAL_FAILURE |
| 3701 | NO_CARRIER_DATA_FOUND |
| 3751 | API_REQUEST_CONFIGURATOR_NOT_AVAILABLE |
| 3801 | SCHEDULE_TRANSLATOR_NOT_AVAILABLE |

**Exception Mappers** (JAX-RS `@Provider`):

| Mapper | Exception | HTTP Status |
|--------|-----------|-------------|
| `RequestExceptionMapper` | `MercuryOSRequestException` | 400 |
| `ServiceExceptionMapper` | `MercuryOSServiceException` | 500 |
| `SecurityExceptionMapper` | `MercurySecurityException` | 401 or 403 |
| `UnrecognizedPropertyExceptionMapper` | `UnrecognizedPropertyException` | 400 |

### 5.11 Utility Classes

| Class | Purpose |
|-------|---------|
| `AWSUtil` | Retryable error detection for AWS SDK v1 exceptions |
| `SharedUtil` | JSON serialization, date parsing, duration calculation |
| `SharedConstants` | Parameter names, schedule types, date formatters, carrier keys |
| `UserSearchRequestValidator` | Comprehensive search parameter validation pipeline |
| `S3Service` | S3 folder listing (common prefixes) and batch deletion with retry |
| `SNSClient` | SNS message publishing with retry (implements `MessageSender`) |
| `MessageSender` | Functional interface for message sending abstraction |
| `MetaData` | SNS/SQS message envelope model (workflowId, bucket, fileName, projections) |
| `Status` | Enum: Active, Inactive |
| `UserDataType` | Enum: RECENT_SEARCH, PREFERENCE |
| `SearchDateType` | Enum: ByDepartureDate, ByArrivalDate, ByCutOffDate |

---

## 6. Component Deep Dive — oceanschedules-process (Batch Pipeline)

### 6.1 Common (Shared Library)

**~204 Java files** providing cross-cutting services to all pipeline modules:

| Category | Key Classes |
|----------|-------------|
| **Messaging** | `SqsThreadPoolListener`, `SQSListener`, `SNSClient`, `MessageSender`, `Listener` |
| **Data Models** | `PortPairSchedule`, `InttraSchedule`, `InttraLeg`, `ExternalAPIResponse`, `MetaData`, `SNSNotification` |
| **S3 Services** | `S3WorkspaceService`, `MultiPartUploader` |
| **Network Services** | `SubscriptionServiceImpl`, `NetworkParticipantServiceImpl`, `AliasServiceImpl` |
| **Format Services** | `FormatServiceImpl` (EDIFACT, ANSI, CSV converters) |
| **Event/Audit** | `EventLogger`, `EventPublisher` |
| **Threading** | `ThreadPoolConfig`, `BoundedBlockingThreadPool` |
| **Utilities** | `ObjectMapperUtil`, `SharedUtil` |

### 6.2 Collector

**ArtifactId**: `oceanschedules-collector`  
**Runtime**: Dropwizard HTTP server  
**Purpose**: Scheduled polling of external carrier APIs (ZIM, MSC, etc.)

**Key Classes**:
- `OceanSchedulesCollectorApplication` — Dropwizard entry point
- `ScheduleCollectorJob` — Fixed-interval scheduled executor
- `ScheduleCollectorProcessor` — HTTP calls to external carrier APIs
- `PortPairMapper` / `PortPairDao` — MyBatis persistence for port-pair routes

**Data Flow**: Timer tick → Fetch from carrier APIs → Store port-pairs in MySQL → Publish to S3 for inbound processing

**Dependencies**: Dropwizard 4.0.x, MyBatis, AWS RDS MySQL JDBC, JWT 0.11.2

### 6.3 Inbound

**ArtifactId**: `os-inbound-processor`  
**Runtime**: Spark batch job (SQS-triggered)  
**Purpose**: Parse EDIFACT/ANSI X.12 schedule files into canonical format

**Key Classes**:
- `ScheduleProcessorTask` — SQS message processor
- `InboundScheduleGenerator` — File parser and schedule generator
- `PortPairGenerator` — Extracts origin-destination port combinations
- EDIFACT utilities: `EdifactQualifier`, `EdifactVoyageType`, `EdifactPortType`, `EdifactDateType`, `EdifactDateFormat`, `EdifactActionType`
- ANSI utilities: `AnsiPortTypeId`, `AnsiDateTypeId`, `AnsiActionType`
- Canonical converters: `CanonicalPortType`, `CanonicalDateType`, `CanonicalActionType`, `DateResolver`

**Data Flow**: SQS message → Download EDIFACT/ANSI from S3 → Parse to canonical `CanonicalSchedule` → Extract port-pairs → Enrich metadata → Publish to SNS → Triggers staging

**Mapping Files**: `maps/inbound/` — XML-based schemas (`.xbm`):
- `IFTSAI_D99B_IN_V1.xbm` — UN/EDIFACT D99B interchange
- `T323_4010_IN_V1.xbm` — ANSI X.12 323 format

### 6.4 Staging

**ArtifactId**: `os-staging`  
**Runtime**: Spark batch job (SQS-triggered)  
**Purpose**: Transform raw schedules into staged format; orchestrate downstream processing

**Key Classes**:
- `OceanSchedulesStagingProcessor` — Entry point, config loader
- `OceanScheduleStagingProcessorTask` — SQS orchestrator, extracts SCAC from metadata
- `StagedPortPairProcessor` — Spark job for port-pair staging
- `OSMaintenanceService` — Routes messages to loader/outbound/aggregator
- `MessageRegisterService` — Concurrency control (blocks duplicate SCAC processing)

**Data Flow**: SNS→SQS message (from inbound) → Extract SCAC → Spark transform/dedup → Save to S3 → Publish events to SNS → Route to Loader + Aggregator + Outbound via SQS

### 6.5 Aggregator

**ArtifactId**: `os-aggregator`  
**Runtime**: Spark batch job (SQS-triggered)  
**Purpose**: Merge schedule data from multiple sources into a unified view

**Key Classes**:
- `OSAggregatorApplication` — Entry point, Guice injection
- `SchedulesAggregatorTask` — SQS message processor
- `ScheduleAggregatorService` — Core aggregation logic
- `DynamoSparkService` — DynamoDB read/write via Spark
- `s3Utils`, `SparkUtils`, `SparkMappingUtils` — Data transformation utilities

**Data Flow**: SQS message (carrier SCACs) → Read staged schedules from S3 → Merge with existing DynamoDB schedules → Write results → Publish SNS events

**Dependencies**: Spark 3.5.3, Hadoop 3.3.4, AWS SDK v1.12.558, Jest 6.3.1, EMR DynamoDB Hadoop connector

### 6.6 Loader

**ArtifactId**: `os-loader`  
**Runtime**: Spark batch job (SQS-triggered)  
**Purpose**: Generate transshipment routes and index schedules into Elasticsearch

**Key Classes**:
- `OceanSchedulesLoader` — Entry point
- `OceanScheduleLoaderTask` — SQS message processor
- `TransshipmentAndUploadTask` — Spark job for transshipment generation + ES bulk upload
- `ElasticSearchUtil` — ES index/alias management, bulk upload operations
- `OceanSchedulesLoaderSql` — SQL queries for schedule processing
- `JestModule`, `JestClientRetryHandler` — Jest client DI and retry

**Data Flow**: SQS message (from staging) → Process port-pairs from S3 → Generate transshipments (Spark SQL) → Bulk upload to Elasticsearch → Manage ES indices/aliases → Publish SNS events

**Dependencies**: Spark 3.5.3, Elasticsearch 8.6.2, Jest 6.3.1, AWS SDK v1

### 6.7 Outbound

**ArtifactId**: `os-outbound-processor`  
**Runtime**: Spark batch job (SQS-triggered)  
**Purpose**: Export schedules in multiple formats (EDIFACT, ANSI, CSV, XML) for downstream subscribers

**Key Classes**:
- `ExportService` — Spark-based export orchestrator
- `OutboundProcessorTask` — SQS message handler
- Export adapters (Factory pattern):
  - `ExportAdapterFactory`, `ExportAdapter` (interface)
  - `DefaultExportAdapter`, `ExportAdapterForGLV`, `ExportAdapterForAgility`, `ExportAdapterForCng`
- `OceanSchedulesOutboundPreference` — Subscriber export preferences
- `PortCombinationFilterPreference`, `PortTypePreference`, `SingleVoyageNumberOnlyPreference`
- `PreferenceResolver` — Resolves subscriber preferences from network services
- `EdifactControlNumGenerator` — EDIFACT control number generation
- `QualifierMap`, `TokenResolver` — Format qualifiers and token substitution

**Data Flow**: SQS message → Query subscriber preferences → Filter/transform schedules per preference → Serialize to target format → Upload to S3 → Publish SNS event

**Mapping Files**: `maps/outbound/` — Export format templates:
- `IFTSAI_CSV_OUT_OCS_V1.xbm`, `IFTSAI_CSV_OUT_V1.xbm` — CSV
- `IFTSAI_D99B_OUT_V1.xbm`, `IFTSAI_D99B_OUT_AGILITY_V1.xbm` — EDIFACT
- `IFTSAI_XML_OUT_V1.xbm` — XML

**Dependencies**: AWS SDK v1.12.773, Spark 3.5.3, Jackson CSV/XML

### 6.8 Port-Pair-Generator

**ArtifactId**: `os-port-pair-generator`  
**Runtime**: Dropwizard HTTP server (SQS-triggered)  
**Purpose**: Discover port-pair route combinations from carrier API responses and persist to DynamoDB

**Key Classes**:
- `OceanSchedulesPortPairGeneratorApplication` — Dropwizard entry point
- `ScheduleGeneratorProcessor` — SQS message processor
- `DynamoService` — DynamoDB persistence with retry (3 attempts, 400KB item limit, TTL)
- `InttraSchedulesMapper` — Maps external API responses to `InttraSchedule`
- `NetworkParticipantClient`, `NetworkServiceClient` — Carrier/participant data lookup
- `S3MergeService`, `PrefetchElasticService` — Schedule merging and pre-fetching

**Data Flow**: SQS message (external API response) → Lookup port-pair info → Map to InttraSchedule → Validate/dedup → Store in DynamoDB with TTL → Log metrics to CloudWatch

**Dependencies**: AWS SDK v1.12.558, Dropwizard 4.0.x, Guava retrying 2.0.0

### 6.9 Maps

XML-based data mapping schemas (`.xbm` files) for EDIFACT/ANSI/CSV/XML format conversions:

```
maps/
├── inbound/
│   ├── IFTSAI_D99B_IN_V1.xbm          # UN/EDIFACT D99B input
│   ├── IFTSAI_D99B_IN_V1_STRUCT.xbm   # Structure definition
│   ├── T323_4010_IN_V1.xbm            # ANSI X.12 323 input
│   ├── T323_4010_IN_V1_STRUCT.xbm     # Structure definition
│   └── T323_4010_IN_ONEY_V1.xbm       # ONE carrier-specific
└── outbound/
    ├── IFTSAI_CSV_OUT_OCS_V1.xbm       # CSV output (OCS format)
    ├── IFTSAI_CSV_OUT_V1.xbm           # CSV output (standard)
    ├── IFTSAI_D99B_OUT_V1.xbm          # EDIFACT output (standard)
    ├── IFTSAI_D99B_OUT_AGILITY_V1.xbm  # EDIFACT output (Agility)
    └── IFTSAI_XML_OUT_V1.xbm           # XML output
```

---

## 7. Data Flow Architecture

### End-to-End Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL DATA SOURCES                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ Carrier EDI  │  │ Carrier APIs │  │  Direct API  │                  │
│  │ (EDIFACT /   │  │ (ZIM, MSC,   │  │ (Maersk, CMA │                  │
│  │  ANSI X.12)  │  │  Hapag, etc) │  │  ONE, etc.)  │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                 │                  │                          │
└─────────┼─────────────────┼──────────────────┼──────────────────────────┘
          │                 │                  │
          │  S3 Upload      │  Collector       │ Real-time
          ▼                 ▼                  ▼
┌────────────────┐  ┌───────────────┐  ┌─────────────────┐
│   INBOUND      │  │  COLLECTOR    │  │  oceanschedules  │
│   Parse EDI/   │  │  Poll APIs    │  │  API (Direct)    │
│   ANSI files   │  │  Save to S3   │  │  ExternalClient  │
└───────┬────────┘  └───────┬───────┘  │  → DynamoDB Cache│
        │ SNS               │ S3       └────────┬────────┘
        ▼                   ▼                   │
┌────────────────┐                              │
│   STAGING      │                              │
│   Dedup/       │                              │
│   Transform    │                              │
└──┬──────┬──────┘                              │
   │      │                                     │
   │ SQS  │ SQS                                 │
   ▼      ▼                                     │
┌──────┐ ┌────────────┐                         │
│LOADER│ │ AGGREGATOR │                         │
│Upload│ │ Merge multi│                         │
│to ES │ │ sources    │                         │
└──┬───┘ └──────┬─────┘                         │
   │            │                               │
   │   ES Index │  DynamoDB                     │
   ▼            ▼                               │
┌────────────────────────────────────────────────┤
│          ELASTICSEARCH INDEX                   │ ← Search queries
│          (edi_schedule_data)                   │
└────────────────────────────────────────────────┘
                                                │
┌────────────────┐                              │
│   OUTBOUND     │                              │
│   Export to    │ ← SQS from staging           │
│   subscribers  │                              │
│   (EDI/CSV/XML)│                              │
└───────┬────────┘                              │
        │ S3                                    │
        ▼                                       │
  Subscriber feeds                              │
                                                │
┌───────────────────────────────────────────────┤
│   PORT-PAIR-GENERATOR                         │
│   Discover routes from API responses          │ ← SQS
│   → DynamoDB storage                          │
└───────────────────────────────────────────────┘
```

### API Schedule Search Flow (Runtime)

```
Client Request (GET /schedule)
    │
    ▼
UserSearchRequestValidator
    │ Validates: origin, destination, dates, carriers, booleans
    ▼
InttraScheduleCollector
    ├── ElasticSearchClient (Primary)
    │       └── Jest → Elasticsearch 6.x
    │           └── BoolQuery: carrier terms + port filter + date range
    │
    └── ExternalClientFactory (Secondary — carrier-specific APIs)
            ├── MaerskExternalClient
            ├── CmaExternalClient
            ├── ZimExternalClient
            │   └── Parallel streams (MDC propagation)
            │       └── DynamoDB RealTimeCache (lock + cache)
            └── ...
    │
    ▼
EnrichmentService
    ├── CarrierName    ← NetworkParticipantClient
    ├── PortGeography  ← GeographyClient (cached)
    ├── CutoffDates    ← CutoffOffsetService (cached)
    ├── Duration       ← Calculated
    ├── LegEnrichment  ← GeographyClient per leg
    └── Filtering      ← Remove > 90-day schedules
    │
    ▼
List<InttraSchedule> Response
```

---

## 8. AWS Services Usage

| AWS Service | Module | Usage | SDK Version |
|-------------|--------|-------|-------------|
| **S3** | API + all process modules | Schedule files, exports, EDI data, intermediate staging | v1 |
| **DynamoDB** | API, Aggregator, Port-Pair-Gen | `os_realtime_cache` (API caching), `schedules_pro_staging` (pipeline) | v1 |
| **SNS** | API, Staging, all process modules | Inter-module event publishing (4 topics: loader, outbound, staging, aggregator) | v1 |
| **SQS** | All process modules | Input queues for each pipeline stage | v1 |
| **Elasticsearch** | API, Loader | Schedule search index (`edi_schedule_data`), carrier schedule indices | Via Jest (v1 signing) |
| **RDS (MySQL)** | API, Collector | Port-pairs, cutoff offsets, vessel details, user data, subscriptions | JDBC (aws-mysql-jdbc) |
| **SSM Parameter Store** | API (AuthUtil), Outbound | Carrier API credentials, configuration parameters | v1 |
| **CloudWatch** | Port-Pair-Gen | Metrics and logging | v1 |

### DynamoDB Table Schemas

**`os_realtime_cache`**:
| Attribute | Type | Key | Notes |
|-----------|------|-----|-------|
| `cacheKey` | String | Hash Key | Format: `{scac}_{origin}_{destination}` |
| `carrierConfigName` | String | — | |
| `writeDateTime` | Number (epoch) | — | |
| `expiresOn` | Number (epoch) | — | TTL attribute |
| `inttraSchedules` | String | — | Serialized JSON |
| `locked` | String | — | Distributed lock flag |

**`schedules_pro_staging`**:
| Attribute | Type | Key | Notes |
|-----------|------|-----|-------|
| `scac` | String | Hash Key | Carrier SCAC code |
| `portPairIndicator` | String | Range Key | |
| `scheduleSource` | String | GSI Hash Key | Index: `schedules_pro_source_index` |
| `scheduleJson` | String | — | Serialized JSON |
| `lastUpdated` | Number (epoch) | — | |
| `expiresOn` | Number (epoch) | — | TTL attribute |

---

## 9. External Carrier Integrations

| Carrier | SCAC | Auth Method | Port-Pair Builder | Notes |
|---------|------|-------------|-------------------|-------|
| Maersk | MAEU, SEAU, SEJJ, MCPU | Consumer key | `MaerskPortPairBuilder` | Location resolution via `MaerskLocationClient` (cached 10K entries, 600 min TTL) |
| CMA CGM | CMDU, ANNU, CHNL, APLU | API key | `CmaPortpairBuilder` | Alliance: ONE group |
| MSC | MSCU | Client assertion (X.509) | `MscPortpairBuilder` | Certificate-based OAuth2 |
| ZIM | ZIMU | OAuth2 + subscription key | `ZimPortpairBuilder` | Azure APIM gateway |
| Hapag-Lloyd | HLCU | IBM API gateway | `HapagLloydPortpairBuilder` | Multi-field auth (client + user + org) |
| Evergreen | EGLV | Static bearer token | `EvergreenPortPairBuilder` | |
| HMM | HDMU | — | `HmmPortpairBuilder` | |
| Marfret | MFRT | — | `MarfretPortpairBuilder` | |
| Swire (OOCL) | CHOL | — | `SwirePortpairBuilder` | Custom request model |
| Sea Lead | SLXX | — | `SeaLeadPortpairBuilder` | |
| Neptune | NEPT | — | `NeptunePortpairBuilder` | Custom request model |
| Wisetech | Multiple | — | `WisetechPortpairBuilder` | Multi-carrier aggregator |

Each carrier integration follows the pattern:
1. `PortPairRequestBuilder` maps `PortPair` → carrier-specific request parameters
2. `ExternalClient<T>` calls carrier API, maps response → `List<InttraSchedule>`
3. Results cached in DynamoDB `RealTimeCache` with TTL
4. Falls back to Elasticsearch on failure

---

## 10. Security & Access Control

### OAuth2 Authentication
- Token validation via configured auth URIs
- JWT (`jjwt` 0.11.2) for token parsing and validation

### Role-Based Access Control (RBAC)
Enforced via JAX-RS `@RolesAllowed` annotations:

| Role | Access |
|------|--------|
| `OCEANSCHEDULE_USER` | Schedule search, recent searches, preferences, vessel details, carriers |
| `OCEANSCHEDULE_API_USER` | Schedule search, carriers (API consumers) |
| `OCEANSCHEDULE_ADMIN_USER` | Process maintenance (staging/loader/outbound triggers, purge) |
| `NETWORK_ADMIN` | Full access to all endpoints |

### Carrier API Credential Management
- Credentials stored in YAML configs per environment (int/qa/cvt/prod)
- Some credentials resolved from AWS SSM Parameter Store at runtime (`AuthUtil.setClientIdAndClientSecret()`)
- Each carrier has a distinct auth model (OAuth2, API keys, certificates, basic auth)

---

## 11. Maven Dependencies

### oceanschedules (API Module)

**Compile Dependencies**:
| GroupId | ArtifactId | Version | Purpose |
|---------|-----------|---------|---------|
| `com.inttra.mercury` | `commons` | 1.R.01.021 | Shared library (Dropwizard, auth, DynamoDB base) |
| `com.inttra.mercury` | `dynamo-client` | 1.R.01.021 | DynamoDB client wrapper |
| `org.elasticsearch` | `elasticsearch` | 6.8.13 | ES query builders |
| `org.yaml` | `snakeyaml` | 2.2 | YAML parsing |
| `org.apache.logging.log4j` | `log4j-to-slf4j` | 2.16.0 | Log4j→SLF4J bridge |
| `org.projectlombok` | `lombok` | (parent) | Code generation |
| `io.swagger` | `swagger-core` / `swagger-annotations` | 1.5.22 | API documentation |
| `io.jsonwebtoken` | `jjwt-api` / `jjwt-impl` / `jjwt-jackson` | 0.11.2 | JWT processing |
| `software.aws.rds` | `aws-mysql-jdbc` | 1.1.0 | AWS RDS MySQL driver |

**Test Dependencies**:
| GroupId | ArtifactId | Version | Purpose |
|---------|-----------|---------|---------|
| `io.dropwizard` | `dropwizard-testing` | 4.0.16 | Dropwizard test support |
| `org.junit.jupiter` | `junit-jupiter` | 5.10.1 | JUnit 5 |
| `org.mockito` | `mockito-core` / `mockito-junit-jupiter` | 5.8.0 | Mocking |
| `com.inttra.mercury` | `integration-test-commons` | 1.0 | Integration test utilities |

### oceanschedules-process Sub-Module Dependencies

| Sub-Module | AWS SDK | Spark | Elasticsearch | Other Notable |
|------------|---------|-------|---------------|---------------|
| Common | 1.12.558 (SQS) | — | — | Guava 33.3.0 |
| Aggregator | 1.12.558 (DynamoDB, SSM, S3) | 3.5.3 | Jest 6.3.1 | EMR DynamoDB connector |
| Collector | — | — | — | Dropwizard, MyBatis, aws-mysql-jdbc |
| Inbound | — | — | — | Jackson CSV, Commons BeanUtils |
| Staging | 1.12.x (SQS, S3, SNS) | 3.5.3 | — | SLF4J 2.0.6 |
| Loader | 1.12.x (SQS, S3, SNS) | 3.5.3 | 8.6.2, Jest 6.3.1 | |
| Outbound | 1.12.773 (SQS, SNS, S3, SSM) | 3.5.3 | — | Jackson CSV/XML |
| Port-Pair-Gen | 1.12.558 (DynamoDB) | — | — | Dropwizard, Guava retrying 2.0.0 |

---

## 12. Test Strategy

### Framework & Tooling
- **Unit Testing**: JUnit 5 (Jupiter) 5.10.1 — exclusively, no JUnit 4
- **Mocking**: Mockito 5.8.0 with `@ExtendWith(MockitoExtension.class)`
- **Integration Testing**: `maven-failsafe-plugin` 3.2.5, excluded groups `com.inttra.mercury.base.IntegrationTest`
- **Test Resources**: JSON fixtures for Elasticsearch payloads, environment-specific test configs

### Test Coverage

**59 test classes** across all layers:

| Layer | Test Classes | Coverage Focus |
|-------|-------------|----------------|
| Resources | 7 (`ScheduleResourceTest`, `CarrierResourceTest`, `RecentSearchResourceTest`, `VesselDetailsResourceTest`, `UserPreferenceResourceTest`, `SubscribedCarrierResourceTest`, `OSProcessResourceTest`) | Request/response mapping, role validation, exception propagation |
| Services | 7 (`InttraScheduleCollectorTest`, `EnrichmentServiceTest`, `CarrierServiceTest`, `CutoffOffsetServiceTest`, `RecentSearchServiceTest`, `OSProcessServiceTest`, `VesselDetailsServiceTest`) | Business logic, filtering, enrichment pipelines |
| Clients | 16 (per-carrier builder tests + `ElasticSearchClientTest`, `ExternalClientTest`, `ExternalClientFactoryTest`, `AuthClientTest`, `GeographyClientTest`, `NetworkParticipantClientTest`, `NetworkServiceClientTest`, `TimezoneServiceClientTest`, `TimezoneAuthClientTest`, `MaerskLocationClientTest`, `CommonClientTest`) | API integration, request building, response mapping, retry logic |
| Persistence | 5 (`PortPairDaoTest`, `PortPairSQLBuilderTest`, `SchedulesProStagingDaoTest`, `ScheduleCutoffOffsetDaoTest`, `UserDataDaoTest`, `RealTimeCacheDaoTest`) | DAO operations, null safety, MyBatis query verification |
| Exceptions | 2 (`MercuryOSServiceExceptionTest`, `MercuryOSRequestExceptionTest`) | Exception code mapping |
| Controllers | 4 (all exception mapper tests) | HTTP status code mapping |
| Config | 3 (`SNSConfigTest`, `S3ConfigTest`, `ElasticSearchConfigTest`) | Config deserialization |
| Utilities | 3 (`UserSearchRequestValidatorTest`, `SNSClientTest`, `S3ServiceTest`, `AWSUtilTest`) | Validation logic, AWS utility functions |

### Test Patterns

1. **Resource Tests**: Mock service layer, verify HTTP status codes and response entities, test `@RolesAllowed` enforcement
2. **Service Tests**: Mock DAOs and clients, verify business logic (filtering, enrichment, dedup)
3. **Client Tests**: Mock HTTP clients and Jest, verify request construction and response parsing
4. **DAO Tests**: Mock MyBatis mappers, verify SQL invocation and null safety
5. **Builder Tests**: Verify carrier-specific request parameter mapping
6. **Test Data Factory**: `TestHelper.java` provides centralized test data builders:
   - `createConfig()` — Full `OceanSchedulesConfig` with all sub-configs
   - `createCarrierDataList()` — Pre-built carrier data
   - `buildValidatedRequest()` — Search query parameter maps
   - Pre-defined carrier SCACs and port codes as constants

### Assertion Style
- Primary: JUnit 5 static assertions (`assertEquals`, `assertThrows`, `assertTrue`, `assertNotNull`)
- Verification: Mockito `verify()` for method invocation checks
- Setup: `@BeforeEach` with `lenient()` mocking for shared setup
- **Note**: Does not use AssertJ (recommended by project conventions)

### SonarQube Coverage Exclusions
```xml
**/model/**,**/exception/**,**/config/**,**/module/**
```

---

## 13. Configuration & Environments

### Environment Matrix

| Environment | Config Path | Purpose |
|-------------|-------------|---------|
| `int` | `conf/int/config.yaml` | Integration testing |
| `qa` | `conf/qa/config.yaml` | QA validation |
| `cvt` | `conf/cvt/config.yaml` | CVT (pre-production) |
| `prod` | `conf/prod/config.yaml` | Production |

### Key Configuration Sections

```yaml
server:
  applicationConnectors:
    - type: http
      port: 8080
  applicationContextPath: /inttra/mercury/api/oceanschedules

database:
  driverClass: software.aws.rds.jdbc.mysql.Driver  # AWS RDS JDBC
  url: jdbc:mysql:aws://...?useSSL=true&...
  minSize: 5
  maxSize: 5

dynamoDbConfig:
  environment: inttra_int   # Table prefix
  sseEnabled: false
  awsRegion: us-east-1

elasticSearchConfig:
  endpointUrl: https://...es.amazonaws.com
  region: us-east-1
  oceanschedulesIndex: edi_schedule_data
  maxRetries: 3
  connTimeoutMillis: 3000
  readTimeoutMillis: 3000

s3Config:
  oceanSchedulesBucket: inttra-oceanschedules-...
  oceanSchedulesPurgePath: current/
  oceanSchedulesPurgeSourcePath: [current/, delta/]
  oceanSchedulesPaths: [staging/, current/, delta/, outbound/]

snsConfig:
  oceanSchedulesLoaderArn: arn:aws:sns:...
  oceanSchedulesOutboundArn: arn:aws:sns:...
  oceanSchedulesStagingArn: arn:aws:sns:...
  oceanSchedulesAggregatorArn: arn:aws:sns:...

jerseyClient:
  minThreads: 32
  maxThreads: 128
  timeout: 15s
  gzipEnabled: true

mercuryServiceDefinitions:
  - name: auth / geography / participant / ...
    uri: https://...
    method: GET
externalServiceDefinitions:
  - name: cma-api / maersk-location / ...
    uri: https://...
    scacs: [CMDU, ANNU, ...]
    retry: 2
    cacheExpiryMinutes: 30
```

### SQL DDL Scripts (MySQL)
Located in `src/main/resources/com/inttra/mercury/db/scripts/`:
- `CreateRecentScheduleSearchTable.sql` — User search history
- `CreateScheduleCutoffOffset.sql` — Carrier cutoff offset configuration
- `CreateScheduleVesselDetailsTable.sql` — Vessel reference data
- `DataLoadForScheduleVesselDetailsTableInQA.sql` — QA data seed

---

## 14. Build & Deployment

### Build Process

**Standard Build** (`build.sh`):
```bash
mvn clean package -DskipTests=false \
    -Dsonar.projectKey=... \
    -P sonar-services-commons
# Copies environment configs → Docker image creation
```

**PR Build** (`build_pr.sh`):
```bash
mvn verify  # Runs all tests including integration
# SonarQube analysis with quality gate wait
```

### Maven Build Plugins

| Plugin | Version | Purpose |
|--------|---------|---------|
| `maven-compiler-plugin` | 3.12.1 | Java 17 compilation |
| `maven-surefire-plugin` | 3.2.5 | Unit tests (excludes `IntegrationTest` groups) |
| `maven-failsafe-plugin` | 3.2.5 | Integration tests |
| `maven-shade-plugin` | 3.5.3 | Fat JAR packaging |
| `swagger-maven-plugin` | 3.1.7 | OpenAPI spec generation from JAX-RS annotations |

### Shade Plugin Configuration
- **Main Class**: `com.inttra.mercury.oceanschedules.OceanSchedulesApplication`
- **Transformers**: `ServicesResourceTransformer`, `ManifestResourceTransformer`
- **Filters**: Excludes `META-INF/*.SF`, `*.DSA`, `*.RSA` (signature files)

### Runtime Execution
```bash
# run.sh (Docker entrypoint)
java -Xms${JVM_HEAP:-1024m} -Xmx${JVM_HEAP:-1024m} \
     -jar ocean-schedules-1.0.jar server config.yaml
```

### OWASP Dependency Check
Suppressions in `suppressions.xml` for known CVEs:
- `CVE-2025-11226` — logback-core
- `CVE-2026-*` — handlebars JavaScript library

---

## 15. Critical Review

### What Is Good

1. **Clean Layered Architecture**: Strict Resource → Service → Client → DAO separation with clear responsibilities. Each layer is independently testable.

2. **Carrier Pluggability**: The `PortPairRequestBuilder` interface + Guice multibinding pattern makes adding new carriers straightforward — just implement the interface and register it. 12 carriers currently supported.

3. **Comprehensive Enrichment Pipeline**: `EnrichmentService` systematically enriches raw schedule data with geography, carrier names, cutoff dates, and duration calculations. This keeps the data rich and useful.

4. **Caching Strategy**: Multi-level caching (Guava in-memory + DynamoDB distributed cache) reduces external API calls and improves response times. Cache keys, TTL, and distributed locking are well thought out.

5. **Good Test Coverage Structure**: 59 test classes covering all layers. Test helper (`TestHelper.java`) provides centralized data builders. Each carrier builder has its own test.

6. **Event-Driven Pipeline**: The SNS/SQS-based batch processing pipeline provides loose coupling between stages (inbound → staging → loader/aggregator/outbound). Each stage can scale independently.

7. **Multiple Export Formats**: The outbound module's factory pattern for export adapters (`ExportAdapterFactory`) cleanly supports EDIFACT, ANSI, CSV, and XML without format-specific coupling.

8. **Comprehensive Exception Model**: Domain-specific error codes with HTTP status mapping (4xxx for client errors, 3xxx for server errors) provide clear error diagnostics.

9. **Configuration-Driven**: All carrier endpoints, auth parameters, caching durations, retry policies, and thread pool sizes are externalized in YAML. No hard-coded infrastructure.

10. **Modern Java**: JUnit 5, Lombok, Java 17 compilation target, `Optional<T>` return types in DAOs.

### What Is Bad

1. **AWS SDK v1 Throughout**: The entire module uses AWS SDK v1 (`com.amazonaws.*`), which is in maintenance mode. This is the primary technical debt. The `DynamoSupport`, `AWSClientConfiguration`, `S3Service`, `SNSClient`, `RealTimeCacheDao`, and all DynamoDB models need migration to v2.

2. **No cloud-sdk Abstraction Layer**: Unlike upgraded modules (auth, network, booking-bridge), this module directly instantiates AWS SDK v1 clients in the Guice module and utility classes. There's no abstraction layer to facilitate the SDK upgrade.

3. **Elasticsearch via Jest Client (Deprecated)**: Jest 6.3.1 is an unofficial, unmaintained Elasticsearch client. The Elasticsearch 6.8.13 dependency is also EOL. This needs migration to OpenSearch SDK or the official Elasticsearch Java client.

4. **Mixed Elasticsearch Versions**: The API module uses ES 6.8.13, while the Loader uses ES 8.6.2. This version inconsistency across modules is a maintenance risk.

5. **Dual JSON Annotation on ES Models**: `ElasticSearchSchedule` and `ElasticSearchLeg` use both Jackson (`@JsonProperty`) and Gson (`@SerializedName`) annotations — a sign of legacy compatibility issues that adds confusion.

6. **`CustomRetryCondition` Always Returns True**: In `AWSClientConfiguration`, the retry condition unconditionally returns `true`, meaning every error triggers retry regardless of type. This can cause unnecessary retries on non-transient errors (e.g., 403 Forbidden).

7. **Static ObjectMapper in `SharedUtil`**: A static `ObjectMapper` creates a singleton that can't be configured per-context and is harder to test. ObjectMapper should be injected via Guice.

8. **JSON Serialization for User Data Storage**: `UserDataDao` serializes complex objects (`UserPreference`, `List<LocationSearch>`) to JSON strings and stores them in a single MySQL column. This prevents querying on individual fields and is a code smell.

9. **Overly Large `CarrierService`**: This class has too many responsibilities — carrier data lookup, port-pair CRUD, Elasticsearch purge, S3 scanning, service enablement management. It should be split into focused services.

10. **No AssertJ in Tests**: Despite project conventions recommending AssertJ, all tests use JUnit 5 static assertions. This makes complex assertions more verbose and less readable.

11. **Swagger 1.5 (Legacy)**: Using Swagger 1.5.22 instead of OpenAPI 3.0. The Swagger Maven plugin 3.1.7 is also outdated.

12. **Inconsistent commons Version**: Using `mercury.commons.version=1.R.01.021` which is a release version, while the latest commons is `1.0.22-SNAPSHOT`. This may miss recent fixes and cloud-sdk additions.

13. **No DynamoDB Integration Tests**: Unlike upgraded modules (auth, registration, booking-bridge, webbl), there are no DynamoDB integration tests using the `dynamo-integration-test` dependency from mercury-services-commons.

14. **Thread Safety Concerns**: `NetworkParticipantClient` uses `ConcurrentHashMap` for carrier data caching, but the cache refresh logic (loading from API → populating maps) may have race conditions during concurrent access.

### What Can Be Improved

1. **AWS SDK v2 Migration (Priority 1)**: Migrate all AWS service interactions to cloud-sdk-api / cloud-sdk-aws from mercury-services-commons. Follow the pattern established in completed modules (auth, network, booking-bridge, etc.):
   - Replace `AmazonDynamoDB` → cloud-sdk DynamoDB repository pattern
   - Replace `AmazonS3` → cloud-sdk S3 client
   - Replace `AmazonSNS` → cloud-sdk SNS publisher
   - Remove `DynamoSupport`, `AWSClientConfiguration` in favor of cloud-sdk configuration

2. **Elasticsearch/OpenSearch Migration**: Replace Jest client with OpenSearch SDK or official ES Java client. Standardize on a single ES version across API and Loader modules.

3. **Add DynamoDB Integration Tests**: Use `dynamo-integration-test` from mercury-services-commons to add integration tests for `RealTimeCacheDao` and `SchedulesProStagingDao`. Follow patterns from auth/registration modules.

4. **Adopt AssertJ**: Refactor test assertions to use AssertJ for fluent, readable assertions as per project conventions.

5. **Split `CarrierService`**: Extract responsibilities into focused services:
   - `CarrierLookupService` — carrier data retrieval
   - `PortPairManagementService` — port-pair CRUD
   - `ElasticSearchPurgeService` — index management
   - `ServiceEnablementService` — rate limiting config

6. **Fix Retry Strategy**: Replace the always-true `CustomRetryCondition` with proper error classification (retry only on transient errors, throttling, clock skew).

7. **Remove Dual JSON Annotations**: Standardize `ElasticSearchSchedule`/`ElasticSearchLeg` on Jackson only. Remove Gson dependency if unused elsewhere.

8. **Upgrade Swagger to OpenAPI 3.0**: Migrate from Swagger 1.5 to OpenAPI 3.0 with the `swagger-core` 2.x library for modern API documentation.

9. **Upgrade commons to Latest**: Move to `1.0.22-SNAPSHOT` (or latest) to benefit from cloud-sdk libraries and recent fixes.

10. **Add Parameterized Tests**: Carrier builder tests follow identical patterns with different data. Use JUnit 5 `@ParameterizedTest` to reduce duplication.

11. **Introduce `@Nested` Test Classes**: Group related test cases (e.g., valid/invalid input, success/error paths) using `@Nested` for better organization as per project conventions.

12. **Centralize ObjectMapper**: Inject Jackson `ObjectMapper` via Guice instead of static instances in `SharedUtil` and `OSProcessService`.

13. **Consider Structured User Data Storage**: Replace JSON-in-column pattern for user preferences/recent searches with proper relational or DynamoDB modeling.

14. **Add Health Checks**: Add health checks for external carrier APIs, Elasticsearch, and DynamoDB in the Dropwizard health check framework to improve operational visibility.

15. **Spark Version Consistency**: Standardize Spark version (3.5.3) and Hadoop version (3.3.4) across all process modules to avoid classpath conflicts.

---

> **Next Steps**: The AWS SDK v2 migration should begin with this module after the booking module upgrade is complete. Use this document as the baseline for planning the migration scope and identifying all AWS touchpoints that need to change.
