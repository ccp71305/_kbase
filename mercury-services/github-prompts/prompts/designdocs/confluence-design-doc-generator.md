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

## Invocation — No PARAMETERS editing needed

If invoked via Copilot CLI or Claude Code with a natural language description, extract
parameters from the user's message. You do not need the PARAMETERS block to be pre-filled.

| What to find | Example |
|---|---|
| Jira ticket(s) | `ION-16032` |
| Support ticket(s) — optional | `PDSUPPORT-203319` |
| Module name | `booking` |
| Confluence page title | `"ION-16032 Booking Template Jetty 12 URI Path Separator Fix"` |
| Parent page ID (numeric) | `12345678` |
| Space key — optional, default `BRM` | `BRM` |
| Analysis file — optional, auto-detect from `<module>/docs/` if not given | `booking/docs/2026-06-18-booking-template-jetty-issue.md` |

**Example Copilot invocations:**
```
follow confluence-design-doc-generator — ION-16032, booking, parent: 12345678,
title: "ION-16032 Booking Template Jetty 12 URI Path Separator Fix"

follow confluence-design-doc-generator — ION-16032 PDSUPPORT-203319 booking,
title: "Jetty URI Fix", parent: 12345678,
source: booking/docs/2026-06-18-booking-template-jetty-issue.md
```

**Auto-detecting the analysis file:** if not specified, search `<MODULE>/docs/` for a markdown
file whose name contains the first Jira key or matches today's date. Confirm with user if
multiple candidates are found.

---

## PARAMETERS — Change these for each new document (skip if using natural language invocation)

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

Map content from the analysis file onto each template section. The template mirrors the corporate
template — **do not rename, reorder, or drop official sections**; subsections marked `(ext)` are
mercury-services additions and may be omitted when they would be empty. Guidance:

- **Contributors** — author, reviewer, product owner.
- **Summary** — 2–4 sentences: what was broken or being added, who is affected, what this achieves.
- **Requirements** — fill the metadata table (Epic, Story ID, Target Release, Scope, Fix Version,
  Customer/Client, Related Documents); then Functional Requirements, Non-Functional Requirements,
  and Acceptance Criteria. `(ext)`: Jira table (Step 1d), support-ticket table, technology stack.
- **Assumptions and Open Issues** — assumptions and open questions, with status.
- **High Level Design** — interface changes affecting other groups, design trades needing a group
  decision, how the feature is configured. `(ext)`: architectural overview, options considered,
  before/after data flow. ASCII box diagrams preferred over Mermaid.
- **Low Level Design → Server** — entities, APIs, DB schema, class/sequence diagrams. `(ext)`: key
  components table, Guice load order, AWS services, DynamoDB changes, component interaction flow.
- **Low Level Design → UI** — `N/A` unless there is UI impact.
- **Low Level Design → API Architecture** — fill the official security table (Use Case, API, Body,
  Method, Query Parameter, Access Privilege, Authorization, Authentication, Remarks).
  `(ext)`: endpoints affected, request/response changes, implementation notes.
- **Configuration** — component-level, model-level, stack-level, and PS/SI config. For each,
  name the files/properties **and the primary actor** who changes them. If none, say `None.`
- **Auditing/Logging** — auditing approach plus new log statements / event publishing.
- **Metrics / Installer / Temporary cleanup / Impact on Tools** — `N/A` unless applicable.
- **Impact on Current Application** — fill the migration table (DB schema, property migration,
  other file migration, UI). `(ext)`: runtime behavior, performance, deployment.
- **Resiliency** — failover / retry / error-handling changes and defensive guards.
- **Impact on Other Components** — cross-module, shared-library, other-service impact.
- **Backwards Compatible** — Yes/No plus breaking changes, independent deployability, data
  migration, and whether clients need changes.
- **New/Upgraded Third party Applications/Jars** — every new or version-bumped dependency with
  reason and CVEs addressed. **Mandatory for OWASP / SDK-upgrade docs.** If none, say `None.`
- **Unit Test Plan** — JUnit and manual tests. `(ext)`: new tests, test layer coverage,
  existing test impact.
- **Risks** — key risks as a red `panel`; **Dependencies** — major dependencies as a blue `panel`.
- **Pre-Dev Security** — the official 10 topics with ids `1,2,3,4,5,6,120,124,125,126`
  (never renumber). Answer Y/N honestly and explain each Y in Comments.
- **REQUIRED: Documentation Changes** — answer the four official questions.
- **Blocking Issues** — leave empty or note known blockers.
- **Deployment Verification** `(ext)` — omit entirely if the doc predates deployment.
- **Design Document Review and Approval Matrix** — all 9 official stages with the Ownership
  column; status blank (or `NA` for Browser/UX when not applicable).

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
