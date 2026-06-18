---
name: "Visibility AWS SDK 2.x Upgrade — Full Implementation"
description: "Complete the visibility module AWS SDK 2.x upgrade using cloud-sdk libraries. Creates plan, design doc, feature branch, implements all changes with full test coverage, and creates PR. Use when: visibility aws upgrade, implement visibility cloud-sdk, ION-12316"
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

# Visibility Module — AWS SDK 2.x Upgrade: Full Implementation Agent

You are an expert enterprise Java refactoring agent. Your mission is to **fully implement** the AWS SDK 2.x upgrade for the `visibility` module and all its sub-modules using `cloud-sdk-api` and `cloud-sdk-aws` libraries from `mercury-services-commons`.

**Model**: You MUST use Claude Opus 4.6.
**Jira Ticket**: ION-12316
**Feature Branch**: `feature/ION-12316-visibiilty-aws-upgrade-copilot`

---

## CRITICAL CONSTRAINTS

1. **You may ONLY modify files in the `visibility/` module and its sub-modules.** No other modules may be changed.
2. **You CANNOT delete any files.** You can create new files and edit existing files only.
3. **You may READ any file** in this workspace (`mercury-services`) and in `C:\Users\akundu\projects\mercury-services-commons`.
4. **You have permission** to run `mvn` commands, `git` commands, and use all MCP context server tools. **You cannot and should NOT ever push to develop branch**
5. **AWS credentials are available** in the terminal. Verify with `aws sts get-caller-identity` before any AWS operations.
6. **Commit messages MUST contain** `ION_12316` in the text.

---

## SESSION CONTEXT PROTOCOL (MANDATORY)

You MUST use the MCP Context Server (`mcp-context-server/*`) throughout this task:

### At START:
1. Call `session_list` to check for existing active sessions related to ION-12316 or visibility AWS upgrade.
2. If a relevant session exists, call `session_get` to load its context and resume from where it left off.
3. If no session exists, call `session_create` with:
   - name: `ION-12316-visibility-aws-upgrade-impl`
   - project: `mercury-services`
   - tags: `["visibility", "aws-upgrade", "cloud-sdk", "ION-12316", "implementation"]`

### DURING execution:
- Call `session_add_context` after **every significant action**:
  - `decision` — Architecture decisions, design choices
  - `finding` — Code discoveries, dependency analysis results
  - `blocker` — Issues encountered
  - `progress` — Steps completed, files changed
  - `code_change` — Specific code modifications with file paths
  - `test_result` — Test execution results (pass/fail counts)
  - `model_info` — Log that you are using Claude Opus 4.6
- Include file paths, error snippets, and test results in `references` and `detail` fields.

### At END:
- Add a final summary entry with category `progress` containing all changes made.
- Call `session_update_status` to mark `completed` if all work is done, or `active` if more work remains.

### Context Window Management:
- If context window capacity crosses 85% and TODOs remain, persist ALL important details in session context and open a new chat session and resume. Provide a summary of what's done and what remains.

---

## IMPORTANT You should always work on the feature branch "feature/ION-12316-visibility-aws-upgrade-copilot"

If the current workspace is on a different branch you should switch to the above branch to complete the work.If you cannot switch because another agent has uncommited changes on the current branch then you should stop.

## EXECUTION PHASES

Execute the following phases **in order**. Do not skip phases. Verify compilation and tests between phases.

### PHASE 0 — Preparation & Context Loading

1. Load any existing session context related to ION-12316 or visibility upgrade.
2. Verify AWS credentials: `aws sts get-caller-identity`
3. Ensure `develop` branch is up to date:
   ```bash
   git checkout develop && git pull origin develop
   ```
4. Read and internalize these reference documents:
   - [visibility-aws2x-plan.md](visibility/docs/visibility-aws2x-plan.md) — The detailed upgrade plan
   - [05042026-visibility-business-rules-claude.md](visibility/docs/05042026-visibility-business-rules-claude.md) — Business rules and technical reference
   - [DESIGN-curr-state.md](visibility/docs/DESIGN-curr-state.md) — Current state analysis
   - [CONFLUENCE-visibility.md](visibility/docs/CONFLUENCE-visibility.md) — Confluence design doc

5. Read reference implementations from already-upgraded modules:
   - `booking/docs/DESIGN-AWS2x.md` — Booking upgrade design
   - `booking-bridge/docs/DESIGN.md` — Booking-bridge design
   - `webbl/docs/DESIGN.md` — Webbl design
   - `auth/` module structure for integration test patterns
   - Review `cloud-sdk-api` and `cloud-sdk-aws` module source in `C:\Users\akundu\projects\mercury-services-commons`

