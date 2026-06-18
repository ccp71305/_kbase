---
name: bk-runtime-issues
description: fixing booking runtime issues
argument-hint: "none"
agent: agent
model: Claude Opus 4.6 (copilot)
tools:
  - execute
  - read
  - edit
  - search
  - mcp-context-server/*
---
# Task instructions

## Reported issues >>

## Fix the IndexHandler runtime ClassNotFound issue

First review the document 2026-03-25-runtime-issue-fixes-summary.md under booking/docs/ to understand the changes done to fix the runtime issues reported below. 

Second Check yesterdays sessions for more details to understand where we left off and the changes that were done.

I just ran a full mvn clean verify -pl booking -am and it was successful without any issues. 
The entire log is under /tmp/mvn-verify.log
Check this log and categorize all the unit and integration tests that were run and passed successfully. 

Make sure you check the surefire configuration in the pom.xml. There are both Junit and TestNG tests.
There are DynamoDB integration tests and there are flow step integration tests and other integration tests which require AWS credentials. 

AWS credentials are available in the terminal session of vscode. and .credentials file is also having valid credentials. 

Check the jar files produced in the target folder and confirm your fixes are reflected in the new shaded lambda jar file. 

I do not think you need to do the changes for the SUBMITTER issue, please undo that and corresponding test changes. 

Verify all the changes are good and confirm 
I will then commit and push to my remote and run Jenkins job to deploy and test in the dev environment.

Below are the details of the runtime issues for reference only
>>>>>>>>

The changes worked for the S3ArchiveHandler lambda and it is working fine. 
However, 
1) the IndexHandler is not invoking and no indexing is happening due to ClassNotFoundException for some Jetty library
The stack from the lambda log is as below:
org/eclipse/jetty/io/RuntimeIOException: java.lang.NoClassDefFoundError
java.lang.NoClassDefFoundError: org/eclipse/jetty/io/RuntimeIOException
	at com.inttra.mercury.booking.lambda.IndexerHandler.<init>(IndexerHandler.java:60)
	at java.base/jdk.internal.reflect.NativeConstructorAccessorImpl.newInstance0(Native Method)
	at java.base/jdk.internal.reflect.NativeConstructorAccessorImpl.newInstance(Unknown Source)
	at java.base/jdk.internal.reflect.DelegatingConstructorAccessorImpl.newInstance(Unknown Source)
	at java.base/java.lang.reflect.Constructor.newInstanceWithCaller(Unknown Source)
	at java.base/java.lang.reflect.Constructor.newInstance(Unknown Source)
Caused by: java.lang.ClassNotFoundException: org.eclipse.jetty.io.RuntimeIOException
	at java.base/java.net.URLClassLoader.findClass(Unknown Source)
	at java.base/java.lang.ClassLoader.loadClass(Unknown Source)
	at java.base/java.lang.ClassLoader.loadClass(Unknown Source)
	... 6 more
	
INIT_REPORT Init Duration: 2332.54 ms	Phase: invoke	Status: error	Error Type: Runtime.BadFunctionCode


2) Also the index search for old records gives summary result. However trying to select one record from UI calls API which gives 400 Bad Request as below 
https://api-alpha.inttra.e2open.com/booking/2011830011
Status Code: 400 Bad Request
Response: 
{
        "code": "000200",
        "message": "Cannot deserialize value of type `java.util.Date` from String \"2020-12-08T18:07:00.000Z\": expected format \"yyyy-MM-dd HH:mm:ss\"\n at [Source: UNKNOWN; byte offset: #UNKNOWN] (through reference chain: com.inttra.mercury.booking.outbound.model.EnrichedAttributes[\"containerTypeList\"]->java.util.ArrayList[0]->com.inttra.mercury.booking.networkservices.referencedata.model.ContainerType[\"lastModifiedDateUtc\"])"
}

Produce these : 

1) confirm the changes you made are good and reflected in the new shaded jar file for the 2 lambdas.
2) undo the SUBMITTER changes and corresponding test changes and confirm the undo is successful.
3) Categorize all the unit and integration tests that were run and passed successfully from the mvn verify log.
4) Update the summary document 2026-03-25-runtime-issue-fixes-summary.md with the details of the changes you made and the tests that were successful.
5) In a sepearate section of the document list all the tests classes, the type of test (unit or integration) and Junit or TestNG, how many tests in each test class and count of pass/failed/skipped tests in each test class.
6) Write exact and accurate commands to run from mvn any specific JUnit test or any specific TestNG test or any specific DynamoDb Integration test or all DynamoDb integration tests or only the Flow Step integration tests or all Junit tests only or all TestNG tests only and update the document with these commands for future reference.


Follow these rules:

- Ask for clarification if the changes are not clear

- if you need more test data or payload let me know

- make sure the depdendencies included in the new shaded jar for the 2 lambdas are sufficient for them to function properly without any runtime issues.

- do a mvn verify and make sure the new jars are built successfully and ALL the tests are passing without any issues.

- Create new session before starting in the session context. 

- Persist all important and necessary information in the session context as you proceed 

- before ending the session, mark the session as complete. 

This will help you and the next agent to have all the necessary information and context for any future work related to this task. 