# Design Document Template — Architecture / Defect Fix

> **Source of truth:** this template mirrors the corporate template at
> https://confluence.dev.e2open.com/display/~akundu/Design+Doc+Template (page id `672934513`,
> synced 2026-07-29). Section names, order, and the Pre-Dev Security / Approval Matrix tables
> match it exactly so published docs pass design review without restructuring.
>
> Sections with no applicable content must contain `N/A` (or `None.` where the official
> placeholder says so) — never delete an official section.
>
> **Sections marked `(ext)` are mercury-services engineering extensions**, not in the corporate
> template. They are additive subsections inside an official section — keep them when they carry
> real content, drop them when they would be empty. Never let an `(ext)` subsection replace or
> reorder an official one.

## Storage-format notes for the publisher

| Template element | Confluence storage |
|---|---|
| Contents | `<ac:structured-macro ac:name="info">` wrapping `<ac:structured-macro ac:name="toc" />` |
| Risks block | `panel` macro — `borderColor`/`titleBGColor` `#D04437`, `bgColor` `#FFD5D2`, title `Key Risks` |
| Dependencies block | `panel` macro — `borderColor`/`titleBGColor` `#4A6785`, `bgColor` `#DEEBFF`, title `Major Dependencies` |
| Approval-matrix callout | `note` macro |
| Pre-Dev Security row markers | `<ac:task-list><ac:task><ac:task-id>N</ac:task-id><ac:task-status>incomplete</ac:task-status>…` — **reuse the exact ids** `1,2,3,4,5,6,120,124,125,126` |
| Section rule under each heading | `<hr />` after every `<h1>`/`<h2>` |

ASCII box diagrams are preferred over Mermaid (no macro dependency). Inside diagrams write
`(yaml)` not `<yaml>` — angle brackets in a code block corrupt the render silently.

---

## Contents

<!-- info macro + TOC macro — see storage-format notes above -->

---

## Contributors

<!-- Official template is a bullet list of @mentions. Role column added for clarity (ext). -->

| Role | Name |
|------|------|
| Author | |
| Reviewer | |
| Product Owner | |

---

## Summary

<!-- Brief overview / high-level explanation of what this design document covers and why it is
     important. 2–4 sentences: what was broken or being added, who is affected, what this achieves. -->

**Status:** <!-- e.g. ✅ Verified working in QA (yyyy-mm-dd) — (ext) -->

---

## Requirements

<!-- Copy the user story with Done criteria into this section. -->

| | |
|---|---|
| **Epic** | |
| **Story ID** | |
| **Target Release** | |
| **Scope** | |
| **Fix Version** | |
| **Customer/Client** | |
| **Related Documents** (*If Any*) | |

### Functional Requirements

<!-- What the system does — features, capabilities, and user actions that must be implemented. -->

### Non-Functional Requirements

<!-- How the system performs — speed, security, scalability, reliability, UX standards. -->

### Acceptance Criteria

<!-- Specific, measurable conditions that must be met for this to be complete and
     production-ready. -->

### Jira Tickets (ext)

| Key | Summary | Type | Priority | Status | Assignee |
|-----|---------|------|----------|--------|----------|
| | | | | | |

### Support Tickets (ext)

| Key | Summary | Priority | Status |
|-----|---------|----------|--------|
| | | | |

### Technology Stack (ext)

| Component | Technology |
|-----------|-----------|
| Framework | |
| Servlet Container | |
| JAX-RS / API layer | |
| Build | |
| AWS SDK | |
| Database | |
| Messaging | |

---

## Assumptions and Open Issues

<!-- Backlog issues or assumptions, especially those needing product-owner review. -->

| # | Item | Type | Status | Resolution |
|---|------|------|--------|------------|
| 1 | | Assumption / Open Issue | Open / Resolved | |

---

## High Level Design

<!-- Official guidance:
     - Describe, at a high level, what you plan to do, especially any interface changes or
       additions that will affect other groups.
     - Describe any important design trades or options you want the group to decide on.
     - If the function is configurable, how will the project team configure the feature?
       Provide specific formats, XML examples, toolkit mockups, etc.
     - UI mockups. -->

### Architectural Overview (ext)

<!-- Module- or system-level overview showing all layers in the request path and where the
     change applies. -->
