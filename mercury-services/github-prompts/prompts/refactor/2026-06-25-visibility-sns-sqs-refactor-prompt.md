---
name: 2026-06-25-visibility-sns-sqs-refactor
description: Continue the visibility AWS-SDK-2.x (cloud-sdk) refactor on ION-12316. Land the remaining SQS + SNS cloud-sdk migration across the whole visibility backbone using booking as the template (no new integration tests for SQS/SNS — match booking's SQS/SNS test level). Verify booking's DynamoAdminCommand tests and add integration tests for visibility's VisibilityInboundDynamoDbAdminCommand proving it is idempotent (existing tables/GSIs are skipped with logging). Fix the Jenkins CI failures in visibility-matcher and visibility-pending (stale booking:2.1.8.M dependency). Rebase onto the latest develop if new visibility commits landed, keeping exactly one unpushed outgoing commit referencing ION-12316. Document gaps in the cloud-sdk library with clear steps. Do not reference internal design docs in code comments/commits. Do not push.
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

# Visibility — Complete SNS/SQS Migration + DynamoAdminCommand IT + CI Dependency Fix — ION-12316

> **Continuation of** `.github/prompts/refactor/2026-06-24-visibility-refactor-sns-sqs-config-coverage.prompt.md`.
> **Prior write-up (read first):** `visibility/docs/2026-06-24-visibility-refactor-sns-sqs-coverage.md` — especially
> **§10 (Goal 2 — SQS/SNS backbone migration plan, not landed last pass)**, **§8 (s3-archiver cloud-sdk gap)**,
> **§6 (S3 client cloud-sdk gap)**, and **§2 (goal-by-goal status table)**.
> **Earlier write-up:** `visibility/docs/2026-06-23-visibility-rebase-refactor.md`.

## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the existing feature branch `feature/ION-12316-visibiilty-aws-upgrade-copilot`
   (note the intentional `visibiilty` spelling in the branch name).
2. **DO NOT PUSH** — Never `git push` / `git push --force` / `--force-with-lease`. The user reviews locally and pushes
   manually. The user will explicitly ask you to push after review.
3. **SINGLE OUTGOING COMMIT** — End state must be exactly **one** outgoing commit (`git log --oneline develop..HEAD`
   returns one line), sitting on top of the **latest** develop. Fold all changes into it via `git commit --amend`.
4. **COMMIT MESSAGE** — The final commit message MUST contain the text `ION-12316` (required by the Bitbucket
   "git control freak" hook).
5. **LATEST DEVELOP IS THE FUNCTIONAL BASELINE** — If new commits landed on develop (and they touch visibility), rebase
   onto the latest develop first (see Step 1). Keep develop's latest functional logic and re-apply the AWS-upgrade
   changes on top. Never drop a functional change to keep an upgrade change.
6. **BACKWARD COMPATIBILITY IS PARAMOUNT** — All SQS/SNS message bodies, SNS subject/attributes, DynamoDB
   encoding/decoding, JSON blob serialization, table-name derivation, and S3 archive formats must remain wire-compatible
   with existing **1.x visibility** data, producers, and consumers. Reads tolerate legacy data; writes reproduce the
   legacy on-disk/on-wire representation. Every change must be proven by a test.
7. **ALIGN WITH booking / network** — These modules are the **reference implementations** for cloud-sdk SQS
   (`MessagingClient` / `MessagingClientFactory`), SNS (`NotificationService` / `SnsService` / `SnsEventPublisher`),
   Guice factories, DynamoDB admin commands, and test patterns. Prefer their proven approach over any divergent one
   already in visibility. Match booking's **level** of SQS/SNS testing (see Goal 2 — do **not** add new live SQS/SNS
   integration tests if booking does not have them).
8. **ALL TESTS MUST PASS** — Unit + the existing integration tests (including DynamoDB Local). Everything must compile
   and keep its coverage. Do not weaken or `@Disabled` a test to go green; root-cause and fix. If a test breaks (related
   or not), log it in session context, find the root cause, and FIX it; add a reproducing test for any bug before fixing.
9. **NO DESIGN-DOC REFERENCES IN CODE** — Do **not** reference these design/`docs/*.md` files (or Jira/Confluence URLs)
   in code comments, javadoc, or git commit messages. The design docs are internal reference material only. Code comments
   must stand on their own and describe the code, not the document.
10. **NO SHORTCUTS** — Always take the best implementation and design approach. If the correct fix is a larger refactor,
    do it in incremental, test-verified steps. Do not take quick wins that compromise correctness, backward
    compatibility, or code quality.
