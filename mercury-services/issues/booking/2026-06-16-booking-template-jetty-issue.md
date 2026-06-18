# ION-16032: Booking Template Jetty 12 URI Path Separator Fix

## Issue Summary

**Jira Tickets**: [PDSUPPORT-203319], [ION-16032]  
**Reported by**: Subhajit Dutta (support), Rupam Gogoi (engineering)  
**Affected users**: DSV (saijai.yamsri@dsv.com)  
**Priority**: Medium  

### Problem
After the Jetty 11.x → 12.x upgrade (Dropwizard 5.0.1, Jetty 12.1.9), users cannot open booking templates whose names contain a forward slash (`/`).

**Sample failing template names**:
- `Indorama Polyester to MXZLO /HAPAG`
- `TAURUS MANUFACTURING TO AUMEL_MELBOURNE, AUSTRALIA/ANL`

**Error**: HTTP 400 Bad Request — "Ambiguous URI Path Separator"

### Affected Endpoint
`GET /booking/template/{name}` — `TemplateResource.getTemplate()`  
Also affects `PUT` (save) and `DELETE` operations on the same path.

---

## Root Cause Analysis

### Jetty 12 Behavioral Change
Jetty 12 introduced stricter URI compliance enforcement via `UriCompliance`. By default, `UriCompliance.DEFAULT` rejects URIs containing `%2F` (encoded forward slash) in path segments, treating it as an "ambiguous path separator" (`UriCompliance.Violation.AMBIGUOUS_PATH_SEPARATOR`).

In Jetty 11.x, encoded `%2F` in path segments was allowed by default.

### Request Flow
1. Client sends: `GET /booking/template/Indorama%20Polyester%20to%20MXZLO%20%2FHAPAG`
2. Jetty 12 HTTP layer parses the URI
3. Jetty detects `%2F` in path → `AMBIGUOUS_PATH_SEPARATOR` violation
4. Since `UriCompliance.DEFAULT` does NOT allow this violation, Jetty returns **HTTP 400** immediately
5. The request never reaches the JAX-RS layer (Jersey/TemplateResource)

### JAX-RS Routing Issue
Even if Jetty accepts the URI, there's a secondary issue:
- `@Path("/{name}")` matches only a single path segment (no `/` allowed)
- When `%2F` is decoded to `/`, JAX-RS routing treats it as a path separator
- `/template/hello/world` with `{name}` would match `name = "hello"` only → **404**
- Need `@Path("/{name: .+}")` to capture the full name including decoded `/`

---

## Impact Assessment

### Characters Affected
| Character | Encoded | Affected by Jetty 12? | Affected by `{name}` pattern? |
|-----------|---------|----------------------|------------------------------|
| `/`       | `%2F`   | ✅ YES (400 error)    | ✅ YES (routing mismatch)     |
| ` ` (space)| `%20`  | ❌ No                 | ❌ No                         |
| `&`       | `%26`   | ❌ No                 | ❌ No                         |
| `(`/`)`   | `%28`/`%29` | ❌ No             | ❌ No                         |
| `,`       | `%2C`   | ❌ No                 | ❌ No                         |
| `_`       | N/A     | ❌ No                 | ❌ No                         |

Only `/` (forward slash) is affected. Other special characters in template names work fine.

### Endpoints Impacted
- `GET /booking/template/{name}` — get template
- `PUT /booking/template/{name}` — save template
- `DELETE /booking/template/{name}` — delete template

**Scope of the `UriCompliance` relaxation:** `UriCompliance` is a *per-connector* Jetty setting and cannot be scoped to a single path. The relaxation is therefore applied **connector-wide** (all application and admin connectors), so `AMBIGUOUS_PATH_SEPARATOR` is permitted for *every* booking endpoint — not just `/template`. This is safe: all other path-param endpoints (`CarrierBookingResource`, `CustomerBookingResource`, `SearchResource`, `OutboundResource`, `RapidReservationResource`, `CarrierSpotRatesResource`, `DangerousGoodsResource`) keep their default `[^/]+` route regex, so an encoded slash in those paths still fails to match and now returns **404 from Jersey** instead of **400 from Jetty** — the same rejection, at a different layer. Only the `/template/{name: .+}` endpoints opt into matching a `/`.

---

## Fix Options Evaluated

### Option A: Configure Jetty UriCompliance (SELECTED)
Configure `UriCompliance.DEFAULT.with("BOOKING", Violation.AMBIGUOUS_PATH_SEPARATOR)` on the server's HTTP connectors.