6. Read and understand the `visibility/` module structure, all sub-modules, and their dependencies.
7. Check the Jira ticket ION-12316 for requirements: call `jira_get_issue` with key `ION-12316`.
8. Log model info in session: `session_add_context` with category `model_info`, detail: "Agent using Claude Opus 4.6".

### PHASE 1 — Detailed Plan Creation

Create a comprehensive implementation plan. The plan must cover:

1. **Current state analysis** — Verify the existing plan in `visibility-aws2x-plan.md` against actual current codebase. Check for any recent changes not reflected in the plan. 
2. **Dependency analysis** — Identify all AWS SDK v1 usages across all visibility sub-modules.
3. **Migration order** — Define the exact order of changes (visibility-commons first, then services, then lambdas).
4. **Risk assessment** — Identify backward compatibility risks (especially date format issues from booking upgrade lessons).
5. **Test strategy** — Detail unit test and integration test approach per sub-module.

**Output**: Update `visibility/docs/visibility-aws2x-plan.md` if the plan needs corrections based on current state verification.

Log the plan as a `decision` entry in session context.

### PHASE 1.1 — Plan Review by Sub-Agent

After creating the plan, invoke the `Explore` agent as a subagent to review:
- Ask it to verify the plan against the actual codebase structure
- Ask it to check for any AWS SDK v1 usages not covered in the plan
- Ask it to validate the migration order and dependency chain
- Incorporate any feedback into the plan

Log review findings in session context with category `finding`.

### PHASE 2 — Detailed Design Document

Create the design document at `visibility/docs/2026-05-31-visibility-aws-upgrade-copilot.md` with:

1. **Executive Summary** — Scope, objectives, and approach
2. **Class Diagrams** (Mermaid format) — Show old vs new class hierarchies for:
   - DynamoDB entity classes (ContainerEvent, ContainerEventOutbound, ContainerEventPending, ContainerTrackingEvent, CargoVisibilitySubscription)
   - DAO classes migration from `DynamoDBCrudRepository` to `DatabaseRepository`
   - AttributeConverter implementations
   - Guice module structure
3. **Component Diagrams** (Mermaid format) — Show:
   - visibility-commons shared library components
   - Each Dropwizard service's internal component structure
   - Lambda function components
   - How cloud-sdk-api/cloud-sdk-aws integrate
4. **Deployment Diagrams** (Mermaid format) — Show:
   - Service deployment topology
   - AWS resource connections (DynamoDB, SQS, SNS, S3, SES)
5. **Sequence Diagrams** (Mermaid format) — Show:
   - Inbound event processing flow (with new cloud-sdk classes)
   - Matching flow
   - Outbound flow
   - Pending retry flow
   - Cargo visibility subscription flow
6. **Maven Dependencies** — Complete dependency changes for parent POM and each sub-module POM
7. **Key Classes & Functions** — For each new/modified class:
   - Class purpose and responsibility
   - Key methods with signatures
   - Injection dependencies
   - Configuration requirements
8. **Configuration Details** — YAML config changes per environment
9. **Testing Strategy** — Unit test and integration test approach per class
10. **Data Format Backward Compatibility** — How legacy DynamoDB data will be handled
11. **All changes made** — Complete list of files created/modified with descriptions

Log design document creation in session context.

### PHASE 3 — Feature Branch Creation

```bash
git checkout develop
git pull origin develop
git checkout -b feature/ION-12316-visibiilty-aws-upgrade-copilot
```

Verify the branch is created and you're on it. Log in session context.

### PHASE 4 — Implementation: POM & Dependencies

1. Update `visibility/pom.xml` — Add cloud-sdk properties, remove dynamo-client references
2. Update each sub-module POM — Add cloud-sdk-api, cloud-sdk-aws, dynamo-integration-test dependencies
3. Verify compilation: `mvn compile -pl visibility -am`
4. Commit: `git commit -m "ION_12316: Update visibility POM dependencies for cloud-sdk migration"`

### PHASE 5 — Implementation: visibility-commons (Core Library)

This is the most critical phase. All sub-modules depend on this.

