# ION-16693 — visibility: align with commons 1.0.33-SNAPSHOT and clear the OWASP CRITICAL/HIGH findings

**Date:** 2026-08-31
**Branch:** `feature/ION-16693-visibility-owasp`
**Modules:** `visibility` (reactor pom) and `visibility-commons`; every deployable module picks the
dependency changes up through the reactor pom.
**Related:** `partner-integrator/docs/2026-08-31-pi-aws-upgrd-refactor.md` (the same 1.0.33-SNAPSHOT bump
in partner-integrator).

---

## 1. Summary

Two independent pieces of work, both triggered by the move to commons **1.0.33-SNAPSHOT**.

| # | Change | Where |
|---|---|---|
| 1 | `mercury.commons.version` `1.0.31-SNAPSHOT` → `1.0.33-SNAPSHOT` | `visibility/pom.xml` |
| 2 | `RetryClassifier` consults `MessagingException.isRetryable()` instead of returning `TRUE` for every `MessagingException` | `visibility-commons` `RetryClassifier` |
| 3 | Five new tests around the messaging verdict | `visibility-commons` `RetryClassifierTest` |
| 4 | Reactor-wide `<dependencyManagement>` closing one CRITICAL and three HIGH OWASP findings | `visibility/pom.xml` |
| 5 | `log4j.version` `2.23.1` → `2.25.5` | `visibility/pom.xml` |

Result: **every deployable visibility module now scans clean of CRITICAL and HIGH findings** (§5), and
nothing about the runtime behaviour of visibility changes except the one deliberate retry-verdict
improvement described in §2.

---

## 2. `RetryClassifier` — the messaging verdict

### 2.1 What was there

```java
if (throwable instanceof MessagingException) {
    return Boolean.TRUE;
}
```

That was the right heuristic while `MessagingException` was opaque: the classifier could see *that* a
messaging call had failed but not *why*, and the safe default for a queue-backed processor is to leave
the message on the queue for redelivery.

### 2.2 What it is now

```java
if (throwable instanceof MessagingException messagingException) {
    return messagingException.isRetryable();
}
```

`MessagingException` now extends `CloudSdkException`, which carries a `retryable` flag alongside
`operation` and `resource`:

```java
public class CloudSdkException extends RuntimeException {
    private final boolean retryable;
    private final String operation;
    private final String resource;
    public boolean isRetryable();
    ...
}
```

`SqsMessagingClient.handleException` sets that flag from `AwsFailureClassifier.isRetryable(cause)` at the
point where it wraps the AWS failure, so the SDK has already inspected the real cause before the
exception reaches visibility. `AwsFailureClassifier` applies the same rules `RetryClassifier` applies to
raw AWS exceptions a few lines further down in the same method:

| Cause | Verdict |
|---|---|
| `JacksonException` | not retryable |
| `SdkClientException` | retryable |
| `SdkServiceException` | retryable if `isRetryableException()`, `isThrottlingException()`, `isClockSkewException()`, or status ≥ 500 |
| other `SdkException` | its own `retryable()` |
| `IOException` | retryable |
| anything else | not retryable |

So the classifier no longer guesses. A `QueueDoesNotExistException`, an
`InvalidMessageContentsException` or the FIFO `UnsupportedOperationException` is now correctly permanent
instead of being redelivered until the redrive policy gives up; a throttle or a socket failure is still
transient.

The verdict short-circuits the cause-chain walk in both directions — the same treatment
`SdkServiceException` and `WebApplicationException` already get, because the flag is authoritative for
the whole call.

### 2.3 Why this is backward compatible

The two short constructors default the flag to **true**:

```java
public CloudSdkException(String message)                  { this(message, null, true, null, null); }
public CloudSdkException(String message, Throwable cause)  { this(message, cause, true, null, null); }
```

Confirmed on the 1.0.33-SNAPSHOT bytecode — both push `iconst_1` into the `retryable` slot before
delegating to the five-argument constructor.

That means:

* Any `MessagingException` built anywhere other than the SDK's classified send/receive paths — including
  the ones `WMEventProcessorTest` and `RetryClassifierTest` build with `new MessagingException("…")` —
  still classifies as transient, exactly as before.
* The only verdicts that flip are the ones where the cloud-sdk explicitly recorded `retryable = false`,
  i.e. failures that could never have succeeded on a replay. Those are precisely the cases the ticket
  asks us to stop replaying.
* The `NonReprocessible` and `JsonProcessingException` rules still run *before* the per-throwable walk,
  so a retryable `MessagingException` nested under a persistence failure stays permanent. Covered by a
  new test.

Nothing else in visibility constructs, catches or re-throws the cloud-sdk `MessagingException`; the only
production reference is this one line in `RetryClassifier`. (`visibility-inbound`'s `EmailSender` uses
`jakarta.mail.MessagingException`, an unrelated type.)

---

## 3. The dependency work

### 3.1 What the commons bump does — and does not — do

Comparing the declared dependency sets of `cloud-sdk-api`, `cloud-sdk-aws` and `commons` between
1.0.31-SNAPSHOT and 1.0.33-SNAPSHOT, the only third-party delta is an added direct
`com.fasterxml.jackson.core:jackson-core:2.21.4` in `cloud-sdk-aws`. Every other library keeps the
version it already had, and no class was removed from either jar.

So the bump is what unlocks `isRetryable()`; it is **not** what fixes the OWASP findings. Those needed
explicit version management.

### 3.2 The pins

Three of the four live in a new `<dependencyManagement>` block in `visibility/pom.xml`; log4j needed
only the property (see below). Nothing in that block *adds* a dependency — it only decides which version
Maven picks when several paths disagree, which is why every module keeps exactly the dependency set it
had before.

| Library | Was | Now | Closes |
|---|---|---|---|
| Jetty (`jetty-bom` + `jetty-ee10-bom`) | 12.1.9 / 12.1.12 split | 12.1.12 | CVE-2026-10050 (HIGH, CVSS v3 9.1), CVE-2026-10051 (MEDIUM, v3 7.5) |
| `httpclient5` | 5.4.4 | 5.6.4 | CVE-2026-71290 (CRITICAL 9.1), CVE-2026-64607 (MEDIUM) |
| `log4j-api` / `log4j-core` (property only) | 2.23.1 | 2.25.5 | CVE-2026-34479 (v3 HIGH 7.5), CVE-2026-34477, CVE-2026-49844 |
| `guava` | 31.0.1-jre / 33.5.0-jre split | 33.5.0-jre | CVE-2023-2976 (HIGH 7.1), CVE-2020-8908 (LOW) |