**Pros**: Minimal change, non-breaking, targeted (only allows AMBIGUOUS_PATH_SEPARATOR)  
**Cons**: Requires server-level configuration  
**Security**: Only `AMBIGUOUS_PATH_SEPARATOR` is relaxed. Path traversal protection (`AMBIGUOUS_PATH_SEGMENT`, `AMBIGUOUS_PATH_ENCODING`) remains enforced.

### Option B: Change to Query Parameters (NOT SELECTED)
Change `/{name}` to `?name=...` for template name.

**Pros**: Pure application-level, avoids all URI encoding issues  
**Cons**: **Breaks API compatibility** — all existing clients (frontend, API consumers) must change  
**Risk**: HIGH — real downside risk of breaking existing integrations

### Option C: Use UriCompliance.LEGACY (NOT SELECTED)
Set `UriCompliance.LEGACY` which allows ALL violations.

**Pros**: Simple one-line change  
**Cons**: **Too permissive** — allows ambiguous path segments, path encoding tricks, etc.  
**Risk**: HIGH — potential security vulnerabilities (path traversal)

### Decision
**Option A** is selected because:
1. Option B has "real downside risk" (API breaking change)
2. Option A is targeted and secure (only allows the specific violation needed)
3. The `with()` method on `UriCompliance.DEFAULT` preserves all other security protections

---

## Implementation Plan

### Change 1: TemplateResource — Path Annotation
**File**: `booking/src/main/java/com/inttra/mercury/booking/template/TemplateResource.java`

Change `@Path("/{name}")` to `@Path("/{name: .+}")` on all three methods (GET, PUT, DELETE).

This allows JAX-RS to match template names containing decoded `/` characters.

### Change 2: BookingApplication — UriCompliance Configuration
**File**: `booking/src/main/java/com/inttra/mercury/booking/BookingApplication.java`

Add a `postSetupHook` that configures Jetty's `UriCompliance` on all application connectors via `DefaultServerFactory`:

```java
.postSetupHook(BookingApplication::configureUriCompliance)
```

### Change 3: Tests
**File**: `booking/src/test/java/com/inttra/mercury/booking/template/TemplateResourceTest.java`

Add parameterized tests verifying template names with special characters (especially `/`) work correctly at the resource level.

---

## Testing Strategy

1. **Unit tests**: Parameterized tests for TemplateResource methods with template names containing:
   - Forward slash: `"Indorama Polyester to MXZLO /HAPAG"`
   - Multiple slashes: `"A/B/C"`
   - Trailing slash: `"template/"`
   - Space + slash: `"template name / carrier"`
   - Other special chars: `&`, `(`, `)`, `,`, `_`

2. **Full test suite**: `mvn test -pl booking` and `mvn verify -pl booking`

3. **Manual verification**: Test with actual template names from Jira ticket

---

## Jira References
- **PDSUPPORT-203319**: Original support ticket
- **ION-16032**: Engineering defect ticket

---

## FAQ: Impact Analysis

### Does `@Path("/{name: .+}")` affect template names that do NOT contain `/`?

**No impact.** The previous implicit JAX-RS regex for `{name}` was `[^/]+` (one or more non-slash characters). The new explicit regex `.+` matches "one or more of any character". For template names without `/`, both patterns match identically — the routing behavior is unchanged.

| Template Name | Old `[^/]+` | New `.+` |
|---------------|-------------|----------|
| `"My Template"` | ✅ Matches | ✅ Matches |
| `"Template_v2"` | ✅ Matches | ✅ Matches |
| `"A & B (test)"` | ✅ Matches | ✅ Matches |
| `"Name /Carrier"` | ❌ No match | ✅ Matches |

Edge case: An empty string `""` is not matched by either regex (both require at least one character), and is independently blocked by the `@NotEmpty` annotation on the path parameter.

### Does the `UriCompliance` change affect other endpoints in the application?

**No functional impact on existing endpoints.** The change from `UriCompliance.DEFAULT` to `UriCompliance.DEFAULT.with(AMBIGUOUS_PATH_SEPARATOR)` means:

1. **Normal requests** (no `%2F` in path): Processed identically as before — no change in behavior.
2. **Requests with `%2F` in path**: Previously rejected with HTTP 400 by Jetty; now allowed through to the servlet/JAX-RS layer.

