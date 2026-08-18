# Mercury Services — AWS SDK 1.x → 2.x (cloud-sdk) Migration — Pending Inventory

**Date:** 2026-07-30
**Scope:** `mercury-services` monorepo (plus the offshoot workspace `mft-s3-aqua-appia`).
**Goal:** every module below must migrate off **AWS SDK v1** (`com.amazonaws:aws-java-sdk-*`,
imports `com.amazonaws.*`) onto **AWS SDK v2** via the internal **cloud-sdk** libraries
(`com.inttra.mercury:cloud-sdk-api` + `cloud-sdk-aws`), following the already-migrated **booking**,
**network**, **auth**, **visibility** modules as the template.

## Methodology & how to read this

- **Signal = imports** in `src/main/java` (the truest usage signal), cross-checked with `pom.xml`
  dependencies. AWS service is derived from the `com.amazonaws.services.<svc>` package.
- **Not counted as SDK-1.x** (expected even after migration):
  - `com.amazonaws.services.lambda.runtime.*` and `...runtime.events.*` → the **Lambda handler
    runtime** (`aws-lambda-java-core` / `aws-lambda-java-events`), *not* the AWS SDK. Handlers keep these.
  - `io.searchbox.*` (**Jest**) / `org.elasticsearch.*` → the **Elasticsearch** client. Separate
    Jest→OpenSearch migration (out of scope here). **Note:** Elasticsearch request signing legitimately
    needs the AWS **v1 `AWS4Signer`** (`aws-java-sdk-core`) until that migration happens — see §D.
- **Deprecated shared libs — IGNORE (per direction):** `libs/atlantida`, `libs/dynamo-client`,
  `libs/email-sender`. Not listed for migration.
- **Already merged to 2.x (per direction) — excluded from the pending list:** `rates`,
  `value-added-service` (verified: 0 `com.amazonaws` imports; use `software.amazon.awssdk` DynamoDB
  Enhanced). Also fully migrated: `auth`, `network`, `booking`, `booking-bridge`, `db-migration`,
  `registration`, `self-service-reports`, `webbl`, `tx-tracking`, `bill-of-lading-v2`.

## cloud-sdk target mapping (v1 service → cloud-sdk / v2)

| AWS v1 usage | cloud-sdk-api target (impl in cloud-sdk-aws) | Reference module |
|---|---|---|
| `services.s3.AmazonS3*` | `StorageClient` via `StorageClientFactory.createS3Client(AwsStorageConfig)` | visibility-s3-archiver, booking |
| `services.sqs.AmazonSQS*` | `MessagingClient` via `MessagingClientFactory.createConfiguredClient(AwsMessagingClientConfig)` | visibility-pending-start, network |
| `services.sns.AmazonSNS*` | cloud-sdk messaging/notification (SNS) API | network, booking-bridge |
| `services.simplesystemsmanagement` (SSM/Param Store) | `CloudParameterStore` via `ParameterStoreClientFactory.createParameterStore(AwsParameterStoreConfig)` | visibility, auth |
| `services.dynamodbv2.datamodeling.*` (DynamoDBMapper v1: `@DynamoDBTable`, `@DynamoDBHashKey`, `DynamoDBTypeConverter`) — **entity/table access** | cloud-sdk **`DatabaseRepository<T,ID>`** created via **`DynamoRepositoryFactory.createRepository/createEnhancedRepository(DynamoDbClientConfig, table, EntityClass, DynamoRepositoryConfig)`**; entity beans annotated with cloud-sdk `@Table` + v2 `@DynamoDbBean`/`@DynamoDbPartitionKey`/`@DynamoDbSortKey` + `@DynamoDbConvertedBy` converters. Wire via a Guice `*DynamoModule` + `*Dao`. **Do NOT hand-build a `DynamoDbClient`.** | booking `BookingDetailDao`+`BookingDynamoModule`, registration `RegistrationDao`, network `SubscriptionsDao`, visibility `ContainerEventDao` |
| `services.dynamodbv2` low-level / **generic raw-item access** (arbitrary attributes → `Map<String,AttributeValue>`, no fixed entity) | cloud-sdk **`DynamoRepositoryFactory.createDynamoDbClient(DynamoDbClientConfig)`** → a *configured* low-level v2 `DynamoDbClient` (region + credentials validated by cloud-sdk, HTTP/retry set). Use this instead of `DynamoDbClient.builder()...` by hand. | visibility-s3-archiver `getDynamoDbClient` (see §E) |
| `services.simpleemail` (SES) | cloud-sdk email API | auth, network, visibility-inbound `EmailSender` |
| `ClientConfiguration`, `retry.RetryPolicy`, `PredefinedBackoffStrategies` | v2 `ClientOverrideConfiguration` + `RetryPolicy`/`RetryStrategy` (set inside the cloud-sdk config) | visibility-s3-archiver `getDynamoDbClient` |
| `auth.*` (`AWSCredentialsProvider`, `DefaultAWSCredentialsProviderChain`, `BasicAWSCredentials`) | `AwsCredentialsProviderWrapper.of(DefaultCredentialsProvider.create())` (v2) | visibility (this ticket, ION-16387) |
| `services.kms` | no cloud-sdk wrapper today → direct v2 `software.amazon.awssdk.services.kms.KmsClient` | (new) |
| `services.cloudformation` | no cloud-sdk wrapper today → direct v2 `software.amazon.awssdk.services.cloudformation` | (new) |
| `services.cloudwatchmetrics` (mft) | direct v2 `software.amazon.awssdk.services.cloudwatch` | (new) |
| `AWS4Signer` for Elasticsearch | **keep v1 until Jest→OpenSearch** (see §D) | visibility-inbound |

