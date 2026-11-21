# Closed items

← [Tracker home](README.md) · Open items: [actions](actions.md), [findings](findings.md), [decisions](decisions.md)

Done, dropped or superseded items, kept for reference with their full text. Links from anywhere in the tracker land here.

<a id="closed-actions"></a>
## Closed actions

<a id="a5"></a>
### A5 · distributor-rest shared bearer token: raise with QA

**Owner:** Arijit · **Needed by:** Before the distributor-rest PR (step 3) · **Source:** Review summary §9 tracker 7

**Action.** distributor-rest `AuthClient` shares one bearer token across subscribers: raise the security defect with QA and share the reference

**Status.** ✅ Closed 2026-11-20: **dropped** (Arijit: no need to tell QA). Recorded instead as an existing defect with a disabled test in the distributor-rest PR

<a id="a2"></a>
### A2 · Interim approach for U3 (size by HEAD)

**Owner:** Arijit · **Needed by:** Step 1d · **Source:** Development plan

**Action.** ~~Decide the interim approach for U3 during development: a temporary `getFileSize` fallback (downloads the object) behind one method plus a disabled HEAD test, or wait for U3~~

**Status.** **Done 2026-11-17:** no interim needed. U3 is in 1.0.39-SNAPSHOT, so the 1d workspace adapter uses `StorageClient.getObjectSize` (one HEAD) from the start (spec decision 7: 1d waits for the commons release)

<a id="a4"></a>
### A4 · Commons snapshot version in use

**Owner:** Arijit · **Needed by:** Before the final PR · **Source:** Review summary §7

**Action.** ~~Commons was consumed as **1.0.38-SNAPSHOT** (1a–1c). Next: **1.0.39-SNAPSHOT** (first 1d commit bumps `mercury.commons.version`, spec §6 item 1). Pin a released commons version before the AppianWay release~~

**Status.** **Dropped 2026-11-19:** 1.0.39-SNAPSHOT is in use since 1d; pinning a released version is an understood release step, not tracked here

<a id="a13"></a>
### A13 · Delete old local branches

**Owner:** Arijit · **Needed by:** Any time · **Source:** Development

**Action.** ~~Old empty local branch `WI01124532-wave0-foundation` and the merged local sub-branches~~

**Status.** **Done 2026-11-17:** deleted `-pom`, `-shared-config`, `-shared-runtime`, `WI01124532-wave0-foundation` (`git branch -d`, all merged). Kept `backup/WI01124532-aws-sdk-upgrade-pre-commons-u-items-2026-11-12` until 1d was merged; deleted 2026-11-18 together with the merged local `-shared-adapters` / `-functional-testing` branches

<a id="a14"></a>
### A14 · Transformer's JUnit 5 tests run for the first time

