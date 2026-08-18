---
name: 20260724-value-added-service-owasp-aws-sdk-upgrade
description: >
  AWS-SDK-2.x (cloud-sdk) refactor / functional change on the value-added-service module (ION-16110).
  Goals: OWASP dependency-check (pre + post) on latest develop, upgrade to commons 1.0.28-SNAPSHOT,
  migrate AWS interactions to cloud-sdk mirroring booking/network/auth/visibility, VS Code run configs,
  boot-check on latest develop before implementing, full unit coverage. Rebase onto the latest develop
  preserving develop's functional changes (incoming-wins on conflicts, then re-apply the AWS-upgrade
  changes), keep exactly one unpushed outgoing commit referencing ION-16110 (the OWASP fix and the
  cloud-sdk migration are inseparable — see Constraint 3), full local mvn clean verify with complete
  JaCoCo coverage on all new code, unit + integration tests (DynamoDB + SNS — the module's actual AWS
  footprint) mirroring the reference modules, document cloud-sdk gaps, and log every search/grep/git/analysis
  command. Do not push.
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

# value-added-service — AWS SDK 2.x (cloud-sdk) Refactor — ION-16110

> **Jira:** ION-16110 (used for the commit message / session tags only — per goals, do NOT connect to Jira or Confluence via the MCP context server for this work)
> **Read first (reference material — all files):**
> - C:\Users\arijit.kundu\projects\mercury-services\value-added-service\docs\2026-06-30-value-added-service-aws2x-DESIGN-claude.md
> - booking/docs/2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md
> - C:\Users\arijit.kundu\projects\mercury-services\visibility\docs\2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md
> - C:\Users\arijit.kundu\projects\mercury-services\visibility\docs\2026-06-25-visibility-sns-sqs-refactor.md

## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the feature branch `feature/ION-16110-vas-owasp-aws-upgrade`. If it **already exists**, check it out and
   rebase it onto the latest develop (Step 1), keeping exactly **one** outgoing commit. If it does **not** exist,
   pull the latest develop and **create `feature/ION-16110-vas-owasp-aws-upgrade` from the latest develop** before any work (Step 0).
2. **DO NOT PUSH** — Never `git push` / `--force` / `--force-with-lease`. The user reviews locally and pushes
   manually, and will explicitly ask you to push after review.
3. **ONE OUTGOING COMMIT** — Have exactly **one** commit. The OWASP fix and the AWS-SDK-2.x (cloud-sdk) upgrade
   are **inseparable** and cannot be split into independent commits: commons `1.0.28-SNAPSHOT` **removes** the
   legacy `com.inttra.mercury.messaging.*` package with **no shim** (so the commons bump cannot compile without
   migrating the SNS/`EventLogger` usage), and clearing the AWS-SDK-v1 CVEs requires dropping `dynamo-client`
   (the DynamoDB migration). Deliver the OWASP fix + full cloud-sdk migration as a single squashed commit
   referencing `ION-16110`.
4. **COMMIT MESSAGE** — The final commit message MUST contain the Jira key `ION-16110` (required by the Bitbucket
   "git control freak" hook).
5. **LATEST DEVELOP IS THE FUNCTIONAL BASELINE (PRIORITY)** — develop's latest commits are **functional changes**
   and take **priority**. If new commits landed on develop that touch `value-added-service/`, rebase onto the latest develop
   first (Step 1). On any conflict between develop and the AWS-upgrade changes, **take the incoming develop change
   first**, then **adjust and re-apply the AWS-SDK-upgrade changes on top** so the upgrade conforms to develop.
   The rebase must in **no way** drop, weaken, or alter develop's incoming functional behavior. Never sacrifice a
   functional change to keep an upgrade change.
6. **BACKWARD COMPATIBILITY IS PARAMOUNT** — All wire/disk formats (SQS/SNS message bodies, SNS subject/attributes,
   DynamoDB encoding/decoding, JSON serialization, table-name derivation, S3 formats, SES payloads) must remain
   compatible with existing 1.x data, producers, and consumers. Reads tolerate legacy data; writes reproduce the
   legacy representation. Every change must be proven by a test.
