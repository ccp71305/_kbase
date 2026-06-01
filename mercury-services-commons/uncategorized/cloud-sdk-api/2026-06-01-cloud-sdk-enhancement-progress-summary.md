# cloud-sdk-api / cloud-sdk-aws Enhancements (G1–G7) — Progress Summary

**Date:** 2026-06-01
**Jira:** ION-12310
**Driving prompt:** `.github/prompts/cloudsdk-enhancements-plan-design-implement.prompt.md`
**MCP session:** `9d86b1da903942c5` — "ION-12310 cloud-sdk Gap-Closure (G1–G7) Enhancements"
**Model:** Claude Opus 4.8 (GitHub Copilot)
**Parent branch:** `feature/ION-12310-commons-cloudsdk-refactoring`

---

## 1. Objective

Close the 7 documented gaps (G1–G7) that the `appianway` aws2x-upgrade design
(`appianway/shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md §1A.6`) requires from the shared
`cloud-sdk-api` (abstraction) and `cloud-sdk-aws` (AWS SDK 2.x) libraries so appianway can adopt
Option B (commons + cloud-sdk-* on Dropwizard 5) and depend only on the abstraction layer.

All work is **additive-only** (new types, new classes, `default` interface methods) to preserve
public API compatibility. AWS SDK 2.x only. Each gap is implemented on its own feature branch off
the parent, with its own design doc (kept untracked — `cloud-sdk-api/docs/` is gitignored), code,
and JUnit 5 + Mockito + AssertJ tests.

---

## 2. Gap index (master list)

| ID | Gap | Status |
|----|-----|--------|
| G1 | Concurrent, semaphore-bounded SQS listener + Task base | ✅ Done |
| G2 | `StorageClient.putObject` with user metadata + content-type | ✅ Done |
| G3 | S3 event-notification parsing (S3→SQS and SNS→SQS) | ✅ Done |
| G4 | DynamoDB optimistic-lock / version attribute + atomic counter | 🟡 Partial (core landed) |
| G5 | Thymeleaf email template engine | ⛔ Not started |
| G6 | Composable config-transform chain (commons) | ⛔ Not started |
| G7 | cloud-sdk-based health checks | ⛔ Not started |

---

## 3. Completed work

Each gap is on its own branch off `feature/ION-12310-commons-cloudsdk-refactoring`
(branches are **not yet merged** to parent and **not pushed**).

### G2 — `StorageClient.putObject` with metadata + content-type ✅
- **Branch:** `feature/ION-12310-cloudsdk-g2-putobject-metadata` — commit `bef4fa3`
- **cloud-sdk-api:** Two additive `default` overloads on `StorageClient`:
  - `putObject(bucket, key, byte[], Map<String,String> metadata, String contentType)`
  - `putObject(bucket, key, InputStream, long contentLength, Map<String,String> metadata, String contentType)`
  - Defaults delegate to the existing metadata-less overloads so all current implementations stay
    source-compatible.
- **cloud-sdk-aws:** `S3StorageClient` overrides both, building `PutObjectRequest` with
  `.metadata()` / `.contentType()` / `.contentLength()` (omitted when null/blank/empty), reusing the
  existing `validateInput` and `handleS3Exception` / `handleSdkException` / `handleUnexpectedException`
  helpers.
- **Tests:** `S3StorageClientPutObjectMetadataTest` (ArgumentCaptor asserts metadata/contentType/length;
  null + blank omission). Existing `S3StorageClientPutObjectTest` still green.

### G1 — Concurrent semaphore-bounded SQS listener + Task base ✅
- **Branch:** `feature/ION-12310-cloudsdk-g1-concurrent-sqs-listener` — commit `4ecd8fe`
- **cloud-sdk-api (messaging.api):** `MessageTask<T>`, `AbstractTask<T>` (template base over
  `QueueMessage<T>`), `ConcurrentListener` lifecycle interface — surfaces `QueueMessage<T>`, never the
  raw SDK v2 `Message`.
- **cloud-sdk-aws (messaging.aws.impl):** `ConcurrentSqsListener<T>` — semaphore-bounded
  `ThreadPoolExecutor` worker pool; delete-on-success semantics; start/stop lifecycle.
- **Factory:** `MessagingClientFactory` overload to build a concurrent listener.
- **Tests:** API-side `AbstractTask` test (cloud-sdk-api) + `ConcurrentSqsListener` impl test
  (cloud-sdk-aws).

### G3 — S3 event-notification parsing ✅
- **Branch:** `feature/ION-12310-cloudsdk-g3-s3-event-notification` — commit `62d0ee5`
- **cloud-sdk-api (storage.event):** `S3EventRecord` (record) + `S3EventParser` interface.
- **cloud-sdk-aws:** `S3EventParserImpl` — parses both S3→SQS and SNS-wrapped→SQS payloads,
  URL-decodes object keys, Jackson-based.
- **Factory:** `StorageClientFactory` method to obtain the parser.
- **Tests:** fixture-driven parser tests (12 cases) covering direct S3, SNS-wrapped, URL-encoded keys,
  malformed input.

### G4 — DynamoDB version attribute + atomic counter 🟡 (core landed)
- **Branch:** `feature/ION-12310-cloudsdk-g4-dynamo-version-attribute` — commit `a94e9ba`
- **cloud-sdk-api:**
  - `@DynamoDbVersionAttribute` — additive field marker for optimistic-locking version attributes.
  - `OptimisticLockException extends DynamoSupportException` — so existing catch-blocks keep working.
  - `DatabaseRepository.incrementAndGet(ID key, String counterAttribute)` — new `default` method
    (throws `UnsupportedOperationException` by default; additive).
