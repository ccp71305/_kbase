# PISE_OUT (QA) — `Not in GZIP format` on NetworkServiceClient — Root Cause & Fix

- **Date:** 2026-09-03
- **Jira / branch:** ION-16417 — `feature/ION-16417-pise-out-gzip-issue`
- **Service:** `PISE_OUT-qa` (ECS `ANEQAPI-001`, acct `642960533737`) = Maven module `pi-statusevents-out-processor`
- **Shared code:** `pi-commons` (`NetworkServiceClient`), commons `JerseyClientModule`
- **Session:** `59a4c1b2109b487d`

---

## 1. Summary

`PISE_OUT-qa` logs, in a tight retry loop, for every Network API GET:

```
ERROR c.i.m.c.n.NetworkServiceClient : ProcessingException occurred while calling GET to following service:
https://api-beta.inttra.com/network/subscription/shipping-instruction/-100:
java.util.zip.ZipException: Not in GZIP format
```

**Root cause (verified): the partner-integrator OWASP pin `httpclient5 = 5.6.4`.**
Apache httpclient5 **5.6.4** (its 5.5+ content-compression rewrite) transparently decompresses a
`Content-Encoding: gzip` response at the transport layer **even though Dropwizard calls
`disableContentCompression(true)`**. Dropwizard's Jersey `GZipDecoder` then runs a **second** gunzip over the
already-decompressed JSON (`[{…`, magic `5b 7b`, not `1f 8b`) → `ZipException: Not in GZIP format`.

The AWS SDK v1→v2 upgrade code and `NetworkServiceClient` itself are **not** the cause. Dropwizard 5 / jakarta
were already in place; the only change that flips this behaviour is the httpclient5 `5.6.4` bump.

**Fix (verified end-to-end against the live QA gateway using the shaded fat-jar):** remove the `5.6.4` pin so the
reactor falls back to the **`5.4.4`** that `commons` pins, and suppress the two CVEs behind the pin because they
only affect code paths partner-integrator does not use (async client + SCRAM auth).

---

## 2. Evidence

### 2.1 Live logs (acct 642960533737, log group `inttra2-qa-lg-pi`)
- The error repeats every ~30 s in 3-error bursts (the `NetworkServiceClient` 3-retry loop), across multiple
  endpoints (`…/subscription/shipping-instruction/-100`, `…/reference/participants?inttraCompanyId=…`).
- CloudWatch Logs Insights over 60 days: **first-ever occurrence `2026-09-03 00:41:22 UTC`**, ~1 min after a fresh
  app boot at `00:40` (`jetty-12.1.12` — the OWASP-pinned build). **Zero occurrences before that deploy** → a clean
  regression introduced by the deployed partner-integrator OWASP/upgrade build.

### 2.2 The gateway is healthy
Hitting `api-beta` directly with a real token: HTTP 200, `Content-Encoding: gzip`, body is a **single valid gzip**
(556 bytes, magic `1f 8b`) that gunzips **once** to 1347 bytes of JSON (`[{"hashKey":…`). Small responses (e.g.
`/auth`, 449 bytes) are returned **uncompressed**, which is why token calls succeed and only larger gzipped
responses fail.

### 2.3 The client build is correct in principle
`commons` builds the JAX-RS client in `JerseyClientModule` via `new JerseyClientBuilder(env).using(config).build()`
with a default `JerseyClientConfiguration` (`gzipEnabled=true`; no partner-integrator yaml overrides `jerseyClient`).
Dropwizard's `JerseyClientBuilder.build()` calls `HttpClientBuilder.disableContentCompression(isGzipEnabled())` — so
with gzip on it *disables* Apache's auto-decompression and uses only its own `GZipDecoder`. That should be a single
decode.

### 2.4 httpclient5 5.6.4 vs 5.4.4 — the behavioural change
Bytecode of `org.apache.hc.client5.http.impl.classic.HttpClientBuilder` differs materially between versions
(contradicting the "no API changes" note on the old pin):
- **5.4.4:** `ContentCompressionExec(List, Lookup, boolean)` / `ContentCompressionExec(boolean)`.
- **5.6.4:** `ContentCompressionExec(List, Lookup)` / `ContentCompressionExec()` **plus a new
  `org.apache.hc.client5.http.entity.compress.DecompressingEntity`** decode path (the 5.5+ rewrite).

### 2.5 Definitive reproduction — the shaded fat-jar
The reactor (unshaded) classpath decodes correctly on 5.6.4, but the **deployed shaded fat-jar** does not. Running
the real failing call through the shaded artifact against live `api-beta` (`GzipProbe`, throwaway):

