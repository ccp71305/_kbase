---
name: 20260728-watermill-booking-aws-sdk-cloud-sdk-upgrade
description: >
  AWS-SDK-2.x (cloud-sdk) refactor / functional change on the watermill-booking module (ION-16380).
  Goals: migrate watermill-booking S3/SQS/SNS/DynamoDB to cloud-sdk (AWS SDK 2.x); mandatory commons 1.0.28-SNAPSHOT; OWASP pre/post scans; VS Code run configs; live AWS DynamoDB parity + AWS service-details tables. Rebase onto the latest develop preserving develop's functional
  changes (incoming-wins on conflicts, then re-apply the AWS-upgrade changes), keep exactly one
  unpushed outgoing commit referencing ION-16380, full local mvn clean verify with complete JaCoCo
  coverage on all new code, unit + integration tests (DynamoDB/SQS/SNS/SES) mirroring the reference
  modules, document cloud-sdk gaps, and log every search/grep/git/analysis command. Do not push.
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

# watermill-booking — AWS SDK 2.x (cloud-sdk) Refactor — ION-16380

> **Jira:** ION-16380


> **Read first (reference material — all files):**
> - C:\Users\arijit.kundu\projects\mercury-services\watermill-publisher\docs\2026-06-30-watermill-publisher-aws2x-DESIGN-claude.md
> - C:\Users\arijit.kundu\projects\mercury-services\watermill-publisher\watermill-booking\docs\2026-06-30-watermill-publisher-watermill-booking-aws2x-DESIGN-claude.md


## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the feature branch `feature/ION-16380-watermill-booking-aws-upgrade`. If it **already exists**, check it out and
   rebase it onto the latest develop (Step 1), keeping exactly **one** outgoing commit. If it does **not** exist,
   pull the latest develop and **create `feature/ION-16380-watermill-booking-aws-upgrade` from the latest develop** before any work (Step 0).
2. **DO NOT PUSH** — Never `git push` / `--force` / `--force-with-lease`. The user reviews locally and pushes
   manually, and will explicitly ask you to push after review.
3. **SINGLE OUTGOING COMMIT** — End state must be exactly **one** outgoing commit
   (`git log --oneline develop..HEAD` returns one line), sitting on top of the **latest** develop. Fold all
   changes into it via `git commit --amend`. This MUST hold even after a rebase + conflict resolution.
   The only exception is if any owasp fix can go on its own separate commit then have 2 seperate commits - one for owasp fix and the other for the aws upgrade.
4. **COMMIT MESSAGE** — The final commit message MUST contain the Jira key `ION-16380` (required by the Bitbucket
   "git control freak" hook).
5. **LATEST DEVELOP IS THE FUNCTIONAL BASELINE (PRIORITY)** — develop's latest commits are **functional changes**
   and take **priority**. If new commits landed on develop that touch `watermill-booking/`, rebase onto the latest develop
   first (Step 1). On any conflict between develop and the AWS-upgrade changes, **take the incoming develop change
   first**, then **adjust and re-apply the AWS-SDK-upgrade changes on top** so the upgrade conforms to develop.
   The rebase must in **no way** drop, weaken, or alter develop's incoming functional behavior. Never sacrifice a
   functional change to keep an upgrade change.
6. **BACKWARD COMPATIBILITY IS PARAMOUNT** — All wire/disk formats (SQS/SNS message bodies, SNS subject/attributes,
   DynamoDB encoding/decoding, JSON serialization, table-name derivation, S3 formats, SES payloads) must remain
   compatible with existing 1.x data, producers, and consumers. Reads tolerate legacy data; writes reproduce the
   legacy representation. Every change must be proven by a test.
7. **ALIGN WITH THE REFERENCE MODULES** — Use the already-upgraded modules as the template:
   - **SQS / SNS** → mirror **booking** and **network** (`MessagingClient` / `MessagingClientFactory`,
     `NotificationService` / `SnsService` / `SnsEventPublisher`, Guice factories, config blocks, test level).
   - **Email / SES** → mirror **booking** and **auth**.
   - **S3** → mirror **booking** (cloud-sdk storage client / factory + config blocks).
   - **DynamoDB** → mirror the upgraded DAO/admin-command patterns in booking/network/registration/webbl/booking-bridge.
   Prefer the proven reference approach over any divergent one already in `watermill-booking`.
8. **ALL TESTS MUST PASS** — Unit + integration (incl. DynamoDB Local). Everything compiles and keeps/raises
   coverage. Do not weaken or `@Disabled` a test to go green — root-cause and fix. If a test breaks (related or
   not), log it in session context, find the root cause, and FIX it; add a reproducing test for any bug first.
