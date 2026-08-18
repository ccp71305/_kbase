# ION-16110 Rates — OWASP HIGH CVE Remediation + AWS SDK 2.x (cloud-sdk) Upgrade

<!-- Generated 2026-07-29 from:
       - rates/docs/2026-07-28-rates-owasp-aws-upgrade.md        (implementation details)
       - rates/docs/2026-06-30-rates-aws2x-DESIGN-claude.md      (initial design plan)
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

`rates` carried **6 OWASP HIGH CVEs** and was still on AWS SDK v1 for its only AWS service, **DynamoDB**. This change
clears all HIGH findings and migrates the spot-rates persistence to the in-house **cloud-sdk** (`cloud-sdk-api` +
`cloud-sdk-aws`, AWS SDK 2.x Enhanced Client over Apache HTTP), removing `com.amazonaws` from the production classpath.

`rates` writes into the **shared `<env>_booking_SpotRatesDetail` table that `booking` had already migrated**, so the
on-wire shape had to match booking's enhanced-client output exactly rather than merely being self-consistent. The
migration also uncovered and fixed a **latent `GZip.compress` truncation bug** that silently corrupted any `spotRates`
payload above 300 KB.

**Status:** ✅ Merged to `develop`; running at steady state in QA. `mvn clean verify` green — 421 unit + 9 integration.

---

## Requirements

| | |
|---|---|
| **Epic** | https://jira.dev.e2open.com/jira/browse/ION-15550 & Security Upgrade 26.3 |
| **Story ID** | ION-16110 — *Jackson-2.21.0 Critical CVE* |
| **Target Release** | 26.2.3 |
| **Scope** | `rates` module only — DynamoDB persistence plus dependency upgrades. **No S3 / SQS / SNS / SES exists in this module.** |
| **Fix Version** | 26.2.3 |
| **Customer/Client** | None — internal security remediation, no customer-visible change |
| **Related Documents** (*If Any*) |  |

### Functional Requirements

- **No functional change to the REST surface.** Spot-rates retrieval, contract rates and container-type lookup behave
  exactly as before.
- Preserve the `SpotRatesDao` public API — `findByOfferKey`, `findBySpotRateId`, `saveSpotRates(4-arg)`, `save`.
- Preserve the **GSI → hash-key two-step** in `findBySpotRateId`: query the KEYS_ONLY `SPOT_RATE_ID_INDEX`
  eventually-consistently, then fetch the full item by partition key with a strongly consistent read. This is a
  behavioural contract, not an implementation detail.
- Preserve the 400-day `expiresOn` computed from `audit.createdDateUtc`, with millisecond precision dropped.
- **One intended behaviour change:** `spotRates` payloads above 300 KB are now stored correctly. The previous
  `GZip.compress` returned its buffer before the `GZIPOutputStream` was closed, producing truncated — unreadable —
  gzip. See Runtime Behavior.

### Non-Functional Requirements

| # | Requirement | Target |
|---|---|---|
| 1 | OWASP dependency-check HIGH findings | **0** |
| 2 | On-wire compatibility | Byte-identical to **booking's** enhanced-client output on the shared table |
| 3 | Read consistency | Base-table reads strongly consistent; GSI read eventually consistent (unchanged) |
| 4 | TTL encoding | `expiresOn` epoch-seconds `N`, milliseconds dropped — consumed by native DynamoDB TTL |
| 5 | Prod classpath | No `com.amazonaws` at all (test-scoped only, for DynamoDB Local) |
| 6 | Provisioning safety | `rates` has **no** table-admin command — it must never create or alter tables |
| 7 | Test coverage | Full local JaCoCo coverage of all new/changed classes |

### Acceptance Criteria

| # | Criterion | Result |
|---|---|---|
| 1 | OWASP post-scan reports 0 HIGH | ✅ 6 HIGH → **0 HIGH**; MEDIUM 49 → 42; low 8 → 8 |
| 2 | `mvn -f rates/pom.xml clean verify` green | ✅ BUILD SUCCESS — **421 unit + 9 integration**, 0 failures / 0 errors |
| 3 | No vulnerable Jackson remains | ✅ `dependency:tree` shows `2.21.4` throughout; no `2.19.x` |
| 4 | `spotRates` > 300 KB round-trips | ✅ Covered by `SpotRatesAttributeConverterTest.compressedRoundTrip` + `SpotRatesDaoIT` gzip test (both failed before the `GZip` fix) |
| 5 | Legacy items still readable | ✅ Tolerant reads for `+0000` / `+00:00` / `Z` / date-only timestamps and a foreign (booking) class prefix |
| 6 | DynamoDB schema parity in all 4 envs | ✅ Hash key, GSI, TTL match the v2 annotations everywhere |
| 7 | Service runs in a healthy environment | ✅ QA `Rates-qa` — desired 1 / running 1, steady state |

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
| Servlet Container | Jetty |
| JAX-RS / API layer | Jersey — `rootPath: /rates`; `SpotRatesResource`, `ContractRateResource` |
| Build | Maven (`mvn -f rates/pom.xml clean verify`) |
| AWS SDK | **AWS SDK 2.x** via `cloud-sdk-aws` (was AWS SDK v1 `1.12.655` + `dynamo-client`) |
| Database | DynamoDB — **shared** `<env>_booking_SpotRatesDetail` + GSI `SPOT_RATE_ID_INDEX` |
| Messaging | **None** — no SNS/SQS in this module |
| Shared library | `commons` **1.0.28-SNAPSHOT** (was `1.R.01.023`) |
| JSON | Jackson **2.21.4** (pinned via `jackson-bom`), `jackson-dataformat-xml` BOM-managed |
| Other pins | Guava **33.5.0-jre** |
| External integrations | Maersk Offers API, TM system, INTTRA network/auth gateway — all unchanged |
| Test | JUnit 5, DynamoDB-Local (`dynamo-integration-test`), JaCoCo |

---

