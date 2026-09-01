---
name: publish-confluence-design
description: >
  Generalized, self-contained runbook for publishing an already-written design-document
  markdown file to Confluence as a child of a given landing page, using the
  mcp-context-server confluence_* tools. Covers SSO refresh, MD -> storage-format
  conversion, publish, and byte-level verification.
argument-hint: "<path to design doc .md> <Confluence landing page URL>"
---

# Publish a Confluence Design Doc — Generalized Runbook

Any VS Code agent (Claude Code / Copilot CLI) can execute this end-to-end with only the two
inputs below. Validated 2026-08-26 publishing
`ION-16416 aw-bridge (ib / ob / shared) — AWS SDK 2.x (cloud-sdk) + Dropwizard 5 Upgrade`
(page `672876384`, 52,701-char body, storage byte-identical, 3/3 CDATA blocks byte-equal).

---

## INPUTS (the only two things the caller supplies)

```yaml
SOURCE_DOC:   "<absolute path to the design-document markdown file>"
LANDING_PAGE: "<Confluence landing/parent page URL>"
```

Everything else is **derived**:

| Derived value | How |
|---|---|
| `CONFLUENCE_SPACE_KEY` | from the landing-page URL — `/display/<SPACE>/<Page+Title>` → `<SPACE>` (usually `BRM`) |
| `PARENT_PAGE_TITLE` | from the landing-page URL path segment, `+` → space (e.g. `26.3.1+Design+Documents` → `26.3.1 Design Documents`) |
| `CONFLUENCE_PARENT_PAGE_ID` | resolved in Step 2 via `confluence_search` (do **not** hand-guess it) |
| `CONFLUENCE_PAGE_TITLE` | the `# ` H1 on line 1 of `SOURCE_DOC`, verbatim (em dashes and parentheses included). The converter strips this H1 from the body, so the page title must carry it |

Example invocation:

> Publish `C:\...\aw-bridge-shared\docs\2026-aw-bridge-ib-ob-confluence-design.md` to
> `https://confluence.dev.e2open.com/display/BRM/26.3.1+Design+Documents` following
> `.github/prompts/designdocs/2026-08-26-publish-confluence-design.md`.

---

## Fixed paths (this machine)

| What | Path |
|---|---|
| MCP server repo + venv | `C:\Users\arijit.kundu\OneDrive - WiseTech Global\aiengg\mcp\mcp-summary-server` |
| venv python | `<server repo>\.venv\Scripts\python.exe` — selenium/httpx live **here**, not in `~/.venvs` |
| SSO cookie jar | `C:\Users\arijit.kundu\.mcp-context-server\browser_cookies.json` (machine-wide, cwd-independent) |
| Reference converter | `C:\Users\arijit.kundu\projects\mercury-services\convert_design_doc.py` |
| MCP wiring | `C:\Users\arijit.kundu\projects\mercury-services\.mcp.json` (untracked; `env` block holds `MCP_CONFLUENCE_BASE_URL` / `_EMAIL`) |
| Scratch output | the session scratchpad dir — **never** rely on `$TMPDIR` in Git Bash (it is unset and the path collapses to `C:/Program Files/Git/...` → `PermissionError`) |

---

## Step 0 — Read the instruction set and the source

1. Read `SOURCE_DOC` **in full** (do not skim — you need the H1 title, the section list, and any
   fenced code blocks / ASCII diagrams).
2. Read the shared publish contract: `.github/prompts/designdocs/_base-confluence-publisher.md`
   (Steps 4–5) and, for template fidelity, `templates/architecture-template.md`.
3. Sanity-check the doc against the corporate template: official section names, order, the
   Pre-Dev Security topic ids (`1,2,3,4,5,6,120,124,125,126`) and the 9-stage Approval Matrix must
   not be renamed, reordered, or dropped. `(ext)` markers are internal — the converter strips them.

---

## Step 1 — Prove MCP Confluence access (and refresh SSO if needed)

The `mcp-context-server` `confluence_*` tools authenticate with **browser SSO cookies**, not a
password. `.mcp.json` only supplies the base URL + email so the server reports `configured = true`.

**Probe first** — call any read tool, e.g.

```
confluence_search(cql = 'title = "<PARENT_PAGE_TITLE>" AND space = "<SPACE>"')
```

Then branch on the result:

