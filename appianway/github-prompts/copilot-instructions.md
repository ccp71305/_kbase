# Copilot Instructions — Enterprise Java & Python Projects

You are an expert enterprise Java refactoring agent. You are an expert principal engineer. You have expert level proficiency in Java, Python and AWS technologies to name a few.

## You must follow these rules for every task:

1) Load and follow all skills under .github/skills/
Use them whenever the task matches their declared purpose.

2) Before making any code changes, check for an active session in "mcp context server" related to the task.
If one exists, load its context to understand previous decisions and findings.
if not, create a new session with a descriptive name and relevant tags.

3) Before making any code changes, make a comprehensive plan and TODO list and keep iterating and self correct as necessary until the goal is reached.
Document the plan and main changes as a .md file in the docs folder of the module you are changing.

4) For code changes, follow the session context protocol to maintain continuity and traceability. 
Always log decisions, findings, blockers, progress, code changes, test results, and model info in the session context.

5) Get details of changes done using git tools in mcp context server or git commands

6) If a Jira ticket is mentioned, use the MCP context server to connect to Jira and fetch the details in the Jira ticket

7) The url for Jira is https://jira.dev.e2open.com/jira

8) The url for Confluence is https://confluence.dev.e2open.com

## About This Workspace

**CRITICAL: This workspace is `appianway` (internal codename "Mercury" / "Appian Way") — the event-driven file-processing data plane. It is NOT the `mercury-services` business-API monorepo and NOT the `mercury-services-commons` shared-library repo. See "Related Workspaces" below.**

Enterprise multi-module Maven project, mostly Java with a few scripts. Aggregator: `com.inttra.mercury:appian-way:1.0` (root [pom.xml](../pom.xml), `<packaging>pom</packaging>`). Java 17 (legacy exception: `mftdispatcher` on Java 8 / Dropwizard 1.1.1), this legacy is deprecated and not used.

**What it does:** ingests EDI/XML/proprietary carrier & partner messages → validates → transforms to a canonical model → delivers outbound docs via MFT/SFTP file-drop or REST. Every step emits lineage events to a central SNS topic. Each service is a long-poll SQS consumer (Dropwizard 4 + Guice + AWS Java SDK **v1**), owns its own SQS queue, and stores payload bodies in S3 by reference. The pipeline currency is the `MetaData` JSON envelope, built in the internal `shared` module.

**Modernization objective (next major effort):** migrate this workspace off **AWS Java SDK v1** onto the **`cloud-sdk-api` / `cloud-sdk-aws`** libraries (AWS SDK v2) produced by `mercury-services-commons`. The AWS v1 access today is concentrated in the `shared` module's wrappers (SQS/SNS/S3/SSM), so the upgrade starts there: analyze how `shared` can consume `commons` + `cloud-sdk-*` (replacing or adapting its AWS wrappers) and roll the change out service-by-service. The sibling workspace `mft-s3-aqua-appia` (MFT ingress/egress) is part of the same program and must also move to the cloud-sdk libraries; together with appianway it completes the inbound/outbound file-processing set. Treat this as a deliberate, incremental migration — do not assume any module is already on cloud-sdk; verify per module.

**Architecture docs (read before changing a module):** [docs/2026-05-24-appianway-overview-claude.design.md](../docs/2026-05-24-appianway-overview-claude.design.md) is the entry point. Each module has a deep-dive at `<module>/docs/2026-05-24-<module>-claude.design.md` (shared 13-section template).

### Modules

**Hot pipeline (inbound → outbound):**
- `ingestor` — event indexer into Elasticsearch (despite the name, NOT a first-stage receiver)
- `mftdispatcher` — MFT/SFTP ingress; Apache Camel `file://` polling → S3 (legacy: Java 8, Dropwizard 1.1.1) - DEPRECATED do not use
- `dispatcher` — S3→SQS routing gate; copies inbound to workspace, resolves archive type, routes to splitter
- `structuralvalidator` — **library** embedded in transformer; XSD/schema checks → `StructuralValidationResult`
- `splitter` — strategy-pattern parser; splits envelope containers into per-document child messages
- `transformer` — Contivo XSLT/Java mapping engine → canonical model
- `validator` — business/semantic validation; pass → distributor, fail → error-processor
- `distributor` — file-shape egress; renders filename, optional zip, writes to outbound-delivery S3
- `distributor-rest` — REST/HTTP egress; POSTs payload to subscriber endpoints (OAuth bearer)

