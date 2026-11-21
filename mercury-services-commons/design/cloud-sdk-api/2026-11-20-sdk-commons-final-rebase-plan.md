# SDK commons ⇄ `develop`: sync, PR and final merge plan

**Date:** 2026-11-20 · **Status:** plan, not yet run · **Branch:** `feature/ION-12310-commons-cloudsdk-refactoring`
**Background:** [2026-11-16-sdk-commons-vs-develop-rebase.md](./2026-11-16-sdk-commons-vs-develop-rebase.md) has the full conflict analysis and simulation. [2026-11-20-commons-github-migration.md](./2026-11-20-commons-github-migration.md) covers today's move to GitHub.
**Not committed:** `cloud-sdk-api/docs/` is git-ignored.

---

## 1. The big picture

```text
                      today (Phase 1)                         later (Phase 4)
develop:  ──8c6fcef──●─●─●─●─●─●──f15b1e1──────────────────────────────────────●  final PR merged
                │                      \                                      ╱
feature:        └──95 commits──aa52175──M── 1.0.40 ── (more work / syncs) ───┘
                                        ↑                 ↑
                              merge develop INTO     Phase 2: draft PR feature → develop
                              feature (WI… commit)   Phase 3: repeat the sync as develop moves
```

| Phase | What | When |
|---|---|---|
| **1** | Merge `develop` **into** the feature branch, release **1.0.40-SNAPSHOT** | now |
| **2** | Open a **draft** GitHub PR: feature → `develop` (replaces Bitbucket PR #29) | right after Phase 1 |
| **3** | Clients bump to the SDK line. Repeat the Phase 1 sync whenever `develop` moves | ongoing |
| **4** | All clients migrated → final sync, PR ready, approval + `PR_BUILD`, **merge feature into `develop`** | at the end |

**The rule:** nothing that works on the feature branch today may break.
- appianway uses **1.0.39-SNAPSHOT**. The upgraded mercury-services modules use **1.0.38-SNAPSHOT**. Neither version is ever republished.
- oceanschedules (still on AWS SDK 1) and bill-of-lading are on develop's `1.R.01.0xx` line, so nothing here affects them.

---

## 2. What `develop` brings and what we keep

`develop` has 6 commits the feature branch doesn't: PR #56 (CSP filter) and PR #58 (SDK1 Xray fixes, Anand N S).

| develop change | Git conflict? | We keep | Why |
|---|---|---|---|
| **Deletes `CryptoLib`, `Encryptor` + tests**, removes `spring-security-crypto` | **no, silent** | **the classes, and the dependency marked `optional` (4.2.3)**, exactly as in 1.0.38/1.0.39 | auth (21 files) and network user/subscriptions (4 files) still use them on mercury-services `develop` (`0f45e3b`, checked 2026-11-20). network already declares crypto 6.4.4 itself, as 1.0.38 expects |
| CSP filter with `form-action …` | yes | the **feature** string (no `form-action`) | what auth runs today. Until the CSP owner decides |
| Jetty 12.1.13 | yes | **12.1.14** | develop's would be a downgrade |
| Jackson 2.21.8 | yes (comment only) | 2.21.8 | the same on both sides |
| MySQL `com.mysql:mysql-connector-j:8.4.0` | **no, silent** | **take it** | CVE fix, build-compatible. Production traffic goes through `aws-mysql-jdbc`'s own shaded driver. Old-name exclusions in appianway `shared`, watermill-commons, tx-tracking and visibility-commons go stale; update them when each app bumps |
| `dependency.version` `1.R.01.030` | yes | **1.0.40-SNAPSHOT** | 1.0.39 is published and in use |
| README notes | yes | hand-merge | — |

---

## 3. Why we merge (and never rebase)

| | Merge `develop` into feature ✅ | Rebase onto `develop` ❌ |
|---|---|---|
| New commits pushed | **1** (`WI01124532 …`) | 91 rewritten |
| GitHub `COMMIT_CHECK` (`^WI\d+…` on all branches except `develop`/`master`) | passes | **64 fail** (the old `ION-12310: …` and other authors' messages) → push rejected |
| Push | normal | force |
| Existing commit ids (`c353706` = 1.0.38, `aa52175` = 1.0.39) | unchanged | all change |
| Files at the end | identical | identical |

> ⛔ **Correction (2026-11-20, from the actual push): the merge is blocked as well.** On a branch **update**, `COMMIT_CHECK` checks **every commit being added to the branch**, including commits that already exist on `develop`. It isn't limited to commits new to the repository. Pushing the merge (`aa52175..f661c95`, 7 commits) was rejected with `GH013`, because develop's two Bitbucket PR merge commits `f15b1e1` (*"Pull request #58: …"*) and `b16ccd6` (*"Pull request #56: …"*) don't start with `WI`. (Creating a new branch, e.g. the backup branch, was accepted.) So **any** sync from `develop` into the feature branch, by merge or rebase, needs a ruleset change or bypass from a repo admin. See §3A.

**The final PR is not affected.** It merges into `develop`, which `COMMIT_CHECK` doesn't cover. `develop` has `PR_CHECK` instead (1 approval, `PR_BUILD`, Copilot review). The 64 old messages matter only if they are rewritten and pushed to the feature branch again, which is exactly what a rebase does.

**Never use GitHub's "Update branch" button.** Its merge message (`Merge branch 'develop' into …`) has no `WI` prefix, so GitHub rejects it. It would also skip the crypto restore and the checks.

### 3A. Status of Phase 1 (2026-11-20): merged and verified locally, push blocked

| Item | Result |
|---|---|
| Merge commit | `f661c95` (parents `aa52175`, `f15b1e1`), **local only**, parked on branch `merge/develop-sync-2026-11-20`. The feature branch was reset to `aa52175` (= GitHub) so normal work and pushes continue. Admin request: `2026-11-20-commons-commit-check-exception-request.md` |
| How it was parked (2026-11-20) | `git branch merge/develop-sync-2026-11-20 f661c95` (keep the merge on a local branch), then `git reset --hard origin/feature/ION-12310-commons-cloudsdk-refactoring` (feature back to `aa52175`; working tree was clean). Checked: `git rev-list --left-right --count 'HEAD...@{u}'` → `0 0`; `merge/develop-sync-2026-11-20` has no upstream (local only, don't push it yet) |
| Branch states after parking | GitHub feature = local feature = `aa52175` (1.0.39-SNAPSHOT); GitHub backup `backup/feature-ION-12310-pre-develop-merge-2026-11-20` = `aa52175`; local `merge/develop-sync-2026-11-20` = `f661c95` (1.0.40-SNAPSHOT); `~/.m2` has a local, unpublished 1.0.40 build from `f661c95` |
| When the exception is granted | feature unchanged since: `git merge --ff-only merge/develop-sync-2026-11-20`, then push. Feature moved on: `git merge --no-ff merge/develop-sync-2026-11-20` (one more `WI01124532 …` merge commit; resolve only new conflicts), re-run the §4 Step 5 checks, then push. Bump the version if 1.0.40 is already taken |
| Git checks | only `pom.xml`, `commons/pom.xml`, `README.md` changed vs the backup; no `.java` change; `CryptoLib`/`Encryptor` present |
| commons build | rehearsal `mvn clean verify`: all 10 modules green, 0 test failures (commons 951). `mvn clean install -DskipTests` on the same commit put 1.0.40 in `~/.m2` |
| auth vs 1.0.40 | green: 2,540 unit + 190 IT tests. A first run had 60 errors from missing local AWS credentials; the same tests error on 1.0.38 without credentials and pass on both with them |
| network user/subscriptions vs 1.0.40 | green: all 8 modules built |
| appianway vs 1.0.40 | all 26 modules green. Notes: `S3PublishServiceTest.testGetFullS3Path_ShouldReturnPathWithCurrentDate` fails after 19:00 EST whatever the commons version (code uses the UTC date, the test uses local time), so it was run with `-Duser.timezone=UTC`. The bill-of-lading consumers need `-Daether.enhancedLocalRepository.trackingFilename=_any.repositories` to resolve `dynamo-client:1.0` offline. `shared` now resolves `com.mysql:mysql-connector-j:8.4.0` (stale exclusion, §6) |
| Push | **rejected (GH013)**: `f15b1e1`, `b16ccd6` violate `COMMIT_CHECK` |
| Publish | **don't run `Mercury_Commons_Publish` yet**: 1.0.40 isn't on GitHub |

**Ways forward (need a repo admin, user `ArijitKunduWTG` has write, not admin):**

| Option | What | Effect |
|---|---|---|
| **A (recommended; requested 2026-11-20)** | Admin **excludes `feature/ION-12310-commons-cloudsdk-refactoring` from `COMMIT_CHECK`** (preferred), or adds a bypass for you, then we push `f661c95` | the plan works as written. With the exclude, future syncs need nothing new; a bypass would have to be granted again for each sync |
| B | Admin widens the pattern to also accept develop's merge messages, e.g. `^(WI\d+(?:\s*[:\-]\s*\|\s+).+\|Pull request #\d+: .+\|Merge pull request #\d+ .+)` | fixes all syncs permanently, but weakens the rule for everyone |
| C | `git merge --squash origin/develop`, one `WI…` commit, no admin | pushes today, but git doesn't record develop as merged: **the next sync re-applies the crypto deletion silently**, and the final PR would conflict or lose the restore. Not recommended |
| D | Do nothing until the final PR (no syncs) | feature stays on 1.0.39 content; the final PR carries all the conflicts |

---

## 4. Phase 1: merge `develop` into the feature branch

PowerShell, in `C:\Users\arijit.kundu\projects\mercury-services-commons`. Close IntelliJ and stop any Maven build first.

### Step 1: pre-flight

```powershell
git switch feature/ION-12310-commons-cloudsdk-refactoring
git status -sb                                   # clean
git fetch origin
git rev-parse --short origin/develop              # f15b1e1. Anything else → STOP, develop moved: re-check §2
git rev-list --left-right --count 'HEAD...@{u}'   # 0 0  (keep the quotes in PowerShell)
git config user.email                             # the wisetechglobal address
```

### Step 2: backup

```powershell
$bk = "C:\Users\arijit.kundu\projects\backups\mercury-services-commons-2026-11-20-pre-develop-merge"
New-Item -ItemType Directory -Force $bk | Out-Null
git branch backup/feature-ION-12310-pre-develop-merge-2026-11-20
git push origin backup/feature-ION-12310-pre-develop-merge-2026-11-20
git bundle create "$bk\feature-pre-merge.bundle" feature/ION-12310-commons-cloudsdk-refactoring origin/develop
git bundle verify "$bk\feature-pre-merge.bundle"
```

### Step 3: rehearse in a throwaway worktree

```powershell
$wt = "C:\Users\arijit.kundu\projects\mercury-services-commons.worktrees\merge-rehearsal"
git -c core.longpaths=true worktree add --detach $wt HEAD
cd $wt
#   run Step 4 and the checks in Step 5 here, using mvn clean verify (not install)
cd C:\Users\arijit.kundu\projects\mercury-services-commons
git -c core.longpaths=true worktree remove --force $wt; git worktree prune
```

Go on only if the rehearsal is green.

### Step 4: the merge

```powershell
# 4.1 start the merge, but don't commit yet
git merge --no-ff --no-commit origin/develop

# 4.2 undo develop's silent deletion of the crypto classes
git checkout HEAD -- `
  commons/src/main/java/com/inttra/mercury/security/CryptoLib.java `
  commons/src/main/java/com/inttra/mercury/security/Encryptor.java `
  commons/src/test/java/com/inttra/mercury/security/CryptoLibTest.java `
  commons/src/test/java/com/inttra/mercury/security/EncryptorTest.java

# 4.3 CSP filter: the feature version
git checkout --ours -- commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java
git add commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java
```

**4.4 Edit `pom.xml` and `commons/pom.xml` by hand**, following §2:
- `dependency.version` → `1.0.40-SNAPSHOT`
- `jetty.version` 12.1.14, Jackson 2.21.8
- keep `bucket4j.version` and `spring.sercurity.crypto.version` (4.2.3.RELEASE)
- keep the `optional` `spring-security-crypto` block
- leave the auto-merged MySQL 8.4.0 lines

**4.5 Edit `README.md` by hand:**
- add a `Commons v1.0.40-SNAPSHOT` note: develop PR #56/#58 merged, Jetty stays 12.1.14, **`CryptoLib`/`Encryptor` kept on the SDK line**, and exclusions should change to `com.mysql:mysql-connector-j`;
- keep develop's v1.R.01.029/030 sections, but with one CSP entry, not two.

```powershell
# 4.6 nothing left unresolved, then commit
Select-String -Path pom.xml,commons/pom.xml,README.md -Pattern '^(<<<<<<<|=======|>>>>>>>)'   # expect nothing
git add pom.xml commons/pom.xml README.md
git status                                        # no "unmerged" paths
git commit -m "WI01124532 ION-12310 merge develop (PR #56 CSP, PR #58 Xray) into the SDK line for 1.0.40-SNAPSHOT; keep CryptoLib/Encryptor and the feature CSP" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

| Command | What it does |
|---|---|
| `git merge --no-ff --no-commit origin/develop` | merges develop in but stops before committing, so the silent deletion can be undone inside the same merge commit. `--no-ff` = always a real merge commit |
| `git checkout HEAD -- FILES` | puts the files back exactly as they were before the merge (working tree and index) |
| `git checkout --ours -- FILE` | in a merge, *ours* = the feature branch, *theirs* = develop |
| `` ` `` at line end | PowerShell line continuation |
| `Select-String -Pattern '^(<<<<<<<\|=======\|>>>>>>>)'` | finds leftover conflict markers |
| `git commit -m A -m B` | A = subject (starts with `WI01124532`, passes `COMMIT_CHECK`), B = trailer paragraph. A normal commit, no workarounds |

### Step 5: checks (all must pass before pushing)

```powershell
$base = "backup/feature-ION-12310-pre-develop-merge-2026-11-20"
git diff --stat $base HEAD                 # only pom.xml, commons/pom.xml, README.md
git diff $base HEAD -- '*.java'            # empty
git ls-files commons/src/main/java/com/inttra/mercury/security/   # CryptoLib.java, Encryptor.java listed
git show --cc HEAD                         # review the hand resolutions
mvn clean install                          # every module green; puts 1.0.40 into ~/.m2
```

Then build the consumers against the local 1.0.40. This only overrides a property on the command line; their poms stay unchanged:

```powershell
cd C:\Users\arijit.kundu\projects\mercury-services\auth
mvn -o clean verify "-Dmercury.commons.version=1.0.40-SNAPSHOT"
cd ..\network
mvn -o clean verify "-Dmercury.commons.version=1.0.40-SNAPSHOT" -pl user,subscriptions -am
cd C:\Users\arijit.kundu\projects\appianway
mvn -o clean verify "-Dmercury.commons.version=1.0.40-SNAPSHOT"
```

| Piece | Meaning |
|---|---|
| `git diff --stat A B` | which files differ, with a count of changed lines |
| `-- '*.java'` | only Java files (the quotes stop the shell expanding `*`) |
| `git show --cc MERGE` | only the lines where the merge result differs from **both** sides, i.e. the hand resolutions |
| `-o` | Maven offline: uses exactly what's in `~/.m2` |
| `"-Dmercury.commons.version=…"` | overrides the pom property for this run only |

### Step 6: push and publish

```powershell
git push origin feature/ION-12310-commons-cloudsdk-refactoring    # normal push, no --force
```

Publish 1.0.40-SNAPSHOT through the usual deploy route, as was done for 1.0.39.

---

## 5. Phase 2: open the GitHub PR

Bitbucket PR #29 (same branch → `develop`) was not migrated. GitHub has no PRs for this repo, and Bitbucket is read-only. Save #29's comments and approvals if they need to be kept.

```powershell
gh pr create --base develop --head feature/ION-12310-commons-cloudsdk-refactoring --draft `
  --title "WI01124532 ION-12310 SDK commons: AWS SDK v2 / cloud-sdk refactoring" --body-file <description.md>
```

| Piece | Meaning |
|---|---|
| `--base` / `--head` | target / source branch |
| `--draft` | reviewable, but can't be merged until marked ready. That fits, because it must not merge before all clients are migrated |
| `--body-file` | description from a file. Link Bitbucket PR #29 for the earlier review history |

Opening it starts `PR_BUILD` (Jenkins) and the Copilot review.

> **Decision 2026-11-20: Phase 2 is optional and deferred.** A PR is required only for the final merge, because `develop` accepts changes only through PRs. `PR_BUILD` is posted by the shared Jenkins job **`DEV_GIT_PR`**, and only for PRs into `develop` (seen on mercury-services PR #8; appianway's sub-PRs into the feature branch have no checks). It has never run for this repo, and what it does for commons isn't known yet. **Before opening the PR, ask the Jenkins owner** what `DEV_GIT_PR` runs for mercury-services-commons, and confirm it only builds and tests, never publishes. Until then, Bitbucket PR #29 stays as the readable review record.
>
> **Publishing:** snapshots are published with the Jenkins job **`Mercury_Commons_Publish`** (1.0.39 on 2026-11-17). After the GitHub cut-over, **check that the job builds from GitHub, not Bitbucket.** Bitbucket is frozen at `aa52175`, so the job would build 1.0.39 again.

---

## 6. Phase 3: while clients migrate

**When an app bumps to 1.0.40 or later:**

| App | Change in its pom |
|---|---|
| appianway `shared`, watermill-commons | exclusion `mysql:mysql-connector-java` → `com.mysql:mysql-connector-j` |
| tx-tracking, visibility-commons | the same, for tidiness (harmless as it is) |
| auth, network/server | nothing in the pom. Run DB integration tests (driver 8.0.16 → 8.4.0) |

**When `develop` moves again:** repeat Phase 1, Steps 1–6.
- Use the next version each time it's published (1.0.41, 1.0.42, …).
- Later syncs **won't** delete the crypto classes again, because git counts that deletion as handled.
- If develop later edits the same files or pom settings, git stops on a conflict instead of applying anything silently. Resolve it with §2 in mind.

---

## 7. Phase 4: final merge into `develop`

When every client is on the SDK line:

1. **Agree the open points:**
   - the **crypto classes** with Anand N S (the PR #58 owner). The final merge puts them back on `develop`. Suggested path: `@Deprecated(forRemoval = true)`, move auth and network to Spring's `BCryptPasswordEncoder`/`Encryptors`, then remove them in a coordinated release;
   - the **CSP string** with Riya Chauhan / app-sec.
2. **Final sync:** Phase 1 once more, so the PR contains everything currently on `develop` and the Jenkins build runs against it.
3. **Mark the PR ready:** `gh pr ready <number>`.
4. **Get 1 approval and a green `PR_BUILD`.**
5. **Merge with "Create a merge commit".** Not squash, which would collapse the history into one commit. Not rebase, which would rewrite the commits. Start the message with `WI01124532` to keep the convention, even though `develop` doesn't check it:
   ```powershell
   gh pr merge <number> --merge --subject "WI01124532 Merge pull request #<number>: SDK commons AWS SDK v2 / cloud-sdk refactoring"
   ```

---

## 8. Rollback

| When | How |
|---|---|
| During the merge | `git merge --abort`: back to `aa52175`, clean |
| Committed, not pushed | `git reset --hard backup/feature-ION-12310-pre-develop-merge-2026-11-20` |
| Pushed | **fix forward:** correct it in a new `WI01124532 …` commit. Avoid `git revert -m 1 <merge>`: git would still count develop's 6 commits as merged, so the next sync wouldn't bring them back without a "revert of the revert" |
| 1.0.40 published but wrong | apps simply stay on 1.0.38/1.0.39 |
| Worst case | `git clone "$bk\feature-pre-merge.bundle"`, or the folder backup from the GitHub cut-over |

---

## 9. Decisions (defaults used above)

| # | Decision | Default |
|---|---|---|
| D1 | merge or rebase | **merge** (§3) |
| D2 | MySQL 8.4.0 | **take** it in 1.0.40 |
| D3 | `spring-security-crypto` | **4.2.3 optional, unchanged**. A move to 6.4.4 can be a separate later commit (network already runs the classes on 6.4.4) |
| D4 | CSP string | **feature** |
| D5 | version | **1.0.40-SNAPSHOT** |
