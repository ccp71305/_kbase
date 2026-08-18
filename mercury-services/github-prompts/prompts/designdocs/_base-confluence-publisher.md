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
| TOC | `<ac:structured-macro ac:name="toc" />` — in the official template it is wrapped in an `info` macro with `<ac:parameter ac:name="icon">false</ac:parameter>` |
| `> blockquote` callout | `<ac:structured-macro ac:name="note"><ac:rich-text-body>…</ac:rich-text-body></ac:structured-macro>` |
| **Risks** bullet block | `panel` macro — `borderColor`/`titleBGColor` `#D04437`, `bgColor` `#FFD5D2`, `title` `Key Risks` |
| **Dependencies** bullet block | `panel` macro — `borderColor`/`titleBGColor` `#4A6785`, `bgColor` `#DEEBFF`, `title` `Major Dependencies` |
| Pre-Dev Security `#` cell | `<ac:task-list><ac:task><ac:task-id>N</ac:task-id><ac:task-status>incomplete</ac:task-status><ac:task-body><span> </span></ac:task-body></ac:task></ac:task-list>` — **reuse the official ids** `1,2,3,4,5,6,120,124,125,126`, never renumber |
| Section rule | emit `<hr />` after every `<h1>`/`<h2>` to match the official template |
| `- ` bullet line | `<ul><li>…</li></ul>` — the reference converter does **not** do this; handle it explicitly |

> **Template fidelity:** the section list, Pre-Dev Security topics, and Approval Matrix in
> `templates/architecture-template.md` mirror the corporate template
> (https://confluence.dev.e2open.com/display/~akundu/Design+Doc+Template, page id `672934513`).
> Do not rename, reorder, or drop official sections. Subsections marked `(ext)` in the template
> are mercury-services additions and may be omitted when empty.

> ### ⚠️ CRITICAL — escape XHTML special characters (the #1 failure mode)
> Confluence storage format is **strict XHTML**. Any literal `&`, `<`, or `>` in text or
> inline-code content causes a `400 "Error parsing xhtml: Unexpected character …"` rejection.
>
> Rules:
> - Escape `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;` in all prose, table cells, and inline `code`.
>   Watch for prose like `(<actual class>)` and inline code containing regex or generics.
> - **Escape raw text first, then** insert your markup — otherwise you escape your own tags.
> - Content inside `<![CDATA[ … ]]>` (fenced code, Mermaid) is exempt — including `<...>`
>   sequences. **`ac:plain-text-body` REQUIRES CDATA**: entity-escaping the content instead makes
>   Confluence silently rewrite the element to `ac:rich-text-body`, which reflows ASCII diagrams.
>   The only real CDATA hazard is a literal `]]>` in the content, which ends the section early.
> - **Use the reference converter at repo root** — do not hand-assemble storage XHTML:
>   ```bash
>   python convert_design_doc.py <input.md> <output.xhtml>
>   ```
>   It emits every official template macro (info+toc, code/CDATA, panel, note, `ac:task-list`
>   with the Pre-Dev Security ids), strips template-internal `(ext)` markers, and runs a
>   **structural self-check**: XML well-formedness, per-table column-count validation, and a
>   byte-comparison of each CDATA code block against its markdown fence. Non-zero exit = do
>   not publish. Rebuilt 2026-07-29; reproduces the published ION-16110 VAS and rates bodies
>   byte-identically.

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

> ### ⚠️ Verify against `body.storage`, NOT `body_text`
> `confluence_get_page` returns `body_text`, a **lossy** text extraction: it omits `<![CDATA[…]]>`
> content entirely, prints macro *parameter* values as bare text (a `diff` language param looks
> like stray content, panel colours appear as `#D04437`), and can show fragments that read exactly
> like a corrupted code block. **Do not diagnose corruption from `body_text`** — it produced a
> false positive on ION-16110 that led to a good page being replaced with a broken one.
>
> To verify code blocks and diagrams, fetch the real storage format and byte-compare:
> `GET /rest/api/content/<id>?expand=body.storage`, extract each
> `<ac:plain-text-body><![CDATA[…]]>`, and assert equality with the markdown fenced blocks.

1. `confluence_get_page(<page_id>)` — confirm the body contains every expected section.
2. Share the page URL with the user.
3. Update the session with final status, page id, version, and URL (`session_update_status`).
