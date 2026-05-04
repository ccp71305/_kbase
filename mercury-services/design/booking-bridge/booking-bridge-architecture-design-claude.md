# Booking Bridge — Architecture & Design Document

**Module:** `booking-bridge`  
**Version:** 1.0  
**Platform:** Mercury Services (Inttra/WiseTech Global)  
**Java Version:** 17  
**Document Date:** 2026-05-04  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [High-Level Architecture Diagram](#3-high-level-architecture-diagram)
4. [Key Classes Reference](#4-key-classes-reference)
5. [Message Processing Pipeline](#5-message-processing-pipeline)
6. [Deduplication Mechanism](#6-deduplication-mechanism)
7. [IBM MQ Routing Logic](#7-ibm-mq-routing-logic)
8. [DynamoDB Table Schemas](#8-dynamodb-table-schemas)
9. [MySQL / Relational Schema Overview](#9-mysql--relational-schema-overview)
10. [SNS Event Publishing Design](#10-sns-event-publishing-design)
11. [Thread Pool Configuration & Concurrency Model](#11-thread-pool-configuration--concurrency-model)
12. [Error Handling & DLQ Design](#12-error-handling--dlq-design)
13. [Guice Dependency Injection Wiring](#13-guice-dependency-injection-wiring)
14. [Configuration Properties Reference](#14-configuration-properties-reference)
15. [Design Patterns Used](#15-design-patterns-used)
16. [Deployment Environments](#16-deployment-environments)

---

## 1. Executive Summary

**Booking Bridge** is a Java microservice within the Mercury Services platform. Its single, well-defined purpose is to act as a **controlled gateway** between the cloud-native booking workflow and the legacy IBM MQ-based back-end system (MIS).

### Business Problem Solved

When a booking request or confirmation is processed in the cloud, downstream legacy systems still depend on receiving an xlog ID via IBM MQ. Without a bridge:

- The same xlog could be delivered to the legacy system multiple times (duplicates).
- There is no observable audit trail of what was delivered and when.
- The legacy system could be flooded with messages it has already handled.

### What Booking Bridge Does

1. **Consumes** inbound booking workflow trigger messages from an AWS SQS queue.
2. **Deduplicates** at two levels: a distributed lock (via Message Register API) and a DynamoDB presence check.
3. **Routes** the xlog ID to the legacy system via IBM MQ (transactional `put` + `commit`).
4. **Persists** a routing record in DynamoDB with a 7-day TTL for audit and idempotency.
5. **Publishes** structured workflow events (start/close) to AWS SNS so that the broader Mercury observability platform can track processing.
6. **Self-heals** IBM MQ connections by looping until a new connection is established on failure.

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Single-consumer SQS listener (`maxNumberOfMessages: 1`) | Prevents race conditions during deduplication without relying solely on the lock |
| Two-layer deduplication (lock + DynamoDB) | Lock prevents concurrent processing; DynamoDB check prevents re-processing after lock release |
| IBM MQ syncpoint transactions | Ensures MQ delivery is atomic; rollback is possible if a later step fails |
| 7-day DynamoDB TTL | Provides a time-bounded audit log without unbounded table growth |
| Guice over Spring | Consistent with the rest of Mercury Services; lightweight DI without classpath scanning overhead |
| Dropwizard lifecycle integration | `ListenerManager` as a `Managed` object ensures clean startup/shutdown of the SQS polling loop |

---

## 2. Technology Stack

### Core Runtime Dependencies

| Artifact | Group ID | Version | Role |
|---|---|---|---|
| `booking-bridge` (this module) | `com.inttra.mercury` | `1.0` | Application module |
| `cloud-sdk-api` | `com.inttra.mercury` | `1.0.21-SNAPSHOT` | Vendor-agnostic cloud abstractions (SQS, SNS, DynamoDB interfaces) |
| `cloud-sdk-aws` | `com.inttra.mercury` | `1.0.21-SNAPSHOT` | AWS SDK v2 implementations of cloud-sdk-api |
| `commons` | `com.inttra.mercury` | `1.0.21-SNAPSHOT` | Shared config, Dropwizard utilities, `InttraServer` |
| `com.ibm.mq.allclient` | `com.ibm.mq` | **9.4.4.1** | IBM MQ Java client (JMS + PCF) |
| `lombok` | `org.projectlombok` | **1.18.32** | Compile-time code generation (`@Data`, `@Builder`, `@Slf4j`) |

### Test Dependencies

| Artifact | Group ID | Version | Scope |
|---|---|---|---|
| `junit-jupiter` | `org.junit.jupiter` | **5.11.3** | Unit & IT test runner |
| `mockito-core` | `org.mockito` | **5.12.0** | Mock object framework |
| `mockito-junit-jupiter` | `org.mockito` | **2.17.0** | Mockito JUnit 5 extension |
| `assertj-core` | `org.assertj` | **3.25.3** | Fluent assertion library |
| `aws-java-sdk-dynamodb` | `com.amazonaws` | **1.12.721** | DynamoDB Local compatibility (test only) |
| `aws-java-sdk-core` | `com.amazonaws` | **1.12.484** | AWS SDK v1 core (test only, DynamoDB Local) |
| `dynamo-integration-test` | `com.inttra.mercury` | `1.0.21-SNAPSHOT` | `BaseDynamoDbIT` base class for integration tests |

### Build Plugins

| Plugin | Version | Purpose |
|---|---|---|
| `maven-shade-plugin` | **3.5.1** | Produces `booking-bridge-1.0.jar` uber-JAR with main class manifest |
| `maven-compiler-plugin` | **3.13.0** | Java 17 compilation (`--release 17`) |
| `maven-surefire-plugin` | **3.2.5** | Runs `**/*Test.java` unit tests |
| `maven-failsafe-plugin` | **3.2.5** | Runs `**/*IT.java` integration tests |
| `maven-dependency-plugin` | **3.6.1** | Copies SQLite native libs for DynamoDB Local |
| `maven-clean-plugin` | **3.0.0** | Cleans build artefacts including `*~` temp files |

### Inherited from Parent POM (`mercury-services`)

| Property | Value |
|---|---|
| `jacoco.plugin.version` | `0.8.11` |
| `dependency-check.version` | `9.2.0` |
| Java source/target (parent default) | 11 (overridden to 17 in this module) |

---

## 3. High-Level Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         BOOKING BRIDGE — SYSTEM CONTEXT                         ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  ┌──────────────────┐        ┌────────────────────────────────────────────────┐
  │  Mercury Booking │        │                BOOKING BRIDGE                  │
  │  Workflow Engine │        │                                                │
  │  (upstream)      │        │  ┌─────────────────────────────────────────┐  │
  │                  │        │  │         SQS Inbound Layer               │  │
  │  Publishes xlog  │        │  │                                         │  │
  │  trigger to SQS  │        │  │  SQSListener (single-threaded loop)     │  │
  └────────┬─────────┘        │  │  Long-poll: 20s, batch-size: 1          │  │
           │                  │  └──────────────┬──────────────────────────┘  │
           │ JSON MetaData    │                 │ QueueMessage<String>         │
           ▼                  │                 ▼                              │
  ┌──────────────────┐        │  ┌─────────────────────────────────────────┐  │
  │  AWS SQS         │        │  │       Processing Layer (8 threads)      │  │
  │  inbound queue   │───────▶│  │                                         │  │
  │                  │        │  │  BookingBridgeProcessorTask             │  │
  │  inttra2_prod_   │        │  │  • Parse MetaData, extract xlogId       │  │
  │  sqs_booking_    │        │  │  • Log START_WORKFLOW event → SNS       │  │
  │  bridge_inbound  │        │  │  • Delegate to BookingBridgeService     │  │
  └──────────────────┘        │  │  • Log CLOSE_WORKFLOW event → SNS      │  │
                              │  └──────────────┬──────────────────────────┘  │
                              │                 │                              │
                              │                 ▼                              │
                              │  ┌─────────────────────────────────────────┐  │
                              │  │        Deduplication Layer              │  │
                              │  │                                         │  │
                              │  │  1. lockMessage("BRIDGE_"+xlogId)       │  │
                              │  │     → POST /network/utility/            │  │
                              │  │         message-register                │  │
                              │  │     → Returns CREATED / DUPLICATE       │  │
                              │  │                                         │  │
                              │  │  2. xlogDetailDao.findByXlogId(xlogId)  │  │
                              │  │     → DynamoDB consistent read          │  │
                              │  │     → Empty = never routed before       │  │
                              │  └──────────────┬──────────────────────────┘  │
                              │                 │ (only if NEW)                │
                              │                 ▼                              │
                              │  ┌─────────────────────────────────────────┐  │
                              │  │          IBM MQ Routing Layer           │  │
                              │  │                                         │  │
                              │  │  MQService.sendToQueue(MQMessage)       │  │
                              │  │  MQService.commit()    [syncpoint]      │  │
                              │  │                                         │  │
                              │  │  Queue: MIS.PICKUP.I                    │  │
                              │  │  Backout: MIS.PICKUP.ERR (threshold 3)  │  │
                              │  └──────────────┬──────────────────────────┘  │
                              │                 │                              │
                              │                 ▼                              │
                              │  ┌─────────────────────────────────────────┐  │
                              │  │          Persistence Layer              │  │
                              │  │                                         │  │
                              │  │  XlogDetailDao.save(XlogDetail)         │  │
                              │  │  • xlogId (PK)                          │  │
                              │  │  • createdDate (epoch seconds)          │  │
                              │  │  • expiresOn (epoch seconds, TTL 7d)    │  │
                              │  └─────────────────────────────────────────┘  │
                              └────────────────────────────────────────────────┘
                                         │                │              │
                                         │                │              │
                                         ▼                ▼              ▼
                              ┌─────────────────┐ ┌──────────────┐ ┌──────────────┐
                              │  AWS DynamoDB   │ │  IBM MQ      │ │  AWS SNS     │
                              │  us-east-1      │ │  QMGR1       │ │  us-east-1   │
                              │                 │ │  host:port   │ │              │
                              │  Table:         │ │  1424        │ │  Topic:      │
                              │  <env>_XlogDetail│ │  MIS.PICKUP.I│ │  inttra2_   │
                              │  TTL: expiresOn │ │              │ │  pr_sns_event│
                              └─────────────────┘ └──────────────┘ └──────────────┘
                                                          │
                                                          ▼
                                                  ┌──────────────┐
                                                  │  Legacy MIS  │
                                                  │  Back-End    │
                                                  │  System      │
                                                  └──────────────┘
```

### Lateral Integration Points

```
                    ┌─────────────────────────────────────────────────┐
                    │            EXTERNAL DEPENDENCIES                │
                    └─────────────────────────────────────────────────┘

  ┌─────────────────────────┐          ┌────────────────────────────────┐
  │   Network Services API  │          │       AWS Parameter Store       │
  │   (api.inttra.com)      │          │                                │
  │                         │          │  /inttra2/prod/mercuryservices/ │
  │  POST /auth             │          │  booking-bridge/authclientsecret│
  │    → Token (JWT)        │          │                                │
  │                         │          │  Resolved at startup by        │
  │  POST /message-register │          │  ParameterStoreLookup          │
  │    → CREATED|DUPLICATE  │          └────────────────────────────────┘
  │                         │
  │  PUT  /message-register │
  │    → UPDATED|INCONSIST. │
  └─────────────────────────┘
```

---

## 4. Key Classes Reference

### Application Bootstrap

| Class | Package | Role / Responsibility |
|---|---|---|
| `BookingBridgeApplication` | `...booking.bridge` | Main entry point; builds `InttraServer`, registers Guice modules, post-setup hooks; starts `ListenerManager` |
| `BookingBridgeConfig` | `...config` | Dropwizard `ApplicationConfiguration` subclass; owns all YAML-bound config including `MQConfig` and `BaseDynamoDbConfig` |
| `BookingBridgeAppLifecycleListener` | `...config` | Jetty `LifeCycle.Listener`; logs startup/shutdown; closes `MQService` on stop; checks executor termination |

### Guice Modules

| Class | Package | Role / Responsibility |
|---|---|---|
| `BookingBridgeApplicationInjector` | `...config` | Primary Guice module; binds `Listener→SQSListener`, `EventPublisher→SNSEventPublisher`; provides `SQSListener` and `MQService` singletons; binds named `ServiceDefinition` instances |
| `BookingBridgeApplicationModule` | `...config` | Creates the `processor` `ThreadPoolExecutor` (8 fixed threads, `SynchronousQueue`, `CallerRunsPolicy`); binds named `ExecutorService` and `Queue` |
| `BookingBridgeMessagingModule` | `...config` | Provides `MessagingClient<String>` (SQS) via `MessagingClientFactory`; provides `NotificationService` (SNS) via `NotificationClientFactory` |
| `BookingBridgeDynamoModule` | `...config` | Provides `DynamoDbClientConfig`; creates `DatabaseRepository<XlogDetail, DefaultPartitionKey<String>>` via `DynamoRepositoryFactory`; provides `XlogDetailDao` |

### Inbound / Processing

| Class | Package | Role / Responsibility |
|---|---|---|
| `Listener` (interface) | `...common.listener` | Contract: `startup()` / `shutdown()` |
| `SQSListener` | `...common.listener` | Infinite long-poll loop; receives batch of `QueueMessage<String>`; delegates to `taskProcessor` BiConsumer; deletes message via callback after successful processing; volatile `interrupted` flag for safe shutdown |
| `ListenerManager` | `...common.listener.support` | Dropwizard `Managed`; submits `SQSListener::startup` to a single-thread executor; calls `shutdown()` on stop |
| `BookingBridgeProcessorTask` | `...inbound` | Submits each message to the `processor` executor; parses `MetaData` JSON; extracts `xlogId` from `MetaData.Projection.XLOG_ID`; calls `BookingBridgeService.routeToDestination()`; handles exceptions by writing to DLQ |

### Business Logic

| Class | Package | Role / Responsibility |
|---|---|---|
| `BookingBridgeService` | `...inbound.service` | Core business logic; acquires lock; checks DynamoDB; routes xlogId to IBM MQ; saves `XlogDetail`; releases lock; handles `MQException` with reconnect loop |

### IBM MQ

| Class | Package | Role / Responsibility |
|---|---|---|
| `MQConfig` | `...mq` | POJO config bean: `hostName`, `port`, `channel`, `userId`, `password`, `queueMgrName`, `queueName`, `backoutQueue`, `backoutThreshold` |
| `MQService` | `...mq` | Wraps IBM MQ API; opens `MQQueueManager` and `MQQueue` at construction; provides `sendToQueue(MQMessage)`, `commit()`, `rollback()`, `close()` |

### AWS / Messaging

| Class | Package | Role / Responsibility |
|---|---|---|
| `SQSClient` | `...common.messaging` | Thin wrapper over `MessagingClient<String>`; adds logging; provides `sendMessage`, `deleteMessage`, `receiveMessage` |
| `SNSClient` | `...common.messaging` | Thin wrapper over `NotificationService`; adds logging; throws `UnrecoverableAWSException` on SNS failure |

### Events / Observability

| Class | Package | Role / Responsibility |
|---|---|---|
| `EventPublisher` (interface) | `...common.event` | Contract: `publishEvent(List<Event>)` |
| `SNSEventPublisher` | `...common.event` | Implements `EventPublisher`; serialises `List<Event>` to JSON; sends to configured SNS topic ARN |
| `EventGenerator` | `...common.event` | Stateless factory for `Event` objects; produces `startWorkflow` events (type=`startWorkflow`) and `closeRun` events (type=`closeRun`); populates token map |
| `EventLogger` | `...common.event` | Orchestrates event lifecycle; calls `EventGenerator`; calls `EventPublisher`; adds `pickupQueue` token |

### Data Access

| Class | Package | Role / Responsibility |
|---|---|---|
| `XlogDetail` | `...model` | `@DynamoDbBean` entity; partition key `xlogId`; `createdDate` and `expiresOn` stored as epoch seconds; 7-day TTL; implements `Expires` interface |
| `XlogDetailDao` | `...dao` | DAO over `DatabaseRepository<XlogDetail, DefaultPartitionKey<String>>`; `save()` and `findByXlogId()` (consistent read) |
| `CreateTables` | `...dynamo` | Dropwizard `Command`; extends `DynamoDbAdminCommand`; creates/idempotently manages DynamoDB tables from entity class annotations |

### Network Services

| Class | Package | Role / Responsibility |
|---|---|---|
| `NetworkServiceClient` | `...networkservices` | HTTP client wrapper; GET/POST/PUT with 3-retry and auto-token-refresh logic; capped exponential backoff |
| `AuthClient` | `...networkservices.auth` | Fetches and caches OAuth2 `Token` from auth service; `synchronized newToken()` guards against concurrent token refresh |
| `AuthUtil` | `...networkservices.auth` | Resolves `clientId`/`clientSecret` from AWS Parameter Store at startup |
| `Token` | `...networkservices.auth` | OAuth2 token model; `isValid()` checks expiry against `InactivityTimeout` or `FixedTimeout` |
| `MessageRegisterService` | `...networkservices.messageRegister` | Distributed lock client; `lockMessage()` → POST with 5-minute TTL; `releaseLock()` → PUT with 1-second TTL |

### Models / Exceptions

| Class | Package | Role / Responsibility |
|---|---|---|
| `RegisterRequest` | `...messageRegister.model` | Lock request payload: `key` + `ttl` |
| `RegisterResponseEnum` | `...messageRegister.model` | Possible lock responses: `CREATED`, `DUPLICATE`, `RETRY`, `UPDATED`, `INCONSISTENT` |
| `InternalException` | `...exceptions` | RuntimeException; thrown when network retries are exhausted |
| `UnrecoverableAWSException` | `...externalwrapper.exception` | Wraps non-retryable AWS errors from SNS |
| `ExternalCallExecutionException` | `...externalwrapper.exception` | General external-call failure |
| `NetworkServicesException` | `...networkservices.exception` | Thrown when all retries to Network Services API fail |
| `Json` | `...util` | Static Jackson utility; `toJsonString`, `fromJsonString`, `fromJsonArrayString`; registers `Jdk8Module`, `JavaTimeModule`; custom `LocalDateTime` deserializer |

---

## 5. Message Processing Pipeline

### End-to-End Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE MESSAGE PROCESSING PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────────────┘

 PHASE 1: INBOUND (ListenerManager thread, single executor)
 ─────────────────────────────────────────────────────────────────────────────────
 ┌──────────────┐    long-poll    ┌──────────────────────────────────────────┐
 │  AWS SQS     │◀───20 seconds──│  SQSListener.pollAndExecute()            │
 │  Queue       │                 │                                          │
 │              │────up to 1 msg─▶│  sqs.receiveMessage(queueUrl, 1, 20s)   │
 └──────────────┘                 │  → List<QueueMessage<String>> messages   │
                                  │                                          │
                                  │  if messages.isEmpty() → loop back       │
                                  │  else → submitMessage(messages)          │
                                  └───────────────────┬──────────────────────┘
                                                      │
                                                      │ BiConsumer.accept(
                                                      │   messages,
                                                      │   deleteCallback)
                                                      ▼

 PHASE 2: ASYNC DISPATCH (processor thread pool — 8 threads)
 ─────────────────────────────────────────────────────────────────────────────────
                                  ┌──────────────────────────────────────────┐
                                  │  BookingBridgeProcessorTask.process()    │
                                  │                                          │
                                  │  executor.submit(() -> execute(          │
                                  │    messages, successCallback))           │
                                  └───────────────────┬──────────────────────┘
                                                      │ (submitted to pool)
                                                      ▼

 PHASE 3: PER-MESSAGE PROCESSING (processor thread)
 ─────────────────────────────────────────────────────────────────────────────────
                                  ┌──────────────────────────────────────────┐
                                  │  execute(QueueMessage<String>, callback) │
                                  │                                          │
                                  │  1. MetaData metaData =                 │
                                  │       Json.fromJsonString(              │
                                  │         message.getPayload(),           │
                                  │         MetaData.class)                 │
                                  │                                          │
                                  │  2. String xlogId =                     │
                                  │       metaData.getProjections()         │
                                  │         .get(XLOG_ID)                   │
                                  │                                          │
                                  │  3. eventLogger                         │
                                  │       .logStartRunEventWithMessage(     │
                                  │           metaData)    ──────────────────┼──▶ SNS
                                  │                                          │
                                  │  4. if (xlogId != null && !blank):      │
                                  │       bookingBridgeService              │
                                  │         .routeToDestination(            │
                                  │             xlogId, tokens)             │
                                  │       success = true                    │
                                  │                                          │
                                  │  [finally block always runs:]           │
                                  │  5. successCallback.accept(message)     │
                                  │       → sqs.deleteMessage(queueUrl,     │
                                  │           message.getReceiptHandle())   │
                                  │                                          │
                                  │  6. eventLogger.logCloseRunEvent(       │
                                  │       metaData, CLOSE_WORKFLOW,         │
                                  │       workflowId, now, success,         │
                                  │       tokens)  ────────────────────────┼──▶ SNS
                                  └───────────────────┬──────────────────────┘
                                                      │ routeToDestination()
                                                      ▼

 PHASE 4: BUSINESS SERVICE (same processor thread)
 ─────────────────────────────────────────────────────────────────────────────────
                                  ┌──────────────────────────────────────────┐
                                  │  BookingBridgeService.routeToDestination │
                                  │                                          │
                                  │  messageKey = "BRIDGE_" + xlogId        │
                                  │                                          │
                                  │  ┌────────────────────────────────────┐ │
                                  │  │ STEP A: Acquire Distributed Lock   │ │
                                  │  │                                    │ │
                                  │  │ registerCreateResponse =           │ │
                                  │  │   messageRegisterService           │ │
                                  │  │     .lockMessage(                  │ │
                                  │  │       messageKey, tokens)          │ │
                                  │  │                                    │ │
                                  │  │ tokens["lockState"] = response     │ │
                                  │  │                                    │ │
                                  │  │ if !CREATED → IGNORED path         │ │
                                  │  └──────────────┬─────────────────────┘ │
                                  │                 │ (CREATED)              │
                                  │                 ▼                        │
                                  │  ┌────────────────────────────────────┐ │
                                  │  │ STEP B: DynamoDB Duplicate Check   │ │
                                  │  │                                    │ │
                                  │  │ xlogDetails =                      │ │
                                  │  │   xlogDetailDao.findByXlogId(      │ │
                                  │  │     xlogId)                        │ │
                                  │  │                                    │ │
                                  │  │ if non-empty && xlogId not blank:  │ │
                                  │  │   tokens["routingStatus"] =        │ │
                                  │  │     "IGNORED"                      │ │
                                  │  │   tokens["ignored"] = "true"       │ │
                                  │  │   → skip to finally (release lock) │ │
                                  │  └──────────────┬─────────────────────┘ │
                                  │                 │ (not found in DynamoDB)│
                                  │                 ▼                        │
                                  │  ┌────────────────────────────────────┐ │
                                  │  │ STEP C: IBM MQ Send                │ │
                                  │  │                                    │ │
                                  │  │ MQMessage mqMessage = new...       │ │
                                  │  │ mqMessage.writeString(xlogId)      │ │
                                  │  │ mqService.sendToQueue(mqMessage)   │ │
                                  │  │ mqService.commit()  ←─ syncpoint   │ │
                                  │  │                                    │ │
                                  │  │ tokens["dropOffQueue"] = queueName │ │
                                  │  │ tokens["routingStatus"] = "ROUTED" │ │
                                  │  │ tokens["ignored"] = "false"        │ │
                                  │  └──────────────┬─────────────────────┘ │
                                  │                 │ (committed)            │
                                  │                 ▼                        │
                                  │  ┌────────────────────────────────────┐ │
                                  │  │ STEP D: DynamoDB Persist           │ │
                                  │  │                                    │ │
                                  │  │ xlogDetailDao.save(                │ │
                                  │  │   XlogDetail.builder()             │ │
                                  │  │     .xlogId(xlogId)               │ │
                                  │  │     .createdDate(now)             │ │
                                  │  │     .expiresOn(now + 7 days)      │ │
                                  │  │     .build())                     │ │
                                  │  └──────────────┬─────────────────────┘ │
                                  │                 │                        │
                                  │                 ▼                        │
                                  │  ┌────────────────────────────────────┐ │
                                  │  │ [finally] STEP E: Release Lock     │ │
                                  │  │                                    │ │
                                  │  │ if (registerCreateResponse):       │ │
                                  │  │   messageRegisterService           │ │
                                  │  │     .releaseLock(messageKey)       │ │
                                  │  │   → PUT /message-register          │ │
                                  │  │     ttl=1s (immediate expiry)      │ │
                                  │  └────────────────────────────────────┘ │
                                  └──────────────────────────────────────────┘

 PHASE 5: MESSAGE ACKNOWLEDGEMENT (SQS delete)
 ─────────────────────────────────────────────────────────────────────────────────
  Message receipt handle → sqs.deleteMessage(queueUrl, receiptHandle)
  → Message removed from queue regardless of routing outcome
  → On exception: message first sent to DLQ, then deleted
```

### SQS Message Payload Structure

```
QueueMessage<String>
├── messageId     : String          (SQS internal ID)
├── receiptHandle : String          (used for deletion)
└── payload       : String (JSON)
      │
      └── MetaData
            ├── workflowId         : String
            ├── parentWorkflowId   : String
            ├── rootWorkflowId     : String
            ├── projections        : Map<Projection, String>
            │      └── XLOG_ID    : String   ← KEY FIELD
            └── (other workflow fields)
```

---

## 6. Deduplication Mechanism

### Overview

Deduplication is implemented in two complementary layers to handle both concurrent processing and historical idempotency:

| Layer | Mechanism | Purpose | Scope |
|---|---|---|---|
| Layer 1 | Distributed lock via Message Register API | Prevent simultaneous processing of the same xlogId by concurrent threads/pods | Transient (5 minute TTL) |
| Layer 2 | DynamoDB presence check | Prevent re-routing of an xlogId that was already successfully delivered | Persistent (7-day TTL) |

### Decision Tree

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DEDUPLICATION DECISION TREE                          │
└─────────────────────────────────────────────────────────────────────────┘

 START: routeToDestination(xlogId, tokens)
   │
   │   messageKey = "BRIDGE_" + xlogId
   │
   ▼
 ┌────────────────────────────────────────────────────────────┐
 │  POST /network/utility/message-register                     │
 │  body: { key: "BRIDGE_<xlogId>", ttl: 300 }               │
 │  (Lock held for 5 minutes if not released sooner)          │
 └───────────────────────┬──────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
       response=CREATED      response=DUPLICATE
       (or RETRY)            (or null/empty/other)
              │                     │
              │                     ▼
              │            tokens["routingStatus"] = "IGNORED"
              │            tokens["ignored"] = "true"
              │            tokens["lockState"] = <response>
              │            ──────────────────────────────────▶ STOP (no MQ send)
              │
              ▼ (CREATED: we own the lock)
 ┌────────────────────────────────────────────────────────────┐
 │  DynamoDB: XlogDetail table                                │
 │  key = DefaultPartitionKey<String>(xlogId)                │
 │  repository.findById(key, consistentRead=true)            │
 └───────────────────────┬──────────────────────────────────┘
                         │
              ┌──────────┴──────────────────┐
              │                             │
       result is empty               result is non-empty
       (never routed)               AND xlogId is not blank
              │                             │
              │                             ▼
              │                  tokens["routingStatus"] = "IGNORED"
              │                  tokens["ignored"] = "true"
              │                  log: "Xlog already routed to mq"
              │                  ────────────────────────────────▶ STOP
              │                  (release lock in finally block)
              │
              ▼ (xlogId not in DynamoDB — proceed to route)
 ┌────────────────────────────────────────────────────────────┐
 │  Route to IBM MQ                                           │
 │  mqService.sendToQueue(MQMessage with xlogId payload)     │
 │  mqService.commit()  ← transactional syncpoint            │
 └───────────────────────┬──────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
          SUCCESS               MQException
              │                     │
              │              handleMQExceptions()
              │              → createNewConnection()
              │                (blocking retry loop,
              │                 60s sleep between attempts)
              │              → throw RuntimeException
              │                (message goes to DLQ)
              │
              ▼
 ┌────────────────────────────────────────────────────────────┐
 │  Persist to DynamoDB                                       │
 │  xlogDetailDao.save(XlogDetail {                          │
 │    xlogId: xlogId,                                        │
 │    createdDate: Date.now(),                               │
 │    expiresOn: now + 7 days (milliseconds truncated)       │
 │  })                                                       │
 └───────────────────────┬──────────────────────────────────┘
                         │
                         ▼
 tokens["routingStatus"] = "ROUTED"
 tokens["ignored"]       = "false"
 tokens["dropOffQueue"]  = "MIS.PICKUP.I"
 tokens["xlogId"]        = xlogId

 ┌────────────────────────────────────────────────────────────┐
 │  [FINALLY — always executes if lock was acquired]          │
 │  messageRegisterService.releaseLock(messageKey)            │
 │  PUT /message-register { key: "BRIDGE_<xlogId>", ttl: 1 } │
 │  → response UPDATED or INCONSISTENT = success             │
 └────────────────────────────────────────────────────────────┘
```

### Lock Key Format

```
messageKey = "BRIDGE_" + xlogId

Examples:
  xlogId = "12345678"      → key = "BRIDGE_12345678"
  xlogId = "XL-2026-00001" → key = "BRIDGE_XL-2026-00001"
```

### Lock Timeout Semantics

| Phase | TTL | Behaviour |
|---|---|---|
| `lockMessage` (acquire) | 300 seconds (5 minutes) | Key expires automatically if process crashes before releasing |
| `releaseLock` (release) | 1 second | Key is set to expire in 1 second — effectively an immediate release |

### Why Two Layers?

```
Scenario A: Two concurrent pods receive different SQS messages for the same xlogId
─────────────────────────────────────────────────────────────────────────────────
  Pod 1: BRIDGE_XL123 → CREATED → DynamoDB empty → send to MQ → save → release
  Pod 2: BRIDGE_XL123 → DUPLICATE → IGNORED (Layer 1 catches it)

Scenario B: SQS message redelivered after visibility timeout (first attempt succeeded)
─────────────────────────────────────────────────────────────────────────────────
  Attempt 1: BRIDGE_XL123 → CREATED → MQ sent → DynamoDB saved → lock released
  Attempt 2: BRIDGE_XL123 → CREATED (lock free now) → DynamoDB NOT empty → IGNORED
                                                        (Layer 2 catches it)
```

---

## 7. IBM MQ Routing Logic

### Connection Topology

```
┌────────────────────────────────────────────────────────────────┐
│                    IBM MQ CONNECTION SETUP                     │
│                (performed once at application startup)         │
└────────────────────────────────────────────────────────────────┘

  MQEnvironment.hostname = mqConfig.hostName    (e.g., 172.17.2.36)
  MQEnvironment.channel  = mqConfig.channel     (JAVA_CHANNEL1)
  MQEnvironment.port     = mqConfig.port        (1424)
  MQEnvironment.userID   = mqConfig.userId
  MQEnvironment.password = mqConfig.password

  MQQueueManager mqMgr = new MQQueueManager(mqConfig.queueMgrName)  ← QMGR1
       │
       └─▶ mqMgr.accessQueue(
                 mqConfig.queueName,         ← MIS.PICKUP.I
                 OPEN_OPTIONS_FOR_PUT,        ← MQOO_INPUT_AS_Q_DEF | MQOO_OUTPUT
                 null, null, null)
                 → MQQueue queue

  Connection string logged:
  "172.17.2.36:1424/QMGR1/JAVA_CHANNEL1/MIS.PICKUP.I successfully opened to put"
```

### Message Put Flow

```
┌────────────────────────────────────────────────────────────────┐
│                     IBM MQ MESSAGE PUT                         │
└────────────────────────────────────────────────────────────────┘

  MQMessage mqMessage = new MQMessage();
  mqMessage.writeString(xlogId);           ← payload is the raw xlogId string
       │
       ▼
  MQPutMessageOptions pmo = new MQPutMessageOptions();
  // NOTE: MQPMO_SYNCPOINT flag is currently NOT set in pmo.options
  // (the constant PUT_OPTIONS = MQPMO_SYNCPOINT is defined but not applied)
  queue.put(mqMessage, pmo);
       │
       ▼
  mqMgr.commit();   ← syncpoint commit on the queue manager
```

### Open Options Breakdown

| Constant | Hex Value | Meaning |
|---|---|---|
| `MQOO_INPUT_AS_Q_DEF` | `0x00000001` | Open for input using queue default |
| `MQOO_OUTPUT` | `0x00000010` | Open for output (put) |
| `OPEN_OPTIONS_FOR_PUT` | `MQOO_INPUT_AS_Q_DEF \| MQOO_OUTPUT` | Both input and output (used for this queue) |
| `GET_OPTIONS` | `MQGMO_SYNCPOINT` | Get under syncpoint (used if reading) |

### Backout Configuration

| Property | QA / INT Value | Production Value |
|---|---|---|
| `backoutQueue` | `MIS.PICKUP.ERR` | `MIS.PICKUP.ERR` |
| `backoutThreshold` | `3` | `3` |

> Note: `backoutQueue` and `backoutThreshold` are configured in `MQConfig` and YAML, but the current `MQService` implementation does not programmatically set these on the queue/message. These values are intended for the IBM MQ queue manager's own backout handling policy.

### MQ Error Recovery

```
MQException thrown during sendToQueue() or commit()
       │
       ▼
  handleMQExceptions(MQException, MQConfig):
       │
       │  log: "reasoncode: <mqex.reasonCode>"
       │
       ▼
  mqService = createNewConnection(configuration):
       │
       └── while(!stop):
               try:
                 mqService = new MQService(configuration)  ← blocks until success
                 break
               catch Exception:
                 log: "Retry for new connection in ms: 60000"
                 Thread.sleep(60_000)   ← 1 minute between retries
                 (InterruptedException is caught but ignored)
       │
       ▼
  throw RuntimeException(mqException)  ← caller sends to DLQ
```

### Queue Manager Lifecycle

```
Startup:  MQService(MQConfig) constructor → connects to QMGR, opens queue
Running:  sendToQueue() + commit() per message
Shutdown: BookingBridgeAppLifecycleListener.lifeCycleStopped()
          → mqService.close()
               → if (queue.isOpen())  queue.close()
               → if (mqMgr.isOpen())  mqMgr.close()
```

---

## 8. DynamoDB Table Schemas

### Overview

The service manages **one** DynamoDB table. Table names are prefixed with the environment string configured in `dynamoDbConfig.environment`.

### Table: XlogDetail

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         TABLE: <env>_XlogDetail                           │
│  Naming pattern: {dynamoDbConfig.environment} + "_" + "XlogDetail"       │
│                                                                           │
│  Examples by environment:                                                 │
│    INT:  inttra_int_booking_XlogDetail                                   │
│    QA:   inttra2_qa_booking_XlogDetail                                   │
│    PROD: inttra2_prod_booking_XlogDetail                                 │
└───────────────────────────────────────────────────────────────────────────┘

PARTITION KEY
  Attribute : xlogId
  Type      : String (S)
  Annotation: @DynamoDbPartitionKey

SORT KEY
  None (single-dimension table)

GLOBAL SECONDARY INDEXES
  None

LOCAL SECONDARY INDEXES
  None

ATTRIBUTES
┌──────────────┬─────────┬────────────────────────────────────────────────┐
│ Attribute    │ DDB Type│ Notes                                          │
├──────────────┼─────────┼────────────────────────────────────────────────┤
│ xlogId       │ S       │ Partition key. Raw xlog ID from booking system  │
│ createdDate  │ N       │ Unix epoch seconds (DateEpochSecondConverter)   │
│ expiresOn    │ N       │ Unix epoch seconds; DynamoDB TTL attribute      │
└──────────────┴─────────┴────────────────────────────────────────────────┘

TTL CONFIGURATION
  TTL Attribute   : expiresOn
  TTL Annotation  : @TTL(name = "expiresOn") on XlogDetail.expiresOn field
  TTL Duration    : 7 days from routing time
  TTL Precision   : Milliseconds truncated to whole seconds before storage
                    (setExpiresOn strips sub-second precision)

PROVISIONED THROUGHPUT (from config.yaml)
  readCapacityUnits  : 25
  writeCapacityUnits : 25
  sseEnabled         : false

READ CONSISTENCY
  findByXlogId() : consistentRead = true
                   (strong consistency to detect duplicates reliably)
  Default client : consistentRead = false
                   (eventual consistency for other operations)

ITEM LIFECYCLE
  Write  : On first successful MQ routing (after MQ commit succeeds)
  Expiry : DynamoDB auto-deletes after expiresOn epoch passes
  Access : Point lookup by xlogId only (no scan operations enabled)

SAMPLE ITEM
{
  "xlogId":      { "S": "XLOG-12345-ABC" },
  "createdDate": { "N": "1746345600" },      ← May 4 2026 00:00:00 UTC
  "expiresOn":   { "N": "1746950400" }       ← May 11 2026 00:00:00 UTC
}
```

### DynamoDB Entity Annotations Summary

```java
@Table(name = "XlogDetail")                 // cloud-sdk: logical table name
@DynamoDbBean                               // AWS SDK v2: marks as mapped entity
@TTL(name = "expiresOn")                    // cloud-sdk: TTL attribute
public class XlogDetail implements Expires {

    @DynamoDbPartitionKey                   // AWS SDK v2: partition key
    String xlogId;

    @DynamoDbConvertedBy(                   // AWS SDK v2: attribute converter
        DateEpochSecondAttributeConverter.class)
    Date createdDate;

    @TTL(name = "expiresOn")               // cloud-sdk: TTL marker
    @DynamoDbConvertedBy(
        DateEpochSecondAttributeConverter.class)
    Date expiresOn;
}
```

### Table Creation Command

```
$ java -jar booking-bridge-1.0.jar create-tables config.yaml
```

Implemented in `CreateTables extends DynamoDbAdminCommand<BookingBridgeConfig>`:
- Reads `dynamoDbConfig` from YAML
- Calls `dynamoConfig.toClientConfigBuilder().consistentRead(false).build()`
- Uses cloud-sdk's `DynamoDbAdminCommand` to create tables from entity class list: `[XlogDetail.class]`
- Configures TTL on `expiresOn` attribute automatically from `@TTL` annotation
- Operation is idempotent (no-op if table already exists)

---

## 9. MySQL / Relational Schema Overview

**Booking Bridge does not own or interact with any MySQL or relational database.**

The service's persistence layer is exclusively DynamoDB (one table: `XlogDetail`). The xlog data itself lives in upstream Inttra systems; booking-bridge only stores a routing-tracking record in DynamoDB.

The legacy IBM MQ system that receives the xlogId may internally persist in a relational database, but that is outside the scope and knowledge of booking-bridge.

---

## 10. SNS Event Publishing Design

### Purpose

Every message processing run produces two SNS events that feed the Mercury platform's workflow observability infrastructure:

1. **START_WORKFLOW event** — published as soon as a message is dequeued and parsed.
2. **CLOSE_RUN event** — published after processing completes (success or failure).

### Event Types

| Event `type` field | Published When | `subType` |
|---|---|---|
| `startWorkflow` | Message received from SQS, MetaData parsed | none |
| `closeRun` | Processing finished (success or failure) | `CLOSE_WORKFLOW` |

### Token Map Structure

The `tokens` map is a `Map<String, String>` that accumulates key-value pairs throughout processing and is embedded in the close event:

| Token Key (Constant) | Value on ROUTED | Value on IGNORED (lock) | Value on IGNORED (DynamoDB) | Value on ERROR |
|---|---|---|---|---|
| `TOKEN_XLOG_ID` = `"xlogId"` | the xlogId | the xlogId | the xlogId | the xlogId |
| `TOKEN_LOCK_STATE` = `"lockState"` | `"CREATED"` | `"DUPLICATE"` (or other) | `"CREATED"` | varies |
| `TOKEN_ROUTING_STATUS` = `"routingStatus"` | `"ROUTED"` | `"IGNORED"` | `"IGNORED"` | not set |
| `TOKEN_IGNORED` = `"ignored"` | `"false"` | `"true"` | `"true"` | not set |
| `DROP_OFF_QUEUE` = `"dropOffQueue"` | `"MIS.PICKUP.I"` | not set | not set | not set |
| `TOKEN_DLQ` = `"dlq"` | not set | not set | not set | `"<queueUrl>_dlq"` |
| `"pickupQueue"` | `inQueueUrl` | `inQueueUrl` | `inQueueUrl` | `inQueueUrl` |

### Event Object Structure

```
Event (from cloud-sdk-api)
├── workflowId         : String  (from MetaData)
├── parentWorkflowId   : String  (from MetaData)
├── rootWorkflowId     : String  (from MetaData)
├── eventId            : String  (UUID generated by EventGenerator)
├── eventTimestamp     : LocalDateTime (UTC)
├── category           : String  = "system"
├── component          : String  = "booking-bridge"
├── type               : String  = "startWorkflow" | "closeRun"
├── subType            : String  = null | "closeWorkflow"
├── runId              : String  (UUID for start; workflowId for close)
├── runTag             : String  = "booking-bridgeRun" (close event only)
├── status             : String  = "success" | "failure"
├── startTimestamp     : LocalDateTime
├── endTimestamp       : LocalDateTime (close event only)
├── eventContent       : String  (JSON of MetaData)
├── pickupMessage      : String  (JSON of MetaData, start event only)
└── tokens             : Map<String, String>
```

### Publishing Flow

```
EventLogger.logStartRunEventWithMessage(metaData)
       │
       ├── EventGenerator.getStartWorkflowEvent(
       │     metaData, UUID.randomUUID(), Json.toJsonString(metaData),
       │     "booking-bridge", inQueueUrl)
       │     → Event (type="startWorkflow", status="success")
       │
       └── EventPublisher.publishEvent([event])
               │
               └── SNSEventPublisher.publishEvent([event])
                       │
                       └── SNSClient.sendMessage(topicArn,
                             Json.toJsonString([event]))
                                   │
                                   └── NotificationService.publish(topicArn, json)
                                             │
                                             └── AWS SNS → Topic fans out
                                                   to subscribers
                                                   (e.g., Mercury event store,
                                                    dashboard, alerting)

EventLogger.logCloseRunEvent(metaData, CLOSE_WORKFLOW, workflowId,
                              now, success, tokens)
       │
       ├── EventGenerator.getCloseRunEvent(...)
       │     → Event (type="closeRun", subType="closeWorkflow",
       │              status="success"|"failure", tokens=tokens)
       │
       └── EventPublisher.publishEvent([event])
               └── (same SNS publish chain as above)
```

### SNS Topic ARN by Environment

| Environment | SNS Topic ARN |
|---|---|
| INT | `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event` |
| QA | `arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event` |
| PROD | `arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event` |

### Error Handling in SNS Publishing

`SNSClient.sendMessage()` catches all exceptions and throws `UnrecoverableAWSException`. `SNSEventPublisher.publishEvent()` wraps the call in a try-catch and logs `SNS_Failed_AFTER_RETRY: <json>` — the failure does **not** propagate to the caller, meaning SNS failures are logged but do not affect message routing success/failure or DLQ placement.

---

## 11. Thread Pool Configuration & Concurrency Model

### Thread Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONCURRENCY ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

THREAD 1: ListenerManager executor (Executors.newSingleThreadExecutor())
──────────────────────────────────────────────────────────────────────────────
  Name:     single-thread, not named by the service
  Count:    1
  Role:     Runs SQSListener.startup() in a tight loop
  Blocking: Long-polling SQS (blocks up to 20 seconds per poll)
  Shutdown: sqsListener.shutdown() sets interrupted=true → loop exits

THREADS 2–9: "processor" ThreadPoolExecutor (BookingBridgeApplicationModule)
──────────────────────────────────────────────────────────────────────────────
  Name prefix:  "processor"
  Pool size:    fixed 8 (minThreads=8, maxThreads=8)
  Keep-alive:   0 seconds (threads don't idle)
  Work queue:   SynchronousQueue (zero capacity — no buffering)
  Overflow:     CallerRunsPolicy (SQS listener thread runs the task itself
                if all 8 processor threads are busy)
  Shutdown:     Dropwizard-managed, 30-second graceful shutdown

  Each submitted task:
  → BookingBridgeProcessorTask.execute(List<QueueMessage>, callback)
  → Iterates messages (1 per poll due to config)
  → Calls routeToDestination() synchronously on this thread
```

### Executor Configuration Detail

```
environment.lifecycle().executorService("processor")
  .minThreads(8)                                   // core pool size
  .maxThreads(8)                                   // max pool size (fixed)
  .keepAliveTime(Duration.seconds(0))              // no idle timeout
  .workQueue(new SynchronousQueue<>())             // handoff queue
  .shutdownTime(Duration.seconds(30))              // graceful drain time
  .rejectedExecutionHandler(
    new ThreadPoolExecutor.CallerRunsPolicy())     // back-pressure
  .build()
```

### Concurrency Model: Why This Design?

```
SQSListener receives 1 message at a time (maxNumberOfMessages=1)
       │
       │ taskProcessor.accept(messages, deleteCallback)
       │
       ▼
ProcessorTask.process() → executor.submit(task)
       │
       ├── If a processor thread is free: task runs on that thread
       │
       └── If all 8 threads are busy:
               SynchronousQueue handoff fails immediately
               → CallerRunsPolicy: SQS listener thread runs the task
               → SQS listener is blocked during this execution
               → No new messages polled until task completes
               → Natural back-pressure without unbounded queuing
```

### Shutdown Sequence

```
Dropwizard stop signal received
       │
       ├── ListenerManager.stop()
       │     ├── sqsListener.shutdown()  → interrupted=true
       │     └── executor.shutdown()     → single listener thread stops
       │
       └── BookingBridgeAppLifecycleListener.lifeCycleStopped()
             ├── Logs managed object states
             ├── Checks: processorExecutorService.isTerminated()
             │     (logs error if not terminated within 30s)
             └── mqService.close()
                   ├── queue.close()
                   └── mqMgr.close()
```

---

## 12. Error Handling & DLQ Design

### Exception Taxonomy

```
Exception Hierarchy
├── RuntimeException
│     ├── InternalException          — network retries exhausted (NetworkServiceClient)
│     ├── UnrecoverableAWSException  — SNS publish failure (not retried, only logged)
│     └── RuntimeException           — wraps MQException or generic Exception
│                                      in BookingBridgeService (triggers DLQ flow)
├── NetworkServicesException         — all GET retries exhausted
├── MQException (IBM)                — IBM MQ error; triggers reconnection loop
└── UncheckedIOException             — JSON parse failures (from Json utility)
```

### Error Handling Decision Matrix

| Exception | Origin | Handling Strategy | Outcome |
|---|---|---|---|
| `UncheckedIOException` (JSON parse) | `Json.fromJsonString()` in ProcessorTask | Caught by outer try-catch → DLQ | Message moved to DLQ |
| `NullPointerException` / `IllegalArgumentException` | MetaData extraction | Caught by outer try-catch → DLQ | Message moved to DLQ |
| `InternalException` | `NetworkServiceClient` lock/release | Caught by `routeToDestination` catch block → throw RuntimeException | DLQ |
| `MQException` | `MQService.sendToQueue` / `commit` | `handleMQExceptions()` → reconnect loop → throw RuntimeException | DLQ |
| Generic `Exception` in `routeToDestination` | Any service call | Caught → throw RuntimeException | DLQ |
| `UnrecoverableAWSException` | `SNSClient.sendMessage()` | Caught by `SNSEventPublisher` → logged only | Event lost, message continues |
| `WebApplicationException` | `NetworkServiceClient` | Thrown (408, 500) or handled (401=retry, 404=null) | Varies |

### DLQ Mechanism

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DLQ ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────────┘

DLQ URL Convention:
  dlq = inQueueUrl + "_dlq"

  Example (PROD):
  inQueueUrl = "https://queue.amazonaws.com/642960533737/
                inttra2_pr_sqs_booking_bridge_inbound"
  dlqUrl     = "https://queue.amazonaws.com/642960533737/
                inttra2_pr_sqs_booking_bridge_inbound_dlq"

  Note: This is a naming convention maintained by the application.
        The DLQ queue must be pre-provisioned in AWS.

DLQ Flow:
  exception caught in execute()
       │
       ├── log.error("Error processing message: {}", e.getMessage(), e)
       │
       ▼
  exceptionHandler(message, exception, tokens):
       │
       ├── log.info("Moving SQS Message: {} to DLQ {}", messageId, dlq)
       │
       ├── sqsClient.sendMessage(dlqUrl, message.getPayload())
       │     → MessagingClient.sendMessage(dlqUrl, payload)
       │     → If sendMessage fails: log.error (swallowed, not re-thrown)
       │
       └── tokens.put("dlq", dlqUrl)

  [finally block]
       └── successCallback.accept(message)
             → sqs.deleteMessage(inQueueUrl, receiptHandle)
             → Original message deleted from inbound queue
             (whether DLQ send succeeded or not)
```

### Network Service Retry Policy

```
NetworkServiceClient retry behaviour:

  POST (lock/release):
    max 3 attempts (hardcoded loop `for (int i = 0; i < 3; i++)`)
    NotAuthorizedException → authClient.newToken() and retry
    ProcessingException (socket timeout) → retry
    ServerErrorException → retry
    NotFoundException → retry
    WebApplicationException (other) → rethrow immediately
    Exhausted → throw InternalException

  PUT:
    max 3 attempts (MAX_RETRIES constant = 3)
    401 → newToken() + retry
    404 → return null
    other → rethrow WebApplicationException
    Exhausted → throw WebApplicationException

  GET:
    max 3 attempts
    NotAuthorizedException → newToken() and retry
    NotFoundException → return Optional.empty()
    Exhausted → throw NetworkServicesException
```

---

## 13. Guice Dependency Injection Wiring

### Module Registration Order

```
InttraServer.newServer()
  .moduleGenerator(BookingBridgeApplicationInjector::generator)      ← Module 1
  .moduleGenerator((c,e) -> new BookingBridgeApplicationModule(e))   ← Module 2
  .moduleGenerator((c,e) -> new BookingBridgeMessagingModule(c))     ← Module 3
  .moduleGenerator((c,e) -> new BookingBridgeDynamoModule(c, e))     ← Module 4
```

### Complete Binding Graph

```
╔══════════════════════════════════════════════════════════════════════════╗
║               GUICE BINDING GRAPH — BOOKING BRIDGE                      ║
╚══════════════════════════════════════════════════════════════════════════╝

MODULE 1: BookingBridgeApplicationInjector
────────────────────────────────────────────────────────────────────────────
  bind(Listener.class)             → SQSListener.class
  bind(EventPublisher.class)       → SNSEventPublisher.class

  Named bindings (from config.serviceDefinitions):
  bind(ServiceDefinition.class)
    @Named("auth")                 → authServiceDefinition instance
  bind(ServiceDefinition.class)
    @Named("message-register")     → msgRegisterDefinition instance

  @Provides @Singleton
  SQSListener sqsListener(SQSClient, BookingBridgeProcessorTask):
    → new SQSListener(sqsClient, waitTimeSeconds, maxNumberOfMessages,
                      inQueueUrl, processorTask::process)

  @Provides @Singleton
  MQService provideMQService():
    → new MQService(bookingBridgeConfig.getMqConfig())
    → connects to IBM MQ at construction time

MODULE 2: BookingBridgeApplicationModule
────────────────────────────────────────────────────────────────────────────
  SynchronousQueue processorWorkQueue = new SynchronousQueue<>()

  ExecutorService processorExecutor =
    environment.lifecycle().executorService("processor")
      .minThreads(8).maxThreads(8)
      .keepAliveTime(Duration.seconds(0))
      .workQueue(processorWorkQueue)
      .shutdownTime(Duration.seconds(30))
      .rejectedExecutionHandler(CallerRunsPolicy)
      .build()

  bind(Queue.class)
    @Named("processor")            → processorWorkQueue instance
  bind(ExecutorService.class)
    @Named("processor")            → processorExecutor instance

MODULE 3: BookingBridgeMessagingModule
────────────────────────────────────────────────────────────────────────────
  bind(BookingBridgeConfig.class)  → config instance

  @Provides @Singleton
  MessagingClient<String>:
    → MessagingClientFactory.createDefaultStringClient()
    → SqsMessagingClient (AWS SDK v2 SQS)

  @Provides @Singleton
  NotificationService:
    → NotificationClientFactory.createDefaultClient(snsTopicARN)
    → SnsNotificationService (AWS SDK v2 SNS)

MODULE 4: BookingBridgeDynamoModule
────────────────────────────────────────────────────────────────────────────
  bind(BookingBridgeConfig.class)  → config instance
  bind(Environment.class)          → environment instance

  @Provides @Singleton
  DynamoDbClientConfig:
    → config.getDynamoDbConfig()
        .toClientConfigBuilder()
        .consistentRead(false)
        .build()

  @Provides @Singleton
  XlogDetailDao:
    → createPartitionKeyRepository(clientConfig, XlogDetail.class, false)
         → tableName = clientConfig.getTablePrefix() + "XlogDetail"
         → DynamoRepositoryFactory.createEnhancedRepository(...)
         → DatabaseRepository<XlogDetail, DefaultPartitionKey<String>>
    → new XlogDetailDao(repository)

INJECTED SINGLETONS (resolved by Guice):
────────────────────────────────────────────────────────────────────────────
  BookingBridgeConfig           ← bound by MessagingModule + DynamoModule
  SQSClient                     ← injected with MessagingClient<String>
  SNSClient                     ← injected with NotificationService
  AuthClient                    ← injected with Client + @Named("auth") SD
  NetworkServiceClient          ← injected with Client + AuthClient + Config
  MessageRegisterService        ← injected with @Named("message-register") SD + NSC
  EventGenerator                ← @Singleton, Clock.systemUTC()
  EventLogger                   ← injected with EventPublisher + EventGenerator + Config
  XlogDetailDao                 ← provided by DynamoModule
  BookingBridgeService          ← injected with Dao + Logger + Config + MsgReg + MQ
  BookingBridgeProcessorTask    ← injected with Service + Logger + @Named executor + Config + SQS
```

### Dependency Resolution Diagram

```
                        ┌─────────────────────────┐
                        │  BookingBridgeProcessorTask  │
                        └────────────┬────────────┘
                                     │ depends on
               ┌─────────────────────┼──────────────────────────┐
               │                     │                          │
               ▼                     ▼                          ▼
  ┌───────────────────┐  ┌──────────────────┐  ┌───────────────────┐
  │ BookingBridge     │  │ EventLogger       │  │ SQSClient         │
  │ Service           │  │                  │  │                   │
  └──────────┬────────┘  └────────┬─────────┘  └────────┬──────────┘
             │                   │                      │
   ┌─────────┴──────────┐       │ depends on           │ depends on
   │                    │       ▼                      ▼
   ▼                    ▼  ┌──────────────┐  ┌────────────────────┐
┌─────────┐  ┌────────┐    │EventPublisher│  │ MessagingClient    │
│XlogDetail│  │MQService│   │(SNSEventPub) │  │<String> (SQS SDK) │
│ Dao     │  │(IBM MQ) │   └──────┬───────┘  └────────────────────┘
└────┬────┘  └────────┘          │
     │                           ▼
     ▼                    ┌────────────┐
┌────────────────────┐    │ SNSClient  │
│ DatabaseRepository │    └─────┬──────┘
│ (DynamoDB SDK v2)  │          │
└────────────────────┘          ▼
                        ┌─────────────────┐
                        │NotificationService│
                        │(SNS SDK v2)     │
                        └─────────────────┘
             │ also depends on
             ▼
  ┌───────────────────────────┐
  │ MessageRegisterService    │
  └────────────┬──────────────┘
               │
               ▼
  ┌──────────────────────────┐
  │ NetworkServiceClient     │
  └────────────┬─────────────┘
               │
               ▼
  ┌────────────────┐
  │  AuthClient    │
  └────────────────┘
```

---

## 14. Configuration Properties Reference

### Full YAML Configuration Map

```yaml
# ─────────────────────────────────────────────────────────────────────────────
# Dropwizard Server
# ─────────────────────────────────────────────────────────────────────────────
server:
  type: default
  rootPath: /booking-bridge
  applicationContextPath: /
  adminContextPath: /admin
  applicationConnectors:
    - type: http
      port: 8080
  adminConnectors:
    - type: http
      port: 8081

# ─────────────────────────────────────────────────────────────────────────────
# OAuth Token Validation
# ─────────────────────────────────────────────────────────────────────────────
securityResources:
  oauthTokenValidationUri: https://api.inttra.com/auth/validate

# ─────────────────────────────────────────────────────────────────────────────
# External Service Definitions
# ─────────────────────────────────────────────────────────────────────────────
serviceDefinitions:
  - name: auth
    uri: https://api.inttra.com
    clientId: <client-id>
    clientSecret: ${awsps:/inttra2/prod/mercuryservices/booking-bridge/authclientsecret}
  - name: message-register
    uri: https://api.inttra.com/network/utility/message-register

# ─────────────────────────────────────────────────────────────────────────────
# DynamoDB Configuration (BaseDynamoDbConfig)
# ─────────────────────────────────────────────────────────────────────────────
dynamoDbConfig:
  environment: inttra2_prod_booking   # Table prefix: "inttra2_prod_booking_"
  region: us-east-1
  readCapacityUnits: 25
  writeCapacityUnits: 25
  sseEnabled: false
  # endpointOverride: http://localhost:8000  # Local testing only

# ─────────────────────────────────────────────────────────────────────────────
# SQS Inbound Queue
# ─────────────────────────────────────────────────────────────────────────────
inQueueUrl: https://queue.amazonaws.com/642960533737/inttra2_pr_sqs_booking_bridge_inbound

# ─────────────────────────────────────────────────────────────────────────────
# SQS Listener Tuning
# ─────────────────────────────────────────────────────────────────────────────
waitTimeSeconds: 20          # Long polling duration (1–20 seconds; 20=max AWS)
maxNumberOfMessages: 1       # Messages per poll (1–10; 1 minimises race conditions)
listenerEnabled: true        # Set to false to disable SQS polling (e.g., maintenance)

# ─────────────────────────────────────────────────────────────────────────────
# SNS Outbound Topic
# ─────────────────────────────────────────────────────────────────────────────
snsTopicARN: arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event

# ─────────────────────────────────────────────────────────────────────────────
# IBM MQ Connection
# ─────────────────────────────────────────────────────────────────────────────
mqConfig:
  hostName: 172.17.2.36        # IBM MQ broker hostname/IP
  channel: JAVA_CHANNEL1       # MQ channel name (server-connection channel)
  port: 1424                   # MQ listener port
  userId: <user>               # MQ authenticated user
  password: <password>         # MQ user password
  queueMgrName: QMGR1          # Queue Manager name
  queueName: MIS.PICKUP.I      # Target queue for routing
  backoutQueue: MIS.PICKUP.ERR # Backout/dead-letter queue for MQ
  backoutThreshold: 3          # Max redeliveries before backout

# ─────────────────────────────────────────────────────────────────────────────
# Network Service Client Retry Policy
# ─────────────────────────────────────────────────────────────────────────────
maxRetries: 5         # Max HTTP retry attempts (used by BookingBridgeConfig)
maxDelay: 12000       # Max retry delay in milliseconds
baseDelay: 200        # Base retry delay in milliseconds

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging:
  level: ERROR
  loggers:
    "com.inttra.mercury": INFO
    "org.eclipse.jetty": ERROR
    "org.apache.http": ERROR
  appenders:
    - type: console
      logFormat: "%-5p [%t] [%d{yyyy-MM-dd HH:mm:ss.SSS}] [id:%X{ID}] %c: %msg%n"
```

### BookingBridgeConfig Fields

| Field | Type | Default | Constraint | Description |
|---|---|---|---|---|
| `inQueueUrl` | `String` | — | `@NotNull @NotBlank` | SQS queue URL for inbound messages |
| `snsTopicARN` | `String` | — | `@NotNull @NotBlank` | SNS topic ARN for event publishing |
| `mqConfig` | `MQConfig` | — | `@NotNull` | IBM MQ connection parameters |
| `waitTimeSeconds` | `int` | `0` | — | SQS long poll wait (0=short, 1-20=long) |
| `maxNumberOfMessages` | `int` | `0` | — | SQS batch size (1–10) |
| `listenerEnabled` | `boolean` | `true` | — | Toggle SQS listener on/off |
| `maxRetries` | `int` | `3` | `@Max(5)` | Max HTTP retries for network calls |
| `maxDelay` | `int` | `10000` | — | Max backoff delay (ms) |
| `baseDelay` | `int` | `100` | — | Base backoff delay (ms) |
| `dynamoDbConfig` | `BaseDynamoDbConfig` | — | — | DynamoDB client configuration |

### MQConfig Fields

| Field | Type | Constraint | Description |
|---|---|---|---|
| `hostName` | `String` | `@NotNull` | IBM MQ broker IP/hostname |
| `port` | `int` | `@NotNull` | Listener port (default 1424) |
| `channel` | `String` | `@NotNull` | Server-connection channel name |
| `userId` | `String` | — | MQ authenticated user (optional) |
| `password` | `String` | — | MQ user password (optional) |
| `queueMgrName` | `String` | `@NotNull` | Queue Manager name |
| `queueName` | `String` | `@NotNull` | Target queue for xlogId routing |
| `backoutQueue` | `String` | `@NotNull` | MQ-level backout/error queue |
| `backoutThreshold` | `int` | `@NotNull` | Max redeliveries before IBM MQ backsout |

### Environment Comparison

| Property | INT | QA | CVT | PROD |
|---|---|---|---|---|
| AWS Account | `081020446316` | `642960533737` | — | `642960533737` |
| DynamoDB prefix | `inttra_int_booking` | `inttra2_qa_booking` | — | `inttra2_prod_booking` |
| MQ host | `10.1.37.92` | `10.1.37.58` | — | `172.17.2.36` |
| MQ port | `1424` | `1424` | — | `1424` |
| MQ queue | `MIS.PICKUP.I` | `MIS.PICKUP.I` | — | `MIS.PICKUP.I` |
| Auth API | `api-alpha.inttra.com` | `api-beta.inttra.com` | — | `api.inttra.com` |

---

## 15. Design Patterns Used

### 1. Strategy Pattern — `EventPublisher` / `Listener` Interfaces

```
«interface» EventPublisher          «interface» Listener
     │                                    │
     └── SNSEventPublisher                └── SQSListener

Guice binds:
  EventPublisher → SNSEventPublisher  (at startup)
  Listener       → SQSListener        (at startup)
```

Allows alternative implementations (e.g., local file publisher, Kafka listener) to be plugged in without changing business logic.

### 2. Factory Pattern — Cloud SDK Factories

```
MessagingClientFactory.createDefaultStringClient()
  → returns MessagingClient<String> (SqsMessagingClient)

NotificationClientFactory.createDefaultClient(topicArn)
  → returns NotificationService (SnsNotificationService)

DynamoRepositoryFactory.createEnhancedRepository(config, table, class, repoConfig)
  → returns DatabaseRepository<XlogDetail, DefaultPartitionKey<String>>
```

Centralises AWS client construction and configuration; business modules depend only on interfaces.

### 3. Template Method Pattern — `DynamoDbAdminCommand`

```
DynamoDbAdminCommand<C>  (cloud-sdk-aws — abstract base)
  │
  └── CreateTables
        │
        └── @Override resolveClientConfig(BookingBridgeConfig config)
              → returns DynamoDbClientConfig
              
Base class handles: table creation loop, TTL setup, error handling.
Subclass only provides: the DynamoDbClientConfig.
```

### 4. Builder Pattern — `XlogDetail`, `Event`, `DynamoDbClientConfig`

Extensive use of Lombok `@Builder` and fluent builders from cloud-sdk:

```java
XlogDetail.builder()
  .xlogId(xlogId)
  .createdDate(Date.from(Instant.now()))
  .expiresOn(calcExpiresOn())
  .build()
```

### 5. Chain of Responsibility — Exception Handling

```
SQSListener.startup()
  ↓ catch Throwable → log, continue loop
    BookingBridgeProcessorTask.execute()
      ↓ catch Exception → exceptionHandler() → DLQ → finally: delete
        BookingBridgeService.routeToDestination()
          ↓ catch MQException → reconnect loop → throw RuntimeException
          ↓ catch Exception   → throw RuntimeException
```

Each layer catches what it can handle and propagates the rest.

### 6. Decorator / Wrapper Pattern — SQSClient / SNSClient

```
cloud-sdk-api MessagingClient<String>
  wrapped by
SQSClient (adds: logging, RuntimeException wrapping)

cloud-sdk-api NotificationService
  wrapped by
SNSClient (adds: logging, UnrecoverableAWSException wrapping)
```

### 7. Observer / Event Pattern — Workflow Events

```
Processing event occurs (start / close)
       ↓
EventLogger (coordinator)
       ↓
EventGenerator (event factory)
       ↓
EventPublisher (observer notification)
       ↓
SNS Topic → multiple subscribers (observers)
```

### 8. Proxy / Guard Pattern — AuthClient Token Cache

```
synchronized boolean newToken() {
  if (token == null || !token.isValid()) {
    // Only one thread fetches a new token even under concurrent access
    token = fetchFromAuthService();
  }
  return ...;
}
```

Lazy token creation with synchronized guard prevents token stampede.

### 9. Retry Pattern — NetworkServiceClient

```
for (int i = 0; i < 3; i++) {
  try {
    return function.apply(preparedRequest);
  } catch (NotAuthorizedException) { newToken(); }
  catch (ProcessingException) { /* retry */ }
  catch (ServerErrorException) { /* retry */ }
}
throw InternalException("exhausted");
```

Simple count-based retry with token refresh on 401.

### 10. Saga / Compensating Transaction Pattern — Lock + Route + Persist

```
ACQUIRE LOCK       ← "reserve" the work
  ↓
CHECK DUPLICATE    ← guard
  ↓
SEND TO MQ         ← side effect (cannot be undone after commit)
  ↓
PERSIST TO DYNAMO  ← record the side effect
  ↓
RELEASE LOCK       ← always in finally block (compensating: ensures lock is freed)
```

This is a lightweight, non-distributed saga. The lock-in-finally ensures that even on failure, the lock is released and the message goes to DLQ for retry.

---

## 16. Deployment Environments

### Build & Run

```bash
# Build uber-JAR
mvn clean package -pl booking-bridge -am
# Output: booking-bridge/target/booking-bridge-1.0.jar

# Run server
java -jar booking-bridge-1.0.jar server conf/prod/config.yaml

# Create DynamoDB tables (one-time / idempotent)
java -jar booking-bridge-1.0.jar create-tables conf/prod/config.yaml

# Startup memory logging (from main()):
# "Cores available: N"
# "Total max memory the JVM can grow to = X MB"
# "Total memory currently available = Y MB"
```

### Admin Endpoints (Dropwizard)

| Endpoint | Port | Path |
|---|---|---|
| Application | 8080 | `/booking-bridge/*` |
| Admin | 8081 | `/admin/*` |
| Health check | 8081 | `/admin/healthcheck` |
| Metrics | 8081 | `/admin/metrics` |

### AWS IAM Permissions Required

| Service | Action | Resource |
|---|---|---|
| SQS | `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:SendMessage` | Inbound queue + DLQ |
| SNS | `sns:Publish` | Event topic |
| DynamoDB | `dynamodb:PutItem`, `dynamodb:GetItem` | XlogDetail table |
| SSM Parameter Store | `ssm:GetParameter` | `/inttra2/<env>/mercuryservices/booking-bridge/*` |

---

*Document generated: 2026-05-04 by Claude (claude-sonnet-4-6) based on full source code analysis of `booking-bridge` module.*
