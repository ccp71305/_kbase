# Visibility prod issue — DynamoDB GSI throughput-0 on Cargo Visibility Subscription

**Ticket:** ION-16650  **Date:** 2026-08-24  **Author of analysis:** @ArijitKunduWTG
**Module:** `watermill-publisher / watermill-cargo-visibility-subscription` (+ latent risk in `visibility-inbound`)
**Source doc analysed:** `gsi-throughput-zero-fix 1.md`
**AWS access:** read-only only — `describe-table` + CloudTrail `lookup-events` against profile
`642960533737_INTTRA2-QATeam`. **No DynamoDB scans, no prod/QA config or table changes were made.**

---

## 1. What broke in prod

The `dynamo-create` command for `CargoVisibilitySubscription` failed with a DynamoDB
`ValidationException` whenever it had to **create** a GSI that did not already exist:

```
Value '0' at 'globalSecondaryIndexUpdates.1.member.create.provisionedThroughput.writeCapacityUnits'
  failed to satisfy constraint: Member must have value greater than or equal to 1
Value '0' at 'globalSecondaryIndexUpdates.1.member.create.provisionedThroughput.readCapacityUnits'
  failed to satisfy constraint: Member must have value greater than or equal to 1
```

**Root cause:** the AWS SDK 2.x (cloud-sdk) upgrade of the entity (ION-16380) omitted the `@GsiConfig`
annotation on the three GSI partition-key getters. `extractGsiMetadata()` only assigns capacity when
`@GsiConfig` is present; with it absent, `GsiMetadata.readCapacity` / `writeCapacity` stayed at the
primitive `long` default `0L`, which was passed verbatim to the `UpdateTable` /
`addGlobalSecondaryIndex` call and rejected by DynamoDB. Table-level throughput in
`DynamoDbClientConfig` does **not** feed the per-GSI path, so there was no fallback.

---

## 2. Why it was missed (through review, CI and earlier deploys)

`createTableWithGsisIfNotExists()` builds a `ProvisionedThroughput` only for a GSI it must **create**.
In every long-lived environment the three entity-declared GSIs already existed, so the add-GSI branch
was skipped and the `0L` value was never exercised:

- QA `inttra2_qa_CargoVisibilitySubscription` — table created **2026-01-19**
- Prod `inttra2_prod_CargoVisibilitySubscription` — table created **2026-07-11**

Deploys to those environments therefore stayed green, and neither PR review nor CI exercised the
failing branch. The defect only surfaces where a declared GSI is **absent** — a fresh environment, or
one that never had that specific index.

---

## 3. Timeline (git + CloudTrail)

| When | Event | Evidence |
|---|---|---|
| 2026-01-19 | QA CVS table created | `describe-table` CreationDateTime |
| 2026-07-11 | Prod CVS table created | `describe-table` CreationDateTime |
| **2026-07-28 19:46 EDT** | AWS 2.x upgrade **authored** (`32608bbccb`, ION-16380) | `git show` author-date |
| 2026-08-13 11:21 EDT | Same commit's **commit-date** (rewritten by pre-merge rebase) | `git show` commit-date |
| **2026-08-13 18:09 UTC** | ION-16380 **merged to `develop`** — PR #1127 (`d5c6f5b9b5`), only merge of the ticket | `git log origin/develop` |
| 2026-08-22 15:36 / 16:32 UTC | ION-16650 fix merged — PR #1201 (`a2210ab56a`) + PR #1202 (`8a9a660d6f`); adds `@GsiConfig(readCapacity=25, writeCapacity=25, KEYS_ONLY)` + capacity normalisation | `git log origin/develop` |
| **2026-08-22 12:39–12:49 EDT** | **Prod GSIs created** on `inttra2_prod_CargoVisibilitySubscription` by operator instance `i-053ceaa3349162198`, read=25/write=25, KEYS_ONLY | CloudTrail `UpdateTable` |

### The "8/13" clarification (author vs commit vs merge)

The upgrade commit `32608bbccb` was **authored 2026-07-28** but its **commit date is 2026-08-13**
(rewritten by a rebase before the PR merge). It reached `develop` only on **2026-08-13** via PR #1127 —
the sole merge of ION-16380. So "committed before 8/13" and "merged 8/13" are both correct, just
different milestones. For deployment impact the merge-to-develop date (8/13) is the relevant one, and
the prod GSI creations (8/22) came after it regardless.

---

## 4. Was the prod table updated, and were the GSIs added after the upgrade?

**Yes — and with the fixed throughput.** CloudTrail `UpdateTable` events on
`inttra2_prod_CargoVisibilitySubscription` (operator instance `i-053ceaa3349162198`, not autoscaling):

