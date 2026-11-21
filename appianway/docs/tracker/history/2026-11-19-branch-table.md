# R.1 Where things stand

← [History index](README.md) · [Tracker home](../README.md)

> Snapshot as written at the time. The IDs link to the current items.


| Branch | Based on | Remote | Tip | State |
|---|---|---|---|---|
| `feature/WI01124532-aws-sdk-upgrade` (feature) | `develop` `0448d362`; `develop` `4cc7b99f` merged in 2026-11-09 | GitHub `origin/feature/WI01124532-aws-sdk-upgrade` | **`ff281fa1`** (PR #5 merge, 2026-11-19; before it `62b07687` PR #4, `58aee71b` PR #3, `673a3d65` PR #2, `fa3efede` PR #80) | Renamed and pushed to GitHub 2026-11-17 (`git push -u`). The old name `WI01124532-aws-sdk-upgrade` stays on GitHub (and on Bitbucket, read-only) as a frozen copy. Remote: `https://github.com/wtg-e2open/INTTRA.appianway.git`; Bitbucket = remote `bitbucket` (read-only) |
| `WI01124532-aws-sdk-upgrade-pom` (1a) | feature | pushed | `6bb9ae6c` | ✅ **PR #76 merged** 2026-11-02 (`a9a7afbb`) |
| `WI01124532-aws-sdk-upgrade-shared-config` (1b) | feature (rebased 2026-11-02) | **pushed** 2026-11-02 | `bbe0be17` | ✅ **PR #78 merged** (`f64fa017`). PR description / walkthrough: `docs/redesign/pr-details/2026-10-31-apway-pr-1b-shared-config-description.md` |
| `WI01124532-aws-sdk-upgrade-shared-runtime` (1c) | feature `34c8fe4e` (rebased 2026-11-09) | deleted on merge (local copy remains) | `0dc30210` (13 commits) | ✅ **PR #80 merged** 2026-11-10 (`fa3efede`); description `pr-details/2026-10-31-apway-pr-1c-shared-runtime-description.md` |
| `WI01124532-aws-sdk-upgrade-shared-adapters` (1d) | feature `fa3efede` | deleted on merge (local copy deleted too) | `366d13f7` (29 commits) | ✅ **PR #2 merged** 2026-11-18 (`673a3d65`); Copilot comment fixed ([D32](../decisions.md#d32)), replied, resolved |
| `WI01124532-aws-sdk-upgrade-functional-testing` (1e) | 1d `366d13f7` (stacked; PR retargeted to the feature branch after #2 merged) | deleted on merge (local copy deleted too) | `78b936f8` (12 commits) | ✅ **PR #3 merged** 2026-11-18 (`58aee71b`); 2 Copilot comments fixed ([D35](../decisions.md#d35), [D36](../decisions.md#d36)), replied, resolved |
| `WI01124532-aws-sdk-upgrade-event-writer` (2) | feature `58aee71b` | deleted on merge (local copy deleted too) | `89a6077d` (13 commits) | ✅ **PR #4 merged** 2026-11-19 (`62b07687`); 4 Copilot rounds (shutdown drain, close order, real-client test, INT check [A27](../actions.md#a27)), threads resolved |
| `WI01124532-aws-sdk-upgrade-error-processor` (2) | feature `62b07687` (rebased 2026-11-19) | deleted on merge (local copy deleted too) | `a36edccc` (15 commits) | ✅ **PR #5 merged** 2026-11-19 (`ff281fa1`); pre-reviewed, no Copilot comments ("Approval recommended") |

Working tree: on `feature/WI01124532-aws-sdk-upgrade` at `ff281fa1`, clean except untracked docs / IDE files (never staged). Build worktree `C:\Users\arijit.kundu\projects\appianway-build` exists (detached; safe to reuse or `git worktree remove`).