9. **NO DESIGN-DOC / TICKET REFERENCES IN CODE** — Do not reference docs/`*.md`, Jira, or Confluence URLs in code
   comments, javadoc, or the commit message. Code comments must stand on their own.
10. **NO SHORTCUTS** — Always take the best implementation/design approach. If the correct fix is a larger
    refactor, do it in incremental, test-verified steps. No quick wins that compromise correctness, backward
    compatibility, or code quality.
11. **MODEL** — Use Claude Opus 4.8 with the 1M context window. Log this in session context (`model_info`).
12. **LOG EVERY COMMAND** — Every search / grep / `git` / build / analysis command you run MUST be captured in
    the output doc (and key ones in session context) **with a clear descriptive comment** explaining why it was
    run and what it found, so the work is reproducible and reusable later (see Step 7 + the command-log rule).
13. **USE THE KNOWLEDGE BASE** — The mcp-context-server kb tooling is configured and indexes both this repo and
    `mercury-services-commons` (so you can read the cloud-sdk-api / cloud-sdk-aws sources directly). Use `kb_grep`
    and `kb_find_files` to locate reference implementations and usages (both verified working). The semantic
    `kb_search` may return empty if its index is not built — if so, fall back to `kb_grep` / `kb_find_files`. Log
    each kb query and what it revealed (Constraint 12).
14. **LOG PASSING TEST COMMANDS + TEST COUNTS** — Record in the output doc every unit-test and integration-test
    command that passes, and an accurate count of tests run (unit + integration). If multiple test runners are
    used (e.g. JUnit and TestNG), summarize the counts **per runner** (see Step 3 + Step 5).
15. **BUILD DISCIPLINE / MACHINE-SLOWNESS HANDLING** (learned on value-added-service ION-16110) —
    - **Do not run multiple `mvn` builds concurrently.** Antivirus scans make parallel Maven
      runs stall. Run one build at a time; wait for it to finish before starting the next.
    - **Never pipe a live `mvn` run straight into `Select-String`/`findstr`.** The pipe buffers all output until the
      JVM exits, so a long build looks like a hang. Instead `... | Tee-Object -FilePath $env:TEMP\<mod>-verify.log`,
      then grep the log for `Tests run:` / `BUILD SUCCESS|FAILURE` while/after it runs.
    - **A stalled build looks identical to a dead one — identify before killing.** List JVMs with
      `Get-Process -Name java,mvn | Select Id,ProcessName,CPU`; a live Maven run shows the `mvn` launcher **plus** a
      forked Surefire/Failsafe JVM. Before stopping anything, read its full command line with
      `(Get-CimInstance Win32_Process -Filter "ProcessId=<pid>").CommandLine` — editor JVMs carry
      `.vscode\extensions\...` / `eclipse.jdt.ls` and must be left alone; build JVMs carry `surefire`/`failsafe`
      booter jars or `-jar target\...`. Only ever stop by explicit **PID** (`Stop-Process -Id <pid>`), never by name.
    - **Before rewriting a pushed branch** (amend/rebase), take a backup branch + tag, and publish only with
      `git push --force-with-lease` (aborts if someone else pushed meanwhile).
16. **BACKWARD-COMPAT NULL ATTRIBUTES + DEPLOYMENT/COMMAND-NAME VERIFICATION** (learned on value-added-service) —
    - A v2 `AttributeConverter.transformFrom` **must return `null` for a null input** (do not build
      `AttributeValue.builder().s(null)`), so the enhanced client omits the attribute; otherwise DynamoDB rejects the
      write with `ValidationException: Supplied AttributeValue is empty`. Prove with a DynamoDB-Local IT that saves an
      entity with the optional attribute absent.
    - Verify the live DynamoDB table schema parity across environments and the ECS deployment, and check whether the
      Dropwizard table-admin **command name** changed (see the dedicated Step 3B).

---

## Session Context Protocol — FOLLOW STRICTLY

Reference: `.github/prompts/_base-session-protocol.md`.

**Before starting ANY work:**
1. `session_list` — look for an existing session for `ION-16380` / `watermill-booking` / `watermill-booking-aws-upgrade`.
2. If found → `session_get` and **resume**; cross-link the prior session.
3. If none → `session_create`:
   - name: `watermill-booking-aws-sdk-cloud-sdk-upgrade-20260728`
   - project: `mercury-services`
   - tags: `["watermill-booking", "ION-16380", "aws-sdk-upgrade", "aws-sdk-cloud-sdk-upgrade", "in-progress"]`

