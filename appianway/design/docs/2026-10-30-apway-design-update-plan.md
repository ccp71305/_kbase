# AppianWay AWS SDK v2 (cloud-sdk) Design-Doc Update — Gap Analysis & Plan

> **Ticket:** ION-12317 · **Date:** 2026-10-30 · **Author:** Arijit Kundu (with Copilot / Claude Opus 4.8; deep audits on Opus 5.5)
> **MCP session:** `a0e9dc68b8f14672`
> **Status:** Rev 5 — one branch `WI01124532-aws-sdk-upgrade`, one release (§9.5); architecture re-based on commons and all review decisions recorded (§9.9); 17 new-template pages under `docs/redesign/` validated and ready for review. **Nothing published yet.**
> **Reading guide:** §1–8 are the Rev 1 gap analysis, kept for history. §9 is current; where anything conflicts, §9.9 wins. Rationale and evidence: `docs/redesign/2026-10-30-apway-WI01124532-review-summary.md`.
> **Work item:** WI01124532 (branches/commits must start with `WI01124532`).

This document answers: *what has changed since the July-2026 ION-12317 design set was published, and how do we update and re-publish the design docs in the new corporate template at a new location?* It is a review deliverable — the per-module rewrites follow after the open decisions below are confirmed.

---

## 1. What was reviewed

| Source | Location | Notes |
|---|---|---|
| **New doc template** | `mercury-services/.github/prompts/designdocs/templates/architecture-template.md` | Mirrors corporate *Design Doc Template* (Confluence page `672934513`, synced 2026-07-29). Plus `_base-confluence-publisher.md`, `confluence-design-doc-generator.md`, `README.md`. |
| **Reference converter** | `mercury-services/convert_design_doc.py` (repo root) | MD → Confluence storage XHTML, with structural self-check. |
| **Current AppianWay design set (old format)** | `appianway/docs/2026-07-22-ION-12317-*.md` (program + 14 modules) + `2026-07-23-appway-awsupgrade-design-summary.md` | Published to Confluence BRM parent `650546306`, program page `672212104`. |
| **Published Confluence program page** | `672212104` (fetched 2026-10-30) | Reflects the July design (targets commons 1.0.27-SNAPSHOT; S-G2/W-G9/X-G7 as *assumed* gaps). |
| **Example new-template pages** | `672213462`, `672221381` | **Pending** — Confluence SSO expired mid-review; fetch on re-auth to confirm exact target parent/location + template rendering. |
| **mercury-services-commons** | `C:\…\mercury-services-commons` @ `1.0.38-SNAPSHOT` (deep audit) | S-G2 / W-G9 / X-G7 status, new capabilities, versions. |
| **appianway code** | `develop` + `feature/ION-12317-apway-aws-upgrade` (deep audit) | Actual migration progress vs design. |

---

## 2. Current-state snapshot (three axes)

### 2.1 Template axis — total structural mismatch
The **old** module docs use a free-form 10-section layout (Overview · Current-vs-Target architecture · AWS touchpoints · Sequence diagram · Configuration · cloud-sdk deps & gaps · Maven · Tests · Rollout · Risks).

The **new** corporate template is a fixed, ordered section set that must not be renamed/reordered/dropped:
Contributors · Summary · Requirements (+ *ext* Jira/Support/Tech-Stack tables) · Assumptions & Open Issues · High Level Design (+ *ext* Architectural Overview / Options / Before-vs-After) · Low Level Design → Server / UI / API Architecture · Configuration (Component/Model/Stack/PS-SI) · Auditing/Logging · Metrics · Installer · Impact on Current Application · Resiliency · Temp-object cleanup · Impact on Tools · Impact on Other Components · Backwards Compatible · New/Upgraded Third-party Jars · Unit Test Plan · **Risks** (red panel) · **Dependencies** (blue panel) · **Pre-Dev Security** (task-list ids `1,2,3,4,5,6,120,124,125,126`) · REQUIRED Documentation Changes · Blocking Issues · Deployment Verification (*ext*) · **Design Review & Approval Matrix** (9 stages).

➡ **Every** design page must be rebuilt into this template. This is the single biggest piece of work.

### 2.2 Commons axis — all assumed gaps are now CLOSED (1.0.27 → 1.0.38-SNAPSHOT)
The July design treated three library enhancements as *"assume added / NOT present yet"*. They are **all implemented** in `1.0.38-SNAPSHOT` and have been since ~1.0.28:

