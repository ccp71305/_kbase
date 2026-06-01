---
agent: agent
description: Plan, design, and implement the cloud-sdk-api / cloud-sdk-aws enhancements required to close the documented gaps (the appianway "G1–G7" cloud-sdk gap list and any other gaps found in the dated design/upgrade-plan docs). Each gap becomes its own feature branch off feature/ION-12310-commons-cloudsdk-refactoring, with a dedicated design document under cloud-sdk-api/docs. Uses the MCP Context Server throughout and preserves the existing public API of both modules.
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

# cloud-sdk-api / cloud-sdk-aws — Gap-Closure Enhancements: Plan, Design & Implement

You are an **expert enterprise refactoring and enhancement engineer** working in the `mercury-services-commons` workspace
(`C:\Users\arijit.kundu\projects\mercury-services-commons`). Your objective is to **plan, design, and
implement enhancements to the `cloud-sdk-api` and `cloud-sdk-aws` modules** so they close the gaps that
have already been discovered and documented during the appianway AWS SDK v1 → v2 upgrade effort.

Before doing anything else, **read and obey** the workspace standards in
[.github/copilot-instructions.md](../copilot-instructions.md) **in full** — especially the **About This
Workspace**, **Session Context Protocol**, **Tech Stack & Conventions**, **Code Quality Rules**, and
**Refactoring & Upgrade Guidelines** sections. Everything below operates *within* those rules.

---

## 1. Active modules (from copilot-instructions.md)

This is the shared-library repo. The **active** modules are:

- **`cloud-sdk-api`** — interfaces/API for the AWS service abstractions plus some common classes.
- **`cloud-sdk-aws`** — AWS SDK **2.x** implementations of the `cloud-sdk-api` interfaces.
- **`commons`** — Dropwizard/common/utility classes.
- **`dynamo-integration-test`** — local DynamoDB integration-test framework.

Deprecated (do **not** build new work on them): `email-sender`, `dynamo-client`.

These libraries are **actively consumed** by the upgraded `mercury-services` applications (e.g. `network`,
`auth`, `booking`, `booking-bridge`, `webbl`, `visibility`) and are the migration target for `appianway`
and `mft-s3-aqua-appia`. **Backward compatibility is therefore non-negotiable** (see §6).

---

## 2. Where the gaps are documented (read these first)

The gaps live in the **`appianway`** workspace at `C:\Users\arijit.kundu\projects\appianway`. Read its
`.github/copilot-instructions.md` for context, then read the gap sources below.

**Master gap list (authoritative index — start here):**
- `shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md` **§11 — cloud-sdk gaps G1–G7**
- `shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md` **§1A.6 / §6 — full technical specs**

**Per-module design + plan docs** (pattern `2026-05-31-<module>-aws2x-upgrade-{DESIGN,plan}-{claude,copilot}.md`)
under each appianway module's `docs/` folder. These attribute specific gaps to specific modules and contain
the concrete usage that each enhancement must support. The modules that carry cloud-sdk gaps are at least:
`dispatcher` (G1, G2, **G3**), `distributor` (G1, G2), `distributor-rest` (G1, G2), `transformer` (G1, G2, **G4**),
`email-sender` (**G5**, G1), `event-writer` (G1, G2), `error-processor` (G1, G2), `splitter` (G1, G2),
`ingestor` (G1), `functional-testing` (test fakes for G1/G2/G4).

> Treat the appianway docs as **read-only requirements input**. Do **not** modify appianway files. The
> implementation work happens only in `mercury-services-commons` (`cloud-sdk-api` / `cloud-sdk-aws`, and
> `dynamo-integration-test` / `commons` only where a gap demands it).

**The documented gaps (G1–G7) — summary you must validate against the source docs:**