The relaxation is connector-wide (see *Scope of the `UriCompliance` relaxation* above), so the Jetty-layer 400 is removed for **all** booking endpoints. However, every other path-param endpoint keeps its default `[^/]+` route regex, so an encoded slash there still does not match a route and is rejected — it simply surfaces as a **404 from Jersey** rather than a **400 from Jetty**. No existing endpoint changes its functional outcome. The only endpoints that newly *accept* a `/` in a path parameter are the `/template/{name: .+}` ones, which is the intended fix.

**Security protections preserved:**

| Protection | Violation Enum | Still Enforced? |
|-----------|---------------|-----------------|
| Path traversal via `/../` | `AMBIGUOUS_PATH_SEGMENT` | ✅ Yes |
| Double-encoded paths `%252F` | `AMBIGUOUS_PATH_ENCODING` | ✅ Yes |
| Path parameters `;param=value` | `AMBIGUOUS_PATH_PARAMETER` | ✅ Yes |
| Empty segments `//` | `AMBIGUOUS_EMPTY_SEGMENT` | ✅ Yes |
| UTF-16 encoding tricks | `UTF16_ENCODINGS` | ✅ Yes |
| Encoded slash `%2F` in path | `AMBIGUOUS_PATH_SEPARATOR` | ❌ Relaxed (intentional) |

The only relaxation is `AMBIGUOUS_PATH_SEPARATOR`, which is specifically needed for template names containing `/`. All other URI compliance protections remain fully enforced.

### What does `{name: .+}` mean? Why the colon `:` syntax?

The JAX-RS `@Path` template syntax is: `{parameterName : regex}`

- The **colon** `:` is simply a separator between the parameter name and its matching regex.
- `{name}` was always shorthand for `{name: [^/]+}` — JAX-RS just hides the default regex.
- `{name: .+}` makes the regex explicit — the parameter is still called `name`.

Here's how the pieces map together:

```
@Path("/{name: .+}")                         ← path template
         ^^^^  ^^
         |     |
         |     └── regex: what characters to match (.+ = any one or more chars)
         |
         └──────── parameter name: what @PathParam binds to

public Template getTemplate(@PathParam("name") String name)
                                        ^^^^
                                        └── matches the "name" in {name: .+}
```

**Before**: `@Path("/{name}")` → hidden regex `[^/]+` (any char except `/`, one or more)  
**After**: `@Path("/{name: .+}")` → explicit regex `.+` (any char including `/`, one or more)

The `@PathParam("name")` binding is unchanged — it still receives the captured value as a `String`. The only difference is what the URL pattern is allowed to match.

---

## Claude Critical Review

*Reviewer: Claude Opus 4.8 — 2026-06-16. Reviewed the actual code on the branch (`TemplateResource.java`, `BookingApplication.java`, `TemplateResourceTest.java`), the Copilot session log (`6096647d2705479f`), and the rest of the booking resource layer.*

### Verdict

The **fix approach is correct and is the right call.** The two-part fix (Jetty `UriCompliance` relaxation + JAX-RS `{name: .+}` regex) is the standard, documented recipe for encoded-slash path params on Jetty 12, and the choice of Option A over query-params (B) or `LEGACY` (C) is well-reasoned. The stated goal — *no impact to existing API or to template names without `/`* — is **met for production behavior**.

However, the **test coverage does not actually cover the reported bug**, and the **blast radius of the `UriCompliance` change is wider than the doc states**. Details below, ordered by importance.

### 🔴 Finding 1 — The added tests give false confidence; the actual bug is untested

The reported failure is an **HTTP 400 raised by Jetty before the request reaches Jersey**. None of the new tests exercise Jetty or Jersey routing:

- **Parameterized tests** (`getTemplate_shouldHandleSpecialCharactersInName`, `deleteTemplate_shouldHandleSlashInName`) call the resource method **directly as a Java method** — `templateResource.getTemplate(securityContext, "A/B/C")`. This bypasses URI parsing, `UriCompliance`, decoding, and routing entirely. The `.+` vs `[^/]+` distinction is invisible to a direct method call, so **these tests would pass even with the fix reverted.** They effectively test the Mockito mock, not the fix.
- **`configureUriCompliance()` has zero test coverage.** The entire Jetty-layer half of the fix — the part that actually resolves the 400 — is unverified. Nothing asserts that the hook is wired, that it allows `AMBIGUOUS_PATH_SEPARATOR`, or (critically for the security claim) that it does **not** relax the other violations.