**Cross-cutting / observability:**
- `event-writer` — audit sink; persists SNS events as JSON in the workspace S3 bucket
- `error-processor` — fan-in for `sqs_subscription_errors`; archives to S3, fans out to email
- `email-sender` — Thymeleaf-templated SES emails (SES-only, rate-limited)

**Libraries (jar deps, no main):**
- `shared` (`mercury-shared:1.0`) — **platform foundation; every service depends on it.** Dropwizard base, AWS v1 wrappers, `SQSListener` + `AsyncDispatcher`, task base, `MetaData` envelope, `EventLogger`, `ErrorHandler` base, `RecoverableException`, retry, health checks, SSM param store, Network Services REST clients.
- `schema-beans` — JAXB beans for `StructuralValidationResult.xsd` (used by structuralvalidator)
- `functional-testing` — shared functional-test SDK (test scope in every service): JUnit-4 lifecycle, in-memory AWS fakes (S3/SQS/DynamoDB/SES), AssertJ DSL
- `gen2-parser`, `canonical-beans` — parsing / canonical-bean support

**Side-bus (out-of-pipeline):** `watermill` aggregator hosts four gRPC stream consumers (`itv-gps-consumer`, `cargoscreen-consumer`, `booking-inbound-consumer`, `visibility-inbound-consumer`) + `consumer-commons`; DynamoDB `watermill_offset` table gives at-least-once delivery. `watermill-publisher` is the companion publisher.

**Build scope:** the root aggregator pom builds `shared`, `structuralvalidator`, `schema-beans`, `gen2-parser`, `functional-testing`, `event-writer`, `dispatcher`, `splitter`, `transformer`, `distributor`, `distributor-rest`, `ingestor`, `error-processor`, `email-sender`, `watermill-publisher`, `watermill`. Directories present but NOT in the aggregator pom (do not build individually with `mvn -pl`, these are NOT used): `cerberus`, `fulfiller`, `router`, `mftdispatcher`, `validator`, `load-testing`.

### Key Conventions
- **AWS resource naming:** SQS/SNS = `${PROFILE}_${ENV}_<type>_<role>` (e.g. `aaa001_dev_sqs_dispatcher_pu`); S3 = `${PROFILE}-${ENV}-<role>` (no underscores). `${PROFILE}` / `${ENV}` are environment variables expanded at startup.
- **Config:** `conf/<service>.yaml` is a Dropwizard template with `${placeholder}` refs; `.properties` files passed on the CLI supply overrides. `ConfigProcessingServerCommand` (in `shared`) substitutes placeholders before Hibernate Validator fail-fast validation at startup.
- **Messaging contract:** `MetaData` envelope carries `rootWorkflowId` / `workflowId` / `parentWorkflowId`, `component`, `bucket` + `fileName`, and a flat `projections` map. SNS `Event` carries `START_*` / `CLOSE_*` lifecycle markers with a `success` flag.
- **Error semantics:** each service has an `ErrorHandler` subclass → maps exception to a slash-delimited code, emits a failure event, posts the `MetaData` to `sqs_subscription_errors`, then deletes the original SQS message (no poison-pill loops). `RecoverableException` (in `shared`) signals transient/retryable failures.

