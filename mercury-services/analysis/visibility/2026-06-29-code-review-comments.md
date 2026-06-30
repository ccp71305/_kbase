# PR 1066 — Code Review Comment Responses

**PR:** [ION-12316: Visibility (Track and Trace) AWS SDK 2.x cloud-sdk upgrade](https://git.dev.e2open.com/projects/INT/repos/mercury-services/pull-requests/1066/overview)
**Source branch:** `feature/ION-12316-visibiilty-aws-upgrade-copilot` → `develop`
**Reviewer:** Sumesh Jacob
**Date:** 2026-06-29
**Status of all comments below:** OPEN / unresolved

> ⏸️ **Deferred — resume 2026-06-30.** No code changes will be applied yet. The PR branch has a
> **merge conflict with the latest `develop`**, so the plan is to **rebase `feature/ION-12316-visibiilty-aws-upgrade-copilot` onto `develop` first**, resolve conflicts, and only then apply the agreed code changes (items A–F below). Draft responses are final; the required changes are pending the rebase.

> Note: These are **draft** responses. No code changes have been applied yet — see the
> "Required code changes" section at the bottom. Confirmation is required before any change is made.

---

## Summary

The reviewer raised **7 comments**, which fall into three themes:

| # | Theme | Files | Action |
|---|-------|-------|--------|
| 1, 2 | Redundant explicit cloud-sdk dependency declarations (transitive via `visibility-inbound`) | `visibility-wm-inbound-processor/pom.xml`, `visibility-itv-gps-processor/pom.xml` | Discuss / optional change |
| 3, 5 | Hard-coded dependency/plugin versions should be parameterized as Maven properties | `visibility-inbound/pom.xml`, `visibility-commons/pom.xml` | **Agree — change** |
| 4 | Removed `dynamoDbTableCreationCommandConfig` — where is config loaded now? | `visibility-inbound/conf/*/config.yaml` | Clarify (no change) |
| 6 | Explicit getter on `Condition.values` while Lombok is present | `Condition.java` | **Agree — likely remove** |
| 7 | Impact of field type change on existing DynamoDB records | `ContainerEventPending.java` | Clarify (no change) |

---

## Comment 1 — `visibility-wm-inbound-processor/pom.xml` line 20 (id 171895)

**Reviewer:**
> Are these dependencies not already brought in transitively through `visibility-inbound`? If so,
> could we avoid adding explicit dependency declarations here and rely on the transitive dependencies
> instead? It would be helpful to understand whether there is a specific reason for importing
> `cloud-sdk-api` and `cloud-sdk-aws` directly (e.g., version override, dependency visibility, or to
> make the dependency relationship explicit).

**Draft response:**
> You're correct — `visibility-wm-inbound-processor` depends on `visibility-inbound`, which declares
> `cloud-sdk-api` and `cloud-sdk-aws` at compile scope, so they do arrive transitively, and there is
> **no version override** here (both use `${mercury.commons.version}`).
>
> They were declared explicitly to follow the "declare the dependencies you use directly" guideline
> (Maven Dependency Analyzer / `dependency:analyze`), because this module references cloud-sdk types
> directly and would otherwise break silently if `visibility-inbound` ever stopped exposing them.
>
> That said, I'm happy to align with whichever convention the team prefers. If we standardize on
> relying on the transitive path from `visibility-inbound`, I'll remove the two explicit declarations
> here. Please confirm.

**Required code change (only if team prefers transitive):** remove the `cloud-sdk-api` and
`cloud-sdk-aws` `<dependency>` blocks from `visibility-wm-inbound-processor/pom.xml`.

---

## Comment 2 — `visibility-itv-gps-processor/pom.xml` line 18 (id 171893)

**Reviewer:** *(same text as Comment 1)*

**Draft response:** Same as Comment 1 — `visibility-itv-gps-processor` also depends on
`visibility-inbound`, so `cloud-sdk-api`/`cloud-sdk-aws` are transitive with no version override.
Declared explicitly only to make the direct usage explicit. Will remove if the team prefers relying
on the transitive declaration — please confirm and I'll apply the same change to both processor modules.

**Required code change (only if team prefers transitive):** remove the two explicit cloud-sdk
`<dependency>` blocks from `visibility-itv-gps-processor/pom.xml`.

---

## Comment 3 — `visibility-inbound/pom.xml` line 39 (id 171891)

**Reviewer:**
> Could we move the version to a Maven property instead of hard-coding it in the dependency
> declaration? This would keep version management centralized and make future upgrades easier,
> similar to how `${mercury.commons.version}` is being used.

**Context:** The cloud-sdk dependencies already use `${mercury.commons.version}`. The hard-coded
values introduced in this file are the `log4j-api` / `log4j-core` version `2.23.1` and the
`maven-dependency-plugin` version `3.6.1`.

**Draft response:**
> Agreed. I'll lift the hard-coded versions into properties in the parent `visibility/pom.xml`
> (which already centralizes versions like `${software.amazon.awssdk.ses.version}` and
> `${maven-surefire-plugin.version}`), and reference them here:
> - `<log4j.version>2.23.1</log4j.version>`
> - `<maven-dependency-plugin.version>3.6.1</maven-dependency-plugin.version>`
>
> The dependency declarations will then use `${log4j.version}` etc. I'll apply this consistently
> across all the visibility module POMs touched in this PR (see Comment 5).

**Required code change:**
1. Add `<log4j.version>2.23.1</log4j.version>` and `<maven-dependency-plugin.version>3.6.1</maven-dependency-plugin.version>` to the `<properties>` of the parent `visibility/pom.xml`.
2. Replace hard-coded `2.23.1` → `${log4j.version}` and `3.6.1` → `${maven-dependency-plugin.version}` in `visibility-inbound/pom.xml`.

---

## Comment 4 — `visibility-inbound/conf/prod/config.yaml` line 82 (REMOVED) (id 171890)

**Reviewer:**
> Where is the apps now loading the configurations from?

**Context:** The removed block was `dynamoDbTableCreationCommandConfig` (per-table read/write
throughput and GSI definitions). The runtime `dynamoDbConfig` block was **kept** (and now also sets
`sseEnabled: false`). The same removal was applied across `int`, `qa`, `cvt`, and `prod` configs.

**Draft response:**
> The removed `dynamoDbTableCreationCommandConfig` block was **table-provisioning** configuration
> consumed only by the legacy `dynamo-client` to auto-create/update DynamoDB tables (throughput,
> GSIs) at application startup. It was never runtime/application configuration.
>
> Under the cloud-sdk model, table creation and administration are no longer driven by the app at
> startup — they are handled out-of-band by the cloud-sdk **table-admin** tooling (referenced in the
> `ContainerEventPending` Javadoc). So that block has no consumer anymore and was removed.
>
> The app still loads its **runtime** DynamoDB settings from the retained `dynamoDbConfig` block,
> which now maps to cloud-sdk's `BaseDynamoDbConfig` (field `dynamoDbConfig` in
> `VisibilityApplicationConfig`); the physical table prefix/environment is derived from it. So no
> runtime configuration was lost — only the now-unused provisioning section was dropped.

