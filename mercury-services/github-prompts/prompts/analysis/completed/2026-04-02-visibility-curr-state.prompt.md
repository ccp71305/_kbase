---
name: visibility analysis
description: visibility current state
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

I want you to document the current state of the visibility module including all of its sub-modules.
Explain to me in clear unambigious terms the data flow, the architecture, the current design of the components and the key classes their responsibilities and dependencices. 
Note this is before the AWS 2.x upgrade to cloud-sdk-api and cloud-sdk-aws libraries
Use diagrams as much as possible and clean readable table formats
Also explain the different sub-module interactions and dependencies and how the build.sh interact
Also explain the lambda functions and what they do

# References
You can refer to the Design documents for the following modules: booking, booking-bridge and webbl
These documents are available in the following locations respectively
for booking module in feature branch feature/ION-14382-bk3-aws-upgrade-2 under booking/docs/DESIGN-AWS2x.md
for booking-bridge this is available in DESIGN.md under booking-bridge/docs both in the above feature branch and in main develop branch
for webbl module, this is available in DESIGN.md under webbl/docs both in the above feature branch and in main develop branch

# Produce
A detailed document named DESIGN-curr-state.md under visibility/docs folder. create this docs folder. This document states the current state. 

Follow these rules:

- Ask for clarification if the changes are not clear
- Create new session before starting in the session context using the mcp-context-server 
- Persist all important and necessary information in the session context as you proceed 
- before ending the session, mark the session as complete. 
This will help you and the next agent to have all the necessary information and context for any future work related to this task. 