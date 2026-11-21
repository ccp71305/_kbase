# Actions (A#)

← [Tracker home](README.md) · Closed actions: [closed-items.md](closed-items.md#closed-actions)

Open and partly done items. Each block: owner, when it is needed, where it came from, the action and its status. 🔴 = must be done before release and needs INT; 🟡 = needed at a later migration step.

Origin: items carried over from the review summary (its §4 to §9) and items raised during development. Done or dropped items are in [closed items](closed-items.md#closed-actions).

| ID | Title | Owner | Status |
|---|---|---|---|
| [A1](#a1) | Commons release with U3, U8, U9 | Arijit / commons | Code done, published as 1.0.39-SNAPSHOT; release pending |
| [A3](#a3) | Raise the remaining commons asks | Arijit | Partly done: U10, U6, U7, U4, U1, U15 open |
| [A6](#a6) | INT: visibility timeouts vs distributor-rest worst-case POST | Arijit / INT | Open, INT |
| [A7](#a7) | INT: distributor null-metadata behaviour | Arijit / INT | Open, INT |
| [A8](#a8) | INT/IAM: SESv2 actions and redrive policies | Arijit / infra | Open, before INT |
| [A9](#a9) | Transformer CloudWatch metric names: dashboards and alarms | Arijit | Open, before transformer INT |
| [A10](#a10) | ingestor: Jest SigV4 signer 0.0.22 check (only before moving off 0.0.16, [F30](findings.md#f30)) | Arijit / INT | Open, not blocking |
| [A11](#a11) | Hystrix and guava-retrying replacement (follow-up design) | Arijit | Open, after release |
| [A12](#a12) | Existing defects: one disabled test per defect in each module PR | Each module PR | Ongoing, steps 2-4 |
| [A15](#a15) | Resolver flag [G2](rules.md#g2) for registration-inbound-consumers: CI? | Arijit | Open |
| [A16](#a16) | cargoscreen-consumer runs 0 tests: add the Vintage engine | cargoscreen PR | Open, step 4 |
| [A18](#a18) | Mockito version decision | Arijit | Open |
| [A21](#a21) | Batched design-page corrections | Arijit | Open, before design approval |
| [A26](#a26) | Commons 1.0.39-SNAPSHOT availability and rebase risk | Arijit / commons | Published; commons-owned risk open |
| [A27](#a27) 🟡 | INT shutdown check: optional confirmation of the ECS task stop | Arijit / INT | Open, optional (lowered 2026-11-19: verified locally on QA) |
| [A29](#a29) 🟡 | Step 5: transformer test code still on SDK v1 (stress harness, parity test's v1 side) | Arijit | Open, at step 5 |
| [A30](#a30) 🟡 | Check the control-number table item in INT, CVT and PROD before cut-over | Arijit | Open, before the transformer release (PROD read only with Arijit's OK) |

Closed: [A2](closed-items.md#a2) Interim approach for U3 (size by HEAD), [A4](closed-items.md#a4) Commons snapshot version in use, [A13](closed-items.md#a13) Delete old local branches, [A14](closed-items.md#a14) Transformer's JUnit 5 tests run for the first time, [A17](closed-items.md#a17) Guava version alignment, [A19](closed-items.md#a19) PRs could not be created on Bitbucket, [A20](closed-items.md#a20) Stress environment configuration, [A22](closed-items.md#a22) Commons asks: no API-call timeout, SSM retry, access-key log, [A23](closed-items.md#a23) INT: large reads within the 10-minute cap, [A24](closed-items.md#a24) Bitbucket build merge check, [A25](closed-items.md#a25) Merge develop into the feature branch.

---

<a id="a1"></a>
### A1 · Commons release with U3, U8, U9

**Owner:** Arijit / commons · **Needed by:** Before the AppianWay release; email-sender PR (step 2) · **Source:** Review summary §1, §9 tracker 1

**Action.** Commons release with **U3** (S3 size HEAD), **U8** (SES message id), **U9** (SES retry strategy). Release prerequisite; U8–U9 block email-sender

**Status.** **Code done 2026-11-12** in commons **1.0.39-SNAPSHOT** (`feature/ION-12310-commons-cloudsdk-refactoring` `aa52175`, commons PR #29 on Bitbucket; checked in the source 2026-11-17: `StorageClient.getObjectSize`, `EmailService.sendEmailWithResult`, SES/SSM factories apply a configured `RetryStrategy`). **Published 2026-11-17** to `inttra-maven` by Jenkins `Mercury_Commons_Publish` from `aa52175` (see [A26](#a26))

<a id="a3"></a>
### A3 · Raise the remaining commons asks

**Owner:** Arijit · **Needed by:** Before step 5, so fallbacks can be retired later · **Source:** Review summary §5 decision 2

**Action.** Raise the commons upstream asks U1, U2, U4, U5, U6, U10 (U7 optional); fallbacks are used meanwhile

**Status.** **Partly done:** U2, U5, U11, U12, U13, U14 are in 1.0.39-SNAPSHOT (spec §1, decision 2), so 1d needs **no** fallback for them. **Still open (later commons release):** U10, U6, U7, U4, U1, and U15 (added 2026-11-19, low: a missing storage key logged at ERROR, [F21](findings.md#f21)); their fallbacks stay (U1 fallback already merged in 1b)

<a id="a6"></a>
### A6 · INT: visibility timeouts vs distributor-rest worst-case POST

**Owner:** Arijit / INT · **Needed by:** distributor-rest PR · **Source:** Review summary §4, §9 tracker 4

**Action.** INT: confirm queue visibility timeouts against the distributor-rest worst-case POST (≈ 3 × 120 s), distributor-rest OI 4

**Status.** Open

<a id="a7"></a>
### A7 · INT: distributor null-metadata behaviour

**Owner:** Arijit / INT · **Needed by:** distributor PR · **Source:** Review summary §9 tracker 4

**Action.** INT: distributor null-metadata behaviour, distributor OI 3

**Status.** Open

<a id="a8"></a>
### A8 · INT/IAM: SESv2 actions and redrive policies

**Owner:** Arijit / infra · **Needed by:** Before INT deployment · **Source:** Review summary §7, `shared` OI 11

**Action.** INT/IAM: SESv2 IAM actions (email-sender); redrive policies. (`sqs:GetQueueAttributes` for the health probe is **no longer needed**: U5 lets `InboundMessageQueueHealthCheck` receive with `requestVisibilityTimeoutSeconds(0)` exactly like v1)

**Status.** Open (narrowed 2026-11-17)

<a id="a9"></a>
### A9 · Transformer CloudWatch metric names: dashboards and alarms

**Owner:** Arijit · **Needed by:** Before INT deployment of transformer · **Source:** Review summary §5 decision 8

**Action.** Transformer SDK 2.x CloudWatch metric names differ from v1: review dashboards and alarms

**Status.** Open

<a id="a10"></a>
### A10 · ingestor: Jest SigV4 signer check on INT

**Owner:** Arijit / INT · **Needed by:** ingestor PR · **Source:** Review summary §6

**Action.** ingestor: Jest SigV4 signer 0.0.22 check on INT. Since 2026-11-20 ([F30](findings.md#f30)): ingestor keeps 0.0.16 in its PR (0.0.22 no longer signs Content-Length, test-proven); this check is needed only before moving to 0.0.22, a separate change

**Status.** Open

<a id="a11"></a>
### A11 · Hystrix and guava-retrying replacement (follow-up design)

**Owner:** Arijit · **Needed by:** After this release · **Source:** Review summary §1, decision 3

**Action.** Hystrix 1.5.18 + guava-retrying replacement: separate follow-up design under WI01124532

**Status.** Open

<a id="a12"></a>
### A12 · Existing defects: one disabled test per defect in each module PR

**Owner:** Each module PR · **Needed by:** Steps 2–4 · **Source:** Review summary §5 decision 4

**Action.** Existing defects (review summary §4): each module PR adds one disabled test (`@Disabled` + defect reference) per defect

**Status.** Open Every defect found so far, with the QA table: [known-defects.md](known-defects.md).

<a id="a15"></a>
### A15 · Resolver flag G2 for registration-inbound-consumers: CI?

**Owner:** Arijit · **Needed by:** Step 1a PR · **Source:** Finding [F1](findings.md#f1)

**Action.** The local full build needs the resolver flag [G2](rules.md#g2) for `registration-inbound-consumers` (finding [F1](findings.md#f1)); check whether CI is affected

**Status.** Open

<a id="a16"></a>
### A16 · cargoscreen-consumer runs 0 tests: add the Vintage engine

**Owner:** cargoscreen PR · **Needed by:** Step 4 · **Source:** Finding [F3](findings.md#f3)

**Action.** cargoscreen-consumer runs 0 of its tests ([F3](findings.md#f3)): add the Vintage engine and verify the count

**Status.** Open

<a id="a18"></a>
### A18 · Mockito version decision

**Owner:** Arijit · **Needed by:** Step 1c · **Source:** Step 1a

**Action.** Mockito: root 2.27.0 vs commons / Dropwizard 5.x. Decide the version when new JUnit 5 tests need `mockito-junit-jupiter`

**Status.** Open

<a id="a21"></a>
### A21 · Batched design-page corrections

**Owner:** Arijit · **Needed by:** Before design approval · **Source:** Step 1c; [D25](decisions.md#d25)

**Action.** Design-page corrections (review-summary §9 tracker, one batched minor edit of `shared` 716084130): Client Profile table — SNS retries 2 → 3, SQS listener socket 30 s → 50 s ([D14](decisions.md#d14)); API-call timeout "none" → S3 10 min / listener 60 s cap ([D13](closed-items.md#d13)); retry condition "cloud-sdk `AwsRetryCondition`" → "SDK standard strategy retrying every exception" ([D16](decisions.md#d16)); transition overloads ([D15](decisions.md#d15)); **naming ([D25](decisions.md#d25)):** test plan and adapter names to the cloud-sdk-api concepts (`CloudSdkWorkspaceServiceTest` → `StorageWorkspaceServiceTest`, `CloudSdkSQSClientTest` → `MessageQueueClientTest`, `CloudSdkSnsEventPublisherTest` → `NotificationEventPublisherTest`, `CloudSdkParameterSupplierTest` → `CloudParameterSupplierTest`, `CloudSdkExceptionMappingTest` → `CloudServiceFailuresTest`, back-pressure listener → `MessageQueueListener`)

**Status.** Open

<a id="a26"></a>
### A26 · Commons 1.0.39-SNAPSHOT availability and rebase risk

**Owner:** Arijit / commons · **Needed by:** Before the first 1d push that CI must build; at the latest the final PR · **Source:** 2026-11-17

**Action.** Commons 1.0.39-SNAPSHOT availability: originally only in the local `~/.m2` (`mvn install` 2026-11-12, `localCopy=true`), so CI (Jenkins `PR_BUILD`) could not resolve it until it was deployed to the shared Maven repository (`inttra-maven`). Also commons-owned: PR #29 is on Bitbucket (commons is **not** on GitHub yet), and its pending rebase onto commons `develop` silently deletes `CryptoLib` / `Encryptor` (commons doc `2026-11-16-sdk-commons-vs-develop-rebase.md`). If 1.0.39-SNAPSHOT is republished from the rebased branch, those classes disappear from the snapshot too

**Status.** **Publish done 2026-11-17:** Jenkins `Mercury_Commons_Publish` (branch `feature/ION-12310-commons-cloudsdk-refactoring`, commit `aa52175`, `Finished: SUCCESS`, 05:54 UTC) deployed all six modules. Checked in `https://inttra-ci.dev.e2open.com/maven2`: `maven-metadata.xml` for cloud-sdk-api, cloud-sdk-aws, commons, dynamo-client, dynamo-integration-test and email-sender is timestamp `20261117.05xxxx`, build 1. The published cloud-sdk-api jar has `StorageClient.getObjectSize` and `EmailService.sendEmailWithResult`. **Still open (commons-owned):** commons is still on Bitbucket (moving to GitHub later, per Arijit), and the rebase risk above

<a id="a27"></a>
### A27 🟡 optional · INT shutdown check: confirm the ECS task stop

**Owner:** Arijit / INT · **Needed by:** Each service's INT boot (event-writer first); before release · **Source:** PR #4 review round 3

**Action.** **INT shutdown check, every migrated service** (PR #4 review: Copilot's "Needs a closer look" asks for runtime validation, which tests and fakes cannot give). With messages flowing, stop the service (ECS task stop) and check: (1) the log shows the clients closing ("Closing … on application shutdown", one line per client) and no "Messages still in progress after 20 s" WARN (a drain that finishes in time logs nothing); at most one `Exception in SQS Listener` ERROR from a cut-off long poll; (2) every message in progress was either stored and deleted, or delivered again, with no event missing (compare events stored with messages sent); (3) the task stops within the 30 s stop timeout. Expected by design: a late poll's messages are not run and come back; at the 20 s deadline the sender closes first and the real sender refuses a late delete (`ClosedSenderRefusesDeleteTest`). **Local check done 2026-11-19 on dispatcher** ([runtime/dispatcher.md](runtime/dispatcher.md#test-4b)): Ctrl+C with 10 in progress and 10 waiting; receiving stopped at once, drain 8 s, 4 clients closed after it, exit 8.7 s, each of the 20 processed exactly once (CloudWatch 20/20/20). The INT check stays for the ECS stop itself (SIGTERM, 30 s stop timeout) and the other services. **Logging prerequisite:** the close lines come from `com.inttra.mercury.cloudsdk.config.ManagedCloudResource` at INFO. error-processor keeps that logger at INFO; **event-writer (merged) has the whole cloud-sdk tree at WARN, so add that logger line to `event-writer.yaml` before its INT check**

**Status.** 🟡 Open, optional. **Lowered 2026-11-19 (Arijit)** from 🔴 "before release": the local QA check on dispatcher verified the shutdown itself, and that code is shared by every migrated service. Ctrl+C and the ECS SIGTERM run the same JVM shutdown hooks, and the exit took 9 s against the 30 s stop timeout. What remains is only to confirm it on a real ECS task stop, when convenient. Dropped from the PR descriptions

<a id="a29"></a>
### A29 🟡 · Step 5: transformer test code still on SDK v1

**Owner:** Arijit · **Needed by:** step 5 (SDK v1 removed from `shared`) · **Source:** transformer pre-review (2026-11-20)

**Action.** When `shared` drops SDK v1, transformer's test code no longer compiles where it uses v1 types: port or delete `stress/TransformerStressTest` (ignored manual harness on SDK v1 clients) and remove the v1 side of `ControlNumberSequenceParityTest` (test-only v1 DAO and item; the v2 tests stay)

**Status.** 🟡 Open

<a id="a30"></a>
### A30 🟡 · Check the control-number table item in the other environments

**Owner:** Arijit · **Needed by:** transformer release · **Source:** transformer design open issue 2, pre-review point 1

**Action.** The new build reads the one item by key `SequenceId` (no "more than one item" check until commons U6). QA checked (one `SequenceId` item). Check INT (`inttra_int_controlnumber_sequence`), CVT (`inttra2_cv_controlnumber_sequence`) and PROD (`inttra2_pr_controlnumber_sequence`, read only, with Arijit's OK) hold exactly one item with that key

**Status.** 🟡 Open