```
┌─────────┐      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Client  │─────▶│   Layer 1        │─────▶│   Layer 2        │─────▶│   Layer 3        │
│          │      │                 │      │                 │      │                 │
└─────────┘      └─────────────────┘      └─────────────────┘      └─────────────────┘
                     describe                  describe                  describe
```

### Design Options Considered (ext)

| Option | Approach | Pros | Cons | Chosen |
|--------|----------|------|------|--------|
| 1 | | | | ✅ / ❌ |

### Data Flow — Before vs After (ext)

**Before:**
```
Client: request
  → Layer: what happened and why it failed
  → error response e.g. HTTP 400
```
**After:**
```
Client: request
  → Layer 1: what changed — now passes
  → Layer 2: next step
  → Handler: processes request normally
  → success response e.g. HTTP 200
```

---

## Low Level Design

### Server

<!-- Official guidance: entities, APIs, database schema, class/sequence diagrams.
     - Entities are best described in a class diagram, with a few words on lifecycle.
     - APIs should include external APIs (e.g. those used by the UI) or major APIs.
     - Database schema should show new or modified tables including columns, type, size, and
       foreign keys. Avoid DDL if possible. Database migration is covered in
       "Impact on Current Application".
     - Not an exhaustive list of everything in the design — only enough that the approach is clear. -->

#### Key Components and Changes (ext)

| # | Component | Location | Purpose | Key Changes |
|---|-----------|----------|---------|-------------|
| 1 | | | | |

#### Guice Module Loading Order (ext)

<!-- Include only if Guice module loading order is relevant to this change. -->

N/A

#### AWS Services Used (ext)

<!-- Include only if AWS service interactions are added or changed. -->

| Service | Usage | SDK |
|---------|-------|-----|
| | | |

#### DynamoDB Changes (ext)

<!-- Include only if DynamoDB table/annotation/schema changes are made. -->

| Table | Partition Key | Sort Key | GSIs | Annotation Class |
|-------|--------------|----------|------|-----------------|
| | | | | |

#### Component Interaction Flow (ext)

```
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐
│  Component A  │    │  Component B      │    │  Component C      │    │  Component D  │
├──────────────┤    ├──────────────────┤    ├──────────────────┤    ├──────────────┤
│ 1. step      │    │ 3. step          │    │ 5. step          │    │ 7. step      │
│ 2. step      │    │ 4. step          │    │ 6. step          │    │ 8. step      │
└──────┬───────┘    └──────┬───────────┘    └──────┬───────────┘    └──────────────┘
       │ Change:            │ Change:               │ Change:
       │ what changed       │ what changed          │ what changed
```

### UI

<!-- Details of beans, APIs, class/sequence diagrams. See notes in the Server section above. -->

N/A

### API Architecture

<!-- Documentation on the API's security measures — specifically authentication and
     authorization mechanisms, access privileges, and other controls in place for the API.
     A swagger file may be attached instead. -->

| Use Case | API | Body | Method<br/>(GET/POST/PUT/DELETE) | Query Parameter | Access Privilege<br/>(Admin/Non-Admin User) | Authorization — (Yes/No)<br/>*(If Yes, mention the approach)* | Authentication — (Yes/No)<br/>*(If Yes, mention the approach)* | Remarks |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

#### Endpoints Affected (ext)

| Method | Path | Description | Changes |
|--------|------|-------------|---------|
| | | | |

#### Request/Response Changes (ext)

<!-- State explicitly if nothing changed: "No changes to request body, response body,
     headers, or status codes." -->

N/A

#### Implementation Notes (ext)

<!-- Optional: non-obvious technical details at the API/routing layer — regex syntax, path
     parameter semantics, encoding behaviour. Remove if there is nothing to explain. -->

N/A

---

## Configuration

<!-- Configuration refers to "non-code" externalized files (properties, datasets, etc.):
     resource bundles, Java properties, text/XML/other files, files used for testing.
     If none, say none. Otherwise identify the files AND the primary actor who will change
     them (project teams, operations, PSR team, etc.). -->

### Component-Level Configuration

<!-- Non-code files/properties committed at the component (E2NA, Portal, etc.) level, and the
     primary actor that will change them. -->

