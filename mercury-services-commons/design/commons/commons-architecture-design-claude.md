# commons — Architecture & Design Reference

> **Document generated:** 2026-05-04  
> **Module version:** 1.0.23-SNAPSHOT  
> **Author analysis by:** Claude (Principal Engineer perspective)  
> **Scope:** Full architectural, design, API, and technology analysis

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Module Position in the System](#2-module-position-in-the-system)
3. [Technology Stack & Maven Dependencies](#3-technology-stack--maven-dependencies)
4. [Package & Class Taxonomy](#4-package--class-taxonomy)
5. [Domain-by-Domain Architecture](#5-domain-by-domain-architecture)
   - 5.1 [Server Bootstrap — InttraServer](#51-server-bootstrap--intraserver)
   - 5.2 [Authentication & Authorization](#52-authentication--authorization)
   - 5.3 [Database Layer (MyBatis + Aurora)](#53-database-layer-mybatis--aurora)
   - 5.4 [Caching Layer](#54-caching-layer)
   - 5.5 [HTTP Clients](#55-http-clients)
   - 5.6 [Excel / CSV Processing](#56-excel--csv-processing)
   - 5.7 [Observability — Logging & Metrics](#57-observability--logging--metrics)
   - 5.8 [Configuration Infrastructure](#58-configuration-infrastructure)
   - 5.9 [Utilities Catalog](#59-utilities-catalog)
   - 5.10 [Elasticsearch Integration](#510-elasticsearch-integration)
   - 5.11 [Exception & Error Handling Framework](#511-exception--error-handling-framework)
   - 5.12 [Internationalization](#512-internationalization)
6. [Key Data Flows](#6-key-data-flows)
7. [Dependency Injection Architecture](#7-dependency-injection-architecture)
8. [Areas of Excellence](#8-areas-of-excellence)
9. [Areas for Improvement](#9-areas-for-improvement)

---

## 1. Executive Summary

`commons` is the **shared platform library** for all Mercury microservices. It is the largest and oldest of the three modules — approximately 350+ Java classes across 30+ packages. It plays three distinct roles simultaneously:

1. **Platform bootstrap**: `InttraServer` provides an opinionated Dropwizard application base — security, health checks, monitoring, Guice DI, SSM config resolution.
2. **Legacy cloud utilities**: pre-SDK-abstraction email, DynamoDB, Elasticsearch, and parameter-store code that predates `cloud-sdk-api`.
3. **Cross-cutting concerns**: logging, metrics, caching, CORS, authentication, exception mapping, Excel/CSV processing, and ~20 utility classes.

```
┌──────────────────────────────────────────────────────────────────┐
│                    commons                                       │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  InttraServer     │  │ Auth/OAuth   │  │  Database        │  │
│  │  (Dropwizard base)│  │ (JWT/OAuth2) │  │  (MyBatis/Aurora)│  │
│  └──────────────────┘  └──────────────┘  └──────────────────┘  │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Caching         │  │  Excel/CSV   │  │  Observability   │  │
│  │  (Guava + Guice) │  │  (Apache POI)│  │  (DW + Datadog)  │  │
│  └──────────────────┘  └──────────────┘  └──────────────────┘  │
│                                                                  │
│  depends on: cloud-sdk-api + cloud-sdk-aws                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Position in the System

```
mercury-services-commons (parent POM v1.0)
├── cloud-sdk-api               ← interfaces only
├── cloud-sdk-aws               ← AWS implementations
└── commons                     ← YOU ARE HERE
      ├── depends on: cloud-sdk-api
      ├── depends on: cloud-sdk-aws
      └── consumed by: all Mercury microservices
```

**Downstream usage:**
Every Mercury microservice adds `commons` as a dependency and extends `InttraServer` to get the full platform stack. This makes `commons` the highest-impact module — a change here affects every service.

---

## 3. Technology Stack & Maven Dependencies

| Technology | Artifact | Version | Role |
|---|---|---|---|
| Java | JDK | 17 | Language |
| Dropwizard | `dropwizard-core` | 4.0.16 | REST framework, lifecycle, config |
| Dropwizard DB | `dropwizard-db` | 4.0.16 | Connection pool (HikariCP) |
| Dropwizard Auth | `dropwizard-auth` | 4.0.16 | Auth filters & annotations |
| Dropwizard Forms | `dropwizard-forms` | 4.0.16 | Multipart form support |
| Dropwizard Client | `dropwizard-client` | 4.0.16 | Jersey HTTP client |
| Dropwizard Assets | `dropwizard-assets` | 4.0.16 | Static asset serving |
| Dropwizard Logging | `dropwizard-logging` | 4.0.16 | Logback + MDC |
| MyBatis | `mybatis` | 3.5.13 | SQL mapping framework |
| MyBatis Guice | `mybatis-guice` | 4.0.0 | Guice integration for MyBatis |
| MySQL Connector | `mysql-connector-java` | 8.0.16 | MySQL/Aurora JDBC driver |
| Guice | `guice` | 7.0.0 | Dependency injection |
| Guice Servlet | `guice-servlet` | 7.0.0 | Servlet-aware DI |
| Guice Multibindings | `guice-multibindings` | 4.2.3 | Set/Map bindings |
| Dropwizard Metrics Datadog | `dropwizard-metrics-datadog` | 4.0.2 | Datadog reporter |
| Metrics Core | `metrics-core` | 4.2.30 | Dropwizard Metrics |
| Apache POI | `poi` + `poi-ooxml` | 5.3.0 | Excel read/write |
| Jackson CSV | `jackson-dataformat-csv` | 2.19.2 | CSV serialization |
| Jackson Joda | `jackson-datatype-joda` | 2.19.2 | Joda Time JSON |
| Spring Security Crypto | `spring-security-crypto` | 4.2.3.RELEASE | BCrypt, AES encryption |
| Jersey JAXB | `jersey-media-jaxb` | 3.1.3 | JAXB XML marshaling |
| JAXB API | `jakarta.xml.bind-api` | 4.0.1 | XML binding (Jakarta) |
| JAXB Runtime | `jaxb-runtime` | 4.0.4 | JAXB implementation |
| JSoup | `jsoup` | 1.17.2 | HTML parsing/sanitization |
| Gson | `gson` | 2.10.1 | JSON (for Elasticsearch) |
| Jest | `jest` | 5.3.3 | Elasticsearch client |
| AWS Signing Interceptor | `aws-signing-request-interceptor` | 0.0.22 | ES AWS auth |
| Apache HttpClient 5 | `httpclient5` | 5.4.4 | HTTP transport |
| Dropwizard Metrics Datadog | `dropwizard-metrics-datadog` | 4.0.2 | Custom Datadog reporter |
| Commons Lang3 | `commons-lang3` | 3.13.0 | String/collection utilities |
| Commons Text | `commons-text` | 1.10.0 | String templates |
| cloud-sdk-api | local | ${dependency.version} | Cloud API interfaces |
| cloud-sdk-aws | local | ${dependency.version} | AWS implementations |
| JUnit 4 | `junit` | 4.13.2 | Legacy test runner |
| JUnit 5 | `junit-jupiter` | 5.12.2 | Modern test runner |
| Mockito | `mockito-core/junit-jupiter` | 5.10.0 / 5.17.0 | Mocking |
| AssertJ | `assertj-core` | 3.27.2 | Fluent assertions |

---

## 4. Package & Class Taxonomy

```
com.inttra.mercury
│
├── InttraServer                         Dropwizard base server (master bootstrap)
├── PostSetupHook                        Server init hook
├── ServicePath                          Path constants
└── ServletContextListener               Web listener

com.inttra.mercury.auth
  ├── MercuryAuthorizer                  JAX-RS @RolesAllowed authorizer
  ├── OAuthProvider                      OAuth provider abstraction
  ├── models/
  │   ├── Address, Client, Token, User   Core auth entities
  │   ├── InttraPrincipal                Principal (wraps User + permissions)
  │   └── UserAttribute, UserExport      Extended user models
  └── ptui/                              Portal UI models
      ├── CompanyAddress, Content
      ├── PermissionScope, ResourcePermission
      ├── ResponseContent, UserAccess, UserDetails

com.inttra.mercury.base
  └── IntegrationTest                   @Tag annotation for IT tests

com.inttra.mercury.bean
  ├── UniqueElements                     @Constraint for unique list elements
  └── UniqueKeyElements                  @Constraint for unique key elements

com.inttra.mercury.cache
  ├── ServiceCache                       Cache abstraction
  ├── GuavaCacheMetrics + CacheMetrics   Metrics integration
  ├── LocalCacheInterceptor              AOP method caching
  ├── LocalCacheModule                   Guice module
  ├── LocalCacheProvider                 Cache provider
  ├── MethodInvocationKeyWrapper         Cache key from method+args
  └── WithLocalCache                     @annotation for cacheable methods

com.inttra.mercury.client
  ├── AuthClient                         Auth service client
  ├── ExternalServiceClient              Generic external HTTP client
  ├── ExternalServiceSSLClient           SSL-enabled external client
  └── ServiceClient                      Internal Mercury service client

com.inttra.mercury.condition
  ├── Condition                          Condition entity
  ├── ConditionEvaluator                 Evaluates conditions
  ├── ConditionOperator                  Operator enum (EQ, NEQ, GT, LT, …)
  └── Operator                           Operator interface

com.inttra.mercury.config
  ├── ApplicationConfiguration           Dropwizard config base class
  ├── ChainingConfigTransformer          Chains multiple config transforms
  ├── ConfigProcessingServerCommand      Custom server command with config transforms
  ├── CustomConfigurationFactoryFactory  Custom Dropwizard config factory
  ├── DatabaseAppConfig                  DB connection pool config
  ├── ElasticSearchServiceConfig         ES endpoint + auth config
  ├── MailConfig                         SMTP/SES email config
  ├── PartnerDetail                      Partner-specific config
  ├── SecurityResources                  Security endpoints config
  └── TrimConfigCommentsTransform        Strips YAML comments before parse

com.inttra.mercury.controller
  ├── ExceptionMapperHelper              Maps exceptions to HTTP responses
  ├── MercuryDefaultExceptionMapper      Default JAX-RS ExceptionMapper
  ├── MercuryWebApplicationExceptionMapper  WebApplicationException mapper
  └── StandardExceptionMappers           Registers all standard mappers

com.inttra.mercury.converter
  ├── JsonToContractTypeHandler          MyBatis TypeHandler for JSON columns
  └── MultiFormatLocalDateTimeDeserializer  Jackson deserializer for date strings

com.inttra.mercury.database
  ├── AuroraDataSourceProvider           HikariCP datasource for Aurora
  ├── DatabaseUtils                      Schema/query utilities
  ├── MyBatisConfigModule                MyBatis Guice module (base)
  ├── MyCustomBatisModule                Custom MyBatis bindings
  ├── interceptor/
  │   └── AuroraDBLoadBalancingInterceptor  Routes reads to replicas
  └── mapper/
      └── DatabaseHealthCheckMapper      MyBatis mapper for health check query

com.inttra.mercury.elasticsearch
  ├── JestClientBuilder                  Builds Jest ES client (with AWS signing)
  └── JestClientRetryHandler             Exponential-backoff retry

com.inttra.mercury.excel
  ├── Cell, Column, ExcelRow             Cell/row model
  ├── ExcelReader, ExcelWriter           Apache POI read/write
  ├── ExcelSheetHandler                  Sheet event handler
  ├── ExcelSheetHeaderHelper             Header resolution
  ├── GroupHeader, GroupHeaders          Grouped header support
  ├── ResultSheet                        Result representation
  ├── Constants                          Excel format constants
  ├── ExcelConfiguration                 Config for Excel processing
  ├── ExcelModule                        Guice module
  ├── CSVStringBeanSerializer            Custom CSV field serializer
  ├── CSVWriter                          Jackson CSV writer wrapper
  ├── InttraTempFileCreationStrategy     Custom temp file creation
  └── TempFilesPurgeProcessor            Background temp file cleanup

com.inttra.mercury.exception
  ├── MercurySecurityException           Security-related exception
  ├── MercuryUuidException               UUID parse/validation exception
  ├── ExceptionResponse                  JAX-RS error response model
  └── ServiceExceptionMapper             Maps service exceptions to HTTP

com.inttra.mercury.filters
  ├── CORSCustomFilter                   CORS response headers
  ├── JerseyClientRequestLoggingFilter   Outbound request logging
  ├── MercuryRequestLoggingFilter        Inbound request logging
  └── MercuryResponseLoggingFilter       Inbound response logging

com.inttra.mercury.health
  ├── AppHealthCheck                     Application-level health check
  └── DatabaseHealthCheck                DB connectivity health check

com.inttra.mercury.listener
  ├── FixedDelayListenerManager          Manages scheduled background listeners
  └── Listener                           Listener lifecycle interface

com.inttra.mercury.log
  ├── ClientLogger                       Log outbound HTTP calls
  ├── ContainerLogger                    Log container events
  ├── FilterLogger                       Log filter chain events
  ├── JerseyClientRequestLogger          Jersey client request logging
  ├── MDC_TAG                            MDC tag constants
  ├── MercuryRequestConsoleLogAppender   Custom Logback appender
  └── MercuryServiceRequestLogger        Structured request log

com.inttra.mercury.metrics
  └── ObservabilityMetrics               Dropwizard Metrics registry wrapper

com.inttra.mercury.util
  ├── AWSUtil                            AWS utility (region, credential helpers)
  ├── CORSUtil                           CORS origin validation
  ├── DateUtil                           Date formatting/parsing
  ├── EncryptionUtil                     AES/BCrypt encryption helpers
  ├── FileNameUtil                       File name sanitization
  ├── FileUtil                           File I/O helpers
  ├── GraphQLUtil                        GraphQL query helpers
  ├── GUIDUtil                           UUID generation
  ├── JsonUtil                           Jackson ObjectMapper wrapper
  ├── KeyStoreUtil                       Java KeyStore helpers
  ├── LocalDateTimeDeserializer          Jackson deserializer
  ├── LocalDateTimeSerializer            Jackson serializer
  ├── NameUtil                           Name formatting
  ├── NumberUtil                         Number parsing/formatting
  ├── ShutdownUtil                       JVM shutdown hook helpers
  └── StringUtil                         String manipulation
```

---

## 5. Domain-by-Domain Architecture

### 5.1 Server Bootstrap — InttraServer

`InttraServer` is the most important class in `commons`. Every Mercury service extends it to get the full platform stack automatically.

#### Class Architecture

```
io.dropwizard.Application<C extends ApplicationConfiguration>
       │
       ▼
InttraServer<C extends ApplicationConfiguration>
       │
       ├── Guice Injector construction
       │     └── installModules(List<Module>)
       │
       ├── Security setup
       │     ├── DoS protection filter
       │     ├── CORS filter (CORSCustomFilter)
       │     └── Auth filter (if auth enabled)
       │
       ├── Health checks
       │     ├── AppHealthCheck
       │     └── DatabaseHealthCheck
       │
       ├── Observability
       │     ├── Datadog metrics reporter
       │     └── Request/response logging filters
       │
       ├── Resource registration
       │     └── for each JAX-RS resource: environment.jersey().register(resource)
       │
       ├── Config transformation pipeline
       │     └── ChainingConfigTransformer
       │           └── SsmParameterTransformation (${awsps:...} resolution)
       │
       └── Exception mapper registration
             └── StandardExceptionMappers.register(environment)
```

#### Server Bootstrap Sequence

```
Service.main(args)
  │
  ▼ InttraServer.run(config, environment)
  │
  ├─ 1. Resolve config placeholders via SSM
  │       ${awsps:/mercury/prod/db-password} → "actualPassword"
  │
  ├─ 2. Build Guice injector
  │       injector = Guice.createInjector(
  │         new MyBatisConfigModule(config),
  │         new LocalCacheModule(),
  │         new ExcelModule(),
  │         ...service-specific modules...
  │       )
  │
  ├─ 3. Configure Jersey
  │       environment.jersey().register(injector.getInstance(MyResource.class))
  │
  ├─ 4. Configure filters
  │       environment.servlets().addFilter("cors", corsFilter)
  │       environment.servlets().addFilter("dos", dosFilter)
  │
  ├─ 5. Register health checks
  │       environment.healthChecks().register("database", dbCheck)
  │
  ├─ 6. Register metrics reporter
  │       DatadogReporter.forRegistry(metrics)
  │         .withHost(config.getDatadogHost())
  │         .build()
  │         .start(60, TimeUnit.SECONDS)
  │
  └─ 7. Start Jetty → service is live
```

#### ConfigProcessingServerCommand

The server command extends Dropwizard's `ServerCommand` to inject config transforms before the server starts. This is how SSM parameter store values are resolved into the config:

```
ConfigProcessingServerCommand
  │
  └── run(config, environment)
        │
        ├── ChainingConfigTransformer.transform(rawYaml)
        │     ├── TrimConfigCommentsTransform   → strips YAML #comments
        │     └── SsmParameterTransformation    → resolves ${awsps:...}
        │
        └── super.run(resolvedConfig, environment)
```

---

### 5.2 Authentication & Authorization

#### InttraPrincipal — The Identity Model

```
InttraPrincipal implements java.security.Principal
  │
  ├── User user                  Core user entity
  ├── String token               JWT bearer token
  ├── List<String> roles         Assigned roles
  ├── List<Permission> perms     Resource permissions
  └── Map<String, String> attrs  User attributes
```

#### Authentication Flow

```
HTTP Request: GET /api/shipments
  Header: Authorization: Bearer <jwt-token>
  │
  ▼ Dropwizard Auth Filter
  │
  ▼ OAuthProvider.authenticate(credentials)
  │   ├── validate JWT signature
  │   ├── check token expiry
  │   └── load User + Permissions from auth service
  │
  ▼ inject @Auth InttraPrincipal principal into resource method
  │
  ▼ MercuryAuthorizer.authorize(principal, role)
  │   └── principal.getRoles().contains(role)
  │
  ▼ Resource method executes
```

#### User Model

```
User
  ├── id              String (UUID)
  ├── email           String
  ├── firstName       String
  ├── lastName        String
  ├── company         String
  ├── locale          String
  ├── status          UserStatus enum
  └── userAttributes  List<UserAttribute>

Client (OAuth Application)
  ├── clientId        String
  ├── clientSecret    String
  ├── redirectUri     String
  └── scopes          List<String>

Token
  ├── accessToken     String (JWT)
  ├── tokenType       String ("Bearer")
  ├── expiresIn       long (seconds)
  └── refreshToken    String
```

#### PTUI (Portal UI) Models

```
UserDetails
  ├── userId           String
  ├── email            String
  ├── firstName/LastName
  ├── companyName      String
  └── userAccess       UserAccess

UserAccess
  ├── permissionScopes List<PermissionScope>
  └── resourcePerms    List<ResourcePermission>

ResourcePermission
  ├── resource         String
  └── permissions      List<String>
```

---

### 5.3 Database Layer (MyBatis + Aurora)

#### Architecture Overview

```
ApplicationConfiguration
  └── DatabaseAppConfig         HikariCP pool config
        ├── driverClass         "com.mysql.cj.jdbc.Driver"
        ├── url                 "jdbc:mysql://aurora-cluster:3306/mercury"
        ├── user, password
        ├── maxSize             pool max connections
        └── minIdle             pool min idle

MyBatisConfigModule (Guice)
  │
  ├── binds DataSource → AuroraDataSourceProvider
  ├── installs MyBatisModule (mybatis-guice)
  └── binds all @Mapper interfaces
```

#### Aurora Load Balancing

```
AuroraDBLoadBalancingInterceptor  implements Interceptor (MyBatis)
  │
  ├── @Before: SELECT queries
  │     └── route to READ REPLICA endpoint
  │
  └── @Before: INSERT/UPDATE/DELETE
        └── route to PRIMARY endpoint
```

**Routing logic:**
```
READONLY_KEYWORDS = ["SELECT", "SHOW", "DESCRIBE", "EXPLAIN"]
│
├── if statement.startsWith(READONLY_KEYWORD)
│     → switch DataSource to replica
│
└── else
      → use primary DataSource
```

#### Health Check

```
DatabaseHealthCheck extends HealthCheck
  │
  └── check()
        │
        └── DatabaseHealthCheckMapper.ping()
              └── SELECT 1
                    ├── success → HealthCheck.Result.healthy()
                    └── failure → HealthCheck.Result.unhealthy(e)
```

#### JSON Column Support

```
JsonToContractTypeHandler implements TypeHandler<T>
  │
  ├── setParameter(): Java object → JSON string → VARCHAR column
  └── getResult():   VARCHAR column → JSON string → Java object
        └── uses JsonUtil.fromJson(json, T.class)
```

---

### 5.4 Caching Layer

The caching layer provides method-level caching via AOP (Guice interceptor).

#### Architecture

```
@WithLocalCache                   (annotation on service method)
       │
       ▼
LocalCacheInterceptor             (Guice AOP interceptor)
       │
       ├── compute cache key from method + args
       │     └── MethodInvocationKeyWrapper.key(method, args)
       │
       ├── check LocalCacheProvider.get(key)
       │     ├── HIT  → return cached value
       │     └── MISS → proceed with method invocation
       │
       ├── store result in cache
       │
       └── record cache metrics (hit/miss counts)

LocalCacheProvider
  └── Guava LoadingCache<String, Object>
        ├── maximumSize: config.maxSize (default 1000)
        └── expireAfterWrite: config.ttl (default 60s)
```

#### Cache Key Generation

```
MethodInvocationKeyWrapper
  │
  └── key(method, args)
        └── method.getDeclaringClass().getName()
              + "#" + method.getName()
              + "(" + Arrays.toString(args) + ")"
```

#### Cache Metrics

```
GuavaCacheMetrics
  ├── hitCount      Counter (incremented on cache hit)
  ├── missCount     Counter (incremented on cache miss)
  ├── hitRate       Gauge (hitCount / (hitCount + missCount))
  └── evictionCount Counter (Guava eviction events)
```

#### Usage Pattern

```java
@Singleton
public class ShipmentService {

    @WithLocalCache(ttl = 300, maxSize = 500)
    public Shipment getShipment(String shipmentId) {
        return repository.findById(shipmentId);  // only called on cache miss
    }
}
```

---

### 5.5 HTTP Clients

#### Client Hierarchy

```
ServiceClient                      (internal Mercury-to-Mercury calls)
  └── Jersey Client with auth token injection

ExternalServiceClient              (outbound to third parties)
  └── Jersey Client with timeout configuration

ExternalServiceSSLClient           (HTTPS to third parties with custom cert)
  └── ExternalServiceClient + custom SSLContext
        └── KeyStoreUtil.loadKeyStore(config)

AuthClient                         (calls auth service)
  └── ServiceClient configured for auth endpoints
```

#### HTTP Client Configuration

```
Dropwizard JerseyClientBuilder
  ├── connectionTimeout: 2s (default)
  ├── readTimeout:       5s (default)
  ├── maxConnections:    10 (default)
  └── userAgent:         "mercury-service/1.0"
```

#### Request Logging

```
HTTP Request → JerseyClientRequestLoggingFilter
  │
  ├── log: method, URI, headers (redacting Authorization)
  ├── log: request body (if JSON/text, truncated at 1KB)
  │
  ▼ actual HTTP call
  │
  ├── log: status code, response time
  └── log: response body (if JSON/text, truncated at 1KB)
```

---

### 5.6 Excel / CSV Processing

#### Excel Architecture

```
ExcelReader
  │
  ├── read(InputStream, ExcelConfiguration) → List<ExcelRow>
  │     │
  │     ├── Apache POI SAX event-based parsing (XSSF)
  │     │     └── ExcelSheetHandler handles row/cell events
  │     │
  │     ├── ExcelSheetHeaderHelper resolves column → header mapping
  │     │
  │     └── GroupHeaders handles multi-level merged headers
  │
  └── supports: .xlsx (OOXML), streaming SAX for large files

ExcelWriter
  │
  └── write(List<T>, ExcelConfiguration, OutputStream)
        │
        ├── creates SXSSFWorkbook (streaming for large output)
        ├── writes header row with Column metadata
        └── writes data rows via reflection on T

Column
  ├── name          String (display name)
  ├── field         String (Java field path)
  ├── width         int (column width in characters)
  └── format        String (number format pattern)

GroupHeader
  ├── title         String
  ├── span          int (columns spanned)
  └── children      List<Column>
```

#### CSV Architecture

```
CSVWriter
  │
  └── write(List<T>, Class<T>, OutputStream)
        │
        └── Jackson CsvMapper
              ├── CsvSchema from @JsonProperty annotations on T
              └── ObjectWriter with schema → CSV bytes

CSVStringBeanSerializer
  └── custom serializer for fields needing special CSV formatting
```

#### Temp File Management

```
InttraTempFileCreationStrategy
  └── createTempFile(prefix, suffix) → Path
        └── creates in OS temp dir with unique name

TempFilesPurgeProcessor
  └── @Scheduled (FixedDelayListenerManager): every 30 min
        └── delete temp files older than 1 hour
```

---

### 5.7 Observability — Logging & Metrics

#### Logging Architecture

```
Logback (via Dropwizard)
  │
  ├── MercuryRequestConsoleLogAppender   structured JSON request logs
  │     └── appends to STDOUT in JSON format
  │
  ├── MercuryServiceRequestLogger        request/response audit trail
  │     ├── MDC: REQUEST_ID (UUID per request)
  │     ├── MDC: USER_ID (from InttraPrincipal)
  │     ├── MDC: SERVICE_NAME
  │     └── MDC: CORRELATION_ID (from X-Correlation-ID header)
  │
  └── FilterLogger                       filter chain diagnostics

MDC_TAG constants:
  REQUEST_ID, USER_ID, SERVICE_NAME, CORRELATION_ID,
  WORKFLOW_ID, COMPONENT, OPERATION
```

#### Metrics Architecture

```
Dropwizard MetricRegistry
  │
  ├── ObservabilityMetrics (wrapper)
  │     ├── counter(name)     → Counter
  │     ├── timer(name)       → Timer
  │     ├── histogram(name)   → Histogram
  │     └── gauge(name, fn)   → Gauge<T>
  │
  └── DatadogReporter (from dropwizard-metrics-datadog)
        ├── host: config.getDatadogHost()
        ├── port: 8125 (DogStatsD)
        ├── prefix: "mercury.{service-name}"
        └── flushInterval: 60s
```

#### Request Logging Filters

```
HTTP Request
  │
  ▼ MercuryRequestLoggingFilter (ContainerRequestFilter)
  │   ├── generate REQUEST_ID → MDC
  │   ├── extract X-Correlation-ID → MDC
  │   ├── log: method, path, query params, user-agent
  │   └── start timer
  │
  ▼ Resource method
  │
  ▼ MercuryResponseLoggingFilter (ContainerResponseFilter)
      ├── log: status code, response time
      └── clear MDC
```

---

### 5.8 Configuration Infrastructure

#### ApplicationConfiguration Class Hierarchy

```
io.dropwizard.core.Configuration
       │
       ▼
ApplicationConfiguration
  ├── DatabaseAppConfig   databaseConfig
  ├── ElasticSearchServiceConfig   elasticSearchConfig
  ├── MailConfig          mailConfig
  ├── SecurityResources   securityResources
  ├── Map<String,PartnerDetail> partners
  └── (service-specific config fields in subclasses)
```

#### Config Transformation Pipeline

```
Raw YAML (from file / environment):
  ───────────────────────────
  database:
    url: ${awsps:/mercury/prod/db-url}
    password: ${awsps:/mercury/prod/db-password}
  ───────────────────────────
              │
              ▼
  TrimConfigCommentsTransform
    removes: # inline comments
    output: clean YAML text
              │
              ▼
  SsmParameterTransformation
    ${awsps:/mercury/prod/db-url}      → jdbc:mysql://aurora:3306/mercury
    ${awsps:/mercury/prod/db-password} → s3cr3tP@ssw0rd
              │
              ▼
  Resolved YAML:
  ───────────────────────────
  database:
    url: jdbc:mysql://aurora:3306/mercury
    password: s3cr3tP@ssw0rd
  ───────────────────────────
              │
              ▼
  Dropwizard deserialises → ApplicationConfiguration
```

#### DatabaseAppConfig

```
DatabaseAppConfig (extends DataSourceFactory)
  ├── driverClass    "com.mysql.cj.jdbc.Driver"
  ├── url            JDBC URL (from SSM)
  ├── user           DB username (from SSM)
  ├── password       DB password (from SSM, SECURE_STRING)
  ├── minSize        minimum pool connections (default 2)
  ├── maxSize        maximum pool connections (default 10)
  ├── validationQuery "SELECT 1"
  └── autoCommitByDefault false
```

---

### 5.9 Utilities Catalog

| Class | Key Methods | Purpose |
|---|---|---|
| `AWSUtil` | `getDefaultRegion()`, `buildCredentials()` | AWS helper shortcuts |
| `CORSUtil` | `isAllowedOrigin(origin, allowedOrigins)` | Origin whitelist check |
| `DateUtil` | `format(date, pattern)`, `parse(str, pattern)` | Date formatting |
| `EncryptionUtil` | `encrypt(text)`, `decrypt(ciphertext)`, `bcrypt(password)` | AES + BCrypt |
| `FileNameUtil` | `sanitize(filename)`, `getExtension(filename)` | Safe file names |
| `FileUtil` | `readBytes(path)`, `writeBytes(path, bytes)` | File I/O |
| `GraphQLUtil` | `parseQuery(gql)`, `extractFields(query)` | GraphQL query parsing |
| `GUIDUtil` | `generate()` → UUID string | UUID generation |
| `JsonUtil` | `toJson(obj)`, `fromJson(json, Class<T>)` | Jackson wrappers |
| `KeyStoreUtil` | `loadKeyStore(path, password)` | JKS/PKCS12 loading |
| `NameUtil` | `capitalize(name)`, `formatDisplayName(first, last)` | Name formatting |
| `NumberUtil` | `parseOrNull(str)`, `safeDivide(a, b)` | Safe arithmetic |
| `ShutdownUtil` | `addHook(Runnable)` | JVM shutdown hooks |
| `StringUtil` | `truncate(s, n)`, `blankToNull(s)`, `padLeft(s, n)` | String manipulation |

---

### 5.10 Elasticsearch Integration

```
JestClientBuilder (commons — legacy)
  │
  └── build(ElasticSearchServiceConfig) → JestClient
        │
        ├── HttpClientConfig.Builder
        │     ├── addServer(config.getEndpoint())
        │     ├── connTimeout(config.getTimeout())
        │     └── readTimeout(config.getTimeout())
        │
        ├── AWS SigV4 signing interceptor
        │     └── AWSSigningRequestInterceptor(config.getRegion())
        │
        └── JestClientRetryHandler
              └── exponential backoff: 3 retries, 2^n * 100ms

ElasticSearchServiceConfig (in commons config)
  ├── endpoint      String ("https://es-cluster.us-east-1.es.amazonaws.com")
  ├── region        String ("us-east-1")
  ├── timeout       int (ms, default 5000)
  ├── maxRetries    int (default 3)
  └── authEnabled   boolean
```

> **Note:** Both `commons` and `cloud-sdk-api` contain a `JestClientBuilder`. The `commons` version is the legacy one (v5.3.3 of Jest); `cloud-sdk-api` contains v6.3.1. This duplication should be consolidated.

---

### 5.11 Exception & Error Handling Framework

#### Exception Hierarchy

```
RuntimeException
  ├── MercurySecurityException    (401/403 scenarios)
  └── MercuryUuidException        (malformed UUID inputs)

javax.ws.rs.WebApplicationException
  └── (all JAX-RS HTTP-aware exceptions)
```

#### Exception Mapper Chain

```
HTTP Request raises exception
  │
  ├── MercuryWebApplicationExceptionMapper
  │     handles: WebApplicationException
  │     returns: Response with ExceptionResponse JSON body
  │
  ├── MercuryDefaultExceptionMapper
  │     handles: Exception (catch-all)
  │     returns: 500 with ExceptionResponse
  │
  └── ServiceExceptionMapper
        handles: service-layer typed exceptions
        maps to: appropriate HTTP status codes

ExceptionResponse
  ├── code      int (HTTP status)
  ├── message   String
  └── details   Map<String,Object> (optional)
```

#### StandardExceptionMappers Registration

```java
StandardExceptionMappers.register(environment)
  ├── environment.jersey().register(MercuryDefaultExceptionMapper.class)
  ├── environment.jersey().register(MercuryWebApplicationExceptionMapper.class)
  └── environment.jersey().register(ServiceExceptionMapper.class)
```

---

### 5.12 Internationalization

```
src/main/resources/i18n/
  ├── messages_en.properties     English messages
  └── messages_ja.properties     Japanese messages

Usage pattern:
  ResourceBundle bundle = ResourceBundle.getBundle("i18n/messages", locale)
  String message = bundle.getString("error.invalid.input")
```

---

## 6. Key Data Flows

### 6.1 Service Startup Flow

```
Service JVM start
  │
  ├─ 1. main() → InttraServer.run(args)
  │
  ├─ 2. Load raw YAML config
  │
  ├─ 3. ChainingConfigTransformer
  │       ├── TrimConfigCommentsTransform
  │       └── SsmParameterTransformation (SSM API calls)
  │
  ├─ 4. Deserialise resolved YAML → ApplicationConfiguration
  │
  ├─ 5. Guice.createInjector(modules)
  │       └── MyBatisConfigModule → AuroraDataSourceProvider → HikariCP pool
  │
  ├─ 6. Register Jersey resources (from injector)
  │
  ├─ 7. Register filters (CORS, DoS, logging)
  │
  ├─ 8. Register health checks
  │
  ├─ 9. Start Datadog reporter
  │
  └─ 10. Jetty starts → service accepts requests
```

### 6.2 Authenticated Request Flow

```
Client: GET /api/v1/shipments
  Header: Authorization: Bearer <jwt>
  │
  ▼ DoS Filter (rate limiting)
  │
  ▼ CORS Filter (add CORS headers)
  │
  ▼ MercuryRequestLoggingFilter
  │   MDC: REQUEST_ID="req-abc", USER_ID=pending
  │
  ▼ Dropwizard Auth Filter
  │   └── OAuthProvider.authenticate(Bearer <jwt>)
  │         └── validate JWT, load InttraPrincipal
  │         └── MDC: USER_ID = principal.getName()
  │
  ▼ @RolesAllowed("SHIPMENT_READ")
  │   └── MercuryAuthorizer.authorize(principal, "SHIPMENT_READ")
  │
  ▼ ShipmentResource.getShipments(@Auth principal, @QueryParam filters)
  │   └── ShipmentService.findShipments(filters)
  │         └── (database, cache, cloud-sdk calls)
  │
  ▼ MercuryResponseLoggingFilter
  │   log: status=200, duration=45ms
  │
  ▼ Response: 200 OK [{...shipments...}]
```

### 6.3 Database Query Flow

```
Service.findOrder(orderId)
  │
  ▼ OrderMapper.findById(orderId)     (MyBatis @Mapper interface)
  │
  ▼ MyBatis SqlSession
  │
  ▼ AuroraDBLoadBalancingInterceptor
  │   SELECT → route to READ REPLICA
  │
  ▼ HikariCP connection pool
  │   acquires connection from pool (max wait 30s)
  │
  ▼ MySQL/Aurora: SELECT * FROM orders WHERE id = ?
  │
  ▼ ResultSet → Order entity
  │   JsonToContractTypeHandler deserialises JSON columns
  │
  ▼ return Order
```

---

## 7. Dependency Injection Architecture

The module uses **Google Guice 7.0.0** throughout. The following modules are provided:

```
MyBatisConfigModule
  ├── binds DataSource (Aurora)
  ├── installs TransactionModule
  └── scans for @Mapper interfaces

MyCustomBatisModule extends MyBatisConfigModule
  └── adds project-specific mapper bindings

LocalCacheModule
  ├── binds LocalCacheProvider (singleton)
  ├── installs MethodInterceptor for @WithLocalCache
  └── binds GuavaCacheMetrics

ExcelModule
  ├── binds ExcelReader (singleton)
  ├── binds ExcelWriter (singleton)
  └── binds CSVWriter (singleton)

SNSModule (legacy)
  └── binds AmazonSNS (SDK v1)

SQSModule (legacy)
  └── binds AmazonSQS (SDK v1)

JestModule (legacy)
  └── binds JestClient
```

#### Guice Module Composition (InttraServer)

```java
// In service's application class:
@Override
protected List<Module> getModules(C config) {
    return List.of(
        new MyBatisConfigModule(config.getDatabaseConfig()),
        new LocalCacheModule(),
        new ExcelModule(),
        new ServiceSpecificModule(config)  // service adds its own
    );
}
```

---

## 8. Areas of Excellence

### Opinionated Platform Bootstrap
`InttraServer` provides a zero-config path to a production-ready Dropwizard service. Security (DoS, CORS, auth), observability (Datadog metrics, structured logging), and SSM config resolution are automatic. A new service needs only to extend `InttraServer` and register its resources.

### SSM Config Resolution at Boot
Resolving `${awsps:...}` placeholders before Dropwizard deserialises the config is architecturally correct. Secrets never appear in plain text in files; they are resolved from SSM (with decryption) at startup only.

### AuroraDB Load Balancing Interceptor
Transparent routing of read queries to replicas at the MyBatis interceptor level is elegant — no application code needs to know about replica topology. This reduces primary load without any service-layer changes.

### Comprehensive Request Logging + MDC
MDC-based correlation (REQUEST_ID, USER_ID, CORRELATION_ID, WORKFLOW_ID) across filters, services, and database calls provides end-to-end request traceability in logs. This is essential for distributed debugging.

### Method-Level Caching via AOP
`@WithLocalCache` + `LocalCacheInterceptor` provides a non-invasive caching mechanism. Services annotate methods rather than manually managing cache operations. Cache metrics are automatically collected.

### Streaming Excel Processing
Using Apache POI's SAX/event-based API (`ExcelSheetHandler`) rather than the in-memory DOM API prevents OutOfMemoryErrors when processing large Excel files. `SXSSFWorkbook` is used for streaming writes.

### Internationalisation Support
Japanese and English message bundles ship with the module. The pattern is established for future locale additions without code changes.

---

## 9. Areas for Improvement

### `commons` Is Doing Too Much — Needs Decomposition
The module has 350+ classes across 30+ packages. It contains: platform bootstrap, legacy email, legacy DynamoDB, Elasticsearch, Excel, CSV, HTTP clients, utilities, auth models, and more. This violates the Single Responsibility Principle at the module level. Suggested decomposition:
- `commons-server` — InttraServer, auth, filters, exception mappers
- `commons-data` — MyBatis, Aurora, health checks
- `commons-util` — utility classes
- `commons-excel` — Excel/CSV processing (already has ExcelModule)

### Dual JUnit 4 + JUnit 5 Dependencies
The POM declares both `junit:junit:4.13.2` and `junit-jupiter:5.12.2`. New tests should exclusively use JUnit 5. The JUnit 4 dependency should be removed and any legacy tests migrated.

### `spring-security-crypto:4.2.3.RELEASE` Is 7+ Years Old
`EncryptionUtil` uses Spring Security Crypto from 2017. This version has known vulnerabilities and is incompatible with modern Spring ecosystems. Migrate to:
- Spring Security Crypto 6.x, or
- Bouncy Castle's `BCryptPasswordEncoder`, or
- JDK's built-in `javax.crypto` for AES

### Jest Version Discrepancy Between Modules
`commons` uses Jest 5.3.3 (`io.searchbox.jest.version`), while `cloud-sdk-api` and `cloud-sdk-aws` use Jest 6.3.1. The older version in `commons` may have security vulnerabilities. Both should be aligned on 6.3.1, or better, both should migrate to the official Elasticsearch Java client.

### JAXB Dependency Duplication (javax + jakarta)
The POM imports both:
- `javax.xml.bind:jaxb-api:2.3.0` (old javax namespace)
- `jakarta.xml.bind-api:4.0.1` (new Jakarta namespace)

These are the same API in different namespaces. Pick one. Since Dropwizard 4.x uses Jakarta EE, the `javax.*` dependencies should be removed.

### `spring.sercurity.crypto.version` Typo in Parent POM
The property key has a typo: `sercurity` (should be `security`). This is a latent bug — if any code references the correctly-spelled property, it would not find the value. Fix the property name and update all references.

### `LocalCacheModule` Uses `guice-multibindings:4.2.3`
The Guice multibindings version (4.2.3) is significantly behind the main Guice version (7.0.0). Multibindings is now part of the core Guice distribution starting from version 4.3. This dependency should be removed; `com.google.inject:guice:7.0.0` already includes it.

### AuroraDBLoadBalancingInterceptor — Fragile String Matching
The read-replica routing is based on `statement.startsWith(keyword)`. This will fail for:
- Statements with leading whitespace or comments
- Stored procedure calls that do reads internally
- CTEs (`WITH ... SELECT ...`)

A more robust approach would use JDBC transaction read-only mode or a proper SQL parser.

### No Connection Retry in `ExternalServiceClient`
The Jersey HTTP client wrapping has no retry logic for transient failures (502, 503, 504). An exponential-backoff retry policy (similar to `JestClientRetryHandler`) should be applied to all outbound HTTP calls.

### `TempFilesPurgeProcessor` — No Configurable Retention Period
The temp file purge hardcodes "files older than 1 hour". This should be configurable via `ApplicationConfiguration` to support different deployment environments.

### Missing Circuit Breaker Pattern
HTTP clients (`ExternalServiceClient`, `ServiceClient`) and database connections have no circuit breaker. In a microservices environment, a failing downstream dependency can exhaust thread pools and cascade failures. Resilience4j or a similar library should be integrated for critical external calls.
