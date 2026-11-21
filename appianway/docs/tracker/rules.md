# Working rules and local guards

← [Tracker home](README.md)

## Working rules


| Rule | Detail |
|---|---|
| Branches | Feature (integration) branch `feature/WI01124532-aws-sdk-upgrade`. One sub-branch `WI01124532-aws-sdk-upgrade-<step or module>` per step or module, cut from the feature branch, one PR each into it (merge commit, no squash). Final single PR feature → `develop` |
| Work item id | **Every commit message starts with `WI01124532`** (the Bitbucket hook rejects commits without it), including local merge commits. **Every PR title starts with `WI01124532`**, because the Bitbucket merge commit is `Pull request #N: <title>`. Enforced locally by the `commit-msg` hook ([G1](#g1)). **On GitHub (2026-11-17)** the ruleset `Commit_Check` enforces it on every branch except `develop` / `master`: message must match `^WI\d+(?:\s*[:\-]\s*\|\s+).+` (the work item id, then a space, `:` or `-`, then text). The repo's default merge-commit message is GitHub's `Merge pull request #N from …` (`merge_commit_title = MERGE_MESSAGE`), which does **not** match, so when merging a sub-PR into the feature branch, set the merge commit message to start with `WI01124532` (in the merge dialog, or `gh pr merge N --merge --subject "WI01124532 Merge pull request #N: TITLE"`) |
| TDD | Red → green → refactor: one commit for the failing test (`WI01124532 red: …`), one for the change that makes it pass (`WI01124532 green: …`), one for the cleanup (`WI01124532 refactor: …`, when there is something to refactor). Build-infrastructure changes that cannot fail a test first are committed on their own (`WI01124532 build: …`) and proven by the test-count check |
| Tests | New test classes: JUnit 5 (Jupiter) + AssertJ, one class per unit under test. Existing JUnit 4 tests unchanged (Vintage engine) |
| **Naming ([D25](decisions.md#d25), PR #80 review)** | Client code (`shared` and the services) is **implementation-agnostic**: new classes, methods, fields, constants and test names use the **cloud-sdk-api concepts**, never the AWS service or SDK names. **messaging / message queue** (not SQS), **notification** (not SNS), **storage** (not S3), **parameter store** (not SSM), **email** (not SES), **database** (not DynamoDB), **cloud service** (not "cloud-sdk" / "AWS" in our own names). Examples: `MessageQueueListener`, `MESSAGING_QUEUE_MAX_MESSAGES_PER_RECEIVE`, `CloudServiceFailures`, `ClientSettings.messageQueueListener()` / `messageQueueSender()` / `storage()` / `notification()`, `ClientProfile.messaging()` / `storage()` / `notification()`. **Allowed exceptions:** (1) types we import and cannot rename (`AwsMessagingClientConfig`, `S3OperationException`, `CloudSdkException`, AWS SDK types inside `ClientProfile`); (2) existing v1 code and its names until step 5 deletes it (`SQSClient`, `SQSListener`, `AWSClientConfiguration.sqs_listener`, `getSqsPickupConfig`), and tests that characterise v1; (3) comments stating an AWS fact (e.g. the SQS 10-message limit) or naming the v1 setting a value keeps; (4) operational strings that must not change: log texts kept from v1 (`"Exception in SQS Listener :"`), health-check names, configuration keys, metric names; (5) tests that are about the AWS boundary itself (`AwsSdkBoundaryArchTest`); (6) fixture data such as queue URLs and topic ARNs |
| Backward compatibility | Wire, storage and configuration formats identical (contract C1–C9, `shared` design) |
| Performance | No extra round trips, downloads or client instances compared with today; listener back-pressure kept |
| Upstream commons asks | Fallbacks first (U1, U2, U4, U5, U6, U7, U10); U3, U8, U9: see [A1](actions.md#a1)–[A2](closed-items.md#a2) |
| **Commits: normal `git commit` only** | Never build commits with `git commit-tree` or strip the message's final newline to get past GitHub's commit rule. That 2026-11-16 workaround (mercury-services PR #1) dropped the `Co-Authored-By` line, and it is not needed since the rule's trailing `$` was removed ([GitHub rulesets how-to](howto/github-rulesets.md)). If a push is rejected for the message, stop and re-check the ruleset ([GitHub rulesets how-to](howto/github-rulesets.md) step 3). Don't rewrite the commit. Checked 2026-11-17: no git alias, hook or script uses `commit-tree`, and the 1d commits `0534f2c3`…`28c65967` are normal multi-line commits ending in a newline |
| Staging | Stage by explicit path only; never `docs/`, `.claude/`, `.vscode/`, `*.code-workspace`, module `docs/` |
| Build gate | Full reactor `mvn clean verify` green before every PR; test counts = baseline + new tests |

<a id="local-guards"></a>
## Local guards and tooling (G#)


Local setup that protects the workflow. None of it is committed; re-create it on a new clone.

| # | What | Where | Why | How to check |
|---|---|---|---|---|
| <a id="g1"></a>[G1](#g1) | `commit-msg` hook rejecting messages whose first line does not start with `WI01124532` | `.git/hooks/commit-msg` (executable) | Bitbucket's server hook rejects pushes containing commits without the work item id; catching it locally avoids rewriting pushed history | `git commit --allow-empty -m "test"` must fail with `commit-msg: first line must start with WI01124532` (verified 2026-10-31) |
| <a id="g2"></a>[G2](#g2) | Resolver flag `-Daether.enhancedLocalRepository.trackingFilename=_any.repositories` on local full builds | Command line ([commands: Maven builds](commands/maven.md#s9-4)) | Lets Maven 3.9 use the cached `dynamo-client:1.0` for `registration-inbound-consumers` (finding [F1](findings.md#f1)) | The full reactor build gets past `registration-inbound-consumers` |
| <a id="g4"></a>[G4](#g4) | Full reactor builds run in a separate git worktree `C:\Users\arijit.kundu\projects\appianway-build` (detached at the commit under test, pending changes applied as a patch) | `git worktree` outside the VS Code workspace | VS Code (`java.autobuild.enabled: true`, `java.configuration.updateBuildConfiguration: automatic`) rebuilds modules into the same `target/classes` while Maven runs, which deletes compiled classes mid-build ([F7](findings.md#f7)) | Build log shows only Maven writing to `target/` |
| <a id="g3"></a>[G3](#g3) | Build logs and test-count snapshots | Session scratchpad (`baseline-build.log`, `baseline-counts.txt`) | Evidence for the test-count check in each PR description | — |

Hook source ([G1](#g1)):

```sh
#!/bin/sh
# Local guard: Bitbucket rejects pushes whose commits lack the work item id.
if ! head -1 "$1" | grep -q '^WI01124532'; then
  echo "commit-msg: first line must start with WI01124532" >&2
  exit 1
fi
```

Git runs `commit-msg` after the message is written and before the commit is created, passing the path of the message file as `$1`. `head -1` takes the subject line; `grep -q '^WI01124532'` checks that it starts with the work item id (`-q` = quiet, only the exit code matters). Exit code 1 aborts the commit. The hook also runs for `git merge` commits. Rebases replay existing messages without re-running it, which is fine because those messages already passed. Install: save the file as `.git/hooks/commit-msg`, then `chmod +x .git/hooks/commit-msg`.
