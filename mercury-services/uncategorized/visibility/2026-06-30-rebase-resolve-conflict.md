# ION-12316 — Visibility AWS SDK 2.x (cloud-sdk): rebase onto latest develop & resolve conflicts

**Branch:** `feature/ION-12316-visibiilty-aws-upgrade-copilot`
**Model:** Claude Opus 4.8 (1M context)
**Outcome:** single outgoing commit `9a795464c8` on top of latest develop (`a1f243c584`), pushed with
`--force-with-lease` to the feature branch after local review.

## Pending TODOs (deferred follow-ups, not in this PR)

- **Migrate `OperationType` off AWS SDK v1** in `visibility-matcher` (`MatchingProcessor`) and
  `visibility-s3-archiver` (`VisibilityS3Archiver`): replace
  `com.amazonaws.services.dynamodbv2.model.OperationType` with the lambda-events
  `com.amazonaws.services.lambda.runtime.events.models.dynamodb.OperationType` (already available via
  `aws-lambda-java-events`), then drop the `aws-java-sdk-dynamodb` compile dependency from both modules.
- **Elasticsearch request-signer migration** off `com.amazonaws.auth.*` in `visibility-inbound`
  (`ElasticSearchClientModule` / `AwsRequestSigner`) — tracked as the separate ES upgrade.
- **Failsafe property consistency**: switch the remaining module POMs' failsafe `<version>` reference from
  `${maven-surefire-plugin.version}` to the new `${maven-failsafe-plugin.version}` (same resolved value).

---

## 1. Summary

Rebased the visibility AWS-SDK-2.x (cloud-sdk) upgrade branch onto the latest `develop` and resolved all
merge conflicts. develop's latest functional changes (ION-16109 logging, ION-13761 Cargo Visibility OCBN/BL#
subscription endpoint + security/coverage, ION-3990 restricted-lists) took priority; the AWS-upgrade changes
were re-applied on top so the upgrade conforms to develop.

The single largest piece of work was a **functional/​upgrade collision**: develop's ION-13761 added a brand-new
`CargoVisibilitySubscription` model + DAO (and a whole `cargo.visibility.model` package) in **visibility-inbound**
built on the **legacy** `com.inttra.mercury.dynamo.*` wrapper + AWS SDK v1 annotations — but the AWS upgrade
removed the legacy dynamo wrapper from inbound. Per the incoming-wins rule, develop's new feature was preserved
**and** migrated to cloud-sdk (AWS SDK 2.x Enhanced Client + `DatabaseRepository`), mirroring the already-upgraded
`visibility-wm-inbound-processor` equivalents.

`mvn -f visibility/pom.xml clean verify` → **BUILD SUCCESS** across all 12 modules (unit + DynamoDB Local
integration tests + packaging). **1073 unit + 47 integration = 1120 tests, 0 failures, 0 errors.**

---

## 2. Rebase

- `git rebase origin/develop` replayed the single upgrade commit onto the latest develop.
- New base SHA: `a1f243c584` (= `origin/develop`). merge-base `f992aaa63132`.
- Backup taken before rebase: branch `feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-20260630`,
  tag `ION-12316-pre-refactor-backup-20260630`.

### Conflicts resolved (incoming develop wins, upgrade re-applied on top)

