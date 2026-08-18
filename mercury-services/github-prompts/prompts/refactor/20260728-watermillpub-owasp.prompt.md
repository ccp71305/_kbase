---
name: 20260728-watermillpub-owasp
description: >
  OWASP dependency-check remediation ONLY (no AWS SDK upgrade / no cloud-sdk refactor) for the three
  watermill-publisher modules: watermill-booking, watermill-booking-aperak, and
  watermill-cargo-visibility-subscription. Try mercury-services-commons 1.0.28-SNAPSHOT first; if it does not
  compile, fall back to 1.R.01.025 (the current version). Run pre- and post-fix dependency-check scans per module,
  publish the reports to C:\temp\latest-dep-chk-reports\<scan-dir>, keep a SINGLE outgoing commit, ensure ALL tests
  pass, boot-check each app locally and add VS Code run configs, and document every command, step and CVE-fix detail.
  Do NOT push.
argument-hint: "none"
agent: agent
model: Claude Opus 4.8 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# watermill-publisher — OWASP dependency-check remediation (OWASP ONLY, no AWS upgrade)

> **Jira:** ION-16381 · **Branch:** `feature/ION-16381-watermillpub-owasp-fix`

> **Scope:** OWASP HIGH/CRITICAL CVE remediation via a dependency version bump only. **No** AWS SDK 2.x / cloud-sdk
> migration, **no** DynamoDB/SNS/SQS refactor, **no** functional code changes beyond what a compile of the bumped
> dependency strictly requires. **No reference files needed.**

## Targets

| Module (path under `watermill-publisher/`) | Main class | Boot config | OWASP report dir |
|--------------------------------------------|------------|-------------|------------------|
| `watermill-booking` | `com.inttra.mercury.watermill.booking.WatermillBKApplication` | `watermill-booking/conf/int/config.yaml` | `C:\temp\latest-dep-chk-reports\watermill-booking` |
| `watermill-booking-aperak` | `com.inttra.mercury.watermill.bookingaperak.WatermillBKAperakApplication` | `watermill-booking-aperak/conf/int/config.yaml` | `C:\temp\latest-dep-chk-reports\watermill-aperak` |
| `watermill-cargo-visibility-subscription` | `com.inttra.mercury.cargo.visibility.WatermillCargoVisibilitySubscriptionPublisherApplication` | `watermill-cargo-visibility-subscription/conf/int/config.yaml` | `C:\temp\latest-dep-chk-reports\watermill-cargo-visibility-subscription` |

> **Report-dir note:** the aperak module maps to the dir **`watermill-aperak`** (not `watermill-booking-aperak`). All
> three dirs live under `C:\temp\latest-dep-chk-reports\` (the aperak path in the request omitted `\temp`; use `\temp`).
> Use `baseline\` and `post\` subfolders inside each, matching the rates/VAS convention.

## Dependency versions

- **Primary:** `mercury-services-commons` **`1.0.28-SNAPSHOT`** (verified present in `~/.m2`). *(The request said
  "1.0.28-SNAPSHOT5"; no such artifact exists — `1.0.28-SNAPSHOT` is the real, available version. Confirm before use.)*
- **Fallback (only if 1.0.28-SNAPSHOT does not compile):** **`1.R.01.025`** — this is the **current** version already in
  the poms, so the fallback is effectively "leave commons as-is and remediate another way / stop and flag".
- The commons version property (`mercury.commons.version`, currently `1.R.01.025`) is defined in
  `watermill-publisher/watermill-commons/pom.xml`. Locate the authoritative property (grep all watermill poms) and bump
  it there; verify each of the three modules resolves the new commons via `mvn dependency:tree`.
- If HIGH CVEs remain after the commons bump (as happened on `rates` for jackson-databind and httpcore5), apply the same
  minimal OWASP hardening used on `rates`: import the patched **`jackson-bom` (`2.21.4`)** via `dependencyManagement` and
  **drop any hard-coded `jackson-*` `<version>`** on direct dependencies so the BOM actually applies (a direct
  `<version>` overrides the BOM). Do this per-module only where needed. No other functional changes.

---

## CRITICAL CONSTRAINTS

1. **OWASP ONLY — NO AWS UPGRADE.** Do not migrate any AWS SDK, DynamoDB, SNS/SQS/SES, or cloud-sdk code. The only
   intended change is the dependency version bump (+ optional jackson-bom pin) to clear HIGH/CRITICAL CVEs. Make the
   smallest source change that a successful compile of the bumped dependency strictly requires, and no more.
2. **SINGLE OUTGOING COMMIT.** End state: exactly **one** commit (`git log --oneline develop..HEAD` = one line) on top of
   the latest develop, covering all three modules. Fold everything via `git commit --amend`.
3. **COMMIT MESSAGE** must contain a valid Jira key `ION-16381` (required by the Bitbucket "git control freak" hook).
   Jira key = **ION-16381**; branch = **feature/ION-16381-watermillpub-owasp-fix**.
4. **DO NOT PUSH.** Never `git push` / `--force` / `--force-with-lease`. The user reviews locally and pushes after review.
5. **ALL TESTS MUST PASS.** `mvn -pl <module> -am ... verify` (or the watermill-publisher reactor) green for every
   module — unit and any integration tests. Do not weaken/`@Disabled` a test to go green; root-cause and fix. If a test
   breaks (related or not), find the cause and FIX it; add a reproducing test for any real bug first.
6. **BOOT-CHECK EACH APP LOCALLY.** Build the shaded jar and run `java -jar <module>/target/<jar> server
   <module>/conf/int/config.yaml` for each module. Confirm the app starts (Dropwizard handlers register / gRPC/consumers
   initialize). **Continue-on-INT-like-boot-failure rule (per request):** if a module fails to fully boot locally with a
   failure that matches the **rates** precedent — i.e. an eager startup call to an INT platform endpoint that is itself
   **down/unreachable** (rates crashed because `ISOContainerToTmContainer` eagerly called the INT `api-alpha` auth
   gateway which returns **HTTP 502**, and the **deployed INT** build failed identically) — then treat it as an
   environmental outage, **flag it and CONTINUE** (do not stop). Verify the "similar error" claim (e.g. probe the
   endpoint / read the deployed INT ECS task + CloudWatch logs) before concluding it is environmental. If a boot failure
   is instead a genuine code/config defect introduced by the change, fix it.
7. **VS CODE RUN CONFIGS.** Add **Run** and **Debug** entries to `.vscode/launch.json` for all three modules (type
   `java`, the `mainClass` above, `args": "server ${workspaceFolder}/<module>/conf/int/config.yaml"`, `cwd` = the module
   dir), mirroring the existing booking/rates entries. (`.vscode/launch.json` is git-ignored — these stay developer-local.)
