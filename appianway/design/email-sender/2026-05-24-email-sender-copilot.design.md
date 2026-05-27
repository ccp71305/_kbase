# Email-Sender Module — Design Document

> **Module:** `email-sender`  
> **Generated:** 2026-05-24  
> **Artifact:** `com.inttra.mercury.email:email-sender:1.0-SNAPSHOT`  
> **Java Version:** 17 | **Framework:** Dropwizard 4.x + Guice 7.x + Thymeleaf 3.x

---

## 1. Executive Summary

The **Email-Sender** module is the notification delivery engine of AppianWay. It consumes email requests from an SQS queue, resolves Thymeleaf-based templates with contextual data, and sends formatted emails via AWS SES. It includes rate limiting to prevent overwhelming SES quotas and supports multiple template resolvers for extensibility.

---

## 2. Role in the Pipeline

```mermaid
flowchart LR
    EP["Error-Processor"] -->|"MetaData + recipient"| EQ["SQS Email Queue"]
    EQ --> ES["🔷 EMAIL-SENDER"]
    ES -->|"Load content"| S3["S3 Workspace"]
    ES -->|"Send email"| SES["AWS SES"]
    ES -->|"Events"| EVT["SNS Event Store"]
    
    style ES fill:#4a90d9,color:#fff
```

---

## 3. High-Level Architecture

```mermaid
graph TB
    subgraph "Email-Sender Service"
        APP[EmailSenderApplication]
        EST[EmailSenderTask]
        
        subgraph "Services"
            MS[MailingService]
            CLS[ContentLoaderService]
            RLS[RateLimiterService]
        end
        
        subgraph "Template Resolution"
            MTR[MailTemplateResolver]
            ESR[ErrorSubjectResolver]
            EBR[ErrorBodyResolver]
            PPR[PropertyPlaceholdersResolver]
            TE[Thymeleaf TemplateEngine]
        end
        
        subgraph "Models"
            MC[MailContext]
            MT[MailTemplate]
            MD[MailDetails]
        end
    end
    
    APP --> EST
    EST --> CLS
    EST --> RLS
    EST --> MS
    MS --> MTR --> ESR & EBR
    MS --> PPR --> TE
    MS --> MD
```

---

## 4. Class Diagram

```mermaid
classDiagram
    class EmailSenderTask {
        -mailingService: MailingService
        -contentLoaderService: ContentLoaderService
        -rateLimiterService: RateLimiterService
        -eventLogger: EventLogger
        +process(Message, String)
        -buildMailContext(MetaData, MetaData, Map): MailContext
    }

    class MailingService {
        -amazonSES: AmazonSimpleEmailService
        -templateResolver: MailTemplateResolver
        -placeholdersResolver: PropertyPlaceholdersResolver
        +sendMail(MailContext): String
        -resolveTemplate(MailTemplate, MailContext): Message
        -createEmailRequest(MailDetails): SendEmailRequest
    }

    class ContentLoaderService {
        -workspaceService: WorkspaceService
        +getOriginalEvent(MetaData): MetaData
        +getContents(MetaData): Map
    }

    class RateLimiterService {
        -rateLimiter: RateLimiter
        +filterByRate(): boolean
    }

    class MailTemplateResolver {
        -subjectResolvers: List~TemplateResolver~
        -bodyResolvers: List~TemplateResolver~
        +apply(MailContext): MailTemplate
    }

    class TemplateResolver {
        <<interface>>
        +match(MailContext): boolean
        +resolve(MailContext): String
    }

    class PropertyPlaceholdersResolver {
        -templateEngine: TemplateEngine
        +resolvePlaceholders(MailTemplate, Map): Message
    }

    class MailContext {
        -originalMetaData: MetaData
        -recipient: String
        -contents: Map
    }

    class MailTemplate {
        -subjectTemplate: String
        -bodyTemplate: String
    }

    EmailSenderTask --> MailingService
    EmailSenderTask --> ContentLoaderService
    EmailSenderTask --> RateLimiterService
    MailingService --> MailTemplateResolver
    MailingService --> PropertyPlaceholdersResolver
    MailTemplateResolver --> TemplateResolver
    TemplateResolver <|.. ErrorSubjectResolver
    TemplateResolver <|.. ErrorBodyResolver
```

---

## 5. Data Flow Diagram

