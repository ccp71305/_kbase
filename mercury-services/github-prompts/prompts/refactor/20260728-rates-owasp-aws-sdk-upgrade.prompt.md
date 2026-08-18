---
name: 20260728-rates-owasp-aws-sdk-upgrade
description: >
  AWS-SDK-2.x (cloud-sdk) refactor / functional change on the rates module (ION-16110).
  Goals: OWASP dependency-check (pre + post) on latest develop, upgrade to commons 1.0.28-SNAPSHOT,
  migrate AWS interactions to cloud-sdk mirroring booking/network/auth/visibility, VS Code run configs,
  boot-check on latest develop before implementing, full unit coverage, live DynamoDB schema parity +
  ECS deployment verification. Rebase onto the latest develop preserving develop's functional changes
  (incoming-wins on conflicts, then re-apply the AWS-upgrade changes), keep the OWASP fix and AWS upgrade
  as separate commits where possible (single combined commit only if a compile-time dependency forces it),
  each referencing ION-16110, full local mvn clean verify with complete JaCoCo coverage on all new code,
  unit + integration tests (DynamoDB/SQS/SNS/SES) mirroring the reference modules, document cloud-sdk gaps,
  and log every search/grep/git/aws/analysis command. Do not push.
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

# rates — AWS SDK 2.x (cloud-sdk) Refactor — ION-16110

> **Jira:** ION-16110 (used for the commit message / session tags only — per goals, do NOT connect to Jira or Confluence via the MCP context server for this work)
> **Read first (reference material — all files):**
> - C:\Users\arijit.kundu\projects\mercury-services\rates\docs\2026-06-30-rates-aws2x-DESIGN-claude.md

## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the feature branch `feature/ION-16110-rates-owasp-aws-upgrade`. If it **already
   exists**, check it out and rebase it onto the latest develop (Step 1), keeping the outgoing commit(s) per Constraint
   3. If it does **not** exist, pull the latest develop and **create `feature/ION-16110-rates-owasp-aws-upgrade` from
   the latest develop** before any work (Step 0).
2. **DO NOT PUSH** — Never `git push` / `--force` / `--force-with-lease`. The user reviews locally and pushes
   manually, and will explicitly ask you to push after review.
3. **COMMIT POLICY (per goals)** — Keep the **OWASP fix** and the **AWS upgrade** as **two separate commits** where
   possible. If a compile-time dependency makes that impossible (e.g. the commons bump removes packages the current
   code imports, forcing the migration to compile), fall back to **one single commit** covering both. Whichever the
   outcome, every commit message MUST contain `ION-16110`, and the branch must sit on top of the **latest** develop.
4. **COMMIT MESSAGE** — Every commit message MUST contain the Jira key `ION-16110` (required by the Bitbucket
   "git control freak" hook).
5. **LATEST DEVELOP IS THE FUNCTIONAL BASELINE (PRIORITY)** — develop's latest commits are **functional changes**
   and take **priority**. If new commits landed on develop that touch `rates/`, rebase onto the latest develop first
   (Step 1). On any conflict between develop and the AWS-upgrade changes, **take the incoming develop change first**,
   then **adjust and re-apply the AWS-SDK-upgrade changes on top** so the upgrade conforms to develop. The rebase must
   in **no way** drop, weaken, or alter develop's incoming functional behavior. Never sacrifice a functional change to
   keep an upgrade change.
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
   Prefer the proven reference approach over any divergent one already in `rates`.
8. **ALL TESTS MUST PASS** — Unit + integration (incl. DynamoDB Local). Everything compiles and keeps/raises
   coverage. Do not weaken or `@Disabled` a test to go green — root-cause and fix. If a test breaks (related or
   not), log it in session context, find the root cause, and FIX it; add a reproducing test for any bug first.
9. **NO DESIGN-DOC / TICKET REFERENCES IN CODE** — Do not reference docs/`*.md`, Jira, or Confluence URLs in code
   comments, javadoc, or the commit message. Code comments must stand on their own.
