# StructuralValidator Module — Design Document

> **Module:** `structuralvalidator`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury:structuralvalidator:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Test Framework:** JUnit 5

---

## 1. Executive Summary

The **StructuralValidator** is a library module (not a standalone service) that validates EDI messages against format-specific rulesets. It checks segment structure, element cardinality, mandatory fields, qualifier values, and occurrence constraints. The validation result is serialized into JAXB types (from `schema-beans`) and used by the Transformer to decide whether to generate Functional Acknowledgments (997/CONTRL).

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    TF["Transformer"] -->|"Calls"| SV["🔷 STRUCTURALVALIDATOR"]
    SV -->|"Uses"| SB["schema-beans<br/>(JAXB types)"]
    SV -->|"Returns"| RES["StructuralValidationResult"]
    TF -->|"If invalid"| FA["Generate FA"]
    
    style SV fill:#1abc9c,color:#fff
```

---

## 3. Architecture

```mermaid
graph TB
    subgraph "StructuralValidator Library"
        SV[StructuralValidator]
        
        subgraph "Ruleset Providers"
            RP1[IFTSTA_D99B_RulesetProvider]
            RP2[IFTMBF_D99B_RulesetProvider]
            RP3[IFTMBC_D99B_RulesetProvider]
            RP4[IFTSAI_D99B_RulesetProvider]
            RP5[T323_4010_RulesetProvider]
        end
        
        subgraph "Validation Engine"
            DV[DataValidator]
            OC[OccurrenceChecks]
        end
        
        subgraph "Result"
            RTYPE[StructuralValidationResultType]
            RI[ResultInterchangeType]
            RS[ResultSegmentType]
            RE[ResultElementType]
        end
    end
    
    SV --> RP1 & RP2 & RP3 & RP4 & RP5
    SV --> DV --> OC
    DV --> RTYPE --> RI --> RS --> RE
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class StructuralValidator {
        -rulesetProviders: Map~String, RulesetProvider~
        +validate(String content, String messageType, String version): StructuralValidationResultType
        -selectRuleset(String type, String version): RulesetProvider
    }

    class RulesetProvider {
        <<interface>>
        +getMessageType(): String
        +getVersion(): String
        +getRuleset(): Ruleset
    }

    class Ruleset {
        -segmentRules: List~SegmentRule~
        -elementRules: Map~String, List~ElementRule~~
        +getSegmentRules(): List
        +getElementRules(String segment): List
    }

    class SegmentRule {
        -tag: String
        -mandatory: boolean
        -maxOccurrences: int
        -qualifiers: List~String~
    }

    class ElementRule {
        -position: int
        -mandatory: boolean
        -minLength: int
        -maxLength: int
        -dataType: DataType
        -allowedValues: Set~String~
    }

    class DataValidator {
        +validate(ParsedMessage, Ruleset): StructuralValidationResultType
        -validateSegment(Segment, SegmentRule): List~Error~
        -validateElement(Element, ElementRule): List~Error~
    }

    class OccurrenceChecks {
        +checkMandatory(Segment, SegmentRule): Optional~Error~
        +checkMaxOccurrences(int count, SegmentRule): Optional~Error~
        +checkQualifier(Element, List~String~): Optional~Error~
    }

    StructuralValidator --> RulesetProvider
    RulesetProvider --> Ruleset
    Ruleset --> SegmentRule
    Ruleset --> ElementRule
    StructuralValidator --> DataValidator
    DataValidator --> OccurrenceChecks
    DataValidator --> Ruleset
```

---

## 5. Ruleset Provider Matrix

| Provider | Message Type | Version | Standard |
|----------|-------------|---------|----------|
| `IFTSTA_D99B_RulesetProvider` | IFTSTA | D99B | UN/EDIFACT |
| `IFTMBF_D99B_RulesetProvider` | IFTMBF | D99B | UN/EDIFACT |
| `IFTMBC_D99B_RulesetProvider` | IFTMBC | D99B | UN/EDIFACT |
| `IFTSAI_D99B_RulesetProvider` | IFTSAI | D99B | UN/EDIFACT |
| `T323_4010_RulesetProvider` | 323 | 4010 | ANSI X12 |

---

## 6. Validation Flow

```mermaid
sequenceDiagram
    participant TF as Transformer
    participant SV as StructuralValidator
    participant RP as RulesetProvider
    participant DV as DataValidator
    participant OC as OccurrenceChecks

    TF->>SV: validate(content, "IFTMBF", "D99B")
    SV->>RP: selectRuleset("IFTMBF", "D99B")
    RP-->>SV: IFTMBF_D99B Ruleset
    SV->>DV: validate(parsedMessage, ruleset)
    loop For each segment
        DV->>OC: checkMandatory(segment, rule)
        DV->>OC: checkMaxOccurrences(count, rule)
        loop For each element
            DV->>DV: validateElement(element, elementRule)
            DV->>OC: checkQualifier(element, allowedValues)
        end
    end
    DV-->>SV: StructuralValidationResultType
    SV-->>TF: result (valid=true/false, errors, warnings)
```

---

## 7. Validation Checks

| Check Category | Description | Severity |
|---------------|-------------|----------|
| Mandatory segment | Required segment missing | ERROR |
| Segment cardinality | Exceeds max occurrences | ERROR |
| Mandatory element | Required element empty/missing | ERROR |
| Element length | Below min or above max length | WARNING/ERROR |
| Data type | Numeric/Alpha/Alphanumeric mismatch | ERROR |
| Qualifier value | Element value not in allowed set | ERROR |
| Occurrence count | Group repetition limits | ERROR |

---

## 8. Result Structure Example

```json
{
  "valid": false,
  "errorCount": 2,
  "warningCount": 1,
  "interchanges": [
    {
      "controlRef": "12345",
      "senderId": "CARRIER01",
      "receiverId": "INTTRA",
      "segments": [
        {
          "tag": "BGM",
          "position": 3,
          "elements": [
            {
              "position": 1,
              "value": "",
              "severity": "ERROR",
              "message": "Mandatory element missing"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 9. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `schema-beans` | 1.0 | JAXB result types |
| `jakarta.xml.bind-api` | 4.0.2 | JAXB API |
| `junit-jupiter` | 5.x | Unit testing |
| `assertj-core` | 3.x | Fluent assertions |

---

## 10. Design Patterns

| Pattern | Usage |
|---------|-------|
| **Strategy** | 5 RulesetProvider implementations |
| **Registry** | Map-based ruleset selection by type+version |
| **Value Object** | SegmentRule, ElementRule (immutable) |
| **Builder** | StructuralValidationResultType via JAXB |
| **Specification** | Each check is a testable predicate |

---

## 11. Extensibility

Adding a new message type validation requires:

1. Create new `XxxRulesetProvider` implementing `RulesetProvider`
2. Define segment and element rules for the message type
3. Register the provider in the `StructuralValidator` constructor
4. No changes to DataValidator or OccurrenceChecks needed

```mermaid
flowchart TD
    NEW["New IFTMIN_D99B_RulesetProvider"] --> REG["Register in validator"]
    REG --> DONE["Automatically validates IFTMIN messages"]
```
