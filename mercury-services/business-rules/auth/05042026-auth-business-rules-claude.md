# Auth Service — Business Rules & Technical Reference

> **Generated:** 2026-05-04  
> **Module:** `auth/`  
> **Author:** Claude (automated analysis)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture](#3-architecture)
4. [Data Models](#4-data-models)
5. [API Endpoints](#5-api-endpoints)
6. [Business Rules](#6-business-rules)
7. [Authentication Flows](#7-authentication-flows)
8. [Authorization Model](#8-authorization-model)
9. [Token Lifecycle](#9-token-lifecycle)
10. [External Integrations](#10-external-integrations)
11. [Persistence](#11-persistence)
12. [Security Controls](#12-security-controls)

---

## 1. Overview

The **Auth Service** is the central identity and access management (IAM) service for the Mercury platform. It handles:

- User login (password, SSO/SAML, OAuth2/OIDC)
- API client credential management
- Token issuance, validation, and invalidation
- Context switching (admin sudo, read-only, user impersonation)
- One-time tokens (OTT) for password resets and partner SSO
- Legal agreement management
- SSO URL mapping

**Root Path:** `/auth`  
**Port:** 8080 (API), 8081 (Admin)

---

## 2. Technology Stack

| Component | Technology |
|-----------|------------|
| Web Framework | DropWizard (JAX-RS / Jakarta EE) |
| DI Framework | Google Guice |
| Security | Spring Security OAuth2, OpenSAML 2.6.6 |
| JWT | auth0 4.3.0 + Bouncy Castle |
| ORM | MyBatis |
| Templating | Freemarker |
| JSON | Jackson |
| Build | Maven (Java 17) |

**Databases:**

| Database | Purpose |
|----------|---------|
| DynamoDB | Token storage, SAML message state |
| Aurora MySQL (Primary) | Clients, roles, entitlements, legal agreements, SSO URL mappings |
| Aurora MySQL (Read-Only) | Read-heavy GET queries |
| Oracle (Legacy PTUI) | Legacy user lookups |

---

## 3. Architecture

```
HTTP Request
    │
    ▼
Auth Resource (JAX-RS)
    │
    ├─── TokenService        → DynamoDB (Token table)
    ├─── ClientService       → Aurora MySQL (clients, client_roles)
    ├─── EntitlementsService → Aurora MySQL (entitlements)
    ├─── RolesService        → Aurora MySQL (roles)
    ├─── UserService (ext)   → Network Services (cloud users)
    ├─── PTUIUserService     → Oracle (legacy users)
    └─── SamlService         → DynamoDB (SAML state) + IDP/SP
```

---

## 4. Data Models

### 4.1 Token

Stored in **DynamoDB** (`token` table).

| Field | Type | Description |
|-------|------|-------------|
| `accessToken` | String (PK) | UUID v4 token string |
| `userId` / `clientId` | Integer / String | Owner (one of the two) |
| `grantType` | String | `password`, `client_credentials`, `authorization_code` |
| `tokenType` | String | Always `"Bearer"` |
| `tokenExpiryType` | String | `InactivityTimeout`, `FixedTimeout`, `OneTimeUse` |
| `tokenTtl` | Integer (seconds) | Time-to-live |
| `scope` | String | Space-separated roles + entitlements |
| `principalDetails` | JSON String | Serialized User or Client |
| `contextSwitchType` | Enum | `AdminSudo`, `AdminReadOnly`, `AdminUserSwitch`, `UserCompanySwitch` |
| `switchCompanyId` | Integer | Target company for context switch |
| `switchLoginName` | String | Target user login for switch |
| `tokenGeneratedUtc` | Timestamp | Creation time |
| `tokenLastAccessUtc` | Timestamp | Last access (for inactivity check) |
| `expirationDate` | Timestamp | Hard expiry date |

**DynamoDB GSI:** `token_principal_id_index` on `principalId` (KEYS_ONLY) — used to find all tokens for a user (OTT invalidation).  
**DynamoDB TTL:** `ttl` = expiration + 72,000 seconds (~20 days).

### 4.2 Client

Stored in **Aurora MySQL**.

| Field | Description |
|-------|-------------|
| `clientId` | Auto-generated: `{companyId}-{randomInt}` |
| `clientSecret` | bcrypt-hashed |
| `clientName` | Display name |
| `clientType` | `API_Client` or `SUDO_CLIENT` |
| `status` | `ACTIVE` or `INACTIVE` |
| `companyId` | Owning company |
| `networkParticipantId` | Linked NP (for entitlements) |
| `tokenExpiryType` | `FixedTimeout` (for API clients) |
| `tokenTtl` | TTL in seconds |
| `roles` | Set of role strings |
| `entitlements` | Set of entitlement strings |
| `emailAddress` | Contact email |

### 4.3 Entitlement

| Field | Description |
|-------|-------------|
| `networkParticipantId` | Company NP ID |
| `module` | Module name (e.g., `Auth`, `Booking`, `Vas`) |
| `rootPath` | URL root path (e.g., `auth`, `booking`) |
| `effectiveStartDateUtc` | Start of validity |
| `effectiveEndDateUtc` | End of validity |

**Default entitlements always added:** `Vas`, `Rates`, `ContainerEvent`.

### 4.4 ContextSwitchRequest

```json
{
  "switchCompanyId": 1234,
  "switchLoginName": "user@company.com",
  "contextSwitchType": "AdminSudo",
  "switchUserId": 789
}
```

### 4.5 LegalAgreement

| Field | Type |
|-------|------|
| `id` | Integer |
| `content` | String (HTML/text) |
| `version` | String |
| `effectiveDate` | Date |

---

## 5. API Endpoints

### 5.1 Auth — `/auth`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/login` | — | Initiate login; domain sync and cookie setup |
| `GET` | `/` | — | Authenticate with client credentials (header params) |
| `POST` | `/` | — | Authenticate with username/password or auth code (body) |
| `GET` | `/principal` | — | Get principal for a token (supports sudo context) |
| `GET` | `/validate` | — | Validate token and check root-path entitlement |
| `GET` | `/validate-user` | — | Validate one-time token; invalidates it on use |
| `GET` | `/invalidate` | — | Invalidate token (optional SAML logout + redirect) |
| `POST` | `/context` | — | Switch context (admin sudo, read-only, user switch) |
| `POST` | `/reset` | — | Restore original context (undo switch) |
| `GET` | `/sso` | — | Generate partner SSO one-time token |
| `GET` | `/ott/{userId}` | `NETWORK_ADMIN`, `REGISTRATION_ADMIN` | Generate one-time token for a user |

#### `GET /login` Parameters

| Parameter | Type | Location | Description |
|-----------|------|----------|-------------|
| `authorization` | String | Header | Existing token (optional) |
| `syncdomain` | Boolean | Query | Trigger domain sync redirect |
| `redirectUrl` | String | Query | Post-login redirect URL |

#### `POST /` Request Body (AuthRequest)

```json
{
  "username": "user@company.com",
  "password": "secret",
  "code": "auth-code",
  "callbackUrl": "https://...",
  "client_id": "1000-12345",
  "client_secret": "abc123",
  "scope": "roles entitlements",
  "grant_type": "password"
}
```

**Supported grant types:** `password`, `authorization_code`, `client_credentials`

#### `GET /principal` Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `Authorization` | Header | Bearer token |
| `sudoCompanyId` | Query | Company ID for admin sudo |
| `sudoModule` | Query | Module entitlement for SUDO_CLIENT |
| `rootPath` | Query | Entitlement root path to check |
| `iv-user` | Query | e2Proxy login name |
| `e2ProxyLoginName` | Query | e2Proxy override login |

#### Token Response Fields

```json
{
  "accessToken": "uuid",
  "tokenType": "Bearer",
  "tokenExpiryType": "InactivityTimeout",
  "tokenTtl": 1800,
  "grantType": "password",
  "userId": 123,
  "clientId": null,
  "scope": "NETWORK_USER NETWORK_ADMIN booking",
  "principalDetails": "{...}",
  "contextSwitchType": null
}
```

---

### 5.2 Connect — `/connect`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/validate` | Validate CSRF token and callback URL for OAuth connect |
| `GET` | `/` | Generate OTT (12h) and CSRF state for connect flow |

#### `GET /` Response (ConnectResponse)

```json
{
  "client_name": "My App",
  "client_id": "1000-12345",
  "callbackUrl": "https://app.com/callback",
  "code": "one-time-token"
}
```

---

### 5.3 External Auth — `/` (e2Proxy)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/authorize` | e2Proxy authentication via `iv-user` header |
| `GET` | `/e2proxyflag` | Check if e2Proxy is enabled |

---

### 5.4 Clients — `/clients`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/register` | `NETWORK_ADMIN` | Register new API client |
| `GET` | `/{clientId}` | `NETWORK_ADMIN` | Get client details |
| `GET` | `/` | `NETWORK_ADMIN` | Get clients by company ID |
| `PUT` | `/{clientId}` | `NETWORK_ADMIN` | Update client (name, roles) |
| `PUT` | `/{clientId}/activate` | `NETWORK_ADMIN` | Activate client |
| `PUT` | `/{clientId}/deactivate` | `NETWORK_ADMIN` | Deactivate client |
| `DELETE` | `/{clientId}` | `NETWORK_ADMIN` | Delete client and all roles |
| `POST` | `/{clientId}/resetpassword` | `NETWORK_ADMIN` | Generate new client secret |
| `GET` | `/{clientId}/roles` | `NETWORK_ADMIN` | Get client roles |
| `POST` | `/{clientId}/roles` | `NETWORK_ADMIN` | Add roles to client |
| `DELETE` | `/{clientId}/roles` | `NETWORK_ADMIN` | Remove all client roles |

**`GET /` Query Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `inttraCompanyId` | Integer | Filter by company |
| `includeInactive` | Boolean | Include inactive clients |

---

### 5.5 SSO — `/sso`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `GET` | `/mappedurl` | — | Decode and return mapped SSO URL |
| `GET` | `/usersession` | — | Get/set SSO user session |
| `GET` | `/urlmapping` | `NETWORK_ADMIN` | Get URL mappings (by ID or component) |
| `POST` | `/urlmapping` | `NETWORK_ADMIN` | Create or update URL mapping |
| `DELETE` | `/urlmapping/{id}` | `NETWORK_ADMIN` | Delete URL mapping |
| `GET` | `/authproviders` | — | List available SSO providers |

---

### 5.6 OAuth Metadata — `/sso/oauth2` and `/oauth/metadata`

| Method | Path | Roles | Description |
|--------|------|-------|-------------|
| `POST` | `/static/{metadataType}` | `SSO_ADMIN` | Create/update static OIDC metadata |
| `POST` | `/dynamic` | `SSO_ADMIN` | Discover metadata from issuer URL |
| `GET` | `/{metadataType}/{id}` | `SSO_ADMIN` | Get metadata by type and ID |
| `POST` | `/referrer/{override}` | `SSO_ADMIN` | Add referrer host whitelist |
| `POST` | `/enable/{metadataType}/{id}` | `SSO_ADMIN` | Enable metadata |
| `POST` | `/disable/{metadataType}/{id}` | `SSO_ADMIN` | Disable metadata |
| `GET` | `/all` | `SSO_ADMIN` | List all metadata |
| `POST` | `/clientinfo/{metadataType}/{id}` | `SSO_ADMIN` | Add OIDC client credentials |
| `GET` | `/clientinfo/{metadataType}/{id}` | `SSO_ADMIN` | Get OIDC client credentials |
| `GET` | `/isOAuthhost` | — | Check if host is SAML/OAuth host |
| `DELETE` | `/{metadataType}/{id}` | `SSO_ADMIN` | Delete metadata |

---

### 5.7 Legal Agreement — `/legalagreement`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/latest` | Get the most recent legal agreement |
| `GET` | `/{id}` | Get legal agreement by ID |
| `GET` | `/` | Get all legal agreements |
| `POST` | `/` | Create legal agreement |
| `DELETE` | `/{id}` | Delete legal agreement |

---

## 6. Business Rules

### 6.1 Client Registration

| # | Rule |
|---|------|
| BR-CLI-1 | Non-INTTRA companies (company ID ≠ 1000) are limited to **1 active client** at a time. |
| BR-CLI-2 | INTTRA company (ID = 1000) may have **multiple active clients**. |
| BR-CLI-3 | `emailAddress` is required and must be a valid email format. |
| BR-CLI-4 | `roles` must be non-empty; a client without roles cannot be registered. |
| BR-CLI-5 | `clientId` is auto-generated as `{companyId}-{randomInt}`. |
| BR-CLI-6 | A setup email is sent on registration; a new secret email is sent on password reset. |
| BR-CLI-7 | Client secrets are stored **bcrypt-hashed**. Validation supports both plaintext (legacy) and bcrypt. |

### 6.2 Entitlement Checks

| # | Rule |
|---|------|
| BR-ENT-1 | The `/auth` root path is **always allowed** — no entitlement check performed. |
| BR-ENT-2 | All other root paths are checked against the principal's entitlements; `403 Forbidden` if absent. |
| BR-ENT-3 | **Legacy users** are limited to: `auth`, `network`, `oceanschedules`, `booking`. |
| BR-ENT-4 | **Session key grant** users are limited to: `auth`, `network`, `oceanschedules`. |
| BR-ENT-5 | Default entitlements (`Vas`, `Rates`, `ContainerEvent`) are always appended to any principal. |

### 6.3 Context Switching

| # | Rule |
|---|------|
| BR-CTX-1 | `SUDO_ADMIN` role is required to initiate any context switch. |
| BR-CTX-2 | **AdminSudo**: Admin gets ALL roles for the target company's entitlements. |
| BR-CTX-3 | **AdminReadOnly**: Admin gets only read-only roles for the target company's entitlements. |
| BR-CTX-4 | **AdminUserSwitch**: Admin fully impersonates the target user (inherits their scope). |
| BR-CTX-5 | **UserCompanySwitch**: Regular user switches between their own linked companies. |
| BR-CTX-6 | Context switch metadata is stored in the token (`switchCompanyId`, `switchLoginName`, `contextSwitchType`). |
| BR-CTX-7 | `POST /reset` clears all switch fields and restores original scope. |

### 6.4 One-Time Tokens (OTT)

| # | Rule |
|---|------|
| BR-OTT-1 | OTTs are `OneTimeUse` expiry type — they are **invalidated immediately after first use** (on `/validate-user`). |
| BR-OTT-2 | OTT TTL for OAuth connect flow: **43,200 seconds (12 hours)**. |
| BR-OTT-3 | When a new OTT is requested for a user, all existing active OTTs for that user are invalidated first. |
| BR-OTT-4 | `/ott/{userId}` requires `NETWORK_ADMIN` or `REGISTRATION_ADMIN` role. |

### 6.5 Domain Sync

| # | Rule |
|---|------|
| BR-DOM-1 | On `GET /login` with `syncdomain=true`, a cookie is set on the secondary domain and the user is redirected there first. |
| BR-DOM-2 | After domain sync redirect, the user is redirected to the original target app or the `redirectUrl`. |

### 6.6 e2Proxy

| # | Rule |
|---|------|
| BR-E2P-1 | The `iv-user` header value must match the token principal's login name. |
| BR-E2P-2 | Validation is skipped for `.inttra.com` domain requests. |
| BR-E2P-3 | The e2Proxy feature is enabled/disabled via `UIConfigurationService` flag. |
| BR-E2P-4 | On mismatch, `401 Unauthorized` is returned. |

---

## 7. Authentication Flows

### 7.1 Password Grant

```
POST /auth/
  username + password + grant_type=password
        │
        ├─ Check PTUI (legacy Oracle): validateLegacyUser()
        │     └─ If found: get legacy roles, map to cloud roles
        │
        └─ Check UserService (cloud): validateUser()
              └─ If found: get cloud roles + entitlements
        │
        ├─ Build scope = roles + entitlements (+ GLV_ENABLED if applicable)
        ├─ Set tokenExpiryType = InactivityTimeout, tokenTtl = 1800s
        └─ Save token to DynamoDB, return token
```

### 7.2 Client Credentials Grant

```
GET /auth/
  client_id + client_secret + grant_type=client_credentials (headers)
        │
        ├─ Load client from Aurora MySQL
        ├─ Validate secret (plaintext OR bcrypt)
        ├─ Build scope from client roles + entitlements
        ├─ Set tokenExpiryType = FixedTimeout (from client config)
        └─ Save token to DynamoDB, return token
```

### 7.3 Authorization Code Grant

```
POST /auth/
  code + client_id + client_secret + grant_type=authorization_code
        │
        ├─ Validate client credentials
        ├─ Load token matching the code (must be OneTimeUse)
        ├─ Invalidate the code token
        └─ Generate new user token, return token
```

### 7.4 Token Validation Flow

```
GET /auth/validate
  Authorization: Bearer <token>
        │
        ├─ Strip "Bearer " prefix
        ├─ Load token from DynamoDB
        ├─ Check expiry:
        │     InactivityTimeout: now - lastAccess > tokenTtl → 401
        │     FixedTimeout: now > expirationDate → 401
        │     OneTimeUse: already used → 401
        ├─ Update tokenLastAccessUtc
        └─ If rootPath provided: check entitlement → 403 if absent
```

---

## 8. Authorization Model

### Role Taxonomy

| Role | Usage |
|------|-------|
| `NETWORK_ADMIN` | General network administration |
| `SUPER_ADMIN` | Platform-level administration |
| `SUDO_ADMIN` | Context switching (impersonation) |
| `REGISTRATION_ADMIN` | User/company registration |
| `SSO_ADMIN` | SSO metadata management |

### Scope Construction

Token `scope` is a space-separated string:
```
{role1} {role2} ... {entitlement1} {entitlement2} ...
```

If the company has GLV enabled:
```
... GLV_ENABLED
```

For SUDO_CLIENT (API client in sudo mode):
```
{roles for sudoModule}
```

---

## 9. Token Lifecycle

```
                Generation
                    │
        ┌───────────┴──────────────┐
        │                         │
   User Token              Client Token
   (InactivityTimeout)     (FixedTimeout)
   TTL = 1800s             TTL = client config
        │                         │
        ▼                         ▼
   Update lastAccess         Fixed expiry date
   on each /validate
        │
        ▼
   Invalidation:
     SET tokenTtl = 0
     Optional SAML logout
        │
        ▼
   DynamoDB TTL cleanup:
     expiresOn + 72000s
     (~20 day grace period)
```

---

## 10. External Integrations

| System | Protocol | Purpose |
|--------|----------|---------|
| Legacy PTUI | Oracle JDBC | Validate legacy username/password; get legacy user details |
| Cloud UserService | REST (internal) | Validate cloud users; get roles, entitlements, company |
| Restricted Party Screening (Accuity) | SOAP | OFAC compliance check during login |
| SAML IDP/SP | OpenSAML | SSO login and logout |
| OAuth2/OIDC Provider | HTTP OIDC discovery | External identity provider integration |
| Email Service | SES (via Freemarker) | Client registration email, password reset email |
| UIConfigurationService | REST (internal) | e2Proxy flag, domain sync flag, portal URLs |

---

## 11. Persistence

### DynamoDB Tables

| Table | Key | Purpose |
|-------|-----|---------|
| `token` | `hashKey` (= accessToken) | Token storage; GSI on `principalId` |
| `samlmessagedetail` | `hashKey` + `entityId` (sort) | SAML request/response state; TTL enabled |

### Aurora MySQL Tables

| Table | Purpose |
|-------|---------|
| `clients` | API client records |
| `client_roles` | Client–role mappings |
| `roles` | Role definitions per module |
| `entitlements` | Module entitlement assignments |
| `legal_agreements` | Legal agreement content versions |
| `url_details` | SSO URL component mappings |

---

## 12. Security Controls

| Control | Description |
|---------|-------------|
| Token format | UUID v4, unpredictable |
| Secret hashing | bcrypt for client secrets |
| Inactivity timeout | Tokens expire after 30 min of inactivity (user tokens) |
| OTT single-use | One-time tokens invalidated on first use |
| SAML state | SAML message state stored in DynamoDB with TTL |
| Domain validation | CSRF validation on OAuth connect flow |
| Entitlement gating | Root-path entitlement checked on every `/validate` |
| Legacy user restriction | Legacy users locked to a subset of modules |
| Admin-only impersonation | Context switch requires `SUDO_ADMIN` role |
| e2Proxy header validation | `iv-user` must match token principal |

---

*End of document — Auth Service Business Rules & Technical Reference*
