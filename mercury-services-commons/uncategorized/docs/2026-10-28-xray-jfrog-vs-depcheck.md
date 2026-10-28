# JFrog Xray vs OWASP Dependency-Check — and how to run Xray locally

**Date:** 2026-10-28
**Context:** The organisation has moved vulnerability scanning from **OWASP Dependency-Check**
(still installed locally and previously wired into our Jenkins pipelines) to **JFrog Xray**.
This note explains how the two differ and what it takes to run Xray scans from a developer
machine.

> Scope: conceptual / tooling reference. No repository code changes are associated with this
> document.

---

## 1. TL;DR

Both tools answer the same question — *"do my dependencies contain known vulnerabilities?"* —
but they are architecturally different:

- **Dependency-Check** is a **standalone, point-in-time** scanner that *guesses* which
  component a JAR is (heuristic CPE matching) and looks it up in the public **NVD** feed.
- **Xray** is a **platform-integrated, continuous** scanner that *knows exactly* which
  component a binary is (checksum-indexed through **Artifactory**) and evaluates it against
  JFrog's curated **VulnDB**, enforcing **Policies/Watches** that can gate builds and
  downloads.

**Running Xray "locally" is possible via the JFrog CLI (`jf audit` / `jf scan`), but it is
not offline** — the CLI still calls a live JFrog Platform (Artifactory + Xray) to perform the
analysis. See §4.

---

## 2. How each tool works

### 2.1 OWASP Dependency-Check (what we used to run)

- **Component identification — heuristic.** It opens each artifact, gathers "evidence"
  (file names, POM coordinates, `MANIFEST.MF` entries) and infers a **CPE** (Common Platform
  Enumeration) identifier. Because the match is fuzzy, it is the source of the familiar
  **false positives / false negatives**.
- **Vulnerability data — public feeds.** Primarily the **NVD** CVE feed, optionally
  **Sonatype OSS Index** (which requires a token). *This is why our local scans historically
  reported fewer findings than Jenkins — the CI host had an OSS Index token and we did not.*
- **Execution model — point-in-time, in-build.** A Maven plugin / CLI step scans whatever is
  on the classpath at that moment and emits a report. When the build ends, nothing keeps
  watching; a CVE published tomorrow is only caught on the next re-run.
- **Scope.** Declared + transitive dependencies, CVEs only.
- **Enforcement & noise handling.** Fails the build on a configured CVSS threshold; false
  positives are silenced with a committed `suppressions.xml`.
- **Infrastructure.** None — fully standalone CLI / Maven plugin.

### 2.2 JFrog Xray (what the company moved to)

- **Component identification — exact.** Xray is tightly coupled to **Artifactory**. Every
  artifact entering Artifactory is indexed by **SHA-256 checksum** and its full dependency
  graph is recorded, so Xray knows the *precise* component + version — no CPE guessing, far
  fewer false positives.
- **Vulnerability data — curated.** JFrog's **VulnDB / global database**: NVD **plus** JFrog
  security research, frequently with earlier disclosure and richer metadata than raw NVD.
- **Execution model — continuous and retroactive.** Xray maintains the dependency/impact tree
  and continuously re-evaluates it. When a *new* CVE is published for a component we shipped
  *last month*, Xray flags the **existing** builds/artifacts automatically — something a
  point-in-time scanner cannot do.
- **Scope — broader.** Besides CVEs: **license compliance**, **operational risk**
  (abandoned / outdated components), and **build-info correlation** tying a finding back to
  the exact build number that produced it.
- **Enforcement — Policies & Watches.** Instead of `suppressions.xml`, you define **Policies**
  (rules, e.g. "fail on CVSS ≥ 7") and **Watches** (which repos / builds a policy applies to).
  A violation can **block a build, block a download, or gate a release** through the CI
  integration. False positives become **Ignore Rules** against a specific CVE + component.
- **Infrastructure.** Requires a **JFrog Platform** — Artifactory + Xray (SaaS `*.jfrog.io`
  or self-hosted).

---

## 3. Side-by-side comparison

| Aspect | OWASP Dependency-Check | JFrog Xray |
|---|---|---|
| Component identification | Heuristic CPE matching (false +/−) | Exact checksum via Artifactory index |
| Vulnerability data source | NVD (+ optional OSS Index token) | JFrog VulnDB (NVD + JFrog research) |
| Timing | Point-in-time, per build run | Continuous + retroactive re-scan |
| Enforcement | Build fail + manual `suppressions.xml` | Policies/Watches gate builds & downloads |
| Noise / false-positive handling | `suppressions.xml` in repo | Ignore Rules in Xray (per CVE+component) |
| Coverage beyond CVEs | CVEs only | CVEs + licenses + operational risk |
| Build traceability | Report only | Build-info correlation to exact build |
| Infrastructure required | None (standalone) | Artifactory + Xray platform |
| Transitive dependencies | Yes | Yes (from indexed graph) |
| Offline capable | Yes (with local NVD cache) | **No** — needs a live platform connection |

---

## 4. Can we run Xray locally? Yes — via JFrog CLI, but not offline

