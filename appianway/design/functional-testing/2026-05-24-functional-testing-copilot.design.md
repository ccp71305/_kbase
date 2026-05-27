# Functional-Testing Module — Design Document

> **Module:** `functional-testing`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury:functional-testing:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Test Framework:** JUnit 4 + Awaitility + AssertJ

---

## 1. Executive Summary

The **Functional-Testing** module is a reusable integration test infrastructure library. It provides in-memory fake implementations of AWS services (S3, SQS, SES, DynamoDB), Dropwizard test lifecycle management, fluent assertion DSLs, and test utilities. All AppianWay modules depend on this for their integration tests, enabling fast local testing without real AWS infrastructure.

---

## 2. Role in the Platform

```mermaid
flowchart LR
    FT["🔷 FUNCTIONAL-TESTING<br/>(Test Library)"]
    
    FT -->|"used by"| D["Dispatcher Tests"]
    FT -->|"used by"| SP["Splitter Tests"]
    FT -->|"used by"| TF["Transformer Tests"]
    FT -->|"used by"| DI["Distributor Tests"]
    FT -->|"used by"| EP["Error-Processor Tests"]
    FT -->|"used by"| ES["Email-Sender Tests"]
    FT -->|"used by"| ING["Ingestor Tests"]
    
    style FT fill:#f1c40f,color:#333
```

---

## 3. Architecture

```mermaid
graph TB
    subgraph "Functional-Testing Library"
        subgraph "Fake AWS Services"
            FS3[FakeS3Impl]
            FSQS[FakeSQSImpl]
            FSES[FakeSESImpl]
            FDDB[FakeDynamoDBImpl]
        end
        
        subgraph "Test Infrastructure"
            ITR[IntegrationTestRule]
            ITS[IntegrationTestSupport]
        end
        
        subgraph "Assertions"
            SA[SqsAssert]
            S3A[S3Assert]
            SNSA[SnsAssert]
            DBA[DynamoDBAssert]
        end
        
        subgraph "Utilities"
            DSL[TestDSL]
            AWAIT[Awaitility Helpers]
        end
    end
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class FakeS3Impl {
        -storage: Map~String, Map~String, byte[]~~
        -metadata: Map~String, ObjectMetadata~
        +putObject(String bucket, String key, InputStream)
        +getObject(String bucket, String key): S3Object
        +doesObjectExist(String bucket, String key): boolean
        +listObjects(String bucket, String prefix): ObjectListing
        +deleteObject(String bucket, String key)
        +clear()
    }

    class FakeSQSImpl {
        -queues: Map~String, Queue~Message~~
        +sendMessage(SendMessageRequest): SendMessageResult
        +receiveMessage(ReceiveMessageRequest): ReceiveMessageResult
        +deleteMessage(DeleteMessageRequest)
        +getQueueUrl(String name): String
        +getMessages(String queueUrl): List~Message~
        +clear()
    }

    class FakeSESImpl {
        -sentEmails: List~SendEmailRequest~
        +sendEmail(SendEmailRequest): SendEmailResult
        +getSentEmails(): List~SendEmailRequest~
        +clear()
    }

    class FakeDynamoDBImpl {
        -tables: Map~String, Map~String, Map~String, AttributeValue~~~
        +putItem(PutItemRequest): PutItemResult
        +getItem(GetItemRequest): GetItemResult
        +updateItem(UpdateItemRequest): UpdateItemResult
        +clear()
    }

    class IntegrationTestRule {
        -application: Application
        -configuration: Configuration
        +before()
        +after()
        +getApplication(): Application
        +getPort(): int
    }

    class IntegrationTestSupport {
        -fakeS3: FakeS3Impl
        -fakeSqs: FakeSQSImpl
        -fakeSes: FakeSESImpl
        -fakeDynamoDB: FakeDynamoDBImpl
        +setUp()
        +tearDown()
        +getS3(): FakeS3Impl
        +getSqs(): FakeSQSImpl
    }

    class SqsAssert {
        -fakeSqs: FakeSQSImpl
        +assertThat(String queue): SqsAssert
        +hasMessages(int count): SqsAssert
        +hasMessageMatching(Predicate): SqsAssert
        +isEmpty(): SqsAssert
    }

    class S3Assert {
        -fakeS3: FakeS3Impl
        +assertThat(String bucket, String key): S3Assert
        +exists(): S3Assert
        +hasContent(String expected): S3Assert
        +hasContentMatching(Predicate): S3Assert
    }

    IntegrationTestSupport --> FakeS3Impl
    IntegrationTestSupport --> FakeSQSImpl
    IntegrationTestSupport --> FakeSESImpl
    IntegrationTestSupport --> FakeDynamoDBImpl
    IntegrationTestRule --> IntegrationTestSupport
```

---

## 5. Fake AWS Service Details

### FakeS3Impl

| Operation | Implementation | Notes |
|-----------|---------------|-------|
| `putObject` | HashMap storage | Stores bytes + metadata |
| `getObject` | HashMap lookup | Returns S3Object wrapper |
| `doesObjectExist` | Key check | O(1) lookup |
| `listObjects` | Prefix filter | Iterates all keys |
| `copyObject` | Internal copy | Same map |
| `deleteObject` | Remove key | Immediate |

