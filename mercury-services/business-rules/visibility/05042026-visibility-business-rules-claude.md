# Visibility Service — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `visibility/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Submodule Map](#3-submodule-map)
4. [Architecture & Data Flow](#4-architecture--data-flow)
5. [visibility-inbound — REST API](#5-visibility-inbound--rest-api)
6. [visibility-inbound — Inbound EDI Processing](#6-visibility-inbound--inbound-edi-processing)
7. [visibility-matcher — Matching Processor](#7-visibility-matcher--matching-processor)
8. [visibility-outbound — Outbound Processor](#8-visibility-outbound--outbound-processor)
9. [visibility-pending — Retry Processor](#9-visibility-pending--retry-processor)
10. [visibility-wm-inbound-processor — Watermill](#10-visibility-wm-inbound-processor--watermill)
11. [visibility-itv-gps-processor — GPS Events](#11-visibility-itv-gps-processor--gps-events)
12. [Lambda Functions](#12-lambda-functions)
13. [Business Rules](#13-business-rules)
14. [Data Models](#14-data-models)
15. [External Integrations](#15-external-integrations)

---

## 1. Overview

The **Visibility** module provides container event tracking services — enabling shippers, carriers, and freight forwarders to track container movements across the supply chain.

It is a **multi-submodule** Maven project organized around a message-driven pipeline: inbound event ingestion → matching against bookings/BLs → outbound distribution to subscribers.

**Key capabilities:**
- REST API for container event submission and tracking queries
- Cargo visibility subscription management (bulk JSON and CSV)
- EDI-to-canonical event transformation
- Elasticsearch-based matching against bookings and shipping instructions
- Subscription-based outbound delivery (EDI via SQS, email via SES)
- Pending event retry (nightly scheduled Lambda)
- GPS event ingestion from ITV and Shippeo providers
- S3 archival of all processed events

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| REST API | DropWizard (JAX-RS) |
| Batch/Lambda | AWS Lambda |
| Search/Match | Elasticsearch |
| Event Queue | AWS SQS |
| Event Bus | AWS SNS |
| Storage | AWS S3 |
| Database | DynamoDB |
| Scheduling | AWS CloudWatch EventBridge |
| Legacy DB | Oracle (outbound threshold) |
| Email | AWS SES |
| Build | Maven (Java 17) per submodule |

---

## 3. Submodule Map

| Submodule | Type | Purpose |
|-----------|------|---------|
| `visibility-commons` | Library | Shared models, utilities, DynamoDB entities |
| `visibility-inbound` | DropWizard service | REST API + inbound EDI SQS processor |
| `visibility-matcher` | DropWizard service | DynamoDB stream → Elasticsearch matching |
| `visibility-outbound` | DropWizard service | Matched events → EDI/email distribution |
| `visibility-pending` | DropWizard service | Retry unmatched events (SQS-triggered) |
| `visibility-pending-start` | AWS Lambda | Nightly trigger for pending retry |
| `visibility-error-email` | AWS Lambda | Scheduled error report emails |
| `visibility-s3-archiver` | AWS Lambda | DynamoDB stream → S3 archival |
| `visibility-outbound-poller` | AWS Lambda | Oracle poll → outbound batch trigger |
| `visibility-wm-inbound-processor` | DropWizard service | Watermill/Shippeo/CargoWise events |
| `visibility-itv-gps-processor` | DropWizard service | ITV GPS S3 events |

---

## 4. Architecture & Data Flow

### Inbound Flow

```
EDI Source ──► S3 (file)
                 │
                 ▼
             SQS (inbound)
                 │
                 ▼
         InboundEdiProcessor
         (transform + validate)
                 │
                 ▼
         DynamoDB (container_events)
                 │
              DynamoDB Stream
                 │
                 ▼
             SNS notification
                 │
                 ▼
         SQS (matcher queue)
```

### Matching Flow

```
SQS (matcher)
    │
    ▼
MatchingProcessor
    ├─ Elasticsearch bulk query (bookings, SIs, BOLs)
    ├─ Update ContainerEvent with matches
    └─ For each match:
           └─► SQS (outbound queue) per subscription
    │
    └─ If no match:
           └─► DynamoDB (pending table)
```

### Outbound Flow

```
SQS (outbound)
    │
    ▼
OutboundSingleTransactionProcessor
    ├─ transactionsPerFile = 1 → send immediately
    └─ transactionsPerFile > 1 → increment threshold counter
                                    │
                               VisibilityOutboundPoller (Lambda)
                               checks count > 0 OR time > 30 min
                                    │
                               OutboundMultiTransactionProcessor
                                    │
                            OutboundGenerator → EDI/email
```

### Pending Retry Flow

```
CloudWatch EventBridge (nightly)
    │
    ▼
VisibilityPendingStart (Lambda)
Generates PendingFilter messages for:
  - Last 7 days (daily)
  - Last 28 days (weekly intervals)
    │
    ▼
SQS (pending queue)
    │
    ▼
PendingSqsProcessor
    ├─ Load pending by date + prefix
    ├─ Bulk match via Elasticsearch
    ├─ If matched → send outbound + delete pending
    └─ If not matched → keep pending
```

---

## 5. visibility-inbound — REST API

### 5.1 Container Tracking

#### `GET /track` (v1.0)

| Param | Type | Description |
|-------|------|-------------|
| `inttra_booking_reference` | String | Search by INTTRA booking ref |
| `carrier_booking_reference` | String | Search by carrier booking ref |
| `bill_of_lading_number` | String | Search by BOL number |
| `equipment_reference` | String | Search by equipment/container ID |

**Response:** `List<Container>` (v1 format)  
**Note:** Only one parameter at a time is supported.

#### `GET /v1.2/track` (v1.2)

Same parameters as v1.0, returns enhanced `List<Container>` (v1.2 format).

#### `GET /track/{broad_search_key}` / `GET /v1.2/track/{broad_search_key}`

Broad search — the path parameter is matched against all reference types.

#### `POST /v1.2/event` — Submit Container Event

**Roles:** `NETWORK_USER`, `NETWORK_ADMIN`

**Request Body (`ContainerEventSubmission`):**

| Field | Description |
|-------|-------------|
| `statusCode` | Event code (e.g., `DEPA`, `LOAD`, `DECA`, `GPS`) |
| `statusDate` | When event occurred |
| `statusLocation` | Location of event |
| `channel` | `API`, `EDI`, `WATERMILL` (auto-set to API if omitted) |
| `provider` | Reporting company (auto-set from authenticated user's company ID) |
| `equipmentDetails` | Container type, size, reference |
| `transportationDetails` | Voyage, vessel, port data |
| `references` | Booking, BOL, purchase order |
| `vesselDetail` | Vessel name, IMO, voyage |
| `premiumEvent` | Visibility level flag |

**Response:**
```json
{ "hashKey": "ce:uuid" }
```

#### `GET /v1.2/event/{id}` — Get Event by ID

**Roles:** `NETWORK_USER`, `NETWORK_ADMIN`  
**Response:** `List<ContainerEvent>`

---

### 5.2 Cargo Visibility API

#### `POST /cargo-visibility/submit/json`

**Roles:** `NETWORK_USER`, `NETWORK_ADMIN`  
**Content-Type:** `application/json`

**Request Body:** `List<CargoVisibilityRequest>`

```json
[
  {
    "carrier_scac": "MAEU",
    "booking_number": "123456",
    "bill_of_lading_number": "MAEU123456",
    "start_location_unloc": "USNYC",
    "end_location_unloc": "DEHAM"
  }
]
```

**Response:**
```json
{
  "status": "PARTIAL_SUCCESS",
  "message": "...",
  "items": [
    { "status": "ACCEPTED", "message": null },
    { "status": "REJECTED", "message": "Carrier not found" }
  ]
}
```

**Processing:** Parallel (20 threads) for batches ≥ 10 records; sequential for smaller batches.

#### `POST /cargo-visibility/submit/csv`

**Content-Type:** `multipart/form-data`  
**Form field:** `file` — CSV with headers: `carrier_scac`, `booking_number`, `bill_of_lading_number`, `start_location_unloc`, `end_location_unloc`

**Processing:** Same as JSON after CSV parsing.

---

### 5.3 Support / Admin API

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/support/report/email/{customerType}/{customerCode}` | `NETWORK_USER`, `NETWORK_ADMIN` | Send inbound error report for customer |
| `POST` | `/support/reprocess/inbound/{inboundContainerEventId}` | `NETWORK_USER`, `NETWORK_ADMIN` | Reprocess inbound event |
| `POST` | `/support/reprocess/outbound/{ipfId}/{sortKey}` | `NETWORK_USER`, `NETWORK_ADMIN` | Reprocess outbound event |
| `POST` | `/support/reprocess/partnerintegrator` | `NETWORK_USER`, `NETWORK_ADMIN` | Reprocess partner integrator events |
| `POST` | `/support/migrate/customer/{inttraCompanyId}` | `NETWORK_ADMIN` | Migrate T&T subscription from Oracle to Network Services |
| `POST` | `/support/rollback/customer/` | `NETWORK_ADMIN` | Rollback customer migration |
| `GET` | `/support/outboundThreshold/{id}` | `NETWORK_ADMIN` | Get outbound threshold by IPF ID |
| `GET` | `/support/outboundThreshold` | `NETWORK_ADMIN` | Get all outbound thresholds |
| `PUT` | `/support/outboundThreshold/{integrationProfileFormatId}` | `NETWORK_ADMIN` | Update outbound threshold |

**`/support/report/email/{customerType}/{customerCode}` Parameters:**

| Parameter | Values | Description |
|-----------|--------|-------------|
| `customerType` (path) | `scacCode`, `ediId`, `companyId` | How to identify the customer |
| `customerCode` (path) | String | Actual code/ID value |
| `startDate` (query) | LocalDate | Defaults to prior day |
| `endDate` (query) | LocalDate | Defaults to current date |

---

## 6. visibility-inbound — Inbound EDI Processing

**Processor:** `InboundEdiProcessor`  
**Trigger:** SQS message → S3 file read → transform → DynamoDB save

**Processing steps:**
1. Receive SQS message → extract MetaData
2. Read EDI content from S3 (using bucket + fileName from MetaData)
3. Apply custom transformations (loaded from subscription customizations)
4. Convert EDI to canonical `ContainerEventSubmission`
5. Validate and persist to DynamoDB
6. Log event with tokens (duration, container event ID, workflow ID)

**Custom Transformations:**
- Cached locally: max 500 entries, 30-minute TTL
- Retrieved by `ediId` + `integrationProfileFormatId`
- Applied only if enabled in subscription customizations

**SQS Error Handling:**

| Exception | Action |
|-----------|--------|
| `ProvisionedThroughputExceededException` | Do NOT delete SQS message (auto-retry via visibility timeout) |
| `NetworkServicesException` | Do NOT delete SQS message (auto-retry) |
| `WebApplicationException` (validation) | Delete SQS message (validation failures won't reprocess) |
| Other exceptions | Send to DLQ, delete SQS message |

---

## 7. visibility-matcher — Matching Processor

**Trigger:** DynamoDB Stream (INSERT) → SNS → SQS → `MatchingProcessor`

**Processing steps:**
1. Extract container event ID from DynamoDB stream event
2. Load full `ContainerEvent` from DynamoDB
3. **Skip GPS events** (`statusCode == "GPS"`)
4. Query Elasticsearch for matching transactions:
   - Bookings index
   - Shipping Instructions index
   - Bill of Lading index
5. Update ContainerEvent with: `matchedBookings`, `matchedShippingInstructions`, `matchedBillOfLadings`
6. For each match: determine subscriptions, send to outbound SQS queue
7. If no match: save to `container_events_pending` table for retry

**Match result token:** `matched = true/false` logged to SNS event.

**SQS Error Handling:**

| Exception | Action |
|-----------|--------|
| `ProvisionedThroughputExceededException` | Retry (no DLQ) |
| `RecoverableException` (ES busy) | Retry (no DLQ) |
| Other exceptions | Send to DLQ, delete SQS message |

---

## 8. visibility-outbound — Outbound Processor

**Processor:** `OutboundSingleTransactionProcessor`  
**Trigger:** SQS message containing `ContainerEventOutbound`

**Processing steps:**
1. Extract `ContainerEventOutbound` from SQS message projections
2. Load Integration Profile Format (IPF) for the outbound
3. **If `transactionsPerFile == 1`:**
   - Load inbound ContainerEvent
   - Call `outboundGenerator.createAndSendSingleTransaction()`
4. **If `transactionsPerFile > 1`:**
   - Increment counter in `ContainerEventOutboundThresholdDao`
   - Wait for `VisibilityOutboundPoller` to trigger batch send

**Outbound Threshold Table (Oracle):**
- Tracks transaction counts per Integration Profile Format
- `VisibilityOutboundPoller` checks every interval:
  - Send if `transactionCount > 0` AND `(count > threshold OR time since last execution > 30 minutes)`

**SQS Error Handling:**

| Exception | Action |
|-----------|--------|
| `ProvisionedThroughputExceededException` | Retry (no DLQ) |
| Missing/invalid IPF | Send to DLQ, log error |
| Other exceptions | Send to DLQ, delete SQS message |

---

## 9. visibility-pending — Retry Processor

**Processor:** `PendingSqsProcessor`  
**Trigger:** SQS message containing `PendingFilter { processDate, prefix }`

**Processing steps:**
1. Load pending container events by `processDate` + `prefix` from DynamoDB
2. Group into batches (size = `elasticsearchRequestLimit`)
3. For each batch:
   - Load full `ContainerEvent` from DynamoDB
   - Bulk match via Elasticsearch
4. For matched events:
   - Save updated ContainerEvent with match data
   - Get subscriptions for matched companies
   - Send to outbound SQS
   - Delete pending record
5. For unmatched events: keep in pending table

**SQS Error Handling:**

| Exception | Action |
|-----------|--------|
| `ProvisionedThroughputExceededException` | Retry (no DLQ) |
| `RecoverableException` | Retry (no DLQ) |
| Other exceptions | Send to DLQ, delete SQS message |

---

## 10. visibility-wm-inbound-processor — Watermill

**Trigger:** SQS message → S3 file read  
**Supported message types:**

| Message Type | Processor | Description |
|-------------|-----------|-------------|
| `SHIPPEO_CONTAINER_EVENT` | `ShippeoContainerEventProcessor` | Shippeo GPS → container event |
| `CARGOWISE_CONTAINER_EVENT` | CargoWise processor | CargoWise events |
| `CARGO_VISIBILITY_SUBSCRIPTION` | `CargoVisibilitySubscriptionProcessor` | Subscription updates |
| `CARGO_VISIBILITY_EVENT` | `CargoVisibilityEventProcessor` | Cargo visibility events |

**Processing:**
1. Extract MetaData from SQS message
2. Determine `messageType` from `projections["messageType"]`
3. Get S3 payload (bucket + fileName from MetaData)
4. Delegate to `MessageTypeProcessor.transformAndProcess(payload, metaData)`
5. Log event with tokens

**Error handling:** `InvalidEventCodeException` → log and skip; other exceptions → log error, send to DLQ.

---

## 11. visibility-itv-gps-processor — GPS Events

**Trigger:** S3 event notification → SNS → SQS  
**Processor:** `GPSEventProcessor`

**Processing steps:**
1. Extract SNS message from SQS body
2. Extract S3 event from SNS message
3. Read ITV GPS event JSON from S3
4. For each GPS upsert transaction (**parallel** via `parallelStream()`):
   - Map `ITVUpsert` → `ContainerEventSubmission` (via `ITVGPSEventMapper`)
   - Validate submission
   - Save to DynamoDB
   - Log event with tokens
5. Per-transaction errors are caught and logged without blocking other upserts

---

## 12. Lambda Functions

### `VisibilityPendingStart`

**Trigger:** CloudWatch EventBridge (nightly)  
**Purpose:** Generates PendingFilter messages to trigger retry processor

**Schedule:**
- Last **7 days**: 1 message per day per prefix
- Last **28 days**: 1 message per 7-day interval per prefix

### `VisibilityErrorEmail`

**Trigger:** CloudWatch EventBridge (scheduled)  
**Purpose:** Send error report emails to subscribers with `contextCode == "REPORT_CONTEXT"`

**Logic:**
- If subscription has EDI ID → send error report by EDI ID
- If subscription has INTTRA Company ID → send by company
- Otherwise → skip

### `VisibilityS3Archiver`

**Trigger:** DynamoDB Stream → SNS → SQS → Lambda  
**Purpose:** Archive processed container events to S3

**Logic:**
- Only process **UPDATE** events (skip INSERT/REMOVE)
- Read full item from DynamoDB (consistent read)
- Enrich locations (merge geography data)
- Skip GPS events
- Write to S3: `{year}/{month}/{day}/{hour}/{id}`

### `VisibilityOutboundPoller`

**Trigger:** CloudWatch EventBridge (scheduled)  
**Purpose:** Trigger batch outbound for IPFs with accumulated transactions

**Oracle query:**
```sql
SELECT integrationProfileFormatId, transactionCount, lastExecutionDatetime,
       transactionsPerFile, timeLimitInMinutes
FROM ContainerEvent.OutboundThreshold
```

**Send to outbound SQS when:**
- `transactionCount > 0` AND
- `(transactionCount >= transactionsPerFile OR time since last execution > 30 minutes)`

**Failure handling:** Retries Oracle connection up to 5 times on failover (SQLState `08S02`).

---

## 13. Business Rules

### 13.1 Container Event Ingestion

| # | Rule |
|---|------|
| BR-VIS-1 | The `channel` field defaults to `API` if not provided in REST submissions. |
| BR-VIS-2 | The `provider` field defaults to the authenticated user's `companyId` if not provided. |
| BR-VIS-3 | GPS events (statusCode = `"GPS"`) are skipped by the matcher and not matched against bookings. |
| BR-VIS-4 | Container event IDs are prefixed with `ce:`. |

### 13.2 Cargo Visibility Batch Processing

| # | Rule |
|---|------|
| BR-VIS-5 | Batches of **≥ 10 records** are processed in **parallel** (20 threads). Smaller batches are sequential. |
| BR-VIS-6 | All unique carriers in a batch are preloaded once before per-record processing to minimize HTTP calls. |
| BR-VIS-7 | Per-record status is `ACCEPTED` or `REJECTED`. Response status is `PARTIAL_SUCCESS` if any items fail. |
| BR-VIS-8 | Files are uploaded to S3 before processing begins (for observability). |

### 13.3 Matching Rules

| # | Rule |
|---|------|
| BR-VIS-9 | Matching queries Elasticsearch for bookings, shipping instructions, and bill of ladings matching the container event references. |
| BR-VIS-10 | Unmatched events are saved to the pending table for nightly retry. |
| BR-VIS-11 | Pending retry covers the last **7 days** (daily) and last **28 days** (weekly). |

### 13.4 Outbound Distribution

| # | Rule |
|---|------|
| BR-VIS-12 | `transactionsPerFile = 1` triggers **immediate** EDI/email send per event. |
| BR-VIS-13 | `transactionsPerFile > 1` triggers **batching** via the Oracle threshold table + Lambda poller. |
| BR-VIS-14 | Batch send is triggered when count exceeds threshold **or** 30 minutes have elapsed since last batch. |
| BR-VIS-15 | Custom EDI transformations are applied if enabled in the subscription configuration. |

### 13.5 Error Handling Rules

| # | Rule |
|---|------|
| BR-VIS-16 | `ProvisionedThroughputExceededException` never routes to DLQ — the message visibility timeout causes automatic SQS retry. |
| BR-VIS-17 | `WebApplicationException` (validation failures) are deleted from SQS without DLQ routing — they cannot be fixed by retry. |
| BR-VIS-18 | All other unrecoverable exceptions route to the DLQ. |

---

## 14. Data Models

### 14.1 ContainerEvent (DynamoDB)

**Table:** `container_events`

| Key / Field | Description |
|-------------|-------------|
| `id` (PK) | Prefixed UUID: `ce:{uuid}` |
| `bookingNumber` | Normalized uppercase |
| `billOfLading` | Normalized uppercase |
| `equipmentIdentifier` | Normalized uppercase |
| `bkInttraReferenceNumber` | INTTRA booking reference |
| `siInttraReferenceNumber` | Shipping instruction reference |
| `containerEventSubmission` | JSON of inbound event |
| `enrichedProperties` | Matched bookings/SIs/BOLs + classifications |
| `metaData` | Workflow tracking |
| `expiresOn` | TTL (epoch seconds) |

**Global Secondary Indexes:**
1. `bookingNumber-index`
2. `blNumber-index`
3. `equipmentIdentifier-index`
4. `bkInttraReferenceNumber-equipmentIdentifier-index`
5. `siInttraReferenceNumber-index`

### 14.2 ContainerEventEnrichedProperties

| Field | Description |
|-------|-------------|
| `matchedBookings` | List of matched booking references |
| `matchedShippingInstructions` | List of matched SI references |
| `matchedBillOfLadings` | List of matched BOL references |
| `requestedRecipients` | Companies with explicit subscriptions |
| `recipientCompanyIds` | Companies with matched products |
| `statusEventCode` | Classified event code with category |
| `transportationLocationGeography` | Resolved geography per location |
| `containerEventOutbound` | References to outbound events |

---

## 15. External Integrations

### 15.1 AWS Services

| Service | Purpose |
|---------|---------|
| DynamoDB | `container_events`, `container_events_outbound`, `container_events_pending`, `container_event_thresholds` |
| SQS | Inbound EDI, matching, outbound, pending, cargo-visibility, Watermill, ITV GPS queues |
| SNS | DynamoDB stream bridging, event publishing |
| S3 | EDI files, GPS files, workspace, archive |
| SES | Error report emails, subscription notifications |
| CloudWatch EventBridge | Lambda scheduling |
| Lambda | Pending start, error email, S3 archiver, outbound poller |

### 15.2 Internal Network Services

| Service | Purpose |
|---------|---------|
| `SubscriptionService` | Subscription configs and customizations |
| `IntegrationProfileFormatService` | Output format metadata |
| `NetworkParticipantService` | Carrier information |
| `ParticipantService` | Visibility permission checks |
| `GeographyService` | Location code resolution |
| `StatusEventCodeService` | Event code classification |
| `ContainerTypeService` | Equipment type lookup |
| `BlacklistEmailService` | Email validity checks |

### 15.3 Oracle Database

Used by `VisibilityOutboundPoller` Lambda to poll the `ContainerEvent.OutboundThreshold` table for batch outbound triggering.

### 15.4 Elasticsearch

- **Indices:** bookings, shipping_instructions, bill_of_ladings
- **Purpose:** Matching container events to transactions
- **Batch size:** Configurable (`elasticsearchRequestLimit`)
- **Error handling:** `RecoverableException` on index busy / throttle

---

*End of document — Visibility Service Business Rules & Technical Reference*
