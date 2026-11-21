# AppianWay — Bitbucket to GitHub migration (WI01124532 branch)

> **Date:** 2026-11-16
> **Scope:** what happened to the WI01124532 AWS SDK upgrade branch during the Bitbucket → GitHub migration, how GitHub access was set up, and what is still to do once the migration is finished.
> **Status:** migration **in progress**. Bitbucket is read-only. The branch was copied to GitHub as is, under its old name.
> **Plan:** once the migration is done, switch the local remote to GitHub, rename the branch locally, **push it as `feature/WI01124532-aws-sdk-upgrade` and set the upstream** (§4). The old branch name is deleted later.
>
> **Update 2026-11-17:** migration confirmed complete and verified (§6.1). §6 is the step-by-step cut-over runbook: backup, switch `origin` to GitHub, fix local branches that GitHub doesn't have, rename and push. Use §6 instead of §4.1–§4.3. **Decision change:** the old `WI01124532-aws-sdk-upgrade` branch on GitHub **stays**, so skip §4.4.

| | |
|---|---|
| Bitbucket (old) | `git.dev.e2open.com` → project `INT`, repo `appianway` (now **read-only**) |
| GitHub (new) | https://github.com/wtg-e2open/INTTRA.appianway (private, default branch `develop`) |
| Feature branch today | `WI01124532-aws-sdk-upgrade` at `fa3efede` (PR #80 merge, 2026-11-10) |
| Feature branch target name | `feature/WI01124532-aws-sdk-upgrade` |

---

## 1. Why rename the branch

- On origin, the other work-item branches already use the `feature/` prefix (`feature/WI01137019-fix-jfrog`, `feature/WI01137977-BK-OCMBE-WATERMILL-CONSUMER`, 14 `feature/...` branches in total). The earlier attempts at this upgrade did too (`feature/ION-12317-apway-aws-upgrade`, `feature/ION-16098-jetty-cve`).
- Nothing in the repo depends on the branch name:
  - The commit-msg hook and the Bitbucket check look only for the `WI01124532` prefix in commit messages.
  - No POM, CI file or script refers to the branch.
- At the time of the decision nothing else would be affected:
  - **No open PRs.** Sub-branch PRs #76, #78 and #80 are merged and their remote branches deleted. No PR from the feature branch to `develop` has been raised.
  - **No Jenkins CI** on this branch.

**Not renamed:**
- Sub-branch names (`WI01124532-aws-sdk-upgrade-pom`, `-shared-config`, `-shared-runtime`) and the planned `WI01124532-aws-sdk-upgrade-<module>` pattern.
- The `backup/...` branch.
- The closed-PR description files in `docs/redesign/pr-details/`, because they record what those PRs targeted.

## 2. What was done on 2026-11-16

### 2.1 Checked that the branch was backed up
- Local and Bitbucket `WI01124532-aws-sdk-upgrade` were the same commit, `fa3efede`. Neither side was ahead or behind, there were no uncommitted tracked changes and no stashes.
- The untracked docs and IDE files (`*.md` docs, `*/docs/`, `.claude/`, `appianway.code-workspace`) are deliberately not in git, so they aren't on any remote.

### 2.2 Tried the rename on Bitbucket, then undid it locally
1. Renamed locally: `git branch -m WI01124532-aws-sdk-upgrade feature/WI01124532-aws-sdk-upgrade`.
2. Push refused: `git push -u origin feature/WI01124532-aws-sdk-upgrade` returned *"Insufficient permissions … your access is read-only"*, because Bitbucket is frozen for the migration.
3. The migration owner advised doing the rename **on GitHub after the migration completes**.
4. Undid the local rename (`git branch -m feature/WI01124532-aws-sdk-upgrade WI01124532-aws-sdk-upgrade`). The reason: with `push.default` unset (`simple`), a plain `git push` fails when the local and upstream names differ.
5. The old Bitbucket branch was never touched.

### 2.3 Updated the docs to the target name
`feature/WI01124532-aws-sdk-upgrade` replaced the main branch name, `origin/` refs included, in:
- `docs/2026-10-30-apway-design-update-plan.md`
- `docs/redesign/2026-10-30-apway-WI01124532-review-summary.md`
- `docs/redesign/2026-10-31-apway-aws-upgrade-dev-progress.md`. Its branch table (§R.1) has a *Rename pending* note.

> Until §4 is done, the docs name the target branch, but git still has `WI01124532-aws-sdk-upgrade`.

### 2.4 Set up GitHub access (GitHub CLI + SAML SSO)
The `wtg-e2open` org enforces SAML SSO, so a token works only once it has been authorised for SSO.

1. `gh auth status` showed a login as `ArijitKunduWTG` with the `repo`, `read:org`, `workflow` and `gist` scopes. The repo API still returned **403** *"Resource protected by organization SAML enforcement"*.
2. A credential popup appeared and disappeared. It came from a `git ls-remote` check that timed out, and nothing was saved. Ignore that popup and use the `gh` login instead.
3. The one-time SSO link in the 403 message gave a **404** because these links expire quickly.
4. Under https://github.com/settings/applications, the **GitHub CLI** app already listed `wtg-e2open` (and `WiseTechGlobal`) as granted. The existing token was still rejected, because SSO approval also applies to each token.
5. **Fix:** start an SSO session at https://github.com/orgs/wtg-e2open/sso, then get a new token in a terminal with `gh auth refresh -h github.com` (or `gh auth login -h github.com -p https -w`) and complete the device-code step in the browser.
6. Optional, so plain `git` uses the same login: `gh auth setup-git`.

### 2.5 Checked GitHub access and the migrated branches
Run with `gh` only, read-only:
```sh
gh api repos/wtg-e2open/INTTRA.appianway --jq '{full_name, visibility, default_branch, archived, permissions}'
gh api "repos/wtg-e2open/INTTRA.appianway/branches?per_page=100" --jq '.[] | "\(.name) \(.commit.sha[0:8])"'
```

| Check | Result |
|---|---|
| Permissions | `pull`, `push`, `triage`: **write access**. Not `maintain` or `admin` |
| Repo | private, not archived, default branch `develop` |
| `WI01124532-aws-sdk-upgrade` | `fa3efede`, same as Bitbucket and local ✅ |
| `develop` | `4cc7b99f` (PR #79), same as Bitbucket ✅ |
| `master` | `08a8939b`, same as Bitbucket ✅ |
| `migration-test` | added by the migration |

**Not migrated** (expected, since only selected branches move):
- `feature/ION-16098-jetty-cve`: already merged into `develop` through PR #68 (`191920fe`), so nothing is lost.
- `feature/ION-12317-apway-aws-upgrade` and `backup/ION-12317-apway-aws-upgrade-20260731`: earlier attempt, replaced by WI01124532.
- Local-only branches (merged sub-branches, `WI01124532-wave0-foundation`, `backup/WI01124532-aws-sdk-upgrade-pre-commons-u-items-2026-11-12`): they all point to commits that are already in `fa3efede`.

---

## 3. Pending: before the migration completes

- [x] **Confirm with the owner that the migration is finished**, meaning Bitbucket is retired and GitHub is the source of truth. Wait for this before switching remotes.
- [x] Don't push to Bitbucket. It's read-only, and any new work should go to GitHub once the migration is done.
- [x] **No extra GitHub rights needed.** The plan is a push, not a rename in GitHub's settings, so your existing write access (`push: true`) is enough.

## 4. Pending: after the migration completes

### 4.1 Point the local clone at GitHub
```sh
git remote set-url origin https://github.com/wtg-e2open/INTTRA.appianway.git
git fetch origin --prune
git remote -v                                  # confirm the GitHub URL
git rev-parse origin/WI01124532-aws-sdk-upgrade   # expect fa3efede… (or newer if work was pushed)
```
Run this in both clones: `C:\Users\arijit.kundu\projects\appianway` and the build worktree `C:\Users\arijit.kundu\projects\appianway-build`. They share one `.git`, so setting the remote once covers both.

### 4.2 Check the local branch matches GitHub before renaming
```sh
git checkout WI01124532-aws-sdk-upgrade
git rev-list --left-right --count WI01124532-aws-sdk-upgrade...origin/WI01124532-aws-sdk-upgrade   # expect 0 0
```
If GitHub is ahead (someone pushed after the migration), run `git merge --ff-only origin/WI01124532-aws-sdk-upgrade` first. If local is ahead, the extra local commits go up with the push in §4.3.

### 4.3 Rename locally, push the new name and set the upstream
```sh
git branch -m WI01124532-aws-sdk-upgrade feature/WI01124532-aws-sdk-upgrade
git push -u origin feature/WI01124532-aws-sdk-upgrade
```
- `-u` sets `origin/feature/WI01124532-aws-sdk-upgrade` as the upstream, so later `git push` and `git pull` need no arguments. It also clears the `push.default=simple` name-mismatch problem from §2.2.
- Check:
  ```sh
  git ls-remote --heads origin feature/WI01124532-aws-sdk-upgrade WI01124532-aws-sdk-upgrade   # both show the same SHA
  git status -sb   # expect: ## feature/WI01124532-aws-sdk-upgrade...origin/feature/WI01124532-aws-sdk-upgrade
  ```
- From here on, commit and push only to `feature/WI01124532-aws-sdk-upgrade`. The old GitHub branch stays, unchanged, as a copy.

### 4.4 Delete the old branch name on GitHub (later)
Do this only after **all** of the following:
- the migration owner has confirmed the migration is finished;
- nothing (PRs, branch protection, other people's clones) uses `WI01124532-aws-sdk-upgrade` any more.

```sh
git push origin --delete WI01124532-aws-sdk-upgrade
git fetch origin --prune
```
A push-based rename leaves no redirect, unlike a rename in GitHub's settings. Anyone who has the old branch checked out has to run `git fetch --prune` and switch to `feature/WI01124532-aws-sdk-upgrade`.

### 4.5 Tidy up
- [x] **Done 2026-11-17.** Remove the *Rename pending* note in `docs/redesign/2026-10-31-apway-aws-upgrade-dev-progress.md` §R.1 and record the GitHub remote there.
- [x] **Done 2026-11-17** (all four were merged, so `-d` deleted them). delete the merged local sub-branches, which point to commits that are already on the feature branch:
  ```sh
  git branch -d WI01124532-aws-sdk-upgrade-pom WI01124532-aws-sdk-upgrade-shared-config WI01124532-aws-sdk-upgrade-shared-runtime WI01124532-wave0-foundation
  ```
  Keep `backup/WI01124532-aws-sdk-upgrade-pre-commons-u-items-2026-11-12` until 1d is done.
- [x] **Checked 2026-11-17.** `develop` has no classic branch protection; it is governed by the ruleset **`PR_CHECK`** (default branch only): PR required, 1 approval, required status **`PR_BUILD`** (posted by `inttra-jenkins-ci[bot]`, Jenkins job `DEV_GIT_PR`), branch must be up to date with `develop` (strict), no force-push. The feature branch and sub-branches have **no** required check, so the Jenkins "set build status" workaround is not needed for sub-PRs. Before the final PR, merge `develop` into the feature branch (strict = up to date).
- [x] **Checked 2026-11-17.** GitHub ruleset **`Commit_Check`** enforces `^WI\d+(?:\s*[:\-]\s*|\s+).+` (the work item id, then a space, `:` or `-`, then text) on every commit message, on every branch except `develop` and `master`. Our `WI01124532 …` commits pass. GitHub's default merge message (`Merge pull request #N from …`) does not, so when merging a sub-PR into the feature branch set the merge message to start with `WI01124532` (e.g. `gh pr merge N --merge --subject "WI01124532 Merge pull request #N: TITLE"`). Keep the local hook.
- [x] Future sub-branches (1d `-shared-adapters` onward) and the final PR into `develop` target `feature/WI01124532-aws-sdk-upgrade` on GitHub.

---

## 5. Quick reference

| Need | Command |
|---|---|
| Check GitHub login and scopes | `gh auth status` |
| Get a new SSO-approved token | open https://github.com/orgs/wtg-e2open/sso, then `gh auth refresh -h github.com` |
| Let git use the gh login | `gh auth setup-git` |
| My permissions on the repo | `gh api repos/wtg-e2open/INTTRA.appianway --jq .permissions` |
| Branches on GitHub | `gh api "repos/wtg-e2open/INTTRA.appianway/branches?per_page=100" --jq '.[].name'` |
| Push the new name and set the upstream | `git branch -m WI01124532-aws-sdk-upgrade feature/WI01124532-aws-sdk-upgrade && git push -u origin feature/WI01124532-aws-sdk-upgrade` |
| Local vs remote in sync? | `git fetch origin && git rev-list --left-right --count HEAD...@{u}` (expect `0 0`) |

---

## 6. 2026-11-17 — Migration complete: verification and cut-over runbook

> **Status:** **all steps done on 2026-11-17** and every check matched what was expected. See the run log in §6.12. Steps are kept below as the record and for any other clone.
> All commands are for **PowerShell** in `C:\Users\arijit.kundu\projects\appianway`. The `git` commands work the same in Git Bash.

### 6.1 Verification results (2026-11-17)

| Check | Command | Result |
|---|---|---|
| `gh` login | `gh auth status` | `ArijitKunduWTG`, scopes `repo`, `read:org`, `workflow`, `gist` ✅ |
| Repo access | `gh api repos/wtg-e2open/INTTRA.appianway --jq .permissions` | `pull`, `push`, `triage` (write) ✅ |
| Plain `git` can reach GitHub | `git ls-remote --heads https://github.com/wtg-e2open/INTTRA.appianway.git` | works, no popup. The `gh` credential helper is already set up for `github.com` ✅ |
| **Feature branch** | same | `WI01124532-aws-sdk-upgrade` = **`fa3efede`** = local = Bitbucket ✅ |
| `master` | same | `08a8939b` = Bitbucket ✅ |
| `feature/WI01137977-BK-OCMBE-WATERMILL-CONSUMER` | same | `00f29851` = Bitbucket ✅ |
| `develop` | same + `gh api .../compare/4cc7b99f...05a1d8fb` | **`05a1d8fb`**, which is Bitbucket's `4cc7b99f` **plus 2 commits** from the migration test (`84ba0912 WI01154766 Test PR`, `05a1d8fb Merge pull request #1 from wtg-e2open/migration-test`). A fast-forward, nothing lost ✅ |
| `migration-test` | same | `84ba0912`, created by the migration (ignore) |
| Local working tree | `git status -sb` | clean apart from the untracked docs/IDE files. Local = remote (`0 0`). No stashes ✅ |
| Bitbucket still readable | `git ls-remote --heads origin` | yes (read-only) ✅ |

**What GitHub does NOT have** (§6.5 and §6.7 deal with this):

| | Bitbucket / local | GitHub |
|---|---|---|
| Branches | 55 `origin/*` remote-tracking refs | **5** branches |
| Tags | 465 local tags | **0** tags |

Conclusion: **safe to cut over.** The one branch that matters is identical on both sides.

### 6.2 The picture: what changes

```text
 BEFORE                                       AFTER (end of §6)
 ──────                                       ─────────────────
 local clone (.git)                           local clone (.git)
 │                                            │
 ├─ origin ──► Bitbucket (read-only)          ├─ origin ────► GitHub  wtg-e2open/INTTRA.appianway
 │             55 branches, 465 tags          │               ├─ WI01124532-aws-sdk-upgrade          fa3efede (kept, untouched)
 │                                            │               └─ feature/WI01124532-aws-sdk-upgrade  fa3efede (new, you push it)
 │                                            │
 │                                            └─ bitbucket ─► Bitbucket (read-only archive, push disabled)
 │                                                            all 55 branches kept as bitbucket/*
 │
 └─ local branch                              local branch
    WI01124532-aws-sdk-upgrade                feature/WI01124532-aws-sdk-upgrade
    tracks origin/WI01124532-aws-sdk-upgrade  tracks origin/feature/WI01124532-aws-sdk-upgrade
```

**Why add a `bitbucket` remote?** `git fetch origin --prune` against GitHub deletes every `origin/*` ref that GitHub doesn't have, which is 50 of the 55. Commits that only those refs point to become *unreachable*, and git's garbage collector eventually deletes them. Keeping Bitbucket under a second name keeps them reachable as `bitbucket/*` for as long as you need them, at no cost (the objects are already on disk).

### 6.3 Step 0: pre-flight

```powershell
cd C:\Users\arijit.kundu\projects\appianway
git status -sb          # expect: ## WI01124532-aws-sdk-upgrade...origin/WI01124532-aws-sdk-upgrade  (only ?? lines below)
git stash list          # expect: nothing
git worktree list       # expect 3 entries (see below)
```

- Close IntelliJ and stop any Maven build in this repo or in `appianway-build`. VS Code can stay open, but don't click its *Sync* button during the steps.
- Worktrees that share this `.git`, and what happens to them:
  - `C:\Users\arijit.kundu\projects\appianway-build`: detached HEAD at `0dc30210`. Not on a branch, so nothing below affects it.
  - `...\copilot-worktrees\appianway\arijitkunduwtg-jubilant-enigma`: local branch with no upstream. Not affected.
- Remotes and branch settings live in the shared `.git`, so run §6.5–§6.8 **once**, here.

### 6.4 Step 1: back up the workspace

Three layers, from most to least complete. Do all three. It takes about a minute.

```powershell
$bk = "C:\Users\arijit.kundu\projects\backups\appianway-2026-11-17"
New-Item -ItemType Directory -Force $bk | Out-Null

# 1a. Full folder copy: code, .git, untracked docs, .claude, .vscode, appianway.code-workspace
robocopy C:\Users\arijit.kundu\projects\appianway "$bk\appianway" /E /COPY:DAT /DCOPY:DAT /XD target /XJ /R:1 /W:1 /NFL /NDL /NP /LOG:"$bk\robocopy.log"
"robocopy exit code: $LASTEXITCODE"     # 0-7 = success, 8 or higher = something failed, check the log

# 1b. Single-file git backup of every ref (all local branches, all origin/* Bitbucket branches, all tags)
git bundle create "$bk\appianway-all.bundle" --all
git bundle verify "$bk\appianway-all.bundle"   # expect: "... is okay"

# 1c. Text snapshot of the git settings you are about to change
git remote -v                    > "$bk\remotes-before.txt"
git branch -vv                   > "$bk\branches-before.txt"
git config --local --list        > "$bk\git-config-before.txt"
git for-each-ref --format="%(objectname) %(refname)" > "$bk\all-refs-before.txt"
```

How to read the syntax:

| Piece | Meaning |
|---|---|
| `$bk = "..."` | PowerShell variable, so the path is typed once |
| `New-Item -ItemType Directory -Force` | like `mkdir -p`: makes the folder, no error if it exists |
| `robocopy SRC DST` | Windows' robust copy tool. Copies the *contents* of SRC into DST |
| `/E` | include all subfolders, empty ones too |
| `/COPY:DAT` `/DCOPY:DAT` | keep **D**ata, **A**ttributes and **T**imestamps of files and folders |
| `/XD target` | e**X**clude **D**irectories named `target` (Maven output, about 1.9 GB, rebuildable). The copy is then about 0.35 GB. Disk has 229 GB free |
| `/XJ` | skip junction points (avoids copy loops) |
| `/R:1 /W:1` | on a locked file, retry once after 1 s (the default is a million retries) |
| `/NFL /NDL /NP /LOG:` | don't print each file, folder or percentage; write a summary log instead |
| `$LASTEXITCODE` | exit code of the last program. robocopy uses 0–7 for success |
| `git bundle create FILE --all` | packs every ref and all their commits into one file. You can clone from it later: `git clone appianway-all.bundle restored` |
| `git bundle verify FILE` | checks the bundle is complete and readable |
| `> file.txt` | write the command's output to a file |
| `git for-each-ref --format=...` | list every ref (branch, remote branch, tag) with its commit id |

> The copy in 1a keeps the `.git\worktrees` entries, which point at the original `appianway-build` path. That's fine for a backup. Don't open the copy in an IDE while the original is open.

### 6.5 Step 2: keep Bitbucket as a read-only `bitbucket` remote

```powershell
git remote add bitbucket https://git.dev.e2open.com/scm/int/appianway.git
git remote set-url --push bitbucket DISABLED-bitbucket-is-read-only
git fetch bitbucket --no-tags
git remote -v
```

Expected:

```text
bitbucket  https://git.dev.e2open.com/scm/int/appianway.git (fetch)
bitbucket  DISABLED-bitbucket-is-read-only (push)
origin     https://git.dev.e2open.com/scm/int/appianway.git (fetch)
origin     https://git.dev.e2open.com/scm/int/appianway.git (push)
```

| Piece | Meaning |
|---|---|
| `git remote add NAME URL` | register a second remote. It gets its own `bitbucket/*` refs |
| `git remote set-url --push NAME X` | change only the **push** URL. A URL that doesn't exist makes any push to `bitbucket` fail at once, so nothing goes to Bitbucket by accident |
| `git fetch bitbucket` | create `bitbucket/*` refs for all 55 branches. Fast, because the objects are already local |
| `--no-tags` | the 465 tags are already local, so don't fetch them again |

Check: `(git branch -r --list "bitbucket/*").Count` should be **55**.

### 6.6 Step 3: point `origin` at GitHub

```powershell
git remote set-url origin https://github.com/wtg-e2open/INTTRA.appianway.git
git fetch origin --prune
git remote set-head origin --auto
git remote -v
git branch -r --list "origin/*"
git rev-parse origin/WI01124532-aws-sdk-upgrade
```

Expected:

```text
origin  https://github.com/wtg-e2open/INTTRA.appianway.git (fetch)
origin  https://github.com/wtg-e2open/INTTRA.appianway.git (push)

  origin/HEAD -> origin/develop
  origin/WI01124532-aws-sdk-upgrade
  origin/develop
  origin/feature/WI01137977-BK-OCMBE-WATERMILL-CONSUMER
  origin/master
  origin/migration-test

fa3efede278e0ce3bccb57fecefc0c090d4cf6b8
```

| Piece | Meaning |
|---|---|
| `git remote set-url origin URL` | change where the existing `origin` points. The name stays `origin`, so each branch's `branch.<name>.remote = origin` setting now means GitHub. Nothing is downloaded yet |
| `git fetch origin` | download GitHub's branches and update the `origin/*` refs |
| `--prune` | delete local `origin/*` refs GitHub doesn't have (the 50 Bitbucket-only ones). Local **branches** are never deleted by this, and **tags are kept** because `--prune-tags` isn't set. The commits stay reachable through `bitbucket/*` (§6.5) |
| `git remote set-head origin --auto` | ask GitHub for its default branch and set `origin/HEAD` (expected `develop`) |
| `git rev-parse REF` | print the commit id a ref points to |

> Don't push tags to GitHub (`git push --tags`). They weren't part of the migration, and that decision belongs to the migration owner.

### 6.7 Step 4: fix local branches whose upstream isn't on GitHub

**The problem.** Some local branches still have an *upstream* (tracking) setting such as `origin/feature/ION-16098-jetty-cve`. After §6.6, `origin` means GitHub, which doesn't have those branches. Two things follow:

- `git branch -vv` and `git status` show `[origin/...: gone]`, which is noise and confusing.
- **The real risk:** with `push.default=simple` (the default, and not overridden here), a plain `git push` on such a branch pushes to the same name on `origin`. That would **create** the old branch on GitHub without asking.

Check what you have:

```powershell
git branch -vv
```

| Local branch | Upstream today | On GitHub? | Action |
|---|---|---|---|
| `WI01124532-aws-sdk-upgrade` | `origin/WI01124532-aws-sdk-upgrade` | yes | rename and push in §6.8 |
| `develop` | `origin/develop` | yes (now `05a1d8fb`) | fast-forward (below) |
| `feature/ION-16098-jetty-cve` | `origin/feature/ION-16098-jetty-cve` | **no** | unset upstream |
| `backup/ION-12317-apway-aws-upgrade-20260731` | `origin/backup/ION-12317-...` | **no** | unset upstream |
| `WI01124532-aws-sdk-upgrade-pom` | `origin/...-pom` (already gone) | **no** | unset upstream (or delete, §4.5) |
| `WI01124532-aws-sdk-upgrade-shared-config` | `origin/...-shared-config` (already gone) | **no** | unset upstream (or delete, §4.5) |
| `WI01124532-aws-sdk-upgrade-shared-runtime` | `origin/...-shared-runtime` (already gone) | **no** | unset upstream (or delete, §4.5) |
| `feature/ION-12317-apway-aws-upgrade`, `WI01124532-wave0-foundation`, `backup/WI01124532-...-2026-11-12`, `arijitkunduwtg-jubilant-enigma` | none | n/a | nothing to do |

**Fix: remove the upstream from the branches GitHub doesn't have.** The branches and their commits stay exactly as they are; only the tracking setting goes.

```powershell
$noGithub = @(
  "feature/ION-16098-jetty-cve",
  "backup/ION-12317-apway-aws-upgrade-20260731",
  "WI01124532-aws-sdk-upgrade-pom",
  "WI01124532-aws-sdk-upgrade-shared-config",
  "WI01124532-aws-sdk-upgrade-shared-runtime"
)
foreach ($b in $noGithub) { git branch --unset-upstream $b }
```

| Piece | Meaning |
|---|---|
| `@( "a", "b" )` | PowerShell array |
| `foreach ($b in $noGithub) { ... }` | run the block once for each branch name |
| `git branch --unset-upstream NAME` | delete `branch.NAME.remote` and `branch.NAME.merge` from `.git/config`. After this, a plain `git push` on that branch **fails** with "has no upstream branch" instead of creating it on GitHub |

**Bring local `develop` up to GitHub's `develop`.** It isn't checked out anywhere, so it can be moved without switching to it:

```powershell
git fetch origin develop:develop
git rev-parse --short=8 develop      # expect 05a1d8fb
```

`git fetch origin SRC:DST` means "fetch GitHub's `SRC` branch and move my local `DST` branch to it". It refuses if the move isn't a fast-forward, so it can't lose local commits.

Check:

```powershell
git branch -vv | Select-String "gone"     # expect: no output
```

### 6.8 Step 5: rename the branch locally and push the new name

```powershell
git rev-list --left-right --count WI01124532-aws-sdk-upgrade...origin/WI01124532-aws-sdk-upgrade   # expect: 0  0
git branch -m WI01124532-aws-sdk-upgrade feature/WI01124532-aws-sdk-upgrade
git push -u origin feature/WI01124532-aws-sdk-upgrade
```

| Piece | Meaning |
|---|---|
| `git rev-list --left-right --count A...B` | count the commits only on A (left) and only on B (right). `0 0` means identical. If the right number is above 0, GitHub is ahead: run `git merge --ff-only origin/WI01124532-aws-sdk-upgrade` first |
| `git branch -m OLD NEW` | **m**ove (rename) a local branch. Same commits, new name. Its settings move with it, but its upstream still names the *old* remote branch until the next line runs |
| `git push -u origin NEW` | create `NEW` on GitHub at the same commit, and (`-u` = `--set-upstream`) make `origin/NEW` the upstream of the local branch. After this, plain `git push` and `git pull` work |

```text
                         git branch -m                            git push -u origin feature/...
 local   WI01124532-aws-sdk-upgrade ──► feature/WI01124532-aws-sdk-upgrade ──────────────┐
             (fa3efede)                       (fa3efede)                                  │
                                                                                          ▼
 GitHub  WI01124532-aws-sdk-upgrade (fa3efede)          feature/WI01124532-aws-sdk-upgrade (fa3efede)
         └─ stays as it is                              └─ new, now the upstream of the local branch
```

Check:

```powershell
git ls-remote --heads origin feature/WI01124532-aws-sdk-upgrade WI01124532-aws-sdk-upgrade
# expect two lines, both fa3efede278e0ce3bccb57fecefc0c090d4cf6b8
git status -sb
# expect: ## feature/WI01124532-aws-sdk-upgrade...origin/feature/WI01124532-aws-sdk-upgrade
git config --get branch.feature/WI01124532-aws-sdk-upgrade.merge
# expect: refs/heads/feature/WI01124532-aws-sdk-upgrade
```

**The old name on GitHub stays.** Don't run §4.4. From now on, commit and push only to `feature/WI01124532-aws-sdk-upgrade`. The old branch is a frozen copy at `fa3efede`.

> This push adds no new commits, so the local commit-msg hook doesn't come into it, and `fa3efede` already starts with `WI01124532`.

### 6.9 Step 6: final check

```powershell
git remote -v      # origin = GitHub (fetch and push); bitbucket = Bitbucket fetch, DISABLED push
git branch -vv     # feature/WI01124532-aws-sdk-upgrade [origin/feature/WI01124532-aws-sdk-upgrade]; no "gone"
git status -sb     # clean apart from ?? files
gh api "repos/wtg-e2open/INTTRA.appianway/branches?per_page=100" --jq '.[] | "\(.name) \(.commit.sha[0:8])"'
# expect 6 branches: the 5 from §6.1 plus feature/WI01124532-aws-sdk-upgrade fa3efede
```

> PowerShell 7 passes the single-quoted `--jq` argument through unchanged, so no `\"` escaping is needed.

Then do the §4.5 tidy-up items (progress-doc note, `develop` branch protection, commit-msg rule on GitHub). Skip deleting the old branch, as decided.

### 6.10 Rollback (if anything looks wrong)

Undo one step at a time, newest first. Nothing above changes any commit, so rollback only touches names and settings.

| Undo | Command |
|---|---|
| The push of the new name (§6.8) | `git push origin --delete feature/WI01124532-aws-sdk-upgrade` (only the new branch; the old one was never touched) |
| The local rename (§6.8) | `git branch -m feature/WI01124532-aws-sdk-upgrade WI01124532-aws-sdk-upgrade` then `git branch -u origin/WI01124532-aws-sdk-upgrade` |
| An unset upstream (§6.7) | `git branch -u bitbucket/<name> <name>` (tracks the read-only copy). The old values are in `$bk\git-config-before.txt` |
| `origin` → GitHub (§6.6) | `git remote set-url origin https://git.dev.e2open.com/scm/int/appianway.git` then `git fetch origin` |
| The `bitbucket` remote (§6.5) | `git remote remove bitbucket` |
| Everything | close the IDE, rename the broken folder, and copy `$bk\appianway` back to `C:\Users\arijit.kundu\projects\appianway`. The bundle (`git clone "$bk\appianway-all.bundle" restored`) is a second fallback |

### 6.11 Quick reference (after cut-over)

| Need | Command |
|---|---|
| Where does origin point? | `git remote -v` |
| Branches on GitHub | `git ls-remote --heads origin` |
| Local vs GitHub in sync? | `git fetch origin; git rev-list --left-right --count HEAD...@{u}` (expect `0 0`) |
| Look at an old Bitbucket-only branch | `git log --oneline -5 bitbucket/<branch>` |
| Restore an old Bitbucket branch locally | `git switch -c <branch> bitbucket/<branch>` (don't push it unless that's agreed) |
| New sub-branch off the feature branch | `git switch -c WI01124532-aws-sdk-upgrade-<module> feature/WI01124532-aws-sdk-upgrade` then `git push -u origin WI01124532-aws-sdk-upgrade-<module>` |
| Open a PR on GitHub | `gh pr create --base feature/WI01124532-aws-sdk-upgrade --title "WI01124532 ..."` |

### 6.12 Run log (2026-11-17)

| Step | Result |
|---|---|
| 0 Pre-flight | clean, 0 stashes, 3 worktrees as expected |
| 1 Backup | `C:\Users\arijit.kundu\projects\backups\appianway-2026-11-17`. robocopy exit 1 (= files copied OK): 2,872 files, 347 MB, 0 failed. `appianway-all.bundle` 181 MB, *is okay*. Snapshots: remotes, branches, config, 537 refs |
| 2 `bitbucket` remote | added, push URL `DISABLED-bitbucket-is-read-only`. 55 branches + `bitbucket/HEAD`, the same set as the old `origin/*` |
| 3 `origin` → GitHub | `origin/*` = GitHub's 5 branches. `origin/HEAD` → `develop`. 465 local tags kept |
| 4 Branch fix | upstream unset on the 5 branches GitHub doesn't have. No `gone` left. `develop` fast-forwarded `0448d362..05a1d8fb` |
| 5 Rename + push | `0 0` before the rename. Pushed `feature/WI01124532-aws-sdk-upgrade` with `-u`. Both names on GitHub at `fa3efede`. `status -sb` = `## feature/WI01124532-aws-sdk-upgrade...origin/feature/WI01124532-aws-sdk-upgrade` |
| 6 Final | GitHub has 6 branches (the 5 + the new one). Worktrees unaffected. Old `WI01124532-aws-sdk-upgrade` left on GitHub as decided |

Noted on push: GitHub reports **66 Dependabot alerts on `develop`** (3 critical, 25 high, 32 moderate, 6 low), at https://github.com/wtg-e2open/INTTRA.appianway/security/dependabot. Worth comparing with the OWASP report (`2026-07-20-appway-owasp-report.md`) and the AWS SDK upgrade scope.

Still open: the §4.5 tidy-up (progress-doc *Rename pending* note, `develop` branch protection and required checks on GitHub, commit-msg rule on GitHub).
