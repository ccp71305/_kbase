# WI01124532 AppianWay AWS SDK upgrade — tracker

The working tracker for the AppianWay move from AWS SDK v1 to cloud-sdk (AWS SDK 2.x). **Start here:** this page has the current state, the next steps, what is waiting on Arijit and a map of every other document. Open the other pages only through the links. Local only: never committed (`docs/` stays untracked).

_Last updated: 2026-11-21: watermill-publisher **merged** ([PR #13](https://github.com/wtg-e2open/INTTRA.appianway/pull/13), `9537d1c1`). **Wave 4a complete.** Next: wave 4b, the consumer platform. **Resume here:** [Prompt for the next session](#next-session-prompt)._

## Now

- **Feature branch** `feature/WI01124532-aws-sdk-upgrade` at **`9537d1c1`** (PR #13 watermill-publisher merged 2026-11-21 03:49 UTC). Last full reactor build: `4f0c89f0` BUILD SUCCESS (11:55 min); the later commits change watermill-publisher only (module green on each).
- **Done so far:** step 1 (shared, functional-testing), step 2 (event-writer, error-processor, email-sender), step 3 (dispatcher, splitter, transformer, ingestor, distributor, distributor-rest), **step 4a watermill-publisher** ([log](steps/step-4a-watermill-publisher.md)): every ETL-style service is on cloud-sdk.
- **Remaining SDK v1 users:** the watermill consumer platform and consumers (`watermill/consumer-framework`, `consumer-commons`, `visibility-inbound-consumer`, `booking-inbound-consumer`, `itv-gps-consumer`, `cargoscreen-consumer`, `billoflading`), all on DynamoDB, plus `shared`'s own v1 code and fakes (step 5). Counts and features: [step-4-plan.md](steps/step-4-plan.md#what-is-left).
- **Runtime verification** (local runs against QA, [runtime-verification.md](runtime-verification.md)): tests 1 event-writer, 2 error-processor, 4 dispatcher, 5 splitter, 6 transformer, 7 ingestor, 8 distributor, 9 distributor-rest and 10 watermill-publisher passed; test 3 email-sender partly (the send to be tried on INT). Logs per service: [runtime/](runtime/README.md).
- **Build worktree** `C:\Users\arijit.kundu\projects\appianway-build` detached at `98d5f8fb` (clean; reset it before the next build). Main tree: on the merged sub-branch; switch to the feature tip for 4b.

## Next steps

1. **Wave 4b: the consumer platform** (`watermill/consumer-framework` + `watermill/consumer-commons`), as one PR, per [step-4-plan.md](steps/step-4-plan.md) (read its "What is different from step 3" section first: DynamoDB item compatibility is the golden test; the Watermill offset store is the consumers' state). Start in a new chat with the prompt below.
2. **Then** 4c (visibility-inbound, booking-inbound, itv-gps, cargoscreen consumers, one PR each), 4d (billoflading), step 5 (remove SDK v1 from `shared`), the final PR feature → `develop`.
3. **Runtime verification on INT:** email-sender's actual send through the ECS task (Arijit); [A27](actions.md#a27) optional.
4. **Open follow-ups:**
   - Tell the pi-statusevents-out-processor owners (mercury-services) about [KD-27](known-defects.md#kd-27): UTF-8 bytes under an ISO-8859-1 declaration, garbled place names at e2open.
   - ingestor's `ExternalServicesModuleWiringTest` stops managed objects it never started, so its real clients stay open (found by Copilot on PR #13; test-only).
   - Move the test helpers each service now copies (`TestQueueMessage`, 11 copies; the shared SDK v1 class list of the boundary test; the `TypeLiteral` client keys) into functional-testing or shared.
   - Commons asks: [F15](findings.md#f15) and [F17](findings.md#f17) (storage and email `close()` do nothing); cloud-sdk logs routine storage calls at INFO (each service overrides it); [F21](findings.md#f21) missing key logged at ERROR (U15, low); [F25](findings.md#f25) the same probe retried 3 times: check the ECS health-check timeout.
   - [A30](actions.md#a30) transformer's sequence item in INT / CVT / PROD (kept out of the PR). [A10](actions.md#a10) only before moving ingestor's signer off 0.0.16 ([F30](findings.md#f30)).
5. **Before every commit:** `git config user.email` is the WTG address; the subject starts with `WI01124532` ([rules](rules.md)). **Before calling a PR ready:** fetch Copilot's review and inline comments, and handle each.

<a id="next-session-prompt"></a>
## Prompt for the next session

Paste into a new chat:

```text
Continue WI01124532: read docs/tracker/README.md, then steps/step-4-plan.md (all of it, especially "What is different from step 3"), and start wave 4b: the watermill consumer platform (watermill/consumer-framework + watermill/consumer-commons) as one PR.
Cut WI01124532-aws-sdk-upgrade-consumer-platform from origin/feature/WI01124532-aws-sdk-upgrade (9537d1c1).
Before any code: map every DynamoDB table, item class, key, attribute name/type and converter they use (SDK v1 DynamoDBMapper, dynamo-client DynamoDBCrudRepository, @DynamoDBStream), and the watermill_offset store; write the step-4b page with the plan; look at mercury-services booking/visibility for the cloud-sdk DatabaseRepository mapping patterns (not their test style).
Then follow the service recipe: golden test on v1 first (exact DynamoDB items written and read, on DynamoDB Local via commons dynamo-integration-test, including an offset written by v1 and read back by the new code), red/green pairs, known defects as disabled tests, full build in the build worktree, pre-review (code-review high), PR doc, push and PR after my OK, then check Copilot's comments, then a runtime test against QA (D46/D47 allow QA offsets and DynamoDB data writes; no publish to e2open, D48).
Keep me posted with short updates; start a new chat per wave.
```

## Waiting on Arijit


(Known defects: not fixed, [D43](decisions.md#d43).)

## Before release

- [A1](actions.md#a1) a released commons version with U3, U8, U9 (today 1.0.39-SNAPSHOT); [A26](actions.md#a26) the snapshot's rebase risk.
- [A8](actions.md#a8) SESv2 IAM actions and redrive policies; [A9](actions.md#a9) transformer metric names; [A21](actions.md#a21) design-page corrections before approval.
- Full list with owners: [actions](actions.md).

## Step status

| Step | Scope | Status | Log |
|---|---|---|---|
| 1a | Root pom: JUnit Platform, commons coordinates, pins aligned | ✅ PR #76 merged (`a9a7afbb`) | [step-1a](steps/step-1a-pom.md) |
| 1b | Commons config chain | ✅ PR #78 merged (`f64fa017`) | [step-1b](steps/step-1b-shared-config.md) |
| 1c | Client profile, `QueueMessage` overloads, back-pressure listener, exception mapping | ✅ PR #80 merged (`fa3efede`) | [step-1c](steps/step-1c-shared-runtime.md) |
| 1d | Shared adapters, `CloudServicesModule`, golden wire tests | ✅ [PR #2](https://github.com/wtg-e2open/INTTRA.appianway/pull/2) merged (`673a3d65`) | [step-1d](steps/step-1d-shared-adapters.md) |
| 1e | cloud-sdk fakes, JUnit 5 functional base, boundary rule | ✅ [PR #3](https://github.com/wtg-e2open/INTTRA.appianway/pull/3) merged (`58aee71b`) | [step-1e](steps/step-1e-functional-testing.md) |
| 2 | event-writer | ✅ [PR #4](https://github.com/wtg-e2open/INTTRA.appianway/pull/4) merged (`62b07687`) | [event-writer](steps/step-2-event-writer.md) |
| 2 | error-processor | ✅ [PR #5](https://github.com/wtg-e2open/INTTRA.appianway/pull/5) merged (`ff281fa1`) | [error-processor](steps/step-2-error-processor.md) |
| 2 | email-sender | ✅ [PR #6](https://github.com/wtg-e2open/INTTRA.appianway/pull/6) merged (`feca5faf`) | [email-sender](steps/step-2-email-sender.md) |
| 3 | dispatcher | ✅ [PR #7](https://github.com/wtg-e2open/INTTRA.appianway/pull/7) merged (`07b5106f`) | [dispatcher](steps/step-3-dispatcher.md) |
| 3 | splitter | ✅ [PR #8](https://github.com/wtg-e2open/INTTRA.appianway/pull/8) merged (`222d58be`) | [splitter](steps/step-3-splitter.md) |
| 3 | transformer | ✅ [PR #9](https://github.com/wtg-e2open/INTTRA.appianway/pull/9) merged (`bef71a96`) | [transformer](steps/step-3-transformer.md) |
| 3 | ingestor | ✅ [PR #10](https://github.com/wtg-e2open/INTTRA.appianway/pull/10) merged (`e90a355a`) | [ingestor](steps/step-3-ingestor.md) |
| 3 | distributor | ✅ [PR #11](https://github.com/wtg-e2open/INTTRA.appianway/pull/11) merged | [distributor](steps/step-3-distributor.md) |
| 3 | distributor-rest | ✅ [PR #12](https://github.com/wtg-e2open/INTTRA.appianway/pull/12) merged (`36a14ced`) | [distributor-rest](steps/step-3-distributor-rest.md) |
| 4a | watermill-publisher | ✅ [PR #13](https://github.com/wtg-e2open/INTTRA.appianway/pull/13) merged (`9537d1c1`) | [step-4a](steps/step-4a-watermill-publisher.md) |
| 4 | consumer platform, booking / visibility / itv-gps / cargoscreen consumers, billoflading | ⏳ next | [plan](steps/step-4-plan.md) |
| 5 | Delete SDK v1 code and fakes from `shared` | ⏳ | |
| — | Final PR feature → `develop` | ⏳ | |

Every step page lists its commits, build result and review rounds: [all steps](steps/README.md).

<a id="service-recipe"></a>
## Service recipe (what each service PR does)

1. Cut `WI01124532-aws-sdk-upgrade-<module>` from the feature branch tip.
2. **Characterize v1 first:** a golden test, written on the v1 code, of everything the service sends, stores and publishes (expected files written by v1, never regenerated), plus unit characterization of edge cases.
3. **Red/green pairs:** task on `QueueMessage<String>`; parts off SDK v1 types; the service on `CloudServicesModule` (boundary test, functional tests on the cloud fakes, production-wiring test); logger lines (cloud-sdk WARN, `ManagedCloudResource` INFO).
4. **Known defects** ([A12](actions.md#a12)): one disabled test per existing defect, checked both ways (fails today, passes with the fix).
5. Full reactor build in the build worktree ([commands: build worktree](commands/build-worktree.md#s9-5)); counts unchanged except the module.
6. **Independent pre-review** (`code-review` skill, high); check each point against the code.
7. PR doc in `docs/redesign/pr-details/`: Part 1 for GitHub (no tracker IDs), Part 2 review guide, Part 3 walkthrough with parse-checked Mermaid diagrams, Part 4 command log. Then push and `gh pr create`.

## Labels

| Label | Meaning | Where |
|---|---|---|
| A# | Pending action or follow-up | [actions](actions.md) (open), [closed items](closed-items.md#closed-actions) |
| F# | Finding: something found during development | [findings](findings.md), [closed items](closed-items.md#closed-findings) |
| D# / DR# | Decision / full decision record of a question asked | [decisions](decisions.md), [superseded](closed-items.md#closed-decisions) |
| G# | Local guard or tooling (hook, build flag, worktree) | [rules: local guards](rules.md#local-guards) |
| U# | Ask to mercury-services-commons | [plan](plan.md#upstream-commons-asks); full spec: [commons upgrade specs](../redesign/2026-11-11-sdk-commons-upgrade-specs.md) |
| C# | Wire / storage / configuration contract of the `shared` design | [shared design page](../redesign/2026-10-30-apway-WI01124532-shared.md) |

Writing rule for this tracker: never a bare ID. Write the linked ID and a few words, for example "[A27](actions.md#a27) INT shutdown check".

## Document map

**Tracker pages** (this folder)

| Page | What it contains | Read when |
|---|---|---|
| [actions.md](actions.md) | Open actions: index, then one block each (owner, needed by, source, status) | An action comes up, or planning |
| [findings.md](findings.md) | Findings: index, then one block each (finding, effect) | A finding comes up |
| [runtime/](runtime/README.md) | One page per service for the local runs against QA: build, configuration, run commands, detailed test logs; plus [runtime/aws/](runtime/aws/README.md), every AWS CLI command used, explained | Running or reviewing a runtime test |
| [runtime-verification.md](runtime-verification.md) | Plan to verify the migrated services on INT: environment choice, safety rules, phases, scenarios per service, shutdown check, what is needed from Arijit | Preparing or running INT checks |
| [known-defects.md](known-defects.md) | Every existing defect found so far: summary, QA table (what you see, how to observe in QA), technical and functional detail, code path, fix; which services share the duplicate-token defect | Telling QA, or deciding which defects to fix |
| [decisions.md](decisions.md) | Decisions D1–D42 with reasons; decision records DR-1 to DR-4 | Before changing something already decided |
| [closed-items.md](closed-items.md) | Done or dropped actions, closed findings, superseded decisions, full text | A link points there |
| [rules.md](rules.md) | Working rules (branches, WI prefix, TDD, naming, staging, build gate) and local guards G1–G4 | Before committing or naming |
| [plan.md](plan.md) | Build order, compatibility and performance rules, commons asks | Choosing the next step |
| [steps/](steps/README.md) | One page per step or service: commits, builds, reviews | Reviewing or resuming a step |
| [commands/](commands/README.md) | git, Maven, build worktree, GitHub CLI, local run, grep/curl: one page per tool | Running builds, branches, counts, PRs, local runs |
| [howto/](howto/README.md) | Learning walkthroughs and command logs (rulesets, commit hook, commons publish check, shells) | Learning or repeating a procedure |
| [cloud-sdk-facts.md](cloud-sdk-facts.md) | cloud-sdk 1.0.38 facts from the step-1c research | Questions about cloud-sdk internals |
| [history/](history/README.md) | Earlier resume notes, one per session, with a one-line index | Looking up what was decided or done on a date |

**Other documents**

| Document | What it contains | Read when |
|---|---|---|
| [Program design](../redesign/2026-10-30-apway-WI01124532-program.md) | Scope, waves, release plan of the whole upgrade | Big picture |
| Design pages `docs/redesign/2026-10-30-apway-WI01124532-<module>.md` ([shared](../redesign/2026-10-30-apway-WI01124532-shared.md), [dispatcher](../redesign/2026-10-30-apway-WI01124532-dispatcher.md), [splitter](../redesign/2026-10-30-apway-WI01124532-splitter.md), …) | Per-module design: requirements, components, compatibility, test plan, open issues | Starting a module |
| [Review summary](../redesign/2026-10-30-apway-WI01124532-review-summary.md) | Why `shared` is re-based on commons; existing-defects list (§4, see [A12](actions.md#a12)); design-page change tracker (§9, see [A21](actions.md#a21)) | Questions on the design rationale or defects policy |
| [Branch and update plan](../2026-10-30-apway-design-update-plan.md) | Branch flow (§9.5): sub-branches, merge commits, final PR | Branching questions |
| [Commons upgrade specs](../redesign/2026-11-11-sdk-commons-upgrade-specs.md) | U1–U14 asks to commons with decisions | A commons ask |
| [GitHub migration](../2026-11-16-apway-github-migration.md) | Bitbucket → GitHub cut-over steps and the branch rename | Remotes, rulesets |
| PR descriptions `docs/redesign/pr-details/` ([1a](../redesign/pr-details/2026-10-31-apway-pr-1a-pom-description.md), [1b](../redesign/pr-details/2026-10-31-apway-pr-1b-shared-config-description.md), [1c](../redesign/pr-details/2026-10-31-apway-pr-1c-shared-runtime-description.md), [1d](../redesign/pr-details/2026-11-17-apway-pr-1d-shared-adapters-description.md), [1e](../redesign/pr-details/2026-11-17-apway-pr-1e-functional-testing-description.md), [event-writer](../redesign/pr-details/2026-11-18-apway-pr-2-event-writer-description.md), [error-processor](../redesign/pr-details/2026-11-18-apway-pr-2-error-processor-description.md), [email-sender](../redesign/pr-details/2026-11-19-apway-pr-2-email-sender-description.md), [dispatcher](../redesign/pr-details/2026-11-19-apway-pr-3-dispatcher-description.md)) | Per PR: Part 1 GitHub text, Part 2 review guide, Part 3 walkthrough, Part 4 command log | Reviewing or answering a PR |
| commons sources `C:\Users\arijit.kundu\projects\mercury-services-commons` (branch `feature/ION-12310-commons-cloudsdk-refactoring`, `aa52175` = 1.0.39-SNAPSHOT) | cloud-sdk-api / cloud-sdk-aws code; commons progress log `cloud-sdk-api/docs/2026-11-12-sdk-commons-changes-for-apway.md`; review description `cloud-sdk-api/docs/2026-11-16-sdk-commons-upgrades-apway-review-desc.md` | Checking cloud-sdk behaviour |
| Older ION-12317 documents (`docs/2026-07-2x-*`, root `2026-06-30-*`, module `docs/`) | The earlier design round, superseded by the WI01124532 redesign | Rarely; history only |
| Backups `C:\Users\arijit.kundu\backups\` (`2026-11-12`, `2026-11-19-tracker`) | Branch bundles and doc tarballs; the progress doc before this split | Recovery |

The old single progress document is kept as a pointer at `docs/redesign/2026-10-31-apway-aws-upgrade-dev-progress.md`. Its full text before the split is in the backup.

## Session end

Replace **Now** and **Next steps** above. Copy the old ones into a new `history/<date>.md`, and add one line to the [history index](history/README.md).
