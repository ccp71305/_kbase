---
name: visibility cloud-sdk-upgrade plan
description: visibility aws upgrade plan
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

I want you to create a detailed plan to upgrade the visibility and its sub-modules to use cloud-sdk-api and cloud-sdk-aws libraries.
Also create a CONFLUENCE_visibility.md document under visibility/docs for uploading to my confluence. This document should follow the pattern for webbl, booking-bridge, booking module. See # References

The cloud-sdk libraries use AWS 2.x API
We do not use dynamo-client library that is deprecated
We use dynamo-integration-test module for DynamoDb Local Integration tests. 
The test coverage should not reduce.

The mercury-service-commons workspace hosts the cloud-sdk-api and cloud-sdk-aws modules alongwith the commons module and dynamo-integration-test module

The latest version of mercury-service-commons for the cloud-sdk upgrade is 1.0.22-SNAPSHOT

Many existing modules have been upgraded to cloud-sdk libraries. 

These modules which have been merged to the develop branch in latest chronological order are:
webbl, booking-bridge, network, auth, self-service-reports, db-migration, registration, tx-tracking

The latest module which is completed is booking. the changes are not yet merged into develop. But available in feature branch /feature/ION-14382-bk3-aws-upgrade-2
You can checkout the branch and get the details as you might need to generate the booking model that is referenced in Visibility

# References
You can refer the detailed current-state analysis in DESIGN-curr-slate.md under visibility/docs and also in the last session in session context

You can refer to the Design documents for the following modules: booking, booking-bridge and webbl
These documents are available in the following locations respectively
for booking module in feature branch feature/ION-14382-bk3-aws-upgrade-2 under booking/docs/DESIGN-AWS2x.md
for booking-bridge this is available in DESIGN.md under booking-bridge/docs in main develop branch
for webbl module, this is available in DESIGN.md under webbl/docs in main develop branch

For Confluence design document, you can refer to 
CONFLUENCE-webbl.md under webbl/docs, 
CONFLUENCE_DESIGN_DC.md under booking-bridge/docs, 
CONFLUENCE_DESIGN_DOC.md under booking/docs


# Produce
The detailed plan document named visibility-aws2x-plan.md under visibility/docs folder. 
This should have all necessary changes needed for the high level implementation.
Include high level details of unit tests, integration tests for dynamodb
The plan should be thorough enough so that the copilot Claude Opus 4.6 can take the plan and implement in a subsequent session.

Also produce the CONFLUENCE-visibility.md similar to the other modules. 

Follow these rules:

- Ask for clarification if the request is not clear and you need more information.
- Ask for documents if any reference is not found.
- you can checkout the booking feature branch if you need to see the latest aws upgrade changes in booking. the branch named is /feature/ION-14382-bk3-aws-upgrade-2
- Create new session before starting in the session context using the mcp-context-server 
- Persist all important and necessary information in the session context as you proceed 
- If your context window is filling up, make sure you update progress to session context with necessry details and open a new chat session and reload all necessary details to continue
- You can ask me to open a new chat session if you cannot open one in such a scenario. but do persist all important details before asking so you can resume comfortably.
- before ending the session, mark the session as complete. 
- also in a separate section of the document visibility-aws2x-plan.md, please log all the tooling commands you used for my reference with some explanation for each

Logging all the necessary information in session context will help you for any future work related to this task. 