# Rebase Analysis — `feature/ION-12310-commons-cloudsdk-refactoring` ← `origin/develop`

**Date:** 2026-08-13
**Author:** Copilot CLI (Claude Opus 4.8) — analysis only, **no fetch-integration, no rebase performed**
**Predecessor:** `cloud-sdk-api/docs/2026-07-17-rebase-with-develop-owasp-jackson.md` (the 1.0.27 rebase)
**Stated goal:** After pulling the incoming `origin/feature` commits (ION-16431), rebase the cloud-sdk
feature branch onto the latest `origin/develop` to pick up the new OWASP fixes, while **preserving every
AWS-upgrade change** and keeping all `cloud-sdk-api` / `cloud-sdk-aws` / `dynamo-integration-test` tests
green and all already-upgraded `mercury-services` apps unaffected.

> This document is a **plan and conflict map**. Nothing is fetched-integrated or rebased. Do not act on it
> until reviewed. Per house rule, this `.md` is **not** to be staged/committed (`cloud-sdk-api/docs/` is
> git-ignored).

---

## 0. TL;DR

| | |
|---|---|
| **Assumed starting point** | Local branch fast-forwarded to `origin/feature/ION-12310-commons-cloudsdk-refactoring` (the 8 ION-16431 commits, `→ 1.0.29-SNAPSHOT`). Local is currently **0 ahead / 8 behind** origin — a clean fast-forward. |
| **Incoming from `develop`** | **5 commits**, two tickets: **ION-16376** (Jetty + logback OWASP fix) and **ION-15990** (gated target-override in `libs/wtg-federation`). |
| **Merge base** | `0c797f4` — the same base for both `HEAD` and `origin/feature` vs `origin/develop`. |
| **Replay size** | 52 feature commits replayed onto `origin/develop`. |
| **Files that can conflict** | Exactly **3**: `pom.xml` (root), `commons/pom.xml`, `README.md`. Everything else is disjoint. |
| **New OWASP content actually gained** | Jetty `12.1.9 → 12.1.12`, slf4j `2.0.17 → 2.0.18`, **new** `logback-core 1.5.38` pin + exclusion from `dropwizard-core`. (The httpcomponents 4.x/5.x pins are already in the merge base from the 1.0.27 rebase — not re-conflicting.) |
| **Source impact on the 3 SDK modules** | **None from develop.** ION-16376 is pom-only; ION-15990 touches only `libs/wtg-federation`. No `cloud-sdk-api` / `cloud-sdk-aws` / `dynamo-integration-test` / `commons` **source** changes incoming. |
| **App impact** | Dependency-version-only (Jetty/logback pins). No API or behavioural change reaches consumers. `wtg-federation` is standalone and unreferenced by apps. |
| **Load-bearing change to protect above all** | The DynamoDB `maxResultSize` cap in `EnhancedDynamoRepository.query()` (ION-16431 / PR #48). It lives in `cloud-sdk-aws` **source**, which develop does not touch → **zero conflict risk**, preserved automatically by the replay. See §4 and the visibility addendum. |

---

## 1. Branch state

| Ref | Commit | Notes |
|-----|--------|-------|
| Local `HEAD` | `1293c50` | `1.0.28-SNAPSHOT` (C-G6). **0 ahead / 8 behind** `origin/feature`. |
| `origin/feature/ION-12310-commons-cloudsdk-refactoring` | `b305acc` | `1.0.29-SNAPSHOT` after ION-16431 (PRs #46/#47/#48). |
| `origin/develop` HEAD | `2f9d341` | `PR #50: ION-16376 Jetty, logback OWASP fix` (merge). Release line `1.R.01.026`. |
| Merge base (both) | `0c797f4` | Common ancestor of feature and develop. |

Counts (verified — §12):

```
git rev-list --left-right --count HEAD...origin/feature      # 0   8   (clean fast-forward)
git rev-list --count origin/feature..origin/develop          # 5   incoming from develop
git rev-list --count origin/develop..origin/feature          # 52  feature commits to replay
git merge-base HEAD origin/develop                           # 0c797f4
git merge-base origin/feature origin/develop                 # 0c797f4
```

## 2. Assumed sequence (per instruction: pull feature first)

1. **Fast-forward to `origin/feature`** — brings in the 8 ION-16431 commits. This is a pure FF (local is
   0 ahead), so no conflicts and the working tree becomes identical to `origin/feature` @ `1.0.29-SNAPSHOT`.
2. **Then rebase onto `origin/develop`** — replays the 52 feature commits, pulling in the 5 develop commits.

Everything below assumes step 1 is done, i.e. the branch already carries ION-16431.

## 3. What comes in from `develop` (net `0c797f4..origin/develop`)

**17 files, +519 / −45.** Two independent tickets:

| Ticket | PR | What | Files | Risk |
|--------|----|------|-------|------|
| **ION-16376** — Jetty/logback OWASP fix | #50 | Root `pom.xml` version bumps + `commons/pom.xml` logback-core pin/exclude/re-declare | `pom.xml`, `commons/pom.xml`, `README.md` | **Conflict** (§5) — but this is the change we *want* |
| **ION-15990** — gated dynamic target-override resolution | #45 | New `TargetConfigurationResolver`, validator refactor, config + tests | `libs/wtg-federation/**` (13 files) | **Clean** — feature branch does not touch this module |

### 3.1 ION-16376 in detail (the OWASP delta)

Root `pom.xml`:
```
- <jetty.version>12.1.9</jetty.version>
+ <jetty.version>12.1.12</jetty.version>
- <slf4j.version>2.0.17</slf4j.version>
+ <slf4j.version>2.0.18</slf4j.version>
+ <logback.core.version>1.5.38</logback.core.version>
- <dependency.version>1.R.01.025</dependency.version>   # develop-line release version
+ <dependency.version>1.R.01.026</dependency.version>   # (feature uses its own SNAPSHOT scheme — see §5.1)
```

`commons/pom.xml` (the *exclude-then-re-declare-at-pinned-version* pattern, same design as the httpcomponents
pins already in the base):
```
+ <dependencyManagement> … logback-core → ${logback.core.version} (1.5.38), scope compile
+ dropwizard-core → <exclusion> ch.qos.logback:logback-core
+ direct dependency ch.qos.logback:logback-core   (inherits pinned 1.5.38, lands in flattened POM)
```

**Why it matters:** DW 5.0.x drags in a `logback-core` version flagged by OWASP; the exclude+pin forces the
patched `1.5.38` into the published (flattened) `commons` POM that apps consume — exactly the mechanism the
feature branch already uses for Jetty and httpcomponents.

### 3.2 OWASP posture — already-present vs newly-gained

| OWASP item | Where it lives | Status after this rebase |
|---|---|---|
| httpcomponents 4.x pins (`httpcore` 4.4.16, `httpcore-nio` 4.4.16, `httpclient` 4.5.14) | already in merge base `0c797f4` (from 1.0.27 rebase) | Unchanged — **not** re-conflicting |
| httpcore5 / httpcore5-h2 `5.4.3` pins | already in merge base | Unchanged |
| Jackson 2.21.x direct pins, DW 5.0.2, handlebars | already in merge base | Unchanged |
| **Jetty `12.1.12`** | **incoming from develop (ION-16376)** | **Newly gained** — supersedes feature's 12.1.9 |
| **slf4j `2.0.18`** | incoming from develop | Newly gained |
| **logback-core `1.5.38` pin + exclusion** | incoming from develop | Newly gained |

> Contrast with the 1.0.27 rebase (2026-07-17 doc): that time the OWASP fixes had been *reverted* on
> develop and the rebase delivered nothing. **This time develop genuinely carries new OWASP hardening**
> (ION-16376) and the rebase is worth doing on that basis alone.

## 4. What comes in from `origin/feature` (ION-16431) — and what must be protected

Pulled in step 1 (§2). Full critical review is in
`mercury-services/visibility/docs/2026-08-12-visibility-shared-http-client-dynamo-refactoring.md`
(and its 2026-08-13 addendum). Summary for rebase purposes:

| Change (ION-16431) | Module / file | Load-bearing? | Conflict risk in the develop rebase |
|---|---|---|---|
| **DynamoDB `maxResultSize` cap** in `query()` | `cloud-sdk-aws` `EnhancedDynamoRepository.java`, `cloud-sdk-api` `QuerySpec`, `DefaultQuerySpec` | **YES — the real fix** | **None** — develop touches no cloud-sdk source |
| `MessagingClient extends AutoCloseable` + `SqsMessagingClient.close()` | `cloud-sdk-api`, `cloud-sdk-aws` | No (valuable leak fix; breaking for implementors) | None |
| HTTP-client builder mode (`AwsHttpClientWrapper.isBuilder`, `S3ClientFactory` branch) | `cloud-sdk-aws` | No (half-implemented; see addendum D-1) | None |
| `1.0.29-SNAPSHOT` bump + README | root `pom.xml`, `README.md` | n/a | **Conflict** (§5) |

**Key point for the rebase:** the single load-bearing change (DynamoDB cap) is entirely in `cloud-sdk`
**source files** that develop does not modify. It therefore cannot be lost or corrupted by the rebase — it is
carried verbatim by the feature-commit replay. The only manual work is the 3-file pom/README union.

## 5. Conflict analysis — 3 files, all resolvable as a UNION

Intersection of files changed on both sides of `0c797f4`:

```
README.md
commons/pom.xml
pom.xml
```

Conflicts surface on the first replayed feature commit(s) that touch each file. Expect **1–3 stop points**,
same character as the 1.0.27 / 1.0.24 rebases.

### 5.1 Root `pom.xml` — CONFLICT, resolve as UNION

| Line | develop side | feature side | **Resolution** |
|------|--------------|--------------|----------------|
| `<jetty.version>` | **12.1.12** | 12.1.9 | **Take develop → 12.1.12** (OWASP) |
| `<slf4j.version>` | **2.0.18** | 2.0.17 | **Take develop → 2.0.18** (OWASP) |
| `<logback.core.version>` | **1.5.38 (new)** | absent | **Add develop's property** |
| `<dependency.version>` | `1.R.01.026` | `1.0.29-SNAPSHOT` | **Keep feature SNAPSHOT** — recommend bump to `1.0.30-SNAPSHOT` (§8). The `1.R.01.x` line is develop's release scheme; the feature line stays on SNAPSHOT. |
| `<libs.dependency.version>` | **1.R.01.003** | 1.R.01.002 | **Take develop → 1.R.01.003** — ION-15990 bumped it and the incoming `wtg-federation` code is versioned by it. |
| `<aws.java.sdk.version>` | (unchanged, 1.12.638-era) | **1.12.730** | **Keep feature → 1.12.730** (AWS upgrade) |
| `<assertj.core.version>` | (unchanged) | **3.27.2** | **Keep feature → 3.27.2** |
| `<modules>` | `libs/wtg-federation` only | + `cloud-sdk-aws`, `cloud-sdk-api`, `dynamo-integration-test` | **Union all 4 modules** |
| AWS SDK v1 `dependencyManagement` reorg (single `aws-java-sdk-core`, TODO comment; `ssm`/`s3` removed) | untouched | feature reorganised | **Keep feature's reorg** |
| DW comment `4.0.10 → 5.0.1` | untouched | feature corrected | **Keep feature's text** |

**Failure mode to avoid:** blindly taking "ours" (feature) during replay would drop the develop OWASP bumps
(Jetty 12.1.12, slf4j 2.0.18, logback property) and `libs.dependency.version=1.R.01.003` → OWASP regression
+ `wtg-federation` fails to resolve. Resolve to the **union** above.

### 5.2 `commons/pom.xml` — CONFLICT, resolve as UNION

| Block | develop side (ION-16376) | feature side | **Resolution** |
|-------|--------------------------|--------------|----------------|
| `<dependencyManagement>` | + `logback-core` → `${logback.core.version}` | (httpcomponents pins already in base) | **Add develop's logback-core managed dep** |
| `dropwizard-core` dependency | + `<exclusion>` logback-core | (untouched) | **Add develop's exclusion** |
| direct deps | + `logback-core` direct dep | + 7 Jetty direct deps, cloud-sdk-api/aws module deps, junit-jupiter/mockito/assertj/commons-lang3/commons-text, AWS SDK v1 removals | **Union — keep all feature deps AND add develop's logback-core direct dep** |
| `flatten-maven-plugin` | untouched | feature removed `flattenDependencyMode=all` (Netty CVE fix) | **Keep feature (no `all` mode)** |

These two sides edit **different regions** of the file, so most hunks auto-merge; the conflict marker (if any)
will be localised to the `dependencyManagement`/`dependencies` boundaries. Union both.

> **Post-rebase touch-up (non-conflict):** the feature branch's Jetty comment block in `commons/pom.xml`
> says "pin 12.1.9". After the rebase, `jetty.version` is `12.1.12`, and the 7 direct Jetty deps inherit it,
> so the flattened POM publishes **12.1.12** (strictly better CVE posture). Update the comment text
> `12.1.9 → 12.1.12` to avoid confusing the next reader. Functionally correct either way.

### 5.3 `README.md` — CONFLICT (low risk)

- develop: top line `v1.R.01.025 → v1.R.01.026` and a new `#### … (v1.R.01.026)` changelog block (Jetty
  12.1.12, logback OWASP).
- feature: appended SNAPSHOT entries (`… v1.0.28`, `v1.0.29`) at the bottom.

Different regions → textual merge. **Keep all feature SNAPSHOT entries, add develop's `v1.R.01.026` block,
accept develop's top-line bump.** Add a `v1.0.30-SNAPSHOT` note recording this rebase (see §8).

### 5.4 Everything else — CLEAN

- All 13 `libs/wtg-federation/**` files (ION-15990) — feature branch does not touch this module (**verified: 0
  files**) → apply without conflict, provided `libs.dependency.version=1.R.01.003` is preserved (§5.1).
- No `cloud-sdk-api` / `cloud-sdk-aws` / `dynamo-integration-test` / `commons` **source** file is changed by
  develop → the entire AWS-upgrade surface replays untouched.

## 6. AWS-upgrade changes to preserve (post-rebase checklist)

All of these must still be present after resolution. They live either in cloud-sdk **source** (auto-preserved)
or in the 3 conflicted files (preserve manually per §5):

- [ ] `cloud-sdk-api`, `cloud-sdk-aws`, `dynamo-integration-test` modules in root `<modules>`.
- [ ] `dependency.version` on the SNAPSHOT line (`1.0.29`→ recommend `1.0.30-SNAPSHOT`), **not** `1.R.01.026`.
- [ ] `aws.java.sdk.version = 1.12.730`; AWS SDK v1 dependencyManagement reorg (single `aws-java-sdk-core`,
      `ssm`/`s3`/`sqs`/`sns` removals) intact.
- [ ] `commons/pom.xml`: 7 Jetty direct deps present; `flattenDependencyMode=all` **absent** (Netty CVE fix);
      cloud-sdk-api/aws module deps present.
- [ ] `EnhancedDynamoRepository.query()` `maxResultSize` cap + early-return (the load-bearing fix) intact.
- [ ] `QuerySpec.getMaxResultSize()` default method + `DefaultQuerySpec.maxResultSize` builder intact.
- [ ] `MessagingClient extends AutoCloseable` + `SqsMessagingClient.close()` intact.
- [ ] `AwsHttpClientWrapper.ofSyncBuilder/ofAsyncBuilder/isBuilder` + `S3ClientFactory` branch intact.
- [ ] Netty removal from `cloud-sdk-aws` still in effect.
- [ ] **Newly added** from develop: Jetty 12.1.12, slf4j 2.0.18, logback-core 1.5.38 pin + exclusion.

## 7. Test / build impact

### 7.1 The four library modules
Develop introduces **zero source changes** to `cloud-sdk-api`, `cloud-sdk-aws`, `commons`,
`dynamo-integration-test`. Their unit + DynamoDB-Local integration tests are unaffected by the incoming
develop commits and must pass exactly as they do on `origin/feature` today. Validation gate:
`mvn clean install` + `mvn -pl dynamo-integration-test verify`.

> Watch item (not a develop conflict): Jetty `12.1.9 → 12.1.12` and logback `1.5.38` are runtime/transitive
> bumps within the same minor line. Very low risk, but run the full build so any DW 5.0.2 ↔ Jetty 12.1.12 ↔
> logback 1.5.38 wiring surprise surfaces in CI, not in an app.

### 7.2 `libs/wtg-federation`
Gains ION-15990 (`TargetConfigurationResolver` + validator refactor + ~4 new/expanded test classes). Builds
**only if** `libs.dependency.version=1.R.01.003` and `junit5.jupiter.version=5.12.2` are preserved in the root
pom union (§5.1). Its tests (`TargetConfigurationResolverTest`, `OutboundRequestValidatorTest`, etc.) are new
and self-contained.

## 8. mercury-services apps impact (already on cloud-sdk)

Apps consume `commons` + `cloud-sdk-api` + `cloud-sdk-aws` (+ `dynamo-integration-test` in tests) via
`mercury.commons.version` / `mercury.cloudsdk.version`. Current fleet is fragmented across
`1.0.27 / 1.0.28 / 1.0.29-SNAPSHOT`.

- Incoming develop changes make **no source/API change** to any consumed module → rebuilt artifacts are
  **behaviourally identical**; the only consumer-visible delta is the flattened-POM dependency bumps
  (Jetty 12.1.12, logback-core 1.5.38) — an OWASP *improvement*, not a break.
- `libs/wtg-federation` is standalone and **not referenced** by any mercury-services pom → no new transitive
  dependency reaches the apps.
- Upgrading each app remains a **version-string change only**.
- ⚠️ Independent of develop, ION-16431 carries one genuinely breaking API change:
  **`MessagingClient extends AutoCloseable`** (abstract `close()` → `AbstractMethodError` for any external
  implementor). Blast radius inside `mercury-services` is nil (only `SqsMessagingClient` implements it), but
  run the §8.3 sweep from the visibility doc across **all** repos depending on `cloud-sdk-api` before publish.

**Recommended consumer version:** bump `dependency.version` to **`1.0.30-SNAPSHOT`** so the rebased line
(OWASP + ION-16431) is a distinct, pullable artifact. This matches the visibility doc §8.4 recommendation.

## 9. Recommended procedure (NOT executed — for review)

1. `git fetch origin --prune` (done for analysis).
2. **Backup:** `git branch backup/feature-ION-12310-pre-rebase-4 origin/feature/ION-12310-commons-cloudsdk-refactoring`.
3. **Fast-forward** local branch to `origin/feature` (brings in ION-16431; §2 step 1).
4. Rehearse in a throwaway worktree first: `git worktree add ../rebase-rehearsal HEAD && cd ../rebase-rehearsal && git rebase origin/develop`.
5. `git rebase origin/develop`; resolve the 3 conflicts per §5 (union `pom.xml` + `commons/pom.xml`,
   textual merge `README.md`). Keep the §6 checklist open while resolving.
6. Version: bump `dependency.version` → `1.0.30-SNAPSHOT`; align `README.md` changelog; update the stale
   `commons/pom.xml` Jetty comment to 12.1.12.
7. **Validate:** `mvn clean install` + `mvn -pl dynamo-integration-test verify`. Expect the current feature
   baseline of green unit tests **plus** the new `wtg-federation` ION-15990 tests.
8. Force-push, update PR, record result + backup ref in the session.

## 10. Open questions / risks

1. **Version scheme:** confirm the feature line should stay on `1.0.x-SNAPSHOT` (recommended) rather than
   adopting develop's `1.R.01.026`. §5.1 assumes SNAPSHOT.
2. **Do we want `wtg-federation` (S2ST + ION-15990) on this branch now?** It is isolated and unreferenced by
   apps, but it grows the reactor/CI. Same open question as the 1.0.27 rebase — carried forward.
3. **`MessagingClient.close()` external-implementor sweep** must complete before any consumer publish (§8).
4. **Do not** split the DynamoDB `maxResultSize` cap from the visibility-side DynamoDB timeout increase when
   these ship to apps (visibility doc §8.4.8).

## 11. Verification commands (evidence)

```
git fetch origin develop feature/ION-12310-commons-cloudsdk-refactoring
git rev-list --left-right --count HEAD...origin/feature                       # 0  8
git merge-base origin/feature origin/develop                                  # 0c797f4
git rev-list --count origin/feature..origin/develop                           # 5
git rev-list --count origin/develop..origin/feature                           # 52
git --no-pager log --oneline origin/feature..origin/develop                   # ION-16376 (#50), ION-15990 (#45)
git diff --stat 0c797f4 origin/develop                                        # 17 files, +519/-45
# conflict candidates = intersection of changed-file sets:
git diff --name-only 0c797f4 origin/develop        \ 
  ∩ git diff --name-only 0c797f4 origin/feature    # README.md, commons/pom.xml, pom.xml
git show bf994ef -- pom.xml commons/pom.xml                                    # ION-16376 OWASP delta
git diff --name-only 0c797f4 origin/feature -- libs/wtg-federation             # (empty) → clean apply
```