8. **PRE- AND POST-FIX OWASP SCANS + CVE DELTA.** Run `dependency-check` on each module's shaded jar **before** the fix
   (baseline) and **after** (post), copy both HTML+JSON reports into the module's report dir (`baseline\` / `post\`), and
   summarize the per-module HIGH/CRITICAL CVE delta in the document.
9. **DOCUMENT EVERYTHING.** Produce a document capturing every command, each step, the boot-check results, and the
   per-module CVE-fix details (which CVEs cleared, by which version bump/pin). Put it at
   `watermill-publisher/docs/2026-07-28-watermillpub-owasp-fix.md` (create the `docs` folder if absent). Include a
   dedicated command-log section.
10. **NO SHORTCUTS / NO UNRELATED CHANGES.** Do not refactor, reformat, or upgrade anything beyond the OWASP remediation.
11. **MODEL:** Claude Opus 4.8 (1M context). Log this in session context.
12. **LOG EVERY COMMAND** (search/grep/git/mvn/dependency-check/aws) in the output doc with a one-line reason.
13. **dependency-check** is installed and the **NVD API key is in `$env:NVD_API_KEY`** — use it on every scan.

---

## Session context protocol (brief)

- `session_list` → resume an existing `watermill-publisher` / OWASP session if present, else `session_create`
  (name `watermillpub-owasp-20260728`, project `mercury-services`, tags `["watermill-publisher","owasp","owasp-fix","in-progress"]`).
- During work, `session_add_context` after each significant step: baseline scan results, version-bump decision
  (1.0.28-SNAPSHOT vs 1.R.01.025 fallback), compile/test results, boot-check outcome (+ any INT-like flag), post scan
  delta, the single-commit SHA. Categories: `finding` / `decision` / `code_change` / `test_result` / `blocker` /
  `progress` / `model_info`.
- Token-usage telemetry is captured by the harness hook; do not fabricate usage. At the end call `session_usage_report`
  and note the result in the doc (flag if `record_count = 0`).

---

## Steps

### Step 0 — Orient, branch, back up, run configs
```powershell
cd C:\Users\arijit.kundu\projects\mercury-services
git checkout develop; git merge --ff-only origin/develop        # latest develop (fetch may need creds; ff to fetched ref)
git checkout -b feature/ION-16381-watermillpub-owasp-fix develop
# Add Run/Debug VS Code configs for the three modules to .vscode/launch.json (see Constraint 7).
# Identify the commons version property:
Select-String -Path watermill-publisher\**\pom.xml -Pattern 'mercury.commons.version|<artifactId>commons</artifactId>'
```

