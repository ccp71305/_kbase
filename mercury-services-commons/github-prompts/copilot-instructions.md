# Copilot Instructions — Enterprise Java & Python Projects

You are the project’s analysis and refactoring agent. Your are an expert principal engineer.

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

5) Get details of changes done from git log

## About This Workspace

**CRITICAL: Read this section carefully**


This is an enterprise Java multi-module Maven project with some Python components. 
The following modules are the main modules. 
- cloud-sdk-api Defines all the interface and API for the AWS service implementations and some common classes
- cloud-sdk-aws Defines all the implementations for the AWS services. These implementations are used by client applications in mercury-services project
- commons Defines common and utility classes and Dropwizard related classes which are used by client applications in mercury-services project
- dynamo-integration-test Defines the local DynamoDb integration test framework 
- email-sender - deprecated. Will be removed once all the client applications in mercury-services project are upgraded to the cloud-sdk libraries
- dynamo-client - deprecated. Will be removed once all the client applications in mercury-services project are upgraded to the cloud-sdk libraries

This project produces the shared commons library and the cloud-sdk-api and cloud-sdk-aws and dynamo-integration-test libraries which are all tagged to the latest version specified in the root pom.xml attribute <dependency.version>< [ version ]></dependency.version>

The workspace physical location for mercury-services project is at C:\Users\akundu\projects\mercury-services


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
- **JDK**: 17 (verify in pom.xml for exact version)
- **Framework**: Dropwizard (JAX-RS, Jersey, Jackson, Jetty)
- **Build**: Maven multi-module with parent POM; use `mvn` commands, not Gradle
- **Testing**: JUnit 5 (Jupiter) with Mockito; integration tests use `maven-failsafe-plugin`

Use assertj for assertions in tests. Example: `assertThat(result).isEqualTo(expected)`.
Use Parameterized tests for testing multiple inputs. Example:
```java
@ParameterizedTest
@ValueSource(strings = {"input1", "input2"})  
void testWithMultipleInputs(String input) {
    // test logic using 'input'
}
```
Use @Nested for grouping related tests. Example:
```java   
@Nested
class WhenInputIsValid {
    @Test
    void shouldReturnExpectedResult() {
        // test logic for valid input
    }
}
```
- **Logging**: SLF4J + Logback
- **AWS SDK**: Goal is to use cloud-sdk-api and cloud-sdk-aws libraries from mercury-services-commons (commons dependency)for AWS interactions, but some legacy code may use AWS SDK v1 directly. These modules are pending AWS upgrade. 
cloud-sdk-api implementations in cloud-sdk-aws modules use AWS 2.x API Service clients
- **Serialization**: Jackson for JSON; be mindful of `@JsonProperty`, `@JsonIgnore`, and custom serializers
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
- **Build Specific**: `mvn package -pl <module1>,<module2>` builds only listed modules.
- **Run Tests**: `mvn verify` runs all tests, including integration tests if resources are available. 

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


2. **Preserve API compatibility.** Public methods and interfaces in `commons` and `cloud-sdk-api` are consumed by other services. Deprecate before removing and always confirm before removing. If you must change a public API, add an adapter layer to preserve the old API and mark it deprecated.

3. **Null safety.** Use `Optional<T>` for return types that may be absent. Validate inputs at public API boundaries.

4. **Exception handling.** Catch specific exceptions, not `Exception` or `Throwable`. Wrap checked exceptions in domain-specific unchecked exceptions where appropriate.

5. **Thread safety.** Shared state in Dropwizard resources is accessed concurrently. Use immutable objects or proper synchronization.

6. **Test coverage.** Every new public method needs a unit test. 
Integration tests for AWS interactions use dynamo-integration-test dependency from mercury-services-commons repository.
Example integration tests can be found in network, auth, registration, booking-bridge, webbl modules 

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

- **Builder pattern**: Most model classes use Lombok `@Builder`
- **Repository pattern**: Data access through repository interfaces in `cloud-sdk-api`, implementations in `cloud-sdk-aws`
- **Service layer**: Business logic in service classes, called by Dropwizard resources
- **Dropwizard resources**: REST endpoints defined in resource classes, annotated with JAX-RS annotations
- **Configuration classes**: Dropwizard YAML configuration mapped to Java classes extending `Configuration`
- **Integration tests**: Use `@Category(IntegrationTests.class)` and often require external resources (e.g., DynamoDB Local, MySQL testcontainers)
- **AWS interactions**: Use `cloud-sdk-api` interfaces for AWS operations, implemented by `cloud-sdk-aws` modules using AWS SDK v2 clients. Avoid direct AWS SDK calls in service code.
- **Dependency injection**: Guice is used for dependency injection in modules, especially for AWS clients and repositories
- **Logging**: Use SLF4J with Logback; log at appropriate levels (DEBUG for detailed info, INFO for high-level events, WARN/ERROR for issues)
- **Error handling**: Use custom exceptions for domain errors, and map them to appropriate HTTP responses in Dropwizard exception mappers
- **Testing patterns**: Use Mockito for mocking dependencies in unit tests, and use real instances with test configurations for integration tests. Use assertj for fluent assertions.
- **Configuration management**: Use Dropwizard YAML configuration files for environment-specific settings, and map them to Java configuration classes. Avoid hardcoding values in code.
- **Documentation**: Maintain up-to-date documentation for modules, including architecture diagrams, API references, and usage examples. Put these documents in the `docs/` directory of each module. The file is usually called DESIGN.md or ARCHITECTURE.md. Confirm before creating a new document or before updating.

## Communication Style

- Be direct and technical. Skip preambles.
- When explaining changes, reference specific classes and methods.
- If a change is risky, flag it explicitly with the risk and mitigation.
- Prefer showing code and then describe as necessary.


---

## Session Telemetry (mcp-context-server)

If the `mcp-context-server` MCP tools are available in this workspace, record token usage:

- After an expensive model turn (and at minimum once at the end of the conversation), call
  `session_record_usage` with the values from the model response's `usage` block:
  `input_tokens` (uncached prompt tokens only), `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens`, and `model` (e.g. `claude-opus-4-8`). Pass the cache fields
  separately — do not fold them into `input_tokens`.
- Do not fabricate numbers. If you cannot see your own token counts, skip recording rather
  than guessing (estimates belong only in `session_estimate_tokens`, labelled
  `source: "estimated"`).
- Use `session_usage_report` (per session) and `telemetry_report` (across sessions) to
  review cost, cache-hit ratio, and context-window utilization.