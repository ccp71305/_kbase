# ION-12316 — Visibility AWS SDK 2.x (cloud-sdk): rebase onto latest develop, resolve conflicts, fix parallel-processing test

**Branch:** `feature/ION-12316-visibiilty-aws-upgrade-copilot`
**Model:** Claude Opus 4.8 (1M context)
**Date:** 2026-07-10
**Outcome:** single outgoing commit `9a04010f1d` rebased onto the latest `develop` (`8621bbe331`); all 12 visibility
modules build; **1069 unit + 49 integration = 1118 tests, 0 failures, 0 errors, 6 skipped**. Not pushed.

Reference doc: [`2026-06-30-rebase-resolve-conflict.md`](./2026-06-30-rebase-resolve-conflict.md).

---

## 1. Summary

Three goals were accomplished on the `visibility` module:

1. **Rebase onto the latest `develop`** — the feature branch (one AWS-SDK-2.x upgrade commit) was rebased from
   its old base `a1f243c584` onto the current `develop` tip `8621bbe331`.
2. **Resolve the resulting merge conflicts** — develop's latest functional changes (ION-16157 "Table Renaming
   inconsistencies" / DynamoDB prefix + pilot companies, and ION-16181 vulnerability suppression) took priority
   (incoming-wins), and the AWS-SDK-upgrade changes were re-applied on top so the upgrade conforms to develop.
3. **Fix the parallel-processing test failure** reported by Jenkins
   (`CargoVisibilityServiceParallelProcessingTest.shouldCompleteRunningTasksBeforeShutdown:616`).

End state: exactly **one** outgoing commit (`git log --oneline develop..HEAD` → one line), message contains
`ION-12316`, sitting on top of the latest develop. Not pushed.

---

## 2. Rebase

New base develop tip: `8621bbe3314654212ec52fe24f77c95e799b5def`.
Old base (pre-rebase merge-base): `a1f243c584ea614d20a9878fb5263c99ce0c3ab6`.

Backups taken before the rebase:
- branch `feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-20260710`
- tag `ION-12316-pre-refactor-backup-20260710`

Incoming develop commits that touched `visibility/` (the functional baseline that won conflicts):

| SHA | Ticket | What it changed |
|-----|--------|-----------------|
| `6823edd60d` / `b8fd7460bd` / `ec479f5066` | ION-16157 | Table-renaming inconsistencies: DynamoDB prefix naming, pilot-company config; **wm `CargoVisibilitySubscription` schema change** — renamed `bookingNumber`→`carrierBookingNumber`, added `billOfLadingNumber`, `clientType`, `serviceType`; replaced the single `bookingNumber-index` GSI with the two composite GSIs `bookingNumber-carrierScac-index` and `billOfLading-carrierScac-index` (carrierScac as range key); fixed `Channel.WATERMILL` description typo `WATRERMILL`→`WATERMILL`; `cargo-visibility-subscription-processor.yaml` env `inttra2_cv`→`inttra2_test`. |
| `46245ba256` | ION-16181 | Suppressing unexploitable vulnerability (`suppressions.xml` across modules). |

### Conflicts resolved (incoming develop wins, upgrade re-applied on top)

| # | File | Resolution |
|---|------|-----------|
| 1 | `visibility-wm-inbound-processor/conf/cvt/cargo-visibility-subscription-processor.yaml` | Kept develop's functional `dynamoDbConfig.environment: inttra2_test` (ION-16157) **and** re-applied the upgrade's `sseEnabled: false` cloud-sdk config key. |
| 2 | `visibility-wm-inbound-processor/.../cargo/visibility/model/CargoVisibilitySubscription.java` | develop rewrote the **SDK v1** model (new composite GSIs, `carrierBookingNumber`/`billOfLadingNumber`, `clientType`, `serviceType`, `carrierScac` range key); the upgrade had migrated the **old** schema to SDK v2 Enhanced Client. Reconciled by re-applying the SDK v2 migration **onto develop's new schema** — the result is byte/shape-identical to the already-migrated `visibility-inbound` SDK v2 model (`@DynamoDbBean`, `@DynamoDbSecondaryPartitionKey` on `carrierBookingNumber`/`billOfLadingNumber`/`subscriptionReference`, `@DynamoDbSecondarySortKey` on `carrierScac` for both composite indexes, legacy `Date` converters preserved for wire compatibility). No functional field or index from develop was dropped. |
| 3 | `visibility-wm-inbound-processor/.../wm/dao/CargoVisibilitySubscriptionDaoTest.java` | Kept develop's functional rename `getBookingNumber()`→`getCarrierBookingNumber()` **and** dropped the SDK v1 `verify(dynamoDBMapper).load(...)` line the upgrade had already replaced with the `DatabaseRepository` (`repository.findById`) path. |

