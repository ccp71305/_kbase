# AppianWay AWS SDK v2 (cloud-sdk) Upgrade — Design Summary & Implementation Reference

> **Ticket:** ION-12317 · **Date:** 2026-07-23 · **Author:** Claude (Opus 4.8) with Arijit Kundu
> **Status:** Design phase **COMPLETE** (all 14 module pages + program page published to Confluence BRM). Next phase: **mercury-services-commons cloud-sdk gap implementation**, then the 5-wave module rollout.
> **MCP context-server session id:** `a0e9dc68b8f14672` — resume with the `session_get`/`session_search` tools on the `mcp-context-server` to recall design decisions, page IDs, and the gap-implementation plan across conversations.

This document is the single-page reference for the whole program: what it is, where every design page lives, the exact cloud-sdk gaps to build first, the rollout order, and the local `.md` source inventory.

---

## 1. What this program is

Migrate the **14 deployable AppianWay apps** off **AWS Java SDK v1 (1.12.720) + the appianway `shared` module** onto:

- **`mercury-services-commons` `1.0.27-SNAPSHOT`** — `commons` (config command, network-services, health base, `InttraServer`) + `cloud-sdk-api` (client interfaces + `notification.*` workflow model) + `cloud-sdk-aws` (AWS SDK **v2** impls).
- A new slim, **appianway-owned** `appianway-commons:1.0-SNAPSHOT` residue library (concurrency dispatcher, error handling, health-registrar glue, config property-substitution transform) — NOT published to mercury-services.

It is an **AWS-layer + drop-`shared` change only**. The framework baseline — **Dropwizard 5.0.2 / Jetty 12.1.9 / Java 17 / Jackson 2.21.4** — already landed under **ION-16098** and is in `develop`; all 14 apps boot clean on it against INT. This program does not revisit that baseline.

**Non-negotiable contract:** `cloud-sdk-api`, `cloud-sdk-aws`, `commons` are consumed in **production by mercury-services**. Every change this program relies on MUST be strictly additive (new `default` methods, overloads, types, visibility-widening only). AppianWay consumes them as a normal client. No queue/topic/bucket/SSM-path/`${key}`-default renames anywhere — they are environment contracts.

---

## 2. Confluence page map (BRM space, parent 650546306 = "26.2.3 Design Documents")

| Page | ID | URL |
|---|---|---|
| **Program landing page** (v5) | 672212104 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212104 |
| event-writer | 672212105 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212105 |
| distributor-rest | 672212106 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212106 |
| splitter | 672212107 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212107 |
| ingestor | 672212108 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212108 |
| dispatcher | 672212125 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212125 |
| distributor | 672212126 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212126 |
| error-processor | 672212128 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212128 |
| email-sender | 672212131 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212131 |
| transformer | 672212132 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212132 |
| watermill-publisher | 672212135 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212135 |
| booking-inbound-consumer | 672212136 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212136 |
| cargoscreen-consumer | 672212137 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212137 |
| itv-gps-consumer | 672212138 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212138 |
| visibility-inbound-consumer | 672212139 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212139 |
| **Baseline reference** (ION-16098 DW5/Jetty12/CVE) | 672212099 | https://confluence.dev.e2open.com/pages/viewpage.action?pageId=672212099 |

---

## 3. The cloud-sdk / commons gaps to build FIRST (Wave 0)

These land in **mercury-services-commons** before any AppianWay module is touched. All are strictly additive. Gate each on cloud-sdk CI + a full mercury-services build green (zero-impact proof), before and after.

### S-G2 — StorageClient metadata/content-type write overloads (`cloud-sdk-api` + `cloud-sdk-aws`)
Add:
- `StorageClient.putObject(bucket, key, byte[], Map<String,String> metadata, String contentType)`
- an `InputStream` variant of the same
- `copyObject(..., Map<String,String> replacedMetadata, String contentType)` (S3 `REPLACE` metadata directive)