## Assumptions and Open Issues

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | commons is consumed as **`1.0.28-SNAPSHOT`** | Pre-requisite | **Closed** | A released commons `1.0.28` build is published |
| 2 | `config.yaml` needs no change — the existing `dynamoDbConfig` keys map directly onto cloud-sdk `BaseDynamoDbConfig` | Assumption | Resolved | Verified: neither upgrade commit touches `rates/conf/`. `readCapacityUnits`, `writeCapacityUnits`, `environment`, `sseEnabled` bind unchanged (identical to booking) |
| 3 | `region` is **not** set in the rates `dynamoDbConfig` | Assumption | Resolved | Unlike VAS, rates never declared a region; it resolves through the standard AWS region provider chain at runtime. The commented `#regionEndpoint`/`#signingRegion` keys remain available for the local DynamoDB emulator |
| 4 | The live GSI projection is KEYS_ONLY, matching `@GsiConfig` | Assumption | Resolved | Confirmed against the live tables in all four environments. `findBySpotRateId` only needs `spotRateKey` from the index, so KEYS_ONLY is behaviourally sufficient |
| 5 | SSE differs by environment — INT disabled, QA/CVT/PROD enabled | Open Issue | Resolved | Table-level encryption owned by external provisioning and matching each environment's `sseEnabled` config. `rates` has **no** table-admin command, so it can never create or alter a table and therefore never overrides SSE, TTL or streams |
| 6 | CVT DynamoDB prefix is `inttra2_test_booking`, **not** `inttra2_cvt` | Assumption | Resolved | Carried through the `BaseDynamoDbConfig` migration unchanged |
| 7 | `booking` already migrated the identical `SpotRatesDetail` entity | Assumption | Resolved | Used as the primary reference. Converters were nevertheless **ported into `rates`** rather than depended upon, and `transformTo` ignores the stored class prefix so items written by either module are readable by both |
| 8 | INT boot-check failed on an `api-alpha` gateway **HTTP 502** outage, not a code defect | Open Issue | Resolved | Proven at the time by the *deployed develop* artifact failing identically and by 502s on all `api-alpha` paths while QA/CVT/PROD gateways were up. The gateway has since been repaired — see Deployment Verification |
| 9 | `rates` is uniquely boot-fragile: `ISOContainerToTmContainer` (`@Singleton`) eagerly warms the container-type cache in its constructor, so a gateway outage fails Guice provisioning and exits the container | Open Issue | **Open** | Pre-existing eager-cache-warm anti-pattern, unrelated to this change and deliberately not altered here. `booking`/`network` load lazily per request and stay up during the same outage. Worth a separate ticket |
| 10 | `spotRates` payloads > 300 KB written **before** this fix are truncated on disk | Closed | **Resolved** | The `GZip` fix makes new writes correct |

---

## High Level Design

### Architectural Overview (ext)

```
┌──────────┐   ┌──────────────────────────────┐   ┌──────────────────────────────┐   ┌──────────────────┐
│  Client   │──▶│  JAX-RS resources            │──▶│  Services + carrier clients  │──▶│  Maersk / TM /    │
│           │   │  SpotRatesResource           │   │  MaerskSpotRatesClient       │   │  network gateway  │
│           │   │  ContractRateResource        │   │  ContractRateService, TMClient│  │  UNCHANGED        │
└──────────┘   └──────────────────────────────┘   └──────────────┬───────────────┘   └──────────────────┘
                                                                  │
                                                    ┌─────────────▼─────────────┐
                                                    │ SpotRatesDao              │
                                                    └─────────────┬─────────────┘
                                                                  │  ◀── MIGRATED ──▶
                                        ┌─────────────────────────▼─────────────────────────┐
                                        │  cloud-sdk-aws  —  AWS SDK 2.x + Apache HTTP       │
                                        │  DatabaseRepository + DefaultQuerySpec              │
                                        └─────────────────────────┬─────────────────────────┘
                                                                  ▼
                                        ┌───────────────────────────────────────────────────┐
                                        │ DynamoDB (SHARED with booking)                     │
                                        │ (env)_booking_SpotRatesDetail                       │
                                        │ + SPOT_RATE_ID_INDEX (KEYS_ONLY), native TTL       │
                                        └───────────────────────────────────────────────────┘
```

Only the shaded band changed. The Maersk / TM / network REST integrations, MapStruct mappers, Swagger, Jackson-XML and
Parameter Store resolution are untouched.

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | **Two separate commits** — OWASP fix, then AWS SDK 2.x migration | Independent review and revert; the security fix can ship on its own merit | Two commits to track | ✅ |
| 2 | Depend on **booking's** converters rather than porting them | No duplicated code | Creates a module dependency from `rates` onto `booking` for persistence encoding; a booking-side change could silently alter rates' on-disk format | ❌ |
| 3 | **Port the converters into `rates`**, with reads tolerant of a foreign class prefix | No cross-module dependency; both modules can read each other's items | Some duplication with booking | ✅ |

### Data Flow — Before vs After (ext)

**Before (AWS SDK v1):**
```
GET /rates/spot/{hashKey}
  → SpotRatesService
  → SpotRatesDao extends DynamoDBCrudRepository
  → DynamoDBMapper (v1 ORM) + DynamoSupport client/mapper construction
  → DynamoDB query(hashKey, CONSISTENT)
  → 200 [spot rates]

save: MaerskSpotRatesClient → SpotRatesDao.saveSpotRates
  → SpotRatesConverter (S), DateToEpochSecond (N)
  → GZip.compress ABOVE 300 KB -> TRUNCATED, unreadable
```
**After (cloud-sdk / AWS SDK 2.x):**
```
GET /rates/spot/{hashKey}
  → SpotRatesService: unchanged
  → SpotRatesDao: injected DatabaseRepository + DefaultQuerySpec
  → findById(partitionKey, consistentRead=true)
  → 200 [spot rates]   (unchanged status, body, headers)

findBySpotRateId: query SPOT_RATE_ID_INDEX (KEYS_ONLY, eventually consistent)
  → then findById(spotRateKey, consistentRead=true)   [two-step preserved]

save: SpotRatesAttributeConverter (S), DateEpochSecondAttributeConverter (N),
      AuditAttributeConverter (M)
  → GZip.compress ABOVE 300 KB -> correct, round-trips
```

---

## Low Level Design

### Server

The migration mirrors `booking`'s already-migrated `SpotRatesDetail` twin field-for-field, because both modules read and
write the **same** table. The fidelity-critical surface is the three attribute encodings: the `spotRates` JSON string
(with its `<fqcn>:` prefix and gzip-above-300 KB branch), the `audit` native Map with ISO timestamps, and the
`expiresOn` epoch-seconds Number that native DynamoDB TTL consumes.

