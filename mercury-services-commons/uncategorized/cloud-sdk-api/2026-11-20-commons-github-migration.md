# mercury-services-commons — Bitbucket to GitHub cut-over

> **Date:** 2026-11-20
> **Status:** **done.** Every step below was run on 2026-11-20 and every check matched what was expected. The run log is in §10.
> **Scope:** how the local clone `C:\Users\arijit.kundu\projects\mercury-services-commons` moved from Bitbucket to GitHub: what was checked, the backup, the remote switch, the branch clean-up, the commit identity, and how to undo each step.
> **Based on:** the AppianWay runbook (`C:\Users\arijit.kundu\projects\appianway\docs\2026-11-16-apway-github-migration.md` §6). The same pattern was used here, without AppianWay's branch rename, because the commons feature branch already has its final name.

| | |
|---|---|
| Bitbucket (old) | `https://git.dev.e2open.com/scm/int/mercury-services-commons.git` (now **read-only**) |
| GitHub (new) | https://github.com/wtg-e2open/INTTRA.mercury-services-commons (private, default branch `develop`) |
| Feature branch | `feature/ION-12310-commons-cloudsdk-refactoring` at **`aa52175`** (1.0.39-SNAPSHOT README note). Same name and same commit on both sides |
| GitHub login | `ArijitKunduWTG` through the `gh` CLI (SAML SSO approved) |
| Backup | `C:\Users\arijit.kundu\projects\backups\mercury-services-commons-2026-11-20` |

All commands below are shown for **PowerShell**, run from `C:\Users\arijit.kundu\projects\mercury-services-commons`. The `git` and `gh` commands are the same in Git Bash.

---

## 1. The picture: what changed

```text
 BEFORE                                         AFTER
 ──────                                         ─────
 local clone (.git)                             local clone (.git)
 │                                              │
 ├─ origin ──► Bitbucket (read-only)            ├─ origin ────► GitHub  wtg-e2open/INTTRA.mercury-services-commons
 │             36 branches                      │               ├─ develop                                         f15b1e1a
 │                                              │               ├─ feature/ION-12310-commons-cloudsdk-refactoring  aa521757
 │                                              │               ├─ backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12  c353706c
 │                                              │               └─ WI01124535_MFA_IMPL_SDK2                        0f27e816 (not ours)
 │                                              │
 │                                              └─ bitbucket ─► Bitbucket (read-only archive, push DISABLED)
 │                                                              all 36 branches kept as bitbucket/*
 │
 ├─ local develop   8c6fcef (6 behind)          local develop   f15b1e1 (= GitHub)
 ├─ feature branch  aa52175 ⇄ origin            feature branch  aa52175 ⇄ origin (now GitHub), 0 ahead / 0 behind
 └─ commit e-mail   e2open (global)             commit e-mail   WiseTech (repo-local) → credited to ArijitKunduWTG
```

**In one sentence:** `origin` now means GitHub, the old Bitbucket repository is kept under the name `bitbucket` so nothing on it is lost, and nothing about the commits themselves changed.

---

## 2. Verification before the cut-over (read-only)

Nothing in this section changes anything. It only checks that GitHub has what we need.

```powershell
gh auth status
gh api repos/wtg-e2open/INTTRA.mercury-services-commons --jq '{full_name, visibility, default_branch, permissions}'
gh api "repos/wtg-e2open/INTTRA.mercury-services-commons/branches?per_page=100" --jq '.[] | "\(.name) \(.commit.sha[0:8])"'
gh api repos/wtg-e2open/INTTRA.mercury-services-commons/compare/<bitbucket-develop-sha>...f15b1e1a --jq '{status, ahead_by, behind_by}'
gh api repos/wtg-e2open/INTTRA.mercury-services-commons/rulesets --jq '.[] | "\(.id) \(.name) \(.target) \(.enforcement)"'
```

| Piece | Meaning |
|---|---|
| `gh auth status` | shows which GitHub account the `gh` CLI is logged in as, and the token's scopes |
| `gh api <path>` | calls the GitHub REST API as you. `repos/OWNER/REPO` is the repository's details |
| `--jq '...'` | filters the JSON reply (the `jq` language is built in to `gh`). `{a, b}` keeps only those fields; `.[] \| "..."` prints one line per item |
| `\(.name)` | inside a jq string, inserts the value of the field `name` |
| `.commit.sha[0:8]` | the first 8 characters of the commit id, which is enough to compare |
| `?per_page=100` | ask for up to 100 results in one page (the default is 30). It's quoted because `?` and `&` mean something to the shell |
| `compare/A...B` | GitHub's comparison of two commits. `identical` means the same commit; `ahead_by`/`behind_by` count the commits only on one side |

