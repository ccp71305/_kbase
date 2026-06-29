# Visibility — Rebase onto Develop + AWS 2.x Upgrade Refactor

**Jira**: ION-12316
**Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot`
**Date**: 2026-06-23
**Model**: Claude Opus 4.8 (1M context)
**Backup**: branch `feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23`, tag `ION-12316-pre-rebase-backup-2026-06-23` (original tip `6e6b2042e3`)

---

## 1. Summary

This change squashes the visibility AWS SDK 2.x (cloud-sdk) feature work into a single commit, rebases it onto the
latest `develop`, and applies the agreed fixes from the 2026-06-01 design/impl review — all while preserving full
backward compatibility with existing 1.x visibility DynamoDB data. It also adds an exhaustive DynamoDB-Local
integration test that pins the backward-compat contract the mocked unit tests could not see.

Result: **one outgoing commit** containing the cloud-sdk migration + review fixes, **not pushed**. Full
`mvn verify -f visibility/pom.xml` is green (190 unit + 10 integration tests, all 12 modules `BUILD SUCCESS`).

---

## 2. Git steps & commands

```bash
# Step 1 — Safety backup (local only, never pushed)
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23
git tag    ION-12316-pre-rebase-backup-2026-06-23
# restore if ever needed:
#   git reset --hard feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23

# Step 2 — Squash 6 outgoing commits -> 1 (soft reset to merge-base, then single commit)
git reset --soft 46e40a3ef2ee3d685c66ecb53a95addaed954d8b
git commit -m "ION-12316: Visibility (Track and Trace) AWS SDK 2.x cloud-sdk upgrade"   # 78b00daa39

# Step 3 — Update develop & analyze conflict risk
git checkout develop && git pull origin develop
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot
MERGE_BASE=$(git merge-base develop HEAD)        # 46e40a3ef2
git log --oneline HEAD..develop -- visibility/   # ION-16054, ION-15892
# overlapping changed files (potential conflicts): only visibility/pom.xml & visibility-commons/pom.xml

