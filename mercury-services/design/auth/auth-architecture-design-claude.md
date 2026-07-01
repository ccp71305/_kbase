# Auth Service — Architecture and Design Document

**Service:** `auth`
**Module Artifact:** `com.inttra.mercury:auth:1.0`
**Main Class:** `com.inttra.mercury.AuthService`
**Root Path:** `/auth`
**Generated:** 2026-05-04

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [Multi-Level Architecture Diagram](#3-multi-level-architecture-diagram)
4. [Key Classes Reference Table](#4-key-classes-reference-table)
5. [Token Lifecycle Data Flow](#5-token-lifecycle-data-flow)
6. [Auth Grant Type Flows](#6-auth-grant-type-flows)
7. [DynamoDB Table Schemas](#7-dynamodb-table-schemas)
8. [Aurora MySQL Schema Overview](#8-aurora-mysql-schema-overview)
9. [Oracle Database Schema Overview](#9-oracle-database-schema-overview)
10. [Guice DI Module Wiring](#10-guice-di-module-wiring)
11. [REST API Summary Table](#11-rest-api-summary-table)
12. [Security Design](#12-security-design)
13. [SSO and SAML Integration Flow](#13-sso-and-saml-integration-flow)
14. [Design Patterns Used](#14-design-patterns-used)
15. [Configuration Properties Reference](#15-configuration-properties-reference)
16. [Inter-Service Dependencies](#16-inter-service-dependencies)

---

## 1. Executive Summary

The **Auth Service** is the central authentication and authorization gateway of the Mercury Services platform — a multi-tenant cloud-native microservices platform built on Dropwizard and hosted on AWS. Every other Mercury microservice (network, booking, ocean schedules, shipment, visibility, etc.) delegates token validation and principal resolution to this service.

### Core Responsibilities

| Responsibility | Description |
|---|---|
| Token Issuance | Issues opaque bearer tokens (UUID-based) for users and API clients |
| Token Validation | Validates tokens, enforces inactivity/fixed/one-time-use TTL rules |
| Principal Resolution | Returns enriched `InttraPrincipal` (user or client) from token for downstream auth filters |
| Multi-Grant OAuth2 | Supports `password`, `client_credentials`, `authorization_code`, and `session_key` grant types |
| SAML 2.0 IDP | Acts as a SAML Identity Provider for external SP integrations (PayCargo, CargoSphere, e2open, etc.) |
| SAML 2.0 SP | Acts as a SAML Service Provider to accept assertions from upstream enterprise IDPs |
| OAuth2/OIDC Relying Party | Delegates SSO login to external OIDC providers (e.g., corporate Identity Providers) |
| User Management | Full lifecycle: create, search, merge, migrate, activate, deactivate, OFAC-check users |
| Client Management | Register/rotate API clients with scoped roles and entitlements |
| Context Switching | Allows SUDO_ADMIN users to impersonate companies or users without re-authentication |
| e2open Proxy (E2Proxy) | Accepts `iv-user` header from e2open's reverse proxy to auto-provision tokens |
| Legal Agreement | Tracks and enforces acceptance of platform-wide legal agreements per user |
| Menu / I18n | Delivers country-specific navigation menus and language preference cookies |

The service is a **fat JAR** assembled by Maven Shade Plugin, launched by Dropwizard's `server` command, and runs on Java 17 in AWS ECS (Fargate). It connects to three distinct persistence backends: Amazon DynamoDB (token + SSO state), Amazon Aurora MySQL (primary read-write workloads), and a legacy Oracle database (legacy INTTRA user directory — PTUI).

---

## 2. Technology Stack

### Runtime and Framework

| Component | Artifact | Version | Notes |
|---|---|---|---|
| Java Runtime | OpenJDK | 17 | `maven.compiler.release=17` |
| Application Framework | `io.dropwizard:dropwizard-core` | `2.1.1` | Inherited from parent BOM |
| DI Container | `com.google.inject:guice` | `4.1.0` | Inherited from parent BOM |
| ORM / SQL Mapping | MyBatis (via `mybatis-guice`) | inherited | MyBatis + Guice integration |
| JSON Serialization | `com.fasterxml.jackson.databind` | `2.13.4.2` | Parent BOM |
| Annotation Processing | `org.projectlombok:lombok` | `1.18.30` | Compile-time code generation |
| Metrics | Dropwizard Metrics / Codahale | `2.1.1` | `@Timed` per endpoint |

### Storage and Data Access

| Component | Artifact | Version | Notes |
|---|---|---|---|
| DynamoDB Client (v2) | AWS SDK Enhanced DynamoDB | via `cloud-sdk-aws` | Token, SAML/OAuth metadata, SSO state |
| DynamoDB Local (test) | `com.amazonaws:aws-java-sdk-dynamodb` | `1.12.721` | Integration test only |
| Aurora MySQL Driver | `software.aws.rds:aws-mysql-jdbc` | `1.1.0` | IAM-aware JDBC driver |
| Oracle JDBC | `com.oracle.database.jdbc:ojdbc10` | `19.14.0.0` | Legacy INTTRA Oracle DB |
| Internal DynamoDB SDK | `com.inttra.mercury:cloud-sdk-aws` | `1.0.23-SNAPSHOT` | Wrapper abstraction |
| Internal DynamoDB API | `com.inttra.mercury:cloud-sdk-api` | `1.0.23-SNAPSHOT` | Repository/QuerySpec API |

### Security and SSO

| Component | Artifact | Version | Notes |
|---|---|---|---|
| OpenSAML | `org.opensaml:opensaml` | `2.6.6` | SAML 2.0 protocol processing |
| Spring Security SAML | `org.springframework.security.extensions:spring-security-saml2-core` | `1.0.9.RELEASE` | `MetadataManager`, `KeyManager` |
| XML Signature | `org.apache.santuario:xmlsec` | `3.0.1` | Overrides OpenSAML's bundled version |
| XML Stream | `com.fasterxml.woodstox:woodstox-core` | `6.4.0` | High-performance XML for SAML |
| OAuth2 Client | `org.springframework.security:spring-security-oauth2-client` | `5.8.7` | OIDC Relying Party flows |
| OIDC SDK | `com.nimbusds:oauth2-oidc-sdk` | `11.23` | Override from Spring exclusion |
| BouncyCastle | `org.bouncycastle:bcpkix-jdk15on` | `1.62` | Key/cert operations (test scope) |

### Utilities and Integrations

| Component | Artifact | Version | Notes |
|---|---|---|---|
| Apache Axis | `org.apache.axis:axis` | `1.4` | Accuity OFAC SOAP web service client |
| FreeMarker | `org.freemarker:freemarker` | `2.3.26-incubating` | Email template engine |
| Commons Text | `org.apache.commons:commons-text` | `1.12.0` | String manipulation |
| Commons Collections | `commons-collections:commons-collections` | `3.2.2` | OpenSAML dependency, safe override |
| JAX-RPC API | `javax.xml:jaxrpc-api` | `1.1` | Accuity SOAP binding |
| WSDL4J | `wsdl4j:wsdl4j` | `1.6.2` | Accuity WSDL parsing |
| Commons Discovery | `commons-discovery:commons-discovery` | `0.4` | Axis service discovery |
| Internal Commons | `com.inttra.mercury:commons` | `1.0.23-SNAPSHOT` | Shared Mercury utilities |

### Testing

| Component | Artifact | Version | Notes |
|---|---|---|---|
| JUnit 5 | `org.junit.jupiter:junit-jupiter` | `5.12.2` (BOM) | Primary test framework |
| JUnit 4 Vintage | `org.junit.vintage:junit-vintage-engine` | `5.12.2` | Legacy test compatibility |
| Mockito | `org.mockito:mockito-core` | `5.10.0` | Mocking |
| AssertJ | `org.assertj:assertj-core` | `3.27.2` | Fluent assertions |

### Build and CI

| Component | Version | Role |
|---|---|---|
| maven-shade-plugin | `3.5.3` | Fat JAR assembly |
| maven-compiler-plugin | `3.12.1` | Java 17 compilation |
| maven-surefire-plugin | `3.2.5` | Unit test runner |
| maven-failsafe-plugin | `3.2.5` | Integration test runner (`*DaoIT.java`) |
| maven-dependency-plugin | `3.7.1` | Copies native libs (SQLite4Java) |
| git-commit-id-plugin | `2.2.3` | Embeds git metadata |

---

## 3. Multi-Level Architecture Diagram

```
+================================================================================================+
|                                   EXTERNAL CLIENTS                                             |
|  Browser (SPA)   API Consumers   External IDPs   Partner Systems (Odex, Shop)   e2open Proxy  |
+================================================================================================+
         |                |                 |                   |                     |
         |  HTTP/HTTPS    |  Bearer Token   |  SAML/OIDC        |  authcode redirect  |  iv-user hdr
         v                v                 v                   v                     v
+================================================================================================+
|                               API GATEWAY / LOAD BALANCER                                      |
|                       AWS ALB  (ECS Fargate — auth-service tasks)                              |
+================================================================================================+
         |
         v  rootPath: /auth  port: 8080
+================================================================================================+
|                               DROPWIZARD SERVER (Jersey 3.x / Jetty)                          |
|   XSSFilter (Query Params)           XSSInterceptor (Request Body)                             |
|   AuthenticationFilter (token->principal per other services)                                   |
+================================================================================================+
         |
         |
+--------+------------------------------------------------------------------------+
|                         API LAYER (JAX-RS Resources)                            |
|                                                                                 |
|  AuthResource          AuthConnectResource     ExternalAuthResource             |
|  /                     /connect                /authorize  /e2proxyflag         |
|                                                                                 |
|  UserResource          UserPasswordResource     UserRolesResource               |
|  /users                /users/password          /users/{id}/roles               |
|                                                                                 |
|  UserLegalAgreementResource  UserOfacResource   UserProfilePreferenceResource   |
|  /users/{id}/legalagreement  /users/{id}/ofac   /users/{id}/preferences        |
|                                                                                 |
|  ClientResource        LegalAgreementResource  MenuResource                    |
|  /clients              /legalagreement          /menus                          |
|                                                                                 |
|  IdpServiceResource    SpServiceResource        MetadataResource                |
|  /saml/idp             /saml/sp                 /saml/metadata                 |
|                                                                                 |
|  SSOResource           OAuthMetadataResource   OAuthResource                   |
|  /sso                  /oauth/metadata          /sso/oauth2                    |
+--------+----+----+----+----+----+----+----+----+----+----+----+----+------+----+
         |    |    |    |    |    |    |    |    |    |    |    |    |      |
         v    v    v    v    v    v    v    v    v    v    v    v    v      v
+================================================================================================+
|                         SERVICE LAYER (Business Logic)                                         |
|                                                                                                |
|  TokenService          ClientService           UserService          PTUIUserService             |
|  - generateToken()     - validateCredentials() - getUserById()      - validateLogin()           |
|  - validateToken()     - getClient()           - validateUserLogin() - getLegacyUser()          |
|  - invalidateToken()   - updateClient()        - getScope()         - getLegacyUserId()         |
|  - setContextSwitch()  - resetPassword()       - getRolesForMigratedUser()                     |
|  - restoreContext()    - getInttraPrincipal()  - isGLVEnabled()                                |
|                                                                                                |
|  EntitlementsService   RolesDao (svc proxy)    IdpService           SpService                  |
|  - getEntitlements()   - getRolesForModule()   - doSSO()            - sendAuthNRequest()        |
|  - checkEntitlements() - getReadOnlyRoles()    - validateToken()    - processAssertion()        |
|                                                                                                |
|  OAuthMetadataService  RelyingPartyService     SSOService           UIConfigurationService      |
|  - createOrUpdate()    - processAuthzResp()    - getMappedUrl()     - getE2ProxyEnabled()       |
|  - getByProvider()     - buildAuthnUrl()       - addUrlMapping()    - getDomainSwitchFlag()     |
|                                                                                                |
|  UserProfilePreferencesService  LegalAgreementDao  I18nService  CountryConfigurationService    |
|  RestrictedPartyScreeningService  PasswordValidationService  EmailSender  TemplateEngine        |
+================================================================================================+
         |                    |                       |                       |
         v                    v                       v                       v
+================+   +===================+   +==================+   +==================+
| DAO/REPOSITORY |   |  MYBATIS MAPPERS  |   |  DYNAMO REPOS    |   |  EXTERNAL HTTP   |
| LAYER          |   |  (Aurora MySQL)   |   |  (cloud-sdk)     |   |  CLIENTS         |
|                |   |                   |   |                  |   |                  |
| TokenDao       |   | UserMapper(RW)    |   | DatabaseRepo     |   | PTUI Portal      |
| SamlMetadata   |   | UserMapperRO(RO)  |   | <TokenWrapper>   |   | (legacy auth)    |
| Dao            |   | ClientMapper(RW)  |   |                  |   |                  |
| SamlMessage    |   | ClientMapperRO    |   | DatabaseRepo     |   | Accuity OFAC     |
| DetailDao      |   | EntitlementsMapper|   | <SAMLMetadata>   |   | (SOAP/Axis)      |
| SSOMessageDet  |   | RolesMapper(RO)   |   |                  |   |                  |
| ailDao         |   | LegalAgreement    |   | DatabaseRepo     |   | RPS (Amber Road) |
| OAuthMetadata  |   | Mapper(RW)        |   | <OAuthMetadata>  |   | Restricted Party |
| Dao            |   | PTUIUserMapper    |   |                  |   | Screening        |
| ClientDao      |   | (RW + RO)         |   | DatabaseRepo     |   |                  |
| EntitlementsDao|   | UserProfilePrefs  |   | <SSOMessageDet>  |   | Email (SES)      |
| LegalAgreement |   | Mapper(RW)        |   |                  |   | via EmailClient  |
| Dao            |   | InttraUserMapper  |   | DatabaseRepo     |   |                  |
| UserDao        |   | (Oracle — PTUI)   |   | <SamlMessage     |   | Xlog Service     |
|                |   | CountryConfig     |   |  Detail>         |   | (legacy audit)   |
|                |   | Mapper(RW)        |   |                  |   |                  |
|                |   | UIConfigReadMapper|   |                  |   |                  |
|                |   | UrlDetailMapper   |   |                  |   |                  |
+================+   +===================+   +==================+   +==================+
         |                    |                       |
         v                    v                       v
+================+   +===================+   +==================+
| STORAGE LAYER  |   |                   |   |                  |
|                |   | Aurora MySQL RW   |   | Amazon DynamoDB  |
| Oracle DB      |   | (primary writer)  |   |                  |
| (INTTRA legacy)|   |                   |   | token            |
| - PTUI users   |   | Aurora MySQL RO   |   | SAMLMetadata     |
| - legacy roles |   | (read replica)    |   | OAuthMetadata    |
| - company data |   |                   |   | sso_message_det  |
|                |   | Database: Network |   | samlmessagedetail|
+================+   +===================+   +==================+
```

---

## 4. Key Classes Reference Table

### Application Bootstrap

| Class | Package | Role |
|---|---|---|
| `AuthService` | `com.inttra.mercury` | Entry point; wires all Guice modules and registers all JAX-RS resources |
| `AuthServiceConfig` | `com.inttra.mercury` | Dropwizard Configuration POJO; holds all YAML-bound config |
| `AuthApplicationModule` | `com.inttra.mercury` | Root Guice module; binds `EnvironmentConfig`, `Encryptor`, registers `XSSFilter`/`XSSInterceptor` |

### JAX-RS Resources (API Layer)

| Class | Package | Base Path |
|---|---|---|
| `AuthResource` | `auth.resources` | `/` |
| `AuthConnectResource` | `auth.resources` | `/connect` |
| `ExternalAuthResource` | `auth.resources` | `/` (e2proxy endpoints) |
| `UserResource` | `users.resources` | `/users` |
| `UserPasswordResource` | `users.resources` | `/users/password` |
| `UserRolesResource` | `users.resources` | `/users/{userId}/roles` |
| `UserLegalAgreementResource` | `users.resources` | `/users/{userId}/legalagreement` |
| `UserOfacResource` | `users.resources` | `/users/{userId}/ofac` |
| `UserProfilePreferenceResource` | `users.resources` | `/users/{userId}/preferences` |
| `ClientResource` | `clients.resources` | `/clients` |
| `LegalAgreementResource` | `legalagreement.resources` | `/legalagreement` |
| `MenuResource` | `menus.resources` | `/menus` |
| `IdpServiceResource` | `sso.saml.resources` | `/saml/idp` |
| `SpServiceResource` | `sso.saml.resources` | `/saml/sp` |
| `MetadataResource` | `sso.saml.resources` | `/saml/metadata` |
| `SSOResource` | `sso.common.resources` | `/sso` |
| `OAuthMetadataResource` | `sso.oauth.resources` | `/oauth/metadata` |
| `OAuthResource` | `sso.oauth.resources` | `/sso/oauth2` |

### Service Layer

| Class | Package | Role |
|---|---|---|
| `TokenService` | `auth.providers.inttra` | All token operations: generate, validate, invalidate, context-switch |
| `ClientService` | `clients.providers.inttra` | Client credential validation, enrichment, CRUD |
| `UserService` | `users.providers.inttra` | User CRUD, role resolution, scope computation, OFAC check |
| `PTUIUserService` | `users.providers.ptui.services` | Legacy PTUI system authentication and user lookup |
| `PTUIUserMgmtService` | `users.providers.ptui.services` | Legacy role provisioning to PTUI portal |
| `EntitlementsService` | `entitlements.providers.inttra` | Entitlement lookup by company/NPI, entitlement enforcement |
| `IdpService` | `sso.saml.services.idp` | SAML IdP — issue assertions, SLO, validate authn request |
| `SpService` | `sso.saml.services.sp` | SAML SP — send AuthnRequest, consume assertions, SLO |
| `RelyingPartyService` | `sso.oauth.services.rp` | OAuth2/OIDC Relying Party: build auth URL, exchange code, validate ID token |
| `SSOService` | `sso.common.services` | URL mapping for SSO post-auth redirects |
| `OAuthMetadataService` | `sso.oauth.services` | OIDC provider metadata management |
| `UIConfigurationService` | `storedconfiguration.service` | Runtime feature flags (e2proxy, domain switch) |
| `UserProfilePreferencesService` | `users.service` | User profile preference retrieval |
| `I18nService` | `menus.service` | Language code normalization |
| `CountryConfigurationService` | `menus.service` | Country-specific menu configuration |
| `RestrictedPartyScreeningService` | `rps.service` | OFAC screening via RPS (Amber Road) |

### DAO / Repository Layer

| Class | Package | Backend | Key |
|---|---|---|---|
| `TokenDao` | `auth.persistence` | DynamoDB | Partition: `hashKey` (access token UUID) |
| `SamlMetadataDao` | `auth.persistence` | DynamoDB | Partition: `entityId` |
| `SamlMessageDetailDao` | `auth.persistence` | DynamoDB | Composite: `hashKey` + `entityId` |
| `SSOMessageDetailDao` | `sso.common.persistence` | DynamoDB | Composite: `messageId` + `messageType` |
| `OAuthMetadataDao` | `sso.oauth.persistence` | DynamoDB | Composite: `id` + `metadataType` |
| `ClientDao` | `clients.persistence` | Aurora MySQL | client_id |
| `UserDao` | `users.persistence` | Aurora MySQL | user_id |
| `PTUIUserDao` | `users.providers.ptui.persistence` | Aurora MySQL (transactional) | PTUI user table |
| `EntitlementsDao` | `entitlements.persistence` | Aurora MySQL | company_id |
| `RolesDao` | `auth.persistence` | Aurora MySQL | module name |
| `LegalAgreementDao` | `legalagreement.persistence` | Aurora MySQL | agreement_id |
| `UrlDetailDao` | `sso.common.persistence` | Aurora MySQL | url_key |
| `CountryConfigurationDao` | `menus.persistance` | Aurora MySQL | country_code |

### DynamoDB Entity / Model Classes

| Class | Package | Table | Key Type |
|---|---|---|---|
| `TokenWrapper` | `auth.model` | `token` | Partition only |
| `SAMLMetadata` | `sso.saml.model` | `SAMLMetadata` | Partition only |
| `OAuthMetadata` | `sso.oauth.model` | `OAuthMetadata` | Composite |
| `SSOMessageDetail` | `sso.common.model` | `sso_message_detail` | Composite |
| `SamlMessageDetail` | `auth.model` | `samlmessagedetail` | Composite |

### Configuration Classes

| Class | Package | Role |
|---|---|---|
| `AuthServiceConfig` | `com.inttra.mercury` | Root configuration POJO |
| `EnvironmentConfig` | `auth.config` | Portal URLs, SSO error URL, payment provider URLs |
| `SamlConfig` | `auth.config` | SAML keystore, IDP/SP config, assertion customizations |
| `IdpConfig` | `auth.config` | IDP entity ID, keys, certificate, clock skew |
| `SpConfig` | `auth.config` | SP entity ID, keys, certificate |
| `SamlComponentConfig` | `auth.config` | Shared IDP/SP fields |
| `AccuityConfig` | `auth.config` | Accuity OFAC SOAP endpoint |
| `XlogConfig` | `auth.config` | Legacy Xlog audit service |
| `PTUIConfig` | `auth.config` | Legacy PTUI portal endpoints |
| `ExternalMenuLinkConfig` | `auth.config` | External portal menu link mappings |
| `ConsumerServiceConfig` | `auth.config` | SSO consumer service name/URL/entityId |

### Guice Modules

| Class | Package | Responsibility |
|---|---|---|
| `AuthApplicationModule` | `com.inttra.mercury` | Binds `EnvironmentConfig`, `Encryptor`; registers XSS filters |
| `AuthDynamoModule` | `auth.config` | Provisions all DynamoDB `DatabaseRepository` instances |
| `AuthEmailSenderModule` | `auth.config` | Binds email sender implementation |
| `SSOModule` | `auth.config` | Bootstraps OpenSAML, builds `MetadataManager`, `SecurityPolicyResolver`, `AuthKeyManager` |
| `RPSModule` | `auth.config` | Binds `RestrictedPartyScreeningService` |
| `LocalCacheModule` | `auth.config` | Provides Guava-backed `REFERRER_HOSTS_CACHE` with 30-min TTL |
| `SSOCacheModule` | `sso.cache` | SSO-specific cache bindings |

---

## 5. Token Lifecycle Data Flow

Tokens are UUID-based opaque bearer tokens stored in DynamoDB. There are three expiry strategies: `InactivityTimeout`, `FixedTimeout`, and `OneTimeUse`.

### Token Structure (in-memory `Token` model)

```
+-------------------------------------------------------+
|                     Token (model)                      |
+-------------------------------------------------------+
| accessToken        : UUID string (partition key)       |
| userId             : Integer (0 if client token)       |
| clientId           : String (null if user token)       |
| grantType          : password|client_credentials|      |
|                      authorization_code|session_key    |
| tokenExpiryType    : InactivityTimeout|FixedTimeout|  |
|                      OneTimeUse                        |
| tokenTtl           : seconds (1800 default for users)  |
| tokenType          : "Bearer"                          |
| tokenGeneratedUtc  : Date                              |
| tokenLastAccessUtc : Date                              |
| principalDetails   : JSON blob (User or Client)        |
| scope              : space-delimited roles+entitlements|
| switchCompanyId    : Integer (context switch)          |
| switchLoginName    : String  (context switch)          |
| contextSwitchType  : AdminSudo|AdminReadOnly|...       |
| switchUserId       : Integer (legacy user in PTUI)     |
+-------------------------------------------------------+
```

### DynamoDB Storage (`TokenWrapper`)

```
+-------------------------------------------------------+
|              DynamoDB Item (table: token)               |
+-------------------------------------------------------+
| hashKey         [PK]  : accessToken UUID               |
| principalId     [GSI] : userId or clientId             |
| token           [attr]: JSON blob (Token object)       |
| principalDetails[attr]: JSON blob (User/Client)        |
| expiresOn       [attr]: computed epoch                 |
| ttl             [TTL] : expiresOn + 72000 seconds      |
+-------------------------------------------------------+
```

### Token Creation

```
CLIENT                         AuthResource / AuthConnectResource
  |                                    |
  | POST / {grant_type, credentials}   |
  |----------------------------------->|
  |                                    |
  |                       validate credentials
  |                       (ClientService / PTUIUserService / UserService)
  |                                    |
  |                       compute scope = roles + entitlements
  |                                    |
  |                       TokenService.generateToken()
  |                            |
  |                            v
  |                       Token.builder()
  |                         .accessToken(UUID.randomUUID())
  |                         .tokenExpiryType("InactivityTimeout")  <-- users
  |                         .tokenTtl(1800)                         <-- 30 min
  |                         .tokenLastAccessUtc(now)
  |                         .principalDetails(JSON)
  |                         .scope(...)
  |                         .build()
  |                            |
  |                            v
  |                       TokenDao.addToken()
  |                         --> DynamoDB PutItem
  |                            (ttl = expiresOn + 72000)
  |<-----------------------------------|
  | { accessToken, tokenType, scope }  |
```

### Token Validation (every downstream resource call)

```
DOWNSTREAM SERVICE              AuthResource
  |                                  |
  | GET /auth/principal              |
  |   Authorization: Bearer <token>  |
  |--------------------------------->|
  |                                  |
  |                     TokenService.validateToken()
  |                       strip "Bearer " prefix
  |                       TokenDao.getToken(uuid)
  |                         --> DynamoDB GetItem (consistent read)
  |                       token == null? --> 401
  |                       token.isValid()?
  |                         InactivityTimeout:
  |                           now - tokenLastAccessUtc > tokenTtl? --> 401
  |                           else: update tokenLastAccessUtc (slide window)
  |                         FixedTimeout:
  |                           now - tokenGeneratedUtc > tokenTtl? --> 401
  |                         OneTimeUse:
  |                           always valid (once), then invalidated
  |                       build InttraPrincipal
  |<---------------------------------|
  | { userId, companyId, roles, ... }|
```

### Token Invalidation (logout)

```
BROWSER                     AuthResource
  |                              |
  | GET /invalidate              |
  |   Authorization: Bearer ...  |
  |----------------------------->|
  |                              |
  |             check grantType == "password"?
  |               yes -> check SAML session:
  |                 idpService.requiresSamlLogout()? -> initiateSingleLogout()
  |                 spService.requiresSamlLogout()?  -> initiateSingleLogout()
  |                              |
  |             TokenService.invalidateToken()
  |               token.setTokenTtl(0)  <-- immediate expiry
  |               TokenDao.updateToken()
  |               --> DynamoDB UpdateItem
  |                              |
  |             redirect=true? --> sendRedirect(loginPortalUrl)
  |<-----------------------------|
```

### Context Switch (Admin Sudo)

```
ADMIN USER                  AuthResource
  |                              |
  | POST /context                |
  |   Authorization: Bearer ...  |
  |   { contextSwitchType,       |
  |     switchCompanyId, ... }   |
  |----------------------------->|
  |                              |
  |             validate current token
  |             check user has SUDO_ADMIN
  |             get target company entitlements
  |             compute roles for context type:
  |               AdminSudo     -> all module roles
  |               AdminReadOnly -> read-only roles only
  |               AdminUserSwitch -> target user's roles
  |               UserCompanySwitch -> same roles, diff company
  |                              |
  |             TokenService.setContextSwitch()
  |               token.switchCompanyId = ...
  |               token.contextSwitchType = ...
  |               TokenDao.updateToken()
  |               --> DynamoDB UpdateItem
  |                              |
  |             return modified token with new scope
  |<-----------------------------|
```

---

## 6. Auth Grant Type Flows

### 6.1 `password` Grant (User Login)

```
BROWSER/SPA                          AuthResource
  |                                       |
  | POST /                                |
  |  { grant_type: "password",            |
  |    username, password }              |
  |-------------------------------------->|
  |                                       |
  |                        try PTUIUserService.validateLogin()
  |                          POST legacy PTUI portal
  |                          returns PTUIUserDetails
  |                          user.setRoles(getRolesForMigratedUser())
  |                        catch NotFoundException:
  |                          UserService.validateUserLogin()
  |                          (new cloud users — Aurora MySQL only)
  |                                       |
  |                        i18n: update preferredLanguage if cookie present
  |                                       |
  |                        generateTokenForUser(user, "password")
  |                          scope = roles + entitlements (space-delimited)
  |                          TokenService.generateToken(user, ...)
  |                                       |
  |<--------------------------------------|
  |  Token { accessToken, scope, ... }    |
  |                                       |
  | GET /login?authorization=<token>      |
  |-------------------------------------->|
  |                          set cookies:
  |                            TOKEN=<uuid>; domain=inttra.com
  |                            SCOPE=...; HttpOnly
  |                            language_pref=...
  |                            domain_switch=...
  |                          redirect: -> second domain for sync
  |                            then redirect: loginPortalUrl -> app
  |<--------------------------------------|
  | 302 Location: <app portal URL>        |
```

### 6.2 `client_credentials` Grant (Machine-to-Machine)

```
API CLIENT                           AuthResource
  |                                       |
  | GET /                                 |
  |   client_id: <id>                     |
  |   client_secret: <secret>             |
  |   grant_type: client_credentials      |
  |  OR                                   |
  | POST / { grant_type, clientId, ... }  |
  |-------------------------------------->|
  |                                       |
  |                        ClientService.validateCredentials()
  |                          ClientDao.getClient() via Aurora MySQL
  |                          cryptoLib.verifyHash(secret, storedHash)
  |                                       |
  |                        enrich client:
  |                          EntitlementsService.getEntitlements(npi)
  |                          ClientDao.getClientRoles()
  |                                       |
  |                        generateTokenForClient(client)
  |                          scope = clientRoles + entitlements
  |                          tokenExpiryType = FixedTimeout
  |                          tokenTtl = 43200 (12 hours)
  |                                       |
  |<--------------------------------------|
  | Token { accessToken, scope, ... }     |
```

### 6.3 `authorization_code` Grant (OAuth2 PKCE-like)

```
BROWSER                   PARTNER CLIENT              AuthResource
  |                             |                           |
  | GET /connect                |                           |
  |   Authorization: Bearer ... |                           |
  |   client_id: <id>           |                           |
  |---------------------------------------> POST /connect/validate
  |                             |        (verify callbackUrl + origin)
  |                             |                           |
  |<--------------------------------------- ConnectResponse
  |  { client_name, client_id,  |        { code: OTT UUID,
  |    callbackUrl, code }       |          callbackUrl }
  |                             |                           |
  | redirect -> callbackUrl?code=OTT
  |------------>                |                           |
  |             | POST /                                    |
  |             |   { grant_type: authorization_code,       |
  |             |     client_id, client_secret, code }       |
  |             |------------------------------------------>|
  |             |                           ClientService.validateCredentials()
  |             |                           TokenService.validateToken(code)
  |             |                           UserService.getUserById(token.userId)
  |             |                           generateTokenForUser(user, "authorization_code")
  |             |<------------------------------------------|
  |             | Token { accessToken, scope }               |
```

### 6.4 `session_key` Grant (Partner SSO via One-Time Token)

```
BROWSER (authenticated)        AuthResource                PARTNER SYSTEM
  |                                  |                           |
  | GET /sso?partner=odex            |                           |
  |   Authorization: Bearer ...      |                           |
  |--------------------------------->|                           |
  |                    validate existing user token              |
  |                    ClientService.validateCredentials(partner)|
  |                    check client.status == "Active"           |
  |                    generateToken(client, "session_key", userJson, null)
  |                      tokenExpiryType = OneTimeUse            |
  |<---------------------------------|                           |
  | { partnerUrl: <url>?authcode=OTT }                          |
  |                                                             |
  | redirect -> partner URL?authcode=OTT                        |
  |------------------------------------------------------------>|
  |                                  | GET /validate-user        |
  |                                  |   Authorization: OTT      |
  |                                  |<--------------------------|
  |                                  | validate token            |
  |                                  | token.tokenExpiryType == OneTimeUse
  |                                  |   -> invalidateToken()     |
  |                                  |-------------------------->|
  |                                  | User { ... }              |
```

### 6.5 e2open Proxy Auto-Login (`ExternalAuthResource`)

```
BROWSER (e2open proxy)          ExternalAuthResource
  |                                    |
  | GET /authorize                     |
  |   iv-user: <loginName>             |
  |   (cookie TOKEN=<uuid> optional)   |
  |----------------------------------->|
  |                    e2ProxyEnabled? (UIConfigurationService)
  |                    true:
  |                      UserService.getUserByLogin(login)
  |                      cookie present?
  |                        validateToken() -- reuse if valid for same user
  |                      else: generateTokenForUser(user, "password")
  |                        set TOKEN cookie
  |                        set SCOPE cookie
  |<-----------------------------------|
  | 200 OK (cookies set)               |
```

---

## 7. DynamoDB Table Schemas

All table names are prefixed with the `environment` value from `dynamoDbConfig.environment` (e.g., `inttra_int_auth_token`, `inttra_int_auth_SAMLMetadata`). The prefix scheme is `<environment>_<tableName>`.

### 7.1 `token` Table

**Purpose:** Stores all active bearer tokens. DynamoDB Streams enabled (`NEW_IMAGE`).

```
+---------------------------------------------+-------------------+----------+
| Attribute         | Type    | Role           | Notes             |          |
+---------------------------------------------+-------------------+----------+
| hashKey           | String  | PARTITION KEY  | UUID access token |          |
| principalId       | String  | GSI partition  | userId or clientId|          |
| token             | Map     | Attribute      | JSON-serialized   |          |
|                   |         |                | Token object      |          |
| principalDetails  | String  | Attribute      | JSON User/Client  |          |
| expiresOn         | Number  | Attribute      | Epoch seconds     |          |
| ttl               | Number  | TTL attribute  | expiresOn + 72000 |          |
+-------------------+---------+----------------+-------------------+----------+

GSI: token_principal_id_index
  Partition Key : principalId
  Projection    : KEYS_ONLY
  Purpose       : Look up all tokens for a given user/client (e.g., invalidate OTTs)

DynamoDB Stream : NEW_IMAGE
  Purpose       : Feeds lambda/auth-tokens-archive for archival of expired tokens
```

### 7.2 `SAMLMetadata` Table

**Purpose:** Stores SAML entity descriptor XML for IDP and SP entities registered in the system.

```
+---------------------------------------------+-------------------+
| Attribute           | Type    | Role         | Notes             |
+---------------------------------------------+-------------------+
| entityId            | String  | PARTITION KEY| SAML entity ID    |
| entityDescriptorType| String  | Attribute    | IDP or SP         |
| entityDescriptor    | String  | Attribute    | Base64 XML        |
| idpProviderName     | String  | GSI partition| Human-readable    |
| referrerHostList    | List    | Attribute    | Allowed referrers |
| activeFlag          | Boolean | Attribute    | Soft-delete flag  |
| audit               | Map     | Attribute    | Created/Modified  |
+---------------------+---------+--------------+-------------------+

GSI: IDENTITY_PROVIDER_NAME_INDEX
  Partition Key : idpProviderName
  Projection    : ALL
  Purpose       : Look up metadata by provider name (e.g., "inttra", "e2open")
```

### 7.3 `OAuthMetadata` Table

**Purpose:** Stores OAuth2/OIDC provider configurations for the Relying Party SSO flows.

```
+-----------------------------------------------+-------------------+
| Attribute               | Type    | Role       | Notes             |
+-----------------------------------------------+-------------------+
| id                      | String  | PARTITION  | Provider ID       |
| metadataType            | String  | SORT KEY   | OAuthMetadataType |
|                         |         |            | enum value        |
| authenticationProvider  | String  | GSI part.  | Provider name     |
|   Name                  |         |            |                   |
| oidcMetadata            | Map     | Attribute  | OIDC discovery    |
|                         |         |            | JSON              |
| clientInfo              | Map     | Attribute  | client_id, secret,|
|                         |         |            | authMethod        |
| referrerHostList        | List    | Attribute  | Allowed origins   |
| isDynamic               | Boolean | Attribute  | Dynamic OIDC disc.|
| activeFlag              | Boolean | Attribute  | Enabled flag      |
| audit                   | Map     | Attribute  | Created/Modified  |
+-------------------------+---------+------------+-------------------+

GSI: AUTHENTICATION_PROVIDER_NAME_INDEX
  Partition Key : authenticationProviderName
  Projection    : KEYS_ONLY
  Purpose       : Look up provider by name for redirect-based SSO entry
```

### 7.4 `sso_message_detail` Table

**Purpose:** Transient SSO state storage: OAuth state parameter, PKCE code challenge, post-auth redirect URL. TTL-controlled.

```
+---------------------------------------------+-------------------+
| Attribute           | Type    | Role         | Notes             |
+---------------------------------------------+-------------------+
| messageId           | String  | PARTITION KEY| OAuth state param |
| messageType         | String  | SORT KEY     | e.g. "AUTHN_REQ"  |
| ssoType             | String  | Attribute    | SAML or OAUTH     |
| authenticationPro   | String  | Attribute    | Provider ID       |
|   viderId           |         |              |                   |
| details             | Map     | Attribute    | destinationUrl,   |
|                     |         |              | refererUrl, etc.  |
| expiresOn           | Number  | TTL attr     | Epoch seconds     |
| createdDateUtc      | String  | Attribute    | ISO-8601          |
+---------------------+---------+--------------+-------------------+

No GSI. Consistent-read lookups by composite key only.
TTL: managed by `expiresOn` field via DynamoDB TTL feature.
```

### 7.5 `samlmessagedetail` Table

**Purpose:** SAML-specific message replay prevention and state tracking. 1-hour TTL.

```
+---------------------------------------------+-------------------+
| Attribute         | Type    | Role           | Notes             |
+---------------------------------------------+-------------------+
| hashKey           | String  | PARTITION KEY  | SAML message ID   |
| entityId          | String  | SORT KEY       | SP/IDP entity ID  |
| messageType       | String  | Attribute      | AuthnRequest/Resp |
| details           | Map     | Attribute      | Map<String,String>|
|                   |         |                | SAML detail attrs |
| ttlInEpochSeconds | Number  | TTL attr       | now + 3600s       |
+-------------------+---------+----------------+-------------------+

No GSI. TTL = 3600 seconds (1 hour).
```

---

## 8. Aurora MySQL Schema Overview

The service maintains two connection pools to the `Network` database:

- **Primary (RW):** `jdbc:mysql:aws://<cluster-writer-endpoint>:3306/Network`
- **Read Replica (RO):** `jdbc:mysql:aws://<cluster-reader-endpoint>:3306/Network`

Driver: `software.aws.rds.jdbc.mysql.Driver` (AWS IAM-aware, version 1.1.0)

### Key Tables (inferred from Mapper classes and domain models)

| Table | Mapper(s) | Key Domain Objects | Description |
|---|---|---|---|
| `user` | `UserMapper`, `UserMapperReadOnly` | `User` | Cloud user accounts with `login_name` (email), `user_status`, `company_id`, `preferred_language`, OFAC status |
| `user_company` | `UserMapper` | `UserCompany` | Multi-company user memberships; links users to `network_participant_id` |
| `client` | `ClientMapper`, `ClientMapperReadOnly` | `Client` | API clients with `client_id`, hashed `client_secret`, `token_expiry_type`, `token_ttl`, `status` |
| `client_role` | `ClientMapper` | `ClientRole` | Role assignments per client; `client_id + role` |
| `entitlement` | `EntitlementsMapper` | `Entitlement` | Module entitlements per company/NPI: `module`, `network_participant_id` |
| `role` | `RolesMapper` | (String set) | Module-to-role mappings; read-only; used by `RolesDao` |
| `legal_agreement` | `LegalAgreementMapper` | `LegalAgreement` | Platform legal agreement versions |
| `user_legal_agreement` | `LegalAgreementMapper` | (join) | Per-user acceptance records |
| `user_profile_preference` | `UserProfilePreferencesMapper` | `UserProfilePreference` | User consent preferences: show userInfo, companyInfo, entitlements to 3rd parties |
| `ptui_user` | `PTUIUserMapper`, `PTUIUserMapperReadOnly` | `PTUIUserDetails` | Migrated PTUI (legacy) user shadow records in Aurora |
| `country_configuration` | `CountryConfigurationMapper` | `MenuConfig` | Country-level menu/feature configuration |
| `url_detail` | `UrlDetailMapper`, `UrlDetailMapperReadOnly` | `UrlDetail` | SSO URL mapping for post-auth redirect computation |
| `ui_configuration` | `UIConfigurationReadMapper` | (String flags) | Feature flags: `e2proxy_enabled`, `domain_switch_flag`, etc. |

### MyBatis Connection Pool Settings (from `config.yaml`)

```
initialSize : 5
minSize     : 5
maxSize     : 35
useSSL      : true
autoReconnect: true
```

---

## 9. Oracle Database Schema Overview

**Connection:** `jdbc:oracle:thin:@<host>:1521/<service>`
**Driver:** `oracle.jdbc.driver.OracleDriver`
**Pool:** 5–35 connections, `validationQuery: select 1 from dual`

This is the **legacy INTTRA portal database** (PTUI — Portal/DELPHI user system). The mapper is read-only from auth's perspective for login validation.

| Table / View | Mapper | Key Fields | Description |
|---|---|---|---|
| INTTRA user tables | `InttraUserMapper` | `userId`, `loginName`, `password` (MD5), `companyId`, `status` | Legacy user credentials. MD5-hashed passwords (`MD5Util`). Auth falls back here if user not found in Aurora. |

The Oracle connection is used only by `PTUIUserService.validateLogin()` — users authenticate against the legacy portal, then roles are fetched from Aurora. The `MD5Util` class handles legacy password comparison.

---

## 10. Guice DI Module Wiring

```
AuthService.main()
  |
  +-- InttraServer.builder()
       |
       +-- moduleGenerator: MyCustomBatisModule (mysql-aurora-auth-readonly)
       |     Binds MyBatis SqlSessionFactory for Aurora read-only replica
       |     Mappers: ClientMapperReadOnly, UserMapperReadOnly, EntitlementsMapper,
       |              RolesMapper, PTUIUserMapperReadOnly, UrlDetailMapperReadOnly,
       |              UIConfigurationReadMapper
       |
       +-- moduleGenerator: MyCustomBatisModule (mysql-aurora-auth-primary)
       |     Binds MyBatis SqlSessionFactory for Aurora writer
       |     Mappers: ClientMapper, UserMapper, PTUIUserMapper, UrlDetailMapper,
       |              DatabaseHealthCheckMapper, LegalAgreementMapper,
       |              UserProfilePreferencesMapper, CountryConfigurationMapper
       |     Transactional: PTUIUserDao
       |
       +-- moduleGenerator: MyCustomBatisModule (oracle-inttra)
       |     Binds MyBatis SqlSessionFactory for Oracle DB
       |     Mappers: InttraUserMapper
       |
       +-- moduleGenerator: AuthApplicationModule
       |     bind(EnvironmentConfig) -> config.getEnvironmentConfig()
       |     bind(Encryptor)         -> new Encryptor(password, salt)
       |     jersey.register(XSSInterceptor, XSSFilter)
       |
       +-- moduleGenerator: AuthEmailSenderModule
       |     Binds EmailClient, EmailSender, TemplateEngine (FreeMarker)
       |
       +-- moduleGenerator: AuthDynamoModule
       |     @Provides DynamoDbClientConfig
       |       -> reads BaseDynamoDbConfig from AuthServiceConfig
       |     @Provides TokenDao
       |       -> DatabaseRepository<TokenWrapper, DefaultPartitionKey<String>>
       |     @Provides SamlMetadataDao
       |       -> DatabaseRepository<SAMLMetadata, DefaultPartitionKey<String>>
       |     @Provides OAuthMetadataDao
       |       -> DatabaseRepository<OAuthMetadata, DefaultCompositeKey<String,String>>
       |     @Provides SSOMessageDetailDao
       |       -> DatabaseRepository<SSOMessageDetail, DefaultCompositeKey<String,String>>
       |     @Provides SamlMessageDetailDao
       |       -> DatabaseRepository<SamlMessageDetail, DefaultCompositeKey<String,String>>
       |
       +-- moduleGenerator: SSOModule
       |     bind(AuthKeyManager)  -> new AuthKeyManager(keyStore, passwordMap, null)
       |     bind(SamlConfig)      -> config.getSamlConfig()
       |     bind(EnvironmentConfig)
       |     bind(ParserPool)      -> StaticBasicParserPool (initialized)
       |     @Provides MetadataManager
       |       -> IDPMetadataProvider + SPMetadataProvider + StoredMetadataProviders (from DynamoDB)
       |     @Provides SecurityPolicyResolver
       |       -> BasicSecurityPolicy with:
       |            IssueInstantRule(clockSkew=300, expiresAfter=300)
       |            SAML2HTTPRedirectDeflateSignatureRule
       |            SAML2HTTPPostSimpleSignRule
       |
       +-- moduleGenerator: RPSModule
       |     Validates OFACBy config (ACCUITY or RPS)
       |     bind(RestrictedPartyScreeningService) -> HTTP client to Amber Road
       |
       +-- moduleGenerator: LocalCacheModule
       |     @Provides @Named("REFERRER_HOSTS_CACHE")
       |       ServiceCache<String, Set<EntityReferrer>>
       |       CacheBuilder.expireAfterWrite(30, MINUTES).recordStats()
       |
       +-- moduleGenerator: SSOCacheModule
             SSO-specific cache bindings
```

---

## 11. REST API Summary Table

All endpoints are mounted under `/auth` (server rootPath). Port `8080` (application), `8081` (admin/health).

### Core Authentication Endpoints (`AuthResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/` | None | Client-credentials grant (headers: `client_id`, `client_secret`, `grant_type`) |
| `POST` | `/auth/` | None | User/client authentication. Body: `AuthRequest` with `grant_type` = `password`, `client_credentials`, or `authorization_code` |
| `GET` | `/auth/login` | None | Token cookie-setter + dual-domain sync redirect after successful login |
| `GET` | `/auth/principal` | None | Return enriched `InttraPrincipal` from bearer token. Validates e2proxy headers when enabled |
| `GET` | `/auth/validate` | None | Validate bearer token, check `rootPath` entitlement |
| `GET` | `/auth/validate-user` | None | Validate token and return filtered `User` object (respects `UserProfilePreference` gates for `authorization_code`) |
| `GET` | `/auth/invalidate` | None | Logout: SAML SLO if applicable, then invalidate token. Optional `?redirect=true` |
| `POST` | `/auth/context` | Authenticated | Admin context switch: `AdminSudo`, `AdminReadOnly`, `AdminUserSwitch`, `UserCompanySwitch` |
| `POST` | `/auth/reset` | Authenticated | Restore context switch — revert to original user context |
| `GET` | `/auth/sso` | Authenticated | Generate one-time token for partner redirect (`?partner=odex`) |
| `GET` | `/auth/ott/{userId}` | `NETWORK_ADMIN`, `REGISTRATION_ADMIN` | Generate one-time token for a specific user (for password reset flows) |

### Connect (OAuth Authorization Code) (`AuthConnectResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/connect` | Authenticated | Initiate authorization-code flow: validate token, generate OTT, return `ConnectResponse` with `code` |
| `POST` | `/auth/connect/validate` | None | Validate client's `callbackUrl` and `origin` before redirect |

### External / E2Proxy Auth (`ExternalAuthResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/authorize` | None (header: `iv-user`) | E2open proxy auto-login: look up user by login name, regenerate token and set cookies |
| `GET` | `/auth/e2proxyflag` | None | Return `{ "e2ProxyEnabled": "true/false" }` |

### User Management (`UserResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `POST` | `/auth/users` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Create user |
| `GET` | `/auth/users/{userId}` | Authenticated | Get user by ID |
| `PUT` | `/auth/users/{userId}` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Update user |
| `DELETE` | `/auth/users/{userId}` | `NETWORK_ADMIN` | Delete user |
| `GET` | `/auth/users` | Authenticated | Search users (by company, status, etc.) |
| `GET` | `/auth/users/current` | Authenticated | Get current logged-in user |
| `GET` | `/auth/users/export` | `NETWORK_ADMIN` | CSV export of users |
| `POST` | `/auth/users/{userId}/migrate` | `NETWORK_ADMIN` | Migrate legacy PTUI user to cloud |
| `POST` | `/auth/users/{userId}/merge` | `NETWORK_ADMIN` | Merge two user accounts |
| `GET` | `/auth/users/validate-email` | None | Check if email already in use |

### User Password (`UserPasswordResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `POST` | `/auth/users/password/forgot` | None | Initiate forgot-password: send reset email with OTT link |
| `POST` | `/auth/users/password/reset` | None (OTT in body) | Reset password using one-time token |
| `POST` | `/auth/users/password/change` | Authenticated | Change own password |

### User Roles (`UserRolesResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/users/{userId}/roles` | Authenticated | Get user's roles |
| `POST` | `/auth/users/{userId}/roles` | `NETWORK_ADMIN`, `COMPANY_USER_ADMIN` | Add roles to user |
| `DELETE` | `/auth/users/{userId}/roles/{role}` | `NETWORK_ADMIN` | Remove role from user |

### User Legal Agreement (`UserLegalAgreementResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/users/{userId}/legalagreement` | Authenticated | Get user's legal agreement acceptance |
| `POST` | `/auth/users/{userId}/legalagreement` | Authenticated | Record user's acceptance of latest agreement |

### User OFAC (`UserOfacResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `POST` | `/auth/users/{userId}/ofac` | `NETWORK_ADMIN` | Run OFAC screening on user (via Accuity or RPS) |

### User Profile Preferences (`UserProfilePreferenceResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/users/{userId}/preferences` | Authenticated | Get data sharing preferences |
| `PUT` | `/auth/users/{userId}/preferences` | Authenticated | Update data sharing preferences |

### Client Management (`ClientResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `POST` | `/auth/clients/register` | `NETWORK_ADMIN` | Register new API client (generates ID/secret, sends email) |
| `GET` | `/auth/clients/{clientId}` | `NETWORK_ADMIN` | Get client by ID |
| `GET` | `/auth/clients` | `NETWORK_ADMIN` | List clients by `?inttraCompanyId` |
| `PUT` | `/auth/clients/{clientId}` | `NETWORK_ADMIN` | Update client name/roles |
| `PUT` | `/auth/clients/{clientId}/activate` | `NETWORK_ADMIN` | Activate client |
| `PUT` | `/auth/clients/{clientId}/deactivate` | `NETWORK_ADMIN` | Deactivate client |
| `DELETE` | `/auth/clients/{clientId}` | `NETWORK_ADMIN` | Delete client |
| `POST` | `/auth/clients/{clientId}/resetpassword` | `NETWORK_ADMIN` | Rotate client secret; sends email |
| `GET` | `/auth/clients/{clientId}/roles` | `NETWORK_ADMIN` | List client roles |
| `POST` | `/auth/clients/{clientId}/roles` | `NETWORK_ADMIN` | Add roles to client |
| `DELETE` | `/auth/clients/{clientId}/roles` | `NETWORK_ADMIN` | Remove all client roles |

### Legal Agreement (`LegalAgreementResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/legalagreement/{id}` | None | Get agreement by ID |
| `GET` | `/auth/legalagreement/latest` | None | Get current active agreement |
| `GET` | `/auth/legalagreement` | None | List all agreements |
| `POST` | `/auth/legalagreement` | Authenticated | Create new agreement |
| `DELETE` | `/auth/legalagreement/{id}` | Authenticated | Delete agreement |

### Menu (`MenuResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/menus` | Authenticated | Get navigation menus for user's locale/country |

### SAML IDP (`IdpServiceResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/saml/idp/metadata` | None | Return IDP XML metadata (optionally for specific SP entityId) |
| `GET` | `/auth/saml/idp/singlesignonservice` | Authenticated | IDP-initiated SSO with service name |
| `GET` | `/auth/saml/idp/redirect/singlesignonservice` | None | SP-initiated SSO via HTTP Redirect binding |
| `POST` | `/auth/saml/idp/post/singlesignonservice` | None | SP-initiated SSO via HTTP POST binding |
| `GET` | `/auth/saml/idp/redirect/singlelogout` | None | SLO via HTTP Redirect |
| `POST` | `/auth/saml/idp/post/singlelogout` | None | SLO via HTTP POST |

### SAML SP (`SpServiceResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/saml/sp/metadata` | None | Return SP XML metadata |
| `GET` | `/auth/saml/sp/sendauthnrequest` | None | Initiate SP-initiated SSO (send AuthnRequest to external IDP) |
| `POST` | `/auth/saml/sp/post/assertionconsumerservice` | None | Receive and process SAML assertion from IDP |
| `GET` | `/auth/saml/sp/redirect/singlelogout` | None | SP SLO via Redirect |
| `POST` | `/auth/saml/sp/post/singlelogout` | None | SP SLO via POST |

### SSO Management (`SSOResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/sso/mappedurl` | None | Resolve encoded destination params to mapped URL |
| `POST` | `/auth/sso/urlmapping` | `SSO_ADMIN` | Add URL mapping |
| `DELETE` | `/auth/sso/urlmapping/{key}` | `SSO_ADMIN` | Remove URL mapping |

### OAuth Metadata Management (`OAuthMetadataResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `POST` | `/auth/oauth/metadata/static/{metadataType}` | `SSO_ADMIN` | Create/update static OIDC provider metadata |
| `POST` | `/auth/oauth/metadata/dynamic` | `SSO_ADMIN` | Create/update dynamic OIDC provider metadata |
| `POST` | `/auth/oauth/metadata/{id}/referrer` | `SSO_ADMIN` | Add referrer host to provider |
| `DELETE` | `/auth/oauth/metadata/{id}/referrer` | `SSO_ADMIN` | Remove referrer host |
| `GET` | `/auth/oauth/metadata/{id}` | `SSO_ADMIN` | Get OAuth metadata by ID |
| `GET` | `/auth/oauth/metadata` | `SSO_ADMIN` | List all providers |
| `POST` | `/auth/oauth/metadata/{id}/update` | `SSO_ADMIN` | Update provider configuration |

### OAuth2/OIDC Relying Party (`OAuthResource`)

| Method | Path | Roles Required | Description |
|---|---|---|---|
| `GET` | `/auth/sso/oauth2/oid` | None | Handle OIDC authorization response (code + state); exchange for ID token, issue Inttra token |

---

## 12. Security Design

### Token Architecture

The Auth service does NOT use JWTs. It issues **opaque UUID-v4 bearer tokens**. All token metadata (user, roles, scope, expiry) is stored server-side in DynamoDB. This is a deliberate architectural choice ensuring:
- Instant revocation without key rotation
- No sensitive claims exposed in the token itself
- No signature verification overhead on each downstream call

```
Token String format:   xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx  (UUID v4)
Token Type:            Bearer
Header format:         Authorization: Bearer <uuid>
Cookie format:         TOKEN=<uuid>; HttpOnly; Secure; SameSite=Lax
```

### Token Expiry Types

| Type | Default TTL | Behavior | Used For |
|---|---|---|---|
| `InactivityTimeout` | 1800 s (30 min) | Last-access time slides on each `/principal` call; expires if idle > TTL | All user (password, authorization_code) grants |
| `FixedTimeout` | 43200 s (12 hrs) | Expires at `tokenGeneratedUtc + tokenTtl` regardless of activity | All `client_credentials` grants |
| `OneTimeUse` | Configurable | Valid once; invalidated immediately after `/validate-user` or partner SSO | OTT for password reset, connect flow, partner SSO |

### Inactivity Timeout Implementation Detail

```
TokenService.getAndValidateToken(accessToken):
  1. DynamoDB GetItem (consistent read = true)
  2. token.isValid() check:
       InactivityTimeout:
         elapsed = now - tokenLastAccessUtc
         if elapsed > tokenTtl * 1000 ms -> throw 401
       FixedTimeout:
         elapsed = now - tokenGeneratedUtc
         if elapsed > tokenTtl * 1000 ms -> throw 401
       OneTimeUse:
         passes validation
  3. if INACTIVITY:
       token.tokenLastAccessUtc = now
       DynamoDB UpdateItem (slide window)
  4. return token
```

### Password Security

| Mechanism | Details |
|---|---|
| Cloud user passwords | Bcrypt hashed via `CryptoLib.hash()` / `verifyHash()` |
| Legacy PTUI passwords | MD5 hashed (via `MD5Util`) — legacy only |
| Client secrets | Bcrypt hashed via `CryptoLib`. Legacy plain-text fallback during migration |
| Text Encryption | Jasypt-based `Encryptor` with configurable `password` and `salt` for field-level encryption |

### XSS Protection

Two layers registered in `AuthApplicationModule`:

| Component | Scope | Mechanism |
|---|---|---|
| `XSSFilter` | Headers + Query Params | Jersey `ContainerRequestFilter`; pattern-matches against XSS signatures; throws `IllegalArgumentException` |
| `XSSInterceptor` | POST/PUT request bodies | Jersey `ReaderInterceptor`; validates JSON body content |

### Cookie Security

| Cookie | Value | Flags |
|---|---|---|
| `TOKEN` | Bearer UUID | `HttpOnly`, `Secure`, domain-scoped |
| `SCOPE` | Space-delimited roles | domain-scoped |
| `domain_switch` | Boolean flag | domain-scoped |
| `language_pref` / `locale_pref` | BCP-47 code | domain-scoped |

### Dual-Domain Cookie Sync

On login, the service performs a two-step redirect to sync cookies across the two platform domains (`inttra.com` and `inttra.e2open.com`):

```
Step 1: primary domain sets cookies, redirects to secondary domain with ?syncdomain=true&authorization=<token>
Step 2: secondary domain sets cookies, redirects to ?syncdomain=false -> final app URL
```

### OFAC Screening

Configurable via `OFACBy` property:
- `ACCUITY`: calls Accuity ComplianceLink SOAP service via Apache Axis
- `RPS`: calls Amber Road Restricted Party Screening REST API

### E2Proxy Validation

When `e2ProxyEnabled = true`:
- Every `/principal` call for user tokens validates the `iv-user` header value matches the token's `loginName`
- Bypass for requests originating from `inttra.com` domain (only enforced on `inttra.e2open.com`)
- The `e2ProxyLoginFromFilter` header is used when the request is from the internal auth filter (bypasses `iv-user` absence)

---

## 13. SSO and SAML Integration Flow

### 13.1 SAML Architecture Overview

The Auth service maintains a dual SAML role:

```
External SP Partners                  Auth Service               Enterprise IDPs
(PayCargo, CargoSphere,  <---SAML--->  IDP Role          SP Role  <---SAML--->  (e2open, LDAP, etc.)
 e2open, ODEX, Shop)                  (/saml/idp)      (/saml/sp)
```

OpenSAML 2.6.6 + Spring Security SAML `MetadataManager` manages entity descriptors for all registered SP and IDP partners. External SP metadata is stored in DynamoDB (`SAMLMetadata` table) and loaded at startup by `SSOModule`.

### 13.2 IDP-Initiated SSO (Inttra as IDP)

```
BROWSER (authenticated)         IdpServiceResource          External SP
  |                                    |                          |
  | GET /saml/idp/singlesignonservice  |                          |
  |   Authorization: Bearer <token>    |                          |
  |   ?serviceName=intransitvisibility |                          |
  |----------------------------------->|                          |
  |              idpService.validateSecurityContext()             |
  |              idpService.doSSOWithServiceName()                |
  |                |                                             |
  |                | build SAMLResponse assertion:               |
  |                |   subject: user loginName (or customized)   |
  |                |   attributes: per AssertionCustomization     |
  |                |     AppendIDPNameAsSuffix: user@inttradev    |
  |                |     ExtendedAttributes: FIRST_NAME, EMAIL... |
  |                |     NameID: emailAddress format              |
  |                |   sign with IDP private key                  |
  |                |                                             |
  |              HTTP POST to SP ACS URL                         |
  |<----------------------------------->|------------------------->|
  |                                    |  SAMLResponse (POST)     |
```

### 13.3 SP-Initiated SSO (Inttra as SP, receiving from external IDP)

```
BROWSER                    SpServiceResource           External IDP
  |                               |                         |
  | GET /saml/sp/sendauthnrequest |                         |
  |   ?referer=<b64>              |                         |
  |   ?destinationUrl=<b64>       |                         |
  |------------------------------>|                         |
  |              spService.sendAuthNRequest()               |
  |                store state in sso_message_detail (DDB)  |
  |                build AuthnRequest XML                   |
  |                sign with SP private key                 |
  |              HTTP Redirect (deflate-encoded)            |
  |<----------------------------->|------------------------>|
  | 302 -> IDP SSO URL?SAMLRequest=...&SigAlg=...          |
  |                                                         |
  | (user authenticates at IDP)                             |
  |                               |                         |
  | POST /saml/sp/post/assertion  |                         |
  |   consumeservice              |                         |
  |   SAMLResponse=...            |<------------------------|
  |------------------------------>|                         |
  |              spService.processAssertion()               |
  |                validateSignature via SecurityPolicyResolver
  |                validateIssueInstant (clockSkew=300s)    |
  |                extract NameID -> loginName              |
  |                UserService.getUserByLogin(nameId)       |
  |                generateTokenForUser(user, "password")   |
  |                set TOKEN cookie                         |
  |              redirect -> destinationUrl                 |
  |<------------------------------|                         |
  | 302 -> app portal with cookies set                      |
```

### 13.4 SAML Assertion Customization

The IDP supports per-SP assertion customization defined in `samlConfig.idp.assertionCustomizations`:

| Customization Type | Handler | Effect |
|---|---|---|
| `AppendIDPNameAsSuffix` | `AppendIdpNameCustomizationHandler` | Appends `@<suffix>` to NameID (e.g., `user@inttradev`) |
| `ExtendedAttributes` | `ExtendedAttributeCustomizationHandler` | Maps `AssertionAttributeKey` enum values to SP-specific SAML attribute names |
| `NameID` | `NameIDCustomizationHandler` | Overrides the NameID format (e.g., to `emailAddress`) |

**AssertionAttributeKey enum values:** `FIRST_NAME`, `LAST_NAME`, `PHONE`, `EMAIL`, `STREET_ADDRESS`, `STATE`, `CITY`, `COUNTRY`, `POSTAL_CODE`, `COMPANY_ID`, `COMPANY_NAME`, `WT_ENTERPRISE_CODE`, `LOGIN_ID`, `USER_ID`, `FULL_NAME`

### 13.5 OAuth2/OIDC Relying Party Flow

```
BROWSER                  OAuthResource / RelyingPartyService     External OIDC IDP
  |                               |                                    |
  | (trigger: referrer host       |                                    |
  |  matches OAuthMetadata)       |                                    |
  | GET /sso/oauth2/oid           |                                    |
  |   (initial request, no code)  |                                    |
  |------------------------------>|                                    |
  |              HostEvaluationService.resolveProvider()              |
  |              OAuthMetadataService.getByReferrer()                 |
  |              AuthenticationRequestUrlBuilder.build()              |
  |                state = UUID, stored in sso_message_detail (DDB)   |
  |              build authorization URL:                              |
  |                response_type=code, scope=openid profile email     |
  |                redirect_uri=/auth/sso/oauth2/oid                  |
  |<------------------------------|                                    |
  | 302 -> IDP authorize endpoint |                                    |
  |--------------------------------------------------------------------->|
  | (user authenticates at IDP)                                        |
  |                                                                    |
  | GET /auth/sso/oauth2/oid      |                                    |
  |   ?code=<authz_code>&state=.. |<-----------------------------------|
  |------------------------------>|                                    |
  |              validate state vs sso_message_detail                  |
  |              AccessTokenService.exchangeCode()                     |
  |                client_auth_method: SecretBasic or SecretPost       |
  |                POST token endpoint with code                       |
  |              validate ID Token (nimbusds oauth2-oidc-sdk)          |
  |              extract sub/email -> UserService.getUserByLogin()     |
  |              generateTokenForUser(user, "password")                |
  |              set TOKEN cookie, redirect to destinationUrl          |
  |<------------------------------|                                    |
  | 302 -> app with cookies set   |                                    |
```

### 13.6 Key Store Management

`AuthKeyStore` loads X.509 certificates and private keys from PEM strings in config (loaded from AWS Parameter Store) into a Java `KeyStore`. `AuthKeyManager` (extending Spring Security SAML's `KeyManager`) manages credential resolution for IDP and SP operations. Dual key support (`privateKey2`, `certificate2`) enables zero-downtime key rotation.

---

## 14. Design Patterns Used

### Repository Pattern
All data access is abstracted behind DAO classes (`TokenDao`, `ClientDao`, etc.) which delegate to either MyBatis mappers or the `cloud-sdk` `DatabaseRepository` interface. Resources and services never touch persistence APIs directly.

### Dependency Injection (Guice)
Google Guice 4.1.0 manages all singleton lifecycles. Each cross-cutting concern (DynamoDB, SAML, Email, RPS) is in its own `AbstractModule`. `@Provides` methods allow factory-style provisioning where simple `bind()` is insufficient.

### Strategy Pattern
- `AccessTokenServiceProvider` selects between `SecretBasicAccessTokenService` and `SecretPostAccessTokenService` based on `OAuthClientInfo.clientAuthenticationMethod`
- `AssertionCustomizationHandlerFactory` selects `CustomizationHandler` implementations by `CustomizationType` enum
- `OfacCheckType` enum drives selection between Accuity SOAP and RPS REST OFAC checkers

### Factory Pattern
`DynamoRepositoryFactory.createEnhancedRepository()` is used throughout `AuthDynamoModule` to create typed repositories from entity class annotations, avoiding duplication of DynamoDB client setup.

### Template Method
`DynamoDbAdminCommand` (base class in `cloud-sdk`) implements the table creation flow; `AuthDynamoDbAdminCommand` only provides the list of entity classes and the `resolveClientConfig()` implementation.

### Builder Pattern
Pervasive use of Lombok `@Builder` across domain models (`Token`, `TokenWrapper`, `SAMLMetadata`, `OAuthMetadata`, `SamlMessageDetail`, `ConnectResponse`, `Client`) and the `InttraServer` bootstrapper.

### Decorator / Wrapper Pattern
`TokenWrapper` wraps the `Token` model for DynamoDB serialization, adding DynamoDB-specific fields (`hashKey`, `principalId`, `ttl`) while preserving clean domain separation.

### Cache-Aside
`LocalCacheModule` provides a Guava `LoadingCache` for `EntityReferrer` lookups. Cache misses trigger a database load; a 30-minute TTL ensures eventual consistency with low read pressure. Cache metrics are registered with Dropwizard.

### Dual-Mapper Pattern (Read/Write Separation)
Every performance-critical entity has two MyBatis mapper interfaces: a read-write version (`UserMapper`, `ClientMapper`) bound to the Aurora writer endpoint, and a read-only version (`UserMapperReadOnly`, `ClientMapperReadOnly`) bound to the Aurora read replica. Reads use the replica; writes use the writer.

### XSS Interceptor Pattern
Two Jersey filter interfaces are combined: a `ContainerRequestFilter` for URL parameters/headers (`XSSFilter`) and a `ReaderInterceptor` for request bodies (`XSSInterceptor`). Both throw `IllegalArgumentException` on detection, which the `ILLEGAL_ARGUMENT_EXCEPTION_MAPPER` converts to `400 Bad Request`.

---

## 15. Configuration Properties Reference

All configuration is loaded from a YAML file passed at startup (`server.run(args)`). Secrets are injected from AWS Systems Manager Parameter Store using the `${awsps:/...}` syntax resolved at startup.

### Server

| Property | Type | Example | Description |
|---|---|---|---|
| `server.rootPath` | String | `/auth` | All endpoints mounted under this path |
| `server.applicationConnectors[0].port` | int | `8080` | Application port |
| `server.adminConnectors[0].port` | int | `8081` | Admin/health port |
| `server.applicationConnectors[0].responseCookieCompliance` | String | `RFC2965` | Cookie compliance for Set-Cookie headers |

### Databases

| Property | Type | Description |
|---|---|---|
| `database.driverClass` | String | Aurora MySQL writer driver (`software.aws.rds.jdbc.mysql.Driver`) |
| `database.url` | String | Writer JDBC URL |
| `database.user`, `database.password` | String | DB credentials (from AWS Parameter Store) |
| `database.maxSize` | int | Max connection pool size (default: 35) |
| `readOnlyDatabase.*` | (same) | Read-replica connection pool |
| `inttraDatabase.driverClass` | String | Oracle driver (`oracle.jdbc.driver.OracleDriver`) |
| `inttraDatabase.url` | String | Oracle JDBC URL |
| `inttraDatabase.validationQuery` | String | `select 1 from dual` |

### DynamoDB

| Property | Type | Example | Description |
|---|---|---|---|
| `dynamoDbConfig.environment` | String | `inttra_int_auth` | Table name prefix |
| `dynamoDbConfig.region` | String | `us-east-1` | AWS region |
| `dynamoDbConfig.readCapacityUnits` | int | `5` | Provisioned RCU (if not on-demand) |
| `dynamoDbConfig.writeCapacityUnits` | int | `5` | Provisioned WCU |
| `dynamoDbConfig.sseEnabled` | boolean | `false` | Server-side encryption |

### SAML Configuration (`samlConfig`)

| Property | Type | Description |
|---|---|---|
| `samlConfig.loginServiceUrl` | String | URL of login portal (redirect target after SSO) |
| `samlConfig.keyStorePassPhrase` | String | Master passphrase for combined IDP+SP keystore |
| `samlConfig.idp.entityId` | String | IDP SAML entity ID |
| `samlConfig.idp.privateKey` | String | PEM private key (from AWS Parameter Store) |
| `samlConfig.idp.certificate` | String | PEM certificate |
| `samlConfig.idp.privateKey2` | String | Secondary key for rotation |
| `samlConfig.idp.certificate2` | String | Secondary certificate for rotation |
| `samlConfig.idp.keyStorePassword` | String | Key entry password in keystore |
| `samlConfig.idp.baseUrl` | String | Auth service base URL (for ACS/SLO endpoint resolution) |
| `samlConfig.idp.clockSkew` | int | Clock tolerance in seconds (default: 300) |
| `samlConfig.idp.expiresAfter` | int | Assertion validity window in seconds (default: 300) |
| `samlConfig.idp.assertionCustomizations` | List | Per-SP assertion customization rules |
| `samlConfig.sp.*` | (same structure) | SP-specific keys and certificates |
| `samlConfig.consumerServiceConfigs` | List | Named consumer services (name, URL, entityId) |
| `samlConfig.referEntityIds` | List | `host|idpEntityId` pairs for referrer-based IDP selection |

### Environment URLs (`environmentConfig`)

| Property | Description |
|---|---|
| `shipmentPortalURL` | Default post-login redirect (if no redirectUrl specified) |
| `osPortalURL` | Ocean Schedules portal |
| `bookingPortalURL` | Booking portal |
| `myAdminPortalURL` | My Admin portal |
| `myAdminHarmonizedPortalURL` | New harmonized My Admin URL |
| `myAccountPortalURL` | My Account portal |
| `authApiURL` | This service's own public URL |
| `visibilityPortalUrl` | Visibility portal |
| `loginPortalUrl` | Login portal URL (redirect target on logout) |
| `ssoErrorUrl` | Error page URL for SSO failures |
| `paycargoShipAndPayUrl` | PayCargo Ship & Pay integration URL |
| `paycargoPayNowUrl` | PayCargo Pay Now integration URL |
| `paycargoLinkEnabled` | Feature flag (from AWS Parameter Store) |
| `paycargoNetworkParticipantId` | PayCargo NPI for link enablement check |
| `eblDashboardUrl` | eBL dashboard URL |
| `shippeoUrl` | Shippeo visibility integration URL |
| `ratesUrl` | CargoSphere rates URL |

### Security Resources

| Property | Description |
|---|---|
| `securityResources.oauthTokenValidationUri` | Public token validation endpoint (used by downstream services) |
| `securityResources.userInfoUri` | User info endpoint |
| `securityResources.userPrincipalUri` | Principal resolution endpoint |
| `securityResources.activateUri` | User activation link base URL |
| `securityResources.activateLinkExpiryDays` | Activation link validity in days |
| `securityResources.resetPasswordUri` | Password reset link base URL |
| `securityResources.resetPasswordLinkExpiryDays` | Reset link validity in days |
| `securityResources.userMgmtCommEmailAddress` | From-address for user management emails |
| `securityResources.landingPage` | Default post-login landing page |

### Mail

| Property | Description |
|---|---|
| `mailConfig.senderEmailAddress` | Sender email address (FROM header) |
| `mailConfig.copyToEmailAddress` | CC address for outbound emails |

### PTUI (Legacy Portal)

| Property | Description |
|---|---|
| `ptuiConfig.createUserURL` | Legacy PTUI user creation endpoint |
| `ptuiConfig.updateUserURL` | Legacy PTUI user roles update endpoint |
| `ptuiConfig.getRolesURL` | Legacy PTUI roles retrieval endpoint |
| `ptuiConfig.updateRolesURL` | Legacy PTUI bulk roles update endpoint |
| `ptuiConfig.adminUserId` | PTUI admin service account |
| `ptuiConfig.adminPassword` | PTUI admin password (from AWS Parameter Store) |
| `ptuiConfig.networkAuthURL` | Callback URL pointing to this auth service |

### Accuity OFAC

| Property | Description |
|---|---|
| `accuityConfig.accuityURL` | ComplianceLink SOAP WSDL/service endpoint |
| `accuityConfig.accuityClientId` | Accuity API client identifier |

### Text Encryption

| Property | Description |
|---|---|
| `textEncryptionConfig.password` | Jasypt encryption password |
| `textEncryptionConfig.salt` | Jasypt encryption salt |

### OFAC Check Type

| Property | Values | Description |
|---|---|---|
| `OFACBy` | `ACCUITY` or `RPS` | Selects the OFAC screening provider |

### RPS (Restricted Party Screening)

| Property | Description |
|---|---|
| `rpsServiceDefinition.name` | Service definition identifier |
| `rpsServiceDefinition.uri` | Amber Road RPS endpoint |
| `rpsServiceDefinition.clientId` | RPS client ID (from AWS Parameter Store) |
| `rpsServiceDefinition.clientSecret` | RPS client secret |

### Xlog (Legacy Audit)

| Property | Description |
|---|---|
| `xlogConfig.xlogServiceUrl` | INTTRA legacy Xlog SOAP audit endpoint |
| `xlogConfig.appSecurityKey` | Application security key for Xlog |
| `xlogConfig.appGuid` | Application GUID for Xlog |
| `xlogConfig.webServiceID` | Web service ID for Xlog |

### Partner Details

```yaml
partnerDetails:
  - partnerName: odex          # partner identifier in /sso?partner= query
    partnerURL: <url>          # redirect target after OTT generation
    responseType: simple       # "simple" = minimal user fields; "all" = full user object
  - partnerName: shop
    partnerURL: <url>
    responseType: all
```

### Jersey Client (for outbound HTTP calls)

| Property | Default | Description |
|---|---|---|
| `jerseyClient.minThreads` | 32 | Minimum thread pool |
| `jerseyClient.maxThreads` | 128 | Maximum thread pool |
| `jerseyClient.timeout` | 10s | Read timeout |
| `jerseyClient.connectionTimeout` | 2s | Connect timeout |

---

## 16. Inter-Service Dependencies

### Inbound Dependencies (services that call Auth)

Every Mercury microservice validates tokens and resolves principals by calling the Auth service. They are configured with three security-resources endpoints:

| Endpoint Called | Purpose |
|---|---|
| `GET /auth/validate` | Validate token exists and is not expired |
| `GET /auth/principal` | Resolve `InttraPrincipal` (roles, entitlements, companyId) from bearer token |
| `GET /auth/validate-user` | Exchange OTT for User object (partner integrations) |

Microservices that call Auth: `network`, `booking`, `ocean-schedules`, `shipment`, `visibility`, `rates`, `cfast`, `registration`, `watermill-publisher`, `webbl`, `bill-of-lading`, `shipping-instruction`, `value-added-service`, `tx-tracking`, `kibisis-iot`, `partner-integrator`.

### Outbound Dependencies (what Auth calls)

| System | Protocol | Purpose |
|---|---|---|
| **Aurora MySQL** (writer) | JDBC (AWS MySQL driver 1.1.0) | Write user/client/entitlement/role data |
| **Aurora MySQL** (reader) | JDBC (AWS MySQL driver 1.1.0) | Read-heavy queries (user lookup, client lookup, entitlements) |
| **Oracle INTTRA DB** | JDBC (ojdbc10 19.14) | Legacy PTUI user credential validation on login fallback |
| **Amazon DynamoDB** | AWS SDK v2 Enhanced Client | Token storage, SAML/OAuth metadata, SSO state |
| **AWS Systems Manager** | Parameter Store API (at startup) | Secret injection: DB passwords, SAML keys, API keys |
| **PTUI Legacy Portal** | HTTP REST | User management (create, update, role provision) via `ptuiConfig` URLs |
| **Accuity ComplianceLink** | SOAP (Apache Axis 1.4) | OFAC/sanction screening on user registration (if OFACBy=ACCUITY) |
| **Amber Road RPS** | HTTP REST | Restricted Party Screening (if OFACBy=RPS) |
| **Email (AWS SES or SMTP)** | SMTP/API | Password reset emails, client setup emails (via `EmailClient`) |
| **Xlog SOAP Service** | SOAP | Legacy audit logging |
| **External OIDC IDPs** | HTTPS (OpenID Connect) | OIDC authorization code exchange for enterprise SSO |
| **External SAML IDPs** | HTTPS (SAML 2.0 HTTP POST/Redirect) | SP-initiated SSO from enterprise IDPs (e2open, etc.) |
| **External SAML SPs** | HTTPS (SAML 2.0 HTTP POST) | IDP-initiated SSO to partner systems (PayCargo, CargoSphere, ODEX, etc.) |

### Lambda Dependencies

| Lambda Module | Trigger | Description |
|---|---|---|
| `lambda/auth-tokens-archive` | DynamoDB Stream on `token` table | Archives expired/deleted tokens to S3 for audit compliance |
| `lambda/bounceback-email` | SES bounce events | Handles email delivery failures for user notifications |

### Internal Mercury Libraries Consumed

| Library | Purpose |
|---|---|
| `commons` | `ApplicationConfiguration`, `InttraServer`, security utilities, `CryptoLib`, `AuthHelper` |
| `cloud-sdk-api` | `DatabaseRepository`, `QuerySpec` interfaces |
| `cloud-sdk-aws` | AWS-specific DynamoDB Enhanced Client implementation |
| `dynamo-integration-test` | DynamoDB Local for integration tests (`*DaoIT.java`) |
| `email-sender` | `EmailClient`, `EmailSender`, FreeMarker template engine wrapper |
| `rps` | `RestrictedPartyScreeningService` |
| `authhelper` | Shared token validation logic used by downstream services |
| `cache-helper` | `ServiceCache`, `GuavaCacheMetrics` |

---

*Document generated by Claude Code on 2026-05-04 from source at `c:\Users\arijit.kundu\projects\mercury-services\auth\`.*