### Results

| Check | Result |
|---|---|
| `gh` login | `ArijitKunduWTG`, scopes `repo`, `read:org`, `workflow`, `gist` ✅ |
| Repo access | private, default branch `develop`, permissions `pull`, `push`, `triage` (write; not `maintain` or `admin`) ✅ |
| **`feature/ION-12310-commons-cloudsdk-refactoring`** | GitHub **`aa521757`** = local = Bitbucket ✅ |
| `develop` | GitHub `f15b1e1a` = Bitbucket's `origin/develop` (`compare` says **identical**) ✅. Local `develop` was 6 commits behind (normal; fixed in §6) |
| `backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12` | `c353706c` = Bitbucket ✅ |
| `WI01124535_MFA_IMPL_SDK2` | `0f27e816`. Not our branch. Note that it is **not** the same as Bitbucket's `feature/WI01124535_MFA_IMPL_SDK2` (`92995879`): a different name and a different commit. That's for its owner, not for us |
| Branches | Bitbucket **36**, GitHub **4** (only the requested branches were migrated, plus `develop`) |
| Tags | GitHub has **0**. Locally there are 4. Don't push tags without the migration owner's OK |
| Local working tree | clean; local feature branch = remote (`0 0`) ✅ |
| Stash | 1 entry, `stash@{0}` *"pre-rebase security work 2026-09-11"*. Stashes are local only; nothing about the cut-over touches them. Also saved as a patch in the backup (§4) |

### GitHub rules on this repository (rulesets)

| Ruleset | Applies to | What it enforces |
|---|---|---|
| **`COMMIT_CHECK`** (id 27417088) | every branch **except** `develop` and `master` | every pushed commit message must match `^WI\d+(?:\s*[:\-]\s*\|\s+).+` |
| **`PR_CHECK`** (id 27417089) | default branch (`develop`) | changes only through a PR, **1 approval**, required status check **`PR_BUILD`** (Jenkins), no force-push. `strict` is **off**, so the branch does not have to be up to date with `develop` to merge (unlike AppianWay) |
| **Copilot review for default branch** (id 27640744) | default branch (`develop`) | GitHub Copilot reviews PRs into `develop` automatically |

How to read the `COMMIT_CHECK` pattern `^WI\d+(?:\s*[:\-]\s*|\s+).+`:

