# Validator Module — Design Document

> **Module:** `validator`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.validator:validator:1.0-SNAPSHOT`  
> **Java Version:** 8 | **Framework:** Dropwizard 1.1.1 + Guice 4.1.0

---

## 1. Executive Summary

The **Validator** module performs business-level XML enrichment and validation for shipping messages. It resolves reference data (carriers, locations, nominees, seal issuers) against the network service, enriches XML documents with resolved codes, and produces validation errors for unresolvable references. It acts as a data quality gate before messages proceed to transformation.

> ⚠️ **Legacy Module:** Uses older Java 8, Dropwizard 1.1.1, and Guice 4.1.0 (unlike modern modules at Java 17/Dropwizard 4.x).

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    SP["Splitter"] -->|"XML Message"| SQ["SQS Validator"]
    SQ --> VL["🔷 VALIDATOR"]
    VL -->|"Enriched XML"| WS["S3 Workspace"]
    VL -->|"Resolved"| TQ["SQS Transformer"]
    VL -->|"Errors"| ERR["SQS Errors"]
    VL <-->|"Lookups"| NET["Network Services"]
    
    style VL fill:#16a085,color:#fff
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Validator Service"
        APP[ValidatorApplication]
        VT[ValidatorTask]
        
        subgraph "Resolution Engine"
            RC[ResolvingConveyor]
            CR[CarrierResolver]
            NR[Nominee4FResolver]
            LR[LocationResolver]
            SR[SealIssuerResolver]
        end
        
        subgraph "Validation"
            VE[ValidationError Builder]
            ERH[ValidationErrorHandler]
        end
    end
    
    APP --> VT --> RC
    RC --> CR & NR & LR & SR
    VT --> VE --> ERH
    CR & NR & LR & SR -->|"Network API"| NET["Network Services"]
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class ValidatorTask {
        -workspaceService: WorkspaceService
        -resolvingConveyor: ResolvingConveyor
        -eventLogger: EventLogger
        +process(Message, String)
    }

    class ResolvingConveyor {
        -resolvers: List~Resolver~
        +resolve(Document, MetaData): ResolutionResult
    }

    class Resolver {
        <<interface>>
        +resolve(Document, MetaData): List~ValidationError~
        +getResolverName(): String
    }

    class CarrierResolver {
        -networkService: NetworkServiceClient
        +resolve(Document, MetaData): List~ValidationError~
        -lookupSCAC(String code): Optional~Carrier~
    }

    class Nominee4FResolver {
        -networkService: NetworkServiceClient
        +resolve(Document, MetaData): List~ValidationError~
        -lookupNominee(String id): Optional~Nominee~
    }

    class LocationResolver {
        -networkService: NetworkServiceClient
        +resolve(Document, MetaData): List~ValidationError~
        -lookupLocation(String code): Optional~Location~
    }

    class SealIssuerResolver {
        -networkService: NetworkServiceClient
        +resolve(Document, MetaData): List~ValidationError~
        -lookupSealIssuer(String code): Optional~SealIssuer~
    }

    class ValidationError {
        -code: String
        -message: String
        -urn: String
        -severity: Severity
        -stopFlag: boolean
        +builder(): ValidationErrorBuilder
    }

    class ResolutionResult {
        -enrichedDocument: Document
        -errors: List~ValidationError~
        -hasStopErrors: boolean
    }

    ResolvingConveyor --> Resolver
    Resolver <|.. CarrierResolver
    Resolver <|.. Nominee4FResolver
    Resolver <|.. LocationResolver
    Resolver <|.. SealIssuerResolver
    ResolvingConveyor --> ResolutionResult
    ResolutionResult --> ValidationError
    ValidatorTask --> ResolvingConveyor
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SQS as SQS Validator
    participant VT as ValidatorTask
    participant S3 as S3 Workspace
    participant RC as ResolvingConveyor
    participant CR as CarrierResolver
    participant LR as LocationResolver
    participant NR as NomineeResolver
    participant SR as SealIssuerResolver
    participant NET as Network Service
    participant OUT as SQS Transformer

    SQS->>VT: receiveMessage (MetaData JSON)
    VT->>S3: getContent(bucket, fileName)
    S3-->>VT: XML document
    VT->>RC: resolve(document, metaData)
    RC->>CR: resolve(document)
    CR->>NET: lookupSCAC("MAEU")
    NET-->>CR: Carrier{id, name, scac}
    CR->>CR: enrich XML with carrier attributes
    RC->>LR: resolve(document)
    LR->>NET: lookupLocation("USLAX")
    NET-->>LR: Location{id, name, unlocode}
    LR->>LR: enrich XML with location details
    RC->>NR: resolve(document)
    RC->>SR: resolve(document)
    RC-->>VT: ResolutionResult{enrichedDoc, errors}
    alt No stop errors
        VT->>S3: putObject(enrichedDocument)
        VT->>OUT: sendMessage(metaData)
    else Has stop errors
        VT->>VT: writeAnnotations(errors)
        VT->>OUT: sendToErrorQueue(metaData)
    end
```

