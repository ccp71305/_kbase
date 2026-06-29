---
name: 2026-06-24-visibility-refactor-sns-sqs-config-coverage
description: Continue the visibility AWS-SDK-2.x (cloud-sdk) refactor on ION-12316. Re-align the DynamoDB config to reuse the existing dynamoDbConfig (drop the divergent cloudSdkDynamoDbConfig) following booking/network, complete the SQS + SNS cloud-sdk migration using booking as the template, harden DynamoDB DAO/converter backward compatibility with exhaustive CRUD/GSI/boundary + round-trip integration tests, review S3 client + lambda AWS-client injection, document the s3-archiver direct-DynamoDbClient gap, ensure logging, raise Sonar new-code coverage for the listed classes, package every visibility sub-module and verify Dropwizard INT startup. Leave exactly one unpushed outgoing commit referencing ION-12316.
argument-hint: "none"
agent: agent
model: Claude Opus 4.8 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# Visibility — SNS/SQS Completion + Config Re-alignment + Coverage Hardening — ION-12316

> **Continuation of** `.github/prompts/refactor/2026-06-23-visibility-rebase-refactor-prompt.md`.
> **Prior write-up (read first):** `visibility/docs/2026-06-23-visibility-rebase-refactor.md` — especially
> **§6 (`commons` 1.0.26-SNAPSHOT — SQS/SNS completion plan)** and **§3 (review comments addressed)**.

## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the existing feature branch `feature/ION-12316-visibiilty-aws-upgrade-copilot`.
2. **DO NOT PUSH** — Never `git push` / `git push --force` / `--force-with-lease`. The user reviews locally and pushes manually.
3. **SINGLE OUTGOING COMMIT** — End state must be exactly **one** outgoing commit (`git log --oneline develop..HEAD` returns one line). Fold all changes into it via `git commit --amend`.
4. **COMMIT MESSAGE** — The final commit message MUST contain the text `ION-12316`.
5. **LATEST DEVELOP IS THE FUNCTIONAL BASELINE** — If a fresh rebase is needed, keep develop's latest functional logic and re-apply the AWS-upgrade changes on top. Never drop a functional change to keep an upgrade change.
6. **BACKWARD COMPATIBILITY IS PARAMOUNT** — All DynamoDB encoding/decoding, JSON blob serialization, table-name derivation, SQS/SNS message payloads, and S3 archive formats must remain wire-compatible with existing **1.x visibility** data and consumers. Reads tolerate legacy data; writes reproduce the legacy on-disk/on-wire representation. Every change must be proven by a test.
7. **ALIGN WITH booking / network** — These modules are the **reference implementations** for cloud-sdk config wiring, SQS (`MessagingClient`), SNS (`NotificationService` / `SnsEventPublisher`), Guice factories, S3 client creation, lambda client injection, and integration-test patterns. Prefer their proven approach over any divergent one already in visibility.
8. **ALL TESTS MUST PASS** — Unit + integration (including DynamoDB Local integration tests). Everything must compile and have coverage. Do not weaken or `@Disabled` a test to go green; root-cause and fix.
9. **STARTUP CHECK** — Every affected visibility sub-module must start cleanly with its **INT** `config.yaml`.
10. **MODEL** — Use Claude Opus 4.8 with the 1M context token window. Log this in session context (`model_info`).

---

## Session Context Protocol — FOLLOW STRICTLY

Reference: `.github/prompts/_base-session-protocol.md`.

Before starting ANY work:
1. `session_list` — look for the existing session for `ION-12316` / `visibility` / `visibility-aws-upgrade` (created 2026-06-23).
2. If found → `session_get` and **resume**; cross-link the prior session.
3. If none → `session_create`:
   - name: `visibility-sns-sqs-config-coverage-2026-06-24`
   - project: `mercury-services`
   - tags: `["visibility", "ION-12316", "aws-sdk-upgrade", "sns", "sqs", "dynamodb", "test-coverage", "sonar", "backward-compat", "in-progress"]`

**DURING** work — `session_add_context` after every significant action:
- Config re-alignment decision (drop `cloudSdkDynamoDbConfig`, reuse `dynamoDbConfig`) → `decision`
- Each SQS/SNS class migrated → `code_change`
- DAO / converter compatibility findings → `finding`
- S3-client + lambda-injection + s3-archiver gap analysis → `finding` / `decision`
- Tests added + coverage results → `test_result`
- Compilation / `mvn verify` / packaging / INT startup results → `test_result`
- Blockers (failing IT, missing cloud-sdk API, etc.) → `blocker`
- Model used → `model_info`

