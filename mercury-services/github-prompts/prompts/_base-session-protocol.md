---
name: _base-session-protocol
description: >
  Shared session context protocol included by all reusable prompts.
  Defines the standard pattern for session create/resume, context logging during work,
  and session completion. Reference this file — do not duplicate inline.
---

# Base Session Protocol

## Before Starting Any Work

1. `session_list` — search for an existing session matching this task's Jira tickets, module, or topic.
2. If found → `session_get` to load it and resume from where it left off.
3. If not found → `session_create` with:
   - `name`: descriptive slug, e.g. `<module>-<topic>-<yyyy-mm-dd>`
   - `project`: repo name, e.g. `mercury-services`
   - `tags`: all Jira ticket keys + module name + topic keywords + `"in-progress"`

## During Work — Add Context After Every Significant Action

| Action | Category |
|--------|----------|
| Reading Jira / support tickets | `finding` |
| Analyzing code, identifying root cause | `finding` |
| Decisions made (approach chosen, option rejected) | `decision` |
| Analysis doc written / plan produced | `progress` |
| Branch created / commits made | `progress` |
| Code changes implemented | `code_change` |
| Test written or run | `test_result` |
| Design doc generated | `progress` |
| Confluence page created/updated (include page id + URL) | `progress` |
| Blockers encountered | `blocker` |
| Model used | `model_info` |

## Context Window Management

If context fills above **85%**:
1. Persist all important details via `session_add_context` (category: `progress`) — include full summary of everything found so far, what remains, and where you left off.
2. Write all findings to the output document immediately so nothing is lost.

## On Completion

Call `session_update_status` with status `complete` and a short summary of what was produced (artifacts, page URLs, commit hashes, etc.).
