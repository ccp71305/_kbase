---
agent: agent
description: Review every appianway module and produce, per module, (1) an AWS SDK v1 → v2 (cloud-sdk-api / cloud-sdk-aws) upgrade PLAN covering both the "keep shared" and "adopt commons" options with a peer review and a recommendation, and (2) a detailed upgrade DESIGN document. Plans and designs are written into each module's docs/ folder. Uses the MCP Context Server throughout.
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

# Appian Way — AWS SDK v2 (cloud-sdk) Upgrade: Planning & Design

You are an **expert enterprise Java refactoring engineer**. Your job in this prompt is **analysis, planning, and design only — DO NOT modify any production source code or `pom.xml` files.** The only files you create are the planning and design markdown documents described below (and MCP session entries).

Read and obey [.github/copilot-instructions.md](../copilot-instructions.md) in full before starting, especially the **About This Workspace**, **Modernization objective**, **Related Workspaces**, and **Session Context Protocol** sections.

## Objective

For **every module built by the root aggregator pom** in this `appianway` workspace, produce:

1. A **per-module upgrade PLAN** to migrate from **AWS Java SDK v1 (1.12.720)** to **AWS SDK v2** via the **`cloud-sdk-api` / `cloud-sdk-aws`** libraries from `mercury-services-commons`. The plan must:
   - Document **both options** in full detail:
     - **Option A — Keep the internal `shared` module**: upgrade `shared`'s AWS wrappers (SQS/SNS/S3/SSM) to delegate to `cloud-sdk-aws`, keeping `shared`'s public API stable so dependent services change minimally.
     - **Option B — Adopt `commons` from `mercury-services-commons`** *(the directed default)*: replace `shared`'s utility/base/AWS classes with the `commons` + `cloud-sdk-*` stack on **Dropwizard 5**, the way `mercury-services` client apps (e.g. `network`, `auth`, `booking`, `booking-bridge`, `webbl`) already do. Route all AWS access through `cloud-sdk-api`.
   - Be **peer reviewed by a second agent** (see "Peer review" below) critically for completeness, correctness, and risk.
   - Conclude with a **clear, justified recommendation** — **Option B by default**; choose Option A only with a categorical, valid technical limitation, stated explicitly.

2. A **per-module DESIGN document** detailing all changes for the **recommended** option, including class diagrams, component diagrams, sequence diagrams, configuration changes, Maven dependency changes, and test details.

## Stakeholder directives (authoritative — supersede any conflicting guidance below)

These directives are mandatory and override the neutral "compare A vs B" framing where they conflict:

1. **Target Dropwizard 5.** `mercury-services-commons` `1.0.26-SNAPSHOT` publishes Dropwizard **5.0.1**. Plan for Dropwizard 5, not 4.
2. **Prefer `commons` + `cloud-sdk-*` (Option B).** Use the `commons` classes and route **all** AWS service communication through `cloud-sdk-api` (abstraction) / `cloud-sdk-aws` (AWS SDK 2.x implementation), exactly like the `mercury-services` consumers. Recommend Option A **only** when you can state a categorical, valid technical limitation that blocks Option B for that module. Document Option A as a fallback, but the default recommendation is **Option B**.
3. **New tests in JUnit 5 (Jupiter).** Write all *new* tests with JUnit 5 via `dropwizard-testing` (JUnit 5). Existing JUnit 4 tests may remain during transition (JUnit Vintage); call out the migration explicitly.
4. **cloud-sdk gap analysis is mandatory.** Where `cloud-sdk-api` / `cloud-sdk-aws` lack a capability appianway needs, the PLAN must **list the gap** and the DESIGN must provide **full technical detail** of the new abstraction (in `cloud-sdk-api`) and its AWS-SDK-2.x implementation (in `cloud-sdk-aws`) in a dedicated section, so the capability can be implemented there rather than worked around in appianway. The end state is: appianway calls only `cloud-sdk-api`; all AWS specifics live in `cloud-sdk-aws`.
5. **Configuration differences are mandatory.** appianway loads YAML differently from `mercury-services` apps (Dropwizard template `conf/<service>.yaml` with `${placeholder}` refs resolved from CLI-passed `.properties` files + `${PROFILE}`/`${ENV}` env vars via appianway's `ProcessedConfigProvider`/`PropertiesLookup`/`EnvironmentVariableLookup`/`ValidatingLookup` chain, before Hibernate Validator). `commons` resolves `${awsps:...}` via its own `ConfigProcessingServerCommand` + `ParameterStoreConfigTransform`. Every DESIGN must specify how the two config models are **composed** under Option B (see the `shared` design's config section as the master reference).

