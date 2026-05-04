# Booking Module — Business Rules & Validations (Improved Reference)

> **Date:** May 4, 2026  
> **Based on:** [booking-business-rules.md](booking-business-rules.md) + source code analysis  
> **Purpose:** Consolidation and improvement of the existing business rules document with newly identified rules, edge cases, and undocumented logic from source code exploration.

---

## Improvements Over Previous Document

This document enhances the original `booking-business-rules.md` with:

1. **Outbound diff generation strategy** — only last 2 versions compared (§12)
2. **Subscription condition evaluation** — full token map construction, SO booking handling, grouped vs non-grouped routing (§12)
3. **Push notification email splitting** — Booker vs non-Booker when `sendLegalTerms=true` (§12)
4. **NIB three-part eligibility check** — core booking existence + config flag + carrier OV rule (§7 addendum)
5. **Migration logic detail** — participant migration by channel (WEB/EDI/DESKTOP), booker-shipper existence check (§13 addendum)
6. **Elasticsearch optimistic locking** — version-based indexing with 409 conflict retry (§11 addendum)
7. **Rapid Reservation two-level range rolling** — range1/range2 shift-down mechanics (§14 addendum)
8. **Template auto-expiration** — `calcExpiresOn()` updated on every access, location deletion edge case (§15 addendum)
9. **Carrier-specific EDI customizations** — ZIM region routing, Heineken reference filtering, special character YAML configs (§12 addendum)
10. **Watermill event publishing** — S3 workspace file creation, carrier metadata enrichment (§12 addendum)

---

## Table of Contents

