---
name: 20260716-visibility-inbound-ses-startup-issue
description: >
  Issue-fix / defect resolution on the visibility module (ION-12316). Analyze the reported issue, investigate
  the module, review related git commits, review referenced cloud-sdk library implementations, consult the
  knowledge base, and — where useful — inspect AWS logs (read-only) for the 081020446316_INTTRA-Dev-Engg profile to find the
  ROOT CAUSE, then implement a proper fix (which may involve refactoring). Reproduce the issue with a failing test
  first where applicable, keep exactly one unpushed outgoing commit referencing ION-12316, full local
  mvn clean verify with complete coverage on all new/changed code, and document the full analysis, root cause, and
  changes in visibility/docs/2026-07-16-ION-12316-inbound-ses-startup-issue.md. Do not push.
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

# visibility — Issue Fix — ION-12316

> **Jira:** ION-12316
> **Workspace:** mercury-services (C:\Users\arijit.kundu\projects\mercury-services)
> **AWS profile (read-only):** 081020446316_INTTRA-Dev-Engg
> **ECS cluster:** ANEINVIS-002
> **CloudWatch log group:** inttra-ecs-logs
> **Read first (reference material — all files):**
>   - visibility\docs\visibility-architecture-design-claude.md
>   - visibility\docs\05042026-visibility-business-rules-claude.md
>   - visibility/docs/2026-07-10-rebase-resolve-conflict-fix-test.md
>   - visibility/docs/2026-06-26-aws-service-resource-details.md

## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the feature branch `feature/ION-12316-inbound-ses-issue`. If it **already exists**, check it out and
   rebase it onto the latest develop (Step 1), keeping exactly **one** outgoing commit. If it does **not** exist,
   pull the latest develop and **create `feature/ION-12316-inbound-ses-issue` from the latest develop** before any work (Step 0).
2. **DO NOT PUSH** — Never `git push` / `--force` / `--force-with-lease`. The user reviews locally and pushes
   manually, and will explicitly ask you to push after review.
3. **SINGLE OUTGOING COMMIT** — End state must be exactly **one** outgoing commit
   (`git log --oneline develop..HEAD` returns one line), sitting on top of the **latest** develop. Fold all
   changes into it via `git commit --amend`. This MUST hold even after a rebase + conflict resolution.
4. **COMMIT MESSAGE** — The final commit message MUST contain the Jira key `ION-12316` (required by the Bitbucket
   "git control freak" hook).
5. **ROOT-CAUSE THE ISSUE — NO BAND-AIDS** — Find and fix the actual root cause, not just the symptom. Prove the
   diagnosis with evidence (code path, git history, logs, a failing test) before changing anything. If the correct
   fix is a larger refactor, do it in incremental, test-verified steps.
6. **REPRODUCE WITH A FAILING TEST FIRST (where applicable)** — Before implementing the fix, add a test that
   reproduces the issue and **fails** for the current (broken) behavior. Then make it pass with the fix. If the
   issue genuinely cannot be captured in a test (e.g. pure infra/config), state why in the output doc.
7. **BACKWARD COMPATIBILITY IS PARAMOUNT** — All wire/disk formats (SQS/SNS message bodies, SNS subject/attributes,
   DynamoDB encoding/decoding, JSON serialization, table-name derivation, S3 formats, SES payloads, EDI/watermill
   message shapes) must remain compatible with existing data, producers, and consumers. Reads tolerate legacy data;
   writes reproduce the legacy representation. Every change must be proven by a test.
8. **ADHERE TO THE MODULE ARCHITECTURE** — Follow the module's existing patterns, layering, and conventions (repo,
   service, resource, DI, config). For AWS interactions prefer the `cloud-sdk-api` interfaces (implemented by
   `cloud-sdk-aws` in `mercury-services-commons`) and the already-upgraded reference modules (booking, network,
   visibility) as the template. Do not introduce a divergent style.
