# `distributor` — AWS SDK v2 (cloud-sdk) Upgrade PLAN

> **DIRECTIVE UPDATE (2026-05-31) — supersedes the Option-A recommendation in this document.** Per stakeholder direction the program now targets **Dropwizard 5** and **Option B — adopt `commons` + `cloud-sdk-api`/`cloud-sdk-aws`** as the directed default (recommend Option A only on a categorical technical blocker). All AWS service communication goes through `cloud-sdk-api`; new tests are written in **JUnit 5 (Jupiter)** (existing JUnit 4 runs via JUnit Vintage during transition); configuration follows the composed appianway `.properties`/`${PROFILE}`/`${ENV}` + commons `${awsps:...}` model in the master [shared plan §10](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md). cloud-sdk gaps are indexed in the master [shared plan §11](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) with full technical specs in the master [shared DESIGN §1A.6](../../shared/docs/2026-05-31-shared-aws2x-upgrade-DESIGN.md).
> **Module-specific cloud-sdk gaps:** G1 (concurrent SQS listener), G2 (S3 putObject with metadata/content-type for rendered outbound files), G6 (config), G7 (health checks). The filename rendering and optional zip (`IOUtils`) file-shaping stay appianway-local (no cloud-sdk gap).
> Sections below are retained as the Option-A fallback reference.

> Module: `distributor` (file-shape egress: renders filename, optional zip, writes to outbound-delivery S3) · Date: 2026-05-31 · Author: GitHub Copilot (Claude Opus 4.8)
> Program: appianway AWS Java SDK v1 (1.12.720) → AWS SDK v2 via `cloud-sdk-api`/`cloud-sdk-aws`. Session `83b822b011714117`.

## 1. Scope & AWS surface
- **`modules/ExternalServicesModule`** binds `AmazonS3` (`AWSClientConfiguration.s3_read_put_copy`); SQS listener/sender via `shared`.
- **Task** consumes `com.amazonaws.services.sqs.model.Message` (shared listener DTO).
- **Module-unique:** `com.amazonaws.util.IOUtils` used by the zip/compression path (`ZipCompression`).

## 2. Migration concerns specific to distributor
- **`IOUtils`** → `software.amazon.awssdk.utils.IoUtils` (or `java.io`/Guava). Trivial swap; the zip logic itself (`java.util.zip`) is JDK, unaffected.
- Outbound write goes through `shared` `WorkspaceService.putObject*` — whose return changes from `PutObjectResult` to `void` (all callers ignore it). Confirm distributor's call site ignores the result (it does, per the `shared` peer review).

## 3. Options (A vs B)
Full A/B detail in the [`shared` plan](../../shared/docs/2026-05-31-shared-aws2x-upgrade-plan-copilot.md) §3–§8. **Option A recommended** — rebind S3 client to `cloud-sdk-aws` `StorageClient`, swap DTO + IOUtils; keep Dropwizard 4 / JUnit 4.

## 4. Maven impact
Remove `aws-java-sdk-s3` (and `sqs` if declared). Add `cloud-sdk-api` only if naming interface types. v2 runtime transitive via `shared`.

## 5. Test impact
Functional tests via `functional-testing` fakes (migrate first). Keep zip-output tests (zip bytes, filename rendering, optional-zip toggle). DTO construction → `MessageRef`. JUnit 4 retained.

## 6. Recommendation
**Option A.** Effort: **Low–Medium** (IOUtils swap + standard rebind).

## 7. Peer review outcome
Peer-reviewed (Explore subagent). Confirmed S3 + IOUtils are the only AWS surfaces; zip is JDK. Reviewer notes: (a) verify `putObject` result is ignored at distributor's call site (confirmed — matches `shared` finding); (b) ensure the optional-zip path still streams via the v2-backed `StorageClient` without buffering whole files in memory if large — keep streaming `putObject(InputStream,length)` semantics. Recommendation unchanged.

## 8. Sequencing
After `shared` + `functional-testing`. Pairs naturally with `distributor-rest` review.

## 9. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Large-file zip buffered in memory under v2 | Preserve streaming put with known content-length; test with a large fixture |
| `putObject` void return breaks a caller | Confirmed all callers ignore it (shared review); compiler will flag otherwise |
| IOUtils behavior diff | Unit-test the compression helper |