11. **MODEL** — Use Claude Opus 4.8 with the 1M context token window. Log this in session context (`model_info`).

---

## Session Context Protocol — FOLLOW STRICTLY

Reference: `.github/prompts/_base-session-protocol.md`.

Before starting ANY work:
1. `session_list` — look for the existing session for `ION-12316` / `visibility` / `visibility-aws-upgrade`
   (created 2026-06-23, continued 2026-06-24).
2. If found → `session_get` and **resume**; cross-link the prior session.
3. If none → `session_create`:
   - name: `visibility-sns-sqs-refactor-2026-06-25`
   - project: `mercury-services`
   - tags: `["visibility", "ION-12316", "aws-sdk-upgrade", "sns", "sqs", "dynamodb", "dynamo-admin-command", "ci-fix", "backward-compat", "in-progress"]`

**DURING** work — `session_add_context` after every significant action:
- Rebase decision + backup branch/tag + new tip SHA → `decision` / `progress`
- CI dependency root cause (`booking:2.1.8.M`) + fix → `finding` / `code_change`
- Each SQS/SNS class migrated + Guice factory swap → `code_change`
- DynamoAdminCommand idempotency findings (booking vs visibility) → `finding`
- Tests added + results → `test_result`
- cloud-sdk library gaps → `finding`
- Compilation / `mvn verify` / packaging results → `test_result`
- Blockers (missing cloud-sdk API, failing build, etc.) → `blocker`
- Model used → `model_info`

If context exceeds **85%**: persist a full summary via `session_add_context` (`progress`), write all findings into the
output doc immediately, note where you left off, then continue/hand off per the base protocol.

Use the MCP context server for **Jira** (ION-12316) and **Confluence** access, and for git operations if helpful.

---

## Goal Overview

Build on the single ION-12316 commit to:
1. **(Goal 1)** Land the remaining **SQS + SNS** cloud-sdk migration across the **whole** visibility backbone
   (the ~12 main classes + ~30 tests documented in §10 of the 2026-06-24 doc), using **booking** as the template.
2. **(Goal 2)** Add **no** new live SQS/SNS integration tests — first inspect what level of SQS/SNS test exists in
   **booking** and align visibility to exactly that level (unit tests mocking `MessagingClient`/`NotificationService`).
3. **(Goal 3)** Verify the **DynamoAdminCommand** tests in **booking**, then add **integration tests** (if missing) for
   visibility's `VisibilityInboundDynamoDbAdminCommand` proving it is **idempotent**: when the target tables / GSIs
   already exist it **skips creation and logs** the skip (no error, no mutation).
4. **(Goal 4)** Fix the **Jenkins CI build failures** in `visibility-matcher` and `visibility-pending` (stale
   `booking:2.1.8.M` dependency — see Step 2).
5. **(Goal 5)** **Document the cloud-sdk library gaps** with clear, actionable steps (carry forward the S3-client and
   s3-archiver raw-`DynamoDbClient` gaps from the 2026-06-24 doc, plus any new gap found while migrating SQS/SNS).

…all backward-compatible with 1.x, all tests green, in exactly **one** unpushed commit referencing ION-12316, with no
design-doc references in code/commits.

---

## Step 0 — Orient & Back Up

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot
git status --short
git log --oneline develop..HEAD            # expect exactly 1 commit (ION-12316)
git rev-parse HEAD                         # record current tip
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-25
git tag    ION-12316-pre-sns-sqs-backup-2026-06-25
```

Read `visibility/docs/2026-06-24-visibility-refactor-sns-sqs-coverage.md` end-to-end (esp. §10, §8, §6, §2). Read the
**booking** module's cloud-sdk SQS/SNS wiring (config classes, Guice modules, `MessagingClient`/`MessagingClientFactory`,
`NotificationService`/`SnsService`/`SnsEventPublisher` usage), its DynamoAdminCommand + that command's tests, and its
SQS/SNS test classes — these are your templates. Log the backup branch/tag + tip SHA and the key reference files in
session context (`progress` / `finding`).

`jira_get_issue: ION-12316` — re-read description / AC / comments for any new constraints. Log findings (`finding`).

---

## Step 1 — (Constraint 5) Rebase onto latest develop if needed

```bash
git fetch origin
git log --oneline HEAD..origin/develop -- visibility/    # any new visibility commits on develop?
```

- If there are **no** new commits touching `visibility/` on `origin/develop`, skip the rebase and continue.
- If there **are** new visibility commits, rebase the single ION-12316 commit onto the latest develop:

```bash
git rebase origin/develop
# resolve conflicts keeping develop's latest functional logic + re-applying the AWS-upgrade changes (Constraint 5)
mvn -f visibility/pom.xml clean verify     # must be BUILD SUCCESS after the rebase, before any new work
```

After the rebase, confirm exactly **one** outgoing commit on top of the latest develop:

```bash
git log --oneline develop..HEAD            # exactly 1 line, message contains ION-12316
```

Log the rebase outcome (new base SHA, conflicts resolved) in session context (`decision` / `progress`).

---

## Step 2 — (Goal 4) Fix the Jenkins CI failures in `visibility-matcher` and `visibility-pending`

**Root cause (already located).** `visibility/visibility-matcher/pom.xml` declares a **hard-pinned** dependency on
`com.inttra.mercury:booking:jar:2.1.8.M`, which does **not** exist in the monorepo/Artifactory — the in-repo `booking`
module is version `1.0`. `visibility-pending` depends on `visibility-matcher`, so it fails to resolve **transitively**.
This is why the build log shows:

```
Could not resolve dependencies for project com.inttra.mercury:visibility-matcher:jar:1.0:
  artifact com.inttra.mercury:booking:jar:2.1.8.M (absent)
