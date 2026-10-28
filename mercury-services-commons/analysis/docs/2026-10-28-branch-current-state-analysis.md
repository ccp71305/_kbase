# Branch Current-State Analysis — `feature/ION-12310-commons-cloudsdk-refactoring`

**Date:** 2026-10-28
**Author of analysis:** automated review (read-only; no code changes made)
**Scope:** Integrity of the local feature branch, changes pushed to the remote feature
branch since the last rebase, and changes pushed to remote `develop` (for future-rebase
planning).

> **Why this branch matters.** `feature/ION-12310-commons-cloudsdk-refactoring` is the
> **primary feature branch for the AWS SDK upgrade of `commons` / `cloud-sdk-*`**. The
> artifacts it produces are consumed by **all client applications** across the
> **mercury-services**, **appianway**, and **mft-s3-aqua-appia** workspaces. Any drift,
> forced history rewrite, or unexpected version bump here ripples into every downstream
> reactor, so branch integrity is tracked deliberately.

---

## 1. Executive summary

| Question | Answer |
|---|---|
| Uncommitted production files locally? | **No.** Working tree is clean (ignored `*.md` docs aside). |
| Local feature branch integrity | **Intact.** `HEAD = 1c45c00`, exactly the tip produced by the last rebase (see §4). 0 local-only commits. |
| Has the remote feature branch moved? | **Yes.** `origin/...` advanced `1c45c00 → fa90f7d`; local is **0 ahead / 8 behind**. |
| Can I safely pull the remote feature changes? | **Yes — clean fast-forward.** No divergence, no conflicts, no history rewrite. |
| Has remote `develop` moved since the last rebase? | **Yes.** `origin/develop` advanced `8c6fcef → b16ccd6` (**4 commits**); local `develop` is 0 ahead / 4 behind. |
| Future-rebase risk from `develop`? | **Low but non-trivial** — `develop` and this branch both add `ContentSecurityPolicyFilter` (WI01128840). See §5. |

**Bottom line:** the branch is healthy. Pulling the remote feature branch is a safe
fast-forward. No action is required today; this document captures the incoming `develop`
delta for when a future rebase is performed.

---

## 2. Local working-tree integrity

- **Current branch:** `feature/ION-12310-commons-cloudsdk-refactoring`
- **Working tree:** clean — nothing staged, nothing modified, no untracked **production**
  files. (Module `docs/**` markdown is git-ignored and out of scope by request.)
- **Local HEAD:** `1c45c005eabddc43d60aa5d88a288b1cd57bef16`
  - This is the **same commit** that the 2026-09-11 rebase document records as its final
    pushed state (`1c45c00` — *"ION-12310: pin commons dependency hygiene for 1.0.34"*).
    i.e. nothing new has been committed locally since that rebase.
- **Divergence vs remote:** `0 ahead / 8 behind` → **no local-only commits**, so the
  remote history layers cleanly on top of local with no merge.

---

## 3. Remote feature branch — what was pushed

`origin/feature/ION-12310-commons-cloudsdk-refactoring` moved from **`1c45c00` → `fa90f7d`**,
adding **8 commits** across **two merged pull requests**.

### 3.1 Incoming commits

| SHA | Author | Date | Subject |
|---|---|---|---|
| `fa90f7d` | Riya Chauhan | 2026-10-12 | **PR #57:** WI01128840 csp string changes |
| `fa11000` | Riya Chauhan | 2026-10-12 | WI01128840 csp string changes |
| `0110419` | Riya Chauhan | 2026-09-30 | WI01128840 content security policy filter class added |
| `2c82a05` | Riya Chauhan | 2026-09-30 | WI01128840 content security policy filter class added. |
| `3ae7c60` | Riya Chauhan | 2026-09-29 | WI01128840 CSP filter test case Green phase |
| `0240e74` | Riya Chauhan | 2026-09-29 | WI01128840 content security policy filter class added. |
| `61589e6` | Raghunandan Shastry | 2026-09-24 | **PR #55:** WI01127797-SDK2-T77433755-Sensitive-info-Disclosure-Registration |
| `ed07226` | Raghunandan Shastry | 2026-09-22 | WI01127797-SDK2-T77433755-Sensitive-info-Disclosure-Registration |

