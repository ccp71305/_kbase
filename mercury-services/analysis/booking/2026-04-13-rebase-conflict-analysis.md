# Rebase Conflict Analysis & Resolution — ION-14382

**Date**: 2026-04-13  
**Branch**: `ION-14382-reapply-bk3-aws-upgrade`  
**Target**: `develop`  
**PR**: https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/965  
**Author**: Arijit Kundu

---

## Background

The branch `ION-14382-reapply-bk3-aws-upgrade` contains a single commit that re-applies the AWS SDK v2 upgrade
for the `booking` module (originally reverted, now re-raised as PR #965).  
While the branch was open, another developer merged `ION-14137` (null-reference fixes in booking outbound)
into `develop`, requiring the branch to be rebased.

---

## Step-by-Step Analysis

### 1. Confirm Current Branch & State

```bash
git branch --show-current
git log --oneline -10
git status
```

| Output | Meaning |
|--------|---------|
| `ION-14382-reapply-bk3-aws-upgrade` | On correct branch |
| 1 commit ahead (f5b6658132) | Single AWS upgrade commit — clean |
| Untracked files only | No staged/unstaged changes — safe to rebase |

---

### 2. Find Merge Base (Divergence Point)

```bash
git merge-base HEAD develop
```

| Result | Meaning |
|--------|---------|
| `38d423afd7` | Branch diverged from `develop` at PR #964 (Bugfix ION-15368) |

---

### 3. Count How Far Behind Develop

```bash
git log --oneline HEAD..develop
git log --oneline HEAD..develop | Measure-Object -Line
```

| Result | Meaning |
|--------|---------|
| 16 commits | Develop moved forward 16 commits since divergence |
| Top commit: `b0b50768a5` | Latest develop tip (ION-14898) |

Key develop commits since divergence (16 total):

| Commit | Description |
|--------|-------------|
| `b0b50768a5` | ION-14898 (SI Preference) |
| `fc6fd43442` | PR #966 — ION-14879 Alliance Partner API |
| `a648469ead` … `25be9edf5a` | Alliance Partner API implementation commits |
| `6dba7309b6` | **PR #953 — ION-14137** ← touches booking |
| `56fcf7a035` … `8b1a8685ef` | ION-14137 individual commits ← touches booking |

---

### 4. Identify Which Develop Commits Touched `booking/`

```bash
git log --oneline HEAD..develop -- booking/
```

| Result | Meaning |
|--------|---------|
| Only `ION-14137` commits (2) | Only one feature touched booking in those 16 commits |

**ION-14137 changed in `booking/`:**

| File | Change Type |
|------|-------------|
| `outbound/services/OutboundServiceImpl.java` | Modified (~6 lines) |
| `outbound/services/SupplementationUtil.java` | New file |
| `outbound/services/OutboundServiceImplReferencesTest.java` | New test file |
| `outbound/services/SupplementationEmptyReferenceTest.java` | New test file |

---

### 5. Identify Overlapping Files (Potential Conflict Zone)

```bash
git diff --name-only HEAD develop -- booking/
```

Many files differed because the branch changed them for AWS upgrade. Key overlap check:

```bash
git diff --name-only HEAD develop -- booking/src/main/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImpl.java
```

| Result | Meaning |
|--------|---------|
| File listed | Both branch and develop changed `OutboundServiceImpl.java` — **potential conflict** |

---

### 6. Diff Analysis — What Each Side Changed in `OutboundServiceImpl.java`

#### What the AWS upgrade (branch) changed — vs merge-base

```bash
git diff 38d423afd7..HEAD -- booking/src/main/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImpl.java
```

| Line Area | Change |
|-----------|--------|
| ~63 (imports) | `com.inttra.mercury.email.model.EmailSendResult` → `com.inttra.mercury.cloudsdk.email.model.EmailSendResult` |
| ~63 (imports) | `com.inttra.mercury.email.module.EmailSenderConfig` → `com.inttra.mercury.booking.config.BookingEmailConfig` |
| ~63 (imports) | `com.inttra.mercury.email.service.EmailResultCollector` → `com.inttra.mercury.cloudsdk.email.legacy.api.EmailResultCollector` |
| ~128 (field) | `EmailSenderConfig emailSenderConfig` → `BookingEmailConfig bookingEmailConfig` |
| ~154 (constructor param) | Same rename |
| ~175 (assignment) | Same rename |
| ~1067, ~1080, ~1091, ~1104 (methods) | `emailSenderConfig.getInternalEmails()` → `bookingEmailConfig.getInternalEmails()` |

#### What ION-14137 (develop) changed — vs merge-base

```bash
git diff 38d423afd7..develop -- booking/src/main/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImpl.java
```

| Line Area | Change |
|-----------|--------|
| ~609 | Added `SupplementationUtil.trimAndFilterReferences(copyOfContract)` call |
| ~612 | Wrapped `customerReferences` with `SupplementationUtil.trimAndFilterCustomerReferences(...)` |

#### Conflict Risk Assessment

| Criterion | Result |
|-----------|--------|
| Same file? | ✅ Yes — `OutboundServiceImpl.java` |
| Same lines? | ❌ No — AWS changes at imports/fields/1000+ line methods; ION-14137 at ~line 609 |
| Conflict predicted? | **No — auto-merge expected** |

---

### 7. Rebase Execution

```bash
git rebase develop
```

| Result | Meaning |
|--------|---------|
| `Successfully rebased and updated refs/heads/ION-14382-reapply-bk3-aws-upgrade` | No conflicts — clean auto-merge ✅ |

---

### 8. Verify Rebase Result

```bash
git log --oneline -5
git log --oneline develop..HEAD
```

| Check | Result |
|-------|--------|
| Single commit ahead | ✅ `ecc0ca9db2` — exactly 1 commit |
| Now on top of develop tip | ✅ `b0b50768a5` (ION-14898) is immediate parent |

---

### 9. Force Push

```bash
git push origin ION-14382-reapply-bk3-aws-upgrade --force-with-lease
```

| Result | Meaning |
|--------|---------|
| `forced update f5b6658132...ecc0ca9db2` | Branch updated on remote safely ✅ |
| `--force-with-lease` | Rejected if someone else pushed in the meantime — safe by design |

---

## Post-Rebase Compilation Issue

After pushing, the CI build reported:

```
[ERROR] /build/src/booking/src/test/java/com/inttra/mercury/booking/outbound/services/OutboundServiceImplReferencesTest.java:[37,39]
        package com.inttra.mercury.email.module does not exist
```

### Root Cause

`OutboundServiceImplReferencesTest.java` was introduced by ION-14137 using the **legacy** `EmailSenderConfig`
from `com.inttra.mercury.email.module`. The AWS upgrade (branch) removed that package and replaced it with
`BookingEmailConfig` from `com.inttra.mercury.booking.config`. The test file inherited from the old API.

### Fix Applied

| File | Old | New |
|------|-----|-----|
| `OutboundServiceImplReferencesTest.java:37` | `import com.inttra.mercury.email.module.EmailSenderConfig;` | `import com.inttra.mercury.booking.config.BookingEmailConfig;` |
| `OutboundServiceImplReferencesTest.java:88` | `mock(EmailSenderConfig.class)` | `mock(BookingEmailConfig.class)` |

### Verification

```bash
mvn test-compile -pl booking -am -q
```

Result: **Exit code 0 — compiles clean** ✅

### Commit & Push

```bash
git add booking/src/test/java/.../OutboundServiceImplReferencesTest.java
git commit --amend --no-edit   # keep single commit
git push origin ION-14382-reapply-bk3-aws-upgrade --force-with-lease
```

| Result | SHA |
|--------|-----|
| Amended commit | `59ebf93a2a` |
| Pushed to remote | ✅ |

---

## Final State

| Item | Value |
|------|-------|
| Branch | `ION-14382-reapply-bk3-aws-upgrade` |
| HEAD | `59ebf93a2a` |
| Commits ahead of develop | 1 (single commit) |
| Develop tip | `b0b50768a5` |
| PR | #965 — up to date |
| Compilation | ✅ Clean |

---

## Lessons Learned

1. **When a new test file is added to `develop` that depends on a class your branch removed/renamed**, it won't show as a git conflict (new file = no merge conflict) but will fail compilation. Always run `mvn test-compile` after rebase before pushing.

2. **Conflict pre-analysis is fast and reliable**: comparing `git diff <merge-base>..HEAD -- <file>` and `git diff <merge-base>..develop -- <file>` for each overlapping file makes it easy to assess conflict risk without doing a trial rebase.

3. **`--force-with-lease` is mandatory** for rebased branches — it refuses to push if the remote has newer commits, protecting against overwriting teammates' work.

---

## Key Commit History — ION-14382 AWS Upgrade (Full Lifecycle)

> Updated: 2026-04-14 after PR #965 was merged to `develop`.

The table below captures every commit that carries the AWS upgrade changes or its revert, in chronological order.

| Date | SHA (short) | PR | Event | Notes |
|------|-------------|-----|-------|-------|
| 2026-02-20 | `74f36e7a71` | — | Original AWS upgrade commit | On feature branch `feature/ION-14382-bk3-aws-upgrade-2`; 224 files, 12 306 insertions |
| 2026-04-06 | `7de030248f` | **#939** | **Merge**: AWS upgrade → `develop` | First landing on develop |
| 2026-04-06 | `dc4a0dde15` | — | Revert commit | Created on branch `ION-14382-BK-AWS-SDK-Revert` |
| 2026-04-06 | `55887494eb` | **#960** | **Merge**: Revert → `develop` | AWS upgrade rolled back same day |
| 2026-04-10 | `59ebf93a2a` | — | Reapply AWS upgrade commit | Rebased on top of `b0b50768a5` (ION-14898); test fix for `OutboundServiceImplReferencesTest.java` included |
| 2026-04-14 | `681e7eba1d` | **#965** | **Merge**: Reapply → `develop` | Final, stable landing; merge parents: `dbcc95ada8` (develop) ← `59ebf93a2a` (feature) |

**Current develop tip** (as of 2026-04-14): `4741ad3f16` (ION-15211)  
Local `develop` == `origin/develop` ✅

---

## How to Revert the AWS Upgrade — Clean Rollback Steps

If the booking AWS SDK v2 upgrade needs to be rolled back from `develop`, follow the steps below.
The revert target is the **merge commit `681e7eba1d`** (PR #965).

### Option A — Preferred: Revert the Merge Commit (safe, traceable)

```bash
# 1. Make sure you are on develop and fully up to date
git checkout develop
git pull origin develop

# 2. Revert the merge commit — mainline 1 = the develop side before the feature was merged
git revert -m 1 681e7eba1d

# 3. Git opens an editor with a pre-filled commit message. Accept or edit, then save.
#    This creates one new revert commit, e.g.:
#      Revert "Pull request #965: Reapply ION-14382 bk3 aws upgrade changes"

# 4. Push to a feature branch and raise a PR — do NOT push directly to develop
git push origin HEAD:ION-14382-BK-AWS-SDK-Revert-2
```

**Why `-m 1`?**  
`681e7eba1d` is a merge commit with two parents:
- Parent 1 (`dbcc95ada8`) — the develop mainline just before the merge
- Parent 2 (`59ebf93a2a`) — the feature branch tip (AWS upgrade commit)

`-m 1` tells git to treat Parent 1 as the "good" baseline, so the revert undoes exactly what the feature branch brought in.

### Option B — Alternative: Revert the AWS Upgrade Commit Directly

If only the inner commit (not the merge envelope) should be reverted:

```bash
git revert 59ebf93a2a
```

This creates a new commit that inverts all 224 files changed by the AWS upgrade.  
Use this only if the merge commit revert causes issues (e.g., conflicts with later commits that already depend on the upgraded APIs).

### Option C — Emergency: Hard Reset (destructive — use only on non-shared branches)

```bash
# Reset develop to the commit just before the reapply merge
git reset --hard dbcc95ada8    # develop tip before PR #965 landed
git push origin develop --force-with-lease  # DANGEROUS — requires team coordination
```

⚠️ **Do not use Option C on `develop` without explicit team agreement.** It rewrites shared history and will break every teammate's local branch.

---

### Post-Revert Checklist

After any revert, verify the following before merging to `develop`:

1. **Compilation**
   ```bash
   mvn test-compile -pl booking -am -q
   ```
2. **Unit tests**
   ```bash
   mvn test -pl booking -am -q
   ```
3. **Check `pom.xml`** — confirm `cloud-sdk-*` dependencies are removed and legacy AWS SDK v1 entries are restored if needed.
4. **Check config classes** — `BookingEmailConfig`, `BookingDynamoModule`, `BookingMessagingModule`, `BookingEmailSenderModule` are all introduced by the upgrade; verify they are gone.
5. **Check `BookingApplicationInjector`** — restore Guice bindings to the pre-upgrade state.
6. **Notify dependent teams** — if any downstream services (e.g., `booking-bridge`) consume APIs that changed during the upgrade, they may also need attention.
