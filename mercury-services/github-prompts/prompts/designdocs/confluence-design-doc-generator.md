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

> **Setup prerequisite (one-time, machine-level):** the mcp-context-server must be configured
> and authenticated for Confluence/Jira. If any Confluence/Jira tool returns
> `"... is not configured"` or `401`, follow `.github/prompts/designdocs/SETUP-confluence-mcp.md`
> before continuing. Do **not** fall back to `curl` or hard-coded credentials.

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
DESIGN_DOC_TEMPLATE: ".github/prompts/designdocs/confluence-design-doc-template.md"
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
5. **Escape XHTML** — see Step 4c. This is the #1 cause of publish failures.
6. **Review before publish** — generate the markdown, show the user, publish only after
   confirmation (skip the wait only if the user explicitly says "publish without review").

---

## Session Context Protocol — FOLLOW STRICTLY

Before starting:
1. `session_list` — look for an existing session for these Jira tickets / this doc.
2. If found, `session_get` to load it. If not, `session_create` with:
   - name: `design-doc-<first-jira-ticket>-<yyyy-mm-dd>`
   - project: the repo name (e.g. `mercury-services`)
   - tags: all Jira tickets, `"design-doc"`, `"confluence"`, the module name.

During work, add context entries:
- After reading analysis file → `finding`
- After generating the design doc → `progress`
- After publishing (with page id + URL) → `progress`
- On any blocker → `blocker`
- Log the model used → `model_info`

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
- **Review** — Author = Draft; reviewers = Pending.

---

## Step 3 — Review

Present the generated markdown to the user. Summarize: sections populated vs `N/A`, diagrams
included, Jira references, and any section needing user input. Wait for confirmation before
publishing (unless the user opted out of review).

---

## Step 4 — Publish to Confluence (via MCP write tools)

### 4a. Verify the parent page
`confluence_get_page(CONFLUENCE_PARENT_PAGE_ID)` — confirm it exists and note its space key.

### 4b. Check for an existing page (avoid duplicates)
`confluence_search('title = "<CONFLUENCE_PAGE_TITLE>" AND space = "<CONFLUENCE_SPACE_KEY>"')`.
If a page already exists, ask whether to **update** it (Step 4d, update form) or create a new one.

### 4c. Convert Markdown → Confluence storage format (XHTML)

| Markdown | Storage format |
|----------|----------------|
| `## Title` | `<h2>Title</h2>` |
| table | `<table><thead><tr><th>…</th></tr></thead><tbody><tr><td>…</td></tr></tbody></table>` |
| ` ```lang ` fenced block | `<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">lang</ac:parameter><ac:plain-text-body><![CDATA[…]]></ac:plain-text-body></ac:structured-macro>` |
| Mermaid block | `<ac:structured-macro ac:name="mermaid-cloud"><ac:plain-text-body><![CDATA[…]]></ac:plain-text-body></ac:structured-macro>` — if the Mermaid macro is not installed, render the diagram as ASCII inside a `code` block, or as a table |
| `**bold**` / `*italic*` | `<strong>…</strong>` / `<em>…</em>` |
| `` `inline code` `` | `<code>…</code>` |
| `[text](url)` | `<a href="url">text</a>` |
| Jira key (e.g. `ION-1234`) | `<ac:structured-macro ac:name="jira"><ac:parameter ac:name="key">ION-1234</ac:parameter></ac:structured-macro>` |
| TOC | `<ac:structured-macro ac:name="toc" />` |

> ### ⚠️ CRITICAL — escape XHTML special characters (the #1 failure mode)
> Confluence storage format is **strict XHTML**. Any literal `&`, `<`, or `>` in **text or
> inline-code** content makes Confluence reject the entire page with
> `400 "Error parsing xhtml: Unexpected character …"`.
> - Escape `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;` in all prose, table cells, and inline `code`.
>   Watch for prose like `(<actual class>)` and inline code containing `&`/`<`/`>`/regex.
> - Escape the **raw text first, then** insert your own tags/macros — otherwise you escape your
>   own markup.
> - Content inside `<![CDATA[ … ]]>` (fenced code blocks, Mermaid) is exempt — keep ASCII
>   diagrams inside code/CDATA blocks.
> - A working reference converter is in the repo root: `convert_design_doc.py`
>   (it `html.escape`s first, then transforms). Reuse or adapt it; write the storage output to a
>   file and read it back rather than hand-assembling a 20 KB+ string inline.

### 4d. Create (or update) the page via MCP

**Create a new page:**
```
confluence_create_page(
  space_key      = "<CONFLUENCE_SPACE_KEY>",
  title          = "<CONFLUENCE_PAGE_TITLE>",
  body           = "<CONVERTED_XHTML>",        # param is `body`, NOT `content`
  parent_id      = "<CONFLUENCE_PARENT_PAGE_ID>",
  representation = "storage"
)
```

**Update an existing page** (pass the FULL body; version auto-increments):
```
confluence_update_page(
  page_id        = "<EXISTING_PAGE_ID>",
  body           = "<CONVERTED_XHTML>",
  title          = "<CONFLUENCE_PAGE_TITLE>",   # optional; omit to keep current
  representation = "storage",
  minor_edit     = false                         # false = notify watchers
)
```

**Rules:**
- Send the **entire** body in one `create`/`update` call. Do NOT publish a partial page and then
  `confluence_append_to_page` the rest — append re-sends the combined body and will hit the same
  XHTML `400` if any chunk is unescaped, leaving a half-populated page. Fix escaping and re-send
  the whole document.
- On `400 "Error parsing xhtml"`: the row/col in the message points at the offending character —
  almost always an unescaped `&`/`<`/`>`. Fix the converter and re-send.
- On `401`: the SSO session expired — see `SETUP-confluence-mcp.md` (re-run `sso_login.py`).
- On `"Confluence is not configured"`: the server is missing `MCP_CONFLUENCE_BASE_URL` — see
  `SETUP-confluence-mcp.md`.

---

## Step 5 — Verify & Report

1. `confluence_get_page(<page_id>)` — confirm the body contains every expected section.
2. Share the page URL with the user.
3. Update the session with the final status, page id, version, and URL.

---

## Output checklist

- [ ] Session context with full traceability
- [ ] Design-doc markdown at `<MODULE>/docs/<yyyy-mm-dd>-design-doc-<first-jira-ticket>.md`
- [ ] Confluence page created/updated under the specified parent
- [ ] All template sections populated (content or `N/A`)
- [ ] Diagrams for architecture/flow; Jira keys linked via the jira macro
- [ ] XHTML fully escaped; page verified by reading it back
- [ ] Page URL shared

---

## Reuse Instructions

1. Edit the **PARAMETERS** block above (analysis file, parent page id, space key, title, Jira
   tickets, module).
2. Run this prompt. The agent reads the analysis, generates the markdown, converts it to escaped
   storage format, and publishes via the MCP write tools.
3. If the MCP server is not configured/authenticated, complete the one-time setup in
   `SETUP-confluence-mcp.md` first.
