---
name: "Ocean Schedules AWS SDK 2.x Upgrade — Full Implementation"
description: "Complete the oceanschedules and oceanschedules-process modules AWS SDK 2.x upgrade using cloud-sdk libraries. Creates a NEW plan (peer-reviewed), a detailed design doc, a feature branch, implements all changes with full test coverage, and verifies startup. Use when: oceanschedules aws upgrade, implement oceanschedules cloud-sdk, ION-11462"
argument-hint: "none"
agent: agent
model: "Claude Opus 4.8 (copilot)"
tools:
  - execute
  - read
  - edit
  - search
  - agent
  - web
  - mcp-context-server/*
---

# Ocean Schedules — AWS SDK 2.x Upgrade: Full Implementation Agent

You are an expert enterprise Java refactoring agent. Your mission is to **fully implement** the AWS SDK 2.x upgrade for the `oceanschedules` and `oceanschedules-process` modules (and all their sub-modules) using `cloud-sdk-api` and `cloud-sdk-aws` libraries from `mercury-services-commons`.

**Model**: You MUST use **Claude Opus** (Claude Opus 4.6).
**Jira Ticket**: ION-11462
**Feature Branch**: `feature/ION-11462-os-aws-upgrade-copilot`

You must follow the workspace `copilot-instructions.md` for project structure, conventions, code-quality rules, and the session-context protocol. Various modules have already been upgraded (auth, network, booking-bridge, registration, webbl, tx-tracking, self-service-reports, db-migration, booking) — follow the **same standards**. Use **`booking`** and **`auth`** as the primary reference modules.

---

## CRITICAL CONSTRAINTS

1. **You may ONLY modify files in the `oceanschedules/` and `oceanschedules-process/` modules** (and their sub-modules). No other modules may be changed.
2. **You CANNOT delete any files.** You can create new files and edit existing files only.
3. **You may READ any file** in this workspace (`mercury-services`) and in `C:\Users\arijit.kundu\projects\mercury-services-commons`.
4. **You have permission** to run `mvn` commands, `git` commands, and use all MCP context server tools. **You must NEVER push to the `develop` branch.**
5. **AWS credentials are available** in the terminal. Verify with `aws sts get-caller-identity` before any AWS operations.
6. **Commit messages MUST contain** `ION_11462` in the text.
7. Use the **most efficient and performant** design and implementation. Do not take shortcuts that compromise code quality or stability.
8. **Complete ALL changes.** The task is not done until everything compiles, all tests (unit + integration) pass, and both applications start successfully.

---

## SESSION CONTEXT PROTOCOL (MANDATORY)

You MUST use the MCP Context Server (`mcp-context-server/*`) throughout this task to record **all progress, findings, decisions, blockers, and resolutions**.

### At START:
1. Call `session_list` to check for existing active sessions related to ION-11462 or oceanschedules AWS upgrade.
2. If a relevant session exists, call `session_get` to load its context and resume from where it left off.
3. If no session exists, call `session_create` with:
   - name: `ION-11462-oceanschedules-aws-upgrade-impl`
   - project: `mercury-services`
   - tags: `["oceanschedules", "oceanschedules-process", "aws-upgrade", "cloud-sdk", "ION-11462", "implementation"]`

### DURING execution:
- Call `session_add_context` after **every significant action**:
  - `decision` — Architecture decisions, design choices
  - `finding` — Code discoveries, dependency analysis results (include `git_log` / `kb_search` findings)
  - `blocker` — Issues encountered
  - `progress` — Steps completed, files changed
  - `code_change` — Specific code modifications with file paths
  - `test_result` — Test execution results (pass/fail counts)
  - `model_info` — Log that you are using Claude Opus 4.6
- Include file paths, error snippets, and test results in `references` and `detail` fields.

### At END:
- Add a final summary entry with category `progress` containing all changes made and all resolutions.
- Call `session_update_status` to mark `completed` if all work is done, or `active` if more work remains.

### Context Window Management:
- If context window capacity crosses 85% and TODOs remain, persist ALL important details in session context, link the old and new sessions, then open a new chat session and resume with a summary of what's done and what remains.

---

## REFERENCE DOCUMENTS (guidance only — VERIFY against current code)

These documents may not reflect the most recent changes. **Verify against the live codebase and proceed.**

- `oceanschedules/docs/os-aws2x-plan.md` — Prior upgrade plan
- `oceanschedules/docs/oceanschedules-architecture-design-claude.md` — Architecture
- `oceanschedules/docs/05042026-oceanschedules-business-rules-claude.md` — Business rules
- `oceanschedules/docs/DESIGN-PRE-AWS-upgrade.md` — Current-state analysis
- `oceanschedules/docs/CONFLUENCE-os.md` — Confluence design doc
- `.github/prompts/visibility-aws-upgrade-impl.prompt.md` — Reference prompt (this prompt is modeled on it)

---

## EXECUTION PHASES

Execute the following phases **in order**. Do not skip phases. Verify compilation and tests between phases.

### PHASE 0 — Preparation & Context Loading

1. Load any existing session context related to ION-11462 or oceanschedules upgrade.
2. Verify AWS credentials: `aws sts get-caller-identity`.
3. Ensure `develop` is up to date: `git checkout develop && git pull origin develop`.
4. Read and internalize the reference documents listed above.
5. Read reference implementations from already-upgraded modules:
   - `booking/` — DynamoDB entities, AttributeConverters, DAOs, Guice modules, Lambda, backward compatibility
   - `auth/` — Integration test patterns, DynamoDB integration tests
   - `booking-bridge/`, `webbl/`, `network/`, `registration/` — additional patterns
   - `cloud-sdk-api` and `cloud-sdk-aws` source in `C:\Users\arijit.kundu\projects\mercury-services-commons`
6. Read and understand the full structure of both modules and all sub-modules:
   - `oceanschedules/` — Dropwizard REST API service
   - `oceanschedules-process/` sub-modules: `common`, `collector`, `inbound`, `aggregator`, `loader`, `maps`, `outbound`, `port-pair-generator`, `staging`
7. Use `git_log` and `kb_search` to understand recent changes and find all AWS SDK v1 usages. Record findings in session context and surface them in your summary.
8. Check Jira: call `jira_get_issue` with key `ION-11462` for requirements and acceptance criteria.
9. Log model info in session: `session_add_context` with category `model_info`, detail: "Agent using Claude Opus 4.6".

### PHASE 1 — Create a NEW Detailed Plan

Create a **comprehensive NEW implementation plan** (do not just reuse the old one — verify it against current state). The plan must cover:

1. **Current state analysis** — Enumerate every AWS SDK v1 usage (`dynamo-client`, `AmazonS3`, `AmazonSQS`, `AmazonSNS`, `AmazonSSM`, EMR/Spark clients) across `oceanschedules` and all `oceanschedules-process` sub-modules. Note anything in reference docs that is now stale.
2. **Dependency analysis** — Map sub-module dependency chain; identify build order (`common` first).
3. **Migration order** — Exact order of changes (POM → `oceanschedules-process/common` → API module → remaining sub-modules → lambdas/Spark jobs).
4. **Risk assessment** — Backward-compatibility risks (especially DynamoDB date/boolean/number format issues — apply lessons from the booking upgrade).
5. **Test strategy** — Unit + integration test approach per sub-module.
6. **cloud-sdk gap analysis** — A dedicated section for any AWS service that `cloud-sdk-api`/`cloud-sdk-aws` does NOT yet support (see "COMMONS GAP HANDLING" below).

**Output**: Publish the plan to `oceanschedules-process/docs/2026-05-31-os-aws-upgrade-plan.md` (create the `oceanschedules-process/docs/` folder if missing).

Log the plan as a `decision` entry in session context.

### PHASE 1.1 — Plan Review by a Sub-Agent

After creating the plan, invoke a sub-agent (the `Explore` / general-purpose agent) to **review the plan**:
- Verify the plan against the actual codebase structure.
- Check for any AWS SDK v1 usages not covered in the plan.
- Validate the migration order and dependency chain.
- Validate the cloud-sdk gap analysis is accurate.

Incorporate feedback into the plan. Log review findings in session context with category `finding`.

### PHASE 2 — Detailed Design Document

Based on the reviewed plan, create the design document at `oceanschedules/docs/2026-05-31-os-aws2x-upgrade-design-copilot.md` with:

1. **Executive Summary** — Scope, objectives, approach.
2. **Class Diagrams** (Mermaid) — Old vs new class hierarchies for DynamoDB entity classes, DAO migration from `DynamoDBCrudRepository` to `DatabaseRepository`, AttributeConverter implementations, Guice module structure.
3. **Component Diagrams** (Mermaid) — `oceanschedules-process/common` shared components, each service's internal structure, Spark/Lambda components, and how `cloud-sdk-api`/`cloud-sdk-aws` integrate.
4. **Deployment Diagrams** (Mermaid) — Service/job deployment topology and AWS resource connections (DynamoDB, SQS, SNS, S3, SSM, EMR/Spark).
5. **Sequence Diagrams** (Mermaid) — Key flows: collection/polling, inbound parse, aggregation, loading, outbound, port-pair generation, staging.
6. **Maven Dependencies** — Complete dependency changes for parent POMs and each sub-module POM.
7. **Key Classes & Functions** — For each new/modified class: purpose/responsibility, key method signatures, injected dependencies, configuration requirements.
8. **Configuration Details** — YAML config changes per environment (`cvt`, `int`, `qa`, `prod`).
9. **Testing Strategy** — Unit and integration test approach per class.
10. **Data Format Backward Compatibility** — How legacy DynamoDB data is handled.
11. **cloud-sdk Gap / Commons Change Requests** — Full technical specifications for anything that must be added to `mercury-services-commons` (see below).
12. **All changes made** — Complete, running list of files created/modified with descriptions. **Keep this updated throughout implementation.**

Log design-document creation in session context.

### PHASE 3 — Feature Branch Creation

```bash
git checkout develop
git pull origin develop
git checkout -b feature/ION-11462-os-aws-upgrade-copilot
```

Verify the branch is created and checked out. Log in session context.

### PHASE 4 — Implementation: POM & Dependencies

1. Update `oceanschedules/pom.xml` and `oceanschedules-process/pom.xml` — Add cloud-sdk properties, remove `dynamo-client` / AWS SDK v1 references.
2. Update each sub-module POM — Add `cloud-sdk-api`, `cloud-sdk-aws`, and `dynamo-integration-test` dependencies.
3. Verify compilation: `mvn compile -pl oceanschedules -am` and `mvn compile -pl oceanschedules-process -am`.
4. Commit: `git commit -m "ION_11462: Update oceanschedules POM dependencies for cloud-sdk migration"`.

### PHASE 5 — Implementation: oceanschedules-process/common (Core Library)

This is the most critical phase — all sub-modules depend on it.

1. **DynamoDB Entity Migration** — Migrate entity classes from SDK v1 to SDK v2 annotations (`@DynamoDbBean`, `@DynamoDbPartitionKey`, `@DynamoDbSortKey`, `@DynamoDbConvertedBy`, `@DynamoDbSecondaryPartitionKey`). Remove `@DynamoDBDocument` from nested models.
2. **AttributeConverter Implementations** — Create converters following booking/webbl patterns, including date converters (`DateEpochMilliSecondAttributeConverter`, `DateIso8601AttributeConverter`, `DateEpochSecondAttributeConverter`) with backward-compatible parsing.
3. **DAO Migration** — Migrate DAOs from `DynamoDBCrudRepository` to `DatabaseRepository`.
4. **SQS Migration** — Replace SQS wrappers with `cloud-sdk-api MessagingClient<String>`.
5. **S3 Migration** — Replace `AmazonS3` with `cloud-sdk-api StorageClient`.
6. **SNS Migration** — Replace custom SNS with `cloud-sdk-api NotificationService`.
7. **SSM Migration** — Replace `AmazonSSM` with cloud-sdk parameter store.
8. **Guice Module Changes** — Create the necessary cloud-sdk Guice modules (Dynamo, Messaging, Storage, Notification).
9. **Configuration Classes** — Add `BaseDynamoDbConfig` and related config to the configuration classes.

**After each sub-step**: `mvn compile -pl oceanschedules-process/common`.

**Unit Tests**: JUnit 5 + AssertJ + parameterized tests for all converters (legacy SDK v1 and new SDK v2 formats), DAO methods, and client wrappers.

**Integration Tests**: DynamoDB integration tests using `dynamo-integration-test` following booking/auth patterns — pre-populate DynamoDB Local with legacy fixtures, read via new converters (no exceptions), write/read round-trip consistency, GSI queries.

Verify: `mvn test -pl oceanschedules-process/common`.
Commit: `git commit -m "ION_11462: Migrate oceanschedules-process/common to cloud-sdk libraries"`.

### PHASE 6 — Implementation: oceanschedules (API Module)

- Update Guice injector modules to install the new cloud-sdk modules.
- Migrate all AWS client references (DynamoDB DAOs, SQS, S3, SNS, SSM).
- Write unit tests (JUnit 5, AssertJ, parameterized) and integration tests (`dynamo-integration-test`).
- Verify: `mvn test -pl oceanschedules`.
- Commit with `ION_11462` prefix.

### PHASE 7 — Implementation: Remaining oceanschedules-process Sub-Modules

For each, in dependency order: `collector`, `inbound`, `aggregator`, `loader`, `maps`, `outbound`, `port-pair-generator`, `staging`.

For each sub-module:
- Install new cloud-sdk Guice modules; migrate SQS processors to `QueueMessage<String>`; update all AWS client references; migrate Spark-job AWS clients and any Lambda functions (use factory methods, no Guice DI for lambdas — follow booking Lambda pattern).
- Write unit tests (JUnit 5, AssertJ, parameterized) and integration tests (`dynamo-integration-test`).
- Verify: `mvn test -pl oceanschedules-process/<sub-module>`.
- Commit with `ION_11462` prefix.

### PHASE 8 — Full Verification

1. Full build + all tests:
   ```bash
   mvn clean verify -pl oceanschedules -am
   mvn clean verify -pl oceanschedules-process -am
   ```
2. Integration tests (DynamoDB Local):
   ```bash
   mvn verify -pl oceanschedules-process -am -P integration-test
   ```
3. **Verify application startup** for both the `oceanschedules` Dropwizard API and the `oceanschedules-process` services using the env config files under `conf/int` (e.g., `java -jar <module>/target/<jar> server <module>/conf/int/config.yaml`). Confirm clean startup with no AWS-client wiring errors.
4. Fix any failures before proceeding. Do NOT skip failing tests.
5. Log all test results and startup results in session context.

### PHASE 9 — Documentation

Update `oceanschedules/docs/2026-05-31-os-aws2x-upgrade-design-copilot.md` with:
- Complete list of all files created and modified.
- All design diagrams (finalized).
- Test coverage summary (unit + integration).
- Any issues encountered and how they were resolved.
- Configuration changes needed per environment.
- The `cloud-sdk Gap / Commons Change Requests` section (finalized, with full technical specs).
- Tooling commands used.

### PHASE 10 — Wrap-Up (NO push, NO PR)

1. Ensure all changes are committed with `ION_11462` in commit messages.
2. **Do NOT push and do NOT create a PR.** Produce complete documentation describing all changes for review.
3. Add a final session summary entry and set session status appropriately.

---

## COMMONS GAP HANDLING (cloud-sdk-api / cloud-sdk-aws)

If `cloud-sdk-api`/`cloud-sdk-aws` do **not** provide an API or implementation for a specific AWS service used by oceanschedules (e.g., EMR/Spark orchestration, a specific SSM or S3 operation, batch/EMR clients):

1. **Flag it clearly** in the design doc under "cloud-sdk Gap / Commons Change Requests" and mark it as a `TODO` in code with `// TODO(ION-11462): requires commons change — <detail>`.
2. Provide a **complete technical specification** so it can be implemented separately in the `mercury-services-commons` workspace and provided for integration. The spec MUST include:
   - Proposed interface(s) in `cloud-sdk-api` (method signatures, parameters, return types, exceptions).
   - Proposed AWS SDK 2.x implementation approach in `cloud-sdk-aws` (service client, key operations).
   - Factory/Guice wiring expectations.
   - Configuration model additions.
   - Test expectations (unit + integration).
3. **Use a temporary workaround** if possible to complete the task end-to-end (e.g., a thin local adapter in the oceanschedules module that mirrors the proposed commons API), clearly marked as a temporary `TODO` to be replaced once commons is updated. The workaround must not compromise test coverage.
4. Record each gap as a `blocker` entry in session context.

---

## TESTING STANDARDS

### Unit Tests
- **Framework**: JUnit 5 (Jupiter) with Mockito for mocking.
- **Assertions**: AssertJ (`assertThat(result).isEqualTo(expected)`).
- **Parameterized Tests**: Use `@ParameterizedTest` with `@ValueSource`, `@MethodSource`, or `@CsvSource` wherever multiple inputs apply.
- **Nested Tests**: Use `@Nested` to group related cases.
- **Coverage**: Every new public method MUST have a unit test.
- **Naming**: `should_expectedBehavior_when_condition`.

### Integration Tests
- Use the `dynamo-integration-test` module from `mercury-services-commons`.
- Follow existing patterns in `booking/` and `auth/`.
- Mark with `@Category(IntegrationTests.class)`.
- Test against DynamoDB Local.
- Test backward compatibility with legacy SDK v1 data formats.
- Test all CRUD operations and GSI queries.

---

## DATA FORMAT BACKWARD COMPATIBILITY

Apply lessons learned from the booking upgrade:
1. **Date/Time fields** — Flexible deserializers handling both `T` and space separators.
2. **Boolean fields** — Handle both string `"1"` and numeric `1` for DynamoDB `N` type.
3. **OffsetDateTime** — Use pattern `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` to handle both `Z` and `+00:00` offsets.
4. **All AttributeConverters MUST be tested against**: SDK v1 (legacy) data, SDK v2 (new) data, null/empty values, and edge cases (epoch 0, empty strings, missing fields).

---

## ERROR HANDLING

- If tests fail, diagnose and fix before proceeding. Do NOT skip failing tests.
- If compilation fails, resolve all errors before moving on.
- If you hit a blocker, log it in session context and attempt resolution.
- If a blocker cannot be resolved, document it clearly and inform the user.

---

## QUALITY GATES (per phase)

- [ ] All code compiles without errors.
- [ ] All existing tests still pass.
- [ ] All new tests pass.
- [ ] No AWS SDK v1 imports remain in modified files.
- [ ] All public methods have unit tests.
- [ ] Integration tests pass against DynamoDB Local.
- [ ] Changes committed with `ION_11462` in the message.
- [ ] Progress logged in session context.

---

## FINAL DELIVERABLES

1. NEW plan at `oceanschedules-process/docs/2026-05-31-os-aws-upgrade-plan.md` (peer-reviewed by a sub-agent).
2. Design document at `oceanschedules/docs/2026-05-31-os-aws2x-upgrade-design-copilot.md` with all diagrams, details, and the running change list.
3. Feature branch `feature/ION-11462-os-aws-upgrade-copilot` with all changes committed (`ION_11462` in messages).
4. All tests passing (unit + integration).
5. `oceanschedules` and `oceanschedules-process` applications start successfully.
6. Any cloud-sdk gaps clearly flagged with full technical specs and `TODO`s.
7. Complete session context log of all work, findings, and resolutions.

Complete all the above and I will review.