- **cloud-sdk-aws:** `StandardDynamoRepository.incrementAndGet(...)` — concrete atomic-counter
  implementation via a DynamoDB `UpdateItem` `ADD` expression (the core `ControlNumberSequence` need
  that `appianway/transformer` calls out in G4).
- **Tests:** `StandardDynamoRepositoryIncrementAndGetTest` (4 cases) — all green; no regression in
  existing DynamoDB repository tests.

---

## 4. Remaining work

### G4 — remainder (to finish the gap)
- Wire optimistic-lock **conditional `UpdateItem`** path (version check → `OptimisticLockException`
  on `ConditionalCheckFailedException`).
- Register `VersionedRecordExtension` on the enhanced client in `EnhancedDynamoRepository`
  (it is currently built **without** extensions — see
  `cloud-sdk-aws/.../database/impl/EnhancedDynamoRepository.java`).
- Add a **DynamoDB-local integration test** (`@Category(IntegrationTests.class)` in
  `dynamo-integration-test`) exercising concurrent increments and a version conflict.

### G5 — Thymeleaf email template engine ⛔
- **Branch (planned):** `feature/ION-12310-cloudsdk-g5-thymeleaf-template-service`
- **cloud-sdk-aws only (no api change):** `ThymeleafTemplateService implements TemplateService`
  (mirror `HandlebarsTemplateServiceImpl`).
- `EmailClientFactory` overload + `EmailTemplateEngine` enum on `AwsSesEmailConfig`
  (default `HANDLEBARS` — preserves current behavior).
- Add `org.thymeleaf:thymeleaf` dependency — **run an OWASP dependency-check scan** and confirm no new
  high/critical CVEs before committing (respect the existing OWASP/Netty/Handlebars fixes documented
  in `cloud-sdk-aws/docs/`).
- Tests: `ThymeleafTemplateServiceTest` + factory engine-selection test.

### G6 — Composable config-transform chain (commons) ⛔
- **Branch (planned):** `feature/ION-12310-cloudsdk-g6-composable-config-chain`
- **commons only:** make `ConfigProcessingServerCommand`'s transform chain pluggable via a new
  `ConfigSourceTransform` SPI + ordered `configTransforms()` hook. Default chain (trim + awsps)
  unchanged.
- **Constraint:** commons must **not** depend on `cloud-sdk-aws` (decoupled via the
  `ParameterStoreLookup` SPI — see `commons/docs/2026-05-29-ParameterStoreLookup-refactor.md`; read it
  first). Honor that SPI.
- Tests: chain-ordering + default-behavior-preserved unit tests.

### G7 — cloud-sdk-based health checks ⛔
- **Branch (planned):** `feature/ION-12310-cloudsdk-g7-cloud-sdk-health-checks`
- **cloud-sdk-api:** `HealthProbe` interface + `HealthStatus` record — **no Dropwizard dependency in
  cloud-sdk-api**.
- **cloud-sdk-aws:** S3 / SQS / SNS / Dynamo probes over the injected clients.
- Tests: per-probe healthy/unhealthy unit tests with mocked clients.

---

## 5. Design docs (untracked — `cloud-sdk-api/docs/` is gitignored)

These stay local and are intentionally **not** committed:

- `2026-06-01-storage-putobject-metadata-copilot-design.md` (G2)
- `2026-06-01-concurrent-sqs-listener-copilot-design.md` (G1)
- `2026-06-01-s3-event-notification-parsing-copilot-design.md` (G3)
- `2026-06-01-dynamodb-version-attribute-copilot-design.md` (G4)
- `2026-06-01-thymeleaf-template-service-copilot-design.md` (G5)
- `2026-06-01-composable-config-transform-chain-copilot-design.md` (G6)
- `2026-06-01-cloud-sdk-health-checks-copilot-design.md` (G7)
- `2026-06-01-cloud-sdk-enhancement-progress-summary.md` (this file)

---

## 6. How to resume

1. Load MCP session `9d86b1da903942c5` (`session_get`) for full decision/finding/code_change history.
2. Finish **G4 remainder** on the existing `feature/ION-12310-cloudsdk-g4-dynamo-version-attribute`
   branch (conditional UpdateItem + `VersionedRecordExtension` + DynamoDB-local IT).
3. Then **G5 → G6 → G7**, each: new branch off
   `feature/ION-12310-commons-cloudsdk-refactoring`, implement api→aws→tests,
   `mvn package -pl cloud-sdk-api,cloud-sdk-aws -am` + `mvn test` (and `mvn verify` where IT applies),
   commit **code-only** (docs stay untracked).
4. Do **not** push, force-push, or open PRs without explicit confirmation.
5. Do **not** commit stray untracked files: `.claude/`, `cloud-sdk-aws/dynamodb-local-metadata.json`,
   `cloud-sdk-aws/effective-pom.xml`, `dynamo-integration-test/dynamodb-local-metadata.json`.

---

## 7. Hard constraints (carried forward)

- **Additive-only** — no breaking public API changes (default methods, new types, new classes).
- **AWS SDK 2.x only** in cloud-sdk-aws.
- Align with existing client / repository / factory / Guice patterns.
- Do **not** modify `appianway` files (it is the consumer that documented the gaps).
- Do **not** regress the documented OWASP / Netty / Handlebars fixes in `cloud-sdk-aws/docs/`.
- `commons` must not depend on `cloud-sdk-aws` (G6).
- cloud-sdk-api must not depend on Dropwizard (G7).
