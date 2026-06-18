---
name: confluence-api-design-generator
description: >
  Reusable prompt to generate an API design document and publish it to Confluence.
  Covers endpoint contracts, request/response schemas, versioning, authentication, and error codes.
  To reuse: fill the PARAMETERS block and run.
argument-hint: "none — edit the PARAMETERS block below"
agent: agent
model: Claude Opus 4.6 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# API Design Document Generator — Confluence Publisher (Reusable)

> **Session protocol:** see `.github/prompts/_base-session-protocol.md`
> **Publish steps (4–5):** see `.github/prompts/designdocs/_base-confluence-publisher.md`

---

## PARAMETERS — Change these for each new document

```yaml
INPUT_ANALYSIS_FILE: "<module>/docs/<source-doc>.md"
MODULE: "<module>"
JIRA_TICKETS:
  - "<JIRA-KEY>"

CONFLUENCE_PARENT_PAGE_ID: "<parent-page-id>"
CONFLUENCE_SPACE_KEY: "<space-key>"
CONFLUENCE_PAGE_TITLE: "<Page Title>"

DESIGN_DOC_TEMPLATE: ".github/prompts/designdocs/templates/api-design-template.md"
```

---

## Steps

1. Read `INPUT_ANALYSIS_FILE` and `DESIGN_DOC_TEMPLATE`.
2. Fetch Jira details for each ticket in `JIRA_TICKETS`.
3. Generate the API design document following the template. Write to
   `<MODULE>/docs/<yyyy-mm-dd>-api-design-<first-jira-ticket>.md`.
4. Present to user for review.
5. Follow `.github/prompts/designdocs/_base-confluence-publisher.md` Steps 4–5 to publish.