| # | File | Resolution |
|---|------|-----------|
| 1 | `visibility-inbound/.../service/CargoVisibilityService.java` (main) | Import conflict. Kept develop's new `CargoVisibilitySubscriptionDao` import (ION-13761) **and** the upgrade's cloud-sdk `MetaData` + `MessagingClient`; dropped legacy `messaging.model.MetaData` + `messaging.sqs.SQSClient`. Body auto-merged (`MessagingClient` + `subscriptionDao` both present). |
| 2 | `visibility-wm-inbound-processor/.../processor/WMEventProcessor.java` (main) | Class-decl conflict. Kept the upgrade's `implements StatusEventProcessor<SqsMessage>` (type migration) **and** develop's `PAYLOAD="Payload"` constant + `TokenAware`-based error handling; dropped the upgrade's now-unused `EMPTY_STR`/`CARGOWISE_PAYLOAD`. |
| 3 | `visibility-commons/.../config/VisibilityApplicationInjectorTest.java` (test) | Took the upgrade's cloud-sdk version (`--theirs`). develop's SDK v1 SNS mock setup was adapting the test to develop's SDK v1 wiring which the upgrade replaced; `configure()` assertions are identical, so zero coverage lost. |
| 4 | `visibility-inbound/.../config/VisibilityInboundApplicationInjectorTest.java` (test) | Real merge. Kept develop's new coverage (`createSesClientReturnsClient()` + SES wrapper, `testServiceDefinitions()`, AWS system-property save/restore, `createSesClient()` mock override); swapped develop's SDK v1 mock bindings for the upgrade's cloud-sdk mocks (`MessagingClient<String>`, `DatabaseRepository<ContainerEvent, DefaultPartitionKey<String>>`). Removed the duplicate `bindNetworkServices`/`createEventLoggingPublisher` since the merged production injector now does them from `config.getServiceDefinitions()`. |
| 5–7 | `visibility-inbound/.../config/DynamoContainerEvents{Outbound,Pending,}TableCommandTest.java` (modify/delete) | `git rm`. develop added `getRegionEndpoint`/`getSigningRegion` mock stubs, but the upgrade deleted the underlying `DynamoContainerEvents*TableCommand` classes (replaced by `VisibilityInboundDynamoDbAdminCommand`, which derives region/signing via cloud-sdk `dynamoConfig.toClientConfigBuilder()`). develop's region intent is preserved by the cloud-sdk admin command. |

---

## 3. Implementation — migrating develop's ION-13761 inbound feature to cloud-sdk

develop's new inbound `cargo.visibility.model` package + DAO used the legacy `com.inttra.mercury.dynamo.*`
wrapper (removed by the upgrade). Migrated to cloud-sdk, mirroring the wm-inbound-processor versions:

- **Nested document types** `Reference`, `TransportLeg`, `Location`, `LocationDate` → replaced with the wm
  cloud-sdk `@DynamoDbBean` versions (field-identical; only the SDK v1→v2 annotation migration differed).
- **`LegacyDynamoDbDateAttributeConverter`** (+ its test) copied into inbound (`cargo.visibility.model.converter`);
  it is wm-local, not shared by cloud-sdk.
- **`CargoVisibilitySubscription`** (inbound) → rewritten as `@DynamoDbBean @Table(name="CargoVisibilitySubscription")`:
  - `@DynamoDbPartitionKey @DynamoDbAttribute("id")` on `getHashKey()`
  - `@DynamoDbConvertedBy(DateEpochSecondAttributeConverter)` on `expiresOn` (was legacy `DateToEpochSecond`)
  - `@DynamoDbConvertedBy(LegacyDynamoDbDateAttributeConverter)` on `createdOn`/`modifiedOn` (legacy default ISO-8601 String marshalling)
  - `@DynamoDbSecondaryPartitionKey` on `carrierBookingNumber` (`bookingNumber-carrierScac-index`),
    `billOfLadingNumber` (`billOfLading-carrierScac-index`), `subscriptionReference` (`subscriptionReference-index`)
  - `@DynamoDbSecondarySortKey` on `carrierScac` for both the booking & BoL composite indexes
  - enums (`state`, `type`, `clientType`) — dropped `@DynamoDBTypeConvertedEnum`; SDK 2.x stores enum `name()` as String (same on-disk form), matching the wm reference.
  - **Verified exact parity with develop:** 22/22 attributes, 3/3 GSI index constants, identical hash/sort keys.
- **`CargoVisibilitySubscriptionDao`** (inbound) → rewritten on `DatabaseRepository` + `DefaultQuerySpec`
  (partition + `carrierScac` sort key, `sortKeyCondition("EQ")`) for the booking/BoL GSI queries and
  `repository.findById(DefaultPartitionKey)` for full loads. **5/5 public/package method signatures identical to
  develop**, same orchestration and trim semantics (no lowercasing).