#### Key Components and Changes (ext)

| # | Component | Location | Purpose | Key Changes |
|---|-----------|----------|---------|-------------|
| 1 | `pom.xml` | `rates/` | Dependencies | commons → `1.0.28-SNAPSHOT`; **removed** `dynamo-client` + prod `aws-java-sdk-dynamodb 1.12.655` and the `mercury.dynamodbclient.version` / `dynamodb-local.version` properties; **added** `cloud-sdk-api`, `cloud-sdk-aws`, test-scoped `dynamo-integration-test` + `aws-java-sdk-dynamodb 1.12.721`; imported `jackson-bom 2.21.4`; pinned Guava `33.5.0-jre`; wired `maven-failsafe-plugin` (`<groups>integration</groups>`, `**/*IT.java`, `sqlite4java.library.path`) and `copy-native-libs` |
| 2 | `SpotRatesDetail` | `spot/model/canonical/` | DynamoDB entity | v1 ORM → `@DynamoDbBean` + `@Table(name="SpotRatesDetail")`; `@DynamoDbPartitionKey` `spotRateKey`; `@DynamoDbSecondaryPartitionKey` + `@GsiConfig(KEYS_ONLY)` `SPOT_RATE_ID_INDEX`; `@TTL` `expiresOn`; deprecated `getHashKey`/`setHashKey` retained for source compatibility |
| 3 | `SpotRatesAttributeConverter` | `spot/dynamodb/` | `spotRates` payload | **New** — v2 `AttributeConverter<SpotRates>` emitting `S`: `className:json`, or `size|className:base64(gzip(json))` above 300 KB. `transformTo` reads into `rates.SpotRates` **ignoring the stored class prefix**, so booking-written items are readable |
| 4 | `AuditAttributeConverter` + `LegacyMapConverter` | `spot/dynamodb/` | `audit` block | **New** — v2 `AttributeConverter<Audit>` writing a native Map (`M`) with `ISO_DATE_TIME` (`Z`) timestamps, plus a Map/List ↔ `AttributeValue` helper |
| 5 | `OffsetDateTimeTypeConverter` | `spot/dynamodb/` | Timestamps | Rewritten to the v2 form (Jackson `StdDeserializer`), tolerant of `Z` / `+00:00` / `+0000` / date-only inputs |
| 6 | `SpotRatesDao` | `spot/dynamodb/` | Persistence | `extends DynamoDBCrudRepository` → injected `DatabaseRepository<SpotRatesDetail, DefaultPartitionKey<String>>` + `DefaultQuerySpec`; public API and the GSI → hash-key two-step preserved |
| 7 | `SpotRatesModule` | `spot/module/` | Guice | Dropped `AmazonDynamoDB` / `DynamoDBMapper` / `DynamoDBMapperConfig` bindings; added cloud-sdk `DynamoDbClientConfig` + `SpotRatesDao` providers. Made **self-contained** in PR review — the provider reuses the `ratesConfig` passed to the constructor instead of an injected `RatesConfig` the module never binds. `@Named ExternalServiceDefinition` maersk bindings kept |
| 8 | `SpotRateConfig` | `config/` | Config binding | `dynamoDbConfig` type `DynamoDbConfig` → `BaseDynamoDbConfig` |
| 9 | `Audit` | `spot/model/` | Domain | Dropped `@DynamoDBDocument` / `@DynamoDBTypeConverted`; **kept** `@JsonFormat` for the REST path |
| 10 | `ContainerType` | `networkservices/containertype/model/` | REST DTO | Dropped stray `@DynamoDBDocument` / `@DynamoDBTypeConvertedEnum`. These were **dead v1 annotations** — the class is a transient network DTO that is never persisted — and would have broken compilation once `com.amazonaws` left the prod classpath |
| 11 | `common/GZip` | `common/` | Compression | **Bug fix** — `compress()` returned `toByteArray()` inside the try-with-resources, before `GZIPOutputStream` was closed and its trailer flushed, yielding truncated gzip. Now closes before reading |
| 12 | Removed | — | — | `DynamoSupport`, `DateToEpochSecond`, `SpotRatesConverter` (replaced by cloud-sdk and the new converters) |

#### AWS Services Used (ext)

| Service | Usage | SDK |
|---------|-------|-----|
| DynamoDB | Persist spot-rates details; consistent partition-key read; eventually-consistent GSI query | cloud-sdk `DatabaseRepository` + `DefaultQuerySpec` (AWS SDK 2.x Enhanced Client) |
| Parameter Store | `${awsps:...}` resolution at startup | commons — **unchanged** |

**No S3, SQS, SNS, SES ** exists in this module.

#### DynamoDB Changes (ext)

No structural change. `rates` has **no table-admin command** — `SpotRatesDetail` and its GSI are externally
provisioned, so the application never issues `CreateTable`, `UpdateTable`, `UpdateTimeToLive` or a stream change in any
environment. Live schema verified against the v2 annotations everywhere:

