# Network Module — Architecture & Design Document

**Platform:** Mercury Services  
**Module:** `network`  
**Document Version:** 1.0  
**Date:** 2026-05-04  
**Audience:** Senior Software Engineers

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [Maven Dependency Overview](#3-maven-dependency-overview)
4. [High-Level Architecture](#4-high-level-architecture)
5. [Submodule Breakdown](#5-submodule-breakdown)
6. [Key Classes Reference](#6-key-classes-reference)
7. [Guice Dependency Injection Wiring](#7-guice-dependency-injection-wiring)
8. [Database Architecture](#8-database-architecture)
9. [REST API Summary](#9-rest-api-summary)
10. [Data Flow Diagrams](#10-data-flow-diagrams)
11. [External Integrations](#11-external-integrations)
12. [Design Patterns](#12-design-patterns)
13. [Configuration Reference](#13-configuration-reference)
14. [Inter-Service Communication](#14-inter-service-communication)

---

## 1. Executive Summary

The `network` module is the central microservice of the Mercury Services platform, owned by WiseTech Global (formerly INTTRA). It serves as the **authoritative registry** and **orchestration layer** for all network-level entities on the global trade network:

- **Network Participants** (shipping companies, freight forwarders, carriers, NVOCCs)
- **Geography data** (countries, ports, locations, trade lanes)
- **Subscriptions** (module-level entitlements per company)
- **User management** (provisioning/deprovisioning)
- **Commercial Entities and Alliance Partners** (contractual groupings of participants)
- **Carrier Connections** (connectivity between network participants)
- **Reference Data** (container types, package types, HS codes, status event codes)
- **Audit Trail** (change tracking across all entities)
- **Monitoring** (application status broadcasting)

The module is a **Dropwizard 4.x** JAX-RS application, using **Google Guice** for dependency injection and **MyBatis** as the SQL mapper framework. Persistence is split across three distinct databases: an **Aurora MySQL** cluster (primary read/write + read replica), an **Oracle legacy database** (INTTRA Oracle DB), an **Oracle XLog DB**, and **Amazon DynamoDB** (for subscriptions, blacklist emails, message register, optional validations, and connections audit trail).

The application boots from the `server` submodule's `NetworkServices.main()`, assembles all Guice modules, registers all JAX-RS resources (50+ endpoints), and starts listening for HTTP traffic.

---

## 2. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| **Language** | Java | 17 |
| **Framework** | Dropwizard | 4.0.16 |
| **DI Container** | Google Guice (via Dropwizard-Guicey) | included via `commons` |
| **SQL Mapper** | MyBatis (custom `MyCustomBatisModule`) | included via `commons` |
| **JSON** | Jackson Databind | 2.19.2 |
| **Jackson Dataformat CBOR** | jackson-dataformat-cbor | 2.19.2 |
| **Jackson JSR310** | jackson-datatype-jsr310 | 2.19.2 |
| **Logging** | SLF4J + Logback | 1.5.18 |
| **Log4j bridge** | log4j-to-slf4j | 2.17.2 |
| **Lombok** | Project Lombok | from parent |
| **Aurora MySQL Driver** | aws-mysql-jdbc | 1.1.10 |
| **Oracle JDBC** | ojdbc10 | 19.14.0.0 |
| **AWS DynamoDB SDK v2** | via `cloud-sdk-aws` | 1.0.23-SNAPSHOT |
| **AWS SES (Email)** | via `cloud-sdk-aws` | 1.0.23-SNAPSHOT |
| **AWS S3 (Storage)** | via `cloud-sdk-aws` | 1.0.23-SNAPSHOT |
| **SOAP/JAX-WS (EORI)** | jaxws-rt | 4.0.3 |
| **Build** | Maven with maven-shade-plugin | 3.5.3 |
| **Test (Unit)** | JUnit 5 | 5.12.2 |
| **Test (Unit, legacy)** | JUnit 4 | 4.13.2 |
| **Test (Mocking)** | Mockito | 5.20.0 |
| **Test (Assertions)** | AssertJ | 3.27.2 |
| **Test (DynamoDB Local)** | dynamo-integration-test | 1.0.23-SNAPSHOT |
| **Test (Aurora Embedded)** | wix-embedded-mysql | 2.1.4 |
| **Test (IT)** | Dropwizard Testing | 4.0.16 |
| **XSS Protection** | Custom XSSFilter + XSSInterceptor | internal |
| **Metrics** | Dropwizard Metrics (`@Timed`) | included |
| **Excel Export** | Apache POI (via `excel` module) | internal |
| **Guava** | Google Guava | 32.1.3-jre |
| **Apache Commons Lang** | commons-lang3 | via `commons` |

---

## 3. Maven Dependency Overview

### Root POM (`network/pom.xml`) — Parent: `mercury-services:1.0`

```
com.inttra.mercury:network:1.0  (pom)
  ├── com.inttra.mercury:alliance-partner:1.0
  ├── com.inttra.mercury:blacklist-email:1.0
  ├── com.inttra.mercury:configuration-service:1.0
  ├── com.inttra.mercury:geography:1.0
  ├── com.inttra.mercury:message-register:1.0
  ├── com.inttra.mercury:network-participant:1.0
  ├── com.inttra.mercury:optionalvalidations:1.0
  ├── com.inttra.mercury:providers:1.0.0
  ├── com.inttra.mercury:referencedata:1.0
  ├── com.inttra.mercury:server:1.0                 <-- main executable
  ├── com.inttra.mercury:subscriptions:1.0
  ├── com.inttra.mercury:ums:1.0
  ├── com.inttra.mercury:user:1.0
  ├── com.inttra.mercury:user-service:1.0
  ├── com.inttra.mercury:xlog:1.0
  ├── com.inttra.mercury:audit-trail:1.0
  ├── com.inttra.mercury:models-interfaces:1.0
  ├── com.inttra.mercury:external-service:1.0
  ├── com.inttra.mercury:monitoring:1.0
  └── com.inttra.mercury:commercial-entity:1.0
```

### Key Transitive Dependencies (declared in `server/pom.xml`)

```
com.inttra.mercury:server:1.0
  ├── com.inttra.mercury:commons:1.0.23-SNAPSHOT         (Dropwizard, MyBatis, common infra)
  ├── com.inttra.mercury:cloud-sdk-api:1.0.23-SNAPSHOT   (DynamoDB/S3/SES interfaces)
  ├── com.inttra.mercury:cloud-sdk-aws:1.0.23-SNAPSHOT   (AWS SDK v2 implementations)
  ├── software.aws.rds:aws-mysql-jdbc:1.1.10             (Aurora MySQL IAM-auth driver)
  ├── com.oracle.database.jdbc:ojdbc10:19.14.0.0         (Oracle JDBC)
  ├── com.sun.xml.ws:jaxws-rt:4.0.3                      (SOAP/WSDL, via external-service)
  ├── com.fasterxml.jackson.core:jackson-databind:2.19.2
  ├── com.fasterxml.jackson.core:jackson-core:2.19.2
  ├── com.fasterxml.jackson.dataformat:jackson-dataformat-cbor:2.19.2
  ├── com.fasterxml.jackson.datatype:jackson-datatype-jsr310:2.19.2
  ├── ch.qos.logback:logback-classic:1.5.18
  ├── ch.qos.logback:logback-core:1.5.18
  ├── com.google.guava:guava:32.1.3-jre
  ├── com.amazonaws:aws-java-sdk-dynamodb:1.12.721        (test scope — DynamoDB Local)
  └── javax.validation:validation-api:1.1.0.Final
```

---

## 4. High-Level Architecture

### 4.1 Layered Architecture (Single Service, Multiple Submodules)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           NETWORK-SERVICES JVM                                   │
│                    (com.inttra.mercury.NetworkServices)                           │
│                    Dropwizard 4.x  |  Java 17  |  Guice DI                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                  JERSEY (JAX-RS) API LAYER                                  │ │
│  │  XSSFilter → XSSInterceptor → @RolesAllowed → Resource → @Timed metrics    │ │
│  │                                                                             │ │
│  │  /reference/participants   /geography/*     /subscription/*                │ │
│  │  /commercial-entity/*      /alliance-partner/*  /audittrail/*              │ │
│  │  /blacklist-email/*        /xlog/*          /ums/*                         │ │
│  │  /monitoring/status/*      /externalservice/eori/*  /connections/*         │ │
│  │  /reference/*  /providers/*  /user/*  /users/*  ... (50+ endpoints)        │ │
│  └────────────────────────────────┬────────────────────────────────────────────┘ │
│                                   │ Guice @Inject                                │
│  ┌─────────────────────────────────▼────────────────────────────────────────────┐ │
│  │                      SERVICE LAYER                                           │ │
│  │                                                                             │ │
│  │  NetworkParticipantService   ConnectionService    SubscriptionsService      │ │
│  │  CommercialEntityService     AlliancePartnerService  AuditTrailService      │ │
│  │  EORIValidationService       StatusService         UserMgmtService          │ │
│  │  ComplianceScreeningService  XlogService           BlacklistEmailService    │ │
│  │  ConfigurationService        RewardsService        ProviderService          │ │
│  │  GeographyService            ParticipantAliasService  LocationAliasService  │ │
│  └─────┬────────────────────────────┬──────────────────────────────────────────┘ │
│        │ MyBatis                    │ cloud-sdk / DynamoDB                       │
│  ┌─────▼────────────────┐  ┌────────▼────────────────────────────────────────┐  │
│  │    DAO / MAPPER LAYER │  │         NOSQL DAO LAYER (DynamoDB)              │  │
│  │   (MyBatis Mappers)   │  │                                                 │  │
│  │                       │  │  SubscriptionsDao    BlacklistEmailDao           │  │
│  │  Aurora Primary:      │  │  MessageRegisterDao  OptionalValidationsDao      │  │
│  │   NetworkParticipant  │  │  ConnectionsAuditTrailDao                        │  │
│  │   ConnectionsMapper   │  └────────────────────────────────────────────────┘  │
│  │   CommercialEntity    │                                                        │
│  │   AlliancePartner     │                                                        │
│  │   AuditTrailMapper    │                                                        │
│  │   GeographyMapper     │                                                        │
│  │   UIConfiguration     │                                                        │
│  │   UserMapper          │                                                        │
│  │   ... (30+ mappers)   │                                                        │
│  │                       │                                                        │
│  │  Aurora ReadOnly:     │                                                        │
│  │   CarrierServiceMapper│                                                        │
│  │   ContainerTypeMapper │                                                        │
│  │   NetworkParticipant  │                                                        │
│  │   ReadOnlyMapper      │                                                        │
│  │   ... (15+ mappers)   │                                                        │
│  │                       │                                                        │
│  │  Oracle INTTRA DB:    │                                                        │
│  │   InttraCompanyMapper │                                                        │
│  │   InttraUserMapper    │                                                        │
│  │   ConnectionInttra    │                                                        │
│  │   Mapper              │                                                        │
│  │   ... (12 mappers)    │                                                        │
│  │                       │                                                        │
│  │  Oracle XLog DB:      │                                                        │
│  │   XlogMapper          │                                                        │
│  └───────────────────────┘                                                        │
│                                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Database Topology

```
                    ┌────────────────────────────────────────────────────┐
                    │              Network Services JVM                   │
                    └─────┬──────────────┬──────────────┬───────────────┘
                          │              │              │
           ┌──────────────▼──┐  ┌────────▼──────┐  ┌──▼────────────────────┐
           │ Aurora MySQL     │  │ Oracle DB      │  │ Amazon DynamoDB        │
           │ (Mercury DB)     │  │ (INTTRA Legacy)│  │                        │
           │                 │  │                │  │  Tables:               │
           │  Primary (RW):  │  │  InttraDB      │  │  - BlacklistEmail       │
           │  All write ops  │  │  (company data,│  │  - OptionalValidation   │
           │                 │  │   users,       │  │  - MessageRegister      │
           │  ReadOnly (RO): │  │   connections, │  │  - ConnectionsAuditTrail│
           │  Read queries   │  │   aliases,     │  │  - Subscription         │
           │  Reference data │  │   partnerships)│  │                        │
           │                 │  │                │  │                        │
           │  XLog DB:       │  │  Oracle XLog   │  │                        │
           │  (separate DB,  │  │  (transaction  │  │                        │
           │   Oracle)       │  │   logs)        │  │                        │
           └─────────────────┘  └────────────────┘  └────────────────────────┘
```

### 4.3 External Systems

```
                        ┌──────────────────────┐
                        │  Network Services JVM  │
                        └──┬──────────┬──────────┘
                           │          │
         ┌─────────────────▼──┐  ┌────▼──────────────────┐
         │ EU EORI Validation  │  │  AWS Services          │
         │ SOAP WebService     │  │                        │
         │ (External)          │  │  - SES (Email)         │
         │  URL from config    │  │  - S3 (File storage)   │
         │  JAX-WS SOAP client │  │  - DynamoDB            │
         └────────────────────┘  │  - Parameter Store     │
                                 └────────────────────────┘

         ┌────────────────────────────────────────────────┐
         │  Restricted Party Screening (RPS) Service       │
         │  (Internal microservice — HTTP REST client)     │
         │  Used by ComplianceScreeningResource            │
         └────────────────────────────────────────────────┘

         ┌────────────────────────────────────────────────┐
         │  WaveBL eBL Provider (External EBL provider)    │
         │  (HTTP REST integration via ProviderModule)     │
         └────────────────────────────────────────────────┘
```

---

## 5. Submodule Breakdown

| Submodule | Artifact ID | Purpose | Key Packages |
|---|---|---|---|
| **server** | `server:1.0` | Application entry point. Bootstraps Dropwizard, wires all Guice modules, registers all JAX-RS resources and MyBatis mappers. Produces the shaded runnable JAR. | `com.inttra.mercury` |
| **network-participant** | `network-participant:1.0` | Core domain: manages NetworkParticipants (companies on the network), entitlements, module migrations, aliases, compliance screening, connections, integration profiles, payments, and GLV participants. | `networkparticipant`, `alias`, `compliance`, `connections`, `integrationprofile`, `partnerships`, `paymentterms`, `participantaddon` |
| **geography** | `geography:1.0` | Location master data: countries, subdivisions, ports, custom locations, carrier services, trade lanes, geography file management and staging. | `geography`, `carrierservice`, `manage.geography` |
| **subscriptions** | `subscriptions:1.0` | DynamoDB-backed subscription management per module (BOOKING, VISIBILITY, etc.) with bulk search, export, and customization configurations. | `subscriptions` |
| **commercial-entity** | `commercial-entity:1.0` | Commercial entity registry — groups of companies under commercial contracts. Manages entity CRUD, company/contract mapping, staging import via Excel, and S3-based file management. | `commercialentity` |
| **alliance-partner** | `alliance-partner:1.0` | Alliance partner registry linking network participants in shipping alliances (e.g. THE Alliance, 2M). Manages partnerships. | `alliancepartner` |
| **audit-trail** | `audit-trail:1.0` | Cross-cutting change tracking. Records before/after snapshots for all audited entities, stored in Aurora with read/write split. | `audittrail` |
| **blacklist-email** | `blacklist-email:1.0` | DynamoDB-backed email blacklist service. Supports add, delete, validate, and SES bounce notifications. | `emailservice` |
| **configuration-service** | `configuration-service:1.0` | Aurora-backed UI configuration store per participant. | `configurationservice` |
| **message-register** | `message-register:1.0` | DynamoDB-backed register for messaging format configurations. | `messageRegister` |
| **optionalvalidations** | `optionalvalidations:1.0` | DynamoDB-backed optional validation definitions per participant module. | `optionalvalidations` |
| **providers** | `providers:1.0.0` | Pluggable eBL (Electronic Bill of Lading) provider framework. Currently supports WaveBL. Uses Strategy + MapBinder for provider routing. | `providers.common`, `providers.ebl.wavebl` |
| **referencedata** | `referencedata:1.0` | Static reference data: container types, package types, HS codes, DGS (Dangerous Goods), status event codes. Aurora ReadOnly. | `containertype`, `packagetype`, `hscode`, `dgs`, `statuseventcode` |
| **user** | `user:1.0` | User entity management — Mercury users and INTTRA legacy users. Dual-database (Aurora + Oracle INTTRA). | `user` |
| **user-service** | `user-service:1.0` | User service facade exposing read-only user data via REST. | `users` |
| **ums** | `ums:1.0` | User Management System proxy — orchestrates user provisioning/deprovisioning workflows through external UMS APIs. | `ums` |
| **xlog** | `xlog:1.0.0` | Oracle XLog database integration — read/write of transaction log entries used by legacy INTTRA systems. | `xlog` |
| **external-service** | `external-service:1.0` | External integrations: EU EORI number validation (SOAP), Divisions lookup. Caches EORI results in Aurora. | `externalservice.eori`, `externalservice.divisions` |
| **monitoring** | `monitoring:1.0` | Application status board — Aurora-backed CRUD for application operational states, exposed publicly at `/monitoring/status/current`. | `monitoring` |
| **models-interfaces** | `models-interfaces:1.0` | Shared model and interface definitions used across submodules. No resource or service classes. | cross-cutting |

---

## 6. Key Classes Reference

### 6.1 Entry Point & Configuration

| Class | Package | Role |
|---|---|---|
| `NetworkServices` | `com.inttra.mercury` | `main()` — assembles all Guice modules, registers resources and MyBatis mappers, boots Dropwizard InttraServer |
| `NetworkServicesConfig` | `com.inttra.mercury` | Dropwizard configuration bean — holds all DB factory configs, DynamoDB, subscription, geography, commercial entity, external service configs |

### 6.2 Guice Modules (all in `server` submodule)

| Class | Package | Role |
|---|---|---|
| `ServerModule` | `com.inttra.mercury` | Core bindings: S3 StorageClient, XSS filters, interface-to-impl bindings (SubscriptionReadOnlyService, UserReadOnlyService, ConfigurationReadOnlyService, BlacklistEmailReadOnlyService) |
| `NetworkDynamoModule` | `com.inttra.mercury.config` | Provides DynamoDB client config + all DynamoDB DAOs: BlacklistEmailDao, OptionalValidationsDao, MessageRegisterDao, ConnectionsAuditTrailDao, SubscriptionsDao |
| `NetworkEmailSenderModule` | `com.inttra.mercury` | Provides SES `EmailService` singleton with email template lists |
| `ServiceDefinitionModule` | `com.inttra.mercury` | Binds named `ServiceDefinition`s from config, binds `RestrictedPartyScreeningService`, `CompanyCreationConfig` |
| `SubscriptionModule` | `com.inttra.mercury` | Binds `SubscriptionConfig` from config |
| `NetworkParticipantModule` | `com.inttra.mercury` | Registers `PaycargoPaymentProvider` via `Multibinder<PaymentProvider>` |
| `CarrierConnectionsModule` | `com.inttra.mercury` | Binds `ConnectionRulesReadService`, `CarrierConnectionReadService`, `ConnectionNotificationServiceConfig`; starts `ConnectionsNotificationListener` background scheduler |
| `ProviderModule` | `com.inttra.mercury` | Registers WaveBL services in `MapBinder<String, ProviderInvocationService>` |
| `GeographyModule` | `com.inttra.mercury` | Binds named S3 bucket name for geography management file storage |
| `CommercialEntityModule` | `com.inttra.mercury` | Binds named S3 bucket name for commercial entity file storage |
| `MonitoringModule` | `com.inttra.mercury` | Placeholder module for monitoring configuration |
| `ExternalServiceModule` | `com.inttra.mercury.externalservice.module` | Provides SOAP `Validation` and `EORIValidation` beans from WSDL config URL |

### 6.3 JAX-RS Resources

| Class | Base Path | Submodule |
|---|---|---|
| `NetworkParticipantResource` | `/reference/participants` | network-participant |
| `CompanyResource` | `/reference/companies` | network-participant |
| `ConnectionsResource` | `/connections` | network-participant |
| `CarrierConnectionsResource` | `/connections/carrier` | network-participant |
| `CustomerConnectionsResource` | `/connections/customer` | network-participant |
| `ConnectionRulesResource` | `/connections/rules` | network-participant |
| `ComplianceScreeningResource` | `/compliance` | network-participant |
| `IntegrationProfileResource` | `/reference/integrationprofiles` | network-participant |
| `IntegrationProfileFormatResource` | `/reference/integrationprofileformats` | network-participant |
| `SubscriptionIPFResource` | `/subscription/ipf` | network-participant |
| `FormatResource` | `/reference/formats` | network-participant |
| `ModuleResource` | `/reference/modules` | network-participant |
| `LocationAliasResource` | `/reference/locationaliases` | network-participant |
| `ParticipantAliasResource` | `/reference/participantaliases` | network-participant |
| `PaymentTermsResource` | `/reference/paymentterms` | network-participant |
| `ParticipantAddOnsResource` | `/reference/participantaddons` | network-participant |
| `PartnershipResource` | `/reference/partnerships` | network-participant |
| `GlobalCompanyResource` | `/reference/globalcompanies` | network-participant |
| `CountryResource` | `/reference/countries` | geography |
| `SubdivisionResource` | `/reference/subdivisions` | geography |
| `LocationResource` | `/reference/locations` | geography |
| `CustomLocationResource` | `/reference/customlocations` | geography |
| `PartnerCustomLocationResource` | `/reference/partnercustomlocations` | geography |
| `GeographyResource` | `/reference/geography` | geography |
| `GeographyManagementResource` | `/manage/geography` | geography |
| `CarrierServiceResource` | `/reference/carrierservices` | geography |
| `CarrierServiceAutocompleteResource` | `/reference/carrierservices/autocomplete` | geography |
| `TradeLaneResource` | `/reference/tradelanes` | geography |
| `CountryContinentResource` | `/reference/countrycontinents` | geography |
| `SubscriptionsResource` | `/subscription` | subscriptions |
| `UIConfigurationResource` | `/reference/uiconfig` | configuration-service |
| `BlacklistEmailResource` | `/blacklist-email` | blacklist-email |
| `MessageRegisterResource` | `/reference/messageregister` | message-register |
| `OptionalValidationResource` | `/reference/optionalvalidations` | optionalvalidations |
| `ContainerTypeResource` | `/reference/containertypes` | referencedata |
| `PackageTypeResource` | `/reference/packagetypes` | referencedata |
| `HSCodeResource` | `/reference/hscodes` | referencedata |
| `DGSResource` | `/reference/dgs` | referencedata |
| `StatusEventCodeResource` | `/reference/statuseventcodes` | referencedata |
| `UserResource` | `/reference/users` | user |
| `UserServiceResource` | `/users` | user-service |
| `UMSServiceResource` | `/ums` | ums |
| `XlogServiceResource` | `/xlog` | xlog |
| `RewardsResource` | `/reference/rewards` | network-participant |
| `ProviderResource` | `/providers` | providers |
| `ProviderConfigurationResource` | `/providers/config` | providers |
| `WaveBLResource` | `/providers/ebl/wavebl` | providers |
| `CarrierEBLProviderResource` | `/reference/carrierebls` | network-participant |
| `CarrierEBLProviderConnectionResource` | `/reference/carrierebls/connections` | network-participant |
| `EBLProviderResource` | `/reference/eblproviders` | network-participant |
| `AuditTrailResource` | `/audittrail` | audit-trail |
| `DomainWhitelistResource` | `/reference/domainwhitelist` | network-participant |
| `EORIServiceResource` | `/externalservice/eori` | external-service |
| `DivisionsResource` | `/externalservice/divisions` | external-service |
| `StatusResource` | `/monitoring/status` | monitoring |
| `CommercialEntityResource` | `/commercial-entity` | commercial-entity |
| `CommercialEntityImportResource` | `/commercial-entity/import` | commercial-entity |
| `AlliancePartnerResource` | `/alliance-partner` | alliance-partner |

### 6.4 Services

| Class | Package | Role |
|---|---|---|
| `NetworkParticipantService` | `networkparticipant.service` | Core CRUD + search + entitlement + module migration + GLV + attribute management for NetworkParticipants |
| `MercuryCompanyService` | `networkparticipant.service.provider.mercury` | Mercury-DB-backed company operations |
| `ConnectionService` | `connections.service` | Manages connection records between participants (transactional, primary DB) |
| `ConnectionRulesService` | `connections.service` | Connection rules management; implements `ConnectionRulesReadService` |
| `CarrierConnectionService` | `connections.service` | Carrier-specific connections; implements `CarrierConnectionReadService` |
| `ConnectionInttraService` | `connections.service` | Bridges Oracle INTTRA DB for legacy connection operations |
| `SubscriptionsService` | `subscriptions.service` | DynamoDB CRUD for subscriptions; search, export, active-flag toggling; implements `SubscriptionReadOnlyService` |
| `CommercialEntityService` | `commercialentity.services` | CRUD for commercial entities, company/contract mapping, Excel export |
| `CommercialEntityImportService` | `commercialentity.services` | S3-based Excel import pipeline with staging |
| `AlliancePartnerService` | `alliancepartner.services` | Alliance partner CRUD, partner mapping/demapping |
| `AuditTrailService` | `audittrail.service` | Insert and query audit trails across entity types |
| `BlacklistEmailService` | `emailservice.service` | DynamoDB-backed email blacklist; implements `BlacklistEmailReadOnlyService` |
| `ConfigurationService` | `configurationservice.service` | Aurora UI configuration CRUD; implements `ConfigurationReadOnlyService` |
| `EORIValidationService` | `externalservice.eori.service` | SOAP calls to EU EORI validation + result caching in Aurora |
| `StatusService` | `monitoring.service` | Aurora-backed application status CRUD |
| `UserService` | `user.service` | User management across Mercury and legacy INTTRA; implements `UserReadOnlyService` |
| `XlogService` | `xlog.service` | Oracle XLog DB read/write (transactional) |
| `ComplianceScreeningService` | `compliance.services` | Sends compliance screening requests to RPS external service |
| `RewardsService` | `rewards.service` | Mercury DB rewards management for participants |
| `ParticipantAliasService` | `alias.service` | Mercury alias operations for participants |
| `ProviderService` | `providers.common.service` | Generic provider orchestration |
| `EBLProviderService` | `eblproviders.service` | eBL provider management |
| `ParticipantAddOnsService` | `participantaddon.service` | Participant add-on flags |

### 6.5 DAO / Mapper Classes (MyBatis — Aurora Primary)

| Class | Package | DB | Role |
|---|---|---|---|
| `NetworkParticipantMapper` | `networkparticipant.persistence.mapper.aurora` | Aurora Primary | Full CRUD for network_participant table |
| `NetworkParticipantReadOnlyMapper` | `networkparticipant.persistence.mapper.aurora` | Aurora ReadOnly | Reads for participant search |
| `NetworkParticipantEntitlementsMapper` | `networkparticipant.persistence.mapper.aurora` | Aurora Primary | Entitlement records |
| `ConnectionsMapper` | `connections.persistence.mapper` | Aurora Primary | Connection management |
| `ConnectionRuleMapper` | `connections.persistence.mapper` | Aurora Primary | Connection rule definitions |
| `CarrierConnectionMapper` | `connections.persistence.mapper` | Aurora Primary | Carrier-specific connections |
| `GeographyMapper` | `geography.persistence.mapper.aurora` | Aurora Primary | Location/geography inserts |
| `LocationMapper` | `geography.persistence.mapper.aurora` | Aurora Primary | Port/location master data |
| `CountryMapper` | `geography.persistence.mapper.aurora` | Aurora Primary | Country master data |
| `SubdivisionMapper` | `geography.persistence.mapper.aurora` | Aurora Primary | Subdivision (state/province) data |
| `CommercialEntityMapper` | `commercialentity.persistance` | Aurora Primary | Commercial entity CRUD |
| `CommercialEntityImportFileMapper` | `commercialentity.persistance` | Aurora Primary | Import file tracking |
| `CommercialEntityStagingDetailMapper` | `commercialentity.persistance` | Aurora Primary | Staging records |
| `AlliancePartnerMapper` | `alliancepartner.persistance` | Aurora Primary | Alliance partner CRUD |
| `AuditTrailMapper` | `audittrail.persistance.mapper` | Aurora Primary | Write audit trail entries |
| `AuditTrailReadOnlyMapper` | `audittrail.persistance.mapper` | Aurora ReadOnly | Query audit trails |
| `UIConfigurationMapper` | `configurationservice.persistence.aurora` | Aurora Primary | UI config CRUD |
| `UserMapper` | `user.persistence.mercury` | Aurora Primary | Mercury user CRUD |
| `GlobalCompanyMapper` | `globalcompany.persistence` | Aurora Primary | Global company grouping |
| `RewardsMapper` | `rewards.persistence.mapper` | Aurora Primary | Participant rewards |
| `EORIValidationResultMapper` | `externalservice.eori.persistance.mapper` | Aurora Primary | Cached EORI results |
| `StatusMapper` | `monitoring.persistence` | Aurora Primary | Application status CRUD |
| `DomainWhitelistMapper` | `domainwhitelist.persistence` | Aurora Primary | Email domain whitelist |
| `ProviderConfigurationMapper` | `providers.common.persistance` | Aurora Primary | Provider configuration |
| `XlogMapper` | `xlog.persistence.mapper` | Oracle XLog | XLog DB read/write |

### 6.6 DAO / Mapper Classes (MyBatis — Oracle INTTRA DB)

| Class | Package | DB | Role |
|---|---|---|---|
| `InttraCompanyMapper` | `networkparticipant.persistence.inttra.mapper.oracle` | Oracle INTTRA | Legacy company data |
| `InttraUserMapper` | `user.persistence.inttra` | Oracle INTTRA | Legacy user data |
| `ConnectionInttraMapper` | `connections.persistence.mapper` | Oracle INTTRA | Legacy connection data |
| `PartnershipInttraMapper` | `partnerships.persistence.mapper` | Oracle INTTRA | Partnership records |
| `ConnectionRuleInttraMapper` | `connections.persistence.mapper` | Oracle INTTRA | Legacy connection rules |
| `ParticipantAliasInttraMapper` | `alias.persistence` | Oracle INTTRA | Participant alias (legacy) |
| `LocationAliasInttraMapper` | `alias.persistence` | Oracle INTTRA | Location alias (legacy) |
| `InttraGlobalCompanyMapper` | `globalcompany.persistence` | Oracle INTTRA | Global company (legacy) |
| `AuditTrailInttraMapper` | `connections.persistence.mapper` | Oracle INTTRA | Legacy audit trail |

### 6.7 DynamoDB DAO Classes

| Class | Package | DynamoDB Table (logical) | Role |
|---|---|---|---|
| `BlacklistEmailDao` | `emailservice.persistence` | `BlacklistEmail` | Email blacklist CRUD |
| `OptionalValidationsDao` | `optionalvalidations.persistance` | `OptionalValidation` | Optional validation definitions |
| `MessageRegisterDao` | `messageRegister.dao` | `MessageRegister` | Message format register |
| `ConnectionsAuditTrailDao` | `connections.persistence` | `ConnectionsAuditTrail` | Connections audit trail (composite key: partition + sort) |
| `SubscriptionsDao` | `subscriptions.persistence` | `Subscription` | Subscriptions (encrypted) |

---

## 7. Guice Dependency Injection Wiring

### 7.1 Module Registration Order in `NetworkServices.main()`

```
InttraServer builder
  │
  ├── MyCustomBatisModule("mySql-aurora-network-readonly")
  │     Aurora ReadOnly datasource
  │     Mappers: DatabaseHealthCheckMapper, CarrierServiceMapper, ContainerTypeMapper,
  │              PackageTypeMapper, HSCodeMapper, UserReadOnlyMapper, NetworkParticipantReadOnlyMapper,
  │              AuditTrailReadOnlyMapper, ... (15 total)
  │
  ├── MyCustomBatisModule("mySql-aurora-network-primary")
  │     Aurora Primary datasource
  │     Mappers: NetworkParticipantMapper, ConnectionsMapper, GeographyMapper, UIConfigurationMapper,
  │              CommercialEntityMapper, AlliancePartnerMapper, AuditTrailMapper, ... (30+ total)
  │     Transactional services: CompanyService, ConnectionService, CommercialEntityService,
  │                             AlliancePartnerService, RewardsService, StatusService, ...
  │
  ├── MyCustomBatisModule("oracle-xlog")
  │     Oracle XLog datasource
  │     Mappers: XlogMapper
  │     Transactional services: XlogService
  │
  ├── MyCustomBatisModule("oracle-inttradb")
  │     Oracle INTTRA datasource
  │     Mappers: InttraCompanyMapper, InttraUserMapper, ConnectionInttraMapper, ...
  │     Transactional services: InttraCompanyService, UserService, InttraUserService, ...
  │
  ├── LocalCacheModule (Custom location in-memory cache)
  │
  ├── ServerModule
  │     bind(StorageClient) → S3 instance
  │     register(XSSInterceptor, XSSFilter, MultiPartFeature)
  │     bind(SubscriptionReadOnlyService) → SubscriptionsService
  │     bind(UserReadOnlyService) → UserService
  │     bind(ConfigurationReadOnlyService) → ConfigurationService
  │     bind(BlacklistEmailReadOnlyService) → BlacklistEmailService
  │     @Provides UIServiceConfig
  │
  ├── NetworkDynamoModule
  │     @Provides DynamoDbClientConfig
  │     @Provides DynamoDbClient
  │     @Provides BlacklistEmailDao (partition key)
  │     @Provides OptionalValidationsDao (partition key)
  │     @Provides MessageRegisterDao (partition key, scan-enabled)
  │     @Provides ConnectionsAuditTrailDao (composite key)
  │     @Provides SubscriptionsDao (partition key + encrypted)
  │
  ├── NetworkEmailSenderModule
  │     @Provides EmailService (SES, with template list)
  │
  ├── ServiceDefinitionModule
  │     bind(ServiceDefinition) annotatedWith Names for each named service
  │     bind(RestrictedPartyScreeningService)
  │     bind(CompanyCreationConfig)
  │     bind("adminLegacyUserId")
  │
  ├── SubscriptionModule
  │     bind(SubscriptionConfig)
  │
  ├── NetworkParticipantModule
  │     Multibinder<PaymentProvider> ← PaycargoPaymentProvider
  │
  ├── CarrierConnectionsModule
  │     bind("UniqueInstanceId") ← timestamp+UUID
  │     bind(ConnectionRulesReadService) → ConnectionRulesService
  │     bind(CarrierConnectionReadService) → CarrierConnectionService
  │     bind(ConnectionNotificationServiceConfig)
  │     postSetupHook: start ConnectionsNotificationListener (FixedDelayListenerManager)
  │
  ├── ProviderModule
  │     MapBinder<String, ProviderInvocationService>
  │       ← "EBL_WAVEBL_REGISTER" → WaveBLProviderRegistrationService
  │       ← "EBL_WAVEBL_CONNECTION" → WaveBLProviderConnectionService
  │
  ├── ExcelModule
  │     Excel configuration + temp file purge processor
  │
  ├── GeographyModule
  │     bind("GEO_MANAGEMENT_FILE_STORAGE") ← S3 bucket name
  │
  ├── ExternalServiceModule
  │     @Provides Validation (SOAP service from WSDL URL)
  │     @Provides EORIValidation (port from Validation service)
  │     @Provides int (EORI cache expiration minutes)
  │
  ├── MonitoringModule (no additional bindings currently)
  │
  └── CommercialEntityModule
        bind("ENTITY_PARTNER_MANAGEMENT_FILE_STORAGE") ← S3 bucket name
```

### 7.2 Interface-to-Implementation Bindings

```
Interface                      →  Implementation
─────────────────────────────────────────────────────────────────────
SubscriptionReadOnlyService    →  SubscriptionsService
UserReadOnlyService            →  UserService
ConfigurationReadOnlyService   →  ConfigurationService
BlacklistEmailReadOnlyService  →  BlacklistEmailService
ConnectionRulesReadService     →  ConnectionRulesService
CarrierConnectionReadService   →  CarrierConnectionService
StorageClient                  →  S3StorageClient (singleton, factory)
EmailService                   →  SES EmailService (singleton)
PaymentProvider (Set)          →  { PaycargoPaymentProvider }
ProviderInvocationService(Map) →  { "WAVEBL_REG" → WaveBLProviderRegistrationService,
                                    "WAVEBL_CONN" → WaveBLProviderConnectionService }
```

---

## 8. Database Architecture

### 8.1 Aurora MySQL (Mercury DB) — Primary + Read Replica

The Aurora cluster is accessed via two separate MyBatis modules using the `aws-mysql-jdbc` driver (version 1.1.10), which supports IAM-based authentication and Aurora-specific failover.

**Key logical tables in Mercury Aurora DB:**

| Table Group | Tables (representative) | Module |
|---|---|---|
| Network Participants | `network_participant`, `network_participant_entitlement`, `network_participant_attribute`, `network_function`, `glv_participant` | network-participant |
| Connections | `connection`, `connection_rule`, `carrier_connection`, `connection_notification`, `carrier_ebl_provider_connection` | network-participant |
| Partnerships | `partnership` | network-participant |
| EBL Providers | `ebl_provider`, `carrier_ebl_provider` | network-participant |
| Aliases | `participant_alias`, `location_alias`, `shared_alias` | network-participant |
| Geography | `location`, `country`, `subdivision`, `custom_location`, `partner_custom_location`, `geography_staging`, `geography_file_details`, `geography_staging_audit` | geography |
| Carrier Services | `carrier_service`, `country_to_continent` | geography |
| Reference Data | `container_type`, `package_type`, `hs_code`, `dgs`, `dgs_package_type`, `status_event_code` | referencedata |
| Users | `user` (mercury), `legacy_user` | user |
| Global Companies | `global_company` | network-participant |
| Integration Profiles | `integration_profile`, `integration_profile_format` | network-participant |
| UI Configuration | `ui_configuration` | configuration-service |
| Subscriptions Customization | `customization_configuration` | subscriptions |
| Rewards | `reward` | network-participant |
| Domain Whitelist | `domain_whitelist` | network-participant |
| Modules | `module` | network-participant |
| Payment Terms | `payment_terms` | network-participant |
| Audit Trail | `audit_trail` | audit-trail |
| Provider Config | `provider_configuration`, `provider_invocation` | providers |
| EORI Results | `eori_validation_result` | external-service |
| Application Status | `application_status` | monitoring |
| Commercial Entity | `commercial_entity`, `commercial_entity_address`, `commercial_entity_contact`, `commercial_entity_contract`, `commercial_entity_import_file`, `commercial_entity_staging_detail` | commercial-entity |
| Alliance Partner | `alliance_partner`, `partnership` (alliance) | alliance-partner |
| Participant Add-Ons | `participant_add_ons` | network-participant |

### 8.2 Oracle INTTRA DB (Legacy)

Accessed via the `oracle-inttradb` MyBatis module using the `ojdbc10` driver (version 19.14.0.0). Represents legacy INTTRA Oracle data that co-exists with the Aurora DB during migration.

| Mapper | Purpose |
|---|---|
| `InttraCompanyMapper` | Legacy company data used for cross-reference |
| `InttraUserMapper` | Legacy INTTRA users |
| `ConnectionInttraMapper` | Connections in INTTRA schema |
| `ConnectionInttraMigrationMapper` | Migration of INTTRA connections to Mercury |
| `ConnectionRuleInttraMapper` | Legacy connection rules |
| `PartnershipInttraMapper` | Legacy partnerships |
| `ParticipantAliasInttraMapper` | Participant aliases in INTTRA |
| `LocationAliasInttraMapper` | Location aliases in INTTRA |
| `SharedAliasInttraMapper` | Shared cross-party aliases |
| `InttraGlobalCompanyMapper` | Legacy global company groupings |
| `AuditTrailInttraMapper` | INTTRA-side connection audit |
| `IntegrationProfileFormatInttraMapper` | Legacy IPF data |

### 8.3 Oracle XLog DB

Accessed via the `oracle-xlog` MyBatis module using `ojdbc10`. Contains transaction log entries used by legacy INTTRA messaging infrastructure.

| Mapper | Purpose |
|---|---|
| `XlogMapper` | CRUD for XLog entries (XlogDetail with nested Xlog model) |

### 8.4 DynamoDB Tables

All DynamoDB access is done via the `cloud-sdk-aws` abstraction (AWS SDK v2 Enhanced Client).

| DynamoDB Domain Class | Table Annotation | Key Type | Use |
|---|---|---|---|
| `BlacklistEmail` | `@Table(name="...")` | Partition (email string) | Blacklisted email entries |
| `OptionalValidation` | `@Table(name="...")` | Partition (string) | Optional validation definitions |
| `MessageRegister` | `@Table(name="...")` | Partition (string), scan enabled | Message format register |
| `ConnectionsAuditTrail` | `@Table(name="...")` | Composite (partition + sort, both string) | Connections audit history |
| `Subscription` | `@Table(name="...")` | Partition (hashKey string) | Module subscriptions (encrypted) |

**Table names** are prefixed by `DynamoDbClientConfig.tablePrefix` from config, enabling environment-specific table isolation (e.g., `dev-`, `prod-`).

---

## 9. REST API Summary

### 9.1 Network Participant APIs

| Method | Path | Auth / Roles | Description |
|---|---|---|---|
| GET | `/reference/participants/{id}` | Any authenticated | Get participant by ID |
| GET | `/reference/participants` | Any authenticated | Search participants (query params: globalId, name, inttraCompanyId, carrierId, scacCode, etc.) |
| GET | `/reference/participants/search` | Any authenticated | Paginated/sorted search returning `NetworkParticipants` envelope |
| POST | `/reference/participants` | Authenticated; `NETWORK_ADMIN` for registered | Create participant |
| PUT | `/reference/participants/{id}` | Authenticated; `NETWORK_ADMIN` for registered | Update participant |
| DELETE | `/reference/participants/{id}` | `NETWORK_ADMIN` | Delete participant |
| GET | `/reference/participants/branches` | Authenticated | Get same-tree company branches |
| GET | `/reference/participants/all` | Authenticated | All related participants in hierarchy |
| GET | `/reference/participants/entitlements` | Authenticated | Entitlements for a participant |
| GET | `/reference/participants/entitlements/all` | `NETWORK_ADMIN` | All available entitlements |
| GET | `/reference/participants/entitlementsbyidentifier` | Authenticated | Entitlements by identifier type |
| POST | `/reference/participants/entitlements` | `NETWORK_ADMIN` | Add entitlement |
| POST | `/reference/participants/{module}/submoduleentitlement` | `NETWORK_ADMIN` | Add sub-module entitlement |
| GET | `/reference/participants/{module}/submoduleentitlement` | Authenticated | Get sub-module entitlements |
| GET | `/reference/participants/{module}/submoduleentitlement/{id}` | `NETWORK_ADMIN` | Get specific sub-module entitlement |
| DELETE | `/reference/participants/{module}/submoduleentitlement/{id}` | `NETWORK_ADMIN` | Delete sub-module entitlement |
| POST | `/reference/participants/{id}/module/migrate` | `NETWORK_ADMIN` | Migrate module for participant |
| POST | `/reference/participants/{id}/module/unmigrate` | `NETWORK_ADMIN` | Unmigrate module |
| GET | `/reference/participants/glv` | Authenticated | Get all active GLV participants |
| PUT | `/reference/participants/glv/{inttraCompanyId}` | `NETWORK_ADMIN` | Add to GLV |
| POST | `/reference/participants/glv/{inttraCompanyId}/{status}` | `NETWORK_ADMIN` | Update GLV status |
| DELETE | `/reference/participants/glv/{inttraCompanyId}` | `NETWORK_ADMIN` | Delete GLV participant |
| PUT | `/reference/participants/{id}/networkfunction` | `NETWORK_ADMIN` | Update all network functions |
| POST | `/reference/participants/{id}/networkfunction` | `NETWORK_ADMIN` | Insert network function |
| DELETE | `/reference/participants/{id}/networkfunction/{code}` | `NETWORK_ADMIN` | Delete network function |
| GET | `/reference/participants/{id}/children` | Authenticated | (Deprecated) Children by inttraCompanyId |
| GET | `/reference/participants/{parentId}/v2/children` | Authenticated | Children by networkParticipantId |
| GET | `/reference/participants/reward/{inttraCompanyId}` | Authenticated | Get reward for participant |
| GET | `/reference/participants/attributes/{networkParticipantId}` | Authenticated | Get participant attributes |
| POST | `/reference/participants/attributes` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Add or update attribute |
| DELETE | `/reference/participants/attributes/{id}` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Delete participant attribute |
| GET | `/reference/participants/export` | Authenticated | Export company data as Excel |

### 9.2 Geography APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/reference/countries` | Authenticated | List countries |
| GET | `/reference/subdivisions` | Authenticated | List subdivisions |
| GET | `/reference/locations` | Authenticated | Search locations/ports |
| GET | `/reference/customlocations` | Authenticated | Custom locations |
| GET | `/reference/partnercustomlocations` | Authenticated | Partner custom locations |
| GET | `/reference/geography` | Authenticated | Combined geography search |
| GET/POST | `/manage/geography` | `NETWORK_ADMIN` | Geography staging management |
| GET | `/reference/carrierservices` | Authenticated | Carrier services |
| GET | `/reference/carrierservices/autocomplete` | Authenticated | Autocomplete for carrier services |
| GET | `/reference/tradelanes` | Authenticated | Trade lanes |
| GET | `/reference/countrycontinents` | Authenticated | Country-to-continent mapping |

### 9.3 Subscription APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| PUT | `/subscription` | Authenticated | Create or update subscription |
| POST | `/subscription/updateStatus/{hashKey}/{flag}` | Authenticated | Toggle active flag |
| GET | `/subscription/{moduleType}` | Authenticated | All subscriptions by module |
| GET | `/subscription/{moduleType}/{inttraCompanyId}` | Authenticated | Subscriptions by module + company |
| GET | `/subscription/{moduleType}/ediid/{ediId}` | Authenticated | By EDI ID |
| GET | `/subscription/{moduleType}/ftpid/{ftpId}` | Authenticated | By FTP ID |
| DELETE | `/subscription/{hashKey}` | `SUPER_ADMIN` | Delete subscription |
| GET | `/subscription/subscription/{hashKey}` | Authenticated | Get by hash key |
| GET | `/subscription/search` | Authenticated | Paginated/sorted search |
| GET | `/subscription/export` | Authenticated | Export as Excel |
| GET | `/subscription/{moduleType}/groupedpreferences` | Authenticated | Grouped preference definitions |
| GET | `/subscription/{moduleType}/preferences` | Authenticated | Preference definitions |
| GET | `/subscription/subscriptioncustomizationconfigs` | Authenticated | Customization configs |

### 9.4 Commercial Entity APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/commercial-entity` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Create commercial entity |
| GET | `/commercial-entity/{id}` | Authenticated | Get by ID |
| GET | `/commercial-entity/search` | Authenticated | Search entities |
| PUT | `/commercial-entity/{id}` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Edit entity |
| PUT | `/commercial-entity/{id}/mapCompanies` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Map network participants |
| PUT | `/commercial-entity/{id}/mapContracts` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Map contracts |
| DELETE | `/commercial-entity/{id}/demapCompanies` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Remove company mapping |
| DELETE | `/commercial-entity/{id}/demapContracts` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Remove contract mapping |
| POST | `/commercial-entity/contract` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Create contract |
| PUT | `/commercial-entity/contract` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Update contract |
| GET | `/commercial-entity/contract/{id}` | Authenticated | Get contract |
| GET | `/commercial-entity/contract/search` | Authenticated | Search contracts |
| PUT | `/commercial-entity/export` | INTTRA company only | Export as Excel |
| POST/GET | `/commercial-entity/import` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Import from Excel via S3 |

### 9.5 Alliance Partner APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/alliance-partner` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Create alliance partner |
| GET | `/alliance-partner/{id}` | Authenticated | Get by ID |
| GET | `/alliance-partner/search` | Authenticated | Search |
| GET | `/alliance-partner/partnerships` | Authenticated | Get partnerships for company |
| PUT | `/alliance-partner/{id}` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Edit alliance partner |
| PUT | `/alliance-partner/{id}/mapPartners` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Map partners |
| DELETE | `/alliance-partner/{id}/demapPartners/{networkParticipantId}` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Remove partner mapping |

### 9.6 Audit Trail APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/audittrail/` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Query audit trail by entityType + entityId with pagination |

### 9.7 Blacklist Email APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/blacklist-email/add` | Authenticated | Add/update blacklisted email |
| DELETE | `/blacklist-email/delete` | `NETWORK_ADMIN` | Remove from blacklist |
| POST | `/blacklist-email/validate` | Any | Filter list of emails against blacklist |
| POST | `/blacklist-email/all` | `NETWORK_ADMIN` | Paginated fetch all |
| POST | `/blacklist-email/find` | Authenticated | Find specific email |

### 9.8 External Service APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/externalservice/eori/validate` | Authenticated | Validate set of EORI numbers (max 95) via EU SOAP service |
| GET | `/externalservice/divisions` | Authenticated | Get divisions for a participant |

### 9.9 Monitoring APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/monitoring/status/current` | None (public) | Get active application statuses (external view) |
| GET | `/monitoring/status` | `NETWORK_USER` | All statuses with filters |
| GET | `/monitoring/status/{id}` | `NETWORK_USER` | Get status by ID |
| POST | `/monitoring/status` | `SUPER_ADMIN` (INTTRA company only) | Create status |
| PUT | `/monitoring/status/{id}` | `SUPER_ADMIN` (INTTRA company only) | Update status |
| DELETE | `/monitoring/status/{id}` | `SUPER_ADMIN` (INTTRA company only) | Delete status |

### 9.10 UMS (User Management System) APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/ums/workflows` | Authenticated | Get provisioning workflows |
| GET | `/ums/workflows/{workflowId}/attributes/{attributeId}/options` | `NETWORK_ADMIN` | Get attribute options |
| POST | `/ums/validateSelection` | Authenticated | Validate user selections |
| GET | `/ums/users/` | Authenticated | Get all managed users |
| GET | `/ums/users/{userId}` | Authenticated | Get user selections |
| POST | `/ums/users/{userId}` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Create/update user profile |
| PUT | `/ums/users/{userId}/selections` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Add selections |
| PATCH | `/ums/users/{userId}/selections` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN`, `USER_MGMT_ADMIN` | Modify selections |
| DELETE | `/ums/users/{userId}/selections` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Delete selections |

### 9.11 XLog APIs

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/xlog/{xlogid}` | Authenticated | Get XLog detail |
| POST | `/xlog/create` | Authenticated | Create new XLog entry |
| POST | `/xlog/update` | Authenticated | Update XLog entry |

---

## 10. Data Flow Diagrams

### 10.1 Standard REST Request Lifecycle

```
HTTP Client
    │
    │  HTTPS Request
    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Dropwizard / Jersey                                   │
│                                                                               │
│  ┌─────────────────┐    ┌──────────────────────────────────────────────────┐ │
│  │  XSSFilter      │    │  Authentication (InttraServer / JWT bearer)       │ │
│  │  (Query/Header  │───►│  Validates token → populates SecurityContext      │ │
│  │   XSS check)   │    │  → InttraPrincipal (companyId, userId, roles)     │ │
│  └─────────────────┘    └──────────────────────────────────────────────────┘ │
│                                    │                                           │
│                                    ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  XSSInterceptor                                                           │ │
│  │  (POST/PUT body payload XSS scan)                                        │ │
│  └────────────────────────────────┬─────────────────────────────────────────┘ │
│                                   │                                            │
│                                   ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  @RolesAllowed enforcement                                                │ │
│  │  (Jersey ContainerRequest filter)                                         │ │
│  └────────────────────────────────┬─────────────────────────────────────────┘ │
│                                   │                                            │
│                                   ▼                                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  Resource Method (@GET/@POST/...)                                          │ │
│  │  @Timed → Dropwizard Metrics timer                                        │ │
│  │  Bean Validation (@Valid, @NotNull, @Positive)                             │ │
│  └────────────────────────────────┬─────────────────────────────────────────┘ │
└────────────────────────────────────┼──────────────────────────────────────────┘
                                     │ @Inject
                                     ▼
                         ┌────────────────────┐
                         │   Service Layer     │
                         │  (Business logic,   │
                         │   orchestration,    │
                         │   validation)       │
                         └─────────┬──────────┘
                                   │
                     ┌─────────────┼─────────────────┐
                     │             │                   │
                     ▼             ▼                   ▼
              ┌──────────┐  ┌──────────┐       ┌─────────────┐
              │ MyBatis  │  │ DynamoDB │       │ External    │
              │ Mapper   │  │ DAO      │       │ Service     │
              │ (Aurora/ │  │          │       │ (SOAP/HTTP) │
              │ Oracle)  │  │          │       │             │
              └──────────┘  └──────────┘       └─────────────┘
                     │             │
                     ▼             ▼
              ┌──────────┐  ┌──────────┐
              │ Aurora   │  │ DynamoDB │
              │ MySQL or │  │          │
              │ Oracle   │  │          │
              └──────────┘  └──────────┘
                                     │
                          ┌──────────┘
                          ▼
               Exception Mappers
               (NetworkServiceExceptionMapper,
                InputValidationExceptionMapper,
                IllegalArgumentExceptionMapper)
                          │
                          ▼
                     HTTP Response
                   (JSON / Excel stream)
```

### 10.2 Network Participant Search Flow

```
Client: GET /reference/participants?name=MAERSK&scacCode=MAEU
    │
    ▼
NetworkParticipantResource.getNetworkParticipant(...)
    │
    │  Validates: at least one param non-empty
    │  Builds NetworkParticipantSearchAttributes (builder pattern)
    ▼
NetworkParticipantService.searchNetworkParticipant(attrs)
    │
    ▼
NetworkParticipantMapper.searchNetworkParticipants(attrs)
    │  (MyBatis, Aurora ReadOnly connection pool)
    ▼
Aurora MySQL ReadOnly
    SQL: SELECT * FROM network_participant
         WHERE name LIKE ? AND scac_code = ?
         AND (include_inactive = false → status = 'Active')
    │
    ▼
List<NetworkParticipant>
    │
    ▼
JSON serialization → HTTP 200
```

### 10.3 Subscription Create/Update Flow (DynamoDB)

```
Client: PUT /subscription
        Body: { inttraCompanyId: 12345, moduleType: "BOOKING", ... }
    │
    ▼
SubscriptionsResource.createOrUpdate(actor, subscription)
    │  Validates inttraCompanyId OR ediId/ftpId not empty
    │  Sets actor from SecurityContext
    ▼
SubscriptionsService.createOrUpdate(actor, subscription)
    │
    │  1. Resolves hashKey (= encrypted compound key)
    │  2. Fetches existing from DynamoDB (if exists)
    │  3. Applies business rules (actor permissions, module)
    │  4. Encrypts sensitive fields (via SubscriptionConfig/ParameterStore key)
    ▼
SubscriptionsDao.save(subscription)
    │
    ▼
DynamoDB Enhanced Client → PutItem → Subscription table
    │
    ▼
Returns saved Subscription → HTTP 200
```

### 10.4 EORI Validation Flow (SOAP External Integration)

```
Client: POST /externalservice/eori/validate
        Body: ["GB123456789012", "DE987654321098"]
    │
    ▼
EORIServiceResource.validateEORIList(eoriSet)
    │  Validates: set not empty, size <= 95
    ▼
EORIValidationService.validateEORIList(eoriSet)
    │
    │  For each EORI number:
    │  1. Check Aurora cache (EORIValidationResultMapper)
    │  2. If not cached or expired:
    │       a. Call EU SOAP service via EORIValidation (JAX-WS)
    │       b. Parse ValidateEORIResponse
    │       c. Store result in Aurora (EORIValidationResultMapper.insert)
    │  3. Return cached result
    ▼
Set<EORIDetails> → HTTP 200 JSON
```

### 10.5 Audit Trail Write Flow

```
Any Service (e.g., CommercialEntityService.editCommercialEntity)
    │
    │  1. Fetch existing entity (before state)
    │  2. Perform update
    │  3. Compute diff (before vs after via EntitySerializer)
    │  4. Build AuditTrail record (entityType, entityId, actorId, before, after, timestamp)
    ▼
AuditTrailService.addAuditTrail(auditTrail)
    │
    ▼
AuditTrailDao.insertIntoAuditTrail(auditTrail)
    │  (AuditTrailMapper → Aurora Primary)
    ▼
Aurora MySQL: INSERT INTO audit_trail (...)
```

### 10.6 Connection Notification Background Scheduler

```
Server startup
    │
    └── CarrierConnectionsModule.startConnectionNotificationServiceListener()
              │
              ▼
        FixedDelayListenerManager
          interval = connectionNotificationServiceConfig.getInvokeNotificationTimeIntervalInHours()
          TimeUnit = HOURS
              │
              Scheduled execution:
              ▼
        ConnectionsNotificationListener.run()
              │
              ▼
        Query pending connection notifications (Aurora)
              │
              ▼
        Send email notifications (SES EmailService)
```

### 10.7 Excel Import Flow (Commercial Entity)

```
Client: POST /commercial-entity/import
        (multipart/form-data, Excel file)
    │
    ▼
CommercialEntityImportResource.uploadFile(file)
    │
    ▼
CommercialEntityImportService.uploadImportFile(file, principal)
    │
    │  1. Upload file to S3 (ENTITY_PARTNER_MANAGEMENT_FILE_STORAGE bucket)
    │  2. Record file metadata in Aurora (CommercialEntityImportFileMapper)
    │  3. Parse Excel rows → staging records
    │  4. Validate each row (CommercialEntityValidationHelper)
    │  5. Insert valid rows to staging table (CommercialEntityStagingDetailMapper)
    │  6. Return file status summary
    ▼
CommercialEntityImportFile → HTTP 200

Later: GET /commercial-entity/import/{fileId}/process
    │
    ▼
CommercialEntityImportService.processImportFile(fileId, principal)
    │  1. Read staging records
    │  2. Upsert commercial entities (CommercialEntityMapper)
    │  3. Update file status
    ▼
CommercialEntityImportStatus → HTTP 200
```

---

## 11. External Integrations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Network Services                                      │
└──┬──────────────────┬───────────────┬──────────────────────┬────────────────┘
   │                  │               │                      │
   ▼                  ▼               ▼                      ▼
┌──────────┐  ┌───────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ EU EORI  │  │ RPS       │  │ WaveBL Provider  │  │  AWS Services         │
│ Validation│  │ Restricted│  │ (eBL)            │  │                      │
│ Service  │  │ Party     │  │                  │  │  SES — Email          │
│          │  │ Screening │  │  Registration    │  │  (user/connection     │
│ Protocol:│  │ Service   │  │  Connection      │  │   notifications,      │
│ SOAP/    │  │           │  │  status updates  │  │   email templates)    │
│ JAX-WS   │  │ Protocol: │  │                  │  │                      │
│          │  │ REST HTTP │  │  Protocol:       │  │  S3 — File storage   │
│ URL:     │  │           │  │  REST HTTP       │  │  (geography files,    │
│ config   │  │ URL:      │  │                  │  │   commercial entity   │
│ (eoriUrl)│  │ service-  │  │  URL: per        │  │   import files)      │
│          │  │ definition│  │  ProviderConfig  │  │                      │
│ Caching: │  │ config    │  │  in Aurora       │  │  DynamoDB — NoSQL    │
│ Aurora   │  │           │  │                  │  │  (subscriptions,     │
└──────────┘  └───────────┘  └──────────────────┘  │   blacklist,         │
                                                    │   message register,  │
                                                    │   audit trail)       │
                                                    │                      │
                                                    │  Parameter Store —   │
                                                    │  Secrets (DynamoDB   │
                                                    │  encryption keys)    │
                                                    └──────────────────────┘
```

**Integration Details:**

| Integration | Mechanism | Module | Notes |
|---|---|---|---|
| EU EORI Validation | JAX-WS SOAP, generated stubs | `external-service` | WSDL URL configured in `external-service.eoriUrl`; results cached in Aurora |
| Restricted Party Screening | Jersey HTTP client (REST) | `network-participant` | ServiceDefinition named "rpsServiceDefinition" |
| WaveBL eBL Provider | REST HTTP client | `providers` | Provider config in Aurora DB; two services: registration + connection |
| AWS SES | SDK v2 via cloud-sdk-aws | Cross-cutting | Templates loaded at startup; used for connection notifications, user notifications |
| AWS S3 | SDK v2 via cloud-sdk-aws | `geography`, `commercial-entity` | File upload/download for import/export |
| AWS DynamoDB | SDK v2 via cloud-sdk-aws | Multiple modules | Subscriptions, blacklist, message register, optional validations, connections audit |
| AWS Parameter Store | SDK v2 | `subscriptions` | Encryption key retrieval for subscription data |

---

## 12. Design Patterns

### 12.1 Repository Pattern
DAOs (MyBatis Mappers + DynamoDB DAOs) abstract persistence completely from services. Services never write SQL directly.

```
Resource → Service → DAO/Mapper → Database
```

### 12.2 Strategy Pattern (Provider Framework)
The `providers` module uses a `MapBinder<String, ProviderInvocationService>` to plug in different eBL provider implementations. Adding a new provider requires implementing `ProviderInvocationService` and binding it with a key in `ProviderModule`.

```java
MapBinder<String, ProviderInvocationService>
  ← "EBL_WAVEBL_REGISTER" → WaveBLProviderRegistrationService
  ← "EBL_WAVEBL_CONNECTION" → WaveBLProviderConnectionService
```

### 12.3 Builder Pattern
Extensively used for all model/search objects (Lombok `@Builder`):
- `NetworkParticipantSearchAttributes.builder()`
- `SubscriptionSearchAttributes.builder()`
- `NetworkParticipant.builder()`

### 12.4 Factory Pattern
- `StorageClientFactory.createDefaultS3Client()` — creates S3 client
- `EmailClientFactory.createDefaultSesClient(templateList)` — creates SES client
- `DynamoRepositoryFactory.createEnhancedRepository(...)` — creates DynamoDB repositories
- `SoapClientFactory` — creates SOAP clients for EORI service

### 12.5 Multibinder Pattern (Guice)
Used for the payment provider registry:
```java
Multibinder<PaymentProvider>
  ← PaycargoPaymentProvider
```

### 12.6 Read/Write Split Pattern
Distinct MyBatis modules bind to separate Aurora connection pools:
- `mySql-aurora-network-primary` → all write + complex read operations
- `mySql-aurora-network-readonly` → read-only queries for high-traffic reference data

Interfaces are used to ensure services use the correct connection:
```java
SubscriptionReadOnlyService → SubscriptionsService (primary)
ConfigurationReadOnlyService → ConfigurationService
```

### 12.7 Facade Pattern (UMS)
`UMSServiceResource` is a facade that delegates all user provisioning operations to the `WorkflowService`, `OptionsService`, and `UserMgmtService`, which in turn proxy calls to an external UMS system.

### 12.8 Decorator Pattern (XSS Protection)
`XSSInterceptor` (body) and `XSSFilter` (headers/query params) decorate all incoming requests transparently through Jersey filter chain registration.

### 12.9 Observer / Listener Pattern
`ConnectionsNotificationListener` runs as a managed background `FixedDelayListenerManager`, polling for connection notification events and dispatching email notifications — a scheduled Observer over the connections state.

### 12.10 Command Pattern (Dropwizard Tasks)
`CountryMasterDataUpload`, `SubdivisionMasterDataUpload`, `LocationMasterDataUpload` are registered Dropwizard `Task` objects, invocable via the admin endpoint for bulk data upload operations.

### 12.11 Staging / Pipeline Pattern (Import)
Commercial entity and geography imports follow a multi-stage pipeline:
```
Upload → S3 storage → Parse Excel → Staging table → Validate → Process → Entities
```

### 12.12 Cache-Aside Pattern
EORI validation results are cached in Aurora:
```
Request → Check Aurora cache → HIT: return → MISS: call SOAP → store in Aurora → return
```

---

## 13. Configuration Reference

All configuration lives in `NetworkServicesConfig`, which extends the common `ApplicationConfiguration`:

| Config Property | Type | Required | Purpose |
|---|---|---|---|
| `database` | `DataSourceFactory` | YES | Aurora MySQL primary connection pool |
| `readOnlyDatabase` | `DataSourceFactory` | YES | Aurora MySQL read-only connection pool |
| `xlogDatabase` | `DataSourceFactory` | YES | Oracle XLog DB connection pool |
| `inttraDatabase` | `DataSourceFactory` | YES | Oracle INTTRA DB connection pool |
| `dynamoDbConfig` | `BaseDynamoDbConfig` | YES | DynamoDB endpoint, region, table prefix, credentials |
| `subscriptionConfig` | `SubscriptionConfig` | YES | DynamoDB subscription table name, encryption config |
| `customLocationCacheConfig` | `CustomLocationCacheConfig` | NO | In-memory cache TTL and size for custom locations |
| `rpsServiceDefinition` | `ServiceDefinition` | YES | URL + credentials for Restricted Party Screening service |
| `companyCreationConfig` | `CompanyCreationConfig` | YES | Admin user ID for company creation approvals |
| `connectionNotificationServiceConfig` | `ConnectionNotificationServiceConfig` | YES | Scheduling interval (hours) for connection notification polling |
| `excelConfiguration` | `ExcelConfiguration` | YES | Temp file directory, purge interval for Excel exports |
| `geographyManagementConfig` | `GeographyManagementConfig` | YES | S3 bucket name for geography import/export files |
| `entityPartnerManagementConfig` | `EntityPartnerManagementConfig` | YES | S3 bucket name for commercial entity import/export files |
| `uiServiceConfig` | `UIServiceConfig` | YES | UI configuration service parameters |
| `external-service` | `ExternalServiceConfiguration` | YES | EORI validation SOAP URL + cache expiration minutes |
| `serviceDefinitions` (list) | `List<ServiceDefinition>` | NO | Named service definitions for inter-service calls |

### DataSourceFactory (each pool) key properties:
- `url` — JDBC connection URL (Aurora: `jdbc:mysql://...`, Oracle: `jdbc:oracle:thin:@//...`)
- `user` / `password` — credentials
- `maxSize` — connection pool max
- `minSize` — connection pool min
- `validationQuery` — health check query

### DynamoDB Config (BaseDynamoDbConfig) key properties:
- `region` — AWS region
- `endpoint` — optional override (for local testing)
- `tablePrefix` — prefix applied to all DynamoDB table names
- `consistentRead` — set to `false` in `NetworkDynamoModule`

---

## 14. Inter-Service Communication

### 14.1 Service-to-Service Calls (Outbound)

```
Network Services
    │
    ├── Restricted Party Screening (RPS) Service
    │     Mechanism: Jersey HTTP REST client
    │     Config: rpsServiceDefinition (URL, clientConfig)
    │     Used by: ComplianceScreeningService
    │     Pattern: Synchronous REST call per compliance screening request
    │
    ├── EU EORI Validation
    │     Mechanism: JAX-WS SOAP client (jaxws-rt 4.0.3)
    │     Config: external-service.eoriUrl
    │     Used by: EORIValidationService
    │     Pattern: Synchronous, with Aurora cache-aside
    │
    └── WaveBL eBL Provider
          Mechanism: REST HTTP client
          Config: ProviderConfiguration from Aurora DB
          Used by: WaveBLProviderRegistrationService, WaveBLProviderConnectionService
          Pattern: Synchronous REST; invocation tracked in ProviderInvocation table
```

### 14.2 Inbound Authentication

The service relies on the `commons` library's `InttraServer` for authentication. Every request passes through JWT bearer token validation. The decoded token produces an `InttraPrincipal` with:
- `id` — user ID
- `companyId` — INTTRA company ID (key for participant lookup)
- `roles` — set of role strings (`NETWORK_ADMIN`, `SUPER_ADMIN`, `COMPANY_USER_ADMIN`, `USER_MGMT_ADMIN`, `NETWORK_USER`, `COMMERCIAL_ENTITY_PARTNER_MGR`)

### 14.3 Email Notifications (Outbound)

Notifications are sent asynchronously via AWS SES using the `EmailService` provided by `cloud-sdk-aws`. Three template lists are merged at startup:
- `UserService.EMAIL_TEMPLATE_LIST` — user lifecycle emails
- `NetworkParticipantConstants.NETWORK_PARTICIPANT_NOTIFICATION_TEMPLATE_LIST` — participant events
- `ConnectionsEmailConstants.CARRIER_CONNECTIONS_EMAIL_TEMPLATE_LIST` — carrier connection events

Templates are resolved by name against SES at runtime.

### 14.4 Assumed Callers (Inbound)

Based on the path conventions and role requirements, the primary callers are:
- **Internal UI (Mercury Web Application)** — for participant management, subscription management, geography
- **Other Mercury microservices** (booking, visibility) — for subscription lookup, participant resolution, geography data
- **Admin tooling** — for network admin operations (NETWORK_ADMIN-gated endpoints)
- **Carrier portals** — for carrier service, connection management

### 14.5 Legacy Oracle Migration Pattern

The dual-database pattern (Aurora primary + Oracle INTTRA) reflects an in-progress migration:

```
Mercury Aurora DB (target)          Oracle INTTRA DB (source of truth, legacy)
      │                                        │
      ├── NetworkParticipantMapper             ├── InttraCompanyMapper
      ├── ConnectionsMapper                    ├── ConnectionInttraMapper
      ├── UserMapper                           ├── InttraUserMapper
      └── ...                                  └── ...

Migration services:
  CarrierConnectionRequestsMigrationService — migrates carrier connections
  ConnectionRulesMigrationService — migrates connection rules
```

`*MigrationMapper` classes (e.g., `ConnectionInttraMigrationMapper`) are dedicated read mappers against INTTRA that feed migration services writing to Aurora.

---

## Appendix: Module Dependency Graph

```
server (executable JAR)
  ├── models-interfaces
  ├── network-participant
  │     ├── commons
  │     ├── cloud-sdk-api / cloud-sdk-aws
  │     ├── xlog
  │     ├── geography
  │     ├── user
  │     ├── audit-trail
  │     └── models-interfaces
  ├── geography
  │     ├── commons
  │     ├── cloud-sdk-api / cloud-sdk-aws
  │     └── audit-trail
  ├── blacklist-email
  │     └── commons
  ├── subscriptions
  │     ├── commons
  │     ├── cloud-sdk-api / cloud-sdk-aws
  │     ├── models-interfaces
  │     └── network-participant
  ├── optionalvalidations
  │     └── commons
  ├── configuration-service
  │     └── commons
  ├── message-register
  │     └── commons
  ├── referencedata
  │     └── commons
  ├── ums
  │     └── commons
  ├── user
  │     └── commons
  ├── user-service
  │     └── commons
  ├── xlog
  │     └── commons
  ├── providers
  │     └── commons
  ├── audit-trail
  │     └── commons
  ├── external-service
  │     ├── commons
  │     ├── network-participant
  │     └── jaxws-rt:4.0.3
  ├── monitoring
  │     └── commons
  ├── commercial-entity
  │     └── commons
  └── alliance-partner
        └── commons
```

---

*Document generated from source code analysis of `c:\Users\arijit.kundu\projects\mercury-services\network` on 2026-05-04.*