**DURING** work — `session_add_context` after every significant action:
- Rebase decision + backup branch/tag + new tip SHA → `decision` / `progress`
- Root causes + fixes → `finding` / `code_change`
- Each class/DAO/service migrated + Guice factory swap → `code_change`
- Tests added + results, coverage numbers → `test_result`
- cloud-sdk library gaps → `finding`
- Compilation / `mvn verify` / packaging results → `test_result`
- Blockers → `blocker`
- Model used → `model_info`
- Key search/grep/git/analysis commands + what they revealed → `finding` (also mirror into the output doc)

**Token-usage telemetry (verified working 2026-06-30).** The mcp-context-server captures token usage
automatically via harness-level hooks — Copilot CLI `agentStop` (`.github/hooks/telemetry.json` →
`scripts/copilot_telemetry_hook.py`) and Claude Code `Stop` (`.claude/settings.json` →
`scripts/claude_telemetry_hook.py`). Therefore:
- **Do NOT fabricate or estimate usage.** The model cannot see its own usage block (it goes to the harness, not
  the model). Only call `session_record_usage` if you have **real** provider usage numbers
  (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `model`); otherwise
  rely on the installed hooks and skip.
- **At the end** (and if context gets large), call `session_usage_report` for this session to confirm usage was
  captured, and optionally `telemetry_report` for the portfolio view; note the result in the output doc. If
  `record_count = 0`, flag that the harness hook may not have fired (do not back-fill with guesses).

If context exceeds **85%**: persist a full summary via `session_add_context` (`progress`), write all findings into
the output doc immediately, note where you left off, then continue/hand off per the base protocol.

Use the MCP context server for **Jira** (`ION-16380`) and **Confluence** access, for git operations if helpful, and
for **knowledge-base** access (`kb_grep` / `kb_find_files` over this repo + `mercury-services-commons`; fall back
from the semantic `kb_search` to `kb_grep` / `kb_find_files` if its index is empty).

---

## Goal Overview

Accomplish the following on the `watermill-booking` module, all backward-compatible with 1.x, all tests green with full
JaCoCo coverage on new code, in exactly **one** unpushed commit referencing `ION-16380`, with no design-doc
references in code/commits:

