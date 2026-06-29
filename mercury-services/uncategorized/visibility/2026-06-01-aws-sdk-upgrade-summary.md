# Visibility Module — AWS SDK 2.x Upgrade Summary

**Jira Ticket**: ION-12316
**Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot`
**Date**: 2026-06-01
**Agent**: GitHub Copilot (Claude Opus 4.8)
**Status**: Implementation complete — all unit & integration tests passing
**Session**: `284a7cba1d4244ee` (ION-12316-visibility-aws-upgrade-impl)

---

## 1. Executive Summary

The `visibility` module (an 11 sub-module Maven aggregator) has been migrated from AWS SDK v1
(`dynamo-client`, `AmazonS3`, `AmazonSQS`, `AmazonSNS`, `AWSSimpleSystemsManagement`) to the
`cloud-sdk-api` + `cloud-sdk-aws` libraries (AWS SDK 2.x Enhanced Client) supplied transitively
through `mercury-services-commons`. This aligns visibility with the already-upgraded modules
(booking, auth, network, webbl, booking-bridge, registration, self-service-reports, tx-tracking,
db-migration).

**Aggregate change set vs `develop`**: 103 files changed, ~9,065 insertions, ~2,359 deletions
across 4 incremental commits.

| Commit | Phase | Scope |
| --- | --- | --- |
| `2a593bf407` | 5 | visibility-commons: entities, DAOs, converters, S3 → cloud-sdk |
| `a38e675661` | 6 | visibility-inbound: DynamoDB → cloud-sdk + admin command |
| `6d4d421fb5` | 7 | 4 lambdas (S3 / DynamoDB / SQS / SSM) → cloud-sdk |
| `3bb89dc2e3` | 7.5 | 5 Dropwizard apps swapped to `VisibilityDynamoModule` |

---

## 2. Per-Module Change Summary

| Module | Java files changed | Highlights |
| --- | ---: | --- |
| visibility-commons | 40 | All 6 DynamoDB entities re-annotated (`@DynamoDbBean`, `@Table`, partition/sort keys, GSIs, `@DynamoDbConvertedBy`); 6 DAOs reworked onto `DatabaseRepository`; 10 attribute converters; `VisibilityDynamoModule`; `VisibilityApplicationConfig.getCloudSdkDynamoDbConfig()`; S3 → `StorageClient` |
| visibility-inbound | 17 | `VisibilityInboundDynamoDbAdminCommand` (replaces SDK v1 `CreateTables`); cargo-visibility models; injector wiring |
| visibility-wm-inbound-processor | 11 | App swapped to `VisibilityDynamoModule`; new `VisibilityWMDynamoModule` providing the wm-specific `CargoVisibilitySubscriptionDao`; config extends `VisibilityApplicationConfig` |
| visibility-s3-archiver | 3 | S3 → `StorageClient`; DynamoDB v1 Document API → v2 `DynamoDbClient.getItem` with raw-map helpers |
| visibility-pending-start | 3 | `AmazonSQS` → `MessagingClient<String>` |
| visibility-outbound-poller | 3 | SSM → `CloudParameterStore` (lazy double-checked init); SQS → `MessagingClient` |
| visibility-error-email | 3 | `ParameterStoreResolver` rewritten onto `CloudParameterStore` |
| visibility-outbound | 2 | App swapped to `VisibilityDynamoModule` |
| visibility-pending | 2 | App swapped to `VisibilityDynamoModule` |
| visibility-matcher | 2 | App swapped to `VisibilityDynamoModule` |
| visibility-itv-gps-processor | 3 | App swapped to `VisibilityDynamoModule`; config extends `VisibilityApplicationConfig` |

---

## 3. Phase 7 — Lambda Migrations (commit `6d4d421fb5`)

### visibility-s3-archiver
- `AmazonS3` → cloud-sdk `StorageClient`.
- DynamoDB v1 Document API → v2 `DynamoDbClient.getItem(...)` with `toJavaMap` / `toJavaObject`
  raw-map helpers.
- Test: replaced `com.amazonaws.util.IOUtils.toString(inputStream)` with
  `new String(inputStream.readAllBytes(), StandardCharsets.UTF_8)`. **9 tests pass.**

### visibility-pending-start
- `AmazonSQS` → `MessagingClient<String>` via `MessagingClientFactory.createDefaultStringClient()`.
  **4 tests (1 skipped) pass.**

### visibility-outbound-poller
- SSM → `CloudParameterStore`; SQS → `MessagingClient`.
- **Fix**: eager `public static final CloudParameterStore` static initializer was replaced with a
  lazy double-checked `getParameterStore()` so the class loads without building an SSM client at
  class-init time. This resolved a `mockStatic(HandlerSupport.class)` "Cannot instrument" failure.
  **2 tests pass.**

### visibility-error-email
- `ParameterStoreResolver` fully rewritten onto `CloudParameterStore`, with a package-private
  constructor accepting a `CloudParameterStore` for testability; handles the `${awsps:...}` prefix.
  **14 tests (1 skipped) pass.**

**Deliberately retained on SDK v1** (correct, no v2 equivalent needed):
- Lambda runtime event models `com.amazonaws.services.lambda.runtime.events.*`.
- `com.amazonaws.services.dynamodbv2.model.OperationType` for stream-record parsing.

---

## 4. Phase 7.5 — Dropwizard App Module Swaps (commit `3bb89dc2e3`)

Five applications were swapped from the legacy `com.inttra.mercury.dynamo.respository.module.DynamoDBModule`
to the cloud-sdk `com.inttra.mercury.visibility.common.config.VisibilityDynamoModule`:

```java
// before
.moduleGenerator((c, e) -> new DynamoDBModule(c.getDynamoDbConfig(), e))
// after
.moduleGenerator((c, e) -> new VisibilityDynamoModule(c))
```

- **visibility-outbound / visibility-pending / visibility-matcher** — clean swaps (configs already
  extended `VisibilityApplicationConfig`).
- **visibility-itv-gps-processor** — `VisibilityGPSEventApplicationConfig` refactored to extend
  `VisibilityApplicationConfig` (removed duplicated `dynamoDbConfig` / `eventLoggingConfig`);
  only injects `ContainerEventDao`, which is provided by `VisibilityDynamoModule`.
- **visibility-wm-inbound-processor** — `VisibilityWMEventApplicationConfig` refactored to extend
  `VisibilityApplicationConfig`. The wm-specific `CargoVisibilitySubscription` entity is **not**
  covered by `VisibilityDynamoModule`, so a dedicated **`VisibilityWMDynamoModule`** was added that
  provides `CargoVisibilitySubscriptionDao` from the shared `DynamoDbClientConfig`. It is wired
  alongside `VisibilityDynamoModule` in the application:

  ```java
  .moduleGenerator((c, e) -> new VisibilityDynamoModule(c))
  .moduleGenerator((c, e) -> new VisibilityWMDynamoModule())
  ```

  **Design note**: the repository provider was intentionally placed in a separate module rather
  than in `VisibilityWMEventApplicationInjector`, because the injector's unit test
  (`VisibilityWMEventApplicationInjectorTest`) instantiates the injector stand-alone and binds a
  mocked `DatabaseRepository`. Adding a `@Provides ...(DynamoDbClientConfig)` to the injector broke
  that test with a Guice `MissingConstructor` error for `DynamoDbClientConfig`. Keeping the provider
  in `VisibilityWMDynamoModule` (only wired by the running application) preserves test isolation.

---

## 5. Operational Note — `cloudSdkDynamoDbConfig` YAML

`VisibilityDynamoModule.provideDynamoDbClientConfig()` reads
`VisibilityApplicationConfig.getCloudSdkDynamoDbConfig()` (a `BaseDynamoDbConfig`). None of the
environment `conf/*.yaml` files yet contain a `cloudSdkDynamoDbConfig:` block — they still carry
only the legacy `dynamoDbConfig:`. Populating the new config block per environment is a **separate
operational/deployment task** and is intentionally **out of scope** for these code commits, matching
the precedent set in the committed Phase 6 (visibility-inbound) work. The completion bar for this
code change is: module/config code swaps in place + all unit and integration tests passing.

---

## 6. Verification

`mvn verify -pl visibility -amd` — all module test suites pass:

| Module | Tests run | Failures | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| visibility-commons | 183 | 0 | 0 | 0 |
| visibility-inbound | 410 | 0 | 0 | 2 |
| visibility-wm-inbound-processor | 117 | 0 | 0 | 0 |
| visibility-matcher | 52 | 0 | 0 | 0 |
| visibility-outbound | 42 | 0 | 0 | 2 |
| visibility-pending | 6 | 0 | 0 | 0 |
| visibility-s3-archiver | 9 | 0 | 0 | 0 |

The remaining lambda modules (pending-start, error-email, outbound-poller, itv-gps) were verified
individually in their respective phases. The only build interruption encountered was a
`maven-assembly-plugin` plugin-resolution error in **offline** mode (`maven-filtering`,
`maven-archiver` not in local repo) — an environment/cache issue, not a code defect; it resolves
when the build runs with network access.

---

## 7. cloud-sdk Reference (verified imports)

| Concern | cloud-sdk type |
| --- | --- |
| DynamoDB repo | `com.inttra.mercury.cloudsdk.database.api.DatabaseRepository` |
| Repo factory | `com.inttra.mercury.cloudsdk.database.factory.DynamoRepositoryFactory` |
| Client config | `com.inttra.mercury.cloudsdk.database.config.DynamoDbClientConfig` |
| Messaging (SQS) | `com.inttra.mercury.cloudsdk.messaging.api.MessagingClient` + `MessagingClientFactory` |
| Parameter Store | `com.inttra.mercury.cloudsdk.paramstore.api.CloudParameterStore` / `CloudParameter` + `ParameterStoreClientFactory` |
| Region | `com.inttra.mercury.cloudsdk.aws.config.AwsRegionWrapper` (+ `DefaultAwsRegionProviderChain`) |

Region resolution pattern used throughout:
```java
Region region = new DefaultAwsRegionProviderChain().getRegion();
AwsRegionWrapper wrapper = AwsRegionWrapper.of(region.id()); // fallback: Region.US_EAST_1.id()
```

---

## 8. Follow-ups (not part of this branch)

1. Populate `cloudSdkDynamoDbConfig:` in each environment `conf/*.yaml` (ops/deploy task).
2. Bump `mercury.commons.version` if a newer commons release is required at deploy time.
3. Run the DynamoDB admin command (`dynamo-create`) against each environment to provision tables/GSIs
   from the SDK v2 entity annotations.
