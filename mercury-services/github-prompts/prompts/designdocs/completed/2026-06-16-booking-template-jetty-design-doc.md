---
name: 2026-06-16-booking-template-jetty-issue-designdoc
description: >
  Generate a Confluence design document from an analysis/implementation markdown file.
  This prompt reads the source analysis, applies the standard design doc template,
  and publishes to Confluence under the specified parent page.
  Reusable — change INPUT_ANALYSIS_FILE, JIRA_TICKETS, and CONFLUENCE_PARENT_PAGE_ID to generate other design docs.
argument-hint: "none"
agent: agent
model: Claude Opus 4.6 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# Design Document Generator — Confluence Publisher

## PARAMETERS — Change these to reuse for other design documents

```yaml
# ─── INPUT ────────────────────────────────────────────────────────────
INPUT_ANALYSIS_FILE: booking/docs/2026-06-16-booking-template-jetty-issue.md
MODULE: booking
JIRA_TICKETS:
  - ION-16032
  - PDSUPPORT-203319

# ─── CONFLUENCE TARGET ────────────────────────────────────────────────
# Parent page under which the design doc will be created
# Default: Arijit Kundu's Home (MySpace) for review drafts
CONFLUENCE_PARENT_PAGE_ID: "197692761"
CONFLUENCE_SPACE_KEY: "~akundu"
CONFLUENCE_PAGE_TITLE: "ION-16032 Booking Template Jetty 12 URI Path Separator Fix"

# ─── TEMPLATE ─────────────────────────────────────────────────────────
DESIGN_DOC_TEMPLATE: .github/prompts/designdocs/confluence-design-doc-template.md

# ─── REFERENCE CONFLUENCE PAGE (for structure/style) ──────────────────
REFERENCE_PAGE_ID: "634525215"
# ION-12316 Visibility AWS SDK upgrade — use as style reference
```

---

## CRITICAL CONSTRAINTS

1. **READ the analysis file first** — All content comes from the `INPUT_ANALYSIS_FILE`. Do not invent information not in the source.
2. **Follow the template** — Use all sections from `DESIGN_DOC_TEMPLATE`. Sections with no applicable content get "N/A".
3. **Lucid and crisp** — Write clear, scannable prose. Use tables and Mermaid diagrams over walls of text.
4. **Confluence via MCP write tools** — The MCP context server now has full write capability. Use `confluence_create_page` / `confluence_update_page` (NOT `curl`). See Step 4 for the exact tool parameters and the XHTML-escaping rule that must be followed.
5. **Review first** — Generate the markdown version, show the user, then publish to Confluence only after confirmation.

---

## Session Context Protocol — FOLLOW THIS STRICTLY

Before starting ANY work:
1. Call `session_list` to check for existing sessions related to the design doc or Jira tickets.
2. If a relevant session exists, call `session_get` to load its context.
3. If no session exists, call `session_create` with:
   - name: `design-doc-<first-jira-ticket>-<date>`
   - project: `mercury-services`
   - tags: include all Jira tickets, `"design-doc"`, `"confluence"`, module name

**DURING** work:
- After reading analysis file → category: `finding`
- After reading reference Confluence page → category: `finding`
- After generating design doc → category: `progress`
- After publishing to Confluence → category: `progress`
- Log your model info with category: `model_info`

---

## Step 1: Gather Context

### 1a. Read the Analysis/Implementation Document

Read the file specified in `INPUT_ANALYSIS_FILE`. This is the source of truth for all design doc content.

Extract:
- Problem description and root cause
- Fix approach and decision rationale
- Code changes (components, files, methods)
- Test strategy and test results
- Impact assessment
- Security considerations

### 1b. Read the Design Doc Template

Read `DESIGN_DOC_TEMPLATE` for the section structure and table formats to follow.

### 1c. Read the Reference Confluence Page (Optional — for style)

Use MCP to read the reference page:
```
confluence_get_page: <REFERENCE_PAGE_ID>
```
Note the writing style, section depth, and diagram usage. Match the tone.

### 1d. Get Jira Ticket Details

For each ticket in `JIRA_TICKETS`, fetch details:
```
jira_get_issue: <ticket_key>
```
Extract: summary, type, priority, status, assignee, reporter.

---

## Step 2: Generate the Design Document

### Output file
Generate the design document as a markdown file at:
```
<MODULE>/docs/<yyyy-mm-dd>-design-doc-<first-jira-ticket>.md
```
For this instance: `booking/docs/2026-06-16-design-doc-ION-16032.md`

### Section-by-Section Guide

Map content from the analysis file to each template section. Use these rules:

#### Contents
Auto-generated TOC (markdown headings).

