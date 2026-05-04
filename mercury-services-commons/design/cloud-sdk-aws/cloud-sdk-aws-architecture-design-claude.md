# cloud-sdk-aws — Architecture & Design Reference

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
   - 5.1 [AWS Configuration & Credentials](#51-aws-configuration--credentials)
   - 5.2 [DynamoDB — Database Implementation](#52-dynamodb--database-implementation)
   - 5.3 [SQS — Messaging Implementation](#53-sqs--messaging-implementation)
   - 5.4 [SNS — Notification Implementation](#54-sns--notification-implementation)
   - 5.5 [S3 — Storage Implementation](#55-s3--storage-implementation)
   - 5.6 [SES v2 — Email Implementation](#56-ses-v2--email-implementation)
   - 5.7 [SSM — Parameter Store Implementation](#57-ssm--parameter-store-implementation)
   - 5.8 [Legacy Guice Modules](#58-legacy-guice-modules)
6. [AWS SDK v2 Migration Status](#6-aws-sdk-v2-migration-status)
7. [HTTP Transport Architecture (Netty Removal)](#7-http-transport-architecture-netty-removal)
8. [Key Data Flows](#8-key-data-flows)
9. [Integration Testing Architecture](#9-integration-testing-architecture)
10. [Areas of Excellence](#10-areas-of-excellence)
11. [Areas for Improvement](#11-areas-for-improvement)

---

## 1. Executive Summary

`cloud-sdk-aws` is the **AWS adapter layer** of the Mercury cloud abstraction. It provides concrete implementations of every interface defined in `cloud-sdk-api` using AWS SDK v2 (with partial AWS SDK v1 legacy code pending migration). It is the **only module in the repository that may import `software.amazon.awssdk.*`** types.

The module has recently undergone a significant architectural decision: **Netty is excluded from all AWS SDK v2 transitive dependencies**. The CRT-based async HTTP client (`aws-crt-client`) is used instead, resolving a known conflict with Dropwizard's embedded Jetty server.

```
┌──────────────────────────────────────────────────────────────┐
│                    cloud-sdk-aws                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ S3StorageClient│  │SqsMessaging  │  │   SnsService     │  │
│  │ (StorageClient)│  │Client        │  │(NotificationSvc) │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────┘  │
│         │                 │                      │          │
│  ┌──────▼─────────────────▼──────────────────────▼───────┐  │
│  │              BaseAwsConfig                            │  │
│  │   credentials · region · httpClient · timeout         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  AWS SDK v2 (2.30.24)                                  │  │
│  │  ssm · sesv2 · s3 · s3-transfer · sns · sqs · dynamo  │  │
│  │  apache-client · aws-crt-client                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Module Position in the System

```
mercury-services-commons (parent POM v1.0)
├── cloud-sdk-api          ← interfaces only (no AWS)
├── cloud-sdk-aws          ← YOU ARE HERE (AWS implementations)
│     ├── depends on: cloud-sdk-api
│     ├── depends on: AWS SDK v2 BOM 2.30.24
│     └── depends on: AWS SDK v1 1.12.730 (temporary)
├── commons                ← depends on cloud-sdk-api + cloud-sdk-aws
└── ...
```

**Dependency graph:**

```
cloud-sdk-aws
  ├── cloud-sdk-api:${dependency.version}
  │
  ├── AWS SDK v2 (via BOM 2.30.24):
  │   ├── software.amazon.awssdk:ssm
  │   ├── software.amazon.awssdk:sesv2
  │   ├── software.amazon.awssdk:s3
  │   ├── software.amazon.awssdk:s3-transfer-manager
  │   ├── software.amazon.awssdk:sns
  │   ├── software.amazon.awssdk:sqs
  │   ├── software.amazon.awssdk:dynamodb
  │   ├── software.amazon.awssdk:dynamodb-enhanced
  │   ├── software.amazon.awssdk:apache-client
  │   ├── software.amazon.awssdk:url-connection-client
  │   ├── software.amazon.awssdk:aws-crt-client  (replaces Netty for async)
  │   ├── software.amazon.awssdk:sso
  │   └── software.amazon.awssdk:ssooidc
  │   [ALL above exclude netty-nio-client]
  │
  ├── AWS SDK v1 (temporary, 1.12.730):
  │   ├── com.amazonaws:aws-java-sdk-core
  │   ├── com.amazonaws:aws-java-sdk-sqs
  │   ├── com.amazonaws:aws-java-sdk-sns
  │   └── com.amazonaws:aws-java-sdk-s3
  │
  ├── com.amazonaws:amazon-sqs-java-extended-client-lib:2.0.4
  ├── io.searchbox:jest:6.3.1                    (ES client, temporary)
  ├── vc.inreach.aws:aws-signing-request-interceptor:0.0.22
  ├── com.github.jknack:handlebars:4.3.1         (email templates)
  ├── com.sun.mail:javax.mail:1.6.2              (email MIME)
  ├── org.yaml:snakeyaml:2.0                     (test)
  └── com.inttra.mercury:dynamo-integration-test  (test)
```

---

## 3. Technology Stack & Maven Dependencies

| Technology | Artifact | Version | Role |
|---|---|---|---|
| Java | JDK | 17 | Language |
| AWS SDK v2 | BOM | 2.30.24 | Cloud services |
| AWS SSM | `software.amazon.awssdk:ssm` | 2.30.24 | Parameter Store |
| AWS SES v2 | `software.amazon.awssdk:sesv2` | 2.30.24 | Email sending |
| AWS S3 | `software.amazon.awssdk:s3` | 2.30.24 | Object storage |
| AWS S3 Transfer | `software.amazon.awssdk:s3-transfer-manager` | 2.30.24 | Large file transfer |
| AWS SNS | `software.amazon.awssdk:sns` | 2.30.24 | Pub/sub notifications |
| AWS SQS | `software.amazon.awssdk:sqs` | 2.30.24 | Message queuing |
| AWS DynamoDB | `software.amazon.awssdk:dynamodb` | 2.30.24 | NoSQL database |
| AWS DynamoDB Enhanced | `software.amazon.awssdk:dynamodb-enhanced` | 2.30.24 | Higher-level DynamoDB API |
| AWS Apache HTTP Client | `software.amazon.awssdk:apache-client` | 2.30.24 | Sync HTTP transport |
| AWS CRT HTTP Client | `software.amazon.awssdk:aws-crt-client` | 2.30.24 | Async HTTP (replaces Netty) |
| AWS SDK v1 | `com.amazonaws:aws-java-sdk-core` | 1.12.730 | Legacy (temporary) |
| SQS Extended Client | `amazon-sqs-java-extended-client-lib` | 2.0.4 | Large SQS messages via S3 |
| Handlebars | `com.github.jknack:handlebars` | 4.3.1 | Email template engine |
| JavaMail | `com.sun.mail:javax.mail` | 1.6.2 | MIME email construction |
| Dropwizard Core | `io.dropwizard:dropwizard-core` | 4.0.16 | Config/lifecycle |
| Lombok | `lombok` | 1.18.32 | Boilerplate (provided) |
| Guice | `com.google.inject:guice` | 7.0.0 | Dependency injection |
| Jest (temp) | `io.searchbox:jest` | 6.3.1 | Elasticsearch client |
| SnakeYAML | `org.yaml:snakeyaml` | 2.0 | Test config parsing |
| JUnit 5 | `junit-jupiter` | 5.12.2 | Testing |
| Mockito | `mockito-junit-jupiter` | 5.17.0 | Mocking |

---

## 4. Package & Class Taxonomy

```
com.inttra.mercury.cloudsdk.aws
│
├── config/
│   ├── AwsCredentialsProviderWrapper     Wraps AwsCredentialsProvider → CredentialsProvider
│   ├── AwsRegionWrapper                  Wraps Region → RegionIdentifier
│   └── BaseAwsConfig (abstract)          Base config for all AWS services
│
└── module/
    ├── AWSConstants                      Pre-built ClientConfiguration instances
    ├── AwsRetryCondition                 Custom retry with logging
    ├── JestModule                        Guice module for Jest (legacy ES client)
    ├── SNSModule                         Guice module for SNS v1 (legacy)
    ├── SQSModule                         Guice module for SQS v1 (legacy)
    └── SQSReader                         Guice module for SQS reader (legacy)

com.inttra.mercury.cloudsdk.database
│
├── annotations/
│   ├── DynamoDBStream                    Stream specification annotation
│   └── GsiConfig                         GSI configuration annotation
│
├── id/
│   ├── DefaultPartitionKey<P>            Single partition key
│   └── DefaultCompositeKey<P,S>          Composite partition+sort key
│
├── config/
│   ├── DynamoRepositoryConfig            DynamoDB repository config
│   ├── SecondaryIndexConfig              GSI/LSI configuration
│   └── TableEncryptionConfig             Table-level encryption config
│
├── converters/
│   ├── CloudAttributeValueConverter      CloudAttributeValue ↔ AWS AttributeValue
│   ├── DateEpochSecondAttributeConverter Date ↔ epoch seconds (DynamoDB)
│   ├── OffsetDateTimeSerializer          OffsetDateTime → JSON string
│   └── OffsetDateTimeTypeConverter       OffsetDateTime ↔ String (DynamoDB)
│
├── ReflectionEntityMapper<T,ID>          Reflection-based EntityMapper impl
├── DynamoDbErrorHandler                  AWS exception → DynamoSupportException
├── DynamoDbKeyExtractor                  Extracts partition/sort keys from entities
└── (DynamoDB repository impls)

com.inttra.mercury.cloudsdk.email
│
├── config/
│   └── AwsSesEmailConfig                 SES v2 client config
│
├── MailContentImpl                        MailContent implementation
├── HandlebarsTemplateServiceImpl          Template processing with Handlebars
├── EmailAttachmentType                    Enum: MIME types for attachments
├── HandlebarsEmailTemplate                Template model for Handlebars
├── AwsJsonEmailTemplate                   Template model for SES JSON templates
│
└── legacy/
    ├── EmailResultCollectorImpl           Bulk result collection
    ├── EmailTemplatesLoader               Load templates from classpath
    ├── HandlebarsTemplateEmailSender      Legacy Handlebars sender
    ├── RawEmailSender                     Raw MIME email sender
    ├── SimpleEmailSender                  Simple text/HTML sender
    ├── EmailMessage                       Legacy email model
    └── EmailMimeUtils                     MIME type utilities

com.inttra.mercury.cloudsdk.messaging
│
├── config/
│   └── AwsMessagingClientConfig          SQS client config
│
├── SqsMessagingClient<T>                 MessagingClient<T> implementation
├── SqsListener                           Listener with startup/shutdown
└── SqsMessage<T>                         QueueMessage<T> implementation

com.inttra.mercury.cloudsdk.notification
│
├── config/
│   └── NotificationClientConfig          SNS client config
│
├── factory/
│   └── NotificationClientFactory         Creates SnsService instances
│
├── SnsService                            NotificationService implementation
├── SnsEventPublisher                     EventPublisher → SNS
└── SnsExceptionHandler                   AWS SNS exceptions → typed exceptions

com.inttra.mercury.cloudsdk.paramstore
│
├── config/
│   └── AwsParameterStoreConfig           SSM client config
│
├── factory/
│   └── ParameterStoreClientFactory       Creates CloudParameterStore instances
│
├── SsmParameter                          CloudParameter implementation
├── SsmParameterTransformation            ${awsps:...} placeholder resolver
└── Main                                  CLI entry point

com.inttra.mercury.cloudsdk.storage
│
├── config/
│   └── AwsStorageConfig                  S3 client config
│
├── factory/
│   ├── S3ClientFactory                   Creates S3Client instances
│   ├── StorageClientFactory              Creates S3StorageClient instances
│   └── TransferManagerFactory            Creates S3TransferManager instances
│
├── S3StorageClient                       StorageClient implementation (full)
├── AbstractStorageObject                 Base for S3 objects
├── S3StorageObject                       StorageObject implementation
├── S3TransferManagerUploader             CRT-based large file uploader
│
├── exceptions/
│   ├── FileTransferException             Transfer-specific error
│   ├── S3OperationException              General S3 operation error
│   └── S3UploadException                 Upload-specific error
│
└── StorageConfigConstants                Config key constants
```

---

## 5. Domain-by-Domain Architecture

### 5.1 AWS Configuration & Credentials

#### BaseAwsConfig — The Configuration Foundation

All AWS service configurations extend `BaseAwsConfig`. It is abstract and uses the builder pattern.

```
BaseAwsConfig (abstract)
  │
  ├── AwsCredentialsProvider  credentials
  ├── Region                  region
  ├── SdkHttpClient           httpClient     (sync — Apache HTTP)
  ├── SdkAsyncHttpClient      asyncHttpClient (async — CRT)
  ├── Duration                timeout         (default: 30s)
  ├── int                     threadPoolSize  (default: 10)
  ├── RetryStrategy           retryStrategy
  │
  ├── buildSyncClient()   → uses ApacheHttpClient
  └── buildAsyncClient()  → uses AwsCrtAsyncHttpClient
```

#### Credentials Resolution Chain

```
AwsCredentialsProviderWrapper
  │
  └── delegates to → AwsCredentialsProvider (SDK v2)
        │
        ├── 1. Explicit credentials (from config)
        ├── 2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        ├── 3. System properties
        ├── 4. ~/.aws/credentials profile
        ├── 5. EC2 instance metadata / ECS task role
        └── 6. SSO (via sso + ssooidc modules)
```

#### Region Resolution

```
AwsRegionWrapper implements RegionIdentifier
  │
  └── wraps Region (AWS SDK v2)
        ├── getId()          → "us-east-1"
        ├── getDisplayName() → "US East (N. Virginia)"
        └── getMetadata()    → Map from Region metadata
```

#### Service-Specific Config Hierarchy

```
BaseAwsConfig
  ├── DynamoRepositoryConfig     — adds tableName, GSI configs, encryption
  ├── AwsMessagingClientConfig   — adds queueUrl, extendedS3Bucket
  ├── NotificationClientConfig   — adds topicArn, messageStructure
  ├── AwsStorageConfig           — adds bucketName, prefix, presign duration
  ├── AwsSesEmailConfig          — adds fromAddress, configSet name
  └── AwsParameterStoreConfig    — adds pathPrefix, decryption flag
```

---

### 5.2 DynamoDB — Database Implementation

#### Architecture Overview

```
DatabaseRepository<T,ID>  (cloud-sdk-api interface)
         │
         ▼
[DynamoDB Enhanced Table impl]  (cloud-sdk-aws)
         │
         ├── uses ReflectionEntityMapper<T,ID>
         │       └── reads @DynamoDbField annotations via reflection
         │
         ├── uses CloudAttributeValueConverter
         │       └── CloudAttributeValue ↔ AttributeValue (AWS)
         │
         ├── uses DynamoDbErrorHandler
         │       └── AWS exceptions → DynamoSupportException
         │
         └── uses DynamoDbKeyExtractor
                 └── extracts partition/sort keys from entity
```

#### ReflectionEntityMapper<T, ID>

The most technically interesting class in the database domain. Uses Java reflection to:

1. Validate the entity type has `@Table` and at least one `@DynamoDbField`
2. Map each annotated field to its DynamoDB attribute name
3. Handle `Date` → epoch-second conversion via `DateEpochSecondAttributeConverter`
4. Handle `OffsetDateTime` → String conversion via `OffsetDateTimeTypeConverter`
5. Extract partition key (via `DefaultPartitionKey`) or composite key (via `DefaultCompositeKey`)

```java
// Entity definition example:
@Table(name = "users", billingMode = BillingMode.PAY_PER_REQUEST)
public class User {
    @DynamoDbField("userId")
    private String userId;

    @DynamoDbField("email")
    private String email;

    @DynamoDbField("createdAt")
    private Date createdAt;

    @TTL
    @DynamoDbField("expiresAt")
    private long expiresAt;
}

// ReflectionEntityMapper resolves at runtime:
// userId  → CloudAttributeValue.ofString(user.getUserId())
// email   → CloudAttributeValue.ofString(user.getEmail())
// createdAt → CloudAttributeValue.ofNumber(epoch seconds)
// expiresAt → CloudAttributeValue.ofNumber(ttl epoch)
```

#### Attribute Conversion Pipeline

```
Java Field Value
      │
      │ (ReflectionEntityMapper)
      ▼
CloudAttributeValue   (type-safe wrapper — cloud-sdk-api)
      │
      │ (CloudAttributeValueConverter — cloud-sdk-aws)
      ▼
software.amazon.awssdk.services.dynamodb.model.AttributeValue
      │
      │ (DynamoDB Enhanced Client)
      ▼
DynamoDB table item
```

**Reverse direction (read):**

```
DynamoDB table item
      │
      ▼
AttributeValue (AWS SDK)
      │
      │ (CloudAttributeValueConverter)
      ▼
CloudAttributeValue
      │
      │ (ReflectionEntityMapper.fromAttributeMap)
      ▼
Java entity instance (T)
```

#### Key Types

```
DefaultPartitionKey<P> implements EntityId
  └── P partitionKey   — single-dimension key

DefaultCompositeKey<P,S> implements CompositeKey<P,S>
  ├── P partitionKey
  └── S sortKey        — composite for range queries
```

#### Secondary Index Support

```
SecondaryIndexConfig
  ├── indexName        String
  ├── partitionKey     String
  ├── sortKey          String (optional)
  └── projectionType   ProjectionType enum

GsiConfig @annotation
  ├── indexName
  ├── partitionKey
  └── sortKey
```

#### Date/Time Converters

| Converter | From | To | Notes |
|---|---|---|---|
| `DateEpochSecondAttributeConverter` | `java.util.Date` | `AttributeValue.N` (epoch seconds) | DynamoDB stores as number |
| `OffsetDateTimeTypeConverter` | `OffsetDateTime` | `AttributeValue.S` (ISO string) | Stored as string |
| `OffsetDateTimeSerializer` | `OffsetDateTime` | JSON string | For JSON serialisation |

---

### 5.3 SQS — Messaging Implementation

#### Class Hierarchy

```
MessagingClient<T>          (cloud-sdk-api)
       │
       ▼
SqsMessagingClient<T>       (cloud-sdk-aws)
       │
       ├── SqsClient          (AWS SDK v2 — sync)
       ├── MessageConverter<T> (converts String↔T, typically JSON)
       └── AwsMessagingClientConfig

QueueMessage<T>             (cloud-sdk-api)
       │
       ▼
SqsMessage<T>               (cloud-sdk-aws)
       ├── messageId
       ├── receiptHandle
       ├── payload (T)
       ├── attributes (Map)
       └── sentTimestamp (Instant)

Listener                    (cloud-sdk-api)
       │
       ▼
SqsListener                 (cloud-sdk-aws)
       ├── start()  → begins polling loop
       └── stop()   → graceful shutdown with drain
```

#### Message Send Flow

```
SqsMessagingClient.sendMessage(queueUrl, payload)
  │
  ├── MessageConverter.serialize(payload) → String (JSON)
  │
  ├── SqsClient.sendMessage(
  │     SendMessageRequest.builder()
  │       .queueUrl(queueUrl)
  │       .messageBody(serialized)
  │       .build())
  │
  └── returns messageId
```

#### Message Receive + Process + Delete Pattern

```
SqsMessagingClient.receiveMessages(ReceiveMessageOptions)
  │
  ├── SqsClient.receiveMessage(
  │     ReceiveMessageRequest.builder()
  │       .queueUrl(url)
  │       .maxNumberOfMessages(options.getMaxMessages())
  │       .visibilityTimeout(options.getVisibilityTimeout())
  │       .waitTimeSeconds(options.getWaitTime())  ← long-polling
  │       .build())
  │
  └── convert each Message → SqsMessage<T>
        │
        └── MessageConverter.deserialize(body) → T

// Consumer:
for (QueueMessage<T> msg : messages) {
    process(msg.getPayload());
    messagingClient.deleteMessage(url, msg.getReceiptHandle());
}
```

#### Extended SQS Client (Large Messages)

For messages exceeding the 256KB SQS limit, the extended client lib transparently stores the payload in S3 and puts a reference in the SQS message:

```
Large Payload (> 256KB)
  │
  ├── amazon-sqs-java-extended-client-lib
  │     └── uploads payload to S3 (configured bucket)
  │     └── SQS message = pointer to S3 object
  │
  └── Consumer transparently downloads from S3
```

#### SqsListener — Long-Poll Loop

```
SqsListener.start()
  │
  └── Thread loop:
        │
        ├── receiveMessages(waitTime=20s)  ← long-poll
        ├── for each message:
        │     ├── handler.handle(message)
        │     └── deleteMessage(receiptHandle)
        │
        └── on stop(): drain in-flight messages, shutdown
```

---

### 5.4 SNS — Notification Implementation

#### Class Hierarchy

```
NotificationService extends EventPublisher  (cloud-sdk-api)
          │
          ▼
SnsService                                  (cloud-sdk-aws)
          │
          ├── SnsClient (AWS SDK v2)
          ├── NotificationClientConfig
          └── SnsExceptionHandler

EventPublisher (@FunctionalInterface)       (cloud-sdk-api)
          │
          ▼
SnsEventPublisher                           (cloud-sdk-aws)
          └── serialises Event → JSON → SNS.publish()
```

#### SnsService Full API

```java
String createTopic(String topicName);
String subscribe(String topicArn, String protocol, String endpoint);
void   publish(String topicArn, String message);
void   publish(String topicArn, String message, String subject);
void   unsubscribe(String subscriptionArn);
void   deleteTopic(String topicArn);
List<String> listTopics();
void   publishEvent(List<Event> events);   // EventPublisher
```

#### Event Publication to SNS

```
SnsEventPublisher.publishEvent(List<Event> events)
  │
  ├── for each event:
  │     ├── JsonSupport.toJson(event)   → JSON string
  │     │
  │     └── SnsClient.publish(
  │           PublishRequest.builder()
  │             .topicArn(config.getTopicArn())
  │             .message(json)
  │             .subject(event.getEventType())
  │             .build())
  │
  └── SnsExceptionHandler handles SnsException → MessagingException
```

#### NotificationClientFactory

```
NotificationClientFactory
  └── create(NotificationClientConfig) → NotificationService
        │
        ├── SnsClient.builder()
        │     .region(config.getRegion())
        │     .credentialsProvider(config.getCredentials())
        │     .httpClient(ApacheHttpClient.builder()...)
        │     .build()
        │
        └── new SnsService(snsClient, config)
```

---

### 5.5 S3 — Storage Implementation

`S3StorageClient` is the most comprehensive implementation in the module (~885 lines). It provides the complete `StorageClient` API plus additional S3-specific error handling.

#### Class Hierarchy

```
StorageClient                  (cloud-sdk-api)
       │
       ▼
S3StorageClient                (cloud-sdk-aws)
       │
       ├── S3Client              (AWS SDK v2 sync)
       ├── S3Presigner           (for pre-signed URLs)
       ├── AwsStorageConfig
       └── S3TransferManagerUploader (for large files)

StorageObject                  (cloud-sdk-api)
       │
       ▼
S3StorageObject                (cloud-sdk-aws)
  ├── extends AbstractStorageObject
  ├── key, size, eTag, lastModified
  ├── metadata (Map<String,String>)
  ├── content (InputStream — lazy)
  └── contentType
```

#### Factory Chain

```
StorageClientFactory.create(AwsStorageConfig)
  │
  ├── S3ClientFactory.createSyncClient(config)
  │     └── S3Client.builder()
  │           .region(...)
  │           .credentialsProvider(...)
  │           .httpClient(ApacheHttpClient...)
  │           .endpointOverride(...)  ← LocalStack support
  │           .build()
  │
  ├── TransferManagerFactory.create(config)
  │     └── S3TransferManager.builder()
  │           .s3Client(asyncS3Client)  ← CRT async client
  │           .build()
  │
  └── new S3StorageClient(s3Client, presigner, transferManager, config)
```

#### Complete Storage Operations

**putObject:**
```
S3StorageClient.putObject(bucket, key, content, contentType, metadata)
  │
  └── S3Client.putObject(
        PutObjectRequest.builder()
          .bucket(bucket)
          .key(key)
          .contentType(contentType)
          .metadata(metadata)
          .build(),
        RequestBody.fromInputStream(content, contentLength))
```

**getObject:**
```
S3StorageClient.getObject(bucket, key)
  │
  ├── S3Client.getObject(
  │     GetObjectRequest.builder()
  │       .bucket(bucket).key(key).build())
  │
  └── returns S3StorageObject wrapping ResponseInputStream
```

**generatePresignedUrl:**
```
S3StorageClient.generatePresignedUrl(bucket, key, duration, filename)
  │
  └── S3Presigner.presignGetObject(
        PresignedGetObjectRequest.builder()
          .getObjectRequest(req)
          .signatureDuration(duration)
          .build())
          │
          └── if filename != null:
                Content-Disposition: attachment; filename="..."
```

**copyObject:**
```
S3StorageClient.copyObject(srcBucket, srcKey, dstBucket, dstKey)
  │
  └── S3Client.copyObject(
        CopyObjectRequest.builder()
          .sourceBucket(srcBucket)
          .sourceKey(srcKey)
          .destinationBucket(dstBucket)
          .destinationKey(dstKey)
          .build())
```

#### Large File Transfer

```
S3TransferManagerUploader (CRT-based)
  │
  └── uploadFile(file, bucket, key)
        │
        └── S3TransferManager.uploadFile(
              UploadFileRequest.builder()
                .putObjectRequest(...)
                .source(file.toPath())
                .build())
              .completionFuture()
              .join()
```

#### Error Handling Strategy

```
S3 Operation
  │
  ├── S3Exception (AWS)
  │     ├── 404 NoSuchKey       → custom message "Object not found"
  │     ├── 404 NoSuchBucket    → custom message "Bucket not found"
  │     ├── 403 AccessDenied    → custom message "Access denied"
  │     └── other               → S3OperationException(e.getMessage())
  │
  └── SdkClientException       → StorageClientInitializationException
```

---

### 5.6 SES v2 — Email Implementation

#### Architecture

```
EmailService                   (cloud-sdk-api)
       │
       ▼
[SES v2 implementation]        (cloud-sdk-aws)
       │
       ├── SesV2Client           (AWS SDK v2)
       ├── AwsSesEmailConfig
       ├── HandlebarsTemplateServiceImpl
       └── MailContentImpl

TemplateService                (cloud-sdk-api)
       │
       ▼
HandlebarsTemplateServiceImpl  (cloud-sdk-aws)
       └── Handlebars engine (jknack 4.3.1)
```

#### Email Send Flow (new API)

```
EmailService.sendEmail(EmailRequest)
  │
  ├── Build SES v2 SendEmailRequest:
  │     ├── Destination.builder().toAddresses(request.getTo()).build()
  │     ├── Content: SimpleEmailServiceV2Content
  │     │     ├── Subject: Content.builder().data(subject).build()
  │     │     ├── HtmlPart: Content.builder().data(htmlBody).build()
  │     │     └── TextPart: Content.builder().data(textBody).build()
  │     └── FromEmailAddress: request.getSource()
  │
  └── SesV2Client.sendEmail(sesRequest)
        └── returns SendEmailResponse.messageId()
```

#### Template Processing Flow

```
HandlebarsTemplateServiceImpl.processTemplate(name, data)
  │
  ├── Handlebars.compile(name)
  │     └── loads template from classpath resources
  │
  └── template.apply(data)
        └── Handlebars mustache-style interpolation
              {{variable}}, {{#each items}}, {{#if condition}}
```

#### Email with Attachments (Legacy)

```
RawEmailSender
  │
  ├── javax.mail.MimeMessage construction
  │     ├── MimeMultipart (mixed)
  │     │     ├── MimeBodyPart (HTML/text)
  │     │     └── MimeBodyPart[] (attachments)
  │     └── encode as raw bytes
  │
  └── SesV2Client.sendEmail(
        SendEmailRequest.builder()
          .content(EmailContent.builder()
            .raw(RawMessage.builder()
              .data(SdkBytes.fromByteArray(rawBytes))
              .build())
            .build())
          .build())
```

---

### 5.7 SSM — Parameter Store Implementation

#### Architecture

```
CloudParameterStore            (cloud-sdk-api)
       │
       ▼
SsmCloudParameterStore         (cloud-sdk-aws)
       │
       ├── SsmClient              (AWS SDK v2)
       └── AwsParameterStoreConfig

CloudParameter                 (cloud-sdk-api)
       │
       ▼
SsmParameter                   (cloud-sdk-aws)
       ├── name, value, type
       ├── lastModified (Instant)
       ├── version (long)
       └── arn
```

#### Parameter Resolution Flow

```
SsmCloudParameterStore.getParameter("/mercury/prod/db-url")
  │
  └── SsmClient.getParameter(
        GetParameterRequest.builder()
          .name("/mercury/prod/db-url")
          .withDecryption(true)
          .build())
        │
        └── SsmParameter(response.parameter())
```

#### Placeholder Transformation

```
SsmParameterTransformation implements ParameterTransformation
  │
  └── transform(text, parameterStore)
        │
        ├── Pattern: \$\{awsps:([^}]+)\}
        │
        ├── Matcher finds all ${awsps:/path/to/param}
        │
        └── For each match:
              parameterStore.getParameter(path).getValue()
              → replace in text
```

#### Factory

```
ParameterStoreClientFactory.create(AwsParameterStoreConfig)
  │
  ├── SsmClient.builder()
  │     .region(config.getRegion())
  │     .credentialsProvider(...)
  │     .httpClient(ApacheHttpClient...)
  │     .endpointOverride(...)  ← LocalStack support
  │     .build()
  │
  └── new SsmCloudParameterStore(ssmClient, config)
```

---

### 5.8 Legacy Guice Modules

These modules use AWS SDK **v1** and are pending migration:

```
AWSConstants
  ├── SQS_READER_CONFIG    ClientConfiguration (maxConn=10, socketTimeout=30s)
  ├── SQS_WRITER_CONFIG    ClientConfiguration (maxConn=5, socketTimeout=10s)
  └── SNS_PUBLISH_CONFIG   ClientConfiguration (maxConn=10, socketTimeout=10s)

SNSModule (Guice)
  └── binds AmazonSNS → AmazonSNSClient (SDK v1)

SQSModule (Guice)
  └── binds AmazonSQS → AmazonSQSClient (SDK v1)

SQSReader (Guice)
  └── configures SQS long-poll reader (SDK v1)

JestModule (Guice)
  └── binds JestClient → JestClientBuilder.build()
```

> These modules are used by legacy services in `commons`. They will be removed after all services migrate to the v2 equivalents.

---

## 6. AWS SDK v2 Migration Status

| Service | v2 Impl | v1 Legacy | Status |
|---|---|---|---|
| DynamoDB | `dynamodb-enhanced` | `dynamo-client` module | v2 complete |
| S3 | `S3StorageClient` | `aws-java-sdk-s3` | v2 complete |
| SQS | `SqsMessagingClient` | `SQSModule`, `SQSReader` | v2 new, v1 legacy still present |
| SNS | `SnsService` | `SNSModule` | v2 new, v1 legacy still present |
| SES | `SesV2Client` | n/a | v2 complete (SES v2 API) |
| SSM | `SsmClient` | n/a | v2 complete |
| Elasticsearch | (Jest, temporary) | `JestModule` | pending migration |

---

## 7. HTTP Transport Architecture (Netty Removal)

This is a critical architectural decision documented in `docs/2026-04-23-netty-removal.md`.

### Problem

AWS SDK v2's default async transport is `NettyNioAsyncHttpClient`. Netty conflicts with Dropwizard's embedded Jetty server because both try to own the NIO event loop, causing classloading conflicts and port binding issues.

### Solution

```xml
<!-- Every AWS SDK v2 dependency excludes Netty: -->
<exclusion>
    <groupId>software.amazon.awssdk</groupId>
    <artifactId>netty-nio-client</artifactId>
</exclusion>
```

### Replacement

```
Sync operations:   ApacheHttpClient (software.amazon.awssdk:apache-client)
                   └── thread-per-request, blocking I/O, Dropwizard-compatible

Async operations:  AwsCrtAsyncHttpClient (software.amazon.awssdk:aws-crt-client)
                   └── uses AWS Common Runtime (C library via JNI)
                   └── no Netty dependency
                   └── used by S3 Transfer Manager for multipart uploads
```

### HTTP Client Usage per Service

| Service | HTTP Client | Reason |
|---|---|---|
| S3 (standard ops) | ApacheHttpClient | Sync, blocking — simpler |
| S3 (transfer manager) | AwsCrtAsyncHttpClient | Async multipart — required by S3TransferManager |
| SQS | ApacheHttpClient | Long-poll with blocking OK |
| SNS | ApacheHttpClient | Fire-and-forget publish |
| SSM | ApacheHttpClient | Low-volume config reads |
| SES | ApacheHttpClient | Synchronous send |
| DynamoDB | ApacheHttpClient | Request-response pattern |

---

## 8. Key Data Flows

### 8.1 Full DynamoDB Round-Trip

```
Application
  │  save(User{ id:"u1", email:"alice@example.com", createdAt: now })
  ▼
DatabaseRepository.save(user)
  │
  ▼ ReflectionEntityMapper.toAttributeMap(user)
  │   reads @DynamoDbField("userId")   → CloudAttributeValue.ofString("u1")
  │   reads @DynamoDbField("email")    → CloudAttributeValue.ofString("alice@example.com")
  │   reads @DynamoDbField("createdAt")→ CloudAttributeValue.ofNumber(epochSec)
  │
  ▼ CloudAttributeValueConverter
  │   CloudAttributeValue(STRING,"u1")  → AttributeValue.builder().s("u1").build()
  │   CloudAttributeValue(NUMBER,epoch) → AttributeValue.builder().n("1746393600").build()
  │
  ▼ DynamoDbEnhancedClient.table("users").putItem(item)
  │
  ▼ DynamoDB PutItem API call
```

### 8.2 SQS Message Round-Trip

```
Producer:
  messagingClient.sendMessage(queueUrl, orderDto)
    │
    ├── JSON.serialize(orderDto) → "{\"orderId\":\"O1\",...}"
    └── SQS.SendMessage → messageId:"msg-abc"

Consumer:
  List<QueueMessage<OrderDto>> msgs = messagingClient.receiveMessages(opts)
    │
    ├── SQS.ReceiveMessage (20s long-poll) → [SQS Message]
    └── JSON.deserialize(body) → OrderDto

  processOrder(msg.getPayload());

  messagingClient.deleteMessage(queueUrl, msg.getReceiptHandle())
    │
    └── SQS.DeleteMessage → message removed from queue
```

### 8.3 Workflow Event Fan-Out

```
FileProcessor
  │
  │  1. Build MetaData
  │     MetaData meta = MetaData.builder()
  │       .bucket("cargo-bucket").fileName("manifest.xml")
  │       .component("file-processor").exitStatus("SUCCESS").build()
  │
  │  2. Create Event
  │     Event event = EventGenerator.getInstance().createCloseRunEvent(meta)
  │
  │  3. Publish
  │     snsEventPublisher.publishEvent(List.of(event))
  │
  ▼ SnsEventPublisher
      │
      ├── JsonSupport.toJson(event) → JSON string
      └── SnsClient.publish(topicArn, json, subject)
            │
            ▼ SNS Topic
              ├── → SQS Queue A (downstream service 1)
              ├── → SQS Queue B (downstream service 2)
              └── → Lambda function (audit log)
```

---

## 9. Integration Testing Architecture

The module uses **DynamoDB Local** (SQLite-backed) for integration tests, managed by `dynamo-integration-test` module.

```
BaseDynamoIT (abstract base)
  │
  ├── @BeforeAll: LocalDynamoDBServer.start()
  │     └── DynamoDB Local embedded server on random port
  │
  ├── TestRepositoryConfig
  │     └── DynamoClient pointing to localhost:randomPort
  │
  └── @AfterAll: LocalDynamoDBServer.stop()

Test execution:
  mvn verify -Pintegration
    └── maven-failsafe-plugin runs *IT.java files
    └── sqlite4java native libs copied to target/native-libs
    └── system property: sqlite4java.library.path
```

**Test Separation:**
- Unit tests: `mvn test` — excludes `integration` tag, uses Mockito for AWS clients
- Integration tests: `mvn verify` — uses DynamoDB Local, real client code

---

## 10. Areas of Excellence

### Clean AWS SDK v2 Adoption
The module is fully on AWS SDK v2 (2.30.24) for all new implementations. The BOM import ensures consistent versions across all AWS modules. Exclusion of `netty-nio-client` from every dependency is thorough and well-documented.

### Netty Removal — Proactive Architectural Decision
Eliminating Netty and replacing with CRT client for async and Apache HTTP for sync is a mature architectural decision that prevents classloading conflicts with Dropwizard's embedded Jetty. The decision is documented in `docs/2026-04-23-netty-removal.md`.

### CRT-Based S3 Transfer Manager
Using `AwsCrtAsyncHttpClient` + `S3TransferManager` for large file operations enables multipart parallel uploads without Netty, providing high throughput.

### ReflectionEntityMapper — Powerful Generic Solution
A single reflection-based mapper eliminates the need for per-entity mapper implementations. The `@DynamoDbField` annotation provides explicit control without forcing a specific DynamoDB SDK annotation.

### LocalStack-Compatible Configuration
`endpointOverride()` in all factory classes enables LocalStack testing without code changes — just configuration.

### Comprehensive S3StorageClient
885 lines covering every S3 operation with consistent error handling, pagination support, pre-signed URL generation with content-disposition, and transfer manager integration.

### Integration Test Isolation
DynamoDB Local integration tests are properly isolated via `@Tag("integration")` and maven-failsafe-plugin, so unit tests remain fast and integration tests run on demand.

---

## 11. Areas for Improvement

### AWS SDK v1 Must Have a Removal Plan
`aws-java-sdk-core`, `aws-java-sdk-sqs`, `aws-java-sdk-sns`, `aws-java-sdk-s3` at version 1.12.730 are marked "temporary" but are live production dependencies. AWS SDK v1 reached maintenance-only status. A concrete migration timeline with deprecation dates should be established.

### SQSModule/SNSModule Still Use SDK v1
The Guice modules `SNSModule`, `SQSModule`, `SQSReader` use `AmazonSNS`, `AmazonSQS` (v1 types). Since `SnsService` and `SqsMessagingClient` exist in v2, these legacy modules should be migrated and removed.

### No Retry/Backoff in SqsMessagingClient
Unlike `JestClientRetryHandler` which implements exponential backoff, `SqsMessagingClient` has no explicit retry strategy. It relies on the SDK's default retry policy. For production use, a configurable `RetryStrategy` (via `BaseAwsConfig`) should be injected.

### Missing Dead Letter Queue (DLQ) Configuration
`AwsMessagingClientConfig` has no DLQ configuration. In production SQS usage, DLQ should be configurable at the client level to handle messages that fail processing repeatedly.

### SesV2Client Not Exposed via StorageClientFactory Pattern
Unlike `NotificationClientFactory` and `StorageClientFactory`, there is no `EmailServiceFactory`. `AwsSesEmailConfig` is used directly. Adding a factory ensures consistent construction and testability.

### Hard-Coded Thread Pool in BaseAwsConfig
`threadPoolSize = 10` (default) is hard-coded logic in `BaseAwsConfig`. This should always come from configuration, not from a default that may be appropriate for one service but not another.

### CloudAttributeValueConverter Missing Null Safety
If a `CloudAttributeValue` has type `LIST` or `MAP` but the inner collection is empty or null, the converter may throw a `NullPointerException`. Add explicit null/empty guards.

### `OffsetDateTimeTypeConverter` Stores as String, Not Number
DynamoDB best practices recommend storing timestamps as numbers (epoch milliseconds) for efficient range queries and sorting. Storing as ISO string prevents efficient sort key range queries on time ranges.

### `AwsStorageConfig` Missing Multipart Threshold Configuration
The S3 Transfer Manager can do multipart uploads, but the threshold (when to switch from single PUT to multipart) is not configurable via `AwsStorageConfig`. This should be an explicit configuration property.

### `spring-security-crypto` Version 4.2.3 in Scope
The parent POM pins `spring.sercurity.crypto.version=4.2.3.RELEASE` (2017). While this library is only used for encryption utilities, it is extremely outdated and should be updated to Spring Security 6.x or replaced with a Bouncy Castle / JCA implementation.