| Env | AWS account | Table | Hash key | GSI `SPOT_RATE_ID_INDEX` | TTL | Stream | SSE |
|-----|-------------|-------|----------|--------------------------|-----|--------|-----|
| INT | `081020446316` | `inttra_int_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | **ENABLED** on `expiresOn` | disabled | disabled |
| QA | `642960533737` | `inttra2_qa_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | **ENABLED** on `expiresOn` | disabled | ENABLED |
| CVT | `642960533737` | `inttra2_test_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | **ENABLED** on `expiresOn` | disabled | ENABLED |
| PROD | `642960533737` | `inttra2_prod_booking_SpotRatesDetail` | `spotRateKey` (S) | `spotRateId` (S), KEYS_ONLY | **ENABLED** on `expiresOn` | disabled | ENABLED |

TTL and streams are **consistent** across all four environments (unlike the VAS table). SSE differs but is table-level
and externally owned, matching each environment's `sseEnabled` config.

**Attribute encoding contract — unchanged per attribute:**

| Attribute | Type | Encoding | v1 → v2 |
|---|---|---|---|
| `spotRateKey` | S | Partition key; UUID with dashes stripped, generated in `SpotRatesDao.calcRandomUUID()` | `@DynamoDBHashKey` on `getHashKey()` → `@DynamoDbPartitionKey @DynamoDbAttribute("spotRateKey")` |
| `spotRates` | **S** | `className:json`, or `size|className:base64(gzip(json))` above 300 KB. Jackson `FAIL_ON_UNKNOWN_PROPERTIES=false`, `SORT_PROPERTIES_ALPHABETICALLY=true` | `SpotRatesConverter` → `SpotRatesAttributeConverter` |
| `audit` | **M** | Native Map; `createdDateUtc` / `lastModifiedDateUtc` as `ISO_DATE_TIME` strings | `@DynamoDBDocument` → `AuditAttributeConverter` + `LegacyMapConverter` |
| `expiresOn` | **N** | Epoch seconds, milliseconds dropped `(t/1000)*1000`; 400 days from `audit.createdDateUtc` | `DateToEpochSecond` → cloud-sdk built-in `DateEpochSecondAttributeConverter` |
| `spotRateId` | S | GSI partition key | `@DynamoDBIndexHashKey` → `@DynamoDbSecondaryPartitionKey` |
| `carrierId`, `carrierResponse` | S | Plain strings | `@DynamoDBAttribute` → `@DynamoDbAttribute` |

> **Decoupling rule (critical).** The DynamoDB on-wire encodings are independent of the REST JSON. `Audit`'s
> `@JsonFormat(pattern="yyyy-MM-dd'T'HH:mm:ss.SSSZ", timezone="UTC")` governs the REST representation, while the
> `AttributeConverter` governs the DynamoDB attribute (`ISO_DATE_TIME`). Both keep their current, **distinct**
> encodings — neither may leak into the other.

#### Component Interaction Flow (ext)

```
┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────────┐  ┌──────────────────┐
│ MaerskSpotRatesClient│  │ SpotRatesDao         │  │ DatabaseRepository     │  │ DynamoDB          │
│ / SpotRatesService   │  │                      │  │ (cloud-sdk)            │  │ shared w/ booking │
├─────────────────────┤  ├──────────────────────┤  ├────────────────────────┤  ├──────────────────┤
│ 1. map Maersk offers │  │ 3. spotRateKey = UUID│  │ 5. Enhanced Client     │  │ 7. PutItem        │
│ 2. saveSpotRates(..) │  │ 4. expiresOn = +400d │  │ 6. converters S / N / M│  │ 8. Query GSI      │
│                      │  │    (epoch sec)       │  │                        │  │ 9. GetItem (CR)   │
└──────────┬──────────┘  └──────────┬───────────┘  └───────────┬────────────┘  └──────────────────┘
           │ Unchanged               │ Change: injected repo    │ Change: v1 mapper -> v2
           │                         │ replaces CrudRepository  │ Enhanced Client + ported
           │                         │ base class               │ converters; GZip fix
```

### UI

N/A 

### API Architecture

**No API change.** No endpoint was added, removed or altered; request bodies, response bodies, headers and status codes
are identical. Authentication and authorization are handled by the existing commons `securityResources` token
validation and were not touched.

| Use Case | API | Body | Method<br/>(GET/POST/PUT/DELETE) | Query Parameter | Access Privilege<br/>(Admin/Non-Admin User) | Authorization — (Yes/No)<br/>*(If Yes, mention the approach)* | Authentication — (Yes/No)<br/>*(If Yes, mention the approach)* | Remarks |
|---|---|---|---|---|---|---|---|---|
| Spot rates search | `/rates/spot` | No | GET | Yes — search criteria | Non-Admin User | Yes — commons `securityResources`, **unchanged** | Yes — OAuth token validation, **unchanged** | Persists results via the migrated DAO |
| Spot rates by company | `/rates/spot/inttraCompanyId/{inttraCompanyId}` | No | GET | None (path param) | Non-Admin User | Yes — **unchanged** | Yes — **unchanged** | Read path |
| Spot rate by key | `/rates/spot/{hashKey}` | No | GET | None (path param) | Non-Admin User | Yes — **unchanged** | Yes — **unchanged** | Consistent partition-key read |
| Contract rates | `/rates/contract` | No | GET | Yes — contract criteria | Non-Admin User | Yes — **unchanged** | Yes — **unchanged** | TM integration; no AWS surface |
| Container types | `/rates/contract/containertype` | No | GET | None | Non-Admin User | Yes — **unchanged** | Yes — **unchanged** | Network gateway; eagerly warmed at startup (see Resiliency) |
| Health / liveness | `/rates/services/ping` | No | GET | None | N/A | No — **unchanged** | No — **unchanged** | commons `InttraServerResource` |
| Build version | `/rates/services/version` | No | GET | None | N/A | No — **unchanged** | No — **unchanged** | commons `InttraServerResource` |

> Paths confirmed from the Jersey registration log on a live boot (2026-07-29). The business resources are mounted
> under `/rates/spot` and `/rates/contract`; only the commons `InttraServerResource` endpoints sit under
> `/rates/services`.

#### Request/Response Changes (ext)

No changes to request body, response body, headers, or status codes.

#### Implementation Notes (ext)

`findBySpotRateId` deliberately keeps a **two-step** lookup rather than collapsing it into a single GSI read: the index
is KEYS_ONLY, so it yields only `spotRateKey`, which is then used for a strongly consistent base-table `findById`. This
preserves both the read-consistency guarantee and the existing return shape. `findByOfferKey`'s v1 `CONSISTENT` query
maps to `findById(key, true)`, with the `Optional` wrapped back into a 0..1 `List` so callers are unaffected.

---

## Configuration

**No configuration change.** Neither upgrade commit touches `rates/conf/` — verified against both commits. The existing
`spotRateConfig.dynamoDbConfig` keys bind directly onto the cloud-sdk `BaseDynamoDbConfig` type, identical to
`booking`:

```
spotRateConfig:
  dynamoDbConfig:
    # set these only when running the local Dynamo emulator
    #regionEndpoint: http://localhost:8000
    #signingRegion: us-west-2
    readCapacityUnits: 25
    writeCapacityUnits: 25
    environment: inttra_int_booking     # QA inttra2_qa_booking, CVT inttra2_test_booking, PROD inttra2_prod_booking
    sseEnabled: false                   # PROD alone is true
  spotRatesEnabled: ${awsps:/inttra/int/rates/config/spotRates}