- **`VisibilityInboundDynamoModule`** (new) `@Provides` the inbound `CargoVisibilitySubscriptionDao` from the
  shared `DynamoDbClientConfig` (mirrors `VisibilityWMDynamoModule`); installed in `VisibilityInboundApplication`
  alongside `VisibilityDynamoModule`.

### Alignment with the real table (per `docs/2026-06-26-aws-service-resource-details.md`)

The live `CargoVisibilitySubscription` table (hash `id`) carries GSIs `billOfLading-carrierScac`,
`bookingNumber-carrierScac`, `bookingNumber`, `subscriptionReference` (tables show 5/5 GSIs). The migrated inbound
model's GSIs (`bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index`, `subscriptionReference-index`)
**match the real table structure**. Note: `visibility-wm-inbound-processor` has **no dedicated ECS service** in the
VIS clusters (its queues exist) — it may be dormant. The inbound and wm `CargoVisibilitySubscription` models are
**not shared** in develop — they are two separate per-module classes (same package name) with different views of
the same table. This migration kept each module's schema exactly as develop and only changed the SDK layer.

### Backward compatibility

Proven by `CargoVisibilitySubscriptionDaoIT` (DynamoDB Local round-trip): `createdOn`/`modifiedOn` persist as
ISO-8601 Strings (S) and `expiresOn` as epoch-seconds Number (N) — byte-compatible with the legacy 1.x
`DynamoDBMapper` representation.

---

## 4. Tests & coverage

All new/changed code is exercised by unit + integration tests; `mvn -f visibility/pom.xml clean verify` runs the
JaCoCo report per submodule (`<module>/target/site/jacoco/`).

### Tests added / updated
- **New:** `VisibilityInboundDynamoModuleTest` (unit), `CargoVisibilitySubscriptionDaoIT` (DynamoDB Local IT —
  booking & BoL composite GSIs, latest-modified selection, orchestration, Date-format backward-compat),
  `LegacyDynamoDbDateAttributeConverterTest` (copied into inbound).
- **Rewritten for cloud-sdk:** inbound `CargoVisibilitySubscriptionDaoTest` (mocks `DatabaseRepository`,
  `ArgumentCaptor` asserts the `DefaultQuerySpec` index/partition/sort/`EQ`), `CargoVisibilityServiceRetrievalTest`
  (`SQSClient`→`MessagingClient<String>`), `WMEventProcessorTest` (`Message`→`SqsMessage` in develop's new
  `TokenAware` test).
- **De-flaked:** `CargoVisibilityServiceParallelProcessingTest.shouldCompleteRunningTasksBeforeShutdown` — replaced
  fixed `Thread.sleep` timing with a `CountDownLatch` handoff (hold the task in-flight, release, then graceful
  shutdown), making it deterministic under full-suite load.