---

# 1. Modules still on AWS SDK v1 (pending migration)

Legend for "AWS services": derived from real v1 SDK imports (Lambda runtime/events and Jest excluded and
noted separately). "pom AWS deps" = AWS-relevant `<artifactId>`s declared in that module's `pom.xml`
(some are inherited from a parent/commons module).

## 1.1 `partner-integrator` (heaviest — 104 v1 files) — multi-module
Parent `partner-integrator`, submodules (each `pi-*`):

| Submodule | AWS services (v1) | Lambda? | pom AWS deps (declared) |
|---|---|---|---|
| `pi-commons` | S3, SQS, DynamoDB (mapper v1) | – | `aws-java-sdk-dynamodb` |
| `pi-booking-processor` | DynamoDB | – | (inherits pi-commons) |
| `pi-bl-in-processor` | DynamoDB | – | `elasticsearch`, `aws-lambda-java-events` |
| `pi-bl-es-lambda` | DynamoDB | **Lambda** (runtime x7) | `aws-lambda-java-events`, `elasticsearch` |
| `pi-si-in-processor` | DynamoDB | – | (inherits) |
| `pi-si-out-processor` | S3, SQS, SNS, SSM, DynamoDB | Lambda (runtime x2) | `aws-lambda-java-events` |
| `pi-statusevents-out-processor` | S3, SQS, SNS, SSM, DynamoDB | Lambda (runtime x3) | `aws-lambda-java-events` |
| `pi-lambda-streamToSns` | DynamoDB, SNS | **Lambda** (runtime x8) | `aws-java-sdk-dynamodb`, `aws-java-sdk-sns`, `aws-lambda-java-core`, `aws-lambda-java-events` |

**Services in play:** S3, SQS, SNS, SSM/Parameter Store, DynamoDB (v1 mapper). Plus Elasticsearch (Jest)
in the `bl-es`/`bl-in` paths → separate OpenSearch track. Contains **Lambda** handlers (see §C for the
handler credential change).

## 1.2 `shipping-instruction` (62 v1 files) — single module
- **AWS services (v1):** S3, DynamoDB (mapper v1), **CloudFormation**, S3 `waiters`, `ClientConfiguration`.
- **pom AWS deps:** `aws-java-sdk-cloudformation`, `aws-lambda-java-events`, `elasticsearch-rest-high-level-client`.
- **Notes:** CloudFormation has **no cloud-sdk wrapper** — migrate to direct v2
  `software.amazon.awssdk.services.cloudformation`. DynamoDB mapper → v2 Enhanced. S3 → `StorageClient`.
  Also a Lambda-events consumer.

## 1.3 `oceanschedules-process` (40 v1 files) — multi-module
Submodules and their v1 services:

| Submodule | AWS services (v1) | pom AWS deps (declared) |
|---|---|---|
| `common` | S3, SQS, SNS + `ClientConfiguration`/`retry` | `aws-java-sdk-sqs`, `amazon-sqs-java-extended-client-lib` |
| `inbound` | S3, SQS, SNS | (inherits common) |
| `outbound` | S3, SQS, SNS | `aws-java-sdk-core/s3/sns/sqs/ssm`, `jest` |
| `loader` | S3, SQS, SNS, `regions`, `auth` | `aws-java-sdk-s3/sns/sqs`, `elasticsearch*`, `jest*` |
| `staging` | S3, SQS, SNS | `jest` |
| `collector` | S3, SQS, SNS | (inherits) |
| `port-pair-generator` | S3, SQS, SNS, DynamoDB, `regions`, `auth` | `aws-java-sdk-dynamodb` |
| `aggregator` | S3, SQS, SNS, DynamoDB, `auth`, `DefaultRequest`, `http` | `aws-java-sdk-bundle/core/dynamodb/s3/ssm`, `emr-dynamodb-hadoop`, `elasticsearch-rest-high-level-client`, `jest` |
| `port-pair-generator`/others | — | — |