**Jetty.** commons 1.0.33 already asks for 12.1.12, but `dropwizard-core` 5.0.2 asks for 12.1.9 from an
equally short path, and Maven's nearest-wins tie-break left the reactor with a genuinely mixed set:
`jetty-http`, `jetty-io`, `jetty-session` and `jetty-ee10-servlets` at 12.1.12 sitting next to
`jetty-server`, `jetty-util`, `jetty-security` and `jetty-ee10-servlet` at 12.1.9. Importing both BOMs
settles every Jetty artifact — including the ones nothing names directly — at one patch release inside
the same 12.1 line, so there is no API change to absorb, and the split goes away as a side benefit.

**httpclient5.** CVE-2026-71290: `HostnameVerificationPolicy#BUILTIN` has no effect on the async client,
so an attacker able to intercept traffic can impersonate the server with a certificate for a different
domain. Affects 5.4 up to but not including 5.6.4; commons pins 5.4.4.

Two artifacts with confusable names are involved, so to be explicit: the vulnerable one is
`org.apache.httpcomponents.client5:httpclient5`, which went **5.4.4 → 5.6.4**.
`org.apache.httpcomponents.core5:httpcore5` is a different artifact, and it stays at **5.4.3** — the
version commons already pins. If anything the pair becomes more consistent: httpclient5 5.6.4 is built
against httpcore5 5.4.3, whereas 5.4.4 was built against 5.4.3's predecessor 5.3.4, so commons was
already running a client against a newer core than it targeted.

**log4j.** This one needed no `dependencyManagement` entry — the property was enough. No commons
artifact declares log4j-api; visibility-commons and visibility-inbound declare it themselves against
`${log4j.version}`, and every other module reaches it through visibility-commons at depth 2, which beats
every competing path. Verified by removing the managed entries and re-resolving: `visibility-matcher`
still gets 2.25.5. `log4j-core` keeps its existing test scope — only the version moves — and the
`LoaderUtil.getClassLoaders()` entry point embedded DynamoDB Local needs is still present in 2.25.5
(the DynamoDB Local integration tests pass).

**guava.** 31.0.1-jre arrives through `guice` 7.0.0 (via `cloud-sdk-api`). `visibility-inbound`,
`visibility-s3-archiver` and `visibility-error-email` were already resolving 33.5.0-jre — the last one
declares it explicitly, with a comment about needing a Guice-7-compatible Guava (`buildOrThrow`) — while
matcher, outbound, pending, pending-start, outbound-poller and itv-gps-processor were still landing on
31.0.1-jre. The pin is the version three modules already ship, so it is proven in this codebase.

---

## 4. Tests

`RetryClassifierTest` grows from 53 to **58** tests. The new ones pin down both halves of the rule:

| Test | Asserts |
|---|---|
| `isReprocessible_returnsTrueForMessagingExceptionWithCause` | the legacy `(message, cause)` constructor is still transient |
| `isReprocessible_returnsTrueForRetryableMessagingException` | `retryable = true` → transient |
| `isReprocessible_returnsFalseForNonRetryableMessagingException` | `retryable = false` → permanent |
| `isReprocessible_messagingExceptionFlagIsAuthoritativeOverNestedCause` | the flag beats a nested `SocketTimeoutException` |
| `isReprocessible_nonReprocessibleWinsOverRetryableMessagingException` | the persistence boundary still wins |
| (existing) `isReprocessible_returnsTrueForMessagingException` | `new MessagingException("…")` is unchanged |

A helper builds the exception the way `SqsMessagingClient` does:

```java
private static MessagingException messagingException(boolean retryable, Throwable cause) {
    return new MessagingException("sqs failure", cause, retryable, "sendMessage", "visibility-queue");
}
```

Full reactor run — `mvn -pl visibility -amd clean package`:

| Module | Tests | Failures | Errors | Skipped |
|---|---:|---:|---:|---:|
| visibility-commons | 465 | 0 | 0 | 1 |
| visibility-inbound | 458 | 0 | 0 | 1 |
| visibility-wm-inbound-processor | 151 | 0 | 0 | 0 |
| visibility-matcher | 97 | 0 | 0 | 0 |
| visibility-outbound | 43 | 0 | 0 | 2 |
| visibility-pending | 6 | 0 | 0 | 0 |
| visibility-s3-archiver | 23 | 0 | 0 | 0 |
| visibility-pending-start | 12 | 0 | 0 | 1 |
| visibility-error-email | 15 | 0 | 0 | 1 |
| visibility-outbound-poller | 12 | 0 | 0 | 0 |
| visibility-itv-gps-processor | 18 | 0 | 0 | 0 |
| **total** | **1300** | **0** | **0** | **6** |

The six skips are pre-existing disabled cases, untouched by this branch.

---

## 5. OWASP verification

### 5.1 How it was run

The repo script resolves the shaded jar and the module's own `suppressions.xml`, and writes reports
outside `target/` so `mvn clean` cannot delete them:

```bash
mvn -pl visibility -amd clean package          # the jar must exist before scanning
./dependency-check.sh visibility/<module>      # add --no-update to reuse the NVD cache
```

The equivalent raw CLI call, in the same shape as the rates one, run from the module's `target`
directory:

```powershell
dependency-check --project visibility-inbound `
                 --scan ./visibility-inbound-1.0.jar `
                 --out owasp `
                 --suppression ../suppressions.xml `
                 --nvdApiKey $env:NVD_API_KEY
```

Reports for every module land in `owasp-reports/visibility/<module>/`.

`visibility-commons` is scanned too, but it is a thin library jar rather than a shaded uber-jar, so it
reports nothing either way; the ten deployables are the meaningful targets.

### 5.2 Before

| Module | CRITICAL | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|---:|
| visibility-inbound | 1 | 4 | 11 | 0 |
| visibility-wm-inbound-processor | 1 | 4 | 11 | 0 |
| visibility-matcher | 1 | 5 | 11 | 1 |
| visibility-outbound | 1 | 5 | 11 | 1 |
| visibility-pending | 1 | 5 | 11 | 1 |
| visibility-s3-archiver | 1 | 4 | 11 | 0 |
| visibility-pending-start | 1 | 5 | 11 | 1 |
| visibility-error-email | 1 | 0 | 8 | 0 |
| visibility-outbound-poller | 1 | 5 | 11 | 1 |
| visibility-itv-gps-processor | 1 | 5 | 11 | 1 |

The CRITICAL was httpclient5 everywhere; the HIGHs were the four Jetty artifacts plus, where Guava had
resolved to 31.0.1-jre, CVE-2023-2976.

### 5.3 After