| ID | Gap | cloud-sdk artifact to add/change |
|----|-----|----------------------------------|
| **G1** | Concurrent, semaphore-bounded SQS listener + `Task` dispatch; expose `QueueMessage<T>` (not raw v2 `Message`). | `ConcurrentSqsListener`/`AsyncDispatcher` in `cloud-sdk-aws`; `AbstractTask<QueueMessage<String>>` base in `cloud-sdk-api`. |
| **G2** | `StorageClient.putObject` with user metadata + content-type. | Add `putObject(bucket, key, content, Map<String,String> metadata, String contentType)` to `StorageClient` + `S3StorageClient`. |
| **G3** | S3 event-notification parsing (bucket/key from `S3EventNotification`). | S3 event-notification model + parse helper in `cloud-sdk-api`/`cloud-sdk-aws`. |
| **G4** | DynamoDB optimistic-lock / version attribute + atomic-counter/sequence pattern. | `@DynamoDbVersionAttribute`-equivalent + conditional-update-on-version (or propagate `EnhancedDynamoRepository`). |
| **G5** | Thymeleaf email template engine (cloud-sdk uses Handlebars). | `ThymeleafTemplateService` impl of `TemplateService` in `cloud-sdk-aws` (or documented Thymeleaf→Handlebars migration). |
| **G6** | Composable config-transform chain (commons `getConfigTransformer` hardcodes the chain). | Make the commons transform chain pluggable / provide composable transform set. |
| **G7** | cloud-sdk-based health checks for S3/SQS/SNS/(Dynamo). | Lightweight health-probe helpers over injected `cloud-sdk-api` clients. |

If, while reading the docs, you find **additional** gaps or enhancements beyond G1–G7, treat each as its own
item using the same workflow below.

---

## 3. Session Context Protocol (use the MCP Context Server religiously)

Per the workspace rules, the MCP Context Server is mandatory:

1. **Start:** `session_list` to find an active session for this work. If one exists, `session_get` to load
   it. Otherwise `session_create` with a descriptive name (e.g. *"cloud-sdk gap-closure ION-12310"*),
   project `mercury-services-commons`, and tags (`cloud-sdk-api`, `cloud-sdk-aws`, `ION-12310`, `aws2x`).
2. **During:** after every significant action call `session_add_context` with the right category
   (`decision`, `finding`, `blocker`, `progress`, `code_change`, `test_result`). Include file paths, the
   gap ID (G1–G7), the Jira key `ION-12310`, branch names, and error snippets in `detail`/`references`.
3. **Model info:** log the LLM model you are running as (`category: model_info`).
4. **End:** add a final `progress` summary; set status `active` (work continues) or `completed`.
5. If context usage crosses **85%** with TODOs remaining, persist everything to the session, link a new
   session to this one, and continue there.
6. If a Jira ticket is referenced, fetch `ION-12310` (and any sub-tasks) via `jira_get_issue` for
   acceptance criteria. Jira: `https://jira.dev.e2open.com/jira`. Confluence: `https://confluence.dev.e2open.com`.

Also run **`git_log`** (MCP git tools or git CLI) and **`kb_search`** on `cloud-sdk-api`/`cloud-sdk-aws` to
understand recent changes and **all existing usages** of any interface you intend to touch. Record findings
from `git_log` and `kb_search` in your summary and in the session context.

---

## 4. Branching strategy

- **Parent branch:** `feature/ION-12310-commons-cloudsdk-refactoring` (the integration branch for this effort).
  Ensure it exists and is based off `develop` (gitflow). Do **not** push or open PRs without explicit
  confirmation.
- **One feature branch per gap / enhancement**, branched **off the parent**, e.g.:
  - `feature/ION-12310-cloudsdk-g1-concurrent-sqs-listener`
  - `feature/ION-12310-cloudsdk-g2-putobject-metadata`
  - `feature/ION-12310-cloudsdk-g3-s3-event-notification`
  - `feature/ION-12310-cloudsdk-g4-dynamo-version-attribute`
  - `feature/ION-12310-cloudsdk-g5-thymeleaf-template-service`
  - `feature/ION-12310-cloudsdk-g6-composable-config-chain`
  - `feature/ION-12310-cloudsdk-g7-cloud-sdk-health-checks`
- Keep each branch **focused on a single gap** so it can be reviewed and merged independently. Verify
  compilation and tests on each branch before moving on.

---

## 5. Per-gap workflow (repeat for every gap / enhancement)

For each gap **first PLAN + DESIGN, then implement** (confirm before large or risky code changes):

### 5a. Design document
Create a detailed design doc under **`cloud-sdk-api/docs/`** named:

```
2026-06-01-<brief-description-of-change>-copilot-design.md
```

(e.g. `2026-06-01-concurrent-sqs-listener-copilot-design.md`). Each design doc must contain:
- **Gap reference** (G-id) and links to the source appianway docs and to `ION-12310`.
- **Problem statement** — the exact appianway usage/requirement the gap must satisfy.
- **Current state** in `cloud-sdk-api`/`cloud-sdk-aws` (what exists, what is missing) — cite specific
  classes/interfaces with workspace-relative links.
