# `transformer` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.appian-way:transformer:1.0` (Contivo XSLT/Java mapping engine + control-number DynamoDB store) · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line: **`1.0.26-SNAPSHOT`** (Dropwizard 5.0.1, AWS SDK v2 BOM 2.30.24, Guice 7, Jackson 2.21). Target = **Option B**.
> **Master references (do not duplicate):** [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) §0/§10/§11 and [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md) §5/§6. The governing constraint is **ZERO IMPACT to existing mercury-services apps** ⇒ every cloud-sdk/commons change must be strictly additive/behavior-preserving.

---

## 0. What this document changes vs. the Copilot plan (critical review)

Reviewed against [`2026-05-31-transformer-aws2x-upgrade-plan-copilot.md`](2026-05-31-transformer-aws2x-upgrade-plan-copilot.md) / [`-DESIGN.md`](2026-05-31-transformer-aws2x-upgrade-DESIGN.md) and the actual transformer source. The Copilot inventory is accurate (transformer binds SQS/S3/SNS **and** DynamoDB; owns `ControlNumberSequence`/`ControlNumberSequenceDao`; Contivo is out of scope). Its **one material error** is proposing a *new* cloud-sdk DynamoDB version attribute (its "G4"). That is unnecessary.

| Copilot position | Evidence | This plan |
|---|---|---|
| **G4** — add a NEW `@DynamoDbVersionAttribute` to `cloud-sdk-api` + conditional-write/`incrementAndGet` helpers | `DynamoRepositoryFactory` builds `DynamoDbEnhancedClient.builder().dynamoDbClient(..).build()` → **DEFAULT extensions**, so AWS SDK v2 `VersionedRecordExtension` (and `AtomicCounterExtension`) are **already active**; `mercury-services` booking `SequenceId` already uses the **native v2** `software.amazon.awssdk.enhanced.dynamodb.extensions.annotations.@DynamoDbVersionAttribute` and relies on `repository.save()` honoring optimistic locking | **De-scoped (NON-GAP).** Migrate `ControlNumberSequence` to a cloud-sdk entity using `cloud-sdk-api` `@Table`/`@DynamoDbField` for the key + attributes and the **native v2** `@DynamoDbVersionAttribute` for the version field; use `EnhancedDynamoRepository` (built via `DynamoRepositoryFactory.createEnhancedRepository`). **No cloud-sdk change for DynamoDB.** |
| **G1** — concurrent SQS listener gap in cloud-sdk | mercury-services hand-roll their own listeners; appianway already owns `SQSListener`+`AsyncDispatcher` | **Not a transformer gap.** Inherit the retained `shared` listener/dispatcher on `MessagingClient<String>` (master plan §0, O-G1). |
| **G2** — S3 putObject-with-metadata | transformer writes transformed output to S3 and *may* set content-type/metadata | **Reference master S-G2 only** (the single program-wide required additive change). No transformer-specific gap. |
| **G6/G7** — config / health-check cloud-sdk changes | composed from public commons transforms; indicators re-point to injected clients | **Not transformer gaps** (master plan §0/§10). |
| Recommend Option A | stakeholder directive | **Option B** (master §7). |

**Net for transformer: ZERO module-specific cloud-sdk gaps.** DynamoDB optimistic locking is satisfied entirely by the existing, default-wired `VersionedRecordExtension`; S3 metadata (if any) is covered by master S-G2. transformer consumes cloud-sdk strictly as a client.

---

## 1. Executive summary

`transformer` is a standard SQS+S3+SNS consumer that **additionally** owns a small DynamoDB control-number store. It runs the **Contivo** XSLT/Java mapping engine (vendor runtime `com.contivo:commons:2.6.0`, **unrelated** to `mercury-services-commons:commons` — see §3). It binds AWS v1 clients in [`modules/ExternalServicesModule`](../src/main/java/com/inttra/mercury/transformer/modules/ExternalServicesModule.java) and uses `DynamoDBMapper` for the control-number sequence ([`ControlNumberSequenceDao`](../src/main/java/com/inttra/mercury/transformer/controlnumbers/sequence/ControlNumberSequenceDao.java)).

