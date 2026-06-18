---
name: confluence-publish-doc
description: >
  Publish an already-written design document markdown file to Confluence.
  Use when the document is written and just needs XHTML conversion and publishing.
  For generating a new doc from an analysis file, use confluence-design-doc-generator instead.
argument-hint: "source doc path, page title, parent page ID [space key — default BRM]"
agent: agent
model: Claude Opus 4.6 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# Confluence Publish Doc (Reusable)

Publish an already-written markdown document to Confluence via the MCP write tools.

> **Session protocol:** see `.github/prompts/_base-session-protocol.md`
> **Publish steps:** see `.github/prompts/designdocs/_base-confluence-publisher.md` (Steps 4–5)
> **Setup prerequisite (one-time):** see `SETUP-confluence-mcp.md` for `401` / not-configured errors.

---

## Invocation — No PARAMETERS editing needed

If invoked via Copilot CLI or Claude Code with a natural language description, extract:

| What to find | Example |
|---|---|
| Path to the source markdown file | `booking/docs/2026-06-18-design-doc-ION-16032.md` |
| Confluence page title | `"ION-16032 Booking Template Jetty 12 URI Path Separator Fix"` |
| Parent page ID (numeric) | `12345678` |
| Space key (optional, default `BRM`) | `BRM` |
| Existing page ID if updating (optional) | `98765432` |

**Example Copilot invocations:**
```
follow confluence-publish-doc — source: booking/docs/2026-06-18-design-doc-ION-16032.md,
title: "ION-16032 Booking Template Fix", parent: 12345678

follow confluence-publish-doc — update page 98765432 with booking/docs/2026-06-18-design-doc-ION-16032.md
```

---

## PARAMETERS — Fill these when not using natural language invocation

```yaml
SOURCE_DOC: "<module>/docs/<yyyy-mm-dd>-<doc-name>.md"
CONFLUENCE_PAGE_TITLE: "<Page Title>"
CONFLUENCE_PARENT_PAGE_ID: "<parent-page-id>"
CONFLUENCE_SPACE_KEY: "BRM"
UPDATE_PAGE_ID: ""          # if set, update this page instead of creating new
```

---

## Session Context

> Follow `.github/prompts/_base-session-protocol.md`.
> Session name pattern: `publish-doc-<yyyy-mm-dd>-<title-slug>`

---

## Steps

1. Read `SOURCE_DOC` in full.
2. Follow `_base-confluence-publisher.md` Steps 4–5:
   - 4a: verify parent page
   - 4b: check for existing page (skip if `UPDATE_PAGE_ID` is set)
   - 4c: convert markdown → Confluence storage XHTML via `convert_design_doc.py`
   - 4d: create or update via MCP
   - 5: verify, share URL, update session

---

## Output Checklist

- [ ] Session context updated
- [ ] XHTML fully escaped; page verified by reading it back
- [ ] Page URL shared with user
