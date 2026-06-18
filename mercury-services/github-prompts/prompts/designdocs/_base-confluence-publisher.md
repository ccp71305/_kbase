---
name: _base-confluence-publisher
description: >
  Shared Confluence publish steps (Steps 4-5) used by all design doc generator prompts.
  Covers XHTML conversion, create/update call signatures, error handling, and verification.
  Reference this file — do not duplicate these steps inline in generator prompts.
---

# Base Confluence Publisher — Steps 4 & 5

## Step 4 — Publish to Confluence (via MCP write tools)

### 4a. Verify the parent page

`confluence_get_page(CONFLUENCE_PARENT_PAGE_ID)` — confirm it exists and note its space key.

### 4b. Check for an existing page (avoid duplicates)

`confluence_search('title = "<CONFLUENCE_PAGE_TITLE>" AND space = "<CONFLUENCE_SPACE_KEY>"')`

If a page already exists, ask whether to **update** it (Step 4d) or create a new one.

### 4c. Convert Markdown → Confluence storage format (XHTML)

| Markdown | Storage format |
|----------|----------------|
| `## Title` | `<h2>Title</h2>` |
| table | `<table><thead><tr><th>…</th></tr></thead><tbody><tr><td>…</td></tr></tbody></table>` |
| ` ```lang ` fenced block | `<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">lang</ac:parameter><ac:plain-text-body><![CDATA[…]]></ac:plain-text-body></ac:structured-macro>` |
| Mermaid block | `<ac:structured-macro ac:name="mermaid-cloud"><ac:plain-text-body><![CDATA[…]]></ac:plain-text-body></ac:structured-macro>` — if Mermaid macro not installed, use ASCII inside a `code` block |
| `**bold**` / `*italic*` | `<strong>…</strong>` / `<em>…</em>` |
| `` `inline code` `` | `<code>…</code>` |
| `[text](url)` | `<a href="url">text</a>` |
| Jira key (e.g. `ION-1234`) | `<ac:structured-macro ac:name="jira"><ac:parameter ac:name="key">ION-1234</ac:parameter></ac:structured-macro>` |
| TOC | `<ac:structured-macro ac:name="toc" />` |

> ### ⚠️ CRITICAL — escape XHTML special characters (the #1 failure mode)
> Confluence storage format is **strict XHTML**. Any literal `&`, `<`, or `>` in text or
> inline-code content causes a `400 "Error parsing xhtml: Unexpected character …"` rejection.
>
> Rules:
> - Escape `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;` in all prose, table cells, and inline `code`.
>   Watch for prose like `(<actual class>)` and inline code containing regex or generics.
> - **Escape raw text first, then** insert your markup — otherwise you escape your own tags.
> - Content inside `<![CDATA[ … ]]>` (fenced code, Mermaid) is exempt.
> - The reference converter is at repo root: `convert_design_doc.py`
>   (`html.escape` first, then transforms). Write storage output to a file and read it back
>   rather than hand-assembling large strings inline.

### 4d. Create (or update) the page via MCP

**Create a new page:**
```
confluence_create_page(
  space_key      = "<CONFLUENCE_SPACE_KEY>",
  title          = "<CONFLUENCE_PAGE_TITLE>",
  body           = "<CONVERTED_XHTML>",
  parent_id      = "<CONFLUENCE_PARENT_PAGE_ID>",
  representation = "storage"
)
```

**Update an existing page** (pass the FULL body; version auto-increments):
```
confluence_update_page(
  page_id        = "<EXISTING_PAGE_ID>",
  body           = "<CONVERTED_XHTML>",
  title          = "<CONFLUENCE_PAGE_TITLE>",
  representation = "storage",
  minor_edit     = false
)
```

**Rules:**
- Send the **entire** body in one call. Do NOT publish partial and then `confluence_append_to_page`
  the rest — append re-sends the combined body and hits the same `400` if any chunk is unescaped.
- On `400 "Error parsing xhtml"`: the row/col in the message points at the offending character —
  almost always an unescaped `&`/`<`/`>`. Fix the converter and re-send the whole document.
- On `401`: SSO session expired — re-run `sso_login.py` (see `SETUP-confluence-mcp.md`).
- On `"Confluence is not configured"`: `MCP_CONFLUENCE_BASE_URL` is missing — see `SETUP-confluence-mcp.md`.

---

## Step 5 — Verify & Report

1. `confluence_get_page(<page_id>)` — confirm the body contains every expected section.
2. Share the page URL with the user.
3. Update the session with final status, page id, version, and URL (`session_update_status`).