If context exceeds **85%**: persist a full summary via `session_add_context` (`progress`), write all findings into the output doc immediately, note where you left off, then continue/hand off per the base protocol.

Use the MCP context server for **Jira** (ION-12316) and **Confluence** access, and for git operations if helpful.

---

## Goal Overview

Build on the single ION-12316 commit to:
- re-align the DynamoDB configuration to the **booking/network** pattern (reuse the existing `dynamoDbConfig`, remove the divergent `cloudSdkDynamoDbConfig`),
- **complete** the SQS and SNS cloud-sdk migration across the whole visibility backbone (not just the two lambda modules),
- harden DynamoDB DAO + converter **backward compatibility** with exhaustive CRUD / GSI / boundary unit tests and round-trip integration tests,
- review and document the S3 client settings, could the specific 1.x settings be leveraged ?, document the lambda AWS-client injection, and the s3-archiver direct-`DynamoDbClient` resolution. Why are we not using the cloud-sdk-api ? is this a gap in the cloud-sdk library ?
- ensure sufficient logging,
- close the listed **Sonar new-code coverage** gaps,
- package every sub-module and verify Dropwizard **INT** startup,

…all backward-compatible with 1.x, all tests green, in exactly **one** unpushed commit referencing ION-12316.

---

## Step 0 — Orient & Back Up

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot
git status --short
git log --oneline develop..HEAD            # expect exactly 1 commit (ION-12316)
git rev-parse HEAD                         # record current tip
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-24
git tag    ION-12316-pre-coverage-backup-2026-06-24
```

Read `visibility/docs/2026-06-23-visibility-rebase-refactor.md` end-to-end (esp. §3 and §6). Read the booking module's cloud-sdk wiring (config classes, Guice modules, `MessagingClient`/`NotificationService` usage, `*DaoIT`, S3/lambda clients) as the template. Log the backup branch/tag + tip SHA and key reference files in session context (`progress` / `finding`).

`jira_get_issue: ION-12316` — re-read description / AC / comments for any new constraints. Log findings (`finding`).

---

## Step 1 — (Goal 1) Re-align DynamoDB config: reuse `dynamoDbConfig`, drop `cloudSdkDynamoDbConfig`

Yesterday's HIGH-2 fix added a separate `cloudSdkDynamoDbConfig` block to all visibility `config.yaml` files. This **diverges** from booking/network. Re-align:

1. Study exactly how **booking** and **network** expose a single DynamoDB config object to the cloud-sdk (`DynamoDbClientConfig` / table-prefix / `environment`) — they reuse one config block, not two.
2. Refactor visibility to **reuse the existing `dynamoDbConfig`** for the cloud-sdk repositories (e.g. by mapping/adapting the existing config class to what the cloud-sdk factory expects, exactly as booking/network do), and **remove** the `cloudSdkDynamoDbConfig` block from **all** visibility `config.yaml` files (conf/ + every app module incl. wm-inbound-processor's three processors) and from the config Java classes.
3. **Preserve table-name backward compatibility (HIGH-3):** the resolved physical names must still equal the legacy `environment + "_" + tableName` (mind the trailing underscore) — verify `container_events`, `container_events_outbound`, `container_events_pending`, `booking_BookingDetail`.
4. Add/extend `VisibilityApplicationConfig` tests proving the single-config wiring deserializes and yields the correct prefix/environment for each env.

Log the chosen approach and the booking/network reference (`decision`).

---

## Step 2 — (Goal 2) Complete the SQS + SNS cloud-sdk migration (booking as template)

Per §6 of the prior doc, only the two lambda modules (`visibility-outbound-poller`, `visibility-pending-start`) were migrated; the **core SQS/SNS backbone (~12 main classes + ~30 tests) still uses legacy `SQSClient`/`SNSClient`**. Complete it:

1. **Dependencies:** introduce the `mercury-services-commons` version property + `dependencyManagement` pinning `commons`, `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test` (mirroring booking); declare `cloud-sdk-api`/`-aws` as direct deps in each module that needs them.
2. **SQS consumers → `cloudsdk.messaging.api.MessagingClient<T>`:** migrate `visibility-commons` `SqsMessageHandler`, `-inbound` (`CargoVisibilityService`, `InboundEdiProcessor`, `ReprocessService`), `-matcher` (`MatchingProcessor`, `AbstractMatcher`), `-outbound` (`Outbound*Processor`, `OutboundGenerator`), `-pending` (`PendingSqsProcessor`), `-itv-gps` (`GPSEventProcessor`), `-wm` (`WMEventProcessor`). Replace `SQSModule` Guice bindings with `MessagingClientFactory`, exactly as booking wires it.
3. **SNS publisher → `cloudsdk.notification.api.NotificationService` / `notification.impl.SnsService` (and `SnsEventPublisher`):** migrate `VisibilityApplicationInjector`'s SNS wiring and any `SNSEventPublisher` usage; replace `SNSModule` with `NotificationClientFactory`.
4. **1:1 class remaps** (`messaging.*` → `cloudsdk.notification.*`): `MetaData`, `Event`, `EventLogger`, `EventPublisher`, `EventGenerator`, `Annotation(s)`, `ErrorHelper`, `RandomGenerator`.
5. **Config:** add the messaging/notification config blocks to each affected `config.yaml`, matching booking's keys/shape.
6. **Backward compatibility:** SQS/SNS message bodies and SNS subject/attributes must be **byte/shape identical** to the 1.x payloads so existing producers/consumers interop. Prove with serialization round-trip tests.

Keep only the legacy v1 AWS deps genuinely required (DynamoDB Local test runtime; lambda runtime event models). Update all affected tests to mock `MessagingClient` / `NotificationService`. Log each migrated class (`code_change`).

---

## Step 3 — (Goals 9, 4, 7, 10) DynamoDB DAO backward-compat + exhaustive tests

For **every** DAO (`ContainerEventDao`, `ContainerEventTableDao`, `ContainerEventOutboundDao`, `ContainerEventPendingDao`, `CargoVisibilitySubscriptionDao`, and any others):

1. **(Goal 9) 1.x compatibility check** — confirm each DAO's cloud-sdk implementation is wire-compatible with the 1.x implementation: same table, key schema, GSIs, attribute names/types, and read/write semantics. Start with `ContainerEventTableDao`, then do all DAOs. Document each comparison and any discrepancy + fix.
2. **(Goal 4) CRUD + boundary unit tests** — every DAO needs create / read / update / delete tests **and** boundary tests (null/empty/missing attributes, max sizes, absent optional GSIs, not-found, conditional-write failures, pagination).
3. **(Goal 7) Rework `*DaoIT` comments & scope** — remove any "focus is on backward compatibility" comment; replace with scope stating backward compatibility is covered **and** full CRUD is exercised across **all GSI indices** for each table plus boundary conditions and data formats. Expand the ITs accordingly so every GSI on every table is queried.
4. **(Goal 10) Round-trip integration tests** — add DynamoDB-Local round-trip ITs (save → read → assert equality, via `BaseDynamoDbIT`, `@Tag("integration")`, mirroring booking `*DaoIT`) for each DAO class to guarantee no break in existing functionality.

---

## Step 4 — (Goal 8) Exhaustive converter unit tests

For **all** attribute converters (e.g. `MetaDataAttributeConverter`, `ContainerEventSubmissionAttributeConverter`, `ContainerEventEnrichedPropertiesAttributeConverter`, and every other `*AttributeConverter`):

- Add exhaustive `transformFrom` **and** `transformTo` tests covering all boundary conditions: null, empty, legacy `S` vs stray `M` shapes, missing/extra fields, date/number encodings (legacy `WRITE_DATES_AS_TIMESTAMPS=true`), large payloads, and unicode.
- Assert the **exact** on-disk representation (byte-identical to 1.x), not just round-trip equality, to lock the backward-compat contract.

---

## Step 5 — (Goal 6) S3 client settings vs `createDefaultS3Client()`

`VisibilityApplicationInjector` historically created its S3 client with **specific socket-timeout and max-connections** settings.

- Compare those settings against the cloud-sdk `createDefaultS3Client()`.
- If `createDefaultS3Client()` does **not** honor them, determine the remedy following booking (e.g. a cloud-sdk factory overload / config-driven `ClientOverrideConfiguration` / `ApacheHttpClient` socket-timeout + max-connections builder) and implement it so the timeouts/connection pool match the legacy behavior.
- Add a test asserting the resulting client carries the expected timeout/max-connections (or that the chosen factory path is used). Document the finding and fix (`decision`).
- if there is a gap then document possible enhancement that is needed in the library

---

## Step 6 — (Goal 11) Document lambda AWS-client injection

- Trace how AWS service clients (DynamoDB, S3, SQS, SNS) are injected into the visibility lambdas (`visibility-s3-archiver`, `visibility-outbound-poller`, `visibility-pending-start`).
- Document the mechanism (Guice modules vs `HandlerSupport` vs cloud-sdk factories) clearly in the output doc, contrasting with booking's lambda injection.

---

## Step 7 — (Goal 12) `visibility-s3-archiver` HandlerSupport direct `DynamoDbClient` resolution

- Investigate **why** `visibility-s3-archiver` `HandlerSupport` resolves the AWS `DynamoDbClient` **directly** instead of via a cloud-sdk repository/factory.
- Compare with booking's `S3ArchiveLambda` / `IndexHandler`: do they resolve the raw client directly, or go through the cloud-sdk? If booking does **not**, determine whether this is a **gap in the cloud-sdk library** (no factory/abstraction for this lambda use case). **Document the conclusion** (gap or not, with evidence) in the output doc.
- Add an **integration test for this lambda** using the existing `dynamo-integration-test` infrastructure (DynamoDB Local via `BaseDynamoDbIT`), mirroring booking's lambda IT pattern if existing and if possible. Document gap and enhancement needed if not possible.

---

## Step 8 — (Goal 14) Logging review

Review and ensure **sufficient logging** (SLF4J/Logback) for:
- all initialization paths (injectors, Guice modules, factories, config wiring),
- main events in processors, DAOs, and services (message received/processed, DynamoDB read/write outcomes, SQS/SNS publish, S3 archive, retries, and error paths).

Use appropriate levels (DEBUG detail, INFO high-level events, WARN/ERROR for issues). Do not log secrets/PII. Note additions in the doc.

---

## Step 9 — (Goal 15) Close Sonar new-code coverage gaps

Add sufficient unit (and where AWS interaction exists, integration) coverage so the new-code quality gate passes for each class below. Target full coverage of the uncovered lines **and** the flagged uncovered conditions/branches:

| Class | Uncovered (new code) |
|-------|----------------------|
| a) `VisibilityApplicationConfig` | 3 lines, 0% |
| b) `VisibilityApplicationInjector` | 1 line, 0% |
| c) `VisibilityDynamoModule` | 49 lines, 0%, 8 conditions |
| d) `ContainerEventDao` | 13 lines, 56.7% |
| e) `VisibilityInboundDynamoDbAdminCommand` | 1 line, 76.5%, 1 condition |
| f) `ContainerEventTableDao` | 2 conditions, 86.7% |
| g) `ContainerEventOutboundDao` | 1 line, 93.8% |
| h) `ContainerEventPendingDao` | 1 line, 93.8% |
| i) `VisibilityWMDynamoModule` | 16 lines, 0%, 2 conditions |
| j) `CargoVisibilitySubscriptionDao` | 7 lines, 50% |
| k) `visibility-s3-archiver` `HandlerSupport` | 5 lines, 0% |
| l) `visibility-outbound-poller` `HandlerSupport` | 20 lines, 0% |

Many of these overlap with Steps 3, 4, 7. For the Guice modules (`VisibilityDynamoModule`, `VisibilityWMDynamoModule`) and `HandlerSupport` classes, add targeted module/handler tests (injector boot + binding assertions + branch coverage) following booking's module-test pattern. Re-check coverage locally (JaCoCo report) and iterate until each listed class is fully covered.

---

## Step 10 — (Goals 5, 3) Test conventions & integration tests (cross-cutting)

Apply to **all** new/updated tests:
- **(Goal 5)** Use **AssertJ** (`assertThat(...)`), `@Nested` for grouping, and `@ParameterizedTest` (`@ValueSource`/`@CsvSource`/`@MethodSource`) wherever multiple inputs apply.
- **(Goal 3)** Add **integration tests wherever feasible** (DynamoDB Local, lambda handlers, DAO round-trips) using the `dynamo-integration-test` infrastructure and `@Tag("integration")`, mirroring network/auth/registration/booking-bridge/webbl/booking examples.

---

## Step 11 — (Goal 13) Package & verify Dropwizard INT startup

```bash
mvn -f visibility/pom.xml clean package
```

For **each** visibility sub-module (`visibility-inbound`, `-outbound`, `-pending`, `-matcher`, `-wm-inbound-processor`, `-itv-gps-processor`, plus the `visibility-s3-archiver` / `-outbound-poller` / `-pending-start` lambdas where applicable), confirm Dropwizard initialization succeeds with its INT `config.yaml`:

```bash
java -jar visibility/<sub-module>/target/<artifact>.jar server visibility/conf/int/config.yaml
```

Verify: no `IllegalStateException` for missing config (the removed `cloudSdkDynamoDbConfig`), no table-name `ResourceNotFound`, no missing messaging/notification config, clean Guice injector start. Log packaging + startup results (`test_result`).

---

## Step 12 — Full verify, commit, document

```bash
mvn -f visibility/pom.xml verify          # unit + integration + dynamo — must be BUILD SUCCESS, 0 failures
```

Root-cause and FIX any failure (related or not); add a reproducing test for any bug before fixing; iterate until green.

Fold everything into the **one** outgoing commit:

```bash
git add -A
git commit --amend -m "ION-12316: Visibility AWS SDK 2.x — complete SQS/SNS migration, reuse dynamoDbConfig, DAO/converter backward-compat tests, lambda + S3 client review, coverage hardening"
git log --oneline develop..HEAD           # exactly 1 line
git log -1 --format="%B"                  # contains ION-12316
git status -sb                            # clean, nothing pushed
```

Do **not** push.

**Document** all findings and change details in `visibility/docs/2026-06-24-visibility-refactor-sns-sqs-coverage.md`, and **link** the prior doc `visibility/docs/2026-06-23-visibility-rebase-refactor.md` for reference. Structure:

1. **Summary** — goal, branch, single-commit outcome, model (Claude Opus 4.8, 1M).
2. **Config re-alignment** — why `cloudSdkDynamoDbConfig` was dropped and `dynamoDbConfig` reused; booking/network reference; table-name backward-compat proof.
3. **SQS/SNS migration** — every class migrated, Guice factory swaps, config blocks added, payload backward-compat evidence.
4. **DAO compatibility & tests** — per-DAO 1.x compatibility result; CRUD/GSI/boundary + round-trip ITs; `*DaoIT` comment/scope changes.
5. **Converter tests** — coverage of `transformFrom`/`transformTo` + on-disk format assertions.
6. **S3 client settings** — `createDefaultS3Client()` comparison + remedy (Goal 6).
7. **Lambda AWS-client injection** — documented mechanism (Goal 11).
8. **s3-archiver direct `DynamoDbClient`** — root cause + cloud-sdk gap conclusion + lambda IT (Goal 12).
9. **Logging** — additions (Goal 14).
10. **Sonar coverage** — before/after per listed class (Goal 15).
11. **Build / packaging / INT startup results** (Goal 13).
12. **References** — ION-12316, prior doc, booking/network reference classes.

Keep the doc updated as you proceed; log doc creation (`progress`).

---

## Step 13 — Handoff

```bash
git log --oneline develop..HEAD           # exactly 1 commit, message contains ION-12316
git status -sb                            # clean working tree, nothing pushed
```

- Update the output doc with final commit hash + full test/coverage/startup results.
- `session_add_context` final summary (`progress`); cross-link the 2026-06-23 session; keep status `active` (user reviews before push).
- Tell the user it is ready for review and **not pushed**.

---

## Output Summary — Definition of Done

- [ ] Session resumed/created with full traceability (decisions, code changes, findings, tests, model info); cross-linked to the 2026-06-23 session.
- [ ] **(Goal 1)** `cloudSdkDynamoDbConfig` removed everywhere; cloud-sdk repositories driven by the existing `dynamoDbConfig`, aligned with booking/network; legacy table names preserved + verified.
- [ ] **(Goal 2)** SQS (`MessagingClient`) + SNS (`NotificationService`/`SnsEventPublisher`) migration completed across the full visibility backbone; Guice factories swapped; config blocks added; payloads backward-compatible.
- [ ] **(Goals 4, 7, 9, 10)** Every DAO verified 1.x-compatible; exhaustive CRUD + boundary unit tests; `*DaoIT` comments/scope reworked to cover all GSIs + boundaries + data formats; round-trip ITs added.
- [ ] **(Goal 8)** Exhaustive `transformFrom`/`transformTo` converter tests with on-disk-format assertions.
- [ ] **(Goal 6)** `createDefaultS3Client()` vs legacy socket-timeout/max-connections analyzed; remedy implemented + tested.
- [ ] **(Goal 11)** Lambda AWS-client injection documented.
- [ ] **(Goal 12)** s3-archiver direct-`DynamoDbClient` root-caused; cloud-sdk gap conclusion documented; lambda IT added.
- [ ] **(Goal 14)** Sufficient logging for init + main events in processors/DAOs/services.
- [ ] **(Goal 15)** Sonar new-code coverage closed for all 12 listed classes (lines + flagged conditions).
- [ ] **(Goal 5)** Tests use AssertJ, `@Nested`, `@ParameterizedTest`; **(Goal 3)** integration tests added wherever feasible.
- [ ] **(Goal 13)** All visibility sub-modules packaged; Dropwizard INT startup verified.
- [ ] `mvn -f visibility/pom.xml verify` BUILD SUCCESS — all unit + integration + dynamo tests pass.
- [ ] `visibility/docs/2026-06-24-visibility-refactor-sns-sqs-coverage.md` written and linking the 2026-06-23 doc.
- [ ] Exactly **one** outgoing commit, message contains `ION-12316`, **not pushed**.
