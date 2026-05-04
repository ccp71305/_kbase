# WebBL Service — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `webbl/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture](#3-architecture)
4. [API Endpoints](#4-api-endpoints)
5. [Inbound Processing](#5-inbound-processing)
6. [Outbound Processing](#6-outbound-processing)
7. [Retry & Resilience](#7-retry--resilience)
8. [Business Rules](#8-business-rules)
9. [Data Models](#9-data-models)
10. [External Integrations](#10-external-integrations)
11. [Configuration](#11-configuration)

---

## 1. Overview

**WebBL** (Web Bill of Lading) is the service that manages the lifecycle of electronic Bills of Lading (eBL / WebBL). It:

- Exposes a REST API for BL lookup (internal admin only)
- Processes inbound PDF and ZIP files from SQS queues
- Distributes BL documents to subscribers via EDI (SQS) and email (SES)
- Maintains BL processing state in Oracle, MySQL, and DynamoDB
- Tracks retries for BLs not yet indexed in Elasticsearch

**Root Path:** Standard DropWizard context  
**Ports:** 8080 (API), 8081 (Admin)

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | DropWizard |
| DI Framework | Google Guice |
| Search | Elasticsearch 6.6.2 (via JestClient) |
| SQL ORM | MyBatis (Oracle + MySQL) |
| NoSQL | DynamoDB (AWS SDK v2, cloud-sdk) |
| Messaging | AWS SQS, AWS SNS |
| Storage | AWS S3 |
| Email | AWS SES (template-based) |
| Schema | JAXB-generated from XSD (`BLData.xsd`) |
| Build | Maven (Java 17) |

**Databases:**

| Database | Purpose |
|----------|---------|
| Oracle | WebBL process queue, BL document details, parties, references |
| MySQL (Network) | Retry request tracking |
| DynamoDB | BL versions (`bill_of_lading` table) |
| Elasticsearch | BL search index (`bl` type) |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              WebBL Service                               │
│                                                                          │
│  REST API              Inbound Listeners          Outbound Processing    │
│  ─────────             ─────────────────          ──────────────────     │
│  WebBLResource ──►     PDF SQS Listener ──►       OutboundServiceImpl   │
│  (admin only)          ZIP SQS Listener ──►         ├─ SQS (EDI)        │
│                        Oracle DB Listener ──►        └─ SES (email)     │
│                        MySQL DB Listener ──►                             │
│                                                                          │
│  Persistence           External Search            Network Services       │
│  ───────────           ───────────────            ─────────────────      │
│  DynamoDB BLVersions   Elasticsearch (BL index)   SubscriptionService   │
│  Oracle (BL docs)      (365-day rolling window)   NetworkParticipant    │
│  MySQL (retries)                                  GeographyService      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. API Endpoints

**Base Path:** (DropWizard root)

### `GET /{carrierId}/{blNumber}`

**Access control:** Only users with `companyId == 1000` (INTTRA internal) are permitted.

| Aspect | Detail |
|--------|--------|
| Auth | `Authorization: Bearer <token>` (required) |
| Response | `BLContract` JSON |
| 403 | If caller's `companyId ≠ 1000` |
| 404 | If BL not found in Elasticsearch |

**Processing steps:**
1. Validate caller is INTTRA internal company (companyId = 1000)
2. Search Elasticsearch for BL using `blNumber` + `carrierId` (within last 365 days)
3. Load matching `BLVersion` records from DynamoDB by ID
4. Select the most relevant version (see [BR-WBL-4](#81-bl-version-selection))
5. Parse BL message JSON to `BLContract` and return

---

## 5. Inbound Processing

### 5.1 PDF Inbound Processor (`WebBLPDFInboundProcessorTask`)

**Thread pool:** 8 threads, `SynchronousQueue`, `CallerRunsPolicy`  
**Input:** SQS queue (`appianWayConfig.inPDFQueueUrl`)

**Processing flow:**

```
SQS Message received
        │
        ▼
Deserialize → MetaData
Extract filename: {SCAC_CODE}_{BL_NUMBER}.pdf
        │
        ├─ Parse SCAC (before first `_`)
        └─ Parse BL number (between `_` and `.pdf`)
              │
              ├─ Failure → BLNumberNotFound (non-retriable)
              │
              ▼
Lookup NetworkParticipant by SCAC code
              │
              ├─ Not found → CarrierNotFound (non-retriable)
              │
              ▼
Search Elasticsearch: blNumber + carrierId
              │
              ├─ Not found → BillOfLadingNotFound (RETRIABLE)
              │
              ▼
Load BLVersion from DynamoDB by ID
              │
              ▼
Select most relevant BLVersion (see BR-WBL-4)
              │
              ▼
OutboundService.processOutbound(blVersion, metaData, errors)
              │
              ▼
Delete SQS message
```

**Non-retriable errors** (`BLNumberNotFound`, `CarrierNotFound`):
- Call `processError()` → sends error email to subscribers
- Delete SQS message

**Retriable errors** (`BillOfLadingNotFound`):
- On attempt 0: Store MetaData JSON to S3, create `RetryRequest` in MySQL
- On attempts 1–4: Update `RetryRequest` with next retry date (minute-based intervals)
- On attempt 5+: Delete `RetryRequest`, send error emails (max retries reached)
- Separate scheduler/listener polls MySQL retry table and reprocesses

### 5.2 ZIP Inbound Processor (`WebBLZipInboundProcessorTask`)

**Status:** Partially implemented — returns empty `WebBLResult`. ZIP processing is intended but not complete.  
**Thread pool:** 8 threads, `SynchronousQueue`

### 5.3 Oracle DB Listener (`InttraDBListener`)

Polls Oracle process queue for `WebBLProcessRequest` records with status `SUBMITTED`.

**Atomic claim pattern:**
```sql
SELECT ... FROM webbl_process_queue WHERE status = 'SUBMITTED'
FOR UPDATE SKIP LOCKED  -- row-level lock, skip locked rows
(up to 5000 rows)

UPDATE webbl_process_queue SET status = 'IN_PROCESSING' WHERE id IN (...)
-- batched in chunks of 1000 (Oracle IN clause limit)
```

---

## 6. Outbound Processing

### 6.1 `OutboundServiceImpl.processOutbound()`

Runs asynchronously (32-thread pool, 60-item `ArrayBlockingQueue`).

**Per subscription processing:**

```
Extract coded parties from BLVersion message
        │
        ▼
Fetch subscriptions for each party (SubscriptionService, cached)
Filter by direction = outbound
        │
        ▼
For each subscription:
    ├─ Download PDF from S3 workspace
    ├─ Generate XML metadata (BlCrossReferenceType via JAXB)
    ├─ Create ZIP: XML + PDF
    ├─ Upload ZIP to S3
    │
    ├─ EDI actions:
    │     ├─ Get IntegrationProfileFormat metadata
    │     ├─ Set MetaData projections (targetId, formatId, etc.)
    │     └─ Send to SQS distributor queue
    │
    ├─ EMAIL actions:
    │     └─ Send via SES (SuccessTemplate)
    │
    └─ Archive BL data to S3 archive bucket
        │
        ▼
Log START_WORKFLOW and CLOSE_WORKFLOW events (SNS)
```

### 6.2 Error Processing (`processError()`)

- Finds subscriptions with `ERROR_EMAIL` action type via MFT ID
- Sends error emails containing validation error details

---

## 7. Retry & Resilience

### 7.1 PDF Retry Schedule

| Attempt | Interval |
|---------|----------|
| 0 (initial) | Immediate (store to S3, create retry record) |
| 1 | `firstRetryGapInMinutes` |
| 2 | `secondRetryGapInMinutes` |
| 3 | `thirdRetryGapInMinutes` |
| 4 | `fourthRetryGapInMinutes` |
| 5+ | `lastRetryGapInDays` (switched to days) |
| Max | 5 retries (`MAX_RETRY_COUNT`) |

After max retries: delete retry record, send error emails.

### 7.2 Network Service Client Retry

| Failure | Behavior |
|---------|----------|
| `401 Unauthorized` | Refresh token, retry (up to 3 times) |
| Socket timeout | Log, retry |
| Other transient | Retry with backoff |
| `404 Not Found` | Return `Optional.empty()` |
| `RecoverableException` (e.g., ES 429) | Re-throw as `RecoverableException` |

---

## 8. Business Rules

### 8.1 BL Version Selection

| # | Rule |
|---|------|
| BR-WBL-1 | If exactly **one BLVersion** is found in DynamoDB, it is used directly. |
| BR-WBL-2 | If **multiple versions** exist, filter for those containing `"FinalTransmission"` in the `sequenceNumber`. |
| BR-WBL-3 | Among filtered versions, select the one with the **latest `expiresOn`** date. |
| BR-WBL-4 | If no "FinalTransmission" versions exist, select the version with the **latest `expiresOn`** from all versions. |

### 8.2 Elasticsearch Search Rules

| # | Rule |
|---|------|
| BR-WBL-5 | BL search uses a **BoolQuery** with: type = `bl`, carrierId matches, last modified within **365 days**. |
| BR-WBL-6 | SHOULD clause matches BL number **or** booking number (minimum 1 match required). |
| BR-WBL-7 | Result set limit: **10,000 documents** with a 1-minute scroll timeout. |
| BR-WBL-8 | HTTP 429 (Too Many Requests) from Elasticsearch triggers a `RecoverableException` (caller should retry). |

### 8.3 Oracle Process Queue Rules

| # | Rule |
|---|------|
| BR-WBL-9 | Oracle `SELECT FOR UPDATE SKIP LOCKED` ensures no two processes claim the same BL record. |
| BR-WBL-10 | Oracle `IN` clause is limited to **1000 items**; batch updates are automatically partitioned. |
| BR-WBL-11 | Up to **5,000 rows** are claimed per polling cycle. |

### 8.4 Outbound Distribution Rules

| # | Rule |
|---|------|
| BR-WBL-12 | EDI actions send MetaData to the SQS **distributor queue** (or action-specific queue). |
| BR-WBL-13 | EMAIL actions send via **SES template** (`SuccessTemplate`). |
| BR-WBL-14 | Each outbound creates a **new workflow ID** for tracking. |
| BR-WBL-15 | After outbound, BL data is archived to the **S3 archive bucket** with a random WebBL Feed ID. |

### 8.5 API Access Rules

| # | Rule |
|---|------|
| BR-WBL-16 | The REST endpoint `GET /{carrierId}/{blNumber}` is restricted to `companyId == 1000` (INTTRA internal). |
| BR-WBL-17 | Any other company receives `403 Forbidden`. |

---

## 9. Data Models

### 9.1 BLVersion (DynamoDB)

**Table:** `bill_of_lading`

| Field | Type | Description |
|-------|------|-------------|
| `id` | String (PK) | BL identifier |
| `sequenceNumber` | String (SK) | Format: `m_{timestamp}_{state}_{inttraRefNumber}` |
| `blInttraReferenceNumber` | String (GSI key) | INTTRA reference number |
| `carrierId` | String | Carrier identifier |
| `bookingNumber` | String | Booking number |
| `blNumber` | String | Bill of Lading number |
| `message` | String | JSON-serialized `BLContract` |
| `expiresOn` | Date | TTL field (auto-delete) |

**GSI:** `INTTRA_REFERENCE_NUMBER_INDEX` on `blInttraReferenceNumber`  
**Streams:** `KEYS_ONLY`

### 9.2 RetryRequest (MySQL)

| Field | Type | Description |
|-------|------|-------------|
| `id` | String | Unique ID |
| `retryCount` | Integer | Current retry attempt (0–5) |
| `nextRetryDate` | Date | Scheduled next retry |
| `expiresOn` | Date | Auto-cleanup date |
| `workflowId` | String | Associated workflow |
| `queueStatus` | String | `IN_QUEUE`, `IN_PROCESSING` |
| `workspaceFilePath` | String | S3 path to stored MetaData JSON |

### 9.3 WebBLProcessRequest (Oracle)

| Field | Type | Description |
|-------|------|-------------|
| `webBLFeedId` | Integer | Feed identifier |
| `blId` | Integer | BL identifier |
| `processRequest` | Enum | `SUBMITTED`, `IN_PROCESSING`, `COMPLETED`, `FAILED` |

### 9.4 BlCrossReferenceType (JAXB)

Generated from `BLData.xsd`. Contains:
- `control`: Bill metadata
- `document`: Parties (shipper, consignee, notify)
- `sailing`: Vessel, voyage, ports
- `references`: BL#, booking#, equipment
- `equipment`: Container list
- `letterOfCredit`
- `comments`

---

## 10. External Integrations

### 10.1 AWS Services

| Service | Operation | Purpose |
|---------|-----------|---------|
| SQS | Receive, Send, Delete | Inbound PDF/ZIP + outbound EDI distribution |
| SNS | Publish | Workflow event tracking |
| S3 | Put, Get, Copy | PDF/XML/ZIP workspace, archive, retry metadata |
| DynamoDB | Query, Save | BL version storage |
| SES | SendTemplateEmail | Success and error email notifications |

### 10.2 Databases

| Database | Tables | Purpose |
|----------|--------|---------|
| Oracle | WebBL process queue, BL details, references, parties, equipment, shipping | BL document storage and processing queue |
| MySQL | RetryRequest | PDF retry tracking |

### 10.3 Network Services

| Service | Purpose |
|---------|---------|
| `SubscriptionService` | Fetch outbound subscriptions per party |
| `NetworkParticipantService` | Carrier lookup by SCAC code |
| `GeographyService` | Location code resolution (2,500 cache entries, 6h TTL) |
| `IntegrationProfileFormatService` | Output format metadata |

---

## 11. Configuration

### Key Configuration Properties

| Property | Description |
|----------|-------------|
| `appianWayConfig.inPDFQueueUrl` | SQS URL for inbound PDF messages |
| `appianWayConfig.inZIPQueueUrl` | SQS URL for inbound ZIP messages |
| `appianWayConfig.distributorQueueUrl` | SQS URL for outbound EDI distribution |
| `appianWayConfig.s3WorkSpaceLocation` | S3 workspace bucket |
| `s3ArchiveBucket` | S3 bucket for archived BL data |
| `appianWayConfig.listenerEnabled` | Enable/disable SQS listeners |
| `appianWayConfig.outboundEnabled` | Enable/disable outbound processing |
| `dynamoDbConfig` | DynamoDB connection settings |
| `blElasticSearchConfig` | Elasticsearch cluster settings |
| `retryConfig.firstRetryGapInMinutes` | PDF retry 1 interval |
| `retryConfig.secondRetryGapInMinutes` | PDF retry 2 interval |
| `retryConfig.thirdRetryGapInMinutes` | PDF retry 3 interval |
| `retryConfig.fourthRetryGapInMinutes` | PDF retry 4 interval |
| `retryConfig.lastRetryGapInDays` | PDF final retry interval (in days) |

### Thread Pools

| Pool | Size | Queue | Policy |
|------|------|-------|--------|
| PDF Processor | 8 | `SynchronousQueue` | `CallerRunsPolicy` |
| ZIP Processor | 8 | `SynchronousQueue` | `CallerRunsPolicy` |
| Outbound Service | 32 | `ArrayBlockingQueue(60)` | Load shedding |

---

*End of document — WebBL Service Business Rules & Technical Reference*