1. [Module Overview & Architecture](#1-module-overview--architecture)
2. [Entry Points — REST Controllers](#2-entry-points--rest-controllers)
3. [Entry Points — SQS / Inbound Processing](#3-entry-points--sqs--inbound-processing)
4. [Entry Points — Lambda Handlers](#4-entry-points--lambda-handlers)
5. [State Machine](#5-state-machine)
6. [Service Layer Business Rules](#6-service-layer-business-rules)
7. [Non-INTTRA Booking (NIB) Rules](#7-non-inttra-booking-nib-rules)
8. [Validation Plans — All Rules by Message Type](#8-validation-plans--all-rules-by-message-type)
9. [Validation Rules — Grouped by Domain](#9-validation-rules--grouped-by-domain)
10. [Authorization Rules](#10-authorization-rules)
11. [Split Booking Rules](#11-split-booking-rules)
12. [Reinstatement Rules (ION-9016)](#12-reinstatement-rules-ion-9016)
13. [Outbound Pipeline & Subscription Routing](#13-outbound-pipeline--subscription-routing)
14. [Migration Logic & Legacy Booking Detection](#14-migration-logic--legacy-booking-detection)
15. [Data Models](#15-data-models)
16. [DAO & Persistence Rules](#16-dao--persistence-rules)
17. [Elasticsearch Indexing & Search](#17-elasticsearch-indexing--search)
18. [Lambda Processing Rules](#18-lambda-processing-rules)
19. [Converters & Mappers](#19-converters--mappers)
20. [Carrier Spot Rates](#20-carrier-spot-rates)
21. [Rapid Reservation](#21-rapid-reservation)
22. [Template Service](#22-template-service)
23. [Dangerous Goods (DGS) Service](#23-dangerous-goods-dgs-service)
24. [Carrier-Specific Customizations](#24-carrier-specific-customizations)
25. [Configuration & Feature Flags](#25-configuration--feature-flags)
26. [External Integrations](#26-external-integrations)
27. [Error Code Reference](#27-error-code-reference)
28. [Constants Quick Reference](#28-constants-quick-reference)

---

## 1. Module Overview & Architecture

The **booking** module is the core transactional engine of the Mercury platform. It manages the end-to-end lifecycle of ocean freight bookings — from initial customer request through carrier confirmation/decline/replacement — exposing capabilities over REST, EDI (SQS), and event-driven (Lambda) interfaces.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Booking Module                                  │
│                                                                              │
│  ┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐           │
│  │  REST APIs     │   │ SQS Listener     │   │  Lambda          │           │
│  │ Customer/      │   │ (Inbound EDI)    │   │  (DynamoDB       │           │
│  │ Carrier/Search │   │ 8-thread pool    │   │   Streams)       │           │
│  └──────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘           │
│         │                      │                       │                     │
│         └──────────────────────┴───────────────────────┘                     │
│                                │                                             │
│              ┌─────────────────▼──────────────────┐                          │
│              │       ValidationService            │                          │
│              │  (24 validator classes, OV rules)   │                          │
│              └─────────────────┬──────────────────┘                          │
│                                │                                             │
│              ┌─────────────────▼──────────────────┐                          │
│              │        BookingService               │                          │
│              │  (Orchestrator, 1227 lines)         │                          │
│              └─────────────────┬──────────────────┘                          │
│                                │                                             │
│     ┌──────────────┬───────────┼────────────┬──────────────┐                │
│     ▼              ▼           ▼            ▼              ▼                │
│  ┌────────┐  ┌──────────┐ ┌────────┐ ┌──────────┐  ┌───────────┐          │
│  │DynamoDB│  │Outbound  │ │  S3    │ │  Event   │  │Elasticsearch│          │
│  │BookDAO │  │Service   │ │Archive │ │  Logger  │  │  Indexer    │          │
│  │(7 tbl) │  │(32-thrd) │ │        │ │  (SNS)   │  │             │          │
│  └────────┘  └────┬─────┘ └────────┘ └──────────┘  └─────────────┘          │
│                    │                                                         │
│     ┌──────────────┼──────────────────────────┐                             │
│     ▼              ▼                          ▼                             │
│  ┌──────────┐ ┌──────────┐            ┌──────────────┐                     │
│  │Email/SES │ │SQS Dist. │            │  Watermill   │                     │
│  │Templates │ │Queue     │            │  Analytics   │                     │
│  └──────────┘ └──────────┘            └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Packages

| Package | Purpose | Key Classes |
|---|---|---|
| `resources/` | JAX-RS REST controllers | `CustomerBookingResource`, `CarrierBookingResource`, `SearchResource` |
| `service/` | Core orchestration | `BookingService` (1227 lines), `ValidationService`, `BookingLocator`, `BookingAuthorizer` |
| `validation/` | Cross-cutting rule engine | 24 validator classes grouped by domain |
| `inbound/` | EDI/SQS message processing | `BookingProcessorTask` (716 lines), `MigrationLogic`, `NonInttraBookingValidator` |
| `outbound/` | Notification pipeline | `OutboundServiceImpl`, `OutboundEmailService`, `DiffGenerator`, `SubscriptionConditionEvaluator` |
| `model/` | Domain types, DTOs | `Booking`, `BookingDetail`, `BookingRequestContract` |
| `dao/` | DynamoDB access | `BookingDetailDao`, `RapidReservationDao`, `UniqueIdDao` |
| `dynamodb/` | DynamoDB attribute converters | 12+ type converters |
| `elasticsearch/` | ES query DSL & indexing | `Indexer`, `Searcher`, `ElasticsearchSupport` |
| `lambda/` | Lambda handlers | `IndexerHandler`, `S3ArchiveHandler` |
| `dgs/` | Dangerous Goods rules | UN number lookup, DGS validation |
| `carrierrule/` | Optional Validation (OV) | Carrier-configurable rule engine |
| `carrierspotrates/` | Maersk spot-rate integration | `CarrierSpotRatesService`, `MaerskApiClient` |
| `rapidreservation/` | Pre-allocated booking numbers | `RapidReservationService` |
| `template/` | Saved booking templates | `TemplateService` |
| `networkservices/` | Network API clients | Hystrix-wrapped REST clients |
| `outbound/custom/` | Carrier EDI customizations | `CustomizationHandler`, ZIM/Heineken-specific |
| `common/` | AWS, events, messaging, S3 | `S3WorkspaceService`, `EventLogger` |

---

## 2. Entry Points — REST Controllers

### `CustomerBookingResource` — Base path `/`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/{inttraReferenceId}` | (any) | Retrieves booking; `NotFoundException("bookingNotFound")` if not visible. Applies `BackwardCompatibilityUtil.mergeSegregationGroups` and `fixAddressMess` (migrates `street01/02` → `unstructuredAddress01/02`). |
| `POST` | `/request` | `BOOKING_RAC` | Auto-fills Booker `TransactionParty` from `NetworkParticipantService`. Truncates Address fields (street1/2/3/city) to **35 chars** via reflection over `@Size(max=…)` annotations. Adds `InformationContact` from User principal's phone+name if missing. |
| `POST` | `/{inttraReferenceId}/amend` | `BOOKING_RAC` | Throws `IllegalArgumentException("illegalBookingState")` if `bookingState != AMEND`. |
| `POST` | `/{inttraReferenceId}/cancel` | `BOOKING_RAC` | Builds `CancelMessage`; sets `transactionContact` of type `InformationContact` from User/Client. |
| `DELETE` | `/{inttraReferenceId}` | `BOOKING_ADMIN` | Throws `NotFoundException` on `DBRecordNotFoundException`. |
| `GET` | `/ov/{carrierId}` | (any) | Returns list of carrier-rule names; lazy `ValidationContext` with no booking. |

### `CarrierBookingResource` — Base path `/`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `POST` | `/{inttraReferenceId}/confirm` | `BOOKING_CPD` | Sets reference & channel; calls `bookingService.confirm`. |
| `POST` | `/{inttraReferenceId}/confirm/validate` | `BOOKING_ADMIN` | Dry-run validation only (no persist). |
| `POST` | `/{inttraReferenceId}/decline` | `BOOKING_CPD` | Wraps comments into `DeclineReplaceMessage` with `BookingState=DECLINE`. Sets `transactionContact` with `ContactType=ConfirmedWith`. |
| `POST` | `/{inttraReferenceId}/replace` | `BOOKING_CPD` | Replace workflow. |
| `POST` | `/{inttraReferenceId}/acknowledge` | `BOOKING_CPD` | Pending workflow. |
| `POST` | `/{inttraReferenceNumber}/s3archive` | `BOOKING_ADMIN` | Manually re-archives all `BookingDetail`s to S3. |

### `SearchResource` — Base path `/search`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/{inttraReferenceNumber}` | (any) | Find by INTTRA ref. |
| `POST` | `/{inttraReferenceNumber}/reindex` | `BOOKING_ADMIN` | Force Elasticsearch re-index. |
| `POST` | `/simple` | (any) | `complianceRisk` excluded from source unless `cargoScreenTrialPeriod=true` OR `cargoScreenPreference.isCargoScreenBookingAllowed`. Aggregations: STATE, CARRIER_ID, LAST_MODIFIED_DATE, CREATED_BY. |
| `GET` | `/summary?rangeInDays=N` | (any) | Booking summary by company/date range. |
| `GET` | `/hasaccess` | (any) | Looks up user's companyId; `NotFoundException("User info not found")` if user not found. Returns total results > 0. |
| `GET` | `/bookingforBL` | INTTRA-only | Returns 403 if caller is not Inttra company (`INTTRA_COMPANY_ID_INTEGER`). Queries by BL number + carrier SCAC + booking state; returns latest carrier + customer versions. |

### `OutboundResource` — Base path `/outbound`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/{inttraReferenceId}?versionnumber=` | (any) | Enriched booking detail. |
| `POST` | `/{inttraRef}/reprocess` | `BOOKING_ADMIN` | Re-runs subscription action for sequenceNumber/subscriptionHashKey/inttraCompanyId. |
| `POST` | `/{inttraRef}/email` | `BOOKING_ADMIN` | Re-sends enriched email. |

### `DangerousGoodsResource` — Base path `/dgs`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/undg/{undg}?variant=` | `BOOKING_RAC` | `400 BAD_REQUEST` if `undg ≤ 0` or non-numeric; `404` if not found. |

### `RapidReservationResource` — Base path `/rapid-reservation`

| Method | Endpoint | Role |
|---|---|---|
| `POST` | `/` | `BOOKING_ADMIN` |
| `POST` | `/{inttraCompanyId}/{name}/add-range` | `BOOKING_ADMIN` |
| `DELETE` | `/{inttraCompanyId}?name=` | `BOOKING_ADMIN` |

### `TemplateResource` — Base path `/template` (User principals only)

`listTemplates`, `GET /{name}`, `PUT /{name}` (save), `DELETE /{name}`.

### `CarrierSpotRatesResource` — Base path `/carrier-spot-rates`

- `GET /{inttraCompanyId}` — `IllegalArgumentException` if container JSON invalid.
- `POST /saveLinkToInttraRef`
- `GET /isSpotRateBooking/{inttraReferenceId}`

---

## 3. Entry Points — SQS / Inbound Processing

### `SQSListener`
- Long-polls AWS SQS queue (`waitTimeSeconds` default 20s, `maxNumberOfMessages` default 10).
- Empty/null `queueUrl` → `IllegalArgumentException`.
- Messages deleted from queue **only** on successful processing.
- Network retry exhaustion (`"Could not connect / retrieve"` in `InternalException` or `UncheckedExecutionException`): message is **NOT** deleted; relies on SQS visibility timeout (~2 min) for automatic retry.

### `BookingProcessorTask.execute()` — Central Dispatcher (716 lines)

**Constants:**
```
RAC = "requestBooking"
CPD = "confirmBooking"
EDI_CLIENT = "BOOKING_ADMIN"
INTTRA_ID = "1000"
INTTRAREF_SEED_VALUE = 2_000_000_000L
```

**Processing Flow:**

```
SQS Message
     │
     ▼
Read MetaData (messageId, workflowId, rootWorkflowId, contextCode, S3 filename)
     │
     ▼
Pull payload from S3 (appianWayConfig.s3WorkSpaceLocation)
     │
     ▼
shouldProcess()
 ├── INTTRA reference < 2,000,000,000 → route to bookingBridgeSQS (legacy)
 │   Log: "Ignoring legacy booking with INTTRA reference {}"
 └── Continue →
     │
     ▼
Structural Error Check:
 ├── exitStatus == EXIT_STATUS_FAILURE → fetch annotations from S3
 └── isStructuralError = true → StructuralValidationException (non-recoverable)
     │
     ▼
Custom Jackson deserialization (EnumDeserializer + NumberDeserializer)
 ├── Unknown enums / number-format errors → captured in errors list
 └── If isStructuralError OR errors exist AND context is RAC/CPD
         → throw StructuralValidationException
     │
     ▼
Route by contextCode (RAC/CPD) and bookingState:
 ├── RAC
 │    ├── REQUEST  → strips inttraRef if present (prevents stale ref)
 │    │             removes INTTRAReferenceNumber from references list
 │    │             → bookingService.request(actor, contract, metaData)
 │    ├── AMEND   → bookingService.amend(actor, contract, metaData)
 │    └── CANCEL  → bookingService.cancel(actor, cancelMessage, metaData)
 │         missing state → ResolutionException("000304", "Booking State Invalid/Missing")
 └── CPD
      ├── CONFIRM  → bookingService.confirm(...)
      ├── PENDING  → bookingService.pending(...)
      ├── REPLACE  → bookingService.replace(...)
      └── DECLINE  → bookingService.decline(...)
           missing carrier → ResolutionException("215053", ...)
           NIB + Pending → StateTransitionException("213002", ...)
```

**Non-Inttra Booking (NIB) detection in CPD path:**
- If `carrierRequest.getInttraReference() == null`: `nonInttraBookingValidator.checkforCarrierIdAndCarrierReference` + `shouldProcessNonInttraBooking`.
- NIB **cannot** be in `Pending` state (`BookingResponseType.Pending`) → `StateTransitionException("213002")`.

**Network API Failure Auto-Retry:**
- Detects Network API failures via exception message containing `"Could not connect / retrieve"`
- Two exception types trigger retry: `InternalException` (direct) and `UncheckedExecutionException` (Guava cache wrapping)
- Message NOT deleted from SQS → remains for visibility timeout re-delivery

**Exception → Outbound Error Channels:**

| Exception | Handler | Retryable? |
|---|---|---|
| `TransformationException` | `outboundService.processTransformationErrors` | No |
| `StructuralValidationException` | `outboundService.processBusinessErrors` | No |
| `AuthorizationException` | `outboundService.processBusinessErrors` | No |
| `BookingNotFoundException` | `outboundService.processBusinessErrors` | No |
| `ResolutionException` | `outboundService.processBusinessErrors` | No |
| `BookingValidationException` | `outboundService.processBusinessErrors` | No |
| `StateTransitionException` | `outboundService.processBusinessErrors` | No |
| `InternalException` | `outboundService.processInternalError` | **Yes** (if network failure) |
| `Exception` (generic) | `outboundService.processInternalError` | **Yes** (if network pattern) |

**Success callback:** Only invoked if `reprocessInbFailure == false`. If true → message remains in SQS for next consumer thread.

---

## 4. Entry Points — Lambda Handlers

### `IndexerHandler` — DynamoDB Stream → Elasticsearch

Triggered by SNS → SQS wrapping DynamoDB stream events.

| Event | Action |
|---|---|
| `INSERT` / `MODIFY` | `Indexer.index(booking)` — skipped if `booking.isCoreBooking()` AND `enableCoreBookingSearch=false` |
| `REMOVE` | `Indexer.delete(inttraReferenceNumber)` — parsed from `sequenceNumber` split on `_`, position 3 |

- Retries up to `MAX_RETRIES_PROPERTY` (default **5**).

### `S3ArchiveHandler` — DynamoDB Stream → S3

Processes **INSERT** events only.

- Archives `BookingDetail` JSON to `s3ArchiveBucket`.
- Uses `soS3ArchiveBucket` for `SOBookingRequestContract` / `SOCancelContract`.
- Skips core bookings if `ENABLE_CORE_BOOKING_ARCHIVE=false`.
- S3 key format: `YYYY/MM/DD/HH/{bookingId}_{sequenceNumber}` (UTC).
- Computes `uniqueVersionId` = `inttraRef + 3-digit version` and `splitCopy` flag.
- Optional Track-and-Trace POST when `tntEnabled=true` and `tntAPI` + `tokenEnv` configured.

---

## 5. State Machine

### Valid Booking States

| State | Active? | Carrier Status? | Context Code |
|---|---|---|---|
| `REQUEST` | Yes | No | RAC |
| `AMEND` | Yes | No | RAC |
| `PENDING` | Yes | Yes | CPD |
| `CONFIRM` | Yes | Yes | CPD |
| `DECLINE` | No | Yes | CPD |
| `CANCEL` | No | No | RAC |
| `REPLACE` | No | Yes | CPD |

`ACTIVE = {REQUEST, PENDING, CONFIRM, AMEND}`
`INACTIVE = {DECLINE, CANCEL, REPLACE}`
`CARRIER_STATUSES = {PENDING, CONFIRM, DECLINE, REPLACE}`

### State Transition Table

```
                        TO STATE
                ┌────┬──────┬───────┬─────────┬─────────┬────────┬─────────┐
FROM STATE      │ RQ │ AMND │ CNCL  │ PENDING │ CONFIRM │ DECLIN │ REPLACE │
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
null            │ ✓  │  —   │  —    │ ignore  │  ✓      │ ignore │ ignore  │
REQUEST         │ —  │  ✓   │  ✓    │  —      │  —      │  —     │  —      │
AMEND           │ —  │  ✓   │  ✓    │  ✓      │  ✓      │  ✓     │  ✓      │
PENDING         │ —  │  ✓   │  ✓    │  ✓      │  ✓      │  ✓     │  ✓      │
CONFIRM         │ —  │  ✓   │  ✓    │ ✗(213001)│  ✓     │  ✓     │  ✓      │
DECLINE         │ —  │  ✗   │ ignore│  ✓*     │  ✓*     │  ✓     │  ✓*     │
CANCEL          │ —  │  ✗   │  ✓    │  ✓*     │  ✓*     │  ✗     │  ✓*     │
REPLACE         │ —  │  ✗   │ ignore│ ✗(213001)│✗(213001)│✗(213001)│✗(213001)│
└───────────────┴────┴──────┴───────┴─────────┴─────────┴────────┴─────────┘

✓  = Allowed
✗  = Throws StateTransitionException(213001)
✓* = Allowed only via ION-9016 reinstatement (see §12)
ignore = Silently ignored, no error
```

> **Rule:** `Carrier_CounterParty` (customer actor) can never transition to/from REPLACE.

---

## 6. Service Layer Business Rules

### 6.1 BookingService (1,227 lines)

**Constants:**

| Constant | Value | Purpose |
|---|---|---|
| `MAX_RR_ATTEMPTS` | 3 | Max retries for Rapid Reservation duplicate detection |
| `ERROR_213001` | `"213001"` | State transition error |
| `INTTRAREF_SEED_VALUE` | `2,000,000,000` | Minimum value for Mercury INTTRA references |
| TTL (expiresOn) | `now + 400 days` | Booking DynamoDB TTL |

#### `request(actor, BookingRequestContract, MetaData)`
```
1. validationService.validate(actor, contract, metaData)
2. Collect EnrichedAttributes
3. If errors → throw BookingValidationException
4. If no BookingNumber reference present:
     └── assignRapidReservedCarrierBookingNumber()
           do { attempt++ } while (rrNumberAlreadyExists && attempt < 3)
5. BookingServiceUtil.supplementNatureOfCargo(contract)
6. BookingServiceUtil.trimPackageDescription(contract)
7. create(...) with state=REQUEST → produces bookingId + inttraRef
8. valueAddedServicesLog → Sumo log VAS offers
9. If APPLIED or APPLIED_WITH_WARNINGS:
     └── outboundService.processOutbound(...)
10. If ContractNumber reference + spotRateId present:
      └── saveContractNumberIfSpotRateBooking(...)
```

#### `amend(actor, BookingRequestContract, MetaData)`
```
1. BookingState.calcTransition(prev, Carrier_CounterParty, AMEND)
2. Supplement package fields
3. outboundService.processOutbound(...)
```

#### `cancel(actor, CancelMessage, MetaData)`
```
1. bookingLocator.getBooking(null, companyId, msg)
2. filterBookerAndCarrier → truncate parties list
3. Skip if state already in {CANCEL, DECLINE, REPLACE}
```

#### `confirm / pending / decline / replace` (carrier paths)
```
if contract.isSplit():
    └── doSplit(...)
else if booking exists OR hasMigratedParties:
    └── doConfirm / doPending / doDecline / doReplace(...)
bookingReinstatementService.validateReinstatement(...)  ← ION-9016 uniqueness
```

#### Access Check — `hasAccess(actorCompanyId, booking)`
```
Booking visible if:
  booking.calcAllCompanyIdsWithAccess() contains actorCompanyId
  OR any of actor's children companies (via networkParticipantService.getAllChildren)
```

#### Deduplication — `update(...)`
```
If booking.isEquivalent(contract) == true → result = IGNORED (no write, no outbound)
```

#### DynamoDB Resilience — `newBookingDetail(...)`
```
Retry DynamoDbException up to config.getDynamoExceptionMaxRetryCount()
On ultimate failure → write dynamo_error/{workflowId} to S3 workspace
```

#### Booking ID Generation
- `calcBookingId()` = UUID without dashes
- INTTRA reference generated via `idGenerator.getUniqueId(carrierPartyId)`
- Per-carrier prefix strategy when `inttraRefConfig.carrierCompanyIds` includes carrier (e.g. ZIM `850803`)

#### Address Field Truncation (reflective)
`truncateStringValuesForTransactionParty` — reflects over `@Size(max=…)` annotations on `TransactionParty` / `Address` / `Contact.name` and truncates to the declared maximum.

#### VAS Logging — `valueAddedServicesLog`
Writes Sumo log entry for VAS offers: `currencyCode`, `containerType`, `amount`, `quantity`, `placeOfReceipt`, `placeOfDelivery`, `earliestDepartureDate`, `latestArrivalDate`.

---

### 6.2 ValidationService

#### Context Building Rules

1. If `state == null` → `ResolutionException("000304", "Booking State is Invalid/Missing.")`
2. **Carrier statuses** (CONFIRM/PENDING/DECLINE/REPLACE):
   - Only carrier resolution; calls `partyValidations.verifyCarrier`
3. **Customer statuses**:
   - Booker resolved under owner `1000`; carrier resolved under booker first, then Inttra fallback
   - Booker-country enrichment → ISO Alpha-2 via `LocationEnrichment.getCountryByName`

#### Pre-Processing Transformations (before validation rules)

| Transformation | Logic |
|---|---|
| `formatMarksAndNumbers` | Split marks on `"#$%"` regex tokens, trim each token |
| `convertFromTNE` | Non-RoRo/non-Breakbulk: weight type `TNE` → × 1000 → `KGM`. Applies to: `goodsGrossWeight`, `goodsNetWeight`, `splitGoodsDetails.grossWeight`, `dangerousGoods.netNetWeight`, DG split weights, `equipment.netWeight` |
| `reArrangePackagesInLineItemOrder` | Non-carrier status, when any INNER/INNERINNER present: reorder to OUTER 1 → INNER 1 → INNERINNER 1 → OUTER 2 → INNER 2 sequence |
| `collectParties` | Also resolves `HaulageParty` from each equipment haulage point |
| `collectPackageTypes` | IMO code type → `referenceDataService.getDangerousPackageType`; else `getPackageType` |
| `collectContainerTypes` | Only for `EquipmentSizeCodeType.ISO` |

---

### 6.3 BookingLocator

#### `findByInttraReferenceNumber(ref)`
- Miss → `BookingNotFoundException("206084", "INTTRA Ref provided must reference a single booking…")`

#### `getBooking(carrierId, bookerId, contract)` routing:

```
if inttraReference != null:
    look up; miss → BookingNotFoundException("206084")
else if state ∈ CARRIER_STATUSES:
    → findBookingForCarrierMessage
else:
    → findBookingForRequesterMessage
```

#### `findBookingForRequesterMessage(bookerId, contract)`:

| Condition | Result |
|---|---|
| 0 active bookings + `state == REQUEST` | `null` → proceed to create |
| 0 active bookings + non-REQUEST | `BookingNotFoundException("221005")` |
| >0 bookings + `state == REQUEST` | `ResolutionException("221001")` — duplicate shipmentId |
| Multiple active + no carrierReferenceNumber to disambiguate | `ResolutionException("221006")` |
| Still ambiguous after disambiguation | `ResolutionException("221103")` |
| Missing bookerId/shipmentId + non-REQUEST | `ResolutionException("224003")` |

#### `findBookingForCarrierMessage(carrierId, contract)`:

| Condition | Result |
|---|---|
| Split → uses `carrierSourceBookingNumber` | Latest by `createdDateUtc` |
| Non-split → uses `carrierReferenceNumber` | Latest by `createdDateUtc` |
| Missing carrier + ref + state == CONFIRM | `ResolutionException("224160")` |
| Missing carrier + ref + other states | `ResolutionException("224002")` |

---

### 6.4 BookingAuthorizer

#### Carrier-Status Messages
```
Brand-swap exemption:
  if no prior CONFIRM/DECLINE exists → skip carrier-match check
Otherwise:
  existing carrierId must match inbound carrier
  Mismatch → AuthorizationException("224016")
```

#### Customer-Status Messages

| State | Rule | Error |
|---|---|---|
| REQUEST | Booker must be activated for carrier (`connectionsService.verify`) | `285` |
| REQUEST | Submitter must be in hierarchy OR partnership with booker | `200816` |
| AMEND | Actor must be associated with resolved customer parties | `221009` |
| CANCEL | Same logic as AMEND | `221010` |

---

### 6.5 BookingReinstatementService

Activated when `fromState ∈ {DECLINE, CANCEL}` (ION-9016).

```
1. Sets contract.setReinstated(true)
2. Finds latest customer detail with non-blank shipmentId
   (among REQUEST / AMEND / CANCEL states)
3. Calls BookingReinstatementValidations.shipmentIdMustBeUnique(
     shipmentId, bookerId, inttraRef, originalInttraRef, false)
4. Throws BookingValidationException if any errors
```

---

## 7. Non-INTTRA Booking (NIB) Rules

**NEW SECTION** — Consolidates NIB handling scattered across multiple classes.

### Three-Part Eligibility Check

All three conditions must be true for NIB processing:

```
1. !coreBookingExists — No legacy core booking in Elasticsearch
   (Searches ES for matching carrier ID + carrier reference number)
2. isNonInttraProcessingEnabled() — Config flag from AWS SSM parameter
3. isCarrierEnabled(carrierParty) — Carrier has OV rule "standAloneBookingMigrated"
```

### NIB vs INTTRA Split Reconfirm Detection

When `carrierRequest.getInttraReference() == null`:
- Could be a true NIB **OR** a split reconfirm of an INTTRA booking
- Elasticsearch check: `checkforCarrierIdAndCarrierReference()` to find indexed bookings
- `isInttraSplitReconfirm(indexedBookings)` differentiates the two cases

### NIB Constraints

- NIB **cannot** be in `Pending` state → `StateTransitionException("213002")`
- Sets metadata projection: `IS_NON_INTTRA_BOOKING = "true"`
- Subscription routing uses `BOOKING_SOURCE = "NON_INTTRA"` token

---

## 8. Validation Plans — All Rules by Message Type

### 8.1 `BookingRequestContract` (REQUEST / AMEND)

Rules run in order by `ValidationPlanFactory`:

| # | Rule | Class | Error Code |
|---|---|---|---|
| 1 | JSR-303 Bean Validation | `ValidationSupport.mustBeJsr303Valid` | Various |
| 2 | Dimension validation | `DimensionValidations.validateDimensions` | `102030` |
| 3 | MoveType exists | `MoveTypeValidations.checkMoveTypeExists` | `666666` |
| 4 | Party roles + max occurrences | `PartyValidations.checkParties`, etc. | `215054` |
| 5 | Header locations | `HeaderLocationValidations.executeHeaderLocationRules` | `200030`, `200042`, `200031` |
| 6 | Shipper/Forwarder existence | `PartyValidations.checkShipperFreightForwarderExists` | `200771` |
| 7 | Request leg dates | `RequestLegValidations.executeRequestLegRules` | Various |
| 8 | Contract vs tariff number | `requestAmendReferenceValidations` | `200061` |
| 9 | Location date range + format | `requestAmendLocationValidations` | ±400 days |
| 10 | Charge payment terms | `PartyValidations.checkForCharges` | `214002` |
| 11 | Reference length | `requestAmendReferenceValidations.checkReferenceLength` | `999990` |
| 12 | Haulage parties | `PartyValidations.checkForHaulageParties` | `200664` |
| 13 | Smart container | `CarrierValidations.smartContainerAllowed` | `300001` |
| 14 | Sanctioned countries | `InttraValidations.isBookingFromOrToSanctionedCountry` | `UNAUTHORIZED_TRANSACTION` |
| 15 | DGS net weight | `CarrierValidations.dgsNetWeightRequired` | `300002` |
| 16 | RoRo allowed | `CarrierValidations.isRoRoAllowed` | `300003` / `300007` |
| 17 | Breakbulk allowed | `CarrierValidations.isBreakbulkAllowed` | `300004` / `300008` |
| 18 | Out-of-gauge constraints | `CarrierValidations.outOfGaugeWithinConstraints` | `300005` |
| **REQUEST-only** | | | |
| 19 | OCBN uniqueness | `BookerValidations.carrierReferenceNumberMustBeUnique` | `200065` |
| 20 | Equipment count | `requestAmendEquipmentValidations.checkEquipmentCount` | `221108` |
| 21 | Cargo count | `requestAmendCargoValidations.checkCargoCount` | `221056` |
| 22 | SMBN allowed | `CarrierValidations.doesCarrierAllowSMBN` | `200068` |
| 23 | ShipmentId exists (EDI) | `BookerValidations.checkShipmentIdExists` | `666660` |
| **AMEND-only** | | | |
| 24 | OCBN must match | `BookerValidations.carrierReferenceNumberMustMatch` | `200069` |
| 25 | Carrier on record | `CarrierValidations.matchCarrierOnRecord` | `200118` |
| 26 | Reject non-Inttra | `BookerValidations.rejectIfNonInttra` | `000200` |
| 27 | Booker party present | `BookerValidations.checkForBookerParty` | `206809` |
| 28 | Request→Amend transition | `CarrierValidations.isRequestToAmendStateTransitionAllowed` | `300006` |
| 29 | Amend→Amend transition | `CarrierValidations.isAmendToAmendStateTransitionAllowed` | `300006` |
| **All** | | | |
| 30 | Carrier OV rules | `optionalValidationsService.getOptionalValidations(carrierId)` | Carrier-specific |
| 31 | Inttra OV rules | `optionalValidationsService.getOptionalValidations("1000")` | Platform-wide |
| 32 | Equipment validations | `requestAmendEquipmentValidations.executeEquipmentValidations` | See §9.3 |
| 33 | Cargo validations | `requestAmendCargoValidations.executeCargoValidations` | See §9.4 |
| 34 | Sea waybill count | `requestAmendDocumentValidations.validateNumberOfSeaWayBills` | `999990`, `303030` |

### 8.2 `CancelMessage`

| # | Rule | Error Code |
|---|---|---|
| 1 | JSR-303 Bean Validation | Various |
| 2 | Party role count (Booker/Carrier only) | `215054` |
| 3 | Booking must exist | `206084` |
| 4 | Party checks + contact max | Various |
| 5 | Carrier on record | `200118` |
| 6 | Smart container | `300001` |
| 7 | Reject non-Inttra | `000200` |

### 8.3 `ConfirmPendingMessage`

| # | Rule | Error Code |
|---|---|---|
| 1 | JSR-303 Bean Validation | Various |
| 2 | RoRo/Breakbulk checks | `300003`/`300004` |
| 3 | Max container count (>999) | `228008` |
| 4 | Header location rules | `215020`, `224075` |
| 5 | Party validations | Various |
| 6 | Reference length | `999990` |
| 7 | Equipment number duplicate | `215170` |
| 8 | Cargo validations | Various |
| 9 | Equipment codes | `215171` |
| 10 | Carrier booking number (CONFIRM only) | `224160` |
| 11 | OCBN uniqueness | `200065`/`206065` |
| 12 | Transport leg validation | Various |
| 13 | Header dates (±400 days) | `206009`/`206010` |
| 14 | Container net weight | `215180` |
| 15 | Haulage dates | Per `HaulageDateType` |
| 16 | Equipment reference length | `999990` |
| 17 | Response type | `224018` |
| 18 | CTA/COM check | `228007` |
| 19 | Booker party | `206809` |
| 20 | Number of containers | `206763` |
| 21 | Haulage arrangement code | `206590` |
| 22 | Contact max occurrences | `228008` |
| 23 | Haulage parties | `200664` |
| 24 | Reefer validations | Temp/NAR rules |

### 8.4 `DeclineReplaceMessage`

| # | Rule | Error Code |
|---|---|---|
| 1 | JSR-303 Bean Validation | Various |
| 2 | Carrier comments required | `206800` |
| 3 | Message date | `206010` |
| 4 | Creation date | `206009` |
| 5 | CTA/COM | `228007` |
| 6 | Booker party | `206809` |
| 7 | Contact max occurrences | `228008` |

---

## 9. Validation Rules — Grouped by Domain

### 9.1 Header & Location Validations

#### REQUEST/AMEND

| Error Code | Condition |
|---|---|
| `200030` | Place of Receipt (POR) missing |
| `200042` | Place of Delivery (POD) missing |
| `200031` | POR and POD are the same location |
| `221020` | More than one of any `LocationType` (except Prohibited/Requested Transshipment) |
| `215020` | UNLOC unresolved for key location types |
| `221023` | Alias unresolved |
| `215023` | Country code mismatch between resolved location and provided code |
| `333333` | LocationType not in `LocationType.VALID_HEADER_LOCATIONS` |

#### Location Date Rules

| Error Code | Condition |
|---|---|
| `200037` | Must provide EarliestDeparture at POR, LatestDelivery at POD, or MainCarriage leg with vessel+conveyanceNumber |
| `200039` | EarliestDeparture at POR not within ±400 days |
| `200040`/`200048` | LatestDelivery at POD range/format error |
| `221024`/`221025` | Date format errors |
| `215024`/`215025` | Invalid date values |

### 9.2 Party Validations

**Constants:**
- `MAX_CONTACT_COMM_COUNT = 9` (phones + faxes + emails per Contact)
- Accepted party roles: `Carrier, Consignee, Shipper, ContractParty, FreightPayer, Forwarder, MessageRecipient, MainNotifyParty, FirstAdditionalNotifyParty, SecondAdditionalNotifyParty, Booker, CustomsBroker`
- Haulage party roles: `{EmptyPickUp, IntermediateStopOff, ReeferSubcontractor, ShipFrom, ShipTo}`

#### Party Identity & Role Rules

| Error Code | Condition |
|---|---|
| `228003` | Party role not in accepted list |
| `215054` | Duplicate party role |
| `215066` | Non-Booker/non-Carrier party missing all identifiers |
| `215067` | Invalid INTTRA Company ID |
| `224102` | Invalid Partner Alias |
| `200771` | Neither Shipper nor Forwarder present |
| `200773` | Neither Shipper nor Forwarder has a party identifier |
| `200774` | Neither Shipper nor Forwarder resolved |
| `214002` | Charge `paymentTerm` not in `{PayableElsewhere, Prepaid, Collect}` |
| `200664` | Haulage party missing phone/email/fax on EquipmentContact |

#### Contact Communication Rules

| Error Code | Condition |
|---|---|
| `200130` | InformationContact name missing while phone/email/fax provided |
| `200132` | InformationContact name present but no communication details |
| `200131` | Contact name contains only dots/spaces |
| `200134` | Phone contains only dots/spaces |
| `200138` | Fax contains only dots/spaces |
| `200135` | Email > 512 characters |
| `200140` | Notification contact missing email |
| `200407` | MessageRecipient party has no notification contact |
| `228008` | Total emails + phones + faxes per Contact > 9 |
| `228007` | Contact name (CTA) present without any communication (COM) |

#### Resolution Rules

| Error Code | Party | Condition |
|---|---|---|
| `ResolutionException("221030")` | Booker | Null booker |
| `ResolutionException("221033")` | Booker | Both partyId and alias missing |
| `ResolutionException("215067")` | Booker | Unresolved by INTTRA ID |
| `ResolutionException("221037")` | Booker | Unresolved by alias |
| `ResolutionException("215053")` | Carrier | Null carrier |
| `ResolutionException("224099")` | Carrier | Both partyId and alias missing |
| `ResolutionException("215067")` | Carrier | Unresolved by INTTRA ID |
| `ResolutionException("224101")` | Carrier | Unresolved by alias |

### 9.3 Equipment Validations

#### REQUEST/AMEND

| Error Code | Condition |
|---|---|
| `215171` | Invalid equipment size/type code |
| `200800` | Equipment count ≠ 1 when container identifier provided |
| `200801` | `ServiceType=FCLFCL` count missing or < 1 |
| `200663` | Haulage party InformationContact with details but missing name |
| `215285` | Haulage party missing all identifiers + name |
| `997009` | Fumigation date not in `CCYYMMDDHHMM` format |
| `997019` | Equipment haulage arrangement code mandatory |
| `997020` | Invalid haulage arrangement enum |
| `221108` | REQUEST with FCLFCL must include equipment (unless RoRo/BreakBulk) |

#### CONFIRM/PENDING

| Error Code | Condition |
|---|---|
| `215170` | Duplicate equipment identifier (container number) |
| `215171` | Invalid equipment size code |
| `215180` | Container Net Weight invalid (must be positive, ≤ 3 decimals) |
| `206763` | `numberOfContainers ≠ 1` when equipment identifier provided |
| `206590` | Different haulage arrangement codes across equipment groups |
| `228008` | Equipment count > 999 |
| `215343` | Invalid date for ReeferSubcontractor haulage |

#### Haulage Date Type Rules (CONFIRM/PENDING)

| Date Type | Allowed Party Role | Error Code |
|---|---|---|
| `EmptyPositioningDate` | `ShipFrom` only | `215289` |
| `FullPickUpDateTime` | `ShipFrom` or `IntermediateStopOff` | `215291` |
| `StopOffPositioningDate` | `IntermediateStopOff` only | `224139` |
| `EstimatedDoorDeliveryDate` | `ShipTo` only | `224141` |
| `EmptyPickupDate` | `EmptyPickUp` only | `224143` |
| `EarliestDropOffDate` | `FullDropOFF` only | `224145` |
| `ClosingDate` | `FullDropOFF` only | `224147` |

#### Reefer / Controlled Atmosphere Rules

| Error Code | Condition |
|---|---|
| `200614` | Reefer container missing temperature and not set to non-active reefer |
| `200615` | Non-reefer/non-hybrid container with temperature or NAR |
| `215235` | Reefer handling fields present without active temperature |
| `200616` | Temperature set on non-active reefer container |
| `215184` | Humidity or AirFlow value has more than 2 decimal places |
| `215332` | Container temperature invalid format |

### 9.4 Cargo Validations

#### REQUEST/AMEND

| Error Code | Condition |
|---|---|
| `997023` | Missing line item number |
| `997024` | Line item number > 5 characters |
| `997016` | Duplicate Outer/SingleLine line number |
| `997017` | INNER without corresponding OUTER |
| `997018` | INNERINNER without corresponding INNER |
| `215094` | Gross/Net weight invalid (positive, ≤ 3 decimals) |
| `215097` | Gross volume invalid (positive, ≤ 4 decimals) |
| `215095` | `marksAndNumbers` exceeds 9 lines |
| `215096` | Marks element > 35 characters |
| `999990` | Reference length exceeded |
| `997015` | Invalid `PackageTypeCodeType` |
| `996003` | Package count not in `[1, 99,999,999]` |
| `996004` | Package count provided without `typeValue`/`typeDescription` |
| `997021` | Package count missing without packageType |
| `996005` | Package type missing |
| `996006` | Package type value not in reference data |
| `996016` | DG outer pack count missing or ≤ 0 |
| `996017` | DG outer pack `typeValue`/`typeDescription` missing |
| `997022` | Split goods missing equipment identifier |
| `221063` | Split goods container number not matching equipment group |
| `221056` | Zero packages on REQUEST |

#### Dangerous Goods (DGS) Rules

| Error Code | Condition |
|---|---|
| `215333` | UN number missing |
| `996019` | UNDG variant > 4 characters |
| `215147` | Proper shipping name missing |
| `215331` | Flashpoint format invalid |
| `996007`/`996008` | DG net-net weight invalid |
| `996009`/`996010` | DG net volume invalid |
| `996011` | DG emergency contact missing phone |
| `996012`/`996013` | Radioactivity value invalid |
| `996014`/`996015` | Acid concentration invalid |
| `996018` | End-of-holding-time format must be `CCYYMMDD` |
| `997010` | Deprecated `segregationGroup` field used |
| `997013` | More than 4 segregation groups |
| `997012` | `None` mixed with other segregation groups |
| `997014` | Inhalant hazard not in `{A, B, C, D, true}` |
| `997011` | Both SADT and SADP provided (mutually exclusive) |

### 9.5 Reference Validations

| Reference Type | Max Length | Error Code |
|---|---|---|
| `UniqueConsignmentNumber` | 45 | `999990` |
| `CanadianCargoControlNumber` | 45 | `999990` |
| `CarrierSourceBookingNumber` | 30 | `999990` |
| `BookingNumber` | 30 | `999990` |
| All other reference types | 35 | `999990` |

| Error Code | Condition |
|---|---|
| `200061` | Both ContractNumber and FreightTariffNumber present |
| `200065` | Active booking with same OCBN for carrier (REQUEST) |
| `200068` | SMBN present but carrier OV `submitterBookingNumberAllowed` not enabled |
| `200069` | OCBN mismatch on AMEND |
| `206065` | Different INTTRA ref with same active OCBN (CONFIRM/PENDING) |
| `224160` | CONFIRM without carrier booking number |

### 9.6 Leg Validations

| Error Code | Condition |
|---|---|
| `215329` | Multiple arrival/departure dates for same leg endpoint |
| `215051` | `CCYYMMDD` date format invalid |
| `215052` | `CCYYMMDDHHMM`/`CCYYMMDDHHMMSS` format invalid |
| `200117` | EstimatedArrivalDate with non-PlaceOfDischarge leg |
| `200116` | EstimatedDepartureDate with non-PlaceOfLoad leg |

### 9.7 Dimension Validations

| Error Code | Condition |
|---|---|
| `102030` | Out-of-gauge package missing length/width/height, or null type/value |

**OOG conversion:** `ValidationHelper.convertToFeet` — Inch/Centimeter/Meter → feet. Special case: 253 m → 830 ft (ZIM workaround override).

### 9.8 Carrier Optional Validations (OV)

Carrier-configurable rules via `@ValidationRuleInfo(ruleName=…)` annotation reflection.

| Rule Name | Description | Error Code |
|---|---|---|
| `submitterBookingNumberAllowed` | Activates SMBN | no-op |
| `spotRateBookingAllowed` | Allows spot rate bookings | no-op |
| `smartContainerAllowed` | Allows smart container equipment | no-op |
| `contractOrTariffNumberRequired` | Contract or tariff number must be present | `201202` |
| `cargoWeightRequired` | Cargo gross weight mandatory | `201229` |
| `hsCodeRequired` | HS code required on cargo | `201228` |
| `emptyPositioningDateRequiredWithShipFrom` | ShipFrom must include empty positioning date | `201232` |
| `fullPickUpDateTimeRequiredWithShipFrom` | ShipFrom must include full pick-up date/time | `201233` |
| `bookingOfficeRequired` | Booking office location mandatory | `201236` |
| `contractPartyRequired` | Contract party must be included | `233180` |
| `consistentTemperatureSettingsRequired` | Reefer/hybrid must have consistent temperature | `200617` |
| `noDecimalsAllowedInTemperatureSettings` | Temperature must be whole number | `201999` |
| `emergencyDangerousGoodsContactRequired` | DG emergency contact mandatory | `201227` |
| `basicFreightOriginAndDestinationChargesRequired` | Must include OceanFreight + OriginTerminalHandling + DestinationTerminalHandling | `233176` |
| `departureDatesMustBeInTheFuture` | Departure dates must be > now (UTC) | `233177` |
| `transportModeRequiredForPreOrOnCarriageLegs` | PreCarriage/OnCarriage must specify transport mode | `233178`/`233179` |
| `specificChargeTypesRequired` | Specific charge types must be present | `233181` |
| `dangerousGoodsAndNonDangerousGoodsMustNotBeInSameBooking` | DG and non-DG cannot be mixed | `233182` |
| `partyAddressRequired` | Forwarder/Shipper must include address | `233181` |
| `outOfGaugeWithinConstraints` | OOG within carrier limits | `300005` |
| `disableBookingForLocations` | Sanctioned location check | `UNAUTHORIZED_TRANSACTION` |
| `requestToAmendStateTransitionNotAllowed` | Blocks REQUEST→AMEND until carrier responds | `300006` |
| `amendToAmendStateTransitionNotAllowed` | Blocks AMEND→AMEND until carrier responds | `300006` |
| `standAloneBookingMigrated` | **NEW** — Enables NIB processing for carrier | (gating flag) |

OV conditions evaluated via `context.isActivated(conditions, conditionOperator)` — checks channel, POR/POD country, container type, etc.

### 9.9 Inttra Validations (Sanctioned Countries)

```
1. Load Inttra-owned OV rule "disableBookingForLocations"
2. Error if:
   a. Booker's country is on sanctioned list, OR
   b. Requester's country is on sanctioned list, OR
   c. BOTH of:
      - Neither POR UNLOC nor POD UNLOC is on the permitted list
      - Either POR or POD country code is on the sanctioned list
→ Error: UNAUTHORIZED_TRANSACTION
   "At present we are not authorized to process this transaction."
```

---

## 10. Authorization Rules

```
┌──────────────────────────────────────────────────────────────┐
│                   Authorization Flow                          │
│                                                              │
│  REQUEST:                                                    │
│  1. connectionsService.verify(bookerId, CARRIER, carrierId)  │
│     NO → AuthorizationException("285")                       │
│  2. Submitter in hierarchy/partnership with booker?           │
│     NO → AuthorizationException("200816")                    │
│                                                              │
│  AMEND: Actor associated with resolved customer parties?     │
│     NO → AuthorizationException("221009")                    │
│                                                              │
│  CANCEL: Same logic as AMEND                                 │
│     NO → AuthorizationException("221010")                    │
│                                                              │
│  CARRIER messages:                                           │
│    If prior CONFIRM/DECLINE exists:                          │
│      carrierId must match → else AuthorizationException      │
│      ("224016")                                              │
│    No prior CONFIRM/DECLINE: brand-swap allowed (skip)       │
└──────────────────────────────────────────────────────────────┘
```

---

## 11. Split Booking Rules

`BookingService.doSplit(...)` — `isCarrierSplitAllowed(...)`:

```
Split ALLOWED when ALL of:
  ├── contract.isSplit() == true
  ├── originalState ∈ {REPLACE, CONFIRM, PENDING, REQUEST, AMEND}
  └── splitState ∈ {CONFIRM, PENDING, DECLINE}

Otherwise → StateTransitionException("213001")
```

On split:
- All active details cloned with new `inttraReferenceNumber`
- `originalInttraReferenceNumber` preserved on cloned details
- OCBN uniqueness check applies to split-CONFIRM

---

## 12. Reinstatement Rules (ION-9016)

```
Trigger: fromState ∈ {DECLINE, CANCEL}
         toState   ∈ {PENDING, CONFIRM, REPLACE}

Actions:
1. contract.setReinstated(true)
2. Find latest customer detail with non-blank shipmentId
   (across REQUEST / AMEND / CANCEL details)
3. shipmentIdMustBeUnique(shipmentId, bookerId, inttraRef, originalInttraRef, false)
4. Throw BookingValidationException on failure
```

---

## 13. Outbound Pipeline & Subscription Routing

**NEW SECTION** — Significantly expanded from original document.

### Processing Flow

```
BookingService.processOutbound()
        │
        ▼
OutboundServiceImpl
  │
  ├── 1. Subscription Discovery
  │     ├── Non-grouped subscriptions → evaluate & execute first
  │     └── Grouped subscriptions → priority queue → sorted → evaluated in order
  │
  ├── 2. Condition Evaluation (SubscriptionConditionEvaluator)
  │     Token map constructed from:
  │     ├── Place of Receipt: UNLOC + Country Code
  │     ├── Port of Load: UNLOC + Country Code
  │     ├── Booking Office: UNLOC + Country Code
  │     ├── Booker's Location: UNLOC + Country Code
  │     ├── Booking State: context-sensitive
  │     │   └── SO booking → "requestSO" (special case)
  │     ├── Booking Source: "INTTRA" vs "NON_INTTRA"
  │     └── DGS Flag: boolean via booking.hasDangerousGoods()
  │
  ├── 3. VAS Preference Processing
  │     └── If subscription does NOT prefer SENDVASDETAILS
  │           → nullify valueAddedServiceOffers
  │     └── If preferred AND offer has carrierUniqueResponseId
  │           → auto-add BRReference with type InternalDataProcessNumber
  │
  ├── 4. VAS Supplementation (conditional)
  │     └── Applied if !detail.isNonInttraBooking()
  │         Preference: BK_INCLUDE_BOOKINGENHANCEMENTS
  │         Uses: SupplementationUtil.supplementCustomerLoadReference()
  │
  ├── 5. Special Character Processing
  │     ├── Carrier-specific: customization/splchar.yaml (per carrier SCAC)
  │     └── Generic: accent character removal (if carrier has no specific config)
  │
  ├── 6. EDI Customizations
  │     ├── Region tokens (ZIM-specific routing)
  │     ├── Global ID overrides (per subscription target)
  │     ├── Company-specific customizations
  │     └── Reference filtering (Heineken-specific)
  │
  ├── 7. Diff Generation (DiffGenerator)
  │     ├── Compares ONLY last 2 booking details (not all history)
  │     ├── EquipmentDiff, PackageDetailsDiff, TransportLegDiff
  │     └── Null filtering applied; errors logged but non-fatal
  │
  ├── 8. Enrichment
  │     ├── LocationEnrichment
  │     ├── PartyEnrichment
  │     ├── EquipmentEnrichment
  │     └── PackageEnrichment
  │
  ├── 9. Email Distribution
  │     ├── Template selection by booking state
  │     ├── Push Notification splitting:
  │     │   ├── sendLegalTerms=true → Booker emails separate from non-Booker
  │     │   │   (Blacklist filtering ONLY on non-Booker emails)
  │     │   └── sendLegalTerms=false → all emails combined
  │     └── Deduplication via .distinct()
  │
  ├── 10. SQS Distribution
  │     └── Send to distributor queue for EDI/API partner delivery
  │
  └── 11. Watermill Analytics Publishing
        ├── Enriches detail with carrier info from NetworkParticipant
        ├── S3 key: watermill_<rootWorkflowId>/<randomUUID>
        ├── One action = one SQS message
        └── Projection: CONTEXT_CODE, TARGET_TYPE="Watermill_SQS"
```

### Email Templates

| State | Template |
|---|---|
| REQUEST/AMEND | `RequestAmendEmailVariablesConverter` |
| CONFIRM/PENDING | `ConfirmPendingEmailVariablesConverter` |
| DECLINE/REPLACE | `DeclineReplaceEmailVariablesConverter` |
| CANCEL | `CancelEmailVariablesConverter` |
| Validation Error | Validation error template |
| Internal Error | Internal error template |

### Error → Outbound Channels

| Error Type | Outbound Channel |
|---|---|
| `TransformationException` | APERAK (transformation error) |
| Business validation errors | APERAK + Email |
| Internal errors | Internal error email |

---

## 14. Migration Logic & Legacy Booking Detection

**NEW SECTION** — Documents `MigrationLogic.java` rules.

### RAC Migration Eligibility (3-step check)

```
Step 1: Resolve Booker party from INTTRA ID "1000"
Step 2: Verify Booker is migrated via isParticipantMigrated(booker, channel)
Step 3: If inttraReference exists:
          Must be numeric & >= INTTRAREF_SEED_VALUE (2B)
          Else → DROP booking (legacy)
        If inttraReference is null:
          Allow only for REQUEST
          Or for AMEND/CANCEL if booker-shipper relationship exists
```

### Participant Migration Check

| Channel | Check Method |
|---|---|
| WEB | `isUIMigrated` |
| EDI | `isEDIAndXMLMigrated` |
| DESKTOP | `isDesktopMigrated` |

Queries NetworkParticipant for module status:
- Module = "Booking"
- Checks: `migrated` value + `migratedDate` (must be in past)

### Booker-Shipper Existence Check (AMEND/CANCEL without reference)

```
Call findByBookerIdAndShipmentIdIncludeCoreBooking()
If NO bookings found → ALLOW (new SA booking)
If bookings found:
  If LAST booking is isCoreBooking() → REJECT (drop message)
  Else → ALLOW (cloud booking exists)
```

---

## 15. Data Models

### Domain Entities

#### `Booking` (aggregate)

| Method | Logic |
|---|---|
| `calcCarrier()` | Brand-swap aware: for PENDING + first DECLINE/CONFIRM, resolves correct carrier |
| `calcBooker()` | Latest booker party |
| `calcState()` | Latest state from most-recent detail |
| `calcAllCompanyIdsWithAccess()` | All company IDs that may view this booking |
| `isCoreBooking()` | Determines if this is a core (non-INTTRA) booking |
| `isNonInttraBooking()` | True when booking originated outside INTTRA network |
| `hasDangerousGoods()` | DGS presence flag used in subscription condition evaluation |
| `fixAddressMess()` | Migrates `street01/02` → `unstructuredAddress01/02` |

#### `BookingDetail` (DynamoDB entity)

| Attribute | Type | Notes |
|---|---|---|
| `bookingId` | String (UUID) | Partition key |
| `sequenceNumber` | String | Sort key: `m_<epochMs>_<state>_<inttraRef>` |
| `version` | Integer | `@DynamoDbVersionAttribute` — optimistic locking |
| `expiresOn` | Long | TTL = now + 400 days |

**GSI Indexes:**

| Index Name | PK | SK |
|---|---|---|
| `INTTRA_REFERENCE_NUMBER_INDEX` | inttraReferenceNumber | — |
| `carrierId_carrierReferenceNumber` | carrierId | carrierReferenceNumber |
| `bookerId_shipmentId` | bookerId | shipmentId |
| `carrierScac_carrierReferenceNumber` | carrierScac | carrierReferenceNumber |

Stream view type: `KEYS_ONLY`

### Field-Level Constraints

| Field | Constraint |
|---|---|
| `unstructuredAddress01`–`04` | `@Size(max=35)` |
| `Contact.name` | `@Size(max=35)` |
| `shipmentId` | `@Size(max=35)` |
| Email address | max 512 characters |
| DGS variant | max 4 characters |
| Cargo line number | max 5 characters |
| Package count | Range: 1–99,999,999 |
| Segregation groups | Max 4 |
| Marks & Numbers | 9 lines × 10 elements × 35 chars |
| Equipment per booking | Max 999 |
| Humidity/AirFlow decimals | Max 2 |
| Container Net Weight decimals | Max 3 |
| Cargo gross/net weight decimals | Max 3 |
| Cargo gross volume decimals | Max 4 |

### Key Enumerations

| Enum | Values | Notes |
|---|---|---|
| `BookingState` | REQUEST, AMEND, PENDING, CONFIRM, DECLINE, CANCEL, REPLACE | |
| `Channel` | WEB, API, EDI, DESKTOP | |
| `BookingDisposition` | APPLIED (200), APPLIED_WITH_WARNINGS (200), IGNORED (200), REJECTED (400), DELETED (200) | HTTP status in parens |
| `PartyRole` | Booker, Carrier, Shipper, Forwarder, Consignee, ContractParty, FreightPayer, MessageRecipient, NotifyParties, BookingOffice, Haulage roles, CustomsBroker, Carrier_CounterParty, Requestor | |
| `ContactType` | InformationContact, NotificationContact, ConfirmedWith, EquipmentContact, EmergencyDangerousGoodsContact | |
| `PackageType` | OUTER, INNER, INNERINNER, SINGLELINE | Hierarchy: INNER requires OUTER, INNERINNER requires INNER |
| `SegregationGroup` | None + others | Max 4; None cannot mix with others |
| `WeightType` | TNE auto-converted to KGM (× 1000) for non-RoRo/non-Breakbulk | |
| `BookingResponseType` | Pending, Accepted, ConditionallyAccepted | |

---

## 16. DAO & Persistence Rules

### `BookingDetailDao`

| Method | Consistency | Notes |
|---|---|---|
| `findByBookingId` | Strong | Partition-key scan |
| `findByInttraReferenceNumber` | Eventual → Strong | GSI query + consistent re-fetch |
| `findByCarrierIdAndCarrierReferenceNumber` | Eventual | GSI query |
| `findBySubmitterIdAndShipmentId` | Eventual | GSI query |
| `findByCarrierScacAndCarrierReferenceNumber` | Eventual | GSI query |
| `findByBookingIdSequenceNumber` | Strong | GET item |
| `findLatestCarrierAndCustomerVersions` | — | Sorts lexicographically; picks latest of each |

**Optimistic locking:** `@DynamoDbVersionAttribute Integer version` — concurrent updates throw and are retried.

**DynamoDB resilience:** Retry up to `dynamoExceptionMaxRetryCount`. On ultimate failure, write `dynamo_error/{workflowId}` to S3.

---

## 17. Elasticsearch Indexing & Search

**NEW SECTION** — Expanded with implementation details.

### Indexing

- Index name: `"booking"`, mapping type: `"Booking"`
- **Optimistic locking**: Uses ES version field if record exists
- **Create-Only Mode**: Sets `OP_TYPE="create"` for new records
- **Conflict Handling**: HTTP 409 → `UncheckedIOException` with retry message
- `complianceRisk` retrieval wrapped in try-catch (failures logged but ignored)
- Core bookings skipped if `enableCoreBookingSearch=false`

### Search

- Default from: `0`, Default size: `10`, Max result set: `10,000`
- Three search patterns:
  1. **Simple Query String** — `SIMPLE_SEARCH_FIELDS`
  2. **Term Query** — exact match on `inttraReferenceNumber`
  3. **Aggregation** — `TermsAggregation` on summary fields
- Aggregation names: `STATE`, `CARRIER_ID`, `LAST_MODIFIED_DATE`, `CREATED_BY`
- `complianceRisk` excluded unless `cargoScreenTrialPeriod=true` or `cargoScreenPreference.isCargoScreenBookingAllowed`

---

## 18. Lambda Processing Rules

### IndexerHandler

```
Environment Variables:
  maxRetries (default 5), connTimeoutMillis, readTimeoutMillis,
  AWS_DEFAULT_REGION, elasticsearchEndpointUrl, dynamoDbEnvironment,
  enableCoreBookingSearch (boolean)

INSERT/MODIFY → index (skip core if disabled)
REMOVE → delete (parse inttraRef from sequenceNumber[3])
```

### S3ArchiveHandler

```
Environment Variables:
  s3ArchiveBucket, soS3ArchiveBucket, reportbridgeSNSTopicArn,
  maxRetries, enableCoreBookingArchive, tntEnabled, tntAPI, tokenEnv

Events: INSERT only
S3 key: YYYY/MM/DD/HH/{bookingId}_{sequenceNumber} (UTC)
SO contracts → soS3ArchiveBucket; others → s3ArchiveBucket
Optional T&T POST when tntEnabled=true
```

---

## 19. Converters & Mappers

### DynamoDB Attribute Converters

| Converter | Purpose |
|---|---|
| `BookingStateConverter` | `BookingState` enum ↔ DynamoDB string |
| `ContractAttributeConverter` | Contract payload JSON ↔ DynamoDB |
| `ContractTypeConverter` | `ContractEnum` discriminator |
| `QuantityTypeConverter` | Weight/Volume quantities |
| `SpotRatesConverter` | Spot rate data |
| `ConditionListAttributeConverter` | OV condition lists |
| `EnrichedAttributesConverter` | Resolved party/location enrichment |
| `RangeAttributeConverter` | Rapid Reservation number ranges |
| `AuditAttributeConverter` | `createdDateUtc`, `modifiedBy` |
| `LegacyMapConverter` | Backward-compatible legacy attributes |
| `MetaDataConverter` | SQS/workflow metadata |
| `LocalDateTimeTypeConverter` / `OffsetDateTimeTypeConverter` | Date conversions |

### Weight Conversion

```
TNE → KGM (× 1000) for NON RoRo AND NON BreakBulk only.
Fields: goodsGrossWeight, goodsNetWeight, splitGoodsDetails.grossWeight,
        dangerousGoods.netNetWeight, DG split weights, equipment.netWeight
```

### Address Backward Compatibility

- `BackwardCompatibilityUtil.mergeSegregationGroups` — legacy single field → list
- `Booking.fixAddressMess` — `street01/02` → `unstructuredAddress01/02`

---

## 20. Carrier Spot Rates

**NEW SECTION** — Expanded from brief mention in original.

### Eligibility Check

- Config-driven: `spotRatesConfig.getCarrierScacWithIntegration()` + `getIntegrationConfig()`
- Only **MAERSK** integration currently implemented
- Preferred language from User actor (if available)

### API Routing

```
Switch on integration type:
  "MAERSK" → MaerskApiClient.getSpotRates()
    Endpoint: https://offers.api.maersk.com/offers/v2/offers
    Auth: AWS Parameter Store awsps:/inttra/{env}/booking/config/maerskAPIToken
    Response mapping: MaerskResponseToCanonical
  Default → log error, return null
```

### Spot Rate ↔ Booking Linkage

- Saves mapping: `spotRateId` + `priceId` + `inttraReference` + `carrierId`
- Queried via `findByInttraReference()` for spot rate lookup by booking

---

## 21. Rapid Reservation

**NEW SECTION** — Documents range management rules.

### Range Management

Supports TWO ranges (`range1` and `range2`) with rolling semantics:

```
On new range added:
  If no range2 → set range2
  If range2 exists → shift: range1 = old range2, range2 = new range
  Reset lastUsedValue if outside new range1
```

### Number Generation

- Generates within specified range boundaries
- Tracks `lastUsedValue` per series
- MAX_RETRY_COUNT = 5 on `ConditionalCheckFailedException`
- Multi-criteria eligibility: queries by carrier ID, filters by condition evaluation
- Returns first matching configuration

### Booking Integration

- `BookingService.assignRapidReservedCarrierBookingNumber()` retries up to `MAX_RR_ATTEMPTS = 3` for duplicate detection

---

## 22. Template Service

**NEW SECTION** — Documents template lifecycle rules.

### Scoping

All templates scoped to `actor.getCompanyId()` (Booker company).

### Validation

- If `carrierId` specified → validates via `networkParticipantService.getByInttraCompanyId()` (throws `IllegalArgumentException` if not found)
- If `portOfDischargeLocationCode` specified → validates via `geographyService.getByLocationCode()` (throws `IllegalArgumentException` if not found)

### Expiration & Tracking

- Auto-calculated via `Template.calcExpiresOn()`, updated on every `save()` and `getTemplate()` call
- `TemplateSummary.lastUsedDateUtc` updated every time template is retrieved

### Edge Cases

- If GeoMaster deletes a PLOD location after template was saved:
  - `portOfDischargeLocationName` returns null
  - Template remains usable (user can re-save with new PLOD)
  - Previously threw exception — fixed to be resilient

---

## 23. Dangerous Goods (DGS) Service

- REST endpoint: `GET /dgs/undg/{undg}?variant=`
- Input validation: `undg ≤ 0` or non-numeric → `400 BAD_REQUEST`; not found → `404`
- DGS inhalant UI values: `["A", "B", "C", "D"]` — maps to UNHAZ inhalation hazard codes
- Used for cargo screening and DGS enrichment

---

## 24. Carrier-Specific Customizations

**NEW SECTION** — Documents EDI customization pipeline.

### ZIM Region Routing

| Region Token | Countries (ISO-2) |
|---|---|
| `ZIMHF` | Default fallback |
| `ZIMHK` | Asia-Pacific countries |
| `ZIMOR` | Americas/Caribbean countries |

- Company ID: `850803`
- Maps POR country code → region token via `CustomizationHandler`
- Sets `FILE_TOKEN_REGION` metadata projection

### Heineken Customizations

- Loaded from `customization/heineken.yaml`
- Filters: Purchase Order Numbers, Shipper References, Booking Numbers, Shipment IDs
- Applied via `EdiCustomizations` class

### Special Character Handling

- Config file: `customization/splchar.yaml`
- Structure: `HashMap<String, List<SpecialCharCustomization>>` (key = carrier SCAC)
- If carrier has specific config → use carrier rules (skip generic accent removal)
- If no carrier config AND subscription `isRemoveAccentCharacters()` → apply generic accent removal

---

## 25. Configuration & Feature Flags

### `BookingConfig` (Dropwizard)

| Property | Type | Notes |
|---|---|---|
| `dynamoDbConfig` | `BaseDynamoDbConfig` | `@Valid @NotNull` |
| `elasticsearchConfig` | `ElasticsearchConfig` | |
| `s3ArchiveBucket` | String | Main S3 archive bucket |
| `appianWayConfig.inQueueUrl` | String | Inbound SQS queue |
| `appianWayConfig.snsTopicARN` | String | Outbound SNS topic |
| `appianWayConfig.waitTimeSeconds` | int | Default: 20 |
| `appianWayConfig.maxNumberOfMessages` | int | Default: 1 |
| `appianWayConfig.listenerEnabled` | boolean | |
| `appianWayConfig.outboundEnabled` | boolean | |
| `bookingBridgeSQS` | String | Legacy routing queue |
| `nonInttraEnabled` | boolean | NIB feature flag |
| `bookingAppIdentity` | String | `"INTTRA"` or `"NON_INTTRA"` |
| `cargoScreenTrialPeriod` | String (boolean) | Show complianceRisk in search |
| `useSequenceId` | boolean | INTTRA reference generation strategy |
| `removeNestedEmailTag` | boolean | Default: false |
| `maxRetries` | int | `@Max(5)`, default: 3 |
| `maxDelay` | int | Default: 10,000 ms |
| `baseDelay` | int | Default: 100 ms |
| `dynamoExceptionMaxRetryCount` | int | DynamoDB retry ceiling |
| `inttraRefConfig.carrierCompanyIds` | List\<String\> | Per-prefix IDs (e.g. `["850803"]`) |
| `spotRatesConfig` | `SpotRateConfig` | Maersk URL, auth |
| `watermillConfig` | `WatermillConfig` | Analytics event bus |

### Feature Flags Summary

| Flag | Source | Purpose |
|---|---|---|
| `nonInttraEnabled` / `isNonInttraProcessingEnabled()` | Config + SSM | Enable NIB processing |
| `enableCoreBookingSearch` | Lambda env | Gate core booking ES indexing |
| `enableCoreBookingArchive` | Lambda env | Gate core booking S3 archival |
| `tntEnabled` | Lambda env | Enable Track & Trace integration |
| `cargoScreenTrialPeriod` | Config | Show complianceRisk in search |
| `listenerEnabled` | Config | Enable SQS listener |
| `outboundEnabled` | Config | Enable outbound processing |
| `sendLegalTerms` (VP active) | Runtime | Split Booker vs non-Booker email distribution |
| `standAloneBookingMigrated` | Carrier OV rule | Enable NIB for specific carrier |

### Guice Modules

| Module | Purpose |
|---|---|
| `BookingApplicationInjector` | Core bindings (Listener, DAO, services) |
| `BookingDynamoModule` | DynamoDB (7 tables via cloud-sdk) |
| `BookingMessagingModule` | SQS/SNS/S3 (via cloud-sdk-aws) |
| `OutboundServiceModule` | 32-thread outbound executor (queue size 60) |
| `InboundServiceModule` | 8-thread inbound executor (`CallerRunsPolicy` back-pressure) |
| `LocalCacheModule` | Guava caches for network services |
| `JestModule` | Elasticsearch Jest client |
| `EmailSenderModule` | SES email sending |
| `SystemUTCClockModule` | `Clock.systemUTC()` |
| `ExternalWrapperModule` | Hystrix + `@ExternalCall` retry interceptor |

---

## 26. External Integrations

### Network Service APIs (Hystrix-wrapped)

| Service | Purpose |
|---|---|
| Auth | Token validation, principal resolution |
| Network Participant | Company hierarchy, children lookup, migration status |
| Connections | Booker↔carrier activation verification |
| Geography / Country | Country resolution, ISO Alpha-2 lookup |
| Reference Data | Package types, container types |
| Format Service | EDI/API format resolution |
| Integration Profile | Carrier profile + format |
| Subscription | Outbound subscription discovery + condition evaluation |
| Blacklist Email | Email block-list check (non-Booker only when sendLegalTerms=true) |
| Participant Addons | Additional participant configuration |
| Alias | Partner alias resolution |
| User Service | Login → companyId |
| Webhook | Webhook delivery |

### AWS Services

| Service | Usage |
|---|---|
| DynamoDB | 7 tables: BookingDetail, RapidReservation, Template, SpotRates, SpotRatesToInttraRef, SequenceId, UniqueId |
| SQS | Inbound, transformer, legacy bridge, outbound distribution, APERAK, Watermill |
| SNS | Outbound events, report bridge |
| S3 | Workspace (payloads), archive buckets, Watermill payloads |
| Elasticsearch | Booking search index (AWS-signed Jest client) |
| Lambda | Indexer, S3Archive (DynamoDB Streams triggered) |
| SES | Outbound email |
| Parameter Store | Secrets and config (`awsps:` placeholders) |

### Watermill Analytics

- S3 key format: `watermill_<rootWorkflowId>/<randomUUID>`
- Enriches detail with carrier metadata from NetworkParticipant
- One action = one SQS message

### Track-and-Trace (Optional)

POST to `tntAPI` endpoint from `S3ArchiveHandler` when `tntEnabled=true`.

---

## 27. Error Code Reference

### Exception Types

| Exception | Extends | Retryable |
|---|---|---|
| `AuthorizationException` | `SecurityException` | No |
| `BookingNotFoundException` | `NotFoundException` | No |
| `ResolutionException` | `IllegalArgumentException` | No |
| `StateTransitionException` | `RuntimeException` | No |
| `StructuralValidationException` | `RuntimeException` | No |
| `TransformationException` | `RuntimeException` | No |
| `InternalException` | `RuntimeException` | **Yes** (network failures) |
| `BookingValidationException` | `RuntimeException` | No |
| `DBRecordNotFoundException` | `RuntimeException` | No |

**HTTP fallback:** `BookingExceptionMapper` maps all uncoded exceptions to `"000200"`.

### Complete Error Code Table

| Code | Domain | Message Summary |
|---|---|---|
| `000200` | Generic | Uncoded/catch-all |
| `000304` | State | Booking State Invalid/Missing |
| `102030` | Dimensions | Out-of-gauge details incomplete |
| `200030` | Header Location | POR required |
| `200031` | Header Location | POR = POD |
| `200037` | Location Date | Must provide departure/arrival date or vessel |
| `200039` | Location Date | Earliest Departure out of ±400 days |
| `200040`/`200048` | Location Date | Latest Delivery errors |
| `200042` | Header Location | POD required |
| `200061` | Reference | Both Contract + Tariff |
| `200065` | Reference | Duplicate active OCBN |
| `200068` | Reference | SMBN not allowed |
| `200069` | Reference | OCBN mismatch on AMEND |
| `200097`–`200117` | Leg | Various leg errors |
| `200118` | Carrier | Carrier mismatch |
| `200130`–`200140` | Contact | Name/comm rules |
| `200407` | Party | MessageRecipient no notification |
| `200614`–`200617` | Reefer | Temperature rules |
| `200663`/`200664` | Haulage | Contact/party missing |
| `200771`–`200774` | Party | Shipper/Forwarder identity |
| `200800`/`200801` | Equipment | Count rules |
| `200816` | Auth | Not in hierarchy |
| `201202`–`201999` | OV | Carrier-optional rules |
| `206009`/`206010` | Date | Creation/message date |
| `206012` | Date | SI Due Date |
| `206065` | Reference | Duplicate OCBN (CONFIRM) |
| `206084` | Locator | INTTRA ref not found |
| `206590` | Equipment | Inconsistent haulage codes |
| `206763` | Equipment | Container count ≠ 1 |
| `206800` | Decline | Comments required |
| `206809` | Party | Booker mismatch |
| `213001` | State | Transition not allowed |
| `213002` | State | NIB transition not allowed |
| `214002` | Party | Invalid payment term |
| `215020`/`215023` | Location | UNLOC/country mismatch |
| `215051`/`215052` | Leg Date | Date format errors |
| `215054` | Party | Duplicate role |
| `215066`/`215067` | Party | Missing/invalid identifier |
| `215079` | Cargo | Invalid outer pack |
| `215094` | Weight | Invalid weight |
| `215095`/`215096` | Cargo | Marks & Numbers limits |
| `215097` | Cargo | Invalid volume |
| `215147` | DGS | Shipping name required |
| `215170`/`215171` | Equipment | Duplicate/invalid code |
| `215180` | Equipment | Net weight format |
| `215184` | Reefer | Humidity/airflow decimals |
| `215235` | Reefer | Handling without temp |
| `215285` | Equipment | Haulage party no ID |
| `215289`/`215291` | Haulage | Wrong party role |
| `215329` | Leg | Multiple dates |
| `215331` | DGS | Flashpoint format |
| `215332` | Reefer | Temperature format |
| `215333` | DGS | UN number missing |
| `215343` | Haulage | Reefer subcontractor date |
| `221001`–`221103` | Locator | ShipmentId issues |
| `221009`/`221010` | Auth | AMEND/CANCEL unauthorized |
| `221020`–`221028` | Location | Various |
| `221030`–`221037` | Party | Booker resolution |
| `221056` | Cargo | Zero cargo |
| `221063` | Cargo | Split goods mismatch |
| `221108` | Equipment | FCLFCL needs equipment |
| `221111` | Cargo | Package without type |
| `224002`/`224003` | Locator | Carrier lookup failure |
| `224016` | Auth | Carrier brand swap |
| `224018` | Header | Invalid response type |
| `224075` | Location | Alias unresolved |
| `224099`–`224102` | Party | Carrier resolution |
| `224139`–`224147` | Haulage | Wrong party for date |
| `224160` | Reference | Missing carrier BN |
| `228003` | Party | Invalid role |
| `228007` | Header/Party | CTA without COM |
| `228008` | Party/Equipment | Count exceeded |
| `233176`–`233182` | OV | Carrier-optional |
| `285` | Auth | Not activated |
| `300001`–`300008` | Carrier | Smart/DGS/RoRo/BB/OOG/amend |
| `303030` | Document | Sea waybill format |
| `333333` | Location | Invalid type |
| `666660` | Booker | ShipmentId required (EDI) |
| `666666` | MoveType | Missing |
| `996003`–`996019` | DGS/Cargo | Package/DGS rules |
| `997009`–`997024` | Equipment/Cargo | Field format rules |
| `999990` | Reference | Length exceeded |
| `UNAUTHORIZED_TRANSACTION` | Inttra | Sanctioned country |

---

## 28. Constants Quick Reference

| Constant | Value | Location |
|---|---|---|
| `INTTRA_COMPANY_ID` | `"1000"` | Multiple |
| `INTTRAREF_SEED_VALUE` | `2,000,000,000` | `BookingProcessorTask` |
| `MAX_RR_ATTEMPTS` | `3` | `BookingService` |
| `MAX_CONTACT_COMM_COUNT` | `9` | `PartyValidations` |
| `MAX_DATE_RANGE_DAYS` | `400` | Date validations, TTL |
| `MAX_RETRIES` (DynamoDB) | configurable | `BookingService` |
| `MAX_RETRIES` (Lambda) | `5` | `IndexerHandler` |
| `MAX_RETRY_COUNT` (RR) | `5` | `RapidReservationService` |
| `RAC` | `"requestBooking"` | `BookingProcessorTask` |
| `CPD` | `"confirmBooking"` | `BookingProcessorTask` |
| `EDI_CLIENT` | `"BOOKING_ADMIN"` | `BookingProcessorTask` |
| `MARKS_AND_NUMBER_TOKEN_REGEX` | `"#$%"` | `ValidationService` |
| UCN/CCC max length | 45 | `ReferenceValidations` |
| OCBN/BookingNumber max | 30 | `ReferenceValidations` |
| Other ref max | 35 | `ReferenceValidations` |
| Equipment count max | 999 | `EquipmentValidations` |
| Package count range | 1–99,999,999 | `CargoValidations` |
| Segregation groups max | 4 | `CargoValidations` |
| Marks & Numbers | 9 lines × 10 elements × 35 chars | `CargoValidations` |
| Address/Contact fields | 35 chars | `Address`, `Contact` |
| Email max | 512 chars | `PartyValidations` |
| DG UNDG variant max | 4 chars | `CargoValidations` |
| Cargo line number max | 5 chars | `CargoValidations` |
| Humidity/AirFlow decimals | 2 | `EquipmentValidations` |
| Weight decimals | 3 | Multiple |
| Volume decimals | 4 | `CargoValidations` |
| ZIM carrier company ID | `"850803"` | `IdGenerator`, config |
| ES default size | 10 | `ElasticsearchSupport` |
| ES max result set | 10,000 | `ElasticsearchSupport` |
| Outbound executor threads | 32 | `OutboundServiceModule` |
| Outbound executor queue | 60 | `OutboundServiceModule` |
| Inbound executor threads | 8 | `InboundServiceModule` |
| i18n bundles | EN, ES, FR, JA, PT, TR, ZH_CN, ZH_TW | `MessageSupport` |