---

## 6. Resolver Chain (Conveyor Pattern)

The `ResolvingConveyor` executes resolvers sequentially — each resolver enriches the document and accumulates errors:

```mermaid
flowchart LR
    DOC["XML Document"] --> CR["CarrierResolver"]
    CR -->|"Enriched + errors"| NR["Nominee4FResolver"]
    NR -->|"Enriched + errors"| LR["LocationResolver"]
    LR -->|"Enriched + errors"| SR["SealIssuerResolver"]
    SR --> RES["ResolutionResult<br/>(enriched doc + all errors)"]
```

---

## 7. Resolver Details

| Resolver | XML Elements | Network Endpoint | Enrichment |
|----------|-------------|-----------------|------------|
| `CarrierResolver` | `<carrier>`, `<scac>` | `/carriers?scac={code}` | Adds carrier ID, name |
| `Nominee4FResolver` | `<nominee>`, `<party4F>` | `/participants?id={id}` | Adds nominee details |
| `LocationResolver` | `<port>`, `<place>` | `/locations?code={code}` | Adds UN/LOCODE, name |
| `SealIssuerResolver` | `<sealIssuer>` | `/sealIssuers?code={code}` | Adds issuer ID |

---

## 8. ValidationError Structure

| Field | Type | Description |
|-------|------|-------------|
| `code` | String | URN-style error code |
| `message` | String | Human-readable description |
| `urn` | String | Full URN path for categorization |
| `severity` | Enum | `ERROR`, `WARNING`, `INFO` |
| `stopFlag` | boolean | If `true`, halts processing |

**Stop error behavior:** If any resolver produces a stop-flag error, the message is routed to the Error queue instead of continuing to Transformer.

---

## 9. Configuration Details

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `componentName` | String | `validator` | Service identity |
| `sqsPickupConfig.queueUrl` | String | — | Validator pickup queue |
| `sqsDropOffConfig.queueUrl` | String | — | Transformer queue |
| `sqsErrorConfig.queueUrl` | String | — | Error subscription queue |
| `s3WorkspaceConfig.bucket` | String | — | Workspace bucket |
| `networkServiceConfig.baseUrl` | String | — | Network service base URL |
| `networkServiceConfig.cacheSize` | int | — | Lookup cache entries |
| `networkServiceConfig.cacheTtl` | int | — | Cache TTL (minutes) |
| `snsEventConfig.topicArn` | String | — | Event topic |

---

## 10. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Framework, S3, SQS, NetworkService |
| `dropwizard-core` | 1.1.1 | Application framework (legacy) |
| `guice` | 4.1.0 | DI container (legacy) |
| `dom4j` / `jdom2` | — | XML DOM manipulation |
| `aws-java-sdk-*` | 1.12.x | S3, SQS, SNS |
| `lombok` | 1.18.x | Code generation |

---

## 11. Design Patterns

| Pattern | Usage |
|---------|-------|
| **Chain of Responsibility** | ResolvingConveyor runs resolvers in order |
| **Builder** | ValidationError.builder() |
| **Enricher** | Each resolver adds data to the XML document |
| **Cache-Aside** | NetworkServiceClient caches lookups |
| **Specification** | Stop-flag predicate on validation errors |
