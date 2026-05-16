# cloud-sdk-api — Architecture & Design Reference

> **Document generated:** 2026-05-04  
> **Module version:** 1.0.23-SNAPSHOT  
> **Author analysis by:** Claude (Principal Engineer perspective)  
> **Scope:** Full architectural, design, API, and technology analysis

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Module Position in the System](#2-module-position-in-the-system)
3. [Technology Stack & Maven Dependencies](#3-technology-stack--maven-dependencies)
4. [Package & Class Taxonomy](#4-package--class-taxonomy)
5. [Domain-by-Domain Architecture](#5-domain-by-domain-architecture)
   - 5.1 [Database / DynamoDB API](#51-database--dynamodb-api)
   - 5.2 [Messaging API](#52-messaging-api)
   - 5.3 [Storage API](#53-storage-api)
   - 5.4 [Email API](#54-email-api)
   - 5.5 [Notification / Workflow Events API](#55-notification--workflow-events-api)
   - 5.6 [Parameter Store API](#56-parameter-store-api)
   - 5.7 [Elasticsearch API](#57-elasticsearch-api)
   - 5.8 [Config & Credentials API](#58-config--credentials-api)
6. [Key Data Flows](#6-key-data-flows)
7. [Cross-Cutting Design Patterns](#7-cross-cutting-design-patterns)
8. [API Surface Reference](#8-api-surface-reference)
9. [Areas of Excellence](#9-areas-of-excellence)
10. [Areas for Improvement](#10-areas-for-improvement)

---

## 1. Executive Summary

`cloud-sdk-api` is a **pure-abstraction module** — it contains *zero* cloud-provider code. Every type in it is an interface, annotation, enum, or immutable model. Its singular purpose is to define the contract between Mercury microservices and whatever cloud back-end implements those contracts.

This is the **hexagonal architecture's port layer**: the inner hexagon of the application depends on these interfaces; the outer adapters (cloud-sdk-aws) implement them. Downstream services never import AWS SDK types.

```
┌─────────────────────────────────────────────────────────┐
│               Mercury Microservices                     │
│  (commons, service-xyz, …)                              │
│                                                         │
│   import cloud-sdk-api only ──► interfaces / models    │
└────────────────────────┬────────────────────────────────┘
                         │ depends on
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   cloud-sdk-api                         │
│   StorageClient  MessagingClient  NotificationService   │
│   DatabaseRepository  CloudParameterStore  EmailService │
│   (INTERFACES ONLY — no implementation)                 │
└────────────────────────┬────────────────────────────────┘
                         │ implemented by
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  cloud-sdk-aws                          │
│   S3StorageClient  SqsMessagingClient  SnsService  …    │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Module Position in the System

```
mercury-services-commons (parent POM v1.0)
├── cloud-sdk-api          ← YOU ARE HERE
│     No runtime AWS deps; pure Java 17 + Dropwizard core
├── cloud-sdk-aws          ← AWS implementations
│     depends on cloud-sdk-api
├── commons                ← Legacy + shared utilities
│     depends on cloud-sdk-api + cloud-sdk-aws
├── dynamo-client          ← Legacy DynamoDB client
├── email-sender           ← Legacy email
└── ...
```

**Compile-time dependency graph (cloud-sdk-api):**

```
cloud-sdk-api
  ├── io.dropwizard:dropwizard-core:4.0.16
  │     └── (transitively) jackson-databind:2.17.x
  ├── com.fasterxml.jackson.datatype:jackson-datatype-jdk8:2.19.2
  ├── com.fasterxml.jackson.datatype:jackson-datatype-jsr310:2.19.2
  ├── com.google.inject:guice:7.0.0
  ├── org.apache.commons:commons-lang3:3.18.0
  ├── org.projectlombok:lombok:1.18.32  (provided)
  ├── org.slf4j:slf4j-api:2.0.16
  ├── io.searchbox:jest:6.3.1           (temporary — Elasticsearch)
  ├── org.apache.httpcomponents:httpclient:4.5.14
  ├── org.apache.httpcomponents:httpasyncclient:4.1.5
  └── vc.inreach.aws:aws-signing-request-interceptor:0.0.22
```

> **Note:** The Jest + AWS signing interceptor dependencies are flagged as temporary in the POM comment. These should be removed when the Elasticsearch migration to the new client is complete.

---

## 3. Technology Stack & Maven Dependencies

| Technology | Artifact | Version | Role |
|---|---|---|---|
| Java | JDK | 17 | Language, records not yet used |
| Dropwizard Core | `io.dropwizard:dropwizard-core` | 4.0.16 | Config, lifecycle, metrics base |
| Jackson JDK8 | `jackson-datatype-jdk8` | 2.19.2 | Optional<T> JSON support |
| Jackson JSR310 | `jackson-datatype-jsr310` | 2.19.2 | Java 8 date/time JSON support |
| Guice | `com.google.inject:guice` | 7.0.0 | Dependency injection contracts |
| Lombok | `org.projectlombok:lombok` | 1.18.32 | Boilerplate reduction (provided) |
| SLF4J | `slf4j-api` | 2.0.16 | Logging facade |
| Commons Lang3 | `commons-lang3` | 3.18.0 | String/collection utilities |
| Jest (temp) | `io.searchbox:jest` | 6.3.1 | Elasticsearch REST client |
| Apache HttpClient | `httpclient` | 4.5.14 | HTTP transport for Jest |
| AWS Signing Interceptor (temp) | `aws-signing-request-interceptor` | 0.0.22 | AWS SigV4 for Elasticsearch |
| JUnit 5 | `junit-jupiter` | 5.12.2 | Unit testing |
| Mockito | `mockito-junit-jupiter` | 5.17.0 | Mocking |
| AssertJ | `assertj-core` | 3.27.2 | Fluent assertions |

---

## 4. Package & Class Taxonomy

```
com.inttra.mercury.cloudsdk
│
├── Internal.java                         @interface — marks internal-only APIs
│
├── config/
│   ├── CloudHttpClient                   Interface — HTTP client abstraction
│   ├── CloudStorageConfig                Interface — storage config contract
│   ├── CredentialsProvider               Interface — cloud credentials (expiry, token)
│   ├── RegionIdentifier                  Interface — region metadata
│   └── ElasticSearchServiceConfig        Interface — ES config (timeout, retry, auth)
│
├── database/
│   ├── annotations/
│   │   ├── DynamoDbField                 @interface — attribute name mapping
│   │   ├── Table                         @interface — table metadata (billing, capacity)
│   │   └── TTL                           @interface — TTL field marker
│   ├── DatabaseRepository<T,ID>          Interface — full CRUD + batch + query
│   ├── EntityMapper<T,ID>                Interface — entity ↔ attribute map
│   ├── QuerySpec                         Class — query parameters (immutable)
│   ├── EntityId                          Interface — base ID contract
│   ├── CompositeKey<P,S>                 Interface — partition + sort key
│   ├── BillingMode                       Enum — PROVISIONED | PAY_PER_REQUEST
│   ├── CloudAttributeValue               Class — type-safe attribute wrapper
│   └── DynamoSupportException            RuntimeException
│
├── messaging/
│   ├── MessagingClient<T>                Interface — send/receive/delete
│   ├── Listener                          Interface — lifecycle (start/stop)
│   ├── QueueMessage<T>                   Interface — message representation
│   ├── ReceiveMessageOptions             Class — receive params (builder)
│   └── MessagingException                RuntimeException
│
├── storage/
│   ├── StorageClient                     Interface — S3-like CRUD + presign
│   ├── StorageObject                     Interface — object metadata + content
│   ├── StorageObjectTransferManager      Interface — large file upload/download
│   └── StorageClientInitializationException  RuntimeException
│
├── email/
│   ├── EmailService                      Interface — send + templated send
│   ├── MailContent                       Interface — subject/body/attachments
│   ├── TemplateService                   Interface — template processing
│   ├── EmailRequest                      Class — request (builder)
│   ├── EmailSendResult                   Class — result value object
│   ├── EmailResultCollector<T>           Interface — bulk result collector
│   ├── TemplateEmailSender               Interface — template send (legacy)
│   ├── SendEmailException                RuntimeException
│   └── TemplateProcessingException       RuntimeException
│
├── notification/
│   ├── NotificationService               Interface — topic + event lifecycle
│   ├── EventPublisher                    @FunctionalInterface — publish(List<Event>)
│   ├── Event                             Class — workflow event (immutable, builder)
│   ├── MetaData                          Class — workflow metadata (immutable, builder)
│   ├── EventGenerator                    Class — singleton event factory
│   ├── EventLogger                       Class — logs + publishes events
│   ├── WorkflowAware                     Interface — workflow ID hierarchy
│   ├── Annotation                        Class — immutable annotation (type/code/value)
│   ├── Annotations                       Class — annotation collection
│   ├── ErrorHelper                       Class — error annotation factory
│   ├── DateConstants                     Class — date format constants
│   ├── JsonSupport                       Class — Jackson ObjectMapper factory
│   ├── RandomGenerator                   Class — UUID / numeric string
│   └── MultiFormatLocalDateTimeDeserializer  JsonDeserializer
│
├── paramstore/
│   ├── CloudParameterStore               Interface — get/put/describe/replace
│   ├── CloudParameter                    Interface — parameter value object
│   ├── CloudParameterType                Enum — STRING | STRING_LIST | SECURE_STRING
│   ├── ParameterTransformation           Interface — placeholder replacement
│   └── ParameterStoreException           RuntimeException
│
└── elasticsearch/
    ├── JestClientBuilder                 Class — builds Jest client with AWS signing
    └── JestClientRetryHandler            Class — exponential-backoff retry
```

---

## 5. Domain-by-Domain Architecture

### 5.1 Database / DynamoDB API

#### Interface Hierarchy

```
EntityId
  └── CompositeKey<P,S>           partition + sort key pair

EntityMapper<T,ID>                entity ↔ attribute map contract
  └── (impl: ReflectionEntityMapper in cloud-sdk-aws)

DatabaseRepository<T,ID>          full CRUD + batch + query
  └── (impl: DynamoDB-enhanced table in cloud-sdk-aws)
```

#### DatabaseRepository<T, ID> — Full API

```java
// Single operations
Optional<T>  findById(ID id)
Optional<T>  findById(ID id, boolean consistentRead)
List<T>      findAll()
T            save(T entity)
T            update(T entity)
Optional<T>  saveIfNotExist(T entity)
void         delete(T entity)
void         deleteById(ID id)

// Batch operations
List<T>      batchSave(List<T> entities)
List<T>      batchGetByIds(List<ID> ids)
void         batchDelete(List<T> entities)

// Query
List<T>      query(QuerySpec querySpec)
List<T>      export(QuerySpec querySpec)       // full scan/export
List<T>      queryByIndex(QuerySpec querySpec) // GSI/LSI
```

#### QuerySpec — Builder-based Query Abstraction

```
QuerySpec
  ├── tableName         String
  ├── indexName         String (optional — for GSI/LSI)
  ├── partitionKey      Map.Entry<String,Object>
  ├── sortKeyCondition  SortKeyCondition (optional)
  ├── filterExpression  String (optional)
  ├── expressionValues  Map<String,Object>
  ├── limit             int (optional)
  ├── consistentRead    boolean
  └── scanForward       boolean (ascending vs descending)
```

#### CloudAttributeValue — Type-Safe Attribute Wrapper

```
CloudAttributeValue (immutable)
│
├── Static factory:
│   ├── ofString(String)
│   ├── ofNumber(Number)
│   ├── ofBoolean(Boolean)
│   ├── ofList(List<CloudAttributeValue>)
│   ├── ofMap(Map<String,CloudAttributeValue>)
│   ├── ofDate(Date)
│   ├── ofObject(Object)              ← generic via toString()
│   └── ofOffsetDateTime(OffsetDateTime)
│
├── Instance:
│   ├── getType()      → Type enum
│   ├── getString()
│   ├── getNumber()
│   ├── getBoolean()
│   ├── getList()
│   └── getMap()
│
└── Type enum: STRING, NUMBER, BOOLEAN, LIST, MAP, DATE, OFFSET_DATE_TIME
```

#### Annotations

| Annotation | Target | Key Attributes |
|---|---|---|
| `@Table` | Class | `name`, `billingMode`, `readCapacity`, `writeCapacity` |
| `@DynamoDbField` | Field | `attributeName` — maps Java field to DynamoDB attribute |
| `@TTL` | Field | Marks field as DynamoDB TTL attribute |

#### Data Flow: Save Entity

```
Service
  │ entity object
  ▼
DatabaseRepository.save(entity)
  │
  ▼
EntityMapper.toAttributeMap(entity)
  │  @DynamoDbField annotations drive field name resolution
  │  CloudAttributeValue wraps each field value
  ▼
Map<String, CloudAttributeValue>
  │
  ▼ (cloud-sdk-aws converts to AWS AttributeValue)
DynamoDB PutItem / Enhanced Table
```

---

### 5.2 Messaging API

```
MessagingClient<T>
  ├── sendMessage(queueUrl, payload)               → String (messageId)
  ├── sendMessage(queueUrl, payload, attributes)   → String
  ├── deleteMessage(queueUrl, receiptHandle)
  ├── listMessages(queueUrl)                       → List<QueueMessage<T>>
  ├── receiveMessages(ReceiveMessageOptions)        → List<QueueMessage<T>>
  └── getQueueAttributes(queueUrl, attrNames)      → Map<String,String>

QueueMessage<T>
  ├── getMessageId()         → String
  ├── getReceiptHandle()     → String
  ├── getPayload()           → T
  ├── getAttributes()        → Map<String,String>
  └── getSentTimestamp()     → Instant

ReceiveMessageOptions (builder)
  ├── queueUrl               required
  ├── maxMessages            default 1
  ├── visibilityTimeout      seconds
  ├── waitTime               seconds (long-poll)
  └── attributeNames         List<String>

Listener (lifecycle)
  ├── start()
  └── stop()
```

#### Message Flow

```
Producer Service
  │
  │ MessagingClient.sendMessage(url, payload)
  ▼
Queue (SQS)
  │
  │ MessagingClient.receiveMessages(options)
  ▼
Consumer Service
  │
  │ process(message.getPayload())
  │
  │ MessagingClient.deleteMessage(url, receiptHandle)
  ▼
Message deleted from queue
```

---

### 5.3 Storage API

```
StorageClient
│
├── Bucket operations:
│   ├── createBucket(bucketName)
│   ├── deleteBucket(bucketName)
│   ├── listBuckets()                → List<String>
│   └── bucketExists(bucketName)     → boolean
│
├── Object operations:
│   ├── putObject(bucket, key, content, contentType)
│   ├── putObject(bucket, key, content, contentType, metadata)
│   ├── getObject(bucket, key)       → StorageObject
│   ├── deleteObject(bucket, key)
│   ├── listObjects(bucket, prefix)  → List<StorageObject>
│   ├── objectExists(bucket, key)    → boolean
│   └── copyObject(sourceBucket, sourceKey, destBucket, destKey)
│
└── URL operations:
    └── generatePresignedUrl(bucket, key, duration, filename) → URL

StorageObject
  ├── getKey()           → String
  ├── getSize()          → long
  ├── getETag()          → String
  ├── getLastModified()  → Instant
  ├── getMetadata()      → Map<String,String>
  ├── getContent()       → InputStream
  └── getContentType()   → String

StorageObjectTransferManager          (large file operations)
  ├── uploadFile(file, bucket, key)   → CompletableFuture<?>
  └── downloadFile(bucket, key, dest) → CompletableFuture<?>
```

---

### 5.4 Email API

#### New API (preferred)

```
EmailService
  ├── sendEmail(EmailRequest)                    → EmailSendResult
  ├── sendTemplatedEmail(EmailRequest, template) → EmailSendResult
  └── sendTemplateEmail(name, data, request)     → EmailSendResult

EmailRequest (builder)
  ├── to                List<String>
  ├── source            String (from address)
  ├── subject           String
  ├── contentHtml       String
  ├── contentText       String
  └── replyToAddress    String

EmailSendResult (value object)
  ├── messageId         String
  ├── emailAddress      String
  ├── exception         Optional<Exception>
  └── emailRequest      EmailRequest

MailContent
  ├── getSubject()        → String
  ├── getHtmlBody()       → String
  ├── getTextBody()       → String
  └── getAttachments()    → List<Attachment>
```

#### Legacy API (for migration)

```
TemplateEmailSender
  ├── sendTemplateEmail(to, template, data)
  └── sendBulkTemplateEmail(recipients, template, data)

EmailResultCollector<T>
  ├── getFailed()     → List<T>
  └── getSucceeded()  → List<T>
```

---

### 5.5 Notification / Workflow Events API

This is the richest domain in cloud-sdk-api — it defines the Mercury workflow event model.

#### NotificationService

```
NotificationService extends EventPublisher
  ├── createTopic(topicName)                  → String (topicArn)
  ├── subscribe(topicArn, protocol, endpoint) → String (subscriptionArn)
  ├── publish(topicArn, message)
  ├── publish(topicArn, message, subject)
  ├── unsubscribe(subscriptionArn)
  ├── deleteTopic(topicArn)
  └── listTopics()                            → List<String>

EventPublisher (@FunctionalInterface)
  └── publishEvent(List<Event>)
```

#### Event — The Central Workflow Event Model

```
Event (immutable, builder)
  │
  ├── Identity:
  │   ├── workflowId          String (UUID)
  │   ├── parentWorkflowId    String
  │   └── rootWorkflowId      String
  │
  ├── Temporal:
  │   ├── createdAt           LocalDateTime
  │   ├── updatedAt           LocalDateTime
  │   └── closedAt            LocalDateTime
  │
  ├── Classification:
  │   ├── eventType           String
  │   ├── eventSubType        String
  │   └── status              String
  │
  ├── Content:
  │   ├── messages            List<String>
  │   ├── eventContent        Object (arbitrary payload)
  │   └── annotations         Annotations
  │
  └── Tokens:
      ├── Token constants     (WORKFLOW_ID, PARENT_WORKFLOW_ID, ROOT_WORKFLOW_ID, …)
      └── MessageToken consts (file path, component, S3 path, …)
```

#### MetaData — Workflow Processing Metadata

```
MetaData (immutable, builder)
  │
  ├── Required:
  │   ├── bucket              String
  │   ├── fileName            String
  │   └── component           String
  │
  ├── Optional:
  │   ├── exitStatus          String (SUCCESS / FAILURE / SCHEDULED_FOR_RETRY)
  │   ├── workflowId          String
  │   ├── parentWorkflowId    String
  │   ├── rootWorkflowId      String
  │   ├── startedAt           LocalDateTime
  │   └── completedAt         LocalDateTime
  │
  └── Projections (constants):
      FILE_NAME, COMPONENT, BUCKET, S3_PATH, WORKFLOW_ID, EXIT_STATUS, …
```

#### Workflow Event Data Flow

```
Processing Component
  │
  │  (1) Build MetaData
  │  MetaData meta = MetaData.builder()
  │       .bucket("my-bucket").fileName("file.txt")
  │       .component("parser").exitStatus(SUCCESS).build()
  │
  │  (2) Generate Event
  │  Event event = EventGenerator.getInstance()
  │       .createCloseRunEvent(meta)
  │
  │  (3) Log & Publish
  │  EventLogger.logAndPublish(event, eventPublisher)
  ▼
NotificationService.publishEvent(List.of(event))
  │
  ▼ (SNS in cloud-sdk-aws)
SNS Topic → Subscribers (other services, SQS, Lambda, …)
```

#### Annotations Model

```
Annotation (immutable)
  ├── type    String
  ├── code    String
  └── value   String

Annotations
  ├── getAnnotations()              → List<Annotation>
  ├── addAnnotations(annotation)
  └── addAnnotations(List<Annotation>)

ErrorHelper (static factory)
  ├── createError(Exception)        → Annotation
  └── createError(code, message)    → Annotation
```

---

### 5.6 Parameter Store API

```
CloudParameterStore
  ├── getParameter(name)                          → CloudParameter
  ├── getParameter(name, withDecryption)          → CloudParameter
  ├── putParameter(name, value, type)
  ├── putParameter(name, value, type, overwrite)
  ├── replacePlaceholders(text)                   → String
  ├── replacePlaceholders(text, transformation)   → String
  └── describeParameters(filters)                 → List<CloudParameter>

CloudParameter
  ├── getName()            → String
  ├── getValue()           → String
  ├── getType()            → CloudParameterType
  ├── getLastModified()    → Instant
  ├── getVersion()         → long
  └── getArn()             → String

CloudParameterType
  ├── STRING
  ├── STRING_LIST
  ├── SECURE_STRING
  └── UNKNOWN_TO_SDK_VERSION

ParameterTransformation
  └── transform(pattern, parameterStore) → String
```

#### Placeholder Replacement Pattern

```
Input config text:
  "database.url=${awsps:/mercury/prod/db-url}"

CloudParameterStore.replacePlaceholders(text)
  │
  │ regex: \$\{awsps:([^}]+)\}
  ▼
  "database.url=jdbc:mysql://prod.rds.amazonaws.com:3306/mercury"
```

---

### 5.7 Elasticsearch API

```
JestClientBuilder
  └── build(ElasticSearchServiceConfig) → JestClient
        │
        ├── AWS SigV4 signing interceptor (AwsSigner)
        ├── Retry handler (exponential backoff)
        └── HTTP client configuration

JestClientRetryHandler implements HttpRequestRetryHandler
  └── retryRequest(IOException, executionCount, context) → boolean
        │
        └── exponential backoff: 2^n * 100ms, max 3 retries

ElasticSearchServiceConfig
  ├── getEndpoint()          → String
  ├── getRegion()            → String
  ├── getTimeout()           → int (ms)
  ├── getMaxRetries()        → int
  └── isAuthEnabled()        → boolean
```

---

### 5.8 Config & Credentials API

```
CredentialsProvider
  ├── getAccessKeyId()      → String
  ├── getSecretAccessKey()  → String
  ├── getSessionToken()     → Optional<String>
  ├── getExpiration()       → Optional<Instant>
  └── isExpired()           → boolean

RegionIdentifier
  ├── getId()               → String   (e.g., "us-east-1")
  ├── getDisplayName()      → String
  └── getMetadata()         → Map<String,String>

CloudStorageConfig extends CloudHttpClient
  ├── getBucketName()       → String
  ├── getRegion()           → RegionIdentifier
  └── getCredentials()      → CredentialsProvider

CloudHttpClient
  ├── getEndpointOverride() → Optional<URI>  (for LocalStack)
  ├── getConnectionTimeout()→ Duration
  └── getReadTimeout()      → Duration
```

---

## 6. Key Data Flows

### 6.1 Entity Persistence Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Application Service                                            │
│                                                                 │
│  User user = new User("alice", "alice@example.com");            │
│  userRepository.save(user);                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │ DatabaseRepository<User, UserId>.save()
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  EntityMapper<User, UserId>.toAttributeMap(user)                │
│                                                                 │
│  @DynamoDbField("userId")    → CloudAttributeValue.ofString()   │
│  @DynamoDbField("email")     → CloudAttributeValue.ofString()   │
│  @DynamoDbField("createdAt") → CloudAttributeValue.ofDate()     │
└────────────────────────┬────────────────────────────────────────┘
                         │ Map<String, CloudAttributeValue>
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  CloudAttributeValueConverter (cloud-sdk-aws)                   │
│  CloudAttributeValue → software.amazon.awssdk.AttributeValue    │
└────────────────────────┬────────────────────────────────────────┘
                         │ AWS AttributeValue
                         ▼
                    DynamoDB PutItem
```

### 6.2 Workflow Event Publication Flow

```
Component completes work
  │
  ├─► Build MetaData (bucket, file, component, exitStatus)
  │
  ├─► EventGenerator.createCloseRunEvent(meta)
  │       └── stamps timestamps, workflowId, status
  │
  ├─► EventLogger.log(event)
  │       └── SLF4J structured log
  │
  └─► EventPublisher.publishEvent(List.of(event))
          │
          ▼ (SNS implementation)
      SNS.publish(topicArn, event.toJson())
          │
          ▼
      Subscribers receive workflow event
```

### 6.3 Parameter Store Config Resolution

```
Application startup
  │
  ├─► Load raw YAML config (with ${awsps:...} placeholders)
  │
  ├─► CloudParameterStore.replacePlaceholders(yamlText)
  │       │
  │       ├─► Regex scan for ${awsps:/path/to/param}
  │       ├─► SSM.GetParameter("/path/to/param")
  │       └─► Replace placeholder with decrypted value
  │
  └─► Deserialise resolved YAML → ApplicationConfiguration
```

---

## 7. Cross-Cutting Design Patterns

### 7.1 Immutable Value Objects + Builder Pattern

Every model class (`Event`, `MetaData`, `QuerySpec`, `EmailRequest`, `ReceiveMessageOptions`, `CloudAttributeValue`, `Annotation`) is immutable with a static nested `Builder`. This ensures:
- Thread safety without synchronisation
- No accidental mutation between creation and use
- Explicit required vs optional fields (required fields throw in `build()`)

### 7.2 Generic Type Parameters

`DatabaseRepository<T, ID>` and `MessagingClient<T>` use generics to enforce type safety at compile time. Services never cast; the type contract is enforced by the compiler.

### 7.3 Optional for Absence

Nullable return values use `Optional<T>` (`findById`, `getSessionToken`, `getExpiration`). This forces callers to handle the absent case explicitly rather than relying on NPE-prone null checks.

### 7.4 @FunctionalInterface Contracts

`EventPublisher` is a `@FunctionalInterface`, making it trivial to wire lambda-based publishers in tests:
```java
EventPublisher publisher = events -> events.forEach(log::info);
```

### 7.5 Annotation-Driven Metadata

`@Table`, `@DynamoDbField`, `@TTL` drive DynamoDB schema without any XML/YAML configuration files. The schema lives with the entity class.

### 7.6 Marker Annotation for Internal APIs

`@Internal` marks types that are not part of the public contract and may change without notice. This is a documentation signal — enforcement is by convention.

---

## 8. API Surface Reference

### DatabaseRepository<T, ID> — Complete Method Signatures

```java
Optional<T>  findById(ID id);
Optional<T>  findById(ID id, boolean consistentRead);
List<T>      findAll();
T            save(T entity);
T            update(T entity);
Optional<T>  saveIfNotExist(T entity);
void         delete(T entity);
void         deleteById(ID id);
List<T>      batchSave(List<T> entities);
List<T>      batchGetByIds(List<ID> ids);
void         batchDelete(List<T> entities);
List<T>      query(QuerySpec querySpec);
List<T>      export(QuerySpec querySpec);
List<T>      queryByIndex(QuerySpec querySpec);
```

### MessagingClient<T> — Complete Method Signatures

```java
String             sendMessage(String queueUrl, T payload);
String             sendMessage(String queueUrl, T payload, Map<String,String> attributes);
void               deleteMessage(String queueUrl, String receiptHandle);
List<QueueMessage<T>> listMessages(String queueUrl);
List<QueueMessage<T>> receiveMessages(ReceiveMessageOptions options);
Map<String,String> getQueueAttributes(String queueUrl, List<String> attributeNames);
```

### StorageClient — Complete Method Signatures

```java
void          createBucket(String bucketName);
void          deleteBucket(String bucketName);
List<String>  listBuckets();
boolean       bucketExists(String bucketName);
void          putObject(String bucket, String key, InputStream content, String contentType);
void          putObject(String bucket, String key, InputStream content, String contentType, Map<String,String> metadata);
StorageObject getObject(String bucket, String key);
void          deleteObject(String bucket, String key);
List<StorageObject> listObjects(String bucket, String prefix);
boolean       objectExists(String bucket, String key);
void          copyObject(String srcBucket, String srcKey, String dstBucket, String dstKey);
URL           generatePresignedUrl(String bucket, String key, Duration duration, String filename);
```

---

## 9. Areas of Excellence

### Clean Hexagonal Port Definition
The module is a textbook implementation of ports-and-adapters. No implementation leaks through. Downstream services that import only cloud-sdk-api are completely decoupled from AWS.

### Immutable Model Design
`Event`, `MetaData`, `CloudAttributeValue`, and all request/result objects are immutable. This eliminates an entire class of concurrency bugs that plague mutable state in event-driven services.

### Rich Workflow Event Model
The `Event`/`MetaData`/`EventGenerator`/`EventLogger` combination provides a complete, opinionated workflow observability framework. The `Token` and `MessageToken` constants enforce consistent field names across all services.

### Type-Safe Attribute Mapping
`CloudAttributeValue` prevents type confusion in DynamoDB operations. The factory methods (`ofString`, `ofNumber`, etc.) make the type explicit at the call site.

### Excellent Test Framework Selection
JUnit 5, Mockito 5, and AssertJ 3 — the current gold standard for Java unit testing. The versions are up-to-date.

### Annotation-Driven Schema
`@Table`, `@DynamoDbField`, `@TTL` keep the schema co-located with the entity. No separate mapping files to keep in sync.

### Consistent Exception Hierarchy
Each domain has its own typed `RuntimeException` subclass: `DynamoSupportException`, `MessagingException`, `StorageClientInitializationException`, `ParameterStoreException`. This allows precise catch blocks.

---

## 10. Areas for Improvement

### Temporary Dependencies Should Be Removed
The Jest + AWS signing interceptor dependencies are marked `temporary` in comments but are committed production code. They create a transitive dependency on Apache HttpClient 4.x (old, EOL) and a third-party AWS signer. A concrete migration ticket should be created with a deadline.

```xml
<!-- These three should be removed post-ES migration -->
<dependency>io.searchbox:jest:6.3.1</dependency>
<dependency>org.apache.httpcomponents:httpclient:4.5.14</dependency>
<dependency>vc.inreach.aws:aws-signing-request-interceptor:0.0.22</dependency>
```

### @Internal Annotation Has No Enforcement
`@Internal` is just a documentation marker. There is no compiler or lint check preventing consumers from using internal types. Consider using a module-info.java to restrict exports, or at minimum a ArchUnit test.

### `QuerySpec` Has Mutable State Risk
While the class is described as immutable, the presence of `Map<String,Object>` fields for `expressionValues` exposes the internal map if the factory/builder does not defensive-copy. Verify all Maps are `Collections.unmodifiableMap(new HashMap<>(...))`.

### `EventGenerator` is a Singleton Anti-Pattern
`EventGenerator.getInstance()` is a static singleton. This makes testing harder (cannot be injected/mocked) and creates hidden global state. It should be converted to a Guice-injectable singleton `@Singleton`.

### `DateConstants.DEFAULT_DATE_TIME_PATTERN = "yyyy-MM-dd HH:mm:ss.SS"` — Only Two Fractional Digits
`SS` is two fractional second digits in `SimpleDateFormat`. Most systems use `SSS` (milliseconds). This could cause precision loss or parse failures when consuming events from systems that write three fractional digits.

### Legacy Email API Not Deprecated
`EmailResultCollector`, `TemplateEmailSender` are documented as "legacy" but carry no `@Deprecated` annotations. Callers have no IDE signal that they should migrate. Add `@Deprecated(since="...", forRemoval=true)`.

### No Pagination API in StorageClient
`listObjects` returns `List<StorageObject>` — unbounded. For large buckets this is an OOM risk. The interface should support cursor-based pagination (`listObjects(bucket, prefix, continuationToken)`).

### Spring Security Crypto Version 4.2.3 in Parent POM
The parent POM declares `spring.sercurity.crypto.version=4.2.3.RELEASE` (note: typo "sercurity"). This is a very old Spring Security version (2017). The crypto module should be updated to 6.x or replaced with a non-Spring alternative.

### Missing `@NotNull` / `@NonNull` Contracts on Interface Methods
Interface methods (e.g., `findById(ID id)`) do not declare nullability contracts. Adding `@NonNull`/`@Nullable` annotations (Lombok, JetBrains, or Jakarta) would improve IDE support and enable null-flow analysis.