### Step 1 — Baseline OWASP scans (per module, BEFORE any change)
For each module build the shaded jar, then scan it. Substitute the real jar name after the build
(`<module>/target/*.jar` — the shaded jar, e.g. `watermill-booking-1.0.jar`).
```powershell
mvn -pl watermill-publisher/<module> -am package -DskipTests                # build shaded jar
New-Item -ItemType Directory -Force -Path "C:\temp\latest-dep-chk-reports\<scan-dir>\baseline" | Out-Null
dependency-check --project <module> --scan .\watermill-publisher\<module>\target\<jar>.jar `
    --out "C:\temp\latest-dep-chk-reports\<scan-dir>\baseline" --format HTML --format JSON `
    --suppression <suppressions.xml if present> --nvdApiKey $env:NVD_API_KEY
```
Parse each JSON: record HIGH/CRITICAL CVEs per module (this is the baseline for the delta).

### Step 2 — Local boot-check (per module)
```powershell
java -jar watermill-publisher\<module>\target\<jar>.jar server watermill-publisher\<module>\conf\int\config.yaml
```
Confirm startup. Apply the **continue-on-INT-like-boot-failure rule** (Constraint 6): verify any boot failure matches the
rates INT-outage precedent before continuing; otherwise fix a genuine defect. Record the outcome per module.

### Step 3 — Apply the OWASP fix (version bump first)
- Bump `mercury.commons.version` → **`1.0.28-SNAPSHOT`** at the authoritative property location.
- `mvn -pl watermill-publisher/<each-module> -am clean test-compile` — if it **compiles**, keep 1.0.28-SNAPSHOT.
- If it **does not compile** (API removed/moved), **revert to `1.R.01.025`** and flag that 1.0.28-SNAPSHOT is not
  drop-in for these modules (document the exact compile error); then remediate the HIGH CVEs by pinning patched
  transitive versions directly (jackson-bom `2.21.4`, and any httpcore5/other flagged HIGH) without the commons bump.
- If HIGH CVEs remain after the commons bump, add the `jackson-bom 2.21.4` `dependencyManagement` import per affected
  module and drop hard-coded `jackson-*` `<version>` overrides (mirrors the rates OWASP fix). No functional changes.

### Step 4 — Build + ALL tests pass
```powershell
mvn -pl watermill-publisher/watermill-booking,watermill-publisher/watermill-booking-aperak,watermill-publisher/watermill-cargo-visibility-subscription -am clean verify `
    2>&1 | Tee-Object $env:TEMP\watermillpub-verify.log | Select-String 'Tests run:|BUILD SUCCESS|BUILD FAILURE'
```
Root-cause and FIX any failure (do not pipe a live mvn run straight into Select-String — tee to a log then grep). Record
per-runner test counts.

### Step 5 — Post-fix OWASP scans + CVE delta
Rebuild each shaded jar and rescan into the module's `post\` folder (same command as Step 1). Compare HIGH/CRITICAL vs
baseline; confirm **0 HIGH/CRITICAL remaining** (or document any that lack an available fix). Ensure **both** baseline and
post reports (HTML+JSON) are present in each module's report dir.

### Step 6 — Single commit, document, handoff
```powershell
git add -A                                                     # only the intended pom/source changes (no target/ or generated)
git commit -m "ION-16381: watermill-publisher OWASP dependency-check fix - commons 1.0.28-SNAPSHOT (jackson-bom 2.21.4 pin as needed)"
git log --oneline develop..HEAD                               # exactly ONE line, message contains ION-16381
git status -sb                                                # clean, nothing pushed
```
Write `watermill-publisher/docs/2026-07-28-watermillpub-owasp-fix.md` with: summary; version decision (1.0.28-SNAPSHOT
vs 1.R.01.025 fallback + why); per-module baseline→post CVE delta and which bump/pin cleared each CVE; boot-check
results (+ any INT-like flag with evidence); VS Code run configs added; full command log; build/test results;
token-usage. **Do not push.** Tell the user it is ready for review.

---

## Definition of Done

- [ ] Session created/resumed; model + decisions + command log recorded; token-usage noted.
- [ ] `mercury.commons.version` bumped to `1.0.28-SNAPSHOT` (or fallback `1.R.01.025` with the compile error documented).
- [ ] Baseline **and** post `dependency-check` reports (HTML+JSON) published for each module under
      `C:\temp\latest-dep-chk-reports\{watermill-booking, watermill-aperak, watermill-cargo-visibility-subscription}\{baseline,post}`.
- [ ] Per-module CVE delta summarized; **0 HIGH/CRITICAL remaining** (or unfixable ones documented).
- [ ] Local boot-check run for all three modules; INT-like environmental boot failures flagged-and-continued (verified),
      genuine defects fixed.
- [ ] VS Code Run/Debug configs added for all three modules.
- [ ] `mvn ... clean verify` BUILD SUCCESS across the three modules; **all** tests pass.
- [ ] **No** AWS/cloud-sdk/DynamoDB/SNS/SQS changes; no unrelated refactors.
- [ ] Exactly **one** outgoing commit, message contains `ION-16381`, **not pushed**.
- [ ] `watermill-publisher/docs/2026-07-28-watermillpub-owasp-fix.md` written with commands, steps and CVE-fix details.