What *is* legitimately covered: the three `*_pathAnnotation_shouldAllowSlashesInTemplateName` tests read the `@Path` value via reflection and assert a slash-containing name matches the extracted regex. Because `extractPathParamRegex` falls back to `[^/]+` when no explicit regex is present, these tests **do** fail if the annotation regresses to `{name}` — so they are a meaningful guard on the annotation value. Credit where due. But note `assertThat(name).matches(".+")` is otherwise near-tautological (`.+` matches every non-empty string).

**Recommendation:** Add a real HTTP-level test using `DropwizardAppExtension` (or `ResourceExtension` for routing only) that issues `GET /booking/template/<name%20with%2Fslash>` and asserts **200, not 400/404** — and a companion negative test confirming a path-traversal attempt (`%2e%2e%2f`) is still rejected. There is currently **no** `DropwizardAppExtension`/`ResourceExtension`/`JerseyTest` anywhere under `booking/src/test`, so this is a net-new harness, but it is the only thing that actually proves the bug is fixed and stays fixed. At minimum, add a focused unit test on `configureUriCompliance` asserting the resulting `UriCompliance` allows `AMBIGUOUS_PATH_SEPARATOR` and still disallows `AMBIGUOUS_PATH_SEGMENT`/`AMBIGUOUS_PATH_ENCODING`.

### 🟠 Finding 2 — The `UriCompliance` relaxation is application-wide, not template-scoped

`setUriCompliance(...)` is applied to **every application connector**, so `AMBIGUOUS_PATH_SEPARATOR` is now permitted for **all** booking endpoints — not just `/template`. The doc's statement *"No functional impact on existing endpoints"* is true for **routing** but understates the change: the app-wide security posture for encoded slashes has changed for every path-param endpoint, including `CarrierBookingResource`, `CustomerBookingResource`, `SearchResource`, `OutboundResource`, `RapidReservationResource`, etc.

In practice the **functional** risk is low: those endpoints keep the default `[^/]+` regex, so an injected decoded `/` still won't match their templates — the request now returns **404 from Jersey** instead of **400 from Jetty**. Same rejection, different layer/status. This is acceptable, because `UriCompliance` is a **per-connector** setting in Jetty — there is no per-path way to scope it, so app-wide is the only option for Option A. The point is that the doc should **state the real scope** rather than imply it is template-only.

**Recommendation:** Update the "Endpoints Impacted" / impact section to say the compliance relaxation applies connector-wide, and that other path-param endpoints remain protected by their `[^/]+` route regex (encoded slash → 404, not a match). The naming `with("BOOKING", …)` reinforces that this is an app-level, not template-level, policy.

### 🟡 Finding 3 — Hook fails silently if the server factory is not `DefaultServerFactory`

`configureUriCompliance` is guarded by `instanceof DefaultServerFactory`. If a future config (or any environment) uses `SimpleServerFactory`, the hook is a **no-op with no warning** — the 400 would silently return and look like a regression with no log trail. Booking currently uses the default (`server:` with application/admin connectors), so this is fine **today**, but a defensive `LOGGER.warn(...)` in the `else` branch would prevent a confusing future incident.

### 🟢 Finding 4 — Minor / cosmetic

- **Doc vs code drift:** the doc (Option A and Implementation Plan) shows `with("BOOKING_TEMPLATE", …)`; the code uses `with("BOOKING", …)`. The string is just a label for the custom compliance mode and is harmless, but the doc should match the code (or vice-versa) to avoid confusion.
- **Admin connectors:** the hook also sets compliance on admin connectors. Harmless, but unnecessary — the template endpoint is on the application connector. Not worth changing.
- **`@NotEmpty` + `.+`:** correctly redundant-but-safe. `.+` already rejects an empty trailing segment (`/template/`), and `@NotEmpty` is a second guard at the bean-validation layer. No issue.

### Routing correctness checks (passed)

- `GET /booking/template` still resolves to `listTemplates()` — `{name: .+}` requires a non-empty sub-path, so there is no ambiguity with the collection endpoint. ✅
- Names without `/` route identically under `.+` and `[^/]+`. ✅ (The FAQ table in this doc is accurate.)
- Path traversal: Jetty still normalizes `..` segments and still enforces `AMBIGUOUS_PATH_SEGMENT`/`AMBIGUOUS_PATH_ENCODING`, and `templateService` lookups are actor-scoped DynamoDB key reads — a decoded `/` in the name is data, not a filesystem/route traversal vector. ✅