```mermaid
sequenceDiagram
    participant SQS as SQS Email Queue
    participant EST as EmailSenderTask
    participant CLS as ContentLoaderService
    participant S3 as S3 Workspace
    participant RLS as RateLimiterService
    participant MS as MailingService
    participant MTR as TemplateResolver
    participant TH as Thymeleaf Engine
    participant SES as AWS SES
    participant SNS as SNS Events

    SQS->>EST: receiveMessage (MetaData JSON)
    EST->>CLS: getOriginalEvent(metaData)
    CLS->>S3: getContent(bucket, fileName)
    S3-->>CLS: original MetaData JSON
    CLS-->>EST: originalMetaData
    EST->>CLS: getContents(metaData)
    CLS->>S3: getContent(bucket, contentFile)
    S3-->>CLS: Annotations JSON
    CLS-->>EST: contents map
    EST->>EST: buildMailContext(originalMetaData, metaData, contents)
    EST->>RLS: filterByRate()
    alt Rate limit OK
        RLS-->>EST: true
        EST->>MS: sendMail(mailContext)
        MS->>MTR: resolveTemplate(mailContext)
        MTR-->>MS: MailTemplate (subject + body)
        MS->>TH: process(template, placeholders)
        TH-->>MS: resolved HTML/text
        MS->>SES: sendEmail(from, to, subject, body)
        SES-->>MS: messageId
        MS-->>EST: messageId
        EST->>SNS: logCloseRunEvent(SUCCESS, messageId)
    else Rate limited
        RLS-->>EST: false
        EST->>SNS: logCloseRunEvent(DROPPED)
    end
```

---

## 6. Template Resolution Chain

```mermaid
flowchart TD
    MC[MailContext] --> MTR{MailTemplateResolver}
    MTR -->|"Subject"| SR[Subject Resolvers Chain]
    MTR -->|"Body"| BR[Body Resolvers Chain]
    SR --> ESR{ErrorSubjectResolver.match?}
    ESR -->|Yes| ST["templates/subject/non_application_error_subject.txt"]
    BR --> EBR{ErrorBodyResolver.match?}
    EBR -->|Yes| BT["templates/body/non_application_error_body.txt"]
    ST & BT --> PPR[PropertyPlaceholdersResolver]
    PPR --> TE[Thymeleaf Engine - TEXT mode]
    TE --> MSG[AWS SES Message]
```

### Template Placeholders

| Placeholder | Source | Example |
|------------|--------|---------|
| `[(${metaData.component})]` | Original MetaData | `transformer` |
| `[(${metaData.projections.contextCode})]` | Projections | `requestBooking` |
| `[(${gmtDateTime})]` | System clock | `Saturday, May 24, 2026 at 14:30 GMT` |
| `[(${environment})]` | Configuration | `production` |
| `[(${content.Annotations})]` | Error annotations | Error code list |

---

## 7. Configuration Details

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `componentName` | String | `email-sender` | Service identity |
| `environment` | String | — | Deployment environment name |
| `mailConfig.senderEmailAddress` | String | — | From address (e.g., `"INTTRA" <no-reply@...>`) |
| `mailConfig.replyToEmailAddress` | String | — | Reply-to address |
| `mailConfig.rateLimitInSeconds` | int | `120` | Rate limit interval |
| `sqsPickupConfig.queueUrl` | String | — | Email queue URL |
| `sqsPickupConfig.waitTimeSeconds` | int | `20` | Long poll |
| `sqsPickupConfig.maxNumberOfMessages` | int | `1` | Batch size |
| `snsEventConfig.topicArn` | String | — | Event topic |
| `s3WorkspaceConfig.bucket` | String | — | Content bucket |
| `sqsErrorConfig.queueUrl` | String | — | Error queue |

---

## 8. Rate Limiting

The `RateLimiterService` uses Guava's `RateLimiter`:

- **Formula:** `permits/sec = 1 / rateLimitInSeconds`
- **Default:** 1 email per 120 seconds = 0.5 emails/minute
- **Behavior:** Non-blocking `tryAcquire()` — drops if exceeded
- **Scope:** Singleton per instance (not distributed)

---

## 9. Error Handling

| Exception | Error Code | Recovery |
|-----------|-----------|----------|
| `TemplateNotFoundException` | Template resolution failure | Non-recoverable |
| `TemplateResolveException` | Thymeleaf processing error | Non-recoverable |
| `EmailNotSendException` | SES delivery failure | Recoverable |
| `SdkClientException` | AWS connectivity issue | Recoverable |

---

## 10. Key Maven Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `mercury-shared` | 1.0 | Framework, events, workspace |
| `thymeleaf` | 3.0.7 | Template engine |
| `aws-java-sdk-ses` | 1.12.720 | Email delivery |
| `dropwizard-core` | 4.0.16 | Application framework |
| `guice` | 7.0.0 | DI container |
| `guava` | 33.1.0-jre | RateLimiter |
