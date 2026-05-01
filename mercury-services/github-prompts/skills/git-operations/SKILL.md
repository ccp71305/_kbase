---
name: git-operations
description: >
  **WORKFLOW SKILL** — Safe git rebase, merge, and branch management for feature branches.
  USE FOR: rebasing feature branches onto develop; resolving merge conflicts; squashing commits;
  force-pushing safely with --force-with-lease; branch cleanup.
  INVOKES: session context tools, git tools, terminal commands.
---

# Git Operations Skill

## Rebase Feature Branch onto Develop

Use this workflow when a feature branch needs to incorporate the latest changes from `develop`
while maintaining a clean single-commit history.

### Prerequisites
- Local `develop` branch is up to date: `git pull origin develop` (on develop)
- You are on the feature branch
- Working directory state is known (stash if needed)

### Workflow

#### 1. Assess Current State
```bash
# Confirm branch and single outgoing commit
git branch --show-current
git log --oneline develop..HEAD

# Find the merge base (where feature diverged from develop)
git merge-base develop HEAD

# Check for uncommitted changes
git status --short
```

#### 2. Stash Uncommitted Work (if any)
```bash
git stash --include-untracked -m "pre-rebase-stash"
```

#### 3. Analyze Incoming Changes & Conflict Risk
```bash
# Count commits on develop since divergence
MERGE_BASE=$(git merge-base develop HEAD)
git log --oneline $MERGE_BASE..develop | wc -l

# Find which develop commits touched YOUR module specifically
git log --oneline HEAD..develop -- <module>/

# Find files changed on BOTH branches (potential conflicts)
comm -12 \
  <(git diff --name-only $MERGE_BASE..HEAD | sort) \
  <(git diff --name-only $MERGE_BASE..develop | sort)

# For each overlapping file, compare the diffs to predict conflicts
git diff $MERGE_BASE..HEAD -- <file>
git diff $MERGE_BASE..develop -- <file>
```

**Conflict risk levels:**
- **No overlapping files** → safe, no conflicts
- **Overlapping file, different line regions** → git auto-resolves; always run `mvn test-compile` after (see step 6)
- **Different changes to same lines** → manual conflict resolution needed

> **Key insight for API-migration branches**: Even when git auto-resolves (changes in different sections),
> new files introduced by `develop` may import classes your branch renamed or removed.
> Always run `mvn test-compile` after rebase before pushing.

#### 4. Perform the Rebase
```bash
git rebase develop
```

**If conflicts occur:**
```bash
# Check which files have conflicts
git diff --name-only --diff-filter=U

# Open and resolve each conflicted file, then:
git add <resolved-file>
git rebase --continue

# To abort if things go wrong:
git rebase --abort
```

#### 5. Verify Result
```bash
# Must show exactly 1 outgoing commit
git log --oneline develop..HEAD

# Confirm commit message is preserved
git log -1 --format="%B"

# Verify local and remote are in expected state
git status -sb
```

#### 6. Post-Rebase Compilation Health Check

After a successful rebase, **always verify compilation** before pushing — especially when your branch
performs API renames or removes packages. New files added by `develop` (no git conflict) may still
import classes that your branch removed or renamed.

```bash
# Compile main + test sources to catch any broken imports in newly merged files
mvn test-compile -pl <module> -am -q
```

**Common pattern in API-migration branches:**  
- Your branch renames/removes a class (e.g., `EmailSenderConfig` → `BookingEmailConfig`)
- A parallel branch adds a new test file that imports the old class
- Git merges both cleanly (no conflict — it's a new file), but compilation fails

**Fix**: Apply the same rename/import change to the newly introduced file, then amend the commit:
```bash
# Fix the import in the newly merged file, then amend to keep a single clean commit
git add <fixed-file>
git commit --amend --no-edit
```

#### 7. Force Push to Remote
```bash
# ALWAYS use --force-with-lease (never --force)
git push --force-with-lease
```

#### 8. Restore Stashed Work
```bash
git stash pop
```

### Conflict Resolution Guide

When conflicts occur during rebase:

1. **Identify conflicted files**: `git diff --name-only --diff-filter=U`
2. **For each file**, compare what each branch intended:
   - Feature branch change: `git diff $MERGE_BASE..REBASE_HEAD -- <file>`
   - Develop change: `git diff $MERGE_BASE..develop -- <file>`
3. **Resolution strategies**:
   - **Keep both**: When changes are in different logical sections
   - **Keep ours (feature)**: When your change supersedes develop's
   - **Keep theirs (develop)**: When develop's change is newer/correct
   - **Manual merge**: When both changes need to coexist in the same lines
4. **After resolving**: `git add <file>` then `git rebase --continue`

### Important Safety Notes

- **Never use `--force`** — always use `--force-with-lease` to prevent overwriting others' work
- **Stash before rebase** — rebase requires a clean working directory
- **Verify single commit** after rebase with `git log --oneline develop..HEAD`
- **Abort if unsure** — `git rebase --abort` returns to pre-rebase state with no data loss
- **Session tracking** — use MCP session context to log rebase actions for traceability

### Squashing Multiple Commits (if needed)

If the feature branch has multiple commits that need squashing into one:
```bash
# Interactive rebase to squash (N = number of commits)
git rebase -i HEAD~N
# Mark all but first commit as 'squash' or 'fixup'
# Save and close editor
# Then force push
git push --force-with-lease
```