Under **Option B** (directed default) transformer:
1. rebinds `ExternalServicesModule` to cloud-sdk-aws factories (`MessagingClient<String>`, `StorageClient`, `NotificationService`) plus `DynamoRepositoryFactory` — replacing `AmazonDynamoDB`/`DynamoDBMapper`/`DynamoDBMapperConfig`;
2. migrates `ControlNumberSequence` to a cloud-sdk entity (`@Table`/`@DynamoDbField` + **native v2** `@DynamoDbVersionAttribute`) and `ControlNumberSequenceDao` to `EnhancedDynamoRepository` (`findAll()` ← v1 `scan`; `save()` keeps optimistic locking via the default `VersionedRecordExtension`);
3. inherits the retained `shared` `SQSListener`+`AsyncDispatcher` chain with element type `Message`→`QueueMessage<String>`;
4. leaves the Contivo engine, its jars and XSLT/Java mappings **untouched**;
5. drops `aws-java-sdk-{sqs,dynamodb}` and `aws-java-sdk-cloudwatchmetrics`.

**No transformer-specific cloud-sdk library change is required** (de-scopes Copilot G4).

---

## 2. Current state — AWS v1 inventory (verified, file:line)

- [`modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/transformer/modules/ExternalServicesModule.java)
  - `AmazonSQS` `amazonSQSForListener` (`sqs_listener`) / `amazonSQSForSender` (`sqs_sender`) — lines 44–47.
  - `AmazonS3` (`s3_read_put_copy`) — lines 48–49.
  - `AmazonSNS` (`sns_publish`) — lines 50–51.
  - `AmazonDynamoDB` + `DynamoDBMapper` + `DynamoDBMapperConfig` (CONSISTENT reads) — lines 53–63.
- [`controlnumbers/sequence/ControlNumberSequence.java`](../src/main/java/com/inttra/mercury/transformer/controlnumbers/sequence/ControlNumberSequence.java) — v1 `datamodeling` annotations:
  - `@DynamoDBIgnore private String keyId` (line 16); `Long id` (line 18); `Long version` (line 20).
  - `@DynamoDBHashKey @DynamoDBAttribute(attributeName="keyId") getHashKey()` (lines 23–27) — hash key.
  - `@DynamoDBVersionAttribute getVersion()` (lines 34–36) — optimistic lock.
  - `@DynamoDBAttribute(attributeName="id") getId()` (lines 43–45).
- [`controlnumbers/sequence/ControlNumberSequenceDao.java`](../src/main/java/com/inttra/mercury/transformer/controlnumbers/sequence/ControlNumberSequenceDao.java):
  - `DynamoDBMapperConfig` with `ConsistentReads.CONSISTENT` + `TableNameOverride(config.getDynamoDbSequenceTable())` — lines 24–29.
  - `findAllWithReadConsistency()` → `dynamoDBMapper.scan(ControlNumberSequence.class, new DynamoDBScanExpression(), cfg)` — lines 32–35.
  - `save(seq)` → `dynamoDBMapper.save(seq, cfg)` — lines 37–39.
- [`controlnumbers/sequence/ControlNumberSequenceProvider.java`](../src/main/java/com/inttra/mercury/transformer/controlnumbers/sequence/ControlNumberSequenceProvider.java):
  - block-allocation (`INCREMENT_RANGE=1000`); reads all rows (expects exactly one), `setId(id+RANGE)`, `save`; **catches `com.amazonaws.services.dynamodbv2.model.ConditionalCheckFailedException`** and retries (lines 4, 56–68). This is the optimistic-lock retry loop that must be preserved.
- SQS/S3/SNS data plane flows through the retained `shared` chain (v1 `com.amazonaws.services.sqs.model.Message` — see master plan §2.2).
- [`pom.xml`](../pom.xml): `aws-java-sdk-cloudwatchmetrics` (lines 100–104), `aws-java-sdk-sqs` (105–109), `aws-java-sdk-dynamodb` (110–114); BOM import lines 45–51. **Already on JUnit 5 Jupiter** (lines 125–141) — transformer is the one module already on the Jupiter platform. Contivo jars lines 166–319.

---

## 3. Findings

- **Contivo is unrelated to mercury-services-commons.** transformer's `com.contivo:commons:2.6.0` ([pom.xml:168–171](../pom.xml)) is the Contivo vendor runtime served from a local file repo (`contivo-lib/`, [pom.xml:18–34](../pom.xml)). It must **not** be confused with, or replaced by, `mercury-services-commons:commons:1.0.26-SNAPSHOT`. The Contivo engine, its jars (`lib/`/`contivo-lib/`) and XSLT/Java mappings are **non-AWS and entirely out of scope** — do not touch them, including the surefire `-Dcontivo.runtime.classpath=lib/maps` arg ([pom.xml:377](../pom.xml)).
- **DynamoDB optimistic lock needs no cloud-sdk change.** The control-number entity has exactly three logical fields — `keyId` (hash key), `id` (`Long` counter), `version` (`Long` optimistic-lock). The cloud-sdk `DynamoRepositoryFactory` constructs the enhanced client with **default extensions**, so AWS SDK v2 `VersionedRecordExtension` automatically increments/asserts `version` on `save()`/`update()` — exactly the v1 `@DynamoDBVersionAttribute` semantics that `ControlNumberSequenceProvider` relies on. The `ConditionalCheckFailedException` retry path maps to the v2 `software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException` raised by the extension (see DESIGN §6).
- **The v1 scan maps to a full read.** `findAllWithReadConsistency()` scans the whole (single-row) table. This maps to `EnhancedDynamoRepository.findAll()` (a `ScanEnhancedRequest`) — or, since the partition key is the constant `"SequenceId"`, to a consistent `findById("SequenceId", consistentRead=true)`. CONSISTENT reads are configured via `DynamoRepositoryConfig`/read options rather than a per-call `DynamoDBMapperConfig`.
- **cloudwatchmetrics v1** (`aws-java-sdk-cloudwatchmetrics`, [pom.xml:100–104](../pom.xml)) — verify whether it is actually used at runtime. If unused, **drop it**; if used, migrate to v2 `software.amazon.awssdk:cloudwatch` (transitive via cloud-sdk-aws / v2 BOM). No cloud-sdk-api wrapper is required for either outcome.
- **transformer already uses JUnit 5 Jupiter** ([pom.xml:125–141](../pom.xml)) — so the "new tests in JUnit 5" rule (master §8) is already the local convention; no Vintage bridge is needed for transformer's existing unit tests.
- S3 writes: the transformed canonical output is written via the `shared` `WorkspaceService`; if those writes carry user metadata/content-type they ride on master **S-G2** — no transformer-specific gap.

---

## 4. Option A — keep `shared`/DW4, delegate in place

Rebind `ExternalServicesModule` to cloud-sdk-aws factories; rewrite `ControlNumberSequence`/`ControlNumberSequenceDao` onto the cloud-sdk repository abstraction (native `@DynamoDbVersionAttribute` + default `VersionedRecordExtension`); keep DW4. Same cloud-sdk consumption and the same (zero) transformer-specific gap as Option B; differs only in the framework base. **Pros:** small blast radius, Contivo untouched, DynamoDB rewrite is identical to B. **Cons:** keeps appianway's bespoke DW4 base. Effort Medium; Risk Low–Medium.

## 5. Option B — adopt `commons` + `cloud-sdk-*` on Dropwizard 5 (directed default)

As Option A plus moving transformer's Dropwizard base/config onto `commons` (DW5) and the appianway composed config command (master §10). DynamoDB and AWS plumbing changes are identical. **Pros:** platform convergence; transformer is already on JUnit 5 so the testing side is low-friction. **Cons:** DW4→5 base migration adjacent to (but not touching) the Contivo runtime; verify Contivo + DW5 classpath/shade coexistence. Effort Medium–High; Risk Medium.

## 6. Comparison

| Criterion | Option A | Option B |
|---|---|---|
| Off AWS v1 | ✅ | ✅ |
| DynamoDB rewrite | identical (native `@DynamoDbVersionAttribute` + `EnhancedDynamoRepository`) | identical |
| Required cloud-sdk change | S-G2 only (program-wide; not transformer-specific) | S-G2 only |
| Impact on mercury-services | none | none |
| Framework churn | none | DW4→5 |
| Contivo risk | none (untouched) | none (untouched; verify shade/classpath) |
| Effort / Risk | Medium / Low–Med | Med–High / Med |

## 7. Recommendation

**Option B**, per the stakeholder directive and master §7. transformer carries **no module-specific cloud-sdk gap**: DynamoDB optimistic locking is satisfied by the native v2 `@DynamoDbVersionAttribute` + default `VersionedRecordExtension` already wired by `DynamoRepositoryFactory`, and S3 metadata writes (if any) ride on master S-G2. Option A remains the fallback with the identical DynamoDB design.

## 8. Peer review (self-reviewed vs source + master)

| Item | Finding | Status |
|---|---|---|
| Copilot G4 (new version attribute) | Default `VersionedRecordExtension` already active; booking uses native `@DynamoDbVersionAttribute` | **De-scoped — no cloud-sdk change** |
| Optimistic-lock retry preserved | `ConditionalCheckFailedException` (v1) → v2 same-named exception from the extension; `ControlNumberSequenceProvider` retry loop unchanged in behavior | **Resolved** |
| CONSISTENT reads | `DynamoDBMapperConfig.CONSISTENT` → `DynamoRepositoryConfig`/consistent `findById`/`findAll` read option | **Resolved** |
| Entity field mapping | `keyId`→`@Table` partition key; `id`→`@DynamoDbField`; `version`→native `@DynamoDbVersionAttribute` | **Resolved (DESIGN §2/§6)** |
| Scan semantics | single-row table; `findAll()` or constant-key `findById` | **Resolved** |
| Contivo scope | vendor runtime, unrelated to commons; out of scope | **Confirmed** |
| cloudwatchmetrics v1 | verify usage; drop or migrate to v2 cloudwatch | **Open question (§9)** |
| Already JUnit 5 | yes — new tests stay Jupiter | **Resolved** |

## 9. Open questions / dependencies / sequencing

- **cloudwatchmetrics usage** — confirm whether `aws-java-sdk-cloudwatchmetrics` is referenced; drop if unused else migrate to v2 `cloudwatch`.
- **Table-name config** — `config.getDynamoDbSequenceTable()` ([Dao:23](../src/main/java/com/inttra/mercury/transformer/controlnumbers/sequence/ControlNumberSequenceDao.java)) must flow into `DynamoRepositoryConfig` (table name) instead of `TableNameOverride`.
- **Sequencing:** after `shared` + `functional-testing`; pair the DynamoDB rewrite with the `watermill` Dynamo pilot to reuse `DynamoRepositoryFactory`/`dynamo-integration-test` patterns. Gate with `mvn -pl transformer -am verify`.
- Keep the `1.0.26-SNAPSHOT` line aligned across the program.

## 10. Configuration changes

Reference master plan **§10** (composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` chain). transformer-specific: route `getDynamoDbSequenceTable()` into `DynamoRepositoryConfig`; preserve the Contivo runtime classpath property; credentials/region remain env/IAM via v2 default providers.

## 11. cloud-sdk-api / cloud-sdk-aws / commons gaps (transformer)

- **DynamoDB optimistic lock — NO cloud-sdk change (de-scopes Copilot G4).** Use the **native v2** `software.amazon.awssdk.enhanced.dynamodb.extensions.annotations.@DynamoDbVersionAttribute` on `ControlNumberSequence.getVersion()`, plus `cloud-sdk-api` `@Table`/`@DynamoDbField` for key/attributes, and `EnhancedDynamoRepository` via `DynamoRepositoryFactory.createEnhancedRepository`. The factory's default enhanced client already applies `VersionedRecordExtension`, so `save()` enforces optimistic locking with no library change (same path `mercury-services` booking `SequenceId` relies on). Full mapping + scan→`findAll`/`findById` detail in DESIGN §6.
- **S3 metadata writes** — reference master **S-G2** only (the single required program-wide additive `StorageClient` overload). No transformer-specific gap.
- **Config / health checks** — no transformer-specific cloud-sdk change (master plan §0/§10; indicators re-point to injected cloud-sdk clients).

**Summary: transformer requires no module-specific cloud-sdk gap.**