| Module | CRITICAL | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|---:|
| visibility-commons | 0 | 0 | 0 | 0 |
| visibility-inbound | 0 | 0 | 3 | 0 |
| visibility-wm-inbound-processor | 0 | 0 | 3 | 0 |
| visibility-matcher | 0 | 0 | 3 | 0 |
| visibility-outbound | 0 | 0 | 3 | 0 |
| visibility-pending | 0 | 0 | 3 | 0 |
| visibility-s3-archiver | 0 | 0 | 3 | 0 |
| visibility-pending-start | 0 | 0 | 3 | 0 |
| visibility-error-email | 0 | 0 | 4 | 0 |
| visibility-outbound-poller | 0 | 0 | 3 | 0 |
| visibility-itv-gps-processor | 0 | 0 | 3 | 0 |

**No CRITICAL or HIGH findings remain in any visibility module** — the objective of the ticket. The
LOWs are gone too, as a side effect of the Guava pin.

Resolved versions in the shipped jars, confirmed from the reports:

```
org.eclipse.jetty:jetty-server        12.1.12
org.eclipse.jetty:jetty-util          12.1.12
org.eclipse.jetty:jetty-security      12.1.12
org.eclipse.jetty:jetty-http/io/session 12.1.12
org.eclipse.jetty.ee10:jetty-ee10-servlet(s) 12.1.12
org.apache.httpcomponents.client5:httpclient5 5.6.4   (httpcore5 unchanged at 5.4.3)
org.apache.logging.log4j:log4j-api    2.25.5
com.google.guava:guava                33.5.0-jre
```

### 5.4 What still shows up, and why it was left

| Severity | CVE | Dependency | Why |
|---|---|---|---|
| MEDIUM | CVE-2026-54515 | `jackson-databind:2.22.0` | No fixed release published yet; the CPE matches the exact version rather than a range. Bumping `jackson.version` reaches far beyond visibility, so it belongs in its own ticket. |
| MEDIUM | CVE-2014-3577, CVE-2020-13956 | `metrics-httpclient5:4.2.39` | False positives. Both are Apache HttpClient **4.x** CVEs (fixed in 4.3.4 and 4.5.13); dependency-check matches them onto the Dropwizard metrics *wrapper* through the `apache:httpclient` CPE. The jars only ever ship httpclient **5.6.4**. |
| MEDIUM | CVE-2025-48924 | `commons-lang3:3.13.0` | `visibility-error-email` only. Every other module already resolves 3.20.0; this one is an older transitive path. MEDIUM, out of scope for this ticket. |

Observation for a follow-up: each module's `suppressions.xml` suppresses CVE-2025-11226 on
`logback-core@1.5.26`, but the reactor resolves logback-core **1.5.38** (unchanged by this branch), so
those rules no longer match anything. Harmless, but they can be retired or re-pointed.

---

## 6. Backward-compatibility checklist

| Concern | Verdict |
|---|---|
| Public API of `RetryClassifier` | unchanged — same two static methods, same signatures |
| `new MessagingException(msg)` / `(msg, cause)` verdicts | unchanged (`retryable` defaults to `true`) |
| `NonReprocessible` and payload-failure precedence | unchanged; a new test pins it |
| DynamoDB, network, HTTP, socket and `IOException` rules | untouched |
| Dependencies added or removed | none — `dependencyManagement` only selects versions |
| Jetty | patch bump inside 12.1.x, and it *removes* a pre-existing 12.1.9/12.1.12 split |
| httpclient5 | 5.6.4 keeps the same `httpcore5` 5.4.3 the classpath already had |
| guava | pinned to the version three visibility modules already ship |
| log4j | API-compatible 2.x patch line; DynamoDB Local integration tests pass |
| Config, wiring, Guice modules, DAOs, DTOs | untouched |
| Tests | 1300 run, 0 failures, 0 errors |

The one intentional behaviour change is in §2: a `MessagingException` that the cloud-sdk marked
non-retryable is now finalised rather than redelivered. That is the point of the ticket, and it can only
affect failures that were guaranteed to fail again on replay.

---

## 7. Out of scope / notes

* `visibility/visibility-inbound/generated/swagger-ui/visibility-1.0.json` is regenerated by the build
  and is stale in git — it is missing the `moduleType` enum. That field exists identically in commons
  1.0.31 and 1.0.33, so the staleness predates this branch and any `mvn package` on `develop` produces
  the same diff. Left out of this commit to keep it focused; worth its own housekeeping change.
* The `jackson-databind` and `commons-lang3` MEDIUMs in §5.4 are deliberately not addressed here.

---

## 8. Review questions

### 8.1 Why did the Jetty split hit visibility but not booking or booking-bridge, on the same commons?

Because Maven picks versions by **shortest path, then declaration order**, and the visibility modules are
the ones whose shortest path to `commons` is longer than their shortest path to `dropwizard-core`.

`commons` pins Jetty 12.1.12 in its own `<dependencies>` — it has no `<dependencyManagement>` at all, so
those pins are ordinary transitive nodes that have to *win a distance contest* rather than being imposed.
Meanwhile `cloud-sdk-api` declares `io.dropwizard:dropwizard-core:5.0.2` at compile scope, and
dropwizard-core declares `jetty-server`, `jetty-util`, `jetty-security` and `jetty-ee10-servlet` directly
at **12.1.9**.

Now compare the graphs.

**visibility-inbound** (and every other visibility module) declares `cloud-sdk-api` directly but does
*not* declare `commons` directly — it reaches it through `visibility-commons`:

```text
visibility-inbound
 +- cloud-sdk-api          (1)
 |   +- dropwizard-core    (2)
 |       +- jetty-server 12.1.9        (3)   <-- wins the tie
 |       +- dropwizard-jetty (3)
 |           +- jetty-http 12.1.9      (4)
 +- visibility-commons     (1)
     +- commons            (2)
         +- jetty-server 12.1.12       (3)   <-- same depth, declared later
         +- jetty-http   12.1.12       (3)   <-- wins, nothing else is nearer
```

Both `jetty-server` candidates sit at depth 3, so the tie breaks on declaration order — and
`cloud-sdk-api` is declared before `visibility-commons` in the module pom, so **12.1.9** wins.
`jetty-http`, `jetty-io` and `jetty-session` are not direct children of dropwizard-core; they only arrive
via `dropwizard-jetty` at depth 4, so commons' depth-3 **12.1.12** wins for those. That is precisely the
observed split: server / util / security / ee10-servlet at 12.1.9, http / io / session / ee10-servlets at
12.1.12.

**booking-bridge** declares `commons` as a *direct* dependency:

```text
booking-bridge
 +- cloud-sdk-api          (1)
 |   +- dropwizard-core    (2)
 |       +- jetty-server 12.1.9        (3)
 +- commons                (1)
     +- jetty-server 12.1.12           (2)   <-- strictly nearer, wins outright
     +- jetty-http   12.1.12           (2)
```

commons' pins land at depth 2 and beat dropwizard-core's at depth 3 outright — no tie, no split.
Confirmed by resolving it: booking-bridge on commons **1.0.31** gets 12.1.12 for *every* Jetty artifact.