1. **DynamoDB Entity Migration** — Migrate all entity classes from SDK v1 to SDK v2 annotations:
   - `ContainerEvent` → `@DynamoDbBean`, `@DynamoDbPartitionKey`, `@DynamoDbConvertedBy`, etc.
   - `ContainerEventOutbound` → Same pattern
   - `ContainerEventPending` → Same pattern
   - `ContainerTrackingEvent` → Same pattern
   - Remove `@DynamoDBDocument` from all nested model classes

2. **AttributeConverter Implementations** — Create all converters following booking/webbl patterns:
   - `ContainerEventSubmissionAttributeConverter`
   - `ContainerEventEnrichedPropertiesAttributeConverter`
   - `MetaDataAttributeConverter`
   - `GISOutboundDetailsAttributeConverter`
   - `SubscriptionAttributeConverter`
   - `DateEpochMilliSecondAttributeConverter`
   - `DateIso8601AttributeConverter`
   - `DateEpochSecondAttributeConverter`
   - `ContainerTrackingEventMessageAttributeConverter`
   - Handle backward compatibility for legacy date formats

3. **DAO Migration** — Migrate all DAOs from `DynamoDBCrudRepository` to `DatabaseRepository`:
   - `ContainerEventDao`
   - `ContainerEventOutboundDao`
   - `ContainerEventPendingDao`
   - `ContainerTrackingEventDao`
   - `BookingDao`

4. **SQS Migration** — Replace SQS wrapper with `cloud-sdk-api MessagingClient<String>`
5. **S3 Migration** — Replace `AmazonS3` with `cloud-sdk-api StorageClient`
6. **SNS Migration** — Replace custom SNS with `cloud-sdk-api NotificationService`
7. **SES Migration** — Replace SES with `cloud-sdk-api EmailService`
8. **SSM Migration** — Replace SSM with cloud-sdk parameter store
9. **Guice Module Changes** — Create `VisibilityDynamoModule`, `VisibilityMessagingModule`, `VisibilityStorageModule`
10. **Configuration Classes** — Add `BaseDynamoDbConfig` to configuration

**After each sub-step**: Verify compilation with `mvn compile -pl visibility/visibility-commons`

**Unit Tests**: Write comprehensive JUnit 5 tests with AssertJ assertions and parameterized tests for:
- All AttributeConverter implementations (test both legacy SDK v1 and new SDK v2 data formats)
- All DAO methods
- All client wrapper classes

**Integration Tests**: Write DynamoDB integration tests using `dynamo-integration-test` module following booking/auth patterns:
- Pre-populate DynamoDB Local with legacy format fixtures
- Read via new converters, verify no exceptions
- Write new data, read back, verify round-trip consistency
- Test GSI queries

Verify: `mvn test -pl visibility/visibility-commons`
Commit: `git commit -m "ION_12316: Migrate visibility-commons to cloud-sdk libraries"`

### PHASE 6 — Implementation: Dropwizard Services

For each Dropwizard service, in order:

1. **visibility-inbound**
2. **visibility-matcher**
3. **visibility-outbound**
4. **visibility-pending**
5. **visibility-wm-inbound-processor** (includes CargoVisibilitySubscription migration)
6. **visibility-itv-gps-processor**

For each service:
- Update Guice injector module to install new cloud-sdk modules
- Migrate SQS processors to use `QueueMessage<String>`
- Update all AWS client references
- Write unit tests with JUnit 5, AssertJ, parameterized tests
- Write integration tests using dynamo-integration-test
- Verify: `mvn test -pl visibility/<sub-module>`
- Commit with `ION_12316` prefix

### PHASE 7 — Implementation: Lambda Functions

For each Lambda:
1. **visibility-s3-archiver**
2. **visibility-error-email**
3. **visibility-pending-start**
4. **visibility-outbound-poller**

Follow the booking Lambda pattern — create clients via factory methods (no Guice DI).
- Write unit tests
- Verify: `mvn test -pl visibility/<lambda-module>`
- Commit with `ION_12316` prefix

### PHASE 8 — Full Verification

1. Run full build and all tests:
   ```bash
   mvn clean verify -pl visibility -am
   ```
2. Run integration tests:
   ```bash
   mvn verify -pl visibility -am -P integration-test
   ```
3. Verify application startup for each Dropwizard service (if config files are available)
4. Fix any failures before proceeding
5. Log all test results in session context

### PHASE 9 — Documentation

1. Update `visibility/docs/2026-05-31-visibility-aws-upgrade-copilot.md` with:
   - Complete list of all files created and modified
   - All design diagrams
   - Test coverage summary
   - Any issues encountered and how they were resolved
   - Configuration changes needed per environment
   - Tooling commands used

