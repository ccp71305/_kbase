---
name: publish-doc
description: >
  Publish an already-written design document markdown file to Confluence BRM space.
  Use this skill when the document is already written and just needs XHTML conversion and
  publishing — skipping the generate step. Triggers on: /publish-doc, "publish this doc",
  "push to Confluence", "upload to Confluence", "publish the doc I already wrote".
  Use design-doc instead if the document still needs to be generated from an analysis file.
---

# publish-doc

Publish an already-written markdown document to Confluence via the MCP write tools.

## Parse the invocation

Extract from the user's message:

| Field | How to find it | Required | Default |
|---|---|---|---|
| `SOURCE_DOC` | File path to the markdown doc | yes | — |
| `CONFLUENCE_PAGE_TITLE` | Quoted string or explicit title | yes | — |
| `CONFLUENCE_PARENT_PAGE_ID` | Numeric page ID | yes | — |
| `CONFLUENCE_SPACE_KEY` | Space key if specified | no | `BRM` |
| `UPDATE_PAGE_ID` | Existing Confluence page ID if updating | no | — |

## Execute the workflow

1. Read `SOURCE_DOC` in full.
2. Follow `.github/prompts/designdocs/_base-confluence-publisher.md` Steps 4–5 exactly:
   - Step 4a: verify parent page exists
   - Step 4b: check for existing page with the same title (avoid duplicates)
   - Step 4c: convert markdown → Confluence storage XHTML (use `convert_design_doc.py`)
   - Step 4d: create or update the page via MCP tools
   - Step 5: verify, share URL, update session context
3. Follow `.github/prompts/_base-session-protocol.md` for session tracking.
   Session name pattern: `publish-doc-<yyyy-mm-dd>-<page-title-slug>`