**Services in play:** S3, SQS (incl. `amazon-sqs-java-extended-client-lib` large-payload), SNS, SSM,
DynamoDB, plus Elasticsearch (Jest/RestHighLevel) and Spark/Hadoop connectors — see the compatibility
note in §1.3.1. `aggregator`/`loader` also use `auth`/`DefaultRequest`/`http` for signed Elasticsearch
requests (§D).

### 1.3.1 Spark / EMR / Elasticsearch-Spark connectors — AWS SDK v2 compatibility

These modules are **Apache Spark SQL** applications (`org.apache.spark:spark-sql_2.13`). Three
Spark/Hadoop dependencies look AWS-related; here is how each interacts with the cloud-sdk (v2) migration:

- **`org.apache.spark:spark-sql_2.13` (Spark) — not AWS.** Pure compute engine, contains no AWS SDK.
  Version-agnostic to the AWS SDK; fully compatible with cloud-sdk v2. No change for the AWS migration.

- **`org.elasticsearch:elasticsearch-spark-30_2.13` (ES-Hadoop/Spark) — not AWS.** Talks to
  Elasticsearch over HTTP/REST and contains **no AWS SDK at all**, so it is completely independent of
  the AWS SDK version and **fully compatible with v2**. Used in `loader`
  (`org.elasticsearch.spark.rdd.api.java.JavaEsSpark` in `TransshipmentAndUploadTask.java`). Its only
  migration concern is the separate **ES→OpenSearch** track (the `opensearch-hadoop` equivalent), not
  the AWS SDK migration.

- **`com.amazon.emr:emr-dynamodb-hadoop:5.3.0` (EMR DynamoDB connector) — AWS-authored, internally
  AWS SDK v1, and *no v2 build exists*.** Two important facts for this repo:
  1. **It is currently a dead / unused dependency here.** There are **zero** references in the source to
     `org.apache.hadoop.dynamodb.*`, `DynamoDBInputFormat`, `DynamoDBItemWritable`, `hadoopRDD`, or
     `newAPIHadoopRDD`. The DynamoDB-from-Spark work in `aggregator/dynamo/DynamoSparkService.java`
     instead uses the **plain AWS SDK v1 `AmazonDynamoDB` client** (`AmazonDynamoDBClientBuilder`,
     `QueryRequest`/`QueryResult`) inside Spark closures. So `emr-dynamodb-hadoop` can most likely be
     **removed outright** from `aggregator` (and from `shipment-loader`, which also declares it) — verify
     no Spark job runtime config references the `dynamodb` Hadoop format and that the shaded/assembly jar
     doesn't need it, then delete the dependency.
  2. **Even if it were used, it would not block the migration.** v1 and v2 have different Maven
     coordinates and Java packages (`com.amazonaws.*` vs `software.amazon.awssdk.*`), so the connector's
     internal v1 SDK can **coexist** on the classpath alongside cloud-sdk's v2 without conflict (same
     coexistence situation as the ES `AWS4Signer` in §D). You simply cannot "upgrade" the connector to
     v2; it would stay on v1 for that bulk-I/O path until replaced by a v2-based approach (e.g. a v2
     custom connector, `DynamoDbClient` scan/parallel-scan, or the DynamoDB→S3 export path).
  - **Actual work here:** migrate `DynamoSparkService`'s direct **v1 `AmazonDynamoDB`** usage to the
    cloud-sdk. Because it issues an ad-hoc query returning `Map<String,AttributeValue>` (raw, no fixed
    entity), use **`DynamoRepositoryFactory.createDynamoDbClient(DynamoDbClientConfig)`** to obtain a
    configured low-level v2 `DynamoDbClient` (region + creds via cloud-sdk) rather than hand-building one;
    the `query` + `LastEvaluatedKey` pagination maps 1:1 to v2 `QueryRequest`/`QueryResponse` (build the
    client per Spark partition, keep it `transient`). If the access is really entity-shaped, prefer a
    cloud-sdk `DatabaseRepository` instead. Then delete the unused `emr-dynamodb-hadoop` dependency.