N/A

### Model-Level Configuration

<!-- Non-code files/properties committed at the model (E2, E2net, MCM, etc.) level, and the
     primary actor that will change them. -->

N/A

### Stack-Level Configuration

<!-- Items configurable at the Stack Manager (E2PD) level, and the primary actor that will
     change them. Document whether changes are YAML or programmatic (postSetupHook etc). -->

| Setting | Before | After | Scope | Changed by |
|---------|--------|-------|-------|-----------|
| | | | | |

### Professional Services/System Integrator Configuration

<!-- How to configure the features intended for use by PS or SI. Identify files/properties
     committed at the hub (IBMSS, Cisco, etc.) level. -->

N/A

---

## Auditing/Logging

<!-- How auditing will be handled (if required) and the types of logging provided for
     debugging/error conditions. -->

### Logging Details (ext)

| Logger | Level | Message Pattern | When |
|--------|-------|----------------|------|
| | | | |

### Event Publishing (ext)

N/A

---

## Metrics and Statistics

<!-- Metrics/statistics added by this story. See the E2NA Statistics Reference page. -->

N/A

---

## Installer Changes

<!-- Deployment changes: regular deployment, migration deployment, Windows deployment. -->

N/A

---

## Impact on Current Application

<!-- How backwards compatibility will be maintained. If there is no impact (migration is not
     needed), state 'None'. Migration may be needed in these areas — give details if so:
     - Database schema (new tables on hub upgrade, copying data between tables, etc.)
     - Property migration (defaults changed, so a migration script is needed for older hubs)
     - Other file migration (model changes that would break older hub models)
     - Look & feel / UI workflow changes that must be migrated so older hubs keep working -->

### Migration Required

| Area | Needed? | Details |
|------|---------|---------|
| Database schema | | |
| Property migration | | |
| Other file migration | | |
| UI / look & feel | | |

### Runtime Behavior (ext)

<!-- Observable behaviour changes per scenario, e.g.:
     - "Names with X: now work correctly (previously HTTP 400)"
     - "Names without X: no change in behaviour"
     - "Other endpoints: no functional change" -->

### Performance (ext)

<!-- Any performance impact, or state explicitly there is none and briefly why. -->

### Deployment (ext)

<!-- Rolling restart? Config change required? Coordinated deploy? Data migration?
     "Standard rolling restart. No data migration, no config changes, no coordinated
     deployment needed." is a complete answer. -->

---

## Resiliency

<!-- Design considerations for resiliency of the component being developed — failover, retry,
     circuit breaker. Include any defensive guards added (e.g. WARN log on unexpected config). -->

N/A

---

## Temporary object cleanup, temporary files cleanup

<!-- Life of objects/files. If temporary files are created, when are they purged? Does the
     program take care of them automatically? -->

N/A

---

## Impact on Tools

<!-- Changes this design forces into other tools. -->

N/A

---

## Impact on Other Components

<!-- Impacts to SCPM, E2NA, E2ND, etc. State impact per module/service explicitly:
     - "<Module name>: <impact>" or "<Module name>: None — <reason>"
     - "Shared library impact: None. No changes to <library>."
     - "Other services: None." -->

N/A

---

## Backwards Compatible

<!-- The update to the component is backwards compatible — Yes or No. By default the design
     change should be backwards compatible. If there are breaking changes, call them out
     specifically and inform the dependent components as well.
     Answer all explicitly: API contract changes? Deployable independently without
     coordinating with other services? Data migration needed? Do clients require changes? -->

---

## New/Upgraded Third party Applications/Jars

<!-- Any new 3rd party applications or jars planned, including new versions of existing 3rd
     party. If none, say "None." -->

| Application / Jar | Current Version | New Version | New or Upgrade | Reason | CVEs Addressed |
|---|---|---|---|---|---|
| | | | | | |

---

## Unit Test Plan

<!-- Identify JUnit and manual tests to be performed. -->

### New Tests (ext)

| # | Test Class | Test Method | Coverage |
|---|-----------|-------------|----------|
| 1 | | | |

### Test Layer Coverage (ext)

<!-- Map each change layer to the test class that validates it and how faithfully it reflects
     the real production path. Remove this table if there is only one layer. -->

