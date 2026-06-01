# appianway — AWS SDK v1 surface inventory (per module)

Date mapped: 2026-05-31. For AWS v1 → cloud-sdk (v2) migration planning. Source: grep `com.amazonaws` across aggregator modules.

## shared (chokepoint — every service depends on it)
S3WorkspaceService/WorkspaceService (AmazonS3), AWSUtil (RetryUtils), SQSClient/SNSClient/SQSListenerClient (AmazonSQS/SNS), SQSListener (v1 Message flows to Dispatcher→AbstractTask→every Task), AWSClientConfigHelper/Configuration, ParameterStore (SSM), 5 health checks build own v1 clients via *ClientBuilder.defaultClient().

## No-AWS modules (transitive/build impact only)
- schema-beans — JAXB beans only.
- structuralvalidator — XSD validation library, no com.amazonaws.
- gen2-parser — parser, no com.amazonaws.

## Standard SQS-consumer services (bind AWS in own modules/ExternalServicesModule via *ClientBuilder.standard().withClientConfiguration(AWSClientConfiguration.*))
**CORRECTION (verified by direct read 2026-05-31): splitter/transformer/distributor-rest/ingestor are NOT DTO-only — they each bind their own AWS clients in ExternalServicesModule, like the others. Earlier "DTO-only" classification was wrong (grep had truncated at 200 matches dominated by functional-testing's SES adaptor).**
- event-writer — AmazonSQS (listener+sender) + AmazonS3.
- dispatcher — AmazonSQS + AmazonSNS + AmazonS3; also S3EventNotification, ObjectMetadata, util.IOUtils.
- distributor — AmazonS3 (+SQS via shared); util.IOUtils for ZipCompression.
- error-processor — AmazonSQS + AmazonSNS + AmazonS3.
- splitter — AmazonSQS (listener+sender) + AmazonS3 + AmazonSNS in ExternalServicesModule. Standard consumer.
- transformer — AmazonSQS + AmazonS3 + AmazonSNS **+ AmazonDynamoDB/DynamoDBMapper/DynamoDBMapperConfig(CONSISTENT)**. Owns annotated VO `controlnumbers/sequence/ControlNumberSequence` (@DynamoDBHashKey/@DynamoDBAttribute/**@DynamoDBVersionAttribute** optimistic-lock/@DynamoDBIgnore) + `ControlNumberSequenceDao`. SECOND DynamoDB module (Enhanced-Client rewrite like watermill). Contivo com.contivo:commons (lib/ + contivo-lib/) is the Contivo runtime — UNRELATED, do-not-touch.
- distributor-rest — AmazonSQS (listener+sender) + AmazonS3 + AmazonSNS. Standard consumer; HTTP/OAuth egress is non-AWS.
- ingestor — AmazonSQS (listener+sender) + AmazonS3 (NO SNS). Standard consumer; Jest/Elasticsearch is non-AWS-SDK, out of scope.

## DynamoDB users (only TWO in the whole aggregator): transformer (control-number sequence) and watermill (offset store). No other built module uses DynamoDB.

## SES (special)
- email-sender — consumes SQS Message (shared) + sends via AmazonSimpleEmailService (simpleemail.model.SendEmailRequest/Result). Maps to cloud-sdk-api EmailService / cloud-sdk-aws SesEmailServiceImpl (SES **v2**) — behavior change SES classic→SESv2.

## DynamoDB (special — watermill side-bus)
- watermill (aggregator) sub-modules: consumer-commons, itv-gps-consumer, cargoscreen-consumer, booking-inbound-consumer, visibility-inbound-consumer.
  - DynamoDB v1: AmazonDynamoDB, AmazonDynamoDBClientBuilder, datamodeling.{DynamoDBMapper,DynamoDBMapperConfig,DynamoDBTable,DynamoDBHashKey,DynamoDBAttribute,DynamoDBTypeConverter/Converted}, model.{CreateTableRequest,ProvisionedThroughput,SSESpecification,StreamViewType}, util.TableUtils.
  - Files: DynamoSupport, WatermillOffsetDao, WatermillOffset (VO with datamodeling annotations), DateToEpochSecond converter, DynamoTableCommand, WatermillConsumerModule, ExternalServicesModule (S3+SNS+SQS), S3PublishService (AmazonS3 + PutObjectResult).
  - Target: cloud-sdk-aws Dynamo support + `dynamo-integration-test` (test). DynamoDBMapper→Enhanced Client (v2) is the biggest rewrite in the repo. gRPC unaffected.
- watermill-publisher — SQS + S3 (own AsyncDispatcher/Task copies), DeadLetterService (ReceiveMessageRequest/Result), WatermillPubTask (Message DTO), task/Test.java (throwaway main). gRPC publisher.

## functional-testing (special — test SDK; biggest fake-rework)
In-memory AWS v1 fakes implementing full v1 interfaces:
- AmazonS3Adaptor implements AmazonS3 (hundreds of methods, S3ClientOptions/S3ResponseMetadata/model.*).
- AmazonSESAdaptor implements AmazonSimpleEmailService (full SES classic surface + waiters).
- AmazonSQS / AmazonSNS fakes; FunctionalTestBase wires them.
Must be re-pointed to cloud-sdk-api interfaces (StorageClient/MessagingClient/NotificationService/EmailService) OR re-implemented as v2 fakes. This is the lockstep change that unblocks every downstream service test compile. Test scope in every service.

## Target libraries (mercury-services-commons, separate workspace)
cloud-sdk-api (interfaces) + cloud-sdk-aws (impls/factories), AWS SDK v2 BOM 2.30.24, commons=Dropwizard 5.0.1. Pin a released cloud-sdk version (not 1.0.26-SNAPSHOT). Recommended option for appianway = Option A (keep shared/Dropwizard 4/JUnit 4, delegate AWS wrappers to cloud-sdk).