- **`hadoop-aws` / `aws-java-sdk-bundle` for `s3a://` (Spark S3 I/O) — separate track.** Spark reads/writes
  S3 via the `s3a://` Hadoop filesystem (`ExportService` uses the `s3a://` prefix), which is provided by
  `hadoop-aws` and pulls its **own** AWS SDK (the v1 `aws-java-sdk-bundle` in the aggregator pom; Hadoop
  3.4+ moved to a v2 bundle). This dependency chain is governed by the **Spark/Hadoop version**, not by
  your application code, and is **independent** of the cloud-sdk migration — migrating the app's direct
  SDK calls to v2 does not force `hadoop-aws` to change, and the two coexist. Moving `s3a` off the v1
  bundle is a Hadoop/Spark upgrade, tracked separately.

**Summary:** Spark and elasticsearch-spark are not AWS SDK and are fully v2-compatible; `emr-dynamodb-hadoop`
is v1-only but **unused here (remove it)**; the real DynamoDB-from-Spark code is plain v1 SDK and migrates
to cloud-sdk/v2 normally; `s3a`/`hadoop-aws` is a separate Hadoop-governed track that coexists with v2.

## 1.4 `watermill-publisher` (30 v1 files) — multi-module

| Submodule | AWS services (v1) | pom AWS deps (declared) |
|---|---|---|
| `watermill-commons` | S3, SQS | (parent) |
| `watermill-booking` | S3, SQS, SNS | (inherits commons) |
| `watermill-booking-aperak` | S3, SQS, SNS | `aws-java-sdk-dynamodb`, `aws-java-sdk-sns`, `aws-java-sdk-sqs`, `aws-lambda-java-events` |
| `watermill-cargo-visibility-subscription` | S3, SQS, SNS, DynamoDB | (inherits) |

**Services in play:** S3, SQS, SNS, DynamoDB.

## 1.5 `oceanschedules` (13 v1 files) — single module
- **AWS services (v1):** S3, SNS, DynamoDB (mapper v1), `ClientConfiguration`/`retry`.
- **pom AWS deps:** `elasticsearch` (+ AWS SDK deps inherited/transitive).
- **Notes:** S3 → StorageClient, SNS → cloud-sdk notification, DynamoDB mapper → v2 Enhanced.

## 1.6 `bill-of-lading` (v1 module, 9 v1 files) — single module
- **AWS services (v1):** DynamoDB (**v1 `DynamoDBMapper`** — `@DynamoDBTable`, `@DynamoDBHashKey`,
  `@DynamoDBIndexHashKey`, `DynamoDBTypeConverter`, `DynamoDBQueryExpression`), S3 (`AmazonS3`,
  `AmazonS3ClientBuilder`, `S3Object`), `ClientConfiguration`, `util.IOUtils`.
- **Notes:** This is the **v1** bill-of-lading; **`bill-of-lading-v2` is already on 2.x** and is the
  reference for the DynamoDB Enhanced model conversion. Largest work here is the DynamoDBMapper→Enhanced
  model migration.

## 1.7 `booking-downstream-processor` → `booking-cargoscreen` (4 v1 files)
- **AWS services (v1):** S3 (`AmazonS3`, `AmazonS3ClientBuilder`, `GetObjectRequest`, `S3Object`,
  `PutObjectResult`), SQS (`sqs.model.Message`), `ClientConfiguration`/`retry`,
  `AbortedException`/`AmazonServiceException`/`SdkClientException`, `util.IOUtils`.
- **pom AWS deps:** `aws-lambda-java-events`, `elasticsearch-rest-high-level-client`.
- **Notes:** S3 → StorageClient; SQS → MessagingClient. Also consumes S3/SNS Lambda events.

## 1.8 `lambda/*` standalone functions
These are AWS Lambda functions **outside** the visibility/booking modules; the visibility lambdas
(under `visibility/`) and booking's lambda path are already migrated (see §C). Each of the following
still uses v1 SDK clients and needs the §C handler change **plus** the service-client migration:

| `lambda/` submodule | AWS services (v1) | pom AWS deps |
|---|---|---|
| `auth-tokens-archive` | DynamoDB, S3, SNS | `aws-java-sdk-dynamodb`, `aws-lambda-java-core/events` |
| `bounceback-email` | S3, **SSM**, SES-adjacent | `aws-java-sdk-kms`, `aws-java-sdk-s3`, `aws-java-sdk-ssm`, `aws-lambda-java-core/events` |
| `optionalvalidation-archive` | DynamoDB, S3, `ClientConfiguration`/`retry` | `aws-java-sdk-dynamodb`, `aws-lambda-java-core/events` |
| `subscription-archive` | DynamoDB, S3, `ClientConfiguration`/`retry` | `aws-java-sdk-dynamodb`, `aws-lambda-java-core/events` |
| `registration-archive` | DynamoDB, S3, **KMS**, `ClientConfiguration` | `aws-java-sdk-dynamodb`, `aws-lambda-java-core/events` |
| `partner-integration` | DynamoDB, **SSM** | `aws-java-sdk-dynamodb`, `aws-java-sdk-ssm`, `aws-lambda-java-core/events` |
| `elasticsearch-purge` | `auth`, `http` (ES signing only) | `aws-java-sdk-core`, `aws-lambda-java-core`, `elasticsearch-rest-high-level-client` |
| `booking-outbound` | **none** (only `com.amazonaws.util.StringUtils`) | `aws-java-sdk-dynamodb`, `aws-java-sdk-ssm` (**declared but unused** — see §D) |