> **Corrected in [§10.1](#101-correction-booking-is-a-dropwizard-service-not-a-lambda).** This
> paragraph originally claimed booking never ships Jetty because it is a Lambda. That is wrong on both
> counts: booking is a **Dropwizard service**, its main shaded jar does contain Jetty, and the exclusion
> block below belongs only to the secondary `booking-lambdas` artifact. The paragraph is kept here so the
> correction has something to point at — read §10.1 for what actually happens.

**booking** ~~never ships Jetty at all~~. Its shade configuration excludes it explicitly:

```xml
<!-- Jetty: ~4MB, server-only -->
<exclude>org.eclipse.jetty:*</exclude>
<exclude>org.eclipse.jetty.toolchain:*</exclude>
<!-- Dropwizard: ~2MB, server-only -->
<exclude>io.dropwizard:*</exclude>
```

~~booking is a Lambda, so the servlet container is dead weight.~~ In fact booking declares `commons`
directly, and first — so it wins the same way booking-bridge does, and its service jar carries Jetty
**12.1.12**. See §10.1.

So the honest summary is: **it is not that booking and booking-bridge are safe and visibility is not.**
Both of them declare `commons` directly and resolve clean; visibility reaches it transitively and lost
the tie-break. The same latent exposure exists in every module that declares
`cloud-sdk-api` without also declaring `commons` directly — today that is all ten visibility deployables
and all six `partner-integrator` sub-modules.

### 8.2 But there is no library diff between 1.0.31 and 1.0.33 — so why did this surface now?

Correct, and worth stating plainly: **the commons bump did not cause any of these findings.** The only
third-party delta between 1.0.31 and 1.0.33 is an added `jackson-core:2.21.4` in `cloud-sdk-aws`.

The findings surfaced because the *CVEs* are new, not because the dependencies moved. CVE-2026-10050,
CVE-2026-10051 and CVE-2026-71290 were all published recently; a scan of the same jars a few weeks ago
would have come back clean. The Jetty split, likewise, has been there for as long as the current
`cloud-sdk-api` / `commons` shapes have — it only became visible when a scan started reporting on 12.1.9.

The two pieces of work simply travel together in one ticket: 1.0.33 is what makes `isRetryable()`
available, and the CVE work is what the scan asked for.

### 8.3 Is there a better way to handle this in mercury-services-commons?

Yes, and it would remove the need for most of the new block in `visibility/pom.xml`. Four things, roughly
in order of value:

**1. Publish a BOM.** `dependencyManagement` in the *consuming* pom is the only mechanism that overrides
nearest-wins. Pinning versions in commons' own `<dependencies>` — what happens today — only works when
commons happens to sit at a shorter path than the competitor, which is exactly the fragility §8.1
describes. A `com.inttra.mercury:mercury-bom` (packaging `pom`, nothing but `<dependencyManagement>`)
covering Jetty, Guava, log4j, jackson, httpclient5/httpcore5 and the AWS SDK would let every app write:

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.inttra.mercury</groupId>
      <artifactId>mercury-bom</artifactId>
      <version>${mercury.commons.version}</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

and the visibility block collapses to that one import. It also means a future CVE is fixed once, in
commons, instead of in every app pom.

**2. Stop `cloud-sdk-api` leaking a servlet container.** `cloud-sdk-api` is an SDK API surface, yet it
declares `dropwizard-core` at compile scope, which is the sole reason Jetty 12.1.9 is in the graph at
all. Any of these fixes it at the source: exclude `org.eclipse.jetty*` / `dropwizard-jetty` from that
dependency, mark it `provided`, or split the Dropwizard-facing helpers into a separate
`cloud-sdk-dropwizard` artifact that only server apps depend on. The Lambda modules would get smaller
jars for free — several of them already hand-exclude the same coordinates.

**3. Manage Guava and log4j, which commons does not touch today.** commons declares neither. Guava's
version is currently decided by an accident of the graph — guice 7.0.0 says 31.0.1-jre, dropwizard-core
5.0.2 says 33.6.0-jre — which is why different visibility modules shipped different Guava. log4j-api is
in the same position. Both belong in the BOM.

**4. Fail the build on a split.** `maven-enforcer-plugin` with `requireUpperBoundDeps` (or
`dependencyConvergence`) would have caught the 12.1.9 / 12.1.12 mix at build time rather than in a
periodic scan.

Until any of that lands, the block in `visibility/pom.xml` is the correct local remedy: it is the only
place a consumer can assert a version, and each entry carries its reason inline.

### 8.4 The team may ignore the httpclient5 CRITICAL because the async client is not used — is there any downside to fixing it anyway?

The exploitability argument is sound. CVE-2026-71290 is specific to the **async** client: on the classic
(`CloseableHttpClient`) path `HostnameVerificationPolicy.BUILTIN` behaves correctly; only
`CloseableHttpAsyncClient` ignores it. And in visibility the question is even simpler — **no visibility
source file references `org.apache.hc.*` at all.** httpclient5 is in the uber-jars purely because commons
declares `dropwizard-client` plus `httpclient5`, and visibility never builds a Dropwizard `JerseyClient`.
Its outbound HTTP goes through Jest and the AWS SDK, which use httpclient **4.x** and the AWS
Apache / URL-connection clients. So the vulnerable code is present but unreachable.

Given that, the fair question is whether the upgrade is worth any risk at all. What it costs was measured
rather than assumed — comparing the class sets, and the constant-pool references of the two artifacts on
the classpath that actually bind to httpclient5:

| Check | Result |
|---|---|
| Classes in httpclient5 5.4.4 + httpcore5 5.4.3 | 1203 |
| Classes in httpclient5 5.6.4 + httpcore5 5.4.3 | 1273 |
| Classes removed between them | 2 — `ProtocolSwitchStrategy$ProtocolSwitch` and `HttpAuthenticator$1`, both internal |
| `metrics-httpclient5:4.2.39` | binds 50 httpclient5/httpcore5 classes, **0** missing in 5.6.4 |
| `dropwizard-client:5.0.2` | binds 62 httpclient5/httpcore5 classes, **0** missing in 5.6.4 |

Nothing on the classpath binds to either removed class, `httpcore5` does not move, and the full test
suite passes. So: **no adverse impact found.**

The remaining trade-off is organisational, not technical — visibility runs one artifact ahead of commons
until commons catches up. Weighed against the alternative, which is carrying a CRITICAL in every scan
report plus a suppression entry that has to be re-justified each time someone reads it, taking the
upgrade is the cheaper option. It also clears CVE-2026-64607 (MEDIUM) in the same move.

If the team prefers to defer instead, the clean way to defer is a suppression entry naming the CVE and
the "async client not used" rationale — not silence.

### 8.5 Does the commons SDK not pin Guava or log4j? Why pin them in visibility?

It does not, and that is the whole reason.

| Library | Managed by commons? | Where the version actually came from |
|---|---|---|
| Jetty | pinned at 12.1.12, but only as a plain `<dependency>` — so it has to win on path length, and in visibility it did not | commons 12.1.12 vs dropwizard-core 12.1.9 |
| `httpclient5` | pinned at 5.4.4 as a plain `<dependency>` | commons |
| `httpcore5` / `httpcore5-h2` | pinned at 5.4.3 | commons |
| **Guava** | managed at 33.5.0-jre in the commons *build parent*, but **absent from every published pom** | guice 7.0.0 → 31.0.1-jre, or dropwizard-core 5.0.2 → 33.6.0-jre, whichever won per module |
| **log4j-api / log4j-core** | **not declared** — commons only *excludes* log4j-api from `poi` and `poi-ooxml` | visibility-commons' own `${log4j.version}` |

So Guava had no owner anywhere a *consumer* can see — §9 explains why the build parent's pin does not
reach us — which is exactly why visibility shipped two different
Guavas: 31.0.1-jre in matcher, outbound, pending, pending-start, outbound-poller and itv-gps-processor;
33.5.0-jre in inbound, s3-archiver and error-email — the last of which had already hand-pinned it, with a
comment, to get a Guice-7-compatible `Map.buildOrThrow`. Pinning it in the visibility reactor is not a
preference; it is the first place in the chain where anybody asserts a version.

log4j is the one case that did **not** need managing. Because visibility-commons declares log4j-api and
log4j-core itself against `${log4j.version}`, and every other module reaches them through
visibility-commons at depth 2, moving the property alone lifts the whole reactor. Verified by deleting
the managed entries and re-resolving — `visibility-matcher` still gets 2.25.5 — so those entries were
dropped and only the property remains.

---

## 9. Fixing this properly in mercury-services-commons (proposal for 1.0.34-SNAPSHOT)

Everything in §8 is a symptom. This section is the cause and the cure.

Repo: `mercury-services-commons`, branch `feature/ION-12310-commons-cloudsdk-refactoring`,
HEAD `9dd413c ION-12310: bump to 1.0.33-SNAPSHOT and document the release`.

### 9.1 Root cause: the published poms are flattened, so all dependency management is erased

The commons build parent (`com.inttra.mercury:mercury-services-commons:1.0`) is already excellent. It
carries a full `<dependencyManagement>`, with reasoned comments on nearly every entry:

```xml
<jetty.version>12.1.12</jetty.version>
<dropwizard.version>5.0.2</dropwizard.version>
<google.guava.version>33.5.0-jre</google.guava.version>
<commons-lang3.version>3.20.0</commons-lang3.version>
<logback.version>1.5.38</logback.version>
...
<dependencyManagement>
  <dependencies>
    <dependency> org.eclipse.jetty:jetty-bom            ${jetty.version}   pom/import </dependency>
    <dependency> org.eclipse.jetty.ee10:jetty-ee10-bom  ${jetty.version}   pom/import </dependency>
    <dependency> io.dropwizard:dropwizard-dependencies  ${dropwizard.version} pom/import </dependency>
    <dependency> com.google.guava:guava                 ${google.guava.version} </dependency>
    ...
```

None of that reaches a downstream app. Every publishable module runs
**`flatten-maven-plugin`** (`cloud-sdk-api/pom.xml:114`, and the same in its siblings), and a flattened
pom is by design standalone: **no `<parent>`, no `<properties>`, and no `<dependencyManagement>`** — only
a flat `<dependencies>` list with every version inlined.

Compare. Source `cloud-sdk-api/pom.xml`:

```xml
<parent>
  <groupId>com.inttra.mercury</groupId>
  <artifactId>mercury-services-commons</artifactId>
  <version>1.0</version>
</parent>
...
<dependency>
  <groupId>io.dropwizard</groupId>
  <artifactId>dropwizard-core</artifactId>     <!-- no version: the parent manages it -->
</dependency>
```

Published `cloud-sdk-api-1.0.33-SNAPSHOT.pom` (`grep -c dependencyManagement` → **0**):

```xml
<project>                                       <!-- no <parent> -->
  <groupId>com.inttra.mercury</groupId>
  <artifactId>cloud-sdk-api</artifactId>
  <version>1.0.33-SNAPSHOT</version>
  <dependencies>
    <dependency>
      <groupId>io.dropwizard</groupId>
      <artifactId>dropwizard-core</artifactId>
      <version>5.0.2</version>                  <!-- inlined, and nothing constrains its Jetty -->
    </dependency>
```

So what a consumer actually receives from `cloud-sdk-api` is a hard `dropwizard-core:5.0.2` with **no
accompanying Jetty constraint at all**. dropwizard-core then contributes Jetty 12.1.9 as an ordinary
transitive node, and the parent's `jetty-bom 12.1.12` — which would have overridden it instantly — was
deleted at publish time.

### 9.2 The current workaround, and why it is not enough

The team already knows about this. `commons/pom.xml` says so in its own comments:

```xml
<!-- Jetty CVE fix: pin 12.1.12 in the published (flattened) POM.
     ... Maven's "nearest wins" gives consumers 12.1.12. -->

<!-- Direct deps at the pinned safe versions so they appear in the flattened POM and win ... -->

<!-- ... commons and dynamo-integration-test both declare the two artifacts explicitly so
     consumers resolve a coherent pair at depth 1 regardless of nearest-wins. -->
```

The workaround is: **re-declare the safe version as a real `<dependency>` of `commons`** so it survives
flattening and wins on proximity. It is applied today to logback-core/classic, httpcore5, httpcore5-h2,
httpclient5, the legacy httpcore/httpclient 4.x, and the eight Jetty artifacts.

It has two structural weaknesses, and visibility hit both:

1. **It is a proximity bet, not a constraint.** It only wins while `commons` sits closer to the app than
   the competing path. visibility reaches `commons` at depth 2 (through `visibility-commons`) while
   `cloud-sdk-api` is at depth 1 — so commons' Jetty lands at depth 3, ties with dropwizard-core's
   12.1.9, and loses the tie on declaration order (§8.1). booking-bridge, which declares `commons`
   directly, wins the same bet. Same commons, same version, opposite outcome.
2. **It only covers artifacts someone remembered to list.** Guava is managed at 33.5.0-jre in the build
   parent but is **not** a direct dependency of `commons`, so it appears in **zero** published poms
   (`grep -c '<artifactId>guava</artifactId>'` on the published commons pom → **0**). It therefore has no
   owner a consumer can see, and each app lands wherever nearest-wins drops it. log4j-api is the same:
   it appears in the published commons pom only inside `<exclusions>` for `poi` and `poi-ooxml`.

### 9.3 Proposal for 1.0.34-SNAPSHOT

Three changes, independent, in decreasing order of value. The first two would each, on their own, have
made this ticket's `visibility/pom.xml` block unnecessary.

#### 9.3.1 Publish a real BOM — new module `mercury-bom`

`dependencyManagement` in the *consuming* pom is the only thing that overrides nearest-wins. Since
flattening strips it from the library poms, commons has to ship it as a separate artifact whose whole
purpose is to be imported.

Add a module to the commons reactor:

```
mercury-services-commons/
  mercury-bom/pom.xml        <-- new: packaging pom, nothing but <dependencyManagement>
```

```xml
<project>
  <parent>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>mercury-services-commons</artifactId>
    <version>1.0</version>
  </parent>
  <artifactId>mercury-bom</artifactId>
  <version>${dependency.version}</version>   <!-- 1.0.34-SNAPSHOT, tracks the library line -->
  <packaging>pom</packaging>

  <dependencyManagement>
    <dependencies>
      <!-- the same content the build parent already has, plus the gaps in 9.3.3 -->
      <dependency>
        <groupId>org.eclipse.jetty</groupId>
        <artifactId>jetty-bom</artifactId>
        <version>${jetty.version}</version>
        <type>pom</type><scope>import</scope>
      </dependency>
      <dependency>
        <groupId>org.eclipse.jetty.ee10</groupId>
        <artifactId>jetty-ee10-bom</artifactId>
        <version>${jetty.version}</version>
        <type>pom</type><scope>import</scope>
      </dependency>
      <dependency>
        <groupId>io.dropwizard</groupId>
        <artifactId>dropwizard-dependencies</artifactId>
        <version>${dropwizard.version}</version>
        <type>pom</type><scope>import</scope>
      </dependency>
      <dependency>
        <groupId>com.google.guava</groupId>
        <artifactId>guava</artifactId>
        <version>${google.guava.version}</version>
      </dependency>
      <dependency>
        <groupId>org.apache.httpcomponents.client5</groupId>
        <artifactId>httpclient5</artifactId>
        <version>${httpclient5.version}</version>
      </dependency>
      <!-- httpcore5 / httpcore5-h2, logback pair, log4j-api/core, jackson modules,
           commons-lang3, slf4j-api, guice, the AWS SDK BOM ... -->
    </dependencies>
  </dependencyManagement>
</project>
```

**The one detail that must not be missed:** `flatten-maven-plugin` deletes `<dependencyManagement>` under
its default mode, which would make this module ship empty. Either skip flattening for `mercury-bom`, or
set the mode the plugin provides for exactly this case:

```xml
<configuration>
  <flattenMode>bom</flattenMode>   <!-- keeps dependencyManagement; resolves the parent and properties -->
</configuration>
```

Verify after building it that the installed `mercury-bom-1.0.34-SNAPSHOT.pom` still contains
`<dependencyManagement>` — that check is the whole point of the module.

Downstream, every app then replaces its hand-rolled pins with one import:

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>com.inttra.mercury</groupId>
      <artifactId>mercury-bom</artifactId>
      <version>${mercury.commons.version}</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

For visibility that is a straight swap for the whole block added in this ticket. The gain is not
cosmetic: a future Jetty CVE becomes one property change in commons instead of a hunt through every app
pom, and version selection stops depending on where in the graph an app happens to sit.

*Why not just import the existing parent* (`mercury-services-commons:1.0`, `type=pom`, `scope=import`)?
It is technically legal and the management is already there, but it is a poor contract: the parent is
frozen at version `1.0` while the libraries move (`1.0.33`, `1.0.34`, …), so an app could never express
"the management that goes with the commons I am on", and importing a reactor parent also drags in
`<modules>` and build config that has nothing to do with a consumer. A versioned BOM is the honest
artifact.

#### 9.3.2 Stop `cloud-sdk-api` exporting a servlet container

This is the smallest change with the largest blast radius, and it is worth doing even if the BOM lands.

`cloud-sdk-api` is an SDK API surface — messaging, storage, database, notification interfaces — yet its
published pom hands every consumer `dropwizard-core:5.0.2` at compile scope. That single line is the only
reason Jetty is in the visibility graph at all, and it arrives with no version constraint attached
(§9.1). Options, in order of preference:

1. **Split it.** Move the Dropwizard-facing helpers (bundles, `Configuration` mix-ins, the
   `EventLoggingConfig`-style types) into a new `cloud-sdk-dropwizard` module. `cloud-sdk-api` then has
   no Dropwizard dependency at all, and only server apps pull the Dropwizard half.
2. **Scope it `provided`.** Correct in spirit — the app supplies the server — and it stops the transitive
   export immediately. Consumers that genuinely need Dropwizard already declare it.
3. **Exclude the server stack** from that one dependency. Least invasive; exclusions *do* survive
   flattening:

   ```xml
   <dependency>
     <groupId>io.dropwizard</groupId>
     <artifactId>dropwizard-core</artifactId>
     <exclusions>
       <exclusion><groupId>org.eclipse.jetty</groupId><artifactId>*</artifactId></exclusion>
       <exclusion><groupId>org.eclipse.jetty.ee10</groupId><artifactId>*</artifactId></exclusion>
     </exclusions>
   </dependency>
   ```

Any of the three removes the 12.1.9 source outright, so the split in §8.1 cannot re-form. The Lambda
modules benefit too: `booking`, `partner-integrator/pi-bl-es-lambda` and several others already
hand-exclude these exact coordinates from their shade plugins to stay under the 250 MB Lambda limit —
they would stop needing to.

#### 9.3.3 Close the two gaps: Guava and log4j

Whether or not the BOM lands, these two have no consumer-visible owner today and should get one.

| Artifact | Today | 1.0.34 |
|---|---|---|
| `com.google.guava:guava` | managed at 33.5.0-jre in the build parent; **absent from every published pom** | add to the BOM, and/or declare it directly in `commons` the way logback and httpcore5 already are |
| `org.apache.logging.log4j:log4j-api` / `log4j-core` | appears in the published commons pom only inside `<exclusions>` | add to the BOM at a current 2.25.x |
| `org.apache.httpcomponents.client5:httpclient5` | pinned 5.4.4 — the version CVE-2026-71290 affects | move to **5.6.4**; it targets the httpcore5 **5.4.3** commons already pins, where 5.4.4 targeted 5.3.4 (§8.4) |

The httpclient5 row matters beyond visibility: every app on commons is carrying that CRITICAL right now,
and fixing it in commons fixes it everywhere at once instead of app by app.

#### 9.3.4 Make a split fail the build

Once the BOM exists, add to the commons parent (and ideally to `mercury-services`):

```xml
<plugin>
  <artifactId>maven-enforcer-plugin</artifactId>
  <executions><execution>
    <goals><goal>enforce</goal></goals>
    <configuration><rules>
      <requireUpperBoundDeps/>       <!-- fails when a nearer path downgrades a library -->
      <banDuplicatePomDependencyVersions/>
    </rules></configuration>
  </execution></executions>
</plugin>
```

`requireUpperBoundDeps` is precisely the rule that would have failed the visibility build the day the
12.1.9/12.1.12 mix appeared, instead of leaving it to be found by a CVE scan months later.

### 9.4 Suggested sequencing

| Step | Change | Risk | Effect |
|---|---|---|---|
| 1 | `cloud-sdk-api` stops exporting Jetty (§9.3.2, option 3 is the cheapest) | low — removes artifacts nothing in the SDK compiles against | kills the 12.1.9 source for every consumer |
| 2 | Bump `httpclient5` to 5.6.4 in commons (§9.3.3) | low — measured in §8.4: 0 binding breaks | clears the CRITICAL repo-wide |
| 3 | Add `mercury-bom` with `flattenMode=bom` (§9.3.1) | none for existing apps until they import it | opt-in, per app, at their own pace |
| 4 | Apps swap their local pins for the BOM import | low | `visibility/pom.xml` loses its whole `<dependencyManagement>` block |
| 5 | Turn on `requireUpperBoundDeps` (§9.3.4) | medium — will surface other latent splits | stops the next one before it ships |

Steps 1 and 2 are worth doing on their own even if the BOM is deferred; together they would have made
this entire ticket a one-line commons bump.

### 9.5 What visibility should do when 1.0.34 lands

Nothing urgent — the pins added here are correct and self-documenting, and they become harmless
no-ops once commons manages the same versions. When visibility next moves to 1.0.34-SNAPSHOT:

1. Import `mercury-bom` in `visibility/pom.xml`.
2. Delete the `jetty-bom` / `jetty-ee10-bom` / `httpclient5` / `guava` entries and the
   `jetty.version`, `httpclient5.version`, `guava.version` properties.
3. Keep `log4j.version` only if commons still does not manage log4j.
4. Re-run `./dependency-check.sh visibility/<module>` on the rebuilt jars and confirm the CRITICAL/HIGH
   count is still zero before removing anything.

---

## 10. Follow-up analysis

Three questions raised in review. No code was changed for this section — it is analysis only.

### 10.1 Correction: booking is a Dropwizard service, not a Lambda

§8.1 said "booking is a Lambda, so the servlet container is dead weight". **That is wrong, and the
conclusion it supported was wrong too.**

`booking` runs **two** shade executions (`booking/pom.xml:461` and `:560`):

| Execution | Artifact | Excludes |
|---|---|---|
| `shade-main` | `booking-${version}.jar`, `Main-Class: com.inttra.mercury.booking.BookingApplication` | only `com.almworks.sqlite4java:*` |
| `shade-lambda` | `booking-lambdas-${version}.jar` (classifier `lambdas`) | Jetty, Dropwizard, Swagger, MySQL, Hibernate, Hystrix, SSO, CRT … |

The primary artifact is the **Dropwizard service**. The `booking-lambdas` jar is a secondary, aggressively
trimmed artifact for two handlers only — `S3ArchiveHandler` and `IndexerHandler`. The exclusion block
quoted in §8.1 belongs to that second jar, and its "Lambda uses IAM role" / "server-only" comments are
scoped to it. The service jar ships the full Jetty stack.

**So the real reason booking is clean is the same as booking-bridge, not the exclusions.** Resolved:

```
[INFO] +- com.inttra.mercury:commons:jar:1.0.31-SNAPSHOT:compile          <- line 97, depth 1
[INFO] +- com.inttra.mercury:cloud-sdk-api:jar:1.0.31-SNAPSHOT:compile    <- line 569
```

`booking` declares `commons` directly, and *before* `cloud-sdk-api`. commons' Jetty pins therefore land
at depth 2 and beat dropwizard-core's 12.1.9 at depth 3 outright. Every Jetty artifact in the booking
service jar resolves **12.1.12** — no split, on commons 1.0.31.

The corrected statement is simply: **all three of booking, booking-bridge and visibility depend on the
same commons; the two that declare it directly win, the one that reaches it transitively loses.** The
booking-lambdas jar is a side note, not the explanation.

(Worth noting separately: `booking` also carries test-scope Jetty at 12.0.2 and 12.0.8 —
`jetty-proxy`, `jetty-alpn-*`, `jetty-client`. Test scope is not shaded, so it does not reach the jar
or the scan, but it is another symptom of nothing centrally managing Jetty.)

### 10.2 Would adding a direct `commons` dependency to visibility have fixed it?

**For Jetty, yes. For the ticket as a whole, no — and it carries a real regression risk.**

#### What it would fix

Declaring `commons` in each of the ten deployable visibility poms puts its pins at depth 2, strictly
nearer than dropwizard-core's depth 3. No tie, so declaration order would not even matter. That closes
CVE-2026-10050 and CVE-2026-10051 exactly the way it is closed for booking and booking-bridge.

Note it has to go in **each deployable module**, not in `visibility-commons`. `visibility-commons`
already declares `commons` at its own depth 1; from `visibility-inbound`'s point of view that is still
depth 2, which is precisely the losing position.

#### What it would not fix

| Finding | Why a direct `commons` does not help |
|---|---|
| **CVE-2026-71290** — httpclient5 (CRITICAL) | commons declares httpclient5 **5.4.4**, the affected version. Moving it to depth 2 makes the *vulnerable* version win more decisively. This gets **worse**, not better. |
| **CVE-2023-2976** — Guava (HIGH) | commons declares no Guava at all in its published pom, so no new node enters the graph. guice's 31.0.1-jre still wins where it wins today. |
| **CVE-2026-34479 / -34477 / -49844** — log4j | commons' published pom mentions log4j-api only inside `<exclusions>`. Unaffected. |

So the approach closes one of the two HIGH families and neither the CRITICAL nor the Guava HIGH.

#### The regression risk, concretely: Jest

Adding `commons` at depth 1 promotes **all ~50 of its direct dependencies** from depth 3 to depth 2 for
every deployable. They would then start winning version contests they currently lose. The clearest
example is already visible in the resolved tree:

```
[INFO] |  +- io.searchbox:jest:jar:6.3.1:compile                                    <- from cloud-sdk-api
[INFO] |  |  +- (io.searchbox:jest:jar:5.3.3:compile - omitted for conflict with 6.3.1)   <- from commons
```

`cloud-sdk-api` asks for Jest **6.3.1**; `commons` asks for **5.3.3**. Today 6.3.1 wins. Move commons to
depth 1 and 5.3.3 wins — a **major-version downgrade of the Elasticsearch client** in the modules that
do the actual ES work (matcher, outbound, s3-archiver). Jest 5.x and 6.x differ in the ES REST API level
they speak; visibility runs ES 6.8.13. That is a silent, build-green, runtime-breaking change.

Jest is the one that is obvious from the tree. Others in the same position include `poi` 5.3.0,
`mybatis`, `mysql-connector` 8.0.16, `handlebars`, `spring-security-crypto`, and the Jackson datatype
modules. Each would need checking.

Two smaller edges: `visibility-commons` declares `commons` with exclusions for `spring-security-crypto`
and `mysql-connector-java`; a fresh direct declaration in ten poms would have to repeat them or those
artifacts return. And `commons` also brings `commons-lang3` **3.13.0** — the module overrides the root
pom's 3.20.0 in `commons/pom.xml:16` — which is the source of the CVE-2025-48924 MEDIUM already seen in
`visibility-error-email` (§5.4); at depth 2 that older version would spread to the other nine modules.

#### Why `dependencyManagement` was chosen instead

| | Direct `commons` dependency | `dependencyManagement` (what this ticket did) |
|---|---|---|
| Mechanism | wins a proximity contest | states a constraint outright |
| Jetty | fixed | fixed |
| httpclient5 CRITICAL | **entrenched at 5.4.4** | fixed |
| Guava HIGH | not fixed | fixed |
| Artifacts affected | all ~50 of commons' direct deps move a level | exactly the four named |
| Failure mode | silent version flips (Jest 6.3.1 → 5.3.3) | none — a managed version is explicit and greppable |
| Survives graph changes | no — a new shorter path re-breaks it | yes |

The proximity approach is the one commons already uses internally (§9.2) and it is exactly what failed
here. Repeating it one level up would have worked for Jetty by luck of the graph, not by construction.

**However** — the observation behind the question is the right one, and it points at the real fix: the
reason booking and booking-bridge are safe is an accident of how their poms are written. That is not a
property anyone should rely on, which is the whole argument for §9.3.1.

### 10.3 Why does `commons` depend on `cloud-sdk-api` and `cloud-sdk-aws`?

`commons/pom.xml:421-432` declares both, unconditionally and at compile scope:

```xml
<!-- Cloud SDK API Module -->
<dependency>
  <groupId>com.inttra.mercury</groupId>
  <artifactId>cloud-sdk-api</artifactId>
  <version>${dependency.version}</version>
</dependency>
<!-- Cloud SDK AWS Module -->
<dependency>
  <groupId>com.inttra.mercury</groupId>
  <artifactId>cloud-sdk-aws</artifactId>
  <version>${dependency.version}</version>
</dependency>
```

**One class needs them.** Searching the whole `commons` source tree for `com.inttra.mercury.cloudsdk`
returns a single file — `commons/src/main/java/com/inttra/mercury/config/ParameterStoreLookup.java`:

```java
import com.inttra.mercury.cloudsdk.aws.config.AwsCredentialsProviderWrapper;   // cloud-sdk-aws
import com.inttra.mercury.cloudsdk.aws.config.AwsRegionWrapper;                // cloud-sdk-aws
import com.inttra.mercury.cloudsdk.paramstore.api.CloudParameter;              // cloud-sdk-api
import com.inttra.mercury.cloudsdk.paramstore.api.CloudParameterStore;         // cloud-sdk-api
import com.inttra.mercury.cloudsdk.paramstore.config.AwsParameterStoreConfig;  // cloud-sdk-api
import com.inttra.mercury.cloudsdk.paramstore.factory.ParameterStoreClientFactory;
```

It is a `StringLookup` that resolves `${ssm:...}` placeholders in Dropwizard config YAML, used by one
other class, `ConfigProcessingServerCommand`. That is the entire justification for the edge.

There is no cycle — neither `cloud-sdk-api` nor `cloud-sdk-aws` depends on `commons`, so the layering is
`cloud-sdk-* → (nothing internal)` and `commons → cloud-sdk-*`.

#### Why it matters here

The edge is what makes the dependency graph loop back on itself from an app's point of view. A visibility
module declares `cloud-sdk-api` *and* (transitively) `commons`, and `commons` in turn re-declares
`cloud-sdk-api` — so the same coordinates appear at several depths, and which of commons' or
cloud-sdk-api's opinion about a shared library wins comes down to arithmetic on path lengths. That is the
machinery behind §8.1.

There is also a layering smell worth naming, in the opposite direction. `cloud-sdk-api` — the module
`commons` depends on — pulls `dropwizard-core:5.0.2` at compile scope for exactly **one import**:

```java
// cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/config/ManagedCloudResource.java
import io.dropwizard.lifecycle.Managed;
```

`ManagedCloudResource` is a 50-line adapter that calls `resource.close()` on shutdown. `Managed` is a
two-method interface (`start()`, `stop()`) that lives in **`dropwizard-lifecycle`**, not
`dropwizard-core`. So the whole Dropwizard server stack — and with it Jetty 12.1.9, `dropwizard-jetty`,
`jetty-ee10-servlet`, `metrics-jetty12`, `logback-access-jetty12` — is exported to every consumer of
`cloud-sdk-api` to satisfy one interface.

Sizing the alternatives:

| Option | Jetty artifacts still exported | Effort |
|---|---|---|
| today: `dropwizard-core` | 8 (server, util, security, session, http, io, ee10-servlet, ee10-servlets) | — |
| swap to `dropwizard-lifecycle` | 2 (`jetty-server`, `jetty-util`, which it declares) | one line |
| `dropwizard-lifecycle` + Jetty exclusions | 0 — `Managed` is a plain interface and needs no Jetty to implement | one line + two exclusions |
| move `ManagedCloudResource` to a `cloud-sdk-dropwizard` module | 0, and `cloud-sdk-api` becomes framework-free | small refactor, cleanest |

Any of the last three removes the 12.1.9 source that caused this ticket. This is the same conclusion as
§9.3.2, now with the exact reason the dependency exists and how little is actually used.

#### Is the `commons → cloud-sdk-*` edge itself worth removing?

Probably, but it is lower priority and not required to fix anything here. `ParameterStoreLookup` and
`ConfigProcessingServerCommand` are both AWS/Dropwizard-specific configuration plumbing; they sit more
naturally in a `cloud-sdk-dropwizard` (or `commons-config`) module than in the general-purpose `commons`
that every service depends on. Splitting them would let `commons` drop both cloud-sdk edges and would
flatten the graph noticeably. But the Jetty problem is fixed by §9.3.2 alone, so this is a tidiness
argument rather than a correctness one.
