# Commands: index

← [Tracker home](../README.md)

The commands that matter for this work, one page per tool, each with its syntax explained. Run from the repository root (`C:\Users\arijit.kundu\projects\appianway`) in Git Bash unless the page says otherwise. AWS CLI commands have their own pages: [runtime/aws/](../runtime/aws/README.md). Step-by-step procedures that use these commands: [howto/](../howto/README.md).

| Page | What is in it |
|---|---|
| [git.md](git.md) | Branches, test-first commits, keeping the feature branch current, history searches, checks before a push |
| [maven.md](maven.md) | Full and module builds, the module loop (`-o`, UTC, `install` of `shared`), single tests, dependency trees, the test-count check |
| [build-worktree.md](build-worktree.md) | The separate build worktree (G4), the full build before a PR, building v1 and the new build of one service for a runtime test |
| [github-cli.md](github-cli.md) | Listing and opening PRs, reading reviews and comments, updating a description, answering a review |
| [local-run.md](local-run.md) | Starting a service jar locally, the start and Ctrl+C scripts, waiting for the start, the health check, stopping |
| [shell-tools.md](shell-tools.md) | Probing the internal Maven site with `curl`, finding where a value comes from with `grep` |

Where to add a new command: on the page of its tool, next to the closest existing one, with what each option does and the result it gave. A test's own step log stays on its runtime page and links here instead of repeating the explanation.

<a id="by-step"></a>
## Commands by step (where the old date sections went)

| Old section | Now |
|---|---|
| 9.1–9.3 Git | [git.md](git.md) |
| 9.4 Maven builds, 9.6 test-count check | [maven.md](maven.md) |
| 9.5 Build worktree | [build-worktree.md](build-worktree.md) |
| 9.7 Commands added during the transformer step (2026-11-20) | Maven: [maven.md#module-loop](maven.md#module-loop) and [build-worktree.md#full-build](build-worktree.md#full-build). Git: [git.md#history](git.md#history). GitHub CLI: [github-cli.md#open-pr](github-cli.md#open-pr) |
| 9.8 Commands for transformer's runtime test 6 (2026-11-20) | PR status: [github-cli.md#read-pr](github-cli.md#read-pr). Maps on the Maven site, `grep` for map names: [shell-tools.md](shell-tools.md). Building the two jars: [build-worktree.md#two-jars](build-worktree.md#two-jars). Start, health, stop: [local-run.md#start-check-stop](local-run.md#start-check-stop). AWS part: [runtime/aws/README.md#by-test](../runtime/aws/README.md#by-test) |
| PR #9 update and the Copilot reply (2026-11-20) | [github-cli.md#update-pr](github-cli.md#update-pr) |