- 2026-08-22 12:39:21 EDT — create `billOfLading-carrierInttraId-index` — read=25, write=25, KEYS_ONLY
- 2026-08-22 12:39:56 / 12:43:01 / 12:49:01 EDT — create `bookingNumber-carrierInttraId-index` — read=25, write=25, KEYS_ONLY (repeated because DynamoDB allows only one GSI build in flight at a time)

The **25/25** capacity exactly matches the ION-16650 `@GsiConfig` values, confirming the **fixed** build
performed the prod GSI creation (not the broken 0-capacity build). These two `carrierInttraId` indexes
did **not** exist on prod before 8/22 — i.e. between the table's 7/11 creation and 8/22 they were absent.

**Evidence limits:** no failed 0-capacity `UpdateTable` attempt was found in the operator-event scan of
the window just before the 8/22 fix deploy, but CloudTrail management events older than ~90 days are not
retained and autoscaling `UpdateTable` volume means the scan did not necessarily reach back to 8/13 —
so absence of a recorded failure is **not conclusive**. QA GSI-add history predates the 90-day window
(table from 2026-01-19) and is not observable.

---

## 5. Live DynamoDB verification (read-only `describe-table`)

Entity currently declares **3 GSIs**, all `KEYS_ONLY`, `25/25` (post-fix watermill copy):
`bookingNumber-carrierInttraId-index`, `billOfLading-carrierInttraId-index`, `subscriptionReference-index`.

**QA `inttra2_qa_CargoVisibilitySubscription`** (created 2026-01-19, ~85,966 items) — 6 GSIs, all ACTIVE, `KEYS_ONLY`, 5/5:
`bookingNumber-carrierInttraId-index`, `billOfLading-carrierInttraId-index`, `subscriptionReference-index` (current model) +
`bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index`, `bookingNumber-index` (legacy SCAC-era, no longer in the model).

**Prod `inttra2_prod_CargoVisibilitySubscription`** (created 2026-07-11, ~93,469 items) — 5 GSIs, all ACTIVE, `KEYS_ONLY`, 5/5:
`bookingNumber-carrierInttraId-index`, `billOfLading-carrierInttraId-index`, `subscriptionReference-index` +
`bookingNumber-carrierScac-index`, `billOfLading-carrierScac-index` (no `bookingNumber-index`).

> Live GSI throughput is **5/5** (created earlier / autoscaling-managed) while the code now requests
> **25/25**; since the GSIs already exist, `dynamo-create` will not re-apply 25/25 — that value only
> applies at first creation. Key schema and `KEYS_ONLY` projection match the model, so DAO queries stay
> consistent.

---

## 6. Related latent risk (same root cause) — NOT yet fixed

1. **`visibility-inbound` `ContainerEvent`** — `VisibilityInboundDynamoDbAdminCommand` runs the same
   `dynamo-create` flow for `container_events` (5 GSIs: `bookingNumber-index`, `blNumber-index`,
   `equipmentIdentifier-index`, `bkInttraReferenceNumber-equipmentIdentifier-index`,
   `siInttraReferenceNumber-index`). `ContainerEvent.java` has **zero `@GsiConfig`** annotations and its
   `resolveClientConfig` does **not** normalise capacity — the **identical defect** ION-16650 fixed for
   CVS. Masked today because `inttra2_qa/prod_container_events` already have all 5 GSIs (QA table created
   2019-07-18, 10/40, ACTIVE), but a fresh-environment deploy would fail the same way.
2. **CVS model drift** — the `visibility-commons` copy of `CargoVisibilitySubscription.java` (used by the
   DAO) still has **no `@GsiConfig`**, unlike the fixed `watermill-publisher` copy. Not a table-creation
   risk today (visibility-inbound's command does not register CVS; only the watermill command creates
   that table), but the copies have diverged and should be reconciled.

---

## 7. Recommendations

1. Apply the ION-16650 pattern to `ContainerEvent` (add `@GsiConfig` to all 5 GSI getters) and add
   capacity normalisation to `VisibilityInboundDynamoDbAdminCommand.resolveClientConfig`.
2. Reconcile the two `CargoVisibilitySubscription` copies (watermill vs visibility-commons), or collapse
   to one shared model, so `@GsiConfig` cannot drift.
3. Add a build-time guard/test (as ION-16650 did via `...SortTest`) that fails if any
   `@DynamoDbSecondaryPartitionKey` getter on a cloud-sdk entity lacks `@GsiConfig`; apply it across all
   AWS-2.x-upgraded modules.
4. Library-level: have the cloud-sdk `addGlobalSecondaryIndex` path fall back to table-level capacity
   when a `@GsiConfig` is missing, so a missing annotation can never produce `0`.

---

*All AWS interactions in this analysis were read-only (`describe-table`, CloudTrail `lookup-events`).
No DynamoDB scans were performed and no prod/QA AWS configuration or tables were modified.*
