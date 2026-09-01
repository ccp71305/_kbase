# pi-commons Test AWS SDK Migration Plan

Date: 2026-08-20

## Scope
Migrate the pi-commons JUnit 5 test sources from AWS SDK v1 model/client types to the in-house cloud-sdk APIs and AWS SDK v2 SQS request type already used by main sources.

## Current state
Main sources already compile against `StorageClient`, `MessagingClient<String>`, `QueueMessage<String>`, `ReceiveMessageOptions`, and AWS SDK v2 `SqsClient`/`SendMessageRequest`. The remaining test sources still import AWS SDK v1 S3, SQS, and DynamoDB classes.

## Changes planned
- Delete `DynamoSupportTest` because `DynamoSupport` was removed during migration.
- Update `S3WorkspaceServiceTest` to mock `StorageClient` and `StorageObject`, verify void `putObject`/copy calls, and assert `SdkException` wrapping.
- Update `SQSClientTest` to mock `MessagingClient<String>` and AWS SDK v2 `SqsClient`, verifying plain send/delete delegation and delayed send request fields.
- Update listener, task, and dispatcher tests to use `QueueMessage<String>` and `ReceiveMessageOptions`.
- Replace immediate idle-thread assertions after asynchronous completion with a bounded wait for restored permits.

## Verification
Run `mvn -f partner-integrator/pom.xml -pl pi-commons test` and iterate until the build reports success with zero failures/errors.