| Gap (design) | Status now | Evidence (mercury-services-commons) |
|---|---|---|
| **S-G2** StorageClient metadata/content-type write + copy-with-REPLACE | ✅ Implemented (commit `44c0d48`, 1.0.28) | `cloud-sdk-api/…/storage/api/StorageClient.java` default `putObject(…,Map,contentType)` (byte[] :42, InputStream :60, File :81), `copyObject(…,replacedMetadata,contentType)` :128; impl `cloud-sdk-aws/…/storage/impl/S3StorageClient.java` (byte[] :462 ct :474; copy REPLACE :1017). Plus `getMetadata` :103. **Caveat:** interface defaults ignore metadata/ct — only `S3StorageClient` honours them. |
| **W-G9.1** Event annotations round-trip | ✅ Fixed (commit `1a683fa`) | `Event.java`: field :65, copy in build :85, `Builder(Event)` copies :214, `setAnnotations` :317. |
| **W-G9.2** Projection / Token constants | ✅ Present | `MetaData.Projection` now **34** constants incl. `DISTRIBUTOR_REST`/`ORIGINAL_IB_WORKSPACE_FILE` (:97-130); `Event.Token` now **18** (:138-155). *(Verify the remaining design-named constants against these ranges during rewrite.)* |
| **X-G7** Email reply-to | ✅ Implemented (commit `0e9a244`) | `MailContent.getReplyTo()` default :22; `MailContentImpl` `@Builder.Default replyTo` :51; `SesEmailServiceImpl.replyToAddresses` :135-137. **Caveat:** reply-to applied only on the no-attachment SES path; MIME/attachment path unconfirmed. |
| **X-G8** ingestor Jest/OpenSearch v1 signer | ✅ Unchanged by design — correct | No cloud-sdk change; keep `vc.inreach` v1 SigV4 + minimal v1 auth jar alongside v2. |
| **C-G6** widen `getConfigTransformer` | ✅ Done (commit `2d6ac42`) | `PropertiesSubstitutionConfigProvider`; `getConfigTransformer` made protected. |

**New capabilities added since 1.0.27** (not in the July design, now available to consume):
- **Classified, AWS-free exception model** (`cloudsdk.exception.CloudSdkException` + domain exceptions messaging/notification/paramstore/storage/email/database; `isRetryable()`/`getOperation()`/`getResource()`). Commit `ae47bb0`, 1.0.33. → Replaces/augments the `RecoverableException` story.
- **Dedicated HTTP clients + timeout-units fix** (`aws.config.AwsHttpDefaults`, `AwsHttpClientWrapper`). 1.0.29–1.0.31.
- **`CloudResource`/`ManagedCloudResource` lifecycle** replacing `AutoCloseable` on clients (commit `85b7875`, 1.0.31). → Affects Guice/Dropwizard managed wiring.
- **DynamoDB enhanced-client repository API** (`database.api.DatabaseRepository`, `EnhancedDynamoRepository`, `@Table/@DynamoDbField/@TTL`, `DynamoDbAdminCommand`). → transformer sequence + watermill offset tables.
- **SQS `DelaySeconds`** on `MessagingClient` (commit `575e434`, 1.0.33).
- **Config command + transform chain** in `commons` (`ConfigProcessingServerCommand`, `ChainingConfigTransformer`, `ParameterStoreConfigTransform`, `TrimConfigCommentsTransform`, `PropertiesSubstitutionConfigProvider`).

### 2.3 AppianWay code axis — migration is Wave-2-deep on a feature branch, nothing on `develop`
- **`develop`:** all 14 apps still on **AWS SDK v1 (1.12.720) + `shared` (`mercury-shared:1.0`)**. No `cloud-sdk`/`commons` dependency anywhere; no `software.amazon.awssdk` import. The `appianway-commons/` folder on `develop` is **leftover build output only** (`target/` jar + classes; **0 git-tracked files**).
- **`feature/ION-12317-apway-aws-upgrade`:** real work exists —
  - *Wave 1:* `appianway-commons` (tracked, with `pom.xml` + `src`) + cloud-sdk `functional-testing` fakes + **event-writer** pilot.
  - *Wave 2:* **distributor-rest + splitter + ingestor** onto cloud-sdk.
  - **Pinned to `mercury.commons.version=1.0.28-SNAPSHOT`** and `appianway.commons.version=1.0` — i.e. it predates commons 1.0.29→1.0.38 (HTTP-client tuning, `CloudResource` lifecycle, exception model, DelaySeconds, config transforms, CVE fixes).
  - Waves 3–5 (dispatcher, distributor, error-processor, email-sender, transformer, watermill-publisher + the 4 consumers) **not started**.