7. **ALIGN WITH THE REFERENCE MODULES** — Use the already-upgraded modules as the template.
   **Scope note:** `value-added-service`'s actual AWS footprint is **DynamoDB + SNS only** — there is no SQS, SES
   or S3 usage in this module (CMA/Hapag-Lloyd REST, Parameter Store `${awsps:}`, carrier OAuth and swagger
   generation are out of scope and unchanged). The SES/S3/SQS mappings below apply only if such usage is actually
   found; otherwise ignore them.
   - **SQS / SNS** → mirror **booking** and **network** (`MessagingClient` / `MessagingClientFactory`,
     `NotificationService` / `SnsService` / `SnsEventPublisher`, Guice factories, config blocks, test level).
   - **Email / SES** → mirror **booking** and **auth**.
   - **S3** → mirror **booking** (cloud-sdk storage client / factory + config blocks).
   - **DynamoDB** → mirror the upgraded DAO/admin-command patterns in booking/network/registration/webbl/booking-bridge.
   Prefer the proven reference approach over any divergent one already in `value-added-service`.
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

---

## Session Context Protocol — FOLLOW STRICTLY

Reference: `.github/prompts/_base-session-protocol.md`.

**Before starting ANY work:**
1. `session_list` — look for an existing session for `ION-16110` / `value-added-service` / `value-added-service-aws-upgrade`.
2. If found → `session_get` and **resume**; cross-link the prior session.
3. If none → `session_create`:
   - name: `value-added-service-owasp-aws-sdk-upgrade-20260724`
   - project: `mercury-services`
   - tags: `["value-added-service", "ION-16110", "aws-sdk-upgrade", "owasp-aws-sdk-upgrade", "in-progress"]`

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

Use the MCP context server for git operations if helpful, and for **knowledge-base** access (`kb_grep` /
`kb_find_files` over this repo + `mercury-services-commons`; fall back from the semantic `kb_search` to `kb_grep` /
`kb_find_files` if its index is empty). Per the goals, do **not** connect to Jira or Confluence via the MCP context
server for this work.

---

## Goal Overview

Accomplish the following on the `value-added-service` module, all backward-compatible with 1.x, all tests green with full
JaCoCo coverage on new code, in a **single** commit referencing `ION-16110` (OWASP fix + cloud-sdk migration are
inseparable — Constraint 3), with no design-doc references in code/commits:

- Run OWASP dependency-check **first** on the latest develop code for this module (baseline scan before any change).
  dependency-check is installed. First build the shaded jar, then scan it (substitute the actual jar name in the dependency-check command after mvn package build):
  ```powershell
  mvn package -pl value-added-service -DskipTests -am
  dependency-check --project value-added-service --scan ./<jar name>.jar --out owasp --suppression ../suppressions.xml --nvdApiKey $env:NVD_API_KEY
  ```

- Create **VS Code run configs** for this module **first**.

- Make sure the application **boots up fine with the latest code in develop** first. If it does not, **flag this and
  do NOT proceed** with implementation.

- If the application boots up fine, create the new feature branch and start implementing first the owasp fix (1.0.28-SNAPSHOT should work)
  and then the aws upgrade based on the design and plan already created (both land in the same single commit — Constraint 3).

- Upgrade to `1.0.28-SNAPSHOT` version of `mercury-services-commons` (commons dependency).

- make any necessary changes to address compilation , tests, or application start up issue, verify OWASP that the CVEs are resolved, then commit once the full migration is done and the app boots cleanly. Expect the HIGH CVE count to drop to **0** (the http-component HIGHs are cleared because AWS SDK v2 pulls in a patched httpcore5; the earlier "2 http false-positives remain" assumption did not hold in practice).
  
- **rerun** dependency-check, compare CVEs against the baseline, and summarize the  pre/post CVE delta in the output document.

- Copy **both** the pre- and post-implementation OWASP scans into `C:\temp\latest-dep-chk-reports\vas`.

- work on the aws upgrade in the same commit as the owasp fix (they are inseparable — Constraint 3).