| Layer | What it protects | Test Class | Faithfulness |
|-------|-----------------|------------|-------------|
| | | | |

### Manual Tests (ext)

| # | Scenario | Steps | Expected Result |
|---|----------|-------|----------------|
| 1 | | | |

### Existing Test Impact (ext)

<!-- Were any existing tests modified? If no: "No existing tests were modified." -->

---

## Risks

<!-- Renders as a red `panel` macro titled "Key Risks" — see storage-format notes. -->

**Key Risks**

- Risk 1
- Risk 2
- Risk 3

---

## Dependencies

<!-- Renders as a blue `panel` macro titled "Major Dependencies" — see storage-format notes. -->

**Major Dependencies**

- Dependency 1
- Dependency 2
- Dependency 3

---

## Pre-Dev Security

[What does the pre-dev security checklist mean in detail?](https://confluence.dev.e2open.com/display/RelMGMT/Release+Management+FAQ%27s#:~:text=What%20does%20the%20pre%2Ddev%20security%20checklist%20mean%20in%20detail%3F)

<!-- The # column holds the official task-list ids — do NOT renumber them. -->

| # | TOPIC | Valid (Y/N) | Comments *(Explain Your Changes)* |
|---|-------|-------------|-----------------------------------|
| 1 | New UI pages/data exposed to users | | |
| 2 | Use of new services/ports | | |
| 3 | Authentication changes | | |
| 4 | New/changed encryption | | |
| 5 | Changes in the way data is transmitted | | |
| 6 | Changes in the way/location data is being stored | | |
| 120 | New API implementation / change of existing APIs (Please fill the API arch table) | | |
| 124 | New / Change in existing file upload functionality | | |
| 125 | New / Change in integration within e2open or third-party apps | | |
| 126 | New / Existing UI functionality support querying via either of them (VST, XML, java expressions, SQL or any other) | | |

---

## REQUIRED: Documentation Changes

Answer the following questions.

| Question | Answer |
|----------|--------|
| Do end users interact with this feature? | |
| Do project teams/SIs/BIT teams need to enable or configure this feature? | |
| Does the feature require special migration from prior releases? | |
| What guides or content sections need updating? | |

### Engineering Documentation Impact (ext)

<!-- Optional — include only when there is real impact. -->

| Area | Impacted? | Details |
|------|-----------|---------|
| API docs (Swagger/OpenAPI) | | |
| Runbook / operational procedures | | |
| Monitoring & alerting | | |

---

## Blocking Issues and Actions from the Design Review

<!-- Blocking action items resulting from the design review — things required before the design
     can be completed. -->

| # | Issue/Action | Owner | Status | Due Date | Resolution |
|---|-------------|-------|--------|----------|------------|
| 1 | | | Open | | |

---

## Deployment Verification (ext)

<!-- Record sign-off after deployment to each environment. Add a subsection per environment.
     Remove this section entirely if the doc is written before deployment. -->

### &lt;ENV&gt; — ✅ / ⚠️ / ❌ (&lt;yyyy-mm-dd&gt;)

| Test | Method | URL | Result |
|------|--------|-----|--------|
| | | | |

<!-- If an environment has a known infrastructure difference that affects results (e.g. upstream
     proxy, load balancer config), document it here explicitly. -->

---

## Design Document Review and Approval Matrix

> Add **"Approved"** or **"NA"** in the status column to approve the design document.
> **Approval Status Should have "Approved" or "NA" Only**

<!-- Renders as a `note` macro — see storage-format notes. -->

| Stage | Reviewer | Status | Notes | Ownership |
|-------|----------|--------|-------|-----------|
| Design | @Arijit Kundu | | | **Product Management** |
| Product Owner | @Mahendran Pandian | | | **Product Owner** |
| Pre Dev Security | @Kamalesh Bhol | | | **InfoSec** |
| Pre Dev Architecture | @Arijit Kundu | | | **Product Development** |
| Browser | NA | NA | | **Product Development** |
| UX | NA | NA | | **Product Development** |
| Post Dev Security | @Kamalesh Bhol | | | **InfoSec** |
| Post Dev Architecture | | | | **Product Development** |
| QA/Test Driven Development (TDD) | @Venkat Ganga | | | **Product Development/QA** |