- **Hermetic credential fix** (pre-existing/environmental, not introduced by the rebase): `VisibilityDynamoModuleTest`,
  `VisibilityWMDynamoModuleTest`, `VisibilityInboundDynamoDbAdminCommandTest` build a real `DynamoDbClientConfig`,
  whose cloud-sdk `BaseDynamoDbConfig.applyDefaultCredentials()` eagerly resolves via `DefaultCredentialsProvider`.
  Added dummy AWS system properties in `@BeforeAll`/`@AfterAll` using **SDK v2** names via
  `software.amazon.awssdk.core.SdkSystemSetting` (`AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
  Root cause of the first failed attempt: SDK v1 `SDKGlobalConfiguration.SECRET_KEY_SYSTEM_PROPERTY` is
  `aws.secretKey`, but the SDK v2 `SystemPropertyCredentialsProvider` reads `aws.secretAccessKey`.

### Passing test commands
```bash
mvn -f visibility/pom.xml clean test     # unit (surefire) — all green
mvn -f visibility/pom.xml clean verify    # unit + integration (failsafe, DynamoDB Local) + JaCoCo — BUILD SUCCESS
# isolated re-runs used during triage:
mvn -f visibility/pom.xml test -pl visibility-commons -Dtest=VisibilityDynamoModuleTest
mvn -f visibility/pom.xml test -pl visibility-inbound -Dtest=VisibilityInboundDynamoDbAdminCommandTest,CargoVisibilityServiceParallelProcessingTest
```

### Test-count summary (single JUnit/Jupiter runner — surefire=unit, failsafe=integration)
- **Unit (surefire):** 1073 tests across 187 report files
- **Integration (failsafe, DynamoDB Local):** 47 tests across 29 report files
- **Total: 1120, 0 failures, 0 errors** (2 skipped pre-existing)
- New inbound DAO IT contributes 7 integration tests (BookingNumberIndex 3, BillOfLadingIndex 2,
  FindLatestSubscription 1, DateStorageFormat 1).

---

## 4a. Review follow-ups (post-review fixes)

1. **SNS coverage in `VisibilityApplicationInjectorTest` (commons).** Re-checked. develop's version asserted the
   1.x SNS classes (`AmazonSNS`, `AmazonSNSClient`, `AbstractAmazonSNS`) plus `EventPublisher`; the upgrade version
   (taken via `--theirs`) drops the 1.x assertions because those classes no longer exist and asserts
   `getInstance(EventPublisher.class)` instead. **SNS coverage is preserved** because in cloud-sdk the SNS event
   publisher *is* `EventPublisher`: the test's `InjectorTest.configure()` sets `enabled=true` +
   `snsEventTopicArn="sndArn"` and calls `createEventLoggingPublisher(eventLoggingConfig)`, which exercises the
   SNS-backed branch `NotificationClientFactory.createDefaultClient(snsEventTopicArn)` (vs `EmptyEventPublisher`
   when disabled). The SNS publishing/mapping logic itself is additionally covered by `SNSMapperTest` and the
   cloud-sdk `NotificationClientFactory` tests in `mercury-services-commons`. No coverage was lost.

2. **Removed the 1.x `SDKGlobalConfiguration` from `VisibilityInboundApplicationInjectorTest`.** develop's ION-13761
   added an AWS system-property save/restore using the **AWS SDK v1** `com.amazonaws.SDKGlobalConfiguration` (needed
   so the new `createSesClientReturnsClient()` test can build a real `SesClient.create()` with a resolvable region).
   Since the goal is to remove 1.x, this was migrated to **AWS SDK v2** `software.amazon.awssdk.core.SdkSystemSetting`
   (`AWS_REGION` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`), dropping the now-unnecessary EC2-metadata toggle
   (explicit dummy creds prevent any metadata fallback). This was also the right fix for credential resolution:
   v1 `SECRET_KEY_SYSTEM_PROPERTY` is `aws.secretKey`, but the v2 provider chain reads `aws.secretAccessKey`.
   After this change the entire migrated inbound feature (model, DAO, nested types, module, and its tests)
   contains **zero** AWS SDK v1 code/imports. (The copied `LegacyDynamoDbDateAttributeConverter` mentions
   `com.amazonaws.util.DateUtils#formatISO8601Date` only in a `{@code}` javadoc comment that documents the legacy
   on-disk format it reproduces — text only, no import or compile dependency; identical to the wm reference.)

3. **DAO integration-test coverage — confirmed complete.** The inbound `CargoVisibilitySubscriptionDao` makes
   exactly four DynamoDB repository calls, all exercised by `CargoVisibilitySubscriptionDaoIT` against DynamoDB Local:
   - `repository.query(...)` on the **bookingNumber-carrierScac** GSI (DAO L145) → `findByBookingNumber`,
     `findLatestByBookingNumber`, `prefersBookingThenFallsBackToBol`
   - `repository.query(...)` on the **billOfLading-carrierScac** GSI (DAO L175) → `findByBillOfLading`,
     `findByBillOfLadingUnknown`, `prefersBookingThenFallsBackToBol`
   - `repository.findById(DefaultPartitionKey)` full-item load (DAO L43, L80) → all of the above (incl. the
     most-recently-modified selection across multiple loaded items)
   Plus `dateFieldsUseLegacyTypes` asserts the raw on-disk Date representation. (`repository.save` is the seeding
   primitive, not a DAO method.)