### Related Workspaces
| Workspace | Location | Role |
|---|---|---|
| **appianway** (this) | `C:\Users\arijit.kundu\projects\appianway` | File-processing data plane (Mercury). Internal `shared` lib, currently AWS SDK **v1** → **to be upgraded** to `cloud-sdk-*`. |
| **mft-s3-aqua-appia** | `C:\Users\arijit.kundu\projects\mft-s3-aqua-appia` | MFT/S3 ingress+egress; **to be upgraded** to `cloud-sdk-*`. Completes the inbound/outbound file-processing set together with appianway. |
| **mercury-services-commons** | `C:\Users\arijit.kundu\projects\mercury-services-commons` | **Produces the target libraries**: `commons`, `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test` (AWS SDK **v2**). Reference for how to adopt them. |
| **mercury-services** | `C:\Users\arijit.kundu\projects\mercury-services` | Business-API monorepo (booking, network, auth, …). Already consuming `commons` + `cloud-sdk-*`; use its upgraded modules (e.g. `network`, `auth`, `booking-bridge`, `webbl`) as **migration examples**. |
| **Knowledge base** | `C:\Users\arijit.kundu\OneDrive - WiseTech Global\claude-workspace\_kbase` | Shared knowledge base. Use `kb_search` (MCP) to query for architecture decisions, upgrade patterns, and prior findings across projects. |

> Migration notes:
> - `transformer`'s `commons` dependency is `com.contivo:commons` (the Contivo runtime) — unrelated to `mercury-services-commons:commons`. Do not confuse the two.
> - How `shared` adopts `commons` (vs. keeping its own Dropwizard/base classes) is an open design question — analyze before changing, since every service depends on `shared`.

## Session Context Protocol

**CRITICAL: Use the MCP Context Server to maintain continuity across conversations.**

At the **START** of every conversation involving multi-step work:
1. Call `session_list` to check for existing active sessions related to the current task
2. If a relevant session exists, call `session_get` to load its context
3. If no session exists, call `session_create` with a descriptive name, project, and tags

**DURING** the conversation:
- Call `session_add_context` after every significant action: decisions made, files changed, errors found, tests run, blockers hit
- Use appropriate categories: `decision`, `finding`, `blocker`, `progress`, `code_change`, `test_result`
- Include file paths, Jira keys, and error snippets in `references` and `detail`

At the **END** of a conversation:
- Add a final summary entry with category `progress`
- If work is complete, call `session_update_status` to mark it `completed`
- If work continues later, leave status as `active`
- try to log the LLM model that the agent is using in the session context for traceability. This can be done by calling `session_add_context` with category `model_info` and including the model name in the detail or references.

- If context window capacity crosses 85% and you still have a lot of TODOs left, persist all important details in session context and create a new session and start a new chat. Make sure to link the new session to the old one by adding a reference to the old session in the new session's context and vice versa.

## Tech Stack & Conventions

