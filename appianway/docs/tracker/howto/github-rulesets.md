# GitHub rulesets for `develop` and the feature branches

← [How-to index](README.md) · [Tracker home](../README.md)


GitHub has two ways to protect branches:

- **Classic branch protection**, set per branch. It's read with `/branches/<name>/protection`.
- **Rulesets**, which are named rule sets that target branches by pattern. They're read with `/rulesets` and `/rules/branches/<name>`.

AppianWay uses **rulesets only**. The checks below show how to tell.

### Step 1 — Is `develop` protected, and by what?

```bash
gh api $R/branches/develop --jq '{protected, protection}'
gh api $R/branches/develop/protection
```

| Part | Meaning |
|---|---|
| `gh api $R/branches/develop` | GET the branch object for `develop` |
| `--jq '{protected, protection}'` | jq **object construction**: build a new object with just those two keys (shorthand for `{protected: .protected, protection: .protection}`) |
| `/branches/develop/protection` | GET the **classic** protection settings |

Output and what it tells you:

```text
{"protected":true,"protection":{"enabled":false,"required_status_checks":{...,"enforcement_level":"off"}}}
{"message":"Not Found", ... "status":"404"}      <- from /protection
```

`protected: true` together with classic protection `enabled: false` and a **404** on `/protection` means a **ruleset** protects the branch, not classic protection.

### Step 2 — List the rulesets

```bash
gh api $R/rulesets --jq '.[] | "\(.id) \(.name) \(.enforcement)"'
```

| Part | Meaning |
|---|---|
| `.[]` | iterate over each element of the JSON array |
| `\|` (pipe, inside jq) | feed each element into the next expression |
| `"\(.id) \(.name) …"` | jq **string interpolation**: `\( … )` inserts a value into a string |

```text
27406203 Commit_Check active
27406223 PR_CHECK active
```

`enforcement` can be `active` (enforced), `evaluate` (logged only) or `disabled`.

### Step 3 — Read each ruleset in full

```bash
gh api $R/rulesets/27406203 --jq '{name, enforcement, conditions, rules, bypass_actors}'
gh api $R/rulesets/27406223 --jq '{name, enforcement, conditions, bypass_actors, rules: [.rules[] | {type, parameters}]}'
```

`rules: [.rules[] | {type, parameters}]` rebuilds the `rules` array, keeping only `type` and `parameters` for each rule. The `[ … ]` collects the results back into an array.

Results (2026-11-17):

| Ruleset | `conditions.ref_name` (which branches) | Rules | Bypass |
|---|---|---|---|
| **Commit_Check** `27406203` | include `~ALL`, exclude `refs/heads/develop`, `refs/heads/master` | `commit_message_pattern`: regex below | none |
| **PR_CHECK** `27406223` | include `~DEFAULT_BRANCH` (= `develop`) | `non_fast_forward` (no force-push); `pull_request` (1 approval, merge/squash/rebase allowed); `required_status_checks`: **`PR_BUILD`**, `strict: true` | none |

`~ALL` and `~DEFAULT_BRANCH` are GitHub's special targets. `~ALL` means every branch, and `~DEFAULT_BRANCH` means whichever branch is the repository default (`develop` here).

The Commit_Check pattern, as the API returns it (JSON doubles each backslash):

```text
"pattern":"^WI\\d+(?:\\s*[:\\-]\\s*|\\s+).+"      JSON text
           ^WI\d+(?:\s*[:\-]\s*|\s+).+            the actual regex
```

```text
^          start of the commit message (its first line)
WI         the literal letters W I
\d+        one or more digits                     -> 01124532
(?: … )    a group that is not captured
  \s*[:\-]\s*   optional spaces, then ":" or "-", then optional spaces   -> "WI01124532: x" / "WI01124532 - x"
  |             or
  \s+           one or more spaces                                        -> "WI01124532 refactor: …"
.+         at least one more character (a non-empty title)
```

| Message | Passes? |
|---|---|
| `WI01124532 refactor: rename CloudSdkFailures` | yes |
| `WI01124532: fix` | yes |
| `wi01124532 fix` | **no** (case-sensitive) |
| `Merge pull request #81 from …` (GitHub's default merge subject) | **no**, so set the merge subject yourself (see below) |
| `WI01124532` alone | **no** (`.+` needs a title) |

**History: the trailing `$` (2026-11-16).** The first version of this rule in both AppianWay and mercury-services ended in `.+$`. GitHub matches the pattern against the **whole** message, and `git commit` always ends the message with a newline. Without multi-line mode, `.` can't match that newline and `$` means "end of the whole text", so every normal commit failed, even a correct one-line message. mercury-services PR #1 (`e153cba1`) only got through because its message was rebuilt with `git commit-tree` and no final newline, which also dropped the `Co-Authored-By` line. The rule was then fixed: the `$` was removed (mercury-services `COMMIT_CHECK` updated 2026-11-17 03:45, AppianWay `Commit_Check` 04:01, US Eastern). With no `$`, the regex only has to match at the start, so multi-line messages with trailers and the final newline pass. **No local git setting is needed**, and the `commit-tree` workaround should not be used any more. Re-check with Step 3 if pushes start failing again. **Confirmed 2026-11-17:** the push of `WI01124532-aws-sdk-upgrade-shared-adapters` (4 multi-line commits with `Co-Authored-By`) was accepted.

### Step 4 — Ask GitHub which rules apply to one branch

This is the easiest check, because GitHub resolves all the rulesets for you:

```bash
gh api $R/rules/branches/develop --jq '.[].type'
gh api $R/rules/branches/feature/WI01124532-aws-sdk-upgrade --jq '.[] | {type, ruleset_id, parameters}'
gh api $R/rules/branches/WI01124532-aws-sdk-upgrade-shared-adapters --jq '.[] | "\(.type) \(.ruleset_id)"'
```

`/rules/branches/<branch>` returns the **effective** rules for that branch name, even for a branch that doesn't exist on GitHub yet. A `/` inside a branch name, as in `feature/...`, is fine in this path.

| Branch | Effective rules | Consequence |
|---|---|---|
| `develop` | `non_fast_forward`, `pull_request`, `required_status_checks` (all from PR_CHECK) | final PR needs 1 approval + green `PR_BUILD` + branch up to date with `develop` |
| `feature/WI01124532-aws-sdk-upgrade` | `commit_message_pattern` (Commit_Check) | every pushed commit, **merge commits included**, must start `WI<digits>` |
| `WI01124532-aws-sdk-upgrade-shared-adapters` (and other sub-branches) | `commit_message_pattern` | same. No required build, so no Jenkins "set build status" workaround needed |

When merging a sub-PR into the feature branch, give the merge commit a compliant subject:

```bash
gh pr merge 81 --merge --subject "WI01124532 Merge pull request #81: <title>"
```

### Step 5 — Who posts `PR_BUILD`?

```bash
gh api "$R/commits/84ba0912/status" --jq '.statuses[] | {context, state}'
gh api "$R/commits/05a1d8fb/check-runs" --jq '.check_runs[] | {name, app: .app.slug, conclusion}'
```

There are two kinds of CI result: **commit statuses** (`/status`, the older API, which Jenkins uses) and **check runs** (`/check-runs`, used by GitHub Apps). `PR_BUILD` appeared as a status (`{"context":"PR_BUILD","state":"success"}`), and the ruleset's `integration_id 5779704` ties it to the `inttra-jenkins-ci[bot]` app (Jenkins job `DEV_GIT_PR`). So only that bot can satisfy the check.
