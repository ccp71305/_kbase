---
name: 20260630-visibility-rebase-resolve-develop-conflict
description: >
  AWS-SDK-2.x (cloud-sdk) refactor / functional change on the visibility module (ION-12316).
  Goals: rebase onto latest develop and resolve merge conflicts. Rebase onto the latest develop preserving develop's functional
  changes (incoming-wins on conflicts, then re-apply the AWS-upgrade changes), keep exactly one
  unpushed outgoing commit referencing ION-12316, full local mvn clean verify with complete JaCoCo
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

# visibility — AWS SDK 2.x (cloud-sdk) Refactor — ION-12316

> **Jira:** ION-12316
> **Read first (reference material — all files):**
> - C:\Users\arijit.kundu\projects\mercury-services\.github\prompts\refactor\2026-06-25-visibility-sns-sqs-refactor-prompt.md

## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the feature branch `feature/ION-12316-visibiilty-aws-upgrade-copilot`. If it **already exists**, check it out and
   rebase it onto the latest develop (Step 1), keeping exactly **one** outgoing commit. If it does **not** exist,
   pull the latest develop and **create `feature/ION-12316-visibiilty-aws-upgrade-copilot` from the latest develop** before any work (Step 0).
2. **DO NOT PUSH** — Never `git push` / `--force` / `--force-with-lease`. The user reviews locally and pushes
   manually, and will explicitly ask you to push after review.
3. **SINGLE OUTGOING COMMIT** — End state must be exactly **one** outgoing commit
   (`git log --oneline develop..HEAD` returns one line), sitting on top of the **latest** develop. Fold all
   changes into it via `git commit --amend`. This MUST hold even after a rebase + conflict resolution.
4. **COMMIT MESSAGE** — The final commit message MUST contain the Jira key `ION-12316` (required by the Bitbucket
   "git control freak" hook).
5. **LATEST DEVELOP IS THE FUNCTIONAL BASELINE (PRIORITY)** — develop's latest commits are **functional changes**
   and take **priority**. If new commits landed on develop that touch `visibility/`, rebase onto the latest develop
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
   Prefer the proven reference approach over any divergent one already in `visibility`.
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
1. `session_list` — look for an existing session for `ION-12316` / `visibility` / `visibility-aws-upgrade`.
2. If found → `session_get` and **resume**; cross-link the prior session.
3. If none → `session_create`:
   - name: `visibility-rebase-resolve-develop-conflict-20260630`
   - project: `mercury-services`
   - tags: `["visibility", "ION-12316", "aws-sdk-upgrade", "rebase-resolve-develop-conflict", "in-progress"]`

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

Use the MCP context server for **Jira** (`ION-12316`) and **Confluence** access, for git operations if helpful, and
for **knowledge-base** access (`kb_grep` / `kb_find_files` over this repo + `mercury-services-commons`; fall back
from the semantic `kb_search` to `kb_grep` / `kb_find_files` if its index is empty).

---

## Goal Overview

Accomplish the following on the `visibility` module, all backward-compatible with 1.x, all tests green with full
JaCoCo coverage on new code, in exactly **one** unpushed commit referencing `ION-12316`, with no design-doc
references in code/commits:

- rebase onto latest develop
- there is merge conflict so resolve them during rebase

---

## Step 0 — Orient, Resolve Branch & Back Up

First make sure develop is current, then resolve the branch — **create it from the latest develop if it does not
exist**, or back it up if it does.

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git fetch origin
git checkout develop && git pull --ff-only origin develop      # latest develop is the functional baseline

