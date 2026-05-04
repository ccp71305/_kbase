# Booking Bridge — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `booking-bridge/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture](#3-architecture)
4. [Message Processing Pipeline](#4-message-processing-pipeline)
5. [Business Rules](#5-business-rules)
6. [State Machine](#6-state-machine)
7. [External Integrations](#7-external-integrations)
8. [Data Models](#8-data-models)
9. [Configuration](#9-configuration)
10. [Concurrency & Resilience](#10-concurrency--resilience)
11. [Event Publishing](#11-event-publishing)
12. [Data Retention](#12-data-retention)

---

## 1. Overview

**Booking Bridge** is a message-driven microservice that acts as the routing bridge between the Mercury booking platform and IBM MQ (used by downstream booking processing systems).

It has **no REST API endpoints**. It operates entirely through:
- **Input:** AWS SQS queue polling
- **Processing:** Distributed locking, deduplication, IBM MQ routing
- **Output:** IBM MQ queue + AWS SNS event publishing

**Primary responsibilities:**
1. Poll SQS for booking change notifications
2. Acquire a distributed lock to prevent duplicate processing
3. Route unique booking events to IBM MQ
4. Persist routing state to DynamoDB (7-day TTL)
5. Publish workflow events (start/close) to SNS for observability

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | DropWizard |
| DI Framework | Google Guice |
| Message Broker (input) | AWS SQS |
| Message Broker (output) | IBM MQ 9.4.4.1 |
| Event Bus | AWS SNS |
| NoSQL Store | DynamoDB (AWS SDK v2) |
| Build | Maven (Java 17) |
| Thread Pool | Java `ExecutorService` (8 threads) |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Booking Bridge                               │
│                                                                      │
│  ┌──────────────┐    ┌───────────────────────┐    ┌──────────────┐  │
│  │ SQSListener  │───►│ BookingBridgeProcessor │───►│  MQService   │  │
│  │ (polling)    │    │ Task (8 threads)       │    │ (IBM MQ)     │  │
│  └──────────────┘    └──────────┬────────────┘    └──────────────┘  │
│                                 │                                    │
│                    ┌────────────┼────────────┐                       │
│                    │            │            │                        │
│              ┌─────▼──────┐  ┌─▼────────┐ ┌▼─────────────────┐    │
│              │ Message    │  │ XlogDetail│ │ EventLogger (SNS) │    │
│              │ Register   │  │ Dao       │ │                   │    │
│              │ Service    │  │ (DynamoDB)│ │                   │    │
│              └────────────┘  └──────────┘ └──────────────────-┘    │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                         │
      AWS SQS             DynamoDB                  AWS SNS
```

---

## 4. Message Processing Pipeline

### 4.1 SQS Listener (`SQSListener`)

- Runs in a **single background thread** (via `ListenerManager`)
- Polls the configured SQS queue in an **infinite loop** until shutdown
- Submits received messages to the processor task
- Message deletion happens via `successCallback` after processing completes

**Configuration:**

| Property | Description |
|----------|-------------|
| `waitTimeSeconds` | Long-poll duration (1–20 seconds recommended) |
| `maxNumberOfMessages` | Messages per poll (typically 1; SQS max = 10) |
| `listenerEnabled` | Boolean to enable/disable on startup |

### 4.2 Processor Task (`BookingBridgeProcessorTask`)

- Thread pool: **8 fixed threads**, `SynchronousQueue` (no buffering)
- `CallerRunsPolicy`: If pool is full, the calling thread processes directly
- Shutdown timeout: **30 seconds**

**Per-message execution steps:**

```
1. Deserialize SQS payload → MetaData (JSON)
2. Extract xlogId from MetaData.projections[XLOG_ID]
3. Publish START_RUN_EVENT to SNS
4. Call BookingBridgeService.routeToDestination(xlogId, tokens)
5. On exception: send to DLQ ({queueUrl}_dlq)
6. Finally: delete message from SQS (successCallback)
7. Publish CLOSE_RUN_EVENT to SNS with all tokens
```

**Tokens captured and emitted in events:**

| Token Key | Possible Values |
|-----------|----------------|
| `xlogId` | Booking identifier |
| `routingStatus` | `ROUTED`, `IGNORED` |
| `ignored` | `true`, `false` |
| `lockState` | Response from Message Register (`CREATED`, `RETRY`, `DUPLICATE`) |
| `dropOffQueue` | IBM MQ queue name (if routed) |
| `dlq` | DLQ path (if exception occurred) |

---

## 5. Business Rules

### 5.1 Core Processing Rules (`BookingBridgeService.routeToDestination`)

| # | Rule |
|---|------|
| BR-BB-1 | A distributed lock is acquired for each message using key `"BRIDGE_" + xlogId` via the Message Register Service (TTL = 5 minutes). |
| BR-BB-2 | If the lock response is **not** `CREATED` (i.e., `RETRY` or `DUPLICATE`), the message is **skipped** — another process owns the lock. |
| BR-BB-3 | If the lock is acquired, DynamoDB is queried to check if `xlogId` was already processed. |
| BR-BB-4 | If a DynamoDB record exists for the `xlogId`, the message is marked `IGNORED` (already routed) — no MQ send occurs. |
| BR-BB-5 | If no DynamoDB record exists, the `xlogId` is written to an IBM MQ message and sent to the queue (committed transactionally). |
| BR-BB-6 | After successful MQ send, the `xlogId` is saved to DynamoDB with a **7-day TTL** (prevents re-routing within the window). |
| BR-BB-7 | The distributed lock is **always released** in the finally block (TTL = 1 second), regardless of success or failure. |
| BR-BB-8 | On MQ failure (`MQException`), the service attempts to **reconnect indefinitely** (every 60 seconds) before throwing. |
| BR-BB-9 | The SQS message is **always deleted** from the queue (via `successCallback`), even on exception. Failed messages are routed to the DLQ. |

### 5.2 Deduplication Rules

| # | Rule |
|---|------|
| BR-BB-DUP-1 | Deduplication is **two-layered**: distributed lock (fast) + DynamoDB record (persistent). |
| BR-BB-DUP-2 | The DynamoDB TTL is **7 days** — re-processing of the same `xlogId` within 7 days is blocked. |
| BR-BB-DUP-3 | The distributed lock TTL is **5 minutes** — prevents concurrent parallel processing of the same message. |
| BR-BB-DUP-4 | Expired locks (stale in-flight) are automatically overwritten on next attempt. |

---

## 6. State Machine

```
SQS Message Received
        │
        ▼
  Parse MetaData, extract xlogId
        │
        ▼
  Publish START_RUN_EVENT (SNS)
        │
        ▼
  Acquire Lock via MessageRegisterService
  Key = "BRIDGE_" + xlogId, TTL = 5 min
        │
        ├─ CREATED ──────────────────────────────────────┐
        │                                                │
        │   ┌─────────────────────────────┐             │
        │   │ Query DynamoDB for xlogId   │             │
        │   └──────────┬──────────────────┘             │
        │              │                                 │
        │     Found ───┤         Not Found               │
        │              │              │                  │
        │              ▼              ▼                  │
        │         IGNORED         Send to IBM MQ         │
        │         (skip)          Commit TX              │
        │                         Save to DynamoDB (7d)  │
        │                         → routingStatus=ROUTED │
        │                                                │
        └─ NOT CREATED (RETRY/DUPLICATE) ────► IGNORED  │
                                                         │
                           ◄────────────────────────────┘
                  Release Lock (TTL = 1 sec)
                           │
                           ▼
                  Delete SQS Message
                           │
                           ▼
                  Publish CLOSE_RUN_EVENT (SNS)
```

---

## 7. External Integrations

### 7.1 IBM MQ

| Property | Description |
|----------|-------------|
| `hostName` | MQ server hostname |
| `port` | MQ server port |
| `channel` | MQ channel name |
| `queueMgrName` | Queue manager name |
| `queueName` | Target queue for bookings |
| `backoutQueue` | Dead-letter queue |
| `backoutThreshold` | Max delivery attempts before DLQ |

**Message format:** Plain string containing the `xlogId`.  
**Commit strategy:** Explicit `mqMgr.commit()` after each `put()`.  
**Failure behavior:** Retry connection every 60 seconds indefinitely on `MQException`.

### 7.2 Message Register Service (Network Services)

REST integration for distributed locking.

| Operation | HTTP | TTL | Response |
|-----------|------|-----|----------|
| Lock (acquire) | `POST` | 300s (5 min) | `CREATED` \| `RETRY` \| `DUPLICATE` |
| Release (unlock) | `PUT` | 1s | `UPDATED` \| `INCONSISTENT` |

### 7.3 Auth Service

- Used by `NetworkServiceClient` to obtain OAuth2 client credentials tokens
- Token is refreshed automatically on `401 Unauthorized`
- Synchronized `newToken()` prevents thundering herd

### 7.4 AWS SQS

- Input queue: `config.inQueueUrl`
- DLQ: `config.inQueueUrl + "_dlq"` (automatic naming convention)
- Message deletion via `successCallback` after processing

### 7.5 AWS SNS

- Topic: `config.snsTopicARN`
- Events published: `START_RUN_EVENT`, `CLOSE_RUN_EVENT`
- Failures are **logged and swallowed** (fail-silent; does not affect message routing)

---

## 8. Data Models

### 8.1 XlogDetail (DynamoDB)

**Table:** `XlogDetail`

| Field | Type | Description |
|-------|------|-------------|
| `xlogId` | String (PK) | Booking transaction ID |
| `createdDate` | Date | Creation timestamp (epoch seconds) |
| `expiresOn` | Date | TTL field — 7 days from creation |

Note: `expiresOn` strips milliseconds precision (DynamoDB TTL requirement).

### 8.2 MetaData (SQS Message Payload)

```json
{
  "workflowId": "uuid",
  "messageId": "uuid",
  "projections": {
    "xlogId": "12345"
  }
}
```

The `xlogId` is extracted from `metaData.getProjections().get("xlogId")`.

### 8.3 RegisterRequest (to Message Register)

```json
{
  "key": "BRIDGE_12345",
  "ttl": 300
}
```

---

## 9. Configuration

**`BookingBridgeConfig` properties:**

| Property | Type | Description |
|----------|------|-------------|
| `inQueueUrl` | String | SQS input queue URL |
| `snsTopicARN` | String | SNS topic ARN for events |
| `mqConfig` | MQConfig | IBM MQ connection parameters |
| `dynamoDbConfig` | BaseDynamoDbConfig | DynamoDB settings |
| `listenerEnabled` | Boolean | Start SQS listener on boot |
| `waitTimeSeconds` | Integer | SQS long-poll duration |
| `maxNumberOfMessages` | Integer (max 10) | SQS batch size |
| `maxRetries` | Integer (max 5, default 3) | Network client retries |
| `maxDelay` | Integer (default 10000ms) | Max backoff delay |
| `baseDelay` | Integer (default 100ms) | Base backoff delay |

**Network client retry strategy:**

| Failure Type | Behavior |
|--------------|----------|
| `401 Unauthorized` | Refresh token, retry (up to 3 times) |
| Socket timeout | Log, retry with exponential backoff |
| `5xx Server Error` | Log, retry |
| `404 Not Found` | Return empty / throw |
| Other `4xx` | Throw immediately (no retry) |

---

## 10. Concurrency & Resilience

### Thread Model

| Component | Threads | Queue |
|-----------|---------|-------|
| SQS Listener | 1 | N/A (polling loop) |
| Processor Task | 8 fixed | `SynchronousQueue` (no buffer) |
| Auth Token Refresh | Synchronized | N/A |

### Failure Handling

| Failure | Behavior |
|---------|----------|
| Missing `xlogId` in MetaData | Log error, skip, still delete SQS message |
| MQ connection failure | Reconnect loop every 60 seconds |
| DynamoDB exception | Fail-safe — returns empty list (treated as no prior record) |
| SNS publish failure | Log error, swallow exception |
| Any unhandled exception | Route message to DLQ (`{queueUrl}_dlq`), delete SQS message |

### Shutdown Sequence

1. `ListenerManager.stop()` → calls `listener.shutdown()` (sets interrupted flag)
2. ExecutorService shutdown with 30-second timeout
3. `mqService.close()` — closes MQ queue and queue manager

---

## 11. Event Publishing

Events are published to SNS in JSON format. Each event contains:

| Field | Description |
|-------|-------------|
| `workflowId` | Booking workflow ID |
| `eventId` | UUID |
| `timestamp` | UTC LocalDateTime |
| `category` | `system` |
| `type` | `startWorkflow` or `closeRun` |
| `component` | `booking-bridge` |
| `runId` | UUID |
| `status` | `success` or `failure` |
| `tokens` | Map of all tracking tokens |

---

## 12. Data Retention

| Store | TTL | Mechanism |
|-------|-----|-----------|
| DynamoDB `XlogDetail` | 7 days | `expiresOn` TTL attribute |
| Message Register lock | 5 minutes (locked) / 1 second (released) | TTL on Message Register API |
| DynamoDB token (from Auth) | 72,000 seconds after expiry | DynamoDB `ttl` field |

---

*End of document — Booking Bridge Business Rules & Technical Reference*
