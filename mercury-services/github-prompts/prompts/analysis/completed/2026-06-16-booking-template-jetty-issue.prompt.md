---
name: 2026-06-16-booking-template-jetty-issue
description: Fix HTTP ERROR 400 Ambiguous URI Path Separator in booking template functionality caused by Jetty 11.x to 12.x upgrade. Analyze, test, and fix forward slash and special character handling in template names.
argument-hint: "none"
agent: agent
model: Claude Opus 4.6 (copilot)
maxModelContextLength: 1000000
tools:
  - execute
  - read
  - search
  - mcp-context-server/*
---

# Booking Template Jetty 12.x URI Path Separator Fix — ION-16032

## CRITICAL CONSTRAINTS

1. **BRANCH MANAGEMENT** — All work must happen on branch `defect/ION-16032-booking-template-issue` created from latest `develop`.
2. **COMMIT CONVENTION** — All commit messages MUST contain `ION-16032` in the message.
3. **TEST-DRIVEN** — Create a failing test FIRST that reproduces the issue, commit it, then implement the fix.
4. **NO UNRELATED CHANGES** — Do not modify code outside the scope of this fix. Do not refactor unrelated code.
5. **ALL TESTS MUST PASS** — Run `mvn test -pl booking` and `mvn verify -pl booking` before final commit. All existing tests must continue to pass.

---

## Session Context Protocol — FOLLOW THIS STRICTLY

Before starting ANY work:
1. Call `session_list` to check for existing sessions related to `booking-template-jetty` or `ION-16032` or `PDSUPPORT-203319`.
2. If a relevant session exists, call `session_get` to load its context and resume from where you left off.
3. If no session exists, call `session_create` with:
   - name: `booking-template-jetty-fix-2026-06-16`
   - project: `mercury-services`
   - tags: `["booking", "ION-16032", "PDSUPPORT-203319", "jetty-upgrade", "template", "uri-path-separator", "defect-fix"]`

**DURING** work — call `session_add_context` after EVERY significant action:
- After reading Jira issue details → category: `finding`
- After analyzing template code → category: `finding`
- After identifying root cause → category: `finding`
- After documenting analysis → category: `progress`
- After creating branch → category: `progress`
- After creating failing test → category: `progress`
- After implementing fix → category: `code_change`
- After test results → category: `test_result`
- After each commit → category: `progress`
- Log decisions with category: `decision`
- Log your model info with category: `model_info`

**CONTEXT MANAGEMENT** — If context window fills above 85%:
1. Persist ALL important details in session context with `session_add_context` (category: `progress`, include full summary of everything found so far)
2. Write all findings to the analysis document immediately
3. Note in session context where you left off and what remains

---

## Goal Overview

After upgrading Jetty from 11.x to 12.x in the booking module, template names containing forward slashes (`/`) trigger an HTTP ERROR 400 "Ambiguous URI Path Separator" response. This is a known behavioral change in Jetty 12 which treats encoded path separators (`%2F`) differently by default.

The fix must:
1. Allow template names with forward slashes to work correctly (as they did before the Jetty upgrade)
2. Ensure other special characters commonly used in template names (spaces, ampersands, parentheses, etc.) continue to work
3. Not introduce security vulnerabilities (path traversal, etc.)

---

## Step 1: Gather Issue Details from Jira

Use the MCP context server to get the full details from the support ticket:

```
jira_get_issue: PDSUPPORT-203319
```

Read:
- The **description** for the reported issue, error details, and reproduction steps
- The **comments** for any developer analysis already performed
- Note the affected endpoints, template names that fail, and exact error messages
- The ticket has screenshots as attachments with URL's and Postman API 

Also check if there is an engineering ticket:
```
jira_get_issue: ION-16032
```

Document all findings from Jira in the session context (category: `finding`).

---

## Step 2: Analyze the Booking Template Functionality

### 2a. Find Template-Related Code

Search the booking module for template-related functionality:

```bash
# Find template resource/endpoint classes
grep -r "template" booking/src/main/java --include="*.java" -l
grep -r "Template" booking/src/main/java --include="*.java" -l

# Find JAX-RS path annotations related to templates
grep -rn "@Path.*template" booking/src/main/java --include="*.java"
grep -rn "@Path.*Template" booking/src/main/java --include="*.java"

# Find existing template tests
grep -r "template" booking/src/test/java --include="*.java" -l
grep -r "Template" booking/src/test/java --include="*.java" -l
```

### 2b. Analyze the URI Path Handling

Identify:
- Which JAX-RS resource class handles template endpoints
- How template names are passed in the URL path (as path parameter, query parameter, etc.)
- Whether template names with `/` are URL-encoded by clients
- How Jetty 12 handles `%2F` in URI paths differently from Jetty 11

### 2c. Check Jetty Configuration

```bash
# Find Jetty configuration in the booking module
grep -rn "jetty" booking/src --include="*.java" -l
grep -rn "jetty" booking/src --include="*.yaml" -l
grep -rn "jetty" booking/conf --include="*.yaml" -l

# Check Dropwizard server configuration
grep -rn "server:" booking/conf -A 20

# Check pom.xml for Jetty version
grep -n "jetty" booking/pom.xml
grep -n "jetty" pom.xml
```

### 2d. Understand Jetty 12 Behavior Change

In Jetty 12, the default `UriCompliance` mode rejects ambiguous URI path separators (`%2F` encoded as part of a path segment). This was allowed in Jetty 11.x.

Key areas to investigate:
- `ComplianceViolation.Listener` configuration
- `UriCompliance` settings
- `HttpConfiguration.setUriCompliance()` or equivalent Dropwizard configuration
- Whether the fix should be at the Jetty configuration level (allowing `%2F`) or at the application level (changing how template names are passed)

### 2e. Assess Impact on Other Special Characters

Test and verify behavior with these characters commonly found in template names:
- Forward slash: `/` (the reported issue)
- Space: ` ` (encoded as `%20` or `+`)
- Ampersand: `&`
- Plus: `+`
- Parentheses: `(`, `)`
- Brackets: `[`, `]`
- Hash/Pound: `#`
- Percent: `%`
- Colon: `:`
- Semicolons: `;`
- Equals: `=`
- At sign: `@`
- Exclamation: `!`
- Asterisk: `*`
- Comma: `,`
- Single quote: `'`
- Tilde: `~`

---

## Step 3: Document Analysis and Plan

Create the analysis document at `booking/docs/2026-06-16-booking-template-jetty-issue.md` with:

1. **Issue Summary** — What was reported, error details, affected functionality
2. **Root Cause Analysis** — Why Jetty 12 rejects the request, the specific compliance change
3. **Impact Assessment** — Which characters are affected, which endpoints are impacted
4. **Fix Options** — Evaluate approaches:
   - Option A: Configure Jetty 12 UriCompliance to allow ambiguous path separators
   - Option B: Change the endpoint to use query parameters instead of path parameters for template names
   - Option C: Custom Dropwizard server factory or filter to handle encoded slashes
   - Evaluate security implications of each approach
5. **Recommended Fix** — Choose the best option with rationale
6. **Testing Strategy** — What tests to write, what characters to cover
7. **Jira References** — Link to PDSUPPORT-203319 and ION-16032

---

## Step 4: Create Branch from Latest Develop

```bash
cd /c/Users/arijit.kundu/projects/mercury-services

# Fetch latest from remote
git fetch origin

# Checkout develop and pull latest
git checkout develop
git pull origin develop

# Create the defect branch
git checkout -b defect/ION-16032-booking-template-issue

# Verify branch
git branch --show-current
```

---

## Step 5: Create Failing Test (Commit 1)

Write a test that reproduces the HTTP 400 "Ambiguous URI Path Separator" error when a template name contains a forward slash.

**Requirements for the test:**
- Place in the appropriate test class alongside existing template tests
- Use the same test patterns as existing tests in the booking module (JUnit 5, Mockito, assertj)
- The test should demonstrate that a template name like `"carrier/booking-template"` or similar with `/` in the name fails
- Also add parameterized tests for other special characters that should be supported
- The test MUST FAIL before the fix is applied
- Use AssertJ libraries for assertion

```bash
# Verify the test fails
mvn test -pl booking -Dtest=<TestClassName>#<testMethodName>

# Commit the failing test
git add -A
git commit -m "ION-16032: Add failing test for template name with forward slash (Jetty 12 URI compliance)"
```

---

## Step 6: Implement the Fix

Based on the analysis from Step 2-3, implement the fix. The fix should:

1. **Be minimal and focused** — Only change what's necessary to fix the issue
2. **Be secure** — Do not blindly allow all ambiguous URIs; be specific about what's allowed
3. **Be compatible** — Work with the existing Dropwizard/Jetty configuration
4. **Handle edge cases** — Template names with multiple slashes, leading/trailing slashes, etc.

Common approaches for Jetty 12:
- If using Dropwizard's `DefaultServerFactory`, configure the `HttpConfiguration` to use `UriCompliance.LEGACY` or a custom `UriCompliance` that specifically allows `AMBIGUOUS_PATH_SEPARATOR`
- If the fix is at application level, ensure proper URL decoding in the resource method
- preference is application level and not dropwizard unless there is real downside risk 

After implementing:
```bash
# Run the previously failing test — it should now PASS
mvn test -pl booking -Dtest=<TestClassName>#<testMethodName>
```

---

## Step 7: Run All Tests and Final Commit

```bash
# Run all unit tests for booking module
mvn test -pl booking

# Run all tests including integration tests
mvn verify -pl booking

# If all pass, commit the fix
git add -A
git commit -m "ION-16032: Fix Jetty 12 ambiguous URI path separator for template names with forward slash"
```

If any tests fail:
1. Analyze whether the failure is related to your change
2. If related, fix it and re-run
3. If unrelated (pre-existing failure), document it in session context but do not fix it in this branch
4. Log all test results in session context (category: `test_result`)

---

## Step 8: Final Verification

1. Verify both commits are on the branch:
```bash
git log --oneline develop..HEAD
```

2. Verify the branch has exactly 2 commits:
   - Commit 1: Failing test
   - Commit 2: Fix + passing tests

3. Run the full test suite one final time:
```bash
mvn test -pl booking
```

4. Update session context with final status (category: `progress`)

5. Update the analysis document with the final fix details and test results

---

## Output Summary

At the end of this task, you should have:
- [ ] Session context with full traceability of decisions, findings, and progress
- [ ] Analysis document at `booking/docs/2026-06-16-booking-template-jetty-issue.md`
- [ ] Branch `defect/ION-16032-booking-template-issue` with 2 commits
- [ ] Commit 1: Failing test reproducing the forward slash issue
- [ ] Commit 2: Fix that resolves the issue and passes all tests
- [ ] All booking module tests passing (unit + integration)
- [ ] Special character coverage verified (space, ampersand, slash, etc.)