4. **AWS SDK v1 in the visibility POMs — status.**
   - `aws-lambda-java-core` / `aws-lambda-java-events` (commons, error-email, outbound-poller, pending-start,
     s3-archiver, itv-gps, matcher) are the **AWS Lambda runtime/event model**, *not* the AWS SDK — required by the
     lambda handlers regardless of SDK version. **Keep.**
   - `aws-java-sdk-dynamodb` + `aws-java-sdk-core` `1.12.721` (**visibility-commons**) are the genuine AWS SDK v1.
     They are **still required by pre-existing upgrade-branch code that this rebase did not touch**: the legacy
     `DynamoDBTypeConverter`-based converters under `visibility-commons/.../model` and
     `.../containerEvent/converters/*`, `TransportationDetail`'s `@DynamoDBIgnore`, the Lambda DynamoDB-stream model
     classes (`com.amazonaws.services.dynamodbv2.model.OperationType`, `ProvisionedThroughputExceededException`),
     and the Elasticsearch request signer in `visibility-inbound` (`com.amazonaws.auth.AWS4Signer` /
     `DefaultAWSCredentialsProviderChain` in `ElasticSearchClientModule` + `AwsRequestSigner`).
   - **Conclusion:** my changeset introduces **no** new v1 usage (and removed the one v1 reference I had carried in
     a test). Fully dropping `aws-java-sdk-core`/`aws-java-sdk-dynamodb` requires migrating those remaining commons
     converters + the ES request signer to SDK 2.x (e.g. the OpenSearch SDK / AWS Crt signer) — a **separate,
     larger upgrade task outside this rebase's scope**, recommended as a follow-up.

---

## 4b. Review follow-ups — round 2 (1.x cleanup, POM hygiene, coverage)

Full `mvn -f visibility/pom.xml clean verify` remained **BUILD SUCCESS** across all 12 modules after these.

1. **Removed dead AWS SDK v1 DynamoDB converters from `visibility-commons`.** All ten `com.amazonaws`
   usages in commons *main* were dead/test-only (the production entities already use the AWS SDK 2.x
   `*AttributeConverter`s):
   - Deleted 8 unused v1 `DynamoDBTypeConverter` converters: `DateToEpochSecond`, `DateToEpochMilliSecond`,
     `DateToIso8601`, `SubscriptionConverter`, `MetaDataConverter`, `ContainerEventEnrichedPropertiesConverter`,
     `ContainerEventSubmissionConverter`, `GISOutboundDetailsConverter`, plus the 2 orphaned unit tests
     (`MetaDataConverterTest`, `GISOutboundDetailsConverterTest` — the 2.x `*AttributeConverterTest`s remain).
   - `ContainerTrackingEventMessageConverter` (a test-only JAXB XML→`ExportSEPartInt` helper, its `convert()`
     was a dead `null`-returning TODO) → converted to a plain utility (dropped the v1
     `DynamoDBTypeConverter` interface + `@Override`s); `ExternalContainerTrackingServiceTest` still uses it.
   - `TransportationDetail` had a dead `import com.amazonaws...DynamoDBIgnore` (a Swagger `@ApiModel`, never a
     DynamoDB bean) → removed.
   Result: **`visibility-commons` main + test now contain zero AWS SDK v1 references.**

