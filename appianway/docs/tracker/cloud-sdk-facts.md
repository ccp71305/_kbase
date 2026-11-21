# cloud-sdk facts from the step-1c research (cloud-sdk 1.0.38)

← [Tracker home](README.md)


- Factories always set an API-call timeout (S3 30 s via `BaseAwsConfig`, SQS 30 s, SNS 10 s, SSM 10 s); zero rejected → [DR-2](decisions.md#dr-2) caps. `ParameterStoreClientFactory` ignores the configured `RetryStrategy`.
- `AwsHttpClientWrapper.ofSyncBuilder(ApacheHttpClient.builder())` = one pool per SDK client, owned and closed by it; cloud-sdk default transport is connect 5 s / socket 30 s / 50 connections.
- `AwsMessagingClientConfig.build()` requires `queueUrl`, `maxConnections > 0`, `maxMessages` 1–10 (validated before defaults); `maxConnections` / `visibilityTimeout` / `threadPoolSize` are not used by the factory.
- `SqsMessagingClient.receiveMessages`: sends queue URL, max messages, wait time, message attribute names (if any); **never** a visibility timeout. Messages: `getMessageAttributes()` = String values only; `getAttributes()` = system attributes. Send: `DelaySeconds` only if > 0; attributes as DataType `String`. `getQueueAttributes` asks for `All`.
- `SqsMessagingClient` / `SnsService` / `S3StorageClient` / `SsmCloudParameterStore` have public constructors; `ManagedCloudResource.of(resource, name)` (cloud-sdk-api) is the Dropwizard lifecycle adapter; only `SqsMessagingClient.close()` closes its SDK client.
- `S3StorageClient(S3Client)` logs the access key id at INFO (set `com.inttra.mercury.cloudsdk` to WARN; [A22](closed-items.md#a22)).
- mercury-services reference for retry/config builders: `mercury-services/booking-downstream-processor/booking-cargoscreen/src/main/java/.../config/BookingCargoScreenApplicationInjector.java:139-246`.

Later versions changed some of these (1.0.39: no-API-call-timeout option, SSM retry strategy, no access-key log). See [A22](closed-items.md#a22).
