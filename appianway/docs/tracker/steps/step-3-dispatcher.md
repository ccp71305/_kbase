# Step 3 — dispatcher (`WI01124532-aws-sdk-upgrade-dispatcher`)

← [Tracker home](../README.md) · [All steps](README.md)


Cut 2026-11-19 from the feature branch at `feca5faf` (after PR #6). Design page: `docs/redesign/2026-10-30-apway-WI01124532-dispatcher.md`. PR description: `pr-details/2026-11-19-apway-pr-3-dispatcher-description.md` (Part 1 GitHub, Part 2 review guide, Part 3 walkthrough with 4 validated Mermaid diagrams, Part 4 command log). dispatcher ran 15 tests; it now runs 50, 3 disabled. No `shared` or functional-testing change.

| # | Commit | Type | Change |
|---|---|---|---|
| 1 | `ecc48acc` test: characterize what dispatcher sends, stores and publishes | test | `DispatcherWireCompatibilityTest` (5, design test 1) on v1: default route, route by file type with an encoded key, booking bridge, empty file, ignored file. `wire/*.expected.txt` written by v1 |
| 2 | `4b5429e2` test: characterize the parser and the zip | test | `S3EventParserTest` 5 → 11, `ZipPreprocessorTest` 2 → 6 (design tests 2, 3), JUnit 5, green on v1 |
| 3–4 | `5a443e67` / `dbb6712a` task and preprocessors on `QueueMessage` | red / green | `DispatcherTaskTest` 4 → 10 (design test 4), `IgnorePreprocessorTest` 1 → 3; `MessageQueueClient` ([D27](../decisions.md#d27)) |
| 5–6 | `6e32e704` / `421a1d1c` parser and zip without SDK v1 types | red / green | Boundary test on `services` + `preprocessor`, no joda; parser no-key case. [D40](../decisions.md#d40) |
| 7–8 | `0ddc55c7` / `2ad5bab9` the service on `CloudServicesModule` | red / green | [D39](../decisions.md#d39). Functional tests on the cloud fakes (+ zip, retry to DLQ, health checks), golden on the fakes, `ExternalServicesModuleWiringTest`. [F22](../findings.md#f22) |
| 9–10 | `2d9c0d6b` / `d5d01887` loggers | red / green | cloud-sdk WARN, `ManagedCloudResource` INFO ([A27](../actions.md#a27)) |
| 11 | `e479822e` known defects | test | [A12](../actions.md#a12): [F18](../findings.md#f18), [F19](../findings.md#f19), [F20](../findings.md#f20), each verified both ways |
| 12 | `b4b8f4b4` refactor | refactor | Pre-review: [D41](../decisions.md#d41), parser javadoc |
| 13 | `f3cb0a3e` build | build | [D42](../decisions.md#d42) |
| 14 | `07596e24` refactor | refactor | joda comment |

Pre-review (`code-review` skill, high): 10 points, outcomes in the PR doc Part 2. New finding [F21](../findings.md#f21) (cloud-sdk logs the health probe's missing key at ERROR).

**Full reactor build of `07596e24`:** green in 14:29 min, all 26 build units; dispatcher 50 (3 skipped), every other count unchanged (shared 1837, functional-testing 48, email-sender 25, error-processor 17, event-writer 19, transformer 665 …).

**Raised as [PR #7](https://github.com/wtg-e2open/INTTRA.appianway/pull/7)** (2026-11-19, mergeStateStatus CLEAN).

**Copilot review 1 (2026-11-19):** no inline comments, "No open issues", banner "Needs a closer look" asking for INT checks (real S3 metadata, zip-generated notifications, shutdown redelivery). Answered with one PR comment ([issuecomment-7015303726](https://github.com/wtg-e2open/INTTRA.appianway/pull/7#issuecomment-7015303726)), approved by Arijit. The PR Next Steps gained the metadata and zip-notification INT check (PR body updated). Shutdown: [A27](../actions.md#a27).

Decisions 2026-11-19: [F21](../findings.md#f21) becomes commons ask U15 (low). The three dispatcher defects ([F18](../findings.md#f18), [F19](../findings.md#f19), [F20](../findings.md#f20)) were confirmed on `develop` `0448d362`, before this work.

**Merged 2026-11-19 17:34 UTC as `07b5106f`.** The feature tree equals the built head `07596e24` (empty diff), so no rebuild was needed. GitHub deleted the remote branch; the local branch was deleted (`git branch -d`) and the local feature branch fast-forwarded.
