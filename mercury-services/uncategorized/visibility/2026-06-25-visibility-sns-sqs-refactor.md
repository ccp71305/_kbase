# Visibility — Complete SQS/SNS cloud-sdk migration, DynamoDB admin-command idempotency, CI dependency fix

**Jira**: ION-12316
**Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot`
**Date**: 2026-06-25
**Model**: Claude Opus 4.8 (1M context)
**Backup**: branch `feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-25`, tag `ION-12316-pre-sns-sqs-backup-2026-06-25`
**Prior write-ups**: [`2026-06-24-visibility-refactor-sns-sqs-coverage.md`](./2026-06-24-visibility-refactor-sns-sqs-coverage.md), [`2026-06-23-visibility-rebase-refactor.md`](./2026-06-23-visibility-rebase-refactor.md)

---

## 1. Summary

This change completes the ION-12316 visibility AWS SDK 2.x (cloud-sdk) upgrade by landing the **SQS + SNS backbone
migration** that the 2026-06-24 pass had documented but deferred, aligning the visibility dependency set with the
**booking** module (the in-production reference), fixing the **Jenkins CI dependency failure** in
`visibility-matcher` / `visibility-pending`, and adding an **idempotency integration test** for the visibility
DynamoDB admin command — which surfaced and fixed a **latent production bug**.

Everything is verified with `mvn -f visibility/pom.xml clean verify`: **1009 unit + 40 integration tests, 0 failures,
0 errors, 6 (pre-existing) skips**. All work is folded into the single ION-12316 commit. **Pushed** to
`origin/feature/ION-12316-visibiilty-aws-upgrade-copilot` on 2026-06-27 via `--force-with-lease` (see §12). PR
[#1066](https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/1066) → `develop`.

---

## 2. Rebase onto latest develop

`origin/develop` had advanced with new visibility commits (`ION-16065`, `ION-16054`), so the single ION-12316 commit
was rebased onto it (clean, no conflicts):

```bash
git fetch origin
git log --oneline HEAD..origin/develop -- visibility/      # showed ION-16065 / ION-16054
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-25
git tag    ION-12316-pre-sns-sqs-backup-2026-06-25
git rebase origin/develop                                  # clean
git log --oneline origin/develop..HEAD                     # exactly 1 commit
```

---

## 3. CI dependency fix (`visibility-matcher`, `visibility-pending`)

**Symptom (Jenkins).** `Could not resolve … com.inttra.mercury:booking:jar:2.1.8.M (absent)` →
`visibility-matcher` FAILURE and, transitively (it depends on matcher), `visibility-pending` FAILURE.

**Root cause.** `booking` deploys a separate *booking-model* artifact `com.inttra.mercury:booking:<ver>.M` to an S3
repo. The 2026-06-24 commit bumped **`visibility-commons`** to the current `booking:3.0.0.M` but left
**`visibility-matcher`** pinned to the now-purged `booking:2.1.8.M`. Two different booking-model versions in one reactor,
with the older one absent from Artifactory.

**Fix.** `visibility-matcher/pom.xml` → `booking` version `2.1.8.M` → `3.0.0.M` (matching `visibility-commons`). The
matcher consumes only `com.inttra.mercury.booking.model.*` (`Booking`, `BookingDetail`, `Contract`,
`BookingRequestContract`, `TransactionReference`), all present and API-compatible in `3.0.0.M`.

```bash
mvn -f visibility/pom.xml -pl visibility-matcher,visibility-pending -am clean test   # green
```

---

## 4. Dependency alignment with booking (single version property + direct cloud-sdk deps)

**Finding.** booking uses a **single** property `mercury.commons.version = 1.0.26-SNAPSHOT` for `commons`,
`cloud-sdk-api`, `cloud-sdk-aws`, and `dynamo-integration-test`. Visibility was split/stale:
`mercury.commons.version = 1.R.01.023` (the legacy commons that still ships `com.inttra.mercury.messaging.*` — 25
classes) **plus** a separate `mercury.cloudsdk.version = 1.0.26-SNAPSHOT`. `commons` 1.0.26 ships **0** `messaging.*`
classes, so bumping it **forces** the SQS/SNS migration to cloud-sdk.

**Change.**
- `visibility/pom.xml`: consolidated to a single `mercury.commons.version = 1.0.26-SNAPSHOT`; removed
  `mercury.cloudsdk.version`. (The legacy `mercury.dynamodbclient.version = 1.R.01.023` for `dynamo-client` — a
  different, lib-local artifact — is retained.)
- All `${mercury.cloudsdk.version}` references repointed to `${mercury.commons.version}`.
- `cloud-sdk-api` + `cloud-sdk-aws` declared as **direct** dependencies in every module that uses them
  (`visibility-inbound`, `-outbound`, `-pending`, `-itv-gps-processor`, `-wm-inbound-processor`, `-s3-archiver`,
  `-outbound-poller`, `-pending-start`).
- **Removed the deprecated `dynamo-client`** (legacy AWS SDK v1 wrapper) entirely, matching booking
  (`<!-- dynamo-client removed: All DAOs migrated to cloud-sdk-aws -->`). Its only remaining use was the obsolete
  `DynamoDbTableCreationCommandConfig` (per-table throughput/GSI config consumed by the old v1 `CreateTables` commands);
  the cloud-sdk `DynamoDbAdminCommand` derives all of that from the entity annotations + `BaseDynamoDbConfig`, so the
  `getDynamoDbTableCreationCommandConfig` / `getTableConfig` field+methods (dead in main, used only by a test) and the
  `dynamoDbTableCreationCommandConfig:` YAML block in **all 20** visibility `config.yaml` files were removed, along with
  the `mercury.dynamodbclient.version` property.
- **Exception — `visibility-matcher`**: declares `cloud-sdk-api` directly (it uses `MessagingClient` / the
  `notification.workflow` models) but **not** `cloud-sdk-aws`, and **excludes `io.searchbox:jest`** from `cloud-sdk-api`.
  See the Jest gap in §8.

ES side-effect forced by the commons bump: the legacy `com.inttra.mercury.module.JestModule` and
`com.inttra.mercury.config.ElasticSearchServiceConfig` were dropped from commons 1.0.26 in favour of
`com.inttra.mercury.cloudsdk.aws.module.JestModule` and `com.inttra.mercury.cloudsdk.config.ElasticSearchServiceConfig`
(identical 8-method interface). `ESConfiguration`, `ElasticSearchClientModule`, and `VisibilityApplicationInjector`
were repointed accordingly (booking does the same).

---

## 5. SQS/SNS cloud-sdk migration (booking as template)

**Reference (booking, in production).** booking wraps the cloud-sdk in thin `SQSClient` / `SNSClient` adapters and a
`BookingMessagingModule` that `@Provides MessagingClient<String>` (`MessagingClientFactory.createDefaultStringClient()`),
`NotificationService` (`NotificationClientFactory.createDefaultClient(topicArn)`), and `StorageClient`.

**Model/logging types — scripted 1:1 FQN remap (48 files).** The legacy `messaging.model.MetaData/Event/Annotation(s)`,
`messaging.logging.EventGenerator/EventLogger/EventPublisher/ErrorHelper`, and `messaging.util.RandomGenerator` are
**field- and builder-identical mirrors** of `cloudsdk.notification.workflow.*` / `notification.annotation.*` /
`notification.util.*` with the same `toJsonString()` / `parseJson()` canonical serializers. Because `MetaData` is also
persisted in DynamoDB (`ContainerEvent` + `MetaDataAttributeConverter`), the swap keeps the on-disk JSON
**byte-identical** — re-verified by the existing converter tests.

**SQS consumers.** `messaging.sqs.SQSClient` (AWS v1, returns `com.amazonaws.services.sqs.model.Message`) →
`cloudsdk.messaging.api.MessagingClient<String>` (`listMessages` / `sendMessage` / `deleteMessage`, returns
`QueueMessage<String>`). Migrated `SqsMessageHandler` + `SqsMessageHandlerManager` and every consumer that builds the
task: `-inbound` (`InboundEdiProcessor`, `CargoVisibilityService`, `ReprocessService`), `-matcher`
(`MatchingProcessor`, `AbstractMatcher`), `-outbound` (`Outbound{Single,Multi}TransactionProcessor`, `OutboundGenerator`),
`-pending` (`PendingSqsProcessor`), `-itv-gps` (`GPSEventProcessor`), `-wm` (`WMEventProcessor`).

**New `SqsMessage` wrapper.** `QueueMessage<String>` is immutable (getters only), but the processing loop needs the
per-message control flags `doNotDelete` / `doNotSendToDlq` that a consumer toggles and the handler reads to decide
delete vs DLQ. A small mutable `SqsMessage` wraps the `QueueMessage` payload + those flags, preserving the exact
delete/DLQ semantics. `SqsMessageHandler.setDoNotDelete()` / `setDoNoSendToDlqKey()` now set booleans on it (replacing
the previous attribute-map hack).

**SNS / event logging.** `messaging.sns.SNSClient` + `messaging.logging.SNSEventPublisher` →
`cloudsdk.notification.api.NotificationService` (which `extends EventPublisher`). `VisibilityApplicationInjector`'s
`createEventLoggingPublisher` now returns `NotificationClientFactory.createDefaultClient(snsEventTopicArn)` when enabled,
else `EmptyEventPublisher` (now implementing the cloud-sdk `EventPublisher`).

**Guice wiring.** New `VisibilityMessagingModule` `@Provides MessagingClient<String>` via the cloud-sdk factory
(mirroring `BookingMessagingModule`). All six service apps drop `new SQSModule(e)` + `new SNSModule(e)` for
`new VisibilityMessagingModule()`. The legacy `commons` `messaging.*`/AWS-v1 SQS/SNS dependency is gone.

**Backward compatibility.** SQS message bodies and the SNS event payloads are produced/consumed exactly as before
(payload types unchanged; `MetaData`/`Event` JSON byte-identical) — proven by the migrated processor tests.

---

## 6. SQS/SNS test level (matched to booking — no new live ITs)

booking covers SQS/SNS with **unit tests that mock `MessagingClient` / `NotificationService`** (e.g.
`BookingMessagingModuleTest`, `SQSClientTest`, `SNSClientTest`, `BookingProcessorTaskTest`) — there are **no** live
SQS/SNS / localstack integration tests. Visibility was aligned to exactly that level: the ~30 affected tests now mock
`MessagingClient<String>` / build `QueueMessage` / `SqsMessage`, using AssertJ, `@Nested`, and `@ParameterizedTest`.
`SqsMessageHandlerTest` and the four `*ApplicationInjectorTest`s were rewritten for the cloud-sdk wiring. **No new live
SQS/SNS integration tests were added.**

---

## 7. DynamoDB admin command — idempotency + integration test (Goal 3)

**booking reference.** `BookingDynamoDbAdminCommand extends cloudsdk…DynamoDbAdminCommand`; the base
`createTableWithGsisIfNotExists(...)` is idempotent. `BookingDynamoDbAdminCommandIT` (DynamoDB Local via
`BaseDynamoDbIT`, a `TestableCommand` overriding `createDynamoDbClient` to point at DynamoDB Local + `runPublic`) has an
`IdempotentCreation` test that runs the command twice.

**New `VisibilityInboundDynamoDbAdminCommandIT`** (7 tests, mirroring booking): client-config resolution (prefix
`inttra_int_`, capacities, null guards); table creation (`container_events` + its 5 GSIs, `container_events_outbound`,
`container_events_pending`, with correct key schema); and **idempotency** — a second run skips the existing
tables/GSIs (logged by `createTableWithGsisIfNotExists`), succeeds, and leaves the key schema + GSI set unchanged.

**IT infra added to `visibility-inbound/pom.xml`** (mirroring `visibility-commons`): `dynamo-integration-test`,
surefire `excludedGroups=integration`, `maven-dependency-plugin` (copy DynamoDB-Local native libs), `maven-failsafe-plugin`,
and the `log4j-api`/`log4j-core` 2.23.1 pin (DynamoDB Local needs `LoaderUtil.getClassLoaders()`).

**Latent production bug found & fixed.** The IT surfaced that the command would **fail in production** for
`container_events_pending`: its partition key was `LocalDate createDate` with `@DynamoDbConvertedBy(DateIso8601AttributeConverter)`.
The cloud-sdk `EntityTableMetadata.fromEntityClass` resolves key attribute types by **reflection on the backing field**
and does **not** honour `@DynamoDbConvertedBy` on a key → `IllegalArgumentException: Unsupported attribute type for
DynamoDB key: java.time.LocalDate`. **Fix:** `createDate` is now a `String` field (DynamoDB attribute `createDate`,
type `S`) — **byte-identical** to the 1.x physical schema (1.x exposed the key via `getHashKey():String` returning
`createDate.toString()`) and to the prior converter output. `ContainerEventPendingDao.save` (`.toString()`), three test
constructors, and the `ContainerEventPendingDaoIT` assertion were updated; the pending DAO unit + IT remain green.

---

## 8. cloud-sdk library gaps (Goal 5)

| # | Gap | Evidence | Workaround in visibility | Proposed cloud-sdk enhancement |
|---|-----|----------|--------------------------|-------------------------------|
| 1 | **`DynamoDbAdminCommand` ignores `@DynamoDbConvertedBy` on a key** — key attribute types are resolved by field reflection, so a converted key type (e.g. `LocalDate`→`S`) that the enhanced client persists fine cannot be created by the admin command. | `EntityTableMetadata.fromEntityClass` → `Unsupported attribute type for DynamoDB key: java.time.LocalDate` (§7). | Persist the key as the native scalar (`String`) it serializes to. | In `EntityTableMetadata.fromEntityClass`, derive the key `ScalarAttributeType` from the bean's `TableSchema` / the key converter's `attributeValueType()` instead of the raw field type. |
| 2 | **No raw/schemaless `getItem`** in `cloud-sdk-api` `DatabaseRepository<T,K>` (bean-typed only). | `visibility-s3-archiver` `HandlerSupport` drops to a raw `DynamoDbClient` for its schemaless archive read (carried from 2026-06-24 §8). | Direct `DynamoDbClient` in that one lambda, documented + IT-covered. | Add a `RawItemRepository` / `getItem(tableName, key) → Optional<Map<String,CloudAttributeValue>>` (+ factory). |
| 3 | **`AwsStorageConfig.Builder` lacks socket/connection-timeout & max-connections knobs**, and `createS3Client(config)` has no default-credentials fallback (unlike `createDefaultS3Client()`). | 2026-06-24 §6. | Hand-built `ApacheHttpClient` via `httpClient(AwsHttpClientWrapper.ofSync(...))` + explicit `credentialsProvider`. | First-class `socketTimeout` / `connectionTimeout` / `maxConnections` setters + default-credentials fallback. |
| 4 | **`cloud-sdk-aws` pulls a newer `io.searchbox:jest`** that breaks consumers compiled against the older Jest API (`AbstractAction.buildURI()` → `buildURI(ElasticsearchVersion)`). | `visibility-matcher` `TransactionScrollSearch` fails to compile once `cloud-sdk-api`/`-aws` is a *direct* dep. | `visibility-matcher` excludes `io.searchbox:jest` from `cloud-sdk-api` and does not declare `cloud-sdk-aws` directly (keeps it transitive). | Align/relocate the bundled Jest version, or shade `io.searchbox` inside `cloud-sdk-aws`, so a direct dependency does not shift consumers' Jest API. |
| 5 | **Removing the legacy `dynamo-client` destabilises transitive Guava** — `dynamo-client` had been pinning Guava 33.5.0; once removed, `mybatis-guice`/`guice-multibindings` drag the old Guava 18.0 into `visibility-error-email`, and Guice 7 fails at runtime (`ImmutableMap$Builder.buildOrThrow()` `NoSuchMethodError`). | Full `verify` after the removal: `VisibilityErrorEmailModuleTest` → `NoSuchMethodError … buildOrThrow`. | Pin `com.google.guava:guava:33.5.0-jre` directly in `visibility-error-email`. | Have `commons` (or a shared BOM) manage a single Guava version so module-level dependency churn cannot down-mediate it. |

---

## 9. Build & test results

```bash
mvn -f visibility/pom.xml clean verify          # BUILD SUCCESS — all 11 modules
mvn -f visibility/pom.xml -pl visibility-matcher,visibility-pending -am clean verify   # the two previously-failing modules: green
```

- **Unit (surefire): 1009 tests, 0 failures, 0 errors, 6 skipped** (pre-existing lambda `HandlerSupportTest` skips).
- **Integration (failsafe, DynamoDB Local): 40 tests, 0 failures, 0 errors** — including the new
  `VisibilityInboundDynamoDbAdminCommandIT` (7).

---

## 10. Verification & checking commands (with descriptions)

Every command below was run from the repo root `C:\Users\arijit.kundu\projects\mercury-services` (PowerShell).
`-D` properties are quoted because PowerShell otherwise mis-parses `-Dit.test=...`.

### Git — rebase, branch state, single-commit hygiene

```bash
git fetch origin                                                   # refresh remote refs
git log --oneline HEAD..origin/develop -- visibility/             # new visibility commits on develop? -> yes, rebase needed
git branch feature/ION-12316-...-backup-2026-06-25                # safety backup branch before rebasing
git tag    ION-12316-pre-sns-sqs-backup-2026-06-25                # safety backup tag
git rebase origin/develop                                         # replay the single ION-12316 commit onto latest develop
git log --oneline origin/develop..HEAD                            # MUST be exactly 1 outgoing commit
git merge-base HEAD origin/develop  == git rev-parse origin/develop  # confirm commit sits on top of latest develop
git diff --cached --name-only                                     # review staged files before --amend (no docs/prompts/junk)
git check-ignore -v visibility/docs/...md .github/prompts/...md   # confirm docs+prompts are gitignored (never staged)
git add visibility/                                               # stage only visibility src/poms (scoped — excludes root scripts)
git commit --amend -m "ION-12316: ..."                            # fold all work into the single commit
git log -1 --format="%B" | grep ION-12316                         # confirm commit message carries the Jira key
```

### Maven — build, compile, unit + integration tests

```bash
# Baseline after rebase + CI fix — confirm the reactor still compiles before any new work:
mvn -f visibility/pom.xml clean install -DskipTests -T1C

