# SETUP — Make the MCP Confluence/Jira publishing work (for Arijit)

This is a **one-time machine setup** so the `confluence-design-doc-generator.md` prompt can read
Jira and publish to Confluence through the `mcp-context-server` tools (no `curl`, no credentials in
prompts). Do these steps in order. Most only need redoing if you change machines or the SSO session
expires.

> TL;DR of what was wrong before: the MCP server reads its credentials from a `.env` file relative
> to its working directory, but Claude Code launches the server **without** honoring the configured
> `cwd`, so `.env` never loaded and every Confluence/Jira tool said *"not configured."* The fix is to
> put the connection settings directly in `.mcp.json`'s `env` block. Auth itself uses your SSO
> browser cookies, not a password.

---

## ✅ Action 1 — Add Jira/Confluence settings to `.mcp.json` (REQUIRED)

I was blocked from editing `.mcp.json` automatically (it's agent-startup config). Please add these
four lines to the `env` block of the `mcp-context-server` entry in
`C:\Users\arijit.kundu\projects\mercury-services\.mcp.json`:

```jsonc
"env": {
  "MCP_SESSIONS_DIR": "...",            // (existing — leave as-is)
  "MCP_KB_ROOTS": "...",                // (existing)
  "MCP_GIT_DEFAULT_REPOS": "...",       // (existing)
  "MCP_LOG_LEVEL": "INFO",              // (existing)

  // ── add these four ──────────────────────────────────────────────
  "MCP_JIRA_BASE_URL": "https://jira.dev.e2open.com/jira",
  "MCP_JIRA_EMAIL": "akundu",
  "MCP_CONFLUENCE_BASE_URL": "https://confluence.dev.e2open.com",
  "MCP_CONFLUENCE_EMAIL": "akundu"
}
```

**No password/token goes here** — authentication is handled by your stored SSO cookies (Action 2).
That's why only the base URL + email are needed: the server's "configured" check just needs the
base URL present, and the SSO cookies do the actual login.

> If you ever want password/basic-auth as a fallback (instead of SSO), you can also add
> `MCP_JIRA_API_TOKEN` and `MCP_CONFLUENCE_API_TOKEN`. If you do, treat `.mcp.json` as a secret —
> see Action 4.

---

## ✅ Action 2 — Refresh the SSO session (REQUIRED, repeat when it expires)

The server authenticates to Jira/Confluence using cookies captured from a browser SSO login. They
live at `C:\Users\arijit.kundu\.mcp-context-server\browser_cookies.json` (machine-wide, not tied to
any project directory).

If a tool ever returns **`401`**, the cookies expired — refresh them:

```powershell
cd "C:\Users\arijit.kundu\OneDrive - WiseTech Global\aiengg\mcp\mcp-summary-server"
.\.venv\Scripts\python.exe sso_login.py
```

This opens a browser; authenticate with passkey/Windows Hello. (You already did this once — the
cookies were valid as of the last publish.)

---

## ✅ Action 3 — Reconnect the MCP server (REQUIRED after Action 1)

Claude Code only re-reads `.mcp.json` when the server (re)connects. After editing it:

- In Claude Code, run `/mcp` and reconnect `mcp-context-server` (or restart Claude Code).

**Verify it worked** — either run `/mcp` and confirm the server is connected, or run this quick
check (it uses the server's own client and should print `configured=True`):

```powershell
cd "C:\Users\arijit.kundu\OneDrive - WiseTech Global\aiengg\mcp\mcp-summary-server"
.\.venv\Scripts\python.exe -c "from mcp_context_server.config import get_settings as g; from mcp_context_server.confluence_client import ConfluenceClient as C; from mcp_context_server.sso_auth import SSOCookieAuth as S; s=g(); c=C(s.confluence_base_url,s.confluence_email,s.confluence_api_token,sso_auth=S()); print('base_url=',s.confluence_base_url,'configured=',c.configured)"
```

Inside Claude Code, you can also just call any read tool (e.g. `jira_get_issue` on a known key) — if
it returns data instead of *"not configured"*, you're set.

---

## ✅ Action 4 — Keep `.mcp.json` out of git (RECOMMENDED)

`.mcp.json` is currently **untracked but not git-ignored**. Even though Actions above don't store a
password, it's safest to never commit your local MCP wiring. Add to `.gitignore`:

```
.mcp.json
```

(Also already-loose local artifacts from earlier debugging that you may want to remove or ignore:
`confluence_design_doc.html`, `convert_design_doc.py`, `mcp_payload.json`, `confluence_*.json`,
`confluence_params.json`, `prepare_confluence_update.py`, `publish_to_confluence.py`,
`show_confluence_params.py`, and the stray `NUL` / `C\357\200\272...log` files in the repo root.
`convert_design_doc.py` is worth **keeping** — the generator prompt references it as the reference
storage-format converter.)

---

## How auth/config flows (reference)

```
.mcp.json env  ──►  MCP_CONFLUENCE_BASE_URL / EMAIL      ──►  server "configured" = true
sso_login.py   ──►  ~/.mcp-context-server/browser_cookies.json  ──►  actual Jira/Confluence auth
```

- **"... is not configured"**  → base URL missing → Action 1 + Action 3.
- **`401 Unauthorized`**        → SSO cookies expired → Action 2.
- **`400 Error parsing xhtml`** → not an auth issue; it's an un-escaped `&`/`<`/`>` in the page body
  → see the escaping rule in `confluence-design-doc-generator.md` (Step 4c).

---

## Files in this folder

| File | Purpose |
|------|---------|
| `confluence-design-doc-generator.md` | **Reusable** prompt — set the PARAMETERS block (analysis file + parent page + space + title + Jira keys) and run to generate & publish any design doc. |
| `confluence-design-doc-template.md` | The standard design-doc section template the generator fills in. |
| `SETUP-confluence-mcp.md` | This file — one-time machine setup for MCP Confluence/Jira access. |
| `2026-06-16-booking-template-jetty-issue.md` | The original ION-16032 instance (kept for history); the generator supersedes it for new docs. |
