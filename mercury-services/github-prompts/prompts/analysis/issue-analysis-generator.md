---
name: issue-analysis-generator
description: >
  Reusable prompt to analyze a reported issue or defect: fetch Jira details, search the codebase
  for root cause, evaluate fix options, and produce a structured analysis + implementation plan
  document. The output document feeds directly into confluence-design-doc-generator.md.
  To reuse: fill the PARAMETERS block and run. Nothing here is hard-coded to a specific ticket.
argument-hint: "none — edit the PARAMETERS block below"
agent: agent
model: Claude Opus 4.6 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# Issue Analysis Generator (Reusable)

Analyze a reported issue or defect, identify the root cause, evaluate fix options, and produce
a structured analysis + implementation plan document that can be fed into the design doc generator.

> **Session protocol:** see `.github/prompts/_base-session-protocol.md` — follow it strictly.

---

## Invocation — No PARAMETERS editing needed

If invoked via Copilot CLI or Claude Code with a natural language description, extract
parameters from the user's message. You do not need the PARAMETERS block to be pre-filled.

| What to find | Example |
|---|---|
| Module name | `booking`, `visibility`, `oceanschedules` |
| Jira ticket(s) — optional | `ION-16032` |
| Support ticket(s) — optional | `PDSUPPORT-203319` |
| Issue description or analysis goal | "date parsing fails on old records after AWS upgrade" |
| Notes file — optional, under `<module>/docs/` | `booking/docs/notes.md` |

**Example Copilot invocations:**
```
follow issue-analysis-generator — booking module, ION-16032, PDSUPPORT-203319

follow issue-analysis-generator — booking module, no ticket yet,
visibility reads are failing after AWS upgrade, details in booking/docs/notes.md

follow issue-analysis-generator — analyze booking date serialization across all
DynamoDB read paths, understand blast radius before the AWS upgrade
```

If a notes file is referenced, read it first and treat its content as additional context.
If no Jira ticket is given, skip the Jira fetch step and proceed with the description as source.

---

## PARAMETERS — Change these for each new issue (skip if using natural language invocation)

```yaml
# ─── INPUT ────────────────────────────────────────────────────────────────────
MODULE: "<module>"                  # e.g. booking, visibility, oceanschedules, network
JIRA_TICKETS:
  - "<JIRA-KEY>"                    # engineering ticket (ION-xxxxx)
SUPPORT_TICKETS:
  - "<SUPPORT-KEY>"                 # support ticket (PDSUPPORT-xxxxx), if any

# ─── CONSTRAINTS ──────────────────────────────────────────────────────────────
BRANCH_NAME: "<branch-name>"        # e.g. defect/ION-xxxxx-short-description
COMMIT_PREFIX: "<JIRA-KEY>"         # all commits must include this in the message
TEST_DRIVEN: true                   # create failing test first, then implement fix

# ─── OUTPUT ───────────────────────────────────────────────────────────────────
OUTPUT_ANALYSIS_DOC: "<module>/docs/<yyyy-mm-dd>-<short-description>.md"
```

---

## CRITICAL CONSTRAINTS

1. **READ before writing** — all analysis must be grounded in Jira details and actual code.
   Do not invent or assume root causes not supported by the evidence.
2. **Minimal scope** — do not refactor or fix unrelated code. Stay within the ticket scope.
3. **Test-driven** — write a failing test first (reproduces the issue), commit, then implement fix.
4. **No unverified options** — evaluate each fix option against actual code before recommending.
5. **Security-aware** — flag any input validation, path traversal, or injection risks in fix options.
6. **All tests must pass** — run `mvn test -pl <MODULE>` and `mvn verify -pl <MODULE>` before done.

---

## Session Context Protocol

> Follow `.github/prompts/_base-session-protocol.md`.
>
> Session name pattern: `<module>-<jira-key>-analysis-<yyyy-mm-dd>`
> Tags: all Jira keys + module + `"analysis"` + `"defect-fix"` (or `"feature"` as appropriate)