9. **ALL TESTS MUST PASS** — Unit + integration (incl. DynamoDB Local where relevant). Everything compiles and
   keeps/raises coverage. Do not weaken or `@Disabled` a test to go green — root-cause and fix. If a test breaks
   (related or not), log it in session context, find the root cause, and FIX it.
10. **NO DESIGN-DOC / TICKET REFERENCES IN CODE** — Do not reference docs/`*.md`, Jira, or Confluence URLs in code
    comments, javadoc, or the commit message. Code comments must stand on their own.
11. **NO SHORTCUTS** — Always take the best implementation/design approach. No quick wins that compromise
    correctness, backward compatibility, or code quality.
12. **AWS CLI IS READ-ONLY** — Any AWS CLI usage MUST use the `081020446316_INTTRA-Dev-Engg` profile and be **READ queries only**
    (`describe-*`, `list-*`, `get-*`, `logs filter-log-events` / `get-log-events`). **Never** mutate anything.
    For **DynamoDB, NEVER run table scans** (`scan`) — many tables hold large data. Use targeted
    `query`/`get-item` with explicit keys, or `describe-table` for schema only. If you cannot answer read-only
    without a scan, stop and note it in the output doc instead.
13. **MODEL** — Use Claude Opus 4.8 with the 1M context window. Log this in session context (`model_info`).
14. **LOG EVERY COMMAND** — Every search / grep / `git` / AWS CLI / build / analysis command you run MUST be
    captured in the output doc (and key ones in session context) **with a clear descriptive comment** explaining
    why it was run and what it found, so the work is reproducible and reusable later (see Step 6 + the
    command-log rule).
15. **USE THE KNOWLEDGE BASE** — The mcp-context-server kb tooling indexes the workspaces, `mercury-services-commons`
    (so you can read cloud-sdk-api / cloud-sdk-aws sources directly), and the kb root
    `C:\Users\arijit.kundu\OneDrive - WiseTech Global\claude-workspace\_kbase`. Use `kb_grep` and `kb_find_files`
    to locate reference implementations, prior analyses, and usages. The semantic `kb_search` may return empty if
    its index is not built — if so, fall back to `kb_grep` / `kb_find_files`. Also check the module's own `docs/`
    folder. Log each kb query and what it revealed (Constraint 14). Check workspace files from filesystems directly if needed (all paths to project workspaces given)

---

## Session Context Protocol — FOLLOW STRICTLY

Reference: `.github/prompts/_base-session-protocol.md`.

**Before starting ANY work:**
1. `session_list` — look for an existing session for `ION-12316` / `visibility` / this issue.
2. If found → `session_get` and **resume**; cross-link the prior session.
3. If none → `session_create`:
   - name: `visibility-inbound-ses-startup-issue-20260716`
   - project: `mercury-services`
   - tags: `["visibility", "ION-12316", "issue-fix", "inbound-ses-startup-issue", "in-progress"]`

**DURING** work — `session_add_context` after every significant action:
- Rebase decision + backup branch/tag + new tip SHA → `decision` / `progress`
- Investigation steps, git-history findings, AWS-log evidence → `finding`
- Root cause (with evidence) → `finding` / `decision`
- Failing reproduction test added → `test_result` / `code_change`
- Each class/method changed + fix rationale → `code_change`
- Tests added + results, coverage numbers → `test_result`
- Compilation / `mvn verify` / packaging results → `test_result`
- Blockers → `blocker`
- Model used → `model_info`
- Key search/grep/git/aws/analysis commands + what they revealed → `finding` (also mirror into the output doc)

**Token-usage telemetry.** The mcp-context-server captures token usage automatically via harness-level hooks
(Copilot CLI `agentStop` and Claude Code `Stop`). Therefore:
- **Do NOT fabricate or estimate usage.** The model cannot see its own usage block. Only call
  `session_record_usage` if you have **real** provider usage numbers (`input_tokens`, `output_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens`, `model`); otherwise rely on the installed hooks and skip.