- **AWS SDK 2.x (cloud-sdk) upgrade** — migrate watermill-booking's AWS interactions (S3, SQS, SNS, and DynamoDB if present) from AWS SDK v1 / legacy client libs to `cloud-sdk-api` + `cloud-sdk-aws`, mirroring booking / network / auth / visibility / webbl / booking-bridge. Follow the reference design docs above.
- **Module path (NESTED):** build/test with `mvn -pl watermill-publisher/watermill-booking -am ...`. The `mercury.commons.version` property lives in `watermill-publisher/watermill-commons/pom.xml` (currently `1.R.01.025`); bump it there and verify each module resolves it via `mvn -pl watermill-publisher/watermill-booking -am dependency:tree`.
- **commons `1.0.28-SNAPSHOT` is MANDATORY** — do NOT fall back to `1.R.01.025` or any other version. If it does not compile, FIX the code to compile against `1.0.28-SNAPSHOT` (adjust imports/APIs); do not downgrade. Add a `jackson-bom 2.21.4` dependencyManagement pin only if a HIGH CVE appears.
- **OWASP (STILL RUN, even though the goal is the AWS upgrade):** run dependency-check on the shaded jar BEFORE any change (baseline) and AFTER (post). dependency-check is installed; NVD key in `$env:NVD_API_KEY`. Publish BOTH HTML+JSON reports under `C:\temp\latest-dep-chk-reports\watermill-booking\{baseline,post}\`; compare CVEs and summarize the delta. The 2026-07-28 baseline was **0 HIGH/CRITICAL + 14 MEDIUM** on commons `1.R.01.025` — confirm the post-upgrade scan does not regress. Example:
  `mvn -pl watermill-publisher/watermill-booking -am package -DskipTests` then
  `dependency-check --project watermill-booking --scan .\watermill-publisher\watermill-booking\target\watermill-booking-1.0.jar --out <out> --format HTML --format JSON --suppression .\watermill-publisher\watermill-booking\suppressions.xml --nvdApiKey $env:NVD_API_KEY`.
- **VS Code run configs first** — add Run + Debug entries for this module (mainClass `com.inttra.mercury.watermill.booking.WatermillBKApplication`, args `server ${workspaceFolder}/watermill-publisher/watermill-booking/conf/int/config.yaml`).
- **Local boot-check** on the shaded jar with the latest develop. **Continue-on-INT-like-boot-failure rule:** if the local boot fails with an error that matches the **rates** precedent — an eager startup call to an INT platform endpoint that is itself down/unreachable (rates crashed on the INT `api-alpha` auth gateway returning HTTP 502, and the deployed INT build failed identically) — then FLAG it and **CONTINUE** (no need to stop). Verify the "similar error" claim (probe the endpoint / read the deployed INT ECS task + CloudWatch logs) before continuing. Only STOP for a genuine code/config defect introduced by the change.
- **Design plan** documented in the output doc (after the OWASP baseline section) before implementing; **unit test coverage** for all new code; **DynamoDB-Local integration tests** (`dynamo-integration-test` / `BaseDynamoDbIT`) for any DynamoDB DAO/service; mirror the reference modules' SQS/SNS/S3 test level.
- **All tests PASS** (unit + integration). No shortcuts.
- **Live AWS verification (Step 3B):** verify the DynamoDB table definitions (key schema, GSIs, TTL, streams) across INT/QA/CVT/PROD — INT via the INT profile, QA/CVT/PROD via the QA profile. Higher-environment (QA/CVT/PROD) TTL/stream config wins — flag any divergence in its own section. Publish ALL AWS service details in proper **tables**: environment-wise ECS cluster / service / task / log-group, and environment-wise DynamoDB tables, task role, SQS queues, SNS topics and S3 buckets.
- **INT deployment details** (account `081020446316`, region `us-east-1`, profile `081020446316_INTTRA-Dev-Engg`, creds already in terminal): cluster **`ANEDVAW-001`**, service **`WatermillPublisherBooking-dev`**, task **`WatermillPublisherBooking-latest-dev-Task:1`**, container `WatermillPublisherBooking-dev-Container`, task role `arn:aws:iam::081020446316:role/INTTRA-ECS-INT-Watermill-BK-Task`, log group `inttra-ecs-logs` (stream prefix `WatermillPublisherBooking-latest-dev`), S3 `inttra-int-workspace`, SQS `inttra_int_sqs_watermill_bk`, SNS `arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event`.
- **QA/CVT/PROD** (account `642960533737`, profile `642960533737_INTTRA2-QATeam`): add the static QA credentials **provided in the generator INPUTS block** (`.github/prompts/aws-sdk-upgrade-refactor-generator.md`) to `~/.aws/credentials` (static-only profile; STS tokens expire — refresh as needed; never commit credentials).

---

## Step 0 — Orient, Resolve Branch & Back Up

First make sure develop is current, then resolve the branch — **create it from the latest develop if it does not
exist**, or back it up if it does.

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git fetch origin
git checkout develop && git pull --ff-only origin develop      # latest develop is the functional baseline

# Does the feature branch already exist (locally or on origin)?
git rev-parse --verify feature/ION-16380-watermill-booking-aws-upgrade 2>/dev/null || git ls-remote --exit-code --heads origin feature/ION-16380-watermill-booking-aws-upgrade
```

- **If `feature/ION-16380-watermill-booking-aws-upgrade` does NOT exist** → create it from the latest develop and start fresh:

```bash
git checkout -b feature/ION-16380-watermill-booking-aws-upgrade develop          # branch off the just-pulled latest develop
```

- **If `feature/ION-16380-watermill-booking-aws-upgrade` already exists** → check it out, back it up, and proceed to the Step 1 rebase:

```bash
git checkout feature/ION-16380-watermill-booking-aws-upgrade
git status --short
git log --oneline develop..HEAD             # record current outgoing commit(s)
git rev-parse HEAD                          # record current tip
git branch feature/ION-16380-watermill-booking-aws-upgrade-backup-20260728   # safety backup before rebase
git tag    ION-16380-pre-refactor-backup-20260728
```

- Read the reference material listed above (all reference files) and the reference
  modules' cloud-sdk wiring (booking/network for SQS/SNS, booking/auth for SES, booking for S3,
  booking/network/registration for DynamoDB) — these are your templates. Use `kb_grep` / `kb_find_files` to open
  the cloud-sdk-api / cloud-sdk-aws sources from `mercury-services-commons` as needed.
- `jira_get_issue: ION-16380` — re-read description / AC / comments for constraints. Log findings.

- Log the branch decision (created-from-develop vs existing+backed-up), the backup branch/tag + tip SHA, and the
  key reference files in session context (`progress` / `finding` / `decision`).

---

## Step 1 — Rebase onto latest develop (develop's functional changes take PRIORITY)

If you **just created `feature/ION-16380-watermill-booking-aws-upgrade` from the latest develop** in Step 0, it is already current — skip the rebase and
go to Step 2. Otherwise (the branch pre-existed), bring it onto the latest develop:

