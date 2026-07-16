# Rebase Analysis — `feature/ION-12310-commons-cloudsdk-refactoring` ← `origin/develop`

**Date:** 2026-07-17
**Author:** Copilot CLI (Claude Opus 4.8) — analysis only, **no rebase performed**
**Session:** `f6889dc0804a47e8` (mcp-context-server) · prior rebase session `54e1c00694b346f1`
**Stated goal:** Rebase latest `develop` (OWASP / Jackson vulnerability fixes) into the critical
`1.0.26-SNAPSHOT` cloud-sdk feature branch consumed by mercury-services production apps.

> ⚠️ **Read Section 3 first.** The premise that the incoming `develop` changes deliver the OWASP/Jackson
> fixes does **not** hold: those fixes were **reverted on `develop`** before the current HEAD. The rebase
> as-is brings in the **S2ST framework module only**, *not* the vulnerability fixes.

---

## 1. Branch state

| Ref | Commit | Date | Notes |
|-----|--------|------|-------|
| Feature HEAD | `841fdf5` | 2026-05-28 | `ION-12310: fix Netty + Jetty CRITICAL CVEs…, bump to 1.0.26-SNAPSHOT` |
| `origin/develop` HEAD | `2745d3a` | 2026-07-15 | `PR #42: ION-16052 S2ST Framework` (merge) |
| Merge base | `0aa4a06` | 2026-05-25 | `PR #40: ION-15755` (DW 5.0.1 / Jetty 12.1.9) |