- **Proposed design** — new/changed interfaces in `cloud-sdk-api`, new/changed implementations in
  `cloud-sdk-aws`, with class, component, and sequence diagrams (mermaid). Show how it aligns with existing
  patterns (repository pattern, Guice modules, builder/Lombok, `QueueMessage<T>`, `StorageClient`,
  `MessagingClient`, `NotificationService`, `DatabaseRepository`, `TemplateService`/`EmailService`, etc.).
- **API-compatibility analysis** — prove no existing public signature breaks (additive only; new overloads,
  new types, default methods, or new classes). List every existing consumer found via `kb_search` and how
  it remains source- and binary-compatible.
- **Maven / dependency changes** (if any) and their transitive/OWASP impact.
- **Test plan** — JUnit 5 (Jupiter) unit tests with Mockito + AssertJ; integration tests via
  `dynamo-integration-test` where AWS interaction is involved; `@Category(IntegrationTests.class)` where
  appropriate.
- **Rollout/back-out** notes.

Log a `decision` entry in the session summarizing the chosen design.

### 5b. Implementation
Once the design is set (and confirmed for risky changes):
- Implement the abstraction in **`cloud-sdk-api`** first, then the implementation in **`cloud-sdk-aws`**.
- Follow the existing module patterns exactly: interfaces in `cloud-sdk-api`, AWS SDK **2.x** impls in
  `cloud-sdk-aws`, Guice modules for wiring, Lombok where the codebase already uses it, SLF4J logging,
  `Optional<T>` for absent returns, specific (not blanket) exception handling, and thread-safe/immutable
  shared state.
- Add unit tests for **every new public method**; add the integration tests described in the design.
- Keep methods focused (< ~50 lines) and follow Google code style. No unrelated refactoring.

### 5c. Verify
- Build only the touched modules incrementally: `mvn package -pl cloud-sdk-api,cloud-sdk-aws -am`.
- Run `mvn test`, then `mvn verify` (includes failsafe integration tests and DynamoDB-local integration
  tests where applicable). **All tests must pass** — including pre-existing tests unrelated to your change.
  If anything is red, root-cause and fix it; log in the session and iterate until green.
- If you find a bug, add a failing test that reproduces it **before** fixing.

---

## 6. Hard constraints (do not violate)

1. **No breaking changes to public APIs** of `cloud-sdk-api` or `cloud-sdk-aws`. They are consumed by
   upgraded `mercury-services` apps. Enhancements must be **additive** (new overloads, new types, default
   methods, new classes). If a behavior change is unavoidable, add an adapter and mark the old path
   `@Deprecated`, and **confirm with the user before removing anything**.
2. **Align with existing patterns** — do not introduce a parallel/competing abstraction style. Reuse the
   existing client/repository/template/Guice conventions.
3. **AWS SDK 2.x only** in `cloud-sdk-aws`. No AWS SDK v1 dependencies.
4. **Security:** no hardcoded credentials (IAM roles/env only); keep OWASP Top 10 in mind; do not regress
   existing OWASP/Netty/Handlebars fixes documented in `cloud-sdk-aws/docs/`.
5. **Incremental, one module/gap at a time**, verifying compilation and tests between steps.
6. **Do not push, force-push, open PRs, or comment on Jira/PRs** without explicit user confirmation.
7. **Documentation:** the design/plan markdown goes in `cloud-sdk-api/docs/` (per §5a). Do not create other
   stray markdown unless asked.

---

## 7. Suggested order of execution

1. Load/create session; read the master gap list (§2) and per-module designs; run `git_log` + `kb_search`.
2. Produce a short **master plan** entry (session `decision`) listing every gap, its feature-branch name,
   and its design-doc filename.
3. For each gap, in dependency-sensible order (G2 and G1 unblock the most consumers; G6/G7 are
   cross-cutting), execute the §5 workflow on its own feature branch.
4. After each gap is green, log a `progress` entry. After all gaps, write the final summary including the
   `git_log`/`kb_search` findings and the list of branches + design docs produced.

Begin by confirming the active session, the parent branch, and the full enumerated gap list (G1–G7 plus any
extras you discovered), then proceed gap-by-gap.