**Owner:** Arijit · **Needed by:** Step 1a · **Source:** Finding [F2](#f2)

**Action.** ~~**Transformer's 43 JUnit 5 test classes do not run on `develop`** (finding [F2](#f2)). After the JUnit Platform switch they run for the first time; decide how to handle any that fail~~

**Status.** Done: all 665 pass after the switch

<a id="a17"></a>
### A17 · Guava version alignment

**Owner:** Arijit · **Needed by:** Step 1b · **Source:** Step 1a

**Action.** ~~Guava: root pins 33.1.0-jre, commons manages 33.5.0-jre. Raise it (red/green) when `shared` starts depending on commons~~

**Status.** Done: 33.6.0-jre in `1294b884` ([D12](decisions.md#d12))

<a id="a19"></a>
### A19 · PRs could not be created on Bitbucket

**Owner:** Arijit · **Needed by:** Every PR · **Source:** Step 1a

**Action.** ~~PRs could not be created from here on Bitbucket (REST API 401)~~

**Status.** **Resolved by the GitHub move (2026-11-17):** `gh` is logged in with write access, so sub-PRs can be raised with `gh pr create --base feature/WI01124532-aws-sdk-upgrade` (on request). Descriptions still prepared in `docs/redesign/pr-details/`

<a id="a20"></a>
### A20 · Stress environment configuration

**Owner:** Arijit · **Needed by:** Any time · **Source:** Finding [F6](#f6)

**Action.** ~~Stress environment: dispatcher, splitter and transformer configuration cannot resolve ([F6](#f6)). Confirm whether stress is still deployed; if so, add `networkservices.messageRegisterServicePath` to `configuration/stress/network-services.properties` (separate change)~~

**Status.** Dropped 2026-10-31: user confirmed stress is not used ([D23](decisions.md#d23))

<a id="a22"></a>
### A22 · Commons asks: no API-call timeout, SSM retry, access-key log

**Owner:** Arijit / commons · **Needed by:** With [A3](actions.md#a3) · **Source:** Step 1c research

**Action.** ~~Upstream ask (add to U-list): cloud-sdk factories cannot express "no API-call timeout" and `ParameterStoreClientFactory` ignores the configured `RetryStrategy`; `S3StorageClient(S3Client)` logs the access key id at INFO~~

**Status.** **Done in 1.0.39-SNAPSHOT:** U11 `noClientExecutionTimeout()`, U12 SSM retry strategy, U13 no access-key log. The `com.inttra.mercury.cloudsdk` WARN-logger workaround is no longer needed

<a id="a23"></a>
### A23 · INT: large reads within the 10-minute cap

**Owner:** Arijit / INT · **Needed by:** Before release · **Source:** [DR-2](decisions.md#dr-2)

**Action.** ~~INT: confirm the largest workspace documents are read well within the 10-minute S3 API-call cap ([DR-2](decisions.md#dr-2))~~

**Status.** **Done 2026-11-17 (no longer needed):** `80c2ec9c` sets `noClientExecutionTimeout()` for storage and the message-queue listener (U11), exact v1 parity. There is no 10-minute cap left to check

<a id="a24"></a>
### A24 · Bitbucket build merge check

**Owner:** Arijit · **Needed by:** Every sub-PR · **Source:** 2026-11-02

**Action.** ~~Bitbucket "minimum 1 successful build" merge check for sub-PRs into the feature branch~~

**Status.** **No longer needed on GitHub (2026-11-17).** Ruleset `PR_CHECK` (PR + 1 approval + required status `PR_BUILD`, branch up to date, no force-push) applies to **`develop` only**. Sub-PRs into `feature/WI01124532-aws-sdk-upgrade` have no required check. `PR_BUILD` is posted by `inttra-jenkins-ci[bot]` (Jenkins job `DEV_GIT_PR`); it matters for the final PR into `develop`

<a id="a25"></a>
### A25 · Merge develop into the feature branch

**Owner:** Arijit · **Needed by:** Remind Arijit after [A24](#a24) is sorted out · **Source:** 2026-11-02

**Action.** ~~`develop` moved on: PR #77 (`daaaea04`, Sonar maven injection revert) restores the root `sonar` profile. Test merge into `WI01124532-aws-sdk-upgrade-pom` conflicts in `pom.xml` (adjacent edits next to `</modules>`). Merge `origin/develop` into the feature branch, then into `-pom`, resolve, full build ([G4](rules.md#g4)), push, so the CI build includes the `sonar` profile that `build_pr.sh` uses~~

**Status.** **Done 2026-11-09:** merged `origin/develop` `4cc7b99f` (also PR #79, WI01149469 transformer pins Jetty 12.1.14 / Jackson 2.21.8 / httpclient5 5.6.4, equal to the root pins) into the feature branch as `34c8fe4e`; `pom.xml` kept both blocks; full build green, counts unchanged; pushed. `-pom` no longer needs it (merged). Commands: [develop-merge command log](howto/2026-11-09-develop-merge.md)

<a id="closed-findings"></a>
<a id="a28"></a>
### A28 · ingestor and watermill-publisher: add the shutdown drain

**Owner:** Arijit · **Needed by:** ingestor and watermill-publisher migrations · **Source:** PR #4 review

**Action.** ingestor and watermill-publisher have their own listener manager (not the shared one): when they move to `CloudServicesModule`, add the same drain before the clients close (the close order comes with the module)

**Status.** **Done 2026-11-21:** ingestor (PR #10: the shared dispatcher counts its batches, 20 s drain; runtime test 7) and watermill-publisher (PR #13, merged `9537d1c1`: each listener's dispatcher refuses new batches first, then waits for its batch **and the stream's pending acks** (a message is deleted on its ack), and the dead-letter redrive in progress, within one 20 s deadline; runtime test 10 busy stop: acks 5 s late are waited for and the messages deleted before the clients close, where v1 loses them).

## Closed findings

<a id="f2"></a>
### F2 · Transformer's JUnit 5 tests not run on develop (2026-10-31)

**Finding.** Transformer's 43 JUnit 5 test classes are not run on `develop`: the root pom adds the `surefire-junit4` provider to the Surefire plugin, child poms inherit plugin dependencies, so transformer runs on the JUnit 4 provider and only its 3 JUnit 4 functional classes execute (4 tests, all skipped)

**Effect.** The JUnit Platform switch in 1a makes them run for the first time ([A14](#a14))

<a id="f5"></a>
### F5 · watermill-publisher logback pair mismatch (2026-10-31)

**Finding.** watermill-publisher hardcodes `logback-classic` 1.5.33 (ION-16098 comment) while `logback-core` follows the root pin, so after the alignment it resolved a mismatched pair (classic 1.5.33 / core 1.5.38)

**Effect.** Fixed in step 1a (commits 5–6) and guarded by the enforcer rule ([D5](decisions.md#d5))

<a id="f6"></a>
### F6 · Stress configuration cannot resolve (2026-10-31)

**Finding.** `configuration/stress/network-services.properties` has no `networkservices.messageRegisterServicePath`, which the dispatcher, splitter and transformer YAMLs reference, so their stress configuration fails to resolve today (previous resolver too)

**Effect.** Existing; behaviour kept (golden test records "both fail"). Add the key if stress is still used ([A20](#a20))

<a id="f8"></a>
### F8 · New config chain ignores unused unresolvable placeholders (2026-11-02)

**Finding.** The previous resolver substituted and validated the whole joined `.properties` text (comment lines included), so an unresolvable `${...}` in a property the YAML never uses failed startup. The commons `PropertiesSubstitutionConfigProvider` resolves property values only when the YAML references them, so such a placeholder is now ignored. No current configuration is affected (golden test: no "previous fails, current succeeds" case)

**Effect.** Documented as a deliberate relaxation in the PR #78 description and walkthrough (`pr-details/…-pr-1b-shared-config-description.md` [actions](actions.md).1.2); no code change. **Accepted by Arijit 2026-11-09**

<a id="f13"></a>
### F13 · error-processor's functional test had not run since 2021 (2026-11-18)

**Finding.** error-processor's functional happy-flow test had not run since `047766ae` (2021-03-23, "reduce events"), which removed its `@Test`. Re-enabled on v1, its event fixture was stale (no `subType`, token `pickUpQueue`). Its expected pickup body was a literal CRLF copy, which only matched on Windows checkouts

**Effect.** Re-enabled in `0f5f3037` with the fixture matching today's v1 event, and the pickup body taken from the fixture file. Archive, delete and email-queue assertions passed unchanged

<a id="closed-decisions"></a>
## Superseded decisions

<a id="d13"></a>
### D13 · API-call timeout caps through the factories (2026-10-31)

**Decision.** ~~No "API-call timeout = none" is possible through the cloud-sdk factories (S3 default 30 s, SQS 30 s, SNS / SSM 10 s; zero rejected). The client profile sets a generous cap through the factories: **S3 10 min, SQS listener 60 s**; SQS sender and SNS keep 10 s as today~~ **Superseded 2026-11-17 by U11** (`80c2ec9c`): storage and the listener have no API-call timeout, as in v1; sender and notification keep 10 s

**Reason.** User decision. Keeps the AWS SDK boundary (factories only); a 30 s cap would fail large S3 reads that work today; stalls stay bounded by the socket timeout as in v1

**Closed:** superseded by U11 (no API-call timeout) and [D32](decisions.md#d32)

<a id="d22"></a>
### D22 · Listener asks for exactly the idle-worker count (2026-10-31)

**Decision.** ~~The v2 listener asks for exactly the idle-worker count, like v1, with no cap at 10~~ **Superseded by [D24](decisions.md#d24) (2026-11-09).**

**Reason.** Every service sizes its `AsyncDispatcher` with `sqsPickupConfig.maxNumberOfMessages` (≤ 10), so the count never exceeds the SQS limit; a cap would only change behaviour for an already-invalid configuration

**Closed:** superseded by [D24](decisions.md#d24)