| Symptom | Cause | Fix |
|---|---|---|
| Data returned | ready | continue to Step 2 |
| `"Confluence is not configured"` | `MCP_CONFLUENCE_BASE_URL` missing from `.mcp.json` `env` | `SETUP-confluence-mcp.md` **Action 1**, then `/mcp` reconnect (**Action 3**) |
| `401 Unauthorized` | SSO session dead | **Action 2 below** |

### Action 2 — Refresh the SSO session (verbatim from `SETUP-confluence-mcp.md`)

```powershell
cd "C:\Users\arijit.kundu\OneDrive - WiseTech Global\aiengg\mcp\mcp-summary-server"
.\.venv\Scripts\python.exe sso_login.py
```

Git Bash equivalent — **forward slashes**, because `.\.venv\Scripts\...` collapses to junk in bash:

```bash
cd "/c/Users/arijit.kundu/OneDrive - WiseTech Global/aiengg/mcp/mcp-summary-server"
./.venv/Scripts/python.exe sso_login.py
```

Notes for the agent:

- `sso_login.py` opens an Edge window and **polls `driver.current_url`** (180 s for Jira, 30 s for
  Confluence). It does **not** read stdin, so launch it with `run_in_background` and ask the user
  to complete passkey / Windows Hello in that window. It self-verifies at the end
  (`Jira: OK — logged in as …` / `Confluence: OK`).
- Afterwards call `auth_reload` so the **running** server re-reads the cookie file. A new chat
  session is not needed.
- `auth_reload` alone can never fix a 401 — it only re-reads the file and is a no-op if the mtime
  hasn't changed. Confluence's `JSESSIONID` is a **server-side** session invalidated independently
  of the cookie's nominal expiry, so the jar can look healthy while every call 401s. Conclusive
  probe: hit `/rest/api/space/<SPACE>` with the cookies off disk and check the response header —
  `X-AUSERNAME: None` means the session is dead. Fix is always `sso_login.py`.

If the user says "SSO credentials are refreshed and saved", still run the probe — it costs one
call and distinguishes a live session from a stale one before you build a 50 KB body.

---

## Step 2 — Resolve the parent page id and check for duplicates

```
confluence_search(cql = 'title = "<PARENT_PAGE_TITLE>" AND space = "<SPACE>"')
    -> CONFLUENCE_PARENT_PAGE_ID
confluence_search(cql = 'space = "<SPACE>" AND title ~ "<TICKET-KEY>"')
    -> existing page? (also try the full CONFLUENCE_PAGE_TITLE)
```

- No hit → **create** (Step 4a).
- Hit → **ask the user** whether to update that page id or create a new one. Never create a
  second page with a near-identical title.
- Optionally `confluence_page_children(<parent id>)` to see the sibling docs and match their
  title convention.

---

## Step 3 — Convert Markdown → Confluence storage format (XHTML)

**Always use the reference converter. Never hand-assemble storage XHTML, and never hand-escape.**

```bash
cd /c/Users/arijit.kundu/projects/mercury-services
SP="<session scratchpad dir>"; mkdir -p "$SP"
python convert_design_doc.py "<SOURCE_DOC>" "$SP/doc.xhtml"
```

Expected output shape:

```
<in> -> <out>
  36403 chars in, 52701 chars out
  h1=24 h2=28 tables=16 code=3 panel=2 note=2 task-list=10 jira=6
  self-check: OK
```

**A non-zero exit means the self-check failed — DO NOT PUBLISH.** The self-check covers XML
well-formedness, per-table column counts, byte-equality of every CDATA block against its markdown
fence, `(ext)` leakage, and CVE-as-Jira-macro.