**Required code change:** None. (Optional: document the table-admin provisioning step in the module
docs / runbook so the throughput & GSI definitions are not lost institutionally.)

---

## Comment 5 — `visibility-commons/pom.xml` line 160 (id 171888)

**Reviewer:**
> Please parameterize the versions of dependencies to keep it consistent with other dependencies and
> maven plugin version, applicable for all new dependencies added.

**Context:** New hard-coded versions in this file: `log4j-api`/`log4j-core` `2.23.1`,
`aws-java-sdk-dynamodb`/`aws-java-sdk-core` `1.12.721`, and `maven-dependency-plugin` `3.6.1`.

**Draft response:**
> Agreed. I'll add properties to the parent `visibility/pom.xml` and reference them in every new
> dependency/plugin declaration added in this PR:
> - `<log4j.version>2.23.1</log4j.version>`
> - `<aws-java-sdk-v1.version>1.12.721</aws-java-sdk-v1.version>`
> - `<maven-dependency-plugin.version>3.6.1</maven-dependency-plugin.version>`
>
> I'll apply this consistently to `visibility-commons`, `visibility-inbound`,
> `visibility-wm-inbound-processor`, and `visibility-itv-gps-processor`.

**Required code change:**
1. Add the three properties above to the parent `visibility/pom.xml` `<properties>`.
2. In `visibility-commons/pom.xml`, replace `2.23.1` → `${log4j.version}`, `1.12.721` →
   `${aws-java-sdk-v1.version}`, `3.6.1` → `${maven-dependency-plugin.version}`.
3. Apply the same substitutions in the other three module POMs that carry these versions.

---

## Comment 6 — `Condition.java` line 36 (id 171866)

**Reviewer:**
> Why is an explicit getter needed for this field alone when lombok getter method is available?

**Context:** The PR removed the v1 `@DynamoDBAttribute(attributeName = "values")` and replaced it with
an explicit getter carrying the v2 annotation:
```java
@DynamoDbAttribute("values")
public List<String> getValues() {
    return values;
}
```
The other fields (`targetType`, `operator`, `valueType`) rely on the Lombok getter with no explicit
annotation.