| Shaded fat-jar httpclient5 | `jerseyClient.gzipEnabled` | Result |
|---|---|---|
| **5.6.4** | `true` (prod default) | ❌ `ZipException: Not in GZIP format` |
| **5.6.4** | `false` | ✅ decodes once → full 1347-byte JSON |
| **5.4.4** (pin removed) | `true` (prod default) | ✅ decodes once → full 1347-byte JSON |

The stack trace shows a single `io.dropwizard.jersey.gzip.GZipDecoder.aroundReadFrom` receiving **already-plain**
JSON — i.e. the first decompression happened at the httpclient5 transport layer.

---

## 3. Root cause (one line)

httpclient5 **5.6.4** auto-decompresses the gzip response at the transport layer despite Dropwizard's
`disableContentCompression(true)`; Dropwizard's Jersey `GZipDecoder` decodes it again → `ZipException`. Only the
partner-integrator OWASP `5.6.4` pin introduced this; `commons` pins the safe `5.4.4`.

---

## 4. Fix applied (this branch)

1. **Remove the pin.** Deleted `<httpclient5.version>5.6.4</httpclient5.version>` and its `dependencyManagement`
   entry from `partner-integrator/pom.xml`; the reactor now resolves httpclient5 **5.4.4** (commons' pin).
   Verified: rebuilt `pi-statusevents-out-processor` shaded jar bundles `httpclient5-5.4.4.jar` and the live probe
   passes with the production default `gzipEnabled=true`.
2. **Suppress the two CVEs** (not applicable to our usage) in every partner-integrator module `suppressions.xml`:
   - `CVE-2026-71290` — **async** client TLS hostname verification bypass.
   - `CVE-2026-40542` — **SCRAM-SHA-256** mutual auth bypass.
   The Dropwizard JAX-RS client is the **classic/sync** httpclient5 (`DropwizardApacheConnector.client` =
   `org.apache.hc.client5.http.impl.classic.CloseableHttpClient`) with bearer-token auth, so neither path is
   reachable.
3. **Regression guard.** `pi-commons` test
   `com.inttra.mercury.common.networkservices.GzipResponseDecodeTest` — a hermetic test that builds the client via
   the production `JerseyClientBuilder(Environment)` path and asserts a `Content-Encoding: gzip` response is decoded
   exactly once.

### Alternative fix (not applied)
Setting `jerseyClient.gzipEnabled: false` (+ `gzipEnabledForRequests: false`) in each service yaml also fixes it
(verified): Dropwizard stops registering its `GZipDecoder` and lets httpclient5 handle gzip once. Rejected in favour
of the version revert because the revert is one central change, removes an unnecessary/incorrect pin, and keeps the
gzip behaviour identical to every other module on the `commons` stack.

---

## 5. Verification checklist

- [x] Reproduced in prod: live QA logs, first occurrence at the `2026-09-03 00:40 UTC` deploy, zero before.
- [x] Reproduced locally through the **shaded fat-jar** against live `api-beta` (5.6.4 + gzipEnabled=true → fail).
- [x] Fix confirmed: shaded fat-jar with httpclient5 **5.4.4** + gzipEnabled=true → success.
- [x] Alternative confirmed: shaded fat-jar 5.6.4 + gzipEnabled=false → success.
- [x] `mvn -pl partner-integrator/pi-commons test -Dtest=GzipResponseDecodeTest` → green on 5.4.4.
- [ ] Deploy to QA and confirm the `NetworkServiceClient` errors stop.
- [ ] OWASP dependency-check green with the new suppressions.

---

## 6. Notes / scope

- Same latent risk applies to **any** module that ships httpclient5 `5.6.4` with a Dropwizard gzip-enabled Jersey
  client. `visibility` carries an identical `5.6.4` pin — out of scope here but should get the same treatment.
- `commons` (`InttraServer` / `JerseyClientModule`) is unchanged; the fix is entirely in `partner-integrator`.

## 7. References

- `partner-integrator/pom.xml` (pin removed)
- `partner-integrator/*/suppressions.xml` (CVE suppressions)
- `partner-integrator/pi-commons/.../networkservices/GzipResponseDecodeTest.java`
- `partner-integrator/pi-commons/.../networkservices/NetworkServiceClient.java`
- commons `JerseyClientModule.java`, `ApplicationConfiguration.java`, `InttraServer.java`
- Session `59a4c1b2109b487d`