- **At the end** (and if context gets large), call `session_usage_report` for this session to confirm usage was
  captured, and optionally `telemetry_report` for the portfolio view; note the result in the output doc. If
  `record_count = 0`, flag that the harness hook may not have fired (do not back-fill with guesses).

If context exceeds **85%**: persist a full summary via `session_add_context` (`progress`), write all findings into
the output doc immediately, note where you left off, then continue/hand off per the base protocol.

Use the MCP context server for **Jira** (`ION-12316`) and **Confluence** access, for git operations if helpful, and
for **knowledge-base** access (`kb_grep` / `kb_find_files` over the workspaces + `mercury-services-commons` + the kb
root; fall back from the semantic `kb_search` if its index is empty).

---

## Goal / Issue Overview

The issue to diagnose and fix on the `visibility` module — analyze it fully, find the root cause, and implement a
proper fix (which may involve refactoring), backward-compatible, all tests green with full coverage on new/changed
code, in exactly **one** unpushed commit referencing `ION-12316`, with no design-doc references in code/commits:

- Visibility-dev-container startup issue. fails to startup. see log stack from aws service events below.
- Checking the visibility-inbound module found that the AWS SES service is used directly without using the cloud-sdk-api wrappers. This is wrong. The aws upgrade refactor have missed this since it was already using AWS 2.x SES clients.
  Please check booking module, auth module, network module which sends email using AWS SES service but through cloud-sdk-api and cloud-sdk-aws implementations.
  Once this is addressed in visibility, it is my understanding that the issue should get addressed. Do check and corroborate.
- the changes done in commit 2c467791676 and pull request https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/1089/overview is not correct and can be overwritten
- From the visibility service event logs >>
  int 256m total 138768 -rw-------. 1 eoadmin eoadmin 6006 Jul 15 05:06 config.yaml -rw-------. 1 eoadmin eoadmin 6038 Jul 15 05:06 config.yaml_cvt_conf -rw-------. 1 eoadmin eoadmin 5963 Jul 15 05:06 config.yaml_prod_conf -rw-------. 1 eoadmin eoadmin 6102 Jul 15 05:06 config.yaml_qa_conf -rwx------. 1 eoadmin eoadmin 337 Jul 15 05:06 run.sh -rw-------. 1 eoadmin eoadmin 414 Jul 15 05:06 suppressions.xml -rw-------. 1 eoadmin eoadmin 142051911 Jul 15 05:06 Visibility-26.07.004.jar 21:57:34.066 [main] INFO c.i.m.v.i.VisibilityInboundApplication - Starting visibility application ... 21:57:34.078 [main] INFO c.i.m.v.i.c.VisibilityInboundDynamoDbAdminCommand - VisibilityInboundDynamoDbAdminCommand initialized with 3 entity classes 2026-07-15T21:57:34.364727633Z main ERROR Log4j2 could not find a logging implementation. Please add log4j-core to the classpath. Using SimpleLogger to log to the console... java.lang.NullPointerException: Cannot invoke "java.nio.file.Path.getFileSystem()" because "<parameter1>" is null at java.base/java.nio.file.Files.provider(Unknown Source) at java.base/java.nio.file.Files.newInputStream(Unknown Source) at software.amazon.awssdk.profiles.ProfileFile$BuilderImpl.lambda$build$0(ProfileFile.java:314) at software.amazon.awssdk.utils.FunctionalUtils.lambda$safeSupplier$4(FunctionalUtils.java:108) at software.amazon.awssdk.utils.FunctionalUtils.invokeSafely(FunctionalUtils.java:136) at software.amazon.awssdk.profiles.ProfileFile$BuilderImpl.build(ProfileFile.java:314) at software.amazon.awssdk.profiles.ProfileFileSupplier.lambda$defaultSupplier$2(ProfileFileSupplier.java:58) at software.amazon.awssdk.core.client.builder.SdkDefaultClientBuilder.lambda$mergeGlobalDefaults$3(SdkDefaultClientBuilder.java:289) at software.amazon.awssdk.utils.AttributeMap$DerivedValue.primeCache(AttributeMap.java:604) at software.amazon.awssdk.utils.AttributeMap$DerivedValue.get(AttributeMap.java:593) at software.amazon.awssdk.utils.AttributeMap$Builder.resolveValue(AttributeMap.java:400) at java.base/java.util.ArrayList.forEach(Unknown Source) at software.amazon.awssdk.utils.AttributeMap$Builder.build(AttributeMap.java:362) at software.amazon.awssdk.core.client.config.SdkClientConfiguration$Builder.build(SdkClientConfiguration.java:224) at software.amazon.awssdk.core.client.config.SdkClientConfiguration.merge(SdkClientConfiguration.java:98) at software.amazon.awssdk.core.client.builder.SdkDefaultClientBuilder.mergeGlobalDefaults(SdkDefaultClientBuilder.java:285) at software.amazon.awssdk.core.client.builder.SdkDefaultClientBuilder.syncClientConfiguration(SdkDefaultClientBuilder.java:201) at software.amazon.awssdk.services.ssm.DefaultSsmClientBuilder.buildClient(DefaultSsmClientBuilder.java:36) at software.amazon.awssdk.services.ssm.DefaultSsmClientBuilder.buildClient(DefaultSsmClientBuilder.java:25) at software.amazon.awssdk.core.client.builder.SdkDefaultClientBuilder.build(SdkDefaultClientBuilder.java:171) at com.inttra.mercury.cloudsdk.paramstore.factory.ParameterStoreClientFactory.createParameterStore(ParameterStoreClientFactory.java:30) at com.inttra.mercury.config.ParameterStoreLookup.<init>(ParameterStoreLookup.java:35) at com.inttra.mercury.config.ConfigProcessingServerCommand.getConfigTransformer(ConfigProcessingServerCommand.java:27) at com.inttra.mercury.config.ConfigProcessingServerCommand.run(ConfigProcessingServerCommand.java:21) at io.dropwizard.core.cli.Cli.run(Cli.java:78) at io.dropwizard.core.Application.run(Application.java:94) at com.inttra.mercury.visibility.inbound.VisibilityInboundApplication.main(VisibilityInboundApplication.java:92)

