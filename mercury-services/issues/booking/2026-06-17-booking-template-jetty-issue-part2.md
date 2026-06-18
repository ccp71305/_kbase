# ION-16032: Booking Template Jetty 12 — Part 2: ee10 Servlet Layer Compliance

## Issue Summary

**Date:** 2026-06-17  
**Ticket:** ION-16032 / PDSUPPORT-203319  
**Previous Analysis:** [2026-06-16-booking-template-jetty-issue.md](2026-06-16-booking-template-jetty-issue.md)  
**Analyst:** Claude Opus 4.6 Agent  
**Session:** `a8666741fee34c39`

### Problem

After deploying the `UriCompliance` + `{name: .+}` fix to QA, users **still** get HTTP 400 when accessing booking templates whose names contain a forward slash (`/`).

### Key Finding

**Jetty 12 has TWO independent URI compliance enforcement layers**, and the deployed fix only addresses ONE of them:

| Layer | Mechanism | Our Fix | Status |
|-------|-----------|---------|--------|
| **Jetty HTTP** (connector) | `HttpConfiguration.getUriCompliance()` | `setUriCompliance(DEFAULT.with(AMBIGUOUS_PATH_SEPARATOR))` | ✅ Working |
| **ee10 Servlet** (Servlet 6.0) | `ServletContextRequest → ServletHandler.isDecodeAmbiguousURIs()` | *Not configured* | ❌ **Still blocking** |

---

## Investigation Steps

### Step 1: Verify ECS Deployment Status

**Query:**
```bash
aws ecs describe-services --cluster arn:aws:ecs:us-east-1:642960533737:cluster/ANEQABK-001 \
  --services Booking-qa --profile 642960533737_INTTRA2-QATeam \
  --query "services[0].{status,runningCount,desiredCount,taskDefinition,deployments[*].{status,runningCount,taskDefinition,createdAt,rolloutState}}"
```

**Result:** Deployment COMPLETED at 2026-06-17T09:29 ET, 2/2 tasks running on `Booking-latest-qa-Task:15`.

**Conclusion:** Deployment is healthy. The fix code should be live.

---

### Step 2: Confirm Fix Is in the Running Containers

**Query — search for UriCompliance configuration log:**
```bash
aws logs filter-log-events --log-group-name inttra2-qa-lg-bkapi \
  --filter-pattern '"UriCompliance"' --start-time <6h_ago> \
  --profile 642960533737_INTTRA2-QATeam
```

**Initial result:** Empty (no matches). This was because the initial log search used the wrong time window.

**Query — targeted search around known container startup time (13:25–13:27 UTC):**
```bash
aws logs filter-log-events --log-group-name inttra2-qa-lg-bkapi \
  --start-time 1781702750000 --end-time 1781702780000 \
  --profile 642960533737_INTTRA2-QATeam \
  --query "events[*].message" --output text | Select-String "Uri|BOOKING|compliance"
```

**Result:**
```
com.inttra.mercury.booking.BookingApplication: Configured Jetty UriCompliance to allow AMBIGUOUS_PATH_SEPARATOR for template names
```
This message appeared TWICE (once per container), confirming both tasks have the fix.

**Query — verify route annotations:**
```bash
aws logs filter-log-events --log-group-name inttra2-qa-lg-bkapi \
  --filter-pattern '"version"' --start-time <3h_ago> \
  --profile 642960533737_INTTRA2-QATeam
```

**Result (from the Dropwizard resource listing at startup):**
```
DELETE  /booking/template/{name: .+} (com.inttra.mercury.booking.template.TemplateResource)
GET     /booking/template/{name: .+} (com.inttra.mercury.booking.template.TemplateResource)
PUT     /booking/template/{name: .+} (com.inttra.mercury.booking.template.TemplateResource)
```

**Conclusion:** ✅ Both code changes are deployed — the `{name: .+}` JAX-RS annotation AND the `UriCompliance` connector configuration.

---

### Step 3: Search for Actual Failing Requests

**Query — search for HTTP 400 responses in access logs since containers started:**
```bash
aws logs filter-log-events --log-group-name inttra2-qa-lg-bkapi \
  --filter-pattern '" 400 "' --start-time 1781702760000 --limit 20 \
  --profile 642960533737_INTTRA2-QATeam
```

**Result — the smoking gun:**
```
10.16.44.135 - - [17/Jun/2026:14:48:50 +0000] "OPTIONS /booking/template/BK_Test%2F001 HTTP/1.1" 400 0 "https://booking-beta.inttra.e2open.com/" "Mozilla/5.0 ..." 3
10.16.44.135 - - [17/Jun/2026:14:49:20 +0000] "OPTIONS /booking/template/BK_Test%2F001 HTTP/1.1" 400 0 "https://booking-beta.inttra.e2open.com/" "Mozilla/5.0 ..." 7
10.16.44.156 - - [17/Jun/2026:15:31:16 +0000] "OPTIONS /booking/template/Arijit_test%2F001 HTTP/1.1" 400 0 "https://booking-beta.inttra.e2open.com/" "Mozilla/5.0 ..." 1
10.16.44.156 - - [17/Jun/2026:15:31:55 +0000] "OPTIONS /booking/template/Arijittest%2F001 HTTP/1.1" 400 0 "https://booking-beta.inttra.e2open.com/" "Mozilla/5.0 ..." 0
```

**And a WORKING request (without `%2F`):**
```
10.16.44.156 - - [17/Jun/2026:15:32:11 +0000] "OPTIONS /booking/template/Arijit-test-001 HTTP/1.1" 200 31 "https://booking-beta.inttra.e2open.com/" "Mozilla/5.0 ..." 1
```

**Key Observations:**
1. The failing requests are **`OPTIONS`** (CORS preflight) — the browser sends these before the actual `GET`/`PUT`/`DELETE`.
2. All failing requests have `%2F` in the path. The working one does NOT.
3. Response body is **0 bytes** and response time is **0–7ms** — characteristic of Jetty rejecting at the HTTP/Servlet layer before reaching Jersey.
4. The working request has a corresponding `MercuryRequestLoggingFilter` log entry (reaches Jersey). The failing ones do NOT.

**Conclusion:** Requests with `%2F` are still being rejected with 400 BEFORE reaching Jersey, even though `UriCompliance` is configured on the connector.

---

### Step 4: Investigate Upstream Components (CloudFront, WAF, ALB)

**Purpose:** Rule out that the 400 comes from CloudFront, WAF, or ALB rather than the booking service.

**Query — find target groups:**
```bash
aws elbv2 describe-target-groups --profile 642960533737_INTTRA2-QATeam \
  --query "TargetGroups[*].{Name:TargetGroupName}" --output json \
  | python -c "..." | grep -i book
```

**Result:** Found `INTTRA2-TG-QA-BKAPI` (on `ALB-QA-APPWAY-WS`), `tg-qa-bkapi-e2open`, and `tg-qa-ptui-bk-ecs` (on `alb-qa-ptui-ecs`).

**Query — check CloudFront distributions:**
```bash
aws cloudfront list-distributions --profile 642960533737_INTTRA2-QATeam \
  --query "DistributionList.Items[*].[Id,DomainName,Comment,Origins.Items[0].DomainName]" --output text
```

**Result:** CloudFront distribution `E2IOQPHIQRDPXV` (`beta.inttra.e2open.com`) → origin `alb-qa-ptui-ecs`.

**Query — check WAF rules:**
```bash
aws wafv2 get-web-acl --name "WACLv2-ALB-QA-US-EAST-1" --scope REGIONAL --id "7a2ce0e6-..." \
  --profile 642960533737_INTTRA2-QATeam
```

**Result:** WAF has `AWSManagedRulesCommonRuleSet` (OWASP) but WAF returns **403** not 400. The 400 is NOT from WAF.

**Key evidence that the 400 is from Jetty (not upstream):** The access log entry IS in the booking service's CloudWatch log group (`inttra2-qa-lg-bkapi`), meaning the request DID reach the booking ECS container. The 400 is generated by Jetty/Dropwizard inside the container.

**Conclusion:** The 400 is definitely from Jetty inside the booking service, not from CloudFront, WAF, or ALB.

---

### Step 5: Analyze Jetty Request Flow (Code Investigation)

**Purpose:** Understand why `UriCompliance` configuration doesn't prevent the 400.

**5a. Verify `HttpConnectorFactory.setUriCompliance()` applies correctly:**

Decompiled `HttpConnectorFactory` (Dropwizard 5.0.1 `dropwizard-jetty-5.0.1.jar`):

```java
// In buildHttpConnectionFactory():
HttpConfiguration clonedConfiguration = new HttpConfiguration(httpConfig);
clonedConfiguration.setHttpCompliance(httpCompliance);
clonedConfiguration.setUriCompliance(uriCompliance);     // ← OUR VALUE IS APPLIED HERE
final HttpConnectionFactory httpConnectionFactory = new HttpConnectionFactory(clonedConfiguration);
```

**Conclusion:** The `uriCompliance` field IS read and applied to the `HttpConfiguration` during connector build. The connector-level fix is correct.

**5b. Check where Jetty actually rejects the URI:**

Decompiled `HttpParser` (Jetty 12.1.9 `jetty-http-12.1.9.jar`):
- `HttpParser` only has `HttpCompliance` (for HTTP protocol), NOT `UriCompliance`
- URI violations are recorded in `HttpURI.Mutable._violations` during parsing
- The violations are NOT checked against `UriCompliance` at the parser level

**5c. Found the enforcement point — `ServletContextRequest`:**

```bash
# In jetty-ee10-servlet-12.1.5.jar:
javap -p -c org.eclipse.jetty.ee10.servlet.ServletContextRequest
```