**KMS** (`registration-archive`, `bounceback-email`) has no cloud-sdk wrapper → direct v2 `KmsClient`.

## 1.9 `libs/integration-test-commons` (test-support library)
- **AWS usage (v1):** `client`, `dynamodbv2` — in `BaseMyBatisDynamoIT.java` / `DynamoSupport.java`
  test-support code; pom declares `aws-java-sdk-dynamodb` + `DynamoDBLocal`.
- **Status / git history:** already touched by the cloud-sdk work — commits
  `ION-12311` (*Auth application integration with cloud-sdk library*), `ION-12313` (*refactoring, email
  and s3, integration tests*), `ION-15887` (*Auth and Db-migration Commons upgrade*),
  `ION-15888` (*Networks Commons Upgrade*). It also already imports `software.amazon.awssdk` (v2) in
  `BaseMyBatisDynamoIT.java`. So it is **partially/primarily upgraded** and consumed by the migrated
  **auth**, **db-migration**, **network** integration tests. Remaining v1 bits are the DynamoDB-Local
  test harness glue; low priority and may be intentional for the local test container.

---

# 2. `mft-s3-aqua-appia` (separate workspace) — fully AWS SDK v1

Path: `C:\Users\arijit.kundu\projects\mft-s3-aqua-appia` — Maven, Java 17, **AWS SDK v1 `1.12.716`**,
no v2, no cloud-sdk, no Elasticsearch/Jest.

| Module | AWS services (v1) | pom AWS deps |
|---|---|---|
| `aw-bridge-shared` | **S3, SQS, SNS, DynamoDB (doc API), SSM** + auth/config/retry/util | `aws-java-sdk-s3`, `aws-java-sdk-sqs`, `aws-java-sdk-sns`, `aws-java-sdk-dynamodb`, `aws-java-sdk-ses`, `aws-java-sdk-ssm`, `aws-java-sdk-cloudwatchmetrics` |
| `aw-bridge-ib` | S3 | (depends on `aw-bridge-shared`) |
| `aw-bridge-ob` | S3, SNS, SQS, S3-event model | (depends on `aw-bridge-shared`) |

- All AWS client construction is centralized in `aw-bridge-shared`
  (`AWSClientConfiguration.java`, `AWSClientConfigHelper.java`, `parameterstore/ParameterStore.java`,
  `s3/S3WorkspaceService.java`, `SQSClient.java`, `SNSClient.java`, DynamoDB health-check).
- **Migration target:** same cloud-sdk mapping as §"cloud-sdk target mapping". Because clients are
  centralized in `aw-bridge-shared`, the migration is well-contained: replace the shared client
  factories/config with cloud-sdk `StorageClient`/`MessagingClient`/`CloudParameterStore` + the SNS and
  SES equivalents, then delete the `aws-java-sdk-*` deps. `cloudwatchmetrics` → direct v2
  `software.amazon.awssdk.services.cloudwatch`.

---

# 3. Sections requested

## §C. Lambda handler upgrade — the change every remaining Lambda needs

The booking and visibility lambdas are already migrated; the remaining Lambda functions
(§1.8 `lambda/*`, plus the Lambda submodules of `partner-integrator` — `pi-bl-es-lambda`,
`pi-lambda-streamToSns`, `pi-si-out-processor`, `pi-statusevents-out-processor` — and any
`oceanschedules-process` handlers) need the **same** two-part change:

**(a) Handler stays on the Lambda runtime.** Keep `com.amazonaws.services.lambda.runtime.*`
(`RequestHandler`, `Context`) and `...runtime.events.*` (`SQSEvent`, `SNSEvent`, `S3Event`,
`DynamodbEvent`, `ScheduledEvent`) — those are `aws-lambda-java-core`/`-events`, **not** the AWS SDK,
and do not change.

**(b) Replace every AWS **client** with the cloud-sdk equivalent, always passing an explicit region
**and** credentials provider.** This is exactly the ION-16387 fix pattern:

