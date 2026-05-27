# Distributor-REST Module — Design Document

> **Module:** `distributor-rest`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.distributorrest:distributor-rest:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Jersey 3.1.11 + Guice 7.x

---

## 1. Executive Summary

The **Distributor-REST** module is a specialized delivery service that pushes transformed files to external E2Open REST endpoints with OAuth2 authentication. Unlike the standard Distributor (S3-based delivery), this module handles HTTP-based integrations where trading partners expose webhooks for receiving EDI data.

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    TF["Transformer"] -->|"MetaData (REST target)"| DQ["SQS REST Delivery"]
    DQ --> DR["🔷 DISTRIBUTOR-REST"]
    DR -->|"OAuth2"| AUTH["E2Open Auth Server"]
    DR -->|"POST file"| E2["E2Open REST Endpoint"]
    DR -->|"Events"| EVT["SNS Event Store"]
    DR -->|"Errors"| ERR["SQS Errors"]
    
    style DR fill:#4a90d9,color:#fff
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Distributor-REST Service"
        APP[DistributorApplication]
        DT[DistributorTask]
        
        subgraph "REST Client"
            RB[RequestBuilder]
            RSC[RestServiceClient]
            AC[AuthClient]
            RT[RetryerBuilder]
        end
        
        subgraph "External Services"
            SS[SubscriptionService - Cached]
            WS[WorkspaceService - S3]
        end
        
        subgraph "E2Open Integration"
            TOK[Token - OAuth2]
            REQ[Request - URL + Headers]
            RESP[ResponseWrapper]
        end
    end
    
    APP --> DT
    DT --> SS
    DT --> WS
    DT --> RB --> REQ
    DT --> RSC --> AC --> TOK
    RSC --> RT
    RSC --> RESP
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class DistributorTask {
        -subscriptionService: SubscriptionService
        -restServiceClient: RestServiceClient
        -workspaceService: WorkspaceService
        -requestBuilder: RequestBuilder
        +process(Message, String)
    }

    class RequestBuilder {
        +build(Subscription): Request
    }

    class Request {
        -url: String
        -headers: MultivaluedMap
        -oAuthRequest: OAuthRequest
    }

    class RestServiceClient {
        -client: Client
        -authClient: AuthClient
        -retryer: Retryer
        +post(Request, String): String
    }

    class AuthClient {
        -client: Client
        -token: Token
        +getToken(OAuthRequest): Token
        +newToken(OAuthRequest): Token
    }

    class OAuthRequest {
        -clientUserId: String
        -clientSecret: String
        -oAuthUrl: String
    }

    class Token {
        -accessToken: String
        -refreshToken: String
        -tokenType: String
        -expires: String
    }

    class ResponseWrapper {
        -response: Response
    }

    class Response {
        -status: Status
    }

    class Status {
        -code: String
        -text: String
        -e2openTransactionId: String
    }

    DistributorTask --> RequestBuilder
    DistributorTask --> RestServiceClient
    RestServiceClient --> AuthClient
    AuthClient --> Token
    RequestBuilder --> Request
    Request --> OAuthRequest
    RestServiceClient --> ResponseWrapper
    ResponseWrapper --> Response
    Response --> Status
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SQS as SQS Pickup
    participant DT as DistributorTask
    participant S3 as S3 Workspace
    participant SUB as Subscription Service
    participant RB as RequestBuilder
    participant AC as AuthClient
    participant E2 as E2Open Endpoint
    participant SNS as SNS Events

    SQS->>DT: receiveMessage (MetaData JSON)
    DT->>DT: extract subscriptionId from projections
    DT->>S3: getContent(bucket, fileName)
    S3-->>DT: file content
    DT->>SUB: findSubscriptions(subscriptionId)
    SUB-->>DT: Subscription (with actions)
    DT->>RB: build(subscription)
    Note over RB: Extract EDI_WEBHOOK action<br/>Map params → URL + headers + OAuth
    RB-->>DT: Request {url, headers, oAuthRequest}
    DT->>AC: getToken(oAuthRequest)
    AC-->>DT: Token {accessToken}
    DT->>E2: POST fileContent with headers + Bearer token
    alt SUCCESS response
        E2-->>DT: {Status: {Code: "SUCCESS", E2openTransactionId: "..."}}
        DT->>SNS: logCloseRunEvent(SUCCESS, transactionId)
    else Non-SUCCESS
        E2-->>DT: {Status: {Code: "ERROR"}}
        DT->>DT: throw NonRecoverableException
    else 401 Unauthorized
        DT->>AC: newToken(oAuthRequest)
        DT->>E2: Retry with fresh token
    end