---

## Step 0 — Orient, Resolve Branch & Back Up

First make sure develop is current, then resolve the branch — **create it from the latest develop if it does not
exist**, or back it up if it does. Run these in the workspace that owns `visibility` (C:\Users\arijit.kundu\projects\mercury-services).

```bash
cd "/c/Users/arijit.kundu/projects/mercury-services"
git fetch origin
git checkout develop && git pull --ff-only origin develop      # latest develop baseline

# Does the feature branch already exist (locally or on origin)?
git rev-parse --verify feature/ION-12316-inbound-ses-issue 2>/dev/null || git ls-remote --exit-code --heads origin feature/ION-12316-inbound-ses-issue
```

- **If `feature/ION-12316-inbound-ses-issue` does NOT exist** → create it from the latest develop and start fresh:

```bash
git checkout -b feature/ION-12316-inbound-ses-issue develop          # branch off the just-pulled latest develop
```

- **If `feature/ION-12316-inbound-ses-issue` already exists** → check it out, back it up, and proceed to the Step 1 rebase:

```bash
git checkout feature/ION-12316-inbound-ses-issue
git status --short
git log --oneline develop..HEAD             # record current outgoing commit(s)
git rev-parse HEAD                          # record current tip
git branch feature/ION-12316-inbound-ses-issue-backup-20260716   # safety backup before rebase
git tag    ION-12316-pre-fix-backup-20260716
```

- Read the module and its `docs/` folder, plus the reference material listed above (all reference
  files). Use `kb_grep` / `kb_find_files` over the workspace, `mercury-services-commons`, and the kb
  root to locate the relevant code, prior analyses, and any cloud-sdk-api / cloud-sdk-aws implementations the fix
  touches.
