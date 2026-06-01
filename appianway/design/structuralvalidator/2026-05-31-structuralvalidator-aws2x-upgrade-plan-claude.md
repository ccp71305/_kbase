# `structuralvalidator` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.structuralvalidator:structuralvalidator:1.0` · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line referenced: **`1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, Jackson **2.21.0**).
> References the **MASTER**: [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) (esp. §0, §10, §11) and [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md).

---

## 0. What this document changes vs. the Copilot plan (critical review)

| Copilot position | Evidence (this review) | This plan |
|---|---|---|
| "No AWS SDK v1 surface; a workspace grep for `com.amazonaws` returns no matches." | Confirmed in **source**: `grep com.amazonaws` over [`structuralvalidator/src`](../src) (main + test): **0 matches**. The module is a pure XSD/schema-check library returning `StructuralValidationResult` ([beans from schema-beans](../../schema-beans)). | **Agree on source.** |
| "Maven changes: none in this module's `pom.xml` for AWS." | **Incorrect.** [`pom.xml:54-58`](../pom.xml) declares a **direct, compile-scope `com.amazonaws:aws-java-sdk-sqs:1.12.720`** dependency — an **orphan**: no `src` class imports it, and the only test-time AWS reach is via the `functional-testing` (test scope) dep. | **Finding: remove the orphan `aws-java-sdk-sqs` dependency** as part of the program's v1 purge. Behavior-neutral (unused). |
| "If it uses `functional-testing` fakes (unlikely for a pure XSD lib)…" | Confirmed it **does** depend on `functional-testing:1.0` (test scope) ([pom.xml:70-75](../pom.xml)), but its tests ([`TestSupport`](../src/test/java/com/inttra/mercury/structuralvalidator/common/TestSupport.java) + the `*RulesetProviderTest`/`*StructuralValidatorTest`) use **only Jackson/Guava/IOUtils**, not the AWS fakes. So the `functional-testing` rework cannot break structuralvalidator's tests. | **Lockstep with `functional-testing` is a compile-classpath concern only**, not a test-behavior one. |
| Silent on test stack | Already **JUnit 5 (Jupiter) 5.10.1 + Mockito 5.11.0** ([pom.xml:23-24](../pom.xml)) — ahead of the program; **no Vintage needed**. | Noted: no JUnit migration required here. |

Net: still **no AWS source migration**, but this plan surfaces the **orphan `aws-java-sdk-sqs` dependency** (which the Copilot draft denied existed) and confirms the `functional-testing`/`shared` couplings are build-classpath only.

## 1. Executive summary
`structuralvalidator` is a **library embedded in `transformer`**: it runs EDIFACT/ANSI structural (XSD/ruleset/occurrence) checks and produces a `StructuralValidationResult` (JAXB beans from `schema-beans`). It has **no AWS source usage**. Its `pom.xml` carries an **unused direct `aws-java-sdk-sqs:1.12.720`** dependency and a **test-scope `functional-testing`** dependency. Under Option B it needs **no source change**; the actions are (a) drop the orphan v1 SQS dependency, (b) rebuild against the migrated `shared`/`functional-testing` (transitive only), (c) align to DW5/Jackson 2.21.0 via the parent BOM. Recommendation: **Option B baseline = remove orphan v1 dep + build alignment.**

## 2. Current state — AWS v1 inventory
**No AWS source surface.** `grep com.amazonaws` over `src/main` and `src/test`: **0 matches**.

Dependency-level AWS exposure (the only exposure), from [`pom.xml`](../pom.xml):
- **`com.amazonaws:aws-java-sdk-sqs:1.12.720`** (compile, lines 54-58) — **orphan; no source uses it.**
- `com.inttra.mercury.shared:mercury-shared:1.0` (compile) — pulls `shared`'s AWS classes transitively, **none referenced** by this module.
- `com.inttra.mercury.test:functional-testing:1.0` (test) — the in-memory fakes; **not referenced** by this module's tests (verified: [`TestSupport`](../src/test/java/com/inttra/mercury/structuralvalidator/common/TestSupport.java) uses Jackson/Guava/IOUtils only).
- `com.inttra.mercury.schema-beans:schema-beans:1.0` (compile), `dropwizard-core 4.0.16`, Guice 7, Guava, GSON. Test stack: **JUnit 5.10.1 + Mockito 5.11.0 + AssertJ 3.24.2** (already on Jupiter).