```

The only Java-side change is the field type on `SpotRateConfig.dynamoDbConfig`
(`DynamoDbConfig` → `BaseDynamoDbConfig`); the YAML shape is unchanged, so no environment needs editing and there is no
configuration migration for any team to perform.

> **Notes.** `region` is deliberately **not** declared in the rates config — it resolves through the standard AWS region
> provider chain at runtime. The commented `#regionEndpoint`/`#signingRegion` keys continue to work for the local
> DynamoDB emulator. **CVT prefix trap:** CVT is `inttra2_test_booking`, *not* `inttra2_cvt`; and INT runs in a
> different AWS account (`081020446316`) from QA/CVT/PROD (`642960533737`).

### Component-Level Configuration

None. No component-level (E2NA / Portal) files or properties are added or changed.

### Model-Level Configuration

None. No model-level (E2 / E2net / MCM) files or properties are added or changed.

### Stack-Level Configuration

None. `conf/<env>/config.yaml` is committed in-repo and ships with the release artifact; no key was added, removed or
renamed by this change, so there is nothing for Stack Manager or Operations to reconfigure.

### Professional Services/System Integrator Configuration

None. No hub-level (IBMSS / Cisco) files or properties are involved.

---

## Auditing/Logging

Auditing of persisted records is unchanged — `Audit` still carries `createdDateUtc` / `lastModifiedDateUtc`, with the
same ISO-8601 `@JsonFormat` on the REST path and `ISO_DATE_TIME` on the DynamoDB path.

### Logging Details (ext)

No new application log statements were added. The `com.amazonaws` logger category remains configured at `ERROR` in
`config.yaml`; it is now inert on the production classpath since the v1 SDK is gone (harmless, left in place).

No log statement emits request payloads, credentials, or PII.

### Event Publishing (ext)

N/A — `rates` publishes no events; there is no SNS/SQS surface in this module.

---

## Metrics and Statistics

N/A — no metrics or statistics are added or changed.

---

## Installer Changes

**None.** `rates` has **no** Dropwizard table-admin command — no `ConfiguredCommand`, `AbstractDynamoCommand`,
`CreateTables` or `dynamo-create`. `SpotRatesDetail` is externally provisioned, and `run.sh` deploys
`java -jar rates-1.0.jar server ./config.yaml`, i.e. task = `server`.

Therefore the `create-tables` → `dynamo-create` CI `$task` migration that affected `visibility`, `booking` and
`booking-bridge` **does not apply to `rates`**. (A `DynamoTableCommand.java` visible in git history belongs to a
long-removed `rates-api`/`rates-batch` structure, not this module.)

---

## Impact on Current Application

### Migration Required

| Area | Needed? | Details |
|------|---------|---------|
| Database schema | **No** | Tables, GSI and TTL already exist and match the v2 annotations in all four environments. `rates` has no table-admin command, so it cannot alter them. No data migration — existing items are read by the new converters unchanged |
| Property migration | **No** | `conf/` is untouched by both commits; existing keys bind onto `BaseDynamoDbConfig` as-is |
| Other file migration | **No** | No model or hub-model changes |
| UI / look & feel | **No** | No UI surface |

### Runtime Behavior (ext)

- **Spot-rates read/write:** unchanged. Identical attribute names, types and encodings; still consistent on the base
  table and eventually consistent on the GSI.
- **`spotRates` payloads above 300 KB:** **now correct.** Previously `GZip.compress` returned its buffer before the
  `GZIPOutputStream` closed, so the gzip trailer was missing and the stored value was unreadable. Any such payload was
  silently corrupt on write. New writes round-trip correctly; see Backwards Compatible for already-written items.
- **Contract rates / container types / Maersk / TM:** no functional change.
- **Cross-module reads:** items written by `booking` remain readable by `rates` (the converter ignores the stored class
  prefix) and vice-versa.
- **Other endpoints:** no functional change.

### Performance (ext)

No measurable impact expected — the access patterns are identical (one `PutItem`, one consistent `GetItem`, one GSI
`Query`). cloud-sdk uses Apache HTTP rather than Netty, matching the booking/visibility rebase, and the client is
constructed once per process at startup. The shaded jar is ~113 MB now that it carries AWS SDK v2.

### Deployment (ext)

Standard rolling ECS deployment. No data migration, no configuration change, and no coordinated deployment with other
services — although note that `rates` shares the `SpotRatesDetail` table with `booking`, which is already migrated, so
the two can be deployed independently in either order.

---

## Resiliency

- **Read consistency preserved** — base-table reads remain strongly consistent (`findById(key, true)`); the GSI read
  remains eventually consistent, as before.
- **GSI → hash-key two-step preserved**, so a KEYS_ONLY projection never yields a partially populated entity.
- **Tolerant timestamp parsing** — reads accept `Z`, `+00:00`, `+0000` and date-only forms, so legacy items written by
  any earlier encoding still deserialize.
- **Tolerant class prefix** — `transformTo` ignores the `<fqcn>:` prefix, so a booking-written item does not throw.
- **Null attributes omitted** rather than written as empty `AttributeValue`s (covered by an integration test), matching
  legacy mapper behaviour and avoiding `ValidationException`.
- **No table mutation** — with no table-admin command, `rates` cannot clobber TTL, SSE, streams or throughput in any
  environment.
- **Known fragility (pre-existing, not addressed here):** `ISOContainerToTmContainer` is a `@Singleton` whose
  constructor eagerly warms the container-type cache through `ContainerTypeClient` → `NetworkClient` → `AuthClient`. If
  the gateway is unavailable at startup, Guice provisioning fails and the container exits. `booking`/`network` load
  their caches lazily and survive the same outage. Recommend a separate ticket to make the warm-up lazy or
  failure-tolerant.

---

## Temporary object cleanup, temporary files cleanup

No temporary files are created. Persisted spot-rates items are purged by **native DynamoDB TTL** on `expiresOn`, which
is **ENABLED in all four environments** — 400 days after `audit.createdDateUtc`. The application writes `expiresOn` as
an epoch-seconds Number with milliseconds dropped, which is exactly the format native TTL consumes; expiry is handled by
DynamoDB with no application involvement.

