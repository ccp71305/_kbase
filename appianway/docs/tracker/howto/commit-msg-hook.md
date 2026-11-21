# Local commit hook (`commit-msg`)

← [How-to index](README.md) · [Tracker home](../README.md)


Git hooks are scripts that Git runs at certain moments. They live in the clone (`.git/hooks/`), so they are **never pushed** and must be re-created on a new clone ([local guards](../rules.md#local-guards) [G1](../rules.md#g1)).

```bash
git config --get core.hooksPath            # empty (exit code 1) = default location is used
git rev-parse --git-path hooks             # -> .git/hooks   (the real hooks folder, also correct inside worktrees)
ls -la "$(git rev-parse --git-path hooks)" | grep -v sample
cat "$(git rev-parse --git-path hooks)/commit-msg"
```

| Part | Meaning |
|---|---|
| `git config --get core.hooksPath` | prints the custom hooks folder if one is set. No output and **exit code 1** means "not set", which is not an error |
| `git rev-parse --git-path hooks` | asks Git where its `hooks` folder really is. Safer than typing `.git/hooks`, because in a linked worktree `.git` is a file, not a folder |
| `$( … )` | command substitution: run the inner command and paste its output |
| `ls -la` | long listing including hidden files. An `x` in `-rwxr-xr-x` means executable, which Git requires |
| `grep -v sample` | `-v` inverts the match: hide the `*.sample` files Git ships by default |

Result: `commit-msg` exists and is executable:

```sh
#!/bin/sh
# Local guard: Bitbucket rejects pushes whose commits lack the work item id.
if ! head -1 "$1" | grep -q '^WI01124532'; then
  echo "commit-msg: first line must start with WI01124532" >&2
  exit 1
fi
```

How the local hook and the server rule fit together:

```text
 git commit ──► .git/hooks/commit-msg ──► commit created locally ──► git push ──► GitHub Commit_Check ──► branch updated
                (local, ^WI01124532)                                               (server, ^WI\d+ …)
                stricter: only this WI                                             any WI number

 gh pr merge ──────────────────────────────────────────────────────► merge commit made ON GitHub
                (local hook does NOT run)                            Commit_Check still applies -> use --subject "WI01124532 …"
```

| | Local `commit-msg` hook | GitHub `Commit_Check` |
|---|---|---|
| Runs when | `git commit` on this machine | a push, or a merge made on GitHub |
| Pattern | `^WI01124532` | `^WI\d+(?:\s*[:\-]\s*\|\s+).+` |
| Skippable | yes, with `git commit --no-verify` (don't) | no (no bypass actors) |
| Shared with team | no | yes |

PowerShell versions:

```powershell
git config --get core.hooksPath; "exit=$LASTEXITCODE"     # $LASTEXITCODE = exit code of the last native command
Test-Path .git\hooks\commit-msg                           # True / False
Get-Content .git\hooks\commit-msg
```