**Draft response:**
> Good catch. The general reason an explicit getter is sometimes required under the Enhanced Client is
> that its annotations (`@DynamoDbAttribute`, `@DynamoDbPartitionKey`, etc.) must sit on the accessor,
> and Lombok-generated getters can't carry them.
>
> In this specific case, however, the Enhanced Client already derives the attribute name `values`
> from the property name, so `@DynamoDbAttribute("values")` is effectively a no-op and the explicit
> getter is **redundant**. I'll remove it and let Lombok provide the getter, keeping it consistent
> with the sibling fields. (I'll confirm via the `visibility-commons` integration test that the
> persisted attribute name remains `values` after removal.)

**Required code change:** Remove the explicit `getValues()` method and `@DynamoDbAttribute("values")`
from `Condition.java`, relying on the Lombok getter and default name mapping. Verify with the
DynamoDB integration test that the stored attribute name is unchanged.

---

## Comment 7 — `ContainerEventPending.java` line 37 (id 171863)

**Reviewer:**
> What would be impact of type change to existing records?

**Context:** The partition key field changed from `LocalDate createDate` (v1, stored via
`DateToIso8601` converter) to `String createDate` (v2). A Javadoc on the field already documents the
intent.

**Draft response:**
> There is **no impact on existing records**. The on-disk representation is byte-identical to the 1.x
> schema:
> - v1 stored `createDate` as the ISO-8601 date **String** (DynamoDB type `S`) via the
>   `DateToIso8601` converter.
> - v2 stores the same ISO-8601 **String** directly under the same attribute name `createDate`,
>   type `S`.
>
> Only the in-memory Java type changed (`LocalDate` → `String`); the persisted attribute name, type,
> and value format are unchanged, so existing items remain fully readable and writable. As the
> Javadoc notes, keeping it a `String` (rather than `LocalDate` + a converter) is also deliberate so
> the cloud-sdk table-admin command can resolve the key attribute type, since its key-type resolution
> is reflection/field-based and does not honour converters on a key attribute.
>
> `expiresOn` is likewise unchanged — still a `Date` persisted as an epoch-second number via the
> equivalent converter. This round-trip is covered by the `ContainerEventPending` DynamoDB
> integration test.

**Required code change:** None. (Behavior preserved; covered by integration test.)

---

## Consolidated list of required code changes

| # | File | Change | Disposition |
|---|------|--------|-------------|
| A | parent `visibility/pom.xml` | Add properties: `log4j.version=2.23.1`, `aws-java-sdk-v1.version=1.12.721`, `maven-dependency-plugin.version=3.6.1` | Pending confirmation (Comments 3, 5) |
| B | `visibility-commons/pom.xml` | Replace hard-coded `2.23.1`, `1.12.721`, `3.6.1` with the new properties | Pending confirmation (Comment 5) |
| C | `visibility-inbound/pom.xml` | Replace hard-coded `2.23.1`, `3.6.1` with the new properties | Pending confirmation (Comment 3) |
| D | `visibility-wm-inbound-processor/pom.xml` | Replace hard-coded `2.23.1`, `3.6.1` with properties; (optional) drop transitive cloud-sdk deps | Pending confirmation (Comments 1, 5) |
| E | `visibility-itv-gps-processor/pom.xml` | Replace hard-coded versions with properties; (optional) drop transitive cloud-sdk deps | Pending confirmation (Comments 2, 5) |
| F | `Condition.java` | Remove redundant explicit `getValues()` + `@DynamoDbAttribute("values")` | Pending confirmation (Comment 6) |
| — | config / model | No change (Comments 4, 7 — clarification only) | — |

> **Verification after changes:** `mvn -pl visibility/visibility-commons,visibility/visibility-inbound,visibility/visibility-wm-inbound-processor,visibility/visibility-itv-gps-processor -am verify`
> (runs unit + DynamoDB `*IT` integration tests) must pass before updating the PR.

**No changes will be made until you confirm.**

---

## Next session — resume plan (2026-06-30)

1. **Rebase first.** `feature/ION-12316-visibiilty-aws-upgrade-copilot` has a merge conflict with the
   latest `develop`. Rebase onto `develop` and resolve conflicts before touching review items.
2. **Re-verify the diff** after rebase — line numbers / context for the 7 comments may shift; confirm
   the required changes (A–F) still apply as written.
3. **Apply agreed changes** (pending confirmation on Comments 1/2 transitive-dep removal):
   parameterize versions (A–E) and remove redundant `getValues()` (F).
4. **Run** the `mvn ... verify` command above (unit + DynamoDB integration tests) until green.
5. **Post draft responses** on the PR and push the rebased branch.

**Session:** `a4ee7696b84f429e` (status: active — resume tomorrow).