```java
// region: from the Lambda-injected AWS_REGION, with a safe fallback
private static AwsRegionWrapper resolveRegion() {
    try {
        Region r = new DefaultAwsRegionProviderChain().getRegion();
        if (r != null) return AwsRegionWrapper.of(r.id());
    } catch (Exception e) { /* log */ }
    return AwsRegionWrapper.of(Region.US_EAST_1.id());
}

// credentials: the Lambda execution-role creds are injected as reserved env vars;
// DefaultCredentialsProvider resolves them via EnvironmentVariableCredentialsProvider.
private static AwsCredentialsProviderWrapper resolveCredentialsProvider() {
    return AwsCredentialsProviderWrapper.of(DefaultCredentialsProvider.create());
}
```

Then per service:
- **SSM/Parameter Store** (`AWSSimpleSystemsManagement`) → `ParameterStoreClientFactory.createParameterStore(
  AwsParameterStoreConfig.builder().region(resolveRegion()).credentialsProvider(resolveCredentialsProvider()).build())`.
  **⚠ Critical:** the `AwsParameterStoreConfig` builder **requires** a non-null credentials provider
  (`BaseAwsConfig` validation) — omitting it throws `IllegalArgumentException: CredentialsProvider must
  not be null` at cold start (this was the ION-16387 outage on outbound-poller/error-email).
- **SQS** (`AmazonSQS`) → `MessagingClientFactory.createConfiguredClient(AwsMessagingClientConfig.builder()
  .queueUrl(...).region(resolveRegion()).credentialsProvider(resolveCredentialsProvider())...build(), converter)`.
- **S3** (`AmazonS3`) → `StorageClientFactory.createS3Client(AwsStorageConfig.builder()
  .region(resolveRegion()).credentialsProvider(resolveCredentialsProvider()).build())`.
- **SNS** → cloud-sdk notification API (region + credentials likewise).
- **DynamoDB (entity/table access)** → cloud-sdk **`DatabaseRepository`** via
  `DynamoRepositoryFactory.createRepository(DynamoDbClientConfig, table, EntityClass, repoConfig)` with
  a `DynamoDbClientConfig` that carries `region(resolveRegion())` + `credentialsProvider(resolveCredentialsProvider())`.
  Migrate any `@DynamoDBTable` v1 models to cloud-sdk `@Table` + v2 `@DynamoDbBean` beans/converters.
  Follow the `*Dao` + `*DynamoModule` pattern (e.g. booking `BookingDetailDao`/`BookingDynamoModule`).
  **Do not hand-build a raw `DynamoDbClient`.** For generic raw-item reads only, use
  `DynamoRepositoryFactory.createDynamoDbClient(config)` (configured low-level client) — see §E.
- **KMS** (`registration-archive`, `bounceback-email`) → direct v2 `KmsClient` with region + creds.

**(c) pom:** drop `com.amazonaws:aws-java-sdk-*`, add `cloud-sdk-api` + `cloud-sdk-aws`; keep
`aws-lambda-java-core`/`-events`. Add DynamoDB-Local integration tests via `dynamo-integration-test`
for any DynamoDB path (mirror visibility/booking `*DaoIT`).

**(d) Tests/coverage:** add unit tests for the new client wiring (assert a client is built and that the
credentials provider is non-null — this reproduces/guards the ION-16387 failure) and integration tests
for DynamoDB. Sonar gate is 80% on new code — see the ION-16387 doc for the `resolveRegion(Supplier<Region>)`
testability seam used to cover the region success/null/exception branches deterministically.

> `lambda/booking-outbound` is effectively **already clean** — it uses no AWS SDK client at all (only
> `com.amazonaws.util.StringUtils`), so it only needs the trivial-residue cleanup in §D, not a client
> migration.

## §D. Trivial residue in otherwise-migrated modules (safe-removal analysis)

These are `com.amazonaws.*` references in modules that are otherwise on cloud-sdk/2.x. Classified by
whether the v1 dependency can be dropped safely.

