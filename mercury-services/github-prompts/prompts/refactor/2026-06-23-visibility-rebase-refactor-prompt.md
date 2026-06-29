---
name: 2026-06-23-visibility-rebase-refactor
description: Squash the visibility AWS-SDK-2.x feature branch into one commit, rebase it onto the latest develop, resolve all conflicts by applying the AWS upgrade changes on top of the latest functional code, address the design/impl review comments (keeping backward compatibility for all encoding/decoding with 1.x visibility), and leave exactly one unpushed outgoing commit referencing ION-12316. Verify everything compiles, has test coverage, all tests pass, and modules start with INT config.
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

# Visibility — Rebase onto Develop + AWS 2.x Upgrade Refactor — ION-12316

## CRITICAL CONSTRAINTS

1. **BRANCH** — All work happens on the existing feature branch `feature/ION-12316-visibiilty-aws-upgrade-copilot`. Nothing has been pushed to remote.
2. **DO NOT PUSH** — Never `git push` or `git push --force`. The user will review locally and push manually. All rebasing/squashing is local only.
3. **SINGLE OUTGOING COMMIT** — The end state must be exactly **one** outgoing commit (`git log --oneline develop..HEAD` returns one line).
4. **COMMIT MESSAGE** — The final commit message MUST contain the text `ION-12316`.
5. **LATEST DEVELOP IS THE FUNCTIONAL BASELINE** — `develop` carries the latest, correct functional code. The feature branch carries the AWS-upgrade changes. When resolving conflicts, the AWS upgrade changes must be **re-applied on top of** the latest functional code — never drop a functional change from develop to keep an upgrade change.
6. **BACKWARD COMPATIBILITY IS PARAMOUNT** — All DynamoDB encoding/decoding, JSON blob serialization, table-name derivation, and S3 archive formats must remain wire-compatible with existing **1.x visibility** data. Reads must tolerate legacy data; writes must match the legacy on-disk representation.
7. **ALL TESTS MUST PASS** — Unit + integration (including DynamoDB integration tests). All changes must compile and have test coverage.
8. **STARTUP CHECK** — Every affected visibility sub-module must start cleanly with its **INT** `config.yaml`.
9. **MODEL** — Use Claude Opus 4.8 with the 1M context token window. Log this in session context (`model_info`).

---

## Session Context Protocol — FOLLOW STRICTLY

Reference: `.github/prompts/_base-session-protocol.md`.

Before starting ANY work:
1. `session_list` — look for an existing session for `ION-12316`, `visibility`, or `visibility-aws-upgrade`.
2. If found → `session_get` and resume.
3. If none → `session_create`:
   - name: `visibility-rebase-refactor-2026-06-23`
   - project: `mercury-services`
   - tags: `["visibility", "ION-12316", "aws-sdk-upgrade", "rebase", "refactor", "backward-compat", "in-progress"]`

**DURING** work — `session_add_context` after every significant action:
- Outgoing-commit count / squash result → `progress`
- Rebase conflict files + resolution decisions → `decision`
- Each review comment addressed → `code_change`
- Compilation / test / startup results → `test_result`
- Blockers (e.g. failing integration test) → `blocker`
- Model used → `model_info`

If context exceeds **85%**: persist a full summary via `session_add_context` (category `progress`), write all findings into the rebase/refactor doc immediately, note where you left off, then continue or hand off per the base protocol.

Use the MCP context server tools for **Jira** (ION-12316) and **Confluence** access, and optionally for **git** operations if it helps.

