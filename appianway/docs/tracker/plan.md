# Development plan

← [Tracker home](README.md)


## Build order

`shared` comes first; every step keeps the full reactor build green.

| Step | Scope |
|---|---|
| 1a | Surefire on the JUnit Platform (Jupiter + Vintage, existing JUnit 4 tests unchanged); commons 1.0.38-SNAPSHOT coordinates; root pins aligned up to commons: Jetty 12.1.14, Jackson 2.21.8, logback 1.5.38 (classic and core as a pair), slf4j 2.0.18; gen2-parser's local logback/slf4j overrides removed |
| 1b | Commons config chain (`PropertiesSubstitutionConfigProvider` → `TrimConfigCommentsTransform` → `ParameterStoreConfigTransform`); U1 fallback = small `shared` command keeping `run (yaml) (properties...)`; config golden test (every module YAML × every environment) |
| 1c | Back-pressure listener on `MessagingClient<String>` (waits for a permit instead of spinning); client profile per role (incl. transformer metrics helper); cloud-sdk → `RecoverableException` mapping |
| 1d | Workspace S3, SQS sender, SNS publisher, health checks, v2 Guice module; golden byte-identical tests |
| 1e | cloud-sdk fakes, JUnit 5 functional-test base, `AwsSdkBoundaryArchTest`; functional-testing pins aligned |
| 2 | event-writer, error-processor, email-sender |
| 3 | dispatcher, splitter, transformer, distributor, distributor-rest, ingestor |
| 4 | watermill-publisher, watermill platform + booking / visibility / cargoscreen / itv-gps consumers; watermill pins aligned |
| 5 | Delete AWS SDK v1 code and v1 fakes from `shared` |

## Backward compatibility and performance

- Wire formats identical (C1–C9): `shared` `Json` for every payload; S3 string put `text/plain`; REPLACE copy sends `application/octet-stream`; SQS `failedAttempts` + `DelaySeconds`; SNS plain JSON array.
- One client per role, built at startup; health checks reuse the injected clients.
- S3 client without an API-call timeout (large reads are not capped); size via HEAD, not a download.
- Listener back-pressure kept (receive at most the idle-worker count).

<a id="upstream-commons-asks"></a>
## Upstream commons asks

| Id | Plan |
|---|---|
| U1, U2, U4, U5, U6, U7, U10 | Interface-only fallbacks, as in the design |
| U3 (size HEAD) | No fallback without a download ([A2](closed-items.md#a2)) |
| U8 (SES message id), U9 (SES retry) | No fallback; block email-sender until released ([A1](actions.md#a1)) |
| U15 (missing key not at ERROR, low) | None needed: one ERROR line per storage-read health check until released ([F21](findings.md#f21)) |

Full specification of every ask: [commons upgrade specs](../redesign/2026-11-11-sdk-commons-upgrade-specs.md).
