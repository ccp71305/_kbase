# value-added-service — OWASP + AWS SDK 2.x (cloud-sdk) Upgrade Design & Plan

**Ticket:** ION-16110
**Date:** 2026-07-24 (implemented 2026-07-27)
**Module:** `value-added-service`
**Reference modules:** `booking` (DynamoDB DAO/entity/converter/module patterns, jackson pin), `webbl` (SNS `NotificationService`/`EventPublisher`/`EventLogger` wiring), `network`/`auth`/`registration` (DynamoDB DAO/IT patterns).

## 1. Goal

1. Resolve the OWASP dependency-check HIGH CVEs by upgrading `com.inttra.mercury:commons` to `1.0.28-SNAPSHOT`
   and pinning Jackson to a patched line (`2.21.4`).
2. Migrate all AWS interactions off AWS SDK v1 to the in-house **cloud-sdk** (`cloud-sdk-api` + `cloud-sdk-aws`,
   AWS SDK 2.x) — DynamoDB (enhanced client) and SNS (notification workflow).
3. Keep every wire/disk format byte-compatible with existing 1.x data, proven by tests.

## 2. AWS footprint (value-added-service)

| Service | Before (AWS SDK v1) | After (cloud-sdk / AWS SDK 2.x) |
|---|---|---|
| DynamoDB | `aws-java-sdk-dynamodb 1.12.652` + `DynamoDBMapper` ORM (via `dynamo-client`) | `DatabaseRepository<DynamoDBValueAddedService, DefaultPartitionKey<String>>` + `@DynamoDbBean` entity + `AttributeConverter`s |
| SNS | `AmazonSNS` + commons `SNSEventPublisher`/`SNSClient`/`EventLogger` (`com.inttra.mercury.messaging.*`) | `NotificationService` + `EventPublisher`/`EventLogger` (`com.inttra.mercury.cloudsdk.notification.workflow.*`) |

Out of scope (unchanged): CMA/Hapag-Lloyd REST integrations, Parameter Store `${awsps:}`, carrier OAuth, swagger generation.

## 3. Forced sequencing (why the two commits overlap)

`commons 1.0.28-SNAPSHOT` **removes** the legacy `com.inttra.mercury.messaging.*` package entirely (verified: the
messaging/SNS classes exist only in `commons 1.R.01.023`; `1.0.28` ships `cloudsdk.notification.*` in
`cloud-sdk-api`/`cloud-sdk-aws` with no shim). Therefore the commons bump cannot compile without migrating the
SNS/`EventLogger` usage, and clearing the AWS-SDK-v1 CVEs requires dropping `dynamo-client`. The full production
cloud-sdk migration is thus part of the OWASP commit (commit 1). Commit 2 adds the DynamoDB-Local integration tests,
backward-compat round-trip fidelity coverage, and this documentation.

## 4. Dependency changes (`pom.xml`)

- `mercury.commons.version` `1.R.01.023` → `1.0.28-SNAPSHOT`.
- Add `<jackson.version>2.21.4</jackson.version>` + `dependencyManagement` import of `jackson-bom` (mirrors booking).
- Add `cloud-sdk-api`, `cloud-sdk-aws` (prod), `dynamo-integration-test` (test), `aws-java-sdk-dynamodb 1.12.721`
  (test, for DynamoDB Local), `assertj-core` (test).
- Remove `dynamo-client` and the production `aws-java-sdk-dynamodb 1.12.652`; drop `mercury.dynamodbclient.version`.

## 5. Backward-compatible on-wire encodings (the fidelity contract)

| Attribute | v1 encoding | v2 approach | Result |
|---|---|---|---|
| partition key | `id` (String) | `@DynamoDbPartitionKey @DynamoDbAttribute("id")` on `getHashKey()` | identical |
| `carrierResponse` (generic `Object`) | `DynamoSupport` string `"<fqcn>:<json>"` (or `"<len>|<fqcn>:<base64(gzip(json))>"` >300KB) | `CarrierResponseAttributeConverter` (String) delegating to **ported** `DynamoSupport` | byte-identical |
| `inttraResponse` | `DynamoSupport` string | `InttraResponseAttributeConverter` (String) | byte-identical |
| `expiresOn` | epoch-seconds Number (`DateToEpochSecond` = `getTime()/1000`) | cloud-sdk `DateEpochSecondAttributeConverter` (identical formula) | identical |
| `audit` | nested Map; timestamps ISO-8601 via `OffsetDateTimeTypeConverter` (`ISO_DATE_TIME`) | `@DynamoDbBean` nested; timestamps `@DynamoDbConvertedBy(OffsetDateTimeTypeConverter)` (`ISO_OFFSET_DATE_TIME`, identical for `OffsetDateTime`); `@JsonFormat` kept for REST | identical |
| `bookingNumber` GSI | `valueAddedServiceBookingNumber-index`, KEYS_ONLY, unpopulated | `@DynamoDbSecondaryPartitionKey` + `@GsiConfig(KEYS_ONLY)`; not written | preserved |
| table name | `<environment>_ValueAddedService` (e.g. `inttra_int_ValueAddedService`) | `BaseDynamoDbConfig.environment` → `tablePrefix = environment + "_"` | identical |