- `jira_get_issue: ION-12316` — read description / AC / comments for the reported behavior and constraints. Log findings.
- Log the branch decision (created-from-develop vs existing+backed-up), the backup branch/tag + tip SHA, and the
  key reference files in session context (`progress` / `finding` / `decision`).

---

## Step 1 — Rebase onto latest develop

If you **just created `feature/ION-12316-inbound-ses-issue` from the latest develop** in Step 0, it is already current — skip the rebase and
go to Step 2. Otherwise (the branch pre-existed), bring it onto the latest develop:

```bash
git fetch origin
git log --oneline HEAD..origin/develop -- visibility/    # any new commits touching this module on develop?
```

- If there are **no** new commits touching `visibility/` on `origin/develop`, skip the rebase and continue.
- If there **are** new commits, rebase the outgoing commit(s) onto the latest develop:

```bash
git rebase origin/develop
```

Resolve any conflicts carefully, preserving develop's incoming functional behavior. After the rebase, confirm the
module still builds and there is exactly **one** outgoing commit on top of the latest develop:

```bash
mvn -f visibility/pom.xml clean verify     # MUST be BUILD SUCCESS after the rebase, before any new work
git log --oneline develop..HEAD            # exactly 1 line (or 0 if no fix committed yet), message contains ION-12316
```

Log the rebase outcome (new base SHA, conflicts resolved) in session context (`decision` / `progress`) and in the
output doc.

---

## Step 2 — Investigate & find the ROOT CAUSE

Diagnose before you change anything. Gather evidence and **log every command with a descriptive comment**
(Constraint 14).

- **Read the module** — trace the code path implicated by the goals/issue. Understand the current behavior fully.
- **Git history** — use `git_log` / `git blame` / `git_diff` (and `mcp-context-server` git tools) to find when and
  why the implicated code changed, and who/what commit introduced the behavior. Log the relevant commits.
- **Referenced library implementations** — if the issue touches AWS interactions, review the `cloud-sdk-api` /
  `cloud-sdk-aws` implementations in `mercury-services-commons` (via `kb_grep` / `kb_find_files`) and compare with
  how the reference modules (booking / network / visibility) use them.
- **Knowledge base** — `kb_grep` / `kb_find_files` across the workspaces, `mercury-services-commons`, and the kb
  root for prior analyses, similar fixes, and usage patterns. Check the module `docs/`.
- **AWS logs (read-only, profile `081020446316_INTTRA-Dev-Engg`)** — where the issue is a runtime/production symptom, inspect
  AWS logs for concrete evidence. **Read queries only; NO DynamoDB scans (Constraint 12).**
  ```bash
  # ECS: cluster -> service -> task definition -> the CloudWatch log group/stream it writes to
  aws --profile 081020446316_INTTRA-Dev-Engg ecs list-services --cluster ANEINVIS-002
  aws --profile 081020446316_INTTRA-Dev-Engg ecs describe-services --cluster ANEINVIS-002 --services <service>
  aws --profile 081020446316_INTTRA-Dev-Engg ecs describe-task-definition --task-definition <taskDefArn>   # find logConfiguration -> awslogs-group
  ```
  ```bash
  # CloudWatch Logs: search for the error/root-cause evidence (read-only)
  aws --profile 081020446316_INTTRA-Dev-Engg logs describe-log-streams --log-group-name "inttra-ecs-logs" \
    --order-by LastEventTime --descending --max-items 5
  aws --profile 081020446316_INTTRA-Dev-Engg logs filter-log-events --log-group-name "inttra-ecs-logs" \
    --filter-pattern "<error-or-correlation-id>" --start-time <epoch-ms> --end-time <epoch-ms> --max-items 100
  ```
  - If a DynamoDB lookup is needed for evidence, use targeted `query` / `get-item` with explicit keys or
    `describe-table` for schema only — **never `scan`**.