| Module / class | v1 reference | Safe to remove? | Action |
|---|---|---|---|
| **network** — `MessageRegisterService.java`, `BlacklistEmailDao.java`, models | `com.amazonaws.util.CollectionUtils`, `com.amazonaws.util.StringUtils` | **Yes** | Pure utility helpers. Replace with `org.apache.commons`/Guava/JDK equivalents (`CollectionUtils.isNullOrEmpty` → `col == null || col.isEmpty()`; `StringUtils` → `org.apache.commons.lang3.StringUtils`). Then the v1 dep is gone from these files. |
| **tx-tracking** — one class | `com.amazonaws.util.IOUtils` | **Yes** | Replace with `java.io`/`com.google.common.io.ByteStreams` / `IOUtils` from commons-io. |
| **shipment-loader** — one class | `com.amazonaws.services.dynamodbv2.model.AttributeValue` (v1) | **Yes, with care** | This is a v1 DynamoDB model type. Migrate the surrounding read to the v2 low-level `software.amazon.awssdk.services.dynamodb.model.AttributeValue` (or Enhanced). Requires touching the DynamoDB call, not just an import swap. |
| **booking-downstream-processor**/`booking-cargoscreen` | real `AmazonS3`/SQS v1 | **No — real migration** | Listed in §1.7, not trivial residue. |
| **lambda/booking-outbound** | `com.amazonaws.util.StringUtils` (only) | **Yes** | Replace with commons/JDK. Also **remove the unused `aws-java-sdk-dynamodb` / `aws-java-sdk-ssm`** pom deps (no matching imports — dead dependencies). |
| **visibility** — `visibility-matcher/MatchingProcessor.java`, `visibility-s3-archiver/VisibilityS3Archiver.java` | `com.amazonaws.services.dynamodbv2.model.OperationType` | **Deferred** | This is the DynamoDB **Streams** event op-type enum used when handling `DynamodbEvent` records. It comes with the Lambda/DynamoDB-events path. Can be replaced by comparing the event's `eventName` string (`"INSERT"/"MODIFY"/"REMOVE"`) or the v2 enum, but it is low-risk residue; migrate opportunistically. |
| **visibility** — `visibility-itv-gps-processor/GPSEventProcessor.java` | `com.amazonaws.services.s3.event.S3EventNotification` | **Deferred** | S3 event-notification model for parsing S3→Lambda events; ships with `aws-lambda-java-events`/`aws-java-sdk-s3`. Keep until the event-parsing is moved to the v2/`aws-lambda-java-events` model. |
| **visibility** — `visibility-inbound/config/ElasticSearchClientModule.java`, `visibility-inbound/aws/AwsRequestSigner.java` | `com.amazonaws.auth.AWS4Signer`, `com.amazonaws.DefaultRequest`, `com.amazonaws.http.HttpMethodName`, `AWSCredentialsProvider`, `DefaultAWSCredentialsProviderChain`, `Signer` | **NO — required** | **Must keep** the AWS **v1 signer** (`aws-java-sdk-core`) to sign requests to **Elasticsearch** via the Jest client. Removing it breaks ES auth. It can only be retired as part of the **Jest→OpenSearch** migration (the OpenSearch SDK/`aws-sdk-java-v2` request signer replaces it). Keep `aws-java-sdk-core` scoped to these two classes until then. |

**Elasticsearch/Jest note (applies broadly):** many modules still declare `jest` /
`elasticsearch-rest-high-level-client` (network, oceanschedules, oceanschedules-process, visibility,
shipping-instruction, booking-downstream-processor, tx-tracking, partner-integrator). That is the
**Elasticsearch** client, a **separate** migration (OpenSearch SDK). Where AWS-signed ES requests are
made (visibility-inbound; oceanschedules-process `aggregator`/`loader`; the `elasticsearch-purge`
lambda), the **v1 `AWS4Signer` must stay** until OpenSearch. Do **not** remove `aws-java-sdk-core` from
those modules during the AWS-SDK migration.

## §E. DynamoDB access — always via cloud-sdk (repository first, configured client for raw)

**Rule:** do **not** construct a raw `software.amazon.awssdk.services.dynamodb.DynamoDbClient` by hand in
application code. cloud-sdk owns DynamoDB access, in two layers:

1. **Entity/table access (the default) — cloud-sdk `DatabaseRepository`.** The repository interface
   `com.inttra.mercury.cloudsdk.database.api.DatabaseRepository<T, ID extends EntityId>` provides
   `findById`, `save`, `update`, `saveIfNotExist`, `query(QuerySpec)`, `batchSave`, `export`, `delete`,
   `count`, etc. Create it with
   `DynamoRepositoryFactory.createRepository(DynamoDbClientConfig, tableName, EntityClass, DynamoRepositoryConfig)`
   (or `createEnhancedRepository` / `createStandardRepository`). Entities are annotated with the cloud-sdk
   `@Table(name=...)` plus the v2 Enhanced annotations `@DynamoDbBean`, `@DynamoDbPartitionKey`,
   `@DynamoDbSortKey`, and `@DynamoDbConvertedBy(<AttributeConverter>)`. This is the pattern used by
   **every** migrated module — auth (`TokenDao`/`AuthDynamoModule`), booking
   (`BookingDetailDao`/`BookingDynamoModule`), network (`SubscriptionsDao`), registration
   (`RegistrationDao`), rates, value-added-service, webbl, visibility (`ContainerEventDao`),
   booking-bridge, bill-of-lading-v2 — typically as a `*Dao` wired by a Guice `*DynamoModule`. New
   DynamoDB code (including the remaining lambdas and Spark modules) should follow this, **not** a raw
   client.
   - `DynamoDbClientConfig` carries `region` + `credentialsProvider` (and http/retry/endpoint) and is
     validated exactly like `BaseAwsConfig` (`Region must not be null`, `CredentialsProvider must not be
     null`) — the same failure family as ION-16387, so the same region/credentials wiring applies.

