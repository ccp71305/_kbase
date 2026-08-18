# Design Doc Prompt Library — Index

Prompts and skills for analyzing issues, generating design documents, and publishing to Confluence BRM space.

## Entry points

### Claude Code skills (no file editing — just run)

| Skill | Invocation | What it does |
|---|---|---|
| `/analyze-issue` | `/analyze-issue ION-16032 booking [PDSUPPORT-203319]` | Analyze issue / root cause / implementation plan |
| `/design-doc` | `/design-doc ION-16032 booking "Page Title" 12345678` | Generate + publish architecture design doc |
| `/publish-doc` | `/publish-doc booking/docs/2026-06-18-doc.md "Page Title" 12345678` | Publish an already-written doc |

Skills live in `.claude/skills/`. Space key defaults to `BRM`.

### Copilot CLI (natural language — no PARAMETERS editing needed)

| Task | Example invocation |
|---|---|
| Analyze issue | `follow issue-analysis-generator — booking, ION-16032, details in booking/docs/notes.md` |
| Generate + publish design doc | `follow confluence-design-doc-generator — ION-16032 booking, title: "...", parent: 12345678` |
| Publish already-written doc | `follow confluence-publish-doc — source: booking/docs/doc.md, title: "...", parent: 12345678` |
| API design doc | `follow confluence-api-design-generator — ...` |
| Feature spec | `follow confluence-feature-spec-generator — ...` |
| Runbook | `follow confluence-runbook-generator — ...` |

All prompt files have a natural language preamble — no PARAMETERS block editing required.

---

## Typical workflow

```
1. /analyze-issue ION-16032 booking
        ↓  produces <module>/docs/<date>-<ticket>.md

2. Implement the fix
   (branch → failing test → fix → all tests pass)

3. /design-doc ION-16032 booking "Page Title" 12345678
        ↓  generates markdown + publishes to Confluence BRM

   — or, if doc is already written —

4. /publish-doc booking/docs/<date>-doc.md "Page Title" 12345678
```

For API design, feature specs, runbooks: skip step 1 and feed your source doc into
the relevant generator's `INPUT_ANALYSIS_FILE`.

---

## Walkthrough — generate + publish a design doc with Claude Code

This is the practical end-to-end recipe (validated 2026-07-22 publishing ION-16098). You can just
ask Claude in natural language — no PARAMETERS editing needed.

### 0. Prerequisites (one-time / when it breaks)

The publish step uses the `mcp-context-server` `confluence_*` tools. Before publishing:

- **MCP configured** — `MCP_CONFLUENCE_BASE_URL` / `_EMAIL` in `.mcp.json` (see `SETUP-confluence-mcp.md` Action 1).
- **SSO valid** — if any tool returns `401`, refresh cookies (`SETUP-confluence-mcp.md` Action 2):
  ```bash
  # Git Bash: forward slashes! ('.\\.venv\\...' collapses to junk in bash)
  cd "/c/Users/<you>/OneDrive - WiseTech Global/aiengg/mcp/mcp-summary-server"
  ./.venv/Scripts/python.exe sso_login.py
  ```
- **Quick check** — ask Claude to call any read tool (e.g. `jira_get_issue ION-xxxxx`). Data back = ready;
  `"not configured"` → Action 1+3; `401` → Action 2.

### 1. What to tell Claude

Give it: the **source file(s)** (analysis / OWASP report / notes), the **Confluence parent** (paste the
page URL — Claude derives the space key + parent page ID from it), and a **title** (or let it propose one).
Example prompt:

> Create a design doc from `<path/to/source.md>` (and `<path/to/second.md>`) and publish it under
> `https://confluence.dev.e2open.com/display/BRM/<Parent+Page>`. Title: "ION-xxxxx <short title>".

Multiple related source files → say so; Claude merges them into one doc (e.g. remediation + verification).

### 2. What Claude does (so you know what to expect)

1. Reads the source(s) + `templates/architecture-template.md`; fetches the Jira ticket(s).
2. Writes the doc markdown to `<repo>/docs/<yyyy-mm-dd>-design-doc-<ticket>.md` and **shows it to you for review**.
   → Edit the markdown directly if you want changes, then tell it to publish.
3. Converts MD → Confluence storage XHTML and calls `confluence_create_page` under your parent.
4. Reads the page back to verify, and gives you the URL.

### 3. Known converter gotchas (Claude handles these; good to know)

`convert_design_doc.py` (repo root) is the reference converter — **rebuilt 2026-07-29**, and the sharp
edges below are now fixed *in it*:

```bash
python convert_design_doc.py <input.md> <output.xhtml>
```

