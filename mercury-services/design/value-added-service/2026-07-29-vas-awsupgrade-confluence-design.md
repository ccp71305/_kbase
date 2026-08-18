# ION-16110 Value Added Service — OWASP HIGH CVE Remediation + AWS SDK 2.x (cloud-sdk) Upgrade

<!-- Generated 2026-07-29 from:
       - value-added-service/docs/2026-07-24-vas-aws-upgrade.md          (implementation guide / work log)
       - value-added-service/docs/2026-06-30-value-added-service-aws2x-DESIGN-claude.md (initial design)
     Template: .github/prompts/designdocs/templates/architecture-template.md
     (mirrors https://confluence.dev.e2open.com/display/~akundu/Design+Doc+Template) -->

## Contents

<!-- info macro + TOC macro -->

---

## Contributors

| Role | Name |
|------|------|
| Author | @Arijit Kundu |
| Implementation | @Arijit Kundu |
| Jira Assignee | @Anand N S |
| Product Owner | @Mahendran Pandian |

---

## Summary

`value-added-service` (VAS) carried **6 OWASP HIGH CVEs** and was the last consumer of AWS SDK v1 in its area. This
change clears all HIGH findings and migrates every AWS interaction in the module — **DynamoDB** and **SNS** — from AWS
SDK v1 (`com.amazonaws.*`, `dynamo-client`, `DynamoDBMapper`) to the in-house **cloud-sdk** (`cloud-sdk-api` +
`cloud-sdk-aws`, AWS SDK 2.x Enhanced Client over Apache HTTP).

Every DynamoDB attribute encoding and the SNS payload shape are **wire-identical** to v1, so the 1.2 M existing PROD
items remain readable and the downstream SNS consumer is unaffected. There is no API, UI, or functional change.

**Status:** ✅ Verified in INT (local boot + ECS deployment, 2026-07-28); Jira **In QA**

---

## Requirements

| | |
|---|---|
| **Epic** | https://jira.dev.e2open.com/jira/browse/ION-15550 & Security Upgrade 26.3|
| **Story ID** | ION-16110 — *Jackson-2.21.0 Critical CVE* |
| **Target Release** | **26.2.3** (deployed INT artifact `centos:VAS-26.07.001` — build tag, not the release number) |
| **Scope** | `value-added-service` module only — DynamoDB + SNS surface, plus dependency upgrades |
| **Fix Version** | 26.2.3 |
| **Customer/Client** | None — internal security remediation, no customer-visible change |
| **Related Documents** (*If Any*) |  |

### Functional Requirements

- **No functional change.** All existing behaviour must be preserved exactly: VAS search, saved-response retrieval by
  id, real-time vessel-schedule visibility, and carrier (CMA-CGM / Hapag-Lloyd) integrations.
- Persist a value-added-service response with its carrier payload, INTTRA payload, audit block and 400-day expiry, and
  retrieve it by id with a **strongly consistent** read.
- Publish Hapag-Lloyd contract/routing events to the per-environment SNS topic.
- Provision the DynamoDB table and its GSI through the Dropwizard `dynamo-create` command, idempotently.

### Non-Functional Requirements

| # | Requirement | Target |
|---|---|---|
| 1 | OWASP dependency-check HIGH findings | **0** |
| 2 | DynamoDB on-wire fidelity | Byte-identical per attribute — existing items readable, new items readable by the old code path |
| 3 | SNS payload + topic ARN | Unchanged |
| 4 | Read consistency | Strongly consistent reads preserved (was `DYNAMO_READ_BEHAVIOUR.CONSISTENT`) |
| 5 | Prod classpath | No `com.amazonaws` DynamoDB/SNS dependency (test-scoped only) |
| 6 | Provisioning safety | `dynamo-create` idempotent — must not override live key schema, GSI projection, throughput, or TTL |
| 7 | Test coverage | Full local JaCoCo coverage of all new/changed classes |

### Acceptance Criteria

| # | Criterion | Result |
|---|---|---|
| 1 | OWASP post-scan reports 0 HIGH | ✅ 6 HIGH → **0 HIGH** (25 → 12 total) |
| 2 | `mvn -pl value-added-service verify` green | ✅ BUILD SUCCESS — 213 unit + 9 integration, 0 failures |
| 3 | App boots against `conf/int/config.yaml` | ✅ DynamoDB repository, SNS `NotificationService`/`EventPublisher`, `EventLogger` all wired |
| 4 | `GET /vas/services/ping` = 200 | ✅ `{"healthy":"true"}` locally and via ALB |
| 5 | INT ECS deployment reaches steady state | ✅ `VAS-dev` 1/1 running, rolloutState COMPLETED, 0 ERROR at startup |
| 6 | Existing v1-written items readable | ✅ Proven by DynamoDB-Local IT converter-fidelity tests |
| 7 | Null carrier/INTTRA payloads persist | ✅ Fixed in PR review — no `ValidationException` |
| 8 | Live table structure unchanged in all 4 envs | ✅ Entity annotations match INT/QA/CVT/PROD; nothing overridden |

### Jira Tickets (ext)

| Key | Summary | Type | Priority | Status | Assignee |
|-----|---------|------|----------|--------|----------|
| ION-16110 | Jackson-2.21.0 Critical CVE | Security Defect | Medium | In QA | Anand N S (reporter: Arijit Kundu) |

### Support Tickets (ext)

None.

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | Dropwizard (InttraServer, Guice) |
| Servlet Container | Jetty 12.1.9 |
| JAX-RS / API layer | Jersey — `ValueAddedServiceResource`, `RealTimeVesselVisibilityResource` |
| Build | Maven (`mvn -pl value-added-service verify`) |
| AWS SDK | **AWS SDK 2.30.24** via `cloud-sdk-aws` (was AWS SDK v1 1.12.652 + `dynamo-client`) |
| Database | DynamoDB — table `<env>_ValueAddedService` + GSI `valueAddedServiceBookingNumber-index` |
| Messaging | SNS — `<env>_sns_event` topic via cloud-sdk `NotificationService` |
| Shared library | `commons` **1.0.28-SNAPSHOT** (was `1.R.01.023`) |
| JSON | Jackson **2.21.4** (pinned via `jackson-bom`) |
| Test | JUnit 5, DynamoDB-Local (`dynamo-integration-test`), JaCoCo |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | commons is consumed as **`1.0.28-SNAPSHOT`** | Pre-requisite | **Closed** | A released commons `1.0.28` build is published |
| 2 | Native TTL is inconsistent across environments — INT **ENABLED** on `expiresOn`, QA/CVT/PROD **DISABLED** | Open Issue | Resolved | Pre-existing environment inconsistency, independent of this change. Entity deliberately declares no `@TTL`, so the admin command never enables/disables TTL and each environment's state is preserved. `expiresOn` is written as epoch-seconds `N` in every env — exactly the format native TTL consumes — so behaviour is correct either way |
| 3 | VAS Dropwizard provisioning command name is `dynamo-create` **before and after** | Assumption | Resolved | Confirmed from source: the old `AbstractDynamoCommand`'s only constructor is `super("dynamo-create", …)` and the new `DynamoDbAdminCommand` hardcodes the same name. VAS is the exception — visibility / booking / booking-bridge moved from a bespoke `create-tables`, VAS did not, so the VAS CI `$task` needs no change |
| 4 | `bookingNumber` GSI is provisioned but **unpopulated** by the write path | Assumption | Resolved | Behaviour preserved — the enhanced-client mapping does not start writing the attribute |
| 5 | cloud-sdk has no converter for the legacy `<fqcn>:<json>` (+ optional gzip/base64) format | Open Issue | **Open** | Worked around by porting `DynamoSupport`/`GZip` into the module. Proposed cloud-sdk enhancement: a reusable `JsonClassTaggedAttributeConverter<T>` in `cloud-sdk-aws` |

---

## High Level Design

### Architectural Overview (ext)

```
┌──────────┐   ┌───────────────────────────────┐   ┌──────────────────────────────┐   ┌────────────────┐
│  Client   │──▶│  JAX-RS resources             │──▶│  Client services + carrier   │──▶│  Carrier APIs   │
│           │   │  ValueAddedServiceResource    │   │  clients (CMA-CGM, Hapag)    │   │  (OAuth, REST)  │
│           │   │  RealTimeVesselVisibility…    │   │  UNCHANGED                   │   │  UNCHANGED      │
└──────────┘   └───────────────────────────────┘   └──────────┬─────────┬─────────┘   └────────────────┘
                                                              │         │
                                        ┌─────────────────────▼──┐   ┌──▼─────────────────────┐
                                        │ ValueAddedServiceDao    │   │ EventLogger            │
                                        └─────────────┬──────────┘   └──────────┬─────────────┘
                                                      │  ◀── MIGRATED ──▶       │
                                        ┌─────────────▼──────────────────────────▼─────────────┐
                                        │  cloud-sdk-aws  —  AWS SDK 2.30.24 + Apache HTTP      │
                                        │  DatabaseRepository<…>        NotificationService      │
                                        └─────────────┬──────────────────────────┬─────────────┘
                                                      ▼                          ▼
                                        ┌──────────────────────────┐  ┌────────────────────────┐
                                        │ DynamoDB                  │  │ SNS                    │
                                        │ <env>_ValueAddedService   │  │ <env>_sns_event        │
                                        │ + KEYS_ONLY GSI           │  │                        │
                                        └──────────────────────────┘  └────────────────────────┘
```

Only the shaded band changed. The REST layer, carrier integrations, OAuth flows, Parameter Store resolution
(`${awsps:}`) and swagger generation are untouched.

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | Full migration — commons `1.0.28` + Jackson `2.21.4` + cloud-sdk for DynamoDB *and* SNS, in one commit | Clears all HIGH CVEs; removes `com.amazonaws` from the prod classpath; aligns VAS with `booking`/`visibility` | Larger diff; requires per-attribute fidelity proof | ✅ |


### Data Flow — Before vs After (ext)

**Before (AWS SDK v1):**
```
POST /vas/search
  → ValueAddedServiceClientService: feature-flag + SCAC route
  → Carrier client: validate, map, call carrier (OAuth)
  → ValueAddedServiceDao extends DynamoDBCrudRepository
  → DynamoDBMapper (v1 ORM, @DynamoDBTable/@DynamoDBHashKey, dynamo-client)
  → DynamoDB PutItem
  → 200 [response]

Hapag event → commons EventLogger → SNSEventPublisher → AmazonSNS (v1) → SNS topic
```
**After (cloud-sdk / AWS SDK 2.x):**
```
POST /vas/search
  → ValueAddedServiceClientService: unchanged
  → Carrier client: unchanged
  → ValueAddedServiceDao: injected DatabaseRepository<DynamoDBValueAddedService, DefaultPartitionKey<String>>
  → Enhanced Client (@DynamoDbBean/@Table + ported DynamoSupport converters)
  → DynamoDB PutItem  — byte-identical attribute encodings
  → 200 [response]   (unchanged status, body, headers)

Hapag event → EventLogger (cloudsdk.notification.workflow.*) → NotificationService → SNS topic (same ARN)
```

---

## Low Level Design

### Server

The migration is annotation-and-wiring only; no business logic was rewritten. The fidelity-critical work is in the
attribute converters, because `carrierResponse` is a **generic `Object`** archived with the legacy `dynamo-client`
`DynamoSupport` format (`<fqcn>:<json>`, optionally gzip+base64 above a size threshold). cloud-sdk has no equivalent
converter, so `DynamoSupport`/`GZip` were ported verbatim into the module to guarantee byte-identical encoding.

#### Key Components and Changes (ext)

| # | Component | Location | Purpose | Key Changes |
|---|-----------|----------|---------|-------------|
| 1 | `pom.xml` | `value-added-service/` | Dependencies | commons `1.R.01.023` → `1.0.28-SNAPSHOT`; **removed** prod `aws-java-sdk-dynamodb 1.12.652` + `dynamo-client`; **added** `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test` (test), test-scoped `aws-java-sdk-dynamodb`; Jackson pinned to `2.21.4` via `jackson-bom` |
| 2 | `DynamoDBValueAddedService` | `…/vas/model/` | DynamoDB entity | v1 ORM annotations → `@DynamoDbBean` + `@Table(name="ValueAddedService")`; getter-level `@DynamoDbPartitionKey @DynamoDbAttribute("id")`; `bookingNumber` → `@DynamoDbSecondaryPartitionKey` + `@GsiConfig(projection = KEYS_ONLY)` |
| 3 | `Audit` | `…/vas/model/` | Nested audit block | `@DynamoDBDocument` → `@DynamoDbBean`; `OffsetDateTime` getters converted for DynamoDB while `@JsonFormat` is retained for the REST/event JSON path |
| 4 | `CarrierResponseAttributeConverter` | `…/vas/dynamodb/` | Generic-`Object` payload | **New** — v2 `AttributeConverter` delegating to the ported `DynamoSupport`; emits `S`. Returns `null` for null input so the attribute is omitted |
| 5 | `InttraResponseAttributeConverter` | `…/vas/dynamodb/` | `ValueAddedServiceResponse` payload | **New** — same pattern, same null handling |
| 6 | `support/DynamoSupport`, `support/GZip`, `support/DynamoSupportException` | `…/vas/dynamodb/support/` | Legacy encoding | **Ported** from `dynamo-client` for byte-identical `<fqcn>:<json>` (+gzip/base64) encoding |
| 7 | `ValueAddedServiceDao` | `…/vas/dao/` | Persistence | `extends DynamoDBCrudRepository` → injected `DatabaseRepository<…, DefaultPartitionKey<String>>`; `query(...)` → `findById` wrapped back into a 0..1 `List` to keep callers identical; consistent read preserved; 400-day `calcExpiresOn` unchanged |
| 8 | `ValueAddedServiceDynamoModule` | `…/vas/config/` | Guice | **New** — provides `DynamoDbClientConfig` (`consistentRead(true)`) and the `DatabaseRepository` |
| 9 | `ValueAddedServiceMessagingModule` | `…/vas/config/` | Guice | **New** — provides cloud-sdk `NotificationService` + `EventPublisher` |
| 10 | `ValueAddedServiceModule` | `…/vas/config/` | Guice | Dropped the `AmazonSNS` binding and `com.amazonaws.services.sns.*` imports; kept `Clock`, service definitions and the three multibinders |
| 11 | `ValueAddedServiceConfig` | `…/vas/config/` | Config binding | `dynamoDbConfig` type `DynamoDbConfig` → `BaseDynamoDbConfig`, annotated `@Valid @NotNull` |
| 12 | `DynamoValueAddedServiceTableCommand` | `…/vas/config/` | Table provisioning | `extends AbstractDynamoCommand` (dynamo-client, v1) → `extends DynamoDbAdminCommand` (cloud-sdk). Registered command name stays **`dynamo-create`** |
| 13 | `EventLogger` / `MetaData` usage | Hapag-Lloyd routing + contract clients | Event publishing | Re-pointed to `cloudsdk.notification.workflow.*` |
| 14 | `ValueAddedServiceApp` | `…/vas/` | Bootstrap | `DynamoDBModule` generator → `ValueAddedServiceDynamoModule` |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| DynamoDB | Persist + strongly-consistent read of value-added-service responses; table/GSI provisioning via `dynamo-create` | cloud-sdk `DatabaseRepository` (AWS SDK 2.30.24 Enhanced Client) |
| SNS | Publish Hapag-Lloyd contract/routing events | cloud-sdk `NotificationService` |
| Parameter Store | `${awsps:...}` resolution at startup | commons — **unchanged** |

#### DynamoDB Changes (ext)

No structural change. Entity annotations were verified against the **live tables in all four environments** — no
discrepancies:

| Env | Table | Partition Key | GSI `valueAddedServiceBookingNumber-index` | Throughput | TTL | Items |
|---|---|---|---|---|---|---|
| INT | `inttra_int_ValueAddedService` | `id` (S) HASH | `bookingNumber` (S) HASH, **KEYS_ONLY**, 5/5, ACTIVE | 5/5 PROVISIONED | **ENABLED** on `expiresOn` | 0 |
| QA | `inttra2_qa_ValueAddedService` | `id` (S) HASH | same | 5/5 PROVISIONED | DISABLED | 50,004 |
| CVT | `inttra2_cvt_ValueAddedService` | `id` (S) HASH | same | 5/5 PROVISIONED | DISABLED | 264 |
| PROD | `inttra2_prod_ValueAddedService` | `id` (S) HASH | same | 5/5 PROVISIONED | DISABLED | 1,236,915 |

**Attribute encoding contract — unchanged per attribute:**

| Attribute | Type | Encoding | v1 → v2 |
|---|---|---|---|
| `id` | S | Partition key | `@DynamoDBHashKey(attributeName="id")` → `@DynamoDbPartitionKey @DynamoDbAttribute("id")` |
| `scacCode` | S | Plain string | `@DynamoDBAttribute` → `@DynamoDbAttribute` |
| `carrierResponse` | **S** | `DynamoSupport` `<fqcn>:<json>` (+gzip/base64 over threshold) | `CarrierResponseConverter` → `CarrierResponseAttributeConverter` (ported `DynamoSupport`) |
| `inttraResponse` | **S** | Same format, `ValueAddedServiceResponse` | `InttraValueAddedServiceResponseConverter` → `InttraResponseAttributeConverter` |
| `bookingNumber` | S | GSI-only, **unpopulated** by the write path | `@DynamoDBIndexHashKey` → `@DynamoDbSecondaryPartitionKey` |
| `expiresOn` | **N** | Epoch seconds, app-managed (+400 days) | `DateToEpochSecond` → `DateEpochSecondAttributeConverter` (format matched exactly) |
| `audit` | **M** | Nested map, ISO-8601 timestamp strings | `@DynamoDBDocument` → `@DynamoDbBean` + `OffsetDateTimeTypeConverter` |

> **Decoupling rule (critical).** The DynamoDB on-wire formats are independent of the REST/SNS JSON formats.
> `Audit`'s `@JsonFormat(pattern="yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone="UTC")` governs REST/event JSON; the
> `AttributeConverter` governs the DynamoDB string. Both keep their current, **distinct** encodings — the v2 attribute
> converter must not leak into the JSON path, nor vice-versa.

#### Provisioning Idempotency (ext)

`dynamo-create` is a **separate one-off Dropwizard command**, not part of `server` startup — the running container
executes `/app/run.sh` → `java … server ./config.yaml`. When `dynamo-create` *is* invoked, verified behaviour against
existing tables is:

1. `describeTable` succeeds → logs *Table already exists* → **no** `CreateTable`, so key schema, attribute definitions
   and throughput are left untouched.
2. `addGlobalSecondaryIndexIfNotExists` finds the index by name and returns immediately → the KEYS_ONLY GSI is **not**
   modified.
3. TTL is only touched when the entity declares `@TTL` — **ours does not**, so `updateTimeToLive` is never called and
   INT's ENABLED / QA-CVT-PROD's DISABLED state are both preserved.
4. Streams are only touched with a `@Stream` annotation (absent) — **not** modified.

**Conclusion: nothing is overridden**, on either `server` startup or an explicit `dynamo-create`.

#### Component Interaction Flow (ext)

```
┌──────────────────────┐   ┌────────────────────────┐   ┌──────────────────────────┐   ┌─────────────────┐
│ ValueAddedService     │   │ ValueAddedServiceDao    │   │ DatabaseRepository       │   │ DynamoDB         │
│ ClientService         │   │                         │   │ (cloud-sdk)              │   │                  │
├──────────────────────┤   ├────────────────────────┤   ├──────────────────────────┤   ├─────────────────┤
│ 1. route by SCAC      │   │ 3. build entity + Audit │   │ 5. Enhanced Client       │   │ 7. PutItem       │
│ 2. carrier call       │   │ 4. expiresOn = +400d    │   │ 6. converters → S / N / M│   │ 8. GetItem (CR)  │
└─────────┬────────────┘   └───────────┬────────────┘   └────────────┬─────────────┘   └─────────────────┘
          │ Unchanged                   │ Change: injected repo       │ Change: v1 mapper → v2
          │                             │ replaces CrudRepository     │ Enhanced Client + ported
          │                             │ base class                  │ DynamoSupport converters
```

### UI

N/A — VAS is a headless service with no UI surface.

### API Architecture

**No API change.** No endpoint was added, removed, or altered; request bodies, response bodies, headers and status
codes are identical. Authentication and authorization are handled by the existing platform filters and were not
touched by this change.

| Use Case | API | Body | Method<br/>(GET/POST/PUT/DELETE) | Query Parameter | Access Privilege<br/>(Admin/Non-Admin User) | Authorization — (Yes/No)<br/>*(If Yes, mention the approach)* | Authentication — (Yes/No)<br/>*(If Yes, mention the approach)* | Remarks |
|---|---|---|---|---|---|---|---|---|
| VAS search | `/vas/search` | Yes — VAS search request | POST | None | Non-Admin User | Yes — platform authorization filter, **unchanged** | Yes — INTTRA principal (`InttraPrincipal`), **unchanged** | Save path — writes via the migrated DAO |
| Retrieve saved VAS response | `/vas/{id}` | No | GET | None (path param `id`) | Non-Admin User | Yes — **unchanged** | Yes — INTTRA principal, **unchanged** | Read path — strongly-consistent `findById` |
| Vessel-schedule search | `/vas/vsv/search/schedule` | Yes | POST | None | Non-Admin User | Yes — **unchanged** | Yes — **unchanged** | No AWS surface; publishes Hapag events via SNS |
| Contract parties lookup | `/vas/vsv/contract-parties/{contractOrPartyNumber}/{scacCode}` | No | GET | None (path params) | Non-Admin User | Yes — **unchanged** | Yes — **unchanged** | No AWS surface |
| Health / liveness | `/vas/services/ping` | No | GET | None | N/A | No — **unchanged** | No — **unchanged** | commons `InttraServerResource`; used by the ALB health check |
| Build version | `/vas/services/version` | No | GET | None | N/A | No — **unchanged** | No — **unchanged** | commons `InttraServerResource` |

> Paths confirmed from the Jersey registration log on a live boot (2026-07-29). Note that only the commons
> `InttraServerResource` endpoints sit under `/vas/services`; the business resources are mounted directly under `/vas`.

#### Request/Response Changes (ext)

No changes to request body, response body, headers, or status codes.

#### Implementation Notes (ext)

`ValueAddedServiceDao.findById` returned a `List` under v1 because the v1 `query` API returned a collection. A
partition-key lookup yields at most one item, so the v2 implementation wraps the `Optional` back into a 0..1 `List`,
keeping `ValueAddedServiceClientService.findSavedValueAddedServiceById` (which does `.stream().map(getInttraResponse)`)
behaviourally identical rather than changing its contract.

---

## Configuration

Configuration is per-environment `conf/<env>/config.yaml`, which is **committed in-repo and ships with the release
artifact** — so the changes below travel with the code and there is no separate configuration migration for any team
to perform.

Because `ValueAddedServiceConfig.dynamoDbConfig` moves from `dynamo-client`'s `DynamoDbConfig` to cloud-sdk's
`BaseDynamoDbConfig`, throughput and index metadata now come from the config block plus the entity annotations rather
than from a separate table-config block. All four environment files changed identically:

```diff
  dynamoDbConfig:
    environment: inttra_int           # QA inttra2_qa, CVT inttra2_cvt, PROD inttra2_prod
+   region: us-east-1
+   readCapacityUnits: 5
+   writeCapacityUnits: 5
+   sseEnabled: false

- dynamoDbTableConfig:                # block REMOVED in full
-   - tableName: ValueAddedService
-     readThroughput: 5
-     writeThroughput: 5
-     globalSecondaryIndexes:
-       - indexName: valueAddedServiceBookingNumber-index
-         hashKey: bookingNumber
-         projectionType: KEYS_ONLY
-         readThroughput: 5
-         writeThroughput: 5

  snsEventTopicArn: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event   # unchanged
```

- **Four keys added** to `dynamoDbConfig`: `region`, `readCapacityUnits`, `writeCapacityUnits`, `sseEnabled`.
- **`dynamoDbTableConfig` removed entirely.** Table name, GSI name and KEYS_ONLY projection are now declared by the
  entity annotations (`@Table`, `@DynamoDbSecondaryPartitionKey`, `@GsiConfig`), and capacity by `BaseDynamoDbConfig` —
  so the same facts are no longer duplicated in YAML.
- `environment` prefixes and `snsEventTopicArn` are unchanged.

> **CVT prefix trap.** The CVT DynamoDB prefix is `inttra2_cvt` while the CVT SNS topic is `inttra2_cv_sns_event`
> (note: `_cv`, not `_cvt`). INT also runs in a **different AWS account** (`081020446316`) from QA/CVT/PROD
> (`642960533737`). These exact strings must be carried through unchanged.

### Component-Level Configuration

None. No component-level (E2NA / Portal) files or properties are added or changed.

### Model-Level Configuration

None. No model-level (E2 / E2net / MCM) files or properties are added or changed.

### Stack-Level Configuration

| Setting | Before | After | Scope | Changed by |
|---------|--------|-------|-------|-----------|
| `dynamoDbConfig.region` | *(absent)* | `us-east-1` | Per-env `config.yaml` — all 4 environments | Project team / Operations |
| `dynamoDbConfig.sseEnabled` | *(absent)* | `false` | Per-env `config.yaml` — all 4 environments | Project team / Operations |
| `dynamoDbConfig.environment` | `inttra_int` / `inttra2_qa` / `inttra2_cvt` / `inttra2_prod` | unchanged | Per-env | Project team / Operations |
| `dynamoDbTableConfig` | 5/5 + KEYS_ONLY GSI | unchanged | Per-env | Project team / Operations |
| `snsEventTopicArn` | per-env topic ARN | unchanged | Per-env | Project team / Operations |

### Professional Services/System Integrator Configuration

None. No hub-level (IBMSS / Cisco) files or properties are involved.

---

## Auditing/Logging

Auditing of persisted records is unchanged — the nested `Audit` block still records `createdDateUtc` /
`lastModifiedDateUtc` from the authenticated `InttraPrincipal`, with the same ISO-8601 JSON format on the REST/event
path.

### Logging Details (ext)

| Logger | Level | Message Pattern | When |
|--------|-------|----------------|------|
| `ValueAddedServiceDynamoModule` | INFO | DynamoDB repository created for `<prefix>_ValueAddedService` | Startup |
| `ValueAddedServiceMessagingModule` | INFO | `NotificationService` / `EventPublisher` created for `<topicArn>` | Startup |
| `DynamoValueAddedServiceTableCommand` | INFO | *Table already exists* / index-exists skip | Explicit `dynamo-create` only |

No new log statement emits request payloads, credentials, or PII.

### Event Publishing (ext)

Hapag-Lloyd contract/routing events continue to publish to the same per-environment SNS topic with the same payload
shape. Only the publishing client changed (v1 `AmazonSNS` → cloud-sdk `NotificationService`); `EventLogger`/`MetaData`
were re-pointed to `cloudsdk.notification.workflow.*`.

---

## Metrics and Statistics

N/A — no metrics or statistics are added or changed.

---

## Installer Changes

No installer change, but one deployment-pipeline fact must be confirmed rather than assumed:

- The Dropwizard provisioning command name is **`dynamo-create` both before and after** this upgrade, because the old
  `dynamo-client` `AbstractDynamoCommand` and the new cloud-sdk `DynamoDbAdminCommand` both register that same name.
- **VAS is the exception in this migration programme.** `visibility`, `booking` and `booking-bridge` each had a bespoke
  `CreateTables extends ConfiguredCommand` registered as **`create-tables`**, so their CI `$task` argument had to change
  to `dynamo-create`. VAS already used `dynamo-create`, so **no CI/deploy change is required**.

| Module | OLD registered name | NEW registered name | CI `$task` change? |
|---|---|---|---|
| **value-added-service** | `dynamo-create` | `dynamo-create` | **NO — unchanged** |
| visibility (inbound) | `create-tables` | `dynamo-create` | YES |
| booking | `create-tables` | `dynamo-create` | YES |
| booking-bridge | `create-tables` | `dynamo-create` | YES |


---

## Impact on Current Application

### Migration Required

| Area | Needed? | Details |
|------|---------|---------|
| Database schema | **No** | Tables and GSIs already exist in all four environments with matching structure. `dynamo-create` is idempotent and overrides nothing. No data migration — existing items (incl. 1.2 M in PROD) are read by the new converters unchanged |
| Other file migration | **No** | No model or hub-model changes |
| UI / look & feel | **No** | No UI surface |

### Runtime Behavior (ext)

- **VAS search / save:** unchanged. Items are written with identical attribute names, types and encodings.
- **Retrieve by id:** unchanged, still a strongly-consistent read returning a 0..1 `List`.
- **Null carrier / INTTRA payloads:** now persist correctly with the attribute omitted (see Resiliency) — this
  *restores* v1 behaviour that an intermediate revision had regressed.
- **`bookingNumber`:** still not written; GSI remains provisioned and empty.
- **Vessel visibility / carrier integrations / OAuth:** no functional change.
- **Other endpoints:** no functional change.

### Performance (ext)

No measurable impact expected. The access patterns are identical (single `PutItem`, single consistent `GetItem`), and
cloud-sdk uses Apache HTTP rather than Netty, matching the `booking`/`visibility` rebase. AWS SDK 2.x's client is
constructed once per process at startup. The shaded jar grows to ~108 MB as it now carries AWS SDK v2.

### Deployment (ext)

Standard rolling ECS deployment (cluster `ANEINWEBSVC-001`, service `VAS-dev` in INT). 
No data migration, no coordinated deployment with other services.

---

## Resiliency

- **Strongly-consistent reads preserved** — `DynamoDbClientConfig` is built with `consistentRead(true)`, matching the
  previous `DYNAMO_READ_BEHAVIOUR.CONSISTENT`.
- **Null-payload guard (PR-review fix).** `transformFrom` in both converters previously always built an
  `AttributeValue`; for a null `carrierResponse`/`inttraResponse`, `objectToString` returns null and the resulting
  `AttributeValue` has no data type set, so DynamoDB rejected the write with
  `ValidationException: Supplied AttributeValue is empty`. Any `save` with an absent payload — permitted by the method
  signature — would have failed, a regression against the v1 mapper which omitted null attributes. Both converters now
  return `null` for null input so the enhanced client omits the attribute, restoring legacy behaviour.
- **Idempotent provisioning** — describe-then-skip for table and GSI; TTL and Streams untouched without their
  annotations, so no environment's live configuration can be clobbered by a re-run.

---

## Temporary object cleanup, temporary files cleanup

N/A — no temporary files or objects are created. 

---

## Impact on Tools

N/A — no tooling changes. Developer-local VS Code run/debug configurations were added to `.vscode/launch.json`, but
`.vscode/` is git-ignored repo-wide, so they are not part of the commit.

---

## Impact on Other Components

| Component | Impact |
|---|---|
| `commons` / `cloud-sdk-api` / `cloud-sdk-aws` | **Consumer only** — no changes made to the shared libraries by this ticket |
| `booking`, `visibility`, `network`, `auth`, `registration` | **None** — used as reference implementations only |
| Downstream SNS consumer | **None** — same topic ARN, same payload shape |
| Other mercury-services modules | **None** — the change is confined to the `value-added-service` module |

**Proposed shared-library enhancement (not delivered here):** add a reusable
`JsonClassTaggedAttributeConverter<T>` to `cloud-sdk-aws` implementing the legacy `<fqcn>:<json>` (+ size-threshold
gzip) format, so future modules with polymorphic archived payloads need not vendor `DynamoSupport` as VAS did.

---

## Backwards Compatible

**Yes — fully backwards compatible.**

| Question | Answer |
|---|---|
| Is the change backwards compatible? | Yes. Every DynamoDB attribute keeps its exact name, type (`S`/`N`/`M`) and encoding; the SNS topic ARN and payload shape are unchanged |
| Are there breaking changes? | None |
| API contract changes? | None — no endpoint, body, header or status-code change |
| Data migration needed? | No. Items written by the v1 mapper are read by the v2 converters (proven by integration test); items written by v2 are readable by v1 |
| Do clients require changes? | No |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason | CVEs Addressed |
|---|---|---|---|---|---|
| `com.inttra.mercury:commons` | `1.R.01.023` | `1.0.28-SNAPSHOT` | Upgrade | Required for the CVE fix; removes legacy `com.inttra.mercury.messaging.*` | Transitively clears AWS SDK v1 / Jackson HIGHs |
| `jackson-bom` (`jackson-databind`) | `2.21.0` | `2.21.4` | Upgrade (pinned) | Direct HIGH CVE remediation | **CVE-2026-54512**, **CVE-2026-54513** |
| `org.apache.httpcomponents.core5:httpcore5` | *(v1 transitive)* | `5.4.3` | Upgrade (transitive via AWS SDK v2 apache-client) | Pulled in by cloud-sdk | **CVE-2026-54399**, **CVE-2026-54428** |
| `com.inttra.mercury:cloud-sdk-api` | — | `1.0.28-SNAPSHOT` | **New** | AWS SDK 2.x abstraction | — |
| `com.inttra.mercury:cloud-sdk-aws` | — | `1.0.28-SNAPSHOT` | **New** | AWS SDK 2.x DynamoDB + SNS implementation (brings AWS SDK **2.30.24**) | Replaces the v1 SDK carrying the HIGHs |
| `com.inttra.mercury:dynamo-client` | `1.R.01.023` | **removed** | Removal | Supplied v1 DynamoDB **and** v1 SNS classes | Removes AWS SDK v1 HIGHs from the prod classpath |
| `com.amazonaws:aws-java-sdk-dynamodb` | `1.12.652` (prod) | **removed from prod**; `1.12.721` test-scoped only | Removal / rescope | Prod classpath must be free of `com.amazonaws` DynamoDB | Removes AWS SDK v1 HIGHs |
| `com.inttra.mercury:dynamo-integration-test` | — | `1.0.28-SNAPSHOT` (test) | **New** | DynamoDB-Local integration-test framework | — |

**OWASP dependency-check — before vs after** (both scans target the shaded jar):

| Scan | Total | HIGH | MEDIUM |
|---|---|---|---|
| Baseline (develop, commons `1.R.01.023`) | 25 | **6** | 19 |
| Post (commons `1.0.28` + Jackson `2.21.4` + cloud-sdk) | 12 | **0** | 12 |


---

## Unit Test Plan

`mvn -pl value-added-service verify` = **BUILD SUCCESS** — **213 unit + 9 integration = 222 tests**, 0 failures,
0 errors, 0 skipped (JUnit 5 only; no TestNG).

### New Tests (ext)

| # | Test Class | Test Method / Group | Coverage |
|---|-----------|---------------------|----------|
| 1 | `ValueAddedServiceDaoIT` | `save` → `findById` round-trip (strongly consistent) | DAO against DynamoDB-Local |
| 2 | `ValueAddedServiceDaoIT` | Generic-`Object` `carrierResponse` fidelity — CMA and Hapag payloads written, re-read, structurally compared | The primary fidelity risk |
| 3 | `ValueAddedServiceDaoIT` | `inttraResponse` JSON fidelity | Converter round-trip |
| 4 | `ValueAddedServiceDaoIT` | `expiresOn` epoch-seconds `N` round-trip + the +400-day calculation | Encoding + business rule |
| 5 | `ValueAddedServiceDaoIT` | GSI existence and KEYS_ONLY projection | Provisioning fidelity |
| 6 | `ValueAddedServiceDaoIT` | Reading an item written by the **v1 mapper** | Backwards-compatibility proof |
| 7 | `ValueAddedServiceDaoIT.OptionalPayloads` | `save(actor, scac, null, inttraResponse)` omits `carrierResponse`; both-null entity omits both — asserting on the **raw item** and the round-tripped entity | The PR-review null-payload fix |
| 8 | `CarrierResponseAttributeConverterTest` | Encode/decode incl. `transformFrom(null) == null` | Converter unit |
| 9 | `InttraResponseAttributeConverterTest` | Encode/decode incl. null case | Converter unit |
| 10 | `ValueAddedServiceMessagingModuleTest` | `NotificationService` / `EventPublisher` provisioning | Guice wiring (offline, dummy creds) |
| 11 | `ValueAddedServiceDynamoModuleTest` | `DynamoDbClientConfig` + repository provisioning | Guice wiring (offline, dummy creds) |
| 12 | `DynamoValueAddedServiceTableCommandTest` | Command construction and registered name | Provisioning command |

### Test Layer Coverage (ext)

| Layer | What it protects | Test Class | Faithfulness |
|-------|-----------------|------------|-------------|
| Persistence | On-wire attribute fidelity + consistent read | `ValueAddedServiceDaoIT` | **High** — real DynamoDB-Local, asserts raw items |
| Converters | Legacy `<fqcn>:<json>` (+gzip) encoding | `CarrierResponse…Test`, `InttraResponse…Test` | High — direct encode/decode |
| Guice wiring | Client construction without network | `…MessagingModuleTest`, `…DynamoModuleTest` | Medium — dummy static credentials via system properties, no AWS call |
| Provisioning | Command name + idempotency path | `DynamoValueAddedServiceTableCommandTest` | Medium — command construction; idempotency verified against cloud-sdk sources and live tables |
| Deployment | Real wiring end-to-end | INT local boot + ECS deployment | **High** — real AWS, real ALB traffic |

**JaCoCo union (unit + integration) line coverage of new/changed code:**

| Class | Coverage |
|---|---|
| `ValueAddedServiceDao` | 100% (24/24, IT) |
| `CarrierResponseAttributeConverter` | 100% (8/8) |
| `InttraResponseAttributeConverter` | 100% (8/8) |
| `support/GZip` | 100% (17/17) |
| `support/DynamoSupportException` | 100% (8/8) |
| `support/DynamoSupport` | 88% (50/57) |
| `ValueAddedServiceMessagingModule` | 90% (19/21) |
| `DynamoValueAddedServiceTableCommand` | 100% (12/12) |
| `ValueAddedServiceDynamoModule` | 89% (25/28) |
| `model/DynamoDBValueAddedService`, `model/Audit` | Excluded via `sonar.coverage.exclusions=**/model/**`; functionally covered by the IT |

Remaining uncovered lines are unreachable defensive guards (e.g. the missing-`@Table`-annotation check on an entity
that always carries `@Table`) and a `configure()` log line.

### Manual Tests (ext)

| # | Scenario | Steps | Expected Result |
|---|----------|-------|----------------|
| 1 | Local boot against INT | `mvn -pl value-added-service -am package -DskipTests`, then `java -jar target/value-added-service-1.0.jar server conf/int/config.yaml` | DynamoDB repository for `inttra_int_ValueAddedService`, SNS `NotificationService`/`EventPublisher` for `inttra_int_sns_event`, `EventLogger` injected; no ERROR |
| 2 | Liveness | `GET :8080/vas/services/ping`; `GET :8081/admin/healthcheck` | `200 {"healthy":"true"}`; 200 healthy |
| 3 | Live table structure | `aws dynamodb describe-table` + `describe-time-to-live` per environment | Structure matches entity annotations in all 4 envs |
| 4 | ECS deployment | Inspect `describe-services` / `describe-tasks` / CloudWatch `inttra-ecs-logs` | Steady state, cloud-sdk wiring in logs, continuous ALB 200s |

### Existing Test Impact (ext)

Existing DAO / service / mapper tests were updated only where mock **types** changed (`DynamoDBMapper` →
`DatabaseRepository`, `AmazonSNS` → `NotificationService`). The two converter unit tests' null cases were updated to
assert `transformFrom(null)` returns `null`. Carrier-mapper and validator tests were untouched — they have no AWS
surface. No test was weakened or deleted.

---

## Risks

**Key Risks**

- **12 MEDIUM CVEs remain**, including jackson-databind `CVE-2026-54515` which needs `2.21.5+`/`2.22.0`. Deliberately
  deferred to stay aligned with the `booking` baseline.
- **`expiresOn` must not be "upgraded" to a native TTL.** It is app-managed; QA/CVT/PROD have TTL disabled by decision.

---

## Dependencies

**Major Dependencies**

- **Released `commons 1.0.28`** 
- **`cloud-sdk-api` / `cloud-sdk-aws` `1.0.28`** — provide `DatabaseRepository`, `NotificationService`,
  `DynamoDbAdminCommand`.
- **DynamoDB-Local** via `dynamo-integration-test` — required for the integration suite in CI.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | **N** | No UI surface; no new data exposed. No endpoint, request or response change |
| 2 | Use of new services/ports | **N** | Same DynamoDB and SNS services, same per-environment table/topic, same app/admin ports 8080/8081 |
| 3 | Authentication changes | **N** | Platform authentication (INTTRA principal) untouched; carrier OAuth flows explicitly out of scope and unchanged |
| 4 | New/changed encryption | **N** | `sseEnabled: false` is a newly *expressed* key that preserves the existing behaviour — server-side encryption was not enabled before and is not enabled now. Transport remains TLS to AWS endpoints |
| 5 | Changes in the way data is transmitted | **Y** | The AWS transport stack changed: AWS SDK v1 → **AWS SDK 2.30.24 over Apache HTTP** (via `cloud-sdk-aws`) for both DynamoDB and SNS, and `httpcore5` moved to `5.4.3`. Endpoints, region, credentials chain, TLS and message payloads are unchanged — only the client library |
| 6 | Changes in the way/location data is being stored | **N** | Same table, same region/account, same partition key and GSI, and **byte-identical attribute encodings** per the encoding contract. Only the mapping library changed (v1 `DynamoDBMapper` → v2 Enhanced Client) |
| 120 | New API implementation / change of existing APIs (Please fill the API arch table) | **N** | No API added or changed — the API architecture table is filled for completeness and records "unchanged" for every row |
| 124 | New / Change in existing file upload functionality | **N** | No file upload/download functionality in this module |
| 125 | New / Change in integration within e2open or third-party apps | **Y** | The third-party AWS integration libraries were replaced: `dynamo-client` + `aws-java-sdk-dynamodb` (v1) removed, `cloud-sdk-api`/`cloud-sdk-aws` (AWS SDK 2.x) added, Jackson upgraded to `2.21.4`. The integrations themselves (which AWS services, which topic/table) are unchanged. Carrier integrations (CMA-CGM, Hapag-Lloyd) are untouched |
| 126 | New / Existing UI functionality support querying via either of them (VST, XML, java expressions, SQL or any other) | **N** | No VST/XML/java-expression/SQL querying. DynamoDB access is a typed partition-key lookup through the enhanced client — no expression language is exposed to input |

---

## REQUIRED: Documentation Changes

Answer the following questions.

| Question | Answer |
|----------|--------|
| Do end users interact with this feature? | **No.** Internal security remediation with no functional, API or UI change |
| Does the feature require special migration from prior releases? | **No data migration.**  DynamoDB tables, GSIs and existing items are unchanged |
| What guides or content sections need updating? | No user-facing guide changes.|

### Engineering Documentation Impact (ext)

| Area | Impacted? | Details |
|------|-----------|---------|
| API docs (Swagger/OpenAPI) | No | No contract change; swagger-maven-plugin generation untouched |
| Monitoring & alerting | No | No new metrics; existing ALB health check on `/vas/services/ping` unchanged |

---

## Blocking Issues and Actions from the Design Review

| # | Issue/Action | Owner | Status | Due Date | Resolution |
|---|-------------|-------|--------|----------|------------|

---

## Deployment Verification (ext)

### INT — ✅ (2026-07-28)

Cluster `ANEINWEBSVC-001`, service `VAS-dev`, container `VAS-dev-Container:8080`, target group `tg-int-vas-inttra`,
artifact `centos:VAS-26.07.001`, task definition `VAS-latest-dev-Task`.

| Test | Method | URL / Target | Result |
|------|--------|-----|--------|
| Service health | `aws ecs describe-services` | `VAS-dev` | ✅ ACTIVE — desired 1 / running 1 / pending 0, launchType EC2 |
| Deployment rollout | `aws ecs describe-services` | `VAS-dev` | ✅ single PRIMARY, rolloutState COMPLETED, steady state reached 08:44 |
| Task state | `aws ecs describe-tasks` | task `7da2e1f2…` | ✅ RUNNING, no exitCode. ECS health `UNKNOWN` — expected, the task def has `healthCheck: null` |
| App boot wiring | CloudWatch `inttra-ecs-logs` | `VAS-latest-dev/VAS-dev-Container/<taskId>` | ✅ DynamoDB repo for `inttra_int_ValueAddedService`; SNS `NotificationService`+`EventPublisher` for `inttra_int_sns_event`; `Starting InttraServer`; **0 ERROR/Exception** |
| ALB health | CloudWatch access logs | `ELB-HealthChecker/2.0 GET /vas/services/ping` | ✅ continuous **200** → target healthy |
| Local boot (twice) | `java -jar … server conf/int/config.yaml` | `:8080/vas/services/ping`, `:8081/admin/healthcheck` | ✅ 200 `{"healthy":"true"}`; 200 healthy |

### Local re-verification on the current build — ✅ (2026-07-29)

Re-run after the INT auth-gateway outage was resolved. `mvn package -pl value-added-service -am -DskipTests` =
BUILD SUCCESS, then booted against `conf/int/config.yaml`.

| Test | Evidence | Result |
|------|----------|--------|
| DynamoDB wiring | `ValueAddedServiceDynamoModule: Creating DynamoDBValueAddedService partition-key repository for table: inttra_int_ValueAddedService` | ✅ |
| Region / credentials | `BaseDynamoDbConfig: Resolved AWS region from DefaultAwsRegionProviderChain: us-east-1`; `Using DefaultCredentialsProvider` | ✅ |
| SNS wiring | `ValueAddedServiceMessagingModule: Creating SNS NotificationService using cloud-sdk-aws factory for topic: arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event`, then `Creating EventPublisher with cloud-sdk NotificationService` | ✅ |
| Startup errors | Full boot log | ✅ **0** ERROR / Exception |
| Liveness | `GET :8080/vas/services/ping` | ✅ 200 `{"healthy":"true"}` |
| Admin health | `GET :8081/admin/healthcheck` | ✅ 200 — *Basic functionality* and *deadlocks* both healthy |


---

## Design Document Review and Approval Matrix

> Add **"Approved"** or **"NA"** in the status column to approve the design document.
> **Approval Status Should have "Approved" or "NA" Only**

| Stage | Reviewer | Status | Notes | Ownership |
|-------|----------|--------|-------|-----------|
| Design | @Arijit Kundu |Approved | | **Product Management** |
| Product Owner | @Mahendran Pandian | | | **Product Owner** |
| Pre Dev Security | @Kamalesh Bhol | |  | **InfoSec** |
| Pre Dev Architecture | @Arijit Kundu |Approved | | **Product Development** |
| Browser | NA | NA | No UI surface | **Product Development** |
| UX | NA | NA | No UI surface | **Product Development** |
| Post Dev Security | @Kamalesh Bhol | | OWASP post-scan: 6 HIGH → 0 HIGH | **InfoSec** |
| Post Dev Architecture |@Arijit Kundu |Approved | | **Product Development** |
| QA/Test Driven Development (TDD) | @Venkat Ganga | | 213 unit + 9 integration green; INT ECS verified | **Product Development/QA** |