10. **NO SHORTCUTS** — Always take the best implementation/design approach. If the correct fix is a larger
    refactor, do it in incremental, test-verified steps. No quick wins that compromise correctness, backward
    compatibility, or code quality.
11. **MODEL** — Use Claude Opus 4.8 with the 1M context window. Log this in session context (`model_info`).
12. **LOG EVERY COMMAND** — Every search / grep / `git` / `aws` / build / analysis command you run MUST be captured
    in the output doc (and key ones in session context) **with a clear descriptive comment** explaining why it was
    run and what it found, so the work is reproducible and reusable later (see Step 5 + the command-log rule).
13. **USE THE KNOWLEDGE BASE** — The mcp-context-server kb tooling is configured and indexes both this repo and
    `mercury-services-commons` (so you can read the cloud-sdk-api / cloud-sdk-aws sources directly). Use `kb_grep`
    and `kb_find_files` to locate reference implementations and usages (both verified working). The semantic
    `kb_search` may return empty if its index is not built — if so, fall back to `kb_grep` / `kb_find_files`. Log
    each kb query and what it revealed (Constraint 12).
14. **LOG PASSING TEST COMMANDS + TEST COUNTS** — Record in the output doc every unit-test and integration-test
    command that passes, and an accurate count of tests run (unit + integration). If multiple test runners are
    used (e.g. JUnit and TestNG), summarize the counts **per runner** (see Step 3 + Step 5).
15. **BUILD DISCIPLINE / MACHINE-SLOWNESS HANDLING** (learned on value-added-service ION-16110) —
    - **Do not run multiple `mvn` builds concurrently.** Antivirus scans + a shared machine make parallel Maven runs
      stall. Run one build at a time; wait for it to finish before starting the next.
    - **Never pipe a live `mvn` run straight into `Select-String`/`findstr`.** The pipe buffers all output until the
      JVM exits, so a long build looks like a hang. Instead `... | Tee-Object -FilePath $env:TEMP\rates-verify.log`,
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
1. `session_list` — look for an existing session for `ION-16110` / `rates` / `rates-aws-upgrade`.
2. If found → `session_get` and **resume**; cross-link the prior session.
3. If none → `session_create`:
   - name: `rates-owasp-aws-sdk-upgrade-20260728`
   - project: `mercury-services`
   - tags: `["rates", "ION-16110", "aws-sdk-upgrade", "owasp-aws-sdk-upgrade", "in-progress"]`

**DURING** work — `session_add_context` after every significant action:
- Rebase decision + backup branch/tag + new tip SHA → `decision` / `progress`
- Root causes + fixes → `finding` / `code_change`
- Each class/DAO/service migrated + Guice factory swap → `code_change`
- Tests added + results, coverage numbers → `test_result`
- cloud-sdk library gaps → `finding`
- Compilation / `mvn verify` / packaging results → `test_result`
- Live DynamoDB parity + ECS deployment + command-name findings → `finding`
- Blockers → `blocker`
- Model used → `model_info`
- Key search/grep/git/aws/analysis commands + what they revealed → `finding` (also mirror into the output doc)

