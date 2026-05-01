---
name: booking-dataformat-issue
description: fixing booking dataformat issue
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

1) DateTimeParseException on MetaData timestamp
new records from booking module after AWS upgrade has MetaData timestamp stored as "2020-04-14 10:21:53.78" (space separator)
This breaks in visibility module. 
The visibility module's SDK v1 DynamoDBMapper ignores the SDK v2 annotation
Without @DynamoDBDocument on MetaData and without a converter on timestamp, SDK v1 falls back to native type marshalling
BookingDetail aws upgrade removed @DynamoDBDocument from MetaData.java
BookingDetail aws upgrade removed @DynamoDBTypeConverted(converter = LocalDateTimeTypeConverter.class) from MetaData.timestamp field
New SDK v2 annotation @DynamoDbConvertedBy(MetaDataConverter.class) added to BookingDetail.getMetaData()
For LocalDateTime, native marshalling uses DateTimeFormatter.ISO_LOCAL_DATE_TIME (expects T separator)
Stored data contains "2020-04-14 10:21:53.78" (space separator) → DateTimeParseException at index 10

2) Viewing old booking records is failing because of below: 
{         "code": "000200",         "message": "Cannot deserialize value of type `java.time.LocalDateTime` from String \"2026-03-27T09:29:31.15\": Failed to deserialize java.time.LocalDateTime: (java.time.format.DateTimeParseException) Text '2026-03-27T09:29:31.15' could not be parsed at index 10\n at [Source: UNKNOWN; byte offset: #UNKNOWN] (through reference chain: com.inttra.mercury.booking.util.MetaData[\"timestamp\"])"     }


3) Viewing old booking records is failing because of below:
{
        "code": "000200",
        "message": "Cannot deserialize value of type `boolean` from String \"1\": only \"true\"/\"True\"/\"TRUE\" or \"false\"/\"False\"/\"FALSE\" recognized\n at [Source: UNKNOWN; byte offset: #UNKNOWN] (through reference chain: com.inttra.mercury.booking.outbound.model.EnrichedAttributes[\"containerTypeList\"]->java.util.ArrayList[0]->com.inttra.mercury.booking.networkservices.referencedata.model.ContainerType[\"displayFlag\"])"
    }
	
4) Rapid Reservation API view for a carrier is failing as below: 
booking/rapid-reservation/802435
{
        "code": "000200",
        "message": "Cannot deserialize value of type `java.time.OffsetDateTime` from String \"2020-11-30T04:23:30.153845Z\": Failed to deserialize java.time.OffsetDateTime: (java.time.format.DateTimeParseException) Text '2020-11-30T04:23:30.153845Z' could not be parsed at index 23\n at [Source: UNKNOWN; byte offset: #UNKNOWN] (through reference chain: com.inttra.mercury.booking.dynamodb.Audit[\"lastModifiedDateUtc\"])"
    }

## Facts

1) Both visibility and booking modules refer to the same dynamo db table "BookingDetail"
For booking module, the environment prefix is inttra2_prod_booking (for production config.yaml)
For visibility module, the environment prefix is inttra2_prod

2) Both visibility module (still in AWS 1.x) and booking module (AWS 2.x upgraded using cloud-sdk libraries) read and write to this same database table

3) The data format for each fields should remain consistent such that 
-  booking module is able to read all old records as well as new records in BookingDetail.
-  visibility module and other modules not aws upgraded yet and using pre-upgrade booking model "booking:2.1.8.M" should also be able to read ALL  old as well as NEW records written by upgraded booking module in BookingDetail table 

## Referenced documentation 

1) visibility/docs/2026-04-17-booking-sdk-upgrade-impact-on-visibility.md --> latest analysis. READ this carefully.
Also update this document with all explanations, verifications and fixes 

2) booking/docs/DESIGN-AWS2x.md

3) booking/docs/2026-03-27-aws-upgrade-branch-migration-summary.md --> see this file for list of all changed files in upgrade

4) booking/docs/2026-03-25-runtime-issue-fixes-summary.md --> some previous runtime issues that were fixed 

## Explain and Verify (Update documentation)

1) how is the booking model booking:2.1.8.M version vontrolled ? check in pom and build scripts for booking. How does it get generated ? 
create new document booking/docs/2026-04-17-booking-dataformat-fixes.md and update