- Refer to **booking**, **network**, **auth**, and **visibility** for the AWS upgrade changes (reference templates).

- Create a **detailed design & plan** for the upgrade under value-added-service/docs/2026-07-24-vas-owasp-aws-upgrade-design.md before implementing.

- All code changes must have **unit test coverage**.

- Make sure **all tests PASS**, **no shortcuts**, and the application boots up fi.

- No need to connect to Jira or Confluence using the MCP context server for this work.

---

## Step 0 — Orient, Resolve Branch & Back Up

First make sure develop is current, then resolve the branch — **create it from the latest develop if it does not
exist**, or back it up if it does.

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git fetch origin
git checkout develop && git pull --ff-only origin develop      # latest develop is the functional baseline

# Does the feature branch already exist (locally or on origin)?
git rev-parse --verify feature/ION-16110-vas-owasp-aws-upgrade 2>/dev/null || git ls-remote --exit-code --heads origin feature/ION-16110-vas-owasp-aws-upgrade
```

**IMPORTANT ordering per goals:** the boot-check on the latest develop and the baseline OWASP scan happen **before**
you create the feature branch. Create/rebase the branch only once develop boots cleanly (see the Goal Overview).

- **If `feature/ION-16110-vas-owasp-aws-upgrade` does NOT exist** → create it from the latest develop and start fresh (only after the develop boot-check passes):

```bash
git checkout -b feature/ION-16110-vas-owasp-aws-upgrade develop          # branch off the just-pulled latest develop
```

- **If `feature/ION-16110-vas-owasp-aws-upgrade` already exists** → check it out, back it up, and proceed to the Step 1 rebase:

```bash
git checkout feature/ION-16110-vas-owasp-aws-upgrade
git status --short
git log --oneline develop..HEAD             # record current outgoing commit(s)
git rev-parse HEAD                          # record current tip
git branch feature/ION-16110-vas-owasp-aws-upgrade-backup-20260724   # safety backup before rebase
git tag    ION-16110-pre-refactor-backup-20260724
```

- Read the reference material listed above (all reference files) and the reference
  modules' cloud-sdk wiring (booking/network for SQS/SNS, booking/auth for SES, booking for S3,
  booking/network/registration for DynamoDB) — these are your templates. Use `kb_grep` / `kb_find_files` to open
  the cloud-sdk-api / cloud-sdk-aws sources from `mercury-services-commons` as needed.
- Log the branch decision (created-from-develop vs existing+backed-up), the backup branch/tag + tip SHA, and the
  key reference files in session context (`progress` / `finding` / `decision`).

---

## Step 1 — Rebase onto latest develop (develop's functional changes take PRIORITY)

If you **just created `feature/ION-16110-vas-owasp-aws-upgrade` from the latest develop** in Step 0, it is already current — skip the rebase and
go to Step 2. Otherwise (the branch pre-existed), bring it onto the latest develop:

```bash
git fetch origin
git log --oneline HEAD..origin/develop -- value-added-service/    # any new commits touching this module on develop?
```

- If there are **no** new commits touching `value-added-service/` on `origin/develop`, skip the rebase and continue.
- If there **are** new commits, rebase the outgoing commit(s) onto the latest develop:

```bash
git rebase origin/develop
```

**Conflict-resolution rule (Constraint 5):** develop's commits are **functional changes** and win. For every
conflict, **take the incoming develop change first**, then **adjust and re-apply the AWS-SDK-upgrade change on top**
so the upgrade conforms to develop's new code. Never drop or alter develop's functional behavior to preserve an
upgrade change.

```bash
mvn -f value-added-service/pom.xml clean verify     # MUST be BUILD SUCCESS after the rebase, before any new work
```

After the rebase + conflict resolution, confirm exactly **one** outgoing commit on top of the latest develop
(squash/`--amend` as needed):

```bash
git log --oneline develop..HEAD            # exactly 1 line, message contains ION-16110
```

Log the rebase outcome (new base SHA, conflicts resolved, how each was reconciled) in session context
(`decision` / `progress`) and in the output doc.

---

## Step 2 — Implement the goals

Implement every goal from the **Goal Overview** on `value-added-service`, in incremental, test-verified steps, mirroring the
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

Certify coverage with JaCoCo locally and record the numbers:

```bash
mvn -f value-added-service/pom.xml clean verify      # runs unit + integration tests and the JaCoCo report
# JaCoCo report: value-added-service/target/site/jacoco/index.html  (and per-submodule target/site/jacoco/*)
```

Inspect the JaCoCo report and confirm **all new/changed code is fully covered**. If any new code is uncovered, add
tests until it is. Log coverage results (`test_result`) and the report path in the output doc.

**Record passing test commands + an accurate test-count summary (Constraint 14).** In the output doc, list **every**
unit-test and integration-test command that passes (e.g. `mvn -f value-added-service/pom.xml test`,
`mvn -f value-added-service/pom.xml verify`, any `-pl <submodule>` runs), each with a one-line descriptive comment. Then give
an **accurate count of tests run** — unit and integration separately. If more than one test runner is in play
(e.g. **JUnit** via surefire/failsafe and **TestNG**), report the counts **per runner**, taken from the actual
reports:

```bash
# JUnit/TestNG surefire = unit, failsafe = integration; count the result XMLs and tally the suite headers:
find value-added-service -path '*/target/surefire-reports/*.xml' | wc -l   # unit report files
find value-added-service -path '*/target/failsafe-reports/*.xml' | wc -l   # integration report files
# Tally tests/failures/errors/skipped from the <testsuite ...> headers (covers JUnit AND TestNG surefire output):
grep -rhoE 'tests="[0-9]+"[^>]*skipped="[0-9]+"' value-added-service/**/target/*-reports/*.xml
```

Summarize, e.g.: "JUnit: 142 unit + 18 integration; TestNG: 7 unit — total 167, 0 failures, 0 errors". Log the
summary (`test_result`).

---

## Step 4 — Document cloud-sdk library gaps

If anything in `cloud-sdk-api` / `cloud-sdk-aws` is missing for `value-added-service`'s needs, maintain a single, actionable
**"cloud-sdk gaps"** section in the output doc. For each gap give: the legacy capability, the cloud-sdk shortfall
(with evidence), the workaround used in `value-added-service`, and a **concrete proposed enhancement** to
`cloud-sdk-api`/`cloud-sdk-aws` (the exact method/builder to add). Summarize options and trade-offs. Log gaps as
`finding`. If no gaps are found, state so explicitly.

---

## Step 5 — Full verify, commit (amend), document

```bash
mvn -f value-added-service/pom.xml clean verify     # unit + integration (DynamoDB Local) — BUILD SUCCESS, 0 failures
```

Root-cause and FIX any failure (related or not); add a reproducing test for any bug before fixing; iterate until
green with full coverage.

Fold everything into the **one** outgoing commit (no design-doc/ticket reference in the message — Constraint 9):

```bash
git add -A
git commit --amend -m "ION-16110: value-added-service AWS SDK 2.x — OWASP dependency-check + commons 1.0.28 cloud-sdk upgrade"
git log --oneline develop..HEAD            # exactly 1 line
git log -1 --format="%B"                   # contains ION-16110, no docs/* path or ticket URL
git status -sb                             # clean, nothing pushed
```

Do **not** push.

**Document** all of today's work in `value-added-service/docs/2026-07-24-vas-aws-upgrade.md` — including **every search/grep/git/analysis command with a clear
descriptive comment** (Constraint 12) for reproducibility, linking the reference docs.
Suggested structure:
1. **Summary** — goals, branch, single-commit outcome, model (Claude Opus 4.8, 1M), rebase result (if any).
2. **Rebase** — whether needed, new base SHA, each conflict and how develop's change was preserved + the upgrade re-applied.
3. **OWASP dependency-check** — pre-scan (baseline) and post-scan CVE comparison, the delta summary, and confirmation both reports were copied to `C:\temp\latest-dep-chk-reports\vas`.
4. **Design plan** — the detailed upgrade design plan created before implementation.
5. **VS Code run configs** — the run configs created for this module.
6. **Develop boot-check** — result of booting the app on the latest develop (pass/fail; if fail, the flag and stop).
7. **Implementation** — every class/DAO/service migrated, Guice factory swaps, config blocks added, backward-compat evidence, legacy deps removed, commons bumped to 1.0.28-SNAPSHOT.
8. **Tests & coverage** — unit + integration (DynamoDB/SQS/SNS/SES/S3) added, reference-module alignment, JaCoCo
   coverage numbers + report path, **every passing unit/integration test command**, and an **accurate test-count
   summary (unit + integration, per runner if JUnit and TestNG are both used)**.
9. **cloud-sdk gaps** — gaps + concrete proposed enhancements (or "none found").
10. **Command log** — every search/grep/git/analysis/build command run, each with a one-line descriptive comment.
11. **Build / packaging results** — `mvn verify` output.
12. **Token-usage** — `session_usage_report` result for this session (or note if the hook didn't fire).
13. **References** — ION-16110, reference files/modules/docs.

Keep the doc updated as you proceed; log doc creation (`progress`). This doc is internal reference only — **do not**
cite it from code comments or the commit message (Constraint 9).

---

## Step 6 — Handoff

```bash
git log --oneline develop..HEAD            # exactly 1 commit, message contains ION-16110
git status -sb                             # clean working tree, nothing pushed
```

- Update `value-added-service/docs/2026-07-24-vas-aws-upgrade.md` with the final commit hash + full test/build/coverage results and the command log.
- `session_add_context` final summary (`progress`); cross-link any prior sessions; keep status `active` (user
  reviews before push).
- `session_usage_report` for this session to confirm token-usage telemetry was captured; note it in the doc.
- Tell the user it is ready for review and **not pushed** (they will ask you to push).

---

## Definition of Done

- [ ] Session resumed/created with full traceability (decisions, code changes, findings, tests, model info,
      command log); token-usage telemetry confirmed via `session_usage_report`.
- [ ] **(Develop boot-check)** App boots on the latest develop; if it does not, flagged and implementation stopped.
- [ ] **(OWASP)** Pre- and post-implementation dependency-check scans run, CVE delta summarized, both reports copied to `C:\temp\latest-dep-chk-reports\vas`.
- [ ] **(commons)** Upgraded to `1.0.28-SNAPSHOT` of `mercury-services-commons`.
- [ ] **(VS Code)** Run configs created for the module.
- [ ] **(Design plan)** Detailed upgrade design plan authored before implementation.
- [ ] **(Constraint 5)** Rebased onto the latest develop if new `value-added-service` commits landed; develop's functional
      changes preserved (incoming-wins), AWS-upgrade changes re-applied on top; exactly one outgoing commit.
- [ ] **(Goals)** Every goal implemented, mirroring the reference modules; AWS interactions on cloud-sdk;
      backward-compatible wire/disk formats proven by tests.
- [ ] **(Coverage)** `mvn -f value-added-service/pom.xml clean verify` BUILD SUCCESS; all new code fully covered per local
      JaCoCo; every DynamoDB DAO/service method integration-tested; SQS/SNS aligned to booking/network, SES to
      booking/auth, S3 to booking.
- [ ] **(Constraint 14)** Every passing unit/integration test command logged in `value-added-service/docs/2026-07-24-vas-aws-upgrade.md` with an accurate
      test-count summary (unit + integration, per runner if JUnit and TestNG are both used).
- [ ] **(cloud-sdk gaps)** Documented with concrete proposed enhancements (or "none found").
- [ ] **(Constraint 9)** No design-doc/ticket references in code comments or the commit message.
- [ ] **(Constraint 10)** No shortcuts — best implementation/design throughout.
- [ ] **(Constraint 12 / 13)** Every search/grep/git/kb/analysis command logged with a descriptive comment in
      `value-added-service/docs/2026-07-24-vas-aws-upgrade.md`; kb tooling (`kb_grep` / `kb_find_files`) used for reference lookups.
- [ ] `value-added-service/docs/2026-07-24-vas-aws-upgrade.md` written with all of the above.
- [ ] Exactly **one** outgoing commit, message contains `ION-16110`, **not pushed**.