## 3. Findings
- Zero AWS source coupling; the validator operates purely on parsed messages + XSD rulesets.
- The direct `aws-java-sdk-sqs:1.12.720` dependency is **dead weight** — almost certainly copied from a service POM template. It contributes v1 classes to the classpath that nothing uses; removing it is part of the program's "remove v1 SDK" hygiene and is behavior-neutral here.
- `dropwizard-core 4.0.16` is declared but the module is a library with no `Application`/`Configuration`; under Option B it inherits DW5 from the parent BOM with no source impact.
- Test compile depends on `functional-testing` (test scope) and `mercury-shared`; both migrate ahead of `transformer`. Because structuralvalidator's tests do not touch the fakes or any AWS type, the **lockstep is purely "must compile against the migrated artifacts"**, not behavioral.

## 4. Option A — keep `shared`/DW4 (program-wide fallback)
No source effect. Action reduces to dropping the orphan v1 SQS dep and rebuilding against `shared`/`functional-testing` (DW4). Rebuild-only otherwise.

## 5. Option B — adopt commons + cloud-sdk on DW5 (directed default)
No source effect. Actions: (a) **remove `aws-java-sdk-sqs:1.12.720`** (unused); (b) inherit DW5/Jackson 2.21.0 from the parent BOM; (c) rebuild against the migrated `shared` (now cloud-sdk-backed) and `functional-testing` (now in-memory cloud-sdk-api fakes). No cloud-sdk dependency is added directly.

## 6. Comparison
| Criterion | Option A | Option B |
|---|---|---|
| Off AWS v1 | drop orphan SQS dep | drop orphan SQS dep |
| Source change | none | none |
| Build action | remove orphan dep + rebuild (DW4) | remove orphan dep + DW5/BOM align + rebuild |
| Impact on mercury-services | none | none |
| cloud-sdk change | none | none |

## 7. Recommendation
**Option B baseline = remove the orphan v1 `aws-java-sdk-sqs` dependency + build alignment.** No source change. Action items: (a) delete [`pom.xml:54-58`](../pom.xml) (`aws-java-sdk-sqs`); (b) rebuild against migrated `shared`/`functional-testing`; (c) inherit DW5/Jackson 2.21.0 via parent BOM. Effort: **negligible.** No cloud-sdk gap.

## 8. Peer review note
Self-review corrects the Copilot draft on one concrete point: the module's `pom.xml` **does** declare a direct AWS v1 dependency (`aws-java-sdk-sqs:1.12.720`) — it is orphaned, not absent. Source-wise the Copilot conclusion (no AWS code) holds. Also confirmed: tests are already on JUnit 5 (no Vintage), and the `functional-testing` dependency, while present, is not exercised by these tests.

## 9. Open questions / sequencing
- **Compile lockstep:** rebuild **after** `shared` and `functional-testing` migrate (their artifacts must compile), and before/with `transformer`. No behavioral dependency on the fakes.
- Build after `schema-beans` (its JAXB beans are the validator's return type).
- Open question: is the orphan `aws-java-sdk-sqs` dep safe to remove immediately (independently of the migration)? (Yes — unused; could be removed now as pure hygiene.)

## 10. Configuration changes
**N/A** — library, no `Application`/YAML/runtime config of its own. (Master config model: [`shared` plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md).)

## 11. cloud-sdk-api / cloud-sdk-aws / commons change list
**NONE.** This module consumes no cloud-sdk artifact directly and proposes no additive change. The program-wide only required additive cloud-sdk change is **S-G2** (StorageClient metadata overloads) — see [`shared` plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) — and it does not touch this module.