State the **root cause** explicitly, with the supporting evidence, in the output doc and session context
(`finding` / `decision`). Do not proceed to the fix until the root cause is established.

---

## Step 3 — Reproduce with a failing test (where applicable)

Before implementing the fix, add a test that reproduces the issue and **fails** against the current behavior:

- Place it with the module's existing tests, following its conventions (AssertJ `assertThat(...)`, `@Nested`
  grouping, `@ParameterizedTest` with `@ValueSource`/`@CsvSource`/`@MethodSource` for multiple inputs).
- Run it and confirm it **fails** for the reason matching the root cause.
- If the issue genuinely cannot be captured in a test (pure infra/config), document why in the output doc and skip.

```bash
mvn -f visibility/pom.xml test -Dtest=<NewReproTest>     # confirm it FAILS before the fix
```

Log the reproduction test and its failing result (`test_result` / `code_change`).

---

## Step 4 — Implement the fix

Implement the proper fix for the root cause, in incremental, test-verified steps, adhering to the module
architecture (Constraint 8). The fix **may involve refactoring** — if so, keep it focused, incremental, and each
step test-verified.

- Follow the module's existing patterns and, for AWS interactions, the `cloud-sdk-api` interfaces + the reference
  modules' wiring. Before editing, use `git_log` / kb tooling / `grep` to find all usages and recent changes;
  **log each command + what it revealed** (Constraint 14).
- Keep every wire/disk format byte/shape-compatible with existing data (Constraint 7); prove it with round-trip
  tests where relevant.
- Make the reproduction test from Step 3 pass. Log each changed class/method and the fix rationale as `code_change`.

---

## Step 5 — Tests & coverage — COVERAGE IS MANDATORY

**All new/changed code must have complete coverage**, certified locally.

- **Unit tests** for every new/changed public method (including the Step 3 reproduction test, now passing).
- **Integration tests where relevant.** Any DAO/service method that calls DynamoDB should be integration-tested
  against DynamoDB Local (via the `dynamo-integration-test` infra / `BaseDynamoDbIT`, `@Tag("integration")`),
  mirroring the existing `*DaoIT` patterns. Match the reference modules' test level for SQS/SNS (mock the
  cloud-sdk clients), SES, and S3.
- **Conventions:** AssertJ, `@Nested`, `@ParameterizedTest` wherever multiple inputs apply.

Certify coverage locally and record the numbers:

```bash
mvn -f visibility/pom.xml clean verify      # runs unit + integration tests and the coverage report
# Coverage report: visibility/target/site/jacoco/index.html  (and per-submodule target/site/jacoco/*)
```

Confirm **all new/changed code is fully covered**; add tests until it is. Log coverage results (`test_result`) and
the report path in the output doc.

**Record passing test commands + an accurate test-count summary.** In the output doc, list **every** unit-test and
integration-test command that passes, each with a one-line descriptive comment, then give an accurate count of tests
run (unit + integration separately; per runner if both JUnit and TestNG are used):

```bash
find visibility -path '*/target/surefire-reports/*.xml' | wc -l   # unit report files
find visibility -path '*/target/failsafe-reports/*.xml' | wc -l   # integration report files
grep -rhoE 'tests="[0-9]+"[^>]*skipped="[0-9]+"' visibility/**/target/*-reports/*.xml
```

Log the summary (`test_result`).

---

## Step 6 — Full verify, commit (amend), document

```bash
mvn -f visibility/pom.xml clean verify     # unit + integration — BUILD SUCCESS, 0 failures
```

Root-cause and FIX any failure (related or not); iterate until green with full coverage.

Fold everything into the **one** outgoing commit (no design-doc/ticket reference in the message — Constraint 10):

```bash
git add -A
git commit --amend -m "ION-12316: visibility — route inbound SES email through cloud-sdk-api wrappers to fix container startup"
git log --oneline develop..HEAD            # exactly 1 line
git log -1 --format="%B"                   # contains ION-12316, no docs/* path or ticket URL
git status -sb                             # clean, nothing pushed
```

