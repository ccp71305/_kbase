# Transformer Module — Design Document

> **Module:** `transformer`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.transformer:transformer:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Guice 7.x + Contivo 6.7.2

---

## 1. Executive Summary

The **Transformer** is the format conversion engine of AppianWay — the most complex module in the pipeline. It transforms EDI messages between formats (EDIFACT ↔ XML ↔ ANSI X12 ↔ Flat-File) using the Contivo mapping engine, generates control numbers via DynamoDB, applies pre/post-processing sanitization, performs structural validation, and can generate EDI Functional Acknowledgments (997/CONTRL).

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    SP["Splitter"] -->|"Split message"| RQ["SQS Router"]
    RQ --> TF["🔷 TRANSFORMER"]
    TF -->|"Transformed output"| WS["S3 Workspace"]
    TF -->|"Route to Distributor"| DQ["SQS Distributor"]
    TF -->|"Route REST"| DRQ["SQS Distributor-REST"]
    TF -->|"FA Response"| FAQ["SQS FA Queue"]
    TF -->|"Errors"| ERR["SQS Errors"]
    TF -->|"Events"| EVT["SNS Event Store"]
    TF -->|"Control Numbers"| DDB["DynamoDB"]
    
    style TF fill:#c0392b,color:#fff
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Transformer Service"
        APP[TransformerApplication]
        TT[TransformerTask]
        
        subgraph "Transformation Engine"
            TF[TransformationsFlow]
            IT[InboundTransformation]
            OT[OutboundTransformation]
            TP[TransformationParams Builder]
        end
        
        subgraph "Pre/Post Processing"
            PP1[X12ControlCharacterPreprocessor]
            PP2[InboundSanitizationPreprocessor]
            PP3[CharacterReplacementPreprocessor]
        end
        
        subgraph "Control Numbers"
            ACNG[AnsiControlNumberGenerator]
            ECNG[EdifactControlNumberGenerator]
            XCNG[XmlControlNumberGenerator]
            FFCNG[FfControlNumberGenerator]
            ZCNG[ZimControlNumberGenerator]
        end
        
        subgraph "Structural Validation"
            SVFP[StructuralValidationFAProcessor]
            SVM[StructuralValidatorModule]
        end
    end
    
    APP --> TT --> TF
    TF --> IT & OT
    TT --> PP1 & PP2 & PP3
    TT --> ACNG & ECNG & XCNG & FFCNG & ZCNG
    TT --> SVFP
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class TransformerTask {
        -transformationsFlow: TransformationsFlow
        -preprocessors: List~Preprocessor~
        -params: TransformationParams
        -eventLogger: EventLogger
        +process(Message, String)
        -buildTransformationParams(MetaData): TransformationParams
    }

    class TransformationsFlow {
        -transformations: List~NamedTransformation~
        +getApplicableTransformation(MetaData): Optional~NamedTransformation~
    }

    class NamedTransformation {
        <<interface>>
        +getName(): String
        +isApplicable(MetaData): boolean
        +transform(TransformationParams): TransformationResult
    }

    class InboundTransformation {
        -contivo: ContivoCacheableTransformer
        -controlNumberGenerator: ControlNumberGenerator
        +isApplicable(MetaData): boolean
        +transform(TransformationParams): TransformationResult
    }

    class OutboundTransformation {
        -contivo: ContivoCacheableTransformer
        -controlNumberGenerator: ControlNumberGenerator
        +isApplicable(MetaData): boolean
        +transform(TransformationParams): TransformationResult
    }

    class TransformationParams {
        -metaData: MetaData
        -content: String
        -sourceFormat: String
        -targetFormat: String
        -integrationProfileId: String
        -subscriptionId: String
        -mapId: String
        -controlNumber: String
        -tokens: Map
    }

    class ControlNumberGenerator {
        <<interface>>
        +generate(String prefix): String
    }

    class DynamoDBControlNumberGenerator {
        -dynamoDBClient: DynamoDB
        -tableName: String
        -sequenceName: String
        +generate(String): String
    }

    class Preprocessor {
        <<interface>>
        +preprocess(String content, MetaData): String
    }

    class StructuralValidationFAProcessor {
        -structuralValidator: StructuralValidator
        +validate(String, MetaData): StructuralValidationResult
        +shouldGenerateFA(MetaData): boolean
        +generateFA(StructuralValidationResult): String
    }

    TransformerTask --> TransformationsFlow
    TransformationsFlow --> NamedTransformation
    NamedTransformation <|.. InboundTransformation
    NamedTransformation <|.. OutboundTransformation
    InboundTransformation --> ControlNumberGenerator
    OutboundTransformation --> ControlNumberGenerator
    ControlNumberGenerator <|.. DynamoDBControlNumberGenerator
    TransformerTask --> Preprocessor
    TransformerTask --> StructuralValidationFAProcessor
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SQS as SQS Router
    participant TT as TransformerTask
    participant S3 as S3 Workspace
    participant PP as Preprocessors
    participant TF as TransformationsFlow
    participant CT as Contivo Engine
    participant DDB as DynamoDB
    participant SV as StructuralValidator
    participant OUT as Target Queue

    SQS->>TT: receiveMessage (MetaData JSON)
    TT->>S3: getContent(bucket, fileName)
    S3-->>TT: raw EDI content
    TT->>PP: preprocess(content, metaData)
    PP-->>TT: sanitized content
    TT->>TF: getApplicableTransformation(metaData)
    TF-->>TT: InboundTransformation | OutboundTransformation
    TT->>DDB: generate(sequenceName)
    DDB-->>TT: controlNumber
    TT->>CT: transform(params)
    CT-->>TT: TransformationResult (transformed content)
    opt Structural Validation Required
        TT->>SV: validate(result, metaData)
        SV-->>TT: StructuralValidationResult
        alt Validation Failed
            TT->>TT: generateFA(result)
            TT->>OUT: route FA to response queue
        end
    end
    TT->>S3: putObject(transformed content)
    TT->>OUT: sendMessage(metaData with new fileName)
