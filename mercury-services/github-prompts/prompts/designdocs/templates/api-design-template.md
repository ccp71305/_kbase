# API Design Document Template

> Sections with no applicable content should contain "N/A".

---

## Contributors

| Role | Name |
|------|------|
| Author | |
| Reviewer | |

---

## Requirements

### Jira Tickets

| Key | Summary | Type | Priority | Status |
|-----|---------|------|----------|--------|
| | | | | |

### Summary

<!-- What API is being designed/changed and why -->

---

## API Overview

<!-- Purpose, consumers, and scope of this API -->

---

## Endpoints

| Method | Path | Description | Auth | Change Type |
|--------|------|-------------|------|-------------|
| | | | | New / Modified / Deprecated |

---

## Request / Response Contracts

<!-- Per endpoint: request headers, path/query params, request body schema, response body schema -->

---

## Authentication & Authorization

<!-- Auth mechanism, required roles/scopes, token handling -->

---

## Versioning

<!-- API version strategy, backwards compatibility, deprecation policy -->

---

## Error Codes

| HTTP Status | Code | Message | When |
|-------------|------|---------|------|
| | | | |

---

## Rate Limiting & Quotas

N/A

---

## Security Checklist

| # | Question | Yes/No | Comments |
|---|----------|--------|----------|
| 1 | Is input validated at all public boundaries? | | |
| 2 | Are sensitive fields excluded from responses? | | |
| 3 | Are all endpoints protected by appropriate auth? | | |
| 4 | Are there injection risks (SQL, LDAP, command)? | | |

---

## Impact on Other Components

<!-- Downstream consumers, SDKs, generated clients that need updating -->

---

## Required Documentation Changes

<!-- Swagger/OpenAPI updates, migration guides, changelog entries -->

---

## Review

| # | Reviewer | Role | Status |
|---|----------|------|--------|
| 1 | | Author | Draft |
| 2 | | Peer Reviewer | Pending |