The **JFrog CLI** (`jf`) exposes Xray scanning from a developer workstation. The important
caveat: these commands are "local" only in that they run from your machine and can scan source
or local binaries — **the actual analysis happens server-side on a JFrog Platform**, so a live
connection to Artifactory + Xray is mandatory. There is **no fully offline Xray scan**.

### 4.1 Prerequisites

1. **Access to a JFrog Platform** with Artifactory **and** Xray enabled (SaaS or self-managed).
   Get the platform URL and either a username/password or an **access token** from whoever
   administers our JFrog instance.
2. **JFrog CLI** installed (v2.1.0+ recommended; Xray 3.29.0+ on the server for full feature
   support).
3. **Network connectivity** to the platform (and any required VPN / SSO).

### 4.2 Install the JFrog CLI (Windows)

```powershell
# Option A: Chocolatey
choco install jfrog-cli

# Option B: winget
winget install JFrog.JFrogCLI

# Option C: direct download of jf.exe from https://releases.jfrog.io/artifactory/jfrog-cli/
# then place it on PATH

jf --version      # verify
```

### 4.3 Configure the server connection (one-time)

```powershell
# Interactive login (prompts for URL + credentials/token)
jf login

# Or add a named server explicitly
jf c add my-jfrog --url=https://<company>.jfrog.io --user=<user> --interactive=false
#   (prefer an access token over a password; follow the interactive prompt for the token)
```

### 4.4 The two local scan commands

| Command | What it scans | Needs platform? | Typical flags |
|---|---|---|---|
| `jf audit` | Project **dependencies from source** (auto-detects Maven/npm/Gradle/pip/Go…) | Yes | `--format=json`, `--licenses` |
| `jf scan` | **Local files / binaries** in a directory | Yes | `--watches`, `--project`, `--repo-path` |
| `jf docker scan <image>` | A local **Docker image** | Yes | `--format=json` |

**For this Maven repo**, the natural fit is `jf audit`, run from the repo root (it reads the
Maven dependency tree):

```powershell
cd C:\Users\arijit.kundu\projects\mercury-services-commons
jf audit --format=json > xray-audit.json      # machine-readable
# or just:
jf audit                                       # human-readable table
jf audit --licenses                            # include license findings
```

To scan an already-built artifact instead of source:

```powershell
jf scan "commons/target/*.jar" --format=json
# Apply a specific policy/watch the platform admins defined:
jf scan "commons/target/*.jar" --watches "commons-security-watch"
```

### 4.5 Applying our org's policies

By default `jf audit` / `jf scan` report findings; to reproduce the **same pass/fail gate** CI
uses, point the scan at the relevant Xray **Watch**, **Project**, or **repo path**:

```powershell
jf scan "commons/target/*.jar" --watches "<watch-name>"
jf audit --project "<xray-project-key>"
```

Ask the JFrog admins which Watch/Project applies to mercury-services artifacts so local results
match the Jenkins gate.

---

## 5. Practical implications for our workflow

- **False-positive noise drops.** Xray's exact checksum identification removes most of the
  CPE-guessing noise we managed with `suppressions.xml`. Suppressions migrate to **Ignore
  Rules** in the Xray UI/API (per CVE + component), managed centrally rather than in each repo.
- **The gate moves.** Enforcement shifts from "a Maven step in the build" to "a Policy/Watch on
  the artifact repository / CI pipeline." A build may still fail for a vulnerability, but
  because a **Watch** blocked it — not because a Maven plugin threw.
- **Expect Xray to report more than local Dependency-Check.** Its DB is richer (NVD + JFrog
  research) and continuous — mirroring how Jenkins + OSS Index historically reported more than
  our token-less local DC runs.
- **Local Dependency-Check still has value** as a fast, offline pre-commit sanity check, but the
  **authoritative** result now comes from Xray evaluating what we publish to Artifactory.
- **No air-gapped scanning.** Because `jf audit` / `jf scan` need the platform, you cannot run
  an authoritative Xray scan without connectivity — unlike Dependency-Check with a cached NVD.

---

## 6. Quick reference — commands

```powershell
# One-time setup
jf login                                  # or: jf c add my-jfrog --url=... --interactive=false
jf --version

# Scan this repo's dependencies from source
jf audit                                  # table output
jf audit --format=json > xray-audit.json  # JSON for automation
jf audit --licenses                       # include license compliance

# Scan a built binary / directory
jf scan "commons/target/*.jar"
jf scan "commons/target/*.jar" --watches "<watch>" --format=json

# Scan a docker image
jf docker scan <image>:<tag>
```

---

## 7. References

- JFrog CLI — Scan your binaries (`jf scan`) and audit (`jf audit`) security commands.
- JFrog blog — *Shift Left and Scan Dependencies Directly From Sources Using JFrog CLI and Xray.*
- JFrog CLI download: <https://jfrog.com/getcli/> · Xray docs: <https://jfrog.com/xray/>
- OWASP Dependency-Check: <https://jeremylong.github.io/DependencyCheck/>

*Key takeaway: even "local" Xray scans require a live Artifactory + Xray connection — the CLI
orchestrates, the platform evaluates.*
