---
name: booking-integration-issues
description: fixing booking integration issues
argument-hint: "none"
agent: agent
model: Claude Opus 4.6 (copilot)
tools:
  - execute
  - read
  - edit
  - search
  - todo
  - agent
  - vscode
  - mcp-context-server/*
---
# Task instructions

## Reported issues >>
All of these issues needs to be fixed and missing unit tests which could have reproduced these bugs needs to be added

1) Status:    visibility-matcher/exception/visibility-matcher -> BookingDetailVisibility[enrichedAttributes]; could not unconvert attribute
com.inttra.mercury.visibility.matcher.processor.MatchingProcessor: Container Event Id: ce:24686632-1e9f-435c-ab21-5bfa405626aa - Failed Matching Processor
com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMappingException: BookingDetailVisibility[enrichedAttributes]; could not unconvert attribute
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperTableModel.unconvert(DynamoDBMapperTableModel.java:271)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapper.privateMarshallIntoObject(DynamoDBMapper.java:472)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapper.marshallIntoObjects(DynamoDBMapper.java:500)
	at com.amazonaws.services.dynamodbv2.datamodeling.PaginatedQueryList.<init>(PaginatedQueryList.java:65)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapper.query(DynamoDBMapper.java:1619)
	at com.amazonaws.services.dynamodbv2.datamodeling.AbstractDynamoDBMapper.query(AbstractDynamoDBMapper.java:285)
	at com.inttra.mercury.dynamo.respository.DynamoDBCrudRepository.query(DynamoDBCrudRepository.java:380)
	at com.inttra.mercury.dynamo.respository.DynamoDBCrudRepository.query(DynamoDBCrudRepository.java:340)
	at com.inttra.mercury.dynamo.respository.DynamoDBCrudRepository.query(DynamoDBCrudRepository.java:328)
	at com.inttra.mercury.dynamo.respository.DynamoDBCrudRepository.query(DynamoDBCrudRepository.java:270)
	at com.inttra.mercury.visibility.common.booking.BookingDao.findBookingDetail(BookingDao.java:118)
	at com.inttra.mercury.visibility.common.booking.BookingDao.findByInttraReferenceNumber(BookingDao.java:49)
	at com.inttra.mercury.visibility.common.booking.BookingDao.findBookingByInttraReference(BookingDao.java:81)
	at com.inttra.mercury.visibility.common.booking.BookingServiceImpl.getBookingByInttraRef(BookingServiceImpl.java:22)
	at com.inttra.mercury.visibility.matcher.processor.elasticsearch.TransactionSearchService.addInttraReference(TransactionSearchService.java:204)
	at com.inttra.mercury.visibility.matcher.processor.elasticsearch.TransactionSearchService.lambda$enrichContainerEvent$1(TransactionSearchService.java:177)
	at java.base/java.util.ArrayList.forEach(Unknown Source)
	at com.inttra.mercury.visibility.matcher.processor.elasticsearch.TransactionSearchService.enrichContainerEvent(TransactionSearchService.java:165)
	at com.inttra.mercury.visibility.matcher.processor.elasticsearch.TransactionSearchService.updateContainerEventFromElasticSearchResults(TransactionSearchService.java:149)
	at com.inttra.mercury.visibility.matcher.processor.elasticsearch.TransactionSearchService.findMatchingTransactions(TransactionSearchService.java:61)
	at com.inttra.mercury.visibility.matcher.processor.MatchingProcessor.process(MatchingProcessor.java:105)
	at com.inttra.mercury.visibility.common.processor.sqs.SqsMessageHandler$1.run(SqsMessageHandler.java:109)
	at com.inttra.mercury.visibility.common.processor.threading.BoundedThreadPool$1.run(BoundedThreadPool.java:64)
	at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(Unknown Source)
	at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(Unknown Source)
	at java.base/java.lang.Thread.run(Unknown Source)
Caused by: com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMappingException: EnrichedAttributes[containerTypeList]; could not unconvert attribute
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperTableModel.unconvert(DynamoDBMapperTableModel.java:271)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardModelFactories$Rules$ObjectDocumentMap$1.unconvert(StandardModelFactories.java:633)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardModelFactories$Rules$ObjectDocumentMap$1.unconvert(StandardModelFactories.java:628)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$DelegateConverter.unconvert(DynamoDBTypeConverter.java:109)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$NullSafeConverter.unconvert(DynamoDBTypeConverter.java:128)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$ExtendedConverter.unconvert(DynamoDBTypeConverter.java:88)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperFieldModel.unconvert(DynamoDBMapperFieldModel.java:146)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperFieldModel.unconvertAndSet(DynamoDBMapperFieldModel.java:164)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperTableModel.unconvert(DynamoDBMapperTableModel.java:267)
	... 25 common frames omitted
Caused by: com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMappingException: ContainerType[lastModifiedDateUtc]; could not unconvert attribute
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperTableModel.unconvert(DynamoDBMapperTableModel.java:271)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardModelFactories$Rules$ObjectDocumentMap$1.unconvert(StandardModelFactories.java:633)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardModelFactories$Rules$ObjectDocumentMap$1.unconvert(StandardModelFactories.java:628)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$DelegateConverter.unconvert(DynamoDBTypeConverter.java:109)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$NullSafeConverter.unconvert(DynamoDBTypeConverter.java:128)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$ExtendedConverter.unconvert(DynamoDBTypeConverter.java:88)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$DelegateConverter.unconvert(DynamoDBTypeConverter.java:109)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardTypeConverters$Vector$ToList.unconvert(StandardTypeConverters.java:393)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardTypeConverters$Vector$ToList$1.unconvert(StandardTypeConverters.java:377)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardTypeConverters$Vector$ToList$1.unconvert(StandardTypeConverters.java:370)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$DelegateConverter.unconvert(DynamoDBTypeConverter.java:109)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$NullSafeConverter.unconvert(DynamoDBTypeConverter.java:128)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$ExtendedConverter.unconvert(DynamoDBTypeConverter.java:88)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperFieldModel.unconvert(DynamoDBMapperFieldModel.java:146)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperFieldModel.unconvertAndSet(DynamoDBMapperFieldModel.java:164)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperTableModel.unconvert(DynamoDBMapperTableModel.java:267)
	... 33 common frames omitted
Caused by: java.lang.IllegalArgumentException: Invalid format: "2018-02-27 16:59:38" is malformed at " 16:59:38"
	at org.joda.time.format.DateTimeParserBucket.doParseMillis(DateTimeParserBucket.java:187)
	at org.joda.time.format.DateTimeFormatter.parseMillis(DateTimeFormatter.java:826)
	at com.amazonaws.util.DateUtils.doParseISO8601Date(DateUtils.java:109)
	at com.amazonaws.util.DateUtils.parseISO8601Date(DateUtils.java:88)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardTypeConverters$ToDate$4.convert(StandardTypeConverters.java:689)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardTypeConverters$ToDate$4.convert(StandardTypeConverters.java:686)
	at com.amazonaws.services.dynamodbv2.datamodeling.StandardTypeConverters$1.unconvert(StandardTypeConverters.java:75)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$DelegateConverter.unconvert(DynamoDBTypeConverter.java:109)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$NullSafeConverter.unconvert(DynamoDBTypeConverter.java:128)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBTypeConverter$ExtendedConverter.unconvert(DynamoDBTypeConverter.java:88)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperFieldModel.unconvert(DynamoDBMapperFieldModel.java:146)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperFieldModel.unconvertAndSet(DynamoDBMapperFieldModel.java:164)
	at com.amazonaws.services.dynamodbv2.datamodeling.DynamoDBMapperTableModel.unconvert(DynamoDBMapperTableModel.java:267)

	2) Booking Outbound generation is breaking
	The **transformer** (`appianway/shared`) deserializes `MetaData.timestamp` using a `LocalDateTimeDeserializer` registered with pattern `"yyyy-MM-dd HH:mm:ss.SS"` (space separator). It cannot parse the 'T' format and throws:
	```
DateTimeParseException: Text '2026-04-21T14:30:18.66' could not be parsed at index 10
→ MetaData$Builder["timestamp"]
→ TransformerTask.process(TransformerTask.java:82)
→ "Message is not processed; Message will reappear"
```

```
Booking-qa
	└─► S3 workspace (inttra2-qa-workspace/{rootWorkflowId}/{fileId})
	└─► SQS: inttra2_qa_sqs_transformer_inbound  ◄─── BROKEN POINT (see Bug #1)
				└─► transformer-qa
							└─► S3 (transformed EDI file)
							└─► SQS: inttra2_qa_sqs_file_delivery
										└─► distributor-qa
													└─► S3: inttra2-qa-outbound-delivery/customers/{id}/outbound/
	└─► SNS: inttra2_qa_sns_event
				├─► SQS: inttra2_qa_sqs_ingest  →  ingestor-qa
				└─► SQS: inttra2_qa_sqs_event   →  event-writer-qa
```


The transformer module is in workspace C:\Users\arijit.kundu\projects\appianway

The metaData.timestamp written to the SQS from Booking module is now in format "timestamp": "2026-04-21T14:30:18.66"

3) Check the Distributor module in workspace C:\Users\arijit.kundu\projects\appianway as well for any impact 

4) Check the workspace C:\Users\arijit.kundu\projects\mft-s3-aqua-appia for the modules "aw-bridge-ib" and "aw-bridge-ob" as well for any impact. 

## Facts

- Both visibility and booking modules refer to the same dynamo db table "BookingDetail"
For booking module, the environment prefix is inttra2_prod_booking (for production config.yaml)
For visibility module, the environment prefix is inttra2_prod

- Both visibility module (still in AWS 1.x) and booking module (AWS 2.x upgraded using cloud-sdk libraries) read and write to this same database table

- The data format for each fields should remain consistent such that 
--  booking module is able to read all old records as well as new records in BookingDetail.
--  visibility module and other modules not aws upgraded yet and using pre-upgrade booking model "booking:2.1.8.M" should also be able to read 

ALL  old as well as NEW records written by upgraded booking module in BookingDetail table 

- In production today, the metaData.timeStamp is like "timestamp": {
				"S": "2026-04-22T18:32:37.65"
			}

	and the containerType.lastModifiedUtc is like "lastModifiedDateUtc": {
									"S": "2018-02-27T16:59:38.000Z"
								}

- A sample message from Production after successful transformer processing as below:
"messageId": "20df5856-b9c0-4ca1-a2ed-0506be0ae07a",
      "workflowId": "be6027fb-21c2-4205-9599-06253a9d598f",
      "rootWorkflowId": "3cfb71f0-8381-41a3-90a3-2ae050770e48",
      "parentWorkflowId": "3cfb71f0-8381-41a3-90a3-2ae050770e48",
      "bucket": "inttra2-pr-workspace",
      "fileName": "3cfb71f0-8381-41a3-90a3-2ae050770e48/191f2f0f-e1ad-4b8a-95a1-58822d94892d",
      "component": "transformer",
      "exitStatus": "success",
      "timestamp": "2026-04-22 18:32:37.65",
      "projections": {
        "originalFileName": "IBK2026042216822.xml",
        "inboundS3FileName": "300_IFTMBF/20260422/customers/m0166602/IBK2026042216822.xml",
        "formatCode": "I_BK_XML_V_2_0",
        "mftId": "m0166602",
        "s3EventCreationTime": "2026-04-22 18:32:36.33",
        "inftpfilepickuptime": "2026-04-22 18:32:36.00",
        "contextCode": "requestBooking",
        "xlogId": "5422434659",
        "integrationProfileId": "4585",
        "splitterFileSize": "15036",
        "pickupFileName": "300_IFTMBF/20260422/customers/m0166602/IBK2026042216822.xml",
        "formatId": "126",
        "originalFileSize": "15036",
        "dispatcherStartRunTime": "2026-04-22 18:32:37.21",
        "ediId": "KEWILLMICHELIN",
        "fileType": "300_IFTMBF",
        "integrationProfileFormatId": "6332"
      }

	- Invalid metaData timestamp from failed QA with no Outbound 
	"messageId": "fe088b9f-deba-4135-8033-30e6a48918d2",
      "workflowId": "c304a43a-9819-4a23-85f8-411b922a8fa6",
      "rootWorkflowId": "83306aae-a723-4138-81b3-26a9618ade24",
      "parentWorkflowId": "83306aae-a723-4138-81b3-26a9618ade24",
      "bucket": "inttra2-qa-workspace",
      "fileName": "83306aae-a723-4138-81b3-26a9618ade24/efb476d7-2add-4704-8a6f-c416397455d2",
      "component": "transformer",
      "exitStatus": "success",
      "timestamp": "2026-04-21T14:30:18.66",
      "projections": {
        "originalFileName": "BK3_Request_All",
        "inboundS3FileName": "300_IFTMBF/20260421/customers/CU2100/BK3_Request_All",
        "interchangeControlReferenceNumber": "MAXRG19021901",
        "formatCode": "IFTMBF2_D99B_IN_V20",
        "mftId": "CU2100",
        "s3EventCreationTime": "2026-04-21 14:30:07.43",
        "inftpfilepickuptime": "2026-04-21 14:30:06.00",
        "contextCode": "requestBooking",
        "xlogId": "9000000000000000000239357671",
        "integrationProfileId": "4",
        "splitterFileSize": "57453",
        "documentControlNumber": "00000000sd0001",
        "pickupFileName": "300_IFTMBF/20260421/customers/CU2100/BK3_Request_All",
        "formatId": "84",
        "originalFileSize": "57453",
        "dispatcherStartRunTime": "2026-04-21 14:30:08.25",
        "ediId": "CU2100",
        "fileType": "300_IFTMBF",
        "integrationProfileFormatId": "131"
      }



## Referenced documentation 

- booking/docs/2026-04-17-booking-dataformat-fixes.md
This document has the details for the last commit for dataformat issue fixes. Check the details to understand the changes made. 

- booking/docs/DESIGN-AWS2x.md
This has the details for the architecture and data flow for the Booking module with the AWS upgrade

- booking/docs/2026-03-27-aws-upgrade-branch-migration-summary.md --> see this file for list of all changed files in the aws upgrade


## Actions (DO THESE DILIGENTLY)

1) Do a thorough analysis to ensure there is no further dataformat issues between all visibility modules with AWS 1.x and the latest booking module with AWS 2.x. 

We cannot afford to have breaking data format issues like this. 
THIS FIX SHOULD FIND ANY AND ALL GAPS INCLUDING THE ONES REPORTED AND ADDRESS

2) Also determine how we are writing to SQS in the booking module. How is the timestamp getting written to in MetaData when the SQS message is published. Document this before and after fix.

3) Create a thorough plan to fix the issues

4) Document in complete detail under booking/docs/booking-integration-issues-04222027-copilot.md

5) Write failing unit tests first

6) Implement the fixes and fix the failing tests 

7) Run ALL UNIT and Integration tests. This includes existing FlowTest Integration tests as well as DynamoDb Integration tests

8) Verify application startup

Verify all the changes are good and confirm 

IMPORTANT
- run all unit and integration tests for booking module to verify changes are good

- run application to make sure application start up is successful

I will then commit and push to my remote and run Jenkins job to deploy and test in the dev environment.

Follow these rules:

- Ask for clarification or confirmation if anything is not clear

- if you need more test data or payload let me know

- Create new session in mcp context server before starting

- Persist all important and necessary information in the session context as you proceed 

- if context window gets full and over 90% save all information to session context, update documents, and stop and ask me to create new chat session with fresh context window. This way you can resume with all analyzed information and continue with context loss. 

- before ending the session, mark the session as complete. 

This will help you and the next agent to have all the necessary information and context for any future work related to this task. 