visibility/visibility-matcher finished FAILURE
visibility/visibility-pending finished FAILURE
```

**Do this:**
1. the booking model version to refer from lib is 3.0.0M, check the other visibility modules. Fix issue in `visibility-matcher` / `visibility-pending`). 
2. Fix `visibility-matcher/pom.xml` (and any other visibility pom pinning a stale booking/`2.1.8.M` version) to the
   correct 3.0.0M version from lib. 
3. **Backward-compat / API check:** make sure all changes in visibility upgrade are backward compatible.
4. Rebuild the two modules to prove the resolution is fixed:

```bash
mvn -f visibility/pom.xml -pl visibility-matcher,visibility-pending -am clean test
```

Log the root cause + fix (`finding` / `code_change`).

---

## Step 3 — (Goals 1, 2) Complete the SQS + SNS cloud-sdk migration (booking as template)

Land the backbone migration that §10 of the 2026-06-24 doc planned but deferred. cloud-sdk `1.0.26` already ships the
full surface (consumer `MessagingClient.listMessages/receiveMessages/sendMessage/deleteMessage` + `QueueMessage`, and
`NotificationService`/`SnsService`/`SnsEventPublisher`), so **use latest `mercury-services-commons` 1.0.26-SNAPSHOT**.

1. **Dependencies / wiring:** add a `MessagingClient<String>` Guice provider (via `MessagingClientFactory`) and a
   `NotificationService` provider (via the notification factory), and the messaging/notification **config blocks** to
   each affected `config.yaml`, mirroring **booking**. Replace the legacy `SQSModule` / `SNSModule` Guice bindings with
   the cloud-sdk factories.
2. **SQS consumers → `cloudsdk.messaging.api.MessagingClient<String>` / `QueueMessage<String>`:** migrate
   `visibility-commons` `SqsMessageHandler` (`Consumer<Message>` → `Consumer<QueueMessage<String>>`;
   `receiveMessage`→`listMessages`, `deleteMessage(url, receiptHandle)`, DLQ `sendMessage`) and `SqsMessageHandlerManager`,
   then every consumer that builds the work unit: `-inbound` (`CargoVisibilityService`, `InboundEdiProcessor`,
   `ReprocessService`), `-matcher` (`MatchingProcessor`, `AbstractMatcher`), `-outbound` (`Outbound*Processor`,
   `OutboundGenerator`), `-pending` (`PendingSqsProcessor`), `-itv-gps` (`GPSEventProcessor`), `-wm` (`WMEventProcessor`).
3. **SNS publisher → `cloudsdk.notification.api.NotificationService` / `notification.impl.SnsService` /
   `notification.workflow.SnsEventPublisher`:** migrate `VisibilityApplicationInjector`'s SNS wiring and any
   `SNSEventPublisher` usage.
4. **1:1 class remaps** (`messaging.*`/`logging.*` → `cloudsdk.notification.*`): `MetaData`, `Event`, `EventLogger`,
   `EventPublisher`, `EventGenerator`, `Annotation(s)`, `ErrorHelper`, `RandomGenerator`, etc. — match booking's targets.
5. **Backward compatibility:** SQS/SNS message bodies and SNS subject/attributes must be **byte/shape identical** to the
   1.x payloads so existing producers/consumers interop. Prove with serialization round-trip **unit** tests.
6. **Remove** the legacy `SQSClient`/`SNSClient` deps and imports once all references are gone. Keep only the legacy v1
   AWS deps genuinely required elsewhere (e.g. DynamoDB Local test runtime, lambda runtime event models).

**(Goal 2) Test level — match booking, no new live SQS/SNS ITs.** First inspect booking's SQS/SNS tests
(`grep`/view booking's `*MessagingClient*`, `*Notification*`, `*Sns*`, processor tests). Booking covers SQS/SNS with
**unit tests that mock `MessagingClient`/`NotificationService`** — replicate exactly that level in visibility. Update the
~30 affected visibility tests to mock `MessagingClient`/`NotificationService` (AssertJ + `@Nested` + `@ParameterizedTest`
per Goal 7). **Do not** add new live SQS/SNS or localstack integration tests unless booking has them.

Log each migrated class (`code_change`) and the booking SQS/SNS test-level finding (`finding`).

---

## Step 4 — (Goal 3) DynamoAdminCommand idempotency + integration tests

1. **Verify booking's command + tests.** Locate booking's DynamoDB admin/table-creation command and its tests
   (`grep` for `*DynamoDbAdminCommand` / `*DynamoAdminCommand` / table-creation command in `booking/`). Confirm how
   booking tests it and, crucially, that it is **idempotent** — i.e. when a table/GSI already exists it **skips** and
   **logs** rather than erroring. Note booking's exact test pattern (unit vs DynamoDB Local IT).
2. **Inspect visibility's `VisibilityInboundDynamoDbAdminCommand`.** Confirm its create-table / create-GSI path detects
   pre-existing tables and GSIs and **skips with a log line** (e.g. catches `ResourceInUseException` /
   checks `describeTable` first). If the skip-on-exists behavior is missing or incomplete, **implement it** following
   booking (best approach, no shortcut) so re-running the command against an already-provisioned environment is a safe
   no-op.
3. **Add an integration test** (if missing) for `VisibilityInboundDynamoDbAdminCommand` using the existing
   `dynamo-integration-test` infra (DynamoDB Local via `BaseDynamoDbIT`, `@Tag("integration")`, mirroring booking's
   command IT and the existing visibility `*DaoIT`). It must assert:
   - first run **creates** the table(s) + GSI(s);
   - a **second run is idempotent** — existing tables/GSIs are **skipped with logging**, the command **succeeds**, and
     the table definition is **unchanged**.
   Use AssertJ, `@Nested`, and `@ParameterizedTest` where multiple inputs apply (Goal 7).

Log the booking-vs-visibility comparison and any production change (`finding` / `code_change`).

---

## Step 5 — (Goal 7) Test conventions

Apply to **all** new/updated tests:
- **AssertJ** (`assertThat(...)`) for assertions.
- `@Nested` for grouping related scenarios.
- `@ParameterizedTest` (`@ValueSource` / `@CsvSource` / `@MethodSource`) wherever multiple inputs apply.
Mirror network/auth/registration/booking-bridge/webbl/booking examples.

---

## Step 6 — (Goal 5) Document cloud-sdk library gaps with clear steps

Maintain a single, actionable **"cloud-sdk gaps"** section in the output doc. Carry forward and keep current:
- **S3 client tuning gap** — `AwsStorageConfig.Builder` has no `socketTimeout`/`connectionTimeout`/`maxConnections`
  knobs and `createS3Client(config)` does not fall back to the default credentials chain (from §6 of the 2026-06-24 doc).
- **Schemaless read gap** — `cloud-sdk-api`'s `DatabaseRepository<T,K>` is bean-typed only; no raw
  `getItem(tableName, key) → Map<String,CloudAttributeValue>` for the s3-archiver use case (from §8 of the 2026-06-24 doc).
- **Any new gap** surfaced while migrating SQS/SNS (e.g. a missing message-attribute API, a missing batch/visibility-
  timeout knob, a missing factory overload).

For each gap give: the legacy capability, the cloud-sdk shortfall (with evidence), the workaround used in visibility,
and a **concrete proposed enhancement** to `cloud-sdk-api`/`cloud-sdk-aws` (the method/builder to add). Log gaps as
`finding`.

---

## Step 7 — Full verify, commit (amend), document

```bash
mvn -f visibility/pom.xml clean verify     # unit + existing integration (DynamoDB Local) — BUILD SUCCESS, 0 failures
```

Also re-run the two previously-failing modules explicitly to prove the CI fix:

```bash
mvn -f visibility/pom.xml -pl visibility-matcher,visibility-pending -am clean verify
```

Root-cause and FIX any failure (related or not); add a reproducing test for any bug before fixing; iterate until green.

Fold everything into the **one** outgoing commit (no design-doc reference in the message — Constraint 9):

```bash
git add -A
git commit --amend -m "ION-12316: Visibility AWS SDK 2.x — complete SQS/SNS cloud-sdk migration, idempotent DynamoDB admin command + IT, fix stale booking dependency in visibility-matcher/visibility-pending"
git log --oneline develop..HEAD            # exactly 1 line
git log -1 --format="%B"                   # contains ION-12316, no docs/* path or Jira URL
git status -sb                             # clean, nothing pushed
```

Do **not** push.

**Document** all of today's work and changes — with **all commands and descriptions** for future reusability and the
user's learning — in a **new** doc `visibility/docs/2026-06-25-visibility-sns-sqs-refactor.md`, linking the prior docs
(`2026-06-24-...` and `2026-06-23-...`). Structure:

1. **Summary** — goal, branch, single-commit outcome, model (Claude Opus 4.8, 1M), rebase result (if any).
2. **Rebase** — whether a rebase was needed, new base SHA, conflicts resolved.
3. **CI dependency fix** — `booking:2.1.8.M` root cause, the corrected coordinate, API-compat check, before/after build.
4. **SQS/SNS migration** — every class migrated, Guice factory swaps, config blocks added, payload backward-compat
   evidence, the legacy v1 deps removed.
5. **SQS/SNS test level** — booking's SQS/SNS test level finding and how visibility was aligned (unit, mocked, no new ITs).
6. **DynamoAdminCommand** — booking command + test review, visibility idempotency (skip-with-logging) implementation/
   confirmation, the new integration test.
7. **cloud-sdk gaps** — the documented gaps + concrete proposed enhancements (Goal 5).
8. **Build / packaging results** — `mvn verify` output, the two previously-failing modules now green.
9. **References** — ION-12316, prior docs, booking reference classes.

Keep the doc updated as you proceed; log doc creation (`progress`). Remember: this doc is **internal reference only** —
**do not** cite it from code comments or the commit message (Constraint 9).

---

## Step 8 — Handoff

```bash
git log --oneline develop..HEAD            # exactly 1 commit, message contains ION-12316
git status -sb                             # clean working tree, nothing pushed
```

- Update the output doc with final commit hash + full test/build results.
- `session_add_context` final summary (`progress`); cross-link the 2026-06-23 / 2026-06-24 sessions; keep status
  `active` (user reviews before push).
- Tell the user it is ready for review and **not pushed** (they will ask you to push).

---

## Output Summary — Definition of Done

- [ ] Session resumed/created with full traceability (decisions, code changes, findings, tests, model info); cross-linked
      to the 2026-06-23 / 2026-06-24 sessions.
- [ ] **(Constraint 5)** Rebased onto the latest develop if new visibility commits landed; exactly one outgoing commit on
      top of the latest develop.
- [ ] **(Goal 4)** `visibility-matcher` (and `visibility-pending` transitively) build cleanly — stale `booking:2.1.8.M`
      replaced with the correct 3.0.0M booking model as referenced by other visibility modules; consumed booking API verified.
- [ ] **(Goal 1)** SQS (`MessagingClient`) + SNS (`NotificationService`/`SnsService`/`SnsEventPublisher`) migration
      completed across the full visibility backbone; Guice factories swapped; config blocks added; payloads
      backward-compatible; legacy `SQSClient`/`SNSClient` removed.
- [ ] **(Goal 2)** SQS/SNS tested at booking's level (unit, mocked `MessagingClient`/`NotificationService`); **no** new
      live SQS/SNS integration tests added.
- [ ] **(Goal 3)** booking's DynamoAdminCommand tests verified; `VisibilityInboundDynamoDbAdminCommand` proven idempotent
      (existing tables/GSIs skipped with logging) via a new DynamoDB-Local integration test.
- [ ] **(Goal 5)** cloud-sdk library gaps documented with concrete proposed enhancements.
- [ ] **(Goal 7)** All new/updated tests use AssertJ, `@Nested`, `@ParameterizedTest`.
- [ ] **(Constraint 9)** No design-doc/Jira-URL references in code comments or the commit message.
- [ ] **(Constraint 10)** No shortcuts — best implementation/design throughout.
- [ ] `mvn -f visibility/pom.xml clean verify` BUILD SUCCESS — all unit + existing integration tests pass; the two
      previously-failing modules are green.
- [ ] `visibility/docs/2026-06-25-visibility-sns-sqs-refactor.md` written (with all commands + descriptions) and linking
      the prior docs.
- [ ] Exactly **one** outgoing commit, message contains `ION-12316`, **not pushed**.
