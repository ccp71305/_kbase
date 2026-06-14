# Booking CONFIRM Record — PROD vs QA DynamoDB Field Format Differences

**Date:** 2026-06-08  
**Table:** BookingDetail  
**Record Type:** CONFIRM  
**Context:** QA runs the AWS SDK v2 migrated booking code; PROD runs the pre-migration (AWS SDK v1) code.  
Both records were created from the same booking confirmation scenario.

---

## Executive Summary

The CONFIRM record shows the **same three systemic issues** found in the REQUEST record comparison, plus **two additional issues** unique to the CONFIRM flow: party list reordering and location list shifting.

| Category | Count | Severity | Description |
|----------|-------|----------|-------------|
| Boolean type change (`N` → `BOOL`) | 6 | **HIGH** | Same fields as REQUEST — booleans stored as `N` in PROD, `BOOL` in QA |
| Null-value field expansion | 314 | **MEDIUM** | QA writes explicit `{"NULL": true}` for null fields (2x the REQUEST count due to more parties) |
| Data/field loss in QA | 36 | **HIGH** | `partyId` missing from all 16 party entries; location data nulled out |
| Party list ordering changed | 11 parties | **HIGH** | `transactionPartyList` order differs — only 2 of 11 entries match by index |
| Location list shifting | 3 locations | **HIGH** | `transactionLocationInfoList` entries are reordered; unresolved entry moves from last to first |
| Top-level field missing in QA | 1 | **MEDIUM** | `splitCopy` exists in PROD but absent in QA |

---

## Category 1: Boolean Type Mismatch — `N` (Number) → `BOOL`

**Identical to REQUEST record findings.** The same 6 fields are affected:

| Field Path | PROD (old) | QA (new) |
|------------|-----------|----------|
| `coreBooking` | `{"N": "0"}` | `{"BOOL": false}` |
| `nonInttraBooking` | `{"N": "0"}` | `{"BOOL": false}` |
| `enrichedAttributes.bookingWithMigratedParties` | `{"N": "1"}` | `{"BOOL": true}` |
| `enrichedAttributes.containerTypeList[0].displayFlag` | `{"N": "1"}` | `{"BOOL": true}` |
| `enrichedAttributes.containerTypeList[0].oogFlag` | `{"N": "0"}` | `{"BOOL": false}` |
| `enrichedAttributes.containerTypeList[0].spareIndicator` | `{"N": "0"}` | `{"BOOL": false}` |

**Root Cause:** AWS SDK v2 Enhanced Client uses native `BOOL` type for Java booleans; SDK v1 used `N`.

---

## Category 2: Null-Value Field Expansion (314 fields)

**Same pattern as REQUEST but larger scale** due to more party roles in a CONFIRM record (11 party roles vs 5 in REQUEST).

QA writes `{"NULL": true}` for all null Java fields; PROD omits them entirely.

### Per-Party NULL Fields (repeated for each party entry, ~11 fields per party)

| Field | Notes |
|-------|-------|
| `address.country.countryCodeType` | |
| `address.street01` | |
| `address.street02` | |
| `address.unstructuredAddress03` | sometimes `S` when populated |
| `address.unstructuredAddress04` | |
| `dunsNumber` | |
| `partyAlias` | |
| `partyName` | type `S` when populated — this is a **new field** in QA |
| `partyName2` | |
| `partyResolvedAlias` | |
| `passThroughCode` | |

### Affected Party Roles (partyMap)

11 roles × varying entry counts = many NULL fields:
- Booker (1), Carrier (1), Consignee (1), ContractParty (1), CustomsBroker (2), FirstAdditionalNotifyParty (1), Forwarder (2), FreightPayer (1), MainNotifyParty (1), SecondAdditionalNotifyParty (1), Shipper (2)

### Affected transactionPartyList

11 entries (indices 0–10), each with the same ~11 NULL fields.

### Other NULL-expanded fields

| Area | Fields |
|------|--------|
| `audit` | `createdByChannel`, `createdById`, `createdByType`, `lastModifiedBy`, `lastModifiedDateUtc` |
| `packageTypeList[0]` | `description`, `imoCode`, `type` |
| `transactionLocationInfoList` | `countryISO2Code`, `resolved`, `resolvedCountry` (per location) |

---

## Category 3: Data/Field Loss in QA (36 fields)