You can check the **git-operations** skill (`.github/skills/git-operations/SKILL.md`) if they are helpful for the rebase/squash workflow — but **skip its force-push steps** (constraint #2). You may want to udpate that document if you find some other commands which are more efficient. You do not have to use that skill if it is in any way incomplete or inefficient or if you have something better. But do update that skill in that case.

---

## Goal Overview

Produce a clean, single, **unpushed** commit on `feature/ION-12316-visibiilty-aws-upgrade-copilot` that:
- contains the AWS SDK 2.x (cloud-sdk) upgrade for the visibility module,
- sits on top of the **latest** `develop`,
- incorporates the agreed fixes from the design/impl review,
- preserves full backward compatibility with 1.x visibility data,
- compiles, is test-covered, passes all tests, and starts under INT config.

---

## Step 1 — Back Up the Current Feature Branch

Before touching history, take a safety backup of the current feature branch so it can be restored if the squash/rebase goes wrong. This is local only — **do not push**.

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot
git status --short                         # ensure clean; stash if needed (git stash -u)

# Record the current tip for reference
git rev-parse HEAD

# Create a dated backup branch pointing at the current tip (no checkout needed)
git branch feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23

# Also tag it for extra safety
git tag ION-12316-pre-rebase-backup-2026-06-23

# Verify the backup exists and points at the same commit
git branch --list "*ION-12316*backup*"
git log --oneline -1 feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23
```

If anything later goes wrong, restore with:

```bash
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot
git reset --hard feature/ION-12316-visibiilty-aws-upgrade-copilot-backup-2026-06-23
```

Log the backup branch/tag name and the original tip SHA in session context (`progress`).

---

## Step 2 — Gather Ticket Context

Use the MCP context server:

```
jira_get_issue: ION-12316
```

Read the description, acceptance criteria, and comments. Note any scope, environment, or table-name constraints. Log findings in session context (`finding`).

---

## Step 3 — Assess the Feature Branch & Squash to One Commit

Confirm you are on the feature branch and count outgoing commits:

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
git branch --show-current                 # expect: feature/ION-12316-visibiilty-aws-upgrade-copilot
git status --short                         # ensure clean; stash if needed (git stash -u)
git fetch origin
git log --oneline develop..HEAD            # how many outgoing commits?
```

- If **one** commit → continue to Step 4.
- If **multiple** commits → squash into one (local only, no push):

```bash
N=<number-of-outgoing-commits>
git rebase -i HEAD~$N
# mark the first as 'pick', all others as 'fixup' (or 'squash' to combine messages)
```

After squashing, verify a single commit and that its message contains `ION-12316` (reword now or at Step 8):

```bash
git log --oneline develop..HEAD            # must be exactly 1 line
git log -1 --format="%B"
```

Log the squash result in session context (`progress`).

---

## Step 4 — Update develop & Analyze Conflict Risk

```bash
git checkout develop
git pull origin develop
git checkout feature/ION-12316-visibiilty-aws-upgrade-copilot

MERGE_BASE=$(git merge-base develop HEAD)

# develop commits since divergence touching visibility
git log --oneline HEAD..develop -- visibility/

# files changed on BOTH sides (potential conflicts)
comm -12 \
  <(git diff --name-only $MERGE_BASE..HEAD | sort) \
  <(git diff --name-only $MERGE_BASE..develop | sort)
```

For each overlapping file, diff both sides to predict conflicts. Log the risk assessment (`finding`).

---

## Step 5 — Rebase onto Develop & Resolve Conflicts

```bash
git rebase develop
```

For every conflict:
1. `git diff --name-only --diff-filter=U` to list conflicts.
2. Compare intentions:
   - feature (AWS upgrade): `git diff $MERGE_BASE..REBASE_HEAD -- <file>`
   - develop (latest functional): `git diff $MERGE_BASE..develop -- <file>`
3. **Resolution rule (constraint #5)**: keep develop's latest **functional** logic, then re-apply the **AWS-upgrade** transformation (cloud-sdk client swap, entity re-annotation, converter changes, Guice wiring) on top of it. Never sacrifice a develop functional change to preserve an upgrade change — combine them.
4. `git add <file>` → `git rebase --continue`.
5. If unrecoverable: `git rebase --abort` and reassess.

**Post-rebase compilation health check** (newly merged develop files may import classes the upgrade renamed/removed — these won't show as conflicts):

```bash
mvn test-compile -pl visibility -am -q
```

Fix any broken imports/usages introduced by newly merged develop files by applying the same AWS-upgrade change to them. Log each conflict + resolution (`decision`/`code_change`).

---

## Step 6 — Apply the Design/Impl Review Comments

Source review:
`visibility/docs/2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md`

Address the findings, with these explicit user directives:

- **HIGH-1 / MEDIUM-5 — `MetaDataAttributeConverter`**: Make it **symmetric with its siblings**. Write `metaData` as a DynamoDB **String (S)** — a JSON string via the canonical `MetaData.toJsonString()` — and declare `attributeValueType() == S`. Keep a **lenient read** that accepts both legacy `S` and any stray `M` rows. Delete the bespoke `ObjectMapper` and `MetaDataDynamoDbMixIn`; round-trip through `MetaData.toJsonString()` / `MetaData.parseJson()`. This restores the `visibility-s3-archiver` contract and 1.x backward compatibility. Re-point the archiver test through the **real** converter.
- **HIGH-2 — `cloudSdkDynamoDbConfig`**: Ensure the DynamoDB config the new module requires is present for **all** `visibility/conf/*/config.yaml` environments (sample/qa/int/cvt/prod/pullRequest) so apps boot. Prefer aligning with how **booking** and **network** already wire their cloud-sdk dynamo config rather than carrying a divergent dual-config; document the chosen approach.
- **HIGH-3 — Table-name prefix (USER DIRECTIVE)**: The table-name prefix must **align with the way the `booking` and `network` modules fetch/derive it**. Verify the resolved physical table names exactly equal the legacy `environment + "_" + tableName` names (mind the **trailing underscore**) for at least `container_events`, `container_events_outbound`, `container_events_pending`, and `booking_BookingDetail`. Confirm with one round-trip integration check per table. Backward compatibility of table names is mandatory.
- **MEDIUM-4 — JSON date encoding in S/JSON blobs**: Match the **legacy** encoding for the submission/enriched JSON blobs (1.x: default `ObjectMapper`, `WRITE_DATES_AS_TIMESTAMPS=true`, no `JavaTimeModule`) unless there is a deliberate, documented reason. Avoid two date encodings coexisting in the same attribute. Keep reads tolerant.
- **MEDIUM-6 — Retry scope**: Narrow `ContainerEventDao.findById` retry from `RuntimeException` to the cloud-sdk throughput/throttling (transient) equivalent only; let other exceptions propagate immediately.
- **LOW-7 / LOW-8**: Track as follow-ups or address if low-risk; if left as-is, document the deliberate trade-off (GSI full deserialization; S3 numeric `BigDecimal` → `String`). Do not regress backward compatibility.
- **LOW-9 (committed `booking-3.0.0.M.jar`) — OK TO LIVE WITH**: Per user, **leave LOW-9 as-is**. No action required; just note it.

**Backward-compat invariant for every change**: all encoding/decoding must align with existing 1.x visibility — reads tolerate legacy data, writes reproduce the legacy on-disk format. Add/extend tests proving legacy-format round-trips.

For each addressed comment, add unit and (where AWS interaction is involved) DynamoDB integration test coverage. Log each change (`code_change`) and the review item it resolves.

---

## Step 7 — Document the Rebase + Refactor

Create `visibility/docs/2026-06-23-visibility-rebase-refactor.md` containing:

1. **Summary** — goal, branch, single-commit outcome, model used (Claude Opus 4.8, 1M context).
2. **Git steps & commands** — the exact backup, squash, fetch/pull, `merge-base`, conflict-analysis, `rebase`, conflict-resolution, `commit --amend`, and verification commands actually run (Steps 1, 3–5, 8).
3. **Conflict log** — each conflicted file, what develop changed, what the upgrade changed, how they were combined.
4. **Review comments addressed** — per finding (HIGH-1…LOW-9): decision, code change, backward-compat rationale, tests added. Note LOW-9 accepted as-is and the table-prefix alignment with booking/network.
5. **Test & startup results** — `mvn verify -pl visibility` (unit + integration + dynamo), and INT `config.yaml` startup verification per sub-module.
6. **References** — ION-12316, the review doc, relevant booking/network config classes used as the prefix/config template.

Keep this document updated as you proceed; log doc creation in session context (`progress`).

---

## Step 8 — Amend to a Single Commit with ION-12316

Fold all rebase resolutions and review fixes into the **one** outgoing commit:

```bash
git add -A
git commit --amend -m "ION-12316: Visibility AWS SDK 2.x upgrade — rebased on latest develop with review fixes (backward-compatible encoding/decoding, table-name alignment)"

# Verify exactly one outgoing commit
git log --oneline develop..HEAD            # must be 1 line
git log -1 --format="%B"                   # must contain ION-12316
git status -sb
```

Do **not** push.

---

## Step 9 — Verify: Compile, Test, Startup

```bash
# Compile main + tests
mvn test-compile -pl visibility -am -q

# Full unit + integration (incl. DynamoDB integration tests)
mvn verify -pl visibility -am
```

- All tests (unit + integration + dynamo) must PASS. If any fail — related or not — root-cause and FIX (add a reproducing test for any bug first), recompute TODOs, and iterate until green. Log results (`test_result`).
- Confirm every new public method has a unit test and every review fix is covered.

**Startup check (INT)** — for each affected visibility sub-module, confirm it boots with its INT config, e.g.:

```bash
mvn -pl visibility -am clean package
java -jar visibility/<sub-module>/target/<artifact>.jar server visibility/conf/int/config.yaml
```

(Use the correct artifact path per sub-module: `visibility-inbound`, `-outbound`, `-pending`, `-matcher`, `-wm-inbound-processor`, `-itv-gps-processor`, plus the `visibility-s3-archiver` lambda where applicable.) Verify no `IllegalStateException` for missing `cloudSdkDynamoDbConfig` and no table-name `ResourceNotFound`. Log startup results (`test_result`).

---

## Step 10 — Final Verification & Handoff

```bash
git log --oneline develop..HEAD            # exactly 1 commit, message contains ION-12316
git log -1 --format="%B"
git status -sb                             # clean working tree, nothing pushed
```

- Update `visibility/docs/2026-06-23-visibility-rebase-refactor.md` with final commit hash and test/startup results.
- `session_add_context` final summary (`progress`); keep status `active` (user will review before push).
- Tell the user it is ready for review and **not pushed**.

---

## Output Summary — Definition of Done

- [ ] Session context with full traceability (decisions, conflicts, code changes, tests, model info).
- [ ] Backup branch/tag of the original feature branch tip created (local, unpushed).
- [ ] Feature branch squashed + rebased onto latest `develop`.
- [ ] All rebase conflicts resolved by applying AWS-upgrade changes on top of latest functional code.
- [ ] Review comments addressed: HIGH-1/MEDIUM-5 (`MetaData` → S, canonical serializer, lenient read), HIGH-2 (config present for all envs), HIGH-3 (table prefix aligned with booking/network, legacy names preserved), MEDIUM-4 (legacy date encoding), MEDIUM-6 (narrowed retry); LOW-9 accepted as-is.
- [ ] All encoding/decoding backward-compatible with 1.x visibility, proven by tests.
- [ ] `visibility/docs/2026-06-23-visibility-rebase-refactor.md` documenting git steps and all changes.
- [ ] Exactly **one** outgoing commit, message contains `ION-12316`, **not pushed**.
- [ ] Everything compiles, all tests (unit + integration + dynamo) pass, modules start with INT config.