## Scope — modules to cover

Cover exactly the modules in the root aggregator pom:
`shared`, `structuralvalidator`, `schema-beans`, `functional-testing`, `event-writer`, `dispatcher`, `splitter`, `transformer`, `distributor`, `distributor-rest`, `ingestor`, `error-processor`, `email-sender`, `watermill-publisher`, `watermill` (and its sub-modules).

- **Start with `shared`** — it is the platform foundation every service depends on and the chokepoint for AWS access; the Option A vs B decision here drives every other module.
- Treat the non-aggregator dirs (`cerberus`, `fulfiller`, `router`, `mftdispatcher`, `validator`, `load-testing`) as **out of scope** — note them as "deprecated / not built" and skip.
- For library modules with **no AWS surface** (e.g. `schema-beans`), produce a short plan/design stating there is no AWS v1 usage and only transitive/build impact to assess.
- `mft-s3-aqua-appia` is part of the same program but **a separate workspace** — mention it as a cross-workspace dependency/sequencing note; do not write files there from this workspace.

## Required workflow

### 1. Session setup (MCP Context Server — mandatory)
- Call `session_list`; if a relevant active session exists, `session_get` it. Otherwise `session_create` named like `appianway-aws2x-upgrade-planning` with project `appianway` and tags `["aws-upgrade","cloud-sdk","planning","appianway"]`.
- Log a `model_info` entry recording the LLM model you are running as.
- Add `decision` / `finding` / `progress` entries at every meaningful step (per module, per peer review, per recommendation).

### 2. Per-module analysis (before writing anything)
For each in-scope module:
- Identify all **AWS SDK v1 usage**: `com.amazonaws.*` imports, client types (`AmazonSQS`, `AmazonSNS`, `AmazonS3`, SSM), `shared` wrapper classes used, Guice bindings, config (`conf/*.yaml`, `.properties`), and health checks.
- Use `usages`/`search` to find call sites and `git_log` + `kb_search` (MCP) to understand recent change history. Summarize these findings in the plan and in session context.
- Map each v1 touchpoint to its **`cloud-sdk-api` equivalent**. Read `mercury-services-commons` (`cloud-sdk-api`, `cloud-sdk-aws`, `commons`) and an already-upgraded `mercury-services` module like `booking` or `auth` as the reference pattern.
- Read the module's existing design doc at `<module>/docs/2026-05-24-<module>-claude.design.md` for context.

