# Git commands

← [Index](README.md) · [Tracker home](../README.md)

Run from the repository root in Git Bash. Commit rules: [G1](../rules.md#g1); never `git add -A` at the root.

<a id="s9-1"></a>
## Branches

```bash
git fetch origin
```

Downloads the latest commits and branch pointers from the remote (`origin`) without changing your working tree or local branches. Run it before cutting a branch so you start from the current `develop`.

```bash
git branch feature/WI01124532-aws-sdk-upgrade origin/develop
git branch --unset-upstream feature/WI01124532-aws-sdk-upgrade
```

Creates the feature (integration) branch at the same commit as the remote `develop`, without switching to it. `git branch <name> <start-point>` sets `origin/develop` as the upstream automatically; `--unset-upstream` removes that link so a later `git push` cannot accidentally target `develop`. The upstream is set to the branch's own remote name at the first push (below).

```bash
git checkout -b WI01124532-aws-sdk-upgrade-pom feature/WI01124532-aws-sdk-upgrade
```

`-b` creates a new branch and switches to it in one step. The last argument is the start point: every sub-branch starts from the tip of the feature branch, never from `develop`.

```bash
git push -u origin feature/WI01124532-aws-sdk-upgrade
```

Publishes the branch to the remote. `-u` (`--set-upstream`) records `origin/feature/WI01124532-aws-sdk-upgrade` as its upstream, so later `git push` / `git pull` on that branch need no arguments.

<a id="s9-2"></a>
## Commits, test first

```bash
git add shared/src/test/java/.../SomeUnitTest.java
git commit -m "WI01124532 red: <what the test expects>"
```

Stage files **by explicit path**. Never `git add -A` or `git add .` at the root: they would also stage the untracked `docs/`, `.claude/`, module `docs/` folders and `*.code-workspace`. The `red:` commit contains only the new failing test; the `green:` commit contains the production change that makes it pass; `refactor:` contains cleanup with all tests still green. The message must start with `WI01124532` ([G1](../rules.md#g1)).

```bash
git commit --amend -m "WI01124532 <corrected message>"
```

Replaces the message (and content, if files are staged) of the last commit. Use it **only before the commit is pushed**; after a push, rewriting it requires a force push.

```bash
git status --short
git diff --cached --stat
```

`--short` gives a compact one-line-per-file status (`M` modified, `A` added, `??` untracked). `diff --cached --stat` lists what is staged (what the next commit will contain) with line counts. Check both before every commit.

```bash
git log --oneline --first-parent feature/WI01124532-aws-sdk-upgrade
```

`--first-parent` follows only the first parent of each merge commit, so on the feature branch it shows one line per merged sub-branch PR (the review history), not every commit inside each PR.

<a id="s9-3"></a>
## Keeping the feature branch current (plan §9.5)

```bash
git rebase --rebase-merges develop
git push --force-with-lease
```

Replays the feature branch on top of the latest `develop`. `--rebase-merges` keeps the sub-branch PR merge commits (a plain rebase would flatten them into a straight line). Because the history is rewritten, the push must be forced; `--force-with-lease` refuses if someone else pushed to the branch since your last fetch, unlike `--force`, which overwrites blindly.

```bash
git rebase --onto <new-feature-tip> <old-feature-tip> <sub-branch>
```

Moves an open sub-branch after the feature branch was rebased: takes the commits that are in `<sub-branch>` but not in `<old-feature-tip>` and replays them on `<new-feature-tip>`.

<a id="history"></a>
## Commit messages, history and checks before a push

```bash
git commit -q -F - <<'EOF'
WI01124532 green: <summary line>

<body: what changed and why>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
```

`-F -` reads the commit message from standard input; the here-document (`<<'EOF' … EOF`) supplies a multi-line message exactly as written (the quotes around `EOF` stop Bash from expanding `$` or backticks inside). `-q` suppresses the summary output. The first line must start with `WI01124532` (GitHub ruleset); the message ends with a newline, which `git commit` keeps ([no commit-tree workaround](../rules.md)).

```bash
git checkout -- <file> <file>
```

Discards uncommitted changes to those files, restoring them from the last commit. Used after checking the known-defect fixes: the fixes were applied only in the working tree, the tests run, then this command removed them; `git status --short` then showed no modified production file.

```bash
git log --format="%ad %s" --date=short -S"retry = 0" -- <path>
```

"Pickaxe" search: `-S<text>` lists only the commits that changed the number of occurrences of that text, i.e. the commit that introduced (or removed) it. `--format="%ad %s" --date=short` prints the author date and subject. Used to date each known defect ("since March 2019").

```bash
git fetch -q origin feature/WI01124532-aws-sdk-upgrade
git rev-parse --short origin/feature/WI01124532-aws-sdk-upgrade
git merge-base --is-ancestor origin/feature/WI01124532-aws-sdk-upgrade HEAD && echo up-to-date
```

Before pushing a sub-branch: fetch only the feature branch, print its tip as a short hash, and check that the tip is an ancestor of `HEAD` (exit code 0 if yes), i.e. the sub-branch already contains everything on the feature branch and needs no rebase.

```bash
git log --reverse --format="%h %s" 222d58be..HEAD
git diff --stat 222d58be..HEAD | tail -1
git show --stat --format=%B <commit>
```

`A..B` = commits reachable from B but not A: the sub-branch's own commits since it was cut. `--reverse` lists them oldest first (the order of the review guide). `diff --stat … | tail -1` gives the summary line (files changed, insertions, deletions). `show --stat --format=%B` prints one commit's full message and the files it touched.

```bash
git worktree list
git -C ../appianway-build status --short
```

Lists every worktree with its checked-out commit; the second line checks the build worktree is clean before moving it to another commit.