# Surface compile errors fast (main only), then including test sources, across all modules:
mvn -f visibility/pom.xml compile
mvn -f visibility/pom.xml test-compile

# Prove the CI fix — the two previously-failing modules build green:
mvn -f visibility/pom.xml -pl visibility-matcher,visibility-pending -am clean test

# Run all unit tests (surefire) across the reactor:
mvn -f visibility/pom.xml test

# Full unit + integration (failsafe, DynamoDB Local) build — the definitive gate:
mvn -f visibility/pom.xml clean verify

# Run a single integration test via failsafe (PowerShell-quoted -D args).
#   -Dtest=NoUnit + -Dsurefire.failIfNoSpecifiedTests=false makes surefire run nothing;
#   -Dit.test=... selects the failsafe IT:
mvn -f visibility/pom.xml -pl visibility-inbound verify "-Dtest=NoUnit" `
    "-Dsurefire.failIfNoSpecifiedTests=false" "-Dit.test=VisibilityInboundDynamoDbAdminCommandIT"

# Install a single module to .m2 so a downstream -pl build (without -am) resolves the fresh jar:
mvn -f visibility/pom.xml -pl visibility-commons install -DskipTests

# Inspect a transitive conflict (used to diagnose the Jest/io.searchbox clash):
mvn -f visibility/pom.xml -pl visibility-matcher dependency:tree -Dincludes=io.searchbox
```

