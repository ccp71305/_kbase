---
name: booking-email-test-restore
description: Restore the email test cases for booking application and ensure all scenarios are covered and tests are passing successfully without any issues.
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

Please check the following files for your understanding.

- booking/docs/2026-03-24-email-test-review-summary.md
- .github/skills/pr-reviews/full-diff.patch

Load the last session context for the analysis and findings that you already did. This will help you avoid repeating work and focus on the objective of this task.

the first file above gives your previous analysis for the email test cases which were removed during the aws upgrade and the proposed strategy to restore the email test cases. 

the second file above gives the full diff of the original changes

I have done a rebase of the latest changes from the develop branch and resolved the conflicts in the email test cases. 

There were conflicts in the following files during rebase:

- booking/src/main/java/com/inttra/mercury/booking/outbound/email/OutboundEmailSender.java 
- booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/ConfirmPendingEmailVariablesConverter.java
- booking/src/main/java/com/inttra/mercury/booking/outbound/email/converter/ConfirmPendingEmailVariablesConverter.java
- booking/src/test/java/com/inttra/mercury/booking/outbound/email/OutBoundEmailSenderTest.java

The 1st three files had conflicts in the import section and the conflict resolution looked ok to me. But still check for any issues. \

The last test file had conflicts and the last test method testConfirmEmailWithControlTotals() may not run successfully as it uses the old assertion for the email content verification which is currently commented out. This should get fixed once you restore the email content verification in the test cases.

the cloud-sdk-aws and cloud-sdk-api are in the mercury-services-commons workspace. if you need to check the SES email sending code you can check the cloud-sdk-aws module and the cloud-sdk-api module.

## important notes:

I would like you to adopt Strategy B as you had recommended in the document. 
Please ensure all the email content verification is restored in the test cases including the converters, subject line etc and make sure all the test cases are running successfully without any issues.

In OutboundEmailSenderTest.java add a comment and mention the proposed strategy to separate the unit vs integration tests for the email sending functionality and the need to have a separate test class for the email content tests.

Follow these rules:

- Ask for missing files if needed
- Ask for clarification if the changes are not clear
- make sure all production and test classes compile 
- the email content test gap for the affected test classes are restored and the test cases are running successfully without any issues.
- make sure the converters are also properly tested along with the subject line and the email variables etc.
- run mvn verify and make sure all the tests (junit and testng and dynamodb and flow test integration tests)are passing successfully without any issues.
- document all the changes and the test results in a new .md file under booking/docs with the name format as YYYY-MM-DD-email-content-test-restore-summary.md. 
This should include the summary of changes, and list of all test cases that were affected and restored. will be good if you can present this in a table format for easy verification etc.
- Create new session before starting in the session context. Persist all important and necessary information in the session context as you proceed and before ending the session. This will help you and the next agent to have all the necessary information and context for any future work related to this task. And finally mark the session as completed once all the required changes, documentations are done and the new jars are built successfully without any issues.