**Result — THE ROOT CAUSE (bytecode translated to Java):**

```java
// In ServletContextRequest (Jetty ee10 Servlet layer):
if (getHttpURI().hasViolations()) {                              // ← ANY violations?
    if (!servletHandler.isDecodeAmbiguousURIs()) {               // ← defaults to FALSE
        for (Violation v : httpURI.getViolations()) {
            if (UriCompliance.AMBIGUOUS_VIOLATIONS.contains(v)) { // ← AMBIGUOUS_PATH_SEPARATOR is in this set
                // Build error: "Ambiguous URI encoding: ..."
                return new AmbiguousURI(request, message);        // → results in HTTP 400
            }
        }
    }
    // If isDecodeAmbiguousURIs() == true, skips the check entirely
}
```

**Key Bytecode Evidence:**
```
4: invokeinterface #216  // HttpURI.hasViolations:()Z
9: ifeq 136              // if no violations, skip to line 136 (allow)
22: invokevirtual #221   // ServletHandler.isDecodeAmbiguousURIs:()Z
25: ifne 136             // if TRUE, skip to line 136 (allow)
64: getstatic #244       // UriCompliance.AMBIGUOUS_VIOLATIONS
68: invokeinterface #250 // Set.contains(violation)
123: new #272            // new AmbiguousURI exception → 400
```

**5d. Verify `setDecodeAmbiguousURIs` exists:**

```bash
javap -classpath jetty-ee10-servlet-12.1.5.jar org.eclipse.jetty.ee10.servlet.ServletHandler \
  | grep -i "DecodeAmbiguous"
```

**Result:**
```
public boolean isDecodeAmbiguousURIs();
public void setDecodeAmbiguousURIs(boolean);
```

**5e. Verify how to access this in Dropwizard:**

```bash
javap -classpath dropwizard-core-5.0.1.jar io.dropwizard.core.setup.Environment \
  | grep -i "ApplicationContext\|servlet"
```

**Result:**
```
public io.dropwizard.jetty.MutableServletContextHandler getApplicationContext();
```

And `MutableServletContextHandler` extends `ServletContextHandler` which has `getServletHandler()`.

---

## Root Cause: Dual-Layer Compliance in Jetty 12

### Architecture

```
Browser Request: OPTIONS /booking/template/BK_Test%2F001
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: Jetty HTTP Connector                                    │
│ Check: HttpConfiguration.getUriCompliance().allows(violation)    │
│ Config: HttpConnectorFactory.setUriCompliance(...)               │
│ Status: ✅ FIXED — allows AMBIGUOUS_PATH_SEPARATOR               │
│ Effect: %2F passes through HTTP parsing                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: ee10 Servlet (ServletContextRequest)                    │
│ Check: httpURI.hasViolations() &&                                │
│        !servletHandler.isDecodeAmbiguousURIs() &&                │
│        AMBIGUOUS_VIOLATIONS.contains(violation)                  │
│ Config: ServletHandler.setDecodeAmbiguousURIs(true)              │
│ Status: ❌ NOT CONFIGURED — defaults to false → rejects with 400 │
└─────────────────────────┬───────────────────────────────────────┘
                          │ (never reached for %2F requests)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: Jersey / JAX-RS                                         │
│ Route: @Path("/{name: .+}")                                      │
│ Config: Regex allows / in path param                             │
│ Status: ✅ FIXED — would work if request reached here             │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Wasn't Caught

1. The unit test (`BookingApplicationUriComplianceTest`) verifies the `UriCompliance` object and factory wiring — but this only tests Layer 1.
2. The JAX-RS routing test (`TemplateResourceTest`) verifies `{name: .+}` regex matching — but this only tests Layer 3.
3. **Layer 2 (ee10 Servlet) is never exercised** because there's no full HTTP integration test (no `DropwizardAppExtension`).

This is precisely what the Claude Critical Review (Finding 1, 🔴) warned about: *"the added tests give false confidence; the actual bug is untested"* — and the mitigation added was still limited to layers 1 and 3.

---

## Fix Shipped (2026-06-17, branch `defect/ION-16032-bk-template-issue-2`)

### Code Change

**File:** `booking/src/main/java/com/inttra/mercury/booking/BookingApplication.java`

`configureUriCompliance` now configures **both** Jetty 12 enforcement layers. The connector half is unchanged; the new servlet-layer half is applied via a package-private `applyServletAmbiguousUriDecoding` helper (so it can be driven directly from an in-container test):

```java
private static void configureUriCompliance(BookingConfig config, Environment environment, Injector injector) {
    if (config.getServerFactory() instanceof DefaultServerFactory serverFactory) {
        applyUriCompliance(serverFactory);                                  // Layer 1 — connector
        LOGGER.info("Configured Jetty UriCompliance to allow AMBIGUOUS_PATH_SEPARATOR for template names");
    } else {
        LOGGER.warn("Server factory is {} (not DefaultServerFactory); UriCompliance for "
                + "AMBIGUOUS_PATH_SEPARATOR was NOT applied. Template names containing '/' "
                + "will fail with HTTP 400 (ION-16032).",
                config.getServerFactory() == null ? "null" : config.getServerFactory().getClass().getName());
    }

    // ION-16032: connector-level UriCompliance alone is NOT sufficient on Jetty 12 — the ee10 servlet
    // layer performs a second, independent ambiguous-URI check. Configure it on the application context.
    applyServletAmbiguousUriDecoding(environment.getApplicationContext());  // Layer 2 — ee10 servlet
    LOGGER.info("Configured Jetty ee10 servlet layer to decode ambiguous URIs for template names (ION-16032)");
}

