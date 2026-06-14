# Booking REQUEST Record — PROD vs QA DynamoDB Field Format Differences

**Date:** 2026-06-08  
**Table:** BookingDetail  
**Record Type:** REQUEST  
**Context:** QA runs the AWS SDK v2 migrated booking code; PROD runs the pre-migration (AWS SDK v1) code.  
Both records were created from the same booking scenario.

---

## Executive Summary

The AWS SDK migration in the booking module introduced **three categories of format differences** in how booking REQUEST records are persisted to DynamoDB:

| Category | Count | Severity | Description |
|----------|-------|----------|-------------|
| Boolean type change (`N` → `BOOL`) | 6 | **HIGH** | Booleans stored as `N("0"/"1")` in PROD are now `BOOL(true/false)` in QA |
| Null-value field expansion | 153 | **MEDIUM** | QA writes explicit `{"NULL": true}` for fields PROD omits entirely |
| Data/field loss in QA | 23 | **HIGH** | Fields present with real values in PROD are missing or NULL in QA |
| Top-level field missing in QA | 1 | **MEDIUM** | `splitCopy` exists in PROD but absent in QA |

---

## Category 1: Boolean Type Mismatch — `N` (Number) → `BOOL`

**Root Cause:** AWS SDK v2 Enhanced Document Client uses native `BOOL` DynamoDB type for Java `boolean`/`Boolean` fields, whereas the legacy code (AWS SDK v1) serialized booleans as `N` (number: `0` or `1`).

**Impact:** Any consumer reading these fields with a fixed type expectation (e.g., expecting `N`) will fail to deserialize QA records. Conversely, code written for `BOOL` will fail on PROD records. This is a **backward-compatibility break** if both code versions coexist or if PROD data is read by the new code.

| Field Path | PROD (old) | QA (new) |
|------------|-----------|----------|
| `coreBooking` | `{"N": "0"}` | `{"BOOL": false}` |
| `nonInttraBooking` | `{"N": "0"}` | `{"BOOL": false}` |
| `enrichedAttributes.bookingWithMigratedParties` | `{"N": "1"}` | `{"BOOL": true}` |
| `enrichedAttributes.containerTypeList[0].displayFlag` | `{"N": "1"}` | `{"BOOL": true}` |
| `enrichedAttributes.containerTypeList[0].oogFlag` | `{"N": "0"}` | `{"BOOL": false}` |
| `enrichedAttributes.containerTypeList[0].spareIndicator` | `{"N": "0"}` | `{"BOOL": false}` |

### Recommendation

The DynamoDB model classes (or custom converters) must handle **both** `N` and `BOOL` types during the migration transition period. Options:
1. Add a custom `AttributeConverter` that reads both `N` and `BOOL` and always writes `BOOL`.
2. Run a one-time data migration to convert existing `N`-based booleans to `BOOL` after PROD deployment.
3. Configure the Enhanced Client's `@DynamoDbConvertedBy` to use a backward-compatible converter.

---

## Category 2: Null-Value Field Expansion (QA writes `NULL` for absent fields)

**Root Cause:** AWS SDK v2 Enhanced Client serializes all Java object fields by default, including those with `null` values, as `{"NULL": true}` in DynamoDB. The legacy SDK v1 code skipped null fields entirely (did not write them to the item).

**Impact:** This increases item size and storage cost but is **functionally benign** for reads — `{"NULL": true}` and a missing attribute both evaluate to `null` when deserialized. However, it changes the DynamoDB item schema shape and may affect:
- DynamoDB Streams consumers that diff old/new images
- Conditional expressions using `attribute_exists()` / `attribute_not_exists()`
- Item size limits (400 KB) for very large records

**Total fields affected:** 153

### Affected Areas (grouped by object)

#### `audit` (5 fields)
| Field | PROD | QA |
|-------|------|-----|
| `createdByChannel` | absent | `{"NULL": true}` |
| `createdById` | absent | `{"NULL": true}` |
| `createdByType` | absent | `{"NULL": true}` |
| `lastModifiedBy` | absent | `{"NULL": true}` |
| `lastModifiedDateUtc` | absent | `{"NULL": true}` |

#### Party objects — `partyMap` and `transactionPartyList` (per-party pattern, ~11 fields each)

The following fields are written as `{"NULL": true}` in QA but absent in PROD, for **every party** (Booker, Carrier, CustomsBroker, Forwarder, Shipper) in both `partyMap` and `transactionPartyList`:

| Field | Notes |
|-------|-------|
| `address.country.countryCodeType` | |
| `address.street01` | |
| `address.street02` | |
| `address.unstructuredAddress04` | |
| `dunsNumber` | |
| `partyAlias` | |
| `partyName` | New field in QA (type `S` when populated, `NULL` when not) — see Category 3 note |
| `partyName2` | |
| `partyResolvedAlias` | |
| `passThroughCode` | |

#### `packageTypeList[0]` (3 fields)
| Field | PROD | QA |
|-------|------|-----|
| `imoCode` | absent | `{"NULL": true}` |
| `type` | absent | `{"NULL": true}` |
| `x12Code` | absent | `{"NULL": true}` |

#### `transactionLocationInfoList` (per-location pattern)

New fields written in QA for each location entry:

| Field | Notes |
|-------|-------|
| `countryISO2Code` | type `S` when populated |
| `resolved` | type `BOOL` |
| `resolvedCountry` | type `BOOL` |
| `country.status` | sometimes `S`, sometimes `NULL` (see Category 3) |
| `geography` | sometimes `M` (map), sometimes `NULL` (see Category 3) |
| `identifierValue` | sometimes `S`, sometimes `NULL` |
| `locationIdentifierType` | sometimes `S`, sometimes `NULL` |
| `locationType` | sometimes `S`, sometimes `NULL` |

