# How-to: verification walkthroughs and command logs

← [Tracker home](../README.md)


Added 2026-11-17. This section shows how two facts in this tracker were checked, command by command, so you can repeat the checks yourself:

1. Which GitHub rules apply to `develop` and to the feature branches, and what the local commit hook does ([GitHub rulesets how-to](../howto/github-rulesets.md), [commit hook how-to](../howto/commit-msg-hook.md)).
2. That commons **1.0.39-SNAPSHOT** really reached the shared Maven repository after the Jenkins publish, and how the 4.7 MB Jenkins log was read ([commons publish how-to](../howto/commons-publish-check.md)).

Every command is read-only. Nothing in this section changes GitHub, the repository or the Maven repository.

| Page | What it shows |
|---|---|
| [build-and-run-a-service-locally.md](build-and-run-a-service-locally.md) | Building v1 and the new build of a service in the build worktree and running both locally against QA: every command and option explained, the start/stop scripts, collect / compare / cleanup, pitfalls |
| [tools-and-shells.md](tools-and-shells.md) | Git Bash, PowerShell, gh, mvn: which tool for what |
| [github-rulesets.md](github-rulesets.md) | Reading the GitHub rulesets (Commit_Check, PR_CHECK) step by step |
| [commit-msg-hook.md](commit-msg-hook.md) | The local commit-msg hook ([G1](../rules.md#g1)): source and how it works |
| [commons-publish-check.md](commons-publish-check.md) | Proving commons 1.0.39-SNAPSHOT was published (Jenkins log, maven-metadata, jar content) |
| [bash-powershell-cheatsheet.md](bash-powershell-cheatsheet.md) | Bash and PowerShell equivalents |
| [2026-11-09-develop-merge.md](2026-11-09-develop-merge.md) | Command log: merging develop into the feature branch and re-basing 1c ([A25](../closed-items.md#a25)), PR #80 review fix |