```bash
git fetch origin
git log --oneline HEAD..origin/develop -- watermill-booking/    # any new commits touching this module on develop?
```

- If there are **no** new commits touching `watermill-booking/` on `origin/develop`, skip the rebase and continue.
- If there **are** new commits, rebase the outgoing commit(s) onto the latest develop:

```bash
git rebase origin/develop
```

**Conflict-resolution rule (Constraint 5):** develop's commits are **functional changes** and win. For every
conflict, **take the incoming develop change first**, then **adjust and re-apply the AWS-SDK-upgrade change on top**
so the upgrade conforms to develop's new code. Never drop or alter develop's functional behavior to preserve an
upgrade change.

```bash
mvn -pl watermill-publisher/watermill-booking -am clean verify     # MUST be BUILD SUCCESS after the rebase, before any new work
```

After the rebase + conflict resolution, confirm exactly **one** outgoing commit on top of the latest develop
(squash/`--amend` as needed):

```bash
git log --oneline develop..HEAD            # exactly 1 line, message contains ION-16380
```

Log the rebase outcome (new base SHA, conflicts resolved, how each was reconciled) in session context
(`decision` / `progress`) and in the output doc.

---

## Step 2 — Implement the goals

Implement every goal from the **Goal Overview** on `watermill-booking`, in incremental, test-verified steps, mirroring the
reference modules (Constraint 7). For each unit of work:
- Use `git_log`, the kb tooling (`kb_grep` / `kb_find_files`; fall back from the semantic `kb_search` if its index
  is empty), and `grep` to find all usages and recent changes before editing; **log each command + what it
  revealed** (Constraint 12 / 13).
- Migrate AWS interactions to the `cloud-sdk-api` interfaces (implemented by `cloud-sdk-aws`), swapping legacy
  Guice bindings for the cloud-sdk factories and adding the matching config blocks to each affected `config.yaml`,
  exactly as the reference modules do.
- Keep every wire/disk format byte/shape-compatible with 1.x (Constraint 6); prove it with round-trip tests.
- Remove legacy AWS SDK v1 deps/imports only once all references are gone (keep any genuinely still required,
  e.g. DynamoDB Local test runtime, lambda runtime event models).
