# Schema-Beans Module — Design Document

> **Module:** `schema-beans`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury:schema-beans:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Build:** Maven + jaxb2-maven-plugin 3.2.0

---

## 1. Executive Summary

The **Schema-Beans** module is a pure code-generation module with zero hand-written Java source files. It houses XSD schema definitions for structural validation results and uses the JAXB (Jakarta XML Binding) code generation plugin to produce type-safe Java classes. These generated beans are consumed by the `structuralvalidator` and `transformer` modules for marshalling/unmarshalling validation results.

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    XSD["StructuralValidationResult.xsd"] -->|"jaxb2-maven-plugin"| GEN["Generated JAXB Classes"]
    GEN --> SV["structuralvalidator"]
    GEN --> TF["transformer"]
    
    style GEN fill:#3498db,color:#fff
```

---

## 3. Architecture

```mermaid
graph TB
    subgraph "schema-beans module"
        subgraph "Source (XSD)"
            X1[StructuralValidationResult.xsd]
        end
        
        subgraph "Generated (target/generated-sources)"
            O1[ObjectFactory.java]
            O2[StructuralValidationResultType.java]
            O3[ResultInterchangeType.java]
            O4[ResultSegmentType.java]
            O5[ResultElementType.java]
            O6[SeverityType.java]
        end
    end
    
    X1 -->|"mvn generate-sources"| O1 & O2 & O3 & O4 & O5 & O6
```

---

## 4. Class Diagram (Generated)

```mermaid
classDiagram
    class ObjectFactory {
        +createStructuralValidationResultType(): StructuralValidationResultType
        +createResultInterchangeType(): ResultInterchangeType
        +createResultSegmentType(): ResultSegmentType
        +createResultElementType(): ResultElementType
    }

    class StructuralValidationResultType {
        -valid: boolean
        -interchanges: List~ResultInterchangeType~
        -errorCount: int
        -warningCount: int
        +isValid(): boolean
        +getInterchanges(): List
    }

    class ResultInterchangeType {
        -controlRef: String
        -segments: List~ResultSegmentType~
        -senderId: String
        -receiverId: String
    }

    class ResultSegmentType {
        -tag: String
        -position: int
        -elements: List~ResultElementType~
        -errors: List~String~
    }

    class ResultElementType {
        -position: int
        -value: String
        -severity: SeverityType
        -message: String
    }

    class SeverityType {
        <<enumeration>>
        ERROR
        WARNING
        INFO
    }

    ObjectFactory --> StructuralValidationResultType
    StructuralValidationResultType --> ResultInterchangeType
    ResultInterchangeType --> ResultSegmentType
    ResultSegmentType --> ResultElementType
    ResultElementType --> SeverityType
```

---

## 5. XSD Schema Structure

```
StructuralValidationResult
├── @valid (boolean)
├── @errorCount (int)
├── @warningCount (int)
└── interchange* (ResultInterchangeType)
    ├── @controlRef (string)
    ├── @senderId (string)
    ├── @receiverId (string)
    └── segment* (ResultSegmentType)
        ├── @tag (string)
        ├── @position (int)
        ├── error* (string)
        └── element* (ResultElementType)
            ├── @position (int)
            ├── @value (string)
            ├── @severity (SeverityType)
            └── @message (string)
```

---

## 6. Build Configuration

### JAXB Generation Plugin

| Plugin Property | Value |
|----------------|-------|
| Plugin | `org.codehaus.mojo:jaxb2-maven-plugin:3.2.0` |
| Goal | `xjc` |
| Source directory | `${project.basedir}/xsd` |
| Output directory | `${project.build.directory}/generated-sources/jaxb` |
| Package | `com.inttra.mercury.schema.validation` |
| Extension | `true` (allows episode file) |

### Build Lifecycle

```mermaid
flowchart LR
    CLEAN["mvn clean"] --> GEN["generate-sources<br/>(jaxb2:xjc)"]
    GEN --> COMPILE["compile<br/>(generated + manual)"]
    COMPILE --> PKG["package<br/>(JAR)"]
```

---

## 7. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `jakarta.xml.bind-api` | 4.0.2 | JAXB API (Jakarta namespace) |
| `jaxb-runtime` | 4.0.5 | JAXB runtime implementation |
| `jaxb2-maven-plugin` | 3.2.0 | XSD → Java code generation |

---

## 8. Consumer Modules

| Module | Usage |
|--------|-------|
| `structuralvalidator` | Creates `StructuralValidationResultType` instances with validation findings |
| `transformer` | Reads `StructuralValidationResultType` to decide FA generation |

---

## 9. Design Notes

- **No source code:** This module exists solely for schema management and code generation
- **Jakarta migration:** Uses `jakarta.xml.bind` (not legacy `javax.xml.bind`)
- **Versioning:** Schema changes require regeneration; downstream modules depend on the generated API
- **Immutable contract:** The XSD defines the structural validation result contract between modules