2) check the booking model to confirm it has the old version of BookingDetail and other classes with 1.x annotations 
Update in booking/docs/2026-04-17-booking-dataformat-fixes.md 

3) did the aws upgrade changes make a new version of the booking model ?
Update in booking/docs/2026-04-17-booking-dataformat-fixes.md 

4) does visibility have any dependency with booking module ?

update in both 
booking/docs/2026-04-17-booking-dataformat-fixes.md & 
visibility/docs/2026-04-17-booking-sdk-upgrade-impact-on-visibility.md

5) Is the only reference to booking module classes in visibility is through the above booking model ? List all booking module classes that Visibility module refers to and use ?
update in booking/docs/2026-04-17-booking-dataformat-fixes.md

6) if the aws upgrade changes did not create any new booking model and 
the booking:2.1.8.M is pre-aws upgrade and 
there is no direct dependency on booking module 
then there should not be any compilation issue in Visibility. 
Developer in visibility did not complain of any compilation issue but still check and confirm

update in visibility/docs/2026-04-17-booking-sdk-upgrade-impact-on-visibility.md

7) Please also determine which modules in mercury-services refer and use this booking model. update document referenced above.
update in booking/docs/2026-04-17-booking-dataformat-fixes.md

9) Explain to me how and why booking is saving records with MetaData timestamp as "2020-04-14 10:21:53.78" 
How was it saving before upgrade. 
Check the git history and confirm. 

If MetaData was using LocalDateTimeTimeTypeConverter with ISO_DATE_TIME with T separator then changing to MetaDataConverter (Jackson ObjectMapper) using @JsonFormat("yyyy-MM-dd HH:mm:ss.SS") 
introduced breaking changes for other modules which are not upgraded and using the pre-upgrade booking model booking:2.1.8.M 
what was the rationale for this change ? 

update in both 
booking/docs/2026-04-17-booking-dataformat-fixes.md & 
visibility/docs/2026-04-17-booking-sdk-upgrade-impact-on-visibility.md

10) Section 4.1 Compile time breaks in visibility/docs/2026-04-17-booking-sdk-upgrade-impact-on-visibility.md looks invalid. right ? COnfirm and update this section accordingly 

11) Section 4.4 reads invalid since Visibility uses the pre-upgrade booking Model with 1.x annotations and also uses the deprecated dynamo-client library. 
So even though these modules read the same BookingDetail table, the API usage is at least consistent using the preupgrade 1.x version model and 1.x AWS wrappers from dynamo-client 
So they should work. Right ? Confirm and update the section accordingly - IMPORTANT 

12) Section 5 also seems invalid similar to Section 4.4 above for the same reason. Confirm and update accordingly 

## Actions (DO THESE DILIGENTLY)

## Fix the dataformat issues reported below and ensure backward compatibility

1) Fix all the reported issues above 

2) Ensure backward compatibility for all models since some modules which are not yet AWS upgraded uses old pre-upgrade booking model 
booking:2.1.8.M.
This should ensure Visibility module with 1.x AWS and pre-upgrade booking model will continue to work fine. 

3) Make sure the round trip test in MetaDataConverterTest uses a TIMESTAMP so that this bug is tested

4) Verify for all other converters in booking that all fields are tested including TIMESTAMPS so that there is no hidden bug and backward compatibility is NOT broken

5) Check and fix for runtime breaks for other model classes as referenced in 4.2 Sectoin of 
visibility/docs/2026-04-17-booking-sdk-upgrade-impact-on-visibility.md. e.g Audit , EnrichedAttributes and provide tests and fixes for the issue - IMPORTANT 

6) Check and fix if needed about payload (Contract) and expiresOn (Date) as reported in 4.3 Section of above document. 
How do we fix this. Add tests - IMPORTANT 

7) Check and Test for payLoadType, BookingState and Channel and make sure they are back ward compatible as well 

8) Section 4.5 of above document is IMPORTANT . make sure with the fixes the listed fields are back ward compatible completely and have complete test coverage for them 

9) Remove all deprecated dependencies from booking pom.xml like dynamo-client and email-client referring to old AWS 1.x libraries

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