---

## Impact on Tools

N/A 

---

## Impact on Other Components

| Component | Impact |
|---|---|
| **`booking`** | **Shares the `<env>_booking_SpotRatesDetail` table.** No booking code change, but this is the critical compatibility contract — the rates converters were verified to produce booking's on-wire shape, and reads on both sides tolerate the other's class prefix. Deployable in either order |
| `commons` / `cloud-sdk-api` / `cloud-sdk-aws` | **Consumer only** — no changes made to the shared libraries by this ticket |
| `network`, `auth`, `visibility`, `registration` | **None** — used as reference implementations only |
| Other mercury-services modules | **None** — the change is confined to the `rates` module |

---

## Backwards Compatible

**Yes.**

| Question | Answer |
|---|---|
| Is the change backwards compatible? | Yes. Every DynamoDB attribute keeps its exact name, type (`S`/`N`/`M`) and encoding, matching both the rates v1 format and booking's migrated format |
| Are there breaking changes? | None |
| API contract changes? | None — no endpoint, body, header or status-code change |
| Deployable independently? | Yes — no config change, and no ordering constraint against `booking` |
| Data migration needed? | No. Legacy items are read by the new converters, including tolerant timestamp and class-prefix handling |
| Do clients require changes? | No |
| Any data **not** recoverable? | **Yes — pre-existing.** `spotRates` payloads above 300 KB written before the `GZip.compress` fix were stored as truncated gzip and were already unreadable. The fix corrects new writes but cannot recover those items; they will age out via the 400-day TTL. |

---

## New/Upgraded Third party Applications/Jars

| Application / Jar | Current Version | New Version | New or Upgrade | Reason | CVEs Addressed |
|---|---|---|---|---|---|
| `com.inttra.mercury:commons` | `1.R.01.023` | `1.0.28-SNAPSHOT` | Upgrade | Brings the patched `httpcore5` line | **CVE-2026-54399**, **CVE-2026-54428** |
| `jackson-bom` (`jackson-databind`) | `2.21.0` | `2.21.4` | Upgrade (BOM import) | Direct HIGH CVE remediation | **CVE-2026-54512**, **CVE-2026-54513** |
| `jackson-dataformat-xml` | `2.19.2` (hard-coded) | `2.21.4` (BOM-managed) | Upgrade | **PR-review finding** — the explicit `<version>` overrode the BOM, leaving a vulnerable Jackson module on the classpath. The hard-coded version was dropped | Completes the Jackson remediation |
| `com.inttra.mercury:cloud-sdk-api` | — | `1.0.28-SNAPSHOT` | **New** | AWS SDK 2.x abstraction | — |
| `com.inttra.mercury:cloud-sdk-aws` | — | `1.0.28-SNAPSHOT` | **New** | AWS SDK 2.x DynamoDB implementation | Replaces the v1 SDK carrying the HIGHs |
| `com.google.guava:guava` | `27.0.1-android` (resolved) | `33.5.0-jre` (pinned) | Upgrade (pin) | After dropping `dynamo-client`, old swagger dragged in `27.0.1-android` by nearest-wins, breaking Guice (`ImmutableMap.buildOrThrow` `NoSuchMethodError`). Pinned to match booking | — |
| `com.inttra.mercury:dynamo-client` | `1.R.01.023` | **removed** | Removal | Supplied the v1 DynamoDB stack | Removes AWS SDK v1 HIGHs from the prod classpath |
| `com.amazonaws:aws-java-sdk-dynamodb` | `1.12.655` (prod) | **removed from prod**; `1.12.721` test-scoped only | Removal / rescope | Prod classpath must be free of `com.amazonaws` | Removes AWS SDK v1 HIGHs |
| `com.inttra.mercury:dynamo-integration-test` | — | `1.0.28-SNAPSHOT` (test) | **New** | DynamoDB-Local integration-test framework | — |

**OWASP dependency-check — before vs after** (both scans target the shaded jar, with the module suppression file):

| Severity | Baseline (develop) | Post-fix | Delta |
|---|---|---|---|
| **HIGH** | **6** | **0** | **−6** |
| MEDIUM | 49 | 42 | −7 |
| low | 8 | 8 | 0 |

All 6 HIGH cleared: `CVE-2026-54512` / `CVE-2026-54513` (jackson-databind `2.21.0` → Jackson pin `2.21.4`) and
`CVE-2026-54399` / `CVE-2026-54428` (httpcore5 `5.4` / httpcore5-h2 `5.3.4` → commons `1.0.28-SNAPSHOT`). Remaining
MEDIUM/low findings are pre-existing transitive advisories with no HIGH-severity fix in scope for this ticket.

---

## Unit Test Plan

`mvn -f rates/pom.xml clean verify` = **BUILD SUCCESS** — **421 unit + 9 integration = 430 tests**, 0 failures,
0 errors (JUnit 5 only; no TestNG; 45 unit suites, 6 integration suites).

### New Tests (ext)

| # | Test Class | Test Method / Group | Coverage |
|---|-----------|---------------------|----------|
| 1 | `SpotRatesDaoIT` | `save` → `findByOfferKey` round-trip on `spotRateKey` | DAO against DynamoDB-Local |
| 2 | `SpotRatesDaoIT` | `findBySpotRateId` — GSI query plus the two-step hash-key fetch | Preserves the behavioural contract |
| 3 | `SpotRatesDaoIT` | `expiresOn` written as epoch-seconds `N`, milliseconds dropped | Native-TTL encoding |
| 4 | `SpotRatesDaoIT` | `spotRates` gzip above 300 KB fidelity | **Failed before the `GZip` fix** |
| 5 | `SpotRatesDaoIT` | Null-attribute omission | Avoids empty-`AttributeValue` writes |
| 6 | `SpotRatesAttributeConverterTest` | `compressedRoundTrip` + `className:json` encoding, foreign class prefix | **Reproduced the `GZip` truncation bug** |
| 7 | `AuditAttributeConverterTest` | Native-Map encode/decode with `ISO_DATE_TIME` | Converter unit |
| 8 | `LegacyMapConverterTest` | Map/List ↔ `AttributeValue` helper | Converter unit |
| 9 | `OffsetDateTimeTypeConverterTest` | Tolerant parsing — `Z`, `+00:00`, `+0000`, date-only | Legacy-read compatibility |
| 10 | `SpotRatesDaoTest` | Public API behaviour with a mocked repository | Unit |
| 11 | `SpotRatesModuleTest` | Provider wiring, offline via dummy `aws.accessKeyId`/`aws.secretAccessKey`/`aws.region` system properties; injector built from `SpotRatesModule` alone | Guice wiring + self-containment |

