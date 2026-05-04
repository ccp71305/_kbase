# Ocean Schedules Service — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `oceanschedules/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture](#3-architecture)
4. [API Endpoints](#4-api-endpoints)
5. [Business Rules](#5-business-rules)
6. [Service Layer](#6-service-layer)
7. [Data Models](#7-data-models)
8. [External Integrations](#8-external-integrations)
9. [Configuration](#9-configuration)
10. [Exception Reference](#10-exception-reference)

---

## 1. Overview

**Ocean Schedules** provides vessel and port schedule search for the Mercury platform. It aggregates carrier schedule data from both EDI (file-based) and direct API integrations with carriers, indexes it in Elasticsearch, and serves it to end-users via REST.

**Key capabilities:**
- Port-pair schedule search with multi-week horizon and nearby port expansion
- Carrier data management (port pairs, service enablement, API configurations)
- Admin process control (staging, loading, outbound, aggregation)
- User preference and recent search management
- Vessel detail lookup by IMO number

**Servlet Context:** `/inttra/mercury/api/oceanschedules`  
**Port:** 9990

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | DropWizard |
| DI Framework | Google Guice |
| Search | Elasticsearch 6.8.13 (via JestClient) |
| ORM | MyBatis |
| NoSQL | DynamoDB |
| Messaging | AWS SNS |
| Storage | AWS S3 |
| JWT | JJWT 0.11.2 |
| API Docs | Swagger/OpenAPI 3.0 |
| Build | Maven (Java 17) |

**Databases:**

| Database | Purpose |
|----------|---------|
| Aurora MySQL | User preferences, recent searches, vessel details, cutoff offsets, port pairs |
| DynamoDB | Real-time carrier response cache, staging data |
| Elasticsearch | Schedule data (`oceanschedulesdata-{SCAC}-*`, `os-pre-fetch-{SCAC}-*`) |

---

## 3. Architecture

```
HTTP Request
    │
    ▼
Resource Layer
    │
    ├─ ScheduleSearchService ──► Elasticsearch (schedule data)
    │                        ──► EnrichmentService (carrier, geo, cutoff)
    │
    ├─ CarrierService ────────► MySQL + Elasticsearch (port pairs)
    │                        ──► External Carrier APIs (port pair validation)
    │
    ├─ OSProcessService ──────► AWS SNS (trigger staging/load/outbound)
    │
    ├─ RecentSearchService ───► MySQL + GeographyClient (recent searches)
    │
    ├─ UserPreferenceService ─► MySQL (user preferences)
    │
    └─ VesselDetailsService ──► MySQL (vessel data)
```

---

## 4. API Endpoints

All endpoints require one of: `OCEANSCHEDULE_API_USER`, `OCEANSCHEDULE_USER`, or `NETWORK_ADMIN` unless noted.

### 4.1 Schedule Search — `/oceanschedules/schedule`

#### `GET /schedule`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `originPort` | String | **Yes** | UNECE Location Code (UNLOC) for origin |
| `destinationPort` | String | **Yes** | UNECE Location Code for destination |
| `searchDate` | String (YYYY-MM-DD) | **Yes** | Departure or arrival date |
| `searchDateType` | String | **Yes** | `ByDepartureDate` or `ByArrivalDate` |
| `weeksOut` | Integer (1–6) | **Yes** | Number of weeks to search forward |
| `scacs` | String | No | Comma-separated SCAC codes (all carriers if omitted) |
| `directOnly` | Boolean | No | Return only direct schedules (default: `false`) |
| `includeNearbyOriginPorts` | Boolean | No | Include nearby origin ports (default: `false`) |
| `includeNearbyDestinationPorts` | Boolean | No | Include nearby destination ports (default: `false`) |

**Response:** `List<InttraSchedule>`

**Processing:**
1. Validate all 6 required parameters
2. Validate UNLOC codes exist in system
3. Expand nearby ports if requested (using configured port surroundings map)
4. Query Elasticsearch for matching schedules
5. Enrich: carrier name, geography (city/country/subdivision), cutoff dates, duration
6. Filter invalid schedules (missing UNLOC, voyage number, or dates)
7. Return enriched schedule list

---

### 4.2 Carrier Management — `/oceanschedules/carrier`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/carrier` | Standard | List all OS carriers |
| `GET` | `/carrier/port-pair` | Standard | Query port pairs |
| `GET` | `/carrier/port-pair/{id}` | Standard | Get port pair by ID |
| `POST` | `/carrier/port-pair` | Standard | Create new port pair |
| `PUT` | `/carrier/port-pair/{id}/{supportedByCarrier}` | Standard | Update supported flag |
| `PUT` | `/carrier/port-pair/{id}/refreshRequestPayload` | Standard | Refresh carrier API payload |
| `DELETE` | `/carrier/port-pair/{id}` | Standard | Delete port pair |
| `GET` | `/carrier/service-enablement` | Standard | List service enablements |
| `POST` | `/carrier/service-enablement` | Standard (+ companyId=1000) | Create service enablement |
| `PUT` | `/carrier/service-enablement/{id}` | Standard (+ companyId=1000) | Update service enablement |

#### `GET /carrier/port-pair` — Query Parameters (all optional)

| Parameter | Type | Description |
|-----------|------|-------------|
| `scac` | String | Filter by carrier SCAC code |
| `loadPortUnCode` | String | Filter by load port UNLOC |
| `destinationPortUnCode` | String | Filter by destination port UNLOC |
| `supportedByCarrier` | Boolean | Filter by carrier support flag |

#### `GET /carrier/service-enablement` — Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `externalServiceName` | String | Filter by external service name |

---

### 4.3 Process Control — `/oceanschedules/process-maintenance`

**Roles:** `OCEANSCHEDULE_ADMIN_USER`, `NETWORK_ADMIN`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/process-maintenance/staging/start` | Start schedule staging for one or all carriers |
| `POST` | `/process-maintenance/loader/start` | Start schedule loader |
| `POST` | `/process-maintenance/outbound/start` | Start outbound process |
| `POST` | `/process-maintenance/aggregator/start` | Start aggregation process |
| `DELETE` | `/process-maintenance/purge` | Purge schedule data for a carrier |

#### Common Query Parameters for Start Endpoints

| Parameter | Type | Description |
|-----------|------|-------------|
| `scacs` | String | Comma-separated SCAC codes (all carriers if omitted) |

**Constraint:** Cannot provide both `scacs` query param AND a MetaData request body simultaneously.

#### `DELETE /process-maintenance/purge` — Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scac` | String | **Yes** | SCAC code to purge |

**Purge operations:**
- Deletes Elasticsearch index: `oceanschedulesdata-{SCAC}-*`
- Deletes Elasticsearch index: `os-pre-fetch-{SCAC}-*`
- Deletes S3 objects at configured purge paths

---

### 4.4 Recent Searches — `/oceanschedules/recentsearches`

**Roles:** `OCEANSCHEDULE_USER`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/recentsearches` | Get up to 12 most recent searches (newest first) |
| `PUT` | `/recentsearches` | Save a recent search |

**`PUT /recentsearches` Request Body:** `LocationSearch` object

**Response for `GET`:** Enriched with geography data (city, country, subdivision for origin and destination).

---

### 4.5 API Carriers — `/oceanschedules/apicarriers`

**Roles:** `OCEANSCHEDULE_USER`, `NETWORK_ADMIN`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/apicarriers` | List carriers providing API-based schedule data |

**Filter:** Only carriers with `osDataSourceType` containing `"API"`.

---

### 4.6 User Preferences — `/oceanschedules/user-preferences`

**Roles:** `OCEANSCHEDULE_USER`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/user-preferences` | Get user preferences (204 if not found) |
| `PUT` | `/user-preferences` | Save user preferences |

---

### 4.7 Vessel Details — `/oceanschedules/vesseldetails`

**Roles:** `OCEANSCHEDULE_USER`, `NETWORK_ADMIN`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/vesseldetails` | Look up vessel by IMO number |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `imoNumber` | String | **Yes** | Vessel IMO number |

**Response:** `VesselDetails` or `204 No Content` if not found.

---

## 5. Business Rules

### 5.1 Schedule Search Validation

| # | Rule |
|---|------|
| BR-OS-1 | All 6 required parameters (`originPort`, `destinationPort`, `searchDate`, `searchDateType`, `weeksOut`, and authorization) must be present and non-empty. |
| BR-OS-2 | `searchDateType` must be exactly `"ByDepartureDate"` or `"ByArrivalDate"`. |
| BR-OS-3 | `searchDate` must be in `YYYY-MM-DD` format. |
| BR-OS-4 | `weeksOut` must be an integer between **1 and 6** inclusive. |
| BR-OS-5 | `scacs` values must exist in the system (validated against combined EDI + API SCAC list). |
| BR-OS-6 | Origin and destination UNLOC codes must be valid location codes. |

### 5.2 Schedule Enrichment & Filtering

| # | Rule |
|---|------|
| BR-OS-7 | Schedules with missing origin or destination UNLOC are **filtered out**. |
| BR-OS-8 | Schedules without a voyage number are **filtered out**. |
| BR-OS-9 | Schedules without origin departure date or destination arrival date are **filtered out**. |
| BR-OS-10 | If vessel name is `null`, it is replaced with `"TO BE DECIDED"`. |
| BR-OS-11 | Terminal cutoff date is calculated as: `originDepartureDate + configuredOffset(SCAC, UNLOC)`. Lookback window: **90 days**. |
| BR-OS-12 | Carrier name is enriched from the SCAC code via `NetworkParticipantService`. |
| BR-OS-13 | Nearby ports expansion uses a configured mapping; when `includeNearbyOriginPorts=true` or `includeNearbyDestinationPorts=true`, additional UNLOCs are added to the search. |

### 5.3 Port Pair Rules

| # | Rule |
|---|------|
| BR-OS-14 | `scac`, `loadPortUnCode`, and `destinationPortUnCode` are **required** and cannot be empty. |
| BR-OS-15 | `loadPortUnCode` and `destinationPortUnCode` must be **different** ports. |
| BR-OS-16 | Duplicate combinations of `scac + loadPortUnCode + destinationPortUnCode` are not permitted. |
| BR-OS-17 | `createdBy`, `createdDate`, `lastModifiedBy`, `lastModifiedDate` are automatically set. |

### 5.4 Service Enablement Rules

| # | Rule |
|---|------|
| BR-OS-18 | `externalServiceName`, `tokenIntervalUnit`, `tokenCount`, and `tokenInterval` are required. |
| BR-OS-19 | `tokenCount` and `tokenInterval` must be **greater than zero**. |
| BR-OS-20 | `tokenIntervalUnit` must be a valid `TimeUnit` enum value (`SECONDS`, `MINUTES`, `HOURS`, `DAYS`). |
| BR-OS-21 | Duplicate `externalServiceName` values are not permitted. |
| BR-OS-22 | Creating/updating service enablements requires the caller's `companyId == 1000` (INTTRA internal). |

### 5.5 Recent Searches Rules

| # | Rule |
|---|------|
| BR-OS-23 | Maximum **12 recent searches** are stored per user. |
| BR-OS-24 | If a duplicate search exists, it is **removed** before adding the new one (no duplicates). |
| BR-OS-25 | Results are returned in **reverse chronological order** (most recent first). |
| BR-OS-26 | Each returned search is enriched with full geography details (city, country, subdivision) for origin and destination. |

### 5.6 Process Control Rules

| # | Rule |
|---|------|
| BR-OS-27 | Process start endpoints publish to the corresponding **SNS topic** for async execution. |
| BR-OS-28 | If `scacs` is not provided, the process runs for **all available carriers**. |
| BR-OS-29 | Providing both `scacs` query parameter AND a MetaData request body is invalid (`400 Bad Request`). |
| BR-OS-30 | SCAC codes are validated against the combined EDI + API source list before publishing. |

---

## 6. Service Layer

### 6.1 `ScheduleSearchService`

**Validation:** `UserSearchRequestValidator`  
**Search:** `InttraScheduleCollector` — aggregates results from all available sources (EDI, API, fallback)  
**Enrichment:** Carrier name, origin/destination geography, cutoff dates, duration, leg data

### 6.2 `CarrierService`

**Data sources:** NetworkParticipantService (carrier list), MySQL (port pairs, service enablement), Elasticsearch (purge)

**Caching:** Carrier data cached with key `"os_carriers"`.

### 6.3 `EnrichmentService`

**Responsibilities:**
- Carrier name from SCAC (network participant cache)
- Geography for each UNLOC (city, country, subdivision) via `GeographyClient` (cached)
- Cutoff dates from `CutoffOffsetService` (cached, key: `{scac}~~~{unloc}`)
- Transit duration in days per leg and total
- Leg-level origin/destination name enrichment

### 6.4 `OSProcessService`

**SNS Topics:**

| Process | Topic |
|---------|-------|
| Staging | `oceanSchedulesStagingArn` |
| Loader | `oceanSchedulesLoaderArn` |
| Outbound | `oceanSchedulesOutboundArn` |
| Aggregator | `oceanSchedulesAggregatorArn` |

**Message timestamp format:** `yyyy-MM-dd HH:mm:ss` (UTC)

### 6.5 `CutoffOffsetService`

**Pattern:** `ServiceCache` with `CacheLoader`  
**Cache key:** `{scac}~~~{unloc}`  
**Null caching:** Yes (prevents repeated DB hits for unconfigured pairs)

### 6.6 External Carrier API Client Architecture

Each carrier has a dedicated `PortPairRequestBuilder` and `ExternalClient<T>` implementation:

**Supported carriers:** Maersk, MSC, CMA, ZIM, Marfret, Swire, Hapag-Lloyd, SeaLead, Neptune, HMM, Evergreen, Wisetech, and more.

**Real-time caching:** `RealTimeCacheDao` (DynamoDB) stores carrier API responses.

---

## 7. Data Models

### 7.1 InttraSchedule

| Field | Type | Description |
|-------|------|-------------|
| `scac` | String | Carrier SCAC code |
| `carrierName` | String | Full carrier name (enriched) |
| `serviceName` | String | Service/route name |
| `vesselName` | String | Vessel name (or "TO BE DECIDED") |
| `voyageNumber` | String | Voyage number (required, filtered if missing) |
| `imoNumber` | String | IMO vessel identifier |
| `originUnloc` | String | Origin UN Location Code |
| `originCountry` | String | Origin country (enriched) |
| `originCityName` | String | Origin city (enriched) |
| `originSubdivision` | String | Origin state/province (enriched) |
| `originTerminal` | String | Origin terminal |
| `destinationUnloc` | String | Destination UN Location Code |
| `destinationCityName` | String | Destination city (enriched) |
| `destinationCountry` | String | Destination country (enriched) |
| `originDepartureDate` | LocalDateTime | Departure date/time |
| `destinationArrivalDate` | LocalDateTime | Arrival date/time |
| `estimatedTerminalCutoff` | LocalDateTime | Estimated terminal cutoff |
| `terminalCutoff` | LocalDateTime | Confirmed terminal cutoff |
| `bkCutoff` | LocalDateTime | Booking cutoff |
| `siCutoff` | LocalDateTime | Shipping instruction cutoff |
| `vgmCutoff` | LocalDateTime | VGM cutoff |
| `reeferCutoff` | LocalDateTime | Reefer cutoff |
| `totalDuration` | Integer | Total transit days |
| `scheduleSource` | String | `API`, `EDI`, or `FALLBACK` |
| `legs` | List\<InttraLeg\> | Individual voyage legs |

### 7.2 InttraLeg

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Leg sequence (1-based) |
| `transportType` | String | `Vessel`, `truck`, `rail`, etc. |
| `transportName` | String | Vessel or vehicle name |
| `conveyanceNumber` | String | Voyage number |
| `departureUnloc` | String | Departure location code |
| `departureCityName` | String | Departure city (enriched) |
| `departureDate` | LocalDateTime | Departure date |
| `arrivalUnloc` | String | Arrival location code |
| `arrivalCityName` | String | Arrival city (enriched) |
| `arrivalDate` | LocalDateTime | Arrival date |
| `transshipmentIndicator` | Boolean | Is this a transshipment? |
| `transitDuration` | Integer | Transit days for this leg |

### 7.3 PortPair

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Auto-generated primary key |
| `scac` | String | Carrier SCAC code |
| `loadPortUnCode` | String | Load port UNLOC |
| `destinationPortUnCode` | String | Destination port UNLOC |
| `supportedByCarrier` | Boolean | Carrier supports this pair |
| `requestPayload` | String | Carrier API request payload |
| `processDate` | LocalDate | Last processing date |
| `processStatus` | String | Processing status |
| `errorMessage` | String | Last error message |
| `createdDate` | LocalDateTime | Creation timestamp |
| `createdBy` | String | Creator user ID |
| `lastModifiedDate` | LocalDateTime | Last modification timestamp |
| `lastModifiedBy` | String | Last modifier user ID |

### 7.4 UserPreference

```json
{
  "carrierPreferences": { "scacs": ["MAEU", "HLCU"] },
  "daysOfWeekPreferences": {
    "departureDays": { ... },
    "arrivalDays": { ... },
    "cutOffDays": { ... }
  },
  "includeNearbyOriginPorts": false,
  "includeNearbyDestinationPorts": false,
  "defaultDateType": "ByDepartureDate",
  "defaultWeeksOut": 4,
  "defaultViewForRecentSearches": "Grid",
  "defaultViewForSearchResults": "Panel"
}
```

### 7.5 VesselDetails

| Field | Type | Description |
|-------|------|-------------|
| `vesselId` | Integer | Internal vessel ID |
| `vesselName` | String | Vessel name |
| `imoNumber` | String | IMO number |
| `owner` | String | Vessel owner |
| `operator` | String | Vessel operator |
| `flag` | String | Flag state |
| `callSign` | String | Radio call sign |
| `yearBuilt` | String | Year of construction |
| `teuCount` | Integer | TEU capacity |
| `grossTonnage` | Float | Gross tonnage |
| `netTonnage` | Float | Net tonnage |
| `length` | Float | Length (meters) |
| `width` | Float | Beam width (meters) |
| `carbonFootprint` | String | Carbon footprint rating |

---

## 8. External Integrations

### 8.1 Elasticsearch

**Indices:**
- `oceanschedulesdata-{SCAC}-*` — Main schedule data per carrier
- `os-pre-fetch-{SCAC}-*` — Pre-fetched/cached schedule data

**Query features:** Aggregations for unique SCAC extraction, date range filtering, schedule source filtering.

### 8.2 AWS SNS

**Topics:** One per process type (staging, loader, outbound, aggregator).  
**Message format:** JSON MetaData with SCAC list and timestamps.

### 8.3 AWS S3

**Buckets:** `oceanSchedulesBucket` — schedule staging data.  
**Operations:** List objects, delete objects per carrier SCAC on purge.

### 8.4 DynamoDB

**Purpose:** Real-time carrier API response cache (`RealTimeCache`), staging data (`SchedulesProStaging`).

### 8.5 External Carrier APIs

Each carrier API integration:
- Uses carrier-specific `PortPairRequestBuilder` to construct requests
- `ExternalClient<T>` handles HTTP communication
- `RealTimeCacheDao` caches responses in DynamoDB
- Carrier authentication configured per-service: MSC, ONE, ZIM, Timezone, Evergreen, Hapag-Lloyd

### 8.6 Network Services

| Service | Method | Purpose |
|---------|--------|---------|
| `GeographyClient` | `getGeoLocationDataByCode(unloc)` | Location enrichment (cached) |
| `GeographyClient` | `buildGeographyMap(Set<unloc>)` | Bulk location lookup |
| `NetworkParticipantClient` | `getOsCarrierData()` | All OS carriers |
| `NetworkParticipantClient` | `getCarrierDataByScacCode(scac)` | Single carrier lookup |

---

## 9. Configuration

| Property | Description |
|----------|-------------|
| `txTrackingElasticSearch.endpointUrl` | Elasticsearch endpoint |
| `oceanSchedulesBucket` | S3 bucket for schedule data |
| `oceanSchedulesStagingArn` | SNS topic for staging |
| `oceanSchedulesLoaderArn` | SNS topic for loader |
| `oceanSchedulesOutboundArn` | SNS topic for outbound |
| `oceanSchedulesAggregatorArn` | SNS topic for aggregator |
| `surroundingPortMappings` | Map of port → nearby ports for `includeNearbyPorts` |

**Jersey Client:**
- Min threads: 32, Max: 128, Queue: 8
- GZIP: Enabled, Timeout: 2 seconds

---

## 10. Exception Reference

**`MercuryOSRequestException`** (HTTP 400) — Request parameter validation:

| Code | Condition |
|------|-----------|
| Missing required parameters | Origin, destination, searchDate, searchDateType, weeksOut absent |
| Invalid `searchDateType` | Not `ByDepartureDate` or `ByArrivalDate` |
| Invalid `weeksOut` | Not an integer or not 1–6 |
| Invalid `directOnly` / `includeNearbyPorts` | Not a boolean |
| Invalid SCAC codes | Not found in system |

**`MercuryOSServiceException`** (HTTP 500) — Service-layer errors:

| Code Range | Meaning |
|------------|---------|
| 3100–3105 | CRUD operation failures |
| 3300–3340 | REST client failures (GET, POST, PUT, PATCH, DELETE) |
| 3350 | Response mapping error |
| 3400–3504 | HTTP 4xx/5xx from downstream |
| 3601 | INTTRA schedule data resource not defined |
| 3701 | No carrier data found |
| 3801 | Schedule translator not available |

---

*End of document — Ocean Schedules Service Business Rules & Technical Reference*
