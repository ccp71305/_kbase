# GitHub CLI (`gh`) commands

← [Index](README.md) · [How-to: GitHub rulesets](../howto/github-rulesets.md)

`gh` uses the login of `gh auth login` (ArijitKunduWTG); every command here runs against `wtg-e2open/INTTRA.appianway`, the repository of the current folder.

<a id="open-pr"></a>
## Listing PRs and opening one

```bash
gh pr list --state all --limit 4 --json number,title,baseRefName,headRefName \
  --jq '.[] | "\(.number) \(.baseRefName) <- \(.headRefName): \(.title)"'
```

Lists the last four PRs (open and closed) as one line each. `--json` chooses the fields; `--jq` formats them with a jq expression (`\(.field)` inserts a value). Used to match the title and base-branch conventions of the earlier service PRs.

```bash
git push -u origin WI01124532-aws-sdk-upgrade-transformer
gh pr create --base feature/WI01124532-aws-sdk-upgrade --head WI01124532-aws-sdk-upgrade-transformer \
  --title "WI01124532 transformer: …" --body-file <scratchpad>/pr-body.md
```

Publishes the sub-branch and records its upstream ([9.1](git.md#s9-1)), then opens the PR against the feature branch (never `develop`). `--body-file` reads the description from a file (Part 1 of the PR description document, between the `✂` lines), which avoids shell-quoting problems with backticks and tables. The command prints the PR URL.

<a id="read-pr"></a>
## Reading a PR, its reviews and comments

```bash
gh pr view 9 --json state,reviewDecision,comments,reviews \
  --jq '{state,reviewDecision,comments:[.comments[]|{author:.author.login,body}],reviews:[.reviews[]|{author:.author.login,state}]}'
```

Shows PR #9's state and every comment and review in one JSON object. `--json` picks the fields; in `--jq`, `{state,reviewDecision}` is shorthand for `{state: .state, reviewDecision: .reviewDecision}`, and `[.comments[] | {…}]` builds a list with one small object per comment. Result 2026-11-20 morning: open, one automated `copilot-pull-request-reviewer` review ("No open issues"), no human review yet.

```bash
gh pr view 9 --json title,body,headRefOid,reviews,comments \
  --jq '{title,head:.headRefOid,body,reviews:[.reviews[]|{author:.author.login,state,body,submittedAt}],comments:[.comments[]|{author:.author.login,body}]}'
gh api repos/{owner}/{repo}/pulls/9/comments --paginate \
  --jq '.[]|{id,user:.user.login,path,line,in_reply_to_id,commit:.commit_id[0:8],body}'
```

The first command reads the description, the head commit and every **review** (with its summary text, such as Copilot's overview) and every **conversation comment**. Inline code comments are not part of `gh pr view`; the second command reads them from the REST API.
- `gh api <path>` calls the GitHub REST API with the `gh` login. `{owner}/{repo}` are filled in by `gh` from the current repository's remote.
- `--paginate` follows the "next page" links, so all comments come back, not only the first 30.
- In `--jq`, `.[]` walks the list; `commit_id[0:8]` keeps the first 8 characters; `in_reply_to_id` shows which comment a reply answers.
- Result 2026-11-20 for PR #9: one Copilot review ("Needs a closer look", no inline comments), so the answer was a PR comment, not a reply in a thread.

<a id="update-pr"></a>
## Updating a PR's description and answering a review

```bash
gh pr view 9 --json body --jq .body > $S/pr9-body-before.md
python -I -c "…replace the text from '## Next Steps' to '## Testing Notes'…"   # writes pr9-body-after.md
gh pr edit 9 --body-file $S/pr9-body-after.md
gh pr view 9 --json body --jq .body | grep -c "Verified on QA (2026-11-20)"
gh pr comment 9 --body-file $S/pr9-copilot-reply.md
```

- `--jq .body` prints the description as plain text (not JSON-quoted), so it is saved exactly as on GitHub and can be edited as a file. The saved copy is also the undo.
- The new section is put in with Python, by heading text, not by line number, so nothing else in the description can change. `diff before after` then shows that only that section changed.
- `gh pr edit --body-file` replaces the whole description with the file. Reading it back and counting a phrase of the new text (`grep -c`, prints the number of matching lines; 1 expected) proves the edit landed.
- `gh pr comment --body-file` adds a conversation comment and prints its URL. GitHub notifies anyone named with `@`, so the text names no one.
- A review can be re-requested only by the PR author in the web page (Copilot: "Re-request review"). The CLI command `gh pr edit --add-reviewer` does not work for Copilot.
- **Pitfall (PR #11, 2026-11-20):** reading `gh pr view --json body` from Python with `subprocess.run(..., text=True)` decodes it with the Windows code page (cp1252), not UTF-8; writing that back turned every non-ASCII character into mojibake (`✅` → `âœ…`). Either save the body with a shell redirect (`> file`, as above) and open the file with `encoding='utf-8'`, or pass `encoding='utf-8'` to `subprocess.run`. Safest: rebuild the body from the PR document file, which is the source.

