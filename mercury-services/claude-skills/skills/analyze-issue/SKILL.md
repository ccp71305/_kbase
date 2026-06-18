---
name: analyze-issue
description: >
  Analyze a reported issue, defect, or module behavior to identify root cause and produce a
  structured implementation plan. Use this skill whenever the user wants to investigate a
  problem, understand why something is failing, plan a fix, or analyze a module for a specific
  purpose — whether they have a Jira ticket, a team message, a pasted description, a file, or
  just a module name and a goal. Triggers on: /analyze-issue, "analyze this issue",
  "find root cause", "investigate why", "what's causing", "analyze the X module for Y".
  Always use this skill before starting any defect fix or implementation work.
---

# analyze-issue

Delegate to the full analysis workflow in `.github/prompts/analysis/issue-analysis-generator.md`.

## Parse the invocation

Extract from the user's message (all fields except module+goal are optional):

| Field | How to find it | Example |
|---|---|---|
| `MODULE` | First or only module name mentioned | `booking`, `visibility` |
| `JIRA_TICKETS` | Any `ION-xxxxx` keys | `ION-16032` |
| `SUPPORT_TICKETS` | Any `PDSUPPORT-xxxxx` keys | `PDSUPPORT-203319` |
| `GOAL` | Free-form issue description or analysis goal | "date parsing fails on old records" |
| `NOTES_FILE` | Any file path mentioned (must be under `<module>/docs/`) | `booking/docs/notes.md` |
| `BRANCH_NAME` | Explicit branch name if given, else derive from first Jira key | `defect/ION-16032-short-desc` |

**If a notes file is referenced**, read it first and treat its content as additional context
alongside whatever was in the invocation message.

**If no Jira ticket is given**, proceed with the description/goal as the issue source.
Skip the Jira fetch step and note the absence in the session context.

## Execute the workflow

Read `.github/prompts/analysis/issue-analysis-generator.md` and follow it exactly,
substituting the parsed values above into the PARAMETERS block mentally.

Use these defaults:
- `COMMIT_PREFIX`: first Jira key if present, else `"NO-TICKET"`
- `TEST_DRIVEN`: `true`
- `OUTPUT_ANALYSIS_DOC`: `<MODULE>/docs/<yyyy-mm-dd>-<short-slug>.md`
- `CONFLUENCE_SPACE_KEY`: `BRM`