```

---

## 6. Transformation Types

### Inbound vs Outbound

| Direction | Source | Target | Example |
|-----------|--------|--------|---------|
| **Inbound** | Partner EDI | INTTRA Canonical XML | EDIFACT IFTMBF → Booking XML |
| **Outbound** | INTTRA XML | Partner EDI | SI XML → EDIFACT IFTMIN |

### Contivo Engine Integration

```mermaid
flowchart TD
    INPUT["Source EDI/XML"] --> MAP["Contivo Map (.cvm file)"]
    MAP --> ENGINE["ContivoCacheableTransformer"]
    ENGINE --> OUTPUT["Transformed EDI/XML"]
    
    CONFIG["Map ID from Integration Profile Format"] --> MAP
    CACHE["LoadingCache (map file cache)"] --> ENGINE
```

---

## 7. Control Number Generators

| Generator | Format | DynamoDB Sequence | Output Example |
|-----------|--------|-------------------|----------------|
| `AnsiControlNumberGenerator` | X12 ISA/GS | `ansi-{prefix}` | `000000001` (9 digits) |
| `EdifactControlNumberGenerator` | EDIFACT UNB/UNG | `edifact-{prefix}` | `0000000001` (10 digits) |
| `XmlControlNumberGenerator` | XML documents | `xml-{prefix}` | `{sequence}` |
| `FfControlNumberGenerator` | Flat-file | `ff-{prefix}` | `{sequence}` |
| `ZimControlNumberGenerator` | ZIM carrier specific | `zim-{prefix}` | `{sequence}` |

**DynamoDB atomic increment:**
```
UpdateItem: SET sequence_value = sequence_value + 1
Table: {controlNumberTable}
Key: {sequenceName}
ReturnValues: UPDATED_NEW
```

---

## 8. Preprocessors

| Preprocessor | When Applied | Action |
|-------------|-------------|--------|
| `X12ControlCharacterPreprocessor` | ANSI X12 inbound | Strips/normalizes control chars (ISA delimiter fixup) |
| `InboundSanitizationPreprocessor` | All inbound | Character encoding normalization, BOM removal |
| `CharacterReplacementPreprocessor` | Configurable | Replaces characters per integration profile rules |

---

## 9. Structural Validation & Functional Acknowledgment

```mermaid
flowchart TD
    MSG["Transformed Message"] --> CHECK{FA Required?}
    CHECK -->|Yes| VAL["StructuralValidator.validate()"]
    VAL --> RESULT{Valid?}
    RESULT -->|Yes| PASS["Continue pipeline"]
    RESULT -->|No| GEN["Generate 997/CONTRL FA"]
    GEN --> ROUTE["Route FA to response queue"]
    ROUTE --> ERR["Mark original as error"]
    CHECK -->|No| PASS
```

FA generation produces EDI acknowledgment messages (997 for X12, CONTRL for EDIFACT) sent back to the originating partner.

---

## 10. Configuration Details

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `componentName` | String | `transformer` | Service identity |
| `sqsPickupConfig.queueUrl` | String | — | Router queue |
| `sqsPickupConfig.maxNumberOfMessages` | int | `10` | Batch size |
| `sqsDropOffConfig.queueUrl` | String | — | Distributor queue |
| `sqsRestDropOffConfig.queueUrl` | String | — | REST distributor queue |
| `sqsErrorConfig.queueUrl` | String | — | Error subscription queue |
| `snsEventConfig.topicArn` | String | — | Event topic |
| `s3WorkspaceConfig.bucket` | String | — | Workspace bucket |
| `dynamoDBConfig.tableName` | String | — | Control number table |
| `dynamoDBConfig.region` | String | — | AWS region |
| `contivoConfig.mapDirectory` | String | — | .cvm map files path |
| `contivoConfig.cacheSize` | int | `100` | Map cache size |
| `contivoConfig.cacheExpiry` | int | `30` | Cache TTL (minutes) |
| `structuralValidation.enabled` | boolean | `true` | Enable/disable FA |
| `preprocessors` | List | 3 | Enabled preprocessor list |
| `networkServiceConfig.*` | Object | — | Format/IP endpoints |

---

## 11. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Framework, S3, SQS |
| `structuralvalidator` | 1.0 | Structural validation |
| `schema-beans` | 1.0 | JAXB result types |
| Contivo dependencies (25+) | 6.7.2 | Transformation engine |
| `aws-java-sdk-dynamodb` | 1.12.720 | Control numbers |
| `dropwizard-core` | 4.0.16 | Application framework |
| `guice` | 7.0.0 | DI container |
| `guava` | 33.1.0-jre | Caching, utilities |

---

## 12. Error Handling

| Error Type | Behavior |
|-----------|----------|
| Map not found | Non-recoverable → Error queue |
| Contivo transformation failure | Non-recoverable → Error queue with details |
| DynamoDB timeout | Recoverable → Retry |
| S3 read/write failure | Recoverable → Retry |
| Structural validation failure | Generate FA + route to error |
| Invalid control character | Preprocessor normalizes (not an error) |

---

## 13. Design Patterns

| Pattern | Usage |
|---------|-------|
| **Strategy** | NamedTransformation implementations |
| **Chain** | Preprocessor pipeline |
| **Builder** | TransformationParams with 20+ fields |
| **Cache-Aside** | Contivo map caching (LoadingCache) |
| **Template Method** | Abstract control number base |
| **Factory** | ControlNumberGeneratorFactory selects by format |
