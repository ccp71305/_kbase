# Registration Service — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `registration/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Domain Model](#3-domain-model)
4. [Registration Workflow](#4-registration-workflow)
5. [API Endpoints](#5-api-endpoints)
6. [Business Rules](#6-business-rules)
7. [Email Templates](#7-email-templates)
8. [External Integrations](#8-external-integrations)
9. [Default User Configuration](#9-default-user-configuration)
10. [Validation Reference](#10-validation-reference)
11. [Exception Reference](#11-exception-reference)

---

## 1. Overview

The **Registration Service** manages the end-to-end lifecycle of new company registrations on the Mercury/INTTRA platform. It handles:

- Self-service registration form submission (public endpoint)
- Admin review, assignment, and processing workflows
- OFAC compliance screening
- Company and user account creation on approval
- Email notifications at every stage

**Root Path:** `/`  
**Data Store:** DynamoDB (with optimistic locking)

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | DropWizard (JAX-RS) |
| DI Framework | Google Guice |
| Database | DynamoDB (AWS SDK v2 Enhanced Client) |
| Validation | Jakarta Bean Validation |
| Build | Maven (Java 17) |
| Testing | JUnit 5, Mockito 5.17, DynamoDB Local |

---

## 3. Domain Model

### 3.1 RegistrationDetail (DynamoDB Entity)

**Table:** `RegistrationDetail`  
**Primary Key:** `registrationId` (UUID, auto-generated)  
**Sort Key:** None  
**GSI:** `REGISTRATION_STATUS_SUBMITTED_ON_INDEX` (PK: `registrationStatus`, SK: `submittedOn`, Projected: `assignedToUserId`)  
**TTL:** `expiresOn` — 400 days from submission  
**Streams:** `KEYS_ONLY`  
**Versioning:** DynamoDB optimistic locking via `version` attribute

| Field | Type | Validated | Description |
|-------|------|-----------|-------------|
| `registrationId` | String | Auto-gen UUID | Primary key |
| `version` | Integer | DynamoDB managed | Optimistic lock version |
| `companyName` | String | @NotBlank | Company legal name |
| `companyRole` | CompanyRole enum | @NotNull | Business role |
| `scacCode` | String | Custom | SCAC (carriers only, max 35 chars, alphanumeric) |
| `streetAddress` | String | @NotBlank, @Size(40) | Address line 1 |
| `streetAddress2` | String | @Size(40) | Address line 2 (optional) |
| `countryCode` | String | @NotBlank | ISO country code |
| `countryName` | String | @NotBlank | Country display name |
| `subdivisionName` | String | Optional | State/province |
| `cityName` | String | @NotBlank | City name |
| `postalCode` | String | Optional | ZIP/postal code |
| `taxId` | String | Optional | Government/tax ID |
| `firstName` | String | @NotBlank | Contact first name |
| `lastName` | String | @NotBlank | Contact last name |
| `businessEmail` | String | @NotBlank | Contact email (used for blacklist and domain checks) |
| `phoneNumber` | String | @NotBlank | Contact phone |
| `preferredLanguage` | String | @NotBlank | Language code |
| `jobLevel` | String | @NotBlank | Job level/title |
| `jobFunction` | String | @NotBlank | Job function |
| `termsOfServiceChecked` | Boolean | Optional | T&C acceptance |
| `communicationConsentChecked` | Boolean | Optional | Marketing consent |
| `inttraCompanyId` | String | Optional | Generated on assignment |
| `registrationStatus` | RegistrationStatus enum | Auto-managed | Current workflow state |
| `submittedOn` | OffsetDateTime | Auto-set | Submission timestamp (RFC 3339) |
| `approvedOn` | OffsetDateTime | Auto-set | Approval timestamp |
| `assignedToUserId` | String | Optional | Admin user handling this |
| `assignedToUser` | String | Optional | Admin user name |
| `activityMessageLogs` | List\<MessageLog\> | Optional | Chronological activity log |
| `audit` | Audit object | Auto-set | Created/modified by and at |
| `expiresOn` | Date (epoch) | Auto-calc | DynamoDB TTL |

### 3.2 CompanyRole Enum

| Value | Description |
|-------|-------------|
| `Shipper` | Company that ships goods |
| `Freight_Forwarder` | Freight forwarding company |
| `Preferred_Partner` | Preferred business partner |
| `Consignee` | Goods receiving company |
| `Custom_House_Broker` | Customs brokerage |
| `Notify_Party` | Party to be notified |
| `Carrier_NVO` | Non-Vessel Operating Common Carrier |
| `Carrier_VO` | Vessel Operating Carrier |

> **Note:** SCAC codes are only valid for `Carrier_NVO` and `Carrier_VO`.

### 3.3 RegistrationStatus State Machine

```
SUBMITTED
    │
    ├─ async: assign InttraCompanyId
    │         └─► (no status change)
    │
    ├─ async: compliance check
    │         ├─► OFAC_PASSED
    │         ├─► OFAC_FAILED
    │         └─► PENDING_OFAC (on error)
    │
    ├─ admin: place on hold ──────────────────► ON_HOLD
    │
    ├─ admin: decline ────────────────────────► DECLINED (terminal)
    │
    └─ admin: approve (requires OFAC_PASSED)
              │
              ├─► EMAIL_BLACKLISTED (abort)
              ├─► COMPANY_CREATED
              ├─► DOMAIN_WHITELISTED | DOMAIN_WHITELIST_FAILED
              ├─► USER_CREATED | USER_CREATION_FAILED
              └─► COMPLETED (terminal)
```

**Terminal statuses:** `COMPLETED`, `DECLINED`

---

## 4. Registration Workflow

### 4.1 Submission (Public)

```
POST /register
  ├─ Validate required fields (bean validation)
  ├─ Validate SCAC code (if carrier):
  │     - Trim and uppercase
  │     - Must be alphanumeric (no spaces/special chars)
  │     - Max 35 characters
  │     - Must be unique (check NetworkParticipantService)
  ├─ Generate UUID registrationId
  ├─ Set status = SUBMITTED
  ├─ Save to DynamoDB
  └─ Async (background thread):
        1. Send welcome email (WLC)
        2. Generate InttraCompanyId (via CompanyService)
        3. Run OFAC compliance check
           ├─ PASS → status = OFAC_PASSED
           ├─ HOLD → status = OFAC_FAILED
           └─ Error → status = PENDING_OFAC
```

### 4.2 Admin Approval

```
POST /process/approve?registrationId=X&versionNumber=N
  ├─ Validate status == OFAC_PASSED (else 400)
  ├─ Check email not blacklisted (BlackListService)
  │     └─ If blacklisted → status = EMAIL_BLACKLISTED, abort
  ├─ Create company (CompanyService)
  │     └─ status = COMPANY_CREATED
  ├─ Whitelist email domain (DomainWhitelistService)
  │     └─ status = DOMAIN_WHITELISTED | DOMAIN_WHITELIST_FAILED
  ├─ Create user (UserService) — skipped if E2Proxy enabled
  │     └─ status = USER_CREATED | USER_CREATION_FAILED
  ├─ Send approval email (APR)
  └─ status = COMPLETED
```

### 4.3 Version-Based Optimistic Locking

Every state-changing operation requires `registrationId` + `versionNumber`. If the version does not match the current DynamoDB version, a `VersionMismatchException` is thrown (HTTP 409).

---

## 5. API Endpoints

**Base Path:** `/`  
**Content-Type:** `application/json`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/register` | — (public) | Submit new registration |
| `POST` | `/assign` | `REGISTRATION_ADMIN` | Assign registration to admin user |
| `GET` | `/{registrationId}` | `REGISTRATION_ADMIN` | Get single registration |
| `GET` | `/fetch/{registrationfetchtype}` | `REGISTRATION_ADMIN` | List registrations by status filter |
| `POST` | `/process/assigninttracompanyId` | `REGISTRATION_ADMIN` | Manually assign INTTRA company ID |
| `POST` | `/process/docompliance` | `REGISTRATION_ADMIN` | Manually trigger OFAC check |
| `POST` | `/process/approve` | `REGISTRATION_ADMIN` | Approve registration |
| `POST` | `/process/update` | `REGISTRATION_ADMIN` | Update registration details |
| `POST` | `/process/decline/{emailType}` | `REGISTRATION_ADMIN` | Decline registration |
| `POST` | `/process/onhold` | `REGISTRATION_ADMIN` | Place registration on hold |
| `POST` | `/process/sendemail/{emailType}` | `REGISTRATION_ADMIN` | Resend email |
| `GET` | `/export` | `REGISTRATION_ADMIN` | Export all registrations |
| `DELETE` | `/delete/{registrationId}` | `REGISTRATION_ADMIN` | Delete registration |

### Query Parameters

| Endpoint | Parameter | Type | Required | Description |
|----------|-----------|------|----------|-------------|
| All `/process/*` | `registrationId` | String | Yes | Registration UUID |
| All `/process/*` | `versionNumber` | Integer | Yes | Optimistic lock version |
| `/process/update` | `triggerofac` | Boolean | No | Re-trigger OFAC check on update |
| `/fetch/{type}` | `type` (path) | RegistrationFetchType | Yes | `ALL`, `OPEN`, `ASSIGNED`, `UNASSIGNED`, `TERMINAL` |
| `/process/decline/{emailType}` | `emailType` (path) | EmailType | Yes | Must be `DDA`, `DNR`, or `DUA` |
| `/process/sendemail/{emailType}` | `emailType` (path) | EmailType | Yes | Any valid EmailType |

---

## 6. Business Rules

### 6.1 SCAC Code Validation

| # | Rule |
|---|------|
| BR-REG-SCAC-1 | SCAC codes are only permitted for `Carrier_NVO` and `Carrier_VO` roles. |
| BR-REG-SCAC-2 | SCAC code is trimmed, converted to **uppercase**, and must be alphanumeric (no spaces or special characters). |
| BR-REG-SCAC-3 | Maximum length is **35 characters**. |
| BR-REG-SCAC-4 | The SCAC code must be **unique** across all existing active network participants. |
| BR-REG-SCAC-5 | If the company role is changed to a non-carrier role during an update, the SCAC code is **automatically removed**. |

### 6.2 Approval Rules

| # | Rule |
|---|------|
| BR-REG-APR-1 | Approval can only proceed when status is **`OFAC_PASSED`**. Any other status returns `400 Bad Request`. |
| BR-REG-APR-2 | The `businessEmail` must not be blacklisted. If blacklisted, status is set to `EMAIL_BLACKLISTED` and approval halts. |
| BR-REG-APR-3 | An INTTRA Company ID must be generated before approval (`inttraCompanyId` must not be null). |
| BR-REG-APR-4 | If the E2Proxy flag is enabled for the environment, user creation is **skipped** during approval. |
| BR-REG-APR-5 | On any step failure during approval, status is set to `FAILED` and an exception is thrown. |

### 6.3 Compliance / OFAC Rules

| # | Rule |
|---|------|
| BR-REG-OFAC-1 | OFAC screening maps `RpsStatus.PASS` → `OFAC_PASSED`. |
| BR-REG-OFAC-2 | OFAC screening maps `RpsStatus.HOLD` → `OFAC_FAILED`. |
| BR-REG-OFAC-3 | On exception during compliance check, status is set to `PENDING_OFAC` (not terminal — can be retried manually). |
| BR-REG-OFAC-4 | Compliance check uses `Action.FULL_UPDATE` on the RPS service. |

### 6.4 Assignment Rules

| # | Rule |
|---|------|
| BR-REG-ASN-1 | An admin assigns themselves to a registration; only the assigned admin can perform state transitions requiring assignment validation. |
| BR-REG-ASN-2 | Assignment does not change the registration status. |
| BR-REG-ASN-3 | `AssignUserRequest` requires: `registrationId`, `versionNumber`, `assignToUserId`, `assignToUserName`. |

### 6.5 Decline Rules

| # | Rule |
|---|------|
| BR-REG-DCL-1 | Decline always transitions to `DECLINED` (terminal). |
| BR-REG-DCL-2 | Only email types `DDA`, `DNR`, or `DUA` are valid for decline. Any other type returns `400 Bad Request`. |

### 6.6 Data Retention & Listing Rules

| # | Rule |
|---|------|
| BR-REG-LST-1 | DynamoDB TTL is **400 days** from submission date. Records auto-delete after this. |
| BR-REG-LST-2 | The listing endpoints only return registrations **≤ 60 days old** (queried via GSI `submittedOn` filter). |
| BR-REG-LST-3 | Results are sorted by `submittedOn` **descending** (most recent first). |

### 6.7 Update Rules

| # | Rule |
|---|------|
| BR-REG-UPD-1 | Updates preserve the `registrationStatus`, `inttraCompanyId`, `submittedOn`, `approvedOn`, `assignedToUserId`. |
| BR-REG-UPD-2 | If `triggerofac=true`, the OFAC check is re-triggered after the update. |
| BR-REG-UPD-3 | All updates require a non-empty `logMessage` (appended to `activityMessageLogs`). |

---

## 7. Email Templates

| Code | Template | When Sent |
|------|----------|-----------|
| `WLC` | `WelcomeEmail` | Immediately after submission (async) |
| `ONH` | `OnHoldEmail` | When placed on hold |
| `DNR` | `DeclinedNoReponseEmail` | Declined — no response from registrant |
| `DDA` | `DeclinedDuplicateAccountEmail` | Declined — duplicate account found |
| `DUA` | `DeclinedUserAddedToExistingAccountEmail` | Declined — user added to existing account |
| `APR` | `ApprovedEmail` | On successful approval (COMPLETED) |

**Common email variables:** `companyName`, `userFullName`, `streetAddress`, `cityName`, `countryName`, `phoneNumber`, `inttraCompanyId`, `shipmentPortalURL`, `myAdminPortalURL`, `carrierConnectionsV2Enabled`

---

## 8. External Integrations

| Service | Name | Purpose |
|---------|------|---------|
| `CompanyService` | `company` | Generate INTTRA company ID + create company record |
| `CompanyComplianceService` | `np-compliance-screening` | OFAC/RPS compliance check |
| `BlackListService` | `blacklist` | Check if `businessEmail` is blacklisted |
| `UserService` | `user` | Create user account after approval |
| `DomainWhitelistService` | `domain-whitelist` | Whitelist email domain after company creation |
| `NetworkParticipantService` | `network-participants` | Validate SCAC code uniqueness |
| `UIConfigurationService` | `ui-configuration` | Feature flags: `carrierConnectionsV2Enabled`, `e2ProxyEnabled` |
| `EmailService` (commons) | SES | Send template emails |

---

## 9. Default User Configuration

Default roles assigned when creating a new user on approval:

**Mercury Roles:**
- `NETWORK_USER`
- `COMPANY_USER_ADMIN`
- `OCEANSCHEDULE_USER`
- `BOOKING_ADMIN`
- `BOOKING_RAC`

**Legacy Roles:**

| Code | Name |
|------|------|
| 3003 | Customer Security Administrator |
| 3009 | Booking User |
| 3021 | Customer Web BL Approval User |
| 3023 | Customer Web BL Edit User |
| 3022 | Customer Web BL Share User |
| 3024 | Customer Web BL View User |
| 3020 | Reports User |
| 800020 | Shipping Instructions User |
| 3004 | Track and Trace User |

**Language Code Mapping:**

| Input | Mapped Value |
|-------|-------------|
| `en` | `en` |
| `es` | `es` |
| `pt` | `pt` |
| `tr` | `tr_TR` |
| `fr` | `fr_FR` |
| `zh-cn` | `zh_CN` |
| `zh-hk` | `zh_TW` |
| `jp` | `ja_JP` |

---

## 10. Validation Reference

### Field-Level Constraints (on `RegistrationDetail`)

| Field | Constraint |
|-------|-----------|
| `companyName` | `@NotBlank` |
| `companyRole` | `@NotNull` |
| `scacCode` | Alphanumeric, max 35 chars, unique (custom logic) |
| `streetAddress` | `@NotBlank`, `@Size(max=40)` |
| `streetAddress2` | `@Size(max=40)` |
| `countryCode` | `@NotBlank` |
| `countryName` | `@NotBlank` |
| `cityName` | `@NotBlank` |
| `firstName` | `@NotBlank` |
| `lastName` | `@NotBlank` |
| `businessEmail` | `@NotBlank` |
| `phoneNumber` | `@NotBlank` |
| `preferredLanguage` | `@NotBlank` |
| `jobLevel` | `@NotBlank` |
| `jobFunction` | `@NotBlank` |

### DynamoDB Query Pattern (by Status)

```
Table: RegistrationDetail
GSI: REGISTRATION_STATUS_SUBMITTED_ON_INDEX
KeyCondition: registrationStatus = {status}
FilterExpression: submittedOn >= {now - 60 days}
ScanLimit: 1000
```

---

## 11. Exception Reference

| Exception | HTTP | Trigger |
|-----------|------|---------|
| `VersionMismatchException` | 409 | DynamoDB optimistic lock failure |
| `AssigneeMismatchException` | 403 | Attempting operation on unassigned registration |
| `SendEmailException` | 500 | Email send failure |
| `BadRequestException` | 400 | SCAC validation, blacklisted email, invalid status for operation |
| `IllegalStateException` | 500 | InttraCompanyId already assigned, OFAC not passed before approve |
| `NotFoundException` | 404 | Registration not found |

---

*End of document — Registration Service Business Rules & Technical Reference*
