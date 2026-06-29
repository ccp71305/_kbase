# Visibility — Pending Changes & cloud-sdk Library Enhancements (ION-12316)

**Jira**: ION-12316 · **Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot` · **PR**: [#1066](https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/1066) → `develop`
**Date**: 2026-06-29 · **Author**: Arijit Kundu
**Purpose**: Single consolidated punch-list of (A) what still has to change in **visibility** before ION-12316 is release-clean, and (B) what enhancements are needed in the shared **cloud-sdk** (`cloud-sdk-api` / `cloud-sdk-aws`, `mercury-services-commons` `1.0.26-SNAPSHOT`).

> **Source docs reviewed** (visibility/docs):
> [2026-06-01 upgrade summary](./2026-06-01-aws-sdk-upgrade-summary.md) ·
> [2026-06-01 design/impl review](./2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md) ·
> [2026-06-23 rebase-refactor](./2026-06-23-visibility-rebase-refactor.md) ·
> [2026-06-24 sns-sqs-coverage](./2026-06-24-visibility-refactor-sns-sqs-coverage.md) ·
> [2026-06-25 sns-sqs-refactor (migration complete)](./2026-06-25-visibility-sns-sqs-refactor.md) ·
> [2026-06-26 AWS resource details](./2026-06-26-aws-service-resource-details.md) ·
> [2026-06-27 correctness review](./2026-06-27-claude-review-aws-services-upgrade.md).

---

## 0. Where the upgrade stands

The AWS SDK v1 → 2.x (cloud-sdk) migration of all visibility sub-modules is **functionally complete and on a single ION-12316 commit, pushed, PR #1066 open to `develop`**:

- **DynamoDB** — all 6 entities re-annotated (`@DynamoDbBean`), 6 DAOs on `DatabaseRepository`, 10 converters; entity↔live-table schema verified **1:1** against QA/CVT/PROD (2026-06-27). `create-tables` (v1) replaced by `dynamo-create` (`VisibilityInboundDynamoDbAdminCommand`), idempotent (describe→skip) on existing tables.
- **SQS + SNS** — full backbone migrated to cloud-sdk `MessagingClient<String>` / `NotificationService` (booking as template); delete/DLQ/retry semantics and on-wire payloads preserved byte-identical.
- **S3 / SSM / SES** — `StorageClient`, `CloudParameterStore` migrated; SES was already v2 and is unchanged.
- **Dependencies** — consolidated to a single `mercury.commons.version = 1.0.26-SNAPSHOT`; legacy `dynamo-client` removed; CI (Jenkins) booking-model pin fixed.
- **Tests** — `mvn -f visibility/pom.xml clean verify` green: **1009 unit + 40 integration (DynamoDB Local), 0 failures/errors**.

The two HIGH defects from the 2026-06-01 review (`metaData` S→M; missing dynamo config) and MEDIUM-4/MEDIUM-6 are **confirmed fixed**. What remains are latent/edge defects the green suite does not catch, plus deliberate library-level follow-ups.

> ### ⚠ Headline decision — F1: immediate vs planned
>
> The F1 fresh-create defect has **two** candidate fixes, and only one carries a cross-module retest cost:
>
> - **Immediate (ships with ION-12316) — module-local fix `B2` + IT hardening `C1`.** Touches **only** `visibility-inbound`. **No other module recompiles or needs retesting.** Existing QA/CVT/PROD/INT tables are unaffected (describe→skip); zero runtime risk (F1 is a table-*creation* defect only). This is the recommended path for the visibility release. See [§A.1](#a1-f1--fresh-create-attribute-name-mismatch-the-headline-pending-item).
> - **Planned (later cloud-sdk release) — library fix `B-1` (= old "Option A").** Makes `EntityTableMetadata` honor `@DynamoDbAttribute` for everyone. **Broad blast radius — requires re-validating every cloud-sdk consumer (booking, network, auth, webbl, ssr…) + a cloud-sdk release + version bump across all dependents.** Do **not** couple this to ION-12316. See [§B-1](#b-cloud-sdk-library-enhancements-needed).
>
> When `B-1` eventually lands, the `B2` override produces identical correct DDL → it becomes redundant-but-harmless and is simply deleted. **Note on naming:** the test-hardening step in §A.1 is labelled **`C1`** to avoid confusion with the **§C "Suggested sequencing"** section (the two are unrelated).

---

## A. Pending changes in **visibility**

Severity and IDs (`F1`–`F8`) carried from the 2026-06-27 correctness review.

| # | Sev | Area | Pending change | Status |
|---|-----|------|----------------|--------|
| **F1** | **HIGH** (latent — fresh-env / DR only) | DynamoDB table creation | `dynamo-create` derives key/GSI attribute names from **getter property names**, ignoring `@DynamoDbAttribute`. A freshly-provisioned `container_events` would get PK **`hashKey`** (not `id`) and `blNumber-index` keyed on **`billOfLading`** (not `blNumber`) → `ValidationException` on first PutItem, GSI queries return nothing. **Existing QA/CVT/PROD/INT are safe** (describe→skip, confirmed live). | **TODO — fix before any fresh-env/DR provisioning.** Immediate: module-local **B2 + C1** (visibility-inbound only). Library root-cause fix B-1 is the planned, all-modules-retest item. See §A.1. |
| **F8** | MEDIUM | DynamoDB TTL (outbound) | `ContainerEventOutbound` now declares `@TTL expiresOn`, but live `container_events_outbound` has **TTL DISABLED** in all envs. First `dynamo-create` run would issue `UpdateTimeToLive(enabled=true)` and start background-expiring rows on a ~2.7 B-item PROD table. | **TODO — decide intentionally** (see §A.2). Resolve before any unguarded PROD `dynamo-create`. |
| **F2** | MEDIUM | S3 (s3-archiver lambda) | `createDefaultS3Client()` regresses socket read-timeout **5 min → 30 s** and maxConnections **100 → 50** on the archive **write** path. | **TODO** — reapply legacy tuning, or consciously accept SDK-v2 defaults with documented rationale (see §A.3). |
| **F3** | LOW–MED | S3 (commons client) | New **30 s `apiCallTimeout`** (bounds the whole call incl. retries) where v1 was effectively unbounded. Practical risk LOW (small EDI/JSON payloads). | Accept + document, or set `clientExecutionTimeout` explicitly if unbounded behaviour must be preserved. |
| **F4** | LOW | Lambda (s3-archiver) | Numeric `N` attributes (e.g. `expiresOn`) archived to S3 JSON as **quoted strings** (`"177…"`) instead of numbers. | Return `BigDecimal` from `toJavaObject` for `N`; add a JSON-content assertion (test gap). |
| **F5** | LOW | DynamoDB streams | `ContainerEvent` has no stream annotation; a fresh table would lack the **KEYS_ONLY** stream the matcher/archiver depend on (parity with v1). | **TODO — user-accepted, deferred (~06-28).** Add cloud-sdk `@DynamoDBStream(KEYS_ONLY)` to `ContainerEvent` + IT assertion. |
| **F6** | LOW (info) | SNS | Confirm the cloud-sdk `SnsEventPublisher` payload (`JsonSupport.toJsonString(List<Event>)`) is byte-identical to the legacy `messaging` JSON. | Add a contract/IT, or capture one INT message and diff against a pre-upgrade sample. |
| **F7** | LOW (edge) | DynamoDB | `OffsetDateTimeTypeConverter.transformFrom(null)` throws (v1 returned null); unreachable in normal saves (enhanced client omits nulls). | Module side already guarantees non-null; optional guard test. Real fix is in cloud-sdk (see §B-7). |
| **SES** | LOW (opportunity) | Email | `visibility-inbound` `EmailSender` calls raw `SesClient` directly instead of the cloud-sdk `EmailService` wrapper. Not a defect (SES was never v1). | Follow-up: migrate `EmailSender` onto `cloudsdk.email.EmailService` for consistency. |

### A.1 F1 — fresh-create attribute-name mismatch (the headline pending item)

**Recommended for the immediate visibility release (no cross-module retest):** `B2` + `C1`. Both are confined to `visibility-inbound`; no other cloud-sdk consumer is touched.

- **B2** — Override `VisibilityInboundDynamoDbAdminCommand` to supply a **corrected `EntityTableMetadata` for `ContainerEvent`** (explicit attribute names: PK `id`; GSIs `blNumber-index`→`blNumber`, `bookingNumber-index`, `equipmentIdentifier-index`, `bkInttraReferenceNumber-equipmentIdentifier-index`, `siInttraReferenceNumber-index`), delegating `ContainerEventOutbound`/`ContainerEventPending` to the annotation-derived path (their getter names already equal attribute names). `EntityTableMetadata` has a public `@Builder` and `createTableWithGsisIfNotExists(EntityTableMetadata)` is `protected` → clean, self-contained, zero runtime risk, existing tables stay describe→skip.
- **C1** — Strengthen `VisibilityInboundDynamoDbAdminCommandIT` to assert **attribute names** (PK == `id`, `blNumber-index` key attr == `blNumber`, each GSI's key attrs + projection == KEYS_ONLY), closing the gap that let F1 pass unnoticed. *(Labelled `C1`, not `C`, to avoid clashing with the §C sequencing section.)*

**Why this is the safe immediate path:** the running services already read/write on `id`/`blNumber` correctly (the enhanced client honors `@DynamoDbAttribute`); F1 only affects the DDL emitted when `dynamo-create` builds a **brand-new** table. So `B2` changes nothing for existing environments and nothing at runtime — it has **zero blast radius outside visibility**.

**Planned (do NOT couple to ION-12316):** the library fix `B-1` makes `EntityTableMetadata` honor `@DynamoDbAttribute` for all consumers — that is the change with the all-modules retest cost; schedule it on a cloud-sdk release with full multi-module regression. After it lands, delete the `B2` override.
**Not recommended:** B1-rename (rename entity properties — ~60 refs across ~10 files, high churn, no runtime benefit).
**Until F1 is fixed: do not provision a new environment with `dynamo-create`.**

### A.2 F8 — outbound TTL divergence
- **Option 1 (recommended unless expiry is intended):** remove `@TTL` from `ContainerEventOutbound` (keep `expiresOn` as a plain `N` attribute via `DateEpochSecondAttributeConverter`), preserving the current "no background expiry" state that matches live/pre-upgrade.
- **Option 2:** keep `@TTL` but treat enabling TTL as a deliberate, separately-reviewed data-lifecycle change — first sample the `expiresOn` distribution on the ~2.7 B-item PROD table, then roll out in a controlled window (not via an incidental deploy-time `dynamo-create`).
- **Either way:** confirm whether the deploy pipeline runs `dynamo-create` automatically; if it does, **F1 and F8 must both be resolved before the next PROD deploy**.

### A.3 F2 — s3-archiver socket timeout / max-connections
- **Option 1 (recommended if large payloads possible):** mirror `visibility-commons` `bindStorageClient()` — build an `AwsStorageConfig` with a custom Apache `SdkHttpClient` (socket 5 min, connect 5 s, maxConn 100) + explicit `DefaultCredentialsProvider`, via `StorageClientFactory.createS3Client(config)` in the lambda `HandlerSupport` (~15 lines).
- **Option 2:** consciously accept SDK-v2 defaults (archive objects are small JSON, low concurrency) — **document the decision**.
- **Option 3 (depends on cloud-sdk gap §B-4):** once `AwsStorageConfig.Builder` gains timeout/maxConnections setters, set three fields instead of hand-building an Apache client.

### A.4 Operational / config discrepancies (from the 2026-06-26 inventory — not code defects, but verify before release)
1. **CVT uses the `inttra2_test` DynamoDB prefix** (shared with `test` env), except the WM-subscription processor → `inttra2_cv`. Confirm intentional.
2. **PROD `CargoVisibilitySubscription` naming mismatch** — prod config derives `inttra2_prod_CargoVisibilitySubscription` (does **not** exist); the only prod table is `inttra2_pr_CargoVisibilitySubscription` (**0 items**). CW-subscription flow may not be landing data — verify.
3. **wm-inbound-processor has no dedicated ECS service** in the VIS clusters though its queues exist — confirm where it is deployed.
4. **PROD `pi_statusevents` backlog ≈ 7.33 M messages** at capture — investigate consumer health (independent of the upgrade).
5. **OpenSearch (ES 6.8) is EOL** and domains don't enforce HTTPS / node-to-node encryption — flagged for a separate effort (OpenSearch SDK migration is planned; Jest gap §B-5 is related).

> **Cross-module caveat (not introduced by this upgrade):** `CargoVisibilitySubscription` is shared with `watermill-publisher/watermill-cargo-visibility-subscription`, still on **AWS SDK v1** (its upgrade is scheduled after visibility ships). The `LegacyDynamoDbDateAttributeConverter` fix (ISO-8601 `S`) keeps items byte-compatible for that still-v1 reader. The live `bookingNumber-index` is keyed on `carrierBookingNumber` (watermill-publisher's schema) — a pre-existing divergence to reconcile when watermill-publisher is upgraded; harmless here because visibility does not create that table.

---

## B. cloud-sdk library enhancements needed

These are gaps in `cloud-sdk-api` / `cloud-sdk-aws` (`mercury-services-commons` `1.0.26-SNAPSHOT`) surfaced by the visibility upgrade. Each currently has a local visibility workaround; the library fix removes the workaround for **all** consumers and should be scheduled with a planned cloud-sdk release (broad blast radius — re-validate booking/network/auth/webbl/ssr fresh-create paths).

| # | Gap | Evidence (visibility) | Current workaround | Proposed cloud-sdk enhancement |
|---|-----|-----------------------|--------------------|--------------------------------|
| **B-1** | **`EntityTableMetadata` ignores `@DynamoDbAttribute`** for **key & GSI attribute names** — derives them from the getter property name. (Root cause of **F1**.) | `extractKeySchema`/`extractAttributeDefinitions`/`extractGsiMetadata` → `getHashKey`→`hashKey`, `getBillOfLading`→`billOfLading`. | Module-level corrected `EntityTableMetadata` override (A.1 / B2). | When a key/GSI getter carries `@DynamoDbAttribute("x")`, use `"x"` as the attribute name. One lookup per getter; fixes every consumer once. |
| **B-2** | **`DynamoDbAdminCommand` ignores `@DynamoDbConvertedBy` on a key** — key types resolved by raw field reflection, so a converted key (e.g. `LocalDate`→`S`) the enhanced client persists fine cannot be **created** by the admin command. | `EntityTableMetadata.fromEntityClass` → `Unsupported attribute type for DynamoDB key: java.time.LocalDate` (found via the new IT; fixed by making `ContainerEventPending.createDate` a `String`). | Persist the key as the native scalar (`String`) it serializes to. | Derive the key `ScalarAttributeType` from the bean's `TableSchema` / the key converter's `attributeValueType()`, not the raw field type. |
| **B-3** | **No raw / schemaless `getItem`** in `cloud-sdk-api` `DatabaseRepository<T,K>` (bean-typed only). | `visibility-s3-archiver` archives **arbitrary** stored attributes (no `@DynamoDbBean`) → drops to a raw `DynamoDbClient`. | Direct `DynamoDbClient` in that one lambda (documented + IT-covered). | Add a `RawItemRepository` / `getItem(tableName, key) → Optional<Map<String,CloudAttributeValue>>` (+ factory) so lambdas don't bypass the abstraction. |
| **B-4** | **`AwsStorageConfig.Builder` lacks socket/connection-timeout & max-connections knobs**, and `createS3Client(config)` has **no default-credentials fallback** (unlike `createDefaultS3Client()`). (Drives **F2** / **F3**.) | `visibility-commons` `bindStorageClient()` and the s3-archiver must hand-build an `ApacheHttpClient` + explicit `credentialsProvider`. | Hand-built Apache client with the legacy 1s/5s/50 (and 5min/100 for archiver) values. | First-class `socketTimeout` / `connectionTimeout` / `maxConnections` setters + default-credentials fallback on `createS3Client(config)`. |
| **B-5** | **`cloud-sdk-aws` pulls a newer `io.searchbox:jest`** that breaks consumers compiled against the older Jest API (`AbstractAction.buildURI()` → `buildURI(ElasticsearchVersion)`). | `visibility-matcher` `TransactionScrollSearch` fails to compile once `cloud-sdk-api`/`-aws` is a **direct** dep. | `visibility-matcher` excludes `io.searchbox:jest` from `cloud-sdk-api` and keeps `cloud-sdk-aws` transitive only. | Align/relocate the bundled Jest version, or shade `io.searchbox` inside `cloud-sdk-aws`, so a direct dependency doesn't shift consumers' Jest API. (Becomes moot after the planned OpenSearch-SDK migration.) |
| **B-6** | **Removing legacy `dynamo-client` destabilises transitive Guava** — it had been pinning Guava 33.5.0; once removed, `mybatis-guice` drags Guava 18.0 in and Guice 7 fails (`ImmutableMap$Builder.buildOrThrow()` `NoSuchMethodError`). | `VisibilityErrorEmailModuleTest` → `NoSuchMethodError … buildOrThrow`. | Pin `com.google.guava:guava:33.5.0-jre` directly in `visibility-error-email`. | Have `commons` (or a shared BOM) manage a single Guava version so module-level dependency churn cannot down-mediate it. |
| **B-7** | **`OffsetDateTimeTypeConverter.transformFrom(null)` throws** (v1 returned null). (Drives **F7**.) | Unreachable in normal saves (enhanced client omits nulls); module cannot fix locally (converter owned by cloud-sdk). | Module guarantees non-null. | Make `transformFrom(null)` return `AttributeValue.builder().nul(true).build()` — defensive, symmetric with the other converters. Bundle with the B-1/B-2 pass. |

---

## C. Suggested sequencing

> This §C is the **schedule**; it is unrelated to the test-hardening step `C1` in §A.1.

1. **Before merge of #1066 (visibility, ION-12316 scope — module-local only, no cross-module retest):** F1 via **`B2` + `C1`** (visibility-inbound only), decide F8, decide F2; resolve the A.4 config-discrepancy verifications (esp. #1, #2 — guard against unguarded `dynamo-create` on PROD).
2. **Fast-follow (visibility, low risk):** F4, F5 (already agreed), F6 contract test, F7 guard test, SES `EmailService` adoption.
3. **cloud-sdk backlog (separate release — this is the tier with the all-consumers retest cost):** B-1 (F1 root cause), B-2, B-3, B-4, B-7 together, each requiring re-validation of booking/network/auth/webbl/ssr fresh-create paths; B-5 folds into the OpenSearch-SDK migration; B-6 as a shared-BOM Guava pin.

> After B-1/B-2 land in cloud-sdk, remove the visibility `B2` override (A.1) to avoid drift — it produces identical correct DDL, so removal is safe.
