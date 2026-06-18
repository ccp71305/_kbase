---
name: confluence-design-doc-generator
description: >
  Reusable prompt to generate a design document from an analysis/design/implementation
  markdown file and publish it to Confluence via the mcp-context-server write tools.
  To reuse: set the PARAMETERS block (analysis file, Confluence parent page, space, title,
  Jira tickets) and run. Works for any module/ticket — nothing here is hard-coded to a
  specific change.
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

# Design Document Generator — Confluence Publisher (Reusable)

Generate a Confluence design document from a source analysis/implementation markdown file,
following the standard template, and publish it to Confluence using the **mcp-context-server
write tools**. This prompt is parameter-driven — change only the PARAMETERS block to reuse it
for any ticket, module, or parent page.

> **Session protocol:** see `.github/prompts/_base-session-protocol.md` — follow it strictly.
> **Publish steps (4–5):** see `.github/prompts/designdocs/_base-confluence-publisher.md`.
> **Setup prerequisite (one-time):** see `.github/prompts/designdocs/SETUP-confluence-mcp.md`
> if any tool returns `"... is not configured"` or `401`. Do **not** fall back to `curl`.

---

## PARAMETERS — Change these for each new document

```yaml
# ─── INPUT ────────────────────────────────────────────────────────────
# Path (repo-relative) to the analysis / design / implementation markdown that is the
# SOURCE OF TRUTH for this design doc. All content is derived from this file.
INPUT_ANALYSIS_FILE: "<module>/docs/<analysis-design-impl>.md"
MODULE: "<module>"            # e.g. booking, visibility, oceanschedules
JIRA_TICKETS:                  # all relevant tickets (defects, stories, support)
  - "<JIRA-KEY>"

# ─── CONFLUENCE TARGET ────────────────────────────────────────────────
CONFLUENCE_PARENT_PAGE_ID: "<parent-page-id>"   # the page the new doc nests under
CONFLUENCE_SPACE_KEY: "<space-key>"             # e.g. ~akundu (personal) or BRM (team)
CONFLUENCE_PAGE_TITLE: "<Page Title>"           # must be unique within the space

# ─── TEMPLATE & STYLE REFERENCE ───────────────────────────────────────
DESIGN_DOC_TEMPLATE: ".github/prompts/designdocs/templates/architecture-template.md"
REFERENCE_PAGE_ID: ""          # optional: an existing Confluence page to match style/depth
```

---

## CRITICAL CONSTRAINTS

1. **READ the analysis file first** — all content comes from `INPUT_ANALYSIS_FILE`. Do not invent
   information that is not in the source.
2. **Follow the template** — use every section from `DESIGN_DOC_TEMPLATE`; sections with no
   applicable content get `N/A`.
3. **Lucid and crisp** — clear, scannable prose; prefer tables and diagrams over walls of text.
4. **Publish via MCP write tools** — use `confluence_create_page` / `confluence_update_page`.
   NEVER use `curl`, and never prompt for or hard-code credentials (the MCP server handles auth).
5. **Escape XHTML** — the #1 cause of publish failures. Full rules in `_base-confluence-publisher.md` Step 4c.
6. **Review before publish** — generate the markdown, show the user, publish only after
   confirmation (skip the wait only if the user explicitly says "publish without review").

---

## Session Context Protocol

> Follow `.github/prompts/_base-session-protocol.md` strictly.
>
> **Session name pattern:** `design-doc-<first-jira-ticket>-<yyyy-mm-dd>`
> **Tags:** all Jira ticket keys + module name + `"design-doc"` + `"confluence"`
>
> Design-doc-specific context entries:
> - After reading analysis file → `finding`
> - After generating the design doc → `progress`
> - After publishing (include page id + URL) → `progress`

---

## Step 1 — Gather Context

1a. **Read the analysis file** (`INPUT_ANALYSIS_FILE`). Extract: problem & root cause; fix approach
and rationale; code changes (components, files, methods); test strategy & results; impact;
security considerations.

1b. **Read the template** (`DESIGN_DOC_TEMPLATE`) for section structure and table formats.

1c. **(Optional) Read the reference page** for style: `confluence_get_page(REFERENCE_PAGE_ID)`.

1d. **Fetch Jira details** for each key in `JIRA_TICKETS`: `jira_get_issue(<key>)`. Extract summary,
type, priority, status, assignee, reporter. (If Jira is not configured, fill the table from the
analysis file and note it.)

---

## Step 2 — Generate the Design Document

Write the markdown to: `<MODULE>/docs/<yyyy-mm-dd>-design-doc-<first-jira-ticket>.md`

Map content from the analysis file onto each template section. Guidance:

- **Requirements** — Jira table (Step 1d), support-ticket table if any, a 2–4 sentence summary
  (what was broken, who was affected, what the fix achieves), and a technology-stack table.
- **Assumptions and Open Issues** — assumptions made and any open questions, with status.
- **High Level Design** — architectural overview + before/after behavior. Use Mermaid diagrams
  (`graph` / `sequenceDiagram`) where they clarify request flow and where the fix applies.
- **Low Level Design** — Key Components table (component, location, purpose, key changes);
  include Guice load order / AWS services / DynamoDB subsections only if relevant; a component
  interaction Mermaid sequence diagram.
- **UI** — `N/A` unless there is UI impact.
- **API Architecture** — affected endpoints (method, path, description, change) and any
  request/response contract changes.
- **Configuration** — model-level (YAML/properties), stack-level (Jetty/JVM/container), and
  professional-services/SI config.
- **Auditing/Logging** — new log statements, event-publishing/lifecycle changes.
- **Metrics / Installer / Temporary cleanup / Impact on Tools** — `N/A` unless applicable.
- **Impact on Current Application** — runtime behavior, performance, deployment (rolling restart?
  config change? coordinated deploy?).
- **Resiliency** — failover / error-handling changes.
- **Impact on Other Components** — cross-module, shared-library, other-service impact.
- **Backwards Compatible** — breaking change? deployable independently? data migration?
- **Unit Test Plan** — table of new test classes/methods with coverage; note modified tests.
- **Pre-Dev Security** — fill the checklist honestly; pay attention to input validation, path
  traversal, and injection.
- **Required Documentation Changes** — answer the user/API/ops questions.
- **Blocking Issues** — leave empty or note known blockers.
- **Review** — Author = Approved; reviewers = Pending.

---

## Step 3 — Review

Present the generated markdown to the user. Summarize: sections populated vs `N/A`, diagrams
included, Jira references, and any section needing user input. Wait for confirmation before
publishing (unless the user opted out of review).

---

## Step 4 — Publish to Confluence

> Follow all steps in `.github/prompts/designdocs/_base-confluence-publisher.md` (Steps 4–5):
> XHTML conversion table, `confluence_create_page` / `confluence_update_page` call signatures,
> error handling (`400` / `401` / not-configured), and verify & report.

---

## Output Checklist

- [ ] Session context with full traceability (findings, decisions, publish URL)
- [ ] Design-doc markdown at `<MODULE>/docs/<yyyy-mm-dd>-design-doc-<first-jira-ticket>.md`
- [ ] Confluence page created/updated under the specified parent
- [ ] All template sections populated (content or `N/A`)
- [ ] Mermaid diagrams for architecture/flow; Jira keys linked via the jira macro
- [ ] XHTML fully escaped; page verified by reading it back
- [ ] Page URL shared with user