### 3. Write the per-module PLAN document
Create `<module>/docs/<YYYY-MM-DD>-<modulename>-aws2x-upgrade-plan-copilot.md` (use today's date) with this structure:

1. **Executive summary** — what the module does, its AWS surface, headline recommendation.
2. **Current state** — inventory of AWS v1 usage with `file:line` references; `shared` classes consumed; config & Guice bindings; tests touching AWS.
3. **Findings from git_log / kb_search** — recent relevant changes and all usages.
4. **Option A — Keep `shared`** — detailed change list, pros/cons, blast radius, effort, risks, backward-compatibility strategy.
5. **Option B — Adopt `commons` + `cloud-sdk-*`** — detailed change list, what `shared` classes get replaced by `commons` equivalents, pros/cons, blast radius, effort, risks, migration of config/DI/tests.
6. **Comparison matrix** — side-by-side on effort, risk, consistency with `mercury-services`, long-term maintainability, test impact, API-compatibility impact.
7. **cloud-sdk-api / cloud-sdk-aws gaps** — list every capability appianway needs that the current `cloud-sdk-*` libraries do **not** provide (e.g. concurrent/semaphore-bounded SQS listener, `StorageClient.putObject` with metadata/content-type, S3 event-notification parsing, DynamoDB optimistic-lock/version attribute, Thymeleaf template engine, composable config-transform chain, cloud-sdk-based health checks). Each gap names the cloud-sdk artifact that must be added/changed; full technical spec goes in the DESIGN.
8. **Recommendation** — chosen option (default **Option B**; Option A only with a categorical technical limitation) with explicit justification.
9. **Peer review** — the second agent's critical review and how it was addressed (see below).
10. **Open questions / dependencies** — incl. `shared`-first sequencing and the `mft-s3-aqua-appia` cross-workspace dependency.
11. **Configuration changes** — how appianway's YAML/`.properties`/`${PROFILE}`/`${ENV}` model composes with `commons` `ConfigProcessingServerCommand` under Option B.

### 4. Peer review (mandatory, per module)
- After drafting each module's plan, invoke a **subagent** (use `runSubagent`, e.g. the `Explore` agent for read-only critique) to **critically review the plan for completeness**: missing AWS touchpoints, unaddressed config/DI/test changes, unrealistic effort/risk, broken API-compatibility, and whether both options are genuinely viable.
- Incorporate the review into section 8 and revise the plan. Log the review outcome as a `finding` in the session.

### 5. Write the per-module DESIGN document
Only after the plan + peer review are done, create `<module>/docs/<YYYY-MM-DD>-<modulename>-aws2x-upgrade-DESIGN.md` for the **recommended** option, containing:

1. **Overview & chosen option.**
2. **Class diagram** (Mermaid `classDiagram`) — new/changed classes, removed v1 wrappers, new `cloud-sdk-api` interfaces used.
3. **Component diagram** (Mermaid) — module ↔ `shared`/`commons` ↔ `cloud-sdk-aws` ↔ AWS.
4. **Sequence diagram(s)** (Mermaid `sequenceDiagram`) — key SQS-consume / S3 / SNS / SSM flows after the change.
5. **Configuration changes** — `conf/*.yaml`, `.properties`, env vars, credential/region handling, **and the appianway-vs-`mercury-services` YAML-loading difference**: how appianway's `${placeholder}` + `.properties` + `${PROFILE}`/`${ENV}` resolution composes with `commons` `ConfigProcessingServerCommand` / `ParameterStoreConfigTransform` (`${awsps:...}`) under Dropwizard 5.
6. **cloud-sdk-api / cloud-sdk-aws gaps to implement** — a dedicated section giving the **full technical specification** of each new abstraction (interface signatures in `cloud-sdk-api`) and its AWS-SDK-2.x implementation (classes/factories/Guice modules in `cloud-sdk-aws`) needed to close the gaps named in the plan. This is the spec the cloud-sdk team implements so appianway depends only on `cloud-sdk-api`.
7. **Maven dependency changes** — exact `groupId:artifactId:version` to add/remove (drop `aws-java-sdk` v1, add `cloud-sdk-api`/`cloud-sdk-aws`/`commons` on the Dropwizard 5 line), version-management notes, shading/uber-jar impact.
8. **Test details** — which unit tests change, how the `functional-testing` in-memory fakes are affected (re-pointed to `cloud-sdk-api` interfaces), AWS SDK v2 test doubles, integration-test strategy (`dynamo-integration-test` where DynamoDB is involved). **New tests are written in JUnit 5 (Jupiter)**; existing JUnit 4 may remain via JUnit Vintage during transition.
9. **Rollout & verification** — `mvn -pl <module> -am verify` gate, sequencing relative to `shared`.
10. **Risks & mitigations.**

### 6. Closeout
- Add a final `progress` summary entry to the session listing every plan and design file created (with paths).
- Confirm both documents exist for every in-scope module.
- Call `session_update_status` to mark the session **completed**.

## Rules & guardrails
- **Do not edit production code or poms** in this prompt — planning/design markdown + MCP entries only.
- Use **relative markdown links** to real files; cite `file:line` where you reference code.
- Keep diagrams in Mermaid so they render in VS Code.
- Be incremental and resilient: if a tool/credential is unavailable (e.g. Jira/Confluence 401), note it and proceed with repo evidence.
- If context usage approaches ~85% with work remaining, persist a detailed handoff in the session, create a linked follow-up session, and continue.
- Keep going until **every in-scope module has both a plan and a design document** and the session is marked completed. Do not stop early.

## Inputs you may be given
- A Jira ticket key (use `jira_get_issue` if reachable) — incorporate its acceptance criteria.
- A specific module subset — if provided, restrict scope to those modules; otherwise cover all in-scope modules.
