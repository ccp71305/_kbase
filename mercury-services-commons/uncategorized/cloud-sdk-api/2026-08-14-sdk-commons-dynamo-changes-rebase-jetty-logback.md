# SDK-Commons Dynamo Changes — Rebase onto `develop` (Jetty + logback OWASP)

**Date:** 2026-08-14
**Author:** Copilot CLI (Claude Opus 4.8, `claude-opus-4-8`)
**Branch:** `feature/ION-12310-commons-cloudsdk-refactoring`
**Analysis / plan of record:** [`cloud-sdk-api/docs/2026-08-13-sdk-commons-rebase-analysis.md`](./2026-08-13-sdk-commons-rebase-analysis.md)
**Session:** `5fab7d4aa9ff4d22` — *sdk-commons-dynamo rebase onto develop (Jetty/logback OWASP) 2026-08-14*

> **Purpose of this document:** an *executed*, step-by-step record (commands + descriptions + results) of
> (1) pulling the incoming `origin/feature` commits (ION-16431) via fast-forward and (2) rebasing the 52
> feature commits onto `origin/develop` to gain the ION-16376 Jetty/logback OWASP hardening and the
> ION-15990 `wtg-federation` work, then bumping `dependency.version` to **`1.0.30-SNAPSHOT`**.
>
> Unlike the 2026-08-13 analysis (plan only), this file logs the **actual actions taken**.

---

## 0. Goal

| | |
|---|---|
| **Pull first** | Fast-forward local `feature/ION-12310-commons-cloudsdk-refactoring` to `origin/feature` (8 ION-16431 commits → `1.0.29-SNAPSHOT`). |
| **Then rebase** | Replay 52 feature commits onto `origin/develop` to pick up ION-16376 (Jetty `12.1.12`, slf4j `2.0.18`, logback-core `1.5.38` pin+exclusion) and ION-15990 (`libs/wtg-federation`). |
| **Version** | Bump `dependency.version` → **`1.0.30-SNAPSHOT`**. |
| **Protect above all** | The DynamoDB `maxResultSize` cap in `EnhancedDynamoRepository.query()` (ION-16431) + all AWS-upgrade surface. develop touches no cloud-sdk source → carried verbatim. |
| **Conflicts expected** | Exactly 3 files, resolve as UNION: `pom.xml`, `commons/pom.xml`, `README.md` (§5 of analysis). |

---

## 1. Pre-flight verification

**Purpose:** confirm the branch state matches the 2026-08-13 analysis before touching anything.

```bash
# Fetch all refs
git fetch origin --prune

# Local is 0 ahead / 8 behind origin/feature (clean fast-forward)
git rev-list --left-right --count HEAD...origin/feature/ION-12310-commons-cloudsdk-refactoring
#   0   8

# Merge base of feature and develop
git merge-base origin/feature/ION-12310-commons-cloudsdk-refactoring origin/develop
#   0c797f4e0d9a63ea477770129ece023a7ca40399

# Incoming from develop / feature commits to replay
git rev-list --count origin/feature/ION-12310-commons-cloudsdk-refactoring..origin/develop   # 5
git rev-list --count origin/develop..origin/feature/ION-12310-commons-cloudsdk-refactoring   # 52
```

**Result — matches analysis exactly:**

| Check | Expected | Actual |
|-------|----------|--------|
| Local ahead / behind `origin/feature` | 0 / 8 | **0 / 8** ✅ |
| Merge base | `0c797f4` | **`0c797f4`** ✅ |
| Incoming from `develop` | 5 | **5** ✅ |
| Feature commits to replay | 52 | **52** ✅ |
| `origin/develop` HEAD | `2f9d341` | **`2f9d341`** ✅ |
| `origin/feature` HEAD | `b305acc` | **`b305acc`** ✅ |

**Incoming `develop` commits (`origin/feature..origin/develop`):**

```
2f9d341 Pull request #50: ION-16376: Jetty,logback version upgrade- OWASP fix
bf994ef ION-16376: Jetty,logback version upgrade- OWASP fix
7b14443 Pull request #45: ION-15990: add gated dynamic target override resolution
3233e5d ION-15990: bump libs dependency version to 1.R.01.003
c3f377a ION-15990: add gated target override resolver and docs
```

---

## 2. Backup

**Purpose:** capture a restore point at the pre-rebase `origin/feature` tip before any history rewrite.