### Aggregating test totals from the reports (PowerShell)

```powershell
# Sum tests/failures/errors/skipped across surefire (unit) and failsafe (integration) TEST-*.xml:
Get-ChildItem -Recurse -Path visibility -Filter "TEST-*.xml" | ForEach-Object {
  [xml]$x = Get-Content $_.FullName; $ts = $x.testsuite
  # bucket by surefire-reports vs failsafe-reports, accumulate tests/failures/errors/skipped
}
# Result this pass: UNIT 1009 (0/0/6), INTEGRATION 40 (0/0/0)

# Read one suite's result line / stack trace when a run fails:
Get-Content visibility/<module>/target/surefire-reports/<FQCN>.txt
```

### Dependency / API introspection (PowerShell + JDK `javap`)

```powershell
# List classes inside a jar (used to confirm commons 1.0.26 dropped messaging.* and JestModule):
[System.IO.Compression.ZipFile]::OpenRead($jar).Entries | Where-Object FullName -match 'pattern'

# Compare API signatures between the legacy commons and cloud-sdk jars (mirror-class check):
javap -classpath <jar> -p com.inttra.mercury.cloudsdk.notification.workflow.MetaData
javap -classpath <jar> com.inttra.mercury.cloudsdk.messaging.api.MessagingClient
javap -p -c -classpath <jar> com.inttra.mercury.cloudsdk.database.util.EntityTableMetadata   # how the admin command resolves key types

# Confirm an installed reactor jar carries the expected change:
javap -classpath %USERPROFILE%\.m2\...\visibility-commons-1.0.jar `
      com.inttra.mercury.visibility.common.model.containerEvent.ContainerEventPending