static void applyServletAmbiguousUriDecoding(ServletContextHandler applicationContext) {
    applicationContext.getServletHandler().setDecodeAmbiguousURIs(true);
}
```

> Note vs. the original proposal above: the call is factored into `applyServletAmbiguousUriDecoding(...)` (testable, mirrors the existing `applyUriCompliance` pattern), and it is applied to the **application** context only — not the admin context. The connector half already covers admin connectors, and template endpoints live on the application context, so the admin servlet context deliberately keeps Jetty's default.

### Security Assessment

`setDecodeAmbiguousURIs(true)` tells the servlet layer to **decode** ambiguous URIs and pass them through to Jersey instead of rejecting them. **Crucially, it is a blanket switch** — it does *not* discriminate by violation type the way the connector `UriCompliance.with(AMBIGUOUS_PATH_SEPARATOR)` does. It tells the ee10 layer to decode *all* ambiguous URIs.

**Why that is still safe — the two fixes are coupled.** Jetty enforces the connector `UriCompliance` *first*, in the server core (`HttpChannelState$HandlerInvoker` → `ComplianceUtils.verify(...)`, which **throws → 400** for any violation the connector does not allow), *before* the ee10 servlet layer runs. Because `bookingUriCompliance()` allows **only** `AMBIGUOUS_PATH_SEPARATOR`, every other ambiguous violation (path segment, path encoding, path parameter, empty segment) is rejected at the connector before the servlet's blanket decode can act on it. So only an encoded path separator ever reaches the servlet layer.

**Consequence / guard-rail:** the connector compliance is now **load-bearing for security**, not just for the 400. Relaxing it (e.g. to `LEGACY`/`UNSAFE`) would let the servlet-layer blanket decode expose all the other ambiguous-URI tricks. This coupling is documented in the `applyServletAmbiguousUriDecoding` Javadoc and locked by a test (below).

**What remains protected:**
- Path traversal / ambiguous path segment (`%2e%2e`) — still rejected with **400 at the connector** (proven by test, not just asserted).
- Double-encoded paths (`%252F`), ambiguous path parameters, empty segments — still rejected at the connector.
- Other JAX-RS endpoints keep their default `[^/]+` regex, so a decoded `/` won't match their routes — 404 from Jersey (safe).
- Booking uses DynamoDB key lookups (not filesystem paths), so a decoded `/` in a template name is data, not a traversal vector.

### Tests Added

**File:** `booking/src/test/java/com/inttra/mercury/booking/BookingTemplateEncodedSlashServletLayerTest.java` — the in-container test that was missing. It stands up a **real Jetty 12 + ee10 servlet** server via `LocalConnector` (no new dependency — `jetty-server`/`jetty-ee10-servlet` are already on the classpath; deliberately avoids `dropwizard-testing`/`jersey-test-framework`), wired exactly as production:

1. `encodedSlashTemplateName_reachesServlet_withFullProductionConfig` — `%2F` reaches the servlet (**200**) with both halves applied. Red if **either** half of the production fix is reverted.
2. `encodedSlashTemplateName_rejectedWith400_whenServletLayerNotConfigured` — documents the QA failure: connector-only config still **400**s `%2F` at the servlet layer.
3. `ambiguousPathSegment_stillRejected_evenWithServletDecodingEnabled` — security guard: `%2e%2e` is **still 400** even with servlet decoding on, because the connector compliance rejects it first. Red if someone relaxes the connector compliance.

Full booking unit suite after the change: **2022 tests, 0 failures, 0 errors**.

---

## Testing Plan

### Local Verification (Before Push to QA)

1. **Apply the fix** on the existing branch
2. **Start the booking service locally:** `java -jar booking/target/booking-1.0.jar server booking/conf/int/config.yaml`
3. **Debug/verify with curl:**
   ```bash
   # Should return 200 (or appropriate response), NOT 400:
   curl -X OPTIONS "http://localhost:8080/booking/template/Test%2FName" -v
   
   # Actual GET with template name containing /:
   curl "http://localhost:8080/booking/template/Test%2FName" -v \
     -H "Cookie: SESSION_KEY=..." -H "Cookie: LOGIN_USER_ID=..."
   ```
4. **Verify the log message appears:** `"Configured Servlet layer to decode ambiguous URIs"`
5. **Run unit tests:** `mvn test -pl booking`
6. **Run full verify:** `mvn verify -pl booking`

### Add Test Coverage

Add to `BookingApplicationUriComplianceTest`:

```java
@Test
void configureUriCompliance_setsDecodeAmbiguousURIsOnServletHandler() {
    // Verify that the servlet handler is configured to decode ambiguous URIs
    // This tests the Layer 2 (Servlet) fix alongside the Layer 1 (connector) fix
    Environment environment = mock(Environment.class);
    MutableServletContextHandler appContext = mock(MutableServletContextHandler.class);
    ServletHandler servletHandler = mock(ServletHandler.class);
    when(environment.getApplicationContext()).thenReturn(appContext);
    when(appContext.getServletHandler()).thenReturn(servletHandler);
    
    // ... invoke configureUriCompliance ...
    
    verify(servletHandler).setDecodeAmbiguousURIs(true);
}
```

---

## References

- **Jetty GitHub Issue:** [#11298 — Error 400: Ambiguous URI Empty Segment](https://github.com/jetty/jetty.project/issues/11298)
- **Jetty Source:** `org.eclipse.jetty.ee10.servlet.ServletContextRequest` (lines ~195-208 in 12.0.x)
- **Jetty Source:** `org.eclipse.jetty.ee10.servlet.ServletHandler.isDecodeAmbiguousURIs()`
- **Dropwizard API:** `Environment.getApplicationContext().getServletHandler()`
- **Previous analysis:** [2026-06-16-booking-template-jetty-issue.md](2026-06-16-booking-template-jetty-issue.md)

---

## Timeline

| Time (ET) | Event |
|-----------|-------|
| 09:25 | ECS deployment triggered (task def rev 15) |
| 09:29 | Deployment completed, 2/2 tasks running with fix |
| 10:48 | QA tests `BK_Test%2F001` → 400 (OPTIONS) |
| 11:31 | QA tests `Arijit_test%2F001` → 400, `Arijittest%2F001` → 400 |
| 11:32 | QA tests `Arijit-test-001` (no /) → 200 ✅ |
| 11:52 | Investigation begins |
| 12:30 | Root cause identified: ee10 Servlet layer dual compliance |

---

## Claude Review

*Reviewer: Claude Opus 4.8 — 2026-06-17. Verified the Copilot Part-2 analysis against the actual artifacts on disk: `jetty-ee10-servlet-12.1.9.jar`, `jetty-server-12.1.9.jar`, `dropwizard-core-5.0.1.jar`, `dropwizard-jetty-5.0.1.jar`, the current `BookingApplication.java`, and `BookingApplicationUriComplianceTest.java`. Decompilation done with `javap -p -c`.*

### Verdict

**The Part-2 root cause is correct and the proposed fix is the right one.** I independently confirmed every load-bearing claim by bytecode inspection (not from memory). The encoded-slash 400 in QA is coming from a *second*, independent URI-compliance gate in the Jetty 12 ee10 servlet environment that our connector-level fix never touched.

### What I verified (and where the Copilot doc was slightly off)

| Claim | Verified? | Evidence |
|-------|-----------|----------|
| ee10 `ServletContextRequest` does an independent ambiguous-URI check | ✅ Yes | Bytecode: `HttpURI.hasViolations()` → `ServletHandler.isDecodeAmbiguousURIs()` → `UriCompliance.AMBIGUOUS_VIOLATIONS.contains(..)` → `new ServletApiRequest$AmbiguousURI` → 400 |
| `ServletHandler.setDecodeAmbiguousURIs(boolean)` exists in **12.1.9** (not just 12.1.5) | ✅ Yes | `javap` on `jetty-ee10-servlet-12.1.9.jar` shows both getter and setter |
| `Environment.getApplicationContext()` → `MutableServletContextHandler` → `getServletHandler()` chain compiles | ✅ Yes | `getApplicationContext()` returns `MutableServletContextHandler` (dropwizard 5.0.1); `getServletHandler()` is inherited from ee10 `ServletContextHandler` and returns `ServletHandler` |
| Connector-level `UriCompliance` (Layer 1) is *not* enforced and is therefore pointless | ❌ **Incorrect** | Layer 1 **is** enforced — see below |

**Correction to the Copilot doc (Step 5b).** The doc concluded the connector `UriCompliance` is never checked because `HttpParser` only knows `HttpCompliance`. That conclusion is wrong even though the `HttpParser` observation is right. In Jetty 12 the connector `UriCompliance` is enforced *later*, in the server core, not in the parser: `org.eclipse.jetty.server.internal.HttpChannelState$HandlerInvoker` calls `HttpConfiguration.getUriCompliance()` and runs `ComplianceUtils.verify(uriCompliance, httpURI, listener, …)` whenever `httpURI.hasViolations()`. So:

- **Layer 1 (connector / server core) is a real gate**, and yesterday's fix genuinely defused it. Had we *not* set connector `UriCompliance`, the request would have been rejected even earlier, in the core handler invoker.
- **Layer 2 (ee10 `ServletContextRequest`) is a separate gate** that consults `ServletHandler.isDecodeAmbiguousURIs()` — **not** the connector `UriCompliance` — and defaults to rejecting. This is why the connector fix passed Layer 1 but still died at Layer 2.

So both gates are real and both must be opened. The fix is additive, not a replacement — keep the existing `configureUriCompliance` connector wiring **and** add the servlet-handler line. The proposed `environment.getApplicationContext().getServletHandler().setDecodeAmbiguousURIs(true)` is correct and sufficient for Layer 2.

### Why did we miss this yesterday?

Three compounding reasons, in order of importance:

**1. We knowingly skipped the one test that would have caught it.** This is the honest answer. Yesterday's own Claude Critical Review raised **Finding 1 (🔴)** verbatim: *"the added tests give false confidence; the actual bug is untested … the reported failure is an HTTP 400 raised by Jetty before the request reaches Jersey,"* and recommended a real HTTP-level test (`DropwizardAppExtension`/`ResourceExtension`) issuing an actual `%2F` request through the container. The Resolution section then **declined** to add that harness — citing Jackson classpath destabilization risk and no in-module precedent — and substituted two *unit-level* tests:

- `BookingApplicationUriComplianceTest` → exercises the `UriCompliance` object + connector wiring → **Layer 1 only**.
- `TemplateResourceTest` routing test → feeds an already-decoded path into Jersey's `UriTemplate` matcher → **Layer 3 only**.

Neither test ever starts a Jetty container, so **Layer 2 was never on the test path**. By construction, both substitute tests pass with the real fix *and* would still pass against the residual bug — they are blind to the servlet-layer gate. The 🔴 finding's closing line ("Closing Finding 1 is what turns 'QA passed' into 'regression-proof'") predicted exactly this outcome: we shipped, QA failed, CI was silent.

**2. The mental model was "2 layers," and the real system has 3.** Yesterday's analysis modeled the request path as *Jetty connector → JAX-RS*. The actual Jetty-12-ee10 path is *connector/server-core → ee10 servlet environment → JAX-RS*, and the middle layer enforces ambiguous-URI policy through a **different knob** (`setDecodeAmbiguousURIs`) than the connector (`setUriCompliance`). This is a genuinely non-obvious Jetty 12 ee10 design: two separate APIs governing the same class of violation, one of which silently ignores the other. Without an end-to-end request we had no way to discover the third gate from the code we were looking at.

**3. The bug only manifests on the real wire, and our reproduction never used the wire.** The failing requests are `OPTIONS` CORS preflights with `%2F`, rejected in 0–7 ms with a 0-byte body — the signature of container-level rejection before the application. A direct method call or a `UriTemplate.match()` call cannot reproduce that; only bytes through a started server can. We validated the parts in isolation and never assembled them.

### Caution on the proposed test (don't repeat the mistake)

The "Add Test Coverage" snippet in this doc mocks `Environment`/`MutableServletContextHandler`/`ServletHandler` and asserts `verify(servletHandler).setDecodeAmbiguousURIs(true)`. That guards the *wiring* (good, add it) but it is the **same class of test that gave us false confidence yesterday** — it proves we *called the setter*, not that the container *stops returning 400*. If we ship on that alone, we're one Jetty-internal behavior change away from the identical surprise.

**Recommended: add one real in-container test that needs no `dropwizard-testing`.** Jetty ships `LocalConnector` (in `jetty-server`, already on the classpath). A test can stand up a tiny `Server` + ee10 `ServletContextHandler` with a trivial servlet, send a raw `OPTIONS /x/a%2Fb HTTP/1.1` through `LocalConnector`, and assert **400 without** `setDecodeAmbiguousURIs(true)` and **200/handled with** it. That reproduces the exact QA failure, proves both gates must be open, uses only Jetty libraries already present (no Jackson/`jersey-test-framework` risk — the reason cited for skipping the harness yesterday), and locks the regression out of CI. This is the test Finding 1 (🔴) was asking for, in a form that sidesteps the objection that blocked it.

### Process takeaway

When a review flags the *actual reported failure* as untested (🔴) and the mitigation substitutes tests at adjacent layers, treat "the real bug is still untested" as a release blocker — not a documentation nuance. The cost of the skipped end-to-end test was a second failed QA cycle and a second investigation. A ~30-line `LocalConnector` test would have caught it locally yesterday.

---

## End-to-End Verification and Steps in INT

*Performed 2026-06-17 by Claude Opus 4.8 on branch `defect/ION-16032-bk-template-issue-2`. The fix was run locally against the **real INT backend** (DynamoDB `inttra_int_booking`, auth via `api-alpha.inttra.com`) and a template whose name contains a forward slash was saved and read back successfully — the exact operation that returns HTTP 400 in QA.*

### Outcome (summary)

| Step | Request | Result |
|------|---------|--------|
| List templates (auth sanity) | `GET /booking/template` | **200** |
| **Save template with `/` in name** | `PUT /booking/template/Arijit%20ION-16032%20%2FHAPAG` | **200** — saved as `Arijit ION-16032 /HAPAG` |
| **Read it back (QA-failing op)** | `GET /booking/template/Arijit%20ION-16032%20%2FHAPAG` | **200** — full template, slash preserved |
| Appears in list | `GET /booking/template` | ✅ `Arijit ION-16032 /HAPAG` present |
| No token | `GET /booking/template` | **401** (reaches Jersey auth — NOT a 400) |
| Security: double-encoded slash | `GET /booking/template/a%252Fb` | **400** (still hard-blocked at connector) |
| Security: encoded dot segment | `GET /booking/template/%2e%2e/x` | **404** (normalized / not served — safe) |

Both ION-16032 config lines were logged at startup:

```
com.inttra.mercury.booking.BookingApplication: Configured Jetty UriCompliance to allow AMBIGUOUS_PATH_SEPARATOR for template names
com.inttra.mercury.booking.BookingApplication: Configured Jetty ee10 servlet layer to decode ambiguous URIs for template names (ION-16032)
```

### Prerequisites

- AWS SSO credentials for the INT account **081020446316** (`aws sts get-caller-identity` should return it). The INT config resolves `${awsps:/inttra/int/...}` from SSM and reads/writes DynamoDB in this account.
- A Bearer access token for an INT user with `BOOKING_ADMIN` scope (used below).

### Step 1 — Build the jar with the fix

```bash
mvn -pl booking package -DskipTests
# verify the fix is in the built jar:
unzip -p booking/target/booking-1.0.jar com/inttra/mercury/booking/BookingApplication.class \
  | javap -p -c -classpath /dev/stdin com.inttra.mercury.booking.BookingApplication 2>/dev/null \
  | grep -i "DecodeAmbiguous"        # -> setDecodeAmbiguousURIs:(Z)V
