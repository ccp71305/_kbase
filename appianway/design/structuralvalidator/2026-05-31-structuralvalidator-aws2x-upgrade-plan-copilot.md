# `structuralvalidator` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** None directly — embedded validation library with no AWS client usage; inherits shared's Option B baseline and the G6 config-composition transitively.
> Sections below are retained as the Option-A fallback reference.

> Module: `structuralvalidator` (library embedded in `transformer`) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
`structuralvalidator` is a **library** (no `main`) performing XSD/schema checks and returning `StructuralValidationResult` (from `schema-beans`). A workspace grep for `com.amazonaws` returns **no matches**. It has **no AWS SDK v1 surface**.

## 2. Impact of the migration
- **Direct code changes:** none.
- **Maven changes:** none in this module's `pom.xml` for AWS.
- **Transitive impact:** verify whether it depends on `shared`. If it does, it inherits `shared`'s recompiled (v2-backed) classes but uses none of the AWS-touching ones, so no source change is required — only a rebuild.
- **Test impact:** none directly; if it uses `functional-testing` fakes (unlikely for a pure XSD lib), align with the `functional-testing` rework.

## 3. Options (A vs B)
Documented in full in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8. For `structuralvalidator` the choice is immaterial to source; under Option A it rebuilds unchanged. Under Option B (Dropwizard 5) it still has no Dropwizard/AWS surface of its own.

## 4. Recommendation
**No action required** beyond a rebuild to confirm compatibility. Effort: **None.**

## 5. Peer review
See §8.

## 8. Peer review outcome
Peer-reviewed in the no-AWS batch (Explore subagent). Confirmed no `com.amazonaws` usage. Reviewer note: confirm at build time whether `structuralvalidator` declares a `shared` dependency; if yes, list it as a "rebuild-only" consumer in the rollout checklist. No corrections needed.

## 9. Sequencing
Rebuild after `shared` (if it depends on `shared`) and after `schema-beans`. No code-ordering constraint.