```

### Source / config inspection (ripgrep-style git grep)

```bash
git grep -n "import com.inttra.mercury.messaging\."            # inventory legacy messaging usage to migrate
git grep -rln "dynamoDbTableCreationCommandConfig"             # find the obsolete YAML block (20 files) + Java refs
git grep -rln "2.1.8.M\|3.0.0.M" -- "visibility/**/pom.xml"    # locate the stale booking-model pin (CI failure)
git grep -n "com.inttra.mercury.dynamo\b\|dynamo-client"      # confirm dynamo-client fully removed
```

### Dropwizard INT config sanity (offline)

```bash
# After removing the dynamoDbTableCreationCommandConfig YAML block, confirm each app still
# deserializes/validates its INT config (no unknown-property failure):
java -jar visibility/<module>/target/<artifact>.jar check visibility/<module>/conf/int/config.yaml   # "Configuration is OK"
```

---

## 11. References

- ION-12316
- Prior docs: `2026-06-24-visibility-refactor-sns-sqs-coverage.md`, `2026-06-23-visibility-rebase-refactor.md`
- Reference module: `booking` (`BookingMessagingModule`, `SQSClient`/`SNSClient`, `BookingDynamoDbAdminCommand(IT)`,
  `cloudsdk.aws.module.JestModule`) — AWS SDK 2.x upgrade complete and in production
- cloud-sdk `1.0.26-SNAPSHOT`: `MessagingClient`/`QueueMessage`/`MessagingClientFactory`,
  `NotificationService`/`NotificationClientFactory`, `DynamoDbAdminCommand`, `EntityTableMetadata`

---

## 12. Push to remote (2026-06-27)

After the rebase (§2) the branch reported `ahead 18, behind 1` against the **stale** remote feature tip, which was
initially mistaken for "many outgoing commits". The count was disambiguated against two baselines:

- vs `origin/develop` (`f992aaa631`): **exactly 1** outgoing commit — the ION-12316 work commit `0f5fa309fc`.
- vs the stale remote feature tip (`dd46b95a34`): **18** — but 17 of those are upstream `develop` history
  (`ION-16065`, `ION-16054`, PRs #1067–#1070) absorbed by the rebase onto the newer develop; only 1 is our work.

The "18 ahead / 1 behind" is the expected post-rebase shape: our single feature commit now sits on the *new* develop
tip, while the old remote branch predated that develop. The behind-1 is the pre-rebase commit being superseded.

**Pre-push verification (all green):**
- `git log --oneline origin/develop..HEAD` → exactly 1 commit (`0f5fa309fc`).
- Commit parent == `origin/develop` tip (`f992aaa631`) → feature commit sits directly on latest develop.
- Working tree clean — no uncommitted/staged `.java` changes; nothing in the index.
- All 22 SQS/SNS + DynamoDB converter sources/tests present and intact — commit-blob vs on-disk line counts
  match exactly, none empty/corrupt. (They appeared "missing" in the VS Code Source Control panel only because
  they were already committed — that panel lists *uncommitted* changes.)
- No real merge-conflict markers in the diff (only `// ====` comment banners).
- Force-with-lease lease target still `dd46b95a34` → safe to force-update.

**Command:**

```bash
git push --force-with-lease origin feature/ION-12316-visibiilty-aws-upgrade-copilot
# dd46b95a34...0f5fa309fc  feature/ION-12316-... -> feature/ION-12316-...  (forced update)
```

**Post-push:** local and remote both at `0f5fa309fc`; branch in sync. PR
[#1066](https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/1066) targets `develop`.