```

---

## 6. Subscription-to-Request Transformation

The `RequestBuilder` maps subscription action parameters to an HTTP request:

```mermaid
flowchart TD
    S[Subscription] --> A[Actions List]
    A --> F{ActionType == EDI_WEBHOOK?}
    F -->|Yes| P[ActionParameters]
    P --> H["Headers: fromDuns, toDuns, dataType, version"]
    P --> O["OAuth: userid, password, oAuthUrl"]
    P --> U["URL: endPointUrl + ?connectionId=X"]
    H & O & U --> R[Request Object]
```

| Parameter | Maps To |
|-----------|---------|
| `fromDuns` | HTTP Header |
| `toDuns` | HTTP Header |
| `dataType` | HTTP Header |
| `version` | HTTP Header |
| `userid` | OAuthRequest.clientUserId |
| `password` | OAuthRequest.clientSecret |
| `oAuthUrl` | OAuthRequest.oAuthUrl |
| `connectionId` | URL query parameter |
| `endPointUrl` | Request base URL |

---

## 7. Retry & Error Recovery Strategy

| Error | Retry? | Action |
|-------|--------|--------|
| HTTP 401 | Yes | Refresh token, retry |
| HTTP 404 | No | Fail immediately |
| HTTP 400 | No | Fail immediately |
| HTTP 5xx | Yes | Exponential backoff |
| Connection error | Yes | Exponential backoff |
| Non-SUCCESS response | No | `NonRecoverableException` |

**Retry Configuration:**
- Max attempts: 3
- Wait strategy: Exponential (100ms base)
- Listener: Logs each retry attempt

---

## 8. Configuration Details

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `componentName` | String | `distributor-rest` | Service identity |
| `healthCheckConfig.errorRateThreshold` | Double | `5.0` | Error rate threshold |
| `restClientConfig.connectTimeout` | String | `60000` | HTTP connect timeout (ms) |
| `restClientConfig.readTimeout` | String | `60000` | HTTP read timeout (ms) |
| `sqsPickupConfig.queueUrl` | String | — | Delivery pickup queue |
| `sqsPickupConfig.waitTimeSeconds` | int | `20` | Long poll duration |
| `sqsPickupConfig.maxNumberOfMessages` | int | `5` | Batch/thread count |
| `sqsErrorConfig.queueUrl` | String | — | Error queue |
| `snsEventConfig.topicArn` | String | — | Event topic |
| `s3WorkspaceConfig.bucket` | String | — | Source file bucket |
| `networkServiceConfig.*` | Object | — | Network service endpoints |

---

## 9. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Framework, workspace, events |
| `jersey-client` | 3.1.11 | HTTP client |
| `jersey-media-multipart` | 3.1.11 | Multipart support |
| `jersey-hk2` | 3.1.11 | DI bridge |
| `dropwizard-core` | 4.0.16 | Application framework |
| `guice` | 7.0.0 | Dependency injection |
| `guava-retrying` | — | Retry library |

---

## 10. OAuth2 Authentication Flow

```mermaid
sequenceDiagram
    participant RSC as RestServiceClient
    participant AC as AuthClient
    participant OAuth as OAuth Server

    RSC->>AC: getToken(oAuthRequest)
    alt Token cached & valid
        AC-->>RSC: cached Token
    else Token expired/missing
        AC->>OAuth: POST (Basic Auth: base64(userId:secret))
        OAuth-->>AC: {access_token, refresh_token, expires}
        AC-->>RSC: new Token
    end
```

---

## 11. Error Handling

| Exception | Handling | Outcome |
|-----------|----------|---------|
| `NonRecoverableException` | E2Open returned non-SUCCESS | ErrorHandler, message fails |
| `RecoverableException` | Network/infra failure | ErrorHandler with retry metadata |
| `IOException` | File read failure | ErrorHandler |
| `WebApplicationException(401)` | Token expired | Automatic token refresh + retry |
