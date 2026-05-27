# Distributor-REST Module — Architecture & Design

> **Author:** Principal Engineering Review · **Date:** 2026-05-24 · **Module Version:** 1.0 (`com.inttra.mercury.appian-way:distributor-rest:1.0`, see [../pom.xml](../pom.xml#L13-L15))

---

## 1. Executive Summary

The **distributor-rest** module is the **HTTP/REST delivery endpoint** of the Mercury (Appian Way) pipeline. Where its sibling `distributor` module fans messages out to third-party SFTP/email/SQS subscribers, `distributor-rest` is the REST-over-HTTPS delivery counterpart: it picks up workflow notifications from an SQS queue, resolves the subscriber's REST endpoint and OAuth credentials from the Network Services subscription registry, fetches the rendered EDI payload from the S3 workspace, and POSTs that payload to the subscriber's REST webhook with a Bearer token.

Despite the module's name, it does not expose a meaningful inbound REST API of its own — Dropwizard's HTTP server is started purely to satisfy the Dropwizard lifecycle (configuration parsing, metrics endpoint, healthchecks). The work happens on a background SQS-listener thread driven by `SQSListener` (poll loop) and an `AsyncDispatcher` (thread pool). The actual delivery is performed by `RestServiceClient` using the **Jersey JAX-RS client (3.1.11)** with a guava-retrying-based retry policy.

Key behavioural facts grounded in the code:

- **Inbound trigger:** Long-polled SQS messages on `distributor.pickupSQSConfig.queueUrl` (`distributor-rest.yaml:14-17`), e.g. `inttra2_pr_sqs_rest_delivery` in prod (`conf/prod/distributor-rest.properties:2`).
- **Payload source:** The SQS message body is a Mercury `MetaData` JSON envelope pointing to an S3 object in the workspace bucket (`DistributorTask.java:68,76-77`).
- **Subscriber resolution:** The `subscriptionId` projection on the `MetaData` is resolved via the cached `SubscriptionService` (Network Services) to obtain `Action`s of type `EDI_WEBHOOK` (`DistributorTask.java:72-78`, `RequestBuilder.java:31`).
- **Auth model:** Two-leg OAuth — Basic-auth POST to the subscriber's OAuth URL using `userId`/`password` parameters from the `Subscription`, returns a Bearer token cached in `AuthClient` (`AuthClient.java:34-46`).
- **Delivery:** Jersey `Client.target(url + "?connectionId=...").request().headers(...).header("Authorization","bearer "+token).post(Entity.entity(content, APPLICATION_JSON), ResponseWrapper.class)` (`RestServiceClient.java:44-48`).
- **Retry policy:** 3 attempts, exponential backoff starting at 100ms, **no retry on HTTP 400/404** (`RetryerBuilder.java:13-14, 31-33`).
- **Token refresh:** On HTTP 401, `AuthClient.newToken(...)` is invoked to force a fresh token then the call is retried by the retryer (`RestServiceClient.java:55-57`).
- **Error handling:** Recoverable failures bounce back to the pickup queue; once `recoverableAttempts` is exhausted they go to `<pickupQueue>_dlq`. Non-recoverable failures (`NonRecoverableException`) are forwarded to `distributor.sqsErrorSubscriptionConfig.queueUrl` via the shared `ErrorHandler`.
- **Response contract:** The remote endpoint must return `{"Response":{"Status":{"Code":"SUCCESS","E2openTransactionId":"..."}}}` JSON. Any other code is treated as a non-recoverable failure (`RestServiceClient.java:64-68`, `e2net/Status.java`).
- **Runtime:** Dropwizard 4.0.16 simple-connector HTTP server on port 8081 (`distributor-rest.yaml:38-42`), JVM `-Xmx384m` on ECS Fargate (`conf/prod/distributor-rest-latest-prod-Task.json:16,24`).

This module is intentionally narrow: one inbound channel (SQS), one outbound protocol (HTTPS+OAuth2+JSON), one downstream contract (the e2net-style `Response`/`Status` envelope from [`src/main/java/com/inttra/mercury/distributorrest/e2net`](../src/main/java/com/inttra/mercury/distributorrest/e2net)). The packaging hints that the original target was e2open's EDI Webhook ingest API.

---

## 2. Position in the Mercury Pipeline

Mercury (Appian Way) is a multi-stage, S3-backed, SQS-orchestrated ETL for shipping EDI documents. The full pipeline runs roughly:

```
ingestor -> validator -> fulfiller -> (distributor | distributor-rest | mft-dispatcher | ...)
```

Upstream stages produce a rendered subscriber-ready payload in S3 and a `MetaData` JSON envelope describing it. A routing/dispatch tier (see the `dispatcher` module) inspects the active `Action` on the subscription and enqueues the envelope onto the per-protocol delivery queue:

- **`distributor`** — handles SFTP / email / S3 / SQS-fan-out deliveries (the original "distributor").
- **`distributor-rest`** — this module: handles `ActionType.EDI_WEBHOOK` deliveries to a subscriber-owned HTTPS endpoint.
- **`mftdispatcher`** — handles MFT-style deliveries.

```mermaid
flowchart LR
    subgraph Upstream["Upstream Pipeline"]
        IN[Ingestor]
        VA[Validator]
        FF[Fulfiller]
    end

    subgraph Routing["Routing"]
        DS[Dispatcher]
    end

    subgraph Delivery["Delivery Tier"]
        D1[distributor<br/>SFTP/Email]
        D2[distributor-rest<br/>HTTPS/OAuth2]
        D3[mftdispatcher<br/>MFT]
    end

    subgraph DownstreamSinks["Subscriber Sinks"]
        SFTP[(Subscriber SFTP)]
        SMTP[(Subscriber SMTP)]
        WEB[(Subscriber<br/>REST Webhook)]
    end

    IN --> VA --> FF --> DS
    DS -->|SFTP/EMAIL action| D1
    DS -->|EDI_WEBHOOK action| D2
    DS -->|MFT action| D3

    D1 --> SFTP
    D1 --> SMTP
    D2 -->|POST + Bearer| WEB
```

### 2.1 The SQS contract that feeds this module

The pickup queue is `inttra2_<env>_sqs_rest_delivery` (e.g. `inttra2_pr_sqs_rest_delivery` in prod — see [`conf/prod/distributor-rest.properties:2`](../conf/prod/distributor-rest.properties)). Messages on this queue are `MetaData` JSON envelopes carrying:

- `workflowId` — correlation id used in close-run events (`DistributorTask.java:71`).
- `bucket` and `fileName` — pointer to the rendered payload in the S3 workspace (`DistributorTask.java:76-77`).
- `projections[SUBSCRIPTION_ID]` — the subscription whose REST endpoint should receive the payload (`DistributorTask.java:72`).

The payload is read as **ISO-8859-1** (`DistributorTask.java:77`) which preserves the byte-faithful EDI rendering produced upstream.

### 2.2 The SNS event bus

On both success and failure paths, the module publishes a `CLOSE_WORKFLOW` close-run event to the central Mercury SNS topic configured by `distributor.snsEventConfig.topicArn` (`distributor-rest.yaml:8-9`, prod ARN `arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event`). These events drive observability/dashboards/replay tooling.

### 2.3 Why a separate module

`distributor` lives in the `aws-java-sdk-sqs` + `commons-net` + JavaMail world; `distributor-rest` carries an extra Jersey client stack and stateful OAuth token cache. Keeping it separate avoids polluting the SFTP/email distributor with HTTP-stack dependencies and isolates the credential lifecycle (every REST subscriber has its own OAuth URL + credentials, whereas SFTP/email creds live in the subscription record only).

---

## 3. High-Level Architecture

### 3.1 Process anatomy

A `distributor-rest` JVM, packaged as an Uber JAR by `maven-shade-plugin` (`pom.xml:163-196`) with main class `com.inttra.mercury.distributorrest.DistributorApplication` (`pom.xml:190`), runs as a single container on ECS Fargate. Inside the JVM there is:

- One **Dropwizard `Application`** loop — `DistributorApplication`, holding the HTTP server (port 8081) and the lifecycle-managed components (`DistributorApplication.java:39-54`).
- One **Guice Injector** built from two modules — `ExternalServicesModule` (AWS clients, Jersey client, Retryer, Network Services bindings) and `DistributorModule` (per-app bindings + SQS listener) (`DistributorApplication.java:45-47`).
- One **`SQSListener` thread** spun up by `ListenerManager` via the Dropwizard lifecycle (`DistributorModule.java:65-80`, `DistributorApplication.java:52-53`, `shared/.../SQSListener.java:90-110`).
- One **`AsyncDispatcher` thread pool** sized to `sqsPickupConfig.maxNumberOfMessages` (default `5`, `distributor-rest.yaml:17`), where each pool slot executes one `DistributorTask.process(...)` (`DistributorModule.java:43-46`).
- One **`AuthClient` singleton** holding the in-process OAuth token cache (`AuthClient.java:14-19`).

```mermaid
flowchart TB
    subgraph JVM["distributor-rest JVM (ECS task, Xmx=384m)"]
        DW[Dropwizard App<br/>:8081 HTTP/admin]
        subgraph Guice["Guice Injector"]
            LM[ListenerManager]
            SL[SQSListener<br/>thread]
            AD[AsyncDispatcher<br/>thread pool n=5]
            DT[DistributorTask<br/>per-message]
            RSC[RestServiceClient]
            AC[AuthClient<br/>singleton + token cache]
            SS[SubscriptionService<br/>cached]
            WS[WorkspaceService<br/>S3]
            EP[EventPublisher<br/>SNS]
            EH[ErrorHandler]
        end
    end

    SQS[(SQS:<br/>inttra2_*_sqs_rest_delivery)]
    NS[(Network Services<br/>REST API)]
    S3[(S3 workspace<br/>bucket)]
    SUB[[Subscriber REST<br/>endpoint + OAuth]]
    SNS[(SNS:<br/>inttra2_*_sns_event)]
    DLQ[(SQS:<br/>*_dlq + *_subscription_errors)]

    DW -.-> LM
    LM --> SL
    SL -->|poll long| SQS
    SQS -->|MetaData JSON| SL
    SL --> AD
    AD --> DT
    DT --> WS
    WS --> S3
    DT --> SS
    SS --> NS
    DT --> RSC
    RSC --> AC
    AC -->|Basic auth| SUB
    RSC -->|Bearer auth POST| SUB
    DT --> EP
    EP --> SNS
    DT -->|on error| EH
    EH --> DLQ
```

### 3.2 Roles in one sentence each

| Component | Role |
|---|---|
| `DistributorApplication` | Dropwizard entry point; wires Guice and starts the SQS listener via `ListenerManager`. |
| `DistributorConfiguration` | Strongly-typed YAML/properties root, extending shared `BaseConfiguration`. |
| `ExternalServicesModule` | Builds AWS SDK clients, the Jersey `Client`s, the Retryer, and Network Services caches. |
| `DistributorModule` | Binds the per-app `Dispatcher`, `SQSListener`, `EventPublisher`, and metrics AOP. |
| `SQSListener` (shared) | Long-polls the pickup queue, submits batches to the dispatcher. |
| `AsyncDispatcher` (shared) | Per-message thread pool that drives `Task.execute(...)`. |
| `DistributorTask` | The unit of work: parse MetaData -> load file -> resolve subscription -> build request -> POST -> emit close-run event. |
| `SubscriptionService` (shared, cached) | Fetches the active `Subscription` and its `Action`s. |
| `RequestBuilder` | Converts a `Subscription` of action type `EDI_WEBHOOK` into a HTTP `Request` (URL, headers, OAuth context). |
| `AuthClient` | Performs Basic-auth client_credentials-style OAuth exchange and caches the resulting `Token`. |
| `RestServiceClient` | Executes the HTTPS POST through Jersey with retry, 401-refresh and JSON response binding. |
| `RetryerBuilder` | Configures the guava-retrying `Retryer` used for the outbound POST. |
| `ErrorHandler` (shared) | Routes recoverable/non-recoverable failures to retry / DLQ / error SQS. |
| `e2net.{Response,ResponseWrapper,Status,Token}` | Jackson DTOs for the subscriber and OAuth wire formats. |

---

## 4. Low-Level Design

This section walks the static structure top-down.

### 4.1 Bootstrap (`DistributorApplication`)

Located at [`src/main/java/com/inttra/mercury/distributorrest/DistributorApplication.java`](../src/main/java/com/inttra/mercury/distributorrest/DistributorApplication.java):

```java
public class DistributorApplication extends Application<DistributorConfiguration> {
    public static void main(final String[] args) throws Exception {
        new DistributorApplication(null).run(args);
    }
```

Notable bootstrap behaviours:

1. **Optional S3-backed configuration source** (`DistributorApplication.java:31-33`). When `S3ConfigurationProvider.requiresS3Configuration()` is `true`, Dropwizard's configuration is read from S3 rather than the local filesystem. The `run.sh` script always launches with local config files (`run.sh:14`), so S3 sourcing only kicks in when the environment opts in via shared env vars.

2. **`ConfigProcessingServerCommand` registration** (`DistributorApplication.java:34`). Replaces the default Dropwizard `server` command with the shared variant that supports multiple property files passed on the CLI — exactly how `run.sh` invokes the jar: `java ... run distributor-rest.yaml ./distributor-rest.properties ./network-services.properties ./datadog.properties` (`run.sh:14`).

3. **Two-stage Guice injection** (`DistributorApplication.java:39-50`). `externalServiceModule` is constructor-injectable for test use (`DistributorApplication.java:21-23`); in production it is built lazily from configuration.

4. **Lifecycle handover** (`DistributorApplication.java:52-53`). The application asks Guice for the `ListenerManager` and registers it with the Dropwizard lifecycle. `ListenerManager` then starts the SQS listener thread on `Server.start()` and signals shutdown on `Server.stop()`.

5. **Defensive but lossy exception handling** (`DistributorApplication.java:48-50`). The `try { Guice.createInjector(...) } catch (Exception ex) { ex.printStackTrace(); }` block swallows wiring errors and proceeds to `injector.getInstance(...)`, which will then NPE. In practice, any wiring failure will crash the container loudly on the very next line — see section 13.

### 4.2 Configuration objects

Three local config types live under [`src/main/java/com/inttra/mercury/distributorrest/config`](../src/main/java/com/inttra/mercury/distributorrest/config):

- **`DistributorConfiguration`** (`DistributorConfiguration.java`) extends `com.inttra.mercury.shared.config.BaseConfiguration`, inheriting `componentName`, `sqsPickupConfig`, `sqsErrorConfig`, `snsEventConfig`, `s3WorkspaceConfig` (`shared/.../BaseConfiguration.java:15-41`). It adds three local fields:
  - `healthCheckConfig` — error-rate threshold + network services healthcheck URL (`HealthCheckConfig.java`).
  - `networkServiceConfig` — base URL, auth endpoint, client credentials, `servicePaths` map (`shared/.../NetworkServiceConfig.java`).
  - `restClientConfig` — Jersey connect/read timeouts (`RestClientConfig.java`).
- **`EndpointConfig`** (`EndpointConfig.java`) defines a single `endPointURL` field; it is currently **dead code** — nothing in the module references it. Likely a leftover from an earlier static endpoint design that was superseded by per-subscription URLs.
- **`HealthCheckConfig`** (`HealthCheckConfig.java`) — though declared, no `HealthCheck` class in this module is registered with Dropwizard's `environment.healthChecks()`. The `errorRateThreshold` value is parsed but never consumed in code. Another vestige; see section 13.

### 4.3 Guice wiring

#### 4.3.1 `ExternalServicesModule`

Source: [`src/main/java/com/inttra/mercury/distributorrest/modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/distributorrest/modules/ExternalServicesModule.java).

It binds:

- Three AWS SDK clients with role-appropriate `ClientConfiguration` from shared `AWSClientConfiguration`:
  - `@Named("amazonSQSForListener") AmazonSQS` (long-poll friendly socket timeouts).
  - `@Named("amazonSQSForSender") AmazonSQS` (used by the SQS sender in error/retry flows).
  - `AmazonS3` (read/put/copy) — used by `S3WorkspaceService` to read the payload.
  - `AmazonSNS` (publish) — used by `SNSEventPublisher`.
- A `Clock` UTC singleton (`ExternalServicesModule.java:54`).
- The `NetworkServiceConfig` plus `Names.bindProperties` of its `servicePaths` map (`ExternalServicesModule.java:56-58`). This exposes the per-microservice path components (e.g. `subscriptionSearchPath`) as `@Named` injectables.
- **Cache-decorated Network Services** (`ExternalServicesModule.java:60-63`): every consumer of `IntegrationProfileByIdService`, `IntegrationProfileFormatByIdService`, `FormatService`, `SubscriptionService` gets the cached implementation rather than the raw HTTP one. This is the only thing keeping subscription lookups out of the critical path.
- **Eager `AuthClient`** (`ExternalServicesModule.java:65-66`). Note: this `AuthClient` is the **shared/Network Services** one (`com.inttra.mercury.shared.networkservices.auth.AuthClient`), not the local `distributorrest.auth.AuthClient`. The shared one logs in to the platform's own OAuth service to talk to Network Services, fail-fast on startup.
- `ParameterStoreModule` for client-secret resolution via SSM, gated by `usePassThrough` (`ExternalServicesModule.java:68-69`).
- `NetworkRetryerModule` — separate retryer for Network Services calls.
- `@Named("RestRetry") Retryer` — the local `RetryerBuilder.getRetryer()` (`ExternalServicesModule.java:71-73`), used for the **subscriber-facing** HTTP POST.
- `@Named("RestClient") Client` — a Jersey client with the timeouts from `restClientConfig` applied (`ExternalServicesModule.java:74-76, 86-91`).
- A default `@Provides Client jerseyClient()` (`ExternalServicesModule.java:80-83`) — this is the unnamed default that the local `AuthClient` constructor `@Inject`s.

A subtle two-client setup falls out: the **subscriber OAuth token call** uses the *default* `jerseyClient()` (no custom timeouts), the **subscriber data POST** uses the `@Named("RestClient")` client (with timeouts). This is consistent with the test fixture `RestServiceClientTest.java:84` injecting both.

#### 4.3.2 `DistributorModule`

Source: [`src/main/java/com/inttra/mercury/distributorrest/modules/DistributorModule.java`](../src/main/java/com/inttra/mercury/distributorrest/modules/DistributorModule.java).

It binds:

- `DistributorConfiguration` and the wider `BaseConfiguration` (so shared classes like `ErrorHandler` resolve the same instance, `DistributorModule.java:40-41`).
- A `Dispatcher` realised as `AsyncDispatcher` whose `TaskFactory` always returns a fresh `DistributorTask` from Guice (`DistributorModule.java:43-46`). Because each task is a Guice-managed instance, the `RestServiceClient`, `SubscriptionService`, etc. are injected per-task instance.
- `WorkspaceService` -> `S3WorkspaceService` (`DistributorModule.java:47`).
- `NetworkServiceConfig` and a *second* binding of its `servicePaths` (`DistributorModule.java:49-50`) — duplicates the bindings in `ExternalServicesModule`; harmless because they bind the same values.
- `MetricsInstrumentationModule` for `@Metered`/`@Timed` AOP using the Dropwizard metrics registry (`DistributorModule.java:53`).
- A singleton `EventPublisher` backed by `SNSEventPublisher` against `snsEventConfig.topicArn` (`DistributorModule.java:57-61`).
- A singleton `ListenerManager` containing the single `SQSListener` (`DistributorModule.java:64-67`).
- The `SQSListener` itself, parameterised from `sqsPickupConfig` (`DistributorModule.java:69-80`).

#### 4.3.3 `RetryerBuilder` (local)

Source: [`src/main/java/com/inttra/mercury/distributorrest/modules/RetryerBuilder.java`](../src/main/java/com/inttra/mercury/distributorrest/modules/RetryerBuilder.java).

Static factory that returns a `com.github.rholder.retry.Retryer<T>` configured as:

| Aspect | Value | Source |
|---|---|---|
| Wait strategy | Exponential, base 100ms, ceiling `Integer.MAX_VALUE` ms | `RetryerBuilder.java:13` |
| Stop strategy | After 3 attempts | `RetryerBuilder.java:14` |
| Retry predicate | Always retry, **except** `WebApplicationException` with status 400 or 404 | `RetryerBuilder.java:15, 29-35` |
| Listener | INFO-logs every attempt+exception | `RetryerBuilder.java:16-25` |

The retryer is **not exception-rethrowing-aware** — it retries unconditionally on plain exceptions including `RuntimeException` and `NullPointerException`. The carve-out for 400/404 makes sense (400 = subscriber rejects the payload as malformed, 404 = endpoint URL is wrong; neither is fixed by retrying), but everything else — including 500s, 401s, connection resets, socket timeouts — will retry up to 3 times.

### 4.4 The task

#### 4.4.1 `DistributorTask`

Source: [`src/main/java/com/inttra/mercury/distributorrest/task/DistributorTask.java`](../src/main/java/com/inttra/mercury/distributorrest/task/DistributorTask.java).

`DistributorTask` extends `AbstractTask` from shared, which itself implements `Task` and provides a `@Metered("messages-processed")` `execute(...)` wrapper that handles SQS message deletion on success (`shared/.../AbstractTask.java:22-41`). The contract for the subclass is `process(message, queueUrl)`; if `process` throws, the message is **not** deleted and SQS will redeliver it after the visibility timeout (`shared/.../AbstractTask.java:33-35`).

`process` does the following (`DistributorTask.java:65-93`):

1. Capture `startDateTime` from the injected `Clock` (used for close-run-event timings).
2. Deserialise the SQS message body as `MetaData` via `Json.fromJsonString(...)` (`DistributorTask.java:68`).
3. Generate a fresh `runId` (`UUID`) (`DistributorTask.java:70`).
4. Read `subscriptionId` from `metaData.projections[SUBSCRIPTION_ID]`.
5. If non-null:
   - Pull the rendered file from S3 as ISO-8859-1 (`DistributorTask.java:76-77`).
   - Resolve the `Subscription` via `subscriptionService.findSubscriptions(subscriptionId)` (`DistributorTask.java:78`).
   - Build the HTTP `Request` from the Subscription via `RequestBuilder` (`DistributorTask.java:79`).
   - POST it via `RestServiceClient` and capture the returned `transactionId` (`DistributorTask.java:80`).
6. If null: log the error, but still proceed to publish a (success-flagged) close-run event with empty transactionId (`DistributorTask.java:82-84`). See section 13 — this is arguably a defect.
7. Publish a `CLOSE_WORKFLOW` close-run event with the pickup queue URL and the `E2OPEN_TRANSACTION_ID` token (`DistributorTask.java:85-87`).
8. Any `NonRecoverableException | IOException` (`DistributorTask.java:89`) is handed to the shared `ErrorHandler`. **Note:** `RestServiceClient.post(...)` wraps everything in `RecoverableException`, which is *not* in this catch block, so recoverable failures propagate out of `process` and bubble up to `AbstractTask.execute`'s generic `catch (Exception ex)` block (`AbstractTask.java:33-35`). That block logs at WARN and *does not delete* the message — so SQS will redeliver it, which is the intended retry mechanism. See section 11.

#### 4.4.2 `Request`

Source: [`src/main/java/com/inttra/mercury/distributorrest/task/Request.java`](../src/main/java/com/inttra/mercury/distributorrest/task/Request.java).

A POJO with three fields: `url` (the fully composed POST URL including `?connectionId=...`), `headers` (a Jersey `MultivaluedMap<String,Object>`), and `oAuthRequest` (Basic-auth credentials + token URL).

#### 4.4.3 `RequestBuilder`

Source: [`src/main/java/com/inttra/mercury/distributorrest/task/RequestBuilder.java`](../src/main/java/com/inttra/mercury/distributorrest/task/RequestBuilder.java).

Walks `subscription.getActions()` looking for the **first** action of type `ActionType.EDI_WEBHOOK` (`RequestBuilder.java:30-31`), then iterates that action's `actionParameters` (`RequestBuilder.java:32`). Each `ActionParameter` has a `name`/`value` pair. Behaviour by name:

| Parameter name | Destination | Code |
|---|---|---|
| `fromDuns`, `toDuns`, `dataType`, `version` | Added as HTTP request headers (multi-valued) | `RequestBuilder.java:33-35` |
| `userid` | `OAuthRequest.clientUserId` | `RequestBuilder.java:35-37` |
| `password` | `OAuthRequest.clientSecret` | `RequestBuilder.java:37-39` |
| `connectionId` | URL query parameter | `RequestBuilder.java:39-41, 49` |
| `oAuthUrl` | `OAuthRequest.oAuthUrl` | `RequestBuilder.java:41-43` |
| `endPointUrl` | Base URL | `RequestBuilder.java:43-45, 49` |

Final URL: `url + "?connectionId=" + connectionId` (`RequestBuilder.java:49`). This is *unconditional* concatenation; if `connectionId` is missing the literal string `?connectionId=null` is appended.

**Subtle bug surface** (see section 13):

- The inner loop iterates `subscription.getActions().get(0).getActionParameters()` (`RequestBuilder.java:32`), not the parameters of the matched action. If the first action is *not* `EDI_WEBHOOK` but a later one is, the parameters of the first (wrong) action are still consumed. The current consumers only ever publish a single EDI_WEBHOOK action, so this works in practice.

#### 4.4.4 `RestServiceClient`

Source: [`src/main/java/com/inttra/mercury/distributorrest/task/RestServiceClient.java`](../src/main/java/com/inttra/mercury/distributorrest/task/RestServiceClient.java).

The HTTP layer. Constructor takes the named Jersey `Client`, the local `AuthClient`, and the named Retryer. `post(request, fileContent)` flow:

1. Build a `WebTarget` for the request URL (`RestServiceClient.java:35`).
2. Execute via the retryer the following callable (`RestServiceClient.java:38-61`):
   - Fetch a token via `authClient.getToken(request.getOAuthRequest())` (cached or fresh).
   - Log request headers (may include sensitive data — see section 13).
   - Submit a Jersey `POST` with the multi-valued headers, an `Authorization: bearer <token>` header, and the file content as `MediaType.APPLICATION_JSON` (`RestServiceClient.java:44-48`).
   - Read the response as `ResponseWrapper.class` — Jersey will use Jackson to deserialise it.
3. On `WebApplicationException 401`: invoke `authClient.newToken(...)` to force-refresh the token, then rethrow so the retryer attempts again (`RestServiceClient.java:55-57`).
4. On success: if `response.getResponse().getStatus().getCode().equals("SUCCESS")`, return `e2openTransactionId` (`RestServiceClient.java:64-65`). Otherwise throw `NonRecoverableException("Error")` (`RestServiceClient.java:66-68`).
5. All exceptions (including `NonRecoverableException`, retryer's `RetryException`, and the `ExecutionException` it raises) are caught at line 70 and wrapped in `RecoverableException` (`RestServiceClient.java:70-72`). This is a deliberate **fail-open-to-retry** strategy: even `NonRecoverableException`s become recoverable because of the wrapping. See section 13.

### 4.5 OAuth client (`AuthClient`)

Source: [`src/main/java/com/inttra/mercury/distributorrest/auth/AuthClient.java`](../src/main/java/com/inttra/mercury/distributorrest/auth/AuthClient.java).

Per-process singleton (`@Singleton`, `AuthClient.java:14`). State: a single shared `Token token` field (`AuthClient.java:19`). This is intentional but heavily implies that **all subscribers share the same token**, which only works if all `(oAuthUrl, userid, password)` triplets are the same. In practice, today there is one e2net OAuth realm, so the assumption holds. See section 13.

- `getToken(oauthRequest)` returns the cached token if non-null, else calls `newToken` (`AuthClient.java:27-32`).
- `newToken(oauthRequest)` (`synchronized`, `AuthClient.java:34-46`):
  - Builds a Basic-auth credential by base64-encoding `userid + ":" + password`.
  - POSTs (empty body) to the OAuth URL with `Authorization: Basic <b64>`.
  - Deserialises the response as `Token.class` (which captures `access_token`, `refresh_token`, `token_type`, `scope`, `expires`, `uid` — see `e2net/Token.java`).
  - Stores the result in the `token` field.
- Local 2-attempt retryer (`AuthClient.java:48-65`) — exponential backoff base 100ms, retries on *any* exception.

**Concurrency:** `getToken()` is not `synchronized`. Two concurrent tasks may both see `token == null` and call `newToken()` once each. The first will block on the synchronized monitor, both will set the same value, and one wasted OAuth call results. Harmless but worth noting.

**Token expiry:** The token's `expires` field is captured but **never inspected**. The cache never auto-refreshes on TTL — it relies on the receiving server returning 401 to trigger a refresh via the 401-handler path in `RestServiceClient`.

### 4.6 Wire DTOs (`e2net.*`)

Source: [`src/main/java/com/inttra/mercury/distributorrest/e2net`](../src/main/java/com/inttra/mercury/distributorrest/e2net).

Four Jackson-bound POJOs (`@JsonInclude(NON_NULL)`, `@JsonIgnoreProperties` ignoring unknown):

- `ResponseWrapper` — `{"Response": {...}}`. Capitalised property to match e2net's JSON.
- `Response` — `{"Status": {...}}`.
- `Status` — `{"Code", "Text", "E2openTransactionId"}`. `Code == "SUCCESS"` is the only positive outcome.
- `Token` — OAuth2 token payload (`access_token`, `refresh_token`, `token_type`, `scope`, `expires`, `uid`).

The class names and JSON capitalisation strongly indicate the original integration target was the **e2net EDI Webhook** API.

### 4.7 Inherited (shared) machinery — abbreviated

These come from the `mercury-shared` jar:

- `BaseConfiguration` ([`shared/.../config/BaseConfiguration.java`](../../shared/src/main/java/com/inttra/mercury/shared/config/BaseConfiguration.java)) — fields inherited by `DistributorConfiguration`.
- `SQSListener` ([`shared/.../listener/SQSListener.java`](../../shared/src/main/java/com/inttra/mercury/shared/listener/SQSListener.java)) — long-poll loop with dispatcher backpressure (`getIdleThreadCount()`).
- `AsyncDispatcher` ([`shared/.../threaddispatcher/AsyncDispatcher.java`](../../shared/src/main/java/com/inttra/mercury/shared/threaddispatcher/AsyncDispatcher.java)) — fixed thread pool, one task per message.
- `AbstractTask` ([`shared/.../task/AbstractTask.java`](../../shared/src/main/java/com/inttra/mercury/shared/task/AbstractTask.java)) — `execute` wrapper with delete-on-success and `@Metered`.
- `ErrorHandler` ([`shared/.../task/ErrorHandler.java`](../../shared/src/main/java/com/inttra/mercury/shared/task/ErrorHandler.java)) — recoverable/non-recoverable router with DLQ fallback after N attempts.
- `S3WorkspaceService` ([`shared/.../workspace/S3WorkspaceService.java`](../../shared/src/main/java/com/inttra/mercury/shared/workspace/S3WorkspaceService.java)) — `getContent(bucket, key, charset)`.
- `SubscriptionService` + `CacheSubscriptionServiceImpl` ([`shared/.../networkservices/subscription`](../../shared/src/main/java/com/inttra/mercury/shared/networkservices/subscription)) — Network Services GETs wrapped in a Guava cache.
- `SNSEventPublisher` + `EventLogger` — emit close-run events to the SNS event topic.

---

## 5. Key Classes — Class Diagram

```mermaid
classDiagram
    class DistributorApplication {
        -Module externalServiceModule
        +main(String[])
        +initialize(Bootstrap)
        +run(DistributorConfiguration, Environment)
    }
    class DistributorConfiguration {
        +HealthCheckConfig healthCheckConfig
        +NetworkServiceConfig networkServiceConfig
        +RestClientConfig restClientConfig
    }
    class BaseConfiguration {
        +String componentName
        +SQSConfig sqsPickupConfig
        +SQSConfig sqsErrorConfig
        +SNSConfig snsEventConfig
        +S3Config s3WorkspaceConfig
    }
    class HealthCheckConfig {
        +Double errorRateThreshold
        +String networkServiceHealthCheckUrl
    }
    class RestClientConfig {
        +String connectTimeout
        +String readTimeout
    }
    class ExternalServicesModule {
        +configure()
        +jerseyClient() Client
        +jerseyRestClient() Client
    }
    class DistributorModule {
        +configure()
        +snsEventPublisher(SNSClient) EventPublisher
        +listenerManager(SQSListener) ListenerManager
        +getSQSListener(Dispatcher, SQSListenerClient) SQSListener
    }
    class RetryerBuilder {
        +getRetryer() Retryer
        +isRetryable(Throwable) boolean
    }
    class DistributorTask {
        -EventLogger eventLogger
        -RestServiceClient restServiceClient
        -SubscriptionService subscriptionService
        -RequestBuilder requestBuilder
        -WorkspaceService workspaceService
        -ErrorHandler errorHandler
        +process(Message, String)
    }
    class AbstractTask {
        -SQSClient sqs
        +execute(Message, String)
        #process(Message, String)
        -deleteMessage(Message)
    }
    class RequestBuilder {
        +build(Subscription) Request
    }
    class Request {
        +String url
        +MultivaluedMap headers
        +OAuthRequest oAuthRequest
    }
    class RestServiceClient {
        -Client client
        -AuthClient authClient
        -Retryer retryer
        +post(Request, String) String
    }
    class AuthClient {
        -Client client
        -Retryer retryer
        -Token token
        +getToken(OAuthRequest) Token
        +newToken(OAuthRequest) Token
    }
    class OAuthRequest {
        +String clientUserId
        +String clientSecret
        +String oAuthUrl
    }
    class ResponseWrapper {
        +Response response
    }
    class Response {
        +Status status
    }
    class Status {
        +String code
        +String text
        +String e2openTransactionId
    }
    class Token {
        +String accessToken
        +String refreshToken
        +String tokenType
        +String scope
        +String expires
        +String uid
    }
    class NonRecoverableException {
    }

    DistributorConfiguration --|> BaseConfiguration
    DistributorConfiguration *-- HealthCheckConfig
    DistributorConfiguration *-- RestClientConfig
    DistributorApplication --> DistributorConfiguration
    DistributorApplication --> ExternalServicesModule
    DistributorApplication --> DistributorModule
    DistributorModule --> DistributorTask : binds factory
    ExternalServicesModule --> RetryerBuilder : invokes
    DistributorTask --|> AbstractTask
    DistributorTask --> RequestBuilder
    DistributorTask --> RestServiceClient
    DistributorTask --> NonRecoverableException : throws
    RequestBuilder --> Request : builds
    RequestBuilder --> OAuthRequest
    Request *-- OAuthRequest
    RestServiceClient --> AuthClient
    RestServiceClient --> Request
    RestServiceClient --> ResponseWrapper
    RestServiceClient --> NonRecoverableException : throws
    ResponseWrapper *-- Response
    Response *-- Status
    AuthClient --> OAuthRequest
    AuthClient --> Token
```

### 5.1 Cardinality and lifecycle

| Class | Scope | Notes |
|---|---|---|
| `DistributorApplication` | 1 per JVM | Dropwizard `Application`. |
| `ExternalServicesModule`, `DistributorModule` | 1 per JVM | Guice modules. |
| `Client` `@Named("RestClient")` | 1 per JVM | Jersey client; thread-safe per JAX-RS spec. |
| `Client` default | 1 per JVM | Used by local `AuthClient`. |
| `Retryer @Named("RestRetry")` | 1 per JVM | Stateless. |
| `AuthClient` (local) | 1 per JVM (`@Singleton`) | Holds `Token token` mutable state. |
| `SubscriptionService` (cached) | 1 per JVM | Guava cache. |
| `SQSListener` | 1 per JVM | Single poller thread. |
| `AsyncDispatcher` thread pool | `maxNumberOfMessages = 5` workers (`distributor-rest.yaml:17`) | One `DistributorTask` per worker call. |
| `DistributorTask` | 1 per message | Built fresh by Guice for every `taskProvider.get()`. |
| `RequestBuilder` | 1 per task (instantiated in `DistributorTask` constructor at `DistributorTask.java:58`) | Stateless. |
| `RestServiceClient` | Injected per-task; the underlying `Client` and `Retryer` are JVM-singletons. | Stateless facade. |

---

## 6. Data Flow Diagram

The end-to-end sequence below tracks one SQS message through the system.

```mermaid
sequenceDiagram
    autonumber
    participant SQS as SQS pickup queue<br/>inttra2_*_sqs_rest_delivery
    participant L as SQSListener thread
    participant D as AsyncDispatcher pool
    participant T as DistributorTask
    participant S3 as S3 workspace
    participant NS as SubscriptionService<br/>(cached -> Network Services)
    participant RB as RequestBuilder
    participant RC as RestServiceClient
    participant AC as AuthClient
    participant OA as Subscriber OAuth endpoint
    participant SUB as Subscriber REST endpoint
    participant SNS as SNS event topic
    participant DLQ as DLQ / subscription_errors queue
    participant EH as ErrorHandler

    L->>SQS: ReceiveMessage(waitTime=20s, max=idleThreads)
    SQS-->>L: List<Message> (each = MetaData JSON)
    L->>D: dispatcher.submit(messages, queueUrl)
    D->>T: execute(message, queueUrl)

    T->>T: Json.fromJsonString(body, MetaData.class)
    T->>T: runId = UUID
    Note over T: subscriptionId = metaData.projections[SUBSCRIPTION_ID]

    alt subscriptionId == null
        T->>T: log.error("No subscriptionId !!!")
        T->>SNS: logCloseRunEvent(success=true, transactionId="")
    else subscriptionId != null
        T->>S3: getObject(bucket, fileName, ISO_8859_1)
        S3-->>T: file content
        T->>NS: findSubscriptions(subscriptionId)
        NS-->>T: Subscription (with EDI_WEBHOOK Action)
        T->>RB: build(subscription)
        RB-->>T: Request(url + "?connectionId=...", headers, OAuthRequest)
        T->>RC: post(request, fileContent)
        RC->>AC: getToken(oAuthRequest)
        alt token cached
            AC-->>RC: cached Token
        else first call
            AC->>OA: POST + Basic auth(b64(userid:password))
            OA-->>AC: {access_token, refresh_token, ...}
            AC-->>RC: Token
        end
        RC->>SUB: POST url<br/>Authorization: bearer <token><br/>Content-Type: application/json<br/>+ multi-valued headers (fromDuns, toDuns, dataType, version)
        alt HTTP 200 + Status.Code == "SUCCESS"
            SUB-->>RC: {"Response":{"Status":{"Code":"SUCCESS","E2openTransactionId":"..."}}}
            RC-->>T: e2openTransactionId
            T->>SNS: logCloseRunEvent(CLOSE_WORKFLOW, success=true, tokens={PICK_UP_QUEUE, E2OPEN_TRANSACTION_ID})
        else HTTP 401
            SUB-->>RC: 401
            RC->>AC: newToken(oAuthRequest)
            AC->>OA: POST + Basic auth (force refresh)
            OA-->>AC: new Token
            Note over RC: rethrow -> retryer attempts again (up to 3 total)
        else HTTP 400 or 404
            SUB-->>RC: 400/404
            Note over RC: retryer.isRetryable == false -> no retry
            RC-->>T: RecoverableException (wraps the WAE)
            T-->>D: exception propagates (NOT caught by IOException/NonRecoverableException catch)
            D->>D: log.warn -> message stays on queue
            Note over SQS: message reappears after visibility timeout
        else HTTP 5xx or transient
            SUB-->>RC: 5xx / connect fail
            Note over RC: retryer retries up to 3 with exp backoff (100ms..)
            alt all attempts fail
                RC-->>T: RecoverableException
                T-->>D: exception propagates
                D->>D: log.warn -> message stays on queue
            end
        else Status.Code != "SUCCESS"
            SUB-->>RC: HTTP 200 + Code="ERROR"|"FAILURE"
            RC->>RC: throw NonRecoverableException("Error")
            Note over RC: outer catch wraps in RecoverableException
            RC-->>T: RecoverableException
            T-->>D: propagates -> message redelivered by SQS
        end
    end

    Note over T: On IOException (S3 read fail) or<br/>NonRecoverableException (escaping any unwrap):
    alt caught NonRecoverableException | IOException
        T->>EH: handleException(message, null, metaData, runId, startDateTime, tokens, ex)
        alt recoverable && attempts remaining
            EH->>SQS: re-send to pickup queue (count++ )
        else recoverable && attempts maxed
            EH->>DLQ: send to <pickupQueue>_dlq
        else non-recoverable
            EH->>DLQ: send to sqsErrorConfig (subscription_errors)
        end
        EH->>SNS: logCloseRunEvent(...status...)
    end

    D->>SQS: deleteMessage(receiptHandle) on success only
```

### 6.1 Message shape examples

**Inbound SQS message body** (illustrative — shape from `MetaData`):
```json
{
  "workflowId": "wf-2026-05-24-abc123",
  "bucket": "inttra2-pr-workspace",
  "fileName": "outbound/wf-2026-05-24-abc123/payload.json",
  "projections": {
    "SUBSCRIPTION_ID": "sub-9f3...c1"
  }
}
```

**Subscription `Action` of type `EDI_WEBHOOK`** (illustrative, drawn from `RequestBuilder.MESSAGE_CONFIG_ATTRS`):
```json
{
  "actionType": "EDI_WEBHOOK",
  "actionParameters": [
    {"name": "endPointUrl", "value": "https://api.subscriber.example.com/webhook"},
    {"name": "oAuthUrl",    "value": "https://auth.subscriber.example.com/oauth2/token"},
    {"name": "userid",      "value": "<client-id>"},
    {"name": "password",    "value": "<client-secret>"},
    {"name": "connectionId","value": "CONN-42"},
    {"name": "fromDuns",    "value": "123456789"},
    {"name": "toDuns",      "value": "987654321"},
    {"name": "dataType",    "value": "BOOKING"},
    {"name": "version",     "value": "1.0"}
  ]
}
```

**Outgoing HTTP request** (assembled by `RequestBuilder` + `RestServiceClient`):
```
POST https://api.subscriber.example.com/webhook?connectionId=CONN-42 HTTP/1.1
Authorization: bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json
fromDuns: 123456789
toDuns: 987654321
dataType: BOOKING
version: 1.0

<file content from S3, ISO-8859-1>
```

**Expected response body:**
```json
{
  "Response": {
    "Status": {
      "Code": "SUCCESS",
      "Text": "...",
      "E2openTransactionId": "E2-2026-1234567"
    }
  }
}
```

### 6.2 SQS-level message lifecycle

```mermaid
stateDiagram-v2
    [*] --> Visible
    Visible --> InFlight: ReceiveMessage by listener
    InFlight --> Deleted: process success -> AbstractTask.deleteMessage
    InFlight --> Visible: exception in process (visibility timeout expires)
    Visible --> DLQ: SQS redrive after maxReceiveCount
    InFlight --> Recovered: ErrorHandler.sendBackToPickupQueue
    Recovered --> Visible
    InFlight --> DLQ_Recoverable: ErrorHandler.sendToDLQ (recoverableAttempts maxed)
    InFlight --> ErrorQueue: ErrorHandler non-recoverable
    Deleted --> [*]
    DLQ --> [*]
    DLQ_Recoverable --> [*]
    ErrorQueue --> [*]
```

The redelivery behaviour is therefore the **union** of two mechanisms:

1. **SQS-native redelivery** when `process` raises any exception (because the message was never `deleteMessage`-d, it reappears after the queue's visibility timeout). This is how `RecoverableException` from `RestServiceClient` ends up being retried.
2. **`ErrorHandler` re-enqueuing** when `NonRecoverableException | IOException` is caught explicitly — these go through the structured DLQ path.

---

## 7. Component Dependencies

### 7.1 Maven dependency graph (logical)

```mermaid
graph TB
    subgraph appianway[appian-way parent pom]
        SHARED[mercury-shared 1.0]
    end

    subgraph this[distributor-rest 1.0]
        APP[DistributorApplication]
    end

    subgraph dropwizard["Dropwizard 4.0.16"]
        DWCORE[dropwizard-core]
        DWMETRICS[metrics-annotation 4.2.37]
    end

    subgraph aws["AWS SDK 1.12.720"]
        SQSSDK[aws-java-sdk-sqs]
        S3SDK[aws-java-sdk-s3<br/>transitive]
        SNSSDK[aws-java-sdk-sns<br/>transitive]
    end

    subgraph jersey["Jersey 3.1.11"]
        JC[jersey-common]
        JCL[jersey-client]
        JS[jersey-server]
        JHK2[jersey-hk2]
        JMP[jersey-media-multipart]
        JCS[jersey-container-servlet-core]
    end

    subgraph google["Google"]
        GUICE[guice 7.0.0]
        GUAVA[guava 33.1.0-jre]
        MG[metrics-guice 3.1.3]
    end

    subgraph testing[Testing]
        FT[functional-testing 1.0]
        MOCK[mockito-core 2.27.0]
        JU[junit 4.13.2]
        AJ[assertj-core 3.19.0]
    end

    LOMBOK[lombok 1.18.32]

    APP --> SHARED
    APP --> DWCORE
    APP --> DWMETRICS
    APP --> SQSSDK
    APP --> GUICE
    APP --> JC
    APP --> JCL
    APP --> JHK2
    APP --> JMP
    APP --> JS
    APP --> JCS
    APP --> MG
    APP --> GUAVA
    APP --> LOMBOK
    APP -. test .-> FT
    APP -. test .-> MOCK
    APP -. test .-> JU
    APP -. test .-> AJ

    SHARED --> SQSSDK
    SHARED --> SNSSDK
    SHARED --> S3SDK
```

### 7.2 Inter-service runtime dependencies

```mermaid
flowchart LR
    DRest[distributor-rest]
    SQSpick[(SQS pickup<br/>*_sqs_rest_delivery)]
    SQSerr[(SQS errors<br/>*_sqs_subscription_errors)]
    SQSdlq[(SQS DLQ<br/>*_sqs_rest_delivery_dlq)]
    SNStopic[(SNS<br/>*_sns_event)]
    S3wks[(S3 workspace<br/>*-workspace)]
    NSvc[Network Services API]
    SubEndpoint[[Subscriber<br/>REST endpoint]]
    SubOAuth[[Subscriber<br/>OAuth issuer]]
    ParamStore[(SSM<br/>Parameter Store)]

    DRest -->|long poll| SQSpick
    DRest -->|send-back / DLQ| SQSpick
    DRest -->|non-recoverable| SQSerr
    DRest -->|recoverable maxed| SQSdlq
    DRest -->|publish| SNStopic
    DRest -->|read| S3wks
    DRest -->|GET subscription / format / integration profile| NSvc
    DRest -->|POST + Bearer| SubEndpoint
    DRest -->|POST + Basic| SubOAuth
    DRest -->|GetParameter for clientSecret if usePassThrough=false| ParamStore
```

### 7.3 IAM dependencies (from prod task)

From [`conf/prod/distributor-rest-latest-prod-Task.json`](../conf/prod/distributor-rest-latest-prod-Task.json):
- `taskRoleArn = arn:aws:iam::642960533737:role/INTTRA2-ECS-PR-Distributor-Rest-Task` — this role needs:
  - `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:SendMessage`, `sqs:GetQueueAttributes` on `inttra2_pr_sqs_rest_delivery`, its `_dlq`, and `inttra2_pr_sqs_subscription_errors`.
  - `s3:GetObject` and `s3:PutObject` on `inttra2-pr-workspace` (the put covers `ErrorHandler.writeErrorsToS3`).
  - `sns:Publish` on `arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event`.
  - `ssm:GetParameter` for Network Services credentials (via shared `ParameterStoreModule`).

---

## 8. Configuration & Validation

### 8.1 Layered configuration model

Dropwizard reads `distributor-rest.yaml` (`distributor-rest.yaml`), and the `ConfigProcessingServerCommand` overlays multiple `.properties` files passed on the CLI (`run.sh:14`). The properties files supply env-specific values that the YAML substitutes via `${...}` placeholders. The four properties files at deploy time are:

| File | Source path | Purpose |
|---|---|---|
| `distributor-rest.properties` | [`conf/<env>/distributor-rest.properties`](../conf/) | App-specific values (queue URLs, S3 buckets, SNS topic, component name). |
| `network-services.properties` | `configuration/<env>/network-services.properties` (root-level, copied at build time per `build.sh:23`) | Network Services base URL, OAuth credentials, service paths. |
| `datadog.properties` | `configuration/<env>/datadog.properties` (root-level) | Metrics frequency, statsd target. |
| `distributor-rest.yaml` | [`conf/distributor-rest.yaml`](../conf/distributor-rest.yaml) | YAML template with `${var:-default}` defaults. |

The `build.sh` script renames each per-env properties file to `<name>.properties_<env>_conf`; the `run.sh` script then keeps only the file matching `$ENV` (`run.sh:10`).

### 8.2 Configuration reference

The top-level YAML structure (`distributor-rest.yaml`):

| Key | Type | Default | Required | Description | Validation |
|---|---|---|---|---|---|
| `componentName` | string | `distributor-rest` | Yes | Reported on close-run events; used by `ErrorHandler` to scope SNS messages. (`distributor-rest.yaml:1`) | `@NotEmpty` (`BaseConfiguration.java:18-19`) |
| `healthCheckConfig.errorRateThreshold` | double (<=2 int digits, <=2 fraction) | `5.0` | Yes | Moving-average error/sec ceiling intended to drive a health check. **Currently parsed but unused** in code. (`distributor-rest.yaml:5`) | `@NotNull`, `@Digits(integer=2, fraction=2)` (`HealthCheckConfig.java:16-17`) |
| `healthCheckConfig.networkServiceHealthCheckUrl` | string | — | Yes | URL hit by an intended Network Services health check; currently unused in code. (`distributor-rest.yaml:6`) | `@NotEmpty` (`HealthCheckConfig.java:20-21`) |
| `snsEventConfig.topicArn` | string | — | Yes | SNS topic to which close-run events are published. e.g. `arn:aws:sns:us-east-1:642960533737:inttra2_pr_sns_event`. (`distributor-rest.yaml:8-9`) | `@NotNull @Valid` from shared `SNSConfig` |
| `sqsErrorConfig.queueUrl` | string | — | Yes | Destination of *non-recoverable* failures. e.g. `.../inttra2_pr_sqs_subscription_errors`. (`distributor-rest.yaml:11-12`) | `@NotNull @Valid` (`BaseConfiguration.java:27-29`, `SQSConfig.java:12-13`) |
| `sqsPickupConfig.queueUrl` | string | — | Yes | The pickup queue. e.g. `.../inttra2_pr_sqs_rest_delivery`. (`distributor-rest.yaml:14-15`) | `@NotNull` |
| `sqsPickupConfig.waitTimeSeconds` | int | `20` | No | SQS long-poll wait. Max 20s. (`distributor-rest.yaml:16`) | (no annotation; range bound by SQS API) |
| `sqsPickupConfig.maxNumberOfMessages` | int | `5` | No | Per-poll batch size; also the dispatcher pool size. (`distributor-rest.yaml:17`) | (no annotation; SQS max 10) |
| `restClientConfig.connectTimeout` | string | `60000` | Yes | TCP connect timeout, ms. Passed as `String` to Jersey `ClientProperties.CONNECT_TIMEOUT` (Jersey accepts both). (`distributor-rest.yaml:20`, `RestClientConfig.java:11-12`) | `@NotNull` |
| `restClientConfig.readTimeout` | string | `60000` | Yes | Read timeout, ms. (`distributor-rest.yaml:21`) | `@NotNull` |
| `s3WorkspaceConfig.bucket` | string | — | Yes | Workspace bucket name where the payload lives. e.g. `inttra2-pr-workspace`. (`distributor-rest.yaml:24`) | `@NotNull @Valid` (shared) |
| `networkServiceConfig.networkBaseUrl` | string | — | Yes | Base URL for Network Services REST API. (`distributor-rest.yaml:27`) | `@NotNull` (`NetworkServiceConfig.java:18`) |
| `networkServiceConfig.authEndpointUrl` | string | — | Yes | Mercury-internal OAuth issuer for Network Services calls. (`distributor-rest.yaml:28`) | `@NotNull` |
| `networkServiceConfig.clientId` | string | — | Yes | Mercury Network Services client_id. (`distributor-rest.yaml:29`) | `@NotNull` |
| `networkServiceConfig.clientSecret` | string | — | Yes | Mercury Network Services client_secret (SSM key when `usePassThrough=false`). (`distributor-rest.yaml:30`) | `@NotNull` |
| `networkServiceConfig.usePassThrough` | bool | `false` | No | If true, `clientSecret` is used as-is; if false, it's a Parameter Store key. (`distributor-rest.yaml:31`) | (none) |
| `networkServiceConfig.servicePaths.integrationProfileServicePath` | string | — | Yes | Path under `networkBaseUrl` for integration-profile GET. (`distributor-rest.yaml:33`) | inherent in map (`@NotNull` on map) |
| `networkServiceConfig.servicePaths.integrationProfileFormatServicePath` | string | — | Yes | Path for integration-profile-format GET. (`distributor-rest.yaml:34`) | as above |
| `networkServiceConfig.servicePaths.formatServicePath` | string | — | Yes | Path for format GET. (`distributor-rest.yaml:35`) | as above |
| `networkServiceConfig.servicePaths.subscriptionSearchPath` | string | — | Yes | Path used by `SubscriptionService.findSubscriptions`. (`distributor-rest.yaml:36`) | as above |
| `server.connector.port` | int | `8081` | No | Dropwizard simple-connector HTTP port. (`distributor-rest.yaml:42`) | (Dropwizard validation) |
| `logging.level` | string | `INFO` | No | Root log level. (`distributor-rest.yaml:45`) | (Dropwizard validation) |
| `logging.loggers."com.inttra.mercury"` | string | `INFO` | No | App-package log level. (`distributor-rest.yaml:47`) | — |
| `logging.appenders` | list | `[{type: console, ...}]` | No | ISO-8601 console formatter with thread + 3-line stacktrace. (`distributor-rest.yaml:48-50`) | (Dropwizard) |
| `metrics.frequency` | string | (env) | Yes | Datadog metric push frequency (`distributor-rest.yaml:52`). Resolved via `datadog.properties` overlay. | — |

### 8.3 Per-environment property overlays

The four `.properties` files differ only in queue/SNS/S3 names — see this side-by-side:

| Key | INT (`int/distributor-rest.properties`) | QA (`qa/distributor-rest.properties`) | CVT (`cvt/distributor-rest.properties`) | PROD (`prod/distributor-rest.properties`) |
|---|---|---|---|---|
| `distributor.pickupSQSConfig.queueUrl` | `inttra_int_sqs_rest_delivery` | `inttra2_qa_sqs_rest_delivery` | `inttra2_cv_sqs_rest_delivery` | `inttra2_pr_sqs_rest_delivery` |
| `distributor.snsEventConfig.topicArn` | `inttra_int_sns_event` | `inttra2_qa_sns_event` | `inttra2_cv_sns_event` | `inttra2_pr_sns_event` |
| `distributor.sqsErrorSubscriptionConfig.queueUrl` | `inttra_int_sqs_subscription_errors` | `inttra2_qa_sqs_subscription_errors` | `inttra2_cv_sqs_subscription_errors` | `inttra2_pr_sqs_subscription_errors` |
| `distributor.s3WorkspaceConfig.bucket` | `inttra-int-workspace` | `inttra2-qa-workspace` | `inttra2-cv-workspace` | `inttra2-pr-workspace` |
| `distributor.s3OutboundConfig.bucket` | `inttra-int-outbound-delivery` | `inttra2-qa-outbound-delivery` | `inttra2-cv-outbound-delivery` | `inttra2-pr-outbound-delivery` |

Note: `distributor.s3OutboundConfig.bucket` is defined in every env's properties (`conf/prod/distributor-rest.properties:6`) but **not referenced** in `distributor-rest.yaml` — vestigial config. See section 13.

Note: INT account is `081020446316` (legacy "inttra-"), while QA/CVT/PROD all live in `642960533737` ("inttra2-"). The 2nd-gen naming/account migration is partial.

### 8.4 Resource excludes

`pom.xml:143-148` includes `conf/` as a resource directory but excludes all `*.properties` files. That means the YAML and any non-properties files in `conf/` get bundled into the JAR, but the env-specific `.properties` files are externalised — `build.sh` copies them onto the container next to the jar as `<file>_<env>_conf`, then `run.sh` renames the matching one to its final name.

### 8.5 Validation summary

| Layer | Mechanism |
|---|---|
| YAML key presence | Jakarta Bean Validation (`@NotNull`, `@NotEmpty`, `@Digits`) on the configuration classes; Dropwizard refuses to start on violations. |
| Endpoint URL shape | None — `endPointUrl` from the subscription is concatenated raw with the connection ID. A missing protocol would surface as a Jersey exception at runtime. |
| OAuth credential presence | None at config level; missing `userid`/`password` would yield a Base64-encoded `null:null` and a 401. |
| SQS queue existence | None at startup — first failed `ReceiveMessage` would surface in the listener loop. |

---

## 9. Maven Dependencies

All compile/runtime dependencies declared in [`pom.xml`](../pom.xml):

| Group:Artifact | Version | Scope | Purpose | pom.xml line |
|---|---|---|---|---|
| `com.inttra.mercury.shared:mercury-shared` | `1.0` (`${mercury.shared.version}`) | compile | Shared `BaseConfiguration`, `SQSListener`, `AbstractTask`, `ErrorHandler`, `S3WorkspaceService`, `SubscriptionService`, `EventLogger`, AWS client configs. | 22-27 |
| `io.dropwizard:dropwizard-core` | `4.0.16` (`${io.dropwizard.version}`) | compile | Application framework (config parsing, lifecycle, server, metrics). `snakeyaml` exclusion uses parent-provided version. | 28-38 |
| `io.dropwizard.metrics:metrics-annotation` | `4.2.37` (`${dropwizard.metrics.annotation}`) | compile | `@Metered`, `@Timed`, etc., consumed by `MetricsInstrumentationModule`. | 39-43 |
| `com.amazonaws:aws-java-sdk-sqs` | `1.12.720` (`${aws-java-sdk.version}`) | compile | SQS client. S3 + SNS SDKs are pulled in transitively via `mercury-shared`. | 44-49 |
| `com.google.inject:guice` | `7.0.0` (`${google-guice.version}`) | compile | DI container. | 50-54 |
| `org.glassfish.jersey.core:jersey-common` | `3.1.11` (`${jersey-version}`) | compile | JAX-RS base classes. | 55-59 |
| `org.glassfish.jersey.core:jersey-client` | `3.1.11` | compile | **JAX-RS Client used for the outbound POST and OAuth call.** | 60-64 |
| `org.glassfish.jersey.inject:jersey-hk2` | `3.1.11` | compile | HK2 injection provider required by Jersey 3.x. | 65-69 |
| `org.glassfish.jersey.media:jersey-media-multipart` | `3.1.11` | compile | Multipart support (not used directly here but bundled, possibly inherited need). | 70-74 |
| `org.glassfish.jersey.core:jersey-server` | `3.1.11` | compile | Server-side Jersey (Dropwizard's HTTP layer). | 75-79 |
| `org.glassfish.jersey.containers:jersey-container-servlet-core` | `3.1.11` | compile | Servlet integration for Dropwizard. | 80-84 |
| `com.palominolabs.metrics:metrics-guice` | `3.1.3` (`${metrics-juice.version}`) | compile | Guice AOP for metrics annotations (`MetricsInstrumentationModule`). | 85-89 |
| `com.google.guava:guava` | `33.1.0-jre` (`${google-guava.version}`) | compile | Immutable collections (`ImmutableMap` in `DistributorTask`). | 90-94 |
| `com.inttra.mercury.test:functional-testing` | `1.0` | test | Mercury functional-test harness. | 97-102 |
| `org.mockito:mockito-core` | `2.27.0` (`${mockito.version}`) | test | Unit-test mocking. | 103-108 |
| `junit:junit` | `4.13.2` (`${junit.version}`) | test | JUnit 4 runner. | 109-114 |
| `org.assertj:assertj-core` | `3.19.0` (`${assertj-core.version}`) | test | Fluent assertions. | 115-120 |
| `org.projectlombok:lombok` | `1.18.32` (`${lombok-version}`) | provided | `@Data`, `@Slf4j`, `@Getter/@Setter` boilerplate. | 123-128 |

### 9.1 Transitive items worth knowing

- **Jackson** comes in via Dropwizard. All `e2net.*` DTOs and `OAuthRequest`/`Token` use Jackson annotations (`@JsonProperty`, `@JsonInclude`, `@JsonIgnoreProperties`).
- **`com.github.rholder:guava-retrying`** comes in via `mercury-shared` (it is `import`ed in `RetryerBuilder.java:3` and `AuthClient.java:3`). It is **not** declared in this `pom.xml`.
- **`org.hibernate.validator`** for the deprecated `org.hibernate.validator.constraints.NotEmpty` used in `HealthCheckConfig.java:8` (still works under Dropwizard 4 / Jakarta Validation).

### 9.2 Build/package shape

- `pom.xml:163-196` shades the jar via `maven-shade-plugin 2.3` (note: this version of the plugin is old).
- The manifest's `Main-Class` is set to `com.inttra.mercury.distributorrest.DistributorApplication` (`pom.xml:190`).
- `META-INF/*.SF`, `*.DSA`, `*.RSA` are stripped (`pom.xml:171-174`) to avoid invalid-signature failures.
- `ServicesResourceTransformer` is applied (`pom.xml:186-187`) — essential for Jersey/HK2 to discover service providers via `META-INF/services`.

---

## 10. How the Module Works — Detailed Walkthrough

This section narrates the lifetime of one delivery from container start to ACK.

### 10.1 Container start

The ECS task launches with `command: ["/app/run.sh"]` (`conf/prod/distributor-rest-latest-prod-Task.json:20-22`) and environment `ENV=prod, JVM_Xmx=384m` (`prod-Task.json:9-17`).

`run.sh` (`run.sh:1-14`):
1. Renames `*_prod_conf` files to drop the suffix (so `distributor-rest.properties_prod_conf` becomes `distributor-rest.properties`).
2. Deletes all other `*_conf` artifacts.
3. Launches `java -Xmx384m -XX:+UseG1GC -jar -DCONFIG_REGION=US_EAST_1 distributor-rest.jar run distributor-rest.yaml ./distributor-rest.properties ./network-services.properties ./datadog.properties`.

`DistributorApplication.main` (`DistributorApplication.java:25-27`) calls `run(args)`, which:
1. `initialize(bootstrap)` registers `ConfigProcessingServerCommand` (`DistributorApplication.java:34`) — this is the command that consumes the multiple `.properties` files for placeholder substitution into the YAML.
2. The `run` subcommand parses `distributor-rest.yaml` with the overlaid properties -> `DistributorConfiguration` instance. Jakarta Bean Validation runs on the resulting object graph; any missing required key fails startup loudly.
3. `DistributorApplication.run(configuration, environment)` (`DistributorApplication.java:39-54`) builds the Guice injector.

### 10.2 Guice graph construction

Inside the injector creation (`DistributorApplication.java:45-47`):

1. `ExternalServicesModule.configure()` (`ExternalServicesModule.java:43-77`):
   - Builds the four AWS SDK clients with role-appropriate `ClientConfiguration` (timeouts, retries) from shared `AWSClientConfiguration`.
   - Wires the Network Services service binding cascade (cached impls).
   - **Eagerly constructs the shared `AuthClient`** (`ExternalServicesModule.java:65-66`) — this immediately calls the platform's `authEndpointUrl` with `clientId`/`clientSecret`. If credentials are wrong, container exits here.
   - Installs `ParameterStoreModule` — pulls the actual `clientSecret` from SSM if `usePassThrough=false`.
   - Installs `NetworkRetryerModule` (separate retryer for NS calls).
   - Binds `@Named("RestRetry")` to `RetryerBuilder.getRetryer()`.
   - Binds `@Named("RestClient")` to a Jersey client with `restClientConfig` timeouts applied.

2. `DistributorModule.configure()` (`DistributorModule.java:39-55`):
   - Binds `DistributorConfiguration` and `BaseConfiguration` to the same instance.
   - Constructs the `Dispatcher` (an `AsyncDispatcher` with a 5-thread pool by default).
   - Installs metrics AOP.

3. `@Provides` methods kick in lazily as `injector.getInstance(...)` is called:
   - `listenerManager(SQSListener)` (`DistributorModule.java:64-67`) -> `ListenerManager` containing one `SQSListener` (`DistributorModule.java:71-79`).
   - `snsEventPublisher(SNSClient)` -> singleton `SNSEventPublisher`.

4. `DistributorApplication.java:52` calls `injector.getInstance(ListenerManager.class)`, which forces creation of the full delivery graph.

5. `environment.lifecycle().manage(listenerManager)` (`DistributorApplication.java:53`) hands the listener manager to Dropwizard's lifecycle. When Dropwizard says `Server.start()`, `listenerManager.start()` runs, which in turn starts the SQS listener thread.

6. Dropwizard's HTTP server (simple connector, port 8081) starts. It serves the standard Dropwizard admin endpoints (`/healthcheck`, `/metrics`, `/ping`, `/threads`) but **no application resources are registered**. Jersey's `jersey-server` and `jersey-container-servlet-core` are still required because `dropwizard-core` is built on top of them.

### 10.3 Listener loop

`SQSListener.startup()` (`shared/.../SQSListener.java:90-110`):

```mermaid
flowchart TD
    A[startup]
    A --> B{isStop?}
    B -- no --> C[get idleThreadCount<br/>from dispatcher]
    C --> D{idle > 0?}
    D -- no --> B
    D -- yes --> E[ReceiveMessageRequest:<br/>waitTimeSeconds=20<br/>maxMsgs=idle]
    E --> F[receiveMessage]
    F --> G[dispatcher.submit<br/>messages, queueUrl]
    G --> B
    B -- yes --> Z[shutdown log]
```

The pollers tracks dispatcher availability via `dispatcher.getIdleThreadCount()` (`SQSListener.java:95`) — when the pool is saturated, the listener spins without polling, applying backpressure naturally. Long-poll wait is 20s (`distributor-rest.yaml:16`), so an idle JVM costs roughly one ReceiveMessage call per 20s.

### 10.4 Per-message processing

When a message arrives, `AsyncDispatcher` calls `task.execute(message, queueUrl)`. This routes through `AbstractTask.execute(...)` (`shared/.../AbstractTask.java:24-36`):

```
@Metered("messages-processed")
execute:
    startTime = currentTimeMillis()
    try:
        process(message, queueUrl)        <- DistributorTask.process
        deleteMessage(message)            <- removes from SQS
    catch (Exception):
        log.warn("Message is not processed; Message will reappear ", ex)
```

If `process` throws *anything*, `execute` swallows the exception and the message is **not** deleted. SQS visibility timeout governs when it next reappears.

`DistributorTask.process` (`DistributorTask.java:65-93`) — detailed pass:

**Step 1 — Time / RNG / Metadata**

```java
LocalDateTime startDateTime = LocalDateTime.now(clock);
final MetaData metaData = Json.fromJsonString(message.getBody(), MetaData.class);
runId = randomGenerator.randomUUID();
String subscriptionId = metaData.getProjections().get(MetaData.Projection.SUBSCRIPTION_ID);
```

`Json.fromJsonString` is the shared Jackson wrapper. The `runId` is a fresh UUID; this is the cross-component correlation id stamped on close-run events. `randomGenerator` is mocked in unit tests, real in prod.

**Step 2 — S3 payload fetch**

```java
String fileContent = workspaceService.getContent(metaData.getBucket(), metaData.getFileName(),
        StandardCharsets.ISO_8859_1);
```

The `S3WorkspaceService` is an `AmazonS3.getObject(...)` wrapper. `ISO_8859_1` is the canonical "byte-identity" charset (every byte 0x00-0xFF maps to the same Unicode codepoint), which avoids any re-encoding mishaps for binary-ish EDI payloads.

**Step 3 — Subscription lookup**

```java
Subscription subscription = subscriptionService.findSubscriptions(subscriptionId);
```

This hits the *cached* `SubscriptionService`. First call for a given `subscriptionId` is a Network Services round-trip; subsequent calls within the cache TTL are O(1). The cache is shared across tasks in the JVM.

**Step 4 — Request build**

```java
Request request = requestBuilder.build(subscription);
```

`RequestBuilder.build` (`RequestBuilder.java:23-53`):
1. Iterates `subscription.getActions()`. First `EDI_WEBHOOK` action triggers the inner block (the loop continues even after a match, which is harmless since the inner loop reads `subscription.getActions().get(0).getActionParameters()` — see section 13).
2. Iterates parameters and dispatches by name into `OAuthRequest` fields, headers map, or URL components.
3. Returns `Request{ url, headers, OAuthRequest }`.

**Step 5 — HTTP POST**

```java
transactionId = restServiceClient.post(request, fileContent);
```

`RestServiceClient.post` (`RestServiceClient.java:34-73`):

1. `WebTarget server = client.target(request.getUrl())` — note that `request.getUrl()` already contains the `?connectionId=...` part.
2. `retryer.call(Callable<ResponseWrapper>)` — the retryer (3 attempts, exp backoff, no-retry-on-400/404) executes the lambda:

   ```java
   String oAuthToken = authClient.getToken(request.getOAuthRequest()).getAccessToken();
   ResponseWrapper result = server.request()
       .headers(request.getHeaders())
       .header("Authorization", "bearer " + oAuthToken)
       .post(Entity.entity(fileContent, MediaType.APPLICATION_JSON), ResponseWrapper.class);
   ```

   - `authClient.getToken(...)` returns the cached token if any.
   - Headers (`fromDuns`, `toDuns`, `dataType`, `version`) are added via `MultivaluedMap`.
   - `Entity.entity(fileContent, APPLICATION_JSON)` sets `Content-Type: application/json`.
   - Jersey deserialises the response body as `ResponseWrapper` via Jackson.
3. On `WebApplicationException`:
   - Status 401 -> `authClient.newToken(...)` (synchronous token refresh).
   - Rethrow to let retryer decide (per `RetryerBuilder.isRetryable`, 400 and 404 are not retried — everything else, including 401 and 5xx, retries).
4. On success: if `response.getResponse().getStatus().getCode().equals("SUCCESS")` return `e2openTransactionId`, else throw `NonRecoverableException`.
5. Outer `catch (Exception e)` wraps anything raised by the retryer in `RecoverableException(e)` and rethrows.

**Step 6 — Close-run event**

```java
publishCloseRunEvent(message, metaData, startDateTime,
    ImmutableMap.of(Event.Token.PICK_UP_QUEUE, configuration.getSqsPickupConfig().getQueueUrl(),
                    Event.Token.E2OPEN_TRANSACTION_ID, transactionId));
```

This goes through `EventLogger.logCloseRunEvent` -> `SNSEventPublisher.publish` -> SNS topic `inttra2_pr_sns_event`. The event records: `runId`, `metaData`, `subType=CLOSE_WORKFLOW`, success flag, and token map.

**Step 7 — Error funnel**

```java
} catch (NonRecoverableException | IOException ex) {
    errorHandler.handleException(message, null, metaData, runId, startDateTime,
        ImmutableMap.of(Event.Token.PICK_UP_QUEUE, ...), ex);
}
```

Note that the immediately preceding section says `RestServiceClient` wraps everything (including `NonRecoverableException`) in `RecoverableException`. `RecoverableException` is **not** in this catch block. So the only paths through here are:
- `IOException` from `S3WorkspaceService.getContent` (e.g. S3 read failure).
- An unwrapped `NonRecoverableException` — in practice this is dead code given the current `RestServiceClient` behaviour.

See section 13. `ErrorHandler.handleException` then routes recoverable -> pickup queue / DLQ; non-recoverable -> error SQS (`shared/.../ErrorHandler.java:45-102`).

### 10.5 Token lifecycle

```mermaid
stateDiagram-v2
    [*] --> Cold: process start
    Cold --> Active: first call -> AuthClient.newToken<br/>POST oAuthUrl Basic Auth(userid:password)
    Active --> Active: subsequent calls hit cached Token
    Active --> Refreshing: HTTP 401 received in POST
    Refreshing --> Active: AuthClient.newToken (synchronized)
    Active --> [*]: container exit
```

The cache is **process-local** and has **no TTL** — only a 401 forces a refresh.

### 10.6 Shutdown

On `SIGTERM`:
1. Dropwizard runs `Server.stop()` -> all managed components stop in reverse-start order.
2. `ListenerManager.stop()` calls `SQSListener.shutdown()` (`shared/.../SQSListener.java:58-60`), setting the `interrupted` flag.
3. The next loop tick in `startup()` exits, logging "Listener ... has been shut down."
4. In-flight `DistributorTask`s in the `AsyncDispatcher` pool continue until the pool shuts down (`AsyncDispatcher.shutdown()`).
5. Jersey clients are not explicitly closed in this module; they will be reaped at JVM exit.

---

## 11. Error Handling & Edge Cases

The error model is layered. From innermost to outermost:

### 11.1 OAuth token call (`AuthClient`)

Retryer: 2 attempts, exp backoff, retries on **any** exception (`AuthClient.java:50-52`).

Edge cases:
- **OAuth endpoint unreachable** -> 2 retries, then exception propagates up. The caller (`RestServiceClient`'s retryer) treats this as just another retryable failure and re-enters its own loop. Effectively: up to `3 x 2 = 6` OAuth-call attempts per `DistributorTask` invocation.
- **OAuth returns 4xx (bad credentials)** -> 2 retries, then `WebApplicationException` propagates. The outer retryer (`RestServiceClient`) will not retry 400/404, will retry other 4xx (incl. 401, 403). 401 from OAuth would also trip the local `if (ex.getResponse().getStatus() == 401)` in `RestServiceClient.post` and call `newToken` again — though `newToken` is what just failed. Pathological case = ~6 attempts total before bubbling up as `RecoverableException`.
- **Race on cache:** Two tasks reach `getToken` simultaneously with null cache. Both invoke `newToken`. The first holds the monitor on the synchronized method, second waits. After the first writes `token`, the second overwrites it with the same value. One redundant OAuth call per "warm-up race".

### 11.2 Subscriber HTTP POST (`RestServiceClient`)

Retryer: 3 attempts, exp backoff from 100ms (`RetryerBuilder.java:13-14`).

Status-code matrix:

| HTTP status | Retried? | Side effects | Outcome |
|---|---|---|---|
| `200` + `Status.Code == "SUCCESS"` | n/a | None | Returns `e2openTransactionId`. |
| `200` + `Status.Code != "SUCCESS"` | n/a — the retry happens via `RecoverableException` wrap then SQS redelivery | Throws `NonRecoverableException("Error")` -> wrapped in `RecoverableException` by outer catch | **Bug-adjacent.** Despite the `NonRecoverableException` name, it ends up retried via SQS. See section 13. |
| `400` Bad Request | **No** (`RetryerBuilder.isRetryable` returns false) | Throws `WebApplicationException` -> wrapped in `RecoverableException` -> SQS redelivers anyway | Even though the retryer skips it, SQS redelivery still re-attempts. |
| `401` Unauthorized | Yes | `authClient.newToken(...)` called | Retried with fresh token. |
| `403` Forbidden | Yes | None | Retried up to 3 times. |
| `404` Not Found | **No** | None | Same as 400 — wrapped in `RecoverableException`, SQS redelivers. |
| `5xx` | Yes | None | Retried up to 3, then SQS redelivers. |
| Connection reset / socket timeout / DNS failure | Yes | None | Retried up to 3, then SQS redelivers. |

### 11.3 Exception wrapping in `RestServiceClient.post`

The combined catch is the most consequential single line:

```java
} catch (Exception e) {
    throw new RecoverableException(e);
}
```

This catches:
- `ExecutionException` from `Retryer.call` (when the callable kept throwing).
- `RetryException` from `Retryer.call` (when the stop strategy fired).
- The locally-thrown `NonRecoverableException` (because the `throw new NonRecoverableException("Error")` is *outside* the retryer's lambda, it bubbles up to this catch).
- Any unchecked exception, e.g. `NullPointerException` from `request.getUrl()` being null.

All become `RecoverableException`. This is **the load-bearing decision** of the module's error semantics: every non-SUCCESS outcome becomes "retry via SQS", and only the structured `ErrorHandler` path through the upper catch (`IOException | NonRecoverableException`) leads to DLQ/error SQS. See section 13 for the consequences.

### 11.4 S3 read failure

`workspaceService.getContent(...)` throws `IOException` on read failure. This *is* in `DistributorTask`'s catch (`DistributorTask.java:89`), so `ErrorHandler.handleException` runs. `ErrorHelper.isRecoverable(IOException)` will likely return true (transient S3 issue) -> bounced back to pickup queue up to `recoverableAttempts`, then to `_dlq`.

### 11.5 Missing subscription

`subscriptionService.findSubscriptions(subscriptionId)` returning null or an empty `actions` list: `RequestBuilder` would return a `Request` with `url = "null?connectionId=null"`. The subsequent `client.target(...)` would throw a Jersey URL parse exception -> caught by `RestServiceClient`'s outer catch -> `RecoverableException` -> SQS redelivery -> infinite-loop hazard until DLQ thresholds trip. See section 13.

### 11.6 `subscriptionId == null`

`DistributorTask.java:82-84` logs an error but proceeds to publish a *success-flagged* close-run event with empty transaction ID. The message will be deleted by `AbstractTask.execute` (because no exception propagated). **The message is silently dropped from the user's perspective**, but with a positive close-run event. See section 13.

### 11.7 DLQ pathways

Two distinct DLQ pathways exist:

1. **`<pickupQueue>_dlq`** — used by `ErrorHandler.handleRecoverableException` after `recoverableAttempts` is maxed (`shared/.../ErrorHandler.java:64-68`). Only reachable for `IOException`/`NonRecoverableException` (because those are the only paths into `errorHandler.handleException` in this task).
2. **`distributor.sqsErrorSubscriptionConfig.queueUrl`** (e.g. `inttra2_pr_sqs_subscription_errors`) — used by `ErrorHandler.handleNonRecoverableException` (`shared/.../ErrorHandler.java:90-102`). Same access constraint.

Failures coming from the `RestServiceClient` outer catch (i.e. all HTTP-layer failures) never reach `ErrorHandler` — they rely on **SQS's own** redrive policy on the pickup queue. The SQS-native DLQ (if configured at the queue level) will catch persistently-failing messages.

### 11.8 No circuit breaker

The pom has a *commented-out* line (`DistributorApplication.java:35`):
```
// bootstrap.addBundle(HystrixBundle.withDefaultSettings());
```
A Hystrix bundle import is still in the file (`DistributorApplication.java:15`). At one point a circuit breaker was wired; it has been disabled. Today there is no per-subscriber circuit breaker — a misbehaving subscriber will absorb retries until its `dlq` thresholds trip and then keep absorbing further messages individually.

---

## 12. Operational Notes

### 12.1 Deployment

- **Runtime image:** `e2openjre11` (selected by `build.sh:40` default) on top of the e2open CentOS base. Despite the image name, the project compiles at `java.version=17` (`parent pom:19`). The base image must in practice carry a JRE17.
- **JVM size:** `-Xmx384m` on a Fargate task reserving 384MiB (`prod-Task.json:14-16,24`). G1GC enabled (`run.sh:14`). Headroom is *very* tight given Jersey's client connection pool, Jackson deserialisation, and the subscription cache. Consider raising for any non-trivial subscriber base.
- **Ports:** Container exposes `8080` and `8081` (`prod-Task.json:25-35`). Only `8081` is actually bound by the app (`distributor-rest.yaml:42`). `8080` is documented but not configured — likely a copy-paste of the standard Dropwizard application/admin port pair.
- **Logging:** Console-only with awslogs driver shipping to CloudWatch group `inttra2-pr-lg-app-way`, stream prefix `AppianWay-distributor-rest-latest-prod` (`prod-Task.json:39-46`).
- **Metrics:** Datadog frequency comes from `${metrics.frequency}` in `datadog.properties` (overlay copied at build time, `build.sh:23`). Default code path in Dropwizard is 1s.

### 12.2 Observability

- **Dropwizard admin** on `:8081/admin` exposes `/metrics`, `/healthcheck`, `/threads`, `/ping`. No custom `HealthCheck` is registered, so the default healthcheck output may be empty — load-balancer / target-group health probes need to be aware.
- **Per-message metrics:**
  - `messages-processed` (`AbstractTask.MESSAGES_PROCESSED`, `shared/.../AbstractTask.java:11,22`) — meter via `@Metered`.
  - `messages-failed` (`ErrorHandler.MESSAGES_FAILED_METRIC`, `shared/.../ErrorHandler.java:23,44`) — meter.
- **Per-call timing** is logged at INFO level (not metered): `Time Taken for the REST call in ms: ...` (`RestServiceClient.java:49-50, 53-54`).

### 12.3 Sensitive-data exposure

- `RestServiceClient.java:43` logs `request.getHeaders()` at INFO. The headers do not contain credentials, but they do contain `fromDuns`, `toDuns`, `dataType`, `version` — operational metadata for the message. Acceptable.
- `AuthClient` does **not** log the Base64-encoded credential, but it does log the OAuth URL and timing (`AuthClient.java:44`). Acceptable.
- The OAuth `Token.accessToken` is not logged anywhere in the local code. Good.

### 12.4 Healthcheck strategy

There is none in this module. `HealthCheckConfig` parses two values that the code never consumes:
- `errorRateThreshold` — would feed a `MeterHealthCheck`.
- `networkServiceHealthCheckUrl` — would back a `WebHealthCheck`.

Neither is registered. The pragmatic mitigation today is to rely on Fargate/ECS container-level health (process alive). See section 13.

### 12.5 Scaling

- One JVM == 5 in-flight messages (default `maxNumberOfMessages`), bounded by the `AsyncDispatcher` pool.
- Horizontal scaling is unbounded (multiple ECS tasks polling the same queue). The OAuth token cache is per-process; multiple JVMs means N tokens for the same subscriber, which the subscriber's OAuth server must tolerate.
- The Network Services cache is per-process; warm-up cost on scale-out is one Network Services call per `subscriptionId`.

### 12.6 Failure modes worth alerting on

| Symptom | Likely cause | Where |
|---|---|---|
| Sustained `messages-failed` rate > 0 | Subscriber endpoint down/misbehaving, or S3 read failures. | `messages-failed` metric. |
| Message age on pickup queue rising | Pool saturated (slow subscriber), or listener stuck. | SQS `ApproximateAgeOfOldestMessage`. |
| Items accumulating in `<pickup>_dlq` | Recoverable attempts maxed -> only `IOException` paths. | SQS DLQ depth. |
| Items in `inttra2_*_sqs_subscription_errors` | Non-recoverable errors. | SQS errors-queue depth. |
| 401 spike correlated with one subscriber | Expired/revoked OAuth credentials for that subscriber. | Application logs `"Auth Service call failed"`. |
| Sustained 400/404 from a subscriber | Endpoint URL or connectionId wrong -> retries via SQS but never 4xx-stop. | Sub-second message reappearance on the queue. |

---

## 13. Open Questions / Risks

This section lists the surface areas a principal engineer would push on in review or hardening. Code references are inline.

### 13.1 Bug-adjacent: `NonRecoverableException` is swallowed by `RecoverableException`

`RestServiceClient.java:66-68` throws `NonRecoverableException` when the response code is not `SUCCESS`. The outer `catch (Exception e)` at line 70 then rewraps it as `RecoverableException`. The upstream `DistributorTask.java:89` only catches `NonRecoverableException | IOException`, so the wrapped form bypasses the structured error handler and falls back to SQS-native redelivery. Effect: **all bad-response messages are retried forever** (until SQS DLQ thresholds catch them at the queue level — assuming a redrive policy is configured on `inttra2_*_sqs_rest_delivery`).

Recommended:
- Either re-narrow the `RestServiceClient` outer catch so `NonRecoverableException` propagates unwrapped, or
- Translate "non-SUCCESS response with 200 OK" into a `NonRecoverableException` that `DistributorTask` actually catches.

### 13.2 Silent drop on missing `subscriptionId`

`DistributorTask.java:82-84` logs `"No subscriptionId !!!"` and falls through to publish a **success** close-run event with an empty `E2OPEN_TRANSACTION_ID`. Then `AbstractTask.execute` deletes the message. From a downstream perspective the message *succeeded*.

Recommended: either throw `NonRecoverableException` (so the message goes to the error queue) or skip the success event and let SQS redrive after visibility timeout.

### 13.3 `RequestBuilder` reads parameters from the wrong action

`RequestBuilder.java:32`:
```java
for (ActionParameter actionParameter : subscription.getActions().get(0).getActionParameters()) {
```
This iterates the parameters of `actions[0]`, not the current iteration's `action`. If a future caller emits a non-EDI_WEBHOOK action at index 0 (e.g. an `EMAIL` and an `EDI_WEBHOOK`), the wrong parameters are read. Today only EDI_WEBHOOK subscriptions reach this module so the bug is latent.

Recommended: change to `action.getActionParameters()`.

### 13.4 OAuth token cache is shared across all subscribers

`AuthClient` keeps a single `Token` field (`AuthClient.java:19`). The current customer base apparently uses a single OAuth realm, but the codepath has no awareness of *which* `OAuthRequest` produced the cached token. Two subscribers with different `oAuthUrl`/`userid`/`password` triplets would:
- Subscriber A goes first -> caches Token A.
- Subscriber B's task hits `getToken`, sees non-null `token` -> returns Token A.
- Subscriber B's POST -> 401 -> `newToken(B)` -> caches Token B.
- Subscriber A's next call -> returns Token B -> 401 -> refresh.
Resulting in oscillation between the two.

Recommended: key the cache by `OAuthRequest` (or by `oAuthUrl + ":" + clientUserId`).

### 13.5 Token TTL ignored

`Token.expires` is parsed but never honoured. Refresh only happens via 401, which is reactive. Some OAuth servers don't return 401 but instead a 403 or a 400 with `invalid_token`. In those cases the module will retry forever without refreshing.

Recommended: parse `expires` (or `Token.refreshToken`) and refresh proactively before TTL.

### 13.6 Unbounded outbound concurrency to a single subscriber

Five concurrent posts can hit the same subscriber endpoint if all five in-flight messages are for the same subscription. There is no per-subscriber concurrency cap or circuit breaker (Hystrix is commented out, `DistributorApplication.java:35`). A misbehaving subscriber will absorb 5x retry storms.

Recommended: a `Semaphore`-keyed-by-`endPointUrl` rate limiter, or revive a circuit-breaker bundle.

### 13.7 Healthcheck wired in config but never registered

`HealthCheckConfig` (`HealthCheckConfig.java`) is `@NotNull` on `DistributorConfiguration` but no code consumes it. Today the Dropwizard `/healthcheck` endpoint trivially returns "deadlock", "metrics", etc. The intended health checks against `networkServiceHealthCheckUrl` (Network Services reachability) and the `errorRateThreshold` (rate guard) are missing.

Recommended: implement and register a `WebHealthCheck` and a `MeterHealthCheck`, both wired from the existing config.

### 13.8 Dead config

- `EndpointConfig` class (`EndpointConfig.java`) is unreferenced.
- `distributor.s3OutboundConfig.bucket` appears in every env's properties but no YAML key maps to it.
- The double binding of `NetworkServiceConfig` and its `servicePaths` in both modules (`ExternalServicesModule.java:56-58` and `DistributorModule.java:49-50`) is redundant.

Recommended: cleanup pass.

### 13.9 Exception-swallowing on bootstrap

`DistributorApplication.java:48-50`:
```java
try { injector = Guice.createInjector(...); } catch (Exception ex) { ex.printStackTrace(); }
```
If injector creation throws, the next line `injector.getInstance(...)` NPEs and crashes the container. The `printStackTrace` adds nothing because Dropwizard's logger would log the original. The pattern reads as defensive cargo-culting.

Recommended: remove the `try/catch` and let the actual stack trace propagate via Dropwizard's logging.

### 13.10 Single global RestClient

A single `@Named("RestClient") Client` (`ExternalServicesModule.java:74-76, 86-91`) is used for all subscribers. JAX-RS clients are thread-safe but their connection pools are shared. With many subscribers on slow connections, head-of-line blocking can occur.

Recommended: configure the underlying `HttpUrlConnectionConfig` (or upgrade to the Apache HTTP Connector provider) with explicit per-route connection limits.

### 13.11 `RestClientConfig` timeouts typed as `String`

`RestClientConfig.connectTimeout` and `readTimeout` are typed as `String` (`RestClientConfig.java:11-16`), but the YAML provides them as integers (`distributor-rest.yaml:20-21`). Jersey's `ClientProperties.CONNECT_TIMEOUT` accepts both `Integer` and `String` so this works, but it bypasses validation (a non-numeric value would be accepted at config time and fail much later in Jersey).

Recommended: type as `Integer` + add `@Min(0)`.

### 13.12 Mockito 2.27 + JUnit 4 alongside JUnit 5 elsewhere

This module is still on JUnit 4 (`pom.xml:109-114`) and Mockito 2.27 (`pom.xml:103-108`). The rest of the codebase may have moved on. Test-stack churn risk on upgrades.

### 13.13 Old `maven-shade-plugin` version

`pom.xml:163-196` pins `maven-shade-plugin` to `2.3`, which is very old (current is 3.x). Known issues with Java 17 multi-release jars and `module-info.class` handling. Has not bitten yet but will when a transitive dependency starts shipping MR-jars.

### 13.14 INT environment account divergence

INT uses account `081020446316` with the legacy `inttra_int_*` naming, while QA/CVT/PROD use `642960533737` with `inttra2_*` (`conf/int/distributor-rest.properties` vs `conf/prod/distributor-rest.properties`). Disaster recovery and IAM templates have to be aware. Recommended: full migration of INT to the inttra2 account when feasible.

### 13.15 Empty `transactionId` treated as success

`RestServiceClient.java:64-65` returns whatever is in `e2openTransactionId`, including `null` and `""` (see test `postShouldHandleEmptyTransactionId`/`postShouldHandleNullTransactionId`, `RestServiceClientTest.java:506-552`). The downstream close-run event then carries an empty `E2OPEN_TRANSACTION_ID` token. Downstream consumers (audit, replay) cannot trace these.

Recommended: treat empty/null `e2openTransactionId` as a non-recoverable failure (the response was syntactically valid but semantically meaningless).

---

> **End of document.** Source files referenced (relative to this document):
> - [`../pom.xml`](../pom.xml)
> - [`../run.sh`](../run.sh), [`../build.sh`](../build.sh), [`../build_pr.sh`](../build_pr.sh)
> - [`../conf/distributor-rest.yaml`](../conf/distributor-rest.yaml)
> - [`../conf/cvt/distributor-rest.properties`](../conf/cvt/distributor-rest.properties), [`../conf/int/distributor-rest.properties`](../conf/int/distributor-rest.properties), [`../conf/qa/distributor-rest.properties`](../conf/qa/distributor-rest.properties), [`../conf/prod/distributor-rest.properties`](../conf/prod/distributor-rest.properties)
> - [`../conf/cvt/distributor-rest-latest-cvt-Task.json`](../conf/cvt/distributor-rest-latest-cvt-Task.json), [`../conf/int/distributor-rest-latest-dev-Task.json`](../conf/int/distributor-rest-latest-dev-Task.json), [`../conf/qa/distributor-rest-latest-qa-Task.json`](../conf/qa/distributor-rest-latest-qa-Task.json), [`../conf/prod/distributor-rest-latest-prod-Task.json`](../conf/prod/distributor-rest-latest-prod-Task.json)
> - [`../src/main/java/com/inttra/mercury/distributorrest/DistributorApplication.java`](../src/main/java/com/inttra/mercury/distributorrest/DistributorApplication.java)
> - [`../src/main/java/com/inttra/mercury/distributorrest/auth/AuthClient.java`](../src/main/java/com/inttra/mercury/distributorrest/auth/AuthClient.java), [`../src/main/java/com/inttra/mercury/distributorrest/auth/OAuthRequest.java`](../src/main/java/com/inttra/mercury/distributorrest/auth/OAuthRequest.java)
> - [`../src/main/java/com/inttra/mercury/distributorrest/config/DistributorConfiguration.java`](../src/main/java/com/inttra/mercury/distributorrest/config/DistributorConfiguration.java), [`../src/main/java/com/inttra/mercury/distributorrest/config/EndpointConfig.java`](../src/main/java/com/inttra/mercury/distributorrest/config/EndpointConfig.java), [`../src/main/java/com/inttra/mercury/distributorrest/config/HealthCheckConfig.java`](../src/main/java/com/inttra/mercury/distributorrest/config/HealthCheckConfig.java), [`../src/main/java/com/inttra/mercury/distributorrest/config/RestClientConfig.java`](../src/main/java/com/inttra/mercury/distributorrest/config/RestClientConfig.java)
> - [`../src/main/java/com/inttra/mercury/distributorrest/e2net/Response.java`](../src/main/java/com/inttra/mercury/distributorrest/e2net/Response.java), [`../src/main/java/com/inttra/mercury/distributorrest/e2net/ResponseWrapper.java`](../src/main/java/com/inttra/mercury/distributorrest/e2net/ResponseWrapper.java), [`../src/main/java/com/inttra/mercury/distributorrest/e2net/Status.java`](../src/main/java/com/inttra/mercury/distributorrest/e2net/Status.java), [`../src/main/java/com/inttra/mercury/distributorrest/e2net/Token.java`](../src/main/java/com/inttra/mercury/distributorrest/e2net/Token.java)
> - [`../src/main/java/com/inttra/mercury/distributorrest/modules/DistributorModule.java`](../src/main/java/com/inttra/mercury/distributorrest/modules/DistributorModule.java), [`../src/main/java/com/inttra/mercury/distributorrest/modules/ExternalServicesModule.java`](../src/main/java/com/inttra/mercury/distributorrest/modules/ExternalServicesModule.java), [`../src/main/java/com/inttra/mercury/distributorrest/modules/RetryerBuilder.java`](../src/main/java/com/inttra/mercury/distributorrest/modules/RetryerBuilder.java)
> - [`../src/main/java/com/inttra/mercury/distributorrest/task/DistributorTask.java`](../src/main/java/com/inttra/mercury/distributorrest/task/DistributorTask.java), [`../src/main/java/com/inttra/mercury/distributorrest/task/NonRecoverableException.java`](../src/main/java/com/inttra/mercury/distributorrest/task/NonRecoverableException.java), [`../src/main/java/com/inttra/mercury/distributorrest/task/Request.java`](../src/main/java/com/inttra/mercury/distributorrest/task/Request.java), [`../src/main/java/com/inttra/mercury/distributorrest/task/RequestBuilder.java`](../src/main/java/com/inttra/mercury/distributorrest/task/RequestBuilder.java), [`../src/main/java/com/inttra/mercury/distributorrest/task/RestServiceClient.java`](../src/main/java/com/inttra/mercury/distributorrest/task/RestServiceClient.java)
> - Shared module (selected): [`../../shared/src/main/java/com/inttra/mercury/shared/config/BaseConfiguration.java`](../../shared/src/main/java/com/inttra/mercury/shared/config/BaseConfiguration.java), [`../../shared/src/main/java/com/inttra/mercury/shared/config/NetworkServiceConfig.java`](../../shared/src/main/java/com/inttra/mercury/shared/config/NetworkServiceConfig.java), [`../../shared/src/main/java/com/inttra/mercury/shared/config/SQSConfig.java`](../../shared/src/main/java/com/inttra/mercury/shared/config/SQSConfig.java), [`../../shared/src/main/java/com/inttra/mercury/shared/listener/SQSListener.java`](../../shared/src/main/java/com/inttra/mercury/shared/listener/SQSListener.java), [`../../shared/src/main/java/com/inttra/mercury/shared/task/AbstractTask.java`](../../shared/src/main/java/com/inttra/mercury/shared/task/AbstractTask.java), [`../../shared/src/main/java/com/inttra/mercury/shared/task/ErrorHandler.java`](../../shared/src/main/java/com/inttra/mercury/shared/task/ErrorHandler.java)