What the converter guarantees (so you don't re-derive it):

- `##` → `<h1>` + `<hr />` (matches the corporate template); the doc's own `#` H1 is dropped —
  it becomes the **page title**.
- Escapes `&` `<` `>` in prose, table cells and inline `<code>` **before** inserting markup. Any
  literal `&`/`<`/`>` reaching Confluence unescaped → `400 "Error parsing xhtml: Unexpected
  character …"` and the whole page is rejected. This is the #1 failure mode.
- Fenced code / Mermaid → `ac:structured-macro` with `<![CDATA[…]]>`. **CDATA is mandatory** —
  entity-escaping `ac:plain-text-body` instead makes Confluence silently rewrite it to
  `ac:rich-text-body`, reflowing ASCII diagrams. Angle brackets inside CDATA are **safe**; the
  only real hazard is a literal `]]>`.
- Official macros: info+toc, `panel` for Risks (`#D04437`/`#FFD5D2`) and Dependencies
  (`#4A6785`/`#DEEBFF`), `note` for blockquotes, `ac:task-list` with the exact non-sequential
  Pre-Dev Security ids.
- Jira macro only for `ION-\d+`, never inside inline code / links / URLs (so `CVE-2026-xxxx` is
  left alone).
- Bullet/ordered lists, and pipes inside inline-code spans, are handled.

> **If `SOURCE_DOC` contains ` ```mermaid ` fences, stop and read
> [Enhancement — Mermaid diagram support](#enhancement--mermaid-diagram-support-findings--implementation-plan)
> first.** Publishing succeeds, but no mermaid macro is installed on this Confluence instance and the
> converter has no mermaid branch — the diagram renders as its own **source text** in a code box.
> Either convert the diagram to ASCII art (zero effort, renders faithfully) or implement Option 2.

Spot-check the output before publishing: `head -c 1200 "$SP/doc.xhtml"` and
`grep -o '<h1>[^<]*</h1>' "$SP/doc.xhtml"` — confirm the section list matches the markdown and the
H1 title is absent from the body.

---

## Step 4 — Publish

Send the **entire** body in one call. Never publish a partial body and then
`confluence_append_to_page` the rest — append re-sends the combined body and hits the same `400`,
leaving a half-populated page.

### 4a. Bodies under ~20 KB — use the MCP tool directly

```
confluence_create_page(
  space_key      = "<SPACE>",
  title          = "<CONFLUENCE_PAGE_TITLE>",
  body           = "<contents of doc.xhtml, verbatim>",
  parent_id      = "<CONFLUENCE_PARENT_PAGE_ID>",
  representation = "storage"
)
```

Updating instead (full body, version auto-increments):

```
confluence_update_page(
  page_id        = "<EXISTING_PAGE_ID>",
  body           = "<contents of doc.xhtml, verbatim>",
  title          = "<CONFLUENCE_PAGE_TITLE>",
  representation = "storage",
  minor_edit     = false
)
```

### 4b. Bodies over ~20 KB (typical for a full design doc) — drive the same client from disk

Re-emitting 50 KB+ of XHTML as a tool argument burns ~30k tokens and risks a transcription defect
that the converter's self-check can no longer catch. Instead, call the **same** `ConfluenceClient`
with the **same** SSO cookies from a venv script that reads the file off disk — identical write
path, zero escaping risk:

```bash
SP="<session scratchpad dir>"
cat > "$SP/publish.py" <<'PY'
import asyncio, sys, json
from mcp_context_server.config import get_settings
from mcp_context_server.confluence_client import ConfluenceClient
from mcp_context_server.sso_auth import SSOCookieAuth

XHTML, TITLE, SPACE, PARENT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
body = open(XHTML, encoding="utf-8").read()
s = get_settings()
c = ConfluenceClient(s.confluence_base_url, s.confluence_email, s.confluence_api_token,
                     sso_auth=SSOCookieAuth())
print("configured=", c.configured, "len(body)=", len(body))
print(json.dumps(asyncio.run(
    c.create_page(space_key=SPACE, title=TITLE, body=body, parent_id=PARENT)), indent=2))
PY

cd "/c/Users/arijit.kundu/OneDrive - WiseTech Global/aiengg/mcp/mcp-summary-server"
./.venv/Scripts/python.exe "$SP/publish.py" "$SP/doc.xhtml" "<CONFLUENCE_PAGE_TITLE>" "<SPACE>" "<PARENT_ID>"
```

Swap `create_page(...)` for `c.update_page(page_id=..., body=body, title=TITLE, minor_edit=False)`
when updating. Run it from the server repo dir so `.env` loads even if the live MCP server is
unconfigured. Never `curl` — no credentials in a shell history.

**Error handling**

| Response | Meaning | Action |
|---|---|---|
| `400 Error parsing xhtml: Unexpected character …` | unescaped `&`/`<`/`>`; the row/col points at it | fix the **converter**, re-run Step 3, re-send the whole body |
| `401` | SSO session dead | Step 1 Action 2, then retry |
| `"Confluence is not configured"` | base URL missing | `SETUP-confluence-mcp.md` Actions 1 + 3 |
| `400 A page with this title already exists` | duplicate title | back to Step 2 and decide create vs update |

---

## Step 5 — Verify (byte-level, against `body.storage`)

> ### ⚠️ Never verify from `body_text`
> `confluence_get_page` returns `body_text`, a **lossy** extraction: it omits all `<![CDATA[…]]>`
> content and prints macro *parameter* values as bare text (a `diff` language param, panel colours
> as `#D04437`, the info macro's `false` icon). A perfectly healthy page therefore reads as though
> its code blocks were swallowed. Diagnosing from `body_text` caused a good page to be replaced
> with a broken one on 2026-07-29.

Fetch `?expand=body.storage` and compare, normalising the **three** documented server-side
rewrites — without them `sent == stored` always reports a false mismatch:

1. `ac:macro-id="<uuid>"` is added to every macro.
2. `&#x27;` / `&apos;` are unescaped to `'`.
3. Empty `<th></th>` / `<td></td>` become self-closing `<th />` / `<td />`.

(Also: Confluence rewrites `<table>` → `<table class="wrapped">`, so counting the literal
`'<table>'` returns 0 on a good page — match `<table[\s>]` instead.)

```bash
SP="<session scratchpad dir>"
cat > "$SP/verify.py" <<'PY'
import asyncio, sys, re
from mcp_context_server.config import get_settings
from mcp_context_server.confluence_client import ConfluenceClient
from mcp_context_server.sso_auth import SSOCookieAuth

PID, LOCAL = sys.argv[1], sys.argv[2]
s = get_settings()
c = ConfluenceClient(s.confluence_base_url, s.confluence_email, s.confluence_api_token,
                     sso_auth=SSOCookieAuth())

async def go():
    r = await c._send("GET", f"/rest/api/content/{PID}",
                      params={"expand": "body.storage,version"})
    r.raise_for_status()
    d = r.json()
    return d["body"]["storage"]["value"], d["version"]["number"], d["title"]

stored, ver, title = asyncio.run(go())
local = open(LOCAL, encoding="utf-8").read()

def norm(x):
    x = re.sub(r'\s*ac:macro-id="[^"]*"', '', x)
    x = x.replace('&#x27;', "'").replace('&apos;', "'")
    x = re.sub(r'<(th|td)></\1>', r'<\1 />', x)
    return re.sub(r'\s+', ' ', x).strip()

ns, nl = norm(stored), norm(local)
print("version=", ver, "| title=", title)
print("stored len=", len(stored), "normalized equal=", ns == nl)
if ns != nl:
    for i, (a, b) in enumerate(zip(ns, nl)):
        if a != b:
            print("first diff at", i)
            print("STORED:", ns[max(0, i-120):i+160])
            print("LOCAL :", nl[max(0, i-120):i+160])
            break
    else:
        print("length diff only:", len(ns), len(nl))

cd_s = re.findall(r'<!\[CDATA\[(.*?)\]\]>', stored, re.S)
cd_l = re.findall(r'<!\[CDATA\[(.*?)\]\]>', local, re.S)
print("CDATA blocks stored/local:", len(cd_s), len(cd_l), "byte-equal:", cd_s == cd_l)
print("code macros:", stored.count('ac:name="code"'),
      "| tables:", len(re.findall(r'<table[\s>]', stored)),
      "| h1:", stored.count('<h1>'),
      "| task-list:", stored.count('<ac:task-list'),
      "| panels:", stored.count('ac:name="panel"'),
      "| jira:", stored.count('ac:name="jira"'))
PY

cd "/c/Users/arijit.kundu/OneDrive - WiseTech Global/aiengg/mcp/mcp-summary-server"
./.venv/Scripts/python.exe "$SP/verify.py" "<NEW_PAGE_ID>" "$SP/doc.xhtml"
```

**Pass criteria — all four:**

- [ ] `normalized equal = True` (or every diff explained by the three rewrites above)
- [ ] `CDATA blocks … byte-equal: True` **and** `count('ac:name="code"') == len(CDATA blocks)`
- [ ] macro/table/heading counts match the converter's Step 3 summary line
- [ ] `confluence_page_children(<PARENT_ID>)` lists the new page under the landing page

---

## Step 6 — Report and record

1. Give the user the page URL — prefer the readable form
   `https://confluence.dev.e2open.com/display/<SPACE>/<url-encoded title>`; the API returns
   `…/pages/viewpage.action?pageId=<id>`, which also works.
2. State the page id, version, body size, and the verification result explicitly.
3. If the MCP session tools are in use, `session_update_status` with the final status, page id,
   version and URL.
4. Delete the scratchpad scripts only if the user asks — keeping them makes a re-publish trivial.

---

## Enhancement — Mermaid diagram support (findings + implementation plan)

**Status: NOT implemented.** This section records what was measured and exactly what to build.
Read it before publishing any doc that contains ` ```mermaid ` fences.

### Findings (probed 2026-08-26 against `confluence.dev.e2open.com`)

Probe method — no page needed. `POST /rest/api/contentbody/convert/view` with
`{"value": "<storage fragment>", "representation": "storage"}` renders a storage fragment exactly
as a page would. An uninstalled macro comes back as `<img class="wysiwyg-unknown-macro" …>`; an
installed-but-erroring one comes back as `<div class="aui-message aui-message-error">`.

| Macro | Verdict |
|---|---|
| `mermaid-cloud`, `mermaid`, `mermaid-diagram`, `mermaid-macro`, `mermaid-diagrams-for-confluence` | ❌ **not installed** |
| `plantuml`, `plantumlrender`, `graphviz`, `dot`, `blockdiag`, `seqdiag`, `gliffy`, `balsamiq` | ❌ not installed |
| `drawio` | ✅ installed (own XML format — not authorable from markdown) |
| `lucidchart`, `chart`, `expand`, `code`, `noformat`, `excerpt`, `attachments`, `view-file` | ✅ installed |

**Consequence today:** `convert_design_doc.py` has **no** mermaid handling (`grep -i mermaid` →
nothing), so a ` ```mermaid ` fence falls through to the generic code-macro path and emits
`<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">mermaid</ac:parameter>…`.

- **Publishing succeeds** — no `400`, self-check passes, page is created.
- **Rendering is plain text** — Confluence does not know the `mermaid` language and silently falls
  back to `brush: java`, so the reader gets the mermaid *source* in a monospace box with Java
  syntax colouring. Verified in the rendered HTML.

> ⚠️ The mermaid row in `_base-confluence-publisher.md` Step 4c promises a `mermaid-cloud` macro.
> That is wrong on this instance twice over: the macro is not installed, and the converter would
> not emit it anyway. Only its parenthetical fallback ("use ASCII inside a `code` block") is
> accurate — and that remains the zero-effort option.

### Option 2 — pre-render mermaid → PNG, attach, reference via `<ac:image>`

The only route that yields real diagrams while keeping **markdown as the source of truth**. Four
changes; the first two are local, the last two touch the publish path.

Tooling on this machine: Node **v24.14.1**, npm/npx **11.11.0** present; `mmdc` **not** installed
(`npx` fetches it).

#### 2.1 Converter — emit an image reference plus a sidecar manifest

Add a mermaid branch to the fenced-code handler in `convert_design_doc.py` (the code-macro emitter
is at ~line 159). Gate it behind a flag so existing behaviour is untouched by default:

```
python convert_design_doc.py <in.md> <out.xhtml> --mermaid=code|image     # default: code
```

With `--mermaid=image`, for each mermaid fence (0-based index `i`, source `src`):

```python
import hashlib
digest   = hashlib.sha1(src.encode("utf-8")).hexdigest()[:8]
filename = f"diagram-{i:02d}-{digest}.png"
```

**Use a content hash, never a timestamp or random suffix.** A re-publish of an unchanged diagram
reuses the same attachment (no version churn); a changed diagram gets a new filename. It also keeps
the converter deterministic, which the self-check depends on.

Emit into the body:

```xml
<ac:image ac:align="center" ac:width="900" ac:alt="Inbound / outbound data flow">
  <ri:attachment ri:filename="diagram-00-7f3a9c21.png" />
</ac:image>
```

No `xmlns` declarations are needed — storage bodies posted via REST are fragments, exactly as with
the existing `ac:structured-macro` output. Cap `ac:width` around `900` or wide diagrams force the
page to scroll.

Write two sidecars next to `out.xhtml`:

- `out.diagrams.json` — the manifest:
  `[{"index":0,"filename":"…png","mmd":"…/diagram-00-7f3a9c21.mmd"}]`
- one `.mmd` file per diagram, holding the raw fence body

#### 2.2 Render step — mermaid-cli

```bash
SP="<scratchpad>"
printf '{ "args": ["--no-sandbox", "--disable-dev-shm-usage"] }' > "$SP/puppeteer-config.json"

for mmd in "$SP"/diagram-*.mmd; do
  npx -y @mermaid-js/mermaid-cli@11 \
      -i "$mmd" -o "${mmd%.mmd}.png" \
      -b white -s 3 -t default \
      -p "$SP/puppeteer-config.json"
done
```

- `-s 3` gives a crisp raster at Confluence display width; `-b white` matches the page.
- **Pin the major version** (`@11`) — an unpinned `npx -y` silently upgrades and can change output.
- **Use PNG, not SVG.** Confluence Server frequently renders an attached SVG as a download link
  rather than inline.

#### 2.3 Attachment upload — add it to the publish script

`ConfluenceClient` has **no attachment method** (`create_page`, `update_page`, `append_to_page`,
`delete_page`, `get_page`, `search`, `get_space_pages`, `get_page_children` only), so drive the
REST endpoint through its authenticated httpx client:

```python
import os, mimetypes

async def upload_attachment(c, page_id, path, comment="mermaid render"):
    """Attach a file, creating it or adding a new version if the filename exists."""
    name   = os.path.basename(path)
    mime   = mimetypes.guess_type(name)[0] or "application/octet-stream"
    client = await c._get_client()          # carries the SSO cookies + base_url

    # (a) MANDATORY: the client sets a DEFAULT header Content-Type: application/json
    #     (both the SSO and the Basic path). Left in place it overrides the multipart
    #     content type and the upload fails. Popping it is safe: httpx re-adds
    #     application/json automatically for later json= calls.
    client.headers.pop("Content-Type", None)

    # (b) MANDATORY on Confluence Server: XSRF bypass, else 403.
    hdrs = {"X-Atlassian-Token": "no-check"}

    r = await client.get(f"/rest/api/content/{page_id}/child/attachment",
                         params={"filename": name}, headers=hdrs)
    r.raise_for_status()
    existing = r.json().get("results", [])

    with open(path, "rb") as fh:
        files = {"file": (name, fh.read(), mime)}
        data  = {"comment": comment, "minorEdit": "true"}
        # (c) Re-POSTing an existing filename to /child/attachment returns
        #     400 "Cannot add a new attachment with same file name as an existing
        #     attachment". Add a new VERSION via the /data endpoint instead.
        ep = (f"/rest/api/content/{page_id}/child/attachment/{existing[0]['id']}/data"
              if existing else
              f"/rest/api/content/{page_id}/child/attachment")
        r = await client.post(ep, files=files, data=data, headers=hdrs)
    r.raise_for_status()
    return r.json()
```

#### 2.4 Publish order — attachments are children of content, so the page must exist first

`ri:attachment ri:filename` is resolved **lazily at render time**, so no third pass to rewrite the
body is needed — the body may reference an attachment that lands moments later.

| Case | Order | Note |
|---|---|---|
| **New page** | `create_page(body)` → `upload_attachment(...)` × N | The page id only exists after create. Images render broken in the gap between the two calls — seconds, and invisible unless someone loads the page mid-flight. |
| **Existing page** | `upload_attachment(...)` × N → `update_page(body)` | Preferred: never shows a broken image. |

If a broken-image window is unacceptable for a brand-new page, create it with a one-line
placeholder body, attach, then `update_page` with the real body.

### Self-check and verification changes this requires

**Converter self-check** (it currently byte-compares every CDATA block against its markdown fence —
mermaid blocks no longer produce CDATA, so it would report a false failure):

- exclude mermaid fences from the CDATA byte-compare, and assert
  `len(CDATA blocks) == len(non-mermaid fences)`
- assert a **1:1** mapping between manifest entries and `<ac:image><ri:attachment>` refs in the
  XHTML — in both directions
- assert every manifest `.png` exists on disk and is non-empty **before** publish
- non-zero exit still means DO NOT PUBLISH

**Step 5 verification** — add to the existing pass criteria:

- `GET /rest/api/content/<id>/child/attachment?limit=100` → every manifest filename present, each
  with a non-zero `extensions.fileSize`
- `GET /rest/api/content/<id>?expand=body.view` → each filename appears in an `<img src=…>`, and
  the view HTML contains no `wysiwyg-unknown-macro` or `aui-message-error`
- the normalised storage byte-compare still applies. **Confirm on the first run** whether
  Confluence adds a fourth server-side rewrite to `<ac:image>` (e.g. `ri:version-at-save`, or
  attribute reordering); if it does, add it to `norm()` rather than treating it as corruption

### Gotchas

| Gotcha | Effect | Mitigation |
|---|---|---|
| Client default `Content-Type: application/json` | multipart upload rejected | `client.headers.pop("Content-Type", None)` (§2.3a) |
| Missing `X-Atlassian-Token: no-check` | `403` on upload | always send it (§2.3b) |
| Re-POST of an existing filename | `400 Cannot add a new attachment with same file name` | use `/child/attachment/{id}/data` (§2.3c) |
| First `npx` run | downloads Chromium (~170 MB); needs npm-registry access through the corporate proxy | pre-install once; if blocked, fall back to `--mermaid=code` + ASCII |
| Puppeteer sandbox on Windows | mmdc hangs or crashes | `-p puppeteer-config.json` with `--no-sandbox` |
| SVG output | renders as a download link, not inline, on Confluence Server | emit PNG |
| Content-hash rename | the previous PNG is orphaned on the page | optionally prune attachments absent from the manifest — never prune blind |
| Rendered PNGs | build artifacts | keep in the scratchpad; do not commit |
| Wide diagrams | page scrolls horizontally | `ac:width` ≤ ~900 |

### Acceptance checklist for the enhancement

- [ ] `--mermaid=code` (default) output is **byte-identical** to today's — no regression for the
      existing docs
- [ ] `--mermaid=image` produces manifest + `.mmd` files + `<ac:image>` refs, and the self-check
      catches both a deliberately deleted PNG and a hand-edited image ref
- [ ] a doc with ≥2 mermaid diagrams publishes, and `body.view` shows both as real `<img>`s
- [ ] re-publishing the same doc unchanged adds **no** new attachment version
- [ ] changing one diagram attaches exactly one new file and leaves the other untouched
- [ ] both new failure modes (403 without the XSRF header, 400 on duplicate filename) are exercised
- [ ] Step 3 / Step 4 / Step 5 of this runbook and the mermaid row in
      `_base-confluence-publisher.md` are updated to match reality

---

## Failure-mode quick reference

| Symptom | Real cause | Fix |
|---|---|---|
| `"Confluence is not configured"` | `.mcp.json` `env` lacks `MCP_CONFLUENCE_BASE_URL` (server never loads `.env` because Claude Code ignores the configured `cwd`) | `SETUP-confluence-mcp.md` Actions 1 + 3 |
| `401` on every call, cookie file looks valid | server-side `JSESSIONID` invalidated; `X-AUSERNAME: None` | `sso_login.py` (Step 1 Action 2) + `auth_reload` |
| `400 Error parsing xhtml` | unescaped `&`/`<`/`>` in prose or inline code | fix converter, regenerate, re-send full body |
| ASCII diagram reflowed on the page | `ac:plain-text-body` entity-escaped instead of CDATA | keep CDATA; never "fix" angle brackets |
| Page looks like its code blocks vanished | you read `body_text` | re-read `?expand=body.storage` |
| `sent != stored` | the three server-side rewrites | normalise before comparing |
| `PermissionError: C:/Program Files/Git/…` | `$TMPDIR` unset in Git Bash | use the session scratchpad dir |
| Half-populated page | partial publish + `confluence_append_to_page` | delete/replace with a single full-body call |

## MCP tools used

`confluence_search` · `confluence_get_page` · `confluence_page_children` ·
`confluence_create_page` · `confluence_update_page` · `auth_reload`
(`confluence_append_to_page` — **do not use** for design docs)

## Related files

| File | Purpose |
|---|---|
| `SETUP-confluence-mcp.md` | One-time machine setup; Action 2 is the SSO refresh referenced above |
| `_base-confluence-publisher.md` | Shared Steps 4–5 contract (this runbook is its standalone, self-contained form) |
| `confluence-design-doc-generator.md` | Use instead when the doc must still be **generated** from an analysis file |
| `confluence-publish-doc.md` | Prompt-style equivalent of this runbook (PARAMETERS block) |
| `templates/architecture-template.md` | Section schema mirroring corporate template page `672934513` |
| `convert_design_doc.py` (repo root) | The reference MD → storage-format converter |