---

## Step 1 — Gather Issue Details from Jira

1a. `jira_get_issue(<JIRA-KEY>)` for each ticket. Extract:
- Summary, type, priority, status, assignee, reporter
- Description: reported error, reproduction steps, affected endpoints/functionality
- Comments: any developer analysis already done
- Attachments: screenshots, logs, Postman collections noted in comments

1b. If support tickets exist, `jira_get_issue(<SUPPORT-KEY>)`. Extract:
- Customer-reported symptoms, affected environment, example payloads

Log all findings → `session_add_context` (category: `finding`).

---

## Step 2 — Analyze the Codebase

2a. **Locate the affected code** — search the module for relevant classes, endpoints, and
configuration related to the reported issue:
```bash
grep -r "<keyword>" <module>/src/main/java --include="*.java" -l
grep -rn "@Path.*<pattern>" <module>/src/main/java --include="*.java"
```

2b. **Trace the execution path** — from the entry point (JAX-RS resource, Lambda handler,
scheduler) through service, repository, and infrastructure layers to where the failure occurs.

2c. **Identify the root cause** — be specific:
- Exact class, method, and line where the failure originates
- What changed (library upgrade, config change, data format, dependency) that caused it
- Why it worked before and why it fails now

2d. **Assess blast radius** — what other endpoints, modules, or data records are affected?
Are there related characters, edge cases, or code paths with the same vulnerability?

2e. **Check relevant configuration** — YAML configs, Jetty/JVM settings, AWS service config,
DynamoDB annotations, Guice bindings — whatever is relevant to the issue domain.

Log root cause findings → `session_add_context` (category: `finding`).

---

## Step 3 — Evaluate Fix Options

For each plausible fix approach, document:

| # | Option | Description | Pros | Cons | Security Risk |
|---|--------|-------------|------|------|---------------|
| A | | | | | |
| B | | | | | |

Evaluate at minimum:
- Application-level fix (preferred — contained, testable)
- Framework/config-level fix (if application-level has genuine downsides)
- Any migration or data-fix approach if data is affected

Log decision rationale → `session_add_context` (category: `decision`).

---

## Step 4 — Produce the Analysis Document

Write to `OUTPUT_ANALYSIS_DOC`. Include all sections:

### 4.1 Issue Summary
- What was reported, exact error messages, affected functionality, Jira/support ticket references

### 4.2 Root Cause Analysis
- Specific class/method/line; what changed; why it fails now; evidence from code

### 4.3 Impact Assessment
- Affected endpoints, data records, modules, edge cases; before/after behavior

### 4.4 Fix Options
- Table from Step 3 with full rationale per option

### 4.5 Recommended Fix
- Chosen option with rationale; security considerations; constraints honored

### 4.6 Implementation Plan
- Ordered steps: branch → failing test → implement → verify → commit
- Exact test class/method names to create
- Exact files/classes to modify and what changes to make
- `mvn` commands to verify

### 4.7 Testing Strategy
- New tests: class, method, what they cover
- Existing tests: any that need updating and why
- Special characters / edge cases / boundary conditions to cover

### 4.8 Jira References
- Table of all Jira and support tickets with key, summary, type, status

Log document written → `session_add_context` (category: `progress`).

---

## Step 5 — Review & Handoff

Present the analysis document to the user. Summarize:
- Root cause (one sentence)
- Recommended fix (one sentence)
- Implementation steps count and estimated scope
- Any open questions needing user input

This document is the input to `.github/prompts/designdocs/confluence-design-doc-generator.md`
for publishing the design doc to Confluence after the fix is implemented.

---

## Output Checklist

- [ ] Session context with full traceability (findings, decisions, root cause)
- [ ] Analysis document at `OUTPUT_ANALYSIS_DOC` with all 8 sections
- [ ] Fix option table with security assessment
- [ ] Implementation plan with exact files, classes, and test names
- [ ] User has reviewed and confirmed the recommended fix before implementation begins