**Consumers:** event-writer (`application/json` audit writes), dispatcher (zip put-with-metadata), distributor (copy-with-replaced-metadata ×2), error-processor (archive put). Referenced-but-not-exercised by transformer/splitter (plain 3-arg put suffices there).

### W-G9 — workflow-model parity (`cloud-sdk-api`)
1. **W-G9.1 (wire round-trip defect, MUST fix):** add `annotations` + `setAnnotations` to `Event.Builder` and copy them in the `Builder(Event)` copy-constructor. Today `Event.parseJson` silently drops an `annotations` block (write-only, asymmetric).
2. **W-G9.2 (source-compat, add for compile):** add the **6 missing `MetaData.Projection`** constants (cloud-sdk has 26, appianway uses 32 — e.g. `DISTRIBUTOR_REST`, `ORIGINAL_IB_WORKSPACE_FILE`) and the **8 missing `Event.Token`** constants (9 vs 17). Pure `String` constants, zero wire change.

**Verification gate (blocks the event-writer pilot, stays green through rollout):** a JSON round-trip corpus test using representative production `MetaData`/`Event`/`Annotations` JSON (e.g. event-writer's S3 archives) asserting appianway-`shared` serialization ≡ cloud-sdk-api serialization, byte-stable parse→serialize, **including an annotations-bearing payload** (guards W-G9.1).

**Consumers:** every event/MetaData publisher+consumer — most acutely event-writer, error-processor, transformer, and the visibility-inbound-consumer (annotation error paths).

### X-G7 — email reply-to (`cloud-sdk-api` + SES)
Add an additive `replyTo` field + builder setter on `MailContent`, mapped by `cloud-sdk-aws` `SesEmailServiceImpl` to SES v2 `replyToAddresses`.

**Consumer:** email-sender (only). **Fallback if not delivered:** email-sender composes the Reply-To header locally against the underlying `SesV2Client` `cloud-sdk-aws` already builds — a contingency only; the additive `MailContent.replyTo` path is preferred.

### X-G8 — ingestor Jest/OpenSearch signing — **CORRECTED: NO cloud-sdk change**
Jest (`io.searchbox` 6.3.1, Apache HttpClient 4.x) + the `vc.inreach.aws.request.AWSSigner` (v1 SigV4) stack is **not compatible with AWS SDK v2**, and **no module in mercury-services migrates it** (verified against `visibility-inbound`, `oceanschedules` loader/port-pair-generator, and the `elasticsearch-purge` lambda). ingestor therefore **keeps the v1 signer as-is** and **retains `vc.inreach:aws-signing-request-interceptor` + a minimal AWS v1 auth/credentials jar** coexisting on-classpath with the cloud-sdk-aws v2 stack (different package namespaces — `com.amazonaws.*` vs `software.amazon.awssdk.*` — no conflict). ingestor is the one module that deliberately carries both SDKs.

### De-scoped (NOT cloud-sdk changes)
- **DynamoDB optimistic lock** → native v2 `@DynamoDbVersionAttribute` (default `VersionedRecordExtension`). Used only by transformer's control-number sequence; the watermill offset tables deliberately do **not** use it (last-writer-wins).
- **Thymeleaf / Handlebars template** → stays local to email-sender (G5 rejected — would force a heavy transitive dep on every `EmailService` consumer).
- **Health helpers** → re-point to injected clients in appianway-commons.
- **C-G6** (widen commons `getConfigTransformer` visibility) → optional; config composition works without it.

---

## 4. Rollout order (verify-gated; each behind `mvn -pl <m> -am verify` + INT boot/health check)

```
0  Land S-G2 + W-G9 + X-G7 in cloud-sdk-api/aws  →  cloud-sdk CI + full mercury-services build GREEN (zero-impact proof)
1  appianway-commons (slim residue) + functional-testing fakes (lockstep)  →  event-writer (pilot; W-G9 round-trip corpus test gates here)
2  distributor-rest · splitter · ingestor            (light consumers; ingestor = keep-v1-Jest-signer)
3  dispatcher · distributor · error-processor         (S-G2 write/copy consumers)
4  email-sender (X-G7) · transformer (DynamoDB v2 + Contivo pre-flight)
5  watermill-publisher  →  consumer-commons (v2 rebind)  →  the 4 watermill consumers (gRPC + DynamoDB offset; port 8085)
```

**Library modules that migrate alongside (not separate pages):** `functional-testing` (cloud-sdk-api-shaped fakes, migrates in lockstep with the pilot), `watermill/consumer-commons` (offset-store/S3/config-POJO consolidation — must land its own v1→v2 rebind before any of the 4 consumers can consolidate onto it).

---

## 5. Per-module headline & gaps (quick index)

| # | Module | Wave | Headline change | Gaps exercised |
|---|--------|:--:|------------------|----------------|
| 1 | event-writer | 1 (pilot) | `application/json` audit writes; archives Event JSON | S-G2, **W-G9** |
| 2 | distributor-rest | 2 | pure client rebind, S3 read-only | W-G9 |
| 3 | splitter | 2 | canonical consumer rebind; ce- variant | W-G9 |
| 4 | ingestor | 2 | **Jest/OpenSearch v1 signer retained** (X-G8 corrected); ce- variant; keeps AWS v1 auth jar alongside v2 | **X-G8**, W-G9 |
| 5 | dispatcher | 3 | local S3-event parser (dispatcher-local); zip put-with-metadata | S-G2, W-G9 |
| 6 | distributor | 3 | copy-with-replaced-metadata ×2 | **S-G2**, W-G9 |
| 7 | error-processor | 3 | archive put; email fan-out; closeWorkflow | S-G2, **W-G9** |
| 8 | email-sender | 4 | SES v2; local Thymeleaf (G5 de-scoped); reply-to | **X-G7** |
| 9 | transformer | 4 | DynamoDB v2 `@DynamoDbVersionAttribute`; Contivo shade pre-flight; `AwsSdkMetrics`→v2 decision; ce-/os- profiles | S-G2 (ref), W-G9 |
| 10 | watermill-publisher | 5 | AWS-layer rebind (gRPC untouched); SSM boot `${awsps:}` creds (Option B) | — |
| 11 | booking-inbound-consumer | 5 | DynamoDB v2 offset; port 8085; SNS Events | W-G9 |
| 12 | cargoscreen-consumer | 5 | DynamoDB v2 offset; S3-only sink | — |
| 13 | itv-gps-consumer | 5 | DynamoDB v2 offset; S3-only; tenant `INTTRA` (not `INTTRA_INT`) | — |
| 14 | visibility-inbound-consumer | 5 | 3 gRPC consumers / 3 DynamoDB offsets in one process; 3 SQS + SNS | W-G9 |

**Cross-cutting notes for implementers:**
- The **watermill consumers** (11–14) run on **port 8085**, have **no ops health check** (verification is boot-evidence only), sit in a **no-parent-pom `watermill` reactor** (shared pins mirrored in `watermill/pom.xml`; `../../configuration` is two levels up), keep gRPC creds **runtime-resolved** from SSM (not boot-time `${awsps:}`), and their **DynamoDB offset row shape** (`{env}_watermill_offset`, attributes `topicName`/`offset`/`readDateTime`/`writeDateTime`, epoch-**seconds** via `LongEpochSecondAttributeConverter`) is the data-plane-safety-critical surface — gate every cutover on a backward-compat fixture seeded from a real INT offset row (booking 35, itv-gps 1353, visibility 35/43/79).
- The gRPC/protobuf layer everywhere (watermill-publisher + 4 consumers) is **NOT AWS and is out of scope** — only the AWS-layer plumbing feeding it is rebound.

---

## 6. Local `.md` document inventory (`appianway/docs/`)

**This summary**
- `2026-07-23-appway-awsupgrade-design-summary.md` — this document.

**ION-12317 program + 14 module design sources (publish-ready markdown; the Confluence pages were generated from these)**
- `2026-07-22-ION-12317-aws-upgrade-program.md` — program landing page (governing decisions, `shared`→replacement mapping, gap table, W-G9 audit, rollout, 14-module index).
- `2026-07-22-ION-12317-event-writer.md`
- `2026-07-22-ION-12317-distributor-rest.md`
- `2026-07-22-ION-12317-splitter.md`
- `2026-07-22-ION-12317-ingestor.md` — includes the corrected X-G8 (keep v1 Jest signer) section + mercury-services verification table.
- `2026-07-22-ION-12317-dispatcher.md`
- `2026-07-22-ION-12317-distributor.md`
- `2026-07-22-ION-12317-error-processor.md`
- `2026-07-22-ION-12317-email-sender.md`
- `2026-07-22-ION-12317-transformer.md`
- `2026-07-22-ION-12317-watermill-publisher.md`
- `2026-07-22-ION-12317-booking-inbound-consumer.md`
- `2026-07-22-ION-12317-cargoscreen-consumer.md`
- `2026-07-22-ION-12317-itv-gps-consumer.md`
- `2026-07-22-ION-12317-visibility-inbound-consumer.md`

**Related prior docs in this folder**
- `2026-05-24-appianway-overview-claude.design.md` — earlier AppianWay architecture overview.
- `2026-07-22-design-doc-ION-16098.md` — the DW5/Jetty12/Java17/Jackson2.21.4 CVE-remediation baseline this program builds on.

> Governing/source docs live one level up in `appianway/` (not in `docs/`): `2026-07-22-appianway-awsupgrade-foundation-claude.md` (foundation brief), `2026-07-22-appianway-awsupgrade-ROLLUP-claude.md` (rollup), the per-module `<module>/docs/2026-07-22-<module>-awsupgrade-claude.md` source designs, `2026-07-22-appway-app-checkouts-run-config.md` (verified INT boot evidence per module), and `2026-06-30-appianway-aws-upgrade-cloud-sdk-gap-DESIGN.md` (consolidated gap doc).

---

## 7. Publishing pipeline (how these pages were produced — for future updates)

- **Converter:** `scratchpad/convert_doc.py` (markdown → Confluence storage-format XHTML). Run through the mcp-summary-server venv python. Handles: CVE/ISO/generics-safe Jira-key macro regex (`\b(?!CVE-)([A-Z][A-Z0-9]+-\d+)(?!-\d)\b`), inline-`<code>` protection, `<ul>` lists, indented fences, literal CDATA code blocks.
- **Gotchas:** keep ASCII diagrams **free of raw `<`/`>`** inside code blocks (they corrupt the Confluence code macro's CDATA) — use `[String]`, `→`/`─▶`, `(under N)`, `[module]`. Pre-publish checks must show `raw '<' in code CDATA = 0`, balanced `cdata` open/close counts, and only intended `ION-*` Jira keys.
- **Publish:** `mcp-context-server` `confluence_create_page` / `confluence_update_page` (`representation="storage"`, `body=<xhtml>`; child pages via `parent_id=672212104`).
- Published Confluence content **does not reference these repo `.md` files** — it references the program Confluence page instead.

---

## 8. Next actions (implementation phase)

1. **Wave 0 — mercury-services-commons gap build:** implement S-G2, W-G9 (both .1 and .2), X-G7 additively; write the W-G9 JSON round-trip corpus test; confirm cloud-sdk CI + full mercury-services build green before/after. (X-G8 needs no cloud-sdk change; DynamoDB version-attribute is native v2.)
2. **appianway-commons + functional-testing** (lockstep) — stand up the slim residue library and the cloud-sdk-api-shaped fakes.
3. **event-writer pilot** — first module cutover, gated on the W-G9 corpus test.
4. Proceed waves 2→5 per §4, each behind `mvn -pl <module> -am clean verify` + INT boot/health evidence.

Log progress, decisions, blockers, and code changes into the **MCP context-server session `a0e9dc68b8f14672`** as implementation proceeds (categories: `progress`, `decision`, `finding`, `blocker`, `code_change`, `test_result`).