### Test Layer Coverage (ext)

| Layer | What it protects | Test Class | Faithfulness |
|-------|-----------------|------------|-------------|
| Persistence | On-wire fidelity, GSI two-step, TTL encoding | `SpotRatesDaoIT` | **High** — real DynamoDB-Local |
| Converters | JSON / gzip / Map / timestamp encodings | `SpotRates…`, `Audit…`, `LegacyMap…`, `OffsetDateTime…Test` | High — direct encode/decode |
| Guice wiring | Client construction without network | `SpotRatesModuleTest` | Medium — dummy credentials, no AWS call |
| Cross-module | booking-written items readable by rates | Foreign-class-prefix assertions in the converter tests | Medium — format-level, not a live shared-table test |
| Deployment | Real wiring end-to-end | QA ECS `Rates-qa` at steady state | **High** — real AWS |

**JaCoCo coverage of new classes (instruction):** `SpotRatesDao` 100%, `LegacyMapConverter` 100%,
`AuditAttributeConverter` 100%, `OffsetDateTimeTypeConverter` 97%, `SpotRatesAttributeConverter` 96%,
`SpotRatesModule` 95%. Residual uncovered lines are unreachable defensive guards (e.g. the `@Table`-missing
`IllegalStateException`, impossible because `SpotRatesDetail` always carries the annotation) and serialization
catch-blocks that valid inputs cannot trigger. 

### Manual Tests (ext)

| # | Scenario | Steps | Expected Result |
|---|----------|-------|----------------|
| 1 | Local build | `mvn package -pl rates -am -DskipTests` | BUILD SUCCESS, shaded `rates-1.0.jar` |
| 2 | Local boot against INT | `java -jar rates/target/rates-1.0.jar server rates/conf/int/config.yaml` | Dropwizard starts; cloud-sdk DynamoDB repository created for `inttra_int_booking_SpotRatesDetail`; no ERROR |
| 3 | Liveness | `GET :8081/admin/healthcheck` | 200 healthy |
| 4 | Live DynamoDB parity | `aws dynamodb describe-table` + `describe-time-to-live` per environment | Structure and TTL match the v2 annotations in all 4 envs |
| 5 | ECS health | `aws ecs describe-services` for `Rates-qa` / `Rates-dev` | QA at steady state, running 1/1 |

### Existing Test Impact (ext)

`SpotRatesDaoTest` and `SpotRatesModuleTest` were updated for the new types (`DynamoDBMapper` → `DatabaseRepository`);
`DynamoSupportTest` was deleted along with the `DynamoSupport` class it covered. Maersk MapStruct mapper tests,
`ContractRateService` and `TMClient` tests were untouched — they have no AWS surface. No test was weakened.

---

## Risks

**Key Risks**

- **Shared `*_booking` namespace with `booking` is the largest risk.** `rates` and `booking` read and write the same
  `SpotRatesDetail` table. The converters must produce booking's exact on-wire shape; a divergence would make one
  module's items unreadable by the other. Mitigated by porting the converters, tolerant class-prefix reads, and
  format-level tests.
- **Boot fragility on gateway outage.** The eager container-type cache warm-up in `ISOContainerToTmContainer`'s
  constructor makes `rates` exit at startup if the auth/network gateway is down — as happened on INT. Pre-existing and
  out of scope here, but it makes `rates` deployments unusually sensitive to gateway health.
- **12+ MEDIUM CVEs remain** (42 post-fix). All pre-existing transitive advisories with no HIGH-severity fix in scope.
- **CVT prefix trap** — `inttra2_test_booking`, not `inttra2_cvt`; 

---

## Dependencies

**Major Dependencies**

- **Released `commons 1.0.28`** — supplies the patched `httpcore5` that clears two of the four HIGH CVEs.
- **`cloud-sdk-api` / `cloud-sdk-aws` `1.0.28`** — provide `DatabaseRepository`, `DefaultQuerySpec`,
  `DynamoRepositoryFactory`, `BaseDynamoDbConfig` and `DateEpochSecondAttributeConverter`.
- **`booking`'s already-migrated `SpotRatesDetail` on-wire format** — the compatibility target for the shared table.
- **Externally provisioned DynamoDB table, GSI and TTL** — `rates` has no table-admin command and relies on them
  existing.
- **DynamoDB-Local** via `dynamo-integration-test` — required for the integration suite in CI.
- **A healthy auth/network gateway at startup** — a consequence of the eager cache warm-up noted under Resiliency.

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | **N** | No UI surface; no new data exposed. No endpoint, request or response change |
| 2 | Use of new services/ports | **N** | Same DynamoDB service and table, same app/admin ports 8080/8081. No messaging surface exists in this module |
| 3 | Authentication changes | **N** | commons `securityResources` OAuth token validation untouched; the Maersk/TM/network integrations are unchanged |
| 4 | New/changed encryption | **N** | `sseEnabled` values are unchanged (INT/QA/CVT `false`, PROD `true`) and SSE is table-level, externally provisioned. `rates` has no table-admin command so it cannot alter encryption. Transport remains TLS to AWS endpoints |
| 5 | Changes in the way data is transmitted | **Y** | The AWS transport stack changed: AWS SDK v1 → **AWS SDK 2.x over Apache HTTP** (via `cloud-sdk-aws`) for DynamoDB, and the `httpcore5` line moved to the patched version via commons `1.0.28`. Endpoints, region resolution, credentials chain, TLS and payloads are unchanged — only the client library |
| 6 | Changes in the way/location data is being stored | **N** | Same table, same account/region, same partition key, GSI and TTL, and byte-identical attribute encodings per the encoding contract. Only the mapping library changed (v1 `DynamoDBMapper` → v2 Enhanced Client). The `GZip` fix corrects a truncation defect; it does not change the encoding format |
| 120 | New API implementation / change of existing APIs (Please fill the API arch table) | **N** | No API added or changed — the API architecture table is filled for completeness and records "unchanged" for every row |
| 124 | New / Change in existing file upload functionality | **N** | No file upload/download functionality in this module |
| 125 | New / Change in integration within e2open or third-party apps | **Y** | The third-party AWS integration libraries were replaced: `dynamo-client` + `aws-java-sdk-dynamodb` (v1) removed, `cloud-sdk-api`/`cloud-sdk-aws` (AWS SDK 2.x) added, Jackson upgraded to `2.21.4` and Guava pinned to `33.5.0-jre`. The integrations themselves (which AWS service, which table) are unchanged. Maersk / TM / network integrations are untouched |
| 126 | New / Existing UI functionality support querying via either of them (VST, XML, java expressions, SQL or any other) | **N** | No VST/XML/java-expression/SQL querying. DynamoDB access is a typed partition-key lookup and a typed GSI query through the enhanced client — no expression language is exposed to input |