### FakeSQSImpl

| Operation | Implementation | Notes |
|-----------|---------------|-------|
| `sendMessage` | Queue add | ConcurrentLinkedQueue |
| `receiveMessage` | Queue poll(N) | Respects maxNumberOfMessages |
| `deleteMessage` | Remove by receipt handle | No visibility timeout simulation |
| `getQueueUrl` | Map lookup | Returns same URL string |

### FakeSESImpl

| Operation | Implementation | Notes |
|-----------|---------------|-------|
| `sendEmail` | List accumulation | Stores entire request |
| `getSentEmails` | Return list | For assertion |

### FakeDynamoDBImpl

| Operation | Implementation | Notes |
|-----------|---------------|-------|
| `putItem` | Nested map storage | Table → PK → attributes |
| `getItem` | Map lookup | By key |
| `updateItem` | ADD/SET expressions | Supports atomic increment |

---

## 6. Integration Test Lifecycle

```mermaid
sequenceDiagram
    participant TEST as Test Method
    participant ITR as IntegrationTestRule
    participant ITS as IntegrationTestSupport
    participant APP as Dropwizard App
    participant FAKES as Fake AWS Services

    Note over ITR: @Rule IntegrationTestRule
    ITR->>ITS: setUp()
    ITS->>FAKES: initialize all fakes
    ITR->>APP: start(testConfig)
    APP-->>ITR: running on random port
    TEST->>FAKES: seed test data (S3 files, etc.)
    TEST->>APP: trigger processing (SQS message)
    TEST->>FAKES: assert results
    Note over TEST: Awaitility.await()...
    ITR->>APP: stop()
    ITR->>ITS: tearDown()
    ITS->>FAKES: clear()
```

---

## 7. Assertion DSL Examples

### SQS Assertions
```java
SqsAssert.assertThat(fakeSqs, "distributor-queue")
    .hasMessages(3)
    .hasMessageMatching(m -> m.contains("rootWorkflowId"));
```

### S3 Assertions
```java
S3Assert.assertThat(fakeS3, "workspace-bucket", "path/to/file.xml")
    .exists()
    .hasContentMatching(c -> c.contains("<BookingRequest>"));
```

### DynamoDB Assertions
```java
DynamoDBAssert.assertThat(fakeDynamoDB, "control-numbers")
    .hasItem("sequence-key")
    .withAttribute("value", "000000005");
```

---

## 8. TestDSL Utilities

| Utility | Purpose |
|---------|---------|
| `TestDSL.metaData()` | Builds MetaData with defaults |
| `TestDSL.sqsMessage(body)` | Creates SQS Message wrapper |
| `TestDSL.s3Event(bucket, key)` | Creates S3 event notification |
| `TestDSL.loadResource(path)` | Reads classpath resource |
| `TestDSL.randomWorkflowId()` | UUID generator |
| `TestDSL.withProjections(...)` | Adds projections to MetaData |

---

## 9. Configuration Details

Test configuration overrides:

| Property | Test Value | Description |
|----------|-----------|-------------|
| `sqsPickupConfig.queueUrl` | `test-pickup` | Fake queue name |
| `sqsDropOffConfig.queueUrl` | `test-dropoff` | Fake queue name |
| `s3WorkspaceConfig.bucket` | `test-bucket` | Fake bucket name |
| `server.applicationConnectors[0].port` | `0` | Random port |
| `logging.level` | `WARN` | Reduce test noise |

---

## 10. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `junit` | 4.13.2 | Test framework |
| `assertj-core` | 3.19.0 | Fluent assertions |
| `awaitility` | 4.x | Async test waiting |
| `mockito-core` | 2.27.0 | Mocking |
| `dropwizard-testing` | 4.0.16 | App test support |
| `mercury-shared` | 1.0 | Shared abstractions |

---

## 11. Design Patterns

| Pattern | Usage |
|---------|-------|
| **Fake Object** | All AWS service implementations |
| **Builder** | TestDSL fluent API |
| **Rule** | JUnit @Rule lifecycle management |
| **Assert Object** | SqsAssert, S3Assert (fluent assertions) |
| **Template** | IntegrationTestSupport base setup |
| **Fixture** | Reusable test data builders |

---

## 12. Usage Pattern (How Modules Use This)

```mermaid
flowchart TD
    subgraph "Module Test (e.g., Dispatcher)"
        TC["DispatcherIntegrationTest"]
        TC -->|"extends"| ITS["IntegrationTestSupport"]
        TC -->|"uses @Rule"| ITR["IntegrationTestRule"]
        TC -->|"seeds"| FS3["fakeS3.putObject(testFile)"]
        TC -->|"triggers"| FSQS["fakeSqs.sendMessage(event)"]
        TC -->|"asserts"| ASR["SqsAssert / S3Assert"]
    end
    
    subgraph "functional-testing module"
        ITS
        ITR
        FS3
        FSQS
        ASR
    end
```

Every integration test:
1. Extends `IntegrationTestSupport` (gets fakes)
2. Declares `IntegrationTestRule` (manages app lifecycle)
3. Seeds input data into fakes
4. Triggers processing (send SQS message)
5. Awaits + asserts output in fakes
