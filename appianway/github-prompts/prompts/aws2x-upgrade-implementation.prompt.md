---
agent: agent
description: Implement the AWS SDK v1 → v2 (cloud-sdk-api / cloud-sdk-aws) upgrade for appianway modules by executing the per-module DESIGN documents produced by the planning prompt. Works one module at a time, shared-first, verifying mvn build + tests at each step, and logs everything to the MCP Context Server.
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

# Appian Way — AWS SDK v2 (cloud-sdk) Upgrade: Implementation

You are an **expert enterprise Java refactoring engineer**. In this prompt you **implement** the migration from **AWS Java SDK v1 (1.12.720)** to **AWS SDK v2** via the **`cloud-sdk-api` / `cloud-sdk-aws`** libraries from `mercury-services-commons`, following the approved per-module DESIGN documents.

Read and obey [.github/copilot-instructions.md](../copilot-instructions.md) in full first — especially **Code Quality Rules**, **Refactoring & Upgrade Guidelines**, **Common Patterns**, and the **Session Context Protocol**.

## Preconditions
- The planning prompt (`aws2x-upgrade-plan-and-design.prompt.md`) has been run and each in-scope module has:
  - `<module>/docs/<date>-<modulename>-aws2x-upgrade-plan-copilot.md`
  - `<module>/docs/<date>-<modulename>-aws2x-upgrade-DESIGN.md`
- If a module's DESIGN doc is missing, **stop and report** — do not improvise the design; ask for it to be planned first.

## Objective
Execute the **recommended option** from each module's DESIGN document so that the module no longer uses AWS SDK v1 directly and instead uses `cloud-sdk-api` (with `cloud-sdk-aws` implementations), keeping the pipeline behavior and public contracts intact. Verify with builds and tests at every step.

## Execution order
1. **`shared` first.** It is the foundation every service depends on and the AWS chokepoint. Land and fully verify `shared` before touching any consumer.
2. Then dependency-light services, then the rest. Suggested order after `shared`: `event-writer`, `error-processor`, `email-sender`, `ingestor`, `dispatcher`, `splitter`, `transformer`, `distributor`, `distributor-rest`, `watermill-publisher`, `watermill`.
3. `structuralvalidator`, `schema-beans`, `gen2-parser`, `functional-testing` — apply only the build/transitive/test-fake changes their DESIGN docs specify.
4. Out of scope (do not touch): `cerberus`, `fulfiller`, `router`, `mftdispatcher`, `validator`, `load-testing`.

## Per-module workflow (repeat for each module)

### A. Session & setup (MCP — mandatory)
- `session_list` → reuse a relevant active session or `session_create` named like `appianway-aws2x-upgrade-impl-<module>` with tags `["aws-upgrade","cloud-sdk","implementation","appianway","<module>"]`. Link it to the planning session by reference.
- Log a `model_info` entry with the LLM model you are running as.
- Re-read the module's DESIGN doc; build a `todos` list from its change list.

### B. Implement
- Apply the changes exactly as the DESIGN specifies: swap `com.amazonaws.*` clients/wrappers for `cloud-sdk-api` interfaces; update Guice bindings; update `pom.xml` (remove `aws-java-sdk` v1, add `cloud-sdk-api`/`cloud-sdk-aws`/`commons` per the design); update `conf/*.yaml` / `.properties` / credential & region handling.
- Preserve public API and the `MetaData` / SNS `Event` contracts. **CRITICAL** A shared public API or data format should NOT change. This could have huge adverse impact to client applications in mercury-services like `booking` , `network` etc. Make sure you check the usage in upgraded applications like `booking` and still not upgraded applications like `visibility` in the develop branch of that workspace. 
- Follow existing patterns: `SQSListener` + `AsyncDispatcher`, `Task` subclasses, `ErrorHandler` + `RecoverableException`, `EventLogger` lineage, `HealthCheckRegistrar`. Do not roll your own loops.
- Catch specific exceptions (never `Exception`/`Throwable`); use `Optional<T>` at boundaries; keep changes minimal and focused (no unrelated refactors).

### C. Tests
- Update/extend unit tests and the `functional-testing` in-memory fakes as the DESIGN requires. If a bug is found, add a failing test that reproduces it, then fix.
- Every new public method needs a unit test. Keep assertions in AssertJ.
- **Upgrade to JUnit 5** for this module; if it does not. Keep old tests in JUnit4. Write all new tests in JUnit 5

### D. Verify (gate — must pass before moving on)
- Run `mvn -pl <module> -am clean verify` (use the workspace terminal). All unit and available integration tests (`@Category(IntegrationTests.class)`) must pass.
- Fix any breakage — **including pre-existing failures you surface** — root-causing each. If a failure is genuinely unrelated and cannot be fixed safely, log it as a `blocker` and flag it explicitly.
- Use `problems`/`get_errors` to confirm no compile errors.

### E. Log & document
- Add `code_change`, `test_result`, `decision`, and `progress` entries to the session for each step, with `file:line` references and key Jira keys.
- Update the module's DESIGN doc only if the implementation deviated from it, noting why (confirm before large doc rewrites).

## Cross-workspace note
- `mft-s3-aqua-appia` is the sibling MFT ingress/egress workspace in the same program and must also move to cloud-sdk. It is a **separate workspace** — do not edit it from here. Note sequencing/coordination in the session if relevant.

## Global rules & guardrails
- **One module at a time**; never start the next module until the current one's `mvn verify` is green and committed-ready.
- Do not bypass safety checks (no `-DskipTests`, no `--no-verify`) to force a green build.
- Do not delete unfamiliar files or in-progress work.
- If a credential/tool is unavailable (e.g. Jira/Confluence 401, no AWS creds for live integration), note it and rely on the `functional-testing` fakes; proceed where possible.
- If context usage approaches ~85% with work remaining, persist a detailed handoff (done modules, current module state, remaining todos) in the session, create a linked follow-up session, and continue.

## Closeout
- When all in-scope modules build and test green on cloud-sdk:
  - Run a final aggregator `mvn clean verify` from the repo root and confirm it passes.
  - Add a final `progress` summary entry listing every module migrated and its verification result.
  - Mark the session **completed** via `session_update_status`.
- Keep going until the upgrade is complete and verified across all in-scope modules. Do not stop early.

## Inputs you may be given
- A module name or subset — if provided, implement only those (still `shared`-first if `shared` is included or required).
- A Jira ticket key — fetch via `jira_get_issue` if reachable and honor its acceptance criteria.
