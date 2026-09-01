# Analysis: DynamoDB GSI throughput-0 deployment issue (Cargo Visibility Subscription)

**Ticket:** ION-16650  **Date:** 2026-08-24  **Scope:** `watermill-cargo-visibility-subscription` (+ related latent risk in `visibility-inbound`)
**Source doc analysed:** `gsi-throughput-zero-fix 1.md`
**AWS profile used (read-only `describe-table` / CloudTrail `lookup-events` only — no scans, no config changes):** `642960533737_INTTRA2-QATeam`

---

## 1. Summary

The `dynamo-create` command for `CargoVisibilitySubscription` failed with a DynamoDB
`ValidationException` (`writeCapacityUnits`/`readCapacityUnits` value `0` must be `>= 1`) whenever it
had to **create** a GSI that did not yet exist. Root cause: the AWS SDK 2.x (cloud-sdk) upgrade of the
entity omitted the `@GsiConfig` annotation on the three GSI partition-key getters, so per-GSI capacity
defaulted to the primitive `long` value `0L`, which was passed verbatim to the `UpdateTable` /
`addGlobalSecondaryIndex` call.

**Why it was missed:** in every long-lived environment (QA, prod) the three entity-declared GSIs
**already existed**, so `createTableWithGsisIfNotExists()` skipped the add-GSI path and the 0-capacity
value was never exercised. The defect only surfaces where a declared GSI is absent (a fresh
environment, or one that never had that specific index). Standard deploys to QA/prod therefore stayed
green and the bug slipped through review and CI.

---

## 2. Timeline (git + CloudTrail, all times normalised where noted)

| When | Event | Evidence |
|---|---|---|
| 2019-07-18 | QA `container_events` table created with its 5 GSIs (unrelated table, see §6) | `describe-table` CreationDateTime |
| 2026-01-19 | QA `inttra2_qa_CargoVisibilitySubscription` table created | `describe-table` CreationDateTime |
| 2026-07-11 | `inttra2_prod_CargoVisibilitySubscription` table created | `describe-table` CreationDateTime |
| **2026-07-28 19:46 EDT** | AWS 2.x upgrade **authored** (`32608bbccb`, ION-16380) — this is the "before 8/13" date | `git show` author-date |
| 2026-08-13 11:21 EDT | Same commit's **commit-date** (rewritten by pre-merge rebase) | `git show` commit-date |
| **2026-08-13 18:09 UTC** | ION-16380 **merged to `develop`** via PR #1127 (`d5c6f5b9b5`) — only merge of this ticket | `git log origin/develop` |
| 2026-08-22 ~15:36–16:32 UTC | ION-16650 fix authored & merged: PR #1201 (`a2210ab56a`) + PR #1202 (`8a9a660d6f`), adds `@GsiConfig(readCapacity=25, writeCapacity=25, KEYS_ONLY)` + capacity normalisation | `git log origin/develop` |
| **2026-08-22 12:39–12:49 EDT** | **Prod GSIs actually created** on `inttra2_prod_CargoVisibilitySubscription` via operator (EC2 instance `i-053ceaa3349162198`) `UpdateTable` calls, with **read=25 / write=25, KEYS_ONLY** | CloudTrail `UpdateTable` |

### Author date vs commit date vs merge date (the "8/13" clarification)

The upgrade commit `32608bbccb` was **authored 2026-07-28** but its **commit date is 2026-08-13**
(rewritten by a rebase before the PR merge). It landed on `develop` only on **2026-08-13** via PR
#1127 — the sole merge of ION-16380. So "authored before 8/13" and "merged 8/13" are both correct;
they are different milestones. For deployment-impact purposes the **merge-to-develop date (8/13)** is
the one that matters, and the prod GSI creations (8/22) came after it either way.

---

## 3. Root cause / how it was missed

1. `extractGsiMetadata()` reads `@GsiConfig` on each GSI partition-key getter. When the annotation is
   **absent**, `GsiMetadata.readCapacity` / `writeCapacity` stay at their `long` default `0L`.
2. The ION-16380 upgrade converted the entity to SDK 2.x annotations but did **not** add `@GsiConfig`.
3. Table-level throughput in `DynamoDbClientConfig` does **not** feed the per-GSI `addGlobalSecondaryIndex`
   path — there is no fallback — so the `0L` reached DynamoDB and was rejected.
4. **Masking:** `createTableWithGsisIfNotExists()` only builds a `ProvisionedThroughput` for a GSI it
   must *create*. QA (table since 2026-01-19) and prod (table since 2026-07-11) already had all three
   entity-declared GSIs, so the failing branch never ran there → deploys were green → defect invisible
   to CI/PR review. It only breaks on a first-time/GSI-missing environment.

---

## 4. Live DynamoDB verification (read-only `describe-table`)

Entity currently declares **3 GSIs**, all `KEYS_ONLY`, `25/25` (post-fix, watermill copy):
`bookingNumber-carrierInttraId-index`, `billOfLading-carrierInttraId-index`, `subscriptionReference-index`.