```

### Step 2 — Make a SAFE local config (disable the SQS listener)

The INT config defaults `appianWayConfig.listenerEnabled = true`. A local instance pointed at INT would otherwise **consume the shared `inttra_int_sqs_bk_inbound` queue**. Copy the config and disable the listener:

```bash
cp booking/conf/int/config.yaml booking/conf/int/config-local-test.yaml
# under appianWayConfig:, add:
#   listenerEnabled: false
```

> This file is a throwaway and was deleted after testing — recreate it if you re-run.

### Step 3 — Run the application locally

```bash
AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 \
  java -Xms256m -Xmx2048m -XX:+ExitOnOutOfMemoryError \
  -jar booking/target/booking-1.0.jar server booking/conf/int/config-local-test.yaml
# App connector: http://localhost:8080  (rootPath /booking)
# Admin:         http://localhost:8081/admin
```

Confirm it is up:

```bash
curl -s -o /dev/null -w "admin -> %{http_code}\n" http://localhost:8081/admin/healthcheck   # 200
```

### Step 4 — API calls (the actual verification)

The Bearer token used for this run (INT, user 100524, `BOOKING_ADMIN`, 30-min inactivity TTL):

```
8e09c21a-9267-4c24-95e9-2911ca5abcc2
```

> Tokens expire (TTL 1800s, inactivity timeout). Replace with a fresh one for a new run.

```bash
TOKEN="8e09c21a-9267-4c24-95e9-2911ca5abcc2"
BASE="http://localhost:8080/booking/template"

# 4a. List templates (auth sanity) -> 200
curl -s -w "\n[HTTP %{http_code}]\n" -H "Authorization: Bearer $TOKEN" "$BASE"

# 4b. Grab an existing template's full payload to clone
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/jerin-hazmat-testing" > src-template.json

# 4c. Build a SaveTemplateRequest body (carrierId, portOfDischargeLocationCode, data, formatVersion)
python - <<'PY'
import json
src = json.load(open("src-template.json"))
body = {"carrierId": src.get("carrierId"),
        "portOfDischargeLocationCode": src.get("portOfDischargeLocationCode"),
        "data": src.get("data"),
        "formatVersion": src.get("formatVersion") or "1"}
json.dump(body, open("put-body.json", "w"))
PY

# 4d. SAVE under a name containing '/'  (space -> %20, slash -> %2F) -> 200
#     name = "Arijit ION-16032 /HAPAG"  ->  Arijit%20ION-16032%20%2FHAPAG
curl -s -w "\n[HTTP %{http_code}]\n" -X PUT \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data-binary @put-body.json \
  "$BASE/Arijit%20ION-16032%20%2FHAPAG"

# 4e. READ IT BACK — this is the operation that returns 400 in QA -> now 200
curl -s -w "\n[HTTP %{http_code}]\n" \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/Arijit%20ION-16032%20%2FHAPAG"
```

### Step 5 — Security spot-checks (other ambiguous violations stay blocked)

```bash
# double-encoded slash -> 400 (AMBIGUOUS_PATH_ENCODING still enforced at the connector)
curl -s -o /dev/null -w "a%%252Fb -> %{http_code}\n" -H "Authorization: Bearer $TOKEN" "$BASE/a%252Fb"
# encoded dot segment -> 404 (normalized away / not served; not a traversal vector)
curl -s -o /dev/null -w "%%2e%%2e/x -> %{http_code}\n" -H "Authorization: Bearer $TOKEN" "$BASE/%2e%2e/x"
```

### Step 6 — Stop the server and clean up

```bash
# stop the process listening on 8080 (PowerShell):
#   Get-NetTCPConnection -LocalPort 8080 -State Listen | %% { Stop-Process -Id $_.OwningProcess -Force }
rm -f src-template.json put-body.json booking/conf/int/config-local-test.yaml
```

### Notes

- The test template `Arijit ION-16032 /HAPAG` was **intentionally left in INT** (company 1000) as evidence for QA. Delete via `DELETE /booking/template/Arijit%20ION-16032%20%2FHAPAG` when no longer needed.
- Only the production file (`BookingApplication.java`) and the test file (`BookingTemplateEncodedSlashServletLayerTest.java`) are committed; the `config-local-test.yaml`, the `*.json` scratch files, and this `docs/` file (gitignored) are **not** part of the change set.

---

## Part 3: The api-alpha Edge Gateway Blocks `%2F` (the app fix is necessary but not sufficient on that path)

*Discovered 2026-06-17 while verifying in INT. After saving the template `Arijit ION-16032 /HAPAG` to INT DynamoDB, opening it in the UI (which calls `https://api-alpha.inttra.e2open.com/booking/template/Arijit%20ION-16032%20%2FHAPAG`) returned **HTTP 404**, not the QA 400.*

### TL;DR

The 404 is **not** from the booking application. It comes from an **E2open edge / API gateway in front of the service** on the `api-alpha` host, which rejects the encoded slash (`%2F`) and returns its own HTML error page **before the request reaches Jetty**. Our ION-16032 fix lives inside the booking app, so on this path it never runs. The booking app itself already handles slash-named templates correctly — proven by the fact that the **literal-slash** form returns 200.

### Request path (more layers than we modeled)

```
Browser SPA (served from booking-alpha = CloudFront/S3)
      │  XHR: GET /booking/template/<name with %2F>
      ▼
┌──────────────────────────────────────────────┐
│ E2open API edge / gateway   (api-alpha)        │  Server: E2open
│  ── rejects %2F here → HTML 404 ──             │  ◄── the 404 you saw
└──────────────────────────────────────────────┘
      │ (never reached for %2F)
      ▼
   ALB → Booking ECS (Jetty + ee10 servlet + Jersey)  ◄── ION-16032 fix lives here
      │
      ▼
   DynamoDB  (template exists: "Arijit ION-16032 /HAPAG")
```

This is the same "wrong layer" trap as Parts 1–2, one tier higher: local verification (`localhost:8080`) and the QA container-log analysis both **bypass this edge**, so neither exercised it.

### Evidence (all via `api-alpha`, valid token, company 1000)

| Request | Status | Content-Type | Origin |
|---------|--------|--------------|--------|
| `GET /booking/template/jerin-hazmat-testing` (exists) | 200 | `application/json` | booking app ✅ |
| `GET /booking/template/NoSuchTemplate_ZZZ` (missing, no slash) | 404 | **`application/json`** — `{"code":"000200","message":"No such template…"}` | **booking app's** 404 |
| `GET /booking/template/Arijit%20ION-16032%20%2FHAPAG` (**`%2F`**) | 404 | **`text/html`**, `Server: E2open` | **edge gateway** |
| `GET /booking/template/Arijit%20ION-16032%20/HAPAG` (**literal `/`**) | **200** | `application/json` | booking app ✅ — **template opens** |

Two facts isolate the cause:
1. The booking app returns **JSON** 404s; the `%2F` request returned an **HTML** page with `Server: E2open` → it was answered by the edge, not the app.
2. Same template, same app — **literal `/` → 200**, **`%2F` → 404**. The *only* variable is encoded-vs-literal slash, so the edge is rejecting the encoded slash specifically. (This is the well-known reverse-proxy "encoded slash" rejection, e.g. Apache `AllowEncodedSlashes Off` default, nginx path normalization, ALB/CloudFront handling.)

`booking-alpha.inttra.e2open.com` was also checked: it is the **SPA static host** (CloudFront/S3, serves `index.html` for any path). The SPA's API calls go to `api-alpha`, so the E2open edge **is** on the real user path.