# Step 4 — Rebase onto develop
git rebase develop                               # -> single commit 24cb5ee56f
# verify:
git log --oneline develop..HEAD
mvn test-compile -pl visibility -am -q           # post-rebase health check: BUILD SUCCESS
```

### Conflict log

| File | develop change (ION-15892 security) | feature change (AWS upgrade) | Resolution |
|------|--------------------------------------|------------------------------|------------|
| `visibility/pom.xml` | bumped `mercury.commons.version` & `mercury.dynamodbclient.version` to `1.R.01.023` | kept `.021` + added `mercury.cloudsdk.version=1.0.26-SNAPSHOT` | **Combined**: keep develop's newer `1.R.01.023` **and** re-add the `cloudsdk` property |
| `visibility/visibility-commons/pom.xml` | (security bump) | cloud-sdk deps | auto-merged cleanly |

Develop's newly merged `AbstractMatcher.java` / `MatchingProcessorTest.java` (ION-15892) compiled cleanly against the
upgrade (post-rebase `mvn test-compile` BUILD SUCCESS), so no follow-up import fixes were needed.

---

## 3. Review comments addressed (2026-06-01 design/impl review)

Source: `visibility/docs/2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md`.
Backward-compat invariant for every change: reads tolerate legacy data; writes reproduce the legacy on-disk format.

### HIGH-1 / MEDIUM-5 — `MetaDataAttributeConverter` (S, canonical serializer)
- Rewrote to **write a DynamoDB String (S)** via the canonical `MetaData.toJsonString()` — identical to the AWS SDK v1
  `MetaDataConverter` (`DynamoDBTypeConverter<String, MetaData>`); `attributeValueType()` is now `S` (was `M`).
- Reads are lenient: `S` → `MetaData.parseJson(...)`; a stray `M` (only from transient intermediate code, never in
  prod) is re-serialized to JSON and parsed through the same canonical path.
- Deleted the bespoke `ObjectMapper`, the `MetaDataDynamoDbMixIn`, and the now-unused `FlexibleLocalDateTimeDeserializer`.
- This restores both 1.x backward compatibility and the `visibility-s3-archiver` contract (which reads `metaData` as a
  JSON String).

### MEDIUM-4 — JSON date encoding in submission/enriched blobs
- Reverted `ContainerEventSubmissionAttributeConverter` and `ContainerEventEnrichedPropertiesAttributeConverter` to a
  **bare `new ObjectMapper()`** (no `JavaTimeModule`, default `WRITE_DATES_AS_TIMESTAMPS=true`) — byte-identical to the
  legacy v1 `ContainerEventSubmissionConverter`/`...EnrichedPropertiesConverter` encoding. `FAIL_ON_UNKNOWN_PROPERTIES`
  is kept `false` for tolerant reads (this does not affect the written format).

### MEDIUM-6 — `ContainerEventDao.findById` retry scope
- Narrowed the retry from `catch (RuntimeException)` to **only transient/throttling faults**, using the cloud-sdk's
  canonical `DynamoDbErrorHandler.isRetryableError(e)` (ProvisionedThroughputExceeded / RequestLimitExceeded /
  InternalServerError / TransactionConflict). Non-transient errors propagate immediately; restored the interrupt flag.

### HIGH-2 — `cloudSdkDynamoDbConfig` present in every environment
- Added a `cloudSdkDynamoDbConfig:` block to **all 36** visibility `config.yaml` files (conf/ + the six app modules,
  incl. wm-inbound-processor's three processors), so the cloud-sdk repositories can boot. The legacy `dynamoDbConfig:`
  block is retained because it is still consumed by the v1 table-creation command and ES wiring (documented dual-config).

### HIGH-3 — Table-name prefix aligned with booking/network
- The cloud-sdk derives table names as `DynamoDbClientConfig.getTablePrefix() + @Table.name`, and
  `getTablePrefix() == environment + "_"` (verified via bytecode; booking uses `environment: inttra_int_booking`).
- Each `cloudSdkDynamoDbConfig.environment` is set to that file's **own legacy `dynamoDbConfig.environment`**
  (`inttra_int`, `inttra2_qa`, `inttra2_test`/`inttra2_cv`, `inttra2_prod`), so the resolved physical names are
  identical to the v1 names — e.g. `inttra_int_container_events` and `inttra_int_booking_BookingDetail`
  (`booking_BookingDetail` `@Table` + `inttra_int_` prefix). This is confirmed end-to-end by the integration test.

### LOW-9 — committed `booking-3.0.0.M.jar` — accepted as-is
- Left in place per direction; no change.

### LOW-7 / LOW-8 — tracked as follow-ups (no backward-compat regression).

---

## 4. Tests

### New
- `MetaDataAttributeConverterTest` (5): S-write equals `toJsonString()`, S round-trip, legacy-S read, lenient-M read, nulls.
- `ContainerEventDaoTest` (+2): `findById` does **not** retry non-transient errors (1 call); retries transient
  throttling (3 calls).
- `ContainerEventDaoIT` (10, `@Tag("integration")`, DynamoDB Local via `BaseDynamoDbIT`, mirrors booking `*DaoIT`):
  - **StorageFormat**: `metaData` stored as `S == toJsonString()`; submission/enriched stored as `S` (not `M`);
    submission JSON byte-identical to legacy bare-`ObjectMapper`; `expiresOn` is `N`, ISO date fields are `S`.
  - **LegacyReads**: reads legacy `S` metaData, legacy `M` metaData, legacy `M` submission.
  - **RoundTrip**: save→read equality; `findById`/`getSingleById`.
  - **GsiQueries**: `queryIndex` by the `bookingNumber` GSI.

### IT infrastructure (visibility-commons `pom.xml`)
- `maven-failsafe-plugin` (`*IT.java`, group `integration`, bound to `integration-test`/`verify`) +
  `maven-dependency-plugin` `copy-native-libs` (sqlite4java) + `surefire` `excludedGroups=integration`.
- Dependency alignment **for the test classpath/DynamoDB Local only**:
  - `log4j-api` pinned `2.23.1` (used by main) + `log4j-core` `2.23.1` (test) — DynamoDB Local needs
    `LoaderUtil.getClassLoaders()`.
  - `aws-java-sdk-dynamodb` + `aws-java-sdk-core` pinned `1.12.721` (DynamoDB Local 2.5.2 needs `OnDemandThroughput`;
    1.12.721 still carries the v1 `datamodeling` API used by the remaining legacy converters).

### Result
`mvn verify -f visibility/pom.xml` → **BUILD SUCCESS**, all 12 modules, 190 unit + 10 integration tests, 0 failures.

---

## 5. INT startup

The migrated apps resolve their DynamoDB table prefix from `cloudSdkDynamoDbConfig.environment` (now present in every
`config.yaml`), eliminating the HIGH-2 `IllegalStateException` at boot, and the table names match the legacy physical
names (HIGH-3), avoiding `ResourceNotFound`. Full `server` startup against INT requires live AWS (DynamoDB/SQS/ES) and
is validated in the INT environment; config deserialization of the new block is exercised by the build.

---

## 6. `commons` 1.0.26-SNAPSHOT (DW 5.x) — analysis & follow-up (NOT in this commit)

A unification onto the `1.0.26-SNAPSHOT` line (commons + cloud-sdk + dynamo-integration-test, like booking) was
investigated. It is **deferred** because it is a larger, separate migration than a version bump:

- `commons` 1.0.26 (DW 5.x / Jetty-EE10 / jakarta) **removed the entire `com.inttra.mercury.messaging.*` package**
  (MetaData, Event, EventLogger/EventPublisher/EventGenerator/SNSEventPublisher, ErrorHelper, Annotation(s),
  RandomGenerator, `SQSClient`, `SNSClient`). 65 visibility files use it.
- Those classes were **refactored into the cloud-sdk**:
  - `messaging.model.MetaData/Event` → `cloudsdk.notification.workflow.*` (MetaData keeps `Builder(7-arg)`,
    `Projection`, `parseJson`/`toJsonString`)
  - `messaging.logging.EventLogger/EventPublisher/EventGenerator` → `cloudsdk.notification.workflow.*`;
    `SNSEventPublisher` → `cloudsdk.notification.workflow.SnsEventPublisher`
  - `messaging.logging.ErrorHelper`, `messaging.model.Annotation(s)` → `cloudsdk.notification.annotation.*`
  - `messaging.util.RandomGenerator` → `cloudsdk.notification.util.RandomGenerator`
  - `messaging.sqs.SQSClient` → `cloudsdk.messaging.api.MessagingClient<T>` **(new API)**
  - `messaging.sns.SNSClient` → `cloudsdk.notification.api.NotificationService` / `notification.impl.SnsService` **(new API)**

### Why it is a dedicated effort
The original upgrade migrated SQS to the cloud-sdk `MessagingClient` **only in the two lambda modules**
`visibility-outbound-poller` and `visibility-pending-start` (via `MessagingClientFactory`). The **core SQS/SNS
backbone — 12 main classes** (`visibility-commons` `SqsMessageHandler` + `VisibilityApplicationInjector` SNS; `-inbound`
`CargoVisibilityService`/`InboundEdiProcessor`/`ReprocessService`; `-matcher` `MatchingProcessor`/`AbstractMatcher`;
`-outbound` `Outbound*Processor`/`OutboundGenerator`; `-pending` `PendingSqsProcessor`; `-itv-gps` `GPSEventProcessor`;
`-wm` `WMEventProcessor`) plus ~30 test files — **still uses the legacy `SQSClient`/`SNSClient`** and was never migrated.
(There is no `VisibilityMessagingModule` class; it is named only in the planning docs.)

### Recommended completion plan (follow-up)
1. Add a `mercury-services-commons` version property (`1.0.26-SNAPSHOT`) and a `dependencyManagement` block pinning
   `commons`, `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test` to it (like booking); declare
   `cloud-sdk-api`/`-aws` as direct top-level deps in every module that uses them.
2. Mechanically remap the 1:1 classes (MetaData/Event/EventLogger/EventPublisher/EventGenerator/Annotation(s)/
   ErrorHelper/RandomGenerator) to `cloudsdk.notification.*`.
3. Migrate the SQS consumers (`SqsMessageHandler` + the 12 classes) from `SQSClient` to `MessagingClient<T>` and the SNS
   publisher from `SNSClient` to `NotificationService`/`SnsEventPublisher`, replacing `SQSModule`/`SNSModule` Guice
   bindings with `MessagingClientFactory`/`NotificationClientFactory`, and add the messaging/notification config blocks
   to each `config.yaml`.
4. Remove the legacy v1 dynamo converters (`*Converter` using `com.amazonaws…datamodeling`) and the `dynamo-client`
   dependency; keep **only** the v1 AWS deps required by DynamoDB Local (test) and the Lambda runtime event models
   (`com.amazonaws.services.lambda.runtime.events.*`, `OperationType`, `S3EventNotification`).
5. Update all affected unit tests (mock `MessagingClient`/`NotificationService`) and the injector tests; re-verify.

---

## 7. Git utilities

Useful commands used while landing this branch. **`docs/` is gitignored (`.gitignore: **/docs/`)**, so this file is
a local-only artifact and is never committed.

### 7.1 First push (set upstream) and the single-commit workflow

Nothing was on the remote until the first push. The first push only needs `-u` (no force, since the remote branch
does not exist yet); every subsequent amend/rebase is published with `--force-with-lease` to keep the remote at a
single commit.

```bash
# first push — creates the remote branch and sets upstream tracking
git push -u origin feature/ION-12316-visibiilty-aws-upgrade-copilot