2. **`Condition.java` — removed the redundant explicit getter (PR comment #6).** The Enhanced Client derives
   the attribute name `values` from the property name, so `@DynamoDbAttribute("values") getValues()` was a
   no-op; removed it and the now-unused `DynamoDbAttribute` import, relying on the Lombok getter (consistent
   with the sibling fields). Persisted attribute name unchanged (`values`), covered by the commons DynamoDB IT.

3. **`visibility-commons/pom.xml` — AWS SDK v1 moved off the compile classpath (your question).** The
   `aws-java-sdk-dynamodb` + `aws-java-sdk-core` `1.12.721` were **not used by commons code** — they are a
   version pin for the embedded **DynamoDB Local (2.5.2)** which needs `1.12.721` (`OnDemandThroughput`). They
   were wrongly at **compile** scope (leaking transitively to every downstream module). Fixed by moving both to
   **`test` scope** and managing them **locally** (no parent `<dependencyManagement>`, per your direction).
   The full verify confirmed downstream DynamoDB-Local ITs (inbound, wm, s3-archiver) still pass — they resolve
   `1.12.721` transitively via the `dynamo-integration-test` artifact, so the commons compile-scope leak was
   unnecessary.

4. **Downstream modules now declare their AWS SDK v1 usage locally** (they previously inherited it transitively
   from commons at compile scope):
   - `visibility-matcher`, `visibility-s3-archiver`: `aws-java-sdk-dynamodb` at **compile** scope
     (`MatchingProcessor` / `VisibilityS3Archiver` use `com.amazonaws.services.dynamodbv2.model.OperationType`
     for DynamoDB-stream event handling — needed, per your note).
   - `visibility-outbound`: `aws-java-sdk-dynamodb` at **test** scope
     (`ProvisionedThroughputExceededException` in a test).
   - `visibility-inbound` needed no addition: its ES request-signer (`com.amazonaws.auth.*`, a separate ES
     upgrade) and its DynamoDB-Local ITs resolve v1 transitively; verified green.

5. **Parameterized hard-coded versions into Maven properties (PR comments #3 & #5).** Added to the parent
   `visibility/pom.xml`: `log4j.version=2.23.1`, `aws-java-sdk-v1.version=1.12.721`,
   `maven-dependency-plugin.version=3.6.1`, and `maven-failsafe-plugin.version` (= `${maven-surefire-plugin.version}`).
   Replaced the hard-coded `2.23.1` / `1.12.721` / `3.6.1` in `visibility-commons/pom.xml` and the `2.23.1` /
   `3.6.1` in `visibility-inbound/pom.xml` with the properties; new local v1 deps use `${aws-java-sdk-v1.version}`.

6. **`maven-failsafe-plugin` version (your question).** It used `${maven-surefire-plugin.version}` because the
   Surefire and Failsafe plugins are released **in lockstep with identical version numbers** (same Apache
   Surefire project), so functionally it was correct — just semantically imprecise. Added a dedicated
   `maven-failsafe-plugin.version` property (pointing at `${maven-surefire-plugin.version}` to preserve the
   lockstep) and switched the `commons`/`inbound` failsafe declarations to it. (The other module POMs still
   reference `${maven-surefire-plugin.version}` for failsafe; they resolve to the same `3.5.2` and can be
   switched to the new property for full consistency in a follow-up.)

7. **Added the missing `BookingDaoIT` (your coverage question).** `BookingDao.findBookingByInttraReference`
   was only **unit**-tested (`BookingDaoTest`, mocked repository) — its two real DynamoDB `repository.query`
   calls were not integration-tested. Added `BookingDaoIT` (DynamoDB Local, `@Tag("integration")`) that
   exercises both: the `INTTRA_REFERENCE_NUMBER_INDEX` GSI query (`findByInttraReferenceNumberFromInttraRefIndex`)
   and the main-table composite-key lookup (`findBookingDetail`, `bookingId` + `sequenceNumber`), including the
   carrier(`CONFIRM`)/customer(`REQUEST`) version resolution and the null/blank/unknown-reference empty paths.
   2 tests, green against DynamoDB Local.

**Recommended follow-ups (out of scope here):** migrate `MatchingProcessor`/`VisibilityS3Archiver` to the
`aws-lambda-java-events` `OperationType` (already a dependency) to drop `aws-java-sdk-dynamodb` from those two
modules entirely; complete the Elasticsearch request-signer migration off `com.amazonaws.auth` (separate ES
upgrade); switch the remaining module POMs' failsafe version reference to `${maven-failsafe-plugin.version}`.

---

## 5. cloud-sdk gaps

**None blocking.** One minor observation: there is no **shared** cloud-sdk `java.util.Date` "legacy default
marshalling" converter — `cloud-sdk-aws` ships `DateEpochSecondAttributeConverter` (epoch seconds) but not an
ISO-8601-String `Date` converter. Both `visibility-wm-inbound-processor` and now `visibility-inbound` carry a
module-local `LegacyDynamoDbDateAttributeConverter`. **Proposed enhancement:** promote
`LegacyDynamoDbDateAttributeConverter` into `com.inttra.mercury.cloudsdk.database.converter` so modules migrating
legacy un-annotated `Date` fields can reuse it instead of duplicating.

---

## 6. Command log (key commands, with intent)

```bash
git fetch origin; git log --oneline origin/develop..HEAD          # 1 outgoing upgrade commit
git log --oneline HEAD..origin/develop -- visibility/             # new develop commits touch visibility -> rebase needed
git branch ...-backup-20260630; git tag ION-12316-pre-refactor-backup-20260630   # safety backup
git rebase origin/develop                                         # 7 conflicts (4 content, 3 modify/delete)
git diff f992aaa63132 origin/develop -- <file>                    # inspect each side's intent vs merge-base
git checkout --theirs <commons injector test>                     # take upgrade cloud-sdk version
git rm <3 obsolete *TableCommandTest.java>                        # underlying classes deleted by upgrade
git rebase --continue                                             # -> single commit f60f230132
mvn -f visibility/pom.xml clean test-compile -DskipTests          # surfaced legacy com.inttra.mercury.dynamo.* refs
git cat-file -e origin/develop:.../CargoVisibilitySubscriptionDao.java  # confirm inbound model+dao are develop's (ION-13761)
# kb_grep / kb_find_files over mercury-services-commons for DefaultQuerySpec, CloudAttributeValue, DatabaseRepository, sortKeyCondition
mvn -f visibility/pom.xml clean verify                            # full unit + IT + JaCoCo -> BUILD SUCCESS
git add -u && git add <new files>; git commit --amend --no-edit   # fold into the single ION-12316 commit
git log --oneline develop..HEAD                                   # exactly 1 line: 445d0ca74f
```

---

## 7. Build / packaging results

`mvn -f visibility/pom.xml clean verify` → **BUILD SUCCESS**. Reactor: visibility, visibility-commons,
visibility-inbound, visibility-wm-inbound-processor, visibility-matcher, visibility-outbound, visibility-pending,
visibility-s3-archiver, visibility-pending-start, visibility-error-email, visibility-outbound-poller,
visibility-itv-gps-processor — all SUCCESS. Shaded JARs produced per service.

---

## 8. Token-usage

Captured automatically by the mcp-context-server harness hooks (Copilot CLI `agentStop`). Verify via
`session_usage_report` for session `f74edefafd0a47a7`.

---

## 9. References

- Jira: **ION-12316** (AWS upgrade), with develop functional changes **ION-13761** (Cargo Visibility OCBN/BL#
  subscription endpoint), **ION-16109** (logging), **ION-3990** (restricted lists).
- Reference modules (cloud-sdk templates): `visibility-wm-inbound-processor` (CargoVisibilitySubscription model/DAO/
  module/IT), booking/network (SQS/SNS), booking (S3), booking/network/registration (DynamoDB).
- Reference prompt: `.github/prompts/refactor/2026-06-25-visibility-sns-sqs-refactor-prompt.md`.
- AWS resource topology: `visibility/docs/2026-06-26-aws-service-resource-details.md`.
- Prior session: `284a7cba1d4244ee` (ION-12316 implementation). This session: `f74edefafd0a47a7`.
- Single commit: `445d0ca74f` — **not pushed** (awaiting review).
