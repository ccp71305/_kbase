---
name: booking-email-test-review
description: Review the email test cases for booking application and provide feedback on any missing scenarios or improvements
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
.github/skills/pr-reviews/pr-context.md
.github/skills/pr-reviews/full-diff.patch

the 1st file will give you the context on how to review a PR and the 2nd file is the full diff of the PR which contains the email test cases for booking application.

Once you have reviewed the diff, you will see that previously we the tests were also verifying the email content for both the html and text versions from test/resources folder. 
But in the AWS upgrade version the email content verification is removed and we are only verifying that the email is sent successfully without any errors.

Can you list out which tests files were similarly affected in the AWS upgrade version and then can you also provide your feedback on whether we should re-add the email content verification in the new AWS upgrade version of the tests?

the cloud-sdk-aws and cloud-sdk-api are in the mercury-services-commons workspace. if you need to check the SES email sending code you can check the cloud-sdk-aws module and the cloud-sdk-api module.

Can we re-add the email content verification in the new AWS upgrade version of the tests?
What is the best way to check the content of the email in the new AWS upgrade version of the tests? 
Can you summarize your findings and suggestions and how to restore the previous email content verification in a new .md file under booking/docs with the name format as YYYY-MM-DD-email-test-review-summary.md?

Follow these rules:

- Ask for missing files if needed
- Ask for clarification if the changes are not clear
- this is analysis and review task so there is no coding required but you can provide detailed code snippets if needed to explain your suggestions on how to restore the previous email content verification in the new AWS upgrade version of the tests.
- Create new session before starting in the session context. Persist all important and necessary information in the session context as you proceed and before ending the session. This will help you and the next agent to have all the necessary information and context for any future work related to this task. And finally mark the session as completed once all the required changes, documentations are done and the new jars are built successfully without any issues.