### 3.2 Incoming file changes (16 files, +740 / −2)

```
 README.md                                                              |   3 +
 pom.xml                                                                |  10 +-   (root)
 commons/pom.xml                                                        |   5 +
 commons/.../InttraServer.java                                          |   5 +
 commons/.../auth/AuthenticationFilter.java                             |   7 +-
 commons/.../auth/ContentSecurityPolicyFilter.java                      |  22 ++   (new)
 commons/.../config/ApplicationConfiguration.java                       |  12 +
 commons/.../ratelimit/RateLimitConfig.java                             |  31 ++   (new)
 commons/.../ratelimit/RateLimitDynamicFeature.java                     |  74 ++   (new)
 commons/.../ratelimit/RateLimitRequestFilter.java                      | 136 ++   (new)
 commons/.../ratelimit/RateLimited.java                                 |  13 ++   (new)
 commons/.../ratelimit/RateLimits.java                                  |   9 ++   (new)
 commons/.../auth/AuthenticationFilterTest.java                         | 121 ++   (new)
 commons/.../auth/ContentSecurityPolicyFilterTest.java                  |  41 ++   (new)
 commons/.../ratelimit/RateLimitDynamicFeatureTest.java                 |  96 ++   (new)
 commons/.../ratelimit/RateLimitRequestFilterTest.java                  | 157 ++   (new)
```

### 3.3 Functional content of the incoming changes