# Does the feature branch already exist (locally or on origin)?
git rev-parse --verify feature/ION-12316-visibiilty-aws-upgrade-copilot 2>/dev/null || git ls-remote --exit-code --heads origin feature/ION-12316-visibiilty-aws-upgrade-copilot
```

- **If `feature/ION-12316-visibiilty-aws-upgrade-copilot` does NOT exist** → create it from the latest develop and start fresh:

```bash
git checkout -b feature/ION-12316-visibiilty-aws-upgrade-copilot develop          # branch off the just-pulled latest develop
```

- **If `feature/ION-12316-visibiilty-aws-upgrade-copilot` already exists** → check it out, back it up, and proceed to the Step 1 rebase:

```bash
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot
git status --short
git log --oneline develop..HEAD             # record current outgoing commit(s)
git rev-parse HEAD                          # record current tip
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-20260630   # safety backup before rebase
git tag    ION-12316-pre-refactor-backup-20260630
```

- Read the reference material listed above (all reference files) and the reference
  modules' cloud-sdk wiring (booking/network for SQS/SNS, booking/auth for SES, booking for S3,
  booking/network/registration for DynamoDB) — these are your templates. Use `kb_grep` / `kb_find_files` to open
  the cloud-sdk-api / cloud-sdk-aws sources from `mercury-services-commons` as needed.
- `jira_get_issue: ION-12316` — re-read description / AC / comments for constraints. Log findings.
- Log the branch decision (created-from-develop vs existing+backed-up), the backup branch/tag + tip SHA, and the
  key reference files in session context (`progress` / `finding` / `decision`).

---

## Step 1 — Rebase onto latest develop (develop's functional changes take PRIORITY)

If you **just created `feature/ION-12316-visibiilty-aws-upgrade-copilot` from the latest develop** in Step 0, it is already current — skip the rebase and
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

**Conflict-resolution rule (Constraint 5):** develop's commits are **functional changes** and win. For every
conflict, **take the incoming develop change first**, then **adjust and re-apply the AWS-SDK-upgrade change on top**
so the upgrade conforms to develop's new code. Never drop or alter develop's functional behavior to preserve an
upgrade change.

```bash
mvn -f visibility/pom.xml clean verify     # MUST be BUILD SUCCESS after the rebase, before any new work
```

After the rebase + conflict resolution, confirm exactly **one** outgoing commit on top of the latest develop
(squash/`--amend` as needed):

```bash
git log --oneline develop..HEAD            # exactly 1 line, message contains ION-12316
```

Log the rebase outcome (new base SHA, conflicts resolved, how each was reconciled) in session context
(`decision` / `progress`) and in the output doc.

---

## Step 2 — Implement the goals

Implement every goal from the **Goal Overview** on `visibility`, in incremental, test-verified steps, mirroring the
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
mvn -f visibility/pom.xml clean verify      # runs unit + integration tests and the JaCoCo report
# JaCoCo report: visibility/target/site/jacoco/index.html  (and per-submodule target/site/jacoco/*)
```

Inspect the JaCoCo report and confirm **all new/changed code is fully covered**. If any new code is uncovered, add
tests until it is. Log coverage results (`test_result`) and the report path in the output doc.

**Record passing test commands + an accurate test-count summary (Constraint 14).** In the output doc, list **every**
unit-test and integration-test command that passes (e.g. `mvn -f visibility/pom.xml test`,
`mvn -f visibility/pom.xml verify`, any `-pl <submodule>` runs), each with a one-line descriptive comment. Then give
an **accurate count of tests run** — unit and integration separately. If more than one test runner is in play
(e.g. **JUnit** via surefire/failsafe and **TestNG**), report the counts **per runner**, taken from the actual
reports:

```bash
# JUnit/TestNG surefire = unit, failsafe = integration; count the result XMLs and tally the suite headers:
find visibility -path '*/target/surefire-reports/*.xml' | wc -l   # unit report files
find visibility -path '*/target/failsafe-reports/*.xml' | wc -l   # integration report files
# Tally tests/failures/errors/skipped from the <testsuite ...> headers (covers JUnit AND TestNG surefire output):
grep -rhoE 'tests="[0-9]+"[^>]*skipped="[0-9]+"' visibility/**/target/*-reports/*.xml
```

Summarize, e.g.: "JUnit: 142 unit + 18 integration; TestNG: 7 unit — total 167, 0 failures, 0 errors". Log the
summary (`test_result`).

---

## Step 4 — Document cloud-sdk library gaps

If anything in `cloud-sdk-api` / `cloud-sdk-aws` is missing for `visibility`'s needs, maintain a single, actionable
**"cloud-sdk gaps"** section in the output doc. For each gap give: the legacy capability, the cloud-sdk shortfall
(with evidence), the workaround used in `visibility`, and a **concrete proposed enhancement** to
`cloud-sdk-api`/`cloud-sdk-aws` (the exact method/builder to add). Summarize options and trade-offs. Log gaps as
`finding`. If no gaps are found, state so explicitly.

---

## Step 5 — Full verify, commit (amend), document

```bash
mvn -f visibility/pom.xml clean verify     # unit + integration (DynamoDB Local) — BUILD SUCCESS, 0 failures
```

Root-cause and FIX any failure (related or not); add a reproducing test for any bug before fixing; iterate until
green with full coverage.