- **Baseline (ION-16098) is in `develop`:** DW 5.0.2 / **Jetty 12.1.9** / **Jackson 2.21.4** / Java 17 / Guice 7. Commons has since moved to **Jetty 12.1.14 / Jackson 2.21.8** — a minor drift to reconcile.
- **Scope growth (ION-14997, PR #69, on `develop`):** a new **watermill consumer-framework** with modules `consumer-framework`, `consumer-commons`, `billoflading/ebl-inbound-consumers`, `registration-inbound-consumers` — **not covered by the 14-module design**; `consumer-commons` and the ebl consumer still use v1/`shared`.

---

## 3. Gap analysis (what must change in the design)

| # | Gap | Severity | What the design currently says | Reality (2026-10-30) | Required doc change |
|---|---|---|---|---|---|
| **G1** | **Template/format** | High | Free-form 10-section module pages | Corporate template mandatory | Rebuild program page + every module page into `architecture-template.md`; run `convert_design_doc.py`. |
| **G2** | **Commons version + closed gaps** | High | Target `1.0.27-SNAPSHOT`; S-G2/W-G9/X-G7 *assumed, not present* | `1.0.38-SNAPSHOT`; all three **implemented** (cite commits/signatures) | Flip gaps from "assume added" → "available"; replace assumption tables with a *consumed-capabilities* table + exact signatures; de-risk the program (libraries are ready). |
| **G3** | **New commons capabilities** | Medium | Not mentioned | Exception model, HTTP-client tuning, `CloudResource` lifecycle, DynamoDB enhanced repo, DelaySeconds, config transforms | Add to HLD/LLD + per-module LLD (error handling, Guice lifecycle, DynamoDB sections). |
| **G4** | **Baseline drift** | Low | Jetty 12.1.9 / Jackson 2.21.4 | Commons on 12.1.14 / 2.21.8 | Note the convergence target; decide whether AppianWay bumps to match commons' managed line. |
| **G5** | **appianway-commons scope** | Medium | "Slim residue only" (concurrency, error handling, health glue, config substitution) — **NOT** networkservices/messaging/SNS publisher/config POJOs | As-built (feature branch) is broader: config POJOs (`S3Config/SNSConfig/SQSConfig`), `NetworkServiceConfig`, `SNSEventPublisher`, `SNSNotification`, `S3ConfigurationProvider`, etc. | **Decision needed** (§4): re-affirm slim intent and trim, or update the design to the as-built boundary. |
| **G6** | **Module scope growth** | Medium | 14 deployable apps | +4 watermill consumer-framework modules (ION-14997) | Add them to the module index + give the new ones their own pages (or fold into watermill). |
| **G7** | **Implementation-progress reality** | Medium | Design-only (nothing built) | Waves 1–2 built on feature branch @ commons 1.0.28 | Either (a) keep docs forward-looking and re-pin to 1.0.38, or (b) add an "as-built vs design" status per module. Re-pin the whole program to **1.0.38-SNAPSHOT** (or the GA coordinate). |
| **G8** | **Confluence location/structure** | Medium | Program page `672212104` + 14 children under BRM `650546306` | New pages go in the **new template at a new location** (parent shown by `672213462`/`672221381`) | Decide parent/space; create fresh pages (don't overwrite the old tree unless asked); link old↔new. |
| **G9** | **Per-module factual refresh** | Medium | Signatures/paths as of July | Exact current class/method/line refs available | Replace "assumed" API shapes with verified `file:line` references from commons 1.0.38. |

---

## 4. Open decisions (need your confirmation before rewriting)

1. **Confluence target location.** Which parent page / space do the new-template docs go under? (Confirm from `672213462` / `672221381` once re-authed.) New pages created fresh, old `672212104` tree left intact and cross-linked — OK?
2. **Program page + 14 module pages, or restructure?** Keep one program landing page + one page per module in the new template, or consolidate? Recommend: keep the 1-program-+-N-modules shape; it maps cleanly onto the template per page.
3. **appianway-commons boundary (G5).** Target the design's "slim residue" or document the as-built broader boundary? This changes the LLD mapping tables materially.
4. **Module scope (G6).** Do the 4 new watermill consumer-framework modules get their own design pages now, or a follow-up? In scope for this update?
5. **Commons pin (G7).** Re-pin the design to `1.0.38-SNAPSHOT` now, or to a specific GA release coordinate? (Feature branch is on 1.0.28.)
6. **Baseline bump (G4).** Converge AppianWay onto commons' Jetty 12.1.14 / Jackson 2.21.8, or hold at 12.1.9 / 2.21.4 for this program?
7. **Model.** Requested Claude Opus 5.5 — used for the deep audits; I (orchestrator) run on Opus 4.8. Confirm whether to also route the doc rewrites through Opus 5.5 subagents.

---

## 5. Recommended approach (phased)

**Phase 0 — Review & confirm (this document).** Deliver gap analysis + approach; resolve §4 decisions. Re-auth Confluence and fetch `672213462`/`672221381` + the 14 old pages to lock the exact target location and confirm template rendering.

**Phase 1 — Program landing page (new template).** Rewrite `2026-07-22-ION-12317-aws-upgrade-program.md` → new template as `docs/2026-10-30-ION-12317-aws-upgrade-program.md`: refreshed governing decisions, commons **1.0.38** consumed-capabilities table (replacing the gap-assumption tables), new-capabilities (exception model / lifecycle / DynamoDB / transforms), reconciled baseline, updated module index incl. watermill-framework, as-built status. Review → publish to the new parent.

**Phase 2 — Per-module pages (new template), in rollout-wave order.** One `.md` per module under `<module>/docs/2026-10-30-design-doc-ION-12317-<module>.md` (generator's convention), mapping the old module content onto the template, with:
- verified commons 1.0.38 client/method references (no "assumed");
- the template's Pre-Dev Security + Approval Matrix + Risks/Dependencies panels;
- "as-built vs design" note where Waves 1–2 already landed (event-writer, distributor-rest, splitter, ingestor).
Review each, then publish under the new program page.

**Phase 3 — New-scope + library modules.** watermill consumer-framework modules (if in scope, §4.4); call out `functional-testing`, `consumer-commons`, `appianway-commons` in each dependent page's Maven/Dependencies section.

**Phase 4 — Publish & verify.** For each: `convert_design_doc.py` (must exit 0) → `confluence_create_page` under the new parent → read back `body.storage` and byte-compare CDATA blocks → record page id/URL in session. Never stage the `.md` files (leave unstaged unless asked).

---

## 6. Per-module work index (rebuild targets)

| # | Module | Wave | Built on feature branch? | Headline (unchanged) | Gaps now resolved |
|---|---|:--:|:--:|---|---|
| — | **program landing page** | — | — | governing decisions, mapping, module index | S-G2/W-G9/X-G7 now available |
| 1 | event-writer | 1 (pilot) | ✅ Wave 1 | application/json audit writes | S-G2, W-G9 |
| 2 | distributor-rest | 2 | ✅ Wave 2 | pure client rebind, S3 read-only | W-G9 |
| 3 | splitter | 2 | ✅ Wave 2 | canonical consumer rebind | W-G9 |
| 4 | ingestor | 2 | ✅ Wave 2 | keep v1 Jest signer (X-G8) | X-G8, W-G9 |
| 5 | dispatcher | 3 | ✗ | local S3-event parser; zip put+metadata | S-G2, W-G9 |
| 6 | distributor | 3 | ✗ | copy-with-replaced-metadata ×2 | S-G2, W-G9 |
| 7 | error-processor | 3 | ✗ | archive put; email fan-out | S-G2, W-G9 |
| 8 | email-sender | 4 | ✗ | SES v2; reply-to | X-G7 |
| 9 | transformer | 4 | ✗ | DynamoDB v2; Contivo | S-G2(ref), W-G9, DynamoDB enhanced |
| 10 | watermill-publisher | 5 | ✗ | AWS-layer rebind; SSM boot creds | — |
| 11 | booking-inbound-consumer | 5 | ✗ | DynamoDB v2 offset; port 8085 | W-G9 |
| 12 | cargoscreen-consumer | 5 | ✗ | DynamoDB v2 offset; S3-only | — |
| 13 | itv-gps-consumer | 5 | ✗ | DynamoDB v2 offset; tenant INTTRA | — |
| 14 | visibility-inbound-consumer | 5 | ✗ | 3 gRPC/3 offsets; 3 SQS + SNS | W-G9 |
| 15+ | **watermill consumer-framework** (ION-14997) | new | n/a | consumer-framework, consumer-commons, ebl/registration inbound | decision §4.4 |

---

## 7. Risks

- **Template fidelity:** section renames/reorders or unescaped XHTML fail Confluence publish — always route through `convert_design_doc.py` (exit 0) and verify `body.storage`.
- **Stale assumptions leaking through:** old docs assert gaps "not present"; every such statement must be flipped and re-verified against 1.0.38 (`file:line`), or the design misleads reviewers.
- **appianway-commons boundary ambiguity (G5):** if the design and the as-built library disagree, implementers get conflicting guidance — resolve §4.3 before Phase 2.
- **Feature branch on 1.0.28:** re-pinning the design to 1.0.38 implies a dependency bump + re-verify for the already-built Waves 1–2.
- **Confluence SSO TTL (~2h):** re-auth (`sso_login.py`) immediately before each publish batch.

---

## 8. Immediate next actions

1. Resolve §4 decisions.
2. Re-auth Confluence; fetch `672213462`, `672221381`, and the 14 old pages; lock target parent/location.
3. Begin Phase 1 (program landing page in new template) → review → publish.
4. Log all findings/decisions in MCP session `a0e9dc68b8f14672`.

---

## 9. Rev 2 — decisions and findings (2026-10-30)

### 9.1 Decisions (from user)

| # | Decision |
|---|---|
| D1 | Work item **WI01124532**. Branch names and commit messages start with `WI01124532`. |
| D2 | New docs: `docs/redesign/2026-10-30-apway-WI01124532-<module>.md` (root `docs/` is gitignored — docs stay local, never staged). |
| D3 | Confluence target: **Draft Design Documents** (BRM, page id `132890668`). Publish only after explicit approval. |
| D4 | Watermill: fold `consumer-commons` + `consumer-framework` (+ framework-based ebl/registration consumers) into one **watermill platform** doc; one short doc per legacy consumer. |
| D5 | Commons pin: **1.0.38-SNAPSHOT**. |
| D6 | **Backward compatibility is paramount** — no data-structure or data-format change (mercury-services consumes these outputs). |
| D7 | Minimal content (security reviewer challenged extra content); Contributors + Approval Matrix rows copied unchanged. |
| D8 | ~~Branch per logical wave~~ **Rev 5:** one branch `WI01124532-aws-sdk-upgrade`, one release (§9.5). The ION-12317 feature branch is not reused (§9.4). |

### 9.2 Example-page calibration (672213462, 672221381)

- Both under Home › Design Documents › 26.X › 26.4 › 26.3.1. Section set = template, Contributors (Author/Implementation/Jira Assignee/Product Owner), Backwards Compatible as Q/A table, Pre-Dev Security with one-line answers.
- **Security reviewer comment (672213462, Kamalesh Bhol, 2026-09-10, open):** queried OWASP scan notes left in the approval matrix — *"why this has been mentioned in the design document in its current form?"* → **Rule: no OWASP/CVE notes or TODOs, no env-specific resource names, no commit hashes/branches in the docs.**

### 9.3 Backward-compatibility audit — verdicts

| Area | Verdict | Design rule |
|---|---|---|
| `MetaData` / `Event` / `Annotations` model | **Identical** — same fields, declaration order, `NON_EMPTY`, Projection/Token values | ~~Use cloud-sdk-api `notification.workflow` types~~ **Rev 4:** keep `shared`'s own `MetaData` / `Event` classes (Tier 3) |
| ObjectMapper | **Different** — cloud `JsonSupport` adds `Jdk8Module`, global `NON_NULL`, unknown-enum→null | **Rev 4:** `shared` `Json` itself for every wire payload (never `JsonSupport`); golden-fixture byte tests |
| S3 `putObject(String)` | **Different header** — v1 sends `text/plain` (verified in 1.12.720 bytecode), cloud sends `text/plain; charset=UTF-8` | **Rev 4:** modules call the `shared` workspace adapter `putObject(String)` (UTF-8, `text/plain`); the adapter owns the cloud-sdk call |
| S3 byte[] put / copy-with-metadata | **Rev 4: different on copy** — v1 adds `application/octet-stream` to a REPLACE copy; SDK 2.x without it stores `binary/octet-stream` | Adapter passes `application/octet-stream` explicitly on copy-with-metadata (`shared` C2) |
| S3 SSE / ACL | Not set by `shared` today | Set nothing (bucket defaults) |
| SQS | `failedAttempts` String attr + DelaySeconds on retry | Preserve exactly |
| SNS | Raw JSON array, no subject/attributes — equivalent | — |
| SES | email-sender has **no attachments**; cloud simple path honours reply-to | Low risk; test From/Reply-To/charset |
| DynamoDB | transformer control-number (`keyId` S, `id` N, `version` N) and `watermill_offset` (`topicName` S, `offset` N, epoch-second N dates) | Identical names/types; custom epoch-second converter; DynamoDB-Local parity tests |
| SSM | Same names, decryption | — |
| ION-15497 | gRPC `maxInboundMessageSize` 50 MB (visibility) — **not** SQS; unaffected | Preserve |
| Earlier design: event-writer `application/json` | **Behaviour change — dropped** | Keep `text/plain` |

**Cross-repo dependency (corrected):** booking-inbound-consumer used `booking:2.1.1.M` and visibility-inbound-consumer `visibility:1.0.M` — both are the **AWS SDK v1 models** (101 / 15 classes reference `com.amazonaws`) and cannot be used. Move to the AWS SDK 2.x models **`booking:3.0.0.M`** and **`visibility:2.0.M`** (dependency-free POMs, 0 v1 references; all 82 imported classes present). Field diff: booking adds `cargoRoRoIndicator`, `cargoBreakBulkIndicator`, `viaExternalLink` (primitive boolean) and `DangerousGoods.variant/variantDescription/applicableReg` (String, null → omitted); visibility adds `TransportationDetail.transportationDetailsPresent` (primitive boolean). Primitive booleans would appear as `false` → ~~Jackson mix-in omits them when false~~ **Rev 4:** `@JsonIgnoreProperties` on the new properties only (omitting every `false` would drop fields in today's output, e.g. `cargoHazardousIndicator`); byte-verified on the fixtures. Models are **vendored** into each consumer's `lib/` (not in the corporate repository). `DynamoDbConfig` replaced by `WatermillDynamoDbConfig`.

### 9.4 Feature-branch reuse

`feature/ION-12317-apway-aws-upgrade` (`deae21e4` wave1, `fc19052d` wave2) is conflict-free against current `develop` but pinned to 1.0.28 and duplicates functionality now in commons 1.0.38 (network services, SNS publisher, config command). ~~Reuse by cherry-pick + adapt~~ **Rev 4: not reused.** Its `appianway-commons` module and duplicated pieces are superseded by the re-based `shared` (§9.9); individual tests or fixtures may be copied where useful. The `application/json` change stays dropped.

### 9.5 Branch plan (from `develop`) — Rev 5: one branch

One branch, `WI01124532-aws-sdk-upgrade`, merged to `develop` once and released together (supersedes the five wave branches and D8). All modules are part of one ETL flow (dispatcher → splitter → transformer → mercury-services → transformer → distributor) and all depend on `shared`, so the v1 code is removed from `shared` in the same release. Wire and storage formats stay identical, so a single service can still be rolled back to its previous build.

| Step | Modules |
|---|---|
| 0 | commons release with U3 (S3 size HEAD), U8–U9 (SES message id, retry strategy) — prerequisite; U7 optional |
| 1 | root pom (commons 1.0.38; Jetty/Jackson/logging pins aligned up to commons), `shared` re-based on commons (Tier 1/2/3), commons config chain, `functional-testing` cloud-sdk fakes |
| 2 | event-writer, error-processor, email-sender |
| 3 | dispatcher, splitter, transformer, distributor, distributor-rest, ingestor |
| 4 | watermill-publisher, watermill platform + consumers (booking 3.0.0.M / visibility 2.0.M models, vendored) |
| 5 | delete the AWS SDK v1 code from `shared` + v1 fakes; ArchUnit boundary test on every module |

**Branch and PR flow (Rev 6).** `WI01124532-aws-sdk-upgrade` is the feature (integration) branch, cut from `develop`. Work happens on short-lived sub-branches cut from it, each merged back by its own PR, so a reviewer sees one module or one step at a time:

| Step | Sub-branch → PR into `WI01124532-aws-sdk-upgrade` | Notes |
|---|---|---|
| 1a | `WI01124532-aws-sdk-upgrade-pom` | root pom: commons 1.0.38, platform pins aligned; `dependency:tree` diff in the PR |
| 1b | `WI01124532-aws-sdk-upgrade-shared-config` | commons config chain + golden config test |
| 1c | `WI01124532-aws-sdk-upgrade-shared-runtime` | back-pressure listener, client profile (incl. metrics helper), exception mapping; v1 code still present so unmigrated modules compile |
| 1d | `WI01124532-aws-sdk-upgrade-shared-adapters` | Tier 2 workspace / SQS sender / SNS publisher adapters, health checks, v2 Guice module |
| 1e | `WI01124532-aws-sdk-upgrade-functional-testing` | cloud-sdk fakes, ArchUnit boundary test |
| 2–4 | `WI01124532-aws-sdk-upgrade-<module>` | one PR per module (15), after 1a–1e; independent of each other, so they can be reviewed in parallel |
| 5 | `WI01124532-aws-sdk-upgrade-shared-v1-removal` | delete v1 code and fakes from `shared` after every module PR is merged |

Rules: every sub-branch PR builds the full reactor (`mvn clean verify`, golden and ArchUnit tests); merge sub-branch PRs with a merge commit (no squash) so `git log --first-parent WI01124532-aws-sdk-upgrade` lists one entry per reviewed PR; rebase the feature branch onto `develop` as needed, with `git rebase --rebase-merges develop` (a plain rebase flattens the sub-PR merge commits) and `git push --force-with-lease` (branch permissions must allow force-push on the feature branch only). Rebase only when no sub-branch PR is open, or announce it: each open sub-branch is then moved with `git rebase --onto <new feature tip> <old feature tip> <sub-branch>`. Re-run the full reactor build after every rebase; INT deployment and the end-to-end flow test run from the feature branch; the final PR `WI01124532-aws-sdk-upgrade` → `develop` is an integration review only (every change already reviewed), merged once.

The earlier `WI01124532-wave0-foundation` branch has no commits and is replaced.

### 9.6 Redesign doc set (`docs/redesign/`)

program · shared (foundation incl. functional-testing; replaces the earlier appianway-commons draft) · event-writer · error-processor · email-sender · dispatcher · splitter · transformer · distributor · distributor-rest · ingestor · watermill-publisher · watermill (platform) · booking-inbound-consumer · visibility-inbound-consumer · cargoscreen-consumer · itv-gps-consumer — 17 pages, all with the identical 25-section template layout, each validated with `convert_design_doc.py` (`self-check: OK`). Plus `review-summary` (local working doc, **not published**).

### 9.8 Rev 3 — foundation = upgrade `shared` in place (supersedes `appianway-commons`) — **superseded by §9.9**

User asked "should we not address shared first?". Decision (taken autonomously, user to confirm on review): **no new `appianway-commons` module**. `mercury-shared` (same coordinates) gets additive cloud-sdk (AWS SDK 2.x) adapters in wave 0; services switch wave by wave; v1 wrappers are `@Deprecated` and deleted in wave 4 (`shared` stays). Rationale: single chokepoint, no package churn for task/dispatcher/ErrorHandler/`MetaData`/`Event`/`EventLogger`/`Json`, wire format preserved by construction (shared keeps its own `MetaData`/`Event` classes).

**Finding:** `cloud-sdk-aws` 1.0.38 depends (compile) on `aws-java-sdk-core/-sqs/-sns/-s3` 1.12.730 (SQS extended client, Jest). So "no AWS SDK v1 jar on the classpath" is not achievable; requirement becomes **"no `com.amazonaws` API usage in AppianWay sources"**; v1 jars stay transitive until removed upstream.

Wave branches superseded by one branch (§9.5).

### 9.9 Rev 4 — `shared` re-based on commons; review decisions (2026-10-30)

**Architecture (replaces §9.8):** `shared` keeps its coordinates and packages but becomes a thin AppianWay layer on top of commons / cloud-sdk 1.0.38, so CVE fixes, dependency versions and config loading come from commons as in mercury-services.

| Tier | What | Where |
|---|---|---|
| 1 | AWS clients and HTTP tuning, `AwsRetryCondition`, Parameter Store, DynamoDB, SES, `CloudSdkException`, `ManagedCloudResource`, config chain (`PropertiesSubstitutionConfigProvider` → `TrimConfigCommentsTransform` → `ParameterStoreConfigTransform`, CLI `run (yaml) (properties...)` kept), dependency versions | commons directly; `shared` v1 equivalents deprecated, deleted in the same release |
| 2 | Workspace S3, SQS sender, back-pressure SQS listener, SNS publisher, health checks, S3 config source, exception mapping | Thin `shared` adapters (wire contract C1–C9) |
| 3 | `MetaData` / `Event` / `Json`, task / dispatcher / `ErrorHandler`, network services, external-call wrapper | `shared`, unchanged |

**Decisions:**

| # | Topic | Decision |
|---|---|---|
| R1 | Architecture | Re-base as above |
| R2 | Upstream commons changes U1–U10 | Fallbacks first (interface only); upstream changes planned on the branch. U3 and U8–U9 must be in a commons release first; U7 optional |
| R3 | Hystrix / guava-retrying | Kept; replacement is a separate follow-up design |
| R4 | Existing defects found in review | Not fixed. Each module adds one test per defect asserting the correct behaviour, committed disabled (`@Ignore` / `@Disabled` + defect reference). distributor-rest token sharing raised as a separate security ticket |
| R5 | `booking:3.0.0.M`, `visibility:2.0.M` | Vendored into each consumer's `lib/` |
| R6 | Modules on SDK v1 client defaults | Keep current values via client-profile overrides, each with a code comment |
| R7 | `cerberus`, `mftdispatcher`, `validator` | Out of scope (first two retired; validator not in the reactor). `fulfiller`, `router`, `load-testing` not in use; `gen2-parser` unchanged |
| R8 | Transformer | Kept as today within R10: consistent `findById` of the same item (scan and "more than one item" error return with U6); SDK CloudWatch metrics, same namespace, once U7 is released |
| R9 | watermill-publisher `task/Test.java` | Replaced by a v2 load harness in test sources, resource names as arguments |
| R10 | AWS SDK boundary | No AWS SDK client built or called in AppianWay code; only `cloud-sdk-api` interfaces, created by `cloud-sdk-aws` factories in Guice wiring. Allowed SDK types as in mercury-services (config `RetryStrategy` in the `shared` client-profile helper, DynamoDB entity annotations, `ConditionalCheckFailedException` catch, ingestor's v1 signer credentials). Enforced by an ArchUnit test |
| R11 | Story ID on every page | `WI01124532 - AWS SDK Upgrade - Appianway - AWS SDK Upgrade` |
| R12 | Release | One branch `WI01124532-aws-sdk-upgrade`, one release, v1 removed from `shared` in the same release; per-service rollback kept by identical formats (§9.5) |
| R13 | Transformer SDK metrics | Kept with the SDK 2.x per-client `CloudWatchMetricPublisher` (no global switch exists in SDK 2.x; a global interceptor cannot add one). The `shared` client-profile helper builds transformer's clients with it and wraps them in `cloud-sdk-aws` implementations; allowed exception to R10. U7 optional |
| R15 | Branch flow | Feature branch `WI01124532-aws-sdk-upgrade` + one sub-branch PR per step/module into it; `develop` brought in by rebase (`--rebase-merges`, `--force-with-lease`) as needed; final single PR to `develop` with a merge commit (§9.5). Branch names stay out of the published pages |
| R16 | Epic field | `N/A` on every page |
| R14 | Program page trim | ION-12317 removed from every Jira Tickets table; program open issues reduced to models, commons changes and Hystrix; known-defect paragraph, SNAPSHOT and root-pin risks removed |

**Other findings carried into the pages:** the root pom pins (Jetty 12.1.9, Jackson 2.21.4, logback 1.5.33, slf4j 2.0.17) would downgrade the commons versions and are aligned in build step 1; the S3 client has no API-call timeout (SDK 2.x would cap the body read); REPLACE copy passes `application/octet-stream`; health checks decide by exception type and reuse the injected clients.

### 9.10 Publish plan (after approval)

Pages are published **one per module, titled by module name** (the page H1, e.g. "WI01124532 transformer — AWS SDK 2.x (cloud-sdk) Upgrade"). Build steps get no pages; they only set the publish order, so reviewers read the foundation before the modules that depend on it. The build order lives on the program page. The review summary is not published.

Per page: re-auth SSO → `convert_design_doc.py` (exit 0) → `confluence_create_page` (BRM, storage) → read back `body.storage` and compare → record the page id in the MCP session.

| Order | Page(s) | Parent |
|---|---|---|
| 1 | program | 26.4.1 Design Documents (`718407506`; first published under Draft Design Documents `132890668`, move pending) |
| 2 | shared (covers `functional-testing`, root pom and the v1 deletion) | program |
| 3 | event-writer, error-processor, email-sender | program |
| 4 | dispatcher, splitter, transformer, distributor, distributor-rest, ingestor | program |
| 5 | watermill-publisher, watermill (platform) | program |
| 6 | booking-inbound-consumer, visibility-inbound-consumer, cargoscreen-consumer, itv-gps-consumer | watermill (platform) |

Before step 4: the distributor-rest security ticket is raised (the page describes the token-sharing defect).

**Published pages (BRM, Draft Design Documents `132890668`):**

| # | Page | Page id | Version | Date |
|---|---|---|---|---|
| 1 | WI01124532 AppianWay — AWS SDK 2.x (cloud-sdk) Upgrade Program | `716084128` (moved under 26.4.1 Design Documents `718407506`) | 2 | 2026-10-30 |
| 2 | WI01124532 shared (mercury-shared) — Re-base on commons / cloud-sdk | `716084130` | 4 | 2026-10-30 |
| 3 | WI01124532 event-writer — AWS SDK 2.x (cloud-sdk) Upgrade | `716084136` | 4 | 2026-10-30 |
| 4 | WI01124532 error-processor — AWS SDK 2.x (cloud-sdk) Upgrade | `716084140` | 2 | 2026-10-30 |
| 5 | WI01124532 email-sender — AWS SDK 2.x (cloud-sdk) Upgrade | `716084141` | 2 | 2026-10-30 |
| 6 | WI01124532 dispatcher — AWS SDK 2.x (cloud-sdk) Upgrade | `716084143` | 2 | 2026-10-30 |
| 7 | WI01124532 splitter — AWS SDK 2.x (cloud-sdk) Upgrade | `716084144` | 2 | 2026-10-30 |
| 8 | WI01124532 transformer — AWS SDK 2.x (cloud-sdk) Upgrade | `716084154` | 1 | 2026-10-30 |
| 9 | WI01124532 distributor — AWS SDK 2.x (cloud-sdk) Upgrade | `716084155` | 1 | 2026-10-30 |
| 10 | WI01124532 distributor-rest — AWS SDK 2.x (cloud-sdk) Upgrade | `716084156` | 1 | 2026-10-30 |
| 11 | WI01124532 ingestor — AWS SDK 2.x (cloud-sdk) Upgrade | `716084157` | 1 | 2026-10-30 |
| 12 | WI01124532 watermill-publisher — AWS SDK 2.x (cloud-sdk) Upgrade | `716084167` | 1 | 2026-10-30 |
| 13 | WI01124532 watermill consumer platform (consumer-commons, consumer-framework, billoflading) — AWS SDK 2.x (cloud-sdk) Upgrade | `716084168` | 1 | 2026-10-30 |
| 14 | WI01124532 watermill booking-inbound-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | `716084170` | 1 | 2026-10-30 |
| 15 | WI01124532 watermill visibility-inbound-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | `716084171` | 1 | 2026-10-30 |
| 16 | WI01124532 watermill cargoscreen-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | `716084172` | 1 | 2026-10-30 |
| 17 | WI01124532 watermill itv-gps-consumer — AWS SDK 2.x (cloud-sdk) Upgrade | `716084173` | 1 | 2026-10-30 |
