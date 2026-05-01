# Handlebars OWASP Vulnerability Impact Analysis

**Date:** 2026-04-23  
**Analyst:** Arijit Kundu  
**Current Version:** com.github.jknack:handlebars:4.3.1  
**Latest Available:** com.github.jknack:handlebars:4.5.0 (2025-08-07)  
**Project:** mercury-services-commons  

---

## 1. Executive Summary

The OWASP dependency-check report flags **5 CVEs** (1 CRITICAL, 4 HIGH) against a bundled JavaScript file (`handlebars-v4.7.7.js`) inside the `handlebars` JAR. These CVEs target the **JavaScript** Handlebars library (versions 4.0.0–4.7.8), not the Java API.

**Key finding:** The codebase uses only the Java-native Handlebars API for email template rendering. The embedded JavaScript file is never executed. Furthermore, even the latest Java library version (4.5.0) still bundles the same `handlebars-v4.7.7.js` — upgrading alone will not resolve these CVE flags.

**Risk Assessment: LOW** — The vulnerable code paths (JS `compile()`, CLI precompiler, `@partial-block`, `resolvePartial()`, decorator registration) exist only in the embedded JavaScript and are not invoked by the Java runtime in this codebase.

---

## 2. CVEs Identified

| CVE | Severity | Summary | Affected |
|-----|----------|---------|----------|
| CVE-2026-33937 | **CRITICAL** | NumberLiteral AST node code injection via `Handlebars.compile()` | handlebars.js 4.0.0–4.7.8 |
| CVE-2026-33941 | HIGH | CLI precompiler string injection | handlebars.js 4.0.0–4.7.8 |
| CVE-2026-33938 | HIGH | `@partial-block` mutation vulnerability | handlebars.js 4.0.0–4.7.8 |
| CVE-2026-33940 | HIGH | `resolvePartial()` bypass causing undefined return | handlebars.js 4.0.0–4.7.8 |
| CVE-2026-33939 | HIGH | Unregistered decorator causes undefined function call | handlebars.js 4.0.0–4.7.8 |

All 5 CVEs affect the **JavaScript** handlebars library (`handlebars-v4.7.7.js`), which is embedded as a resource file inside the `com.github.jknack:handlebars` JAR. The Java library bundles this JS file to support optional JavaScript engine integration (Nashorn/Rhino).

---

## 3. Modules Using Handlebars

### 3.1 Active Module: `cloud-sdk-aws`

**Dependency declaration:** `cloud-sdk-aws/pom.xml` (uses `${jknack.handlebars.version}` from parent)

**Classes with Handlebars imports:**

| Class | Usage | Public API Exposure |
|-------|-------|---------------------|
| `HandlebarsTemplateServiceImpl` | Core template engine — implements `TemplateService` interface. Creates `Handlebars` instance, registers 11 custom helpers, compiles templates from JSON data. | **None** — returns `String` via interface. Handlebars is internal implementation detail. |
| `HandlebarsEmailTemplate` | Data class wrapping a compiled `Template` object with subject, sender, recipients. | **YES** — `getBodyTemplate()` and `getSubjectTemplate()` return `com.github.jknack.handlebars.Template` type. |
| `HandlebarsSelfDefinedExpressionHelpers` | Inner class defining 11 custom Handlebars helpers (date formatting, string ops, conditionals). | None — internal to `HandlebarsTemplateServiceImpl`. |
| `SesEmailServiceImpl` | Uses `TemplateService` (interface) to render email bodies before sending via SES. | None — consumes interface only. |
| `EmailClientFactory` | Factory that creates `HandlebarsTemplateServiceImpl` instances; returns `TemplateService` interface type. | None — returns interface type. |
| `HandlebarsTemplateEmailSender` | **DEPRECATED** — indirect Handlebars usage via TemplateService. | None. |

### 3.2 Deprecated Module: `email-sender`

**Status:** DEPRECATED (per team confirmation)  
**Dependency declaration:** `email-sender/pom.xml`  
**Usage:** Contains `HandlebarsTemplateEmailSender` which uses Handlebars for email template rendering. No further investment planned.

### 3.3 Deprecated Module: `dynamo-client`

**Status:** DEPRECATED (per team confirmation)  
**Handlebars dependency:** None — does not use Handlebars.

### 3.4 Module: `cloud-sdk-api`

**Handlebars dependency:** None — contains only interfaces (`TemplateService`, `EmailTemplate`, etc.).

---

## 4. How Handlebars Is Used

### 4.1 Template Processing Flow

1. Email template definitions (subject + body as Handlebars template strings) are loaded from JSON data at runtime
2. `HandlebarsTemplateServiceImpl` creates a `Handlebars` instance with the Java API
3. Templates are compiled using `Handlebars.compileInline()` (Java method, NOT the JS `compile()`)
4. 11 custom helpers are registered for date formatting, string operations, and conditionals
5. Compiled templates are applied against a data model (`Map<String, Object>`) to produce HTML email bodies
6. The rendered HTML is sent via AWS SES

### 4.2 JavaScript Engine Usage

**None.** The codebase does NOT:
- Import or use `javax.script.ScriptEngine`, Nashorn, or Rhino
- Call any method that triggers the embedded JavaScript file
- Use `Handlebars.compilePrecompile()` or any JS-engine-backed compilation path

