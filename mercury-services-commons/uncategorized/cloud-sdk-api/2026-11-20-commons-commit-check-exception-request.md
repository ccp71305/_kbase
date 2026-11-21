# Request: `COMMIT_CHECK` exception to merge `develop` into the SDK-Commons feature branch

**Repository:** https://github.com/wtg-e2open/INTTRA.mercury-services-commons
**Branch:** `feature/ION-12310-commons-cloudsdk-refactoring` (work item WI01124532 / ION-12310)
**Ruleset:** `COMMIT_CHECK` (id 27417088), all branches except `develop` and `master`, pattern `^WI\d+(?:\s*[:\-]\s*|\s+).+`
**Requested by:** GitHub user `ArijitKunduWTG` (write access, not admin)
**Date:** 2026-11-20

---

## In short

We need to merge `develop` into our long-running SDK-Commons feature branch. GitHub rejects the push because **two commits that already exist on `develop`** don't match the commit-message pattern. They are **Bitbucket-era PR merge commits** (`Pull request #56: …` and `Pull request #58: …`), created before the move to GitHub. We can't change their messages without rewriting `develop`'s history.

**We are asking for a way to push this merge**: preferably by excluding this one branch from the rule (options below).

## The branches

```text
                    8c6fcef  (last common point)
                       │
       ┌───────────────┴────────────────────────────────┐
       │                                                │
   develop (6 new commits since 8c6fcef)            feature/ION-12310-commons-cloudsdk-refactoring
       │                                                │  95 commits of SDK work
   0c7ff23  WI01128840 content security policy …  ✅     │  (published as commons 1.0.38 / 1.0.39-SNAPSHOT,
   ce373b6  WI01128840 CSP filter test case …     ✅     │   used by mercury-services and appianway)
   cb447a4  WI01128840 content security policy …  ✅     │
   b16ccd6  Pull request #56: WI01128840 …        ❌     │
   e28bef0  WI01149458:T78662935 - Commons …      ✅     │
   f15b1e1  Pull request #58: WI01149458 …        ❌     │
       │                                                │
       │  tip f15b1e1                                   │  tip aa52175   (on GitHub)
       └──────────────────────┬─────────────────────────┘
                              │
                          f661c95  WI01124532 ION-12310 merge develop … ✅
                              (the merge we want to push: ready, built and tested)
```

❌ = starts with `Pull request #…`, so it doesn't match `^WI\d+…`. These were Bitbucket's standard PR merge messages.

---

## What happened

```text
git push origin feature/ION-12310-commons-cloudsdk-refactoring        (aa52175 → f661c95)

remote: error: GH013: Repository rule violations found for refs/heads/feature/ION-12310-commons-cloudsdk-refactoring.
remote: - Commit message must match a given regex pattern: ^WI\d+(?:\s*[:\-]\s*|\s+).+
remote:   Found 2 violations:
remote:   f15b1e1a292d143cf1d5d96db8a43bdc25f9c58f
remote:   b16ccd69b211848796ff511e714a0cd91769f7c9
 ! [remote rejected] … (push declined due to repository rule violations)
```

On a branch update, the rule checks **every commit being added to the branch**, including commits already on `develop`. Our own merge commit passes. Only develop's two commits fail.

---

## What we need (any one of these)

| # | Change | Scope | Notes |
|---|---|---|---|
| **1 (preferred)** | Add `refs/heads/feature/ION-12310-commons-cloudsdk-refactoring` to the ruleset's **exclude** list | one branch | until the branch is merged into `develop`. Also covers later `develop` syncs without asking again. The rule stays in force for all other branches, and our own commits keep using the `WI…` prefix |
| 2 | Add a **bypass** to `COMMIT_CHECK` for `ArijitKunduWTG` (or a team they're in) | one user | we push the one merge, then the bypass can be removed. Needed again each time `develop` is merged in |
| 3 | Widen the pattern so the old Bitbucket merge messages pass (example below) | all branches | fixes it for every team syncing old `develop` history, but loosens the rule slightly |

Example pattern for option 3:

```text
^(WI\d+(?:\s*[:\-]\s*|\s+).+|Pull request #\d+: .+)
```

No other rule needs to change. `develop` stays protected by `PR_CHECK` (PR, 1 approval, `PR_BUILD`), and the feature branch will reach `develop` through a normal PR later.

---

## Current state (nothing is broken)

| Branch (GitHub) | Commit | State |
|---|---|---|
| `develop` | `f15b1e1` | unchanged |
| `feature/ION-12310-commons-cloudsdk-refactoring` | `aa52175` | unchanged, normal work continues |
| `backup/feature-ION-12310-pre-develop-merge-2026-11-20` | `aa52175` | safety copy |

The merge commit (`f661c95`) is built and tested, together with the client apps that use commons, and is ready to push.

Once one of the changes above is in place, we push the merge with a **normal push**: no force-push, and no existing commits are changed.

---

## Background: why we merge `develop` into the SDK-Commons feature branch

- **The feature branch is a released line.** It is the AWS SDK v2 / cloud-sdk version of commons. Client apps already use its snapshots: the upgraded mercury-services modules use `1.0.38-SNAPSHOT` and appianway uses `1.0.39-SNAPSHOT`.
- **It can't go into `develop` yet.** That happens through a normal PR, once every client app has moved to the SDK line. Until then, `develop` still serves the apps on the old AWS SDK 1 line, such as oceanschedules.
- **`develop` has fixes the SDK line must carry.** It now has a CSP filter (PR #56) and JFrog Xray vulnerability fixes (PR #58). Merging them now lets the SDK apps get those fixes in the next snapshot (`1.0.40`).
- **The merge is recorded in git.** Later syncs and the final PR don't repeat the conflict work.
- **Why not rebase:** it would rewrite all 95 published commits and need a force-push, and it would still include the same two `develop` commits.
- **Why locally:** GitHub's "Update branch" button would create a merge commit without the `WI…` prefix.

Thank you.