# ongoing: keep exactly one outgoing commit, then publish
git commit --amend --no-edit                 # fold new local changes into the one commit
git rebase develop                           # re-base on develop when needed (still one commit)
git push --force-with-lease                  # safe force: refuses if someone else pushed meanwhile

# verify a single outgoing commit (message must contain ION-12316)
git log --oneline develop..HEAD
git log -1 --format="%s"
```

> Use `--force-with-lease`, **never** `--force`: it aborts the push if the remote moved since your last fetch,
> protecting a teammate's work.

### 7.2 Removing accidentally-committed `docs/` files (keep them on disk)

The 9 `visibility/docs/*.md` files were already **tracked** from earlier feature commits, so the squash carried them in
and the first push published them. (The `**/docs/` ignore rule only affects *untracked* files — it does not untrack
already-tracked files.) To remove them from the commit + remote while keeping the files locally:

```bash
# untrack everything under visibility/docs (files stay on disk; ignore rule keeps them out going forward)
git rm -r --cached visibility/docs

# fold the removal into the single commit (keep the ION-12316 message)
git commit --amend --no-edit                 # 9a678c919c -> 35c1414cdd

# publish — updates the remote branch AND the open PR automatically
git push --force-with-lease

# verify the docs are gone from the tracked tree but still present locally
git ls-tree -r --name-only origin/feature/ION-12316-visibiilty-aws-upgrade-copilot -- visibility/docs   # (empty)
ls visibility/docs/*.md                                                                                  # files still here
```

**PR note:** a force-push does **not** require deleting/recreating the pull request — the existing PR (here **#1065**)
re-points at the amended commit automatically. Only delete a PR if you intentionally want a fresh one.

### 7.3 Safety backup before history rewrites

```bash
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23
git tag    ION-12316-pre-rebase-backup-2026-06-23
# restore if a squash/rebase goes wrong:
git reset --hard feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23
```
