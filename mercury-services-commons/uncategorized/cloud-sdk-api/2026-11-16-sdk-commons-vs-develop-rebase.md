# Rebase Review — `feature/ION-12310-commons-cloudsdk-refactoring` ← `origin/develop`

**Date:** 2026-11-16
**Author:** Claude Code (Claude Opus 5.5, `claude-opus-5-5`). Analysis only. **No rebase was performed on the feature branch.**
**Predecessors:** the [2026-05-15](./2026-05-15-commons-rebase.md), [2026-07-17](./2026-07-17-rebase-with-develop-owasp-jackson.md), [2026-08-13](./2026-08-13-sdk-commons-rebase-analysis.md) and [2026-08-14](./2026-08-14-sdk-commons-dynamo-changes-rebase-jetty-logback.md) rebase docs, plus the undocumented 2026-09-11 rebase (reconstructed from the reflog in §2).
**Constraint:** the feature branch is the released SDK-commons line. **`1.0.38-SNAPSHOT` is in use by most mercury-services apps.** Nothing coming in from `develop` may break those apps when they move to the next feature snapshot.

> This document is a **review-before-rebase** conflict map and plan. Do not act on it until it is reviewed.
> `cloud-sdk-api/docs/` is git-ignored (`.gitignore:17: docs/`). This file must **not** be staged or committed.

---

## 0. TL;DR

