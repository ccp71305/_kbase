# Booking Module — Business Rules & Validations (Exhaustive Reference)

> **Original prompt:** *"review the booking module in detail and document all business rules and validations. This should be completely exhaustive and detailed and include diagrams where necessary for easy elucidation and readability. All inbound, outbound, lambda, validations should be documented across all service, models, dao, utils, converters etc. Group the business rules logically. Create the .md document under booking/docs/booking-business-rules.md."*

---

## Table of Contents

1. [Module Overview & Architecture](#1-module-overview--architecture)
2. [Entry Points](#2-entry-points)
   - [REST Controllers](#21-rest-controllers)
   - [SQS / Inbound Processing](#22-sqs--inbound-processing)
   - [Lambda Handlers](#23-lambda-handlers)
3. [State Machine](#3-state-machine)
4. [Service Layer Business Rules](#4-service-layer-business-rules)
   - [BookingService](#41-bookingservice)
   - [ValidationService](#42-validationservice)
   - [BookingLocator](#43-bookinglocator)
   - [BookingAuthorizer](#44-bookingauthorizer)
   - [BookingReinstatementService](#45-bookingreinstatementservice)
5. [Validation Plans — All Rules by Message Type](#5-validation-plans--all-rules-by-message-type)
   - [BookingRequestContract (REQUEST / AMEND)](#51-bookingrequestcontract-request--amend)
   - [CancelMessage](#52-cancelmessage)
   - [ConfirmPendingMessage](#53-confirmpendingmessage)
   - [DeclineReplaceMessage](#54-declinereplacement)
6. [Validation Rules — Grouped by Domain](#6-validation-rules--grouped-by-domain)
   - [Header & Location Validations](#61-header--location-validations)
   - [Party Validations](#62-party-validations)
   - [Equipment Validations](#63-equipment-validations)
   - [Cargo Validations](#64-cargo-validations)
   - [Reference Validations](#65-reference-validations)
   - [Leg Validations](#66-leg-validations)
   - [Date Validations](#67-date-validations)
   - [Dimension Validations](#68-dimension-validations)
   - [Carrier Optional Validations (OV)](#69-carrier-optional-validations-ov)
   - [Inttra Validations (Sanctioned Countries)](#610-inttra-validations-sanctioned-countries)
7. [Authorization Rules](#7-authorization-rules)
8. [Split Booking Rules](#8-split-booking-rules)
9. [Reinstatement Rules (ION-9016)](#9-reinstatement-rules-ion-9016)
10. [Data Models](#10-data-models)
    - [Domain Entities](#101-domain-entities)
    - [Field-Level Constraints](#102-field-level-constraints)
    - [Enumerations](#103-enumerations)
11. [DAO & Persistence Rules](#11-dao--persistence-rules)
12. [Outbound Pipeline](#12-outbound-pipeline)
13. [Lambda Processing Rules](#13-lambda-processing-rules)
14. [Converters & Mappers](#14-converters--mappers)
15. [Utilities & Cross-Cutting Logic](#15-utilities--cross-cutting-logic)
16. [Configuration & Feature Flags](#16-configuration--feature-flags)
17. [External Integrations](#17-external-integrations)
18. [Error Code Reference](#18-error-code-reference)
19. [Constants Quick Reference](#19-constants-quick-reference)

---

## 1. Module Overview & Architecture

The **booking** module is the core transactional engine of the Mercury platform. It handles end-to-end lifecycle of ocean freight bookings — from initial customer request through carrier confirmation/decline/replacement — and exposes these capabilities over REST, EDI (SQS), and event-driven (Lambda) interfaces.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Booking Module                           │
│                                                                 │
│  ┌──────────┐  ┌─────────────┐  ┌──────────────┐              │
│  │  REST    │  │ SQS/EDI     │  │  Lambda      │              │
│  │ Customer │  │ Inbound     │  │  (DynamoDB   │              │
│  │ Carrier  │  │ Processor   │  │   Streams)   │              │
│  │ Search   │  │             │  │              │              │
│  └────┬─────┘  └──────┬──────┘  └──────┬───────┘              │
│       │               │                │                       │
│       └───────────────┴────────────────┘                       │
│                        │                                        │
│              ┌──────────▼──────────┐                           │
│              │  ValidationService  │                            │
│              │  (Plans + Rules)    │                            │
│              └──────────┬──────────┘                           │
│                         │                                       │
│              ┌──────────▼──────────┐                           │
│              │    BookingService   │                            │
│              │  (Orchestrator)     │                            │
│              └──────────┬──────────┘                           │
│                         │                                       │
│         ┌───────────────┼───────────────┐                      │
│         │               │               │                      │
│  ┌──────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐              │
│  │  DynamoDB   │ │    S3       │ │ Outbound   │              │
│  │  BookingDAO │ │  Archive    │ │ Pipeline   │              │
│  └─────────────┘ └─────────────┘ └──────┬─────┘              │
│                                          │                      │
│                               ┌──────────▼──────────┐         │
│                               │  ES Index  │  Email  │         │
│                               │  SQS/SNS   │  Webhook│         │
│                               └─────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

**Key packages:**

| Package | Purpose |
|---|---|
| `resources/` | JAX-RS REST controllers |
| `service/` | Core orchestration |
| `validation/` | Cross-cutting rule engine |
| `inbound/` | EDI/SQS message processing |
| `outbound/` | Notification pipeline |
| `model/` | Domain types, DTOs |
| `dao/` | DynamoDB access |
| `dynamodb/` | DynamoDB attribute converters |
| `elasticsearch/` | ES query DSL & indexing |
| `lambda/` | Lambda handlers (Indexer, S3Archive) |
| `dgs/` | Dangerous Goods rules |
| `carrierrule/` | Optional Validation (OV) domain |
| `carrierspotrates/` | Maersk spot-rate integration |
| `rapidreservation/` | Pre-allocated booking number series |
| `template/` | Saved booking templates |
| `networkservices/` | Network API clients |
| `util/` | Common utilities |
| `common/` | AWS, events, messaging, S3 helpers |

---

## 2. Entry Points

### 2.1 REST Controllers

#### `CustomerBookingResource` — Base path `/`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/{inttraReferenceId}` | (any) | Retrieves booking; throws `NotFoundException("bookingNotFound")` if booking is not visible to actor. Applies `BackwardCompatibilityUtil.mergeSegregationGroups` and `fixAddressMess` (migrates `street01/02` → `unstructuredAddress01/02`). |
| `POST` | `/request` | `BOOKING_RAC` | Auto-fills Booker `TransactionParty` from `NetworkParticipantService` (by `partyINTTRACompanyId`/`partyAlias` or `networkParticipantId`). Truncates Address fields (street1/2/3/city) to **35 chars**. Adds `InformationContact` from User principal's `primaryPhone`+name if missing. |
| `POST` | `/{inttraReferenceId}/amend` | `BOOKING_RAC` | Throws `IllegalArgumentException("illegalBookingState")` if `bookingState != AMEND`. |
| `POST` | `/{inttraReferenceId}/cancel` | `BOOKING_RAC` | Builds `CancelMessage`; sets `transactionContact` of type `InformationContact` from User/Client. |
| `DELETE` | `/{inttraReferenceId}` | `BOOKING_ADMIN` | Throws `NotFoundException` on `DBRecordNotFoundException`. |
| `GET` | `/ov/{carrierId}` | (any) | Returns list of carrier-rule names; lazy `ValidationContext` with no booking. |

#### `CarrierBookingResource` — Base path `/`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `POST` | `/{inttraReferenceId}/confirm` | `BOOKING_CPD` | Sets reference & channel; calls `bookingService.confirm`. |
| `POST` | `/{inttraReferenceId}/confirm/validate` | `BOOKING_ADMIN` | Dry-run validation only (no persist). |
| `POST` | `/{inttraReferenceId}/decline` | `BOOKING_CPD` | Wraps comments into `DeclineReplaceMessage` with `BookingState=DECLINE`. Sets `transactionContact` with `ContactType=ConfirmedWith`. |
| `POST` | `/{inttraReferenceId}/replace` | `BOOKING_CPD` | Replace workflow. |
| `POST` | `/{inttraReferenceId}/acknowledge` | `BOOKING_CPD` | Pending workflow. |
| `POST` | `/{inttraReferenceNumber}/s3archive` | `BOOKING_ADMIN` | Manually re-archives all `BookingDetail`s to S3. |

#### `SearchResource` — Base path `/search`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/{inttraReferenceNumber}` | (any) | Find by INTTRA ref. |
| `POST` | `/{inttraReferenceNumber}/reindex` | `BOOKING_ADMIN` | Force Elasticsearch re-index. |
| `POST` | `/simple` | (any) | `complianceRisk` excluded from source unless `cargoScreenTrialPeriod=true` OR `cargoScreenPreference.isCargoScreenBookingAllowed`. Aggregations: STATE, CARRIER_ID, LAST_MODIFIED_DATE, CREATED_BY. |
| `GET` | `/summary?rangeInDays=N` | (any) | Booking summary by company/date range. |
| `GET` | `/hasaccess` | (any) | Looks up user's companyId; throws `NotFoundException("User info not found")` if user not found. Returns whether total results > 0. |
| `GET` | `/bookingforBL` | INTTRA-only | Returns 403 if caller is not Inttra company (`INTTRA_COMPANY_ID_INTEGER`). Queries by BL number + carrier SCAC + booking state; returns latest carrier + customer versions. |

#### `OutboundResource` — Base path `/outbound`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/{inttraReferenceId}?versionnumber=` | (any) | Enriched booking detail. |
| `POST` | `/{inttraRef}/reprocess` | `BOOKING_ADMIN` | Re-runs subscription action for sequenceNumber/subscriptionHashKey/inttraCompanyId. |
| `POST` | `/{inttraRef}/email` | `BOOKING_ADMIN` | Re-sends enriched email. |

#### `DangerousGoodsResource` — Base path `/dgs`

| Method | Endpoint | Role | Business Rule |
|---|---|---|---|
| `GET` | `/undg/{undg}?variant=` | `BOOKING_RAC` | Throws `400 BAD_REQUEST` if `undg ≤ 0` or non-numeric; `404` if not found. |

#### `RapidReservationResource` — Base path `/rapid-reservation`

| Method | Endpoint | Role | Note |
|---|---|---|---|
| `POST` | `/` | `BOOKING_ADMIN` | Create/update series. |
| `POST` | `/{inttraCompanyId}/{name}/add-range` | `BOOKING_ADMIN` | Extend range. |
| `DELETE` | `/{inttraCompanyId}?name=` | `BOOKING_ADMIN` | Remove series. |

#### `TemplateResource` — Base path `/template` (User principals only)

`listTemplates`, `GET /{name}`, `PUT /{name}` (save), `DELETE /{name}`.

#### `CarrierSpotRatesResource` — Base path `/carrier-spot-rates`

- `GET /{inttraCompanyId}` — throws `IllegalArgumentException` (with example payload) if container JSON is invalid.
- `POST /saveLinkToInttraRef`
- `GET /isSpotRateBooking/{inttraReferenceId}`

---

### 2.2 SQS / Inbound Processing

#### `SQSListener`
- Long-polls AWS SQS queue.
- Empty/null `queueUrl` → `IllegalArgumentException`.
- Messages deleted from queue **only** on successful processing.
- Network retry exhaustion (`"Could not connect / retrieve"` in `InternalException`): message is **NOT** deleted; relies on SQS visibility timeout (~2 min) for automatic retry.

#### `BookingProcessorTask.execute()`
`booking/inbound/BookingProcessorTask.java` — Central dispatcher.

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
Read MetaData
     │
     ▼
Pull payload from S3 (appianWayConfig.s3WorkSpaceLocation)
     │
     ▼
shouldProcess()
 ├── INTTRA reference < 2_000_000_000 → route to bookingBridgeSQS (legacy)
 └── Continue →
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
 │    ├── REQUEST  → bookingService.request(actor, contract, metaData)
 │    │             (strips inttraRef if present on new REQUEST)
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

**Non-Inttra Booking (NIB) rules:**
- If `carrierRequest.getInttraReference() == null`: `nonInttraBookingValidator.checkforCarrierIdAndCarrierReference` + `shouldProcessNonInttraBooking`.
- NIB **cannot** be in `Pending` state (`BookingResponseType.Pending`) → `StateTransitionException("213002")`.

**Exception → Outbound Error Channels:**

| Exception | Handler |
|---|---|
| `TransformationException` | `outboundService.processTransformationErrors` |
| `StructuralValidationException` | `outboundService.processBusinessErrors` |
| `AuthorizationException` | `outboundService.processBusinessErrors` |
| `BookingNotFoundException` | `outboundService.processBusinessErrors` |
| `ResolutionException` | `outboundService.processBusinessErrors` |
| `BookingValidationException` | `outboundService.processBusinessErrors` |
| `StateTransitionException` | `outboundService.processBusinessErrors` |
| `InternalException` | `outboundService.processInternalError` |
| `Exception` (generic) | `outboundService.processInternalError` |

---

### 2.3 Lambda Handlers

#### `IndexerHandler` — DynamoDB Stream → Elasticsearch

Triggered by SNS → SQS wrapping DynamoDB stream events.

| Event | Action |
|---|---|
| `INSERT` / `MODIFY` | `Indexer.index(booking)` — skipped if `booking.isCoreBooking()` AND `enableCoreBookingSearch=false` |
| `REMOVE` | `Indexer.delete(inttraReferenceNumber)` — parsed from `sequenceNumber` split on `_`, position 3 |

- Retries up to `MAX_RETRIES_PROPERTY` (default **5**).

#### `S3ArchiveHandler` — DynamoDB Stream → S3

Processes **INSERT** events only.

- Archives `BookingDetail` JSON to `s3ArchiveBucket`.
- Uses `soS3ArchiveBucket` for `SOBookingRequestContract` / `SOCancelContract`.
- Skips core bookings if `ENABLE_CORE_BOOKING_ARCHIVE=false`.
- S3 key format: `YYYY/MM/DD/HH/{bookingId}_{sequenceNumber}` (UTC).
- Computes `uniqueVersionId` = `inttraRef + 3-digit version` and `splitCopy` flag (true when this version is a split but not the latest split).
- Optional Track-and-Trace POST when `tntEnabled=true` and `tntAPI` + `tokenEnv` configured.

---

## 3. State Machine

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
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
REQUEST         │ —  │  ✓   │  ✓    │  —      │  —      │  —     │  —      │
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
AMEND           │ —  │  ✓   │  ✓    │  ✓      │  ✓      │  ✓     │  ✓      │
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
PENDING         │ —  │  ✓   │  ✓    │  ✓      │  ✓      │  ✓     │  ✓      │
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
CONFIRM         │ —  │  ✓   │  ✓    │  ✗(213001)│ ✓      │  ✓     │  ✓      │
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
DECLINE         │ —  │  ✗   │ ignore│  ✓*     │  ✓*     │  ✓     │  ✓*     │
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
CANCEL          │ —  │  ✗   │  ✓    │  ✓*     │  ✓*     │  ✗     │  ✓*     │
────────────────┼────┼──────┼───────┼─────────┼─────────┼────────┼─────────┤
REPLACE         │ —  │  ✗   │ ignore│  ✗(213001)│ ✗(213001)│ ✗(213001)│ ✗(213001)│
└───────────────┴────┴──────┴───────┴─────────┴─────────┴────────┴─────────┘

✓  = Allowed
✗  = Throws StateTransitionException(213001)
✓* = Allowed only via ION-9016 reinstatement (see §9)
ignore = Silently ignored, no error
```

> **Rule:** `Carrier_CounterParty` (customer actor) can never transition to/from REPLACE.

Error messages:
- `213001` — "The transition from ${fromState} status to ${toState} status is not allowed."
- `213002` — "The transition to ${toState} status is not allowed for Non-Inttra booking."

---

## 4. Service Layer Business Rules

### 4.1 BookingService

`booking/service/BookingService.java`

**Constants:**

| Constant | Value | Purpose |
|---|---|---|
| `MAX_RR_ATTEMPTS` | 3 | Max retries for Rapid Reservation duplicate detection |
| `ERROR_213001` | `"213001"` | State transition error |
| `INTTRAREF_SEED_VALUE` | `2,000,000,000` | Minimum value for Mercury INTTRA references |
| TTL (expiresOn) | `now + 400 days` | Booking DynamoDB TTL |

**Key Operations:**

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
bookingReinstatementService.validateReinstatement(...)  ← enforces ION-9016 uniqueness
```

#### Access Check — `hasAccess(actorCompanyId, booking)`
```
Booking visible if:
  booking.calcAllCompanyIdsWithAccess() contains actorCompanyId
  OR any of actor's children companies (via networkParticipantService.getAllChildren)
```

#### Deduplication — `update(...)`
```
If booking.isEquivalent(contract) == true → result = IGNORED (no write)
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
Writes Sumo log entry for VAS offers containing: `currencyCode`, `containerType`, `amount`, `quantity`, `placeOfReceipt`, `placeOfDelivery`, `earliestDepartureDate`, `latestArrivalDate`.

---

### 4.2 ValidationService

`booking/service/ValidationService.java`

#### Context Building Rules

1. If `state == null` → `ResolutionException("000304", "Booking State is Invalid/Missing.")`
2. **Carrier statuses** (CONFIRM/PENDING/DECLINE/REPLACE):
   - Only carrier resolution; calls `partyValidations.verifyCarrier`
3. **Customer statuses**:
   - Booker resolved under owner `1000`; carrier resolved under booker first, then Inttra fallback
   - Booker-country enrichment → ISO Alpha-2 via `LocationEnrichment.getCountryByName`

#### Pre-Processing Transformations (before validation rules run)

| Transformation | Logic |
|---|---|
| `formatMarksAndNumbers` | Split marks on `"#$%"` regex tokens, trim each token |
| `convertFromTNE` | Non-RoRo/non-Breakbulk: weight type `TNE` → × 1000 → `KGM`. Applies to: `goodsGrossWeight`, `goodsNetWeight`, `splitGoodsDetails.grossWeight`, `dangerousGoods.netNetWeight`, DG split weights, `equipment.netWeight` |
| `reArrangePackagesInLineItemOrder` | Non-carrier status, when any INNER/INNERINNER present: reorder to OUTER 1 → INNER 1 → INNERINNER 1 → OUTER 2 → INNER 2 sequence |
| `collectParties` | Also resolves `HaulageParty` from each equipment haulage point |
| `collectPackageTypes` | IMO code type → `referenceDataService.getDangerousPackageType`; else `getPackageType` |
| `collectContainerTypes` | Only for `EquipmentSizeCodeType.ISO` |

**Constant:** `INTTRA_ALIAS_OWNER = "1000"`

---

### 4.3 BookingLocator

`booking/service/BookingLocator.java`

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

### 4.4 BookingAuthorizer

`booking/service/BookingAuthorizer.java`

#### Carrier-Status Messages

```
Brand-swap exemption:
  if no prior CONFIRM/DECLINE exists → skip carrier-match check

Otherwise:
  existing carrierId must match inbound carrier
  Mismatch → AuthorizationException("224016")
```

#### Customer-Status Messages

**REQUEST:**
```
1. Booker must be activated for the carrier:
   connectionsService.verify(bookerId, ConnectionType.CARRIER, carrierId)
   Failure → AuthorizationException("285")

2. Submitter must be in hierarchy OR partnership with booker
   Failure → AuthorizationException("200816")
```

**AMEND:**
```
Actor must be:
  associated (network org) with booking's resolved customer parties
  OR in hierarchy/partnership with booker/shipper/forwarder
Failure → AuthorizationException("221009")
```

**CANCEL:**
```
Same logic as AMEND
Failure → AuthorizationException("221010")
```

---

### 4.5 BookingReinstatementService

`booking/service/BookingReinstatementService.java`

Activated when `fromState ∈ {DECLINE, CANCEL}` (ION-9016 reinstatement).

```
1. Sets contract.setReinstated(true)
2. Finds latest customer detail with non-blank shipmentId
   (among REQUEST / AMEND / CANCEL states)
3. Calls BookingReinstatementValidations.shipmentIdMustBeUnique(
     shipmentId, bookerId, inttraRef, originalInttraRef, false)
4. Throws BookingValidationException if any errors
```

---

## 5. Validation Plans — All Rules by Message Type

### 5.1 `BookingRequestContract` (REQUEST / AMEND)

Rules run in order by `ValidationPlanFactory`:

| # | Rule | Class | Notes |
|---|---|---|---|
| 1 | JSR-303 Bean Validation | `ValidationSupport.mustBeJsr303Valid` | `@NotNull`, `@Size`, `@Valid`, custom validators |
| 2 | Dimension validation | `DimensionValidations.validateDimensions` | Out-of-gauge fields completeness (→ `102030`) |
| 3 | MoveType exists | `MoveTypeValidations.checkMoveTypeExists` | Missing moveType → `666666` |
| 4 | Party roles + max occurrences | `PartyValidations.checkParties`, `checkPartyRoleCountForRequestAmend`, `checkForContactMaxOccurance` | Duplicated role → `215054` |
| 5 | Header locations | `HeaderLocationValidations.executeHeaderLocationRules` | POR required, POD required, POR≠POD |
| 6 | Shipper/Forwarder existence | `PartyValidations.checkShipperFreightForwarderExists`, `checkShipperFreightForwarderPartyId` | Neither present → `200771` |
| 7 | Request leg dates | `RequestLegValidations.executeRequestLegRules` | Date format/range/type per leg |
| 8 | Contract vs tariff number | `requestAmendReferenceValidations.checkNotBothExistContractNumberTarrifNumber` | Both present → `200061` |
| 9 | Location date range + format | `requestAmendLocationValidations.checkForLocationDates`, `checkForHeaderLocationDateRangeAndFormat` | ±400 days |
| 10 | Charge payment terms | `PartyValidations.checkForCharges` | Must be in {PayableElsewhere, Prepaid, Collect} → `214002` |
| 11 | Reference length | `requestAmendReferenceValidations.checkReferenceLength` | UCN/CCC ≤ 45; OCBN/BookingNumber ≤ 30; others ≤ 35 |
| 12 | Haulage parties | `PartyValidations.checkForHaulageParties` | Equipment contact requires phone/email/fax → `200664` |
| 13 | Smart container | `CarrierValidations.smartContainerAllowed` | OV rule required → `300001` |
| 14 | Sanctioned countries | `InttraValidations.isBookingFromOrToSanctionedCountry` | → `UNAUTHORIZED_TRANSACTION` |
| 15 | DGS net weight | `CarrierValidations.dgsNetWeightRequired` | OV rule + DG present + no weight → `300002` |
| 16 | RoRo allowed | `CarrierValidations.isRoRoAllowed` | OV rule required → `300003` / `300007` |
| 17 | Breakbulk allowed | `CarrierValidations.isBreakbulkAllowed` | OV rule required → `300004` / `300008` |
| 18 | Out-of-gauge constraints | `CarrierValidations.outOfGaugeWithinConstraints` | OV thresholds → `300005` |
| **REQUEST-only** | | | |
| 19 | OCBN uniqueness | `BookerValidations.carrierReferenceNumberMustBeUnique` | Active booking with same OCBN → `200065` |
| 20 | Equipment count | `requestAmendEquipmentValidations.checkEquipmentCount` | Zero on REQUEST → `221108` |
| 21 | Cargo count | `requestAmendCargoValidations.checkCargoCount` | Zero → `221056` |
| 22 | SMBN allowed | `CarrierValidations.doesCarrierAllowSMBN` | OV rule required → `200068` |
| 23 | ShipmentId exists (EDI) | `BookerValidations.checkShipmentIdExists` | EDI channel + blank → `666660` |
| **AMEND-only** | | | |
| 24 | OCBN must match | `BookerValidations.carrierReferenceNumberMustMatch` | Mismatch → `200069` |
| 25 | Carrier on record | `CarrierValidations.matchCarrierOnRecord` | Mismatch → `200118` |
| 26 | Reject non-Inttra | `BookerValidations.rejectIfNonInttra` | NIB → `000200` |
| 27 | Booker party present | `BookerValidations.checkForBookerParty` | Mismatch → `206809` |
| 28 | Request→Amend transition | `CarrierValidations.isRequestToAmendStateTransitionAllowed` | OV blocks it → `300006` |
| 29 | Amend→Amend transition | `CarrierValidations.isAmendToAmendStateTransitionAllowed` | OV blocks it → `300006` |
| **All** | | | |
| 30 | Carrier OV rules | via `optionalValidationsService.getOptionalValidations(carrierId)` | Carrier-specific rules (see §6.9) |
| 31 | Inttra OV rules | via `optionalValidationsService.getOptionalValidations("1000")` | Platform-wide rules |
| 32 | Equipment validations | `requestAmendEquipmentValidations.executeEquipmentValidations` | All equipment rules (see §6.3) |
| 33 | Cargo validations | `requestAmendCargoValidations.executeCargoValidations` | All cargo rules (see §6.4) |
| 34 | Sea waybill count | `requestAmendDocumentValidations.validateNumberOfSeaWayBills` | > 35 chars → `999990`; not positive whole → `303030` |

---

### 5.2 `CancelMessage`

| # | Rule | Class |
|---|---|---|
| 1 | JSR-303 Bean Validation | `mustBeJsr303Valid` |
| 2 | Party role count | `partyValidations.checkPartyRoleCountForCancel` (Booker/Carrier only) |
| 3 | Booking must exist | `carrierValidations.bookingMustExist` |
| 4 | Party checks + contact max | `partyValidations.checkParties`, `checkForContactMaxOccurance` |
| 5 | Carrier on record | `carrierValidations.matchCarrierOnRecord` |
| 5 | Smart container | `carrierValidations.smartContainerAllowed` |
| 6 | Reject non-Inttra | `bookerValidations.rejectIfNonInttra` |

---

### 5.3 `ConfirmPendingMessage`

| # | Rule | Class | Notes |
|---|---|---|---|
| 1 | JSR-303 Bean Validation | `mustBeJsr303Valid` | |
| 2 | RoRo/Breakbulk | `carrierValidations.isBreakbulkAllowed`, `isRoRoAllowed` | |
| 3 | Max container count | `confirmPendingEquipmentValidations.checkForMaxContainerCount` | > 999 → `228008` |
| 4 | Header location rules | `confirmPendingHeaderLocationValidations.executeHeaderLocationRules` | |
| 5 | Party validations | `confirmPendingPartyValidations.executeConfirmPendingPartyValidations` | |
| 6 | Reference length | `confirmPendingReferenceValidations.checkReferenceLength` | |
| 7 | Equipment number duplicate | `confirmPendingEquipmentValidations.equipmentNumberDuplicateCheck` | → `215170` |
| 8 | Cargo validations | `confirmPendingCargoValidations.executeCargoValidations` | |
| 9 | Equipment codes | `confirmPendingEquipmentValidations.checkEquipmentCodes` | → `215171` |
| 10 | Carrier booking number (CONFIRM only) | `confirmPendingReferenceValidations.carrierBookingNumberMustExist` | → `224160` |
| 11 | OCBN uniqueness | Split → `bookerValidations.carrierReferenceNumberMustBeUnique`; non-split → `confirmPendingReferenceValidations.carrierReferenceNumberMustBeUnique` | |
| 12 | Transport leg | `confirmPendingLegValidations.checkTransportLeg` | Vessel/voyage, seq, stage |
| 13 | Header dates | `checkForMessageDate`, `mustExistCreationDate`, `checkForSIDocumentDate`, `checkForVGMCutOffDate` | ±400 days |
| 14 | Container net weight | `checkForContainerNetWeight` | → `215180` |
| 15 | Haulage date | `checkForHaulageDate` | Per `HaulageDateType` rules |
| 16 | Equipment reference length | `checkReferenceLength` | |
| 17 | Response type | `checkResponseType` | → `224018` |
| 18 | CTA/COM check | `checkCOMForCTA` | → `228007` |
| 19 | Booker party | `bookerValidations.checkForBookerParty` | → `206809` |
| 20 | Number of containers | `checkForNumberOfContainers` | → `206763` |
| 21 | Haulage arrangement code | `checkForHaulageArrangementcode` | → `206590` |
| 22 | Contact max occurrences | `partyValidations.checkForContactMaxOccurance` | → `228008` |
| 23 | Haulage parties | `partyValidations.checkForHaulageParties` | → `200664` |
| 24 | Reefer validations | `reeferValidations` | Temp/NAR rules |

---

### 5.4 `DeclineReplaceMessage`

| # | Rule | Class | Error |
|---|---|---|---|
| 1 | JSR-303 Bean Validation | `mustBeJsr303Valid` | |
| 2 | Carrier comments required | `declineCommentValidations.carrierCommentsMustExist` | `206800` |
| 3 | Message date | `declineHeaderValidations.checkForMessageDate` | `206010` |
| 4 | Creation date | `mustExistCreationDate` | `206009` |
| 5 | CTA/COM | `checkCOMForCTA` | `228007` |
| 6 | Booker party | `bookerValidations.checkForBookerParty` | `206809` |
| 7 | Contact max occurrences | `partyValidations.checkForContactMaxOccurance` | `228008` |

---

## 6. Validation Rules — Grouped by Domain

### 6.1 Header & Location Validations

#### REQUEST/AMEND Header Location Rules (`HeaderLocationValidations`)

| Error Code | Condition |
|---|---|
| `200030` | Place of Receipt (POR) is missing |
| `200042` | Place of Delivery (POD) is missing |
| `200031` | POR and POD are the same location |
| `221020` | More than one of any `LocationType` (except `ProhibitedTransshipment`/`RequestedTransshipment`) |
| `215020` | UNLOC unresolved for: BLReleaseOffice, GoodsOrigin, POR, POD, ProhibitedTransshipment, RequestedTransshipment, BookingOffice |
| `221023` | Alias unresolved for the same set |
| `215023` | Country code mismatch between resolved location and provided code |
| `333333` | LocationType not in `LocationType.VALID_HEADER_LOCATIONS` |

#### REQUEST/AMEND Location Date Rules

| Error Code | Condition |
|---|---|
| `200037` | Must provide one of: EarliestDeparture at POR, LatestDelivery at POD, or MainCarriage leg with vessel+conveyanceNumber |
| `200039` | EarliestDeparture at POR not within ±400 days |
| `200040`/`200048` | LatestDelivery at POD — date range or format error |
| `221024`/`221025` | Date format errors |
| `215024`/`215025` | Invalid date values |

#### CONFIRM/PENDING Header Location Rules

For location types `{FirstForeignPortOfAcceptance, FinalPortForAMSDocumentation, FirstUSPort, LastNonUSPort}`:

| Error Code | Condition |
|---|---|
| `215020` | Unresolved UNLOC |
| `224075` | Unresolved alias |
| `215023` | Country code mismatch |

---

### 6.2 Party Validations

**Constants:**
- `MAX_CONTACT_COMM_COUNT = 9` (phones + faxes + emails per Contact)
- Accepted party roles: `Carrier, Consignee, Shipper, ContractParty, FreightPayer, Forwarder, MessageRecipient, MainNotifyParty, FirstAdditionalNotifyParty, SecondAdditionalNotifyParty, Booker, CustomsBroker`
- Haulage party roles: `{EmptyPickUp, IntermediateStopOff, ReeferSubcontractor, ShipFrom, ShipTo}`
- Freight accepted terms: `{PayableElsewhere, Prepaid, Collect}`

#### Party Identity & Role Rules

| Error Code | Condition |
|---|---|
| `228003` | Party role not in accepted list |
| `215054` | Duplicate party role (only one of each allowed) |
| `215066` | Non-Booker/non-Carrier party missing all identifiers (alias, INTTRA id, DUNS, passthrough, name) |
| `215067` | Invalid INTTRA Company ID for resolved parties |
| `224102` | Invalid Partner Alias |
| `200771` | Neither Shipper nor Forwarder present |
| `200773` | Neither Shipper nor Forwarder has a party identifier |
| `200774` | Neither Shipper nor Forwarder resolved |
| `214002` | Charge `paymentTerm` not in `{PayableElsewhere, Prepaid, Collect}` |
| `200664` | Haulage party of allowed role with `EquipmentContact` missing phone/email/fax |

#### Contact Communication Rules

| Error Code | Condition |
|---|---|
| `200130` | `InformationContact` name missing while phone/email/fax provided |
| `200132` | `InformationContact` name present but no phone/email/fax |
| `200131` | Contact name contains only dots/spaces |
| `200134` | Phone contains only dots/spaces |
| `200138` | Fax contains only dots/spaces |
| `200135` | Email > 512 characters |
| `200140` | Notification contact missing email |
| `200407` | `MessageRecipient` party has no notification contact |
| `228008` | Total emails + phones + faxes per Contact > 9 |
| `228007` | Contact name (CTA) present without any communication (COM) — phone/email/fax |

#### Booker Resolution Rules

| Error Code | Condition |
|---|---|
| `ResolutionException("221030")` | Null booker |
| `ResolutionException("221033")` | Both partyId and alias missing for booker |
| `ResolutionException("215067")` | Booker unresolved by INTTRA ID |
| `ResolutionException("221037")` | Booker unresolved by alias |

#### Carrier Resolution Rules

| Error Code | Condition |
|---|---|
| `ResolutionException("215053")` | Null carrier |
| `ResolutionException("224099")` | Both partyId and alias missing for carrier |
| `ResolutionException("215067")` | Carrier unresolved by INTTRA ID |
| `ResolutionException("224101")` | Carrier unresolved by alias |

#### Confirmation Party Validations (inbound confirm)

| Error Code | Condition |
|---|---|
| `215066` | Missing identifier for: Consignee, Shipper, ContractParty, FreightPayer, Forwarder, MessageRecipient, Notify Parties |
| `215067` | Invalid INTTRA Company ID |
| `224102` | Invalid Partner Alias |
| `200140` | Notification contact missing email |
| `200407` | MessageRecipient lacks notification contact |

---

### 6.3 Equipment Validations

#### REQUEST/AMEND Equipment Rules (`request/validation/EquipmentValidations`)

| Error Code | Condition |
|---|---|
| `215171` | Invalid equipment size/type code |
| `200800` | Equipment count ≠ 1 when container identifier provided |
| `200801` | `ServiceType=FCLFCL` count missing or < 1 |
| `200663` | Haulage party `InformationContact` with details but missing name (for EmptyPickUp, ReeferSubcontractor, ShipTo, ShipFrom, IntermediateStopOff) |
| `215285` | Haulage party missing all identifiers + name |
| `997009` | Fumigation date not in `CCYYMMDDHHMM` format |
| `997019` | Equipment haulage arrangement code mandatory |
| `997020` | Invalid haulage arrangement enum |
| `221108` | REQUEST with FCLFCL service must include equipment information (unless RoRo or BreakBulk) |

#### CONFIRM/PENDING Equipment Rules (`inbound/confirmation/validation/EquipmentValidations`)

| Error Code | Condition |
|---|---|
| `215170` | Duplicate equipment identifier (container number) |
| `215171` | Invalid equipment size code |
| `215180` | Container Net Weight invalid — must be positive whole number or ≤ 3 decimal places |
| `206763` | `numberOfContainers ≠ 1` when equipment identifier provided |
| `206590` | Different haulage arrangement codes across equipment groups |
| `228008` | Equipment count > 999 |
| `215343` | Invalid date for `ReeferSubcontractor` haulage date |

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

#### Reefer / Controlled Atmosphere Rules (REQUEST/AMEND and CONFIRM/PENDING)

| Error Code | Condition |
|---|---|
| `200614` | Reefer container missing temperature and not set to non-active reefer |
| `200615` | Non-reefer/non-hybrid container with temperature or NAR (Non-Active Reefer) |
| `215235` | Reefer handling fields (humidity/airflow/etc.) present without active temperature setting |
| `200616` | Temperature set on non-active reefer container |
| `215184` | Humidity or AirFlow value has more than 2 decimal places |
| `215332` | Container temperature invalid format (strict format check via `TemperatureFormatValidationAndConversion`) |

---

### 6.4 Cargo Validations

#### REQUEST/AMEND Cargo Rules (`request/validation/CargoValidations`)

| Error Code | Condition |
|---|---|
| `997023` | Missing line item number |
| `997024` | Line item number > 5 characters |
| `997016` | Duplicate Outer/SingleLine line number |
| `997017` | INNER without corresponding OUTER for same line number |
| `997018` | INNERINNER without corresponding INNER |
| `215094` | Gross/Net weight invalid — must be positive whole or ≤ 3 decimal places |
| `215097` | Gross volume invalid — must be positive whole or ≤ 4 decimal places |
| `215095` | `marksAndNumbers` exceeds 9 lines |
| `215096` | Marks element > 35 characters |
| `999990` | Reference length: UCN/CCC > 45; others > 35 |
| `997015` | Invalid `PackageTypeCodeType` |
| `996003` | Package count not in `[1, 99,999,999]` |
| `996004` | Package count provided without `typeValue`/`typeDescription` |
| `997021` | Package count missing without packageType (XML edge-case) |
| `996005` | Package type missing |
| `996006` | Package type value not in reference data |
| `996016` | DG outer pack count missing or ≤ 0 |
| `996017` | DG outer pack `typeValue`/`typeDescription` missing |
| `997022` | Split goods missing equipment identifier |
| `221063` | Split goods container number not matching any container in equipment group |
| `221056` | Zero packages on REQUEST |

#### Dangerous Goods (DGS) Rules

| Error Code | Condition |
|---|---|
| `215333` | UN number missing |
| `996019` | UNDG variant > 4 characters |
| `215147` | Proper shipping name missing |
| `215331` | Flashpoint format invalid |
| `996007`/`996008` | DG net-net weight invalid (decimal/comma format) |
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

#### CONFIRM/PENDING Cargo Rules (`inbound/confirmation/validation/CargoValidations`)

| Error Code | Condition |
|---|---|
| `215094` | Cargo gross weight invalid (negative or `Weight.isInvalidWeight`) |
| `215079` | Invalid Outer-Pack package type code |
| `221111` | Package count provided without `typeValue`/`typeDescription` |
| `215147` | Proper shipping name required for DG |
| `215331` | Flashpoint format invalid |
| `996011` | DG emergency contact name without phone |

---

### 6.5 Reference Validations

#### Length Thresholds (all message types)

| Reference Type | Max Length | Error Code |
|---|---|---|
| `UniqueConsignmentNumber` | 45 | `999990` |
| `CanadianCargoControlNumber` | 45 | `999990` |
| `CarrierSourceBookingNumber` | 30 | `999990` |
| `BookingNumber` | 30 | `999990` |
| All other reference types | 35 | `999990` |

#### Business Rules

| Error Code | Condition |
|---|---|
| `200061` | Both `ContractNumber` and `FreightTariffNumber` present simultaneously |
| `200065` | Active booking with same OCBN already exists under the same carrier (REQUEST) |
| `200068` | Carrier-supplied `BookingNumber` (SMBN) present but carrier OV `submitterBookingNumberAllowed` not enabled |
| `200069` | OCBN in AMEND does not match OCBN on existing booking record |
| `206065` | Different INTTRA ref with same active OCBN under same carrier (CONFIRM/PENDING duplicate) |
| `224160` | CONFIRM without a `BookingNumber` (carrier booking number) reference |

---

### 6.6 Leg Validations

#### REQUEST/AMEND Leg Rules (`RequestLegValidations`)

Per leg endpoint (Start/End locations):

| Error Code | Condition |
|---|---|
| `215329` | More than one `EstimatedArrivalDate` or `EstimatedDepartureDate` for same leg endpoint |
| `215051` | `CCYYMMDD` date format invalid |
| `215052` | `CCYYMMDDHHMM` or `CCYYMMDDHHMMSS` format invalid |
| `200117` | `EstimatedArrivalDate` with non-`PlaceOfDischarge` leg or missing identifier+city |
| `200116` | `EstimatedDepartureDate` with non-`PlaceOfLoad` leg or missing identifier+city |
| `200107` | Leg-related field error |
| `200108` | Leg-related field error |
| `200767` | Leg-related field error |
| `200097` | Leg-related field error |
| `221028` | Leg-related field error |
| `215043` | Leg-related field error |
| `215047` | Leg-related field error |
| `215050` | Leg-related field error |

#### CONFIRM/PENDING Leg Rules (`LegValidations`)
Validates carrier transport leg semantics: vessel/voyage, sequence, stage (EDI map derivation).

---

### 6.7 Date Validations

**Global rule:** All key dates must be within **±400 days** of the current system date.

| Date Field | Error When Missing | Error When Out of Range |
|---|---|---|
| `messageDate` (confirm/pending/decline) | `206009` | `206010` |
| `creationDate` | `206009` | `206010` |
| `siDueDate` | — | `206012` |
| `vgmCutOffDate` | — | `200100` |
| `EarliestDepartureDate` at POR | — | `200039` |

Date formats accepted:

| Format | Usage |
|---|---|
| `CCYYMMDD` | Most dates (default) |
| `CCYYMMDDHHMM` | Fumigation date, timestamps |
| `CCYYMMDDHHMMSS` | Full timestamp |

---

### 6.8 Dimension Validations

`DimensionValidations.validateDimensions` — Out-of-gauge packages:

| Error Code | Condition |
|---|---|
| `102030` | Any `outOfGaugeDetails` package missing length/width/height, or any has null type or value |

**Out-of-Gauge dimension conversion** (when OOG OV constraint rule active):
`ValidationHelper.convertToFeet` — converts Inch / Centimeter / Meter to feet.
Special case: 253 m → 830 ft (ZIM workaround override).

---

### 6.9 Carrier Optional Validations (OV)

Carrier-configurable rules discovered via `@ValidationRuleInfo(ruleName=…)` annotation reflection.
Loaded from `optionalValidationsService.getOptionalValidations(carrierId)` and `("1000")` (Inttra-owned).

| Rule Name | Description | Error Code |
|---|---|---|
| `submitterBookingNumberAllowed` | Activates SMBN (carrier-provided booking number) | no-op |
| `spotRateBookingAllowed` | Allows spot rate bookings | no-op |
| `smartContainerAllowed` | Allows smart container equipment | no-op (gated by `CarrierValidations`) |
| `contractOrTariffNumberRequired` | Contract or tariff number must be present | `201202` |
| `cargoWeightRequired` | Cargo gross weight is mandatory | `201229` |
| `hsCodeRequired` | HS code required on cargo | `201228` |
| `emptyPositioningDateRequiredWithShipFrom` | ShipFrom haulage must include empty positioning date | `201232` |
| `fullPickUpDateTimeRequiredWithShipFrom` | ShipFrom haulage must include full pick-up date/time | `201233` |
| `bookingOfficeRequired` | Booking office location mandatory | `201236` |
| `contractPartyRequired` | Contract party must be included | `233180` |
| `consistentTemperatureSettingsRequired` | Reefer/hybrid containers must have consistent temperature | `200617` |
| `noDecimalsAllowedInTemperatureSettings` | Temperature must be whole number | `201999` |
| `emergencyDangerousGoodsContactRequired` | DG emergency contact mandatory | `201227` |
| `basicFreightOriginAndDestinationChargesRequired` | Must include `OceanFreight` + `OriginTerminalHandling` + `DestinationTerminalHandling` | `233176` |
| `departureDatesMustBeInTheFuture` | `EarliestDepartureDate`/`EstimatedDepartureDate` must be > now (UTC) | `233177` |
| `transportModeRequiredForPreOrOnCarriageLegs` | PreCarriage missing mode → `233178`; OnCarriage → `233179` | `233178`/`233179` |
| `specificChargeTypesRequired` | Specific charge types must be present | `233181` |
| `dangerousGoodsAndNonDangerousGoodsMustNotBeInSameBooking` | DG and non-DG cargo cannot be mixed | `233182` |
| `partyAddressRequired` | Forwarder or Shipper (by name) must include address fields | `233181` |
| `outOfGaugeWithinConstraints` | OOG dimensions must be within carrier limits | `300005` |
| `disableBookingForLocations` | Sanctioned location check (used by `InttraValidations`) | `UNAUTHORIZED_TRANSACTION` |
| `requestToAmendStateTransitionNotAllowed` | Blocks REQUEST→AMEND until carrier responds | `300006` |
| `amendToAmendStateTransitionNotAllowed` | Blocks AMEND→AMEND until carrier responds | `300006` |

OV conditions evaluated via `context.isActivated(conditions, conditionOperator)` — checks channel, POR/POD country, container type, etc.

---

### 6.10 Inttra Validations (Sanctioned Countries)

`InttraValidations.isBookingFromOrToSanctionedCountry`

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

## 7. Authorization Rules

```
┌──────────────────────────────────────────────────────────────┐
│                   Authorization Flow                          │
│                                                              │
│  REQUEST ──────────────────────────────────────────────────► │
│                                                              │
│  1. Is booker activated for the carrier?                     │
│     connectionsService.verify(bookerId, CARRIER, carrierId)  │
│     NO → AuthorizationException("285")                       │
│                                                              │
│  2. Is submitter in hierarchy or partnership with booker?    │
│     NO → AuthorizationException("200816")                    │
│                                                              │
│  AMEND / CANCEL ───────────────────────────────────────────► │
│                                                              │
│  Is actor associated with booking's resolved customer        │
│  parties OR in hierarchy/partnership with                    │
│  booker/shipper/forwarder?                                   │
│  NO → AuthorizationException("221009") [AMEND]              │
│       AuthorizationException("221010") [CANCEL]              │
│                                                              │
│  CARRIER messages ─────────────────────────────────────────► │
│                                                              │
│  If prior CONFIRM/DECLINE exists:                            │
│    existing carrierId must match inbound carrier             │
│    MISMATCH → AuthorizationException("224016")               │
│  If no prior CONFIRM/DECLINE: brand-swap allowed (skip)      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

| Error Code | Condition |
|---|---|
| `285` | Booker not activated for carrier |
| `200816` | Submitter not in hierarchy or partnership with booker |
| `221009` | Actor not authorized to AMEND |
| `221010` | Actor not authorized to CANCEL |
| `224016` | Carrier mismatch on existing confirmed/declined booking |

---

## 8. Split Booking Rules

`BookingService.doSplit(...)` — `isCarrierSplitAllowed(...)`:

```
Split is ALLOWED when ALL of:
  ├── contract.isSplit() == true
  ├── originalState ∈ {REPLACE, CONFIRM, PENDING, REQUEST, AMEND}
  └── splitState ∈ {CONFIRM, PENDING, DECLINE}

Otherwise → StateTransitionException("213001")
```

**On split:**
- All active details are cloned with the new `inttraReferenceNumber`
- `originalInttraReferenceNumber` preserved on cloned details
- OCBN uniqueness check applies to split-CONFIRM (via `bookerValidations.carrierReferenceNumberMustBeUnique`)

---

## 9. Reinstatement Rules (ION-9016)

Reinstatement applies when a booking is moved from `DECLINE` or `CANCEL` back to an active carrier state.

```
Trigger: fromState ∈ {DECLINE, CANCEL}
         toState   ∈ {PENDING, CONFIRM, REPLACE}

Actions:
1. contract.setReinstated(true)
2. Find latest customer detail with non-blank shipmentId
   (across REQUEST / AMEND / CANCEL details)
3. BookingReinstatementValidations.shipmentIdMustBeUnique(
     shipmentId, bookerId, inttraRef, originalInttraRef, false)
   → Ensures no other active booking under this booker has the same shipmentId
4. Throw BookingValidationException on failure
```

This prevents duplicate bookings being reinstated to the same operational shipment.

---

## 10. Data Models

### 10.1 Domain Entities

#### `Booking` (aggregate)

Key computed properties:

| Method | Logic |
|---|---|
| `calcCarrier()` | Brand-swap aware: for `PENDING` + first `DECLINE`/`CONFIRM`, resolves correct carrier |
| `calcBooker()` | Latest booker party |
| `calcState()` | Latest state from most-recent detail |
| `calcAllCompanyIdsWithAccess()` | All company IDs that may view this booking |
| `isCoreBooking()` | Determines if this is a core (non-INTTRA) booking |
| `isNonInttraBooking()` | True when booking originated outside INTTRA network |
| `getWorkflowId(metaData)` | Extracts workflow context from metadata |
| `fixAddressMess()` | Migrates `street01/02` → `unstructuredAddress01/02` for legacy data |

#### `BookingDetail` (DynamoDB entity)

| Attribute | Type | Notes |
|---|---|---|
| `bookingId` | String (UUID) | Partition key |
| `sequenceNumber` | String | Sort key. Format: `m_<epochMs>_<state>_<inttraRef>` |
| `version` | Integer | `@DynamoDbVersionAttribute` — optimistic locking |
| `expiresOn` | Long | TTL = now + 400 days |

**GSI Indexes:**

| Index Name | Partition Key | Sort Key |
|---|---|---|
| `INTTRA_REFERENCE_NUMBER_INDEX` | inttraReferenceNumber | — |
| `carrierId_carrierReferenceNumber` | carrierId | carrierReferenceNumber |
| `bookerId_shipmentId` | bookerId | shipmentId |
| `carrierScac_carrierReferenceNumber` | carrierScac | carrierReferenceNumber |

Stream view type: `KEYS_ONLY`

---

### 10.2 Field-Level Constraints

| Field | Model | Constraint |
|---|---|---|
| `unstructuredAddress01`–`04` | `Address` | `@Size(max=35)` |
| `street01`/`street02` | `Address` | Deprecated; migrated to unstructured |
| `Contact.name` | `Contact` | `@Size(max=35)` |
| `shipmentId` | `BookingRequestContract` | `@Size(max=35, message=ERROR_999990)` |
| `numberOfSeaWayBills` | `BookingRequestContract` | Length ≤ 35; must be positive whole number |
| Email address | `Contact` | max 512 characters |
| `DGS variant` | `DangerousGoods` | max 4 characters |
| `cargoLineNumber` | Cargo | max 5 characters |
| `maxRetries` (config) | `BookingConfig` | `@Max(5)` |
| Package count | `PackageDetail` | Range: 1–99,999,999 |
| Segregation groups | `DangerousGoods` | Max 4 groups |
| Marks & Numbers | `MarksAndNumbers` | Max 9 lines; max 10 elements/line; each element ≤ 35 chars |
| Equipment per booking | `Equipment` | Max 999 (→ `228008`) |
| Humidity/AirFlow decimals | `ReeferHandling` | Max 2 decimal places |
| Container Net Weight decimals | `Equipment` | Max 3 decimal places |
| Cargo gross/net weight decimals | `PackageDetail` | Max 3 decimal places |
| Cargo gross volume decimals | `PackageDetail` | Max 4 decimal places |

---

### 10.3 Enumerations

#### `BookingState`
`REQUEST, AMEND, PENDING, CONFIRM, DECLINE, CANCEL, REPLACE`

#### `Channel`
`WEB("Web"), API("API"), EDI("EDI"), DESKTOP("Desktop")`

#### `BookingDisposition`
`APPLIED, APPLIED_WITH_WARNINGS, IGNORED, REJECTED, DELETED`

**HTTP response mapping:**

| Disposition | HTTP Status |
|---|---|
| `APPLIED` | 200 |
| `APPLIED_WITH_WARNINGS` | 200 |
| `IGNORED` | 200 |
| `REJECTED` | 400 |
| `DELETED` | 200 |

#### `PartyRole`
`Booker, Carrier, Shipper, Forwarder, Consignee, ContractParty, FreightPayer, MessageRecipient, MainNotifyParty, FirstAdditionalNotifyParty, SecondAdditionalNotifyParty, BookingOffice, EmptyPickUp, IntermediateStopOff, ReeferSubcontractor, ShipFrom, ShipTo, FullDropOFF, CustomsBroker, Carrier_CounterParty, Requestor`

#### `ContactType`
`InformationContact, NotificationContact, ConfirmedWith, EquipmentContact, EmergencyDangerousGoodsContact`

#### `HaulageDateType`
`EstimatedDoorDeliveryDate, EarliestDropOffDate, ClosingDate, EmptyPositioningDate, FullPickUpDateTime, EmptyPickupDate, StopOffPositioningDate, RequestedEmptyPickUpDate`

#### `BookingResponseType` (CONFIRM/PENDING)
`Pending, Accepted, ConditionallyAccepted`

#### `MoveType` (required on all REQUEST/AMEND)
Checked by `MoveTypeValidations` → error `666666` if missing.

#### `ServiceType`
`FCLFCL` (and others) — FCLFCL requires equipment information on REQUEST (→ `221108`).

#### `PaymentTermType`
Accepted for charges: `PayableElsewhere, Prepaid, Collect` (all others → `214002`).

#### `EquipmentSizeCodeType`
`ISO` (others) — only `ISO` type triggers container-type resolution.

#### `PackageType`
`OUTER, INNER, INNERINNER, SINGLELINE` — hierarchical nesting rules enforced (INNER requires OUTER, INNERINNER requires INNER).

#### `SegregationGroup`
`None` + others (max 4; `None` cannot be mixed with others).

#### `WeightType`
`TNE` automatically converted to `KGM` (× 1000) for non-RoRo/non-Breakbulk bookings.

---

## 11. DAO & Persistence Rules

### `BookingDetailDao`

All reads use **consistent reads** (strong consistency) except GSI queries (eventual, then re-fetched with consistent read).

| Method | Consistency | Notes |
|---|---|---|
| `findByBookingId` | Strong | Partition-key scan |
| `findByInttraReferenceNumber` | Eventual then Strong | GSI query + consistent re-fetch |
| `findByCarrierIdAndCarrierReferenceNumber` | Eventual | GSI: `carrierId_carrierReferenceNumber` |
| `findBySubmitterIdAndShipmentId` | Eventual | GSI: `bookerId_shipmentId` |
| `findByCarrierScacAndCarrierReferenceNumber` | Eventual | GSI: `carrierScac_carrierReferenceNumber` |
| `findByBookingIdSequenceNumber` | Strong | GET item |
| `findLatestCarrierAndCustomerVersions` | — | Sorts by seq lexicographically; picks latest carrier-status and latest customer-status |

**Optimistic locking:** `@DynamoDbVersionAttribute Integer version` — concurrent updates throw and are retried by `BookingService`.

**DynamoDB resilience:** On `DynamoDbException`, retried up to `config.getDynamoExceptionMaxRetryCount()`. On ultimate failure, writes `dynamo_error/{workflowId}` to S3 workspace.

### `RapidReservationDao`
Backing store for pre-allocated carrier booking number ranges.

### `SequenceIdDao` / `UniqueIdDao`
INTTRA reference number allocation — per-carrier prefix strategy when `inttraRefConfig.carrierCompanyIds` includes the carrier (e.g. ZIM `850803`).

### Elasticsearch (`Indexer` / `Searcher`)
- Static aggregation names: `STATE_AGGREGATION_NAME`, `CARRIER_ID_AGGREGATION_NAME`, `LAST_MODIFIED_DATE_AGGREGATION_NAME`, `CREATED_BY_AGGREGATION_NAME`
- `complianceRisk` field excluded from search source by default (gated by `cargoScreenTrialPeriod` or `CargoScreenPreference`)

---

## 12. Outbound Pipeline

```
BookingService.processOutbound()
        │
        ▼
OutboundService
  ├── Subscription lookup (per carrier/booker subscriptions)
  ├── Diff generation (DiffGenerator)
  │     ├── EquipmentDiff
  │     ├── HeaderPartiesDiff
  │     ├── HeaderReferencesDiff
  │     ├── OtherAttributesDiff
  │     ├── PackageDetailsDiff
  │     ├── TransactionLocationsDiff
  │     └── TransportLegDiff
  ├── Enrichment
  │     ├── LocationEnrichment
  │     ├── PartyEnrichment
  │     ├── EquipmentEnrichment
  │     └── PackageEnrichment
  ├── Email (SES via OutboundEmailSender)
  │     Templates: Request/Amend, Confirm/Pending, Decline/Replace, Cancel, Internal Error, Validation Error
  ├── Webhook
  ├── EDI / API partner integration
  └── SNS event publication (BookingEventRelay)
```

**Error scenarios → outbound channels:**

| Error Type | Outbound Channel |
|---|---|
| `TransformationException` | APERAK (transformation error) |
| Business validation errors | APERAK + Email |
| Internal errors | Internal error email |

**Customizations per carrier:**
- `HeinekenCustomization` — Heineken-specific EDI transformations
- `SpecialCharCustomization` — Special character handling
- ZIM carrier (company `850803`): region-based routing — `ZIMHF` (default) / `ZIMHK` (Asia-Pacific) / `ZIMOR` (Americas/Caribbean) based on origin country ISO-2 codes

---

## 13. Lambda Processing Rules

### IndexerHandler

```
Environment Variables:
  maxRetries            (default: 5)
  connTimeoutMillis
  readTimeoutMillis
  AWS_DEFAULT_REGION
  elasticsearchEndpointUrl
  dynamoDbEnvironment
  enableCoreBookingSearch (boolean)

DynamoDB Stream events:
  INSERT/MODIFY → Indexer.index(booking)
    └── Skip if: booking.isCoreBooking() AND enableCoreBookingSearch=false
  REMOVE        → Indexer.delete(inttraReferenceNumber)
    └── inttraRef parsed from sequenceNumber split on "_" at position 3
```

### S3ArchiveHandler

```
Environment Variables:
  s3ArchiveBucket           (main archive)
  soS3ArchiveBucket         (SO contract archive)
  reportbridgeSNSTopicArn   (analytics)
  maxRetries
  enableCoreBookingArchive  (boolean)
  tntEnabled                (Track & Trace)
  tntAPI                    (T&T endpoint)
  tokenEnv                  (T&T auth)

Events processed: INSERT only

S3 key: YYYY/MM/DD/HH/{bookingId}_{sequenceNumber} (UTC)

Routing:
  SOBookingRequestContract / SOCancelContract → soS3ArchiveBucket
  All others                                 → s3ArchiveBucket
  enableCoreBookingArchive=false → skip core bookings

Optional Track-and-Trace POST when tntEnabled=true
```

---

## 14. Converters & Mappers

### DynamoDB Attribute Converters (`dynamodb/`)

| Converter | Purpose |
|---|---|
| `BookingStateConverter` | `BookingState` enum ↔ DynamoDB string |
| `ContractAttributeConverter` | Contract payload JSON ↔ DynamoDB |
| `ContractTypeConverter` | `ContractEnum` discriminator |
| `QuantityTypeConverter` | Weight/Volume quantities |
| `SpotRatesConverter`/`SpotRatesAttributeConverter` | Spot rate data |
| `ConditionListAttributeConverter` | OV condition lists |
| `EnrichedAttributesConverter` | Resolved party/location enrichment |
| `RangeAttributeConverter` | Rapid Reservation number ranges |
| `AuditAttributeConverter` | `createdDateUtc`, `modifiedBy` |
| `LegacyMapConverter` | Backward-compatible legacy attributes |
| `MetaDataConverter` | SQS/workflow metadata |
| `LocalDateTimeTypeConverter` / `OffsetDateTimeTypeConverter` | Date type conversions |

### Weight Conversion (ValidationService)

```
TNE → KGM (× 1000):
  Applies to NON RoRo AND NON BreakBulk bookings only.
  Fields converted:
    - goodsGrossWeight
    - goodsNetWeight
    - splitGoodsDetails.grossWeight
    - dangerousGoods.netNetWeight
    - dangerousGoods split weights
    - equipment.netWeight
```

### Address Backward Compatibility

`BackwardCompatibilityUtil.mergeSegregationGroups` — legacy single segregation group field → list.
`Booking.fixAddressMess` — `street01/02` → `unstructuredAddress01/02`.

### Outbound Email Converters

`CancelEmailVariablesConverter`, `ConfirmPendingEmailVariablesConverter`, `DeclineReplaceEmailVariablesConverter`, `RequestAmendEmailVariablesConverter`, `MetadataVariableConverter`.

---

## 15. Utilities & Cross-Cutting Logic

### `BookingServiceUtil`
- `supplementNatureOfCargo(contract)` — enriches cargo nature/classification fields
- `trimPackageDescription(contract)` — trims oversized descriptions

### `BackwardCompatibilityUtil`
- `mergeSegregationGroups` — handles legacy single-value segregation to list migration

### `IdGenerator` / `UniqueId` / `SequenceId`
- INTTRA reference numbers ≥ `2,000,000,000`
- Per-carrier prefix strategy (e.g. ZIM `850803`)
- `SequenceId` format: `m_<epochMs>_<state>_<inttraRef>`

### `MessageSupport`
- i18n bundle resolution for all validation error messages
- `newELContext("k", v, …)` builds EL expression context for `${token}` substitution in messages
- Localized bundles available: EN (default), ES, FR, JA, PT, TR, ZH_CN, ZH_TW

### `CappedExponentialBackOff`
Retry back-off strategy with configurable `maxRetries`, `maxDelay`, `baseDelay`.

### `GZip`
Compression helper for large payload storage.

### `AWSUtil`
Common AWS utilities (region detection, parameter store helpers).

### `QuantitySupport`
Quantity arithmetic for weight/volume calculations.

### `EnumValidator` / `DoubleLengthValidator` / `StringListPattern`
Custom Bean Validation constraint annotations.

### `FlexibleLocalDateTimeDeserializer`
Accepts multiple date-time formats during JSON deserialization.

### `TaskIdGenerator`
Lambda task ID generation.

---

## 16. Configuration & Feature Flags

### `BookingConfig` (DropWizard)

| Property | Type | Notes |
|---|---|---|
| `dynamoDbConfig` | `BaseDynamoDbConfig` | `@Valid @NotNull` |
| `elasticsearchConfig` | `ElasticsearchConfig` | |
| `enableSwaggerUI` | boolean | Default: `false` |
| `s3ArchiveBucket` | String | Main S3 archive bucket |
| `appianWayConfig.s3WorkSpaceLocation` | String | SQS payload S3 workspace |
| `appianWayConfig.inQueueUrl` | String | Inbound SQS queue URL |
| `appianWayConfig.snsTopicARN` | String | Outbound SNS topic |
| `appianWayConfig.waitTimeSeconds` | int | Default: 20 |
| `appianWayConfig.maxNumberOfMessages` | int | Default: 1 |
| `appianWayConfig.listenerEnabled` | boolean | |
| `appianWayConfig.outboundEnabled` | boolean | |
| `bookingBridgeSQS` | String | Legacy routing queue |
| `nonInttraEnabled` | boolean | Feature flag for non-INTTRA bookings |
| `bookingAppIdentity` | String | `"INTTRA"` or `"NON_INTTRA"` |
| `cargoScreenTrialPeriod` | String (boolean) | Show `complianceRisk` in search |
| `useSequenceId` | boolean | Switches INTTRA reference generation strategy |
| `removeNestedEmailTag` | boolean | Default: `false` |
| `maxRetries` | int | `@Max(5)`, default: 3 |
| `maxDelay` | int | Default: 10,000 ms |
| `baseDelay` | int | Default: 100 ms |
| `dynamoExceptionMaxRetryCount` | int | DynamoDB retry ceiling |
| `inttraRefConfig.carrierCompanyIds` | List\<String\> | Carriers with per-prefix IDs (e.g. `["850803"]`) |
| `spotRatesConfig` | `SpotRateConfig` | Maersk URL, auth |
| `watermillConfig` | `WatermillConfig` | Analytics event bus |

### Guice Modules

| Module | Purpose |
|---|---|
| `BookingApplicationModule` | Root Guice wiring |
| `BookingDynamoModule` | DynamoDB bindings |
| `BookingMessagingModule` | SQS/SNS bindings |
| `BookingEmailSenderModule` | SES email |
| `InboundServiceModule` | Inbound EDI services |
| `OutboundServiceModule` | Outbound notification services |
| `LocalCacheModule` | Guava cache (network service responses) |
| `SystemUTCClockModule` | UTC clock injection |
| `ExternalWrapperModule` | Hystrix + `@ExternalCall` retry interceptor |

---

## 17. External Integrations

### Network Service APIs (via `NetworkServiceClient` + Hystrix wrapper)

| Service | Purpose |
|---|---|
| Auth | Token validation, principal resolution |
| Network Participant | Company hierarchy, children lookup |
| Connections | Booker↔carrier activation verification (`#285`) |
| Geography / Country | Country-by-name resolution, ISO Alpha-2 lookup |
| Reference Data | Package types, container types |
| Format Service | EDI/API format resolution |
| Integration Profile | Carrier profile + format |
| Subscription | Outbound subscription discovery |
| Blacklist Email | Email block-list check |
| Participant Addons | Additional participant configuration |
| Alias | Partner alias resolution |
| User Service | Login → companyId (`/hasaccess` endpoint) |
| Webhook | Webhook delivery |

### Maersk Spot Rates

- Endpoint: `https://offers.api.maersk.com/offers/v2/offers`
- Auth: AWS Parameter Store `awsps:/inttra/{env}/booking/config/maerskAPIToken`
- Mapping: `MaerskResponseToCanonical`

### AWS Services

| Service | Usage |
|---|---|
| DynamoDB | BookingDetail, RapidReservation, Template, SpotRates, SpotRatesToInttraRef, SequenceId, UniqueId |
| SQS | Inbound (`inQueueUrl`), transformer (`transformerSQSUrl`), legacy bridge (`bookingBridgeSQS`), outbound queues |
| SNS | Outbound events (`snsTopicARN`), report bridge (`reportbridgeSNSTopicArn`) |
| S3 | Workspace (inbound payloads), archive buckets |
| Elasticsearch | Booking search index (AWS-signed Jest client) |
| Lambda | Indexer, S3Archive (triggered by DynamoDB Streams) |
| SES | Outbound email via `OutboundEmailSender` |
| Parameter Store | Secrets and config (`awsps:` placeholders) |

### Watermill
Analytics/event bus for booking events (`WatermillService` / `WatermillConfig`).

### Track-and-Trace (Optional)
POST to `tntAPI` endpoint from `S3ArchiveHandler` when `tntEnabled=true`.

---

## 18. Error Code Reference

### Exception Types

| Exception | Extends | Carries |
|---|---|---|
| `AuthorizationException` | `SecurityException` | Code, Contract, EnrichedAttributes |
| `BookingNotFoundException` | `NotFoundException` | Code, Contract, EnrichedAttributes |
| `ResolutionException` | `IllegalArgumentException` | Code, Contract, EnrichedAttributes |
| `StateTransitionException` | `RuntimeException` | Code, Contract, EnrichedAttributes |
| `StructuralValidationException` | `RuntimeException` | JSR-303 ValidationErrors + Contivo annotations |
| `TransformationException` | `RuntimeException` | EDI/XML format failure |
| `InternalException` | `RuntimeException` | Wrapped Throwable, stack trace |
| `BookingValidationException` | `RuntimeException` | List\<ValidationError\>, EnrichedAttributes |
| `DBRecordNotFoundException` | `RuntimeException` | Not-found from DynamoDB |

**HTTP fallback:** `BookingExceptionMapper` maps all uncoded exceptions to `"000200"`.

### Complete Error Code Table

| Code | Domain | Message Summary |
|---|---|---|
| `000200` | Generic | Uncoded/catch-all error |
| `000304` | State | Booking State is Invalid/Missing |
| `102030` | Dimensions | Out-of-gauge details incomplete |
| `200030` | Header Location | Place of Receipt required |
| `200031` | Header Location | POR and POD are the same location |
| `200037` | Location Date | Must provide departure/arrival date or vessel |
| `200039` | Location Date | Earliest Departure not within 400 days |
| `200040`/`200048` | Location Date | Latest Delivery date range/format error |
| `200042` | Header Location | Place of Delivery required |
| `200061` | Reference | Both Contract Number and Tariff Number present |
| `200065` | Reference | Active OCBN already exists for carrier (duplicate) |
| `200068` | Reference | Carrier-supplied booking number (SMBN) not allowed |
| `200069` | Reference | OCBN mismatch on AMEND |
| `200097`/`200107`/`200108`/`200116`/`200117` | Leg | Various leg date/location field errors |
| `200118` | Carrier | Carrier mismatch on existing booking |
| `200130`/`200131`/`200132` | Party/Contact | Information contact name/comm rules |
| `200134`/`200135`/`200138`/`200140` | Party/Contact | Phone/email/fax rules |
| `200407` | Party | MessageRecipient lacks notification contact |
| `200614` | Reefer | Reefer container missing temperature |
| `200615` | Reefer | Non-reefer container with temperature/NAR |
| `200616` | Reefer | Temperature on non-active reefer |
| `200617` | Reefer | Inconsistent temperature settings (OV) |
| `200663`/`200664` | Haulage | Haulage contact/party missing fields |
| `200771`/`200773`/`200774` | Party | Shipper/Forwarder identity rules |
| `200800`/`200801` | Equipment | Count rules with identifier/FCLFCL |
| `200816` | Auth | Submitter not in hierarchy/partnership |
| `201202` | OV | Contract or tariff number required |
| `201227` | OV | DG emergency contact required |
| `201228` | OV | HS code required |
| `201229` | OV | Cargo weight required |
| `201232`/`201233` | OV | Haulage date required with ShipFrom |
| `201236` | OV | Booking office required |
| `201999` | OV | No decimals in temperature |
| `206009`/`206010` | Header Date | Creation/message date missing or out of range |
| `206012` | Header Date | SI Due Date out of range |
| `206065` | Reference | Duplicate OCBN on different INTTRA ref (CONFIRM) |
| `206084` | Locator | INTTRA ref not found |
| `206590` | Equipment | Inconsistent haulage arrangement codes |
| `206763` | Equipment | numberOfContainers ≠ 1 with identifier |
| `206800` | Decline | Carrier comments required for Decline/Replace |
| `206809` | Party | Booker mismatch |
| `213001` | State | Transition not allowed |
| `213002` | State | Transition not allowed for non-INTTRA |
| `214002` | Party | Invalid freight payment term |
| `215020`/`215023` | Location | UNLOC unresolved / country code mismatch |
| `215024`/`215025` | Date | Invalid date values |
| `215051`/`215052` | Leg Date | Date format errors |
| `215054` | Party | Duplicate party role |
| `215066`/`215067` | Party | Missing/invalid party identifier |
| `215079` | Cargo | Invalid outer pack code |
| `215094` | Cargo/Weight | Invalid gross/net weight |
| `215095`/`215096` | Cargo | Marks & Numbers line/element count/length |
| `215097` | Cargo | Invalid volume |
| `215147` | DGS | Proper shipping name required |
| `215170`/`215171` | Equipment | Duplicate container number / invalid size code |
| `215180` | Equipment | Container net weight invalid format |
| `215184` | Reefer | Humidity/airflow too many decimals |
| `215235` | Reefer | Reefer handling fields without active temp |
| `215285` | Equipment | Haulage party missing identifiers |
| `215289`/`215291` | Haulage | Wrong party role for haulage date type |
| `215329` | Leg | Multiple arrival/departure dates |
| `215331` | DGS | Flashpoint format invalid |
| `215332` | Reefer | Temperature format invalid |
| `215333` | DGS | UN number missing |
| `215343` | Haulage | Reefer subcontractor date invalid |
| `221001`/`221005`/`221006`/`221103` | Locator | ShipmentId duplicate/missing/ambiguous |
| `221009`/`221010` | Auth | AMEND/CANCEL not authorized |
| `221020` | Header Location | Duplicate location type |
| `221023`/`221024`/`221025`/`221028` | Location | Alias/date format/value errors |
| `221030`/`221033`/`221037` | Party | Booker resolution failures |
| `221056` | Cargo | Zero cargo on REQUEST |
| `221063` | Cargo | Split goods container not in equipment group |
| `221108` | Equipment | FCLFCL must include equipment |
| `221111` | Cargo | Package count without type description |
| `224002`/`224003` | Locator | Carrier message lookup failure |
| `224016` | Auth | Carrier mismatch / brand swap |
| `224018` | Header | Invalid response type for CONFIRM |
| `224075` | Location | Alias unresolved (AMS locations) |
| `224099`/`224101`/`224102` | Party | Carrier resolution failures |
| `224139`/`224141`/`224143`/`224145`/`224147` | Haulage | Wrong party type for haulage date |
| `224160` | Reference | Missing carrier booking number on CONFIRM |
| `228003` | Party | Invalid party role |
| `228007` | Header/Party | CTA without COM |
| `228008` | Party/Equipment | Communication count > 9 / Equipment > 999 |
| `233176`/`233177`/`233178`/`233179`/`233180`/`233181`/`233182` | OV | Various carrier-optional validations |
| `285` | Auth | Booker not activated for carrier |
| `300001` | Carrier | Smart container not authorized |
| `300002` | Carrier | DGS net weight required by carrier |
| `300003`/`300004` | Carrier | RoRo / Breakbulk not accepted by carrier |
| `300005` | Carrier | OOG dimensions exceed carrier limits |
| `300006` | Carrier | Amend not allowed (carrier response required first) |
| `300007`/`300008` | Carrier | RoRo/Breakbulk container code not authorized |
| `303030` | Document | Sea waybill count not a positive whole number |
| `333333` | Header Location | Invalid location type |
| `666660` | Booker | ShipmentId required for EDI channel |
| `666666` | MoveType | MoveType missing |
| `996003`–`996019` | DGS/Cargo | DG and package count/type rules (see §6.4) |
| `997009`–`997024` | Equipment/Cargo | Various field format/count rules (see §6.3, §6.4) |
| `999990` | Reference/Doc | Field length exceeded |
| `UNAUTHORIZED_TRANSACTION` | Inttra | Sanctioned country/location |

---

## 19. Constants Quick Reference

| Constant | Value | Location |
|---|---|---|
| `INTTRA_COMPANY_ID` | `"1000"` | `ValidationPlanFactory`, `ValidationService`, `PartyLocator` |
| `INTTRAREF_SEED_VALUE` | `2,000,000,000` | `BookingProcessorTask` |
| `MAX_RR_ATTEMPTS` | `3` | `BookingService` |
| `MAX_CONTACT_COMM_COUNT` | `9` | `PartyValidations` |
| `MAX_DATE_RANGE_DAYS` | `400` | Date validations, booking TTL |
| `MAX_RETRIES` (DynamoDB) | via `dynamoExceptionMaxRetryCount` config | `BookingService` |
| `MAX_RETRIES` (Lambda) | `5` (env `MAX_RETRIES_PROPERTY`) | `IndexerHandler` |
| `RAC` | `"requestBooking"` | `BookingProcessorTask` |
| `CPD` | `"confirmBooking"` | `BookingProcessorTask` |
| `EDI_CLIENT` | `"BOOKING_ADMIN"` | `BookingProcessorTask` |
| `MARKS_AND_NUMBER_TOKEN_REGEX` | `"#$%"` | `ValidationService` |
| Reference max lengths | UCN/CCC: 45; OCBN/BkgNum: 30; others: 35 | `ReferenceValidations` |
| Equipment count max | 999 | `EquipmentValidations` |
| Package count range | 1–99,999,999 | `CargoValidations` |
| Segregation groups max | 4 | `CargoValidations` |
| Marks & Numbers | 9 lines × 10 elements × 35 chars | `CargoValidations` |
| Address/Contact fields | 35 chars | `Address`, `Contact`, `BookingService` |
| Email max | 512 chars | `PartyValidations` |
| DG UNDG variant max | 4 chars | `CargoValidations` |
| Cargo line number max | 5 chars | `CargoValidations` |
| Humidity/AirFlow decimals | 2 | `EquipmentValidations` |
| Weight/volume decimals | weight: 3; volume: 4 | `EquipmentValidations`, `CargoValidations` |
| ZIM carrier company ID | `"850803"` | `IdGenerator`, `customizationConfig` |
| ZIM region default | `ZIMHF` | `BookingConfig.customizationConfig` |
| SeaWayBill max length | 35 chars | `RequestAmendDocumentValidations` |
| SQS wait time | 20 seconds | `appianWayConfig` |
| SQS max messages per poll | 1 | `appianWayConfig` |
| Booking TTL | `now + 400 days` | `BookingService.calcExpiresOn` |
| TNE→KGM multiplier | × 1000 | `ValidationService.convertFromTNE` |

---

*Document generated: 2026-04-27. Covers booking module as of branch `develop`.*