---

## REQUIRED: Documentation Changes

Answer the following questions.

| Question | Answer |
|----------|--------|
| Do end users interact with this feature? | **No.** Internal security remediation with no functional, API or UI change |
| Do project teams/SIs/BIT teams need to enable or configure this feature? | **No.** `conf/` is untouched — no key was added, removed or renamed, so nothing needs enabling or reconfiguring |
| Does the feature require special migration from prior releases? | **No.** No data migration and no configuration migration. DynamoDB tables, GSI, TTL and existing items are unchanged |
| What guides or content sections need updating? | No user-facing guide changes. Internal only: the migration programme's module tracker should record that `rates` has **no** table-admin command, so the `create-tables` → `dynamo-create` CI `$task` change does not apply |

### Engineering Documentation Impact (ext)

| Area | Impacted? | Details |
|------|-----------|---------|
| API docs (Swagger/OpenAPI) | No | No contract change; Swagger generation untouched |
| Runbook / operational procedures | No | No config or deployment-procedure change |
| Monitoring & alerting | No | No new metrics |

---

## Blocking Issues and Actions from the Design Review

| # | Issue/Action | Owner | Status | Due Date | Resolution |
|---|-------------|-------|--------|----------|------------|
| 1 | Raise a separate ticket for the eager container-type cache warm-up in `ISOContainerToTmContainer` that makes `rates` exit at boot on a gateway outage | Rates dev / Architecture | Open | Next cycle | Pre-existing and out of scope for ION-16110 |

---

## Deployment Verification (ext)

### QA — ✅ (2026-07-28)

| Test | Method | URL / Target | Result |
|------|--------|-----|--------|
| Service health | `aws ecs describe-services` | cluster `ANEQAWEBSVC-001`, service `Rates-qa`, taskDef `Rates-latest-qa-Task:5` | ✅ ACTIVE — desired 1 / **running 1**, rolloutState COMPLETED, *"has reached a steady state"* |
| Gateway health | Direct probe | `api-beta.inttra.com` | ✅ up (400/401) — the identical eager startup path completes cleanly |

### INT — ⚠️ (2026-07-28, superseded)

> The INT `api-alpha` gateway outage has since been resolved. Local startup verification on the current build is
> recorded below.

### Local startup on the current build — ✅ (2026-07-29, after the gateway fix)

`mvn package -pl rates -am -DskipTests` = BUILD SUCCESS (shaded `rates-1.0.jar`, ~113 MB), then booted against
`conf/int/config.yaml`. **This is the boot verification that the INT gateway outage previously made impossible.**

| Test | Evidence | Result |
|------|----------|--------|
| Gateway recovered | `api-alpha.inttra.com` `/auth` → **400**, `/network/containertype` → **401** (both were **502**) | ✅ up |
| DynamoDB wiring | `SpotRatesModule: Creating SpotRatesDetail partition-key repository for table: inttra_int_booking_SpotRatesDetail` | ✅ |
| Region / credentials | `BaseDynamoDbConfig: Resolved AWS region from DefaultAwsRegionProviderChain: us-east-1`; `Using DefaultCredentialsProvider` — confirms region is resolved from the provider chain, not from `config.yaml` | ✅ |
| Eager container-type warm-up | Completed without the `AuthClient.newToken` → HTTP 502 failure that previously aborted Guice provisioning | ✅ **cleared** |
| Startup errors | Full boot log | ✅ **0** ERROR / Exception |
| Server started | Jersey registered all 7 endpoints; connectors listening on 8080 (app) and 8081 (admin) | ✅ |
| Liveness | `GET :8080/rates/services/ping` | ✅ 200 |
| Build version | `GET :8080/rates/services/version` | ✅ 200 |
| Admin health | `GET :8081/admin/healthcheck` | ✅ 200 — *Basic functionality* and *deadlocks* both healthy |

The only log warning is benign and unrelated to this change: `LogbackAccessRequestLog — Missing
ch.logback.core.util.VersionUtil class on classpath` (logback-core earlier than 1.5.25).

---

## Design Document Review and Approval Matrix

> Add **"Approved"** or **"NA"** in the status column to approve the design document.
> **Approval Status Should have "Approved" or "NA" Only**

| Stage | Reviewer | Status | Notes | Ownership |
|-------|----------|--------|-------|-----------|
| Design | @Arijit Kundu | Approved | | **Product Management** |
| Product Owner | @Mahendran Pandian | | | **Product Owner** |
| Pre Dev Security | @Kamalesh Bhol | | | **InfoSec** |
| Pre Dev Architecture | @Arijit Kundu | Approved | | **Product Development** |
| Browser | NA | NA | No UI surface | **Product Development** |
| UX | NA | NA | No UI surface | **Product Development** |
| Post Dev Security | @Kamalesh Bhol | | OWASP post-scan: 6 HIGH → 0 HIGH | **InfoSec** |
| Post Dev Architecture | @Arijit Kundu | Approved | | **Product Development** |
| QA/Test Driven Development (TDD) | @Venkat Ganga | | 421 unit + 9 integration green; QA ECS at steady state | **Product Development/QA** |