#### Requirements
- Fill the Jira table with ticket details fetched in Step 1d
- Fill support ticket table if applicable (PDSUPPORT tickets)
- Write a high-level summary (2-4 sentences): what was broken, who was affected, what the fix achieves
- Include technology stack table if the change involves specific technologies

#### Assumptions and Open Issues
- List any assumptions made during analysis/fix
- List any open issues or future considerations noted in the analysis

#### High Level Design
- Architectural overview of the affected module/component area
- Use Mermaid diagrams showing the request flow and where the fix applies
- Show the "before" and "after" behavior at a high level

#### Low Level Design
- **Key Components and Changes**: Create a table with component name, file path, purpose, and key changes
- **Guice Module Loading Order**: Include if the fix involves module initialization order
- **AWS Services Used**: Include if the change touches AWS services
- **DynamoDB Changes**: Include if DynamoDB tables/annotations change
- **Component Interaction Flow**: Mermaid sequence diagram showing the fix's interaction

#### UI
N/A unless the change has UI impact.

#### API Architecture
- List affected endpoints with method, path, description, and what changed
- Note any request/response contract changes

#### Configuration
- **Model Level**: Application-level config changes (YAML, properties)
- **Stack Level**: Server/container-level config (Jetty, JVM, etc.)
- **Professional Services/SI Config**: Customer-facing config changes

#### Auditing/Logging
- New log statements added
- Event publishing changes
- Lifecycle stage changes

#### Metrics and Statistics
N/A unless new metrics were added.

#### Installer Changes
N/A unless deployment artifacts changed.

#### Impact on Current Application
- Runtime behavior changes
- Performance implications
- Deployment considerations (rolling restart needed? config change?)

#### Resiliency
- Failover behavior
- Error handling changes

#### Temporary object cleanup
N/A unless temp files/objects are involved.

#### Impact on Tools
N/A unless dev/ops tooling is affected.

#### Impact on Other Components
- Cross-module impact
- Shared library impact
- Other services affected

#### Backwards Compatible
- Is this a breaking change? 
- Can it be deployed without coordinating with other services?
- Does it require data migration?

#### Unit Test Plan
- Table of all new test classes and methods with coverage description
- Note any modified existing tests

#### Pre-Dev Security
- Fill the security checklist table honestly based on the change
- Pay special attention to input validation, path traversal, injection risks

#### Required Documentation Changes
- User docs, API docs, operations docs — answer each question

#### Blocking Issues and Actions from the Design Review
- Leave empty or note any known blockers

#### Review
- Fill with Author as Draft status, reviewers as Pending

---

## Step 3: Review the Generated Document

Present the generated markdown to the user for review. Wait for confirmation before publishing to Confluence.

Show a summary:
- Total sections populated vs N/A
- Key diagrams included
- Jira ticket references
- Any sections that need user input

---

## Step 4: Publish to Confluence

### 4a. Verify Parent Page Exists

Use MCP to verify the parent page:
```
confluence_get_page: <CONFLUENCE_PARENT_PAGE_ID>
```
Confirm it exists and note the space key.

### 4b. Check for Existing Page

Search for an existing page with the same title to avoid duplicates:
```
confluence_search: title = "<CONFLUENCE_PAGE_TITLE>" AND space = "<CONFLUENCE_SPACE_KEY>"
```

If a page already exists, inform the user and ask whether to update or create a new one.

### 4c. Convert Markdown to Confluence Storage Format

Convert the markdown design doc to Confluence storage format (XHTML). Key conversions:

- **Headings**: `## Title` → `<h2>Title</h2>`
- **Tables**: Markdown tables → `<table><tr><th>...</th></tr><tr><td>...</td></tr></table>`
- **Code blocks**: ````java` → `<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">java</ac:parameter><ac:plain-text-body><![CDATA[...]]></ac:plain-text-body></ac:structured-macro>`
- **Mermaid diagrams**: Convert to ASCII art or use the Mermaid macro if available: `<ac:structured-macro ac:name="mermaid-cloud"><ac:plain-text-body><![CDATA[...]]></ac:plain-text-body></ac:structured-macro>`
  - If Mermaid macro is not available, convert diagrams to ASCII art or describe the flow in a table
- **Bold/Italic**: `**bold**` → `<strong>bold</strong>`, `*italic*` → `<em>italic</em>`
- **Links**: `[text](url)` → `<a href="url">text</a>`
- **Jira links**: Use `<ac:structured-macro ac:name="jira"><ac:parameter ac:name="key">ION-16032</ac:parameter></ac:structured-macro>`
- **TOC**: Use `<ac:structured-macro ac:name="toc" />`
- **Info/Note panels**: Use `<ac:structured-macro ac:name="info"><ac:rich-text-body>...</ac:rich-text-body></ac:structured-macro>`