The wm DAO main source only queries the still-present `SUBSCRIPTION_REFERENCE_INDEX` GSI (plus `findById`), so
develop's booking/BoL GSI rename required no DAO query changes.

---

## 3. Post-rebase compile fixes (upgrade re-applied on top of develop's schema)

After the rebase, three upgrade-only **test** files still referenced the pre-ION-16157 field name
`bookingNumber` on the SDK v2 `CargoVisibilitySubscription` (these test files exist only on the upgrade branch, so
develop's rename never reached them). Renamed to the new schema:

- `visibility-wm-inbound-processor/.../wm/dao/CargoVisibilitySubscriptionDaoIT.java` — `sample(...)` builder
  `.bookingNumber(...)`→`.carrierBookingNumber(...)`; assertion `getBookingNumber()`→`getCarrierBookingNumber()`.
- `visibility-wm-inbound-processor/.../wm/dao/CargoVisibilitySubscriptionDaoTest.java` — builder
  `.bookingNumber("SAVE-BOOK")`→`.carrierBookingNumber("SAVE-BOOK")`.

No production code changed here; only test data/assertions were aligned to develop's schema.

---

## 4. Parallel-processing test fix

**Failure (Jenkins):**

```
CargoVisibilityServiceParallelProcessingTest.shouldCompleteRunningTasksBeforeShutdown:616
Expecting actual: 0 to be greater than: 0
Tests run: 491, Failures: 1, Errors: 0, Skipped: 2
```

**Root cause — a test-side race, not a product bug.** The test stubs
`s3WorkspaceService.putObject(anyString(), contains("/"), anyString())` with a `doAnswer` that (a) counts down
`taskStarted`, (b) blocks on `releaseTask`, then (c) does `completedTasks.incrementAndGet()`. The very first
`putObject` this intercepts is the *root* upload in `CargoVisibilityService.processJsonSubmission` (line 236),
which runs on the **spawned thread**, not on the internal executor. The test released `releaseTask` and then
immediately asserted `completedTasks > 0` on the **main** thread — with no happens-before edge guaranteeing the
spawned thread had executed the `incrementAndGet()` yet. On the slower Jenkins host the main thread won the race
and observed `0`. (`service.shutdown()`'s `awaitTermination` only bounds *executor* tasks, so it does not
synchronize the spawned-thread increment.)

**Fix (deterministic, no weakening).** Added a `CountDownLatch taskCompleted` that the `doAnswer` counts down
**after** `incrementAndGet()`, and the test now `await`s it (bounded 5s, asserted) before checking
`completedTasks`. The test still verifies its original intent — a genuinely in-flight task runs to completion
around shutdown — but the completion is now observed via a happens-before latch instead of a data race. File:
`visibility-inbound/.../service/CargoVisibilityServiceParallelProcessingTest.java`.

Result: `CargoVisibilityServiceParallelProcessingTest` → 21 tests, 0 failures;
`shouldCompleteRunningTasksBeforeShutdown` passes.

---

## 5. Tests & coverage

Full reactor `mvn -f visibility/pom.xml clean verify` → **BUILD SUCCESS** (all 12 modules), unit + DynamoDB Local
integration tests + JaCoCo. No coverage gate was tripped (build is green).

**Test-count summary (JUnit 5 only; no TestNG in visibility):**

| Runner / phase | Report dir | Tests | Failures | Errors | Skipped | Report files |
|----------------|-----------|-------|----------|--------|---------|--------------|
| surefire (unit) | `*/target/surefire-reports` | 1069 | 0 | 0 | 6 | 185 |
| failsafe (integration) | `*/target/failsafe-reports` | 49 | 0 | 0 | 0 | 27 |
| **Total** | | **1118** | **0** | **0** | **6** | |

Passing test commands (each with what it verified):

```bash
# Full certifying run — unit + DynamoDB Local integration + JaCoCo across all 12 visibility modules.
mvn -f visibility/pom.xml clean verify        # BUILD SUCCESS; 1069 unit + 49 IT, 0 failures

# Install just the commons artifact into ~/.m2 (used only while iterating on -rf resumes; superseded by the
# full reactor run above, which resolves all inter-module deps from the reactor).
mvn -f visibility/pom.xml install -pl visibility-commons -DskipTests -Djacoco.skip=true
```

JaCoCo per-module reports: `visibility/<module>/target/site/jacoco/index.html`.

---

## 6. cloud-sdk gaps

**None found** for this task. It was a rebase + conflict-resolution + test-fix; no new cloud-sdk capability was
required beyond what the already-migrated modules use. The `LegacyDynamoDbDateAttributeConverter` gap already
documented in `2026-06-30-rebase-resolve-conflict.md` (SDK 2.x Enhanced Client has no built-in `java.util.Date`
converter) still applies and is worked around locally, unchanged.

---

## 7. Command log

Every command run for this task, with why it was run and what it revealed.

```bash
# --- Orient / branch resolution ---
git fetch origin                                              # refresh remotes
git checkout develop && git pull --ff-only origin develop     # latest develop = functional baseline; already up to date (8621bbe331)
git rev-parse --verify feature/ION-12316-visibiilty-aws-upgrade-copilot   # branch exists locally at 9a795464c8
git ls-remote --heads origin feature/ION-12316-visibiilty-aws-upgrade-copilot  # also on origin at 9a795464c8
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot # switch to feature branch
git log --oneline develop..HEAD                               # one outgoing commit (9a795464c8)
git rev-parse HEAD                                            # tip 9a795464c8
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-20260710  # safety backup branch
git tag    ION-12316-pre-refactor-backup-20260710             # safety backup tag
git merge-base HEAD origin/develop                            # old base a1f243c584
git log --oneline HEAD..origin/develop -- visibility/         # incoming visibility commits: ION-16157 x3, ION-16181

# --- Inspect incoming functional changes before rebasing ---
git diff --stat a1f243c584 origin/develop -- visibility/                          # 15 files changed on develop
git diff a1f243c584 origin/develop -- <CargoVisibilitySubscription.java|Channel.java|*.yaml>  # the ION-16157 schema/enum/config changes
git diff a1f243c584 origin/develop -- <CargoVisibilitySubscriptionDaoTest.java|...ProcessorTest.java>  # test renames bookingNumber->carrierBookingNumber
git grep -n "JsonIgnoreProperties" origin/develop -- <wm|inbound>/CargoVisibilitySubscription.java  # confirm annotation intent

# --- Rebase + resolve ---
git rebase origin/develop                                     # 3 conflicts: yaml, wm model, wm dao test
git diff --name-only --diff-filter=U                          # list unmerged files
# (yaml) kept inttra2_test + sseEnabled:false
# (model) replaced with the SDK v2 form conforming to develop's schema (copied from the migrated visibility-inbound model)
# (dao test) kept getCarrierBookingNumber(), dropped SDK v1 dynamoDBMapper.load verify
git grep -c -E "^(<<<<<<<|=======|>>>>>>>)" -- <the 3 files>  # confirm markers cleared
git grep -n "dynamoDBMapper" -- wm/.../CargoVisibilitySubscriptionDaoTest.java   # confirm no stale SDK v1 refs
git add <the 3 resolved files>
GIT_EDITOR=true git rebase --continue                         # rebased -> 40b68d2ee8 on 8621bbe331
git log --oneline develop..HEAD                               # exactly one outgoing commit
git merge-base HEAD develop                                   # new base 8621bbe331

# --- Post-rebase stale-reference scan + fixes ---
grep -n "\.bookingNumber(|getBookingNumber|setBookingNumber|BOOKING_NUMBER_INDEX" visibility/visibility-wm-inbound-processor  # found 3 upgrade-only test refs; fixed to carrierBookingNumber
grep -n "bookingNumber|BOOKING_NUMBER" visibility-wm-inbound-processor/.../wm/dao/CargoVisibilitySubscriptionDao.java  # DAO only uses SUBSCRIPTION_REFERENCE_INDEX -> no change

# --- Build / verify ---
mvn -f visibility/pom.xml clean verify                        # first run: FAILED wm testCompile on stale bookingNumber refs -> fixed
mvn -f visibility/pom.xml clean verify                        # second run: BUILD SUCCESS, 1069 unit + 49 IT, 0 failures
# (test-count tally via PowerShell over */target/{surefire,failsafe}-reports/TEST-*.xml)
```

Environment note: an initial `clean` failed because the VS Code Java language server held a lock on
`visibility-commons/target`; the language-server JVM was stopped so `clean` could delete the directory.

---

## 8. Build / packaging results

`mvn -f visibility/pom.xml clean verify` — Reactor Summary: **BUILD SUCCESS**, all 12 modules
(`visibility-commons`, `visibility-inbound`, `visibility-wm-inbound-processor`, `visibility-matcher`,
`visibility-outbound`, `visibility-pending`, `visibility-s3-archiver`, `visibility-pending-start`,
`visibility-error-email`, `visibility-outbound-poller`, `visibility-itv-gps-processor`) including shaded-JAR
packaging. Total time ~07:53 min.

---

## 9. References

- Jira: **ION-12316** (visibility AWS SDK 2.x upgrade).
- Incoming develop tickets preserved: **ION-16157** (table renaming / DynamoDB prefix / pilot companies),
  **ION-16181** (vulnerability suppression).
- Reference modules (cloud-sdk templates): booking, network (SQS/SNS), booking, auth (SES), booking (S3),
  booking/network/registration/webbl/booking-bridge (DynamoDB).
- Prior session doc: [`2026-06-30-rebase-resolve-conflict.md`](./2026-06-30-rebase-resolve-conflict.md).