| # | Finding | Severity for 1.0.38 consumers |
|---|---------|-------------------------------|
| 1 | `develop` brings in **6 commits (2 PRs)**: PR #56 adds the CSP filter (WI01128840) and PR #58 fixes Xray vulnerabilities (WI01149458). | — |
| 2 | Rebasing replays **91 of 95** feature commits. Simulated end to end: **3 stop points, 4 file conflicts**, all in `pom.xml` or `commons/pom.xml`. All of them can be resolved mechanically. | Low |
| 3 | 🔴 **Silent break:** develop **deletes `com.inttra.mercury.security.CryptoLib` and `Encryptor`** and removes `spring-security-crypto`. Git applies the deletion **with no conflict**. The commons build stays **green (945 tests)**, so this repo's CI will not catch it. **auth** (6 main + 15 test files) and **network** (`user`, `subscriptions`) would **fail to compile** once they bump. | **Breaking** |
| 4 | 🟠 **Silent change:** develop moves MySQL from `mysql:mysql-connector-java:8.0.16` to `com.mysql:mysql-connector-j:8.4.0`. This also merges with no conflict. It changes the transitive driver for every consumer, and it makes the `mysql:mysql-connector-java` exclusions in apps stale. | Medium (behaviour) / Low (build) |
| 5 | 🟡 **CSP filter divergence:** develop's `ContentSecurityPolicyFilter` has a `form-action` directive. The feature branch **removed it later** (`fa11000`, PR #57, 2026-10-12). auth registers this filter. Someone has to decide which policy wins. | Medium (auth, browser behaviour) |
| 6 | Jackson is already **2.21.8** on both sides. Jetty is **12.1.14** on the feature branch and **12.1.13** on develop, so the feature value must be kept (develop's would be a downgrade). | Low |
| 7 | **Recommendation:** rebase, but resolve as a *union where the feature wins on public API*. Keep the 1.0.39 version line, Jetty 12.1.14 and bucket4j. **Restore `CryptoLib`/`Encryptor`** in an explicit post-rebase commit (git will not stop for it). Accept the MySQL move with targeted regression testing. Keep the feature CSP string until the CSP owner decides. Fix up the README by hand. | — |

---

## 1. Branch state (2026-11-16, after `git fetch origin`)

| Item | Value |
|------|-------|
| Feature branch | `feature/ION-12310-commons-cloudsdk-refactoring` @ `aa52175` (docs: README release note for 1.0.39-SNAPSHOT) |
| Local vs `origin/feature/...` | `0 0`. In sync, nothing unpushed. |
| Working tree | clean |
| Feature `dependency.version` | `1.0.39-SNAPSHOT` (in progress, the apway work from 2026-11-12) |
| Version consumed by apps | `1.0.38-SNAPSHOT` (`c353706`, 2026-10-29, Xray CVE fixes) |
| `origin/develop` tip | `f15b1e1` (Pull request #58, 2026-11-04) |
| Merge base | `8c6fcef` = develop PR #52 *ION-16740/ION-16741 OWASP vulnerability fixes*. This was the target of the 2026-09-11 rebase. |
| Ahead / behind | feature **95** ahead (93 commits + 2 merge commits), **6** behind (4 commits + 2 PR merges) |
| Commits the rebase replays | **91** = 95 − 2 merge commits (rebase drops merges) − 2 commits already on develop as equivalent patches |

**Commits dropped automatically as "already upstream"** (`git cherry origin/develop HEAD` marks them `-`):

| Feature commit | Equivalent on develop | Content |
|----------------|-----------------------|---------|
| `3ae7c60` | `ce373b6` | CSP filter test (`ContentSecurityPolicyFilterTest`) |
| `2c82a05` | `cb447a4` | CSP README wording tweak |

The two **merge commits** on the feature branch, `fa90f7d` (PR #57 csp string changes) and `61589e6` (PR #55 Sensitive-info-Disclosure-Registration), are flattened. The commits inside them are replayed individually, which is the same as in every previous rebase.

---

## 2. Previous rebase history (context)

| Date | Doc | Rebased onto (develop) | Brought in | Stops / conflicts | Resulting version |
|------|-----|------------------------|-----------|-------------------|-------------------|
| 2026-05-15 | `2026-05-15-commons-rebase.md` | `cc001e3`… | 10 develop commits | `pom.xml` (HIGH), `README.md` | 1.0.23-SNAPSHOT |
| 2026-07-17 | `2026-07-17-rebase-with-develop-owasp-jackson.md` | OWASP/Jackson (after it was reinstated on develop) | S2ST module + OWASP/Jackson | 3 stops: `pom.xml`, `README.md`, `commons/pom.xml` | 1.0.27-SNAPSHOT |
| 2026-08-13/14 | `2026-08-13-…analysis.md`, `2026-08-14-…jetty-logback.md` | `0c797f4` → ION-16376 Jetty/logback, ION-15990 wtg-federation | Jetty 12.1.12, logback, federation | 1 stop: `pom.xml` (`fa2d428`, `dependency.version`) | 1.0.30-SNAPSHOT |
| 2026-09-11 | *(no doc; reconstructed from reflog)* | `8c6fcef` (PR #52, ION-16740/16741 OWASP) | OWASP fixes | 63 picks between 15:12:34 and 15:12:55, **no stops** (reflog has only `start`, `pick` and `finish` entries). Backup: `backup/pre-develop-rebase-2026-09-11` @ `9dd413c` | 1.0.33-SNAPSHOT |
| **2026-11-16** | **this doc** | **`f15b1e1`** (PR #56 CSP + PR #58 Xray) | CSP filter, Jackson 2.21.8, Jetty 12.1.13, MySQL 8.4.0, **crypto removal** | **3 stops / 4 file conflicts** (simulated, §4.2) | proposed 1.0.39 or 1.0.40-SNAPSHOT (§9, Q4) |

**Recurring pattern from earlier rebases:** every rebase has hit the root `pom.xml` `dependency.version` line (`1.R.01.0xx` on develop vs `1.0.x-SNAPSHOT` on the feature branch), and the resolution was always **keep the feature line**. This time the version-line conflict comes back at the very first feature commit (`1be6b58`, `1.0.0-SNAPSHOT`), as it did in 2026-05.

**What is new this time:** earlier develop changes only **added or upgraded**. This develop change is the first one that **removes public API** from `commons`, so a clean merge does not mean a safe merge.

---

## 3. What comes in from `develop` (`8c6fcef..origin/develop`)

```
f15b1e1 Anand N S    2026-11-04 Pull request #58: WI01149458:T78662935 - Commons(SDK1) Vulnerability Fixes
e28bef0 Anand N S    2026-11-02 WI01149458:T78662935 - Commons(SDK1) Vulnerability Fixes
b16ccd6 Riya Chauhan 2026-09-29 Pull request #56: WI01128840 content security policy filter class added.
cb447a4 Riya Chauhan 2026-09-30 WI01128840 content security policy filter class added.   (README)
ce373b6 Riya Chauhan 2026-09-29 WI01128840 CSP filter test case Green phase
0c7ff23 Riya Chauhan 2026-09-29 WI01128840 content security policy filter class added.   (class + pom ver)
```

Net diff: **9 files, +86 / −179**.

### 3.1 PR #56: CSP filter (WI01128840), develop release `1.R.01.029`

* Adds `commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java`, a JAX-RS `ContainerResponseFilter` that `putSingle`s a fixed `Content-Security-Policy` header.
* Adds `ContentSecurityPolicyFilterTest` (2 tests).
* **The feature branch already has this filter.** It was cherry-picked as `0240e74` and `3ae7c60`, and then **changed on the feature branch only** by `fa11000` (PR #57, 2026-10-12, same author), which **removed the `form-action` directive**. See §6.

### 3.2 PR #58: Xray vulnerability fixes (WI01149458), develop release `1.R.01.030`

| Change | develop value | feature value today | Overlap with feature |
|--------|---------------|---------------------|----------------------|
| Jackson | 2.21.6 → **2.21.8** | **2.21.8** (done in 1.0.38) | Same value, comment text differs → conflict |
| Jetty | 12.1.12 → **12.1.13** | **12.1.14** (1.0.38) | Feature is newer → **keep 12.1.14** |
| spring-security-crypto | **removed** from `commons/pom.xml` and the root property | kept as **`<optional>true</optional>`** (1.0.38) | Conflict in both poms |
| `CryptoLib`, `Encryptor` + their tests | **deleted** | present, used by auth and network | ⚠️ **No conflict. Applied silently.** |
| MySQL driver | `mysql:mysql-connector-java:8.0.16` → **`com.mysql:mysql-connector-j:8.4.0`** | 8.0.16, old coordinates | ⚠️ **No conflict. Applied silently.** |
| `dependency.version` | `1.R.01.028` → `1.R.01.030` | `1.0.39-SNAPSHOT` | Conflict, keep feature |
| README | adds v1.R.01.029 and v1.R.01.030 sections | 1.0.x-SNAPSHOT sections | Conflict / duplicated text |

---

## 4. Conflict analysis

### 4.1 Final-state view (`git merge-tree`, the end-to-end merge of the two tips)

`git merge-tree --write-tree --name-only --messages HEAD origin/develop` reports **4 conflicted files**:

| File | Type | Hunks | Notes |
|------|------|-------|-------|
| `pom.xml` (root) | content | 3 | (a) `dependency.version`; (b) Jetty/Jackson property and comment block; (c) `bucket4j.version` + `spring.sercurity.crypto.version` vs develop's deletion |
| `commons/pom.xml` | content | 1 | feature's optional `spring-security-crypto` block vs develop's deletion of the dependency |
| `commons/.../auth/ContentSecurityPolicyFilter.java` | add/add | 1 | feature ends `font-src 'self' data:;`; develop adds `form-action …` |
| `README.md` | content | – | release-note sections on both sides |

The same merged tree shows **silent changes with no conflict marker**:

* `commons/src/main/java/com/inttra/mercury/security/CryptoLib.java`: **deleted**
* `commons/src/main/java/com/inttra/mercury/security/Encryptor.java`: **deleted**
* `commons/src/test/.../security/CryptoLibTest.java`, `EncryptorTest.java`: **deleted**
* `commons/pom.xml`: `<groupId>com.mysql</groupId><artifactId>mysql-connector-j</artifactId>`
* `pom.xml`: `<mysql.connector.version>8.4.0</mysql.connector.version>`

(`security/model/TextEncryptionConfig.java` stays. auth's `AuthServiceConfig` uses it.)

### 4.2 Rebase view (simulated per commit)

A rebase replays commit by commit, so the stop points differ from the merge view. To get them, I ran the **real rebase in a throwaway, detached `git worktree`** in the session scratchpad (script in §11.6). The feature branch was not touched. At each stop the simulation resolved only the conflicted **hunks** in favour of the replayed (feature) commit (`git merge-file --theirs`) so it could continue. Non-conflicting develop hunks were kept.

| Stop | Step | Commit being replayed | File(s) | What collides | Resolution to apply |
|------|------|-----------------------|---------|---------------|---------------------|
| **#1** | 3/91 | `1be6b58` 2025-08-19 *ION-12310 pom changes* (Arijit Kundu) | `pom.xml` (1 hunk) | `dependency.version`: develop `1.R.01.030` vs commit `1.0.0-SNAPSHOT` | **Keep the commit's line** (`1.0.0-SNAPSHOT`). Later commits carry it forward to 1.0.39. This is the same resolution as every previous rebase. |
| **#2** | 65/91 | `ed07226` 2026-09-22 *WI01127797 Sensitive-info-Disclosure-Registration* (Raghunandan Shastry) | `pom.xml` (1 hunk) | the commit adds `bucket4j.version` right above `spring.sercurity.crypto.version`, which develop deleted | **Keep `bucket4j.version`.** **Keep `spring.sercurity.crypto.version`** (needed if crypto is restored, §5.1; drop it only under Option B). |
| **#3** | 69/91 | `c353706` 2026-10-29 *commons 1.0.38-SNAPSHOT: Xray CVE fixes* (Arijit Kundu) | `pom.xml` (1 hunk), `commons/pom.xml` (1 hunk) | root: Jetty 12.1.13 (develop) vs **12.1.14**, plus the Jackson comment text. commons: develop deleted `spring-security-crypto` vs feature's `optional` block | root: **keep `jetty.version` 12.1.14**. For the comments, optionally fold develop's CVE IDs into the feature comment. Jackson value is identical. commons: **keep the optional `spring-security-crypto` block** (unless Option B). |

* **Total: 3 stops, 4 file conflicts.** No Java source conflicts during the rebase.
* `ContentSecurityPolicyFilter.java` **does not stop** during the rebase. `0240e74` adds identical content on top of develop's file, then `fa11000` applies cleanly and removes `form-action`. **Net result: the feature's string wins silently.** That is the 1.0.38-compatible outcome, but it reverts develop's policy (see §6).
* `README.md` **does not stop**, but the auto-merge leaves **duplicated text** ("Content security policy filter class added" under both a v1.R.01.029 and a v1.R.01.028 heading) and changes the top line to `Latest release version: v1.R.01.030`. Clean it up by hand.

**The simulated rebase result compared with today's feature tip** (`git diff --stat HEAD <sim-tip>`) is the true "what develop does to the SDK line":

```
 README.md                                     | 11 +++-
 commons/pom.xml                               |  4 +-      <- mysql coordinates
 .../com/inttra/mercury/security/CryptoLib.java     | 27 ---------   <- deleted
 .../com/inttra/mercury/security/Encryptor.java     | 47 ----------    <- deleted
 .../com/inttra/mercury/security/CryptoLibTest.java | 24 --------    <- deleted
 .../com/inttra/mercury/security/EncryptorTest.java | 65 ----------    <- deleted
 pom.xml                                       |  3 +-      <- mysql 8.4.0
 7 files changed, 14 insertions(+), 167 deletions(-)
```

**Build check of the simulated result:** `mvn -o -B -pl commons -am verify` gave **BUILD SUCCESS. cloud-sdk-api, dynamo-integration-test, cloud-sdk-aws and commons all passed, 945 commons tests, 0 failures.** This proves the break in §5.1 is **invisible to this repo's build**. Only consumers would see it.

---

## 5. Silent changes: what they mean for 1.0.38 consumers

### 5.1 🔴 `CryptoLib` / `Encryptor` deletion (develop `e28bef0`)

**What develop intends:** remove `spring-security-crypto` (Xray: CVE-2025-22228, the BCrypt `matches` issue with passwords over 72 bytes) and the two classes built on it. Develop's README says *"Services using these classes must declare their own crypto dependency."* That wording is misleading: services would also have to **bring their own copy of the classes**, because the classes are gone, not just the jar.

**What the feature branch already did in 1.0.38 (`c353706`):** it marked `spring-security-crypto` `<optional>true</optional>`. The jar is therefore **no longer passed on** to consumers, so Xray no longer sees it in app builds. It **kept the classes** so apps stay source-compatible. Apps that use them declare the jar themselves. That handles the same CVE at app level **without breaking API**.

**Consumers that use the classes** (grep of `mercury-services`, see §11.4):

| App / module | Main sources | Tests | How it gets the crypto jar today |
|--------------|--------------|-------|----------------------------------|
| `auth` | `AuthApplicationModule` (Encryptor), `ClientService`, `ClientResource`, `OAuthMetadataService` (Encryptor), `UserService`, `PasswordValidationService` | 15 test classes | `spring-security-core:4.2.4.RELEASE` (via `spring-security-saml2-core`) **bundles the crypto packages**. The fat jar contains `org/springframework/security/crypto/bcrypt/BCryptPasswordEncoder.class` (verified). |
| `network/user` | `MercuryUserService` (CryptoLib) | 2 | declares `spring-security-crypto` itself, resolves **6.4.4** |
| `network/subscriptions` | `SubscriptionsDao` (Encryptor) | 1 IT | declares `spring-security-crypto` itself |

**If develop's deletion is accepted:** the next feature snapshot gives auth and network **`package com.inttra.mercury.security does not exist` / cannot find symbol `CryptoLib`** compile errors. That is a breaking API change on a line that is supposed to be drop-in. It also cannot be fixed only in the consumers' poms: each app would have to copy the classes in, or migrate to `BCryptPasswordEncoder` and `Encryptors` directly.

**Options:**

| Option | What | Breaks 1.0.38 apps? | CVE posture |
|--------|------|---------------------|-------------|
| **A** | Restore both classes plus tests; keep `spring-security-crypto` `optional` at `4.2.3.RELEASE` (exactly the 1.0.38 state) | No | Same as 1.0.38: not shipped to consumers, but commons still builds against a version flagged as vulnerable |
| **A′ (recommended)** | As A, but bump `spring.sercurity.crypto.version` to **6.4.4** or later (the CVE-2025-22228 fix line; Java 17 baseline matches) | No | Commons' own build is clean as well. `network/user` already runs `CryptoLib`/`Encryptor` on 6.4.4 at runtime, which is empirical evidence of API compatibility. `CryptoLibTest`/`EncryptorTest` must pass on 6.4.4. |
| **B** | Accept the deletion | **Yes**: auth and network fail to compile | Clean |
| **B′** | Accept later: restore now, mark both classes `@Deprecated(forRemoval = true)` with a README migration note, and remove them in a coordinated release once auth and network have moved | No (now) | Clean once removed |

**Mechanics:** git will not stop for this, so it must be an **explicit post-rebase commit**, for example:

```bash
git checkout backup/feature-ION-12310-pre-rebase-2026-11-16 -- \
  commons/src/main/java/com/inttra/mercury/security/CryptoLib.java \
  commons/src/main/java/com/inttra/mercury/security/Encryptor.java \
  commons/src/test/java/com/inttra/mercury/security/CryptoLibTest.java \
  commons/src/test/java/com/inttra/mercury/security/EncryptorTest.java
```

**Merge-back note:** when the feature branch is eventually merged into develop, this restore commit **re-adds the classes on develop**. Agree this with the PR #58 owner (Anand N S) up front: either develop accepts Option B′, or the restore is deliberately reverted in that merge after auth and network have migrated.

### 5.2 🟠 MySQL `mysql:mysql-connector-java:8.0.16` → `com.mysql:mysql-connector-j:8.4.0` (develop `e28bef0`)

**What it fixes:** CVE-2023-22102 and older Connector/J CVEs. Upstream moved to the `com.mysql:mysql-connector-j` coordinates after 8.0.31. The `protobuf-java` exclusion in `commons/pom.xml` is kept by develop's change.

**Why it is "silent" for Maven consumers:** the **GroupId:ArtifactId changes**, so Maven treats it as a *different* artifact. Mediation (nearest-wins) and consumer exclusions keyed on the old GA no longer apply.

| Consumer situation | Apps (on 1.0.38) | Effect after the bump |
|--------------------|------------------|------------------------|
| Excludes `mysql:mysql-connector-java` from commons **and** declares `com.mysql:mysql-connector-j` directly | `tx-tracking` (26.10.0), `visibility/visibility-commons` (26.10.0) | Exclusion is stale but harmless. Same GA as commons' new dependency, so their **direct 26.10.0 wins** (nearest). **No change.** |
| Excludes `mysql:mysql-connector-java`, **no** MySQL use | `watermill-publisher/watermill-commons` | Exclusion no longer matches, so **`mysql-connector-j-8.4.0.jar` now lands on the classpath**. Unused at runtime, but it is a new jar in the Xray scan and the shaded app. Fix by updating the exclusion to `com.mysql:mysql-connector-j`. |
| No exclusion, uses MySQL | `auth` (`aws-mysql-jdbc` 1.1.0), `network/server` (`aws-mysql-jdbc` 1.1.10) | Connector/J changes **8.0.16 → 8.4.0**. Production configs use `jdbc:mysql:aws://` (16×) and `jdbc:mysql:aurora://` (1×). Those go through the **AWS driver, which shades its own copy** (`software/aws/rds/jdbc/mysql/shading/com/mysql/cj/...`, verified in 1.1.0, 1.1.10 and 1.1.15), so there is **no class overlap**. Plain `jdbc:mysql://` (3×, sample/test configs) goes to Connector/J 8.4.0. |
| No exclusion, no MySQL use | most others (booking, booking-bridge, rates, registration, shipping-instruction, value-added-service, partner-integrator, bill-of-lading-v2, cargoscreen, selfservicereportsengine) | The driver jar is swapped, nothing else. Verify it is not used. |

**Driver class names:** some configs name the legacy `com.mysql.jdbc.Driver` (auth `sample.yaml`, network `sample.yaml` and test, `libs/embedded-mysql/MyPooledDataSourceFactory`, oceanschedules). **Both `com/mysql/jdbc/Driver.class` and `com/mysql/cj/jdbc/Driver.class` exist in `mysql-connector-j-8.4.0.jar`** (verified), so there is no ClassNotFoundException.

**Recommendation:** **accept** develop's change. It is a real CVE fix, it is build-compatible for every 1.0.38 consumer, and production DB traffic goes through the shaded AWS driver. Gate it on (a) auth and network integration tests against MySQL, and (b) a follow-up ticket to update stale `mysql:mysql-connector-java` exclusions in `watermill-commons`, `tx-tracking` and `visibility-commons`. If the line must stay byte-for-byte drop-in, the alternative is to **defer**: revert the two-line change in a post-rebase commit and take it in a separate snapshot.

### 5.3 Non-breaking incoming changes

* **Jackson 2.21.8**: identical value on both sides, comment text only.
* **Jetty**: keep **12.1.14**. Taking develop's 12.1.13 would *downgrade* what 1.0.38 apps already run. Both versions clear CVE-2026-19863/19864/76182.
* **`dependency.version`**: keep the feature line.

---

## 6. 🟡 CSP filter: two policies for one class

| Line | `font-src` tail | `form-action` | Where it is |
|------|-----------------|---------------|-------------|
| develop (`0c7ff23`, released in `1.R.01.029/030`) | `"font-src 'self' data:; "` | `form-action 'self' e2open.com inttra.com *.inttra.com *.e2open.com wss://*.e2open.com;` | develop |
| feature after `fa11000` (PR #57, 2026-10-12): **what 1.0.38 apps run** | `"font-src 'self' data:;"` | *(removed)* | feature |

**Consumer:** `auth`, via `AuthApplicationModule:53` → `environment.jersey().register(ContentSecurityPolicyFilter.class)`, verified by `AuthApplicationModuleTest:67`. No other app registers it.

**What it means:** `form-action` limits where an HTML `<form>` on an auth-served page can submit to. auth serves SSO flows (SAML2 / OAuth2 OID). A form auto-posting to an external IdP or a partner URL outside `*.inttra.com`/`*.e2open.com` would be **blocked by the browser** under develop's policy. This is the likely reason `fa11000` removed it. That is a hypothesis; confirm with the commit author.

**Rebase outcome without intervention:** the feature string wins (§4.2). That is **non-breaking for 1.0.38 auth**, but it leaves develop and the feature line with different CSP policies.

**Decision needed** (owner: Riya Chauhan / app-sec): which policy is canonical? If the feature string is right, develop should get the `fa11000` change too. If develop's is right, auth's SSO flows need browser testing before the feature line adopts it.

---

## 7. Impact matrix: mercury-services apps on `1.0.38-SNAPSHOT`

Found with `grep mercury.commons.version` across `mercury-services` (`develop` @ `53e77f4e8f`).

| App | commons | Crypto removal (§5.1) | MySQL move (§5.2) | CSP (§6) |
|-----|---------|-----------------------|-------------------|----------|
| auth | 1.0.38 | 🔴 compile break (6 main + 15 test) | 🟠 8.0.16→8.4.0; prod via shaded aws-mysql-jdbc 1.1.0 | 🟡 only if develop string adopted |
| network (user, subscriptions, server) | 1.0.38 | 🔴 compile break (`MercuryUserService`, `SubscriptionsDao`) | 🟠 same as auth (aws-mysql-jdbc 1.1.10) | – |
| tx-tracking | 1.0.38 | – | 🟢 direct `mysql-connector-j` 26.10.0 wins | – |
| visibility (+ visibility-commons) | 1.0.38 | – (stale crypto exclusion, harmless) | 🟢 direct 26.10.0 wins | – |
| watermill-commons | 1.0.38 | – | 🟡 unwanted 8.4.0 jar appears (stale exclusion) | – |
| watermill-cargo-visibility-subscription | dynamo-integration-test 1.0.38 | – | – | – |
| booking, booking-bridge, booking-cargoscreen, bill-of-lading-v2, partner-integrator, rates, registration, selfservicereportsengine, shipping-instruction, value-added-service | 1.0.38 | – | 🟢 transitive driver swap only | – |
| db-migration, webbl | 1.0.34 | not affected until they bump | | |
| lambda/* | 1.0.31 | not affected until they bump | | |
| bill-of-lading (1.R.01.021), oceanschedules / oceanschedules-process (1.R.01.030) | develop line | already on develop's artifacts, not affected by this rebase | | |

---

## 8. Recommended resolution (per file)

| File | Resolve to |
|------|------------|
| `pom.xml` `dependency.version` | feature line (stop #1: the commit's own value) |
| `pom.xml` `jetty.version` | **12.1.14**, feature comment (optionally add develop's CVE IDs) |
| `pom.xml` `jackson.*` | 2.21.8 (identical). Use either comment; prefer develop's CVE-ID comment for traceability. |
| `pom.xml` `bucket4j.version` | keep |
| `pom.xml` `spring.sercurity.crypto.version` | keep (A/A′: bump to 6.4.4 under A′) |
| `pom.xml` `mysql.connector.version` | auto-merged **8.4.0**: accept (or defer, §5.2) |
| `commons/pom.xml` `spring-security-crypto` | keep the optional block (A/A′) |
| `commons/pom.xml` mysql coordinates | auto-merged `com.mysql:mysql-connector-j`: accept (or defer) |
| `CryptoLib`, `Encryptor` + tests | **restore** (post-rebase commit) |
| `ContentSecurityPolicyFilter` | feature string (auto). Pending the §6 decision. |
| `README.md` | hand-merge: remove the duplicated CSP entry. Keep the top line as feature practice dictates. Add the develop v1.R.01.029/030 notes **with an explicit remark that the crypto removal is not applied on the SDK line**. Add the new 1.0.x-SNAPSHOT block. |

**Success criterion after the rebase:** `git diff --stat backup/feature-ION-12310-pre-rebase-2026-11-16 HEAD` should show **only** README, the MySQL coordinates and version (3 lines in 2 poms), and any deliberate changes (A′ crypto bump, version bump). **No deletions under `commons/src/main/java/com/inttra/mercury/security/`.**

---

## 9. Proposed procedure (NOT executed, for review)

```bash
# 0. Pre-flight
git status                                   # must be clean
git fetch origin
git rev-list --left-right --count HEAD...origin/feature/ION-12310-commons-cloudsdk-refactoring   # expect 0 0

# 1. Backup (local + remote)
git branch backup/feature-ION-12310-pre-rebase-2026-11-16
git push origin backup/feature-ION-12310-pre-rebase-2026-11-16

# 2. Rebase
git rebase origin/develop
#   stop #1 (1be6b58)  pom.xml       -> keep commit's dependency.version line
#   stop #2 (ed07226)  pom.xml       -> keep bucket4j.version AND spring.sercurity.crypto.version
#   stop #3 (c353706)  pom.xml       -> jetty 12.1.14; jackson 2.21.8 (comment of choice)
#                      commons/pom.xml -> keep optional spring-security-crypto block
#   at each stop:  git add <file> && git rebase --continue

# 3. Post-rebase commits (one concern per commit)
git checkout backup/feature-ION-12310-pre-rebase-2026-11-16 -- \
  commons/src/main/java/com/inttra/mercury/security/CryptoLib.java \
  commons/src/main/java/com/inttra/mercury/security/Encryptor.java \
  commons/src/test/java/com/inttra/mercury/security/CryptoLibTest.java \
  commons/src/test/java/com/inttra/mercury/security/EncryptorTest.java
git commit -m "ION-12310: restore CryptoLib/Encryptor removed by develop e28bef0 (keeps auth/network source-compatible)"
#   (A' only) bump spring.sercurity.crypto.version -> 6.4.4 ; commit
#   README hand-merge ; version bump (see Q4) ; commit

# 4. Verify
git diff --stat backup/feature-ION-12310-pre-rebase-2026-11-16 HEAD     # §8 success criterion
git ls-files commons/src/main/java/com/inttra/mercury/security/          # CryptoLib + Encryptor present
grep -n "jetty.version\|mysql.connector.version\|spring.sercurity" pom.xml
mvn clean verify                                                          # all modules green
#   consumer check (auth, network) against the new snapshot BEFORE apps bump:
#   mvn -o dependency:tree -Dincludes=com.mysql,mysql,org.springframework.security  (in auth, network/user)

# 5. Publish
git push --force-with-lease origin feature/ION-12310-commons-cloudsdk-refactoring
```

---

## 10. Open questions (resolve before rebasing)

1. **Crypto:** Option A, **A′ (recommended)** or B′? Option B is not acceptable on this line.
2. **MySQL 8.4.0:** accept now (recommended, with auth/network DB regression) or defer to a separate snapshot?
3. **CSP `form-action`:** which string is canonical? Owner: Riya Chauhan / app-sec. Until then, keep the feature string.
4. **Version after the rebase:** has `1.0.39-SNAPSHOT` already been deployed to Artifactory and picked up by apway or any app? If yes, bump to **1.0.40-SNAPSHOT** so the rebased content (MySQL change) is not slipped under an existing snapshot. If no, keep 1.0.39.
5. **Merge-back:** agree with the develop owners (PR #58, Anand N S) how the restored crypto classes and the CSP string will reconcile when the feature merges into develop.
6. **Pre-existing, out of scope:** auth's crypto comes from `spring-security-core:4.2.4.RELEASE` (EOL, bundled crypto), which is likely within the CVE-2025-22228 range. That is auth's own dependency and is not changed by this rebase. Raise it separately.

---

## 11. Command log (everything run for this analysis, with syntax and explanation)

All commands are **read-only** with respect to the feature branch. The only writes were to a disposable worktree in the session scratchpad (§11.6), which was then unregistered.

### 11.1 Fetch and branch topology

```bash
git fetch origin
```
Updates the remote-tracking refs (`origin/develop`, `origin/feature/...`) without touching local branches or the working tree.

```bash
git merge-base HEAD origin/develop
# -> 8c6fcef0cb8e1aca1d645e6f08379f75623591ac
```
Finds the best common ancestor: the point the feature last rebased onto. Everything after it on either side is "new".

```bash
git rev-list --left-right --count HEAD...origin/develop
# -> 95  6
```
`A...B` (three dots) is the symmetric difference. `--left-right --count` prints `<only-in-left> <only-in-right>`, which gives the feature-ahead and develop-ahead counts.

```bash
git rev-list --left-right --count HEAD...origin/feature/ION-12310-commons-cloudsdk-refactoring
# -> 0  0
```
Confirms the local branch equals the pushed branch.

```bash
git log --oneline --no-merges HEAD..origin/develop
git log --oneline --merges   HEAD..origin/develop
git log --format='%h %an %ad %s' --date=short 8c6fcef..origin/develop
```
`A..B` (two dots) means "commits reachable from B but not A", i.e. what is incoming. `--no-merges` / `--merges` split real commits from PR merge commits. `--format` adds author and date.

```bash
git log --merges --oneline 8c6fcef..HEAD
```
Lists the feature's own merge commits (`fa90f7d`, `61589e6`). Rebase drops merges, which explains part of the 95 → 91 gap.

### 11.2 Scope the incoming diff and predict conflicts

```bash
git diff --stat 8c6fcef origin/develop
git diff --stat 8c6fcef origin/develop --diff-filter=D
```
The net change develop makes since the merge base. `--diff-filter=D` shows only **deleted** files (`CryptoLib`, `Encryptor` and their tests).

```bash
comm -12 <(git diff --name-only 8c6fcef origin/develop | sort) \
         <(git diff --name-only 8c6fcef HEAD          | sort)
```
`comm -12` prints lines common to both sorted lists: the files changed on **both** sides, which are the only possible content-conflict candidates. Result: `README.md`, `commons/pom.xml`, `ContentSecurityPolicyFilter.java`, `ContentSecurityPolicyFilterTest.java`, `pom.xml`.

```bash
git diff 8c6fcef origin/develop -- pom.xml commons/pom.xml README.md \
  commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java \
  commons/src/test/java/com/inttra/mercury/auth/ContentSecurityPolicyFilterTest.java
```
The full incoming hunks for the overlapping files. `--` separates revisions from paths.

```bash
git show HEAD:pom.xml | sed -n '1,140p'
git show HEAD:commons/pom.xml | grep -nE -B2 -A14 'mysql-connector|spring-security-crypto'
```
`git show <rev>:<path>` prints a file as it is at a revision without checking it out. `grep -B/-A` adds context lines before and after.

### 11.3 Patch equivalence and CSP history

```bash
git log --oneline 8c6fcef..HEAD -- commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java \
                                   commons/src/test/java/com/inttra/mercury/auth/ContentSecurityPolicyFilterTest.java
git diff HEAD origin/develop -- commons/src/main/java/com/inttra/mercury/auth/
```
History of the CSP files on the feature branch (`0240e74`, `3ae7c60`, `fa11000`) and the current tip-to-tip difference. This also shows the feature-only `/registration/*` entries in `AuthenticationFilter`, which are not a conflict.

```bash
git show <sha> | git patch-id
```
`git patch-id` hashes a diff while ignoring line numbers and whitespace. Identical IDs mean the same change, which is how rebase decides to skip a commit.

```bash
git cherry -v HEAD origin/develop     # develop commits: '-' = already on feature
git cherry    origin/develop HEAD     # feature commits: '-' = already on develop -> skipped by rebase
```
`git cherry <upstream> <head>` lists commits in `<head>` that are not in `<upstream>`. `-` means a patch-equivalent commit exists upstream. Result: `3ae7c60` and `2c82a05` are dropped.

```bash
git show --stat --format='%h %ad %s' --date=iso 0c7ff23   # (also ce373b6, cb447a4, 0240e74)
git show --format='%h %an %ad %s' --date=iso fa11000
```
Per-commit view: what each CSP commit touched and when. This established that `fa11000` (feature-only) removes `form-action`.

### 11.4 Previous rebases and backups

```bash
git reflog --date=iso | grep -iE 'rebase|merge|reset'
git reflog --date=iso | grep -E 'rebase \(start\)'
git reflog --date=iso | grep '2026-09-11' | grep -vE 'rebase \(pick\)'
git reflog --date=iso | grep '2026-09-11' | grep -cE 'rebase \(pick\)'
```
The reflog records every movement of HEAD. `rebase (start)` shows the base each rebase used. A rebase that never stopped has only `start`, `pick…` and `finish` entries, with no `continue`. `grep -c` counts the picks (63 on 2026-09-11).

```bash
git branch -a | grep -iE 'backup|ION-12310'
git log -1 --format='%h %s' backup/pre-develop-rebase-2026-09-11
git log --oneline 0c797f4..8c6fcef --no-merges
git log --oneline --format='%h %ad %s' --date=short HEAD -- pom.xml | grep -iE '1\.0\.3[6-9]'
git show --stat --format='%h %ad %s%n%b' --date=short c353706
```
Lists existing backup branches and what the 2026-09-11 rebase pulled in, finds the 1.0.38/1.0.39 version commits, and reads the full 1.0.38 commit message. That message is what established the "spring-security-crypto optional" decision.

```bash
for f in cloud-sdk-api/docs/2026-0*-*rebase*.md; do grep -nE '^#{1,3} ' "$f"; sed -n '1,16p' "$f"; done
git check-ignore -v cloud-sdk-api/docs/2026-11-16-sdk-commons-vs-develop-rebase.md
# -> .gitignore:17:docs/
```
Section headings and preambles of the earlier rebase docs. `git check-ignore -v` proves which ignore rule covers this document, so it can't be committed by accident.

### 11.5 Final-state conflict prediction (no checkout, no index change)

```bash
git merge-tree --write-tree --name-only --messages HEAD origin/develop
# -> <tree-oid>, conflicted file list, CONFLICT messages; exit 1 = conflicts
```
Git 2.38+ "real" merge-tree. It performs a full in-memory three-way merge and writes the result (with conflict markers) as a **tree object** only. No branch, index or working-tree change. `--name-only` lists conflicted paths; `--messages` prints the `CONFLICT (content|add/add)` reasons.

```bash
T=197ebcdf1b4b0621c2ecc2d70160458b2720cac5
git show $T:pom.xml | awk '/^<<<<<<< /{p=1} p{print NR": "$0} /^>>>>>>> /{p=0; print "----"}'
git show $T:commons/pom.xml | grep -n -A3 '<artifactId>mysql-connector'
git ls-tree -r --name-only $T commons/src | grep -i security
```
Reads the merged tree: `awk` prints only the regions between conflict markers, `grep` confirms what auto-merged (the MySQL GA), and `git ls-tree -r` lists files in the tree to prove `CryptoLib`/`Encryptor` are silently gone.

### 11.6 Per-commit rebase simulation (disposable worktree)

Script `C:\Users\arijit.kundu\AppData\Local\Temp\claude\eefc1ea3b32fcceb\2752c1d0-395d-403b-9dfd-3f50e5253dc0\scratchpad\sim-rebase.sh`:

```sh
git worktree add --detach "$WT" HEAD          # separate checkout, detached: no branch is moved
cd "$WT"
GIT_EDITOR=true git rebase origin/develop     # real rebase; GIT_EDITOR=true accepts messages non-interactively
while [ -d "$(git rev-parse --git-path rebase-merge)" ]; do      # rebase still in progress?
  RM=$(git rev-parse --git-path rebase-merge)
  files=$(git diff --name-only --diff-filter=U)                  # U = unmerged (conflicted) paths
  # stop number, step "msgnum/end" and stopped commit come from $RM/msgnum, $RM/end, $RM/stopped-sha
  for f in $files; do
    grep -c '^<<<<<<<' "$f"                                      # hunks in this file
    git show :1:"$f" > .b; git show :2:"$f" > .o; git show :3:"$f" > .t   # index stages: base / ours(develop+replayed) / theirs(commit)
    git merge-file --theirs .o .b .t; cp .o "$f"; git add "$f"   # per-HUNK resolve toward the commit; keeps develop's non-conflicting hunks
  done
  GIT_EDITOR=true git rebase --continue
done
git rev-list --count origin/develop..HEAD      # commits replayed (91)
```
Why this way: it reproduces the actual stop points of a real `git rebase`, which `merge-tree` cannot show. `git merge-file --theirs` resolves only the conflicting hunks, unlike `git checkout --theirs`, which would discard develop's whole file. That keeps the simulation close to a sensible resolution. The resolution is mechanical and only for counting. §8 gives the intended resolution.

```bash
git diff --stat HEAD bd551d7                  # bd551d7 = simulated rebased tip
git diff HEAD bd551d7 -- pom.xml commons/pom.xml commons/src/main/java/com/inttra/mercury/auth/ContentSecurityPolicyFilter.java README.md
git show --format='%h %an %ad %s' --date=short 1be6b58 -- pom.xml     # (also ed07226)
```
Net effect of the rebase on the SDK line, and the content of the commits that stopped.

```bash
git -c core.longpaths=true worktree remove --force <scratchpad>/rebase-sim
git worktree prune
git worktree list            # only the main worktree remains
```
Unregisters the disposable worktree. `core.longpaths` handles Windows' 260-character path limit on deep Maven `target/` paths. The simulated commit `bd551d7` is unreferenced and will be garbage-collected. Leftover files may remain in the scratchpad folder, which is harmless.

### 11.7 Maven

```bash
# in the simulated worktree
mvn -o -B -pl commons -am verify
```
`-o` offline (use `~/.m2`, no network). `-B` batch mode (no colour or progress). `-pl commons` builds the commons module, and `-am` ("also make") also builds the modules it depends on. `verify` runs compile, unit tests and integration-test phases but **does not `install`**, so `~/.m2`'s `1.0.39-SNAPSHOT` (used by local app builds) is not overwritten. Result: BUILD SUCCESS, 945 commons tests green.

```bash
# in mercury-services/auth and mercury-services/network/user
mvn -o dependency:tree -Dincludes=org.springframework.security:spring-security-crypto,mysql:mysql-connector-java,com.mysql:mysql-connector-j
mvn -o dependency:tree -Dincludes=org.springframework.security
mvn -o dependency:tree -Dincludes=software.aws.rds
```
`dependency:tree` prints the resolved graph. `-Dincludes=groupId[:artifactId]` filters it to the paths leading to those artifacts. (Do **not** combine it with `-q`, which suppresses the tree, because the tree is logged at INFO.) This showed auth gets `mysql-connector-java:8.0.16` via commons and crypto via `spring-security-core:4.2.4`, network/user resolves `spring-security-crypto:6.4.4`, and auth uses `aws-mysql-jdbc:1.1.0`.

### 11.8 grep / jar inspection in `mercury-services`

```bash
grep -rn --include=pom.xml -E '1\.0\.3[0-9]-SNAPSHOT|1\.R\.01\.0[0-9]+' . | grep -v target
```
Which commons version each app pins (§7).

```bash
grep -rlE 'com\.inttra\.mercury\.security\.(CryptoLib|Encryptor)|\b(CryptoLib|Encryptor)\b' --include=*.java . | grep -v /target/
grep -rnE 'import com\.inttra\.mercury\.security\.(CryptoLib|Encryptor)' --include=*.java . | grep -v /target/
```
Every consumer of the classes develop deletes. `-l` lists files only; the second command shows the exact import lines.

```bash
grep -rn --include=pom.xml 'spring-security-crypto' . | grep -v target
grep -rn --include=pom.xml -B1 -A2 -E 'mysql-connector' . | grep -v target
grep -B10 'mysql-connector-java' tx-tracking/pom.xml | grep artifactId      # (also visibility-commons, watermill-commons)
```
Which apps declare or exclude the crypto jar and the MySQL driver, and which dependency each exclusion sits under (to confirm it is an exclusion *from commons*).

```bash
grep -rn --include=*.java 'ContentSecurityPolicyFilter' . | grep -v /target/
grep -rn 'TextEncryptionConfig' --include=*.java . | grep -v target
```
Who registers the CSP filter (auth only), and confirmation that `TextEncryptionConfig` (kept by develop) is used by auth.

```bash
grep -rhoE 'com\.mysql(\.cj)?\.jdbc\.Driver' --include=*.yml --include=*.yaml --include=*.properties --include=*.java . | sort | uniq -c
grep -rlE 'com\.mysql\.jdbc\.Driver' --include=*.yml --include=*.yaml --include=*.properties --include=*.java . | grep -v /target/
grep -rhoE 'jdbc:mysql[^"'"'"' ]*' auth/conf network/server/conf --include=*.yaml | sed -E 's#//[^/]+/#//<host>/#' | sort | uniq -c
```
`-o` prints only the match, `-h` drops filenames, and `sort | uniq -c` counts distinct values. This gives the JDBC driver class names in use and the URL schemes (`jdbc:mysql:aws://`, `:aurora://`, plain). `sed` masks hostnames.

```bash
unzip -l ~/.m2/repository/com/mysql/mysql-connector-j/8.4.0/mysql-connector-j-8.4.0.jar | grep -E 'com/mysql/jdbc/Driver.class|com/mysql/cj/jdbc/Driver.class'
unzip -l ~/.m2/repository/software/aws/rds/aws-mysql-jdbc/<ver>/aws-mysql-jdbc-<ver>.jar | grep -cE ' com/mysql/cj/'
unzip -l ~/.m2/repository/software/aws/rds/aws-mysql-jdbc/<ver>/aws-mysql-jdbc-<ver>.jar | grep -E 'Driver.class'
unzip -l mercury-services/auth/target/auth-1.0.jar | grep -c 'org/springframework/security/crypto/bcrypt/BCryptPasswordEncoder'
```
`unzip -l` lists jar entries without extracting. This proved (a) 8.4.0 still ships the legacy `com.mysql.jdbc.Driver`, (b) the AWS driver has **0** unshaded `com/mysql/cj/` classes, so there is no overlap with Connector/J, and (c) the auth fat jar contains `BCryptPasswordEncoder`.
