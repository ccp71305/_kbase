---
name: design-doc
description: >
  Generate a Confluence architecture/defect-fix design document from an analysis file and
  publish it to the BRM Confluence space. Use this skill whenever the user wants to create a
  design doc, write up a fix for Confluence, document a change, or publish engineering findings.
  Triggers on: /design-doc, "create design doc", "write up the design", "publish design doc",
  "document this for Confluence", "generate design doc for ION-xxxxx".
  Always use this skill after analyze-issue has produced an analysis document.
---

# design-doc

Delegate to the full workflow in `.github/prompts/designdocs/confluence-design-doc-generator.md`.

## Parse the invocation

Extract from the user's message:

| Field | How to find it | Required | Default |
|---|---|---|---|
| `JIRA_TICKETS` | Any `ION-xxxxx` keys | yes | — |
| `SUPPORT_TICKETS` | Any `PDSUPPORT-xxxxx` keys | no | — |
| `MODULE` | Module name mentioned | yes | — |
| `CONFLUENCE_PAGE_TITLE` | Quoted string or explicit title | yes | — |
| `CONFLUENCE_PARENT_PAGE_ID` | Numeric page ID | yes | — |
| `CONFLUENCE_SPACE_KEY` | Space key if specified | no | `BRM` |
| `INPUT_ANALYSIS_FILE` | File path if given, else find the most recent analysis doc under `<MODULE>/docs/` matching the first Jira key | yes | auto-detect |
| `REFERENCE_PAGE_ID` | Explicit reference page ID if given | no | `""` |

**Auto-detecting the analysis file:** if not explicitly given, search `<MODULE>/docs/` for a
markdown file whose name contains the first Jira key or was created today. Ask the user to
confirm if more than one candidate is found.

## Execute the workflow

Read `.github/prompts/designdocs/confluence-design-doc-generator.md` and follow it exactly,
substituting the parsed values above into the PARAMETERS block mentally.

For publish steps, also read `.github/prompts/designdocs/_base-confluence-publisher.md`.
