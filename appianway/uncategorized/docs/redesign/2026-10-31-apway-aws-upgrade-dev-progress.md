# AWS Upgrade AppianWay — Development Progress (WI01124532)

> **Main work document** for the WI01124532 development. Started 2026-10-31. Local only (`docs/` is gitignored; never committed).
> Design pages: `docs/redesign/2026-10-30-apway-WI01124532-*.md` (program, shared, 15 modules). Design rationale: `docs/redesign/2026-10-30-apway-WI01124532-review-summary.md`. Branch plan: `docs/2026-10-30-apway-design-update-plan.md` §9.5.
> Pending follow-ups from the review summary have been moved into §2 and are tracked here from now on.

**Contents:** R Resume here · 1 Tracker · 2 Pending actions · 3 Working rules · 4 Local guards and tooling · 5 Development plan · 6 Step log · 7 Decisions · 7a Decision records · 8 Findings · 9 Key commands

---

## R. Resume here (stopped Monday 2026-11-02, Arijit off Tue–Wed, resume Thursday 2026-11-05)

### R.0 Thursday 2026-11-05 — start here

What happened on Monday 2026-11-02: PR #76 (1a) merged; stack rebased cleanly (trees identical, no rebuild needed); 1b pushed and raised as **PR #78**; cycle D done on 1c (`5a2d0e21` red / `a8de6ee7` green, full build green); PR descriptions moved to `docs/redesign/pr-details/`; the PR #78 description rewritten as a full walkthrough (Part 1 = Bitbucket text, Part 2 = commit-by-commit walkthrough with diagrams, old-loader detail, parity table, test layers; Appendix A = Java/JUnit syntax refresher); finding **F8** (new config chain is less strict for unused unresolvable placeholders) recorded and added to the PR text.

Thursday, in order:

