# Mercury Network Services — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `network/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture & Technology Stack](#2-architecture--technology-stack)
3. [Submodule Map](#3-submodule-map)
4. [Shared Concepts & Cross-Cutting Concerns](#4-shared-concepts--cross-cutting-concerns)
5. [Submodule: Alliance Partner](#5-submodule-alliance-partner)
6. [Submodule: Audit Trail](#6-submodule-audit-trail)
7. [Submodule: Blacklist Email](#7-submodule-blacklist-email)
8. [Submodule: Commercial Entity](#8-submodule-commercial-entity)
9. [Submodule: Configuration Service](#9-submodule-configuration-service)
10. [Submodule: External Service (EORI)](#10-submodule-external-service-eori)
11. [Submodule: Geography](#11-submodule-geography)
12. [Submodule: Message Register](#12-submodule-message-register)
13. [Submodule: Monitoring / Status](#13-submodule-monitoring--status)
14. [Submodule: Network Participant](#14-submodule-network-participant)
15. [Submodule: Optional Validations](#15-submodule-optional-validations)
16. [Submodule: Providers](#16-submodule-providers)
17. [Submodule: Reference Data](#17-submodule-reference-data)
18. [Submodule: Subscriptions](#18-submodule-subscriptions)
19. [Submodule: UMS (User Management System)](#19-submodule-ums-user-management-system)
20. [Submodule: User](#20-submodule-user)
21. [Submodule: XLog](#21-submodule-xlog)
22. [Dependency Graph](#22-dependency-graph)
23. [Role Reference](#23-role-reference)

---

## 1. Overview

**Mercury Network Services** is a DropWizard-based Java microservice that manages the network layer of the Mercury platform. It governs identities (companies, users), geography, relationships (connections, alliances), compliance (EORI, OFAC screening), subscriptions, audit trails, and transaction logging.

The service exposes a unified REST API and coordinates across four databases: MySQL Aurora (primary and read-replica), Oracle XLog, and Oracle INTTRA (legacy).

```
┌─────────────────────────────────────────────────────────────────┐
│                   Mercury Network Services                       │
│                  (DropWizard JAX-RS + Guice)                    │
│                                                                  │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │ Geography│  │  Network   │  │   User /   │  │ Commercial │  │
│  │ Reference│  │Participant │  │    UMS     │  │   Entity   │  │
│  └──────────┘  └────────────┘  └────────────┘  └────────────┘  │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │  XLog    │  │Subscriptions│ │   Audit    │  │   EORI     │  │
│  │ (Oracle) │  │ (DynamoDB) │  │   Trail    │  │  External  │  │
│  └──────────┘  └────────────┘  └────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │               │               │               │
    MySQL Aurora    Oracle XLog    Oracle INTTRA      DynamoDB
   (Primary+RO)    (Logging)      (Legacy Sync)   (NoSQL Store)
```

---

## 2. Architecture & Technology Stack

### 2.1 Framework & Runtime

| Component | Technology |
|-----------|------------|
| Web Framework | DropWizard (JAX-RS via Jakarta EE) |
| DI Framework | Google Guice |
| ORM / SQL | MyBatis (mapper interfaces + SQL annotations) |
| Validation | Jakarta Bean Validation + Hibernate Validator |
| JSON | Jackson 2.19.2 |
| Logging | Logback 1.5.18 + SLF4J |
| Build | Maven (Java 17 target) |
| Auth | JWT (auth0 4.3.0 + Bouncy Castle) |

### 2.2 Databases

| Database | Purpose | Access Pattern |
|----------|---------|----------------|
| MySQL Aurora (Primary) | All write operations — participants, connections, aliases, geography, audit trails | MyBatis @Mapper |
| MySQL Aurora (Read-Only) | Read-heavy queries for reference data and search | MyBatis @Mapper (dedicated mapper classes) |
| Oracle XLog | Transaction logging (XLog) | MyBatis @Mapper |
| Oracle INTTRA | Legacy system synchronization — company, connection, invoice data | MyBatis @Mapper |
| DynamoDB | Subscriptions, optional validations, blacklist emails, message register | AWS SDK DynamoDB client |

### 2.3 External Integrations

| Integration | Protocol | Purpose |
|-------------|----------|---------|
| EU EORI Validation Service | SOAP/WSDL | Validate economic operator registration numbers |
| AWS S3 | HTTPS presigned URL | Blacklist email message storage |
| AWS SQS | Poll listener | Bounced email processing |
| Restricted Party Screening (RPS) | Internal REST | OFAC / sanctions compliance screening |
| E2 Open / IDP Provider | REST | SSO user provisioning |

### 2.4 Main Application Bootstrap

**Entry Point:** `com.inttra.mercury.NetworkServices` (DropWizard `Application<>`)

On startup it:
1. Configures four database connections with their respective MyBatis mapper classes
2. Registers 22+ resource (JAX-RS endpoint) classes
3. Registers Guice modules per submodule
4. Registers admin tasks for master-data uploads (Country, Subdivision, Location)
5. Registers exception mappers and post-setup hooks

---

## 3. Submodule Map

```
network/
├── alliance-partner          # Partner relationship management
├── audit-trail               # Entity change tracking
├── blacklist-email           # Email suppression management
├── commercial-entity         # Legal entity & contract management
├── configuration-service     # UI configuration key-value store
├── external-service          # EU EORI number validation (SOAP)
├── geography                 # Location, country, subdivision reference data
├── message-register          # Idempotency / dedup register (DynamoDB)
├── models-interfaces         # Shared read-only service interfaces
├── monitoring                # Application status board
├── network-participant       # Core company/participant + connections
├── optionalvalidations       # Configurable validation rules (DynamoDB)
├── providers                 # External provider configuration (WaveBL, etc.)
├── referencedata             # Container types and master reference data
├── server                    # DropWizard bootstrap — no domain logic
├── subscriptions             # Module subscriptions + customizations (DynamoDB)
├── ums                       # User provisioning workflows
├── user                      # User account management
├── user-service              # Supplementary user services
└── xlog                      # Transaction logging (Oracle)
```

---

## 4. Shared Concepts & Cross-Cutting Concerns

### 4.1 Security Model

All protected endpoints use JAX-RS `@RolesAllowed`. The authenticated principal is injected as `InttraPrincipal`, which carries `userId`, `companyId`, and roles.

**Special rule:** Several admin operations check that `inttraPrincipal.getCompanyId() == 1000` (the INTTRA internal company ID) before proceeding.

### 4.2 Role Taxonomy

| Role Constant | Description |
|---------------|-------------|
| `NETWORK_ADMIN` | Full network administration |
| `SUPER_ADMIN` | Platform-level administration |
| `COMPANY_USER_ADMIN` | Company-scoped user administration |
| `COMMERCIAL_ENTITY_PARTNER_MGR` | Manage commercial entities and partners |
| `NETWORK_USER` | Read-only network access |
| `USER_MGMT_ADMIN` | User account management |
| `REGISTRATION_ADMIN` | New company/user registration |
| `SSO_ADMIN` | SSO user provisioning |
| `EBL_REG_UPDATES` | WaveBL / eBL registration updates |

### 4.3 Audit Trail Pattern

Every create, update, and delete operation in core submodules records an audit trail entry. The pattern is:

```
Service.create/update/delete()
  └─> auditTrailService.addAuditTrails(List<AuditTrail>)
        └─> AuditTrailDao.insertIntoAuditTrail(auditTrail)
```

Each `AuditTrail` captures: `entityType`, `entityId`, `before` state (JSON), `after` state (JSON), `actorId`, `timestamp`.

### 4.4 Request/Response Layers

```
HTTP Request
    │
    ▼
*Resource.java  ← JAX-RS, @RolesAllowed, @QueryParam, @PathParam, Bean Validation
    │
    ▼
*Service.java   ← Business rules, @Transactional, cross-module orchestration
    │
    ▼
*Dao.java       ← Delegates to MyBatis or DynamoDB
    │
    ▼
*Mapper.java    ← @Select / @Insert / @Update / @Delete SQL annotations (MyBatis)
```

### 4.5 Transactional Consistency

- `@Transactional` is applied at the service method level.
- Multi-step operations (e.g., create entity + insert audit trail) are wrapped in a single transaction.
- Cross-database operations (e.g., MySQL + Oracle INTTRA) are coordinated but not distributed-transactional — failures in secondary systems are logged, not rolled back.

### 4.6 Common Validation Patterns

| Jakarta Annotation | Use |
|-------------------|-----|
| `@NotNull` | Mandatory query/path params and model fields |
| `@NotEmpty` | Strings that must not be blank |
| `@Pattern(regexp)` | UUID or numeric ID validation |
| `@Valid` | Cascade bean validation on request bodies |

Business-level validations (uniqueness, active status, at-least-one-criteria) are performed in the service layer and raise `WebApplicationException` with descriptive messages.

---

## 5. Submodule: Alliance Partner

### 5.1 Purpose

Manages partnership relationships between network participants. Supports two relationship types: **Reseller** and **Intermediary**. Allows multiple network participants to be _associated_ under one alliance partner entry.

### 5.2 Domain Model

```
AlliancePartner
├── id                         (Long, generated UUID)
├── alliancePartnerName        (String)
├── alliancePartnerType        (Enum: RESELLER | INTERMEDIARY)
├── networkParticipant         (NetworkParticipant — the owning participant)
├── associatedNetworkParticipants (List<NetworkParticipant>)
├── createdOn / updatedOn      (OffsetDateTime)
└── createdBy / updatedBy      (String)

Partnership (read model)
├── partnerName
├── partnerCompanyId
├── partnerType
└── displayName
```

### 5.3 API Endpoints

**Base path:** `/alliance-partner`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/{id}` | — | Get alliance partner by ID |
| `GET` | `/search` | — | Search alliance partners |
| `GET` | `/partnerships` | — | Get all partnerships for a company |
| `POST` | `/` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Create new alliance partner |
| `PUT` | `/{alliancePartnerId}` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Edit alliance partner |
| `PUT` | `/{alliancePartnerId}/mapPartners` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Add associated participants |
| `DELETE` | `/{alliancePartnerId}/demapPartners/{networkParticipantId}` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Remove an associated participant |

#### Search Query Parameters (`GET /search`)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `partnerCompanyId` | Integer | No | Filter by partner company ID |
| `partnerCompanyName` | String | No | Filter by name |
| `country` | String | No | Filter by country |
| `city` | String | No | Filter by city |
| `associatedCompanyId` | Integer | No | Filter by associated company |
| `associatedCompanyName` | String | No | Filter by associated company name |

> At least one search criterion must be provided.

#### Partnerships Query Parameters (`GET /partnerships`)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `inttraCompanyId` | Integer | At least one | Filter by INTTRA company ID |
| `networkParticipantId` | Integer | At least one | Filter by network participant ID |

### 5.4 Business Rules

| # | Rule |
|---|------|
| BR-AP-1 | A `networkParticipant` is required when creating or editing an alliance partner. It must have a valid positive ID. |
| BR-AP-2 | The `alliancePartnerType` must be one of `RESELLER` or `INTERMEDIARY` (case-insensitive, normalized on save). |
| BR-AP-3 | The owning `networkParticipant` must exist in the system **and** be in `Active` status. |
| BR-AP-4 | No duplicate alliance partner may exist for the same `networkParticipant` + `alliancePartnerType` combination. |
| BR-AP-5 | Associated participants must each be unique within the same alliance partner entry. |
| BR-AP-6 | An associated participant cannot be the same as the owning `networkParticipant`. |
| BR-AP-7 | All associated participants must be in `Active` status. |
| BR-AP-8 | All create and edit operations record audit trails before and after the change. |

---

## 6. Submodule: Audit Trail

### 6.1 Purpose

Central entity-change log. Any submodule can record changes by injecting `AuditTrailService`. The trail supports paginated retrieval and understands entity type relationships (e.g., fetching the trail for a parent entity also fetches connected child entity types).

### 6.2 API Endpoints

**Base path:** `/audittrail`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Retrieve audit trails for an entity |

#### Query Parameters (`GET /`)

| Parameter | Type | Required | Validation | Description |
|-----------|------|----------|------------|-------------|
| `entityType` | String | Yes | Valid `EntityType` enum value | Type of the entity being queried |
| `entityId` | String | Yes | UUID or positive integer pattern | ID of the entity |
| `batchsize` | Integer | No | — | Page size |
| `offset` | Integer | No | — | Page offset |

**`entityId` pattern:** `^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[1-9][0-9]*)$`

### 6.3 Business Rules

| # | Rule |
|---|------|
| BR-AT-1 | When querying, the service resolves all _connected_ entity types for the given `entityType` and fetches audit trails for all of them in one response (`AuditTrails` with total count). |
| BR-AT-2 | Audit records are append-only — no update or delete operations exist on the audit trail store. |
| BR-AT-3 | Both UUID and positive-integer entity IDs are supported depending on which database table the entity lives in. |

---

## 7. Submodule: Blacklist Email

### 7.1 Purpose

Manages a suppression list of email addresses that must not receive platform emails. Processes AWS SQS bounce notifications automatically and supports manual management via REST.

### 7.2 Data Store

**DynamoDB** — primary data store (not MySQL). S3 used for storing raw bounce/complaint message payloads.

### 7.3 API Endpoints

**Base path:** `/blacklist-email`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/add` | — | Add or update a blacklisted email |
| `DELETE` | `/delete` | `NETWORK_ADMIN` | Remove an email from the blacklist |
| `POST` | `/validate` | — | Filter a list of emails, returning only non-blacklisted ones |
| `POST` | `/all` | `NETWORK_ADMIN` | Paginated scan of all blacklisted emails |
| `POST` | `/find` | — | Find a specific blacklisted email |

#### `/all` Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | Integer | Max results (hard cap: 200) |
| `startKey` | String | DynamoDB pagination continuation key |

### 7.4 SQS Listener

`BouncedEmailSQSListener` automatically processes bounce and complaint notifications from AWS SES via SQS. On receipt it calls `addOrUpdateToBlackListEmails()`.

### 7.5 Business Rules

| # | Rule |
|---|------|
| BR-BE-1 | All email addresses are stored and compared **case-insensitively** (normalized to lowercase). |
| BR-BE-2 | If an email already exists with type `"Manual"`, it **cannot** be updated via the API — it is permanently suppressed. |
| BR-BE-3 | Each blacklist record stores up to **5 message links** (S3 references). Older links are dropped when a 6th arrives. |
| BR-BE-4 | Message links are stored as S3 URIs (`s3://bucket/key` or `https://` format). On retrieval, presigned URLs are generated for secure access. |
| BR-BE-5 | The `/validate` endpoint returns the **subset of input emails that are NOT blacklisted** (i.e., safe to send to). |
| BR-BE-6 | `/all` scans are limited to 200 records per request to prevent full-table scan overload. |
| BR-BE-7 | The `subType` field tracks the origin of the blacklist entry (e.g., `"Bounce"`, `"Complaint"`, `"Manual"`). |

---

## 8. Submodule: Commercial Entity

### 8.1 Purpose

Manages **Commercial Entities** — legal organizations that may aggregate multiple network participants under a single commercial identity. Supports address, contact, and contract management, plus Excel export.

### 8.2 Domain Model

```
CommercialEntity
├── id                      (Long, generated)
├── companyLegalName        (String)
├── status                  (CommericalEntityStatusType)
├── addresses               (List<CommercialEntityAddress>)
│     ├── id, addressType   (CommercialEntityAddressType)
│     ├── address1..4, city, state, postalCode, country
│     └── primaryAddress    (Boolean)
├── contacts                (List<CommercialEntityContact>)
│     ├── id, contactType   (CommercialEntityContactType)
│     ├── contactName, phone, email
│     └── primaryContact    (Boolean)
├── networkParticipants     (List<NetworkParticipant> — mapped companies)
├── contracts               (List<CommercialEntityContract>)
│     ├── id, contractName, contractNumber
│     ├── startDate, endDate
│     └── status            (ContractStatusType)
└── audit fields            (createdOn, updatedOn, createdBy, updatedBy)
```

### 8.3 API Endpoints

**Base path:** `/commercial-entity`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/search` | — | Search commercial entities |
| `GET` | `/{commercialEntityId}` | — | Get by ID |
| `POST` | `/` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Create commercial entity |
| `PUT` | `/{commercialEntityId}` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Edit commercial entity |
| `PUT` | `/{commercialEntityId}/mapCompanies` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Map network participants |
| `PUT` | `/{commercialEntityId}/mapContracts` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Map contracts |
| `DELETE` | `/{commercialEntityId}/demapCompanies` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Unmap a network participant |
| `DELETE` | `/{commercialEntityId}/demapContracts` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Unmap a contract |
| `GET` | `/contract/search` | — | Search contracts by name or number |
| `GET` | `/contract/{contractId}` | — | Get contract by ID |
| `POST` | `/contract` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Create contract |
| `PUT` | `/contract` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Update contract |
| `PUT` | `/export` | `COMMERCIAL_ENTITY_PARTNER_MGR` | Export data to Excel |

#### Search Query Parameters (`GET /search`)

| Parameter | Type | Required |
|-----------|------|----------|
| `inttraCompanyId` | Integer | At least one |
| `companyLegalName` | String | At least one |
| `country` | String | At least one |
| `city` | String | At least one |

#### Unmap Query Parameters

| Parameter | Endpoint | Required |
|-----------|----------|----------|
| `networkParticipantId` | `demapCompanies` | Yes |
| `contractId` | `demapContracts` | Yes |

### 8.4 Business Rules

| # | Rule |
|---|------|
| BR-CE-1 | `commercialEntityId` in the URL path must be > 0. |
| BR-CE-2 | On edit, the ID in the URL path must match the ID in the request payload. |
| BR-CE-3 | Search requires at least one non-null filter criterion. |
| BR-CE-4 | At least one network participant must be provided when mapping companies. |
| BR-CE-5 | Duplicate network participant mappings to the same commercial entity are rejected. |
| BR-CE-6 | Only **Active** network participants can be mapped. |
| BR-CE-7 | Contract `contractNumber` must be unique (case-insensitive) across all contracts on **create**. |
| BR-CE-8 | On **update**, contract number uniqueness is checked excluding the contract being updated. |
| BR-CE-9 | When editing, the address and contact `id` values in the payload must already belong to the commercial entity. |
| BR-CE-10 | Addresses/contacts not present in an edit payload are **deleted**; new ones without IDs are **inserted**; existing ones are **updated**. |
| BR-CE-11 | All create/edit/map/unmap operations produce audit trail entries. |

### 8.5 Validation Rules (`ValidationUtil`)

| Field | Constraint |
|-------|-----------|
| Address line 1–4 | Max length enforced |
| City, State | Max length enforced |
| Postal code | Format validated |
| Phone number | Format validated |
| Email | Format validated |
| Contact name | Max length enforced |

---

## 9. Submodule: Configuration Service

### 9.1 Purpose

A key-value store for UI configuration settings. Values are stored in Aurora MySQL and surfaced through specific named endpoints for common configs (chatbot, RUM, carrier connections).

### 9.2 API Endpoints

**Base path:** `/ui-configuration`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/` | — | Get all configs, or a named config |
| `GET` | `/chatbot-config` | — | Get chatbot configuration |
| `GET` | `/carrierconnections-v2-config` | — | Get carrier connections v2 config |
| `GET` | `/rum-config` | — | Get RUM (Real User Monitoring) config |
| `PUT` | `/update/ui-config` | `SUPER_ADMIN` | Update a configuration value |

#### Query Parameters (`GET /`)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | String | No | If provided, returns only the named config |

#### Update Request Body (`PUT /update/ui-config`)

```json
{
  "name": "feature-flag-x",
  "value": "true"
}
```

### 9.3 Business Rules

| # | Rule |
|---|------|
| BR-CS-1 | Only `SUPER_ADMIN` can update configuration values. |
| BR-CS-2 | Updates are rejected with `404 Not Found` if the named configuration does not already exist (no upsert — only update). |
| BR-CS-3 | The `name` and `value` fields in the update request are required (not null/empty). |

---

## 10. Submodule: External Service (EORI)

### 10.1 Purpose

Validates EU **Economic Operators Registration and Identification (EORI)** numbers against the EU Customs authority via SOAP. Results are cached in the database to minimize external calls.

### 10.2 Configuration (`ExternalServiceConfiguration`)

| Property | Description |
|----------|-------------|
| `eoriUrl` | WSDL URL for the EU EORI SOAP service |
| `eoriCacheExpirationMinutes` | How long cached EORI results remain valid (default: 1440 = 24 hours) |
| `connectTimeoutMs` | SOAP client connection timeout |
| `requestTimeoutMs` | SOAP client request timeout |

### 10.3 API Endpoints

**Base path:** `/externalservice/eori`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/validate` | — | Validate a set of EORI numbers |

#### Request Body

```json
{
  "eoriNumbers": ["GB123456789000", "DE987654321000", ...]
}
```

Maximum: **95 EORI numbers per request**.

#### Response

```json
[
  {
    "eoriNumber": "GB123456789000",
    "valid": true,
    "details": { ... }
  },
  ...
]
```

Returns a `Set<EORIDetails>` (deduplication of input).

### 10.4 Business Rules & Processing Flow

```
POST /validate
  │
  ├─ 1. Input: up to 95 EORI numbers (deduplicated to Set)
  │
  ├─ 2. Cache lookup: query DB for previously validated results
  │       └─ If found and not expired → use cached result
  │
  ├─ 3. For uncached EORIs:
  │       └─ Batch into groups of 8
  │           └─ Send each batch via SOAP to EU service
  │               └─ On SOAP fault → retry each EORI individually
  │
  ├─ 4. Persist all results to DB
  │       └─ Set expiration = now + eoriCacheExpirationMinutes
  │
  └─ 5. Return combined Set<EORIDetails>
```

| # | Rule |
|---|------|
| BR-EO-1 | Maximum **95 EORI numbers** per API call. |
| BR-EO-2 | EORI numbers are **deduplicated** (stored as `Set`) before processing. |
| BR-EO-3 | Valid results are cached for `eoriCacheExpirationMinutes` (default 24 hours). |
| BR-EO-4 | Batch size to the SOAP service is **8 EORIs per call**. |
| BR-EO-5 | If a batch SOAP call results in a fault, each EORI in the batch is retried **individually**. |
| BR-EO-6 | EORI results marked as unavailable include an error message truncated to **512 characters**. |

---

## 11. Submodule: Geography

### 11.1 Purpose

Manages geographic reference data: locations (ports, cities), countries, subdivisions, custom locations, carrier services, and location aliases. Combines standard INTTRA locations with company-specific custom locations in search.

### 11.2 API Endpoints

#### Locations — `/reference/geography`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{code}` | Get location by UN/LOCODE |
| `GET` | `/codes` | Get multiple locations by code list |
| `GET` | `/search` | Search locations |
| `GET` | `/cns` | Get by country + subdivision |
| `GET` | `/search/{id}` | Get by geography internal ID |

**Search Query Parameters (`GET /search`)**

| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | String | Free-text search on location name |
| `seaportsOnly` | Boolean | Restrict to seaports |
| `continent` | String | Filter by continent |
| `carrierId` | Integer | Filter by carrier (limits to carrier's ports) |
| `bookerId` | Integer | Include booker's custom locations in results |

**By Code Query Parameters (`GET /{code}`)**

| Parameter | Type | Description |
|-----------|------|-------------|
| `effectiveDate` | String (`yyyy-MM-dd`) | Date for historical lookup |

#### Countries — `/reference/country`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/` | — | Search countries by multiple filters |
| `GET` | `/search` | — | Free-text search on country name |
| `GET` | `/{id}` | — | Get country by ID |
| `POST` | `/` | `NETWORK_ADMIN` | Add new country |
| `PUT` | `/{id}` | `NETWORK_ADMIN` | Update country |
| `DELETE` | `/{id}` | `NETWORK_ADMIN` | Delete country |

**Country Search Query Parameters**

| Parameter | Description |
|-----------|-------------|
| `standardName` | Official country name |
| `isoAlpha2` | 2-letter ISO code |
| `isoAlpha3` | 3-letter ISO code |
| `isoNumeric` | Numeric ISO code |
| `status` | Active / Inactive filter |

#### Location Aliases — `/reference/alias`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{participantId}/aliases` | Get aliases for participant |
| `POST` | `/` | Create alias |
| `PUT` | `/aliases/{id}` | Update alias |
| `DELETE` | `/aliases/{id}` | Delete alias |

#### Subdivisions — `/reference/subdivision`

CRUD for country subdivisions (states, provinces, regions).

#### Carrier Services — `/reference/carrier-service`

CRUD for carrier service definitions.

#### Custom Locations — `/reference/customlocation`, `/reference/partnercustomlocation`

Company-specific location overrides.

### 11.3 Business Rules

| # | Rule |
|---|------|
| BR-GEO-1 | Location search combines standard INTTRA locations with company custom locations when `bookerId` is provided. |
| BR-GEO-2 | Currency code and region for a country are resolved per provider; if a provider-specific value is absent, the INTTRA default is used as fallback. |
| BR-GEO-3 | Country names are UTF-8 normalized (diacritical marks stripped) for sorting purposes. |
| BR-GEO-4 | Alias types distinguish between INTTRA-owned and company-owned aliases via `OwnerEntityType`. |

---

## 12. Submodule: Message Register

### 12.1 Purpose

A **DynamoDB-backed idempotency / deduplication register**. External services write a key before processing a message and update it when done. This prevents duplicate message processing in at-least-once delivery scenarios.

### 12.2 State Machine

```
                  ┌─────────────────────┐
       create     │      PROCESSING     │  TTL = configurable
  ──────────────► │   (in progress)     │
                  └─────────┬───────────┘
                            │  update (success)
                            ▼
                  ┌─────────────────────┐
                  │  PROCESSING_COMPLETE │  TTL = 1 day
                  │   (done, keep 1d)   │
                  └─────────────────────┘

  DONE  = legacy state for backwards compatibility
```

### 12.3 API Endpoints

**Base path:** `/utility/message-register`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/` | — | Register a new message key |
| `PUT` | `/` | — | Mark a message as processed |
| `DELETE` | `/` | `NETWORK_ADMIN` | Delete a specific register entry |
| `DELETE` | `/delete/all` | `NETWORK_ADMIN` | Delete all register entries |

#### Query Parameters (`DELETE /`)

| Parameter | Type | Required |
|-----------|------|----------|
| `key` | String | Yes |

### 12.4 Business Rules

| # | Rule |
|---|------|
| BR-MR-1 | **Create (`POST /`)** returns `CREATED` if the key does not exist → a new `PROCESSING` entry is created. |
| BR-MR-2 | **Create** returns `RETRY` if the key exists in `PROCESSING` state **and** has not expired → caller should retry later. |
| BR-MR-3 | **Create** returns `CREATED` (replaces entry) if the key exists in `PROCESSING` state **but** has expired (stale in-flight message). |
| BR-MR-4 | **Create** returns `DUPLICATE` if the key exists in `PROCESSING_COMPLETE` or `DONE` state → message was already processed. |
| BR-MR-5 | **Update (`PUT /`)** transitions `PROCESSING` → `PROCESSING_COMPLETE` and sets a **1-day TTL** on the completed entry. |
| BR-MR-6 | **Update** returns `INCONSISTENT` if the state is not `PROCESSING` at update time. |
| BR-MR-7 | **Update** returns `DUPLICATE` if the entry is already `PROCESSING_COMPLETE` or `DONE`. |

---

## 13. Submodule: Monitoring / Status

### 13.1 Purpose

A simple status board for platform applications. Admins post application-level status updates that are displayed to users in the UI (e.g., planned maintenance, degraded performance).

### 13.2 API Endpoints

**Base path:** `/monitoring/status`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/current` | — | Get all currently **active** statuses |
| `GET` | `/` | `NETWORK_USER` | Filtered status search |
| `GET` | `/{id}` | `NETWORK_USER` | Get status by ID |
| `POST` | `/` | `SUPER_ADMIN` | Add new application status |
| `PUT` | `/{id}` | `SUPER_ADMIN` | Update existing status |
| `DELETE` | `/{id}` | `SUPER_ADMIN` | Delete status |

#### Search Query Parameters (`GET /`)

| Parameter | Type | Description |
|-----------|------|-------------|
| `applicationName` | String | Filter by application name |
| `status` | String | Filter by status value |
| `active` | Boolean | Show only active entries |
| `display` | Boolean | Show only display-flagged entries |

### 13.3 Business Rules

| # | Rule |
|---|------|
| BR-MON-1 | Only users from the **INTTRA internal company** (`companyId == 1000`) can perform admin operations (`POST`, `PUT`, `DELETE`). |
| BR-MON-2 | Application name must be unique (case-insensitive). On update, uniqueness excludes the record being updated. |
| BR-MON-3 | Application name and status value cannot be blank. Leading/trailing whitespace is trimmed. |
| BR-MON-4 | `PUT` performs a **partial update** — only provided fields are modified; missing fields are left unchanged. |
| BR-MON-5 | `GET /current` returns only entries with `active = true`. |

---

## 14. Submodule: Network Participant

### 14.1 Purpose

Core module. Manages **network participants** (companies registered on the platform) and their **connections** (relationships between participants, typically carrier–customer). Also manages participant aliases, GLV (Global Legal Vehicle) entities, entitlements, attributes, and compliance screening.

### 14.2 Domain Model

```
NetworkParticipant
├── id                         (Integer)
├── inttraCompanyId            (Integer — legacy identifier)
├── globalId                   (String — UUID-like)
├── companyName                (String)
├── status                     (Active | Inactive | Suspended)
├── carrierId                  (Integer, optional)
├── scacCode                   (String — SCAC for carriers)
├── networkFunctionCode        (String)
├── addresses                  (List)
├── parentNetworkParticipant   (NetworkParticipant, optional)
└── children                   (List<NetworkParticipant>)

Connection
├── managingParticipant        (NetworkParticipant)
├── participant                (NetworkParticipant)
├── parentParticipant          (NetworkParticipant, optional)
└── alias                      (String)

ConnectionDetails
├── sourceNetworkParticipantId
├── targetNetworkParticipantId
├── module                     (String)
├── type                       (ConnectionType: CUSTOMER | CARRIER)
├── active                     (Boolean)
├── lastModifiedDate
└── lastModifiedBy
```

### 14.3 API Endpoints

#### Network Participants — `/reference/participants`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/` | — | Search by multiple filters |
| `GET` | `/search` | — | Advanced search with pagination + sort |
| `GET` | `/{id}` | — | Get by ID |
| `POST` | `/` | — | Add new participant |
| `PUT` | `/{id}` | — | Update participant |
| `DELETE` | `/{id}` | `NETWORK_ADMIN` | Delete participant |
| `GET` | `/branches` | — | Get tree branches for current user |
| `GET` | `/all` | — | Get all related participants |
| `GET` | `/children` | — | Get child participants |
| `PUT` | `/export` | — | Export participant data to Excel |
| `GET/PUT/DELETE` | `/entitlements/*` | — | Manage module entitlements |
| `GET/POST/PUT/DELETE` | `/glv/*` | — | GLV participant management |
| `GET/POST/PUT/DELETE` | `/networkfunction/*` | — | Network function management |
| `GET/POST/PUT/DELETE` | `/attributes/*` | — | Participant attribute management |
| `GET` | `/reward/{inttraCompanyId}` | — | Get rewards for company |

**Search Query Parameters**

| Parameter | Description |
|-----------|-------------|
| `globalId` | Filter by global UUID |
| `name` | Filter by company name |
| `inttraCompanyId` | Filter by INTTRA company ID |
| `carrierId` | Filter by carrier ID |
| `scacCode` | Filter by SCAC code |
| `networkFunctionCode` | Filter by network function |

**Export** streams an Excel file (`.xlsx`) with batching: 40 iterations × 500 records = up to 20,000 records.

#### Company — `/company`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/generateinttracompanyId` | `NETWORK_ADMIN`, `REGISTRATION_ADMIN` | Generate next company ID |
| `POST` | `/create` | `NETWORK_ADMIN`, `REGISTRATION_ADMIN` | Create company |
| `POST` | `/nameandaddress` | — | Update name and address |
| `POST` | `/notify/nameandaddress` | — | Notify name/address changes |
| `POST` | `/{networkparticipantid}/{status}` | `NETWORK_ADMIN` | Update company status |
| `PUT` | `/{networkparticipantid}/companyidentifier` | — | Create/update identifiers |
| `GET` | `/parent/{networkParticipantId}` | — | Get parent company |
| `PUT` | `/parent/{networkParticipantId}` | `NETWORK_ADMIN` | Set parent company |
| `DELETE` | `/parent/{networkParticipantId}` | `NETWORK_ADMIN` | Remove parent company |
| `POST` | `/contact/{networkParticipantId}` | — | Update contact |

#### Connections — `/connections`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/connections` | — | Search connections |
| `GET` | `/connections/verify` | — | Verify connection between two participants |
| `POST` | `/connections/link` | `NETWORK_ADMIN` | Create (link) a connection |
| `POST` | `/connections/unlink` | — | Remove (unlink) a connection |
| `POST` | `/connections/bulkapprove` | — | Bulk approve pending connections |
| `POST` | `/connections/bulkdecline` | — | Bulk decline pending connections |
| `POST` | `/connections/manage` | — | Manage a single connection |
| `GET` | `/connections/audittrail` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Get connection audit trail |

**Connection Search Query Parameters**

| Parameter | Description |
|-----------|-------------|
| `type` | `ConnectionType` (CUSTOMER / CARRIER) |
| `module` | Module name filter |
| `name` | Company name search |

#### Connection Rules — `/connectionrules`

| Method | Path | Description |
|--------|------|-------------|
| `GET/POST` | `/excludedcountries/{networkParticipantId}` | Manage excluded countries |
| `GET/POST` | `/customfields/{networkParticipantId}` | Manage custom connection fields |
| `GET/PUT` | `/loa/{networkParticipantId}` | Letter of Authority management |
| `GET/PUT` | `/rulesstatus/{networkParticipantId}` | Connection rules status |
| `GET/POST/PUT/DELETE` | `/rule/{networkParticipantId}` | CRUD for connection rules |
| `POST` | `/migrate` | Migrate connection rules |

#### Participant Aliases — `/participants`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{participantId}/aliases` | Get aliases for participant |
| `GET` | `/aliases/{alias}` | Search by alias value |
| `POST` | `/` | Create new alias |
| `PUT` | `/aliases/{id}` | Update alias |
| `DELETE` | `/aliases/{id}` | Delete alias |

#### Compliance Screening — `/participant/compliance`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/` | Execute OFAC / RPS compliance screening |

### 14.4 Business Rules

**Network Participants**

| # | Rule |
|---|------|
| BR-NP-1 | Only `Active` participants can be mapped as connections, associated participants, or contract mappings elsewhere in the system. |
| BR-NP-2 | A participant's status can be updated by `NETWORK_ADMIN` only. |
| BR-NP-3 | Excel export is batched: max 40 iterations × 500 records per batch. |

**Connections**

| # | Rule |
|---|------|
| BR-CON-1 | User must be a `NETWORK_ADMIN` **or** a carrier with the appropriate network function to manage connections. |
| BR-CON-2 | Bulk approval creates network connections, then creates legacy INTTRA connection requests, then approves them — in that order. |
| BR-CON-3 | Bulk decline requires valid `declineReasonIds` to be provided. |
| BR-CON-4 | Duplicate connection detection runs before any link/approve operation to prevent double-mapping. |
| BR-CON-5 | Shared alias rules are validated when managing connection aliases. |
| BR-CON-6 | Connections are synchronized to the **Oracle INTTRA** legacy database after every create/approve/decline operation. |

**Compliance Screening**

| # | Rule |
|---|------|
| BR-COMP-1 | OFAC compliance is checked via the Restricted Party Screening (RPS) service using `Action.FULL_UPDATE`. |
| BR-COMP-2 | Input includes company name, address, and contact information; output is an RPS status or error. |

---

## 15. Submodule: Optional Validations

### 15.1 Purpose

A **DynamoDB-backed configurable rule store**. Modules can define optional validation rules per company (identified by `moduleType` + `inttraCompanyId`). Rules can be toggled active/inactive without deletion.

### 15.2 API Endpoints

**Base path:** `/optionalvalidations`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `PUT` | `/` | `NETWORK_ADMIN` | Create or update a rule |
| `GET` | `/{moduleType}/{inttraCompanyId}` | — | Get all rules for a company |
| `GET` | `/{moduleType}/{inttraCompanyId}/list` | — | List rule names only |
| `GET` | `/{hashKey}` | — | Get rule by hash key |
| `DELETE` | `/{hashKey}` | `NETWORK_ADMIN` | Delete a rule |
| `GET` | `/updateStatus/{hashKey}/{activeFlag}` | — | Toggle rule active/inactive |
| `GET` | `/definitions` | — | Get available validation rule definitions |

### 15.3 Business Rules

| # | Rule |
|---|------|
| BR-OV-1 | Rules are identified by a `hashKey` (DynamoDB partition key). |
| BR-OV-2 | The `validationType` must be a valid `ValidationType` enum value. |
| BR-OV-3 | Create/update operations record audit trails. |
| BR-OV-4 | The `activeFlag` on `updateStatus` is a path parameter (`true` / `false`). |
| BR-OV-5 | Delete verifies existence before proceeding. |

---

## 16. Submodule: Providers

### 16.1 Purpose

Manages external service provider configurations (e.g., WaveBL for eBL — Electronic Bill of Lading). Configurations are stored per network participant and grouped by attribute type.

### 16.2 API Endpoints

#### Provider Configuration — `/provider/configuration`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Get all provider configurations for a provider type |

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `providertype` | ProviderType enum | Yes | The provider type to query |

Configuration attributes are grouped by type: `TEXT`, `BOOLEAN`, `NETWORK_PARTICIPANT`.

#### WaveBL — `/provider/ebl/wavebl`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/integratedWaveBusinessUnit` | `EBL_REG_UPDATES` | Process WaveBL integration response |
| `GET` | `/configuration` | — | Get WaveBL configs for a customer |

**Configuration Query Parameters**

| Parameter | Type | Validation |
|-----------|------|-----------|
| `customerNetworkParticipantId` | Integer | Must be > 0 |

### 16.3 Business Rules

| # | Rule |
|---|------|
| BR-PROV-1 | Provider configurations are grouped by `networkParticipantId` — one group per participant. |
| BR-PROV-2 | `NETWORK_PARTICIPANT` type attributes are resolved to full participant objects (sorted by company name). |
| BR-PROV-3 | `EBL_REG_UPDATES` role is required to push WaveBL integration responses. |
| BR-PROV-4 | `customerNetworkParticipantId` must be a positive integer for WaveBL config retrieval. |

---

## 17. Submodule: Reference Data

### 17.1 Purpose

Manages master reference data, primarily container types. Also includes carrier/booking party reference data.

### 17.2 API Endpoints

#### Container Types — `/containertype`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/all` | Get predefined container types (deprecated — static list) |
| `GET` | `/` | Query container types by filter |

**Container Type Query Parameters**

| Parameter | Description |
|-----------|-------------|
| `typeCode` | Container ISO type code |
| `groupCode` | Container group code |
| `typeCategory` | Category filter |
| `description` | Description search |
| `displayFlag` | Show/hide flag filter |

---

## 18. Submodule: Subscriptions

### 18.1 Purpose

Manages **module subscriptions** — company-level opt-ins to specific platform modules (e.g., booking, visibility). Each subscription can have customization settings and action configurations (e.g., Watermill actions, Aperak codes). Backed by **DynamoDB**.

### 18.2 Domain Model

```
Subscription
├── hashKey                    (String — DynamoDB partition key)
├── moduleType                 (String — module identifier)
├── inttraCompanyId            (Integer)
├── ediId                      (String — EDI identifier)
├── ftpId                      (String — FTP identifier)
├── active                     (Boolean)
├── customizations             (Map<String, Object>)
├── actions                    (List<SubscriptionAction>)
│     ├── type                 (Watermill | Aperak)
│     ├── parameters           (Map)
│     └── active               (Boolean)
└── audit fields
```

### 18.3 API Endpoints

**Base path:** `/subscription`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `PUT` | `/` | — | Create or update subscription |
| `POST` | `/updateStatus/{hashKey}/{activeFlag}` | — | Toggle active/inactive |
| `GET` | `/{moduleType}` | — | Get all subscriptions for a module |
| `GET` | `/{moduleType}/{inttraCompanyId}` | — | Get company subscriptions |
| `GET` | `/{moduleType}/ediid/{ediId}` | — | Get by EDI ID |
| `GET` | `/{moduleType}/ftpid/{ftpId}` | — | Get by FTP ID |
| `GET` | `/subscription/{hashKey}` | — | Get subscription by hash key |
| `DELETE` | `/{hashKey}` | `SUPER_ADMIN` | Delete subscription |
| `GET` | `/search` | — | Advanced search with pagination |
| `GET` | `/export` | — | Export to Excel (`.xlsx`) |
| `GET` | `/subscriptioncustomizationconfigs` | — | Get customization config definitions |
| `GET` | `/{moduleType}/groupedpreferences` | — | Get grouped preference definitions |
| `GET` | `/{moduleType}/preferences` | — | Get preference definitions |

#### Search Query Parameters (`GET /search`)

| Parameter | Description |
|-----------|-------------|
| `moduleType` | Module filter |
| `inttraCompanyId` | Company filter |
| `companyName` | Company name search |
| `active` | Active status filter |
| Pagination | `limit`, `offset` / DynamoDB continuation key |

### 18.4 Business Rules

| # | Rule |
|---|------|
| BR-SUB-1 | DynamoDB batch operations are limited to **49 items per batch** (DynamoDB limit is 100, but 49 is used for safety). |
| BR-SUB-2 | Excel export is batched at **250 records per batch**. |
| BR-SUB-3 | Watermill actions are validated: type, parameters, and active flag must all be valid. |
| BR-SUB-4 | Aperak action codes are validated against the allowable code list. |
| BR-SUB-5 | Customization values are validated against the `subscriptioncustomizationconfigs` definitions before save. |
| BR-SUB-6 | Create/update/delete operations produce audit trail entries. |
| BR-SUB-7 | Sub-module entitlement configuration is synchronized on subscription create/update. |
| BR-SUB-8 | Subscriptions can be searched via company hierarchy — parent companies can include child company subscriptions. |

---

## 19. Submodule: UMS (User Management System)

### 19.1 Purpose

**User provisioning workflows.** UMS is the structured process for adding/updating user access to platform applications. It abstracts workflow definitions (questions, attributes, options) and applies them to create/modify users.

### 19.2 API Endpoints

**Base path:** `/ums`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/workflows` | — | Get available user workflows |
| `GET` | `/workflows/{workflowId}/attributes/{attributeId}/options` | `NETWORK_ADMIN` | Get options for a workflow attribute |
| `POST` | `/validateSelection` | — | Validate user selections |
| `GET` | `/users/` | — | Get all managed users |
| `GET` | `/users/{userId}` | — | Get user current selections |
| `POST` | `/users/{userId}` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Create or update user profile |
| `PUT` | `/users/{userId}/selections` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Add new selections |
| `PATCH` | `/users/{userId}/selections` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN`, `USER_MGMT_ADMIN` | Modify existing selections |
| `DELETE` | `/users/{userId}/selections` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Remove user from an application |

**Options Query Parameters**

| Parameter | Description |
|-----------|-------------|
| `searchText` | Filter options by text |
| `locale` | Language/locale for option labels |
| `limit` | Max options returned |
| `offset` | Pagination offset |

### 19.3 Business Rules

| # | Rule |
|---|------|
| BR-UMS-1 | Default roles `NETWORK_USER` and `OCEANSCHEDULE_USER` are assigned to all new UMS-provisioned users. |
| BR-UMS-2 | Primary vs. secondary company assignments are tracked separately per user. |
| BR-UMS-3 | UMS supports two IDP providers: **E2OPEN** and **E2Open** (legacy naming). |
| BR-UMS-4 | OFAC compliance check is performed during `addUser` — provisioning is blocked if screening fails. |
| BR-UMS-5 | Network roles and legacy roles are managed separately and merged at display time. |
| BR-UMS-6 | GLV (Global Legal Vehicle) participant listing is available for admin selection workflows. |
| BR-UMS-7 | Admin selections are encoded/decoded for transport. |
| BR-UMS-8 | `PATCH /selections` performs a **merge** (modify existing); `PUT /selections` performs an **add** (append new). |

---

## 20. Submodule: User

### 20.1 Purpose

Manages user accounts across Mercury and the legacy INTTRA system. Handles registration, SSO, cookie consent, and PayCargo legal agreements.

### 20.2 API Endpoints

**Base path:** `/user`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/usercompany` | — | Get company ID for a login name |
| `GET` | `/registration/validate-email/{emailaddress}` | — | Check email availability |
| `POST` | `/create` | `USER_MGMT_ADMIN`, `REGISTRATION_ADMIN` | Create new user |
| `POST` | `/sso/create` | `SSO_ADMIN` | Create SSO user |
| `GET` | `/{userId}` | — | Get user details |
| `POST` | `/linkeduser` | `SSO_ADMIN` | Add or update linked user |
| `DELETE` | `/linkeduser` | `SSO_ADMIN` | Delete linked user |
| `GET` | `/linkeduser` | — | Get linked user by ID |
| `PUT` | `/paycargolegal/{status}` | — | Update PayCargo legal agreement status |
| `POST` | `/cookieconsent/{userId}` | — | Save cookie consent preferences |
| `GET` | `/cookieconsent/{userId}` | — | Get cookie consent preferences |

### 20.3 Business Rules

| # | Rule |
|---|------|
| BR-USR-1 | Email addresses are validated for format and checked against domain whitelisting rules. |
| BR-USR-2 | OFAC compliance (`UserComplianceService`) is checked during `createUser`. User creation is blocked if screening fails. |
| BR-USR-3 | User accounts are synchronized to the **Oracle INTTRA** legacy system on create/update. |
| BR-USR-4 | If the **E2 Proxy** flag is enabled for a company, it is enforced when creating users for that company. |
| BR-USR-5 | Multiple companies can be linked to one user via `linkeduser` — managed by `SSO_ADMIN` only. |
| BR-USR-6 | Cookie consent preferences are stored per `userId` and keyed by consent category. |

---

## 21. Submodule: XLog

### 21.1 Purpose

Records detailed **transaction logs** in an Oracle database. Used for EDI/messaging traceability — tracks the full lifecycle of a transaction with revisions, entities, events, and attributes.

### 21.2 Domain Model

```
XlogDetail
├── transaction
│     ├── transactionId        (BigDecimal)
│     └── ...
├── revision
│     ├── revisionId           (BigDecimal)
│     └── ...
├── xlog
│     ├── id                   (BigDecimal — sequence generated)
│     ├── overallId            (BigDecimal)
│     ├── parentId             (BigDecimal)
│     ├── statusId             (BigDecimal)
│     ├── typeId               (BigDecimal)
│     ├── actorId              (BigDecimal)
│     ├── customerCompanyId    (BigDecimal)
│     ├── customerCompanyName  (String)
│     ├── carrierCompanyId     (BigDecimal)
│     ├── carrierCompanyName   (String)
│     ├── interfaceId          (BigDecimal)
│     ├── serviceId            (BigDecimal)
│     ├── formatId             (BigDecimal)
│     ├── channelId            (BigDecimal)
│     ├── logDate              (Date)
│     └── interfaceDate        (Date)
├── entities                   (List<XlogEntity>)
├── events                     (List<XlogEvent>)
│     └── eventDetails, eventAttributes, eventArchive
└── attributes                 (List<XlogAttribute>)
```

All IDs are `BigDecimal` (Oracle NUMBER compatibility).

### 21.3 API Endpoints

**Base path:** `/xlog`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/{xlogid}` | Get complete XLog detail |
| `POST` | `/create` | Create new XLog entry |
| `POST` | `/update` | Update existing XLog entry |

### 21.4 Business Rules

| # | Rule |
|---|------|
| BR-XLOG-1 | IDs for transactions, revisions, and xlogs are generated from **Oracle database sequences**. |
| BR-XLOG-2 | `create` and `update` are `@Transactional` — all inserts (xlog, entities, events, attributes) succeed or all roll back. |
| BR-XLOG-3 | `@NotNull` annotated fields are validated via reflection before persistence — missing required fields cause a `400 Bad Request`. |
| BR-XLOG-4 | `@Size` annotated fields are **silently truncated** to the max length (not rejected) before persistence. |
| BR-XLOG-5 | Nested structures (event details, event attributes, event archive) are each persisted independently within the same transaction. |

---

## 22. Dependency Graph

```
server
  ├── network-participant   ← geography, xlog, user, audit-trail
  ├── geography             ← (standalone)
  ├── subscriptions         ← models-interfaces, network-participant
  ├── user                  ← models-interfaces, audit-trail
  ├── ums                   ← user, network-participant
  ├── xlog                  ← (standalone, Oracle)
  ├── providers             ← network-participant
  ├── referencedata         ← (standalone)
  ├── optionalvalidations   ← (standalone, DynamoDB)
  ├── external-service      ← (standalone, SOAP)
  ├── commercial-entity     ← (standalone)
  ├── alliance-partner      ← network-participant
  ├── audit-trail           ← (standalone)
  ├── blacklist-email       ← models-interfaces
  ├── configuration-service ← (standalone)
  ├── monitoring            ← (standalone)
  ├── message-register      ← (standalone, DynamoDB)
  └── models-interfaces     ← (interface definitions only)
```

**`models-interfaces`** defines read-only service interfaces (`BlacklistEmailReadOnlyService`, `ConfigurationReadOnlyService`, `SubscriptionReadOnlyService`, `UserReadOnlyService`) that break circular dependencies between submodules.

---

## 23. Role Reference

| Endpoint Pattern | Roles Required |
|-----------------|----------------|
| Audit trail retrieval | `NETWORK_ADMIN` OR `COMPANY_USER_ADMIN` |
| Blacklist email delete/list | `NETWORK_ADMIN` |
| Commercial entity management | `COMMERCIAL_ENTITY_PARTNER_MGR` |
| UI configuration update | `SUPER_ADMIN` |
| Geography admin (add/update country) | `NETWORK_ADMIN` |
| Message register delete | `NETWORK_ADMIN` |
| Monitoring admin (add/update/delete status) | `SUPER_ADMIN` + INTTRA company (ID=1000) |
| Network participant delete | `NETWORK_ADMIN` |
| Company status update / parent management | `NETWORK_ADMIN` |
| Company generate ID / create | `NETWORK_ADMIN` OR `REGISTRATION_ADMIN` |
| Connection link | `NETWORK_ADMIN` |
| Connection audit trail | `NETWORK_ADMIN` OR `COMPANY_USER_ADMIN` |
| Optional validation CRUD | `NETWORK_ADMIN` |
| WaveBL integration push | `EBL_REG_UPDATES` |
| Subscription delete | `SUPER_ADMIN` |
| UMS user provisioning | `NETWORK_ADMIN` OR `COMPANY_USER_ADMIN` |
| UMS selection modify | `NETWORK_ADMIN` OR `COMPANY_USER_ADMIN` OR `USER_MGMT_ADMIN` |
| User create | `USER_MGMT_ADMIN` OR `REGISTRATION_ADMIN` |
| User SSO operations | `SSO_ADMIN` |
| Participant alias list all | `NETWORK_ADMIN` OR `COMPANY_USER_ADMIN` |
| Alliance partner management | `COMMERCIAL_ENTITY_PARTNER_MGR` |

---

*End of document — Mercury Network Services Business Rules & Technical Reference*
