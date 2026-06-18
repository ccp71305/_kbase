---
name: network-ov-runtime-issue
description: fix network OV issue ION-15098
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

## Investigate and find the root cause of the issue and fix

The issue is from network module
Please get the latest on develop branch, create a new branch following defect branch naming convention and fix the issue.
Write unit test to cover for the reported issue and a passing unit test to confirm the fix.
Commit the change and push the branch to remote and create a PR with appropriate title and description and link the JIRA ION-15098 in the PR description.
Ask me for confirmation on the changes and before pushing to remote.

## Reported exception

When user tries to change the OV status from UI, it shows 400 error.

API- https://api-beta.inttra.e2open.com/network/optionalvalidations 
Company ID- Wcarrier1 (1002354) 
Error: {"code":400,"message":"Unable to process JSON"}

{ "hashKey": "1ce3b279-8017-4b65-be26-29602c6d0882", "inttraCompanyId": 1002354, "moduleType": "Booking", "ruleName": "HS Code required", "version": 1, "audit": { "createdById": "112474", "createdByType": "User", "createdBy": "qacloud2+apitsuitrunadmin1@inttra.com", "createdByChannel": "WEB", "createdDateUtc": "2025-12-11T13:46:27.348382207Z", "lastModifiedById": null, "lastModifiedByType": null, "lastModifiedBy": null, "lastModifiedByChannel": null, "lastModifiedDateUtc": null }, "conditions": [ { "targetType": "PLACE_OF_RECEIPT", "operator": "IN", "valueType": "UNLOC", "values": [ "INBOM" ] } ], "conditionOperator": "AND", "ruleParameters": null, "activeFlag": false, "validationType": "error", "formattedAudit": "qacloud2+apitsuitrunadmin1@inttra.com
11-12-2025 19:16:27 GMT+5:30" }

When we remove the field 'createdDateUtc', then it passes.

## Initial analysis

these two fields in OptionalValdiation.java are serialized into a format         "createdDateUtc": "2025-12-03T14:49:38.5613668Z",        "lastModifiedDateUtc": "2026-03-12T07:10:47.402961767Z" in the API response. And UI sends the whole payload with the date fields, the dates deserialization fails because its expecting the date in the yyyy-MM-dd'T'HH:mm:ss.SSSZ format.  the format difference is introduced by OffsetDateTimeTypeConverter.

Produce these : 
- a fix for the issue and make sure the date is serialized and deserialized in the correct format.
- with detailed explaination of the root cause and the fix you implemented.


Follow these rules:

- Ask for clarification if the changes are not clear

- if you need more test data or payload let me know

- Create new session before starting in the session context. 

- Persist all important and necessary information in the session context as you proceed 

- before ending the session, mark the session as complete. 

This will help you and the next agent to have all the necessary information and context for any future work related to this task. 