### Recommendation

Configure the Enhanced Client table schema to **ignore nulls** on write using `@DynamoDbIgnoreNulls` or a custom mapper configuration, to match PROD behavior and minimize item bloat. Alternatively, accept the expanded schema if downstream consumers are compatible.

---

## Category 3: Data/Field Loss in QA (Fields with values in PROD but missing/NULL in QA)

**This is the most critical category.** These are fields that carry real data in PROD but are absent or explicitly `NULL` in QA, indicating a potential **serialization bug** in the migrated code.

### 3a. `partyId` missing from all parties in QA

| PROD Field Path | PROD Value | QA |
|-----------------|------------|-----|
| `partyMap.Booker[0].partyId` | `{"S": "802442"}` | **MISSING** |
| `partyMap.Carrier[0].partyId` | `{"S": "802435"}` | **MISSING** |
| `partyMap.CustomsBroker[0].partyId` | `{"S": "802443"}` | **MISSING** |
| `partyMap.Forwarder[0].partyId` | `{"S": "802442"}` | **MISSING** |
| `partyMap.Shipper[0].partyId` | `{"S": "802441"}` | **MISSING** |
| `transactionPartyList[0].partyId` | present | **MISSING** |
| `transactionPartyList[1].partyId` | present | **MISSING** |
| `transactionPartyList[2].partyId` | present | **MISSING** |
| `transactionPartyList[3].partyId` | present | **MISSING** |
| `transactionPartyList[4].partyId` | present | **MISSING** |

> **Note:** QA has `partyINTTRACompanyId` which holds the same value. The `partyId` field may have been intentionally removed or renamed. **Verify the model class to confirm whether `partyId` was dropped or if this is a regression.**

### 3b. `partyScac` missing from Carrier in QA

| PROD Field Path | PROD Value | QA |
|-----------------|------------|-----|
| `partyMap.Carrier[0].partyScac` | `{"S": "CA20"}` | **MISSING** |
| `transactionPartyList[2].partyScac` | `{"S": "CA20"}` | **MISSING** |

### 3c. Location data loss — fields with real values in PROD become NULL in QA

| PROD Field Path | PROD Value | QA Value |
|-----------------|------------|----------|
| `transactionLocationInfoList[2].country.status` | `{"S": "active"}` | `{"NULL": true}` |
| `transactionLocationInfoList[2].geography` | full geography map (NLRTM) | `{"NULL": true}` |
| `transactionLocationInfoList[2].identifierValue` | `{"S": "NLRTM"}` | `{"NULL": true}` |
| `transactionLocationInfoList[2].locationIdentifierType` | `{"S": "UNLOC"}` | `{"NULL": true}` |
| `transactionLocationInfoList[3].locationType` | `{"S": "PlaceOfLoad"}` | `{"NULL": true}` |
| `transactionLocationInfoList[6].country.status` | `{"S": "active"}` | `{"NULL": true}` |
| `transactionLocationInfoList[6].geography` | full geography map (NLRTM) | `{"NULL": true}` |
| `transactionLocationInfoList[6].identifierValue` | `{"S": "NLRTM"}` | `{"NULL": true}` |
| `transactionLocationInfoList[6].locationIdentifierType` | `{"S": "UNLOC"}` | `{"NULL": true}` |

> **This may be a data-dependent difference** (QA test data may not have resolved these locations), or it may indicate the enrichment/resolution step is not running correctly in QA.

### 3d. Other value losses

| PROD Field Path | PROD Value | QA Value |
|-----------------|------------|----------|
| `partyMap.Shipper[0].address.state` | `{"S": "SALTA"}` | `{"NULL": true}` |
| `transactionPartyList[2].address.state` | `{"S": "ARKANSAS"}` | `{"NULL": true}` |
| `transactionPartyList[4].address.country.countryCodeValue` | `{"S": "FI"}` | `{"NULL": true}` |

> These could be data-dependent differences from different test company profiles in PROD vs QA.

---

## Category 4: Top-Level Field Missing in QA

| Field | PROD | QA |
|-------|------|-----|
| `splitCopy` | `{"N": "0"}` | **absent** |
| `metaData.notificationParties` | `{"L": []}` | **absent** |

> `splitCopy` may have been intentionally removed in the migration. Verify the model class.

---

## Summary of Action Items

| # | Action | Priority | Category |
|---|--------|----------|----------|
| 1 | **Fix boolean serialization** — ensure backward-compatible read for both `N` and `BOOL` types during migration | P0 | Cat 1 |
| 2 | **Investigate `partyId` removal** — confirm if intentional (renamed to `partyINTTRACompanyId`) or regression | P0 | Cat 3a |
| 3 | **Investigate `partyScac` removal** from Carrier party | P1 | Cat 3b |
| 4 | **Investigate location data loss** — determine if data-dependent or enrichment bug | P1 | Cat 3c |
| 5 | **Investigate `splitCopy` removal** — confirm if intentional | P1 | Cat 4 |
| 6 | **Configure null handling** — suppress writing `{"NULL": true}` for absent fields to match PROD behavior | P2 | Cat 2 |
| 7 | **Plan data migration strategy** — decide how to handle existing `N`-type booleans when PROD is upgraded | P2 | Cat 1 |

---

## Appendix: Files Compared

| Environment | File | BookingId |
|-------------|------|-----------|
| PROD (pre-migration) | `PROD-DianamoDBJSON-RequestBK.txt` | `70e09110320e4136960b5da7ee962882` |
| QA (post-migration) | `QA-DianamoDBJSON-RequestBK.txt` | `ab762eddbc0c4134b64bcda7165721aa` |

Both records: `payloadType=RequestAmend`, `state=REQUEST`, `channel=EDI`, `version=1`