### Summary of recommended actions

| # | Severity | Action | Blocks merge? |
|---|----------|--------|---------------|
| 1 | 🔴 High | Add an HTTP-level test (DropwizardAppExtension/ResourceExtension) proving `%2F` name → 200, and a unit test on `configureUriCompliance` asserting only `AMBIGUOUS_PATH_SEPARATOR` is relaxed. The current parameterized tests do not exercise the fix. | Recommended before merge — otherwise the fix is unverified by CI and could silently regress. |
| 2 | 🟠 Med | Correct the doc to state the compliance change is **connector-wide**; note other endpoints stay protected by `[^/]+` (encoded slash → 404). | No — doc accuracy |
| 3 | 🟡 Low | Add `LOGGER.warn` in the `else` branch of the `instanceof` check. | No |
| 4 | 🟢 Nit | Align `with("BOOKING"/"BOOKING_TEMPLATE")` label between doc and code. | No |

**Bottom line on the stated goal:** No impact to the existing API contract or to non-`/` template names — **confirmed.** No impact to the booking application at runtime — **confirmed** (other endpoints unaffected in behavior). Good test coverage — **not yet met**: the bug itself and the Jetty config are untested; the existing tests would pass with the fix reverted. Closing Finding 1 is what turns "QA passed" into "regression-proof."

---

### Resolution — recommendations implemented (2026-06-16)

All four findings have been addressed on the branch. Full booking unit suite after the changes: **2019 tests, 0 failures, 0 errors** (`mvn test -pl booking`).

**Finding 1 (🔴) — closed.** The original "at minimum" recommendation (a focused unit test on the UriCompliance config) is implemented, and the routing half is now covered by a faithful test rather than the heavy DropwizardAppExtension harness. Rationale for not adding `dropwizard-testing`: there is **no** in-memory Jersey/Dropwizard test harness anywhere in the `booking` module, and the module's `pom.xml` carefully manages Jackson classpath conflicts — pulling in `dropwizard-testing`/`jersey-test-framework` would be a real destabilization risk with no precedent. Instead, using only libraries already on the classpath:

- **`BookingApplicationUriComplianceTest`** (new) — verifies the Jetty-layer half (the actual HTTP 400) against Jetty's real `UriCompliance` engine and Dropwizard's real `DefaultServerFactory`/`HttpConnectorFactory`:
  - `bookingUriCompliance` relaxes **exactly** `AMBIGUOUS_PATH_SEPARATOR` on top of `DEFAULT` (the security claim — would fail on a switch to `LEGACY`/`UNSAFE`);
  - path-traversal / encoding protections (`AMBIGUOUS_PATH_SEGMENT`, `AMBIGUOUS_PATH_ENCODING`, `AMBIGUOUS_PATH_PARAMETER`, `AMBIGUOUS_EMPTY_SEGMENT`) remain **disallowed**;
  - Jetty `DEFAULT` does **not** allow `AMBIGUOUS_PATH_SEPARATOR` (baseline — confirms the change is meaningful);
  - `applyUriCompliance` actually sets the compliance on **every** application and admin HTTP connector (the wiring).
- **`TemplateResourceTest.JaxRsRoutingMatchesDecodedSlashNames`** (new) — feeds the *decoded* path (literal `/`, as the servlet hands Jersey) into Jersey's real `UriTemplate` matcher, reading the template from the live `@Path` annotations: the production `{name: .+}` matches a slash name and captures the **full** name; the pre-fix `{name}` (default `[^/]+`) does **not** match it (reproduces the routing bug and fails if the annotation regresses); non-slash names match identically under both (the "no impact" claim).

This means a revert of either half of the fix now fails a test in CI, which is what was missing.

**Finding 2 (🟠) — closed.** Doc updated to state the relaxation is connector-wide (see *Scope of the `UriCompliance` relaxation* and the revised FAQ), and a matching Javadoc note was added to `configureUriCompliance`.

**Finding 3 (🟡) — closed.** `configureUriCompliance` now logs a `LOGGER.warn` (naming the actual factory class) when the server factory is not a `DefaultServerFactory`, instead of silently no-op'ing. The body was refactored into package-private `bookingUriCompliance()` and `applyUriCompliance(DefaultServerFactory)` for testability — behaviour is unchanged.

**Finding 4 (🟢) — closed.** Doc label aligned to the code's `with("BOOKING", …)` in both Option A and this section.