`DynamoSupport`, `GZip`, `DynamoSupportException` are **ported verbatim** into
`com.inttra.mercury.vas.dynamodb.support` (they came from `dynamo-client`, which is removed) so the generic-`Object`
serialization stays byte-for-byte identical.

## 6. Class changes

| Class | Change |
|---|---|
| `pom.xml` | dependency swap (§4) |
| `ValueAddedServiceApp` | `DynamoDBModule` → `ValueAddedServiceDynamoModule`; add `ValueAddedServiceMessagingModule` |
| `ValueAddedServiceConfig` | `dynamoDbConfig` type → `BaseDynamoDbConfig` (`@Valid @NotNull`); remove `dynamoDbTableConfig` |
| `ValueAddedServiceModule` | drop `AmazonSNS` binding + `SNSEventPublisher` provider; keep `Clock`, service defs, multibinders |
| `ValueAddedServiceDynamoModule` (new) | provides `DynamoDbClientConfig` + `ValueAddedServiceDao` (cloud-sdk repository) |
| `ValueAddedServiceMessagingModule` (new) | provides `NotificationService` + `EventPublisher` |
| `DynamoDBValueAddedService` | v1 ORM → `@Table`/`@DynamoDbBean` + enhanced key/converter annotations |
| `Audit` | `@DynamoDBDocument` → `@DynamoDbBean`; timestamp converters; keep `@JsonFormat` |
| `ValueAddedServiceDao` | `extends DynamoDBCrudRepository` → injected `DatabaseRepository`; `query` → `findById`/`save`, consistent read, `List` shape preserved |
| `CarrierResponseAttributeConverter` / `InttraResponseAttributeConverter` (new) | `AttributeConverter` via ported `DynamoSupport` |
| `dynamodb/support/{DynamoSupport,GZip,DynamoSupportException}` (new) | ported from `dynamo-client` |
| `DynamoValueAddedServiceTableCommand` | v1 `AbstractDynamoCommand` → cloud-sdk `DynamoDbAdminCommand` (annotation-driven) |
| `HapagLloyd{Routing,Contract}Client` | `messaging.logging.EventLogger`/`messaging.model.MetaData` → `cloudsdk.notification.workflow.*` |
| `conf/{int,qa,cvt,prod}/config.yaml` | `dynamoDbConfig` → cloud-sdk shape (`region`, `readCapacityUnits`, `writeCapacityUnits`, `sseEnabled`); remove `dynamoDbTableConfig` |

## 7. Testing strategy

- Unit tests for every new/changed public method (converters incl. byte-identical encoding assertions, ported
  `DynamoSupport`/`GZip`, config modules, table command).
- DynamoDB-Local integration test (`ValueAddedServiceDaoIT`, `@Tag("integration")`, `BaseDynamoDbIT`): save→findById
  round-trip (consistent read); generic-`Object` `carrierResponse` fidelity; `inttraResponse` fidelity; `expiresOn`
  epoch-seconds + 400-day calc; `audit` nested map with ISO timestamp; KEYS_ONLY GSI existence.
- SNS at the reference (booking/webbl) level — unit tests mocking `NotificationService`/`EventPublisher`; no live SNS IT.
- Certify JaCoCo coverage locally; keep all tests (unit + IT) green.

## 8. Backward-compatibility guarantees

Reads tolerate legacy data; writes reproduce the legacy representation. Table name, partition key, GSI projection,
per-env prefixes (incl. CVT `inttra2_cvt` vs SNS topic `inttra2_cv_sns_event`) and SNS topic ARNs are unchanged.

**Optional (null) attributes.** `carrierResponse` and `inttraResponse` are nullable per the DAO `save(...)` signature.
The v2 `AttributeConverter.transformFrom` returns `null` for a null input (mirroring the v1 mapper), so the enhanced
client **omits** the attribute rather than emitting an empty-typed `AttributeValue` (which DynamoDB rejects with
`ValidationException: Supplied AttributeValue is empty`). Covered by `ValueAddedServiceDaoIT.OptionalPayloads`
(null `carrierResponse`, and both payloads null).