### 3a. `partyId` missing from ALL parties in QA

**16 party entries** across both `partyMap` and `transactionPartyList` are missing `partyId`:

**partyMap (all roles):**
| Role | PROD has `partyId` | QA |
|------|-------------------|-----|
| Booker | ✅ | **MISSING** |
| Carrier | ✅ | **MISSING** |
| Consignee | ✅ | **MISSING** |
| ContractParty | ✅ | **MISSING** |
| CustomsBroker[0] | ✅ | **MISSING** |
| CustomsBroker[1] | ✅ | **MISSING** |
| FirstAdditionalNotifyParty | ✅ | **MISSING** |
| Forwarder[0] | ✅ | **MISSING** |
| Forwarder[1] | ✅ | **MISSING** |
| FreightPayer | ✅ | **MISSING** |
| MainNotifyParty | ✅ | **MISSING** |
| SecondAdditionalNotifyParty | ✅ | **MISSING** |
| Shipper[0] | ✅ | **MISSING** |
| Shipper[1] | ✅ | **MISSING** |

**transactionPartyList:** All 11 entries (indices 0–10) are missing `partyId`.

> Same as REQUEST: QA retains `partyINTTRACompanyId`. Investigate whether `partyId` was intentionally removed.

### 3b. `partyScac` missing from Carrier

| Location | PROD | QA |
|----------|------|-----|
| `partyMap.Carrier[0].partyScac` | `{"S": "CA20"}` | **MISSING** |
| `transactionPartyList[5].partyScac` (PROD Carrier index) | `{"S": "CA20"}` | **MISSING** |

### 3c. Location data loss — resolved location fields become NULL in QA

QA's `transactionLocationInfoList[0]` has **all resolution data nulled out** while PROD has fully resolved values:

| Field | PROD Location[0] | QA Location[0] |
|-------|-------------------|-----------------|
| `locationType` | `{"S": "PlaceOfLoad"}` | `{"NULL": true}` |
| `identifierValue` | `{"S": "USNYC"}` | `{"NULL": true}` |
| `locationIdentifierType` | `{"S": "UNLOC"}` | `{"NULL": true}` |
| `geography` | full map (US) | `{"NULL": true}` |
| `country.status` | `{"S": "active"}` | `{"NULL": true}` |
| `resolved` | (absent) | `{"BOOL": false}` |

> **Note:** This is partially explained by the location reordering issue (Category 5). QA location[0] is the unresolved entry that PROD stores at index[2]. However, PROD's resolved location[0] data (PlaceOfLoad/USNYC) appears at QA location[1] with `resolved: true`, so **no actual data loss occurred** — only positional shifting.

### 3d. `metaData.notificationParties` missing in QA

Same as REQUEST record — PROD has `{"L": []}`, QA omits entirely.

### 3e. Shipper state field

| Path | PROD | QA |
|------|------|-----|
| `partyMap.Shipper[0].address.state` | `{"S": "SALTA"}` | `{"NULL": true}` |

> Likely data-dependent (different test company profile).

---

## Category 4: `transactionPartyList` Ordering Changed ⚠️ NEW

**This issue is unique to the CONFIRM record comparison and was not detected in REQUEST.**

The `transactionPartyList` entries appear in **completely different order** between PROD and QA. Only 2 of 11 entries are at the same index:

| Index | PROD Role | QA Role | Match? |
|-------|-----------|---------|--------|
| 0 | Consignee | FreightPayer | ❌ |
| 1 | Shipper | Shipper | ✅ |
| 2 | MainNotifyParty | Carrier | ❌ |
| 3 | ContractParty | CustomsBroker | ❌ |
| 4 | CustomsBroker | Forwarder | ❌ |
| 5 | Carrier | FirstAdditionalNotifyParty | ❌ |
| 6 | FreightPayer | SecondAdditionalNotifyParty | ❌ |
| 7 | Forwarder | Consignee | ❌ |
| 8 | Booker | Booker | ✅ |
| 9 | FirstAdditionalNotifyParty | ContractParty | ❌ |
| 10 | SecondAdditionalNotifyParty | MainNotifyParty | ❌ |

**Impact:**
- Any consumer that accesses parties **by index position** will get wrong data.
- The contact data differences (e.g., phones at index 4 in PROD vs emails at index 4 in QA) are **not real data loss** — they are caused by different parties being at those indices.
- If the list is treated as **unordered** (keyed by `partyRole`), this is benign.

