# TX-Tracking Service — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `tx-tracking/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture](#3-architecture)
4. [API Endpoints](#4-api-endpoints)
5. [Business Rules](#5-business-rules)
6. [Elasticsearch Integration](#6-elasticsearch-integration)
7. [Reprocessing System](#7-reprocessing-system)
8. [Reporting System](#8-reporting-system)
9. [Export System](#9-export-system)
10. [Data Models](#10-data-models)
11. [Configuration](#11-configuration)

---

## 1. Overview

**TX-Tracking** is a transaction visibility and operational tooling service. It provides:

- Workflow and event search across the Mercury platform (Elasticsearch-backed)
- Transaction reprocessing (SQS-based retry)
- DLQ (Dead Letter Queue) management and purge
- Report generation and scheduled report email delivery
- CSV export of transaction data

**Root Path:** `/tx-tracking`  
**Port:** 8080 (API), 8081 (Admin)  
**Data Source:** Elasticsearch 6.6.2 (`txtrack-agg-*`, `txtrack-event-*` indices)

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | DropWizard |
| Search | Elasticsearch 6.6.2 (via JestClient) |
| Queue | AWS SQS |
| Storage | AWS S3 |
| Email | AWS SES |
| Serialization | Jackson (CSV + JSON) |
| Build | Maven (Java 17) |

---

## 3. Architecture

```
HTTP Request
    │
    ▼
TxTrackingResource
    │
    ├─ TxTrackingService ──────────► Elasticsearch (txtrack-agg-*, txtrack-event-*)
    │
    ├─ ReprocessService ───────────► Elasticsearch (read) + SQS (write)
    │
    ├─ ReportService ──────────────► Elasticsearch (scroll) + S3 + SES
    │
    └─ CsvWriterService ───────────► Elasticsearch (read) → HTTP Response (text/csv)

Scheduled:
ReportScheduler ──────────────────► ReportService → EmailSender
```

---

## 4. API Endpoints

**Base Path:** `/tx-tracking`

### 4.1 Workflow Search

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/workflow` | Filtered workflow list with pagination |
| `GET` | `/workflow/search` | Full-text workflow search |
| `GET` | `/workflow/{id}` | Detailed workflow with all components |
| `GET` | `/event/{id}` | Raw event by event ID |
| `GET` | `/module/{moduleType}` | Module-specific workflow search |

#### `GET /workflow` — Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `fromDateTime` | String | Start date/time filter |
| `toDateTime` | String | End date/time filter |
| `from` | Integer (default: 0) | Pagination offset |
| `size` | Integer (default: 10) | Page size |
| `inttraReferenceNumber` | String | INTTRA reference number filter |
| `carrierReferenceNumber` | String | Carrier reference filter |
| `shipmentId` | String | Shipment ID filter |
| `shipperReferenceNumber` | String | Shipper reference filter |
| `forwardersReferenceNumber` | String | Forwarder reference filter |
| `interchangeControlReferenceNumber` | String | EDI interchange reference filter |

**Response:**
```json
{
  "total": 42,
  "workflows": [ { "workflowId": "...", "startTimestamp": "...", ... } ]
}
```

#### `GET /workflow/search` — Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `q` | String | Yes | Full-text search query |
| `size` | Integer | No | Result count (default 10) |
| `from` | Integer | No | Pagination offset (default 0) |

#### `GET /workflow/{id}` — Response Structure

```json
{
  "workflow": {
    "workflowId": "...",
    "startTimestamp": "...",
    "components": [
      {
        "name": "booking-inbound",
        "runId": "...",
        "startTimestamp": "...",
        "endTimestamp": "...",
        "exitStatus": "success",
        "exceptions": [ { "code": "...", "value": "..." } ],
        "tokens": [ { "key": "xlogId", "value": "123" } ],
        "workspaceFileUrl": "https://s3.presigned..."
      }
    ]
  }
}
```

#### `GET /module/{moduleType}` — Supported Module Types

| Module Type | Search Scope |
|-------------|-------------|
| `container-event` | Visibility components (visibility-*, ce-*, distributor-*) |

---

### 4.2 Reprocessing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reprocess/{workflowId}/{runId}` | Reprocess a specific workflow run |
| `POST` | `/reprocess/dlq/{id}` | Reprocess all messages from a named DLQ |
| `POST` | `/reprocess/dlq/all` | Reprocess all configured DLQs |
| `POST` | `/purge/dlq/{name}/` | Download DLQ messages to S3 and delete |

#### `POST /reprocess/{workflowId}/{runId}` — Response

```json
{
  "trackingId": "uuid",
  "messages": ["MetaData sent to booking-inbound"]
}
```

#### `POST /reprocess/dlq/{id}` — Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `separator` | `_` | Character separating queue name from `dlq` suffix |

**DLQ URL constructed as:** `{baseSQSUrl}{queueName}{separator}dlq`

#### `POST /purge/dlq/{name}/` — Response

```json
{
  "preSignedUrl": "https://s3.presigned...",
  "fileName": "booking-inbound_messages/sqs_messages_uuid_timestamp.txt",
  "numberOfMessagesAffected": "42"
}
```

---

### 4.3 Reporting

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/report` | Execute a named report and return presigned S3 URL |
| `POST` | `/report/{id}` | Create or update report query definition (upload files) |

#### `POST /report` — Query Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `report_name` | Yes | Name of the report to execute |
| `index` | Yes | Elasticsearch index to query |
| `type` | Yes | Elasticsearch document type |
| Additional params | No | Template variable substitution values |

**Response:** Presigned S3 URL string for CSV download.

#### `POST /report/{id}` — Form Parameters (multipart/form-data)

| Field | Type | Description |
|-------|------|-------------|
| `queryFile` | File | Elasticsearch query template |
| `columnsFile` | File | CSV column heading definitions |

---

### 4.4 Export

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/export` | Export workflows to CSV |

#### `GET /export` — Query Parameters

| Parameter | Required | Values | Description |
|-----------|----------|--------|-------------|
| `context` | Yes | `requestBooking`, `confirmBooking`, `containerEvent` | Export format type |
| + all `/workflow` params | No | — | Same filters as workflow search |

**Response:** `text/csv` with `Content-Disposition: attachment; filename=transactions_{context}_{timestamp}.csv`

---

## 5. Business Rules

### 5.1 Workflow Search Rules

| # | Rule |
|---|------|
| BR-TX-1 | Workflow searches target the **aggregate index** (`txtrack-agg-*`). Event details are fetched from the **event index** (`txtrack-event-*`). |
| BR-TX-2 | Internal fields `es_metadata_id`, `dropOffQueue`, `nextRetry` are **excluded** from all search responses. |
| BR-TX-3 | Results are sorted by `startTimestamp` **descending** (most recent first). |
| BR-TX-4 | Full-text search (`/search`) uses Elasticsearch **multi-match** on `_all` field. |
| BR-TX-5 | Multi-valued search fields use `.keyword` suffix for exact match (not analyzed). |

### 5.2 Workflow Detail Rules

| # | Rule |
|---|------|
| BR-TX-6 | The detail view builds a **components list** from `startRun` / `closeRun` event pairs. |
| BR-TX-7 | If the workflow's start date is within **7 days**, date-specific index patterns are used (e.g., `txtrack-event-2026-05-01,...`). Beyond 7 days, the wildcard `txtrack-event-*` is used. |
| BR-TX-8 | Workspace file presigned S3 URLs are generated for **failed** run components (for diagnostic access). |

### 5.3 Reprocessing Rules

| # | Rule |
|---|------|
| BR-TX-9 | Reprocess searches for the `closeRun` event matching `workflowId` + `runId` to extract the pickup queue and message content. |
| BR-TX-10 | On reprocess, the workflow aggregate document is **updated** with the reprocess tracking ID and timestamp. |
| BR-TX-11 | If no `closeRun` event is found, the system falls back to the `startRun` event. |
| BR-TX-12 | DLQ reprocessing polls with **max 8 messages per batch** and a **5-second wait time**. |
| BR-TX-13 | DLQ polling stops after **2 consecutive empty batches** (max 20 iterations total). |
| BR-TX-14 | Successfully reprocessed DLQ messages are **deleted** from the DLQ after being sent to the main queue. |
| BR-TX-15 | The main queue URL is derived by stripping the `{separator}dlq` suffix from the DLQ URL. |

### 5.4 Report Rules

| # | Rule |
|---|------|
| BR-TX-16 | Report queries are stored in S3 at path `reports/query/{reportName}.txt`. |
| BR-TX-17 | Report column definitions are stored at `reports/query/{reportName}_columns.txt`. |
| BR-TX-18 | Report query parameters support token substitution: `{from_date}`, `{to_date}`, `{previousDayStart}`, `{previousDayEnd}`. |
| BR-TX-19 | Reports use Elasticsearch **scroll API** to retrieve all results beyond the default limit. |
| BR-TX-20 | Scheduled reports run daily at the time configured in `txReportConfig.scheduledTime` (UTC). |
| BR-TX-21 | Scheduled reports are sent via SES to subscribers of the `TxReport` module subscription. |

### 5.5 Export CSV Column Sets

**Request Booking (33 columns):** workflowId, xlogId, ediId, mftId, inttraReferenceNumber, bookerId, and booking-specific reference fields.

**Confirm Booking (32 columns):** Similar to request booking, minus some submission-specific fields.

**Container Event (31 columns):** workflowId, xlogId, scac, statusEventCode, containerEventId, visibility component fields, outbound subscription fields.

> Container event export generates **one row per outbound record** (flat expansion of the outbound transactions map).

---

## 6. Elasticsearch Integration

### Index Patterns

| Pattern | Purpose |
|---------|---------|
| `txtrack-agg-*` | Workflow aggregate summaries |
| `txtrack-event-*` | Individual workflow events per date |
| `txtrack-event-{date},...` | Date-specific patterns for recent workflows (< 7 days) |

### Event Document Fields

| Field | Description |
|-------|-------------|
| `workflowId` | Workflow identifier |
| `runId` | Run identifier (start/close pair) |
| `eventId` | Unique event ID |
| `component` | Component name (e.g., `booking-inbound`) |
| `type` | `startRun` or `closeRun` |
| `startTimestamp` / `endTimestamp` | ISO timestamps |
| `tokens` | Key-value metadata |
| `eventContent` | Serialized MetaData (bucket, fileName, exitStatus) |

### Query Strategy

- **BoolQuery** with MUST clauses for all filter parameters
- **Date range** on `startTimestamp`
- **Multi-match** on `_all` for full-text search
- **Aggregation** queries for module-specific searches (container-event)

---

## 7. Reprocessing System

```
POST /reprocess/{workflowId}/{runId}
        │
        ├─ Search Elasticsearch for closeRun event
        │     (workflowId + runId)
        │
        ├─ Extract: pickUpMessage, queueName
        │
        ├─ Generate trackingId (UUID)
        │
        ├─ Update aggregate doc in ES
        │     (set reprocess flag, timestamp, trackingId)
        │
        ├─ Send message to SQS queue (pickUpQueue)
        │
        └─ Return ReprocessResponse { trackingId, messages }
```

```
POST /reprocess/dlq/{queueName}
        │
        ├─ Build DLQ URL: baseSQSUrl + queueName + separator + "dlq"
        ├─ Poll DLQ (max 8 msgs, 5s wait)
        │     └─ Repeat until 2 consecutive empty batches (max 20 iterations)
        │
        ├─ For each message:
        │     ├─ Extract workflowId (from JSON)
        │     ├─ Send to main queue (queueName, no _dlq suffix)
        │     └─ Delete from DLQ
        │
        └─ Return count sent
```

---

## 8. Reporting System

### Report Query Templates

Stored in S3. Parameterized with `{token}` placeholders substituted from query parameters.

**Built-in token resolvers:**

| Token | Resolved Value |
|-------|---------------|
| `{from_date}` | User-provided start date |
| `{to_date}` | User-provided end date |
| `{previousDayStart}` | Yesterday 00:00:00 |
| `{previousDayEnd}` | Yesterday 23:59:59 |

### Scheduled Reports

```
ReportScheduler (daily at txReportConfig.scheduledTime)
    │
    ├─ Load subscriptions for module = "TxReport"
    ├─ For each subscription:
    │     ├─ Execute report query (Elasticsearch scroll)
    │     ├─ Write results to CSV
    │     └─ Send via SES to subscription recipients
    └─ Reschedule for next execution
```

---

## 9. Export System

**Container Event export** uses the `ContainerEventModuleSearch` which:
1. Filters by visibility component prefixes: `visibility-`, `ce-`, `distributor`
2. Applies date range (default 7 days if unspecified)
3. Finds distinct workflow IDs, then multi-searches for all component details
4. Enriches with container event data from the network service
5. Flattens the `outboundTransactions` map into individual rows

---

## 10. Data Models

### MetaData (SQS Message Content)

```json
{
  "messageId": "uuid",
  "workflowId": "uuid",
  "rootWorkflowId": "uuid",
  "parentWorkflowId": "uuid",
  "bucket": "s3-bucket-name",
  "fileName": "path/to/file",
  "component": "booking-inbound",
  "exitStatus": "success",
  "timestamp": "2026-05-04T12:00:00",
  "projections": {
    "xlogId": "12345",
    "mftId": "abc",
    "ediId": "MAEU",
    "reprocess": "true"
  }
}
```

### ReprocessResponse

```json
{
  "trackingId": "uuid",
  "messages": [
    "MetaData sent to booking-inbound",
    "Error: queue not found"
  ]
}
```

### PurgeResponse

```json
{
  "preSignedUrl": "https://s3.presigned...",
  "fileName": "queue_messages/sqs_messages_uuid_20260504.txt",
  "numberOfMessagesAffected": "15"
}
```

---

## 11. Configuration

| Property | Description |
|----------|-------------|
| `txTrackingElasticSearch.endpointUrl` | Elasticsearch cluster URL |
| `txTrackingElasticSearch.region` | AWS region (e.g., `us-east-1`) |
| `reprocessConfig.queues` | Comma-separated list of queue names for `/reprocess/dlq/all` |
| `reprocessConfig.baseSQSUrl` | Base SQS URL (prefix for queue names) |
| `txReportConfig.scheduledTime` | Daily report execution time (format: `HH:mm:ss`, UTC) |
| `txReportConfig.sender` | SES sender email address |
| `txReportConfig.reportBucket` | S3 bucket for report output |
| `workSpaceConfig.s3WorkSpaceBucket` | S3 bucket for workspace files (failed run diagnostics) |

**Jersey Client:**
- Min threads: 32, Max: 128, Queue: 8
- GZIP: Disabled, Chunked encoding: Disabled
- Timeout: 15 seconds

---

*End of document — TX-Tracking Service Business Rules & Technical Reference*
