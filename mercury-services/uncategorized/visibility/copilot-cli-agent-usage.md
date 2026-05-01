# Copilot Agent Usage Guide — CLI vs Chat for Enterprise Refactoring

> **Date**: 2026-03-30  
> **Context**: Visibility AWS SDK 2.x Upgrade  
> **Session**: `6fd63aa02b1c4a75`

---

## Table of Contents

1. [CLI Agent vs Chat Agent — Which to Use](#1-cli-agent-vs-chat-agent--which-to-use)
2. [Copilot CLI Agent (`gh copilot`) — Setup & Basics](#2-copilot-cli-agent-gh-copilot--setup--basics)
3. [Prompt Files (`.prompt.md`) — Reusable Task Definitions](#3-prompt-files-promptmd--reusable-task-definitions)
4. [Skills — Domain-Specific Knowledge](#4-skills--domain-specific-knowledge)
5. [MCP Context Server — Session Continuity](#5-mcp-context-server--session-continuity)
6. [Copilot Instructions — Workspace-Level Rules](#6-copilot-instructions--workspace-level-rules)
7. [Best Practices for Large Refactoring Tasks](#7-best-practices-for-large-refactoring-tasks)
8. [Recommended Workflow for Visibility Upgrade](#8-recommended-workflow-for-visibility-upgrade)
9. [Prompt Engineering Tips](#9-prompt-engineering-tips)
10. [Troubleshooting & Common Issues](#10-troubleshooting--common-issues)

---

## 1. CLI Agent vs Chat Agent — Which to Use

### Overview

| Feature | **VS Code Chat Agent** (Copilot Chat) | **CLI Agent** (`gh copilot` in terminal) |
|---------|---------------------------------------|------------------------------------------|
| Interface | VS Code sidebar panel | Terminal (`gh copilot coding-agent`) |
| Context window | Larger — includes open files, editor state, workspace structure | Terminal-focused — reads files explicitly |
| File editing | Direct in-editor editing with diffs | Edits files via terminal tools |
| MCP tools | Full access to configured MCP servers | Full access to configured MCP servers |
| Skills | Auto-loaded from `.github/skills/` | Auto-loaded from `.github/skills/` |
| Prompts | Click to run from `.github/prompts/` | Reference via `--prompt` flag or inline |
| Git operations | Via MCP git tools + terminal | Native terminal git — more natural |
| Build/Test | Via terminal tool | Native terminal — more natural |
| Multi-turn | Full conversation history | Full conversation history |
| Parallelism | Can run multiple tool calls in parallel | Sequential terminal execution |
| Best for | Code exploration, review, design docs, complex edits across many files | Build-test-fix cycles, git operations, incremental refactoring, CI/CD tasks |

### Recommendation for the Visibility Upgrade

**Use the VS Code Chat Agent (Copilot Chat) for the visibility refactoring.** Here's why:

1. **Large-scale cross-file edits** — The upgrade touches 50+ files across 11 sub-modules. The Chat agent can read multiple files in parallel, understand relationships, and make coordinated edits.

2. **Design document references** — The agent needs to read the plan (`visibility-aws2x-plan.md`), reference modules (webbl, booking-bridge, booking), and the current state doc. The Chat agent handles multi-file context naturally.

3. **MCP session context** — Both agents can use the MCP Context Server, but the Chat agent's larger context window means it can hold more session history in working memory.

4. **Skills auto-loading** — The `java-refactoring` and `session-context` skills are automatically available in both, but the Chat agent tends to invoke them more reliably.

5. **Iterative refinement** — When tests fail, the Chat agent can read test output, identify the fix, and edit the file without switching context.

**Use the CLI Agent for**:
- Git operations (branch creation, cherry-pick, rebase)
- Running Maven builds and inspecting output
- Quick one-off tasks where you want to stay in terminal flow
- CI/CD debugging

**Hybrid approach** (recommended):
- Use **Chat agent** for the main refactoring work (Phases 1-5)
- Use **terminal directly** for git operations (the cherry-pick/rebase strategy)
- Use **Chat agent** to verify test results and iterate on fixes

---

## 2. Copilot CLI Agent (`gh copilot`) — Setup & Basics

### Prerequisites

```bash
# Ensure GitHub CLI is installed and authenticated
gh --version
gh auth status

# Verify Copilot extension is available
gh extension list | grep copilot
```

### Running the CLI Agent

```bash
# Start an interactive coding agent session
gh copilot coding-agent

# Or use the VS Code terminal (the agent inherits VS Code's MCP configuration)
```

### Key Capabilities

The CLI agent can:
- Read and edit files in the workspace
- Run terminal commands (build, test, git)
- Use MCP tools (session context, git, Jira, Confluence, KB)
- Follow `.github/copilot-instructions.md` automatically
- Load skills from `.github/skills/`
- Execute prompt files from `.github/prompts/`

### Example CLI Session

```bash
# Start the agent
gh copilot coding-agent

# Give it a task with context
> Load session 6fd63aa02b1c4a75 and start Phase 1 of the visibility AWS upgrade. 
> Follow the plan in visibility/docs/visibility-aws2x-plan.md.
> Start with POM changes in the parent pom.xml and visibility-commons/pom.xml.
```

---

## 3. Prompt Files (`.prompt.md`) — Reusable Task Definitions

### What Are Prompt Files?

Prompt files are pre-written task instructions stored in `.github/prompts/`. They define:
- The task to perform
- Which agent mode and model to use
- Which tools the agent can access
- References to relevant files and context
- Success criteria

### Location

```
.github/prompts/
├── visibility-aws-upgrade-plan.prompt.md    ← Used to generate the upgrade plan
├── visibility-curr-state.prompt.md          ← Used to generate DESIGN-curr-state.md
├── bk-runtime-issues.prompt.md              ← Booking runtime fix task
├── booking-email-test-restore.prompt.md     ← Email test restoration task
└── lambda-workaround.prompt.md              ← Lambda jar size fix
```

### Prompt File Structure

```yaml
---
name: descriptive-name
description: What this prompt does
argument-hint: "none"          # or describe expected arguments
agent: agent                   # use "agent" for agentic mode
model: Claude Opus 4.6 (copilot)
tools:                         # which tools the agent can use
  - execute                    # terminal commands
  - read                       # file reading
  - edit                       # file editing
  - search                     # code search
  - mcp-context-server/*       # all MCP context server tools
---
# Task instructions

Detailed instructions for the agent...

# References

Links to relevant files, documents, branches...

# Produce

What output is expected...
```

### How to Use Prompts

**In VS Code Chat:**
1. Open the Copilot Chat panel
2. Click the "Attach" icon (📎) or type `#`
3. Select "Prompt..." and pick from the list
4. Or type `@workspace /prompt visibility-aws-upgrade-plan`

**In CLI Agent:**
```bash
# Reference the prompt when starting
gh copilot coding-agent --prompt ".github/prompts/visibility-aws-upgrade-plan.prompt.md"
```

### Creating a Prompt for Visibility Implementation

For the actual refactoring, create a new prompt. Here's a template:

```yaml
---
name: visibility-aws-upgrade-impl
description: Execute the visibility AWS SDK 2.x upgrade based on the plan
argument-hint: "phase number (0-5) or 'all'"
agent: agent
model: Claude Opus 4.6 (copilot)
tools:
  - execute
  - read
  - edit
  - search
  - mcp-context-server/*
---
# Task instructions

Execute the visibility AWS SDK 2.x upgrade following the plan in 
visibility/docs/visibility-aws2x-plan.md.

## Before starting
1. Load session context: session_get(session_id="6fd63aa02b1c4a75")
2. Read the plan: visibility/docs/visibility-aws2x-plan.md
3. Read current state: visibility/docs/DESIGN-curr-state.md
4. Create a NEW session for the implementation work (link to planning session)

## Phase to execute
Execute the phase specified in the argument. If "all", execute all phases sequentially.

## After each phase
1. Run: mvn compile -pl visibility -am
2. Run: mvn test -pl visibility/{changed-submodule}
3. Log results to session context
4. If tests fail, fix and iterate

## Reference modules
- webbl/src/main/java (DynamoDB, SQS, SNS, S3, SES patterns)
- booking-bridge/src/main/java (DynamoDB, SQS patterns)
- booking/src/main/java (complex DynamoDB, Lambda patterns) — on branch via cherry-pick

## Rules
- Follow the java-refactoring skill
- Follow the session-context skill
- Never break existing tests
- Log every significant action to session context
```

---

## 4. Skills — Domain-Specific Knowledge

### What Are Skills?

Skills are instruction files in `.github/skills/` that the agent **automatically loads** when a task matches their described purpose. They provide domain-specific workflows, rules, and patterns.

### Available Skills in This Workspace

```
.github/skills/
├── java-refactoring/SKILL.md      ← Library upgrade workflow + rules
├── session-context/SKILL.md       ← MCP session management protocol
├── git-operations/SKILL.md        ← Safe rebase/merge/force-push workflow
├── aws-skills/aws-dynamo-check.md ← DynamoDB schema verification
└── pr-reviews/                    ← PR review workflow files
    ├── pr-context.md
    ├── pr-review-comments.md
    └── pr-review-responses.md
```

### Skill: `java-refactoring`

**Triggers when**: Library upgrade, API migration, Maven dependency changes, module refactoring.

**What it provides**:
- Step-by-step workflow: Gather requirements → Assess impact → Execute module by module → Final verification
- AWS upgrade context: Lists all upgraded modules as reference
- Rules: Never break public API, watch transitive dependencies, verify Jackson serialization, run integration tests
- Commands: `mvn compile`, `mvn test`, `mvn verify` patterns

**How the agent uses it**: When you ask for a code change, the agent checks if `java-refactoring` SKILL.md matches the task. If it does, the agent reads the skill file and follows its workflow before making changes.

### Skill: `session-context`

**Triggers when**: Multi-step work, Jira tickets, refactoring across conversations.

**What it provides**:
- Protocol: START → check for existing sessions → load or create
- DURING: Log every action with `session_add_context()`
- END: Add summary, mark completed

**Critical for visibility upgrade**: The session `6fd63aa02b1c4a75` contains all planning decisions, git analysis, and implementation details. Any new agent conversation should load this session first.

### Skill: `git-operations`

**Triggers when**: Rebase, merge, force-push, conflict resolution.

**What it provides**:
- Safe rebase workflow with conflict prediction
- `--force-with-lease` enforcement (never bare `--force`)
- Squash and cleanup patterns
- Stash management

### Skill: `aws-skills/aws-dynamo-check`

**Triggers when**: DynamoDB schema verification against live AWS tables.

**What it provides**:
- AWS CLI commands to describe live table schemas
- Comparison methodology: live schema vs model class annotations
- JSON reference files for existing table schemas (booking tables)

---

## 5. MCP Context Server — Session Continuity

### What Is It?

The MCP (Model Context Protocol) Context Server is an external tool server that provides persistent storage for session context across agent conversations. It's configured in VS Code's MCP settings and provides these operations:

| Tool | Purpose |
|------|---------|
| `session_create` | Start a new tracked session |
| `session_get` | Load an existing session's full context |
| `session_list` | Find sessions by status, project, tags |
| `session_search` | Search across all sessions |
| `session_add_context` | Log an action/decision/finding |
| `session_update_status` | Mark active/completed/paused |
| `session_delete` | Remove a session |

### Additional MCP Tools Available

The MCP Context Server also provides:

| Tool Category | Tools | Purpose |
|---------------|-------|---------|
| **Git** | `git_log`, `git_diff`, `git_status`, `git_blame`, `git_branches`, `git_file_history`, `git_show_file` | Repository operations without terminal |
| **Jira** | `jira_get_issue`, `jira_search`, `jira_get_comments`, `jira_add_comment` | Ticket lookup and management |
| **Confluence** | `confluence_search`, `confluence_get_page`, `confluence_page_children`, `confluence_space_pages` | Documentation access |
| **Knowledge Base** | `kb_search`, `kb_grep`, `kb_read_file`, `kb_find_files`, `kb_list_directory` | Workspace file search across multiple repos |

### Current Visibility Session

```
Session ID: 6fd63aa02b1c4a75
Name: "Visibility Module - AWS 2.x Upgrade Plan"
Project: mercury-services
Status: completed (planning phase)
Entries: 9

Key entries:
1. Progress: Initial analysis started
2. Finding: 11 sub-modules, 134 tests, 5 DAOs, AWS SDK v1 usage catalog
3. Progress: Both documents created
4. Decision: Architectural decisions (phase approach, SQS/DynamoDB/S3 patterns)
5. Progress: Session complete (planning phase)
6. Code change: Section numbering fix
7. Finding: CORRECTED — booking commit only touches booking/ (223 files, zero overlap)
8. Code change: Updated both docs with corrected git findings
9. Progress: FINAL — comprehensive implementation details
```

### How to Use Sessions for Visibility Implementation

**Starting a new implementation conversation:**
```
# Agent's first action should be:
session_list(project="mercury-services", status="completed")
# → finds 6fd63aa02b1c4a75

session_get(session_id="6fd63aa02b1c4a75")
# → loads all 9 entries with planning context

session_create(
  name="Visibility AWS Upgrade - Implementation Phase 1",
  project="mercury-services",
  tags=["visibility", "aws-upgrade", "implementation", "phase-1"]
)
# → creates new session for implementation, reference the planning session
```

**Linking sessions:**
```
session_add_context(
  session_id="<new-session-id>",
  summary="Linked to planning session 6fd63aa02b1c4a75",
  category="progress",
  detail="Planning session contains: upgrade plan (20 sections), git strategy (cherry-pick + rebase-drop), verified facts (booking commit scope, develop delta), architectural decisions",
  references=["6fd63aa02b1c4a75", "visibility/docs/visibility-aws2x-plan.md"]
)
```

---

## 6. Copilot Instructions — Workspace-Level Rules

### What Is `copilot-instructions.md`?

The file `.github/copilot-instructions.md` is automatically loaded by every Copilot agent conversation in this workspace. It defines:

- **Project structure** — Which modules exist, which are upgraded
- **Tech stack** — JDK 17, Dropwizard, Maven, JUnit 5, Mockito
- **Session context protocol** — Mandatory session management rules
- **Code quality rules** — Never break tests, preserve API compatibility, null safety
- **Testing conventions** — AssertJ, parameterized tests, `@Nested` grouping
- **Refactoring guidelines** — Assess impact, plan changes, incremental execution
- **Common patterns** — Builder, Repository, Service layer, Guice DI

### Key Rules the Agent Follows Automatically

1. **Before any code change**: Check for active sessions, load context
2. **Plan first**: Create TODO list, document in `docs/` folder
3. **Test after every change**: `mvn test`, `mvn verify`
4. **Log everything**: Decisions, findings, blockers, test results to session context
5. **Never break existing tests**: Fix broken tests before proceeding
6. **Integration tests**: Use `dynamo-integration-test` for DynamoDB testing

### How It Affects Your Prompts

You don't need to repeat these rules in your prompts — the agent reads them automatically. Your prompts should focus on **what to do**, not **how to work**. The instructions file handles the "how."

---

## 7. Best Practices for Large Refactoring Tasks

### 1. Break Work into Phases

Don't ask the agent to do everything at once. Use the phases from the plan:

```
# Good — focused, one phase at a time
"Execute Phase 1 from the visibility upgrade plan. Only POM changes."

# Bad — too broad, likely to exceed context window
"Do the entire visibility AWS SDK upgrade."
```

### 2. One Sub-Module at a Time Within a Phase

For Phase 3 (6 Dropwizard services), do one service per conversation:

```
"Execute Phase 3 for visibility-inbound. Follow the plan section 7.1."
```

### 3. Always Reference the Plan and Session

Start every conversation with:
```
Load session 6fd63aa02b1c4a75 for the planning context.
Read visibility/docs/visibility-aws2x-plan.md for the plan.
Then execute [specific phase/task].
```

### 4. Verify Between Phases

After each phase, explicitly ask:
```
"Run mvn compile -pl visibility -am and show me any compilation errors."
"Run mvn test -pl visibility/visibility-commons and show me the test results."
```

### 5. Use Reference Modules

When the agent isn't sure how to implement something:
```
"Look at how webbl/src/main/java/.../config/WebBLDynamoModule.java creates the 
DynamoRepositoryFactory and replicate that pattern for VisibilityDynamoModule."
```

### 6. Persist Context at Conversation Boundaries

If the context window is filling up (agent mentions it, or responses get slower):
```
"Persist your current progress and TODO list to the session context, 
then we'll continue in a new conversation."
```

### 7. Use Dual-Workspace Pattern

The visibility upgrade references `mercury-services-commons` (cloud-sdk-api, cloud-sdk-aws). Keep that workspace open too:
```
"Check the StorageClient interface in mercury-services-commons cloud-sdk-api module 
to understand the putObject method signature."
```

### 8. Commit Incrementally

Don't wait until everything is done:
```
"Phase 1 is complete and compiling. Commit with message: 
'Phase 1: POM dependency changes for visibility AWS SDK 2.x upgrade'"
```

---

## 8. Recommended Workflow for Visibility Upgrade

### Step 0: Branch Setup (Do Yourself in Terminal)

```bash
git checkout develop
git pull origin develop
git checkout -b feature/visibility-aws-sdk-2x-upgrade
git fetch origin feature/ION-14382-bk3-aws-upgrade-2
git cherry-pick 74f36e7a71
# Verify: git log --oneline develop..HEAD  → 1 commit (booking)
```

### Step 1: Phase 1 — POM Changes (Chat Agent)

```
@workspace Load session 6fd63aa02b1c4a75 and read visibility/docs/visibility-aws2x-plan.md 
Section 5 (Phase 1). Execute the POM changes for all 11 sub-modules. 
Create a new implementation session. 
After changes, run mvn compile -pl visibility -am.
```

### Step 2: Phase 2 — visibility-commons (Chat Agent, Multiple Conversations)

This is the largest phase. Break it into sub-tasks:

**Conversation 2a — DynamoDB Models + Converters:**
```
Load the implementation session. Execute Phase 2, sections 6.1 and 6.2 from the plan.
Migrate DynamoDB entity classes and create all AttributeConverter implementations.
Run mvn test -pl visibility/visibility-commons after changes.
```

**Conversation 2b — DAOs:**
```
Load the implementation session. Execute section 6.3 — migrate all 5 DAO classes.
Run mvn test -pl visibility/visibility-commons after changes.
```

**Conversation 2c — SQS/S3/SNS + Guice Modules + Config:**
```
Load the implementation session. Execute sections 6.4 through 6.9.
Run mvn test -pl visibility/visibility-commons after changes.
```

### Step 3: Phase 3 — Dropwizard Services (Chat Agent, One Per Service)

```
# For each of the 6 services:
Load the implementation session. Execute Phase 3 for visibility-inbound (section 7.1).
Run mvn test -pl visibility/visibility-inbound after changes.
```

### Step 4: Phase 4 — Lambda Functions (Chat Agent)

```
Load the implementation session. Execute Phase 4 for all 4 Lambda functions.
Run mvn test for each Lambda sub-module.
```

### Step 5: Phase 5 — Booking Alignment (Chat Agent)

```
Load the implementation session. Execute Phase 5 — align BookingDetailVisibility 
and BookingDao with the upgraded booking models from the cherry-picked commit.
Run mvn verify -pl visibility -am (full verification).
```

### Step 6: Integration Tests (Chat Agent)

```
Load the implementation session. Create DynamoDB integration tests as described 
in the plan Section 18. Run mvn verify to execute them.
```

### Step 7: Final Verification + Commit

```bash
# In terminal
mvn clean verify -pl visibility -am
git add -A
git commit -m "Visibility AWS SDK 2.x upgrade - cloud-sdk migration"
git push -u origin feature/visibility-aws-sdk-2x-upgrade
```

### Step 8: Pre-PR Rebase (When Booking Merges)

```bash
git checkout develop && git pull origin develop
git checkout feature/visibility-aws-sdk-2x-upgrade
git rebase -i develop
# DROP the booking cherry-pick commit, KEEP all visibility commits
git push --force-with-lease
```

---

## 9. Prompt Engineering Tips

### Be Specific About Scope

```
# Good
"Migrate ContainerEventDao from DynamoDBCrudRepository to DatabaseRepository.
Follow the pattern in webbl WayBillDao."

# Bad  
"Update the DAOs"
```

### Reference Exact Plan Sections

```
# Good
"Execute plan section 6.4 — SQS Migration in visibility-commons"

# Bad
"Do the SQS stuff"
```

### Give the Agent an Exit Condition

```
# Good
"Keep iterating until mvn test -pl visibility/visibility-commons passes with 0 failures"

# Bad
"Fix the tests"
```

### Use the Session as Breadcrumbs

```
"Before starting, check the session for any blockers or findings from the previous 
conversation. Then continue with the next TODO item."
```

### Include the Model Preference

The prompt file header specifies the model. For complex refactoring, use:
```yaml
model: Claude Opus 4.6 (copilot)
```

### After Errors, Give Full Context

```
# Good
"The test ContainerEventDaoTest fails with: 
java.lang.ClassCastException: cannot cast DefaultPartitionKey to DynamoHashKey
Show me the test code and fix the mock setup."

# Bad
"Tests are failing, fix them"
```

---

## 10. Troubleshooting & Common Issues

### Agent Loses Context Mid-Conversation

**Symptom**: Agent forgets what it was doing or re-reads files unnecessarily.  
**Fix**: Persist progress to session context, start a new conversation, and load the session.

### Agent Makes Changes to Wrong Files

**Symptom**: Edits a file in the wrong module or creates unnecessary files.  
**Fix**: Be explicit about file paths. Use `visibility/visibility-commons/src/main/java/...` not just "the DAO file."

### Maven Build Fails After Agent Edits

**Symptom**: Compilation errors after agent edits.  
**Fix**: Ask the agent to read the error output and fix. Always verify with `mvn compile` before asking for more changes.

### Agent Doesn't Load Skills

**Symptom**: Agent doesn't follow the `java-refactoring` workflow.  
**Fix**: Explicitly reference the skill: "Follow the java-refactoring skill for this task."

### Session Context Lost

**Symptom**: `session_get` returns empty or stale data.  
**Fix**: Check `session_list(project="mercury-services")` to find sessions. Sessions persist across conversations.

### Context Window Fills Up

**Symptom**: Agent responses get truncated or it says the context is too large.  
**Fix**: 
1. Persist current state to session context
2. Start a new conversation
3. Load the session in the new conversation
4. Continue from where you left off

### Cherry-Pick Commit Creates Merge Conflicts

**Symptom**: `git cherry-pick 74f36e7a71` fails.  
**Fix**: As of 2026-03-30, there is **zero file overlap** between the booking commit and latest develop. If conflicts appear later (develop changed booking/ files), resolve using the `git-operations` skill workflow:
```bash
git cherry-pick --abort  # start over
git pull origin develop  # get latest
git cherry-pick 74f36e7a71  # retry
# If conflicts: resolve, git add, git cherry-pick --continue
```

---

## Quick Reference Card

| What | Where |
|------|-------|
| Upgrade plan | `visibility/docs/visibility-aws2x-plan.md` |
| Confluence doc | `visibility/docs/CONFLUENCE-visibility.md` |
| Current state analysis | `visibility/docs/DESIGN-curr-state.md` |
| Planning session ID | `6fd63aa02b1c4a75` |
| Copilot instructions | `.github/copilot-instructions.md` |
| Java refactoring skill | `.github/skills/java-refactoring/SKILL.md` |
| Session context skill | `.github/skills/session-context/SKILL.md` |
| Git operations skill | `.github/skills/git-operations/SKILL.md` |
| AWS DynamoDB check | `.github/skills/aws-skills/aws-dynamo-check.md` |
| Upgrade plan prompt | `.github/prompts/visibility-aws-upgrade-plan.prompt.md` |
| Booking feature branch | `feature/ION-14382-bk3-aws-upgrade-2` |
| Booking commit to cherry-pick | `74f36e7a71` |
| Target visibility branch | `feature/visibility-aws-sdk-2x-upgrade` |
| cloud-sdk version | `1.0.22-SNAPSHOT` |
| commons version | `1.R.01.021` |

---

*End of Document*