**QA `inttra2_qa_CargoVisibilitySubscription`** (created 2026-01-19, ~85,966 items) — 6 GSIs, all ACTIVE, `KEYS_ONLY`, 5/5:
- `bookingNumber-carrierInttraId-index`, `billOfLading-carrierInttraId-index`, `subscriptionReference-index` (current model)
- `bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index`, `bookingNumber-index` (legacy SCAC-era, no longer in the model)

**Prod `inttra2_prod_CargoVisibilitySubscription`** (created 2026-07-11, ~93,469 items) — 5 GSIs, all ACTIVE, `KEYS_ONLY`, 5/5:
- `bookingNumber-carrierInttraId-index`, `billOfLading-carrierInttraId-index`, `subscriptionReference-index`
- `bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index` (legacy; no `bookingNumber-index`)

> Note: live GSI throughput is **5/5** (created earlier / autoscaling-managed), whereas the code now
> requests **25/25**. Because those GSIs already exist, `dynamo-create` will not re-apply 25/25 — the
> code value only applies when a GSI is first created. Key schema and `KEYS_ONLY` projection match the
> model, so DAO queries are consistent.

---

## 5. Was the prod table updated, and were the GSIs added after the upgrade?

**Yes — prod GSIs were added on 2026-08-22, after the upgrade merged to develop (8/13), and with the
fixed throughput.** CloudTrail `UpdateTable` events on `inttra2_prod_CargoVisibilitySubscription` by
operator instance `i-053ceaa3349162198` (not autoscaling):

- 2026-08-22 12:39:21 EDT — create `billOfLading-carrierInttraId-index` — read=25, write=25, KEYS_ONLY
- 2026-08-22 12:39:56 / 12:43:01 / 12:49:01 EDT — create `bookingNumber-carrierInttraId-index` — read=25, write=25, KEYS_ONLY (repeated because DynamoDB allows only one GSI creation in flight at a time)

The **25/25** capacity in these calls exactly matches the ION-16650 `@GsiConfig` values, confirming the
**fixed** build (not the broken 0-capacity build) performed the prod GSI creation. These indexes did
**not** exist on prod before 8/22 — so between the table's 7/11 creation and 8/22 the two
`carrierInttraId` indexes were absent in prod.

**Caveats / limits of evidence:**
- No failed 0-capacity `UpdateTable` attempt was found in the operator-event scan of the window
  immediately before the 8/22 fix deploy, but CloudTrail management events older than ~90 days are not
  retained, and the autoscaling `UpdateTable` volume means the scan did not necessarily reach back to
  8/13. Absence of a recorded failure is therefore **not conclusive**.
- QA GSI creation predates the 90-day CloudTrail window (table from 2026-01-19), so its GSI-add history
  is not observable; the indexes are simply present and ACTIVE.

---

## 6. Related latent risk (same root cause) — NOT yet fixed

Two follow-ups worth flagging (no changes made; prod/QA untouched per instruction):

1. **`visibility-inbound` `ContainerEvent`** — `VisibilityInboundDynamoDbAdminCommand` runs the same
   `dynamo-create` flow for `container_events` (5 GSIs: `bookingNumber-index`, `blNumber-index`,
   `equipmentIdentifier-index`, `bkInttraReferenceNumber-equipmentIdentifier-index`,
   `siInttraReferenceNumber-index`). `ContainerEvent.java` has **zero `@GsiConfig`** annotations, and
   its `resolveClientConfig` does **not** normalise capacity. This is the **identical defect** ION-16650
   fixed for CVS. It is currently masked because `inttra2_qa/prod_container_events` already have all 5
   GSIs (QA table created 2019-07-18, 10/40 capacity, all ACTIVE), but a fresh-environment deploy would
   fail the same way.
2. **Model drift for CVS** — the `visibility-commons` copy of `CargoVisibilitySubscription.java` (used
   by the DAO) still has **no `@GsiConfig`**, unlike the fixed `watermill-publisher` copy. Not currently
   a table-creation risk (visibility-inbound's command does not register CVS; only the watermill command
   creates that table), but the two copies have diverged and should be reconciled to avoid confusion.

---

## 7. Recommendations

1. Apply the ION-16650 pattern to `ContainerEvent` (add `@GsiConfig` to all 5 GSI getters) and add the
   same capacity normalisation to `VisibilityInboundDynamoDbAdminCommand.resolveClientConfig`.
2. Reconcile the two `CargoVisibilitySubscription` copies (watermill vs visibility-commons) or collapse
   to one shared model so `@GsiConfig` cannot drift.
3. Add a build-time guard/test (as ION-16650 did via `...SortTest`) that fails if any
   `@DynamoDbSecondaryPartitionKey` getter on a cloud-sdk entity lacks `@GsiConfig` — apply across all
   AWS-2.x-upgraded modules, not just CVS.
4. Prefer sourcing per-GSI capacity from table-level config as a fallback in the cloud-sdk
   `addGlobalSecondaryIndex` path (library-level fix) so a missing annotation can never yield `0`.