### Why QA showed 400 but INT/api-alpha shows 404

Different front doors. In QA (part 2) the `%2F` request **reached the booking container** and Jetty rejected it with 400 (seen in the container's access log). On the INT `api-alpha` path, the `%2F` request is stopped at the **E2open edge** with a 404 and never reaches the container. So the two environments expose the problem at different layers — and the app fix only addresses the container layer.

### Impact on this PR

- The ION-16032 app fix (connector `UriCompliance` + ee10 servlet `setDecodeAmbiguousURIs`) is **correct and required** for any path where `%2F` reaches the container (the QA 400). **Keep the PR.**
- It is **not sufficient** to make the UI open `/`-templates via `api-alpha`, because the edge blocks `%2F` upstream.

### Resolution options for the api-alpha path

1. **Infra (proper fix):** configure the E2open API edge to allow encoded slashes through without rejecting/decoding (e.g. Apache `AllowEncodedSlashes NoDecode`, nginx no path merge/decode, or ALB/CloudFront passthrough). Owner: platform/infra team.
2. **Frontend (quick, confirmed working):** send the **literal `/`** in the template-name path segment instead of `encodeURIComponent`'s `%2F`. The literal-slash form already returns 200 end-to-end through the edge and the app. Caveat: fragile if a name contains other characters that genuinely need percent-encoding.
3. **API design:** move the template name out of the URL path into a query parameter or request body for GET/PUT/DELETE (this is the "Option B" rejected in part 1 for API-compatibility reasons).

### Recommended next step

Confirm with the platform/infra team **whether the production booking UI's API calls traverse this same E2open edge**. If yes, the edge `%2F` rejection must be fixed (option 1) — or the frontend switched to a literal slash (option 2) — in addition to deploying this PR. The customer ticket (PDSUPPORT-203319) is only fully resolved when `%2F` is accepted end-to-end on the path real users take.

---

## Part 4: After Deploy to INT — the UI fails on the CORS preflight (`OPTIONS` `%2F` → 404 at the edge)

*2026-06-17, after the ION-16032 app fix was deployed to INT. Postman PUT/GET succeed, but the booking UI (`booking-alpha`) fails with a CORS error:*

```
Access to XMLHttpRequest at
'https://api-alpha.inttra.e2open.com/booking/template/ION-16032-Arijit-test%2F0001'
from origin 'https://booking-alpha.inttra.e2open.com' has been blocked by CORS policy:
Response to preflight request doesn't pass access control check: It does not have HTTP ok status.
```

### Root cause (confirmed by logs)

Same E2open edge as Part 3, now hit on the **CORS preflight**. The browser sends an `OPTIONS` preflight before the real GET/PUT; the edge **404s the `%2F` path**, and a 404 is not a 2xx, so the browser blocks the actual request.

The `%2F` requests **never reach the booking container** — the INT app log (`inttra-int-lg-bkapi`) shows only the literal-slash calls:

```
OPTIONS /booking/template/ION-16032-Arijit-test/0001 ... 200    (reached app)
GET     /booking/template/ION-16032-Arijit-test/0001 ... 401    (reached app, no token)
```

The `%2F` forms appear nowhere in the container log → blocked at the edge.

### Evidence table (via api-alpha)

| Request | Status | Origin | Reaches container? |
|---------|--------|--------|--------------------|
| `OPTIONS .../jerin-hazmat-testing` (no slash) | **200** + full `Access-Control-*` headers | edge | n/a (edge answers preflight) |
| `OPTIONS .../...test%2F0001` (`%2F`) | **404** `text/html` `Server: E2open` | **edge** | ❌ no |
| `OPTIONS .../...test/0001` (literal `/`) | **200** | edge→app | ✅ yes (log shows 200) |
| `GET .../...test%2F0001` (`%2F`) | **404** `text/html` | **edge** | ❌ no |
| `GET .../...test/0001` (literal `/`) | **401/200** `application/json` | app | ✅ yes (log shows 401) |

### Why Postman works but the browser doesn't

- **Postman** sends no CORS preflight and sends the slash in a form the edge accepts → reaches the app → works.
- **Browser** sends an `OPTIONS` preflight to the `encodeURIComponent` form (`%2F`) → edge 404 → CORS block. The browser never even sends the real GET/PUT.

### Fix options

**Option 1 — Booking UI change (fastest, unblocks now).** Send the template name with a **literal `/`** instead of `%2F`. Wherever the UI builds the path with `encodeURIComponent(name)` (which yields `%2F`), encode everything except the slash:

```js
// before:  `/booking/template/${encodeURIComponent(name)}`            // -> %2F (edge 404)
// after:   `/booking/template/${encodeURIComponent(name).replace(/%2F/gi, '/')}`   // -> literal / (works)
```

Confirmed end-to-end against the deployed INT backend: literal-slash `OPTIONS` → 200 and `GET`/`PUT` → 200. This path is served by the `@Path("/{name: .+}")` route and does **not** depend on the `%2F` servlet fix. Apply the change to all four template calls (list is unaffected; GET, PUT, DELETE carry the name).

**Option 2 — Infra change (proper long-term fix).** Configure the E2open edge to allow encoded slashes (`AllowEncodedSlashes NoDecode` / passthrough). Then standard `encodeURIComponent` (`%2F`) works, and the deployed ION-16032 connector+servlet fix is what makes the container accept it.

### Recommendation

Do **Option 1** to unblock the UI/customer immediately, and raise **Option 2** with the platform/infra team so the API accepts standard-encoded slashes for any client. The deployed app fix (this PR) remains correct and is required for the `%2F` path once the edge passes it.

---

## Post-Deploy Verification — QA and INT (2026-06-17)

### Deployment Confirmation

| Environment | Cluster | Service | Task Def | Deployed At (ET) | Rollout |
|-------------|---------|---------|----------|-------------------|---------|
| **QA** | `ANEQABK-001` | `Booking-qa` | `Booking-latest-qa-Task:15` | 2026-06-17 09:25 | ✅ COMPLETED |
| **INT** | `ANEINWEBSVC-001` | `Booking-dev` | `Booking-latest-dev-Task:11` | 2026-06-17 14:54 | ✅ COMPLETED |

Both environments show the two expected log messages at container startup:

```
INFO  com.inttra.mercury.booking.BookingApplication: Configured Jetty UriCompliance to allow AMBIGUOUS_PATH_SEPARATOR for template names
INFO  com.inttra.mercury.booking.BookingApplication: Configured Jetty ee10 servlet layer to decode ambiguous URIs for template names (ION-16032)
```

And both show `{name: .+}` in the Dropwizard route listing:
```
DELETE  /booking/template/{name: .+}
GET     /booking/template/{name: .+}
PUT     /booking/template/{name: .+}
```

---

### QA Verification — PASSED ✅

**Host:** `api-beta.inttra.e2open.com`  
**UI:** `booking-beta.inttra.e2open.com`

#### Before the fix (earlier today, only connector-level `UriCompliance` deployed):

| Time (UTC) | Request | Result | Explanation |
|------------|---------|--------|-------------|
| 14:48:50 | `OPTIONS /booking/template/BK_Test%2F001` | **400** (0 bytes) | ee10 Servlet layer rejected — `ServletHandler.isDecodeAmbiguousURIs()` was `false` |
| 14:49:20 | `OPTIONS /booking/template/BK_Test%2F001` | **400** (0 bytes) | Same — retry |
| 15:31:16 | `OPTIONS /booking/template/Arijit_test%2F001` | **400** (0 bytes) | Same |
| 15:31:55 | `OPTIONS /booking/template/Arijittest%2F001` | **400** (0 bytes) | Same |
| 15:32:11 | `OPTIONS /booking/template/Arijit-test-001` (no `/`) | **200** (31 bytes) | No `%2F` → no violation → works |

Key observation: requests with `%2F` **reached the booking service** (appeared in the access log) but were rejected at the Servlet layer with 400 and empty body. Requests without `%2F` worked fine.

#### After the full fix (both `UriCompliance` + `setDecodeAmbiguousURIs`):

| Time (UTC) | Request | Result | Explanation |
|------------|---------|--------|-------------|
| 19:56:51 | `OPTIONS /booking/template/Arijit-test-ION-16032%2F001` | **200** (31 bytes, 9ms) | ✅ Preflight passes — Servlet layer allows ambiguous URI |
| 19:56:51 | `PUT /booking/template/Arijit-test-ION-16032%2F001` | **200** (437 bytes, 303ms) | ✅ Template saved via browser (CORS flow) |
| 19:53:45 | `PUT /booking/template/Arijit-test-001/002` | **200** (375 bytes, 261ms) | ✅ Template with literal `/` saved via Postman |
| 19:54:40 | `GET /booking/template/Arijit-test-001/002` | **200** (2327 bytes, 409ms) | ✅ Template with literal `/` retrieved via Postman |
| 19:54:31 | `GET /booking/template/Arijit%20ION-16032%20/HAPAG` | **200** | ✅ Template with space + slash retrieved |

**Both Postman (direct API) and Browser (CORS preflight → PUT) work correctly.**

The key difference in the access log — the `OPTIONS` request now reaches Jersey and gets a proper `200` response with CORS headers:
```
Before: "OPTIONS /booking/template/BK_Test%2F001 HTTP/1.1" 400 0  ← Servlet layer 400, empty body
After:  "OPTIONS /booking/template/Arijit-test-ION-16032%2F001 HTTP/1.1" 200 31  ← Jersey handles it
```

---

### INT Verification — Application Fix Deployed, Upstream Proxy Blocks `%2F`

**Host:** `api-alpha.inttra.e2open.com`  
**UI:** `booking-alpha.inttra.e2open.com`

#### What works:

- Container started with both fix log messages ✅
- Routes show `{name: .+}` ✅
- Regular template operations work (no `/` in name):
  ```
  GET /booking/template/Tmeplate%201.01    → 200 (3472 bytes)
  GET /booking/template/only_alpha_anan    → 200 (1455 bytes)
  GET /booking/template                    → 200 (574 bytes, list)
  ```

#### What fails:

- `PUT /booking/template/ION-16032-Arijit-test%2F0001` → **404** (from upstream, never reaches booking service)
- `OPTIONS /booking/template/ION-16032-Arijit-test%2F0001` → **404** (from upstream)

#### Proof the request never reaches the booking service:

Searched CloudWatch logs (`inttra-int-lg-bkapi`) for:
- `"HAPAG"` → no results
- `"%2F"` in template path → no results  
- `"2F"` → no results
- `"ION-16032"` in request context → no results

Meanwhile, non-`%2F` requests to the SAME host DO appear in the logs (confirming the service is healthy and reachable).

#### Root cause in INT:

The `api-alpha.inttra.e2open.com` endpoint has an **upstream reverse proxy** (not present in QA's `api-beta` path) that:
1. Receives the request with `%2F` in the URL path
2. Either decodes `%2F` → `/` (causing path routing to fail) or rejects it outright
3. Returns **404** before the request ever reaches the booking ECS container

Evidence:
- The 404 response includes a `Content-Security-Policy` header that the booking service (Dropwizard/Jetty) does NOT set — confirming the 404 originates from the proxy layer
- The browser console shows: *"Response to preflight request doesn't pass access control check: It does not have HTTP ok status"* — because the proxy's 404 lacks CORS headers

---

### Comparison: Why QA Works but INT Doesn't

```
QA request flow (WORKS):
  Browser → api-beta.inttra.e2open.com → ALB-QA-APPWAY-WS → Booking ECS
                                          (forwards %2F intact)

INT request flow (FAILS):
  Browser → api-alpha.inttra.e2open.com → [PROXY/GATEWAY] → ALB → Booking ECS
                                           ↑
                                           Returns 404 for %2F
                                           (request never reaches booking)
```

The QA path (`api-beta.inttra.e2open.com`) routes **directly through the ALB** to the booking service. The ALB passes `%2F` through without modification.

The INT path (`api-alpha.inttra.e2open.com`) has an **additional proxy/gateway layer** that does not forward requests with `%2F` in the URL path. This is an infrastructure configuration difference unrelated to the application fix.

---

### Conclusion

| Question | Answer |
|----------|--------|
| Is the application fix correct? | ✅ **Yes** — verified working in QA (both Postman and browser) |
| Does the fix handle `OPTIONS` preflight? | ✅ **Yes** — `OPTIONS` now returns 200 with CORS headers |
| Does the fix handle `PUT` (save template)? | ✅ **Yes** — `PUT` with `%2F` returns 200, template persisted |
| Does the fix handle `GET` (load template)? | ✅ **Yes** — `GET` with literal `/` returns the template |
| Why doesn't INT work? | **Upstream proxy** at `api-alpha.inttra.e2open.com` blocks `%2F` — not an application issue |
| Is INT fix deployed? | ✅ **Yes** — both log messages present, would work if requests reached the service |
| Action needed for INT? | Configure the INT proxy to allow `%2F` passthrough (same as QA) |
| Will PROD work? | Depends on whether PROD's `api.inttra.e2open.com` uses the same proxy as INT or same direct-ALB path as QA — needs verification |

---

## Part 5: QA Infrastructure Trace — What Is Actually In Front of the Booking Cluster (and why QA works but INT/UI did not)

*2026-06-17. Traced with read-only AWS CLI using profile `642960533737_INTTRA2-QATeam`, region `us-east-1`. ECS cluster `ANEQABK-001`, service `Booking-qa`, app log group `inttra2-qa-lg-bkapi`. No DynamoDB access.*

### QA request topology (verified)

```
                 ┌─ booking-beta.inttra.com  ──► CloudFront ELSVHPDXA4BQ2 ──► S3 (static SPA)
 Browser (SPA) ──┤
                 └─ api-beta.inttra(.e2open).com ──► WAF ──► ALB ──► ECS Booking-qa (Jetty)
                                                                       :8080  /booking/*

 (separately) beta.inttra.e2open.com / beta.inttra.com ──► CloudFront E2IOQPHIQRDPXV / E74GV8B5G76O3
                                                            ──► alb-qa-ptui-ecs  (PTUI ECS, NOT booking)
```

**ECS service → target groups → ALBs** (`aws ecs describe-services`, `aws elbv2 describe-target-groups`):

| Target group | ALB | Scheme | Listener | Booking rule |
|---|---|---|---|---|
| `INTTRA2-TG-QA-BKAPI` | `ALB-QA-APPWAY-WS` (legacy INTTRA) | internet-facing | HTTPS:443 | `/booking/*` → TG (prio 26) |
| `tg-qa-bkapi-e2open` | `alb-qa-api-e2open` (E2open) | internet-facing | HTTPS:443 | `/booking/*` → TG (prio 26) |

Both target groups point at the **same** containers (`Booking-qa-Container:8080`, health `/booking/services/ping`), desired/running 2/2, task def `Booking-latest-qa-Task:15`.

**WAF** (`aws wafv2 get-web-acl-for-resource` / `get-web-acl`): both ALBs are associated with **`WACLv2-ALB-QA-US-EAST-1`** (default *Allow*). Managed/custom rule groups: `AWSManagedRulesAmazonIpReputationList`, two custom `Block-Malicious-IP-Addresses-RG-*`, `AWSManagedRulesSQLiRuleSet`, `AWSManagedRulesKnownBadInputsRuleSet`, `AWSManagedRulesCommonRuleSet` (OWASP). WAF rejects with **403** — not the 400/404 in question.

**CloudFront** (`aws cloudfront list-distributions`): **no distribution fronts the booking API.** Distributions with an ALB origin front only the **PTUI/UI** ECS: `beta.inttra.e2open.com` + `beta.inttra.com` → `alb-qa-ptui-ecs` (ids `E2IOQPHIQRDPXV`, `E74GV8B5G76O3`). The booking SPA host `booking-beta.inttra.com` is **CloudFront → S3** (`ELSVHPDXA4BQ2`). The booking **API** is reached directly through `api-beta.inttra.com` / `api-beta.inttra.e2open.com` → WAF/ALB → ECS. So in QA, **ALB (not CloudFront) is the component directly in front of the booking cluster**, with WAF attached.

### Do we concur with the Copilot QA findings (Part 2, Step 4)?

**Yes — every documented QA fact is confirmed:**
- Target groups `INTTRA2-TG-QA-BKAPI` (on `ALB-QA-APPWAY-WS`), `tg-qa-bkapi-e2open`, and the UI `…-ptui-…` on `alb-qa-ptui-ecs`. ✓
- CloudFront `E2IOQPHIQRDPXV` (`beta.inttra.e2open.com`) → origin `alb-qa-ptui-ecs`. ✓
- WAF `WACLv2-ALB-QA-US-EAST-1` with OWASP `CommonRuleSet`; WAF = 403, not 400. ✓
- **Conclusion that the QA 400 came from Jetty in the container** — ✓ confirmed: the historical 400 preflights are in the container's own access log:
  ```
  OPTIONS /booking/template/BK_Test%2F001   HTTP/1.1  400 0  referer https://booking-beta.inttra.e2open.com/  (14:48 UTC)
  OPTIONS /booking/template/Arijit_test%2F001 HTTP/1.1 400 0  referer https://booking-beta.inttra.e2open.com/  (15:31 UTC)
  ```
  `%2F` reached the container and Jetty rejected it (the Part-2 bug).

**One addition (gap, not error):** the Copilot investigation inventoried CloudFront / WAF / ALB / container but **not the `api-*` reverse-proxy tier**. In QA that tier does **not** block `%2F`, so a QA-only investigation could not surface it. In INT the equivalent tier (`api-alpha.inttra.e2open.com`, `Server: E2open`) is precisely what 404s `%2F` (Parts 3–4). This omission is *why* the app fix turned QA green yet left the INT UI failing.

### The decisive QA vs INT difference (the `api-*` edge)

Same probe, two environments:

| Probe | QA `api-beta.inttra.e2open.com` | INT `api-alpha.inttra.e2open.com` |
|---|---|---|
| `OPTIONS …/x%2Fy` (preflight) | **200** + full `Access-Control-Allow-Methods/Max-Age`; **no** `Server` proxy header | **404** `text/html`, **`Server: E2open`**, partial CORS only |
| `GET …/x%2Fy` (no token) | **401** (reaches app auth) | **404** (edge HTML) |
| Reaches container? (access log) | **yes — encoded** `GET …/testION16032%2Fslash` 401 / `OPTIONS …%2Fslash` 200 | **no** (never in container log) |

So:
- **QA:** the `api-beta` edge passes `%2F` through (encoded) to WAF→ALB→container. The container now has the servlet-layer fix, so `OPTIONS %2F → 200` (with CORS) and `GET %2F → 401/200`. **QA works end-to-end.**
- **INT:** an **E2open reverse proxy** (`Server: E2open`, Apache-style `AllowEncodedSlashes Off` behavior) sits on `api-alpha` and **404s `%2F`** before WAF/ALB/container. The deployed app fix never runs on that path → the browser's CORS preflight fails.

### Current QA state

QA is **no longer failing**: the historical `%2F → 400`s were 14:48–15:31 UTC today; after the servlet-layer fix was deployed to QA, the same probe now returns `OPTIONS 200` / `GET 401` with `%2F` arriving encoded at the container. The fix in this PR is confirmed working on the QA path.

### Implication

The QA path (`api-beta` → ALB → ECS) is the path the app fix addresses, and it works. The INT/customer path (`api-alpha` E2open proxy) needs the edge to allow `%2F` (Option 2 in Part 4) **or** the UI to send a literal `/` (Option 1). Confirm whether production users traverse an `api-*` E2open proxy like INT's; if so, the edge change is required in addition to this PR.

### Read-only commands used

```bash
export AWS_PROFILE=642960533737_INTTRA2-QATeam AWS_REGION=us-east-1
aws ecs list-services --cluster ANEQABK-001
aws ecs describe-services --cluster ANEQABK-001 --services Booking-qa --query "services[0].loadBalancers"
aws elbv2 describe-target-groups --names INTTRA2-TG-QA-BKAPI tg-qa-bkapi-e2open
aws elbv2 describe-load-balancers --names ALB-QA-APPWAY-WS alb-qa-api-e2open
aws elbv2 describe-listeners --load-balancer-arn <alb-arn>
aws elbv2 describe-rules --listener-arn <listener-arn>
aws wafv2 get-web-acl-for-resource --resource-arn <alb-arn>
aws wafv2 get-web-acl --name WACLv2-ALB-QA-US-EAST-1 --scope REGIONAL --id 7a2ce0e6-60f5-479a-98ba-2a311afcb695
aws cloudfront list-distributions
aws logs filter-log-events --log-group-name inttra2-qa-lg-bkapi --filter-pattern '"OPTIONS" "2F" "400"'
```

---

## Part 6: PR Description Blurb (for reviewers and infra)

> **ION-16032 — Booking templates with `/` in the name return HTTP 400 (Jetty 12 ee10 servlet layer)**
>
> **What & why.** After the Jetty 11→12 upgrade, `GET/PUT/DELETE /booking/template/{name}` returns **HTTP 400** when the name contains an encoded slash (`%2F`). Jetty 12 enforces ambiguous-URI policy in **two independent places**: the connector-level `UriCompliance` (fixed earlier) **and** the ee10 servlet layer (`ServletContextRequest`), which has its own check controlled by `ServletHandler.setDecodeAmbiguousURIs(...)`. Only the first was configured, so `%2F` was still rejected at the servlet layer before reaching Jersey.
>
> **Change (2 files).** `BookingApplication.configureUriCompliance` now also calls a new package-private `applyServletAmbiguousUriDecoding(environment.getApplicationContext())` → `setDecodeAmbiguousURIs(true)`. New in-container test `BookingTemplateEncodedSlashServletLayerTest` stands up a real Jetty 12 + ee10 servlet via `LocalConnector` (no new dependency) and asserts: `%2F` reaches the servlet (200) with the full fix, 400 without the servlet half, and a path-segment attack (`%2e%2e`) is **still** 400. Full booking suite: 2022 tests, 0 failures.
>
> **Security.** `setDecodeAmbiguousURIs(true)` is a blanket switch; its safety relies on the connector `UriCompliance` (allows **only** `AMBIGUOUS_PATH_SEPARATOR`) still rejecting every other ambiguous violation first. Do **not** loosen the connector compliance without revisiting this. Verified in INT: double-encoded `%252F` still returns 400.
>
> **Verified.** Locally against the INT backend: save + read-back of a `/`-named template returns 200. QA confirmed: `%2F` now flows end-to-end (was 400 earlier today).
>
> **⚠️ Infra note (action needed beyond this PR).** This fixes the **booking application**. On the **INT customer path** (`api-alpha.inttra.e2open.com`), an upstream **e2proxy** edge (Kubernetes reverse proxy, `Server: E2open`) **rejects `%2F` with a 404** *before* the request reaches the app — so the browser's CORS preflight fails and the UI cannot open `/`-templates even with this PR deployed. **QA does not have this blocking edge, which is why QA works.** Resolution requires **either** the edge to allow encoded slashes (`AllowEncodedSlashes`/passthrough) **or** the booking UI to send a literal `/` instead of `%2F` (confirmed working). See Parts 3–5.

---

## Part 7: Network Topology in Plain English (with diagram and glossary)

### The idea in one sentence

When you click "open template" in the browser, your request passes through **several gatekeepers** before it reaches the booking program — and any one of them can say "no" before the booking code ever runs.

### The layers, as a simple analogy

Think of visiting someone in a **secure office building**:

1. **DNS** = the *address book*. You look up `api-alpha.inttra.e2open.com` and get a street address (an IP).
2. **Edge / reverse proxy** (e.g. the "e2proxy", `Server: E2open`) = the *building's front gate* / first guard. It can turn you away before you even enter — this is the gate that rejects `%2F` in INT.
3. **CDN / CloudFront** = a *photocopy desk in the lobby* for things that don't change (the website's HTML, JS, images). Serves them fast from cache. It only handles the **static UI**, not the booking API.
4. **WAF** = the *security scanner / metal detector*. Looks for attacks (SQL injection, known-bad inputs, bad IPs). If it sees an attack it stops you with a **403**.
5. **ALB (load balancer)** = the *receptionist* who decides which office (which copy of the program) gets your request, matching the path (`/booking/*`) to the right team.
6. **Target group** = the *receptionist's list* of which specific desks (containers) are open and healthy.
7. **ECS container running the booking app (Jetty)** = the *actual office* where your request is finally handled. **Our fix lives here.**
8. **DynamoDB** = the *filing cabinet* the office reads/writes.

The `%2F` (encoded slash) problem: **different gatekeepers have different rules about it.** Our fix taught the *office* (step 7) to accept it — but in INT the *front gate* (step 2) rejects it first, so the office never sees it.

### Diagram

```
  YOU (browser, booking SPA)
        |
        |  https://api-...  GET /booking/template/Name%2FCarrier
        v
  +---------------+
  | DNS           |  name  ->  IP address
  +---------------+
        |
        v
  +----------------------------------------------------------------+
  | EDGE / reverse proxy  ("e2proxy", Server: E2open)              |
  |   - first gatekeeper, public front door                        |
  |   - INT: REJECTS %2F  -> 404 (request stops here)  <---------- the INT bug
  |   - QA : no such blocking edge -> passes %2F through           |
  +----------------------------------------------------------------+
        |
        v
  +---------------+     (CloudFront/CDN is a SEPARATE branch, only for the
  | WAF           |      static website files: booking-beta -> S3. Not the API.)
  |  attack scan  |  -> blocks attacks with 403
  +---------------+
        |
        v
  +---------------+
  | ALB           |  matches /booking/*  ->  booking target group
  | load balancer |
  +---------------+
        |
        v
  +---------------+
  | Target group  |  -> a healthy booking container
  +---------------+
        |
        v
  +----------------------------------------------+
  | ECS container: Booking app (Jetty 12)        |
  |   Layer A: connector UriCompliance           |  <-- ION-16032 fix (both layers)
  |   Layer B: ee10 servlet decodeAmbiguousURIs  |
  |   Layer C: Jersey route {name: .+}           |
  +----------------------------------------------+
        |
        v
  +---------------+
  | DynamoDB      |  template stored/read
  +---------------+
```

### Why QA works but the INT UI did not (one line)

**QA has no `%2F`-blocking edge, so the request reaches the fixed app → works. INT has the e2proxy edge that 404s `%2F`, so the request dies before reaching the fixed app.**

### Glossary (use these to explain to others)

| Term | What it is | In our story |
|------|-----------|--------------|
| **DNS** | Domain Name System — translates a hostname (`api-alpha…`) into an IP address. | Tells the browser where to send the request. |
| **Edge / reverse proxy** | A server that sits *in front of* your real servers and forwards requests to them. "Reverse" because it proxies for the *server*, not the client. Often does TLS, routing, auth, basic filtering. | The **e2proxy** (`Server: E2open`) on `api-alpha`. Rejects `%2F` in INT. |
| **CDN / CloudFront** | Content Delivery Network — caches *static* files (HTML/JS/images) near users for speed. AWS's CDN is **CloudFront**. | Serves the booking **website** (`booking-beta` → S3). **Not** the booking API. |
| **WAF** | Web Application Firewall — inspects HTTP requests for attack patterns (SQLi, XSS, bad IPs) and blocks them, usually with **403**. AWS's is **AWS WAF**; rule bundles are "managed rule groups" (e.g. OWASP `CommonRuleSet`). | `WACLv2-ALB-QA-US-EAST-1` on the QA ALBs. Not the cause here (would be 403). |
| **ALB** | Application Load Balancer — an AWS layer-7 (HTTP) load balancer. Accepts requests and forwards them to healthy backends; can route by host/path (`/booking/* → booking`). | `ALB-QA-APPWAY-WS`, `alb-qa-api-e2open` (QA); `alb-int-api-inttra-internal` (INT). |
| **Listener** | The port+protocol an ALB listens on (e.g. HTTPS:443), with **rules** deciding where each request goes. | All booking listeners are HTTPS:443 with a `/booking/*` rule. |
| **Target group** | The list of backend targets (containers/IPs+port) an ALB forwards to, plus a **health check**. | `INTTRA2-TG-QA-BKAPI`, `tg-qa-bkapi-e2open`, `tg-int-bkapi-inttra` (all :8080, health `/booking/services/ping`). |
| **ECS** | Elastic Container Service — runs Docker **containers**. A **cluster** holds **services**; a service runs N **tasks** of a **task definition**. | Cluster `ANEQABK-001`, service `Booking-qa`, task def `Booking-latest-qa-Task:15`. |
| **EKS / "k8s"** | Elastic Kubernetes Service — AWS-managed Kubernetes, another way to run containers. | The **e2proxy** edge runs on EKS (its ALB's NIC has `k8s-e2proxy-…` security groups). |
| **EIP / ENI** | Elastic IP (fixed public IP) / Elastic Network Interface (virtual NIC). Following EIP→ENI tells you what a public IP really points to. | How we found `api-alpha`'s IP belongs to ALB `alb-e2proxy` (the edge). |
| **`%2F`** | URL-encoding of `/`. `encodeURIComponent` turns `/` into `%2F`. Many proxies treat `%2F` specially (reject/normalize) for security. | The whole bug: who accepts `%2F` and who rejects it. |
| **CORS preflight (`OPTIONS`)** | Before a cross-site browser request, the browser first sends an `OPTIONS` "may I?". If that isn't a 2xx with the right `Access-Control-*` headers, the browser **blocks** the real request. | The INT edge returns **404** to the preflight `%2F` → browser blocks → the CORS error you saw. |

### INT vs QA, mapped to the diagram

| Layer | QA | INT |
|-------|----|----|
| Edge / reverse proxy | none that blocks `%2F` (request passes) | **e2proxy** (`alb-e2proxy` → EKS, `Server: E2open`) **404s `%2F`** |
| WAF | `WACLv2-ALB-QA-US-EAST-1` (OWASP etc.) | not visible to my role (see Part 8) |
| ALB | `ALB-QA-APPWAY-WS` + `alb-qa-api-e2open` (internet-facing) | `alb-int-api-inttra-internal` (**internal**, behind the edge) |
| Target group | `INTTRA2-TG-QA-BKAPI`, `tg-qa-bkapi-e2open` | `tg-int-bkapi-inttra` |
| App (fix) | deployed, works | deployed, works — but unreachable via `%2F` due to the edge |

---

## Part 8: Reusable Investigation Queries (read-only) + INT Access Notes

*All read-only. Set the profile/region first. No DynamoDB table scans were used anywhere in this investigation.*

```bash
# QA:
export AWS_PROFILE=642960533737_INTTRA2-QATeam AWS_REGION=us-east-1
# INT:
export AWS_PROFILE=081020446316_INTTRA-Dev-Engg AWS_REGION=us-east-1
```

### A. Find what runs and where (ECS)

```bash
# Purpose: list services in a cluster (find the booking service).
aws ecs list-services --cluster ANEQABK-001

# Purpose: see which target groups a service is wired to (the link from app -> ALB).
aws ecs describe-services --cluster ANEQABK-001 --services Booking-qa \
  --query "services[0].{loadBalancers:loadBalancers,running:runningCount,taskDef:taskDefinition}"

# Purpose: list all clusters (find the env's booking cluster by naming, e.g. *BK*).
aws ecs list-clusters --query "clusterArns" --output text | tr '\t' '\n'
```

### B. Trace the load balancer chain (ELB / ALB)

```bash
# Purpose: a target group tells you protocol/port, health check, AND which ALB(s) it attaches to.
aws elbv2 describe-target-groups --names INTTRA2-TG-QA-BKAPI tg-qa-bkapi-e2open \
  --query "TargetGroups[].{TG:TargetGroupName,Port:Port,Health:HealthCheckPath,LBs:LoadBalancerArns}"

# Purpose: ALB basics — internet-facing vs internal, and its DNS name.
aws elbv2 describe-load-balancers --names ALB-QA-APPWAY-WS alb-qa-api-e2open \
  --query "LoadBalancers[].{Name:LoadBalancerName,DNS:DNSName,Scheme:Scheme}"

# Purpose: which ports/protocols the ALB listens on.
aws elbv2 describe-listeners --load-balancer-arn <alb-arn> \
  --query "Listeners[].{Port:Port,Proto:Protocol,SSL:SslPolicy}"

# Purpose: routing rules — which host/path goes to which target group (find the /booking/* rule).
aws elbv2 describe-rules --listener-arn <listener-arn> \
  --query "Rules[?contains(to_string(Conditions),'booking')].{Prio:Priority,Cond:Conditions[].Values,TG:Actions[?Type=='forward']|[0].TargetGroupArn}"
```

### C. Web Application Firewall (WAF)

```bash
# Purpose: is a WAF attached to this ALB, and which one.
aws wafv2 get-web-acl-for-resource --resource-arn <alb-arn> --query "WebACL.{Name:Name,Id:Id}"

# Purpose: what rules the WAF enforces (managed rule groups, default action). WAF blocks = 403.
aws wafv2 get-web-acl --name WACLv2-ALB-QA-US-EAST-1 --scope REGIONAL --id <web-acl-id> \
  --query "WebACL.{Default:DefaultAction,Rules:Rules[].{Name:Name,Managed:Statement.ManagedRuleGroupStatement.Name}}"
```

### D. CDN (CloudFront)

```bash
# Purpose: all distributions, their aliases (hostnames) and origins (what they front).
aws cloudfront list-distributions \
  --query "DistributionList.Items[].{Id:Id,Aliases:Aliases.Items,Origins:Origins.Items[].DomainName}"

# Purpose: only distributions that front an ALB (API/dynamic, not S3 static).
aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(to_string(Origins.Items[].DomainName),'elb.amazonaws.com')].{Id:Id,Aliases:Aliases.Items,Origins:Origins.Items[].DomainName}"
```

### E. Identify a mystery public hostname / edge (DNS -> EIP -> ENI -> resource)

```bash
# Purpose: resolve the hostname to an IP.
python -c "import socket;print(socket.gethostbyname('api-alpha.inttra.e2open.com'))"

# Purpose: is that IP an Elastic IP in this account, and on which ENI?
aws ec2 describe-addresses --query "Addresses[?PublicIp=='<ip>'].{IP:PublicIp,Instance:InstanceId,ENI:NetworkInterfaceId}"

# Purpose: what does that ENI belong to? Description reveals e.g. 'ELB app/alb-e2proxy/...';
#          security-group names like 'k8s-e2proxy-...' reveal it runs on EKS/Kubernetes.
aws ec2 describe-network-interfaces --network-interface-ids <eni-id> \
  --query "NetworkInterfaces[0].{Desc:Description,Instance:Attachment.InstanceId,PrivateIp:PrivateIpAddress,Group:Groups[].GroupName}"
```

### F. Read the access/app logs (CloudWatch Logs) — proves WHICH layer answered

```bash
# Purpose: did a request reach the booking container, and with the slash encoded or decoded?
#          (If it's in this log group, it reached the app. %2F vs / shows whether an edge decoded it.)
NOW=$(python -c "print(int(__import__('time').time()*1000))"); START=$((NOW-900000))
aws logs filter-log-events --log-group-name inttra2-qa-lg-bkapi \
  --start-time $START --filter-pattern '"testION16032"' --query "events[*].message" --output text

# Purpose: find historical %2F 400s (the original bug evidence).
aws logs filter-log-events --log-group-name inttra2-qa-lg-bkapi \
  --start-time $START --filter-pattern '"OPTIONS" "2F" "400"' --query "events[*].message" --output text
```

### G. Black-box probes from outside (curl) — tell edge vs app apart

```bash
# Purpose: CORS preflight as the browser sends it. A 2xx = ok; a 404 here breaks the UI.
curl -s -i -X OPTIONS \
  -H "Origin: https://booking-alpha.inttra.e2open.com" \
  -H "Access-Control-Request-Method: GET" \
  "https://api-alpha.inttra.e2open.com/booking/template/Name%2FCarrier"

# Purpose: compare encoded %2F vs literal / . If %2F fails but / works, the slash encoding is the issue.
curl -s -o /dev/null -w "%{http_code}\n" "https://<host>/booking/template/Name%2FCarrier"   # encoded
curl -s -o /dev/null -w "%{http_code}\n" "https://<host>/booking/template/Name/Carrier"      # literal

# How to read the response:
#   Server: E2open + text/html 404      -> the EDGE answered (request did NOT reach the app)
#   application/json {"code":...}        -> the BOOKING APP answered (request reached Jersey)
#   401                                  -> reached the app, auth required (so the URL itself is fine)
```

### INT access notes (what this SSO role can and cannot do)

Role: `AWSReservedSSO_INTTRA-Dev-Engg` in account `081020446316`.

| Action | INT access | Note |
|--------|-----------|------|
| `sts get-caller-identity` | YES | |
| `ecs list-clusters` / `list-services` / `describe-*` | YES | No `*BK*` cluster visible by name; booking targets live under `tg-int-bkapi-inttra`. |
| `elbv2 describe-target-groups` | YES | Found `tg-int-bkapi-inttra` → ALB `alb-int-api-inttra-internal` (**internal** ALB). |
| `elbv2 describe-load-balancers` / `describe-listeners` / `describe-rules` | NO — **AccessDenied** | Cannot read ALB scheme/listeners/rules in INT — the main gap vs QA. |
| `ec2 describe-addresses` / `describe-network-interfaces` / `describe-instances` | YES | Used to identify the `api-alpha` edge as ALB `alb-e2proxy` on **EKS**. |
| `wafv2 list-web-acls` / `get-web-acl*` | NO / empty | Could not enumerate INT WAF. |
| `cloudfront list-distributions` | NO / empty | Returned nothing for this role. |
| `logs filter-log-events` (`inttra-int-lg-bkapi`) | YES | Confirmed `%2F` requests never reach the INT booking container (blocked at edge). |

**Net:** in INT I can confirm the **app/container** layer and the **edge identity** (e2proxy on EKS, internal ALB behind it), but I **cannot** read INT ALB listener/rule or WAF/CloudFront config with this role. A trace as complete as QA's needs an infra/platform role with `elasticloadbalancing:Describe*`, `wafv2:Get*`, and `cloudfront:List*` in the INT account.
