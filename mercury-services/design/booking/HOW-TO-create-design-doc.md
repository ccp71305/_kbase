# How to Create and Publish a Design Document to Confluence

This guide documents the end-to-end process for generating a Confluence design document from an analysis markdown file, based on the ION-16028 workflow (2026-06-18).

---

## Prerequisites

- Analysis markdown file already exists under `<module>/docs/`
- MCP context server is connected (provides Jira + Confluence tools)
- `convert_design_doc.py` is at the repo root

---

## Step 1 — Find the Reference Page ID

If you want the new doc to match the style of an existing Confluence page, look up its page ID first.

The easiest way is via the MCP context server in Claude:

```
Search Confluence for the reference page title to get its numeric ID.
```

For the BRM space, ION-16032's page ID is **672205089** — use this as the style reference for booking defect fix docs.

---

## Step 2 — Find the Parent Page ID

New design docs nest under **"26.2.2 Design Documents"** (ID: `650546304`) in the BRM space.

Ancestry path:
```
BRM Home (131322209)
  └─ Design Documents (131322288)
       └─ 26.X (536258688)
            └─ 26.3 Design Documents (650546297)
                 └─ 26.2.2 Design Documents (650546304)  ← parent for new docs
```

---

## Step 3 — Invoke the `/design-doc` Skill

Use the inline form with all three key args:

```
/design-doc analysis=<module>/docs/<analysis-file>.md ticket=<ION-XXXXX> reference-page-id=<reference-confluence-page-id>
```

**Example (ION-16028):**
```
/design-doc analysis=booking/docs/2026-06-15-booking-post-prod-excp-analysis.md ticket=ION-16028 reference-page-id=672205089
```

The skill reads `confluence-design-doc-generator.md` and:
1. Fetches the Jira issue for ticket metadata
2. Fetches the reference Confluence page for style matching
3. Generates the design doc markdown

---

## Step 4 — Review and Edit the Generated Markdown

The generated file is written to:
```
<module>/docs/<yyyy-mm-dd>-design-doc-<ticket>.md
```

Open it and review. Common edits:
- Adjust the Review table (add/remove reviewers)
- Trim or expand Blocking Issues
- Remove action items that are already resolved

---

## Step 5 — Convert Markdown to Confluence XHTML

Run the converter script, passing the new file as input via Python directly (the script's `__main__` block has a hardcoded path — bypass it):

```bash
python -c "
import sys, io
sys.path.insert(0, '.')
from convert_design_doc import markdown_to_confluence_storage

with open('<module>/docs/<yyyy-mm-dd>-design-doc-<ticket>.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

confluence_html = markdown_to_confluence_storage(md_content)
final_content = '<ac:structured-macro ac:name=\"toc\" />\n' + confluence_html

with open('confluence_design_doc.html', 'w', encoding='utf-8') as f:
    f.write(final_content)

print(f'Converted {len(md_content)} chars to {len(final_content)} chars')
"
```

Output is written to `confluence_design_doc.html` at the repo root.

> **Note:** The converter handles `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;` escaping, Jira macros, code blocks (CDATA), and table conversion. Em dashes (`—`) and emoji (✅) are passed through as Unicode — the MCP tool call must use XML character references (`&#x2014;`, `&#x2705;`) for these to avoid encoding issues in the Confluence API payload.

---

## Step 6 — Check for an Existing Page (Avoid Duplicates)

Before creating, search Confluence:

```
Search: title = "<Page Title>" AND space = "BRM"
```

If a page already exists, use `confluence_update_page` instead of `confluence_create_page`.

---

## Step 7 — Publish via MCP

Call `confluence_create_page` with the full XHTML body:

```
confluence_create_page(
  space_key      = "BRM",
  title          = "ION-XXXXX <Short Description>",
  body           = <full XHTML from confluence_design_doc.html>,
  parent_id      = "650546304",
  representation = "storage"
)
```

On success, the tool returns the page `id` and `url`.

**Common errors:**
| Error | Cause | Fix |
|-------|-------|-----|
| `400 Error parsing xhtml` | Unescaped `&`, `<`, or `>` in body | Find the offending character (row/col in error message), escape it, re-send the whole body |
| `401` | SSO session expired | Re-run `sso_login.py` (see `SETUP-confluence-mcp.md`) |
| `"Confluence is not configured"` | `MCP_CONFLUENCE_BASE_URL` missing | Check `.mcp.json` and restart the MCP server |

---

## Step 8 — Verify

After creation, confirm the page is live at the returned URL. Spot-check:
- Title and Jira macro render correctly
- TOC macro appears at the top
- Code blocks display (not raw XHTML)
- Tables render cleanly

---

## Quick Reference

| Item | Value |
|------|-------|
| BRM space key | `BRM` |
| Parent page (26.2.2 Design Docs) | `650546304` |
| ION-16032 style reference page | `672205089` |
| Converter script | `convert_design_doc.py` (repo root) |
| Output XHTML file | `confluence_design_doc.html` (repo root) |
| Design doc template | `.github/prompts/designdocs/templates/architecture-template.md` |
| Generator prompt | `.github/prompts/designdocs/confluence-design-doc-generator.md` |
| Publisher prompt | `.github/prompts/designdocs/_base-confluence-publisher.md` |