**Token-usage telemetry (verified working 2026-06-30).** The mcp-context-server captures token usage automatically via
harness-level hooks — Copilot CLI `agentStop` (`.github/hooks/telemetry.json` → `scripts/copilot_telemetry_hook.py`)
and Claude Code `Stop` (`.claude/settings.json` → `scripts/claude_telemetry_hook.py`). Therefore:
- **Do NOT fabricate or estimate usage.** The model cannot see its own usage block (it goes to the harness, not the
  model). Only call `session_record_usage` if you have **real** provider usage numbers (`input_tokens`,
  `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `model`); otherwise rely on the installed
  hooks and skip.
- **At the end** (and if context gets large), call `session_usage_report` for this session to confirm usage was
  captured, and optionally `telemetry_report` for the portfolio view; note the result in the output doc. If
  `record_count = 0`, flag that the harness hook may not have fired (do not back-fill with guesses).

If context exceeds **85%**: persist a full summary via `session_add_context` (`progress`), write all findings into the
output doc immediately, note where you left off, then continue/hand off per the base protocol.

Use the MCP context server for git operations if helpful, and for **knowledge-base** access (`kb_grep` /
`kb_find_files` over this repo + `mercury-services-commons`; fall back from the semantic `kb_search` to `kb_grep` /
`kb_find_files` if its index is empty). Per the goals, do **not** connect to Jira or Confluence via the MCP context
server for this work.

---

## Goal Overview

Accomplish the following on the `rates` module, all backward-compatible with 1.x, all tests green with full JaCoCo
coverage on new code, in separate OWASP + AWS commits (or one combined commit if compile-time deps force it — see
Constraint 3) referencing `ION-16110`, with no design-doc references in code/commits:

- Run OWASP dependency-check **first** on the latest develop code for this module (baseline scan before any change).
  dependency-check is installed. First build the shaded jar, then scan it (substitute the actual jar name after the
  `mvn package` build):
  ```powershell
  mvn package -pl rates -DskipTests -am
  dependency-check --project rates --scan ./<jar name>.jar --out owasp --suppression ../suppressions.xml --nvdApiKey $env:NVD_API_KEY
  ```
- Create **VS Code run configs** for this module **first**.
- Make sure the application **boots up fine with the latest code in develop** first. If it does not, **flag this and
  do NOT proceed** with implementation.
- If the application boots up fine, create the new feature branch and start implementing first the OWASP fix
  (commons `1.0.28-SNAPSHOT` should work) and then the AWS upgrade based on the design and plan already created.
- Upgrade to `1.0.28-SNAPSHOT` version of `mercury-services-commons` (commons dependency).
- Keep the OWASP fix and the AWS upgrade as **separate commits** if possible; if a compile-time dependency forces it,
  use **one single commit** for both (Constraint 3).
- **rerun** dependency-check, compare CVEs against the baseline, and summarize the pre/post CVE delta in the output
  document.
- Copy **both** the pre- and post-implementation OWASP scans into `C:\temp\latest-dep-chk-reports\rates`.
- Refer to **booking**, **network**, **auth**, and **visibility** for the AWS upgrade changes (reference templates).
- Create a **detailed design & plan** for the upgrade in the same output document, after the OWASP changes, before
  implementing the AWS upgrade.
- All code changes must have **unit test coverage**.
- Make sure **all tests PASS**, **no shortcuts**, and the application boots up fine.
- No need to connect to Jira or Confluence using the MCP context server for this work.

**Live-environment verification inputs (used in Step 3B).** Log in to AWS via the CLI and confirm the DynamoDB table
definitions in **INT, QA, CVT and PROD**. Use the **INT** profile for INT, and the **QA** profile for QA/CVT/PROD.
**If any TTL or streaming attributes differ, the higher-environment (QA/CVT/PROD) configuration stands** — do NOT
change from what QA/CVT/PROD have; flag any differences in the document in its own separate section.

- **INT** (account `081020446316`): profile `081020446316_INTTRA-Dev-Engg`
  - Deploy: `Rates-dev 26.06.003 to ANEINWEBSVC-001`; task def `Rates-latest-dev-Task.json` (`Rates-latest-dev-Task:7`)
  - service `arn:aws:ecs:us-east-1:081020446316:service/ANEINWEBSVC-001/Rates-dev` (`Rates-dev`)
  - cluster `arn:aws:ecs:us-east-1:081020446316:cluster/ANEINWEBSVC-001`
- **QA/CVT/PROD** (account `642960533737`): profile `642960533737_INTTRA2-QATeam`
  - Deploy: `Rates-qa 26.05.002 to ANEQAWEBSVC-001`; task `Rates-latest-qa-Task:5`
  - service `arn:aws:ecs:us-east-1:642960533737:service/ANEQAWEBSVC-001/Rates-qa` (`Rates-qa`)
  - cluster `arn:aws:ecs:us-east-1:642960533737:cluster/ANEQAWEBSVC-001`
  - The INT profile credentials are already in the terminal. To switch to QA, add the `[642960533737_INTTRA2-QATeam]`
    static credentials (aws_access_key_id / aws_secret_access_key / aws_session_token) to the local `~/.aws/credentials`
    file **only** (never commit them). If the config-file profile shadows the static keys via `sso_session`, add a
    distinct static-only profile name (e.g. `qa-team-static`) and use that. QA SSO tokens expire — re-auth or refresh
    the static keys as needed.

---

## Step 0 — Orient, Resolve Branch & Back Up

First make sure develop is current, then resolve the branch — **create it from the latest develop if it does not
exist**, or back it up if it does.

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git fetch origin
git checkout develop && git pull --ff-only origin develop      # latest develop is the functional baseline

# Does the feature branch already exist (locally or on origin)?
git rev-parse --verify feature/ION-16110-rates-owasp-aws-upgrade 2>/dev/null || git ls-remote --exit-code --heads origin feature/ION-16110-rates-owasp-aws-upgrade
```

**IMPORTANT ordering per goals:** the boot-check on the latest develop and the baseline OWASP scan happen **before**
you create the feature branch. Create/rebase the branch only once develop boots cleanly.

- **If `feature/ION-16110-rates-owasp-aws-upgrade` does NOT exist** → create it from the latest develop and start fresh
  (only after the develop boot-check passes):

```bash
git checkout -b feature/ION-16110-rates-owasp-aws-upgrade develop          # branch off the just-pulled latest develop
```

- **If `feature/ION-16110-rates-owasp-aws-upgrade` already exists** → check it out, back it up, and proceed to Step 1:

```bash
git checkout feature/ION-16110-rates-owasp-aws-upgrade
git status --short
git log --oneline develop..HEAD             # record current outgoing commit(s)
git rev-parse HEAD                          # record current tip
git branch feature/ION-16110-rates-owasp-aws-upgrade-backup-20260728   # safety backup before rebase
git tag    ION-16110-pre-refactor-backup-20260728
```

- Read the reference material listed above (the rates design doc) and the reference modules' cloud-sdk wiring
  (booking/network for SQS/SNS, booking/auth for SES, booking for S3, booking/network/registration for DynamoDB) —
  these are your templates. Use `kb_grep` / `kb_find_files` to open the cloud-sdk-api / cloud-sdk-aws sources from
  `mercury-services-commons` as needed. Reference the completed **value-added-service** upgrade
  (`value-added-service/docs/2026-07-24-vas-aws-upgrade.md`) for the DynamoSupport-port pattern, offline
  client-construction coverage technique, and the command-name / CI `$task` analysis.
- Log the branch decision (created-from-develop vs existing+backed-up), the backup branch/tag + tip SHA, and the key
  reference files in session context (`progress` / `finding` / `decision`).

---

## Step 1 — Rebase onto latest develop (develop's functional changes take PRIORITY)

If you **just created `feature/ION-16110-rates-owasp-aws-upgrade` from the latest develop** in Step 0, it is already
current — skip the rebase and go to Step 2. Otherwise (the branch pre-existed), bring it onto the latest develop:

```bash
git fetch origin
git log --oneline HEAD..origin/develop -- rates/    # any new commits touching this module on develop?
```

- If there are **no** new commits touching `rates/` on `origin/develop`, skip the rebase and continue.
- If there **are** new commits, rebase the outgoing commit(s) onto the latest develop:

```bash
git rebase origin/develop
```

**Conflict-resolution rule (Constraint 5):** develop's commits are **functional changes** and win. For every conflict,
**take the incoming develop change first**, then **adjust and re-apply the AWS-SDK-upgrade change on top** so the
upgrade conforms to develop's new code. Never drop or alter develop's functional behavior to preserve an upgrade change.

```bash
mvn -f rates/pom.xml clean verify     # MUST be BUILD SUCCESS after the rebase, before any new work
```

After the rebase + conflict resolution, confirm the outgoing commit(s) per Constraint 3 sit on top of the latest
develop (squash/`--amend` as needed):

```bash
git log --oneline develop..HEAD            # 1 or 2 commits per Constraint 3, message(s) contain ION-16110
```

Log the rebase outcome (new base SHA, conflicts resolved, how each was reconciled) in session context
(`decision` / `progress`) and in the output doc.

---

## Step 2 — Implement the goals

Implement every goal from the **Goal Overview** on `rates`, in incremental, test-verified steps, mirroring the
reference modules (Constraint 7). For each unit of work:
- Use `git_log`, the kb tooling (`kb_grep` / `kb_find_files`; fall back from the semantic `kb_search` if its index is
  empty), and `grep` to find all usages and recent changes before editing; **log each command + what it revealed**
  (Constraint 12 / 13).
- Migrate AWS interactions to the `cloud-sdk-api` interfaces (implemented by `cloud-sdk-aws`), swapping legacy Guice
  bindings for the cloud-sdk factories and adding the matching config blocks to each affected `config.yaml`, exactly
  as the reference modules do.
- Keep every wire/disk format byte/shape-compatible with 1.x (Constraint 6); prove it with round-trip tests. If any
  attribute is stored via a custom `DynamoSupport`-style class-tagged JSON encoding, **port that utility into the
  module** (as value-added-service did) so the encoding stays byte-identical after `dynamo-client` is removed.
- Remove legacy AWS SDK v1 deps/imports only once all references are gone (keep any genuinely still required, e.g.
  DynamoDB Local test runtime, lambda runtime event models).
- **Dropwizard DynamoDB table-admin command** — migrate the module's table-provisioning command to extend the
  cloud-sdk `DynamoDbAdminCommand` (mirrors booking/booking-bridge/visibility), deriving the table/GSI/TTL from the
  v2 `@DynamoDbBean`/`@Table`/`@GsiConfig`/`@DynamoDbSecondaryPartitionKey` annotations. **Watch the registered
  command name:** `DynamoDbAdminCommand` (and the old dynamo-client `AbstractDynamoCommand`) register
  `super("dynamo-create", …)`. If the module's **pre-upgrade** command was a bespoke `CreateTables extends
  ConfiguredCommand` with `super("create-tables", …)` (as booking / booking-bridge / visibility had), the CLI verb
  changes `create-tables` → `dynamo-create`, and the module's **deploy/CI `$task` argument must be updated to match**
  (the CI helper `mercury-run-docker-task.sh <task>` runs `java -jar <app>.jar <task> <config>.yaml`, where `<task>`
  is exactly the Dropwizard command name). Determine old vs new name from git history and flag the CI change in
  Step 3B / the output doc. On normal `server` startup the container runs `run.sh → server config.yaml`, not the
  provisioning command.
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
  **dummy static credentials via system properties** in a `@BeforeEach`/`@AfterEach` (set/restore `aws.accessKeyId`,
  `aws.secretAccessKey`, `aws.region`) — resolved by the default provider chain with no network. This lifts
  config-module / table-command coverage from ~40–75% to ~90–100%. Also assert converter
  `type()`/`attributeValueType()`.
- **Optional (null) attribute round-trip** — for every nullable attribute persisted via a custom `AttributeConverter`,
  add a DynamoDB-Local IT that saves the entity with that attribute **absent** and asserts the raw item omits it
  (proves the null-returning converter, per Constraint 16 — guards against `ValidationException: Supplied
  AttributeValue is empty`).

Certify coverage with JaCoCo locally and record the numbers (note: the JaCoCo agents live in the `sonar` profile —
run with `-Pmercury-commons,sonar` so the default profile's `${lombok.version}` etc. stay active):

```bash
mvn -f rates/pom.xml clean verify      # runs unit + integration tests
mvn -pl rates "-Pmercury-commons,sonar" verify "-Dsonar.skip=true"   # produces the JaCoCo report
# JaCoCo report: rates/target/site/jacoco/index.html  (UT: target/jacoco-ut.exec, IT: target/jacoco-it.exec)
```

Inspect the JaCoCo report and confirm **all new/changed code is fully covered**. If any new code is uncovered, add
tests until it is (use the offline-client-construction technique above for Guice modules / commands). Log coverage
results (`test_result`) and the report path in the output doc.

**Record passing test commands + an accurate test-count summary (Constraint 14).** In the output doc, list **every**
unit-test and integration-test command that passes (e.g. `mvn -f rates/pom.xml test`, `mvn -f rates/pom.xml verify`,
any `-pl <submodule>` runs), each with a one-line descriptive comment. Then give an **accurate count of tests run** —
unit and integration separately. If more than one test runner is in play (e.g. **JUnit** via surefire/failsafe and
**TestNG**), report the counts **per runner**, taken from the actual reports.

---

## Step 3B — Live AWS verification (DynamoDB schema parity + ECS deployment + Dropwizard command-name / CI)

Using the cluster/service/task and AWS-profile details in the **Goal Overview**, verify the live environment and
record findings in the output doc (its own section). Read-only; do not mutate any table.

**(a) DynamoDB schema parity across environments.** Log in with the INT profile for INT, and the QA profile for
QA/CVT/PROD. For every `rates` table, in every env, capture key schema, attribute definitions, GSIs
(name / key / projection / throughput), and TTL + stream settings:

```powershell
aws sts get-caller-identity --profile <profile>                       # confirm account before each batch
aws dynamodb describe-table        --table-name <env-prefix>_<Table> --profile <profile> --region us-east-1
aws dynamodb describe-time-to-live --table-name <env-prefix>_<Table> --profile <profile> --region us-east-1
# INT profile: 081020446316_INTTRA-Dev-Engg ; QA/CVT/PROD profile: 642960533737_INTTRA2-QATeam (or qa-team-static)
```

- Confirm the live schema **matches the v2 entity annotations** (partition/sort key, each GSI name + projection,
  throughput) and the per-env table prefix derivation. Flag any mismatch.
- **TTL / stream divergence rule (per goals):** if TTL or stream settings differ between environments, **the higher
  environment (QA/CVT/PROD) wins** — do NOT add `@TTL`/`@Stream` (or change config) to match a lower env. Since the
  table-admin command only touches TTL/streams when the entity is annotated, leaving the annotation off preserves each
  env's existing setting (nothing overridden). Document the divergence in its **own section**.

**(b) ECS deployment health.** From the Goal Overview's cluster/service/task, confirm the service is deployed and
running, and that the container booted all AWS services cleanly:

```powershell
aws ecs describe-services --cluster ANEINWEBSVC-001 --services Rates-dev --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 `
  --query "services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount,taskDef:taskDefinition,deployments:deployments[].{rollout:rolloutState,status:status}}"
aws ecs describe-services --cluster ANEINWEBSVC-001 --services Rates-dev --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 `
  --query "services[0].events[0:5].[createdAt,message]" --output text            # expect "reached a steady state"
aws ecs describe-task-definition --task-definition Rates-latest-dev-Task:7 --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 `
  --query "taskDefinition.containerDefinitions[0].{logDriver:logConfiguration.logDriver,options:logConfiguration.options,command:command,healthCheck:healthCheck}"
# Then read the deployed container startup logs from the awslogs group/prefix and confirm the cloud-sdk AWS wiring
# booted (Dynamo repository, SNS/SQS/SES/S3 clients) with 0 ERROR/Exception, plus the ELB health-check 200s:
aws logs get-log-events --log-group-name <awslogs-group> `
  --log-stream-name "<prefix>/<container>/<taskId>" --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 --start-from-head --limit 200 --query "events[].message" --output text
```

- ECS container `healthStatus: UNKNOWN` is expected when the task def has `healthCheck: null` — not a failure; confirm
  health instead via the ELB `GET .../services/ping → 200` lines in the logs and the service reaching steady state.
  `elbv2:DescribeTargetHealth` may be `AccessDenied` on a dev SSO role — note it, don't treat as failure.

**(c) Dropwizard command-name / CI `$task`.** Determine the module's pre- vs post-upgrade table-admin command name and
whether the deploy `$task` must change (Step 2 rule):

```powershell
git --no-pager show origin/develop:rates/**/<OldTableCommand>.java | Select-String 'extends |super\('   # old name
# Bespoke CreateTables anywhere in this module's history?
git --no-pager log --all --pretty=format: --name-only | Select-String "rates/.*CreateTables.*\.java" | Sort-Object -Unique
# If a file was deleted, read the removed super("...") from its last (deletion) commit:
git --no-pager show <commit> -- <path> | Select-String '^\-.*super\("'
```

If old = `create-tables` and new = `dynamo-create`, **flag that the `rates` deploy/CI `$task` must change**
`create-tables → dynamo-create` (jenkins-config, outside this repo). If both are `dynamo-create`, state explicitly
that no CI change is needed. Log all commands + findings (Constraint 12).

---

## Step 4 — Document cloud-sdk library gaps

If anything in `cloud-sdk-api` / `cloud-sdk-aws` is missing for `rates`'s needs, maintain a single, actionable
**"cloud-sdk gaps"** section in the output doc. For each gap give: the legacy capability, the cloud-sdk shortfall
(with evidence), the workaround used in `rates`, and a **concrete proposed enhancement** to `cloud-sdk-api`/
`cloud-sdk-aws` (the exact method/builder to add). Summarize options and trade-offs. Log gaps as `finding`. If no gaps
are found, state so explicitly.

---

## Step 5 — Full verify, commit, document

```bash
mvn -f rates/pom.xml clean verify     # unit + integration (DynamoDB Local) — BUILD SUCCESS, 0 failures
```

Root-cause and FIX any failure (related or not); add a reproducing test for any bug before fixing; iterate until green
with full coverage.

Assemble the commit(s) per Constraint 3 (no design-doc/ticket reference in the message — Constraint 9):

```bash
# Two-commit path (preferred): commit the OWASP fix, then the AWS upgrade.
git add -A
git commit -m "ION-16110: rates OWASP dependency-check — commons 1.0.28-SNAPSHOT + Jackson pin"
# ... then the AWS upgrade changes ...
git commit -m "ION-16110: rates AWS SDK 2.x (cloud-sdk) upgrade — DynamoDB/SNS/SQS/SES migration + tests"
# Single-commit fallback (only if a compile-time dependency forces it):
#   git commit --amend -m "ION-16110: rates OWASP dependency-check + AWS SDK 2.x (cloud-sdk) upgrade"

git log --oneline develop..HEAD            # 1 or 2 lines per Constraint 3
git log -1 --format="%B"                   # contains ION-16110, no docs/* path or ticket URL
git status -sb                             # clean, nothing pushed
```

Do **not** push.

**Document** all of today's work in `rates/docs/2026-07-24-rates-owasp-aws-upgrade.md` — including **every
search/grep/git/aws/analysis command with a clear descriptive comment** (Constraint 12) for reproducibility, linking
the reference docs. Suggested structure:
1. **Summary** — goals, branch, commit outcome, model (Claude Opus 4.8, 1M), rebase result (if any).
2. **Rebase** — whether needed, new base SHA, each conflict and how develop's change was preserved + the upgrade re-applied.
3. **OWASP dependency-check** — pre-scan (baseline) and post-scan CVE comparison, the delta summary, and confirmation
   both reports were copied to `C:\temp\latest-dep-chk-reports\rates`.
4. **Design plan** — the detailed upgrade design plan created before implementation.
5. **VS Code run configs** — the run configs created for this module.
6. **Develop boot-check** — result of booting the app on the latest develop (pass/fail; if fail, the flag and stop).
7. **Implementation** — every class/DAO/service migrated, Guice factory swaps, config blocks added, backward-compat
   evidence, legacy deps removed, commons bumped to 1.0.28-SNAPSHOT.
8. **Tests & coverage** — unit + integration (DynamoDB/SQS/SNS/SES/S3) added, reference-module alignment, JaCoCo
   coverage numbers + report path, **every passing unit/integration test command**, and an **accurate test-count
   summary (unit + integration, per runner if JUnit and TestNG are both used)**.
9. **Live AWS verification (Step 3B)** — DynamoDB schema parity per env (key/GSI/throughput vs entity annotations),
   any TTL/stream divergence in its **own subsection** (higher-env-wins, nothing overridden), ECS deployment health
   (service steady state + container AWS boot from logs), and the Dropwizard command-name / CI `$task` finding.
10. **cloud-sdk gaps** — gaps + concrete proposed enhancements (or "none found").
11. **Command log** — every search/grep/git/aws/analysis/build command run, each with a one-line descriptive comment.
12. **Build / packaging results** — `mvn verify` output.
13. **Token-usage** — `session_usage_report` result for this session (or note if the hook didn't fire).
14. **References** — ION-16110, reference files/modules/docs.

Keep the doc updated as you proceed; log doc creation (`progress`). This doc is internal reference only — **do not**
cite it from code comments or the commit message (Constraint 9).

---

## Step 6 — Handoff

```bash
git log --oneline develop..HEAD            # 1 or 2 commits per Constraint 3, message(s) contain ION-16110
git status -sb                             # clean working tree, nothing pushed
```

- Update `rates/docs/2026-07-24-rates-owasp-aws-upgrade.md` with the final commit hash(es) + full test/build/coverage
  results and the command log.
- `session_add_context` final summary (`progress`); cross-link any prior sessions; keep status `active` (user reviews
  before push).
- `session_usage_report` for this session to confirm token-usage telemetry was captured; note it in the doc.
- Tell the user it is ready for review and **not pushed** (they will ask you to push).

---

## Definition of Done

- [ ] Session resumed/created with full traceability (decisions, code changes, findings, tests, model info,
      command log); token-usage telemetry confirmed via `session_usage_report`.
- [ ] **(Develop boot-check)** App boots on the latest develop; if it does not, flagged and implementation stopped.
- [ ] **(OWASP)** Pre- and post-implementation dependency-check scans run, CVE delta summarized, both reports copied
      to `C:\temp\latest-dep-chk-reports\rates`.
- [ ] **(commons)** Upgraded to `1.0.28-SNAPSHOT` of `mercury-services-commons`.
- [ ] **(VS Code)** Run configs created for the module.
- [ ] **(Design plan)** Detailed upgrade design plan authored before implementation.
- [ ] **(Constraint 5)** Rebased onto the latest develop if new `rates` commits landed; develop's functional changes
      preserved (incoming-wins), AWS-upgrade changes re-applied on top.
- [ ] **(Constraint 3)** OWASP + AWS as separate commits where possible, else one combined commit; each contains
      `ION-16110`; branch on top of the latest develop.
- [ ] **(Goals)** Every goal implemented, mirroring the reference modules; AWS interactions on cloud-sdk;
      backward-compatible wire/disk formats proven by tests.
- [ ] **(Coverage)** `mvn -f rates/pom.xml clean verify` BUILD SUCCESS; all new code fully covered per local JaCoCo;
      every DynamoDB DAO/service method integration-tested; SQS/SNS aligned to booking/network, SES to booking/auth,
      S3 to booking.
- [ ] **(Constraint 14)** Every passing unit/integration test command logged in the output doc with an accurate
      test-count summary (unit + integration, per runner if JUnit and TestNG are both used).
- [ ] **(cloud-sdk gaps)** Documented with concrete proposed enhancements (or "none found").
- [ ] **(Step 3B)** Live DynamoDB schema parity verified per env vs the v2 entity annotations; any TTL/stream
      divergence flagged in its own section (higher-env-wins, nothing overridden); ECS deployment confirmed running
      with the container's AWS services booted; Dropwizard command-name / CI `$task` change assessed and flagged.
- [ ] **(Constraint 9)** No design-doc/ticket references in code comments or the commit message.
- [ ] **(Constraint 10)** No shortcuts — best implementation/design throughout.
- [ ] **(Constraint 12 / 13)** Every search/grep/git/aws/kb/analysis command logged with a descriptive comment in the
      output doc; kb tooling (`kb_grep` / `kb_find_files`) used for reference lookups.
- [ ] `rates/docs/2026-07-24-rates-owasp-aws-upgrade.md` written with all of the above.
- [ ] Commit(s) per Constraint 3, message(s) contain `ION-16110`, **not pushed**.