> **CRITICAL — escape XHTML special characters in text content.** Confluence's storage-format parser is strict XHTML and will reject the whole page with a `400 "Error parsing xhtml: Unexpected character ..."` if any literal `&`, `<`, or `>` appears in **text or inline-code** content. This is the single most common publish failure.
> - Escape `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;` in all prose, table cells, and inline `code` spans. (Watch for prose like `(<actual class>)` and inline code containing `&`, `<`, `>`.)
> - Do this BEFORE inserting your own tags/macros, so you don't escape the markup you generate.
> - Content inside `<![CDATA[ ... ]]>` (fenced code blocks, Mermaid macros) does NOT need escaping — CDATA is literal. Keep ASCII diagrams inside code/CDATA blocks.
> - A working reference converter lives at `convert_design_doc.py` (escapes via `html.escape` first, then transforms). Reuse/adapt it.

### 4d. Create or Update the Page via MCP Write Tools

The MCP context server has full Confluence write capability. **Use the MCP tools — do NOT use `curl`.** Authentication is handled by the server (SSO cookies stored via its `sso_login.py`, or `MCP_CONFLUENCE_*` basic-auth env vars); you never pass or prompt for credentials.

**Prerequisite:** the server must be *configured* — i.e. `MCP_CONFLUENCE_BASE_URL` must be set in its environment. In Claude Code, the server is launched from `.mcp.json`; that `env` block must include `MCP_CONFLUENCE_BASE_URL` (and `MCP_JIRA_BASE_URL`) because Claude Code does not honor the server's `cwd`, so its `.env` is not auto-loaded. If a Confluence tool returns `"Confluence is not configured"`, add those vars to `.mcp.json` and reconnect the MCP server.

**To create a new page:**
```
confluence_create_page(
  space_key   = "<CONFLUENCE_SPACE_KEY>",     # e.g. "~akundu"
  title       = "<CONFLUENCE_PAGE_TITLE>",
  body        = "<CONVERTED_XHTML_CONTENT>",   # storage format; param name is `body`, NOT `content`
  parent_id   = "<CONFLUENCE_PARENT_PAGE_ID>", # optional
  representation = "storage"                    # default
)
```

**To update an existing page** (e.g. if `confluence_search` in Step 4b found a same-title page — pass the full body, the tool auto-increments the version):
```
confluence_update_page(
  page_id        = "<EXISTING_PAGE_ID>",
  body           = "<CONVERTED_XHTML_CONTENT>",
  title          = "<CONFLUENCE_PAGE_TITLE>",  # optional; omit to keep current
  representation = "storage",
  minor_edit     = false                        # false = notify watchers
)
```

**IMPORTANT:**
- Pass the **entire** converted body in a single `create`/`update` call. Do NOT publish a partial page and then try to `confluence_append_to_page` the rest — `append` re-sends the combined body and will hit the same XHTML `400` if any chunk is unescaped, leaving a half-populated page. Fix the escaping (Step 4c) and send the whole document at once.
- If a write returns `400 "Error parsing xhtml"`, the row/col in the message points at the offending character in the body — almost always an unescaped `&`/`<`/`>`. Fix it in the converter and re-send.
- If a write returns `401`, the SSO session expired — ask the user to re-run the server's `sso_login.py`. Do NOT fall back to hardcoding credentials.
- Verify the page after writing (Step 5).

---

## Step 5: Final Verification

1. Use MCP to read the created page and verify content:
   ```
   confluence_get_page: <new_page_id>
   ```

2. Verify all sections are present and properly formatted

3. Share the page URL with the user

4. Update session context with the final status and page link

---

## Output Summary

At the end of this task, you should have:
- [ ] Session context with full traceability
- [ ] Design document markdown at `<MODULE>/docs/design-doc-<JIRA_TICKET>.md`
- [ ] Confluence page created under the specified parent page
- [ ] All template sections populated (content or N/A)
- [ ] Mermaid diagrams or ASCII art for architectural/flow diagrams
- [ ] Jira ticket references linked
- [ ] Security checklist completed
- [ ] Review table initialized

---

## Reuse Instructions

To generate a design doc for a different change:

1. **Copy this prompt** to a new file under `.github/prompts/designdocs/`
2. **Update the PARAMETERS section** at the top:
   - `INPUT_ANALYSIS_FILE`: path to the analysis/implementation markdown
   - `MODULE`: the service module name
   - `JIRA_TICKETS`: relevant Jira ticket keys
   - `CONFLUENCE_PARENT_PAGE_ID`: target parent page ID
   - `CONFLUENCE_SPACE_KEY`: target space key
   - `CONFLUENCE_PAGE_TITLE`: title for the new page
3. **Run the prompt** — the agent will read the analysis, generate the design doc, and publish to Confluence