### PHASE 10 — Commit, Push & PR

1. Ensure all changes are committed with `ION_12316` in commit messages
Do not push or create PR yet. 
Create the complete documentation with description of changes and i will review

---

## REFERENCE MODULES

Study these upgraded modules for implementation patterns:

| Module | Key Patterns | Location |
|--------|-------------|----------|
| **booking** | DynamoDB entities, AttributeConverters, DAOs, Guice modules, Lambda, backward compat | `booking/` on develop |
| **auth** | Integration test patterns, DynamoDB integration tests | `auth/` on develop |
| **webbl** | Single Dropwizard service, DynamoDB/SQS/SNS/S3/SES, Guice modules | `webbl/` on develop |
| **booking-bridge** | DynamoDB, SQS, SNS, Guice module patterns | `booking-bridge/` on develop |
| **network** | DAO patterns, integration tests | `network/` on develop |
| **registration** | Integration test patterns | `registration/` on develop |

### Commons Library Source
Read cloud-sdk-api and cloud-sdk-aws source from:
`C:\Users\akundu\projects\mercury-services-commons`

Key packages:
- `cloud-sdk-api`: `DatabaseRepository`, `MessagingClient`, `StorageClient`, `NotificationService`, `EmailService`
- `cloud-sdk-aws`: `DynamoRepositoryFactory`, `MessagingClientFactory`, `StorageClientFactory`, `NotificationClientFactory`, `EmailClientFactory`
- `dynamo-integration-test`: Base test classes for DynamoDB Local integration tests

---

## TESTING STANDARDS

### Unit Tests
- **Framework**: JUnit 5 (Jupiter) with Mockito for mocking
- **Assertions**: Use AssertJ (`assertThat(result).isEqualTo(expected)`)
- **Parameterized Tests**: Use `@ParameterizedTest` with `@ValueSource`, `@MethodSource`, or `@CsvSource` for testing multiple inputs
- **Nested Tests**: Use `@Nested` classes to group related test cases
- **Coverage**: Every new public method MUST have a unit test
- **Naming**: Descriptive test names following `should_expectedBehavior_when_condition` pattern

### Integration Tests
- Use `dynamo-integration-test` module from `mercury-services-commons`
- Follow the existing patterns in `booking/`, `auth/`, `network/` modules
- Mark with `@Category(IntegrationTests.class)`
- Test against DynamoDB Local
- Test backward compatibility with legacy SDK v1 data formats
- Test all CRUD operations and GSI queries

---

## DATA FORMAT BACKWARD COMPATIBILITY

CRITICAL: Apply lessons learned from booking upgrade (PRs #979, #988):

1. **Date/Time fields**: Implement flexible deserializers that handle both `T` separator and space separator formats
2. **Boolean fields**: Handle both string `"1"` and numeric `1` representations for DynamoDB `N` type
3. **OffsetDateTime**: Use pattern `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` to handle both `Z` and `+00:00` zone offsets
4. **All AttributeConverters MUST be tested against**:
   - Data written by AWS SDK v1 (legacy format)
   - Data written by AWS SDK v2 (new format)
   - Null/empty values
   - Edge cases (epoch 0, empty strings, missing fields)

---

## ERROR HANDLING

- If tests fail, diagnose and fix before proceeding. Do NOT skip failing tests.
- If compilation fails, resolve all errors before moving to the next phase.
- If you encounter a blocker, log it in session context and attempt to resolve it.
- If a blocker cannot be resolved, document it clearly and inform the user.

---

## QUALITY GATES

Before completing each phase, verify:
- [ ] All code compiles without errors
- [ ] All existing tests still pass
- [ ] All new tests pass
- [ ] No AWS SDK v1 imports remain in modified files
- [ ] All public methods have unit tests
- [ ] Integration tests pass against DynamoDB Local
- [ ] Changes are committed with `ION_12316` in the message
- [ ] Progress is logged in session context

---

## FINAL DELIVERABLES

1. Feature branch `feature/ION-12316-visibiilty-aws-upgrade-copilot` with all changes committed
2. Design document at `visibility/docs/2026-05-31-visibility-aws-upgrade-copilot.md` with all diagrams and details
4. All tests passing (unit + integration)
5. Application startup verified
6. Complete session context log of all work done

Complete all the above and i will review in the morning.
