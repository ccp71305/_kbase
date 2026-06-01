# `watermill` (aggregator + sub-modules) — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G6 (config). DynamoDB is **fully covered** by cloud-sdk: `WatermillOffsetDao`→`DatabaseRepository`, `DateToEpochSecond`→`DateEpochSecondAttributeConverter`, `DynamoTableCommand`→`DynamoDbAdminCommand`/`DynamoDbAdminUtil`; verify G4 only if an entity uses a version attribute. The gRPC stream consumers are not SQS, so G1 does not apply; use `dynamo-integration-test` for DynamoDB tests.
> Sections below are retained as the Option-A fallback reference.

> Module: `watermill` aggregator: `consumer-commons`, `itv-gps-consumer`, `cargoscreen-consumer`, `booking-inbound-consumer`, `visibility-inbound-consumer` (gRPC stream consumers; DynamoDB `watermill_offset` at-least-once) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws` + `dynamo-integration-test`. Session `83b822b011714117`.

## 1. Scope & AWS surface (the largest rewrite in the repo)
The watermill side-bus uses **DynamoDB v1 with the `DynamoDBMapper` data-modeling API** — which has **no drop-in equivalent** in AWS SDK v2 (v2 uses the **DynamoDB Enhanced Client** with a different annotation/schema model). AWS v1 usage spans every sub-module:
- **DynamoDB:** `AmazonDynamoDB`, `AmazonDynamoDBClientBuilder`, `datamodeling.{DynamoDBMapper, DynamoDBMapperConfig, DynamoDBTable, DynamoDBHashKey, DynamoDBAttribute, DynamoDBTypeConverter, DynamoDBTypeConverted}`, `model.{CreateTableRequest, ProvisionedThroughput, SSESpecification, StreamViewType}`, `util.TableUtils`.
- **Files (per consumer + `consumer-commons`):** `dynamodb/DynamoSupport`, `dao/WatermillOffsetDao`, `vo/WatermillOffset` (annotated VO), `vo/DateToEpochSecond` (type converter), `dynamodb/command/DynamoTableCommand`, `modules/WatermillConsumerModule`, `modules/ExternalServicesModule` (S3+SNS+SQS), `service/S3PublishService` (`AmazonS3` + `PutObjectResult`).
- **gRPC** stream consumption is unaffected (not AWS).

## 2. Migration concerns specific to watermill
1. **`DynamoDBMapper` → DynamoDB Enhanced Client (v2).** The `WatermillOffset` VO's `datamodeling` annotations (`@DynamoDBTable/@DynamoDBHashKey/@DynamoDBAttribute/@DynamoDBTypeConverted`) must be re-expressed with v2 Enhanced Client `@DynamoDbBean`/`@DynamoDbPartitionKey`/`@DynamoDbAttribute` (or a `TableSchema` builder). `DateToEpochSecond` (`DynamoDBTypeConverter`) → v2 `AttributeConverter`. **This is a real rewrite, not a rename.** Prefer routing it through `cloud-sdk-aws` Dynamo support if it provides a repository/abstraction; otherwise implement against the v2 Enhanced Client directly.
2. **`DynamoTableCommand`** (table create via `TableUtils` + `CreateTableRequest`/`ProvisionedThroughput`/`SSESpecification`) → v2 `DynamoDbClient.createTable` / Enhanced `createTable`. Preserve SSE + provisioned-throughput settings.
3. **`S3PublishService`** (`AmazonS3` + `PutObjectResult`) → `cloud-sdk-aws` `StorageClient` (the `PutObjectResult` is presumably ignored or only logged — verify and drop).
4. **`ExternalServicesModule` (S3/SNS/SQS)** → rebind to `cloud-sdk-aws` (same pattern as the hot-pipeline services), but note watermill **does not depend on `appianway`'s `shared`** in the same way — verify whether it reuses `shared` wrappers or builds its own clients. If it builds its own, it migrates **independently of `shared`** and can adopt `cloud-sdk-aws` factories directly.
5. **Offset semantics:** `watermill_offset` gives at-least-once delivery — the read/write/commit offset logic must be behavior-identical after the Enhanced Client rewrite. This is the highest-risk correctness area.

## 3. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8.
- **Option A (recommended):** keep watermill's own bootstrap; adopt `cloud-sdk-aws` (+ v2 Enhanced Client / `dynamo-integration-test`) for DynamoDB/S3/SNS/SQS; rewrite the mapper/VO/converter/table-command; keep Dropwizard 4 / JUnit 4.
- **Option B:** also adopt commons `InttraServer`/Dropwizard 5. Larger churn; only worth it if watermill is being modernized for other reasons.

Because watermill is a **self-contained side-bus**, it is the **best candidate to pilot the DynamoDB-v2 path** independently, and a reasonable place to evaluate `dynamo-integration-test`.

## 4. Maven impact (per sub-module)
Remove `com.amazonaws:aws-java-sdk-{dynamodb,s3,sns,sqs}`. Add `cloud-sdk-api` + `cloud-sdk-aws` (and `software.amazon.awssdk:dynamodb-enhanced` if used directly) and `dynamo-integration-test` (test). Define versions in the aggregator `dependencyManagement` (v2 BOM 2.30.24).

## 5. Test impact
- **`dynamo-integration-test`** (from mercury-services-commons) is the intended vehicle for DynamoDB integration tests under v2 — adopt it for the offset-DAO tests.
- Existing `WatermillOffsetDao`/`DynamoSupport` tests rewritten against the Enhanced Client.
- `S3PublishService` tests re-pointed to `StorageClient` fakes.
- gRPC consumer tests unaffected. JUnit 4 retained for unit tests (commons' own dynamo-integration-test may use Jupiter — keep watermill's own tests on JUnit 4 unless adopting the harness forces otherwise; flag if it does).

## 6. Recommendation
**Option A**, piloting the **DynamoDB Enhanced Client** rewrite here (isolated side-bus). Use `dynamo-integration-test`. Effort: **High** — the `DynamoDBMapper`→Enhanced-Client conversion across five sub-modules is the single biggest code change in the program.

## 7. Peer review outcome
Peer-reviewed (Explore subagent). Confirmed the DynamoDB `datamodeling` surface across all five sub-modules and that v2 has no `DynamoDBMapper` equivalent (Enhanced Client required). Reviewer notes incorporated: (a) **verify whether watermill depends on `appianway/shared`** — if not, it migrates independently and need not wait for `shared`; (b) the at-least-once **offset commit semantics** are the top correctness risk — add explicit equivalence tests; (c) consolidate the duplicated `DynamoSupport`/`WatermillOffsetDao`/`DynamoTableCommand` across sub-modules into `consumer-commons` during the rewrite to avoid five divergent conversions (note as an opportunity, not a mandate, to avoid scope creep); (d) confirm whether watermill's tests must move to Jupiter when adopting `dynamo-integration-test`. Recommendation unchanged.

## 8. Sequencing
**Independent track.** If watermill does not depend on `shared`, it can proceed in parallel with the hot-pipeline migration and serve as the DynamoDB-v2 pilot. Do `consumer-commons` first, then the four consumers.

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Offset semantics change → duplicate/lost delivery | Behavior-equivalence tests; `dynamo-integration-test` against real/local DynamoDB |
| `DynamoDBMapper`→Enhanced annotation gaps (converters, key schema) | Map each annotation explicitly; unit-test serialization round-trip |
| SSE / provisioned-throughput dropped in table create | Preserve in v2 `createTable`; assert |
| Five divergent conversions | Optionally centralize in `consumer-commons` |
| `dynamo-integration-test` forces Jupiter | Evaluate; isolate from JUnit-4 unit tests or accept per-module test-framework split (flagged) |
