---
name: session-context
description: >
  **MCP SKILL** — Manage persistent session contexts across agent conversations.
  USE FOR: starting work on a Jira ticket; resuming multi-conversation refactoring;
  tracking decisions, findings, blockers, and progress across agent sessions.
  INVOKES: session_create, session_get, session_list, session_add_context,
  session_update_status, session_search, session_delete via MCP.
tools:
  - session_create
  - session_get
  - session_list
  - session_add_context
  - session_update_status
  - session_search
  - session_delete
---

# Session Context Management

## Protocol

At the **START** of every multi-step conversation:
1. `session_list(status="active", project="mercury-services-commons")` — check for existing sessions
2. If found: `session_get(session_id)` — load context
3. If not: `session_create(name="<ticket> <description>", project="mercury-services-commons", tags=[...])`

**DURING** work — after every significant action:
```
session_add_context(session_id, summary="...", category="decision|finding|blocker|progress|code_change|test_result", detail="...", references=["files", "JIRA-KEY"])
```

At the **END**:
```
session_add_context(session_id, summary="Session paused: <state>", category="progress")
session_update_status(session_id, "completed")  # if done
```
