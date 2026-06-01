# `schema-beans` — AWS SDK v2 (cloud-sdk) Upgrade Plan (claude)

> Module: `com.inttra.mercury.schema-beans:schema-beans:1.0` · Date: 2026-05-31 · Author: Claude (Opus 4.8)
> Status: **Planning / design only — no production code or `pom.xml` changes made.**
> cloud-sdk / commons line referenced: **`1.0.26-SNAPSHOT`** (Dropwizard **5.0.1**, Jackson **2.21.0**).
> References the **MASTER**: [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) (esp. §0, §10, §11) and [`shared` DESIGN](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN-claude.md).

---

## 0. What this document changes vs. the Copilot plan (critical review)

| Copilot position | Evidence (this review) | This plan |
|---|---|---|
| "No AWS surface; no `shared` dependency; no Dropwizard." | Confirmed: [`pom.xml`](../pom.xml) has **no `com.amazonaws` and no `mercury-shared`/`commons` dependency**; module has **no `src/`** at all — it is pure JAXB generated from [`xsd/structuralValidationResult/StructuralValidationResult.xsd`](../xsd/structuralValidationResult/StructuralValidationResult.xsd) via `jaxb2-maven-plugin`. | **Agree — nothing to migrate.** |
| "Migrate when convenient as a no-op; rebuild to confirm." | Correct, but the Copilot draft **understates the one real exposure**: the module pins `jackson-databind:2.10.0` ([pom.xml:41-44](../pom.xml)) and JAXB `4.0.x`. When the parent line moves to DW5/Jackson **2.21.0**, version skew on the consumer classpath (`structuralvalidator`→`transformer`) is the only thing to verify. | **Build/BOM alignment is the action**, not "nothing". Verify JAXB 4 + Jackson 2.21 compatibility on the assembled classpath. |

Net: still **no AWS migration**, but this plan names the concrete build-alignment check the Copilot draft glossed over.

## 1. Executive summary

`schema-beans` generates the `StructuralValidationResult` JAXB beans (package `com.inttra.mercury.schemas.StructuralValidationResult`) consumed by `structuralvalidator` → `transformer`. It has **no AWS code, no `shared`/`commons` dependency, and no Dropwizard**. Under the program's Option B it requires **no source change and no AWS dependency change** — only confirmation that its pinned JAXB/Jackson versions stay compatible once the platform converges on Dropwizard 5 / Jackson 2.21.0. Recommendation: **Option B baseline = build/BOM alignment only.**

## 2. Current state — AWS v1 inventory

**None — no AWS surface.** No `src/` directory; `grep com.amazonaws` over the module: **0 matches**. Dependencies ([`pom.xml`](../pom.xml)): `jakarta.xml.bind-api 4.0.2`, `jaxb-core/jaxb-impl 4.0.5`, `javax.activation-api 1.2.0`, `jackson-databind 2.10.0`. Build: `jaxb2-maven-plugin 3.2.0` `xjc` goal over one XSD. Java 17.

## 3. Findings
- Pure generated-bean library; zero AWS, zero Dropwizard, zero `shared`/`commons`.
- Only coupling to the program is **transitive version alignment**: the module independently pins `jackson-databind 2.10.0` (older than the rest of appianway, e.g. `structuralvalidator` at 2.19.2). DW5 brings Jackson **2.21.0**; the assembled `transformer` uber-jar must resolve a single Jackson version.
- JAXB on Jakarta namespace (`jakarta.xml.bind`) already — compatible with the DW5/Jakarta EE 10 line; no `javax`→`jakarta` migration needed.

## 4. Option A — keep `shared`/DW4 (program-wide fallback)
No effect on this module: it does not consume `shared`/Dropwizard. Rebuild-only.

## 5. Option B — adopt commons + cloud-sdk on DW5 (directed default)
No effect on this module's source. The only Option B action is **build/BOM alignment**: drop/relax the local `jackson-databind 2.10.0` pin so the module inherits the program Jackson **2.21.0** (or confirm the explicit pin is overridden by the consumer's BOM), and confirm JAXB `4.0.x` + Jackson 2.21 coexist on the `transformer` classpath. No cloud-sdk dependency is added.

## 6. Comparison
| Criterion | Option A | Option B |
|---|---|---|
| Off AWS v1 | N/A (no AWS) | N/A (no AWS) |
| Source change | none | none |
| Build action | rebuild-only | BOM/Jackson alignment + rebuild |
| Impact on mercury-services | none | none |
| cloud-sdk change | none | none |

## 7. Recommendation
**Option B baseline = build/BOM alignment only.** No source, no AWS, no cloud-sdk dependency. Action items: (a) relax/remove the local `jackson-databind 2.10.0` pin so the program Jackson 2.21.0 governs; (b) clean aggregator rebuild after `shared` migrates to confirm `transformer` still assembles with JAXB 4 + Jackson 2.21. Effort: **negligible.**

## 8. Peer review note
Self-review confirms: no `com.amazonaws`, no `mercury-shared`, no Dropwizard. The Copilot draft's "no action" conclusion is correct on AWS but missed the local Jackson pin (2.10.0) as the single concrete alignment risk — captured here.

## 9. Open questions / sequencing
- No code-ordering constraint. Rebuild under the aggregator **after** `shared`/parent BOM moves to DW5/Jackson 2.21 to confirm classpath resolution.
- Open question: should the local `jackson-databind` pin be removed entirely and inherited from the parent/BOM? (Recommended, to avoid silent version skew.) Decided at parent-BOM time.

## 10. Configuration changes
**N/A** — no runtime, no Dropwizard config. (Master config model: [`shared` plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md).)

## 11. cloud-sdk-api / cloud-sdk-aws / commons change list
**NONE.** This module consumes no cloud-sdk artifact and proposes no additive change. The program-wide only required additive cloud-sdk change is **S-G2** (StorageClient metadata overloads) — see [`shared` plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-claude.md) — and it does not touch this module.