1. **Arijit reviews** `docs/redesign/pr-details/2026-10-31-apway-pr-1b-shared-config-description.md`. Decide on **F8**: accept the relaxation (current text) or restore strictness with a small red/green cycle on 1b (`PropertiesSources` checks every property value on load). If Part 1 changed, paste it into PR #78 on Bitbucket.
2. **Check PR #78**: `git fetch origin` then `git log --oneline --first-parent origin/WI01124532-aws-sdk-upgrade -3`. Build check: Arijit ran the **set build status** job for #78's head commit `bbe0be17` on 2026-11-02 (A24). If anything is pushed to #78 later, give Arijit the new head commit id so it can be run again. Arijit runs the job after approval on every PR; just provide the latest head commit id. Review comments → fix on `-shared-config` (red/green), push, then re-base 1c (`git rebase --onto WI01124532-aws-sdk-upgrade-shared-config <old 1b tip bbe0be17> WI01124532-aws-sdk-upgrade-shared-runtime`).
3. **Remind Arijit of A25** (merge `develop` / PR #77 `sonar` profile into the feature branch; `pom.xml` conflict). A24 is now cleared. Arijit asked to handle it "one thing at a time".
4. **Write the 1c PR description** `docs/redesign/pr-details/2026-10-31-apway-pr-1c-shared-runtime-description.md` in the same style as 1b (Part 1 Bitbucket text + Part 2 per-commit walkthrough with diagrams and test flow; 11 commits `c4015b09` … `a8de6ee7`). Push 1c after #78 merges, or earlier as a stacked PR (Arijit's choice).
5. Then **1d** (`-shared-adapters`; needs A2 answered) and **1e**.

Build worktree `../appianway-build` is detached at `5a2d0e21` with the cycle-D green patch still applied (uncommitted): run `git -C ../appianway-build reset -q --hard && git -C ../appianway-build clean -qfd` before reusing it.

### R.1 Where things stand

| Branch | Based on | Remote | Tip | State |
|---|---|---|---|---|
| `WI01124532-aws-sdk-upgrade` (feature) | `develop` `0448d362` | pushed | `a9a7afbb` (PR #76 merge) | Target of every sub-PR |
| `WI01124532-aws-sdk-upgrade-pom` (1a) | feature | pushed | `6bb9ae6c` | ✅ **PR #76 merged** 2026-11-02 (`a9a7afbb`) |
| `WI01124532-aws-sdk-upgrade-shared-config` (1b) | feature (rebased 2026-11-02) | **pushed** 2026-11-02 | `bbe0be17` | Complete. 7 commits; tree identical to the built `0224e384`. **PR #78 raised**, awaiting build + review. PR description / walkthrough: `docs/redesign/pr-details/2026-10-31-apway-pr-1b-shared-config-description.md` |
| `WI01124532-aws-sdk-upgrade-shared-runtime` (1c) | 1b branch (stacked, rebased 2026-11-02) | **local only** | `a8de6ee7` (11 commits on top of 1b; tree identical to the built `d2ce0f82`) | Cycles A, B1, B2, C, D done (full builds green); next: 1c PR description |
| `WI01124532-wave0-foundation` | — | local | `0448d362` | Obsolete, empty (A13) |

Working tree: clean except untracked docs / IDE files (never staged). Build worktree `C:\Users\arijit.kundu\projects\appianway-build` exists (detached; safe to reuse or `git worktree remove`).

### R.2 Monday 2026-11-02 — steps (history; Thursday's list is R.0)

1. ~~**Check PR #76.**~~ Merged 2026-11-02 (`a9a7afbb`, tip `6bb9ae6c` unchanged). `git fetch origin` then `git log --oneline --first-parent origin/WI01124532-aws-sdk-upgrade -3` — a "Pull request #76 …" merge commit means it is merged. If reviewers asked for changes: fix on `WI01124532-aws-sdk-upgrade-pom` (red/green rules apply), push, then redo step 2 with the new tip.
2. ~~**Re-base the stack after #76 merges**~~ Done 2026-11-02, clean (1b `bbe0be17`, 1c `a8de6ee7`). (keeps 1b/1c commits, drops the already-merged 1a ones):
   ```bash
   git fetch origin
   git checkout WI01124532-aws-sdk-upgrade && git merge --ff-only origin/WI01124532-aws-sdk-upgrade
   git rebase --onto WI01124532-aws-sdk-upgrade WI01124532-aws-sdk-upgrade-pom WI01124532-aws-sdk-upgrade-shared-config
   git rebase --onto WI01124532-aws-sdk-upgrade-shared-config 0224e384 WI01124532-aws-sdk-upgrade-shared-runtime
   ```
   `--onto <new base> <old base> <branch>` replays the commits that are in `<branch>` but not in `<old base>` onto `<new base>`. The second command uses the **old** 1b tip `0224e384` as the old base, because the first rebase gives 1b new commit ids. Check with `git log --oneline WI01124532-aws-sdk-upgrade..WI01124532-aws-sdk-upgrade-shared-runtime` (expect 7 + 9 = 16 commits, all starting `WI01124532`).
3. ~~**Full reactor build of 1b**~~ Skipped 2026-11-02: the rebased trees are identical to the already-built `0224e384` / `d2ce0f82` (`git rev-parse <commit>^{tree}`). in the build worktree (§9.5; flag G2), compare test counts with §6 step 1b (`shared` 1628).
4. ~~**Push 1b and give the user the PR link**~~ Done: pushed 2026-11-02, raised as PR #78; `git push -u origin WI01124532-aws-sdk-upgrade-shared-config`; link `https://git.dev.e2open.com/projects/INT/repos/appianway/pull-requests?create&sourceBranch=refs%2Fheads%2FWI01124532-aws-sdk-upgrade-shared-config&targetBranch=refs%2Fheads%2FWI01124532-aws-sdk-upgrade`; title `WI01124532 shared: resolve configuration with the mercury-services-commons chain`; paste the description file in chat too (A19: PRs cannot be created through the REST API).
5. ~~Continue 1c with cycle D~~ (done 2026-11-02, `5a2d0e21` / `d2ce0f82`), then 1c's PR description (`docs/redesign/pr-details/2026-10-31-apway-pr-1c-shared-runtime-description.md`), push after 1b is merged (or as a stacked PR, user's choice).
6. Then **1d** (`-shared-adapters`) and **1e** (`-functional-testing`), per §5.

### R.3 Cycle D (done 2026-11-02) — cloud-sdk exception → `RecoverableException` (contract C9)

Where v1 wraps today (each `catch (SdkClientException ex) { throw new RecoverableException(ex); }`): `messaging/SQSClient` (3 `sendMessage` variants; `deleteMessage` and `getVisibilityTimeout` are **not** wrapped), `messaging/SNSClient` (publish), `workspace/S3WorkspaceService` (5+ methods — read them in 1d). `SdkClientException` is the v1 base of every client/service failure, so "wrap everything the SDK throws" is the rule.

cloud-sdk failure types to map (from the research in step 1c, file refs under `mercury-services-commons/cloud-sdk-api|aws/src/main/java/com/inttra/mercury/cloudsdk/`):
- `exception/CloudSdkException` (`RuntimeException`, has `isRetryable()`, `getOperation()`, `getResource()`) and subclasses `messaging/exception/MessagingException` (every `SqsMessagingClient` call wraps failures in it), `notification/exception/NotificationException` (SNS).
- Not `CloudSdkException`: `paramstore/exception/ParameterStoreException`, `storage/exception/StorageClientInitializationException`, aws-side `storage/exception/S3OperationException`, `S3UploadException`, `FileTransferException`; one S3 write path throws a bare `RuntimeException` (`S3StorageClient.java:789-796`).
- `SendMessageOptions.delaySeconds` > 900 throws `IllegalArgumentException` client-side (v1: server-side → `RecoverableException`) — map it in the 1d SQS sender adapter.

Planned unit: `com.inttra.mercury.shared.externalwrapper.exception.CloudSdkFailures` (name to confirm) — `isCloudSdkFailure(Throwable)` and `toRecoverable(RuntimeException)`; `isRetryable()` is logged, not used to narrow (design C9). Test class `CloudSdkExceptionMappingTest` (design test 7). Red → green → (refactor) as usual.

### R.4 Facts from the step-1c research (cloud-sdk 1.0.38) to keep

- Factories always set an API-call timeout (S3 30 s via `BaseAwsConfig`, SQS 30 s, SNS 10 s, SSM 10 s); zero rejected → DR-2 caps. `ParameterStoreClientFactory` ignores the configured `RetryStrategy`.
- `AwsHttpClientWrapper.ofSyncBuilder(ApacheHttpClient.builder())` = one pool per SDK client, owned and closed by it; cloud-sdk default transport is connect 5 s / socket 30 s / 50 connections.
- `AwsMessagingClientConfig.build()` requires `queueUrl`, `maxConnections > 0`, `maxMessages` 1–10 (validated before defaults); `maxConnections` / `visibilityTimeout` / `threadPoolSize` are not used by the factory.
- `SqsMessagingClient.receiveMessages`: sends queue URL, max messages, wait time, message attribute names (if any); **never** a visibility timeout. Messages: `getMessageAttributes()` = String values only; `getAttributes()` = system attributes. Send: `DelaySeconds` only if > 0; attributes as DataType `String`. `getQueueAttributes` asks for `All`.
- `SqsMessagingClient` / `SnsService` / `S3StorageClient` / `SsmCloudParameterStore` have public constructors; `ManagedCloudResource.of(resource, name)` (cloud-sdk-api) is the Dropwizard lifecycle adapter; only `SqsMessagingClient.close()` closes its SDK client.
- `S3StorageClient(S3Client)` logs the access key id at INFO (set `com.inttra.mercury.cloudsdk` to WARN; A22).
- mercury-services reference for retry/config builders: `mercury-services/booking-downstream-processor/booking-cargoscreen/src/main/java/.../config/BookingCargoScreenApplicationInjector.java:139-246`.

### R.5 Open questions waiting for the user

A2 (U3 interim approach, needed by 1d), A5 (distributor-rest QA security defect reference), F8 (accept the 1b strictness relaxation or restore it). (A20 answered: stress is not used.) Everything else in §2 is a later-stage or INT item.

### R.6 Where everything is

| What | Path |
|---|---|
| This document | `docs/redesign/2026-10-31-apway-aws-upgrade-dev-progress.md` |
| PR descriptions | `docs/redesign/pr-details/2026-10-31-apway-pr-1a-pom-description.md`, `…-pr-1b-shared-config-description.md` (PR #78; full walkthrough, the template for 1c onwards) |
| Design pages | `docs/redesign/2026-10-30-apway-WI01124532-<page>.md` (`shared` = foundation; module pages for steps 2–4) |
| Design rationale / defects list | `docs/redesign/2026-10-30-apway-WI01124532-review-summary.md` (§4 defects → A12; §9 page-change tracker → A21) |
| Branch plan | `docs/2026-10-30-apway-design-update-plan.md` §9.5 |
| commons sources (1.0.38-SNAPSHOT) | `C:\Users\arijit.kundu\projects\mercury-services-commons` (branch `feature/ION-12310-commons-cloudsdk-refactoring`) |
| New `shared` classes so far | `config/ConfigTransformChain`, `config/PropertiesSources`, `config/ClientSettings`, `config/ClientProfile`, `task/V1MessageBridge`, `listener/CloudSdkSQSListener`, `externalwrapper/exception/CloudSdkFailures`; overloads in `task/Task`, `TaskFactory`, `AbstractTask`, `ErrorHandler`, `errorhandler/ErrorHelper`, `threaddispatcher/Dispatcher`, `AsyncDispatcher`; command rewired `command/ConfigProcessingServerCommand` |
| Local guards | G1 hook `.git/hooks/commit-msg`; G2 build flag; G4 build worktree (§4) |
| Session scratchpad (build logs, count snapshots) | Temporary; not needed to resume — the counts are in §6 |

---

## 1. Tracker

_Last updated: 2026-11-02 (end of day; Arijit off Tue–Wed; resume Thursday 2026-11-05 from §R.0)._

| Step | Sub-branch (PR into `WI01124532-aws-sdk-upgrade`) | Scope | Status | Commits | PR |
|---|---|---|---|---|---|
| — | `WI01124532-aws-sdk-upgrade` | Feature (integration) branch, from `develop` `0448d362` | ✅ Pushed 2026-10-31 | — | — |
| 1a | `WI01124532-aws-sdk-upgrade-pom` | JUnit Platform; commons 1.0.38 coordinates; root pins aligned with commons | ✅ PR #76 merged 2026-11-02 (`a9a7afbb`) | `701cc85c`, `42593970`, `3f27f8e7`, `9b0a1235`, `fb837d9d`, `6bb9ae6c` | [#76](https://git.dev.e2open.com/projects/INT/repos/appianway/pull-requests/76) |
| 1b | `WI01124532-aws-sdk-upgrade-shared-config` | Commons config chain, no-downgrade guard (Guava, AWS SDK v1), command rewired, golden test; stacked on 1a until #76 merges (D6) | 🔄 Rebased onto the feature branch and pushed 2026-11-02; PR #78 raised, awaiting build + review; F8 decision pending | `7a5393ef` … `bbe0be17` (7; before the rebase `8bf1db21` … `0224e384`) | [#78](https://git.dev.e2open.com/projects/INT/repos/appianway/pull-requests/78) |
| 1c | `WI01124532-aws-sdk-upgrade-shared-runtime` | Client profile, QueueMessage overloads, back-pressure listener, exception mapping; stacked on 1b | 🔄 Cycles A, B1, B2, C, D done (full builds green); PR description next | `c4015b09` … `a8de6ee7` (before the rebase `97987059` … `d2ce0f82`) | — |
| 1d | `WI01124532-aws-sdk-upgrade-shared-adapters` | Workspace S3, SQS sender, SNS publisher, health checks, v2 Guice module | ⏳ Not started | | |
| 1e | `WI01124532-aws-sdk-upgrade-functional-testing` | cloud-sdk fakes, JUnit 5 functional base, ArchUnit boundary test | ⏳ Not started | | |
| 2 | `-event-writer`, `-error-processor`, `-email-sender` | Module migrations (email-sender blocked by A1) | ⏳ Not started | | |
| 3 | `-dispatcher`, `-splitter`, `-transformer`, `-distributor`, `-distributor-rest`, `-ingestor` | Module migrations | ⏳ Not started | | |
| 4 | `-watermill-publisher`, `-watermill`, `-booking-inbound-consumer`, `-visibility-inbound-consumer`, `-cargoscreen-consumer`, `-itv-gps-consumer` | Module migrations | ⏳ Not started | | |
| 5 | `WI01124532-aws-sdk-upgrade-shared-v1-removal` | Delete v1 code and v1 fakes from `shared` | ⏳ Not started | | |
| — | Final PR `WI01124532-aws-sdk-upgrade` → `develop` | Integration review, merged once | ⏳ Not started | | |

Legend: ✅ done · 🔄 in progress · ⏳ not started · ⛔ blocked. Module sub-branches are `WI01124532-aws-sdk-upgrade-<module>`.

---

## 2. Pending actions and follow-ups

Items carried over from the review summary (its §4–§9) and items raised during development. Status: **Open** (action pending), **Done**, **Dropped**.

| # | Action | Owner | Needed by | Source | Status |
|---|---|---|---|---|---|
| A1 | Commons release with **U3** (S3 size HEAD), **U8** (SES message id), **U9** (SES retry strategy). Release prerequisite; U8–U9 block email-sender | Arijit / commons | Before the AppianWay release; email-sender PR (step 2) | Review summary §1, §9 tracker 1 | Open |
| A2 | Decide the interim approach for U3 during development: a temporary `getFileSize` fallback (downloads the object) behind one method plus a disabled HEAD test, or wait for U3 | Arijit | Step 1d | Development plan | Open |
| A3 | Raise the commons upstream asks U1, U2, U4, U5, U6, U10 (U7 optional); fallbacks are used meanwhile | Arijit | Before step 5, so fallbacks can be retired later | Review summary §5 decision 2 | Open |
| A4 | Commons is consumed as **1.0.38-SNAPSHOT** (local checkout on `feature/ION-12310-commons-cloudsdk-refactoring`, published 2026-10-29). Pin a released commons version before the AppianWay release | Arijit | Before the final PR | Review summary §7 | Open |
| A5 | distributor-rest `AuthClient` shares one bearer token across subscribers: raise the security defect with QA and share the reference | Arijit | Before the distributor-rest PR (step 3) | Review summary §9 tracker 7 | Open |
| A6 | INT: confirm queue visibility timeouts against the distributor-rest worst-case POST (≈ 3 × 120 s), distributor-rest OI 4 | Arijit / INT | distributor-rest PR | Review summary §4, §9 tracker 4 | Open |
| A7 | INT: distributor null-metadata behaviour, distributor OI 3 | Arijit / INT | distributor PR | Review summary §9 tracker 4 | Open |
| A8 | INT/IAM: `sqs:GetQueueAttributes` on every task role (U5 health-probe fallback); SESv2 IAM actions (email-sender); redrive policies | Arijit / infra | Before INT deployment | Review summary §7, `shared` OI 11 | Open |
| A9 | Transformer SDK 2.x CloudWatch metric names differ from v1: review dashboards and alarms | Arijit | Before INT deployment of transformer | Review summary §5 decision 8 | Open |
| A10 | ingestor: Jest SigV4 signer 0.0.22 check on INT | Arijit / INT | ingestor PR | Review summary §6 | Open |
| A11 | Hystrix 1.5.18 + guava-retrying replacement: separate follow-up design under WI01124532 | Arijit | After this release | Review summary §1, decision 3 | Open |
| A12 | Existing defects (review summary §4): each module PR adds one disabled test (`@Disabled` + defect reference) per defect | Each module PR | Steps 2–4 | Review summary §5 decision 4 | Open |
| A13 | Old empty local branch `WI01124532-wave0-foundation`: delete when convenient | Arijit | Any time | Development | Open |
| A14 | **Transformer's 43 JUnit 5 test classes do not run on `develop`** (finding F2). After the JUnit Platform switch they run for the first time; decide how to handle any that fail | Arijit | Step 1a | Finding F2 | Done: all 665 pass after the switch |
| A15 | The local full build needs the resolver flag G2 for `registration-inbound-consumers` (finding F1); check whether CI is affected | Arijit | Step 1a PR | Finding F1 | Open |
| A16 | cargoscreen-consumer runs 0 of its tests (F3): add the Vintage engine and verify the count | cargoscreen PR | Step 4 | Finding F3 | Open |
| A17 | Guava: root pins 33.1.0-jre, commons manages 33.5.0-jre. Raise it (red/green) when `shared` starts depending on commons | Arijit | Step 1b | Step 1a | Done: 33.6.0-jre in `1294b884` (D12) |
| A19 | PRs cannot be created from here: the Bitbucket REST API returns 401 for the git credential (Basic and Bearer). Arijit creates each PR from the pre-filled link; description text is prepared in `docs/redesign/pr-details/2026-10-31-apway-pr-<step>-description.md` (gitignored). Optional: a Bitbucket HTTP access token with PR write scope would let PRs be created automatically | Arijit | Every PR | Step 1a | Open |
| A20 | Stress environment: dispatcher, splitter and transformer configuration cannot resolve (F6). Confirm whether stress is still deployed; if so, add `networkservices.messageRegisterServicePath` to `configuration/stress/network-services.properties` (separate change) | Arijit | Any time | Finding F6 | Dropped 2026-10-31: user confirmed stress is not used (D23) |
| A21 | Design-page corrections (review-summary §9 tracker, one batched minor edit of `shared` 716084130): Client Profile table — SNS retries 2 → 3, SQS listener socket 30 s → 50 s (D14); API-call timeout "none" → S3 10 min / listener 60 s cap (D13); retry condition "cloud-sdk `AwsRetryCondition`" → "SDK standard strategy retrying every exception" (D16); transition overloads (D15) | Arijit | Before design approval | Step 1c | Open |
| A22 | Upstream ask (add to U-list): cloud-sdk factories cannot express "no API-call timeout" and `ParameterStoreClientFactory` ignores the configured `RetryStrategy`; `S3StorageClient(S3Client)` logs the access key id at INFO | Arijit / commons | With A3 | Step 1c research | Open |
| A23 | INT: confirm the largest workspace documents are read well within the 10-minute S3 API-call cap (DR-2) | Arijit / INT | Before release | DR-2 | Open |
| A24 | Jenkins PR job only builds PRs targeting `develop`, so sub-PRs into the feature branch never get the build that Bitbucket's "minimum 1 successful build" merge check needs (#76 approved but blocked). Asked the Jenkins owner on 2026-11-02 to widen the target filter to `WI01124532-*` or any branch; interim: ask for a manual run on `6bb9ae6c`. PR builds run each module's `build_pr.sh` (`verify sonar:sonar -P sonar`, quality gate wait). **Resolved 2026-11-02:** a Jenkins **"set build status" job** takes a commit id and posts a passing build for it, which satisfies Bitbucket's merge check. For each sub-PR: run it with the PR's head commit (re-run after every push, since the check is on the head commit). Run the full local build (G4) first, because this job does not build anything | Arijit | Every sub-PR (#78 now: head `bbe0be17`) | 2026-11-02 | Done (workaround) |
| A25 | `develop` moved on: PR #77 (`daaaea04`, Sonar maven injection revert) restores the root `sonar` profile. Test merge into `WI01124532-aws-sdk-upgrade-pom` conflicts in `pom.xml` (adjacent edits next to `</modules>`). Merge `origin/develop` into the feature branch, then into `-pom`, resolve, full build (G4), push, so the CI build includes the `sonar` profile that `build_pr.sh` uses | Arijit | Remind Arijit after A24 is sorted out | 2026-11-02 | Open |
| A18 | Mockito: root 2.27.0 vs commons / Dropwizard 5.x. Decide the version when new JUnit 5 tests need `mockito-junit-jupiter` | Arijit | Step 1c | Step 1a | Open |

---

## 3. Working rules

| Rule | Detail |
|---|---|
| Branches | Feature (integration) branch `WI01124532-aws-sdk-upgrade`. One sub-branch `WI01124532-aws-sdk-upgrade-<step or module>` per step or module, cut from the feature branch, one PR each into it (merge commit, no squash). Final single PR feature → `develop` |
| Work item id | **Every commit message starts with `WI01124532`** (the Bitbucket hook rejects commits without it), including local merge commits. **Every PR title starts with `WI01124532`**, because the Bitbucket merge commit is `Pull request #N: <title>`. Enforced locally by the `commit-msg` hook (G1) |
| TDD | Red → green → refactor: one commit for the failing test (`WI01124532 red: …`), one for the change that makes it pass (`WI01124532 green: …`), one for the cleanup (`WI01124532 refactor: …`, when there is something to refactor). Build-infrastructure changes that cannot fail a test first are committed on their own (`WI01124532 build: …`) and proven by the test-count check |
| Tests | New test classes: JUnit 5 (Jupiter) + AssertJ, one class per unit under test. Existing JUnit 4 tests unchanged (Vintage engine) |
| Backward compatibility | Wire, storage and configuration formats identical (contract C1–C9, `shared` design) |
| Performance | No extra round trips, downloads or client instances compared with today; listener back-pressure kept |
| Upstream commons asks | Fallbacks first (U1, U2, U4, U5, U6, U7, U10); U3, U8, U9: see A1–A2 |
| Staging | Stage by explicit path only; never `docs/`, `.claude/`, `.vscode/`, `*.code-workspace`, module `docs/` |
| Build gate | Full reactor `mvn clean verify` green before every PR; test counts = baseline + new tests |

---

## 4. Local guards and tooling

Local setup that protects the workflow. None of it is committed; re-create it on a new clone.

| # | What | Where | Why | How to check |
|---|---|---|---|---|
| G1 | `commit-msg` hook rejecting messages whose first line does not start with `WI01124532` | `.git/hooks/commit-msg` (executable) | Bitbucket's server hook rejects pushes containing commits without the work item id; catching it locally avoids rewriting pushed history | `git commit --allow-empty -m "test"` must fail with `commit-msg: first line must start with WI01124532` (verified 2026-10-31) |
| G2 | Resolver flag `-Daether.enhancedLocalRepository.trackingFilename=_any.repositories` on local full builds | Command line (§9.4) | Lets Maven 3.9 use the cached `dynamo-client:1.0` for `registration-inbound-consumers` (finding F1) | The full reactor build gets past `registration-inbound-consumers` |
| G4 | Full reactor builds run in a separate git worktree `C:\Users\arijit.kundu\projects\appianway-build` (detached at the commit under test, pending changes applied as a patch) | `git worktree` outside the VS Code workspace | VS Code (`java.autobuild.enabled: true`, `java.configuration.updateBuildConfiguration: automatic`) rebuilds modules into the same `target/classes` while Maven runs, which deletes compiled classes mid-build (F7) | Build log shows only Maven writing to `target/` |
| G3 | Build logs and test-count snapshots | Session scratchpad (`baseline-build.log`, `baseline-counts.txt`) | Evidence for the test-count check in each PR description | — |

Hook source (G1):

```sh
#!/bin/sh
# Local guard: Bitbucket rejects pushes whose commits lack the work item id.
if ! head -1 "$1" | grep -q '^WI01124532'; then
  echo "commit-msg: first line must start with WI01124532" >&2
  exit 1
fi
```

Git runs `commit-msg` after the message is written and before the commit is created, passing the path of the message file as `$1`. `head -1` takes the subject line; `grep -q '^WI01124532'` checks that it starts with the work item id (`-q` = quiet, only the exit code matters). Exit code 1 aborts the commit. The hook also runs for `git merge` commits. Rebases replay existing messages without re-running it, which is fine because those messages already passed. Install: save the file as `.git/hooks/commit-msg`, then `chmod +x .git/hooks/commit-msg`.

---

## 5. Development plan

### Build order

`shared` comes first; every step keeps the full reactor build green.

| Step | Scope |
|---|---|
| 1a | Surefire on the JUnit Platform (Jupiter + Vintage, existing JUnit 4 tests unchanged); commons 1.0.38-SNAPSHOT coordinates; root pins aligned up to commons: Jetty 12.1.14, Jackson 2.21.8, logback 1.5.38 (classic and core as a pair), slf4j 2.0.18; gen2-parser's local logback/slf4j overrides removed |
| 1b | Commons config chain (`PropertiesSubstitutionConfigProvider` → `TrimConfigCommentsTransform` → `ParameterStoreConfigTransform`); U1 fallback = small `shared` command keeping `run (yaml) (properties...)`; config golden test (every module YAML × every environment) |
| 1c | Back-pressure listener on `MessagingClient<String>` (waits for a permit instead of spinning); client profile per role (incl. transformer metrics helper); cloud-sdk → `RecoverableException` mapping |
| 1d | Workspace S3, SQS sender, SNS publisher, health checks, v2 Guice module; golden byte-identical tests |
| 1e | cloud-sdk fakes, JUnit 5 functional-test base, `AwsSdkBoundaryArchTest`; functional-testing pins aligned |
| 2 | event-writer, error-processor, email-sender |
| 3 | dispatcher, splitter, transformer, distributor, distributor-rest, ingestor |
| 4 | watermill-publisher, watermill platform + booking / visibility / cargoscreen / itv-gps consumers; watermill pins aligned |
| 5 | Delete AWS SDK v1 code and v1 fakes from `shared` |

### Backward compatibility and performance

- Wire formats identical (C1–C9): `shared` `Json` for every payload; S3 string put `text/plain`; REPLACE copy sends `application/octet-stream`; SQS `failedAttempts` + `DelaySeconds`; SNS plain JSON array.
- One client per role, built at startup; health checks reuse the injected clients.
- S3 client without an API-call timeout (large reads are not capped); size via HEAD, not a download.
- Listener back-pressure kept (receive at most the idle-worker count).

### Upstream commons asks

| Id | Plan |
|---|---|
| U1, U2, U4, U5, U6, U7, U10 | Interface-only fallbacks, as in the design |
| U3 (size HEAD) | No fallback without a download (A2) |
| U8 (SES message id), U9 (SES retry) | No fallback; block email-sender until released (A1) |

---

## 6. Step log

### Step 1a — root pom (`WI01124532-aws-sdk-upgrade-pom`)

**Plan:**

1. `WI01124532 build:` Surefire on the JUnit Platform: remove the root `surefire-junit4` provider; add `junit-jupiter` + `junit-vintage-engine` (test scope, versions from the Dropwizard 5.0.2 JUnit BOM, 5.14.4) for the root pom's children. Proof: per-module test counts equal the baseline (transformer increases, F2).
2. `WI01124532 red:` `shared` `PlatformLibraryVersionsTest` (JUnit 5 + AssertJ), failing on today's pins.
3. `WI01124532 green:` align the root pins with commons 1.0.38; pin `logback-core` together with `logback-classic`; add `mercury.commons.version` and `dependencyManagement` entries for `commons`, `cloud-sdk-api`, `cloud-sdk-aws`; remove gen2-parser's local logback/slf4j overrides.
4. `WI01124532 refactor:` tidy the root pom (duplicate `dropwizard.metrics.annotation` property, unused `shared` `jackson-datatype-jsr310-version`).
5. `dependency:tree` per service in the PR description (acceptance criterion 5).

**Baseline (`develop` `0448d362`):** first run failed at `registration-inbound-consumers` (F1); re-run with G2: **BUILD SUCCESS, 26 modules, 9:05 min**. Tests / skipped per module:

| Module | Tests | Skipped |
|---|---|---|
| watermill/billoflading/ebl-inbound-consumers | 10 | 0 |
| watermill/billoflading/registration-inbound-consumers | 10 | 0 |
| watermill/booking-inbound-consumer | 173 | 0 |
| watermill/cargoscreen-consumer | 0 | 0 (F3) |
| watermill/itv-gps-consumer | 80 | 0 |
| watermill/visibility-inbound-consumer | 318 | 0 |
| shared | 1510 | 1 |
| structuralvalidator | 239 | 10 |
| gen2-parser | 1726 | 0 |
| event-writer | 3 | 0 |
| dispatcher | 15 | 0 |
| splitter | 179 | 2 |
| transformer | 4 | 4 (F2) |
| distributor | 48 | 4 |
| distributor-rest | 142 | 0 |
| ingestor | 179 | 0 |
| error-processor | 2 | 0 |
| email-sender | 13 | 0 |
| watermill-publisher | 153 | 0 |
| watermill/consumer-commons | 149 | 0 |
| watermill/consumer-framework | 38 | 0 |

**Key class: `com.inttra.mercury.shared.support.PlatformLibraryVersionsTest` (test, JUnit 5):**

| Method | Asserts |
|---|---|
| `jacksonIsAtLeastTheCommonsVersion` | `jackson-databind`, `jackson-core` ≥ 2.21.8 |
| `jettyIsAtLeastTheCommonsVersion` | `jetty-server` ≥ 12.1.14 |
| `logbackIsAtLeastTheCommonsVersion` | `logback-classic` ≥ 1.5.38 |
| `logbackClassicAndCoreAreTheSameVersion` | `logback-core` = `logback-classic` (a mismatched pair fails at runtime) |
| `slf4jIsAtLeastTheCommonsVersion` | `slf4j-api` ≥ 2.0.18 |
| `httpCore5IsAtLeastTheCommonsVersion` | `httpcore5` ≥ 5.4.3 |
| `dropwizardIsTheCommonsVersion` | `dropwizard-core` = 5.0.2 |
| `versionOf(groupId, artifactId)` (helper) | Reads the resolved version from the jar's `META-INF/maven/<groupId>/<artifactId>/pom.properties` on the test classpath; compares with `Runtime.Version` (numeric, not string, ordering) |

**Commits:**

| # | Commit | Type | Files | Result |
|---|---|---|---|---|
| 1 | `701cc85c` WI01124532 build: run tests on the JUnit Platform (Jupiter + Vintage) | build | `pom.xml` | Full reactor green (9:14 min). Test counts identical to the baseline for every module except transformer: **4 → 665 tests (5 skipped), all passing** (F2 resolved, A14 done) |
| 2 | `42593970` WI01124532 red: platform library versions must not be below commons 1.0.38 | red | `shared/.../support/PlatformLibraryVersionsTest.java` | 7 tests, **4 fail** (Jackson 2.21.4, Jetty 12.1.9, logback 1.5.33, slf4j 2.0.17); logback pair, httpcore5, Dropwizard pass |
| 3 | `3f27f8e7` WI01124532 green: align platform pins with commons 1.0.38 | green | `pom.xml`, `gen2-parser/pom.xml` | `PlatformLibraryVersionsTest` 7/7 pass; full reactor green (9:24 min); counts unchanged except `shared` +7 |
| 4 | `9b0a1235` WI01124532 refactor: tidy platform pin comments and unused properties | refactor | `pom.xml`, `shared/pom.xml` | Stale ION-16098 version comments updated; duplicate `dropwizard.metrics.annotation` and unused `jackson-datatype-jsr310-version` removed; reactor `validate` + `shared` 1517 tests green |
| 5 | `fb837d9d` WI01124532 red: enforce one logback-classic/logback-core version per module | red | `pom.xml` | `dependency:tree` showed watermill-publisher on classic 1.5.33 / core 1.5.38 (F5). New `maven-enforcer-plugin` 3.4.1 `requireSameVersions` rule fails watermill-publisher only |
| 6 | `6bb9ae6c` WI01124532 green: watermill-publisher takes logback from the root pins | green | `watermill-publisher/pom.xml` | Hardcoded `logback-classic` 1.5.33 removed; full reactor green (11:26 min); enforcer passes in all 13 root-pom modules; test counts identical to commit 3 |

**Step 1a status:** all commits done, full reactor green. Waiting for review → push `WI01124532-aws-sdk-upgrade-pom` and open the PR (title starting `WI01124532`) into `WI01124532-aws-sdk-upgrade`.

**Acceptance criterion 5 (`dependency:tree`, after commit 4)** — services on the root pom:

| Library | Version | Modules |
|---|---|---|
| `jackson-databind` | 2.21.8 | shared, event-writer, dispatcher, splitter, transformer, distributor, distributor-rest, ingestor, error-processor, email-sender, watermill-publisher |
| `jetty-server` | 12.1.14 | same |
| `slf4j-api` | 2.0.18 | same + gen2-parser |
| `logback-core` | 1.5.38 | same + gen2-parser |
| `logback-classic` | 1.5.38 | all except watermill-publisher (1.5.33, fixed by commits 5–6) |

**Key build guard — root `maven-enforcer-plugin` execution `logback-pair`:** goal `enforce` (phase `validate`), rule `requireSameVersions` over `ch.qos.logback:logback-classic` and `ch.qos.logback:logback-core`. Runs for every child of the root pom, so a module that pins one half of the pair fails the build at `validate`, before compiling (D5).

**Green change details (`pom.xml`):**

- Properties: `mercury.commons.version` = `1.0.38-SNAPSHOT` (new); `jetty.version` 12.1.9 → 12.1.14; `jackson.bom.version` 2.21.4 → 2.21.8; `slf4j-api.version` 2.0.17 → 2.0.18; `logback-classic.version` 1.5.33 → 1.5.38.
- `dependencyManagement`: `logback-classic` + `logback-core` (one property, D3) and `slf4j-api`, placed before the Dropwizard BOM so they win; `com.inttra.mercury:commons`, `cloud-sdk-api`, `cloud-sdk-aws` at `${mercury.commons.version}` (managed only; `shared` starts depending on them in step 1b).
- `gen2-parser/pom.xml`: removed its local `slf4j-api.version` 2.0.17 / `logback-classic.version` 1.5.21 overrides, so it inherits the root pins.

**Not changed in 1a (and why):** Guava (root 33.1.0-jre, commons 33.5.0-jre) only downgrades commons once a module depends on commons, which starts in step 1b; covered by a red/green cycle there (A17). Mockito (root 2.27.0, commons 5.10.0) is test scope and not transitive; revisit when new tests need `mockito-junit-jupiter` (A18). functional-testing and watermill keep their own pins until steps 1e and 4.

### Step 1b — commons config chain (`WI01124532-aws-sdk-upgrade-shared-config`)

Stacked on `WI01124532-aws-sdk-upgrade-pom` until PR #76 merges (D6).

**Plan (TDD cycles):**

| Cycle | Red | Green | Refactor |
|---|---|---|---|
| A | Tests + skeletons for `ConfigTransformChain`, `PropertiesSources`; `ConfigResolutionGoldenTest` | `shared` depends on `commons` (exclusions, D7); implement both classes | — |
| B | Root enforcer `requireUpperBoundDeps` for Guava and AWS SDK v1 (no-downgrade guard, A17) | Raise `google-guava.version` and `aws-java-sdk.version` to the commons versions | — |
| C | Command test: `ConfigProcessingServerCommand` builds its source with the commons chain (comment lines removed, `${awsps:}` through the lookup) | Rewire the command onto `ConfigTransformChain` (D8, D9) | Move the previous lookup classes (`config.lookup.*`) to test sources as the golden-test oracle |

**Key classes:**

| Class | Role | Important methods |
|---|---|---|
| `com.inttra.mercury.shared.config.ConfigTransformChain` (new) | Builds the commons chain `PropertiesSubstitutionConfigProvider → TrimConfigCommentsTransform → ParameterStoreConfigTransform` around a YAML source | `create(yamlSource, properties, environment, parameterStoreLookup)`: overlays `environment` on `properties` (env first, as today); wraps the Parameter Store lookup in `Suppliers.memoize` so the SSM client is only built on the first `${awsps:}` (D9) |
| `com.inttra.mercury.shared.config.PropertiesSources` (new) | Reads the `run` command's `.properties` paths through the bootstrap source provider (file system or S3) | `load(source, paths)`: each file read as UTF-8, joined with the line separator in command-line order, parsed once with `Properties.load(Reader)`, so later files override earlier keys exactly as the previous command did |
| `com.inttra.mercury.shared.command.ConfigProcessingServerCommand` (changed in cycle C) | Same CLI `run (yaml) (properties...)`, same constructors | `run(bootstrap, namespace)` |

**Tests:**

| Test class | Unit | Cases |
|---|---|---|
| `ConfigTransformChainTest` | `ConfigTransformChain` | properties placeholder; environment before properties (test-only env key, so the build machine's environment cannot interfere); `${k:-default}`; property referencing another property (`datadog.properties` uses `${componentName}`); unresolved placeholder fails naming the key; unresolved placeholder **on a comment line** still fails (same as today); comment lines removed; `${awsps:}` via the lookup; lookup not created without `${awsps:}`; lookup created once for several |
| `PropertiesSourcesTest` | `PropertiesSources` | UTF-8 (`Zürich`); later file overrides; last line without newline kept; no paths → empty; missing file → `IOException` naming the path |
| `ConfigResolutionGoldenTest` | Acceptance criterion 4 | **89 cases** = 16 services × their deployed environments × app variants (splitter `ce-`, transformer `ce-` / `os-`, ingestor `ce-`). Each case rebuilds the real start command from `run.sh` (`run <yaml> ./<app>.properties ./network-services.properties ./datadog.properties`): app properties from `<module>/conf/<env>/`, the others from `configuration/<env>/`, environment variables from the module's ECS task JSON. The previous shared resolver (`VariableLookupProvider` + `ProcessedConfigProvider`) is the oracle; output compared with comment lines removed; both must resolve identically or both fail. `local` environments are skipped (no `configuration/local`). Plus `everyModuleHasAtLeastOneCase` |

**Commits:**

| # | Commit | Type | Result |
|---|---|---|---|
| 1 | `8bf1db21` WI01124532 red: commons config chain must resolve configuration like the shared command | red | 85 golden cases + all 15 unit tests fail on the skeletons; 4 stress cases fail in both resolvers (F6) |
| 2 | `9a704fb0` WI01124532 green: shared builds configuration with the commons chain classes | green | Golden 90/90; full reactor green (13:04 min); counts unchanged except `shared` +105 |
| 3 | `d21bb68e` WI01124532 red: no AppianWay pin may downgrade Guava or AWS SDK v1 below commons | red | Root enforcer execution `no-downgrade` (`requireUpperBoundDeps`, includes `com.google.guava:guava`, `com.amazonaws:aws-java-sdk-{core,s3,sqs,sns}`) fails `shared`: 1.12.720 pinned, `cloud-sdk-aws` needs 1.12.730 |
| 4 | `1294b884` WI01124532 green: raise Guava and AWS SDK v1 pins to the commons versions | green | `aws-java-sdk.version` 1.12.720 → 1.12.730; `google-guava.version` 33.1.0-jre → 33.6.0-jre (Dropwizard-managed; ≥ commons 33.5.0-jre). Enforcer passes everywhere; full reactor green in the build worktree (8:39 min, after F7); counts unchanged (A17 done) |
| 5 | `98f28d96` WI01124532 red: ConfigProcessingServerCommand must build its source with the commons chain | red | `ConfigProcessingServerCommandSourceTest` 5/6 fail on stub hooks |
| 6 | `e23ec6cf` WI01124532 green: ConfigProcessingServerCommand resolves configuration with the commons chain | green | Command tests 6/6 + existing JUnit 4 20/20 + golden 90/90; full reactor green (7:42 min); counts unchanged except `shared` +6 |
| 7 | `0224e384` WI01124532 refactor: keep the previous config resolver only as the golden-test oracle | refactor | `config.lookup.*` (5 classes) moved `src/main` → `src/test` with `git mv` + `package-info` explaining the oracle role; full reactor green (7:38 min), counts unchanged |

**Step 1b status:** all commits done, full reactor green, local only. After #76 merges: rebase onto the feature branch (D6), re-run the full build, push, PR (title `WI01124532 shared: resolve configuration with the mercury-services-commons chain`).

**PR description:** `docs/redesign/pr-details/2026-10-31-apway-pr-1b-shared-config-description.md`.

**Cycle C details — `ConfigProcessingServerCommand`:**

| Method | Behaviour |
|---|---|
| `run(bootstrap, namespace)` | Unchanged CLI: reads the `properties` list, installs `createConfigurationSourceProvider(bootstrap.getConfigurationSourceProvider(), properties)`, then `super.run` |
| `createConfigurationSourceProvider(propertiesSource, propertiesPaths)` (new, `protected`) | `ConfigTransformChain.create(new ResourceConfigurationSourceProvider(), PropertiesSources.load(propertiesSource, paths), System.getenv(), this::createParameterStoreLookup)`. A read failure is logged (`Error reading config …`) and rethrown as `UncheckedIOException` — a `RuntimeException`, as the previous command threw (the existing JUnit 4 tests `testRunWithIOException…` assert this; D11) |
| `createParameterStoreLookup()` (new, `protected`) | `new com.inttra.mercury.config.ParameterStoreLookup()` (SSM, us-east-1, default credentials); called only on the first `${awsps:}` (D9) |
| Removed | private `createVarLookupProvider`, `streamToString` (the previous `config.lookup` path) |

Subclasses (`CreateMappingTemplate`, the three `DynamoTableCommand`s) only use the constructors, so they are unaffected.

**Dependency effect of cycle A (`dependency:tree`):** mysql-connector-java, MyBatis, POI, Jest 5.3.3, junit:junit (compile) absent; ingestor keeps Jest 6.3.1; bucket4j 8.7.0 and AWS SDK 2.x `sdk-core` 2.30.24 now present via commons. Gaps for cycle B: Guava — `shared` 33.6.0-jre (Dropwizard-managed) but dispatcher / ingestor 33.1.0-jre (module pin, below commons 33.5.0-jre); AWS SDK v1 — `shared` pins 1.12.720, `cloud-sdk-aws` expects 1.12.730.

### Step 1c — shared runtime (`WI01124532-aws-sdk-upgrade-shared-runtime`)

Stacked on `WI01124532-aws-sdk-upgrade-shared-config` (D6). Decisions D13–D17, DR-2–DR-4.

**Plan (TDD cycles):**

| Cycle | Scope |
|---|---|
| A | `ClientSettings` (per-role values = today's v1) + `ClientProfile` (cloud-sdk SQS / S3 / SNS configs, retry strategy, HTTP transport); direct `cloud-sdk-api` / `cloud-sdk-aws` dependencies |
| B | v2 overloads on the task model (`Task`, `TaskFactory`, `Dispatcher`, `TaskMessage`, `AsyncDispatcher`, `AbstractTask`) typed on `QueueMessage<String>` (D15) |
| C | Back-pressure listener on `MessagingClient<String>`: receive at most the idle-worker count, `failedAttempts` requested, no visibility timeout, wait for a free worker instead of spinning |
| D | cloud-sdk exception → `RecoverableException` mapping (C9) |

**Key classes (cycle A):**

| Class | Role | Important methods |
|---|---|---|
| `com.inttra.mercury.shared.config.ClientSettings` (new record) | Per-role HTTP and retry values: `connectionTimeout`, `socketTimeout`, `apiCallTimeout`, `maxConnections`, `maxRetries` | `sqsListener()` 1 s / 50 s / 60 s / 50 / 3; `sqsSender()` 1 s / 5 s / 10 s / 50 / 3; `s3()` 1 s / 5 s / 10 min / 50 / 3; `sns()` 1 s / 5 s / 10 s / 50 / 3; `withMaxRetries`, `withTimeouts` for per-module overrides (error-processor etc., D6 of the review) — each value commented with the v1 setting it keeps |
| `com.inttra.mercury.shared.config.ClientProfile` (new) | Turns `ClientSettings` into cloud-sdk configs for the factories; the only AppianWay class touching AWS SDK configuration types | `sqs(settings, queueUrl)` → `AwsMessagingClientConfig` (also sets the builder-required `maxMessages(10)`, unused by the factory); `s3(settings)` → `AwsStorageConfig`; `sns(settings, topicArn)` → `NotificationClientConfig`; `retryStrategy(maxRetries)` — SDK standard strategy, `maxAttempts = retries + 1`, `exponentialDelayWithoutJitter(500 ms, 5 s)`, `retryOnException(any)` (D16); private `httpClient(settings)` — `AwsHttpClientWrapper.ofSyncBuilder(ApacheHttpClient.builder()…)` (D17) |

**Tests (cycle A):**

| Test class | Cases |
|---|---|
| `V1ClientConfigurationCharacterizationTest` (evidence, removed in step 5) | every v1 role: policy max retries 3 and `isMaxErrorRetryInClientConfigHonored() == false` (SNS's configured 2 unused); retry condition true for a 403; backoff 500 / 1000 / 2000 ms, capped 5000; listener socket = v1 default 50 000 ms, no execution timeout; sender / S3 / SNS 1 s / 5 s / 10 s / 50 |
| `ClientSettingsTest` | the four role defaults; `withMaxRetries`; `withTimeouts` |
| `ClientProfileTest` | SQS / S3 / SNS configs carry the role values (call timeout, max connections, 4 attempts, region, credentials, sync transport, topic, queue); retry strategy on a non-retryable-looking failure gives delays 500 ms → 1 s → 2 s, then `TokenAcquisitionFailedException`; 0 retries = 1 attempt |

**Commits:**

| # | Commit | Type | Result |
|---|---|---|---|
| 1 | `97987059` WI01124532 test: characterize the SDK v1 client settings used today | test | 5/5 pass (records existing behaviour; DR-3 follow-up 2 done) |
| 2 | `baa97bb3` WI01124532 red: client profile must reproduce today's v1 client settings | red | 11/11 fail on stubs |
| 3 | `72de727b` WI01124532 green: client profile builds cloud-sdk configs with today's v1 settings | green | Full reactor green (7:39 min); counts unchanged except `shared` +16 |
| 4 | `b951a796` WI01124532 red: task model must accept cloud-sdk QueueMessage alongside the v1 Message | red | 14 of 15 new tests fail on stubs; existing `AsyncDispatcherTest` gets a type witness (`any(Message.class)`) because the overloads make `any()` ambiguous |
| 5 | `d5f78da3` WI01124532 green: task model processes cloud-sdk QueueMessage alongside the v1 Message | green | Full reactor green (8:04 min); all 8 `AbstractTask` services' tests pass unchanged; `shared` +16 |
| 6 | `a852d843` WI01124532 red: error handling must accept cloud-sdk QueueMessage alongside the v1 Message | red | 11/11 new fail on stubs; 18 call sites in existing tests get a type witness (D21) |
| 7 | `b3d10949` WI01124532 green: error handling processes cloud-sdk QueueMessage alongside the v1 Message | green | Full reactor green (6:42 min); counts unchanged except `shared` +11 |

**Cycle B2 details — `ErrorHelper` / `ErrorHandler`:**

| Class | v2 members | Notes |
|---|---|---|
| `task.errorhandler.ErrorHelper` | `getFailedAttempts(QueueMessage<String>)` (String attribute `failedAttempts`, absent → 0), `isRecoverableAttemptsNotMaxed(QueueMessage)`, `sendBackToPickupQueue(QueueMessage, queue)` and `(QueueMessage, MetaData, queue)`, `sendToDLQ(QueueMessage, queue)`, `sendToQueue(QueueMessage, queue)` | Thin; share the existing private `sendToPickupQueue` / `calculateDelay` and a new private `sendBodyToDLQ`, so delay `2^attempt × multiplier`, `failedAttempts + 1`, tokens and log lines are identical |
| `task.ErrorHandler` | `@Metered handleException(QueueMessage<String>, …)` | The logic lives in private methods over a private `FailedMessage` view (body, attempts-not-maxed, send-back, DLQ) with one implementation per message type, so each path calls the `ErrorHelper` overload of its own type. The v1 `handleException` keeps its original call path through the protected hooks (`handleRecoverableException`, `publishCloseRunEvent`, `handleNonRecoverableException`), which now delegate to the private methods. No subclass in the repo overrides a `Message`-typed method (they override `getErrors()` only) |

**Cycle C — back-pressure listener:**

| # | Commit | Type | Result |
|---|---|---|---|
| 8 | `52c36758` WI01124532 red: back-pressure listener on the cloud-sdk MessagingClient | red | 10 of 12 new fail on stubs (the two that pass do so only because the stub's thread dies at once) |
| 9 | `0b8df5d2` WI01124532 green: listener waits for a free worker and receives through cloud-sdk | green | Full reactor green (7:09 min); counts unchanged except `shared` +12 (now 1683); the 4 timing-sensitive classes repeated 5× without a failure |

| Class | Change | Important methods |
|---|---|---|
| `listener.CloudSdkSQSListener` (new; replaces `SQSListener` in step 5) | Same loop as `SQSListener` on `MessagingClient<String>` | `startup()`: while not stopped — `dispatcher.awaitIdleWorker(1 s)`; if a worker is free, `receiveMessages(queueUrl, maxMessages = getIdleThreadCount(), waitTimeSeconds, messageAttributeNames = [failedAttempts])` and `dispatcher.dispatch(...)` when not empty; `InterruptedException` → stop; any other `Throwable` logged ("Exception in SQS Listener :") and the loop continues, as today. No visibility timeout is sent (cloud-sdk never sends it — verified in `SqsMessagingClient`), so the queue default applies, as today. Same start / shutdown log lines. `shutdown()` sets the stop flag; constructor rejects an empty queue URL, as today |
| `threaddispatcher.Dispatcher` | `default awaitIdleWorker(Duration)` | Returns at once if a worker is idle, otherwise sleeps `min(timeout, 50 ms)` — for dispatchers without a pool (ingestor, watermill-publisher) |
| `threaddispatcher.AsyncDispatcher` | `awaitIdleWorker(Duration)` | `semaphore.tryAcquire(timeout)` then `release()`: blocks until a worker finishes, takes nothing (`dispatch` takes the permit) |

**Behaviour versus `SQSListener`:** same receive sizes, attribute, wait time, dispatch and error handling; the only difference is that when every worker is busy the thread now blocks on the dispatcher's semaphore instead of calling `getIdleThreadCount()` in a tight loop (one CPU core per service saved while busy). Worker pools equal `sqsPickupConfig.maxNumberOfMessages` in every service, so the idle count never exceeds the SQS limit of 10 (no cap added, D22).

**Cycle D — cloud-sdk exception mapping (C9):**

| # | Commit | Type | Result |
|---|---|---|---|
| 10 | `5a2d0e21` WI01124532 red: cloud-sdk failures must map to RecoverableException as the v1 wrappers did | red | 23/23 new fail on the stub |
| 11 | `d2ce0f82` WI01124532 green: cloud-sdk failures map to RecoverableException by exception type | green | Full reactor green (8:57 min); counts unchanged except `shared` +23 (now 1706) |

| Class | Role | Important methods |
|---|---|---|
| `externalwrapper.exception.CloudSdkFailures` (new) | The single C9 mapping the 1d adapters call: `catch (RuntimeException e) { throw CloudSdkFailures.toRecoverable(e); }` | `isCloudSdkFailure(Throwable)`: `CloudSdkException` (SQS `MessagingException`, SNS `NotificationException`), `ParameterStoreException`, `S3OperationException`, `S3UploadException`, `FileTransferException`, `StorageClientInitializationException`, or anything that is / is caused by an AWS SDK v2 `SdkException` (raw leaks, e.g. reading the S3 response stream, and the bare `RuntimeException` of the S3 string upload). `toRecoverable(RuntimeException)`: `new RecoverableException(failure)` (same constructor and message as v1); any other failure returned unchanged; an existing `RecoverableException` not wrapped again; for `CloudSdkException` logs operation / resource / `isRetryable()` at WARN without narrowing |

Notes: second `shared` class referencing an AWS SDK type (`SdkException`), next to `ClientProfile` — justified because v1's catch-all was SDK-typed too. Not mapped on purpose: client-side `IllegalArgumentException` (`delaySeconds` > 900 → 1d SQS sender adapter), `SendEmailException` / `TemplateProcessingException` (email-sender step, U8/U9), `DynamoSupportException` (watermill, outside `shared`).

**Tests (cycle D):** `CloudSdkExceptionMappingTest` (23: 10 failure types × {becomes `RecoverableException` with the failure as cause and the v1 message; recognised} — SQS, SNS, non-retryable `CloudSdkException`, SSM, S3 operation / upload / transfer / client init, raw SDK v2, S3 string upload; `IllegalArgumentException` unchanged; `UncheckedIOException` with a non-SDK cause unchanged; `RecoverableException` not wrapped again). Design test 7.

**Tests (cycle C):** `CloudSdkSQSListenerTest` (7: request = idle count + `failedAttempts` + wait + queue; received messages dispatched to the pickup queue; empty receive not dispatched; no receive while no worker is free; continues after a `MessagingException`; stops on interrupt; empty queue URL rejected), `AsyncDispatcherIdleWorkerTest` (3: returns at once without taking a worker; times out while all are busy; returns when a worker finishes), `DispatcherIdleWorkerDefaultTest` (2: immediate when idle; pauses instead of spinning).

**Tests (cycle B2):** `ErrorHelperQueueMessageTest` (8: attribute → attempts; absent → 0; not-maxed boundary 4/5; disabled recovery; send-back delay 80 s and attempts 3 with `NEXT_RETRY_TIME` from the fixed clock; with-MetaData variant 20 s / 1; DLQ body unchanged + token; send-to-queue), `ErrorHandlerQueueMessageTest` (3: recoverable with attempts left → pickup queue and close event `status=true` with the payload as body; attempts exhausted → DLQ, `status=false`; non-recoverable → errors queue).

**Cycle B1 details — QueueMessage overloads (D15, D18–D20):**

| Class | v2 member (stays after step 5) | v1 member (removed in step 5) |
|---|---|---|
| `task.Task` | `default execute(QueueMessage<String>, String)` — until a task overrides it, bridges to the v1 method | `execute(Message, String)` (still the single abstract method, so lambdas keep working) |
| `task.TaskFactory` | `default getTask(QueueMessage<String>)` — bridges to the v1 method, so the services' `message -> taskProvider.get()` lambdas serve both; the same lambda text compiles against the v2-only interface after step 5 | `getTask(Message)` |
| `threaddispatcher.Dispatcher` | `default dispatch(List<QueueMessage<String>>, String)` — bridges to `submit`; own name because `submit(List<…>)` overloads erase to the same signature (D19) | `submit(List<Message>, String)` |
| `threaddispatcher.AsyncDispatcher` | `dispatch(…)` + `work(QueueMessage<String>, …)`: same semaphore permit per message, same logging, `task.execute(QueueMessage, …)` | `submit`, `work(Message, …)` |
| `task.AbstractTask` | `process(QueueMessage<String>, String)` (abstract in step 5); `@Metered execute(QueueMessage<String>, String)` | `process(Message, String)` (no longer abstract; default throws); `@Metered execute(Message, String)` |
| `task.V1MessageBridge` (new, `@Deprecated`) | — | `toQueueMessage(Message)`, `toV1Message(QueueMessage<String>)`: id, receipt handle, body ↔ payload, system attributes, `SentTimestamp` ↔ `Instant`, String message attributes (`failedAttempts`) |

`AbstractTask` decides once per instance (`overridesQueueMessageProcess(getClass())`, reflection) which `process` method the service implements; each `execute` calls that one, converting only when needed, so a v1 task called by the v1 path receives the **same `Message` instance** as before (D18). Both `execute` methods delegate to one private `run(…)`, because Guice intercepts self-calls through its generated subclass: a v1 `execute` calling the public v2 `execute` would count `messages-processed` twice (D20).

**New tests (cycle B1):** `V1MessageBridgeTest` (4), `TaskQueueMessageOverloadTest` (1), `TaskFactoryQueueMessageOverloadTest` (2), `DispatcherQueueMessageOverloadTest` (1), `AsyncDispatcherQueueMessageTest` (3: each message runs the v2 overload; a worker stays busy until its task ends; a failing task releases its worker), `AbstractTaskQueueMessageTest` (5: process then delete by receipt handle; no delete on failure; v1 task via v2 path; migrated task via v1 path; v1 path does not go through the public v2 `execute`). Fixture `TestQueueMessage` (test sources). `shared` gains `awaitility` (test scope).

**Dependencies (cycle A):** `shared` declares `cloud-sdk-api` and `cloud-sdk-aws` directly, excluding Jest and `aws-signing-request-interceptor` (only ingestor needs them and declares its own: Jest 6.3.1, signer 0.0.16 — checked with `dependency:tree`).

---

## 7. Decisions during development

| # | Date | Decision | Reason |
|---|---|---|---|
| D1 | 2026-10-31 | The progress document is the main work document; pending items from the review summary are tracked here (§2) | User request |
| D2 | 2026-10-31 | The library-version guard is a unit test reading `pom.properties` from the test classpath and asserting "at least the commons version" (not equality), except Dropwizard (exact) and the logback pair (equal to each other) | Detects any AppianWay pin that downgrades commons without breaking on later commons upgrades |
| D3 | 2026-10-31 | `logback-core` is pinned next to `logback-classic` in the root pom | Today only classic is pinned; core comes from the Dropwizard BOM, so bumping classic alone would create a mismatched pair |
| D4 | 2026-10-31 | HttpComponents 4.x is not asserted in the version test | It reaches `shared` only through AWS SDK v1, which step 5 removes; covered by `dependency:tree` instead |
| D6 | 2026-10-31 | Step 1b is cut from the 1a sub-branch (stacked), not from the feature branch | 1b needs 1a's commons coordinates and JUnit Platform; #76 is not merged yet. After #76 merges: `git rebase --onto WI01124532-aws-sdk-upgrade WI01124532-aws-sdk-upgrade-pom WI01124532-aws-sdk-upgrade-shared-config`, then open the 1b PR |
| D7 | 2026-10-31 | `shared` depends on `commons` with the unused heavy transitives excluded (mysql-connector-java, MyBatis + mybatis-guice, Apache POI, Jest 5.3.3 + aws-signing-request-interceptor, junit:junit, dropwizard-db, dropwizard-forms) | User decision: smaller service jars and CVE surface; the full reactor tests prove nothing needs them |
| D8 | 2026-10-31 | The U1 fallback keeps `com.inttra.mercury.shared.command.ConfigProcessingServerCommand` (same name, constructors, `run (yaml) (properties...)`) and replaces only its internals with the commons chain | No service or subclass (ingestor `CreateMappingTemplate`, transformer / cargoscreen / itv-gps `DynamoTableCommand`) changes |
| D9 | 2026-10-31 | The Parameter Store lookup is created lazily, only when the configuration contains `${awsps:` | commons `ParameterStoreLookup()` builds an SSM client in its constructor; no AppianWay config uses `${awsps:}` today, so eager creation would add a client and startup time to every service |
| D10 | 2026-10-31 | Red commits contain the new tests plus compiling skeletons (signatures that throw `UnsupportedOperationException`), so each red commit builds and fails only at test time | Keeps every commit compilable for review and bisect |
| D11 | 2026-10-31 | The command keeps wrapping a properties read failure in a `RuntimeException` (`UncheckedIOException`); the new JUnit 5 test's first expectation (`IOException`) was corrected in the green commit | The existing JUnit 4 tests are the compatibility contract; the new test had asserted a behaviour change |
| D12 | 2026-10-31 | Guava pinned to 33.6.0-jre (the Dropwizard 5.0.2 managed version), not commons' 33.5.0-jre | `shared` already resolves 33.6.0-jre from the Dropwizard BOM; pinning modules to 33.5.0-jre would itself be a downgrade for the upper-bound rule |
| D13 | 2026-10-31 | No "API-call timeout = none" is possible through the cloud-sdk factories (S3 default 30 s, SQS 30 s, SNS / SSM 10 s; zero rejected). The client profile sets a generous cap through the factories: **S3 10 min, SQS listener 60 s**; SQS sender and SNS keep 10 s as today | User decision. Keeps the AWS SDK boundary (factories only); a 30 s cap would fail large S3 reads that work today; stalls stay bounded by the socket timeout as in v1 |
| D14 | 2026-10-31 | The client profile follows **today's real v1 values**, not the design table: SNS **3** retries (v1 `RetryPolicy(…, 3, honorMaxErrorRetryInClientConfig=false)` ignores SNS's `withMaxErrorRetry(2)`), SQS listener socket timeout **50 s** (v1 default; `sqs_listener` sets none) | User decision: backward compatibility first. Design pages corrected later via the review-summary post-publish tracker (A21) |
| D15 | 2026-10-31 | Transition of the v1-typed APIs (`Task`, `TaskFactory`, `Dispatcher`, `AbstractTask`, `ErrorHandler`, `ErrorHelper`, `TaskMessage`): `QueueMessage<String>` **overloads on the same classes** (v2 methods as defaults / concrete methods), used by the v2 listener and dispatcher; each module PR switches its tasks to the v2 overloads; step 5 deletes the v1 methods so the final API matches the design (same packages and class names) | User decision; no second import change in every module |
| D16 | 2026-10-31 | Retry strategy for SQS/SNS/S3: SDK 2.x standard strategy, 4 max attempts (= v1 3 retries), `BackoffStrategy.exponentialDelayWithoutJitter(500 ms, 5 s)` for both normal and throttling backoff (v1 `ExponentialBackoffStrategy(500, 5000)` has no jitter), **retry on every exception** (v1 `CustomRetryCondition` always returns true). cloud-sdk `AwsRetryCondition` is not used: it is the legacy SDK 2 `RetryPolicy` API and cannot be passed to `BaseAwsConfig.retryStrategy(RetryStrategy)`. Circuit breaker (retry token bucket) left at the SDK default, comparable to v1's default throttled retries | Same retry behaviour as v1; fits the factories |
| D17 | 2026-10-31 | HTTP transport per client via `AwsHttpClientWrapper.ofSyncBuilder(ApacheHttpClient.builder()…)` (connect 1 s; socket 5 s, listener 50 s; max connections 50); builder mode, so each SDK client owns and closes its own pool | Same per-role connection settings as v1; the cloud-sdk default transport (connect 5 s, socket 30 s) differs |
| D18 | 2026-10-31 | `AbstractTask` picks the `process` method by checking once whether the subclass overrides the `QueueMessage` one, rather than bridging every call | A v1 task keeps receiving the original `Message` instance (existing tests and code may rely on identity or on fields the bridge does not carry, e.g. MD5s); avoids mutual recursion between two default methods |
| D19 | 2026-10-31 | The v2 dispatcher method is named `dispatch` and keeps that name after step 5 | `submit(List<Message>)` and `submit(List<QueueMessage<String>>)` have the same erasure; a permanent new name avoids a second rename in ingestor and watermill-publisher |
| D20 | 2026-10-31 | Both metered `execute` methods share one private `run` method | Guice AOP intercepts self-calls (generated subclass), so calling the public v2 method from the v1 one would double-count `messages-processed` |
| D21 | 2026-10-31 | The `QueueMessage` overloads make untyped `any()` / `null` arguments ambiguous in existing tests; the shared PR adds a type witness at each such call site — `ArgumentMatchers.<Message>any()` (still matches `null`, unlike `any(Message.class)`) or `(Message) null` — and changes nothing else in those tests. 20 sites so far: shared `AsyncDispatcherTest` (2, `any(Message.class)`; arguments are never null there), shared `ErrorHandlerTest` (2), ingestor `ErrorHandlerTest` (6), splitter `SplitErrorHandlerTest` (9), transformer `TransformerTaskTest` (1) | Keeps the reactor compiling with unchanged test meaning; the module PRs later move those tests to `QueueMessage` anyway |
| D22 | 2026-10-31 | The v2 listener asks for exactly the idle-worker count, like v1, with no cap at 10 | Every service sizes its `AsyncDispatcher` with `sqsPickupConfig.maxNumberOfMessages` (≤ 10), so the count never exceeds the SQS limit; a cap would only change behaviour for an already-invalid configuration |
| D23 | 2026-10-31 | The stress environment is not used and is ignored: no fix for its incomplete `network-services.properties` (F6). `ConfigResolutionGoldenTest` keeps its stress cases (they still prove "both resolvers fail the same way"); they may be dropped from the test later without loss | User decision |
| D5 | 2026-10-31 | The logback pair is guarded per module by a Maven Enforcer `requireSameVersions` rule in the root pom, in addition to the `shared` unit test | A unit test only sees its own module's classpath; the enforcer rule checks every child's resolved dependencies at `validate`, so one rule covers all services and future modules |

---

## 7a. Decision records (questions asked during development)

Each record keeps the question as asked, a plain explanation, the options, the answer and the follow-up. The short form is in §7.

### DR-1 (2026-10-31) — How `shared` takes the commons dependency → D7

**Question:** the `commons` artifact also brings mysql-connector-java, MyBatis, Apache POI, Jest 5.3.3, dropwizard-db/forms, bucket4j and compile-scope junit; AppianWay uses none. Exclude them, take commons as-is, or depend only on cloud-sdk?
**Answer:** exclude the unused ones. **Follow-up:** done in step 1b (`9a704fb0`); re-check the exclusion list whenever the commons version changes.

### DR-2 (2026-10-31) — API-call timeout for the S3 and SQS-listener clients → D13

**What an "API-call timeout" is.** It is the longest time one AWS SDK call may take end to end, including its retries. In SDK 2.x (`apiCallTimeout`) it also covers reading the response body, because cloud-sdk's `getContent` / `getObject` read the whole object inside the call. It is different from the **socket timeout**, which only fires when the connection stays silent (no bytes) for that long.

**What happens today (SDK v1).**

| Client | v1 setting | Effect |
|---|---|---|
| S3 | `clientExecutionTimeout` 10 s, socket 5 s | The 10 s clock stops once S3 has *started* answering; reading a large document's body afterwards has no total limit. It only fails if the stream stalls for 5 s |
| SQS listener | no execution timeout, socket 50 s | A 20 s long poll can never be cut short |
| SQS sender, SNS | 10 s execution, socket 5 s | Small requests; 10 s total is ample |

**Why v1's 10 s never cut off a large read, but a v2 cap would.** Both SDKs call the setting a call timeout; what differs is *where the body is read*:

- **SDK v1 (today):** `shared` `S3WorkspaceService` calls `s3Client.getObject(...)`, which returns as soon as S3 sends the response headers; the 10 s clock covers only that call. The body is then read by `shared`'s own code (`read(s3object.getObjectContent())`, `IOUtils.toByteArray(...)` — `S3WorkspaceService.java:150-189`), outside the SDK call, so it is not timed.
- **SDK 2.x via cloud-sdk:** `S3StorageClient` reads the body *inside* the SDK call — `getObjectAsBytes(...)` and `getObject(request, ResponseTransformer.toBytes())` (`S3StorageClient.java:364, 553, 845`); the call returns only when every byte has arrived, and the API-call timeout covers the whole call including the download.

So the same-named limit measures something larger in v2: with a 30 s cap a document that takes 35 s to download fails in v2 but works in v1.

**Why the design asked for "no API-call timeout".** S3: exactly the point above — copying v1's 10 s (the obvious mapping) would cap the whole download, so the design chose no cap and left stalls to the 5 s socket timeout, as in v1. SQS listener: v1 `sqs_listener` sets no execution timeout at all (a receive is bounded only by the 20 s long poll and the 50 s socket timeout), so "none" was simply today's behaviour. That the factories cannot express "none" was found only in step 1c.

**The problem.** The design said "no API-call timeout" for S3 and the listener, but the cloud-sdk factories cannot express "none": they always set one (S3 30 s, SQS 30 s, SNS 10 s, SSM 10 s), and zero is rejected. With a 30 s cap on S3, reading a large document that keeps flowing but takes over 30 s (big EDI files, slow network, an ECS task under load) would **fail where it works today** — the task then raises `RecoverableException`, the message is retried with delay and can end in the DLQ. For the listener, 30 s leaves little margin over a 20 s long poll plus one retry.

**Options.**

| Option | Meaning | Trade-off |
|---|---|---|
| A. Generous cap through the factories (**chosen**) | S3 **10 min**, SQS listener **60 s**; sender and SNS stay 10 s | Stays inside the AWS SDK boundary rule (clients only from cloud-sdk factories). Practically the same as today: a stall is still caught by the socket timeout (5 s / 50 s); only a transfer that keeps trickling bytes for over 10 minutes would be stopped |
| B. Build the SDK clients in `shared` and wrap them | Use the public cloud-sdk-aws constructors with no API-call timeout | Exact v1 parity, but widens the exception to the boundary rule (today only for transformer metrics) |
| C. Factory defaults (30 s) | Nothing configured | Simplest, but not backward compatible for large documents |

**Your answer:** A — generous cap via the factories.

**Follow-up actions.**

| # | Action | Where | Status |
|---|---|---|---|
| 1 | Encode the caps in the client-profile settings (S3 10 min, listener 60 s, sender / SNS 10 s), each with a comment naming the v1 setting it replaces | Step 1c, `ClientSettings` | In progress |
| 2 | Correct the `shared` design page Client Profile table ("none" → the caps) in the batched post-publish edit | A21 | Open |
| 3 | Ask commons to allow "no API-call timeout" in the factory configs; once released, switch S3 / listener to it | A22 | Open |
| 4 | On INT, confirm the largest workspace documents read well within 10 minutes (expected: seconds) | A23 | Open |

### DR-3 (2026-10-31) — Client settings: today's real v1 values or the design table → D14

**What was found.** Reading `shared` `AWSClientConfiguration` against the SDK v1 source showed two values in the published Client Profile table that do not match what runs today:

1. **SNS retries.** The code says `sns_publish ... .withMaxErrorRetry(2)`, so the design table says 2. But every client also gets `.withRetryPolicy(retryPolicy)`, and that policy is built as `new RetryPolicy(condition, backoff, 3, false)`. The last argument, `honorMaxErrorRetryInClientConfig = false`, tells SDK v1 to **ignore** `withMaxErrorRetry(...)` and use the policy's own number, **3**. So SNS publishing today makes up to 4 attempts (1 + 3 retries), like SQS and S3.
2. **SQS listener socket timeout.** `sqs_listener` sets connection timeout and max connections but **no socket timeout**, so SDK v1's default applies: **50 s**. The design table says 30 s (chosen because it must exceed the 20 s long poll). Both are above 20 s; 50 s is what production uses.

**Why it matters.** Backward compatibility is the rule for this program. With the design values, a failing SNS publish would give up after 3 attempts instead of 4 (SNS failures are logged and processing continues, so the visible difference is one fewer retry and about 2 s less waiting before the log line), and the listener would drop a silent connection after 30 s instead of 50 s. Small, but a change nobody asked for.

**Options:** follow today's real values (**chosen**), or the design table.

**Your answer:** today's real values — SNS 3 retries, listener socket 50 s.

**Follow-up actions.**

| # | Action | Where | Status |
|---|---|---|---|
| 1 | Encode SNS 3 retries and listener socket 50 s in `ClientSettings`, with comments | Step 1c | In progress |
| 2 | Add a characterization test that reads the **v1** `AWSClientConfiguration` objects (still on the classpath until step 5) and proves the facts above: policy max retries 3, `isMaxErrorRetryInClientConfigHonored() == false`, listener socket timeout = v1 default 50 s. It is the evidence for the reviewers and is deleted with the v1 code in step 5 | Step 1c | Open |
| 3 | Correct the design page Client Profile table (SNS 2 → 3, listener socket 30 s → 50 s) in the batched post-publish edit | A21 | Open |

### DR-4 (2026-10-31) — Carrying v1 and v2 task signatures during the transition → D15

**Question:** every module's `Task` / `TaskFactory` / `Dispatcher` / `AbstractTask` / `ErrorHandler` uses the v1 `Message`; modules migrate one PR at a time. Overloads on the same classes, or a parallel v2 package?
**Answer:** overloads on the same classes (`QueueMessage<String>`); step 5 deletes the v1 methods. **Follow-up:** implemented in step 1c; each module PR switches its tasks to the v2 overloads.

---

## 8. Findings

| # | Date | Finding | Effect |
|---|---|---|---|
| F1 | 2026-10-31 | The full reactor build of `develop` fails locally at `registration-inbound-consumers`: `dynamo-client:1.0` is only in the local repository, cached from other watermill modules' `lib/` file repositories, and Maven 3.9's enhanced local repository refuses artifacts whose recorded origin is not one of the module's repositories. There is no `~/.m2/settings.xml` locally | Local builds use flag G2; CI presumably resolves it from the corporate repository (A15) |
| F2 | 2026-10-31 | Transformer's 43 JUnit 5 test classes are not run on `develop`: the root pom adds the `surefire-junit4` provider to the Surefire plugin, child poms inherit plugin dependencies, so transformer runs on the JUnit 4 provider and only its 3 JUnit 4 functional classes execute (4 tests, all skipped) | The JUnit Platform switch in 1a makes them run for the first time (A14) |
| F3 | 2026-10-31 | watermill `cargoscreen-consumer` runs 0 tests on `develop`: its 2 JUnit 4 test classes are on the JUnit Platform provider (auto-detected) with no Vintage engine. The watermill tree does not inherit the root pom, so 1a does not change it | Fix in the cargoscreen-consumer PR (step 4): add `junit-vintage-engine` (A16) |
| F4 | 2026-10-31 | Building a single service with `-pl <module>` (without `shared` in the reactor) resolves `mercury-shared:1.0` from `~/.m2`, which can be a stale jar from another branch. watermill-publisher then failed 57 tests (Mockito "Could not create type"); with `-pl shared,<module>` all 153 pass | Always build a service together with `shared` (`-pl shared,<module>` or `-am`); never trust a lone `-pl` result (§9.4) |
| F5 | 2026-10-31 | watermill-publisher hardcodes `logback-classic` 1.5.33 (ION-16098 comment) while `logback-core` follows the root pin, so after the alignment it resolved a mismatched pair (classic 1.5.33 / core 1.5.38) | Fixed in step 1a (commits 5–6) and guarded by the enforcer rule (D5) |
| F6 | 2026-10-31 | `configuration/stress/network-services.properties` has no `networkservices.messageRegisterServicePath`, which the dispatcher, splitter and transformer YAMLs reference, so their stress configuration fails to resolve today (previous resolver too) | Existing; behaviour kept (golden test records "both fail"). Add the key if stress is still used (A20) |
| F7 | 2026-10-31 | A full build failed in gen2-parser with `NoClassDefFoundError: com/inttra/mis/data/IMessage` (Vintage engine discovery). Maven had compiled 48 classes; at 18:06:25, before the tests, `target/classes` held one class written by the VS Code Java extension, which rebuilds the workspace automatically | Environmental, not caused by the change. Builds now run in a separate worktree (G4) |
| F8 | 2026-11-02 | The previous resolver substituted and validated the whole joined `.properties` text (comment lines included), so an unresolvable `${...}` in a property the YAML never uses failed startup. The commons `PropertiesSubstitutionConfigProvider` resolves property values only when the YAML references them, so such a placeholder is now ignored. No current configuration is affected (golden test: no "previous fails, current succeeds" case) | Documented as a deliberate relaxation in the PR #78 description and walkthrough (`pr-details/…-pr-1b-shared-config-description.md` §2.1.2); no code change |

---

## 9. Key commands

Only the commands that matter for this work. Run from the repository root (`C:\Users\arijit.kundu\projects\appianway`) in Git Bash unless stated otherwise.

### 9.1 Git — branches

```bash
git fetch origin
```

Downloads the latest commits and branch pointers from the remote (`origin`) without changing your working tree or local branches. Run it before cutting a branch so you start from the current `develop`.

```bash
git branch WI01124532-aws-sdk-upgrade origin/develop
git branch --unset-upstream WI01124532-aws-sdk-upgrade
```

Creates the feature (integration) branch at the same commit as the remote `develop`, without switching to it. `git branch <name> <start-point>` sets `origin/develop` as the upstream automatically; `--unset-upstream` removes that link so a later `git push` cannot accidentally target `develop`. The upstream is set to the branch's own remote name at the first push (below).

```bash
git checkout -b WI01124532-aws-sdk-upgrade-pom WI01124532-aws-sdk-upgrade
```

`-b` creates a new branch and switches to it in one step. The last argument is the start point: every sub-branch starts from the tip of the feature branch, never from `develop`.

```bash
git push -u origin WI01124532-aws-sdk-upgrade
```

Publishes the branch to the remote. `-u` (`--set-upstream`) records `origin/WI01124532-aws-sdk-upgrade` as its upstream, so later `git push` / `git pull` on that branch need no arguments.

### 9.2 Git — TDD commits

```bash
git add shared/src/test/java/.../SomeUnitTest.java
git commit -m "WI01124532 red: <what the test expects>"
```

Stage files **by explicit path**. Never `git add -A` or `git add .` at the root: they would also stage the untracked `docs/`, `.claude/`, module `docs/` folders and `*.code-workspace`. The `red:` commit contains only the new failing test; the `green:` commit contains the production change that makes it pass; `refactor:` contains cleanup with all tests still green. The message must start with `WI01124532` (G1).

```bash
git commit --amend -m "WI01124532 <corrected message>"
```

Replaces the message (and content, if files are staged) of the last commit. Use it **only before the commit is pushed**; after a push, rewriting it requires a force push.

```bash
git status --short
git diff --cached --stat
```

`--short` gives a compact one-line-per-file status (`M` modified, `A` added, `??` untracked). `diff --cached --stat` lists what is staged (what the next commit will contain) with line counts. Check both before every commit.

```bash
git log --oneline --first-parent WI01124532-aws-sdk-upgrade
```

`--first-parent` follows only the first parent of each merge commit, so on the feature branch it shows one line per merged sub-branch PR (the review history), not every commit inside each PR.

### 9.3 Git — keeping the feature branch current (plan §9.5)

```bash
git rebase --rebase-merges develop
git push --force-with-lease
```

Replays the feature branch on top of the latest `develop`. `--rebase-merges` keeps the sub-branch PR merge commits (a plain rebase would flatten them into a straight line). Because the history is rewritten, the push must be forced; `--force-with-lease` refuses if someone else pushed to the branch since your last fetch, unlike `--force`, which overwrites blindly.

```bash
git rebase --onto <new-feature-tip> <old-feature-tip> <sub-branch>
```

Moves an open sub-branch after the feature branch was rebased: takes the commits that are in `<sub-branch>` but not in `<old-feature-tip>` and replays them on `<new-feature-tip>`.

### 9.4 Maven — builds

```bash
mvn -B clean verify -Ddependency-check.skip=true -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
```

Full reactor build: `clean` deletes every `target/`; `verify` compiles, runs the unit tests (Surefire) and anything else bound up to the `verify` phase. `-B` (batch mode) gives plain, log-friendly output without download progress bars. `-Ddependency-check.skip=true` skips the OWASP dependency-check plugin (slow, network-heavy) during routine builds; run it separately when checking CVEs. `-Daether.enhancedLocalRepository.trackingFilename=_any.repositories` (G2) points Maven's resolver at a tracking file that does not exist, so it stops checking which remote repository each cached artifact came from and accepts what is in `~/.m2` (needed locally for `dynamo-client:1.0`, F1). Acceptance criterion 1: this must be green at every step.

```bash
mvn -B -pl shared -am verify
```

`-pl shared` (projects list) builds only the `shared` module; `-am` (also make) also builds the reactor modules it depends on. Fast loop for a single module.

```bash
mvn -B -pl shared,watermill-publisher verify -Ddependency-check.skip=true
```

Builds a service **together with `shared`** from source. A service built alone (`-pl watermill-publisher`) takes `mercury-shared:1.0` from `~/.m2`, which may be a stale jar left by another branch and gives misleading failures (F4). `-pl a,b` lists several modules; Maven orders them by dependency.

```bash
mvn -B validate -fae
```

Runs only the `validate` phase (no compile, no tests) for the whole reactor; this is where the enforcer `logback-pair` rule runs, so it is the fastest way to check the logback pair in every module. `-fae` (fail at end) keeps going after a failing module, so one run lists every failing module instead of stopping at the first.

```bash
mvn -B -pl shared test -Dtest=PlatformLibraryVersionsTest
```

Runs a single test class. `-Dtest` accepts a class name, `Class#method`, or patterns such as `*VersionsTest`. Use it for the red/green loop.

```bash
mvn -B -pl dispatcher dependency:tree -Dincludes=org.eclipse.jetty,com.fasterxml.jackson.core,ch.qos.logback,org.slf4j
```

Prints the resolved dependency tree for one module. `-Dincludes=groupId[:artifactId]` (comma-separated) filters it to the libraries of interest. Acceptance criterion 5: every service resolves the commons-managed versions (no downgrade by AppianWay pins).

### 9.5 Building in a separate worktree (G4)

```bash
git worktree add --detach ../appianway-build HEAD
git diff > /tmp/wip.patch && git -C ../appianway-build apply /tmp/wip.patch
cd ../appianway-build && mvn -B clean verify -Ddependency-check.skip=true -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
```

`git worktree add` checks out a second working directory that shares the same repository (objects, branches) — no second clone. `--detach` checks out the commit itself rather than a branch (a branch can only be checked out in one worktree at a time, and the main tree already has it). `git diff > patch` captures uncommitted changes and `git -C <dir> apply` applies them in the other worktree (`-C` runs git as if started in `<dir>`). Building there keeps the IDE's automatic Java build from touching Maven's `target/` folders (F7).

```bash
git -C ../appianway-build checkout --detach <commit> && git -C ../appianway-build reset --hard
git worktree remove ../appianway-build
```

Moves the build worktree to another commit (discarding the applied patch), or deletes it when the work is done. `git worktree list` shows all worktrees.

### 9.6 Test-count check (acceptance criterion 7)

```bash
for d in $(find . -type d -name surefire-reports -path "*/target/*" | sort); do
  m=${d%/target/surefire-reports}
  t=$(grep -ho ' tests="[0-9]*"' $d/TEST-*.xml | grep -o '[0-9]*' | awk '{s+=$1} END {print s}')
  s=$(grep -ho ' skipped="[0-9]*"' $d/TEST-*.xml | grep -o '[0-9]*' | awk '{s+=$1} END {print s}')
  echo "$m $t $s"
done
```

After a full build, prints per module the total of the `tests="N"` and `skipped="N"` attributes of all its Surefire XML reports (`target/surefire-reports/TEST-*.xml`). `grep -ho` prints only the matching part without file names; the second `grep -o` keeps the number; `awk` adds the numbers up (`bc` is not installed in Git Bash). `${d%/target/surefire-reports}` strips that suffix to get the module path. Compare the output before and after a change: each module must show its previous count plus only the new tests, which proves no JUnit 4 test was silently skipped.