The Java Handlebars library has its own ANTLR-based parser that processes templates natively in Java. The embedded `handlebars-v4.7.7.js` exists only as an optional feature for JS engine integration that this project does not use.

---

## 5. Public API Impact Assessment

### 5.1 Type Leakage

`HandlebarsEmailTemplate` exposes `com.github.jknack.handlebars.Template` through public getter methods:
- `getBodyTemplate()` → returns `Template`
- `getSubjectTemplate()` → returns `Template`

This means downstream consumers that directly use `HandlebarsEmailTemplate` (rather than the `EmailTemplate` interface) have a compile-time dependency on the Handlebars `Template` type. Any breaking changes to the `Template` interface in a Handlebars upgrade could affect them.

### 5.2 Interface Boundary

All other classes hide Handlebars behind the `TemplateService` interface. The `EmailClientFactory` returns `TemplateService`, not the concrete `HandlebarsTemplateServiceImpl`. This means most downstream consumers are insulated from Handlebars internals.

---

## 6. Upgrade Analysis

### 6.1 Available Versions

| Version | Release Date | Key Changes |
|---------|-------------|-------------|
| 4.3.1 (current) | 2022-10-18 | Current version |
| 4.4.0 | 2024-03-06 | Minor improvements |
| 4.5.0 | 2025-08-07 | Java 21 ArrayList fix, commons-lang3 bump (CVE-2025-48924 fix), JVM version check removal |

### 6.2 Critical Finding: Upgrade Does NOT Resolve These CVEs

**The `handlebars-v4.7.7.js` file is identical across all versions (4.3.1, 4.4.0, 4.5.0).** The last update to this bundled JS file was ~5 years ago when it was upgraded to handlebars.js 4.7.7.

Since the CVEs affect handlebars.js 4.0.0–4.7.8, and even the latest Java library (4.5.0) still bundles 4.7.7, **upgrading the Java library version will not resolve the OWASP scanner findings.**

### 6.3 Upgrade Benefits (Independent of CVEs)

Upgrading to 4.5.0 would still provide:
- Fix for `commons-lang3` CVE-2025-48924 (separate vulnerability)
- Java 21 compatibility fix (ArrayList `getLast` method)
- Removal of JVM version check

---

## 7. Mitigation Options

### Option A: Upgrade + OWASP Suppression (RECOMMENDED)

1. **Upgrade** `jknack.handlebars.version` from `4.3.1` → `4.5.0` to get the commons-lang3 CVE fix and Java 21 compatibility
2. **Add OWASP suppression** for the 5 JS-specific CVEs with documented justification that the embedded JavaScript file is not executed
3. **Effort:** Low
4. **Risk:** Low — the JS code is not invoked; suppression is justified

### Option B: Upgrade + Shade/Exclude the JS File

1. Upgrade to 4.5.0
2. Use maven-shade-plugin to exclude `handlebars-v4.7.7.js` from the final JAR
3. **Effort:** Medium — requires shade plugin configuration and testing
4. **Risk:** Low — if JS engine integration is truly unused, removing the file has no impact. However, if any transitive code path attempts to load the resource, it would fail at runtime.

### Option C: Replace Handlebars with Alternative

1. Replace Handlebars with a different template engine (e.g., Mustache.java, Thymeleaf, FreeMarker)
2. **Effort:** High — requires rewriting template processing, migrating 11 custom helpers, updating all template definitions, extensive testing
3. **Risk:** Medium — functional regression risk
4. **Not recommended** unless there are additional drivers beyond this CVE

### Option D: No Action (Accept Risk)

1. Document that the CVEs apply to JS code paths not used by this application
2. Accept the OWASP report findings with risk documentation
3. **Effort:** Minimal
4. **Risk:** Audit/compliance findings may not accept this without suppression entries

---

## 8. Recommendation

**Proceed with Option A: Upgrade to 4.5.0 + OWASP suppression.**

- The upgrade provides genuine value (commons-lang3 CVE fix, Java 21 compat)
- The 5 handlebars.js CVEs are false positives in context — the JS file is bundled but never executed
- OWASP suppression entries with clear justification satisfy compliance requirements
- Lowest effort, lowest risk approach

### Pre-Upgrade Checklist

- [ ] Fix duplicate `jknack.handlebars.version` property in root `pom.xml` (declared at lines 42 and 48)
- [ ] Update version from 4.3.1 to 4.5.0
- [ ] Review Handlebars 4.4.0 and 4.5.0 changelogs for breaking changes
- [ ] Run full test suite (`mvn clean verify`)
- [ ] Add OWASP suppression file for the 5 JS CVEs
- [ ] Verify OWASP report no longer flags these after suppression

---

## 9. Appendix: Handlebars Custom Helpers

The following 11 custom helpers are registered in `HandlebarsSelfDefinedExpressionHelpers`:

| Helper | Purpose |
|--------|---------|
| `formatDate` | Date formatting |
| `dateFormat` | Alternative date formatting |
| `ifEquals` | Equality conditional |
| `ifNotEquals` | Inequality conditional |
| `toLowerCase` | String lowercase |
| `toUpperCase` | String uppercase |
| `substring` | String substring |
| `replace` | String replacement |
| `concat` | String concatenation |
| `ifContains` | String contains check |
| `math` | Arithmetic operations |

These helpers use standard Handlebars Java API (`registerHelper`) and are unaffected by the JS-specific CVEs.