Fold everything into the **one** outgoing commit (no design-doc/ticket reference in the message — Constraint 9):

```bash
git add -A
git commit --amend -m "ION-12316: visibility AWS SDK 2.x — rebase onto latest develop and resolve merge conflicts"
git log --oneline develop..HEAD            # exactly 1 line
git log -1 --format="%B"                   # contains ION-12316, no docs/* path or ticket URL
git status -sb                             # clean, nothing pushed
```

Do **not** push.

**Document** all of today's work in `visibility/docs/2026-06-30-rebase-resolve-conflict.md` — including **every search/grep/git/analysis command with a clear
descriptive comment** (Constraint 12) for reproducibility, linking the reference docs.
Suggested structure:
1. **Summary** — goals, branch, single-commit outcome, model (Claude Opus 4.8, 1M), rebase result (if any).
2. **Rebase** — whether needed, new base SHA, each conflict and how develop's change was preserved + the upgrade re-applied.
3. **Implementation** — every class/DAO/service migrated, Guice factory swaps, config blocks added, backward-compat evidence, legacy deps removed.
4. **Tests & coverage** — unit + integration (DynamoDB/SQS/SNS/SES/S3) added, reference-module alignment, JaCoCo
   coverage numbers + report path, **every passing unit/integration test command**, and an **accurate test-count
   summary (unit + integration, per runner if JUnit and TestNG are both used)**.
5. **cloud-sdk gaps** — gaps + concrete proposed enhancements (or "none found").
6. **Command log** — every search/grep/git/analysis/build command run, each with a one-line descriptive comment.
7. **Build / packaging results** — `mvn verify` output.
8. **Token-usage** — `session_usage_report` result for this session (or note if the hook didn't fire).
9. **References** — ION-12316, reference files/modules/docs.

Keep the doc updated as you proceed; log doc creation (`progress`). This doc is internal reference only — **do not**
cite it from code comments or the commit message (Constraint 9).

---

## Step 6 — Handoff

```bash
git log --oneline develop..HEAD            # exactly 1 commit, message contains ION-12316
git status -sb                             # clean working tree, nothing pushed
```

- Update `visibility/docs/2026-06-30-rebase-resolve-conflict.md` with the final commit hash + full test/build/coverage results and the command log.
- `session_add_context` final summary (`progress`); cross-link any prior sessions; keep status `active` (user
  reviews before push).
- `session_usage_report` for this session to confirm token-usage telemetry was captured; note it in the doc.
- Tell the user it is ready for review and **not pushed** (they will ask you to push).

---

## Definition of Done

- [ ] Session resumed/created with full traceability (decisions, code changes, findings, tests, model info,
      command log); token-usage telemetry confirmed via `session_usage_report`.
- [ ] **(Constraint 5)** Rebased onto the latest develop if new `visibility` commits landed; develop's functional
      changes preserved (incoming-wins), AWS-upgrade changes re-applied on top; exactly one outgoing commit.
- [ ] **(Goals)** Every goal implemented, mirroring the reference modules; AWS interactions on cloud-sdk;
      backward-compatible wire/disk formats proven by tests.
- [ ] **(Coverage)** `mvn -f visibility/pom.xml clean verify` BUILD SUCCESS; all new code fully covered per local
      JaCoCo; every DynamoDB DAO/service method integration-tested; SQS/SNS aligned to booking/network, SES to
      booking/auth, S3 to booking.
- [ ] **(Constraint 14)** Every passing unit/integration test command logged in `visibility/docs/2026-06-30-rebase-resolve-conflict.md` with an accurate
      test-count summary (unit + integration, per runner if JUnit and TestNG are both used).
- [ ] **(cloud-sdk gaps)** Documented with concrete proposed enhancements (or "none found").
- [ ] **(Constraint 9)** No design-doc/ticket references in code comments or the commit message.
- [ ] **(Constraint 10)** No shortcuts — best implementation/design throughout.
- [ ] **(Constraint 12 / 13)** Every search/grep/git/kb/analysis command logged with a descriptive comment in
      `visibility/docs/2026-06-30-rebase-resolve-conflict.md`; kb tooling (`kb_grep` / `kb_find_files`) used for reference lookups.
- [ ] `visibility/docs/2026-06-30-rebase-resolve-conflict.md` written with all of the above.
- [ ] Exactly **one** outgoing commit, message contains `ION-12316`, **not pushed**.