```bash
git branch backup/feature-ION-12310-pre-rebase-4 origin/feature/ION-12310-commons-cloudsdk-refactoring
```

**Result:** `backup/feature-ION-12310-pre-rebase-4` → `b305acc` (Pull request #48: Bugfix/ION-16431). ✅

---

## 3. Step 1 — Pull the incoming `origin/feature` (ION-16431) via fast-forward

**Purpose:** bring the 8 ION-16431 commits into the local branch *before* rebasing (per instruction:
pull feature first). Local is 0 ahead, so this is a pure fast-forward with no history rewrite.

```bash
git check-ignore cloud-sdk-api/docs/2026-08-14-sdk-commons-dynamo-changes-rebase-jetty-logback.md   # confirmed ignored
git merge --ff-only origin/feature/ION-12310-commons-cloudsdk-refactoring
```

**Result — clean fast-forward `1293c50..b305acc` (13 files, +382 / −40):**

- `cloud-sdk-api`: `QuerySpec.getMaxResultSize()`, `MessagingClient extends AutoCloseable`.
- `cloud-sdk-aws`: `EnhancedDynamoRepository` maxResultSize cap, `DefaultQuerySpec.maxResultSize`,
  `SqsMessagingClient.close()`, `AwsHttpClientWrapper` builder mode, `S3ClientFactory` branch.
- Root `pom.xml` → `1.0.29-SNAPSHOT`.

Branch tip now `b305acc` @ `1.0.29-SNAPSHOT`. ✅

---

## 4. Step 2 — Rebase the 52 feature commits onto `origin/develop`

**Purpose:** replay the feature history on top of `origin/develop` so the branch gains ION-16376 (Jetty/logback
OWASP) and ION-15990 (wtg-federation).

```bash
git rebase origin/develop
```

Git replayed **49** commits (3 feature commits were patch-identical to develop content and dropped
automatically). **Exactly one** stop point, on the earliest pom-touching feature commit:

```
Rebasing (3/49)
Auto-merging pom.xml
CONFLICT (content): Merge conflict in pom.xml
could not apply fa2d428... ION-12310 pom changes
```

### 4.1 Conflict resolution — root `pom.xml` (commit `fa2d428`), resolved as UNION

Only the `<dependency.version>` line conflicted; every other property (incl. `libs.dependency.version`,
`jetty.version`, `slf4j.version`, `logback.core.version`) auto-merged cleanly to the develop side.

| Property | develop (HEAD) | feature (incoming) | **Resolution** |
|----------|----------------|--------------------|----------------|
| `<dependency.version>` | `1.R.01.026` | `1.0.0-SNAPSHOT` (early lineage value) | **Keep feature SNAPSHOT lineage** (later feature commits bump it to `1.0.29`; finalised to `1.0.30` in §5) |
| `<libs.dependency.version>` | `1.R.01.003` | — | Auto-merged to develop `1.R.01.003` |
| `<jetty.version>` | `12.1.12` | — | Auto-merged to develop `12.1.12` (OWASP) |
| `<slf4j.version>` | `2.0.18` | — | Auto-merged to develop `2.0.18` (OWASP) |
| `<logback.core.version>` | `1.5.38` (new) | — | Auto-merged, develop property added |

```bash
# after editing pom.xml to keep the feature dependency.version line:
git add pom.xml
git rebase --continue
# → Rebasing (4/49) … (49/49)
# Successfully rebased and updated refs/heads/feature/ION-12310-commons-cloudsdk-refactoring
```

`commons/pom.xml` (logback-core managed dep + `dropwizard-core` exclusion + direct dep) and `README.md`
(develop top-line bump + changelog block vs feature SNAPSHOT entries) **auto-merged** — the two sides edited
disjoint regions, so no manual resolution was needed there.

### 4.2 Post-rebase verification — the final tip carries the correct UNION

```bash
git rev-list --left-right --count HEAD...origin/develop     # 50   0  (ahead-only, develop fully integrated)
```

| Item | Expected | Actual at tip |
|------|----------|---------------|
| `dependency.version` | feature SNAPSHOT | `1.0.29-SNAPSHOT` (→ bumped in §5) ✅ |
| `libs.dependency.version` | `1.R.01.003` (develop) | `1.R.01.003` ✅ |
| `aws.java.sdk.version` | `1.12.730` (feature) | `1.12.730` ✅ |
| `jetty.version` | `12.1.12` (develop OWASP) | `12.1.12` ✅ |
| `slf4j.version` | `2.0.18` (develop OWASP) | `2.0.18` ✅ |
| `logback.core.version` | `1.5.38` (develop OWASP) | `1.5.38` ✅ |
| `assertj.core.version` | `3.27.2` (feature) | `3.27.2` ✅ |
| `<modules>` | cloud-sdk-aws/api + dynamo-integration-test + wtg-federation | all present ✅ |
| `commons/pom.xml` logback-core | managed + excluded + direct | 3 declarations present ✅ |
| `flattenDependencyMode=all` | absent (Netty CVE fix) | absent ✅ |
| 7 Jetty direct deps | present | 8 `org.eclipse.jetty` refs present ✅ |
| `EnhancedDynamoRepository` maxResultSize cap | present | present ✅ |
| ION-15990 `TargetConfigurationResolver` | present | present ✅ |

ION-16376 and ION-15990 commits now appear in `git log` below the new tip. Branch is **50 ahead / 0 behind**
`origin/develop`. ✅

---

## 5. Step 3 — Version bump + post-rebase touch-ups

**Purpose:** stamp the rebased line as a distinct, pullable artifact and remove stale comments.

Changes (single commit `727dd87`):

1. **Root `pom.xml`:** `dependency.version` `1.0.29-SNAPSHOT` → **`1.0.30-SNAPSHOT`**. Child modules inherit
   via `<version>${dependency.version}</version>`, so this one property bump versions all four library
   artifacts.
2. **`commons/pom.xml`:** updated the now-stale Jetty pin comments `12.1.9` → `12.1.12` (comment-only; the
   effective pinned version is already `12.1.12` from the inherited BOM after the rebase).
3. **`README.md`:** added a `### Commons v1.0.30-SNAPSHOT` changelog block recording the OWASP gains and
   ION-15990 pickup, above the preserved `v1.0.29-SNAPSHOT` entry. develop's `v1.R.01.026` top-line and
   changelog block were kept from the auto-merge.

```bash
git add README.md commons/pom.xml pom.xml
git commit -m "ION-12310: rebase onto develop (ION-16376 Jetty/logback OWASP + ION-15990), bump to 1.0.30-SNAPSHOT"
# → [feature/ION-12310-commons-cloudsdk-refactoring 727dd87] 3 files changed, 13 insertions(+), 7 deletions(-)
```

---

## 6. Step 4 — Validation

**Purpose:** prove the rebased branch builds and all unit + DynamoDB-Local integration tests pass.

| Command | Purpose | Result |
|---------|---------|--------|
| `mvn clean install -DskipITs` | Full reactor build + all unit tests | **BUILD SUCCESS** — 2159 tests, 0 failures, 0 errors, 0 skipped (332 surefire reports) |
| `mvn -pl dynamo-integration-test verify` | DynamoDB-Local IT framework module | **BUILD SUCCESS** — 6 tests, 0 failures |
| `mvn -pl cloud-sdk-aws verify` | cloud-sdk-aws DynamoDB-Local failsafe ITs (incl. `RepositoryQueryIT`, `QuerySpecIntegrationTests` — the maxResultSize cap) | **BUILD SUCCESS** — 137 integration tests, 0 failures, 0 errors |

No test regressions. The load-bearing DynamoDB `maxResultSize` cap is exercised green by the cloud-sdk-aws
integration suite.

---

## 7. Final state summary

| | |
|---|---|
| **Branch tip** | `727dd87` — *ION-12310: rebase onto develop (ION-16376 Jetty/logback OWASP + ION-15990), bump to 1.0.30-SNAPSHOT* |
| **Version** | `1.0.30-SNAPSHOT` (all four library artifacts) |
| **Backup** | `backup/feature-ION-12310-pre-rebase-4` → `b305acc` (pre-rebase `origin/feature`) |
| **vs `origin/develop`** | 50 ahead / 0 behind |
| **OWASP gained** | Jetty `12.1.12`, slf4j `2.0.18`, logback-core `1.5.38` pin+exclusion |
| **Also gained** | ION-15990 `wtg-federation` (`libs.dependency.version=1.R.01.003`) |
| **Preserved** | DynamoDB maxResultSize cap, `MessagingClient` AutoCloseable, HTTP-client builder mode, AWS-upgrade surface, Netty CVE fix (no `flattenDependencyMode=all`) |
| **Tests** | 2159 unit + 6 dynamo-integration-test + 137 cloud-sdk-aws IT — all green |

### 7.1 Remaining (pre-publish, out of scope of this rebase)

- Force-push the rewritten branch to `origin` and update the PR (not performed here).
- Run the `MessagingClient.close()` external-implementor sweep across all `cloud-sdk-api` consumers before
  any consumer publish (analysis §8 / visibility doc §8.3).

---

## 8. Command appendix (chronological)

```bash
# Pre-flight
git fetch origin --prune
git rev-list --left-right --count HEAD...origin/feature/ION-12310-commons-cloudsdk-refactoring   # 0 8
git merge-base origin/feature/ION-12310-commons-cloudsdk-refactoring origin/develop              # 0c797f4
git rev-list --count origin/feature/ION-12310-commons-cloudsdk-refactoring..origin/develop       # 5
git rev-list --count origin/develop..origin/feature/ION-12310-commons-cloudsdk-refactoring       # 52

# Backup + pull feature (FF)
git branch backup/feature-ION-12310-pre-rebase-4 origin/feature/ION-12310-commons-cloudsdk-refactoring
git merge --ff-only origin/feature/ION-12310-commons-cloudsdk-refactoring                        # 1293c50..b305acc

# Rebase onto develop
git rebase origin/develop
#   CONFLICT in pom.xml (fa2d428) → keep feature dependency.version line (UNION)
git add pom.xml
git rebase --continue                                                                            # 49/49 done

# Version bump + touch-ups
#   pom.xml dependency.version -> 1.0.30-SNAPSHOT
#   commons/pom.xml Jetty comments 12.1.9 -> 12.1.12
#   README.md + v1.0.30-SNAPSHOT changelog block
git add README.md commons/pom.xml pom.xml
git commit -m "ION-12310: rebase onto develop (ION-16376 Jetty/logback OWASP + ION-15990), bump to 1.0.30-SNAPSHOT"

# Validation
mvn clean install -DskipITs               # 2159 unit tests, BUILD SUCCESS
mvn -pl dynamo-integration-test verify     # 6 tests, BUILD SUCCESS
mvn -pl cloud-sdk-aws verify               # 137 integration tests, BUILD SUCCESS
```

---

## 9. Post-rebase code review — removed `(T)` casts in `EnhancedDynamoRepository`

**Question raised (review):** what is the purpose of removing the cast on (old) lines **275** and **324** of
`EnhancedDynamoRepository.java` in the incoming ION-16431 changes, and is there any downside?

### 9.1 Commands used to review

```bash
# Which commits touched the file (identify the ION-16431 change)
git --no-pager log --oneline -- cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/database/impl/EnhancedDynamoRepository.java

# The exact incoming diff pulled by the fast-forward (1293c50..b305acc)
git --no-pager diff 1293c50 b305acc -- cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/database/impl/EnhancedDynamoRepository.java

# Read the enclosing method signatures/bodies to confirm the static types
#   (view tool) EnhancedDynamoRepository.java lines 248-300  -> update(...)
#   (view tool) EnhancedDynamoRepository.java lines 303-335  -> saveIfNotExist(...)
```

### 9.2 The incoming change

```java
// update(...)  (old line 275)
- .item((T) item)
+ .item(item)

// saveIfNotExist(...)  (old line 324)
- .item((T) item)
+ .item(item)
```

Enclosing signatures (both use a bounded type parameter `S extends T`):

```java
public <S extends T> S update(final S item) { ... }
public <S extends T> Optional<S> saveIfNotExist(final S item) { ... }
```

The builders are typed to `T` — `UpdateItemEnhancedRequest.builder(itemClass)` → `Builder<T>` and
`PutItemEnhancedRequest.builder(itemClass)` → `Builder<T>` — so `.item(...)` expects a `T`.

### 9.3 Purpose of the removal

Because `S extends T`, `item` (static type `S`) **is already a `T`**. Passing it where a `T` is expected is
an implicit *widening reference conversion*, so no cast is needed. The `(T) item` was therefore:

1. **Redundant** — a no-op upcast the compiler performs automatically.
2. **An *unchecked* cast** — casting to a type variable (`T` is erased at runtime) makes `javac` emit an
   "unchecked cast" warning, falsely implying an unsafe operation.

It was almost certainly a leftover from an earlier, non-generic signature (when `item` was not statically
known to be a `T`). Removing it deletes a dead cast and its spurious warning.

### 9.4 Downside

None material:

- **Runtime:** identical. The cast to `T` erases to a `checkcast` against `T`'s bound that always succeeds
  for an `S`; the compiler may even elide it. Bytecode behaviour is unchanged.
- **API:** method signatures untouched → no source/binary compatibility impact.
- **Type safety:** *improved*. If the parameter type were later loosened (e.g. to `Object`), the absence of
  the cast makes it a **compile error** rather than being silently masked by an unchecked cast.

The only theoretical cost is that such a hypothetical future change would need a cast reintroduced — forcing
that to be explicit is the safer behaviour, not a regression. Verified green by the cloud-sdk-aws integration
suite (`mvn -pl cloud-sdk-aws verify`, 137 tests) in §6.

---

## 10. Follow-on enhancement — D-2: `export()` total-result cap + integration tests

**Jira:** ION-16431 · **Source gap:** D-2 (High) in `visibility/docs/2026-08-12-visibility-shared-http-client-dynamo-refactoring.md` §5.3 · **Module:** `cloud-sdk-aws`

The `maxResultSize` cap this rebase carried verbatim (§0, §4.2) was applied **only** to
`EnhancedDynamoRepository.query(QuerySpec)`. The same v1→v2 semantic inversion was still live in
`export(projectionExpression, limit)`: `limit` was passed straight to `ScanEnhancedRequest.limit(...)`
(a **per-page** size) and every page was then drained via
`table.scan(req).items().stream().collect(toList())` — an unbounded full-table scan whose Javadoc
actively misdescribed `limit` as a total "maximum number of items to return". D-2 closes that gap.

### 10.1 Source change — `EnhancedDynamoRepository.export(...)`

`limit` is now a **total result cap**, mirroring the proven `query()` pattern:

- `capped = limit != null && limit > 0`; the per-page `limit` is set on the request only when capped.
- Iterate `table.scan(...)` pages and early-`return` once `results.size() >= resultCap`. Because
  `PageIterable`/`ScanIterable` is lazy, no further `Scan` RPC is issued — heap **and** consumed RCUs
  are bounded (same guarantee as the load-bearing `query()` cap).
- `null`/non-positive `limit` means unbounded (documented as a production hazard).
- Javadoc corrected: `limit` is a total cap, not a page size.

```java
final boolean capped = limit != null && limit > 0;
if (capped) {
    requestBuilder.limit(limit);
}
// ...projection unchanged...
final int resultCap = capped ? limit : Integer.MAX_VALUE;
final List<T> results = new ArrayList<>(Math.min(resultCap, 1024));
for (final Page<T> page : table.scan(requestBuilder.build())) {
    for (final T item : page.items()) {
        results.add(item);
        if (results.size() >= resultCap) {
            return results;      // early return — ScanIterable is lazy, so no further RPC
        }
    }
}
return results;
```

> `findAll()` unpaginated scan is intentionally **out of scope**: it is guarded by
> `DynamoRepositoryConfig.isFindAllUnpaginatedScanEnabled()` (default off), so it cannot silently OOM.

### 10.2 Integration tests — `EnhancedDynamoRepositoryIT` → new `@Nested ExportIntegrationTests`

DynamoDB-Local end-to-end coverage (12 tests) verifying the cap + projection contract:

| Test | Verifies |
|---|---|
| `shouldReturnAllItemsWhenLimitIsNull` | `limit == null` → all items, full attributes populated |
| `shouldCapResultsWhenLimitIsSmallerThanTotal` | cap < total → exactly `limit` items |
| `shouldReturnAllItemsWhenLimitEqualsTotalCount` | cap == total → all items |
| `shouldReturnAllItemsWhenLimitExceedsTotalCount` | cap > total → all items |
| `shouldTreatNonPositiveLimitAsUnbounded` (`@ValueSource ints={0,-1,-100}`) | non-positive `limit` → unbounded |
| `shouldReturnEmptyListWhenTableHasNoItems` | empty table → empty list |
| `shouldPopulateOnlyProjectedAttributes` | projection populates only requested attrs; others `null` |
| `shouldIgnoreBlankAndDuplicateSegmentsInProjectionExpression` | projection parsing tolerates blank/embedded/trailing-empty segments |
| `shouldReturnFullItemsWhenProjectionIsBlank` | blank projection → full items |
| `shouldCombineProjectionAndTotalCap` | projection + cap together → capped, projected items |

### 10.3 Validation

```bash
mvn -pl cloud-sdk-aws -am verify -Dit.test=EnhancedDynamoRepositoryIT \
    -Dsurefire.failIfNoSpecifiedTests=false -Dfailsafe.failIfNoSpecifiedTests=false
# failsafe-summary.xml → completed=61, failures=0, errors=0, skipped=0
```

All green, no regressions. A standalone module note also exists at
`cloud-sdk-aws/docs/2026-08-14-export-total-cap-integration-tests.md`.

---

## 11. Final push to `origin` — history rewrite to clear Control Freak

**Purpose:** publish the rebased branch. Because the rebase **rewrote history** (branch is 50+ ahead of the
old `origin/feature` tip and 52 behind it in the old lineage), the remote branch cannot fast-forward — a
force push is required. The first attempt was **rejected by Control Freak** (the Bitbucket pre-receive Jira
policy hook) because pushed commit messages referenced **`ION-16431`**, which is now **Closed** and therefore
"invalid for receiving commits". The fix: rewrite every outgoing commit message so it references only the
active umbrella ticket **`ION-12310`**, then force-push with a lease.

> **Why the README was left untouched:** Control Freak only parses **commit messages**, not file contents.
> The `ION-16431` mention in `README.md` is fine and was intentionally preserved.

### 11.1 First attempt — amend HEAD only (insufficient)

The version-bump commit (§5) subject was already `ION-12310:` but its **body** contained a
`D-2 (ION-16431):` line. Amending rewrites only the tip commit's message; the tree/SHA of its content is
preserved.

```bash
# --amend rewrites the most recent commit; -F reads the new message from a file
# (avoids shell-quoting a multi-line message). This does NOT touch the tree.
git commit --amend -F .amend-msg.txt
```

**Syntax notes**

| Token | Meaning |
|---|---|
| `--amend` | Replace the tip commit with a new one; here only the **message** changes, the tree is identical, so a new SHA is minted but no files move. |
| `-F <file>` | Take the commit message verbatim from `<file>` (vs `-m` which is awkward for multi-paragraph messages with parentheses/quotes that PowerShell would mangle). |

Result: HEAD message clean, **but the push still failed** — Control Freak scans **every** commit in the
push, and 5 earlier fast-forwarded commits (§3) still had `ION-16431` **subjects**.

```
remote: Control Freak - Push rejected. ... invalid statuses ...
remote:   [ION-16431] - Closed.
```

### 11.2 Identify every outgoing commit still referencing the closed ticket

**Purpose:** scope the rewrite to exactly the commits that will be pushed (`<remote-tip>..HEAD`), not the
whole branch history.

```bash
# Range A..B = commits reachable from B but not from A → the outgoing set only.
git log --oneline origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD | grep 'ION-16431'
#   d63812b ION-16431 Max size limit
#   76943ce ION-16431 Test for maxResultSize
#   8bc88b8 ION-16431 Version Update
#   a4b6d11 ION-16431 Dedicated HTTP Clients
#   62ffe4a ION-16431 Tests for clietn close

# Count occurrences across subjects AND bodies (%B) to be exhaustive
git log <range> --format='%H%n%B' | grep -c 'ION-16431'   # 5 — all subjects, one each
```

### 11.3 Rewrite all outgoing commit messages — `ION-16431` → `ION-12310`

**Purpose:** relabel the 5 commits (whose code legitimately belongs to the `ION-12310` umbrella) without
touching a single byte of any tree.

```bash
# Squelch the deprecation banner; filter-branch is fine here for a message-only rewrite.
export FILTER_BRANCH_SQUELCH_WARNING=1

# --msg-filter runs the given sh command per commit, feeding the old message on stdin
# and taking the new message from stdout. sed does a global (g) literal replace.
# The trailing <range> restricts the rewrite to the outgoing commits only.
git filter-branch -f --msg-filter "sed 's/ION-16431/ION-12310/g'" \
    origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD
```

**Syntax notes**

| Token | Meaning |
|---|---|
| `-f` | Force — overwrite any leftover `refs/original/` backup from a prior run. |
| `--msg-filter <cmd>` | For each commit, pipe the **old** message into `<cmd>`; its **stdout** becomes the new message. Only messages change → trees preserved, but **all commit SHAs in range are rewritten** (a child's SHA depends on its parent). |
| `sed 's/old/new/g'` | Stream-edit: substitute `old`→`new`, `g` = every occurrence on each line. |
| `<A>..HEAD` | Rewrite only commits after the remote tip; commits before it (shared with `origin`) are left byte-identical. |
| auto `refs/original/` | filter-branch stashes the pre-rewrite ref here as a safety net (cleaned up in §11.5). |

**Result:** `Ref 'refs/heads/feature/...' was rewritten` — the 5 subjects are now
`ION-12310 Max size limit`, `ION-12310 Test for maxResultSize`, `ION-12310 Version Update`,
`ION-12310 Dedicated HTTP Clients`, `ION-12310 Tests for clietn close`.

```bash
# Verify: zero remaining references in any outgoing message before pushing
git log origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD --format='%H %B' \
    | grep -c 'ION-16431'   # 0 ✅
```

### 11.4 Force-push with a lease

**Purpose:** overwrite the rewritten branch on `origin` **safely**. `--force-with-lease` refuses the push if
`origin/feature` has advanced since our last fetch (i.e. someone else pushed), preventing us from silently
clobbering their work — the difference between "safe force" and the blunt `--force`.

```bash
git push --force-with-lease origin feature/ION-12310-commons-cloudsdk-refactoring
```

**Syntax notes**

| Token | Meaning |
|---|---|
| `--force-with-lease` | Force **only if** the remote ref still points at the commit our local remote-tracking ref remembers. If the remote moved, the push aborts instead of overwriting. Prefer this over `--force`. |
| (bare form) | With no `<ref>:<ref>` expected-value argument, the lease is taken against our remote-tracking `origin/feature/...` — valid here because we had not re-fetched since the rewrite. |

**Result — accepted:**

```
remote: View pull request ... /pull-requests/29
 + b305acc...1e2fcd6 feature/ION-12310-commons-cloudsdk-refactoring -> ... (forced update)
```

Control Freak passed (no closed-ticket references remain). PR **#29** → `develop`.

### 11.5 Cleanup + sync verification

**Purpose:** drop the local filter-branch safety refs and confirm the branch is fully in sync (no
ahead/behind) with the rewritten remote.

```bash
# Delete the auto-created backup refs now that the push is verified good.
git for-each-ref --format='%(refname)' refs/original/ | ForEach-Object { git update-ref -d $_ }

git status -sb
# ## feature/ION-12310-commons-cloudsdk-refactoring...origin/feature/ION-12310-commons-cloudsdk-refactoring
#   (no [ahead]/[behind] → in sync) ✅
```

### 11.6 Command appendix (final push, chronological)

```bash
# 1. Amend the tip message (body still had a D-2 (ION-16431) line)
git commit --amend -F .amend-msg.txt

# 2. First push rejected by Control Freak — earlier FF commits still name ION-16431
git push --force-with-lease origin feature/ION-12310-commons-cloudsdk-refactoring   # REJECTED

# 3. Scope the offenders in the outgoing range
git log --oneline origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD | grep 'ION-16431'   # 5

# 4. Rewrite all outgoing commit messages ION-16431 -> ION-12310
export FILTER_BRANCH_SQUELCH_WARNING=1
git filter-branch -f --msg-filter "sed 's/ION-16431/ION-12310/g'" \
    origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD

# 5. Verify none remain, then safe force-push
git log origin/feature/ION-12310-commons-cloudsdk-refactoring..HEAD --format='%B' | grep -c 'ION-16431'  # 0
git push --force-with-lease origin feature/ION-12310-commons-cloudsdk-refactoring   # b305acc..1e2fcd6 (forced)

# 6. Cleanup backup refs + confirm in sync
git for-each-ref --format='%(refname)' refs/original/ | ForEach-Object { git update-ref -d $_ }
git status -sb
```

> **Takeaway for future pushes on this branch:** Control Freak validates the Jira key in **every** pushed
> commit message against the ticket's status. Keep feature-branch commit subjects on the **active** umbrella
> ticket (`ION-12310`); do not reference sub-tickets that may be closed independently. If a rebase/FF drags
> in commits naming a now-closed ticket, rewrite the outgoing range's messages (§11.3) before pushing.