A **non-zero exit means the self-check failed — do not publish.** The self-check covers XML
well-formedness, per-table column counts, byte-equality of every CDATA block against its markdown
fence, `(ext)` leakage, and CVE-as-Jira-macro. It reproduces the published ION-16110 VAS and rates
bodies byte-identically.

Also fixed in the rebuild: **pipes inside inline-code spans** no longer corrupt table rows (a cell
holding `` `size|className:...` `` used to spill an extra column — this really happened on the rates
doc); bullet and ordered lists are converted; `(ext)` markers are stripped; and the official
panel / note / info+toc / `ac:task-list` macros are emitted.

The remaining notes explain *why* the converter behaves as it does:

- **CVE ids used to get mangled** — the old Jira-key regex `[A-Z]+-\d+` also matched `CVE-2026-xxxx`.
  Now only `ION-\d+` matches, and never inside inline code, links or URLs. No scratchpad copy needed.
- **`<...>` inside code blocks is FINE** — corrected 2026-07-29. ASCII diagrams containing `<env>` or
  `DefaultPartitionKey<String>>` round-trip byte-identically inside `<![CDATA[…]]>`. The earlier claim that
  this "breaks the code macro and leaks `]]>`" was a **misreading of `body_text`** (see next point).
  The only real CDATA hazard is a literal `]]>` in the content.
- **`ac:plain-text-body` requires CDATA** — entity-escaping the content instead makes Confluence silently
  rewrite it to `ac:rich-text-body`, reflowing the diagram. This is a real corruption; CDATA is not optional.
- **Never diagnose corruption from `body_text`** — it is a lossy extraction that omits CDATA content and
  prints macro parameter values as bare text, so a healthy page can look mangled. Verify with
  `?expand=body.storage` and byte-compare the CDATA blocks against the markdown.
- **Bullet lists** — `- ` lines used to render as literal "- " paragraphs; now converted to `<ul>`/`<ol>`
  (including wrapped continuation lines). Only relevant if you hand-roll a converter instead of using this one.
- **Always read the page back** after publishing — but read `body.storage`, not `body_text`.

See `reference_confluence_mcp_publish` in Claude's memory for the full list.

---

## Prompt files (canonical source of truth — skills and Copilot both read these)

| File | Purpose |
|---|---|
| `../analysis/issue-analysis-generator.md` | Analyze defect / module / produce impl plan |
| `confluence-design-doc-generator.md` | Generate + publish architecture/defect-fix design doc |
| `confluence-publish-doc.md` | Publish an already-written doc (Steps 4–5 only) |
| `confluence-api-design-generator.md` | Generate + publish API design doc |
| `confluence-feature-spec-generator.md` | Generate + publish feature spec |
| `confluence-runbook-generator.md` | Generate + publish runbook |
| `SETUP-confluence-mcp.md` | One-time MCP / SSO setup |

---

## Shared base files (update once — all prompts and skills inherit)

| File | Used by |
|---|---|
| `_base-confluence-publisher.md` | All generators (XHTML conversion, create/update, error handling, verify) |
| `../_base-session-protocol.md` | All prompts and skills (session create/resume, context logging, completion) |
| `convert_design_doc.py` (repo root) | XHTML converter called by `_base-confluence-publisher.md` |

---

## Templates (section schemas for generators)

| Template | Doc type |
|---|---|
| `templates/architecture-template.md` | Architecture / defect-fix design docs — **mirrors the corporate template** ([~akundu/Design Doc Template](https://confluence.dev.e2open.com/display/~akundu/Design+Doc+Template), page id `672934513`, synced 2026-07-29) |
| `templates/api-design-template.md` | API design docs |
| `templates/feature-spec-template.md` | Feature specs |
| `templates/runbook-template.md` | Runbooks |

**Template contract:** `architecture-template.md` is kept in sync with the corporate Confluence
template. Official section names, order, the Pre-Dev Security topic ids (`1,2,3,4,5,6,120,124,125,126`)
and the 9-stage Approval Matrix must not be renamed, reordered, or dropped. Subsections marked
`(ext)` are mercury-services engineering additions — keep them when they carry real content, omit
them when empty. To re-sync, fetch page `672934513` and diff.

---

## Completed instances

| Folder | Contents |
|---|---|
| `completed/` | Past design doc runs — produced artifacts, published to Confluence |
| `../analysis/completed/` | Past analysis/fix prompt runs |

---

## Prerequisites

- MCP server configured: `MCP_CONFLUENCE_BASE_URL`, `MCP_CONFLUENCE_EMAIL` in `.mcp.json`
- SSO session valid: re-run `sso_login.py` when tools return `401` → see `SETUP-confluence-mcp.md`
- `convert_design_doc.py` present at repo root