- **WI01127797 (PR #55) — Sensitive-info disclosure / Registration (SDK2):** touches
  `AuthenticationFilter` and brings in the bulk of the new **rate-limiting** subsystem
  under `com.inttra.mercury.ratelimit` (`@RateLimited` / `@RateLimits` annotations, a JAX-RS
  `DynamicFeature` + request filter, and config), wired through `InttraServer` and
  `ApplicationConfiguration`.
- **WI01128840 (PR #57) — Content Security Policy:** adds
  `ContentSecurityPolicyFilter` (a JAX-RS `ContainerResponseFilter` emitting a CSP header)
  with its test, plus a later "csp string changes" tweak to the policy string.

### 3.4 Build / dependency changes (feature branch)

| File | Change |
|---|---|
| root `pom.xml` | `dependency.version` **`1.0.34-SNAPSHOT` → `1.0.37-SNAPSHOT`** |
| root `pom.xml` | New property `bucket4j.version = 8.7.0`; new `dependencyManagement` entry `com.bucket4j:bucket4j-core` |
| `commons/pom.xml` | New direct dependency `com.bucket4j:bucket4j-core:${bucket4j.version}` (token-bucket engine backing `@RateLimited`) |

> **New third-party dependency** `com.bucket4j:bucket4j-core:8.7.0` now enters the
> `commons` compile classpath and therefore every downstream consumer. Worth a dependency
> /OWASP note on the next security pass, but out of scope for this read-only analysis.

> **Version continuity:** `1.0.34 → 1.0.37` (the `1.0.35` / `1.0.36` snapshots were
> consumed by the two PRs). This is the single source of truth all published modules
> inherit.

---

## 4. Relationship to the last rebase (2026-09-11)

Reference doc: [`docs/2026-09-11-sdk-commons-owasp-fix-rebase.md`](./2026-09-11-sdk-commons-owasp-fix-rebase.md)
(*"commons #1.0.34-SNAPSHOT"*).

Key facts carried forward from that rebase, still true today:

- The feature branch was **rebased onto `origin/develop = 8c6fcef`** and force-pushed
  (`--force-with-lease`), finishing at commit **`1c45c00`** (jackson direct-deps pin,
  httpclient5 held at `5.4.4`, jsoup removed). A safety tag
  `backup/pre-develop-rebase-2026-09-11` was created at the pre-rebase tip.
- **Today, local `HEAD` is still `1c45c00`** — confirming no local work has been layered on
  top since that rebase; all subsequent change arrived on the **remote** via PRs #55/#57.
- The **merge-base of the current branch and `origin/develop` is `8c6fcef`** — i.e. the
  exact `develop` tip the branch was last rebased onto. So the "new develop work since the
  last rebase" is precisely the §5 delta below.

---

## 5. Remote `develop` — incoming delta for future rebase

Local `develop` is **0 ahead / 4 behind** `origin/develop` (fetched, **not** merged).
`origin/develop` moved **`8c6fcef` → `b16ccd6`**.

### 5.1 Incoming `develop` commits

| SHA | Author | Date | Subject |
|---|---|---|---|
| `b16ccd6` | Riya Chauhan | 2026-09-29 | **PR #56:** WI01128840 content security policy filter class added. |
| `cb447a4` | Riya Chauhan | 2026-09-30 | WI01128840 content security policy filter class added. |
| `ce373b6` | Riya Chauhan | 2026-09-29 | WI01128840 CSP filter test case Green phase |
| `0c7ff23` | Riya Chauhan | 2026-09-29 | WI01128840 content security policy filter class added. |

### 5.2 Incoming `develop` file changes (4 files, +68 / −1)

```
 README.md                                               |  3 ++
 commons/.../auth/ContentSecurityPolicyFilter.java       | 23 ++   (new)
 commons/.../auth/ContentSecurityPolicyFilterTest.java   | 41 ++   (new)
 pom.xml                                                 |  2 +-   dependency.version 1.R.01.028 -> 1.R.01.029
```

> Note the **different version lineage** on `develop` (`1.R.01.xxx`) vs this feature branch
> (`1.0.xx-SNAPSHOT`). That is pre-existing and expected; it only matters that a future
> rebase must not drag `develop`'s `1.R.01.029` over the branch's `1.0.37-SNAPSHOT`
> (handle `pom.xml` / `README.md` conflicts deterministically, exactly as the 2026-09-11
> rebase did).

### 5.3 Future-rebase risk assessment — **CSP overlap**

The single meaningful thing `develop` gained since the last rebase is **WI01128840's
`ContentSecurityPolicyFilter`** — **the same feature this branch also added independently**
(via PR #57). Both branches now contain:

- `commons/.../auth/ContentSecurityPolicyFilter.java`
- `commons/.../auth/ContentSecurityPolicyFilterTest.java`

**They are not identical.** The test files match, but the filter's policy string differs —
the **feature branch is the newer intent**:

- `develop` (`b16ccd6`) CSP string **still contains** a `form-action` directive.
- This feature branch (PR #57, 2026-10-12, *"csp string changes"*) **intentionally removed**
  the `form-action` directive (and trimmed `font-src`).

```diff
# origin/develop  ->  origin/feature  (ContentSecurityPolicyFilter.java)
-        + "font-src 'self' data:; "
-        + "form-action 'self' e2open.com inttra.com *.inttra.com *.e2open.com wss://*.e2open.com;";
+        + "font-src 'self' data:;";
```

**Implication for the next `develop → feature` rebase:**

1. The CSP files will **conflict** (both sides add/modify the same new files). This is a
   *content* conflict, not a structural one.
2. **Resolve in favour of the feature branch's CSP string** (no `form-action`, trimmed
   `font-src`) — it is the later, deliberate change (PR #57, 2026-10-12) and supersedes
   `develop`'s earlier WI01128840 (PR #56, 2026-09-29).
3. Everything else in the `develop` delta (`README.md`, root `pom.xml` version line) is the
   usual deterministic-resolution set already handled every rebase.

No other `develop` change touches the AWS-SDK-upgrade surface of this branch, so the rebase
blast radius is limited to the CSP file + the standard `pom.xml`/`README.md` lines.

---

## 6. Recommended next steps (not executed — analysis only)

1. **Feature branch:** `git pull --ff-only` (or `git merge --ff-only
   origin/feature/ION-12310-commons-cloudsdk-refactoring`) to take PRs #55/#57. Safe,
   non-destructive.
2. **Before downstream consumption:** note the new `bucket4j-core:8.7.0` transitive and the
   `1.0.37-SNAPSHOT` bump for the mercury-services / appianway / mft-s3-aqua-appia reactors.
3. **When a `develop` rebase is next required:** fast-forward local `develop` to
   `b16ccd6` first, then rebase; expect and resolve the CSP conflict per §5.3, and keep the
   branch's `1.0.x-SNAPSHOT` version line.

---

## 7. Appendix — commands used (with descriptions, syntax, output)

All commands below are **read-only** (plus `git fetch`, which only updates remote-tracking
refs and never changes the working tree or local branch pointers). No branch was pulled,
merged, rebased, or pushed.

### 7.1 Identify branch, check working-tree cleanliness, refresh remote refs

```powershell
git branch --show-current
git status
git fetch --all --prune
```

- `git branch --show-current` — prints only the checked-out branch name.
  **Output:** `feature/ION-12310-commons-cloudsdk-refactoring`
- `git status` — working-tree / index state vs upstream.
  **Output:** *"nothing to commit, working tree clean"* (before fetch it reported
  "up to date"; that only reflects the stale remote-tracking ref).
- `git fetch --all --prune` — downloads all remotes' refs and **prunes** deleted ones.
  `--all` = every configured remote; `--prune` = drop local remote-tracking refs that no
  longer exist upstream. Updates `origin/*` pointers **only**; never touches local
  branches or files.
  **Key output lines:**
  ```
  1c45c00..fa90f7d  feature/ION-12310-commons-cloudsdk-refactoring -> origin/feature/...
  8c6fcef..b16ccd6  develop    -> origin/develop
  ```
  (plus several brand-new `feature/WI0112xxxx-*` remote branches, unrelated to this task.)

### 7.2 Measure divergence (ahead / behind)

```powershell
git rev-list --left-right --count HEAD...origin/feature/ION-12310-commons-cloudsdk-refactoring
git rev-list --left-right --count develop...origin/develop
```

- `git rev-list --left-right --count A...B` — the **three-dot** form counts commits unique
  to each side of the symmetric difference. Output is two numbers: `<left-only>\t<right-only>`
  = `<ahead>\t<behind>` when `A = local`, `B = remote`.
  **Output (feature):** `0  8` → 0 ahead, 8 behind (clean fast-forward possible).
  **Output (develop):** `0  4` → 0 ahead, 4 behind.

### 7.3 List the incoming (and local-only) commits

```powershell
git --no-pager log --oneline --no-decorate HEAD..origin/feature/ION-12310-commons-cloudsdk-refactoring
git --no-pager log --oneline --no-decorate origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD   # local-only (empty)
git --no-pager log --oneline --no-decorate develop..origin/develop
# detailed form:
git --no-pager log --pretty=format:'%h | %an | %ad | %s' --date=short HEAD..origin/feature/ION-12310-commons-cloudsdk-refactoring
git --no-pager log --pretty=format:'%h | %an | %ad | %s' --date=short develop..origin/develop
```

- `A..B` (**two-dot**) in `log` = commits reachable from `B` but not `A` — i.e. "what `B`
  has that `A` lacks". `HEAD..origin/...` therefore lists **incoming** commits; the reverse
  `origin/.....HEAD` lists **local-only** commits.
  **Output:** incoming = the 8 / 4 commits tabulated in §3.1 and §5.1; local-only = **empty**.
- `--no-pager` (global flag) prevents `git` from piping to a pager — essential for
  non-interactive capture. `--pretty=format:'...'` with `%h|%an|%ad|%s` prints
  short-SHA | author | date | subject; `--date=short` = `YYYY-MM-DD`.

### 7.4 Summarise changed files

```powershell
git --no-pager diff --stat HEAD..origin/feature/ION-12310-commons-cloudsdk-refactoring
git --no-pager diff --stat develop..origin/develop
```

- `git diff --stat A..B` — per-file change summary (insertions/deletions histogram) between
  the two commits. Used for the tables in §3.2 and §5.2. (`diff A..B` and `diff A B` are
  equivalent for two committish endpoints.)

### 7.5 Inspect the build/version-sensitive diffs

```powershell
git --no-pager diff HEAD..origin/feature/ION-12310-commons-cloudsdk-refactoring -- pom.xml commons/pom.xml
git --no-pager diff develop..origin/develop -- pom.xml
```

- Trailing `-- <paths>` restricts the diff to the named files. Confirmed the
  `dependency.version` bump (`1.0.34 → 1.0.37-SNAPSHOT`), the new `bucket4j` property +
  dependencyManagement/direct-dep, and develop's `1.R.01.028 → 1.R.01.029`.

### 7.6 Confirm commit identity and rebase base

```powershell
git rev-parse HEAD
git merge-base HEAD origin/develop
git merge-base develop origin/develop
```

- `git rev-parse HEAD` — full 40-char SHA of the current commit.
  **Output:** `1c45c005eabddc43d60aa5d88a288b1cd57bef16` (matches the last rebase's final
  commit `1c45c00`).
- `git merge-base A B` — the best common ancestor of `A` and `B`.
  **Output (both):** `8c6fcef…` — the `develop` tip this branch was last rebased onto,
  proving the §5 delta is exactly "develop since the last rebase".

### 7.7 Compare the overlapping CSP file across branches

```powershell
git --no-pager diff origin/develop:commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java \
                     origin/feature/ION-12310-commons-cloudsdk-refactoring:commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java
git --no-pager diff origin/develop:...ContentSecurityPolicyFilterTest.java \
                     origin/feature/...:...ContentSecurityPolicyFilterTest.java
```

- `git diff <rev>:<path> <rev>:<path>` — diffs the **same file as it exists in two different
  commits/branches** (the `rev:path` "blob" syntax), without checking anything out. Revealed
  that the feature branch's CSP string **drops `form-action`** vs develop (see §5.3); the
  test files are **identical** (empty diff).

### 7.8 Sync local feature branch to remote — fast-forward pull (2026-10-28, executed)

> Unlike §7.1–§7.7 (read-only), this step **does** advance the local branch pointer. It was
> run after confirming §1–§3: clean tree, 0 local-only commits, 0 ahead / 8 behind — the
> preconditions that make a fast-forward safe and non-destructive.

```powershell
git merge --ff-only origin/feature/ION-12310-commons-cloudsdk-refactoring
git status -sb
git rev-parse --short HEAD
```

- `git merge --ff-only <ref>` — advances the current branch to `<ref>` **only if it can be
  done as a pure fast-forward** (no new local commits to replay). `--ff-only` makes the
  command **refuse and abort** rather than create a merge commit if the history had diverged,
  so it is the safe way to "pull" here. Equivalent to `git pull --ff-only` given the remote
  ref was already fetched.
  **Output:**
  ```
  Updating 1c45c00..fa90f7d
  Fast-forward
   ... 16 files changed, 740 insertions(+), 2 deletions(-)
   create mode 100644 commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java
   create mode 100644 commons/src/main/java/com/inttra/mercury/ratelimit/RateLimitConfig.java
   ... (9 new files total)
  ```
- `git status -sb` — short, branch-aware status.
  **Output:** `## feature/ION-12310-commons-cloudsdk-refactoring...origin/feature/ION-12310-commons-cloudsdk-refactoring`
  (no `[ahead]`/`[behind]` marker → local is now **exactly even** with the remote).
- `git rev-parse --short HEAD` — confirm the new tip.
  **Output:** `fa90f7d` (was `1c45c00`).

**Post-state:** local `feature/ION-12310-commons-cloudsdk-refactoring` == `origin/...` at
`fa90f7d`. New commits can now be made and pushed with the normal
`git add → git commit → git push` flow — no force-push or rebase required.

---

*End of analysis. The only repository change performed was the fast-forward sync of the
local feature branch in §7.8 (`1c45c00 → fa90f7d`); all other steps were read-only.*