**Root Cause:** The AWS SDK v2 Enhanced Client likely uses a `HashMap` or unordered collection for the `partyMap`, which produces a different iteration order when building `transactionPartyList`. The legacy SDK v1 code may have used an insertion-ordered structure (e.g., `LinkedHashMap`).

**Recommendation:** Verify whether any downstream consumer relies on party list ordering. If ordering matters, use a `LinkedHashMap` or sort by `partyRole` before serialization.

---

## Category 5: `transactionLocationInfoList` Ordering Changed ⚠️ NEW

The location entries are also **shifted** between PROD and QA:

| Index | PROD (locationType / identifier) | QA (locationType / identifier) |
|-------|----------------------------------|--------------------------------|
| 0 | PlaceOfLoad / USNYC | **NULL / NULL** (unresolved, `resolved: false`) |
| 1 | FirstForeignPortOfAcceptance / USEWR | PlaceOfLoad / USNYC (`resolved: true`) |
| 2 | _(unresolved — no locationType/identifier)_ | FirstForeignPortOfAcceptance / USEWR (`resolved: true`) |

**Analysis:**
- PROD puts resolved locations first, unresolved last.
- QA puts unresolved location first, resolved locations after.
- The same data is present in both — just at different positions.
- QA adds new fields `resolved` (BOOL) and `resolvedCountry` (BOOL) to track resolution status — these are absent in PROD.

**Impact:** Same as party ordering — consumers relying on index position will get incorrect data.

---

## Category 6: Top-Level Field Missing in QA

| Field | PROD | QA |
|-------|------|-----|
| `splitCopy` | `{"N": "0"}` | **absent** |

Same finding as REQUEST record.

---

## Cross-Reference with REQUEST Record Findings

| Issue | REQUEST | CONFIRM | Notes |
|-------|---------|---------|-------|
| Boolean N→BOOL | 6 fields | 6 fields (same) | Systemic — affects all record types |
| NULL expansion | 153 fields | 314 fields | Scales with # of parties |
| `partyId` missing | 10 entries | 16 entries | Systemic — all party types affected |
| `partyScac` missing | Carrier only | Carrier only | Consistent |
| `splitCopy` absent | ✅ | ✅ | Consistent |
| `metaData.notificationParties` absent | ✅ | ✅ | Consistent |
| Party list reordering | Not observed | **9 of 11 differ** | May be data-dependent or CONFIRM-specific |
| Location list shifting | Partial | **All 3 shifted** | QA inserts unresolved first |
| Location data loss | Real loss (some) | **Apparent only** (reordering) | CONFIRM has no real loss, just shifting |

---

## Summary of Action Items

| # | Action | Priority | Category |
|---|--------|----------|----------|
| 1 | **Fix boolean serialization** — ensure backward-compatible read for both `N` and `BOOL` types | P0 | Cat 1 |
| 2 | **Investigate `partyId` removal** — confirm if intentional or regression (affects 16+ parties per CONFIRM) | P0 | Cat 3a |
| 3 | **Fix party list ordering** — use `LinkedHashMap` or sorted collection to ensure deterministic order | P0 | Cat 4 |
| 4 | **Fix location list ordering** — ensure unresolved entries don't shift to front | P1 | Cat 5 |
| 5 | **Investigate `partyScac` removal** from Carrier party | P1 | Cat 3b |
| 6 | **Investigate `splitCopy` removal** — confirm if intentional | P1 | Cat 6 |
| 7 | **Configure null handling** — suppress `{"NULL": true}` for absent fields | P2 | Cat 2 |

---

## Appendix: Files Compared

| Environment | File | BookingId |
|-------------|------|-----------|
| PROD (pre-migration) | `PROD-DianamoDBJSON-ConfirmBK.txt` | _(from same booking scenario)_ |
| QA (post-migration) | `QA-DianamoDBJSON-ConfirmBK.txt` | _(from same booking scenario)_ |

Both records: `payloadType=ConfirmPending`, `state=CONFIRM`, `version=1`

Party roles present (11): Booker, Carrier, Consignee, ContractParty, CustomsBroker (×2), FirstAdditionalNotifyParty, Forwarder (×2), FreightPayer, MainNotifyParty, SecondAdditionalNotifyParty, Shipper (×2)