2. **Generic raw-item access (the exception) — cloud-sdk `createDynamoDbClient(config)`.** When the data
   has no fixed entity shape — e.g. reading whatever attributes a DynamoDB **Streams** record or an
   archival row contains as a `Map<String,AttributeValue>` — the entity-based repository does not fit.
   In that case still go through cloud-sdk: `DynamoRepositoryFactory.createDynamoDbClient(DynamoDbClientConfig)`
   returns a **configured** low-level v2 `DynamoDbClient` (region, credentials, HTTP pool, retry all set
   by cloud-sdk). Use that; do not hand-roll `DynamoDbClient.builder()`.

**The "other module" — `visibility-s3-archiver` `HandlerSupport.getDynamoDbClient()`.** This is the one
place that currently builds a **raw** `DynamoDbClient` directly. Its javadoc explains why: it performs a
*generic raw-item DynamoDB read that returns arbitrary stored attributes as a map and has no entity-based
cloud-sdk equivalent* (it archives DynamoDB Streams records of many shapes), so an entity repository can't
be used. That rationale is valid for the raw-read requirement, **but** the client should still be obtained
from cloud-sdk via `DynamoRepositoryFactory.createDynamoDbClient(config)` (config carrying region +
`AwsCredentialsProviderWrapper.of(DefaultCredentialsProvider.create())`) rather than a hand-built
`DynamoDbClient.builder()`. On the current `develop` this method also omits region/credentials entirely;
the ION-16387 fix (branch `bugfix/ION-16387`) already adds explicit `region` + `credentialsProvider` to it.
**Recommended follow-up:** route `getDynamoDbClient()` through `createDynamoDbClient(DynamoDbClientConfig)`
so region/credentials/retry come from cloud-sdk config uniformly — same as the repository path. (Same
applies to `oceanschedules-process/aggregator` `DynamoSparkService` in §1.3.1.)

---

# 4. Priority / grouping suggestion

1. **Self-contained, high impact:** `mft-s3-aqua-appia` (`aw-bridge-shared` centralizes all clients) —
   clean, well-bounded migration.
2. **Standalone lambdas (§C):** `lambda/auth-tokens-archive`, `bounceback-email`,
   `optionalvalidation-archive`, `subscription-archive`, `registration-archive`, `partner-integration`
   — each small, follow the booking/visibility lambda template. (`booking-outbound` = residue-only;
   `elasticsearch-purge` = ES-only, defer with OpenSearch.)
3. **DynamoDBMapper-heavy:** `bill-of-lading` (mirror `bill-of-lading-v2`), `partner-integrator`,
   `oceanschedules`.
4. **Messaging/S3-heavy multi-modules:** `oceanschedules-process`, `watermill-publisher`,
   `partner-integrator`, `shipping-instruction`, `booking-downstream-processor`. Watch for special
   cases: `amazon-sqs-java-extended-client-lib` (large-payload SQS), `emr-dynamodb-hadoop` /
   `elasticsearch-spark` (Spark/EMR — no direct cloud-sdk path).
5. **Trivial residue (§D):** quick cleanups (network/tx-tracking util, booking-outbound) — do anytime.
6. **Do NOT touch during this migration:** deprecated libs (`atlantida`, `dynamo-client`,
   `email-sender`); Jest/Elasticsearch signers (keep v1 until OpenSearch).

## Appendix — verification commands used
```powershell
# per-module v1 service usage (imports), excluding lambda runtime
Select-String -Path <module>\src\main\java\**\*.java -Pattern '^\s*import\s+(com\.amazonaws\.[^;]+);'
# per-module AWS pom deps
Select-String -Path <module>\**\pom.xml -Pattern '<artifactId>([^<]*(aws-java-sdk|aws-lambda-java|amazon-sqs|cloud-sdk|elasticsearch|jest)[^<]*)</artifactId>'
# integration-test-commons history
git --no-pager log --oneline -- libs/integration-test-commons
```
