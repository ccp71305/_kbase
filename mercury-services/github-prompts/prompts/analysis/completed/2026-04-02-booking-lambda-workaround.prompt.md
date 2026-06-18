---
name: lambda-workaround
description: Workaround for booking lambda size issue
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

Please check the session context last for the analysis and findings that you already did. This will help you avoid repeating work and focus on the objective of this task.

Also please check the document 2026-03-23-lambda-jar-size-fix-plan.md under booking/docs/ where you listed all the findings and proposed some solutions as Options A, B, C, D etc.

Option B Lambda Container Image Deployment is not feasible.
Option C Sepate lambda modules is long term solution and we will do it post all AWS upgrades are done. 

The goal is not to optimize the booking jar.

So the current best option is to adopt the aggresive alternate shading to produce a separate lambda jar with only the required dependencies for the lambda function. 

This is mentioned in section 8. Alternative Quick Fix: Exclude MORE from Shade Plugin of the document.

Name the new shaded jar as booking-lambdas-${project.version}.jar 
Update the build.sh in booking module to mv the new shaded jar to the target folder and have the final name as Booking-Lambdas-${RELEASE_NAME}.jar

So if the {RELEASE_NAME} is 26.03.010 then the booking application jar will be named as Booking-26.03.010.jar and the new shaded Lambda jar will be named as 
Booking-Lambdas-26.03.010.jar

Only one shaded lambda jar will suffice even if only elasticsearch lambda needs the jest client.
  
Produce:

1. Summary of changes in a new .md file under booking/docs with the name format as YYYY-MM-DD-lambda-jar-size-fix-summary.md.
2. Required fixes  
3. Detalied plan for the long term solution of refactoring the booking application to have separate lambda modules with all necessary changes. Make sure we follow the structure of the lambda module and there are cfn scripts created for the new lambda module etc. This will be a separate .md file under booking/docs with the name format as YYYY-MM-DD-lambda-module-refactor-plan.md.

Follow these rules:

- Ask for missing files if needed
- Ask for clarification if the changes are not clear
- make sure the new shaded lambda jar unzipped size is less than 250MB to avoid lambda size issue.
- make sure the shaded exclusions are correct and only the required dependencies for the lambda function are included in the new shaded jar.
- make sure the build.sh script is updated correctly to move and rename the new shaded jar as per the naming convention mentioned above.
- make sure the depdendencies included in the new shaded jar for the 2 lambdas are sufficient for them to function properly without any runtime issues.
- do a mvn verify and make sure the new jars are built successfully and the tests are passing without any issues.
- Create new session before starting in the session context. Persist all important and necessary information in the session context as you proceed and before ending the session. This will help you and the next agent to have all the necessary information and context for any future work related to this task. And finally mark the session as completed once all the required changes, documentations are done and the new jars are built successfully without any issues.