- Local `develop` is **8 commits behind** `origin/develop` → fetch/fast-forward before rebasing.
- Rebase would **replay 39 feature commits** onto `origin/develop` and pull in **8 develop commits**.
- Merge base is unchanged since **Rebase #2** (2026-05-27, session `54e1c00694b346f1`), i.e. the branch
  has not been rebased since ION-15755 (PR #40).

## 2. Prior rebase history (context)

- **Rebase #1** — 2026-05-15 (doc `cloud-sdk-api/docs/2026-05-15-commons-rebase.md`).
- **Rebase #2** — 2026-05-27, session `54e1c00694b346f1`: onto `0aa4a06` (ION-15755, DW 5.0.1 + Jetty 12.1.9).
  Result `ca99f8d`, 2 003 tests passed, backup at `backup/feature-ION-12310-pre-rebase-2`.
  **Standing resolution rule:** keep the feature branch's **removal of AWS SDK 1.x** deps
  (`aws-java-sdk-core/ssm/s3/sqs/sns`) — cloud-sdk uses AWS SDK 2.x. `.gitignore` needs a
  `/docs/` (root-only) or `!cloud-sdk-api/docs/` exception so design docs stay tracked.

## 3. 🔴 CRITICAL — the OWASP/Jackson fixes are NOT on `develop` HEAD

The 8 incoming commits include **ION-16159** ("Commons upgrade, dropwizard minor version and Vulnerability
Fixes", PR #43) which *did* add the OWASP fixes. **However**, the later **S2ST work** (`fac9edb`, PR #42,
ION-16052) **reverted them** — see §3.1 for the exact mechanism.

Verified state of `origin/develop` HEAD:

| Item | ION-16159 set it to | `origin/develop` HEAD actually has | Feature branch has |
|------|--------------------|-----------------------------------|--------------------|
| `dropwizard.version` | 5.0.2 | **5.0.1** | 5.0.1 |
| `jackson-dataformat-csv` / jdk8 / jsr310 / joda | 2.21.4 | **2.21.0** | 2.21.0 |
| `jknack.handlebars.version` | 4.5.3 | **4.3.1** | 4.3.1 |
| `dependency.version` | 1.R.01.024 | **1.R.01.023** | 1.0.26-SNAPSHOT |
| `httpcore5.version` / `httpcomponents4.*` properties (root pom) | added | **absent** | absent |
| `httpcore5` / `httpcomponents4` OWASP pins + exclusions in `commons/pom.xml` | added (113 lines) | **absent** | absent |

**Consequence:** rebasing onto `origin/develop` HEAD will **not** deliver any OWASP/Jackson vulnerability
fix. Neither `develop` HEAD **nor** the feature branch currently carries them.

### 3.1 How did the revert happen? (exact mechanism)

It was **not** a merge conflict-resolution artifact — it was a **stale-file overwrite committed inside the
S2ST feature commit `fac9edb`**. The DAG proves it:

```
fac9edb  ION-16052 - S2ST Framework changes      <-- reverts the pins
1625bd0  Pull request #43: ION-16159 …           <-- fac9edb's PARENT (pins PRESENT here)
e9bce53  ION-16159: … Vulnerability Fixes
```

- `git merge-base 6db8b14 e9bce53` → `e9bce53`, i.e. the S2ST branch was built **on top of** ION-16159
  (ION-16159 is an ancestor). So the author had the pinned poms available.
- `fac9edb^ :commons/pom.xml` (= `1625bd0`) **contains** the HttpComponents `<dependencyManagement>` pins.
- `git show fac9edb -- commons/pom.xml` shows the blob going **`91686b9 → a096fa1`** — where `a096fa1`
  is the *exact original pre-ION-16159* `commons/pom.xml` blob. In other words `fac9edb` restored the old
  file verbatim, deleting all 113 lines of pins/exclusions, and likewise reverted root `pom.xml`
  (DW 5.0.2→5.0.1, Jackson 2.21.4→2.21.0, handlebars 4.5.3→4.3.1, `dependency.version` 024→023).

**Interpretation:** the S2ST author's working copy still held **pre-ION-16159 copies** of `pom.xml` and
`commons/pom.xml` (likely edited before rebasing/pulling ION-16159, or restored from a stale branch/backup).
Committing those old files recorded a content revert. ION-16052 is a *feature addition* unrelated to the
dependency hardening, so this is almost certainly **accidental**, not a deliberate rollback. PR #42
(`2745d3a`) then merged `fac9edb` into `develop`, propagating the regression to `develop` HEAD.

**This is a regression on `develop`** — it should be raised with the team independently of this rebase
(re-apply ION-16159 on `develop`, or re-add the pins directly). See §11–§12 for the full analysis of what
ION-16159 did and why it is safe to reinstate.

> Note: the feature branch **does** carry its own separate CVE remediation for **Netty + Jetty** consumer
> builds (`841fdf5`), which is preserved through the rebase replay. That is unrelated to the ION-16159
> httpcore/Jackson pins above.

## 4. What actually comes in through the rebase (net `0aa4a06..origin/develop`)

**82 files, +5 526 / −4** — essentially one new, self-contained module:

| Area | Change | Risk |
|------|--------|------|
| `libs/wtg-federation/**` | **New module** — S2ST / WTG Federation framework (ION-16052): config, JWT/OIDC token services, outbound/inbound invocation, ~40 source + ~35 test files | Low — all new files, no overlap |
| `build_libs_deploy.sh` | New deploy script for the `libs/` tree | Low — new file |
| `pom.xml` (root) | `+ <module>libs/wtg-federation</module>`, `+ <libs.dependency.version>1.R.01.001</libs.dependency.version>` | **Conflict** (see §5) |
| `README.md` | Changelog / module list updates | **Conflict** (see §5) |

**Zero source changes** under `commons/`, `cloud-sdk-api/`, `cloud-sdk-aws/`, `dynamo-integration-test/`.

### `libs/wtg-federation` self-containment

- Declares its **own** properties: `nimbus.jose.jwt.version=10.9.1`, `nimbus.oauth2.oidc.sdk.version=11.37.2`,
  `surefireArgLine`. Parent = `mercury-services-commons:1.0` (unchanged project version on both sides).
- Consumes **root** properties `junit5.jupiter.version` (=`5.12.2` on develop) and `libs.dependency.version`
  (=`1.R.01.001` on develop). **Both are MISSING on the feature branch root pom** → they must be preserved
  during the `pom.xml` conflict resolution (see §5), otherwise the new module fails to build.
- Its version is governed by `libs.dependency.version`, independent of the feature branch's
  `dependency.version=1.0.26-SNAPSHOT`, so there is no version-scheme clash.

## 5. Conflict analysis — only 2 files conflict

Files changed on **both** sides of the merge base (the only rebase conflict candidates):

### 5.1 `pom.xml` (root) — **CONFLICT, must resolve as a UNION**

| Keep from `develop` | Keep from feature |
|---------------------|-------------------|
| `<module>libs/wtg-federation</module>` | `<module>dynamo-integration-test</module>` |
| `<libs.dependency.version>1.R.01.001</libs.dependency.version>` | `dependency.version = 1.0.26-SNAPSHOT` (→ bump, see §8) |
| `<junit5.jupiter.version>5.12.2</junit5.jupiter.version>` | Feature's property/BOM changes, AWS 1.x removals |
| `cloud-sdk-aws`, `cloud-sdk-api` modules | (already present on both) |

**Failure mode to avoid:** naively taking the feature ("ours" during rebase replay) side would drop
`junit5.jupiter.version`, `libs.dependency.version`, and the `libs/wtg-federation` module → the new module
would not resolve/build. Resolve to the **union** above.

### 5.2 `README.md` — **CONFLICT (low risk)**

Both sides edited the changelog/module list. Merge textually: keep the feature branch's cloud-sdk /
`1.0.26-SNAPSHOT` changelog **and** add the S2ST / `libs/wtg-federation` entry from develop.

### 5.3 Everything else — clean

The other **80** develop-side files (all of `libs/wtg-federation/**` and `build_libs_deploy.sh`) do not
exist on the feature branch and apply without conflict.

> Rebase mechanics: conflicts surface on the first replayed feature commit(s) that touch `pom.xml` /
> `README.md`. Expect 1–2 stop points, same character as Rebase #2.

## 6. Confirmation 1 — impact on the four library modules

**cloud-sdk-api, cloud-sdk-aws, commons, dynamo-integration-test: no functional change from the incoming
develop commits.** The net incoming diff touches **none** of their sources. The only additions are an
isolated sibling module (`libs/wtg-federation`) plus root-pom/README/deploy-script edits.

✅ Provided the `pom.xml` union in §5.1 is applied, these four modules build and behave exactly as they do
today on the feature branch. Validation gate: `mvn clean install` (baseline Rebase #2 = 2 003 tests) plus
the DynamoDB Local integration tests must pass post-rebase.

⚠️ Caveat: the rebase does **not** add the OWASP/Jackson pins (§3), so it does **not** improve the
vulnerability posture of these modules. If closing those CVEs is a goal, it is a **separate** change.

## 7. Confirmation 2 — impact on mercury-services apps (auth, network, registration, tx-tracking, booking, visibility, booking-bridge, webbl)

- Apps consume `commons` + `cloud-sdk-api` (22 refs) + `cloud-sdk-aws` (21) + `dynamo-integration-test`
  (16) via `mercury.commons.version` / `mercury.cloudsdk.version = 1.0.26-SNAPSHOT`.
- Incoming develop changes make **no source change** to any consumed module → rebuilt artifacts are
  **behaviorally identical**. Upgrading apps to the post-rebase version is a **version-string change only**.
- `libs/wtg-federation` (`wtg-federation-framework`) is a **standalone** artifact and is **not referenced**
  by any mercury-services pom (verified) → no new transitive dependency reaches the apps.

✅ Once the feature branch is re-published, the eight apps upgrade safely with no API/behavioral break,
assuming the `pom.xml` union is applied and the full build + integration tests pass.

⚠️ Same caveat as §6: apps gain **no** OWASP/Jackson remediation from this rebase.

## 8. Recommended rebase procedure (NOT executed — for review)

1. `git fetch origin --prune` (done) and fast-forward local `develop` (8 behind).
2. Create a fresh backup: `git branch backup/feature-ION-12310-pre-rebase-3 feature/ION-12310-commons-cloudsdk-refactoring`.
3. `git rebase origin/develop` (or first trial in an isolated `git worktree` to rehearse conflicts).
4. Resolve the two conflicts per §5 (union for `pom.xml`, textual merge for `README.md`).
5. Version: bump `dependency.version` to a new SNAPSHOT (e.g. `1.0.27-SNAPSHOT`) so consumers can pick up
   the rebased line deterministically; align `README.md` changelog.
6. Full validation: `mvn clean install` + DynamoDB Local integration tests (`mvn verify`). Expect ≥ 2 003
   unit tests green plus the new `libs/wtg-federation` tests (~35).
7. Force-push + update PR; record result and backup ref in the session.

## 9. Concerns & recommendations (summary)

1. **🔴 OWASP/Jackson fixes are missing on `develop` (regression via PR #42).** The rebase will **not**
   close those CVEs. Recommend: raise a ticket to re-apply ION-16159 on `develop`, then either re-rebase or
   cherry-pick the httpcore/Jackson/DW-5.0.2/handlebars pins onto the feature branch explicitly. **Do not
   assume this rebase remediates the vulnerability.**
2. **Root `pom.xml` union is mandatory** (§5.1) — the new module needs `junit5.jupiter.version` and
   `libs.dependency.version`, which are absent on the feature branch.
3. **Scope of incoming change is a whole new framework module** (S2ST, ~5.5k LOC). It is isolated, but the
   feature branch build/CI time and reactor grow; confirm the team wants `libs/wtg-federation` on this
   branch now (vs. deferring until the feature merges to develop).
4. **Version bump** required so the eight production apps consume a distinct artifact (§8.5).
5. **Docs are intentionally untracked.** `cloud-sdk-api/docs/` is git-ignored (`.gitignore:17 docs/`); this
   file and all prior rebase docs live on disk only and are **not** committed — do not force-add them.

## 10. Verification commands used (evidence)

```
git merge-base feature/ION-12310-commons-cloudsdk-refactoring origin/develop        # 0aa4a06
git rev-list --count feature/…..origin/develop                                       # 8 incoming
git rev-list --count origin/develop..feature/…                                       # 39 to replay
git diff --stat 0aa4a06 origin/develop                                               # 82 files, S2ST only
git diff 2745d3a^1 2745d3a -- pom.xml commons/pom.xml                                 # OWASP revert proof
git show origin/develop:pom.xml | grep dropwizard/jackson/handlebars                  # 5.0.1 / 2.21.0 / 4.3.1
git show origin/develop:commons/pom.xml | grep httpcore                              # no OWASP pins
# conflict candidates = README.md, pom.xml (intersection of both-side changes)

# --- revert mechanism (§3.1) ---
git merge-base 6db8b14 e9bce53                                                       # e9bce53 (S2ST built on top of ION-16159)
git log --oneline fac9edb -3                                                         # fac9edb parent = 1625bd0 (ION-16159 merge)
git show fac9edb -- commons/pom.xml                                                  # blob 91686b9->a096fa1 = restores pre-fix file

# --- ION-16159 pin/exclusion compatibility proof (§12) ---
git worktree add --detach <tmp> e9bce53
mvn -pl commons dependency:tree -Dincludes=org.apache.httpcomponents:*,org.apache.httpcomponents.core5:*,\
  org.apache.httpcomponents.client5:*,io.searchbox:*,vc.inreach.aws:*                # BUILD SUCCESS; 4.4.16/4.5.14/5.4.3
git worktree remove <tmp> --force
```

**App-level end-to-end proof (§12.1)** — install pinned `commons`, resolve each app, then revert:
```
# (apply ION-16159 httpcomponents pins to feature commons/pom.xml + 3 root props)
mvn -pl commons install -DskipTests                                                  # pinned commons -> local .m2
cd ../mercury-services/booking      && mvn dependency:tree -Dincludes=org.apache.httpcomponents:*,…,io.searchbox:*,vc.inreach.aws:*
cd ../mercury-services/webbl        && mvn dependency:tree -Dincludes=…              # httpcore(-nio) 4.4.16, httpclient 4.5.14, httpcore5 5.4.3
cd ../mercury-services/tx-tracking  && mvn dependency:tree -Dincludes=…
cd ../mercury-services/visibility   && mvn dependency:tree -Dincludes=…              # own-jest 6.3.1 modules keep httpcore-nio 4.4.6
git checkout -- pom.xml commons/pom.xml && mvn -pl commons install -DskipTests       # revert + restore pristine .m2
```

---

## 11. ION-16159 explained in detail — the HttpComponents pinning & exclusions

> This section documents what ION-16159 (`e9bce53`, PR #43) actually changed, so the fix can be reinstated
> confidently. It currently exists **nowhere** on `develop` HEAD or the feature branch (reverted per §3.1).

### 11.1 Why it was needed

OWASP dependency-check flagged **HIGH** vulnerabilities in Apache HttpComponents artifacts that reach
`commons` **transitively** (nobody declared them directly at a safe version):

| Artifact (line) | Pulled by | Version before | CVE / issue | Safe target |
|-----------------|-----------|----------------|-------------|-------------|
| `core5:httpcore5` | `dropwizard-client` → `metrics-httpclient5`; DW BOM manages **5.4.2** | 5.4 / 5.4.2 | **CVE-2026-54399** — HTTP/1.1 header memory-exhaustion DoS (≤ 5.4.2) | **5.4.3** |
| `core5:httpcore5-h2` | `client5:httpclient5:5.4.4` | 5.3.4 | HTTP/2 hardening; aligned with `httpcore5` 5.4.x (related to CVE-2025-27820 line fixed in 5.4.3) | **5.4.3** |
| `httpcomponents:httpcore` (4.x) | `vc.inreach.aws:aws-signing-request-interceptor:0.0.22` | 4.4.1 | Legacy 4.x — roll to final patched release | **4.4.16** |
| `httpcomponents:httpcore-nio` (4.x) | `io.searchbox:jest:5.3.3` (via `httpasyncclient`) | 4.4.6 | Legacy 4.x — roll to final patched release | **4.4.16** |
| `httpcomponents:httpclient` (4.x) | `io.searchbox:jest:5.3.3` | 4.5.3 | **CVE-2020-13956** (URI parsing, < 4.5.13) | **4.5.14** |

`4.4.16` / `4.5.14` are the **final releases** of the legacy 4.4.x / 4.5.x lines (all published fixes for
that line); `5.4.3` is the current 5.x patch that closes CVE-2026-54399 / CVE-2025-27820.

### 11.2 What it changed (three coordinated parts)

**(a) Root `pom.xml` — three version properties:**
```xml
<httpcore5.version>5.4.3</httpcore5.version>
<httpcomponents4.core.version>4.4.16</httpcomponents4.core.version>
<httpcomponents4.client.version>4.5.14</httpcomponents4.client.version>
```

**(b) `commons/pom.xml` — a *module-level* `<dependencyManagement>`** pinning `httpcore5`, `httpcore5-h2`
(5.4.3) and `httpcore`, `httpcore-nio` (4.4.16), `httpclient` (4.5.14).
*Why module-level and not the parent:* the Dropwizard BOM is imported in the parent POM and manages
`httpcore5` at 5.4.2. A module's own `<dependencyManagement>` takes precedence over BOMs imported by its
parent, and — critically — with **`flattenDependencyMode=all`** it is these managed versions that get
written into the **published flattened `commons` POM** that mercury-services apps consume. Pinning only in
the parent would let the BOM's 5.4.2 win in the flattened output.

**(c) `commons/pom.xml` — targeted `<exclusions>` + direct re-declarations** so the vulnerable transitives
are physically removed and the safe versions win conflict resolution and appear in the flattened POM:

| On dependency | Excluded | Re-declared as direct dep |
|---------------|----------|---------------------------|
| `dropwizard-client` | `core5:httpcore5`, `core5:httpcore5-h2` | `httpcore5` 5.4.3, `httpcore5-h2` 5.4.3 |
| `client5:httpclient5:5.4.4` | `core5:httpcore5-h2` (pulls 5.3.4) | (covered by the two above) |
| `io.searchbox:jest` | `httpcomponents:httpcore`, `httpcore-nio`, `httpclient` | `httpcore` 4.4.16, `httpcore-nio` 4.4.16, `httpclient` 4.5.14 |
| `vc.inreach.aws:aws-signing-request-interceptor` | `httpcomponents:httpcore`, `httpclient` | (same 4.x direct deps above) |

**Design pattern:** *exclude-then-re-declare-at-pinned-version*. The exclusions drop the old vulnerable
transitives; the direct declarations guarantee the safe versions are present (so nothing that jest /
aws-signing / dropwizard-client needs at runtime goes missing) **and** land in the flattened POM.

### 11.3 What it did **not** touch

- **`httpasyncclient` (4.1.3)** — not excluded/pinned; jest still gets it (it is the async transport jest
  needs). Its transitive `httpcore-nio`/`httpcore` are overridden by the pinned 4.4.16 direct deps.
- No source/API changes; purely dependency hygiene. (ION-16159 also bumped DW 5.0.1→5.0.2 / Jackson
  2.21.0→2.21.4 / handlebars 4.3.1→4.5.3 — separate from the HttpComponents work and also reverted.)

---

## 12. Compatibility review — `io.searchbox:jest` and `vc.inreach.aws:aws-signing-request-interceptor`

**Question:** do the pinned `dependencyManagement` versions + exclusions break jest or aws-signing (still
used to call Elasticsearch and to AWS-sign Elastic API requests, even after the AWS SDK v2 migration)?

**Answer: No — verified compatible.** Proof by actual `dependency:tree` in an isolated worktree at
`e9bce53` (pins applied), `mvn -pl commons dependency:tree` → **BUILD SUCCESS**:

| Artifact | Feature branch (no pins) | With ION-16159 pins | Verdict |
|----------|--------------------------|---------------------|---------|
| `client5:httpclient5` | 5.4.4 | 5.4.4 | unchanged |
| `core5:httpcore5` | 5.4 | **5.4.3** | ✅ patch-up, same 5.4 line |
| `core5:httpcore5-h2` | 5.3.4 | **5.4.3** | ✅ aligned with core5 |
| `io.searchbox:jest` | 5.3.3 | 5.3.3 | unchanged |
| `io.searchbox:jest-common` | 5.3.3 | 5.3.3 | ✅ retained |
| `httpcomponents:httpasyncclient` | 4.1.3 | 4.1.3 | ✅ retained (not touched) |
| `httpcomponents:httpcore-nio` | 4.4.6 (via jest) | **4.4.16** (direct) | ✅ patch-up, same 4.4 line |
| `httpcomponents:httpclient` | 4.5.3 (via jest) | **4.5.14** (direct) | ✅ patch-up, same 4.5 line |
| `httpcomponents:httpcore` | 4.4.1 (via aws-signing) | **4.4.16** (direct) | ✅ patch-up, same 4.4 line |
| `vc.inreach.aws:aws-signing-request-interceptor` | 0.0.22 | 0.0.22 | ✅ retained |

**Why it is safe:**
1. Every pin is a **later patch of the same minor line** the consumer already used (jest 5.3.3 → 4.4.x /
   4.5.x; aws-signing 0.0.22 → 4.4.x). Apache HttpComponents guarantees binary/API compatibility **within**
   a minor line, so `4.4.6→4.4.16`, `4.5.3→4.5.14`, `5.4→5.4.3` are drop-in.
2. The **exclude-then-re-declare** pattern removes only the *duplicate* vulnerable copies and puts back the
   exact artifacts jest/aws-signing need — the tree shows `jest-common`, `httpasyncclient`, `httpcore-nio`,
   `httpclient`, `httpcore` all still present. **Nothing is dropped.**
3. `httpasyncclient` (jest's async transport) is left at 4.1.3; its required `httpcore-nio`/`httpcore` 4.4.x
   are satisfied by the pinned 4.4.16.
4. The 5.x line (`httpcore5`, `httpclient5`) is a **separate groupId** (`…core5`/`…client5`) used only by
   Dropwizard's client — it does not intersect jest/aws-signing (4.x), so pinning one cannot affect the
   other.
5. ION-16159 was **merged green** (PR #43) before being accidentally reverted — independent evidence the
   build/tests passed with these pins.

### 12.1 Impact on the consuming apps — **empirically verified end-to-end**

To answer this conclusively I installed a **pinned `commons`** (ION-16159 HttpComponents changes applied to
the feature branch, `mvn -pl commons install`) into the local repo and re-resolved each app's real
dependency tree, then reverted and reinstalled the pristine `commons`. Results (**before → after** the pins):

**Apps that consume jest/aws-signing *via* `commons` — fully remediated:**

| App / module | jest | aws-signing | httpcore | httpcore-nio | httpclient | httpcore5 | httpcore5-h2 |
|--------------|------|-------------|----------|--------------|------------|-----------|--------------|
| **booking** | 5.3.3 (from commons) | 0.0.22 | 4.4.1 → **4.4.16** | 4.4.6 → **4.4.16** | 4.5.14 | 5.4 → **5.4.3** | 5.3.4 → **5.4.3** |
| **webbl** | 5.3.3 (from commons) | 0.0.22 | 4.4.1 → **4.4.16** | 4.4.6 → **4.4.16** | 4.5.14 | 5.4 → **5.4.3** | 5.3.4 → **5.4.3** |
| **tx-tracking** | 5.3.3 (from commons) | 0.0.22 | 4.4.13 → **4.4.16** | 4.4.6 → **4.4.16** | 4.5.13 → **4.5.14** | 5.4 → **5.4.3** | 5.3.4 → **5.4.3** |
| **visibility-commons** | 5.3.3 (from commons) | 0.0.22 | 4.4.1 → **4.4.16** | 4.4.6 → **4.4.16** | 4.5.14 | 5.4 → **5.4.3** | 5.3.4 → **5.4.3** |

`jest`, `jest-common`, `httpasyncclient` and `aws-signing-request-interceptor` all **resolved and were
retained** in every tree — **`BUILD SUCCESS`**, nothing dropped. This directly confirms the legacy
`io.searchbox:jest` ES client and the legacy `vc.inreach.aws` request signer **continue to work**.

**Apps that declare their *own* jest directly — functional but a nuance on `httpcore-nio`:**

Several `visibility` modules (`visibility-inbound`, `-wm-inbound-processor`, `-outbound`, `-pending`,
`-s3-archiver`, `-pending-start`) declare **`io.searchbox:jest 6.3.1` directly**. Post-pin resolution:

| Artifact | Resolved | Note |
|----------|----------|------|
| `jest` | **6.3.1** (own) | works |
| `aws-signing-request-interceptor` | 0.0.22 | works |
| `httpcore` | **4.4.16** | commons pin wins |
| `httpclient` | **4.5.14** | commons pin wins |
| `httpcore5` / `httpcore5-h2` | **5.4.3 / 5.4.3** | commons pin wins |
| `httpcore-nio` | **4.4.6** (jest 6.3.1's own transitive) | ⚠️ commons pin **does not** win here |

Because jest 6.3.1 is a **direct** dependency of the module, its transitive `httpcore-nio 4.4.6` sits at the
**same depth** as the `commons`-provided `httpcore-nio 4.4.16`, and Maven's *nearest-wins* mediation keeps
jest's `4.4.6`. (`visibility-matcher` similarly resolves `httpcore-nio 4.4.15` from its RHLC stack.)

**Functional verdict (the actual question): ✅ YES — proven.** jest **5.3.3 and 6.3.1** and
`aws-signing 0.0.22` resolve and function in **every** app/module. Every `httpcore-nio` value that appears
(`4.4.6`, `4.4.15`, `4.4.16`) is the **same 4.4.x minor line**, binary-compatible with both jest versions and
with `httpasyncclient` — so the pins **cannot break** the legacy jest or aws-signing usage anywhere.

**Security verdict (secondary): mostly remediated, one residual.** Everything routed through `commons`
(booking, webbl, tx-tracking, visibility-commons) is fully upgraded to safe versions. The `visibility`
modules that declare **their own jest 6.3.1** keep `httpcore-nio 4.4.6`; if that artifact must also be raised,
it is an **app-side** fix (bump their `jest`, or add `httpcore-nio` to that module's `dependencyManagement` /
a jest exclusion) — this is **independent of ION-16159**, which correctly hardens everything it owns.

### 12.2 Residual / follow-ups

- **`visibility` modules declaring their own `jest 6.3.1`** retain `httpcore-nio 4.4.6` (nearest-wins tie).
  If OWASP flags 4.4.6, pin `httpcore-nio` in those modules (or exclude it from their direct jest). Not a
  regression from ION-16159 — those modules already resolve 4.4.6 today.
- **`httpasyncclient`** is not pinned by ION-16159 (apps resolve 4.1.3–4.1.5). No CVE flagged in scope;
  consider pinning to 4.1.5 for completeness.
- When ION-16159 is reinstated on the feature branch, re-run the per-app `dependency:tree` (commands in §10)
  to reconfirm — the results above were produced with a locally-installed pinned `commons` and then reverted.
- Reinstating ION-16159's **HttpComponents** hardening is independent of its DW-5.0.2 / Jackson-2.21.4 bump;
  either can be applied on its own.
