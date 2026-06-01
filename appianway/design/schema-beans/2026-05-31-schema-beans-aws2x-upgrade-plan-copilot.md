# `schema-beans` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** None — no AWS surface (JAXB beans only); build/transitive impact only. Inherits the Dropwizard 5 / commons baseline.
> Sections below are retained as the Option-A fallback reference.

> Module: `schema-beans` · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
`schema-beans` is a **pure JAXB-beans library** (generated from `StructuralValidationResult.xsd`, consumed by `structuralvalidator`). A workspace grep for `com.amazonaws` returns **no matches** in this module. It has **no AWS SDK v1 surface**.

## 2. Impact of the migration
- **Direct code changes:** none.
- **Maven changes:** none in this module's own `pom.xml` (it does not declare AWS deps).
- **Transitive/build impact:** none — it does not depend on `shared`.
- **Test impact:** none.

## 3. Options (A vs B)
Both options are documented in full in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8. For `schema-beans` the choice is **irrelevant**: with no AWS surface and no dependency on `shared`/`commons`, neither option touches this module. If the program adopts Option B (commons/Dropwizard 5) repo-wide, `schema-beans` still needs no change because it pulls in no Dropwizard.

## 4. Recommendation
**No action required.** Migrate when convenient as a no-op; rebuild under the aggregator to confirm it still compiles after `shared` changes. Effort: **None.**

## 5. Peer review
See §8 below.

## 8. Peer review outcome
Peer-reviewed as part of the no-AWS module batch (Explore subagent). Confirmed: no `com.amazonaws` usage; no `shared` dependency; no Dropwizard. Reviewer note: keep a one-line entry in the program rollout checklist so it is explicitly verified (rebuild only), not silently skipped. No corrections needed.

## 9. Sequencing
No ordering constraint. Verify with a clean aggregator build after `shared` migrates.