- **Dropwizard DynamoDB table-admin command** — migrate the module's table-provisioning command to extend the
  cloud-sdk `DynamoDbAdminCommand` (mirrors booking/booking-bridge/visibility), deriving the table/GSI/TTL from the
  v2 `@DynamoDbBean`/`@Table`/`@GsiConfig`/`@DynamoDbSecondaryPartitionKey` annotations. **Watch the registered
  command name:** `DynamoDbAdminCommand` (and the old dynamo-client `AbstractDynamoCommand`) register
  `super("dynamo-create", …)`. If the module's **pre-upgrade** command was a bespoke `CreateTables extends
  ConfiguredCommand` with `super("create-tables", …)` (as booking / booking-bridge / visibility had), the CLI verb
  changes `create-tables` → `dynamo-create`, and the module's **deploy/CI `$task` argument must be updated to match**
  (the CI helper runs `java -jar <app>.jar <task> <config>.yaml`, where `<task>` is exactly the Dropwizard command
  name). Determine old vs new name from git history and flag the CI change in Step 3B / the output doc. On normal
  `server` startup the container runs `run.sh → server config.yaml`, not the provisioning command.
- Log each migrated class / DAO / service and Guice swap as `code_change`.

---

## Step 3 — Tests & coverage (local JaCoCo) — COVERAGE IS MANDATORY

**All new code must have complete code coverage**, certified locally with JaCoCo.

- **Unit tests** for every new/changed public method.
- **Integration tests where possible.** **Every DAO and service-layer method that calls DynamoDB MUST be
  integration-tested** against DynamoDB Local (via the `dynamo-integration-test` infra / `BaseDynamoDbIT`,
  `@Tag("integration")`), asserting the DynamoDB call happens and round-trips as expected. Mirror the existing
  `*DaoIT` patterns in network/auth/registration/booking-bridge/webbl/booking.
- **SQS / SNS** test level → mirror **booking** and **network** (inspect their `*MessagingClient*`, `*Notification*`,
  `*Sns*`, processor tests first; do not add new live SQS/SNS integration tests if the reference modules don't have
  them — match their level, typically unit tests mocking `MessagingClient`/`NotificationService`).
- **Email / SES** test level → mirror **booking** and **auth**.
- **S3** test level → mirror **booking**.
- **Conventions:** AssertJ (`assertThat(...)`), `@Nested` for grouping, `@ParameterizedTest`
  (`@ValueSource`/`@CsvSource`/`@MethodSource`) wherever multiple inputs apply.
- **Covering Guice modules / factories / the table-admin command that build AWS SDK clients** (learned on
  value-added-service): the cloud-sdk factories (`NotificationClientFactory.createDefaultClient`,
  `DynamoRepositoryFactory.createEnhancedRepository`, `BaseDynamoDbConfig.toClientConfigBuilder`) build clients
  **without any network call**, so their happy paths are unit-testable **offline**. `NotificationService`
  construction needs no setup (region hardcoded, lazy creds). The DynamoDB paths validate credentials, so provide
  **dummy static credentials via system properties** in a `@BeforeEach`/`@AfterEach` (set/restore
  `aws.accessKeyId`, `aws.secretAccessKey`, `aws.region`) — resolved by the default provider chain with no network.
  This lifts config-module / table-command coverage from ~40–75% to ~90–100%. Also assert converter
  `type()`/`attributeValueType()`.
- **Optional (null) attribute round-trip** — for every nullable attribute persisted via a custom `AttributeConverter`,
  add a DynamoDB-Local IT that saves the entity with that attribute **absent** and asserts the raw item omits it
  (proves the null-returning converter, per Constraint 16 — guards against `ValidationException: Supplied
  AttributeValue is empty`).

Certify coverage with JaCoCo locally and record the numbers:

```bash
mvn -pl watermill-publisher/watermill-booking -am clean verify      # runs unit + integration tests and the JaCoCo report
# JaCoCo report: watermill-publisher/watermill-booking/target/site/jacoco/index.html  (and per-submodule target/site/jacoco/*)
```

Inspect the JaCoCo report and confirm **all new/changed code is fully covered**. If any new code is uncovered, add
tests until it is. Log coverage results (`test_result`) and the report path in the output doc.

**Record passing test commands + an accurate test-count summary (Constraint 14).** In the output doc, list **every**
unit-test and integration-test command that passes (e.g. `mvn -pl watermill-publisher/watermill-booking -am test`,
`mvn -pl watermill-publisher/watermill-booking -am verify`, any `-pl <submodule>` runs), each with a one-line descriptive comment. Then give
an **accurate count of tests run** — unit and integration separately. If more than one test runner is in play
(e.g. **JUnit** via surefire/failsafe and **TestNG**), report the counts **per runner**, taken from the actual
reports:

```bash
# JUnit/TestNG surefire = unit, failsafe = integration; count the result XMLs and tally the suite headers:
find watermill-booking -path '*/target/surefire-reports/*.xml' | wc -l   # unit report files
find watermill-booking -path '*/target/failsafe-reports/*.xml' | wc -l   # integration report files
# Tally tests/failures/errors/skipped from the <testsuite ...> headers (covers JUnit AND TestNG surefire output):
grep -rhoE 'tests="[0-9]+"[^>]*skipped="[0-9]+"' watermill-booking/**/target/*-reports/*.xml
```

Summarize, e.g.: "JUnit: 142 unit + 18 integration; TestNG: 7 unit — total 167, 0 failures, 0 errors". Log the
summary (`test_result`).

---

## Step 3B — Live AWS verification (DynamoDB schema parity + ECS deployment + Dropwizard command-name / CI)

Using the cluster/service/task and AWS-profile details supplied in the **Goal Overview**, verify the live
environment and record findings in the output doc (its own section). Do this read-only; do not mutate any table.

**(a) DynamoDB schema parity across environments.** Log in with the INT profile for INT, and the QA profile for
QA/CVT/PROD (switch profiles as the Goal Overview specifies). For every `watermill-booking` table, in every env, capture the
key schema, attribute definitions, GSIs (name / key / projection / throughput), and TTL + stream settings:

```bash
aws sts get-caller-identity --profile <profile>                       # confirm account before each batch
aws dynamodb describe-table        --table-name <env-prefix>_<Table> --profile <profile> --region us-east-1
aws dynamodb describe-time-to-live --table-name <env-prefix>_<Table> --profile <profile> --region us-east-1
```

- Confirm the live schema **matches the v2 entity annotations** (partition/sort key, each GSI name + projection,
  throughput) and the per-env table prefix derivation. Flag any mismatch.
- **TTL / stream divergence rule:** if TTL or stream settings differ between environments, **the higher environment
  (QA/CVT/PROD) wins** — do NOT add `@TTL`/`@Stream` (or change config) to match a lower env. Since the table-admin
  command only touches TTL/streams when the entity is annotated, leaving the annotation off preserves each env's
  existing setting (nothing overridden). Document the divergence in its **own section**.

**(b) ECS deployment health.** From the Goal Overview's cluster/service/task, confirm the service is deployed and
running, and that the container booted all AWS services cleanly. You do this when prompted specifically. In local environment 
runs you can check if all AWS services started up and application startup completed. Local environment cannot deploy to AWS. That happens only after Jenkins CI build:

```bash
aws ecs describe-services --cluster <cluster> --services <service> --profile <profile> --region us-east-1 \
  --query "services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount,taskDef:taskDefinition,deployments:deployments[].{rollout:rolloutState,status:status}}"
aws ecs describe-services --cluster <cluster> --services <service> --profile <profile> --region us-east-1 \
  --query "services[0].events[0:5].[createdAt,message]" --output text            # expect "reached a steady state"
aws ecs describe-task-definition --task-definition <taskDef> --profile <profile> --region us-east-1 \
  --query "taskDefinition.containerDefinitions[0].{logDriver:logConfiguration.logDriver,options:logConfiguration.options,command:command,healthCheck:healthCheck}"
# Then read the deployed container startup logs from the awslogs group/prefix and confirm the cloud-sdk AWS wiring
# booted (Dynamo repository, SNS/SQS/SES/S3 clients) with 0 ERROR/Exception, plus the ELB health-check 200s:
aws logs get-log-events --log-group-name <awslogs-group> \
  --log-stream-name "<prefix>/<container>/<taskId>" --profile <profile> --region us-east-1 --start-from-head --limit 200 --query "events[].message" --output text
```

- ECS container `healthStatus: UNKNOWN` is expected when the task def has `healthCheck: null` — not a failure;
  confirm health instead via the ELB `GET .../services/ping → 200` lines in the logs and the service reaching
  steady state. `elbv2:DescribeTargetHealth` may be `AccessDenied` on a dev SSO role — note it, don't treat as failure.

**(c) Dropwizard command-name / CI `$task`.** Determine the module's pre-upgrade vs post-upgrade table-admin command
name and whether the deploy `$task` must change (Step 2 rule):

```bash
git --no-pager show origin/develop:watermill-booking/**/<OldTableCommand>.java | Select-String 'extends |super\('   # old name
# Bespoke CreateTables anywhere in this module's history?
git --no-pager log --all --pretty=format: --name-only | Select-String "watermill-booking/.*CreateTables.*\.java" | Sort-Object -Unique
# If a file was deleted, read the removed super("...") from its last (deletion) commit:
git --no-pager show <commit> -- <path> | Select-String '^\-.*super\("'
```

If old = `create-tables` and new = `dynamo-create`, **flag that the `watermill-booking` deploy/CI `$task` must change**
`create-tables → dynamo-create` (jenkins-config, outside this repo). If both are `dynamo-create`, state explicitly
that no CI change is needed. Log all commands + findings (Constraint 12).

---

## Step 4 — Document cloud-sdk library gaps

If anything in `cloud-sdk-api` / `cloud-sdk-aws` is missing for `watermill-booking`'s needs, maintain a single, actionable
**"cloud-sdk gaps"** section in the output doc. For each gap give: the legacy capability, the cloud-sdk shortfall
(with evidence), the workaround used in `watermill-booking`, and a **concrete proposed enhancement** to
`cloud-sdk-api`/`cloud-sdk-aws` (the exact method/builder to add). Summarize options and trade-offs. Log gaps as
`finding`. If no gaps are found, state so explicitly.

---

## Step 5 — Full verify, commit (amend), document

```bash
mvn -pl watermill-publisher/watermill-booking -am clean verify     # unit + integration (DynamoDB Local) — BUILD SUCCESS, 0 failures
```

Root-cause and FIX any failure (related or not); add a reproducing test for any bug before fixing; iterate until
green with full coverage.

Fold everything into the **one** outgoing commit (no design-doc/ticket reference in the message — Constraint 9):

```bash
git add -A
git commit --amend -m "ION-16380: watermill-booking AWS SDK 2.x — migrate watermill-booking S3/SQS/SNS/DynamoDB to cloud-sdk (AWS SDK 2.x); mandatory commons 1.0.28-SNAPSHOT; OWASP pre/post scans; VS Code run configs; live AWS DynamoDB parity + AWS service-details tables"
git log --oneline develop..HEAD            # exactly 1 line
git log -1 --format="%B"                   # contains ION-16380, no docs/* path or ticket URL
git status -sb                             # clean, nothing pushed
```

Do **not** push.

**Document** all of today's work in `watermill-publisher/watermill-booking/docs/2026-07-28-watermill-booking-aws-upgrade-refactor.md` — including **every search/grep/git/analysis command with a clear
descriptive comment** (Constraint 12) for reproducibility, linking the reference docs.
Suggested structure:
1. **Summary** — goals, branch, single-commit outcome, model (Claude Opus 4.8, 1M), rebase result (if any).
2. **Rebase** — whether needed, new base SHA, each conflict and how develop's change was preserved + the upgrade re-applied.
3. **Implementation** — every class/DAO/service migrated, Guice factory swaps, config blocks added, backward-compat evidence, legacy deps removed.
4. **Tests & coverage** — unit + integration (DynamoDB/SQS/SNS/SES/S3) added, reference-module alignment, JaCoCo
   coverage numbers + report path, **every passing unit/integration test command**, and an **accurate test-count
   summary (unit + integration, per runner if JUnit and TestNG are both used)**.
5. **Live AWS verification (Step 3B)** — DynamoDB schema parity per env (key/GSI/throughput vs entity annotations),
   any TTL/stream divergence in its **own subsection** (higher-env-wins, nothing overridden), ECS deployment health
   (service steady state + container AWS boot from logs), and the Dropwizard command-name / CI `$task` finding.
6. **cloud-sdk gaps** — gaps + concrete proposed enhancements (or "none found").
7. **Command log** — every search/grep/git/analysis/build/aws command run, each with a one-line descriptive comment.
8. **Build / packaging results** — `mvn verify` output.
9. **Token-usage** — `session_usage_report` result for this session (or note if the hook didn't fire).
10. **References** — ION-16380, reference files/modules/docs.

Keep the doc updated as you proceed; log doc creation (`progress`). This doc is internal reference only — **do not**
cite it from code comments or the commit message (Constraint 9).

---

## Step 6 — Handoff

```bash
git log --oneline develop..HEAD            # exactly 1 commit, message contains ION-16380
git status -sb                             # clean working tree, nothing pushed
```

- Update `watermill-publisher/watermill-booking/docs/2026-07-28-watermill-booking-aws-upgrade-refactor.md` with the final commit hash + full test/build/coverage results and the command log.
- `session_add_context` final summary (`progress`); cross-link any prior sessions; keep status `active` (user
  reviews before push).
- `session_usage_report` for this session to confirm token-usage telemetry was captured; note it in the doc.
- Tell the user it is ready for review and **not pushed** (they will ask you to push).

---

## Definition of Done

- [ ] Session resumed/created with full traceability (decisions, code changes, findings, tests, model info,
      command log); token-usage telemetry confirmed via `session_usage_report`.
- [ ] **(Constraint 5)** Rebased onto the latest develop if new `watermill-booking` commits landed; develop's functional
      changes preserved (incoming-wins), AWS-upgrade changes re-applied on top; exactly one outgoing commit.
- [ ] **(Goals)** Every goal implemented, mirroring the reference modules; AWS interactions on cloud-sdk;
      backward-compatible wire/disk formats proven by tests.
- [ ] **(Coverage)** `mvn -pl watermill-publisher/watermill-booking -am clean verify` BUILD SUCCESS; all new code fully covered per local
      JaCoCo; every DynamoDB DAO/service method integration-tested; SQS/SNS aligned to booking/network, SES to
      booking/auth, S3 to booking.
- [ ] **(Constraint 14)** Every passing unit/integration test command logged in `watermill-publisher/watermill-booking/docs/2026-07-28-watermill-booking-aws-upgrade-refactor.md` with an accurate
      test-count summary (unit + integration, per runner if JUnit and TestNG are both used).
- [ ] **(cloud-sdk gaps)** Documented with concrete proposed enhancements (or "none found").
- [ ] **(Step 3B)** Live DynamoDB schema parity verified per env vs the v2 entity annotations; any TTL/stream
      divergence flagged in its own section (higher-env-wins, nothing overridden); ECS deployment confirmed running
      with the container's AWS services booted; Dropwizard command-name / CI `$task` change assessed and flagged.
- [ ] **(Constraint 9)** No design-doc/ticket references in code comments or the commit message.
- [ ] **(Constraint 10)** No shortcuts — best implementation/design throughout.
- [ ] **(Constraint 12 / 13)** Every search/grep/git/kb/analysis command logged with a descriptive comment in
      `watermill-publisher/watermill-booking/docs/2026-07-28-watermill-booking-aws-upgrade-refactor.md`; kb tooling (`kb_grep` / `kb_find_files`) used for reference lookups.
- [ ] `watermill-publisher/watermill-booking/docs/2026-07-28-watermill-booking-aws-upgrade-refactor.md` written with all of the above.
- [ ] Exactly **one** outgoing commit, message contains `ION-16380`, **not pushed**.