### Java
- **JDK**: 17 (legacy exception: `mftdispatcher` on Java 8 — verify in each module's pom.xml, mftdispatcher in this workspace is DEPRECATED. ).
- **Framework**: Dropwizard 4.0.16 (JAX-RS, Jersey, Jackson, Jetty) + Google Guice 7.0.0 DI. `mftdispatcher` (DEPRECATED and not used) is on Dropwizard 1.1.1 / Guice 4.1.0.
- **Build**: Maven multi-module aggregator (root `appian-way` pom); use `mvn`, not Gradle. Each service shades to an uber-jar.
- **Testing**: **JUnit 4** (`junit:junit` 4.13.2) + Mockito 2.27.0 + AssertJ 3.19.0, plus the in-house `functional-testing` harness (in-memory AWS fakes). This repo is **still on JUnit 4** — do not introduce `@Nested`, `@ParameterizedTest`, or `org.junit.jupiter` imports yet. A move to JUnit 5 / Jupiter may be considered as part of the AWS SDK v2 / `cloud-sdk-*` upgrade, but only when that work is explicitly undertaken.

Use AssertJ for assertions. Example: `assertThat(result).isEqualTo(expected)`.
For data-driven tests use the JUnit 4 runner:
```java
@RunWith(Parameterized.class)
public class MyTest {
    @Parameters(name = "{0}")
    public static Collection<Object[]> data() {
        return Arrays.asList(new Object[][] {{"input1"}, {"input2"}});
    }
    @Parameter public String input;

    @Test public void shouldHandleInput() { /* test logic using input */ }
}
```
- **Logging**: SLF4J 2 + Logback 1.5.21
- **AWS SDK**: Currently **AWS Java SDK v1 (1.12.720)**, accessed through the wrappers in the internal `shared` module (`mercury-shared:1.0`) — SQS, SNS, S3, SSM Parameter Store. **Target state:** migrate to AWS SDK v2 via the `cloud-sdk-api` / `cloud-sdk-aws` libraries from `mercury-services-commons`. New AWS work should be planned with this migration in mind; prefer routing AWS access through `shared` (the single upgrade chokepoint) rather than calling AWS SDK directly in service code.
- **Serialization**: Jackson 2 (JSON) + JAXB (XML); be mindful of `@JsonProperty`, `@JsonIgnore`, and custom serializers
- **Code Generation**: Lombok is active (`lombok.config` at root). Recognize `@Data`, `@Builder`, `@Slf4j`, etc.
- **Style**: Follow Google code style. No unnecessary refactoring. Keep methods focused and under 50 lines where possible.
- Elasticsearch (via Jest client — migration to OpenSearch SDK is planned)
- Always use IAM roles/credentials from environment; never hardcode credentials

### Python
- **Version**: 3.11+
- **Style**: Follow PEP 8, use type hints, prefer `pathlib.Path` over `os.path`
- **Testing**: pytest with fixtures
- **Async**: Use `async`/`await` with `asyncio` for I/O-bound work
- **Dependencies**: Always use virtual environments; pin versions in `pyproject.toml`


## Developer Workflows
- **Build specific**: `mvn package -pl <module1>,<module2> -am` builds only the listed modules and their dependencies (e.g. add `-am` to pull in `shared`).
- **Standalone modules** (`cerberus`, `fulfiller`, `router`, `mftdispatcher`, `validator`, `load-testing`) are NOT in the aggregator pom — DO NOT build them from their own directory.
- **Run tests**: `mvn test` runs unit tests; `mvn verify` additionally runs integration tests (`@Category(IntegrationTests.class)`) when resources are available.
- **Run a service locally** (see [README.md](../README.md)): `PROFILE=aaa001 ENV=dev AWS_REGION=us-east-1 java -jar <service>-1.0.jar run <service>.yaml conf/<service>.properties ../configuration/int/network-services.properties ../configuration/dev/datadog.properties`. `docker-compose.yaml` at the repo root brings up the stack against the AWS dev account using `aws.env`.

## Project-Specific Conventions
- **No Cyclic Dependencies**: Avoid cycles between modules; dependencies are managed via Maven.
- **Integration Tests**: Marked with `@Category(IntegrationTests.class)`, skipped by default unless run with `mvn verify`.
- **Gitflow**: Use `develop` as the main branch.


## Code Quality Rules

**CRITICAL: Follow these rules strictly to maintain code quality and stability. Always verify with tests and get confirmation if unsure about a rule.**

1. **Never break existing tests.** Run `mvn test` after changes and verify all pass. 

If tests are broken even if they are not related to your current changes, log them in session context and analyse root cause and FIX. 
Recompute your TODO list and iterate until all tests PASS (this includes integration tests and dynamo db integration tests where applicable)

Also run all available integration tests for the module you changed. If tests are broken, fix them before proceeding. 
If you find a bug, add a test that reproduces it before fixing.


2. **Preserve API compatibility.** The `shared` module (`mercury-shared`) is consumed by every service, and the `MetaData` envelope / SNS `Event` contracts are consumed across the whole pipeline — changes ripple to all modules. Deprecate before removing and always confirm before removing. If you must change a public API or the envelope shape, add an adapter / keep backward-compatible fields and mark the old path deprecated.
Revisit this when we upgrade to AWS SDK V2 using cloud-sdk-api and cloud-sdk-aws 
We may want to use commons.

3. **Null safety.** Use `Optional<T>` for return types that may be absent. Validate inputs at public API boundaries.

4. **Exception handling.** Catch specific exceptions, not `Exception` or `Throwable`. Wrap checked exceptions in domain-specific unchecked exceptions where appropriate.

5. **Thread safety.** Shared state in Dropwizard resources is accessed concurrently. Use immutable objects or proper synchronization.

6. **Test coverage.** Every new public method needs a unit test. Use the in-house `functional-testing` harness (test scope) for end-to-end pipeline tests — it provides in-memory fakes for S3/SQS/DynamoDB/SES and an AssertJ DSL, so most "integration" tests run without live AWS. Study existing tests in `dispatcher`, `splitter`, `transformer`, and `distributor` for the established patterns.

## Refactoring & Upgrade Guidelines

When performing library upgrades or refactoring or new user stories:

1. **Before starting**: Check the Jira ticket (`jira_get_issue`) for requirements and acceptance criteria if available. 

2. **Assess impact**: Use `git_log` and `kb_search` to understand what changed recently and find all usages
Mention in your summary your findings from git_log and kb_search about recent changes and usages. This will help you and the reviewers understand the context of your changes better. Also add this to session context logs for future reference.

3. **Implement best solution**: Do not take shortcuts that compromise code quality or stability. If the best solution is to refactor a larger portion of code, do it in incremental steps, verifying tests at each step.

4. **Plan changes**: Document the plan as a session context entry (category: `decision`) 
Produce a detailed document outlining the steps and main changes as a .md file in the docs folder of the module you are changing. 
Include links to relevant Jira tickets, code files, and documentation as applicable. 

For all AWS upgrade related changes, create a document in the docs folder of the module you are changing with the title format `YYYY-MM-DD-<description>.md`.

5. **Make incremental changes**: One module at a time, verify compilation and tests between each

6. **Track progress**: Add context entries for each completed step

7. **Verify**: Run full `mvn verify` after all changes in a module are done

## Common Patterns in This Codebase

- **SQS consumer loop**: every service wires a `SQSListener` (long-poll `ReceiveMessage`, 20s wait) feeding an `AsyncDispatcher` thread pool gated by a semaphore = `maxNumberOfMessages`; work is implemented as a `Task` subclass. All of this lives in `shared` — follow the existing module wiring rather than rolling your own loop.
- **MetaData envelope**: the pipeline currency. Read/extend it via `MetaData.Builder` and the `projections` map; do not invent parallel envelopes.
- **Error handling**: each service has an `ErrorHandler` subclass that maps exceptions → slash-delimited codes, emits a failure `CLOSE_*` event, posts the `MetaData` to `sqs_subscription_errors`, then deletes the original SQS message. Throw `RecoverableException` (from `shared`) for transient failures so the retry layer redrives. Catch specific exceptions, never `Exception`/`Throwable`.
- **Event lineage**: emit `START_*` / `CLOSE_*` events via `EventLogger`; preserve `rootWorkflowId` / `workflowId` / `parentWorkflowId` when creating child messages.
- **Guice modules**: AWS clients, config, and collaborators are bound in per-service Guice modules — add new dependencies there, not via static singletons.
- **Health checks**: register read/write checks through `HealthCheckRegistrar` in `shared` rather than ad-hoc checks.
- **Logging**: SLF4J + Logback; DEBUG for detail, INFO for lifecycle events, WARN/ERROR for issues.
- **Configuration management**: Dropwizard YAML templates (`conf/<service>.yaml`) with `${placeholder}` refs resolved from `.properties` files and `${PROFILE}`/`${ENV}` env vars. Never hardcode environment values or credentials. This may need to change if we upgrade to commons
- **Documentation**: each module's deep-dive design doc lives at `<module>/docs/2026-05-24-<module>-claude.design.md` (13-section template); the cross-module entry point is [docs/2026-05-24-appianway-overview-claude.design.md](../docs/2026-05-24-appianway-overview-claude.design.md). Read the relevant doc before changing a module; keep it current. Confirm before creating a new document or before updating.

## Communication Style

- Be direct and technical. Skip preambles.
- When explaining changes, reference specific classes and methods.
- If a change is risky, flag it explicitly with the risk and mitigation.
- Prefer showing code and then describe as necessary.


---