| Piece | Meaning |
|---|---|
| `^` | start of the message |
| `WI` | the literal letters `WI` (the work item prefix) |
| `\d+` | one or more digits, e.g. `01124532` |
| `(?: ... \| ... )` | a group with two choices (`?:` = "don't capture", it's just grouping) |
| `\s*[:\-]\s*` | choice 1: a `:` or `-`, with optional spaces around it |
| `\s+` | choice 2: one or more spaces |
| `.+` | then at least one more character (the summary) |

So `WI01124532 ION-12310 docs: …` passes and `ION-12310: …` does **not**. The rule has no `$` at the end any more, so a normal `git commit` (whose message ends in a newline) passes, and the Co-Authored-By trailer is fine. **Never** use the old `git commit-tree` "no trailing newline" workaround. GitHub's default merge-commit message (`Merge pull request #N from …`) fails the rule on feature branches, so when merging a PR into a feature branch, set the subject to start with the WI id (example in §11).

> Older commits on the feature branch that start with `ION-12310:` are already on GitHub. The rule only checks **new** commits being pushed, so they are not a problem.

---

## 3. Step 0: pre-flight

```powershell
cd C:\Users\arijit.kundu\projects\mercury-services-commons
git status -sb          # expect: ## feature/ION-12310-commons-cloudsdk-refactoring...origin/feature/ION-12310-commons-cloudsdk-refactoring
git stash list          # 1 entry (kept, see §2)
git worktree list       # expect: only this folder
git check-ignore -v cloud-sdk-api/docs/x.md   # docs/ folders are git-ignored (.gitignore line 17)
```

| Piece | Meaning |
|---|---|
| `git status -sb` | **s**hort status with the **b**ranch line: `## local...upstream [ahead N, behind M]`. Untracked files show as `??` |
| `git stash list` | the saved-aside changes (`git stash`). They live only in this clone |
| `git worktree list` | other folders that share this `.git`. Here there are none, so the steps affect only this folder |
| `git check-ignore -v PATH` | tells you whether a path is ignored and which `.gitignore` line does it. Confirms this document will never be committed by accident |

Result: clean tree, 1 stash, 1 worktree, `docs/` ignored. ✅

---

## 4. Step 1: back up the workspace

Three layers, from most to least complete.

```powershell
$bk = "C:\Users\arijit.kundu\projects\backups\mercury-services-commons-2026-11-20"
New-Item -ItemType Directory -Force $bk | Out-Null

# 1a. Full folder copy: code, .git (with the stash), untracked docs, IDE files
robocopy C:\Users\arijit.kundu\projects\mercury-services-commons "$bk\mercury-services-commons" /E /COPY:DAT /DCOPY:DAT /XD target /XJ /R:1 /W:1 /NFL /NDL /NP /LOG:"$bk\robocopy.log"
"robocopy exit code: $LASTEXITCODE"     # 0-7 = success, 8 or higher = something failed

# 1b. One-file git backup of every ref (local branches, all Bitbucket origin/* branches, tags)
git bundle create "$bk\mercury-services-commons-all.bundle" --all
git bundle verify "$bk\mercury-services-commons-all.bundle"

# 1c. Text snapshots of the settings about to change
git remote -v                    > "$bk\remotes-before.txt"
git branch -vv                   > "$bk\branches-before.txt"
git config --local --list        > "$bk\git-config-before.txt"
git for-each-ref --format="%(objectname) %(refname)" > "$bk\all-refs-before.txt"
git stash list                   > "$bk\stash-before.txt"
git stash show -p "stash@{0}"    > "$bk\stash0.patch"
```

| Piece | Meaning |
|---|---|
| `$bk = "..."` | a PowerShell variable, so the long path is typed once and reused as `$bk` |
| `New-Item -ItemType Directory -Force PATH` | like `mkdir -p`: creates the folder, and no error if it already exists |
| `\| Out-Null` | throw away the command's output (here, the folder details it would print) |
| `robocopy SRC DST` | Windows' robust copy tool. Copies the **contents** of SRC into DST |
| `/E` | include all subfolders, empty ones too |
| `/COPY:DAT` `/DCOPY:DAT` | keep **D**ata, **A**ttributes and **T**imestamps, for files and for folders |
| `/XD target` | e**X**clude **D**irectories named `target` (Maven build output, can be rebuilt) |
| `/XJ` | skip junction points (Windows folder links), which avoids copy loops |
| `/R:1 /W:1` | if a file is locked, retry once after 1 second (the default is a million retries, 30 s apart) |
| `/NFL /NDL /NP` | **N**o **F**ile **L**ist, **N**o **D**irectory **L**ist, **N**o **P**ercentage: keep the screen quiet |
| `/LOG:FILE` | write the summary to a log file instead |
| `$LASTEXITCODE` | exit code of the last program. robocopy is unusual: **0–7 mean success** (1 = "files were copied"), 8+ means failure |
| `git bundle create FILE --all` | packs every ref and all their history into a single file. You can clone from it: `git clone FILE restored` |
| `git bundle verify FILE` | checks the bundle is complete and readable (exit code 0 = OK) |
| `> file.txt` | write the command's output to a file |
| `git config --local --list` | every setting in this repo's `.git\config` (remotes, branch tracking, e-mail) |
| `git for-each-ref --format="%(objectname) %(refname)"` | one line per ref (branch, remote branch, tag, stash) with its commit id |
| `git stash show -p "stash@{0}"` | the stash's changes as a **p**atch. Quoted because `{}` means something to PowerShell. Re-apply later with `git apply stash0.patch` if ever needed |

**Result**

| File | What it is |
|---|---|
| `mercury-services-commons\` | folder copy: robocopy exit **1** (= copied OK), **1,729 files, 62.4 MB, 0 failed** (751 folders, 10 `target` folders skipped) |
| `mercury-services-commons-all.bundle` | 57 MB, verify exit **0**, *"records a complete history"* |
| `remotes-before.txt`, `branches-before.txt`, `git-config-before.txt` | the settings as they were before the cut-over (used for rollback, §9) |
| `all-refs-before.txt` | **71** refs |
| `stash-before.txt`, `stash0.patch` | the one stash, listed and as a patch |

---

## 5. Step 2: keep Bitbucket as a read-only `bitbucket` remote

**Why this step exists.** In Step 3 we point `origin` at GitHub and run `git fetch --prune`. *Prune* deletes every local `origin/*` ref that GitHub doesn't have: here **32 of the 36** Bitbucket branches. Commits that only those refs point to would become *unreachable* and git's garbage collector would eventually delete them. Registering Bitbucket under a second name keeps them reachable as `bitbucket/*` for as long as we want. It costs nothing because the objects are already on disk.

```powershell
git remote add bitbucket https://git.dev.e2open.com/scm/int/mercury-services-commons.git
git remote set-url --push bitbucket DISABLED-bitbucket-is-read-only
git fetch bitbucket --no-tags
git remote -v
(git branch -r --list "bitbucket/*").Count
```

| Piece | Meaning |
|---|---|
| `git remote add NAME URL` | register another remote. It gets its own `NAME/*` refs, separate from `origin/*` |
| `git remote set-url --push NAME X` | change only the **push** address. `X` is not a real URL, so any `git push bitbucket` fails at once: nothing can go to Bitbucket by accident |
| `git fetch bitbucket` | download Bitbucket's branch list and create the `bitbucket/*` refs (fast: the commits are already local) |
| `--no-tags` | don't fetch tags again (the tags are already local) |
| `git remote -v` | list remotes with their fetch and push URLs (**v**erbose) |
| `(...).Count` | PowerShell: count the lines a command printed |

**Result:** `bitbucket` = Bitbucket for fetch, `DISABLED-bitbucket-is-read-only` for push. **37** refs = all 36 branches + `bitbucket/HEAD`. ✅

---

## 6. Step 3: point `origin` at GitHub

```powershell
git remote set-url origin https://github.com/wtg-e2open/INTTRA.mercury-services-commons.git
git fetch origin --prune
git remote set-head origin --auto
git remote -v
git branch -r --list "origin/*"
git rev-parse origin/feature/ION-12310-commons-cloudsdk-refactoring
```

| Piece | Meaning |
|---|---|
| `git remote set-url origin URL` | change where the existing `origin` points. The **name** stays `origin`, so each branch's setting `branch.<name>.remote = origin` now means GitHub. Nothing is downloaded yet |
| `git fetch origin` | download GitHub's branches and update the `origin/*` refs |
| `--prune` | delete local `origin/*` refs that GitHub doesn't have (the 32 Bitbucket-only ones). It never deletes local **branches**, and **tags are kept** because `--prune-tags` isn't given. The commits are still reachable through `bitbucket/*` (Step 2) |
| `git remote set-head origin --auto` | ask GitHub for its default branch and set `origin/HEAD` to it (`develop`) |
| `git branch -r --list "origin/*"` | list **r**emote-tracking refs that match the pattern |
| `git rev-parse REF` | print the full commit id a ref points to |

**Result**

```text
origin  https://github.com/wtg-e2open/INTTRA.mercury-services-commons.git (fetch)
origin  https://github.com/wtg-e2open/INTTRA.mercury-services-commons.git (push)

  origin/HEAD -> origin/develop
  origin/WI01124535_MFA_IMPL_SDK2
  origin/backup/feature-ION-12310-pre-WI01124532-u-items-2026-11-12
  origin/develop
  origin/feature/ION-12310-commons-cloudsdk-refactoring

aa52175716a51b8fb6727c5612eb2d8f5ef88a61
```

32 `origin/*` refs pruned, 1 new (`origin/WI01124535_MFA_IMPL_SDK2`), 4 local tags kept. ✅

> No credential popup: git uses the `gh` login for `github.com` (`gh auth setup-git` was done for the other workspaces and is a global setting). If a popup ever appears, close it and run `gh auth status`; if the token was rejected, open https://github.com/orgs/wtg-e2open/sso and run `gh auth refresh -h github.com`.

---

## 7. Step 4: fix local branch tracking

After Step 3, `origin` means GitHub. Any local branch whose *upstream* (tracking branch) GitHub doesn't have would show `[origin/...: gone]`, and with `push.default=simple` (git's default, not overridden here) a plain `git push` on it would **create** that branch on GitHub without asking.

Check every local branch:

```powershell
git for-each-ref --format='%(refname:short)|%(upstream:short)|%(upstream:track)' refs/heads
```

| Piece | Meaning |
|---|---|
| `git for-each-ref ... refs/heads` | loop over all local branches |
| `%(refname:short)` | the branch name |
| `%(upstream:short)` | its upstream, e.g. `origin/develop` (empty = none) |
| `%(upstream:track)` | `[ahead N, behind M]`, `[gone]`, or empty when in sync |
| single quotes `'...'` | stop PowerShell from treating `%(...)` or `\|` specially |

**What we found**

| Local branch | Upstream | Action |
|---|---|---|
| `feature/ION-12310-commons-cloudsdk-refactoring` | `origin/feature/ION-12310-commons-cloudsdk-refactoring` | none: GitHub has it at the same commit |
| `develop` | `origin/develop` | fast-forward, 6 commits behind (below) |
| `backup/feature-ION-12310-pre-rebase-4` | `origin/feature/ION-12310-commons-cloudsdk-refactoring` (ahead 52, behind 107) | **unset upstream.** A backup should not track the live feature branch: a `git pull` there would merge the feature branch into the backup |
| the other 15 (`backup*`, G1–G4, `parameterstorelookup-refactor`) | none | nothing to do |

No branch showed `gone`, so no other changes were needed.

```powershell
git branch --unset-upstream backup/feature-ION-12310-pre-rebase-4
git fetch origin develop:develop
git rev-parse --short=8 develop      # expect f15b1e1a
git branch -vv | Select-String "gone"   # expect: no output
```

| Piece | Meaning |
|---|---|
| `git branch --unset-upstream NAME` | delete `branch.NAME.remote` and `branch.NAME.merge` from `.git\config`. The branch and its commits are untouched; only the tracking link goes |
| `git fetch origin SRC:DST` | fetch GitHub's `SRC` branch and move local `DST` to it **without checking it out**. It refuses unless it's a fast-forward, so it can't lose local commits |
| `--short=8` | print an 8-character commit id |
| `git branch -vv` | every local branch with its commit, upstream and ahead/behind (**v**ery **v**erbose) |
| `\| Select-String "gone"` | PowerShell's `grep`: show only lines containing `gone` |

**Result:** `develop` moved `8c6fcef` → `f15b1e1` (fast-forward). The 6 new commits: PRs #56 (WI01128840 CSP filter) and #58 (WI01149458 Commons SDK1 vulnerability fixes). No `gone` branches. ✅

> The feature branch is **6 commits behind `develop`** (those same 6). `PR_CHECK` doesn't require it to be up to date, but merge `develop` into the feature branch before the final PR anyway, so the PR build checks what will actually land.

---

## 8. Step 5: commit identity

The global git e-mail is the e2open address, and GitHub credits that to the older account `akundue2i`. `gh` is logged in as `ArijitKunduWTG`, which pushes and opens PRs. To credit commits to the same account (as was done in AppianWay), set a **repo-local** e-mail:

```powershell
git config --local user.email arijit.kundu@wisetechglobal.com
git config user.email      # expect the wisetechglobal address
git config user.name       # Arijit Kundu (unchanged, from the global config)
```

| Piece | Meaning |
|---|---|
| `git config --local KEY VALUE` | write the setting to this repo's `.git\config` only. It overrides the global value (`~\.gitconfig`) in this repo and nowhere else |
| `git config KEY` (no value) | print the value git will actually use, after local/global/system are combined |

Existing commits keep their old author (changing them would need a force-push). Only new commits use the new address.

---

## 9. Step 6: final check

```powershell
git remote -v                                   # origin = GitHub (fetch and push); bitbucket = fetch only, push DISABLED
git status -sb                                  # ## feature/ION-12310-commons-cloudsdk-refactoring...origin/feature/ION-12310-commons-cloudsdk-refactoring
git rev-list --left-right --count 'HEAD...@{u}'   # expect: 0  0  (quotes needed in PowerShell)
git push --dry-run                              # expect: Everything up-to-date (proves push auth works, sends nothing)
git stash list                                  # stash@{0} still there
```

| Piece | Meaning |
|---|---|
| `git rev-list --left-right --count A...B` | count commits only on A (left) and only on B (right). `0 0` = identical |
| `HEAD` | the commit you have checked out |
| `@{u}` | short for "the upstream of the current branch" (`origin/feature/ION-12310-…`). **In PowerShell, always quote it** (`'HEAD...@{u}'`): unquoted, `@{…}` is PowerShell's hashtable syntax and git receives garbage (`fatal: ambiguous argument 'dQA='`). Git Bash doesn't need the quotes |
| `'…'` | single quotes: PowerShell passes the text to git exactly as written |
| `git push --dry-run` | does everything a push does (connect, log in, compare) **except** send anything |

**Result:** all as expected. ✅

### Rollback (if anything ever looks wrong)

Undo newest first. No step changed any commit, so rollback only touches names and settings.

| Undo | Command |
|---|---|
| Commit e-mail (Step 5) | `git config --local --unset user.email` |
| `develop` fast-forward (Step 4) | `git branch -f develop 8c6fcef` (not really needed: it only moved forward) |
| Unset upstream (Step 4) | `git branch -u bitbucket/feature/ION-12310-commons-cloudsdk-refactoring backup/feature-ION-12310-pre-rebase-4` (tracks the read-only copy). Old values are in `$bk\git-config-before.txt` |
| `origin` → GitHub (Step 3) | `git remote set-url origin https://git.dev.e2open.com/scm/int/mercury-services-commons.git` then `git fetch origin` |
| `bitbucket` remote (Step 2) | `git remote remove bitbucket` |
| Everything | close the IDE, rename the folder, copy `$bk\mercury-services-commons` back to `C:\Users\arijit.kundu\projects\mercury-services-commons`. Second fallback: `git clone "$bk\mercury-services-commons-all.bundle" restored` |

---

## 10. Run log (2026-11-20)

| Step | Result |
|---|---|
| Verification | GitHub feature branch `aa521757` = local = Bitbucket. `develop` identical. Write access. 3 rulesets read |
| 0 Pre-flight | clean, 1 stash (kept), 1 worktree, `docs/` git-ignored |
| 1 Backup | `backups\mercury-services-commons-2026-11-20`: robocopy exit 1, 1,729 files / 62.4 MB / 0 failed; bundle 57 MB, verify OK; snapshots incl. 71 refs and `stash0.patch` |
| 2 `bitbucket` remote | added, push DISABLED, 36 branches + `bitbucket/HEAD` |
| 3 `origin` → GitHub | 32 refs pruned; `origin/*` = GitHub's 4 branches; `origin/HEAD` → `develop`; 4 tags kept |
| 4 Branch fix | `backup/feature-ION-12310-pre-rebase-4` upstream unset; `develop` fast-forwarded `8c6fcef..f15b1e1`; no `gone` |
| 5 Identity | repo-local `user.email` = WiseTech address |
| 6 Final | `0 0`, `push --dry-run` = *Everything up-to-date*, stash intact |

**Still open (not part of the cut-over)**
- Merge `develop` (6 commits: CSP filter #56, SDK1 vulnerability fixes #58) into the feature branch before the final PR.
- Tags were not migrated to GitHub. Leave them to the migration owner.
- `WI01124535_MFA_IMPL_SDK2` on GitHub is different from Bitbucket's `feature/WI01124535_MFA_IMPL_SDK2`. Tell its owner if it matters.

---

## 11. Quick reference (after the cut-over)

| Need | Command |
|---|---|
| Where does origin point? | `git remote -v` |
| Branches on GitHub | `git ls-remote --heads origin` |
| Local vs GitHub in sync? | `git fetch origin; git rev-list --left-right --count 'HEAD...@{u}'` (expect `0 0`) |
| My permissions on the repo | `gh api repos/wtg-e2open/INTTRA.mercury-services-commons --jq .permissions` |
| Look at an old Bitbucket-only branch | `git log --oneline -5 bitbucket/<branch>` |
| Restore an old Bitbucket branch locally | `git switch -c <branch> bitbucket/<branch>` (don't push it unless that's agreed) |
| New sub-branch off the feature branch | `git switch -c feature/ION-12310-<topic> feature/ION-12310-commons-cloudsdk-refactoring` then `git push -u origin feature/ION-12310-<topic>` |
| Open a PR | `gh pr create --base feature/ION-12310-commons-cloudsdk-refactoring --title "WI01124532 ..."` |
| Merge a PR into the feature branch (passes `COMMIT_CHECK`) | `gh pr merge N --merge --subject "WI01124532 Merge pull request #N: TITLE"` |
| Re-read a ruleset if a push is rejected | `gh api repos/wtg-e2open/INTTRA.mercury-services-commons/rulesets/27417088` |
| Token rejected (SAML) | open https://github.com/orgs/wtg-e2open/sso, then `gh auth refresh -h github.com` |