Do **not** push.

**Document** all of today's work in `visibility/docs/2026-07-16-ION-12316-inbound-ses-startup-issue.md` — the full analysis, root cause, and changes — including **every
search/grep/git/aws/analysis command with a clear descriptive comment** (Constraint 14) for reproducibility,
linking the reference docs. Suggested structure:
1. **Summary** — issue, branch, single-commit outcome, model (Claude Opus 4.8, 1M).
2. **Investigation** — code-path trace, git-history findings, referenced cloud-sdk implementations reviewed, kb
   findings, AWS-log evidence (read-only, profile `081020446316_INTTRA-Dev-Engg`).
3. **Root cause** — the established root cause with its supporting evidence.
4. **Reproduction** — the failing test added (or why a test wasn't feasible).
5. **Fix** — every class/method changed, rationale, any refactoring done, backward-compat evidence.
6. **Tests & coverage** — unit + integration added, coverage numbers + report path, **every passing test command**,
   and an **accurate test-count summary**.
7. **Command log** — every search/grep/git/aws/analysis/build command run, each with a one-line descriptive comment.
8. **Build results** — `mvn verify` output.
9. **Token-usage** — `session_usage_report` result for this session (or note if the hook didn't fire).
10. **References** — ION-12316, reference files/docs.

Keep the doc updated as you proceed; log doc creation (`progress`). This doc is internal reference only — **do not**
cite it from code comments or the commit message (Constraint 10).

---

## Step 7 — Handoff

```bash
git log --oneline develop..HEAD            # exactly 1 commit, message contains ION-12316
git status -sb                             # clean working tree, nothing pushed
```

- Update `visibility/docs/2026-07-16-ION-12316-inbound-ses-startup-issue.md` with the final commit hash + full test/build/coverage results and the command log.
- `session_add_context` final summary (`progress`) — persist the analysis, root cause, and the changes done to
  implement the fix; cross-link any prior sessions; keep status `active` (user reviews before push).
- `session_usage_report` for this session to confirm token-usage telemetry was captured; note it in the doc.
- Tell the user it is ready for review and **not pushed** (they will ask you to push).

---

## Definition of Done

- [ ] Session resumed/created with full traceability (decisions, code changes, findings, tests, model info,
      command log); token-usage telemetry confirmed via `session_usage_report`.
- [ ] **(Constraint 5)** Root cause established with evidence and documented before any fix.
- [ ] **(Constraint 6)** Issue reproduced with a failing test first (or justified why not).
- [ ] **(Goals)** Proper fix implemented, adhering to module architecture; backward-compatible formats proven by tests.
- [ ] **(Coverage)** `mvn -f visibility/pom.xml clean verify` BUILD SUCCESS; all new/changed code fully covered;
      relevant DynamoDB paths integration-tested.
- [ ] Every passing unit/integration test command logged in `visibility/docs/2026-07-16-ION-12316-inbound-ses-startup-issue.md` with an accurate test-count summary.
- [ ] **(Constraint 12)** Any AWS CLI usage was read-only on the `081020446316_INTTRA-Dev-Engg` profile; no DynamoDB scans.
- [ ] **(Constraint 10)** No design-doc/ticket references in code comments or the commit message.
- [ ] **(Constraint 11)** No shortcuts — best implementation/design throughout.
- [ ] **(Constraint 14 / 15)** Every search/grep/git/aws/kb/analysis command logged with a descriptive comment in
      `visibility/docs/2026-07-16-ION-12316-inbound-ses-startup-issue.md`; kb tooling (`kb_grep` / `kb_find_files`) used for lookups.
- [ ] `visibility/docs/2026-07-16-ION-12316-inbound-ses-startup-issue.md` written with the full analysis, root cause, and changes.
- [ ] Exactly **one** outgoing commit, message contains `ION-12316`, **not pushed**.
